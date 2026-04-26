"""
Supervision Service Tests

Tests for agent supervision, real-time monitoring, and intervention.
Coverage target: 20-25 tests for supervision_service.py (737 lines)
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.supervision_service import (
    SupervisionService,
    SupervisionEvent,
    InterventionResult,
    SupervisionOutcome
)
from core.models import SupervisionStatus


class TestSupervisionSessions:
    """Test supervision session lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_supervision_session_success(self):
        """SupervisionService creates supervision session for SUPERVISED agent."""
        db = Mock(spec=Session)

        # Mock agent query
        mock_agent = Mock()
        mock_agent.id = "agent-001"
        mock_agent.name = "Test Agent"
        db.query.return_value.filter.return_value.first.return_value = mock_agent

        # Mock session operations
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()

        service = SupervisionService(db)
        session = await service.start_supervision_session(
            agent_id="agent-001",
            trigger_context={"task": "test task"},
            workspace_id="default",
            supervisor_id="user-001"
        )

        # Verify session was created
        db.add.assert_called_once()
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_supervision_session_agent_not_found(self):
        """SupervisionService raises error when agent not found."""
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None

        service = SupervisionService(db)

        with pytest.raises(ValueError, match="Agent .* not found"):
            await service.start_supervision_session(
                agent_id="nonexistent-agent",
                trigger_context={},
                workspace_id="default",
                supervisor_id="user-001"
            )

    @pytest.mark.asyncio
    async def test_complete_supervision_session(self):
        """SupervisionService completes session and records outcomes."""
        db = Mock(spec=Session)

        # Mock session
        mock_session = Mock()
        mock_session.id = "session-001"
        mock_session.agent_id = "agent-001"
        mock_session.status = SupervisionStatus.RUNNING.value
        mock_session.started_at = datetime.now() - timedelta(minutes=10)
        mock_session.intervention_count = 2
        mock_session.interventions = []

        # Mock agent
        mock_agent = Mock()
        mock_agent.confidence_score = 0.75
        mock_agent.status = "supervised"

        db.query.return_value.filter.return_value.first.return_value = mock_session
        db.query.return_value.filter.return_value.first.return_value = mock_agent

        service = SupervisionService(db)
        outcome = await service.complete_supervision(
            session_id="session-001",
            supervisor_rating=4,
            feedback="Good performance"
        )

        assert isinstance(outcome, SupervisionOutcome)
        assert outcome.session_id == "session-001"
        assert outcome.supervisor_rating == 4

    @pytest.mark.asyncio
    async def test_complete_supervision_promotes_to_autonomous(self):
        """SupervisionService promotes agent to AUTONOMOUS when threshold met."""
        db = Mock(spec=Session)

        # Mock session
        mock_session = Mock()
        mock_session.id = "session-001"
        mock_session.agent_id = "agent-001"
        mock_session.status = SupervisionStatus.RUNNING.value
        mock_session.started_at = datetime.now() - timedelta(minutes=10)
        mock_session.intervention_count = 0
        mock_session.interventions = []

        # Mock agent with high confidence
        mock_agent = Mock()
        mock_agent.confidence_score = 0.89
        mock_agent.status = "supervised"

        db.query.return_value.filter.return_value.first.return_value = mock_session
        db.query.return_value.filter.return_value.first.return_value = mock_agent

        service = SupervisionService(db)
        await service.complete_supervision(
            session_id="session-001",
            supervisor_rating=5,
            feedback="Excellent"
        )

        # Agent should be promoted to AUTONOMOUS
        assert mock_agent.confidence_score >= 0.9
        assert mock_agent.status == "autonomous"


