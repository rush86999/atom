"""
Comprehensive tests for Analytics Engine

Target: 60%+ coverage for core/analytics_engine.py (186 lines)
Focus: Workflow metrics, integration metrics, data persistence, aggregation, error handling
"""

import pytest
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock

from core.analytics_engine import (
    AnalyticsEngine,
    WorkflowMetric,
    IntegrationMetric,
    get_analytics_engine
)


# ========================================================================
# Fixtures
# ========================================================================


@pytest.fixture
def temp_data_dir():
    """Create temporary directory for analytics data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def analytics_engine(temp_data_dir):
    """Create AnalyticsEngine instance with temporary data directory."""
    with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
        engine = AnalyticsEngine()
        # Force re-initialization for each test
        AnalyticsEngine._instance = None
        engine = AnalyticsEngine()
        engine.data_dir = temp_data_dir
        return engine


@pytest.fixture
def reset_analytics_engine():
    """Reset AnalyticsEngine singleton between tests."""
    AnalyticsEngine._instance = None
    yield
    AnalyticsEngine._instance = None


# ========================================================================
# TestAnalyticsEngine: Service Initialization and Configuration
# ========================================================================


class TestAnalyticsEngine:
    """Test analytics engine initialization and configuration."""

    def test_engine_singleton_pattern(self, reset_analytics_engine, temp_data_dir):
        """Test that AnalyticsEngine follows singleton pattern."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine1 = AnalyticsEngine()
            engine2 = AnalyticsEngine()

            assert engine1 is engine2
            assert engine1._initialized is True

    def test_engine_initialization_creates_data_dir(self, reset_analytics_engine):
        """Test that engine initialization creates data directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = os.path.join(tmpdir, "analytics_data")
            with patch('core.analytics_engine.os.path.join', return_value=data_dir):
                engine = AnalyticsEngine()
                assert os.path.exists(data_dir)

    def test_engine_initializes_empty_metrics(self, reset_analytics_engine, temp_data_dir):
        """Test that engine initializes with empty metrics."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            assert len(engine.workflow_metrics) == 0
            assert len(engine.integration_metrics) == 0

    def test_get_analytics_engine_singleton(self, reset_analytics_engine, temp_data_dir):
        """Test get_analytics_engine returns singleton instance."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = get_analytics_engine()
            engine2 = get_analytics_engine()

            assert engine is engine2

    def test_engine_loads_existing_data(self, reset_analytics_engine, temp_data_dir):
        """Test that engine loads existing metrics from files."""
        # Create existing workflow metrics file
        wf_path = os.path.join(temp_data_dir, "workflow_metrics.json")
        with open(wf_path, 'w') as f:
            json.dump({
                "wf-001": {
                    "execution_count": 10,
                    "success_count": 9,
                    "failure_count": 1,
                    "total_duration_seconds": 100.0,
                    "total_time_saved_seconds": 500.0,
                    "total_business_value": 1000.0,
                    "last_executed": "2026-03-17T10:00:00Z"
                }
            }, f)

        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            assert "wf-001" in engine.workflow_metrics
            assert engine.workflow_metrics["wf-001"].execution_count == 10

    def test_engine_loads_integration_data(self, reset_analytics_engine, temp_data_dir):
        """Test that engine loads existing integration metrics."""
        int_path = os.path.join(temp_data_dir, "integration_metrics.json")
        with open(int_path, 'w') as f:
            json.dump({
                "slack": {
                    "call_count": 100,
                    "error_count": 5,
                    "total_response_time_ms": 5000.0,
                    "last_called": "2026-03-17T10:00:00Z",
                    "status": "READY"
                }
            }, f)

        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            assert "slack" in engine.integration_metrics
            assert engine.integration_metrics["slack"].call_count == 100

    def test_engine_handles_corrupted_data_gracefully(self, reset_analytics_engine, temp_data_dir):
        """Test that engine handles corrupted JSON files gracefully."""
        # Create corrupted file
        wf_path = os.path.join(temp_data_dir, "workflow_metrics.json")
        with open(wf_path, 'w') as f:
            f.write("invalid json")

        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            # Should not crash
            engine = AnalyticsEngine()
            assert len(engine.workflow_metrics) == 0

    def test_engine_saves_data_on_initialization(self, reset_analytics_engine, temp_data_dir):
        """Test that engine creates data files on initialization."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # Files should exist
            wf_path = os.path.join(temp_data_dir, "workflow_metrics.json")
            int_path = os.path.join(temp_data_dir, "integration_metrics.json")

            assert os.path.exists(wf_path)
            assert os.path.exists(int_path)

    def test_engine_prevents_double_initialization(self, reset_analytics_engine, temp_data_dir):
        """Test that engine prevents double initialization."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.custom_attr = "test"

            # Create new instance (should return same object)
            engine2 = AnalyticsEngine()
            assert hasattr(engine2, 'custom_attr')
            assert engine2.custom_attr == "test"


# ========================================================================
# TestAnalyticsQueries: Workflow and Integration Metrics
# ========================================================================


class TestAnalyticsQueries:
    """Test workflow and integration metric queries."""

    def test_track_workflow_execution_creates_metric(self, reset_analytics_engine, temp_data_dir):
        """Test tracking workflow execution creates new metric."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.track_workflow_execution(
                workflow_id="wf-001",
                success=True,
                duration_seconds=10.5,
                time_saved_seconds=60.0,
                business_value=100.0
            )

            assert "wf-001" in engine.workflow_metrics
            metric = engine.workflow_metrics["wf-001"]
            assert metric.execution_count == 1
            assert metric.success_count == 1

    def test_track_workflow_execution_updates_existing(self, reset_analytics_engine, temp_data_dir):
        """Test tracking updates existing workflow metric."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # First execution
            engine.track_workflow_execution("wf-001", True, 10.0, 50.0, 100.0)
            # Second execution
            engine.track_workflow_execution("wf-001", True, 15.0, 75.0, 150.0)

            metric = engine.workflow_metrics["wf-001"]
            assert metric.execution_count == 2
            assert metric.success_count == 2
            assert metric.total_duration_seconds == 25.0

    def test_track_workflow_execution_counts_failures(self, reset_analytics_engine, temp_data_dir):
        """Test that workflow execution tracking counts failures."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.track_workflow_execution("wf-001", False, 10.0, 0.0, 0.0)

            metric = engine.workflow_metrics["wf-001"]
            assert metric.execution_count == 1
            assert metric.success_count == 0
            assert metric.failure_count == 1

    def test_track_workflow_execution_saves_to_disk(self, reset_analytics_engine, temp_data_dir):
        """Test that workflow tracking saves to disk."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.track_workflow_execution("wf-001", True, 10.0, 50.0, 100.0)

            # Load from file
            wf_path = os.path.join(temp_data_dir, "workflow_metrics.json")
            with open(wf_path, 'r') as f:
                data = json.load(f)
                assert "wf-001" in data

    def test_track_integration_call_creates_metric(self, reset_analytics_engine, temp_data_dir):
        """Test tracking integration call creates new metric."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.track_integration_call(
                integration_name="slack",
                success=True,
                response_time_ms=150.0
            )

            assert "slack" in engine.integration_metrics
            metric = engine.integration_metrics["slack"]
            assert metric.call_count == 1
            assert metric.error_count == 0

    def test_track_integration_call_updates_existing(self, reset_analytics_engine, temp_data_dir):
        """Test tracking updates existing integration metric."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            engine.track_integration_call("slack", True, 100.0)
            engine.track_integration_call("slack", True, 200.0)

            metric = engine.integration_metrics["slack"]
            assert metric.call_count == 2
            assert metric.total_response_time_ms == 300.0

    def test_track_integration_call_counts_errors(self, reset_analytics_engine, temp_data_dir):
        """Test that integration tracking counts errors."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.track_integration_call("slack", False, 100.0)

            metric = engine.integration_metrics["slack"]
            assert metric.call_count == 1
            assert metric.error_count == 1

    def test_track_integration_calculates_status_ready(self, reset_analytics_engine, temp_data_dir):
        """Test that integration status is READY with no errors."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # 10 successful calls
            for _ in range(10):
                engine.track_integration_call("slack", True, 100.0)

            metric = engine.integration_metrics["slack"]
            assert metric.status == "READY"

    def test_track_integration_calculates_status_partial(self, reset_analytics_engine, temp_data_dir):
        """Test that integration status is PARTIAL with some errors."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # 10 calls, 1 error
            for i in range(10):
                engine.track_integration_call("slack", i == 0, 100.0)

            metric = engine.integration_metrics["slack"]
            assert metric.status == "PARTIAL"

    def test_track_integration_calculates_status_error(self, reset_analytics_engine, temp_data_dir):
        """Test that integration status is ERROR with high error rate."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # 10 calls, 5 errors (50% error rate)
            for i in range(10):
                engine.track_integration_call("slack", i >= 5, 100.0)

            metric = engine.integration_metrics["slack"]
            assert metric.status == "ERROR"

    def test_track_integration_saves_to_disk(self, reset_analytics_engine, temp_data_dir):
        """Test that integration tracking saves to disk."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.track_integration_call("slack", True, 150.0)

            # Load from file
            int_path = os.path.join(temp_data_dir, "integration_metrics.json")
            with open(int_path, 'r') as f:
                data = json.load(f)
                assert "slack" in data


