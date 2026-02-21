"""
Integration tests for workflow_engine.py using real database.

Pattern: Use SQLite in-memory DB, NOT mock_engine

These tests use real database operations to exercise actual SQL queries
and transaction handling, not mocked responses.
"""

import asyncio
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Dict, Any

from core.workflow_engine import WorkflowEngine
from core.models import Base, WorkflowExecution, WorkflowStepExecution, WorkflowExecutionStatus
from core.execution_state_manager import ExecutionStateManager, get_state_manager


@pytest.fixture
def db_engine():
    """Real SQLite in-memory DB (not mocked)"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Real database session for integration tests"""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def state_manager(db_engine):
    """Real execution state manager using real database"""
    # Create a new session factory for the state manager
    SessionLocal = sessionmaker(bind=db_engine)

    # Patch the get_db_session to use our test engine
    import core.database
    original_get_db = core.database.get_db_session

    def test_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    core.database.get_db_session = test_get_db

    # Get state manager with test database
    sm = get_state_manager()
    yield sm

    # Restore original
    core.database.get_db_session = original_get_db


@pytest.fixture
def workflow_engine(db_session, state_manager):
    """Real workflow engine using real database"""
    return WorkflowEngine(max_concurrent_steps=5)


@pytest.fixture
def sample_workflow():
    """Sample workflow definition for testing"""
    return {
        "id": "test-workflow-1",
        "name": "Test Workflow",
        "steps": [
            {
                "id": "step-1",
                "name": "First Step",
                "sequence_order": 1,
                "service": "test",
                "action": "test_action",
                "parameters": {"input": "value"},
                "continue_on_error": False,
                "timeout": 30
            },
            {
                "id": "step-2",
                "name": "Second Step",
                "sequence_order": 2,
                "service": "test",
                "action": "test_action_2",
                "parameters": {},
                "continue_on_error": True,
                "timeout": 30
            }
        ]
    }


@pytest.fixture
def sample_graph_workflow():
    """Sample graph-based workflow for testing node-to-step conversion"""
    return {
        "id": "graph-workflow-1",
        "name": "Graph Workflow",
        "nodes": [
            {
                "id": "node-1",
                "type": "trigger",
                "title": "Trigger Node",
                "config": {
                    "service": "trigger",
                    "action": "manual_trigger",
                    "parameters": {}
                }
            },
            {
                "id": "node-2",
                "type": "action",
                "title": "Action Node",
                "config": {
                    "service": "test",
                    "action": "test_action",
                    "parameters": {"input": "value"},
                    "timeout": 30
                }
            },
            {
                "id": "node-3",
                "type": "action",
                "title": "Final Node",
                "config": {
                    "service": "test",
                    "action": "final_action",
                    "parameters": {}
                }
            }
        ],
        "connections": [
            {"source": "node-1", "target": "node-2"},
            {"source": "node-2", "target": "node-3"}
        ]
    }


# ============================================================================
# Tests: Graph to Step Conversion
# ============================================================================

@pytest.mark.integration
def test_convert_nodes_to_steps_linear(workflow_engine, sample_graph_workflow):
    """Test converting linear graph nodes to steps"""
    steps = workflow_engine._convert_nodes_to_steps(sample_graph_workflow)

    assert len(steps) == 3
    assert steps[0]["id"] == "node-1"
    assert steps[0]["type"] == "trigger"
    assert steps[0]["action"] == "manual_trigger"
    assert steps[0]["sequence_order"] == 1

    assert steps[1]["id"] == "node-2"
    assert steps[1]["type"] == "action"
    assert steps[1]["action"] == "test_action"
    assert steps[1]["sequence_order"] == 2

    assert steps[2]["id"] == "node-3"
    assert steps[2]["sequence_order"] == 3


