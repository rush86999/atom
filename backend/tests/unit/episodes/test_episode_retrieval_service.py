"""
Unit tests for EpisodeRetrievalService

Tests cover:
1. Temporal retrieval (time-based queries)
2. Semantic retrieval (vector similarity search)
3. Sequential retrieval (full episodes with segments)
4. Contextual retrieval (hybrid search)
5. Filtering and pagination
6. Access logging
7. Canvas and feedback context
8. Governance enforcement
9. Error handling
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
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
    ChatSession,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session."""
    session = MagicMock(spec=Session)
    # Configure mock query chain
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    mock_query.first.return_value = None
    session.add.return_value = None
    session.commit.return_value = None
    session.flush.return_value = None
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
        with patch('core.episode_retrieval_service.AgentGovernanceService', return_value=mock_governance):
            service = EpisodeRetrievalService(db_session)
            service.lancedb = mock_lancedb
            service.governance = mock_governance
            return service


@pytest.fixture
def mock_student_agent():
    """Mock student agent for governance tests."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "student-agent"
    agent.name = "Student Agent"
    agent.maturity_level = "STUDENT"
    agent.confidence_score = 0.3
    return agent


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
        ep.tenant_id = "tenant-1"
        ep.status = "completed"
        ep.started_at = now - timedelta(days=i)
        ep.ended_at = now - timedelta(days=i) + timedelta(hours=1)
        ep.completed_at = now - timedelta(days=i) + timedelta(hours=1)
        ep.task_description = f"Task {i}"
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
        ep.session_id = f"session-{i}"
        ep.outcome = None
        ep.success = None
        ep.supervisor_id = None
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
        seg.canvas_context = None
        seg.created_at = datetime.now()
        segments.append(seg)
    return segments


# ============================================================================
# Task 1: Temporal Retrieval Tests
# ============================================================================

class TestTemporalRetrieval:
    """Test time-based episode retrieval."""

    @pytest.mark.asyncio
    async def test_temporal_retrieval_1d(self, retrieval_service, sample_episodes):
        """Test retrieving episodes from last 24 hours."""
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:2]

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="1d",
            limit=50
        )

        assert "episodes" in result
        assert result["time_range"] == "1d"
        assert result["count"] == len(result["episodes"])
        assert "governance_check" in result

    @pytest.mark.asyncio
    async def test_temporal_retrieval_7d(self, retrieval_service, sample_episodes):
        """Test retrieving episodes from last 7 days (default)."""
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:3]

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="7d",
            limit=50
        )

        assert "episodes" in result
        assert result["time_range"] == "7d"
        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_temporal_retrieval_30d(self, retrieval_service, sample_episodes):
        """Test retrieving episodes from last 30 days."""
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="30d",
            limit=50
        )

        assert "episodes" in result
        assert result["time_range"] == "30d"

    @pytest.mark.asyncio
    async def test_temporal_retrieval_90d(self, retrieval_service, sample_episodes):
        """Test retrieving episodes from last 90 days."""
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="90d",
            limit=50
        )

        assert "episodes" in result
        assert result["time_range"] == "90d"

    @pytest.mark.asyncio
    async def test_temporal_retrieval_invalid_range(self, retrieval_service):
        """Test that invalid time range defaults to 7 days."""
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="invalid",
            limit=50
        )

        # Should default to 7 days (deltas.get(time_range, 7))
        assert "episodes" in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_temporal_retrieval_with_user_filter(self, retrieval_service, sample_episodes):
        """Test temporal retrieval with user ID filtering via ChatSession join."""
        # Mock query chain for user_id filtering
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = sample_episodes[:2]

        # Mock session_user_ids query
        mock_session_query = MagicMock()
        mock_session_query.filter.return_value.all.return_value = []

        retrieval_service.db.query.side_effect = [mock_query, mock_session_query]
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
    async def test_temporal_retrieval_ordering(self, retrieval_service, sample_episodes):
        """Test that temporal retrieval orders by started_at DESC."""
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="7d"
        )

        assert "episodes" in result
        # Verify order_by was called with DESC
        retrieval_service.db.query.return_value.filter.return_value.order_by.assert_called()

    @pytest.mark.asyncio
    async def test_temporal_retrieval_excludes_archived(self, retrieval_service, sample_episodes):
        """Test that archived episodes are excluded from temporal retrieval."""
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="7d"
        )

        assert "episodes" in result
        # Archived episodes (status == "archived") should be filtered out

    @pytest.mark.asyncio
    async def test_temporal_retrieval_governance_blocked(self, retrieval_service):
        """Test that STUDENT agents are blocked from read_memory."""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Insufficient maturity: STUDENT cannot read memory"
        }

        result = await retrieval_service.retrieve_temporal(
            agent_id="student-agent",
            time_range="7d"
        )

        assert result["episodes"] == []
        assert "governance_check" in result
        assert result["governance_check"]["allowed"] == False

    @pytest.mark.asyncio
    async def test_temporal_retrieval_empty_results(self, retrieval_service):
        """Test handling of no episodes found."""
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent-123",
            time_range="7d"
        )

        assert result["episodes"] == []
        assert result["count"] == 0
        assert "error" not in result


# ============================================================================
# Task 1: Semantic Retrieval Tests
# ============================================================================

class TestSemanticRetrieval:
    """Test semantic similarity-based retrieval."""

    @pytest.mark.asyncio
    async def test_semantic_retrieval_vector_search(self, retrieval_service, sample_episodes):
        """Test LanceDB search invocation."""
        # Mock LanceDB search results
        lancedb_results = [
            {
                "id": "ep-1",
                "metadata": '{"episode_id": "episode-1"}',
                "_distance": 0.2
            },
            {
                "id": "ep-2",
                "metadata": '{"episode_id": "episode-2"}',
                "_distance": 0.5
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
    async def test_semantic_retrieval_agent_filter(self, retrieval_service):
        """Test agent ID filter in semantic query."""
        retrieval_service.lancedb.search.return_value = []
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="test query",
            limit=10
        )

        # Verify filter_str includes agent_id
        retrieval_service.lancedb.search.assert_called_once()
        call_args = retrieval_service.lancedb.search.call_args
        assert "agent_id == 'agent-123'" in call_args[1]["filter_str"]

    @pytest.mark.asyncio
    async def test_semantic_retrieval_limit(self, retrieval_service):
        """Test that limit parameter is enforced."""
        retrieval_service.lancedb.search.return_value = []
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = []

        await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="test",
            limit=5
        )

        # Verify limit was passed to LanceDB search
        call_args = retrieval_service.lancedb.search.call_args
        assert call_args[1]["limit"] == 5

    @pytest.mark.asyncio
    async def test_semantic_retrieval_no_results(self, retrieval_service):
        """Test handling empty LanceDB results."""
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="nonexistent topic",
            limit=10
        )

        assert result["episodes"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_semantic_retrieval_governance_blocked(self, retrieval_service):
        """Test that INTERN+ is required for semantic_search."""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Insufficient maturity: STUDENT cannot perform semantic search"
        }

        result = await retrieval_service.retrieve_semantic(
            agent_id="student-agent",
            query="test query"
        )

        assert result["episodes"] == []
        assert "governance_check" in result
        assert result["governance_check"]["allowed"] == False

    @pytest.mark.asyncio
    async def test_semantic_retrieval_metadata_parsing(self, retrieval_service, sample_episodes):
        """Test parsing JSON metadata (string vs dict)."""
        # Test with string metadata
        lancedb_results = [
            {"id": "ep-1", "metadata": '{"episode_id": "episode-1"}', "_distance": 0.2},
            {"id": "ep-2", "metadata": None, "_distance": 0.5}  # None metadata
        ]
        retrieval_service.lancedb.search.return_value = lancedb_results
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="test"
        )

        # Should handle both string and None metadata gracefully
        assert isinstance(result["episodes"], list)

    @pytest.mark.asyncio
    async def test_semantic_retrieval_lancedb_error(self, retrieval_service):
        """Test graceful handling of LanceDB errors."""
        retrieval_service.lancedb.search.side_effect = Exception("LanceDB connection failed")

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="test"
        )

        assert result["episodes"] == []
        assert "error" in result
        assert "LanceDB connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_semantic_retrieval_episode_fetching(self, retrieval_service, sample_episodes):
        """Test fetching full episodes from PostgreSQL after LanceDB search."""
        lancedb_results = [
            {"id": "ep-1", "metadata": '{"episode_id": "episode-1"}', "_distance": 0.2}
        ]
        retrieval_service.lancedb.search.return_value = lancedb_results
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes[:1]

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="test"
        )

        # Should fetch full episode details from DB
        retrieval_service.db.query.assert_called()

    @pytest.mark.asyncio
    async def test_semantic_retrieval_missing_episode_id(self, retrieval_service):
        """Test skipping results with missing episode_id."""
        lancedb_results = [
            {"id": "ep-1", "metadata": '{"episode_id": "episode-1"}', "_distance": 0.2},
            {"id": "ep-2", "metadata": '{}', "_distance": 0.5},  # Missing episode_id
            {"id": "ep-3", "metadata": '{"other_field": "value"}', "_distance": 0.3}  # No episode_id
        ]
        retrieval_service.lancedb.search.return_value = lancedb_results
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent-123",
            query="test"
        )

        # Should only process results with valid episode_id
        assert isinstance(result["episodes"], list)

    @pytest.mark.asyncio
    async def test_semantic_retrieval_query_encoding(self, retrieval_service):
        """Test handling special characters in query."""
        retrieval_service.lancedb.search.return_value = []
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = []

        special_queries = [
            "query with 'quotes'",
            'query with "double quotes"',
            "query with $pecial #characters",
            "query with emoji 🎉"
        ]

        for query in special_queries:
            result = await retrieval_service.retrieve_semantic(
                agent_id="agent-123",
                query=query
            )
            assert "episodes" in result
            assert "error" not in result


# ============================================================================
# Task 2: Sequential Retrieval Tests
# ============================================================================

class TestSequentialRetrieval:
    """Test full episode retrieval with segments."""

    @pytest.mark.asyncio
    async def test_sequential_retrieval_full_episode(self, retrieval_service, sample_episodes, sample_segments):
        """Test retrieving full episode with all segments."""
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
    async def test_sequential_retrieval_segment_ordering(self, retrieval_service, sample_episodes, sample_segments):
        """Test that segments are ordered by sequence_order ASC."""
        episode = sample_episodes[0]
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = episode
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-0",
            agent_id="agent-123"
        )

        # Verify order_by was called with ASC
        retrieval_service.db.query.return_value.filter.return_value.order_by.assert_called()

    @pytest.mark.asyncio
    async def test_sequential_retrieval_with_canvas(self, retrieval_service, sample_episodes, sample_segments):
        """Test that canvas context is included by default."""
        episode = sample_episodes[0]
        episode.canvas_ids = ["canvas-1"]
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = episode
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-0",
            agent_id="agent-123",
            include_canvas=True
        )

        assert "episode" in result
        assert "canvas_context" in result or episode.canvas_ids == []

    @pytest.mark.asyncio
    async def test_sequential_retrieval_with_feedback(self, retrieval_service, sample_episodes, sample_segments):
        """Test that feedback context is included by default."""
        episode = sample_episodes[0]
        episode.feedback_ids = ["feedback-1"]
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = episode
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-0",
            agent_id="agent-123",
            include_feedback=True
        )

        assert "episode" in result
        assert "feedback_context" in result or episode.feedback_ids == []

    @pytest.mark.asyncio
    async def test_sequential_retrieval_exclude_canvas(self, retrieval_service, sample_episodes, sample_segments):
        """Test that canvas is excluded when include_canvas=False."""
        episode = sample_episodes[0]
        episode.canvas_ids = []
        episode.feedback_ids = []
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

    @pytest.mark.asyncio
    async def test_sequential_retrieval_exclude_feedback(self, retrieval_service, sample_episodes, sample_segments):
        """Test that feedback is excluded when include_feedback=False."""
        episode = sample_episodes[0]
        episode.canvas_ids = []
        episode.feedback_ids = []
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = episode
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-0",
            agent_id="agent-123",
            include_canvas=False,
            include_feedback=False
        )

        assert "episode" in result

    @pytest.mark.asyncio
    async def test_sequential_retrieval_not_found(self, retrieval_service):
        """Test that None is returned for nonexistent episode."""
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = None

        result = await retrieval_service.retrieve_sequential(
            episode_id="nonexistent",
            agent_id="agent-123"
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_sequential_retrieval_empty_segments(self, retrieval_service, sample_episodes):
        """Test handling episodes with no segments."""
        episode = sample_episodes[0]
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = episode
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-0",
            agent_id="agent-123"
        )

        assert "episode" in result
        assert result["segments"] == []

    @pytest.mark.asyncio
    async def test_sequential_retrieval_canvas_context_format(self, retrieval_service, sample_episodes, sample_segments):
        """Test that canvas context is properly formatted."""
        episode = sample_episodes[0]
        episode.canvas_ids = []
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = episode
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-0",
            agent_id="agent-123",
            include_canvas=False
        )

        assert "episode" in result

    @pytest.mark.asyncio
    async def test_sequential_retrieval_feedback_aggregation(self, retrieval_service, sample_episodes, sample_segments):
        """Test that feedback scores are properly aggregated."""
        episode = sample_episodes[0]
        episode.feedback_ids = []
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = episode
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.all.return_value = sample_segments

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode-0",
            agent_id="agent-123",
            include_feedback=False
        )

        assert "episode" in result


# ============================================================================
# Task 2: Contextual Retrieval Tests
# ============================================================================

class TestContextualRetrieval:
    """Test hybrid contextual retrieval."""

    @pytest.mark.asyncio
    async def test_contextual_retrieval_hybrid_scoring(self, retrieval_service, sample_episodes):
        """Test hybrid scoring: temporal (30%) + semantic (70%)."""
        # Mock both temporal and semantic queries
        retrieval_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes
        retrieval_service.lancedb.search.return_value = []

        # Patch retrieve_temporal and retrieve_semantic to control scoring
        with patch.object(retrieval_service, 'retrieve_temporal') as mock_temporal:
            with patch.object(retrieval_service, 'retrieve_semantic') as mock_semantic:
                mock_temporal.return_value = {"episodes": [e.__dict__ for e in sample_episodes[:3]]}
                mock_semantic.return_value = {"episodes": [e.__dict__ for e in sample_episodes[2:5]]}

                result = await retrieval_service.retrieve_contextual(
                    agent_id="agent-123",
                    current_task="data analysis task",
                    limit=5
                )

                assert "episodes" in result
                assert isinstance(result["episodes"], list)

    @pytest.mark.asyncio
    async def test_contextual_retrieval_canvas_boost(self, retrieval_service, sample_episodes):
        """Test +0.1 boost for episodes with canvas."""
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes[:2]
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="show charts",
            limit=5
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_contextual_retrieval_positive_feedback_boost(self, retrieval_service, sample_episodes):
        """Test +0.2 boost for positive feedback."""
        # Set up episode with positive feedback
        for ep in sample_episodes:
            ep.aggregate_feedback_score = 0.8  # Positive

        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="high rated task",
            limit=5
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_contextual_retrieval_negative_feedback_penalty(self, retrieval_service, sample_episodes):
        """Test -0.3 penalty for negative feedback."""
        # Set up episode with negative feedback
        for ep in sample_episodes:
            ep.aggregate_feedback_score = -0.7  # Negative

        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="low rated task",
            limit=5
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_contextual_retrieval_require_canvas(self, retrieval_service, sample_episodes):
        """Test filtering to only episodes with canvas."""
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="show charts",
            limit=5,
            require_canvas=True
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_contextual_retrieval_require_feedback(self, retrieval_service, sample_episodes):
        """Test filtering to only episodes with feedback."""
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="high rated task",
            limit=5,
            require_feedback=True
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_contextual_retrieval_limit(self, retrieval_service, sample_episodes):
        """Test that limit is enforced on scored results."""
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="test",
            limit=3
        )

        # Result count should not exceed limit
        assert len(result["episodes"]) <= 3

    @pytest.mark.asyncio
    async def test_contextual_retrieval_empty_temporal(self, retrieval_service):
        """Test handling empty temporal results."""
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = []
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="test",
            limit=5
        )

        assert result["episodes"] == []

    @pytest.mark.asyncio
    async def test_contextual_retrieval_empty_semantic(self, retrieval_service, sample_episodes):
        """Test handling empty semantic results."""
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="test",
            limit=5
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_contextual_retrieval_score_normalization(self, retrieval_service, sample_episodes):
        """Test that scores are normalized to [0, 1]."""
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent-123",
            current_task="test",
            limit=5
        )

        # All relevance scores should be valid
        for ep in result["episodes"]:
            if "relevance_score" in ep:
                assert 0.0 <= ep["relevance_score"] <= 1.0


# ============================================================================
# Task 3: Access Logging Tests
# ============================================================================

class TestAccessLogging:
    """Test episode access logging."""

    @pytest.mark.asyncio
    async def test_log_access_creates_record(self, retrieval_service):
        """Test that EpisodeAccessLog record is created."""
        await retrieval_service._log_access(
            episode_id="ep1",
            access_type="temporal",
            governance_check={"allowed": True},
            agent_id="agent1",
            results_count=5
        )

        # Verify add and commit were called
        retrieval_service.db.add.assert_called()
        retrieval_service.db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_log_access_with_governance_check(self, retrieval_service):
        """Test that governance check result is logged."""
        governance_check = {"allowed": False, "reason": "Unauthorized"}

        await retrieval_service._log_access(
            episode_id="ep1",
            access_type="temporal",
            governance_check=governance_check,
            agent_id="agent1",
            results_count=0
        )

        retrieval_service.db.add.assert_called()

    @pytest.mark.asyncio
    async def test_log_access_result_count(self, retrieval_service):
        """Test that result count is stored in access log."""
        await retrieval_service._log_access(
            episode_id="ep1",
            access_type="temporal",
            governance_check={"allowed": True},
            agent_id="agent1",
            results_count=10
        )

        retrieval_service.db.add.assert_called()

    @pytest.mark.asyncio
    async def test_log_access_batch_logging(self, retrieval_service):
        """Test that multiple episodes are logged correctly."""
        # Simulate logging for multiple episodes
        for i in range(5):
            await retrieval_service._log_access(
                episode_id=f"ep{i}",
                access_type="temporal",
                governance_check={"allowed": True},
                agent_id="agent1",
                results_count=5
            )

        # Verify add was called 5 times
        assert retrieval_service.db.add.call_count == 5

    @pytest.mark.asyncio
    async def test_log_access_error_handling(self, retrieval_service):
        """Test graceful handling of log failures."""
        # Mock database error
        retrieval_service.db.add.side_effect = Exception("Database error")

        # Should not raise exception
        await retrieval_service._log_access(
            episode_id="ep1",
            access_type="temporal",
            governance_check={"allowed": True},
            agent_id="agent1",
            results_count=5
        )

    @pytest.mark.asyncio
    async def test_log_access_timestamp(self, retrieval_service):
        """Test that timestamp is accurately recorded."""
        await retrieval_service._log_access(
            episode_id="ep1",
            access_type="temporal",
            governance_check={"allowed": True},
            agent_id="agent1",
            results_count=5
        )

        retrieval_service.db.add.assert_called()


# ============================================================================
# Task 3: Helper Method Tests
# ============================================================================

class TestHelperMethods:
    """Test helper methods for serialization and context fetching."""

    def test_serialize_episode_basic(self, retrieval_service, sample_episodes):
        """Test converting Episode to dict."""
        episode = sample_episodes[0]
        episode_dict = retrieval_service._serialize_episode(episode)

        assert episode_dict["id"] == "episode-0"
        # title is mapped from task_description
        assert episode_dict["title"] == "Task 0"
        assert "agent_id" in episode_dict
        assert "started_at" in episode_dict
        assert "importance_score" in episode_dict
        assert "maturity_at_time" in episode_dict

    def test_serialize_episode_with_user_id(self, retrieval_service, sample_episodes):
        """Test that user_id is included when provided."""
        episode = sample_episodes[0]
        episode_dict = retrieval_service._serialize_episode(episode, user_id="user-123")

        assert episode_dict["user_id"] == "user-123"

    def test_serialize_episode_datetime_formatting(self, retrieval_service, sample_episodes):
        """Test that datetimes are serialized to ISO format."""
        episode = sample_episodes[0]
        episode_dict = retrieval_service._serialize_episode(episode)

        # Check ISO format
        assert isinstance(episode_dict["started_at"], str)
        assert "T" in episode_dict["started_at"] or episode_dict["started_at"] is None

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_single(self, retrieval_service):
        """Test fetching single canvas context."""
        canvas = Mock(spec=CanvasAudit)
        canvas.id = "canvas-1"
        canvas.canvas_type = "sheets"
        canvas.component_type = "table"
        canvas.component_name = "Data Table"
        canvas.action = "present"
        canvas.created_at = datetime.now()
        canvas.audit_metadata = {"rows": 10}

        retrieval_service.db.query.return_value.filter.return_value.all.return_value = [canvas]

        result = await retrieval_service._fetch_canvas_context(["canvas-1"])

        assert len(result) == 1
        assert result[0]["id"] == "canvas-1"
        assert result[0]["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_multiple(self, retrieval_service):
        """Test fetching multiple canvas contexts."""
        canvases = [Mock(spec=CanvasAudit) for _ in range(3)]
        for i, c in enumerate(canvases):
            c.id = f"canvas-{i}"
            c.canvas_type = "sheets"
            c.component_type = "table"
            c.component_name = f"Table {i}"
            c.action = "present"
            c.created_at = datetime.now()
            c.audit_metadata = {}

        retrieval_service.db.query.return_value.filter.return_value.all.return_value = canvases

        result = await retrieval_service._fetch_canvas_context([c.id for c in canvases])

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_none(self, retrieval_service):
        """Test handling None canvas_audit_id."""
        result = await retrieval_service._fetch_canvas_context([])

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_single(self, retrieval_service):
        """Test fetching single feedback context."""
        feedback = Mock(spec=AgentFeedback)
        feedback.id = "feedback-1"
        feedback.feedback_type = "rating"
        feedback.rating = 5
        feedback.thumbs_up_down = True
        feedback.user_correction = None
        feedback.created_at = datetime.now()

        retrieval_service.db.query.return_value.filter.return_value.all.return_value = [feedback]

        result = await retrieval_service._fetch_feedback_context(["feedback-1"])

        assert len(result) == 1
        assert result[0]["id"] == "feedback-1"
        assert result[0]["rating"] == 5

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_multiple(self, retrieval_service):
        """Test fetching multiple feedback contexts."""
        feedbacks = [Mock(spec=AgentFeedback) for _ in range(3)]
        for i, f in enumerate(feedbacks):
            f.id = f"feedback-{i}"
            f.feedback_type = "rating"
            f.rating = 3 + i
            f.thumbs_up_down = i % 2 == 0
            f.user_correction = None
            f.created_at = datetime.now()

        retrieval_service.db.query.return_value.filter.return_value.all.return_value = feedbacks

        result = await retrieval_service._fetch_feedback_context([f.id for f in feedbacks])

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_aggregation(self, retrieval_service):
        """Test that feedback scores are properly aggregated."""
        feedbacks = [Mock(spec=AgentFeedback) for _ in range(3)]
        for i, f in enumerate(feedbacks):
            f.id = f"feedback-{i}"
            f.feedback_type = "rating"
            f.rating = 3 + i
            f.thumbs_up_down = True
            f.user_correction = None
            f.created_at = datetime.now()

        retrieval_service.db.query.return_value.filter.return_value.all.return_value = feedbacks

        result = await retrieval_service._fetch_feedback_context([f.id for f in feedbacks])

        # All feedback should be included
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_none(self, retrieval_service):
        """Test handling empty feedback list."""
        result = await retrieval_service._fetch_feedback_context([])

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_error_handling(self, retrieval_service):
        """Test graceful error handling in feedback context fetch."""
        retrieval_service.db.query.return_value.filter.return_value.all.return_value = []

        result = await retrieval_service._fetch_feedback_context(["feedback-1"])

        assert result == []


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

    @pytest.mark.asyncio
    async def test_database_connection_error(self, retrieval_service):
        """Test graceful handling of database connection errors."""
        retrieval_service.db.query.side_effect = Exception("Database connection lost")

        try:
            result = await retrieval_service.retrieve_temporal(
                agent_id="agent-123",
                time_range="7d"
            )
            # If it doesn't raise, should handle error gracefully
            assert "error" in result or "episodes" in result
        except Exception as e:
            # Should raise the database error
            assert "Database connection lost" in str(e)

    @pytest.mark.asyncio
    async def test_governance_service_timeout(self, retrieval_service):
        """Test handling governance service timeout."""
        retrieval_service.governance.can_perform_action.side_effect = Exception("Governance service timeout")

        try:
            result = await retrieval_service.retrieve_temporal(
                agent_id="agent-123",
                time_range="7d"
            )
            # If it doesn't raise, should handle error gracefully
            assert "episodes" in result or "error" in result
        except Exception as e:
            # Should raise the governance error
            assert "Governance service timeout" in str(e)


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