# ========================================================================
# TestAnalyticsReporting: Aggregation and Reporting
# ========================================================================


class TestAnalyticsReporting:
    """Test analytics aggregation and reporting."""

    def test_get_workflow_analytics_aggregates_all_workflows(self, reset_analytics_engine, temp_data_dir):
        """Test that workflow analytics aggregates all workflows."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # Track multiple workflows
            engine.track_workflow_execution("wf-001", True, 10.0, 50.0, 100.0)
            engine.track_workflow_execution("wf-002", True, 20.0, 100.0, 200.0)
            engine.track_workflow_execution("wf-003", False, 15.0, 0.0, 0.0)

            analytics = engine.get_workflow_analytics()

            assert analytics["total_executions"] == 3
            assert analytics["workflow_count"] == 3

    def test_get_workflow_analytics_calculates_time_saved(self, reset_analytics_engine, temp_data_dir):
        """Test that workflow analytics calculates time saved."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            engine.track_workflow_execution("wf-001", True, 10.0, 3600.0, 100.0)  # 1 hour
            engine.track_workflow_execution("wf-002", True, 10.0, 7200.0, 200.0)  # 2 hours

            analytics = engine.get_workflow_analytics()

            assert analytics["total_time_saved_hours"] == 3.0

    def test_get_workflow_analytics_calculates_business_value(self, reset_analytics_engine, temp_data_dir):
        """Test that workflow analytics calculates business value."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            engine.track_workflow_execution("wf-001", True, 10.0, 50.0, 500.0)
            engine.track_workflow_execution("wf-002", True, 10.0, 100.0, 750.0)

            analytics = engine.get_workflow_analytics()

            assert analytics["total_business_value"] == 1250.0

    def test_get_workflow_analytics_includes_individual_workflows(self, reset_analytics_engine, temp_data_dir):
        """Test that workflow analytics includes individual workflow data."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            engine.track_workflow_execution("wf-001", True, 10.0, 50.0, 100.0)

            analytics = engine.get_workflow_analytics()

            assert "workflows" in analytics
            assert "wf-001" in analytics["workflows"]
            assert analytics["workflows"]["wf-001"]["execution_count"] == 1

    def test_get_integration_health_aggregates_integrations(self, reset_analytics_engine, temp_data_dir):
        """Test that integration health aggregates all integrations."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            engine.track_integration_call("slack", True, 100.0)
            engine.track_integration_call("discord", True, 150.0)
            engine.track_integration_call("email", True, 200.0)

            health = engine.get_integration_health()

            assert health["total_integrations"] == 3

    def test_get_integration_health_counts_ready_integrations(self, reset_analytics_engine, temp_data_dir):
        """Test that integration health counts ready integrations."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # All successful calls
            for _ in range(10):
                engine.track_integration_call("slack", True, 100.0)

            # Some errors
            for i in range(10):
                engine.track_integration_call("discord", i < 1, 100.0)

            health = engine.get_integration_health()

            assert health["ready_count"] == 1  # Only slack is READY

    def test_get_integration_health_includes_individual_integrations(self, reset_analytics_engine, temp_data_dir):
        """Test that integration health includes individual integration data."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            engine.track_integration_call("slack", True, 100.0)

            health = engine.get_integration_health()

            assert "integrations" in health
            assert "slack" in health["integrations"]
            assert health["integrations"]["slack"]["call_count"] == 1

    def test_empty_analytics_returns_zeros(self, reset_analytics_engine, temp_data_dir):
        """Test that empty analytics returns zero values."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            workflow_analytics = engine.get_workflow_analytics()
            integration_health = engine.get_integration_health()

            assert workflow_analytics["total_executions"] == 0
            assert workflow_analytics["workflow_count"] == 0
            assert integration_health["total_integrations"] == 0
            assert integration_health["ready_count"] == 0


