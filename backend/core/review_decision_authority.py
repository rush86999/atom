"""Reviewer authority for durable TASK-admission HITL decisions.

A ``never_autonomous_task`` row is a human admission for ONE exact task
execution. Its ``approved``/``executed`` status is not, by itself, authority:
the persisted reviewer must still be a real, currently active principal in
the row's EXACT canonical tenant/workspace, and must be the persisted owner
or an authorized supervisor under the same policy every other HITL decision
uses. Missing, unknown, inactive or foreign reviewers cannot mint a task
clearance.

This module is deliberately a thin seam over the existing shared mechanisms:

* ``core.goal_run_decision_service`` already resolves the CURRENT actor from
  a fresh session (``_resolve_actor``), canonicalises Personal-Edition
  NULL/``default`` scope (``canonical_scope_id``) and exposes the conditional
  UPDATE fresh-actor fence (``claim_fresh_reviewer``).
* ``core.security.rbac`` already merges and enforces BOTH persisted
  ``required_role`` locations (HITLAction column + governance snapshot).

It adds only the task-admission binding/provenance checks; there is no second
policy registry and no alternate role map.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy import update

from core.autonomy_policy import (
    NEVER_TASK_ADMISSION_ACTION,
    NEVER_OUTCOME_REVIEW,
    decision_covers,
)
from core.models import HITLAction, HITLActionStatus
from core.goal_run_decision_service import (
    _resolve_actor,
    canonical_scope_id,
    claim_fresh_reviewer,
)
from core.models import UserRole
from core.security.rbac import (
    persisted_required_roles,
    required_role_denial,
    role_level,
)

logger = logging.getLogger(__name__)

_ACCEPTED_STATUSES = ("approved", "executed")


def _refusal(
    http_status: int, error_code: str, message: str,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "http_status": int(http_status),
        "error_code": str(error_code),
        "message": str(message),
    }


def _nonempty(value: Any) -> str:
    return str(value if value is not None else "").strip()


def task_admission_action(action: Any) -> bool:
    return str(getattr(action, "action_type", "") or "") == (
        NEVER_TASK_ADMISSION_ACTION)


def task_admission_binding_denial(action: Any) -> Optional[str]:
    """Return a refusal message when the server-owned task binding is malformed.

    The binding is written by ``task_admission_params`` before any human sees
    the row. It is immutable thereafter: the exact execution, task
    fingerprint, persisted owner, reviewed rule revisions and resolved task
    profile are what the human reviewed. A row missing any of them cannot
    authorise today's task merely because somebody flipped its status.
    """
    params = getattr(action, "params", None)
    if not isinstance(params, Mapping):
        return "The task-admission binding is missing or unreadable."

    execution_id = _nonempty(params.get("execution_id"))
    if not execution_id:
        return "The task-admission binding names no execution."

    fingerprint = _nonempty(params.get("task_fingerprint"))
    if not fingerprint:
        return "The task-admission binding has no reviewed task fingerprint."

    owner = _nonempty(params.get("owner_user_id"))
    if not owner:
        return "The task-admission binding has no persisted owner."
    row_owner = _nonempty(getattr(action, "user_id", None))
    if not row_owner or row_owner != owner:
        return (
            "The task-admission owner binding changed; a fresh review is "
            "required.")

    bindings = params.get("rule_bindings")
    if not isinstance(bindings, (list, tuple)) or not bindings:
        return "The task-admission binding has no reviewed rule revisions."
    for entry in bindings:
        if not isinstance(entry, Mapping):
            return "The reviewed rule revisions are malformed."
        if not _nonempty(entry.get("id")):
            return "The reviewed rule revisions are malformed."
        try:
            revision = int(entry.get("revision"))
        except (TypeError, ValueError):
            return "The reviewed rule revisions are malformed."
        if revision < 0:
            return "The reviewed rule revisions are malformed."

    profile = params.get("task_profile")
    if not isinstance(profile, Mapping):
        return "The reviewed task profile is missing."
    profile_owner = _nonempty(profile.get("owner_user_id"))
    if profile_owner and profile_owner != owner:
        return (
            "The reviewed task profile does not belong to the persisted "
            "owner.")

    snapshot = getattr(action, "context_snapshot", None)
    if isinstance(snapshot, Mapping):
        bound = _nonempty(
            snapshot.get("execution_id") or snapshot.get("run_id"))
        if bound and bound != execution_id:
            return (
                "The task-admission execution binding changed; a fresh "
                "review is required.")
        snapshot_owner = _nonempty(snapshot.get("user_id"))
        if snapshot_owner and snapshot_owner != owner:
            return (
                "The task-admission owner binding changed; a fresh review is "
                "required.")
    return None


def resolve_task_admission_reviewer(
    db: Any, action: Any, reviewer: Any,
) -> Dict[str, Any]:
    """Resolve the CURRENT reviewer and decide whether they may decide the row.

    Reuses the shared fresh-actor read (the caller's request object is never
    trusted) plus the shared role policy for BOTH persisted required_role
    locations. Cross-scope is a 404 so an id from another workspace/tenant is
    never confirmed; an in-scope non-owner/non-supervisor is a 403.
    """
    authority = _resolve_actor(db, reviewer)
    if not authority.get("ok"):
        return authority

    action_workspace = canonical_scope_id(
        getattr(action, "workspace_id", None))
    action_tenant = canonical_scope_id(getattr(action, "tenant_id", None))
    if (
        canonical_scope_id(authority.get("workspace_id")) != action_workspace
        or canonical_scope_id(authority.get("tenant_id")) != action_tenant
    ):
        return _refusal(
            404, "TASK_ADMISSION_SCOPE_DENIED",
            "This task admission is outside your workspace or tenant.")

    params = action.params if isinstance(
        getattr(action, "params", None), Mapping) else {}
    owner = _nonempty(
        params.get("owner_user_id") or getattr(action, "user_id", None))
    if not owner:
        return _refusal(
            403, "AUTHORITY_REQUIRED",
            "This task admission has no persisted owner; decision denied "
            "(fail closed).")

    is_owner = owner == authority["id"]
    is_supervisor = role_level(authority["role"]) >= role_level(
        UserRole.TEAM_LEAD)
    if not (is_owner or is_supervisor):
        return _refusal(
            403, "AUTHORITY_REQUIRED",
            "Only this task's owner or a supervisor (team_lead or higher) "
            "can decide its admission.")

    denial = required_role_denial(
        authority["role"], persisted_required_roles(action),
        subject="task admission", actor_label="Reviewer")
    if denial:
        return _refusal(403, "AUTHORITY_REQUIRED", denial)
    return authority


def _exact_column(column: Any, value: Any):
    """NULL-safe scalar equivalence for a persisted binding field."""
    return column.is_(None) if value is None else column == value


def task_admission_binding_conditions(action: Any) -> List[Any]:
    """SQL predicates that freeze the task binding a reviewer saw.

    The row is authority only while these exact server-owned fields still
    match. ``params`` carries the execution id, task fingerprint, owner,
    reviewed rule revisions and reviewed task profile; ``context_snapshot``
    carries the execution/scope/actor binding. Both are compared to the
    values loaded BEFORE the decision, so a peer that rewrites the binding
    between the load and the claim makes the conditional UPDATE miss.

    JSON columns compare exactly on SQLite (serialized text) and semantically
    on PostgreSQL (JSONB equality). A NULL ``context_snapshot`` is the only
    shipped task-admission shape that has no object; it is compared as SQL
    NULL. Task-admission ``params`` is non-null by contract.
    """
    return [
        HITLAction.id == str(getattr(action, "id", "") or ""),
        HITLAction.action_type == NEVER_TASK_ADMISSION_ACTION,
        _exact_column(
            HITLAction.agent_id, getattr(action, "agent_id", None)),
        _exact_column(
            HITLAction.workspace_id, getattr(action, "workspace_id", None)),
        _exact_column(
            HITLAction.tenant_id, getattr(action, "tenant_id", None)),
        _exact_column(HITLAction.user_id, getattr(action, "user_id", None)),
        HITLAction.params == getattr(action, "params", None),
        _exact_column(
            HITLAction.context_snapshot,
            getattr(action, "context_snapshot", None)),
    ]


def claim_task_admission_decision(
    db: Any,
    action: Any,
    *,
    status: str,
    reviewer_id: str,
    reviewed_at: Optional[datetime] = None,
    user_feedback: Optional[str] = None,
) -> bool:
    """Atomically claim ONE pending task-admission decision.

    This is the write fence, not a re-read: the conditional UPDATE requires
    the row to still be ``pending`` AND every immutable execution/task/owner/
    rule/profile binding field to equal the values the reviewer's authority
    was checked against. A peer rejection, approval, cancel or binding
    rewrite committed after the load makes ``rowcount`` 0, so the stale
    writer returns a conflict instead of overwriting the winner. The caller
    must run :func:`claim_task_admission_reviewer` (the fresh-actor fence) in
    the SAME transaction before this statement.
    """
    if status not in (
            HITLActionStatus.APPROVED.value, HITLActionStatus.REJECTED.value):
        raise ValueError("task admission decision must be approved or rejected")
    reviewer = _nonempty(reviewer_id)
    if not reviewer:
        raise ValueError("task admission decision requires a reviewer")

    values: Dict[str, Any] = {
        "status": status,
        "reviewed_by": reviewer,
        "reviewed_at": reviewed_at or datetime.now(timezone.utc),
    }
    if user_feedback is not None:
        values["user_feedback"] = user_feedback

    conditions = task_admission_binding_conditions(action)
    conditions.append(HITLAction.status == HITLActionStatus.PENDING.value)
    result = db.execute(
        update(HITLAction)
        .where(*conditions)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    return int(result.rowcount or 0) == 1


def authorize_task_admission_decision(
    db: Any,
    action: Any,
    reviewer: Any,
    *,
    modified_params: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate one decision BEFORE any status mutation/advance.

    Returns ``{"ok": True, "authority": ...}`` or a refusal carrying the
    shared HTTP status/code. The caller must still run
    ``claim_task_admission_reviewer`` (fresh actor) and
    ``claim_task_admission_decision`` (pending state + immutable binding) in
    the same transaction as its status write; this read alone is not the
    fence.
    """
    binding = task_admission_binding_denial(action)
    if binding:
        return _refusal(
            409, "TASK_ADMISSION_REVIEW_INVALID", binding)
    if modified_params is not None:
        return _refusal(
            409, "TASK_ADMISSION_REVIEW_IMMUTABLE",
            "A task admission's reviewed task/rule binding cannot be "
            "rewritten during approval; reject it and request a fresh "
            "review.")
    authority = resolve_task_admission_reviewer(db, action, reviewer)
    if not authority.get("ok"):
        return authority
    return {"ok": True, "authority": authority}


