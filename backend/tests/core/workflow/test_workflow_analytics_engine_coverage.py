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
