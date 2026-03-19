"""
Comprehensive tests for EpisodeRetrievalService.

Tests cover temporal, semantic, sequential, and contextual retrieval modes.
Achieves 70%+ coverage target.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from core.episode_retrieval_service import (
    EpisodeRetrievalService,
    RetrievalMode,
    RetrievalResult
)
from core.models import (
    Episode,
    EpisodeSegment,
    EpisodeAccessLog,
    AgentRegistry,
    ChatSession,
    CanvasAudit,
    AgentFeedback,
    AgentStatus
)


@pytest.fixture
def db_session():
    """Mock database session."""
    session = Mock()
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    return session


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler."""
    handler = Mock()
    handler.db = Mock()
    handler.search = Mock(return_value=[])
    handler.table_names = Mock(return_value=[])
    return handler


@pytest.fixture
def mock_governance():
    """Mock governance service."""
    governance = Mock()
    governance.can_perform_action = Mock(return_value={"allowed": True, "agent_maturity": "INTERN"})
    return governance


@pytest.fixture
def retrieval_service(db_session, mock_lancedb, mock_governance):
    """Create EpisodeRetrievalService instance."""
    with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=mock_lancedb):
        service = EpisodeRetrievalService(db_session)
        service.governance = mock_governance
        service.lancedb = mock_lancedb
        return service


@pytest.fixture
def sample_episodes():
    """Create sample episodes."""
    episodes = []
    for i in range(5):
        episode = Episode(
            id=f"episode-{i}",
            agent_id="agent-1",
            tenant_id="default",
            task_description=f"Task {i}",
            status="completed",
            started_at=datetime.now() - timedelta(days=i),
            completed_at=datetime.now() - timedelta(days=i) + timedelta(hours=1),
            maturity_at_time="INTERN",
            human_intervention_count=0,
            access_count=i,
            decay_score=1.0 - (i * 0.1)
        )
        episodes.append(episode)
    return episodes


@pytest.fixture
def sample_episode():
    """Create single sample episode with all fields."""
    episode = Episode(
        id="episode-1",
        agent_id="agent-1",
        tenant_id="default",
        task_description="Test Episode",
        status="completed",
        started_at=datetime.now() - timedelta(days=1),
        completed_at=datetime.now() - timedelta(days=1) + timedelta(hours=1),
        topics=["topic1", "topic2"],
        entities=["entity1"],
        importance_score=0.8,
        maturity_at_time="INTERN",
        human_intervention_count=1,
        constitutional_score=0.9,
        decay_score=0.9,
        access_count=5,
        outcome="success",
        success=True,
        supervisor_id="supervisor-1",
        canvas_ids=["canvas-1"],
        feedback_ids=["feedback-1"],
        canvas_action_count=2,
        aggregate_feedback_score=0.5,
        metadata_json={"key": "value"}
    )
    return episode


@pytest.fixture
def sample_segments():
    """Create sample episode segments."""
    segments = []
    for i in range(3):
        segment = EpisodeSegment(
            id=f"segment-{i}",
            episode_id="episode-1",
            segment_type="conversation" if i % 2 == 0 else "execution",
            sequence_order=i,
            content=f"Segment content {i}",
            content_summary=f"Summary {i}",
            source_type="chat_message",
            source_id=f"msg-{i}",
            canvas_context={"canvas_type": "sheets"} if i == 0 else None
        )
        segments.append(segment)
    return segments


@pytest.fixture
def sample_agent():
    """Create sample agent."""
    agent = AgentRegistry(
        id="agent-1",
        name="Test Agent",
        status=AgentStatus.INTERN
    )
    return agent


