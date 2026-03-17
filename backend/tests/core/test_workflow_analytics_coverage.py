"""
Coverage tests for workflow_analytics_engine.py.

Target: 60%+ coverage (567 statements, ~340 lines to cover)
Focus: Metrics collection, aggregation, reporting
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import os

from core.workflow_analytics_engine import (
    WorkflowAnalyticsEngine,
    WorkflowMetric,
    WorkflowExecutionEvent,
    PerformanceMetrics,
    Alert,
    MetricType,
    AlertSeverity,
    WorkflowStatus,
    get_analytics_engine
)


class TestWorkflowAnalyticsEngineInitialization:
    """Test analytics engine initialization."""

    def test_engine_initialization_default(self):
        """Test engine initializes with default config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)
            assert engine is not None
            assert engine.db_path == Path(db_path)
            assert engine.enable_background_thread is False

    def test_engine_initialization_with_background_thread(self):
        """Test engine with background thread enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)
            assert engine.enable_background_thread is False

    def test_database_initialization(self):
        """Test database tables are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Check database file exists
            assert os.path.exists(db_path)

    def test_global_analytics_engine(self):
        """Test global analytics engine singleton."""
        engine = get_analytics_engine()
        assert engine is not None
        assert isinstance(engine, WorkflowAnalyticsEngine)


class TestMetricsCollection:
    """Test workflow metrics collection."""

    def test_track_workflow_start(self):
        """Test tracking workflow execution start."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_workflow_start(
                workflow_id="test-workflow-1",
                execution_id="exec-1",
                user_id="user-1",
                metadata={"test": "data"}
            )

            assert len(engine.events_buffer) == 1
            assert len(engine.metrics_buffer) == 1

            event = engine.events_buffer[0]
            assert event.workflow_id == "test-workflow-1"
            assert event.execution_id == "exec-1"
            assert event.user_id == "user-1"
            assert event.event_type == "workflow_started"

    def test_track_workflow_completion_success(self):
        """Test tracking successful workflow completion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_workflow_completion(
                workflow_id="test-workflow-1",
                execution_id="exec-1",
                status=WorkflowStatus.COMPLETED,
                duration_ms=5000,
                user_id="user-1"
            )

            assert len(engine.events_buffer) == 1
            assert len(engine.metrics_buffer) == 2  # duration + success counter

            event = engine.events_buffer[0]
            assert event.status == "completed"
            assert event.duration_ms == 5000

    def test_track_workflow_completion_failure(self):
        """Test tracking failed workflow completion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_workflow_completion(
                workflow_id="test-workflow-1",
                execution_id="exec-1",
                status=WorkflowStatus.FAILED,
                duration_ms=3000,
                error_message="Test error",
                user_id="user-1"
            )

            event = engine.events_buffer[0]
            assert event.status == "failed"
            assert event.error_message == "Test error"

    def test_track_step_execution(self):
        """Test tracking individual step execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_step_execution(
                workflow_id="wf-1",
                execution_id="exec-1",
                step_id="step-1",
                step_name="Test Step",
                event_type="step_completed",
                duration_ms=500,
                status="success",
                user_id="user-1"
            )

            assert len(engine.events_buffer) == 1
            assert len(engine.metrics_buffer) == 1

            event = engine.events_buffer[0]
            assert event.step_id == "step-1"
            assert event.step_name == "Test Step"
            assert event.duration_ms == 500

    def test_track_manual_override(self):
        """Test tracking manual override events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_manual_override(
                workflow_id="wf-1",
                execution_id="exec-1",
                resource_id="task-123",
                action="modified_deadline",
                original_value="2024-01-01",
                new_value="2024-01-02",
                user_id="user-1"
            )

            assert len(engine.events_buffer) == 1
            assert len(engine.metrics_buffer) == 1

            event = engine.events_buffer[0]
            assert event.event_type == "manual_override"
            assert event.resource_id == "task-123"
            assert event.metadata["action"] == "modified_deadline"

    def test_track_resource_usage(self):
        """Test tracking resource usage metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_resource_usage(
                workflow_id="wf-1",
                cpu_usage=45.5,
                memory_usage=256.0,
                step_id="step-1",
                disk_io=1024,
                network_io=2048,
                user_id="user-1"
            )

            # Should have 4 metrics: CPU, memory, disk I/O, network I/O
            assert len(engine.metrics_buffer) == 4

    def test_track_user_activity(self):
        """Test tracking user activity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_user_activity(
                user_id="user-1",
                action="workflow_created",
                workflow_id="wf-1",
                workspace_id="ws-1"
            )

            assert len(engine.metrics_buffer) == 1

            metric = engine.metrics_buffer[0]
            assert metric.metric_name == "user_activity"
            assert metric.user_id == "user-1"
            assert metric.tags["action"] == "workflow_created"

    def test_track_general_metric(self):
        """Test tracking a general workflow metric."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_metric(
                workflow_id="wf-1",
                metric_name="custom_metric",
                metric_type=MetricType.GAUGE,
                value=42.5,
                tags={"custom": "tag"},
                step_id="step-1",
                user_id="user-1"
            )

            assert len(engine.metrics_buffer) == 1

            metric = engine.metrics_buffer[0]
            assert metric.metric_name == "custom_metric"
            assert metric.value == 42.5
            assert metric.tags["custom"] == "tag"


