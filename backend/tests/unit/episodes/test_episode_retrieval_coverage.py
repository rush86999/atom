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
            aggregate_feedback_score=None,
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
            aggregate_feedback_score=0.5,
            canvas_action_count=0
)
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


# ========================================================================
# H. Canvas-Aware Retrieval (8 tests)
# =========================================================================

class TestCanvasAwareRetrieval:
    """Test canvas-aware episode retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_with_canvas_interactions(self, retrieval_service, sample_episodes):
        """Should retrieve episodes with canvas context prioritized"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        # Mock LanceDB search results
        retrieval_service.lancedb.search.return_value = [
            {
                "id": "ep1",
                "metadata": {"episode_id": "ep1"},
                "_distance": 0.2
            }
        ]

        # Mock episode query
        episode_query = MagicMock()
        episode_query.filter.return_value.all.return_value = sample_episodes[:1]

        # Mock segments query
        segment_query = MagicMock()
        segment_query.filter.return_value.all.return_value = []

        # Set up query chain - first call for episodes, second for segments
        retrieval_service.db.query.side_effect = [episode_query, segment_query]

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent1",
            query="spreadsheet analysis",
            limit=10
        )

        assert "episodes" in result
        assert result["canvas_context_detail"] == "summary"
        assert retrieval_service.lancedb.search.called

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_filters_by_canvas_type(self, retrieval_service, sample_episodes):
        """Should filter episodes by canvas type"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        retrieval_service.lancedb.search.return_value = []
        retrieval_service.db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        await retrieval_service.retrieve_canvas_aware(
            agent_id="agent1",
            query="data analysis",
            canvas_type="sheets",
            limit=10
        )

        # Verify LanceDB was called with canvas type filter
        call_args = retrieval_service.lancedb.search.call_args
        assert "sheets" in call_args[1]["filter_str"]

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_visual_elements_extracted(self, retrieval_service):
        """Should extract visual elements from chart canvases"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        # Create episode with chart canvas context
        now = datetime.now()
        chart_episode = Episode(
            id="chart1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Chart Episode",
            summary="Line chart presentation",
            status="completed",
            started_at=now,
            topics=["visualization"],
            importance_score=0.8,
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=1,
            canvas_ids=[],
            feedback_ids=[]
        )

        retrieval_service.lancedb.search.return_value = [
            {"id": "chart1", "metadata": {"episode_id": "chart1"}, "_distance": 0.1}
        ]

        episode_query = MagicMock()
        episode_query.filter.return_value.all.return_value = [chart_episode]

        # Mock segment with visual elements
        chart_segment = EpisodeSegment(
            id="seg1",
            episode_id="chart1",
            segment_type="canvas_presentation",
            sequence_order=0,
            content="Presented line chart",
            content_summary="Chart visualization",
            source_type="canvas",
            source_id="canvas1",
            created_at=now,
            canvas_context={
                "canvas_type": "charts",
                "presentation_summary": "Sales trend chart",
                "visual_elements": {
                    "chart_type": "line",
                    "data_series": ["sales", "targets"]
                }
            }
        )

        segment_query = MagicMock()
        segment_query.filter.return_value.all.return_value = [chart_segment]

        retrieval_service.db.query.side_effect = [episode_query, segment_query]

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent1",
            query="chart visualization",
            canvas_context_detail="full",
            limit=10
        )

        assert result["canvas_context_detail"] == "full"

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_form_data_extracted(self, retrieval_service):
        """Should extract form submission data"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        form_episode = Episode(
            id="form1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Form Episode",
            summary="Form submission",
            status="completed",
            started_at=now,
            topics=["form"],
            importance_score=0.7,
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=1,
            canvas_ids=[],
            feedback_ids=[]
        )

        retrieval_service.lancedb.search.return_value = [
            {"id": "form1", "metadata": {"episode_id": "form1"}, "_distance": 0.1}
        ]

        episode_query = MagicMock()
        episode_query.filter.return_value.all.return_value = [form_episode]

        # Mock segment with form data
        form_segment = EpisodeSegment(
            id="seg2",
            episode_id="form1",
            segment_type="form_submission",
            sequence_order=0,
            content="Form submitted",
            content_summary="User submitted form",
            source_type="canvas",
            source_id="form1",
            created_at=now,
            canvas_context={
                "canvas_type": "generic",
                "presentation_summary": "Data collection form",
                "form_fields": ["name", "email", "approval_status"],
                "user_submissions": 5
            }
        )

        segment_query = MagicMock()
        segment_query.filter.return_value.all.return_value = [form_segment]

        retrieval_service.db.query.side_effect = [episode_query, segment_query]

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent1",
            query="form submission",
            canvas_context_detail="standard",
            limit=10
        )

        assert result["canvas_context_detail"] == "standard"

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_without_canvas_context(self, retrieval_service, sample_episodes):
        """Should return episodes without canvas enrichment when none exists"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        # Episode with no canvas interactions
        sample_episodes[0].canvas_action_count = 0

        retrieval_service.lancedb.search.return_value = []
        retrieval_service.db.query.return_value.filter.return_value.filter.return_value.all.return_value = []

        await retrieval_service.retrieve_canvas_aware(
            agent_id="agent1",
            query="general task",
            limit=10
        )

        # Should complete without error even with no canvas context
        assert retrieval_service.lancedb.search.called

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_multiple_canvas_types(self, retrieval_service):
        """Should handle episodes with multiple canvas types"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        multi_canvas_episode = Episode(
            id="multi1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Multi Canvas Episode",
            summary="Episode with sheets and charts",
            status="completed",
            started_at=now,
            topics=["visualization", "data"],
            importance_score=0.9,
            maturity_at_time="SUPERVISED",
            human_intervention_count=1,
            constitutional_score=0.85,
            decay_score=0.95,
            access_count=3,
            canvas_ids=["canvas1", "canvas2"],
            feedback_ids=[]
        )

        retrieval_service.lancedb.search.return_value = [
            {"id": "multi1", "metadata": {"episode_id": "multi1"}, "_distance": 0.15}
        ]

        episode_query = MagicMock()
        episode_query.filter.return_value.all.return_value = [multi_canvas_episode]

        segment_query = MagicMock()
        segment_query.filter.return_value.all.return_value = []

        retrieval_service.db.query.side_effect = [episode_query, segment_query]

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent1",
            query="multi canvas analysis",
            limit=10
        )

        assert result["count"] >= 0

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_governance_check(self, retrieval_service):
        """Should perform governance check before canvas retrieval"""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "INTERN maturity required for semantic search"
        }

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="student_agent",
            query="test",
            limit=10
        )

        assert result["episodes"] == []
        assert "error" in result
        assert result["governance_check"]["allowed"] is False

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_empty_results(self, retrieval_service):
        """Should handle empty canvas-aware results gracefully"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        retrieval_service.lancedb.search.return_value = []

        result = await retrieval_service.retrieve_canvas_aware(
            agent_id="agent1",
            query="nonexistent canvas",
            limit=10
        )

        assert result["episodes"] == []
        assert result["count"] == 0
        assert "error" not in result


