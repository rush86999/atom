"""
Integration tests for workflow_analytics_engine.py (Phase 12, GAP-02).

Tests cover:
- Database query aggregation with real DB operations
- Time series aggregation
- Percentile computation
- Success rate calculation
- Trend analysis
- Workflow execution tracking
- Performance metrics computation
- Alert management
- Event tracking

Coverage target: 50% of workflow_analytics_engine.py (297+ lines from 593 total)
Current coverage: 27.77% (165 lines)
Target coverage: 50%+ (297+ lines)

Key difference from property tests: These tests CALL actual analytics methods
(compute_workflow_metrics, compute_percentile, get_performance_metrics) with
real database operations, rather than just validating aggregation invariants.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.workflow_analytics_engine import (
    WorkflowAnalyticsEngine,
    WorkflowMetric,
    WorkflowExecutionEvent,
    MetricType,
    WorkflowStatus,
    PerformanceMetrics,
    AlertSeverity
)


class TestDatabaseQueryAggregation:
    """Integration tests for database query aggregation."""

    def test_aggregate_execution_metrics(self, db_session: Session):
        """Test actual metric aggregation from database."""
        # Create temporary database for this test
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_analytics.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create test workflow executions in database
            for i in range(10):
                engine.track_workflow_start(
                    workflow_id=f"test_workflow_{i % 3}",
                    execution_id=f"exec_{i}",
                    user_id="test_user"
                )
                engine.track_workflow_completion(
                    workflow_id=f"test_workflow_{i % 3}",
                    execution_id=f"exec_{i}",
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=5000 + i * 100
                )

            # Call actual aggregation method
            metrics = engine.get_performance_metrics(
                workflow_id="test_workflow_0",
                time_window="24h"
            )

            # Verify actual aggregation occurred
            assert metrics is not None
            assert metrics.total_executions > 0
            assert metrics.average_duration_ms > 0
            assert metrics.success_rate >= 0.0

    def test_aggregate_multiple_workflows(self, db_session: Session):
        """Test aggregation across multiple workflows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_multi.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Track multiple workflows
            workflow_ids = ["workflow_a", "workflow_b", "workflow_c"]
            for wf_id in workflow_ids:
                for i in range(5):
                    engine.track_workflow_start(
                        workflow_id=wf_id,
                        execution_id=f"{wf_id}_exec_{i}",
                        user_id="test_user"
                    )
                    engine.track_workflow_completion(
                        workflow_id=wf_id,
                        execution_id=f"{wf_id}_exec_{i}",
                        status=WorkflowStatus.COMPLETED,
                        duration_ms=3000 + i * 500
                    )

            # Verify each workflow has metrics
            for wf_id in workflow_ids:
                metrics = engine.get_performance_metrics(wf_id, time_window="24h")
                assert metrics is not None
                assert metrics.total_executions == 5


class TestTimeSeriesAggregation:
    """Integration tests for time series computation."""

    def test_execution_timeline(self, db_session: Session):
        """Test actual time series computation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_timeline.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create executions across time range
            base_time = datetime.utcnow() - timedelta(hours=5)
            for i in range(10):
                exec_id = f"time_exec_{i}"
                exec_time = base_time + timedelta(minutes=i * 30)
                engine.track_workflow_start(
                    workflow_id="timeline_test",
                    execution_id=exec_id,
                    user_id="test_user"
                )
                engine.track_workflow_completion(
                    workflow_id="timeline_test",
                    execution_id=exec_id,
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=3000
                )

            # Get execution timeline
            timeline = engine.get_execution_timeline(
                workflow_id="timeline_test",
                time_window="24h",
                interval="1h"
            )

            # Verify time series was computed
            assert len(timeline) > 0
            assert all("timestamp" in point and "value" in point for point in timeline)

    def test_time_series_with_failures(self, db_session: Session):
        """Test time series with failed executions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_failures.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create mix of successful and failed executions
            for i in range(10):
                exec_id = f"fail_exec_{i}"
                engine.track_workflow_start(
                    workflow_id="failure_test",
                    execution_id=exec_id,
                    user_id="test_user"
                )
                status = WorkflowStatus.COMPLETED if i % 2 == 0 else WorkflowStatus.FAILED
                engine.track_workflow_completion(
                    workflow_id="failure_test",
                    execution_id=exec_id,
                    status=status,
                    duration_ms=5000
                )

            timeline = engine.get_execution_timeline(
                workflow_id="failure_test",
                time_window="24h",
                interval="1h"
            )

            # Should have data points even with failures
            assert len(timeline) > 0


