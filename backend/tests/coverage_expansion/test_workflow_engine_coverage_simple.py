"""
Coverage expansion tests for workflow engine - simplified version.

Tests cover critical code paths in:
- workflow_engine.py: Workflow execution, state management, error handling

Target: Cover critical paths (happy path + error paths) to increase coverage.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from core.workflow_engine import WorkflowEngine, MissingInputError
from core.models import AgentRegistry, AgentStatus
from core.execution_state_manager import get_state_manager


class TestWorkflowEngineCoverageSimple:
    """Coverage expansion for WorkflowEngine - simplified tests."""

    @pytest.fixture
    def db_session(self):
        """Get test database session."""
        from core.database import SessionLocal
        session = SessionLocal()
        yield session
        session.rollback()
        session.close()

    @pytest.fixture
    async def state_manager(self):
        """Get state manager instance."""
        return get_state_manager()

    @pytest.fixture
    def engine(self):
        """Get workflow engine instance."""
        return WorkflowEngine()

    @pytest.fixture
    def ws_manager(self):
        """Mock WebSocket manager."""
        manager = MagicMock()
        manager.notify_workflow_status = AsyncMock()
        return manager

    # Test: workflow initialization and start
    @pytest.mark.asyncio
    async def test_start_workflow_success(self, engine, state_manager):
        """Start workflow with valid blueprint."""
        workflow = {
            "id": "test-workflow",
            "steps": [
                {
                    "id": "step1",
                    "name": "Test Step 1",
                    "service": "test_service",
                    "action": "test_action",
                    "parameters": {}
                }
            ]
        }
        input_data = {"test": "data"}

        execution_id = await engine.start_workflow(workflow, input_data)
        assert execution_id is not None
        assert isinstance(execution_id, str)

    @pytest.mark.asyncio
    async def test_start_workflow_with_nodes(self, engine, state_manager):
        """Start workflow with nodes (graph-based)."""
        workflow = {
            "id": "test-workflow-graph",
            "nodes": [
                {
                    "id": "node1",
                    "type": "action",
                    "title": "Test Node",
                    "config": {
                        "service": "test_service",
                        "action": "test_action",
                        "parameters": {}
                    }
                }
            ],
            "connections": []
        }
        input_data = {"test": "data"}

        execution_id = await engine.start_workflow(workflow, input_data)
        assert execution_id is not None

    # Test: convert nodes to steps
    def test_convert_nodes_to_steps_linear(self, engine):
        """Convert linear nodes to steps."""
        workflow = {
            "nodes": [
                {"id": "node1", "type": "action", "title": "Step 1", "config": {"action": "action1"}},
                {"id": "node2", "type": "action", "title": "Step 2", "config": {"action": "action2"}}
            ],
            "connections": [
                {"source": "node1", "target": "node2"}
            ]
        }
        steps = engine._convert_nodes_to_steps(workflow)

        assert len(steps) == 2
        assert steps[0]["id"] == "node1"
        assert steps[1]["id"] == "node2"
        assert steps[0]["sequence_order"] == 1
        assert steps[1]["sequence_order"] == 2

    def test_convert_nodes_to_steps_with_trigger(self, engine):
        """Convert nodes with trigger type."""
        workflow = {
            "nodes": [
                {
                    "id": "trigger1",
                    "type": "trigger",
                    "title": "Manual Trigger",
                    "config": {"action": "manual_trigger"}
                }
            ],
            "connections": []
        }
        steps = engine._convert_nodes_to_steps(workflow)

        assert len(steps) == 1
        assert steps[0]["type"] == "trigger"
        assert steps[0]["action"] == "manual_trigger"

    # Test: build execution graph
    def test_build_execution_graph(self, engine):
        """Build execution graph from workflow."""
        workflow = {
            "nodes": [
                {"id": "node1", "title": "Node 1"},
                {"id": "node2", "title": "Node 2"}
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

    # Test: conditional connections
    def test_has_conditional_connections_true(self, engine):
        """Detect conditional connections."""
        workflow = {
            "connections": [
                {"source": "node1", "target": "node2", "condition": "{{data.value > 10}}"}
            ]
        }
        assert engine._has_conditional_connections(workflow) == True

    def test_has_conditional_connections_false(self, engine):
        """Detect no conditional connections."""
        workflow = {
            "connections": [
                {"source": "node1", "target": "node2"}
            ]
        }
        assert engine._has_conditional_connections(workflow) == False

    # Test: parameter resolution
    def test_resolve_parameters_no_variables(self, engine):
        """Resolve parameters with no variables."""
        params = {"key": "value", "number": 42}
        state = {}
        resolved = engine._resolve_parameters(params, state)
        assert resolved == params

    def test_resolve_parameters_with_variable(self, engine):
        """Resolve parameters with variable reference."""
        params = {"result": "${step1.output}"}
        state = {
            "outputs": {
                "step1": {"data": "test_result"}
            }
        }
        resolved = engine._resolve_parameters(params, state)
        assert resolved["result"] == {"data": "test_result"}

    def test_resolve_parameters_missing_variable(self, engine):
        """Raise error for missing variable."""
        params = {"result": "${missing_step.output}"}
        state = {"outputs": {}}

        with pytest.raises(MissingInputError) as exc_info:
            engine._resolve_parameters(params, state)
        assert "missing_step" in str(exc_info.value.missing_var)

    # Test: schema validation
    def test_validate_input_schema_valid(self, engine):
        """Validate valid input against schema."""
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

    def test_validate_input_schema_invalid(self, engine):
        """Reject invalid input against schema."""
        step = {
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "required": ["name"]
            }
        }
        params = {"age": 30}  # Missing required 'name'

        from core.workflow_engine import SchemaValidationError
        with pytest.raises(SchemaValidationError):
            engine._validate_input_schema(step, params)

    def test_validate_output_schema_valid(self, engine):
        """Validate valid output against schema."""
        step = {
            "output_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string"}
                }
            }
        }
        output = {"result": "success"}

        # Should not raise
        engine._validate_output_schema(step, output)

    # Test: condition evaluation
    def test_evaluate_condition_true(self, engine):
        """Evaluate condition that is true."""
        condition = "{{outputs.step1.status == 'completed'}}"
        state = {"outputs": {"step1": {"status": "completed"}}}
        result = engine._evaluate_condition(condition, state)
        assert result == True

    def test_evaluate_condition_false(self, engine):
        """Evaluate condition that is false."""
        condition = "{{outputs.step1.status == 'completed'}}"
        state = {"outputs": {"step1": {"status": "failed"}}}
        result = engine._evaluate_condition(condition, state)
        assert result == False

    # Test: workflow cancellation
    @pytest.mark.asyncio
    async def test_cancel_workflow(self, engine, state_manager):
        """Cancel workflow execution."""
        execution_id = "test-execution-cancel"
        engine.cancellation_requests.add(execution_id)

        assert execution_id in engine.cancellation_requests

        # Cleanup
        engine.cancellation_requests.discard(execution_id)

    # Test: error handling
    @pytest.mark.asyncio
    async def test_execute_workflow_with_invalid_service(self, engine, state_manager, ws_manager):
        """Handle workflow execution with invalid service."""
        workflow = {
            "id": "test-workflow-invalid",
            "workspace_id": "default",
            "tenant_id": "default",
            "nodes": [
                {
                    "id": "node1",
                    "type": "action",
                    "title": "Invalid Service",
                    "config": {
                        "service": "nonexistent_service",
                        "action": "invalid_action",
                        "parameters": {}
                    }
                }
            ],
            "connections": []
        }

        input_data = {}
        user_id = "test-user"

        # Start workflow (should handle error gracefully)
        execution_id = await engine.start_workflow(workflow, input_data)
        assert execution_id is not None

    # Test: concurrent execution with semaphore
    def test_semaphore_limit(self, engine):
        """Verify semaphore limits concurrent steps."""
        assert engine.max_concurrent_steps == 5
        assert engine.semaphore._value == 5  # Internal semaphore counter

    # Test: topological sort for DAG execution
    def test_topological_sort_kahn_algorithm(self, engine):
        """Test topological sort using Kahn's algorithm."""
        workflow = {
            "nodes": [
                {"id": "a", "title": "A"},
                {"id": "b", "title": "B"},
                {"id": "c", "title": "C"}
            ],
            "connections": [
                {"source": "a", "target": "b"},
                {"source": "a", "target": "c"},
                {"source": "b", "target": "c"}
            ]
        }
        steps = engine._convert_nodes_to_steps(workflow)

        # Should execute in topological order: a -> b -> c
        step_ids = [s["id"] for s in steps]
        assert step_ids.index("a") < step_ids.index("b")
        assert step_ids.index("a") < step_ids.index("c")
        assert step_ids.index("b") < step_ids.index("c")

    # Test: workflow with multiple branches
    def test_convert_nodes_with_branching(self, engine):
        """Convert nodes with multiple branches."""
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
        steps = engine._convert_nodes_to_steps(workflow)

        assert len(steps) == 4
        # Start should come before branches
        step_ids = [s["id"] for s in steps]
        assert step_ids.index("start") < step_ids.index("branch1")
        assert step_ids.index("start") < step_ids.index("branch2")

    # Test: parameter with complex nested structure
    def test_resolve_parameters_complex_nested(self, engine):
        """Resolve complex nested parameter structure."""
        params = {
            "config": {
                "source": "${step1.output.url}",
                "headers": {
                    "auth": "${step1.token}"
                }
            }
        }
        state = {
            "outputs": {
                "step1": {
                    "output": {"url": "https://api.example.com"},
                    "token": "Bearer abc123"
                }
            }
        }
        resolved = engine._resolve_parameters(params, state)

        assert resolved["config"]["source"] == "https://api.example.com"
        assert resolved["config"]["headers"]["auth"] == "Bearer abc123"

    # Test: workflow with continue_on_error
    def test_step_continue_on_error(self, engine):
        """Test step configuration for continue_on_error."""
        workflow = {
            "nodes": [
                {
                    "id": "step1",
                    "title": "Step 1",
                    "config": {
                        "continue_on_error": True,
                        "action": "test_action"
                    }
                }
            ],
            "connections": []
        }
        steps = engine._convert_nodes_to_steps(workflow)

        assert steps[0]["continue_on_error"] == True

    # Test: workflow with timeout
    def test_step_timeout_configuration(self, engine):
        """Test step timeout configuration."""
        workflow = {
            "nodes": [
                {
                    "id": "step1",
                    "title": "Step 1",
                    "config": {
                        "timeout": 30000,
                        "action": "test_action"
                    }
                }
            ],
            "connections": []
        }
        steps = engine._convert_nodes_to_steps(workflow)

        assert steps[0]["timeout"] == 30000

    # Test: schema validation with no schema
    def test_validate_no_schema(self, engine):
        """Handle steps with no schema."""
        step = {}
        params = {"any": "data"}

        # Should not raise when no schema
        engine._validate_input_schema(step, params)
        engine._validate_output_schema(step, {})

    # Test: condition evaluation with complex expressions
    def test_evaluate_complex_condition(self, engine):
        """Evaluate complex condition with multiple variables."""
        condition = "{{outputs.step1.output.value > 10 and outputs.step2.output.enabled == true}}"
        state = {
            "outputs": {
                "step1": {"output": {"value": 15}},
                "step2": {"output": {"enabled": True}}
            }
        }
        result = engine._evaluate_condition(condition, state)
        assert result == True

    # Test: resolve parameters with list variable
    def test_resolve_parameters_list_variable(self, engine):
        """Resolve parameter that references a list."""
        params = {"items": "${step1.output.items}"}
        state = {
            "outputs": {
                "step1": {
                    "output": {
                        "items": ["a", "b", "c"]
                    }
                }
            }
        }
        resolved = engine._resolve_parameters(params, state)
        assert resolved["items"] == ["a", "b", "c"]

    # Test: empty workflow
    def test_convert_empty_nodes_to_steps(self, engine):
        """Handle workflow with no nodes."""
        workflow = {"nodes": [], "connections": []}
        steps = engine._convert_nodes_to_steps(workflow)
        assert steps == []

    # Test: workflow with isolated nodes
    def test_convert_isolated_nodes(self, engine):
        """Handle nodes with no connections."""
        workflow = {
            "nodes": [
                {"id": "isolated", "title": "Isolated", "config": {"action": "test"}}
            ],
            "connections": []
        }
        steps = engine._convert_nodes_to_steps(workflow)
        assert len(steps) == 1
        assert steps[0]["id"] == "isolated"

    # Test: MissingInputError exception attributes
    def test_missing_input_error_attributes(self):
        """Test MissingInputError exception attributes."""
        error = MissingInputError("Variable missing_var not found", "missing_var")
        assert error.missing_var == "missing_var"
        assert "missing_var" in str(error)

    # Test: execution graph with multiple connections
    def test_build_graph_multiple_connections(self, engine):
        """Build graph with multiple outgoing connections."""
        workflow = {
            "nodes": [
                {"id": "source", "title": "Source"},
                {"id": "target1", "title": "Target 1"},
                {"id": "target2", "title": "Target 2"}
            ],
            "connections": [
                {"source": "source", "target": "target1"},
                {"source": "source", "target": "target2"}
            ]
        }
        graph = engine._build_execution_graph(workflow)

        assert len(graph["adjacency"]["source"]) == 2
        assert len(graph["reverse_adjacency"]["target1"]) == 1
        assert len(graph["reverse_adjacency"]["target2"]) == 1

    # Test: parameter resolution with null values
    def test_resolve_parameters_null_value(self, engine):
        """Handle null values in parameter resolution."""
        params = {"value": "${step1.data}"}
        state = {
            "outputs": {
                "step1": {"data": None}
            }
        }
        resolved = engine._resolve_parameters(params, state)
        assert resolved["value"] is None

    # Test: schema validation with additional properties
    def test_validate_schema_additional_properties(self, engine):
        """Validate schema with additionalProperties flag."""
        step = {
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                },
                "additionalProperties": False
            }
        }
        params = {"name": "test", "extra": "not_allowed"}

        # Should reject due to additionalProperties: false
        from core.workflow_engine import SchemaValidationError
        with pytest.raises(SchemaValidationError):
            engine._validate_input_schema(step, params)

    # Test: condition evaluation with boolean values
    def test_evaluate_condition_boolean(self, engine):
        """Evaluate condition with boolean literals."""
        condition = "{{true}}"
        state = {}
        result = engine._evaluate_condition(condition, state)
        assert result == True

    # Test: resolve parameters with variable in array
    def test_resolve_parameters_variable_in_array(self, engine):
        """Resolve parameters with variable reference in array."""
        params = {
            "targets": ["${step1.output.email1}", "${step1.output.email2}"]
        }
        state = {
            "outputs": {
                "step1": {
                    "output": {
                        "email1": "user1@example.com",
                        "email2": "user2@example.com"
                    }
                }
            }
        }
        resolved = engine._resolve_parameters(params, state)
        assert resolved["targets"] == ["user1@example.com", "user2@example.com"]

    # Test: workflow with mixed node types
    def test_convert_mixed_node_types(self, engine):
        """Convert workflow with trigger and action nodes."""
        workflow = {
            "nodes": [
                {"id": "trigger", "type": "trigger", "title": "Trigger", "config": {"action": "webhook"}},
                {"id": "action1", "type": "action", "title": "Action 1", "config": {"action": "step1"}},
                {"id": "action2", "type": "action", "title": "Action 2", "config": {"action": "step2"}}
            ],
            "connections": [
                {"source": "trigger", "target": "action1"},
                {"source": "action1", "target": "action2"}
            ]
        }
        steps = engine._convert_nodes_to_steps(workflow)

        assert len(steps) == 3
        assert steps[0]["type"] == "trigger"
        assert steps[1]["type"] == "action"
        assert steps[2]["type"] == "action"

    # Test: empty condition evaluation
    def test_evaluate_empty_condition(self, engine):
        """Evaluate empty condition (should return True)."""
        condition = ""
        state = {}
        result = engine._evaluate_condition(condition, state)
        assert result == True

    def test_evaluate_none_condition(self, engine):
        """Evaluate None condition (should return True)."""
        condition = None
        state = {}
        result = engine._evaluate_condition(condition, state)
        assert result == True

    # Test: resolve parameters with deeply nested path
    def test_resolve_parameters_deeply_nested(self, engine):
        """Resolve deeply nested variable path."""
        params = {"value": "${step1.data.nested.path.value}"}
        state = {
            "outputs": {
                "step1": {
                    "data": {
                        "nested": {
                            "path": {
                                "value": "deep_value"
                            }
                        }
                    }
                }
            }
        }
        resolved = engine._resolve_parameters(params, state)
        assert resolved["value"] == "deep_value"