# ========================================================================
# TestWorkflowMetric: Metric Properties and Calculations
# ========================================================================


class TestWorkflowMetric:
    """Test WorkflowMetric dataclass properties."""

    def test_success_rate_zero_executions(self):
        """Test success rate with zero executions."""
        metric = WorkflowMetric()
        assert metric.success_rate == 0.0

    def test_success_rate_all_success(self):
        """Test success rate with all successful executions."""
        metric = WorkflowMetric(execution_count=10, success_count=10)
        assert metric.success_rate == 100.0

    def test_success_rate_partial_success(self):
        """Test success rate with partial success."""
        metric = WorkflowMetric(execution_count=10, success_count=7, failure_count=3)
        assert metric.success_rate == 70.0

    def test_average_duration_zero_executions(self):
        """Test average duration with zero executions."""
        metric = WorkflowMetric()
        assert metric.average_duration == 0.0

    def test_average_duration_multiple_executions(self):
        """Test average duration with multiple executions."""
        metric = WorkflowMetric(
            execution_count=3,
            total_duration_seconds=150.0
        )
        assert metric.average_duration == 50.0

    def test_workflow_metric_serialization(self):
        """Test that WorkflowMetric can be serialized to dict."""
        metric = WorkflowMetric(
            execution_count=10,
            success_count=9,
            failure_count=1,
            total_duration_seconds=100.0,
            total_time_saved_seconds=500.0,
            total_business_value=1000.0,
            last_executed="2026-03-17T10:00:00Z"
        )

        from dataclasses import asdict
        data = asdict(metric)

        assert data["execution_count"] == 10
        assert data["success_count"] == 9
        assert data["last_executed"] == "2026-03-17T10:00:00Z"


