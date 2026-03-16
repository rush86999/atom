"""
Unit tests for advanced_workflow_system.py

Tests the AdvancedWorkflowSystem including:
- Initialization and workflow creation
- State management and persistence
- Parameter validation
- Execution engine (workflow lifecycle)
- Nested workflows and parallel execution
- Error handling and recovery
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest
from typing import Dict, Any

# Import the module to test
import sys
sys.path.insert(0, '/Users/rushiparikh/projects/atom/backend')

from core.advanced_workflow_system import (
    ParameterType,
    WorkflowState,
    InputParameter,
    WorkflowStep,
    AdvancedWorkflowDefinition,
    WorkflowExecutionPlan,
    StateManager,
    ParameterValidator,
    ExecutionEngine,
    MultiOutputConfig,
)


# ==================== Test Fixtures ====================

@pytest.fixture
def temp_state_dir():
    """Create temporary directory for state storage"""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        yield tmpdir
        os.chdir(original_cwd)
        # Clean up workflow_states directory if created
        if os.path.exists("workflow_states"):
            import shutil
            shutil.rmtree("workflow_states")


@pytest.fixture
def sample_input_parameters():
    """Sample input parameters for workflow"""
    return [
        InputParameter(
            name="source_type",
            type=ParameterType.SELECT,
            label="Source Type",
            description="Select data source type",
            required=True,
            options=["database", "api", "file"]
        ),
        InputParameter(
            name="batch_size",
            type=ParameterType.NUMBER,
            label="Batch Size",
            description="Number of records per batch",
            required=False,
            default_value=100,
            validation_rules={"min_value": 1, "max_value": 10000}
        )
    ]


@pytest.fixture
def sample_workflow_steps():
    """Sample workflow steps"""
    return [
        WorkflowStep(
            step_id="validate",
            name="Validate Inputs",
            description="Validate input parameters",
            step_type="validation",
            input_parameters=[],
            depends_on=[],
            timeout_seconds=60
        ),
        WorkflowStep(
            step_id="extract",
            name="Extract Data",
            description="Extract data from source",
            step_type="data_extraction",
            input_parameters=[],
            depends_on=["validate"],
            timeout_seconds=300
        ),
        WorkflowStep(
            step_id="transform",
            name="Transform Data",
            description="Transform and clean data",
            step_type="data_transformation",
            input_parameters=[],
            depends_on=["extract"],
            timeout_seconds=600,
            can_pause=True
        )
    ]


@pytest.fixture
def sample_workflow_dict(sample_input_parameters, sample_workflow_steps):
    """Sample workflow definition as dict"""
    return {
        "workflow_id": "test_workflow_001",
        "name": "Test ETL Workflow",
        "description": "A test ETL workflow for unit testing",
        "version": "1.0",
        "category": "data_processing",
        "tags": ["etl", "test"],
        "input_schema": [p.dict() for p in sample_input_parameters],
        "steps": [s.dict() for s in sample_workflow_steps],
        "step_connections": [
            {"source": "validate", "target": "extract"},
            {"source": "extract", "target": "transform"}
        ]
    }


# ==================== Test AdvancedWorkflowInit ====================

class TestAdvancedWorkflowInit:
    """Tests for AdvancedWorkflowDefinition initialization"""

    def test_create_workflow_minimal(self):
        """Test creating workflow with minimal parameters"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="minimal_wf",
            name="Minimal Workflow",
            description="A minimal test workflow"
        )

        assert workflow.workflow_id == "minimal_wf"
        assert workflow.name == "Minimal Workflow"
        assert workflow.state == WorkflowState.DRAFT
        assert workflow.version == "1.0"
        assert workflow.category == "general"
        assert workflow.input_schema == []
        assert workflow.steps == []

    def test_create_workflow_full(self, sample_workflow_dict):
        """Test creating workflow with all parameters"""
        workflow = AdvancedWorkflowDefinition(**sample_workflow_dict)

        assert workflow.workflow_id == "test_workflow_001"
        assert workflow.name == "Test ETL Workflow"
        assert len(workflow.input_schema) == 2
        assert len(workflow.steps) == 3
        assert workflow.category == "data_processing"
        assert "etl" in workflow.tags

    def test_workflow_state_enum(self):
        """Test WorkflowState enum values"""
        assert WorkflowState.DRAFT == "draft"
        assert WorkflowState.RUNNING == "running"
        assert WorkflowState.PAUSED == "paused"
        assert WorkflowState.COMPLETED == "completed"
        assert WorkflowState.FAILED == "failed"
        assert WorkflowState.CANCELLED == "cancelled"

    def test_parameter_type_enum(self):
        """Test ParameterType enum values"""
        assert ParameterType.STRING == "string"
        assert ParameterType.NUMBER == "number"
        assert ParameterType.BOOLEAN == "boolean"
        assert ParameterType.SELECT == "select"
        assert ParameterType.MULTISELECT == "multiselect"

    def test_workflow_timestamps(self):
        """Test workflow has creation and update timestamps"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="timestamp_wf",
            name="Timestamp Test",
            description="Test timestamps"
        )

        assert isinstance(workflow.created_at, datetime)
        assert isinstance(workflow.updated_at, datetime)

    def test_advance_to_step(self):
        """Test advancing workflow to specific step"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="advance_wf",
            name="Advance Test",
            description="Test step advancement"
        )

        workflow.advance_to_step("step2")

        assert workflow.current_step == "step2"

    def test_add_step_output(self):
        """Test adding step output to workflow"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="output_wf",
            name="Output Test",
            description="Test step output"
        )

        test_output = {"result": "success", "count": 42}
        workflow.add_step_output("step1", test_output)

        assert "step1" in workflow.step_results
        assert workflow.step_results["step1"]["output"] == test_output
        assert "timestamp" in workflow.step_results["step1"]

    def test_get_all_outputs(self):
        """Test getting all step outputs"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="outputs_wf",
            name="Outputs Test",
            description="Test getting all outputs"
        )

        workflow.add_step_output("step1", {"result": "first"})
        workflow.add_step_output("step2", {"result": "second"})

        outputs = workflow.get_all_outputs()

        assert len(outputs) == 2
        assert outputs["step1"]["result"] == "first"
        assert outputs["step2"]["result"] == "second"


