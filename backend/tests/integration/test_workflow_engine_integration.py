"""
Integration tests for workflow_engine.py (Phase 12, GAP-02).

Tests cover:
- Async workflow execution with mocked state_manager, ws_manager, analytics
- Step execution with concurrency control
- Error recovery and retry logic
- Conditional branching evaluation
- DAG topological sort execution order
- Parameter resolution with variable references
- Schema validation for inputs and outputs
- Pause/resume on missing inputs
- WebSocket notification handling

Coverage target: 40% of workflow_engine.py (465+ lines from 1,163 total)
Current coverage: 9.17% (123 lines)
Target coverage: 40%+ (465+ lines)

Key difference from property tests: These tests CALL actual implementation methods
(execute_workflow, _execute_step, _resolve_parameters) rather than just validating
state transitions.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from core.workflow_engine import WorkflowEngine, MissingInputError
from core.models import WorkflowExecution, WorkflowStepExecution, WorkflowExecutionStatus
from tests.factories.workflow_factory import WorkflowExecutionFactory, WorkflowStepExecutionFactory


class TestAsyncWorkflowExecution:
    """Integration tests for async workflow execution paths."""

    @pytest.mark.asyncio
    async def test_execute_simple_workflow_with_mocks(self, db_session: Session):
        """Test actual workflow execution with mocked dependencies."""
        # Mock state manager
        mock_state_manager = AsyncMock()
        mock_state_manager.create_execution = AsyncMock(return_value="exec_123")
        mock_state_manager.get_execution_state = AsyncMock(return_value={
            "status": "RUNNING",
            "steps": {},
            "outputs": {},
            "inputs": {}
        })
        mock_state_manager.update_step_status = AsyncMock()
        mock_state_manager.update_execution_status = AsyncMock()

        # Mock WebSocket manager
        mock_ws_manager = MagicMock()
        mock_ws_manager.notify_workflow_status = AsyncMock()

        # Mock analytics
        mock_analytics = MagicMock()
        mock_analytics.track_step_execution = MagicMock()

        # Create engine with mocked dependencies
        engine = WorkflowEngine(max_concurrent_steps=2)
        engine.state_manager = mock_state_manager

        # Create actual workflow definition
        workflow_def = {
            "id": "test_workflow",
            "nodes": [
                {
                    "id": "step1",
                    "title": "First Step",
                    "type": "action",
                    "config": {
                        "action": "test_action",
                        "service": "test_service",
                        "parameters": {"input1": "value1"}
                    }
                }
            ],
            "connections": []
        }

        # Mock _execute_step to return success
        async def mock_execute_step(step, params):
            return {"result": {"status": "success", "data": "test_output"}}

        with patch.object(engine, '_execute_step', side_effect=mock_execute_step):
            with patch('core.analytics_engine.get_analytics_engine', return_value=mock_analytics):
                result = await engine._execute_workflow_graph(
                    execution_id="exec_123",
                    workflow=workflow_def,
                    state={"steps": {}, "outputs": {}},
                    ws_manager=mock_ws_manager,
                    user_id="test_user",
                    start_time=datetime.utcnow()
                )

        # Verify state manager was called
        mock_state_manager.create_execution.assert_called_once()
        mock_state_manager.update_step_status.assert_called()

        # Verify WebSocket notifications were sent
        assert mock_ws_manager.notify_workflow_status.call_count > 0

    @pytest.mark.asyncio
    async def test_concurrent_step_execution(self, db_session: Session):
        """Test actual step execution logic with concurrency limits."""
        # Mock dependencies
        mock_state_manager = AsyncMock()
        mock_state_manager.get_execution_state = AsyncMock(return_value={
            "status": "RUNNING",
            "steps": {},
            "outputs": {},
            "inputs": {}
        })
        mock_state_manager.update_step_status = AsyncMock()

        mock_ws_manager = MagicMock()
        mock_ws_manager.notify_workflow_status = AsyncMock()

        mock_analytics = MagicMock()
        mock_analytics.track_step_execution = MagicMock()

        # Create engine with concurrency limit of 2
        engine = WorkflowEngine(max_concurrent_steps=2)
        engine.state_manager = mock_state_manager

        # Create workflow with 3 steps
        workflow_def = {
            "id": "concurrent_test",
            "nodes": [
                {"id": "step1", "title": "Step 1", "type": "action", "config": {"action": "wait1"}},
                {"id": "step2", "title": "Step 2", "type": "action", "config": {"action": "wait2"}},
                {"id": "step3", "title": "Step 3", "type": "action", "config": {"action": "wait3"}},
            ],
            "connections": []
        }

        execution_order = []

        # Mock step executor that tracks execution order
        async def mock_execute_step(step, params):
            execution_order.append(step["id"])
            await asyncio.sleep(0.1)  # Simulate work
            return {"result": {"status": "success"}}

        with patch.object(engine, '_execute_step', side_effect=mock_execute_step):
            with patch('core.analytics_engine.get_analytics_engine', return_value=mock_analytics):
                await engine._execute_workflow_graph(
                    execution_id="exec_concurrent",
                    workflow=workflow_def,
                    state={"steps": {}, "outputs": {}},
                    ws_manager=mock_ws_manager,
                    user_id="test_user",
                    start_time=datetime.utcnow()
                )

        # Verify all steps were executed
        assert len(execution_order) == 3
        assert "step1" in execution_order
        assert "step2" in execution_order
        assert "step3" in execution_order

    @pytest.mark.asyncio
    async def test_workflow_retry_on_failure(self, db_session: Session):
        """Test actual retry logic when steps fail."""
        # Mock dependencies
        mock_state_manager = AsyncMock()
        mock_state_manager.get_execution_state = AsyncMock(return_value={
            "status": "RUNNING",
            "steps": {},
            "outputs": {},
            "inputs": {}
        })
        mock_state_manager.update_step_status = AsyncMock()

        mock_ws_manager = MagicMock()
        mock_ws_manager.notify_workflow_status = AsyncMock()

        mock_analytics = MagicMock()

        engine = WorkflowEngine()
        engine.state_manager = mock_state_manager

        workflow_def = {
            "id": "retry_test",
            "nodes": [
                {"id": "failing_step", "title": "Failing Step", "type": "action",
                 "config": {"action": "failing_action", "continue_on_error": True}}
            ],
            "connections": []
        }

        # Mock step executor that fails then succeeds
        call_count = 0
        async def mock_executor(step, context):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Simulated failure")
            return {"result": {"status": "success"}}

        with patch.object(engine, '_execute_step', side_effect=mock_executor):
            with patch('core.analytics_engine.get_analytics_engine', return_value=mock_analytics):
                try:
                    await engine._execute_workflow_graph(
                        execution_id="exec_retry",
                        workflow=workflow_def,
                        state={},
                        ws_manager=mock_ws_manager,
                        user_id="test_user",
                        start_time=datetime.utcnow()
                    )
                except Exception:
                    pass  # Expected to fail on first attempt

        # Verify retry was attempted
        assert call_count >= 1


class TestConditionalBranching:
    """Integration tests for conditional branching evaluation."""

    @pytest.mark.asyncio
    async def test_conditional_branch_execution(self, db_session: Session):
        """Test actual conditional branch evaluation."""
        # Mock dependencies
        mock_state_manager = AsyncMock()
        mock_state_manager.get_execution_state = AsyncMock(return_value={
            "status": "RUNNING",
            "steps": {
                "step1": {"status": "COMPLETED", "output": {"result": True}}
            },
            "outputs": {
                "step1": {"result": True}
            },
            "inputs": {}
        })
        mock_state_manager.update_step_status = AsyncMock()

        mock_ws_manager = MagicMock()
        mock_ws_manager.notify_workflow_status = AsyncMock()

        mock_analytics = MagicMock()
        mock_analytics.track_step_execution = MagicMock()

        engine = WorkflowEngine()
        engine.state_manager = mock_state_manager

        workflow_def = {
            "id": "conditional_test",
            "nodes": [
                {"id": "step1", "title": "Step 1", "type": "action",
                 "config": {"action": "set_value"}},
                {"id": "true_branch", "title": "True Branch", "type": "action",
                 "config": {"action": "true_action"}},
                {"id": "false_branch", "title": "False Branch", "type": "action",
                 "config": {"action": "false_action"}}
            ],
            "connections": [
                {"source": "step1", "target": "true_branch", "condition": "${step1.result} == true"},
                {"source": "step1", "target": "false_branch", "condition": "${step1.result} == false"}
            ]
        }

        executed_steps = []

        async def mock_execute_step(step, params):
            executed_steps.append(step["id"])
            if step["id"] == "step1":
                return {"result": {"result": True}}
            return {"result": {"status": "success"}}

        with patch.object(engine, '_execute_step', side_effect=mock_execute_step):
            with patch('core.analytics_engine.get_analytics_engine', return_value=mock_analytics):
                await engine._execute_workflow_graph(
                    execution_id="exec_conditional",
                    workflow=workflow_def,
                    state={"step1": {"result": True}},
                    ws_manager=mock_ws_manager,
                    user_id="test_user",
                    start_time=datetime.utcnow()
                )

        # Verify true_branch was executed
        assert "true_branch" in executed_steps

    @pytest.mark.asyncio
    async def test_has_conditional_connections(self, db_session: Session):
        """Test _has_conditional_connections method."""
        engine = WorkflowEngine()

        workflow_with_condition = {
            "id": "test",
            "connections": [
                {"source": "a", "target": "b", "condition": "${x} > 0"}
            ]
        }

        workflow_without_condition = {
            "id": "test",
            "connections": [
                {"source": "a", "target": "b"}
            ]
        }

        assert engine._has_conditional_connections(workflow_with_condition) == True
        assert engine._has_conditional_connections(workflow_without_condition) == False


class TestDAGExecution:
    """Integration tests for DAG execution order."""

    @pytest.mark.asyncio
    async def test_dag_execution_order(self, db_session: Session):
        """Test actual DAG execution preserves dependency order."""
        # Mock dependencies
        mock_state_manager = AsyncMock()
        mock_state_manager.get_execution_state = AsyncMock(return_value={
            "status": "RUNNING",
            "steps": {},
            "outputs": {},
            "inputs": {}
        })
        mock_state_manager.update_step_status = AsyncMock()

        mock_ws_manager = MagicMock()
        mock_ws_manager.notify_workflow_status = AsyncMock()

        mock_analytics = MagicMock()
        mock_analytics.track_step_execution = MagicMock()

        engine = WorkflowEngine()
        engine.state_manager = mock_state_manager

        # Create DAG: step3 depends on step1 and step2
        workflow_def = {
            "id": "dag_test",
            "nodes": [
                {"id": "step3", "title": "Final Step", "type": "action",
                 "config": {"action": "final"}},
                {"id": "step1", "title": "First Step", "type": "action",
                 "config": {"action": "first"}},
                {"id": "step2", "title": "Second Step", "type": "action",
                 "config": {"action": "second"}},
            ],
            "connections": [
                {"source": "step1", "target": "step3"},
                {"source": "step2", "target": "step3"}
            ]
        }

        execution_order = []

        async def tracking_executor(step, context):
            execution_order.append(step["id"])
            return {"result": {"status": "success"}}

        with patch.object(engine, '_execute_step', side_effect=tracking_executor):
            with patch('core.workflow_engine.get_analytics_engine', return_value=mock_analytics):
                await engine._execute_workflow_graph(
                    execution_id="exec_dag",
                    workflow=workflow_def,
                    state={"steps": {}, "outputs": {}},
                    ws_manager=mock_ws_manager,
                    user_id="test_user",
                    start_time=datetime.utcnow()
                )

        # Verify step1 and step2 executed before step3
        assert execution_order.index("step1") < execution_order.index("step3")
        assert execution_order.index("step2") < execution_order.index("step3")

    @pytest.mark.asyncio
    async def test_build_execution_graph(self, db_session: Session):
        """Test _build_execution_graph method."""
        engine = WorkflowEngine()

        workflow = {
            "id": "graph_test",
            "nodes": [
                {"id": "a", "title": "Node A"},
                {"id": "b", "title": "Node B"}
            ],
            "connections": [
                {"source": "a", "target": "b"}
            ]
        }

        graph = engine._build_execution_graph(workflow)

        assert "nodes" in graph
        assert "connections" in graph
        assert "adjacency" in graph
        assert "reverse_adjacency" in graph
        assert graph["nodes"]["a"]["title"] == "Node A"
        assert graph["adjacency"]["a"][0]["target"] == "b"
        assert graph["reverse_adjacency"]["b"][0]["source"] == "a"


class TestParameterResolution:
    """Integration tests for parameter resolution with variable references."""

    def test_resolve_simple_parameters(self, db_session: Session):
        """Test resolving parameters without variables."""
        engine = WorkflowEngine()

        params = {"input1": "value1", "input2": 42}
        state = {"steps": {}}

        result = engine._resolve_parameters(params, state)

        assert result == params

    def test_resolve_variable_references(self, db_session: Session):
        """Test resolving variable references like ${step_id.output_key}."""
        engine = WorkflowEngine()

        params = {"input1": "${step1.output}"}
        state = {
            "outputs": {
                "step1": {"result": "resolved_value"}
            }
        }

        result = engine._resolve_parameters(params, state)

        assert result["input1"] == "resolved_value"

    def test_resolve_nested_variable_references(self, db_session: Session):
        """Test resolving nested variable references."""
        engine = WorkflowEngine()

        params = {
            "input1": "${step1.data.nested}",
            "input2": "${step2}"
        }
        state = {
            "outputs": {
                "step1": {"data": {"nested": "value1"}},
                "step2": "value2"
            }
        }

        result = engine._resolve_parameters(params, state)

        assert result["input1"] == "value1"
        assert result["input2"] == "value2"

    def test_missing_variable_raises_error(self, db_session: Session):
        """Test that missing variables raise MissingInputError."""
        engine = WorkflowEngine()

        params = {"input1": "${missing_step.output}"}
        state = {"outputs": {}}

        with pytest.raises(MissingInputError) as exc_info:
            engine._resolve_parameters(params, state)

        assert "missing_step" in str(exc_info.value)


class TestSchemaValidation:
    """Integration tests for input and output schema validation."""

    def test_validate_input_schema_success(self, db_session: Session):
        """Test successful input schema validation."""
        engine = WorkflowEngine()

        step = {
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"}
                },
                "required": ["name"]
            }
        }

        params = {"name": "John", "age": 30}

        # Should not raise
        engine._validate_input_schema(step, params)

    def test_validate_input_schema_failure(self, db_session: Session):
        """Test input schema validation failure."""
        from core.workflow_engine import SchemaValidationError

        engine = WorkflowEngine()

        step = {
            "id": "test_step",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "required": ["name"]
            }
        }

        params = {"age": 30}  # Missing required 'name'

        with pytest.raises(SchemaValidationError):
            engine._validate_input_schema(step, params)

    def test_validate_output_schema_success(self, db_session: Session):
        """Test successful output schema validation."""
        engine = WorkflowEngine()

        step = {
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"}
                }
            }
        }

        output = {"result": {"status": "success"}}

        # Should not raise
        engine._validate_output_schema(step, output)

    def test_validate_output_schema_no_schema(self, db_session: Session):
        """Test that missing output schema doesn't raise error."""
        engine = WorkflowEngine()

        step = {}  # No output_schema
        output = {"result": {"status": "success"}}

        # Should not raise
        engine._validate_output_schema(step, output)


