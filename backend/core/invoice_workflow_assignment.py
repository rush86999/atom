"""Persist a stock-invoice assignment and deliver its owner handoff.

The execution row is the authorization anchor.  The assignment path records a
server-validated plan and the goal/run that owns it; the handoff path rereads
those durable facts and sends one scoped in-app notification.  Neither path
executes the assignment or performs an external send.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import sqlite3
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from core import notification_service
from core.assignment_plan import validate_assignment
from core.database import get_db_session
from core.models import GoalObjective, GoalRun, WorkflowExecution
from core.task_lifecycle import new_task_revision


_WORKFLOW_ID = "htn_invoice_followup"
_ACCOUNT_OWNER_CONTEXT_KEY = "_atom_account_owner_user_id"
# One durable receipt lives beside the link.  It is written under a single
# namespaced key so an execution context that carries unrelated state is never
# replaced by the handoff path.
_OWNER_HANDOFF_CONTEXT_KEY = "_atom_invoice_owner_handoff"
_OWNER_HANDOFF_RECEIPT_KEY = _OWNER_HANDOFF_CONTEXT_KEY
_OWNER_HANDOFF_CAS_ATTEMPTS = 5

_OWNER_HANDOFF_TITLE = "Invoice owner handoff"
_OWNER_HANDOFF_MESSAGE = (
    "Invoice {invoice_number} has been handed off to you for review.")
_ACTOR_SCOPE_UNAVAILABLE = "actor_scope_unavailable"

#: Bounded periodic recovery for a terminal execution whose owner handoff was
#: persisted as pending before the effect (or whose acknowledgement was lost).
#: Only the exact stock workflow rows are considered, and each scan admits a
#: small deterministic slice so discovery can never become an unbounded scan.
_TERMINAL_EXECUTION_STATUSES = frozenset({
    "completed", "failed", "cancelled", "canceled", "timed_out", "terminated",
})
_TERMINAL_RUN_STATUSES = frozenset({
    "achieved", "completed", "failed", "cancelled", "canceled", "terminated",
})
_PENDING_HANDOFF_SCAN_LIMIT = 20
_MAX_PENDING_HANDOFF_SCAN_LIMIT = 50

# A stable namespace keeps the goal and run ids reproducible from the
# execution id alone.
_ASSIGNMENT_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "atom.invoice.workflow.assignment")


class OwnerHandoffDeliveryError(RuntimeError):
    """The in-app owner handoff could not prove that it was delivered."""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _execution_key(execution_id: Any) -> str:
    key = _text(execution_id)
    if not key:
        raise ValueError("execution_id is required")
    return key


def _optional_account_owner(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(
            "account_owner_user_id must be a non-empty string")
    owner = value.strip()
    if not owner:
        raise ValueError(
            "account_owner_user_id must be a non-empty string")
    return owner


def _stored_account_owner(context: Dict[str, Any]) -> Optional[str]:
    value = context.get(_ACCOUNT_OWNER_CONTEXT_KEY)
    if value is None:
        return None
    owner = _text(value)
    return owner or None


def _identity_values(identity: Any) -> Dict[str, str]:
    values = {
        "tenant_id": _text(_field(identity, "tenant_id")),
        "workspace_id": _text(_field(identity, "workspace_id")),
        "user_id": _text(_field(identity, "user_id")),
        "employee_id": _text(_field(identity, "employee_id")),
    }
    for name in ("tenant_id", "workspace_id", "user_id"):
        if not values[name]:
            raise PermissionError(f"caller {name} is required")
    return values


def _json_object(value: Any, label: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (str, bytes, bytearray)):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} is not valid JSON") from exc
        if not isinstance(parsed, Mapping):
            raise ValueError(f"{label} must contain a JSON object")
        return dict(parsed)
    raise ValueError(f"{label} must be a JSON object")


def _goal_id(execution_key: str) -> str:
    return str(uuid.uuid5(_ASSIGNMENT_NAMESPACE, f"goal:{execution_key}"))


def _run_id(execution_key: str) -> str:
    return str(uuid.uuid5(_ASSIGNMENT_NAMESPACE, f"run:{execution_key}"))


def _validate_input_assignment(
    assignment: Any, identity: Dict[str, str],
) -> Dict[str, Any]:
    if not isinstance(assignment, Mapping) or not assignment:
        raise ValueError("assignment is required")
    plan = copy.deepcopy(dict(assignment))

    if not _text(plan.get("objective")):
        raise ValueError("assignment objective is required")

    # Server-side schema/non-empty validation.  This is the only validation
    # path used for persisted assignment plans.
    validate_assignment(plan)

    if not plan.get("steps"):
        raise ValueError("assignment must contain at least one step")

    if _text(plan.get("employee_id")) != identity["employee_id"]:
        raise PermissionError("assignment employee does not match caller")
    if _text(plan.get("tenant_id")) != identity["tenant_id"]:
        raise PermissionError("assignment tenant does not match caller")
    if _text(plan.get("workspace_id")) != identity["workspace_id"]:
        raise PermissionError("assignment workspace does not match caller")

    return plan


def _assignment_projection(assignment: Dict[str, Any]) -> list:
    from core.goals.goal_plan_validation import (
        validate_assignment_projection,
    )

    plan = []
    for step in assignment.get("steps") or []:
        plan.append({
            "id": step.get("step_id"),
            "kind": "operation",
            "title": step.get("title"),
            "description": step.get("instruction") or step.get("title"),
            "operation_type": step.get("operation_type"),
            "depends_on": list(step.get("depends_on") or []),
            "status": step.get("status"),
        })
    errors = validate_assignment_projection(plan)
    if errors:
        raise ValueError(
            "invalid assignment projection: " + "; ".join(errors))
    return plan


def _require_execution_scope(
    row: WorkflowExecution,
    input_data: Dict[str, Any],
    identity: Dict[str, str],
) -> None:
    if _text(row.owner_id) != identity["user_id"]:
        raise PermissionError("workflow execution owner does not match caller")
    if _text(row.user_id) != identity["user_id"]:
        raise PermissionError("workflow execution user does not match caller")
    if _text(row.tenant_id) != identity["tenant_id"]:
        raise PermissionError("workflow execution tenant does not match caller")

    scope = input_data.get("_atom_execution_scope")
    if not isinstance(scope, Mapping):
        raise PermissionError("workflow execution scope is missing")
    if (
        _text(scope.get("tenant_id")) != identity["tenant_id"]
        or _text(scope.get("workspace_id")) != identity["workspace_id"]
        or _text(scope.get("user_id")) != identity["user_id"]
    ):
        raise PermissionError("workflow execution scope does not match caller")


def _require_invoice_intent(
    input_data: Dict[str, Any], invoice_number: str,
) -> None:
    expected = hashlib.sha256(invoice_number.encode("utf-8")).hexdigest()
    stored = input_data.get("_atom_invoice_intent")
    if not isinstance(stored, str) or not hmac.compare_digest(
            stored, expected):
        raise ValueError(
            "workflow execution invoice intent does not match invoice_number")


def _require_account_owner_recipient(
    session: Any,
    owner_id: str,
    identity: Dict[str, str],
) -> None:
    scope_error = notification_service._workflow_scope_error(
        session,
        user_id=owner_id,
        workspace_id=identity["workspace_id"],
        tenant_id=identity["tenant_id"],
    )
    if scope_error:
        raise PermissionError(str(scope_error))


def _status_text(value: Any) -> str:
    return _text(getattr(value, "value", value)).lower()


def _is_pending(status: Any) -> bool:
    return _status_text(status) == "pending"


def _extract_link(context: Dict[str, Any]) -> Optional[Dict[str, str]]:
    run_id = _text(context.get("run_id"))
    if not run_id:
        return None
    return {
        "execution_id": _text(context.get("execution_id")),
        "workflow_id": _text(context.get("workflow_id")),
        "goal_id": _text(context.get("goal_id")),
        "run_id": run_id,
        "tenant_id": _text(context.get("tenant_id")),
        "workspace_id": _text(context.get("workspace_id")),
        "user_id": _text(context.get("user_id")),
    }


def _link_matches(
    link: Dict[str, str],
    execution_key: str,
    identity: Dict[str, str],
    goal_id: str,
    run_id: str,
    run: GoalRun,
    parameters: Dict[str, Any],
) -> bool:
    expected_link = {
        "execution_id": execution_key,
        "workflow_id": _WORKFLOW_ID,
        "goal_id": goal_id,
        "run_id": run_id,
        "tenant_id": identity["tenant_id"],
        "workspace_id": identity["workspace_id"],
        "user_id": identity["user_id"],
    }
    if link != expected_link:
        return False

    if _text(_field(run, "id")) != run_id:
        return False
    if _text(_field(run, "goal_id")) != goal_id:
        return False
    for name in ("tenant_id", "workspace_id"):
        if _text(_field(run, name)) != identity[name]:
            return False
    if _text(_field(run, "created_by")) != identity["user_id"]:
        return False
    if _text(_field(run, "agent_id")) != identity["employee_id"]:
        return False

    task_lifecycle = _field(parameters, "task_lifecycle")
    if not isinstance(task_lifecycle, Mapping):
        return False
    assignment = _field(task_lifecycle, "assignment")
    if not isinstance(assignment, Mapping):
        return False
    for name in ("tenant_id", "workspace_id", "employee_id"):
        if _text(_field(assignment, name)) != identity[name]:
            return False

    expected_context = {
        "execution_id": execution_key,
        "workflow_id": _WORKFLOW_ID,
        "tenant_id": identity["tenant_id"],
        "workspace_id": identity["workspace_id"],
        "user_id": identity["user_id"],
    }
    execution_context = _field(parameters, "execution_context")
    if not isinstance(execution_context, Mapping):
        return False
    if dict(execution_context) != expected_context:
        return False

    return True


def _resolve_link(
    session: Any,
    row: WorkflowExecution,
    execution_key: str,
    identity: Dict[str, str],
    goal_id: str,
    run_id: str,
) -> Tuple[bool, Optional[GoalRun]]:
    context = _json_object(row.context, "workflow execution context")
    link = _extract_link(context)
    if link is None:
        return False, None

    run = session.query(GoalRun).filter(
        GoalRun.id == run_id,
        GoalRun.tenant_id == identity["tenant_id"],
        GoalRun.workspace_id == identity["workspace_id"],
    ).first()
    if run is None:
        return True, None

    parameters = _json_object(
        _field(run, "parameters"), "goal run parameters")
    if not _link_matches(
            link, execution_key, identity, goal_id, run_id, run, parameters):
        return True, None

    return True, run


def _persist_assignment(
    session: Any,
    row: WorkflowExecution,
    execution_key: str,
    identity: Dict[str, str],
    assignment: Dict[str, Any],
    projection: list,
    goal_id: str,
    run_id: str,
    account_owner_user_id: Optional[str],
) -> None:
    objective = _text(assignment.get("objective"))
    revision = new_task_revision(
        objective_text=objective,
        authorized_actions=list(
            assignment.get("authorized_actions") or []),
        completion_criteria=list(
            assignment.get("completion_criteria") or []),
        provenance={
            "assignment_id": assignment.get("assignment_id"),
            "execution_id": execution_key,
            "workflow_id": _WORKFLOW_ID,
        },
    )

    goal = GoalObjective(
        id=goal_id,
        tenant_id=identity["tenant_id"],
        workspace_id=identity["workspace_id"],
        title=objective[:500],
        description="",
        status="active",
        progress=0.0,
        criteria=copy.deepcopy(
            list(assignment.get("completion_criteria") or [])),
        key_results=[],
        metadata_json={
            "execution_id": execution_key,
            "workflow_id": _WORKFLOW_ID,
            "assignment_id": assignment.get("assignment_id"),
        },
        owner_id=identity["user_id"],
        parent_goal_id=None,
        source="api",
        target_date=None,
    )

    run = GoalRun(
        id=run_id,
        tenant_id=identity["tenant_id"],
        workspace_id=identity["workspace_id"],
        goal_id=goal_id,
        agent_id=identity["employee_id"] or None,
        role=None,
        status="active",
        supervision_mode="shadow",
        plan=projection,
        cursor=projection[0].get("id") if projection else None,
        parameters={
            "task_lifecycle": {
                "task_version": 1,
                "task_revision": revision,
                "operations": [],
                "assignment": copy.deepcopy(assignment),
            },
            "execution_context": {
                "execution_id": execution_key,
                "workflow_id": _WORKFLOW_ID,
                "tenant_id": identity["tenant_id"],
                "workspace_id": identity["workspace_id"],
                "user_id": identity["user_id"],
            },
        },
        decision_log=[
            {
                "kind": "task_created",
                "rationale": objective[:500],
                "revision": 1,
            },
            {
                "kind": "assignment_attached",
                "assignment_id": assignment.get("assignment_id"),
                "plan_revision": assignment.get("plan_revision"),
            },
        ],
        created_by=identity["user_id"],
    )

    context = _json_object(row.context, "workflow execution context")
    context.update({
        "execution_id": execution_key,
        "workflow_id": _WORKFLOW_ID,
        "goal_id": goal_id,
        "run_id": run_id,
        "tenant_id": identity["tenant_id"],
        "workspace_id": identity["workspace_id"],
        "user_id": identity["user_id"],
    })
    if account_owner_user_id is not None:
        context[_ACCOUNT_OWNER_CONTEXT_KEY] = account_owner_user_id

    session.add(goal)
    session.add(run)
    row.context = json.dumps(
        context, sort_keys=True, separators=(",", ":"))
    session.commit()


_PK_CONSTRAINT_NAMES = frozenset({
    "goal_objectives_pkey",
    "goal_runs_pkey",
})
_SQLITE_PK_COLUMNS = frozenset({
    "goal_objectives.id",
    "goal_runs.id",
})
_SQLITE_UNIQUE_PREFIX = "UNIQUE constraint failed: "
_POSTGRES_UNIQUE_VIOLATION = "23505"


def _error_chain(error: Any):
    seen = set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = getattr(current, "__cause__", None)


def _postgres_sqlstate(error: Any) -> Optional[str]:
    for name in ("sqlstate", "pgcode"):
        value = getattr(error, name, None)
        if value is not None:
            return str(value)
    for name in ("diag", "diagnostic"):
        diagnostic = getattr(error, name, None)
        if diagnostic is None:
            continue
        value = getattr(diagnostic, "sqlstate", None)
        if value is None and isinstance(diagnostic, Mapping):
            value = diagnostic.get("sqlstate")
        if value is not None:
            return str(value)
    value = getattr(error, "code", None)
    if isinstance(value, str):
        return value
    return None


def _postgres_constraint_name(error: Any) -> Optional[str]:
    for name in ("diag", "diagnostic"):
        diagnostic = getattr(error, name, None)
        if diagnostic is None:
            continue
        value = getattr(diagnostic, "constraint_name", None)
        if value is None and isinstance(diagnostic, Mapping):
            value = diagnostic.get("constraint_name")
        if value:
            return str(value)
    value = getattr(error, "constraint_name", None)
    if value:
        return str(value)
    return None


def _is_deterministic_pk_collision(exc: Exception) -> bool:
    if not isinstance(exc, IntegrityError):
        return False
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False

    if isinstance(orig, sqlite3.IntegrityError):
        message = str(orig).strip()
        if not message.startswith(_SQLITE_UNIQUE_PREFIX):
            return False
        column = message[len(_SQLITE_UNIQUE_PREFIX):]
        return column in _SQLITE_PK_COLUMNS

    for error in _error_chain(orig):
        if (
            _postgres_sqlstate(error) == _POSTGRES_UNIQUE_VIOLATION
            and _postgres_constraint_name(error) in _PK_CONSTRAINT_NAMES
        ):
            return True
    return False


def _recover_existing_run(
    session: Any,
    execution_key: str,
    identity: Dict[str, str],
    invoice_number: str,
    goal_id: str,
    run_id: str,
    account_owner_user_id: Optional[str],
) -> Optional[str]:
    """Read-only recovery for a deterministic goal/run id collision."""
    row = session.query(WorkflowExecution).filter(
        WorkflowExecution.execution_id == execution_key).first()
    if row is None or _text(row.workflow_id) != _WORKFLOW_ID:
        return None

    try:
        input_data = _json_object(
            row.input_data, "workflow execution input_data")
        _require_execution_scope(row, input_data, identity)
        _require_invoice_intent(input_data, invoice_number)
        has_link, run = _resolve_link(
            session, row, execution_key, identity, goal_id, run_id)
        context = _json_object(row.context, "workflow execution context")
        if _stored_account_owner(context) != account_owner_user_id:
            return None
    except Exception:  # noqa: BLE001 - failed recovery keeps original error
        return None

    if not has_link or run is None:
        return None
    return _text(run.id)


def attach_stock_invoice_assignment(
    execution_id: str,
    invoice_number: str,
    *,
    identity: Any,
    assignment: Any,
    account_owner_user_id: Optional[str] = None,
) -> Dict[str, str]:
    """Attach *assignment* to an existing ``htn_invoice_followup`` execution.

    The execution must belong to the caller's tenant/workspace/user, its
    ``_atom_invoice_intent`` must hash the exact invoice number, and the plan
    must be a validated, non-empty assignment for the same employee/scope.

    When ``account_owner_user_id`` is supplied it is an explicit launch input:
    the recipient is validated in the caller's scope and the exact value is
    persisted with the execution.  Omitting it preserves the legacy behavior.
    """
    execution_key = _execution_key(execution_id)
    identity_values = _identity_values(identity)
    account_owner = _optional_account_owner(account_owner_user_id)

    if not isinstance(invoice_number, str) or not invoice_number.strip():
        raise ValueError("invoice_number is required")

    plan = _validate_input_assignment(assignment, identity_values)
    projection = _assignment_projection(plan)

    goal_id = _goal_id(execution_key)
    run_id = _run_id(execution_key)

    with get_db_session() as session:
        try:
            row = session.query(WorkflowExecution).filter(
                WorkflowExecution.execution_id == execution_key).first()
            if row is None:
                raise LookupError("workflow execution not found")
            if _text(row.workflow_id) != _WORKFLOW_ID:
                raise ValueError(
                    "workflow execution is not htn_invoice_followup")

            input_data = _json_object(
                row.input_data, "workflow execution input_data")
            _require_execution_scope(row, input_data, identity_values)
            _require_invoice_intent(input_data, invoice_number)

            has_link, existing_run = _resolve_link(
                session, row, execution_key, identity_values,
                goal_id, run_id)
            if has_link:
                if existing_run is None:
                    raise LookupError(
                        "workflow execution links an unverified goal run")
                stored_owner = _stored_account_owner(
                    _json_object(
                        row.context, "workflow execution context"))
                if stored_owner != account_owner:
                    raise ValueError(
                        "account_owner_user_id conflicts with the existing "
                        "assignment")
                return {"run_id": _text(existing_run.id)}

            if not _is_pending(row.status):
                raise ValueError(
                    "an unlinked workflow execution must be PENDING")

            if account_owner is not None:
                _require_account_owner_recipient(
                    session, account_owner, identity_values)

            _persist_assignment(
                session,
                row,
                execution_key,
                identity_values,
                plan,
                projection,
                goal_id,
                run_id,
                account_owner,
            )
            return {"run_id": run_id}
        except Exception as exc:
            session.rollback()
            if not _is_deterministic_pk_collision(exc):
                raise
            recovered_run_id = _recover_existing_run(
                session,
                execution_key,
                identity_values,
                invoice_number,
                goal_id,
                run_id,
                account_owner,
            )
            if recovered_run_id is None:
                raise
            return {"run_id": recovered_run_id}


# ---------------------------------------------------------------------------
# Reusable in-app owner handoff delivery/receipt boundary
# ---------------------------------------------------------------------------


def _owner_handoff_operation_id(execution_key: str, run_id: str) -> str:
    """Return the one stable operation id for an assignment's owner handoff.

    The id deliberately depends only on durable assignment identity.  Trigger
    reasons, reply/review expiry timestamps and the latest invoice snapshot are
    not inputs, so every handoff state for this assignment shares one
    notification and one idempotency key.  Including the validated run id binds
    the operation to the exact deterministic assignment rather than to a bare
    execution string supplied by a caller.
    """
    return str(uuid.uuid5(
        _ASSIGNMENT_NAMESPACE,
        f"owner-handoff:{execution_key}:{run_id}",
    ))


def _bound_account_owner(context: Dict[str, Any]) -> str:
    """Return the exact persisted owner binding, never the caller fallback."""
    raw = context.get(_ACCOUNT_OWNER_CONTEXT_KEY)
    if raw is None:
        raise LookupError(
            "workflow execution has no account owner binding")
    if not isinstance(raw, str):
        raise ValueError(
            "workflow execution account owner binding is malformed")
    owner = raw.strip()
    if not owner or owner != raw:
        raise ValueError(
            "workflow execution account owner binding is malformed")
    return owner


def _read_owner_handoff_binding(
    execution_key: str,
    run_id: str,
    invoice_number: str,
    identity: Dict[str, str],
) -> Dict[str, Any]:
    """Re-read and prove every durable fact needed to deliver the handoff.

    The returned facts and receipt are copies.  The read transaction is closed
    before the caller opens the notification transaction.
    """
    with get_db_session() as session:
        row = session.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_key,
        ).populate_existing().first()
        if row is None:
            raise LookupError("workflow execution not found")
        if _text(row.workflow_id) != _WORKFLOW_ID:
            raise ValueError(
                "workflow execution is not htn_invoice_followup")

        input_data = _json_object(
            row.input_data, "workflow execution input_data")
        _require_execution_scope(row, input_data, identity)
        _require_invoice_intent(input_data, invoice_number)

        goal_id = _goal_id(execution_key)
        has_link, run = _resolve_link(
            session, row, execution_key, identity, goal_id, run_id)
        if not has_link:
            raise LookupError(
                "workflow execution has no stock invoice goal run link")
        if run is None:
            raise LookupError(
                "workflow execution links an unverified goal run")

        context = _json_object(
            row.context, "workflow execution context")
        owner_user_id = _bound_account_owner(context)
        receipt = context.get(_OWNER_HANDOFF_CONTEXT_KEY)
        if receipt is not None and not isinstance(receipt, Mapping):
            # A malformed receipt is not delivery proof.  Treat it as absent;
            # the CAS writer below keeps every other context key intact.
            receipt = None

        return {
            "execution_id": execution_key,
            "run_id": _text(run.id),
            "invoice_number": invoice_number,
            "owner_user_id": owner_user_id,
            "tenant_id": identity["tenant_id"],
            "workspace_id": identity["workspace_id"],
            "execution_status": getattr(row.status, "value", row.status),
            "run_status": _field(run, "status"),
            "receipt": copy.deepcopy(dict(receipt)) if receipt else None,
        }


def _owner_handoff_receipt(
    *,
    notification_id: str,
    operation_id: str,
    created: bool,
) -> Dict[str, Any]:
    return {
        "notification_id": notification_id,
        "operation_id": operation_id,
        "status": "delivered",
        "delivery_status": "delivered",
        "delivered": True,
        "success": True,
        "created": created,
        "duplicate": not created,
    }


def _owner_handoff_failure(
    operation_id: str,
    error: str,
) -> Dict[str, Any]:
    """Return a truthful failure receipt; never look like a handoff."""
    return {
        "notification_id": None,
        "operation_id": operation_id,
        "status": "failed",
        "delivery_status": "failed",
        "delivered": False,
        "success": False,
        "created": False,
        "duplicate": False,
        "error": _text(error) or "notification_failed",
    }


async def deliver_stock_invoice_owner_handoff(
    *,
    execution_id: str,
    run_id: str,
    invoice_number: str,
    identity: Any,
) -> Dict[str, Any]:
    """Deliver the one scoped in-app owner handoff for a stock invoice.

    ``execution_id``, the deterministic ``run_id`` and the exact
    ``invoice_number`` are checked against the durable execution row in a short
    read transaction.  The recipient comes only from the execution's immutable
    account-owner binding; the caller's identity is used solely to prove the
    execution scope.

    The read transaction is released before a *separate* notification
    transaction calls the existing scoped ``NotificationService`` boundary.
    That service rechecks current recipient usability.  Immediately before the
    notification, the originating actor's current scope is also rechecked in
    the same delivery transaction, so a deactivated actor cannot deliver a
    handoff left pending by an earlier attempt.  The notification material and
    operation id contain no trigger reason, mutable dates or other changing
    state, so reply expiry, review expiry and reviewed-without-commitment all
    converge on one deduplicated delivery.

    A delivered receipt requires the service's explicit ``success is True``,
    ``notification_id`` exactly equal to the operation id (the service uses it
    as the primary key), an actual boolean ``created``, ``emailed is False``
    and no error.  A known negative outcome keeps its error; a missing or
    malformed response is a generic failure, never a delivered receipt.  An
    unavailable/broken service raises :class:`OwnerHandoffDeliveryError`.
    """
    execution_key = _execution_key(execution_id)
    expected_run_id = _run_id(execution_key)
    run_key = _text(run_id)
    if not run_key:
        raise ValueError("goal run id is required")
    if run_key != expected_run_id:
        raise LookupError(
            "goal run is not the deterministic stock invoice assignment run")
    if not isinstance(invoice_number, str) or not invoice_number.strip():
        raise ValueError("invoice_number is required")

    identity_values = _identity_values(identity)

    facts = _read_owner_handoff_binding(
        execution_key, run_key, invoice_number, identity_values)
    operation_id = _owner_handoff_operation_id(
        facts["execution_id"], facts["run_id"])

    try:
        with get_db_session() as send_session:
            actor_scope_error = notification_service._workflow_scope_error(
                send_session,
                user_id=identity_values["user_id"],
                workspace_id=identity_values["workspace_id"],
                tenant_id=identity_values["tenant_id"],
            )
            if actor_scope_error:
                return _owner_handoff_failure(
                    operation_id, _ACTOR_SCOPE_UNAVAILABLE)
            service = notification_service.NotificationService(send_session)
            outcome = await service.send_workflow_notification(
                user_id=facts["owner_user_id"],
                workspace_id=facts["workspace_id"],
                tenant_id=facts["tenant_id"],
                operation_id=operation_id,
                title=_OWNER_HANDOFF_TITLE,
                message=_OWNER_HANDOFF_MESSAGE.format(
                    invoice_number=facts["invoice_number"]),
            )
    except Exception as exc:
        raise OwnerHandoffDeliveryError(
            "owner handoff delivery is unavailable") from exc

    if not isinstance(outcome, Mapping):
        return _owner_handoff_failure(operation_id, "notification_failed")

    error = _text(outcome.get("error"))
    if outcome.get("success") is not True:
        return _owner_handoff_failure(
            operation_id, error or "notification_failed")
    if error:
        return _owner_handoff_failure(operation_id, "notification_failed")

    notification_id = outcome.get("notification_id")
    if notification_id != operation_id:
        return _owner_handoff_failure(operation_id, "notification_failed")

    created = outcome.get("created")
    if not isinstance(created, bool):
        return _owner_handoff_failure(operation_id, "notification_failed")
    if outcome.get("emailed") is not False:
        return _owner_handoff_failure(operation_id, "notification_failed")

    return _owner_handoff_receipt(
        notification_id=notification_id,
        operation_id=operation_id,
        created=created,
    )


# ---------------------------------------------------------------------------
# Durable pending/delivered receipt
# ---------------------------------------------------------------------------


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt_status(receipt: Any) -> str:
    if not isinstance(receipt, Mapping):
        return ""
    return _text(receipt.get("status")).lower()


def _receipt_trigger(receipt: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(receipt, Mapping):
        return None
    trigger = receipt.get("trigger")
    if not isinstance(trigger, Mapping):
        return None
    return copy.deepcopy(dict(trigger))


def _is_cancelled_status(value: Any) -> bool:
    return _status_text(value) in ("cancelled", "canceled")


def _cas_owner_handoff_receipt(
    execution_key: str,
    mutate: Any,
) -> Optional[Dict[str, Any]]:
    """Lock/CAS-update only the handoff key on one execution context.

    The fresh context is re-read inside the write transaction and every other
    key is copied through unchanged.  A compare-and-swap on the exact prior
    context keeps a concurrent unrelated context writer from being clobbered;
    a conflict simply re-reads and re-applies the receipt mutation.
    """
    from sqlalchemy import update

    for _attempt in range(_OWNER_HANDOFF_CAS_ATTEMPTS):
        with get_db_session() as session:
            query = session.query(WorkflowExecution).filter(
                WorkflowExecution.execution_id == execution_key)
            query = query.populate_existing()
            try:
                query = query.with_for_update()
            except Exception:  # noqa: BLE001 - dialect without row locks
                pass
            row = query.first()
            if row is None:
                raise LookupError("workflow execution not found")

            raw_context = row.context
            context = _json_object(
                raw_context, "workflow execution context")
            current = context.get(_OWNER_HANDOFF_CONTEXT_KEY)
            if current is not None and not isinstance(current, Mapping):
                current = None

            updated = mutate(
                copy.deepcopy(dict(current)) if current is not None else None)
            if updated is None:
                session.rollback()
                return (
                    copy.deepcopy(dict(current))
                    if current is not None else None)

            context[_OWNER_HANDOFF_CONTEXT_KEY] = copy.deepcopy(updated)
            new_context = json.dumps(
                context, sort_keys=True, separators=(",", ":"))

            if raw_context is not None and not isinstance(
                    raw_context, (str, bytes, bytearray)):
                # A JSON-typed column returns a decoded object.  The row is
                # locked above, so write it back through the ORM.
                row.context = context
                session.commit()
                return copy.deepcopy(updated)

            condition = (
                WorkflowExecution.context.is_(None)
                if raw_context is None
                else WorkflowExecution.context == raw_context)
            result = session.execute(
                update(WorkflowExecution)
                .where(
                    WorkflowExecution.execution_id == execution_key,
                    condition,
                )
                .values(context=new_context))
            if result.rowcount == 1:
                session.commit()
                return copy.deepcopy(updated)
            session.rollback()

    raise RuntimeError("owner handoff receipt update conflict")


def _handoff_error_text(error: Any) -> str:
    text = _text(error)
    return text[:500] if text else "notification_failed"


async def reconcile_stock_invoice_owner_handoff(
    *,
    execution_id: str,
    run_id: str,
    invoice_number: str,
    identity: Any,
    trigger: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Record and deliver one stock-invoice owner handoff safely.

    ``trigger`` is built only from the executor's persisted lifecycle facts.
    The durable execution link, invoice intent and bound account owner are
    re-read here through the same helpers used by direct delivery.  A pending
    receipt is written before the notification effect; the effect runs outside
    every transaction.  A delivered receipt is terminal, while an error leaves
    a truthful retryable ``pending`` receipt for the next authorized advance.

    Returning ``None`` means there was no trigger and no pending receipt to
    recover (or the run is cancelled).  A returned receipt is the persisted
    state after this attempt.
    """
    execution_key = _execution_key(execution_id)
    expected_run_id = _run_id(execution_key)
    run_key = _text(run_id)
    if not run_key:
        raise ValueError("goal run id is required")
    if run_key != expected_run_id:
        raise LookupError(
            "goal run is not the deterministic stock invoice assignment run")
    if not isinstance(invoice_number, str) or not invoice_number.strip():
        raise ValueError("invoice_number is required")

    identity_values = _identity_values(identity)
    facts = _read_owner_handoff_binding(
        execution_key, run_key, invoice_number, identity_values)

    if _is_cancelled_status(facts.get("execution_status")) or \
            _is_cancelled_status(facts.get("run_status")):
        return copy.deepcopy(facts.get("receipt"))

    operation_id = _owner_handoff_operation_id(
        facts["execution_id"], facts["run_id"])
    existing = facts.get("receipt")
    if _receipt_status(existing) == "delivered":
        return copy.deepcopy(existing)

    first_trigger = _receipt_trigger(existing)
    if first_trigger is None and isinstance(trigger, Mapping):
        first_trigger = copy.deepcopy(dict(trigger))
    if existing is None and first_trigger is None:
        return None
    if first_trigger is None:
        # A pending receipt without its first source event is still retryable
        # proof that the effect may have landed.  Keep the operation stable.
        first_trigger = {}

    now = _utc_now_text()

    def mark_pending(current: Optional[Dict[str, Any]]):
        receipt = dict(current or {})
        if _receipt_status(receipt) == "delivered":
            return None
        receipt.setdefault("trigger", copy.deepcopy(first_trigger))
        receipt.setdefault("first_source_event", copy.deepcopy(first_trigger))
        receipt.setdefault(
            "source_event", _text(first_trigger.get("event")))
        receipt["operation_id"] = operation_id
        receipt["status"] = "pending"
        receipt["delivery_status"] = "pending"
        receipt["pending"] = True
        receipt["delivered"] = False
        receipt["success"] = False
        receipt["attempts"] = int(receipt.get("attempts") or 0) + 1
        receipt["pending_at"] = receipt.get("pending_at") or now
        receipt["last_attempt_at"] = now
        receipt["last_error"] = None
        receipt.pop("error", None)
        return receipt

    pending = _cas_owner_handoff_receipt(
        execution_key, mark_pending)
    if pending is None:
        return None
    if _receipt_status(pending) == "delivered":
        return pending

    try:
        outcome = await deliver_stock_invoice_owner_handoff(
            execution_id=execution_key,
            run_id=run_key,
            invoice_number=invoice_number,
            identity=identity_values,
        )
    except Exception:  # noqa: BLE001 - durable retry state
        # The exception text may contain provider/private detail.  Persist
        # only the stable failure label; the receipt remains retryable.
        error_text = _handoff_error_text(None)

        def mark_error(current: Optional[Dict[str, Any]]):
            receipt = dict(current or {})
            if _receipt_status(receipt) == "delivered":
                return None
            receipt.setdefault("trigger", copy.deepcopy(first_trigger))
            receipt.setdefault(
                "first_source_event", copy.deepcopy(first_trigger))
            receipt.setdefault(
                "source_event", _text(first_trigger.get("event")))
            receipt["operation_id"] = operation_id
            receipt["status"] = "pending"
            receipt["delivery_status"] = "pending"
            receipt["pending"] = True
            receipt["delivered"] = False
            receipt["success"] = False
            receipt["error"] = error_text
            receipt["last_error"] = error_text
            receipt["failed_at"] = _utc_now_text()
            return receipt

        return _cas_owner_handoff_receipt(execution_key, mark_error)

    if not isinstance(outcome, Mapping) or outcome.get("delivered") is not True:
        error_text = _handoff_error_text(
            (outcome or {}).get("error")
            if isinstance(outcome, Mapping) else None)

        def mark_failure(current: Optional[Dict[str, Any]]):
            receipt = dict(current or {})
            if _receipt_status(receipt) == "delivered":
                return None
            receipt.setdefault("trigger", copy.deepcopy(first_trigger))
            receipt.setdefault(
                "first_source_event", copy.deepcopy(first_trigger))
            receipt.setdefault(
                "source_event", _text(first_trigger.get("event")))
            receipt["operation_id"] = operation_id
            receipt["status"] = "pending"
            receipt["delivery_status"] = "pending"
            receipt["pending"] = True
            receipt["delivered"] = False
            receipt["success"] = False
            receipt["error"] = error_text
            receipt["last_error"] = error_text
            receipt["failed_at"] = _utc_now_text()
            return receipt

        return _cas_owner_handoff_receipt(execution_key, mark_failure)

    notification_id = _text(outcome.get("notification_id"))
    delivered_at = _utc_now_text()

    def mark_delivered(current: Optional[Dict[str, Any]]):
        receipt = dict(current or {})
        if _receipt_status(receipt) == "delivered":
            return None
        receipt.setdefault("trigger", copy.deepcopy(first_trigger))
        receipt.setdefault(
            "first_source_event", copy.deepcopy(first_trigger))
        receipt.setdefault(
            "source_event", _text(first_trigger.get("event")))
        receipt["operation_id"] = operation_id
        receipt["notification_id"] = notification_id
        receipt["status"] = "delivered"
        receipt["delivery_status"] = "delivered"
        receipt["pending"] = False
        receipt["delivered"] = True
        receipt["success"] = True
        receipt["created"] = outcome.get("created") is True
        receipt["duplicate"] = outcome.get("created") is not True
        receipt["delivered_at"] = delivered_at
        receipt["last_error"] = None
        receipt.pop("error", None)
        return receipt

    return _cas_owner_handoff_receipt(
        execution_key, mark_delivered)


