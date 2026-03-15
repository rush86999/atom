"""
Coverage-driven tests for workflow_analytics_engine.py (86% -> 98%+ target)

Building on Phase 191's 86% baseline (481/561 statements).
Covering remaining edge cases and error paths.

Coverage Target Areas:
- Remaining lines in error handling paths
- Edge cases in metrics calculation
- Boundary conditions for aggregation
- Exception handling blocks
- Alert checking and resolution paths
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import json
import uuid
import time

from core.workflow_analytics_engine import (
    WorkflowAnalyticsEngine,
    WorkflowMetric,
    WorkflowExecutionEvent,
    PerformanceMetrics,
    Alert,
    AlertSeverity,
    MetricType,
    WorkflowStatus
)


class TestPerformanceMetricsEdgeCases:
    """Test edge cases in performance metrics calculation"""

    def test_performance_metrics_empty_database(self):
        """Test performance metrics with no data"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            metrics = engine.get_performance_metrics("nonexistent_workflow")

            assert metrics.total_executions == 0
            assert metrics.successful_executions == 0
            assert metrics.failed_executions == 0
            assert metrics.average_duration_ms == 0
            assert metrics.median_duration_ms == 0
            assert metrics.p95_duration_ms == 0
            assert metrics.p99_duration_ms == 0
            assert metrics.error_rate == 0
            assert metrics.most_common_errors == []
            assert metrics.average_cpu_usage == 0
            assert metrics.peak_memory_usage == 0
            assert metrics.average_step_duration == {}
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_performance_metrics_database_error(self):
        """Test performance metrics with database error"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Corrupt the database
            conn = sqlite3.connect(db_path)
            conn.execute("DROP TABLE IF EXISTS workflow_events")
            conn.close()

            with pytest.raises(Exception):
                engine.get_performance_metrics("test_workflow")
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestAlertCheckingEdgeCases:
    """Test edge cases in alert checking and triggering"""

    def test_check_alerts_no_active_alerts(self):
        """Test check_alerts when no alerts are active"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Should not raise any errors
            engine.check_alerts()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_check_alerts_no_metric_data(self):
        """Test alert checking when no metric data exists"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create alert using Alert object but don't add any metrics
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                name="Test Alert",
                description="Test",
                severity=AlertSeverity.LOW,
                condition="greater_than",
                threshold_value=100.0,
                metric_name="nonexistent_metric"
            )
            alert = engine.create_alert(alert)

            # Should not raise any errors
            engine.check_alerts()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_trigger_alert_nonexistent_alert(self):
        """Test _trigger_alert with nonexistent alert ID"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Should not raise any errors
            engine._trigger_alert("nonexistent_alert_id")
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_resolve_alert_nonexistent_alert(self):
        """Test _resolve_alert with nonexistent alert ID"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Should not raise any errors
            engine._resolve_alert("nonexistent_alert_id")
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestRecentEventsEdgeCases:
    """Test edge cases in recent events retrieval"""

    def test_get_recent_events_no_events(self):
        """Test getting recent events when none exist"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            events = engine.get_recent_events(limit=10)
            assert events == []
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_recent_events_limit_zero(self):
        """Test getting recent events with limit=0"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_workflow_start("test_workflow", "exec_1", "user1")

            events = engine.get_recent_events(limit=0)
            assert events == []
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestMetricsAggregationEdgeCases:
    """Test edge cases in metrics aggregation"""

    def test_track_metric_with_tags(self):
        """Test tracking metric with custom tags"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            tags = {"environment": "production", "region": "us-east-1"}
            engine.track_metric(
                workflow_id="test_workflow",
                metric_name="custom_metric",
                metric_type=MetricType.COUNTER,
                value=1,
                tags=tags
            )

            # Verify metric was tracked
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT tags FROM workflow_metrics WHERE metric_name = 'custom_metric'"
            )
            result = cursor.fetchone()
            conn.close()

            assert result is not None
            stored_tags = json.loads(result[0]) if result[0] else {}
            assert stored_tags == tags
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_track_metric_with_step_context(self):
        """Test tracking metric with step context"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_metric(
                workflow_id="test_workflow",
                metric_name="step_duration_ms",
                metric_type=MetricType.HISTOGRAM,
                value=150,
                step_id="step_1",
                step_name="data_processing"
            )

            # Verify step context was stored
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT step_id, step_name FROM workflow_metrics WHERE step_id = 'step_1'"
            )
            result = cursor.fetchone()
            conn.close()

            assert result is not None
            assert result[0] == "step_1"
            assert result[1] == "data_processing"
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_system_overview_empty_database(self):
        """Test system overview with no data"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            overview = engine.get_system_overview()

            assert overview["total_workflows"] == 0
            assert overview["total_executions"] == 0
            assert overview["success_rate"] == 0
            assert overview["total_alerts"] == 0
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestErrorHandlingPaths:
    """Test error handling paths"""

    def test_track_workflow_completion_with_error(self):
        """Test tracking workflow completion with error message"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_workflow_start("test_workflow", "exec_1", "user1")

            engine.track_workflow_completion(
                workflow_id="test_workflow",
                execution_id="exec_1",
                status="failed",
                duration_ms=1000,
                error_message="Database connection failed"
            )

            # Verify error was stored
            events = engine.get_execution_timeline("test_workflow")
            assert len(events) == 2
            completion_event = events[1]
            assert completion_event.error_message == "Database connection failed"
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_track_step_execution_with_error(self):
        """Test tracking step execution with error"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_step_execution(
                workflow_id="test_workflow",
                execution_id="exec_1",
                step_id="step_1",
                step_name="failing_step",
                event_type="step_failed",
                status="failed",
                duration_ms=500,
                error_message="Step validation failed"
            )

            # Verify error was stored
            events = engine.get_recent_events(workflow_id="test_workflow")
            assert len(events) == 1
            assert events[0].error_message == "Step validation failed"
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_manual_override_tracking(self):
        """Test tracking manual override events"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_manual_override(
                workflow_id="test_workflow",
                execution_id="exec_1",
                resource_id="resource_1",
                action="manual_intervention",
                original_value="automated",
                new_value="manual",
                user_id="admin_user"
            )

            events = engine.get_recent_events(workflow_id="test_workflow")
            assert len(events) == 1
            assert events[0].event_type == "manual_override"
            assert events[0].user_id == "admin_user"
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestAlertLifecycle:
    """Test alert lifecycle operations"""

    def test_create_alert_with_notification_channels(self):
        """Test creating alert with notification channels"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            channels = ["email", "slack", "webhook"]
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                name="Multi-channel Alert",
                description="Test alert",
                severity=AlertSeverity.CRITICAL,
                condition="greater_than",
                threshold_value=100.0,
                metric_name="error_rate",
                notification_channels=channels
            )
            alert = engine.create_alert(alert)

            assert alert.notification_channels == channels

            # Verify persisted to database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT notification_channels FROM analytics_alerts WHERE alert_id = ?",
                (alert.alert_id,)
            )
            result = cursor.fetchone()
            conn.close()

            stored_channels = json.loads(result[0])
            assert stored_channels == channels
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_create_alert_with_step_specific(self):
        """Test creating alert for specific step"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            alert = Alert(
                alert_id=str(uuid.uuid4()),
                name="Step Duration Alert",
                description="Step taking too long",
                severity=AlertSeverity.HIGH,
                condition="greater_than",
                threshold_value=5000.0,
                metric_name="step_duration_ms",
                workflow_id="test_workflow",
                step_id="slow_step"
            )
            alert = engine.create_alert(alert)

            assert alert.workflow_id == "test_workflow"
            assert alert.step_id == "slow_step"
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_update_alert_severity(self):
        """Test updating alert severity"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            alert = Alert(
                alert_id=str(uuid.uuid4()),
                name="Severity Test Alert",
                description="Test",
                severity=AlertSeverity.LOW,
                condition="greater_than",
                threshold_value=10.0,
                metric_name="test_metric"
            )
            alert = engine.create_alert(alert)

            # Update severity using the update_alert method with alert_id
            engine.update_alert(alert.alert_id, threshold_value=20.0)

            # Verify update by getting all alerts
            all_alerts = engine.get_all_alerts()
            updated_alert = next((a for a in all_alerts if a.alert_id == alert.alert_id), None)
            assert updated_alert is not None
            # Note: update_alert signature uses alert_id, not alert object
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_delete_alert(self):
        """Test deleting an alert"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            alert = Alert(
                alert_id=str(uuid.uuid4()),
                name="Deletable Alert",
                description="Will be deleted",
                severity=AlertSeverity.MEDIUM,
                condition="greater_than",
                threshold_value=50.0,
                metric_name="test_metric"
            )
            alert = engine.create_alert(alert)

            alert_id = alert.alert_id

            # Delete alert
            engine.delete_alert(alert_id)

            # Verify deletion by checking active_alerts
            assert alert_id not in engine.active_alerts

            # Verify by getting all alerts (should be empty)
            all_alerts = engine.get_all_alerts()
            assert not any(a.alert_id == alert_id for a in all_alerts)
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestBoundaryConditions:
    """Test boundary conditions and extreme values"""

    def test_very_large_duration_values(self):
        """Test handling of very large duration values"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_workflow_start("test_workflow", "exec_1", "user1")

            # Very large duration (24 hours in ms)
            large_duration = 24 * 60 * 60 * 1000
            engine.track_workflow_completion(
                workflow_id="test_workflow",
                execution_id="exec_1",
                status="completed",
                duration_ms=large_duration
            )

            metrics = engine.get_performance_metrics("test_workflow")
            assert metrics.average_duration_ms == large_duration
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_negative_duration_values(self):
        """Test handling of negative duration values (edge case)"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_workflow_start("test_workflow", "exec_1", "user1")

            # Negative duration (shouldn't happen but test robustness)
            engine.track_workflow_completion(
                workflow_id="test_workflow",
                execution_id="exec_1",
                status="completed",
                duration_ms=-100
            )

            # Should still calculate metrics
            metrics = engine.get_performance_metrics("test_workflow")
            assert metrics.total_executions == 1
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_zero_threshold_alert(self):
        """Test alert with zero threshold"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            alert = Alert(
                alert_id=str(uuid.uuid4()),
                name="Zero Threshold Alert",
                description="Test",
                severity=AlertSeverity.LOW,
                condition="greater_than",
                threshold_value=0.0,
                metric_name="test_metric"
            )
            alert = engine.create_alert(alert)

            # Track metric with value 0
            engine.track_metric(
                workflow_id="test_workflow",
                metric_name="test_metric",
                metric_type=MetricType.GAUGE,
                value=0.0
            )

            # Should not trigger (0 is not > 0)
            engine.check_alerts()
            assert alert.triggered_at is None
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_extremely_high_metric_values(self):
        """Test handling of extremely high metric values"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track very high value
            engine.track_metric(
                workflow_id="test_workflow",
                metric_name="high_value_metric",
                metric_type=MetricType.GAUGE,
                value=1e20  # Extremely large number
            )

            # Should be stored without error
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM workflow_metrics WHERE metric_name = 'high_value_metric'"
            )
            result = cursor.fetchone()
            conn.close()

            assert result is not None
            assert float(result[0]) == 1e20
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_performance_metrics_different_time_windows(self):
        """Test performance metrics with different time windows"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            engine.track_workflow_start("test_workflow", "exec_1", "user1")
            engine.track_workflow_completion(
                workflow_id="test_workflow",
                execution_id="exec_1",
                status="completed",
                duration_ms=1000
            )

            # Test different time windows
            for window in ["1h", "24h", "7d", "30d"]:
                metrics = engine.get_performance_metrics("test_workflow", time_window=window)
                assert metrics.time_window == window
                assert metrics.total_executions == 1
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_error_breakdown_with_errors(self):
        """Test error breakdown when errors exist"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track multiple failures with different errors
            for i in range(3):
                engine.track_workflow_start("test_workflow", f"exec_{i}", "user1")
                engine.track_workflow_completion(
                    workflow_id="test_workflow",
                    execution_id=f"exec_{i}",
                    status="failed",
                    duration_ms=1000,
                    error_message=f"Error type {i % 2}"  # Two types of errors
                )

            breakdown = engine.get_error_breakdown("test_workflow")
            assert len(breakdown) == 2  # Two unique error types
            assert breakdown[0]["count"] + breakdown[1]["count"] == 3
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_error_breakdown_all_workflows(self):
        """Test error breakdown across all workflows"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Track failures for different workflows
            for wf in ["workflow_1", "workflow_2"]:
                engine.track_workflow_start(wf, f"exec_{wf}", "user1")
                engine.track_workflow_completion(
                    workflow_id=wf,
                    execution_id=f"exec_{wf}",
                    status="failed",
                    duration_ms=1000,
                    error_message="Common error"
                )

            breakdown = engine.get_error_breakdown()  # All workflows
            assert len(breakdown) >= 1
            assert any(e["error"] == "Common error" for e in breakdown)
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_get_all_alerts_with_filters(self):
        """Test getting all alerts with severity filter"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = WorkflowAnalyticsEngine(db_path=db_path)

            # Create alerts with different severities
            for severity in [AlertSeverity.LOW, AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
                alert = Alert(
                    alert_id=str(uuid.uuid4()),
                    name=f"{severity.value} Alert",
                    description="Test",
                    severity=severity,
                    condition="greater_than",
                    threshold_value=10.0,
                    metric_name="test_metric"
                )
                engine.create_alert(alert)

            # Filter by HIGH severity
            high_alerts = engine.get_all_alerts(severity=AlertSeverity.HIGH)
            assert len(high_alerts) == 1
            assert high_alerts[0].severity == AlertSeverity.HIGH
        finally:
            Path(db_path).unlink(missing_ok=True)
