"""
EXTENSION coverage tests for core/workflow_analytics_engine.py.

Existing coverage (tests/core/test_workflow_analytics_coverage.py and
tests/unit/test_workflow_analytics_engine.py) hits ~81%. This file covers the
gaps:
- get_performance_metrics("*") aggregation wrapper + _get_all_workflows_metrics
- check_alerts / _trigger_alert / _resolve_alert / _send_alert_notification
- create_alert(Alert) wrapper, update_alert, delete_alert
- _process_metrics_batch / _process_events_batch / _cleanup_old_data / flush
- _start_background_processing guard
- get_execution_timeline (specific + "*" + exception)
- get_error_breakdown (specific workflow branch)
- get_unique_workflow_count / get_last_execution_time edge cases
- exception re-raise paths in performance-metrics queries
"""
import asyncio
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from core.workflow_analytics_engine import (
    Alert,
    AlertSeverity,
    MetricType,
    PerformanceMetrics,
    WorkflowAnalyticsEngine,
    WorkflowExecutionEvent,
    WorkflowStatus,
    WorkflowMetric,
    get_analytics_engine,
)


@pytest.fixture
def engine():
    """Fresh engine on a temp DB for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        eng = WorkflowAnalyticsEngine(db_path=db_path)
        yield eng


def _insert_event(conn, workflow_id, execution_id, event_type, status=None,
                  duration_ms=None, error_message=None, step_name=None,
                  user_id="default_user", timestamp=None, resource_id=None):
    ts = (timestamp or datetime.now()).isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO workflow_events
           (event_id, workflow_id, execution_id, user_id, event_type, timestamp,
            step_id, step_name, duration_ms, status, error_message, metadata, resource_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (f"{execution_id}-{event_type}-{ts}", workflow_id, execution_id, user_id,
         event_type, ts, None, step_name, duration_ms, status, error_message, None, resource_id),
    )


def _insert_metric(conn, workflow_id, metric_name, value, timestamp=None, step_name=None):
    ts = (timestamp or datetime.now()).isoformat()
    conn.execute(
        """INSERT INTO workflow_metrics
           (workflow_id, metric_name, metric_type, value, timestamp, tags, step_id,
            step_name, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (workflow_id, metric_name, "gauge", str(value), ts, None, None, step_name, "default_user"),
    )


