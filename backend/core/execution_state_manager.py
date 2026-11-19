"""
Execution State Manager

Handles persistence of workflow execution state using SQLAlchemy async ORM.
Supports both SQLite and PostgreSQL backends.

MIGRATED: Now uses SQLAlchemy async ORM instead of raw SQL via database_manager
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional
import uuid
from sqlalchemy import select, update
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

    async def update_execution_status(self, execution_id: str, status: str, error: Optional[str] = None):
        """Update the overall execution status"""
        async with get_async_db_session() as db:
            await db.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.execution_id == execution_id)
                .values(
                    status=status,
                    error=error,
                    version=WorkflowExecution.version + 1,
                    updated_at=datetime.now(timezone.utc)
                )
            )
            await db.commit()

    async def update_execution_inputs(self, execution_id: str, new_inputs: Dict[str, Any]):
        """Update execution inputs (e.g. for resume)"""
        state = await self.get_execution_state(execution_id)
        if not state:
            raise ValueError(f"Execution {execution_id} not found")

        current_inputs = state["input_data"]
        current_inputs.update(new_inputs)

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
