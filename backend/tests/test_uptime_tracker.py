"""
Tests for Uptime Tracking System

Tests for:
- Service uptime calculation
- Health checks (database)
- Downtime event logging
- Uptime percentage calculation
- Performance metrics
"""

import time
from datetime import datetime, timedelta
import pytest

from core.uptime_tracker import (
    DowntimeEvent,
    UptimeMetrics,
    UptimeTracker,
    check_uptime,
    get_uptime_tracker,
)


class TestUptimeTrackerBasics:
    """Test basic uptime tracker functionality"""

    def test_initialization(self):
        """Should initialize with start time"""
        tracker = UptimeTracker()

        assert tracker.start_time is not None
        assert isinstance(tracker.start_time, datetime)
        assert len(tracker.downtime_events) == 0
        assert tracker.current_downtime_start is None

    def test_custom_start_time(self):
        """Should accept custom start time"""
        custom_time = datetime(2026, 1, 1, 12, 0, 0)
        tracker = UptimeTracker(start_time=custom_time)

        assert tracker.start_time == custom_time

    def test_global_tracker_singleton(self):
        """Should return singleton instance"""
        tracker1 = get_uptime_tracker()
        tracker2 = get_uptime_tracker()

        assert tracker1 is tracker2


class TestHealthChecks:
    """Test health check functionality"""

    def test_health_check_returns_metrics(self, db_session):
        """Should return UptimeMetrics object"""
        tracker = UptimeTracker()
        metrics = tracker.check_health(db_session)

        assert isinstance(metrics, UptimeMetrics)
        assert metrics.start_time == tracker.start_time
        assert metrics.uptime_seconds >= 0
        assert metrics.database_healthy is not None

    def test_database_health_check(self, db_session):
        """Should check database connectivity"""
        tracker = UptimeTracker()
        metrics = tracker.check_health(db_session)

        assert metrics.database_healthy is True
        assert metrics.database_response_time_ms is not None
        assert metrics.database_response_time_ms >= 0

    def test_database_response_time_recorded(self, db_session):
        """Should record database response time"""
        tracker = UptimeTracker()
        metrics = tracker.check_health(db_session)

        # Response time should be reasonable (< 1 second for local DB)
        assert metrics.database_response_time_ms < 1000

    def test_health_check_creates_db_session_if_needed(self):
        """Should create database session if not provided"""
        tracker = UptimeTracker()
        metrics = tracker.check_health(db=None)

        assert metrics is not None
        assert metrics.database_healthy is not None

    def test_uptime_calculation(self):
        """Should calculate uptime correctly"""
        start = datetime.utcnow() - timedelta(hours=2)
        tracker = UptimeTracker(start_time=start)

        metrics = tracker.check_health()

        # Uptime should be approximately 2 hours (7200 seconds)
        assert 7100 < metrics.uptime_seconds < 7300
        assert metrics.uptime_percentage == 100.0  # No downtime events


class TestDowntimeTracking:
    """Test downtime event tracking"""

    def test_record_downtime_start(self):
        """Should record downtime start"""
        tracker = UptimeTracker()
        tracker.record_downtime_start("Database failure", ["database"])

        assert tracker.current_downtime_start is not None
        assert isinstance(tracker.current_downtime_start, datetime)

    def test_record_downtime_end(self):
        """Should record downtime end and create event"""
        tracker = UptimeTracker()
        tracker.record_downtime_start("API failure", ["api"])

        time.sleep(0.1)  # Small delay
        tracker.record_downtime_end()

        assert len(tracker.downtime_events) == 1
        assert tracker.current_downtime_start is None

        event = tracker.downtime_events[0]
        assert event.duration_seconds >= 0.1
        assert event.start_time is not None
        assert event.end_time is not None

    def test_downtime_affects_uptime_percentage(self):
        """Should calculate correct uptime percentage with downtime"""
        # Set start time to exactly 1 hour ago
        start = datetime.utcnow() - timedelta(seconds=3600)
        tracker = UptimeTracker(start_time=start)

        # Manually create downtime event (5 minutes = 300 seconds)
        downtime_start = start + timedelta(seconds=100)  # Start during uptime
        downtime_end = downtime_start + timedelta(seconds=300)  # 5 minutes later

        event = DowntimeEvent(
            start_time=downtime_start,
            end_time=downtime_end,
            duration_seconds=300,
            reason="Simulated downtime",
            affected_components=["database"],
        )
        tracker.downtime_events.append(event)

        metrics = tracker.check_health()

        # Total time: 3600 seconds (1 hour from start to now, approximately)
        # Downtime: 300 seconds
        # Expected: uptime_percentage should be > 90% with only 5 min downtime
        assert metrics.uptime_percentage > 90.0
        assert metrics.total_downtime_seconds == 300

    def test_multiple_downtime_events(self):
        """Should track multiple downtime events"""
        tracker = UptimeTracker()

        # Record multiple events
        for i in range(3):
            tracker.record_downtime_start(f"Failure {i}", ["component"])
            time.sleep(0.05)
            tracker.record_downtime_end()

        assert len(tracker.downtime_events) == 3

        metrics = tracker.check_health()
        assert metrics.total_downtime_events == 3

    def test_ignore_duplicate_start(self):
        """Should ignore downtime start if already in progress"""
        tracker = UptimeTracker()
        tracker.record_downtime_start("First failure", ["db"])

        first_start = tracker.current_downtime_start

        # Try to start again
        tracker.record_downtime_start("Second failure", ["api"])

        # Should keep first start time
        assert tracker.current_downtime_start == first_start

    def test_ignore_end_without_start(self):
        """Should ignore downtime end if no downtime in progress"""
        tracker = UptimeTracker()

        # Should not raise error
        tracker.record_downtime_end()

        assert len(tracker.downtime_events) == 0


