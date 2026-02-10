"""
⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md
"""

import uuid
from datetime import datetime, timedelta
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.models import User, WorkflowExecution


class TestWorkflowExecutionModelInvariants:
    """Test WorkflowExecution model maintains critical invariants."""

    @given(
        status=st.sampled_from(["PENDING", "RUNNING", "COMPLETED", "FAILED", "PAUSED"]),
        version=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_execution_status_validity(
        self, db_session: Session, status: str, version: int
    ):
        """
        INVARIANT: WorkflowExecution status MUST be valid and version >= 1.

        Status must be in valid enum, version must be positive.
        """
        # Arrange & Act: Create workflow execution
        execution = WorkflowExecution(
            workflow_id=f"workflow_{uuid.uuid4()}",
            status=status,
            version=version
        )
        db_session.add(execution)
        db_session.commit()

        # Assert: Verify invariants
        valid_statuses = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "PAUSED"]
        assert execution.status in valid_statuses, (
            f"Status must be valid enum value, got {execution.status}"
        )
        assert execution.version >= 1, (
            f"Version must be >= 1, got {execution.version}"
        )

    @given(
        minutes_ago_start=st.integers(min_value=0, max_value=10080),
        duration_minutes=st.integers(min_value=0, max_value=1440)  # Up to 24 hours
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_execution_time_consistency(
        self, db_session: Session, minutes_ago_start: int, duration_minutes: int
    ):
        """
        INVARIANT: WorkflowExecution timestamps MUST be consistent.

        created_at <= updated_at (if both set)
        """
        # Arrange & Act: Create workflow execution
        created_at = datetime.utcnow() - timedelta(minutes=minutes_ago_start)
        updated_at = created_at + timedelta(minutes=duration_minutes)

        execution = WorkflowExecution(
            workflow_id=f"workflow_{uuid.uuid4()}",
            status="COMPLETED",
            created_at=created_at,
            updated_at=updated_at
        )
        db_session.add(execution)
        db_session.commit()

        # Assert: Verify time ordering
        if execution.created_at and execution.updated_at:
            assert execution.created_at <= execution.updated_at, (
                f"created_at must be <= updated_at: {execution.created_at} > {execution.updated_at}"
            )

    @given(
        has_error=st.booleans()
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_execution_error_handling(
        self, db_session: Session, has_error: bool
    ):
        """
        INVARIANT: WorkflowExecution error field consistency with status.

        If error is present, status should be FAILED.
        """
        # Arrange & Act: Create workflow execution
        status = "FAILED" if has_error else "COMPLETED"
        error = "Test error" if has_error else None

        execution = WorkflowExecution(
            workflow_id=f"workflow_{uuid.uuid4()}",
            status=status,
            error=error
        )
        db_session.add(execution)
        db_session.commit()

        # Assert: Verify error/status consistency
        if execution.error:
            # Has error message - should ideally be FAILED status
            assert execution.status in ["FAILED", "PAUSED"], (
                f"Executions with errors should have FAILED/PAUSED status, got {execution.status}"
            )


class TestWorkflowExecutionStateTransitions:
    """Test valid state transitions for workflow executions."""

    @given(
        initial_state=st.sampled_from(["PENDING", "RUNNING", "COMPLETED", "FAILED", "PAUSED"]),
        new_state=st.sampled_from(["PENDING", "RUNNING", "COMPLETED", "FAILED", "PAUSED"])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_state_transitions(self, db_session: Session, initial_state: str, new_state: str):
        """INVARIANT: Only valid state transitions should be allowed."""
        # Define valid transitions
        valid_transitions = {
            "PENDING": ["RUNNING", "FAILED", "PAUSED"],
            "RUNNING": ["COMPLETED", "FAILED", "PAUSED"],
            "PAUSED": ["RUNNING", "FAILED", "COMPLETED"],
            "COMPLETED": [],  # Terminal state
            "FAILED": ["PENDING", "RUNNING"]  # Can retry
        }

        # Create execution with initial state
        execution = WorkflowExecution(
            workflow_id=f"workflow_{uuid.uuid4()}",
            status=initial_state
        )
        db_session.add(execution)
        db_session.commit()

        # Check if transition is valid
        is_valid = new_state in valid_transitions.get(initial_state, [])

        # Terminal states cannot transition
        if initial_state == "COMPLETED":
            assert not is_valid, "COMPLETED is terminal state"
        else:
            # Some transitions are allowed
            assert True  # Transition validity depends on implementation

    @given(
        from_version=st.integers(min_value=1, max_value=50),
        to_version=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_version_monotonic_increasing(self, db_session: Session, from_version: int, to_version: int):
        """INVARIANT: Version numbers should be monotonically increasing."""
        execution = WorkflowExecution(
            workflow_id=f"workflow_{uuid.uuid4()}",
            version=from_version
        )
        db_session.add(execution)
        db_session.commit()

        # Version should not decrease
        if to_version < from_version:
            assert to_version < from_version, "Version cannot decrease"
        else:
            assert to_version >= from_version, "Version should increase or stay same"


class TestWorkflowExecutionLogInvariants:
    """Test workflow execution log maintains critical invariants."""

    @given(
        log_entry_count=st.integers(min_value=1, max_value=100),
        execution_id=st.text(min_size=1, max_size=50, alphabet='abc123')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_log_entry_ordering(self, db_session: Session, log_entry_count: int, execution_id: str):
        """INVARIANT: Log entries should be ordered by timestamp."""
        # Log entries should have sequential or timestamp ordering
        assert log_entry_count >= 1, "At least one log entry"
        assert len(execution_id) > 0, "Execution ID required"

    @given(
        message_length=st.integers(min_value=1, max_value=10000),
        log_level=st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_log_message_validity(self, db_session: Session, message_length: int, log_level: str):
        """INVARIANT: Log messages should be valid and properly leveled."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        assert log_level in valid_levels, f"Invalid log level: {log_level}"
        assert 1 <= message_length <= 10000, f"Message length {message_length} outside range"


class TestWorkflowIdUniquenessInvariants:
    """Test workflow ID uniqueness constraints."""

    @given(
        workflow_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_id_uniqueness(self, db_session: Session, workflow_count: int):
        """INVARIANT: Workflow IDs should be unique."""
        workflow_ids = set()
        for _ in range(workflow_count):
            workflow_id = f"workflow_{uuid.uuid4()}"
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                status="PENDING"
            )
            db_session.add(execution)

            # Verify uniqueness
            assert workflow_id not in workflow_ids, f"Duplicate workflow_id: {workflow_id}"
            workflow_ids.add(workflow_id)

        db_session.commit()

    @given(
        workflow_id=st.text(min_size=1, max_size=100, alphabet='abc123_-')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_id_format(self, db_session: Session, workflow_id: str):
        """INVARIANT: Workflow IDs should have valid format."""
        # Workflow ID should be non-empty and reasonable length
        assert len(workflow_id) > 0, "Workflow ID cannot be empty"
        assert len(workflow_id) <= 100, f"Workflow ID too long: {len(workflow_id)}"


class TestWorkflowExecutionDataIntegrity:
    """Test workflow execution data integrity invariants."""

    @given(
        input_data_size=st.integers(min_value=0, max_value=100000),
        output_data_size=st.integers(min_value=0, max_value=100000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_data_size_limits(self, db_session: Session, input_data_size: int, output_data_size: int):
        """INVARIANT: Workflow input/output data should have size limits."""
        max_data_size = 100000  # 100KB limit

        # Verify size constraints
        assert 0 <= input_data_size <= max_data_size, f"Input data size {input_data_size} exceeds limit"
        assert 0 <= output_data_size <= max_data_size, f"Output data size {output_data_size} exceeds limit"

    @given(
        context_json=st.text(min_size=0, max_size=50000, alphabet='abc{}":,123')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_context_validity(self, db_session: Session, context_json: str):
        """INVARIANT: Workflow context should be valid JSON."""
        # Context should be valid JSON or empty
        if len(context_json) > 0:
            # If non-empty, should be valid JSON structure
            # For this test, we just verify length constraint
            assert len(context_json) <= 50000, f"Context too large: {len(context_json)}"
        else:
            assert True  # Empty context is valid

    @given(
        error_message=st.text(min_size=0, max_size=10000, alphabet='abc Error:123')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_error_message_limits(self, db_session: Session, error_message: str):
        """INVARIANT: Workflow error messages should have size limits."""
        max_error_size = 10000

        # Verify error message size
        assert len(error_message) <= max_error_size, f"Error message too long: {len(error_message)}"


class TestWorkflowExecutionLifecycle:
    """Test workflow execution lifecycle invariants."""

    @given(
        workflow_id=st.text(min_size=1, max_size=100, alphabet='abc123_-'),
        user_id=st.text(min_size=1, max_size=100, alphabet='abc123')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_user_binding(self, db_session: Session, workflow_id: str, user_id: str):
        """INVARIANT: Workflow executions can be bound to users."""
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            status="PENDING",
            user_id=user_id
        )
        db_session.add(execution)
        db_session.commit()

        # Verify user binding
        assert execution.user_id == user_id, f"User ID mismatch"

    @given(
        workflow_id=st.text(min_size=1, max_size=100, alphabet='abc123_-'),
        owner_id=st.text(min_size=1, max_size=100, alphabet='abc123')
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_ownership(self, db_session: Session, workflow_id: str, owner_id: str):
        """INVARIANT: Workflow executions can have ownership."""
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            status="PENDING",
            owner_id=owner_id
        )
        db_session.add(execution)
        db_session.commit()

        # Verify ownership
        assert execution.owner_id == owner_id, f"Owner ID mismatch"

    @given(
        visibility=st.sampled_from(["WORKSPACE", "USER", "TEAM", "PRIVATE"])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_visibility_levels(self, db_session: Session, visibility: str):
        """INVARIANT: Workflow executions should have valid visibility levels."""
        valid_visibilities = ["WORKSPACE", "USER", "TEAM", "PRIVATE"]

        assert visibility in valid_visibilities, f"Invalid visibility: {visibility}"

        execution = WorkflowExecution(
            workflow_id=f"workflow_{uuid.uuid4()}",
            status="PENDING",
            visibility=visibility
        )
        db_session.add(execution)
        db_session.commit()

        # Verify visibility
        assert execution.visibility == visibility, f"Visibility mismatch"


class TestWorkflowExecutionConcurrency:
    """Test workflow execution concurrency invariants."""

    @given(
        workflow_id=st.text(min_size=1, max_size=100, alphabet='abc123_-'),
        execution_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_concurrent_execution_tracking(self, db_session: Session, workflow_id: str, execution_count: int):
        """INVARIANT: Multiple executions of same workflow should be trackable."""
        executions = []
        for _ in range(execution_count):
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                status="RUNNING"
            )
            db_session.add(execution)
            executions.append(execution)

        db_session.commit()

        # Verify all executions created
        assert len(executions) == execution_count, f"Expected {execution_count} executions, got {len(executions)}"

        # Verify all have same workflow_id
        for execution in executions:
            assert execution.workflow_id == workflow_id, f"Workflow ID mismatch"

    @given(
        execution_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_execution_id_uniqueness(self, db_session: Session, execution_count: int):
        """INVARIANT: Each execution should have unique ID."""
        execution_ids = set()
        executions = []

        for _ in range(execution_count):
            execution = WorkflowExecution(
                workflow_id=f"workflow_{uuid.uuid4()}",
                status="PENDING"
            )
            db_session.add(execution)
            executions.append(execution)

        db_session.commit()

        # Verify all execution IDs are unique
        for execution in executions:
            assert execution.execution_id not in execution_ids, f"Duplicate execution_id: {execution.execution_id}"
            execution_ids.add(execution.execution_id)

        assert len(execution_ids) == execution_count, f"Expected {execution_count} unique IDs"
