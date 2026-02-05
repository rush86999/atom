"""
Student Training Service Tests

Comprehensive test suite for StudentTrainingService including:
- Training proposal creation from blocked triggers
- Training approval and session creation
- Training completion and agent maturity progression
- AI-based training duration estimation
- Training history retrieval
- Confidence boost calculations
- Error handling and edge cases
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pytest
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


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def db():
    """Create a test database session."""
    import os
    # Set test database URL
    os.environ['DATABASE_URL'] = 'sqlite:///./test_atom.db'

    from core.database import engine, SessionLocal
    from core.models import Base

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create session
    db = SessionLocal()
    db.expire_on_commit = False  # Allow access to objects after commit

    try:
        yield db
        db.rollback()  # Rollback changes after test
    finally:
        db.close()
        # Clean up test database
        import os
        try:
            os.remove('./test_atom.db')
        except:
            pass


@pytest.fixture
def student_agent(db):
    """Create a test STUDENT agent."""
    agent_id = f"student-agent-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Test Student Agent",
        category="Sales",
        module_path="agents.test_student",
        class_name="TestStudentAgent",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.35,
        description="A test student agent for training"
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)
    yield agent
    # Cleanup
    db.query(TrainingSession).filter(TrainingSession.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentProposal).filter(AgentProposal.agent_id == agent_id).delete(synchronize_session=False)
    db.query(BlockedTriggerContext).filter(BlockedTriggerContext.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def intern_agent(db):
    """Create a test INTERN agent for historical data."""
    agent_id = f"intern-agent-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Test Intern Agent",
        category="Sales",
        module_path="agents.test_intern",
        class_name="TestInternAgent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.65,
        description="A test intern agent for comparison"
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)
    yield agent
    # Cleanup
    db.query(TrainingSession).filter(TrainingSession.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentProposal).filter(AgentProposal.agent_id == agent_id).delete(synchronize_session=False)
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def blocked_trigger(db, student_agent):
    """Create a blocked trigger context."""
    trigger = BlockedTriggerContext(
        agent_id=student_agent.id,
        trigger_type="workflow_trigger",
        trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
        trigger_context={
            "workflow_id": "test-workflow-123",
            "category": "Sales",
            "action": "update_crm"
        },
        reason="Agent is in STUDENT maturity level and cannot execute automated triggers",
        resolved=False
    )
    db.add(trigger)
    db.commit()
    db.expunge(trigger)
    yield trigger
    # Cleanup
    db.query(BlockedTriggerContext).filter(BlockedTriggerContext.id == trigger.id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def training_service(db):
    """Create a StudentTrainingService instance."""
    return StudentTrainingService(db)


# ============================================================================
# Tests: Training Proposal Creation
# ============================================================================

class TestTrainingProposalCreation:
    """Tests for creating training proposals from blocked triggers."""

    @pytest.mark.asyncio
    async def test_create_training_proposal_basic(self, training_service, blocked_trigger):
        """Test basic training proposal creation."""
        proposal = await training_service.create_training_proposal(blocked_trigger)

        assert proposal is not None
        assert proposal.proposal_type == ProposalType.TRAINING.value
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert proposal.agent_id == blocked_trigger.agent_id
        assert proposal.capability_gaps is not None
        assert len(proposal.capability_gaps) > 0
        assert proposal.learning_objectives is not None
        assert len(proposal.learning_objectives) > 0
        assert proposal.estimated_duration_hours > 0
        assert proposal.duration_estimation_confidence > 0
        assert proposal.proposed_by == "atom_meta_agent"

    @pytest.mark.asyncio
    async def test_create_training_proposal_links_blocked_trigger(self, training_service, blocked_trigger, db):
        """Test that blocked trigger is linked to proposal."""
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Refresh blocked trigger from DB
        db.refresh(blocked_trigger)
        assert blocked_trigger.proposal_id == proposal.id

    @pytest.mark.asyncio
    async def test_create_training_proposal_capability_gaps(self, training_service, blocked_trigger):
        """Test capability gap identification."""
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Check that relevant capability gaps are identified
        assert any("workflow" in gap.lower() or "automation" in gap.lower()
                   for gap in proposal.capability_gaps)

    @pytest.mark.asyncio
    async def test_create_training_proposal_learning_objectives(self, training_service, blocked_trigger):
        """Test learning objective generation."""
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Check that learning objectives are generated
        assert len(proposal.learning_objectives) >= 3  # Base objectives + capability-specific

    @pytest.mark.asyncio
    async def test_create_training_proposal_duration_estimation(self, training_service, blocked_trigger):
        """Test AI-based duration estimation."""
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Check duration estimation
        assert proposal.estimated_duration_hours >= 10  # Minimum reasonable duration
        assert proposal.estimated_duration_hours <= 100  # Maximum reasonable duration
        assert proposal.duration_estimation_confidence >= 0.5
        assert proposal.duration_estimation_reasoning is not None
        assert len(proposal.duration_estimation_reasoning) > 0

    @pytest.mark.asyncio
    async def test_create_training_proposal_agent_not_found(self, training_service, db):
        """Test error handling when agent is not found."""
        # Create blocked trigger for non-existent agent
        fake_agent_id = f"fake-agent-{uuid.uuid4()}"
        trigger = BlockedTriggerContext(
            agent_id=fake_agent_id,
            trigger_type="workflow_trigger",
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_context={},
            reason="Test",
            resolved=False
        )
        db.add(trigger)
        db.commit()

        with pytest.raises(ValueError, match=f"Agent {fake_agent_id} not found"):
            await training_service.create_training_proposal(trigger)


# ============================================================================
# Tests: Training Approval
# ============================================================================

class TestTrainingApproval:
    """Tests for approving training proposals and creating sessions."""

    @pytest.mark.asyncio
    async def test_approve_training_basic(self, training_service, blocked_trigger, db):
        """Test basic training approval."""
        # Create proposal first
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Approve training
        user_id = f"user-{uuid.uuid4()}"
        session = await training_service.approve_training(proposal.id, user_id)

        assert session is not None
        assert session.proposal_id == proposal.id
        assert session.agent_id == proposal.agent_id
        assert session.status == "scheduled"
        assert session.supervisor_id == user_id
        assert session.total_tasks == len(proposal.learning_objectives)

        # Check proposal is updated
        db.refresh(proposal)
        assert proposal.status == ProposalStatus.APPROVED.value
        assert proposal.approved_by == user_id
        assert proposal.approved_at is not None
        assert proposal.training_start_date is not None
        assert proposal.training_end_date is not None

    @pytest.mark.asyncio
    async def test_approve_training_with_modifications(self, training_service, blocked_trigger):
        """Test training approval with duration modifications."""
        proposal = await training_service.create_training_proposal(blocked_trigger)

        user_id = f"user-{uuid.uuid4()}"
        modifications = {
            "duration_override_hours": 20.0,
            "hours_per_day_limit": 4.0
        }
        session = await training_service.approve_training(proposal.id, user_id, modifications)

        # Check modifications are applied
        assert proposal.user_override_duration_hours == 20.0
        assert proposal.hours_per_day_limit == 4.0

        # Check end date calculation (20 hours / 4 hours per day = 5 days)
        expected_duration = timedelta(days=5)
        actual_duration = proposal.training_end_date - proposal.training_start_date
        assert abs(actual_duration.total_seconds() - expected_duration.total_seconds()) < 60  # Within 1 minute

    @pytest.mark.asyncio
    async def test_approve_training_default_schedule(self, training_service, blocked_trigger):
        """Test default schedule calculation (8 hours/day)."""
        proposal = await training_service.create_training_proposal(blocked_trigger)

        user_id = f"user-{uuid.uuid4()}"
        session = await training_service.approve_training(proposal.id, user_id)

        # Check default 8 hours/day is used
        expected_days = proposal.estimated_duration_hours / 8
        expected_duration = timedelta(days=expected_days)
        actual_duration = proposal.training_end_date - proposal.training_start_date
        assert abs(actual_duration.total_seconds() - expected_duration.total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_approve_training_proposal_not_found(self, training_service):
        """Test error handling when proposal is not found."""
        fake_proposal_id = f"fake-proposal-{uuid.uuid4()}"
        user_id = f"user-{uuid.uuid4()}"

        with pytest.raises(ValueError, match=f"Proposal {fake_proposal_id} not found"):
            await training_service.approve_training(fake_proposal_id, user_id)

    @pytest.mark.asyncio
    async def test_approve_training_invalid_status(self, training_service, blocked_trigger, db):
        """Test error handling when proposal is not in PROPOSED status."""
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Change proposal status to APPROVED
        proposal.status = ProposalStatus.APPROVED.value
        db.commit()

        user_id = f"user-{uuid.uuid4()}"
        with pytest.raises(ValueError, match="Proposal must be in PROPOSED status"):
            await training_service.approve_training(proposal.id, user_id)


# ============================================================================
# Tests: Training Completion
# ============================================================================

class TestTrainingCompletion:
    """Tests for completing training sessions."""

    @pytest.mark.asyncio
    async def test_complete_training_basic(self, training_service, student_agent, blocked_trigger, db):
        """Test basic training completion."""
        # Create and approve training
        proposal = await training_service.create_training_proposal(blocked_trigger)
        session = await training_service.approve_training(proposal.id, f"user-{uuid.uuid4()}")

        # Start the session
        session.status = "in_progress"
        session.started_at = datetime.now()
        db.commit()

        # Complete training
        outcome = TrainingOutcome(
            performance_score=0.85,
            supervisor_feedback="Excellent progress",
            errors_count=2,
            tasks_completed=8,
            total_tasks=10,
            capabilities_developed=["workflow_automation", "decision_making"],
            capability_gaps_remaining=["advanced_analytics"]
        )
        result = await training_service.complete_training_session(session.id, outcome)

        assert result is not None
        assert result["session_id"] == session.id
        assert result["agent_id"] == student_agent.id
        assert result["performance_score"] == 0.85
        assert result["confidence_boost"] > 0
        assert result["old_confidence"] < result["new_confidence"]
        assert "capabilities_developed" in result

        # Check session is updated
        db.refresh(session)
        assert session.status == "completed"
        assert session.completed_at is not None
        assert session.performance_score == 0.85
        assert session.confidence_boost > 0

    @pytest.mark.asyncio
    async def test_complete_training_promotes_to_intern(self, training_service, student_agent, blocked_trigger, db):
        """Test that successful training promotes agent to INTERN."""
        # Start with confidence just below threshold
        student_agent.confidence_score = 0.48
        db.commit()

        proposal = await training_service.create_training_proposal(blocked_trigger)
        session = await training_service.approve_training(proposal.id, f"user-{uuid.uuid4()}")
        session.status = "in_progress"
        session.started_at = datetime.now()
        db.commit()

        # Complete with excellent performance
        outcome = TrainingOutcome(
            performance_score=0.95,
            supervisor_feedback="Outstanding",
            errors_count=0,
            tasks_completed=10,
            total_tasks=10,
            capabilities_developed=["all"],
            capability_gaps_remaining=[]
        )
        result = await training_service.complete_training_session(session.id, outcome)

        assert result["promoted_to_intern"] is True
        assert result["new_status"] == AgentStatus.INTERN.value

        db.refresh(student_agent)
        assert student_agent.status == AgentStatus.INTERN.value
        assert student_agent.confidence_score >= 0.5

    @pytest.mark.asyncio
    async def test_complete_training_no_promotion(self, training_service, student_agent, blocked_trigger, db):
        """Test that marginal performance doesn't promote agent."""
        proposal = await training_service.create_training_proposal(blocked_trigger)
        session = await training_service.approve_training(proposal.id, f"user-{uuid.uuid4()}")
        session.status = "in_progress"
        session.started_at = datetime.now()
        db.commit()

        # Complete with poor performance
        outcome = TrainingOutcome(
            performance_score=0.35,
            supervisor_feedback="Needs more practice",
            errors_count=5,
            tasks_completed=5,
            total_tasks=10,
            capabilities_developed=["basic"],
            capability_gaps_remaining=["advanced"]
        )
        result = await training_service.complete_training_session(session.id, outcome)

        assert result["promoted_to_intern"] is False

        db.refresh(student_agent)
        assert student_agent.status == AgentStatus.STUDENT.value
        assert student_agent.confidence_score < 0.5

    @pytest.mark.asyncio
    async def test_complete_training_updates_proposal(self, training_service, blocked_trigger, db):
        """Test that proposal is updated with execution result."""
        proposal = await training_service.create_training_proposal(blocked_trigger)
        session = await training_service.approve_training(proposal.id, f"user-{uuid.uuid4()}")
        session.status = "in_progress"
        session.started_at = datetime.now()
        db.commit()

        outcome = TrainingOutcome(
            performance_score=0.75,
            supervisor_feedback="Good",
            errors_count=3,
            tasks_completed=7,
            total_tasks=10,
            capabilities_developed=["workflow_automation"],
            capability_gaps_remaining=[]
        )
        await training_service.complete_training_session(session.id, outcome)

        # Check proposal is updated
        db.refresh(proposal)
        assert proposal.status == ProposalStatus.EXECUTED.value
        assert proposal.completed_at is not None
        assert proposal.execution_result is not None
        assert "performance_score" in proposal.execution_result
        assert "confidence_boost" in proposal.execution_result

    @pytest.mark.asyncio
    async def test_complete_training_resolves_blocked_trigger(self, training_service, blocked_trigger, db):
        """Test that blocked trigger is resolved."""
        proposal = await training_service.create_training_proposal(blocked_trigger)
        session = await training_service.approve_training(proposal.id, f"user-{uuid.uuid4()}")
        session.status = "in_progress"
        session.started_at = datetime.now()
        db.commit()

        outcome = TrainingOutcome(
            performance_score=0.80,
            supervisor_feedback="Well done",
            errors_count=2,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["workflow_automation"],
            capability_gaps_remaining=[]
        )
        await training_service.complete_training_session(session.id, outcome)

        # Check blocked trigger is resolved
        db.refresh(blocked_trigger)
        assert blocked_trigger.resolved is True
        assert blocked_trigger.resolved_at is not None
        assert blocked_trigger.resolution_outcome is not None

    @pytest.mark.asyncio
    async def test_complete_training_session_not_found(self, training_service):
        """Test error handling when session is not found."""
        fake_session_id = f"fake-session-{uuid.uuid4()}"
        outcome = TrainingOutcome(
            performance_score=0.75,
            supervisor_feedback="Test",
            errors_count=0,
            tasks_completed=10,
            total_tasks=10,
            capabilities_developed=[],
            capability_gaps_remaining=[]
        )

        with pytest.raises(ValueError, match=f"Training session {fake_session_id} not found"):
            await training_service.complete_training_session(fake_session_id, outcome)


