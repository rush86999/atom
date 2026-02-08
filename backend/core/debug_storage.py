"""
Hybrid Storage Layer for AI Debug System

Provides multi-tier storage architecture:
- Redis: Hot storage (1-hour TTL) for frequently accessed data
- PostgreSQL: Warm storage (7-day retention) for recent data
- Archive: Cold storage (30+ day retention) for historical data

Features:
- Automatic tier management and data migration
- Sub-millisecond hot storage access
- Efficient archival to compressed JSON/LanceDB
"""

import asyncio
import gzip
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from redis import Redis
from redis.exceptions import RedisError

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugStateSnapshot,
    DebugMetric,
)
from core.structured_logger import StructuredLogger


# Configuration
DEBUG_REDIS_HOT_TTL_HOURS = int(os.getenv("DEBUG_REDIS_HOT_TTL_HOURS", "1"))
DEBUG_EVENT_RETENTION_HOURS = int(os.getenv("DEBUG_EVENT_RETENTION_HOURS", "168"))  # 7 days
DEBUG_INSIGHT_RETENTION_HOURS = int(os.getenv("DEBUG_INSIGHT_RETENTION_HOURS", "720"))  # 30 days
DEBUG_ARCHIVE_PATH = os.getenv("DEBUG_ARCHIVE_PATH", "./debug_archive")
DEBUG_REDIS_KEY_PREFIX = os.getenv("DEBUG_REDIS_KEY_PREFIX", "debug")


