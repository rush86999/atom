"""
Chat Process Manager

Handles persistence of multi-step chat processes.
Supports pausing/resuming when parameters are missing.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from core.database_manager import db_manager

logger = logging.getLogger(__name__)


class ChatProcessManager:
    """
    Manages the state of multi-step chat processes.
    Persists state to database to allow resuming after restarts.
    """

    def __init__(self):
        self.db = db_manager

    async def create_process(
        self,
        user_id: str,
        name: str,
        steps: List[Dict[str, Any]],
        initial_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Initialize a new chat process"""
        process_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        query = """
            INSERT INTO chat_processes
            (id, user_id, name, current_step, total_steps, steps, context, inputs,
             outputs, status, missing_parameters, created_at, updated_at)
            VALUES (:id, :user_id, :name, :current_step, :total_steps, :steps, :context, :inputs,
             :outputs, :status, :missing_parameters, :created_at, :updated_at)
        """

        params = {
            "id": process_id,
            "user_id": user_id,
            "name": name,
            "current_step": 0,
            "total_steps": len(steps),
            "steps": json.dumps(steps),
            "context": json.dumps(initial_context or {}),
            "inputs": json.dumps({}),
            "outputs": json.dumps({}),
            "status": "active",
            "missing_parameters": json.dumps([]),
            "created_at": now,
            "updated_at": now
        }

        logger.debug(f"Query: {query}")
        logger.debug(f"Params: {params}")
        await self.db.execute(query, params)
        return process_id

    async def get_process(self, process_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve process state from storage"""
        query = "SELECT * FROM chat_processes WHERE id = :id"
        row = await self.db.fetch_one(query, {"id": process_id})

        if not row:
            return None

        # Deserialize JSON fields
        try:
            return {
                "id": row["id"],
                "user_id": row["user_id"],
                "name": row["name"],
                "current_step": row["current_step"],
                "total_steps": row["total_steps"],
                "steps": json.loads(row["steps"]) if row["steps"] else [],
                "context": json.loads(row["context"]) if row["context"] else {},
                "inputs": json.loads(row["inputs"]) if row["inputs"] else {},
                "outputs": json.loads(row["outputs"]) if row["outputs"] else {},
                "status": row["status"],
                "missing_parameters": json.loads(row["missing_parameters"]) if row["missing_parameters"] else [],
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"])
            }
        except Exception as e:
            logger.error(f"Error deserializing process state {process_id}: {e}")
            return None

    async def update_process_step(
        self,
        process_id: str,
        step_input: Dict[str, Any],
        step_output: Optional[Dict[str, Any]] = None,
        missing_parameters: Optional[List[str]] = None
    ):
        """Update process state after a step execution"""
        process = await self.get_process(process_id)
        if not process:
            raise ValueError(f"Process {process_id} not found")

        # Update inputs with new step input
        current_inputs = process["inputs"]
        current_inputs.update(step_input)

        # Update outputs if step_output provided
        current_outputs = process["outputs"]
        if step_output:
            step_id = f"step_{process['current_step']}"
            current_outputs[step_id] = step_output

        # Determine next step and status
        current_step = process["current_step"]
        total_steps = process["total_steps"]

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

        query = """
            UPDATE chat_processes
            SET current_step = :current_step, inputs = :inputs, outputs = :outputs, status = :status,
                missing_parameters = :missing_parameters, updated_at = :updated_at
            WHERE id = :id
        """

        await self.db.execute(
            query,
            {
                "current_step": next_step,
                "inputs": json.dumps(current_inputs),
                "outputs": json.dumps(current_outputs),
                "status": new_status,
                "missing_parameters": json.dumps(missing_parameters or []),
                "updated_at": datetime.now().isoformat(),
                "id": process_id
            }
        )

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
        process = await self.get_process(process_id)
        if not process:
            raise ValueError(f"Process {process_id} not found")

        if process["status"] != "paused":
            raise ValueError(f"Process {process_id} is not paused")

        # Update inputs with new values
        current_inputs = process["inputs"]
        current_inputs.update(new_inputs)

        # Clear missing parameters since we're providing them
        missing_params = process["missing_parameters"]
        for key in new_inputs.keys():
            if key in missing_params:
                missing_params.remove(key)

        query = """
            UPDATE chat_processes
            SET inputs = :inputs, missing_parameters = :missing_parameters, status = :status, updated_at = :updated_at
            WHERE id = :id
        """

        await self.db.execute(
            query,
            {
                "inputs": json.dumps(current_inputs),
                "missing_parameters": json.dumps(missing_params),
                "status": "active" if len(missing_params) == 0 else "paused",
                "updated_at": datetime.now().isoformat(),
                "id": process_id
            }
        )

        return {
            "status": "active" if len(missing_params) == 0 else "paused",
            "remaining_missing": missing_params
        }

    async def cancel_process(self, process_id: str):
        """Cancel an active process"""
        query = """
            UPDATE chat_processes
            SET status = 'cancelled', updated_at = :updated_at
            WHERE id = :id AND status IN ('active', 'paused')
        """

        await self.db.execute(
            query,
            {
                "updated_at": datetime.now().isoformat(),
                "id": process_id
            }
        )

    async def get_user_processes(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all processes for a user, optionally filtered by status"""
        if status:
            query = "SELECT * FROM chat_processes WHERE user_id = :user_id AND status = :status ORDER BY created_at DESC"
            rows = await self.db.fetch_all(query, {"user_id": user_id, "status": status})
        else:
            query = "SELECT * FROM chat_processes WHERE user_id = :user_id ORDER BY created_at DESC"
            rows = await self.db.fetch_all(query, {"user_id": user_id})

        processes = []
        for row in rows:
            try:
                processes.append({
                    "id": row["id"],
                    "name": row["name"],
                    "current_step": row["current_step"],
                    "total_steps": row["total_steps"],
                    "status": row["status"],
                    "created_at": str(row["created_at"]),
                    "updated_at": str(row["updated_at"])
                })
            except Exception as e:
                logger.error(f"Error deserializing process row: {e}")
                continue

        return processes


# Global instance
_process_manager = None

def get_process_manager() -> ChatProcessManager:
    global _process_manager
    if _process_manager is None:
        _process_manager = ChatProcessManager()
    return _process_manager