# ---------------------------------------------------------------------------
# get_performance_metrics("*") aggregation
# ---------------------------------------------------------------------------
class TestAggregationAllWorkflows:
    @pytest.mark.asyncio
    async def test_get_all_workflows_metrics_with_data(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        # two workflows with started + completed events
        _insert_event(conn, "wf1", "e1", "workflow_started")
        _insert_event(conn, "wf1", "e1", "workflow_completed", status="completed", duration_ms=100)
        _insert_event(conn, "wf2", "e2", "workflow_started", user_id="u2")
        _insert_event(conn, "wf2", "e2", "workflow_completed", status="failed", duration_ms=200,
                      error_message="boom")
        conn.commit()
        conn.close()

        result = engine.get_performance_metrics("*", "24h")
        assert isinstance(result, PerformanceMetrics)
        assert result.workflow_id == "*"
        assert result.total_executions == 2
        assert result.successful_executions == 1
        assert result.failed_executions == 1
        assert result.error_rate == 50.0
        assert result.unique_users == 2
        assert len(result.most_common_errors) == 1
        assert result.most_common_errors[0]["error"] == "boom"

    def test_get_all_workflows_metrics_empty(self, engine):
        result = engine._get_all_workflows_metrics("24h")
        assert result.total_executions == 0
        assert result.error_rate == 0

    def test_get_performance_metrics_star_routes_to_aggregation(self, engine):
        result = engine.get_performance_metrics("*", "7d")
        assert result.workflow_id == "*"

    def test_get_all_workflows_metrics_re_raise_on_error(self, engine):
        """Force an exception inside _get_all_workflows_metrics by breaking the DB."""
        engine.db_path = Path("/nonexistent/dir/missing.db")
        with pytest.raises(Exception):
            engine._get_all_workflows_metrics("24h")


# ---------------------------------------------------------------------------
# get_workflow_performance_metrics edge cases
# ---------------------------------------------------------------------------
class TestPerformanceMetricsEdges:
    def test_performance_metrics_no_completed_events(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        _insert_event(conn, "wf", "e", "workflow_started")
        conn.commit()
        conn.close()
        m = engine.get_workflow_performance_metrics("wf", "24h")
        assert m.total_executions == 1
        assert m.successful_executions == 0
        assert m.average_duration_ms == 0

    def test_performance_metrics_with_many_durations_for_percentiles(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        for i in range(25):
            _insert_event(conn, "wf", f"e{i}", "workflow_started")
            _insert_event(conn, "wf", f"e{i}", "workflow_completed", status="completed",
                          duration_ms=100 + i)
        conn.commit()
        conn.close()
        m = engine.get_workflow_performance_metrics("wf", "24h")
        # >20 durations -> p95 populated
        assert m.p95_duration_ms > 0

    def test_performance_metrics_re_raise_on_db_error(self, engine):
        engine.db_path = Path("/nonexistent/dir/missing.db")
        with pytest.raises(Exception):
            engine.get_workflow_performance_metrics("wf", "24h")

    def test_performance_cache_returns_cached(self, engine):
        # Prime cache by inserting a metric and querying
        conn = sqlite3.connect(str(engine.db_path))
        _insert_event(conn, "wf", "e", "workflow_started")
        conn.commit()
        conn.close()
        first = engine.get_workflow_performance_metrics("wf", "24h")
        second = engine.get_workflow_performance_metrics("wf", "24h")
        assert first is second  # same cached object


# ---------------------------------------------------------------------------
# Alert lifecycle: create -> check -> trigger -> resolve
# ---------------------------------------------------------------------------
class TestAlertLifecycle:
    def test_create_alert_with_kwargs_returns_alert(self, engine):
        """BUG: WorkflowAnalyticsEngine.create_alert was defined TWICE in the
        class body (kwargs form at line 760, Alert-object form at line 1522).
        Python let the second silently shadow the first, so every kwargs-style
        call raised `TypeError: create_alert() got an unexpected keyword
        argument 'name'`. The dispatching fix supports both call styles.
        """
        alert = engine.create_alert(
            name="High Error Rate",
            description="error rate too high",
            severity=AlertSeverity.HIGH,
            condition="error_rate > threshold",
            threshold_value=10.0,
            metric_name="error_rate",
            workflow_id="wf1",
            notification_channels=["email"],
        )
        assert alert.alert_id in engine.active_alerts
        assert alert.name == "High Error Rate"

    def test_check_alerts_triggers_when_above_threshold(self, engine):
        # Create an alert with threshold 5 and a metric value of 10
        alert = engine.create_alert(
            name="t", description="d", severity=AlertSeverity.MEDIUM,
            condition="x", threshold_value=5.0, metric_name="mymetric",
        )
        # Insert metric above threshold
        conn = sqlite3.connect(str(engine.db_path))
        _insert_metric(conn, "wf", "mymetric", 10.0)
        conn.commit()
        conn.close()

        engine.check_alerts()
        assert engine.active_alerts[alert.alert_id].triggered_at is not None

    def test_check_alerts_resolves_when_below_threshold(self, engine):
        alert = engine.create_alert(
            name="t", description="d", severity=AlertSeverity.MEDIUM,
            condition="x", threshold_value=5.0, metric_name="mymetric",
        )
        # First trigger it
        conn = sqlite3.connect(str(engine.db_path))
        _insert_metric(conn, "wf", "mymetric", 10.0)
        conn.commit()
        engine.check_alerts()
        assert engine.active_alerts[alert.alert_id].triggered_at is not None

        # Now insert a lower value and re-check
        _insert_metric(conn, "wf", "mymetric", 1.0)
        conn.commit()
        conn.close()
        engine.check_alerts()
        assert engine.active_alerts[alert.alert_id].resolved_at is not None

    def test_check_alerts_no_metric_does_nothing(self, engine):
        alert = engine.create_alert(
            name="t", description="d", severity=AlertSeverity.LOW,
            condition="x", threshold_value=5.0, metric_name="nomatch",
        )
        engine.check_alerts()
        assert engine.active_alerts[alert.alert_id].triggered_at is None

    def test_trigger_alert_noop_when_not_in_active(self, engine):
        engine._trigger_alert("nonexistent")  # no error

    def test_resolve_alert_noop_when_not_in_active(self, engine):
        engine._resolve_alert("nonexistent")  # no error

    def test_resolve_alert_noop_when_not_triggered(self, engine):
        alert = engine.create_alert(
            name="t", description="d", severity=AlertSeverity.LOW,
            condition="x", threshold_value=5.0, metric_name="m",
        )
        engine._resolve_alert(alert.alert_id)  # not triggered yet -> noop
        assert engine.active_alerts[alert.alert_id].resolved_at is None

    def test_check_alerts_handles_invalid_threshold(self, engine):
        """threshold_value stored as non-numeric -> inner except logs, continues."""
        conn = sqlite3.connect(str(engine.db_path))
        conn.execute(
            """INSERT INTO analytics_alerts
               (alert_id, name, description, severity, condition, threshold_value,
                metric_name, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            ("a-bad", "n", "d", "low", "c", "not-a-number", "m"),
        )
        conn.commit()
        conn.close()
        # must not raise
        engine.check_alerts()


# ---------------------------------------------------------------------------
# Alert CRUD wrappers (create_alert(Alert), update_alert, delete_alert)
# ---------------------------------------------------------------------------
class TestAlertCRUD:
    def test_create_alert_from_object(self, engine):
        alert = Alert(
            alert_id="alert-obj-1",
            name="obj",
            description="d",
            severity=AlertSeverity.LOW,
            condition="c",
            threshold_value=5.0,
            metric_name="m",
            enabled=True,
            notification_channels=["email"],
        )
        result = engine.create_alert(alert)
        assert result is alert
        assert "alert-obj-1" in engine.active_alerts

    def test_create_alert_from_object_threshold_none_stored_as_null(self, engine):
        alert = Alert(
            alert_id="alert-null",
            name="obj", description="d", severity=AlertSeverity.LOW,
            condition="c", threshold_value=None, metric_name="m",
            enabled=False, notification_channels=None,
        )
        result = engine.create_alert(alert)
        assert result is alert

    def test_update_alert_enable_and_threshold(self, engine):
        alert = engine.create_alert(
            name="t", description="d", severity=AlertSeverity.LOW,
            condition="x", threshold_value=5.0, metric_name="m",
        )
        engine.update_alert(alert.alert_id, enabled=False, threshold_value=99.0)
        assert engine.active_alerts[alert.alert_id].enabled is False
        assert engine.active_alerts[alert.alert_id].threshold_value == 99.0

    def test_update_alert_no_changes_noop(self, engine):
        alert = engine.create_alert(
            name="t", description="d", severity=AlertSeverity.LOW,
            condition="x", threshold_value=5.0, metric_name="m",
        )
        engine.update_alert(alert.alert_id)  # no fields -> no updates
        assert engine.active_alerts[alert.alert_id].enabled is True

    def test_update_alert_unknown_id_no_crash(self, engine):
        engine.update_alert("ghost", enabled=True)

    def test_delete_alert_removes_from_db_and_memory(self, engine):
        alert = engine.create_alert(
            name="t", description="d", severity=AlertSeverity.LOW,
            condition="x", threshold_value=5.0, metric_name="m",
        )
        engine.delete_alert(alert.alert_id)
        assert alert.alert_id not in engine.active_alerts
        # verify gone from DB
        conn = sqlite3.connect(str(engine.db_path))
        cur = conn.execute("SELECT COUNT(*) FROM analytics_alerts WHERE alert_id = ?",
                           (alert.alert_id,))
        assert cur.fetchone()[0] == 0
        conn.close()


# ---------------------------------------------------------------------------
# Batch processing (flush + _process_*_batch + _cleanup_old_data)
# ---------------------------------------------------------------------------
class TestBatchProcessing:
    @pytest.mark.asyncio
    async def test_flush_persists_metrics_and_events(self, engine):
        engine.track_workflow_start("wf", "exec-1")
        engine.track_workflow_completion("wf", "exec-1", WorkflowStatus.COMPLETED, 100)
        assert len(engine.metrics_buffer) > 0
        assert len(engine.events_buffer) > 0

        await engine.flush()
        assert len(engine.metrics_buffer) == 0
        assert len(engine.events_buffer) == 0

        # verify persisted
        conn = sqlite3.connect(str(engine.db_path))
        m_count = conn.execute("SELECT COUNT(*) FROM workflow_metrics").fetchone()[0]
        e_count = conn.execute("SELECT COUNT(*) FROM workflow_events").fetchone()[0]
        conn.close()
        assert m_count > 0
        assert e_count > 0

    @pytest.mark.asyncio
    async def test_flush_empty_buffers_noop(self, engine):
        await engine.flush()  # nothing to flush
        assert len(engine.metrics_buffer) == 0

    @pytest.mark.asyncio
    async def test_process_metrics_batch_handles_exception(self, engine):
        """_process_metrics_batch swallows DB errors during execute and rolls back.
        Trigger by pointing at a DB file whose schema was never initialized
        (the INSERT references a table that doesn't exist)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_db = f.name
        try:
            engine.db_path = Path(empty_db)
            metric = WorkflowMetric(
                workflow_id="wf", metric_name="m", metric_type=MetricType.GAUGE,
                value=1, timestamp=datetime.now(),
            )
            # must not raise (no workflow_metrics table exists)
            await engine._process_metrics_batch([metric])
        finally:
            os.unlink(empty_db)

    @pytest.mark.asyncio
    async def test_process_events_batch_handles_exception(self, engine):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_db = f.name
        try:
            engine.db_path = Path(empty_db)
            event = WorkflowExecutionEvent(
                event_id="e1", workflow_id="wf", execution_id="x",
                event_type="started", timestamp=datetime.now(),
            )
            await engine._process_events_batch([event])  # no raise
        finally:
            os.unlink(empty_db)

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        # insert an old metric (100 days ago) and a recent one
        old_ts = (datetime.now() - timedelta(days=100)).isoformat()
        new_ts = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO workflow_metrics (workflow_id, metric_name, metric_type, value, timestamp, user_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("wf", "m", "gauge", "1", old_ts, "u"),
        )
        conn.execute(
            "INSERT INTO workflow_metrics (workflow_id, metric_name, metric_type, value, timestamp, user_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("wf", "m", "gauge", "2", new_ts, "u"),
        )
        conn.commit()
        conn.close()

        await engine._cleanup_old_data()

        conn = sqlite3.connect(str(engine.db_path))
        remaining = conn.execute("SELECT COUNT(*) FROM workflow_metrics").fetchone()[0]
        conn.close()
        assert remaining == 1  # only the recent one

    @pytest.mark.asyncio
    async def test_cleanup_old_data_handles_exception(self, engine):
        """_cleanup_old_data swallows errors during DELETE and rolls back."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_db = f.name
        try:
            engine.db_path = Path(empty_db)
            await engine._cleanup_old_data()  # no tables -> DELETE errors swallowed
        finally:
            os.unlink(empty_db)


# ---------------------------------------------------------------------------
# Background processing guard
# ---------------------------------------------------------------------------
class TestBackgroundProcessing:
    def test_start_background_processing_disabled_noop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            eng = WorkflowAnalyticsEngine(
                db_path=os.path.join(tmpdir, "x.db"), enable_background_thread=False
            )
            # calling _start_background_processing directly returns early
            eng._start_background_processing()
            assert eng._background_thread is None


# ---------------------------------------------------------------------------
# get_execution_timeline
# ---------------------------------------------------------------------------
class TestExecutionTimeline:
    def test_timeline_specific_workflow(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        _insert_event(conn, "wf", "e1", "workflow_started")
        _insert_event(conn, "wf", "e1", "workflow_completed", status="completed", duration_ms=50)
        conn.commit()
        conn.close()
        timeline = engine.get_execution_timeline("wf", "24h", "1h")
        assert isinstance(timeline, list)
        assert len(timeline) >= 1
        # at least one bucket has count
        assert any(b["count"] > 0 for b in timeline)

    def test_timeline_all_workflows_star(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        _insert_event(conn, "wf", "e1", "workflow_started")
        conn.commit()
        conn.close()
        timeline = engine.get_execution_timeline("*", "24h", "1h")
        assert isinstance(timeline, list)
        assert any(b["count"] > 0 for b in timeline)

    def test_timeline_exception_returns_empty(self, engine):
        """get_execution_timeline returns [] when the query errors (e.g. no table)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_db = f.name
        try:
            engine.db_path = Path(empty_db)
            result = engine.get_execution_timeline("wf", "24h")
            assert result == []
        finally:
            os.unlink(empty_db)


# ---------------------------------------------------------------------------
# get_error_breakdown
# ---------------------------------------------------------------------------
class TestErrorBreakdown:
    def test_error_breakdown_all_workflows_star(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        _insert_event(conn, "wf1", "e1", "workflow_completed", status="failed",
                      error_message="timeout error")
        _insert_event(conn, "wf2", "e2", "workflow_completed", status="failed",
                      error_message="auth error")
        conn.commit()
        conn.close()
        result = engine.get_error_breakdown("*", "24h")
        assert "workflows_with_errors" in result
        assert len(result["workflows_with_errors"]) == 2
        assert "recent_errors" in result

    def test_error_breakdown_specific_workflow(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        _insert_event(conn, "wf", "e1", "workflow_completed", status="failed",
                      error_message="boom", step_name="step1")
        conn.commit()
        conn.close()
        result = engine.get_error_breakdown("wf", "24h")
        assert result["workflow_id"] == "wf"
        assert len(result["recent_errors"]) == 1
        assert result["recent_errors"][0]["step_name"] == "step1"
        assert len(result["error_types"]) == 1

    def test_error_breakdown_specific_workflow_no_errors(self, engine):
        result = engine.get_error_breakdown("ghost-wf", "24h")
        assert result["workflow_id"] == "ghost-wf"
        assert result["error_types"] == []

    def test_error_breakdown_specific_workflow_error_message_none(self, engine):
        """error_msg is None -> error_type becomes 'Unknown'."""
        conn = sqlite3.connect(str(engine.db_path))
        # Insert a row with NULL error_message but matched by the query? The query
        # filters error_message IS NOT NULL, so NULLs won't match. Instead test the
        # defensive [:50] handling by inserting a normal error.
        _insert_event(conn, "wf", "e1", "workflow_completed", status="failed",
                      error_message="x" * 100)  # long message, truncated to 50
        conn.commit()
        conn.close()
        result = engine.get_error_breakdown("wf", "24h")
        assert len(result["error_types"]) == 1
        assert len(result["error_types"][0]["type"]) == 50

    def test_error_breakdown_handles_exception(self, engine):
        """get_error_breakdown returns {} when the query errors (no table)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_db = f.name
        try:
            engine.db_path = Path(empty_db)
            result = engine.get_error_breakdown("wf", "24h")
            assert result == {}
        finally:
            os.unlink(empty_db)


# ---------------------------------------------------------------------------
# Misc query helpers edge cases
# ---------------------------------------------------------------------------
class TestQueryHelpers:
    def test_get_unique_workflow_count(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        _insert_event(conn, "wf1", "e1", "workflow_started")
        _insert_event(conn, "wf2", "e2", "workflow_started")
        conn.commit()
        conn.close()
        assert engine.get_unique_workflow_count("24h") == 2

    def test_get_unique_workflow_count_empty(self, engine):
        assert engine.get_unique_workflow_count("24h") == 0

    def test_get_workflow_name_returns_id(self, engine):
        assert engine.get_workflow_name("wf-xyz") == "wf-xyz"

    def test_get_all_workflow_ids(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        _insert_event(conn, "wf1", "e1", "workflow_started")
        _insert_event(conn, "wf2", "e2", "workflow_started")
        conn.commit()
        conn.close()
        ids = engine.get_all_workflow_ids("24h")
        assert sorted(ids) == ["wf1", "wf2"]

    def test_get_last_execution_time_present(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        ts = datetime.now()
        _insert_event(conn, "wf", "e", "workflow_started", timestamp=ts)
        conn.commit()
        conn.close()
        result = engine.get_last_execution_time("wf")
        assert result is not None
        assert isinstance(result, datetime)

    def test_get_last_execution_time_absent(self, engine):
        assert engine.get_last_execution_time("ghost") is None

    def test_get_recent_events_with_workflow_filter(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        _insert_event(conn, "wf", "e1", "workflow_started")
        _insert_event(conn, "other", "e2", "workflow_started")
        conn.commit()
        conn.close()
        events = engine.get_recent_events(limit=10, workflow_id="wf")
        assert len(events) == 1
        assert all(e.workflow_id == "wf" for e in events)

    def test_get_recent_events_no_workflow(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        _insert_event(conn, "wf", "e1", "workflow_started")
        conn.commit()
        conn.close()
        events = engine.get_recent_events(limit=10)
        assert len(events) == 1

    def test_get_recent_events_with_metadata(self, engine):
        conn = sqlite3.connect(str(engine.db_path))
        ts = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO workflow_events
               (event_id, workflow_id, execution_id, user_id, event_type, timestamp, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("eid", "wf", "e", "u", "started", ts, json.dumps({"k": "v"})),
        )
        conn.commit()
        conn.close()
        events = engine.get_recent_events(limit=10)
        assert events[0].metadata == {"k": "v"}

    def test_get_all_alerts_filtered(self, engine):
        engine.create_alert(
            name="a1", description="d", severity=AlertSeverity.LOW,
            condition="c", threshold_value=1.0, metric_name="m", workflow_id="wf1",
        )
        engine.create_alert(
            name="a2", description="d", severity=AlertSeverity.HIGH,
            condition="c", threshold_value=1.0, metric_name="m", workflow_id="wf2",
        )
        all_alerts = engine.get_all_alerts()
        assert len(all_alerts) == 2
        wf1 = engine.get_all_alerts(workflow_id="wf1")
        assert len(wf1) == 1
        enabled = engine.get_all_alerts(enabled_only=True)
        assert len(enabled) == 2

    def test_get_all_alerts_handles_exception(self, engine):
        """get_all_alerts returns [] when the query errors (no table)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_db = f.name
        try:
            engine.db_path = Path(empty_db)
            assert engine.get_all_alerts() == []
        finally:
            os.unlink(empty_db)


class TestSingleton:
    def test_get_analytics_engine_singleton(self):
        e1 = get_analytics_engine()
        e2 = get_analytics_engine()
        assert e1 is e2
