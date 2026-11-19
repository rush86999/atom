"""
Execution State Manager

Handles persistence of workflow execution state using SQLAlchemy async ORM.
Supports both SQLite and PostgreSQL backends.

MIGRATED: Now uses SQLAlchemy async ORM instead of raw SQL via database_manager
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Dict, Optional, Tuple
import uuid
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db_session
from core.models import WorkflowExecution
import threading

logger = logging.getLogger(__name__)

# Reserved execution-input key carrying the authenticated caller's frozen
# scope. The durable writer only persists it from the explicit, trusted
# ``identity`` argument; a copy already present in caller-supplied
# ``input_data`` is stripped. Defined here because the state manager is the
# component that stamps the persisted row and owns the durable channel.
EXECUTION_SCOPE_KEY = "_atom_execution_scope"

_SCOPE_KEYS = ("tenant_id", "workspace_id", "user_id")

INVOICE_LAUNCH_WORKFLOW_ID = "htn_invoice_followup"
# Reserved execution-input key for the server-stamped invoice intent digest.
INVOICE_INTENT_KEY = "_atom_invoice_intent"
INVOICE_LAUNCH_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "atom:invoice-launch:htn_invoice_followup"
)
_MAX_IDEMPOTENCY_KEY_LENGTH = 255


class InvoiceLaunchConflict(RuntimeError):
    """An invoice idempotency slot is already bound to another intent."""


def _invoice_intent_digest(invoice_number: str) -> str:
    return hashlib.sha256(
        invoice_number.encode("utf-8", "surrogatepass")
    ).hexdigest()


def _invoice_launch_slot(identity: Dict[str, str], idempotency_key: str) -> str:
    """Return the deterministic execution id for a scoped idempotency key."""
    material = json.dumps(
        [
            identity["tenant_id"],
            identity["workspace_id"],
            identity["user_id"],
            idempotency_key,
        ],
        separators=(",", ":"),
    )
    return str(uuid.uuid5(INVOICE_LAUNCH_NAMESPACE, material))


def _is_execution_id_primary_key_violation(error: IntegrityError) -> bool:
    """True only for a duplicate ``execution_id`` primary-key conflict.

    ``str(IntegrityError)`` names every INSERT column and exposes its
    parameters, including on an unrelated constraint, so the text of the
    wrapped error is never used for classification. SQLite is matched by the
    original driver error's exact duplicate-column list. PostgreSQL is
    matched by the driver's ``23505`` SQLSTATE together with the exact
    primary-key constraint name, including an asyncpg exception supplied as
    ``orig.__cause__``.
    """
    orig = getattr(error, "orig", None)
    if orig is None:
        return False

    table = getattr(WorkflowExecution, "__table__", None)
    table_name = getattr(WorkflowExecution, "__tablename__", None) or getattr(
        table, "name", None
    )
    table_name = str(table_name or "workflow_executions")

    if str(orig).strip() == (
        f"UNIQUE constraint failed: {table_name}.execution_id"
    ):
        return True

    candidates = [orig]
    cause = getattr(orig, "__cause__", None)
    if cause is not None:
        candidates.append(cause)

    expected_constraint = getattr(
        getattr(table, "primary_key", None), "name", None
    ) or f"{table_name}_pkey"
    for candidate in candidates:
        sqlstate = (
            getattr(candidate, "sqlstate", None)
            or getattr(candidate, "pgcode", None)
            or getattr(candidate, "code", None)
        )
        if str(sqlstate) != "23505":
            continue
        constraint_name = getattr(candidate, "constraint_name", None)
        if not constraint_name:
            diag = getattr(candidate, "diag", None)
            constraint_name = getattr(diag, "constraint_name", None)
        if constraint_name == expected_constraint:
            return True
    return False


def _is_matching_invoice_reservation(
    execution: Optional[WorkflowExecution],
    digest: str,
    trusted: Dict[str, str],
) -> bool:
    """Validate the raw durable row owns the replaying caller's frozen scope."""
    if execution is None:
        return False
    if execution.workflow_id != INVOICE_LAUNCH_WORKFLOW_ID:
        return False

    actor = trusted.get("user_id") or ""
    tenant = trusted.get("tenant_id") or ""
    if not actor or not tenant:
        return False
    if normalize_scope_token(execution.user_id) != actor:
        return False
    if normalize_scope_token(execution.owner_id) != actor:
        return False
    if normalize_scope_token(execution.tenant_id) != tenant:
        return False

    try:
        inputs = json.loads(execution.input_data) if execution.input_data else {}
    except (TypeError, ValueError):
        return False
    if not isinstance(inputs, dict):
        return False
    if inputs.get(INVOICE_INTENT_KEY) != digest:
        return False
    return normalize_execution_identity(inputs.get(EXECUTION_SCOPE_KEY)) == trusted


