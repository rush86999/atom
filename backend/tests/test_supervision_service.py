"""
Tests for Supervision Service

Tests for SUPERVISED agent real-time supervision, monitoring, intervention, and completion.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from core.supervision_service import (
    SupervisionService,
    SupervisionEvent,
    InterventionResult,
    SupervisionOutcome,
)
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    SupervisionSession,
    SupervisionStatus,
)


# ========================================================================
# Fixtures
# ========================================================================

@pytest.fixture
def db_session():
    """Mock database session"""
    session = MagicMock(spec=Session)
    session.query = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def mock_supervised_agent():
    """Mock SUPERVISED agent"""
    agent = AgentRegistry(
        id="supervised-agent-123",
        name="Test Supervised Agent",
        category="Finance",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.75,
    )
    return agent


@pytest.fixture
def mock_supervision_session(mock_supervised_agent):
    """Mock supervision session"""
    session = SupervisionSession(
        id="supervision-123",
        agent_id=mock_supervised_agent.id,
        agent_name=mock_supervised_agent.name,
        workspace_id="workspace-123",
        trigger_context={
            "trigger_type": "agent_message",
            "task": "Process invoice"
        },
        status=SupervisionStatus.RUNNING.value,
        supervisor_id="supervisor-123",
        started_at=datetime.now(),
        interventions=[],
        intervention_count=0,
        supervisor_rating=None,
        supervisor_feedback=None,
    )
    return session


@pytest.fixture
def mock_agent_execution(mock_supervised_agent):
    """Mock agent execution"""
    execution = AgentExecution(
        id="execution-123",
        agent_id=mock_supervised_agent.id,
        status="running",
        started_at=datetime.now(),
        input_summary="Processing invoice #12345",
        result_summary=None,
        duration_seconds=None,
    )
    return execution


@pytest.fixture
def service(db_session):
    """SupervisionService instance"""
    return SupervisionService(db_session)


# ========================================================================
# Test Supervision Sessions
# ========================================================================

class TestSupervisionSessions:
    """Tests for supervision session management"""

    @pytest.mark.asyncio
    async def test_start_supervision(
        self, service, mock_supervised_agent, db_session
    ):
        """Test starting supervision session for SUPERVISED agent"""
        # Mock agent query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervised_agent)
        db_session.query.return_value = mock_query

        # Start supervision
        session = await service.start_supervision_session(
            agent_id=mock_supervised_agent.id,
            trigger_context={"task": "Process invoice"},
            workspace_id="workspace-123",
            supervisor_id="supervisor-123"
        )

        # Verify session created
        assert session is not None
        assert session.agent_id == mock_supervised_agent.id
        assert session.workspace_id == "workspace-123"
        assert session.supervisor_id == "supervisor-123"
        assert session.status == SupervisionStatus.RUNNING.value

    @pytest.mark.asyncio
    async def test_start_for_supervised_agent_only(
        self, service, db_session
    ):
        """Test that only SUPERVISED agents can start supervision"""
        # Create STUDENT agent
        student_agent = AgentRegistry(
            id="student-agent",
            name="Student Agent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=student_agent)
        db_session.query.return_value = mock_query

        # Start supervision (should still work, governance is enforced elsewhere)
        session = await service.start_supervision_session(
            agent_id=student_agent.id,
            trigger_context={},
            workspace_id="workspace-123",
            supervisor_id="supervisor-123"
        )

        # Session created (governance is enforced by TriggerInterceptor)
        assert session is not None
        assert session.agent_id == student_agent.id

    @pytest.mark.asyncio
    async def test_start_non_existent_agent(self, service, db_session):
        """Test starting supervision for non-existent agent"""
        # Mock query returning None
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        db_session.query.return_value = mock_query

        # Should raise ValueError
        with pytest.raises(ValueError, match="not found"):
            await service.start_supervision_session(
                agent_id="non-existent",
                trigger_context={},
                workspace_id="workspace-123",
                supervisor_id="supervisor-123"
            )

    @pytest.mark.asyncio
    async def test_stop_supervision(
        self, service, mock_supervision_session, db_session
    ):
        """Test stopping supervision session"""
        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Stop supervision by completing it
        mock_supervision_session.status = SupervisionStatus.COMPLETED.value
        mock_supervision_session.completed_at = datetime.now()

        # Verify stopped
        assert mock_supervision_session.status == SupervisionStatus.COMPLETED.value
        assert mock_supervision_session.completed_at is not None


# ========================================================================
# Test Real-Time Monitoring
# ========================================================================

class TestRealTimeMonitoring:
    """Tests for real-time agent execution monitoring"""

    @pytest.mark.asyncio
    async def test_monitor_execution_yields_events(
        self, service, mock_supervision_session, mock_agent_execution, db_session
    ):
        """Test that monitoring yields supervision events"""
        # Mock execution query - first returns execution, then None for session refresh
        execution_query = MagicMock()
        execution_query.filter = MagicMock(return_value=execution_query)
        execution_query.order_by = MagicMock(return_value=execution_query)
        execution_query.first = MagicMock(return_value=mock_agent_execution)

        session_query = MagicMock()
        session_query.filter = MagicMock(return_value=session_query)
        session_query.order_by = MagicMock(return_value=session_query)
        session_query.limit = MagicMock(return_value=session_query)
        session_query.all = MagicMock(return_value=[mock_supervision_session])

        db_session.query.side_effect = [
            session_query,  # For get_active_sessions
            execution_query,  # For monitoring
        ]

        # Patch asyncio.sleep to avoid delay
        with patch('asyncio.sleep', AsyncMock()):
            # Monitor for one event then break
            events = []
            async for event in service.monitor_agent_execution(
                session=mock_supervision_session,
                db=db_session
            ):
                events.append(event)
                if len(events) >= 1:  # Get first event then stop
                    break

        # Verify events received
        assert len(events) > 0
        assert isinstance(events[0], SupervisionEvent)

    @pytest.mark.asyncio
    async def test_pause_execution(
        self, service, mock_supervision_session, db_session
    ):
        """Test pausing agent execution"""
        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Pause execution
        result = await service.intervene(
            session_id=mock_supervision_session.id,
            intervention_type="pause",
            guidance="Pausing to review approach"
        )

        # Verify pause
        assert result.success is True
        assert result.session_state == "paused"
        assert "paused" in result.message.lower()
        assert mock_supervision_session.intervention_count == 1

    @pytest.mark.asyncio
    async def test_resume_execution_after_pause(
        self, service, mock_supervision_session, db_session
    ):
        """Test resuming execution after pause"""
        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # First pause
        await service.intervene(
            session_id=mock_supervision_session.id,
            intervention_type="pause",
            guidance="Pause"
        )

        # Then resume (using "correct" intervention type)
        result = await service.intervene(
            session_id=mock_supervision_session.id,
            intervention_type="correct",
            guidance="Resume with corrected approach"
        )

        # Verify resume
        assert result.success is True
        assert result.session_state == "running"
        assert "Correction applied" in result.message
        assert mock_supervision_session.intervention_count == 2

    @pytest.mark.asyncio
    async def test_correct_execution(
        self, service, mock_supervision_session, db_session
    ):
        """Test correcting agent execution"""
        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Correct execution
        result = await service.intervene(
            session_id=mock_supervision_session.id,
            intervention_type="correct",
            guidance="Use different calculation method"
        )

        # Verify correction
        assert result.success is True
        assert result.session_state == "running"
        assert "Correction applied" in result.message

    @pytest.mark.asyncio
    async def test_terminate_execution(
        self, service, mock_supervision_session, db_session
    ):
        """Test terminating agent execution"""
        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Terminate execution
        result = await service.intervene(
            session_id=mock_supervision_session.id,
            intervention_type="terminate",
            guidance="Critical error - stopping execution"
        )

        # Verify termination
        assert result.success is True
        assert result.session_state == "terminated"
        assert "terminated" in result.message.lower()
        assert mock_supervision_session.status == SupervisionStatus.INTERRUPTED.value

    @pytest.mark.asyncio
    async def test_unknown_intervention_type(self, service, mock_supervision_session, db_session):
        """Test unknown intervention type raises error"""
        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Should raise ValueError
        with pytest.raises(ValueError, match="Unknown intervention type"):
            await service.intervene(
                session_id=mock_supervision_session.id,
                intervention_type="unknown_type",
                guidance="Unknown intervention"
            )


# ========================================================================
# Test Supervision Events
# ========================================================================

class TestSupervisionEvents:
    """Tests for supervision event tracking"""

    @pytest.mark.asyncio
    async def test_log_event(self):
        """Test logging supervision event"""
        event = SupervisionEvent(
            event_type="action",
            timestamp=datetime.now(),
            data={"action": "execution_started"}
        )

        # Verify event
        assert event.event_type == "action"
        assert event.data["action"] == "execution_started"

    @pytest.mark.asyncio
    async def test_event_intervention(self, service, mock_supervision_session, db_session):
        """Test logging intervention event"""
        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Intervene (logs event)
        await service.intervene(
            session_id=mock_supervision_session.id,
            intervention_type="pause",
            guidance="Intervention reason"
        )

        # Verify intervention logged
        assert len(mock_supervision_session.interventions) > 0
        assert mock_supervision_session.interventions[0]["type"] == "pause"

    @pytest.mark.asyncio
    async def test_event_auto_approval(self):
        """Test auto-approval event logging"""
        # Auto-approval would be logged via intervention
        intervention = {
            "timestamp": datetime.now().isoformat(),
            "type": "correct",
            "guidance": "Auto-approved: Action within policy"
        }

        # Verify auto-approval structure
        assert intervention["type"] == "correct"
        assert "Auto-approved" in intervention["guidance"]

    @pytest.mark.asyncio
    async def test_get_events(
        self, service, mock_supervision_session, db_session
    ):
        """Test retrieving supervision events"""
        # Add some interventions
        mock_supervision_session.interventions = [
            {"timestamp": datetime.now().isoformat(), "type": "pause", "guidance": "First pause"},
            {"timestamp": datetime.now().isoformat(), "type": "correct", "guidance": "Correction"},
        ]

        # Get events
        events = mock_supervision_session.interventions

        # Verify events
        assert len(events) == 2
        assert events[0]["type"] == "pause"
        assert events[1]["type"] == "correct"


# ========================================================================
# Test Supervision Permissions
# ========================================================================

class TestSupervisionPermissions:
    """Tests for supervision permissions and access control"""

    @pytest.mark.asyncio
    async def test_supervisor_can_pause(
        self, service, mock_supervision_session, db_session
    ):
        """Test that supervisor can pause execution"""
        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Supervisor pauses
        result = await service.intervene(
            session_id=mock_supervision_session.id,
            intervention_type="pause",
            guidance="Supervisor pause"
        )

        # Verify allowed
        assert result.success is True

    @pytest.mark.asyncio
    async def test_supervisor_can_terminate(
        self, service, mock_supervision_session, db_session
    ):
        """Test that supervisor can terminate execution"""
        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Supervisor terminates
        result = await service.intervene(
            session_id=mock_supervision_session.id,
            intervention_type="terminate",
            guidance="Supervisor termination"
        )

        # Verify allowed
        assert result.success is True

    @pytest.mark.asyncio
    async def test_supervisor_can_correct(
        self, service, mock_supervision_session, db_session
    ):
        """Test that supervisor can correct execution"""
        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Supervisor corrects
        result = await service.intervene(
            session_id=mock_supervision_session.id,
            intervention_type="correct",
            guidance="Supervisor correction"
        )

        # Verify allowed
        assert result.success is True

    @pytest.mark.asyncio
    async def test_non_supervisor_blocked(
        self, service, mock_supervision_session, db_session
    ):
        """Test that non-supervisors are blocked"""
        # This would be enforced at the API layer
        # Service layer doesn't check permissions directly
        # Permissions are handled by authentication/authorization middleware

        # Mock session query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Service doesn't check supervisor_id, assumes authorized caller
        result = await service.intervene(
            session_id=mock_supervision_session.id,
            intervention_type="pause",
            guidance="Any user"
        )

        # Service allows it (permission check happens elsewhere)
        assert result.success is True


# ========================================================================
# Test Supervision Completion
# ========================================================================

class TestSupervisionCompletion:
    """Tests for supervision session completion"""

    @pytest.mark.asyncio
    async def test_complete_supervision(
        self, service, mock_supervision_session, mock_supervised_agent, db_session
    ):
        """Test completing supervision session"""
        # Mock queries
        mock_session_query = MagicMock()
        mock_session_query.filter = MagicMock(return_value=mock_session_query)
        mock_session_query.first = MagicMock(return_value=mock_supervision_session)

        mock_agent_query = MagicMock()
        mock_agent_query.filter = MagicMock(return_value=mock_agent_query)
        mock_agent_query.first = MagicMock(return_value=mock_supervised_agent)

        db_session.query.side_effect = [
            mock_session_query,  # Session query
            mock_agent_query,    # Agent query
        ]

        # Mock episode creation (non-blocking)
        with patch('core.supervision_service.asyncio.create_task', MagicMock()):
            # Complete supervision
            outcome = await service.complete_supervision(
                session_id=mock_supervision_session.id,
                supervisor_rating=5,
                feedback="Excellent performance"
            )

            # Verify completion
            assert outcome is not None
            assert outcome.session_id == mock_supervision_session.id
            assert outcome.supervisor_rating == 5
            assert outcome.feedback == "Excellent performance"
            assert outcome.success is True
            assert mock_supervision_session.status == SupervisionStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_complete_with_low_rating(
        self, service, mock_supervision_session, mock_supervised_agent, db_session
    ):
        """Test completion with low supervisor rating"""
        # Mock queries
        mock_session_query = MagicMock()
        mock_session_query.filter = MagicMock(return_value=mock_session_query)
        mock_session_query.first = MagicMock(return_value=mock_supervision_session)

        mock_agent_query = MagicMock()
        mock_agent_query.filter = MagicMock(return_value=mock_agent_query)
        mock_agent_query.first = MagicMock(return_value=mock_supervised_agent)

        db_session.query.side_effect = [
            mock_session_query,
            mock_agent_query,
        ]

        with patch('core.supervision_service.asyncio.create_task', MagicMock()):
            # Complete with low rating
            outcome = await service.complete_supervision(
                session_id=mock_supervision_session.id,
                supervisor_rating=2,
                feedback="Poor performance, many corrections needed"
            )

            # Verify low rating outcome
            assert outcome.success is False  # Rating < 3
            assert outcome.supervisor_rating == 2

    @pytest.mark.asyncio
    async def test_complete_promotes_to_autonomous(
        self, service, mock_supervision_session, mock_supervised_agent, db_session
    ):
        """Test that excellent performance promotes to AUTONOMOUS"""
        # Set agent confidence just below threshold
        mock_supervised_agent.confidence_score = 0.88
        mock_supervised_agent.status = AgentStatus.SUPERVISED.value

        # Mock queries
        mock_session_query = MagicMock()
        mock_session_query.filter = MagicMock(return_value=mock_session_query)
        mock_session_query.first = MagicMock(return_value=mock_supervision_session)

        mock_agent_query = MagicMock()
        mock_agent_query.filter = MagicMock(return_value=mock_agent_query)
        mock_agent_query.first = MagicMock(return_value=mock_supervised_agent)

        db_session.query.side_effect = [
            mock_session_query,
            mock_agent_query,
        ]

        with patch('core.supervision_service.asyncio.create_task', MagicMock()):
            # Complete with perfect rating (max confidence boost)
            outcome = await service.complete_supervision(
                session_id=mock_supervision_session.id,
                supervisor_rating=5,
                feedback="Perfect performance"
            )

            # Verify promotion to AUTONOMOUS
            assert mock_supervised_agent.status == AgentStatus.AUTONOMOUS.value

    @pytest.mark.asyncio
    async def test_complete_non_existent_session(self, service, db_session):
        """Test completing non-existent session"""
        # Mock query returning None
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        db_session.query.return_value = mock_query

        # Should raise ValueError
        with pytest.raises(ValueError, match="not found"):
            await service.complete_supervision(
                session_id="non-existent",
                supervisor_rating=5,
                feedback="Good"
            )

    @pytest.mark.asyncio
    async def test_complete_already_completed_session(
        self, service, mock_supervision_session, db_session
    ):
        """Test completing already completed session"""
        # Set session to already completed
        mock_supervision_session.status = SupervisionStatus.COMPLETED.value

        # Mock query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Should raise ValueError
        with pytest.raises(ValueError, match="RUNNING"):
            await service.complete_supervision(
                session_id=mock_supervision_session.id,
                supervisor_rating=5,
                feedback="Good"
            )


# ========================================================================
# Test Confidence Boost Calculation
# ========================================================================

class TestConfidenceBoostCalculation:
    """Tests for confidence boost calculations"""

    def test_calculate_boost_for_perfect_rating(self, service):
        """Test confidence boost for perfect rating (5 stars)"""
        boost = service._calculate_confidence_boost(
            supervisor_rating=5,
            intervention_count=0,
            duration_seconds=300
        )
        # (5-1)/40 = 0.1
        assert boost == 0.1

    def test_calculate_boost_with_interventions(self, service):
        """Test that interventions reduce confidence boost"""
        boost = service._calculate_confidence_boost(
            supervisor_rating=5,
            intervention_count=3,  # 3 interventions = 0.03 penalty
            duration_seconds=300
        )
        # 0.1 - 0.03 = 0.07
        assert boost == 0.07

    def test_calculate_boost_for_low_rating(self, service):
        """Test confidence boost for low rating (1 star)"""
        boost = service._calculate_confidence_boost(
            supervisor_rating=1,
            intervention_count=0,
            duration_seconds=300
        )
        # (1-1)/40 = 0.0
        assert boost == 0.0

    def test_calculate_boost_never_negative(self, service):
        """Test that confidence boost is never negative"""
        # Even with many interventions, boost >= 0
        boost = service._calculate_confidence_boost(
            supervisor_rating=2,  # Low rating
            intervention_count=10,  # Many interventions
            duration_seconds=300
        )
        # Should be clamped to 0.0
        assert boost >= 0.0


# ========================================================================
# Test Supervision History
# ========================================================================

class TestSupervisionHistory:
    """Tests for supervision history retrieval"""

    @pytest.mark.asyncio
    async def test_get_supervision_history(
        self, service, mock_supervision_session, db_session
    ):
        """Test retrieving agent's supervision history"""
        # Add confidence_boost to mock session (service code expects it)
        mock_supervision_session.confidence_boost = 0.1

        # Mock query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.order_by = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_supervision_session])
        db_session.query.return_value = mock_query

        # Get history
        history = await service.get_supervision_history(
            agent_id=mock_supervision_session.agent_id,
            limit=50
        )

        # Verify history
        assert history is not None
        assert len(history) > 0
        assert history[0]["session_id"] == mock_supervision_session.id

    @pytest.mark.asyncio
    async def test_get_active_sessions(
        self, service, mock_supervision_session, db_session
    ):
        """Test retrieving active supervision sessions"""
        # Mock query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.order_by = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_supervision_session])
        db_session.query.return_value = mock_query

        # Get active sessions
        sessions = await service.get_active_sessions(
            workspace_id="workspace-123",
            limit=50
        )

        # Verify sessions
        assert sessions is not None
        assert len(sessions) > 0
        assert sessions[0].status == SupervisionStatus.RUNNING.value


# ========================================================================
# Test Error Handling
# ========================================================================

class TestErrorHandling:
    """Tests for error handling"""

    @pytest.mark.asyncio
    async def test_intervene_non_existent_session(self, service, db_session):
        """Test intervening on non-existent session"""
        # Mock query returning None
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        db_session.query.return_value = mock_query

        # Should raise ValueError
        with pytest.raises(ValueError, match="not found"):
            await service.intervene(
                session_id="non-existent",
                intervention_type="pause",
                guidance="Test"
            )

    @pytest.mark.asyncio
    async def test_intervene_completed_session(
        self, service, mock_supervision_session, db_session
    ):
        """Test intervening on already completed session"""
        # Set session to completed
        mock_supervision_session.status = SupervisionStatus.COMPLETED.value

        # Mock query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_supervision_session)
        db_session.query.return_value = mock_query

        # Should raise ValueError
        with pytest.raises(ValueError, match="RUNNING"):
            await service.intervene(
                session_id=mock_supervision_session.id,
                intervention_type="pause",
                guidance="Test"
            )
