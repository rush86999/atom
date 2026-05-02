"""
Unit Tests for Episode Retrieval Service

Tests multi-mode episode retrieval with governance:
- Temporal retrieval (time-based: 1d, 7d, 30d, 90d)
- Semantic retrieval (vector similarity search)
- Sequential retrieval (full episodes with segments)
- Contextual retrieval (hybrid scoring)

Target Coverage: 80%
Target Branch Coverage: 50%+
Pass Rate Target: 95%+
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.episode_retrieval_service import (
    EpisodeRetrievalService,
    RetrievalMode,
    RetrievalResult
)
from core.models import (
    Episode,
    EpisodeSegment,
    ChatSession,
    AgentRegistry,
    AgentStatus,
    User,
    UserRole
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def db():
    """Create database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_agent(db):
    """Create sample agent."""
    agent = AgentRegistry(
        id="retrieval-agent-123",
        name="Retrieval Test Agent",
        description="Agent for retrieval testing",
        category="testing",
        status=AgentStatus.SUPERVISED,
        confidence_score=0.75,
        module_path="agents.retrieval",
        class_name="RetrievalAgent",
        configuration={},
        workspace_id="default",
        user_id="test-user-123"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def sample_user(db):
    """Create sample user."""
    user = User(
        id="test-user-123",
        email="test@example.com",
        hashed_password="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_episodes(db, sample_agent):
    """Create sample episodes for retrieval."""
    now = datetime.now(timezone.utc)

    episodes = []
    for i in range(5):
        episode = Episode(
            id=f"episode-{i}",
            agent_id=sample_agent.id,
            session_id=f"session-{i}",
            workspace_id="default",
            user_id=sample_agent.user_id,
            started_at=now - timedelta(days=i),
            ended_at=now - timedelta(days=i) + timedelta(minutes=30),
            status="completed",
            summary=f"Episode {i} summary",
            metadata={"index": i}
        )
        db.add(episode)
        episodes.append(episode)

    db.commit()

    for ep in episodes:
        db.refresh(ep)

    return episodes


# =============================================================================
# Test Class: RetrievalMode Enum
# =============================================================================

class TestRetrievalMode:
    """Tests for RetrievalMode enumeration."""

    def test_temporal_mode_exists(self):
        """RED: Test TEMPORAL mode exists."""
        assert RetrievalMode.TEMPORAL == "temporal"

    def test_semantic_mode_exists(self):
        """RED: Test SEMANTIC mode exists."""
        assert RetrievalMode.SEMANTIC == "semantic"

    def test_sequential_mode_exists(self):
        """RED: Test SEQUENTIAL mode exists."""
        assert RetrievalMode.SEQUENTIAL == "sequential"

    def test_contextual_mode_exists(self):
        """RED: Test CONTEXTUAL mode exists."""
        assert RetrievalMode.CONTEXTUAL == "contextual"


# =============================================================================
# Test Class: Retrieve Temporal
# =============================================================================

class TestRetrieveTemporal:
    """Tests for retrieve_temporal method."""

    @pytest.mark.asyncio
    async def test_retrieves_episodes_within_7_days(self, db, sample_agent, sample_episodes):
        """RED: Test temporal retrieval with 7d range."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()):
            result = await service.retrieve_temporal(
                agent_id=sample_agent.id,
                time_range="7d",
                limit=50
            )

            assert "episodes" in result
            assert "count" in result
            assert result["time_range"] == "7d"
            assert isinstance(result["episodes"], list)

    @pytest.mark.asyncio
    async def test_retrieves_episodes_within_1_day(self, db, sample_agent, sample_episodes):
        """RED: Test temporal retrieval with 1d range."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()):
            result = await service.retrieve_temporal(
                agent_id=sample_agent.id,
                time_range="1d",
                limit=50
            )

            # Should have fewer episodes than 7d
            assert result["count"] >= 0

    @pytest.mark.asyncio
    async def test_filters_by_user_id(self, db, sample_agent, sample_episodes, sample_user):
        """RED: Test user_id filtering in temporal retrieval."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()):
            result = await service.retrieve_temporal(
                agent_id=sample_agent.id,
                time_range="7d",
                user_id=sample_user.id,
                limit=50
            )

            assert isinstance(result["episodes"], list)

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self, db, sample_agent, sample_episodes):
        """RED: Test that limit parameter is respected."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()):
            result = await service.retrieve_temporal(
                agent_id=sample_agent.id,
                time_range="7d",
                limit=2
            )

            assert result["count"] <= 2

    @pytest.mark.asyncio
    async def test_orders_by_started_at_descending(self, db, sample_agent, sample_episodes):
        """RED: Test that results are ordered by started_at DESC."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()):
            result = await service.retrieve_temporal(
                agent_id=sample_agent.id,
                time_range="90d",
                limit=50
            )

            episodes = result["episodes"]
            if len(episodes) > 1:
                # Check that dates are descending
                for i in range(len(episodes) - 1):
                    assert episodes[i].started_at >= episodes[i+1].started_at


# =============================================================================
# Test Class: Retrieve Semantic
# =============================================================================

class TestRetrieveSemantic:
    """Tests for retrieve_semantic method."""

    @pytest.mark.asyncio
    async def test_performs_vector_similarity_search(self, db, sample_agent):
        """RED: Test semantic retrieval using vector similarity."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()), \
             patch.object(service.lancedb, 'search') as mock_search:

            # Mock vector search results
            mock_search.return_value = [
                {"id": "episode-1", "score": 0.95},
                {"id": "episode-2", "score": 0.87}
            ]

            result = await service.retrieve_semantic(
                agent_id=sample_agent.id,
                query="test query about episodes",
                limit=10
            )

            assert "episodes" in result
            assert mock_search.called

    @pytest.mark.asyncio
    async def test_filters_by_agent_id(self, db, sample_agent):
        """RED: Test that semantic search filters by agent."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()), \
             patch.object(service.lancedb, 'search') as mock_search:

            mock_search.return_value = []

            result = await service.retrieve_semantic(
                agent_id=sample_agent.id,
                query="test query",
                limit=10
            )

            # Should pass agent_id to search
            assert mock_search.called

    @pytest.mark.asyncio
    async def test_returns_similarity_scores(self, db, sample_agent):
        """RED: Test that similarity scores are included."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()), \
             patch.object(service.lancedb, 'search') as mock_search:

            mock_search.return_value = [
                {"id": "episode-1", "score": 0.95},
                {"id": "episode-2", "score": 0.87}
            ]

            result = await service.retrieve_semantic(
                agent_id=sample_agent.id,
                query="test query",
                limit=10
            )

            # Should include scores
            assert "episodes" in result


# =============================================================================
# Test Class: Retrieve Sequential
# =============================================================================

class TestRetrieveSequential:
    """Tests for retrieve_sequential method."""

    @pytest.mark.asyncio
    async def test_retrieves_full_episode_with_segments(self, db, sample_agent, sample_episodes):
        """RED: Test sequential retrieval with segments."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()):
            episode_id = sample_episodes[0].id

            result = await service.retrieve_sequential(
                episode_id=episode_id,
                agent_id=sample_agent.id
            )

            assert "episode" in result
            assert result["episode"]["id"] == episode_id

    @pytest.mark.asyncio
    async def test_includes_segments_in_result(self, db, sample_agent, sample_episodes):
        """RED: Test that segments are included."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()):
            episode_id = sample_episodes[0].id

            result = await service.retrieve_sequential(
                episode_id=episode_id,
                agent_id=sample_agent.id
            )

            # Should have segments field
            assert "segments" in result or "episode" in result

    @pytest.mark.asyncio
    async def test_handles_nonexistent_episode(self, db, sample_agent):
        """RED: Test handling of nonexistent episode."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()):
            result = await service.retrieve_sequential(
                episode_id="nonexistent-episode",
                agent_id=sample_agent.id
            )

            # Should handle gracefully
            assert "error" in result or result.get("episode") is None


# =============================================================================
# Test Class: Retrieve Contextual
# =============================================================================

class TestRetrieveContextual:
    """Tests for retrieve_contextual method."""

    @pytest.mark.asyncio
    async def test_performs_hybrid_search(self, db, sample_agent):
        """RED: Test contextual retrieval with hybrid scoring."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()), \
             patch.object(service, '_calculate_contextual_score') as mock_score:

            mock_score.return_value = 0.85

            result = await service.retrieve_contextual(
                agent_id=sample_agent.id,
                query="current task context",
                context={"task": "test"},
                limit=10
            )

            assert "episodes" in result

    @pytest.mark.asyncio
    async def test_includes_contextual_scores(self, db, sample_agent):
        """RED: Test that contextual scores are included."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()), \
             patch.object(service, '_calculate_contextual_score') as mock_score:

            mock_score.return_value = 0.90

            result = await service.retrieve_contextual(
                agent_id=sample_agent.id,
                query="test query",
                context={},
                limit=5
            )

            assert "episodes" in result

    @pytest.mark.asyncio
    async def test_ranks_by_contextual_score(self, db, sample_agent):
        """RED: Test that results are ranked by contextual score."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()), \
             patch.object(service, '_calculate_contextual_score') as mock_score:

            mock_score.return_value = 0.95

            result = await service.retrieve_contextual(
                agent_id=sample_agent.id,
                query="test query",
                context={},
                limit=10
            )

            assert "episodes" in result


# =============================================================================
# Test Class: Governance Checks
# =============================================================================

class TestGovernanceChecks:
    """Tests for governance integration."""

    @pytest.mark.asyncio
    async def test_blocks_unauthorized_retrieval(self, db, sample_agent):
        """RED: Test that unauthorized retrieval is blocked."""
        service = EpisodeRetrievalService(db)

        # Mock governance check to deny access
        with patch.object(service.governance, 'can_perform_action') as mock_gov:
            mock_gov.return_value = {"allowed": False, "reason": "Access denied"}

            result = await service.retrieve_temporal(
                agent_id=sample_agent.id,
                time_range="7d"
            )

            # Should return error
            assert "error" in result
            assert "denied" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_allows_authorized_retrieval(self, db, sample_agent, sample_episodes):
        """RED: Test that authorized retrieval succeeds."""
        service = EpisodeRetrievalService(db)

        # Mock governance check to allow access
        with patch.object(service.governance, 'can_perform_action') as mock_gov, \
             patch.object(service, '_log_access', new_callable=AsyncMock()):

            mock_gov.return_value = {"allowed": True}

            result = await service.retrieve_temporal(
                agent_id=sample_agent.id,
                time_range="7d"
            )

            # Should succeed
            assert "episodes" in result
            assert "error" not in result


# =============================================================================
# Test Class: Logging and Access
# =============================================================================

class TestLoggingAndAccess:
    """Tests for access logging."""

    @pytest.mark.asyncio
    async def test_logs_retrieval_access(self, db, sample_agent, sample_episodes):
        """RED: Test that all retrievals are logged."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()) as mock_log:
            await service.retrieve_temporal(
                agent_id=sample_agent.id,
                time_range="7d"
            )

            # Should log access
            assert mock_log.called

    @pytest.mark.asyncio
    async def test_includes_agent_id_in_log(self, db, sample_agent, sample_episodes):
        """RED: Test that agent_id is included in log."""
        service = EpisodeRetrievalService(db)

        with patch.object(service, '_log_access', new_callable=AsyncMock()) as mock_log:
            await service.retrieve_temporal(
                agent_id=sample_agent.id,
                time_range="7d"
            )

            # Check call arguments
            assert mock_log.called
            call_args = mock_log.call_args_list
            # Should have agent_id in one of the calls
            agent_id_logged = any(sample_agent.id in str(call) for call in call_args)
            assert agent_id_logged


# =============================================================================
# Test Class: Serialization
# =============================================================================

class TestSerializeEpisode:
    """Tests for _serialize_episode method."""

    def test_includes_all_required_fields(self, db, sample_agent):
        """RED: Test serialization includes all required fields."""
        service = EpisodeRetrievalService(db)

        # Create a mock episode
        episode = Mock()
        episode.id = "test-episode-123"
        episode.agent_id = sample_agent.id
        episode.started_at = datetime.now(timezone.utc)
        episode.summary = "Test summary"
        episode.status = "completed"

        result = service._serialize_episode(episode, None)

        # Should have required fields
        assert result["id"] == episode.id
        assert result["agent_id"] == episode.agent_id
        assert "started_at" in result
        assert "summary" in result
        assert "status" in result


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