# ========================================================================
# TestIntegrationMetric: Metric Properties and Calculations
# ========================================================================


class TestIntegrationMetric:
    """Test IntegrationMetric dataclass properties."""

    def test_error_rate_zero_calls(self):
        """Test error rate with zero calls."""
        metric = IntegrationMetric()
        assert metric.error_rate == 0.0

    def test_error_rate_no_errors(self):
        """Test error rate with no errors."""
        metric = IntegrationMetric(call_count=100, error_count=0)
        assert metric.error_rate == 0.0

    def test_error_rate_with_errors(self):
        """Test error rate with some errors."""
        metric = IntegrationMetric(call_count=100, error_count=5)
        assert metric.error_rate == 5.0

    def test_average_response_time_zero_calls(self):
        """Test average response time with zero calls."""
        metric = IntegrationMetric()
        assert metric.average_response_time == 0.0

    def test_average_response_time_multiple_calls(self):
        """Test average response time with multiple calls."""
        metric = IntegrationMetric(
            call_count=5,
            total_response_time_ms=500.0
        )
        assert metric.average_response_time == 100.0

    def test_uptime_percentage_calculated_from_error_rate(self):
        """Test that uptime is 100% minus error rate."""
        metric = IntegrationMetric(call_count=100, error_count=10)
        assert metric.uptime_percentage == 90.0

    def test_integration_metric_default_status(self):
        """Test that default status is UNKNOWN."""
        metric = IntegrationMetric()
        assert metric.status == "UNKNOWN"

    def test_integration_metric_serialization(self):
        """Test that IntegrationMetric can be serialized to dict."""
        metric = IntegrationMetric(
            call_count=100,
            error_count=5,
            total_response_time_ms=5000.0,
            last_called="2026-03-17T10:00:00Z",
            status="READY"
        )

        from dataclasses import asdict
        data = asdict(metric)

        assert data["call_count"] == 100
        assert data["error_count"] == 5
        assert data["status"] == "READY"


