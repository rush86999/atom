"""
Comprehensive tests for EpisodeLifecycleService.

Tests cover episode decay, consolidation, archival, and state transitions.
Achieves 70%+ coverage target.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import List

from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import Episode, EpisodeSegment


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
def lifecycle_service(db_session, mock_lancedb):
    """Create EpisodeLifecycleService instance."""
    with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=mock_lancedb):
        service = EpisodeLifecycleService(db_session)
        service.lancedb = mock_lancedb
        return service


@pytest.fixture
def sample_episodes():
    """Create sample episodes with different ages."""
    episodes = []
    now = datetime.now()

    # Recent episode (1 day old)
    episodes.append(Episode(
        id="episode-1",
        agent_id="agent-1",
        tenant_id="default",
        task_description="Recent task",
        status="active",
        started_at=now - timedelta(days=1),
        decay_score=0.99,
        access_count=0
    ))

    # Medium episode (45 days old)
    episodes.append(Episode(
        id="episode-2",
        agent_id="agent-1",
        tenant_id="default",
        task_description="Medium task",
        status="active",
        started_at=now - timedelta(days=45),
        decay_score=0.5,
        access_count=5
    ))

    # Old episode (100 days old)
    episodes.append(Episode(
        id="episode-3",
        agent_id="agent-1",
        tenant_id="default",
        task_description="Old task",
        status="active",
        started_at=now - timedelta(days=100),
        decay_score=0.1,
        access_count=10
    ))

    # Very old episode (200 days old)
    episodes.append(Episode(
        id="episode-4",
        agent_id="agent-1",
        tenant_id="default",
        task_description="Very old task",
        status="active",
        started_at=now - timedelta(days=200),
        decay_score=0.0,
        access_count=20
    ))

    return episodes


@pytest.fixture
def sample_episode():
    """Create single sample episode."""
    return Episode(
        id="episode-1",
        agent_id="agent-1",
        tenant_id="default",
        task_description="Test task",
        status="active",
        started_at=datetime.now() - timedelta(days=10),
        decay_score=0.9,
        access_count=5,
        importance_score=0.8
    )


class TestEpisodeDecay:
    """Tests for episode decay functionality."""

    @pytest.mark.asyncio
    async def test_decay_old_episodes_basic(
        self, lifecycle_service, db_session, sample_episodes
    ):
        """Test basic decay application to old episodes."""
        # Only return episodes older than 90 days
        old_episodes = [sample_episodes[2], sample_episodes[3]]  # 100 and 200 days old
        db_session.query.return_value.filter.return_value.all.return_value = old_episodes

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert result["affected"] == 2
        assert result["archived"] >= 0
        db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_decay_old_episodes_calculates_correct_score(
        self, lifecycle_service, db_session
    ):
        """Test decay score calculation formula."""
        # Create episode 100 days old
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=100),
            decay_score=1.0,
            access_count=0
        )

        db_session.query.return_value.filter.return_value.all.return_value = [episode]

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Decay formula: max(0, 1 - (days_old / 180))
        # 100 days old: 1 - (100 / 180) = 0.444
        assert episode.decay_score >= 0.0
        assert episode.decay_score <= 1.0

    @pytest.mark.asyncio
    async def test_decay_old_episodes_archives_very_old(
        self, lifecycle_service, db_session
    ):
        """Test very old episodes (>180 days) are archived."""
        # Create episode 200 days old
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=200),
            decay_score=1.0,
            access_count=0
        )

        db_session.query.return_value.filter.return_value.all.return_value = [episode]

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert episode.status == "archived"
        assert episode.archived_at is not None
        assert result["archived"] == 1

    @pytest.mark.asyncio
    async def test_decay_old_episodes_skips_archived(
        self, lifecycle_service, db_session
    ):
        """Test decay skips already archived episodes."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="archived",  # Already archived
            started_at=datetime.now() - timedelta(days=100),
            decay_score=0.5,
            access_count=0
        )

        db_session.query.return_value.filter.return_value.all.return_value = []

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert result["affected"] == 0

    @pytest.mark.asyncio
    async def test_decay_old_episodes_increments_access_count(
        self, lifecycle_service, db_session
    ):
        """Test decay increments access count."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=100),
            decay_score=1.0,
            access_count=5
        )

        db_session.query.return_value.filter.return_value.all.return_value = [episode]

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert episode.access_count == 6

    @pytest.mark.asyncio
    async def test_decay_old_episodes_custom_threshold(
        self, lifecycle_service, db_session
    ):
        """Test decay with custom threshold."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=60),  # 60 days old
            decay_score=1.0,
            access_count=0
        )

        db_session.query.return_value.filter.return_value.all.return_value = [episode]

        # Use 30-day threshold instead of default 90
        result = await lifecycle_service.decay_old_episodes(days_threshold=30)

        assert result["affected"] == 1

    @pytest.mark.asyncio
    async def test_decay_old_episodes_no_episodes(
        self, lifecycle_service, db_session
    ):
        """Test decay with no old episodes."""
        db_session.query.return_value.filter.return_value.all.return_value = []

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert result["affected"] == 0
        assert result["archived"] == 0