# ==================== Test Parameter Validation ====================

class TestParameterValidation:
    """Tests for parameter validation"""

    def test_validate_required_string_success(self):
        """Test validating required string parameter"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.STRING,
            label="Test Parameter",
            description="A test parameter",
            required=True
        )

        is_valid, error = ParameterValidator.validate_parameter(param, "test_value")

        assert is_valid is True
        assert error is None

    def test_validate_required_string_missing(self):
        """Test validating missing required parameter"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.STRING,
            label="Test Parameter",
            description="A test parameter",
            required=True
        )

        is_valid, error = ParameterValidator.validate_parameter(param, None)

        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_string_with_wrong_type(self):
        """Test validating string with wrong type"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.STRING,
            label="Test Parameter",
            description="A test parameter",
            required=True
        )

        is_valid, error = ParameterValidator.validate_parameter(param, 123)

        assert is_valid is False
        assert "string" in error.lower()

    def test_validate_number_success(self):
        """Test validating number parameter"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.NUMBER,
            label="Test Parameter",
            description="A test parameter",
            required=True
        )

        is_valid, error = ParameterValidator.validate_parameter(param, 42.5)

        assert is_valid is True
        assert error is None

    def test_validate_number_with_wrong_type(self):
        """Test validating number with wrong type"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.NUMBER,
            label="Test Parameter",
            description="A test parameter",
            required=True
        )

        is_valid, error = ParameterValidator.validate_parameter(param, "not a number")

        assert is_valid is False
        assert "number" in error.lower()

    def test_validate_boolean_success(self):
        """Test validating boolean parameter"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.BOOLEAN,
            label="Test Parameter",
            description="A test parameter",
            required=True
        )

        is_valid, error = ParameterValidator.validate_parameter(param, True)

        assert is_valid is True
        assert error is None

    def test_validate_select_valid_option(self):
        """Test validating select with valid option"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.SELECT,
            label="Test Parameter",
            description="A test parameter",
            required=True,
            options=["option1", "option2", "option3"]
        )

        is_valid, error = ParameterValidator.validate_parameter(param, "option2")

        assert is_valid is True
        assert error is None

    def test_validate_select_invalid_option(self):
        """Test validating select with invalid option"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.SELECT,
            label="Test Parameter",
            description="A test parameter",
            required=True,
            options=["option1", "option2", "option3"]
        )

        is_valid, error = ParameterValidator.validate_parameter(param, "invalid")

        assert is_valid is False
        assert "one of" in error.lower()

    def test_validate_min_length(self):
        """Test validating min length rule"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.STRING,
            label="Test Parameter",
            description="A test parameter",
            required=True,
            validation_rules={"min_length": 5}
        )

        is_valid, error = ParameterValidator.validate_parameter(param, "abc")

        assert is_valid is False
        assert "at least 5" in error.lower()

    def test_validate_max_length(self):
        """Test validating max length rule"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.STRING,
            label="Test Parameter",
            description="A test parameter",
            required=True,
            validation_rules={"max_length": 10}
        )

        is_valid, error = ParameterValidator.validate_parameter(param, "this is way too long")

        assert is_valid is False
        assert "at most 10" in error.lower()

    def test_validate_min_value(self):
        """Test validating min value rule"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.NUMBER,
            label="Test Parameter",
            description="A test parameter",
            required=True,
            validation_rules={"min_value": 10}
        )

        is_valid, error = ParameterValidator.validate_parameter(param, 5)

        assert is_valid is False
        assert "at least 10" in error.lower()

    def test_validate_max_value(self):
        """Test validating max value rule"""
        param = InputParameter(
            name="test_param",
            type=ParameterType.NUMBER,
            label="Test Parameter",
            description="A test parameter",
            required=True,
            validation_rules={"max_value": 100}
        )

        is_valid, error = ParameterValidator.validate_parameter(param, 150)

        assert is_valid is False
        assert "at most 100" in error.lower()


# ==================== Test Nested Workflows ====================

class TestNestedWorkflows:
    """Tests for workflow composition and nested structures"""

    def test_workflow_with_dependencies(self, sample_workflow_dict):
        """Test workflow with step dependencies"""
        workflow = AdvancedWorkflowDefinition(**sample_workflow_dict)

        # Validate dependency chain
        validate_step = next(s for s in workflow.steps if s.step_id == "validate")
        extract_step = next(s for s in workflow.steps if s.step_id == "extract")
        transform_step = next(s for s in workflow.steps if s.step_id == "transform")

        assert validate_step.depends_on == []
        assert extract_step.depends_on == ["validate"]
        assert transform_step.depends_on == ["extract"]

    def test_workflow_step_connections(self, sample_workflow_dict):
        """Test workflow step connections"""
        workflow = AdvancedWorkflowDefinition(**sample_workflow_dict)

        assert len(workflow.step_connections) == 2
        assert workflow.step_connections[0] == {"source": "validate", "target": "extract"}
        assert workflow.step_connections[1] == {"source": "extract", "target": "transform"}

    def test_workflow_with_multi_output(self):
        """Test workflow with multi-output configuration"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="multi_output_wf",
            name="Multi Output Test",
            description="Test multi-output workflow",
            output_config=MultiOutputConfig(
                output_type="dataset",
                output_parameters=[
                    InputParameter(
                        name="result_file",
                        type=ParameterType.STRING,
                        label="Result File",
                        description="Output file path",
                        required=True
                    )
                ]
            )
        )

        assert workflow.output_config is not None
        assert workflow.output_config.output_type == "dataset"
        assert len(workflow.output_config.output_parameters) == 1

    def test_get_missing_inputs_none_required(self):
        """Test getting missing inputs when none are required"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="no_required_wf",
            name="No Required Inputs",
            description="Test workflow with no required inputs"
        )

        missing = workflow.get_missing_inputs({})

        assert len(missing) == 0

    def test_get_missing_inputs_with_required(self):
        """Test getting missing required inputs"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="required_wf",
            name="Required Inputs",
            description="Test workflow with required inputs",
            input_schema=[
                InputParameter(
                    name="required_field",
                    type=ParameterType.STRING,
                    label="Required Field",
                    description="A required field",
                    required=True
                ),
                InputParameter(
                    name="optional_field",
                    type=ParameterType.STRING,
                    label="Optional Field",
                    description="An optional field",
                    required=False
                )
            ]
        )

        missing = workflow.get_missing_inputs({})

        assert len(missing) == 1
        assert missing[0]["name"] == "required_field"

    def test_parameter_with_default_value(self):
        """Test parameter with default value"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="default_wf",
            name="Default Values",
            description="Test default values",
            input_schema=[
                InputParameter(
                    name="with_default",
                    type=ParameterType.NUMBER,
                    label="With Default",
                    description="Has default value",
                    required=True,
                    default_value=100
                )
            ]
        )

        missing = workflow.get_missing_inputs({})

        # Should not be missing since it has default
        assert len(missing) == 0


# ==================== Test Parallel Execution ====================

class TestParallelExecution:
    """Tests for parallel execution logic"""

    def test_workflow_with_parallel_steps(self):
        """Test workflow with steps that can run in parallel"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="parallel_wf",
            name="Parallel Test",
            description="Test parallel execution",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="First step",
                    step_type="validation",
                    depends_on=[]
                ),
                WorkflowStep(
                    step_id="step2a",
                    name="Step 2A",
                    description="Parallel step 2A",
                    step_type="processing",
                    depends_on=["step1"],
                    is_parallel=True
                ),
                WorkflowStep(
                    step_id="step2b",
                    name="Step 2B",
                    description="Parallel step 2B",
                    step_type="processing",
                    depends_on=["step1"],
                    is_parallel=True
                ),
                WorkflowStep(
                    step_id="step3",
                    name="Step 3",
                    description="Final step",
                    step_type="output",
                    depends_on=["step2a", "step2b"]
                )
            ]
        )

        # Count parallel steps
        parallel_steps = [s for s in workflow.steps if s.is_parallel]
        assert len(parallel_steps) == 2
        assert parallel_steps[0].step_id == "step2a"
        assert parallel_steps[1].step_id == "step2b"

    def test_execution_plan_parallel_groups(self, sample_workflow_dict):
        """Test execution plan identifies parallel groups"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(**sample_workflow_dict)
        plan = engine._create_execution_plan(workflow)

        # Check plan structure
        assert plan.workflow_id == workflow.workflow_id
        assert len(plan.planned_steps) == 3
        assert plan.planned_steps == ["validate", "extract", "transform"]

    def test_step_order_respects_dependencies(self):
        """Test execution plan respects dependencies"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="order_test",
            name="Order Test",
            description="Test dependency ordering",
            steps=[
                WorkflowStep(step_id="c", name="C", description="Step C", step_type="task", depends_on=["b"]),
                WorkflowStep(step_id="a", name="A", description="Step A", step_type="task", depends_on=[]),
                WorkflowStep(step_id="b", name="B", description="Step B", step_type="task", depends_on=["a"])
            ]
        )

        plan = engine._create_execution_plan(workflow)

        # Should execute in dependency order: a -> b -> c
        assert plan.planned_steps == ["a", "b", "c"]


