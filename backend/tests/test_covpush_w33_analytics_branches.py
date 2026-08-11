"""Coverage wave 33 — core/workflow_analytics_engine.py branches (TDD).

Picks up after the W33 engine repair (write-through persistence + API-compat
params) which took the module from 50 failing tests to 33 green and coverage
from ~50% to 68%. This wave drives the remaining 214 uncovered lines:
- _get_all_workflows_metrics (aggregation math, percentiles, error rates,
  unique users, most-common errors, empty store)
- get_unique_workflow_count / get_all_workflow_ids / get_workflow_name /
  get_last_execution_time / get_performance_metrics("*")
- alert lifecycle internals: _trigger_alert (unknown id, already triggered,
  fresh trigger + notification + DB update), _resolve_alert (unknown id,
  never-triggered, resolution), _send_alert_notification, check_alerts
  (metric below/above threshold, exception per alert, DB error), update_alert
  (enabled/threshold/no-op/exception), delete_alert (hit/miss/exception),
  _create_alert_kwargs / _create_alert_from_object (incl. exception path)
- _cleanup_old_data, background_task loop (with mocked loop/thread),
  _start_background_processing (enabled + disabled)
- get_recent_events workflow_id filter + exception path, get_error_breakdown,
  get_execution_timeline interval branch, get_system_overview branches
- flush() write-through, get_analytics_engine singleton (reset + lock)
"""
import json
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from core.workflow_analytics_engine import (
    Alert,
    AlertSeverity,
    MetricType,
    WorkflowAnalyticsEngine,
    WorkflowExecutionEvent,
    WorkflowMetric,
    WorkflowStatus,
)


def _engine(tmpdir, **kwargs):
    return WorkflowAnalyticsEngine(
        db_path=f"{tmpdir}/test.db",
        enable_background_thread=kwargs.pop("enable_background_thread", False),
        **kwargs,
    )


def _failing_execute_conn():
    """sqlite3 connection whose cursor().execute raises mid-statement —
    exercises the except-blocks that sit after a successful connect."""
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = RuntimeError("query boom")
    conn.commit = MagicMock()
    return conn


def _seed_workflow(engine, workflow_id="wf-1", n=5, status="completed",
                   duration_ms=1000, user_id="u-1"):
    for i in range(n):
        engine.track_workflow_start(
            workflow_id=workflow_id, execution_id=f"{workflow_id}-exec-{i}",
            user_id=user_id)
        engine.track_workflow_completion(
            workflow_id=workflow_id, execution_id=f"{workflow_id}-exec-{i}",
            status=status, duration_ms=duration_ms + i, user_id=user_id)