class TestUptimeFormatting:
    """Test uptime duration formatting"""

    def test_format_seconds_only(self):
        """Should format seconds correctly"""
        tracker = UptimeTracker()
        formatted = tracker._format_duration(45)

        assert "45s" in formatted

    def test_format_minutes_and_seconds(self):
        """Should format minutes and seconds"""
        tracker = UptimeTracker()
        formatted = tracker._format_duration(125)  # 2m 5s

        assert "2m" in formatted
        assert "5s" in formatted

    def test_format_hours_minutes_seconds(self):
        """Should format hours, minutes, seconds"""
        tracker = UptimeTracker()
        formatted = tracker._format_duration(3661)  # 1h 1m 1s

        assert "1h" in formatted
        assert "1m" in formatted
        assert "1s" in formatted

    def test_format_days_hours_minutes(self):
        """Should format days, hours, minutes"""
        tracker = UptimeTracker()
        formatted = tracker._format_duration(90061)  # 1d 1h 1m 1s

        assert "1d" in formatted
        assert "1h" in formatted
        assert "1m" in formatted

    def test_uptime_formatted_in_metrics(self):
        """Should include formatted uptime in metrics"""
        start = datetime.utcnow() - timedelta(hours=2, minutes=30)
        tracker = UptimeTracker(start_time=start)

        metrics = tracker.check_health()

        assert metrics.uptime_formatted is not None
        assert "2h" in metrics.uptime_formatted


class TestDowntimeEventRetrieval:
    """Test retrieval of downtime events"""

    def test_get_recent_downtime_events(self):
        """Should return most recent downtime events"""
        tracker = UptimeTracker()

        # Create events with different times
        now = datetime.utcnow()
        for i in range(5):
            event = DowntimeEvent(
                start_time=now - timedelta(hours=i),
                end_time=now - timedelta(hours=i) + timedelta(minutes=5),
                duration_seconds=300,
                reason=f"Event {i}",
                affected_components=[],
            )
            tracker.downtime_events.append(event)

        recent = tracker.get_recent_downtime_events(limit=3)

        assert len(recent) == 3
        # Should be sorted by start time (newest first)
        assert recent[0].reason == "Event 0"  # Most recent

    def test_get_downtime_events_in_range(self):
        """Should filter events by time range"""
        tracker = UptimeTracker()
        now = datetime.utcnow()

        # Create events at different times
        events = [
            (now - timedelta(hours=3), "Old event"),
            (now - timedelta(hours=2), "Event in range"),
            (now - timedelta(hours=1), "Another in range"),
            (now - timedelta(minutes=30), "Recent event"),
        ]

        for start_time, reason in events:
            event = DowntimeEvent(
                start_time=start_time,
                end_time=start_time + timedelta(minutes=5),
                duration_seconds=300,
                reason=reason,
                affected_components=[],
            )
            tracker.downtime_events.append(event)

        # Query last 2 hours
        start_range = now - timedelta(hours=2)
        end_range = now
        in_range = tracker.get_downtime_events_in_range(start_range, end_range)

        # Should get 3 events (excluding the 3-hour-old one)
        assert len(in_range) == 3


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_check_uptime_returns_dict(self):
        """Should return dictionary from check_uptime"""
        result = check_uptime()

        assert isinstance(result, dict)
        assert "uptime_percentage" in result
        assert "database_healthy" in result
        assert "uptime_formatted" in result

    def test_check_uptime_dict_structure(self):
        """Should return properly structured dict"""
        result = check_uptime()

        required_keys = [
            "start_time",
            "current_time",
            "uptime_seconds",
            "uptime_formatted",
            "uptime_percentage",
            "downtime_percentage",
            "total_downtime_events",
            "total_downtime_seconds",
            "database_healthy",
        ]

        for key in required_keys:
            assert key in result, f"Missing key: {key}"


class TestMetricsToDict:
    """Test UptimeMetrics to_dict conversion"""

    def test_metrics_to_dict(self, db_session):
        """Should convert metrics to dict correctly"""
        tracker = UptimeTracker()
        metrics = tracker.check_health(db_session)

        result = metrics.to_dict()

        assert isinstance(result, dict)
        assert result["uptime_percentage"] == metrics.uptime_percentage
        assert result["database_healthy"] == metrics.database_healthy
        assert "start_time" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
