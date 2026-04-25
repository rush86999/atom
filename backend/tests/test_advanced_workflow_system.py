"""
Advanced Workflow System Tests
Tests for core/advanced_workflow_system.py

Tests cover:
- ParameterType and WorkflowState enums
- InputParameter model validation
- WorkflowStep model and execution
- MultiOutputConfig structure
- AdvancedWorkflowDefinition workflow creation and validation
- State management and transitions
- Parameter dependencies and conditions
"""

import os
os.environ["TESTING"] = "1"

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from pydantic import ValidationError

from core.advanced_workflow_system import (
    ParameterType,
    WorkflowState,
    InputParameter,
    WorkflowStep,
    MultiOutputConfig,
    AdvancedWorkflowDefinition,
)


class TestParameterTypeEnum:
    """Test ParameterType enum values and string conversion."""

    def test_enum_values(self):
        """ParameterType has all expected enum values."""
        assert ParameterType.STRING.value == "string"
        assert ParameterType.NUMBER.value == "number"
        assert ParameterType.BOOLEAN.value == "boolean"
        assert ParameterType.ARRAY.value == "array"
        assert ParameterType.OBJECT.value == "object"
        assert ParameterType.FILE.value == "file"
        assert ParameterType.SELECT.value == "select"
        assert ParameterType.MULTISELECT.value == "multiselect"

    def test_string_enum(self):
        """ParameterType is a string enum."""
        param_type = ParameterType.STRING
        assert isinstance(param_type, str)
        assert param_type == "string"

    def test_parameter_types(self):
        """All parameter types are correctly defined."""
        types = [t.value for t in ParameterType]
        assert "string" in types
        assert "number" in types
        assert "boolean" in types
        assert "array" in types
        assert "object" in types
        assert "file" in types
        assert "select" in types
        assert "multiselect" in types