# ============================================================================
# Tests: Training History
# ============================================================================

class TestTrainingHistory:
    """Tests for retrieving training history."""

    @pytest.mark.asyncio
    async def test_get_training_history_empty(self, training_service, student_agent):
        """Test getting training history for agent with no history."""
        history = await training_service.get_training_history(student_agent.id)

        assert history is not None
        assert isinstance(history, list)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_get_training_history_with_sessions(self, training_service, student_agent, blocked_trigger):
        """Test getting training history with completed sessions."""
        # Create and complete training
        proposal = await training_service.create_training_proposal(blocked_trigger)
        session = await training_service.approve_training(proposal.id, f"user-{uuid.uuid4()}")
        session.status = "in_progress"
        session.started_at = datetime.now()
        session_id = session.id

        outcome = TrainingOutcome(
            performance_score=0.85,
            supervisor_feedback="Great",
            errors_count=1,
            tasks_completed=9,
            total_tasks=10,
            capabilities_developed=["workflow_automation"],
            capability_gaps_remaining=[]
        )
        await training_service.complete_training_session(session_id, outcome)

        # Get history
        history = await training_service.get_training_history(student_agent.id)

        assert len(history) == 1
        assert history[0]["session_id"] == session_id
        assert history[0]["status"] == "completed"
        assert history[0]["performance_score"] == 0.85
        assert history[0]["proposal_title"] is not None

    @pytest.mark.asyncio
    async def test_get_training_history_limit(self, training_service, student_agent):
        """Test training history limit parameter."""
        # Create multiple proposals (we'll just create them without completing)
        for i in range(5):
            trigger = BlockedTriggerContext(
                agent_id=student_agent.id,
                trigger_type=f"trigger_{i}",
                trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
                trigger_context={},
                reason="Test",
                resolved=False
            )
            training_service.db.add(trigger)
            training_service.db.commit()

            await training_service.create_training_proposal(trigger)
            await training_service.approve_training(
                training_service.db.query(AgentProposal).order_by(
                    AgentProposal.created_at.desc()
                ).first().id,
                f"user-{uuid.uuid4()}"
            )

        # Get limited history
        history = await training_service.get_training_history(student_agent.id, limit=3)

        assert len(history) <= 3


