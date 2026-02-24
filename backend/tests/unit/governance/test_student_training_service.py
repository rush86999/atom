"""
Unit tests for StudentTrainingService

Tests training duration estimation, session creation, and historical data analysis.
Covers AI-based estimation, session lifecycle, and confidence boost calculation.

Coverage target: 80%+ for student_training_service.py
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.student_training_service import (
    StudentTrainingService,
    TrainingDurationEstimate,
    TrainingOutcome,
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    TriggerSource,
    ProposalStatus,
    ProposalType,
    TrainingSession,
)


class TestTrainingDurationEstimation:
    """Test AI-based training duration estimation"""

    @pytest.mark.asyncio
    async def test_estimate_training_duration_with_confidence_below_05(self, db_session: Session):
        """
        Test training duration estimation for low confidence agents (<0.5).
        Should recommend longer training for agents with larger confidence gaps.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["task_execution", "context_understanding"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        assert isinstance(estimate, TrainingDurationEstimate)
        assert estimate.estimated_hours > 0
        assert 0 <= estimate.confidence <= 1
        assert estimate.min_hours <= estimate.estimated_hours <= estimate.max_hours
        assert "confidence" in estimate.reasoning.lower()
        assert "capability" in estimate.reasoning.lower()
        assert isinstance(estimate.similar_agents, list)

    @pytest.mark.asyncio
    async def test_estimate_training_duration_for_multiple_capability_gaps(self, db_session: Session):
        """
        Test that more capability gaps result in longer training estimates.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_2",
            name="Student Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act - Test with multiple gaps
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1", "gap2", "gap3", "gap4", "gap5"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        assert estimate.estimated_hours > 0
        # capability_gaps is not returned in estimate (service only uses it for calculation)
        # More gaps should result in longer duration (gaps_factor in formula)
        assert "5" in estimate.reasoning  # Should mention 5 gaps

    @pytest.mark.asyncio
    async def test_estimate_training_duration_with_similar_agents_history(self, db_session: Session):
        """
        Test estimation uses historical data from similar agents when available.
        """
        # Arrange - Create similar agents with completed training
        similar_agent = AgentRegistry(
            id="similar_agent_1",
            name="Similar Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(similar_agent)

        # Create completed training session for similar agent
        training_session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal_1",
            agent_id=similar_agent.id,
            agent_name=similar_agent.name,
            supervisor_id="test_supervisor",  # Required field
            status="completed",
            started_at=datetime.now() - timedelta(days=5),
            completed_at=datetime.now() - timedelta(days=1),
            duration_seconds=144000,  # 40 hours
        )
        db_session.add(training_session)
        db_session.commit()

        agent = AgentRegistry(
            id="student_agent_3",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["task_execution"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        assert estimate.estimated_hours > 0
        assert len(estimate.similar_agents) == 1
        # similar_agents contains agent info
        assert "Historical Data" in estimate.reasoning
        assert "1 similar" in estimate.reasoning

    @pytest.mark.asyncio
    async def test_estimate_training_duration_default_for_new_agent(self, db_session: Session):
        """
        Test that new agents without historical data get default estimates.
        """
        # Arrange
        agent = AgentRegistry(
            id="new_student_agent",
            name="New Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.1,  # Very low confidence
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["basic_task"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        assert estimate.estimated_hours > 0
        assert len(estimate.similar_agents) == 0  # No similar agents
        assert "0 similar" in estimate.reasoning


class TestSessionCreation:
    """Test training session creation and state tracking"""

    @pytest.mark.asyncio
    async def test_approve_training_creates_session(self, db_session: Session):
        """
        Test approving training proposal creates training session.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_4",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # First create a training proposal
        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act - Approve the training
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications=None
        )

        # Assert
        assert session is not None
        assert session.agent_id == agent.id
        assert session.status == "scheduled"
        assert session.supervisor_id == "test_user"
        assert session.total_tasks > 0

        # Verify proposal was updated
        db_session.refresh(proposal)
        assert proposal.status == ProposalStatus.APPROVED.value
        assert proposal.approved_by == "test_user"
        assert proposal.training_start_date is not None
        assert proposal.training_end_date is not None

    @pytest.mark.asyncio
    async def test_approve_training_with_user_modifications(self, db_session: Session):
        """
        Test approving training with user-specified duration override.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_5",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act - Approve with custom duration and daily limit
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications={
                "duration_override_hours": 20.0,  # Override AI estimate
                "hours_per_day_limit": 4.0  # Only 4 hours per day
            }
        )

        # Assert
        assert session is not None
        db_session.refresh(proposal)
        assert proposal.user_override_duration_hours == 20.0
        assert proposal.hours_per_day_limit == 4.0

        # Check end date calculation: 20 hours / 4 hours per day = 5 days
        expected_duration_days = 20.0 / 4.0
        actual_duration_days = (proposal.training_end_date - proposal.training_start_date).days
        assert abs(actual_duration_days - expected_duration_days) <= 1  # Allow 1 day variance

    @pytest.mark.asyncio
    async def test_approve_training_invalid_status_raises_error(self, db_session: Session):
        """
        Test approving training with invalid proposal status raises error.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_6",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act & Assert - Try to approve a proposal that doesn't exist
        with pytest.raises(ValueError, match="Proposal .* not found"):
            await service.approve_training(
                proposal_id="nonexistent_proposal",
                user_id="test_user",
                modifications=None
            )


