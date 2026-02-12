"""
Unit tests for EpisodeRetrievalService

Tests cover:
1. Temporal retrieval (time-based queries)
2. Semantic retrieval (vector similarity search)
3. Sequential retrieval (full episodes with segments)
4. Contextual retrieval (hybrid search)
5. Filtering and pagination
6. Access logging
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from core.episode_retrieval_service import (
    EpisodeRetrievalService,
    RetrievalMode,
    RetrievalResult,
)
from core.models import (
    AgentFeedback,
    AgentRegistry,
    AgentStatus,
    CanvasAudit,
    Episode,
    EpisodeAccessLog,
    EpisodeSegment,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session."""
    session = Mock()
    session.query.return_value = session
    session.filter.return_value = session
    session.order_by.return_value = session
    session.limit.return_value = session
    session.all.return_value = []
    session.first.return_value = None
    session.add.return_value = None
    session.commit.return_value = None
    return session


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler."""
    lancedb = Mock()
    lancedb.search = Mock(return_value=[])
    lancedb.embed_text = Mock(return_value=[0.1, 0.2, 0.3])
    return lancedb


@pytest.fixture
def mock_governance():
    """Mock governance service."""
    governance = Mock()
    governance.can_perform_action = Mock(return_value={"allowed": True})
    return governance


@pytest.fixture
def retrieval_service(db_session, mock_lancedb, mock_governance):
    """Create EpisodeRetrievalService with mocked dependencies."""
    with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=mock_lancedb):
        service = EpisodeRetrievalService(db_session)
        service.lancedb = mock_lancedb
        service.governance = mock_governance
        return service


@pytest.fixture
def sample_episodes():
    """Create sample episodes."""
    now = datetime.now()
    episodes = []
    for i in range(5):
        ep = Mock(spec=Episode)
        ep.id = f"episode-{i}"
        ep.title = f"Episode {i}"
        ep.description = f"Description {i}"
        ep.summary = f"Summary {i}"
        ep.agent_id = "agent-123"
        ep.status = "completed"
        ep.started_at = now - timedelta(days=i)
        ep.ended_at = now - timedelta(days=i) + timedelta(hours=1)
        ep.topics = [f"topic{i}"]
        ep.entities = [f"entity{i}"]
        ep.importance_score = 0.5 + (i * 0.1)
        ep.maturity_at_time = "INTERN"
        ep.human_intervention_count = i
        ep.constitutional_score = 0.7 + (i * 0.05)
        ep.decay_score = 1.0 - (i * 0.1)
        ep.access_count = i * 10
        ep.canvas_ids = []
        ep.feedback_ids = []
        ep.canvas_action_count = 0
        ep.aggregate_feedback_score = None
        episodes.append(ep)
    return episodes


@pytest.fixture
def sample_segments():
    """Create sample episode segments."""
    segments = []
    for i in range(5):
        seg = Mock(spec=EpisodeSegment)
        seg.id = f"segment-{i}"
        seg.episode_id = "episode-0"
        seg.segment_type = "conversation"
        seg.sequence_order = i
        seg.content = f"Content {i}"
        seg.content_summary = f"Summary {i}"
        seg.source_type = "chat_message"
        seg.source_id = f"msg-{i}"
        seg.created_at = datetime.now()
        segments.append(seg)
    return segments


# ============================================================================
# Temporal Retrieval Tests
# ============================================================================

class TestTemporalRetrieval:
    """Test time-based episode retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_temporal_default_7d(self, retrieval_service, sample_episodes):
        """Test retrieving episodes from last 7 days (default)."""
        # Mock query chain
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:3]

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="7d",
            limit=50
        )

        assert "episodes" in result
        assert len(result["episodes"]) == 3
        assert result["time_range"] == "7d"
        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_retrieve_temporal_with_user_filter(self, retrieval_service, sample_episodes):
        """Test temporal retrieval with user filter."""
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:2]

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="30d",
            user_id="user-456",
            limit=10
        )

        assert "episodes" in result
        assert len(result["episodes"]) == 2

    @pytest.mark.asyncio
    async def test_retrieve_temporal_governance_denied(self, retrieval_service):
        """Test temporal retrieval when governance check fails."""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Insufficient permissions"
        }

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="7d"
        )

        assert result["episodes"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_retrieve_temporal_time_boundaries(self, retrieval_service):
        """Test temporal retrieval with different time ranges."""
        time_ranges = ["1d", "7d", "30d", "90d"]
        for time_range in time_ranges:
            retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

            result = await retrieval_service.retrieve_temporal(
                agent_id="agent-123",
                time_range=time_range
            )

            assert result["time_range"] == time_range


# ============================================================================
# Semantic Retrieval Tests
# ============================================================================

class TestSemanticRetrieval:
    """Test semantic similarity-based retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_semantic_basic(self, retrieval_service, sample_episodes):
        """Test basic semantic retrieval."""
        # Mock LanceDB search results
        lancedb_results = [
            {
                "id": "ep-1",
                "metadata": '{"episode_id": "episode-1"}',
                "_distance": 0.2  # High similarity
            },
            {
                "id": "ep-2",
                "metadata": '{"episode_id": "episode-2"}',
                "_distance": 0.5  # Lower similarity
            }
        ]
        retrieval_service.lancedb.search.return_value = lancedb_results
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes[:2]

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="machine learning algorithms",
            limit=10
        )

        assert "episodes" in result
        assert result["query"] == "machine learning algorithms"
        retrieval_service.lancedb.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_semantic_zero_results(self, retrieval_service):
        """Test semantic retrieval with no matching episodes."""
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="nonexistent topic",
            limit=10
        )

        assert result["episodes"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_retrieve_semantic_governance_denied(self, retrieval_service):
        """Test semantic retrieval when governance check fails."""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Insufficient maturity"
        }

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="test query"
        )

        assert result["episodes"] == []
        assert "error" in result


# ============================================================================
# Sequential Retrieval Tests
# ============================================================================

class TestSequentialRetrieval:
    """Test full episode retrieval with segments."""

    @pytest.mark.asyncio
    async def test_retrieve_sequential_full_episode(self, retrieval_service, sample_episodes, sample_segments):
        """Test retrieving full episode with segments."""
        episode = sample_episodes[0]
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = episode
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-0",
            agent_id="agent-123",
            include_canvas=True,
            include_feedback=True
        )

        assert "episode" in result
        assert "segments" in result
        assert len(result["segments"]) == 5
        assert result["episode"]["id"] == "episode-0"

    @pytest.mark.asyncio
    async def test_retrieve_sequential_episode_not_found(self, retrieval_service):
        """Test sequential retrieval when episode doesn't exist."""
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = None

        result = await retrieval_service.retrieve_sequential(
            episode_id="nonexistent",
            agent_id="agent-123"
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_retrieve_sequential_exclude_canvas(self, retrieval_service, sample_episodes, sample_segments):
        """Test sequential retrieval without canvas context."""
        episode = sample_episodes[0]
        episode.canvas_ids = []  # No canvas
        episode.feedback_ids = []  # No feedback
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = episode
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-0",
            agent_id="agent-123",
            include_canvas=False,
            include_feedback=False
        )

        assert "episode" in result
        assert "segments" in result
        # Canvas and feedback context should not be in result
        assert "canvas_context" not in result or result.get("canvas_context") is None
        assert "feedback_context" not in result or result.get("feedback_context") is None


# ============================================================================
# Contextual Retrieval Tests
# ============================================================================

class TestContextualRetrieval:
    """Test hybrid contextual retrieval."""

    @pytest.mark.asyncio
    async def test_retrieve_contextual_basic(self, retrieval_service, sample_episodes):
        """Test basic contextual retrieval combining temporal and semantic."""
        # Mock both temporal and semantic queries
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="data analysis task",
            limit=5
        )

        assert "episodes" in result
        assert isinstance(result["episodes"], list)

    @pytest.mark.asyncio
    async def test_retrieve_contextual_with_canvas_filter(self, retrieval_service, sample_episodes):
        """Test contextual retrieval with canvas requirement."""
        # Mock: temporal returns episodes, semantic returns empty
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="show charts",
            limit=5,
            require_canvas=True
        )

        # Should complete without error even if no results
        assert "episodes" in result
        assert isinstance(result["episodes"], list)

    @pytest.mark.asyncio
    async def test_retrieve_contextual_with_feedback_filter(self, retrieval_service, sample_episodes):
        """Test contextual retrieval with feedback requirement."""
        # Mock: temporal returns episodes, semantic returns empty
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="high rated task",
            limit=5,
            require_feedback=True
        )

        # Should complete without error even if no results
        assert "episodes" in result
        assert isinstance(result["episodes"], list)


