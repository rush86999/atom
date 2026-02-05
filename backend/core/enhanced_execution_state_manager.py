"""
Enhanced Execution State Manager
Extends the existing ExecutionStateManager with multi-step, pause/resume, and multi-output support

MIGRATED: Now uses SQLAlchemy async ORM instead of raw SQL via database_manager
"""

import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db_session
from core.execution_state_manager import ExecutionStateManager, get_state_manager

logger = logging.getLogger(__name__)


class WorkflowState(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ParameterDefinition(BaseModel):
    """Enhanced parameter definition with validation and dependencies"""
    name: str
    type: str  # string, number, boolean, array, object, file
    label: str
    description: str
    required: bool = True
    default_value: Any = None
    validation_rules: Dict[str, Any] = {}
    options: List[str] = []  # For select/multiselect
    depends_on: Optional[str] = None  # Parameter that this depends on
    show_when: Optional[Dict[str, Any]] = None  # Condition to show this parameter
    multi_step: bool = False  # Can be collected across multiple steps


class MultiOutputConfig(BaseModel):
    """Configuration for multi-step outputs"""
    output_type: str  # single, multiple, aggregated, stream
    aggregation_method: Optional[str] = None  # merge, append, transform
    output_schema: Dict[str, Any] = {}
    step_outputs: Dict[str, List[str]] = {}  # Map step_id to output fields


class EnhancedExecutionState:
    """Enhanced execution state with multi-step tracking"""

    def __init__(self, execution_id: str, workflow_id: str):
        self.execution_id = execution_id
        self.workflow_id = workflow_id
        self.state = WorkflowState.PENDING
        self.current_step_index = 0
        self.total_steps = 0
        self.step_states: Dict[str, StepState] = {}
        self.step_inputs: Dict[str, Dict[str, Any]] = {}
        self.step_outputs: Dict[str, Dict[str, Any]] = {}
        self.required_inputs: List[ParameterDefinition] = []
        self.collected_inputs: Dict[str, Any] = {}
        self.missing_inputs: List[str] = []
        self.execution_context: Dict[str, Any] = {}
        self.multi_output_config: Optional[MultiOutputConfig] = None
        self.aggregated_outputs: Dict[str, Any] = {}
        self.pause_reason: Optional[str] = None
        self.error_details: Optional[str] = None
        self.created_at = datetime.now()
        self.updated_at = datetime.now()


class EnhancedExecutionStateManager(ExecutionStateManager):
    """Enhanced execution state manager with advanced features"""

    def __init__(self):
        super().__init__()
        self.enhanced_states: Dict[str, EnhancedExecutionState] = {}
        self.step_completion_callbacks: Dict[str, Callable] = {}
        self.pause_callbacks: Dict[str, Callable] = {}

    async def create_enhanced_execution(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        step_definitions: List[Dict[str, Any]],
        required_inputs: List[Dict[str, Any]],
        multi_output_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create enhanced execution with step tracking"""
        execution_id = str(uuid.uuid4())

        # Create base execution
        await self.create_execution(workflow_id, input_data)

        # Create enhanced state
        enhanced_state = EnhancedExecutionState(execution_id, workflow_id)
        enhanced_state.total_steps = len(step_definitions)
        enhanced_state.required_inputs = [ParameterDefinition(**inp) for inp in required_inputs]
        enhanced_state.collected_inputs = input_data.copy()

        if multi_output_config:
            enhanced_state.multi_output_config = MultiOutputConfig(**multi_output_config)

        # Initialize step states
        for step_def in step_definitions:
            enhanced_state.step_states[step_def["step_id"]] = StepState.PENDING
            enhanced_state.step_inputs[step_def["step_id"]] = {}

        # Store enhanced state
        self.enhanced_states[execution_id] = enhanced_state

        # Persist to database with enhanced fields
        await self._save_enhanced_state(enhanced_state)

        return execution_id

    async def get_enhanced_execution_state(self, execution_id: str) -> Optional[EnhancedExecutionState]:
        """Get enhanced execution state"""
        # Check memory first
        if execution_id in self.enhanced_states:
            return self.enhanced_states[execution_id]

        # Load from database
        base_state = await self.get_execution_state(execution_id)
        if not base_state:
            return None

        # Try to load enhanced fields from database
        try:
            async with get_async_db_session() as db:
                result = await db.execute(
                    text("SELECT enhanced_data FROM workflow_executions_enhanced WHERE execution_id = :execution_id"),
                    {"execution_id": execution_id}
                )
                row = result.fetchone()

                if row and row[0]:
                    enhanced_data = json.loads(row[0])

                    # Recreate enhanced state
                    enhanced_state = EnhancedExecutionState(execution_id, base_state["workflow_id"])

                    # Populate from enhanced data
                    enhanced_state.state = WorkflowState(enhanced_data.get("state", "pending"))
                    enhanced_state.current_step_index = enhanced_data.get("current_step_index", 0)
                    enhanced_state.step_states = {
                        k: StepState(v) for k, v in enhanced_data.get("step_states", {}).items()
                    }
                    enhanced_state.step_inputs = enhanced_data.get("step_inputs", {})
                    enhanced_state.step_outputs = enhanced_data.get("step_outputs", {})
                    enhanced_state.collected_inputs = enhanced_data.get("collected_inputs", {})
                    enhanced_state.missing_inputs = enhanced_data.get("missing_inputs", [])
                    enhanced_state.execution_context = enhanced_data.get("execution_context", {})
                    enhanced_state.aggregated_outputs = enhanced_data.get("aggregated_outputs", {})
                    enhanced_state.pause_reason = enhanced_data.get("pause_reason")
                    enhanced_state.error_details = enhanced_data.get("error_details")

                    if enhanced_data.get("multi_output_config"):
                        enhanced_state.multi_output_config = MultiOutputConfig(**enhanced_data["multi_output_config"])

                    self.enhanced_states[execution_id] = enhanced_state
                    return enhanced_state

        except Exception as e:
            logger.error(f"Error loading enhanced state {execution_id}: {e}")

        # Fallback: create basic enhanced state from base state
        enhanced_state = EnhancedExecutionState(execution_id, base_state["workflow_id"])
        enhanced_state.collected_inputs = base_state.get("input_data", {})
        enhanced_state.state = WorkflowState(base_state.get("status", "pending"))

        self.enhanced_states[execution_id] = enhanced_state
        return enhanced_state

    async def _save_enhanced_state(self, state: EnhancedExecutionState):
        """Save enhanced state to database"""
        enhanced_data = {
            "state": state.state.value,
            "current_step_index": state.current_step_index,
            "step_states": {k: v.value for k, v in state.step_states.items()},
            "step_inputs": state.step_inputs,
            "step_outputs": state.step_outputs,
            "collected_inputs": state.collected_inputs,
            "missing_inputs": state.missing_inputs,
            "execution_context": state.execution_context,
            "multi_output_config": state.multi_output_config.dict() if state.multi_output_config else None,
            "aggregated_outputs": state.aggregated_outputs,
            "pause_reason": state.pause_reason,
            "error_details": state.error_details
        }

        # Create enhanced table if not exists
        await self._ensure_enhanced_table()

        # Upsert enhanced state using SQLAlchemy
        async with get_async_db_session() as db:
            # Check if row exists
            result = await db.execute(
                text("SELECT execution_id FROM workflow_executions_enhanced WHERE execution_id = :execution_id"),
                {"execution_id": state.execution_id}
            )
            existing = result.fetchone()

            if existing:
                # Update
                await db.execute(
                    text("""
                        UPDATE workflow_executions_enhanced
                        SET enhanced_data = :enhanced_data, updated_at = :updated_at
                        WHERE execution_id = :execution_id
                    """),
                    {
                        "execution_id": state.execution_id,
                        "enhanced_data": json.dumps(enhanced_data),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )
            else:
                # Insert
                await db.execute(
                    text("""
                        INSERT INTO workflow_executions_enhanced
                        (execution_id, workflow_id, enhanced_data, updated_at)
                        VALUES (:execution_id, :workflow_id, :enhanced_data, :updated_at)
                    """),
                    {
                        "execution_id": state.execution_id,
                        "workflow_id": state.workflow_id,
                        "enhanced_data": json.dumps(enhanced_data),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )
            await db.commit()

    async def _ensure_enhanced_table(self):
        """Ensure enhanced workflow executions table exists"""
        async with get_async_db_session() as db:
            await db.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS workflow_executions_enhanced (
                        execution_id TEXT PRIMARY KEY,
                        workflow_id TEXT NOT NULL,
                        enhanced_data TEXT,
                        updated_at TEXT,
                        FOREIGN KEY (execution_id) REFERENCES workflow_executions (execution_id)
                    )
                """)
            )
            await db.commit()

    async def start_step_execution(
        self,
        execution_id: str,
        step_id: str,
        step_inputs: Dict[str, Any]
    ) -> bool:
        """Start execution of a specific step"""
        state = await self.get_enhanced_execution_state(execution_id)
        if not state:
            return False

        # Update step state
        state.step_states[step_id] = StepState.RUNNING
        state.step_inputs[step_id] = step_inputs
        state.state = WorkflowState.RUNNING
        state.updated_at = datetime.now()

        # Save state
        await self._save_enhanced_state(state)
        await self.update_step_status(execution_id, step_id, "RUNNING")

        return True

    async def complete_step(
        self,
        execution_id: str,
        step_id: str,
        outputs: Dict[str, Any],
        next_inputs: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark a step as completed and process outputs"""
        state = await self.get_enhanced_execution_state(execution_id)
        if not state:
            return False

        # Update step state and outputs
        state.step_states[step_id] = StepState.COMPLETED
        state.step_outputs[step_id] = outputs
        state.current_step_index += 1
        state.updated_at = datetime.now()

        # Process multi-output aggregation
        if state.multi_output_config:
            await self._aggregate_outputs(state, step_id, outputs)

        # Add next inputs to collected inputs
        if next_inputs:
            state.collected_inputs.update(next_inputs)

        # Check if workflow is complete
        if state.current_step_index >= state.total_steps:
            state.state = WorkflowState.COMPLETED
            await self.update_execution_status(execution_id, "COMPLETED")
        else:
            # Check for missing inputs for next step
            missing = await self._check_missing_inputs(state)
            if missing:
                state.state = WorkflowState.WAITING_FOR_INPUT
                state.missing_inputs = missing

                # Trigger pause callback if registered
                if execution_id in self.pause_callbacks:
                    try:
                        await self.pause_callbacks[execution_id](state)
                    except Exception as e:
                        logger.error(f"Error in pause callback: {e}")

        # Save state
        await self._save_enhanced_state(state)
        await self.update_step_status(execution_id, step_id, "COMPLETED", outputs)

        return True

    async def pause_execution(
        self,
        execution_id: str,
        reason: str = "User requested pause",
        step_inputs: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Pause workflow execution"""
        state = await self.get_enhanced_execution_state(execution_id)
        if not state:
            return False

        state.state = WorkflowState.PAUSED
        state.pause_reason = reason
        state.updated_at = datetime.now()

        # Add any provided inputs
        if step_inputs:
            state.collected_inputs.update(step_inputs)

        # Save state
        await self._save_enhanced_state(state)
        await self.update_execution_status(execution_id, "PAUSED")

        return True

    async def resume_execution(
        self,
        execution_id: str,
        additional_inputs: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Resume paused workflow execution"""
        state = await self.get_enhanced_execution_state(execution_id)
        if not state or state.state != WorkflowState.PAUSED:
            return False

        # Add additional inputs
        if additional_inputs:
            state.collected_inputs.update(additional_inputs)

        # Check if all required inputs are now available
        missing = await self._check_missing_inputs(state)
        if missing:
            # Still missing inputs, update but keep paused
            state.missing_inputs = missing
            await self._save_enhanced_state(state)
            return False

        # All inputs available, resume
        state.state = WorkflowState.RUNNING
        state.pause_reason = None
        state.missing_inputs = []
        state.updated_at = datetime.now()

        # Save state
        await self._save_enhanced_state(state)
        await self.update_execution_status(execution_id, "RUNNING")

        return True

    async def fail_step(
        self,
        execution_id: str,
        step_id: str,
        error: str,
        can_retry: bool = True
    ) -> bool:
        """Mark a step as failed"""
        state = await self.get_enhanced_execution_state(execution_id)
        if not state:
            return False

        state.step_states[step_id] = StepState.FAILED
        state.error_details = error
        state.updated_at = datetime.now()

        # Save state
        await self._save_enhanced_state(state)
        await self.update_step_status(execution_id, step_id, "FAILED", error=error)

        return True

    async def skip_step(
        self,
        execution_id: str,
        step_id: str,
        reason: str = "Step skipped by user"
    ) -> bool:
        """Skip a step"""
        state = await self.get_enhanced_execution_state(execution_id)
        if not state:
            return False

        state.step_states[step_id] = StepState.SKIPPED
        state.current_step_index += 1
        state.updated_at = datetime.now()

        # Save state
        await self._save_enhanced_state(state)
        await self.update_step_status(execution_id, step_id, "SKIPPED")

        return True

    async def _check_missing_inputs(self, state: EnhancedExecutionState) -> List[str]:
        """Check for missing required inputs"""
        missing = []

        for param in state.required_inputs:
            if param.required and param.name not in state.collected_inputs:
                # Check if parameter should be shown based on conditions
                if self._should_show_parameter(param, state.collected_inputs):
                    missing.append(param.name)

        return missing

    def _should_show_parameter(self, param: ParameterDefinition, inputs: Dict[str, Any]) -> bool:
        """Check if parameter should be shown based on conditions"""
        if not param.show_when:
            return True

        # Simple condition evaluation
        for param_name, condition in param.show_when.items():
            if param_name not in inputs:
                continue

            if isinstance(condition, dict):
                for operator, value in condition.items():
                    if operator == "equals" and inputs[param_name] != value:
                        return False
                    elif operator == "not_equals" and inputs[param_name] == value:
                        return False
                    elif operator == "contains" and value not in str(inputs[param_name]):
                        return False
            else:
                if inputs[param_name] != condition:
                    return False

        return True

    async def _aggregate_outputs(
        self,
        state: EnhancedExecutionState,
        step_id: str,
        outputs: Dict[str, Any]
    ):
        """Aggregate outputs according to multi-output configuration"""
        if not state.multi_output_config:
            return

        config = state.multi_output_config

        if config.output_type == "multiple":
            # Store outputs as array
            if step_id not in state.aggregated_outputs:
                state.aggregated_outputs[step_id] = []
            state.aggregated_outputs[step_id].append(outputs)

        elif config.output_type == "aggregated":
            # Merge outputs
            for key, value in outputs.items():
                if key not in state.aggregated_outputs:
                    state.aggregated_outputs[key] = []
                state.aggregated_outputs[key].append(value)

        elif config.output_type == "stream":
            # Stream outputs (for real-time processing)
            state.aggregated_outputs[f"stream_{step_id}"] = outputs

    async def get_progress(self, execution_id: str) -> Dict[str, Any]:
        """Get workflow execution progress"""
        state = await self.get_enhanced_execution_state(execution_id)
        if not state:
            return {"error": "Execution not found"}

        completed_steps = sum(
            1 for step_state in state.step_states.values()
            if step_state in [StepState.COMPLETED, StepState.SKIPPED]
        )

        progress_percentage = (completed_steps / max(state.total_steps, 1)) * 100

        return {
            "execution_id": execution_id,
            "state": state.state.value,
            "total_steps": state.total_steps,
            "completed_steps": completed_steps,
            "current_step_index": state.current_step_index,
            "progress_percentage": round(progress_percentage, 2),
            "step_states": {k: v.value for k, v in state.step_states.items()},
            "missing_inputs": state.missing_inputs,
            "pause_reason": state.pause_reason,
            "updated_at": state.updated_at.isoformat()
        }

    async def get_step_details(self, execution_id: str, step_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific step"""
        state = await self.get_enhanced_execution_state(execution_id)
        if not state:
            return {"error": "Execution not found"}

        step_state = state.step_states.get(step_id)
        step_inputs = state.step_inputs.get(step_id, {})
        step_outputs = state.step_outputs.get(step_id, {})

        return {
            "step_id": step_id,
            "state": step_state.value if step_state else "unknown",
            "inputs": step_inputs,
            "outputs": step_outputs,
            "is_current": state.current_step_index < state.total_steps and \
                        list(state.step_states.keys())[state.current_step_index] == step_id
        }

    def register_pause_callback(self, execution_id: str, callback: Callable):
        """Register a callback to be called when execution is paused"""
        self.pause_callbacks[execution_id] = callback

    def register_step_completion_callback(self, execution_id: str, callback: Callable):
        """Register a callback to be called when a step completes"""
        self.step_completion_callbacks[execution_id] = callback


# Global instance
_enhanced_state_manager = None

def get_enhanced_state_manager() -> EnhancedExecutionStateManager:
    """Get the global enhanced state manager instance"""
    global _enhanced_state_manager
    if _enhanced_state_manager is None:
        _enhanced_state_manager = EnhancedExecutionStateManager()
    return _enhanced_state_manager
