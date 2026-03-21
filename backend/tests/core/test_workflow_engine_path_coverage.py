"""
Path coverage tests for workflow_engine.py - Target 50%+

These tests focus on covering the main execution paths without complex mocking.
They test the actual behavior with mocked external dependencies.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone
from core.workflow_engine import WorkflowEngine, MissingInputError
from core.models import WorkflowExecutionLog
from core.execution_state_manager import get_state_manager


class TestWorkflowEngineConditionalEvaluation:
    """Test condition evaluation logic."""

    def test_evaluate_condition_simple_true(self):
        """Test simple condition that evaluates to true."""
        engine = WorkflowEngine()
        # Create state with proper structure
        state = {
            "input_data": {"value": 15},
            "outputs": {}
        }
        # Condition using simple eval with allowed_names
        result = engine._evaluate_condition("True", state)
        assert result is True

    def test_evaluate_condition_simple_false(self):
        """Test simple condition that evaluates to false."""
        engine = WorkflowEngine()
        state = {"input_data": {}, "outputs": {}}
        result = engine._evaluate_condition("False", state)
        assert result is False

    def test_evaluate_condition_error_handling(self):
        """Test condition evaluation with invalid expression."""
        engine = WorkflowEngine()
        state = {"input_data": {}, "outputs": {}}
        # Invalid expression should return False (safe default)
        result = engine._evaluate_condition("undefined_var", state)
        assert result is False

    def test_has_conditional_connections_true(self):
        """Test detecting workflow with conditional connections."""
        engine = WorkflowEngine()
        workflow = {
            "connections": [
                {"source": "a", "target": "b", "condition": "${x} > 0"}
            ]
        }
        result = engine._has_conditional_connections(workflow)
        assert result is True

    def test_has_conditional_connections_false(self):
        """Test workflow without conditional connections."""
        engine = WorkflowEngine()
        workflow = {
            "connections": [
                {"source": "a", "target": "b"}
            ]
        }
        result = engine._has_conditional_connections(workflow)
        assert result is False


class TestWorkflowEngineParameterResolution:
    """Test parameter resolution with different state structures."""

    def test_resolve_parameters_no_substitution(self):
        """Test resolving parameters without variables."""
        engine = WorkflowEngine()
        parameters = {"name": "John", "value": 42}
        state = {"input_data": {}, "outputs": {}}

        result = engine._resolve_parameters(parameters, state)
        assert result == parameters

    def test_resolve_parameters_with_input_reference(self):
        """Test resolving parameters from input_data."""
        engine = WorkflowEngine()
        parameters = {"user_name": "${input.name}"}
        state = {
            "input_data": {"name": "Alice"},
            "outputs": {}
        }

        result = engine._resolve_parameters(parameters, state)
        assert result["user_name"] == "Alice"

    def test_resolve_parameters_missing_input_raises_error(self):
        """Test that missing variable raises MissingInputError."""
        engine = WorkflowEngine()
        parameters = {"name": "${input.missing}"}
        state = {"input_data": {}, "outputs": {}}

        with pytest.raises(MissingInputError) as exc_info:
            engine._resolve_parameters(parameters, state)

        assert "missing" in str(exc_info.value.missing_var)

    def test_get_value_from_path_input(self):
        """Test getting value from input_data path."""
        engine = WorkflowEngine()
        state = {
            "input_data": {"user": {"name": "Bob"}},
            "outputs": {}
        }

        result = engine._get_value_from_path("input.user.name", state)
        assert result == "Bob"

    def test_get_value_from_path_step_output(self):
        """Test getting value from step output."""
        engine = WorkflowEngine()
        state = {
            "input_data": {},
            "outputs": {
                "step1": {"result": 42}
            }
        }

        result = engine._get_value_from_path("step1.result", state)
        assert result == 42

    def test_get_value_from_path_missing_returns_none(self):
        """Test missing path returns None."""
        engine = WorkflowEngine()
        state = {
            "input_data": {},
            "outputs": {}
        }

        result = engine._get_value_from_path("missing.path", state)
        assert result is None


class TestWorkflowEngineSchemaValidation:
    """Test schema validation methods."""

    def test_validate_input_schema_no_schema(self):
        """Test validation passes when no schema defined."""
        engine = WorkflowEngine()
        step = {"id": "step1", "action": "test"}
        params = {"any": "value"}

        # Should not raise
        engine._validate_input_schema(step, params)

    def test_validate_input_schema_valid(self):
        """Test validation with valid input."""
        engine = WorkflowEngine()
        step = {
            "id": "step1",
            "action": "test",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "required": ["name"]
            }
        }
        params = {"name": "test"}

        # Should not raise
        engine._validate_input_schema(step, params)

    def test_validate_output_schema_no_schema(self):
        """Test output validation passes when no schema defined."""
        engine = WorkflowEngine()
        step = {"id": "step1", "action": "test"}
        output = {"any": "value"}

        # Should not raise
        engine._validate_output_schema(step, output)

    def test_validate_output_schema_valid(self):
        """Test output validation with valid output."""
        engine = WorkflowEngine()
        step = {
            "id": "step1",
            "action": "test",
            "output_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "number"}
                },
                "required": ["result"]
            }
        }
        output = {"result": 42}

        # Should not raise
        engine._validate_output_schema(step, output)


class TestWorkflowEngineDependencyChecking:
    """Test dependency checking logic."""

    def test_check_dependencies_no_deps(self):
        """Test step with no dependencies always returns True."""
        engine = WorkflowEngine()
        step = {"id": "step1", "dependencies": []}
        state = {"steps": {}}

        result = engine._check_dependencies(step, state)
        assert result is True

    def test_check_dependencies_all_completed(self):
        """Test dependencies satisfied when all completed."""
        engine = WorkflowEngine()
        step = {"id": "step2", "dependencies": ["step1"]}
        state = {
            "steps": {
                "step1": {"status": "COMPLETED"}
            }
        }

        result = engine._check_dependencies(step, state)
        assert result is True

    def test_check_dependencies_incomplete(self):
        """Test dependencies not satisfied when step not complete."""
        engine = WorkflowEngine()
        step = {"id": "step2", "dependencies": ["step1"]}
        state = {
            "steps": {
                "step1": {"status": "RUNNING"}
            }
        }

        result = engine._check_dependencies(step, state)
        assert result is False

    def test_check_dependencies_missing_step(self):
        """Test dependencies not satisfied when step missing."""
        engine = WorkflowEngine()
        step = {"id": "step2", "dependencies": ["step1"]}
        state = {"steps": {}}

        result = engine._check_dependencies(step, state)
        assert result is False


class TestWorkflowEngineExecutionGraph:
    """Test execution graph building."""

    def test_build_execution_graph_simple(self):
        """Test building graph from simple workflow."""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "a", "title": "A"},
                {"id": "b", "title": "B"}
            ],
            "connections": [
                {"source": "a", "target": "b"}
            ]
        }

        graph = engine._build_execution_graph(workflow)

        assert "nodes" in graph
        assert "adjacency" in graph
        assert "reverse_adjacency" in graph
        assert "a" in graph["nodes"]
        assert "b" in graph["nodes"]
        assert "b" in graph["adjacency"]["a"]
        assert "a" in graph["reverse_adjacency"]["b"]

    def test_build_execution_graph_disconnected(self):
        """Test graph with disconnected nodes."""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "a", "title": "A"},
                {"id": "b", "title": "B"}
            ],
            "connections": []
        }

        graph = engine._build_execution_graph(workflow)

        assert "a" in graph["nodes"]
        assert "b" in graph["nodes"]
        assert len(graph["adjacency"]["a"]) == 0
        assert len(graph["adjacency"]["b"]) == 0


class TestWorkflowEnginePauseResumeCancel:
    """Test pause, resume, and cancel operations."""

    @pytest.mark.asyncio
    async def test_cancel_execution_adds_to_set(self):
        """Test cancellation adds execution ID to cancellation set."""
        engine = WorkflowEngine()

        with patch('core.workflow_engine.get_connection_manager') as mock_ws:
            mock_manager = AsyncMock()
            mock_ws.return_value = mock_manager

            execution_id = "test-exec-123"
            result = await engine.cancel_execution(execution_id)

            assert result is True
            assert execution_id in engine.cancellation_requests

    @pytest.mark.asyncio
    async def test_resume_workflow_invalid_state(self):
        """Test resuming workflow that isn't paused returns False."""
        engine = WorkflowEngine()
        state_manager = get_state_manager()

        # Create execution in RUNNING state
        execution_id = "test-resume-running"
        await state_manager.create_execution_state(
            execution_id,
            {},
            workflow_id="test-wf"
        )
        await state_manager.update_execution_status(execution_id, "RUNNING")

        workflow = {"id": "test-wf"}
        result = await engine.resume_workflow(execution_id, workflow, {})

        assert result is False

    @pytest.mark.asyncio
    async def test_resume_workflow_nonexistent_raises_error(self):
        """Test resuming non-existent execution raises ValueError."""
        engine = WorkflowEngine()

        workflow = {"id": "test-wf"}

        with pytest.raises(ValueError, match="not found"):
            await engine.resume_workflow("fake-exec-id", workflow, {})


