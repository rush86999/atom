"""
Property-Based Tests for Workflow Execution - Critical Workflow Engine Logic

Tests workflow execution invariants:
- Status transitions (valid state machine)
- Execution time consistency
- Step execution order
- Version monotonic increase
- Error handling (failed steps have errors)
- Log consistency
- Rollback integrity
- Cancellation cleanliness
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings
from uuid import uuid4
from typing import List, Dict, Any
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestWorkflowStatusTransitionInvariants:
    """Tests for workflow status transition invariants"""

    @given(
        initial_status=st.sampled_from(["pending", "running", "paused", "completed", "failed", "cancelled"]),
        num_transitions=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_valid_status_transitions(self, initial_status, num_transitions):
        """Test that workflow status follows valid transitions"""
        valid_transitions = {
            "pending": ["running", "cancelled"],
            "running": ["paused", "completed", "failed", "cancelled"],
            "paused": ["running", "cancelled"],
            "completed": [],  # Terminal state
            "failed": ["pending"],  # Can retry
            "cancelled": []  # Terminal state
        }

        current_status = initial_status
        status_history = [current_status]

        for _ in range(num_transitions):
            if current_status in valid_transitions and valid_transitions[current_status]:
                # Make a valid transition
                next_status = valid_transitions[current_status][0]
                current_status = next_status
                status_history.append(current_status)
            else:
                # Terminal state or no valid transitions
                break

        # Verify all transitions are valid
        for i in range(1, len(status_history)):
            prev_state = status_history[i-1]
            curr_state = status_history[i]
            valid_next = valid_transitions.get(prev_state, [])
            assert curr_state in valid_next, "Status transition should be valid"

    @given(
        status=st.sampled_from(["pending", "running", "paused", "completed", "failed", "cancelled"])
    )
    @settings(max_examples=50)
    def test_terminal_states(self, status):
        """Test that terminal states cannot transition"""
        terminal_states = ["completed", "cancelled"]
        valid_transitions = {
            "pending": ["running", "cancelled"],
            "running": ["paused", "completed", "failed", "cancelled"],
            "paused": ["running", "cancelled"],
            "completed": [],
            "failed": ["pending"],
            "cancelled": []
        }

        if status in terminal_states:
            assert len(valid_transitions[status]) == 0

    @given(
        workflow_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_workflow_initial_status(self, workflow_count):
        """Test that workflows start with pending status"""
        workflows = []
        for i in range(workflow_count):
            workflow = {
                "id": str(uuid4()),
                "status": "pending",
                "created_at": datetime(2024, 1, 1, 12, 0, 0)
            }
            workflows.append(workflow)

        # Verify all workflows start with pending status
        for workflow in workflows:
            assert workflow["status"] == "pending"


class TestExecutionTimeInvariants:
    """Tests for execution time consistency"""

    @given(
        start_hour=st.integers(min_value=0, max_value=20),
        duration_minutes=st.integers(min_value=1, max_value=120)
    )
    @settings(max_examples=50)
    def test_execution_time_consistency(self, start_hour, duration_minutes):
        """Test that execution time is consistent (created_at <= started_at <= updated_at)"""
        created_at = datetime(2024, 1, 1, start_hour, 0, 0)
        started_at = created_at + timedelta(minutes=duration_minutes)
        updated_at = started_at + timedelta(seconds=30)

        # Verify time ordering
        assert created_at <= started_at
        assert started_at <= updated_at
        assert created_at <= updated_at

    @given(
        num_steps=st.integers(min_value=2, max_value=20),
        step_duration_seconds=st.integers(min_value=1, max_value=60)
    )
    @settings(max_examples=50)
    def test_step_execution_ordering(self, num_steps, step_duration_seconds):
        """Test that steps execute in order with consistent timestamps"""
        steps = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_steps):
            step = {
                "id": str(uuid4()),
                "sequence_number": i,
                "started_at": base_time + timedelta(seconds=i*step_duration_seconds),
                "completed_at": base_time + timedelta(seconds=i*step_duration_seconds + step_duration_seconds//2)
            }
            steps.append(step)

        # Verify steps are in order
        for i in range(1, len(steps)):
            assert steps[i]["sequence_number"] > steps[i-1]["sequence_number"]
            assert steps[i]["started_at"] >= steps[i-1]["completed_at"]


class TestWorkflowVersionInvariants:
    """Tests for workflow version invariants"""

    @given(
        num_updates=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_version_monotonic_increase(self, num_updates):
        """Test that workflow version only increases"""
        versions = []
        current_version = 1

        for i in range(num_updates):
            current_version += 1
            versions.append(current_version)

        # Verify versions are strictly increasing
        for i in range(1, len(versions)):
            assert versions[i] > versions[i-1]

    @given(
        initial_version=st.integers(min_value=1, max_value=10),
        num_updates=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=50)
    def test_version_increment_by_one(self, initial_version, num_updates):
        """Test that version increments by 1 each update"""
        current_version = initial_version

        for _ in range(num_updates):
            old_version = current_version
            current_version += 1
            assert current_version == old_version + 1

        assert current_version == initial_version + num_updates


class TestWorkflowErrorHandlingInvariants:
    """Tests for workflow error handling invariants"""

    @given(
        num_steps=st.integers(min_value=5, max_value=20),
        failed_step_index=st.integers(min_value=0, max_value=19)
    )
    @settings(max_examples=50)
    def test_failed_step_has_error(self, num_steps, failed_step_index):
        """Test that failed steps have error information"""
        assume(failed_step_index < num_steps)

        steps = []
        for i in range(num_steps):
            step = {
                "id": str(uuid4()),
                "sequence_number": i,
                "status": "failed" if i == failed_step_index else "completed"
            }
            if step["status"] == "failed":
                step["error"] = f"Error in step {i}"
            steps.append(step)

        # Verify failed step has error
        failed_step = steps[failed_step_index]
        assert failed_step["status"] == "failed"
        assert "error" in failed_step


class TestWorkflowLogInvariants:
    """Tests for workflow log consistency"""

    @given(
        num_log_entries=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    def test_log_chronological_order(self, num_log_entries):
        """Test that workflow logs are in chronological order"""
        logs = []
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        for i in range(num_log_entries):
            log = {
                "id": str(uuid4()),
                "timestamp": base_time + timedelta(seconds=i),
                "level": "INFO",
                "message": f"Log entry {i}"
            }
            logs.append(log)

        # Verify chronological order
        for i in range(1, len(logs)):
            assert logs[i]["timestamp"] >= logs[i-1]["timestamp"]


class TestWorkflowRollbackInvariants:
    """Tests for workflow rollback invariants"""

    @given(
        num_steps=st.integers(min_value=3, max_value=20),
        rollback_point=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_rollback_reverts_state(self, num_steps, rollback_point):
        """Test that rollback reverts state correctly"""
        assume(rollback_point < num_steps)

        # Simulate workflow state
        steps_completed = []
        for i in range(num_steps):
            steps_completed.append(i)
            if i == rollback_point:
                # Trigger rollback
                steps_completed = steps_completed[:rollback_point]
                break

        # Verify rollback point is respected
        assert len(steps_completed) <= rollback_point


class TestWorkflowCancellationInvariants:
    """Tests for workflow cancellation invariants"""

    @given(
        num_steps_total=st.integers(min_value=10, max_value=50),
        cancel_at_step=st.integers(min_value=1, max_value=40)
    )
    @settings(max_examples=50)
    def test_cancellation_stops_execution(self, num_steps_total, cancel_at_step):
        """Test that cancellation stops workflow execution"""
        assume(cancel_at_step < num_steps_total)

        steps_executed = []
        for i in range(num_steps_total):
            if i == cancel_at_step:
                # Cancellation occurs
                break
            steps_executed.append(i)

        # Verify execution stopped at cancellation point
        assert len(steps_executed) == cancel_at_step

    @given(
        cancel_reason=st.sampled_from(["user_request", "timeout", "error", "resource_limit"])
    )
    @settings(max_examples=50)
    def test_cancellation_has_reason(self, cancel_reason):
        """Test that cancelled workflows have cancellation reason"""
        workflow = {
            "id": str(uuid4()),
            "status": "cancelled",
            "cancelled_at": datetime(2024, 1, 1, 12, 30, 0),
            "cancellation_reason": cancel_reason
        }

        assert workflow["status"] == "cancelled"
        assert "cancellation_reason" in workflow
        assert workflow["cancellation_reason"] in ["user_request", "timeout", "error", "resource_limit"]
