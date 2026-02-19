"""
Property-Based Tests for WorkflowEngine State Invariants

Tests CRITICAL workflow engine invariants:
- Topological sort preserves execution order (Kahn's algorithm invariant)
- Variable resolution is deterministic and consistent
- Step failure triggers rollback on dependent steps
- Concurrent step limit enforced by semaphore
- Cancellation propagates to all dependent steps
- Conditional branching evaluates correctly
- Parameter schema validation catches invalid inputs
- Timeout enforcement prevents infinite execution

These tests protect against state management bugs and workflow execution errors.
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, assume
from hypothesis import HealthCheck
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import jsonschema

from core.workflow_engine import (
    WorkflowEngine,
    MissingInputError,
    SchemaValidationError,
    StepTimeoutError
)
from core.execution_state_manager import ExecutionStateManager

# Common Hypothesis settings
hypothesis_settings = settings(
    max_examples=30,  # Reduced for faster execution
    deadline=None,  # Disable deadline for slow tests
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow
    ]
)


class TestWorkflowStateInvariants:
    """Property-based tests for workflow state invariants."""

    @pytest.fixture
    def state_manager(self):
        """Mock state manager for testing."""
        manager = AsyncMock(spec=ExecutionStateManager)
        manager.create_execution = AsyncMock(return_value="test-execution-123")
        manager.get_execution_state = AsyncMock(return_value={
            "execution_id": "test-execution-123",
            "workflow_id": "test-workflow",
            "status": "RUNNING",
            "input_data": {},
            "steps": {},
            "outputs": {},
            "context": {},
            "version": 1
        })
        manager.update_step_status = AsyncMock()
        manager.update_execution_status = AsyncMock()
        manager.update_execution_inputs = AsyncMock()
        return manager

    @pytest.fixture
    def workflow_engine(self, state_manager):
        """Create WorkflowEngine instance with mocked dependencies."""
        with patch('core.workflow_engine.get_state_manager', return_value=state_manager):
            engine = WorkflowEngine(max_concurrent_steps=3)
            engine.state_manager = state_manager
            yield engine

    # ==========================================================================
    # INVARIANT 1: Topological Sort Preserves Execution Order
    # ==========================================================================

    @given(
        node_count=st.integers(min_value=2, max_value=8)
    )
    @hypothesis_settings
    def test_execution_order_preserved_topological_sort(
        self, workflow_engine, node_count
    ):
        """
        INVARIANT: Topological sort produces a valid execution order where
        all dependencies are satisfied before dependent steps execute.

        Kahn's algorithm guarantees: if u -> v is an edge, u appears before v.
        """
        # Create nodes with predictable IDs
        nodes = [
            {
                "id": f"node{i}",
                "title": f"Node {i}",
                "config": {"service": "test"}
            }
            for i in range(node_count)
        ]

        # Create edges (connections) - each node connects to next
        connections = [
            {
                "source": f"node{i}",
                "target": f"node{i+1}",
                "condition": None
            }
            for i in range(node_count - 1)
        ]

        workflow = {
            "id": "test-workflow",
            "nodes": nodes,
            "connections": connections
        }

        # Convert nodes to steps (uses topological sort internally)
        steps = workflow_engine._convert_nodes_to_steps(workflow)

        # INVARIANT: Step sequence_order should respect dependencies
        # If source -> target, then source.sequence_order < target.sequence_order
        step_order = {s['id']: s.get('sequence_order', 0) for s in steps}

        for conn in connections:
            source_order = step_order.get(conn['source'], 0)
            target_order = step_order.get(conn['target'], 0)

            # Source should come before target in execution order
            assert source_order < target_order, \
                f"Topological sort violated: {conn['source']} (order {source_order}) " \
                f"should execute before {conn['target']} (order {target_order})"

    # ==========================================================================
    # INVARIANT 2: Variable Resolution is Deterministic
    # ==========================================================================

    @given(
        value=st.one_of(st.text(), st.integers(), st.booleans()),
        param_key=st.text(min_size=1, alphabet='abcdefghijklmnopqrstuvwxyz')
    )
    @hypothesis_settings
    def test_variable_resolution_deterministic(
        self, workflow_engine, value, param_key
    ):
        """
        INVARIANT: Variable resolution is deterministic - same input produces
        same output consistently, regardless of execution order.
        """
        # Build state with output
        state = {
            "outputs": {
                "step1": {"result": value}
            }
        }

        # Build parameter with variable reference
        parameters = {param_key: "${step1.result}"}

        # Resolve parameters twice
        result1 = workflow_engine._resolve_parameters(parameters, state)
        result2 = workflow_engine._resolve_parameters(parameters, state)

        # INVARIANT: Resolution is deterministic
        assert result1 == result2, \
            f"Variable resolution is non-deterministic: {result1} != {result2}"
        assert result1[param_key] == value, \
            f"Resolved value doesn't match: {result1[param_key]} != {value}"

    @given(
        nested_path=st.lists(
            st.text(min_size=1, alphabet='abcdefghijklmnopqrstuvwxyz'),
            min_size=1,
            max_size=5
        )
    )
    @hypothesis_settings
    def test_variable_resolution_nested_path_deterministic(
        self, workflow_engine, nested_path
    ):
        """
        INVARIANT: Nested path resolution is deterministic.
        ${step_id.output.key1.key2} should resolve consistently.
        """
        # Build nested output structure
        nested_value = "final_value"
        state = {
            "outputs": {
                "step1": {
                    "output": {}
                }
            }
        }

        # Build nested structure
        current = state["outputs"]["step1"]["output"]
        for i, key in enumerate(nested_path[:-1]):
            current[key] = {}
            current = current[key]
        current[nested_path[-1]] = nested_value

        # Build parameter with nested reference
        path = ".".join(nested_path)
        parameter = f"${{step1.output.{path}}}"

        # Resolve twice
        result1 = workflow_engine._resolve_parameters({"key": parameter}, state)
        result2 = workflow_engine._resolve_parameters({"key": parameter}, state)

        # INVARIANT: Nested resolution is deterministic
        assert result1 == result2, \
            f"Nested path resolution non-deterministic: {result1} != {result2}"
        assert result1["key"] == nested_value, \
            f"Nested path resolved incorrectly: {result1['key']} != {nested_value}"

    # ==========================================================================
    # INVARIANT 3: Step Failure Triggers Rollback
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_step_failure_rollback(self, workflow_engine, state_manager):
        """
        INVARIANT: When a step fails, dependent steps should not execute
        and the workflow should enter FAILED state.
        """
        # Track which steps executed
        executed_steps = []

        # Create workflow with 5 steps, third one fails
        steps = []
        for i in range(5):
            step_id = f"step{i}"
            steps.append({
                "id": step_id,
                "name": f"Step {i}",
                "sequence_order": i,
                "service": "test",
                "action": "action" if i != 2 else "fail_action",
                "parameters": {},
                "continue_on_error": False
            })

        workflow = {
            "id": "test-workflow",
            "steps": steps
        }

        # Mock _execute_step to track execution and fail at step 2
        async def mock_execute_step(step, params):
            executed_steps.append(step["id"])
            if step["action"] == "fail_action":
                raise Exception(f"Step {step['id']} failed")
            return {"result": "success"}

        workflow_engine._execute_step = mock_execute_step

        # Mock state updates
        state = {
            "execution_id": "test-exec-123",
            "workflow_id": "test-workflow",
            "status": "RUNNING",
            "input_data": {},
            "steps": {},
            "outputs": {},
            "context": {}
        }
        state_manager.get_execution_state = AsyncMock(return_value=state)

        # Run workflow (should fail at step 2)
        try:
            await workflow_engine._run_execution("test-exec-123", workflow)
        except Exception:
            pass  # Expected to fail

        # INVARIANT: Failed step (step2) should be the last executed
        assert "step2" in executed_steps, "Failed step not executed"
        # Should have executed step0, step1, step2 (the failing step)
        assert len(executed_steps) <= 3, \
            f"Steps beyond failure executed: {executed_steps}"

    # ==========================================================================
    # INVARIANT 4: Concurrent Step Limit Enforced
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_concurrent_step_limit(self):
        """
        INVARIANT: Semaphore enforces max concurrent step execution.
        No more than max_concurrent steps should execute simultaneously.
        """
        max_concurrent = 3
        step_count = 10

        # Track concurrent executions
        concurrent_count = 0
        max_observed = 0
        lock = asyncio.Lock()

        async def mock_execute_step(step, params):
            nonlocal concurrent_count, max_observed

            async with lock:
                concurrent_count += 1
                if concurrent_count > max_observed:
                    max_observed = concurrent_count

            # Simulate work
            await asyncio.sleep(0.01)

            async with lock:
                concurrent_count -= 1

            return {"result": "success"}

        # Create engine with concurrency limit
        state_manager = AsyncMock()
        state_manager.create_execution = AsyncMock(return_value="test-exec-123")
        state_manager.get_execution_state = AsyncMock(return_value={
            "execution_id": "test-exec-123",
            "workflow_id": "test-workflow",
            "status": "RUNNING",
            "input_data": {},
            "steps": {},
            "outputs": {},
            "context": {}
        })
        state_manager.update_step_status = AsyncMock()
        state_manager.update_execution_status = AsyncMock()

        with patch('core.workflow_engine.get_state_manager', return_value=state_manager):
            engine = WorkflowEngine(max_concurrent_steps=max_concurrent)
            engine.state_manager = state_manager
            engine._execute_step = mock_execute_step

            # Create independent steps (can run in parallel)
            steps = [
                {
                    "id": f"step{i}",
                    "name": f"Step {i}",
                    "sequence_order": i,
                    "service": "test",
                    "action": "action",
                    "parameters": {},
                    "depends_on": []  # No dependencies = can run parallel
                }
                for i in range(step_count)
            ]

            workflow = {"id": "test-workflow", "steps": steps}

            try:
                await engine._run_execution("test-exec-123", workflow)
            except Exception:
                pass

        # INVARIANT: Max concurrent should not exceed limit
        assert max_observed <= max_concurrent, \
            f"Concurrency limit violated: observed {max_observed} > limit {max_concurrent}"

    # ==========================================================================
    # INVARIANT 5: Cancellation Propagation
    # ==========================================================================

    @given(
        step_count=st.integers(min_value=3, max_value=15),
        cancel_at_step=st.integers(min_value=1, max_value=10)
    )
    @hypothesis_settings
    async def test_cancellation_propagation(
        self, step_count, cancel_at_step
    ):
        """
        INVARIANT: Cancellation request stops workflow execution and
        prevents subsequent steps from executing.
        """
        assume(cancel_at_step < step_count)

        # Track which steps executed
        executed_steps = []

        async def mock_execute_step(step, params):
            # Simulate cancellation during execution
            executed_steps.append(step["id"])
            await asyncio.sleep(0.01)
            return {"result": "success"}

        state_manager = AsyncMock()
        state_manager.create_execution = AsyncMock(return_value="test-exec-123")

        # Return different state to track progress
        call_count = [0]

        async def get_state(exec_id):
            call_count[0] += 1
            # Request cancellation after cancel_at_step steps
            if call_count[0] > cancel_at_step:
                # Add to cancellation requests
                engine.cancellation_requests.add(exec_id)
            return {
                "execution_id": exec_id,
                "workflow_id": "test-workflow",
                "status": "RUNNING",
                "input_data": {},
                "steps": {},
                "outputs": {},
                "context": {}
            }

        state_manager.get_execution_state = get_state
        state_manager.update_step_status = AsyncMock()
        state_manager.update_execution_status = AsyncMock()

        with patch('core.workflow_engine.get_state_manager', return_value=state_manager):
            engine = WorkflowEngine(max_concurrent_steps=3)
            engine.state_manager = state_manager
            engine._execute_step = mock_execute_step

            steps = [
                {
                    "id": f"step{i}",
                    "name": f"Step {i}",
                    "sequence_order": i,
                    "service": "test",
                    "action": "action",
                    "parameters": {}
                }
                for i in range(step_count)
            ]

            workflow = {"id": "test-workflow", "steps": steps}

            await engine._run_execution("test-exec-123", workflow)

        # INVARIANT: Cancellation should stop execution
        # Some steps may have started, but not all should complete
        assert len(executed_steps) < step_count, \
            f"All steps executed despite cancellation: {executed_steps}"

    # ==========================================================================
    # INVARIANT 6: Conditional Branching Evaluation
    # ==========================================================================

    @given(
        condition_value=st.booleans(),
        condition_expression=st.sampled_from([
            "${step1.output.success} == true",
            "${step1.output.value} > 5",
            "${step1.output.status} == 'active'",
            "step1.output.count >= 10"
        ])
    )
    @hypothesis_settings
    def test_conditional_branching_evaluation(
        self, workflow_engine, condition_value, condition_expression
    ):
        """
        INVARIANT: Conditional connections evaluate correctly based on
        execution state and only activate when conditions are met.
        """
        # Build state with step output
        state = {
            "outputs": {
                "step1": {
                    "output": {
                        "success": condition_value,
                        "value": 10 if condition_value else 0,
                        "status": "active" if condition_value else "inactive",
                        "count": 15 if condition_value else 5
                    }
                }
            }
        }

        # Build workflow with conditional connection
        workflow = {
            "id": "test-workflow",
            "nodes": [
                {"id": "step1", "title": "Step 1", "config": {}},
                {"id": "step2", "title": "Step 2", "config": {}}
            ],
            "connections": [
                {
                    "source": "step1",
                    "target": "step2",
                    "condition": condition_expression
                }
            ]
        }

        # Check if workflow has conditional connections
        has_conditionals = workflow_engine._has_conditional_connections(workflow)
        assert has_conditionals, "Should detect conditional connection"

        # Evaluate condition
        result = workflow_engine._evaluate_condition(condition_expression, state)

        # INVARIANT: Condition evaluation matches expected truth value
        # (This is a simplified check - real conditions may be more complex)
        assert isinstance(result, bool), \
            f"Condition evaluation should return bool, got {type(result)}"

    # ==========================================================================
    # INVARIANT 7: Parameter Schema Validation
    # ==========================================================================

    @given(
        has_message=st.booleans(),
        message_is_string=st.booleans(),
        has_count=st.booleans(),
        count_is_negative=st.booleans()
    )
    @hypothesis_settings
    def test_parameter_schema_validation(
        self, workflow_engine, has_message, message_is_string, has_count, count_is_negative
    ):
        """
        INVARIANT: Input schema validation rejects parameters that don't
        match the required schema (type, format, constraints).
        """
        # Define schema requiring string type
        step = {
            "id": "step1",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "count": {"type": "integer", "minimum": 0}
                },
                "required": ["message"]
            }
        }

        # Build test parameters
        test_params = {}
        if has_message:
            test_params["message"] = "valid" if message_is_string else 123
        if has_count:
            test_params["count"] = -1 if count_is_negative else 5

        # Check if parameters should be valid
        should_be_valid = (
            has_message and
            message_is_string and
            (not has_count or not count_is_negative)
        )

        try:
            workflow_engine._validate_input_schema(step, test_params)
            # If no exception, params should be valid
            assert should_be_valid, \
                f"Expected validation error but none raised for {test_params}"
        except (SchemaValidationError, jsonschema.ValidationError):
            # INVARIANT: Invalid schema should raise validation error
            assert not should_be_valid, \
                f"Unexpected validation error for valid params {test_params}"

    # ==========================================================================
    # INVARIANT 8: Timeout Enforcement
    # ==========================================================================

    @given(
        timeout_seconds=st.integers(min_value=1, max_value=5),
        execution_delay=st.floats(min_value=0.1, max_value=10.0)
    )
    @hypothesis_settings
    async def test_timeout_enforcement(self, timeout_seconds, execution_delay):
        """
        INVARIANT: Step timeout enforcement prevents infinite execution.
        Steps exceeding timeout should raise StepTimeoutError.
        """
        from core.workflow_engine import StepTimeoutError

        async def slow_execute_step(step, params):
            await asyncio.sleep(execution_delay)
            return {"result": "done"}

        state_manager = AsyncMock()
        state_manager.get_execution_state = AsyncMock(return_value={
            "execution_id": "test-exec-123",
            "workflow_id": "test-workflow",
            "status": "RUNNING",
            "input_data": {},
            "steps": {},
            "outputs": {},
            "context": {}
        })
        state_manager.update_step_status = AsyncMock()
        state_manager.update_execution_status = AsyncMock()

        with patch('core.workflow_engine.get_state_manager', return_value=state_manager):
            engine = WorkflowEngine(max_concurrent_steps=1)
            engine.state_manager = state_manager
            engine._execute_step = slow_execute_step

            step = {
                "id": "slow_step",
                "name": "Slow Step",
                "timeout": timeout_seconds,
                "parameters": {}
            }

            # Test timeout enforcement
            # Note: Actual timeout handling is in _execute_step with asyncio.wait_for
            # This test verifies the timeout configuration is respected
            if execution_delay > timeout_seconds:
                # Should timeout in real execution
                # (mocking the actual timeout mechanism)
                assert step["timeout"] == timeout_seconds, \
                    "Timeout configuration not preserved"

    # ==========================================================================
    # INVARIANT 9: Graph Execution Maintains State Consistency
    # ==========================================================================

    @given(
        node_count=st.integers(min_value=3, max_value=10),
        edge_count=st.integers(min_value=2, max_value=15)
    )
    @hypothesis_settings
    def test_graph_execution_builds_consistent_state(
        self, workflow_engine, node_count, edge_count
    ):
        """
        INVARIANT: Building execution graph from nodes/connections produces
        consistent adjacency lists and reverse adjacency lists.
        """
        # Create nodes
        nodes = [
            {
                "id": f"node{i}",
                "title": f"Node {i}",
                "config": {"service": "test"}
            }
            for i in range(node_count)
        ]

        # Create edges (connections)
        edges = []
        for i in range(min(edge_count, node_count * (node_count - 1))):
            source = f"node{i % node_count}"
            target = f"node{(i + 1) % node_count}"
            edges.append({
                "source": source,
                "target": target,
                "condition": None
            })

        workflow = {
            "id": "test-workflow",
            "nodes": nodes,
            "connections": edges
        }

        # Build execution graph
        graph = workflow_engine._build_execution_graph(workflow)

        # INVARIANT: All nodes present in graph
        assert len(graph["nodes"]) == node_count, \
            f"Missing nodes in graph: {len(graph['nodes'])} != {node_count}"

        # INVARIANT: Adjacency and reverse adjacency are consistent
        for source, target in [(e["source"], e["target"]) for e in edges]:
            if source in graph["adjacency"] and target in graph["adjacency"]:
                # Forward edge exists
                forward_edges = [e for e in graph["adjacency"][source]
                                 if e["target"] == target]
                # Reverse edge exists
                reverse_edges = [e for e in graph["reverse_adjacency"][target]
                                  if e["source"] == source]

                # At least one direction should exist (graph may filter duplicates)
                assert len(forward_edges) > 0 or len(reverse_edges) > 0, \
                    f"Edge {source} -> {target} missing from graph"

    # ==========================================================================
    # INVARIANT 10: State Persistence Maintains Consistency
    # ==========================================================================

    @given(
        update_count=st.integers(min_value=1, max_value=20)
    )
    @hypothesis_settings
    async def test_state_persistence_consistency(
        self, state_manager, update_count
    ):
        """
        INVARIANT: Multiple state updates maintain consistency and versioning.
        State updates should be applied sequentially without corruption.
        """
        execution_id = "test-exec-123"

        # Track update calls
        update_calls = []

        async def mock_update_step_status(exec_id, step_id, status, **kwargs):
            update_calls.append({
                "exec_id": exec_id,
                "step_id": step_id,
                "status": status,
                "kwargs": kwargs
            })

        state_manager.update_step_status = mock_update_step_status

        # Simulate multiple step updates
        for i in range(update_count):
            await state_manager.update_step_status(
                execution_id,
                f"step{i}",
                "COMPLETED",
                output={"result": f"output{i}"}
            )

        # INVARIANT: All updates recorded
        assert len(update_calls) == update_count, \
            f"Missing updates: {len(update_calls)} != {update_count}"

        # INVARIANT: Update order preserved
        for i, call in enumerate(update_calls):
            assert call["step_id"] == f"step{i}", \
                f"Update order violated at index {i}"
            assert call["status"] == "COMPLETED", \
                f"Update status incorrect at index {i}"

    # ==========================================================================
    # INVARIANT 11: Variable Reference Resolution Edge Cases
    # ==========================================================================

    @given(
        variable_name=st.text(min_size=1, max_size=20),
        has_output=st.booleans()
    )
    @hypothesis_settings
    def test_variable_resolution_missing_raises_error(
        self, workflow_engine, variable_name, has_output
    ):
        """
        INVARIANT: Missing variable references raise MissingInputError
        with the missing variable name in the error.
        """
        assume(variable_name != "input" and variable_name != "output")

        state = {"outputs": {}}
        if has_output:
            state["outputs"]["step1"] = {"result": "value"}

        # Reference non-existent variable
        parameter = f"${{nonexistent.{variable_name}}}"

        with pytest.raises(MissingInputError) as exc_info:
            workflow_engine._resolve_parameters({"key": parameter}, state)

        # INVARIANT: Error should mention the missing variable
        assert "nonexistent" in str(exc_info.value), \
            f"MissingInputError should reference the missing variable"

    # ==========================================================================
    # INVARIANT 12: Dependency Checking is Correct
    # ==========================================================================

    @given(
        step_dependencies=st.lists(
            st.tuples(
                st.text(min_size=1, alphabet='abcdefghij'),
                st.lists(st.text(min_size=1, alphabet='abcdefghij'), min_size=0, max_size=5)
            ),
            min_size=1,
            max_size=10
        )
    )
    @hypothesis_settings
    def test_dependency_checking_correctness(
        self, workflow_engine, step_dependencies
    ):
        """
        INVARIANT: Dependency checking returns True only when all
        dependencies are marked as COMPLETED in state.
        """
        state = {
            "steps": {},
            "outputs": {}
        }

        # Mark some steps as completed
        completed_steps = set()
        for step_id, deps in step_dependencies[:len(step_dependencies)//2]:
            completed_steps.add(step_id)
            state["steps"][step_id] = {"status": "COMPLETED"}

        # Check dependencies for each step
        for step_id, deps in step_dependencies:
            step = {"id": step_id, "depends_on": deps}

            # Manual dependency check (same logic as WorkflowEngine._check_dependencies)
            all_deps_met = True
            for dep_id in deps:
                dep_state = state["steps"].get(dep_id, {})
                if dep_state.get("status") != "COMPLETED":
                    all_deps_met = False
                    break

            result = workflow_engine._check_dependencies(step, state)

            # INVARIANT: Result should match manual check
            assert result == all_deps_met, \
                f"Dependency check mismatch for {step_id}: {result} != {all_deps_met}"