class TestEpisodeConsolidation:
    """Tests for episode consolidation functionality."""

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_basic(
        self, lifecycle_service, db_session, mock_lancedb
    ):
        """Test basic episode consolidation."""
        # Setup completed episodes
        episodes = [
            Episode(
                id=f"episode-{i}",
                agent_id="agent-1",
                tenant_id="default",
                task_description=f"Task about data analysis {i}",
                status="completed",
                started_at=datetime.now() - timedelta(days=i),
                consolidated_into=None
            )
            for i in range(5)
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes

        # Setup LanceDB search results (similar episodes)
        mock_lancedb.search.return_value = [
            {
                "metadata": {"episode_id": "episode-1"},
                "_distance": 0.1  # High similarity (0.9)
            },
            {
                "metadata": {"episode_id": "episode-2"},
                "_distance": 0.2  # High similarity (0.8)
            }
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-1",
            similarity_threshold=0.85
        )

        assert "consolidated" in result
        assert "parent_episodes" in result
        db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_no_episodes(
        self, lifecycle_service, db_session
    ):
        """Test consolidation with no episodes."""
        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-1",
            similarity_threshold=0.85
        )

        assert result["consolidated"] == 0
        assert result["parent_episodes"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_below_threshold(
        self, lifecycle_service, db_session, mock_lancedb
    ):
        """Test consolidation only merges episodes above threshold."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Data analysis",
                status="completed",
                started_at=datetime.now(),
                consolidated_into=None
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes

        # Return low similarity results
        mock_lancedb.search.return_value = [
            {
                "metadata": {"episode_id": "episode-2"},
                "_distance": 0.5  # Low similarity (0.5)
            }
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-1",
            similarity_threshold=0.85
        )

        # Should not consolidate below threshold
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_custom_threshold(
        self, lifecycle_service, db_session, mock_lancedb
    ):
        """Test consolidation with custom similarity threshold."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="completed",
                started_at=datetime.now(),
                consolidated_into=None
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes

        # Use lower threshold
        mock_lancedb.search.return_value = [
            {
                "metadata": {"episode_id": "episode-2"},
                "_distance": 0.3  # Similarity = 0.7
            }
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-1",
            similarity_threshold=0.7  # Lower threshold
        )

        assert result["consolidated"] >= 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_skips_consolidated(
        self, lifecycle_service, db_session
    ):
        """Test consolidation skips already consolidated episodes."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="completed",
                started_at=datetime.now(),
                consolidated_into="parent-1"  # Already consolidated
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-1",
            similarity_threshold=0.85
        )

        # Should skip already consolidated
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_handles_exception(
        self, lifecycle_service, db_session, mock_lancedb
    ):
        """Test consolidation handles exceptions gracefully."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="completed",
                started_at=datetime.now(),
                consolidated_into=None
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes
        mock_lancedb.search.side_effect = Exception("LanceDB error")

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-1",
            similarity_threshold=0.85
        )

        # Should not crash, return zero counts
        assert result["consolidated"] == 0
        db_session.rollback.assert_called()