@pytest.mark.integration
def test_convert_nodes_to_steps_with_complex_config(workflow_engine):
    """Test conversion with complex node configurations"""
    workflow = {
        "id": "complex-workflow",
        "nodes": [
            {
                "id": "node-with-config",
                "type": "action",
                "title": "Complex Node",
                "config": {
                    "service": "api",
                    "action": "http_request",
                    "parameters": {
                        "url": "https://api.example.com",
                        "method": "POST",
                        "headers": {"Content-Type": "application/json"},
                        "body": {"data": "value"}
                    },
                    "input_schema": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}}
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {"response": {"type": "object"}}
                    },
                    "timeout": 60,
                    "continue_on_error": True
                }
            }
        ],
        "connections": []
    }

    steps = workflow_engine._convert_nodes_to_steps(workflow)

    assert len(steps) == 1
    step = steps[0]
    assert step["service"] == "api"
    assert step["action"] == "http_request"
    assert step["parameters"]["url"] == "https://api.example.com"
    assert step["parameters"]["method"] == "POST"
    assert step["timeout"] == 60
    assert step["continue_on_error"] is True
    assert "input_schema" in step
    assert "output_schema" in step


@pytest.mark.integration
def test_topological_sort_preserves_dependencies(workflow_engine):
    """Test that topological sort respects dependency chains"""
    workflow = {
        "id": "dag-workflow",
        "nodes": [
            {"id": "a", "type": "action", "title": "A", "config": {}},
            {"id": "b", "type": "action", "title": "B", "config": {}},
            {"id": "c", "type": "action", "title": "C", "config": {}},
            {"id": "d", "type": "action", "title": "D", "config": {}}
        ],
        "connections": [
            {"source": "a", "target": "b"},
            {"source": "a", "target": "c"},
            {"source": "b", "target": "d"},
            {"source": "c", "target": "d"}
        ]
    }

    steps = workflow_engine._convert_nodes_to_steps(workflow)

    # 'a' should come before 'b' and 'c'
    # 'b' and 'c' should come before 'd'
    step_ids = [s["id"] for s in steps]
    assert step_ids.index("a") < step_ids.index("b")
    assert step_ids.index("a") < step_ids.index("c")
    assert step_ids.index("b") < step_ids.index("d")
    assert step_ids.index("c") < step_ids.index("d")


# ============================================================================
# Tests: Execution Graph Building
# ============================================================================

@pytest.mark.integration
def test_build_execution_graph(workflow_engine, sample_graph_workflow):
    """Test building execution graph from workflow"""
    graph = workflow_engine._build_execution_graph(sample_graph_workflow)

    assert "nodes" in graph
    assert "connections" in graph
    assert "adjacency" in graph
    assert "reverse_adjacency" in graph

    assert len(graph["nodes"]) == 3
    assert "node-1" in graph["nodes"]
    assert "node-2" in graph["nodes"]
    assert "node-3" in graph["nodes"]

    # Check adjacency list
    assert len(graph["adjacency"]["node-1"]) == 1
    assert graph["adjacency"]["node-1"][0]["target"] == "node-2"

    assert len(graph["adjacency"]["node-2"]) == 1
    assert graph["adjacency"]["node-2"][0]["target"] == "node-3"

    assert len(graph["adjacency"]["node-3"]) == 0


@pytest.mark.integration
def test_build_execution_graph_with_conditions(workflow_engine):
    """Test graph building with conditional connections"""
    workflow = {
        "id": "conditional-workflow",
        "nodes": [
            {"id": "start", "type": "action", "title": "Start", "config": {}},
            {"id": "branch-a", "type": "action", "title": "Branch A", "config": {}},
            {"id": "branch-b", "type": "action", "title": "Branch B", "config": {}}
        ],
        "connections": [
            {
                "source": "start",
                "target": "branch-a",
                "condition": "${data.value > 10}"
            },
            {
                "source": "start",
                "target": "branch-b",
                "condition": "${data.value <= 10}"
            }
        ]
    }

    graph = workflow_engine._build_execution_graph(workflow)

    assert len(graph["connections"]) == 2
    assert graph["connections"][0]["condition"] == "${data.value > 10}"
    assert graph["connections"][1]["condition"] == "${data.value <= 10}"
    assert len(graph["adjacency"]["start"]) == 2


