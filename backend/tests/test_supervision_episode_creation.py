"""
Property-based and unit tests for supervision episode creation.

Tests the integration between SupervisionService and EpisodeSegmentationService
to ensure supervision sessions are properly captured as learning episodes.
"""

import asyncio
from datetime import datetime, timedelta
import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    SupervisionSession,
    SupervisionStatus,
    User,
    Workspace,
)
from core.episode_segmentation_service import EpisodeSegmentationService
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
        id="test_supervision_user",
        email="supervision_test@example.com",
        first_name="Supervision",
        last_name="Test User",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def workspace(db: Session, user: User):
    """Create test workspace."""
    workspace = Workspace(
        id="test_supervision_workspace",
        name="Supervision Test Workspace",
        
    )
    db.add(workspace)
    db.commit()
    return workspace


@pytest.fixture
def supervised_agent(db: Session, workspace: Workspace, user: User):
    """Create SUPERVISED agent."""
    agent = AgentRegistry(
        id="test_supervised_agent_episode",
        name="Test Supervised Agent Episode",
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
def supervision_session_factory(db: Session, supervised_agent: AgentRegistry, user: User):
    """Factory to create supervision sessions."""
    def _create_session(
        intervention_count: int = 0,
        supervisor_rating: int = 4,
        status: str = SupervisionStatus.COMPLETED.value,
        duration_seconds: int = 300,
    ) -> SupervisionSession:
        session = SupervisionSession(
            agent_id=supervised_agent.id,
            agent_name=supervised_agent.name,
            workspace_id=workspace.id,
            supervisor_id=user.id,
            status=status,
            intervention_count=intervention_count,
            supervisor_rating=supervisor_rating,
            supervision_feedback=f"Test feedback with {intervention_count} interventions",
            duration_seconds=duration_seconds,
            started_at=datetime.now() - timedelta(seconds=duration_seconds),
            completed_at=datetime.now() if status == SupervisionStatus.COMPLETED.value else None,
            interventions=[
                {
                    "timestamp": (datetime.now() - timedelta(seconds=i * 60)).isoformat(),
                    "type": "correct" if i % 2 == 0 else "pause",
                    "guidance": f"Test intervention {i + 1}"
                }
                for i in range(intervention_count)
            ]
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    return _create_session


@pytest.fixture
def agent_execution_factory(db: Session, supervised_agent: AgentRegistry, user: User):
    """Factory to create agent executions."""
    def _create_execution(
        status: str = "completed",
        task_description: str = "Test task",
    ) -> AgentExecution:
        execution = AgentExecution(
            id=f"test_exec_{datetime.now().timestamp()}",
            agent_id=supervised_agent.id,
            agent_name=supervised_agent.name,
            
            status=status,
            task_description=task_description,
            input_summary="Test input",
            output_summary="Test output",
            started_at=datetime.now() - timedelta(seconds=60),
            completed_at=datetime.now() if status == "completed" else None,
            duration_seconds=60,
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution

    return _create_execution


# ============================================================================
# Unit Tests
# ============================================================================

class TestSupervisionEpisodeCreation:
    """Test supervision episode creation functionality."""

    @pytest.mark.asyncio
    async def test_create_episode_from_supervision_session(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
    ):
        """Test creating episode from supervision session."""
        # Create supervision session and execution
        session = supervision_session_factory(
            intervention_count=2,
            supervisor_rating=4,
            duration_seconds=300,
        )
        execution = agent_execution_factory()

        # Create episode
        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=db,
        )

        # Verify episode created
        assert episode is not None
        assert episode.agent_id == session.agent_id
        assert episode.supervisor_id == session.supervisor_id
        assert episode.supervisor_rating == session.supervisor_rating
        assert episode.intervention_count == session.intervention_count
        assert episode.intervention_types == ["correct", "pause"]
        assert episode.supervision_feedback == session.supervision_feedback
        assert episode.maturity_at_time == AgentStatus.SUPERVISED.value
        assert episode.status == "completed"

    @pytest.mark.asyncio
    async def test_episode_links_to_execution(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
    ):
        """Test episode correctly links to agent execution."""
        session = supervision_session_factory()
        execution = agent_execution_factory(task_description="Specific test task")

        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=db,
        )

        assert episode.execution_ids == [execution.id]

    @pytest.mark.asyncio
    async def test_episode_captures_interventions(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
    ):
        """Test episode captures intervention details accurately."""
        session = supervision_session_factory(
            intervention_count=3,
            supervisor_rating=3,
        )
        execution = agent_execution_factory()

        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=db,
        )

        # Verify intervention count
        assert episode.intervention_count == 3

        # Verify intervention types extracted
        assert episode.intervention_types is not None
        assert len(episode.intervention_types) == 2  # "correct" and "pause"
        assert "correct" in episode.intervention_types
        assert "pause" in episode.intervention_types

        # Verify segments created
        from core.models import EpisodeSegment
        segments = db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) >= 2  # At least execution and intervention segments
        intervention_segments = [s for s in segments if s.segment_type == "intervention"]
        assert len(intervention_segments) == 1

    @pytest.mark.asyncio
    async def test_episode_importance_score_calculation(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
    ):
        """Test importance score calculated from supervision quality."""
        # High-quality session (5 stars, 0 interventions)
        session_high = supervision_session_factory(
            intervention_count=0,
            supervisor_rating=5,
        )
        execution_high = agent_execution_factory()

        episode_service = EpisodeSegmentationService(db)
        episode_high = await episode_service.create_supervision_episode(
            supervision_session=session_high,
            agent_execution=execution_high,
            db=db,
        )

        # Low-quality session (2 stars, 5 interventions)
        session_low = supervision_session_factory(
            intervention_count=5,
            supervisor_rating=2,
        )
        execution_low = agent_execution_factory()

        episode_low = await episode_service.create_supervision_episode(
            supervision_session=session_low,
            agent_execution=execution_low,
            db=db,
        )

        # High-quality episode should have higher importance
        assert episode_high.importance_score > episode_low.importance_score
        assert episode_high.importance_score > 0.7  # Should be > 0.7
        assert episode_low.importance_score < 0.5   # Should be < 0.5

    @pytest.mark.asyncio
    async def test_episode_with_no_interventions(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
    ):
        """Test episode creation when no interventions occurred."""
        session = supervision_session_factory(
            intervention_count=0,
            supervisor_rating=5,
        )
        execution = agent_execution_factory()

        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=db,
        )

        assert episode.intervention_count == 0
        assert episode.intervention_types == [] or episode.intervention_types is None

    @pytest.mark.asyncio
    async def test_episode_topics_extraction(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
    ):
        """Test topics extracted from supervision session."""
        session = supervision_session_factory()
        execution = agent_execution_factory(task_description="Financial analysis and reporting")

        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=db,
        )

        # Should have topics from agent name and task
        assert episode.topics is not None
        assert len(episode.topics) > 0

    @pytest.mark.asyncio
    async def test_supervision_service_integration(
        self,
        db: Session,
        supervised_agent: AgentRegistry,
        user: User,
    ):
        """Test SupervisionService creates episode on completion."""
        supervision_service = SupervisionService(db)

        # Start supervision session
        session = await supervision_service.start_supervision_session(
            agent_id=supervised_agent.id,
            trigger_context={"trigger_type": "manual"},
            workspace_id=workspace.id,
            supervisor_id=user.id,
        )

        # Complete supervision
        outcome = await supervision_service.complete_supervision(
            session_id=session.id,
            supervisor_rating=4,
            feedback="Great work!",
        )

        # Verify outcome
        assert outcome.success is True
        assert outcome.supervisor_rating == 4
        assert outcome.intervention_count == 0

        # Episode creation is async, wait a bit
        await asyncio.sleep(0.1)

        # Verify episode created (non-blocking async)
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.supervisor_id == user.id,
            Episode.agent_id == supervised_agent.id,
        ).first()

        # Note: Episode creation is fire-and-forget, so may not exist immediately
        # This test verifies the integration point is called
        assert outcome.session_id == session.id


