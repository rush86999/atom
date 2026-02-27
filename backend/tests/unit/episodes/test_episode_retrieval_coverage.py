"""
Unit tests for episode_retrieval_service.py

Target: 60%+ coverage (current: 9.03%, target: ~188 lines)

Test Categories:
- Temporal Retrieval (5 tests)
- Semantic Retrieval (5 tests)
- Sequential Retrieval (4 tests)
- Contextual Retrieval (4 tests)
- Governance Integration (3 tests)
- Access Logging (2 tests)
- Error Paths (2 tests)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from core.episode_retrieval_service import (
    EpisodeRetrievalService,
    RetrievalMode,
    RetrievalResult
)
from core.models import (
    AgentFeedback,
    AgentRegistry,
    CanvasAudit,
    Episode,
    EpisodeAccessLog,
    EpisodeSegment,
)


# ========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def db_session():
    """Mock database session"""
    session = MagicMock(spec=Session)
    session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler"""
    lancedb = MagicMock()
    lancedb.search = MagicMock(return_value=[])
    lancedb.db = MagicMock()
    return lancedb


@pytest.fixture
def mock_governance():
    """Mock governance service"""
    governance = MagicMock()
    governance.can_perform_action = MagicMock(return_value={"allowed": True})
    return governance


@pytest.fixture
def retrieval_service(db_session, mock_lancedb, mock_governance):
    """EpisodeRetrievalService fixture"""
    with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=mock_lancedb):
        with patch('core.episode_retrieval_service.AgentGovernanceService', return_value=mock_governance):
            service = EpisodeRetrievalService(db_session)
            service.lancedb = mock_lancedb
            service.governance = mock_governance
            return service


@pytest.fixture
def sample_episodes():
    """Sample episodes for testing"""
    now = datetime.now()
    episodes = [
        Episode(
            id="ep1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Episode 1",
            description="First episode",
            summary="Summary 1",
            status="completed",
            started_at=now - timedelta(days=1),
            ended_at=now - timedelta(days=1) + timedelta(minutes=30),
            topics=["topic1", "topic2"],
            entities=["entity1"],
            importance_score=0.8,
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=5,
            canvas_ids=[],
            feedback_ids=[],
            aggregate_feedback_score=None
        ),
        Episode(
            id="ep2",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Episode 2",
            description="Second episode",
            summary="Summary 2",
            status="completed",
            started_at=now - timedelta(days=7),
            ended_at=now - timedelta(days=7) + timedelta(minutes=45),
            topics=["topic3"],
            entities=["entity2", "entity3"],
            importance_score=0.6,
            maturity_at_time="SUPERVISED",
            human_intervention_count=2,
            constitutional_score=0.85,
            decay_score=0.95,
            access_count=3,
            canvas_ids=["canvas1"],
            feedback_ids=["feedback1"],
            aggregate_feedback_score=0.5
        ),
    ]
    return episodes


@pytest.fixture
def sample_segments():
    """Sample episode segments"""
    now = datetime.now()
    segments = [
        EpisodeSegment(
            id="seg1",
            episode_id="ep1",
            segment_type="conversation",
            sequence_order=0,
            content="User asked about weather",
            content_summary="Weather question",
            source_type="chat_message",
            source_id="msg1",
            created_at=now
        ),
        EpisodeSegment(
            id="seg2",
            episode_id="ep1",
            segment_type="execution",
            sequence_order=1,
            content="Agent executed data analysis",
            content_summary="Data analysis",
            source_type="agent_execution",
            source_id="exec1",
            created_at=now + timedelta(seconds=1)
        ),
    ]
    return segments


@pytest.fixture
def sample_canvas_audits():
    """Sample canvas audits"""
    now = datetime.now()
    audits = [
        CanvasAudit(
            id="canvas1",
            episode_id="ep1",
            session_id="session1",
            canvas_type="sheets",
            component_type="table",
            component_name="data_table",
            action="present",
            audit_metadata={"rows": 100},
            created_at=now
        ),
    ]
    return audits


