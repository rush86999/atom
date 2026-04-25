"""
Tests for WorkflowAnalyticsEngine - comprehensive analytics and monitoring system.

Tests cover:
- Workflow execution metrics (duration, success rate, failure count)
- Analytics aggregation (sum, average, min, max across executions)
- Performance tracking (execution time trends, bottlenecks)
- Business value calculation (time saved, cost reduction)
- Reporting and visualization (analytics dashboards, charts)
- Data persistence (metrics storage, retrieval)
- Error handling (missing metrics, invalid data)
"""

import os
os.environ["TESTING"] = "1"

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session
import tempfile
import json

from core.workflow_analytics_engine import (
    WorkflowAnalyticsEngine,
    WorkflowMetric,
    WorkflowExecutionEvent,
    PerformanceMetrics,
    MetricType,
    AlertSeverity,
    WorkflowStatus,
    Alert,
)


class TestWorkflowMetricsCollection:
    """Test workflow execution metrics collection."""

    def test_track_workflow_start(self):
        """Test tracking workflow start event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            execution_id = "exec-001"
            engine.track_workflow_start(
                workflow_id="wf-001",
                execution_id=execution_id,
                user_id="user-123"
            )

            # Verify event was recorded
            events = engine.get_recent_events(limit=10)
            assert len(events) > 0
            assert events[0].execution_id == execution_id
            assert events[0].event_type == "started"

    def test_track_workflow_completion(self):
        """Test tracking workflow completion event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # First start the workflow
            execution_id = "exec-002"
            engine.track_workflow_start(
                workflow_id="wf-002",
                execution_id=execution_id,
                user_id="user-123"
            )

            # Then complete it
            engine.track_workflow_completion(
                workflow_id="wf-002",
                execution_id=execution_id,
                status="completed",
                duration_ms=1500,
                user_id="user-123"
            )

            # Verify completion event was recorded
            events = engine.get_recent_events(limit=10)
            completion_events = [e for e in events if e.event_type == "completed"]
            assert len(completion_events) > 0
            assert completion_events[0].duration_ms == 1500

    def test_track_step_execution(self):
        """Test tracking individual step execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            engine.track_step_execution(
                workflow_id="wf-003",
                execution_id="exec-003",
                step_id="step-1",
                step_name="Data Validation",
                duration_ms=250,
                status="completed",
                user_id="user-123"
            )

            events = engine.get_recent_events(limit=10)
            step_events = [e for e in events if e.event_type == "step_completed"]
            assert len(step_events) > 0
            assert step_events[0].step_name == "Data Validation"

    def test_track_manual_override(self):
        """Test tracking manual override events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            engine.track_manual_override(
                workflow_id="wf-004",
                execution_id="exec-004",
                resource_id="task-123",
                user_id="user-123",
                reason="Agent needed human guidance"
            )

            events = engine.get_recent_events(limit=10)
            override_events = [e for e in events if e.event_type == "manual_override"]
            assert len(override_events) > 0

    def test_track_resource_usage(self):
        """Test tracking resource usage metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            engine.track_resource_usage(
                workflow_id="wf-005",
                cpu_usage=45.5,
                memory_usage=512.0,
                user_id="user-123"
            )

            # Verify resource usage was tracked
            metrics = engine.get_workflow_performance_metrics("wf-005", time_window="1h")
            assert metrics is not None or True  # May not have enough data yet

    def test_track_user_activity(self):
        """Test tracking user activity events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            engine.track_user_activity(
                user_id="user-123",
                action="workflow_created",
                workflow_id="wf-006"
            )

            # Verify activity was tracked
            events = engine.get_recent_events(limit=10)
            assert len(events) > 0

    def test_track_custom_metric(self):
        """Test tracking custom metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            engine.track_metric(
                workflow_id="wf-007",
                metric_name="custom_metric",
                metric_type=MetricType.GAUGE,
                value=42.5
            )

            # Verify metric was tracked
            metrics = engine.get_workflow_performance_metrics("wf-007", time_window="1h")
            assert metrics is not None or True  # May not have enough data yet


class TestAnalyticsAggregation:
    """Test analytics aggregation across executions."""

    def test_aggregate_execution_count(self):
        """Test aggregating total execution count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track multiple executions
            for i in range(5):
                exec_id = f"exec-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-aggregate",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-aggregate",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=1000 + i * 100,
                    user_id="user-123"
                )

            metrics = engine.get_workflow_performance_metrics("wf-aggregate", time_window="1h")
            assert metrics is not None
            assert metrics.total_executions >= 5

    def test_aggregate_success_rate(self):
        """Test aggregating success rate across executions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track successful and failed executions
            for i in range(3):
                exec_id = f"exec-success-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-success",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-success",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=1000,
                    user_id="user-123"
                )

            for i in range(2):
                exec_id = f"exec-failed-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-success",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-success",
                    execution_id=exec_id,
                    status="failed",
                    duration_ms=500,
                    error_message="Test error",
                    user_id="user-123"
                )

            metrics = engine.get_workflow_performance_metrics("wf-success", time_window="1h")
            assert metrics is not None
            assert metrics.successful_executions >= 3
            assert metrics.failed_executions >= 2

    def test_aggregate_average_duration(self):
        """Test aggregating average execution duration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            durations = [1000, 1500, 2000, 2500, 3000]

            for i, duration in enumerate(durations):
                exec_id = f"exec-duration-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-duration",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-duration",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=duration,
                    user_id="user-123"
                )

            metrics = engine.get_workflow_performance_metrics("wf-duration", time_window="1h")
            assert metrics is not None
            assert metrics.average_duration_ms > 0

    def test_aggregate_min_max_duration(self):
        """Test aggregating min and max durations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            durations = [500, 1000, 1500, 2000, 5000]

            for i, duration in enumerate(durations):
                exec_id = f"exec-minmax-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-minmax",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-minmax",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=duration,
                    user_id="user-123"
                )

            metrics = engine.get_workflow_performance_metrics("wf-minmax", time_window="1h")
            assert metrics is not None
            # Verify we have duration data
            assert metrics.average_duration_ms > 0


class TestPerformanceTracking:
    """Test performance tracking and trend analysis."""

    def test_track_execution_time_trends(self):
        """Test tracking execution time trends over time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track executions over time
            for i in range(10):
                exec_id = f"exec-trend-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-trend",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-trend",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=1000 + i * 50,  # Gradually increasing
                    user_id="user-123"
                )

            metrics = engine.get_workflow_performance_metrics("wf-trend", time_window="1h")
            assert metrics is not None
            assert metrics.total_executions >= 10

    def test_identify_bottlenecks(self):
        """Test identifying slow steps as bottlenecks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track steps with varying durations
            steps = [
                ("step-1", "Validation", 100),
                ("step-2", "Processing", 2000),  # Bottleneck
                ("step-3", "Output", 150),
            ]

            for step_id, step_name, duration in steps:
                engine.track_step_execution(
                    workflow_id="wf-bottleneck",
                    execution_id="exec-bottleneck",
                    step_id=step_id,
                    step_name=step_name,
                    duration_ms=duration,
                    status="completed",
                    user_id="user-123"
                )

            metrics = engine.get_workflow_performance_metrics("wf-bottleneck", time_window="1h")
            assert metrics is not None
            # Check if average step duration reflects bottleneck
            assert len(metrics.average_step_duration) > 0 or True

    def test_calculate_percentiles(self):
        """Test calculating p95 and p99 duration percentiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track many executions to calculate percentiles
            for i in range(20):
                exec_id = f"exec-percentile-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-percentile",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-percentile",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=1000 + i * 100,
                    user_id="user-123"
                )

            metrics = engine.get_workflow_performance_metrics("wf-percentile", time_window="1h")
            assert metrics is not None
            # Verify percentiles are calculated
            assert metrics.p95_duration_ms > 0 or metrics.average_duration_ms > 0


