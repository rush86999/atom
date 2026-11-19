"""
In-app notification service for upstream / Personal Edition.

Replaces the prior no-op stub with a real implementation that persists to the
existing ``Notification`` model (see models.py:4625) and optionally fires an
email via ``email_utils.send_smtp_email`` for high-priority notifications when
the user has opted in.

Design notes:
- ``send_notification(user_id, notification_type, data)`` signature is preserved
  bit-for-bit; existing callers (e.g. graduation service) keep working.
- Personal Edition uses ``workspace_id == "default"`` and ``tenant_id == "default"``
  (matches admin_bootstrap.py). SaaS deployments pass real IDs through ``data``.
- Email is OPT-IN. The user's preference is read from
  ``User.notification_preferences["email_enabled"]`` (default False). We never
  spam — a missing preference or an unreadable user record both mean "no email".
- Notification failures are logged but NEVER raised; graduation/promotion
  callers must not roll back on a notification glitch.
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import and_, func, insert, literal, or_, select
from sqlalchemy.orm import Session

from core.personal_scope import PERSONAL_TENANT_ID, PERSONAL_WORKSPACE_ID

logger = logging.getLogger(__name__)


def workspace_supervisor_ids(
    db: Session,
    workspace_id: Optional[str] = None,
    exclude_user_id: Optional[str] = None,
    limit: int = 25,
) -> list[str]:
    """ACTIVE users who can decide supervisor-gated actions (TEAM_LEAD+).

    For notification fan-out when the person an event would naturally
    notify (e.g. an agent's owner) is below the gate that decides it.
    Scoped to the workspace when given; capped to keep large user tables
    from turning one proposal into a mailing list.
    """
    from core.models import User, UserStatus
    from core.security.rbac import _ROLE_LEVELS, UserRole

    supervisor_roles = [
        role.value for role, level in _ROLE_LEVELS.items()
        if level >= _ROLE_LEVELS[UserRole.TEAM_LEAD]
    ]
    q = db.query(User).filter(
        User.role.in_(supervisor_roles),
        User.status == UserStatus.ACTIVE.value,
    )
    if workspace_id:
        q = q.filter(User.workspace_id == workspace_id)
    if exclude_user_id:
        q = q.filter(User.id != exclude_user_id)
    return [str(u.id) for u in q.limit(limit).all()]


# Notification types that warrant an email in addition to the in-app row.
# Kept conservative on purpose — only things a user would actually want mailed.
HIGH_PRIORITY_TYPES = {
    "agent_graduated",
    "approval_needed",
    "security_alert",
}


class NotificationService:
    """Persist notifications + dispatch optional email.

    Backwards compatible with the previous stub: the constructor signature and
    ``send_notification`` async signature are unchanged. The only difference is
    that calls now actually do something.
    """

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session

    async def send_notification(
        self,
        user_id: str,
        notification_type: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Persist a notification row and (optionally) send email.

        Args:
            user_id: Recipient user ID.
            notification_type: Free-form short string (e.g. "agent_graduated").
                High-priority types in ``HIGH_PRIORITY_TYPES`` may trigger email.
            data: Notification payload. Recognized keys:
                - title (str, required)
                - message (str, required)
                - workspace_id (str, default "default")
                - tenant_id (str, default "default")
                - action_url (str, optional)
                - action_label (str, optional)
                - priority (str, optional — "high" forces email consideration)

        Returns:
            ``{"success": bool, "notification_id": str | None, "emailed": bool}``
            — never raises on failure, only logs.
        """
        try:
            return self._persist_and_maybe_email(
                user_id=user_id,
                notification_type=notification_type,
                data=data,
            )
        except Exception as exc:
            # Critical invariant: notification glitches must NOT propagate to
            # callers (graduation, approval flows). Log and return a soft fail.
            logger.error(
                "Notification service failed (type=%s user=%s): %s",
                notification_type, user_id, exc,
            )
            return {
                "success": False,
                "notification_id": None,
                "emailed": False,
                "error": "notification_failed",
            }

    async def send_workflow_notification(
        self,
        *,
        user_id: str,
        workspace_id: str,
        tenant_id: str,
        operation_id: str,
        title: str,
        message: str,
    ) -> Dict[str, Any]:
        """Deliver one workflow step notification to an already-proven recipient.

        This is the reusable in-app boundary for workflow execution steps. It is
        deliberately separate from :meth:`send_notification`:

        * recipient and scope are REQUIRED and verified against the DB; there are
          no "default" fallbacks and no email/external fan-out,
        * ``operation_id`` is the stable execution+step idempotency key and is
          used as the ``Notification.id`` so the existing primary-key uniqueness
          protects retries and concurrent delivery,
        * the committed row is read back before reporting success,
        * a replay with identical operation material returns the original row,
          while the same operation id with different material is refused.

        Returns ``{"success": bool, "notification_id": str | None,
        "created": bool, "emailed": False, "error": str | None}``. Failures are
        reported truthfully rather than converted into a successful insert.
        """
        try:
            user_id = _required_text(user_id, "user_id")
            workspace_id = _required_text(workspace_id, "workspace_id")
            tenant_id = _required_text(tenant_id, "tenant_id")
            operation_id = _required_text(operation_id, "operation_id")
            title = _required_text(title, "title")
            message = _required_text(message, "message")
        except ValueError as exc:
            return _workflow_failure("invalid_arguments", detail=str(exc))

        try:
            return self._persist_workflow_notification(
                user_id=user_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                operation_id=operation_id,
                title=title,
                message=message,
            )
        except Exception as exc:
            # The workflow caller must see a failure; do not pretend a row was
            # written. Roll back the caller-owned session when applicable.
            self._rollback_quietly()
            logger.error(
                "Workflow notification failed (operation=%s user=%s): %s",
                operation_id, user_id, exc,
            )
            return _workflow_failure("notification_failed")

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _persist_workflow_notification(
        self,
        *,
        user_id: str,
        workspace_id: str,
        tenant_id: str,
        operation_id: str,
        title: str,
        message: str,
    ) -> Dict[str, Any]:
        from core.models import Notification  # local import avoids cycles

        _owns_session = False
        if self.db is None:
            from core.database import SessionLocal as _SL
            self.db = _SL()
            _owns_session = True

        try:
            scope_error = _workflow_scope_error(
                self.db,
                user_id=user_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
            )
            if scope_error:
                return _workflow_failure(scope_error)

            # The operation id doubles as the row id. That is the whole
            # idempotency contract: Notification.id's primary-key uniqueness
            # makes a retry/concurrent attempt collide instead of inserting a
            # second notification.
            notification_id = operation_id
            canonical_title = title[:500]

            existing = (
                self.db.query(Notification)
                .filter(Notification.id == notification_id)
                .first()
            )
            if existing is not None:
                self.db.refresh(existing)
                if _workflow_material_matches(
                    existing,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    operation_id=operation_id,
                    title=canonical_title,
                    message=message,
                ):
                    return _workflow_result(
                        notification_id=existing.id,
                        created=False,
                    )
                return _workflow_failure(
                    "operation_conflict",
                    existing_notification_id=existing.id,
                )

            # Re-evaluate the recipient's current authority inside the INSERT
            # statement itself. The scope check above only provides precise
            # early error codes; it is deliberately not the gate that decides
            # whether a row may be written. Because the authority predicate is
            # part of this one INSERT ... SELECT, a membership revocation
            # committed after the pre-check makes the statement insert zero
            # rows instead of delivering to a revoked recipient.
            try:
                insert_result = self.db.execute(
                    _workflow_notification_insert_statement(
                        notification_id=notification_id,
                        user_id=user_id,
                        workspace_id=workspace_id,
                        tenant_id=tenant_id,
                        title=canonical_title,
                        message=message,
                        metadata={
                            "notification_type": "workflow_step",
                            "operation_id": operation_id,
                            "workflow_step": True,
                        },
                    )
                )
                if insert_result.rowcount == 0:
                    # Authority was gone when the insert ran. Use a fresh
                    # transaction to recognise a concurrently committed
                    # replay, otherwise surface the denial instead of a
                    # successful notification.
                    self.db.rollback()
                    existing = (
                        self.db.query(Notification)
                        .filter(Notification.id == notification_id)
                        .first()
                    )
                    if existing is not None:
                        if _workflow_material_matches(
                            existing,
                            user_id=user_id,
                            workspace_id=workspace_id,
                            tenant_id=tenant_id,
                            operation_id=operation_id,
                            title=canonical_title,
                            message=message,
                        ):
                            return _workflow_result(
                                notification_id=existing.id,
                                created=False,
                            )
                        return _workflow_failure(
                            "operation_conflict",
                            existing_notification_id=existing.id,
                        )

                    denial = _workflow_scope_error(
                        self.db,
                        user_id=user_id,
                        workspace_id=workspace_id,
                        tenant_id=tenant_id,
                    )
                    logger.warning(
                        "Workflow notification refused by conditional insert "
                        "(operation=%s user=%s): %s",
                        operation_id,
                        user_id,
                        denial or "recipient_not_authorized",
                    )
                    return _workflow_failure(
                        denial or "recipient_not_authorized"
                    )
                self.db.commit()
            except Exception as exc:
                # A concurrent writer may have won the race on the same
                # operation id. Roll back, then read the committed row back. If
                # it matches, this attempt is a successful replay; if it does
                # not, the operation id was reused with different material.
                self.db.rollback()
                existing = (
                    self.db.query(Notification)
                    .filter(Notification.id == notification_id)
                    .first()
                )
                if existing is None:
                    logger.error(
                        "Workflow notification commit failed without an "
                        "existing row (operation=%s): %s",
                        operation_id, exc,
                    )
                    return _workflow_failure("notification_failed")
                if _workflow_material_matches(
                    existing,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    operation_id=operation_id,
                    title=canonical_title,
                    message=message,
                ):
                    return _workflow_result(
                        notification_id=existing.id,
                        created=False,
                    )
                return _workflow_failure(
                    "operation_conflict",
                    existing_notification_id=existing.id,
                )

            # Read the committed row back rather than trusting the in-memory
            # object (sessions may be configured with expire_on_commit=False).
            self.db.expire_all()
            committed = (
                self.db.query(Notification)
                .filter(Notification.id == notification_id)
                .first()
            )
            if committed is None or not _workflow_material_matches(
                committed,
                user_id=user_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                operation_id=operation_id,
                title=canonical_title,
                message=message,
            ):
                logger.error(
                    "Workflow notification read-back verification failed "
                    "(operation=%s)",
                    operation_id,
                )
                return _workflow_failure("notification_verification_failed")

            return _workflow_result(notification_id=committed.id, created=True)
        finally:
            if _owns_session:
                try:
                    self.db.close()
                except Exception:
                    pass
                self.db = None

    def _rollback_quietly(self) -> None:
        """Best-effort rollback for a caller-owned session after a failure."""
        if self.db is None:
            return
        try:
            self.db.rollback()
        except Exception:
            pass

    def _persist_and_maybe_email(
        self,
        user_id: str,
        notification_type: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        from core.models import Notification, User  # local import avoids cycles

        if self.db is None:
            # Bug 11 fix: callers using the default constructor (db=None)
            # silently lost ALL notifications (security alerts, approvals,
            # graduation). Now opens a short-lived session so the notification
            # is persisted even when the caller didn't provide one.
            from core.database import SessionLocal as _SL
            self.db = _SL()
            _owns_session = True
        else:
            _owns_session = False

        title = (data.get("title") or _default_title(notification_type)).strip()
        message = (data.get("message") or "").strip()
        if not message:
            message = title

        # Personal Edition scope: single-tenant "default". Caller may override
        # via data dict (SaaS sync paths do); otherwise use the shared constants
        # so "default" isn't hardcoded in five places. See core/personal_scope.py.
        workspace_id = data.get("workspace_id") or PERSONAL_WORKSPACE_ID
        tenant_id = data.get("tenant_id") or PERSONAL_TENANT_ID

        notification = Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            title=title[:500],
            message=message,
            type=_classify(notification_type),
            metadata_json={
                "notification_type": notification_type,
                **{k: v for k, v in data.items() if k not in {
                    "title", "message", "workspace_id", "tenant_id",
                    "action_url", "action_label",
                }},
            },
            read=False,
            action_url=data.get("action_url"),
            action_label=data.get("action_label"),
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        emailed = False
        is_high_priority = (
            notification_type in HIGH_PRIORITY_TYPES
            or str(data.get("priority", "")).lower() == "high"
        )
        if is_high_priority:
            emailed = self._maybe_send_email(
                self.db, user_id, notification_type, title, message, data
            )

        result = {
            "success": True,
            "notification_id": notification.id,
            "emailed": emailed,
        }

        # Bug 11: close the session we opened if we created it.
        if _owns_session:
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None

        return result

    def _maybe_send_email(
        self,
        db: Session,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        data: Dict[str, Any],
    ) -> bool:
        from core.models import User  # local import; see note above
        from core.email_utils import send_smtp_email

        try:
            user = db.query(User).filter(User.id == user_id).first()
        except Exception as exc:
            logger.warning(
                "Notification email: could not load user %s (%s); skipping email",
                user_id, exc,
            )
            return False

        if not user:
            return False

        # OPT-IN: never email unless the user explicitly enabled it. Default
        # is False — unreadable preferences, missing column, or falsy value all
        # mean "do not email". This is the single source of truth.
        if not _user_email_enabled(user):
            return False

        to_email = getattr(user, "email", None)
        if not to_email:
            return False

        try:
            return bool(
                send_smtp_email(
                    to_email=to_email,
                    subject=title,
                    body=message,
                )
            )
        except Exception as exc:
            logger.warning("Notification email to %s failed: %s", to_email, exc)
            return False


def _required_text(value: Any, field: str) -> str:
    """Require an explicit, non-blank string. Never choose a default."""
    if value is None:
        raise ValueError(f"{field} is required")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _workflow_result(*, notification_id: str, created: bool) -> Dict[str, Any]:
    return {
        "success": True,
        "notification_id": notification_id,
        "created": created,
        "emailed": False,
    }


def _workflow_failure(error: str, **extra: Any) -> Dict[str, Any]:
    result = {
        "success": False,
        "notification_id": None,
        "created": False,
        "emailed": False,
        "error": error,
    }
    result.update(extra)
    return result


def _workflow_scope_error(
    db: Session,
    *,
    user_id: str,
    workspace_id: str,
    tenant_id: str,
) -> Optional[str]:
    """Describe why the recipient is not currently active in exactly this scope.

    Returns a short error code, or ``None`` when the caller-supplied recipient
    and tenant/workspace all match the database. No defaults are applied here.

    This read only shapes precise error codes. It is NOT the write gate: the
    notification INSERT re-evaluates the same authority predicate in the same
    statement (see :func:`_workflow_notification_insert_statement`) so a
    revocation committed between this check and the insert cannot be bypassed.
    """
    from core.models import User, UserStatus, Workspace, user_workspaces

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return "recipient_not_found"

    status = getattr(user, "status", None)
    status_value = getattr(status, "value", status)
    is_active = getattr(user, "is_active", True)
    if str(status_value).lower() != UserStatus.ACTIVE.value or is_active in (False, 0):
        return "recipient_inactive"

    if str(getattr(user, "tenant_id", "") or "") != tenant_id:
        return "tenant_scope_mismatch"

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if workspace is None:
        return "workspace_not_found"
    if str(getattr(workspace, "tenant_id", "") or "") != tenant_id:
        return "workspace_scope_mismatch"

    # A user may be assigned to the workspace directly (User.workspace_id) or
    # through the user_workspaces membership table. Both are DB facts; either
    # one proves the exact workspace for this recipient.
    if str(getattr(user, "workspace_id", "") or "") == workspace_id:
        return None

    membership = db.execute(
        select(user_workspaces.c.user_id).where(
            user_workspaces.c.user_id == user_id,
            user_workspaces.c.workspace_id == workspace_id,
        )
    ).first()
    if membership is None:
        return "workspace_scope_mismatch"
    return None


def _workflow_notification_insert_statement(
    *,
    notification_id: str,
    user_id: str,
    workspace_id: str,
    tenant_id: str,
    title: str,
    message: str,
    metadata: Dict[str, Any],
):
    """Build the conditional workflow-notification insert.

    The recipient's authority is a predicate of the same ``INSERT ... SELECT``
    that writes the row, so membership cannot be revoked between an
    authorisation read and the write: the database evaluates the predicate
    when the insert executes. A denial inserts zero rows.

    Authority matches :func:`_workflow_scope_error`: the recipient is active,
    in the requested tenant, and is either directly assigned to the exact
    workspace or has an explicit membership row for it. The workspace itself
    must exist in that tenant.
    """
    from core.models import (
        Notification,
        User,
        UserStatus,
        Workspace,
        user_workspaces,
    )

    notifications = Notification.__table__
    users = User.__table__
    workspaces = Workspace.__table__
    memberships = user_workspaces

    workspace_in_tenant = (
        select(workspaces.c.id)
        .where(
            workspaces.c.id == workspace_id,
            workspaces.c.tenant_id == tenant_id,
        )
        .exists()
    )
    exact_membership = or_(
        users.c.workspace_id == workspace_id,
        select(memberships.c.user_id)
        .where(
            memberships.c.user_id == users.c.id,
            memberships.c.workspace_id == workspace_id,
        )
        .exists(),
    )
    authority = and_(
        users.c.id == user_id,
        func.lower(users.c.status) == UserStatus.ACTIVE.value,
        or_(users.c.is_active.is_(None), users.c.is_active.is_(True)),
        users.c.tenant_id == tenant_id,
        workspace_in_tenant,
        exact_membership,
    )

    return insert(notifications).from_select(
        [
            notifications.c.id,
            notifications.c.user_id,
            notifications.c.workspace_id,
            notifications.c.tenant_id,
            notifications.c.title,
            notifications.c.message,
            notifications.c.type,
            notifications.c.metadata_json,
            notifications.c.read,
            notifications.c.action_url,
            notifications.c.action_label,
        ],
        select(
            literal(notification_id, type_=notifications.c.id.type),
            literal(user_id, type_=notifications.c.user_id.type),
            literal(workspace_id, type_=notifications.c.workspace_id.type),
            literal(tenant_id, type_=notifications.c.tenant_id.type),
            literal(title, type_=notifications.c.title.type),
            literal(message, type_=notifications.c.message.type),
            literal(_classify("workflow_step"), type_=notifications.c.type.type),
            literal(metadata, type_=notifications.c.metadata_json.type),
            literal(False, type_=notifications.c.read.type),
            literal(None, type_=notifications.c.action_url.type),
            literal(None, type_=notifications.c.action_label.type),
        )
        .select_from(users)
        .where(authority),
    )


def _workflow_material_matches(
    notification,
    *,
    user_id: str,
    workspace_id: str,
    tenant_id: str,
    operation_id: str,
    title: str,
    message: str,
) -> bool:
    """True only when an existing row represents this exact operation."""
    metadata = getattr(notification, "metadata_json", None) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    # The row id is the operation id, so a pre-existing row with the same
    # caller-supplied material is a replay. If metadata explicitly names a
    # different operation, treat it as a conflict rather than silently reusing
    # the row.
    metadata_operation_id = metadata.get("operation_id")
    if metadata_operation_id is not None and metadata_operation_id != operation_id:
        return False

    return (
        str(getattr(notification, "user_id", "") or "") == user_id
        and str(getattr(notification, "workspace_id", "") or "") == workspace_id
        and str(getattr(notification, "tenant_id", "") or "") == tenant_id
        and (getattr(notification, "title", None) or "") == title
        and (getattr(notification, "message", None) or "") == message
    )


def _user_email_enabled(user) -> bool:
    """Return True only if the user has explicitly opted into email.

    Reads from ``User.notification_preferences["email_enabled"]`` (JSON column,
    already in the schema). Falls back to checking the legacy
    ``email_notifications_enabled`` attribute if a migration adds it later.
    """
    prefs = getattr(user, "notification_preferences", None)
    if isinstance(prefs, dict) and prefs.get("email_enabled") is True:
        return True
    if getattr(user, "email_notifications_enabled", False) is True:
        return True
    return False


def _classify(notification_type: str) -> str:
    """Map a free-form notification_type to the Notification.type enum bucket."""
    t = (notification_type or "").lower()
    if "error" in t or "alert" in t or "security" in t:
        return "error"
    if "warning" in t or "approval" in t:
        return "warning"
    if "success" in t or "graduat" in t or "promot" in t:
        return "success"
    return "info"


def _default_title(notification_type: str) -> str:
    """Human-readable fallback title when the caller omits one."""
    if notification_type == "agent_graduated":
        return "Your agent graduated to the next tier"
    if notification_type == "approval_needed":
        return "An approval is needed"
    if notification_type == "security_alert":
        return "Security alert"
    return "New notification"