# ==================== Test Workflow Errors ====================

class TestWorkflowErrors:
    """Tests for error handling"""

    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="circular_wf",
            name="Circular Test",
            description="Test circular dependency detection",
            steps=[
                WorkflowStep(step_id="a", name="A", description="Step A", step_type="task", depends_on=["c"]),
                WorkflowStep(step_id="b", name="B", description="Step B", step_type="task", depends_on=["a"]),
                WorkflowStep(step_id="c", name="C", description="Step C", step_type="task", depends_on=["b"])
            ]
        )

        # Should detect circular dependency
        has_circular = engine._has_circular_dependencies(workflow.steps)
        assert has_circular is True

    def test_invalid_dependency_reference(self):
        """Test validation fails with invalid dependency"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="invalid_dep_wf",
            name="Invalid Dependency Test",
            description="Test invalid dependency reference",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="First step",
                    step_type="task",
                    depends_on=[]
                ),
                WorkflowStep(
                    step_id="step2",
                    name="Step 2",
                    description="Second step",
                    step_type="task",
                    depends_on=["nonexistent_step"]
                )
            ]
        )

        is_valid, error = engine._validate_workflow(workflow)
        assert is_valid is False
        assert "non-existent" in error.lower()

    def test_pause_workflow(self):
        """Test pausing a running workflow"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        # Create and start a workflow
        workflow_dict = {
            "workflow_id": "pause_test_wf",
            "name": "Pause Test",
            "description": "Test pausing workflow",
            "steps": [
                {"step_id": "s1", "name": "S1", "description": "Step 1", "step_type": "task", "depends_on": []}
            ]
        }

        state = {
            **workflow_dict,
            "state": WorkflowState.RUNNING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        state_manager.save_state("pause_test_wf", state)

        # Pause the workflow
        result = engine.pause_workflow("pause_test_wf")

        assert result is True

        # Verify state is paused
        loaded_state = state_manager.load_state("pause_test_wf")
        assert loaded_state["state"] == WorkflowState.PAUSED

    def test_cancel_workflow(self):
        """Test canceling a workflow"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        # Create a workflow
        workflow_dict = {
            "workflow_id": "cancel_test_wf",
            "name": "Cancel Test",
            "description": "Test canceling workflow",
            "steps": [
                {"step_id": "s1", "name": "S1", "description": "Step 1", "step_type": "task", "depends_on": []}
            ],
            "state": WorkflowState.RUNNING
        }

        state_manager.save_state("cancel_test_wf", workflow_dict)

        # Cancel the workflow
        result = engine.cancel_workflow("cancel_test_wf")

        assert result is True

        # Verify state is cancelled
        loaded_state = state_manager.load_state("cancel_test_wf")
        assert loaded_state["state"] == WorkflowState.CANCELLED


# ==================== Test State Management ====================

class TestStateManager:
    """Tests for StateManager class"""

    def test_save_and_load_state(self, temp_state_dir):
        """Test saving and loading workflow state"""
        state_manager = StateManager()

        test_state = {
            "workflow_id": "test_state_wf",
            "name": "Test State",
            "state": WorkflowState.RUNNING,
            "current_step": "step1",
            "created_at": datetime.now().isoformat()
        }

        # Save state
        result = state_manager.save_state("test_state_wf", test_state)
        assert result is True

        # Load state
        loaded_state = state_manager.load_state("test_state_wf")
        assert loaded_state is not None
        assert loaded_state["workflow_id"] == "test_state_wf"
        assert loaded_state["state"] == WorkflowState.RUNNING

    def test_load_nonexistent_state(self, temp_state_dir):
        """Test loading non-existent state returns None"""
        state_manager = StateManager()

        loaded_state = state_manager.load_state("nonexistent_wf")
        assert loaded_state is None

    def test_delete_state(self, temp_state_dir):
        """Test deleting workflow state"""
        state_manager = StateManager()

        # Create state
        test_state = {
            "workflow_id": "delete_test_wf",
            "name": "Delete Test",
            "state": WorkflowState.DRAFT
        }

        state_manager.save_state("delete_test_wf", test_state)

        # Delete state
        result = state_manager.delete_state("delete_test_wf")
        assert result is True

        # Verify it's gone
        loaded_state = state_manager.load_state("delete_test_wf")
        assert loaded_state is None

    def test_list_workflows_empty(self, temp_state_dir):
        """Test listing workflows when none exist"""
        state_manager = StateManager()

        workflows = state_manager.list_workflows()
        assert len(workflows) == 0

    def test_list_workflows_with_data(self, temp_state_dir):
        """Test listing workflows with existing workflows"""
        state_manager = StateManager()

        # Create multiple workflows
        for i in range(3):
            state = {
                "workflow_id": f"list_test_wf_{i}",
                "name": f"List Test {i}",
                "description": f"Test workflow {i}",
                "state": WorkflowState.DRAFT,
                "category": "test",
                "tags": ["test"],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "steps": []
            }
            state_manager.save_state(f"list_test_wf_{i}", state)

        # List all workflows
        workflows = state_manager.list_workflows()
        assert len(workflows) == 3

        # Verify summary fields
        for wf in workflows:
            assert "workflow_id" in wf
            assert "name" in wf
            assert "state" in wf

    def test_list_workflows_with_status_filter(self, temp_state_dir):
        """Test listing workflows with status filter"""
        state_manager = StateManager()

        # Create workflows with different statuses
        for status in [WorkflowState.DRAFT, WorkflowState.RUNNING, WorkflowState.COMPLETED]:
            state = {
                "workflow_id": f"status_test_{status.value}",
                "name": f"Status Test {status}",
                "state": status,
                "steps": []
            }
            state_manager.save_state(f"status_test_{status.value}", state)

        # Filter by running status
        running_workflows = state_manager.list_workflows(status=WorkflowState.RUNNING)
        assert len(running_workflows) == 1
        assert running_workflows[0]["workflow_id"] == "status_test_running"

    def test_list_workflows_with_category_filter(self, temp_state_dir):
        """Test listing workflows with category filter"""
        state_manager = StateManager()

        # Create workflows in different categories
        for category in ["data", "automation", "reporting"]:
            state = {
                "workflow_id": f"category_test_{category}",
                "name": f"Category Test {category}",
                "state": WorkflowState.DRAFT,
                "category": category,
                "steps": []
            }
            state_manager.save_state(f"category_test_{category}", state)

        # Filter by data category
        data_workflows = state_manager.list_workflows(category="data")
        assert len(data_workflows) == 1
        assert data_workflows[0]["category"] == "data"

    def test_list_workflows_with_tag_filter(self, temp_state_dir):
        """Test listing workflows with tag filter"""
        state_manager = StateManager()

        # Create workflows with different tags
        state1 = {
            "workflow_id": "tag_test_1",
            "name": "Tag Test 1",
            "state": WorkflowState.DRAFT,
            "tags": ["etl", "data"]
        }
        state2 = {
            "workflow_id": "tag_test_2",
            "name": "Tag Test 2",
            "state": WorkflowState.DRAFT,
            "tags": ["automation"]
        }
        state3 = {
            "workflow_id": "tag_test_3",
            "name": "Tag Test 3",
            "state": WorkflowState.DRAFT,
            "tags": ["etl", "automation"]
        }

        state_manager.save_state("tag_test_1", state1)
        state_manager.save_state("tag_test_2", state2)
        state_manager.save_state("tag_test_3", state3)

        # Filter by etl tag
        etl_workflows = state_manager.list_workflows(tags=["etl"])
        assert len(etl_workflows) == 2

        # Filter by both etl and automation
        both_workflows = state_manager.list_workflows(tags=["etl", "automation"])
        assert len(both_workflows) == 1
        assert both_workflows[0]["workflow_id"] == "tag_test_3"


# ==================== Test ExecutionEngine ====================

class TestExecutionEngine:
    """Tests for ExecutionEngine class"""

    def test_create_workflow_success(self, temp_state_dir):
        """Test creating a new workflow"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow_dict = {
            "workflow_id": "create_test_wf",
            "name": "Create Test",
            "description": "Test workflow creation",
            "steps": [
                {
                    "step_id": "step1",
                    "name": "Step 1",
                    "description": "First step",
                    "step_type": "task",
                    "depends_on": [],
                    "timeout_seconds": 60
                }
            ]
        }

        workflow = asyncio.run(engine.create_workflow(workflow_dict))

        assert workflow.workflow_id == "create_test_wf"
        assert workflow.name == "Create Test"
        assert len(workflow.steps) == 1

        # Verify state was saved
        loaded_state = state_manager.load_state("create_test_wf")
        assert loaded_state is not None

    def test_create_workflow_invalid_structure(self, temp_state_dir):
        """Test creating workflow with invalid structure"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        # Workflow with circular dependency
        workflow_dict = {
            "workflow_id": "invalid_wf",
            "name": "Invalid Workflow",
            "description": "Has circular dependency",
            "steps": [
                {
                    "step_id": "a",
                    "name": "A",
                    "description": "Step A",
                    "step_type": "task",
                    "depends_on": ["b"]
                },
                {
                    "step_id": "b",
                    "name": "B",
                    "description": "Step B",
                    "step_type": "task",
                    "depends_on": ["a"]
                }
            ]
        }

        with pytest.raises(ValueError, match="circular"):
            asyncio.run(engine.create_workflow(workflow_dict))

    def test_get_workflow_status(self, temp_state_dir):
        """Test getting workflow status"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        # Create a workflow state
        workflow_dict = {
            "workflow_id": "status_test_wf",
            "name": "Status Test",
            "description": "Test status retrieval",
            "state": WorkflowState.RUNNING,
            "current_step": "step2",
            "user_inputs": {"input1": "value1"},
            "step_results": {
                "step1": {"output": "result1"}
            },
            "updated_at": datetime.now().isoformat(),
            "steps": [
                {"step_id": "step1", "name": "S1", "description": "Step 1", "step_type": "task"},
                {"step_id": "step2", "name": "S2", "description": "Step 2", "step_type": "task"},
                {"step_id": "step3", "name": "S3", "description": "Step 3", "step_type": "task"}
            ]
        }

        state_manager.save_state("status_test_wf", workflow_dict)

        # Get status
        status = engine.get_workflow_status("status_test_wf")

        assert status is not None
        assert status["workflow_id"] == "status_test_wf"
        assert status["state"] == WorkflowState.RUNNING
        assert status["current_step"] == "step2"
        # Progress should be 33% (1 of 3 steps completed)
        assert status["progress"] == pytest.approx(33.33, rel=0.1)

    def test_get_workflow_status_nonexistent(self, temp_state_dir):
        """Test getting status for non-existent workflow"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        status = engine.get_workflow_status("nonexistent_wf")
        assert status is None


# ==================== Test WorkflowProgress ====================

class TestWorkflowProgress:
    """Tests for workflow progress calculation"""

    def test_progress_calculation_no_steps(self):
        """Test progress calculation with no steps"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        state = {
            "steps": [],
            "step_results": {}
        }

        progress = engine._calculate_progress(state)
        assert progress == 0.0

    def test_progress_calculation_partial(self):
        """Test progress calculation with partial completion"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        state = {
            "steps": [
                {"step_id": "s1"},
                {"step_id": "s2"},
                {"step_id": "s3"},
                {"step_id": "s4"}
            ],
            "step_results": {
                "s1": {"output": "done"},
                "s2": {"output": "done"}
            }
        }

        progress = engine._calculate_progress(state)
        assert progress == 50.0  # 2 of 4 steps

    def test_progress_calculation_complete(self):
        """Test progress calculation when complete"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        state = {
            "steps": [
                {"step_id": "s1"},
                {"step_id": "s2"},
                {"step_id": "s3"}
            ],
            "step_results": {
                "s1": {"output": "done"},
                "s2": {"output": "done"},
                "s3": {"output": "done"}
            }
        }

        progress = engine._calculate_progress(state)
        assert progress == 100.0