class TestPercentileComputation:
    """Integration tests for percentile computation."""

    def test_percentile_computation(self, db_session: Session):
        """Test actual percentile computation from data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_percentile.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create executions with varying times
            execution_times = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
            for i, time_ms in enumerate(execution_times):
                exec_id = f"pct_exec_{i}"
                engine.track_workflow_start(
                    workflow_id="percentile_test",
                    execution_id=exec_id,
                    user_id="test_user"
                )
                engine.track_workflow_completion(
                    workflow_id="percentile_test",
                    execution_id=exec_id,
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=time_ms
                )

            # Get performance metrics with percentiles
            metrics = engine.get_performance_metrics(
                workflow_id="percentile_test",
                time_window="24h"
            )

            # Verify percentiles
            assert metrics is not None
            assert metrics.median_duration_ms > 0
            assert metrics.p95_duration_ms > 0
            assert metrics.p99_duration_ms > 0
            # P95 should be higher than median
            assert metrics.p95_duration_ms >= metrics.median_duration_ms

    def test_percentile_with_single_execution(self, db_session: Session):
        """Test percentile computation with single data point."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_single_pct.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            engine.track_workflow_start(
                workflow_id="single_test",
                execution_id="single_exec",
                user_id="test_user"
            )
            engine.track_workflow_completion(
                workflow_id="single_test",
                execution_id="single_exec",
                status=WorkflowStatus.COMPLETED,
                duration_ms=1000
            )

            metrics = engine.get_performance_metrics(
                workflow_id="single_test",
                time_window="24h"
            )

            # All percentiles should be same for single execution
            assert metrics.median_duration_ms == 1000
            assert metrics.p95_duration_ms == 1000


