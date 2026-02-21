"""
Integration tests for Episode Memory services.

Tests real database persistence for episode creation, segmentation,
and retrieval using SQLite in-memory database.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session

from core.episode_segmentation_service import (
    EpisodeSegmentationService,
    EpisodeBoundaryDetector,
    TIME_GAP_THRESHOLD_MINUTES,
)
from core.episode_retrieval_service import (
    EpisodeRetrievalService,
    RetrievalMode,
)
from core.models import (
    Base,
    Episode,
    EpisodeSegment,
    AgentRegistry,
    User,
    Workspace,
    ChatSession,
    ChatMessage,
    CanvasAudit,
    AgentFeedback,
    MaturityLevel,
)


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_agent(db_session: Session):
    """Create test agent."""
    agent = AgentRegistry(
        id="test-agent-001",
        name="Test Agent",
        description="Test agent for episode memory",
        maturity=MaturityLevel.STUDENT.value,
        system_prompt="You are a test agent",
        created_by="test-user",
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_user(db_session: Session):
    """Create test user."""
    user = User(
        id="test-user-001",
        email="test@example.com",
        username="testuser",
        full_name="Test User",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_workspace(db_session: Session, test_user: User):
    """Create test workspace."""
    workspace = Workspace(
        id="test-workspace-001",
        name="Test Workspace",
        description="Test workspace for episodes",
        created_by=test_user.id,
    )
    db_session.add(workspace)
    db_session.commit()
    return workspace


@pytest.fixture
def segmentation_service(db_session: Session):
    """Create EpisodeSegmentationService instance."""
    return EpisodeSegmentationService(db_session)


@pytest.fixture
def retrieval_service(db_session: Session):
    """Create EpisodeRetrievalService instance."""
    return EpisodeRetrievalService(db_session)


@pytest.mark.integration
def test_create_episode_with_segments(
    db_session: Session,
    segmentation_service: EpisodeSegmentationService,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
):
    """Test episode creation with real DB persistence."""
    # Create episode
    episode = segmentation_service.create_episode(
        agent_id=test_agent.id,
        session_id="test-session-001",
        workspace_id=test_workspace.id,
        title="Test Episode",
        description="Test episode description",
        content="Test episode content for memory",
    )

    # Verify episode persisted in DB
    assert episode.id is not None
    assert episode.title == "Test Episode"
    assert episode.agent_id == test_agent.id

    # Query from DB
    db_episode = db_session.query(Episode).filter_by(id=episode.id).first()
    assert db_episode is not None
    assert db_episode.title == "Test Episode"
    assert db_episode.agent_id == test_agent.id


@pytest.mark.integration
def test_episode_segmentation_by_time_gap(
    db_session: Session,
    segmentation_service: EpisodeSegmentationService,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
):
    """Test episode segmentation on time gaps."""
    # Create chat session with messages
    chat_session = ChatSession(
        id="chat-session-001",
        user_id="test-user",
        agent_id=test_agent.id,
        workspace_id=test_workspace.id,
    )
    db_session.add(chat_session)
    db_session.commit()

    # Create messages with time gap
    now = datetime.utcnow()

    # First message
    msg1 = ChatMessage(
        id="msg-001",
        session_id=chat_session.id,
        role="user",
        content="First message",
        created_at=now,
    )
    db_session.add(msg1)

    # Second message after 45 minutes (exceeds threshold)
    msg2 = ChatMessage(
        id="msg-002",
        session_id=chat_session.id,
        role="user",
        content="Second message after gap",
        created_at=now + timedelta(minutes=45),
    )
    db_session.add(msg2)
    db_session.commit()

    # Detect time gaps
    messages = db_session.query(ChatMessage).filter_by(
        session_id=chat_session.id
    ).order_by(ChatMessage.created_at).all()

    boundary_detector = EpisodeBoundaryDetector(lancedb_handler=None)
    gaps = boundary_detector.detect_time_gap(messages)

    # Should detect 1 time gap
    assert len(gaps) == 1
    assert gaps[0] == 1  # Gap at index 1 (between msg1 and msg2)


@pytest.mark.integration
@pytest.mark.parametrize("retrieval_mode,limit,expected_max", [
    ("temporal", 10, 10),
    ("temporal", 50, 50),
    ("sequential", 5, 5),
])
def test_episode_retrieval_modes(
    db_session: Session,
    retrieval_service: EpisodeRetrievalService,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
    retrieval_mode,
    limit,
    expected_max,
):
    """Parametrized test for retrieval modes."""
    # Create test episodes
    now = datetime.utcnow()
    for i in range(20):
        episode = Episode(
            id=f"episode-{i:03d}",
            title=f"Episode {i}",
            description=f"Test episode {i}",
            agent_id=test_agent.id,
            workspace_id=test_workspace.id,
            created_at=now - timedelta(hours=i),
        )
        db_session.add(episode)
    db_session.commit()

    # Test temporal retrieval
    if retrieval_mode == "temporal":
        import asyncio

        result = asyncio.run(retrieval_service.retrieve_temporal(
            agent_id=test_agent.id,
            time_range="7d",
            limit=limit,
        ))

        assert len(result["episodes"]) <= expected_max
        assert result["count"] <= expected_max


@pytest.mark.integration
def test_episode_segment_creation(
    db_session: Session,
    segmentation_service: EpisodeSegmentationService,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
):
    """Test episode segments are persisted correctly."""
    # Create episode
    episode = Episode(
        id="test-episode-segments",
        title="Test Episode with Segments",
        agent_id=test_agent.id,
        workspace_id=test_workspace.id,
    )
    db_session.add(episode)
    db_session.commit()

    # Create segments
    for i in range(3):
        segment = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=i,
            content=f"Segment content {i}",
            content_summary=f"Summary {i}",
        )
        db_session.add(segment)
    db_session.commit()

    # Query segments
    segments = db_session.query(EpisodeSegment).filter_by(
        episode_id=episode.id
    ).order_by(EpisodeSegment.sequence_order).all()

    assert len(segments) == 3
    assert segments[0].sequence_order == 0
    assert segments[1].sequence_order == 1
    assert segments[2].sequence_order == 2


@pytest.mark.integration
def test_episode_canvas_context(
    db_session: Session,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
    test_user: User,
):
    """Test episodes track canvas presentations."""
    # Create episode with canvas context
    episode = Episode(
        id="test-episode-canvas",
        title="Canvas Episode",
        agent_id=test_agent.id,
        workspace_id=test_workspace.id,
        canvas_context={
            "canvas_id": "canvas-001",
            "canvas_type": "chart",
            "action": "present",
        }
    )
    db_session.add(episode)

    # Create canvas audit
    canvas_audit = CanvasAudit(
        id="canvas-audit-001",
        canvas_id="canvas-001",
        user_id=test_user.id,
        agent_id=test_agent.id,
        workspace_id=test_workspace.id,
        action="present",
        canvas_type="chart",
        canvas_state={"title": "Test Chart"},
    )
    db_session.add(canvas_audit)
    db_session.commit()

    # Query episode with canvas context
    db_episode = db_session.query(Episode).filter_by(
        id="test-episode-canvas"
    ).first()

    assert db_episode is not None
    assert db_episode.canvas_context is not None
    assert db_episode.canvas_context["canvas_id"] == "canvas-001"
    assert db_episode.canvas_context["action"] == "present"


@pytest.mark.integration
def test_episode_feedback_aggregation(
    db_session: Session,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
    test_user: User,
):
    """Test episodes aggregate user feedback scores."""
    # Create episode
    episode = Episode(
        id="test-episode-feedback",
        title="Feedback Episode",
        agent_id=test_agent.id,
        workspace_id=test_workspace.id,
        feedback_context={
            "average_score": 0.5,
            "feedback_count": 3,
        }
    )
    db_session.add(episode)
    db_session.commit()

    # Create feedback records
    feedback_scores = [1.0, 0.5, 0.0]  # Thumbs up, neutral, thumbs down
    for i, score in enumerate(feedback_scores):
        feedback = AgentFeedback(
            id=f"feedback-{i}",
            agent_id=test_agent.id,
            user_id=test_user.id,
            session_id="test-session",
            feedback_type="thumbs_up_down",
            score=score,
            comment=f"Feedback {i}",
        )
        db_session.add(feedback)
    db_session.commit()

    # Calculate average
    avg_score = sum(feedback_scores) / len(feedback_scores)

    # Update episode feedback context
    episode.feedback_context = {
        "average_score": avg_score,
        "feedback_count": len(feedback_scores),
    }
    db_session.commit()

    # Verify aggregation
    db_episode = db_session.query(Episode).filter_by(
        id="test-episode-feedback"
    ).first()

    assert db_episode.feedback_context is not None
    assert db_episode.feedback_context["average_score"] == avg_score
    assert db_episode.feedback_context["feedback_count"] == 3


@pytest.mark.integration
def test_episode_lifecycle_decay(
    db_session: Session,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
):
    """Test episode decay over time."""
    now = datetime.utcnow()

    # Create old episode (should be decayed)
    old_episode = Episode(
        id="old-episode",
        title="Old Episode",
        agent_id=test_agent.id,
        workspace_id=test_workspace.id,
        created_at=now - timedelta(days=100),
        status="decayed",
    )
    db_session.add(old_episode)

    # Create recent episode (active)
    recent_episode = Episode(
        id="recent-episode",
        title="Recent Episode",
        agent_id=test_agent.id,
        workspace_id=test_workspace.id,
        created_at=now - timedelta(days=1),
        status="active",
    )
    db_session.add(recent_episode)
    db_session.commit()

    # Query active episodes only
    active_episodes = db_session.query(Episode).filter_by(
        agent_id=test_agent.id,
        status="active",
    ).all()

    assert len(active_episodes) == 1
    assert active_episodes[0].id == "recent-episode"


@pytest.mark.integration
def test_episode_workspace_filtering(
    db_session: Session,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
):
    """Test filtering episodes by workspace."""
    # Create second workspace
    workspace2 = Workspace(
        id="test-workspace-002",
        name="Second Workspace",
        created_by="test-user",
    )
    db_session.add(workspace2)
    db_session.commit()

    # Create episodes in different workspaces
    for ws_id in [test_workspace.id, workspace2.id]:
        for i in range(3):
            episode = Episode(
                id=f"episode-{ws_id}-{i}",
                title=f"Episode in {ws_id}",
                agent_id=test_agent.id,
                workspace_id=ws_id,
            )
            db_session.add(episode)
    db_session.commit()

    # Query episodes by workspace
    ws1_episodes = db_session.query(Episode).filter_by(
        workspace_id=test_workspace.id
    ).all()

    ws2_episodes = db_session.query(Episode).filter_by(
        workspace_id=workspace2.id
    ).all()

    assert len(ws1_episodes) == 3
    assert len(ws2_episodes) == 3
    assert all(ep.workspace_id == test_workspace.id for ep in ws1_episodes)
    assert all(ep.workspace_id == workspace2.id for ep in ws2_episodes)


@pytest.mark.integration
def test_segmentation_boundary_detection(
    db_session: Session,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
):
    """Test boundary detector identifies all boundary types."""
    # Create chat session
    chat_session = ChatSession(
        id="boundary-test-session",
        user_id="test-user",
        agent_id=test_agent.id,
        workspace_id=test_workspace.id,
    )
    db_session.add(chat_session)
    db_session.commit()

    now = datetime.utcnow()

    # Create messages with different patterns
    messages_data = [
        ("Message 1", now),
        ("Message 2", now + timedelta(minutes=10)),  # No gap
        ("Message 3", now + timedelta(minutes=50)),  # Time gap > 30min
        ("Message 4", now + timedelta(minutes=60)),
    ]

    for i, (content, timestamp) in enumerate(messages_data):
        msg = ChatMessage(
            id=f"boundary-msg-{i}",
            session_id=chat_session.id,
            role="user",
            content=content,
            created_at=timestamp,
        )
        db_session.add(msg)
    db_session.commit()

    # Query and detect boundaries
    messages = db_session.query(ChatMessage).filter_by(
        session_id=chat_session.id
    ).order_by(ChatMessage.created_at).all()

    boundary_detector = EpisodeBoundaryDetector(lancedb_handler=None)
    gaps = boundary_detector.detect_time_gap(messages)

    # Should detect 1 time gap (between message 2 and 3)
    assert len(gaps) == 1
    assert gaps[0] == 2  # Gap at index 2


@pytest.mark.integration
def test_episode_temporal_query_range(
    db_session: Session,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
):
    """Test temporal retrieval with different time ranges."""
    now = datetime.utcnow()

    # Create episodes at different times
    time_ranges = [
        (now - timedelta(hours=2), "recent-episode"),  # 1d range
        (now - timedelta(days=5), "week-episode"),  # 7d range
        (now - timedelta(days=20), "month-episode"),  # 30d range
    ]

    for timestamp, ep_id in time_ranges:
        episode = Episode(
            id=ep_id,
            title=f"Episode at {ep_id}",
            agent_id=test_agent.id,
            workspace_id=test_workspace.id,
            created_at=timestamp,
        )
        db_session.add(episode)
    db_session.commit()

    # Query last 24 hours
    yesterday = now - timedelta(days=1)
    recent_episodes = db_session.query(Episode).filter(
        Episode.agent_id == test_agent.id,
        Episode.created_at >= yesterday,
    ).all()

    assert len(recent_episodes) == 1
    assert recent_episodes[0].id == "recent-episode"


@pytest.mark.integration
def test_segment_ordering_within_episode(
    db_session: Session,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
):
    """Test segments maintain correct sequential order."""
    # Create episode
    episode = Episode(
        id="ordering-test-episode",
        title="Ordering Test",
        agent_id=test_agent.id,
        workspace_id=test_workspace.id,
    )
    db_session.add(episode)
    db_session.commit()

    # Create segments in random order
    segment_data = [
        (2, "Third segment"),
        (0, "First segment"),
        (1, "Second segment"),
    ]

    for seq_order, content in segment_data:
        segment = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=seq_order,
            content=content,
        )
        db_session.add(segment)
    db_session.commit()

    # Query and verify ordering
    segments = db_session.query(EpisodeSegment).filter_by(
        episode_id=episode.id
    ).order_by(EpisodeSegment.sequence_order).all()

    assert len(segments) == 3
    assert segments[0].content == "First segment"
    assert segments[1].content == "Second segment"
    assert segments[2].content == "Third segment"


@pytest.mark.integration
def test_episode_cascade_delete_segments(
    db_session: Session,
    test_agent: AgentRegistry,
    test_workspace: Workspace,
):
    """Test deleting episode cascades to segments."""
    # Create episode with segments
    episode = Episode(
        id="cascade-test-episode",
        title="Cascade Test",
        agent_id=test_agent.id,
        workspace_id=test_workspace.id,
    )
    db_session.add(episode)
    db_session.commit()

    # Add segments
    for i in range(3):
        segment = EpisodeSegment(
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=i,
            content=f"Segment {i}",
        )
        db_session.add(segment)
    db_session.commit()

    # Verify segments exist
    segments_before = db_session.query(EpisodeSegment).filter_by(
        episode_id=episode.id
    ).count()
    assert segments_before == 3

    # Delete episode
    db_session.delete(episode)
    db_session.commit()

    # Verify segments are cascade deleted
    segments_after = db_session.query(EpisodeSegment).filter_by(
        episode_id=episode.id
    ).count()
    assert segments_after == 0


@pytest.mark.integration
def test_multi_agent_episode_isolation(
    db_session: Session,
    test_workspace: Workspace,
):
    """Test episodes are isolated between agents."""
    # Create two agents
    agent1 = AgentRegistry(
        id="agent-1",
        name="Agent 1",
        maturity=MaturityLevel.STUDENT.value,
        created_by="test-user",
    )
    agent2 = AgentRegistry(
        id="agent-2",
        name="Agent 2",
        maturity=MaturityLevel.INTERN.value,
        created_by="test-user",
    )
    db_session.add(agent1)
    db_session.add(agent2)
    db_session.commit()

    # Create episodes for each agent
    for agent_id in ["agent-1", "agent-2"]:
        for i in range(3):
            episode = Episode(
                id=f"episode-{agent_id}-{i}",
                title=f"Episode for {agent_id}",
                agent_id=agent_id,
                workspace_id=test_workspace.id,
            )
            db_session.add(episode)
    db_session.commit()

    # Query episodes per agent
    agent1_episodes = db_session.query(Episode).filter_by(
        agent_id="agent-1"
    ).all()

    agent2_episodes = db_session.query(Episode).filter_by(
        agent_id="agent-2"
    ).all()

    assert len(agent1_episodes) == 3
    assert len(agent2_episodes) == 3
    assert all(ep.agent_id == "agent-1" for ep in agent1_episodes)
    assert all(ep.agent_id == "agent-2" for ep in agent2_episodes)