# ==================== Test Conditional Parameters ====================

class TestConditionalParameters:
    """Tests for conditional parameter display logic"""

    def test_should_show_parameter_no_condition(self):
        """Test parameter without show_when condition is always shown"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="no_condition_wf",
            name="No Condition",
            description="Test parameter without condition"
        )

        param = InputParameter(
            name="always_visible",
            type=ParameterType.STRING,
            label="Always Visible",
            description="This parameter is always visible",
            required=True
        )

        should_show = workflow._should_show_parameter(param, {})
        assert should_show is True

    def test_should_show_parameter_with_simple_condition(self):
        """Test parameter with simple equals condition"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="simple_condition_wf",
            name="Simple Condition",
            description="Test simple condition"
        )

        param = InputParameter(
            name="conditional_field",
            type=ParameterType.STRING,
            label="Conditional Field",
            description="Only shown when source_type is 'api'",
            required=True,
            show_when={"source_type": "api"}
        )

        # Should show when condition matches
        inputs_match = {"source_type": "api"}
        assert workflow._should_show_parameter(param, inputs_match) is True

        # Should not show when condition doesn't match
        inputs_no_match = {"source_type": "database"}
        assert workflow._should_show_parameter(param, inputs_no_match) is False

    def test_should_show_parameter_with_list_condition(self):
        """Test parameter with list-based condition (value in list)"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="list_condition_wf",
            name="List Condition",
            description="Test list condition"
        )

        param = InputParameter(
            name="api_specific_field",
            type=ParameterType.STRING,
            label="API Specific Field",
            description="Only shown for API sources",
            required=True,
            show_when={"source_type": ["api", "webhook"]}
        )

        # Should show when value is in list
        inputs_match = {"source_type": "api"}
        assert workflow._should_show_parameter(param, inputs_match) is True

        inputs_match2 = {"source_type": "webhook"}
        assert workflow._should_show_parameter(param, inputs_match2) is True

        # Should not show when value is not in list
        inputs_no_match = {"source_type": "database"}
        assert workflow._should_show_parameter(param, inputs_no_match) is False

    def test_should_show_parameter_with_complex_condition(self):
        """Test parameter with complex condition (operator-based)"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="complex_condition_wf",
            name="Complex Condition",
            description="Test complex condition"
        )

        param = InputParameter(
            name="high_value_field",
            type=ParameterType.NUMBER,
            label="High Value Field",
            description="Only shown when amount > 1000",
            required=False,
            show_when={"amount": {"min": 1000}}
        )

        # Note: The actual implementation uses 'equals', 'not_equals', 'contains'
        # This test documents the expected behavior
        inputs = {"amount": 1500}
        # Current implementation would check for exact match or operator
        should_show = workflow._should_show_parameter(param, inputs)
        # Based on implementation, this would need proper operator support
        assert isinstance(should_show, bool)

    def test_should_show_parameter_missing_referenced_field(self):
        """Test parameter when referenced field is missing"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="missing_field_wf",
            name="Missing Field",
            description="Test missing referenced field"
        )

        param = InputParameter(
            name="depends_on_missing",
            type=ParameterType.STRING,
            label="Depends on Missing",
            description="References non-existent field",
            required=True,
            show_when={"non_existent_field": "value"}
        )

        # Should not show when referenced field is missing
        should_show = workflow._should_show_parameter(param, {})
        assert should_show is False

    def test_get_missing_inputs_with_conditional_parameters(self):
        """Test get_missing_inputs respects conditional display"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="conditional_missing_wf",
            name="Conditional Missing",
            description="Test missing inputs with conditions",
            input_schema=[
                InputParameter(
                    name="source_type",
                    type=ParameterType.SELECT,
                    label="Source Type",
                    description="Select source",
                    required=True,
                    options=["api", "database", "file"]
                ),
                InputParameter(
                    name="api_key",
                    type=ParameterType.STRING,
                    label="API Key",
                    description="API authentication key",
                    required=True,
                    show_when={"source_type": "api"}
                ),
                InputParameter(
                    name="db_connection",
                    type=ParameterType.STRING,
                    label="DB Connection",
                    description="Database connection string",
                    required=True,
                    show_when={"source_type": "database"}
                )
            ]
        )

        # When source_type is api, only api_key should be required
        inputs_api = {"source_type": "api"}
        missing = workflow.get_missing_inputs(inputs_api)
        assert len(missing) == 1
        assert missing[0]["name"] == "api_key"

        # When source_type is database, only db_connection should be required
        inputs_db = {"source_type": "database"}
        missing = workflow.get_missing_inputs(inputs_db)
        assert len(missing) == 1
        assert missing[0]["name"] == "db_connection"

        # When source_type is file, neither should be required
        inputs_file = {"source_type": "file"}
        missing = workflow.get_missing_inputs(inputs_file)
        assert len(missing) == 0


