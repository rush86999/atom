"""
Execution State Manager

Handles persistence of workflow execution state using DatabaseManager.
Supports both SQLite and PostgreSQL backends.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from .database_manager import db_manager

logger = logging.getLogger(__name__)

class ExecutionStateManager:
    """
    Manages the state of workflow executions.
    Persists state to database to allow resuming after restarts.
    """
    
    def __init__(self):
        self.db = db_manager
        
    async def create_execution(self, workflow_id: str, input_data: Dict[str, Any]) -> str:
        """Initialize a new execution state"""
        execution_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        query = """
            INSERT INTO workflow_executions
            (execution_id, workflow_id, status, input_data, steps, outputs, context, version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            execution_id,
            workflow_id,
            "PENDING",
            json.dumps(input_data),
            json.dumps({}),  # steps
            json.dumps({}),  # outputs
            json.dumps({}),  # context
            1,  # initial version
            now,
            now
        )
        
        await self.db.execute(query, params)
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
                "created_at": datetime.now().isoformat()
            }
            
        step_state = steps[step_id]
        step_state["status"] = status
        step_state["updated_at"] = datetime.now().isoformat()
        
        if output is not None:
            step_state["output"] = output
            state["outputs"][step_id] = output
            
        if error is not None:
            step_state["error"] = error
            
        # Update DB with version increment
        query = """
            UPDATE workflow_executions
            SET steps = ?, outputs = ?, version = version + 1, updated_at = ?
            WHERE execution_id = ?
        """

        await self.db.execute(
            query,
            (
                json.dumps(steps),
                json.dumps(state["outputs"]),
                datetime.now().isoformat(),
                execution_id
            )
        )
        
    async def update_execution_status(self, execution_id: str, status: str, error: Optional[str] = None):
        """Update the overall execution status"""
        query = """
            UPDATE workflow_executions
            SET status = ?, error = ?, version = version + 1, updated_at = ?
            WHERE execution_id = ?
        """

        await self.db.execute(
            query,
            (
                status,
                error,
                datetime.now().isoformat(),
                execution_id
            )
        )

    async def update_execution_inputs(self, execution_id: str, new_inputs: Dict[str, Any]):
        """Update execution inputs (e.g. for resume)"""
        state = await self.get_execution_state(execution_id)
        if not state:
            raise ValueError(f"Execution {execution_id} not found")
            
        current_inputs = state["input_data"]
        current_inputs.update(new_inputs)
        
        query = """
            UPDATE workflow_executions
            SET input_data = ?, version = version + 1, updated_at = ?
            WHERE execution_id = ?
        """

        await self.db.execute(
            query,
            (
                json.dumps(current_inputs),
                datetime.now().isoformat(),
                execution_id
            )
        )
        
    async def get_execution_state(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve execution state from storage"""
        query = "SELECT * FROM workflow_executions WHERE execution_id = ?"
        row = await self.db.fetch_one(query, (execution_id,))
        
        if not row:
            return None
            
        # Deserialize JSON fields
        try:
            return {
                "execution_id": row["execution_id"],
                "workflow_id": row["workflow_id"],
                "status": row["status"],
                "version": row.get("version", 1),  # Default to 1 for backward compatibility
                "input_data": json.loads(row["input_data"]) if row["input_data"] else {},
                "steps": json.loads(row["steps"]) if row["steps"] else {},
                "outputs": json.loads(row["outputs"]) if row["outputs"] else {},
                "context": json.loads(row["context"]) if row["context"] else {},
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "error": row["error"]
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
