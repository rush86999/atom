from datetime import datetime
import copy
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import update
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import (
    AgentRegistry, HITLAction, HITLActionStatus, User, UserRole,
)

logger = logging.getLogger(__name__)

# Durable approval receipt key inside the EXISTING ``HITLAction.context_snapshot``
# JSON column. No second table/registry: one append-only list keeps every
# reviewed proposal and the exact effective parameters the human approved.
HITL_PARAMETER_HISTORY_KEY = "parameter_history"

# Where a parameter receipt starts/ends. ``_MISSING`` lets the atomic claim
# distinguish "leave the column untouched" from an explicit ``None``/``{}``.
_MISSING = object()


def _copy_json_value(value: Any) -> Any:
    """Deep-copy a JSON-ish HITL value so history can never alias live params."""
    return copy.deepcopy(value)


def _history_scan(
    action: Any,
) -> Tuple[List[Dict[str, Any]], int, bool]:
    """Return (well-formed entries, malformed element count, unreadable).

    Malformed elements are NEVER dropped from storage and NEVER silently
    counted as history. They are reported so a reader can say the lineage is
    incomplete instead of claiming a complete append-only chain.
    """
    snapshot = getattr(action, "context_snapshot", None)
    if snapshot is None:
        return [], 0, False
    if not isinstance(snapshot, dict):
        return [], 0, True
    raw = snapshot.get(HITL_PARAMETER_HISTORY_KEY)
    if raw is None:
        return [], 0, False
    if isinstance(raw, dict):
        return [raw], 0, False
    if isinstance(raw, list):
        known = [entry for entry in raw if isinstance(entry, dict)]
        return known, len(raw) - len(known), False
    return [], 0, True


def _history_entries(action: Any) -> List[Dict[str, Any]]:
    return _history_scan(action)[0]


def _next_revision(entries: List[Dict[str, Any]]) -> int:
    """Next revision number from the well-formed entries actually stored."""
    revisions: List[int] = []
    for entry in entries:
        value = entry.get("revision")
        if isinstance(value, int) and not isinstance(value, bool):
            revisions.append(value)
    return (max(revisions) + 1) if revisions else (len(entries) + 1)