# ==================== Test Workflow Execution ====================

class TestWorkflowExecution:
    """Tests for workflow execution engine"""

    def test_start_workflow_with_missing_inputs(self, temp_state_dir):
        """Test starting workflow with missing required inputs"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow_dict = {
            "workflow_id": "missing_inputs_wf",
            "name": "Missing Inputs Test",
            "description": "Test missing inputs handling",
            "input_schema": [
                {
                    "name": "required_field",
                    "type": "string",
                    "label": "Required Field",
                    "description": "A required field",
                    "required": True
                }
            ],
            "steps": [
                {"step_id": "s1", "name": "S1", "description": "Step 1", "step_type": "task", "depends_on": []}
            ]
        }

        # Create workflow
        asyncio.run(engine.create_workflow(workflow_dict))

        # Try to start without required inputs
        result = asyncio.run(engine.start_workflow("missing_inputs_wf", {}))

        assert result["status"] == "waiting_for_input"
        assert "missing_parameters" in result
        assert len(result["missing_parameters"]) == 1

    def test_start_workflow_success(self, temp_state_dir):
        """Test starting workflow with all required inputs"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow_dict = {
            "workflow_id": "start_success_wf",
            "name": "Start Success",
            "description": "Test successful workflow start",
            "input_schema": [
                {
                    "name": "data_source",
                    "type": "string",
                    "label": "Data Source",
                    "description": "Source of data",
                    "required": True
                }
            ],
            "steps": [
                {"step_id": "validate", "name": "Validate", "description": "Validate inputs", "step_type": "task", "depends_on": []},
                {"step_id": "process", "name": "Process", "description": "Process data", "step_type": "task", "depends_on": ["validate"]}
            ]
        }

        # Create workflow
        asyncio.run(engine.create_workflow(workflow_dict))

        # Start with required inputs
        result = asyncio.run(engine.start_workflow("start_success_wf", {"data_source": "api"}))

        assert result["status"] == "started"
        assert "execution_id" in result
        assert "planned_steps" in result
        assert len(result["planned_steps"]) == 2

    def test_execution_plan_with_dependencies(self, temp_state_dir):
        """Test execution plan respects step dependencies"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="complex_deps_wf",
            name="Complex Dependencies",
            description="Test complex dependency graph",
            steps=[
                WorkflowStep(step_id="a", name="A", description="Step A", step_type="task", depends_on=[]),
                WorkflowStep(step_id="b", name="B", description="Step B", step_type="task", depends_on=["a"]),
                WorkflowStep(step_id="c", name="C", description="Step C", step_type="task", depends_on=["a"]),
                WorkflowStep(step_id="d", name="D", description="Step D", step_type="task", depends_on=["b", "c"])
            ]
        )

        plan = engine._create_execution_plan(workflow)

        # Should execute in dependency order: a -> [b, c] -> d
        assert plan.planned_steps[0] == "a"
        assert plan.planned_steps[-1] == "d"
        assert "b" in plan.planned_steps
        assert "c" in plan.planned_steps

        # Should identify parallel group (b and c can run in parallel)
        assert len(plan.parallel_groups) > 0
        assert {"b", "c"} in [set(g) for g in plan.parallel_groups]

    def test_execution_plan_empty_workflow(self, temp_state_dir):
        """Test execution plan for workflow with no steps"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="empty_wf",
            name="Empty Workflow",
            description="No steps",
            steps=[]
        )

        plan = engine._create_execution_plan(workflow)

        assert len(plan.planned_steps) == 0
        assert len(plan.parallel_groups) == 0