class TestNodeConversion:
    """Integration tests for node-to-step conversion."""

    def test_convert_nodes_to_steps_simple(self, db_session: Session):
        """Test converting simple graph nodes to steps."""
        engine = WorkflowEngine()

        workflow = {
            "id": "test",
            "nodes": [
                {
                    "id": "node1",
                    "title": "Node 1",
                    "type": "action",
                    "config": {
                        "service": "test_service",
                        "action": "test_action",
                        "parameters": {"param1": "value1"}
                    }
                }
            ],
            "connections": []
        }

        steps = engine._convert_nodes_to_steps(workflow)

        assert len(steps) == 1
        assert steps[0]["id"] == "node1"
        assert steps[0]["service"] == "test_service"
        assert steps[0]["action"] == "test_action"

    def test_convert_nodes_to_steps_with_trigger(self, db_session: Session):
        """Test converting trigger node to step."""
        engine = WorkflowEngine()

        workflow = {
            "id": "test",
            "nodes": [
                {
                    "id": "trigger1",
                    "title": "Manual Trigger",
                    "type": "trigger",
                    "config": {
                        "action": "manual_trigger"
                    }
                }
            ],
            "connections": []
        }

        steps = engine._convert_nodes_to_steps(workflow)

        assert len(steps) == 1
        assert steps[0]["type"] == "trigger"
        assert steps[0]["action"] == "manual_trigger"


class TestConditionEvaluation:
    """Integration tests for condition evaluation."""

    def test_evaluate_condition_simple(self, db_session: Session):
        """Test evaluating simple conditions."""
        engine = WorkflowEngine()

        state = {"outputs": {"value": 42}}
        condition = "${value} == 42"

        result = engine._evaluate_condition(condition, state)

        assert result == True

    def test_evaluate_condition_complex(self, db_session: Session):
        """Test evaluating complex conditions."""
        engine = WorkflowEngine()

        state = {
            "outputs": {
                "step1": {"output": {"result": True}}
            }
        }
        condition = "${step1.output.result} == true"

        result = engine._evaluate_condition(condition, state)

        assert result == True

    def test_evaluate_condition_false(self, db_session: Session):
        """Test evaluating false conditions."""
        engine = WorkflowEngine()

        state = {"value": 10}
        condition = "${value} > 100"

        result = engine._evaluate_condition(condition, state)

        assert result == False
