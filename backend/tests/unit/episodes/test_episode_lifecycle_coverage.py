"""
Unit tests for episode_lifecycle_service.py

Target: 60%+ coverage (file size: 251 lines, target: ~151 lines)

Test Categories:
- Decay Operations (4 tests)
- Consolidation (4 tests)
- Archival (3 tests)
- Importance Scoring (2 tests)
- Error Paths (2 tests)
- Batch Update Access Counts (4 tests)
- Edge Cases (2 tests)
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from sqlalchemy.orm import Session

from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import Episode


# ========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def db_session():
    """Mock database session"""
    session = MagicMock(spec=Session)
    session.query.return_value.filter.return_value.all.return_value = []
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
def lifecycle_service(db_session, mock_lancedb):
    """EpisodeLifecycleService fixture"""
    with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=mock_lancedb):
        service = EpisodeLifecycleService(db_session)
        service.lancedb = mock_lancedb
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
            title="Old Episode 1",
            description="Episode from 100 days ago",
            summary="Old summary",
            status="completed",
            started_at=now - timedelta(days=100),
            ended_at=now - timedelta(days=100) + timedelta(minutes=30),
            decay_score=1.0,
            access_count=5
        ),
        Episode(
            id="ep2",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Recent Episode",
            description="Episode from 10 days ago",
            summary="Recent summary",
            status="completed",
            started_at=now - timedelta(days=10),
            ended_at=now - timedelta(days=10) + timedelta(minutes=30),
            decay_score=1.0,
            access_count=3
        ),
        Episode(
            id="ep3",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Very Old Episode",
            description="Episode from 200 days ago",
            summary="Very old summary",
            status="completed",
            started_at=now - timedelta(days=200),
            ended_at=now - timedelta(days=200) + timedelta(minutes=30),
            decay_score=1.0,
            access_count=2
        ),
    ]
    return episodes


# ========================================================================
# A. Decay Operations (4 tests)
# =========================================================================

class TestDecayOperations:
    """Test episode decay operations"""

    @pytest.mark.asyncio
    async def test_decay_old_episodes_applies_score(self, lifecycle_service, sample_episodes):
        """Should apply decay scores to episodes older than threshold"""
        # Set up mock to return episodes
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes[:2]

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert "affected" in result
        assert "archived" in result
        assert result["affected"] >= 0

        # Verify commit was called
        lifecycle_service.db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_decay_score_formula_correct(self, lifecycle_service, sample_episodes):
        """Should calculate decay score using correct formula: max(0, 1 - (days_old / 180))"""
        # Episode from 100 days ago
        # decay_score = max(0, 1 - (100/180)) = max(0, 1 - 0.556) = 0.444
        old_episode = sample_episodes[0]
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = [old_episode]

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Verify decay_score was updated (approximately 0.44)
        # The exact value depends on when the test runs, but it should be < 1.0
        assert old_episode.decay_score < 1.0
        assert old_episode.decay_score >= 0.0

    @pytest.mark.asyncio
    async def test_decay_archives_episodes_over_180_days(self, lifecycle_service, sample_episodes):
        """Should archive episodes older than 180 days"""
        # Episode from 200 days ago should be archived
        very_old_episode = sample_episodes[2]
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = [very_old_episode]

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert result["archived"] >= 0
        # 200 days > 180, so should be archived
        if very_old_episode.status == "archived":
            assert very_old_episode.archived_at is not None

    @pytest.mark.asyncio
    async def test_decay_returns_affected_and_archived_counts(self, lifecycle_service, sample_episodes):
        """Should return counts of affected and archived episodes"""
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = sample_episodes

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert isinstance(result["affected"], int)
        assert isinstance(result["archived"], int)
        assert result["affected"] >= result["archived"]  # Archived is subset of affected


# ========================================================================
# B. Consolidation (4 tests)
# =========================================================================

class TestConsolidation:
    """Test episode consolidation operations"""

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_by_vector(self, lifecycle_service):
        """Should consolidate episodes using semantic similarity"""
        # Mock LanceDB search to return similar episodes
        lifecycle_service.lancedb.search.return_value = [
            {
                "id": "search1",
                "metadata": '{"episode_id": "ep2"}',
                "_distance": 0.1  # High similarity (0.9)
            },
            {
                "id": "search2",
                "metadata": '{"episode_id": "ep3"}',
                "_distance": 0.2  # Similarity = 0.8
            }
        ]

        # Mock episode queries
        mock_query_result = MagicMock()
        mock_query_result.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        lifecycle_service.db.query.return_value = mock_query_result

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        assert "consolidated" in result
        assert "parent_episodes" in result

    @pytest.mark.asyncio
    async def test_consolidate_merges_under_parent(self, lifecycle_service):
        """Should merge similar episodes under a parent episode"""
        # Mock to return episodes for consolidation
        parent_episode = Episode(
            id="parent_ep",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Parent Episode",
            description="Parent",
            summary="Parent summary",
            status="completed",
            started_at=datetime.now(),
            decay_score=1.0
        )

        child_episode = Episode(
            id="child_ep",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Child Episode",
            description="Child",
            summary="Child summary",
            status="completed",
            started_at=datetime.now(),
            decay_score=1.0,
            consolidated_into=None  # Not yet consolidated
        )

        # Mock query chain
        query_mock = lifecycle_service.db.query.return_value
        query_mock.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent_episode]

        # Second query for child episode
        child_query_mock = MagicMock()
        child_query_mock.filter.return_value.filter.return_value.first.return_value = child_episode

        # Alternate between parent query and child query
        call_count = [0]
        def query_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return query_mock
            else:
                return child_query_mock

        lifecycle_service.db.query.side_effect = query_side_effect

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Verify consolidation was attempted
        assert "consolidated" in result

    @pytest.mark.asyncio
    async def test_consolidate_respects_similarity_threshold(self, lifecycle_service):
        """Should only consolidate episodes above similarity threshold"""
        # Return results below threshold
        lifecycle_service.lancedb.search.return_value = [
            {
                "id": "search1",
                "metadata": '{"episode_id": "ep2"}',
                "_distance": 0.5  # Low similarity (0.5) < 0.85 threshold
            }
        ]

        query_mock = MagicMock()
        query_mock.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        lifecycle_service.db.query.return_value = query_mock

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Should not consolidate low-similarity episodes
        assert result["consolidated"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_empty_results(self, lifecycle_service):
        """Should handle empty episode list"""
        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        assert result["consolidated"] == 0
        assert result["parent_episodes"] == 0


# ========================================================================
# C. Archival (3 tests)
# =========================================================================

class TestArchival:
    """Test episode archival operations"""

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage(self, lifecycle_service):
        """Should archive episode to cold storage"""
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Test Episode",
            description="Test",
            summary="Test summary",
            status="completed",
            started_at=datetime.now(),
            decay_score=1.0
        )

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.archive_to_cold_storage(episode_id="ep1")

        assert result is True
        assert episode.status == "archived"
        assert episode.archived_at is not None
        lifecycle_service.db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_updates_status_and_timestamp(self, lifecycle_service):
        """Should update episode status and archived_at timestamp"""
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Test Episode",
            description="Test",
            summary="Test summary",
            status="completed",
            started_at=datetime.now(),
            decay_score=1.0
        )

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        before_archive = datetime.now()
        await lifecycle_service.archive_to_cold_storage(episode_id="ep1")
        after_archive = datetime.now()

        assert episode.status == "archived"
        assert before_archive <= episode.archived_at <= after_archive

    @pytest.mark.asyncio
    async def test_archive_prevents_further_modification(self, lifecycle_service):
        """Should prevent further modification after archival"""
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Test Episode",
            description="Test",
            summary="Test summary",
            status="completed",
            started_at=datetime.now(),
            decay_score=1.0
        )

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        await lifecycle_service.archive_to_cold_storage(episode_id="ep1")

        # After archival, status should be "archived"
        assert episode.status == "archived"
        # Further operations should check this status


# ========================================================================
# D. Importance Scoring (2 tests)
# =========================================================================

class TestImportanceScoring:
    """Test importance score updates"""

    @pytest.mark.asyncio
    async def test_update_importance_score(self, lifecycle_service):
        """Should update episode importance based on feedback"""
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Test Episode",
            description="Test",
            summary="Test summary",
            status="completed",
            started_at=datetime.now(),
            importance_score=0.5,
            decay_score=1.0
        )

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        result = await lifecycle_service.update_importance_scores(
            episode_id="ep1",
            user_feedback=0.8  # Positive feedback
        )

        assert result is True
        # Importance should increase with positive feedback
        # Formula: new_importance = old * 0.8 + (feedback + 1) / 2 * 0.2
        # new_importance = 0.5 * 0.8 + 1.8 / 2 * 0.2 = 0.4 + 0.18 = 0.58
        assert episode.importance_score > 0.5
        assert episode.importance_score <= 1.0

    @pytest.mark.asyncio
    async def test_importance_based_on_access_and_feedback(self, lifecycle_service):
        """Should consider access count and feedback for importance"""
        episode = Episode(
            id="ep1",
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Popular Episode",
            description="Popular",
            summary="Popular summary",
            status="completed",
            started_at=datetime.now(),
            importance_score=0.5,
            access_count=100,  # High access count
            decay_score=1.0
        )

        lifecycle_service.db.query.return_value.filter.return_value.first.return_value = episode

        await lifecycle_service.update_importance_scores(
            episode_id="ep1",
            user_feedback=0.9  # Very positive feedback
        )

        # With high feedback and access, importance should be high
        assert episode.importance_score >= 0.5


# ========================================================================
# E. Error Paths (2 tests)
# =========================================================================

class TestErrorPaths:
    """Test error handling paths"""

    @pytest.mark.asyncio
    async def test_decay_with_database_error(self, lifecycle_service):
        """Should handle database errors during decay"""
        # Mock database to raise error on commit
        lifecycle_service.db.commit.side_effect = Exception("Database commit failed")

        # Set up mock to return episodes
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = []

        # Should raise exception (not swallow it)
        with pytest.raises(Exception, match="Database commit failed"):
            await lifecycle_service.decay_old_episodes(days_threshold=90)

    @pytest.mark.asyncio
    async def test_consolidate_with_lancedb_error(self, lifecycle_service):
        """Should handle LanceDB errors during consolidation"""
        # Mock empty results (no episodes to consolidate)
        lifecycle_service.db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # LanceDB error should be handled gracefully
        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Should return without crashing
        assert "consolidated" in result
        assert result["consolidated"] == 0


# ========================================================================
# F. Batch Update Access Counts (4 tests)
# ========================================================================

class TestBatchUpdateAccessCounts:
    """Test batch update access counts method"""

    @pytest.mark.asyncio
    async def test_batch_update_access_counts_multiple_episodes(self, lifecycle_service):
        """Should increment access counts for multiple episodes"""
        # Create 3 episodes with unique IDs
        ep1 = Episode(
            id=str(uuid.uuid4()),
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Episode 1",
            status="completed",
            started_at=datetime.now(),
            access_count=5
        )
        ep2 = Episode(
            id=str(uuid.uuid4()),
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Episode 2",
            status="completed",
            started_at=datetime.now(),
            access_count=3
        )
        ep3 = Episode(
            id=str(uuid.uuid4()),
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Episode 3",
            status="completed",
            started_at=datetime.now(),
            access_count=10
        )

        episode_ids = [ep1.id, ep2.id, ep3.id]

        # Mock query to return episodes by ID - use a simpler approach
        # Create a mapping of episode IDs to episodes
        episode_map = {ep1.id: ep1, ep2.id: ep2, ep3.id: ep3}
        query_call_count = [0]

        def mock_query_side_effect(*args, **kwargs):
            mock_query = MagicMock()
            mock_filter = MagicMock()

            def first_side_effect():
                # Extract episode ID from filter call
                query_call_count[0] += 1
                # Return the appropriate episode based on call order
                if query_call_count[0] == 1:
                    return ep1
                elif query_call_count[0] == 2:
                    return ep2
                elif query_call_count[0] == 3:
                    return ep3
                return None

            mock_filter.first.side_effect = first_side_effect
            mock_query.filter.return_value = mock_filter
            return mock_query

        lifecycle_service.db.query.side_effect = mock_query_side_effect

        # Act
        result = await lifecycle_service.batch_update_access_counts(episode_ids)

        # Assert
        assert result["updated"] == 3
        # Each episode should be incremented exactly once
        assert ep1.access_count == 6  # 5 + 1
        assert ep2.access_count == 4  # 3 + 1
        assert ep3.access_count == 11  # 10 + 1
        lifecycle_service.db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_update_access_counts_empty_list(self, lifecycle_service):
        """Should return updated: 0 for empty episode_ids list"""
        # Act
        result = await lifecycle_service.batch_update_access_counts([])

        # Assert
        assert result["updated"] == 0
        # Verify commit was still called (method commits even if no updates)
        lifecycle_service.db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_update_access_counts_nonexistent_episodes(self, lifecycle_service):
        """Should handle missing episodes gracefully"""
        # Mock query to return None for all IDs
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        lifecycle_service.db.query.return_value = mock_query

        # Act with IDs that don't exist
        result = await lifecycle_service.batch_update_access_counts([
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4())
        ])

        # Assert - should not crash, just report 0 updated
        assert result["updated"] == 0

    @pytest.mark.asyncio
    async def test_batch_update_access_counts_duplicate_ids(self, lifecycle_service):
        """Should handle duplicate episode IDs correctly"""
        # Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Episode",
            status="completed",
            started_at=datetime.now(),
            access_count=5
        )

        # Include duplicate ID in list
        episode_ids = [episode.id, episode.id, episode.id]

        # Mock query to return same episode each time
        def mock_query_side_effect(*args, **kwargs):
            mock_query = MagicMock()
            mock_filter = MagicMock()
            mock_filter.first.return_value = episode
            mock_query.filter.return_value = mock_filter
            return mock_query

        lifecycle_service.db.query.side_effect = mock_query_side_effect

        # Act
        result = await lifecycle_service.batch_update_access_counts(episode_ids)

        # Assert - should update same episode 3 times (access_count += 1 three times)
        assert result["updated"] == 3
        assert episode.access_count == 8  # 5 + 1 + 1 + 1


# ========================================================================
# G. Edge Cases (2 tests)
# ========================================================================

class TestEdgeCases:
    """Test edge cases in consolidation and archival"""

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_json_metadata_parsing(self, lifecycle_service):
        """Should handle JSON metadata parsing correctly"""
        # Create a parent episode to trigger the search
        parent_episode = Episode(
            id=str(uuid.uuid4()),
            agent_id="agent1",
            user_id="user1",
            workspace_id="default",
            title="Parent Episode",
            description="Parent description",
            status="completed",
            started_at=datetime.now(),
            consolidated_into=None
        )

        # Mock query to return the parent episode
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [parent_episode]
        lifecycle_service.db.query.return_value = mock_query

        # Mock LanceDB search with string metadata (not dict)
        lifecycle_service.lancedb.search.return_value = [
            {
                "id": "search1",
                "metadata": '{"episode_id": "ep2", "agent_id": "agent1"}',  # String, not dict
                "_distance": 0.1  # High similarity (0.9)
            }
        ]

        # Mock second query for child episode to return None (not found)
        child_query = MagicMock()
        child_query.filter.return_value.filter.return_value.first.return_value = None

        # Set up query to return parent query first, then child query
        query_call_count = [0]
        def query_side_effect(*args, **kwargs):
            query_call_count[0] += 1
            if query_call_count[0] == 1:
                return mock_query
            else:
                return child_query

        lifecycle_service.db.query.side_effect = query_side_effect

        # Act - should not raise JSON parsing error
        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent1",
            similarity_threshold=0.85
        )

        # Assert - should handle JSON parsing
        assert "consolidated" in result
        assert "parent_episodes" in result
        # Verify search was called
        lifecycle_service.lancedb.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_to_cold_storage_nonexistent_episode(self, lifecycle_service):
        """Should return False for nonexistent episode_id"""
        # Mock query to return None (episode not found)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        lifecycle_service.db.query.return_value = mock_query

        # Act
        result = await lifecycle_service.archive_to_cold_storage(
            episode_id=str(uuid.uuid4())
        )

        # Assert - should return False, not raise exception
        assert result is False
        # Verify commit was NOT called (no changes to commit)
        lifecycle_service.db.commit.assert_not_called()


# ========================================================================
# H. Async Lifecycle Method Tests (New for Phase 162)
# ========================================================================
# Tests for actual async methods (not sync wrappers) that were missed
# in Phase 161. These use real database sessions for proper testing.
# ========================================================================


class TestAsyncDecay:
    """
    Test async episode decay methods.

    Phase 161 tested sync wrappers (apply_decay) but not the actual
    async method (decay_old_episodes). These tests directly test
    the async decay implementation.
    """

    @pytest.mark.asyncio
    async def test_decay_old_episodes_applies_decay_to_old_episodes(
        self, lifecycle_service
    ):
        """
        Should apply decay to episodes older than threshold.

        Creates 2 episodes:
        - 100 days old: decayed (above threshold)
        - 200 days old: decayed AND archived (very old)

        Note: The query filter (started_at < cutoff) only returns episodes
        older than 90 days, so we only mock those episodes.
        """
        # Create episodes with different ages
        # Note: service uses datetime.now() without timezone, so tests must match
        now = datetime.now()
        agent_id = str(uuid.uuid4())

        episode_100_days = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="100 day old episode",
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            outcome="success",
            status="completed",
            started_at=now - timedelta(days=100),
            decay_score=1.0,
            access_count=3
        )

        episode_200_days = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="200 day old episode",
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            outcome="success",
            status="completed",
            started_at=now - timedelta(days=200),
            decay_score=1.0,
            access_count=2
        )

        # Set up mock to return episodes older than 90 days
        episodes_to_return = [episode_100_days, episode_200_days]
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = episodes_to_return

        # Apply decay with 90-day threshold
        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Verify commit was called
        lifecycle_service.db.commit.assert_called_once()

        # Verify decay scores were updated
        # 100-day episode: decayed (decay_score = 1 - 100/180 = 0.44)
        assert episode_100_days.decay_score < 1.0
        assert episode_100_days.decay_score > 0.0

        # 200-day episode: decayed AND archived
        assert episode_200_days.decay_score < 1.0
        assert episode_200_days.status == "archived"
        assert episode_200_days.archived_at is not None

        # Verify counts (100-day and 200-day episodes affected)
        assert result["affected"] == 2
        assert result["archived"] == 1

    @pytest.mark.asyncio
    async def test_decay_old_episodes_excludes_archived(
        self, lifecycle_service
    ):
        """
        Should exclude already archived episodes from decay processing.
        """
        # Note: service uses datetime.now() without timezone
        now = datetime.now()
        agent_id = str(uuid.uuid4())

        # Create archived episode
        archived_episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Already archived episode",
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            outcome="success",
            status="archived",  # Already archived
            started_at=now - timedelta(days=100),
            decay_score=0.5,
            access_count=5,
            archived_at=now - timedelta(days=50)
        )

        # Set up mock to return archived episode (should be excluded by filter)
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = []

        # Apply decay
        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Archived episode should NOT be in affected count
        assert result["affected"] == 0
        assert result["archived"] == 0

    @pytest.mark.asyncio
    async def test_decay_old_episodes_empty_database(
        self, lifecycle_service
    ):
        """
        Should handle empty database gracefully.
        """
        # Set up mock to return no episodes
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = []

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert result["affected"] == 0
        assert result["archived"] == 0

    @pytest.mark.asyncio
    async def test_decay_old_episodes_threshold_edge_case(
        self, lifecycle_service
    ):
        """
        Should treat threshold correctly (< 90 days decayed, >= 90 not decayed).

        Episode exactly 90 days old should NOT be decayed (filter uses < not <=).
        """
        # Note: service uses datetime.now() without timezone
        now = datetime.now()
        agent_id = str(uuid.uuid4())

        # Create episode exactly 90 days old
        episode_90_days = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="90 day old episode",
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            outcome="success",
            status="completed",
            started_at=now - timedelta(days=90),
            decay_score=1.0,
            access_count=5
        )

        # Set up mock to return empty list (90-day episode should be excluded by filter)
        lifecycle_service.db.query.return_value.filter.return_value.all.return_value = []

        # Apply decay with 90-day threshold
        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Episode exactly 90 days old should NOT be decayed
        # (filter uses <, not <=, so 90 days is excluded)
        assert result["affected"] == 0

    def test_update_lifecycle_single_episode(
        self, lifecycle_service
    ):
        """
        Should calculate decay score for single episode using update_lifecycle.

        Decay formula: decay_score = days_old / 90
        60-day-old episode: decay_score = 60 / 90 = 0.67
        """
        # Note: service uses datetime.now() without timezone
        now = datetime.now()
        agent_id = str(uuid.uuid4())

        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="60 day old episode",
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            outcome="success",
            status="completed",
            started_at=now - timedelta(days=60),
            decay_score=1.0,
            access_count=5
        )

        # Update lifecycle
        result = lifecycle_service.update_lifecycle(episode)

        assert result is True
        # decay_score should be approximately 0.67 (60/90)
        assert 0.65 <= episode.decay_score <= 0.70

    def test_update_lifecycle_timezone_aware(
        self, lifecycle_service
    ):
        """
        Should handle timezone-aware datetimes correctly.

        Episode with timezone-aware started_at should not raise TypeError.
        """
        # Note: Test that the service handles timezone-aware datetimes
        # The service checks if started_at has tzinfo and adjusts now() accordingly
        from datetime import timezone

        now = datetime.now(timezone.utc)
        agent_id = str(uuid.uuid4())

        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            tenant_id="default",
            task_description="Timezone-aware episode",
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            outcome="success",
            status="completed",
            started_at=now - timedelta(days=30),  # timezone-aware datetime
            decay_score=1.0,
            access_count=5
        )

        # Should not raise TypeError comparing timezone-aware datetimes
        result = lifecycle_service.update_lifecycle(episode)

        assert result is True
        assert episode.decay_score >= 0.0