# ---------------------------------------------------------------------------
# Bounded terminal-run discovery for pending owner handoffs
# ---------------------------------------------------------------------------


def _pending_handoff_invoice_number(assignment: Mapping[str, Any]) -> str:
    """Read one exact invoice number from the persisted assignment plan."""
    values = set()

    def collect(holder: Any) -> None:
        if not isinstance(holder, Mapping):
            return
        value = holder.get("invoice_number")
        if isinstance(value, str) and value.strip():
            values.add(value.strip())

    for step in assignment.get("steps") or []:
        if not isinstance(step, Mapping):
            continue
        collect(step.get("inputs"))
        collect(step.get("waiting"))
        result = step.get("result")
        if isinstance(result, Mapping):
            collect(result.get("data"))
            collect(result)
    if len(values) != 1:
        return ""
    return next(iter(values))


def _pending_stock_invoice_owner_handoff_candidates(
    *, limit: int = _PENDING_HANDOFF_SCAN_LIMIT,
) -> list[Dict[str, Any]]:
    """Return a small ordered slice of terminal stock pending handoffs.

    Discovery is restricted to the exact stock workflow id and a persisted
    pending handoff key.  The linked goal run is read only for the candidate's
    exact deterministic run id; the candidate must then be terminal at the
    execution or run level.  Every returned candidate has already passed the
    same link/scope checks used by delivery.  No assignment step is advanced
    or enumerated here.
    """
    from sqlalchemy import String, cast, func, or_

    from core.models import GoalRun, WorkflowExecution

    bounded = max(
        1, min(int(limit), _MAX_PENDING_HANDOFF_SCAN_LIMIT))
    with get_db_session() as session:
        context_text = cast(WorkflowExecution.context, String)
        status_text = func.lower(cast(WorkflowExecution.status, String))
        rows = (
            session.query(WorkflowExecution)
            .filter(
                WorkflowExecution.workflow_id == _WORKFLOW_ID,
                # Cancelled executions are excluded before the bound so they
                # cannot consume the whole scan slice.  A still-PENDING
                # execution remains eligible because its GoalRun may be
                # terminal.
                status_text.notin_(("cancelled", "canceled")),
                context_text.like(f"%{_OWNER_HANDOFF_CONTEXT_KEY}%"),
                or_(
                    context_text.like('%"status": "pending"%'),
                    context_text.like('%"status":"pending"%'),
                ),
            )
            # A retried receipt updates the execution row, moving it behind
            # older pending work.  Fall back to created_at when updated_at is
            # absent, then keep execution_id as the stable final tie-breaker.
            .order_by(
                func.coalesce(
                    WorkflowExecution.updated_at,
                    WorkflowExecution.created_at,
                ).asc(),
                WorkflowExecution.execution_id.asc(),
            )
            .limit(bounded)
            .all()
        )

        candidates: list[Dict[str, Any]] = []
        for row in rows:
            try:
                execution_key = _text(_field(row, "execution_id"))
                if not execution_key:
                    continue
                execution_status = _status_text(_field(row, "status"))
                if _is_cancelled_status(execution_status):
                    continue
                execution_terminal = (
                    execution_status in _TERMINAL_EXECUTION_STATUSES)

                context = _json_object(
                    _field(row, "context"), "workflow execution context")
                if _text(context.get("execution_id")) not in (
                        "", execution_key):
                    continue
                if _text(context.get("workflow_id")) not in (
                        "", _WORKFLOW_ID):
                    continue

                run_id = _text(context.get("run_id"))
                if run_id != _run_id(execution_key):
                    continue

                receipt = context.get(_OWNER_HANDOFF_CONTEXT_KEY)
                if _receipt_status(receipt) != "pending":
                    continue

                tenant_id = _text(context.get("tenant_id"))
                workspace_id = _text(context.get("workspace_id"))
                user_id = _text(context.get("user_id"))
                if not tenant_id or not workspace_id or not user_id:
                    continue
                if _text(_field(row, "tenant_id")) not in (
                        "", tenant_id):
                    continue
                if _text(_field(row, "workspace_id")) not in (
                        "", workspace_id):
                    continue
                if _text(_field(row, "user_id")) not in ("", user_id):
                    continue

                run = session.query(GoalRun).filter(
                    GoalRun.id == run_id,
                    GoalRun.tenant_id == tenant_id,
                    GoalRun.workspace_id == workspace_id,
                ).first()
                if run is None:
                    continue
                run_status = _status_text(_field(run, "status"))
                if _is_cancelled_status(run_status):
                    continue
                if not execution_terminal and run_status not in (
                        _TERMINAL_RUN_STATUSES):
                    continue

                parameters = _json_object(
                    _field(run, "parameters"), "goal run parameters")
                task_lifecycle = _field(parameters, "task_lifecycle")
                if not isinstance(task_lifecycle, Mapping):
                    continue
                assignment = _field(task_lifecycle, "assignment")
                if not isinstance(assignment, Mapping):
                    continue
                task_revision = _field(task_lifecycle, "task_revision")
                if _text(_field(task_revision, "authorization")).lower() == (
                        "cancelled"):
                    continue
                if _text(assignment.get("status")).lower() == "cancelled":
                    continue

                employee_id = _text(assignment.get("employee_id")) \
                    or _text(_field(run, "agent_id"))
                identity = {
                    "tenant_id": tenant_id,
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "employee_id": employee_id,
                }
                link = _extract_link(context)
                if link is None or not _link_matches(
                        link,
                        execution_key,
                        identity,
                        _goal_id(execution_key),
                        run_id,
                        run,
                        parameters,
                ):
                    continue

                first_trigger = _receipt_trigger(receipt) or {}
                invoice_number = _text(
                    first_trigger.get("invoice_number"))
                if not invoice_number:
                    invoice_number = _pending_handoff_invoice_number(
                        assignment)
                if not invoice_number:
                    continue

                candidates.append({
                    "execution_id": execution_key,
                    "run_id": run_id,
                    "invoice_number": invoice_number,
                    "identity": identity,
                })
            except Exception:  # noqa: BLE001 - one bad row cannot stop a scan
                continue
        return candidates


async def recover_pending_stock_invoice_owner_handoffs(
    *, limit: int = _PENDING_HANDOFF_SCAN_LIMIT,
) -> int:
    """Retry each discovered pending handoff at most once in this scan.

    The exact original operation and first source event are retained by the
    durable receipt.  Delivered receipts are excluded during discovery and are
    also terminal inside reconciliation.  Cancelled executions, runs or task
    revisions are skipped before any effect.  A failed retry leaves its
    truthful pending receipt for the next periodic scan.
    """
    attempted = 0
    for candidate in _pending_stock_invoice_owner_handoff_candidates(
            limit=limit):
        try:
            await reconcile_stock_invoice_owner_handoff(
                execution_id=candidate["execution_id"],
                run_id=candidate["run_id"],
                invoice_number=candidate["invoice_number"],
                identity=candidate["identity"],
                trigger=None,
            )
        except Exception:  # noqa: BLE001 - keep the scan bounded and alive
            continue
        attempted += 1
    return attempted