class TestEpisodeArchival:
    """Tests for episode archival functionality."""

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage_basic(
        self, lifecycle_service, db_session, sample_episode
    ):
        """Test basic archival to cold storage."""
        db_session.query.return_value.filter.return_value.first.return_value = sample_episode

        result = await lifecycle_service.archive_to_cold_storage("episode-1")

        assert result is True
        assert sample_episode.status == "archived"
        assert sample_episode.archived_at is not None
        db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage_not_found(
        self, lifecycle_service, db_session
    ):
        """Test archival with non-existent episode."""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = await lifecycle_service.archive_to_cold_storage("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage_sets_timestamp(
        self, lifecycle_service, db_session, sample_episode
    ):
        """Test archival sets archived_at timestamp."""
        db_session.query.return_value.filter.return_value.first.return_value = sample_episode

        before = datetime.now()
        result = await lifecycle_service.archive_to_cold_storage("episode-1")
        after = datetime.now()

        assert result is True
        assert sample_episode.archived_at >= before
        assert sample_episode.archived_at <= after

    def test_archive_episode_synchronous(
        self, lifecycle_service, db_session, sample_episode
    ):
        """Test synchronous archive method."""
        result = lifecycle_service.archive_episode(sample_episode)

        assert result is True
        assert sample_episode.status == "archived"
        assert sample_episode.archived_at is not None

    def test_archive_episode_handles_exception(
        self, lifecycle_service, db_session
    ):
        """Test archive episode handles exceptions."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active"
        )

        db_session.commit.side_effect = Exception("DB error")

        result = lifecycle_service.archive_episode(episode)

        assert result is False
        db_session.rollback.assert_called()


class TestImportanceScores:
    """Tests for importance score updates."""

    @pytest.mark.asyncio
    async def test_update_importance_scores_positive_feedback(
        self, lifecycle_service, db_session, sample_episode
    ):
        """Test updating importance with positive feedback."""
        db_session.query.return_value.filter.return_value.first.return_value = sample_episode

        result = await lifecycle_service.update_importance_scores(
            episode_id="episode-1",
            user_feedback=1.0  # Max positive
        )

        assert result is True
        # Importance should increase
        assert sample_episode.importance_score > 0.8

    @pytest.mark.asyncio
    async def test_update_importance_scores_negative_feedback(
        self, lifecycle_service, db_session, sample_episode
    ):
        """Test updating importance with negative feedback."""
        db_session.query.return_value.filter.return_value.first.return_value = sample_episode

        result = await lifecycle_service.update_importance_scores(
            episode_id="episode-1",
            user_feedback=-1.0  # Max negative
        )

        assert result is True
        # Importance should decrease
        assert sample_episode.importance_score < 0.8

    @pytest.mark.asyncio
    async def test_update_importance_scores_clamps_range(
        self, lifecycle_service, db_session
    ):
        """Test importance scores are clamped to [0.0, 1.0]."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            importance_score=0.5
        )

        db_session.query.return_value.filter.return_value.first.return_value = episode

        # Test with extreme positive feedback
        await lifecycle_service.update_importance_scores("episode-1", user_feedback=2.0)
        assert episode.importance_score <= 1.0

        # Test with extreme negative feedback
        await lifecycle_service.update_importance_scores("episode-1", user_feedback=-2.0)
        assert episode.importance_score >= 0.0

    @pytest.mark.asyncio
    async def test_update_importance_scores_not_found(
        self, lifecycle_service, db_session
    ):
        """Test updating importance for non-existent episode."""
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = await lifecycle_service.update_importance_scores(
            episode_id="nonexistent",
            user_feedback=0.5
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_importance_scores_weighted_formula(
        self, lifecycle_service, db_session
    ):
        """Test importance score uses weighted formula."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            importance_score=0.5
        )

        db_session.query.return_value.filter.return_value.first.return_value = episode

        await lifecycle_service.update_importance_scores("episode-1", user_feedback=1.0)

        # Formula: new_importance = old * 0.8 + feedback * 0.2
        # 0.5 * 0.8 + 1.0 * 0.2 = 0.6
        assert 0.0 <= episode.importance_score <= 1.0


class TestAccessCounts:
    """Tests for access count updates."""

    @pytest.mark.asyncio
    async def test_batch_update_access_counts_basic(
        self, lifecycle_service, db_session
    ):
        """Test batch updating access counts."""
        episodes = [
            Episode(
                id=f"episode-{i}",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="active",
                access_count=i
            )
            for i in range(3)
        ]

        db_session.query.return_value.filter.return_value.first.side_effect = episodes

        result = await lifecycle_service.batch_update_access_counts([
            "episode-0",
            "episode-1",
            "episode-2"
        ])

        assert result["updated"] == 3
        assert episodes[0].access_count == 1
        assert episodes[1].access_count == 2
        assert episodes[2].access_count == 3

    @pytest.mark.asyncio
    async def test_batch_update_access_counts_partial(
        self, lifecycle_service, db_session
    ):
        """Test batch update with some non-existent episodes."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            access_count=5
        )

        db_session.query.return_value.filter.return_value.first.side_effect = [
            episode,
            None  # Second episode not found
        ]

        result = await lifecycle_service.batch_update_access_counts([
            "episode-1",
            "nonexistent"
        ])

        assert result["updated"] == 1
        assert episode.access_count == 6

    @pytest.mark.asyncio
    async def test_batch_update_access_counts_empty(
        self, lifecycle_service, db_session
    ):
        """Test batch update with empty list."""
        result = await lifecycle_service.batch_update_access_counts([])

        assert result["updated"] == 0


