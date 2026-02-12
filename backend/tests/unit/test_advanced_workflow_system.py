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
                "workflow_id": f"status_test_{status}",
                "name": f"Status Test {status}",
                "state": status,
                "steps": []
            }
            state_manager.save_state(f"status_test_{status}", state)

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