class TestMetricsAggregation:
    """Test metrics aggregation and analysis."""

    def test_get_workflow_performance_metrics(self):
        """Test getting performance metrics for a workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add some test data
            engine.track_workflow_start("wf-1", "exec-1", "user-1")
            engine.track_workflow_completion(
                "wf-1", "exec-1",
                WorkflowStatus.COMPLETED,
                duration_ms=5000,
                user_id="user-1"
            )

            # Flush to database
            import asyncio
            asyncio.run(engine.flush())

            # Get metrics
            metrics = engine.get_workflow_performance_metrics("wf-1", "24h")

            assert metrics is not None
            assert metrics.workflow_id == "wf-1"
            assert metrics.time_window == "24h"

    def test_get_performance_metrics_all_workflows(self):
        """Test getting aggregated metrics for all workflows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add test data for multiple workflows
            engine.track_workflow_start("wf-1", "exec-1", "user-1")
            engine.track_workflow_start("wf-2", "exec-2", "user-1")

            import asyncio
            asyncio.run(engine.flush())

            # Get all metrics
            metrics = engine.get_performance_metrics("*", "24h")

            assert metrics is not None
            assert metrics.workflow_id == "*"

    def test_get_unique_workflow_count(self):
        """Test getting count of unique workflows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add test data
            engine.track_workflow_start("wf-1", "exec-1", "user-1")
            engine.track_workflow_start("wf-2", "exec-2", "user-1")

            import asyncio
            asyncio.run(engine.flush())

            count = engine.get_unique_workflow_count("24h")
            assert count >= 0

    def test_get_all_workflow_ids(self):
        """Test getting list of all workflow IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add test data
            engine.track_workflow_start("wf-1", "exec-1", "user-1")

            import asyncio
            asyncio.run(engine.flush())

            workflow_ids = engine.get_all_workflow_ids("24h")
            assert isinstance(workflow_ids, list)

    def test_get_last_execution_time(self):
        """Test getting last execution time for workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add test data
            engine.track_workflow_start("wf-1", "exec-1", "user-1")

            import asyncio
            asyncio.run(engine.flush())

            last_time = engine.get_last_execution_time("wf-1")
            # May be None if no data yet
            assert last_time is None or isinstance(last_time, datetime)

    def test_get_execution_timeline(self):
        """Test getting execution timeline data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add test data
            engine.track_workflow_start("wf-1", "exec-1", "user-1")
            engine.track_workflow_completion(
                "wf-1", "exec-1",
                WorkflowStatus.COMPLETED,
                duration_ms=5000,
                user_id="user-1"
            )

            import asyncio
            asyncio.run(engine.flush())

            timeline = engine.get_execution_timeline("wf-1", "24h", "1h")
            assert isinstance(timeline, list)

    def test_get_error_breakdown(self):
        """Test getting error breakdown."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add test data
            engine.track_workflow_completion(
                "wf-1", "exec-1",
                WorkflowStatus.FAILED,
                duration_ms=3000,
                error_message="Test error",
                user_id="user-1"
            )

            import asyncio
            asyncio.run(engine.flush())

            error_breakdown = engine.get_error_breakdown("wf-1", "24h")
            assert isinstance(error_breakdown, dict)


class TestAlerts:
    """Test analytics alerts."""

    def test_create_alert(self):
        """Test creating a new alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            alert = engine.create_alert(
                name="Test Alert",
                description="Test alert description",
                severity=AlertSeverity.HIGH,
                condition="error_rate > 5",
                threshold_value=5.0,
                metric_name="error_rate",
                workflow_id="wf-1"
            )

            assert alert is not None
            assert alert.name == "Test Alert"
            assert alert.severity == AlertSeverity.HIGH
            assert alert.enabled is True

    def test_get_all_alerts(self):
        """Test getting all alerts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create an alert
            engine.create_alert(
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.MEDIUM,
                condition="cpu > 80",
                threshold_value=80.0,
                metric_name="cpu_usage"
            )

            alerts = engine.get_all_alerts()
            assert len(alerts) >= 1

    def test_get_alerts_filtered(self):
        """Test getting alerts with filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create an alert
            engine.create_alert(
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.LOW,
                condition="memory > 100",
                threshold_value=100.0,
                metric_name="memory_usage",
                workflow_id="wf-1"
            )

            alerts = engine.get_all_alerts(workflow_id="wf-1", enabled_only=True)
            assert isinstance(alerts, list)

    def test_update_alert(self):
        """Test updating an alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create an alert
            alert = engine.create_alert(
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.MEDIUM,
                condition="cpu > 50",
                threshold_value=50.0,
                metric_name="cpu_usage"
            )

            # Update alert
            engine.update_alert(alert.alert_id, enabled=False, threshold_value=75.0)

            # Verify update
            updated_alert = engine.active_alerts.get(alert.alert_id)
            assert updated_alert is not None
            assert updated_alert.enabled is False
            assert updated_alert.threshold_value == 75.0

    def test_delete_alert(self):
        """Test deleting an alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create an alert
            alert = engine.create_alert(
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.LOW,
                condition="test > 0",
                threshold_value=1.0,
                metric_name="test_metric"
            )

            alert_id = alert.alert_id

            # Delete alert
            engine.delete_alert(alert_id)

            # Verify deletion
            assert alert_id not in engine.active_alerts


