"""
Chat Process Manager

Handles persistence of multi-step chat processes.
Supports pausing/resuming when parameters are missing.

MIGRATED: Now uses SQLAlchemy async ORM instead of deprecated database_manager
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db_session
from core.models import ChatProcess

logger = logging.getLogger(__name__)


class ChatProcessManager:
    """
    Manages the state of multi-step chat processes.
    Persists state to database to allow resuming after restarts.

    Migrated to use SQLAlchemy async ORM instead of raw SQL.
    """

    async def create_process(
        self,
        user_id: str,
        name: str,
        steps: List[Dict[str, Any]],
        initial_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Initialize a new chat process"""
        process_id = str(uuid.uuid4())
        now = datetime.utcnow()

        async with get_async_db_session() as db:
            process = ChatProcess(
                id=process_id,
                user_id=user_id,
                name=name,
                current_step=0,
                total_steps=len(steps),
                steps=steps,
                context=initial_context or {},
                inputs={},
                outputs={},
                status="active",
                missing_parameters=[],
                created_at=now,
                updated_at=now
            )

            db.add(process)
            await db.commit()

        logger.debug(f"Created chat process {process_id} for user {user_id}")
        return process_id

    async def get_process(self, process_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve process state from storage"""
        async with get_async_db_session() as db:
            result = await db.execute(
                select(ChatProcess).where(ChatProcess.id == process_id)
            )
            process = result.scalar_one_or_none()

            if not process:
                return None

            # Convert to dict
            try:
                return {
                    "id": process.id,
                    "user_id": process.user_id,
                    "name": process.name,
                    "current_step": process.current_step,
                    "total_steps": process.total_steps,
                    "steps": process.steps if isinstance(process.steps, list) else json.loads(process.steps),
                    "context": process.context if isinstance(process.context, dict) else json.loads(process.context),
                    "inputs": process.inputs if isinstance(process.inputs, dict) else json.loads(process.inputs),
                    "outputs": process.outputs if isinstance(process.outputs, dict) else json.loads(process.outputs),
                    "status": process.status,
                    "missing_parameters": process.missing_parameters if isinstance(process.missing_parameters, list) else json.loads(process.missing_parameters),
                    "created_at": process.created_at.isoformat() if process.created_at else None,
                    "updated_at": process.updated_at.isoformat() if process.updated_at else None
                }
            except Exception as e:
                logger.error(f"Error converting process {process_id}: {e}")
                return None

    async def update_process_step(
        self,
        process_id: str,
        step_input: Dict[str, Any],
        step_output: Optional[Dict[str, Any]] = None,
        missing_parameters: Optional[List[str]] = None
    ):
        """Update process state after a step execution"""
        async with get_async_db_session() as db:
            result = await db.execute(
                select(ChatProcess).where(ChatProcess.id == process_id)
            )
            process = result.scalar_one_or_none()

            if not process:
                raise ValueError(f"Process {process_id} not found")

            # Update inputs with new step input
            current_inputs = process.inputs if isinstance(process.inputs, dict) else json.loads(process.inputs)
            current_inputs.update(step_input)

            # Update outputs if step_output provided
            current_outputs = process.outputs if isinstance(process.outputs, dict) else json.loads(process.outputs)
            if step_output:
                step_id = f"step_{process.current_step}"
                current_outputs[step_id] = step_output

            # Determine next step and status
            current_step = process.current_step
            total_steps = process.total_steps

            if missing_parameters and len(missing_parameters) > 0:
                # Pause process due to missing parameters
                new_status = "paused"
                next_step = current_step  # Stay on same step
            elif current_step + 1 < total_steps:
                # Move to next step
                new_status = "active"
                next_step = current_step + 1
            else:
                # Process completed
                new_status = "completed"
                next_step = current_step

            # Update process
            process.current_step = next_step
            process.inputs = current_inputs
            process.outputs = current_outputs
            process.status = new_status
            process.missing_parameters = missing_parameters or []
            process.updated_at = datetime.utcnow()

            await db.commit()

        return {
            "next_step": next_step,
            "status": new_status,
            "missing_parameters": missing_parameters or []
        }

    async def resume_process(
        self,
        process_id: str,
        new_inputs: Dict[str, Any]
    ):
        """Resume a paused process with new inputs"""
        async with get_async_db_session() as db:
            result = await db.execute(
                select(ChatProcess).where(ChatProcess.id == process_id)
            )
            process = result.scalar_one_or_none()

            if not process:
                raise ValueError(f"Process {process_id} not found")

            if process.status != "paused":
                raise ValueError(f"Process {process_id} is not paused")

            # Update inputs with new values
            current_inputs = process.inputs if isinstance(process.inputs, dict) else json.loads(process.inputs)
            current_inputs.update(new_inputs)

            # Clear missing parameters since we're providing them
            missing_params = process.missing_parameters if isinstance(process.missing_parameters, list) else json.loads(process.missing_parameters)
            for key in new_inputs.keys():
                if key in missing_params:
                    missing_params.remove(key)

            # Update process
            process.inputs = current_inputs
            process.missing_parameters = missing_params
            process.status = "active" if len(missing_params) == 0 else "paused"
            process.updated_at = datetime.utcnow()

            await db.commit()

        return {
            "status": "active" if len(missing_params) == 0 else "paused",
            "remaining_missing": missing_params
        }

    async def cancel_process(self, process_id: str):
        """Cancel an active process"""
        async with get_async_db_session() as db:
            result = await db.execute(
                select(ChatProcess).where(
                    ChatProcess.id == process_id,
                    ChatProcess.status.in_(["active", "paused"])
                )
            )
            process = result.scalar_one_or_none()

            if process:
                process.status = "cancelled"
                process.updated_at = datetime.utcnow()
                await db.commit()

    async def get_user_processes(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all processes for a user, optionally filtered by status"""
        async with get_async_db_session() as db:
            if status:
                result = await db.execute(
                    select(ChatProcess).where(
                        ChatProcess.user_id == user_id,
                        ChatProcess.status == status
                    ).order_by(ChatProcess.created_at.desc())
                )
            else:
                result = await db.execute(
                    select(ChatProcess).where(
                        ChatProcess.user_id == user_id
                    ).order_by(ChatProcess.created_at.desc())
                )

            processes = result.scalars().all()

            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "current_step": p.current_step,
                    "total_steps": p.total_steps,
                    "status": p.status,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None
                }
                for p in processes
            ]


# Global instance
_process_manager = None

def get_process_manager() -> ChatProcessManager:
    global _process_manager
    if _process_manager is None:
        _process_manager = ChatProcessManager()
    return _process_manager