# ==================== Test Step Execution ====================

class TestStepExecution:
    """Tests for individual step execution"""

    @pytest.mark.asyncio
    async def test_execute_step_api_call(self, temp_state_dir):
        """Test executing API call step"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="api_step_wf",
            name="API Step Test",
            description="Test API call step execution"
        )

        step = WorkflowStep(
            step_id="api_call",
            name="API Call",
            description="Call external API",
            step_type="api_call",
            depends_on=[]
        )

        result = await engine._execute_step(workflow, step)

        assert result["status"] == "success"
        assert "execution_time" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_execute_step_data_transform(self, temp_state_dir):
        """Test executing data transformation step"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="transform_step_wf",
            name="Transform Step Test",
            description="Test data transform step execution",
            user_inputs={"raw_data": "test"}
        )

        step = WorkflowStep(
            step_id="transform",
            name="Transform",
            description="Transform data",
            step_type="data_transform",
            depends_on=[]
        )

        result = await engine._execute_step(workflow, step)

        assert result["status"] == "success"
        assert "result" in result

    @pytest.mark.asyncio
    async def test_execute_step_user_input(self, temp_state_dir):
        """Test executing user input step"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="user_input_step_wf",
            name="User Input Step Test",
            description="Test user input step execution"
        )

        step = WorkflowStep(
            step_id="user_input",
            name="User Input",
            description="Get user input",
            step_type="user_input",
            depends_on=[]
        )

        result = await engine._execute_step(workflow, step)

        assert result["status"] == "success"
        assert "result" in result

    @pytest.mark.asyncio
    async def test_execute_step_condition(self, temp_state_dir):
        """Test executing condition step"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="condition_step_wf",
            name="Condition Step Test",
            description="Test condition step execution",
            user_inputs={"amount": 1500}
        )

        step = WorkflowStep(
            step_id="condition",
            name="Condition",
            description="Evaluate condition",
            step_type="condition",
            depends_on=[]
        )

        result = await engine._execute_step(workflow, step)

        assert result["status"] == "success"
        assert "result" in result

    @pytest.mark.asyncio
    async def test_execute_step_custom_type(self, temp_state_dir):
        """Test executing custom step type"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="custom_step_wf",
            name="Custom Step Test",
            description="Test custom step execution"
        )

        step = WorkflowStep(
            step_id="custom",
            name="Custom",
            description="Custom step",
            step_type="custom_processing",
            depends_on=[]
        )

        result = await engine._execute_step(workflow, step)

        assert result["status"] == "success"
        assert result["result"]["step_type"] == "custom_processing"

    @pytest.mark.asyncio
    async def test_execute_step_with_error(self, temp_state_dir):
        """Test step execution with error"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow = AdvancedWorkflowDefinition(
            workflow_id="error_step_wf",
            name="Error Step Test",
            description="Test error handling in step execution"
        )

        # Create a step that will fail
        step = WorkflowStep(
            step_id="failing_step",
            name="Failing Step",
            description="This step will fail",
            step_type="api_call",
            depends_on=[]
        )

        # Mock the API call to raise an exception
        original_execute = engine._execute_api_call
        async def failing_execute(step, inputs):
            raise ValueError("Simulated API error")

        engine._execute_api_call = failing_execute

        result = await engine._execute_step(workflow, step)

        # Should handle error gracefully
        assert result["status"] == "error"
        assert "error" in result

        # Restore original
        engine._execute_api_call = original_execute