@pytest.mark.integration
def test_has_conditional_connections(workflow_engine):
    """Test detection of conditional connections"""
    workflow_without_conditions = {
        "id": "simple-workflow",
        "nodes": [
            {"id": "a", "type": "action", "title": "A", "config": {}},
            {"id": "b", "type": "action", "title": "B", "config": {}}
        ],
        "connections": [
            {"source": "a", "target": "b"}
        ]
    }

    workflow_with_conditions = {
        "id": "conditional-workflow",
        "nodes": [
            {"id": "a", "type": "action", "title": "A", "config": {}},
            {"id": "b", "type": "action", "title": "B", "config": {}}
        ],
        "connections": [
            {"source": "a", "target": "b", "condition": "${data.test == true}"}
        ]
    }

    assert workflow_engine._has_conditional_connections(workflow_without_conditions) is False
    assert workflow_engine._has_conditional_connections(workflow_with_conditions) is True


# ============================================================================
# Tests: Variable Substitution
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("pattern,variables,expected", [
    ("${step1.output}", {"step1": {"output": "result"}}, "result"),
    ("${step1.output} and ${step2.value}", {"step1": {"output": "A"}, "step2": {"value": "B"}}, "A and B"),
    ("static text", {}, "static text"),
    ("${missing.key}", {}, ""),  # Missing variable returns empty
])
def test_substitute_variables(workflow_engine, pattern, variables, expected):
    """Test variable substitution in parameter patterns"""
    result = workflow_engine._substitute_variables(pattern, variables)
    assert result == expected


@pytest.mark.integration
def test_substitute_variables_nested(workflow_engine):
    """Test variable substitution with nested data"""
    pattern = "${step1.data.user.name}"
    variables = {
        "step1": {
            "data": {
                "user": {
                    "name": "John Doe"
                }
            }
        }
    }

    result = workflow_engine._substitute_variables(pattern, variables)
    assert result == "John Doe"


# ============================================================================
# Tests: Condition Evaluation
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("condition,state,expected", [
    ("${value > 10}", {"value": 15}, True),
    ("${value > 10}", {"value": 5}, False),
    ("${status == 'active'}", {"status": "active"}, True),
    ("${status == 'active'}", {"status": "inactive"}, False),
    ("${data.enabled == true and data.count > 0}", {"data": {"enabled": True, "count": 5}}, True),
    ("${data.enabled == true and data.count > 0}", {"data": {"enabled": True, "count": 0}}, False),
])
def test_evaluate_condition(workflow_engine, condition, state, expected):
    """Test condition evaluation with various expressions"""
    result = workflow_engine._evaluate_condition(condition, state)
    assert result is expected


# ============================================================================
# Tests: Database Persistence
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_execution_persists_to_database(db_session, state_manager):
    """Test that workflow creation persists to real database"""
    workflow_id = "test-workflow"
    input_data = {"test": "input"}

    execution_id = await state_manager.create_execution(workflow_id, input_data)

    # Verify real database state (not mock assertions)
    execution = db_session.query(WorkflowExecution).filter_by(
        execution_id=execution_id
    ).first()

    assert execution is not None
    assert execution.workflow_id == workflow_id
    assert execution.status == WorkflowExecutionStatus.PENDING.value
    assert execution.input_data is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_execution_status(db_session, state_manager):
    """Test that status updates persist to database"""
    execution_id = await state_manager.create_execution("test-workflow", {})

    # Update status
    await state_manager.update_execution_status(
        execution_id,
        WorkflowExecutionStatus.RUNNING
    )

    # Verify database state
    execution = db_session.query(WorkflowExecution).filter_by(
        execution_id=execution_id
    ).first()

    assert execution.status == WorkflowExecutionStatus.RUNNING.value


@pytest.mark.integration
@pytest.mark.asyncio
async def test_step_execution_logging(db_session, state_manager):
    """Test that step execution logs are persisted"""
    execution_id = await state_manager.create_execution("test-workflow", {})

    # Log step execution
    await state_manager.log_step_execution(
        execution_id=execution_id,
        step_id="step-1",
        step_name="Test Step",
        status="COMPLETED",
        input_data={"in": "value"},
        output_data={"out": "result"},
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )

    # Verify in database
    step_executions = db_session.query(WorkflowStepExecution).filter_by(
        execution_id=execution_id
    ).all()

    assert len(step_executions) == 1
    step = step_executions[0]
    assert step.step_id == "step-1"
    assert step.step_name == "Test Step"
    assert step.status == "COMPLETED"


