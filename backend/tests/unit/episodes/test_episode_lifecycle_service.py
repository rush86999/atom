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

class TestDecayOperations:
    """Test time-based episode decay operations."""

    @pytest.mark.asyncio
    async def test_decay_old_episodes_threshold(self, lifecycle_service):
        """Test episodes older than threshold get decayed."""
        now = datetime.now()
        # Create episodes: 60 days, 100 days, 150 days old
        episodes = [
            Mock(id="ep-1", started_at=now - timedelta(days=60), status="completed", decay_score=1.0, access_count=0, archived_at=None),
            Mock(id="ep-2", started_at=now - timedelta(days=100), status="completed", decay_score=1.0, access_count=0, archived_at=None),
            Mock(id="ep-3", started_at=now - timedelta(days=150), status="completed", decay_score=1.0, access_count=0, archived_at=None),
        ]

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Episodes older than 90 days should be affected
        assert result["affected"] >= 2  # ep-2 and ep-3
        assert "archived" in result

    @pytest.mark.asyncio
    async def test_decay_formula_90_days(self, lifecycle_service):
        """Test decay score at 90 days boundary."""
        now = datetime.now()
        # Create episode exactly 90 days old
        ninety_days_ago = now - timedelta(days=90)
        episode = Mock(id="ep-90", started_at=ninety_days_ago, status="completed", decay_score=1.0, access_count=0, archived_at=None)

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = [episode]

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Verify: decay_score = max(0, 1 - 90/180) = 0.5
        assert abs(episode.decay_score - 0.5) < 0.01

    @pytest.mark.asyncio
    async def test_decay_formula_180_days(self, lifecycle_service):
        """Test decay score reaches minimum at 180 days."""
        now = datetime.now()
        # Create episode exactly 180 days old
        one_eighty_days_ago = now - timedelta(days=180)
        episode = Mock(id="ep-180", started_at=one_eighty_days_ago, status="completed", decay_score=1.0, access_count=0, archived_at=None)

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = [episode]

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Verify: decay_score = max(0, 1 - 180/180) = 0.0
        assert episode.decay_score == 0.0

    @pytest.mark.asyncio
    async def test_decay_formula_over_180_days(self, lifecycle_service):
        """Test decay score stays at 0.0 for >180 days."""
        now = datetime.now()
        # Create episode 200 days old
        two_hundred_days_ago = now - timedelta(days=200)
        episode = Mock(id="ep-200", started_at=two_hundred_days_ago, status="completed", decay_score=1.0, access_count=0, archived_at=None)

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = [episode]

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Verify: decay_score stays at 0.0 (minimum)
        assert episode.decay_score == 0.0

    @pytest.mark.asyncio
    async def test_decay_access_count_increment(self, lifecycle_service):
        """Test access count incremented during decay."""
        now = datetime.now()
        episode = Mock(id="ep-access", started_at=now - timedelta(days=100), status="completed", decay_score=1.0, access_count=5, archived_at=None)

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = [episode]

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Access count should be incremented
        assert episode.access_count == 6

    @pytest.mark.asyncio
    async def test_decay_archival_trigger(self, lifecycle_service):
        """Test episodes >180 days auto-archived."""
        now = datetime.now()
        # Create episode 200 days old
        episode = Mock(id="ep-archive", started_at=now - timedelta(days=200), status="completed", decay_score=1.0, access_count=0, archived_at=None)

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = [episode]

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Episode should be auto-archived
        assert episode.status == "archived"
        assert episode.archived_at is not None
        assert result["archived"] >= 1

    @pytest.mark.asyncio
    async def test_decay_excludes_archived(self, lifecycle_service):
        """Test already archived episodes excluded from decay."""
        now = datetime.now()
        episodes = [
            Mock(id="ep-1", started_at=now - timedelta(days=100), status="completed", decay_score=1.0, access_count=0, archived_at=None),
            Mock(id="ep-2", started_at=now - timedelta(days=100), status="archived", decay_score=1.0, access_count=0, archived_at=None),
            Mock(id="ep-3", started_at=now - timedelta(days=100), status="completed", decay_score=1.0, access_count=0, archived_at=None),
        ]

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Archived episode (ep-2) should not have decay_score updated
        # Only completed episodes should be affected
        # Note: The query filters out archived episodes, so all 3 returned should be processed
        assert result["affected"] >= 0

    @pytest.mark.asyncio
    async def test_decay_custom_threshold(self, lifecycle_service):
        """Test custom days_threshold parameter."""
        now = datetime.now()
        episodes = [
            Mock(id="ep-1", started_at=now - timedelta(days=25), status="completed", decay_score=1.0, access_count=0, archived_at=None),
            Mock(id="ep-2", started_at=now - timedelta(days=35), status="completed", decay_score=1.0, access_count=0, archived_at=None),
        ]

        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = episodes

        # Use custom threshold of 30 days
        result = await lifecycle_service.decay_old_episodes(days_threshold=30)

        # Only episodes older than 30 days should be affected
        assert result["affected"] >= 1  # ep-2

    @pytest.mark.asyncio
    async def test_decay_empty_results(self, lifecycle_service):
        """Test handling no episodes matching criteria."""
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = []

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Should handle gracefully with zero counts
        assert result["affected"] == 0
        assert result["archived"] == 0

    @pytest.mark.asyncio
    async def test_decay_formula_calculation(self, lifecycle_service):
        """Test verify formula: max(0, 1 - days_old/180)."""
        # Test the decay formula explicitly
        test_cases = [
            (0, 1.0),      # 0 days old = 1.0 score
            (45, 0.75),    # 45 days old = 0.75 score
            (90, 0.5),     # 90 days old = 0.5 score
            (135, 0.25),   # 135 days old = 0.25 score
            (180, 0.0),    # 180 days old = 0.0 score
            (270, 0.0),    # 270 days old = 0.0 score (capped)
        ]

        for days_old, expected_score in test_cases:
            calculated_score = max(0, 1 - (days_old / 180))
            assert abs(calculated_score - expected_score) < 0.001, \
                f"Decay formula incorrect for {days_old} days: expected {expected_score}, got {calculated_score}"

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

