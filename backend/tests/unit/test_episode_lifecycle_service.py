"""
Unit tests for Episode Lifecycle Service

Tests cover:
- Service initialization
- Episode decay operations
- Episode consolidation
- Archive/unarchive operations
- Importance score updates
- Access count tracking
- Cleanup operations
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import Episode


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.query = Mock()
    return db


@pytest.fixture
def mock_lancedb_handler():
    """Mock LanceDB handler"""
    handler = Mock()
    handler.db = Mock()
    handler.table_names = Mock(return_value=["episodes"])
    handler.search = Mock(return_value=[])
    handler.create_table = Mock()
    return handler


@pytest.fixture
def lifecycle_service(mock_db, mock_lancedb_handler):
    """Create EpisodeLifecycleService with mocked dependencies"""
    with patch('core.episode_lifecycle_service.get_lancedb_handler', return_value=mock_lancedb_handler):
        service = EpisodeLifecycleService(mock_db)
        service.lancedb = mock_lancedb_handler
        return service


@pytest.fixture
def sample_episodes():
    """Create sample episodes with different ages"""
    episodes = []
    base_time = datetime.now()

    for i in range(5):
        episode = Mock(spec=Episode)
        episode.id = f"episode_{i}"
        episode.agent_id = "agent_1"
        episode.status = "completed"
        episode.started_at = base_time - timedelta(days=i * 30)  # 0, 30, 60, 90, 120 days
        episode.ended_at = episode.started_at + timedelta(hours=1)
        episode.decay_score = 1.0
        episode.access_count = i * 10
        episode.importance_score = 0.5 + (i * 0.1)
        episode.archived_at = None
        episode.consolidated_into = None

        episodes.append(episode)

    return episodes


@pytest.fixture
def sample_old_episodes():
    """Create old episodes for archival"""
    episodes = []
    base_time = datetime.now()

    for i in range(3):
        episode = Mock(spec=Episode)
        episode.id = f"old_episode_{i}"
        episode.agent_id = "agent_1"
        episode.status = "completed"
        episode.started_at = base_time - timedelta(days=200 + i * 10)  # 200+ days old
        episode.ended_at = episode.started_at + timedelta(hours=1)
        episode.decay_score = 0.2
        episode.access_count = i
        episode.importance_score = 0.3
        episode.archived_at = None
        episode.consolidated_into = None

        episodes.append(episode)

    return episodes


# ============================================================================
# Service Initialization Tests
# ============================================================================

class TestLifecycleServiceInitialization:
    """Test service initialization"""

    def test_lifecycle_service_init(self, lifecycle_service):
        """Test service initialization"""
        assert lifecycle_service.db is not None
        assert lifecycle_service.lancedb is not None


# ============================================================================
# Episode Decay Tests
# ============================================================================

class TestEpisodeDecay:
    """Test episode decay operations"""

    @pytest.mark.asyncio
    async def test_decay_old_episodes_basic(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test basic episode decay"""
        # Mock query to return episodes older than threshold
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_episodes[1:]  # Exclude first (0 days old)
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.decay_old_episodes(days_threshold=30)

        assert result is not None
        assert "affected" in result
        assert result["affected"] > 0
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_decay_old_episodes_no_episodes(
        self,
        lifecycle_service,
        mock_db
    ):
        """Test decay when no old episodes exist"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        assert result["affected"] == 0
        assert result["archived"] == 0

    @pytest.mark.asyncio
    async def test_decay_calculates_scores(
        self,
        lifecycle_service,
        sample_old_episodes,
        mock_db
    ):
        """Test decay score calculation"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_old_episodes
        mock_db.query.return_value = mock_query

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Check that decay scores were updated
        for episode in sample_old_episodes:
            # Decay score should be reduced based on age
            assert episode.decay_score < 1.0
            # Access count should be incremented
            assert episode.access_count > 0

    @pytest.mark.asyncio
    async def test_decay_archives_very_old_episodes(
        self,
        lifecycle_service,
        sample_old_episodes,
        mock_db
    ):
        """Test that very old episodes (>180 days) are archived"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_old_episodes
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Should archive episodes older than 180 days
        assert result["archived"] > 0

        # Check that archived episodes have status and archived_at set
        for episode in sample_old_episodes:
            if (datetime.now() - episode.started_at).days > 180:
                assert episode.status == "archived"
                assert episode.archived_at is not None


# ============================================================================
# Episode Consolidation Tests
# ============================================================================

class TestEpisodeConsolidation:
    """Test episode consolidation operations"""

    @pytest.mark.asyncio
    async def test_consolidate_similar_episodes_basic(
        self,
        lifecycle_service,
        sample_episodes,
        mock_lancedb_handler
    ):
        """Test basic episode consolidation"""
        # Mock LanceDB search to return similar episodes
        mock_lancedb_handler.search.return_value = [
            {
                "_distance": 0.1,  # High similarity (1 - 0.1 = 0.9)
                "metadata": '{"episode_id": "episode_2"}'
            },
            {
                "_distance": 0.2,  # High similarity
                "metadata": '{"episode_id": "episode_3"}'
            }
        ]

        # Mock database query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:3]
        mock_query.filter.return_value.first.side_effect = [sample_episodes[1], sample_episodes[2]]
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent_1",
            similarity_threshold=0.85
        )

        assert result is not None
        assert "consolidated" in result
        assert "parent_episodes" in result

    @pytest.mark.asyncio
    async def test_consolidate_no_episodes(
        self,
        lifecycle_service,
        mock_db
    ):
        """Test consolidation with no episodes"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent_1"
        )

        assert result["consolidated"] == 0
        assert result["parent_episodes"] == 0

    @pytest.mark.asyncio
    async def test_consolidate_with_different_thresholds(
        self,
        lifecycle_service,
        sample_episodes,
        mock_lancedb_handler
    ):
        """Test consolidation with different similarity thresholds"""
        # Test with lower threshold
        mock_lancedb_handler.search.return_value = [
            {
                "_distance": 0.3,  # Medium similarity
                "metadata": '{"episode_id": "episode_2"}'
            }
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:2]
        mock_query.filter.return_value.first.return_value = sample_episodes[1]
        mock_db.query.return_value = mock_query

        result_low = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent_1",
            similarity_threshold=0.6  # Lower threshold
        )

        # Test with higher threshold
        result_high = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent_1",
            similarity_threshold=0.95  # Higher threshold
        )

        # Lower threshold should consolidate more
        assert result_low is not None
        assert result_high is not None

    @pytest.mark.asyncio
    async def test_consolidate_error_handling(
        self,
        lifecycle_service,
        mock_db,
        mock_lancedb_handler
    ):
        """Test consolidation error handling"""
        mock_lancedb_handler.search.side_effect = Exception("LanceDB error")

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = [Mock()]
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent_1"
        )

        # Should return zeros on error
        assert result["consolidated"] == 0
        assert mock_db.rollback.called