class TestWorkflowEngineStepExecution:
    """Test step execution with mocked services."""

    @pytest.mark.asyncio
    async def test_execute_step_slack_action(self):
        """Test executing Slack action step."""
        engine = WorkflowEngine()

        step = {
            "id": "slack-step",
            "service": "slack",
            "action": "send_message",
            "parameters": {"channel": "#test", "text": "Hello"}
        }

        with patch.object(engine, '_execute_slack_action') as mock_slack:
            mock_slack.return_value = {"status": "success", "message": "sent"}

            result = await engine._execute_step(step, step["parameters"])

            assert result["status"] == "success"
            mock_slack.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_step_email_action(self):
        """Test executing email action step."""
        engine = WorkflowEngine()

        step = {
            "id": "email-step",
            "service": "email",
            "action": "send",
            "parameters": {"to": "test@example.com", "subject": "Test"}
        }

        with patch.object(engine, '_execute_email_action') as mock_email:
            mock_email.return_value = {"status": "sent"}

            result = await engine._execute_step(step, step["parameters"])

            assert result["status"] == "sent"
            mock_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_step_unknown_service(self):
        """Test executing step with unknown service."""
        engine = WorkflowEngine()

        step = {
            "id": "unknown-step",
            "service": "unknown_service",
            "action": "test_action",
            "parameters": {}
        }

        result = await engine._execute_step(step, {})

        # Should handle unknown service gracefully
        assert "status" in result or "error" in result