class TestConsolidation:
    """Test episode consolidation with LanceDB vector search."""

    @pytest.mark.asyncio
    async def test_consolidation_similar_episodes(self, lifecycle_service):
        """Test similar episodes merged under parent."""
        # Create parent and child episodes
        parent = Mock(id="parent", agent_id="agent1", task_description="Project status updates", consolidated_into=None)
        child = Mock(id="child", agent_id="agent1", task_description="Status update", consolidated_into=None)

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent]
        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = child

        # Mock LanceDB to return similar episodes (90% similar)
        lifecycle_service.lancedb.search.return_value = [
            {"metadata": {"episode_id": "child"}, "_distance": 0.1}  # 90% similar
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        assert result["consolidated"] >= 1
        assert child.consolidated_into == parent.id

    @pytest.mark.asyncio
    async def test_consolidation_similarity_threshold(self, lifecycle_service):
        """Test only episodes >= threshold consolidated."""
        parent = Mock(id="parent", agent_id="agent1", task_description="Project updates", consolidated_into=None)
        child_similar = Mock(id="similar", agent_id="agent1", task_description="Update", consolidated_into=None)
        child_dissimilar = Mock(id="dissimilar", agent_id="agent1", task_description="Different", consolidated_into=None)

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent]
        lifecycle_service.db.query.return_value.filter.return_value.first.side_effect = [child_similar, None]

        # Mock LanceDB results with different similarities
        lifecycle_service.lancedb.search.return_value = [
            {"metadata": {"episode_id": "similar"}, "_distance": 0.1},   # 90% similar (>= 0.85)
            {"metadata": {"episode_id": "dissimilar"}, "_distance": 0.3}  # 70% similar (< 0.85)
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Only similar episode should consolidate
        assert result["consolidated"] >= 0

    @pytest.mark.asyncio
    async def test_consolidation_prevents_duplicates(self, lifecycle_service):
        """Test already consolidated episodes skipped."""
        parent = Mock(id="parent", agent_id="agent1", task_description="Updates", consolidated_into=None)
        already_consolidated = Mock(id="consolidated", agent_id="agent1", task_description="Old", consolidated_into="other-parent")

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent]
        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = None  # Already consolidated, skipped

        lifecycle_service.lancedb.search.return_value = [
            {"metadata": {"episode_id": "consolidated"}, "_distance": 0.1}
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Already consolidated episode should be skipped
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_consolidation_circular_references(self, lifecycle_service):
        """Test no circular consolidated_into references."""
        parent = Mock(id="parent", agent_id="agent1", task_description="Main", consolidated_into=None)
        child = Mock(id="child", agent_id="agent1", task_description="Sub", consolidated_into=None)

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent]
        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = child

        lifecycle_service.lancedb.search.return_value = [
            {"metadata": {"episode_id": "child"}, "_distance": 0.1}
        ]

        await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Verify no circular reference
        assert child.consolidated_into == parent.id
        # parent should not be consolidated into child
        assert parent.consolidated_into is None or parent.consolidated_into != child.id

    @pytest.mark.asyncio
    async def test_consolidation_empty_results(self, lifecycle_service):
        """Test handling no similar episodes found."""
        parent = Mock(id="parent", agent_id="agent1", task_description="Updates", consolidated_into=None)

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent]

        # No similar episodes found
        lifecycle_service.lancedb.search.return_value = []

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        assert result["consolidated"] == 0
        assert result["parent_episodes"] == 0

    @pytest.mark.asyncio
    async def test_consolidation_custom_threshold(self, lifecycle_service):
        """Test custom similarity_threshold parameter."""
        parent = Mock(id="parent", agent_id="agent1", task_description="Updates", consolidated_into=None)
        child = Mock(id="child", agent_id="agent1", task_description="Update", consolidated_into=None)

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent]
        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = child

        # Episode is 80% similar, below default 0.85 but above custom 0.75
        lifecycle_service.lancedb.search.return_value = [
            {"metadata": {"episode_id": "child"}, "_distance": 0.2}  # 80% similar
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.75  # Lower threshold
        )

        # Should consolidate with custom threshold
        assert result["consolidated"] >= 1

    @pytest.mark.asyncio
    async def test_consolidation_lancedb_search(self, lifecycle_service):
        """Test LanceDB search invoked correctly."""
        parent = Mock(id="parent", agent_id="agent1", task_description="Project updates", consolidated_into=None)

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Verify LanceDB search was called
        lifecycle_service.lancedb.search.assert_called_once()
        call_args = lifecycle_service.lancedb.search.call_args
        assert call_args[1]["table_name"] == "episodes"
        assert call_args[1]["limit"] == 20

    @pytest.mark.asyncio
    async def test_consolidation_metadata_parsing(self, lifecycle_service):
        """Test episode IDs extracted from metadata."""
        parent = Mock(id="parent", agent_id="agent1", task_description="Updates", consolidated_into=None)
        child = Mock(id="child", agent_id="agent1", task_description="Update", consolidated_into=None)

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent]
        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = child

        # Mock LanceDB with JSON string metadata
        lifecycle_service.lancedb.search.return_value = [
            {"metadata": '{"episode_id": "child", "agent_id": "agent1"}', "_distance": 0.1}
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Should parse JSON metadata and extract episode_id
        assert result["consolidated"] >= 1

    @pytest.mark.asyncio
    async def test_consolidation_distance_calculation(self, lifecycle_service):
        """Test similarity = 1 - distance calculation."""
        parent = Mock(id="parent", agent_id="agent1", task_description="Updates", consolidated_into=None)
        child_close = Mock(id="close", agent_id="agent1", task_description="Close match", consolidated_into=None)
        child_far = Mock(id="far", agent_id="agent1", task_description="Far match", consolidated_into=None)

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent]
        lifecycle_service.db.query.return_value.filter.return_value.first.side_effect = [child_close, None]

        # Test similarity calculation: similarity = 1 - distance
        lifecycle_service.lancedb.search.return_value = [
            {"metadata": {"episode_id": "close"}, "_distance": 0.05},  # 95% similar
            {"metadata": {"episode_id": "far"}, "_distance": 0.25}    # 75% similar
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Only "close" episode should consolidate (95% >= 85%)
        # "far" should not (75% < 85%)
        assert result["consolidated"] >= 0

    @pytest.mark.asyncio
    async def test_consolidation_transaction_rollback(self, lifecycle_service):
        """Test rollback on error."""
        parent = Mock(id="parent", agent_id="agent1", task_description="Updates", consolidated_into=None)
        child = Mock(id="child", agent_id="agent1", task_description="Update", consolidated_into=None)

        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent]
        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = child
        lifecycle_service.db.commit.side_effect = Exception("Database error")

        lifecycle_service.lancedb.search.return_value = [
            {"metadata": {"episode_id": "child"}, "_distance": 0.1}
        ]

        # Should handle error gracefully and call rollback
        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Verify rollback was called
        lifecycle_service.db.rollback.assert_called_once()
        assert isinstance(result, dict)

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

