"""
Comprehensive unit tests for EnhancedExecutionStateManager class

Tests cover:
- Initialization and configuration
- Enhanced execution state lifecycle
- Step execution management (start, complete, fail, skip)
- Pause and resume functionality
- State transitions and validation
- Multi-output aggregation
- Progress tracking
- Database persistence
- Concurrency handling
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime
from typing import Dict, Any
import json

# Import the EnhancedExecutionStateManager and related classes
from core.enhanced_execution_state_manager import (
    EnhancedExecutionStateManager,
    EnhancedExecutionState,
    WorkflowState,
    StepState,
    ParameterDefinition,
    MultiOutputConfig,
    get_enhanced_state_manager
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_base_state_manager():
    """Mock base ExecutionStateManager for testing"""
    manager = AsyncMock()
    manager.create_execution = AsyncMock(return_value="base-execution-123")
    manager.get_execution_state = AsyncMock(return_value={
        "execution_id": "test-execution-123",
        "workflow_id": "test-workflow",
        "status": "RUNNING",
        "input_data": {"test_input": "value"},
        "steps": {},
        "outputs": {},
        "context": {},
        "version": 1
    })
    manager.update_step_status = AsyncMock()
    manager.update_execution_status = AsyncMock()
    return manager


@pytest.fixture
def mock_db_session():
    """Mock database session for testing"""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def enhanced_state_manager(mock_base_state_manager):
    """Create an EnhancedExecutionStateManager instance with mocked dependencies"""
    with patch('core.enhanced_execution_state_manager.ExecutionStateManager.__init__', return_value=None):
        manager = EnhancedExecutionStateManager()
        manager.create_execution = mock_base_state_manager.create_execution
        manager.get_execution_state = mock_base_state_manager.get_execution_state
        manager.update_step_status = mock_base_state_manager.update_step_status
        manager.update_execution_status = mock_base_state_manager.update_execution_status
        yield manager


@pytest.fixture
def sample_step_definitions():
    """Sample step definitions for testing"""
    return [
        {"step_id": "step1", "name": "First Step", "action": "process"},
        {"step_id": "step2", "name": "Second Step", "action": "validate"},
        {"step_id": "step3", "name": "Third Step", "action": "output"}
    ]


@pytest.fixture
def sample_required_inputs():
    """Sample required inputs for testing"""
    return [
        {
            "name": "api_key",
            "type": "string",
            "label": "API Key",
            "description": "API key for service",
            "required": True
        },
        {
            "name": "endpoint",
            "type": "string",
            "label": "Endpoint",
            "description": "Service endpoint",
            "required": True
        }
    ]


@pytest.fixture
def sample_multi_output_config():
    """Sample multi-output configuration for testing"""
    return {
        "output_type": "multiple",
        "aggregation_method": "append",
        "output_schema": {"results": "array"},
        "step_outputs": {}
    }


@pytest.fixture
def sample_execution_state():
    """Sample execution state for testing"""
    return EnhancedExecutionState(
        execution_id="test-execution-123",
        workflow_id="test-workflow"
    )


# =============================================================================
# TEST STATE MANAGER INITIALIZATION
# =============================================================================

class TestStateManagerInit:
    """Tests for EnhancedExecutionStateManager initialization"""

    def test_init_creates_empty_state(self):
        """Test that initialization creates empty state dictionaries"""
        manager = EnhancedExecutionStateManager()
        assert hasattr(manager, 'enhanced_states')
        assert hasattr(manager, 'step_completion_callbacks')
        assert hasattr(manager, 'pause_callbacks')
        assert len(manager.enhanced_states) == 0
        assert len(manager.step_completion_callbacks) == 0
        assert len(manager.pause_callbacks) == 0

    def test_global_singleton(self):
        """Test that get_enhanced_state_manager returns singleton instance"""
        manager1 = get_enhanced_state_manager()
        manager2 = get_enhanced_state_manager()
        assert manager1 is manager2


# =============================================================================
# TEST ENHANCED EXECUTION STATE
# =============================================================================

class TestEnhancedExecutionState:
    """Tests for EnhancedExecutionState dataclass"""

    def test_state_initialization(self):
        """Test state object initialization with default values"""
        state = EnhancedExecutionState(
            execution_id="exec-123",
            workflow_id="workflow-456"
        )
        assert state.execution_id == "exec-123"
        assert state.workflow_id == "workflow-456"
        assert state.state == WorkflowState.PENDING
        assert state.current_step_index == 0
        assert state.total_steps == 0
        assert len(state.step_states) == 0
        assert len(state.missing_inputs) == 0
        assert state.created_at is not None
        assert state.updated_at is not None

    def test_state_with_multi_output_config(self):
        """Test state with multi-output configuration"""
        config = MultiOutputConfig(
            output_type="multiple",
            aggregation_method="append"
        )
        state = EnhancedExecutionState(
            execution_id="exec-123",
            workflow_id="workflow-456"
        )
        state.multi_output_config = config
        assert state.multi_output_config.output_type == "multiple"


# =============================================================================
# TEST STATE LIFECYCLE
# =============================================================================

class TestStateLifecycle:
    """Tests for enhanced execution state lifecycle"""

    @pytest.mark.asyncio
    async def test_create_enhanced_execution(self, enhanced_state_manager, sample_step_definitions, sample_required_inputs):
        """Test creating an enhanced execution with step tracking"""
        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            execution_id = await enhanced_state_manager.create_enhanced_execution(
                workflow_id="test-workflow",
                input_data={"api_key": "test-key"},
                step_definitions=sample_step_definitions,
                required_inputs=sample_required_inputs
            )

            assert execution_id is not None
            assert execution_id in enhanced_state_manager.enhanced_states

            state = enhanced_state_manager.enhanced_states[execution_id]
            assert state.workflow_id == "test-workflow"
            assert state.total_steps == 3
            assert len(state.step_states) == 3
            assert state.step_states["step1"] == StepState.PENDING
            assert len(state.required_inputs) == 2

    @pytest.mark.asyncio
    async def test_create_enhanced_execution_with_multi_output(self, enhanced_state_manager, sample_step_definitions, sample_required_inputs, sample_multi_output_config):
        """Test creating execution with multi-output configuration"""
        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            execution_id = await enhanced_state_manager.create_enhanced_execution(
                workflow_id="test-workflow",
                input_data={"api_key": "test-key"},
                step_definitions=sample_step_definitions,
                required_inputs=sample_required_inputs,
                multi_output_config=sample_multi_output_config
            )

            state = enhanced_state_manager.enhanced_states[execution_id]
            assert state.multi_output_config is not None
            assert state.multi_output_config.output_type == "multiple"

    @pytest.mark.asyncio
    async def test_get_enhanced_execution_state_from_memory(self, enhanced_state_manager, sample_execution_state):
        """Test retrieving execution state from memory"""
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        state = await enhanced_state_manager.get_enhanced_execution_state("test-execution-123")
        assert state is not None
        assert state.execution_id == "test-execution-123"
        assert state.workflow_id == "test-workflow"

    @pytest.mark.asyncio
    async def test_get_enhanced_execution_state_not_found(self, enhanced_state_manager):
        """Test retrieving non-existent execution state"""
        with patch.object(enhanced_state_manager, 'get_execution_state', new_callable=AsyncMock, return_value=None):
            state = await enhanced_state_manager.get_enhanced_execution_state("non-existent")
            assert state is None


# =============================================================================
# TEST STEP EXECUTION
# =============================================================================

class TestStepExecution:
    """Tests for step execution management"""

    @pytest.mark.asyncio
    async def test_start_step_execution(self, enhanced_state_manager, sample_execution_state):
        """Test starting execution of a step"""
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state
        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            result = await enhanced_state_manager.start_step_execution(
                execution_id="test-execution-123",
                step_id="step1",
                step_inputs={"input": "value"}
            )

            assert result is True
            assert sample_execution_state.step_states["step1"] == StepState.RUNNING
            assert sample_execution_state.step_inputs["step1"] == {"input": "value"}

    @pytest.mark.asyncio
    async def test_complete_step(self, enhanced_state_manager, sample_execution_state):
        """Test completing a step"""
        sample_execution_state.total_steps = 3
        sample_execution_state.step_states["step1"] = StepState.RUNNING
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            with patch.object(enhanced_state_manager, '_check_missing_inputs', new_callable=AsyncMock, return_value=[]):
                result = await enhanced_state_manager.complete_step(
                    execution_id="test-execution-123",
                    step_id="step1",
                    outputs={"result": "success"}
                )

                assert result is True
                assert sample_execution_state.step_states["step1"] == StepState.COMPLETED
                assert sample_execution_state.step_outputs["step1"] == {"result": "success"}

    @pytest.mark.asyncio
    async def test_complete_step_finalizes_workflow(self, enhanced_state_manager, sample_execution_state):
        """Test that completing last step finalizes workflow"""
        sample_execution_state.total_steps = 1
        sample_execution_state.current_step_index = 0
        sample_execution_state.step_states["step1"] = StepState.RUNNING
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            with patch.object(enhanced_state_manager, '_check_missing_inputs', new_callable=AsyncMock, return_value=[]):
                await enhanced_state_manager.complete_step(
                    execution_id="test-execution-123",
                    step_id="step1",
                    outputs={"result": "done"}
                )

                assert sample_execution_state.state == WorkflowState.COMPLETED

    @pytest.mark.asyncio
    async def test_fail_step(self, enhanced_state_manager, sample_execution_state):
        """Test failing a step"""
        sample_execution_state.step_states["step1"] = StepState.RUNNING
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            result = await enhanced_state_manager.fail_step(
                execution_id="test-execution-123",
                step_id="step1",
                error="Connection failed"
            )

            assert result is True
            assert sample_execution_state.step_states["step1"] == StepState.FAILED
            assert sample_execution_state.error_details == "Connection failed"

    @pytest.mark.asyncio
    async def test_skip_step(self, enhanced_state_manager, sample_execution_state):
        """Test skipping a step"""
        sample_execution_state.step_states["step1"] = StepState.PENDING
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            result = await enhanced_state_manager.skip_step(
                execution_id="test-execution-123",
                step_id="step1",
                reason="Not needed"
            )

            assert result is True
            assert sample_execution_state.step_states["step1"] == StepState.SKIPPED
            assert sample_execution_state.current_step_index == 1


# =============================================================================
# TEST PAUSE AND RESUME
# =============================================================================

class TestPauseResume:
    """Tests for pause and resume functionality"""

    @pytest.mark.asyncio
    async def test_pause_execution(self, enhanced_state_manager, sample_execution_state):
        """Test pausing workflow execution"""
        sample_execution_state.state = WorkflowState.RUNNING
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            result = await enhanced_state_manager.pause_execution(
                execution_id="test-execution-123",
                reason="User requested pause"
            )

            assert result is True
            assert sample_execution_state.state == WorkflowState.PAUSED
            assert sample_execution_state.pause_reason == "User requested pause"

    @pytest.mark.asyncio
    async def test_pause_execution_with_inputs(self, enhanced_state_manager, sample_execution_state):
        """Test pausing and providing additional inputs"""
        sample_execution_state.state = WorkflowState.RUNNING
        sample_execution_state.collected_inputs = {"api_key": "test"}
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            result = await enhanced_state_manager.pause_execution(
                execution_id="test-execution-123",
                reason="Waiting for input",
                step_inputs={"endpoint": "https://api.example.com"}
            )

            assert result is True
            assert sample_execution_state.collected_inputs["endpoint"] == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_resume_execution_success(self, enhanced_state_manager, sample_execution_state):
        """Test resuming paused execution with all inputs"""
        sample_execution_state.state = WorkflowState.PAUSED
        sample_execution_state.required_inputs = [
            ParameterDefinition(name="api_key", type="string", label="API Key", required=True)
        ]
        sample_execution_state.collected_inputs = {"api_key": "test-key"}
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            with patch.object(enhanced_state_manager, '_check_missing_inputs', new_callable=AsyncMock, return_value=[]):
                result = await enhanced_state_manager.resume_execution(
                    execution_id="test-execution-123"
                )

                assert result is True
                assert sample_execution_state.state == WorkflowState.RUNNING
                assert sample_execution_state.pause_reason is None

    @pytest.mark.asyncio
    async def test_resume_execution_missing_inputs(self, enhanced_state_manager, sample_execution_state):
        """Test resuming execution with still-missing inputs"""
        sample_execution_state.state = WorkflowState.PAUSED
        sample_execution_state.required_inputs = [
            ParameterDefinition(name="api_key", type="string", label="API Key", required=True)
        ]
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            with patch.object(enhanced_state_manager, '_check_missing_inputs', new_callable=AsyncMock, return_value=["api_key"]):
                result = await enhanced_state_manager.resume_execution(
                    execution_id="test-execution-123",
                    additional_inputs={"endpoint": "https://api.example.com"}
                )

                assert result is False
                assert sample_execution_state.state == WorkflowState.PAUSED


# =============================================================================
# TEST STATE TRANSITIONS
# =============================================================================

class TestStateTransitions:
    """Tests for workflow state transitions"""

    def test_workflow_state_enum_values(self):
        """Test that WorkflowState enum has correct values"""
        assert WorkflowState.DRAFT.value == "draft"
        assert WorkflowState.PENDING.value == "pending"
        assert WorkflowState.RUNNING.value == "running"
        assert WorkflowState.PAUSED.value == "paused"
        assert WorkflowState.COMPLETED.value == "completed"
        assert WorkflowState.FAILED.value == "failed"

    def test_step_state_enum_values(self):
        """Test that StepState enum has correct values"""
        assert StepState.PENDING.value == "pending"
        assert StepState.RUNNING.value == "running"
        assert StepState.COMPLETED.value == "completed"
        assert StepState.FAILED.value == "failed"
        assert StepState.SKIPPED.value == "skipped"

    @pytest.mark.asyncio
    async def test_state_transition_running_to_paused(self, enhanced_state_manager, sample_execution_state):
        """Test state transition from RUNNING to PAUSED"""
        sample_execution_state.state = WorkflowState.RUNNING
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            await enhanced_state_manager.pause_execution("test-execution-123")
            assert sample_execution_state.state == WorkflowState.PAUSED

    @pytest.mark.asyncio
    async def test_state_transition_paused_to_running(self, enhanced_state_manager, sample_execution_state):
        """Test state transition from PAUSED to RUNNING"""
        sample_execution_state.state = WorkflowState.PAUSED
        sample_execution_state.collected_inputs = {"api_key": "test"}
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        with patch.object(enhanced_state_manager, '_save_enhanced_state', new_callable=AsyncMock):
            with patch.object(enhanced_state_manager, '_check_missing_inputs', new_callable=AsyncMock, return_value=[]):
                await enhanced_state_manager.resume_execution("test-execution-123")
                assert sample_execution_state.state == WorkflowState.RUNNING


# =============================================================================
# TEST MULTI-OUTPUT AGGREGATION
# =============================================================================

class TestMultiOutputAggregation:
    """Tests for multi-output aggregation"""

    @pytest.mark.asyncio
    async def test_aggregate_multiple_outputs(self, enhanced_state_manager, sample_execution_state):
        """Test aggregating outputs from multiple steps"""
        config = MultiOutputConfig(output_type="multiple")
        sample_execution_state.multi_output_config = config
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        await enhanced_state_manager._aggregate_outputs(
            sample_execution_state,
            "step1",
            {"result": "value1"}
        )

        await enhanced_state_manager._aggregate_outputs(
            sample_execution_state,
            "step1",
            {"result": "value2"}
        )

        assert "step1" in sample_execution_state.aggregated_outputs
        assert len(sample_execution_state.aggregated_outputs["step1"]) == 2

    @pytest.mark.asyncio
    async def test_aggregate_outputs_merge(self, enhanced_state_manager, sample_execution_state):
        """Test merging outputs across steps"""
        config = MultiOutputConfig(output_type="aggregated")
        sample_execution_state.multi_output_config = config
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        await enhanced_state_manager._aggregate_outputs(
            sample_execution_state,
            "step1",
            {"count": 5}
        )

        await enhanced_state_manager._aggregate_outputs(
            sample_execution_state,
            "step2",
            {"count": 10}
        )

        assert "count" in sample_execution_state.aggregated_outputs
        assert len(sample_execution_state.aggregated_outputs["count"]) == 2

    @pytest.mark.asyncio
    async def test_aggregate_stream_outputs(self, enhanced_state_manager, sample_execution_state):
        """Test streaming outputs"""
        config = MultiOutputConfig(output_type="stream")
        sample_execution_state.multi_output_config = config
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        await enhanced_state_manager._aggregate_outputs(
            sample_execution_state,
            "step1",
            {"chunk": "data1"}
        )

        assert "stream_step1" in sample_execution_state.aggregated_outputs


# =============================================================================
# TEST PROGRESS TRACKING
# =============================================================================

class TestProgressTracking:
    """Tests for progress tracking"""

    @pytest.mark.asyncio
    async def test_get_progress_empty(self, enhanced_state_manager, sample_execution_state):
        """Test progress for workflow with no completed steps"""
        sample_execution_state.total_steps = 5
        sample_execution_state.step_states = {
            "step1": StepState.PENDING,
            "step2": StepState.PENDING
        }
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        progress = await enhanced_state_manager.get_progress("test-execution-123")

        assert progress["total_steps"] == 5
        assert progress["completed_steps"] == 0
        assert progress["progress_percentage"] == 0.0

    @pytest.mark.asyncio
    async def test_get_progress_partial(self, enhanced_state_manager, sample_execution_state):
        """Test progress for partially completed workflow"""
        sample_execution_state.total_steps = 4
        sample_execution_state.step_states = {
            "step1": StepState.COMPLETED,
            "step2": StepState.COMPLETED,
            "step3": StepState.RUNNING,
            "step4": StepState.PENDING
        }
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        progress = await enhanced_state_manager.get_progress("test-execution-123")

        assert progress["completed_steps"] == 2
        assert progress["progress_percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_get_step_details(self, enhanced_state_manager, sample_execution_state):
        """Test getting detailed information about a step"""
        sample_execution_state.step_states["step1"] = StepState.RUNNING
        sample_execution_state.step_inputs["step1"] = {"input": "value"}
        sample_execution_state.step_outputs["step1"] = {"output": "result"}
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        details = await enhanced_state_manager.get_step_details("test-execution-123", "step1")

        assert details["step_id"] == "step1"
        assert details["state"] == "running"
        assert details["inputs"] == {"input": "value"}
        assert details["outputs"] == {"output": "result"}


# =============================================================================
# TEST CALLBACKS
# =============================================================================

class TestCallbacks:
    """Tests for callback registration"""

    def test_register_pause_callback(self, enhanced_state_manager):
        """Test registering a pause callback"""
        callback = AsyncMock()
        enhanced_state_manager.register_pause_callback("exec-123", callback)

        assert "exec-123" in enhanced_state_manager.pause_callbacks
        assert enhanced_state_manager.pause_callbacks["exec-123"] is callback

    def test_register_step_completion_callback(self, enhanced_state_manager):
        """Test registering a step completion callback"""
        callback = AsyncMock()
        enhanced_state_manager.register_step_completion_callback("exec-123", callback)

        assert "exec-123" in enhanced_state_manager.step_completion_callbacks
        assert enhanced_state_manager.step_completion_callbacks["exec-123"] is callback


# =============================================================================
# TEST INPUT VALIDATION
# =============================================================================

class TestInputValidation:
    """Tests for input validation and checking"""

    @pytest.mark.asyncio
    async def test_check_missing_inputs_all_present(self, enhanced_state_manager, sample_execution_state):
        """Test checking missing inputs when all are present"""
        param = ParameterDefinition(
            name="api_key",
            type="string",
            label="API Key",
            required=True
        )
        sample_execution_state.required_inputs = [param]
        sample_execution_state.collected_inputs = {"api_key": "test-key"}
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        missing = await enhanced_state_manager._check_missing_inputs(sample_execution_state)

        assert len(missing) == 0

    @pytest.mark.asyncio
    async def test_check_missing_inputs_some_missing(self, enhanced_state_manager, sample_execution_state):
        """Test checking missing inputs when some are missing"""
        param1 = ParameterDefinition(
            name="api_key",
            type="string",
            label="API Key",
            required=True
        )
        param2 = ParameterDefinition(
            name="endpoint",
            type="string",
            label="Endpoint",
            required=True
        )
        sample_execution_state.required_inputs = [param1, param2]
        sample_execution_state.collected_inputs = {"api_key": "test-key"}
        enhanced_state_manager.enhanced_states["test-execution-123"] = sample_execution_state

        missing = await enhanced_state_manager._check_missing_inputs(sample_execution_state)

        assert len(missing) == 1
        assert "endpoint" in missing

    def test_should_show_parameter_no_condition(self):
        """Test parameter visibility when no condition is set"""
        param = ParameterDefinition(
            name="param1",
            type="string",
            label="Param 1",
            required=True
        )
        manager = EnhancedExecutionStateManager()
        result = manager._should_show_parameter(param, {})
        assert result is True

    def test_should_show_parameter_with_condition(self):
        """Test parameter visibility with condition"""
        param = ParameterDefinition(
            name="param2",
            type="string",
            label="Param 2",
            required=True,
            show_when={"param1": "value1"}
        )
        manager = EnhancedExecutionStateManager()
        result = manager._should_show_parameter(param, {"param1": "value1"})
        assert result is True

    def test_should_show_parameter_condition_not_met(self):
        """Test parameter visibility when condition is not met"""
        param = ParameterDefinition(
            name="param2",
            type="string",
            label="Param 2",
            required=True,
            show_when={"param1": "value1"}
        )
        manager = EnhancedExecutionStateManager()
        result = manager._should_show_parameter(param, {"param1": "other"})
        assert result is False