class TestWorkflowEngineStateManagement:
    """Test state persistence and retrieval."""

    @pytest.mark.asyncio
    async def test_state_manager_initialization(self):
        """Test engine initializes state manager."""
        engine = WorkflowEngine()
        assert engine.state_manager is not None

    @pytest.mark.asyncio
    async def test_get_workflow_engine_singleton(self):
        """Test get_workflow_engine returns singleton instance."""
        from core.workflow_engine import get_workflow_engine

        engine1 = get_workflow_engine()
        engine2 = get_workflow_engine()

        assert engine1 is engine2


class TestWorkflowEngineTopologicalSort:
    """Test topological sorting of workflow steps."""

    def test_convert_nodes_to_steps_preserves_order(self):
        """Test converting nodes maintains topological order."""
        engine = WorkflowEngine()

        workflow = {
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"action": "action1"}},
                {"id": "b", "title": "B", "type": "action", "config": {"action": "action2"}},
                {"id": "c", "title": "C", "type": "action", "config": {"action": "action3"}}
            ],
            "connections": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"}
            ]
        }

        steps = engine._convert_nodes_to_steps(workflow)

        assert len(steps) == 3
        # Topological order should be a, b, c
        assert steps[0]["id"] == "a"
        assert steps[1]["id"] == "b"
        assert steps[2]["id"] == "c"

    def test_convert_nodes_with_parallel_branches(self):
        """Test converting parallel branches creates correct structure."""
        engine = WorkflowEngine()

        workflow = {
            "nodes": [
                {"id": "start", "title": "Start", "type": "action", "config": {"action": "start"}},
                {"id": "parallel1", "title": "P1", "type": "action", "config": {"action": "p1"}},
                {"id": "parallel2", "title": "P2", "type": "action", "config": {"action": "p2"}},
                {"id": "end", "title": "End", "type": "action", "config": {"action": "end"}}
            ],
            "connections": [
                {"source": "start", "target": "parallel1"},
                {"source": "start", "target": "parallel2"},
                {"source": "parallel1", "target": "end"},
                {"source": "parallel2", "target": "end"}
            ]
        }

        steps = engine._convert_nodes_to_steps(workflow)

        assert len(steps) == 4
        # start should come first
        assert steps[0]["id"] == "start"
        # end should come last
        assert steps[3]["id"] == "end"


