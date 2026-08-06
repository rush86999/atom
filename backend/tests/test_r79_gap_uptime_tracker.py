# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: core/uptime_tracker.py (uptime/health/downtime tracking;
zero test references before this file).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from core import uptime_tracker as ut
from core.uptime_tracker import (
    DowntimeEvent,
    UptimeMetrics,
    UptimeTracker,
    check_uptime,
    get_uptime_tracker,
)


def _past(seconds=3600):
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


class TestMetricsDataClasses:
    def test_uptime_metrics_to_dict(self):
        m = UptimeMetrics(
            start_time=_past(),
            current_time=datetime.now(timezone.utc),
            uptime_seconds=100.0,
            uptime_formatted="1m 40s",
            uptime_percentage=99.5,
            downtime_percentage=0.5,
            total_downtime_events=1,
            total_downtime_seconds=0.5,
            database_healthy=True,
            database_response_time_ms=2.0,
        )
        d = m.to_dict()
        assert d["uptime_percentage"] == 99.5
        assert d["database_healthy"] is True
        assert d["total_downtime_events"] == 1

    def test_downtime_event_to_dict_with_open_end(self):
        e = DowntimeEvent(
            start_time=_past(600),
            end_time=None,
            duration_seconds=600.0,
            reason="maintenance",
            affected_components=["api"],
        )
        d = e.to_dict()
        assert d["end_time"] is None
        assert d["reason"] == "maintenance"


class TestCheckHealth:
    def test_healthy_database(self):
        tracker = UptimeTracker(start_time=_past(3600))
        db = MagicMock()
        db.execute.return_value.scalar.return_value = 1
        metrics = tracker.check_health(db=db)
        assert metrics.database_healthy is True
        assert metrics.database_response_time_ms is not None
        assert metrics.uptime_percentage > 99.0

    def test_unhealthy_database(self):
        tracker = UptimeTracker(start_time=_past(3600))
        db = MagicMock()
        db.execute.side_effect = RuntimeError("db down")
        metrics = tracker.check_health(db=db)
        assert metrics.database_healthy is False
        assert metrics.database_response_time_ms is None

    def test_fresh_tracker_percentage_100(self):
        tracker = UptimeTracker(start_time=datetime.now(timezone.utc))
        db = MagicMock()
        db.execute.return_value.scalar.return_value = 1
        metrics = tracker.check_health(db=db)
        assert metrics.uptime_percentage == 100.0
        assert metrics.downtime_percentage == 0.0

    def test_check_health_creates_session_when_no_db(self):
        tracker = UptimeTracker(start_time=_past(60))
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        with patch.object(ut, "get_db_session", return_value=cm):
            tracker.check_health()
        cm.__enter__.assert_called_once()


class TestDowntimeTracking:
    def test_record_start_end_creates_event(self):
        tracker = UptimeTracker(start_time=_past(3600))
        tracker.record_downtime_start("outage", ["db"])
        tracker.record_downtime_end()
        assert len(tracker.downtime_events) == 1
        assert tracker.current_downtime_start is None
        assert tracker.downtime_events[0].duration_seconds >= 0

    def test_double_start_ignored(self):
        tracker = UptimeTracker()
        tracker.record_downtime_start("first")
        tracker.record_downtime_start("second")
        assert len(tracker.downtime_events) == 0

    def test_end_without_start_ignored(self):
        tracker = UptimeTracker()
        tracker.record_downtime_end()
        assert len(tracker.downtime_events) == 0

    def test_recent_events_sorted_newest_first(self):
        tracker = UptimeTracker()
        tracker.downtime_events = [
            DowntimeEvent(_past(3000), None, 1, "a", []),
            DowntimeEvent(_past(1000), None, 1, "b", []),
            DowntimeEvent(_past(2000), None, 1, "c", []),
        ]
        recent = tracker.get_recent_downtime_events(limit=2)
        assert [e.reason for e in recent] == ["b", "c"]

    def test_events_in_range(self):
        tracker = UptimeTracker()
        tracker.downtime_events = [
            DowntimeEvent(_past(5000), None, 1, "old", []),
            DowntimeEvent(_past(1500), None, 1, "new", []),
        ]
        start = datetime.now(timezone.utc) - timedelta(seconds=2000)
        matched = tracker.get_downtime_events_in_range(start, datetime.now(timezone.utc))
        assert [e.reason for e in matched] == ["new"]

    def test_format_duration(self):
        tracker = UptimeTracker()
        assert tracker._format_duration(0) == "0s"
        assert tracker._format_duration(45) == "45s"
        assert tracker._format_duration(90061) == "1d 1h 1m 1s"


class TestSingletonAndHelper:
    def test_get_uptime_tracker_singleton(self):
        with patch.object(ut, "_uptime_tracker", None):
            assert get_uptime_tracker() is get_uptime_tracker()

    def test_check_uptime_returns_dict(self):
        with patch.object(ut, "get_uptime_tracker") as get_tracker:
            tracker = UptimeTracker(start_time=_past(60))
            db = MagicMock()
            db.execute.return_value.scalar.return_value = 1
            tracker.check_health = MagicMock(return_value=tracker.check_health(db=db))
            get_tracker.return_value = tracker
            result = check_uptime()
        assert isinstance(result, dict)
        assert "uptime_percentage" in result