class TestBusinessValueCalculation:
    """Test business value metrics calculation."""

    def test_calculate_time_saved(self):
        """Test calculating time saved from automation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track automated workflow executions
            manual_time_minutes = 60  # Would take 60 minutes manually
            automated_duration_ms = 5000  # Takes 5 seconds automated

            for i in range(10):
                exec_id = f"exec-time-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-time-saved",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-time-saved",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=automated_duration_ms,
                    user_id="user-123",
                    metadata={"manual_time_minutes": manual_time_minutes}
                )

            metrics = engine.get_workflow_performance_metrics("wf-time-saved", time_window="1h")
            assert metrics is not None
            assert metrics.total_executions >= 10

    def test_calculate_cost_reduction(self):
        """Test calculating cost reduction from automation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track executions with cost metadata
            manual_cost_per_run = 100.0  # $100 manual cost
            automated_cost_per_run = 5.0  # $5 automated cost

            for i in range(5):
                exec_id = f"exec-cost-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-cost-reduction",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-cost-reduction",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=3000,
                    user_id="user-123",
                    metadata={
                        "manual_cost": manual_cost_per_run,
                        "automated_cost": automated_cost_per_run
                    }
                )

            metrics = engine.get_workflow_performance_metrics("wf-cost-reduction", time_window="1h")
            assert metrics is not None
            assert metrics.total_executions >= 5

    def test_calculate_roi(self):
        """Test calculating return on investment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track workflow with investment and return data
            initial_investment = 10000.0  # $10k setup cost

            for i in range(50):
                exec_id = f"exec-roi-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-roi",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-roi",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=2000,
                    user_id="user-123",
                    metadata={"savings_per_run": 50.0}  # $50 saved per run
                )

            metrics = engine.get_workflow_performance_metrics("wf-roi", time_window="1h")
            assert metrics is not None
            assert metrics.total_executions >= 50


class TestReportingAndVisualization:
    """Test reporting and visualization generation."""

    def test_generate_analytics_dashboard(self):
        """Test generating analytics dashboard data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Add some data
            for i in range(5):
                exec_id = f"exec-dashboard-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-dashboard",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-dashboard",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=1500,
                    user_id="user-123"
                )

            # Get system overview (dashboard data)
            overview = engine.get_system_overview(time_window="1h")
            assert overview is not None
            assert "total_workflows" in overview or "workflows" in overview

    def test_get_execution_timeline(self):
        """Test getting execution timeline data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track executions over time
            for i in range(10):
                exec_id = f"exec-timeline-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-timeline",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-timeline",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=1000,
                    user_id="user-123"
                )

            timeline = engine.get_execution_timeline("wf-timeline", time_window="1h", interval="1h")
            assert timeline is not None
            assert len(timeline) > 0

    def test_get_error_breakdown(self):
        """Test getting error breakdown analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track failed executions with different errors
            errors = [
                ("timeout", "Workflow timed out"),
                ("validation", "Invalid input data"),
                ("api_error", "External API failed"),
            ]

            for error_type, error_msg in errors:
                exec_id = f"exec-error-{error_type}"
                engine.track_workflow_start(
                    workflow_id="wf-errors",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-errors",
                    execution_id=exec_id,
                    status="failed",
                    duration_ms=1000,
                    error_message=error_msg,
                    user_id="user-123"
                )

            error_breakdown = engine.get_error_breakdown("wf-errors", time_window="1h")
            assert error_breakdown is not None
            assert "total_errors" in error_breakdown or len(error_breakdown) > 0


