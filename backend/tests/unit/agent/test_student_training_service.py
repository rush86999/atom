"""
Unit Tests for Student Training Service

Tests cover:
- STUDENT agents blocked from automated triggers
- Routing to training scenarios
- Training session creation
- Graduation from training
"""
import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from core.student_training_service import StudentTrainingService, TrainingOutcome
from core.trigger_interceptor import TriggerInterceptor
from core.models import AgentRegistry, AgentStatus, BlockedTriggerContext, TrainingSession, AgentProposal
from tests.factories import (
    StudentAgentFactory,
    BlockedTriggerContextFactory
)


class TestStudentTrainingService:
    """Test STUDENT agent training service."""

    @pytest.fixture
    def training_service(self, db_session):
        """Create training service."""
        return StudentTrainingService(db_session)

    @pytest.fixture
    def interceptor(self, db_session):
        """Create trigger interceptor."""
        return TriggerInterceptor(db_session, workspace_id="test_workspace")

    @pytest.mark.asyncio
    async def test_student_blocked_from_automated_triggers(self, interceptor, db_session):
        """STUDENT agents should be blocked from automated triggers."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Try to execute action via trigger
        from core.trigger_interceptor import TriggerSource
        result = await interceptor.intercept_trigger(
            agent_id=agent.id,
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            trigger_context={"action_type": "agent_message", "data": "test"},
            user_id=None
        )

        # Should block and route to training
        assert result.execute is False
        assert result.routing_decision in ["training", "proposal"]

    @pytest.mark.asyncio
    async def test_training_proposal_creation(self, training_service, db_session):
        """Training proposals should be created for STUDENT agents."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Create a blocked trigger manually to avoid factory issues
        from core.models import BlockedTriggerContext
        import uuid
        blocked_trigger = BlockedTriggerContext(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block="STUDENT",
            confidence_score_at_block=agent.confidence_score,
            trigger_source="WORKFLOW_ENGINE",
            trigger_type="workflow_trigger",
            trigger_context={"test": "data"},
            routing_decision="training",
            block_reason="Test block for training"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        # Create training proposal
        proposal = await training_service.create_training_proposal(blocked_trigger)

        assert proposal.agent_id == agent.id
        assert proposal.status == "proposed"
        assert proposal.proposal_type == "training"
        assert proposal.estimated_duration_hours > 0
        assert len(proposal.capability_gaps) > 0
        assert len(proposal.learning_objectives) > 0

    @pytest.mark.asyncio
    async def test_training_session_creation(self, training_service, db_session):
        """Training sessions should be created for STUDENT agents."""
        import uuid
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Create a proposal with all required fields
        proposal = AgentProposal(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            agent_name=agent.name,
            proposal_type="training",
            title="Training Proposal",
            description="Test training",
            status="proposed",
            proposed_by="atom_meta_agent",
            learning_objectives=["obj1", "obj2"],
            capability_gaps=["gap1", "gap2"],
            estimated_duration_hours=10.0
        )
        db_session.add(proposal)
        db_session.commit()

        # Approve training
        session = await training_service.approve_training(
            proposal_id=proposal.id,
            user_id="test_user"
        )

        assert session.agent_id == agent.id
        assert session.status == "scheduled"
        assert session.supervisor_id == "test_user"
        assert session.total_tasks == 2

    @pytest.mark.asyncio
    async def test_training_completion_increases_confidence(self, training_service, db_session):
        """Training completion should increase agent confidence."""
        import uuid
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.3)
        db_session.commit()

        # Create a completed training session
        proposal = AgentProposal(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            agent_name=agent.name,
            proposal_type="training",
            title="Training Proposal",
            description="Test training",
            status="approved",
            proposed_by="atom_meta_agent"
        )
        db_session.add(proposal)

        session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id=proposal.id,
            agent_id=agent.id,
            agent_name=agent.name,
            status="in_progress",
            supervisor_id="test_user",
            started_at=datetime.now()
        )
        db_session.add(session)
        db_session.commit()

        # Complete training with good performance
        outcome = TrainingOutcome(
            performance_score=0.8,
            supervisor_feedback="Good progress",
            errors_count=2,
            tasks_completed=8,
            total_tasks=10,
            capabilities_developed=["task_execution", "context_understanding"],
            capability_gaps_remaining=[]
        )

        result = await training_service.complete_training_session(
            session_id=session.id,
            outcome=outcome
        )

        assert result["agent_id"] == agent.id
        assert result["performance_score"] == 0.8
        assert result["confidence_boost"] > 0
        assert result["new_confidence"] > result["old_confidence"]

    @pytest.mark.asyncio
    async def test_training_completion_promotes_to_intern(self, training_service, db_session):
        """Training completion should promote to INTERN if confidence >= 0.5."""
        import uuid
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.45)
        db_session.commit()

        # Create a completed training session
        proposal = AgentProposal(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            agent_name=agent.name,
            proposal_type="training",
            title="Training Proposal",
            description="Test training",
            status="approved",
            proposed_by="atom_meta_agent"
        )
        db_session.add(proposal)

        session = TrainingSession(
            id=str(uuid.uuid4()),
            proposal_id=proposal.id,
            agent_id=agent.id,
            agent_name=agent.name,
            status="in_progress",
            supervisor_id="test_user",
            started_at=datetime.now()
        )
        db_session.add(session)
        db_session.commit()

        # Complete training with excellent performance (should boost to >= 0.5)
        outcome = TrainingOutcome(
            performance_score=0.95,
            supervisor_feedback="Excellent work",
            errors_count=0,
            tasks_completed=10,
            total_tasks=10,
            capabilities_developed=["task_execution", "decision_making"],
            capability_gaps_remaining=[]
        )

        result = await training_service.complete_training_session(
            session_id=session.id,
            outcome=outcome
        )

        assert result["promoted_to_intern"] is True
        assert result["new_status"] == "intern"

    @pytest.mark.asyncio
    async def test_training_duration_estimation(self, training_service, db_session):
        """Training duration should be estimated based on multiple factors."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.3, category="Finance")

        # Estimate training duration
        estimate = await training_service.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=["workflow_automation", "decision_making"],
            target_maturity="INTERN"
        )

        assert estimate.estimated_hours > 0
        assert estimate.confidence > 0
        assert estimate.min_hours <= estimate.estimated_hours <= estimate.max_hours
        assert len(estimate.reasoning) > 0
        assert 0.0 <= estimate.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_training_history_retrieval(self, training_service, db_session):
        """Training history should be retrievable for an agent."""
        import uuid
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Create completed training sessions
        for i in range(5):
            proposal = AgentProposal(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                agent_name=agent.name,
                proposal_type="training",
                title=f"Training {i}",
                description="Test training",
                status="executed",
                proposed_by="atom_meta_agent"
            )
            db_session.add(proposal)

            session = TrainingSession(
                id=str(uuid.uuid4()),
                proposal_id=proposal.id,
                agent_id=agent.id,
                agent_name=agent.name,
                status="completed",
                supervisor_id="test_user",
                started_at=datetime.now(),
                completed_at=datetime.now(),
                duration_seconds=3600,
                performance_score=0.7 + (i * 0.05)
            )
            db_session.add(session)
        db_session.commit()

        # Get training history
        history = await training_service.get_training_history(agent_id=agent.id)

        assert len(history) == 5
        assert all("session_id" in h for h in history)
        assert all("performance_score" in h for h in history)

    @pytest.mark.asyncio
    async def test_capability_gap_identification(self, training_service, db_session):
        """Capability gaps should be identified from blocked triggers."""
        import uuid
        from core.models import BlockedTriggerContext
        agent = StudentAgentFactory(_session=db_session, category="Finance")
        db_session.commit()

        # Create blocked trigger manually
        blocked_trigger = BlockedTriggerContext(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block="STUDENT",
            confidence_score_at_block=agent.confidence_score,
            trigger_source="WORKFLOW_ENGINE",
            trigger_type="workflow_trigger",
            trigger_context={"category": "Finance"},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        # Identify capability gaps
        gaps = await training_service._identify_capability_gaps(agent, blocked_trigger)

        assert len(gaps) > 0
        assert isinstance(gaps, list)
        # Should include workflow-related gaps
        assert any("workflow" in gap.lower() for gap in gaps)

    @pytest.mark.asyncio
    async def test_learning_objectives_generation(self, training_service, db_session):
        """Learning objectives should be generated for training proposals."""
        import uuid
        from core.models import BlockedTriggerContext
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Create blocked trigger manually
        blocked_trigger = BlockedTriggerContext(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            agent_name=agent.name,
            agent_maturity_at_block="STUDENT",
            confidence_score_at_block=agent.confidence_score,
            trigger_source="WORKFLOW_ENGINE",
            trigger_type="form_submit",
            trigger_context={},
            routing_decision="training",
            block_reason="Test block"
        )
        db_session.add(blocked_trigger)
        db_session.commit()

        # Generate learning objectives
        objectives = await training_service._generate_learning_objectives(
            agent,
            blocked_trigger,
            ["data_validation", "form_processing"]
        )

        assert len(objectives) > 0
        assert all(isinstance(obj, str) for obj in objectives)
        # Should include base objectives
        assert any("form_submit" in obj for obj in objectives)

    @pytest.mark.asyncio
    async def test_confidence_boost_calculation(self, training_service):
        """Confidence boost should be calculated based on performance."""
        # Poor performance (< 0.3) -> 0.05 boost
        boost1 = training_service._calculate_confidence_boost(0.2)
        assert boost1 == 0.05

        # Below average (0.3-0.5) -> 0.10 boost
        boost2 = training_service._calculate_confidence_boost(0.4)
        assert boost2 == 0.10

        # Good performance (0.5-0.7) -> 0.15 boost
        boost3 = training_service._calculate_confidence_boost(0.6)
        assert boost3 == 0.15

        # Excellent performance (0.7-1.0) -> 0.20 boost
        boost4 = training_service._calculate_confidence_boost(0.9)
        assert boost4 == 0.20

    @pytest.mark.asyncio
    async def test_scenario_template_selection(self, training_service):
        """Scenario template should be selected based on trigger context."""
        from core.models import BlockedTriggerContext
        import uuid

        # Finance trigger
        blocked_trigger_finance = BlockedTriggerContext(
            id=str(uuid.uuid4()),
            agent_id="test-agent",
            agent_name="Test Agent",
            agent_maturity_at_block="STUDENT",
            confidence_score_at_block=0.5,
            trigger_type="workflow_trigger",
            trigger_context={"category": "Finance"},
            routing_decision="training",
            block_reason="Test"
        )

        template_finance = training_service._select_scenario_template(blocked_trigger_finance)
        assert template_finance == "Finance Fundamentals"

        # Sales trigger
        blocked_trigger_sales = BlockedTriggerContext(
            id=str(uuid.uuid4()),
            agent_id="test-agent",
            agent_name="Test Agent",
            agent_maturity_at_block="STUDENT",
            confidence_score_at_block=0.5,
            trigger_type="workflow_trigger",
            trigger_context={"category": "Sales"},
            routing_decision="training",
            block_reason="Test"
        )

        template_sales = training_service._select_scenario_template(blocked_trigger_sales)
        assert template_sales == "Sales Operations"

        # Unknown trigger -> default
        blocked_trigger_unknown = BlockedTriggerContext(
            id=str(uuid.uuid4()),
            agent_id="test-agent",
            agent_name="Test Agent",
            agent_maturity_at_block="STUDENT",
            confidence_score_at_block=0.5,
            trigger_type="unknown_trigger",
            trigger_context={},
            routing_decision="training",
            block_reason="Test"
        )

        template_unknown = training_service._select_scenario_template(blocked_trigger_unknown)
        assert template_unknown == "General Operations"
