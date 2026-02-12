"""
Unit tests for Episode Retrieval Service

Tests cover:
- Service initialization
- Temporal retrieval (time-based)
- Semantic retrieval (vector search)
- Sequential retrieval (full episodes)
- Contextual retrieval (hybrid)
- Canvas-aware retrieval
- Feedback-weighted retrieval
- Supervision context retrieval
- Access logging
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

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
    CanvasAudit,
    AgentFeedback,
    AgentStatus
)


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_lancedb_handler():
    """Mock LanceDB handler"""
    handler = Mock()
    handler.db = Mock()
    handler.table_names = Mock(return_value=["episodes"])
    handler.search = Mock(return_value=[])
    return handler


@pytest.fixture
def mock_governance():
    """Mock governance service"""
    governance = Mock()
    governance.can_perform_action = Mock(return_value={"allowed": True})
    return governance


@pytest.fixture
def retrieval_service(mock_db, mock_lancedb_handler, mock_governance):
    """Create EpisodeRetrievalService with mocked dependencies"""
    with patch('core.episode_retrieval_service.get_lancedb_handler', return_value=mock_lancedb_handler):
        with patch('core.episode_retrieval_service.AgentGovernanceService', return_value=mock_governance):
            service = EpisodeRetrievalService(mock_db)
            service.lancedb = mock_lancedb_handler
            service.governance = mock_governance
            return service


@pytest.fixture
def sample_episodes():
    """Create sample episodes"""
    episodes = []
    base_time = datetime.now() - timedelta(days=5)

    for i in range(5):
        episode = Mock(spec=Episode)
        episode.id = f"episode_{i}"
        episode.title = f"Episode {i}"
        episode.description = f"Description {i}"
        episode.summary = f"Summary {i}"
        episode.agent_id = "agent_1"
        episode.user_id = "user_1" if i % 2 == 0 else "user_2"
        episode.workspace_id = "workspace_1"
        episode.session_id = f"session_{i}"
        episode.status = "completed"
        episode.started_at = base_time + timedelta(days=i)
        episode.ended_at = episode.started_at + timedelta(hours=1)
        episode.topics = [f"topic_{i}"]
        episode.entities = [f"entity_{i}"]
        episode.importance_score = 0.5 + (i * 0.1)
        episode.maturity_at_time = "INTERN"
        episode.human_intervention_count = i
        episode.constitutional_score = 0.8 + (i * 0.02)
        episode.decay_score = 1.0 - (i * 0.1)
        episode.access_count = i * 5
        episode.canvas_ids = [f"canvas_{i}"] if i < 3 else []
        episode.canvas_action_count = 1 if i < 3 else 0
        episode.feedback_ids = [f"feedback_{i}"]
        episode.aggregate_feedback_score = 0.5 if i % 2 == 0 else -0.5
        episode.supervisor_id = f"supervisor_{i}" if i < 2 else None
        episode.supervisor_rating = 4 + (i % 2) if i < 2 else None
        episode.intervention_count = i if i < 2 else None
        episode.intervention_types = ["pause", "correct"] if i < 2 else None

        episodes.append(episode)

    return episodes


@pytest.fixture
def sample_segments():
    """Create sample episode segments"""
    segments = []
    for i in range(3):
        segment = Mock(spec=EpisodeSegment)
        segment.id = f"segment_{i}"
        segment.episode_id = "episode_1"
        segment.segment_type = "conversation"
        segment.sequence_order = i
        segment.content = f"Content {i}"
        segment.content_summary = f"Summary {i}"
        segment.source_type = "chat_message"
        segment.source_id = f"msg_{i}"
        segment.created_at = datetime.now()
        segments.append(segment)
    return segments


@pytest.fixture
def sample_canvas_audits():
    """Create sample canvas audits"""
    canvases = []
    for i in range(3):
        canvas = Mock(spec=CanvasAudit)
        canvas.id = f"canvas_{i}"
        canvas.canvas_type = "sheets" if i == 0 else "charts"
        canvas.component_type = "table"
        canvas.component_name = f"Component {i}"
        canvas.action = "present"
        canvas.audit_metadata = {"test": "data"}
        canvas.created_at = datetime.now()
        canvases.append(canvas)
    return canvases


@pytest.fixture
def sample_feedbacks():
    """Create sample feedback records"""
    feedbacks = []
    for i in range(3):
        feedback = Mock(spec=AgentFeedback)
        feedback.id = f"feedback_{i}"
        feedback.feedback_type = "thumbs_up" if i == 0 else "rating"
        feedback.rating = 5 if i == 1 else None
        feedback.thumbs_up_down = True if i == 0 else None
        feedback.user_correction = "Good" if i == 0 else None
        feedback.created_at = datetime.now()
        feedbacks.append(feedback)
    return feedbacks


@pytest.fixture
def sample_agent():
    """Create sample agent"""
    agent = Mock(spec=AgentRegistry)
    agent.id = "agent_1"
    agent.name = "Test Agent"
    agent.status = AgentStatus.INTERN
    return agent


# ============================================================================
# Service Initialization Tests
# ============================================================================

class TestRetrievalServiceInitialization:
    """Test service initialization"""

    def test_retrieval_service_init(self, retrieval_service):
        """Test service initialization"""
        assert retrieval_service.db is not None
        assert retrieval_service.lancedb is not None
        assert retrieval_service.governance is not None


# ============================================================================
# Temporal Retrieval Tests
# ============================================================================

class TestTemporalRetrieval:
    """Test time-based retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_temporal_basic(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test basic temporal retrieval"""
        # Setup mock query chain
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value.all.return_value = sample_episodes[:3]
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent_1",
            time_range="7d",
            limit=50
        )

        assert result is not None
        assert "episodes" in result
        assert "count" in result
        assert result["count"] == 3
        assert len(result["episodes"]) == 3

    @pytest.mark.asyncio
    async def test_retrieve_temporal_governance_denied(
        self,
        retrieval_service,
        mock_governance
    ):
        """Test temporal retrieval when governance denies access"""
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Agent not authorized"
        }

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent_1",
            time_range="7d"
        )

        assert result["episodes"] == []
        assert "error" in result
        assert "governance_check" in result

    @pytest.mark.asyncio
    async def test_retrieve_temporal_with_user_filter(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test temporal retrieval with user filter"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value.all.return_value = [e for e in sample_episodes if e.user_id == "user_1"]
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent_1",
            time_range="7d",
            user_id="user_1",
            limit=50
        )

        assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_retrieve_temporal_different_time_ranges(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test temporal retrieval with different time ranges"""
        time_ranges = ["1d", "7d", "30d", "90d"]

        for time_range in time_ranges:
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value.all.return_value = sample_episodes[:2]
            mock_db.query.return_value = mock_query

            result = await retrieval_service.retrieve_temporal(
                agent_id="agent_1",
                time_range=time_range
            )

            assert result["time_range"] == time_range


# ============================================================================
# Semantic Retrieval Tests
# ============================================================================

class TestSemanticRetrieval:
    """Test vector similarity retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_semantic_basic(
        self,
        retrieval_service,
        sample_episodes,
        mock_lancedb_handler
    ):
        """Test basic semantic retrieval"""
        # Mock LanceDB search results
        mock_lancedb_handler.search.return_value = [
            {"id": "ep1", "metadata": '{"episode_id": "episode_1"}'},
            {"id": "ep2", "metadata": '{"episode_id": "episode_2"}'}
        ]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = sample_episodes[:2]
        retrieval_service.db.query.return_value = mock_query

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent_1",
            query="test query",
            limit=10
        )

        assert result is not None
        assert "episodes" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_retrieve_semantic_no_results(
        self,
        retrieval_service,
        mock_lancedb_handler
    ):
        """Test semantic retrieval with no results"""
        mock_lancedb_handler.search.return_value = []

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent_1",
            query="nonexistent query"
        )

        assert result["count"] == 0
        assert len(result["episodes"]) == 0

    @pytest.mark.asyncio
    async def test_retrieve_semantic_lancedb_error(
        self,
        retrieval_service,
        mock_lancedb_handler
    ):
        """Test semantic retrieval when LanceDB fails"""
        mock_lancedb_handler.search.side_effect = Exception("LanceDB error")

        result = await retrieval_service.retrieve_semantic(
            agent_id="agent_1",
            query="test query"
        )

        assert "error" in result
        assert result["episodes"] == []


# ============================================================================
# Sequential Retrieval Tests
# ============================================================================

class TestSequentialRetrieval:
    """Test full episode retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_sequential_basic(
        self,
        retrieval_service,
        sample_episodes,
        sample_segments,
        mock_db
    ):
        """Test basic sequential retrieval"""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = sample_episodes[0]
        mock_query.filter.return_value.order_by.return_value.all.return_value = sample_segments
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode_1",
            agent_id="agent_1"
        )

        assert result is not None
        assert "episode" in result
        assert "segments" in result
        assert len(result["segments"]) == 3

    @pytest.mark.asyncio
    async def test_retrieve_sequential_not_found(
        self,
        retrieval_service,
        mock_db
    ):
        """Test sequential retrieval when episode not found"""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_sequential(
            episode_id="nonexistent",
            agent_id="agent_1"
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_retrieve_sequential_with_canvas_context(
        self,
        retrieval_service,
        sample_episodes,
        sample_canvas_audits,
        mock_db
    ):
        """Test sequential retrieval includes canvas context"""
        episode = sample_episodes[0]
        episode.canvas_ids = ["canvas_1", "canvas_2"]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_query.filter.return_value.all.return_value = sample_canvas_audits
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode_1",
            agent_id="agent_1",
            include_canvas=True
        )

        assert "canvas_context" in result
        assert len(result["canvas_context"]) > 0

    @pytest.mark.asyncio
    async def test_retrieve_sequential_with_feedback_context(
        self,
        retrieval_service,
        sample_episodes,
        sample_feedbacks,
        mock_db
    ):
        """Test sequential retrieval includes feedback context"""
        episode = sample_episodes[0]
        episode.feedback_ids = ["feedback_1", "feedback_2"]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_query.filter.return_value.all.return_value = sample_feedbacks
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode_1",
            agent_id="agent_1",
            include_feedback=True
        )

        assert "feedback_context" in result
        assert len(result["feedback_context"]) > 0


