"""
Additional integration coverage tests for episode services.

Tests for EpisodeSegmentationService, EpisodeRetrievalService, and EpisodeLifecycleService.
These tests call actual class methods to increase coverage beyond existing test files.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from core.episode_segmentation_service import (
    EpisodeBoundaryDetector,
    EpisodeSegmentationService,
)
from core.episode_retrieval_service import EpisodeRetrievalService
from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import Episode, EpisodeSegment
from core.database import get_db_session

@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    with get_db_session() as db:
        yield db

@pytest.fixture
def segmentation_service(db_session):
    """Create segmentation service with mocked BYOK handler."""
    mock_byok = Mock()
    return EpisodeSegmentationService(db_session, byok_handler=mock_byok)

@pytest.fixture
def boundary_detector():
    """Create boundary detector with mocked handler."""
    return EpisodeBoundaryDetector(lancedb_handler=Mock())

@pytest.fixture
def retrieval_service(db_session):
    """Create retrieval service."""
    return EpisodeRetrievalService(db_session)

@pytest.fixture
def lifecycle_service(db_session):
    """Create lifecycle service."""
    return EpisodeLifecycleService(db_session)

class TestEpisodeSegmentationMethods:
    """Tests for EpisodeSegmentationService methods."""

    def test_detect_time_gap(self, boundary_detector):
        """Test time gap detection."""
        from core.models import ChatMessage
        now = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id="1",
                role="user",
                content="First message",
                created_at=now - timedelta(minutes=10)
            ),
            ChatMessage(
                id="2",
                role="assistant",
                content="Second message",
                created_at=now - timedelta(minutes=5)
            ),
            ChatMessage(
                id="3",
                role="user",
                content="Third message after long gap",
                created_at=now  # 5 minute gap
            ),
        ]

        gaps = boundary_detector.detect_time_gap(messages)
        assert isinstance(gaps, list)
        # Should detect gap at index 2 (third message)

    def test_detect_topic_changes(self, boundary_detector):
        """Test topic change detection."""
        from core.models import ChatMessage
        now = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id="1",
                role="user",
                content="Let's talk about finance",
                created_at=now
            ),
            ChatMessage(
                id="2",
                role="assistant",
                content="Sure, I can help with finance",
                created_at=now
            ),
            ChatMessage(
                id="3",
                role="user",
                content="Now let's switch to HR topics",
                created_at=now
            ),
        ]

        changes = boundary_detector.detect_topic_changes(messages)
        assert isinstance(changes, list)

    def test_extract_topics(self, segmentation_service):
        """Test topic extraction."""
        topics = segmentation_service._extract_topics([], [])
        assert isinstance(topics, list)

    def test_extract_entities(self, segmentation_service):
        """Test entity extraction."""
        entities = segmentation_service._extract_entities([], [])
        assert isinstance(entities, list)

    def test_calculate_importance(self, segmentation_service):
        """Test importance calculation."""
        importance = segmentation_service._calculate_importance([], [])
        assert isinstance(importance, float)

    def test_get_agent_maturity(self, segmentation_service):
        """Test getting agent maturity level."""
        maturity = segmentation_service._get_agent_maturity("test_agent")
        assert isinstance(maturity, str)

    def test_count_interventions(self, segmentation_service):
        """Test counting interventions."""
        interventions = segmentation_service._count_interventions([])
        assert isinstance(interventions, int)

    def test_extract_skill_metadata(self, segmentation_service):
        """Test extracting skill metadata."""
        metadata = segmentation_service.extract_skill_metadata({
            "skill_name": "test_skill",
            "inputs": {"param1": "value1"}
        })
        assert isinstance(metadata, dict)

    def test_summarize_skill_inputs(self, segmentation_service):
        """Test summarizing skill inputs."""
        summary = segmentation_service._summarize_skill_inputs({
            "param1": "value1",
            "param2": "value2"
        })
        assert isinstance(summary, str)

class TestEpisodeRetrievalMethods:
    """Tests for EpisodeRetrievalService methods."""

    @pytest.mark.asyncio
    async def test_retrieve_temporal_empty(self, retrieval_service):
        """Test temporal retrieval with no episodes."""
        episodes = await retrieval_service.retrieve_temporal(
            agent_id="nonexistent_agent",
            time_range="7d",
            limit=10
        )
        assert isinstance(episodes, dict)
        assert "episodes" in episodes

    @pytest.mark.asyncio
    async def test_retrieve_semantic_empty(self, retrieval_service):
        """Test semantic retrieval with no episodes."""
        episodes = await retrieval_service.retrieve_semantic(
            agent_id="nonexistent_agent",
            query="test query",
            limit=5
        )
        assert isinstance(episodes, dict)
        assert "episodes" in episodes

    @pytest.mark.asyncio
    async def test_retrieve_sequential_empty(self, retrieval_service):
        """Test sequential retrieval with no episodes."""
        episodes = await retrieval_service.retrieve_sequential(
            episode_id="nonexistent_episode",
            agent_id="nonexistent_agent"
        )
        assert isinstance(episodes, dict)

    @pytest.mark.asyncio
    async def test_retrieve_contextual_empty(self, retrieval_service):
        """Test contextual retrieval with no episodes."""
        episodes = await retrieval_service.retrieve_contextual(
            agent_id="nonexistent_agent",
            current_task="test context",
            limit=5
        )
        assert isinstance(episodes, dict)
        assert "episodes" in episodes

    @pytest.mark.asyncio
    async def test_retrieve_canvas_aware_empty(self, retrieval_service):
        """Test canvas-aware retrieval."""
        episodes = await retrieval_service.retrieve_canvas_aware(
            agent_id="nonexistent_agent",
            query="test canvas query",
            limit=5
        )
        assert isinstance(episodes, dict)

    def test_serialize_episode(self, retrieval_service):
        """Test episode serialization."""
        # Create a mock episode
        episode = Episode(
            id="test_episode",
            agent_id="test_agent",
            task_description="Test Episode",
            tenant_id="t1",
            status="active",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            maturity_at_time="SUPERVISED",
            human_intervention_count=0,
            constitutional_score=0.5,
            access_count=0,
            decay_score=0.0,
        )

        serialized = retrieval_service._serialize_episode(episode)
        assert isinstance(serialized, dict)
        assert serialized["id"] == "test_episode"
        assert serialized["title"] == "Test Episode"

class TestEpisodeLifecycleMethods:
    """Tests for EpisodeLifecycleService methods."""

    @pytest.mark.asyncio
    async def test_decay_old_episodes_empty(self, lifecycle_service):
        """Test decay on a DB with no stale episodes."""
        result = await lifecycle_service.decay_old_episodes(days_threshold=90)
        assert isinstance(result, dict)
        assert "affected" in result
        assert "archived" in result

    def test_archive_episode_success(self, lifecycle_service):
        """Test archiving an episode."""
        db = Mock()
        lifecycle_service.db = db
        episode = Mock()
        episode.id = "ep_1"
        episode.status = "active"
        episode.archived_at = None
        result = lifecycle_service.archive_episode(episode)
        assert result is True
        assert episode.status == "archived"
        assert episode.archived_at is not None
        db.commit.assert_called_once()

    def test_archive_episode_commit_error(self, lifecycle_service):
        """Test archiving when commit fails."""
        db = Mock()
        lifecycle_service.db = db
        episode = Mock()
        episode.id = "ep_1"
        episode.status = "active"
        episode.archived_at = None
        db.commit.side_effect = RuntimeError("boom")
        result = lifecycle_service.archive_episode(episode)
        assert result is False
        db.rollback.assert_called_once()

    def test_update_lifecycle(self, lifecycle_service):
        """Test update_lifecycle on a mock episode."""
        episode = Mock()
        episode.started_at = datetime.now(timezone.utc) - timedelta(days=30)
        episode.access_count = 5
        episode.status = "active"
        episode.decay_score = 0.0
        episode.archived_at = None
        result = lifecycle_service.update_lifecycle(episode)
        assert result is True

class TestEpisodeServiceIntegration:
    """Integration tests across episode services."""

    def test_service_initialization(self, segmentation_service, retrieval_service, lifecycle_service):
        """Test that all services initialize correctly."""
        assert segmentation_service is not None
        assert retrieval_service is not None
        assert lifecycle_service is not None

    def test_database_access(self, segmentation_service, retrieval_service, lifecycle_service):
        """Test that services can access database."""
        # All services should have db attribute
        assert segmentation_service.db is not None
        assert retrieval_service.db is not None
        assert lifecycle_service.db is not None

    def test_serialize_multiple_episodes(self, retrieval_service):
        """Test serializing multiple episodes."""
        episodes = [
            Episode(
                id=f"ep_{i}",
                agent_id="test_agent",
                task_description=f"Episode {i}",
                tenant_id="t1",
                status="active",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                maturity_at_time="SUPERVISED",
                human_intervention_count=0,
                constitutional_score=0.5,
                access_count=0,
                decay_score=0.0,
            )
            for i in range(3)
        ]

        serialized = [retrieval_service._serialize_episode(ep) for ep in episodes]
        assert len(serialized) == 3
        assert all(isinstance(s, dict) for s in serialized)

    @pytest.mark.asyncio
    async def test_retrieve_all_modes_empty(self, retrieval_service):
        """Test all retrieval modes with no data."""
        agent_id = "empty_test_agent"

        temporal = await retrieval_service.retrieve_temporal(agent_id, limit=5)
        semantic = await retrieval_service.retrieve_semantic(agent_id, query="test", limit=5)
        sequential = await retrieval_service.retrieve_sequential(
            episode_id="nonexistent", agent_id=agent_id
        )
        contextual = await retrieval_service.retrieve_contextual(
            agent_id, current_task="test", limit=5
        )

        # All should return dicts
        assert isinstance(temporal, dict)
        assert isinstance(semantic, dict)
        assert isinstance(sequential, dict)
        assert isinstance(contextual, dict)

class TestEpisodeSegmentationHelpers:
    """Tests for segmentation helper methods."""

    def test_format_messages(self, segmentation_service):
        """Test message formatting."""
        from core.models import ChatMessage
        now = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id="1",
                role="user",
                content="Test message",
                created_at=now
            )
        ]

        formatted = segmentation_service._format_messages(messages)
        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_summarize_messages(self, segmentation_service):
        """Test message summarization."""
        from core.models import ChatMessage
        now = datetime.now(timezone.utc)

        messages = [
            ChatMessage(
                id=str(i),
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                created_at=now
            )
            for i in range(5)
        ]

        summary = segmentation_service._summarize_messages(messages)
        assert isinstance(summary, str)

    def test_format_skill_content(self, segmentation_service):
        """Test skill content formatting."""
        formatted = segmentation_service._format_skill_content(
            skill_name="test_skill",
            result={"output": "success"},
            error=None
        )
        assert isinstance(formatted, str)

        formatted_error = segmentation_service._format_skill_content(
            skill_name="test_skill",
            result=None,
            error=Exception("Test error")
        )
        assert isinstance(formatted_error, str)