class TestWorkflowStateEnum:
    """Test WorkflowState enum values and transitions."""

    def test_state_values(self):
        """WorkflowState has all expected state values."""
        assert WorkflowState.DRAFT.value == "draft"
        assert WorkflowState.WAITING_FOR_INPUT.value == "waiting_for_input"
        assert WorkflowState.RUNNING.value == "running"
        assert WorkflowState.PAUSED.value == "paused"
        assert WorkflowState.COMPLETED.value == "completed"
        assert WorkflowState.FAILED.value == "failed"
        assert WorkflowState.CANCELLED.value == "cancelled"

    def test_state_transitions(self):
        """WorkflowState supports valid state transitions."""
        state = WorkflowState.DRAFT
        assert state in WorkflowState

    def test_default_state(self):
        """WorkflowState default is DRAFT."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test-wf",
            name="Test Workflow",
            description="Test description"
        )
        assert workflow.state == WorkflowState.DRAFT


class TestInputParameter:
    """Test InputParameter model validation."""

    def test_valid_parameter(self):
        """InputParameter accepts valid parameter definition."""
        param = InputParameter(
            name="test_param",
            type=ParameterType.STRING,
            label="Test Parameter",
            description="A test parameter",
            required=True
        )
        assert param.name == "test_param"
        assert param.type == ParameterType.STRING
        assert param.label == "Test Parameter"
        assert param.required is True

    def test_required_validation(self):
        """InputParameter required field validation works."""
        param = InputParameter(
            name="required_param",
            type=ParameterType.STRING,
            label="Required Parameter",
            description="This is required",
            required=True
        )
        assert param.required is True
        assert param.default_value is None

    def test_type_validation(self):
        """InputParameter type must be valid ParameterType."""
        param = InputParameter(
            name="typed_param",
            type=ParameterType.NUMBER,
            label="Number Parameter",
            description="A number parameter"
        )
        assert param.type == ParameterType.NUMBER

    def test_default_values(self):
        """InputParameter default values are set correctly."""
        param = InputParameter(
            name="param_with_default",
            type=ParameterType.STRING,
            label="Parameter with Default",
            description="Has default value",
            required=False,
            default_value="default"
        )
        assert param.default_value == "default"
        assert param.required is False


class TestWorkflowStep:
    """Test WorkflowStep model and execution logic."""

    def test_step_creation(self):
        """WorkflowStep can be created with valid parameters."""
        step = WorkflowStep(
            step_id="step-1",
            name="First Step",
            description="Execute first step",
            step_type="data_processing",
            input_parameters=[
                InputParameter(
                    name="input_data",
                    type=ParameterType.STRING,
                    label="Input Data",
                    description="Data to process"
                )
            ],
            output_schema={"result": "string"},
            timeout_seconds=300
        )
        assert step.step_id == "step-1"
        assert step.name == "First Step"
        assert step.step_type == "data_processing"
        assert len(step.input_parameters) == 1
        assert step.timeout_seconds == 300

    def test_step_execution(self):
        """WorkflowStep has execution configuration."""
        step = WorkflowStep(
            step_id="step-2",
            name="Second Step",
            description="Execute second step",
            step_type="analysis",
            can_pause=True,
            is_parallel=False
        )
        assert step.can_pause is True
        assert step.is_parallel is False

    def test_step_validation(self):
        """WorkflowStep validates required fields."""
        with pytest.raises(ValidationError):
            WorkflowStep(
                name="Invalid Step",
                description="Missing step_id"
            )


class TestMultiOutputConfig:
    """Test MultiOutputConfig structure."""

    def test_multi_output_config(self):
        """MultiOutputConfig defines output structure."""
        config = MultiOutputConfig(
            output_type="dataset",
            output_parameters=[
                InputParameter(
                    name="output_file",
                    type=ParameterType.FILE,
                    label="Output File",
                    description="Generated output file",
                    required=False
                )
            ],
            aggregation_method="concatenate"
        )
        assert config.output_type == "dataset"
        assert len(config.output_parameters) == 1
        assert config.aggregation_method == "concatenate"


class TestAdvancedWorkflowDefinition:
    """Test AdvancedWorkflowDefinition workflow creation and validation."""

    def test_workflow_creation(self):
        """AdvancedWorkflowDefinition can be created with valid parameters."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-001",
            name="Test Workflow",
            description="A test workflow",
            version="1.0",
            category="test"
        )
        assert workflow.workflow_id == "wf-001"
        assert workflow.name == "Test Workflow"
        assert workflow.version == "1.0"
        assert workflow.category == "test"
        assert workflow.state == WorkflowState.DRAFT

    def test_workflow_validation(self):
        """AdvancedWorkflowDefinition validates required fields."""
        with pytest.raises(ValidationError):
            AdvancedWorkflowDefinition(
                name="Invalid Workflow"
                # Missing workflow_id
            )

    def test_workflow_with_steps(self):
        """AdvancedWorkflowDefinition can have multiple steps."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-002",
            name="Multi-Step Workflow",
            description="Workflow with multiple steps",
            steps=[
                WorkflowStep(
                    step_id="step-1",
                    name="Step 1",
                    description="First step",
                    step_type="processing"
                ),
                WorkflowStep(
                    step_id="step-2",
                    name="Step 2",
                    description="Second step",
                    step_type="analysis"
                )
            ]
        )
        assert len(workflow.steps) == 2
        assert workflow.steps[0].step_id == "step-1"
        assert workflow.steps[1].step_id == "step-2"

    def test_workflow_with_input_schema(self):
        """AdvancedWorkflowDefinition can have input schema."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-003",
            name="Input Workflow",
            description="Workflow with input schema",
            input_schema=[
                InputParameter(
                    name="username",
                    type=ParameterType.STRING,
                    label="Username",
                    description="User name",
                    required=True
                ),
                InputParameter(
                    name="age",
                    type=ParameterType.NUMBER,
                    label="Age",
                    description="User age",
                    required=True
                )
            ]
        )
        assert len(workflow.input_schema) == 2
        assert workflow.input_schema[0].name == "username"
        assert workflow.input_schema[1].name == "age"

    def test_workflow_with_output_config(self):
        """AdvancedWorkflowDefinition can have output configuration."""
        output_config = MultiOutputConfig(
            output_type="report",
            output_parameters=[
                InputParameter(
                    name="report_file",
                    type=ParameterType.FILE,
                    label="Report File",
                    description="Generated report",
                    required=False
                )
            ]
        )
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-004",
            name="Output Workflow",
            description="Workflow with output config",
            output_config=output_config
        )
        assert workflow.output_config is not None
        assert workflow.output_config.output_type == "report"

    def test_workflow_state_transitions(self):
        """AdvancedWorkflowDefinition supports state transitions."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-005",
            name="State Workflow",
            description="Workflow testing state transitions"
        )
        assert workflow.state == WorkflowState.DRAFT

        workflow.state = WorkflowState.RUNNING
        assert workflow.state == WorkflowState.RUNNING

        workflow.state = WorkflowState.COMPLETED
        assert workflow.state == WorkflowState.COMPLETED

    def test_workflow_advance_to_step(self):
        """AdvancedWorkflowDefinition can advance to specific step."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-006",
            name="Step Workflow",
            description="Workflow testing step advancement",
            steps=[
                WorkflowStep(
                    step_id="step-1",
                    name="Step 1",
                    description="First step",
                    step_type="processing"
                ),
                WorkflowStep(
                    step_id="step-2",
                    name="Step 2",
                    description="Second step",
                    step_type="analysis"
                )
            ]
        )
        assert workflow.current_step is None

        workflow.advance_to_step("step-2")
        assert workflow.current_step == "step-2"

    def test_workflow_get_missing_inputs(self):
        """AdvancedWorkflowDefinition can identify missing required inputs."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-007",
            name="Missing Inputs Workflow",
            description="Workflow testing missing inputs",
            input_schema=[
                InputParameter(
                    name="required_param",
                    type=ParameterType.STRING,
                    label="Required Param",
                    description="Required parameter",
                    required=True
                ),
                InputParameter(
                    name="optional_param",
                    type=ParameterType.STRING,
                    label="Optional Param",
                    description="Optional parameter",
                    required=False
                )
            ]
        )

        # No inputs provided
        missing = workflow.get_missing_inputs({})
        assert len(missing) == 1
        assert missing[0]["name"] == "required_param"

        # Required input provided
        missing = workflow.get_missing_inputs({"required_param": "value"})
        assert len(missing) == 0

    def test_workflow_parameter_with_default_not_missing(self):
        """InputParameter with default value is not considered missing."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-008",
            name="Default Parameter Workflow",
            description="Workflow testing default parameters",
            input_schema=[
                InputParameter(
                    name="param_with_default",
                    type=ParameterType.STRING,
                    label="Param with Default",
                    description="Parameter with default value",
                    required=True,
                    default_value="default_value"
                )
            ]
        )

        # No inputs provided, but default exists
        missing = workflow.get_missing_inputs({})
        assert len(missing) == 0

    def test_workflow_conditional_parameter_visibility(self):
        """InputParameter visibility can be conditional."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-009",
            name="Conditional Parameter Workflow",
            description="Workflow testing conditional parameters",
            input_schema=[
                InputParameter(
                    name="show_second",
                    type=ParameterType.BOOLEAN,
                    label="Show Second",
                    description="Whether to show second parameter",
                    required=False
                ),
                InputParameter(
                    name="conditional_param",
                    type=ParameterType.STRING,
                    label="Conditional Param",
                    description="Conditional parameter",
                    required=True,
                    show_when={"show_second": [True]}
                )
            ]
        )

        # Conditional parameter should be visible when show_second is True
        assert workflow._should_show_parameter(
            workflow.input_schema[1],
            {"show_second": True}
        ) is True

        # Conditional parameter should be hidden when show_second is False
        assert workflow._should_show_parameter(
            workflow.input_schema[1],
            {"show_second": False}
        ) is False
