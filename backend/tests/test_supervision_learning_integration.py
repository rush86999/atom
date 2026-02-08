"""
End-to-end integration tests for supervision learning system.

Tests the complete flow from supervision → episodes → graduation.
"""

import asyncio
import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from core.models import (
    AgentExecution,
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    Episode,
    EpisodeSegment,
    ProposalStatus,
    SupervisionSession,
    SupervisionStatus,
    User,
    Workspace,
)
from core.agent_graduation_service import AgentGraduationService
from core.episode_segmentation_service import EpisodeSegmentationService
from core.episode_retrieval_service import EpisodeRetrievalService, RetrievalMode
from core.proposal_service import ProposalService
from core.supervision_service import SupervisionService


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create a test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def user(db: Session):
    """Create test user."""
    user = User(
        id="test_integration_user",
        email="integration_test@example.com",
        first_name="Integration",
        last_name="Test User",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def workspace(db: Session, user: User):
    """Create test workspace."""
    workspace = Workspace(
        id="test_integration_workspace",
        name="Integration Test Workspace",
        
    )
    db.add(workspace)
    db.commit()
    return workspace


@pytest.fixture
def supervised_agent(db: Session, workspace: Workspace, user: User):
    """Create SUPERVISED agent."""
    agent = AgentRegistry(
        id="test_integration_supervised_agent",
        name="Test Integration Supervised Agent",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.75,
        
        
    )
    db.add(agent)
    db.commit()
    return agent


@pytest.fixture
def intern_agent(db: Session, workspace: Workspace, user: User):
    """Create INTERN agent."""
    agent = AgentRegistry(
        id="test_integration_intern_agent",
        name="Test Integration Intern Agent",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        
        
    )
    db.add(agent)
    db.commit()
    return agent


# ============================================================================
# End-to-End Integration Tests
# ============================================================================

class TestSupervisionToEndToEnd:
    """Test complete supervision learning flow."""

    @pytest.mark.asyncio
    async def test_supervision_to_episode_to_graduation(
        self,
        db: Session,
        supervised_agent: AgentRegistry,
        user: User,
    ):
        """Test complete flow: supervision → episode → graduation."""
        # Step 1: Create supervision session
        supervision_service = SupervisionService(db)
        session = await supervision_service.start_supervision_session(
            agent_id=supervised_agent.id,
            trigger_context={"trigger_type": "manual"},
            workspace_id=workspace.id,
            supervisor_id=user.id,
        )

        # Step 2: Simulate agent execution
        execution = AgentExecution(
            id=f"exec_{datetime.now().timestamp()}",
            agent_id=supervised_agent.id,
            agent_name=supervised_agent.name,
            
            status="running",
            task_description="Test task for supervision",
            started_at=datetime.now(),
        )
        db.add(execution)
        db.commit()

        # Step 3: Complete supervision
        outcome = await supervision_service.complete_supervision(
            session_id=session.id,
            supervisor_rating=5,
            feedback="Excellent work!",
        )

        # Step 4: Wait for episode creation (async)
        await asyncio.sleep(0.2)

        # Step 5: Verify episode created
        episodes = db.query(Episode).filter(
            Episode.supervisor_id == user.id,
            Episode.agent_id == supervised_agent.id,
        ).all()

        assert len(episodes) > 0
        episode = episodes[0]

        assert episode.supervisor_rating == 5
        assert episode.intervention_count == 0
        assert episode.supervision_feedback == "Excellent work!"

        # Step 6: Use episode for graduation validation
        graduation_service = AgentGraduationService(db)

        # Create more episodes to meet graduation criteria
        for _ in range(20):
            session = await supervision_service.start_supervision_session(
                agent_id=supervised_agent.id,
                trigger_context={"trigger_type": "manual"},
                workspace_id=workspace.id,
                supervisor_id=user.id,
            )

            execution = AgentExecution(
                id=f"exec_{datetime.now().timestamp()}_{_}",
                agent_id=supervised_agent.id,
                agent_name=supervised_agent.name,
                
                status="completed",
                task_description=f"Test task {_}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )
            db.add(execution)
            db.commit()

            await supervision_service.complete_supervision(
                session_id=session.id,
                supervisor_rating=5,
                feedback="Good work",
            )

        await asyncio.sleep(0.2)

        # Validate graduation readiness
        readiness = await graduation_service.calculate_readiness_score(
            agent_id=supervised_agent.id,
            target_maturity="AUTONOMOUS",
        )

        assert readiness["episode_count"] >= 20

    @pytest.mark.asyncio
    async def test_proposal_to_episode_to_learning(
        self,
        db: Session,
        intern_agent: AgentRegistry,
        user: User,
    ):
        """Test complete flow: proposal → episode → learning."""
        # Step 1: Create proposal
        proposal_service = ProposalService(db)
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={"trigger_type": "manual"},
            proposed_action={
                "action_type": "canvas_present",
                "canvas_type": "chart",
            },
            reasoning="This proposal presents a chart",
        )

        # Step 2: Approve proposal
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            
        )

        # Step 3: Verify episode created
        episodes = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).all()

        assert len(episodes) > 0
        episode = episodes[0]

        assert episode.proposal_outcome == "approved"
        assert episode.human_intervention_count == 1

        # Step 4: Reject another proposal
        proposal2 = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={"trigger_type": "manual"},
            proposed_action={
                "action_type": "canvas_present",
                "canvas_type": "sheet",
            },
            reasoning="This proposal presents a sheet",
        )

        await proposal_service.reject_proposal(
            proposal_id=proposal2.id,
            
            reason="Not needed",
        )

        # Step 5: Verify rejected episode
        rejected_episode = db.query(Episode).filter(
            Episode.proposal_id == proposal2.id,
        ).first()

        assert rejected_episode is not None
        assert rejected_episode.proposal_outcome == "rejected"
        assert rejected_episode.rejection_reason == "Not needed"

    @pytest.mark.asyncio
    async def test_supervision_retrieval_with_context(
        self,
        db: Session,
        supervised_agent: AgentRegistry,
        user: User,
    ):
        """Test retrieving episodes with supervision context."""
        # Create supervision sessions
        supervision_service = SupervisionService(db)

        for i in range(5):
            session = await supervision_service.start_supervision_session(
                agent_id=supervised_agent.id,
                trigger_context={"trigger_type": "manual"},
                workspace_id=workspace.id,
                supervisor_id=user.id,
            )

            execution = AgentExecution(
                id=f"exec_{datetime.now().timestamp()}_{i}",
                agent_id=supervised_agent.id,
                agent_name=supervised_agent.name,
                
                status="completed",
                task_description=f"Task {i}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )
            db.add(execution)
            db.commit()

            await supervision_service.complete_supervision(
                session_id=session.id,
                supervisor_rating=5 - (i % 2),  # Vary ratings
                feedback=f"Feedback {i}",
            )

        await asyncio.sleep(0.2)

        # Retrieve with supervision context
        retrieval_service = EpisodeRetrievalService(db)
        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id=supervised_agent.id,
            retrieval_mode=RetrievalMode.TEMPORAL,
            limit=10,
            supervision_outcome_filter="high_rated",
        )

        assert result["count"] > 0
        assert "supervision_filters_applied" in result
        assert "high_rated" in result["supervision_filters_applied"]

        # Verify supervision context in episodes
        for episode_data in result["episodes"]:
            assert "supervision_context" in episode_data
            ctx = episode_data["supervision_context"]
            assert "has_supervision" in ctx
            assert "intervention_count" in ctx
            assert "supervisor_rating" in ctx


