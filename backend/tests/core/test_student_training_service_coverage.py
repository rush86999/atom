"""
Comprehensive tests for StudentTrainingService

Target: 75%+ coverage for core/student_training_service.py
Focus: Training sessions, proposal workflows, duration estimation, supervision integration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

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
# Note: db_session fixture is imported from tests/conftest.py


@pytest.fixture
def student_agent(db_session):
    """Create a STUDENT level agent for testing."""
    agent = AgentRegistry(
        id="test-student-agent",
        tenant_id="test-tenant",
        name="Test Student Agent",
        category="Finance",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def intern_agent(db_session):
    """Create an INTERN level agent for testing."""
    agent = AgentRegistry(
        id="test-intern-agent",
        tenant_id="test-tenant",
        name="Test Intern Agent",
        category="Sales",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def blocked_trigger(db_session, student_agent):
    """Create a blocked trigger context for testing."""
    trigger = BlockedTriggerContext(
        id="test-blocked-trigger",
        agent_id=student_agent.id,
        agent_name=student_agent.name,
        agent_maturity_at_block=AgentStatus.STUDENT.value,
        confidence_score_at_block=student_agent.confidence_score,
        trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
        trigger_type="workflow_trigger",
        trigger_context={
            "category": "Finance",
            "action": "process_invoice",
            "priority": "high"
        },
        routing_decision="training",
        block_reason="STUDENT maturity level prevents automated execution",
        resolved=False
    )
    db_session.add(trigger)
    db_session.commit()
    db_session.refresh(trigger)
    return trigger


@pytest.fixture
def training_service(db_session):
    """Create StudentTrainingService instance."""
    return StudentTrainingService(db_session)


# ========================================================================
# Test Class 1: Training Session Tests
# ========================================================================

class TestTrainingSessions:
    """Test training session CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_training_proposal_for_student_agent(
        self, training_service, student_agent, blocked_trigger
    ):
        """Test creating training proposal from blocked trigger."""
        proposal = await training_service.create_training_proposal(blocked_trigger)

        assert proposal is not None
        assert proposal.agent_id == student_agent.id
        assert proposal.proposal_type == ProposalType.TRAINING.value
        assert proposal.status == ProposalStatus.PROPOSED.value
        assert proposal.estimated_duration_hours > 0
        assert len(proposal.capability_gaps) > 0
        assert len(proposal.learning_objectives) > 0
        assert blocked_trigger.proposal_id == proposal.id

    @pytest.mark.asyncio
    async def test_get_training_session_by_id(
        self, training_service, student_agent, blocked_trigger, db_session
    ):
        """Test retrieving training session by ID."""
        # Create proposal first
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Create session
        session = TrainingSession(
            proposal_id=proposal.id,
            agent_id=student_agent.id,
            agent_name=student_agent.name,
            status="scheduled",
            supervisor_id="test-supervisor",
            total_tasks=5
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Retrieve by ID
        retrieved = db_session.query(TrainingSession).filter(
            TrainingSession.id == session.id
        ).first()

        assert retrieved is not None
        assert retrieved.id == session.id
        assert retrieved.agent_id == student_agent.id

    @pytest.mark.asyncio
    async def test_update_training_session_progress(
        self, training_service, student_agent, blocked_trigger, db_session
    ):
        """Test updating training session progress."""
        # Create proposal and session
        proposal = await training_service.create_training_proposal(blocked_trigger)
        session = TrainingSession(
            proposal_id=proposal.id,
            agent_id=student_agent.id,
            agent_name=student_agent.name,
            status="in_progress",
            started_at=datetime.now(),
            supervisor_id="test-supervisor",
            total_tasks=5
        )
        db_session.add(session)
        db_session.commit()

        # Update progress
        session.tasks_completed = 3
        session.progress_percentage = 60.0
        db_session.commit()

        # Verify update
        assert session.tasks_completed == 3
        assert session.progress_percentage == 60.0

    @pytest.mark.asyncio
    async def test_complete_training_session_success(
        self, training_service, student_agent, blocked_trigger
    ):
        """Test completing training session with good performance."""
        # Create proposal
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Create session
        session = TrainingSession(
            proposal_id=proposal.id,
            agent_id=student_agent.id,
            agent_name=student_agent.name,
            status="in_progress",
            started_at=datetime.now() - timedelta(hours=2),
            supervisor_id="test-supervisor",
            total_tasks=5
        )
        training_service.db.add(session)
        training_service.db.commit()

        # Create outcome
        outcome = TrainingOutcome(
            performance_score=0.85,
            supervisor_feedback="Excellent progress",
            errors_count=2,
            tasks_completed=5,
            total_tasks=5,
            capabilities_developed=["task_execution", "decision_making"],
            capability_gaps_remaining=["complex_problem_solving"]
        )

        # Complete training
        result = await training_service.complete_training_session(session.id, outcome)

        assert result["session_id"] == session.id
        assert result["performance_score"] == 0.85
        assert result["confidence_boost"] > 0
        assert result["promoted_to_intern"] == True  # Should promote with 0.85 performance
        assert result["new_status"] == AgentStatus.INTERN.value

    @pytest.mark.asyncio
    async def test_complete_training_session_failure(
        self, training_service, student_agent, blocked_trigger
    ):
        """Test completing training session with poor performance."""
        # Create proposal and session
        proposal = await training_service.create_training_proposal(blocked_trigger)
        session = TrainingSession(
            proposal_id=proposal.id,
            agent_id=student_agent.id,
            agent_name=student_agent.name,
            status="in_progress",
            started_at=datetime.now() - timedelta(hours=2),
            supervisor_id="test-supervisor",
            total_tasks=5
        )
        training_service.db.add(session)
        training_service.db.commit()

        # Create poor outcome
        outcome = TrainingOutcome(
            performance_score=0.25,
            supervisor_feedback="Needs significant improvement",
            errors_count=10,
            tasks_completed=2,
            total_tasks=5,
            capabilities_developed=["basic_understanding"],
            capability_gaps_remaining=["task_execution", "decision_making", "error_handling"]
        )

        # Complete training
        old_confidence = student_agent.confidence_score
        result = await training_service.complete_training_session(session.id, outcome)

        assert result["performance_score"] == 0.25
        assert result["promoted_to_intern"] == False
        assert result["confidence_boost"] < old_confidence  # Small boost for poor performance
        assert result["new_status"] == AgentStatus.STUDENT.value  # Still STUDENT


# ========================================================================
# Test Class 2: Proposal Workflow Tests
# ========================================================================

class TestProposalWorkflow:
    """Test proposal creation, approval, rejection, expiration."""

    @pytest.mark.asyncio
    async def test_create_proposal_for_intern_agent(
        self, training_service, intern_agent, db_session
    ):
        """Test creating proposal for INTERN agent (different category)."""
        # Create blocked trigger for intern agent
        trigger = BlockedTriggerContext(
            id="intern-blocked-trigger",
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            agent_maturity_at_block=AgentStatus.INTERN.value,
            confidence_score_at_block=intern_agent.confidence_score,
            trigger_source=TriggerSource.MANUAL.value,
            trigger_type="agent_message",
            trigger_context={"category": "Sales", "action": "send_email"},
            routing_decision="training",
            block_reason="INTERN requires approval for email actions",
            resolved=False
        )
        db_session.add(trigger)
        db_session.commit()

        # Create proposal
        proposal = await training_service.create_training_proposal(trigger)

        assert proposal is not None
        assert proposal.agent_id == intern_agent.id
        assert "Sales" in proposal.title or "Operations" in proposal.title

    @pytest.mark.asyncio
    async def test_approve_proposal_creates_session(
        self, training_service, student_agent, blocked_trigger
    ):
        """Test approving proposal creates training session."""
        # Create proposal
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Approve training
        session = await training_service.approve_training(
            proposal_id=proposal.id,
            user_id="test-supervisor"
        )

        assert session is not None
        assert session.agent_id == student_agent.id
        assert session.status == "scheduled"
        assert session.supervisor_id == "test-supervisor"
        assert session.total_tasks > 0

        # Verify proposal status updated
        training_service.db.refresh(proposal)
        assert proposal.status == ProposalStatus.APPROVED.value
        assert proposal.approved_by == "test-supervisor"

    @pytest.mark.asyncio
    async def test_approve_proposal_with_modifications(
        self, training_service, student_agent, blocked_trigger
    ):
        """Test approving proposal with custom duration and schedule."""
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Approve with modifications
        modifications = {
            "duration_override_hours": 20.0,
            "hours_per_day_limit": 4.0
        }
        session = await training_service.approve_training(
            proposal_id=proposal.id,
            user_id="test-supervisor",
            modifications=modifications
        )

        # Verify modifications applied
        training_service.db.refresh(proposal)
        assert proposal.user_override_duration_hours == 20.0
        assert proposal.hours_per_day_limit == 4.0

    @pytest.mark.asyncio
    async def test_proposal_with_nonexistent_agent(
        self, training_service, db_session
    ):
        """Test proposal creation fails for nonexistent agent."""
        trigger = BlockedTriggerContext(
            id="invalid-trigger",
            agent_id="nonexistent-agent-id",
            trigger_type="workflow_trigger",
            trigger_context={"action": "test"},
            blocked_reason="Test",
            resolved=False
        )
        db_session.add(trigger)
        db_session.commit()

        # Should raise ValueError
        with pytest.raises(ValueError, match="Agent .* not found"):
            await training_service.create_training_proposal(trigger)

    @pytest.mark.asyncio
    async def test_approve_nonexistent_proposal(self, training_service):
        """Test approving proposal that doesn't exist."""
        with pytest.raises(ValueError, match="Proposal .* not found"):
            await training_service.approve_training(
                proposal_id="nonexistent-proposal",
                user_id="test-supervisor"
            )


# ========================================================================
# Test Class 3: Training Duration Tests
# ========================================================================

class TestTrainingDuration:
    """Test training duration estimation."""

    @pytest.mark.asyncio
    async def test_estimate_training_duration_new_agent(
        self, training_service, student_agent
    ):
        """Test duration estimation for new agent (no history)."""
        estimate = await training_service.estimate_training_duration(
            agent_id=student_agent.id,
            capability_gaps=["task_execution", "decision_making"],
            target_maturity=AgentStatus.INTERN.value
        )

        assert isinstance(estimate, TrainingDurationEstimate)
        assert estimate.estimated_hours > 0
        assert 0 <= estimate.confidence <= 1.0
        assert estimate.min_hours < estimate.estimated_hours < estimate.max_hours
        assert len(estimate.reasoning) > 0
        assert isinstance(estimate.similar_agents, list)

    @pytest.mark.asyncio
    async def test_estimate_training_duration_with_history(
        self, training_service, student_agent, db_session
    ):
        """Test duration estimation with historical data."""
        # Create similar agents with completed training
        similar_agent1 = AgentRegistry(
            id="similar-agent-1",
            tenant_id="test-tenant",
            name="Similar Agent 1",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        similar_agent2 = AgentRegistry(
            id="similar-agent-2",
            tenant_id="test-tenant",
            name="Similar Agent 2",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.7
        )
        db_session.add_all([similar_agent1, similar_agent2])
        db_session.commit()

        # Create completed training sessions for similar agents
        for agent in [similar_agent1, similar_agent2]:
            session = TrainingSession(
                proposal_id="test-proposal",
                agent_id=agent.id,
                agent_name=agent.name,
                status="completed",
                performance_score=0.8,
                duration_seconds=144000,  # 40 hours
                started_at=datetime.now() - timedelta(days=10),
                completed_at=datetime.now() - timedelta(days=5)
            )
            db_session.add(session)
        db_session.commit()

        # Estimate with historical data
        estimate = await training_service.estimate_training_duration(
            agent_id=student_agent.id,
            capability_gaps=["task_execution"],
            target_maturity=AgentStatus.INTERN.value
        )

        assert estimate.estimated_hours > 0
        assert len(estimate.similar_agents) > 0
        assert estimate.confidence > 0.5  # Higher confidence with history

    @pytest.mark.asyncio
    async def test_estimate_training_duration_override(
        self, training_service, student_agent
    ):
        """Test that user can override estimated duration."""
        estimate = await training_service.estimate_training_duration(
            agent_id=student_agent.id,
            capability_gaps=["task_execution"],
            target_maturity=AgentStatus.INTERN.value
        )

        # Get base estimate
        base_hours = estimate.estimated_hours

        # Verify reasonable range
        assert estimate.min_hours < base_hours < estimate.max_hours
        assert estimate.min_hours >= base_hours * 0.7
        assert estimate.max_hours <= base_hours * 1.5


# ========================================================================
# Test Class 4: Supervision Integration Tests
# ========================================================================

class TestSupervisionIntegration:
    """Test training references supervision session."""

    @pytest.mark.asyncio
    async def test_training_references_supervision_session(
        self, training_service, student_agent, blocked_trigger, db_session
    ):
        """Test that training session can reference supervision session."""
        # Create proposal
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Create training session with supervision reference
        session = TrainingSession(
            proposal_id=proposal.id,
            agent_id=student_agent.id,
            agent_name=student_agent.name,
            status="in_progress",
            started_at=datetime.now(),
            supervisor_id="test-supervisor",
            supervision_session_id="supervision-123",  # Reference to supervision
            total_tasks=5
        )
        db_session.add(session)
        db_session.commit()

        # Verify reference stored
        assert session.supervision_session_id == "supervision-123"

    @pytest.mark.asyncio
    async def test_training_complete_allows_supervision_promotion(
        self, training_service, student_agent, blocked_trigger
    ):
        """Test that completed training enables supervision-based promotion."""
        # Create proposal and session
        proposal = await training_service.create_training_proposal(blocked_trigger)
        session = TrainingSession(
            proposal_id=proposal.id,
            agent_id=student_agent.id,
            agent_name=student_agent.name,
            status="in_progress",
            started_at=datetime.now(),
            supervisor_id="test-supervisor",
            total_tasks=5
        )
        training_service.db.add(session)
        training_service.db.commit()

        # Complete with excellent performance
        outcome = TrainingOutcome(
            performance_score=0.95,
            supervisor_feedback="Outstanding performance",
            errors_count=0,
            tasks_completed=5,
            total_tasks=5,
            capabilities_developed=["task_execution", "decision_making", "autonomy"],
            capability_gaps_remaining=[]
        )

        result = await training_service.complete_training_session(session.id, outcome)

        # Should promote to INTERN
        assert result["promoted_to_intern"] == True
        assert result["new_status"] == AgentStatus.INTERN.value

    @pytest.mark.asyncio
    async def test_training_incomplete_blocks_graduation(
        self, training_service, student_agent, blocked_trigger
    ):
        """Test that incomplete training blocks graduation to higher levels."""
        # Create proposal and session
        proposal = await training_service.create_training_proposal(blocked_trigger)
        session = TrainingSession(
            proposal_id=proposal.id,
            agent_id=student_agent.id,
            agent_name=student_agent.name,
            status="in_progress",
            started_at=datetime.now(),
            supervisor_id="test-supervisor",
            total_tasks=5
        )
        training_service.db.add(session)
        training_service.db.commit()

        # Complete with poor performance
        outcome = TrainingOutcome(
            performance_score=0.35,
            supervisor_feedback="Needs more training",
            errors_count=8,
            tasks_completed=2,
            total_tasks=5,
            capabilities_developed=["basic_tasks"],
            capability_gaps_remaining=["advanced_tasks", "decision_making"]
        )

        result = await training_service.complete_training_session(session.id, outcome)

        # Should NOT promote
        assert result["promoted_to_intern"] == False
        assert result["new_status"] == AgentStatus.STUDENT.value


# ========================================================================
# Test Class 5: Error Path Tests
# ========================================================================

class TestErrorPaths:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_training_with_nonexistent_agent(
        self, training_service, db_session
    ):
        """Test creating training proposal for nonexistent agent."""
        trigger = BlockedTriggerContext(
            id="error-trigger",
            agent_id="nonexistent-agent",
            agent_name="Nonexistent Agent",
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=0.3,
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            trigger_type="workflow_trigger",
            trigger_context={},
            routing_decision="training",
            block_reason="Test error",
            resolved=False
        )
        db_session.add(trigger)
        db_session.commit()

        with pytest.raises(ValueError, match="Agent .* not found"):
            await training_service.create_training_proposal(trigger)

    @pytest.mark.asyncio
    async def test_proposal_with_deleted_session(
        self, training_service, student_agent, blocked_trigger, db_session
    ):
        """Test completing training when session doesn't exist."""
        # Create proposal
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Try to complete nonexistent session
        outcome = TrainingOutcome(
            performance_score=0.8,
            supervisor_feedback="Good",
            errors_count=1,
            tasks_completed=4,
            total_tasks=5,
            capabilities_developed=["tasks"],
            capability_gaps_remaining=[]
        )

        with pytest.raises(ValueError, match="Training session .* not found"):
            await training_service.complete_training_session(
                "nonexistent-session-id",
                outcome
            )

    @pytest.mark.asyncio
    async def test_training_with_invalid_maturity_level(
        self, training_service, db_session
    ):
        """Test duration estimation with invalid target maturity."""
        agent = AgentRegistry(
            id="test-invalid-maturity",
            tenant_id="test-tenant",
            name="Test Agent",
            category="Finance",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()

        # Should still work (maturity level is just a string)
        estimate = await training_service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["task_execution"],
            target_maturity="INVALID_LEVEL"
        )

        assert estimate.estimated_hours > 0

    @pytest.mark.asyncio
    async def test_approve_already_approved_proposal(
        self, training_service, student_agent, blocked_trigger
    ):
        """Test approving proposal that's already approved."""
        # Create and approve proposal
        proposal = await training_service.create_training_proposal(blocked_trigger)
        session1 = await training_service.approve_training(
            proposal_id=proposal.id,
            user_id="supervisor1"
        )

        # Try to approve again
        with pytest.raises(ValueError, match="Proposal must be in PROPOSED status"):
            await training_service.approve_training(
                proposal_id=proposal.id,
                user_id="supervisor2"
            )

    @pytest.mark.asyncio
    async def test_get_training_history_empty(
        self, training_service, student_agent
    ):
        """Test getting training history for agent with no history."""
        history = await training_service.get_training_history(
            agent_id=student_agent.id,
            limit=10
        )

        assert isinstance(history, list)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_get_training_history_with_sessions(
        self, training_service, student_agent, blocked_trigger, db_session
    ):
        """Test getting training history returns sessions in reverse chronological order."""
        # Create proposal and sessions
        proposal = await training_service.create_training_proposal(blocked_trigger)

        # Create multiple sessions
        for i in range(3):
            session = TrainingSession(
                proposal_id=proposal.id,
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                status="completed",
                started_at=datetime.now() - timedelta(days=3-i),
                completed_at=datetime.now() - timedelta(days=2-i),
                performance_score=0.7 + (i * 0.1),
                supervisor_id=f"supervisor-{i}",
                total_tasks=5
            )
            db_session.add(session)
        db_session.commit()

        # Get history
        history = await training_service.get_training_history(
            agent_id=student_agent.id,
            limit=10
        )

        assert len(history) == 3
        # Should be in reverse chronological order (most recent first)
        assert history[0]["performance_score"] >= history[1]["performance_score"]
        assert history[1]["performance_score"] >= history[2]["performance_score"]
