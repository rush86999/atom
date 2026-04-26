"""
Test suite for Student Training Service

Tests student training service including:
- Training proposals from blocked triggers
- Training session lifecycle
- Training duration estimation (AI-based)
- Agent maturity progression (STUDENT → INTERN)
- Training history tracking
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.student_training_service import (
    StudentTrainingService,
    TrainingDurationEstimate,
    TrainingOutcome
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    AgentProposal,
    BlockedTriggerContext,
    ProposalStatus,
    ProposalType,
    TrainingSession,
    TriggerSource
)


class TestTrainingDurationEstimate:
    """Test TrainingDurationEstimate dataclass"""

    def test_training_duration_estimate_creation(self):
        """TrainingDurationEstimate can be created with valid parameters."""
        estimate = TrainingDurationEstimate(
            estimated_hours=40.0,
            confidence=0.85,
            reasoning="Based on similar agents",
            similar_agents=[],
            min_hours=28.0,
            max_hours=60.0
        )
        assert estimate.estimated_hours == 40.0
        assert estimate.confidence == 0.85
        assert estimate.min_hours == 28.0
        assert estimate.max_hours == 60.0

    def test_training_duration_estimate_fields(self):
        """TrainingDurationEstimate has all required fields."""
        similar_agents = [
            {"agent_id": "agent-1", "duration_hours": 35.0}
        ]
        estimate = TrainingDurationEstimate(
            estimated_hours=45.0,
            confidence=0.75,
            reasoning="Test reasoning",
            similar_agents=similar_agents,
            min_hours=31.5,
            max_hours=67.5
        )
        assert len(estimate.similar_agents) == 1
        assert estimate.reasoning == "Test reasoning"


class TestTrainingOutcome:
    """Test TrainingOutcome dataclass"""

    def test_training_outcome_creation(self):
        """TrainingOutcome can be created with valid parameters."""
        outcome = TrainingOutcome(
            performance_score=0.85,
            supervisor_feedback="Excellent progress",
            errors_count=2,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task_execution", "context_understanding"],
            capability_gaps_remaining=["advanced_planning"]
        )
        assert outcome.performance_score == 0.85
        assert outcome.tasks_completed == 9
        assert outcome.total_tasks == 10
        assert len(outcome.capabilities_developed) == 2
        assert len(outcome.capability_gaps_remaining) == 1

    def test_training_outcome_performance_calculation(self):
        """TrainingOutcome performance score is within valid range."""
        outcome = TrainingOutcome(
            performance_score=0.65,
            supervisor_feedback="Good performance",
            errors_count=5,
            tasks_completed=7,
            total_tasks=10,
            capabilities_developed=[],
            capability_gaps_remaining=[]
        )
        assert 0.0 <= outcome.performance_score <= 1.0
        assert outcome.performance_score == 0.65


class TestStudentTrainingServiceInit:
    """Test StudentTrainingService initialization"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_service_initialization(self, mock_db):
        """StudentTrainingService initializes with database session."""
        service = StudentTrainingService(mock_db)
        assert service.db == mock_db