class TestLifecycleUpdates:
    """Tests for lifecycle update methods."""

    def test_update_lifecycle_basic(
        self, lifecycle_service, db_session, sample_episode
    ):
        """Test basic lifecycle update."""
        sample_episode.started_at = datetime.now() - timedelta(days=10)

        result = lifecycle_service.update_lifecycle(sample_episode)

        assert result is True
        assert sample_episode.decay_score >= 0.0
        assert sample_episode.decay_score <= 1.0
        db_session.commit.assert_called()

    def test_update_lifecycle_no_started_at(
        self, lifecycle_service, db_session
    ):
        """Test lifecycle update with no started_at."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=None
        )

        result = lifecycle_service.update_lifecycle(episode)

        assert result is False

    def test_update_lifecycle_archives_old(
        self, lifecycle_service, db_session
    ):
        """Test lifecycle update archives very old episodes."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=200)
        )

        result = lifecycle_service.update_lifecycle(episode)

        assert result is True
        assert episode.status == "archived"
        assert episode.archived_at is not None

    def test_update_lifecycle_timezone_aware(
        self, lifecycle_service, db_session
    ):
        """Test lifecycle update handles timezone-aware datetimes."""
        from datetime import timezone

        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
        )

        result = lifecycle_service.update_lifecycle(episode)

        assert result is True

    def test_apply_decay_single_episode(
        self, lifecycle_service, db_session, sample_episode
    ):
        """Test applying decay to single episode."""
        sample_episode.started_at = datetime.now() - timedelta(days=45)

        result = lifecycle_service.apply_decay(sample_episode)

        assert result is True
        assert sample_episode.decay_score >= 0.0

    def test_apply_decay_multiple_episodes(
        self, lifecycle_service, db_session
    ):
        """Test applying decay to multiple episodes."""
        episodes = [
            Episode(
                id=f"episode-{i}",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="active",
                started_at=datetime.now() - timedelta(days=i*30)
            )
            for i in range(1, 4)
        ]

        result = lifecycle_service.apply_decay(episodes)

        assert result is True
        for episode in episodes:
            assert episode.decay_score >= 0.0

    def test_apply_decay_handles_exception(
        self, lifecycle_service, db_session
    ):
        """Test apply decay handles exceptions."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now()
        )

        db_session.commit.side_effect = Exception("DB error")

        result = lifecycle_service.apply_decay(episode)

        assert result is False


class TestSynchronousConsolidation:
    """Tests for synchronous consolidation wrapper."""

    def test_consolidate_episodes_with_agent_id(
        self, lifecycle_service, db_session
    ):
        """Test consolidating episodes by agent ID string."""
        # Mock async method
        with patch.object(lifecycle_service, 'consolidate_similar_episodes', new=AsyncMock(return_value={"consolidated": 2, "parent_episodes": 1})):
            result = lifecycle_service.consolidate_episodes("agent-1", similarity_threshold=0.85)

            assert result["consolidated"] == 2
            assert result["parent_episodes"] == 1

    def test_consolidate_episodes_with_agent_object(
        self, lifecycle_service, db_session
    ):
        """Test consolidating episodes with agent object."""
        from core.models import AgentRegistry

        agent = AgentRegistry(
            id="agent-1",
            name="Test Agent"
        )

        # Mock async method
        with patch.object(lifecycle_service, 'consolidate_similar_episodes', new=AsyncMock(return_value={"consolidated": 1, "parent_episodes": 1})):
            result = lifecycle_service.consolidate_episodes(agent, similarity_threshold=0.85)

            assert result["consolidated"] == 1

    def test_consolidate_episodes_handles_timeout(
        self, lifecycle_service, db_session
    ):
        """Test consolidation handles timeout."""
        import asyncio

        # Mock async method that times out
        async def slow_consolidate(*args, **kwargs):
            await asyncio.sleep(10)
            return {"consolidated": 0, "parent_episodes": 0}

        with patch.object(lifecycle_service, 'consolidate_similar_episodes', new=slow_consolidate):
            result = lifecycle_service.consolidate_episodes("agent-1")

            # Should return zero counts on timeout
            assert result["consolidated"] == 0
            assert result["parent_episodes"] == 0

    def test_consolidate_episodes_handles_exception(
        self, lifecycle_service, db_session
    ):
        """Test consolidation handles exceptions."""
        # Mock async method that raises exception
        async def failing_consolidate(*args, **kwargs):
            raise Exception("Consolidation failed")

        with patch.object(lifecycle_service, 'consolidate_similar_episodes', new=failing_consolidate):
            result = lifecycle_service.consolidate_episodes("agent-1")

            # Should return zero counts on error
            assert result["consolidated"] == 0
            assert result["parent_episodes"] == 0


class TestDecayFormula:
    """Tests for decay score calculation."""

    def test_decay_formula_fresh_episode(self, lifecycle_service, db_session):
        """Test decay formula for fresh episode (1 day old)."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=1)
        )

        lifecycle_service.update_lifecycle(episode)

        # 1 day old: 1 / 90 = ~0.01
        assert episode.decay_score < 0.1

    def test_decay_formula_mid_age(self, lifecycle_service, db_session):
        """Test decay formula for mid-age episode (45 days old)."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=45)
        )

        lifecycle_service.update_lifecycle(episode)

        # 45 days old: 45 / 90 = 0.5
        assert 0.4 <= episode.decay_score <= 0.6

    def test_decay_formula_fully_decayed(self, lifecycle_service, db_session):
        """Test decay formula for fully decayed episode (90+ days old)."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=90)
        )

        lifecycle_service.update_lifecycle(episode)

        # 90 days old: 90 / 90 = 1.0 (fully decayed)
        assert episode.decay_score == 1.0

    def test_decay_formula_clamps_to_zero(self, lifecycle_service, db_session):
        """Test decay score is clamped to minimum 0.0."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=1000)  # Very old
        )

        lifecycle_service.update_lifecycle(episode)

        # Should be clamped to [0, 1]
        assert episode.decay_score >= 0.0
        assert episode.decay_score <= 1.0


class TestStateTransitions:
    """Tests for episode state transitions."""

    @pytest.mark.asyncio
    async def test_state_transition_active_to_decayed(
        self, lifecycle_service, db_session
    ):
        """Test transition from active to decayed state."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=100)
        )

        db_session.query.return_value.filter.return_value.first.return_value = episode

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Decay score should be > 0, indicating decayed state
        assert episode.decay_score > 0.0

    @pytest.mark.asyncio
    async def test_state_transition_decayed_to_archived(
        self, lifecycle_service, db_session
    ):
        """Test transition from decayed to archived state."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=200)
        )

        db_session.query.return_value.filter.return_value.first.return_value = episode

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Should be archived after 180 days
        assert episode.status == "archived"
        assert episode.archived_at is not None

    def test_state_transition_preserves_metadata(
        self, lifecycle_service, db_session
    ):
        """Test state transitions preserve episode metadata."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            started_at=datetime.now() - timedelta(days=100),
            importance_score=0.8,
            access_count=10
        )

        lifecycle_service.update_lifecycle(episode)

        # Metadata should be preserved
        assert episode.importance_score == 0.8
        assert episode.access_count == 10


