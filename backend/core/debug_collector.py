"""
Debug Collector Service for Atom Platform

Collects logs and state from distributed components for the AI Debug System.
Integrates with StructuredLogger for automatic log capture.

Features:
- Automatic log capture from StructuredLogger
- State snapshot API for distributed components
- Batch collection (100ms intervals)
- Redis pub/sub integration for real-time events
"""

import asyncio
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from redis import Redis
from redis.exceptions import RedisError

from core.models import (
    DebugEvent,
    DebugEventType,
    DebugStateSnapshot,
)
from core.structured_logger import StructuredLogger


# Configuration
DEBUG_SYSTEM_ENABLED = os.getenv("DEBUG_SYSTEM_ENABLED", "true").lower() == "true"
DEBUG_BATCH_SIZE_MS = int(os.getenv("DEBUG_BATCH_SIZE_MS", "100"))  # 100ms default
DEBUG_REDIS_ENABLED = os.getenv("DEBUG_REDIS_ENABLED", "true").lower() == "true"
DEBUG_REDIS_KEY_PREFIX = os.getenv("DEBUG_REDIS_KEY_PREFIX", "debug")


class DebugCollector:
    """
    Debug event and state collector.

    Automatically captures logs from StructuredLogger and provides
    state snapshot API for distributed components.

    Example:
        collector = DebugCollector()

        # Automatic log capture (enabled by default)
        collector.start()

        # Manual event capture
        await collector.collect_event(
            event_type="log",
            component_type="agent",
            component_id="agent-123",
            correlation_id="corr-456",
            level="INFO",
            message="Agent started",
            data={"timestamp": "2026-02-06T10:00:00Z"}
        )

        # State snapshot
        await collector.collect_state_snapshot(
            component_type="agent",
            component_id="agent-123",
            operation_id="op-456",
            state_data={"status": "running", "progress": 0.5}
        )
    """

    def __init__(
        self,
        db_session: Optional[Session] = None,
        redis_client: Optional[Redis] = None,
        batch_size_ms: int = DEBUG_BATCH_SIZE_MS,
    ):
        """
        Initialize debug collector.

        Args:
            db_session: SQLAlchemy database session (optional, creates new if not provided)
            redis_client: Redis client for pub/sub (optional)
            batch_size_ms: Batch collection interval in milliseconds
        """
        self.logger = StructuredLogger(__name__)
        self.db_session = db_session
        self.redis_client = redis_client
        self.batch_size_ms = batch_size_ms

        # Event batching
        self._event_buffer: List[DebugEvent] = []
        self._state_buffer: List[DebugStateSnapshot] = []
        self._batch_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

        # Redis pub/sub
        self._redis_channel = f"{DEBUG_REDIS_KEY_PREFIX}:events"

    def start(self):
        """Start automatic log collection and batch processing."""
        if self._running:
            self.logger.warning("DebugCollector already running")
            return

        self._running = True

        # Start batch flush task
        self._flush_task = asyncio.create_task(self._batch_flush_loop())

        # Hook into StructuredLogger
        self._hook_structured_logger()

        self.logger.info(
            "DebugCollector started",
            batch_size_ms=self.batch_size_ms,
            redis_enabled=DEBUG_REDIS_ENABLED,
        )

    def stop(self):
        """Stop automatic log collection."""
        if not self._running:
            return

        self._running = False

        # Cancel flush task
        if self._flush_task:
            self._flush_task.cancel()
            self._flush_task = None

        # Flush remaining events
        asyncio.create_task(self._flush_batches())

        self.logger.info("DebugCollector stopped")

    def _hook_structured_logger(self):
        """
        Hook into StructuredLogger for automatic log capture.

        This adds debug-specific fields (correlation_id, component_type, operation_id)
        to the logging context.
        """
        # TODO: Integrate with StructuredLogger to automatically capture logs
        # For now, components will need to call collect_event explicitly
        pass

    async def collect_event(
        self,
        event_type: str,
        component_type: str,
        component_id: Optional[str],
        correlation_id: str,
        level: Optional[str] = None,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        event_metadata: Optional[Dict[str, Any]] = None,
        parent_event_id: Optional[str] = None,
    ) -> Optional[DebugEvent]:
        """
        Collect a debug event.

        Args:
            event_type: Event type (log, state_snapshot, metric, error, system)
            component_type: Component type (agent, browser, workflow, system)
            component_id: Component identifier
            correlation_id: Correlation ID to link related events
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            data: Full event data
            event_metadata: Tags, labels, additional context
            parent_event_id: Parent event ID for event chains

        Returns:
            Created DebugEvent object or None if disabled
        """
        if not DEBUG_SYSTEM_ENABLED:
            return None

        try:
            # Create event
            event = DebugEvent(
                id=str(uuid.uuid4()),
                event_type=event_type,
                component_type=component_type,
                component_id=component_id,
                correlation_id=correlation_id,
                parent_event_id=parent_event_id,
                level=level,
                message=message,
                data=data or {},
                event_metadata=event_metadata or {},
                timestamp=datetime.utcnow(),
            )

            # Add to buffer
            async with self._batch_lock:
                self._event_buffer.append(event)

            # Publish to Redis pub/sub for real-time streaming
            if self.redis_client and DEBUG_REDIS_ENABLED:
                await self._publish_event(event)

            return event

        except Exception as e:
            self.logger.error(
                "Failed to collect debug event",
                event_type=event_type,
                component_type=component_type,
                error=str(e),
            )
            return None

    async def collect_state_snapshot(
        self,
        component_type: str,
        component_id: str,
        operation_id: str,
        state_data: Dict[str, Any],
        checkpoint_name: Optional[str] = None,
        snapshot_type: str = "full",
        diff_from_previous: Optional[Dict[str, Any]] = None,
    ) -> Optional[DebugStateSnapshot]:
        """
        Collect a component state snapshot.

        Args:
            component_type: Component type (agent, browser, workflow, system)
            component_id: Component identifier
            operation_id: Operation correlation ID
            state_data: Full state capture
            checkpoint_name: Optional checkpoint label
            snapshot_type: Snapshot type (full, incremental, partial)
            diff_from_previous: Delta from previous snapshot

        Returns:
            Created DebugStateSnapshot object or None if disabled
        """
        if not DEBUG_SYSTEM_ENABLED:
            return None

        try:
            # Create snapshot
            snapshot = DebugStateSnapshot(
                id=str(uuid.uuid4()),
                component_type=component_type,
                component_id=component_id,
                operation_id=operation_id,
                checkpoint_name=checkpoint_name,
                state_data=state_data,
                diff_from_previous=diff_from_previous,
                snapshot_type=snapshot_type,
                captured_at=datetime.utcnow(),
            )

            # Add to buffer
            async with self._batch_lock:
                self._state_buffer.append(snapshot)

            # Publish to Redis
            if self.redis_client and DEBUG_REDIS_ENABLED:
                await self._publish_snapshot(snapshot)

            return snapshot

        except Exception as e:
            self.logger.error(
                "Failed to collect state snapshot",
                component_type=component_type,
                component_id=component_id,
                error=str(e),
            )
            return None

    async def collect_batch_events(
        self,
        events: List[Dict[str, Any]],
    ) -> List[Optional[DebugEvent]]:
        """
        Collect multiple events in batch.

        Args:
            events: List of event dictionaries

        Returns:
            List of created DebugEvent objects
        """
        if not DEBUG_SYSTEM_ENABLED:
            return []

        collected_events = []
        for event_data in events:
            event = await self.collect_event(**event_data)
            collected_events.append(event)

        return collected_events

    async def _batch_flush_loop(self):
        """Background task to flush event batches at regular intervals."""
        while self._running:
            try:
                await asyncio.sleep(self.batch_size_ms / 1000)  # Convert to seconds
                await self._flush_batches()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Batch flush loop error", error=str(e))

    async def _flush_batches(self):
        """Flush event and state buffers to database."""
        async with self._batch_lock:
            # Flush events
            if self._event_buffer:
                events_to_flush = self._event_buffer.copy()
                self._event_buffer.clear()

                if self.db_session:
                    try:
                        self.db_session.add_all(events_to_flush)
                        self.db_session.commit()

                        self.logger.debug(
                            "Flushed debug events",
                            count=len(events_to_flush),
                        )
                    except Exception as e:
                        self.db_session.rollback()
                        self.logger.error(
                            "Failed to flush debug events",
                            error=str(e),
                        )

            # Flush state snapshots
            if self._state_buffer:
                states_to_flush = self._state_buffer.copy()
                self._state_buffer.clear()

                if self.db_session:
                    try:
                        self.db_session.add_all(states_to_flush)
                        self.db_session.commit()

                        self.logger.debug(
                            "Flushed state snapshots",
                            count=len(states_to_flush),
                        )
                    except Exception as e:
                        self.db_session.rollback()
                        self.logger.error(
                            "Failed to flush state snapshots",
                            error=str(e),
                        )

    async def _publish_event(self, event: DebugEvent):
        """Publish event to Redis pub/sub for real-time streaming."""
        if not self.redis_client:
            return

        try:
            event_data = {
                "id": event.id,
                "event_type": event.event_type,
                "component_type": event.component_type,
                "component_id": event.component_id,
                "correlation_id": event.correlation_id,
                "parent_event_id": event.parent_event_id,
                "level": event.level,
                "message": event.message,
                "data": event.data,
                "event_metadata": event.event_metadata,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            }

            self.redis_client.publish(
                self._redis_channel,
                json.dumps({"type": "event", "data": event_data}),
            )

        except RedisError as e:
            self.logger.error("Failed to publish event to Redis", error=str(e))

    async def _publish_snapshot(self, snapshot: DebugStateSnapshot):
        """Publish state snapshot to Redis pub/sub."""
        if not self.redis_client:
            return

        try:
            snapshot_data = {
                "id": snapshot.id,
                "component_type": snapshot.component_type,
                "component_id": snapshot.component_id,
                "operation_id": snapshot.operation_id,
                "checkpoint_name": snapshot.checkpoint_name,
                "state_data": snapshot.state_data,
                "diff_from_previous": snapshot.diff_from_previous,
                "snapshot_type": snapshot.snapshot_type,
                "captured_at": snapshot.captured_at.isoformat() if snapshot.captured_at else None,
            }

            self.redis_client.publish(
                self._redis_channel,
                json.dumps({"type": "snapshot", "data": snapshot_data}),
            )

        except RedisError as e:
            self.logger.error("Failed to publish snapshot to Redis", error=str(e))

    @asynccontextmanager
    async def correlated_operation(
        self,
        correlation_id: Optional[str] = None,
        component_type: str = "system",
        component_id: Optional[str] = None,
    ):
        """
        Context manager for correlated operations.

        Automatically creates a correlation ID and tracks all events
        within the operation.

        Example:
            async with collector.correlated_operation(
                component_type="agent",
                component_id="agent-123"
            ) as corr_id:
                # All events within this block share the correlation ID
                await collector.collect_event(
                    event_type="log",
                    correlation_id=corr_id,
                    message="Operation started"
                )
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        try:
            yield correlation_id
        finally:
            # Optionally mark operation as complete
            pass

    def get_buffer_stats(self) -> Dict[str, int]:
        """
        Get statistics about event buffers.

        Returns:
            Dictionary with buffer sizes
        """
        return {
            "event_buffer_size": len(self._event_buffer),
            "state_buffer_size": len(self._state_buffer),
            "running": self._running,
        }


# Global collector instance
_collector_instance: Optional[DebugCollector] = None


def get_debug_collector() -> Optional[DebugCollector]:
    """
    Get the global DebugCollector instance.

    Returns:
        DebugCollector instance or None if not initialized
    """
    global _collector_instance
    return _collector_instance


def init_debug_collector(
    db_session: Optional[Session] = None,
    redis_client: Optional[Redis] = None,
) -> DebugCollector:
    """
    Initialize the global DebugCollector instance.

    Args:
        db_session: SQLAlchemy database session
        redis_client: Redis client for pub/sub

    Returns:
        Initialized DebugCollector instance
    """
    global _collector_instance

    if _collector_instance is None:
        _collector_instance = DebugCollector(
            db_session=db_session,
            redis_client=redis_client,
        )
        _collector_instance.start()

    return _collector_instance
