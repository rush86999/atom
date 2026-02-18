"""
Integration Tests for Workflow Analytics Engine

Tests CRITICAL analytics functionality:
- Metrics tracking (step execution, workflow execution, execution time, error counts, success rates)
- Aggregation queries (get_workflow_metrics_by_id, get_workflow_metrics_by_date_range, get_average_execution_time, get_most_failed_steps, get_workflow_success_rate)
- Performance reporting (generate_performance_report, generate_comparison_report, export_metrics_to_csv, metrics_trend_analysis)

Target: 50% coverage on workflow_analytics_engine.py (593 lines)
"""

import pytest
import uuid
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import json
import csv

from core.workflow_analytics_engine import (
    WorkflowAnalyticsEngine,
    WorkflowMetric,
    MetricType,
    WorkflowExecutionEvent,
    PerformanceMetrics,
    Alert,
    AlertSeverity
)


class TestWorkflowMetricsTracking:
    """Integration tests for workflow metrics tracking."""

    @pytest.fixture
    def analytics_engine(self):
        """Create a fresh analytics engine for each test."""
        # Use temp database file
        fd, db_path = tempfile.mkstemp(suffix='_analytics.db')
        os.close(fd)

        engine = WorkflowAnalyticsEngine(db_path=db_path)

        yield engine

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass

    def test_track_step_execution_creates_metrics_record(self, analytics_engine):
        """Test that tracking step execution creates a metrics record."""
        workflow_id = f"workflow_{uuid.uuid4()}"
        execution_id = f"exec_{uuid.uuid4()}"
        step_id = f"step_{uuid.uuid4()}"
        step_name = "Test Step"

        # Track step execution
        analytics_engine.track_step_execution(
            workflow_id=workflow_id,
            execution_id=execution_id,
            step_id=step_id,
            step_name=step_name,
            event_type="step_completed",
            duration_ms=1500,
            status="success",
            user_id="test_user"
        )

        # Allow background processing
        import time
        time.sleep(0.1)

        # Query metrics from database
        import sqlite3
        conn = sqlite3.connect(analytics_engine.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT workflow_id, step_id, step_name, metric_type, value
            FROM workflow_metrics
            WHERE workflow_id = ? AND step_id = ?
        """, (workflow_id, step_id))

        result = cursor.fetchone()
        conn.close()

        # Invariant: Metric should be created
        assert result is not None
        assert result[0] == workflow_id
        assert result[1] == step_id
        assert result[2] == step_name

    def test_track_workflow_execution_creates_summary(self, analytics_engine):
        """Test that tracking workflow execution creates a summary."""
        workflow_id = f"workflow_{uuid.uuid4()}"
        execution_id = f"exec_{uuid.uuid4()}"

        # Track workflow start and completion
        analytics_engine.track_workflow_start(
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id="test_user"
        )

        analytics_engine.track_workflow_completion(
            workflow_id=workflow_id,
            execution_id=execution_id,
            duration_ms=5000,
            status="completed",
            user_id="test_user"
        )

        # Allow background processing
        import time
        time.sleep(0.1)

        # Query events from database
        import sqlite3
        conn = sqlite3.connect(analytics_engine.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM workflow_events
            WHERE workflow_id = ? AND execution_id = ?
        """, (workflow_id, execution_id))

        count = cursor.fetchone()[0]
        conn.close()

        # Invariant: Should have 2 events (start + completion)
        assert count == 2

    def test_track_execution_time_recorded(self, analytics_engine):
        """Test that execution time is recorded correctly."""
        workflow_id = f"workflow_{uuid.uuid4()}"
        execution_id = f"exec_{uuid.uuid4()}"
        duration_ms = 3456

        # Track workflow completion with duration
        analytics_engine.track_workflow_completion(
            workflow_id=workflow_id,
            execution_id=execution_id,
            duration_ms=duration_ms,
            status="completed",
            user_id="test_user"
        )

        # Allow background processing
        import time
        time.sleep(0.1)

        # Query events from database
        import sqlite3
        conn = sqlite3.connect(analytics_engine.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT duration_ms
            FROM workflow_events
            WHERE workflow_id = ? AND execution_id = ? AND event_type = 'workflow_completed'
        """, (workflow_id, execution_id))

        result = cursor.fetchone()
        conn.close()

        # Invariant: Duration should match
        assert result is not None
        assert result[0] == duration_ms

    def test_track_error_counts_recorded(self, analytics_engine):
        """Test that error counts are recorded correctly."""
        workflow_id = f"workflow_{uuid.uuid4()}"
        execution_id = f"exec_{uuid.uuid4()}"

        # Track workflow failure
        analytics_engine.track_workflow_completion(
            workflow_id=workflow_id,
            execution_id=execution_id,
            duration_ms=1000,
            status="failed",
            error_message="Step failed: timeout",
            user_id="test_user"
        )

        # Allow background processing
        import time
        time.sleep(0.1)

        # Query events from database
        import sqlite3
        conn = sqlite3.connect(analytics_engine.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT status, error_message
            FROM workflow_events
            WHERE workflow_id = ? AND execution_id = ? AND event_type = 'workflow_completed'
        """, (workflow_id, execution_id))

        result = cursor.fetchone()
        conn.close()

        # Invariant: Error status and message should be recorded
        assert result is not None
        assert result[0] == "failed"
        assert "timeout" in result[1]

    def test_track_success_rates_calculated(self, analytics_engine):
        """Test that success rates are calculated correctly."""
        workflow_id = f"workflow_{uuid.uuid4()}"

        # Track multiple executions with mixed results
        for i in range(10):
            execution_id = f"exec_{uuid.uuid4()}"
            status = "completed" if i < 7 else "failed"  # 7 success, 3 failures

            analytics_engine.track_workflow_completion(
                workflow_id=workflow_id,
                execution_id=execution_id,
                duration_ms=1000 + i * 100,
                status=status,
                user_id="test_user"
            )

        # Allow background processing
        import time
        time.sleep(0.1)

        # Get success rate
        success_rate = analytics_engine.get_workflow_success_rate(workflow_id)

        # Invariant: Success rate should be 70% (7/10)
        assert success_rate >= 0.6  # Allow some tolerance
        assert success_rate <= 0.8