# ========================================================================
# TestAnalyticsErrors: Error Handling and Edge Cases
# ========================================================================


class TestAnalyticsErrors:
    """Test analytics error handling and edge cases."""

    def test_save_data_handles_write_errors(self, reset_analytics_engine, temp_data_dir):
        """Test that save data handles write errors gracefully."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # Make directory read-only
            os.chmod(temp_data_dir, 0o444)

            # Should not crash
            engine.track_workflow_execution("wf-001", True, 10.0, 50.0, 100.0)

            # Restore permissions
            os.chmod(temp_data_dir, 0o755)

    def test_load_data_handles_missing_files(self, reset_analytics_engine, temp_data_dir):
        """Test that load data handles missing files gracefully."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            # Don't create any files
            engine = AnalyticsEngine()

            # Should not crash and have empty metrics
            assert len(engine.workflow_metrics) == 0
            assert len(engine.integration_metrics) == 0

    def test_get_workflow_analytics_with_negative_values(self, reset_analytics_engine, temp_data_dir):
        """Test that analytics handles negative values (edge case)."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # Manually add negative values (edge case from bad data)
            engine.workflow_metrics["wf-001"] = WorkflowMetric(
                execution_count=1,
                total_duration_seconds=-10.0
            )

            analytics = engine.get_workflow_analytics()

            # Should still return data
            assert "total_executions" in analytics

    def test_track_workflow_with_zero_duration(self, reset_analytics_engine, temp_data_dir):
        """Test tracking workflow with zero duration."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.track_workflow_execution("wf-001", True, 0.0, 50.0, 100.0)

            metric = engine.workflow_metrics["wf-001"]
            assert metric.execution_count == 1
            assert metric.total_duration_seconds == 0.0

    def test_track_integration_with_zero_response_time(self, reset_analytics_engine, temp_data_dir):
        """Test tracking integration with zero response time."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.track_integration_call("slack", True, 0.0)

            metric = engine.integration_metrics["slack"]
            assert metric.call_count == 1
            assert metric.total_response_time_ms == 0.0

    def test_concurrent_tracking_safety(self, reset_analytics_engine, temp_data_dir):
        """Test that concurrent tracking is safe (basic test)."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # Track same workflow multiple times rapidly
            for i in range(10):
                engine.track_workflow_execution(f"wf-{i}", True, 10.0, 50.0, 100.0)

            # All should be tracked
            assert len(engine.workflow_metrics) == 10

    def test_get_workflow_analytics_with_large_dataset(self, reset_analytics_engine, temp_data_dir):
        """Test analytics with large dataset."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()

            # Track 100 workflows
            for i in range(100):
                engine.track_workflow_execution(f"wf-{i}", True, 10.0, 50.0, 100.0)

            analytics = engine.get_workflow_analytics()

            assert analytics["total_executions"] == 100
            assert analytics["workflow_count"] == 100

    def test_workflow_metric_last_executed_format(self, reset_analytics_engine, temp_data_dir):
        """Test that last_executed is in ISO format."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.track_workflow_execution("wf-001", True, 10.0, 50.0, 100.0)

            metric = engine.workflow_metrics["wf-001"]

            # Should be ISO format string
            assert metric.last_executed is not None
            assert "T" in metric.last_executed  # ISO format has 'T'

    def test_integration_metric_last_called_format(self, reset_analytics_engine, temp_data_dir):
        """Test that last_called is in ISO format."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            engine = AnalyticsEngine()
            engine.track_integration_call("slack", True, 100.0)

            metric = engine.integration_metrics["slack"]

            # Should be ISO format string
            assert metric.last_called is not None
            assert "T" in metric.last_called  # ISO format has 'T'

    def test_metrics_persist_across_instances(self, reset_analytics_engine, temp_data_dir):
        """Test that metrics persist across engine instances."""
        with patch('core.analytics_engine.os.path.join', return_value=temp_data_dir):
            # First instance
            engine1 = AnalyticsEngine()
            engine1.track_workflow_execution("wf-001", True, 10.0, 50.0, 100.0)

            # Second instance (should load from disk)
            AnalyticsEngine._instance = None
            engine2 = AnalyticsEngine()

            assert "wf-001" in engine2.workflow_metrics
            assert engine2.workflow_metrics["wf-001"].execution_count == 1