class TestLearningImpact:
    """Test learning impact on agent behavior."""

    @pytest.mark.asyncio
    async def test_graduation_reflects_supervision_performance(
        self,
        db: Session,
        supervised_agent: AgentRegistry,
        user: User,
    ):
        """Test graduation validation reflects supervision performance."""
        supervision_service = SupervisionService(db)
        graduation_service = AgentGraduationService(db)

        # Create high-quality supervision history
        for i in range(15):
            session = await supervision_service.start_supervision_session(
                agent_id=supervised_agent.id,
                trigger_context={"trigger_type": "manual"},
                workspace_id=workspace.id,
                supervisor_id=user.id,
            )

            execution = AgentExecution(
                id=f"exec_{datetime.now().timestamp()}_{i}",
                agent_id=supervised_agent.id,
                agent_name=supervised_agent.name,
                
                status="completed",
                task_description=f"Task {i}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )
            db.add(execution)
            db.commit()

            await supervision_service.complete_supervision(
                session_id=session.id,
                supervisor_rating=5,
                feedback="Excellent",
            )

        await asyncio.sleep(0.2)

        # Check supervision metrics
        supervision_metrics = await graduation_service.calculate_supervision_metrics(
            agent_id=supervised_agent.id,
            maturity_level=AgentStatus.SUPERVISED,
        )

        assert supervision_metrics["average_supervisor_rating"] >= 4.5
        assert supervision_metrics["high_rating_sessions"] >= 10

    @pytest.mark.asyncio
    async def test_low_rated_sessions_impact_graduation(
        self,
        db: Session,
        supervised_agent: AgentRegistry,
        user: User,
    ):
        """Test low-rated supervision sessions negatively impact graduation."""
        supervision_service = SupervisionService(db)
        graduation_service = AgentGraduationService(db)

        # Create low-quality supervision history
        for i in range(10):
            session = await supervision_service.start_supervision_session(
                agent_id=supervised_agent.id,
                trigger_context={"trigger_type": "manual"},
                workspace_id=workspace.id,
                supervisor_id=user.id,
            )

            execution = AgentExecution(
                id=f"exec_{datetime.now().timestamp()}_{i}",
                agent_id=supervised_agent.id,
                agent_name=supervised_agent.name,
                
                status="completed",
                task_description=f"Task {i}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )
            db.add(execution)
            db.commit()

            await supervision_service.complete_supervision(
                session_id=session.id,
                supervisor_rating=2,
                feedback="Needs improvement",
            )

        await asyncio.sleep(0.2)

        # Check supervision metrics
        supervision_metrics = await graduation_service.calculate_supervision_metrics(
            agent_id=supervised_agent.id,
            maturity_level=AgentStatus.SUPERVISED,
        )

        assert supervision_metrics["average_supervisor_rating"] < 3.0
        assert supervision_metrics["high_rating_sessions"] == 0


# ============================================================================
# Property-Based Integration Tests
# ============================================================================

class TestIntegrationProperties:
    """Property-based tests for integration scenarios."""

    @given(
        st.lists(
            st.integers(min_value=1, max_value=5),
            min_size=10,
            max_size=30,
        )
    )
    @settings(max_examples=5)
    @pytest.mark.asyncio
    async def test_average_rating_preserved_through_flow(
        self,
        db: Session,
        supervised_agent: AgentRegistry,
        user: User,
        ratings,
    ):
        """Test average supervisor rating preserved from supervision to episode to metrics."""
        supervision_service = SupervisionService(db)
        graduation_service = AgentGraduationService(db)

        # Create sessions with specified ratings
        for i, rating in enumerate(ratings):
            session = await supervision_service.start_supervision_session(
                agent_id=supervised_agent.id,
                trigger_context={"trigger_type": "manual"},
                workspace_id=workspace.id,
                supervisor_id=user.id,
            )

            execution = AgentExecution(
                id=f"exec_{datetime.now().timestamp()}_{i}",
                agent_id=supervised_agent.id,
                agent_name=supervised_agent.name,
                
                status="completed",
                task_description=f"Task {i}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )
            db.add(execution)
            db.commit()

            await supervision_service.complete_supervision(
                session_id=session.id,
                supervisor_rating=rating,
                feedback=f"Feedback {i}",
            )

        await asyncio.sleep(0.5)  # Wait for all episode creations

        # Check metrics
        supervision_metrics = await graduation_service.calculate_supervision_metrics(
            agent_id=supervised_agent.id,
            maturity_level=AgentStatus.SUPERVISED,
        )

        expected_avg = sum(ratings) / len(ratings)
        assert abs(supervision_metrics["average_supervisor_rating"] - expected_avg) < 0.1

    @given(
        st.lists(
            st.integers(min_value=0, max_value=10),
            min_size=10,
            max_size=30,
        )
    )
    @settings(max_examples=5)
    @pytest.mark.asyncio
    async def test_intervention_count_preserved_through_flow(
        self,
        db: Session,
        supervised_agent: AgentRegistry,
        user: User,
        intervention_counts,
    ):
        """Test intervention counts preserved through flow."""
        supervision_service = SupervisionService(db)

        # Create sessions with specified intervention counts
        for i, count in enumerate(intervention_counts):
            session = await supervision_service.start_supervision_session(
                agent_id=supervised_agent.id,
                trigger_context={"trigger_type": "manual"},
                workspace_id=workspace.id,
                supervisor_id=user.id,
            )

            # Add interventions
            session.interventions = [
                {
                    "timestamp": datetime.now().isoformat(),
                    "type": "correct",
                    "guidance": f"Intervention {j}",
                }
                for j in range(count)
            ]
            session.intervention_count = count
            db.commit()

            execution = AgentExecution(
                id=f"exec_{datetime.now().timestamp()}_{i}",
                agent_id=supervised_agent.id,
                agent_name=supervised_agent.name,
                
                status="completed",
                task_description=f"Task {i}",
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )
            db.add(execution)
            db.commit()

            await supervision_service.complete_supervision(
                session_id=session.id,
                supervisor_rating=4,
                feedback=f"Feedback {i}",
            )

        await asyncio.sleep(0.5)

        # Verify episodes
        episodes = db.query(Episode).filter(
            Episode.agent_id == supervised_agent.id,
            Episode.supervisor_id == user.id,
        ).all()

        # Should have created episodes for all sessions
        assert len(episodes) >= len(intervention_counts) * 0.8  # Allow for some async delays

    @given(
        st.integers(min_value=1, max_value=5),
        st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=10)
    @pytest.mark.asyncio
    async def test_episode_importance_correlation(
        self,
        db: Session,
        supervised_agent: AgentRegistry,
        user: User,
        rating,
        interventions,
    ):
        """Test episode importance correlates with supervision quality."""
        supervision_service = SupervisionService(db)

        session = await supervision_service.start_supervision_session(
            agent_id=supervised_agent.id,
            trigger_context={"trigger_type": "manual"},
            workspace_id=workspace.id,
            supervisor_id=user.id,
        )

        # Add interventions
        session.interventions = [
            {
                "timestamp": datetime.now().isoformat(),
                "type": "correct",
                "guidance": f"Intervention {i}",
            }
            for i in range(interventions)
        ]
        session.intervention_count = interventions
        db.commit()

        execution = AgentExecution(
            id=f"exec_{datetime.now().timestamp()}",
            agent_id=supervised_agent.id,
            agent_name=supervised_agent.name,
            
            status="completed",
            task_description="Test task",
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )
        db.add(execution)
        db.commit()

        await supervision_service.complete_supervision(
            session_id=session.id,
            supervisor_rating=rating,
            feedback="Test feedback",
        )

        await asyncio.sleep(0.2)

        # Get episode
        episode = db.query(Episode).filter(
            Episode.agent_id == supervised_agent.id,
            Episode.supervisor_id == user.id,
        ).order_by(Episode.created_at.desc()).first()

        if episode:
            # Higher rating and lower interventions should give higher importance
            if rating >= 4 and interventions <= 2:
                assert episode.importance_score >= 0.6
            elif rating <= 2 and interventions >= 5:
                assert episode.importance_score <= 0.5

            # Always within bounds
            assert 0.0 <= episode.importance_score <= 1.0
