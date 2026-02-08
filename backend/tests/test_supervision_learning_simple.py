"""
Simple demonstration tests for supervision learning integration.

These tests verify the core functionality works without complex fixtures.
"""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from core.database import SessionLocal
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    Episode,
    SupervisionSession,
    SupervisionStatus,
    User,
    Workspace,
)
from core.episode_segmentation_service import EpisodeSegmentationService
from core.supervision_service import SupervisionService


@pytest.fixture
def db():
    """Create a test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        # Clean up test data
        db.query(Episode).filter(Episode.id.like("test_%")).delete()
        db.query(SupervisionSession).filter(SupervisionSession.id.like("test_%")).delete()
        db.query(AgentExecution).filter(AgentExecution.id.like("test_%")).delete()
        db.query(AgentRegistry).filter(AgentRegistry.id.like("test_%")).delete()
        db.query(Workspace).filter(Workspace.id.like("test_%")).delete()
        db.query(User).filter(User.id.like("test_%")).delete()
        db.commit()
        db.close()


class TestSupervisionLearningBasic:
    """Basic tests for supervision learning functionality."""

    @pytest.mark.asyncio
    async def test_supervision_episode_creation(self, db: Session):
        """Test creating episode from supervision session."""
        # Create unique test data
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        workspace_id = f"test_workspace_{uuid.uuid4().hex[:8]}"
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"
        session_id = f"test_supervision_{uuid.uuid4().hex[:8]}"
        execution_id = f"test_exec_{uuid.uuid4().hex[:8]}"

        # Create user
        user = User(
            id=user_id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
        )
        db.add(user)

        # Create workspace
        workspace = Workspace(
            id=workspace_id,
            name="Test Workspace",
        )
        db.add(workspace)

        # Create agent
        agent = AgentRegistry(
            id=agent_id,
            name="Test Agent",
            category="testing",
            module_path="agents.test",
            class_name="TestAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.75,
        )
        db.add(agent)

        # Create supervision session
        supervision_session = SupervisionSession(
            id=session_id,
            agent_id=agent_id,
            agent_name=agent.name,
            workspace_id=workspace_id,
            supervisor_id=user_id,
            status=SupervisionStatus.COMPLETED.value,
            trigger_context={},  # Required field
            intervention_count=2,
            supervisor_rating=5,
            supervisor_feedback="Excellent work",
            duration_seconds=300,
            started_at=datetime.now() - timedelta(seconds=300),
            completed_at=datetime.now(),
            interventions=[
                {
                    "timestamp": datetime.now().isoformat(),
                    "type": "correct",
                    "guidance": "Test guidance"
                }
            ]
        )
        db.add(supervision_session)

        # Create agent execution
        execution = AgentExecution(
            id=execution_id,
            agent_id=agent_id,
            status="completed",
            started_at=datetime.now() - timedelta(seconds=300),
            completed_at=datetime.now(),
            duration_seconds=300,
        )
        db.add(execution)

        db.commit()

        # Create episode from supervision session
        episode_service = EpisodeSegmentationService(db)
        episode = await episode_service.create_supervision_episode(
            supervision_session=supervision_session,
            agent_execution=execution,
            db=db,
        )

        # Verify episode created
        assert episode is not None
        assert episode.agent_id == agent_id
        assert episode.supervisor_id == user_id
        assert episode.supervisor_rating == 5
        assert episode.intervention_count == 2
        assert episode.maturity_at_time == AgentStatus.SUPERVISED.value
        assert episode.status == "completed"

        # Verify segments created
        from core.models import EpisodeSegment
        segments = db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) >= 2  # At least execution and intervention segments

        print(f"✓ Successfully created supervision episode: {episode.id}")
        print(f"  - Agent: {episode.agent_id}")
        print(f"  - Supervisor: {episode.supervisor_id}")
        print(f"  - Rating: {episode.supervisor_rating}/5")
        print(f"  - Interventions: {episode.intervention_count}")
        print(f"  - Segments: {len(segments)}")

    def test_supervision_columns_exist(self, db: Session):
        """Test that supervision columns exist in episodes table."""
        # Check if columns exist by inspecting the table
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        columns = [c['name'] for c in inspector.get_columns('episodes')]

        supervision_columns = [
            'supervisor_id',
            'supervisor_rating',
            'intervention_count',
            'intervention_types',
            'proposal_id',
            'proposal_outcome',
        ]

        for col in supervision_columns:
            assert col in columns, f"Column {col} not found in episodes table"

        print("✓ All supervision columns exist in episodes table")

    @pytest.mark.asyncio
    async def test_episode_retrieval_with_supervision(self, db: Session):
        """Test retrieving episodes with supervision context."""
        from core.episode_retrieval_service import EpisodeRetrievalService, RetrievalMode

        # Create test data
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        workspace_id = f"test_workspace_{uuid.uuid4().hex[:8]}"
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"

        user = User(
            id=user_id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
        )
        db.add(user)

        workspace = Workspace(
            id=workspace_id,
            name="Test Workspace",
        )
        db.add(workspace)

        agent = AgentRegistry(
            id=agent_id,
            name="Test Agent",
            category="testing",
            module_path="agents.test",
            class_name="TestAgent",
            status=AgentStatus.SUPERVISED.value,
        )
        db.add(agent)

        # Create episode with supervision data
        episode = Episode(
            id=f"test_episode_{uuid.uuid4().hex[:8]}",
            title="Test Episode",
            description="Test",
            summary="Test",
            agent_id=agent_id,
            user_id=user_id,
            workspace_id=workspace_id,
            supervisor_id=user_id,
            supervisor_rating=5,
            intervention_count=1,
            intervention_types=["correct"],
            maturity_at_time=AgentStatus.SUPERVISED.value,
            status="completed",
            started_at=datetime.now(),
            ended_at=datetime.now(),
        )
        db.add(episode)
        db.commit()

        # Retrieve with supervision context
        retrieval_service = EpisodeRetrievalService(db)
        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id=agent_id,
            retrieval_mode=RetrievalMode.TEMPORAL,
            limit=10,
        )

        assert result["count"] > 0
        assert len(result["episodes"]) > 0

        # Check supervision context
        episode_data = result["episodes"][0]
        assert "supervision_context" in episode_data
        ctx = episode_data["supervision_context"]
        assert ctx["has_supervision"] is True
        assert ctx["supervisor_rating"] == 5
        assert ctx["intervention_count"] == 1

        print(f"✓ Successfully retrieved episode with supervision context")
        print(f"  - Supervisor Rating: {ctx['supervisor_rating']}/5")
        print(f"  - Intervention Count: {ctx['intervention_count']}")
        print(f"  - Outcome Quality: {ctx['outcome_quality']}")

    @pytest.mark.asyncio
    async def test_graduation_metrics_calculation(self, db: Session):
        """Test supervision metrics calculation for graduation."""
        from core.agent_graduation_service import AgentGraduationService

        # Create test data
        user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        workspace_id = f"test_workspace_{uuid.uuid4().hex[:8]}"
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"

        user = User(
            id=user_id,
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Test",
            last_name="User",
        )
        db.add(user)

        workspace = Workspace(
            id=workspace_id,
            name="Test Workspace",
        )
        db.add(workspace)

        agent = AgentRegistry(
            id=agent_id,
            name="Test Agent",
            category="testing",
            module_path="agents.test",
            class_name="TestAgent",
            status=AgentStatus.SUPERVISED.value,
        )
        db.add(agent)

        # Create supervision sessions
        for i in range(5):
            session = SupervisionSession(
                id=f"test_supervision_{i}_{uuid.uuid4().hex[:8]}",
                agent_id=agent_id,
                agent_name=agent.name,
                workspace_id=workspace_id,
                supervisor_id=user_id,
                status=SupervisionStatus.COMPLETED.value,
                trigger_context={},  # Required field
                intervention_count=i % 3,
                supervisor_rating=5 - (i % 2),
                supervisor_feedback=f"Session {i} feedback",
                duration_seconds=300,
                started_at=datetime.now() - timedelta(days=i+1, seconds=300),
                completed_at=datetime.now() - timedelta(days=i+1),
            )
            db.add(session)

        db.commit()

        # Calculate supervision metrics
        graduation_service = AgentGraduationService(db)
        metrics = await graduation_service.calculate_supervision_metrics(
            agent_id=agent_id,
            maturity_level=AgentStatus.SUPERVISED,
        )

        assert metrics["total_sessions"] == 5
        assert metrics["total_supervision_hours"] > 0
        assert 1 <= metrics["average_supervisor_rating"] <= 5

        print(f"✓ Successfully calculated supervision metrics")
        print(f"  - Total Sessions: {metrics['total_sessions']}")
        print(f"  - Total Hours: {metrics['total_supervision_hours']:.2f}")
        print(f"  - Avg Rating: {metrics['average_supervisor_rating']:.2f}/5")
        print(f"  - High-Rated Sessions: {metrics['high_rating_sessions']}")
        print(f"  - Low-Intervention Sessions: {metrics['low_intervention_sessions']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
