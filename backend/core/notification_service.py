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

from sqlalchemy.orm import Session

from core.personal_scope import PERSONAL_TENANT_ID, PERSONAL_WORKSPACE_ID

logger = logging.getLogger(__name__)


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

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _persist_and_maybe_email(
        self,
        user_id: str,
        notification_type: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        from core.models import Notification, User  # local import avoids cycles

        if self.db is None:
            # No session means we can't persist. Log and bail without raising.
            logger.warning(
                "NotificationService called without a db session; skipping (type=%s user=%s)",
                notification_type, user_id,
            )
            return {"success": False, "notification_id": None, "emailed": False}

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

        return {
            "success": True,
            "notification_id": notification.id,
            "emailed": emailed,
        }

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