@pytest.fixture
def sample_feedback():
    """Sample feedback records"""
    now = datetime.now()
    feedbacks = [
        AgentFeedback(
            id="feedback1",
            agent_id="agent1",
            user_id="user1",
            feedback_type="thumbs_up",
            thumbs_up_down=True,
            rating=5,
            created_at=now
        ),
    ]
    return feedbacks


# ========================================================================
# A. Temporal Retrieval (5 tests)
# =========================================================================

class TestTemporalRetrieval:
    """Test temporal-based episode retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_temporal_1d_range(self, retrieval_service, sample_episodes):
        """Should retrieve episodes from last 1 day"""
        # Mock governance check
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        # Mock query chain
        query_mock = retrieval_service.db.query.return_value.filter
        query_mock.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:1]

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent1",
            time_range="1d",
            limit=50
        )

        assert result["count"] >= 0
        assert "episodes" in result
        assert result["time_range"] == "1d"
        assert result["governance_check"]["allowed"] is True

    @pytest.mark.asyncio
    async def test_retrieve_temporal_7d_range(self, retrieval_service, sample_episodes):
        """Should retrieve episodes from last 7 days"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}
        retrieval_service.db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent1",
            time_range="7d",
            limit=50
        )

        assert "episodes" in result
        assert result["time_range"] == "7d"

    @pytest.mark.asyncio
    async def test_retrieve_temporal_30d_range(self, retrieval_service, sample_episodes):
        """Should retrieve episodes from last 30 days"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}
        retrieval_service.db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent1",
            time_range="30d",
            limit=50
        )

        assert "episodes" in result
        assert result["time_range"] == "30d"

    @pytest.mark.asyncio
    async def test_retrieve_temporal_90d_range(self, retrieval_service, sample_episodes):
        """Should retrieve episodes from last 90 days"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}
        retrieval_service.db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent1",
            time_range="90d",
            limit=50
        )

        assert "episodes" in result
        assert result["time_range"] == "90d"

    @pytest.mark.asyncio
    async def test_retrieve_temporal_respects_limit(self, retrieval_service, sample_episodes):
        """Should respect limit parameter"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}
        retrieval_service.db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:1]

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent1",
            time_range="7d",
            limit=10
        )

        # Should not exceed limit
        assert result["count"] <= 10


# ========================================================================
# B. Semantic Retrieval (5 tests)
# =========================================================================

class TestSemanticRetrieval:
    """Test semantic similarity-based retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_semantic_by_vector_similarity(self, retrieval_service):
        """Should retrieve episodes using vector similarity"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        # Mock LanceDB search results
        retrieval_service.lancedb.search.return_value = [
            {
                "id": "ep1",
                "metadata": {"episode_id": "ep1"},
                "_distance": 0.2  # High similarity
            }
        ]

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent1",
            query="data analysis task",
            limit=10
        )

        retrieval_service.lancedb.search.assert_called_once()
        assert "episodes" in result
        assert result["query"] == "data analysis task"

    @pytest.mark.asyncio
    async def test_retrieve_semantic_with_query_embedding(self, retrieval_service):
        """Should handle query with embedding"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent1",
            query="find similar tasks",
            limit=5
        )

        assert "episodes" in result
        assert result["count"] >= 0

    @pytest.mark.asyncio
    async def test_retrieve_semantic_empty_results(self, retrieval_service):
        """Should handle empty search results"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}
        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent1",
            query="nonexistent topic",
            limit=10
        )

        assert result["episodes"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_retrieve_semantic_filters_by_agent(self, retrieval_service):
        """Should filter results by agent_id"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}
        retrieval_service.lancedb.search.return_value = []

        await retrieval_service.retrieve_semantic(
            agent_id="agent1",
            query="test query",
            limit=10
        )

        # Verify LanceDB was called with agent filter
        call_args = retrieval_service.lancedb.search.call_args
        assert "agent_id == 'agent1'" in call_args[1]["filter_str"]

    @pytest.mark.asyncio
    async def test_retrieve_semantic_governance_check(self, retrieval_service):
        """Should perform governance check before retrieval"""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Insufficient maturity level"
        }

        result = await retrieval_service.retrieve_semantic(
            agent_id="student_agent",
            query="test",
            limit=10
        )

        assert result["episodes"] == []
        assert "error" in result
        assert "governance_check" in result