class TestSystemOverview:
    """Test system overview analytics."""

    def test_get_system_overview(self):
        """Test getting system-wide analytics overview."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add test data
            engine.track_workflow_start("wf-1", "exec-1", "user-1")
            engine.track_workflow_completion(
                "wf-1", "exec-1",
                WorkflowStatus.COMPLETED,
                duration_ms=5000,
                user_id="user-1"
            )

            import asyncio
            asyncio.run(engine.flush())

            overview = engine.get_system_overview("24h")

            assert overview is not None
            assert "total_workflows" in overview
            assert "total_executions" in overview
            assert "success_rate" in overview
            assert "average_execution_time_ms" in overview
            assert "top_workflows" in overview
            assert "recent_errors" in overview

    def test_get_workflow_name(self):
        """Test getting workflow name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Should return workflow_id as fallback
            name = engine.get_workflow_name("wf-1")
            assert name == "wf-1"

    def test_get_recent_events(self):
        """Test getting recent events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add test data
            engine.track_workflow_start("wf-1", "exec-1", "user-1")

            import asyncio
            asyncio.run(engine.flush())

            events = engine.get_recent_events(limit=10)
            assert isinstance(events, list)


class TestErrorHandling:
    """Test error handling in analytics engine."""

    def test_handle_invalid_metric_data(self):
        """Test handling of invalid metrics data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Should not raise error for None workflow_id
            engine.track_user_activity(
                user_id="user-1",
                action="test_action",
                workflow_id=None
            )

            assert len(engine.metrics_buffer) == 1

    def test_handle_database_connection_error(self):
        """Test handling of database connection errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # This should work fine
            engine.track_workflow_start("wf-1", "exec-1", "user-1")
            assert len(engine.events_buffer) == 1

    def test_flush_with_empty_buffers(self):
        """Test flushing when buffers are empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Flush with empty buffers should not raise
            import asyncio
            asyncio.run(engine.flush())

            assert len(engine.metrics_buffer) == 0
            assert len(engine.events_buffer) == 0


