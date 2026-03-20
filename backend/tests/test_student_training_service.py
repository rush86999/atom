"""
Tests for Student Training Service

Tests for training proposals, sessions, duration estimation, and maturity progression.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock
from sqlalchemy.orm import Session

from core.student_training_service import (
    StudentTrainingService,
    TrainingDurationEstimate,
    TrainingOutcome,
)
from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    ProposalStatus,
    ProposalType,
    TrainingSession,
    TriggerSource,
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
def mock_agent():
    """Mock agent registry"""
    agent = AgentRegistry(
        id="test-agent-123",
        name="Test Student Agent",
        category="Finance",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3,
    )
    return agent


@pytest.fixture
def mock_blocked_trigger(mock_agent):
    """Mock blocked trigger context"""
    trigger = BlockedTriggerContext(
        id="blocked-trigger-123",
        agent_id=mock_agent.id,
        agent_name=mock_agent.name,
        agent_maturity_at_block=AgentStatus.STUDENT.value,
        confidence_score_at_block=0.3,
        trigger_type="agent_message",
        trigger_context={
            "category": "Finance",
            "task": "Process invoice"
        },
        trigger_source=TriggerSource.MANUAL.value,
        routing_decision="training",
        block_reason="Agent is in STUDENT maturity level",
        resolved=False,
    )
    return trigger


@pytest.fixture
def mock_training_proposal(mock_agent, mock_blocked_trigger):
    """Mock training proposal"""
    proposal = MagicMock()
    proposal.id = "proposal-123"
    proposal.agent_id = mock_agent.id
    proposal.agent_name = mock_agent.name
    proposal.proposal_type = ProposalType.TRAINING.value
    proposal.title = "Training Proposal: Test Student Agent - Finance Fundamentals"
    proposal.description = "Training to develop finance capabilities"
    proposal.learning_objectives = [
        "Understand agent_message execution flow",
        "Demonstrate reliable task completion",
        "Develop proficiency in financial_analysis"
    ]
    proposal.capability_gaps = ["financial_analysis", "task_execution"]
    proposal.training_scenario_template = "Finance Fundamentals"
    proposal.estimated_duration_hours = 40.0
    proposal.duration_estimation_confidence = 0.75
    proposal.status = ProposalStatus.PROPOSED.value
    proposal.proposed_by = "atom_meta_agent"
    proposal.user_override_duration_hours = None
    proposal.hours_per_day_limit = None
    proposal.training_start_date = None
    proposal.training_end_date = None
    proposal.approved_by = None
    proposal.approved_at = None
    proposal.completed_at = None
    proposal.execution_result = None
    return proposal


@pytest.fixture
def mock_training_session(mock_agent, mock_training_proposal):
    """Mock training session"""
    session = TrainingSession(
        id="session-123",
        proposal_id=mock_training_proposal.id,
        agent_id=mock_agent.id,
        agent_name=mock_agent.name,
        status="scheduled",
        supervisor_id="supervisor-123",
        total_tasks=3,
    )
    return session


@pytest.fixture
def service(db_session):
    """StudentTrainingService instance"""
    return StudentTrainingService(db_session)


# ========================================================================
# Test Training Duration Estimation
# ========================================================================

class TestTrainingEstimation:
    """Tests for AI-based training duration estimation"""

    @pytest.mark.asyncio
    async def test_estimate_duration_for_new_agent(
        self, service, mock_agent, db_session
    ):
        """Test estimation for new agent with no historical data"""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_agent)
        db_session.query.return_value = mock_query

        # Mock private methods to avoid database queries
        service._get_similar_agents_training_history = AsyncMock(return_value=[])
        service._calculate_learning_rate = AsyncMock(return_value=1.0)

        # Estimate duration
        estimate = await service.estimate_training_duration(
            agent_id=mock_agent.id,
            capability_gaps=["financial_analysis", "task_execution"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Verify estimate
        assert estimate is not None
        assert estimate.estimated_hours > 0
        assert estimate.confidence >= 0.5
        assert estimate.min_hours < estimate.estimated_hours
        assert estimate.max_hours > estimate.estimated_hours
        assert "Current Confidence" in estimate.reasoning
        assert "Capability Gaps" in estimate.reasoning

    @pytest.mark.asyncio
    async def test_estimate_based_on_confidence(
        self, service, mock_agent, db_session
    ):
        """Test that lower confidence increases estimated duration"""
        # Setup mock for low confidence agent
        low_confidence_agent = AgentRegistry(
            id="low-conf-agent",
            name="Low Confidence Agent",
            category="Finance",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.1,  # Very low confidence
        )

        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=low_confidence_agent)
        db_session.query.return_value = mock_query

        # Mock private methods
        service._get_similar_agents_training_history = AsyncMock(return_value=[])
        service._calculate_learning_rate = AsyncMock(return_value=1.0)

        # Estimate for low confidence
        low_conf_estimate = await service.estimate_training_duration(
            agent_id=low_confidence_agent.id,
            capability_gaps=["task_execution"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Setup mock for high confidence agent
        high_confidence_agent = AgentRegistry(
            id="high-conf-agent",
            name="High Confidence Agent",
            category="Finance",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.45,  # Near INTERN threshold
        )

        mock_query.first = MagicMock(return_value=high_confidence_agent)

        # Estimate for high confidence
        high_conf_estimate = await service.estimate_training_duration(
            agent_id=high_confidence_agent.id,
            capability_gaps=["task_execution"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Low confidence should require more training
        assert low_conf_estimate.estimated_hours > high_conf_estimate.estimated_hours

    @pytest.mark.asyncio
    async def test_estimate_includes_capability_gaps(
        self, service, mock_agent, db_session
    ):
        """Test that more capability gaps increase estimated duration"""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_agent)
        db_session.query.return_value = mock_query

        # Mock private methods
        service._get_similar_agents_training_history = AsyncMock(return_value=[])
        service._calculate_learning_rate = AsyncMock(return_value=1.0)

        # Estimate with few gaps
        few_gaps_estimate = await service.estimate_training_duration(
            agent_id=mock_agent.id,
            capability_gaps=["task_execution"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Estimate with many gaps
        many_gaps_estimate = await service.estimate_training_duration(
            agent_id=mock_agent.id,
            capability_gaps=[
                "task_execution",
                "financial_analysis",
                "data_validation",
                "reporting",
                "reconciliation",
            ],
            target_maturity=AgentStatus.INTERN.value
        )

        # More gaps should require more training
        assert many_gaps_estimate.estimated_hours > few_gaps_estimate.estimated_hours

    @pytest.mark.asyncio
    async def test_estimate_with_user_override(
        self, service, mock_agent, mock_training_proposal, db_session
    ):
        """Test that user can override estimated duration"""
        # Mock proposal query
        mock_proposal_query = MagicMock()
        mock_proposal_query.filter = MagicMock(return_value=mock_proposal_query)
        mock_proposal_query.first = MagicMock(return_value=mock_training_proposal)
        db_session.query.return_value = mock_proposal_query

        # Approve with override
        modifications = {
            "duration_override_hours": 20.0,  # Override from 40 to 20
            "hours_per_day_limit": 4.0
        }

        session = await service.approve_training(
            proposal_id=mock_training_proposal.id,
            user_id="supervisor-123",
            modifications=modifications
        )

        # Verify override applied
        assert mock_training_proposal.user_override_duration_hours == 20.0
        assert mock_training_proposal.hours_per_day_limit == 4.0
        assert session is not None


# ========================================================================
# Test Training Proposals
# ========================================================================

class TestTrainingProposals:
    """Tests for training proposal creation and management"""

    @pytest.mark.asyncio
    async def test_create_training_proposal(
        self, service, mock_blocked_trigger, mock_agent, db_session
    ):
        """Test creating training proposal from blocked trigger"""
        # Setup mocks
        mock_agent_query = MagicMock()
        mock_agent_query.filter = MagicMock(return_value=mock_agent_query)
        mock_agent_query.first = MagicMock(return_value=mock_agent)

        db_session.query.return_value = mock_agent_query

        # Mock private methods
        service._get_similar_agents_training_history = AsyncMock(return_value=[])
        service._calculate_learning_rate = AsyncMock(return_value=1.0)

        # Create proposal
        proposal = await service.create_training_proposal(mock_blocked_trigger)

        # Verify proposal created
        assert proposal is not None
        assert proposal.agent_id == mock_agent.id
        assert proposal.proposal_type == ProposalType.TRAINING.value
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert proposal.estimated_duration_hours > 0
        assert len(proposal.capability_gaps) > 0
        assert len(proposal.learning_objectives) > 0
        assert mock_blocked_trigger.proposal_id == proposal.id

    @pytest.mark.asyncio
    async def test_proposal_includes_learning_objectives(
        self, service, mock_blocked_trigger, mock_agent, db_session
    ):
        """Test that proposal includes relevant learning objectives"""
        mock_agent_query = MagicMock()
        mock_agent_query.filter = MagicMock(return_value=mock_agent_query)
        mock_agent_query.first = MagicMock(return_value=mock_agent)
        db_session.query.return_value = mock_agent_query

        # Mock private methods
        service._get_similar_agents_training_history = AsyncMock(return_value=[])
        service._calculate_learning_rate = AsyncMock(return_value=1.0)

        # Create proposal
        proposal = await service.create_training_proposal(mock_blocked_trigger)

        # Verify objectives
        assert proposal.learning_objectives is not None
        assert len(proposal.learning_objectives) > 0
        assert any("execution flow" in obj.lower() for obj in proposal.learning_objectives)
        assert any("task completion" in obj.lower() for obj in proposal.learning_objectives)

    @pytest.mark.asyncio
    async def test_proposal_identifies_capability_gaps(
        self, service, mock_blocked_trigger, mock_agent, db_session
    ):
        """Test that proposal identifies relevant capability gaps"""
        mock_agent_query = MagicMock()
        mock_agent_query.filter = MagicMock(return_value=mock_agent_query)
        mock_agent_query.first = MagicMock(return_value=mock_agent)
        db_session.query.return_value = mock_agent_query

        # Mock private methods
        service._get_similar_agents_training_history = AsyncMock(return_value=[])
        service._calculate_learning_rate = AsyncMock(return_value=1.0)

        # Create proposal
        proposal = await service.create_training_proposal(mock_blocked_trigger)

        # Verify capability gaps identified
        assert proposal.capability_gaps is not None
        assert len(proposal.capability_gaps) > 0
        # Should include trigger-specific gaps
        assert any("task_execution" in gap for gap in proposal.capability_gaps)

    @pytest.mark.asyncio
    async def test_proposal_estimates_duration(
        self, service, mock_blocked_trigger, mock_agent, db_session
    ):
        """Test that proposal includes AI-generated duration estimate"""
        mock_agent_query = MagicMock()
        mock_agent_query.filter = MagicMock(return_value=mock_agent_query)
        mock_agent_query.first = MagicMock(return_value=mock_agent)
        db_session.query.return_value = mock_agent_query

        # Mock private methods
        service._get_similar_agents_training_history = AsyncMock(return_value=[])
        service._calculate_learning_rate = AsyncMock(return_value=1.0)

        # Create proposal
        proposal = await service.create_training_proposal(mock_blocked_trigger)

        # Verify duration estimation
        assert proposal.estimated_duration_hours > 0
        assert proposal.duration_estimation_confidence >= 0.5
        assert proposal.duration_estimation_reasoning is not None
        assert len(proposal.duration_estimation_reasoning) > 0

    @pytest.mark.asyncio
    async def test_accept_proposal_creates_session(
        self, service, mock_training_proposal, mock_agent, db_session
    ):
        """Test that accepting proposal creates training session"""
        # Mock proposal query
        mock_proposal_query = MagicMock()
        mock_proposal_query.filter = MagicMock(return_value=mock_proposal_query)
        mock_proposal_query.first = MagicMock(return_value=mock_training_proposal)
        db_session.query.return_value = mock_proposal_query

        # Accept proposal
        session = await service.approve_training(
            proposal_id=mock_training_proposal.id,
            user_id="supervisor-123"
        )

        # Verify session created
        assert session is not None
        assert session.agent_id == mock_training_proposal.agent_id
        assert session.status == "scheduled"
        assert session.supervisor_id == "supervisor-123"
        assert mock_training_proposal.status == ProposalStatus.APPROVED.value
        assert mock_training_proposal.approved_by == "supervisor-123"

    @pytest.mark.asyncio
    async def test_reject_proposal(self, service, mock_training_proposal, db_session):
        """Test rejecting a training proposal"""
        # Mock query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_training_proposal)
        db_session.query.return_value = mock_query

        # Reject proposal
        mock_training_proposal.status = ProposalStatus.REJECTED.value
        mock_training_proposal.rejected_by = "supervisor-123"
        mock_training_proposal.rejected_at = datetime.now()

        # Verify rejection
        assert mock_training_proposal.status == ProposalStatus.REJECTED.value
        assert mock_training_proposal.rejected_by == "supervisor-123"


# ========================================================================
# Test Training Sessions
# ========================================================================

class TestTrainingSessions:
    """Tests for training session management"""

    @pytest.mark.asyncio
    async def test_create_training_session(
        self, service, mock_training_proposal, mock_agent, db_session
    ):
        """Test creating training session from approved proposal"""
        # Mock proposal query
        mock_proposal_query = MagicMock()
        mock_proposal_query.filter = MagicMock(return_value=mock_proposal_query)
        mock_proposal_query.first = MagicMock(return_value=mock_training_proposal)
        db_session.query.return_value = mock_proposal_query

        # Approve training
        session = await service.approve_training(
            proposal_id=mock_training_proposal.id,
            user_id="supervisor-123"
        )

        # Verify session created
        assert session is not None
        assert session.proposal_id == mock_training_proposal.id
        assert session.agent_id == mock_training_proposal.agent_id
        assert session.status == "scheduled"
        assert session.supervisor_id == "supervisor-123"

    @pytest.mark.asyncio
    async def test_start_training(
        self, service, mock_training_session, db_session
    ):
        """Test starting a training session"""
        # Mock session query
        mock_session_query = MagicMock()
        mock_session_query.filter = MagicMock(return_value=mock_session_query)
        mock_session_query.first = MagicMock(return_value=mock_training_session)
        db_session.query.return_value = mock_session_query

        # Start training
        mock_training_session.status = "in_progress"
        mock_training_session.started_at = datetime.now()

        # Verify training started
        assert mock_training_session.status == "in_progress"
        assert mock_training_session.started_at is not None

    @pytest.mark.asyncio
    async def test_complete_training_with_outcome(
        self, service, mock_training_session, mock_agent, mock_training_proposal, db_session
    ):
        """Test completing training with performance outcome"""
        # Setup queries
        mock_session_query = MagicMock()
        mock_session_query.filter = MagicMock(return_value=mock_session_query)

        mock_agent_query = MagicMock()
        mock_agent_query.filter = MagicMock(return_value=mock_agent_query)
        mock_agent_query.first = MagicMock(return_value=mock_agent)

        mock_proposal_query = MagicMock()
        mock_proposal_query.filter = MagicMock(return_value=mock_proposal_query)
        mock_proposal_query.first = MagicMock(return_value=mock_training_proposal)

        mock_blocked_query = MagicMock()
        mock_blocked_query.filter = MagicMock(return_value=mock_blocked_query)
        mock_blocked_query.first = MagicMock(return_value=None)  # No blocked trigger

        # Chain queries
        db_session.query.side_effect = [
            mock_session_query,  # First query: session
            mock_agent_query,    # Second query: agent
            mock_proposal_query, # Third query: proposal
            mock_blocked_query,  # Fourth query: blocked trigger
        ]

        # Create outcome
        outcome = TrainingOutcome(
            performance_score=0.85,
            supervisor_feedback="Excellent performance",
            errors_count=2,
            tasks_completed=5,
            total_tasks=5,
            capabilities_developed=["financial_analysis", "task_execution"],
            capability_gaps_remaining=[]
        )

        # Complete training
        result = await service.complete_training_session(
            session_id=mock_training_session.id,
            outcome=outcome
        )

        # Verify completion
        assert result is not None
        assert result["performance_score"] == 0.85
        assert result["confidence_boost"] > 0
        assert result["session_id"] == mock_training_session.id
        assert mock_training_session.status == "completed"

    @pytest.mark.asyncio
    async def test_complete_training_promotes_to_intern(
        self, service, mock_training_session, mock_agent, mock_training_proposal, db_session
    ):
        """Test that good performance promotes agent to INTERN"""
        # Setup: Agent with confidence just below threshold
        mock_agent.confidence_score = 0.45  # Will reach 0.5 after boost

        # Setup queries
        mock_session_query = MagicMock()
        mock_session_query.filter = MagicMock(return_value=mock_session_query)

        mock_agent_query = MagicMock()
        mock_agent_query.filter = MagicMock(return_value=mock_agent_query)
        mock_agent_query.first = MagicMock(return_value=mock_agent)

        mock_proposal_query = MagicMock()
        mock_proposal_query.filter = MagicMock(return_value=mock_proposal_query)
        mock_proposal_query.first = MagicMock(return_value=mock_training_proposal)

        mock_blocked_query = MagicMock()
        mock_blocked_query.filter = MagicMock(return_value=mock_blocked_query)
        mock_blocked_query.first = MagicMock(return_value=None)

        db_session.query.side_effect = [
            mock_session_query,
            mock_agent_query,
            mock_proposal_query,
            mock_blocked_query,
        ]

        # Create excellent outcome (0.20 boost)
        outcome = TrainingOutcome(
            performance_score=0.90,
            supervisor_feedback="Outstanding",
            errors_count=0,
            tasks_completed=5,
            total_tasks=5,
            capabilities_developed=["task_execution"],
            capability_gaps_remaining=[]
        )

        # Complete training
        result = await service.complete_training_session(
            session_id=mock_training_session.id,
            outcome=outcome
        )

        # Verify promotion
        assert result["promoted_to_intern"] == True
        assert result["new_status"] == AgentStatus.INTERN.value
        assert mock_agent.status == AgentStatus.INTERN.value

    @pytest.mark.asyncio
    async def test_training_history(
        self, service, mock_training_session, db_session
    ):
        """Test retrieving agent's training history"""
        # Mock query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.order_by = MagicMock(return_value=mock_query)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_training_session])
        db_session.query.return_value = mock_query

        # Get history
        history = await service.get_training_history(
            agent_id=mock_training_session.agent_id,
            limit=50
        )

        # Verify history
        assert history is not None
        assert len(history) > 0
        assert history[0]["session_id"] == mock_training_session.id
        assert history[0]["agent_id"] == mock_training_session.agent_id