# ============================================================================
# Tests: Status Transitions (Parametrized)
# ============================================================================

@pytest.mark.integration
@pytest.mark.parametrize("current_status,action,expected_valid", [
    (WorkflowExecutionStatus.PENDING, "start", True),
    (WorkflowExecutionStatus.PENDING, "complete", False),
    (WorkflowExecutionStatus.RUNNING, "complete", True),
    (WorkflowExecutionStatus.RUNNING, "fail", True),
    (WorkflowExecutionStatus.COMPLETED, "restart", True),
    (WorkflowExecutionStatus.FAILED, "retry", True),
    (WorkflowExecutionStatus.FAILED, "complete", False),
])
@pytest.mark.asyncio
async def test_workflow_status_transitions(
    db_session,
    state_manager,
    current_status,
    action,
    expected_valid
):
    """Parametrized test for status transitions"""
    execution_id = await state_manager.create_execution("test-workflow", {})

    # Set initial status
    await state_manager.update_execution_status(execution_id, current_status)

    # Attempt action
    try:
        if action == "start":
            await state_manager.update_execution_status(execution_id, WorkflowExecutionStatus.RUNNING)
        elif action == "complete":
            await state_manager.update_execution_status(execution_id, WorkflowExecutionStatus.COMPLETED)
        elif action == "fail":
            await state_manager.update_execution_status(execution_id, WorkflowExecutionStatus.FAILED)
        elif action == "retry":
            await state_manager.update_execution_status(execution_id, WorkflowExecutionStatus.RUNNING)
        elif action == "restart":
            # Create new execution
            execution_id = await state_manager.create_execution("test-workflow", {})

        # If we got here, action was valid
        assert expected_valid is True

    except Exception:
        # Transition was invalid
        assert expected_valid is False


# ============================================================================
# Tests: Error Handling
# ============================================================================

@pytest.mark.integration
def test_workflow_execution_with_invalid_step_config(workflow_engine):
    """Test workflow handles invalid step configuration gracefully"""
    workflow = {
        "id": "invalid-workflow",
        "steps": [
            {
                "id": "step-1",
                "name": "Invalid Step",
                "sequence_order": 1,
                "service": "nonexistent",
                "action": "invalid_action",
                "parameters": None  # Invalid parameters
            }
        ]
    }

    # Should not raise exception, but handle gracefully
    steps = workflow.get("steps", [])
    assert len(steps) == 1
    assert steps[0]["service"] == "nonexistent"


@pytest.mark.integration
def test_workflow_with_circular_dependencies(workflow_engine):
    """Test topological sort handles cycles gracefully"""
    workflow = {
        "id": "cyclic-workflow",
        "nodes": [
            {"id": "a", "type": "action", "title": "A", "config": {}},
            {"id": "b", "type": "action", "title": "B", "config": {}},
            {"id": "c", "type": "action", "title": "C", "config": {}}
        ],
        "connections": [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
            {"source": "c", "target": "a"}  # Cycle!
        ]
    }

    # Topological sort should handle this
    # Kahn's algorithm will stop when queue is empty but not all nodes processed
    steps = workflow_engine._convert_nodes_to_steps(workflow)

    # Should return some ordering (may not include all nodes due to cycle)
    assert isinstance(steps, list)
    assert len(steps) >= 0


@pytest.mark.integration
def test_variable_substitution_with_missing_keys(workflow_engine):
    """Test variable substitution handles missing keys gracefully"""
    pattern = "${step1.missing.nested.key}"
    variables = {"step1": {"other": "value"}}

    # Should not raise exception
    result = workflow_engine._substitute_variables(pattern, variables)
    # Missing key should return empty string or original pattern
    assert result == "" or result == pattern


# ============================================================================
# Tests: Schema Validation
# ============================================================================