class TestTrainingCompletion:
    """Test training completion and confidence boost calculation"""

    @pytest.mark.asyncio
    async def test_complete_training_session_updates_confidence(self, db_session: Session):
        """
        Test completing training session updates agent confidence.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_7",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Create a training session
        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act - Complete training with good performance
        outcome = TrainingOutcome(
            performance_score=0.8,  # Good performance
            supervisor_feedback="Excellent progress",
            errors_count=2,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task_execution", "context_understanding"],
            capability_gaps_remaining=[]
        )

        result = await service.complete_training_session(
            session_id=session.id,
            outcome=outcome
        )

        # Assert
        assert result["session_id"] == session.id
        assert result["agent_id"] == agent.id
        assert result["performance_score"] == 0.8
        assert result["confidence_boost"] > 0
        assert result["new_confidence"] > result["old_confidence"]
        assert result["promoted_to_intern"] is True  # Should promote to INTERN

        # Verify agent was updated
        db_session.refresh(agent)
        assert agent.status == AgentStatus.INTERN.value
        assert agent.confidence_score >= 0.5

    @pytest.mark.asyncio
    async def test_complete_training_poor_performance_small_boost(self, db_session: Session):
        """
        Test poor training performance results in smaller confidence boost.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_8",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act - Complete with poor performance
        outcome = TrainingOutcome(
            performance_score=0.2,  # Poor performance
            supervisor_feedback="Needs more practice",
            errors_count=10,
            tasks_completed=3,
            total_tasks=10,
            capabilities_developed=["basic_task"],
            capability_gaps_remaining=["advanced_task", "context_understanding"]
        )

        result = await service.complete_training_session(
            session_id=session.id,
            outcome=outcome
        )

        # Assert
        assert result["confidence_boost"] < 0.1  # Small boost for poor performance
        assert result["promoted_to_intern"] is False  # Not promoted

        # Verify agent still STUDENT
        db_session.refresh(agent)
        assert agent.status == AgentStatus.STUDENT.value

    @pytest.mark.asyncio
    async def test_complete_training_excellent_performance_large_boost(self, db_session: Session):
        """
        Test excellent training performance results in larger confidence boost.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_9",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.45,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.45,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act - Complete with excellent performance
        outcome = TrainingOutcome(
            performance_score=0.95,  # Excellent
            supervisor_feedback="Outstanding work",
            errors_count=0,
            tasks_completed=10,
            total_tasks=10,
            capabilities_developed=["task_execution", "context_understanding", "advanced_task"],
            capability_gaps_remaining=[]
        )

        result = await service.complete_training_session(
            session_id=session.id,
            outcome=outcome
        )

        # Assert
        assert result["confidence_boost"] >= 0.15  # Large boost for excellent performance
        assert result["promoted_to_intern"] is True


class TestTrainingHistory:
    """Test training history retrieval"""

    @pytest.mark.asyncio
    async def test_get_training_history_returns_sessions(self, db_session: Session):
        """
        Test retrieving agent's training history.
        """
        # Arrange
        agent = AgentRegistry(
            id="student_agent_10",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Create multiple training sessions
        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal1 = await service.create_training_proposal(blocked_trigger)
        session1 = await service.approve_training(proposal1.id, "test_user", None)

        # Complete the session
        outcome = TrainingOutcome(
            performance_score=0.8,
            supervisor_feedback="Good",
            errors_count=1,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task1"],
            capability_gaps_remaining=[]
        )
        await service.complete_training_session(session1.id, outcome)

        # Act
        history = await service.get_training_history(agent_id=agent.id, limit=10)

        # Assert
        assert len(history) > 0
        assert history[0]["session_id"] == session1.id
        assert history[0]["status"] == "completed"
        assert history[0]["performance_score"] == 0.8
        assert "proposal_title" in history[0]

    @pytest.mark.asyncio
    async def test_get_training_history_empty_for_new_agent(self, db_session: Session):
        """
        Test that new agents have empty training history.
        """
        # Arrange
        agent = AgentRegistry(
            id="new_agent_1",
            name="New Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        history = await service.get_training_history(agent_id=agent.id, limit=10)

        # Assert
        assert len(history) == 0


class TestConfidenceBoostCalculation:
    """Test confidence boost calculation based on performance"""

    def test_calculate_confidence_boost_poor_performance(self):
        """
        Test poor performance (<0.3) results in minimal boost (0.05).
        """
        # Arrange
        service = StudentTrainingService(None)  # No DB needed for this test

        # Act
        boost = service._calculate_confidence_boost(performance_score=0.2)

        # Assert
        assert boost == 0.05

    def test_calculate_confidence_boost_below_average(self):
        """
        Test below average performance (0.3-0.5) results in small boost (0.10).
        """
        service = StudentTrainingService(None)

        boost = service._calculate_confidence_boost(performance_score=0.4)

        assert boost == 0.10

    def test_calculate_confidence_boost_good(self):
        """
        Test good performance (0.5-0.7) results in medium boost (0.15).
        """
        service = StudentTrainingService(None)

        boost = service._calculate_confidence_boost(performance_score=0.6)

        assert boost == 0.15

    def test_calculate_confidence_boost_excellent(self):
        """
        Test excellent performance (0.7-1.0) results in large boost (0.20).
        """
        service = StudentTrainingService(None)

        boost = service._calculate_confidence_boost(performance_score=0.9)

        assert boost == 0.20


class TestCapabilityGapIdentification:
    """Test capability gap identification based on blocked triggers"""

    @pytest.mark.asyncio
    async def test_identify_capability_gaps_for_trigger_type(self, db_session: Session):
        """
        Test capability gaps are identified based on trigger type.
        """
        # Arrange
        agent = AgentRegistry(
            id="agent_1",
            name="Test Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="workflow_trigger",  # Workflow trigger type
            trigger_context={"action_type": "workflow_trigger"},
            routing_decision="training",
            block_reason="Test"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        # Act
        gaps = await service._identify_capability_gaps(agent, blocked_trigger)

        # Assert
        assert isinstance(gaps, list)
        assert len(gaps) > 0
        # Should include workflow-related gaps
        assert any("workflow" in gap.lower() for gap in gaps)

    @pytest.mark.asyncio
    async def test_identify_capability_gaps_includes_category_specific(self, db_session: Session):
        """
        Test capability gaps include category-specific gaps.
        """
        # Arrange
        agent = AgentRegistry(
            id="agent_2",
            name="Finance Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"category": "Finance"},
            routing_decision="training",
            block_reason="Test"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        # Act
        gaps = await service._identify_capability_gaps(agent, blocked_trigger)

        # Assert
        assert isinstance(gaps, list)
        # Should include Finance-specific gaps
        assert any("financial" in gap.lower() for gap in gaps)


class TestLearningRateCalculation:
    """Test learning rate calculation from previous training sessions"""

    @pytest.mark.asyncio
    async def test_calculate_learning_rate_from_sessions(self, db_session: Session):
        """
        Test learning rate is calculated from previous training sessions.
        """
        # Arrange
        agent = AgentRegistry(
            id="agent_3",
            name="Test Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Create training session with good performance
        session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="proposal_1",
            agent_id=agent.id,
            agent_name=agent.name,
            supervisor_id="test_supervisor",  # Required field
            status="completed",
            performance_score=0.85,  # Above average performance
            started_at=datetime.now() - timedelta(days=2),
            completed_at=datetime.now() - timedelta(days=1),
            duration_seconds=3600
        )
        db_session.add(session)
        db_session.commit()

        # Act
        learning_rate = await service._calculate_learning_rate(agent.id)

        # Assert
        assert learning_rate > 1.0  # Good performance = fast learner
        assert learning_rate <= 2.0  # Clamped to max 2.0

    @pytest.mark.asyncio
    async def test_calculate_learning_rate_default_for_new_agent(self, db_session: Session):
        """
        Test new agents get default learning rate (1.0).
        """
        # Arrange
        agent = AgentRegistry(
            id="new_agent_2",
            name="New Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        learning_rate = await service._calculate_learning_rate(agent.id)

        # Assert
        assert learning_rate == 1.0  # Default for agents with no history


class TestCreateTrainingProposal:
    """Test training proposal creation from blocked triggers"""

    @pytest.mark.asyncio
    async def test_proposal_created_for_agent_message_trigger(self, db_session: Session):
        """Test proposal created for agent_message trigger type"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_msg_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        assert proposal.agent_id == agent.id
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert proposal.proposal_type == ProposalType.TRAINING.value
        assert proposal.estimated_duration_hours > 0
        assert len(proposal.capability_gaps) > 0
        assert len(proposal.learning_objectives) > 0
        assert "agent_message" in proposal.description
        assert blocked_trigger.proposal_id == proposal.id

    @pytest.mark.asyncio
    async def test_proposal_created_for_workflow_trigger(self, db_session: Session):
        """Test proposal created for workflow_trigger trigger type"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_wf_1",
            name="Student Agent",
            category="Operations",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="workflow_trigger",
            trigger_context={"action": "automate_process"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        assert proposal.agent_id == agent.id
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert "workflow_trigger" in proposal.description
        # Should include workflow-specific gaps
        assert any("workflow" in gap.lower() for gap in proposal.capability_gaps)

    @pytest.mark.asyncio
    async def test_proposal_created_for_form_submit_trigger(self, db_session: Session):
        """Test proposal created for form_submit trigger type"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_form_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="form_submit",
            trigger_context={"form_id": "test_form"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        assert proposal.agent_id == agent.id
        assert "form_submit" in proposal.description
        # Should include form-specific gaps
        assert any("form" in gap.lower() for gap in proposal.capability_gaps)

    @pytest.mark.asyncio
    async def test_proposal_created_for_canvas_update_trigger(self, db_session: Session):
        """Test proposal created for canvas_update trigger type"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_canvas_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="canvas_update",
            trigger_context={"canvas_id": "test_canvas"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        assert proposal.agent_id == agent.id
        assert "canvas_update" in proposal.description
        # Should include canvas-specific gaps
        assert any("visualization" in gap.lower() or "presentation" in gap.lower()
                   for gap in proposal.capability_gaps)

    @pytest.mark.asyncio
    async def test_capability_gaps_include_finance_category(self, db_session: Session):
        """Test capability gaps include Finance-specific gaps"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_finance_1",
            name="Finance Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"category": "Finance"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Should include Finance-specific gaps
        assert any("financial" in gap.lower() for gap in proposal.capability_gaps)

    @pytest.mark.asyncio
    async def test_capability_gaps_include_sales_category(self, db_session: Session):
        """Test capability gaps include Sales-specific gaps"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_sales_1",
            name="Sales Agent",
            category="Sales",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"category": "Sales"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Should include Sales-specific gaps
        assert any("crm" in gap.lower() or "sales" in gap.lower()
                   for gap in proposal.capability_gaps)

    @pytest.mark.asyncio
    async def test_learning_objectives_include_base_objectives(self, db_session: Session):
        """Test learning objectives include base objectives"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_obj_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="workflow_trigger",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Should include base objectives for trigger type
        assert any("workflow_trigger" in obj for obj in proposal.learning_objectives)
        # Should include reliable task completion objective
        assert any("reliable task completion" in obj.lower()
                   for obj in proposal.learning_objectives)
        # Should include decision-making objective
        assert any("decision-making" in obj.lower()
                   for obj in proposal.learning_objectives)

    @pytest.mark.asyncio
    async def test_learning_objectives_include_capability_specific(self, db_session: Session):
        """Test learning objectives include capability-specific objectives (max 5 gaps)"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_obj_2",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Should include capability-specific objectives (max 5 gaps)
        capability_objectives = [obj for obj in proposal.learning_objectives
                                 if "proficiency in" in obj.lower()]
        assert len(capability_objectives) > 0
        # Max 5 capability gaps
        assert len(capability_objectives) <= 5

    @pytest.mark.asyncio
    async def test_scenario_template_selected_from_trigger_context(self, db_session: Session):
        """Test scenario template selected based on category from trigger_context"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_scenario_1",
            name="Student Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"category": "Finance"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Should use Finance scenario template
        assert proposal.training_scenario_template == "Finance Fundamentals"
        assert "Finance Fundamentals" in proposal.title

    @pytest.mark.asyncio
    async def test_duration_estimation_called_with_correct_parameters(self, db_session: Session):
        """Test duration estimation called with target_maturity=INTERN"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_duration_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Duration estimation should be called
        assert proposal.estimated_duration_hours > 0
        assert proposal.duration_estimation_confidence >= 0
        assert proposal.duration_estimation_reasoning is not None
        # Target maturity should be INTERN
        assert "0.5" in proposal.duration_estimation_reasoning or "INTERN" in proposal.duration_estimation_reasoning


class TestProposalGenerationEdgeCases:
    """Test edge cases in proposal generation"""

    @pytest.mark.asyncio
    async def test_proposal_creation_fails_for_nonexistent_agent(self, db_session: Session):
        """Test proposal creation fails for non-existent agent (ValueError)"""
        # Arrange
        blocked_trigger = BlockedTriggerContext(
            agent_id="nonexistent_agent",
            agent_name="Ghost Agent",
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="Agent .* not found"):
            await service.create_training_proposal(blocked_trigger)

    @pytest.mark.asyncio
    async def test_proposal_with_no_capability_gaps_handled_gracefully(self, db_session: Session):
        """Test proposal with no capability gaps handled gracefully"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_no_gaps_1",
            name="Student Agent",
            category="Unknown",  # Unknown category
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        # Use unknown trigger type to minimize gaps
        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="unknown_trigger",
            trigger_context={},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Should still create proposal with empty or minimal gaps
        assert proposal is not None
        assert proposal.capability_gaps is not None

    @pytest.mark.asyncio
    async def test_proposal_with_empty_trigger_context_uses_default_scenario(self, db_session: Session):
        """Test proposal with empty trigger_context uses default scenario"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_empty_ctx_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={},  # Empty context
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Should use default scenario
        assert proposal.training_scenario_template == "General Operations"

    @pytest.mark.asyncio
    async def test_deduplication_of_capability_gaps(self, db_session: Session):
        """Test deduplication of capability gaps (duplicate gaps removed)"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_dedup_1",
            name="Student Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"category": "Finance"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Should not have duplicate gaps
        assert len(proposal.capability_gaps) == len(set(proposal.capability_gaps))

    @pytest.mark.asyncio
    async def test_proposal_title_includes_scenario_template_name(self, db_session: Session):
        """Test proposal title includes scenario template name"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_title_1",
            name="Test Agent",
            category="Sales",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"category": "Sales"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Title should include scenario template
        assert "Sales Operations" in proposal.title
        assert "Fundamentals" in proposal.title

    @pytest.mark.asyncio
    async def test_proposal_description_includes_blocked_task_and_gaps(self, db_session: Session):
        """Test proposal description includes blocked task type and capability gaps"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_desc_1",
            name="Test Agent",
            category="Operations",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="workflow_trigger",
            trigger_context={"category": "Operations"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        proposal = await service.create_training_proposal(blocked_trigger)

        # Assert
        # Description should include blocked task type
        assert "workflow_trigger" in proposal.description
        # Description should include capability gaps
        assert "Capability Gaps:" in proposal.description
        # Description should mention training purpose
        assert "training" in proposal.description.lower()


class TestApprovalWithModifications:
    """Test training approval with user modifications"""

    @pytest.mark.asyncio
    async def test_duration_override_applied(self, db_session: Session):
        """Test duration override applied (user_override_duration_hours set)"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_mod_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act - Approve with duration override
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications={"duration_override_hours": 50.0}
        )

        # Assert
        db_session.refresh(proposal)
        assert proposal.user_override_duration_hours == 50.0

    @pytest.mark.asyncio
    async def test_hours_per_day_limit_applied(self, db_session: Session):
        """Test hours per day limit applied (hours_per_day_limit set)"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_mod_2",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act - Approve with hours per day limit
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications={"hours_per_day_limit": 6.0}
        )

        # Assert
        db_session.refresh(proposal)
        assert proposal.hours_per_day_limit == 6.0

    @pytest.mark.asyncio
    async def test_training_end_date_calculated_with_custom_hours_per_day(self, db_session: Session):
        """Test training end date calculated with custom hours_per_day_limit"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_mod_3",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act - Approve with custom duration and hours per day
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications={
                "duration_override_hours": 40.0,
                "hours_per_day_limit": 5.0  # 5 hours/day = 8 days
            }
        )

        # Assert
        db_session.refresh(proposal)
        expected_days = 40.0 / 5.0  # 8 days
        actual_days = (proposal.training_end_date - proposal.training_start_date).days
        assert abs(actual_days - expected_days) <= 1  # Allow 1 day variance

    @pytest.mark.asyncio
    async def test_training_end_date_calculated_with_default_8_hours_per_day(self, db_session: Session):
        """Test training end date calculated with default 8 hours/day when no limit"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_mod_4",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        original_duration = proposal.estimated_duration_hours

        # Act - Approve without custom hours per day
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications=None  # No custom limit
        )

        # Assert
        db_session.refresh(proposal)
        assert proposal.hours_per_day_limit is None  # Should remain None
        # Should use default 8 hours/day
        expected_days = original_duration / 8.0
        actual_days = (proposal.training_end_date - proposal.training_start_date).days
        assert abs(actual_days - expected_days) <= 1

    @pytest.mark.asyncio
    async def test_proposal_status_updated_to_approved(self, db_session: Session):
        """Test proposal status updated to APPROVED"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_mod_5",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications=None
        )

        # Assert
        db_session.refresh(proposal)
        assert proposal.status == ProposalStatus.APPROVED.value

    @pytest.mark.asyncio
    async def test_approved_by_and_approved_at_timestamps_set(self, db_session: Session):
        """Test approved_by and approved_at timestamps set"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_mod_6",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="admin_user",
            modifications=None
        )

        # Assert
        db_session.refresh(proposal)
        assert proposal.approved_by == "admin_user"
        assert proposal.approved_at is not None
        assert proposal.approved_at <= datetime.now()

    @pytest.mark.asyncio
    async def test_training_start_date_set_to_current_datetime(self, db_session: Session):
        """Test training start date set to current datetime"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_mod_7",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        before_approval = datetime.now()

        # Act
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications=None
        )

        # Assert
        db_session.refresh(proposal)
        assert proposal.training_start_date is not None
        assert before_approval <= proposal.training_start_date <= datetime.now()

    @pytest.mark.asyncio
    async def test_training_session_created_with_correct_total_tasks(self, db_session: Session):
        """Test training session created with correct total_tasks (from learning_objectives length)"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_mod_8",
            name="Student Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"category": "Finance"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        expected_tasks = len(proposal.learning_objectives)

        # Act
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications=None
        )

        # Assert
        assert session.total_tasks == expected_tasks
        assert session.total_tasks > 0


