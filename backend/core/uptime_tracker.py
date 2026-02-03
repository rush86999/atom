"""
Uptime Tracking System

Provides comprehensive uptime monitoring with:
- Service start time tracking
- Health checks (database, cache, external services)
- Downtime event logging
- Uptime percentage calculation
- Performance metrics

Usage:
    from core.uptime_tracker import UptimeTracker, get_uptime_tracker

    tracker = get_uptime_tracker()
    metrics = tracker.check_health()
    print(f"Uptime: {metrics.uptime_percentage:.2f}%")
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from core.database import get_db_session

logger = logging.getLogger(__name__)


@dataclass
class UptimeMetrics:
    """Uptime metrics data class"""

    # Timing
    start_time: datetime
    current_time: datetime
    uptime_seconds: float
    uptime_formatted: str

    # Percentage
    uptime_percentage: float
    downtime_percentage: float

    # Counts
    total_downtime_events: int
    total_downtime_seconds: float

    # Health status
    database_healthy: bool
    database_response_time_ms: Optional[float] = None

    # Additional metrics
    additional_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "start_time": self.start_time.isoformat(),
            "current_time": self.current_time.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "uptime_formatted": self.uptime_formatted,
            "uptime_percentage": round(self.uptime_percentage, 2),
            "downtime_percentage": round(self.downtime_percentage, 2),
            "total_downtime_events": self.total_downtime_events,
            "total_downtime_seconds": round(self.total_downtime_seconds, 2),
            "database_healthy": self.database_healthy,
            "database_response_time_ms": self.database_response_time_ms,
            **self.additional_metrics,
        }


@dataclass
class DowntimeEvent:
    """Record of a downtime event"""

    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: float
    reason: str
    affected_components: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "reason": self.reason,
            "affected_components": self.affected_components,
        }


class UptimeTracker:
    """
    Tracks system uptime and health metrics.

    Features:
    - Tracks service start time
    - Monitors database connectivity
    - Logs downtime events
    - Calculates uptime percentage
    - Provides health check endpoints
    """

    def __init__(self, start_time: Optional[datetime] = None):
        """
        Initialize uptime tracker.

        Args:
            start_time: Service start time (defaults to now)
        """
        self.start_time = start_time or datetime.utcnow()
        self.downtime_events: List[DowntimeEvent] = []
        self.current_downtime_start: Optional[datetime] = None
        self._last_health_check: Optional[datetime] = None

        logger.info(f"UPTIME_TRACKER: Initialized at {self.start_time.isoformat()}")

    def check_health(self, db: Optional[Session] = None) -> UptimeMetrics:
        """
        Perform comprehensive health check.

        Args:
            db: Database session (creates new one if None)

        Returns:
            UptimeMetrics object with current health status
        """
        current_time = datetime.utcnow()
        self._last_health_check = current_time

        # Calculate uptime
        uptime_seconds = (current_time - self.start_time).total_seconds()
        total_downtime_seconds = sum(e.duration_seconds for e in self.downtime_events)

        # Calculate percentages
        total_time = uptime_seconds + total_downtime_seconds
        if total_time > 0:
            uptime_percentage = (uptime_seconds / total_time) * 100
            downtime_percentage = (total_downtime_seconds / total_time) * 100
        else:
            uptime_percentage = 100.0
            downtime_percentage = 0.0

        # Check database health
        db_healthy, db_response_time = self._check_database_health(db)

        # Format uptime
        uptime_formatted = self._format_duration(uptime_seconds)

        metrics = UptimeMetrics(
            start_time=self.start_time,
            current_time=current_time,
            uptime_seconds=uptime_seconds,
            uptime_formatted=uptime_formatted,
            uptime_percentage=uptime_percentage,
            downtime_percentage=downtime_percentage,
            total_downtime_events=len(self.downtime_events),
            total_downtime_seconds=total_downtime_seconds,
            database_healthy=db_healthy,
            database_response_time_ms=db_response_time,
        )

        logger.debug(
            f"Health check: uptime={uptime_percentage:.2f}%, "
            f"db_healthy={db_healthy}, "
            f"downtime_events={len(self.downtime_events)}"
        )

        return metrics

    def _check_database_health(
        self, db: Optional[Session] = None
    ) -> tuple[bool, Optional[float]]:
        """
        Check database connectivity and performance.

        Args:
            db: Database session (creates new one if None)

        Returns:
            Tuple of (is_healthy, response_time_ms)
        """
        close_db = False
        if db is None:
            with get_db_session() as db:
            close_db = True

        try:
            # Measure response time
            start = time.time()

            # Simple query to check connectivity
            result = db.execute(text("SELECT 1")).scalar()

            response_time = (time.time() - start) * 1000  # Convert to ms

            if result == 1:
                return True, response_time
            else:
                return False, response_time

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False, None

        finally:
            if close_db:
                db.close()

    def record_downtime_start(
        self, reason: str, affected_components: List[str] = None
    ) -> None:
        """
        Record the start of a downtime event.

        Args:
            reason: Description of the downtime cause
            affected_components: List of components affected (e.g., ["database", "api"])
        """
        if self.current_downtime_start is not None:
            logger.warning("Downtime already in progress, ignoring start event")
            return

        self.current_downtime_start = datetime.utcnow()
        logger.error(
            f"DOWNTIME STARTED: {reason} at {self.current_downtime_start.isoformat()}, "
            f"components: {affected_components or ['unknown']}"
        )

    def record_downtime_end(self) -> None:
        """
        Record the end of a downtime event.

        Automatically calculates duration and creates event log.
        """
        if self.current_downtime_start is None:
            logger.warning("No downtime in progress, ignoring end event")
            return

        end_time = datetime.utcnow()
        duration = (end_time - self.current_downtime_start).total_seconds()

        # Create downtime event
        event = DowntimeEvent(
            start_time=self.current_downtime_start,
            end_time=end_time,
            duration_seconds=duration,
            reason="Downtime event",
            affected_components=[],
        )

        self.downtime_events.append(event)
        self.current_downtime_start = None

        logger.error(
            f"DOWNTIME ENDED: Duration {duration:.2f}s, "
            f"from {event.start_time.isoformat()} to {end_time.isoformat()}"
        )

    def get_recent_downtime_events(
        self, limit: int = 10
    ) -> List[DowntimeEvent]:
        """
        Get recent downtime events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent DowntimeEvents, sorted by start time (newest first)
        """
        return sorted(
            self.downtime_events,
            key=lambda e: e.start_time,
            reverse=True
        )[:limit]

    def get_downtime_events_in_range(
        self, start: datetime, end: datetime
    ) -> List[DowntimeEvent]:
        """
        Get downtime events within a time range.

        Args:
            start: Start of time range
            end: End of time range

        Returns:
            List of DowntimeEvents within the range
        """
        return [
            e
            for e in self.downtime_events
            if start <= e.start_time <= end
        ]

    def _format_duration(self, seconds: float) -> str:
        """
        Format duration in human-readable format.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string (e.g., "2d 5h 30m 15s")
        """
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")

        return " ".join(parts)


# Global uptime tracker instance
_uptime_tracker: Optional[UptimeTracker] = None


def get_uptime_tracker() -> UptimeTracker:
    """Get or create global uptime tracker instance"""
    global _uptime_tracker
    if _uptime_tracker is None:
        _uptime_tracker = UptimeTracker()
    return _uptime_tracker


def check_uptime() -> Dict[str, Any]:
    """
    Convenience function to check uptime and return dict.

    Usage in API endpoints:
        @router.get("/health")
        async def health_check():
            return check_uptime()
    """
    tracker = get_uptime_tracker()
    metrics = tracker.check_health()
    return metrics.to_dict()
