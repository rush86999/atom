"""
Fixtures for agent execution property tests.

Provides test data and Hypothesis settings for testing agent execution
invariants (idempotence, termination, determinism).
"""

import pytest
from hypothesis import settings, HealthCheck
from hypothesis.strategies import (
    text, integers, floats, lists, sampled_from,
    booleans, dictionaries, tuples, datetimes, timedeltas, uuids
)
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import uuid

# Import fixtures from parent conftest to avoid duplication
from tests.property_tests.conftest import (
    db_session, test_agent, test_agents,
    DEFAULT_PROFILE
)

# Import models
from sqlalchemy.orm import Session
from core.models import (
    AgentRegistry, AgentExecution, AgentStatus,
    ExecutionStatus
)

# ============================================================================
# HYPOTHESIS SETTINGS FOR AGENT EXECUTION TESTS
# ============================================================================
#
# Property tests run with max_examples iterations to comprehensively validate
# invariants. Different invariants require different example counts:
#
# - CRITICAL: max_examples=200 (idempotence, determinism)
# - STANDARD: max_examples=100 (termination, state transitions)
# - IO_BOUND: max_examples=50 (database operations)
# ============================================================================

HYPOTHESIS_SETTINGS_CRITICAL = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 200  # Critical invariants (idempotence, determinism)
}

HYPOTHESIS_SETTINGS_STANDARD = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 100  # Standard invariants (termination, state transitions)
}

HYPOTHESIS_SETTINGS_IO = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 50  # IO-bound operations (database queries)
}


# ============================================================================
# FIXTURES FOR AGENT EXECUTION TESTS
# ============================================================================

@pytest.fixture(scope="function")
def test_agent_execution(db_session: Session):
    """
    Create a test agent execution with valid state.

    Returns an AgentExecution with PENDING status for testing
    state transitions and lifecycle invariants.
    """
    # First create a test agent
    agent = AgentRegistry(
        name="ExecutionTestAgent",
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

    # Create execution
    execution = AgentExecution(
        agent_id=agent.id,
        tenant_id="default",
        status=ExecutionStatus.PENDING.value,
        input_summary="Test input",
        triggered_by="manual",
        started_at=datetime.utcnow(),
        duration_seconds=0.0,
        result_summary=None,
        error_message=None,
        metadata_json={}
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    return execution


@pytest.fixture(scope="function")
def test_agent_executions(db_session: Session):
    """
    Create multiple test agent executions with different statuses.

    Returns a list of AgentExecution objects with various statuses
    (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED) for testing
    state transition invariants.
    """
    # First create a test agent
    agent = AgentRegistry(
        name="MultiExecutionTestAgent",
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

    executions = []
    for status in ExecutionStatus:
        execution = AgentExecution(
            agent_id=agent.id,
            tenant_id="default",
            status=status.value,
            input_summary=f"Test input for {status.value}",
            triggered_by="manual",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow() if status != ExecutionStatus.PENDING and status != ExecutionStatus.RUNNING else None,
            duration_seconds=1.0 if status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED] else 0.0,
            result_summary="Test result" if status == ExecutionStatus.COMPLETED else None,
            error_message="Test error" if status == ExecutionStatus.FAILED else None,
            metadata_json={"test_key": "test_value"}
        )
        db_session.add(execution)
        db_session.commit()
        db_session.refresh(execution)
        executions.append(execution)

    return executions


@pytest.fixture(scope="function")
def mock_llm_response():
    """
    Mock LLM responses for deterministic testing.

    Returns a Mock object that simulates LLM responses with
    consistent output for testing idempotence and determinism.
    """
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage = Mock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    mock_response.usage.total_tokens = 30
    return mock_response


@pytest.fixture(scope="function")
def execution_params():
    """
    Strategy for generating valid execution parameters.

    Returns Hypothesis strategies for generating test data:
    - agent_ids: UUID-based agent identifiers
    - params: Dictionaries with string keys and values
    - durations: Integer durations in seconds
    """
    agent_ids = uuids()
    params = dictionaries(
        keys=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz_'),
        values=text(min_size=0, max_size=100),
        min_size=0,
        max_size=10
    )
    durations = integers(min_value=0, max_value=3600)

    return {
        "agent_ids": agent_ids,
        "params": params,
        "durations": durations
    }


# ============================================================================
# HYPOTHESIS STRATEGIES FOR AGENT EXECUTION TESTS
# ============================================================================

@pytest.fixture(scope="session")
def valid_agent_ids():
    """Strategy for generating valid agent IDs."""
    return uuids()


@pytest.fixture(scope="session")
def execution_params_strategy():
    """Strategy for generating valid execution parameters."""
    return dictionaries(
        keys=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz_'),
        values=text(min_size=0, max_size=100),
        min_size=0,
        max_size=10
    )


@pytest.fixture(scope="session")
def execution_durations():
    """Strategy for generating execution durations."""
    return integers(min_value=0, max_value=3600)


@pytest.fixture(scope="session")
def execution_statuses():
    """Strategy for generating execution status values."""
    return sampled_from([
        ExecutionStatus.PENDING.value,
        ExecutionStatus.RUNNING.value,
        ExecutionStatus.COMPLETED.value,
        ExecutionStatus.FAILED.value,
        ExecutionStatus.CANCELLED.value
    ])


# ============================================================================
# HELPER FUNCTIONS FOR AGENT EXECUTION TESTS
# ============================================================================

def create_execution_record(
    db_session: Session,
    agent_id: str,
    status: str = ExecutionStatus.PENDING.value,
    input_summary: str = None,
    triggered_by: str = "manual",
    started_at: datetime = None,
    completed_at: datetime = None,
    duration_seconds: float = 0.0,
    result_summary: str = None,
    error_message: str = None,
    metadata_json: dict = None
) -> AgentExecution:
    """
    Helper function to create an AgentExecution record.

    Args:
        db_session: Database session
        agent_id: Agent ID
        status: Execution status
        input_summary: Input summary text
        triggered_by: Trigger source (manual, schedule, websocket, event)
        started_at: Start timestamp
        completed_at: Completion timestamp
        duration_seconds: Execution duration in seconds
        result_summary: Result summary text
        error_message: Error message text
        metadata_json: Additional metadata

    Returns:
        AgentExecution object
    """
    execution = AgentExecution(
        agent_id=agent_id,
        tenant_id="default",
        status=status,
        input_summary=input_summary,
        triggered_by=triggered_by,
        started_at=started_at or datetime.utcnow(),
        completed_at=completed_at,
        duration_seconds=duration_seconds,
        result_summary=result_summary,
        error_message=error_message,
        metadata_json=metadata_json or {}
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return execution


def simulate_execution(
    db_session: Session,
    execution_id: str,
    result: str = None,
    error: str = None,
    duration: float = 1.0
) -> AgentExecution:
    """
    Helper function to simulate agent execution completion.

    Args:
        db_session: Database session
        execution_id: Execution ID to update
        result: Result summary (if successful)
        error: Error message (if failed)
        duration: Execution duration in seconds

    Returns:
        Updated AgentExecution object
    """
    execution = db_session.query(AgentExecution).filter(
        AgentExecution.id == execution_id
    ).first()

    if not execution:
        raise ValueError(f"Execution {execution_id} not found")

    execution.completed_at = datetime.utcnow()
    execution.duration_seconds = duration

    if error:
        execution.status = ExecutionStatus.FAILED.value
        execution.error_message = error
    else:
        execution.status = ExecutionStatus.COMPLETED.value
        execution.result_summary = result

    db_session.commit()
    db_session.refresh(execution)
    return execution
