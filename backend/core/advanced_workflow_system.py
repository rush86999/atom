"""
Advanced Workflow System
Supports multi-input, multi-step, multi-output workflows with state management
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable
from enum import Enum
from pydantic import BaseModel, Field, validator
import asyncio
import logging

logger = logging.getLogger(__name__)

class ParameterType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    FILE = "file"
    SELECT = "select"
    MULTISELECT = "multiselect"

class WorkflowState(str, Enum):
    DRAFT = "draft"
    WAITING_FOR_INPUT = "waiting_for_input"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class InputParameter(BaseModel):
    name: str
    type: ParameterType
    label: str
    description: str
    required: bool = True
    default_value: Any = None
    validation_rules: Dict[str, Any] = {}
    options: List[str] = []  # For select/multiselect
    depends_on: Optional[str] = None  # Parameter that this depends on
    show_when: Optional[Dict[str, Any]] = None  # Condition to show this parameter

class WorkflowStep(BaseModel):
    step_id: str
    name: str
    description: str
    step_type: str
    input_parameters: List[InputParameter] = []
    output_schema: Dict[str, Any] = {}
    depends_on: List[str] = []  # Previous step IDs
    condition: Optional[str] = None  # Condition to execute this step
    retry_config: Dict[str, Any] = {}
    timeout_seconds: int = 300
    can_pause: bool = True
    is_parallel: bool = False

class MultiOutputConfig(BaseModel):
    output_type: str  # "multiple_files", "dataset", "report", "stream"
    output_parameters: List[InputParameter]
    aggregation_method: Optional[str] = None  # For multiple outputs

class AdvancedWorkflowDefinition(BaseModel):
    workflow_id: str
    name: str
    description: str
    version: str = "1.0"
    category: str = "general"
    tags: List[str] = []

    # Multi-input support
    input_schema: List[InputParameter] = []

    # Multi-step support
    steps: List[WorkflowStep] = []
    step_connections: List[Dict[str, str]] = []  # step connections

    # Multi-output support
    output_config: Optional[MultiOutputConfig] = None

    # State management
    state: WorkflowState = WorkflowState.DRAFT
    current_step: Optional[str] = None

    # Execution context
    execution_context: Dict[str, Any] = {}
    user_inputs: Dict[str, Any] = {}
    step_results: Dict[str, Any] = {}

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[str] = None

    @validator('steps', each_item=True)
    def validate_step_ids(cls, v):
        if isinstance(v, WorkflowStep):
            v.step_id = str(v.step_id)
        return v

    def advance_to_step(self, step_id: str):
        """Advance workflow to specific step"""
        self.current_step = step_id
        self.updated_at = datetime.now()

    def get_missing_inputs(self, provided_inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get missing required inputs based on current context"""
        missing = []

        for param in self.input_schema:
            # Check if parameter should be shown
            if not self._should_show_parameter(param, provided_inputs):
                continue

            # Check if parameter is required and not provided
            if param.required and param.name not in provided_inputs:
                missing.append({
                    "name": param.name,
                    "label": param.label,
                    "description": param.description,
                    "type": param.type.value,
                    "default_value": param.default_value,
                    "options": param.options
                })

        return missing

    def _should_show_parameter(self, param: InputParameter, inputs: Dict[str, Any]) -> bool:
        """Check if parameter should be shown based on conditions"""
        if not param.show_when:
            return True

        # Simple condition evaluation
        for field_name, condition in param.show_when.items():
            if field_name not in inputs:
                return False

            if isinstance(condition, list):
                # Parameter should be shown if field value is in the list
                if inputs[field_name] not in condition:
                    return False
            else:
                # Parameter should be shown if field value matches
                if inputs[field_name] != condition:
                    return False

        return True

    def add_step_output(self, step_id: str, output: Dict[str, Any]):
        """Add output from a step"""
        self.step_results[step_id] = {
            "output": output,
            "timestamp": datetime.now().isoformat()
        }
        self.updated_at = datetime.now()

    def get_all_outputs(self) -> Dict[str, Any]:
        """Get all outputs from all completed steps"""
        return {step_id: step_data["output"] for step_id, step_data in self.step_results.items()}