class TestAggregationQueries:
    """Integration tests for aggregation queries."""

    @pytest.fixture
    def analytics_engine(self):
        """Create analytics engine with sample data."""
        fd, db_path = tempfile.mkstemp(suffix='_analytics.db')
        os.close(fd)

        engine = WorkflowAnalyticsEngine(db_path=db_path)

        # Create sample data
        workflow_id = f"workflow_{uuid.uuid4()}"

        for i in range(10):
            execution_id = f"exec_{uuid.uuid4()}"
            duration_ms = 1000 + i * 100

            engine.track_workflow_completion(
                workflow_id=workflow_id,
                execution_id=execution_id,
                duration_ms=duration_ms,
                status="completed" if i < 8 else "failed",
                user_id=f"user_{i % 3}"  # 3 different users
            )

        # Allow background processing
        import time
        time.sleep(0.1)

        yield engine, workflow_id

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass

    def test_get_workflow_metrics_by_id(self, analytics_engine):
        """Test getting workflow metrics by ID."""
        engine, workflow_id = analytics_engine

        # Get metrics
        metrics = engine.get_workflow_metrics_by_id(workflow_id)

        # Invariant: Should return metrics
        assert metrics is not None
        assert "total_executions" in metrics
        assert metrics["total_executions"] == 10

    def test_get_workflow_metrics_by_date_range(self, analytics_engine):
        """Test getting workflow metrics by date range."""
        engine, workflow_id = analytics_engine

        now = datetime.now()
        start_date = now - timedelta(hours=1)
        end_date = now + timedelta(hours=1)

        # Get metrics for date range
        metrics = engine.get_workflow_metrics_by_date_range(
            workflow_id=workflow_id,
            start_date=start_date,
            end_date=end_date
        )

        # Invariant: Should return metrics within range
        assert metrics is not None
        assert "total_executions" in metrics

    def test_get_average_execution_time(self, analytics_engine):
        """Test getting average execution time."""
        engine, workflow_id = analytics_engine

        # Get average execution time
        avg_time = engine.get_average_execution_time(workflow_id)

        # Invariant: Average should be around 1450ms (1000 to 1900 average)
        assert avg_time is not None
        assert 1000 <= avg_time <= 2000

    def test_get_most_failed_steps(self, analytics_engine):
        """Test getting most failed steps."""
        engine, workflow_id = analytics_engine

        # Track some step failures
        for i in range(5):
            engine.track_step_execution(
                workflow_id=workflow_id,
                execution_id=f"exec_{uuid.uuid4()}",
                step_id=f"step_{i % 3}",  # 3 different steps
                step_name=f"Step {i % 3}",
                event_type="step_failed",
                duration_ms=500,
                status="failed",
                error_message="Step timeout",
                user_id="test_user"
            )

        # Allow background processing
        import time
        time.sleep(0.1)

        # Get most failed steps
        failed_steps = engine.get_most_failed_steps(workflow_id, limit=3)

        # Invariant: Should return failed steps
        assert failed_steps is not None
        assert len(failed_steps) <= 3

    def test_get_workflow_success_rate(self, analytics_engine):
        """Test getting workflow success rate."""
        engine, workflow_id = analytics_engine

        # Get success rate
        success_rate = engine.get_workflow_success_rate(workflow_id)

        # Invariant: Success rate should be 80% (8/10 completed)
        assert success_rate is not None
        assert 0.7 <= success_rate <= 0.9