class TestSuccessRateCalculation:
    """Integration tests for success rate computation."""

    def test_success_rate_all_successful(self, db_session: Session):
        """Test success rate with all successful executions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_success.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create all successful executions
            for i in range(10):
                exec_id = f"success_exec_{i}"
                engine.track_workflow_start(
                    workflow_id="success_test",
                    execution_id=exec_id,
                    user_id="test_user"
                )
                engine.track_workflow_completion(
                    workflow_id="success_test",
                    execution_id=exec_id,
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=5000
                )

            metrics = engine.get_performance_metrics(
                workflow_id="success_test",
                time_window="24h"
            )

            # Should have 100% success rate
            assert metrics.success_rate == 1.0

    def test_success_rate_mixed(self, db_session: Session):
        """Test success rate with mixed results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_mixed.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create mix of successful and failed executions
            for i in range(10):
                exec_id = f"mixed_exec_{i}"
                engine.track_workflow_start(
                    workflow_id="mixed_test",
                    execution_id=exec_id,
                    user_id="test_user"
                )
                status = WorkflowStatus.COMPLETED if i < 7 else WorkflowStatus.FAILED
                engine.track_workflow_completion(
                    workflow_id="mixed_test",
                    execution_id=exec_id,
                    status=status,
                    duration_ms=5000
                )

            metrics = engine.get_performance_metrics(
                workflow_id="mixed_test",
                time_window="24h"
            )

            # Should have 70% success rate (7/10)
            assert 0.65 <= metrics.success_rate <= 0.75

    def test_success_rate_all_failed(self, db_session: Session):
        """Test success rate with all failed executions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_fail.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create all failed executions
            for i in range(5):
                exec_id = f"fail_exec_{i}"
                engine.track_workflow_start(
                    workflow_id="all_fail_test",
                    execution_id=exec_id,
                    user_id="test_user"
                )
                engine.track_workflow_completion(
                    workflow_id="all_fail_test",
                    execution_id=exec_id,
                    status=WorkflowStatus.FAILED,
                    duration_ms=3000
                )

            metrics = engine.get_performance_metrics(
                workflow_id="all_fail_test",
                time_window="24h"
            )

            # Should have 0% success rate
            assert metrics.success_rate == 0.0


class TestTrendAnalysis:
    """Integration tests for trend computation."""

    def test_trend_improving(self, db_session: Session):
        """Test detecting improving trend (decreasing duration)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_improve.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create executions with decreasing duration
            base_time = datetime.utcnow() - timedelta(hours=1)
            for i in range(10):
                exec_id = f"improve_exec_{i}"
                exec_time = base_time + timedelta(minutes=i * 6)
                engine.track_workflow_start(
                    workflow_id="improve_test",
                    execution_id=exec_id,
                    user_id="test_user"
                )
                # Duration decreases over time
                duration = 10000 - (i * 1000)
                engine.track_workflow_completion(
                    workflow_id="improve_test",
                    execution_id=exec_id,
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=duration
                )

            # Get metrics - should show average duration
            metrics = engine.get_performance_metrics(
                workflow_id="improve_test",
                time_window="24h"
            )

            # Average should be lower than initial duration
            assert metrics is not None
            assert metrics.average_duration_ms < 10000

    def test_trend_degrading(self, db_session: Session):
        """Test detecting degrading trend (increasing duration)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_degrade.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create executions with increasing duration
            base_time = datetime.utcnow() - timedelta(hours=1)
            for i in range(10):
                exec_id = f"degrade_exec_{i}"
                exec_time = base_time + timedelta(minutes=i * 6)
                engine.track_workflow_start(
                    workflow_id="degrade_test",
                    execution_id=exec_id,
                    user_id="test_user"
                )
                # Duration increases over time
                duration = 1000 + (i * 1000)
                engine.track_workflow_completion(
                    workflow_id="degrade_test",
                    execution_id=exec_id,
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=duration
                )

            metrics = engine.get_performance_metrics(
                workflow_id="degrade_test",
                time_window="24h"
            )

            # Average should be higher than initial duration
            assert metrics is not None
            assert metrics.average_duration_ms > 1000


class TestErrorBreakdown:
    """Integration tests for error analysis."""

    def test_error_breakdown_by_type(self, db_session: Session):
        """Test error breakdown aggregation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_error.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create executions with different error types
            error_types = ["TimeoutError", "ValueError", "ConnectionError", "TimeoutError"]
            for i, error_type in enumerate(error_types):
                exec_id = f"error_exec_{i}"
                engine.track_workflow_start(
                    workflow_id="error_test",
                    execution_id=exec_id,
                    user_id="test_user"
                )
                engine.track_workflow_completion(
                    workflow_id="error_test",
                    execution_id=exec_id,
                    status=WorkflowStatus.FAILED,
                    duration_ms=3000,
                    error_message=error_type
                )

            # Get error breakdown
            error_breakdown = engine.get_error_breakdown(
                workflow_id="error_test",
                time_window="24h"
            )

            # Verify error breakdown
            assert error_breakdown is not None
            assert "total_errors" in error_breakdown
            assert error_breakdown["total_errors"] == 4

    def test_error_breakdown_no_errors(self, db_session: Session):
        """Test error breakdown when no errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_no_error.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create successful execution
            engine.track_workflow_start(
                workflow_id="no_error_test",
                execution_id="no_error_exec",
                user_id="test_user"
            )
            engine.track_workflow_completion(
                workflow_id="no_error_test",
                execution_id="no_error_exec",
                status=WorkflowStatus.COMPLETED,
                duration_ms=2000
            )

            error_breakdown = engine.get_error_breakdown(
                workflow_id="no_error_test",
                time_window="24h"
            )

            # Should have zero errors
            assert error_breakdown["total_errors"] == 0


class TestAlertManagement:
    """Integration tests for alert creation and management."""

    def test_create_alert(self, db_session: Session):
        """Test creating an alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_alert.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create alert
            alert = engine.create_alert(
                name="Test Alert",
                description="Test alert description",
                severity=AlertSeverity.HIGH,
                workflow_id="test_workflow",
                metric_name="error_rate",
                threshold_value=0.1,
                condition="greater_than"
            )

            # Verify alert was created
            assert alert is not None
            assert alert["name"] == "Test Alert"
            assert alert["severity"] == AlertSeverity.HIGH

    def test_get_alerts(self, db_session: Session):
        """Test retrieving alerts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_get_alerts.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create multiple alerts
            engine.create_alert(
                name="Alert 1",
                description="First alert",
                severity=AlertSeverity.LOW,
                workflow_id="workflow_a"
            )
            engine.create_alert(
                name="Alert 2",
                description="Second alert",
                severity=AlertSeverity.HIGH,
                workflow_id="workflow_b"
            )

            # Get all alerts
            alerts = engine.get_all_alerts()

            # Verify alerts retrieved
            assert len(alerts) == 2

    def test_delete_alert(self, db_session: Session):
        """Test deleting an alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_delete_alert.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create alert
            alert = engine.create_alert(
                name="Delete Test",
                description="To be deleted",
                severity=AlertSeverity.MEDIUM
            )

            # Delete alert
            engine.delete_alert(alert["id"])

            # Verify deleted
            alerts = engine.get_all_alerts(enabled_only=False)
            assert len(alerts) == 0


