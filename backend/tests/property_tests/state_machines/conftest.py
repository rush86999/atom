"""
Shared fixtures for state machine property-based tests.

Provides test data for agent graduation and training session state machine tests.
"""

import pytest
from hypothesis import strategies as st
from sqlalchemy.orm import Session

# Import shared fixtures from parent conftest to avoid duplication
from tests.property_tests.conftest import (
    db_session,
    DEFAULT_PROFILE,
    CI_PROFILE
)

# Import models needed for state machine tests
from core.models import (
    AgentRegistry,
    AgentStatus,
    TrainingSession,
    Episode,
    SupervisionSession
)


# ============================================================================
# HYPOTHESIS SETTINGS FOR STATE MACHINE TESTS
# ============================================================================

from hypothesis import settings, HealthCheck

# CRITICAL: Agent graduation monotonicity is critical for system correctness
HYPOTHESIS_SETTINGS_CRITICAL = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)

# STANDARD: Training session transitions and other state machine invariants
HYPOTHESIS_SETTINGS_STANDARD = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)

# IO-BOUND: State machine tests with database operations
HYPOTHESIS_SETTINGS_IO = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)


# ============================================================================
# FIXTURES FOR AGENT GRADUATION STATE MACHINE TESTS
# ============================================================================

@pytest.fixture(scope="function")
def test_training_sessions(db_session: Session):
    """
    Create training sessions with valid states for state machine testing.

    Returns a dictionary of sessions in different states:
    - PENDING: Session not yet started
    - IN_PROGRESS: Session currently running
    - COMPLETED: Session successfully finished
    - CANCELLED: Session cancelled
    """
    sessions = {
        "pending": TrainingSession(
            agent_id="test-agent-1",
            target_maturity=AgentStatus.INTERN.value,
            status="PENDING",
            duration_minutes=60,
            assigned_supervisor_id="supervisor-1"
        ),
        "in_progress": TrainingSession(
            agent_id="test-agent-2",
            target_maturity=AgentStatus.SUPERVISED.value,
            status="IN_PROGRESS",
            duration_minutes=120,
            assigned_supervisor_id="supervisor-1",
            started_at=None
        ),
        "completed": TrainingSession(
            agent_id="test-agent-3",
            target_maturity=AgentStatus.AUTONOMOUS.value,
            status="COMPLETED",
            duration_minutes=180,
            assigned_supervisor_id="supervisor-1",
            started_at=None,
            completed_at=None
        ),
        "cancelled": TrainingSession(
            agent_id="test-agent-4",
            target_maturity=AgentStatus.INTERN.value,
            status="CANCELLED",
            duration_minutes=60,
            assigned_supervisor_id="supervisor-1",
            cancelled_at=None
        )
    }

    for session in sessions.values():
        db_session.add(session)

    db_session.commit()

    for key, session in sessions.items():
        db_session.refresh(session)

    return sessions


@pytest.fixture(scope="function")
def test_agents_for_graduation(db_session: Session):
    """
    Create agents at all maturity levels for graduation state machine testing.

    Returns a dictionary of agents at different maturity levels:
    - STUDENT: Entry-level agent (confidence < 0.5)
    - INTERN: Mid-level agent (confidence 0.5-0.7)
    - SUPERVISED: Advanced agent (confidence 0.7-0.9)
    - AUTONOMOUS: Expert agent (confidence > 0.9)
    """
    agents = {
        "student": AgentRegistry(
            name="StudentAgent",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="StudentClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        ),
        "intern": AgentRegistry(
            name="InternAgent",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="InternClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        ),
        "supervised": AgentRegistry(
            name="SupervisedAgent",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="SupervisedClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
        ),
        "autonomous": AgentRegistry(
            name="AutonomousAgent",
            tenant_id="default",
            category="test",
            module_path="test.module",
            class_name="AutonomousClass",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95,
        )
    }

    for agent in agents.values():
        db_session.add(agent)

    db_session.commit()

    for key, agent in agents.items():
        db_session.refresh(agent)

    return agents


@pytest.fixture(scope="session")
def confidence_boosts():
    """
    Strategy for generating confidence boost values for state machine tests.

    Returns a Hypothesis strategy that generates floats in [0.0, 0.3] range.
    """
    return st.floats(min_value=0.0, max_value=0.3, allow_nan=False, allow_infinity=False)


@pytest.fixture(scope="session")
def episode_counts():
    """
    Strategy for generating episode counts for graduation requirements.

    Returns a Hypothesis strategy that generates integers in [0, 100] range.
    """
    return st.integers(min_value=0, max_value=100)


@pytest.fixture(scope="session")
def intervention_rates():
    """
    Strategy for generating intervention rates for graduation requirements.

    Returns a Hypothesis strategy that generates floats in [0.0, 1.0] range.
    """
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@pytest.fixture(scope="session")
def constitutional_scores():
    """
    Strategy for generating constitutional compliance scores for graduation requirements.

    Returns a Hypothesis strategy that generates floats in [0.5, 1.0] range.
    """
    return st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False)
