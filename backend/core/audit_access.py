"""Read-scope and subject-authority rules for the agent action audit trail.

The audit trail is both an ordinary member's own-work record and a
supervisor's workspace review surface. This module owns the ONE general read
scope both cases share, so the four audit read endpoints and the
correction-request link writer cannot drift apart.

Scope rules (all derived from the persisted ``User`` row, never a token or a
request body):

* Ordinary member — rows whose ``user_id`` is the caller's. Unbound legacy
  rows (``user_id IS NULL``) are *not* assigned to an arbitrary member.
* Supervisor (TEAM_LEAD+) — every user's rows in the caller's CURRENT
  workspace only. There is no global all-users read.
* Workspace — a real workspace stays exact. A personal/null actor keeps the
  documented Personal-Edition default compatibility (``None``/``""``/
  ``default``), mirroring ``api.agent_routes._reader_scope``. A caller with a
  real workspace never inherits the shared default bucket.
* Active account — a deactivated or deleted account is refused even when its
  JWT is still cryptographically valid.

Execution ids are matched exactly, with LIKE metacharacters escaped, and the
parsed metadata value is re-checked in Python. A ``%``/``_`` filter can never
widen the query.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.models import AgentExecution, AuditLog, User, UserRole, UserStatus
from core.personal_scope import (
    PERSONAL_WORKSPACE_ID,
    resolve_tenant_id,
    resolve_workspace_id,
)
from core.security.rbac import user_meets_role

AUDIT_EVENT_TYPES = ("agent_action", "llm_call")
SUPERVISOR_MIN_ROLE = UserRole.TEAM_LEAD

# Execution ids are server-minted (UUIDs) but durable readers also accept
# legacy ids such as ``e1``/``legacy-1``. Percent/underscore are deliberately
# NOT accepted: they are LIKE wildcards and have no business in an id.
EXECUTION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
AUDIT_ROW_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
# Identifiers accepted for a governed correction channel target. No URLs,
# slashes, query separators or percent-encoding can pass.
CORRECTION_TARGET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")

# The only supported repair channels. The UI builds a relative link from the
# channel name plus a validated target id; the backend never stores a URL.
CORRECTION_CHANNELS: Dict[str, str] = {
    "activity": "Activity (goal run)",
    "learning": "Learning review",
    "assignment": "Assignments",
    "autodev": "Auto-Dev review",
}


class AuditAccessDenied(Exception):
    """A refusal that the API layer translates into an honest HTTP status."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def authoritative_actor(db: Session, current_user: User) -> User:
    """Return the active, current ``User`` row for an audit read.

    The token object is only a subject hint. Role, workspace and active state
    are re-read here so a stale JWT cannot preserve authority that has since
    changed or been revoked.
    """
    actor_id = str(getattr(current_user, "id", "") or "")
    if not actor_id:
        raise AuditAccessDenied(
            401, "AUTHENTICATION_REQUIRED", "Authentication required.")

    try:
        actor = (
            db.query(User)
            .filter(User.id == actor_id)
            .populate_existing()
            .first()
        )
    except Exception as exc:  # noqa: BLE001 — unreadable authority fails closed
        raise AuditAccessDenied(
            503,
            "AUDIT_AUTHORITY_UNAVAILABLE",
            "Audit authority is temporarily unavailable; retry.",
        ) from exc

    if actor is None:
        raise AuditAccessDenied(
            401, "AUTHENTICATION_REQUIRED", "Authentication required.")
    if (
        str(getattr(actor, "status", "") or "") != UserStatus.ACTIVE.value
        or getattr(actor, "is_active", None) is False
    ):
        raise AuditAccessDenied(
            403,
            "ACCOUNT_NOT_ACTIVE",
            "This account is not active. Sign in with an active account.",
        )
    return actor


def resolve_audit_scope(actor: User) -> Dict[str, Any]:
    """Resolve the supported audit read scope from the authoritative row.

    Mirrors ``api.agent_routes._reader_scope``: a real workspace stays exact;
    only an explicitly personal/null actor gets the default compatibility
    bucket. ``supervisor`` widens *whose* rows are visible, never *which*
    workspace.
    """
    raw_workspace = getattr(actor, "workspace_id", None)
    workspace = str(resolve_workspace_id(actor)).strip()
    tenant = str(resolve_tenant_id(actor)).strip()
    personal = raw_workspace in (None, "") or workspace == PERSONAL_WORKSPACE_ID
    supervisor = user_meets_role(actor, SUPERVISOR_MIN_ROLE)
    return {
        "user_id": str(actor.id),
        "workspace_id": workspace,
        "tenant_id": tenant,
        "personal": personal,
        "supervisor": supervisor,
        "kind": "workspace" if supervisor else "owner",
    }


def _workspace_condition(scope: Dict[str, Any]):
    """Workspace boundary for audit rows.

    The audit writer stamps ``workspace_id`` (falling back to ``default`` for
    legacy context-less writes). A real-workspace reader is held to its exact
    workspace; the personal reader keeps the documented default compatibility.
    """
    if scope["personal"]:
        return or_(
            AuditLog.workspace_id.is_(None),
            AuditLog.workspace_id == "",
            AuditLog.workspace_id == PERSONAL_WORKSPACE_ID,
            AuditLog.workspace_id == scope["workspace_id"],
        )
    return AuditLog.workspace_id == scope["workspace_id"]


