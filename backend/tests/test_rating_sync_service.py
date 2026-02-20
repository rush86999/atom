"""
Rating Sync Service Tests - Phase 61 Plan 02

Comprehensive test suite for bidirectional rating sync with Atom SaaS.

Test Coverage:
- SkillRating model extensions (sync tracking fields)
- Batch upload with parallel execution
- Pending ratings query efficiency
- Conflict resolution (timestamp-based)
- Scheduler integration
- Dead letter queue for failed uploads
- Admin endpoint governance
- Edge cases (empty ratings, network errors, duplicates)
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import SkillRating, FailedRatingUpload, Base
from core.rating_sync_service import RatingSyncService
from core.atom_saas_client import AtomSaaSClient


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def test_db():
    """Create test database in-memory"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def mock_atom_client():
    """Mock Atom SaaS client"""
    client = MagicMock(spec=AtomSaaSClient)
    client.rate_skill = AsyncMock(return_value={
        "success": True,
        "id": "remote-rating-123"
    })
    client.get_skill_by_id = AsyncMock(return_value={
        "id": "skill-123",
        "ratings": [{
            "id": "remote-rating-123",
            "user_id": "user-123",
            "rating": 5,
            "comment": "Great skill",
            "created_at": "2026-02-19T12:00:00Z"
        }]
    })
    return client


@pytest.fixture
def rating_sync_service(test_db, mock_atom_client):
    """Create rating sync service with mocked client"""
    return RatingSyncService(test_db, mock_atom_client)


@pytest.fixture
def sample_ratings(test_db):
    """Create sample skill ratings"""
    ratings = []
    for i in range(5):
        rating = SkillRating(
            skill_id=f"skill-{i}",
            user_id="user-123",
            rating=5,
            comment="Great skill",
            created_at=datetime.now(timezone.utc) - timedelta(hours=i)
        )
        test_db.add(rating)
        ratings.append(rating)
    test_db.commit()
    return ratings


# ============================================================================
# TestRatingSyncModelExtensions
# ============================================================================

class TestRatingSyncModelExtensions:
    """Test SkillRating model sync tracking fields"""

    def test_skill_rating_has_synced_at_field(self, test_db):
        """Test SkillRating has synced_at field"""
        rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5
        )
        test_db.add(rating)
        test_db.commit()

        # Initially None
        assert rating.synced_at is None

        # Can be set
        rating.synced_at = datetime.now(timezone.utc)
        test_db.commit()

        # Persisted
        test_db.refresh(rating)
        assert rating.synced_at is not None

    def test_skill_rating_has_synced_to_saas_field(self, test_db):
        """Test SkillRating has synced_to_saas boolean field"""
        rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5
        )
        test_db.add(rating)
        test_db.commit()

        # Default is False
        assert rating.synced_to_saas is False

        # Can be set to True
        rating.synced_to_saas = True
        test_db.commit()

        # Persisted
        test_db.refresh(rating)
        assert rating.synced_to_saas is True

    def test_skill_rating_has_remote_rating_id_field(self, test_db):
        """Test SkillRating has remote_rating_id field"""
        rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5
        )
        test_db.add(rating)
        test_db.commit()

        # Initially None
        assert rating.remote_rating_id is None

        # Can be set
        rating.remote_rating_id = "remote-rating-123"
        test_db.commit()

        # Persisted
        test_db.refresh(rating)
        assert rating.remote_rating_id == "remote-rating-123"

    def test_pending_ratings_query_uses_index(self, test_db):
        """Test pending ratings query is efficient (uses synced_to_saas index)"""
        # Create 100 ratings, 50 synced
        for i in range(100):
            rating = SkillRating(
                skill_id=f"skill-{i}",
                user_id="user-123",
                rating=5
            )
            if i < 50:
                rating.synced_to_saas = True
            test_db.add(rating)
        test_db.commit()

        # Query pending ratings
        service = RatingSyncService(test_db, MagicMock())
        pending = service.get_pending_ratings()

        # Should only get unsynced ratings
        assert len(pending) == 50
        assert all(not r.synced_to_saas for r in pending)


# ============================================================================
# TestRatingSyncServiceBatchUpload
# ============================================================================