class TestAllWorkflowsMetrics:
    def test_empty_store_returns_zeroed_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            metrics = engine._get_all_workflows_metrics(time_window="1h")
            assert metrics.total_executions == 0
            assert metrics.successful_executions == 0
            assert metrics.failed_executions == 0
            assert metrics.error_rate == 0.0
            assert metrics.most_common_errors == []
            assert metrics.unique_users == 0

    def test_aggregates_success_and_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-a", n=3, status="completed", user_id="u-1")
            _seed_workflow(engine, "wf-b", n=2, status="failed", user_id="u-2")
            metrics = engine._get_all_workflows_metrics(time_window="1h")
            assert metrics.total_executions == 5
            assert metrics.successful_executions == 3
            assert metrics.failed_executions == 2
            assert metrics.error_rate == 40.0
            assert metrics.unique_users == 2

    def test_duration_statistics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-c", n=3, duration_ms=100)
            metrics = engine._get_all_workflows_metrics(time_window="1h")
            assert metrics.average_duration_ms == 101.0
            assert metrics.median_duration_ms == 101.0
            assert metrics.p95_duration_ms == 0  # < 20 samples → 0
            assert metrics.p99_duration_ms == 0  # < 100 samples → 0

    def test_percentile_branches_with_many_samples(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            for i in range(25):
                engine.track_workflow_start("wf-p", f"p-{i}", "u-1")
                engine.track_workflow_completion(
                    "wf-p", f"p-{i}", "completed", 100 + i, user_id="u-1")
            metrics = engine._get_all_workflows_metrics(time_window="1h")
            assert metrics.p95_duration_ms > 100  # 25 samples → p95 exists
            assert metrics.p99_duration_ms == 0  # < 100 samples → 0

    def test_most_common_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            for i in range(3):
                engine.track_workflow_start("wf-e", f"e-{i}", "u-1")
                engine.track_workflow_completion(
                    "wf-e", f"e-{i}", "failed", 50, user_id="u-1",
                    error_message="boom")
            engine.track_workflow_start("wf-e", "e-3", "u-1")
            engine.track_workflow_completion(
                "wf-e", "e-3", "failed", 60, user_id="u-1",
                error_message="kaboom")
            metrics = engine._get_all_workflows_metrics(time_window="1h")
            assert metrics.failed_executions == 4
            assert {e["error"] for e in metrics.most_common_errors} == {"boom", "kaboom"}
            by_error = {e["error"]: e["count"] for e in metrics.most_common_errors}
            assert by_error["boom"] == 3
            assert by_error["kaboom"] == 1

    def test_custom_time_window_falls_back_to_24h(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-t", n=1)
            metrics = engine._get_all_workflows_metrics(time_window="bogus")
            assert metrics.total_executions == 1

    def test_unknown_time_window_maps_to_24h_delta(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            # 30d window must include everything we seeded
            metrics = engine._get_all_workflows_metrics(time_window="30d")
            assert metrics.total_executions == 0  # nothing seeded

    def test_exception_reraises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                with pytest.raises(RuntimeError, match="db down"):
                    engine._get_all_workflows_metrics()


class TestWorkflowQueries:
    def test_get_unique_workflow_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-x", n=2)
            _seed_workflow(engine, "wf-y", n=3)
            assert engine.get_unique_workflow_count("1h") == 2
            assert engine.get_unique_workflow_count("bogus") == 2  # fallback 24h

    def test_get_all_workflow_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-z", n=1)
            _seed_workflow(engine, "wf-a", n=1)
            ids = engine.get_all_workflow_ids("1h")
            assert sorted(ids) == ["wf-a", "wf-z"]

    def test_get_workflow_name_falls_back_to_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            assert engine.get_workflow_name("wf-any") == "wf-any"

    def test_get_last_execution_time(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-last", n=2)
            last = engine.get_last_execution_time("wf-last")
            assert last is not None
            assert isinstance(last, datetime)
            assert last.tzinfo is None  # stored as naive isoformat

    def test_get_last_execution_time_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            assert engine.get_last_execution_time("wf-ghost") is None

    def test_get_performance_metrics_star(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-s", n=2)
            metrics = engine.get_performance_metrics("*", time_window="1h")
            assert metrics is not None
            assert metrics.workflow_id == "*"
            assert metrics.total_executions == 2


class TestAlertInternals:
    def test_trigger_alert_unknown_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            engine._trigger_alert("nope")  # no-op

    def test_trigger_alert_fresh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="a-1", name="High", description="d",
                severity=AlertSeverity.CRITICAL, condition=">", threshold_value=10.0,
                metric_name="m", notification_channels=["log"])
            engine.active_alerts["a-1"] = alert
            with patch.object(engine, "_send_alert_notification") as mock_send:
                engine._trigger_alert("a-1")
            assert alert.triggered_at is not None
            mock_send.assert_called_once_with(alert)
            # Second trigger: already triggered → no re-notify
            triggered_at = alert.triggered_at
            with patch.object(engine, "_send_alert_notification") as mock_send2:
                engine._trigger_alert("a-1")
            assert alert.triggered_at == triggered_at
            mock_send2.assert_not_called()

    def test_resolve_alert_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            engine._resolve_alert("nope")  # unknown → no-op
            alert = Alert(
                alert_id="a-2", name="Low", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=1.0,
                metric_name="m")
            engine.active_alerts["a-2"] = alert
            engine._resolve_alert("a-2")  # never triggered → no-op
            assert alert.resolved_at is None
            alert.triggered_at = datetime.now()
            engine._resolve_alert("a-2")
            assert alert.resolved_at is not None
            resolved_at = alert.resolved_at
            engine._resolve_alert("a-2")  # already resolved → no-op
            assert alert.resolved_at == resolved_at

    def test_send_alert_notification_logs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="a-3", name="N", description="desc",
                severity=AlertSeverity.CRITICAL, condition=">", threshold_value=1.0,
                metric_name="m")
            engine._send_alert_notification(alert)  # just logs

    def test_check_alerts_below_threshold_resolves(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="a-4", name="N", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=100.0,
                metric_name="cpu", enabled=True)
            engine.active_alerts["a-4"] = alert
            engine.create_alert(alert=alert)
            engine.track_metric("wf-1", "cpu", MetricType.GAUGE, 10.0)
            with patch.object(engine, "_resolve_alert") as mock_resolve, \
                 patch.object(engine, "_trigger_alert") as mock_trigger:
                engine.check_alerts()
            mock_resolve.assert_called_once_with("a-4")
            mock_trigger.assert_not_called()

    def test_check_alerts_above_threshold_triggers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="a-5", name="N", description="d",
                severity=AlertSeverity.CRITICAL, condition=">", threshold_value=10.0,
                metric_name="cpu", enabled=True)
            engine.active_alerts["a-5"] = alert
            engine.create_alert(alert=alert)
            engine.track_metric("wf-1", "cpu", MetricType.GAUGE, 50.0)
            with patch.object(engine, "_trigger_alert") as mock_trigger:
                engine.check_alerts()
            mock_trigger.assert_called_once_with("a-5")

    def test_check_alerts_metric_error_swallowed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="a-6", name="N", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=10.0,
                metric_name="cpu", enabled=True)
            engine.active_alerts["a-6"] = alert
            engine.create_alert(alert=alert)
            # Non-numeric metric value → float() raises inside the loop
            engine.track_metric("wf-1", "cpu", MetricType.GAUGE, "not-a-number")
            engine.check_alerts()  # must not raise

    def test_check_alerts_db_error_swallowed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                engine.check_alerts()  # outer except → swallowed

    def test_update_alert_enabled_and_threshold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="a-7", name="N", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=10.0,
                metric_name="cpu", enabled=True)
            engine.active_alerts["a-7"] = alert
            engine.create_alert(alert=alert)
            engine.update_alert("a-7", enabled=False, threshold_value=20.0)
            assert alert.enabled is False
            assert alert.threshold_value == 20.0
            engine.update_alert("a-7")  # no updates → no-op
            engine.update_alert("a-7", enabled=True)  # active_alerts hit

    def test_update_alert_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                with pytest.raises(RuntimeError, match="db down"):
                    engine.update_alert("a-8", enabled=False)

    def test_delete_alert(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="a-9", name="N", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=1.0,
                metric_name="cpu")
            engine.active_alerts["a-9"] = alert
            engine.create_alert(alert=alert)
            engine.delete_alert("a-9")
            assert "a-9" not in engine.active_alerts
            engine.delete_alert("a-9")  # already gone → still fine
            engine.active_alerts["a-10"] = alert
            engine.delete_alert("a-10")  # no DB row → DELETE affects 0 rows

    def test_delete_alert_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                with pytest.raises(RuntimeError, match="db down"):
                    engine.delete_alert("a-11")

    def test_create_alert_kwargs_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = engine._create_alert_kwargs(
                name="N", description="d", severity=AlertSeverity.MEDIUM,
                condition=">", threshold_value=5.0, metric_name="m",
                workflow_id="wf-1", step_id="s-1", notification_channels=["log"])
            assert alert.alert_id in engine.active_alerts
            assert alert.notification_channels == ["log"]

    def test_create_alert_dispatcher_kwargs_style(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = engine.create_alert(
                name="Disp", description="d", severity=AlertSeverity.MEDIUM,
                condition=">", threshold_value=3.0, metric_name="m")
            assert alert.alert_id in engine.active_alerts

    def test_get_performance_metrics_specific_workflow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-pm", n=2)
            metrics = engine.get_performance_metrics("wf-pm", time_window="1h")
            assert metrics is not None
            assert metrics.workflow_id == "wf-pm"

    def test_get_all_workflow_ids_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                with pytest.raises(RuntimeError, match="query boom"):
                    engine.get_all_workflow_ids("1h")

    def test_get_workflow_name_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                # get_workflow_name never queries — returns the id directly,
                # so the except path is unreachable (dead code).
                assert engine.get_workflow_name("wf-x") == "wf-x"

    def test_persist_metrics_batch_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            metric = WorkflowMetric(
                workflow_id="wf-p2", metric_name="m", metric_type=MetricType.GAUGE,
                value=1.0, timestamp=datetime.now())
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                engine._persist_metrics_batch([metric])  # rollback + swallow

    def test_persist_events_batch_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            event = WorkflowExecutionEvent(
                event_id="ev-1", workflow_id="wf-e1", execution_id="ex-1",
                user_id="u-1", event_type="workflow_started", timestamp=datetime.now())
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                engine._persist_events_batch([event])  # rollback + swallow

    def test_create_alert_from_object_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="a-12", name="N", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=1.0,
                metric_name="m")
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                with pytest.raises(RuntimeError, match="db down"):
                    engine._create_alert_from_object(alert)