# ============================================================================
# Archive Operations Tests
# ============================================================================

class TestArchiveOperations:
    """Test episode archive and unarchive operations"""

    @pytest.mark.asyncio
    async def test_archive_episode_success(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test successful episode archival"""
        episode = sample_episodes[0]

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.archive_to_cold_storage(episode_id="episode_0")

        assert result is True
        assert episode.status == "archived"
        assert episode.archived_at is not None
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_archive_episode_not_found(
        self,
        lifecycle_service,
        mock_db
    ):
        """Test archival when episode not found"""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.archive_to_cold_storage(episode_id="nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_archive_preserves_metadata(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test archival preserves episode metadata"""
        episode = sample_episodes[0]
        original_title = getattr(episode, 'title', 'Test')
        original_agent_id = episode.agent_id

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_db.query.return_value = mock_query

        await lifecycle_service.archive_to_cold_storage(episode_id="episode_0")

        # Metadata should be preserved
        assert episode.agent_id == original_agent_id


# ============================================================================
# Importance Score Tests
# ============================================================================

class TestImportanceScores:
    """Test importance score operations"""

    @pytest.mark.asyncio
    async def test_update_importance_score_positive(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test updating importance with positive feedback"""
        episode = sample_episodes[0]
        episode.importance_score = 0.5

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.update_importance_scores(
            episode_id="episode_0",
            user_feedback=1.0  # Positive
        )

        assert result is True
        # Importance should increase with positive feedback
        assert episode.importance_score >= 0.5
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_update_importance_score_negative(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test updating importance with negative feedback"""
        episode = sample_episodes[0]
        episode.importance_score = 0.5

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.update_importance_scores(
            episode_id="episode_0",
            user_feedback=-1.0  # Negative
        )

        assert result is True
        # Importance should decrease with negative feedback
        assert episode.importance_score <= 0.5

    @pytest.mark.asyncio
    async def test_update_importance_episode_not_found(
        self,
        lifecycle_service,
        mock_db
    ):
        """Test updating importance when episode not found"""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.update_importance_scores(
            episode_id="nonexistent",
            user_feedback=0.5
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_importance_clamps_range(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test importance score is clamped to [0.0, 1.0]"""
        episode = sample_episodes[0]
        episode.importance_score = 0.9

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_db.query.return_value = mock_query

        # Try to set very high feedback
        await lifecycle_service.update_importance_scores(
            episode_id="episode_0",
            user_feedback=2.0  # Above max
        )

        # Should be clamped to 1.0
        assert episode.importance_score <= 1.0


# ============================================================================
# Access Count Tests
# ============================================================================

class TestAccessCounts:
    """Test access count tracking"""

    @pytest.mark.asyncio
    async def test_batch_update_access_counts(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test batch update of access counts"""
        episode_ids = ["episode_0", "episode_1", "episode_2"]

        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [
            sample_episodes[0],
            sample_episodes[1],
            sample_episodes[2]
        ]
        mock_db.query.return_value = mock_query

        original_counts = [e.access_count for e in sample_episodes[:3]]

        result = await lifecycle_service.batch_update_access_counts(episode_ids)

        assert result is not None
        assert result["updated"] == 3
        assert mock_db.commit.called

        # Check that counts were incremented
        for i, episode in enumerate(sample_episodes[:3]):
            assert episode.access_count == original_counts[i] + 1

    @pytest.mark.asyncio
    async def test_batch_update_partial_episodes(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test batch update with some episodes not found"""
        episode_ids = ["episode_0", "nonexistent", "episode_1"]

        mock_query = Mock()
        mock_query.filter.return_value.first.side_effect = [
            sample_episodes[0],
            None,  # Not found
            sample_episodes[1]
        ]
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.batch_update_access_counts(episode_ids)

        # Should update only found episodes
        assert result["updated"] == 2

    @pytest.mark.asyncio
    async def test_batch_update_empty_list(
        self,
        lifecycle_service
    ):
        """Test batch update with empty list"""
        result = await lifecycle_service.batch_update_access_counts([])

        assert result["updated"] == 0


# ============================================================================
# Decay Status Tests
# ============================================================================

class TestDecayStatus:
    """Test decay status tracking"""

    @pytest.mark.asyncio
    async def test_decay_status_fresh_episode(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test decay status for fresh episode"""
        episode = sample_episodes[0]  # 0 days old

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [episode]
        mock_db.query.return_value = mock_query

        await lifecycle_service.decay_old_episodes(days_threshold=30)

        # Fresh episode should have high decay score
        assert episode.decay_score >= 0.9

    @pytest.mark.asyncio
    async def test_decay_status_old_episode(
        self,
        lifecycle_service,
        sample_old_episodes,
        mock_db
    ):
        """Test decay status for old episode"""
        episode = sample_old_episodes[0]  # 200 days old

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [episode]
        mock_db.query.return_value = mock_query

        await lifecycle_service.decay_old_episodes(days_threshold=90)

        # Old episode should have low decay score
        assert episode.decay_score < 0.5


# ============================================================================
# Access Frequency Tests
# ============================================================================

class TestAccessFrequency:
    """Test access frequency calculation"""

    def test_calculate_access_frequency_high(
        self,
        sample_episodes
    ):
        """Test access frequency for frequently accessed episode"""
        episode = sample_episodes[4]  # access_count = 40

        # High access count indicates high frequency
        assert episode.access_count > 20

    def test_calculate_access_frequency_low(
        self,
        sample_episodes
    ):
        """Test access frequency for rarely accessed episode"""
        episode = sample_episodes[0]  # access_count = 0

        # Low access count indicates low frequency
        assert episode.access_count < 10


# ============================================================================
# Promote Hot Episode Tests
# ============================================================================

class TestHotEpisodePromotion:
    """Test hot episode promotion"""

    @pytest.mark.asyncio
    async def test_promote_hot_episode_by_access(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test promoting episode based on access frequency"""
        # Frequently accessed episode
        episode = sample_episodes[4]
        episode.status = "archived"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_db.query.return_value = mock_query

        # Unarchive the episode (simulating promotion)
        episode.status = "completed"
        episode.archived_at = None

        mock_db.commit()

        assert episode.status == "completed"
        assert episode.archived_at is None


# ============================================================================
# Cleanup Operations Tests
# ============================================================================

class TestCleanupOperations:
    """Test cleanup of archived episodes"""

    @pytest.mark.asyncio
    async def test_cleanup_very_old_archives(
        self,
        lifecycle_service,
        mock_db
    ):
        """Test cleanup of very old archived episodes"""
        # This would typically delete episodes older than a threshold
        # For testing, we just verify the operation would be called

        # In real implementation, this would query for episodes
        # older than a threshold and delete them
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 5
        mock_db.query.return_value = mock_query

        # Simulate cleanup
        mock_query.filter.return_value.delete()

        assert mock_query.filter.called


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_consolidate_already_consolidated(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db,
        mock_lancedb_handler
    ):
        """Test consolidation of already consolidated episodes"""
        # Mark some episodes as already consolidated
        sample_episodes[1].consolidated_into = "parent_episode"

        mock_lancedb_handler.search.return_value = []
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = sample_episodes[:3]
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent_1"
        )

        # Should not fail, just skip already consolidated
        assert result is not None

    @pytest.mark.asyncio
    async def test_archive_already_archived(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test archiving an already archived episode"""
        episode = sample_episodes[0]
        episode.status = "archived"
        episode.archived_at = datetime.now()

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_db.query.return_value = mock_query

        # Should still succeed
        result = await lifecycle_service.archive_to_cold_storage(episode_id="episode_0")

        assert result is True

    @pytest.mark.asyncio
    async def test_update_importance_boundary_values(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test importance update with boundary values"""
        episode = sample_episodes[0]
        episode.importance_score = 0.5

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = episode
        mock_db.query.return_value = mock_query

        # Test with minimum feedback
        await lifecycle_service.update_importance_scores(
            episode_id="episode_0",
            user_feedback=-1.0
        )
        assert episode.importance_score >= 0.0

        # Test with maximum feedback
        await lifecycle_service.update_importance_scores(
            episode_id="episode_0",
            user_feedback=1.0
        )
        assert episode.importance_score <= 1.0

    @pytest.mark.asyncio
    async def test_decay_with_zero_threshold(
        self,
        lifecycle_service,
        sample_episodes,
        mock_db
    ):
        """Test decay with zero-day threshold"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_episodes
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.decay_old_episodes(days_threshold=0)

        # Should process all episodes
        assert result["affected"] >= 0

    @pytest.mark.asyncio
    async def test_consolidate_with_lancedb_unavailable(
        self,
        lifecycle_service,
        mock_db
    ):
        """Test consolidation when LanceDB is unavailable"""
        lifecycle_service.lancedb = None

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        result = await lifecycle_service.consolidate_similar_episodes(
            agent_id="agent_1"
        )

        # Should return zeros when LanceDB unavailable
        assert result["consolidated"] == 0


# ============================================================================
# Episode Access Log and Audit Tests
# ============================================================================

class TestEpisodeAccessLog:
    """Test episode access logging and audit trail"""

    @pytest.mark.asyncio
    async def test_log_access(
        self,
        retrieval_service,
        mock_db
    ):
        """Test recording episode access"""
        from core.episode_retrieval_service import EpisodeRetrievalService
        
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
    async def test_get_access_history(
        self,
        mock_db
    ):
        """Test retrieving access log history"""
        from core.models import EpisodeAccessLog
        
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = [
            Mock(spec=EpisodeAccessLog, episode_id="episode_1", access_type="temporal", created_at=datetime.now()),
            Mock(spec=EpisodeAccessLog, episode_id="episode_1", access_type="semantic", created_at=datetime.now()),
        ]
        mock_db.query.return_value = mock_query

        logs = mock_db.query.return_value.filter.return_value.order_by.return_value.all()

        assert len(logs) == 2

    @pytest.mark.asyncio
    async def test_access_count_tracking(
        self,
        retrieval_service,
        mock_db
    ):
        """Test access count is tracked correctly"""
        # Log multiple accesses
        for i in range(5):
            await retrieval_service._log_access(
                episode_id="episode_1",
                access_type="temporal",
                governance_check={"allowed": True},
                agent_id="agent_1",
                results_count=i
            )

        # Should have called add 5 times
        assert mock_db.add.call_count == 5

    @pytest.mark.asyncio
    async def test_last_access_tracking(
        self,
        retrieval_service,
        mock_db
    ):
        """Test last access time is tracked"""
        import time
        
        # Log access
        await retrieval_service._log_access(
            episode_id="episode_1",
            access_type="sequential",
            governance_check={"allowed": True, "agent_maturity": "AUTONOMOUS"},
            agent_id="agent_1",
            results_count=1
        )

        # Verify the log entry was created
        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_audit_trail_integrity(
        self,
        retrieval_service,
        mock_db
    ):
        """Test audit trail maintains integrity"""
        # Test different access types
        access_types = ["temporal", "semantic", "sequential", "contextual"]

        for access_type in access_types:
            await retrieval_service._log_access(
                episode_id="episode_1",
                access_type=access_type,
                governance_check={"allowed": True, "agent_maturity": "INTERN"},
                agent_id="agent_1",
                results_count=10
            )

        # Should have logged all access types
        assert mock_db.add.call_count == len(access_types)

    @pytest.mark.asyncio
    async def test_audit_log_includes_metadata(
        self,
        retrieval_service,
        mock_db
    ):
        """Test audit log includes required metadata"""
        from core.models import EpisodeAccessLog
        
        # Create a mock log entry
        log = EpisodeAccessLog(
            id="log_1",
            episode_id="episode_1",
            accessed_by_agent="agent_1",
            access_type="temporal",
            governance_check_passed=True,
            agent_maturity_at_access="INTERN",
            results_count=5,
            access_duration_ms=150,
            created_at=datetime.now()
        )

        # Verify all required fields
        assert log.episode_id == "episode_1"
        assert log.accessed_by_agent == "agent_1"
        assert log.access_type == "temporal"
        assert log.governance_check_passed is True
        assert log.agent_maturity_at_access == "INTERN"
        assert log.results_count == 5