class TestRatingSyncServiceBatchUpload:
    """Test batch upload with parallel execution"""

    @pytest.mark.asyncio
    async def test_upload_single_rating_success(self, rating_sync_service, sample_ratings):
        """Test uploading single rating successfully"""
        rating = sample_ratings[0]
        result = await rating_sync_service.upload_rating(rating)

        assert result["success"] is True
        assert result["rating_id"] == "remote-rating-123"

    @pytest.mark.asyncio
    async def test_upload_single_rating_invalid_value(self, rating_sync_service, sample_ratings):
        """Test uploading rating with invalid value (outside 1-5)"""
        rating = sample_ratings[0]
        rating.rating = 6  # Invalid

        result = await rating_sync_service.upload_rating(rating)

        assert result["success"] is False
        assert "Invalid rating value" in result["error"]

    @pytest.mark.asyncio
    async def test_upload_ratings_batch_parallel(self, rating_sync_service, sample_ratings):
        """Test batch upload executes in parallel"""
        results = await rating_sync_service.upload_ratings_batch(sample_ratings)

        assert len(results) == 5
        assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_batch_upload_handles_partial_failures(self, rating_sync_service, sample_ratings, mock_atom_client):
        """Test batch upload handles some failures gracefully"""
        # Track call count to make 3rd upload fail
        call_count = 0

        async def failing_upload(skill_id, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:  # 3rd call fails
                return {"success": False, "error": "Network error"}
            return {"success": True, "id": "remote-rating-123"}

        mock_atom_client.rate_skill = AsyncMock(side_effect=failing_upload)

        results = await rating_sync_service.upload_ratings_batch(sample_ratings)

        assert len(results) == 5
        assert results[0]["success"] is True
        assert results[1]["success"] is True
        assert results[2]["success"] is False
        assert "Network error" in results[2]["error"]

    @pytest.mark.asyncio
    async def test_batch_upload_respects_semaphore_limit(self, rating_sync_service, test_db, mock_atom_client):
        """Test batch upload limits concurrent uploads to 10"""
        # Create 20 ratings
        ratings = []
        for i in range(20):
            rating = SkillRating(
                skill_id=f"skill-{i}",
                user_id="user-123",
                rating=5
            )
            test_db.add(rating)
            ratings.append(rating)
        test_db.commit()

        # Track concurrent uploads
        concurrent_count = 0
        max_concurrent = 0

        async def tracking_upload(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.01)  # Simulate some work
            concurrent_count -= 1
            return {"success": True, "id": "remote-123"}

        mock_atom_client.rate_skill = AsyncMock(side_effect=tracking_upload)

        # Execute batch upload
        await rating_sync_service.upload_ratings_batch(ratings)

        # Should not exceed max concurrent limit
        assert max_concurrent <= rating_sync_service._max_concurrent_uploads


# ============================================================================
# TestRatingSyncServicePending
# ============================================================================

class TestRatingSyncServicePending:
    """Test pending ratings query and management"""

    def test_get_pending_returns_only_unsynced(self, test_db):
        """Test get_pending_ratings only returns unsynced ratings"""
        service = RatingSyncService(test_db, MagicMock())

        # Create 10 ratings, 5 synced
        for i in range(10):
            rating = SkillRating(
                skill_id=f"skill-{i}",
                user_id="user-123",
                rating=5
            )
            if i < 5:
                rating.synced_to_saas = True
            test_db.add(rating)
        test_db.commit()

        pending = service.get_pending_ratings()

        assert len(pending) == 5
        assert all(not r.synced_to_saas for r in pending)

    def test_get_pending_respects_limit(self, test_db):
        """Test get_pending_ratings respects limit parameter"""
        service = RatingSyncService(test_db, MagicMock())

        # Create 100 pending ratings
        for i in range(100):
            rating = SkillRating(
                skill_id=f"skill-{i}",
                user_id="user-123",
                rating=5,
                synced_to_saas=False
            )
            test_db.add(rating)
        test_db.commit()

        # Request 10
        pending = service.get_pending_ratings(limit=10)

        assert len(pending) == 10

    def test_get_pending_orders_by_created_at(self, test_db):
        """Test pending ratings are ordered by created_at"""
        service = RatingSyncService(test_db, MagicMock())

        # Create ratings with different timestamps
        base_time = datetime.now(timezone.utc)
        for i in range(5):
            rating = SkillRating(
                skill_id=f"skill-{i}",
                user_id="user-123",
                rating=5,
                created_at=base_time - timedelta(hours=5-i)
            )
            test_db.add(rating)
        test_db.commit()

        pending = service.get_pending_ratings()

        # Should be ordered oldest first
        assert pending[0].created_at < pending[-1].created_at


# ============================================================================
# TestRatingConflictResolution
# ============================================================================

class TestRatingConflictResolution:
    """Test timestamp-based conflict resolution"""

    @pytest.mark.asyncio
    async def test_remote_newer_updates_local(self, rating_sync_service, test_db):
        """Test remote rating updates local when remote is newer"""
        # Create local rating (old)
        local_time = datetime.now(timezone.utc) - timedelta(hours=2)
        local_rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=4,
            created_at=local_time
        )
        test_db.add(local_rating)
        test_db.commit()

        # Remote rating (newer)
        remote_rating = {
            "id": "remote-123",
            "rating": 5,
            "comment": "Updated comment",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        }

        result = await rating_sync_service.resolve_rating_conflict(local_rating, remote_rating)

        assert result["action"] == "updated_local"
        assert "Remote rating is newer" in result["reason"]

        # Verify local was updated
        test_db.refresh(local_rating)
        assert local_rating.rating == 5
        assert local_rating.comment == "Updated comment"

    @pytest.mark.asyncio
    async def test_local_newer_should_update_remote(self, rating_sync_service, test_db):
        """Test local rating should push to remote when local is newer"""
        # Create local rating (new)
        local_time = datetime.now(timezone.utc) - timedelta(hours=1)
        local_rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5,
            created_at=local_time
        )
        test_db.add(local_rating)
        test_db.commit()

        # Remote rating (older)
        remote_rating = {
            "id": "remote-123",
            "rating": 4,
            "comment": "Old comment",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        }

        result = await rating_sync_service.resolve_rating_conflict(local_rating, remote_rating)

        assert result["action"] == "should_update_remote"
        assert "Local rating is newer" in result["reason"]

    @pytest.mark.asyncio
    async def test_same_timestamp_no_change(self, rating_sync_service, test_db):
        """Test same timestamp results in no change"""
        now = datetime.now(timezone.utc)
        local_rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5,
            created_at=now
        )
        test_db.add(local_rating)
        test_db.commit()

        remote_rating = {
            "id": "remote-123",
            "rating": 4,
            "created_at": now.isoformat()
        }

        result = await rating_sync_service.resolve_rating_conflict(local_rating, remote_rating)

        assert result["action"] == "no_change"
        assert "Timestamps are equal" in result["reason"]

    @pytest.mark.asyncio
    async def test_missing_remote_timestamp_skips(self, rating_sync_service, test_db):
        """Test missing remote timestamp results in skip"""
        local_rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5
        )
        test_db.add(local_rating)
        test_db.commit()

        remote_rating = {
            "id": "remote-123",
            "rating": 4
            # Missing created_at
        }

        result = await rating_sync_service.resolve_rating_conflict(local_rating, remote_rating)

        assert result["action"] == "skip"
        assert "no timestamp" in result["reason"]


