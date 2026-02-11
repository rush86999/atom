"""
Unit tests for SupervisionService

Tests SUPERVISED agent monitoring, intervention tracking, and session lifecycle.
Covers real-time monitoring, control operations (pause/correct/terminate), and audit trail.

Coverage target: 80%+ for supervision_service.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.supervision_service import (
    SupervisionService,
    SupervisionEvent,
    InterventionResult,
    SupervisionOutcome,
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentExecution,
    SupervisionSession,
    SupervisionStatus,
)


class TestSupervisionSessionCreation:
    """Test supervision session creation and lifecycle"""

    @pytest.mark.asyncio
    async def test_start_supervision_session_creates_session(self, db_session: Session):
        """
        Test starting supervision session creates session with RUNNING status.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_1",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            user_id="test_user",
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        # Act
        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test_action"},
            workspace_id="test_workspace",
            supervisor_id="test_supervisor"
        )

        # Assert
        assert session is not None
        assert session.id is not None
        assert session.agent_id == agent.id
        assert session.agent_name == agent.name
        assert session.workspace_id == "test_workspace"
        assert session.status == SupervisionStatus.RUNNING.value
        assert session.supervisor_id == "test_supervisor"
        assert session.started_at is not None
        assert session.intervention_count == 0

    @pytest.mark.asyncio
    async def test_start_supervision_missing_agent_raises_error(self, db_session: Session):
        """
        Test starting supervision with nonexistent agent raises ValueError.
        """
        # Arrange
        service = SupervisionService(db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="Agent .* not found"):
            await service.start_supervision_session(
                agent_id="nonexistent_agent",
                trigger_context={"action_type": "test"},
                workspace_id="test_workspace",
                supervisor_id="test_supervisor"
            )


class TestInterventionTracking:
    """Test intervention recording and tracking"""

    @pytest.mark.asyncio
    async def test_intervene_pause_operation(self, db_session: Session):
        """
        Test pause intervention records correctly and pauses session.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_2",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test"},
            workspace_id="test_workspace",
            supervisor_id="test_supervisor"
        )

        # Act - Pause intervention
        result = await service.intervene(
            session_id=session.id,
            intervention_type="pause",
            guidance="Pause to review output"
        )

        # Assert
        assert result.success is True
        assert result.session_state == "paused"
        assert "paused" in result.message.lower()
        assert "Pause to review output" in result.message

        # Verify intervention was recorded
        db_session.refresh(session)
        assert session.intervention_count == 1
        assert len(session.interventions) == 1
        assert session.interventions[0]["type"] == "pause"
        assert session.interventions[0]["guidance"] == "Pause to review output"

    @pytest.mark.asyncio
    async def test_intervene_correct_operation(self, db_session: Session):
        """
        Test correct intervention updates agent and continues execution.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_3",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test"},
            workspace_id="test_workspace",
            supervisor_id="test_supervisor"
        )

        # Act - Correct intervention
        result = await service.intervene(
            session_id=session.id,
            intervention_type="correct",
            guidance="Use different parameters"
        )

        # Assert
        assert result.success is True
        assert result.session_state == "running"
        assert "correction applied" in result.message.lower()
        assert "Use different parameters" in result.message

        db_session.refresh(session)
        assert session.intervention_count == 1

    @pytest.mark.asyncio
    async def test_intervene_terminate_operation(self, db_session: Session):
        """
        Test terminate intervention stops session and marks as INTERRUPTED.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_4",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test"},
            workspace_id="test_workspace",
            supervisor_id="test_supervisor"
        )

        # Act - Terminate intervention
        result = await service.intervene(
            session_id=session.id,
            intervention_type="terminate",
            guidance="Critical error - stop execution"
        )

        # Assert
        assert result.success is True
        assert result.session_state == "terminated"
        assert "terminated" in result.message.lower()

        # Verify session was terminated
        db_session.refresh(session)
        assert session.status == SupervisionStatus.INTERRUPTED.value
        assert session.completed_at is not None

    @pytest.mark.asyncio
    async def test_intervene_invalid_session_raises_error(self, db_session: Session):
        """
        Test intervening on nonexistent session raises ValueError.
        """
        # Arrange
        service = SupervisionService(db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="Supervision session .* not found"):
            await service.intervene(
                session_id="nonexistent_session",
                intervention_type="pause",
                guidance="Test"
            )

    @pytest.mark.asyncio
    async def test_intervene_invalid_intervention_type_raises_error(self, db_session: Session):
        """
        Test invalid intervention type raises ValueError.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_5",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test"},
            workspace_id="test_workspace",
            supervisor_id="test_supervisor"
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown intervention type"):
            await service.intervene(
                session_id=session.id,
                intervention_type="invalid_type",
                guidance="Test"
            )


