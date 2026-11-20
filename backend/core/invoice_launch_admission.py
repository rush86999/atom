"""Shared admission boundary for the stock invoice launch workflow.

The service in this module deliberately sits *behind* the future route layer.
It compiles the assignment on the server, reserves (or replays) the
deterministic execution slot, runs the existing task-level never-autonomous
gate, and only then attaches the plan.  It does not start an execution, call an
invoice provider, send a message, or expose a public route.

Keeping attachment after the gate is important: the generic background
assignment recovery executes plans that are already attached to a run.  A plan
attached before review/policy clearance would therefore become executable
without the task-level admission ever being granted.
"""

from __future__ import annotations

import asyncio
import copy
import functools
import json
import threading
import weakref
from collections.abc import Mapping
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from core.execution_state_manager import (
    INVOICE_LAUNCH_WORKFLOW_ID,
    InvoiceLaunchConflict,
    get_state_manager,
    normalize_execution_identity,
)
from core.invoice_reminder_plan import build_invoice_reminder_plan
from core.invoice_workflow_assignment import attach_stock_invoice_assignment
from core.workflow_engine import WorkflowEngine

__all__ = [
    "STOCK_INVOICE_LAUNCH_WORKFLOW_ID",
    "InvoiceLaunchConflict",
    "StockInvoiceLaunchAdmissionService",
    "admit_stock_invoice_launch",
    "build_stock_invoice_launch_assignment",
    "build_stock_invoice_launch_workflow",
]

#: The durable workflow id shared with the reservation and assignment modules.
STOCK_INVOICE_LAUNCH_WORKFLOW_ID = INVOICE_LAUNCH_WORKFLOW_ID

_SCOPE_KEYS = ("tenant_id", "workspace_id", "user_id")
_TERMINAL_STATUSES = frozenset({
    "completed", "failed", "cancelled", "canceled", "timed_out", "terminated",
})
_PAUSED = "paused"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _status_text(value: Any) -> str:
    return _text(getattr(value, "value", value)).lower()


def _identity_values(identity: Any) -> Dict[str, str]:
    """Return the trusted execution scope, refusing caller-invented gaps.

    ``employee_id`` is optional for the reservation, but the assignment is
    bound to an executor.  When the trusted caller does not carry a separate
    employee id, the authenticated actor is that executor (the same convention
    as the stock reminder plan builder).
    """
    if identity is None:
        raw_identity: Dict[str, Any] = {}
    elif isinstance(identity, Mapping):
        raw_identity = dict(identity)
    else:
        raw_identity = {
            key: getattr(identity, key, None)
            for key in (*_SCOPE_KEYS, "employee_id")
        }

    values = normalize_execution_identity(raw_identity)
    for key in _SCOPE_KEYS:
        if not values.get(key):
            raise ValueError(
                "identity must include tenant_id, workspace_id and user_id")

    employee_id = _text(raw_identity.get("employee_id"))
    if employee_id:
        values["employee_id"] = employee_id
    else:
        values["employee_id"] = values["user_id"]
    return values


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


