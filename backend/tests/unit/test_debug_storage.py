"""
Comprehensive unit tests for HybridDebugStorage class

Tests cover:
- Initialization and configuration
- Event storage (hot, warm, cold tiers)
- Insight storage and retrieval
- State snapshot management
- Data tier migration
- Archive operations
- Time range parsing
- Dictionary conversion helpers
- Error handling and edge cases
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any
import json
import gzip

# Import the HybridDebugStorage and related classes
from core.debug_storage import (
    HybridDebugStorage,
    DEBUG_REDIS_HOT_TTL_HOURS,
    DEBUG_EVENT_RETENTION_HOURS,
    DEBUG_INSIGHT_RETENTION_HOURS,
    DEBUG_ARCHIVE_PATH,
    DEBUG_REDIS_KEY_PREFIX
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db_session():
    """Mock database session for testing"""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.delete = MagicMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    redis = MagicMock()
    redis.setex = MagicMock()
    redis.get = MagicMock()
    return redis


@pytest.fixture
def temp_archive_dir(tmp_path):
    """Create a temporary directory for archive testing"""
    archive_dir = tmp_path / "debug_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return str(archive_dir)


@pytest.fixture
def debug_storage(mock_db_session, mock_redis_client, temp_archive_dir):
    """Create a HybridDebugStorage instance with mocked dependencies"""
    with patch('core.debug_storage.StructuredLogger'):
        storage = HybridDebugStorage(
            db_session=mock_db_session,
            redis_client=mock_redis_client,
            archive_path=temp_archive_dir
        )
        yield storage


@pytest.fixture
def sample_debug_event():
    """Sample debug event for testing"""
    event = MagicMock()
    event.id = "event-123"
    event.event_type = "agent_step"
    event.component_type = "agent"
    event.component_id = "agent-456"
    event.correlation_id = "corr-789"
    event.parent_event_id = None
    event.level = "INFO"
    event.message = "Step completed successfully"
    event.data = {"step_name": "process", "duration": 1.5}
    event.event_metadata = {"retry_count": 0}
    event.timestamp = datetime(2024, 1, 15, 10, 30, 0)
    return event


@pytest.fixture
def sample_debug_insight():
    """Sample debug insight for testing"""
    insight = MagicMock()
    insight.id = "insight-123"
    insight.insight_type = "performance"
    insight.severity = "medium"
    insight.title = "Slow step execution"
    insight.description = "Step took longer than expected"
    insight.summary = "Average duration: 2.5s"
    insight.evidence = {"durations": [2.0, 2.5, 3.0]}
    insight.confidence_score = 0.85
    insight.suggestions = ["Optimize database queries"]
    insight.resolved = False
    insight.resolution_notes = None
    insight.scope = "workflow"
    insight.affected_components = ["step1", "step2"]
    insight.generated_at = datetime(2024, 1, 15, 10, 30, 0)
    insight.expires_at = datetime(2024, 1, 22, 10, 30, 0)
    return insight


@pytest.fixture
def sample_state_snapshot():
    """Sample state snapshot for testing"""
    snapshot = MagicMock()
    snapshot.id = "snapshot-123"
    snapshot.component_type = "agent"
    snapshot.component_id = "agent-456"
    snapshot.operation_id = "op-789"
    snapshot.checkpoint_name = "pre_execution"
    snapshot.state_data = {"var1": "value1", "var2": 42}
    snapshot.diff_from_previous = '{"var1": ["old_value", "value1"]}'
    snapshot.snapshot_type = "checkpoint"
    snapshot.captured_at = datetime(2024, 1, 15, 10, 30, 0)
    return snapshot


# =============================================================================
# TEST STORAGE INITIALIZATION
# =============================================================================

class TestDebugStorageInit:
    """Tests for HybridDebugStorage initialization"""

    def test_init_creates_archive_directory(self, mock_db_session, mock_redis_client, tmp_path):
        """Test that initialization creates archive directory"""
        archive_dir = tmp_path / "test_archive"

        with patch('core.debug_storage.StructuredLogger'):
            storage = HybridDebugStorage(
                db_session=mock_db_session,
                redis_client=mock_redis_client,
                archive_path=str(archive_dir)
            )

            assert archive_dir.exists()
            assert storage.archive_path == archive_dir

    def test_init_sets_key_prefixes(self, debug_storage):
        """Test that Redis key prefixes are set correctly"""
        assert debug_storage._event_key_prefix == f"{DEBUG_REDIS_KEY_PREFIX}:event"
        assert debug_storage._insight_key_prefix == f"{DEBUG_REDIS_KEY_PREFIX}:insight"
        assert debug_storage._state_key_prefix == f"{DEBUG_REDIS_KEY_PREFIX}:state"
        assert debug_storage._metric_key_prefix == f"{DEBUG_REDIS_KEY_PREFIX}:metric"


# =============================================================================
# TEST EVENT STORAGE
# =============================================================================

class TestEventStorage:
    """Tests for event storage operations"""

    @pytest.mark.asyncio
    async def test_store_event_hot_and_warm(self, debug_storage, sample_debug_event):
        """Test storing event in both hot and warm tiers"""
        result = await debug_storage.store_event(
            sample_debug_event,
            store_hot=True,
            store_warm=True
        )

        assert result is True
        debug_storage.redis.setex.assert_called_once()
        debug_storage.db.add.assert_called_once_with(sample_debug_event)

    @pytest.mark.asyncio
    async def test_store_event_hot_only(self, debug_storage, sample_debug_event):
        """Test storing event only in hot tier"""
        result = await debug_storage.store_event(
            sample_debug_event,
            store_hot=True,
            store_warm=False
        )

        assert result is True
        debug_storage.redis.setex.assert_called_once()
        debug_storage.db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_event_warm_only(self, debug_storage, sample_debug_event):
        """Test storing event only in warm tier"""
        result = await debug_storage.store_event(
            sample_debug_event,
            store_hot=False,
            store_warm=True
        )

        assert result is True
        debug_storage.redis.setex.assert_not_called()
        debug_storage.db.add.assert_called_once_with(sample_debug_event)

    @pytest.mark.asyncio
    async def test_store_event_error_handling(self, debug_storage, sample_debug_event):
        """Test error handling when storing event"""
        debug_storage.redis.setex.side_effect = Exception("Redis error")

        result = await debug_storage.store_event(
            sample_debug_event,
            store_hot=True,
            store_warm=False
        )

        assert result is False


# =============================================================================
# TEST EVENT RETRIEVAL
# =============================================================================

class TestEventRetrieval:
    """Tests for event retrieval operations"""

    @pytest.mark.asyncio
    async def test_get_event_from_hot(self, debug_storage, sample_debug_event):
        """Test retrieving event from hot tier"""
        event_dict = debug_storage._event_to_dict(sample_debug_event)
        debug_storage.redis.get.return_value = json.dumps(event_dict)

        result = await debug_storage.get_event("event-123")

        assert result is not None
        assert result["id"] == "event-123"
        debug_storage.redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_event_from_warm(self, debug_storage, sample_debug_event):
        """Test retrieving event from warm tier when not in hot"""
        debug_storage.redis.get.return_value = None

        # Mock database query
        mock_query = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = sample_debug_event
        debug_storage.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_result

        result = await debug_storage.get_event("event-123")

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_event_not_found(self, debug_storage):
        """Test retrieving non-existent event"""
        debug_storage.redis.get.return_value = None

        mock_query = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        debug_storage.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_result

        result = await debug_storage.get_event("non-existent")

        assert result is None


# =============================================================================
# TEST EVENT QUERIES
# =============================================================================

class TestEventQueries:
    """Tests for event query operations"""

    @pytest.mark.asyncio
    async def test_query_events_by_component(self, debug_storage, sample_debug_event):
        """Test querying events by component"""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = [sample_debug_event]
        debug_storage.db.query.return_value = mock_query

        results = await debug_storage.query_events(
            component_type="agent",
            component_id="agent-456"
        )

        assert len(results) == 1
        assert results[0]["component_id"] == "agent-456"

    @pytest.mark.asyncio
    async def test_query_events_with_time_range(self, debug_storage, sample_debug_event):
        """Test querying events with time range filter"""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.all.return_value = [sample_debug_event]
        debug_storage.db.query.return_value = mock_query

        results = await debug_storage.query_events(time_range="last_1h")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_query_events_error_handling(self, debug_storage):
        """Test error handling in event queries"""
        debug_storage.db.query.side_effect = Exception("Database error")

        results = await debug_storage.query_events()

        assert results == []


# =============================================================================
# TEST INSIGHT STORAGE
# =============================================================================

class TestInsightStorage:
    """Tests for insight storage operations"""

    @pytest.mark.asyncio
    async def test_store_insight(self, debug_storage, sample_debug_insight):
        """Test storing insight"""
        result = await debug_storage.store_insight(
            sample_debug_insight,
            store_hot=True,
            store_warm=True
        )

        assert result is True
        debug_storage.redis.setex.assert_called_once()
        debug_storage.db.add.assert_called_once_with(sample_debug_insight)

    @pytest.mark.asyncio
    async def test_get_insight_from_hot(self, debug_storage, sample_debug_insight):
        """Test retrieving insight from hot tier"""
        insight_dict = debug_storage._insight_to_dict(sample_debug_insight)
        debug_storage.redis.get.return_value = json.dumps(insight_dict)

        result = await debug_storage.get_insight("insight-123")

        assert result is not None
        assert result["id"] == "insight-123"

    @pytest.mark.asyncio
    async def test_query_insights(self, debug_storage, sample_debug_insight):
        """Test querying insights with filters"""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_debug_insight]
        debug_storage.db.query.return_value = mock_query

        results = await debug_storage.query_insights(
            insight_type="performance",
            severity="medium"
        )

        assert len(results) == 1
        assert results[0]["insight_type"] == "performance"


# =============================================================================
# TEST STATE SNAPSHOTS
# =============================================================================

class TestStateSnapshots:
    """Tests for state snapshot operations"""

    @pytest.mark.asyncio
    async def test_store_state_snapshot(self, debug_storage, sample_state_snapshot):
        """Test storing state snapshot"""
        result = await debug_storage.store_state_snapshot(
            sample_state_snapshot,
            store_hot=True,
            store_warm=True
        )

        assert result is True
        debug_storage.redis.setex.assert_called_once()
        debug_storage.db.add.assert_called_once_with(sample_state_snapshot)

    @pytest.mark.asyncio
    async def test_get_state_snapshot(self, debug_storage, sample_state_snapshot):
        """Test retrieving state snapshot"""
        mock_query = MagicMock()
        mock_result = MagicMock()
        mock_result.order_by.return_value = mock_result
        mock_result.first.return_value = sample_state_snapshot
        debug_storage.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_result

        result = await debug_storage.get_state_snapshot(
            component_type="agent",
            component_id="agent-456",
            operation_id="op-789"
        )

        assert result is not None
        assert result["component_id"] == "agent-456"

    @pytest.mark.asyncio
    async def test_get_state_snapshot_with_checkpoint(self, debug_storage, sample_state_snapshot):
        """Test retrieving state snapshot with checkpoint filter"""
        mock_query = MagicMock()
        mock_result = MagicMock()
        mock_result.order_by.return_value = mock_result
        mock_result.first.return_value = sample_state_snapshot
        debug_storage.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_result

        result = await debug_storage.get_state_snapshot(
            component_type="agent",
            component_id="agent-456",
            operation_id="op-789",
            checkpoint_name="pre_execution"
        )

        assert result is not None


# =============================================================================
# TEST HOT TIER OPERATIONS
# =============================================================================

class TestHotTierOperations:
    """Tests for Redis hot tier operations"""

    @pytest.mark.asyncio
    async def test_store_event_hot(self, debug_storage, sample_debug_event):
        """Test storing event in Redis"""
        event_dict = debug_storage._event_to_dict(sample_debug_event)

        await debug_storage._store_event_hot("event-123", event_dict)

        debug_storage.redis.setex.assert_called_once()
        call_args = debug_storage.redis.setex.call_args
        key = call_args[0][0]
        assert "event" in key
        assert "event-123" in key

    @pytest.mark.asyncio
    async def test_get_event_hot(self, debug_storage):
        """Test getting event from Redis"""
        event_data = {"id": "event-123", "message": "test"}
        debug_storage.redis.get.return_value = json.dumps(event_data)

        result = await debug_storage._get_event_hot("event-123")

        assert result is not None
        assert result["id"] == "event-123"

    @pytest.mark.asyncio
    async def test_get_event_hot_not_found(self, debug_storage):
        """Test getting non-existent event from Redis"""
        debug_storage.redis.get.return_value = None

        result = await debug_storage._get_event_hot("non-existent")

        assert result is None

    @pytest.mark.asyncio
    async def test_store_insight_hot(self, debug_storage, sample_debug_insight):
        """Test storing insight in Redis"""
        insight_dict = debug_storage._insight_to_dict(sample_debug_insight)

        await debug_storage._store_insight_hot("insight-123", insight_dict)

        debug_storage.redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_insight_hot(self, debug_storage):
        """Test getting insight from Redis"""
        insight_data = {"id": "insight-123", "title": "test"}
        debug_storage.redis.get.return_value = json.dumps(insight_data)

        result = await debug_storage._get_insight_hot("insight-123")

        assert result is not None
        assert result["id"] == "insight-123"


# =============================================================================
# TEST WARM TIER OPERATIONS
# =============================================================================

class TestWarmTierOperations:
    """Tests for PostgreSQL warm tier operations"""

    @pytest.mark.asyncio
    async def test_get_event_warm(self, debug_storage, sample_debug_event):
        """Test getting event from PostgreSQL"""
        mock_query = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = sample_debug_event
        debug_storage.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_result

        result = await debug_storage._get_event_warm("event-123")

        assert result is not None
        assert result["id"] == "event-123"

    @pytest.mark.asyncio
    async def test_get_event_warm_not_found(self, debug_storage):
        """Test getting non-existent event from PostgreSQL"""
        mock_query = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        debug_storage.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_result

        result = await debug_storage._get_event_warm("non-existent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_insight_warm(self, debug_storage, sample_debug_insight):
        """Test getting insight from PostgreSQL"""
        mock_query = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = sample_debug_insight
        debug_storage.db.query.return_value = mock_query
        mock_query.filter.return_value = mock_result

        result = await debug_storage._get_insight_warm("insight-123")

        assert result is not None
        assert result["id"] == "insight-123"


# =============================================================================
# TEST COLD TIER OPERATIONS
# =============================================================================

class TestColdTierOperations:
    """Tests for archive cold tier operations"""

    @pytest.mark.asyncio
    async def test_write_archive(self, debug_storage, temp_archive_dir):
        """Test writing archive file"""
        from pathlib import Path

        archive_file = Path(temp_archive_dir) / "test_archive.json.gz"
        data = [{"id": "1"}, {"id": "2"}]

        await debug_storage._write_archive(archive_file, data)

        assert archive_file.exists()

        # Verify content
        with gzip.open(archive_file, "rt") as f:
            content = json.load(f)
            assert len(content) == 2

    @pytest.mark.asyncio
    async def test_read_archive(self, debug_storage, temp_archive_dir):
        """Test reading archive file"""
        from pathlib import Path

        # Create test archive
        archive_file = Path(temp_archive_dir) / "test_read.json.gz"
        test_data = [{"id": "1"}, {"id": "2"}]

        with gzip.open(archive_file, "wt") as f:
            json.dump(test_data, f)

        result = await debug_storage._read_archive(archive_file)

        assert len(result) == 2
        assert result[0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_get_event_cold(self, debug_storage, temp_archive_dir):
        """Test getting event from archive"""
        from pathlib import Path

        # Create test archive
        archive_file = Path(temp_archive_dir) / "events_2024-01-15.json.gz"
        test_data = [{"id": "event-123", "message": "test"}]

        with gzip.open(archive_file, "wt") as f:
            json.dump(test_data, f)

        result = await debug_storage._get_event_cold("event-123")

        assert result is not None
        assert result["id"] == "event-123"


# =============================================================================
# TEST DATA MIGRATION
# =============================================================================

class TestDataMigration:
    """Tests for data migration operations"""

    @pytest.mark.asyncio
    async def test_migrate_warm_to_cold(self, debug_storage):
        """Test migrating data from warm to cold tier"""
        # Mock old events
        old_event = MagicMock()
        old_event.timestamp = datetime.utcnow() - timedelta(days=10)
        old_event.id = "old-event-123"

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [old_event]
        debug_storage.db.query.return_value = mock_query

        await debug_storage.migrate_warm_to_cold()

        debug_storage.db.delete.assert_called_once_with(old_event)
        debug_storage.db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_expired_data(self, debug_storage, temp_archive_dir):
        """Test cleanup of expired archive files"""
        from pathlib import Path

        # Create old archive file
        old_archive = Path(temp_archive_dir) / "old_archive.json.gz"
        old_archive.touch()

        # Modify file timestamp to make it old
        import time
        old_time = time.time() - (100 * 24 * 60 * 60)  # 100 days ago
        import os
        os.utime(old_archive, (old_time, old_time))

        await debug_storage.cleanup_expired_data()

        assert not old_archive.exists()


# =============================================================================
# TEST HELPER METHODS
# =============================================================================

class TestHelperMethods:
    """Tests for helper methods"""

    def test_event_to_dict(self, debug_storage, sample_debug_event):
        """Test converting event to dictionary"""
        result = debug_storage._event_to_dict(sample_debug_event)

        assert result["id"] == "event-123"
        assert result["event_type"] == "agent_step"
        assert result["component_type"] == "agent"
        assert result["level"] == "INFO"
        assert result["message"] == "Step completed successfully"
        assert result["data"]["step_name"] == "process"
        assert "timestamp" in result

    def test_insight_to_dict(self, debug_storage, sample_debug_insight):
        """Test converting insight to dictionary"""
        result = debug_storage._insight_to_dict(sample_debug_insight)

        assert result["id"] == "insight-123"
        assert result["insight_type"] == "performance"
        assert result["severity"] == "medium"
        assert result["title"] == "Slow step execution"
        assert result["confidence_score"] == 0.85
        assert result["resolved"] is False

    def test_snapshot_to_dict(self, debug_storage, sample_state_snapshot):
        """Test converting snapshot to dictionary"""
        result = debug_storage._snapshot_to_dict(sample_state_snapshot)

        assert result["id"] == "snapshot-123"
        assert result["component_type"] == "agent"
        assert result["component_id"] == "agent-456"
        assert result["operation_id"] == "op-789"
        assert result["checkpoint_name"] == "pre_execution"
        assert result["snapshot_type"] == "checkpoint"

    def test_parse_time_range_last_1h(self, debug_storage):
        """Test parsing 'last_1h' time range"""
        result = debug_storage._parse_time_range("last_1h")

        assert result is not None
        expected = datetime.utcnow() - timedelta(hours=1)
        assert abs((result - expected).total_seconds()) < 5

    def test_parse_time_range_last_24h(self, debug_storage):
        """Test parsing 'last_24h' time range"""
        result = debug_storage._parse_time_range("last_24h")

        assert result is not None
        expected = datetime.utcnow() - timedelta(hours=24)
        assert abs((result - expected).total_seconds()) < 5

    def test_parse_time_range_last_7d(self, debug_storage):
        """Test parsing 'last_7d' time range"""
        result = debug_storage._parse_time_range("last_7d")

        assert result is not None
        expected = datetime.utcnow() - timedelta(days=7)
        assert abs((result - expected).total_seconds()) < 5

    def test_parse_time_range_invalid(self, debug_storage):
        """Test parsing invalid time range"""
        result = debug_storage._parse_time_range("invalid_range")

        assert result is None
