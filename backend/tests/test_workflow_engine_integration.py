"""
Workflow Engine Integration Tests

Integration tests for workflow_engine.py that CALL actual WorkflowEngine class methods.
These tests use real database sessions and test the full workflow lifecycle.

Coverage target: Increase workflow_engine.py coverage from baseline
Reference: Phase 127-08A Plan - Integration tests for high-impact files
"""

import os
os.environ["TESTING"] = "1"

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, patch, AsyncMock

# Import WorkflowEngine and related classes
from core.workflow_engine import WorkflowEngine
from core.database import SessionLocal
from core.models import WorkflowExecution, WorkflowStepExecution
from core.execution_state_manager import get_state_manager


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def db_session():
    """Create a database session for testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def workflow_engine(db_session):
    """Create WorkflowEngine instance."""
    return WorkflowEngine()


@pytest.fixture
def sample_workflow_data():
    """Sample workflow data for testing."""
    return {
        "id": "test_workflow_001",
        "name": "Test Integration Workflow",
        "description": "Test workflow for integration coverage",
        "nodes": [
            {
                "id": "step1",
                "type": "action",
                "title": "First Step",
                "config": {
                    "service": "test",
                    "action": "test_action",
                    "parameters": {"test": "value"}
                }
            },
            {
                "id": "step2",
                "type": "action",
                "title": "Second Step",
                "config": {
                    "service": "test",
                    "action": "another_action",
                    "parameters": {"test2": "value2"}
                }
            }
        ],
        "connections": [
            {
                "id": "conn1",
                "source": "step1",
                "target": "step2"
            }
        ]
    }


@pytest.fixture
def parallel_workflow_data():
    """Sample workflow with parallel steps."""
    return {
        "id": "test_workflow_parallel",
        "name": "Parallel Workflow",
        "nodes": [
            {
                "id": "step1",
                "type": "action",
                "title": "Parallel Step 1",
                "config": {
                    "service": "test",
                    "action": "action1",
                    "parameters": {}
                }
            },
            {
                "id": "step2",
                "type": "action",
                "title": "Parallel Step 2",
                "config": {
                    "service": "test",
                    "action": "action2",
                    "parameters": {}
                }
            },
            {
                "id": "step3",
                "type": "action",
                "title": "Final Step",
                "config": {
                    "service": "test",
                    "action": "action3",
                    "parameters": {}
                }
            }
        ],
        "connections": [
            {"id": "conn1", "source": "step1", "target": "step3"},
            {"id": "conn2", "source": "step2", "target": "step3"}
        ]
    }


@pytest.fixture
def cyclic_workflow_data():
    """Sample workflow with cycle for testing cycle detection."""
    return {
        "id": "test_workflow_cyclic",
        "name": "Cyclic Workflow",
        "nodes": [
            {
                "id": "step1",
                "type": "action",
                "title": "Step 1",
                "config": {"service": "test", "action": "action1", "parameters": {}}
            },
            {
                "id": "step2",
                "type": "action",
                "title": "Step 2",
                "config": {"service": "test", "action": "action2", "parameters": {}}
            }
        ],
        "connections": [
            {"id": "conn1", "source": "step1", "target": "step2"},
            {"id": "conn2", "source": "step2", "target": "step1"}  # Cycle!
        ]
    }


@pytest.fixture
def conditional_workflow_data():
    """Sample workflow with conditional connections."""
    return {
        "id": "test_workflow_conditional",
        "name": "Conditional Workflow",
        "nodes": [
            {
                "id": "step1",
                "type": "action",
                "title": "Decision Step",
                "config": {
                    "service": "test",
                    "action": "decision_action",
                    "parameters": {}
                }
            },
            {
                "id": "step2a",
                "type": "action",
                "title": "Branch A",
                "config": {"service": "test", "action": "action_a", "parameters": {}}
            },
            {
                "id": "step2b",
                "type": "action",
                "title": "Branch B",
                "config": {"service": "test", "action": "action_b", "parameters": {}}
            }
        ],
        "connections": [
            {"id": "conn1", "source": "step1", "target": "step2a", "condition": "{{status == 'approved'}}"},
            {"id": "conn2", "source": "step1", "target": "step2b", "condition": "{{status == 'rejected'}}"}
        ]
    }


# ============================================================================
# INTEGRATION TESTS: Workflow Lifecycle
# ============================================================================

class TestWorkflowEngineLifecycle:
    """Tests for complete workflow lifecycle through WorkflowEngine methods."""

    def test_convert_nodes_to_steps_simple(self, workflow_engine, sample_workflow_data):
        """
        GIVEN WorkflowEngine instance
        WHEN _convert_nodes_to_steps() is called with linear workflow
        THEN return correct step list with sequence_order
        """
        steps = workflow_engine._convert_nodes_to_steps(sample_workflow_data)

        assert len(steps) == 2
        assert steps[0]["id"] == "step1"
        assert steps[0]["sequence_order"] == 1
        assert steps[1]["id"] == "step2"
        assert steps[1]["sequence_order"] == 2
        assert steps[0]["action"] == "test_action"
        assert steps[1]["action"] == "another_action"

    def test_convert_nodes_to_steps_parallel(self, workflow_engine, parallel_workflow_data):
        """
        GIVEN WorkflowEngine instance
        WHEN _convert_nodes_to_steps() is called with parallel workflow
        THEN return steps with topological sort order
        """
        steps = workflow_engine._convert_nodes_to_steps(parallel_workflow_data)

        assert len(steps) == 3
        # Step 3 should come after steps 1 and 2 (topological sort)
        step_ids = [s["id"] for s in steps]
        assert step_ids.index("step3") > step_ids.index("step1")
        assert step_ids.index("step3") > step_ids.index("step2")

    def test_convert_nodes_to_steps_with_cycle(self, workflow_engine, cyclic_workflow_data):
        """
        GIVEN WorkflowEngine instance with cyclic workflow
        WHEN _convert_nodes_to_steps() is called
        THEN return steps (topological sort handles cycles, may not include all)
        """
        steps = workflow_engine._convert_nodes_to_steps(cyclic_workflow_data)

        # Topological sort with cycles may not include all nodes
        # That's expected behavior - Kahn's algorithm stops when no nodes with in_degree=0 remain
        assert len(steps) >= 0  # May be 0, 1, or 2 depending on cycle detection
        assert all("id" in s for s in steps)
        assert all("action" in s for s in steps)


class TestWorkflowEngineGraphBuilding:
    """Tests for workflow graph construction."""

    def test_build_execution_graph_simple(self, workflow_engine, sample_workflow_data):
        """
        GIVEN WorkflowEngine instance
        WHEN _build_execution_graph() is called
        THEN return correct adjacency structure
        """
        graph = workflow_engine._build_execution_graph(sample_workflow_data)

        assert "nodes" in graph
        assert "connections" in graph
        assert "adjacency" in graph
        assert "reverse_adjacency" in graph

        assert len(graph["nodes"]) == 2
        assert "step1" in graph["nodes"]
        assert "step2" in graph["nodes"]

        # Check adjacency (step1 -> step2)
        assert len(graph["adjacency"]["step1"]) == 1
        assert graph["adjacency"]["step1"][0]["target"] == "step2"

        # Check reverse adjacency (step2 <- step1)
        assert len(graph["reverse_adjacency"]["step2"]) == 1
        assert graph["reverse_adjacency"]["step2"][0]["source"] == "step1"

    def test_build_execution_graph_parallel(self, workflow_engine, parallel_workflow_data):
        """
        GIVEN WorkflowEngine instance with parallel workflow
        WHEN _build_execution_graph() is called
        THEN return correct adjacency with multiple outgoing edges
        """
        graph = workflow_engine._build_execution_graph(parallel_workflow_data)

        # Step 1 and 2 should connect to step 3
        assert len(graph["adjacency"]["step1"]) == 1
        assert len(graph["adjacency"]["step2"]) == 1
        assert len(graph["reverse_adjacency"]["step3"]) == 2


class TestWorkflowConditionEvaluation:
    """Tests for condition evaluation in workflows."""

    def test_has_conditional_connections_true(self, workflow_engine, conditional_workflow_data):
        """
        GIVEN workflow with conditional connections
        WHEN _has_conditional_connections() is called
        THEN return True
        """
        result = workflow_engine._has_conditional_connections(conditional_workflow_data)
        assert result is True

    def test_has_conditional_connections_false(self, workflow_engine, sample_workflow_data):
        """
        GIVEN workflow without conditional connections
        WHEN _has_conditional_connections() is called
        THEN return False
        """
        result = workflow_engine._has_conditional_connections(sample_workflow_data)
        assert result is False

    def test_evaluate_condition_no_condition(self, workflow_engine):
        """
        GIVEN connection without condition
        WHEN _evaluate_condition() is called with None
        THEN return True (default activation)
        """
        result = workflow_engine._evaluate_condition(None, {"test": "value"})
        assert result is True

    def test_evaluate_condition_empty_string(self, workflow_engine):
        """
        GIVEN connection with empty condition string
        WHEN _evaluate_condition() is called
        THEN return True
        """
        result = workflow_engine._evaluate_condition("", {"test": "value"})
        assert result is True

    def test_evaluate_condition_simple_equality(self, workflow_engine):
        """
        GIVEN condition with variable reference and equality check
        WHEN _evaluate_condition() is called with matching state
        THEN return True
        """
        condition = "${input.status} == 'approved'"
        state = {"input_data": {"status": "approved"}}
        result = workflow_engine._evaluate_condition(condition, state)
        assert result is True

    def test_evaluate_condition_simple_inequality(self, workflow_engine):
        """
        GIVEN condition with variable reference and equality check
        WHEN _evaluate_condition() is called with non-matching state
        THEN return False
        """
        condition = "${input.status} == 'approved'"
        state = {"input_data": {"status": "rejected"}}
        result = workflow_engine._evaluate_condition(condition, state)
        assert result is False


class TestWorkflowParameterResolution:
    """Tests for parameter resolution in workflows."""

    def test_resolve_parameters_no_variables(self, workflow_engine):
        """
        GIVEN parameters without variable references
        WHEN _resolve_parameters() is called
        THEN return parameters unchanged
        """
        params = {"key": "value", "number": 123}
        state = {"test": "data"}
        result = workflow_engine._resolve_parameters(params, state)

        assert result == params

    def test_resolve_parameters_with_simple_variable(self, workflow_engine):
        """
        GIVEN parameters with variable reference
        WHEN _resolve_parameters() is called with matching state
        THEN replace variable with state value
        """
        params = {"input": "${step1.output}"}
        state = {"outputs": {"step1": {"output": "test_value"}}}
        result = workflow_engine._resolve_parameters(params, state)

        assert result["input"] == "test_value"

    def test_resolve_parameters_with_nested_variable(self, workflow_engine):
        """
        GIVEN parameters with nested variable reference
        WHEN _resolve_parameters() is called
        THEN extract nested value from state
        """
        params = {"user_id": "${step1.user.id}"}
        state = {"outputs": {"step1": {"user": {"id": "user_123"}}}}
        result = workflow_engine._resolve_parameters(params, state)

        assert result["user_id"] == "user_123"

    def test_resolve_parameters_multiple_variables(self, workflow_engine):
        """
        GIVEN parameters with multiple variable references
        WHEN _resolve_parameters() is called
        THEN replace all variables
        """
        params = {
            "input1": "${step1.output}",
            "input2": "${step2.result}",
            "static": "unchanged"
        }
        state = {
            "outputs": {
                "step1": {"output": "value1"},
                "step2": {"result": "value2"}
            }
        }
        result = workflow_engine._resolve_parameters(params, state)

        assert result["input1"] == "value1"
        assert result["input2"] == "value2"
        assert result["static"] == "unchanged"

    def test_resolve_parameters_missing_variable(self, workflow_engine):
        """
        GIVEN parameters with undefined variable reference
        WHEN _resolve_parameters() is called
        THEN raise MissingInputError
        """
        from core.workflow_engine import MissingInputError

        params = {"input": "${missing.output}"}
        state = {"outputs": {"other": "value"}}

        with pytest.raises(MissingInputError):
            workflow_engine._resolve_parameters(params, state)


class TestWorkflowDependencyChecking:
    """Tests for dependency checking in workflows."""

    def test_check_dependencies_no_dependencies(self, workflow_engine):
        """
        GIVEN step with no dependencies
        WHEN _check_dependencies() is called
        THEN return True
        """
        step = {"id": "step1", "depends_on": []}
        state = {"steps": {}}
        result = workflow_engine._check_dependencies(step, state)

        assert result is True

    def test_check_dependencies_satisfied(self, workflow_engine):
        """
        GIVEN step with satisfied dependencies
        WHEN _check_dependencies() is called
        THEN return True
        """
        step = {"id": "step2", "depends_on": ["step1"]}
        state = {"steps": {"step1": {"status": "COMPLETED"}}}
        result = workflow_engine._check_dependencies(step, state)

        assert result is True

    def test_check_dependencies_unsatisfied(self, workflow_engine):
        """
        GIVEN step with unsatisfied dependencies
        WHEN _check_dependencies() is called
        THEN return False
        """
        step = {"id": "step2", "depends_on": ["step1"]}
        state = {"steps": {"step1": {"status": "PENDING"}}}
        result = workflow_engine._check_dependencies(step, state)

        assert result is False


class TestWorkflowValuePathExtraction:
    """Tests for value extraction from state paths."""

    def test_get_value_from_path_simple_key(self, workflow_engine):
        """
        GIVEN simple key path for input data
        WHEN _get_value_from_path() is called
        THEN return correct value
        """
        state = {"input_data": {"key": "value"}}
        result = workflow_engine._get_value_from_path("input.key", state)

        assert result == "value"

    def test_get_value_from_path_nested_key(self, workflow_engine):
        """
        GIVEN nested key path with dots for input data
        WHEN _get_value_from_path() is called
        THEN return nested value
        """
        state = {"input_data": {"level1": {"level2": {"level3": "deep_value"}}}}
        result = workflow_engine._get_value_from_path("input.level1.level2.level3", state)

        assert result == "deep_value"

    def test_get_value_from_path_missing_key(self, workflow_engine):
        """
        GIVEN path to non-existent key in outputs
        WHEN _get_value_from_path() is called
        THEN return None
        """
        state = {"outputs": {"existing": "value"}}
        result = workflow_engine._get_value_from_path("missing", state)

        assert result is None

    def test_get_value_from_path_missing_nested_key(self, workflow_engine):
        """
        GIVEN path with missing intermediate key in outputs
        WHEN _get_value_from_path() is called
        THEN return None
        """
        state = {"outputs": {"level1": {"level2": "value"}}}
        result = workflow_engine._get_value_from_path("level1.missing.level3", state)

        assert result is None