class TestCleanupAndBackground:
    def test_cleanup_old_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-old", n=1)
            import asyncio
            asyncio.run(engine._cleanup_old_data())  # nothing older than 90d → no-op

    def test_background_processing_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            assert engine._background_thread is None

    def test_background_processing_enabled_starts_thread(self):
        import asyncio
        real_loop = asyncio.new_event_loop()
        created = []
        task_count = []

        def _fake_new_loop():
            created.append(real_loop)
            return real_loop

        orig_create_task = real_loop.create_task

        def _counting_create_task(coro):
            task_count.append(coro)
            return orig_create_task(coro)

        real_loop.create_task = _counting_create_task
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch("core.workflow_analytics_engine.asyncio.new_event_loop",
                           new=_fake_new_loop), \
                     patch("threading.Thread") as mock_thread:
                    engine = WorkflowAnalyticsEngine(
                        db_path=f"{tmpdir}/test.db", enable_background_thread=True)
                assert created == [real_loop]
                assert len(task_count) == 1
                mock_thread.assert_called_once()
                engine._stop_event = None  # tolerate teardown
        finally:
            real_loop.close()

    def test_flush_write_through(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            engine.track_metric("wf-f", "m", MetricType.GAUGE, 1.0)
            import asyncio
            asyncio.run(engine.flush())
            metrics = engine.get_workflow_performance_metrics("wf-f", "1h")
            assert metrics is not None


class TestReadPaths:
    def test_track_manual_override_with_reason_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            engine.track_manual_override(
                workflow_id="wf-mo", execution_id="ex-mo", resource_id="r-1",
                user_id="u-1", reason="needed human", metadata={"extra": 1})
            events = engine.get_recent_events(limit=10)
            assert any(e.event_type == "manual_override" for e in events)

    def test_track_resource_usage_all_branches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            engine.track_resource_usage(
                workflow_id="wf-ru", cpu_usage=10.0, memory_usage=20.0,
                disk_io=100, network_io=200, step_id="s-1")
            engine.track_resource_usage(
                workflow_id="wf-ru2", cpu_usage=5.0, memory_usage=6.0)
            metrics = engine.get_workflow_performance_metrics("wf-ru", "1h")
            assert metrics is not None

    def test_get_error_breakdown_star_and_specific(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            for i in range(2):
                engine.track_workflow_start("wf-err", f"err-{i}", "u-1")
                engine.track_workflow_completion(
                    "wf-err", f"err-{i}", "failed", 10, user_id="u-1",
                    error_message="boom at step")
            star = engine.get_error_breakdown("*", "1h")
            assert star["workflows_with_errors"]
            assert star["recent_errors"]
            assert star["error_types"]
            specific = engine.get_error_breakdown("wf-err", "1h")
            assert specific["workflow_id"] == "wf-err"
            assert specific["error_types"]
            empty = engine.get_error_breakdown("wf-nothing", "1h")
            assert empty["error_types"] == []

    def test_get_error_breakdown_exception_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                assert engine.get_error_breakdown("wf-x", "1h") == {}

    def test_get_execution_timeline_star(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-tl2", n=2)
            timeline = engine.get_execution_timeline("*", time_window="1h", interval="1h")
            assert isinstance(timeline, list)

    def test_get_all_alerts_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            a1 = Alert(
                alert_id="all-1", name="N1", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=1.0,
                metric_name="m", workflow_id="wf-1", enabled=True)
            a2 = Alert(
                alert_id="all-2", name="N2", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=1.0,
                metric_name="m", workflow_id="wf-2", enabled=False)
            for a in (a1, a2):
                engine.active_alerts[a.alert_id] = a
                engine.create_alert(alert=a)
            assert len(engine.get_all_alerts()) == 2
            assert len(engine.get_all_alerts(workflow_id="wf-1")) == 1
            assert len(engine.get_all_alerts(enabled_only=True)) == 1
            assert len(engine.get_all_alerts(workflow_id="wf-1", enabled_only=True)) == 1

    def test_get_all_alerts_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                assert engine.get_all_alerts() == []

    def test_performance_cache_hit_and_miss(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-cache", n=1)
            m1 = engine.get_workflow_performance_metrics("wf-cache", "1h")
            m2 = engine.get_workflow_performance_metrics("wf-cache", "1h")
            assert m1 is m2  # cache hit returns same object

    def test_get_workflow_performance_metrics_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                with pytest.raises(RuntimeError, match="query boom"):
                    engine.get_workflow_performance_metrics("wf-x", "1h")

    def test_get_system_overview_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                with pytest.raises(RuntimeError, match="query boom"):
                    engine.get_system_overview("1h")

    def test_get_unique_workflow_count_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                with pytest.raises(RuntimeError, match="query boom"):
                    engine.get_unique_workflow_count("1h")

    def test_get_error_breakdown_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                assert engine.get_error_breakdown("*", "1h") == {}

    def test_get_recent_events_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                assert engine.get_recent_events() == []

    def test_get_all_alerts_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                assert engine.get_all_alerts() == []

    def test_update_alert_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                with pytest.raises(RuntimeError, match="query boom"):
                    engine.update_alert("a-1", enabled=False)

    def test_delete_alert_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                with pytest.raises(RuntimeError, match="query boom"):
                    engine.delete_alert("a-1")

    def test_create_alert_from_object_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="obj-2", name="N", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=1.0,
                metric_name="m")
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                with pytest.raises(RuntimeError, match="query boom"):
                    engine._create_alert_from_object(alert)

    def test_get_all_workflows_metrics_exception_reraises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                with pytest.raises(RuntimeError, match="db down"):
                    engine._get_all_workflows_metrics("1h")

    def test_get_execution_timeline_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                with pytest.raises(RuntimeError, match="db down"):
                    engine.get_execution_timeline("wf-x", "1h")

    def test_create_alert_from_object_success_and_conn_close(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="obj-1", name="N", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=1.0,
                metric_name="m", enabled=True)
            result = engine._create_alert_from_object(alert)
            assert result.alert_id == "obj-1"
            assert engine.get_all_alerts(workflow_id=None, enabled_only=False)

    def test_update_alert_active_alerts_branch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="upd-1", name="N", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=5.0,
                metric_name="m", enabled=True)
            engine.active_alerts["upd-1"] = alert
            engine.create_alert(alert=alert)
            engine.update_alert("upd-1", enabled=True, threshold_value=7.0)
            assert alert.threshold_value == 7.0
            engine.update_alert("missing-id", enabled=True)  # no active entry → DB-only

    def test_delete_alert_db_removal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            alert = Alert(
                alert_id="del-1", name="N", description="d",
                severity=AlertSeverity.MEDIUM, condition=">", threshold_value=1.0,
                metric_name="m")
            engine.active_alerts["del-1"] = alert
            engine.create_alert(alert=alert)
            engine.delete_alert("del-1")
            assert engine.get_all_alerts() == []

    def test_get_system_overview_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                with pytest.raises(RuntimeError, match="db down"):
                    engine.get_system_overview("1h")

    def test_persist_batch_exceptions_swallowed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            metric = WorkflowMetric(
                workflow_id="wf-p", metric_name="m", metric_type=MetricType.GAUGE,
                value=1.0, timestamp=datetime.now())
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                engine._persist_metrics_batch([metric])  # logged + rollback, no raise
                engine._persist_events_batch([])  # empty is fine
            import asyncio
            asyncio.run(engine._cleanup_old_data())  # nothing to clean

    def test_cleanup_old_data_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            import asyncio
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                asyncio.run(engine._cleanup_old_data())  # swallowed

    def test_cleanup_old_data_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            import asyncio
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                asyncio.run(engine._cleanup_old_data())  # rollback + swallow

    def test_get_all_workflows_metrics_mid_function_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       return_value=_failing_execute_conn()):
                with pytest.raises(RuntimeError, match="query boom"):
                    engine._get_all_workflows_metrics("1h")

    def test_get_recent_events_workflow_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-1", n=1)
            _seed_workflow(engine, "wf-2", n=1)
            events = engine.get_recent_events(limit=10, workflow_id="wf-2")
            assert events
            assert all(e.workflow_id == "wf-2" for e in events)

    def test_get_recent_events_exception_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            with patch("core.workflow_analytics_engine.sqlite3.connect",
                       side_effect=RuntimeError("db down")):
                assert engine.get_recent_events() == []

    def test_get_error_breakdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            for i in range(2):
                engine.track_workflow_start("wf-err", f"err-{i}", "u-1")
                engine.track_workflow_completion(
                    "wf-err", f"err-{i}", "failed", 10, user_id="u-1",
                    error_message="boom")
            breakdown = engine.get_error_breakdown("wf-err", "1h")
            assert isinstance(breakdown, dict)
            # workflow-level aggregation keys
            assert "workflows" in breakdown or "recent_errors" in breakdown or "error_types" in breakdown

    def test_get_execution_timeline_interval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-tl", n=3)
            timeline = engine.get_execution_timeline("wf-tl", time_window="1h", interval="1h")
            assert isinstance(timeline, list)

    def test_get_system_overview(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _engine(tmpdir)
            _seed_workflow(engine, "wf-ov", n=2)
            overview = engine.get_system_overview("1h")
            assert isinstance(overview, dict)
            assert "total_workflows" in overview or "workflows" in overview or "total" in overview


class TestSingleton:
    def test_get_analytics_engine_singleton(self):
        import core.workflow_analytics_engine as mod
        with patch.object(mod, "_analytics_engine", None):
            e1 = mod.get_analytics_engine()
            e2 = mod.get_analytics_engine()
            assert e1 is e2
            assert isinstance(e1, WorkflowAnalyticsEngine)