class TestApprovalErrorHandling:
    """Test approval workflow error handling"""

    @pytest.mark.asyncio
    async def test_value_error_for_nonexistent_proposal(self, db_session: Session):
        """Test ValueError raised for non-existent proposal"""
        # Arrange
        service = StudentTrainingService(db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="Proposal .* not found"):
            await service.approve_training(
                proposal_id="nonexistent_proposal_id",
                user_id="test_user",
                modifications=None
            )

    @pytest.mark.asyncio
    async def test_value_error_for_proposal_not_in_proposed_status(self, db_session: Session):
        """Test ValueError raised for proposal not in PROPOSED status"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_err_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Change status to APPROVED
        proposal.status = ProposalStatus.APPROVED.value
        db_session.commit()

        # Act & Assert - Try to approve already approved proposal
        with pytest.raises(ValueError, match="must be in PROPOSED status"):
            await service.approve_training(
                proposal_id=proposal.id,
                user_id="test_user",
                modifications=None
            )

    @pytest.mark.asyncio
    async def test_training_session_created_with_supervisor_id_from_user_id(self, db_session: Session):
        """Test training session created with supervisor_id from user_id"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_err_2",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="supervisor_123",
            modifications=None
        )

        # Assert
        assert session.supervisor_id == "supervisor_123"

    @pytest.mark.asyncio
    async def test_training_session_agent_name_from_proposal(self, db_session: Session):
        """Test training session agent_name from proposal"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_err_3",
            name="Test Agent Name",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications=None
        )

        # Assert
        assert session.agent_name == proposal.agent_name
        assert session.agent_name == "Test Agent Name"

    @pytest.mark.asyncio
    async def test_training_session_initial_status_is_scheduled(self, db_session: Session):
        """Test training session initial status is 'scheduled'"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_err_4",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications=None
        )

        # Assert
        assert session.status == "scheduled"

    @pytest.mark.asyncio
    async def test_database_commit_refresh_called_in_correct_order(self, db_session: Session):
        """Test database commit/refresh called in correct order"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_err_5",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)

        # Act
        session = await service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user",
            modifications=None
        )

        # Assert - Session should have ID after commit/refresh
        assert session.id is not None
        # Verify proposal is updated in DB
        db_session.refresh(proposal)
        assert proposal.status == ProposalStatus.APPROVED.value


class TestTrainingCompletionPromotion:
    """Test training completion and promotion decisions"""

    @pytest.mark.asyncio
    async def test_agent_promoted_to_intern_when_confidence_reaches_05(self, db_session: Session):
        """Test agent promoted to INTERN when confidence reaches 0.5 (exact threshold)"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_promote_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.45,  # Close to threshold
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.45,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act - Complete with excellent performance to boost confidence to 0.5+
        outcome = TrainingOutcome(
            performance_score=0.8,  # Good performance = 0.15 boost
            supervisor_feedback="Excellent",
            errors_count=1,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task_execution"],
            capability_gaps_remaining=[]
        )

        result = await service.complete_training_session(session.id, outcome)

        # Assert
        assert result["promoted_to_intern"] is True
        db_session.refresh(agent)
        assert agent.status == AgentStatus.INTERN.value
        assert agent.confidence_score >= 0.5

    @pytest.mark.asyncio
    async def test_agent_not_promoted_when_confidence_below_05(self, db_session: Session):
        """Test agent NOT promoted when confidence below 0.5"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_promote_2",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,  # Low confidence
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act - Complete with average performance (small boost)
        outcome = TrainingOutcome(
            performance_score=0.4,  # Below average = 0.10 boost
            supervisor_feedback="Needs improvement",
            errors_count=5,
            tasks_completed=6,
            total_tasks=10,
            capabilities_developed=["basic_task"],
            capability_gaps_remaining=["advanced_task"]
        )

        result = await service.complete_training_session(session.id, outcome)

        # Assert
        assert result["promoted_to_intern"] is False
        db_session.refresh(agent)
        assert agent.status == AgentStatus.STUDENT.value
        assert agent.confidence_score < 0.5

    @pytest.mark.asyncio
    async def test_agent_not_promoted_when_already_intern(self, db_session: Session):
        """Test agent NOT promoted when already INTERN (status check)"""
        # Arrange
        agent = AgentRegistry(
            id="intern_agent_promote_1",
            name="Intern Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,  # Already INTERN
            confidence_score=0.6,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Create training session directly (no proposal needed)
        session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal",
            agent_id=agent.id,
            agent_name=agent.name,
            supervisor_id="test_supervisor",
            status="scheduled",
            total_tasks=5,
            started_at=datetime.now()
        )
        db_session.add(session)
        db_session.commit()

        # Act - Complete training
        outcome = TrainingOutcome(
            performance_score=0.9,
            supervisor_feedback="Excellent",
            errors_count=0,
            tasks_completed=5,
            total_tasks=5,
            capabilities_developed=["task1", "task2"],
            capability_gaps_remaining=[]
        )

        result = await service.complete_training_session(session.id, outcome)

        # Assert - Should not promote again
        assert result["promoted_to_intern"] is False
        db_session.refresh(agent)
        assert agent.status == AgentStatus.INTERN.value  # Still INTERN

    @pytest.mark.asyncio
    async def test_confidence_boost_capped_at_10(self, db_session: Session):
        """Test confidence boost capped at 1.0 (max value)"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_cap_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.95,  # Very high already
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Create training session directly
        session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal",
            agent_id=agent.id,
            agent_name=agent.name,
            supervisor_id="test_supervisor",
            status="scheduled",
            total_tasks=5,
            started_at=datetime.now()
        )
        db_session.add(session)
        db_session.commit()

        # Act - Complete with excellent performance
        outcome = TrainingOutcome(
            performance_score=1.0,  # Perfect score = 0.20 boost
            supervisor_feedback="Perfect",
            errors_count=0,
            tasks_completed=5,
            total_tasks=5,
            capabilities_developed=["all_tasks"],
            capability_gaps_remaining=[]
        )

        result = await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(agent)
        assert agent.confidence_score == 1.0  # Capped at max
        assert result["new_confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_session_status_updated_to_completed(self, db_session: Session):
        """Test session status updated to 'completed'"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_status_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.7,
            supervisor_feedback="Good",
            errors_count=2,
            tasks_completed=8,
            total_tasks=10,
            capabilities_developed=["task1"],
            capability_gaps_remaining=[]
        )

        await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(session)
        assert session.status == "completed"

    @pytest.mark.asyncio
    async def test_session_completed_at_timestamp_set(self, db_session: Session):
        """Test session completed_at timestamp set"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_timestamp_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        before_completion = datetime.now()

        # Act
        outcome = TrainingOutcome(
            performance_score=0.7,
            supervisor_feedback="Good",
            errors_count=2,
            tasks_completed=8,
            total_tasks=10,
            capabilities_developed=["task1"],
            capability_gaps_remaining=[]
        )

        await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(session)
        assert session.completed_at is not None
        assert before_completion <= session.completed_at <= datetime.now()

    @pytest.mark.asyncio
    async def test_session_duration_seconds_calculated(self, db_session: Session):
        """Test session duration_seconds calculated from started_at to completed_at"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_duration_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Set started_at to simulate training start
        session.started_at = datetime.now() - timedelta(hours=2)  # Started 2 hours ago
        db_session.commit()

        # Act
        outcome = TrainingOutcome(
            performance_score=0.7,
            supervisor_feedback="Good",
            errors_count=2,
            tasks_completed=8,
            total_tasks=10,
            capabilities_developed=["task1"],
            capability_gaps_remaining=[]
        )

        await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(session)
        assert session.duration_seconds is not None
        assert session.duration_seconds > 0
        # Duration should be approximately 2 hours (7200 seconds)
        assert 7000 < session.duration_seconds < 7500  # Allow some variance

    @pytest.mark.asyncio
    async def test_session_outcomes_dict_populated(self, db_session: Session):
        """Test session outcomes dict populated with performance_score, tasks_completed"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_outcomes_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.75,
            supervisor_feedback="Good work",
            errors_count=2,
            tasks_completed=8,
            total_tasks=10,
            capabilities_developed=["task1", "task2"],
            capability_gaps_remaining=[]
        )

        await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(session)
        assert session.outcomes is not None
        assert session.outcomes["performance_score"] == 0.75
        assert session.outcomes["tasks_completed"] == 8
        assert session.outcomes["total_tasks"] == 10


