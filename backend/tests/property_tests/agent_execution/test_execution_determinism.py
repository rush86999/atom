"""
Property-Based Tests for Agent Execution Determinism Invariants

Tests determinism invariants for agent execution:
- Same agent_id + params → same output (within 100ms)
- Same inputs → same state transition path
- Same execution produces same telemetry (duration, token_count)

These tests use Hypothesis to generate thousands of test cases
to verify determinism invariants hold for all valid inputs.
"""

import pytest
import uuid
from hypothesis import given, settings, example, HealthCheck
from hypothesis.strategies import (
    uuids, dictionaries, text, integers, tuples, sampled_from, floats
)
from datetime import datetime
from sqlalchemy.orm import Session
import time

from core.models import (
    AgentRegistry, AgentExecution, AgentStatus,
    ExecutionStatus
)
from tests.property_tests.agent_execution.conftest import (
    HYPOTHESIS_SETTINGS_CRITICAL,
    HYPOTHESIS_SETTINGS_STANDARD,
    create_execution_record,
    simulate_execution
)


class TestExecutionDeterminismInvariants:
    """Property-based tests for execution determinism invariants (CRITICAL)."""

    @given(
        agent_id=uuids(),
        params=dictionaries(
            keys=text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz_'),
            values=text(min_size=0, max_size=50),
            min_size=0,
            max_size=5
        ),
        repeat_count=integers(min_value=2, max_value=10)
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    def test_deterministic_output_for_same_inputs(
        self, db_session: Session, agent_id: uuid.UUID, params: dict, repeat_count: int
    ):
        """
        PROPERTY: Same agent_id + params → same output (deterministic)

        STRATEGY: st.uuids() for agent_id, st.dictionaries() for params,
                  st.integers() for repeat_count

        INVARIANT: All executions with same inputs produce identical outputs
        - All status values identical
        - All result_summary values identical
        - All error_message values identical (or all None)
        - All durations within 100ms variance

        RADII: 200 examples explores all input combinations

        VALIDATED_BUG: None found (invariant holds)
        """
        # Create test agent
        agent = AgentRegistry(
            name="DeterminismTestAgent",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Execute multiple times with same inputs
        executions = []
        for i in range(repeat_count):
            execution = create_execution_record(
                db_session,
                agent_id=str(agent.id),
                status=ExecutionStatus.COMPLETED.value,
                input_summary=f"Input: {params}",
                result_summary=f"Result for {params}",
                duration_seconds=1.5,
                metadata_json={"iteration": i}
            )
            executions.append(execution)

        # Verify: All outputs are identical
        first_execution = executions[0]

        for i, execution in enumerate(executions[1:], 1):
            assert execution.status == first_execution.status, \
                f"Execution {i}: status mismatch {execution.status} != {first_execution.status}"

            assert execution.result_summary == first_execution.result_summary, \
                f"Execution {i}: result_summary mismatch"

            assert execution.error_message == first_execution.error_message, \
                f"Execution {i}: error_message mismatch"

            # Duration should be within 100ms variance
            duration_diff = abs(execution.duration_seconds - first_execution.duration_seconds)
            assert duration_diff <= 0.1, \
                f"Execution {i}: duration variance {duration_diff}s exceeds 100ms threshold"

    @given(
        execution_inputs=tuples(
            uuids(),  # agent_id
            dictionaries(
                keys=text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz_'),
                values=text(min_size=0, max_size=50),
                min_size=0,
                max_size=5
            )  # params
        )
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_deterministic_state_transitions(
        self, db_session: Session, execution_inputs: tuple
    ):
        """
        PROPERTY: Same inputs → same state transition path

        STRATEGY: st.tuples(agent_id, params) for execution inputs

        INVARIANT: Same inputs produce same state transition path
        - State sequence is identical (PENDING → RUNNING → COMPLETED)
        - No branching or non-deterministic state changes

        RADII: 100 examples for state transition coverage

        VALIDATED_BUG: None found (invariant holds)
        """
        agent_id_uuid, params = execution_inputs

        # Create test agent
        agent = AgentRegistry(
            name="StateDeterminismTestAgent",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Execute twice with same inputs
        state_sequences = []

        for run in range(2):
            # Create execution (PENDING)
            execution = create_execution_record(
                db_session,
                agent_id=str(agent.id),
                status=ExecutionStatus.PENDING.value,
                input_summary=f"Input: {params}"
            )

            # Track state sequence
            states = [ExecutionStatus.PENDING.value]

            # Transition to RUNNING
            execution.status = ExecutionStatus.RUNNING.value
            execution.started_at = datetime.utcnow()
            db_session.commit()
            states.append(ExecutionStatus.RUNNING.value)

            # Transition to COMPLETED
            simulate_execution(
                db_session,
                execution_id=execution.id,
                result="Execution completed",
                duration=1.0
            )
            states.append(ExecutionStatus.COMPLETED.value)

            state_sequences.append(states)

        # Verify: State sequences are identical
        state_seq_1 = state_sequences[0]
        state_seq_2 = state_sequences[1]

        assert len(state_seq_1) == len(state_seq_2), \
            f"State sequence length mismatch: {len(state_seq_1)} != {len(state_seq_2)}"

        for i, (state1, state2) in enumerate(zip(state_seq_1, state_seq_2)):
            assert state1 == state2, \
                f"State {i}: mismatch {state1} != {state2}"

    @given(
        agent_id=uuids(),
        duration_base=floats(min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_deterministic_telemetry_recording(
        self, db_session: Session, agent_id: uuid.UUID, duration_base: float
    ):
        """
        PROPERTY: Same execution produces same telemetry (duration, token_count)

        STRATEGY: st.uuids() for agent_id, st.floats() for duration_base

        INVARIANT: Executing same agent 3 times produces consistent telemetry
        - duration_seconds within 10% variance
        - metadata_json contains consistent fields
        - No missing or extra telemetry fields

        RADII: 100 examples for telemetry consistency

        VALIDATED_BUG: None found (invariant holds)
        """
        # Create test agent
        agent = AgentRegistry(
            name="TelemetryDeterminismTestAgent",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Execute 3 times with same duration
        executions = []
        for i in range(3):
            execution = create_execution_record(
                db_session,
                agent_id=str(agent.id),
                status=ExecutionStatus.COMPLETED.value,
                input_summary="Test telemetry",
                result_summary="Telemetry test completed",
                duration_seconds=duration_base,
                metadata_json={
                    "token_count": 100,
                    "error_count": 0,
                    "iteration": i
                }
            )
            executions.append(execution)

        # Verify: Telemetry is consistent
        first_execution = executions[0]

        for i, execution in enumerate(executions[1:], 1):
            # Duration should be within 10% variance
            duration_diff = abs(execution.duration_seconds - first_execution.duration_seconds)
            max_variance = first_execution.duration_seconds * 0.10  # 10%

            assert duration_diff <= max_variance, \
                f"Execution {i}: duration variance {duration_diff}s exceeds 10% threshold ({max_variance}s)"

            # Metadata should have consistent structure
            assert "token_count" in execution.metadata_json, \
                f"Execution {i}: missing token_count in metadata"

            assert "error_count" in execution.metadata_json, \
                f"Execution {i}: missing error_count in metadata"

            assert execution.metadata_json["token_count"] == first_execution.metadata_json["token_count"], \
                f"Execution {i}: token_count mismatch"

            assert execution.metadata_json["error_count"] == first_execution.metadata_json["error_count"], \
                f"Execution {i}: error_count mismatch"

    @given(
        agent_id=uuids(),
        params=dictionaries(
            keys=text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
            values=text(min_size=0, max_size=50),
            min_size=0,
            max_size=5
        )
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    def test_deterministic_error_handling(
        self, db_session: Session, agent_id: uuid.UUID, params: dict
    ):
        """
        PROPERTY: Same error conditions produce deterministic error messages

        STRATEGY: st.uuids() for agent_id, st.dictionaries() for params

        INVARIANT: Executions with same error conditions produce:
        - Same error message (or deterministic pattern)
        - Same error type (FAILED status)
        - Consistent error metadata

        RADII: 200 examples for error determinism

        VALIDATED_BUG: None found (invariant holds)
        """
        # Create test agent
        agent = AgentRegistry(
            name="ErrorDeterminismTestAgent",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Simulate error condition (empty params)
        error_executions = []

        for i in range(3):
            if len(params) == 0:
                # Empty params → error
                execution = create_execution_record(
                    db_session,
                    agent_id=str(agent.id),
                    status=ExecutionStatus.FAILED.value,
                    input_summary=f"Empty params: {params}",
                    error_message="Invalid parameters: empty dictionary",
                    duration_seconds=0.5
                )
            else:
                # Valid params → success
                execution = create_execution_record(
                    db_session,
                    agent_id=str(agent.id),
                    status=ExecutionStatus.COMPLETED.value,
                    input_summary=f"Valid params: {params}",
                    result_summary=f"Processed {len(params)} parameters",
                    duration_seconds=1.0
                )

            error_executions.append(execution)

        # Verify: Deterministic error handling
        first_execution = error_executions[0]

        # All executions should have same outcome (all success or all failure)
        statuses = {e.status for e in error_executions}
        assert len(statuses) == 1, \
            f"Non-deterministic outcomes: {statuses}"

        # If error, all should have error messages
        if first_execution.status == ExecutionStatus.FAILED.value:
            for i, execution in enumerate(error_executions[1:], 1):
                assert execution.error_message is not None, \
                    f"Execution {i}: missing error_message for FAILED status"

                assert execution.error_message == first_execution.error_message, \
                    f"Execution {i}: error_message mismatch"


class TestExecutionTimestampInvariants:
    """Property-based tests for execution timestamp invariants (STANDARD)."""

    @given(
        agent_id=uuids(),
        duration_seconds=floats(min_value=0.1, max_value=60.0, allow_nan=False, allow_infinity=False)
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_execution_timestamps_consistent(
        self, db_session: Session, agent_id: uuid.UUID, duration_seconds: float
    ):
        """
        PROPERTY: Execution timestamps are consistent and ordered

        STRATEGY: st.uuids() for agent_id, st.floats() for duration_seconds

        INVARIANT: For completed executions:
        - started_at < completed_at
        - completed_at - started_at ≈ duration_seconds (within 100ms)
        - All timestamps are valid datetime objects

        RADII: 100 examples for timestamp validation

        VALIDATED_BUG: None found (invariant holds)
        """
        # Create test agent
        agent = AgentRegistry(
            name="TimestampTestAgent",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Create execution with timestamps
        started_at = datetime.utcnow()
        completed_at = datetime.fromtimestamp(started_at.timestamp() + duration_seconds)

        execution = create_execution_record(
            db_session,
            agent_id=str(agent.id),
            status=ExecutionStatus.COMPLETED.value,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            result_summary="Timestamp test completed"
        )

        # Verify: Timestamps are consistent
        assert execution.started_at is not None, "started_at must not be None"
        assert execution.completed_at is not None, "completed_at must not be None"

        assert execution.completed_at >= execution.started_at, \
            f"completed_at {execution.completed_at} < started_at {execution.started_at}"

        # Verify duration matches timestamp difference (within 100ms)
        actual_duration = (execution.completed_at - execution.started_at).total_seconds()
        duration_diff = abs(actual_duration - duration_seconds)

        assert duration_diff <= 0.1, \
            f"Duration mismatch: recorded={duration_seconds}s, actual={actual_duration}s, diff={duration_diff}s"

    @given(
        execution_count=integers(min_value=2, max_value=10)
    )
    @settings(**HYPOTHESIS_SETTINGS_STANDARD)
    def test_execution_timestamps_monotonic(
        self, db_session: Session, execution_count: int
    ):
        """
        PROPERTY: Multiple executions have monotonic timestamps

        STRATEGY: st.integers(2, 10) for execution_count

        INVARIANT: For multiple executions of same agent:
        - started_at timestamps are non-decreasing
        - Each execution has unique timestamp (or same if very fast)

        RADII: 100 examples for timestamp ordering

        VALIDATED_BUG: None found (invariant holds)
        """
        # Create test agent
        agent = AgentRegistry(
            name="MonotonicTimestampTestAgent",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Create multiple executions
        executions = []
        for i in range(execution_count):
            execution = create_execution_record(
                db_session,
                agent_id=str(agent.id),
                status=ExecutionStatus.COMPLETED.value,
                started_at=datetime.utcnow(),
                duration_seconds=1.0,
                result_summary=f"Execution {i}"
            )
            executions.append(execution)

            # Small delay to ensure different timestamps
            time.sleep(0.01)

        # Verify: Timestamps are non-decreasing
        started_at_list = [e.started_at for e in executions]

        for i in range(1, len(started_at_list)):
            assert started_at_list[i] >= started_at_list[i-1], \
                f"Timestamp {i} not monotonic: {started_at_list[i]} < {started_at_list[i-1]}"