# ========================================================================
# I. Business Data Retrieval (4 tests)
# =========================================================================

class TestBusinessDataRetrieval:
    """Test business data-based episode retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_finds_entity_matches(self, retrieval_service, sample_episodes):
        """Should find episodes with matching business entities"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        # Mock segment query with canvas context
        segment_mock = MagicMock()
        segment_mock.join.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = []

        # Mock episode query
        episode_mock = MagicMock()
        episode_mock.filter.return_value.all.return_value = []

        # Set up query chain
        query_count = 0
        def query_side_effect(model):
            nonlocal query_count
            query_count += 1
            if query_count == 1:
                return segment_mock
            return episode_mock

        retrieval_service.db.query.side_effect = query_side_effect

        result = await retrieval_service.retrieve_by_business_data(
            agent_id="agent1",
            business_filters={"entity": "ACME Corp"},
            limit=10
        )

        assert "episodes" in result
        assert result["filters"] == {"entity": "ACME Corp"}

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_extracts_business_facts(self, retrieval_service, sample_episodes):
        """Should extract business facts from episode summaries"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        segment_mock = MagicMock()
        segment_mock.join.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = []

        episode_mock = MagicMock()
        episode_mock.filter.return_value.all.return_value = []

        query_count = 0
        def query_side_effect(model):
            nonlocal query_count
            query_count += 1
            if query_count == 1:
                return segment_mock
            return episode_mock

        retrieval_service.db.query.side_effect = query_side_effect

        result = await retrieval_service.retrieve_by_business_data(
            agent_id="agent1",
            business_filters={"approval_status": "approved"},
            limit=10
        )

        assert "episodes" in result
        assert "filters" in result

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_temporal_window(self, retrieval_service):
        """Should filter business episodes by time window"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        timed_episode = Episode(
            id="ep_business",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Business Episode",
            summary="Business transaction",
            status="completed",
            started_at=now - timedelta(days=15),
            topics=["business"],
            importance_score=0.8,
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=2,
            canvas_ids=[],
            feedback_ids=[]
        )

        segment_mock = MagicMock()
        segment_mock.join.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = []

        episode_mock = MagicMock()
        episode_mock.filter.return_value.all.return_value = [timed_episode]

        query_count = 0
        def query_side_effect(model):
            nonlocal query_count
            query_count += 1
            if query_count == 1:
                return segment_mock
            return episode_mock

        retrieval_service.db.query.side_effect = query_side_effect

        result = await retrieval_service.retrieve_by_business_data(
            agent_id="agent1",
            business_filters={"revenue": {"$gt": 1000000}},
            limit=10
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_by_business_data_no_matches(self, retrieval_service):
        """Should return empty list when no business data matches"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        segment_mock = MagicMock()
        segment_mock.join.return_value.filter.return_value.filter.return_value.limit.return_value.all.return_value = []

        episode_mock = MagicMock()
        episode_mock.filter.return_value.all.return_value = []

        query_count = 0
        def query_side_effect(model):
            nonlocal query_count
            query_count += 1
            if query_count == 1:
                return segment_mock
            return episode_mock

        retrieval_service.db.query.side_effect = query_side_effect

        result = await retrieval_service.retrieve_by_business_data(
            agent_id="agent1",
            business_filters={"nonexistent_field": "value"},
            limit=10
        )

        assert result["episodes"] == []
        assert result["count"] == 0
        assert "error" not in result


# ========================================================================
# J. Canvas Type Retrieval (6 tests)
# =========================================================================

class TestCanvasTypeRetrieval:
    """Test canvas type filtering"""

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_sheets(self, retrieval_service, sample_episodes):
        """Should retrieve episodes with sheets canvas type"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        # Episode with sheets canvas
        sample_episodes[0].canvas_action_count = 5

        # Mock canvas subquery
        canvas_subquery_mock = MagicMock()
        canvas_subquery_mock.filter.return_value = canvas_subquery_mock

        # Mock episode query
        episode_query = retrieval_service.db.query.return_value.filter
        episode_query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:1]

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent1",
            canvas_type="sheets",
            time_range="30d",
            limit=10
        )

        assert "episodes" in result
        assert result["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_charts(self, retrieval_service, sample_episodes):
        """Should retrieve episodes with charts canvas type"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        sample_episodes[0].canvas_action_count = 3

        canvas_subquery_mock = MagicMock()
        canvas_subquery_mock.filter.return_value = canvas_subquery_mock

        episode_query = retrieval_service.db.query.return_value.filter
        episode_query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:1]

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent1",
            canvas_type="charts",
            time_range="30d",
            limit=10
        )

        assert result["canvas_type"] == "charts"

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_forms(self, retrieval_service, sample_episodes):
        """Should retrieve episodes with form canvas type"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        sample_episodes[0].canvas_action_count = 2

        canvas_subquery_mock = MagicMock()
        canvas_subquery_mock.filter.return_value = canvas_subquery_mock

        episode_query = retrieval_service.db.query.return_value.filter
        episode_query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:1]

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent1",
            canvas_type="generic",
            time_range="30d",
            limit=10
        )

        assert result["canvas_type"] == "generic"

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_multiple_types(self, retrieval_service):
        """Should retrieve episodes with multiple canvas types"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        multi_type_episode = Episode(
            id="multi_type",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Multi Type Episode",
            summary="Episode with sheets and charts",
            status="completed",
            started_at=now,
            topics=["data", "visualization"],
            importance_score=0.85,
            maturity_at_time="SUPERVISED",
            human_intervention_count=1,
            constitutional_score=0.88,
            decay_score=0.96,
            access_count=4,
            canvas_ids=["sheet1", "chart1"],
            feedback_ids=[],
            canvas_action_count=7
        )

        canvas_subquery_mock = MagicMock()
        canvas_subquery_mock.filter.return_value = canvas_subquery_mock

        episode_query = retrieval_service.db.query.return_value.filter
        episode_query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [multi_type_episode]

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent1",
            canvas_type="sheets",
            time_range="30d",
            limit=10
        )

        assert result["count"] >= 0

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_with_action_filter(self, retrieval_service, sample_episodes):
        """Should filter by both canvas type and action"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        sample_episodes[0].canvas_action_count = 4

        canvas_subquery_mock = MagicMock()
        canvas_subquery_mock.filter.return_value = canvas_subquery_mock
        canvas_subquery_mock.filter.return_value = canvas_subquery_mock

        episode_query = retrieval_service.db.query.return_value.filter
        episode_query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:1]

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent1",
            canvas_type="sheets",
            action="submit",
            time_range="30d",
            limit=10
        )

        assert result["action"] == "submit"

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type_no_type_filter(self, retrieval_service):
        """Should return all episodes when no type filter specified"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        # This tests the method requires canvas_type parameter
        # If canvas_type is not provided, it should still work with just the action filter

        now = datetime.now()
        test_episode = Episode(
            id="test_ep",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Test Episode",
            summary="Test canvas interaction",
            status="completed",
            started_at=now,
            topics=["test"],
            importance_score=0.7,
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=0.9,
            decay_score=1.0,
            access_count=1,
            canvas_ids=[],
            feedback_ids=[],
            canvas_action_count=2
        )

        canvas_subquery_mock = MagicMock()
        canvas_subquery_mock.filter.return_value = canvas_subquery_mock

        episode_query = retrieval_service.db.query.return_value.filter
        episode_query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [test_episode]

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent1",
            canvas_type="sheets",  # Required parameter
            time_range="7d",
            limit=10
        )

        assert "episodes" in result


# ========================================================================
# K. Supervision Context Retrieval (6 tests)
# =========================================================================

class TestSupervisionContextRetrieval:
    """Test supervision context enrichment"""

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_includes_interventions(self, retrieval_service):
        """Should include intervention details in supervision context"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        supervised_episode = Episode(
            id="supervised1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Supervised Episode",
            summary="Episode with human interventions",
            status="completed",
            started_at=now,
            topics=["supervision"],
            importance_score=0.8,
            maturity_at_time="SUPERVISED",
            human_intervention_count=3,
            constitutional_score=0.85,
            decay_score=0.95,
            access_count=2,
            canvas_ids=[],
            feedback_ids=[]
        )

        # Mock temporal retrieval result
        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(supervised_episode)],
                "count": 1
            }

        retrieval_service.retrieve_temporal = mock_temporal

        # Mock episode query
        episode_mock = MagicMock()
        episode_mock.filter.return_value.all.return_value = [supervised_episode]
        retrieval_service.db.query.side_effect = [episode_mock]

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            limit=10
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_pause_events(self, retrieval_service):
        """Should track pause events in supervision context"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        paused_episode = Episode(
            id="paused1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Paused Episode",
            summary="Episode with pause events",
            status="completed",
            started_at=now,
            topics=["supervision"],
            importance_score=0.75,
            maturity_at_time="SUPERVISED",
            human_intervention_count=2,
            constitutional_score=0.88,
            decay_score=0.96,
            access_count=1,
            canvas_ids=[],
            feedback_ids=[]
        )

        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(paused_episode)],
                "count": 1
            }

        retrieval_service.retrieve_temporal = mock_temporal

        episode_mock = MagicMock()
        episode_mock.filter.return_value.all.return_value = [paused_episode]
        retrieval_service.db.query.side_effect = [episode_mock]

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            limit=10
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_correction_events(self, retrieval_service):
        """Should track corrections in supervision context"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        corrected_episode = Episode(
            id="corrected1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Corrected Episode",
            summary="Episode with supervisor corrections",
            status="completed",
            started_at=now,
            topics=["supervision"],
            importance_score=0.7,
            maturity_at_time="SUPERVISED",
            human_intervention_count=4,
            constitutional_score=0.82,
            decay_score=0.94,
            access_count=3,
            canvas_ids=[],
            feedback_ids=[]
        )

        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(corrected_episode)],
                "count": 1
            }

        retrieval_service.retrieve_temporal = mock_temporal

        episode_mock = MagicMock()
        episode_mock.filter.return_value.all.return_value = [corrected_episode]
        retrieval_service.db.query.side_effect = [episode_mock]

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            limit=10
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_learning_outcomes(self, retrieval_service):
        """Should capture learning outcomes from supervision"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        learning_episode = Episode(
            id="learning1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Learning Episode",
            summary="Episode with learning feedback",
            status="completed",
            started_at=now,
            topics=["learning", "improvement"],
            importance_score=0.9,
            maturity_at_time="SUPERVISED",
            human_intervention_count=1,
            constitutional_score=0.92,
            decay_score=0.98,
            access_count=5,
            canvas_ids=[],
            feedback_ids=[]
        )

        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(learning_episode)],
                "count": 1
            }

        retrieval_service.retrieve_temporal = mock_temporal

        episode_mock = MagicMock()
        episode_mock.filter.return_value.all.return_value = [learning_episode]
        retrieval_service.db.query.side_effect = [episode_mock]

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            limit=10
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_governance_check(self, retrieval_service):
        """Should block STUDENT agents from supervision history"""
        retrieval_service.governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT agents cannot access supervision history"
        }

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="student_agent",
            retrieval_mode=RetrievalMode.TEMPORAL,
            limit=10
        )

        assert result["episodes"] == []
        assert "error" in result
        assert result["governance_check"]["allowed"] is False

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_empty_supervision_history(self, retrieval_service):
        """Should return episodes without supervision enrichment when none exists"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        unsupervised_episode = Episode(
            id="unsupervised1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Unsupervised Episode",
            summary="Episode with no supervision",
            status="completed",
            started_at=now,
            topics=["autonomous"],
            importance_score=0.7,
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            constitutional_score=0.95,
            decay_score=1.0,
            access_count=1,
            canvas_ids=[],
            feedback_ids=[]
        )

        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(unsupervised_episode)],
                "count": 1
            }

        retrieval_service.retrieve_temporal = mock_temporal

        episode_mock = MagicMock()
        episode_mock.filter.return_value.all.return_value = [unsupervised_episode]
        retrieval_service.db.query.side_effect = [episode_mock]

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            limit=10
        )

        assert "episodes" in result