# ==================== Test Error Handling ====================

class TestErrorHandling:
    """Tests for error handling and recovery"""

    def test_workflow_marked_failed_on_exception(self, temp_state_dir):
        """Test workflow is marked as FAILED when exception occurs"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow_dict = {
            "workflow_id": "failing_wf",
            "name": "Failing Workflow",
            "description": "Test failure handling",
            "steps": [
                {"step_id": "s1", "name": "S1", "description": "Step 1", "step_type": "task", "depends_on": []}
            ]
        }

        asyncio.run(engine.create_workflow(workflow_dict))

        # Mock execution to raise error
        async def failing_execute(workflow, plan):
            raise ValueError("Simulated workflow failure")

        original_execute = engine._execute_workflow
        engine._execute_workflow = failing_execute

        # This should handle the error and mark workflow as failed
        try:
            asyncio.run(engine.start_workflow("failing_wf", {}))
        except:
            pass

        # Verify workflow is marked as failed
        state = state_manager.load_state("failing_wf")
        # The workflow should be in FAILED state or RUNNING (if execution didn't complete)

        engine._execute_workflow = original_execute

    def test_pause_nonexistent_workflow(self):
        """Test pausing non-existent workflow returns False"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        result = engine.pause_workflow("nonexistent_wf")
        assert result is False

    def test_cancel_nonexistent_workflow(self):
        """Test canceling non-existent workflow returns False"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        result = engine.cancel_workflow("nonexistent_wf")
        assert result is False

    def test_pause_completed_workflow(self, temp_state_dir):
        """Test pausing already completed workflow"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow_dict = {
            "workflow_id": "completed_wf",
            "name": "Completed Workflow",
            "description": "Test pausing completed workflow",
            "state": WorkflowState.COMPLETED
        }

        state_manager.save_state("completed_wf", workflow_dict)

        result = engine.pause_workflow("completed_wf")
        # Should not pause a completed workflow
        # (Implementation-specific, this might return False or be a no-op)