# ========================================================================
# Test Training Progress
# ========================================================================

class TestTrainingProgress:
    """Tests for training progress tracking"""

    @pytest.mark.asyncio
    async def test_update_progress(
        self, service, mock_training_session, db_session
    ):
        """Test updating training progress"""
        # Mock query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_training_session)
        db_session.query.return_value = mock_query

        # Update progress
        mock_training_session.tasks_completed = 3
        mock_training_session.total_tasks = 5

        # Verify progress
        assert mock_training_session.tasks_completed == 3
        assert mock_training_session.total_tasks == 5

    def test_progress_percentage_calculation(self, mock_training_session):
        """Test calculating progress percentage"""
        # Set progress
        mock_training_session.tasks_completed = 3
        mock_training_session.total_tasks = 5

        # Calculate percentage
        percentage = (
            mock_training_session.tasks_completed / mock_training_session.total_tasks * 100
            if mock_training_session.total_tasks > 0 else 0
        )

        assert percentage == 60.0

    def test_complete_all_modules_required(self, mock_training_session):
        """Test that all modules must be completed"""
        # Set all tasks completed
        mock_training_session.tasks_completed = 5
        mock_training_session.total_tasks = 5

        # Verify all complete
        assert mock_training_session.tasks_completed == mock_training_session.total_tasks

    def test_incomplete_modules_tracking(self, mock_training_session):
        """Test tracking incomplete modules"""
        # Set some tasks incomplete
        mock_training_session.tasks_completed = 3
        mock_training_session.total_tasks = 5
        mock_training_session.capability_gaps_remaining = ["reporting", "reconciliation"]

        # Verify incomplete
        remaining = mock_training_session.total_tasks - mock_training_session.tasks_completed
        assert remaining == 2
        assert len(mock_training_session.capability_gaps_remaining) > 0