class TestBlockedTriggerResolution:
    """Test blocked trigger resolution on training completion"""

    @pytest.mark.asyncio
    async def test_blocked_trigger_resolved_set_to_true(self, db_session: Session):
        """Test blocked trigger resolved set to True"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_resolve_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.8,
            supervisor_feedback="Good",
            errors_count=1,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task1"],
            capability_gaps_remaining=[]
        )

        await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(blocked_trigger)
        assert blocked_trigger.resolved is True

    @pytest.mark.asyncio
    async def test_blocked_trigger_resolved_at_timestamp_set(self, db_session: Session):
        """Test blocked trigger resolved_at timestamp set"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_resolve_2",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        before_completion = datetime.now()

        # Act
        outcome = TrainingOutcome(
            performance_score=0.8,
            supervisor_feedback="Good",
            errors_count=1,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task1"],
            capability_gaps_remaining=[]
        )

        await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(blocked_trigger)
        assert blocked_trigger.resolved_at is not None
        assert before_completion <= blocked_trigger.resolved_at <= datetime.now()

    @pytest.mark.asyncio
    async def test_blocked_trigger_resolution_outcome_includes_performance_score(self, db_session: Session):
        """Test blocked trigger resolution_outcome includes performance score"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_resolve_3",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.85,
            supervisor_feedback="Great",
            errors_count=1,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task1"],
            capability_gaps_remaining=[]
        )

        await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(blocked_trigger)
        assert "0.85" in blocked_trigger.resolution_outcome
        assert "Performance:" in blocked_trigger.resolution_outcome

    @pytest.mark.asyncio
    async def test_blocked_trigger_resolution_outcome_includes_confidence_boost(self, db_session: Session):
        """Test blocked trigger resolution_outcome includes confidence boost"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_resolve_4",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.8,
            supervisor_feedback="Good",
            errors_count=1,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task1"],
            capability_gaps_remaining=[]
        )

        await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(blocked_trigger)
        assert "Confidence boost:" in blocked_trigger.resolution_outcome

    @pytest.mark.asyncio
    async def test_blocked_trigger_resolution_outcome_includes_promoted_status(self, db_session: Session):
        """Test blocked trigger resolution_outcome includes promoted status"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_resolve_5",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.45,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.45,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.8,
            supervisor_feedback="Good",
            errors_count=1,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task1"],
            capability_gaps_remaining=[]
        )

        await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(blocked_trigger)
        assert "Promoted to INTERN:" in blocked_trigger.resolution_outcome
        assert "True" in blocked_trigger.resolution_outcome

    @pytest.mark.asyncio
    async def test_proposal_status_updated_to_executed(self, db_session: Session):
        """Test proposal status updated to EXECUTED"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_executed_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.8,
            supervisor_feedback="Good",
            errors_count=1,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task1"],
            capability_gaps_remaining=[]
        )

        await service.complete_training_session(session.id, outcome)

        # Assert
        db_session.refresh(proposal)
        assert proposal.status == ProposalStatus.EXECUTED.value
        assert proposal.completed_at is not None


