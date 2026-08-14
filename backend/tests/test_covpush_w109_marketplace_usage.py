# -*- coding: utf-8 -*-
"""Coverage wave 109 — core/marketplace_usage_tracker.py (never-tested module,
26% import baseline -> target 100%; fully mocked, no DB, no network).

- track_usage: new-row creation (success True/False), existing-row increment
  (success/failure counters), DB exception swallowed + logged (never raises).
- get_pending_reports: empty result set, report shape (avg duration, period
  start from last_reported_at/updated_at fallback), counter reset +
  last_reported_at stamp, DB exception swallowed.
- get_db_session context-manager contract (patch returns a mock context).
"""
from datetime import datetime, timezone

from unittest.mock import MagicMock, patch

import pytest

from core.marketplace_usage_tracker import MarketplaceUsageTracker


class FakeRow:
    """Mutable stand-in for a MarketplaceUsage ORM row."""

    def __init__(self, item_type="skill", item_id="s1", execution_count=0,
                 success_count=0, total_duration_ms=0.0, last_reported_at=None,
                 updated_at=None):
        self.item_type = item_type
        self.item_id = item_id
        self.execution_count = execution_count
        self.success_count = success_count
        self.total_duration_ms = total_duration_ms
        self.last_reported_at = last_reported_at
        self.updated_at = updated_at or datetime.now(timezone.utc)


from contextlib import contextmanager


@pytest.fixture
def db_ctx():
    rows = {"first": None, "all": [], "added": None, "committed": False}

    class FakeSession:
        def query(self, model):
            return self

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return rows["first"]

        def all(self):
            return list(rows["all"])

        def add(self, obj):
            rows["added"] = obj

        def commit(self):
            rows["committed"] = True

    session = FakeSession()

    @contextmanager
    def _ctx():
        try:
            yield session
        finally:
            pass

    return _ctx, session, rows


class TestTrackUsage:
    def test_new_row_success(self, db_ctx):
        _ctx, session, rows = db_ctx
        rows["first"] = None
        with patch("core.marketplace_usage_tracker.get_db_session", side_effect=lambda: _ctx()):
            MarketplaceUsageTracker.track_usage("skill", "s1", success=True, duration_ms=12.5)
        added = rows["added"]
        assert added is not None
        assert added.execution_count == 1
        assert added.success_count == 1
        assert added.total_duration_ms == 12.5
        assert rows["committed"] is True

    def test_new_row_failure(self, db_ctx):
        _ctx, session, rows = db_ctx
        rows["first"] = None
        with patch("core.marketplace_usage_tracker.get_db_session", side_effect=lambda: _ctx()):
            MarketplaceUsageTracker.track_usage("agent", "a1", success=False, duration_ms=3.0)
        added = rows["added"]
        assert added.success_count == 0
        assert added.execution_count == 1

    def test_existing_row_increments(self, db_ctx):
        _ctx, session, rows = db_ctx
        row = FakeRow(execution_count=4, success_count=3, total_duration_ms=100.0)
        rows["first"] = row
        with patch("core.marketplace_usage_tracker.get_db_session", side_effect=lambda: _ctx()):
            MarketplaceUsageTracker.track_usage("skill", "s1", success=True, duration_ms=20.0)
        assert row.execution_count == 5
        assert row.success_count == 4
        assert row.total_duration_ms == 120.0

    def test_existing_row_failure_not_counted(self, db_ctx):
        _ctx, session, rows = db_ctx
        row = FakeRow(execution_count=1, success_count=1, total_duration_ms=10.0)
        rows["first"] = row
        with patch("core.marketplace_usage_tracker.get_db_session", side_effect=lambda: _ctx()):
            MarketplaceUsageTracker.track_usage("skill", "s1", success=False, duration_ms=5.0)
        assert row.execution_count == 2
        assert row.success_count == 1
        assert row.total_duration_ms == 15.0

    def test_db_exception_swallowed(self):
        with patch("core.marketplace_usage_tracker.get_db_session", side_effect=RuntimeError("db down")):
            # Must NOT raise — analytics must never break the main flow.
            MarketplaceUsageTracker.track_usage("skill", "s1")
        assert True


class TestGetPendingReports:
    def test_no_reports(self, db_ctx):
        _ctx, session, rows = db_ctx
        rows["all"] = []
        with patch("core.marketplace_usage_tracker.get_db_session", side_effect=lambda: _ctx()):
            reports = MarketplaceUsageTracker.get_pending_reports()
        assert reports == []

    def test_report_shape_and_reset(self, db_ctx):
        _ctx, session, rows = db_ctx
        updated = datetime(2026, 8, 1, tzinfo=timezone.utc)
        row = FakeRow(execution_count=5, success_count=4, total_duration_ms=250.0,
                      last_reported_at=None, updated_at=updated)
        rows["all"] = [row]
        with patch("core.marketplace_usage_tracker.get_db_session", side_effect=lambda: _ctx()):
            reports = MarketplaceUsageTracker.get_pending_reports()
        assert len(reports) == 1
        rep = reports[0]
        assert rep["item_type"] == "skill"
        assert rep["item_id"] == "s1"
        assert rep["execution_count"] == 5
        assert rep["success_count"] == 4
        assert rep["avg_duration_ms"] == 50.0
        assert rep["period_start"] == updated
        assert rep["period_end"] is not None
        # Counters reset for the next period.
        assert row.execution_count == 0
        assert row.success_count == 0
        assert row.total_duration_ms == 0.0
        assert row.last_reported_at is not None

    def test_report_uses_last_reported_at(self, db_ctx):
        _ctx, session, rows = db_ctx
        last_reported = datetime(2026, 7, 15, tzinfo=timezone.utc)
        row = FakeRow(execution_count=1, success_count=1, total_duration_ms=5.0,
                      last_reported_at=last_reported)
        rows["all"] = [row]
        with patch("core.marketplace_usage_tracker.get_db_session", side_effect=lambda: _ctx()):
            reports = MarketplaceUsageTracker.get_pending_reports()
        assert reports[0]["period_start"] == last_reported

    def test_zero_duration_safe(self, db_ctx):
        _ctx, session, rows = db_ctx
        row = FakeRow(execution_count=0, success_count=0, total_duration_ms=0.0)
        rows["all"] = [row]
        with patch("core.marketplace_usage_tracker.get_db_session", side_effect=lambda: _ctx()):
            reports = MarketplaceUsageTracker.get_pending_reports()
        assert reports[0]["avg_duration_ms"] == 0

    def test_db_exception_swallowed_returns_empty(self):
        with patch("core.marketplace_usage_tracker.get_db_session", side_effect=RuntimeError("db down")):
            reports = MarketplaceUsageTracker.get_pending_reports()
        assert reports == []
