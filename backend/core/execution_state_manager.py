"""
Execution State Manager

Handles persistence of workflow execution state using SQLAlchemy async ORM.
Supports both SQLite and PostgreSQL backends.

MIGRATED: Now uses SQLAlchemy async ORM instead of raw SQL via database_manager
"""

from datetime import datetime
import json
import logging
from typing import Any, Dict, Optional
import uuid
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db_session
from core.models import WorkflowExecution

logger = logging.getLogger(__name__)


class ExecutionStateManager:
    """
    Manages the state of workflow executions.
    Persists state to database to allow resuming after restarts.

    Migrated to use SQLAlchemy async ORM instead of raw SQL.
    """

    async def create_execution(self, workflow_id: str, input_data: Dict[str, Any]) -> str:
        """Initialize a new execution state"""
        execution_id = str(uuid.uuid4())
        now = datetime.utcnow()

        async with get_async_db_session() as db:
            execution = WorkflowExecution(
                execution_id=execution_id,
                workflow_id=workflow_id,
                status="PENDING",
                input_data=json.dumps(input_data),
                steps=json.dumps({}),  # steps
                outputs=json.dumps({}),  # outputs
                context=json.dumps({}),  # context
                version=1,  # initial version
                created_at=now,
                updated_at=now
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
                "created_at": datetime.utcnow().isoformat()
            }

        step_state = steps[step_id]
        step_state["status"] = status
        step_state["updated_at"] = datetime.utcnow().isoformat()

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
                    updated_at=datetime.utcnow()
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
                    updated_at=datetime.utcnow()
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
                    updated_at=datetime.utcnow()
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

def get_state_manager() -> ExecutionStateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = ExecutionStateManager()
    return _state_manager