class TestTrainingProposalCreation:
    """Test training proposal creation from blocked triggers"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def mock_agent(self):
        """Mock agent registry."""
        agent = AgentRegistry(
            id="agent-001",
            name="Test Agent",
            category="Finance",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        return agent

    @pytest.fixture
    def mock_blocked_trigger(self):
        """Mock blocked trigger context."""
        trigger = BlockedTriggerContext(
            id="trigger-001",
            agent_id="agent-001",
            trigger_type="workflow_trigger",
            trigger_context={"category": "Finance"},
            source=TriggerSource.MANUAL.value,
            resolved=False
        )
        return trigger

    @pytest.mark.asyncio
    async def test_create_training_proposal_success(self, mock_db, mock_agent, mock_blocked_trigger):
        """Training proposal created successfully from blocked trigger."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        service = StudentTrainingService(mock_db)

        with patch.object(service, '_identify_capability_gaps', new_callable=AsyncMock) as mock_gaps:
            mock_gaps.return_value = ["task_execution", "decision_making"]

            with patch.object(service, '_generate_learning_objectives', new_callable=AsyncMock) as mock_objectives:
                mock_objectives.return_value = ["Learn task execution", "Understand decision making"]

                with patch.object(service, 'estimate_training_duration', new_callable=AsyncMock) as mock_estimate:
                    mock_estimate.return_value = TrainingDurationEstimate(
                        estimated_hours=40.0,
                        confidence=0.8,
                        reasoning="Based on similar agents",
                        similar_agents=[],
                        min_hours=28.0,
                        max_hours=60.0
                    )

                    proposal = await service.create_training_proposal(mock_blocked_trigger)

                    assert proposal.agent_id == "agent-001"
                    assert proposal.proposal_type == ProposalType.TRAINING.value
                    assert proposal.status == ProposalStatus.PROPOSED.value
                    assert "Training Proposal:" in proposal.title
                    assert len(proposal.capability_gaps) == 2
                    mock_db.add.assert_called()
                    mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_training_proposal_agent_not_found(self, mock_db, mock_blocked_trigger):
        """Training proposal creation fails when agent not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = StudentTrainingService(mock_db)

        with pytest.raises(ValueError, match="Agent .* not found"):
            await service.create_training_proposal(mock_blocked_trigger)


class TestTrainingSessionLifecycle:
    """Test training session lifecycle management"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def mock_proposal(self):
        """Mock training proposal."""
        proposal = AgentProposal(
            id="proposal-001",
            agent_id="agent-001",
            agent_name="Test Agent",
            proposal_type=ProposalType.TRAINING.value,
            title="Training Proposal",
            description="Test training",
            estimated_duration_hours=40.0,
            duration_estimation_confidence=0.8,
            status=ProposalStatus.PROPOSED.value,
            learning_objectives=["Learn task execution"],
            capability_gaps=["task_execution"]
        )
        return proposal

    @pytest.mark.asyncio
    async def test_approve_training_success(self, mock_db, mock_proposal):
        """Training proposal approved and session created successfully."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        service = StudentTrainingService(mock_db)

        session = await service.approve_training(
            proposal_id="proposal-001",
            user_id="user-001"
        )

        assert session.agent_id == "agent-001"
        assert session.status == "scheduled"
        assert session.supervisor_id == "user-001"
        assert mock_proposal.status == ProposalStatus.APPROVED.value
        assert mock_proposal.approved_by == "user-001"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_approve_training_with_modifications(self, mock_db, mock_proposal):
        """Training approved with duration modifications."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        service = StudentTrainingService(mock_db)

        modifications = {
            "duration_override_hours": 50.0,
            "hours_per_day_limit": 4.0
        }

        session = await service.approve_training(
            proposal_id="proposal-001",
            user_id="user-001",
            modifications=modifications
        )

        assert mock_proposal.user_override_duration_hours == 50.0
        assert mock_proposal.hours_per_day_limit == 4.0

    @pytest.mark.asyncio
    async def test_approve_training_proposal_not_found(self, mock_db):
        """Training approval fails when proposal not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = StudentTrainingService(mock_db)

        with pytest.raises(ValueError, match="Proposal .* not found"):
            await service.approve_training(
                proposal_id="invalid-proposal",
                user_id="user-001"
            )

    @pytest.mark.asyncio
    async def test_approve_training_invalid_status(self, mock_db, mock_proposal):
        """Training approval fails when proposal not in PROPOSED status."""
        mock_proposal.status = ProposalStatus.APPROVED.value
        mock_db.query.return_value.filter.return_value.first.return_value = mock_proposal

        service = StudentTrainingService(mock_db)

        with pytest.raises(ValueError, match="Proposal must be in PROPOSED status"):
            await service.approve_training(
                proposal_id="proposal-001",
                user_id="user-001"
            )


class TestTrainingCompletion:
    """Test training session completion and agent maturity progression"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def mock_session(self):
        """Mock training session."""
        session = TrainingSession(
            id="session-001",
            proposal_id="proposal-001",
            agent_id="agent-001",
            agent_name="Test Agent",
            status="in_progress",
            supervisor_id="user-001",
            started_at=datetime.now(),
            total_tasks=10
        )
        return session

    @pytest.fixture
    def mock_agent(self):
        """Mock agent."""
        agent = AgentRegistry(
            id="agent-001",
            name="Test Agent",
            category="Finance",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.35
        )
        return agent

    @pytest.fixture
    def mock_outcome(self):
        """Mock training outcome."""
        return TrainingOutcome(
            performance_score=0.85,
            supervisor_feedback="Excellent progress",
            errors_count=2,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["task_execution", "decision_making"],
            capability_gaps_remaining=[]
        )

    @pytest.mark.asyncio
    async def test_complete_training_promotes_to_intern(self, mock_db, mock_session, mock_agent, mock_outcome):
        """Agent promoted to INTERN after successful training completion."""
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_session, mock_agent, None, None]
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        service = StudentTrainingService(mock_db)

        result = await service.complete_training_session(
            session_id="session-001",
            outcome=mock_outcome
        )

        assert result["promoted_to_intern"] is True
        assert mock_agent.status == AgentStatus.INTERN.value
        assert mock_agent.confidence_score >= 0.5
        assert mock_session.status == "completed"
        assert mock_session.performance_score == 0.85

    @pytest.mark.asyncio
    async def test_complete_training_confidence_boost(self, mock_db, mock_session, mock_agent, mock_outcome):
        """Agent confidence score boosted after training completion."""
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_session, mock_agent, None, None]
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        service = StudentTrainingService(mock_db)

        old_confidence = mock_agent.confidence_score
        result = await service.complete_training_session(
            session_id="session-001",
            outcome=mock_outcome
        )

        assert result["confidence_boost"] > 0
        assert result["new_confidence"] > old_confidence
        assert mock_agent.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_complete_training_session_not_found(self, mock_db):
        """Training completion fails when session not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = StudentTrainingService(mock_db)

        mock_outcome = TrainingOutcome(
            performance_score=0.8,
            supervisor_feedback="Good",
            errors_count=1,
            tasks_completed=8,
            total_tasks=10,
            capabilities_developed=[],
            capability_gaps_remaining=[]
        )

        with pytest.raises(ValueError, match="Training session .* not found"):
            await service.complete_training_session(
                session_id="invalid-session",
                outcome=mock_outcome
            )


class TestTrainingDurationEstimation:
    """Test AI-based training duration estimation"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def mock_agent(self):
        """Mock agent."""
        agent = AgentRegistry(
            id="agent-001",
            name="Test Agent",
            category="Finance",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        return agent

    @pytest.mark.asyncio
    async def test_estimate_training_duration_success(self, mock_db, mock_agent):
        """Training duration estimated successfully based on multiple factors."""
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_agent, []]
        mock_db.query.return_value.filter.side_effect = [
            Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[])))),
            Mock(filter=Mock(return_value=Mock(all=Mock(return_value=[]))))
        ]

        service = StudentTrainingService(mock_db)

        with patch.object(service, '_get_similar_agents_training_history', new_callable=AsyncMock) as mock_history:
            mock_history.return_value = [
                {"agent_id": "agent-002", "duration_hours": 38.0, "session_count": 1}
            ]

            with patch.object(service, '_calculate_learning_rate', new_callable=AsyncMock) as mock_learning:
                mock_learning.return_value = 1.0

                estimate = await service.estimate_training_duration(
                    agent_id="agent-001",
                    capability_gaps=["task_execution", "decision_making"],
                    target_maturity=AgentStatus.INTERN.value
                )

                assert estimate.estimated_hours > 0
                assert estimate.confidence > 0
                assert estimate.min_hours < estimate.estimated_hours < estimate.max_hours
                assert len(estimate.reasoning) > 0

    @pytest.mark.asyncio
    async def test_estimate_training_duration_agent_not_found(self, mock_db):
        """Duration estimation fails when agent not found."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = StudentTrainingService(mock_db)

        with pytest.raises(ValueError, match="Agent .* not found"):
            await service.estimate_training_duration(
                agent_id="invalid-agent",
                capability_gaps=[],
                target_maturity=AgentStatus.INTERN.value
            )


class TestTrainingHistory:
    """Test training history retrieval"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.mark.asyncio
    async def test_get_training_history_success(self, mock_db):
        """Training history retrieved successfully for agent."""
        mock_session = TrainingSession(
            id="session-001",
            proposal_id="proposal-001",
            agent_id="agent-001",
            agent_name="Test Agent",
            status="completed",
            supervisor_id="user-001",
            started_at=datetime.now(),
            completed_at=datetime.now() + timedelta(hours=40),
            duration_seconds=144000,
            performance_score=0.85,
            confidence_boost=0.15,
            promoted_to_intern=True,
            total_tasks=10,
            tasks_completed=9
        )

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_session]
        mock_db.query.return_value.filter.return_value.first.return_value = Mock(
            title="Training Proposal",
            capability_gaps=["task_execution"]
        )

        service = StudentTrainingService(mock_db)

        history = await service.get_training_history(agent_id="agent-001", limit=50)

        assert len(history) == 1
        assert history[0]["session_id"] == "session-001"
        assert history[0]["status"] == "completed"
        assert history[0]["performance_score"] == 0.85
        assert history[0]["promoted_to_intern"] is True

    @pytest.mark.asyncio
    async def test_get_training_history_empty(self, mock_db):
        """Empty training history returned for agent with no sessions."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        service = StudentTrainingService(mock_db)

        history = await service.get_training_history(agent_id="agent-001")

        assert len(history) == 0