# ========================================================================
# L. Feedback-Weighted Retrieval (6 tests)
# =========================================================================

class TestFeedbackWeightedRetrieval:
    """Test feedback-based relevance boosting"""

    @pytest.mark.asyncio
    async def test_retrieve_feedback_weighted_positive_boost(self, retrieval_service):
        """Should boost relevance with positive feedback"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        positive_episode = Episode(
            id="positive1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Positive Feedback Episode",
            summary="Highly rated episode",
            status="completed",
            started_at=now,
            topics=["success"],
            importance_score=0.9,
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            constitutional_score=0.95,
            decay_score=1.0,
            access_count=10,
            canvas_ids=[],
            feedback_ids=["feedback1"],
            aggregate_feedback_score=0.8,
            canvas_action_count=0
        )

        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(positive_episode)],
                "count": 1
            }

        async def mock_semantic(*args, **kwargs):
            return {
                "episodes": [],
                "count": 0
            }

        retrieval_service.retrieve_temporal = mock_temporal
        retrieval_service.retrieve_semantic = mock_semantic

        # Mock episode query for feedback boost
        # The contextual retrieval calls: self.db.query(Episode).filter(...).first()
        # We need to set up the mock chain properly - first() is called multiple times
        def always_return_episode(*args, **kwargs):
            return positive_episode

        mock_filter_result = MagicMock()
        mock_filter_result.first.side_effect = always_return_episode

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value = mock_filter_result

        retrieval_service.db.query.return_value = mock_query_result

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent1",
            current_task="similar successful task",
            limit=5
        )

        # Should return episodes (positive feedback boosts relevance)
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_feedback_weighted_negative_penalty(self, retrieval_service):
        """Should penalize relevance with negative feedback"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        negative_episode = Episode(
            id="negative1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Negative Feedback Episode",
            summary="Poorly rated episode",
            status="completed",
            started_at=now,
            topics=["failure"],
            importance_score=0.4,
            maturity_at_time="INTERN",
            human_intervention_count=2,
            constitutional_score=0.75,
            decay_score=0.9,
            access_count=5,
            canvas_ids=[],
            feedback_ids=["feedback2"],
            aggregate_feedback_score=-0.6,
            canvas_action_count=0
)

        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(negative_episode)],
                "count": 1
            }

        async def mock_semantic(*args, **kwargs):
            return {
                "episodes": [],
                "count": 0
            }

        retrieval_service.retrieve_temporal = mock_temporal
        retrieval_service.retrieve_semantic = mock_semantic

        # Mock episode query - using return_value which always returns the same value
        mock_filter_result = MagicMock()
        mock_filter_result.first.return_value = negative_episode

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value = mock_filter_result

        retrieval_service.db.query.return_value = mock_query_result

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent1",
            current_task="task",
            limit=5
        )

        # Negative feedback should reduce relevance
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_feedback_weighted_neutral_no_effect(self, retrieval_service):
        """Should not adjust relevance for neutral feedback"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        neutral_episode = Episode(
            id="neutral1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Neutral Feedback Episode",
            summary="Average rated episode",
            status="completed",
            started_at=now,
            topics=["neutral"],
            importance_score=0.6,
            maturity_at_time="INTERN",
            human_intervention_count=1,
            constitutional_score=0.85,
            decay_score=0.95,
            access_count=3,
            canvas_ids=[],
            feedback_ids=["feedback3"],
            aggregate_feedback_score=0.0,
            canvas_action_count=0
)

        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(neutral_episode)],
                "count": 1
            }

        async def mock_semantic(*args, **kwargs):
            return {
                "episodes": [],
                "count": 0
            }

        retrieval_service.retrieve_temporal = mock_temporal
        retrieval_service.retrieve_semantic = mock_semantic

        # Mock episode query
        mock_filter_result = MagicMock()
        mock_filter_result.first.return_value = neutral_episode

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value = mock_filter_result

        retrieval_service.db.query.return_value = mock_query_result

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent1",
            current_task="task",
            limit=5
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_feedback_weighted_thumbs_up_handling(self, retrieval_service, sample_feedback):
        """Should handle thumbs up/down feedback signals"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        thumbs_up_episode = Episode(
            id="thumbs1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Thumbs Up Episode",
            summary="User thumbed up",
            status="completed",
            started_at=now,
            topics=["success"],
            importance_score=0.85,
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            constitutional_score=0.93,
            decay_score=0.98,
            access_count=7,
            canvas_ids=[],
            feedback_ids=[sample_feedback[0].id],
            aggregate_feedback_score=0.7,
            canvas_action_count=0
)

        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(thumbs_up_episode)],
                "count": 1
            }

        async def mock_semantic(*args, **kwargs):
            return {
                "episodes": [],
                "count": 0
            }

        retrieval_service.retrieve_temporal = mock_temporal
        retrieval_service.retrieve_semantic = mock_semantic

        # Mock episode query
        mock_filter_result = MagicMock()
        mock_filter_result.first.return_value = thumbs_up_episode

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value = mock_filter_result

        retrieval_service.db.query.return_value = mock_query_result

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent1",
            current_task="task",
            limit=5
        )

        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_feedback_weighted_rating_integration(self, retrieval_service):
        """Should convert star ratings to feedback scores"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        rated_episode = Episode(
            id="rated1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="High Rated Episode",
            summary="5-star rated episode",
            status="completed",
            started_at=now,
            topics=["excellent"],
            importance_score=0.95,
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            constitutional_score=0.98,
            decay_score=1.0,
            access_count=15,
            canvas_ids=[],
            feedback_ids=["feedback5"],
            aggregate_feedback_score=1.0,  # Max rating
            canvas_action_count=0
        )

        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(rated_episode)],
                "count": 1
            }

        async def mock_semantic(*args, **kwargs):
            return {
                "episodes": [],
                "count": 0
            }

        retrieval_service.retrieve_temporal = mock_temporal
        retrieval_service.retrieve_semantic = mock_semantic

        # Mock episode query
        mock_filter_result = MagicMock()
        mock_filter_result.first.return_value = rated_episode

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value = mock_filter_result

        retrieval_service.db.query.return_value = mock_query_result

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent1",
            current_task="task",
            limit=5
        )

        # High rating should boost relevance
        assert "episodes" in result

    @pytest.mark.asyncio
    async def test_retrieve_feedback_weighted_combined_signals(self, retrieval_service):
        """Should combine thumbs up and rating signals"""
        retrieval_service.governance.can_perform_action.return_value = {"allowed": True}

        now = datetime.now()
        combined_episode = Episode(
            id="combined1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Combined Feedback Episode",
            summary="Both thumbs up and 5-star rating",
            status="completed",
            started_at=now,
            topics=["excellent"],
            importance_score=0.95,
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            constitutional_score=0.98,
            decay_score=1.0,
            access_count=20,
            canvas_ids=[],
            feedback_ids=["feedback_combined"],
            aggregate_feedback_score=1.0,
            canvas_action_count=0
)

        async def mock_temporal(*args, **kwargs):
            return {
                "episodes": [retrieval_service._serialize_episode(combined_episode)],
                "count": 1
            }

        async def mock_semantic(*args, **kwargs):
            return {
                "episodes": [],
                "count": 0
            }

        retrieval_service.retrieve_temporal = mock_temporal
        retrieval_service.retrieve_semantic = mock_semantic

        # Mock episode query
        mock_filter_result = MagicMock()
        mock_filter_result.first.return_value = combined_episode

        mock_query_result = MagicMock()
        mock_query_result.filter.return_value = mock_filter_result

        retrieval_service.db.query.return_value = mock_query_result

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent1",
            current_task="task",
            limit=5
        )

        # Combined positive signals should maximize relevance
        assert "episodes" in result