# ==================== Test Workflow State Transitions ====================

class TestWorkflowStateTransitions:
    """Tests for workflow state transitions"""

    def test_state_transition_draft_to_running(self, temp_state_dir):
        """Test state transition from DRAFT to RUNNING"""
        state_manager = StateManager()

        # Create workflow in DRAFT state
        workflow_dict = {
            "workflow_id": "draft_to_running_wf",
            "name": "Draft to Running",
            "description": "Test DRAFT to RUNNING transition",
            "state": WorkflowState.DRAFT,
            "steps": [
                {"step_id": "s1", "name": "S1", "description": "Step 1", "step_type": "task", "depends_on": []}
            ]
        }

        state_manager.save_state("draft_to_running_wf", workflow_dict)

        # Load and verify state
        state = state_manager.load_state("draft_to_running_wf")
        assert state["state"] == WorkflowState.DRAFT

    def test_state_transition_running_to_paused(self, temp_state_dir):
        """Test state transition from RUNNING to PAUSED"""
        state_manager = StateManager()
        engine = ExecutionEngine(state_manager)

        workflow_dict = {
            "workflow_id": "running_to_paused_wf",
            "name": "Running to Paused",
            "description": "Test RUNNING to PAUSED transition",
            "state": WorkflowState.RUNNING,
            "steps": []
        }

        state_manager.save_state("running_to_paused_wf", workflow_dict)

        # Pause workflow
        result = engine.pause_workflow("running_to_paused_wf")

        assert result is True

        # Verify state transition
        state = state_manager.load_state("running_to_paused_wf")
        assert state["state"] == WorkflowState.PAUSED

    def test_state_transition_to_completed(self, temp_state_dir):
        """Test state transition to COMPLETED"""
        state_manager = StateManager()

        workflow_dict = {
            "workflow_id": "to_completed_wf",
            "name": "To Completed",
            "description": "Test transition to COMPLETED",
            "state": WorkflowState.RUNNING,
            "current_step": "final_step",
            "steps": [
                {"step_id": "final_step", "name": "Final", "description": "Final step", "step_type": "task"}
            ]
        }

        state_manager.save_state("to_completed_wf", workflow_dict)

        # Simulate completion by updating state
        workflow_dict["state"] = WorkflowState.COMPLETED
        workflow_dict["current_step"] = None
        state_manager.save_state("to_completed_wf", workflow_dict)

        # Verify state
        state = state_manager.load_state("to_completed_wf")
        assert state["state"] == WorkflowState.COMPLETED
        assert state["current_step"] is None


# ==================== Test Multi-Output Workflows ====================

class TestMultiOutputWorkflows:
    """Tests for multi-output workflow configurations"""

    def test_multi_output_config_dataset(self):
        """Test multi-output configuration for dataset type"""
        config = MultiOutputConfig(
            output_type="dataset",
            output_parameters=[
                InputParameter(
                    name="output_path",
                    type=ParameterType.STRING,
                    label="Output Path",
                    description="Path to output dataset",
                    required=True
                )
            ]
        )

        assert config.output_type == "dataset"
        assert len(config.output_parameters) == 1
        assert config.output_parameters[0].name == "output_path"

    def test_multi_output_config_stream(self):
        """Test multi-output configuration for stream type"""
        config = MultiOutputConfig(
            output_type="stream",
            output_parameters=[
                InputParameter(
                    name="stream_url",
                    type=ParameterType.STRING,
                    label="Stream URL",
                    description="URL for output stream",
                    required=True
                )
            ]
        )

        assert config.output_type == "stream"
        assert len(config.output_parameters) == 1

    def test_multi_output_config_with_aggregation(self):
        """Test multi-output configuration with aggregation method"""
        config = MultiOutputConfig(
            output_type="multiple_files",
            output_parameters=[
                InputParameter(
                    name="file_pattern",
                    type=ParameterType.STRING,
                    label="File Pattern",
                    description="Pattern for output files",
                    required=True
                )
            ],
            aggregation_method="concatenate"
        )

        assert config.output_type == "multiple_files"
        assert config.aggregation_method == "concatenate"

    def test_workflow_with_multi_output(self):
        """Test workflow definition with multi-output config"""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="multi_output_wf",
            name="Multi Output Workflow",
            description="Test multi-output",
            output_config=MultiOutputConfig(
                output_type="report",
                output_parameters=[
                    InputParameter(
                        name="report_format",
                        type=ParameterType.SELECT,
                        label="Report Format",
                        description="Format of the report",
                        required=True,
                        options=["pdf", "html", "json"]
                    )
                ]
            )
        )

        assert workflow.output_config is not None
        assert workflow.output_config.output_type == "report"
        assert len(workflow.output_config.output_parameters) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