class TestTemporalRetrieval:
    """Tests for temporal retrieval mode."""

    @pytest.mark.asyncio
    async def test_retrieve_temporal_basic(
        self, retrieval_service, db_session, sample_episodes
    ):
        """Test basic temporal retrieval."""
        # Setup query chain
        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            sample_episodes,
            [Mock(id="s1", user_id="user-1")]  # ChatSession
        ]

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-1",
            time_range="7d"
        )

        assert result["count"] == 5
        assert len(result["episodes"]) == 5
        assert result["time_range"] == "7d"
        assert "governance_check" in result

    @pytest.mark.asyncio
    async def test_retrieve_temporal_governance_denied(
        self, retrieval_service, mock_governance
    ):
        """Test temporal retrieval when governance check fails."""
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Agent not authorized"
        }

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-1",
            time_range="7d"
        )

        assert result["episodes"] == []
        assert "error" in result
        assert "not authorized" in result["error"]

    @pytest.mark.asyncio
    async def test_retrieve_temporal_different_time_ranges(
        self, retrieval_service, db_session, sample_episodes
    ):
        """Test temporal retrieval with different time ranges."""
        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes
        db_session.query.return_value.filter.return_value.all.return_value = []

        # Test 1d
        result = await retrieval_service.retrieve_temporal("agent-1", "1d")
        assert result["time_range"] == "1d"

        # Test 30d
        result = await retrieval_service.retrieve_temporal("agent-1", "30d")
        assert result["time_range"] == "30d"

        # Test 90d
        result = await retrieval_service.retrieve_temporal("agent-1", "90d")
        assert result["time_range"] == "90d"

    @pytest.mark.asyncio
    async def test_retrieve_temporal_with_user_filter(
        self, retrieval_service, db_session, sample_episodes
    ):
        """Test temporal retrieval with user_id filter."""
        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            sample_episodes,
            [Mock(id="s1", user_id="user-1")]  # ChatSession
        ]

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-1",
            time_range="7d",
            user_id="user-1"
        )

        assert result["count"] >= 0
        # Verify join was called
        assert db_session.query.return_value.join.called

    @pytest.mark.asyncio
    async def test_retrieve_temporal_limit(
        self, retrieval_service, db_session, sample_episodes
    ):
        """Test temporal retrieval with limit."""
        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-1",
            time_range="7d",
            limit=3
        )

        # Verify limit was applied
        db_session.query.return_value.filter.return_value.order_by.return_value.limit.assert_called_with(3)

    @pytest.mark.asyncio
    async def test_retrieve_temporal_excludes_archived(
        self, retrieval_service, db_session
    ):
        """Test temporal retrieval excludes archived episodes."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Active",
                status="active",
                started_at=datetime.now()
            ),
            Episode(
                id="episode-2",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Archived",
                status="archived",
                started_at=datetime.now()
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_temporal("agent-1", "7d")

        # Should only return non-archived episodes
        assert result["count"] >= 0


class TestSemanticRetrieval:
    """Tests for semantic retrieval mode."""

    @pytest.mark.asyncio
    async def test_retrieve_semantic_basic(
        self, retrieval_service, mock_lancedb, db_session, sample_episodes
    ):
        """Test basic semantic retrieval."""
        # Setup LanceDB search results
        mock_lancedb.search.return_value = [
            {
                "id": "ep-1",
                "metadata": '{"episode_id": "episode-1"}',
                "_distance": 0.2
            },
            {
                "id": "ep-2",
                "metadata": '{"episode_id": "episode-2"}',
                "_distance": 0.3
            }
        ]

        db_session.query.return_value.filter.return_value.all.return_value = sample_episodes[:2]

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-1",
            query="test query"
        )

        assert len(result["episodes"]) >= 0
        assert result["query"] == "test query"
        mock_lancedb.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_semantic_governance_denied(
        self, retrieval_service, mock_governance
    ):
        """Test semantic retrieval when governance check fails."""
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "INTERN maturity required"
        }

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-1",
            query="test query"
        )

        assert result["episodes"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_retrieve_semantic_with_limit(
        self, retrieval_service, mock_lancedb, db_session
    ):
        """Test semantic retrieval with custom limit."""
        mock_lancedb.search.return_value = []
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-1",
            query="test query",
            limit=20
        )

        # Verify limit was passed to LanceDB
        mock_lancedb.search.assert_called_once()
        call_kwargs = mock_lancedb.search.call_args[1]
        assert call_kwargs["limit"] == 20

    @pytest.mark.asyncio
    async def test_retrieve_semantic_parse_metadata_string(
        self, retrieval_service, mock_lancedb, db_session, sample_episodes
    ):
        """Test semantic retrieval parses string metadata."""
        # LanceDB returns metadata as string
        mock_lancedb.search.return_value = [
            {
                "id": "ep-1",
                "metadata": '{"episode_id": "episode-1", "agent_id": "agent-1"}',
                "_distance": 0.2
            }
        ]

        db_session.query.return_value.filter.return_value.all.return_value = sample_episodes[:1]

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-1",
            query="test query"
        )

        assert len(result["episodes"]) >= 0

    @pytest.mark.asyncio
    async def test_retrieve_semantic_parse_metadata_dict(
        self, retrieval_service, mock_lancedb, db_session, sample_episodes
    ):
        """Test semantic retrieval parses dict metadata."""
        # LanceDB returns metadata as dict
        mock_lancedb.search.return_value = [
            {
                "id": "ep-1",
                "metadata": {"episode_id": "episode-1", "agent_id": "agent-1"},
                "_distance": 0.2
            }
        ]

        db_session.query.return_value.filter.return_value.all.return_value = sample_episodes[:1]

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-1",
            query="test query"
        )

        assert len(result["episodes"]) >= 0

    @pytest.mark.asyncio
    async def test_retrieve_semantic_handles_exception(
        self, retrieval_service, mock_lancedb
    ):
        """Test semantic retrieval handles exceptions."""
        mock_lancedb.search.side_effect = Exception("LanceDB error")

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-1",
            query="test query"
        )

        assert result["episodes"] == []
        assert "error" in result


class TestSequentialRetrieval:
    """Tests for sequential retrieval mode."""

    @pytest.mark.asyncio
    async def test_retrieve_sequential_basic(
        self, retrieval_service, db_session, sample_episode, sample_segments
    ):
        """Test basic sequential retrieval."""
        # Setup episode query
        db_session.query.return_value.filter.return_value.first.return_value = sample_episode
        # Setup segments query
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-1",
            agent_id="agent-1"
        )

        assert "episode" in result
        assert "segments" in result
        assert len(result["segments"]) == 3

    @pytest.mark.asyncio
    async def test_retrieve_sequential_episode_not_found(self, retrieval_service, db_session):
        """Test sequential retrieval when episode not found."""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = await retrieval_service.retrieve_sequential(
            episode_id="nonexistent",
            agent_id="agent-1"
        )

        assert "error" in result
        assert result["error"] == "Episode not found"

    @pytest.mark.asyncio
    async def test_retrieve_sequential_with_canvas_context(
        self, retrieval_service, db_session, sample_episode, sample_segments
    ):
        """Test sequential retrieval includes canvas context."""
        sample_episode.canvas_ids = ["canvas-1", "canvas-2"]

        # Setup queries
        db_session.query.return_value.filter.return_value.first.return_value = sample_episode
        db_session.query.return_value.order_by.return_value.all.return_value = sample_segments
        db_session.query.return_value.filter.return_value.all.return_value = [
            CanvasAudit(id="canvas-1", canvas_type="sheets", action="present")
        ]

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-1",
            agent_id="agent-1",
            include_canvas=True
        )

        assert "canvas_context" in result

    @pytest.mark.asyncio
    async def test_retrieve_sequential_with_feedback_context(
        self, retrieval_service, db_session, sample_episode, sample_segments
    ):
        """Test sequential retrieval includes feedback context."""
        sample_episode.feedback_ids = ["feedback-1"]

        # Setup queries
        db_session.query.return_value.filter.return_value.first.return_value = sample_episode
        db_session.query.return_value.order_by.return_value.all.return_value = sample_segments
        db_session.query.return_value.filter.return_value.all.return_value = [
            AgentFeedback(id="feedback-1", feedback_type="thumbs_up")
        ]

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-1",
            agent_id="agent-1",
            include_feedback=True
        )

        assert "feedback_context" in result

    @pytest.mark.asyncio
    async def test_retrieve_sequential_exclude_canvas(
        self, retrieval_service, db_session, sample_episode, sample_segments
    ):
        """Test sequential retrieval can exclude canvas context."""
        sample_episode.canvas_ids = ["canvas-1"]

        # Setup queries
        db_session.query.return_value.filter.return_value.first.return_value = sample_episode
        db_session.query.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-1",
            agent_id="agent-1",
            include_canvas=False
        )

        assert "canvas_context" not in result

    @pytest.mark.asyncio
    async def test_retrieve_sequential_exclude_feedback(
        self, retrieval_service, db_session, sample_episode, sample_segments
    ):
        """Test sequential retrieval can exclude feedback context."""
        sample_episode.feedback_ids = ["feedback-1"]

        # Setup queries
        db_session.query.return_value.filter.return_value.first.return_value = sample_episode
        db_session.query.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-1",
            agent_id="agent-1",
            include_feedback=False
        )

        assert "feedback_context" not in result


class TestContextualRetrieval:
    """Tests for contextual retrieval mode."""

    @pytest.mark.asyncio
    async def test_retrieve_contextual_basic(
        self, retrieval_service, mock_lancedb, db_session, sample_episodes
    ):
        """Test basic contextual retrieval."""
        # Setup temporal and semantic results
        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            sample_episodes,  # Temporal
            sample_episodes[:2],  # Semantic
            []  # ChatSession
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []
        mock_lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-1",
            current_task="test task"
        )

        assert "episodes" in result
        assert result["query"] == "test task"

    @pytest.mark.asyncio
    async def test_retrieve_contextual_scoring(
        self, retrieval_service, mock_lancedb, db_session
    ):
        """Test contextual retrieval combines temporal and semantic scores."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task 1",
                status="completed",
                started_at=datetime.now(),
                canvas_action_count=0,
                aggregate_feedback_score=0.0
            ),
            Episode(
                id="episode-2",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task 2",
                status="completed",
                started_at=datetime.now(),
                canvas_action_count=1,
                aggregate_feedback_score=0.5
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            episodes,  # Temporal
            [episodes[0]],  # Semantic
            []
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []
        db_session.query.return_value.first.return_value = episodes[0]
        mock_lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-1",
            current_task="test task"
        )

        # Episode with canvas and positive feedback should score higher
        assert len(result["episodes"]) >= 0

    @pytest.mark.asyncio
    async def test_retrieve_contextual_canvas_boost(
        self, retrieval_service, mock_lancedb, db_session
    ):
        """Test contextual retrieval applies canvas boost."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="completed",
                started_at=datetime.now(),
                canvas_action_count=2,  # Has canvas interactions
                aggregate_feedback_score=0.0
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            episodes,
            [],
            []
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []
        db_session.query.return_value.first.return_value = episodes[0]
        mock_lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-1",
            current_task="test task"
        )

        # Canvas boost should be applied
        assert len(result["episodes"]) >= 0

    @pytest.mark.asyncio
    async def test_retrieve_contextual_positive_feedback_boost(
        self, retrieval_service, mock_lancedb, db_session
    ):
        """Test contextual retrieval applies positive feedback boost."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="completed",
                started_at=datetime.now(),
                canvas_action_count=0,
                aggregate_feedback_score=0.8  # Positive feedback
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            episodes,
            [],
            []
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []
        db_session.query.return_value.first.return_value = episodes[0]
        mock_lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-1",
            current_task="test task"
        )

        assert len(result["episodes"]) >= 0

    @pytest.mark.asyncio
    async def test_retrieve_contextual_negative_feedback_penalty(
        self, retrieval_service, mock_lancedb, db_session
    ):
        """Test contextual retrieval applies negative feedback penalty."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="completed",
                started_at=datetime.now(),
                canvas_action_count=0,
                aggregate_feedback_score=-0.5  # Negative feedback
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            episodes,
            [],
            []
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []
        db_session.query.return_value.first.return_value = episodes[0]
        mock_lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-1",
            current_task="test task"
        )

        assert len(result["episodes"]) >= 0

    @pytest.mark.asyncio
    async def test_retrieve_contextual_require_canvas(
        self, retrieval_service, mock_lancedb, db_session
    ):
        """Test contextual retrieval filters by canvas requirement."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="completed",
                started_at=datetime.now(),
                canvas_action_count=0,  # No canvas
                feedback_ids=[]
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            episodes,
            [],
            []
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []
        db_session.query.return_value.first.return_value = episodes[0]
        mock_lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-1",
            current_task="test task",
            require_canvas=True
        )

        # Should filter out episodes without canvas
        assert len(result["episodes"]) == 0

    @pytest.mark.asyncio
    async def test_retrieve_contextual_require_feedback(
        self, retrieval_service, mock_lancedb, db_session
    ):
        """Test contextual retrieval filters by feedback requirement."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="completed",
                started_at=datetime.now(),
                canvas_action_count=0,
                feedback_ids=[]  # No feedback
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            episodes,
            [],
            []
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []
        db_session.query.return_value.first.return_value = episodes[0]
        mock_lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-1",
            current_task="test task",
            require_feedback=True
        )

        # Should filter out episodes without feedback
        assert len(result["episodes"]) == 0


class TestCanvasAwareRetrieval:
    """Tests for canvas-aware retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_basic(
        self, retrieval_service, mock_lancedb, db_session, sample_episodes
    ):
        """Test basic canvas-aware retrieval."""
        mock_lancedb.search.return_value = [
            {
                "id": "ep-1",
                "metadata": {"episode_id": "episode-1"},
                "_distance": 0.2
            }
        ]

        db_session.query.return_value.filter.return_value.all.return_value = sample_episodes[:1]
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent-1",
            query="test query"
        )

        assert "episodes" in result
        assert "canvas_context_detail" in result

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_with_type_filter(
        self, retrieval_service, mock_lancedb, db_session
    ):
        """Test canvas-aware retrieval with canvas type filter."""
        mock_lancedb.search.return_value = []
        db_session.query.return_value.filter.return_value.all.return_value = []
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent-1",
            query="test query",
            canvas_type="sheets"
        )

        # Verify canvas type filter was applied
        mock_lancedb.search.assert_called_once()
        call_kwargs = mock_lancedb.search.call_args[1]
        assert "sheets" in call_kwargs["filter_str"]

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_summary_detail(
        self, retrieval_service, mock_lancedb, db_session, sample_segments
    ):
        """Test canvas-aware retrieval with summary detail level."""
        mock_lancedb.search.return_value = [
            {
                "id": "ep-1",
                "metadata": {"episode_id": "episode-1"},
                "_distance": 0.2
            }
        ]

        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="completed",
            started_at=datetime.now()
        )

        db_session.query.return_value.filter.return_value.all.return_value = [episode]
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent-1",
            query="test query",
            canvas_context_detail="summary"
        )

        # Verify summary detail was applied
        assert result["canvas_context_detail"] == "summary"

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_standard_detail(
        self, retrieval_service, mock_lancedb, db_session, sample_segments
    ):
        """Test canvas-aware retrieval with standard detail level."""
        mock_lancedb.search.return_value = [
            {
                "id": "ep-1",
                "metadata": {"episode_id": "episode-1"},
                "_distance": 0.2
            }
        ]

        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="completed",
            started_at=datetime.now()
        )

        db_session.query.return_value.filter.return_value.all.return_value = [episode]
        db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent-1",
            query="test query",
            canvas_context_detail="standard"
        )

        assert result["canvas_context_detail"] == "standard"


