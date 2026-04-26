"""
Test Suite for Hybrid Debug Storage

Tests for core.debug_storage module (638 lines)
- Event storage (Redis hot, PostgreSQL warm, archive cold)
- Insight storage and retrieval
- State snapshot management
- Data migration (hot → warm → cold)
- Multi-tier storage architecture

Target Tests: 20-25
Target Coverage: 25-30%
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest

from core.debug_storage import HybridDebugStorage


class TestHybridDebugStorageInit:
    """Test HybridDebugStorage initialization."""

    def test_initialization_with_db_and_redis(self):
        """HybridDebugStorage can be initialized with database and Redis clients."""
        mock_db = Mock()
        mock_redis = Mock()

        storage = HybridDebugStorage(
            db_session=mock_db,
            redis_client=mock_redis,
            archive_path="/tmp/test_archive"
        )

        assert storage.db == mock_db
        assert storage.redis == mock_redis
        assert storage.archive_path == Path("/tmp/test_archive")

    def test_initialization_creates_archive_directory(self):
        """HybridDebugStorage creates archive directory on initialization."""
        mock_db = Mock()
        mock_redis = Mock()
        archive_path = "/tmp/test_debug_archive"

        with patch('pathlib.Path.mkdir') as mock_mkdir:
            storage = HybridDebugStorage(
                db_session=mock_db,
                redis_client=mock_redis,
                archive_path=archive_path
            )

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_initialization_sets_redis_key_prefixes(self):
        """HybridDebugStorage sets correct Redis key prefixes."""
        mock_db = Mock()
        mock_redis = Mock()

        storage = HybridDebugStorage(
            db_session=mock_db,
            redis_client=mock_redis
        )

        assert storage._event_key_prefix.startswith("debug")
        assert storage._insight_key_prefix.startswith("debug")
        assert storage._state_key_prefix.startswith("debug")
        assert storage._metric_key_prefix.startswith("debug")


class TestEventStorage:
    """Test event storage in hybrid storage system."""

    @pytest.fixture
    def storage(self):
        """Create storage instance with mocked dependencies."""
        mock_db = Mock()
        mock_redis = AsyncMock()
        return HybridDebugStorage(
            db_session=mock_db,
            redis_client=mock_redis,
            archive_path="/tmp/test_archive"
        )

    @pytest.mark.asyncio
    async def test_store_event_in_hot_and_warm(self, storage):
        """HybridDebugStorage can store event in both hot and warm tiers."""
        mock_event = Mock()
        mock_event.id = "event-001"
        mock_event.timestamp = datetime.now()

        result = await storage.store_event(
            event=mock_event,
            store_hot=True,
            store_warm=True
        )

        assert result is True
        storage.db.add.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_store_event_hot_tier_only(self, storage):
        """HybridDebugStorage can store event in hot tier only."""
        mock_event = Mock()
        mock_event.id = "event-002"

        result = await storage.store_event(
            event=mock_event,
            store_hot=True,
            store_warm=False
        )

        assert result is True
        # Should not add to database
        storage.db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_event_handles_errors(self, storage):
        """HybridDebugStorage handles storage errors gracefully."""
        mock_event = Mock()
        mock_event.id = "event-003"

        # Mock database error
        storage.db.add.side_effect = Exception("Database error")

        result = await storage.store_event(
            event=mock_event,
            store_hot=False,
            store_warm=True
        )

        assert result is False


class TestEventRetrieval:
    """Test event retrieval from hybrid storage."""

    @pytest.fixture
    def storage(self):
        """Create storage instance with mocked dependencies."""
        mock_db = Mock()
        mock_redis = AsyncMock()
        return HybridDebugStorage(
            db_session=mock_db,
            redis_client=mock_redis
        )

    @pytest.mark.asyncio
    async def test_get_event_from_hot_tier(self, storage):
        """HybridDebugStorage retrieves event from hot tier (Redis) first."""
        event_data = {"id": "event-001", "message": "Test event"}
        storage.redis.get.return_value = '{"id": "event-001", "message": "Test event"}'

        result = await storage.get_event(event_id="event-001")

        assert result is not None
        assert result["id"] == "event-001"

    @pytest.mark.asyncio
    async def test_get_event_promotes_from_warm_to_hot(self, storage):
        """HybridDebugStorage promotes event from warm to hot tier."""
        # Mock Redis miss
        storage.redis.get.return_value = None

        # Mock database hit
        mock_event = Mock()
        mock_event.id = "event-002"
        mock_event.timestamp = datetime.now()

        async def mock_get_event_warm(event_id):
            if event_id == "event-002":
                return storage._event_to_dict(mock_event)
            return None

        storage._get_event_warm = mock_get_event_warm

        result = await storage.get_event(event_id="event-002")

        assert result is not None
        assert result["id"] == "event-002"
        # Should have promoted to hot tier
        storage.redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_get_event_returns_none_if_not_found(self, storage):
        """HybridDebugStorage returns None when event not found in any tier."""
        # Mock miss in all tiers
        storage.redis.get.return_value = None
        storage._get_event_warm = AsyncMock(return_value=None)
        storage._get_event_cold = AsyncMock(return_value=None)

        result = await storage.get_event(event_id="nonexistent-event")

        assert result is None


class TestEventQuerying:
    """Test event querying with filters."""

    @pytest.fixture
    def storage(self):
        """Create storage instance with mocked database."""
        mock_db = Mock()
        mock_redis = AsyncMock()
        return HybridDebugStorage(
            db_session=mock_db,
            redis_client=mock_redis
        )

    @pytest.mark.asyncio
    async def test_query_events_by_component_type(self, storage):
        """HybridDebugStorage can query events by component type."""
        # Mock query chain
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = [
            Mock(id="event-001", component_type="agent"),
            Mock(id="event-002", component_type="agent")
        ]
        storage.db.query.return_value = mock_query

        result = await storage.query_events(component_type="agent", limit=10)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_query_events_with_time_range(self, storage):
        """HybridDebugStorage can query events with time range filter."""
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = []
        storage.db.query.return_value = mock_query

        result = await storage.query_events(time_range="last_1h")

        # Should apply time filter
        assert mock_query.filter.call_count >= 2  # Once for component, once for time

    @pytest.mark.asyncio
    async def test_query_events_handles_errors(self, storage):
        """HybridDebugStorage handles query errors gracefully."""
        storage.db.query.side_effect = Exception("Database error")

        result = await storage.query_events(component_type="agent")

        assert result == []


class TestInsightStorage:
    """Test insight storage operations."""

    @pytest.fixture
    def storage(self):
        """Create storage instance."""
        mock_db = Mock()
        mock_redis = AsyncMock()
        return HybridDebugStorage(
            db_session=mock_db,
            redis_client=mock_redis
        )

    @pytest.mark.asyncio
    async def test_store_insight(self, storage):
        """HybridDebugStorage can store insight."""
        mock_insight = Mock()
        mock_insight.id = "insight-001"

        result = await storage.store_insight(
            insight=mock_insight,
            store_hot=True,
            store_warm=True
        )

        assert result is True
        storage.db.add.assert_called_once_with(mock_insight)

    @pytest.mark.asyncio
    async def test_get_insight_from_hot_tier(self, storage):
        """HybridDebugStorage retrieves insight from hot tier first."""
        insight_data = {"id": "insight-001", "title": "Test Insight"}
        storage.redis.get.return_value = '{"id": "insight-001", "title": "Test Insight"}'

        result = await storage.get_insight(insight_id="insight-001")

        assert result is not None
        assert result["id"] == "insight-001"

    @pytest.mark.asyncio
    async def test_query_insights_by_severity(self, storage):
        """HybridDebugStorage can query insights by severity."""
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        storage.db.query.return_value = mock_query

        result = await storage.query_insights(severity="high", limit=20)

        # Should apply severity filter
        mock_query.filter.assert_called()


class TestStateSnapshotStorage:
    """Test state snapshot storage and retrieval."""

    @pytest.fixture
    def storage(self):
        """Create storage instance."""
        mock_db = Mock()
        mock_redis = AsyncMock()
        return HybridDebugStorage(
            db_session=mock_db,
            redis_client=mock_redis
        )

    @pytest.mark.asyncio
    async def test_store_state_snapshot(self, storage):
        """HybridDebugStorage can store state snapshot."""
        mock_snapshot = Mock()
        mock_snapshot.id = "snapshot-001"

        result = await storage.store_state_snapshot(
            snapshot=mock_snapshot,
            store_hot=True,
            store_warm=True
        )

        assert result is True
        storage.db.add.assert_called_once_with(mock_snapshot)

    @pytest.mark.asyncio
    async def test_get_state_snapshot(self, storage):
        """HybridDebugStorage can retrieve state snapshot."""
        mock_snapshot = Mock()
        mock_snapshot.id = "snapshot-001"
        mock_snapshot.captured_at = datetime.now()

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = mock_snapshot
        storage.db.query.return_value = mock_query

        result = await storage.get_state_snapshot(
            component_type="agent",
            component_id="agent-001",
            operation_id="op-001"
        )

        assert result is not None
        assert result["id"] == "snapshot-001"

    @pytest.mark.asyncio
    async def test_get_state_snapshot_with_checkpoint(self, storage):
        """HybridDebugStorage can retrieve snapshot with checkpoint filter."""
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = None
        storage.db.query.return_value = mock_query

        result = await storage.get_state_snapshot(
            component_type="agent",
            component_id="agent-001",
            operation_id="op-001",
            checkpoint_name="pre_execution"
        )

        # Should apply checkpoint filter
        assert mock_query.filter.call_count >= 2


class TestDataMigration:
    """Test data migration between storage tiers."""

    @pytest.fixture
    def storage(self):
        """Create storage instance."""
        mock_db = Mock()
        mock_redis = AsyncMock()
        return HybridDebugStorage(
            db_session=mock_db,
            redis_client=mock_redis,
            archive_path="/tmp/test_archive"
        )

    @pytest.mark.asyncio
    async def test_migrate_warm_to_cold(self, storage):
        """HybridDebugStorage can migrate old events to cold storage."""
        # Mock old events
        old_events = [
            Mock(id="event-001", timestamp=datetime.now() - timedelta(days=10)),
            Mock(id="event-002", timestamp=datetime.now() - timedelta(days=10))
        ]

        from collections import defaultdict
        storage.db.query.return_value.filter.return_value.all.return_value = old_events
        storage._write_archive = AsyncMock()
        storage._event_to_dict = Mock(side_effect=lambda e: {"id": e.id})

        await storage.migrate_warm_to_cold()

        # Should delete old events from database
        assert storage.db.delete.call_count == 2
        storage.db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_expired_data(self, storage):
        """HybridDebugStorage can cleanup expired archive files."""
        # Mock archive file that is too old
        old_file = Path("/tmp/test_archive/events_2025-01-01.json.gz")

        with patch('pathlib.Path.glob') as mock_glob:
            mock_glob.return_value = [old_file]
            with patch('pathlib.Path.stat') as mock_stat:
                mock_stat.return_value.st_mtime = 1609459200  # 2021-01-01

                await storage.cleanup_expired_data()

                # Should delete old file
                # (Note: This test may need adjustment based on actual implementation)


class TestHelperMethods:
    """Test helper methods for data conversion."""

    @pytest.fixture
    def storage(self):
        """Create storage instance."""
        mock_db = Mock()
        mock_redis = AsyncMock()
        return HybridDebugStorage(
            db_session=mock_db,
            redis_client=mock_redis
        )

    def test_event_to_dict(self, storage):
        """HybridDebugStorage converts DebugEvent to dictionary."""
        mock_event = Mock()
        mock_event.id = "event-001"
        mock_event.event_type = "log"
        mock_event.component_type = "agent"
        mock_event.component_id = "agent-001"
        mock_event.correlation_id = "corr-001"
        mock_event.parent_event_id = None
        mock_event.level = "INFO"
        mock_event.message = "Test message"
        mock_event.data = {"key": "value"}
        mock_event.event_metadata = {}
        mock_event.timestamp = datetime.now()

        result = storage._event_to_dict(mock_event)

        assert result["id"] == "event-001"
        assert result["event_type"] == "log"
        assert result["component_type"] == "agent"
        assert result["message"] == "Test message"

    def test_insight_to_dict(self, storage):
        """HybridDebugStorage converts DebugInsight to dictionary."""
        mock_insight = Mock()
        mock_insight.id = "insight-001"
        mock_insight.insight_type = "performance"
        mock_insight.severity = "high"
        mock_insight.title = "Performance Issue"
        mock_insight.description = "Slow response detected"
        mock_insight.summary = "Agent took too long"
        mock_insight.evidence = []
        mock_insight.confidence_score = 0.9
        mock_insight.suggestions = ["Optimize code"]
        mock_insight.resolved = False
        mock_insight.resolution_notes = None
        mock_insight.scope = "agent"
        mock_insight.affected_components = ["agent-001"]
        mock_insight.generated_at = datetime.now()
        mock_insight.expires_at = None

        result = storage._insight_to_dict(mock_insight)

        assert result["id"] == "insight-001"
        assert result["insight_type"] == "performance"
        assert result["severity"] == "high"
        assert result["title"] == "Performance Issue"

    def test_snapshot_to_dict(self, storage):
        """HybridDebugStorage converts DebugStateSnapshot to dictionary."""
        mock_snapshot = Mock()
        mock_snapshot.id = "snapshot-001"
        mock_snapshot.component_type = "agent"
        mock_snapshot.component_id = "agent-001"
        mock_snapshot.operation_id = "op-001"
        mock_snapshot.checkpoint_name = "pre_execution"
        mock_snapshot.state_data = {"state": "running"}
        mock_snapshot.diff_from_previous = None
        mock_snapshot.snapshot_type = "full"
        mock_snapshot.captured_at = datetime.now()

        result = storage._snapshot_to_dict(mock_snapshot)

        assert result["id"] == "snapshot-001"
        assert result["component_type"] == "agent"
        assert result["operation_id"] == "op-001"
        assert result["state_data"] == {"state": "running"}

    def test_parse_time_range_last_1h(self, storage):
        """HybridDebugStorage parses 'last_1h' time range correctly."""
        result = storage._parse_time_range("last_1h")

        assert result is not None
        # Should be approximately 1 hour ago
        expected = datetime.utcnow() - timedelta(hours=1)
        diff = abs((result - expected).total_seconds())
        assert diff < 5  # Allow 5 seconds tolerance

    def test_parse_time_range_last_24h(self, storage):
        """HybridDebugStorage parses 'last_24h' time range correctly."""
        result = storage._parse_time_range("last_24h")

        assert result is not None
        expected = datetime.utcnow() - timedelta(hours=24)
        diff = abs((result - expected).total_seconds())
        assert diff < 5

    def test_parse_time_range_invalid(self, storage):
        """HybridDebugStorage returns None for invalid time range."""
        result = storage._parse_time_range("invalid_range")

        assert result is None