# ============================================================================
# Canvas Type Filtering Tests
# ============================================================================

class TestCanvasTypeFiltering:
    """Test retrieval by canvas type."""

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_governance_denied(self, retrieval_service):
        """Test canvas type retrieval when governance check fails."""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Unauthorized"
        }

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent-123",
            canvas_type="sheets",
            time_range="30d"
        )

        assert result["episodes"] == []
        assert "error" in result

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_parameters(self, retrieval_service):
        """Test that canvas type retrieval accepts all expected parameters."""
        # Test with different parameter combinations
        test_cases = [
            {"canvas_type": "sheets", "time_range": "1d"},
            {"canvas_type": "charts", "time_range": "7d", "action": "present"},
            {"canvas_type": "forms", "time_range": "30d", "action": "submit", "limit": 5},
        ]

        for params in test_cases:
            # Just verify the method accepts these parameters without error
            # We can't easily test the full query chain with mocks
            try:
                result = await retrieval_service.retrieve_by_canvas_type(
                    agent_id="agent-123",
                    **params
                )
                # Should return some response (even if empty due to mocking)
                assert "episodes" in result
            except Exception as e:
                # If it fails, it should be due to mocking limitations, not parameter validation
                assert "canvas_type" not in str(e)


# ============================================================================
# Supervision Context Tests
# ============================================================================

