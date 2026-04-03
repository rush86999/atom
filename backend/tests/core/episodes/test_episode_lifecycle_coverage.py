"""
Coverage-driven tests for EpisodeLifecycleService (currently 0% -> target 80%+)

Focus areas from episode_lifecycle_service.py:
- EpisodeLifecycleService initialization
- decay_old_episodes() - mark old episodes with decay scores
- consolidate_similar_episodes() - merge related episodes
- archive_to_cold_storage() - PostgreSQL to LanceDB migration
- update_importance_scores() - feedback-based importance
- batch_update_access_counts() - batch access tracking
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from core.episode_lifecycle_service import EpisodeLifecycleService


class TestEpisodeLifecycleInit:
    """Test EpisodeLifecycleService initialization."""

    def test_init_with_db(self, db_session):
        """Cover service initialization with database session."""
        service = EpisodeLifecycleService(db_session)

        assert service.db is db_session
        assert service.lancedb is not None


class TestEpisodeDecay:
    """Test episode decay and lifecycle updates."""

    @pytest.mark.asyncio
    async def test_decay_old_episodes(self, db_session):
        """Cover decay_old_episodes method (lines 29-69)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        # Create old episode
        old_episode = Episode(
            id="old-ep1",
            agent_id="agent1",
            task_description="Old task",
            status="completed",
            started_at=datetime.now() - timedelta(days=100),
            decay_score=1.0,
            outcome="success"
        )
        db_session.add(old_episode)
        db_session.commit()

        result = await service.decay_old_episodes(days_threshold=90)

        # Should apply decay and archive
        assert result["affected"] >= 1

    @pytest.mark.asyncio
    async def test_decay_old_episodes_no_episodes(self, db_session):
        """Cover decay_old_episodes with no old episodes."""
        from core.episode_lifecycle_service import EpisodeLifecycleService

        service = EpisodeLifecycleService(db_session)

        result = await service.decay_old_episodes(days_threshold=90)

        # Should return zero affected
        assert result["affected"] == 0
        assert result["archived"] == 0

    def test_update_lifecycle(self, db_session):
        """Cover update_lifecycle method (lines 279-330)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        # Create episode
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            task_description="Test task",
            status="completed",
            started_at=datetime.now() - timedelta(days=30),
            decay_score=0.0,
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        result = service.update_lifecycle(episode)

        # Should update decay score
        assert result is True
        assert episode.decay_score > 0

    def test_update_lifecycle_no_started_at(self, db_session):
        """Cover update_lifecycle with None started_at (lines 293-295)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        episode = Episode(
            id="ep2",
            agent_id="agent1",
            task_description="Test task",
            status="completed",
            started_at=None,
            decay_score=0.0,
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        result = service.update_lifecycle(episode)

        # Should return False for episode without started_at
        assert result is False

    def test_apply_decay_single_episode(self, db_session):
        """Cover apply_decay with single episode (lines 332-353)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        episode = Episode(
            id="ep3",
            agent_id="agent1",
            task_description="Test task",
            status="completed",
            started_at=datetime.now() - timedelta(days=30),
            decay_score=0.0,
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        result = service.apply_decay(episode)

        # Should apply decay
        assert result is True

    def test_apply_decay_list_of_episodes(self, db_session):
        """Cover apply_decay with list of episodes (lines 344-350)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        episodes = []
        for i in range(3):
            episode = Episode(
                id=f"ep-{i}",
                agent_id="agent1",
                task_description=f"Task {i}",
                status="completed",
                started_at=datetime.now() - timedelta(days=30 * (i + 1)),
                decay_score=0.0
            )
            db_session.add(episode)
            episodes.append(episode)
        db_session.commit()

        result = service.apply_decay(episodes)

        # Should apply decay to all
        assert result is True


class TestEpisodeConsolidation:
    """Test episode consolidation methods."""

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes(self, db_session):
        """Cover consolidate_similar_episodes method (lines 71-163)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        # Create completed episodes
        for i in range(3):
            episode = Episode(
                id=f"ep-{i}",
                agent_id="agent1",
                task_description=f"Similar task {i}",
                status="completed",
                started_at=datetime.now() - timedelta(days=i),
                consolidated_into=None
            )
            db_session.add(episode)
        db_session.commit()

        # Mock LanceDB search to return similar episodes
        with patch.object(service.lancedb, 'search', return_value=[
            {"metadata": '{"episode_id": "ep-1"}', "_distance": 0.1},
            {"metadata": '{"episode_id": "ep-2"}', "_distance": 0.15},
        ]):
            result = await service.consolidate_similar_episodes(
                agent_id="agent1",
                similarity_threshold=0.85
            )

            # Should attempt consolidation
            assert "consolidated" in result
            assert "parent_episodes" in result

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_no_episodes(self, db_session):
        """Cover consolidate_similar_episodes with no episodes."""
        from core.episode_lifecycle_service import EpisodeLifecycleService

        service = EpisodeLifecycleService(db_session)

        result = await service.consolidate_similar_episodes("agent1")

        # Should return zero consolidated
        assert result["consolidated"] == 0
        assert result["parent_episodes"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_lancedb_error(self, db_session):
        """Cover consolidate_similar_episodes with LanceDB error (lines 159-162)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        # Create episode
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            task_description="Test task",
            status="completed",
            started_at=datetime.now(),
            consolidated_into=None,
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        # Mock LanceDB to raise error
        with patch.object(service.lancedb, 'search', side_effect=Exception("LanceDB error")):
            result = await service.consolidate_similar_episodes("agent1")

            # Should handle error gracefully
            assert result["consolidated"] == 0

    def test_consolidate_episodes_wrapper(self, db_session):
        """Cover consolidate_episodes sync wrapper (lines 355-421)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        # Create episode
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            task_description="Test task",
            status="completed",
            started_at=datetime.now(),
            consolidated_into=None,
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        # Mock async method
        with patch.object(service, 'consolidate_similar_episodes', return_value={"consolidated": 0, "parent_episodes": 0}):
            result = service.consolidate_episodes("agent1")

            # Should return result from async method
            assert "consolidated" in result


class TestEpisodeArchival:
    """Test episode archival to LanceDB."""

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage(self, db_session):
        """Cover archive_to_cold_storage method (lines 165-191)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        # Create episode
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            task_description="Test task",
            status="completed",
            started_at=datetime.now(),
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        result = await service.archive_to_cold_storage("ep1")

        # Should mark as archived
        assert result is True
        assert episode.status == "archived"

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage_nonexistent(self, db_session):
        """Cover archive_to_cold_storage with nonexistent episode (lines 178-183)."""
        from core.episode_lifecycle_service import EpisodeLifecycleService

        service = EpisodeLifecycleService(db_session)

        result = await service.archive_to_cold_storage("nonexistent")

        # Should return False
        assert result is False

    def test_archive_episode_sync(self, db_session):
        """Cover archive_episode synchronous method (lines 193-217)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        episode = Episode(
            id="ep1",
            agent_id="agent1",
            task_description="Test task",
            status="completed",
            started_at=datetime.now(),
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        result = service.archive_episode(episode)

        # Should mark as archived
        assert result is True
        assert episode.status == "archived"
        assert episode.archived_at is not None


class TestImportanceScores:
    """Test importance score updates."""

    @pytest.mark.asyncio
    async def test_update_importance_scores(self, db_session):
        """Cover update_importance_scores method (lines 219-248)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        # Create episode
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            task_description="Test task",
            status="completed",
            started_at=datetime.now(),
            importance_score=0.5,
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        result = await service.update_importance_scores(
            episode_id="ep1",
            user_feedback=1.0  # Positive feedback
        )

        # Should update importance
        assert result is True
        assert episode.importance_score > 0.5

    @pytest.mark.asyncio
    async def test_update_importance_scores_nonexistent(self, db_session):
        """Cover update_importance_scores with nonexistent episode (lines 234-239)."""
        from core.episode_lifecycle_service import EpisodeLifecycleService

        service = EpisodeLifecycleService(db_session)

        result = await service.update_importance_scores(
            episode_id="nonexistent",
            user_feedback=1.0
        )

        # Should return False
        assert result is False

    @pytest.mark.asyncio
    async def test_update_importance_scores_negative_feedback(self, db_session):
        """Cover update_importance_scores with negative feedback (lines 242-243)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        episode = Episode(
            id="ep1",
            agent_id="agent1",
            task_description="Test task",
            status="completed",
            started_at=datetime.now(),
            importance_score=0.5,
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        result = await service.update_importance_scores(
            episode_id="ep1",
            user_feedback=-1.0  # Negative feedback
        )

        # Should decrease importance
        assert result is True
        assert episode.importance_score < 0.5


class TestAccessCountUpdates:
    """Test access count batch updates."""

    @pytest.mark.asyncio
    async def test_batch_update_access_counts(self, db_session):
        """Cover batch_update_access_counts method (lines 250-277)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        # Create episodes
        for i in range(3):
            episode = Episode(
                id=f"ep-{i}",
                agent_id="agent1",
                task_description=f"Task {i}",
                status="completed",
                started_at=datetime.now(),
                access_count=0
            )
            db_session.add(episode)
        db_session.commit()

        result = await service.batch_update_access_counts([f"ep-{i}" for i in range(3)])

        # Should update all episodes
        assert result["updated"] == 3

    @pytest.mark.asyncio
    async def test_batch_update_access_counts_empty(self, db_session):
        """Cover batch_update_access_counts with empty list."""
        from core.episode_lifecycle_service import EpisodeLifecycleService

        service = EpisodeLifecycleService(db_session)

        result = await service.batch_update_access_counts([])

        # Should return zero updated
        assert result["updated"] == 0

    @pytest.mark.asyncio
    async def test_batch_update_access_counts_mixed(self, db_session):
        """Cover batch_update_access_counts with mix of existent and non-existent."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        # Create only one episode
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            task_description="Task",
            status="completed",
            started_at=datetime.now(),
            access_count=0,
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        result = await service.batch_update_access_counts(["ep1", "nonexistent"])

        # Should update only existing episode
        assert result["updated"] == 1


class TestArchiveEligibleEpisodes:
    """Test archival of eligible old episodes."""

    def test_archive_episode_by_age_old(self, db_session):
        """Cover archive_episode for old episode (>180 days)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        episode = Episode(
            id="old-ep",
            agent_id="agent1",
            task_description="Old task",
            status="completed",
            started_at=datetime.now() - timedelta(days=200),
            decay_score=1.0,
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        # Apply decay should archive very old episodes
        service.update_lifecycle(episode)

        # Should be archived
        assert episode.status == "archived"
        assert episode.archived_at is not None

    def test_archive_episode_by_age_recent(self, db_session):
        """Cover archive_episode for recent episode (<180 days)."""
        from core.models import Episode

        service = EpisodeLifecycleService(db_session)

        episode = Episode(
            id="recent-ep",
            agent_id="agent1",
            task_description="Recent task",
            status="completed",
            started_at=datetime.now() - timedelta(days=30),
            decay_score=0.3,
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        # Apply decay should not archive recent episodes
        service.update_lifecycle(episode)

        # Should NOT be archived
        assert episode.status == "completed"
        assert episode.archived_at is None