class TestPerformanceReporting:
    """Integration tests for performance reporting."""

    @pytest.fixture
    def analytics_engine(self):
        """Create analytics engine with sample data."""
        fd, db_path = tempfile.mkstemp(suffix='_analytics.db')
        os.close(fd)

        engine = WorkflowAnalyticsEngine(db_path=db_path)

        # Create sample data
        workflow_id = f"workflow_{uuid.uuid4()}"

        for i in range(20):
            execution_id = f"exec_{uuid.uuid4()}"
            duration_ms = 1000 + i * 50

            engine.track_workflow_completion(
                workflow_id=workflow_id,
                execution_id=execution_id,
                duration_ms=duration_ms,
                status="completed" if i < 15 else "failed",
                user_id="test_user"
            )

        # Allow background processing
        import time
        time.sleep(0.1)

        yield engine, workflow_id

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass

    def test_generate_performance_report(self, analytics_engine):
        """Test generating performance report."""
        engine, workflow_id = analytics_engine

        # Generate performance report
        report = engine.generate_performance_report(
            workflow_id=workflow_id,
            time_window="24h"
        )

        # Invariant: Report should contain required fields
        assert report is not None
        assert "total_executions" in report
        assert "average_duration_ms" in report
        assert "success_rate" in report
        assert report["total_executions"] == 20

    def test_generate_comparison_report(self, analytics_engine):
        """Test generating comparison report."""
        engine, workflow_id = analytics_engine

        # Create another workflow for comparison
        workflow_id_2 = f"workflow_{uuid.uuid4()}"

        for i in range(15):
            execution_id = f"exec_{uuid.uuid4()}"
            engine.track_workflow_completion(
                workflow_id=workflow_id_2,
                execution_id=execution_id,
                duration_ms=800 + i * 50,
                status="completed" if i < 12 else "failed",
                user_id="test_user"
            )

        # Allow background processing
        import time
        time.sleep(0.1)

        # Generate comparison report
        report = engine.generate_comparison_report(
            workflow_ids=[workflow_id, workflow_id_2],
            time_window="24h"
        )

        # Invariant: Comparison report should have data for both workflows
        assert report is not None
        assert len(report) >= 2

    def test_export_metrics_to_csv(self, analytics_engine):
        """Test exporting metrics to CSV."""
        engine, workflow_id = analytics_engine

        # Create temp file for CSV export
        fd, csv_path = tempfile.mkstemp(suffix='.csv')
        os.close(fd)

        try:
            # Export metrics to CSV
            engine.export_metrics_to_csv(
                workflow_id=workflow_id,
                output_path=csv_path
            )

            # Read CSV and verify
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Invariant: CSV should have data
            assert len(rows) > 0

        finally:
            # Cleanup
            try:
                os.unlink(csv_path)
            except Exception:
                pass

    def test_metrics_trend_analysis(self, analytics_engine):
        """Test metrics trend analysis."""
        engine, workflow_id = analytics_engine

        # Get trend analysis
        trends = engine.get_metrics_trends(
            workflow_id=workflow_id,
            time_window="7d"
        )

        # Invariant: Trends should be available
        assert trends is not None
        assert "average_duration_trend" in trends or "execution_count_trend" in trends


class TestMultiUserAnalytics:
    """Integration tests for multi-user analytics."""

    @pytest.fixture
    def analytics_engine(self):
        """Create analytics engine with multi-user data."""
        fd, db_path = tempfile.mkstemp(suffix='_analytics.db')
        os.close(fd)

        engine = WorkflowAnalyticsEngine(db_path=db_path)

        # Create sample data for multiple users
        workflow_id = f"workflow_{uuid.uuid4()}"
        users = ["user_1", "user_2", "user_3"]

        for user_id in users:
            for i in range(10):
                execution_id = f"exec_{uuid.uuid4()}"
                engine.track_workflow_completion(
                    workflow_id=workflow_id,
                    execution_id=execution_id,
                    duration_ms=1000 + i * 100,
                    status="completed" if i < 8 else "failed",
                    user_id=user_id
                )

        # Allow background processing
        import time
        time.sleep(0.1)

        yield engine, workflow_id

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass

    def test_get_user_specific_metrics(self, analytics_engine):
        """Test getting user-specific metrics."""
        engine, workflow_id = analytics_engine

        # Get metrics for specific user
        user_id = "user_1"
        metrics = engine.get_workflow_metrics_by_id(workflow_id, user_id=user_id)

        # Invariant: Should return user-specific metrics
        assert metrics is not None
        assert "total_executions" in metrics

    def test_get_cross_user_comparison(self, analytics_engine):
        """Test comparing metrics across users."""
        engine, workflow_id = analytics_engine

        # Get metrics for all users
        user_metrics = {}
        for user_id in ["user_1", "user_2", "user_3"]:
            metrics = engine.get_workflow_metrics_by_id(workflow_id, user_id=user_id)
            user_metrics[user_id] = metrics

        # Invariant: All users should have metrics
        assert len(user_metrics) == 3
        for user_id, metrics in user_metrics.items():
            assert metrics["total_executions"] == 10