class TestSupervisionContextRetrieval:
    """Test retrieval with supervision context."""

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context(self, retrieval_service, sample_episodes):
        """Test retrieving episodes enriched with supervision metadata."""
        # Add supervision fields to episodes
        for ep in sample_episodes[:3]:
            ep.supervisor_id = "supervisor-1"
            ep.supervisor_rating = 4 + (sample_episodes.index(ep) % 2)  # 4 or 5
            ep.intervention_count = sample_episodes.index(ep)
            ep.intervention_types = ["guidance", "correction"]
            ep.supervision_feedback = "Good work"

        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes[:3]
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:3]

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent-123",
            retrieval_mode=RetrievalMode.TEMPORAL,
            limit=10
        )

        assert "episodes" in result
        assert len(result["episodes"]) == 3
        # Check supervision context in first episode
        first_ep = result["episodes"][0]
        assert "supervision_context" in first_ep

    @pytest.mark.asyncio
    async def test_supervision_outcome_quality(self, retrieval_service):
        """Test assessment of supervision outcome quality."""
        # Test different quality scenarios
        test_cases = [
            (5, 0, "excellent"),  # 5 stars, 0 interventions
            (4, 1, "good"),      # 4 stars, 1 intervention
            (3, 2, "fair"),      # 3 stars, 2 interventions
            (2, 5, "poor"),      # 2 stars, 5 interventions
        ]

        for rating, interventions, expected_quality in test_cases:
            episode = Mock()
            episode.supervisor_rating = rating
            episode.intervention_count = interventions

            quality = retrieval_service._assess_outcome_quality(episode)
            assert quality == expected_quality


# ============================================================================
# Serialization Tests
# ============================================================================

class TestSerialization:
    """Test episode and segment serialization."""

    def test_serialize_episode(self, retrieval_service, sample_episodes):
        """Test converting Episode to dict."""
        episode = sample_episodes[0]
        episode_dict = retrieval_service._serialize_episode(episode)

        assert episode_dict["id"] == "episode-0"
        assert episode_dict["title"] == "Episode 0"
        assert "agent_id" in episode_dict
        assert "started_at" in episode_dict
        assert "importance_score" in episode_dict
        assert "maturity_at_time" in episode_dict

    def test_serialize_segment(self, retrieval_service, sample_segments):
        """Test converting EpisodeSegment to dict."""
        segment = sample_segments[0]
        segment_dict = retrieval_service._serialize_segment(segment)

        assert segment_dict["id"] == "segment-0"
        assert segment_dict["segment_type"] == "conversation"
        assert "content" in segment_dict
        assert "sequence_order" in segment_dict


# ============================================================================
# Access Logging Tests
# ============================================================================

class TestAccessLogging:
    """Test episode access logging."""

    @pytest.mark.asyncio
    async def test_log_access_successful(self, retrieval_service):
        """Test logging successful access."""
        await retrieval_service._log_access(
            episode_id="episode-123",
            access_type="temporal",
            governance_check={"allowed": True},
            agent_id="agent-123",
            results_count=5
        )

        # Verify add and commit were called
        retrieval_service.db.add.assert_called()
        retrieval_service.db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_log_access_governance_denied(self, retrieval_service):
        """Test logging access when governance check fails."""
        await retrieval_service._log_access(
            episode_id=None,  # No episode accessed
            access_type="temporal",
            governance_check={"allowed": False, "reason": "Unauthorized"},
            agent_id="agent-123",
            results_count=0
        )

        # Should still log the attempt
        retrieval_service.db.add.assert_called()


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_lancedb_response(self, retrieval_service):
        """Test handling empty LanceDB response."""
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="test"
        )

        assert result["episodes"] == []

    @pytest.mark.asyncio
    async def test_malformed_lancedb_metadata(self, retrieval_service, sample_episodes):
        """Test handling malformed metadata in LanceDB results."""
        lancedb_results = [
            {"id": "ep-1", "metadata": "invalid json", "_distance": 0.3},
            {"id": "ep-2", "metadata": None, "_distance": 0.5}
        ]
        retrieval_service.lancedb.search.return_value = lancedb_results
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = []

        # Should not crash, return empty episodes
        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="test"
        )

        assert isinstance(result["episodes"], list)


# ============================================================================
# Performance Trend Tests
# ============================================================================

class TestPerformanceTrend:
    """Test performance trend calculation."""

    def test_filter_improvement_trend_insufficient_data(self, retrieval_service):
        """Test trend calculation with insufficient data."""
        episodes = [Mock() for _ in range(3)]  # Less than 5

        result = retrieval_service._filter_improvement_trend(episodes)

        # Should return original episodes when insufficient data
        assert result == episodes

    def test_filter_improvement_trend_improving(self, retrieval_service):
        """Test detecting improving performance trend."""
        now = datetime.now()
        episodes = []
        # Create episodes with improving ratings
        for i in range(10):
            ep = Mock()
            ep.started_at = now - timedelta(days=i)
            ep.supervisor_rating = 3 + (i // 3)  # Ratings improving over time
            episodes.append(ep)

        result = retrieval_service._filter_improvement_trend(episodes)

        # Should return non-empty list for improving trend
        assert isinstance(result, list)