class TestRealTimeMonitoring:
    """Test agent execution monitoring and event streaming."""

    @pytest.mark.asyncio
    async def test_monitor_agent_execution_starts(self):
        """SupervisionService streams events when agent execution starts."""
        db = Mock(spec=Session)

        # Mock session
        mock_session = Mock()
        mock_session.id = "session-001"
        mock_session.agent_id = "agent-001"
        mock_session.status = SupervisionStatus.RUNNING.value

        # Mock execution
        mock_execution = Mock()
        mock_execution.id = "exec-001"
        mock_execution.status = "running"
        mock_execution.started_at = datetime.now()
        mock_execution.input_summary = "Test task"

        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_execution

        service = SupervisionService(db)
        event_count = 0

        async for event in service.monitor_agent_execution(mock_session, db):
            event_count += 1
            assert isinstance(event, SupervisionEvent)
            if event_count == 1:
                break  # Test first event only

        assert event_count == 1

    @pytest.mark.asyncio
    async def test_monitor_agent_execution_completes(self):
        """SupervisionService streams completion event when agent finishes."""
        db = Mock(spec=Session)

        # Mock session
        mock_session = Mock()
        mock_session.id = "session-001"
        mock_session.agent_id = "agent-001"
        mock_session.status = SupervisionStatus.RUNNING.value

        # Mock execution that completes
        mock_execution = Mock()
        mock_execution.id = "exec-001"
        mock_execution.status = "completed"
        mock_execution.started_at = datetime.now()
        mock_execution.completed_at = datetime.now()
        mock_execution.output_summary = "Task completed"

        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_execution

        service = SupervisionService(db)
        events = []

        async for event in service.monitor_agent_execution(mock_session, db):
            events.append(event)
            if len(events) >= 2:  # Get start and completion events
                break

        assert len(events) >= 1
        assert events[-1].event_type in ["result", "error"]


class TestInterventionManagement:
    """Test human supervisor intervention in agent execution."""

    @pytest.mark.asyncio
    async def test_intervene_pause(self):
        """SupervisionService pauses agent execution on supervisor request."""
        db = Mock(spec=Session)

        # Mock session
        mock_session = Mock()
        mock_session.id = "session-001"
        mock_session.status = SupervisionStatus.RUNNING.value
        mock_session.interventions = []
        mock_session.intervention_count = 0

        db.query.return_value.filter.return_value.first.return_value = mock_session

        service = SupervisionService(db)
        result = await service.intervene(
            session_id="session-001",
            intervention_type="pause",
            guidance="Wait for user input"
        )

        assert isinstance(result, InterventionResult)
        assert result.success is True
        assert result.session_state == "paused"

    @pytest.mark.asyncio
    async def test_intervene_terminate(self):
        """SupervisionService terminates agent execution on supervisor request."""
        db = Mock(spec=Session)

        # Mock session
        mock_session = Mock()
        mock_session.id = "session-001"
        mock_session.status = SupervisionStatus.RUNNING.value
        mock_session.interventions = []
        mock_session.intervention_count = 0

        db.query.return_value.filter.return_value.first.return_value = mock_session

        service = SupervisionService(db)
        result = await service.intervene(
            session_id="session-001",
            intervention_type="terminate",
            guidance="Critical error - stop execution"
        )

        assert isinstance(result, InterventionResult)
        assert result.success is True
        assert result.session_state == "terminated"

    @pytest.mark.asyncio
    async def test_intervene_session_not_found(self):
        """SupervisionService raises error when session not found."""
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None

        service = SupervisionService(db)

        with pytest.raises(ValueError, match="Supervision session .* not found"):
            await service.intervene(
                session_id="nonexistent-session",
                intervention_type="pause",
                guidance="Test"
            )

    @pytest.mark.asyncio
    async def test_intervene_invalid_type(self):
        """SupervisionService raises error for invalid intervention type."""
        db = Mock(spec=Session)

        # Mock session
        mock_session = Mock()
        mock_session.id = "session-001"
        mock_session.status = SupervisionStatus.RUNNING.value

        db.query.return_value.filter.return_value.first.return_value = mock_session

        service = SupervisionService(db)

        with pytest.raises(ValueError, match="Unknown intervention type"):
            await service.intervene(
                session_id="session-001",
                intervention_type="invalid_type",
                guidance="Test"
            )


