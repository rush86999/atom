"""
Coverage-driven tests for WorkflowAnalyticsEngine (currently 0% -> target 80%+)

Focus areas from workflow_analytics_engine.py:
- AnalyticsEngine initialization (lines ~122-143)
- Alert management (lines 670-711, 1315-1362)
- Dataclass models (WorkflowMetric, WorkflowExecutionEvent, PerformanceMetrics, Alert)
- Database initialization (lines 145-227)
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from core.workflow_analytics_engine import (
    WorkflowAnalyticsEngine,
    WorkflowMetric,
    WorkflowExecutionEvent,
    PerformanceMetrics,
    Alert,
    MetricType,
    AlertSeverity,
    WorkflowStatus,
)


class TestAnalyticsEngineInit:
    """Test WorkflowAnalyticsEngine initialization (lines 122-143)."""

    def test_init_default_config(self):
        """Cover default initialization."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)
            assert engine.db_path == Path(db_path).expanduser().absolute()
            assert len(engine.metrics_buffer) == 0
            assert len(engine.events_buffer) == 0
            assert len(engine.performance_cache) == 0
            assert engine.cache_ttl == 300
            assert len(engine.active_alerts) == 0
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_database_initialization(self):
        """Cover database table creation (lines 145-227)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Verify database file exists
            assert Path(db_path).exists()

            # Verify tables were created
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            conn.close()

            # Should have created at least workflow_metrics, workflow_events, analytics_alerts tables
            assert len(tables) >= 3
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestDataclassModels:
    """Test dataclass model definitions."""

    def test_workflow_metric_dataclass(self):
        """Cover WorkflowMetric dataclass (lines 41-52)."""
        metric = WorkflowMetric(
            workflow_id="test-wf",
            metric_name="test_metric",
            metric_type=MetricType.COUNTER,
            value=42,
            timestamp=datetime.now(),
            step_id="step1",
            step_name="Step 1",
            user_id="user1"
        )

        assert metric.workflow_id == "test-wf"
        assert metric.metric_name == "test_metric"
        assert metric.metric_type == MetricType.COUNTER
        assert metric.value == 42
        assert metric.step_id == "step1"
        assert metric.user_id == "user1"

    def test_workflow_execution_event_dataclass(self):
        """Cover WorkflowExecutionEvent dataclass (lines 54-69)."""
        event = WorkflowExecutionEvent(
            event_id="event-1",
            workflow_id="test-wf",
            execution_id="exec-1",
            event_type="completed",
            timestamp=datetime.now(),
            step_id="step1",
            step_name="Step 1",
            duration_ms=1000,
            status="completed",
            error_message=None,
            metadata={"key": "value"},
            resource_id="resource-1",
            user_id="user1"
        )

        assert event.event_id == "event-1"
        assert event.workflow_id == "test-wf"
        assert event.execution_id == "exec-1"
        assert event.event_type == "completed"
        assert event.duration_ms == 1000
        assert event.status == "completed"
        assert event.resource_id == "resource-1"
        assert event.user_id == "user1"

    def test_performance_metrics_dataclass(self):
        """Cover PerformanceMetrics dataclass (lines 71-99)."""
        metrics = PerformanceMetrics(
            workflow_id="test-wf",
            time_window="24h",
            total_executions=100,
            successful_executions=95,
            failed_executions=5,
            average_duration_ms=1500.0,
            median_duration_ms=1400.0,
            p95_duration_ms=2000.0,
            p99_duration_ms=2500.0,
            error_rate=0.05,
            most_common_errors=[{"error": "timeout", "count": 5}],
            average_cpu_usage=50.0,
            peak_memory_usage=1024.0,
            average_step_duration={"step1": 500.0},
            unique_users=10,
            executions_by_user={"user1": 50, "user2": 50},
            timestamp=datetime.now()
        )

        assert metrics.workflow_id == "test-wf"
        assert metrics.time_window == "24h"
        assert metrics.total_executions == 100
        assert metrics.successful_executions == 95
        assert metrics.failed_executions == 5
        assert metrics.error_rate == 0.05
        assert metrics.unique_users == 10

    def test_alert_dataclass(self):
        """Cover Alert dataclass (lines 101-117)."""
        alert = Alert(
            alert_id="alert-1",
            name="High Error Rate",
            description="Error rate exceeds 10%",
            severity=AlertSeverity.HIGH,
            condition="error_rate > 0.1",
            threshold_value=0.1,
            metric_name="error_rate",
            workflow_id="test-wf",
            step_id="step1",
            enabled=True,
            created_at=datetime.now(),
            triggered_at=None,
            resolved_at=None,
            notification_channels=["email", "slack"]
        )

        assert alert.alert_id == "alert-1"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.enabled is True
        assert alert.triggered_at is None
        assert alert.resolved_at is None


class TestEnumTypes:
    """Test enum type definitions."""

    def test_metric_type_enum(self):
        """Cover MetricType enum (lines 21-25)."""
        assert MetricType.COUNTER == "counter"
        assert MetricType.GAUGE == "gauge"
        assert MetricType.HISTOGRAM == "histogram"
        assert MetricType.TIMER == "timer"

    def test_alert_severity_enum(self):
        """Cover AlertSeverity enum (lines 27-31)."""
        assert AlertSeverity.LOW == "low"
        assert AlertSeverity.MEDIUM == "medium"
        assert AlertSeverity.HIGH == "high"
        assert AlertSeverity.CRITICAL == "critical"

    def test_workflow_status_enum(self):
        """Cover WorkflowStatus enum (lines 33-39)."""
        assert WorkflowStatus.RUNNING == "running"
        assert WorkflowStatus.COMPLETED == "completed"
        assert WorkflowStatus.FAILED == "failed"
        assert WorkflowStatus.PAUSED == "paused"
        assert WorkflowStatus.CANCELLED == "cancelled"
        assert WorkflowStatus.TIMEOUT == "timeout"


class TestAlertManagement:
    """Test alert dataclass and alert-related functionality."""

    def test_alert_dataclass_instantiation(self):
        """Cover Alert dataclass instantiation (lines 101-117)."""
        alert = Alert(
            alert_id="alert-1",
            name="High Error Rate",
            description="Error rate exceeds 10%",
            severity=AlertSeverity.HIGH,
            condition="error_rate > 0.1",
            threshold_value=0.1,
            metric_name="error_rate",
            workflow_id="test-wf",
            step_id="step1",
            enabled=True,
            created_at=datetime.now(),
            triggered_at=None,
            resolved_at=None,
            notification_channels=["email", "slack"]
        )

        assert alert.alert_id == "alert-1"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.enabled is True
        assert alert.triggered_at is None
        assert alert.resolved_at is None

    @pytest.mark.parametrize("severity", [
        AlertSeverity.LOW,
        AlertSeverity.MEDIUM,
        AlertSeverity.HIGH,
        AlertSeverity.CRITICAL,
    ])
    def test_alert_with_severities(self, severity):
        """Cover alert creation with different severity levels."""
        alert = Alert(
            alert_id=f"alert-{severity.value}",
            name=f"Alert {severity.value}",
            description=f"Test {severity} alert",
            severity=severity,
            condition="true",
            threshold_value=1,
            metric_name="test_metric"
        )

        assert alert.severity == severity


class TestWorkflowTracking:
    """Test workflow execution tracking methods."""

    def test_track_workflow_start(self):
        """Cover track_workflow_start (lines 229-254)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track workflow start
            engine.track_workflow_start(
                workflow_id="test-wf",
                execution_id="exec-1",
                user_id="user1",
                metadata={"key": "value"}
            )

            # Verify event was added to buffer
            assert len(engine.events_buffer) == 1
            event = engine.events_buffer[0]
            assert event.workflow_id == "test-wf"
            assert event.execution_id == "exec-1"
            assert event.event_type == "workflow_started"
            assert event.user_id == "user1"
            assert event.metadata == {"key": "value"}

            # Verify metric was added to buffer
            assert len(engine.metrics_buffer) == 1
            metric = engine.metrics_buffer[0]
            assert metric.workflow_id == "test-wf"
            assert metric.metric_name == "workflow_executions"
            assert metric.metric_type == MetricType.COUNTER
            assert metric.value == 1
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_track_workflow_completion_success(self):
        """Cover track_workflow_completion with success (lines 256-299)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track successful completion
            engine.track_workflow_completion(
                workflow_id="test-wf",
                execution_id="exec-1",
                status=WorkflowStatus.COMPLETED,
                duration_ms=5000,
                step_outputs={"step1": "result"},
                user_id="user1"
            )

            # Verify event was added
            assert len(engine.events_buffer) == 1
            event = engine.events_buffer[0]
            assert event.event_type == "workflow_completed"
            assert event.status == "completed"
            assert event.duration_ms == 5000

            # Verify metrics
            assert len(engine.metrics_buffer) == 2
            duration_metric = engine.metrics_buffer[0]
            assert duration_metric.metric_name == "execution_duration_ms"
            assert duration_metric.value == 5000

            success_metric = engine.metrics_buffer[1]
            assert success_metric.metric_name == "successful_executions"
            assert success_metric.value == 1
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_track_workflow_completion_failure(self):
        """Cover track_workflow_completion with failure."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track failed completion
            engine.track_workflow_completion(
                workflow_id="test-wf",
                execution_id="exec-2",
                status=WorkflowStatus.FAILED,
                duration_ms=3000,
                error_message="Step failed",
                user_id="user2"
            )

            # Verify event
            assert len(engine.events_buffer) == 1
            event = engine.events_buffer[0]
            assert event.status == "failed"
            assert event.error_message == "Step failed"

            # Verify metrics
            assert len(engine.metrics_buffer) == 2
            failed_metric = engine.metrics_buffer[1]
            assert failed_metric.metric_name == "failed_executions"
            assert failed_metric.value == 1
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_track_step_execution(self):
        """Cover track_step_execution (lines 301-334)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track step execution
            engine.track_step_execution(
                workflow_id="test-wf",
                execution_id="exec-1",
                step_id="step-1",
                step_name="Data Processing",
                event_type="step_completed",
                duration_ms=1000,
                status="completed",
                user_id="user1"
            )

            # Verify event
            assert len(engine.events_buffer) == 1
            event = engine.events_buffer[0]
            assert event.event_type == "step_completed"
            assert event.step_id == "step-1"
            assert event.step_name == "Data Processing"
            assert event.duration_ms == 1000

            # Verify metric
            assert len(engine.metrics_buffer) == 1
            metric = engine.metrics_buffer[0]
            assert metric.metric_name == "step_duration_ms"
            assert metric.value == 1000
            assert metric.tags == {"step_id": "step-1", "step_name": "Data Processing", "event_type": "step_completed"}
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_track_manual_override(self):
        """Cover track_manual_override (lines 336-367)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track manual override
            engine.track_manual_override(
                workflow_id="test-wf",
                execution_id="exec-1",
                resource_id="task-123",
                action="modified_deadline",
                original_value="2026-03-15",
                new_value="2026-03-16",
                user_id="user1"
            )

            # Verify event
            assert len(engine.events_buffer) == 1
            event = engine.events_buffer[0]
            assert event.event_type == "manual_override"
            assert event.resource_id == "task-123"
            assert event.metadata == {
                "action": "modified_deadline",
                "original_value": "2026-03-15",
                "new_value": "2026-03-16"
            }
            assert event.status == "OVERRIDDEN"

            # Verify counter metric
            assert len(engine.metrics_buffer) == 1
            metric = engine.metrics_buffer[0]
            assert metric.metric_name == "manual_override_count"
            assert metric.value == 1
            assert metric.tags == {"resource_id": "task-123", "action": "modified_deadline"}
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_track_resource_usage(self):
        """Cover track_resource_usage (lines 369-424)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track resource usage
            engine.track_resource_usage(
                workflow_id="test-wf",
                cpu_usage=75.5,
                memory_usage=1024.0,
                step_id="step-1",
                disk_io=5000000,
                network_io=1000000,
                user_id="user1"
            )

            # Verify metrics
            assert len(engine.metrics_buffer) == 4

            # CPU metric
            cpu_metric = engine.metrics_buffer[0]
            assert cpu_metric.metric_name == "cpu_usage_percent"
            assert cpu_metric.value == 75.5
            assert cpu_metric.metric_type == MetricType.GAUGE

            # Memory metric
            memory_metric = engine.metrics_buffer[1]
            assert memory_metric.metric_name == "memory_usage_mb"
            assert memory_metric.value == 1024.0

            # Disk I/O metric
            disk_metric = engine.metrics_buffer[2]
            assert disk_metric.metric_name == "disk_io_bytes"
            assert disk_metric.value == 5000000

            # Network I/O metric
            network_metric = engine.metrics_buffer[3]
            assert network_metric.metric_name == "network_io_bytes"
            assert network_metric.value == 1000000
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_track_user_activity(self):
        """Cover track_user_activity (lines 426-438)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track user activity
            engine.track_user_activity(
                user_id="user1",
                action="workflow_created",
                workflow_id="test-wf",
                metadata={"source": "ui"},
                workspace_id="ws-1"
            )

            # Verify metric
            assert len(engine.metrics_buffer) == 1
            metric = engine.metrics_buffer[0]
            assert metric.workflow_id == "test-wf"
            assert metric.metric_name == "user_activity"
            assert metric.metric_type == MetricType.COUNTER
            assert metric.value == 1
            assert metric.tags == {"user_id": "user1", "action": "workflow_created", "workspace_id": "ws-1"}
            assert metric.user_id == "user1"
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_track_metric(self):
        """Cover track_metric (lines 440-455)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track custom metric
            engine.track_metric(
                workflow_id="test-wf",
                metric_name="custom_counter",
                metric_type=MetricType.COUNTER,
                value=42,
                tags={"environment": "production"},
                step_id="step-1",
                step_name="Custom Step",
                user_id="user1"
            )

            # Verify metric
            assert len(engine.metrics_buffer) == 1
            metric = engine.metrics_buffer[0]
            assert metric.workflow_id == "test-wf"
            assert metric.metric_name == "custom_counter"
            assert metric.metric_type == MetricType.COUNTER
            assert metric.value == 42
            assert metric.tags == {"environment": "production"}
            assert metric.step_id == "step-1"
            assert metric.step_name == "Custom Step"
            assert metric.user_id == "user1"
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestPerformanceMetrics:
    """Test performance metrics computation."""

    def test_get_workflow_performance_metrics_cache_hit(self):
        """Cover performance cache logic (lines 457-465)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create cached metrics
            cached_metrics = PerformanceMetrics(
                workflow_id="test-wf",
                time_window="24h",
                total_executions=100,
                successful_executions=95,
                failed_executions=5,
                average_duration_ms=1500.0,
                median_duration_ms=1400.0,
                p95_duration_ms=2000.0,
                p99_duration_ms=2500.0,
                error_rate=0.05,
                most_common_errors=[],
                average_cpu_usage=50.0,
                peak_memory_usage=1024.0,
                average_step_duration={},
                unique_users=10,
                executions_by_user={},
                timestamp=datetime.now()
            )

            # Add to cache
            engine.performance_cache["test-wf_24h"] = cached_metrics

            # Get metrics (should hit cache)
            metrics = engine.get_workflow_performance_metrics("test-wf", "24h")

            assert metrics is cached_metrics
            assert metrics.total_executions == 100
            assert metrics.successful_executions == 95
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_workflow_performance_metrics_no_data(self):
        """Cover performance metrics with no executions (lines 480-575)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get metrics for workflow with no data
            metrics = engine.get_workflow_performance_metrics("nonexistent-wf", "24h")

            assert metrics.total_executions == 0
            assert metrics.successful_executions == 0
            assert metrics.failed_executions == 0
            assert metrics.average_duration_ms == 0
            assert metrics.median_duration_ms == 0
            assert metrics.error_rate == 0
            assert metrics.unique_users == 0
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestSystemOverview:
    """Test system-wide analytics overview."""

    def test_get_system_overview_empty(self):
        """Cover get_system_overview with no data (lines 577-668)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get system overview
            overview = engine.get_system_overview("24h")

            assert overview["total_workflows"] == 0
            assert overview["total_executions"] == 0
            assert overview["success_rate"] == 0
            assert overview["average_execution_time_ms"] == 0
            assert overview["top_workflows"] == []
            assert overview["recent_errors"] == []
            assert overview["time_window"] == "24h"
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestAlertManagement:
    """Test alert creation and management."""

    def test_create_alert(self):
        """Cover create_alert (lines 670-711, 1420-1449)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create alert using Alert object (second method overwrites first)
            alert = Alert(
                alert_id="test-alert-1",
                name="High Error Rate",
                description="Error rate exceeds 10%",
                severity=AlertSeverity.HIGH,
                condition="error_rate > 0.1",
                threshold_value=0.1,
                metric_name="error_rate",
                workflow_id="test-wf",
                step_id="step-1",
                notification_channels=["email", "slack"]
            )
            created_alert = engine.create_alert(alert=alert)

            assert created_alert.alert_id == "test-alert-1"
            assert created_alert.name == "High Error Rate"
            assert created_alert.severity == AlertSeverity.HIGH
            assert created_alert.workflow_id == "test-wf"
            assert created_alert.step_id == "step-1"
            assert created_alert.notification_channels == ["email", "slack"]

            # Verify alert is in active_alerts
            assert created_alert.alert_id in engine.active_alerts

            # Note: First create_alert method (lines 670-711) is unreachable due to method overloading
            # Second method (lines 1420-1449) overwrites it
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_check_alerts_no_alerts(self):
        """Cover check_alerts with no alerts (lines 713-753)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Check alerts (should not crash)
            engine.check_alerts()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_trigger_alert(self):
        """Cover _trigger_alert (lines 755-777)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create alert manually
            alert = Alert(
                alert_id="test-alert",
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.HIGH,
                condition="true",
                threshold_value=1.0,
                metric_name="test_metric",
                enabled=True
            )
            engine.active_alerts["test-alert"] = alert

            # Trigger alert
            engine._trigger_alert("test-alert")

            assert alert.triggered_at is not None
            assert alert.triggered_at <= datetime.now()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_resolve_alert(self):
        """Cover _resolve_alert (lines 779-798)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create triggered alert
            alert = Alert(
                alert_id="test-alert",
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.HIGH,
                condition="true",
                threshold_value=1.0,
                metric_name="test_metric",
                enabled=True,
                triggered_at=datetime.now()
            )
            engine.active_alerts["test-alert"] = alert

            # Resolve alert
            engine._resolve_alert("test-alert")

            assert alert.resolved_at is not None
            assert alert.resolved_at <= datetime.now()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_send_alert_notification(self):
        """Cover _send_alert_notification (lines 800-804)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create alert
            alert = Alert(
                alert_id="test-alert",
                name="Critical Alert",
                description="System failure",
                severity=AlertSeverity.CRITICAL,
                condition="true",
                threshold_value=1.0,
                metric_name="test_metric"
            )

            # Send notification (should log critical message)
            engine._send_alert_notification(alert)
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestBackgroundProcessing:
    """Test background processing methods."""

    def test_flush_metrics_and_events(self):
        """Cover flush method (lines 932-942)."""
        import asyncio

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Add some data to buffers
            engine.track_workflow_start("test-wf", "exec-1")
            engine.track_metric("test-wf", "test_metric", MetricType.COUNTER, 42)

            # Flush buffers
            asyncio.run(engine.flush())

            # Buffers should be cleared
            assert len(engine.metrics_buffer) == 0
            assert len(engine.events_buffer) == 0
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestAnalyticsHelperMethods:
    """Test analytics dashboard helper methods."""

    def test_get_performance_metrics_workflow(self):
        """Cover get_performance_metrics for specific workflow (lines 946-954)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get performance metrics for specific workflow
            metrics = engine.get_performance_metrics("test-wf", "24h")

            assert metrics is not None
            assert metrics.workflow_id == "test-wf"
            assert metrics.time_window == "24h"
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_performance_metrics_all_workflows(self):
        """Cover get_performance_metrics for all workflows (line 951-954, 956-1041)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get performance metrics for all workflows
            metrics = engine.get_performance_metrics("*", "24h")

            assert metrics is not None
            assert metrics.workflow_id == "*"
            assert metrics.time_window == "24h"
            assert metrics.total_executions == 0
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_unique_workflow_count(self):
        """Cover get_unique_workflow_count (lines 1043-1066)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get unique workflow count
            count = engine.get_unique_workflow_count("24h")

            assert count == 0
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_workflow_name(self):
        """Cover get_workflow_name (lines 1068-1082)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get workflow name (should return workflow_id as fallback)
            name = engine.get_workflow_name("test-wf")

            assert name == "test-wf"
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_all_workflow_ids(self):
        """Cover get_all_workflow_ids (lines 1084-1109)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get all workflow IDs
            workflow_ids = engine.get_all_workflow_ids("24h")

            assert workflow_ids == []
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_last_execution_time(self):
        """Cover get_last_execution_time (lines 1111-1128)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get last execution time for non-existent workflow
            last_time = engine.get_last_execution_time("test-wf")

            assert last_time is None
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_execution_timeline(self):
        """Cover get_execution_timeline (lines 1130-1214)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get execution timeline
            timeline = engine.get_execution_timeline("test-wf", "24h", "1h")

            # Timeline returns time buckets, not empty list
            assert isinstance(timeline, list)
            # Each entry should have the expected fields
            if timeline:
                assert "timestamp" in timeline[0]
                assert "count" in timeline[0]
                assert "success_count" in timeline[0]
                assert "failure_count" in timeline[0]
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_error_breakdown(self):
        """Cover get_error_breakdown (lines 1216-1313)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get error breakdown for specific workflow
            breakdown = engine.get_error_breakdown("test-wf", "24h")

            assert breakdown["workflow_id"] == "test-wf"
            assert breakdown["error_types"] == []
            assert breakdown["recent_errors"] == []
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_error_breakdown_all_workflows(self):
        """Cover get_error_breakdown for all workflows."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get error breakdown for all workflows
            breakdown = engine.get_error_breakdown("*", "24h")

            assert "error_types" in breakdown
            assert "workflows_with_errors" in breakdown
            assert "recent_errors" in breakdown
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_all_alerts(self):
        """Cover get_all_alerts (lines 1315-1362)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get all alerts
            alerts = engine.get_all_alerts()

            assert alerts == []

            # Create alert using individual parameters
            alert = Alert(
                alert_id="test-alert-1",
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.LOW,
                condition="true",
                threshold_value=1.0,
                metric_name="test_metric"
            )
            engine.create_alert(alert=alert)

            # Get all alerts again
            alerts = engine.get_all_alerts()

            assert len(alerts) == 1
            assert alerts[0].name == "Test Alert"
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_all_alerts_filtered(self):
        """Cover get_all_alerts with filters."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create alerts for different workflows using Alert objects
            alert1 = Alert(
                alert_id="alert-1",
                name="Alert 1",
                description="Test",
                severity=AlertSeverity.LOW,
                condition="true",
                threshold_value=1.0,
                metric_name="test_metric",
                workflow_id="wf-1"
            )
            engine.create_alert(alert=alert1)

            alert2 = Alert(
                alert_id="alert-2",
                name="Alert 2",
                description="Test",
                severity=AlertSeverity.HIGH,
                condition="true",
                threshold_value=1.0,
                metric_name="test_metric",
                workflow_id="wf-2"
            )
            engine.create_alert(alert=alert2)

            # Filter by workflow_id
            alerts = engine.get_all_alerts(workflow_id="wf-1")

            assert len(alerts) == 1
            assert alerts[0].workflow_id == "wf-1"

            # Filter enabled only
            alerts = engine.get_all_alerts(enabled_only=True)

            assert len(alerts) == 2
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_recent_events(self):
        """Cover get_recent_events (lines 1364-1417)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Get recent events
            events = engine.get_recent_events(limit=50)

            assert events == []
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_update_alert(self):
        """Cover update_alert (lines 1451-1486)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create alert using Alert object
            alert = Alert(
                alert_id="test-alert",
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.LOW,
                condition="true",
                threshold_value=1.0,
                metric_name="test_metric",
                enabled=True
            )
            engine.create_alert(alert=alert)

            # Update alert
            engine.update_alert(alert.alert_id, enabled=False, threshold_value=2.0)

            # Verify update
            updated_alert = engine.active_alerts[alert.alert_id]
            assert updated_alert.enabled is False
            assert updated_alert.threshold_value == 2.0
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_delete_alert(self):
        """Cover delete_alert (lines 1488-1507)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create alert using Alert object
            alert = Alert(
                alert_id="test-alert",
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.LOW,
                condition="true",
                threshold_value=1.0,
                metric_name="test_metric"
            )
            engine.create_alert(alert=alert)

            alert_id = alert.alert_id

            # Delete alert
            engine.delete_alert(alert_id)

            # Verify deletion
            assert alert_id not in engine.active_alerts
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestGlobalInstance:
    """Test global analytics engine instance."""

    def test_get_analytics_engine_singleton(self):
        """Cover get_analytics_engine singleton (lines 1510-1517)."""
        from core.workflow_analytics_engine import get_analytics_engine

        # Get global instance
        engine1 = get_analytics_engine()
        engine2 = get_analytics_engine()

        # Should return same instance
        assert engine1 is engine2