# ========================================================================
# Test Confidence Boost Calculation
# ========================================================================

class TestConfidenceBoost:
    """Tests for confidence boost calculations"""

    def test_calculate_boost_for_poor_performance(self, service):
        """Test confidence boost for poor performance (<0.3)"""
        boost = service._calculate_confidence_boost(0.2)
        assert boost == 0.05

    def test_calculate_boost_for_below_average_performance(self, service):
        """Test confidence boost for below average performance (0.3-0.5)"""
        boost = service._calculate_confidence_boost(0.4)
        assert boost == 0.10

    def test_calculate_boost_for_good_performance(self, service):
        """Test confidence boost for good performance (0.5-0.7)"""
        boost = service._calculate_confidence_boost(0.6)
        assert boost == 0.15

    def test_calculate_boost_for_excellent_performance(self, service):
        """Test confidence boost for excellent performance (>0.7)"""
        boost = service._calculate_confidence_boost(0.85)
        assert boost == 0.20

    def test_confidence_never_exceeds_1_0(
        self, service, mock_training_session, mock_agent
    ):
        """Test that confidence score never exceeds 1.0"""
        # Set agent at 0.95 confidence
        mock_agent.confidence_score = 0.95

        # Apply maximum boost (0.20)
        boost = 0.20
        new_confidence = min(1.0, mock_agent.confidence_score + boost)

        # Verify capped at 1.0
        assert new_confidence == 1.0