def normalize_scope_token(value: Any) -> str:
    """Normalize an authoritative identity value to a JSON/pickle-safe token.

    Auth providers hand ids back as strings, ints or UUIDs. Anything else
    (an ORM object, a claim container, a boolean) is not a provable identity
    and is dropped instead of being stringified into the frozen scope.
    """
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (str, int, uuid.UUID)):
        return str(value).strip()
    return ""


def normalize_execution_identity(
    identity: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Normalize an explicit, trusted execution identity mapping.

    Only the scope keys are read. Missing or non-provable values are dropped;
    they are never invented from caller input.
    """
    if not isinstance(identity, dict):
        return {}
    normalized: Dict[str, str] = {}
    for key in _SCOPE_KEYS:
        token = normalize_scope_token(identity.get(key))
        if token:
            normalized[key] = token
    return normalized


def frozen_execution_identity(
    input_data: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Return the trusted, server-frozen identity from execution inputs.

    Only the reserved scope key is read; plain caller keys named ``user_id``,
    ``owner_id`` or ``tenant_id`` in job input are never identity.
    """
    if not isinstance(input_data, dict):
        return {}
    return normalize_execution_identity(input_data.get(EXECUTION_SCOPE_KEY))


class ExecutionStateManager:
    """
    Manages the state of workflow executions.
    Persists state to database to allow resuming after restarts.

    Migrated to use SQLAlchemy async ORM instead of raw SQL.
    """

    async def create_execution(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        *,
        identity: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Initialize a new execution state.

        ``identity`` is the explicit, trusted scope supplied by the caller that
        authenticated the run (``WorkflowEngine.start_workflow``). It is the
        only source of durable ownership; a reserved marker already present in
        ``input_data`` is untrusted and stripped, so a direct caller cannot
        stamp a receipt by crafting job input. The normalized trusted scope is
        kept in the persisted inputs for the engine (and every later resume).

        The row's ``user_id``/``owner_id``/``tenant_id`` are stamped only when
        the trusted scope proves an actor together with both tenant and
        workspace. A trusted ownerless scope (a legacy schedule with no actor)
        keeps its tenant/workspace in the inputs but leaves all receipt columns
        NULL: stamping the tenant alone would turn it into tenant-wide
        visibility in the read filter.
        """
        execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        durable_inputs = dict(input_data) if isinstance(input_data, dict) else {}
        durable_inputs.pop(EXECUTION_SCOPE_KEY, None)
        durable_inputs.pop(INVOICE_INTENT_KEY, None)
        trusted = normalize_execution_identity(identity)
        if trusted:
            durable_inputs[EXECUTION_SCOPE_KEY] = trusted

        actor_user_id = trusted.get("user_id") or ""
        tenant_id = trusted.get("tenant_id") or ""
        workspace_id = trusted.get("workspace_id") or ""
        if actor_user_id and tenant_id and workspace_id:
            receipt = {
                "user_id": actor_user_id,
                "owner_id": actor_user_id,
                "tenant_id": tenant_id,
            }
        else:
            receipt = {"user_id": None, "owner_id": None, "tenant_id": None}

        async with get_async_db_session() as db:
            execution = WorkflowExecution(
                execution_id=execution_id,
                workflow_id=workflow_id,
                status="PENDING",
                input_data=json.dumps(durable_inputs),
                steps=json.dumps({}),  # steps
                outputs=json.dumps({}),  # outputs
                context=json.dumps({}),  # context
                version=1,  # initial version
                created_at=now,
                updated_at=now,
                **receipt,
            )

            db.add(execution)
            await db.commit()

        logger.debug(f"Created execution {execution_id} for workflow {workflow_id}")
        return execution_id

    async def _get_raw_execution(
        self, execution_id: str
    ) -> Optional[WorkflowExecution]:
        """Read the durable row for collision verification."""
        async with get_async_db_session() as db:
            result = await db.execute(
                select(WorkflowExecution).where(
                    WorkflowExecution.execution_id == execution_id
                )
            )
            return result.scalar_one_or_none()

    async def reserve_invoice_launch(
        self,
        invoice_number: str,
        *,
        identity: Optional[Dict[str, Any]],
        idempotency_key: str,
    ) -> Tuple[str, bool]:
        """Reserve one deterministic invoice-launch execution.

        Returns ``(execution_id, created)``. Replaying the same scoped
        idempotency key and invoice returns the existing execution; reusing the
        key for another invoice raises :class:`InvoiceLaunchConflict`.
        """
        if type(invoice_number) is not str or not invoice_number.strip():
            raise ValueError("invoice_number must be a non-blank string")
        if type(idempotency_key) is not str or not idempotency_key.strip():
            raise ValueError("idempotency_key must be a non-blank string")
        if len(idempotency_key) > _MAX_IDEMPOTENCY_KEY_LENGTH:
            raise ValueError("idempotency_key is too long")

        trusted = normalize_execution_identity(identity)
        if any(not trusted.get(key) for key in _SCOPE_KEYS):
            raise ValueError(
                "identity must include tenant_id, workspace_id and user_id"
            )

        digest = _invoice_intent_digest(invoice_number)
        execution_id = _invoice_launch_slot(trusted, idempotency_key)

        now = datetime.now(timezone.utc)
        receipt = {
            "user_id": trusted["user_id"],
            "owner_id": trusted["user_id"],
            "tenant_id": trusted["tenant_id"],
        }
        try:
            async with get_async_db_session() as db:
                execution = WorkflowExecution(
                    execution_id=execution_id,
                    workflow_id=INVOICE_LAUNCH_WORKFLOW_ID,
                    status="PENDING",
                    input_data=json.dumps(
                        {
                            "invoice_number": invoice_number,
                            EXECUTION_SCOPE_KEY: trusted,
                            INVOICE_INTENT_KEY: digest,
                        }
                    ),
                    steps=json.dumps({}),
                    outputs=json.dumps({}),
                    context=json.dumps({}),
                    version=1,
                    created_at=now,
                    updated_at=now,
                    **receipt,
                )
                db.add(execution)
                await db.commit()
        except IntegrityError as error:
            if not _is_execution_id_primary_key_violation(error):
                raise
            existing = await self._get_raw_execution(execution_id)
            if existing is None:
                raise
            if not _is_matching_invoice_reservation(
                existing, digest, trusted
            ):
                raise InvoiceLaunchConflict(
                    "idempotency key is already bound to another invoice"
                ) from error
            return execution_id, False

        logger.debug(
            f"Reserved invoice launch {execution_id} for "
            f"workflow {INVOICE_LAUNCH_WORKFLOW_ID}"
        )
        return execution_id, True

    async def update_step_status(
        self,
        execution_id: str,
        step_id: str,
        status: str,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """Update the status and output of a specific step"""
        state = await self.get_execution_state(execution_id)
        if not state:
            raise ValueError(f"Execution {execution_id} not found")

        # Update steps map
        steps = state["steps"]
        if step_id not in steps:
            steps[step_id] = {
                "id": step_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

        step_state = steps[step_id]
        step_state["status"] = status
        step_state["updated_at"] = datetime.now(timezone.utc).isoformat()

        if output is not None:
            step_state["output"] = output
            state["outputs"][step_id] = output

        if error is not None:
            step_state["error"] = error

        # Update DB with version increment
        async with get_async_db_session() as db:
            await db.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.execution_id == execution_id)
                .values(
                    steps=json.dumps(steps),
                    outputs=json.dumps(state["outputs"]),
                    version=WorkflowExecution.version + 1,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()

    async def update_execution_status(self, execution_id: str, status: str, error: Optional[str] = None) -> bool:
        """Update the overall execution status and report whether it matched.

        A durable ``CANCELLED`` is authoritative over later runner writes.
        Cancellation may be accepted by a different engine instance (or by an
        API/UI surface) than the one still executing the workflow, so a late
        ``RUNNING``, ``PAUSED``, ``COMPLETED``, ``PARTIAL`` or ``FAILED`` write
        must not replace it. Repeating the cancellation itself stays allowed.
        The check is part of the SQL update so two workers cannot race between
        reading the status and writing it.

        Returns ``True`` when the conditional UPDATE matched a row. ``False``
        means the write was rejected (for example the row is already
        ``CANCELLED``): callers must not publish or announce the status change
        they attempted. Older/fake managers that return ``None`` remain
        compatible; only an explicit ``False`` is a rejection.
        """
        async with get_async_db_session() as db:
            statement = update(WorkflowExecution).where(
                WorkflowExecution.execution_id == execution_id
            )
            if str(status or "").strip().upper() != "CANCELLED":
                statement = statement.where(
                    func.coalesce(
                        func.upper(WorkflowExecution.status), ""
                    ) != "CANCELLED"
                )
            result = await db.execute(
                statement.values(
                    status=status,
                    error=error,
                    version=WorkflowExecution.version + 1,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()
            rowcount = getattr(result, "rowcount", 0)
            return bool(rowcount and rowcount > 0)

    async def update_execution_inputs(self, execution_id: str, new_inputs: Dict[str, Any]):
        """Update execution inputs (e.g. for resume)"""
        state = await self.get_execution_state(execution_id)
        if not state:
            raise ValueError(f"Execution {execution_id} not found")

        current_inputs = state["input_data"]
        is_invoice_reservation = (
            state.get("workflow_id") == INVOICE_LAUNCH_WORKFLOW_ID
            and isinstance(current_inputs.get(INVOICE_INTENT_KEY), str)
        )
        retained = {}
        if is_invoice_reservation:
            for key in (EXECUTION_SCOPE_KEY, INVOICE_INTENT_KEY):
                if key in current_inputs:
                    retained[key] = current_inputs[key]

        current_inputs.update(new_inputs)

        if is_invoice_reservation:
            for key in (EXECUTION_SCOPE_KEY, INVOICE_INTENT_KEY):
                if key in retained:
                    current_inputs[key] = retained[key]
                else:
                    current_inputs.pop(key, None)

        async with get_async_db_session() as db:
            await db.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.execution_id == execution_id)
                .values(
                    input_data=json.dumps(current_inputs),
                    version=WorkflowExecution.version + 1,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()

    async def get_execution_state(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve execution state from storage"""
        async with get_async_db_session() as db:
            result = await db.execute(
                select(WorkflowExecution).where(WorkflowExecution.execution_id == execution_id)
            )
            execution = result.scalar_one_or_none()

            if not execution:
                return None

            # Deserialize JSON fields
            try:
                return {
                    "execution_id": execution.execution_id,
                    "workflow_id": execution.workflow_id,
                    "status": execution.status,
                    "version": execution.version,
                    "input_data": json.loads(execution.input_data) if execution.input_data else {},
                    "steps": json.loads(execution.steps) if execution.steps else {},
                    "outputs": json.loads(execution.outputs) if execution.outputs else {},
                    "context": json.loads(execution.context) if execution.context else {},
                    "created_at": execution.created_at.isoformat() if execution.created_at else None,
                    "updated_at": execution.updated_at.isoformat() if execution.updated_at else None,
                    "error": execution.error
                }
            except Exception as e:
                logger.error(f"Error deserializing execution state {execution_id}: {e}")
                return None

    async def get_step_output(self, execution_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """Get the output of a specific step"""
        state = await self.get_execution_state(execution_id)
        if not state:
            return None
        return state["outputs"].get(step_id)


# Global instance
_state_manager = None
_state_manager_lock = __import__('threading').Lock()
def get_state_manager() -> ExecutionStateManager:
    global _state_manager
    if _state_manager is None:
        with _state_manager_lock:
            if _state_manager is None:
                _state_manager = ExecutionStateManager()
    return _state_manager