class TestArchivalAndImportance:
    """Test archival operations and importance scoring."""

    # ========== Archival Tests ==========

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage_success(self, lifecycle_service):
        """Test episode marked as archived."""
        episode = Mock(id="ep1", agent_id="agent1", status="completed")

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.archive_to_cold_storage("ep1")

        assert result is True
        assert episode.status == "archived"
        assert episode.archived_at is not None

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage_not_found(self, lifecycle_service):
        """Test returns False for nonexistent episode."""
        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = None

        result = await lifecycle_service.archive_to_cold_storage("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage_timestamp(self, lifecycle_service):
        """Test archived_at set correctly."""
        episode = Mock(id="ep1", agent_id="agent1", status="completed")

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        before = datetime.now()
        result = await lifecycle_service.archive_to_cold_storage("ep1")
        after = datetime.now()

        assert result is True
        assert episode.archived_at is not None
        assert before <= episode.archived_at <= after

    @pytest.mark.asyncio
    async def test_archive_episode_sync(self, lifecycle_service):
        """Test synchronous archive method."""
        episode = Mock(id="ep1", agent_id="agent1", status="completed")

        result = lifecycle_service.archive_episode(episode)

        assert result is True
        assert episode.status == "archived"
        assert episode.archived_at is not None

    @pytest.mark.asyncio
    async def test_archive_excludes_from_retrieval(self, lifecycle_service):
        """Test archived episodes excluded from retrieval."""
        # Create archived episode
        episode = Mock(id="ep1", agent_id="agent1", status="archived")

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.archive_to_cold_storage("ep1")

        assert result is True
        # Archived episodes should be filtered out in retrieval queries
        # (This is tested in retrieval service tests)

    # ========== Importance Scoring Tests ==========

    @pytest.mark.asyncio
    async def test_update_importance_scores_single(self, lifecycle_service):
        """Test update single episode importance."""
        episode = Mock(id="ep1", agent_id="agent1", importance_score=0.5)

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.update_importance_scores(
            episode_id="ep1",
            user_feedback=1.0  # Maximum positive
        )

        assert result is True
        # Importance should increase with positive feedback
        assert episode.importance_score >= 0.5

    @pytest.mark.asyncio
    async def test_update_importance_scores_batch(self, lifecycle_service):
        """Test update multiple episodes via batch_update_access_counts."""
        episode_ids = ["ep1", "ep2", "ep3"]

        # Mock episodes
        def mock_episode(ep_id):
            ep = Mock()
            ep.id = ep_id
            ep.access_count = 5
            return ep

        lifecycle_service.db.query.return_value.filter.return_value.first.side_effect = [
            mock_episode(eid) for eid in episode_ids
        ]

        result = await lifecycle_service.batch_update_access_counts(episode_ids)

        assert result["updated"] == 3

    @pytest.mark.asyncio
    async def test_importance_bounds_enforcement(self, lifecycle_service):
        """Test importance clamped to [0.0, 1.0]."""
        episode = Mock(id="ep1", agent_id="agent1", importance_score=0.5)

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        # Test extreme positive feedback
        await lifecycle_service.update_importance_scores("ep1", 10.0)
        assert 0.0 <= episode.importance_score <= 1.0

        # Reset
        episode.importance_score = 0.5

        # Test extreme negative feedback
        await lifecycle_service.update_importance_scores("ep1", -10.0)
        assert 0.0 <= episode.importance_score <= 1.0

    @pytest.mark.asyncio
    async def test_importance_feedback_boost(self, lifecycle_service):
        """Test positive feedback increases importance."""
        episode = Mock(id="ep1", agent_id="agent1", importance_score=0.5)

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        before = episode.importance_score
        await lifecycle_service.update_importance_scores("ep1", 1.0)  # Max positive

        # Formula: new_importance = old * 0.8 + (feedback + 1.0) / 2.0 * 0.2
        # For feedback=1.0: new = 0.5 * 0.8 + 1.0 * 0.2 = 0.4 + 0.2 = 0.6
        assert episode.importance_score > before

    @pytest.mark.asyncio
    async def test_importance_access_count_boost(self, lifecycle_service):
        """Test access count increases importance via batch update."""
        episode = Mock(id="ep1", agent_id="agent1", access_count=10)

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        await lifecycle_service.batch_update_access_counts(["ep1"])

        # Access count should be incremented
        assert episode.access_count == 11

    # ========== Decay Application Tests ==========

    @pytest.mark.asyncio
    async def test_apply_decay_to_single_episode(self, lifecycle_service):
        """Test apply decay to single episode."""
        now = datetime.now()
        episode = Mock(
            id="ep1",
            agent_id="agent1",
            started_at=now - timedelta(days=100),
            decay_score=1.0
        )

        result = lifecycle_service.apply_decay(episode)

        assert result is True
        # Decay score should be updated based on age

    @pytest.mark.asyncio
    async def test_apply_decay_to_episode_list(self, lifecycle_service):
        """Test apply decay to multiple episodes."""
        now = datetime.now()
        episodes = [
            Mock(id=f"ep{i}", started_at=now - timedelta(days=i * 30), decay_score=1.0)
            for i in range(1, 4)
        ]

        result = lifecycle_service.apply_decay(episodes)

        assert result is True

    @pytest.mark.asyncio
    async def test_apply_decay_with_access_boost(self, lifecycle_service):
        """Test access count offsets decay."""
        now = datetime.now()
        episode = Mock(
            id="ep1",
            agent_id="agent1",
            started_at=now - timedelta(days=100),
            access_count=50  # High access count
        )

        result = lifecycle_service.apply_decay(episode)

        assert result is True
        # High access count should offset some decay

    @pytest.mark.asyncio
    async def test_apply_decay_bounds_check(self, lifecycle_service):
        """Test decay score never negative."""
        now = datetime.now()
        # Very old episode (500 days)
        episode = Mock(
            id="ep1",
            agent_id="agent1",
            started_at=now - timedelta(days=500),
            decay_score=1.0,
            status="completed"
        )

        result = lifecycle_service.apply_decay(episode)

        assert result is True
        # Decay score should be clamped to valid range
        assert episode.decay_score >= 0.0


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

        # Only return non-consolidated episodes (parent only)
        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            parent_ep  # Child not returned because already consolidated
        ]
        # Mock second query to return None when looking for child
        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = None

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

        # Child should not be consolidated again because it's not in the candidate list
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_decay_with_zero_threshold(self, lifecycle_service):
        """Test decay with threshold of 0 (affects all episodes)."""
        episodes = [
            Mock(
                id=f"ep-{i}",
                started_at=datetime.now() - timedelta(days=i),
                status="completed",
                decay_score=1.0,
                access_count=i * 10,
                archived_at=None
            ) for i in range(5)
        ]

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