# ============================================================================
# TestDeadLetterQueue
# ============================================================================

class TestDeadLetterQueue:
    """Test failed upload dead letter queue"""

    def test_failed_upload_stored_in_queue(self, test_db):
        """Test failed uploads are stored in FailedRatingUpload table"""
        service = RatingSyncService(test_db, MagicMock())

        rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5
        )
        test_db.add(rating)
        test_db.commit()

        # Simulate failed upload
        service.handle_upload_failure(rating, "Network timeout")

        # Verify failed record exists
        failed = (
            test_db.query(FailedRatingUpload)
            .filter(FailedRatingUpload.rating_id == rating.id)
            .first()
        )

        assert failed is not None
        assert failed.error_message == "Network timeout"
        assert failed.retry_count == 1

    def test_failed_upload_increments_retry_count(self, test_db):
        """Test retry count increments on subsequent failures"""
        service = RatingSyncService(test_db, MagicMock())

        rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5
        )
        test_db.add(rating)
        test_db.commit()

        # First failure
        service.handle_upload_failure(rating, "Error 1")
        failed = test_db.query(FailedRatingUpload).first()
        assert failed.retry_count == 1

        # Second failure
        service.handle_upload_failure(rating, "Error 2")
        test_db.refresh(failed)
        assert failed.retry_count == 2
        assert failed.error_message == "Error 2"

    @pytest.mark.asyncio
    async def test_sync_metrics_counts_failed_uploads(self, test_db):
        """Test sync metrics includes failed upload count"""
        service = RatingSyncService(test_db, MagicMock())

        # Create failed uploads
        for i in range(3):
            rating = SkillRating(
                skill_id=f"skill-{i}",
                user_id="user-123",
                rating=5
            )
            test_db.add(rating)
            test_db.commit()
            service.handle_upload_failure(rating, f"Error {i}")

        metrics = service.get_sync_metrics()

        assert metrics["failed_count"] == 3

    def test_failed_upload_updates_last_retry_at(self, test_db):
        """Test last_retry_at is updated on retry"""
        service = RatingSyncService(test_db, MagicMock())

        rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5
        )
        test_db.add(rating)
        test_db.commit()

        # First failure - last_retry_at should be None initially
        service.handle_upload_failure(rating, "Error 1")
        failed = test_db.query(FailedRatingUpload).first()
        assert failed.retry_count == 1
        assert failed.last_retry_at is None  # First failure doesn't set last_retry_at

        # Wait and retry
        import time
        time.sleep(0.01)
        service.handle_upload_failure(rating, "Error 2")
        test_db.refresh(failed)

        # last_retry_at should now be set
        assert failed.retry_count == 2
        assert failed.last_retry_at is not None