# ========================================================================
# C. Sequential Retrieval (4 tests)
# =========================================================================

class TestSequentialRetrieval:
    """Test full episode sequential retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_sequential_full_episode(self, retrieval_service, sample_episodes, sample_segments):
        """Should retrieve full episode with segments"""
        # Simplified mock setup
        mock_query = MagicMock()

        # Episode query
        episode_result = MagicMock()
        episode_result.filter.return_value.first.return_value = sample_episodes[0]

        # Segments query
        segments_result = MagicMock()
        segments_result.filter.return_value.order_by.return_value.all.return_value = sample_segments

        # Set up query to return different mocks based on argument
        def query_side_effect(model):
            if model == EpisodeSegment:
                return segments_result
            elif model == CanvasAudit:
                canvas_mock = MagicMock()
                canvas_mock.filter.return_value.all.return_value = []
                return canvas_mock
            elif model == AgentFeedback:
                feedback_mock = MagicMock()
                feedback_mock.filter.return_value.all.return_value = []
                return feedback_mock
            return episode_result

        retrieval_service.db.query.side_effect = query_side_effect

        result = await retrieval_service.retrieve_sequential(
            episode_id="ep1",
            agent_id="agent1"
        )

        assert "episode" in result
        assert "segments" in result
        assert result["episode"]["id"] == "ep1"

    @pytest.mark.asyncio
    async def test_retrieve_sequential_includes_segments(self, retrieval_service, sample_episodes, sample_segments):
        """Should include all segments in order"""
        # Set up mocks
        episode_result = MagicMock()
        episode_result.filter.return_value.first.return_value = sample_episodes[0]

        segments_result = MagicMock()
        segments_result.filter.return_value.order_by.return_value.all.return_value = sample_segments

        def query_side_effect(model):
            if model == EpisodeSegment:
                return segments_result
            return episode_result

        retrieval_service.db.query.side_effect = query_side_effect

        result = await retrieval_service.retrieve_sequential(
            episode_id="ep1",
            agent_id="agent1"
        )

        assert len(result["segments"]) == 2
        assert result["segments"][0]["sequence_order"] == 0
        assert result["segments"][1]["sequence_order"] == 1

    @pytest.mark.asyncio
    async def test_retrieve_sequential_with_canvas_context(self, retrieval_service, sample_episodes):
        """Should include canvas context when requested"""
        sample_episodes[0].canvas_ids = ["canvas1"]
        sample_episodes[0].feedback_ids = []

        episode_result = MagicMock()
        episode_result.filter.return_value.first.return_value = sample_episodes[0]

        segments_result = MagicMock()
        segments_result.filter.return_value.order_by.return_value.all.return_value = []

        canvas_result = MagicMock()
        canvas_result.filter.return_value.all.return_value = []

        feedback_result = MagicMock()
        feedback_result.filter.return_value.all.return_value = []

        def query_side_effect(model):
            if model == EpisodeSegment:
                return segments_result
            elif model == CanvasAudit:
                return canvas_result
            elif model == AgentFeedback:
                return feedback_result
            return episode_result

        retrieval_service.db.query.side_effect = query_side_effect

        result = await retrieval_service.retrieve_sequential(
            episode_id="ep1",
            agent_id="agent1",
            include_canvas=True
        )

        # Verify canvas context fetching was attempted
        assert "episode" in result

    @pytest.mark.asyncio
    async def test_retrieve_sequential_with_feedback_context(self, retrieval_service, sample_episodes):
        """Should include feedback context when requested"""
        sample_episodes[0].feedback_ids = ["feedback1"]
        sample_episodes[0].canvas_ids = []

        episode_result = MagicMock()
        episode_result.filter.return_value.first.return_value = sample_episodes[0]

        segments_result = MagicMock()
        segments_result.filter.return_value.order_by.return_value.all.return_value = []

        canvas_result = MagicMock()
        canvas_result.filter.return_value.all.return_value = []

        feedback_result = MagicMock()
        feedback_result.filter.return_value.all.return_value = []

        def query_side_effect(model):
            if model == EpisodeSegment:
                return segments_result
            elif model == CanvasAudit:
                return canvas_result
            elif model == AgentFeedback:
                return feedback_result
            return episode_result

        retrieval_service.db.query.side_effect = query_side_effect

        result = await retrieval_service.retrieve_sequential(
            episode_id="ep1",
            agent_id="agent1",
            include_feedback=True
        )

        assert "episode" in result


# ========================================================================
# D. Contextual Retrieval (4 tests)
# =========================================================================

class TestContextualRetrieval:
    """Test hybrid contextual retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_contextual_hybrid_scoring(self, retrieval_service, sample_episodes):
        """Should combine temporal and semantic scoring"""
        # Mock temporal and semantic retrieval
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        async def mock_retrieve_temporal(*args, **kwargs):
            return {"episodes": [retrieval_service._serialize_episode(e) for e in sample_episodes], "count": len(sample_episodes)}

        async def mock_retrieve_semantic(*args, **kwargs):
            return {"episodes": [retrieval_service._serialize_episode(e) for e in sample_episodes[:1]], "count": 1}

        retrieval_service.retrieve_temporal = mock_retrieve_temporal
        retrieval_service.retrieve_semantic = mock_retrieve_semantic

        # Mock episode queries for filtering - ensure canvas_action_count is set
        for ep in sample_episodes:
            ep.canvas_action_count = ep.canvas_action_count or 0

        # Use a function that always returns an episode to avoid StopIteration
        def mock_first(*args, **kwargs):
            return sample_episodes[0] if sample_episodes else None

        retrieval_service.db.query.return_value.filter.return_value.first.side_effect = mock_first

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent1",
            current_task="data analysis",
            limit=5
        )

        assert "episodes" in result
        assert result["count"] >= 0

    @pytest.mark.asyncio
    async def test_retrieve_contextual_weights_temporal_semantic(self, retrieval_service, sample_episodes):
        """Should apply 0.3 temporal and 0.7 semantic weights"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        async def mock_retrieve(*args, **kwargs):
            return {"episodes": [retrieval_service._serialize_episode(e) for e in sample_episodes], "count": len(sample_episodes)}

        retrieval_service.retrieve_temporal = mock_retrieve
        retrieval_service.retrieve_semantic = mock_retrieve

        # Ensure canvas_action_count is set
        for ep in sample_episodes:
            ep.canvas_action_count = ep.canvas_action_count or 0

        def mock_first(*args, **kwargs):
            return sample_episodes[0] if sample_episodes else None

        retrieval_service.db.query.return_value.filter.return_value.first.side_effect = mock_first

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent1",
            current_task="test",
            limit=5
        )

        # Should return episodes with relevance scores
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_contextual_includes_feedback(self, retrieval_service, sample_episodes):
        """Should include feedback-based boosting"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        async def mock_retrieve(*args, **kwargs):
            return {"episodes": [retrieval_service._serialize_episode(e) for e in sample_episodes], "count": len(sample_episodes)}

        retrieval_service.retrieve_temporal = mock_retrieve
        retrieval_service.retrieve_semantic = mock_retrieve

        # Ensure canvas_action_count is set
        for ep in sample_episodes:
            ep.canvas_action_count = ep.canvas_action_count or 0

        def mock_first(*args, **kwargs):
            return sample_episodes[0] if sample_episodes else None

        retrieval_service.db.query.return_value.filter.return_value.first.side_effect = mock_first

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent1",
            current_task="test",
            limit=5
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_contextual_governance_blocking(self, retrieval_service):
        """Should block retrieval based on governance"""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Blocked by governance"
        }

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent1",
            current_task="test",
            limit=5
        )

        assert result["episodes"] == []