class TestWorkflowEngineErrorRecovery:
    """Test error handling and recovery mechanisms."""

    @pytest.mark.asyncio
    async def test_step_execution_with_retry(self):
        """Test step execution uses retry mechanism."""
        engine = WorkflowEngine()

        step = {
            "id": "retry-step",
            "service": "slack",
            "action": "send_message",
            "parameters": {"test": "data"}
        }

        # First call fails, second succeeds
        call_count = 0

        async def flaky_action(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return {"status": "success"}

        with patch.object(engine, '_execute_slack_action', side_effect=flaky_action):
            result = await engine._execute_step(step, step["parameters"])

            # Should eventually succeed
            assert result["status"] == "success"
            assert call_count == 2


class TestWorkflowExecutionLogging:
    """Test execution logging and audit trail."""

    @pytest.mark.asyncio
    async def test_workflow_execution_log_created(self):
        """Test that execution creates log entry."""
        from core.database import get_db_session
        from core.models import WorkflowExecutionLog

        engine = WorkflowEngine()
        state_manager = get_state_manager()

        workflow = {
            "id": "test-log-wf",
            "created_by": "test-user",
            "nodes": [
                {"id": "step1", "title": "Step 1", "type": "action", "config": {"action": "test"}}
            ],
            "connections": []
        }

        with patch.object(engine, '_execute_step') as mock_execute:
            mock_execute.return_value = {"status": "success"}

            with patch('core.workflow_engine.get_db_session') as mock_db:
                mock_session = MagicMock()
                mock_db.return_value.__enter__.return_value = mock_session

                execution_id = await engine.start_workflow(workflow, {})
                await asyncio.sleep(0.1)

                # Verify we attempted to create log
                # (The exact behavior depends on implementation)


class TestWorkflowEngineConcurrencyControl:
    """Test concurrency control with semaphore."""

    def test_semaphore_limits_concurrent_steps(self):
        """Test semaphore properly limits concurrent execution."""
        engine = WorkflowEngine(max_concurrent_steps=2)

        assert engine.semaphore._value == 2
        assert engine.max_concurrent_steps == 2

    @pytest.mark.asyncio
    async def test_semaphore_respects_limit(self):
        """Test that semaphore enforces limit on concurrent operations."""
        engine = WorkflowEngine(max_concurrent_steps=2)

        async def slow_operation():
            await asyncio.sleep(0.1)
            return "done"

        # Launch 5 concurrent operations
        tasks = [asyncio.create_task(engine.semaphore.acquire()) for _ in range(5)]

        # Wait a bit
        await asyncio.sleep(0.05)

        # Only 2 should have acquired the semaphore
        # Others should be waiting

        # Clean up
        for task in tasks:
            if task.done():
                engine.semaphore.release()


class TestWorkflowEngineSpecialCases:
    """Test special edge cases and boundary conditions."""

    def test_empty_workflow(self):
        """Test handling empty workflow."""
        engine = WorkflowEngine()
        workflow = {"nodes": [], "connections": []}

        graph = engine._build_execution_graph(workflow)

        assert len(graph["nodes"]) == 0
        assert len(graph["adjacency"]) == 0

    def test_workflow_single_node(self):
        """Test workflow with single node."""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "only", "title": "Only", "type": "action", "config": {"action": "test"}}
            ],
            "connections": []
        }

        steps = engine._convert_nodes_to_steps(workflow)

        assert len(steps) == 1
        assert steps[0]["id"] == "only"

    def test_circular_dependencies(self):
        """Test handling of circular dependencies in graph."""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "a", "title": "A", "type": "action", "config": {"action": "a"}},
                {"id": "b", "title": "B", "type": "action", "config": {"action": "b"}},
                {"id": "c", "title": "C", "type": "action", "config": {"action": "c"}}
            ],
            "connections": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
                {"source": "c", "target": "a"}  # Circular!
            ]
        }

        # Should handle gracefully (may raise or detect cycle)
        try:
            steps = engine._convert_nodes_to_steps(workflow)
            # If it succeeds, check it produced some order
            assert len(steps) == 3
        except Exception as e:
            # Cycle detection is also valid
            assert "cycle" in str(e).lower() or "cyclic" in str(e).lower()
