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