class WorkflowExecutionPlan(BaseModel):
    workflow_id: str
    execution_id: str
    planned_steps: List[str]  # Order of step execution
    parallel_groups: List[List[str]] = []  # Steps that can run in parallel
    estimated_duration: int = 0
    required_inputs: List[str]  # Required parameters for next step

class StateManager:
    """Manages workflow state persistence and restoration"""

    def __init__(self):
        self.state_store: Dict[str, Dict[str, Any]] = {}

    def save_state(self, workflow_id: str, state: Dict[str, Any]) -> bool:
        """Save workflow state"""
        try:
            state["saved_at"] = datetime.now().isoformat()
            self.state_store[workflow_id] = state

            # Also persist to file for durability
            self._persist_to_file(workflow_id, state)
            return True
        except Exception as e:
            logger.error(f"Failed to save state for {workflow_id}: {e}")
            return False

    def load_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load workflow state"""
        try:
            # Try memory first
            if workflow_id in self.state_store:
                return self.state_store[workflow_id]

            # Try file storage
            state = self._load_from_file(workflow_id)
            if state:
                self.state_store[workflow_id] = state
                return state

            return None
        except Exception as e:
            logger.error(f"Failed to load state for {workflow_id}: {e}")
            return None

    def _persist_to_file(self, workflow_id: str, state: Dict[str, Any]):
        """Persist state to file"""
        import os
        os.makedirs("workflow_states", exist_ok=True)
        filename = f"workflow_states/{workflow_id}.json"

        with open(filename, 'w') as f:
            json.dump(state, f, indent=2, default=str)

    def _load_from_file(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load state from file"""
        import os
        filename = f"workflow_states/{workflow_id}.json"

        if not os.path.exists(filename):
            return None

        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except Exception:
            return None

class ParameterValidator:
    """Validates workflow input parameters"""

    @staticmethod
    def validate_parameter(param: InputParameter, value: Any) -> tuple[bool, Optional[str]]:
        """Validate a single parameter"""
        try:
            # Check if required
            if param.required and value is None:
                if param.default_value is not None:
                    return True, None
                return False, f"{param.label} is required"

            # Use default value if None
            if value is None and param.default_value is not None:
                value = param.default_value

            # Type validation
            if param.type == ParameterType.STRING:
                if not isinstance(value, str):
                    return False, f"{param.label} must be a string"

            elif param.type == ParameterType.NUMBER:
                if not isinstance(value, (int, float)):
                    return False, f"{param.label} must be a number"

            elif param.type == ParameterType.BOOLEAN:
                if not isinstance(value, bool):
                    return False, f"{param.label} must be true or false"

            elif param.type == ParameterType.ARRAY:
                if not isinstance(value, list):
                    return False, f"{param.label} must be an array"

            elif param.type in [ParameterType.SELECT, ParameterType.MULTISELECT]:
                if param.type == ParameterType.SELECT:
                    if value not in param.options:
                        return False, f"{param.label} must be one of: {', '.join(param.options)}"
                else:  # MULTISELECT
                    if not all(v in param.options for v in value):
                        return False, f"All {param.label} values must be from: {', '.join(param.options)}"

            # Custom validation rules
            for rule_name, rule_value in param.validation_rules.items():
                if rule_name == "min_length" and len(str(value)) < rule_value:
                    return False, f"{param.label} must be at least {rule_value} characters"

                elif rule_name == "max_length" and len(str(value)) > rule_value:
                    return False, f"{param.label} must be at most {rule_value} characters"

                elif rule_name == "min_value" and value < rule_value:
                    return False, f"{param.label} must be at least {rule_value}"

                elif rule_name == "max_value" and value > rule_value:
                    return False, f"{param.label} must be at most {rule_value}"

                elif rule_name == "pattern" and not re.match(rule_value, str(value)):
                    return False, f"{param.label} format is invalid"

            return True, None

        except Exception as e:
            logger.error(f"Parameter validation error: {e}")
            return False, f"Validation failed: {str(e)}"

class ExecutionEngine:
    """Advanced workflow execution engine"""

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.running_workflows: Dict[str, asyncio.Task] = {}

    async def create_workflow(self, definition: Dict[str, Any]) -> AdvancedWorkflowDefinition:
        """Create a new workflow"""
        workflow = AdvancedWorkflowDefinition(**definition)

        # Validate workflow structure
        validation_result = self._validate_workflow(workflow)
        if not validation_result[0]:
            raise ValueError(f"Invalid workflow: {validation_result[1]}")

        # Save initial state
        self.state_manager.save_state(workflow.workflow_id, workflow.dict())

        return workflow

    def _validate_workflow(self, workflow: AdvancedWorkflowDefinition) -> tuple[bool, Optional[str]]:
        """Validate workflow structure"""
        try:
            # Check step dependencies
            for step in workflow.steps:
                for dep_id in step.depends_on:
                    if not any(s.step_id == dep_id for s in workflow.steps):
                        return False, f"Step {step.step_id} depends on non-existent step {dep_id}"

            # Check for circular dependencies
            if self._has_circular_dependencies(workflow.steps):
                return False, "Workflow has circular dependencies"

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _has_circular_dependencies(self, steps: List[WorkflowStep]) -> bool:
        """Check for circular dependencies using DFS"""
        visited = set()
        rec_stack = set()

        def has_cycle(step_id: str) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)

            step = next((s for s in steps if s.step_id == step_id), None)
            if not step:
                return False

            for dep_id in step.depends_on:
                if dep_id not in visited:
                    if has_cycle(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(step_id)
            return False

        for step in steps:
            if step.step_id not in visited:
                if has_cycle(step.step_id):
                    return True

        return False

    async def start_workflow(self, workflow_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Start or resume workflow execution"""
        # Load workflow state
        state = self.state_manager.load_state(workflow_id)
        if not state:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow = AdvancedWorkflowDefinition(**state)

        # Validate inputs
        missing_inputs = self._get_missing_inputs(workflow, inputs)
        if missing_inputs:
            workflow.state = WorkflowState.WAITING_FOR_INPUT
            workflow.user_inputs.update(inputs)
            self.state_manager.save_state(workflow_id, workflow.dict())

            return {
                "status": "waiting_for_input",
                "missing_parameters": missing_inputs,
                "current_step": workflow.current_step
            }

        # Start execution
        workflow.user_inputs.update(inputs)
        workflow.state = WorkflowState.RUNNING

        # Create execution plan
        plan = self._create_execution_plan(workflow)

        # Save state and start execution
        self.state_manager.save_state(workflow_id, workflow.dict())

        # Run workflow in background
        task = asyncio.create_task(self._execute_workflow(workflow, plan))
        self.running_workflows[workflow_id] = task

        return {
            "status": "started",
            "execution_id": plan.execution_id,
            "planned_steps": plan.planned_steps
        }

    def _get_missing_inputs(self, workflow: AdvancedWorkflowDefinition, provided_inputs: Dict[str, Any]) -> List[InputParameter]:
        """Get missing required inputs for current step"""
        missing = []

        # Check global inputs
        for param in workflow.input_schema:
            if param.required and param.name not in provided_inputs:
                # Check if parameter should be shown based on conditions
                if self._should_show_parameter(param, provided_inputs):
                    missing.append(param)

        # Check current step inputs
        if workflow.current_step:
            current_step = next((s for s in workflow.steps if s.step_id == workflow.current_step), None)
            if current_step:
                for param in current_step.input_parameters:
                    if param.required and param.name not in provided_inputs:
                        if self._should_show_parameter(param, provided_inputs):
                            missing.append(param)

        return missing

    def _should_show_parameter(self, param: InputParameter, inputs: Dict[str, Any]) -> bool:
        """Check if parameter should be shown based on conditions"""
        if not param.show_when:
            return True

        # Simple condition evaluation
        # Format: {"parameter_name": "value"} or {"parameter_name": {"operator": "value"}}
        for param_name, condition in param.show_when.items():
            if param_name not in inputs:
                continue

            if isinstance(condition, dict):
                # Complex condition
                for operator, value in condition.items():
                    if operator == "equals" and inputs[param_name] != value:
                        return False
                    elif operator == "not_equals" and inputs[param_name] == value:
                        return False
                    elif operator == "contains" and value not in str(inputs[param_name]):
                        return False
            else:
                # Simple equals condition
                if inputs[param_name] != condition:
                    return False

        return True

    def _create_execution_plan(self, workflow: AdvancedWorkflowDefinition) -> WorkflowExecutionPlan:
        """Create execution plan for workflow"""
        plan = WorkflowExecutionPlan(
            workflow_id=workflow.workflow_id,
            execution_id=str(uuid.uuid4()),
            planned_steps=[],
            parallel_groups=[],
            required_inputs=[]
        )

        # Build execution order considering dependencies
        executed = set()
        to_execute = set(step.step_id for step in workflow.steps if not step.depends_on)

        while to_execute:
            current_batch = []
            next_batch = set()

            for step_id in to_execute:
                if step_id not in executed:
                    step = next(s for s in workflow.steps if s.step_id == step_id)

                    # Check if all dependencies are executed
                    if all(dep in executed for dep in step.depends_on):
                        current_batch.append(step_id)
                        executed.add(step_id)

                        # Add next steps
                        for other_step in workflow.steps:
                            if step_id in other_step.depends_on and other_step.step_id not in executed:
                                next_batch.add(other_step.step_id)

            plan.planned_steps.extend(current_batch)

            # Check if current batch can run in parallel
            if len(current_batch) > 1:
                plan.parallel_groups.append(current_batch)

            to_execute = next_batch

        return plan

    async def _execute_workflow(self, workflow: AdvancedWorkflowDefinition, plan: WorkflowExecutionPlan):
        """Execute workflow steps"""
        try:
            for step_id in plan.planned_steps:
                # Check if workflow is paused
                state = self.state_manager.load_state(workflow.workflow_id)
                if state and state.get("state") == WorkflowState.PAUSED:
                    break

                step = next(s for s in workflow.steps if s.step_id == step_id)
                workflow.current_step = step_id

                # Save state before step execution
                self.state_manager.save_state(workflow.workflow_id, workflow.dict())

                # Execute step
                result = await self._execute_step(workflow, step)

                # Store step result
                workflow.step_results[step_id] = result

                # Update state
                workflow.updated_at = datetime.now()
                self.state_manager.save_state(workflow.workflow_id, workflow.dict())

            # Mark as completed
            workflow.state = WorkflowState.COMPLETED
            workflow.current_step = None
            self.state_manager.save_state(workflow.workflow_id, workflow.dict())

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            workflow.state = WorkflowState.FAILED
            workflow.current_step = None
            self.state_manager.save_state(workflow.workflow_id, workflow.dict())

        finally:
            # Clean up running task
            if workflow.workflow_id in self.running_workflows:
                del self.running_workflows[workflow.workflow_id]

    async def _execute_step(self, workflow: AdvancedWorkflowDefinition, step: WorkflowStep) -> Dict[str, Any]:
        """Execute a single workflow step"""
        start_time = datetime.now()

        try:
            # Prepare step inputs
            step_inputs = {}

            # Global inputs
            step_inputs.update(workflow.user_inputs)

            # Results from previous steps
            for dep_id in step.depends_on:
                if dep_id in workflow.step_results:
                    step_inputs[f"step_{dep_id}_result"] = workflow.step_results[dep_id]

            # Execute step based on type
            if step.step_type == "api_call":
                result = await self._execute_api_call(step, step_inputs)
            elif step.step_type == "data_transform":
                result = await self._execute_data_transform(step, step_inputs)
            elif step.step_type == "user_input":
                result = await self._execute_user_input(step, step_inputs)
            elif step.step_type == "condition":
                result = await self._execute_condition(step, step_inputs)
            else:
                result = await self._execute_custom_step(step, step_inputs)

            return {
                "status": "success",
                "result": result,
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat()
            }

    async def _execute_api_call(self, step: WorkflowStep, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute API call step"""
        # Implementation would depend on specific API requirements
        return {"message": "API call executed", "inputs": inputs}

    async def _execute_data_transform(self, step: WorkflowStep, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute data transformation step"""
        # Implementation would depend on transformation requirements
        return {"message": "Data transformed", "inputs": inputs}

    async def _execute_user_input(self, step: WorkflowStep, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute user input step - pause workflow"""
        # This would trigger a pause and wait for user input
        return {"message": "User input required", "inputs": inputs}

    async def _execute_condition(self, step: WorkflowStep, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute condition step"""
        # Evaluate condition based on inputs
        return {"message": "Condition evaluated", "inputs": inputs}

    async def _execute_custom_step(self, step: WorkflowStep, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute custom step type"""
        # Default implementation
        return {"message": "Custom step executed", "step_type": step.step_type, "inputs": inputs}

    def pause_workflow(self, workflow_id: str) -> bool:
        """Pause workflow execution"""
        state = self.state_manager.load_state(workflow_id)
        if not state:
            return False

        if state.get("state") == WorkflowState.RUNNING:
            state["state"] = WorkflowState.PAUSED
            self.state_manager.save_state(workflow_id, state)

            # Cancel running task if exists
            if workflow_id in self.running_workflows:
                self.running_workflows[workflow_id].cancel()
                del self.running_workflows[workflow_id]

            return True

        return False

    def resume_workflow(self, workflow_id: str, additional_inputs: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Resume paused workflow"""
        state = self.state_manager.load_state(workflow_id)
        if not state or state.get("state") != WorkflowState.PAUSED:
            raise ValueError("Workflow is not paused")

        # Merge additional inputs
        if additional_inputs:
            state["user_inputs"].update(additional_inputs)

        # Update state and resume
        state["state"] = WorkflowState.RUNNING
        self.state_manager.save_state(workflow_id, state)

        # Resume execution
        workflow = AdvancedWorkflowDefinition(**state)
        plan = self._create_execution_plan(workflow)

        task = asyncio.create_task(self._execute_workflow(workflow, plan))
        self.running_workflows[workflow_id] = task

        return {"status": "resumed", "execution_id": plan.execution_id}

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel workflow execution"""
        state = self.state_manager.load_state(workflow_id)
        if not state:
            return False

        state["state"] = WorkflowState.CANCELLED
        self.state_manager.save_state(workflow_id, state)

        # Cancel running task if exists
        if workflow_id in self.running_workflows:
            self.running_workflows[workflow_id].cancel()
            del self.running_workflows[workflow_id]

        return True

    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get current workflow status"""
        state = self.state_manager.load_state(workflow_id)
        if not state:
            return None

        return {
            "workflow_id": workflow_id,
            "state": state.get("state"),
            "current_step": state.get("current_step"),
            "progress": self._calculate_progress(state),
            "step_results": state.get("step_results", {}),
            "user_inputs": state.get("user_inputs", {}),
            "updated_at": state.get("updated_at")
        }

    def _calculate_progress(self, state: Dict[str, Any]) -> float:
        """Calculate workflow progress percentage"""
        total_steps = len(state.get("steps", []))
        completed_steps = len(state.get("step_results", {}))

        if total_steps == 0:
            return 0.0

        return (completed_steps / total_steps) * 100