def _invoice_number(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("invoice_number must be a non-blank string")
    return value


def build_stock_invoice_launch_assignment(
    invoice_number: str,
    *,
    identity: Any,
) -> Dict[str, Any]:
    """Compile the trusted stock-invoice assignment on the server.

    No caller-supplied plan is accepted.  The exact invoice and trusted scope
    are the only inputs, so a retry cannot quietly substitute different steps.
    """
    invoice = _invoice_number(invoice_number)
    values = _identity_values(identity)
    plan = build_invoice_reminder_plan(
        invoice_number=invoice,
        user_id=values["employee_id"],
        workspace_id=values["workspace_id"],
        tenant_id=values["tenant_id"],
    )
    return copy.deepcopy(plan)


def build_stock_invoice_launch_workflow(
    invoice_number: str,
    *,
    identity: Any,
    assignment: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the deterministic workflow material used by task admission.

    The task fingerprint must be stable across a paused attempt and the later
    approved retry.  Every material field is therefore derived only from the
    invoice and trusted scope (or the already server-compiled assignment).
    """
    invoice = _invoice_number(invoice_number)
    values = _identity_values(identity)
    plan = (
        copy.deepcopy(dict(assignment))
        if isinstance(assignment, Mapping)
        else build_stock_invoice_launch_assignment(
            invoice, identity=values)
    )
    objective = _text(plan.get("objective"))
    owner_user_id = values["user_id"]
    agent_id = values["employee_id"]

    return {
        "id": STOCK_INVOICE_LAUNCH_WORKFLOW_ID,
        "name": "Stock invoice follow-up",
        "description": objective,
        "goal": objective,
        "objective": objective,
        "created_by": owner_user_id,
        "user_id": owner_user_id,
        "agent_id": agent_id,
        "tenant_id": values["tenant_id"],
        "workspace_id": values["workspace_id"],
        "invoice_number": invoice,
        "assignment": copy.deepcopy(plan),
        "steps": copy.deepcopy(list(plan.get("steps") or [])),
    }


def _paused_result(
    execution_id: str,
    *,
    created: bool,
    admission: Any = None,
    reason: str = "",
) -> Dict[str, Any]:
    return {
        "execution_id": execution_id,
        "run_id": None,
        "created": created,
        "status": _PAUSED,
        "admission_status": _PAUSED,
        "paused": True,
        "review_required": True,
        "requires_review": True,
        "attached": False,
        "terminal": False,
        "reason": _text(reason),
        "admission": copy.deepcopy(admission),
    }


def _terminal_result(
    execution_id: str,
    *,
    created: bool,
    status: str,
) -> Dict[str, Any]:
    return {
        "execution_id": execution_id,
        "run_id": None,
        "created": created,
        "status": status or "terminal",
        "admission_status": status or "terminal",
        "paused": False,
        "review_required": False,
        "requires_review": False,
        "attached": False,
        "terminal": True,
        "reason": "",
        "admission": None,
    }


def _attached_result(
    execution_id: str,
    *,
    created: bool,
    run_id: str,
    admission: Any = None,
) -> Dict[str, Any]:
    return {
        "execution_id": execution_id,
        "run_id": run_id,
        "created": created,
        "status": "attached",
        "admission_status": "allowed",
        "paused": False,
        "review_required": False,
        "requires_review": False,
        "attached": True,
        "terminal": False,
        "reason": "",
        "admission": copy.deepcopy(admission),
    }


class _LaunchLock:
    """One event-loop-local async lock and its acquired/waiter count."""

    __slots__ = ("lock", "references")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.references = 0


# Coordinate the *whole* same-execution admission sequence, not just the final
# sync attachment.  Locks belong to the running event loop because asyncio
# primitives are loop-bound.  The registry is weakly keyed by loop and each
# key is removed as soon as its last holder/waiter leaves, so replaying many
# idempotency keys cannot grow it without bound.  Different event loops (and
# other processes) remain independent and rely on the durable DB guards.
_LAUNCH_LOCKS: "weakref.WeakKeyDictionary[Any, Dict[tuple, _LaunchLock]]" = (
    weakref.WeakKeyDictionary()
)
_LAUNCH_LOCKS_GUARD = threading.Lock()


def _launch_lock_key(
    identity: Mapping[str, str],
    idempotency_key: str,
) -> tuple:
    """Return the deterministic trusted scope/idempotency coordination key."""
    return (
        identity["tenant_id"],
        identity["workspace_id"],
        identity["user_id"],
        idempotency_key,
    )


def _release_launch_lock(
    loop: Any,
    key: tuple,
    entry: _LaunchLock,
) -> None:
    with _LAUNCH_LOCKS_GUARD:
        entry.references -= 1
        if entry.references > 0 or entry.lock.locked():
            return
        per_loop = _LAUNCH_LOCKS.get(loop)
        if per_loop is None or per_loop.get(key) is not entry:
            return
        del per_loop[key]
        if not per_loop:
            try:
                del _LAUNCH_LOCKS[loop]
            except KeyError:
                pass


@asynccontextmanager
async def _launch_lock(key: tuple):
    """Hold the event-loop-local lock for one deterministic launch slot."""
    loop = asyncio.get_running_loop()
    with _LAUNCH_LOCKS_GUARD:
        per_loop = _LAUNCH_LOCKS.get(loop)
        if per_loop is None:
            per_loop = {}
            _LAUNCH_LOCKS[loop] = per_loop
        entry = per_loop.get(key)
        if entry is None:
            entry = _LaunchLock()
            per_loop[key] = entry
        entry.references += 1

    try:
        await entry.lock.acquire()
    except BaseException:  # noqa: BLE001 - cancellation is re-raised
        # The waiter never held the lock; drop only its registry reference.
        _release_launch_lock(loop, key, entry)
        raise

    try:
        yield
    finally:
        entry.lock.release()
        _release_launch_lock(loop, key, entry)


def _attach_plan_blocking(
    execution_id: str,
    invoice: str,
    *,
    identity: Dict[str, str],
    plan: Dict[str, Any],
    account_owner: Optional[str],
) -> Dict[str, str]:
    return attach_stock_invoice_assignment(
        execution_id,
        invoice,
        identity=identity,
        assignment=plan,
        account_owner_user_id=account_owner,
    )


async def _attach_plan(
    execution_id: str,
    invoice: str,
    identity: Dict[str, str],
    plan: Dict[str, Any],
    account_owner: Optional[str],
) -> str:
    # Same-slot admission is already serialized by the event-loop-local lock,
    # so this offload needs no process-wide attachment lock.  Independent
    # slots may attach in parallel and rely on the attacher's durable guards.
    attached = await asyncio.get_running_loop().run_in_executor(
        None,
        functools.partial(
            _attach_plan_blocking,
            execution_id,
            invoice,
            identity=identity,
            plan=plan,
            account_owner=account_owner,
        ),
    )
    return _text(attached.get("run_id"))


def _linked_run_id(state: Mapping[str, Any]) -> str:
    context = state.get("context") if isinstance(state, Mapping) else None
    if isinstance(context, (str, bytes, bytearray)):
        try:
            context = json.loads(context)
        except (TypeError, ValueError):
            return ""
    if not isinstance(context, Mapping):
        return ""
    return _text(context.get("run_id"))


def _gate_paused(admission: Any) -> bool:
    if admission is None:
        return False
    if isinstance(admission, str):
        return admission.strip().lower() in (
            "paused", "pause", "review", "blocked")
    if isinstance(admission, Mapping):
        outcome = _text(
            admission.get("outcome") or admission.get("status")).lower()
        if outcome in ("review", "paused", "blocked", "denied"):
            return True
        return admission.get("paused") is True
    return False


async def _run_task_gate(
    *,
    state_manager: Any,
    engine: Any,
    execution_id: str,
    workflow: Dict[str, Any],
    state: Dict[str, Any],
    identity: Dict[str, str],
    admission_action_id: Any,
) -> Any:
    """Invoke the existing WorkflowEngine task-level admission gate."""
    # The real gate publishes PAUSED through its engine's state manager.  Bind
    # the exact manager used to reserve this slot so an injected/scratch store
    # is never bypassed by a process-global singleton.
    if (isinstance(engine, WorkflowEngine)
            and getattr(engine, "state_manager", None) is not state_manager):
        try:
            engine.state_manager = state_manager
        except Exception:  # noqa: BLE001 - immutable doubles are fine
            pass

    method = getattr(engine, "admit_never_autonomous_task", None)
    if not callable(method):
        raise RuntimeError("workflow task admission gate is unavailable")

    kwargs = {
        "execution_id": execution_id,
        "workflow": workflow,
        "state": state,
        "user_id": identity["user_id"],
        "workspace_id": identity["workspace_id"],
        "tenant_id": identity["tenant_id"],
    }
    if admission_action_id is not None:
        kwargs["admission_action_id"] = admission_action_id
    return await method(**kwargs)


async def _reserve_launch(
    state_manager: Any,
    invoice: str,
    *,
    identity: Dict[str, str],
    idempotency_key: str,
    account_owner: Optional[str],
) -> Any:
    reserve = getattr(state_manager, "reserve_invoice_launch", None)
    if not callable(reserve):
        raise RuntimeError("invoice launch reservation is unavailable")
    kwargs = {
        "identity": identity,
        "idempotency_key": idempotency_key,
    }
    if account_owner is not None:
        kwargs["account_owner_user_id"] = account_owner
    return await reserve(invoice, **kwargs)


async def _mark_policy_paused(
    state_manager: Any,
    execution_id: str,
    reason: str,
) -> None:
    update = getattr(state_manager, "update_execution_status", None)
    if not callable(update):
        return
    state = await _execution_state(state_manager, execution_id)
    if _status_text(state.get("status")) in _TERMINAL_STATUSES:
        return
    try:
        await update(execution_id, "PAUSED", error=reason)
    except TypeError:
        try:
            await update(execution_id, "PAUSED")
        except Exception:  # noqa: BLE001 - the gate already failed closed
            pass
    except Exception:  # noqa: BLE001 - the gate already failed closed
        pass


async def _execution_state(
    state_manager: Any,
    execution_id: str,
) -> Dict[str, Any]:
    getter = getattr(state_manager, "get_execution_state", None)
    if not callable(getter):
        return {}
    state = await getter(execution_id)
    return state if isinstance(state, Mapping) else {}


async def _paused_or_terminal_result(
    state_manager: Any,
    execution_id: str,
    *,
    created: bool,
    admission: Any = None,
    reason: str = "",
) -> Dict[str, Any]:
    """Return the durable terminal status when a pause raced a cancellation.

    A gate may have reported a pause (or failed) while another request committed
    a terminal status.  The reservation row is authoritative: report that exact
    status and never attach a plan or create new work for it.
    """
    state = await _execution_state(state_manager, execution_id)
    status = _status_text(state.get("status"))
    if status in _TERMINAL_STATUSES:
        return _terminal_result(
            execution_id, created=created, status=status)
    return _paused_result(
        execution_id,
        created=created,
        admission=admission,
        reason=reason,
    )


async def _restore_pending_for_attachment(
    state_manager: Any,
    execution_id: str,
) -> bool:
    """Make a PAUSED reservation attachable without reopening terminal work."""
    state = await _execution_state(state_manager, execution_id)
    if not state:
        # A minimal injected manager may not expose state reads.  The real
        # attacher still performs every exact scope/link/status check.
        return True
    status = _status_text(state.get("status"))
    if not status or status == "pending":
        return True
    if status != _PAUSED:
        return False

    restore = getattr(
        state_manager, "restore_paused_invoice_launch", None)
    if not callable(restore) or not await restore(execution_id):
        return False

    state = await _execution_state(state_manager, execution_id)
    return _status_text(state.get("status")) == "pending"


async def admit_stock_invoice_launch(
    invoice_number: str,
    identity: Any = None,
    idempotency_key: Any = None,
    *,
    account_owner_user_id: Optional[str] = None,
    state_manager: Any = None,
    engine: Any = None,
    admission_action_id: Any = None,
    actor: Any = None,
) -> Dict[str, Any]:
    """Reserve, admit and attach one stock invoice launch.

    The deterministic execution slot comes from the trusted actor plus
    ``idempotency_key``.  The invoice is immutable in the reservation, and the
    account owner is carried explicitly through every retry so attachment uses
    the same owner binding.

    The task-level never-autonomous gate is evaluated *before* any GoalRun or
    assignment exists.  A review/policy pause therefore leaves only the bare
    reservation.  On an approved retry the same gate must pass again; only then
    may the narrow PAUSED -> PENDING transition be used and the server-built
    plan attached.  Terminal and cancelled reservations stay terminal.

    Same-slot calls are serialized for the complete reserve/gate/restore/attach
    sequence on the current event loop.  Independent scope/idempotency tuples
    are not globally serialized; cross-process contention remains guarded by
    the reservation primary key and the assignment's durable checks.
    """
    invoice = _invoice_number(invoice_number)
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("idempotency_key must be a non-blank string")
    if identity is None:
        identity = actor
    owner = _optional_account_owner(account_owner_user_id)
    values = _identity_values(identity)

    async with _launch_lock(_launch_lock_key(values, idempotency_key)):
        return await _admit_stock_invoice_launch_locked(
            invoice,
            idempotency_key=idempotency_key,
            identity=values,
            account_owner=owner,
            state_manager=state_manager,
            engine=engine,
            admission_action_id=admission_action_id,
        )


async def _admit_stock_invoice_launch_locked(
    invoice: str,
    *,
    idempotency_key: str,
    identity: Dict[str, str],
    account_owner: Optional[str],
    state_manager: Any,
    engine: Any,
    admission_action_id: Any,
) -> Dict[str, Any]:
    manager = (
        state_manager if state_manager is not None else get_state_manager())
    plan = build_stock_invoice_launch_assignment(
        invoice, identity=identity)
    workflow = build_stock_invoice_launch_workflow(
        invoice, identity=identity, assignment=plan)

    execution_id, created = await _reserve_launch(
        manager,
        invoice,
        identity=identity,
        idempotency_key=idempotency_key,
        account_owner=account_owner,
    )

    state = await _execution_state(manager, execution_id)
    status = _status_text(state.get("status"))
    linked_run_id = _linked_run_id(state)
    if status in _TERMINAL_STATUSES:
        if not linked_run_id:
            # A terminal reservation is never reopened or attached.  Do not
            # even evaluate policy: a policy outage must not rewrite terminal
            # state, and there is no new work to admit.
            return _terminal_result(
                execution_id, created=created, status=status)
        # Already attached before it became terminal: replay is read-only and
        # keeps the exact owner-conflict guarantee.
        run_id = await _attach_plan(
            execution_id, invoice, identity, plan, account_owner)
        return _attached_result(
            execution_id,
            created=created,
            run_id=run_id,
            admission=None,
        )

    try:
        admission = await _run_task_gate(
            state_manager=manager,
            engine=(
                engine if engine is not None
                else WorkflowEngine()),
            execution_id=execution_id,
            workflow=workflow,
            state=state,
            identity=identity,
            admission_action_id=admission_action_id,
        )
    except Exception:  # noqa: BLE001 - configured policy fails CLOSED
        reason = (
            "Never-autonomous task policy could not be evaluated; "
            "human review is required.")
        await _mark_policy_paused(manager, execution_id, reason)
        return await _paused_or_terminal_result(
            manager,
            execution_id,
            created=created,
            admission=None,
            reason=reason,
        )

    if _gate_paused(admission):
        reason = ""
        if isinstance(admission, Mapping):
            reason = _text(
                admission.get("reason") or admission.get("error"))
        state = await _execution_state(manager, execution_id)
        if (_status_text(state.get("status")) != _PAUSED
                and _status_text(state.get("status")) not in _TERMINAL_STATUSES):
            await _mark_policy_paused(
                manager,
                execution_id,
                reason or "Human review is required.",
            )
        return await _paused_or_terminal_result(
            manager,
            execution_id,
            created=created,
            admission=admission,
            reason=reason,
        )

    # Re-read after the gate.  A concurrent cancellation is authoritative; a
    # normal paused reservation may be restored once, and only once, for this
    # attachment attempt.  An already-linked execution is replayed through the
    # same attacher so owner conflicts keep their typed identity even after the
    # run became terminal (the replay itself writes nothing).
    state = await _execution_state(manager, execution_id)
    linked_run_id = _linked_run_id(state)
    if not linked_run_id:
        status = _status_text(state.get("status"))
        if status in _TERMINAL_STATUSES:
            return _terminal_result(
                execution_id, created=created, status=status)
        if not await _restore_pending_for_attachment(manager, execution_id):
            state = await _execution_state(manager, execution_id)
            status = _status_text(state.get("status")) or "not_pending"
            return _terminal_result(
                execution_id, created=created, status=status)

    run_id = await _attach_plan(
        execution_id, invoice, identity, plan, account_owner)
    return _attached_result(
        execution_id,
        created=created,
        run_id=run_id,
        admission=admission,
    )


class StockInvoiceLaunchAdmissionService:
    """Object wrapper around :func:`admit_stock_invoice_launch`."""

    def __init__(
        self,
        *,
        state_manager: Any = None,
        engine: Any = None,
    ):
        self.state_manager = state_manager
        self.engine = engine

    async def admit(
        self,
        invoice_number: str,
        identity: Any = None,
        idempotency_key: Any = None,
        *,
        account_owner_user_id: Optional[str] = None,
        admission_action_id: Any = None,
        actor: Any = None,
    ) -> Dict[str, Any]:
        return await admit_stock_invoice_launch(
            invoice_number,
            identity=identity,
            idempotency_key=idempotency_key,
            account_owner_user_id=account_owner_user_id,
            state_manager=self.state_manager,
            engine=self.engine,
            admission_action_id=admission_action_id,
            actor=actor,
        )