class HybridDebugStorage:
    """
    Hybrid storage layer for debug data.

    Manages data across Redis (hot), PostgreSQL (warm), and archive (cold).

    Example:
        storage = HybridDebugStorage(db_session, redis_client)

        # Store event in hot tier
        await storage.store_event(event_dict)

        # Retrieve event (checks hot, then warm, then cold)
        event = await storage.get_event(event_id)

        # Query events by criteria
        events = await storage.query_events(
            component_type="agent",
            component_id="agent-123",
            time_range="last_1h"
        )
    """

    def __init__(
        self,
        db_session: Session,
        redis_client: Redis,
        archive_path: str = DEBUG_ARCHIVE_PATH,
    ):
        """
        Initialize hybrid storage.

        Args:
            db_session: SQLAlchemy database session
            redis_client: Redis client for hot storage
            archive_path: Path to archive storage
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session
        self.redis = redis_client
        self.archive_path = Path(archive_path)

        # Create archive directory
        self.archive_path.mkdir(parents=True, exist_ok=True)

        # Redis key prefixes
        self._event_key_prefix = f"{DEBUG_REDIS_KEY_PREFIX}:event"
        self._insight_key_prefix = f"{DEBUG_REDIS_KEY_PREFIX}:insight"
        self._state_key_prefix = f"{DEBUG_REDIS_KEY_PREFIX}:state"
        self._metric_key_prefix = f"{DEBUG_REDIS_KEY_PREFIX}:metric"

    # ========================================================================
    # Event Storage
    # ========================================================================

    async def store_event(
        self,
        event: DebugEvent,
        store_hot: bool = True,
        store_warm: bool = True,
    ) -> bool:
        """
        Store debug event in hybrid storage.

        Args:
            event: DebugEvent object
            store_hot: Store in Redis hot tier
            store_warm: Store in PostgreSQL warm tier

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert event to dict
            event_dict = self._event_to_dict(event)

            # Store in Redis hot tier
            if store_hot and self.redis:
                await self._store_event_hot(event.id, event_dict)

            # Store in PostgreSQL warm tier
            if store_warm and self.db:
                self.db.add(event)
                self.db.commit()

            return True

        except Exception as e:
            self.logger.error(
                "Failed to store event",
                event_id=event.id,
                error=str(e),
            )
            return False

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve event from storage (checks hot, then warm).

        Args:
            event_id: Event ID

        Returns:
            Event dictionary or None
        """
        # Check hot tier first (Redis)
        event = await self._get_event_hot(event_id)
        if event:
            return event

        # Check warm tier (PostgreSQL)
        event = await self._get_event_warm(event_id)
        if event:
            # Promote to hot tier
            if self.redis:
                await self._store_event_hot(event_id, event)
            return event

        # Check cold tier (archive)
        event = await self._get_event_cold(event_id)
        return event

    async def query_events(
        self,
        component_type: Optional[str] = None,
        component_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        event_type: Optional[str] = None,
        level: Optional[str] = None,
        time_range: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Query events from storage.

        Args:
            component_type: Filter by component type
            component_id: Filter by component ID
            correlation_id: Filter by correlation ID
            event_type: Filter by event type
            level: Filter by log level
            time_range: Time range filter (last_1h, last_24h, last_7d)
            limit: Maximum number of results
            offset: Result offset for pagination

        Returns:
            List of event dictionaries
        """
        try:
            # Build query
            query = self.db.query(DebugEvent)

            # Apply filters
            if component_type:
                query = query.filter(DebugEvent.component_type == component_type)
            if component_id:
                query = query.filter(DebugEvent.component_id == component_id)
            if correlation_id:
                query = query.filter(DebugEvent.correlation_id == correlation_id)
            if event_type:
                query = query.filter(DebugEvent.event_type == event_type)
            if level:
                query = query.filter(DebugEvent.level == level)

            # Apply time range filter
            if time_range:
                time_filter = self._parse_time_range(time_range)
                if time_filter:
                    query = query.filter(DebugEvent.timestamp >= time_filter)

            # Order and paginate
            query = query.order_by(DebugEvent.timestamp.desc())
            query = query.limit(limit).offset(offset)

            # Execute query
            events = query.all()

            # Convert to dictionaries
            return [self._event_to_dict(event) for event in events]

        except Exception as e:
            self.logger.error(
                "Failed to query events",
                error=str(e),
            )
            return []

    # ========================================================================
    # Insight Storage
    # ========================================================================

    async def store_insight(
        self,
        insight: DebugInsight,
        store_hot: bool = True,
        store_warm: bool = True,
    ) -> bool:
        """Store insight in hybrid storage."""
        try:
            insight_dict = self._insight_to_dict(insight)

            if store_hot and self.redis:
                await self._store_insight_hot(insight.id, insight_dict)

            if store_warm and self.db:
                self.db.add(insight)
                self.db.commit()

            return True

        except Exception as e:
            self.logger.error(
                "Failed to store insight",
                insight_id=insight.id,
                error=str(e),
            )
            return False

    async def get_insight(self, insight_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve insight from storage."""
        # Check hot tier
        insight = await self._get_insight_hot(insight_id)
        if insight:
            return insight

        # Check warm tier
        insight = await self._get_insight_warm(insight_id)
        if insight:
            if self.redis:
                await self._store_insight_hot(insight_id, insight)
            return insight

        return None

    async def query_insights(
        self,
        insight_type: Optional[str] = None,
        severity: Optional[str] = None,
        scope: Optional[str] = None,
        resolved: Optional[bool] = None,
        time_range: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query insights from storage."""
        try:
            query = self.db.query(DebugInsight)

            if insight_type:
                query = query.filter(DebugInsight.insight_type == insight_type)
            if severity:
                query = query.filter(DebugInsight.severity == severity)
            if scope:
                query = query.filter(DebugInsight.scope == scope)
            if resolved is not None:
                query = query.filter(DebugInsight.resolved == resolved)

            if time_range:
                time_filter = self._parse_time_range(time_range)
                if time_filter:
                    query = query.filter(DebugInsight.generated_at >= time_filter)

            query = query.order_by(DebugInsight.generated_at.desc())
            query = query.limit(limit)

            insights = query.all()
            return [self._insight_to_dict(insight) for insight in insights]

        except Exception as e:
            self.logger.error("Failed to query insights", error=str(e))
            return []

    # ========================================================================
    # State Snapshot Storage
    # ========================================================================

    async def store_state_snapshot(
        self,
        snapshot: DebugStateSnapshot,
        store_hot: bool = True,
        store_warm: bool = True,
    ) -> bool:
        """Store state snapshot in hybrid storage."""
        try:
            snapshot_dict = self._snapshot_to_dict(snapshot)

            if store_hot and self.redis:
                await self._store_snapshot_hot(snapshot.id, snapshot_dict)

            if store_warm and self.db:
                self.db.add(snapshot)
                self.db.commit()

            return True

        except Exception as e:
            self.logger.error(
                "Failed to store state snapshot",
                snapshot_id=snapshot.id,
                error=str(e),
            )
            return False

    async def get_state_snapshot(
        self,
        component_type: str,
        component_id: str,
        operation_id: str,
        checkpoint_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve state snapshot from storage."""
        try:
            query = self.db.query(DebugStateSnapshot).filter(
                and_(
                    DebugStateSnapshot.component_type == component_type,
                    DebugStateSnapshot.component_id == component_id,
                    DebugStateSnapshot.operation_id == operation_id,
                )
            )

            if checkpoint_name:
                query = query.filter(DebugStateSnapshot.checkpoint_name == checkpoint_name)

            snapshot = query.order_by(DebugStateSnapshot.captured_at.desc()).first()

            if snapshot:
                return self._snapshot_to_dict(snapshot)

            return None

        except Exception as e:
            self.logger.error(
                "Failed to get state snapshot",
                component_type=component_type,
                component_id=component_id,
                error=str(e),
            )
            return None

    # ========================================================================
    # Data Migration and Archival
    # ========================================================================

    async def migrate_hot_to_warm(self):
        """Migrate data from Redis hot tier to PostgreSQL warm tier."""
        try:
            # This is typically handled by Redis TTL expiration
            # but can be triggered manually if needed
            pass

        except Exception as e:
            self.logger.error("Failed to migrate hot to warm", error=str(e))

    async def migrate_warm_to_cold(self):
        """Archive old data from PostgreSQL to compressed JSON files."""
        try:
            # Archive events older than retention period
            cutoff_time = datetime.utcnow() - timedelta(hours=DEBUG_EVENT_RETENTION_HOURS)

            old_events = self.db.query(DebugEvent).filter(
                DebugEvent.timestamp < cutoff_time
            ).all()

            if old_events:
                # Group by date for efficient archival
                events_by_date = defaultdict(list)
                for event in old_events:
                    date_key = event.timestamp.strftime("%Y-%m-%d")
                    events_by_date[date_key].append(self._event_to_dict(event))

                # Write compressed archives
                for date_key, events in events_by_date.items():
                    archive_file = self.archive_path / f"events_{date_key}.json.gz"
                    await self._write_archive(archive_file, events)

                # Delete from database
                for event in old_events:
                    self.db.delete(event)
                self.db.commit()

                self.logger.info(
                    "Archived debug events",
                    count=len(old_events),
                )

        except Exception as e:
            self.logger.error("Failed to migrate warm to cold", error=str(e))
            self.db.rollback()

    async def cleanup_expired_data(self):
        """Clean up expired data from all tiers."""
        try:
            # Redis handles hot tier cleanup via TTL

            # Clean up old archived files
            archive_cutoff = datetime.utcnow() - timedelta(days=90)
            for archive_file in self.archive_path.glob("*.json.gz"):
                file_mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
                if file_mtime < archive_cutoff:
                    archive_file.unlink()
                    self.logger.info(f"Deleted old archive: {archive_file}")

        except Exception as e:
            self.logger.error("Failed to cleanup expired data", error=str(e))

    # ========================================================================
    # Hot Tier (Redis) Operations
    # ========================================================================

    async def _store_event_hot(self, event_id: str, event_dict: Dict[str, Any]):
        """Store event in Redis hot tier."""
        try:
            key = f"{self._event_key_prefix}:{event_id}"
            self.redis.setex(
                key,
                DEBUG_REDIS_HOT_TTL_HOURS * 3600,  # Convert hours to seconds
                json.dumps(event_dict),
            )
        except RedisError as e:
            self.logger.error("Failed to store event in Redis", error=str(e))

    async def _get_event_hot(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event from Redis hot tier."""
        try:
            key = f"{self._event_key_prefix}:{event_id}"
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except RedisError as e:
            self.logger.error("Failed to get event from Redis", error=str(e))
        return None

    async def _store_insight_hot(self, insight_id: str, insight_dict: Dict[str, Any]):
        """Store insight in Redis hot tier."""
        try:
            key = f"{self._insight_key_prefix}:{insight_id}"
            self.redis.setex(
                key,
                DEBUG_REDIS_HOT_TTL_HOURS * 3600,
                json.dumps(insight_dict),
            )
        except RedisError as e:
            self.logger.error("Failed to store insight in Redis", error=str(e))

    async def _get_insight_hot(self, insight_id: str) -> Optional[Dict[str, Any]]:
        """Get insight from Redis hot tier."""
        try:
            key = f"{self._insight_key_prefix}:{insight_id}"
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except RedisError as e:
            self.logger.error("Failed to get insight from Redis", error=str(e))
        return None

    async def _store_snapshot_hot(self, snapshot_id: str, snapshot_dict: Dict[str, Any]):
        """Store snapshot in Redis hot tier."""
        try:
            key = f"{self._state_key_prefix}:{snapshot_id}"
            self.redis.setex(
                key,
                DEBUG_REDIS_HOT_TTL_HOURS * 3600,
                json.dumps(snapshot_dict),
            )
        except RedisError as e:
            self.logger.error("Failed to store snapshot in Redis", error=str(e))

    # ========================================================================
    # Warm Tier (PostgreSQL) Operations
    # ========================================================================

    async def _get_event_warm(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event from PostgreSQL warm tier."""
        try:
            event = self.db.query(DebugEvent).filter(DebugEvent.id == event_id).first()
            if event:
                return self._event_to_dict(event)
        except Exception as e:
            self.logger.error("Failed to get event from PostgreSQL", error=str(e))
        return None

    async def _get_insight_warm(self, insight_id: str) -> Optional[Dict[str, Any]]:
        """Get insight from PostgreSQL warm tier."""
        try:
            insight = self.db.query(DebugInsight).filter(DebugInsight.id == insight_id).first()
            if insight:
                return self._insight_to_dict(insight)
        except Exception as e:
            self.logger.error("Failed to get insight from PostgreSQL", error=str(e))
        return None

    # ========================================================================
    # Cold Tier (Archive) Operations
    # ========================================================================

    async def _get_event_cold(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event from archive storage."""
        try:
            # Search through archive files
            for archive_file in self.archive_path.glob("events_*.json.gz"):
                events = await self._read_archive(archive_file)
                for event in events:
                    if event.get("id") == event_id:
                        return event
        except Exception as e:
            self.logger.error("Failed to get event from archive", error=str(e))
        return None

    async def _write_archive(self, file_path: Path, data: List[Dict[str, Any]]):
        """Write data to compressed archive file."""
        try:
            json_data = json.dumps(data)
            with gzip.open(file_path, "wt", encoding="utf-8") as f:
                f.write(json_data)
        except Exception as e:
            self.logger.error("Failed to write archive", file_path=str(file_path), error=str(e))

    async def _read_archive(self, file_path: Path) -> List[Dict[str, Any]]:
        """Read data from compressed archive file."""
        try:
            with gzip.open(file_path, "rt", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error("Failed to read archive", file_path=str(file_path), error=str(e))
            return []

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _event_to_dict(self, event: DebugEvent) -> Dict[str, Any]:
        """Convert DebugEvent to dictionary."""
        return {
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

    def _insight_to_dict(self, insight: DebugInsight) -> Dict[str, Any]:
        """Convert DebugInsight to dictionary."""
        return {
            "id": insight.id,
            "insight_type": insight.insight_type,
            "severity": insight.severity,
            "title": insight.title,
            "description": insight.description,
            "summary": insight.summary,
            "evidence": insight.evidence,
            "confidence_score": insight.confidence_score,
            "suggestions": insight.suggestions,
            "resolved": insight.resolved,
            "resolution_notes": insight.resolution_notes,
            "scope": insight.scope,
            "affected_components": insight.affected_components,
            "generated_at": insight.generated_at.isoformat() if insight.generated_at else None,
            "expires_at": insight.expires_at.isoformat() if insight.expires_at else None,
        }

    def _snapshot_to_dict(self, snapshot: DebugStateSnapshot) -> Dict[str, Any]:
        """Convert DebugStateSnapshot to dictionary."""
        return {
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

    def _parse_time_range(self, time_range: str) -> Optional[datetime]:
        """Parse time range string to datetime."""
        now = datetime.utcnow()

        if time_range == "last_1h":
            return now - timedelta(hours=1)
        elif time_range == "last_24h":
            return now - timedelta(hours=24)
        elif time_range == "last_7d":
            return now - timedelta(days=7)
        elif time_range == "last_30d":
            return now - timedelta(days=30)
        else:
            return None