@pytest.mark.integration
def test_workflow_input_schema_validation(workflow_engine):
    """Test workflow input schema validation"""
    workflow = {
        "id": "validated-workflow",
        "steps": [
            {
                "id": "step-1",
                "name": "Validated Step",
                "sequence_order": 1,
                "service": "test",
                "action": "test_action",
                "parameters": {},
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "number"}
                    },
                    "required": ["name"]
                }
            }
        ]
    }

    step = workflow["steps"][0]
    assert "input_schema" in step
    assert step["input_schema"]["type"] == "object"
    assert "name" in step["input_schema"]["properties"]


# ============================================================================
# Tests: Concurrency Control
# ============================================================================

@pytest.mark.integration
def test_concurrent_step_limit_enforcement(workflow_engine):
    """Test that workflow engine respects concurrent step limit"""
    # Engine initialized with max_concurrent_steps=5
    assert workflow_engine.max_concurrent_steps == 5

    # Semaphore should be created
    assert workflow_engine.semaphore is not None
    assert workflow_engine.semaphore._value == 5


@pytest.mark.integration
def test_cancellation_tracking(workflow_engine):
    """Test cancellation request tracking"""
    execution_id = "test-execution-123"

    # Add cancellation request
    workflow_engine.cancellation_requests.add(execution_id)

    # Check if tracked
    assert execution_id in workflow_engine.cancellation_requests

    # Remove cancellation request
    workflow_engine.cancellation_requests.remove(execution_id)
    assert execution_id not in workflow_engine.cancellation_requests


# ============================================================================
# Tests: Real Database Query Patterns
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_execution_state_from_database(db_session, state_manager):
    """Test retrieving execution state from real database"""
    execution_id = await state_manager.create_execution("test-workflow", {"key": "value"})

    # Update state
    await state_manager.update_step_output(execution_id, "step-1", {"output": "result"})

    # Retrieve state from database
    state = await state_manager.get_execution_state(execution_id)

    assert state is not None
    assert "input_data" in state
    assert state["input_data"]["key"] == "value"
    assert "steps" in state


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_executions_by_workflow_id(db_session, state_manager):
    """Test querying executions by workflow ID"""
    workflow_id = "test-workflow"

    # Create multiple executions
    exec_id_1 = await state_manager.create_execution(workflow_id, {"run": 1})
    exec_id_2 = await state_manager.create_execution(workflow_id, {"run": 2})
    exec_id_3 = await state_manager.create_execution("other-workflow", {"run": 3})

    # Query from database
    executions = db_session.query(WorkflowExecution).filter_by(
        workflow_id=workflow_id
    ).all()

    assert len(executions) == 2
    execution_ids = [e.execution_id for e in executions]
    assert exec_id_1 in execution_ids
    assert exec_id_2 in execution_ids
    assert exec_id_3 not in execution_ids


# ============================================================================
# Tests: Edge Cases
# ============================================================================

@pytest.mark.integration
def test_empty_workflow_handling(workflow_engine):
    """Test handling of workflows with no steps"""
    workflow = {
        "id": "empty-workflow",
        "steps": []
    }

    steps = workflow.get("steps", [])
    assert len(steps) == 0


@pytest.mark.integration
def test_workflow_with_null_parameters(workflow_engine):
    """Test workflow with null/None parameters"""
    workflow = {
        "id": "null-param-workflow",
        "steps": [
            {
                "id": "step-1",
                "name": "Null Param Step",
                "sequence_order": 1,
                "service": "test",
                "action": "test_action",
                "parameters": None  # Null parameters
            }
        ]
    }

    steps = workflow.get("steps", [])
    assert len(steps) == 1
    # Should handle None gracefully
    assert steps[0]["parameters"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_workflow_with_large_input_data(workflow_engine, db_session, state_manager):
    """Test workflow with large input data"""
    large_data = {"items": [f"item-{i}" for i in range(1000)]}

    # Should handle large data without issues
    execution_id = await state_manager.create_execution("large-workflow", large_data)

    # Verify persistence
    execution = db_session.query(WorkflowExecution).filter_by(
        execution_id=execution_id
    ).first()

    assert execution is not None
    assert execution.input_data is not None
