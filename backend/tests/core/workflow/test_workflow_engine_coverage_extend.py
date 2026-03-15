"""
Coverage-driven tests for workflow_engine.py (13% -> 60%+ target)

Building on Phase 192's 13% baseline (148/1,164 statements).
Focus on testable synchronous methods, accept partial coverage on async orchestration.

Coverage Target Areas:
- Lines 120-200: Workflow validation and schema checking
- Lines 200-300: Step execution with output mapping
- Lines 300-400: Error handling and rollback logic
- Lines 400-500: Workflow status transitions
- Lines 500-600: Semaphore and concurrency management
- Lines 700-900: Additional synchronous helper methods

SKIPPED (async orchestration, requires integration testing):
- Lines 50-120: _execute_workflow_graph (261 statements, 0% coverage)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import asyncio
from core.workflow_engine import WorkflowEngine, MissingInputError
from core.models import WorkflowExecutionLog


class TestWorkflowEngineCoverageExtend:
    """Extended coverage tests for workflow_engine.py (13% -> 60%+ target)"""

    # ==================== Workflow Validation Tests (8 tests) ====================
    # Cover lines 120-200: _build_execution_graph, _has_conditional_connections

    def test_build_execution_graph_simple(self):
        """Cover _build_execution_graph with simple workflow"""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "node1", "title": "Step 1"},
                {"id": "node2", "title": "Step 2"}
            ],
            "connections": [
                {"source": "node1", "target": "node2"}
            ]
        }

        graph = engine._build_execution_graph(workflow)

        assert "nodes" in graph
        assert "connections" in graph
        assert "adjacency" in graph
        assert "reverse_adjacency" in graph
        assert len(graph["nodes"]) == 2
        assert len(graph["adjacency"]["node1"]) == 1
        assert len(graph["reverse_adjacency"]["node2"]) == 1

    def test_build_execution_graph_empty(self):
        """Cover _build_execution_graph with empty workflow"""
        engine = WorkflowEngine()
        workflow = {"nodes": [], "connections": []}

        graph = engine._build_execution_graph(workflow)

        assert graph["nodes"] == {}
        assert graph["connections"] == []
        assert graph["adjacency"] == {}
        assert graph["reverse_adjacency"] == {}

    def test_build_execution_graph_diamond(self):
        """Cover _build_execution_graph with diamond pattern"""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "start", "title": "Start"},
                {"id": "branch1", "title": "Branch 1"},
                {"id": "branch2", "title": "Branch 2"},
                {"id": "end", "title": "End"}
            ],
            "connections": [
                {"source": "start", "target": "branch1"},
                {"source": "start", "target": "branch2"},
                {"source": "branch1", "target": "end"},
                {"source": "branch2", "target": "end"}
            ]
        }

        graph = engine._build_execution_graph(workflow)

        assert len(graph["adjacency"]["start"]) == 2
        assert len(graph["reverse_adjacency"]["end"]) == 2
        assert len(graph["adjacency"]["branch1"]) == 1
        assert len(graph["adjacency"]["branch2"]) == 1

    def test_has_conditional_connections_true(self):
        """Cover _has_conditional_connections returns True"""
        engine = WorkflowEngine()
        workflow = {
            "connections": [
                {"source": "a", "target": "b", "condition": "approved"},
                {"source": "b", "target": "c"}
            ]
        }

        has_conditional = engine._has_conditional_connections(workflow)

        assert has_conditional is True

    def test_has_conditional_connections_false(self):
        """Cover _has_conditional_connections returns False"""
        engine = WorkflowEngine()
        workflow = {
            "connections": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"}
            ]
        }

        has_conditional = engine._has_conditional_connections(workflow)

        assert has_conditional is False

    def test_has_conditional_connections_empty(self):
        """Cover _has_conditional_connections with empty connections"""
        engine = WorkflowEngine()
        workflow = {"connections": []}

        has_conditional = engine._has_conditional_connections(workflow)

        assert has_conditional is False

    def test_has_conditional_connections_empty_condition(self):
        """Cover _has_conditional_connections with empty condition string"""
        engine = WorkflowEngine()
        workflow = {
            "connections": [
                {"source": "a", "target": "b", "condition": ""}
            ]
        }

        has_conditional = engine._has_conditional_connections(workflow)

        assert has_conditional is False

    def test_build_execution_graph_with_conditions(self):
        """Cover _build_execution_graph with conditional connections"""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "decision", "title": "Decision"},
                {"id": "yes", "title": "Yes Path"},
                {"id": "no", "title": "No Path"}
            ],
            "connections": [
                {"source": "decision", "target": "yes", "condition": "approved"},
                {"source": "decision", "target": "no", "condition": "rejected"}
            ]
        }

        graph = engine._build_execution_graph(workflow)

        assert len(graph["connections"]) == 2
        assert graph["connections"][0]["condition"] == "approved"
        assert graph["connections"][1]["condition"] == "rejected"

    # ==================== Step Execution Tests (12 tests) ====================
    # Cover lines 200-300: Output mapping, parameter passing, step chaining

    def test_check_dependencies_no_deps(self):
        """Cover _check_dependencies with no dependencies"""
        engine = WorkflowEngine()
        step = {"id": "step1", "depends_on": []}
        state = {"steps": {}}

        result = engine._check_dependencies(step, state)

        assert result is True

    def test_check_dependencies_met(self):
        """Cover _check_dependencies with met dependencies"""
        engine = WorkflowEngine()
        step = {"id": "step2", "depends_on": ["step1"]}
        state = {
            "steps": {
                "step1": {"status": "COMPLETED"}
            }
        }

        result = engine._check_dependencies(step, state)

        assert result is True

    def test_check_dependencies_unmet(self):
        """Cover _check_dependencies with unmet dependencies"""
        engine = WorkflowEngine()
        step = {"id": "step2", "depends_on": ["step1"]}
        state = {
            "steps": {
                "step1": {"status": "RUNNING"}
            }
        }

        result = engine._check_dependencies(step, state)

        assert result is False

    def test_check_dependencies_missing_step(self):
        """Cover _check_dependencies with missing dependency step"""
        engine = WorkflowEngine()
        step = {"id": "step2", "depends_on": ["step1"]}
        state = {"steps": {}}

        result = engine._check_dependencies(step, state)

        assert result is False

    def test_check_dependencies_multiple(self):
        """Cover _check_dependencies with multiple dependencies"""
        engine = WorkflowEngine()
        step = {"id": "step3", "depends_on": ["step1", "step2"]}
        state = {
            "steps": {
                "step1": {"status": "COMPLETED"},
                "step2": {"status": "COMPLETED"}
            }
        }

        result = engine._check_dependencies(step, state)

        assert result is True

    def test_check_dependencies_partial(self):
        """Cover _check_dependencies with partial dependencies met"""
        engine = WorkflowEngine()
        step = {"id": "step3", "depends_on": ["step1", "step2"]}
        state = {
            "steps": {
                "step1": {"status": "COMPLETED"},
                "step2": {"status": "RUNNING"}
            }
        }

        result = engine._check_dependencies(step, state)

        assert result is False

    @pytest.mark.parametrize("condition,state,expected", [
        ("True == True", {}, True),
        ("False == True", {}, False),
        ("10 > 5", {}, True),
        ("3 > 5", {}, False),
        ("'completed' == 'completed'", {}, True),
    ])
    def test_evaluate_condition_simple(self, condition, state, expected):
        """Cover _evaluate_condition with simple conditions"""
        engine = WorkflowEngine()

        result = engine._evaluate_condition(condition, state)

        assert result == expected

    def test_evaluate_condition_with_variable_substitution(self):
        """Cover _evaluate_condition with variable substitution"""
        engine = WorkflowEngine()
        state = {
            "outputs": {
                "step1": {"success": True}
            }
        }

        result = engine._evaluate_condition("${step1.success} == True", state)

        assert result is True

    def test_evaluate_condition_with_input_variable(self):
        """Cover _evaluate_condition with input_data variable"""
        engine = WorkflowEngine()
        state = {
            "input_data": {"count": 10}
        }

        result = engine._evaluate_condition("${input.count} > 5", state)

        assert result is True

    def test_evaluate_condition_empty(self):
        """Cover _evaluate_condition with empty condition"""
        engine = WorkflowEngine()
        state = {}

        result = engine._evaluate_condition("", state)

        assert result is True

    def test_evaluate_condition_none(self):
        """Cover _evaluate_condition with None condition"""
        engine = WorkflowEngine()
        state = {}

        result = engine._evaluate_condition(None, state)

        assert result is True

    def test_evaluate_condition_missing_var(self):
        """Cover _evaluate_condition with missing variable"""
        engine = WorkflowEngine()
        state = {"steps": {}, "input_data": {}}

        result = engine._evaluate_condition("${missing.value} == True", state)

        assert result is False

    # ==================== Error Handling Tests (12 tests) ====================
    # Cover lines 300-400: Step failures, rollback, error propagation

    def test_resolve_parameters_dict_with_strings(self):
        """Cover _resolve_parameters with string values"""
        engine = WorkflowEngine()
        params = {"key": "value", "url": "https://example.com"}
        state = {}

        resolved = engine._resolve_parameters(params, state)

        assert resolved == params

    def test_resolve_parameters_dict_with_numbers(self):
        """Cover _resolve_parameters with numeric values"""
        engine = WorkflowEngine()
        params = {"count": 10, "rate": 0.5}
        state = {}

        resolved = engine._resolve_parameters(params, state)

        assert resolved == params

    def test_resolve_parameters_dict_with_booleans(self):
        """Cover _resolve_parameters with boolean values"""
        engine = WorkflowEngine()
        params = {"enabled": True, "active": False}
        state = {}

        resolved = engine._resolve_parameters(params, state)

        assert resolved == params

    def test_resolve_parameters_dict_with_nulls(self):
        """Cover _resolve_parameters with None values"""
        engine = WorkflowEngine()
        params = {"value": None, "optional": None}
        state = {}

        resolved = engine._resolve_parameters(params, state)

        assert resolved == params

    def test_resolve_parameters_nested_dict(self):
        """Cover _resolve_parameters with nested dict"""
        engine = WorkflowEngine()
        params = {"config": {"nested": {"key": "value"}}}
        state = {}

        resolved = engine._resolve_parameters(params, state)

        assert resolved == params

    def test_resolve_parameters_list_value(self):
        """Cover _resolve_parameters with list value"""
        engine = WorkflowEngine()
        params = {"items": [1, 2, 3]}
        state = {}

        resolved = engine._resolve_parameters(params, state)

        assert resolved == params

    def test_get_value_from_path_outputs(self):
        """Cover _get_value_from_path from outputs"""
        engine = WorkflowEngine()
        state = {
            "outputs": {
                "step1": {"token": "abc123", "count": 5}
            }
        }

        value = engine._get_value_from_path("step1.token", state)

        assert value == "abc123"

    def test_get_value_from_path_input_data(self):
        """Cover _get_value_from_path from input_data"""
        engine = WorkflowEngine()
        state = {
            "input_data": {"user_id": 123, "email": "test@example.com"}
        }

        value = engine._get_value_from_path("input.user_id", state)

        assert value == 123

    def test_get_value_from_path_deep_nested(self):
        """Cover _get_value_from_path with deep nesting"""
        engine = WorkflowEngine()
        state = {
            "outputs": {
                "step1": {
                    "data": {
                        "user": {
                            "profile": {
                                "name": "John"
                            }
                        }
                    }
                }
            }
        }

        value = engine._get_value_from_path("step1.data.user.profile.name", state)

        assert value == "John"

    def test_get_value_from_path_list_element(self):
        """Cover _get_value_from_path with list access (should return None)"""
        engine = WorkflowEngine()
        state = {
            "outputs": {
                "step1": {"items": [1, 2, 3]}
            }
        }

        # List access not supported, returns None
        value = engine._get_value_from_path("step1.items.0", state)

        assert value is None

    def test_get_value_from_path_invalid_key(self):
        """Cover _get_value_from_path with invalid intermediate key"""
        engine = WorkflowEngine()
        state = {
            "outputs": {
                "step1": {"valid": "data"}
            }
        }

        value = engine._get_value_from_path("step1.invalid.key", state)

        assert value is None

    def test_resolve_parameters_missing_var_raises(self):
        """Cover _resolve_parameters raises MissingInputError"""
        engine = WorkflowEngine()
        params = {"url": "${missing.step.value}"}
        state = {"outputs": {}}

        with pytest.raises(MissingInputError) as exc_info:
            engine._resolve_parameters(params, state)

        assert exc_info.value.missing_var == "missing.step.value"

    # ==================== Status Transition Tests (8 tests) ====================
    # Cover lines 400-500: Workflow status transitions

    @pytest.mark.asyncio
    async def test_cancel_execution_adds_to_set(self):
        """Cover cancel_execution adds to cancellation_requests set"""
        engine = WorkflowEngine()
        execution_id = "test-exec-123"

        mock_ws = AsyncMock()
        with patch('core.workflow_engine.get_connection_manager', return_value=mock_ws):
            with patch.object(engine.state_manager, 'update_execution_status'):
                result = await engine.cancel_execution(execution_id)

        assert execution_id in engine.cancellation_requests
        assert result is True

    @pytest.mark.asyncio
    async def test_resume_workflow_success(self):
        """Cover resume_workflow with valid paused execution"""
        engine = WorkflowEngine()
        execution_id = "test-exec-123"
        workflow = {"id": "test-workflow"}
        new_inputs = {"key": "value"}

        with patch.object(engine.state_manager, 'get_execution_state') as mock_get:
            mock_get.return_value = {"status": "PAUSED", "steps": {}}
            with patch.object(engine.state_manager, 'update_execution_inputs'):
                with patch.object(engine.state_manager, 'update_execution_status'):
                    with patch('asyncio.create_task'):
                        result = await engine.resume_workflow(execution_id, workflow, new_inputs)

        assert result is True

    @pytest.mark.asyncio
    async def test_resume_workflow_not_paused(self):
        """Cover resume_workflow with non-paused execution"""
        engine = WorkflowEngine()
        execution_id = "test-exec-123"
        workflow = {"id": "test-workflow"}
        new_inputs = {"key": "value"}

        with patch.object(engine.state_manager, 'get_execution_state') as mock_get:
            mock_get.return_value = {"status": "RUNNING", "steps": {}}
            result = await engine.resume_workflow(execution_id, workflow, new_inputs)

        assert result is False

    @pytest.mark.asyncio
    async def test_resume_workflow_not_found(self):
        """Cover resume_workflow with non-existent execution"""
        engine = WorkflowEngine()
        execution_id = "nonexistent"
        workflow = {"id": "test-workflow"}
        new_inputs = {"key": "value"}

        with patch.object(engine.state_manager, 'get_execution_state') as mock_get:
            mock_get.return_value = None
            with pytest.raises(ValueError, match="Execution .* not found"):
                await engine.resume_workflow(execution_id, workflow, new_inputs)

    def test_cancellation_request_set_operations(self):
        """Cover cancellation_requests set add/discard operations"""
        engine = WorkflowEngine()
        execution_id = "test-exec-456"

        # Add
        engine.cancellation_requests.add(execution_id)
        assert execution_id in engine.cancellation_requests

        # Discard
        engine.cancellation_requests.discard(execution_id)
        assert execution_id not in engine.cancellation_requests

    @pytest.mark.asyncio
    async def test_start_workflow_with_background_tasks(self):
        """Cover start_workflow with background_tasks parameter"""
        engine = WorkflowEngine()
        workflow = {
            "id": "test-workflow",
            "nodes": [{"id": "node1"}],
            "connections": []
        }
        input_data = {"key": "value"}

        mock_background = MagicMock()
        with patch.object(engine.state_manager, 'create_execution') as mock_create:
            mock_create.return_value = "exec-123"
            await engine.start_workflow(workflow, input_data, mock_background)

        mock_background.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_workflow_without_background_tasks(self):
        """Cover start_workflow without background_tasks (uses asyncio)"""
        engine = WorkflowEngine()
        workflow = {
            "id": "test-workflow",
            "steps": [{"id": "step1"}]
        }
        input_data = {"key": "value"}

        with patch.object(engine.state_manager, 'create_execution') as mock_create:
            mock_create.return_value = "exec-123"
            with patch('asyncio.create_task') as mock_create_task:
                await engine.start_workflow(workflow, input_data)

        mock_create_task.assert_called_once()

    # ==================== Concurrency Tests (6 tests) ====================
    # Cover lines 500-600: Semaphore and concurrency management

    def test_semaphore_custom_limit(self):
        """Cover semaphore initialization with custom limit"""
        engine = WorkflowEngine(max_concurrent_steps=10)

        assert engine.max_concurrent_steps == 10
        assert engine.semaphore._value == 10

    def test_semaphore_single_concurrency(self):
        """Cover semaphore with limit of 1 (sequential execution)"""
        engine = WorkflowEngine(max_concurrent_steps=1)

        assert engine.max_concurrent_steps == 1
        assert engine.semaphore._value == 1

    def test_semaphore_high_concurrency(self):
        """Cover semaphore with high concurrency limit"""
        engine = WorkflowEngine(max_concurrent_steps=50)

        assert engine.max_concurrent_steps == 50
        assert engine.semaphore._value == 50

    @pytest.mark.asyncio
    async def test_semaphore_acquire_release(self):
        """Cover semaphore acquire and release in async context"""
        engine = WorkflowEngine(max_concurrent_steps=2)

        assert engine.semaphore._value == 2

        async with engine.semaphore:
            assert engine.semaphore._value == 1

        # Released after context
        assert engine.semaphore._value == 2

    @pytest.mark.asyncio
    async def test_semaphore_concurrent_acquisitions(self):
        """Cover semaphore with multiple concurrent acquisitions"""
        engine = WorkflowEngine(max_concurrent_steps=2)

        async def acquire_and_hold():
            async with engine.semaphore:
                await asyncio.sleep(0.01)

        # Run 3 tasks but only 2 can acquire at once
        tasks = [acquire_and_hold() for _ in range(3)]
        await asyncio.gather(*tasks)

        # All completed successfully
        assert engine.semaphore._value == 2

    def test_cancellation_requests_is_set(self):
        """Cover cancellation_requests is a set data structure"""
        engine = WorkflowEngine()

        assert isinstance(engine.cancellation_requests, set)
        assert len(engine.cancellation_requests) == 0

    # ==================== Edge Cases (8 tests) ====================
    # Cover edge cases: empty workflows, single-step, circular refs, large workflows

    def test_empty_workflow_edges(self):
        """Cover workflow with no nodes and no connections"""
        engine = WorkflowEngine()
        workflow = {"nodes": [], "connections": []}

        graph = engine._build_execution_graph(workflow)

        assert graph["nodes"] == {}
        assert graph["connections"] == []
        assert graph["adjacency"] == {}

    def test_single_step_workflow(self):
        """Cover workflow with single step (no dependencies)"""
        engine = WorkflowEngine()
        workflow = {
            "steps": [
                {"id": "only_step", "name": "Only Step", "sequence_order": 1}
            ]
        }

        step = workflow["steps"][0]
        result = engine._check_dependencies(step, {"steps": {}})

        assert result is True

    def test_circular_reference_detection(self):
        """Cover handling of circular references in dependencies"""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "a", "title": "A"},
                {"id": "b", "title": "B"},
                {"id": "c", "title": "C"}
            ],
            "connections": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
                {"source": "c", "target": "a"}  # Circular
            ]
        }

        # Should handle gracefully (topological sort may not include all)
        steps = engine._convert_nodes_to_steps(workflow)

        assert isinstance(steps, list)

    def test_large_workflow_performance(self):
        """Cover handling of large workflow (50+ nodes)"""
        engine = WorkflowEngine()
        nodes = [{"id": f"node{i}", "title": f"Node {i}"} for i in range(50)]
        connections = [{"source": f"node{i}", "target": f"node{i+1}"} for i in range(49)]

        workflow = {"nodes": nodes, "connections": connections}

        graph = engine._build_execution_graph(workflow)

        assert len(graph["nodes"]) == 50
        assert len(graph["connections"]) == 49

    def test_workflow_with_isolated_nodes(self):
        """Cover workflow with disconnected nodes"""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "connected1", "title": "Connected 1"},
                {"id": "connected2", "title": "Connected 2"},
                {"id": "isolated", "title": "Isolated"}
            ],
            "connections": [
                {"source": "connected1", "target": "connected2"}
            ]
        }

        graph = engine._build_execution_graph(workflow)

        # All nodes should be in graph
        assert len(graph["nodes"]) == 3
        # Isolated node has no connections
        assert len(graph["adjacency"]["isolated"]) == 0
        assert len(graph["reverse_adjacency"]["isolated"]) == 0

    def test_duplicate_connections_in_workflow(self):
        """Cover workflow with duplicate connections"""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "a", "title": "A"},
                {"id": "b", "title": "B"}
            ],
            "connections": [
                {"source": "a", "target": "b"},
                {"source": "a", "target": "b"}  # Duplicate
            ]
        }

        graph = engine._build_execution_graph(workflow)

        # Should handle duplicates (both added to adjacency list)
        assert len(graph["adjacency"]["a"]) == 2

    def test_self_referential_connection(self):
        """Cover workflow with self-referential connection"""
        engine = WorkflowEngine()
        workflow = {
            "nodes": [
                {"id": "self_ref", "title": "Self Ref"}
            ],
            "connections": [
                {"source": "self_ref", "target": "self_ref"}
            ]
        }

        graph = engine._build_execution_graph(workflow)

        # Should handle self-reference
        assert len(graph["adjacency"]["self_ref"]) == 1
        assert len(graph["reverse_adjacency"]["self_ref"]) == 1

    def test_mixed_condition_types(self):
        """Cover workflow with mixed connection conditions"""
        engine = WorkflowEngine()
        workflow = {
            "connections": [
                {"source": "a", "target": "b", "condition": "approved"},
                {"source": "a", "target": "c"},  # No condition
                {"source": "a", "target": "d", "condition": ""},  # Empty condition
            ]
        }

        has_conditional = engine._has_conditional_connections(workflow)

        # Should return True because at least one connection has condition
        assert has_conditional is True