# ============================================================================
# Tests: Duration Estimation
# ============================================================================

class TestDurationEstimation:
    """Tests for AI-based training duration estimation."""

    @pytest.mark.asyncio
    async def test_estimate_duration_basic(self, training_service, student_agent):
        """Test basic duration estimation."""
        capability_gaps = ["workflow_automation", "decision_making"]
        estimate = await training_service.estimate_training_duration(
            agent_id=student_agent.id,
            capability_gaps=capability_gaps,
            target_maturity=AgentStatus.INTERN.value
        )

        assert isinstance(estimate, TrainingDurationEstimate)
        assert estimate.estimated_hours > 0
        assert estimate.confidence > 0
        assert estimate.reasoning is not None
        assert estimate.min_hours < estimate.estimated_hours < estimate.max_hours
        assert estimate.similar_agents is not None

    @pytest.mark.asyncio
    async def test_estimate_duration_low_confidence(self, training_service, student_agent):
        """Test duration estimation for low confidence agent."""
        student_agent.confidence_score = 0.1
        training_service.db.commit()

        capability_gaps = ["task_execution", "context_understanding"]
        estimate = await training_service.estimate_training_duration(
            agent_id=student_agent.id,
            capability_gaps=capability_gaps,
            target_maturity=AgentStatus.INTERN.value
        )

        # Low confidence should result in longer training
        assert estimate.estimated_hours > 40  # Base hours

    @pytest.mark.asyncio
    async def test_estimate_duration_many_gaps(self, training_service, student_agent):
        """Test duration estimation with many capability gaps."""
        many_gaps = ["gap1", "gap2", "gap3", "gap4", "gap5", "gap6", "gap7"]
        estimate = await training_service.estimate_training_duration(
            agent_id=student_agent.id,
            capability_gaps=many_gaps,
            target_maturity=AgentStatus.INTERN.value
        )

        # Many gaps should increase duration
        assert estimate.estimated_hours > 40  # Base hours

    @pytest.mark.asyncio
    async def test_estimate_duration_with_similar_agents(self, training_service, intern_agent, db):
        """Test duration estimation using historical data."""
        # Create completed training sessions for intern_agent
        for i in range(3):
            proposal = AgentProposal(
                agent_id=intern_agent.id,
                agent_name=intern_agent.name,
                proposal_type=ProposalType.TRAINING.value,
                title=f"Training {i}",
                description="Test",
                status=ProposalStatus.EXECUTED.value,
                proposed_by="test"
            )
            db.add(proposal)
            db.commit()

            session = TrainingSession(
                proposal_id=proposal.id,
                agent_id=intern_agent.id,
                agent_name=intern_agent.name,
                status="completed",
                performance_score=0.8,
                duration_seconds=3600 * 45  # 45 hours
            )
            db.add(session)
            db.commit()

        # Now estimate for student agent
        student_agent = db.query(AgentRegistry).filter(AgentRegistry.id == student_agent.id).first()
        estimate = await training_service.estimate_training_duration(
            agent_id=student_agent.id,
            capability_gaps=["workflow_automation"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Should have similar agents in history
        assert len(estimate.similar_agents) > 0
        assert estimate.confidence > 0.5  # Higher confidence with historical data

    @pytest.mark.asyncio
    async def test_estimate_duration_agent_not_found(self, training_service):
        """Test error handling when agent is not found."""
        fake_agent_id = f"fake-agent-{uuid.uuid4()}"

        with pytest.raises(ValueError, match=f"Agent {fake_agent_id} not found"):
            await training_service.estimate_training_duration(
                agent_id=fake_agent_id,
                capability_gaps=[],
                target_maturity=AgentStatus.INTERN.value
            )


# ============================================================================
# Tests: Confidence Boost Calculation
# ============================================================================

class TestConfidenceBoost:
    """Tests for confidence boost calculation."""

    def test_calculate_confidence_boost_poor_performance(self, training_service):
        """Test confidence boost for poor performance (0.0-0.3)."""
        boost = training_service._calculate_confidence_boost(0.2)
        assert boost == 0.05

    def test_calculate_confidence_boost_below_average(self, training_service):
        """Test confidence boost for below average performance (0.3-0.5)."""
        boost = training_service._calculate_confidence_boost(0.4)
        assert boost == 0.10

    def test_calculate_confidence_boost_good_performance(self, training_service):
        """Test confidence boost for good performance (0.5-0.7)."""
        boost = training_service._calculate_confidence_boost(0.6)
        assert boost == 0.15

    def test_calculate_confidence_boost_excellent_performance(self, training_service):
        """Test confidence boost for excellent performance (0.7-1.0)."""
        boost = training_service._calculate_confidence_boost(0.9)
        assert boost == 0.20

    def test_calculate_confidence_boost_boundary_values(self, training_service):
        """Test confidence boost at boundary values."""
        # Lower boundary
        boost = training_service._calculate_confidence_boost(0.0)
        assert boost == 0.05

        # Upper boundary
        boost = training_service._calculate_confidence_boost(1.0)
        assert boost == 0.20


# ============================================================================
# Tests: Learning Rate Calculation
# ============================================================================

class TestLearningRate:
    """Tests for agent learning rate calculation."""

    @pytest.mark.asyncio
    async def test_learning_rate_no_previous_sessions(self, training_service, student_agent):
        """Test learning rate for agent with no previous sessions."""
        learning_rate = await training_service._calculate_learning_rate(student_agent.id)
        assert learning_rate == 1.0  # Default for new agents

    @pytest.mark.asyncio
    async def test_learning_rate_with_sessions(self, training_service, student_agent, db):
        """Test learning rate calculation with previous sessions."""
        # Create completed sessions
        for score in [0.6, 0.7, 0.8]:
            proposal = AgentProposal(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                proposal_type=ProposalType.TRAINING.value,
                title="Test Training",
                description="Test",
                status=ProposalStatus.EXECUTED.value,
                proposed_by="test"
            )
            db.add(proposal)
            db.commit()

            session = TrainingSession(
                proposal_id=proposal.id,
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                status="completed",
                performance_score=score
            )
            db.add(session)
            db.commit()

        learning_rate = await training_service._calculate_learning_rate(student_agent.id)

        # Average performance is 0.7, so learning rate should be around 1.0
        assert 0.8 <= learning_rate <= 1.2

    @pytest.mark.asyncio
    async def test_learning_rate_fast_learner(self, training_service, student_agent, db):
        """Test learning rate for fast learner (high performance)."""
        # Create high-performance sessions
        for score in [0.9, 0.95, 0.85]:
            proposal = AgentProposal(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                proposal_type=ProposalType.TRAINING.value,
                title="Test Training",
                description="Test",
                status=ProposalStatus.EXECUTED.value,
                proposed_by="test"
            )
            db.add(proposal)
            db.commit()

            session = TrainingSession(
                proposal_id=proposal.id,
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                status="completed",
                performance_score=score
            )
            db.add(session)
            db.commit()

        learning_rate = await training_service._calculate_learning_rate(student_agent.id)

        # Should be > 1.0 for fast learner
        assert learning_rate > 1.0

    @pytest.mark.asyncio
    async def test_learning_rate_slow_learner(self, training_service, student_agent, db):
        """Test learning rate for slow learner (low performance)."""
        # Create low-performance sessions
        for score in [0.5, 0.55, 0.6]:
            proposal = AgentProposal(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                proposal_type=ProposalType.TRAINING.value,
                title="Test Training",
                description="Test",
                status=ProposalStatus.EXECUTED.value,
                proposed_by="test"
            )
            db.add(proposal)
            db.commit()

            session = TrainingSession(
                proposal_id=proposal.id,
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                status="completed",
                performance_score=score
            )
            db.add(session)
            db.commit()

        learning_rate = await training_service._calculate_learning_rate(student_agent.id)

        # Should be < 1.0 for slow learner
        assert learning_rate < 1.0


# ============================================================================
# Tests: Capability Gaps and Learning Objectives
# ============================================================================

class TestCapabilityGapsAndObjectives:
    """Tests for capability gap identification and learning objective generation."""

    @pytest.mark.asyncio
    async def test_identify_capability_gaps_workflow_trigger(self, training_service, student_agent, db):
        """Test capability gap identification for workflow triggers."""
        trigger = BlockedTriggerContext(
            agent_id=student_agent.id,
            trigger_type="workflow_trigger",
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_context={"workflow_id": "test"},
            reason="Test",
            resolved=False
        )
        db.add(trigger)
        db.commit()

        gaps = await training_service._identify_capability_gaps(student_agent, trigger)

        assert "workflow_automation" in gaps
        assert "decision_making" in gaps

    @pytest.mark.asyncio
    async def test_identify_capability_gaps_form_submit(self, training_service, student_agent, db):
        """Test capability gap identification for form submissions."""
        trigger = BlockedTriggerContext(
            agent_id=student_agent.id,
            trigger_type="form_submit",
            trigger_source=TriggerSource.MANUAL.value,
            trigger_context={"form_id": "test"},
            reason="Test",
            resolved=False
        )
        db.add(trigger)
        db.commit()

        gaps = await training_service._identify_capability_gaps(student_agent, trigger)

        assert "data_validation" in gaps
        assert "form_processing" in gaps

    @pytest.mark.asyncio
    async def test_generate_learning_objectives(self, training_service, student_agent, db):
        """Test learning objective generation."""
        trigger = BlockedTriggerContext(
            agent_id=student_agent.id,
            trigger_type="agent_message",
            trigger_source=TriggerSource.MANUAL.value,
            trigger_context={},
            reason="Test",
            resolved=False
        )
        db.add(trigger)
        db.commit()

        gaps = ["task_execution", "context_understanding"]
        objectives = await training_service._generate_learning_objectives(
            student_agent, trigger, gaps
        )

        assert len(objectives) > 3
        assert any("task_execution" in obj.lower() for obj in objectives)


# ============================================================================
# Tests: Scenario Template Selection
# ============================================================================

class TestScenarioTemplate:
    """Tests for training scenario template selection."""

    def test_select_scenario_template_finance(self, training_service):
        """Test scenario template for Finance category."""
        trigger = BlockedTriggerContext(
            agent_id="test",
            trigger_type="test",
            trigger_source=TriggerSource.MANUAL.value,
            trigger_context={"category": "Finance"},
            reason="Test",
            resolved=False
        )
        template = training_service._select_scenario_template(trigger)
        assert template == "Finance Fundamentals"

    def test_select_scenario_template_sales(self, training_service):
        """Test scenario template for Sales category."""
        trigger = BlockedTriggerContext(
            agent_id="test",
            trigger_type="test",
            trigger_source=TriggerSource.MANUAL.value,
            trigger_context={"category": "Sales"},
            reason="Test",
            resolved=False
        )
        template = training_service._select_scenario_template(trigger)
        assert template == "Sales Operations"

    def test_select_scenario_template_default(self, training_service):
        """Test default scenario template."""
        trigger = BlockedTriggerContext(
            agent_id="test",
            trigger_type="test",
            trigger_source=TriggerSource.MANUAL.value,
            trigger_context={},
            reason="Test",
            resolved=False
        )
        template = training_service._select_scenario_template(trigger)
        assert template == "General Operations"
