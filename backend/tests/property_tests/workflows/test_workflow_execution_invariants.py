"""
Property-Based Tests for Workflow Execution Invariants

⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for workflow execution.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md

Tests:
    - 8 comprehensive property-based tests for workflow execution
    - Coverage targets: 100% of workflow execution logic
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from typing import List, Dict
from core.workflow_engine import (
    WorkflowEngine,
    WorkflowExecution,
    WorkflowStep,
    WorkflowStatus,
    StepStatus
)
from core.models import WorkflowExecution as WorkflowExecutionModel


class TestWorkflowExecutionInvariants:
    """Property-based tests for workflow execution invariants."""

    # ========== Status Transition Validity ==========

    @given(
        initial_status=st.sampled_from([
            WorkflowStatus.PENDING,
            WorkflowStatus.RUNNING,
            WorkflowStatus.PAUSED,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED
        ]),
        target_status=st.sampled_from([
            WorkflowStatus.PENDING,
            WorkflowStatus.RUNNING,
            WorkflowStatus.PAUSED,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED
        ])
    )
    @settings(max_examples=100)
    def test_workflow_execution_status_transitions(self, initial_status, target_status):
        """INVARIANT: Status transitions must follow valid state machine."""
        engine = WorkflowEngine()

        # Define valid transitions
        valid_transitions = {
            WorkflowStatus.PENDING: [WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED],
            WorkflowStatus.RUNNING: [WorkflowStatus.PAUSED, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED],
            WorkflowStatus.PAUSED: [WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED],
            WorkflowStatus.COMPLETED: [],  # Terminal state
            WorkflowStatus.FAILED: [WorkflowStatus.PENDING],  # Can retry
            WorkflowStatus.CANCELLED: []  # Terminal state
        }

        # Check if transition is valid
        is_valid = target_status in valid_transitions.get(initial_status, [])

        # Attempt transition
        execution = WorkflowExecution(
            workflow_id="test_workflow",
            status=initial_status
        )

        if is_valid:
            # Valid transition should succeed
            new_status = engine.transition_status(execution, target_status)
            assert new_status == target_status, f"Valid transition {initial_status} -> {target_status} failed"
        else:
            # Invalid transition should fail
            with pytest.raises(ValueError):
                engine.transition_status(execution, target_status)

    # ========== Time Consistency ==========

    @given(
        steps=st.lists(
            st.fixed_dictionaries({
                'step_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'duration_seconds': st.integers(min_value=0, max_value=3600)
            }),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_workflow_execution_time_consistency(self, steps):
        """INVARIANT: created_at <= started_at <= completed_at."""
        engine = WorkflowEngine()

        # Create workflow execution
        execution = WorkflowExecution(
            workflow_id="test_workflow",
            steps=[]
        )

        # Add steps
        for step_data in steps:
            step = WorkflowStep(
                step_id=step_data['step_id'],
                duration_seconds=step_data['duration_seconds']
            )
            execution.add_step(step)

        # Execute workflow
        engine.execute(execution)

        # Verify time consistency
        assert execution.created_at is not None, "created_at must be set"

        if execution.started_at is not None:
            assert execution.started_at >= execution.created_at, \
                "started_at must be >= created_at"

        if execution.completed_at is not None:
            assert execution.completed_at >= execution.started_at, \
                "completed_at must be >= started_at"

        # Verify step times
        for step in execution.steps:
            if step.started_at is not None:
                assert step.started_at >= execution.created_at, \
                    f"Step {step.step_id} started_at before workflow created_at"

            if step.completed_at is not None:
                assert step.completed_at >= step.started_at, \
                    f"Step {step.step_id} completed_at before started_at"

    # ========== Step Execution Order ==========

    @given(
        steps=st.lists(
            st.fixed_dictionaries({
                'step_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'depends_on': st.lists(st.text(min_size=1, max_size=20, alphabet='abc123'), min_size=0, max_size=3),
                'duration_seconds': st.integers(min_value=1, max_value=60)
            }),
            min_size=2,
            max_size=10,
            unique_by=lambda x: x['step_id']
        )
    )
    @settings(max_examples=100)
    def test_workflow_step_execution_order(self, steps):
        """INVARIANT: Steps must execute in dependency order."""
        engine = WorkflowEngine()

        # Create workflow with dependencies
        execution = WorkflowExecution(
            workflow_id="test_workflow",
            steps=[]
        )

        step_map = {}
        for step_data in steps:
            step = WorkflowStep(
                step_id=step_data['step_id'],
                depends_on=step_data['depends_on'],
                duration_seconds=step_data['duration_seconds']
            )
            execution.add_step(step)
            step_map[step.step_id] = step

        # Execute workflow
        engine.execute(execution)

        # Verify execution order respects dependencies
        execution_order = {}
        for step in execution.steps:
            if step.completed_at is not None:
                execution_order[step.step_id] = step.completed_at

        for step_id, step in step_map.items():
            for dep_id in step.depends_on:
                if dep_id in execution_order and step_id in execution_order:
                    # Dependent step must complete after dependency
                    assert execution_order[step_id] >= execution_order[dep_id], \
                        f"Step {step_id} completed before its dependency {dep_id}"

    # ========== Version Monotonicity ==========

    @given(
        initial_version=st.integers(min_value=1, max_value=100),
        updates=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100)
    def test_workflow_version_monotonic(self, initial_version, updates):
        """INVARIANT: Workflow version must only increase."""
        engine = WorkflowEngine()

        # Create workflow execution
        execution = WorkflowExecution(
            workflow_id="test_workflow",
            version=initial_version
        )

        # Perform updates
        for _ in range(updates):
            engine.update_workflow(execution)
            assert execution.version > initial_version, \
                "Version must increase after update"
            initial_version = execution.version

    # ========== Error Handling ==========

    @given(
        steps=st.lists(
            st.fixed_dictionaries({
                'step_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'should_fail': st.booleans(),
                'error_message': st.text(min_size=5, max_size=100)
            }),
            min_size=3,
            max_size=15,
            unique_by=lambda x: x['step_id']
        )
    )
    @settings(max_examples=100)
    def test_workflow_error_handling(self, steps):
        """INVARIANT: Failed steps must have error details."""
        engine = WorkflowEngine()

        # Create workflow with mixed success/failure steps
        execution = WorkflowExecution(
            workflow_id="test_workflow",
            steps=[]
        )

        for step_data in steps:
            step = WorkflowStep(
                step_id=step_data['step_id'],
                should_fail=step_data['should_fail'],
                error_message=step_data['error_message']
            )
            execution.add_step(step)

        # Execute workflow
        engine.execute(execution)

        # Verify failed steps have error details
        failed_steps = [s for s in execution.steps if s.status == StepStatus.FAILED]

        for step in failed_steps:
            assert hasattr(step, 'error'), "Failed step must have error attribute"
            assert step.error is not None, "Failed step must have error details"
            assert len(step.error) > 0, "Error message must not be empty"

    # ========== Log Consistency ==========

    @given(
        steps=st.lists(
            st.fixed_dictionaries({
                'step_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'log_messages': st.lists(st.text(min_size=5, max_size=100), min_size=0, max_size=10)
            }),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x['step_id']
        )
    )
    @settings(max_examples=100)
    def test_workflow_log_consistency(self, steps):
        """INVARIANT: Logs must match execution flow."""
        engine = WorkflowEngine()

        # Create workflow execution
        execution = WorkflowExecution(
            workflow_id="test_workflow",
            steps=[]
        )

        expected_log_count = 0
        for step_data in steps:
            step = WorkflowStep(
                step_id=step_data['step_id'],
                log_messages=step_data['log_messages']
            )
            execution.add_step(step)
            expected_log_count += len(step_data['log_messages'])

        # Execute workflow
        engine.execute(execution)

        # Verify logs match
        # Each step should have logs for start, completion
        min_expected_logs = len(steps) * 2  # start + complete for each step
        max_expected_logs = min_expected_logs + expected_log_count

        assert len(execution.logs) >= min_expected_logs, \
            f"Missing logs: {len(execution.logs)} logs, expected at least {min_expected_logs}"

    # ========== Rollback Integrity ==========

    @given(
        steps=st.lists(
            st.fixed_dictionaries({
                'step_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'is_rollback_point': st.booleans(),
                'should_fail': st.booleans()
            }),
            min_size=3,
            max_size=10,
            unique_by=lambda x: x['step_id']
        )
    )
    @settings(max_examples=100)
    def test_workflow_rollback_integrity(self, steps):
        """INVARIANT: Rollback must restore consistent state."""
        engine = WorkflowEngine()

        # Create workflow with rollback points
        execution = WorkflowExecution(
            workflow_id="test_workflow",
            steps=[],
            enable_rollback=True
        )

        rollback_points = []
        for step_data in steps:
            step = WorkflowStep(
                step_id=step_data['step_id'],
                is_rollback_point=step_data['is_rollback_point'],
                should_fail=step_data['should_fail']
            )
            execution.add_step(step)

            if step_data['is_rollback_point']:
                rollback_points.append(step.step_id)

        # Execute workflow
        engine.execute(execution)

        # If rollback occurred, verify state
        if execution.status == WorkflowStatus.FAILED and execution.rolled_back:
            assert execution.rollback_to_step is not None, \
                "Rollback step must be specified"

            # Verify rollback to valid rollback point
            assert execution.rollback_to_step in rollback_points, \
                f"Rollback to non-rollback point: {execution.rollback_to_step}"

            # Verify steps after rollback point are not completed
            rolled_back_index = list(step['step_id'] for step in steps).index(execution.rollback_to_step)
            for i in range(rolled_back_index + 1, len(steps)):
                step = execution.steps[i]
                assert step.status != StepStatus.COMPLETED, \
                    f"Step {step.step_id} after rollback point is completed"

    # ========== Clean Cancellation ==========

    @given(
        steps=st.lists(
            st.fixed_dictionaries({
                'step_id': st.text(min_size=1, max_size=20, alphabet='abc123'),
                'duration_seconds': st.integers(min_value=1, max_size=60)
            }),
            min_size=3,
            max_size=10,
            unique_by=lambda x: x['step_id']
        ),
        cancel_at_step=st.integers(min_value=0, max_value=5)
    )
    @settings(max_examples=100)
    def test_workflow_cancellation_clean(self, steps, cancel_at_step):
        """INVARIANT: Cancellation must cleanly stop execution."""
        engine = WorkflowEngine()

        # Create workflow execution
        execution = WorkflowExecution(
            workflow_id="test_workflow",
            steps=[]
        )

        for step_data in steps:
            step = WorkflowStep(
                step_id=step_data['step_id'],
                duration_seconds=step_data['duration_seconds']
            )
            execution.add_step(step)

        # Execute with cancellation
        engine.execute_with_cancellation(execution, cancel_after_step=cancel_at_step)

        # Verify cancellation state
        assert execution.status == WorkflowStatus.CANCELLED, \
            "Workflow should be cancelled"

        # Verify no steps after cancellation point completed
        if cancel_at_step < len(steps):
            for i in range(cancel_at_step, len(steps)):
                step = execution.steps[i]
                if step.status == StepStatus.COMPLETED:
                    assert step.step_id == steps[cancel_at_step]['step_id'], \
                        f"Step {step.step_id} after cancellation point completed"