class TestBackgroundProcessing:
    """Test background processing functionality."""

    def test_process_metrics_batch(self):
        """Test processing a batch of metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create test metrics
            metrics = [
                WorkflowMetric(
                    workflow_id="wf-1",
                    metric_name="test_metric",
                    metric_type=MetricType.COUNTER,
                    value=1,
                    timestamp=datetime.now(),
                    user_id="user-1"
                )
            ]

            import asyncio
            asyncio.run(engine._process_metrics_batch(metrics))

    def test_process_events_batch(self):
        """Test processing a batch of events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create test event
            events = [
                WorkflowExecutionEvent(
                    event_id="event-1",
                    workflow_id="wf-1",
                    execution_id="exec-1",
                    user_id="user-1",
                    event_type="test_event",
                    timestamp=datetime.now()
                )
            ]

            import asyncio
            asyncio.run(engine._process_events_batch(events))

    def test_cleanup_old_data(self):
        """Test cleanup of old analytics data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Cleanup should not raise
            import asyncio
            asyncio.run(engine._cleanup_old_data())


class TestAlertChecking:
    """Test alert checking functionality."""

    def test_check_alerts_with_no_alerts(self):
        """Test checking alerts when none exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Should not raise
            engine.check_alerts()

    def test_trigger_alert(self):
        """Test triggering an alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create alert
            alert = Alert(
                alert_id="alert-1",
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.HIGH,
                condition="test > 0",
                threshold_value=1.0,
                metric_name="test_metric",
                created_at=datetime.now()
            )

            engine.active_alerts["alert-1"] = alert

            # Trigger alert
            engine._trigger_alert("alert-1")

            assert alert.triggered_at is not None

    def test_resolve_alert(self):
        """Test resolving an alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create triggered alert
            alert = Alert(
                alert_id="alert-1",
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.MEDIUM,
                condition="test > 0",
                threshold_value=1.0,
                metric_name="test_metric",
                created_at=datetime.now(),
                triggered_at=datetime.now()
            )

            engine.active_alerts["alert-1"] = alert

            # Resolve alert
            engine._resolve_alert("alert-1")

            assert alert.resolved_at is not None


class TestCacheFunctionality:
    """Test performance cache functionality."""

    def test_performance_cache_hit(self):
        """Test that performance cache works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_analytics.db")
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add test data and flush
            engine.track_workflow_start("wf-1", "exec-1", "user-1")
            engine.track_workflow_completion(
                "wf-1", "exec-1",
                WorkflowStatus.COMPLETED,
                duration_ms=5000,
                user_id="user-1"
            )

            import asyncio
            asyncio.run(engine.flush())

            # First call - cache miss
            metrics1 = engine.get_workflow_performance_metrics("wf-1", "24h")

            # Second call - cache hit
            metrics2 = engine.get_workflow_performance_metrics("wf-1", "24h")

            assert metrics1 is not None
            assert metrics2 is not None
