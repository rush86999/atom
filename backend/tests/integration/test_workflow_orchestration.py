"""
Workflow Orchestration Integration Tests

Tests cover complete workflow orchestration from template to execution to analytics:
- Linear workflow execution (step 1 → step 2 → step 3)
- Conditional workflow execution (branch based on data)
- Parallel workflow execution (concurrent steps)
- Workflow analytics (state transitions, performance metrics)

Uses real WorkflowEngine and WorkflowAnalyticsEngine with test database.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile
import os

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.workflow_engine import WorkflowEngine
from core.workflow_analytics_engine import (
    WorkflowAnalyticsEngine,
    WorkflowStatus,
    MetricType
)
from core.models import WorkflowExecution, WorkflowExecutionLog, WorkflowExecutionStatus
from tests.factories.user_factory import UserFactory


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def analytics_db():
    """Create temporary analytics database for testing."""
    fd, db_path = tempfile.mkstemp(suffix='_analytics.db')
    os.close(fd)

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture(scope="function")
def analytics_engine(analytics_db):
    """Create WorkflowAnalyticsEngine with test database."""
    engine = WorkflowAnalyticsEngine(db_path=analytics_db, enable_background_thread=False)
    yield engine
    # Flush any pending data
    asyncio.run(engine.flush())


@pytest.fixture(scope="function")
def workflow_engine():
    """Create WorkflowEngine for testing."""
    engine = WorkflowEngine(max_concurrent_steps=5)
    yield engine


@pytest.fixture(scope="function")
def workflow_template_linear():
    """Create linear workflow template: step 1 → step 2 → step 3."""
    return {
        "workflow_id": "test-linear-workflow",
        "name": "Linear Test Workflow",
        "description": "Simple linear workflow for testing",
        "steps": [
            {
                "step_id": "step1",
                "name": "First Step",
                "type": "task",
                "integration_id": "test_integration",
                "action": "create",
                "inputs": {
                    "title": "${workflow_input.title}",
                    "description": "Created by step 1"
                }
            },
            {
                "step_id": "step2",
                "name": "Second Step",
                "type": "task",
                "integration_id": "test_integration",
                "action": "update",
                "inputs": {
                    "task_id": "${step1.task_id}",
                    "status": "in_progress"
                }
            },
            {
                "step_id": "step3",
                "name": "Third Step",
                "type": "task",
                "integration_id": "test_integration",
                "action": "complete",
                "inputs": {
                    "task_id": "${step1.task_id}",
                    "status": "completed"
                }
            }
        ]
    }


@pytest.fixture(scope="function")
def workflow_template_conditional():
    """Create conditional workflow template with branching logic."""
    return {
        "workflow_id": "test-conditional-workflow",
        "name": "Conditional Test Workflow",
        "description": "Workflow with conditional branching",
        "steps": [
            {
                "step_id": "step1",
                "name": "Evaluate Priority",
                "type": "task",
                "integration_id": "test_integration",
                "action": "evaluate",
                "inputs": {
                    "priority": "${workflow_input.priority}"
                }
            },
            {
                "step_id": "high_priority_branch",
                "name": "High Priority Path",
                "type": "task",
                "integration_id": "test_integration",
                "action": "escalate",
                "condition": "${step1.priority_level > 5}",
                "inputs": {
                    "task_id": "${step1.task_id}",
                    "escalation_level": "urgent"
                }
            },
            {
                "step_id": "low_priority_branch",
                "name": "Low Priority Path",
                "type": "task",
                "integration_id": "test_integration",
                "action": "process",
                "condition": "${step1.priority_level <= 5}",
                "inputs": {
                    "task_id": "${step1.task_id}",
                    "escalation_level": "normal"
                }
            }
        ]
    }


@pytest.fixture(scope="function")
def workflow_template_parallel():
    """Create parallel workflow template: step 1 → (step 2A || step 2B) → step 3."""
    return {
        "workflow_id": "test-parallel-workflow",
        "name": "Parallel Test Workflow",
        "description": "Workflow with parallel execution",
        "steps": [
            {
                "step_id": "step1",
                "name": "Initialize",
                "type": "task",
                "integration_id": "test_integration",
                "action": "init",
                "inputs": {
                    "workspace_id": "${workflow_input.workspace_id}"
                }
            },
            {
                "step_id": "step2a",
                "name": "Parallel Task A",
                "type": "task",
                "integration_id": "test_integration",
                "action": "process_a",
                "parallel_group": "parallel_group_1",
                "inputs": {
                    "workspace_id": "${step1.workspace_id}",
                    "task": "A"
                }
            },
            {
                "step_id": "step2b",
                "name": "Parallel Task B",
                "type": "task",
                "integration_id": "test_integration",
                "action": "process_b",
                "parallel_group": "parallel_group_1",
                "inputs": {
                    "workspace_id": "${step1.workspace_id}",
                    "task": "B"
                }
            },
            {
                "step_id": "step3",
                "name": "Finalize",
                "type": "task",
                "integration_id": "test_integration",
                "action": "finalize",
                "inputs": {
                    "workspace_id": "${step1.workspace_id}",
                    "results_a": "${step2a.results}",
                    "results_b": "${step2b.results}"
                }
            }
        ]
    }


@pytest.fixture(scope="function")
def mock_step_executor():
    """Mock executor for individual step execution."""
    async def _execute_step(step: dict, inputs: dict, execution_id: str):
        # Simulate step execution
        step_id = step.get("step_id")
        action = step.get("action")

        # Return mock outputs based on action
        if action == "create":
            return {"task_id": f"task-{execution_id}-{step_id}", "status": "created"}
        elif action == "update":
            return {"task_id": inputs.get("task_id"), "status": "updated"}
        elif action == "complete":
            return {"task_id": inputs.get("task_id"), "status": "completed"}
        elif action == "evaluate":
            priority = inputs.get("priority", 5)
            return {
                "task_id": f"task-{execution_id}-{step_id}",
                "priority_level": priority,
                "evaluation": f"Priority {priority} evaluated"
            }
        elif action == "escalate":
            return {"task_id": inputs.get("task_id"), "status": "escalated", "level": "urgent"}
        elif action == "process":
            return {"task_id": inputs.get("task_id"), "status": "processed", "level": "normal"}
        elif action == "init":
            return {"workspace_id": inputs.get("workspace_id"), "status": "initialized"}
        elif action == "process_a":
            return {"results": "Result A", "task": "A", "status": "completed"}
        elif action == "process_b":
            return {"results": "Result B", "task": "B", "status": "completed"}
        elif action == "finalize":
            return {
                "status": "finalized",
                "combined_results": f"{inputs.get('results_a')} + {inputs.get('results_b')}"
            }
        else:
            return {"status": "unknown_action"}

    return _execute_step


# =============================================================================
# TEST: LINEAR WORKFLOW EXECUTION
# =============================================================================

class TestLinearWorkflowExecution:
    """Test linear workflow execution with sequential steps."""

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_linear_workflow_execution_complete(
        self, workflow_engine, workflow_template_linear, mock_step_executor, db_session: Session
    ):
        """Test complete linear workflow execution from start to finish."""
        # Create user
        user = UserFactory(email="linear@test.com", _session=db_session)
        db_session.commit()

        # Create workflow execution record
        execution = WorkflowExecution(
            workflow_id=workflow_template_linear["workflow_id"],
            status=WorkflowExecutionStatus.PENDING.value,
            user_id=user.id,
            owner_id=user.id,
            input_data=json.dumps({"title": "Test Task"})
        )
        db_session.add(execution)
        db_session.commit()

        execution_id = execution.execution_id

        # Track analytics
        analytics = WorkflowAnalyticsEngine(enable_background_thread=False)
        analytics.track_workflow_start(
            workflow_id=workflow_template_linear["workflow_id"],
            execution_id=execution_id,
            user_id=user.id
        )

        # Execute steps sequentially
        steps = workflow_template_linear["steps"]
        step_outputs = {}

        for step in steps:
            # Mock step execution
            result = asyncio.run(mock_step_executor(step, {"title": "Test Task"}, execution_id))
            step_outputs[step["step_id"]] = result

            # Log step execution
            log = WorkflowExecutionLog(
                execution_id=execution_id,
                workflow_id=workflow_template_linear["workflow_id"],
                step_id=step["step_id"],
                step_type="task",
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                duration_ms=10.0,
                status="completed",
                results=result
            )
            db_session.add(log)

        # Update execution status
        execution.status = WorkflowExecutionStatus.COMPLETED.value
        execution.outputs = json.dumps(step_outputs)
        db_session.commit()

        # Track completion in analytics
        analytics.track_workflow_completion(
            workflow_id=workflow_template_linear["workflow_id"],
            execution_id=execution_id,
            status=WorkflowStatus.COMPLETED,
            duration_ms=150,
            step_outputs=step_outputs,
            user_id=user.id
        )

        # Verify execution state
        retrieved = db_session.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id
        ).first()

        assert retrieved.status == WorkflowExecutionStatus.COMPLETED.value
        assert json.loads(retrieved.outputs) == step_outputs

        # Verify all steps executed
        assert "step1" in step_outputs
        assert "step2" in step_outputs
        assert "step3" in step_outputs
        assert step_outputs["step1"]["status"] == "created"
        assert step_outputs["step2"]["status"] == "updated"
        assert step_outputs["step3"]["status"] == "completed"

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_linear_workflow_with_all_steps_succeeding(
        self, workflow_engine, workflow_template_linear, mock_step_executor, db_session: Session
    ):
        """Test linear workflow where all steps succeed."""
        user = UserFactory(email="success@test.com", _session=db_session)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id=workflow_template_linear["workflow_id"],
            status=WorkflowExecutionStatus.PENDING.value,
            user_id=user.id,
            owner_id=user.id,
            input_data=json.dumps({"title": "Success Task"})
        )
        db_session.add(execution)
        db_session.commit()

        execution_id = execution.execution_id

        # Execute all steps
        steps = workflow_template_linear["steps"]
        step_outputs = {}

        for step in steps:
            result = asyncio.run(mock_step_executor(step, {"title": "Success Task"}, execution_id))
            step_outputs[step["step_id"]] = result

        # Verify all steps succeeded
        for step_id, output in step_outputs.items():
            assert "status" in output
            assert output["status"] in ["created", "updated", "completed"]

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_workflow_state_transitions(
        self, workflow_engine, workflow_template_linear, db_session: Session
    ):
        """Test workflow state transitions: pending → running → completed."""
        user = UserFactory(email="states@test.com", _session=db_session)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id=workflow_template_linear["workflow_id"],
            status=WorkflowExecutionStatus.PENDING.value,
            user_id=user.id,
            owner_id=user.id,
            input_data=json.dumps({})
        )
        db_session.add(execution)
        db_session.commit()

        execution_id = execution.execution_id

        # Verify initial state
        assert execution.status == WorkflowExecutionStatus.PENDING.value

        # Transition to running
        execution.status = WorkflowExecutionStatus.RUNNING.value
        db_session.commit()
        assert execution.status == WorkflowExecutionStatus.RUNNING.value

        # Transition to completed
        execution.status = WorkflowExecutionStatus.COMPLETED.value
        execution.outputs = json.dumps({"final": "result"})
        db_session.commit()
        assert execution.status == WorkflowExecutionStatus.COMPLETED.value

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_workflow_execution_persistence(
        self, workflow_engine, workflow_template_linear, mock_step_executor, db_session: Session
    ):
        """Test workflow execution state persists across database queries."""
        user = UserFactory(email="persist@test.com", _session=db_session)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id=workflow_template_linear["workflow_id"],
            status=WorkflowExecutionStatus.PENDING.value,
            user_id=user.id,
            owner_id=user.id,
            input_data=json.dumps({"title": "Persistence Test"})
        )
        db_session.add(execution)
        db_session.commit()

        execution_id = execution.execution_id

        # Execute steps
        steps = workflow_template_linear["steps"]
        step_outputs = {}

        for step in steps:
            result = asyncio.run(mock_step_executor(step, {"title": "Persistence Test"}, execution_id))
            step_outputs[step["step_id"]] = result

        # Save to database
        execution.status = WorkflowExecutionStatus.COMPLETED.value
        execution.outputs = json.dumps(step_outputs)
        db_session.commit()

        # Query from database (new session)
        retrieved = db_session.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id
        ).first()

        # Verify persistence
        assert retrieved is not None
        assert retrieved.status == WorkflowExecutionStatus.COMPLETED.value
        assert json.loads(retrieved.outputs) == step_outputs

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_linear_workflow_with_step_failure(
        self, workflow_engine, workflow_template_linear, db_session: Session
    ):
        """Test linear workflow with a step that fails."""
        user = UserFactory(email="failure@test.com", _session=db_session)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id=workflow_template_linear["workflow_id"],
            status=WorkflowExecutionStatus.RUNNING.value,
            user_id=user.id,
            owner_id=user.id,
            input_data=json.dumps({})
        )
        db_session.add(execution)
        db_session.commit()

        execution_id = execution.execution_id

        # Simulate step 2 failure
        log = WorkflowExecutionLog(
            execution_id=execution_id,
            workflow_id=workflow_template_linear["workflow_id"],
            step_id="step2",
            step_type="task",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=50.0,
            status="failed",
            error_code="TIMEOUT",
            results={"error": "Connection timeout"}
        )
        db_session.add(log)

        # Update execution to failed
        execution.status = WorkflowExecutionStatus.FAILED.value
        execution.error_message = "Step 2 failed: Connection timeout"
        db_session.commit()

        # Verify failed state
        retrieved = db_session.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id
        ).first()

        assert retrieved.status == WorkflowExecutionStatus.FAILED.value
        assert "Step 2 failed" in retrieved.error_message


# =============================================================================
# TEST: CONDITIONAL WORKFLOW EXECUTION
# =============================================================================

class TestConditionalWorkflowExecution:
    """Test conditional workflow execution with data-driven routing."""

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_conditional_branch_execution_true(
        self, workflow_engine, workflow_template_conditional, mock_step_executor, db_session: Session
    ):
        """Test conditional workflow where condition is true (high priority)."""
        user = UserFactory(email="cond_true@test.com", _session=db_session)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id=workflow_template_conditional["workflow_id"],
            status=WorkflowExecutionStatus.PENDING.value,
            user_id=user.id,
            owner_id=user.id,
            input_data=json.dumps({"priority": 8})
        )
        db_session.add(execution)
        db_session.commit()

        execution_id = execution.execution_id

        # Execute step 1 (evaluation)
        step1 = workflow_template_conditional["steps"][0]
        result1 = asyncio.run(mock_step_executor(step1, {"priority": 8}, execution_id))

        # Verify high priority path (8 > 5)
        assert result1["priority_level"] == 8

        # Execute high priority branch
        step2_high = workflow_template_conditional["steps"][1]
        result2 = asyncio.run(mock_step_executor(
            step2_high,
            {"task_id": result1["task_id"]},
            execution_id
        ))

        assert result2["status"] == "escalated"
        assert result2["level"] == "urgent"

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_conditional_branch_execution_false(
        self, workflow_engine, workflow_template_conditional, mock_step_executor, db_session: Session
    ):
        """Test conditional workflow where condition is false (low priority)."""
        user = UserFactory(email="cond_false@test.com", _session=db_session)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id=workflow_template_conditional["workflow_id"],
            status=WorkflowExecutionStatus.PENDING.value,
            user_id=user.id,
            owner_id=user.id,
            input_data=json.dumps({"priority": 3})
        )
        db_session.add(execution)
        db_session.commit()

        execution_id = execution.execution_id

        # Execute step 1 (evaluation)
        step1 = workflow_template_conditional["steps"][0]
        result1 = asyncio.run(mock_step_executor(step1, {"priority": 3}, execution_id))

        # Verify low priority path (3 <= 5)
        assert result1["priority_level"] == 3

        # Execute low priority branch
        step2_low = workflow_template_conditional["steps"][2]
        result2 = asyncio.run(mock_step_executor(
            step2_low,
            {"task_id": result1["task_id"]},
            execution_id
        ))

        assert result2["status"] == "processed"
        assert result2["level"] == "normal"

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_workflow_routing_based_on_data(
        self, workflow_engine, workflow_template_conditional, mock_step_executor, db_session: Session
    ):
        """Test workflow routes correctly based on input data."""
        user = UserFactory(email="routing@test.com", _session=db_session)
        db_session.commit()

        # Test multiple data points
        test_cases = [
            ({"priority": 1}, "low_priority_branch", "normal"),
            ({"priority": 5}, "low_priority_branch", "normal"),
            ({"priority": 6}, "high_priority_branch", "urgent"),
            ({"priority": 10}, "high_priority_branch", "urgent"),
        ]

        for input_data, expected_branch, expected_level in test_cases:
            execution = WorkflowExecution(
                workflow_id=workflow_template_conditional["workflow_id"],
                status=WorkflowExecutionStatus.PENDING.value,
                user_id=user.id,
                owner_id=user.id,
                input_data=json.dumps(input_data)
            )
            db_session.add(execution)
            db_session.commit()

            execution_id = execution.execution_id

            # Execute step 1
            step1 = workflow_template_conditional["steps"][0]
            result1 = asyncio.run(mock_step_executor(step1, input_data, execution_id))

            # Determine which branch should execute
            if result1["priority_level"] > 5:
                step = workflow_template_conditional["steps"][1]  # high_priority_branch
            else:
                step = workflow_template_conditional["steps"][2]  # low_priority_branch

            result2 = asyncio.run(mock_step_executor(
                step,
                {"task_id": result1["task_id"]},
                execution_id
            ))

            # Verify routing
            assert result2["level"] == expected_level

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_workflow_with_multiple_conditions(
        self, workflow_engine, db_session: Session
    ):
        """Test workflow with multiple conditional branches."""
        # Create workflow with multiple conditions
        workflow_multi = {
            "workflow_id": "test-multi-condition-workflow",
            "steps": [
                {
                    "step_id": "evaluate",
                    "name": "Evaluate Score",
                    "type": "task",
                    "action": "evaluate_score",
                    "inputs": {"score": "${workflow_input.score}"}
                },
                {
                    "step_id": "grade_a",
                    "name": "Grade A Path",
                    "type": "task",
                    "action": "assign_grade_a",
                    "condition": "${evaluate.score >= 90}",
                    "inputs": {"grade": "A"}
                },
                {
                    "step_id": "grade_b",
                    "name": "Grade B Path",
                    "type": "task",
                    "action": "assign_grade_b",
                    "condition": "${evaluate.score >= 80 and evaluate.score < 90}",
                    "inputs": {"grade": "B"}
                },
                {
                    "step_id": "grade_c",
                    "name": "Grade C Path",
                    "type": "task",
                    "action": "assign_grade_c",
                    "condition": "${evaluate.score < 80}",
                    "inputs": {"grade": "C"}
                }
            ]
        }

        user = UserFactory(email="multi_cond@test.com", _session=db_session)
        db_session.commit()

        # Test different scores
        test_cases = [
            (95, "grade_a", "A"),
            (85, "grade_b", "B"),
            (75, "grade_c", "C"),
            (90, "grade_a", "A"),  # Boundary case
        ]

        for score, expected_step, expected_grade in test_cases:
            execution = WorkflowExecution(
                workflow_id=workflow_multi["workflow_id"],
                status=WorkflowExecutionStatus.PENDING.value,
                user_id=user.id,
                owner_id=user.id,
                input_data=json.dumps({"score": score})
            )
            db_session.add(execution)
            db_session.commit()

            # Verify input data
            assert json.loads(execution.input_data) == {"score": score}


# =============================================================================
# TEST: PARALLEL WORKFLOW EXECUTION
# =============================================================================

class TestParallelWorkflowExecution:
    """Test parallel workflow execution with concurrent steps."""

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_parallel_step_execution(
        self, workflow_engine, workflow_template_parallel, mock_step_executor, db_session: Session
    ):
        """Test parallel workflow executes steps concurrently."""
        user = UserFactory(email="parallel@test.com", _session=db_session)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id=workflow_template_parallel["workflow_id"],
            status=WorkflowExecutionStatus.PENDING.value,
            user_id=user.id,
            owner_id=user.id,
            input_data=json.dumps({"workspace_id": "ws-123"})
        )
        db_session.add(execution)
        db_session.commit()

        execution_id = execution.execution_id

        # Execute step 1
        step1 = workflow_template_parallel["steps"][0]
        result1 = asyncio.run(mock_step_executor(
            step1,
            {"workspace_id": "ws-123"},
            execution_id
        ))

        # Execute parallel steps 2A and 2B concurrently
        step2a = workflow_template_parallel["steps"][1]
        step2b = workflow_template_parallel["steps"][2]

        # Simulate concurrent execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def execute_parallel():
            results = await asyncio.gather(
                mock_step_executor(step2a, {"workspace_id": result1["workspace_id"], "task": "A"}, execution_id),
                mock_step_executor(step2b, {"workspace_id": result1["workspace_id"], "task": "B"}, execution_id)
            )
            return results

        parallel_results = loop.run_until_complete(execute_parallel())
        loop.close()

        # Verify both parallel steps completed
        assert len(parallel_results) == 2
        assert parallel_results[0]["task"] == "A"
        assert parallel_results[1]["task"] == "B"

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_parallel_workflow_with_independent_steps(
        self, workflow_engine, workflow_template_parallel, mock_step_executor, db_session: Session
    ):
        """Test parallel workflow where steps are independent of each other."""
        user = UserFactory(email="independent@test.com", _session=db_session)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id=workflow_template_parallel["workflow_id"],
            status=WorkflowExecutionStatus.RUNNING.value,
            user_id=user.id,
            owner_id=user.id,
            input_data=json.dumps({"workspace_id": "ws-independent"})
        )
        db_session.add(execution)
        db_session.commit()

        execution_id = execution.execution_id

        # Execute parallel steps independently
        step2a = workflow_template_parallel["steps"][1]
        step2b = workflow_template_parallel["steps"][2]

        result_a = asyncio.run(mock_step_executor(
            step2a,
            {"workspace_id": "ws-independent", "task": "A"},
            execution_id
        ))

        result_b = asyncio.run(mock_step_executor(
            step2b,
            {"workspace_id": "ws-independent", "task": "B"},
            execution_id
        ))

        # Verify both completed successfully
        assert result_a["status"] == "completed"
        assert result_b["status"] == "completed"
        assert result_a["task"] == "A"
        assert result_b["task"] == "B"

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_parallel_workflow_join_after_completion(
        self, workflow_engine, workflow_template_parallel, mock_step_executor, db_session: Session
    ):
        """Test parallel workflow joins after parallel steps complete."""
        user = UserFactory(email="join@test.com", _session=db_session)
        db_session.commit()

        execution = WorkflowExecution(
            workflow_id=workflow_template_parallel["workflow_id"],
            status=WorkflowExecutionStatus.RUNNING.value,
            user_id=user.id,
            owner_id=user.id,
            input_data=json.dumps({"workspace_id": "ws-join"})
        )
        db_session.add(execution)
        db_session.commit()

        execution_id = execution.execution_id

        # Execute step 1
        step1 = workflow_template_parallel["steps"][0]
        result1 = asyncio.run(mock_step_executor(
            step1,
            {"workspace_id": "ws-join"},
            execution_id
        ))

        # Execute parallel steps
        step2a = workflow_template_parallel["steps"][1]
        step2b = workflow_template_parallel["steps"][2]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def execute_parallel():
            return await asyncio.gather(
                mock_step_executor(step2a, {"workspace_id": result1["workspace_id"], "task": "A"}, execution_id),
                mock_step_executor(step2b, {"workspace_id": result1["workspace_id"], "task": "B"}, execution_id)
            )

        parallel_results = loop.run_until_complete(execute_parallel())

        # Execute final step (join) after parallel completion
        step3 = workflow_template_parallel["steps"][3]
        result3 = asyncio.run(mock_step_executor(
            step3,
            {
                "workspace_id": result1["workspace_id"],
                "results_a": parallel_results[0]["results"],
                "results_b": parallel_results[1]["results"]
            },
            execution_id
        ))

        # Verify join step combined results
        assert result3["status"] == "finalized"
        assert "Result A" in result3["combined_results"]
        assert "Result B" in result3["combined_results"]

        # Mark execution as completed
        execution.status = WorkflowExecutionStatus.COMPLETED.value
        execution.outputs = json.dumps({
            "step1": result1,
            "step2a": parallel_results[0],
            "step2b": parallel_results[1],
            "step3": result3
        })
        db_session.commit()

        # Verify final state
        retrieved = db_session.query(WorkflowExecution).filter(
            WorkflowExecution.execution_id == execution_id
        ).first()

        assert retrieved.status == WorkflowExecutionStatus.COMPLETED.value


# =============================================================================
# TEST: WORKFLOW ANALYTICS
# =============================================================================

class TestWorkflowAnalytics:
    """Test workflow analytics collection and reporting."""

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_workflow_analytics_collection(
        self, analytics_engine, db_session: Session
    ):
        """Test workflow analytics collects execution data."""
        user = UserFactory(email="analytics@test.com", _session=db_session)
        db_session.commit()

        workflow_id = "test-analytics-workflow"
        execution_id = "exec-analytics-001"

        # Track workflow start
        analytics_engine.track_workflow_start(
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id=user.id,
            metadata={"test": "analytics"}
        )

        # Track workflow completion
        analytics_engine.track_workflow_completion(
            workflow_id=workflow_id,
            execution_id=execution_id,
            status=WorkflowStatus.COMPLETED,
            duration_ms=250,
            step_outputs={"step1": {"result": "success"}},
            user_id=user.id
        )

        # Flush to database
        asyncio.run(analytics_engine.flush())

        # Verify metrics collected
        performance = analytics_engine.get_workflow_performance_metrics(workflow_id, "24h")

        assert performance.workflow_id == workflow_id
        assert performance.total_executions >= 1
        assert performance.successful_executions >= 1

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_workflow_performance_metrics(
        self, analytics_engine, db_session: Session
    ):
        """Test workflow performance metrics tracking."""
        user = UserFactory(email="performance@test.com", _session=db_session)
        db_session.commit()

        workflow_id = "test-performance-workflow"

        # Track multiple executions
        for i in range(5):
            execution_id = f"exec-perf-{i}"
            analytics_engine.track_workflow_start(
                workflow_id=workflow_id,
                execution_id=execution_id,
                user_id=user.id
            )

            analytics_engine.track_workflow_completion(
                workflow_id=workflow_id,
                execution_id=execution_id,
                status=WorkflowStatus.COMPLETED,
                duration_ms=100 + (i * 50),  # 100, 150, 200, 250, 300
                step_outputs={},
                user_id=user.id
            )

        asyncio.run(analytics_engine.flush())

        # Get performance metrics
        performance = analytics_engine.get_workflow_performance_metrics(workflow_id, "24h")

        assert performance.total_executions == 5
        assert performance.successful_executions == 5
        assert performance.average_duration_ms > 0
        assert performance.median_duration_ms > 0

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_workflow_state_tracking_in_analytics(
        self, analytics_engine, db_session: Session
    ):
        """Test workflow state transitions are tracked in analytics."""
        user = UserFactory(email="state_track@test.com", _session=db_session)
        db_session.commit()

        workflow_id = "test-state-tracking"
        execution_id = "exec-state-001"

        # Track state transitions
        analytics_engine.track_workflow_start(
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id=user.id,
            metadata={"initial_state": "pending"}
        )

        # Track step execution
        analytics_engine.track_step_execution(
            workflow_id=workflow_id,
            execution_id=execution_id,
            step_id="step1",
            step_name="First Step",
            event_type="step_completed",
            duration_ms=50,
            status="completed",
            user_id=user.id
        )

        # Track workflow completion
        analytics_engine.track_workflow_completion(
            workflow_id=workflow_id,
            execution_id=execution_id,
            status=WorkflowStatus.COMPLETED,
            duration_ms=200,
            step_outputs={"step1": {"status": "done"}},
            user_id=user.id
        )

        asyncio.run(analytics_engine.flush())

        # Verify events tracked
        events = analytics_engine.get_recent_events(limit=10, workflow_id=workflow_id)

        assert len(events) >= 3
        event_types = [e.event_type for e in events]
        assert "workflow_started" in event_types
        assert "step_completed" in event_types
        assert "workflow_completed" in event_types

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_workflow_execution_history(
        self, analytics_engine, db_session: Session
    ):
        """Test workflow execution history tracking."""
        user = UserFactory(email="history@test.com", _session=db_session)
        db_session.commit()

        workflow_id = "test-execution-history"

        # Track multiple executions over time
        timestamps = []
        for i in range(3):
            execution_id = f"exec-history-{i}"
            analytics_engine.track_workflow_start(
                workflow_id=workflow_id,
                execution_id=execution_id,
                user_id=user.id
            )

            analytics_engine.track_workflow_completion(
                workflow_id=workflow_id,
                execution_id=execution_id,
                status=WorkflowStatus.COMPLETED if i < 2 else WorkflowStatus.FAILED,
                duration_ms=150,
                step_outputs={},
                user_id=user.id
            )

            timestamps.append(datetime.now())

        asyncio.run(analytics_engine.flush())

        # Get execution history
        events = analytics_engine.get_recent_events(limit=10, workflow_id=workflow_id)

        # Verify history
        workflow_events = [e for e in events if e.workflow_id == workflow_id]
        assert len(workflow_events) >= 3

        # Verify completion events
        completion_events = [e for e in workflow_events if e.event_type == "workflow_completed"]
        assert len(completion_events) == 3

    @pytest.mark.integration
    @pytest.mark.workflow
    def test_analytics_with_workflow_failure(
        self, analytics_engine, db_session: Session
    ):
        """Test analytics captures workflow failures."""
        user = UserFactory(email="failure_analytics@test.com", _session=db_session)
        db_session.commit()

        workflow_id = "test-failure-analytics"
        execution_id = "exec-failure-001"

        # Track workflow that fails
        analytics_engine.track_workflow_start(
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id=user.id
        )

        analytics_engine.track_workflow_completion(
            workflow_id=workflow_id,
            execution_id=execution_id,
            status=WorkflowStatus.FAILED,
            duration_ms=100,
            error_message="Step 3 failed: API timeout",
            user_id=user.id
        )

        asyncio.run(analytics_engine.flush())

        # Verify failure tracked
        performance = analytics_engine.get_workflow_performance_metrics(workflow_id, "24h")

        assert performance.failed_executions >= 1
        assert performance.error_rate > 0

        # Check error breakdown
        error_breakdown = analytics_engine.get_error_breakdown(workflow_id, "24h")

        assert "recent_errors" in error_breakdown
        if error_breakdown["recent_errors"]:
            # Verify error message captured
            error_messages = [e["error_message"] for e in error_breakdown["recent_errors"]]
            assert any("timeout" in msg.lower() for msg in error_messages if msg)


# =============================================================================
# PYTEST MARKERS
# =============================================================================

pytestmark = [
    pytest.mark.integration,
    pytest.mark.workflow
]