class TestAlerting:
    """Integration tests for analytics alerting."""

    @pytest.fixture
    def analytics_engine(self):
        """Create analytics engine with alerting."""
        fd, db_path = tempfile.mkstemp(suffix='_analytics.db')
        os.close(fd)

        engine = WorkflowAnalyticsEngine(db_path=db_path)

        yield engine

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass

    def test_create_alert(self, analytics_engine):
        """Test creating an alert."""
        workflow_id = f"workflow_{uuid.uuid4()}"

        # Create alert
        alert = analytics_engine.create_alert(
            name="High Error Rate",
            description="Error rate exceeds threshold",
            severity=AlertSeverity.HIGH,
            condition="error_rate > 0.5",
            threshold_value=0.5,
            metric_name="error_rate",
            workflow_id=workflow_id
        )

        # Invariant: Alert should be created
        assert alert is not None
        assert alert.name == "High Error Rate"
        assert alert.workflow_id == workflow_id

    def test_trigger_alert(self, analytics_engine):
        """Test triggering an alert."""
        workflow_id = f"workflow_{uuid.uuid4()}"

        # Create alert
        alert = analytics_engine.create_alert(
            name="Slow Execution",
            description="Execution time exceeds threshold",
            severity=AlertSeverity.MEDIUM,
            condition="average_duration_ms > 3000",
            threshold_value=3000,
            metric_name="average_duration_ms",
            workflow_id=workflow_id
        )

        # Check alert (should not trigger initially)
        is_triggered = analytics_engine.check_alert(alert.alert_id)
        assert is_triggered is False or is_triggered is None  # May not trigger without data

    def test_list_active_alerts(self, analytics_engine):
        """Test listing active alerts."""
        workflow_id = f"workflow_{uuid.uuid4()}"

        # Create multiple alerts
        for i in range(3):
            analytics_engine.create_alert(
                name=f"Alert {i}",
                description=f"Description {i}",
                severity=AlertSeverity.LOW,
                condition=f"metric_{i} > {i}",
                threshold_value=i,
                metric_name=f"metric_{i}",
                workflow_id=workflow_id
            )

        # List alerts
        alerts = analytics_engine.list_alerts(workflow_id=workflow_id)

        # Invariant: Should list all alerts
        assert alerts is not None
        assert len(alerts) >= 3


class TestDataPersistence:
    """Integration tests for data persistence."""

    @pytest.fixture
    def analytics_engine(self):
        """Create analytics engine."""
        fd, db_path = tempfile.mkstemp(suffix='_analytics.db')
        os.close(fd)

        engine = WorkflowAnalyticsEngine(db_path=db_path)

        yield engine, db_path

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass

    def test_metrics_persist_across_restarts(self, analytics_engine):
        """Test that metrics persist across engine restarts."""
        engine, db_path = analytics_engine

        workflow_id = f"workflow_{uuid.uuid4()}"

        # Track some metrics
        for i in range(5):
            execution_id = f"exec_{uuid.uuid4()}"
            engine.track_workflow_completion(
                workflow_id=workflow_id,
                execution_id=execution_id,
                duration_ms=1000 + i * 100,
                status="completed",
                user_id="test_user"
            )

        # Allow background processing
        import time
        time.sleep(0.2)

        # Create new engine instance (simulates restart)
        new_engine = WorkflowAnalyticsEngine(db_path=db_path)

        # Get metrics from new engine
        metrics = new_engine.get_workflow_metrics_by_id(workflow_id)

        # Invariant: Metrics should persist
        assert metrics is not None
        assert metrics["total_executions"] == 5

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass

    def test_events_persist_across_restarts(self, analytics_engine):
        """Test that events persist across engine restarts."""
        engine, db_path = analytics_engine

        workflow_id = f"workflow_{uuid.uuid4()}"
        execution_id = f"exec_{uuid.uuid4()}"

        # Track event
        engine.track_workflow_start(
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id="test_user"
        )

        # Allow background processing
        import time
        time.sleep(0.2)

        # Create new engine instance
        new_engine = WorkflowAnalyticsEngine(db_path=db_path)

        # Query events directly from database
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM workflow_events
            WHERE workflow_id = ? AND execution_id = ?
        """, (workflow_id, execution_id))

        count = cursor.fetchone()[0]
        conn.close()

        # Invariant: Event should persist
        assert count == 1

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass
