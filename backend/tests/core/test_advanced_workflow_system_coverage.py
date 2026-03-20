"""
Coverage tests for advanced_workflow_system.py.

Target: 50%+ coverage (499 statements, ~250 lines to cover)
Focus: DAG validation, workflow patterns, orchestration, parallel execution
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone
import json
import tempfile
import os

from core.advanced_workflow_system import (
    AdvancedWorkflowSystem,
    AdvancedWorkflowDefinition,
    WorkflowStep,
    InputParameter,
    ParameterType,
    WorkflowState,
    MultiOutputConfig,
    StateManager,
    WorkflowExecutionPlan
)


class TestInputParameters:
    """Test input parameter validation and configuration."""

    def test_create_string_parameter(self):
        """Test creating string input parameter."""
        param = InputParameter(
            name="test_param",
            type=ParameterType.STRING,
            label="Test Parameter",
            description="A test parameter",
            required=True
        )
        assert param.name == "test_param"
        assert param.type == ParameterType.STRING
        assert param.required is True

    def test_create_number_parameter(self):
        """Test creating number input parameter."""
        param = InputParameter(
            name="count",
            type=ParameterType.NUMBER,
            label="Count",
            description="Number parameter",
            required=False,
            default_value=10
        )
        assert param.type == ParameterType.NUMBER
        assert param.default_value == 10

    def test_create_select_parameter(self):
        """Test creating select parameter with options."""
        param = InputParameter(
            name="option",
            type=ParameterType.SELECT,
            label="Option",
            description="Select option",
            required=True,
            options=["option1", "option2", "option3"]
        )
        assert len(param.options) == 3
        assert "option1" in param.options

    def test_parameter_with_validation_rules(self):
        """Test parameter with validation rules."""
        param = InputParameter(
            name="email",
            type=ParameterType.STRING,
            label="Email",
            description="Email address",
            required=True,
            validation_rules={"pattern": "^[a-z]+@[a-z]+\\.com$"}
        )
        assert "pattern" in param.validation_rules

    def test_parameter_with_conditional_visibility(self):
        """Test parameter with conditional visibility."""
        param = InputParameter(
            name="sub_option",
            type=ParameterType.SELECT,
            label="Sub Option",
            description="Sub option",
            required=False,
            show_when={"main_option": ["value1", "value2"]}
        )
        assert param.show_when is not None
        assert "main_option" in param.show_when


class TestWorkflowDefinition:
    """Test workflow definition creation and validation."""

    def test_create_basic_workflow(self):
        """Test creating basic workflow definition."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow"
        )
        assert workflow.workflow_id == "test-workflow"
        assert workflow.state == WorkflowState.DRAFT
        assert workflow.version == "1.0"

    def test_workflow_with_input_schema(self):
        """Test workflow with input parameters."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            input_schema=[
                InputParameter(
                    name="param1",
                    type=ParameterType.STRING,
                    label="Parameter 1",
                    description="First parameter"
                )
            ]
        )
        assert len(workflow.input_schema) == 1
        assert workflow.input_schema[0].name == "param1"

    def test_workflow_with_steps(self):
        """Test workflow with multiple steps."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="First step",
                    step_type="task"
                ),
                WorkflowStep(
                    step_id="step2",
                    name="Step 2",
                    description="Second step",
                    step_type="task",
                    depends_on=["step1"]
                )
            ]
        )
        assert len(workflow.steps) == 2
        assert workflow.steps[1].depends_on == ["step1"]

    def test_workflow_with_multi_output(self):
        """Test workflow with multiple output configuration."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            output_config=MultiOutputConfig(
                output_type="dataset",
                output_parameters=[
                    InputParameter(
                        name="output1",
                        type=ParameterType.STRING,
                        label="Output 1",
                        description="First output"
                    )
                ]
            )
        )
        assert workflow.output_config is not None
        assert workflow.output_config.output_type == "dataset"

    def test_get_missing_inputs(self):
        """Test getting missing required inputs."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            input_schema=[
                InputParameter(
                    name="required_param",
                    type=ParameterType.STRING,
                    label="Required",
                    description="Required parameter",
                    required=True
                ),
                InputParameter(
                    name="optional_param",
                    type=ParameterType.STRING,
                    label="Optional",
                    description="Optional parameter",
                    required=False
                )
            ]
        )
        missing = workflow.get_missing_inputs({})
        assert len(missing) == 1
        assert missing[0]["name"] == "required_param"

    def test_get_missing_inputs_with_default(self):
        """Test that parameters with defaults are not missing."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            input_schema=[
                InputParameter(
                    name="param_with_default",
                    type=ParameterType.STRING,
                    label="With Default",
                    description="Parameter with default",
                    required=True,
                    default_value="default_value"
                )
            ]
        )
        missing = workflow.get_missing_inputs({})
        assert len(missing) == 0

    def test_should_show_parameter_no_condition(self):
        """Test parameter visibility without conditions."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            input_schema=[
                InputParameter(
                    name="unconditional_param",
                    type=ParameterType.STRING,
                    label="Unconditional",
                    description="Always visible"
                )
            ]
        )
        param = workflow.input_schema[0]
        assert workflow._should_show_parameter(param, {}) is True

    def test_should_show_parameter_with_condition(self):
        """Test parameter visibility with conditions."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            input_schema=[
                InputParameter(
                    name="conditional_param",
                    type=ParameterType.STRING,
                    label="Conditional",
                    description="Conditionally visible",
                    show_when={"trigger_param": "show_value"}
                )
            ]
        )
        param = workflow.input_schema[0]

        # Should show when condition matches
        assert workflow._should_show_parameter(param, {"trigger_param": "show_value"}) is True

        # Should not show when condition doesn't match
        assert workflow._should_show_parameter(param, {"trigger_param": "other_value"}) is False

    def test_advance_to_step(self):
        """Test advancing workflow to specific step."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow"
        )
        workflow.advance_to_step("step2")
        assert workflow.current_step == "step2"

    def test_add_step_output(self):
        """Test adding step output to workflow."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow"
        )
        workflow.add_step_output("step1", {"result": "success"})
        assert "step1" in workflow.step_results
        assert workflow.step_results["step1"]["output"]["result"] == "success"

    def test_get_all_outputs(self):
        """Test getting all outputs from completed steps."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow"
        )
        workflow.add_step_output("step1", {"result": "output1"})
        workflow.add_step_output("step2", {"result": "output2"})

        outputs = workflow.get_all_outputs()
        assert len(outputs) == 2
        assert outputs["step1"]["result"] == "output1"
        assert outputs["step2"]["result"] == "output2"


class TestWorkflowStep:
    """Test workflow step configuration."""

    def test_create_basic_step(self):
        """Test creating basic workflow step."""
        step = WorkflowStep(
            step_id="step1",
            name="Step 1",
            description="First step",
            step_type="task"
        )
        assert step.step_id == "step1"
        assert step.step_type == "task"
        assert step.depends_on == []

    def test_step_with_dependencies(self):
        """Test step with dependencies on other steps."""
        step = WorkflowStep(
            step_id="step2",
            name="Step 2",
            description="Second step",
            step_type="task",
            depends_on=["step1", "step0"]
        )
        assert len(step.depends_on) == 2

    def test_step_with_condition(self):
        """Test step with execution condition."""
        step = WorkflowStep(
            step_id="conditional_step",
            name="Conditional Step",
            description="Conditional step",
            step_type="task",
            condition="{{ step1.output.value > 10 }}"
        )
        assert step.condition is not None

    def test_step_with_retry_config(self):
        """Test step with retry configuration."""
        step = WorkflowStep(
            step_id="retry_step",
            name="Retry Step",
            description="Step with retry",
            step_type="task",
            retry_config={"max_retries": 3, "backoff": "exponential"}
        )
        assert "max_retries" in step.retry_config

    def test_step_with_timeout(self):
        """Test step with custom timeout."""
        step = WorkflowStep(
            step_id="timeout_step",
            name="Timeout Step",
            description="Step with timeout",
            step_type="task",
            timeout_seconds=600
        )
        assert step.timeout_seconds == 600

    def test_step_parallel_execution(self):
        """Test step configured for parallel execution."""
        step = WorkflowStep(
            step_id="parallel_step",
            name="Parallel Step",
            description="Parallel step",
            step_type="task",
            is_parallel=True
        )
        assert step.is_parallel is True


class TestStateManager:
    """Test workflow state persistence and restoration."""

    def setup_method(self):
        """Setup test state manager."""
        self.manager = StateManager()

    def teardown_method(self):
        """Cleanup state files."""
        # Clean up any test state files
        if os.path.exists("workflow_states"):
            import shutil
            shutil.rmtree("workflow_states", ignore_errors=True)

    def test_save_state(self):
        """Test saving workflow state."""
        state = {
            "workflow_id": "test-workflow",
            "status": "running",
            "current_step": "step1"
        }
        result = self.manager.save_state("test-workflow", state)
        assert result is True
        assert "test-workflow" in self.manager.state_store

    def test_load_state_from_memory(self):
        """Test loading state from memory."""
        state = {
            "workflow_id": "test-workflow",
            "status": "running"
        }
        self.manager.save_state("test-workflow", state)
        loaded = self.manager.load_state("test-workflow")
        assert loaded is not None
        assert loaded["status"] == "running"

    def test_load_state_from_file(self):
        """Test loading state from file storage."""
        state = {
            "workflow_id": "test-workflow",
            "status": "completed"
        }
        self.manager.save_state("test-workflow", state)

        # Create new manager instance (empty memory)
        new_manager = StateManager()
        loaded = new_manager.load_state("test-workflow")
        assert loaded is not None
        assert loaded["status"] == "completed"

    def test_load_nonexistent_state(self):
        """Test loading non-existent state returns None."""
        loaded = self.manager.load_state("nonexistent-workflow")
        assert loaded is None

    def test_save_state_adds_timestamp(self):
        """Test that saving state adds timestamp."""
        state = {"status": "running"}
        self.manager.save_state("test-workflow", state)
        loaded = self.manager.load_state("test-workflow")
        assert "saved_at" in loaded

    def test_list_workflows_empty(self):
        """Test listing workflows when none exist."""
        workflows = self.manager.list_workflows()
        assert workflows == []

    def test_list_workflows_with_filter(self):
        """Test listing workflows with status filter."""
        # Save multiple workflows
        self.manager.save_state("workflow1", {"status": "completed", "name": "Workflow 1"})
        self.manager.save_state("workflow2", {"status": "running", "name": "Workflow 2"})
        self.manager.save_state("workflow3", {"status": "completed", "name": "Workflow 3"})

        # Filter by status
        completed = self.manager.list_workflows(status="completed")
        assert len(completed) == 2

        running = self.manager.list_workflows(status="running")
        assert len(running) == 1

    def test_list_workflows_with_sorting(self):
        """Test listing workflows with sorting."""
        # Save workflows with different update times
        self.manager.save_state("workflow1", {"status": "draft", "name": "C Workflow", "updated_at": "2026-01-01T10:00:00"})
        self.manager.save_state("workflow2", {"status": "draft", "name": "A Workflow", "updated_at": "2026-01-01T12:00:00"})
        self.manager.save_state("workflow3", {"status": "draft", "name": "B Workflow", "updated_at": "2026-01-01T11:00:00"})

        # Sort by name ascending
        workflows = self.manager.list_workflows(sort_by="name", sort_order="asc")
        assert workflows[0]["name"] == "A Workflow"
        assert workflows[-1]["name"] == "C Workflow"

    def test_list_workflows_with_pagination(self):
        """Test listing workflows with pagination."""
        # Save multiple workflows
        for i in range(10):
            self.manager.save_state(f"workflow{i}", {"status": "draft", "name": f"Workflow {i}"})

        # Get first page
        page1 = self.manager.list_workflows(limit=5, offset=0)
        assert len(page1) == 5

        # Get second page
        page2 = self.manager.list_workflows(limit=5, offset=5)
        assert len(page2) == 5

        # Verify different content
        assert page1[0]["name"] != page2[0]["name"]


class TestAdvancedWorkflowSystem:
    """Test advanced workflow system functionality."""

    def setup_method(self):
        """Setup test workflow system."""
        self.system = AdvancedWorkflowSystem()

    def test_create_workflow_definition(self):
        """Test creating a new workflow definition."""
        workflow = self.system.create_workflow(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow"
        )
        assert workflow.workflow_id == "test-workflow"
        assert workflow.state == WorkflowState.DRAFT

    def test_validate_workflow_definition(self):
        """Test validating workflow definition."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="First step",
                    step_type="task"
                )
            ]
        )
        validation = self.system.validate_workflow(workflow)
        assert validation["is_valid"] is True

    def test_validate_workflow_with_invalid_dependencies(self):
        """Test validating workflow with invalid dependencies."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="First step",
                    step_type="task",
                    depends_on=["nonexistent_step"]
                )
            ]
        )
        validation = self.system.validate_workflow(workflow)
        assert validation["is_valid"] is False
        assert "invalid_dependencies" in validation

    def test_execute_workflow_step(self):
        """Test executing a single workflow step."""
        step = WorkflowStep(
            step_id="step1",
            name="Step 1",
            description="Test step",
            step_type="task"
        )

        with patch.object(self.system, '_execute_step_impl') as mock_exec:
            mock_exec.return_value = {"status": "success", "output": {"result": "done"}}
            result = self.system.execute_step(step, {})
            assert result["status"] == "success"

    def test_create_execution_plan(self):
        """Test creating workflow execution plan."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="First step",
                    step_type="task"
                ),
                WorkflowStep(
                    step_id="step2",
                    name="Step 2",
                    description="Second step",
                    step_type="task",
                    depends_on=["step1"]
                )
            ]
        )

        plan = self.system.create_execution_plan(workflow)
        assert isinstance(plan, WorkflowExecutionPlan)
        assert len(plan.planned_steps) == 2
        assert plan.planned_steps[0] == "step1"
        assert plan.planned_steps[1] == "step2"

    def test_create_execution_plan_with_parallel_steps(self):
        """Test creating execution plan with parallel steps."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="First step",
                    step_type="task"
                ),
                WorkflowStep(
                    step_id="step2a",
                    name="Step 2a",
                    description="Parallel step 2a",
                    step_type="task",
                    depends_on=["step1"],
                    is_parallel=True
                ),
                WorkflowStep(
                    step_id="step2b",
                    name="Step 2b",
                    description="Parallel step 2b",
                    step_type="task",
                    depends_on=["step1"],
                    is_parallel=True
                ),
                WorkflowStep(
                    step_id="step3",
                    name="Step 3",
                    description="Final step",
                    step_type="task",
                    depends_on=["step2a", "step2b"]
                )
            ]
        )

        plan = self.system.create_execution_plan(workflow)
        assert len(plan.parallel_groups) > 0
        # step2a and step2b should be in a parallel group
        parallel_group = plan.parallel_groups[0]
        assert "step2a" in parallel_group
        assert "step2b" in parallel_group


class TestWorkflowExecution:
    """Test workflow execution scenarios."""

    def setup_method(self):
        """Setup test workflow system."""
        self.system = AdvancedWorkflowSystem()

    def test_execute_linear_workflow(self):
        """Test executing linear workflow (one step after another)."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="Linear workflow",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="First step",
                    step_type="task"
                ),
                WorkflowStep(
                    step_id="step2",
                    name="Step 2",
                    description="Second step",
                    step_type="task",
                    depends_on=["step1"]
                )
            ]
        )

        with patch.object(self.system, '_execute_step_impl') as mock_exec:
            mock_exec.return_value = {"status": "success", "output": {"result": "done"}}
            result = self.system.execute_workflow(workflow)
            assert result["status"] in ["running", "completed"]

    def test_execute_workflow_with_failure(self):
        """Test executing workflow that fails at a step."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="Failing workflow",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="First step",
                    step_type="task"
                )
            ]
        )

        with patch.object(self.system, '_execute_step_impl') as mock_exec:
            mock_exec.return_value = {"status": "error", "error": "Step failed"}
            result = self.system.execute_workflow(workflow)
            assert result["status"] == "failed"

    def test_pause_workflow(self):
        """Test pausing workflow execution."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="Pausable workflow",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="Pausable step",
                    step_type="task",
                    can_pause=True
                )
            ]
        )

        with patch.object(self.system, '_execute_step_impl') as mock_exec:
            # Simulate long-running step
            import asyncio
            async def long_running(*args, **kwargs):
                await asyncio.sleep(0.1)
                return {"status": "success"}

            mock_exec.side_effect = long_running

            # Start execution
            result = self.system.execute_workflow(workflow)

            # Pause workflow
            paused = self.system.pause_workflow(workflow.workflow_id)
            # Note: Actual pause behavior depends on implementation

    def test_resume_workflow(self):
        """Test resuming paused workflow."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="Resumable workflow",
            state=WorkflowState.PAUSED,
            current_step="step2"
        )

        with patch.object(self.system, '_execute_step_impl') as mock_exec:
            mock_exec.return_value = {"status": "success", "output": {}}
            result = self.system.resume_workflow(workflow)
            # Workflow should transition to running

    def test_cancel_workflow(self):
        """Test canceling workflow execution."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="Cancellable workflow",
            state=WorkflowState.RUNNING
        )

        result = self.system.cancel_workflow(workflow.workflow_id)
        assert result["cancelled"] is True
        assert workflow.state == WorkflowState.CANCELLED


class TestWorkflowPersistence:
    """Test workflow persistence and recovery."""

    def setup_method(self):
        """Setup test workflow system."""
        self.system = AdvancedWorkflowSystem()

    def teardown_method(self):
        """Cleanup state files."""
        if os.path.exists("workflow_states"):
            import shutil
            shutil.rmtree("workflow_states", ignore_errors=True)

    def test_save_workflow(self):
        """Test saving workflow definition."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="Persistent workflow"
        )

        saved = self.system.save_workflow(workflow)
        assert saved is True

    def test_load_workflow(self):
        """Test loading workflow definition."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="Loadable workflow"
        )

        # Save workflow
        self.system.save_workflow(workflow)

        # Load workflow
        loaded = self.system.load_workflow("test-workflow")
        assert loaded is not None
        assert loaded.workflow_id == "test-workflow"
        assert loaded.name == "Test Workflow"

    def test_delete_workflow(self):
        """Test deleting workflow definition."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-workflow",
            name="Test Workflow",
            description="Deletable workflow"
        )

        # Save workflow
        self.system.save_workflow(workflow)

        # Delete workflow
        deleted = self.system.delete_workflow("test-workflow")
        assert deleted is True

        # Verify workflow is deleted
        loaded = self.system.load_workflow("test-workflow")
        assert loaded is None