def _append_parameter_history(
    snapshot: Any,
    *,
    reviewed_params: Any,
    approved_params: Any,
    actor_id: Optional[str],
    reason: Optional[str] = None,
    decided_at: Any = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Pure append: return (new snapshot, appended entry) without mutating.

    The existing list is copied verbatim, including malformed elements, so a
    later write can never erase material it did not understand. A snapshot
    that is not a JSON object, or a history container that is neither a list,
    an object, nor absent, refuses to record rather than overwrite.
    """
    base = snapshot if snapshot is not None else {}
    if not isinstance(base, dict):
        return None, None

    existing = base.get(HITL_PARAMETER_HISTORY_KEY)
    if existing is None:
        raw_entries: List[Any] = []
        known: List[Dict[str, Any]] = []
    elif isinstance(existing, dict):
        raw_entries = [existing]
        known = [existing]
    elif isinstance(existing, list):
        # Preserve EVERY element (dict or not) in its original position.
        raw_entries = list(existing)
        known = [entry for entry in raw_entries if isinstance(entry, dict)]
    else:
        return None, None

    try:
        reviewed_copy = _copy_json_value(reviewed_params)
        approved_copy = _copy_json_value(approved_params)
    except Exception:  # noqa: BLE001 - never fake a receipt
        return None, None

    when = decided_at
    if when is None:
        when = datetime.now()
    when_text = when.isoformat() if hasattr(when, "isoformat") else str(when)

    reason_text: Optional[str]
    if reason is None:
        reason_text = None
    else:
        reason_text = str(reason)
        if not reason_text.strip():
            reason_text = None

    entry = {
        "revision": _next_revision(known),
        "reviewed_params": reviewed_copy,
        "approved_params": approved_copy,
        "modified": reviewed_copy != approved_copy,
        "modified_by": str(actor_id) if actor_id not in (None, "") else None,
        "modified_at": when_text,
        "reason": reason_text,
    }
    raw_entries.append(entry)

    updated = dict(base)
    updated[HITL_PARAMETER_HISTORY_KEY] = raw_entries
    return updated, entry


def record_approved_parameters(
    action: Any,
    *,
    reviewed_params: Any,
    approved_params: Any,
    actor_id: Optional[str],
    reason: Optional[str] = None,
    decided_at: Any = None,
) -> Optional[Dict[str, Any]]:
    """Append the review/approval parameter receipt to the HITL row.

    The original reviewed payload is copied BEFORE any caller assigns the
    effective payload to ``action.params``. Both values are deep-copied into
    ``context_snapshot[HITL_PARAMETER_HISTORY_KEY]``, which is the existing
    durable JSON history field on the row, and every previous entry is kept
    (append-only). The scan is deliberately narrow: this is the same protected
    authority row the approval itself writes, not a new audit payload.

    Returns the appended entry, or ``None`` when the existing snapshot is not
    a JSON object / cannot be copied. A malformed snapshot is left untouched:
    the approval still commits with the effective params, and the readback
    reports the original as unknown instead of inventing one.
    """
    when = decided_at
    if when is None:
        when = getattr(action, "reviewed_at", None) or datetime.now()
    updated, entry = _append_parameter_history(
        getattr(action, "context_snapshot", None),
        reviewed_params=reviewed_params,
        approved_params=approved_params,
        actor_id=actor_id,
        reason=reason,
        decided_at=when,
    )
    if updated is None or entry is None:
        logger.error(
            "HITL %s parameter history not recorded: existing snapshot/"
            "history is not appendable",
            getattr(action, "id", None))
        return None
    action.context_snapshot = updated
    return entry


def _redact_history_value(
    value: Any, *, redact: bool,
) -> Any:
    """Project one JSON value through the existing repo sanitizers."""
    copied = _copy_json_value(value)
    if not redact or copied is None:
        return copied
    from core.blueprint_sanitizer import strip_credentials

    return strip_credentials(copied)


def _redact_history_reason(
    value: Any, *, redact: bool,
) -> Any:
    if not redact or not value:
        return value
    from core.secrets_redactor import redact_before_storage

    return redact_before_storage(str(value))


def describe_parameter_history(
    action: Any, *, redact: bool = True, max_revisions: int = 20,
) -> Dict[str, Any]:
    """Read back the review/approval parameter lineage for one HITL row.

    New approvals carry an append-only receipt. Historical rows approved
    before this receipt existed have NO recorded original: their
    ``original_params`` is ``None`` and ``original_known`` is ``False`` — the
    current ``params`` are reported as the effective payload, never passed off
    as the reviewed original.

    ``redact=True`` (default) applies the repo's existing
    ``core.blueprint_sanitizer.strip_credentials`` sanitizer to the projection
    so a general audit/export surface cannot dump credential-shaped keys. The
    raw values remain only in the protected HITL authority row; use
    ``redact=False`` only inside trusted server-side code.
    """
    entries, malformed_entries, history_unreadable = _history_scan(action)
    latest = entries[-1] if entries else None
    status = str(getattr(action, "status", "") or "")
    current_params = _copy_json_value(getattr(action, "params", None))

    if latest is not None:
        original = _copy_json_value(latest.get("reviewed_params"))
        effective = _copy_json_value(latest.get("approved_params"))
        original_known = (
            "reviewed_params" in latest
            and latest.get("reviewed_params") is not None)
        modified = latest.get("modified")
        if modified is None and original_known:
            modified = original != effective
        revision = latest.get("revision")
        modified_by = latest.get("modified_by")
        modified_at = latest.get("modified_at")
        reason = latest.get("reason")
        legacy_unrecorded = not original_known
    elif status == HITLActionStatus.APPROVED.value:
        # The approval may have rewritten params before this receipt existed.
        # Do not reconstruct a reviewed original from the rewritten value.
        original = None
        effective = current_params
        original_known = False
        modified = None
        revision = None
        modified_by = None
        modified_at = None
        reason = None
        legacy_unrecorded = True
    else:
        # Pending/rejected rows never had a params rewrite path, so the
        # current payload is still the reviewed proposal. Effective params
        # exist only after an approval.
        original = current_params
        effective = None
        original_known = isinstance(current_params, dict)
        modified = None
        revision = None
        modified_by = None
        modified_at = None
        reason = None
        legacy_unrecorded = False

    history_complete = not malformed_entries and not history_unreadable

    # Bounded revision projection. Most recent N revisions only; the total is
    # reported so a reader never mistakes the page for the whole lineage.
    try:
        revision_limit = int(max_revisions)
    except (TypeError, ValueError):
        revision_limit = 20
    revision_limit = max(0, revision_limit)
    selected = entries[-revision_limit:] if revision_limit else []
    revisions: List[Dict[str, Any]] = []
    for entry in selected:
        revisions.append({
            "revision": entry.get("revision"),
            "reviewed_params": _redact_history_value(
                entry.get("reviewed_params"), redact=redact),
            "approved_params": _redact_history_value(
                entry.get("approved_params"), redact=redact),
            "modified": entry.get("modified"),
            "modified_by": entry.get("modified_by"),
            "modified_at": entry.get("modified_at"),
            "reason": _redact_history_reason(
                entry.get("reason"), redact=redact),
        })

    reviewed_at = getattr(action, "reviewed_at", None)
    result: Dict[str, Any] = {
        "status": status,
        "original_known": bool(original_known),
        "original_params": original,
        "effective_params": effective,
        "modified": modified,
        "revision": revision,
        "modified_by": modified_by,
        "modified_at": modified_at,
        "reason": reason,
        "reviewed_by": str(getattr(action, "reviewed_by", None) or "") or None,
        "reviewed_at": (
            reviewed_at.isoformat()
            if hasattr(reviewed_at, "isoformat") else reviewed_at),
        "history_entries": len(entries),
        "legacy_unrecorded": legacy_unrecorded,
        "revisions": revisions,
        "revisions_truncated": len(entries) > len(selected),
        "history_complete": history_complete,
        "malformed_history_entries": malformed_entries,
        "history_unreadable": history_unreadable,
        "redacted": bool(redact),
    }
    if redact:
        # Existing repo sanitizer (P5 sharing surfaces); deep-copies and drops
        # credential-shaped KEYS. Never mutates the stored authority values.
        from core.blueprint_sanitizer import strip_credentials

        if result["original_params"] is not None:
            result["original_params"] = strip_credentials(
                result["original_params"])
        if result["effective_params"] is not None:
            result["effective_params"] = strip_credentials(
                result["effective_params"])
        if result["reason"]:
            # Free text: the existing text sanitizer redacts key/password/PII
            # patterns that a JSON key denylist cannot see.
            from core.secrets_redactor import redact_before_storage

            result["reason"] = redact_before_storage(str(result["reason"]))
    return result


def _refusal(
    message: str, error_code: str, http_status: int,
    action_id: Optional[str] = None,
) -> Dict[str, Any]:
    """One refusal shape for every intervention decision surface.

    ``success: False`` keeps the historical service contract; the explicit
    HTTP status/code lets governance/approval routes answer 401/403/404/409
    instead of flattening a scope denial into a generic 400 or a 500.
    """
    result: Dict[str, Any] = {
        "success": False,
        "message": message,
        "error_code": error_code,
        "http_status": int(http_status),
    }
    if action_id:
        result["action_id"] = action_id
    return result


def _exact_column(column: Any, value: Any):
    """NULL-safe scalar equality for a conditional claim predicate."""
    return column.is_(None) if value is None else column == value


def _exact_json_column(column: Any, value: Any):
    """NULL-safe equality for a JSON column.

    SQLAlchemy's JSON type stores Python ``None`` as the JSON text ``null``
    (not SQL NULL) unless ``none_as_null`` is set, so ``IS NULL`` alone misses
    both the shipped model default and rows written by other dialects. Match
    either representation; non-null values compare through the JSON bind.
    """
    from sqlalchemy import String, cast, or_

    if value is None:
        return or_(column.is_(None), cast(column, String) == "null")
    return column == value


def resolve_decision_reviewer(
    db: Session, action: Any, reviewer_id: Any,
) -> Dict[str, Any]:
    """Resolve the CURRENT reviewer for one ordinary HITL decision.

    Reuses the shared fresh-actor read (never the request's stale token/object)
    and the shared role policy for BOTH persisted ``required_role`` locations.
    Scope is checked against the row's canonical tenant/workspace: the
    Personal/default scope is the one universal fallback (an unscoped admin
    decides rows in a named workspace), but a NAMED-scope reviewer may never
    cross into a different named workspace/tenant or an unscoped row. A
    guessed/cross-scope id is therefore a 404, not a confirmed decision.

    This is a read; the caller MUST still run ``claim_fresh_reviewer`` and the
    conditional ``claim_pending_decision`` in the same transaction.
    """
    from core.goal_run_decision_service import (
        _resolve_actor,
        canonical_scope_id,
    )
    from core.security.rbac import persisted_required_roles, required_role_denial

    authority = _resolve_actor(db, reviewer_id)
    if not authority.get("ok"):
        return {
            "ok": False,
            "http_status": int(authority.get("http_status") or 401),
            "error_code": str(
                authority.get("error_code") or "AUTHENTICATION_REQUIRED"),
            "message": str(
                authority.get("message") or "Authentication required"),
        }

    actor_workspace = canonical_scope_id(authority.get("workspace_id"))
    action_workspace = canonical_scope_id(
        getattr(action, "workspace_id", None))
    actor_tenant = canonical_scope_id(authority.get("tenant_id"))
    action_tenant = canonical_scope_id(getattr(action, "tenant_id", None))
    if (
        (actor_workspace != "default" and actor_workspace != action_workspace)
        or (actor_tenant != "default" and actor_tenant != action_tenant)
    ):
        return {
            "ok": False,
            "http_status": 404,
            "error_code": "DECISION_SCOPE_DENIED",
            "message": (
                "This approval is outside your workspace or tenant."),
        }

    denial = required_role_denial(
        authority.get("role"), persisted_required_roles(action),
        subject="approval", actor_label="Approver")
    if denial:
        return {
            "ok": False,
            "http_status": 403,
            "error_code": "AUTHORITY_REQUIRED",
            "message": denial,
        }
    return {"ok": True, "authority": authority}


def pending_decision_conditions(action: Any) -> List[Any]:
    """The exact reviewed-row fence used by ``claim_pending_decision``.

    Exposed so the dialect-specific CAS semantics can be traced (PostgreSQL
    JSONB equality is semantic; SQLite compares serialized text) without
    opening a database or claiming a run that did not happen.
    """
    return [
        HITLAction.id == str(getattr(action, "id", "") or ""),
        HITLAction.status == HITLActionStatus.PENDING.value,
        _exact_column(
            HITLAction.action_type, getattr(action, "action_type", None)),
        _exact_column(
            HITLAction.required_role, getattr(action, "required_role", None)),
        _exact_column(
            HITLAction.workspace_id, getattr(action, "workspace_id", None)),
        _exact_column(
            HITLAction.tenant_id, getattr(action, "tenant_id", None)),
        _exact_json_column(
            HITLAction.params, getattr(action, "params", None)),
        _exact_json_column(
            HITLAction.context_snapshot,
            getattr(action, "context_snapshot", None)),
    ]


def claim_pending_decision(
    db: Session,
    action: Any,
    *,
    status: str,
    reviewer_id: Any,
    effective_params: Any = _MISSING,
    user_feedback: Any = _MISSING,
    reason: Optional[str] = None,
    record_history: bool = False,
    reviewed_at: Any = None,
) -> bool:
    """Atomically claim ONE pending decision for this exact loaded review.

    A conditional ``UPDATE ... WHERE status = 'pending' AND every authority
    field still equals the row the reviewer was checked against`` is the
    fence, not a re-read. Status, effective ``params``, reviewer, review time,
    feedback and the appended ``parameter_history`` snapshot are written in
    the SAME statement/transaction. A peer that decided the row (or rewrote
    the reviewed payload, role policy or snapshot) after the load makes
    ``rowcount`` 0, so this caller gets an honest conflict instead of
    overwriting the winner. Returns True only for the single winning claim.

    ``modified_params``/``user_feedback`` semantics are the caller's: an
    omitted ``effective_params`` leaves ``params`` untouched (the legacy
    merge handler computes the merged value first), and an explicit value
    replaces it (the service's edit-before-approve contract).
    """
    if status not in (
            HITLActionStatus.APPROVED.value, HITLActionStatus.REJECTED.value):
        raise ValueError("decision status must be approved or rejected")
    reviewer = str(reviewer_id or "").strip()
    if not reviewer:
        raise ValueError("decision requires a reviewer")

    prior_params = getattr(action, "params", None)
    prior_snapshot = _copy_json_value(
        getattr(action, "context_snapshot", None))

    params_value = (
        prior_params if effective_params is _MISSING else effective_params)
    when = reviewed_at or datetime.now()

    values: Dict[str, Any] = {
        "status": status,
        "reviewed_by": reviewer,
        "reviewed_at": when,
    }
    if effective_params is not _MISSING:
        values["params"] = params_value
    if user_feedback is not _MISSING:
        values["user_feedback"] = user_feedback
    if record_history:
        updated_snapshot, _entry = _append_parameter_history(
            prior_snapshot,
            reviewed_params=prior_params if prior_params is not None else {},
            approved_params=(
                params_value if params_value is not None else {}),
            actor_id=reviewer,
            reason=reason,
            decided_at=when,
        )
        if updated_snapshot is not None:
            values["context_snapshot"] = updated_snapshot

    conditions = pending_decision_conditions(action)
    result = db.execute(
        update(HITLAction)
        .where(*conditions)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    claimed = int(result.rowcount or 0) == 1
    # The ORM object still holds the pre-claim values. Expire it so any later
    # read in this request (response/broadcast) loads the committed winner
    # rather than the stale snapshot.
    db.expire(action)
    return claimed


def _decision_read_denial(
    authority: Dict[str, Any], action: Any,
) -> Optional[Dict[str, Any]]:
    """Permission for reading one decision's history (server-derived only).

    Scope first (cross-scope is a 404 so an id is never confirmed), then:
    supervisors (team_lead+) may read any decision in their current scope;
    an ordinary member may read only their own subject/reviewed rows. No
    client-supplied owner/scope/role is consulted anywhere here.
    """
    from core.goal_run_decision_service import canonical_scope_id
    from core.security.rbac import role_level

    actor_workspace = canonical_scope_id(authority.get("workspace_id"))
    action_workspace = canonical_scope_id(
        getattr(action, "workspace_id", None))
    actor_tenant = canonical_scope_id(authority.get("tenant_id"))
    action_tenant = canonical_scope_id(getattr(action, "tenant_id", None))
    if (
        (actor_workspace != "default" and actor_workspace != action_workspace)
        or (actor_tenant != "default" and actor_tenant != action_tenant)
    ):
        return _refusal(
            "Approval not found", "APPROVAL_NOT_FOUND", 404)

    is_supervisor = role_level(authority.get("role")) >= role_level(
        UserRole.TEAM_LEAD)
    if not is_supervisor:
        actor_id = str(authority.get("id") or "")
        subject = str(getattr(action, "user_id", None) or "")
        reviewer = str(getattr(action, "reviewed_by", None) or "")
        if actor_id not in (subject, reviewer):
            return _refusal(
                "Only the approval's owner or its authorized reviewer can "
                "read this decision history.",
                "AUTHORITY_REQUIRED", 403)
    return None


def get_decision_history(
    action_id: str, actor_id: Any, *, revision_limit: int = 10,
) -> Dict[str, Any]:
    """Bounded, permission-scoped decision history for the Approvals UI.

    Returns ``{"success": True, "history": {...}}`` or the shared refusal
    envelope. The projection is redacted by default (existing repo
    sanitizers); the protected ``context_snapshot`` is never returned raw and
    no credential payload is dumped.
    """
    from sqlalchemy.exc import SQLAlchemyError

    from core.goal_run_decision_service import _resolve_actor

    try:
        with get_db_session() as db:
            authority = _resolve_actor(db, actor_id)
            if not authority.get("ok"):
                return _refusal(
                    str(authority.get("message") or "Authentication required"),
                    str(authority.get("error_code")
                        or "AUTHENTICATION_REQUIRED"),
                    int(authority.get("http_status") or 401),
                )
            action = db.query(HITLAction).filter(
                HITLAction.id == str(action_id)).first()
            if action is None:
                return _refusal(
                    "Approval not found", "APPROVAL_NOT_FOUND", 404)
            denial = _decision_read_denial(authority, action)
            if denial is not None:
                return denial
            history = describe_parameter_history(
                action, max_revisions=revision_limit)
            history["approval_id"] = action.id
            history["action_type"] = action.action_type
            history["agent_id"] = action.agent_id
            return {"success": True, "history": history}
    except SQLAlchemyError:
        logger.exception(
            "HITL %s decision history unreadable", action_id)
        return _refusal(
            "Decision history is temporarily unavailable; retry.",
            "HISTORY_UNAVAILABLE", 503)


def list_recent_decisions(
    actor_id: Any, *, limit: int = 20,
) -> Dict[str, Any]:
    """Bounded recent decisions the caller may see (discoverability read).

    Same scope/role policy as the history read, applied in SQL with the
    caller's DB-derived scope. No row params or snapshots are returned: this
    is a navigation list, the per-decision history is fetched lazily.
    """
    from sqlalchemy import func, or_
    from sqlalchemy.exc import SQLAlchemyError

    from core.goal_run_decision_service import (
        _resolve_actor,
        canonical_scope_id,
    )
    from core.security.rbac import role_level

    try:
        with get_db_session() as db:
            authority = _resolve_actor(db, actor_id)
            if not authority.get("ok"):
                return _refusal(
                    str(authority.get("message") or "Authentication required"),
                    str(authority.get("error_code")
                        or "AUTHENTICATION_REQUIRED"),
                    int(authority.get("http_status") or 401),
                )

            try:
                bounded = int(limit)
            except (TypeError, ValueError):
                bounded = 20
            bounded = max(1, min(bounded, 100))

            query = db.query(HITLAction).filter(HITLAction.status.in_(
                ("approved", "rejected", "expired", "executed")))
            # Scope filters are EXACT for a named scope. The Personal/default
            # actor keeps the existing unscoped read (never widened with an
            # ``OR workspace IS NULL`` predicate).
            if canonical_scope_id(authority.get("workspace_id")) != "default":
                query = query.filter(
                    HITLAction.workspace_id == authority["workspace_id"])
            if canonical_scope_id(authority.get("tenant_id")) != "default":
                query = query.filter(
                    HITLAction.tenant_id == authority["tenant_id"])

            is_supervisor = role_level(
                authority.get("role")) >= role_level(UserRole.TEAM_LEAD)
            if not is_supervisor:
                query = query.filter(or_(
                    HITLAction.user_id == authority["id"],
                    HITLAction.reviewed_by == authority["id"],
                ))

            rows = query.order_by(
                func.coalesce(
                    HITLAction.reviewed_at, HITLAction.created_at).desc()
            ).limit(bounded).all()

            decisions = []
            for action in rows:
                decisions.append({
                    "id": action.id,
                    "action_type": action.action_type,
                    "status": str(action.status or ""),
                    "reviewed_by": (
                        str(action.reviewed_by or "") or None),
                    "reviewed_at": (
                        action.reviewed_at.isoformat()
                        if hasattr(action.reviewed_at, "isoformat")
                        else action.reviewed_at),
                    "created_at": (
                        action.created_at.isoformat()
                        if hasattr(action.created_at, "isoformat")
                        else action.created_at),
                    "has_parameter_history": bool(
                        _history_entries(action)),
                })
            return {"success": True, "decisions": decisions}
    except SQLAlchemyError:
        logger.exception("Recent HITL decisions unreadable")
        return _refusal(
            "Decision history is temporarily unavailable; retry.",
            "HISTORY_UNAVAILABLE", 503)


class InterventionService:
    """
    Service for managing Human-in-the-Loop (HITL) interventions.
    Handles creation, retrieval, and resolution of HITL actions.
    """
    
    async def request_intervention(
        self,
        workspace_id: str,
        action_type: str,
        platform: str,
        params: Dict[str, Any],
        reason: str,
        agent_id: Optional[str] = None,
        user_id: Optional[str] = None,
        required_role: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new HITL action request in the database.

        ``required_role`` (from governance config ``roles`` map) is persisted
        in ``context_snapshot`` so the approval surface can enforce it; the
        kwarg was already being passed by mcp_service._check_hitl_policy —
        before it existed here every governed intercept raised TypeError and
        failed closed into "policy check unavailable".
        """
        try:
            with get_db_session() as db:
                hitl_action = HITLAction(
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    action_type=action_type,
                    platform=platform,
                    params=params, # SQLAlchemy JSON type handles dict
                    reason=reason,
                    context_snapshot={"required_role": required_role} if required_role else None,
                    status=HITLActionStatus.PENDING.value
                )
                db.add(hitl_action)
                db.commit()
                db.refresh(hitl_action)
                
                logger.info(f"Created HITL action {hitl_action.id} for agent {agent_id}")
                
                return {
                    "status": "PAUSED",
                    "action_id": hitl_action.id,
                    "message": f"Action paused for human review: {reason}",
                    "requires_approval": True
                }
        except Exception as e:
            logger.error(f"Failed to request intervention: {e}")
            return {
                "status": "ERROR",
                "message": f"Failed to persist intervention request: {str(e)}"
            }

    def get_pending_interventions(
        self,
        workspace_id: str = None,
        user_id: str = None,
        tenant_id: str = None,
        include_legacy_unscoped: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get pending interventions, optionally filtered by workspace or user
        ownership.

        Resource scoping is applied whenever a workspace/tenant is supplied —
        including the literal ``"default"`` workspace. The previous
        ``workspace_id != "default"`` exception made the default workspace a
        cross-workspace read, which is exactly how a guessed approval id could
        leak or approve another assignment. Legacy rows with no workspace are
        included only when the caller explicitly asks for them.
        """
        with get_db_session() as db:
            query = db.query(HITLAction).filter(
                HITLAction.status == HITLActionStatus.PENDING.value)

            if workspace_id:
                if include_legacy_unscoped:
                    from sqlalchemy import or_
                    query = query.filter(or_(
                        HITLAction.workspace_id == workspace_id,
                        HITLAction.workspace_id.is_(None),
                    ))
                else:
                    query = query.filter(
                        HITLAction.workspace_id == workspace_id)
            if tenant_id:
                query = query.filter(HITLAction.tenant_id == tenant_id)
            if user_id:
                query = query.filter(HITLAction.user_id == user_id)

            actions = query.all()
            
            results = []
            for action in actions:
                agent_name = "Unknown Agent"
                if action.agent_id:
                    agent = db.query(AgentRegistry).filter(AgentRegistry.id == action.agent_id).first()
                    if agent:
                        agent_name = agent.name
                
                results.append({
                    "id": action.id,
                    "agent_id": action.agent_id,
                    "agent_name": agent_name,
                    "user_id": action.user_id,
                    "action_type": action.action_type,
                    "platform": action.platform,
                    "params": action.params,
                    "reason": action.reason,
                    "created_at": action.created_at.isoformat(),
                    "status": action.status
                })
            return results

    async def approve_intervention(
        self,
        action_id: str,
        approver_id: str,
        modified_params: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approve a pending intervention.

        Enforces the per-action ``required_role`` persisted by
        ``request_intervention`` (from the governance config ``roles`` map):
        the approver must hold at least that role. Unknown role strings fail
        closed. ``modified_params`` replaces the action's params so the row
        reflects what was actually approved (the UI "Modify before approve"
        flow).

        The exact reviewed (original) and approved (effective) payloads are
        appended to the row's existing ``context_snapshot`` history before the
        ``params`` column is rewritten. Execution therefore keeps consuming
        the effective payload, while an auditor can still read what the human
        was shown. ``reason`` is the approver's optional note; when absent it
        is recorded as unknown rather than invented.
        """
        with get_db_session() as db:
            action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
            if not action:
                return {"success": False, "message": "Action not found"}

            if action.status != HITLActionStatus.PENDING.value:
                return _refusal(
                    f"Action is {action.status}, cannot approve.",
                    "DECISION_CONFLICT", 409, action.id)

            # A never-autonomous TASK admission is a human admission for ONE
            # exact task execution. Its status is not authority: the current
            # reviewer must be verified (exact canonical scope, persisted
            # owner or supervisor, BOTH required_role locations) and the
            # server-owned task/rule binding must be immutable. This runs
            # BEFORE any status write, so governance/bridge callers cannot be
            # the weak surface. The same reviewer fence and the atomic
            # pending-state/binding claim are re-checked in the write below.
            is_task_admission = (
                str(action.action_type or "") == "never_autonomous_task")
            if is_task_admission:
                from core.review_decision_authority import (
                    authorize_task_admission_decision,
                    claim_task_admission_reviewer,
                )

                check = authorize_task_admission_decision(
                    db, action, approver_id,
                    modified_params=modified_params)
                if not check.get("ok"):
                    return _refusal(
                        check["message"], check["error_code"],
                        check["http_status"], action.id)
                if not claim_task_admission_reviewer(
                        db, check["authority"]):
                    db.rollback()
                    return _refusal(
                        "Reviewer authority changed; refresh and retry.",
                        "AUTHORITY_CHANGED", 409, action.id)

            # A goal-run checkpoint is not a status-only intervention: its
            # decision and the run wake are one atomic claim, bound to the
            # run's exact current wait. Governance/messaging callers reach
            # this service with arbitrary HITL ids, so this is the shared
            # guard that keeps them from committing an approved checkpoint
            # row without resuming (the original defect). Reviewer authority
            # (active user, exact scope, owner/supervisor, required_role) is
            # enforced inside the claim, so every checkpoint entry answers
            # the SAME refusal shape/status. Every other action_type keeps
            # the historical path below unchanged.
            if str(action.action_type or "") == "goal_run_checkpoint":
                if modified_params is not None:
                    return _refusal(
                        "A checkpoint's reviewed scope cannot be rewritten "
                        "during approval; refresh the run and decide the "
                        "current checkpoint.",
                        "CHECKPOINT_REVIEW_IMMUTABLE", 409, action.id)
                from core.hitl_resume import resolve_goal_run_checkpoint

                outcome = await resolve_goal_run_checkpoint(
                    action_id,
                    approved=True,
                    reviewer_id=approver_id,
                    db=db,
                )
                if not outcome.get("resumed"):
                    return _refusal(
                        outcome.get("message") or (
                            "This checkpoint is no longer current; refresh "
                            "the run."),
                        str(outcome.get("error_code")
                            or "CHECKPOINT_STALE"),
                        int(outcome.get("http_status") or 409),
                        action.id,
                    )
                return {
                    "success": True,
                    "message": "Checkpoint approved",
                    "action_id": action.id,
                    "resumed": True,
                    "resume": outcome,
                }

            denial = self._required_role_denial(db, action, approver_id)
            if denial:
                return _refusal(
                    denial, "AUTHORITY_REQUIRED", 403, action.id)

            if is_task_admission:
                # Atomic pending-state + immutable binding + fresh-actor
                # claim. A peer that rejected/approved the row (or rewrote
                # its execution/task/rule/profile binding) after our load
                # makes this UPDATE miss; the stale approver never wins.
                from core.review_decision_authority import (
                    claim_task_admission_decision,
                )

                if not claim_task_admission_decision(
                        db, action,
                        status=HITLActionStatus.APPROVED.value,
                        reviewer_id=approver_id):
                    db.rollback()
                    return _refusal(
                        "This task admission was decided or its reviewed "
                        "task binding changed; refresh and retry.",
                        "TASK_ADMISSION_DECISION_CONFLICT", 409, action.id)
            else:
                # Same durable authority seam as rejection: resolve the
                # CURRENT reviewer (fresh active user, canonical scope, both
                # persisted required_role locations), then fence that actor
                # and the exact reviewed row in the SAME transaction as the
                # status/params/history write. A peer decision or a role/
                # scope/payload change after the load makes the claim miss.
                authority = resolve_decision_reviewer(
                    db, action, approver_id)
                if not authority.get("ok"):
                    return _refusal(
                        authority["message"], authority["error_code"],
                        authority["http_status"], action.id)
                from core.goal_run_decision_service import claim_fresh_reviewer

                if not claim_fresh_reviewer(db, authority["authority"]):
                    db.rollback()
                    return _refusal(
                        "Reviewer authority changed; refresh and retry.",
                        "AUTHORITY_CHANGED", 409, action.id)

                claimed = claim_pending_decision(
                    db, action,
                    status=HITLActionStatus.APPROVED.value,
                    reviewer_id=approver_id,
                    effective_params=(
                        modified_params if modified_params is not None
                        else _MISSING),
                    reason=reason,
                    record_history=True,
                )
                if not claimed:
                    db.rollback()
                    return _refusal(
                        "This approval was already decided, or its reviewed "
                        "payload/authority changed; refresh and retry.",
                        "DECISION_CONFLICT", 409, action.id)

            db.commit()

            # In a real system, this would resume the suspended workflow/agent.
            # For now, we just mark it approved. The agent/workflow needs to poll or be triggered.

            return {
                "success": True,
                "message": "Action approved",
                "action_id": action.id
            }

    async def reject_intervention(self, action_id: str, approver_id: str, reason: str) -> Dict[str, Any]:
        """
        Reject a pending intervention.

        Enforces the same ``required_role`` gate as approval — rejection is
        also a governance decision.
        """
        with get_db_session() as db:
            action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
            if not action:
                return {"success": False, "message": "Action not found"}

            if action.status != HITLActionStatus.PENDING.value:
                return _refusal(
                    f"Action is {action.status}, cannot reject.",
                    "DECISION_CONFLICT", 409, action.id)

            is_task_admission = (
                str(action.action_type or "") == "never_autonomous_task")
            if is_task_admission:
                from core.review_decision_authority import (
                    authorize_task_admission_decision,
                    claim_task_admission_reviewer,
                )

                check = authorize_task_admission_decision(
                    db, action, approver_id)
                if not check.get("ok"):
                    return _refusal(
                        check["message"], check["error_code"],
                        check["http_status"], action.id)
                if not claim_task_admission_reviewer(
                        db, check["authority"]):
                    db.rollback()
                    return _refusal(
                        "Reviewer authority changed; refresh and retry.",
                        "AUTHORITY_CHANGED", 409, action.id)

            if str(action.action_type or "") == "goal_run_checkpoint":
                from core.hitl_resume import resolve_goal_run_checkpoint

                outcome = await resolve_goal_run_checkpoint(
                    action_id,
                    approved=False,
                    reviewer_id=approver_id,
                    guidance=reason,
                    db=db,
                )
                if not outcome.get("resumed"):
                    return _refusal(
                        outcome.get("message") or (
                            "This checkpoint is no longer current; refresh "
                            "the run."),
                        str(outcome.get("error_code")
                            or "CHECKPOINT_STALE"),
                        int(outcome.get("http_status") or 409),
                        action.id,
                    )
                return {
                    "success": True,
                    "message": "Checkpoint rejected",
                    "action_id": action.id,
                    "resumed": True,
                    "resume": outcome,
                }

            denial = self._required_role_denial(db, action, approver_id)
            if denial:
                return _refusal(
                    denial, "AUTHORITY_REQUIRED", 403, action.id)

            if is_task_admission:
                from core.review_decision_authority import (
                    claim_task_admission_decision,
                )

                if not claim_task_admission_decision(
                        db, action,
                        status=HITLActionStatus.REJECTED.value,
                        reviewer_id=approver_id,
                        user_feedback=reason):
                    db.rollback()
                    return _refusal(
                        "This task admission was decided or its reviewed "
                        "task binding changed; refresh and retry.",
                        "TASK_ADMISSION_DECISION_CONFLICT", 409, action.id)
            else:
                # Resolution + fresh-actor fence + conditional pending claim:
                # the rejection, reviewer and feedback commit atomically, and
                # a peer answer/role/scope change after the load cannot be
                # overwritten (the loser gets an honest conflict).
                authority = resolve_decision_reviewer(
                    db, action, approver_id)
                if not authority.get("ok"):
                    return _refusal(
                        authority["message"], authority["error_code"],
                        authority["http_status"], action.id)
                from core.goal_run_decision_service import claim_fresh_reviewer

                if not claim_fresh_reviewer(db, authority["authority"]):
                    db.rollback()
                    return _refusal(
                        "Reviewer authority changed; refresh and retry.",
                        "AUTHORITY_CHANGED", 409, action.id)

                if not claim_pending_decision(
                        db, action,
                        status=HITLActionStatus.REJECTED.value,
                        reviewer_id=approver_id,
                        user_feedback=reason):
                    db.rollback()
                    return _refusal(
                        "This rejection was already decided, or the reviewed "
                        "payload/authority changed; refresh and retry.",
                        "DECISION_CONFLICT", 409, action.id)

            db.commit()

            return {
                "success": True,
                "message": "Action rejected",
                "action_id": action.id
            }

    @staticmethod
    def _required_role_denial(db: Session, action: HITLAction, approver_id: str) -> Optional[str]:
        """
        Return a denial reason if ``approver_id`` may not decide ``action``,
        else None. The approver must be a verified (existing, ACTIVE) user;
        they must hold at least EVERY persisted ``required_role`` (HITLAction
        column + governance ``context_snapshot``). Unknown role strings deny
        (fail closed).
        """
        approver = db.query(User).filter(User.id == approver_id).first()
        if (
            not approver
            or not bool(getattr(approver, "is_active", True))
            or getattr(approver, "status", None) not in (None, "active")
        ):
            return "Approver could not be verified; decision denied (fail closed)"

        # ``request_intervention`` persists the governance policy in
        # ``context_snapshot``; the HITLAction column is the durable field
        # other writers set. Both are the same policy, so EVERY persisted
        # requirement is enforced (never only the column when the snapshot is
        # stricter) and an unknown role in either location denies.
        from core.security.rbac import (
            persisted_required_roles,
            required_role_denial,
        )

        return required_role_denial(
            getattr(approver, "role", None),
            persisted_required_roles(action),
        )

# Singleton instance
intervention_service = InterventionService()