class TestCompletionErrorHandling:
    """Test training completion error handling"""

    @pytest.mark.asyncio
    async def test_value_error_for_nonexistent_session(self, db_session: Session):
        """Test ValueError raised for non-existent session"""
        # Arrange
        service = StudentTrainingService(db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="Training session .* not found"):
            outcome = TrainingOutcome(
                performance_score=0.8,
                supervisor_feedback="Good",
                errors_count=1,
                tasks_completed=9,
                total_tasks=10,
                capabilities_developed=["task1"],
                capability_gaps_remaining=[]
            )
            await service.complete_training_session("nonexistent_session_id", outcome)

    @pytest.mark.asyncio
    async def test_value_error_for_nonexistent_agent(self, db_session: Session):
        """Test ValueError raised for non-existent agent"""
        # Arrange
        service = StudentTrainingService(db_session)

        # Create session without agent
        session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal",
            agent_id="nonexistent_agent",
            agent_name="Ghost Agent",
            supervisor_id="test_supervisor",
            status="scheduled",
            total_tasks=5,
            started_at=datetime.now()
        )
        db_session.add(session)
        db_session.commit()

        # Act & Assert
        with pytest.raises(ValueError, match="Agent .* not found"):
            outcome = TrainingOutcome(
                performance_score=0.8,
                supervisor_feedback="Good",
                errors_count=1,
                tasks_completed=9,
                total_tasks=10,
                capabilities_developed=["task1"],
                capability_gaps_remaining=[]
            )
            await service.complete_training_session(session.id, outcome)

    @pytest.mark.asyncio
    async def test_return_dict_includes_all_expected_fields(self, db_session: Session):
        """Test return dict includes all expected fields"""
        # Arrange
        agent = AgentRegistry(
            id="student_agent_return_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        blocked_trigger = BlockedTriggerContext(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="agent_message",
            trigger_context={"data": "test"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        proposal = await service.create_training_proposal(blocked_trigger)
        session = await service.approve_training(proposal.id, "test_user", None)

        # Act
        outcome = TrainingOutcome(
            performance_score=0.75,
            supervisor_feedback="Good",
            errors_count=2,
            tasks_completed=8,
            total_tasks=10,
            capabilities_developed=["task1", "task2"],
            capability_gaps_remaining=[]
        )

        result = await service.complete_training_session(session.id, outcome)

        # Assert
        expected_keys = [
            "session_id", "agent_id", "performance_score", "confidence_boost",
            "old_confidence", "new_confidence", "promoted_to_intern",
            "new_status", "capabilities_developed"
        ]
        for key in expected_keys:
            assert key in result
        assert result["session_id"] == session.id
        assert result["agent_id"] == agent.id
        assert result["performance_score"] == 0.75


class TestDurationEstimationFactors:
    """Test AI-based duration estimation factors"""

    @pytest.mark.asyncio
    async def test_confidence_factor_low_confidence_adds_hours(self, db_session: Session):
        """Test confidence factor: Lower confidence (0.0) adds ~20 hours to base"""
        # Arrange
        agent = AgentRegistry(
            id="student_est_conf_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.0,  # Lowest confidence
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        # Confidence factor: (0.5 - 0.0) * 50 = 25 hours
        assert "0.00" in estimate.reasoning
        assert "confidence" in estimate.reasoning.lower()

    @pytest.mark.asyncio
    async def test_confidence_factor_higher_confidence_adds_fewer_hours(self, db_session: Session):
        """Test confidence factor: Higher confidence (0.4) adds fewer hours"""
        # Arrange
        agent = AgentRegistry(
            id="student_est_conf_2",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,  # Close to threshold
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        # Confidence factor: (0.5 - 0.4) * 50 = 5 hours
        assert "0.40" in estimate.reasoning
        assert "confidence" in estimate.reasoning.lower()

    @pytest.mark.asyncio
    async def test_capability_gaps_factor_each_gap_adds_hours(self, db_session: Session):
        """Test capability gaps factor: Each gap adds ~4 hours"""
        # Arrange
        agent = AgentRegistry(
            id="student_est_gaps_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1", "gap2", "gap3", "gap4", "gap5"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        # 5 gaps * 4 hours = 20 hours from gaps factor
        assert "5 identified" in estimate.reasoning
        assert "Capability Gaps:" in estimate.reasoning

    @pytest.mark.asyncio
    async def test_historical_factor_similar_agents_average_duration(self, db_session: Session):
        """Test historical factor: Similar agents' average duration used"""
        # Arrange - Create similar agent with completed training
        similar_agent = AgentRegistry(
            id="similar_est_1",
            name="Similar Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(similar_agent)

        training_session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal",
            agent_id=similar_agent.id,
            agent_name=similar_agent.name,
            supervisor_id="test_supervisor",
            status="completed",
            started_at=datetime.now() - timedelta(days=5),
            completed_at=datetime.now() - timedelta(days=1),
            duration_seconds=180000  # 50 hours
        )
        db_session.add(training_session)
        db_session.commit()

        agent = AgentRegistry(
            id="student_est_hist_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        assert len(estimate.similar_agents) == 1
        assert "1 similar" in estimate.reasoning
        assert "Historical Data" in estimate.reasoning

    @pytest.mark.asyncio
    async def test_learning_rate_factor_fast_learner_reduces_duration(self, db_session: Session):
        """Test learning rate factor: Fast learner (>1.0) reduces duration"""
        # Arrange - Agent with good training history (fast learner)
        agent = AgentRegistry(
            id="student_est_rate_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)

        # Create completed session with high performance
        session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal",
            agent_id=agent.id,
            agent_name=agent.name,
            supervisor_id="test_supervisor",
            status="completed",
            performance_score=0.9,  # Excellent performance
            started_at=datetime.now() - timedelta(days=2),
            completed_at=datetime.now() - timedelta(days=1),
            duration_seconds=3600
        )
        db_session.add(session)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        assert "Fast learner" in estimate.reasoning
        # Learning rate should be > 1.0 for fast learner
        assert "Learning Rate:" in estimate.reasoning

    @pytest.mark.asyncio
    async def test_learning_rate_factor_slow_learner_increases_duration(self, db_session: Session):
        """Test learning rate factor: Slow learner (<1.0) increases duration"""
        # Arrange - Agent with poor training history (slow learner)
        agent = AgentRegistry(
            id="student_est_rate_2",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)

        # Create completed session with low performance
        session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal",
            agent_id=agent.id,
            agent_name=agent.name,
            supervisor_id="test_supervisor",
            status="completed",
            performance_score=0.4,  # Poor performance
            started_at=datetime.now() - timedelta(days=2),
            completed_at=datetime.now() - timedelta(days=1),
            duration_seconds=3600
        )
        db_session.add(session)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        # Should indicate slow learner or average pace
        reasoning_lower = estimate.reasoning.lower()
        assert "learning rate:" in reasoning_lower

    @pytest.mark.asyncio
    async def test_min_max_bounds_calculated(self, db_session: Session):
        """Test min/max bounds: min_hours = 70% of estimate, max_hours = 150%"""
        # Arrange
        agent = AgentRegistry(
            id="student_est_bounds_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1", "gap2"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        assert estimate.min_hours == round(estimate.estimated_hours * 0.7, 1)
        assert estimate.max_hours == round(estimate.estimated_hours * 1.5, 1)
        assert estimate.min_hours <= estimate.estimated_hours <= estimate.max_hours

    @pytest.mark.asyncio
    async def test_confidence_in_estimate_increases_with_more_similar_agents(self, db_session: Session):
        """Test confidence in estimate increases with more similar agents (0.5 + n*0.05)"""
        # Arrange - Create 3 similar agents
        for i in range(3):
            similar_agent = AgentRegistry(
                id=f"similar_est_{i}",
                name=f"Similar Agent {i}",
                category="testing",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6,
            )
            db_session.add(similar_agent)

            training_session = TrainingSession(
                id=str(uuid.uuid4()),
                proposal_id=f"test_proposal_{i}",
                agent_id=similar_agent.id,
                agent_name=similar_agent.name,
                supervisor_id="test_supervisor",
                status="completed",
                started_at=datetime.now() - timedelta(days=5),
                completed_at=datetime.now() - timedelta(days=1),
                duration_seconds=144000  # 40 hours
            )
            db_session.add(training_session)

        db_session.commit()

        agent = AgentRegistry(
            id="student_est_conf_3",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        # Confidence: 0.5 + 3 * 0.05 = 0.65
        assert estimate.confidence >= 0.5
        assert len(estimate.similar_agents) == 3


class TestDurationEstimationEdgeCases:
    """Test edge cases in duration estimation"""

    @pytest.mark.asyncio
    async def test_new_agent_with_no_similar_agents_uses_base_hours(self, db_session: Session):
        """Test new agent with no similar agents uses base_hours"""
        # Arrange
        agent = AgentRegistry(
            id="new_student_est_1",
            name="New Student Agent",
            category="BrandNewCategory",  # No similar agents
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.2,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        assert len(estimate.similar_agents) == 0
        assert "0 similar" in estimate.reasoning
        # Should still provide estimate
        assert estimate.estimated_hours > 0

    @pytest.mark.asyncio
    async def test_agent_not_found_raises_value_error(self, db_session: Session):
        """Test agent not found raises ValueError"""
        # Arrange
        service = StudentTrainingService(db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="Agent .* not found"):
            await service.estimate_training_duration(
                agent_id="nonexistent_agent",
                capability_gaps=["gap1"],
                target_maturity=AgentStatus.INTERN.value
            )

    @pytest.mark.asyncio
    async def test_invalid_target_maturity_handled_gracefully(self, db_session: Session):
        """Test invalid target_maturity handled gracefully"""
        # Arrange
        agent = AgentRegistry(
            id="student_est_invalid_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act - Use invalid maturity (should still work)
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity="INVALID_STATUS"
        )

        # Assert - Should return estimate regardless
        assert estimate.estimated_hours > 0
        assert estimate.reasoning is not None

    @pytest.mark.asyncio
    async def test_reasoning_includes_all_4_factors(self, db_session: Session):
        """Test reasoning string includes all 4 factors (confidence, gaps, historical, learning)"""
        # Arrange - Create similar agent for historical factor
        similar_agent = AgentRegistry(
            id="similar_est_reason_1",
            name="Similar Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(similar_agent)

        training_session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal",
            agent_id=similar_agent.id,
            agent_name=similar_agent.name,
            supervisor_id="test_supervisor",
            status="completed",
            started_at=datetime.now() - timedelta(days=5),
            completed_at=datetime.now() - timedelta(days=1),
            duration_seconds=144000
        )
        db_session.add(training_session)
        db_session.commit()

        agent = AgentRegistry(
            id="student_est_reason_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1", "gap2"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        reasoning_lower = estimate.reasoning.lower()
        assert "confidence" in reasoning_lower
        assert "capability" in reasoning_lower
        assert "historical" in reasoning_lower or "similar" in reasoning_lower
        assert "learning" in reasoning_lower

    @pytest.mark.asyncio
    async def test_similar_agents_list_limited_to_5_max(self, db_session: Session):
        """Test similar agents list limited to 5 agents max"""
        # Arrange - Create 7 similar agents
        for i in range(7):
            similar_agent = AgentRegistry(
                id=f"similar_est_limit_{i}",
                name=f"Similar Agent {i}",
                category="testing",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6,
            )
            db_session.add(similar_agent)

            training_session = TrainingSession(
                id=str(uuid.uuid4()),
                proposal_id=f"test_proposal_{i}",
                agent_id=similar_agent.id,
                agent_name=similar_agent.name,
                supervisor_id="test_supervisor",
                status="completed",
                started_at=datetime.now() - timedelta(days=5),
                completed_at=datetime.now() - timedelta(days=1),
                duration_seconds=144000
            )
            db_session.add(training_session)

        db_session.commit()

        agent = AgentRegistry(
            id="student_est_limit_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        assert len(estimate.similar_agents) <= 5  # Limited to 5


class TestSimilarAgentsHistory:
    """Test similar agents historical data retrieval"""

    @pytest.mark.asyncio
    async def test_similar_agents_filtered_by_category_and_target_maturity(self, db_session: Session):
        """Test similar agents filtered by category and target_maturity"""
        # Arrange - Create agents in different categories WITH completed sessions
        finance_agent = AgentRegistry(
            id="finance_similar_1",
            name="Finance Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.7,
        )
        db_session.add(finance_agent)

        finance_session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal",
            agent_id=finance_agent.id,
            agent_name=finance_agent.name,
            supervisor_id="test_supervisor",
            status="completed",
            duration_seconds=3600 * 20
        )
        db_session.add(finance_session)

        testing_agent = AgentRegistry(
            id="testing_similar_1",
            name="Testing Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.7,
        )
        db_session.add(testing_agent)

        testing_session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal2",
            agent_id=testing_agent.id,
            agent_name=testing_agent.name,
            supervisor_id="test_supervisor",
            status="completed",
            duration_seconds=3600 * 20
        )
        db_session.add(testing_session)

        student_agent = AgentRegistry(
            id="student_similar_1",
            name="Student Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,  # Not INTERN
            confidence_score=0.7,
        )
        db_session.add(student_agent)
        db_session.commit()

        agent = AgentRegistry(
            id="target_similar_1",
            name="Target Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert - Should only match testing_agent (same category + INTERN status + completed session)
        assert len(estimate.similar_agents) == 1
        assert estimate.similar_agents[0]["agent_id"] == "testing_similar_1"

    @pytest.mark.asyncio
    async def test_similar_agents_filtered_by_confidence_score(self, db_session: Session):
        """Test similar agents filtered by confidence_score >= 0.5"""
        # Arrange - Create agents with different confidence scores AND completed sessions
        high_conf_agent = AgentRegistry(
            id="high_conf_similar_1",
            name="High Confidence Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.8,  # >= 0.5
        )
        db_session.add(high_conf_agent)

        high_conf_session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal_high",
            agent_id=high_conf_agent.id,
            agent_name=high_conf_agent.name,
            supervisor_id="test_supervisor",
            status="completed",
            duration_seconds=3600 * 20
        )
        db_session.add(high_conf_session)

        low_conf_agent = AgentRegistry(
            id="low_conf_similar_1",
            name="Low Confidence Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.4,  # < 0.5
        )
        db_session.add(low_conf_agent)

        low_conf_session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id="test_proposal_low",
            agent_id=low_conf_agent.id,
            agent_name=low_conf_agent.name,
            supervisor_id="test_supervisor",
            status="completed",
            duration_seconds=3600 * 20
        )
        db_session.add(low_conf_session)
        db_session.commit()

        agent = AgentRegistry(
            id="target_similar_2",
            name="Target Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert - Should only match high_conf_agent (confidence >= 0.5)
        assert len(estimate.similar_agents) == 1
        assert estimate.similar_agents[0]["agent_id"] == "high_conf_similar_1"

    @pytest.mark.asyncio
    async def test_training_duration_summed_from_all_completed_sessions(self, db_session: Session):
        """Test training duration summed from all completed sessions"""
        # Arrange - Create agent with multiple completed sessions
        similar_agent = AgentRegistry(
            id="similar_sum_1",
            name="Similar Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(similar_agent)

        # Create 3 completed sessions
        for i in range(3):
            training_session = TrainingSession(
                id=str(uuid.uuid4()),
                proposal_id=f"test_proposal_{i}",
                agent_id=similar_agent.id,
                agent_name=similar_agent.name,
                supervisor_id="test_supervisor",
                status="completed",
                started_at=datetime.now() - timedelta(days=5),
                completed_at=datetime.now() - timedelta(days=1),
                duration_seconds=3600 * 10  # 10 hours each
            )
            db_session.add(training_session)

        db_session.commit()

        agent = AgentRegistry(
            id="target_similar_3",
            name="Target Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert - Should sum to 30 hours (3 * 10)
        assert len(estimate.similar_agents) == 1
        assert estimate.similar_agents[0]["duration_hours"] == 30.0

    @pytest.mark.asyncio
    async def test_session_count_included_in_similar_agents_data(self, db_session: Session):
        """Test session count included in similar_agents data"""
        # Arrange
        similar_agent = AgentRegistry(
            id="similar_count_1",
            name="Similar Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
        )
        db_session.add(similar_agent)

        # Create 2 completed sessions
        for i in range(2):
            training_session = TrainingSession(
                id=str(uuid.uuid4()),
                proposal_id=f"test_proposal_{i}",
                agent_id=similar_agent.id,
                agent_name=similar_agent.name,
                supervisor_id="test_supervisor",
                status="completed",
                started_at=datetime.now() - timedelta(days=5),
                completed_at=datetime.now() - timedelta(days=1),
                duration_seconds=3600 * 15  # 15 hours each
            )
            db_session.add(training_session)

        db_session.commit()

        agent = AgentRegistry(
            id="target_similar_4",
            name="Target Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3,
        )
        db_session.add(agent)
        db_session.commit()

        service = StudentTrainingService(db_session)

        # Act
        estimate = await service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["gap1"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Assert
        assert len(estimate.similar_agents) == 1
        assert estimate.similar_agents[0]["session_count"] == 2
        assert estimate.similar_agents[0]["duration_hours"] == 30.0