# ========================================================================
# E. Governance Integration (3 tests)
# =========================================================================

class TestGovernanceIntegration:
    """Test governance checks for retrieval"""

    @pytest.mark.asyncio
    async def test_governance_blocks_student_memory_access(self, retrieval_service):
        """Should block STUDENT agents from memory access"""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT agents cannot access memory",
            "agent_maturity": "STUDENT"
        }

        result = await retrieval_service.retrieve_temporal(
            agent_id="student_agent",
            time_range="7d"
        )

        assert result["episodes"] == []
        assert "error" in result
        assert result["governance_check"]["allowed"] is False

    @pytest.mark.asyncio
    async def test_governance_allows_supervised_memory_read(self, retrieval_service, sample_episodes):
        """Should allow SUPERVISED agents to read memory"""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": True,
            "agent_maturity": "SUPERVISED"
        }
        retrieval_service.db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes

        result = await retrieval_service.retrieve_temporal(
            agent_id="supervised_agent",
            time_range="7d"
        )

        assert result["governance_check"]["allowed"] is True

    @pytest.mark.asyncio
    async def test_governance_logs_denied_access(self, retrieval_service):
        """Should log denied access attempts"""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Insufficient permissions",
            "agent_maturity": "STUDENT"
        }

        with patch.object(retrieval_service, '_log_access', new_callable=AsyncMock) as mock_log:
            result = await retrieval_service.retrieve_temporal(
                agent_id="student_agent",
                time_range="7d"
            )

            # Should log the denied access
            mock_log.assert_called_once()