def claim_task_admission_reviewer(db: Any, authority: Mapping[str, Any]) -> bool:
    """Fresh-actor fence: authority must still be true at the status write."""
    return claim_fresh_reviewer(db, authority)


def validate_task_admission_receipt(
    db: Any,
    action: Any,
    decision: Any,
    *,
    execution_id: Any = None,
    fingerprint: Any = None,
    tenant_id: Any = None,
    workspace_id: Any = None,
) -> Optional[Dict[str, Any]]:
    """Validate a DURABLE approved/executed task-admission receipt.

    Returns a provenance dict only when the row, its immutable binding, the
    reviewed rule revisions and the CURRENT reviewer authority all still
    match the task being admitted. Any failure returns ``None`` — absence of
    authority, never a status-only shortcut.
    """
    if not task_admission_action(action):
        return None
    if str(getattr(action, "status", "") or "") not in _ACCEPTED_STATUSES:
        return None
    if task_admission_binding_denial(action):
        return None

    params = action.params if isinstance(action.params, Mapping) else {}
    bound_execution = _nonempty(params.get("execution_id"))
    if execution_id not in (None, "") and bound_execution != _nonempty(
            execution_id):
        return None
    bound_fingerprint = _nonempty(params.get("task_fingerprint"))
    if fingerprint not in (None, "") and bound_fingerprint != _nonempty(
            fingerprint):
        return None

    if tenant_id not in (None, "") and canonical_scope_id(
            getattr(action, "tenant_id", None)) != canonical_scope_id(tenant_id):
        return None
    if workspace_id not in (None, "") and canonical_scope_id(
            getattr(action, "workspace_id", None)) != canonical_scope_id(
                workspace_id):
        return None

    if not isinstance(decision, Mapping) or (
            decision.get("outcome") != NEVER_OUTCOME_REVIEW):
        return None
    owner = _nonempty(params.get("owner_user_id"))
    current_owner = _nonempty(decision.get("owner_user_id"))
    if not owner or not current_owner or owner != current_owner:
        return None
    reviewed = {
        "outcome": NEVER_OUTCOME_REVIEW,
        "rule_bindings": list(params.get("rule_bindings") or []),
        "owner_user_id": owner,
    }
    if not decision_covers(reviewed, decision):
        return None

    reviewed_by = _nonempty(getattr(action, "reviewed_by", None))
    if not reviewed_by:
        return None
    if getattr(action, "reviewed_at", None) is None:
        return None
    authority = resolve_task_admission_reviewer(db, action, reviewed_by)
    if not authority.get("ok"):
        return None

    return {
        "hitl_action_id": str(getattr(action, "id", "") or ""),
        "params": dict(params),
        "approved_by": authority["id"],
        "approved_role": authority["role"],
        "resolved_at": (
            action.reviewed_at.isoformat()
            if getattr(action, "reviewed_at", None) else None),
    }