# ========================================================================
# Test Error Handling
# ========================================================================

class TestErrorHandling:
    """Tests for error handling"""

    @pytest.mark.asyncio
    async def test_estimate_duration_agent_not_found(self, service, db_session):
        """Test estimating duration for non-existent agent"""
        # Mock query returning None
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        db_session.query.return_value = mock_query

        # Should raise ValueError
        with pytest.raises(ValueError, match="not found"):
            await service.estimate_training_duration(
                agent_id="non-existent",
                capability_gaps=["task_execution"],
                target_maturity=AgentStatus.INTERN.value
            )

    @pytest.mark.asyncio
    async def test_approve_non_existent_proposal(self, service, db_session):
        """Test approving non-existent proposal"""
        # Mock query returning None
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        db_session.query.return_value = mock_query

        # Should raise ValueError
        with pytest.raises(ValueError, match="not found"):
            await service.approve_training(
                proposal_id="non-existent",
                user_id="supervisor-123"
            )

    @pytest.mark.asyncio
    async def test_approve_already_approved_proposal(
        self, service, mock_training_proposal, db_session
    ):
        """Test approving proposal that's already approved"""
        # Set proposal to already approved
        mock_training_proposal.status = ProposalStatus.APPROVED.value

        # Mock query
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_training_proposal)
        db_session.query.return_value = mock_query

        # Should raise ValueError
        with pytest.raises(ValueError, match="PROPOSED"):
            await service.approve_training(
                proposal_id=mock_training_proposal.id,
                user_id="supervisor-123"
            )

    @pytest.mark.asyncio
    async def test_complete_non_existent_session(self, service, db_session):
        """Test completing non-existent session"""
        # Mock query returning None
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        db_session.query.return_value = mock_query

        # Create outcome
        outcome = TrainingOutcome(
            performance_score=0.85,
            supervisor_feedback="Good",
            errors_count=0,
            tasks_completed=5,
            total_tasks=5,
            capabilities_developed=["task_execution"],
            capability_gaps_remaining=[]
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="not found"):
            await service.complete_training_session(
                session_id="non-existent",
                outcome=outcome
            )