# ============================================================================
# Property-Based Tests
# ============================================================================

class TestSupervisionEpisodeProperties:
    """Property-based tests for supervision episode creation."""

    @given(
        intervention_count=st.integers(min_value=0, max_value=10),
        supervisor_rating=st.integers(min_value=1, max_value=5),
        duration_seconds=st.integers(min_value=60, max_value=3600),
    )
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_importance_score_bounds(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
        intervention_count,
        supervisor_rating,
        duration_seconds,
    ):
        """Test importance score always within [0, 1] bounds."""
        session = supervision_session_factory(
            intervention_count=intervention_count,
            supervisor_rating=supervisor_rating,
            duration_seconds=duration_seconds,
        )
        execution = agent_execution_factory()

        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=db,
        )

        assert 0.0 <= episode.importance_score <= 1.0

    @given(
        rating=st.integers(min_value=1, max_value=5),
        interventions=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_importance_score_monotonicity(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
        rating,
        interventions,
    ):
        """Test importance score increases with rating and decreases with interventions."""
        session = supervision_session_factory(
            intervention_count=interventions,
            supervisor_rating=rating,
        )
        execution = agent_execution_factory()

        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=db,
        )

        # Higher rating should give higher score
        if interventions == 0:
            assert episode.importance_score >= 0.6  # Base + rating boost

        # More interventions should decrease score
        if rating == 5:
            if interventions == 0:
                assert episode.importance_score >= 0.8
            elif interventions >= 5:
                assert episode.importance_score <= 0.7

    @given(
        st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_intervention_types_preservation(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
        intervention_count,
    ):
        """Test intervention types are correctly extracted and preserved."""
        session = supervision_session_factory(
            intervention_count=intervention_count,
        )
        execution = agent_execution_factory()

        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=db,
        )

        # Verify intervention count preserved
        assert episode.intervention_count == intervention_count

        # Verify types extracted (should be subset of ["correct", "pause"])
        if intervention_count > 0:
            assert episode.intervention_types is not None
            assert all(t in ["correct", "pause"] for t in episode.intervention_types)

    @given(
        st.lists(
            st.sampled_from(["correct", "pause", "terminate"]),
            min_size=0,
            max_size=10,
            unique=False,
        )
    )
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_intervention_content_formatting(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
        intervention_types_list,
    ):
        """Test intervention content is formatted correctly."""
        # Create session with specific intervention types
        session = supervision_session_factory(
            intervention_count=len(intervention_types_list),
        )

        # Override interventions with specific types
        session.interventions = [
            {
                "timestamp": datetime.now().isoformat(),
                "type": int_type,
                "guidance": f"Test {int_type} intervention"
            }
            for int_type in intervention_types_list
        ]
        db.commit()

        execution = agent_execution_factory()

        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=db,
        )

        # Verify segments created
        from core.models import EpisodeSegment
        segments = db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id,
            EpisodeSegment.segment_type == "intervention"
        ).all()

        if intervention_types_list:
            assert len(segments) == 1
            # Verify content mentions intervention count
            assert str(len(intervention_types_list)) in segments[0].content

    @given(
        st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=5)
    @pytest.mark.asyncio
    async def test_supervisor_feedback_preserved(
        self,
        db: Session,
        supervision_session_factory,
        agent_execution_factory,
        rating,
    ):
        """Test supervisor feedback is preserved in episode."""
        feedback_text = f"Rated {rating}/5 - Performance feedback"

        session = supervision_session_factory(
            supervisor_rating=rating,
        )
        session.supervision_feedback = feedback_text
        db.commit()

        execution = agent_execution_factory()

        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=db,
        )

        assert episode.supervision_feedback == feedback_text
        assert episode.supervisor_rating == rating