class TestSupervisionCompletion:
    """Test supervision session completion and outcomes"""

    @pytest.mark.asyncio
    async def test_complete_supervision_updates_agent_confidence(self, db_session: Session):
        """
        Test completing supervision updates agent confidence based on rating.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_6",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test"},
            workspace_id="test_workspace",
            supervisor_id="test_supervisor"
        )

        # Wait a bit to have a duration
        import time
        time.sleep(0.1)

        # Act - Complete with high rating
        outcome = await service.complete_supervision(
            session_id=session.id,
            supervisor_rating=5,  # Excellent
            feedback="Great performance"
        )

        # Assert
        assert outcome.session_id == session.id
        assert outcome.success is True  # Rating >= 3
        assert outcome.supervisor_rating == 5
        assert outcome.feedback == "Great performance"
        assert outcome.confidence_boost > 0

        # Verify agent confidence increased
        db_session.refresh(agent)
        assert agent.confidence_score > 0.75

        # Verify session was completed
        db_session.refresh(session)
        assert session.status == SupervisionStatus.COMPLETED.value
        assert session.completed_at is not None
        assert session.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_complete_supervision_promotes_to_autonomous(self, db_session: Session):
        """
        Test excellent supervision can promote agent to AUTONOMOUS.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_7",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.89,  # Just below threshold
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test"},
            workspace_id="test_workspace",
            supervisor_id="test_supervisor"
        )

        # Act - Complete with perfect rating and no interventions
        outcome = await service.complete_supervision(
            session_id=session.id,
            supervisor_rating=5,
            feedback="Perfect performance, ready for autonomy"
        )

        # Assert
        assert outcome.confidence_boost > 0

        # Verify promotion to AUTONOMOUS
        db_session.refresh(agent)
        assert agent.confidence_score >= 0.9
        assert agent.status == AgentStatus.AUTONOMOUS.value

    @pytest.mark.asyncio
    async def test_complete_supervision_low_rating_small_boost(self, db_session: Session):
        """
        Test low supervisor rating results in minimal confidence boost.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_8",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test"},
            workspace_id="test_workspace",
            supervisor_id="test_supervisor"
        )

        # Act - Complete with low rating
        outcome = await service.complete_supervision(
            session_id=session.id,
            supervisor_rating=1,  # Poor
            feedback="Needs improvement"
        )

        # Assert
        assert outcome.success is False  # Rating < 3
        assert outcome.confidence_boost < 0.05  # Minimal boost

        # Verify agent didn't get promoted
        db_session.refresh(agent)
        assert agent.status == AgentStatus.SUPERVISED.value


class TestConfidenceBoostCalculation:
    """Test confidence boost calculation based on supervision performance"""

    def test_calculate_confidence_boost_formula(self):
        """
        Test confidence boost formula: rating-based with intervention penalty.
        """
        service = SupervisionService(None)

        # Test rating 5 (excellent): (5-1)/40 = 0.1 base
        boost = service._calculate_confidence_boost(
            supervisor_rating=5,
            intervention_count=0,
            duration_seconds=3600  # 1 hour
        )
        assert boost == 0.1  # No penalty

        # Test with intervention penalty: each intervention subtracts 0.01
        boost_with_penalty = service._calculate_confidence_boost(
            supervisor_rating=5,
            intervention_count=3,  # 3 interventions
            duration_seconds=3600
        )
        assert boost_with_penalty == 0.07  # 0.1 - 0.03

        # Test rating 1 (poor): (1-1)/40 = 0.0 base
        boost_poor = service._calculate_confidence_boost(
            supervisor_rating=1,
            intervention_count=0,
            duration_seconds=3600
        )
        assert boost_poor == 0.0

        # Test minimum boost is 0.0
        boost_minimum = service._calculate_confidence_boost(
            supervisor_rating=1,
            intervention_count=10,  # Would be negative, but clamped
            duration_seconds=3600
        )
        assert boost_minimum == 0.0


class TestActiveSessions:
    """Test retrieval of active supervision sessions"""

    @pytest.mark.asyncio
    async def test_get_active_sessions_returns_running_sessions(self, db_session: Session):
        """
        Test retrieving active supervision sessions.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_9",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        # Create active session
        active_session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test"},
            workspace_id="test_workspace",
            supervisor_id="test_supervisor"
        )

        # Act
        active_sessions = await service.get_active_sessions(
            workspace_id="test_workspace",
            limit=10
        )

        # Assert
        assert len(active_sessions) >= 1
        assert any(s.id == active_session.id for s in active_sessions)
        assert all(s.status == SupervisionStatus.RUNNING.value for s in active_sessions)

    @pytest.mark.asyncio
    async def test_get_supervision_history_returns_past_sessions(self, db_session: Session):
        """
        Test retrieving agent's supervision history.
        """
        # Arrange
        agent = AgentRegistry(
            id="supervised_agent_10",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
        )
        db_session.add(agent)
        db_session.commit()

        service = SupervisionService(db_session)

        # Create and complete a session
        session = await service.start_supervision_session(
            agent_id=agent.id,
            trigger_context={"action_type": "test"},
            workspace_id="test_workspace",
            supervisor_id="test_supervisor"
        )

        await service.complete_supervision(
            session_id=session.id,
            supervisor_rating=4,
            feedback="Good work"
        )

        # Act
        history = await service.get_supervision_history(
            agent_id=agent.id,
            limit=10
        )

        # Assert
        assert len(history) >= 1
        assert history[0]["session_id"] == session.id
        assert history[0]["status"] == SupervisionStatus.COMPLETED.value
        assert "duration_seconds" in history[0]
        assert "supervisor_rating" in history[0]