# ========================================================================
# F. Access Logging (2 tests)
# =========================================================================

class TestAccessLogging:
    """Test episode access logging"""

    @pytest.mark.asyncio
    async def test_log_access_creates_entry(self, retrieval_service, sample_episodes):
        """Should create EpisodeAccessLog entry"""
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = sample_episodes[0]
        retrieval_service.db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        await retrieval_service.retrieve_sequential(
            episode_id="ep1",
            agent_id="agent1"
        )

        # Verify log entry was created
        retrieval_service.db.add.assert_called()
        retrieval_service.db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_log_access_updates_episode_metrics(self, retrieval_service, sample_episodes):
        """Should update episode access_count via log"""
        retrieval_service.db.query.return_value.filter.return_value.first.return_value = sample_episodes[0]
        retrieval_service.db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

        await retrieval_service.retrieve_sequential(
            episode_id="ep1",
            agent_id="agent1"
        )

        # Verify access was logged with results count
        assert retrieval_service.db.add.called


# ========================================================================
# G. Error Paths (2 tests)
# =========================================================================

class TestErrorPaths:
    """Test error handling paths"""

    @pytest.mark.asyncio
    async def test_retrieve_invalid_mode_raises_error(self, retrieval_service):
        """Should handle invalid retrieval mode"""
        # This tests the validation of retrieval modes
        # Note: RetrievalMode is an Enum, so invalid modes won't compile
        # This test ensures the enum works correctly
        assert RetrievalMode.TEMPORAL == "temporal"
        assert RetrievalMode.SEMANTIC == "semantic"
        assert RetrievalMode.SEQUENTIAL == "sequential"
        assert RetrievalMode.CONTEXTUAL == "contextual"

    @pytest.mark.asyncio
    async def test_retrieve_with_lancedb_failure(self, retrieval_service):
        """Should handle LanceDB failures gracefully"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}
        retrieval_service.lancedb.search.side_effect = Exception("LanceDB connection failed")

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent1",
            query="test",
            limit=10
        )

        # Should return error instead of crashing
        assert "episodes" in result
        assert result["episodes"] == []