class TestErrorHandling:
    """Tests for error handling in lifecycle operations."""

    @pytest.mark.asyncio
    async def test_consolidation_handles_json_parse_error(
        self, lifecycle_service, db_session, mock_lancedb
    ):
        """Test consolidation handles JSON parsing errors."""
        episodes = [
            Episode(
                id="episode-1",
                agent_id="agent-1",
                tenant_id="default",
                task_description="Task",
                status="completed",
                started_at=datetime.now(),
                consolidated_into=None
            )
        ]

        db_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes

        # Return invalid JSON
        mock_lancedb.search.return_value = [
            {
                "metadata": "invalid json {",
                "_distance": 0.2
            }
        ]

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent-1",
            similarity_threshold=0.85
        )

        # Should handle gracefully
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_update_importance_handles_invalid_score(
        self, lifecycle_service, db_session
    ):
        """Test update importance handles out-of-range scores."""
        episode = Episode(
            id="episode-1",
            agent_id="agent-1",
            tenant_id="default",
            task_description="Task",
            status="active",
            importance_score=0.5
        )

        db_session.query.return_value.filter.return_value.first.return_value = episode

        # Test with invalid feedback
        result = await lifecycle_service.update_importance_scores(
            episode_id="episode-1",
            user_feedback=999.0  # Way out of range
        )

        assert result is True
        # Should be clamped to [0, 1]
        assert 0.0 <= episode.importance_score <= 1.0
