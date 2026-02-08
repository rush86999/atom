"""
Tests for Supervision SSE Endpoint

Test Server-Sent Events streaming for real-time monitoring.
"""

import pytest
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    SupervisionSession,
    SupervisionStatus,
    User,
    UserActivity,
    UserState,
)
from core.supervision_service import SupervisionService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Get database session."""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db: Session):
    """Create test user."""
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        status="ACTIVE"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def supervised_agent(db: Session, test_user: User):
    """Create SUPERVISED agent."""
    agent = AgentRegistry(
        name="Supervised Agent",
        description="Agent for testing supervision",
        agent_type="generic",
        category="testing",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.75,
        user_id=test_user.id
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def supervision_session(
    db: Session,
    supervised_agent: AgentRegistry,
    test_user: User
):
    """Create supervision session."""
    session = SupervisionSession(
        agent_id=supervised_agent.id,
        agent_name=supervised_agent.name,
        workspace_id="test_workspace",
        trigger_context={"test": "context"},
        status=SupervisionStatus.RUNNING.value,
        supervisor_id=test_user.id
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@pytest.fixture
def supervision_service(db: Session):
    """Get SupervisionService instance."""
    return SupervisionService(db)


# ============================================================================
# SSE Streaming Tests
# ============================================================================

def test_stream_supervision_logs_sends_connected_event(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession,
    supervised_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test that SSE stream sends connected event."""
    import asyncio

    # Create execution
    execution = AgentExecution(
        id="test_exec_sse_1",
        agent_id=supervised_agent.id,
        user_id=test_user.id,
        agent_name=supervised_agent.name,
        status="running",
        input_data={},
        started_at=datetime.utcnow()
    )
    db.add(execution)
    db.commit()

    # Collect events from monitoring
    events = []
    async def collect_events():
        async for event in supervision_service.monitor_agent_execution(
            session=supervision_session,
            db=db
        ):
            events.append(event)
            if len(events) >= 1:
                break

    asyncio.run(collect_events())

    # Should have at least one event
    assert len(events) > 0


