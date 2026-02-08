"""
Tests for Debug Collector Service

Tests cover:
- Event collection and batching
- State snapshot collection
- Batch operations
- Correlation tracking
- Redis pub/sub integration
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import DebugEvent, DebugStateSnapshot, Base
from core.debug_collector import DebugCollector
from core.structured_logger import StructuredLogger


@pytest.fixture
def test_db():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")

    # Create only debug tables
    debug_tables = [
        DebugEvent.__table__,
        DebugStateSnapshot.__table__,
    ]

    for table in debug_tables:
        table.create(bind=engine, checkfirst=True)

    TestingSessionLocal = sessionmaker(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        for table in reversed(debug_tables):
            table.drop(bind=engine, checkfirst=True)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = Mock()
    redis.publish = Mock()
    return redis


@pytest.fixture
def collector(test_db, mock_redis):
    """Create debug collector for testing."""
    collector_instance = DebugCollector(
        db_session=test_db,
        redis_client=mock_redis,
        batch_size_ms=100,
    )
    # Don't start the background task for tests
    collector_instance._running = True
    yield collector_instance
    collector_instance._running = False


class TestDebugCollector:
    """Tests for DebugCollector service."""

    @pytest.mark.asyncio
    async def test_collect_log_event(self, collector):
        """Test collecting a log event."""
        event = await collector.collect_event(
            event_type="log",
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-456",
            level="INFO",
            message="Agent started",
            data={"timestamp": "2026-02-06T10:00:00Z"},
        )

        assert event is not None
        assert event.event_type == "log"
        assert event.component_type == "agent"
        assert event.component_id == "agent-123"
        assert event.correlation_id == "corr-456"
        assert event.level == "INFO"

    @pytest.mark.asyncio
    async def test_collect_error_event(self, collector):
        """Test collecting an error event."""
        event = await collector.collect_event(
            event_type="error",
            component_type="browser",
            component_id="browser-789",
            correlation_id="corr-123",
            level="ERROR",
            message="Connection failed",
            data={"error": "Timeout"},
        )

        assert event is not None
        assert event.event_type == "error"
        assert event.level == "ERROR"

    @pytest.mark.asyncio
    async def test_collect_event_with_parent(self, collector):
        """Test collecting event with parent event ID."""
        parent = await collector.collect_event(
            event_type="log",
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-456",
            level="INFO",
            message="Parent event",
        )

        child = await collector.collect_event(
            event_type="log",
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-456",
            parent_event_id=parent.id,
            level="INFO",
            message="Child event",
        )

        assert child.parent_event_id == parent.id

    @pytest.mark.asyncio
    async def test_collect_state_snapshot(self, collector):
        """Test collecting state snapshot."""
        snapshot = await collector.collect_state_snapshot(
            component_type="agent",
            component_id="agent-123",
            operation_id="op-456",
            state_data={"status": "running", "progress": 0.5},
            checkpoint_name="checkpoint_1",
            snapshot_type="full",
        )

        assert snapshot is not None
        assert snapshot.component_type == "agent"
        assert snapshot.component_id == "agent-123"
        assert snapshot.operation_id == "op-456"
        assert snapshot.snapshot_type == "full"

    @pytest.mark.asyncio
    async def test_collect_incremental_snapshot_with_diff(self, collector):
        """Test collecting incremental snapshot with diff."""
        snapshot = await collector.collect_state_snapshot(
            component_type="workflow",
            component_id="workflow-789",
            operation_id="op-123",
            state_data={"step": 2},
            snapshot_type="incremental",
            diff_from_previous={"step": {"from": 1, "to": 2}},
        )

        assert snapshot.snapshot_type == "incremental"
        assert snapshot.diff_from_previous is not None

    @pytest.mark.asyncio
    async def test_collect_batch_events(self, collector):
        """Test collecting multiple events in batch."""
        events_data = [
            {
                "event_type": "log",
                "component_type": "agent",
                "component_id": "agent-1",
                "correlation_id": "corr-1",
                "level": "INFO",
                "message": "Event 1",
            },
            {
                "event_type": "log",
                "component_type": "agent",
                "component_id": "agent-2",
                "correlation_id": "corr-2",
                "level": "INFO",
                "message": "Event 2",
            },
            {
                "event_type": "error",
                "component_type": "browser",
                "component_id": "browser-1",
                "correlation_id": "corr-3",
                "level": "ERROR",
                "message": "Error 1",
            },
        ]

        events = await collector.collect_batch_events(events_data)

        assert len(events) == 3
        assert all(e is not None for e in events)
        assert events[0].message == "Event 1"
        assert events[1].message == "Event 2"
        assert events[2].message == "Error 1"

    @pytest.mark.asyncio
    async def test_event_batching(self, collector, test_db):
        """Test event batching and flushing."""
        # Collect multiple events
        for i in range(5):
            await collector.collect_event(
                event_type="log",
                component_type="agent",
                component_id="agent-123",
                correlation_id=f"corr-{i}",
                level="INFO",
                message=f"Event {i}",
            )

        # Flush batches
        await collector._flush_batches()

        # Verify events are in database
        events = test_db.query(DebugEvent).filter(
            DebugEvent.component_id == "agent-123"
        ).all()

        assert len(events) == 5

    @pytest.mark.asyncio
    async def test_correlated_operation_context_manager(self, collector):
        """Test correlated operation context manager."""
        async with collector.correlated_operation(
            component_type="agent",
            component_id="agent-123"
        ) as correlation_id:
            # Collect events within the operation
            event1 = await collector.collect_event(
                event_type="log",
                component_type="agent",
                component_id="agent-123",
                correlation_id=correlation_id,
                level="INFO",
                message="Step 1",
            )

            event2 = await collector.collect_event(
                event_type="log",
                component_type="agent",
                component_id="agent-123",
                correlation_id=correlation_id,
                level="INFO",
                message="Step 2",
            )

            # Verify both events share correlation ID
            assert event1.correlation_id == event2.correlation_id

    @pytest.mark.asyncio
    async def test_redis_pubsub_on_event_collection(self, collector, mock_redis):
        """Test that events are published to Redis."""
        await collector.collect_event(
            event_type="log",
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-456",
            level="INFO",
            message="Test event",
        )

        # Verify Redis publish was called
        assert mock_redis.publish.called

    @pytest.mark.asyncio
    async def test_redis_pubsub_on_snapshot_collection(self, collector, mock_redis):
        """Test that snapshots are published to Redis."""
        await collector.collect_state_snapshot(
            component_type="agent",
            component_id="agent-123",
            operation_id="op-456",
            state_data={"status": "running"},
        )

        # Verify Redis publish was called
        assert mock_redis.publish.called

    def test_get_buffer_stats(self, collector):
        """Test getting buffer statistics."""
        stats = collector.get_buffer_stats()

        assert "event_buffer_size" in stats
        assert "state_buffer_size" in stats
        assert "running" in stats
        assert stats["running"] is True

    @pytest.mark.asyncio
    async def test_collector_start_stop(self, test_db, mock_redis):
        """Test starting and stopping collector."""
        collector = DebugCollector(
            db_session=test_db,
            redis_client=mock_redis,
        )

        assert collector._running is False

        collector.start()
        assert collector._running is True

        collector.stop()
        assert collector._running is False

    @pytest.mark.asyncio
    async def test_collect_event_when_disabled(self, test_db, mock_redis):
        """Test event collection when debug system is disabled."""
        with patch("core.debug_collector.DEBUG_SYSTEM_ENABLED", False):
            collector = DebugCollector(
                db_session=test_db,
                redis_client=mock_redis,
            )
            collector.start()

            event = await collector.collect_event(
                event_type="log",
                component_type="agent",
                component_id="agent-123",
                correlation_id="corr-456",
                level="INFO",
                message="Test event",
            )

            # Event should not be collected
            assert event is None

            collector.stop()

    @pytest.mark.asyncio
    async def test_collect_state_snapshot_when_disabled(self, test_db, mock_redis):
        """Test state snapshot collection when disabled."""
        with patch("core.debug_collector.DEBUG_SYSTEM_ENABLED", False):
            collector = DebugCollector(
                db_session=test_db,
                redis_client=mock_redis,
            )
            collector.start()

            snapshot = await collector.collect_state_snapshot(
                component_type="agent",
                component_id="agent-123",
                operation_id="op-456",
                state_data={"status": "running"},
            )

            # Snapshot should not be collected
            assert snapshot is None

            collector.stop()


class TestDebugCollectorIntegration:
    """Integration tests for DebugCollector."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, collector, test_db):
        """Test full event collection workflow."""
        # Collect events
        for i in range(10):
            await collector.collect_event(
                event_type="log",
                component_type="agent",
                component_id="agent-123",
                correlation_id="corr-workflow",
                level="INFO",
                message=f"Step {i}",
            )

        # Collect state snapshots
        await collector.collect_state_snapshot(
            component_type="agent",
            component_id="agent-123",
            operation_id="op-workflow",
            state_data={"step": 5, "status": "running"},
            checkpoint_name="midpoint",
        )

        # Flush batches
        await collector._flush_batches()

        # Verify data in database
        events = (
            test_db.query(DebugEvent)
            .filter(DebugEvent.correlation_id == "corr-workflow")
            .all()
        )
        assert len(events) == 10

        snapshots = (
            test_db.query(DebugStateSnapshot)
            .filter(DebugStateSnapshot.operation_id == "op-workflow")
            .all()
        )
        assert len(snapshots) == 1