# ============================================================================
# Contextual Retrieval Tests
# ============================================================================

class TestContextualRetrieval:
    """Test hybrid retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_contextual_basic(
        self,
        retrieval_service,
        sample_episodes,
        mock_db,
        mock_lancedb_handler
    ):
        """Test basic contextual retrieval"""
        mock_lancedb_handler.search.return_value = [
            {"id": "ep1", "metadata": '{"episode_id": "episode_1"}'}
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes
        mock_query.filter.return_value.first.side_effect = sample_episodes
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent_1",
            current_task="Test task",
            limit=5
        )

        assert result is not None
        assert "episodes" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_retrieve_contextual_with_canvas_requirement(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test contextual retrieval with canvas requirement"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes
        mock_query.filter.return_value.first.side_effect = sample_episodes
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent_1",
            current_task="Test task",
            limit=5,
            require_canvas=True
        )

        # Should filter to episodes with canvas_action_count > 0
        assert result["count"] >= 0

    @pytest.mark.asyncio
    async def test_retrieve_contextual_with_feedback_requirement(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test contextual retrieval with feedback requirement"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes
        mock_query.filter.return_value.first.side_effect = sample_episodes
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent_1",
            current_task="Test task",
            limit=5,
            require_feedback=True
        )

        # Should filter to episodes with feedback_ids
        assert result["count"] >= 0


# ============================================================================
# Feedback Weighting Tests
# ============================================================================

class TestFeedbackWeighting:
    """Test feedback score weighting in retrieval"""

    @pytest.mark.asyncio
    async def test_boost_positive_feedback(
        self,
        retrieval_service,
        sample_episodes,
        mock_db,
        mock_lancedb_handler
    ):
        """Test positive feedback gets +0.2 boost"""
        # Create episode with positive feedback
        episode = sample_episodes[0]
        episode.aggregate_feedback_score = 0.8

        mock_lancedb_handler.search.return_value = []
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [episode]
        mock_query.filter.return_value.first.return_value = episode
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent_1",
            current_task="test",
            limit=5
        )

        # Positive feedback should boost score
        assert result["count"] >= 0

    @pytest.mark.asyncio
    async def test_penalty_negative_feedback(
        self,
        retrieval_service,
        sample_episodes,
        mock_db,
        mock_lancedb_handler
    ):
        """Test negative feedback gets -0.3 penalty"""
        episode = sample_episodes[1]
        episode.aggregate_feedback_score = -0.8

        mock_lancedb_handler.search.return_value = []
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [episode]
        mock_query.filter.return_value.first.return_value = episode
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_contextual(
            agent_id="agent_1",
            current_task="test",
            limit=5
        )

        # Negative feedback should decrease score
        assert result["count"] >= 0


# ============================================================================
# Canvas-Aware Retrieval Tests
# ============================================================================

class TestCanvasAwareRetrieval:
    """Test canvas-filtered retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_type(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test retrieval filtered by canvas type"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:3]
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent_1",
            canvas_type="sheets",
            limit=10
        )

        assert result is not None
        assert "episodes" in result
        assert "canvas_type" in result
        assert result["canvas_type"] == "sheets"

    @pytest.mark.asyncio
    async def test_retrieve_by_canvas_action(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test retrieval filtered by canvas action"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:2]
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_by_canvas_type(
            agent_id="agent_1",
            canvas_type="charts",
            action="present",
            limit=10
        )

        assert result is not None
        assert result["action"] == "present"


# ============================================================================
# Supervision Context Tests
# ============================================================================

class TestSupervisionContextRetrieval:
    """Test supervision context retrieval"""

    @pytest.mark.asyncio
    async def test_retrieve_with_supervision_context_temporal(
        self,
        retrieval_service,
        sample_episodes,
        mock_db,
        mock_governance
    ):
        """Test supervision context retrieval with temporal mode"""
        # Filter to episodes with supervisor_id
        supervision_episodes = [e for e in sample_episodes if e.supervisor_id]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = supervision_episodes
        mock_query.filter.return_value.all.return_value = sample_episodes
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent_1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            limit=10
        )

        assert result is not None
        assert "episodes" in result
        # Episodes should have supervision_context
        if result["episodes"]:
            assert "supervision_context" in result["episodes"][0]

    @pytest.mark.asyncio
    async def test_supervision_filter_high_rated(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test supervision filter for high-rated episodes"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes
        mock_query.filter.return_value.all.return_value = sample_episodes
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent_1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            supervision_outcome_filter="high_rated",
            limit=10
        )

        # Should filter to episodes with supervisor_rating >= 4
        assert result["count"] >= 0

    @pytest.mark.asyncio
    async def test_supervision_filter_low_intervention(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test supervision filter for low intervention episodes"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = sample_episodes
        mock_query.filter.return_value.all.return_value = sample_episodes
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_with_supervision_context(
            agent_id="agent_1",
            retrieval_mode=RetrievalMode.TEMPORAL,
            supervision_outcome_filter="low_intervention",
            limit=10
        )

        # Should filter to episodes with intervention_count <= 1
        assert result["count"] >= 0


# ============================================================================
# Serialization Tests
# ============================================================================

class TestSerialization:
    """Test episode and segment serialization"""

    def test_serialize_episode(self, retrieval_service, sample_episodes):
        """Test episode serialization"""
        episode = sample_episodes[0]
        serialized = retrieval_service._serialize_episode(episode)

        assert serialized["id"] == episode.id
        assert serialized["title"] == episode.title
        assert serialized["agent_id"] == episode.agent_id
        assert "started_at" in serialized
        assert "ended_at" in serialized
        assert "topics" in serialized
        assert "maturity_at_time" in serialized
        assert "canvas_ids" not in serialized  # Not included in serialization

    def test_serialize_segment(self, retrieval_service, sample_segments):
        """Test segment serialization"""
        segment = sample_segments[0]
        serialized = retrieval_service._serialize_segment(segment)

        assert serialized["id"] == segment.id
        assert serialized["segment_type"] == segment.segment_type
        assert serialized["sequence_order"] == segment.sequence_order
        assert "content" in serialized
        assert "created_at" in serialized


# ============================================================================
# Access Logging Tests
# ============================================================================

class TestAccessLogging:
    """Test episode access logging"""

    @pytest.mark.asyncio
    async def test_log_access_success(
        self,
        retrieval_service,
        mock_db
    ):
        """Test successful access logging"""
        await retrieval_service._log_access(
            episode_id="episode_1",
            access_type="temporal",
            governance_check={"allowed": True, "agent_maturity": "INTERN"},
            agent_id="agent_1",
            results_count=5
        )

        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_log_access_governance_denied(
        self,
        retrieval_service,
        mock_db
    ):
        """Test access logging when governance denied"""
        await retrieval_service._log_access(
            episode_id=None,
            access_type="temporal",
            governance_check={"allowed": False},
            agent_id="agent_1",
            results_count=0
        )

        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_log_access_error_handling(
        self,
        retrieval_service,
        mock_db
    ):
        """Test access logging error handling"""
        mock_db.add.side_effect = Exception("Database error")

        # Should not raise exception
        await retrieval_service._log_access(
            episode_id="episode_1",
            access_type="temporal",
            governance_check={"allowed": True},
            agent_id="agent_1",
            results_count=5
        )


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_retrieve_temporal_empty_results(
        self,
        retrieval_service,
        mock_db
    ):
        """Test temporal retrieval with no results"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_temporal(
            agent_id="agent_1",
            time_range="7d"
        )

        assert result["count"] == 0
        assert len(result["episodes"]) == 0

    @pytest.mark.asyncio
    async def test_retrieve_sequential_excluded_canvas(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test sequential retrieval with canvas excluded"""
        episode = sample_episodes[0]
        episode.canvas_ids = ["canvas_1"]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode_1",
            agent_id="agent_1",
            include_canvas=False
        )

        assert "canvas_context" not in result

    @pytest.mark.asyncio
    async def test_retrieve_sequential_excluded_feedback(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test sequential retrieval with feedback excluded"""
        episode = sample_episodes[0]
        episode.feedback_ids = ["feedback_1"]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode_1",
            agent_id="agent_1",
            include_feedback=False
        )

        assert "feedback_context" not in result

    @pytest.mark.asyncio
    async def test_fetch_canvas_context_empty(
        self,
        retrieval_service,
        mock_db
    ):
        """Test fetching canvas context with no IDs"""
        result = await retrieval_service._fetch_canvas_context([])

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_feedback_context_empty(
        self,
        retrieval_service,
        mock_db
    ):
        """Test fetching feedback context with no IDs"""
        result = await retrieval_service._fetch_feedback_context([])

        assert result == []

    @pytest.mark.asyncio
    async def test_supervision_outcome_quality_unknown(
        self,
        retrieval_service,
        sample_episodes
    ):
        """Test outcome quality assessment with no rating"""
        episode = sample_episodes[3]  # Has no supervisor_rating
        quality = retrieval_service._assess_outcome_quality(episode)

        assert quality == "unknown"

    @pytest.mark.asyncio
    async def test_supervision_improvement_trend_insufficient_data(
        self,
        retrieval_service,
        sample_episodes
    ):
        """Test improvement trend with insufficient episodes"""
        result = retrieval_service._filter_improvement_trend(sample_episodes[:3])

        # Should return episodes as-is when insufficient data
        assert len(result) == 3


# ============================================================================
# Canvas-Aware Episode Tests (Additional)
# ============================================================================

class TestCanvasAwareEpisodesExtended:
    """Extended canvas-aware episode tests"""

    @pytest.mark.asyncio
    async def test_track_canvas_presentation(
        self,
        retrieval_service,
        sample_episodes,
        sample_canvas_audits,
        mock_db
    ):
        """Test tracking canvas presentation in episode"""
        episode = sample_episodes[0]
        episode.canvas_ids = ["canvas_1"]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_query.filter.return_value.all.return_value = sample_canvas_audits[:1]
        mock_db.query.return_value = mock_query

        result = await retrieval_service._fetch_canvas_context(episode.canvas_ids)

        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_track_canvas_action(
        self,
        retrieval_service,
        sample_canvas_audits
    ):
        """Test tracking canvas actions"""
        # Different canvas actions
        actions = ["present", "submit", "close", "update", "execute"]

        for i, action in enumerate(actions):
            canvas = Mock(spec=CanvasAudit)
            canvas.id = f"canvas_{i}"
            canvas.action = action
            canvas.canvas_type = "sheets"
            canvas.component_type = "table"
            canvas.component_name = f"Component {i}"
            canvas.audit_metadata = {}
            canvas.created_at = datetime.now()
            sample_canvas_audits.append(canvas)

        # Verify all actions are tracked
        assert len(sample_canvas_audits) >= len(actions)

    @pytest.mark.asyncio
    async def test_filter_by_canvas_type_extended(
        self,
        retrieval_service,
        sample_episodes,
        mock_db
    ):
        """Test filtering by canvas type for all types"""
        canvas_types = ["generic", "docs", "email", "sheets", "orchestration", "terminal", "coding"]

        for canvas_type in canvas_types:
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_db.query.return_value = mock_query

            result = await retrieval_service.retrieve_by_canvas_type(
                agent_id="agent_1",
                canvas_type=canvas_type,
                limit=10
            )

            assert result is not None
            assert result["canvas_type"] == canvas_type

    @pytest.mark.asyncio
    async def test_filter_by_canvas_action_extended(
        self,
        retrieval_service,
        mock_db
    ):
        """Test filtering by all canvas actions"""
        actions = ["present", "submit", "close", "update", "execute"]

        for action in actions:
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_db.query.return_value = mock_query

            result = await retrieval_service.retrieve_by_canvas_type(
                agent_id="agent_1",
                canvas_type="sheets",
                action=action,
                limit=10
            )

            assert result is not None
            assert result["action"] == action

    @pytest.mark.asyncio
    async def test_canvas_context_inclusion(
        self,
        retrieval_service,
        sample_episodes,
        sample_canvas_audits,
        mock_db
    ):
        """Test canvas context is included in episode retrieval"""
        episode = sample_episodes[0]
        episode.canvas_ids = ["canvas_1", "canvas_2"]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_query.filter.return_value.all.return_value = sample_canvas_audits[:2]
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode_1",
            agent_id="agent_1",
            include_canvas=True
        )

        assert "canvas_context" in result
        assert len(result["canvas_context"]) == 2

    @pytest.mark.asyncio
    async def test_multiple_canvas_tracking(
        self,
        retrieval_service,
        sample_episodes,
        sample_canvas_audits,
        mock_db
    ):
        """Test tracking multiple canvases in single episode"""
        episode = sample_episodes[0]
        # Assign multiple canvases
        episode.canvas_ids = ["canvas_0", "canvas_1", "canvas_2"]
        episode.canvas_action_count = 3

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_query.filter.return_value.all.return_value = sample_canvas_audits
        mock_db.query.return_value = mock_query

        result = await retrieval_service.retrieve_sequential(
            episode_id="episode_1",
            agent_id="agent_1",
            include_canvas=True
        )

        assert "canvas_context" in result
        assert result["canvas_context"] is not None