class TestSupervisionPolicies:
    """Test supervision policy configuration and enforcement."""

    def test_calculate_confidence_boost_high_rating(self):
        """SupervisionService calculates high boost for 5-star rating."""
        db = Mock(spec=Session)
        service = SupervisionService(db)

        boost = service._calculate_confidence_boost(
            supervisor_rating=5,
            intervention_count=0,
            duration_seconds=300
        )

        assert boost == 0.1  # Maximum boost

    def test_calculate_confidence_boost_low_rating(self):
        """SupervisionService calculates zero boost for 1-star rating."""
        db = Mock(spec=Session)
        service = SupervisionService(db)

        boost = service._calculate_confidence_boost(
            supervisor_rating=1,
            intervention_count=0,
            duration_seconds=300
        )

        assert boost == 0.0  # No boost

    def test_calculate_confidence_boost_intervention_penalty(self):
        """SupervisionService applies penalty for interventions."""
        db = Mock(spec=Session)
        service = SupervisionService(db)

        boost_no_interventions = service._calculate_confidence_boost(
            supervisor_rating=4,
            intervention_count=0,
            duration_seconds=300
        )

        boost_with_interventions = service._calculate_confidence_boost(
            supervisor_rating=4,
            intervention_count=3,
            duration_seconds=300
        )

        assert boost_with_interventions < boost_no_interventions


class TestSupervisionHistory:
    """Test supervision history and analytics."""

    @pytest.mark.asyncio
    async def test_get_supervision_history(self):
        """SupervisionService retrieves agent's supervision history."""
        db = Mock(spec=Session)

        # Mock sessions
        mock_session = Mock()
        mock_session.id = "session-001"
        mock_session.status = SupervisionStatus.COMPLETED.value
        mock_session.started_at = datetime.now() - timedelta(hours=1)
        mock_session.completed_at = datetime.now()
        mock_session.duration_seconds = 3600
        mock_session.intervention_count = 2
        mock_session.supervisor_rating = 4
        mock_session.supervisor_feedback = "Good"
        mock_session.confidence_boost = 0.05

        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_session
        ]

        service = SupervisionService(db)
        history = await service.get_supervision_history(agent_id="agent-001", limit=10)

        assert len(history) == 1
        assert history[0]["session_id"] == "session-001"
        assert history[0]["supervisor_rating"] == 4

    @pytest.mark.asyncio
    async def test_get_active_sessions(self):
        """SupervisionService retrieves currently active supervision sessions."""
        db = Mock(spec=Session)

        # Mock active sessions
        mock_session = Mock()
        mock_session.id = "session-001"
        mock_session.started_at = datetime.now() - timedelta(minutes=5)

        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_session
        ]

        service = SupervisionService(db)
        sessions = await service.get_active_sessions(workspace_id="default", limit=50)

        assert len(sessions) == 1


class TestSupervisionEvent:
    """Test SupervisionEvent dataclass."""

    def test_supervision_event_creation(self):
        """SupervisionEvent creates event with correct attributes."""
        event = SupervisionEvent(
            event_type="action",
            timestamp=datetime.now(),
            data={"step": "test"}
        )

        assert event.event_type == "action"
        assert isinstance(event.timestamp, datetime)
        assert event.data["step"] == "test"


class TestInterventionResult:
    """Test InterventionResult dataclass."""

    def test_intervention_result_creation(self):
        """InterventionResult creates result with correct attributes."""
        result = InterventionResult(
            success=True,
            message="Operation paused",
            session_state="paused"
        )

        assert result.success is True
        assert result.session_state == "paused"


class TestSupervisionOutcome:
    """Test SupervisionOutcome dataclass."""

    def test_supervision_outcome_creation(self):
        """SupervisionOutcome creates outcome with correct attributes."""
        outcome = SupervisionOutcome(
            session_id="session-001",
            success=True,
            duration_seconds=3600,
            intervention_count=2,
            supervisor_rating=4,
            feedback="Good performance",
            confidence_boost=0.05
        )

        assert outcome.session_id == "session-001"
        assert outcome.duration_seconds == 3600
        assert outcome.confidence_boost == 0.05