def audit_row_condition(scope: Dict[str, Any]):
    """The single SQL predicate shared by every audit read."""
    conditions = [
        AuditLog.event_type.in_(AUDIT_EVENT_TYPES),
        _workspace_condition(scope),
    ]
    if not scope["supervisor"]:
        # Owner scope: only rows stamped with this actor. Unbound legacy rows
        # remain unassigned rather than being handed to the first member.
        conditions.append(AuditLog.user_id == scope["user_id"])
    return and_(*conditions)


def scoped_event_query(db: Session, scope: Dict[str, Any]):
    return db.query(AuditLog).filter(audit_row_condition(scope))


def execution_identifier_valid(execution_id: Any) -> bool:
    return isinstance(execution_id, str) and bool(EXECUTION_ID_RE.match(execution_id))


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def exact_execution_condition(execution_id: str):
    """JSON-fragment match for one execution id, with LIKE escaping.

    The needle is derived from ``json.dumps`` (writer/reader stay consistent)
    and every LIKE metacharacter is escaped with an explicit escape char.
    Callers must still re-check the parsed value (``row_execution_id``) so a
    serialization quirk cannot turn this into a substring match.
    """
    from core.agent_action_audit import execution_needle

    needle = execution_needle(execution_id)
    return AuditLog.metadata_json.like(
        f"%{_escape_like(needle)}%", escape="\\")


def parse_metadata(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def row_execution_id(row: AuditLog) -> Optional[str]:
    value = parse_metadata(row.metadata_json).get("agent_execution_id")
    return str(value) if value else None


def execution_workspace_visible(scope: Dict[str, Any], execution: AgentExecution) -> bool:
    """Whether an execution's frozen workspace belongs to the reader's scope."""
    workspace = getattr(execution, "workspace_id", None)
    if scope["personal"]:
        return workspace in (None, "", PERSONAL_WORKSPACE_ID, scope["workspace_id"])
    return workspace == scope["workspace_id"]


def execution_visible_to_scope(
    db: Session,
    scope: Dict[str, Any],
    execution_id: str,
) -> bool:
    """Prove an execution is inside the reader's scope before reading it.

    A member needs at least one owner-scoped audit row for the execution; the
    row's presence is the durable ownership evidence (AgentExecution itself
    has no user column). A supervisor additionally sees a workspace-bound
    execution that has no per-event trail.
    """
    if not execution_identifier_valid(execution_id):
        return False

    execution = (
        db.query(AgentExecution)
        .filter(AgentExecution.id == execution_id)
        .first()
    )
    if execution is not None and not execution_workspace_visible(scope, execution):
        return False

    owned_row = (
        scoped_event_query(db, scope)
        .filter(exact_execution_condition(execution_id))
        .first()
    )
    if owned_row is not None and row_execution_id(owned_row) == execution_id:
        return True
    if scope["supervisor"] and execution is not None:
        return True
    return False


def load_visible_audit_row(
    db: Session,
    scope: Dict[str, Any],
    audit_id: str,
) -> AuditLog:
    """Load one audit row inside the scope, or refuse without revealing it."""
    if not isinstance(audit_id, str) or not AUDIT_ROW_ID_RE.match(audit_id):
        raise AuditAccessDenied(
            404, "AUDIT_EVENT_NOT_FOUND",
            "Audit event not found in your authorized scope.")
    row = (
        db.query(AuditLog)
        .filter(AuditLog.id == audit_id)
        .filter(audit_row_condition(scope))
        .first()
    )
    if row is None:
        raise AuditAccessDenied(
            404, "AUDIT_EVENT_NOT_FOUND",
            "Audit event not found in your authorized scope.")
    return row


def correction_href(channel: str, target_id: Optional[str]) -> Optional[str]:
    """Safe, relative deep link for a supported correction channel.

    Only hard-coded path shapes are produced from a channel allowlist plus an
    id that matched ``CORRECTION_TARGET_ID_RE``. No stored value can become an
    arbitrary URL.
    """
    if channel not in CORRECTION_CHANNELS:
        return None
    if target_id is not None and not CORRECTION_TARGET_ID_RE.match(str(target_id)):
        return None
    from urllib.parse import quote

    if channel == "activity":
        return f"/goal-runs/{quote(str(target_id), safe='')}" if target_id else "/goal-runs"
    if channel == "learning":
        return f"/learning?thread={quote(str(target_id), safe='')}" if target_id else "/learning"
    if channel == "assignment":
        return f"/assignments?agent={quote(str(target_id), safe='')}" if target_id else "/assignments"
    if channel == "autodev":
        return "/agents"
    return None


def read_scope_payload(scope: Dict[str, Any]) -> Dict[str, Any]:
    """Client-facing description of what this read includes."""
    return {
        "kind": scope["kind"],
        "workspace_id": scope["workspace_id"],
        "supervisor": scope["supervisor"],
        "note": (
            "Workspace supervisor scope: every user's audited rows in the "
            "current workspace."
            if scope["supervisor"]
            else "Own scope: only audited rows recorded for your user."
        ),
    }