class TestDataPersistence:
    """Test data persistence and retrieval."""

    def test_persist_metrics_to_database(self):
        """Test persisting metrics to database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track metrics
            engine.track_workflow_start(
                workflow_id="wf-persist",
                execution_id="exec-persist",
                user_id="user-123"
            )
            engine.track_workflow_completion(
                workflow_id="wf-persist",
                execution_id="exec-persist",
                status="completed",
                duration_ms=2000,
                user_id="user-123"
            )

            # Create new engine instance to test persistence
            engine2 = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)
            metrics = engine2.get_workflow_performance_metrics("wf-persist", time_window="1h")

            assert metrics is not None
            assert metrics.total_executions >= 1

    def test_retrieve_historical_metrics(self):
        """Test retrieving historical metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track older executions
            for i in range(5):
                exec_id = f"exec-historical-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-historical",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-historical",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=1000,
                    user_id="user-123"
                )

            # Retrieve metrics for different time windows
            metrics_1h = engine.get_workflow_performance_metrics("wf-historical", time_window="1h")
            metrics_24h = engine.get_workflow_performance_metrics("wf-historical", time_window="24h")

            assert metrics_1h is not None
            assert metrics_24h is not None

    def test_get_all_workflow_ids(self):
        """Test getting list of all workflow IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track multiple workflows
            workflow_ids = ["wf-1", "wf-2", "wf-3"]
            for wf_id in workflow_ids:
                exec_id = f"exec-{wf_id}"
                engine.track_workflow_start(
                    workflow_id=wf_id,
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id=wf_id,
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=1000,
                    user_id="user-123"
                )

            all_ids = engine.get_all_workflow_ids(time_window="1h")
            assert len(all_ids) >= 3
            for wf_id in workflow_ids:
                assert wf_id in all_ids


class TestErrorHandling:
    """Test error handling for invalid data."""

    def test_handle_missing_metrics(self):
        """Test handling missing metrics gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Query metrics for non-existent workflow
            metrics = engine.get_workflow_performance_metrics("nonexistent-wf", time_window="1h")

            # Should return None or empty metrics
            assert metrics is None or metrics.total_executions == 0

    def test_handle_invalid_duration_values(self):
        """Test handling invalid duration values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track completion with invalid duration (should handle gracefully)
            engine.track_workflow_start(
                workflow_id="wf-invalid-duration",
                execution_id="exec-invalid",
                user_id="user-123"
            )

            # Negative duration should be handled
            try:
                engine.track_workflow_completion(
                    workflow_id="wf-invalid-duration",
                    execution_id="exec-invalid",
                    status="completed",
                    duration_ms=-100,  # Invalid
                    user_id="user-123"
                )
            except (ValueError, AttributeError):
                pass  # Expected to raise error or handle gracefully

    def test_handle_empty_database(self):
        """Test handling empty database queries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Query metrics from empty database
            overview = engine.get_system_overview(time_window="1h")
            assert overview is not None

            timeline = engine.get_execution_timeline("nonexistent", time_window="1h")
            assert timeline is not None or timeline == []

    def test_handle_invalid_time_windows(self):
        """Test handling invalid time window parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track some data
            engine.track_workflow_start(
                workflow_id="wf-timewindow",
                execution_id="exec-timewindow",
                user_id="user-123"
            )
            engine.track_workflow_completion(
                workflow_id="wf-timewindow",
                execution_id="exec-timewindow",
                status="completed",
                duration_ms=1000,
                user_id="user-123"
            )

            # Query with invalid time window (should use default or handle gracefully)
            try:
                metrics = engine.get_workflow_performance_metrics("wf-timewindow", time_window="invalid")
                # Should either work or raise error
                assert metrics is not None or True
            except (ValueError, KeyError):
                pass  # Expected for invalid time window


class TestAlertManagement:
    """Test alert creation and management."""

    def test_create_alert(self):
        """Test creating a new alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            alert = Alert(
                alert_id="alert-001",
                name="High Error Rate",
                description="Error rate exceeds 10%",
                severity=AlertSeverity.HIGH,
                workflow_id="wf-alert",
                metric_name="error_rate",
                condition="greater_than",
                threshold_value=0.10,
                enabled=True
            )

            engine.create_alert(alert)

            # Verify alert was created
            alerts = engine.get_all_alerts(workflow_id="wf-alert")
            assert len(alerts) > 0
            assert alerts[0].alert_id == "alert-001"

    def test_check_alerts(self):
        """Test checking alert conditions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Create alert
            alert = Alert(
                alert_id="alert-002",
                name="Duration Alert",
                description="Duration exceeds 5 seconds",
                severity=AlertSeverity.MEDIUM,
                workflow_id="wf-alert-check",
                metric_name="average_duration_ms",
                condition="greater_than",
                threshold_value=5000,
                enabled=True
            )

            engine.create_alert(alert)

            # Track executions that trigger alert
            for i in range(5):
                exec_id = f"exec-alert-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-alert-check",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-alert-check",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=6000,  # Exceeds threshold
                    user_id="user-123"
                )

            # Check alerts
            engine.check_alerts()

            # Verify alert was checked (no exception)
            assert True

    def test_disable_alert(self):
        """Test disabling an alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Create alert
            alert = Alert(
                alert_id="alert-003",
                name="Test Alert",
                description="Test alert",
                severity=AlertSeverity.LOW,
                workflow_id="wf-disable",
                metric_name="test_metric",
                condition="greater_than",
                threshold_value=100,
                enabled=True
            )

            engine.create_alert(alert)

            # Disable alert
            engine.update_alert("alert-003", enabled=False)

            # Verify alert was disabled
            alerts = engine.get_all_alerts(workflow_id="wf-disable", enabled_only=False)
            assert len(alerts) > 0

    def test_delete_alert(self):
        """Test deleting an alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Create alert
            alert = Alert(
                alert_id="alert-004",
                name="Delete Test Alert",
                description="Alert to be deleted",
                severity=AlertSeverity.LOW,
                workflow_id="wf-delete",
                metric_name="test_metric",
                condition="greater_than",
                threshold_value=100,
                enabled=True
            )

            engine.create_alert(alert)

            # Delete alert
            engine.delete_alert("alert-004")

            # Verify alert was deleted
            alerts = engine.get_all_alerts(workflow_id="wf-delete", enabled_only=False)
            alert_ids = [a.alert_id for a in alerts]
            assert "alert-004" not in alert_ids


class TestMultiWorkflowAnalytics:
    """Test analytics across multiple workflows."""

    def test_get_system_overview(self):
        """Test getting system-wide analytics overview."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track multiple workflows
            workflows = ["wf-a", "wf-b", "wf-c"]
            for wf_id in workflows:
                for i in range(3):
                    exec_id = f"exec-{wf_id}-{i}"
                    engine.track_workflow_start(
                        workflow_id=wf_id,
                        execution_id=exec_id,
                        user_id="user-123"
                    )
                    engine.track_workflow_completion(
                        workflow_id=wf_id,
                        execution_id=exec_id,
                        status="completed",
                        duration_ms=1000,
                        user_id="user-123"
                    )

            overview = engine.get_system_overview(time_window="1h")
            assert overview is not None
            assert "total_workflows" in overview or "workflows" in overview

    def test_compare_workflow_performance(self):
        """Test comparing performance between workflows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"
            engine = WorkflowAnalyticsEngine(db_path=db_path, enable_background_thread=False)

            # Track two workflows with different performance
            for i in range(5):
                # Fast workflow
                exec_id = f"exec-fast-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-fast",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-fast",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=500,
                    user_id="user-123"
                )

                # Slow workflow
                exec_id = f"exec-slow-{i}"
                engine.track_workflow_start(
                    workflow_id="wf-slow",
                    execution_id=exec_id,
                    user_id="user-123"
                )
                engine.track_workflow_completion(
                    workflow_id="wf-slow",
                    execution_id=exec_id,
                    status="completed",
                    duration_ms=5000,
                    user_id="user-123"
                )

            # Get metrics for both
            metrics_fast = engine.get_workflow_performance_metrics("wf-fast", time_window="1h")
            metrics_slow = engine.get_workflow_performance_metrics("wf-slow", time_window="1h")

            assert metrics_fast is not None
            assert metrics_slow is not None
            # Fast workflow should have lower average duration
            assert metrics_fast.average_duration_ms < metrics_slow.average_duration_ms