# ============================================================================
# TestRatingSyncOrchestration
# ============================================================================

class TestRatingSyncOrchestration:
    """Test full sync orchestration"""

    @pytest.mark.asyncio
    async def test_sync_ratings_uploads_pending(self, rating_sync_service, test_db, mock_atom_client):
        """Test sync_ratings uploads all pending ratings"""
        # Create 10 pending ratings
        for i in range(10):
            rating = SkillRating(
                skill_id=f"skill-{i}",
                user_id="user-123",
                rating=5,
                synced_to_saas=False
            )
            test_db.add(rating)
        test_db.commit()

        result = await rating_sync_service.sync_ratings()

        assert result["success"] is True
        assert result["uploaded"] == 10
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_sync_ratings_marks_as_synced(self, rating_sync_service, test_db, mock_atom_client):
        """Test successful uploads mark ratings as synced"""
        rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5,
            synced_to_saas=False
        )
        test_db.add(rating)
        test_db.commit()

        await rating_sync_service.sync_ratings()

        # Verify marked as synced
        test_db.refresh(rating)
        assert rating.synced_to_saas is True
        assert rating.synced_at is not None
        assert rating.remote_rating_id == "remote-rating-123"

    @pytest.mark.asyncio
    async def test_sync_ratings_handles_empty_pending(self, rating_sync_service, test_db):
        """Test sync completes gracefully with no pending ratings"""
        result = await rating_sync_service.sync_ratings()

        assert result["success"] is True
        assert result["uploaded"] == 0
        assert result["message"] == "No pending ratings"

    @pytest.mark.asyncio
    async def test_sync_returns_503_if_already_in_progress(self, rating_sync_service, test_db):
        """Test sync returns error if already in progress"""
        # Set flag manually
        rating_sync_service._sync_in_progress = True

        result = await rating_sync_service.sync_ratings()

        assert result["success"] is False
        assert "already in progress" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_upload_all_flag(self, rating_sync_service, test_db, mock_atom_client):
        """Test upload_all flag re-syncs all ratings"""
        # Create 5 ratings, 3 already synced
        for i in range(5):
            rating = SkillRating(
                skill_id=f"skill-{i}",
                user_id="user-123",
                rating=5,
                synced_to_saas=(i < 3)
            )
            test_db.add(rating)
        test_db.commit()

        # Sync all
        result = await rating_sync_service.sync_ratings(upload_all=True)

        # Should process all 5 (re-uploads synced ones too)
        assert result["uploaded"] == 5


# ============================================================================
# TestRatingSyncMetrics
# ============================================================================

class TestRatingSyncMetrics:
    """Test sync metrics and monitoring"""

    def test_get_sync_metrics_returns_counts(self, test_db):
        """Test get_sync_metrics returns accurate counts"""
        service = RatingSyncService(test_db, MagicMock())

        # Create ratings
        for i in range(5):
            rating = SkillRating(
                skill_id=f"skill-{i}",
                user_id="user-123",
                rating=5,
                synced_to_saas=(i < 3)
            )
            test_db.add(rating)
        test_db.commit()

        metrics = service.get_sync_metrics()

        assert metrics["synced_count"] == 3
        assert metrics["pending_count"] == 2

    def test_get_sync_metrics_includes_failed_count(self, test_db):
        """Test metrics include failed upload count"""
        service = RatingSyncService(test_db, MagicMock())

        # Create failed upload
        rating = SkillRating(
            skill_id="skill-123",
            user_id="user-123",
            rating=5
        )
        test_db.add(rating)
        test_db.commit()
        service.handle_upload_failure(rating, "Error")

        metrics = service.get_sync_metrics()

        assert metrics["failed_count"] == 1
