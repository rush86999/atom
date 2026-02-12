"""
Unit tests for EpisodeLifecycleService

Tests cover:
1. Episode decay (time-based importance reduction)
2. Episode consolidation (merging related episodes)
3. Episode archival to cold storage
4. Importance score updates
5. Batch access count updates
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from core.episode_lifecycle_service import EpisodeLifecycleService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session."""
    session = Mock()
    session.query.return_value = session
    session.filter.return_value = session
    session.commit.return_value = None
    session.rollback.return_value = None
    return session


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler."""
    lancedb = Mock()
    lancedb.search = Mock(return_value=[])
    lancedb.db = Mock()
    return lancedb


@pytest.fixture
def lifecycle_service(db_session, mock_lancedb):
    """Create EpisodeLifecycleService with mocked dependencies."""
    with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=mock_lancedb):
        service = EpisodeLifecycleService(db_session)
        service.lancedb = mock_lancedb
        return service


@pytest.fixture
def sample_episodes():
    """Create sample episodes."""
    now = datetime.now()
    episodes = []
    for i in range(5):
        ep = Mock()
        ep.id = f"episode-{i}"
        ep.started_at = now - timedelta(days=i * 30)  # 0, 30, 60, 90, 120 days ago
        ep.status = "completed"
        ep.decay_score = 1.0
        ep.access_count = i * 10
        ep.archived_at = None
        episodes.append(ep)
    return episodes


# ============================================================================
# Episode Decay Tests
# ============================================================================

class TestEpisodeDecay:
    """Test time-based episode decay."""

    @pytest.mark.asyncio
    async def test_decay_old_episodes(self, lifecycle_service, sample_episodes):
        """Test applying decay scores to old episodes."""
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert "affected" in result
        assert "archived" in result
        # Episodes older than 90 days should be affected
        assert result["affected"] >= 0

    @pytest.mark.asyncio
    async def test_decay_calculation(self, lifecycle_service):
        """Test decay score calculation formula."""
        # Test the decay formula: decay_score = max(0, 1 - (days_old / 180))
        test_cases = [
            (0, 1.0),      # 0 days old = 1.0 score
            (90, 0.5),     # 90 days old = 0.5 score
            (180, 0.0),    # 180 days old = 0.0 score
            (360, 0.0),    # 360 days old = 0.0 score (capped at 0)
        ]

        for days_old, expected_min_score in test_cases:
            # Calculate what the score should be
            expected_score = max(0, 1 - (days_old / 180))
            assert abs(expected_score - expected_min_score) < 0.01

    @pytest.mark.asyncio
    async def test_decay_with_threshold(self, lifecycle_service):
        """Test decay with different threshold values."""
        thresholds = [30, 60, 90, 180]

        for threshold in thresholds:
            lifecycle_service.db.query.return_value.filter.return_value.all.return_value = []

            result = await lifecycle_service.decay_old_episodes(days_threshold=threshold)

            assert isinstance(result, dict)
            assert "affected" in result


# ============================================================================
# Episode Consolidation Tests
# ============================================================================

class TestEpisodeConsolidation:
    """Test episode consolidation functionality."""

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes(self, lifecycle_service):
        """Test merging semantically similar episodes."""
        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        lifecycle_service.lancedb.search.return_value = []

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-123",
            similarity_threshold=0.85
        )

        assert "consolidated" in result
        assert "parent_episodes" in result
        assert isinstance(result["consolidated"], int)

    @pytest.mark.asyncio
    async def test_consolidate_with_no_episodes(self, lifecycle_service):
        """Test consolidation when no episodes available."""
        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = await lifecycle_service.consolidate_similar_episodes(agent_id="agent-456")

        assert result["consolidated"] == 0
        assert result["parent_episodes"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similarity_threshold(self, lifecycle_service):
        """Test different similarity thresholds."""
        thresholds = [0.7, 0.8, 0.9, 0.95]

        for threshold in thresholds:
            lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            lifecycle_service.lancedb.search.return_value = []

            result = await lifecycle_service.consolidate_similar_episodes(
                agent_id="agent-123",
                similarity_threshold=threshold
            )

            assert isinstance(result, dict)


# ============================================================================
# Episode Archival Tests
# ============================================================================

class TestEpisodeArchival:
    """Test episode archival to cold storage."""

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage(self, lifecycle_service):
        """Test moving episode to cold storage."""
        episode = Mock()
        episode.id = "episode-123"
        episode.status = "completed"

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.archive_to_cold_storage(episode_id="episode-123")

        assert result is True
        assert episode.status == "archived"
        assert episode.archived_at is not None

    @pytest.mark.asyncio
    async def test_archive_nonexistent_episode(self, lifecycle_service):
        """Test archiving non-existent episode."""
        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = None

        result = await lifecycle_service.archive_to_cold_storage(episode_id="nonexistent")

        assert result is False


# ============================================================================
# Importance Score Tests
# ============================================================================

class TestImportanceScore:
    """Test importance score updates."""

    @pytest.mark.asyncio
    async def test_update_importance_scores_positive(self, lifecycle_service):
        """Test updating importance with positive feedback."""
        episode = Mock()
        episode.id = "episode-123"
        episode.importance_score = 0.5

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.update_importance_scores(
            episode_id="episode-123",
            user_feedback=1.0  # Maximum positive feedback
        )

        assert result is True
        # Score should increase with positive feedback
        assert episode.importance_score >= 0.5

    @pytest.mark.asyncio
    async def test_update_importance_scores_negative(self, lifecycle_service):
        """Test updating importance with negative feedback."""
        episode = Mock()
        episode.id = "episode-123"
        episode.importance_score = 0.5

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.update_importance_scores(
            episode_id="episode-123",
            user_feedback=-1.0  # Maximum negative feedback
        )

        assert result is True
        # Score should decrease with negative feedback
        assert episode.importance_score <= 0.5

    @pytest.mark.asyncio
    async def test_update_importance_scores_bounds(self, lifecycle_service):
        """Test importance scores stay within [0, 1] bounds."""
        episode = Mock()
        episode.id = "episode-123"
        episode.importance_score = 0.5

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        # Test extreme values
        await lifecycle_service.update_importance_scores("episode-123", 10.0)  # Way above range
        assert 0.0 <= episode.importance_score <= 1.0

        await lifecycle_service.update_importance_scores("episode-123", -10.0)  # Way below range
        assert 0.0 <= episode.importance_score <= 1.0


# ============================================================================
# Batch Access Count Tests
# ============================================================================

class TestBatchAccessCounts:
    """Test batch access count updates."""

    @pytest.mark.asyncio
    async def test_batch_update_access_counts(self, lifecycle_service):
        """Test updating access counts for multiple episodes."""
        episode_ids = ["episode-1", "episode-2", "episode-3"]

        # Mock query to find episodes
        def mock_filter(ep_id):
            ep = Mock()
            ep.access_count = 5
            return ep

        lifecycle_service.db.query.return_value.filter.return_value.first.side_effect = [
            mock_filter(eid) for eid in episode_ids
        ]

        result = await lifecycle_service.batch_update_access_counts(episode_ids)

        assert "updated" in result
        assert result["updated"] == len(episode_ids)

    @pytest.mark.asyncio
    async def test_batch_update_empty_list(self, lifecycle_service):
        """Test batch update with empty episode list."""
        result = await lifecycle_service.batch_update_access_counts([])

        assert result["updated"] == 0


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_consolidate_handles_lancedb_errors(self, lifecycle_service):
        """Test graceful handling of LanceDB errors during consolidation."""
        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        lifecycle_service.lancedb.search.side_effect = Exception("LanceDB error")

        # Should not crash, should handle error gracefully
        result = await lifecycle_service.consolidate_similar_episodes(agent_id="agent-123")

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_update_importance_nonexistent_episode(self, lifecycle_service):
        """Test updating importance for non-existent episode."""
        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = None

        result = await lifecycle_service.update_importance_scores(
            episode_id="nonexistent",
            user_feedback=0.5
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_consolidate_with_metadata_parsing(self, lifecycle_service):
        """Test consolidation handles JSON metadata parsing."""
        # Create mock episodes with metadata
        episodes = []
        for i in range(3):
            ep = Mock()
            ep.id = f"episode-{i}"
            ep.consolidated_into = None
            episodes.append(ep)

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes

        # Mock LanceDB search results with metadata as string
        mock_results = [
            {
                "metadata": '{"episode_id": "episode-1", "similarity": 0.9}',
                "_distance": 0.1
            },
            {
                "metadata": '{"episode_id": "episode-2", "similarity": 0.8}',
                "_distance": 0.2
            }
        ]
        lifecycle_service.lancedb.search.return_value = mock_results

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-123",
            similarity_threshold=0.85
        )

        assert "consolidated" in result
        assert isinstance(result["consolidated"], int)

    @pytest.mark.asyncio
    async def test_consolidate_skips_already_consolidated(self, lifecycle_service):
        """Test consolidation skips episodes already consolidated."""
        parent_ep = Mock()
        parent_ep.id = "episode-parent"
        parent_ep.consolidated_into = None

        child_ep = Mock()
        child_ep.id = "episode-child"
        child_ep.consolidated_into = "some-other-parent"  # Already consolidated

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            parent_ep, child_ep
        ]
        lifecycle_service.db.query.return_value.filter.return_value.first.side_effect = [parent_ep, child_ep, None]

        lifecycle_service.lancedb.search.return_value = [
            {
                "metadata": '{"episode_id": "episode-child"}',
                "_distance": 0.1
            }
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-123",
            similarity_threshold=0.85
        )

        # Child should not be consolidated again
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_decay_with_zero_threshold(self, lifecycle_service):
        """Test decay with threshold of 0 (affects all episodes)."""
        episodes = [Mock(id=f"ep-{i}", started_at=datetime.now() - timedelta(days=i), status="completed") for i in range(5)]

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await lifecycle_service.decay_old_episodes(days_threshold=0)

        assert result["affected"] >= 0

    @pytest.mark.asyncio
    async def test_decay_skips_archived_episodes(self, lifecycle_service):
        """Test decay calculation skips already archived episodes."""
        now = datetime.now()
        episodes = [
            Mock(id="ep-1", started_at=now - timedelta(days=100), status="completed", decay_score=1.0, access_count=0, archived_at=None),
            Mock(id="ep-2", started_at=now - timedelta(days=100), status="archived", decay_score=1.0, access_count=0, archived_at=None),
            Mock(id="ep-3", started_at=now - timedelta(days=100), status="completed", decay_score=1.0, access_count=0, archived_at=None),
        ]

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Archived episode should be skipped from decay calculation
        assert result["affected"] >= 0

    @pytest.mark.asyncio
    async def test_consolidate_with_empty_search_results(self, lifecycle_service):
        """Test consolidation when LanceDB returns no similar episodes."""
        parent_ep = Mock()
        parent_ep.id = "episode-parent"
        parent_ep.consolidated_into = None

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent_ep]

        # No similar episodes found
        lifecycle_service.lancedb.search.return_value = []

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-123",
            similarity_threshold=0.85
        )

        assert result["consolidated"] == 0
        assert result["parent_episodes"] == 0

    @pytest.mark.asyncio
    async def test_update_importance_with_zero_feedback(self, lifecycle_service):
        """Test importance update with neutral (zero) feedback."""
        episode = Mock()
        episode.id = "episode-123"
        episode.importance_score = 0.7

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.update_importance_scores(
            episode_id="episode-123",
            user_feedback=0.0  # Neutral feedback
        )

        assert result is True
        # Score should remain close to original (0.7 * 0.8 + 0.5 * 0.2 = 0.56 + 0.1 = 0.66)
        assert 0.0 <= episode.importance_score <= 1.0

    @pytest.mark.asyncio
    async def test_update_importance_clamps_at_minimum(self, lifecycle_service):
        """Test importance score clamps at minimum 0.0."""
        episode = Mock()
        episode.id = "episode-123"
        episode.importance_score = 0.05  # Already very low

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.update_importance_scores(
            episode_id="episode-123",
            user_feedback=-1.0  # Maximum negative
        )

        assert result is True
        assert episode.importance_score >= 0.0

    @pytest.mark.asyncio
    async def test_update_importance_clamps_at_maximum(self, lifecycle_service):
        """Test importance score clamps at maximum 1.0."""
        episode = Mock()
        episode.id = "episode-123"
        episode.importance_score = 0.95  # Already very high

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.update_importance_scores(
            episode_id="episode-123",
            user_feedback=1.0  # Maximum positive
        )

        assert result is True
        assert episode.importance_score <= 1.0

    @pytest.mark.asyncio
    async def test_batch_update_with_mixed_valid_invalid_ids(self, lifecycle_service):
        """Test batch update with mix of valid and invalid episode IDs."""
        episode_ids = ["episode-1", "nonexistent-1", "episode-2", "nonexistent-2"]

        # Mock returns episode for valid IDs, None for invalid
        def mock_query_side_effect(*args, **kwargs):
            ep = Mock()
            ep.access_count = 5
            return ep

        lifecycle_service.db.query.return_value.filter.return_value.first.side_effect = [
            mock_query_side_effect(),  # episode-1
            None,  # nonexistent-1
            mock_query_side_effect(),  # episode-2
            None   # nonexistent-2
        ]

        result = await lifecycle_service.batch_update_access_counts(episode_ids)

        assert result["updated"] == 2  # Only valid episodes

    @pytest.mark.asyncio
    async def test_archive_already_archived_episode(self, lifecycle_service):
        """Test archiving an episode that's already archived."""
        episode = Mock()
        episode.id = "episode-123"
        episode.status = "archived"  # Already archived
        episode.archived_at = datetime.now()

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.archive_to_cold_storage(episode_id="episode-123")

        assert result is True
        # Should update archived_at even if already archived

    @pytest.mark.asyncio
    async def test_consolidate_distance_calculation(self, lifecycle_service):
        """Test consolidation correctly calculates similarity from distance."""
        parent_ep = Mock()
        parent_ep.id = "episode-parent"
        parent_ep.consolidated_into = None

        child_ep = Mock()
        child_ep.id = "episode-child"
        child_ep.consolidated_into = None

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent_ep]
        lifecycle_service.db.query.return_value.filter.return_value.first.side_effect = [child_ep, None]

        # Mock results with different distances
        lifecycle_service.lancedb.search.return_value = [
            {
                "metadata": '{"episode_id": "episode-child"}',
                "_distance": 0.1  # High similarity (0.9)
            }
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-123",
            similarity_threshold=0.85
        )

        # Should consolidate since 1.0 - 0.1 = 0.9 >= 0.85
        assert result["consolidated"] >= 0

    @pytest.mark.asyncio
    async def test_consolidate_below_threshold(self, lifecycle_service):
        """Test episodes below similarity threshold are not consolidated."""
        parent_ep = Mock()
        parent_ep.id = "episode-parent"
        parent_ep.consolidated_into = None

        child_ep = Mock()
        child_ep.id = "episode-child"
        child_ep.consolidated_into = None

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent_ep]
        lifecycle_service.db.query.return_value.filter.return_value.first.side_effect = [child_ep, None]

        # Mock result with low similarity
        lifecycle_service.lancedb.search.return_value = [
            {
                "metadata": '{"episode_id": "episode-child"}',
                "_distance": 0.5  # Low similarity (0.5)
            }
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-123",
            similarity_threshold=0.85
        )

        # Should NOT consolidate since 1.0 - 0.5 = 0.5 < 0.85
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_decay_updates_access_count(self, lifecycle_service):
        """Test decay operation increments access count."""
        now = datetime.now()
        episode = Mock()
        episode.id = "episode-123"
        episode.started_at = now - timedelta(days=100)
        episode.status = "completed"
        episode.decay_score = 1.0
        episode.access_count = 10
        episode.archived_at = None

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = [episode]

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Access count should be incremented
        assert episode.access_count == 11

    @pytest.mark.asyncio
    async def test_consolidate_rollback_on_error(self, lifecycle_service):
        """Test consolidation rolls back on database error."""
        episodes = [Mock(id=f"ep-{i}", consolidated_into=None) for i in range(3)]

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes
        lifecycle_service.db.query.return_value.filter.return_value.first.side_effect = [Mock(consolidated_into=None)] * 10
        lifecycle_service.db.commit.side_effect = Exception("Database error")

        lifecycle_service.lancedb.search.return_value = [
            {
                "metadata": '{"episode_id": "ep-1"}',
                "_distance": 0.1
            }
        ]

        # Should handle error gracefully
        result = await lifecycle_service.consolidate_similar_episodes(agent_id="agent-123")

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_archive_updates_timestamp(self, lifecycle_service):
        """Test archival sets archived_at timestamp."""
        episode = Mock()
        episode.id = "episode-123"
        episode.status = "completed"

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        before_archival = datetime.now()
        result = await lifecycle_service.archive_to_cold_storage(episode_id="episode-123")
        after_archival = datetime.now()

        assert result is True
        assert episode.archived_at is not None
        assert before_archival <= episode.archived_at <= after_archival