class TestWorkflowTracking:
    """Integration tests for workflow execution tracking."""

    def test_track_workflow_lifecycle(self, db_session: Session):
        """Test tracking complete workflow lifecycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_lifecycle.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Track workflow start
            engine.track_workflow_start(
                workflow_id="lifecycle_test",
                execution_id="lifecycle_exec",
                user_id="test_user"
            )

            # Track workflow completion
            engine.track_workflow_completion(
                workflow_id="lifecycle_test",
                execution_id="lifecycle_exec",
                status=WorkflowStatus.COMPLETED,
                duration_ms=5000
            )

            # Verify metrics recorded
            metrics = engine.get_performance_metrics(
                workflow_id="lifecycle_test",
                time_window="24h"
            )

            assert metrics is not None
            assert metrics.total_executions == 1

    def test_track_step_execution(self, db_session: Session):
        """Test tracking individual step execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_step.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Track step execution
            engine.track_step_execution(
                workflow_id="step_test",
                execution_id="step_exec",
                step_id="step1",
                step_name="First Step",
                event_type="step_completed",
                duration_ms=1000,
                status="COMPLETED"
            )

            # Get recent events
            events = engine.get_recent_events(limit=10)

            # Verify step event tracked
            assert len(events) > 0
            step_events = [e for e in events if e.step_id == "step1"]
            assert len(step_events) > 0


class TestSystemOverview:
    """Integration tests for system-wide metrics."""

    def test_system_overview(self, db_session: Session):
        """Test getting system overview."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_overview.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create multiple workflow executions
            for i in range(5):
                engine.track_workflow_start(
                    workflow_id=f"overview_workflow_{i}",
                    execution_id=f"overview_exec_{i}",
                    user_id="test_user"
                )
                engine.track_workflow_completion(
                    workflow_id=f"overview_workflow_{i}",
                    execution_id=f"overview_exec_{i}",
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=3000 + i * 1000
                )

            # Get system overview
            overview = engine.get_system_overview(time_window="24h")

            # Verify overview metrics
            assert overview is not None
            assert "total_workflows" in overview
            assert "total_executions" in overview
            assert overview["total_executions"] >= 5

    def test_unique_workflow_count(self, db_session: Session):
        """Test counting unique workflows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_unique.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create executions for different workflows
            workflow_ids = ["wf_a", "wf_b", "wf_a", "wf_c", "wf_b"]
            for i, wf_id in enumerate(workflow_ids):
                engine.track_workflow_start(
                    workflow_id=wf_id,
                    execution_id=f"unique_exec_{i}",
                    user_id="test_user"
                )
                engine.track_workflow_completion(
                    workflow_id=wf_id,
                    execution_id=f"unique_exec_{i}",
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=2000
                )

            # Count unique workflows
            unique_count = engine.get_unique_workflow_count(time_window="24h")

            # Should have 3 unique workflows (a, b, c)
            assert unique_count == 3


class TestEventRetrieval:
    """Integration tests for event retrieval and querying."""

    def test_get_recent_events(self, db_session: Session):
        """Test retrieving recent events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_events.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create multiple events
            for i in range(5):
                engine.track_workflow_start(
                    workflow_id="events_test",
                    execution_id=f"event_exec_{i}",
                    user_id="test_user"
                )

            # Get recent events
            events = engine.get_recent_events(limit=10)

            # Verify events retrieved
            assert len(events) >= 5

    def test_get_events_by_workflow(self, db_session: Session):
        """Test filtering events by workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_filter_events.db"
            engine = WorkflowAnalyticsEngine(db_path=str(db_path))

            # Create events for different workflows
            engine.track_workflow_start(
                workflow_id="filter_test_a",
                execution_id="filter_exec_a",
                user_id="test_user"
            )
            engine.track_workflow_start(
                workflow_id="filter_test_b",
                execution_id="filter_exec_b",
                user_id="test_user"
            )

            # Get events for specific workflow
            events = engine.get_recent_events(
                limit=10,
                workflow_id="filter_test_a"
            )

            # Verify filtering
            assert all(e.workflow_id == "filter_test_a" for e in events)