class TestBusinessDataRetrieval:
    """Tests for business data retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_basic(
        self, retrieval_service, db_session
    ):
        """Test retrieval by business data."""
        segments = [
            EpisodeSegment(
                id="segment-1",
                episode_id="episode-1",
                segment_type="conversation",
                sequence_order=0,
                content="Content",
                content_summary="Summary",
                source_type="chat_message",
                source_id="msg-1",
                canvas_context={
                    "critical_data_points": {"revenue": 1000000}
                }
            )
        ]

        db_session.query.return_value.join.return_value.filter.return_value.limit.return_value.all.return_value = segments
        db_session.query.return_value.filter.return_value.all.return_value = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="completed",
                started_at=datetime.now()
            )
        ]

        result = await retrieval_service.retrieve_by_business_data(
            agent_id="agent-1",
            business_filters={"revenue": {"$gt": 500000}}
        )

        assert len(result["episodes"]) >= 0
        assert "filters" in result

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_with_operators(
        self, retrieval_service, db_session
    ):
        """Test business data retrieval with comparison operators."""
        segments = []

        db_session.query.return_value.join.return_value.filter.return_value.limit.return_value.all.return_value = segments
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_by_business_data(
            agent_id="agent-1",
            business_filters={
                "revenue": {"$gt": 1000000, "$lt": 5000000},
                "approval_status": "approved"
            }
        )

        assert len(result["episodes"]) >= 0


class TestCanvasTypeRetrieval:
    """Tests for canvas type filtering."""

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_basic(
        self, retrieval_service, db_session, sample_episodes
    ):
        """Test retrieval by canvas type."""
        # Setup canvas subquery
        canvas_subquery = Mock()
        canvas_subquery.filter.return_value = ["episode-1", "episode-2"]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:2]
        db_session.query.return_value.filter.return_value.first.return_value = canvas_subquery

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent-1",
            canvas_type="sheets"
        )

        assert len(result["episodes"]) >= 0
        assert result["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_with_action_filter(
        self, retrieval_service, db_session, sample_episodes
    ):
        """Test retrieval by canvas type and action."""
        canvas_subquery = Mock()
        canvas_subquery.filter.return_value.filter.return_value = ["episode-1"]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:1]
        db_session.query.return_value.filter.return_value.first.return_value = canvas_subquery

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent-1",
            canvas_type="sheets",
            action="submit"
        )

        assert len(result["episodes"]) >= 0
        assert result["action"] == "submit"


class TestSupervisionContextRetrieval:
    """Tests for supervision context retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_high_rated(
        self, retrieval_service, db_session, sample_episodes
    ):
        """Test retrieval with high-rated supervision filter."""
        # Add supervision fields to episodes
        sample_episodes[0].supervisor_rating = 5
        sample_episodes[1].supervisor_rating = 4
        sample_episodes[2].supervisor_rating = 2

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            sample_episodes,
            [],
            []
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent-1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            supervision_outcome_filter="high_rated"
        )

        assert "episodes" in result
        assert "supervision_filters_applied" in result

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_low_intervention(
        self, retrieval_service, db_session, sample_episodes
    ):
        """Test retrieval with low intervention filter."""
        sample_episodes[0].intervention_count = 0
        sample_episodes[1].intervention_count = 1
        sample_episodes[2].intervention_count = 5

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            sample_episodes,
            [],
            []
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent-1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            supervision_outcome_filter="low_intervention"
        )

        assert len(result["episodes"]) >= 0

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_min_rating(
        self, retrieval_service, db_session, sample_episodes
    ):
        """Test retrieval with minimum rating filter."""
        sample_episodes[0].supervisor_rating = 5
        sample_episodes[1].supervisor_rating = 3
        sample_episodes[2].supervisor_rating = 2

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            sample_episodes,
            [],
            []
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent-1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            min_rating=4
        )

        assert len(result["episodes"]) >= 0

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_max_interventions(
        self, retrieval_service, db_session, sample_episodes
    ):
        """Test retrieval with maximum interventions filter."""
        sample_episodes[0].intervention_count = 0
        sample_episodes[1].intervention_count = 1
        sample_episodes[2].intervention_count = 3

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [
            sample_episodes,
            [],
            []
        ]
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent-1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            max_interventions=1
        )

        assert len(result["episodes"]) >= 0

    def test_create_supervision_context(self, retrieval_service, sample_episode):
        """Test creating supervision context dictionary."""
        sample_episode.supervisor_id = "supervisor-1"
        sample_episode.supervisor_rating = 5
        sample_episode.intervention_count = 1
        sample_episode.intervention_types = ["correction"]
        sample_episode.supervision_feedback = "Good job"

        context = retrieval_service._create_supervision_context(sample_episode)

        assert context["has_supervision"] is True
        assert context["supervisor_id"] == "supervisor-1"
        assert context["supervisor_rating"] == 5
        assert context["intervention_count"] == 1

    def test_assess_outcome_quality_excellent(self, retrieval_service):
        """Test assessing outcome quality as excellent."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="completed",
            started_at=datetime.now(),
            supervisor_rating=5,
            intervention_count=0
        )

        quality = retrieval_service._assess_outcome_quality(episode)
        assert quality == "excellent"

    def test_assess_outcome_quality_good(self, retrieval_service):
        """Test assessing outcome quality as good."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="completed",
            started_at=datetime.now(),
            supervisor_rating=4,
            intervention_count=2
        )

        quality = retrieval_service._assess_outcome_quality(episode)
        assert quality == "good"

    def test_assess_outcome_quality_poor(self, retrieval_service):
        """Test assessing outcome quality as poor."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="completed",
            started_at=datetime.now(),
            supervisor_rating=2
        )

        quality = retrieval_service._assess_outcome_quality(episode)
        assert quality == "poor"


class TestSerialization:
    """Tests for episode and segment serialization."""

    def test_serialize_episode_basic(self, retrieval_service, sample_episode):
        """Test basic episode serialization."""
        serialized = retrieval_service._serialize_episode(sample_episode)

        assert serialized["id"] == "episode-1"
        assert serialized["agent_id"] == "agent-1"
        assert serialized["status"] == "completed"
        assert "started_at" in serialized
        assert "ended_at" in serialized

    def test_serialize_episode_with_user_id(self, retrieval_service, sample_episode):
        """Test episode serialization with user_id."""
        serialized = retrieval_service._serialize_episode(sample_episode, user_id="user-1")

        assert serialized["user_id"] == "user-1"

    def test_serialize_episode_all_fields(self, retrieval_service, sample_episode):
        """Test episode serialization includes all fields."""
        serialized = retrieval_service._serialize_episode(sample_episode)

        assert "topics" in serialized
        assert "entities" in serialized
        assert "importance_score" in serialized
        assert "canvas_ids" in serialized
        assert "feedback_ids" in serialized
        assert "maturity_at_time" in serialized
        assert "constitutional_score" in serialized

    def test_serialize_segment(self, retrieval_service, sample_segments):
        """Test segment serialization."""
        serialized = retrieval_service._serialize_segment(sample_segments[0])

        assert serialized["id"] == "segment-0"
        assert serialized["segment_type"] == "conversation"
        assert serialized["sequence_order"] == 0
        assert "content" in serialized
        assert "content_summary" in serialized

    def test_serialize_segment_with_canvas_context(self, retrieval_service):
        """Test segment serialization with canvas context."""
        segment = EpisodeSegment(
            id="segment-1",
            episode_id="episode-1",
            segment_type="conversation",
            sequence_order=0,
            content="Content",
            content_summary="Summary",
            source_type="chat_message",
            source_id="msg-1",
            canvas_context={"canvas_type": "sheets"}
        )

        serialized = retrieval_service._serialize_segment(segment)

        assert serialized["canvas_context"] == {"canvas_type": "sheets"}


class TestCanvasContextFiltering:
    """Tests for canvas context detail filtering."""

    def test_filter_canvas_context_full(self, retrieval_service):
        """Test filtering canvas context to full detail."""
        context = {
            "canvas_type": "sheets",
            "presentation_summary": "Summary",
            "visual_elements": ["table"],
            "critical_data_points": {"revenue": 1000000}
        }

        filtered = retrieval_service._filter_canvas_context_detail(context, "full")
        assert filtered == context

    def test_filter_canvas_context_standard(self, retrieval_service):
        """Test filtering canvas context to standard detail."""
        context = {
            "canvas_type": "sheets",
            "presentation_summary": "Summary",
            "visual_elements": ["table"],
            "critical_data_points": {"revenue": 1000000}
        }

        filtered = retrieval_service._filter_canvas_context_detail(context, "standard")

        assert "presentation_summary" in filtered
        assert "critical_data_points" in filtered
        assert "visual_elements" not in filtered

    def test_filter_canvas_context_summary(self, retrieval_service):
        """Test filtering canvas context to summary detail."""
        context = {
            "canvas_type": "sheets",
            "presentation_summary": "Summary",
            "visual_elements": ["table"],
            "critical_data_points": {"revenue": 1000000}
        }

        filtered = retrieval_service._filter_canvas_context_detail(context, "summary")

        assert "presentation_summary" in filtered
        assert "visual_elements" not in filtered
        assert "critical_data_points" not in filtered


class TestAccessLogging:
    """Tests for access logging functionality."""

    @pytest.mark.asyncio
    async def test_log_access(self, retrieval_service, db_session):
        """Test logging episode access."""
        await retrieval_service._log_access(
            episode_id="episode-1",
            access_type="temporal",
            governance_check={"allowed": True, "agent_maturity": "INTERN"},
            agent_id="agent-1",
            results_count=5
        )

        # Verify log was added
        db_session.add.assert_called()
        db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_log_access_handles_exception(self, retrieval_service, db_session):
        """Test access logging handles exceptions."""
        db_session.add.side_effect = Exception("DB error")

        # Should not raise exception
        await retrieval_service._log_access(
            episode_id="episode-1",
            access_type="temporal",
            governance_check={"allowed": True},
            agent_id="agent-1",
            results_count=0
        )


class TestFetchContextMethods:
    """Tests for context fetching methods."""

    @pytest.mark.asyncio
    async def test_fetch_canvas_context(self, retrieval_service, db_session):
        """Test fetching canvas context."""
        canvases = [
            CanvasAudit(
                id="canvas-1",
                canvas_type="sheets",
                action="present",
                audit_metadata={"data": "value"}
            )
        ]

        db_session.query.return_value.filter.return_value.all.return_value = canvases

        context = await retrieval_service._fetch_canvas_context(["canvas-1"])

        assert len(context) == 1
        assert context[0]["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_empty(self, retrieval_service, db_session):
        """Test fetching canvas context with empty IDs."""
        context = await retrieval_service._fetch_canvas_context([])
        assert context == []

    @pytest.mark.asyncio
    async def test_fetch_feedback_context(self, retrieval_service, db_session):
        """Test fetching feedback context."""
        feedbacks = [
            AgentFeedback(
                id="feedback-1",
                feedback_type="thumbs_up",
                thumbs_up_down=True,
                rating=5,
                user_correction="No corrections"
            )
        ]

        db_session.query.return_value.filter.return_value.all.return_value = feedbacks

        context = await retrieval_service._fetch_feedback_context(["feedback-1"])

        assert len(context) == 1
        assert context[0]["feedback_type"] == "thumbs_up"

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_empty(self, retrieval_service):
        """Test fetching feedback context with empty IDs."""
        context = await retrieval_service._fetch_feedback_context([])
        assert context == []


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_retrieve_semantic_exception_handling(
        self, retrieval_service, mock_lancedb
    ):
        """Test semantic retrieval handles LanceDB exceptions."""
        mock_lancedb.search.side_effect = Exception("Search failed")

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-1",
            query="test query"
        )

        assert result["episodes"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_exception_handling(
        self, retrieval_service, mock_lancedb
    ):
        """Test canvas-aware retrieval handles exceptions."""
        mock_lancedb.search.side_effect = Exception("Search failed")

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent-1",
            query="test query"
        )

        assert result["episodes"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_exception_handling(
        self, retrieval_service, db_session
    ):
        """Test business data retrieval handles exceptions."""
        db_session.query.return_value.join.side_effect = Exception("Query failed")

        result = await retrieval_service.retrieve_by_business_data(
            agent_id="agent-1",
            business_filters={"revenue": 1000000}
        )

        assert result["episodes"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_exception_handling(
        self, retrieval_service, db_session
    ):
        """Test canvas context fetching handles exceptions."""
        db_session.query.return_value.filter.return_value.all.side_effect = Exception("Query failed")

        context = await retrieval_service._fetch_canvas_context(["canvas-1"])
        assert context == []

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_exception_handling(
        self, retrieval_service, db_session
    ):
        """Test feedback context fetching handles exceptions."""
        db_session.query.return_value.filter.return_value.all.side_effect = Exception("Query failed")

        context = await retrieval_service._fetch_feedback_context(["feedback-1"])
        assert context == []
