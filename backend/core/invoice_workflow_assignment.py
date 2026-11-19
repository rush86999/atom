"""Persist a stock-invoice assignment against an existing workflow execution.

The execution row is the authorization anchor.  This module intentionally does
not execute the assignment; it only records a server-validated plan and the
goal/run that owns it.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import sqlite3
import uuid
from collections.abc import Mapping
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from core import notification_service
from core.assignment_plan import validate_assignment
from core.database import get_db_session
from core.models import GoalObjective, GoalRun, WorkflowExecution
from core.task_lifecycle import new_task_revision


_WORKFLOW_ID = "htn_invoice_followup"
_ACCOUNT_OWNER_CONTEXT_KEY = "_atom_account_owner_user_id"

# A stable namespace keeps the goal and run ids reproducible from the
# execution id alone.
_ASSIGNMENT_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "atom.invoice.workflow.assignment")


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


def _is_pending(status: Any) -> bool:
    value = getattr(status, "value", status)
    return _text(value).lower() == "pending"


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