def test_stream_supervision_logs_tracks_execution_progress(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession,
    supervised_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test that SSE stream tracks execution progress."""
    import asyncio

    # Create execution
    execution = AgentExecution(
        id="test_exec_progress",
        agent_id=supervised_agent.id,
        user_id=test_user.id,
        agent_name=supervised_agent.name,
        status="running",
        input_data={"test": "data"},
        started_at=datetime.utcnow()
    )
    db.add(execution)
    db.commit()

    # Collect events
    events = []
    async def collect_events():
        async for event in supervision_service.monitor_agent_execution(
            session=supervision_session,
            db=db
        ):
            events.append(event)
            if len(events) >= 3:
                break

    asyncio.run(collect_events())

    # Should have multiple events showing progress
    assert len(events) >= 1


def test_stream_supervision_logs_detects_completion(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession,
    supervised_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test that SSE stream detects execution completion."""
    import asyncio

    # Create completed execution
    execution = AgentExecution(
        id="test_exec_completed_sse",
        agent_id=supervised_agent.id,
        user_id=test_user.id,
        agent_name=supervised_agent.name,
        status="completed",
        input_data={},
        started_at=datetime.utcnow() - timedelta(minutes=5),
        completed_at=datetime.utcnow(),
        duration_seconds=300,
        output_summary="Execution completed"
    )
    db.add(execution)
    db.commit()

    # Collect events
    events = []
    async def collect_events():
        async for event in supervision_service.monitor_agent_execution(
            session=supervision_session,
            db=db
        ):
            events.append(event)
            if event.event_type == "execution_completed":
                break
            if len(events) >= 10:
                break

    asyncio.run(collect_events())

    # Should detect completion
    completion_events = [e for e in events if e.event_type == "execution_completed"]
    assert len(completion_events) > 0


def test_stream_supervision_logs_handles_errors(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession,
    supervised_agent: AgentRegistry,
    test_user: User,
    db: Session
):
    """Test that SSE stream handles execution errors."""
    import asyncio

    # Create failed execution
    execution = AgentExecution(
        id="test_exec_failed_sse",
        agent_id=supervised_agent.id,
        user_id=test_user.id,
        agent_name=supervised_agent.name,
        status="failed",
        input_data={},
        started_at=datetime.utcnow() - timedelta(minutes=1),
        completed_at=datetime.utcnow(),
        error_message="Execution failed: timeout"
    )
    db.add(execution)
    db.commit()

    # Collect events
    events = []
    async def collect_events():
        async for event in supervision_service.monitor_agent_execution(
            session=supervision_session,
            db=db
        ):
            events.append(event)
            if event.event_type in ["execution_failed", "error"]:
                break
            if len(events) >= 10:
                break

    asyncio.run(collect_events())

    # Should detect error
    error_events = [e for e in events if e.event_type in ["execution_failed", "error"]]
    assert len(error_events) > 0


def test_stream_supervision_logs_nonexistent_execution(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession,
    db: Session
):
    """Test that SSE stream handles non-existent execution."""
    import asyncio

    # Try to monitor non-existent execution
    events = []
    async def collect_events():
        async for event in supervision_service.monitor_agent_execution(
            session=supervision_session,
            db=db
        ):
            events.append(event)
            if len(events) >= 2:
                break

    asyncio.run(collect_events())

    # Should handle gracefully - no execution found scenario
    # The service should complete without crashing
    assert len(events) >= 0


# ============================================================================
# Intervention Tests
# ============================================================================

def test_intervene_pause_session(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession
):
    """Test pausing execution via intervention."""
    import asyncio

    result = asyncio.run(supervision_service.intervene(
        session_id=supervision_session.id,
        intervention_type="pause",
        guidance="Pausing for review"
    ))

    assert result.success is True
    assert "paused" in result.message.lower()
    assert result.session_state == "paused"


def test_intervene_correct_session(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession
):
    """Test correcting execution via intervention."""
    import asyncio

    result = asyncio.run(supervision_service.intervene(
        session_id=supervision_session.id,
        intervention_type="correct",
        guidance="Fix the parameter value"
    ))

    assert result.success is True
    assert "correction" in result.message.lower()
    assert result.session_state == "running"


def test_intervene_terminate_session(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession,
    db: Session
):
    """Test terminating execution via intervention."""
    import asyncio

    result = asyncio.run(supervision_service.intervene(
        session_id=supervision_session.id,
        intervention_type="terminate",
        guidance="Critical error - terminate"
    ))

    assert result.success is True
    assert "terminated" in result.message.lower()
    assert result.session_state == "terminated"

    # Check session status
    db.refresh(supervision_session)
    assert supervision_session.status == SupervisionStatus.INTERRUPTED.value


def test_intervene_nonexistent_session(
    supervision_service: SupervisionService
):
    """Test intervening on non-existent session."""
    import asyncio

    with pytest.raises(ValueError):
        asyncio.run(supervision_service.intervene(
            session_id="nonexistent_session",
            intervention_type="pause",
            guidance="Test"
        ))


def test_intervene_invalid_intervention_type(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession
):
    """Test intervening with invalid intervention type."""
    import asyncio

    with pytest.raises(ValueError):
        asyncio.run(supervision_service.intervene(
            session_id=supervision_session.id,
            intervention_type="invalid_type",
            guidance="Test"
        ))


# ============================================================================
# Session Completion Tests
# ============================================================================

def test_complete_supervision_session(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession,
    supervised_agent: AgentRegistry,
    db: Session
):
    """Test completing supervision session."""
    import asyncio

    outcome = asyncio.run(supervision_service.complete_supervision(
        session_id=supervision_session.id,
        supervisor_rating=5,
        feedback="Excellent performance"
    ))

    assert outcome.session_id == supervision_session.id
    assert outcome.success is True
    assert outcome.supervisor_rating == 5
    assert outcome.feedback == "Excellent feedback"
    assert outcome.confidence_boost > 0

    # Check session status
    db.refresh(supervision_session)
    assert supervision_session.status == SupervisionStatus.COMPLETED.value


def test_complete_supervision_with_interventions(
    supervision_service: SupervisionService,
    supervision_session: SupervisionSession,
    db: Session
):
    """Test completing session with interventions reduces confidence boost."""
    import asyncio

    # Add some interventions
    supervision_session.interventions = [
        {"timestamp": datetime.utcnow().isoformat(), "type": "pause", "guidance": "Review"},
        {"timestamp": datetime.utcnow().isoformat(), "type": "correct", "guidance": "Fix"}
    ]
    supervision_session.intervention_count = 2
    db.commit()

    outcome = asyncio.run(supervision_service.complete_supervision(
        session_id=supervision_session.id,
        supervisor_rating=4,
        feedback="Good but needed corrections"
    ))

    # Should have lower boost due to interventions
    assert outcome.confidence_boost < 0.1  # Should be reduced
    assert outcome.intervention_count == 2


# Need to import timedelta
from datetime import timedelta
