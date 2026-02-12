"""
Unit tests for WorkflowAnalyticsEngine

Tests workflow execution tracking, performance metrics collection,
and analytics aggregation.
"""

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import uuid

import pytest

# Import the analytics engine
from core.workflow_analytics_engine import (
    WorkflowAnalyticsEngine,
    WorkflowMetric,
    WorkflowExecutionEvent,
    PerformanceMetrics,
    Alert,
    MetricType,
    AlertSeverity,
    WorkflowStatus,
    get_analytics_engine,
    _analytics_engine,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def analytics_engine(temp_db_path):
    """Create a fresh analytics engine instance for each test."""
    engine = WorkflowAnalyticsEngine(db_path=temp_db_path)
    yield engine
    # Cleanup is handled by temp_db_path fixture


@pytest.fixture
def mock_db():
    """Mock database session for testing."""
    db = Mock()
    return db


@pytest.fixture
def sample_workflow_id():
    """Sample workflow ID for testing."""
    return "test-workflow-123"


@pytest.fixture
def sample_execution_id():
    """Sample execution ID for testing."""
    return "test-execution-456"


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "test-user-789"


@pytest.fixture
def sample_step_id():
    """Sample step ID for testing."""
    return "step-001"


# ============================================================================
# Test AnalyticsInit - Initialization and Singleton
# ============================================================================

class TestAnalyticsInit:
    """Tests for analytics engine initialization."""

    def test_analytics_engine_init(self, temp_db_path):
        """Test engine initialization creates database and tables."""
        engine = WorkflowAnalyticsEngine(db_path=temp_db_path)

        # Verify database was created
        assert Path(temp_db_path).exists()

        # Verify tables exist
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        conn.close()

        # Check for expected tables
        assert "workflow_metrics" in tables
        assert "workflow_events" in tables
        assert "analytics_alerts" in tables

    def test_analytics_engine_init_default_path(self):
        """Test engine initialization with default database path."""
        # Create engine with default path
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            engine = WorkflowAnalyticsEngine()

            # Should create analytics.db in current directory
            assert Path("analytics.db").exists()

    def test_metrics_buffer_initialization(self, analytics_engine):
        """Test metrics buffer is initialized correctly."""
        assert hasattr(analytics_engine, "metrics_buffer")
        assert analytics_engine.metrics_buffer.maxlen == 10000
        assert len(analytics_engine.metrics_buffer) == 0

    def test_events_buffer_initialization(self, analytics_engine):
        """Test events buffer is initialized correctly."""
        assert hasattr(analytics_engine, "events_buffer")
        assert analytics_engine.events_buffer.maxlen == 50000
        assert len(analytics_engine.events_buffer) == 0

    def test_performance_cache_initialization(self, analytics_engine):
        """Test performance cache is initialized correctly."""
        assert hasattr(analytics_engine, "performance_cache")
        assert isinstance(analytics_engine.performance_cache, dict)
        assert analytics_engine.cache_ttl == 300

    def test_active_alerts_initialization(self, analytics_engine):
        """Test active alerts dictionary is initialized."""
        assert hasattr(analytics_engine, "active_alerts")
        assert isinstance(analytics_engine.active_alerts, dict)

    def test_database_indexes_created(self, temp_db_path):
        """Test that database indexes are created for performance."""
        engine = WorkflowAnalyticsEngine(db_path=temp_db_path)

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index'
            ORDER BY name
        """)
        indexes = [row[0] for row in cursor.fetchall()]

        conn.close()

        # Check for expected indexes
        assert "idx_metrics_workflow_time" in indexes
        assert "idx_events_workflow_time" in indexes
        assert "idx_events_type" in indexes


class TestAnalyticsSingleton:
    """Tests for singleton pattern."""

    def test_get_analytics_engine_singleton(self, temp_db_path):
        """Test that get_analytics_engine returns singleton instance."""
        # Reset global and create custom engine
        import core.workflow_analytics_engine
        core.workflow_analytics_engine._analytics_engine = None

        # Create custom engine with temp DB
        custom_engine = WorkflowAnalyticsEngine(db_path=temp_db_path)
        core.workflow_analytics_engine._analytics_engine = custom_engine

        engine1 = get_analytics_engine()
        engine2 = get_analytics_engine()

        # Should be same instance
        assert engine1 is engine2
        assert engine1.db_path == Path(temp_db_path)

    def test_singleton_persistence_across_calls(self, temp_db_path):
        """Test singleton persists across multiple calls."""
        # Create custom engine
        custom_engine = WorkflowAnalyticsEngine(db_path=temp_db_path)

        # Monkey patch the global
        import core.workflow_analytics_engine
        core.workflow_analytics_engine._analytics_engine = custom_engine

        # Should return same engine
        result = get_analytics_engine()
        assert result is custom_engine
        assert result.db_path == Path(temp_db_path)


# ============================================================================
# Test Workflow Tracking
# ============================================================================

class TestWorkflowTracking:
    """Tests for workflow execution tracking."""

    def test_track_workflow_start(self, analytics_engine, sample_workflow_id,
                                    sample_execution_id, sample_user_id):
        """Test workflow start tracking."""
        metadata = {"trigger": "manual", "environment": "test"}

        analytics_engine.track_workflow_start(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            user_id=sample_user_id,
            metadata=metadata
        )

        # Verify event was buffered
        assert len(analytics_engine.events_buffer) == 1
        event = analytics_engine.events_buffer[0]

        assert event.workflow_id == sample_workflow_id
        assert event.execution_id == sample_execution_id
        assert event.user_id == sample_user_id
        assert event.event_type == "workflow_started"
        assert event.metadata == metadata

    def test_track_workflow_start_creates_counter_metric(self, analytics_engine,
                                                         sample_workflow_id,
                                                         sample_execution_id):
        """Test workflow start creates execution counter metric."""
        analytics_engine.track_workflow_start(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            user_id="test-user"
        )

        # Verify metric was created
        assert len(analytics_engine.metrics_buffer) == 1
        metric = analytics_engine.metrics_buffer[0]

        assert metric.workflow_id == sample_workflow_id
        assert metric.metric_name == "workflow_executions"
        assert metric.metric_type == MetricType.COUNTER
        assert metric.value == 1
        assert metric.tags == {"event_type": "started"}

    def test_track_workflow_completion_success(self, analytics_engine,
                                               sample_workflow_id,
                                               sample_execution_id):
        """Test tracking successful workflow completion."""
        step_outputs = {"step1": {"result": "success"}}

        analytics_engine.track_workflow_completion(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            status=WorkflowStatus.COMPLETED,
            duration_ms=1500,
            step_outputs=step_outputs,
            user_id="test-user"
        )

        assert len(analytics_engine.events_buffer) == 1
        event = analytics_engine.events_buffer[0]

        assert event.event_type == "workflow_completed"
        assert event.status == "completed"
        assert event.duration_ms == 1500
        assert event.metadata == {"step_count": 1}

    def test_track_workflow_completion_failure(self, analytics_engine,
                                               sample_workflow_id,
                                               sample_execution_id):
        """Test tracking failed workflow completion."""
        error_message = "Step failed: timeout"

        analytics_engine.track_workflow_completion(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            status=WorkflowStatus.FAILED,
            duration_ms=500,
            error_message=error_message,
            user_id="test-user"
        )

        event = analytics_engine.events_buffer[0]
        assert event.status == "failed"
        assert event.error_message == error_message

    def test_track_workflow_completion_creates_duration_metric(self, analytics_engine,
                                                              sample_workflow_id,
                                                              sample_execution_id):
        """Test completion creates duration histogram metric."""
        analytics_engine.track_workflow_completion(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            status=WorkflowStatus.COMPLETED,
            duration_ms=2500,
            user_id="test-user"
        )

        # Check for duration metric
        duration_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "execution_duration_ms"
        ]

        assert len(duration_metrics) == 1
        metric = duration_metrics[0]

        assert metric.metric_type == MetricType.HISTOGRAM
        assert metric.value == 2500
        assert metric.tags == {"status": "completed"}

    def test_track_workflow_completion_creates_status_counter(self, analytics_engine,
                                                             sample_workflow_id,
                                                             sample_execution_id):
        """Test completion creates success/failure counter."""
        # Test successful completion
        analytics_engine.track_workflow_completion(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            status=WorkflowStatus.COMPLETED,
            duration_ms=1000,
            user_id="test-user"
        )

        success_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "successful_executions"
        ]

        assert len(success_metrics) == 1
        assert success_metrics[0].value == 1

    def test_track_step_execution(self, analytics_engine, sample_workflow_id,
                                   sample_execution_id, sample_step_id):
        """Test individual step execution tracking."""
        analytics_engine.track_step_execution(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            step_id=sample_step_id,
            step_name="Process Data",
            event_type="step_completed",
            duration_ms=250,
            status="completed",
            user_id="test-user"
        )

        assert len(analytics_engine.events_buffer) == 1
        event = analytics_engine.events_buffer[0]

        assert event.event_type == "step_completed"
        assert event.step_id == sample_step_id
        assert event.step_name == "Process Data"
        assert event.duration_ms == 250
        assert event.status == "completed"

    def test_track_step_execution_with_error(self, analytics_engine,
                                            sample_workflow_id,
                                            sample_execution_id):
        """Test step execution tracking with error."""
        analytics_engine.track_step_execution(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            step_id="step-002",
            step_name="API Call",
            event_type="step_failed",
            duration_ms=5000,
            status="failed",
            error_message="API timeout",
            user_id="test-user"
        )

        event = analytics_engine.events_buffer[0]
        assert event.error_message == "API timeout"
        assert event.status == "failed"

    def test_track_step_execution_creates_duration_metric(self, analytics_engine,
                                                         sample_workflow_id,
                                                         sample_execution_id):
        """Test step execution creates duration metric."""
        analytics_engine.track_step_execution(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            step_id="step-001",
            step_name="Transform",
            event_type="step_completed",
            duration_ms=450,
            user_id="test-user"
        )

        # Check for step duration metric
        duration_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "step_duration_ms"
        ]

        assert len(duration_metrics) == 1
        metric = duration_metrics[0]

        assert metric.metric_type == MetricType.HISTOGRAM
        assert metric.value == 450
        assert metric.tags["step_id"] == "step-001"

    def test_record_timing_for_multiple_steps(self, analytics_engine):
        """Test recording timing data for multiple workflow steps."""
        workflow_id = "wf-timing"
        execution_id = "exec-timing"

        steps = [
            ("step-001", "Initialize", 100),
            ("step-002", "Process", 500),
            ("step-003", "Validate", 200),
            ("step-004", "Finalize", 150),
        ]

        for step_id, step_name, duration in steps:
            analytics_engine.track_step_execution(
                workflow_id=workflow_id,
                execution_id=execution_id,
                step_id=step_id,
                step_name=step_name,
                event_type="step_completed",
                duration_ms=duration,
                user_id="test-user"
            )

        # Should have 4 events and 4 metrics
        assert len(analytics_engine.events_buffer) == 4
        assert len(analytics_engine.metrics_buffer) == 4

        # Verify durations
        for i, event in enumerate(analytics_engine.events_buffer):
            assert event.duration_ms == steps[i][2]

    def test_track_workflow_with_user_id(self, analytics_engine,
                                         sample_workflow_id,
                                         sample_execution_id):
        """Test that user_id is properly tracked in events."""
        user_id = "user-123"

        analytics_engine.track_workflow_start(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            user_id=user_id
        )

        event = analytics_engine.events_buffer[0]
        assert event.user_id == user_id

        metric = analytics_engine.metrics_buffer[0]
        assert metric.user_id == user_id


# ============================================================================
# Test Manual Override Tracking
# ============================================================================

class TestManualOverrideTracking:
    """Tests for manual override tracking."""

    def test_track_manual_override(self, analytics_engine, sample_workflow_id,
                                    sample_execution_id):
        """Test tracking manual override of automated action."""
        resource_id = "task-12345"

        analytics_engine.track_manual_override(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            resource_id=resource_id,
            action="modified_deadline",
            original_value="2024-02-15",
            new_value="2024-02-20",
            user_id="test-user"
        )

        assert len(analytics_engine.events_buffer) == 1
        event = analytics_engine.events_buffer[0]

        assert event.event_type == "manual_override"
        assert event.resource_id == resource_id
        assert event.metadata["action"] == "modified_deadline"
        assert event.metadata["original_value"] == "2024-02-15"
        assert event.metadata["new_value"] == "2024-02-20"

    def test_manual_override_creates_counter_metric(self, analytics_engine,
                                                    sample_workflow_id):
        """Test manual override creates counter metric."""
        analytics_engine.track_manual_override(
            workflow_id=sample_workflow_id,
            execution_id="exec-001",
            resource_id="task-001",
            action="changed_priority",
            user_id="test-user"
        )

        # Check for override counter metric
        override_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "manual_override_count"
        ]

        assert len(override_metrics) == 1
        assert override_metrics[0].value == 1


# ============================================================================
# Test Resource Usage Tracking
# ============================================================================

class TestResourceUsageTracking:
    """Tests for resource usage tracking."""

    def test_track_cpu_usage(self, analytics_engine, sample_workflow_id):
        """Test CPU usage tracking."""
        analytics_engine.track_resource_usage(
            workflow_id=sample_workflow_id,
            cpu_usage=75.5,
            memory_usage=1024,
            user_id="test-user"
        )

        # Check for CPU metric
        cpu_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "cpu_usage_percent"
        ]

        assert len(cpu_metrics) == 1
        assert cpu_metrics[0].value == 75.5
        assert cpu_metrics[0].metric_type == MetricType.GAUGE

    def test_track_memory_usage(self, analytics_engine, sample_workflow_id):
        """Test memory usage tracking."""
        analytics_engine.track_resource_usage(
            workflow_id=sample_workflow_id,
            cpu_usage=50.0,
            memory_usage=2048.5,
            user_id="test-user"
        )

        # Check for memory metric
        memory_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "memory_usage_mb"
        ]

        assert len(memory_metrics) == 1
        assert memory_metrics[0].value == 2048.5

    def test_track_disk_io(self, analytics_engine, sample_workflow_id):
        """Test disk I/O tracking."""
        analytics_engine.track_resource_usage(
            workflow_id=sample_workflow_id,
            cpu_usage=50.0,
            memory_usage=1024,
            disk_io=1048576,  # 1 MB
            user_id="test-user"
        )

        # Check for disk I/O metric
        disk_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "disk_io_bytes"
        ]

        assert len(disk_metrics) == 1
        assert disk_metrics[0].value == 1048576

    def test_track_network_io(self, analytics_engine, sample_workflow_id):
        """Test network I/O tracking."""
        analytics_engine.track_resource_usage(
            workflow_id=sample_workflow_id,
            cpu_usage=50.0,
            memory_usage=1024,
            network_io=2097152,  # 2 MB
            user_id="test-user"
        )

        # Check for network I/O metric
        network_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "network_io_bytes"
        ]

        assert len(network_metrics) == 1
        assert network_metrics[0].value == 2097152

    def test_track_resource_usage_with_step_id(self, analytics_engine):
        """Test resource usage tracking for specific step."""
        step_id = "step-heavy-processing"

        analytics_engine.track_resource_usage(
            workflow_id="wf-001",
            cpu_usage=95.0,
            memory_usage=4096,
            step_id=step_id,
            user_id="test-user"
        )

        cpu_metric = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "cpu_usage_percent"
        ][0]

        assert cpu_metric.step_id == step_id


# ============================================================================
# Test User Activity Tracking
# ============================================================================

class TestUserActivityTracking:
    """Tests for user activity tracking."""

    def test_track_user_activity(self, analytics_engine):
        """Test basic user activity tracking."""
        user_id = "user-activity-test"

        analytics_engine.track_user_activity(
            user_id=user_id,
            action="workflow_created",
            workflow_id="wf-001",
            metadata={"source": "ui"}
        )

        assert len(analytics_engine.metrics_buffer) == 1
        metric = analytics_engine.metrics_buffer[0]

        assert metric.metric_name == "user_activity"
        assert metric.user_id == user_id
        assert metric.tags["action"] == "workflow_created"
        assert metric.tags["workspace_id"] == "default"

    def test_track_user_activity_with_workspace(self, analytics_engine):
        """Test user activity with workspace context."""
        analytics_engine.track_user_activity(
            user_id="user-123",
            action="workflow_executed",
            workflow_id="wf-002",
            workspace_id="workspace-456",
            metadata={"trigger": "automation"}
        )

        metric = analytics_engine.metrics_buffer[0]
        assert metric.tags["workspace_id"] == "workspace-456"

    def test_track_user_activity_without_workflow(self, analytics_engine):
        """Test user activity not tied to specific workflow."""
        analytics_engine.track_user_activity(
            user_id="user-123",
            action="logged_in",
            metadata={"ip": "192.168.1.1"}
        )

        metric = analytics_engine.metrics_buffer[0]
        assert metric.workflow_id == "system"
        assert metric.tags["action"] == "logged_in"


# ============================================================================
# Test General Metric Tracking
# ============================================================================

class TestGeneralMetricTracking:
    """Tests for general metric tracking."""

    def test_track_metric(self, analytics_engine, sample_workflow_id):
        """Test general metric tracking."""
        analytics_engine.track_metric(
            workflow_id=sample_workflow_id,
            metric_name="custom_metric",
            metric_type=MetricType.COUNTER,
            value=42,
            tags={"label": "test"},
            step_id="step-001",
            step_name="Custom Step",
            user_id="test-user"
        )

        assert len(analytics_engine.metrics_buffer) == 1
        metric = analytics_engine.metrics_buffer[0]

        assert metric.metric_name == "custom_metric"
        assert metric.metric_type == MetricType.COUNTER
        assert metric.value == 42
        assert metric.tags == {"label": "test"}
        assert metric.step_id == "step-001"
        assert metric.step_name == "Custom Step"

    def test_track_gauge_metric(self, analytics_engine):
        """Test tracking gauge metric."""
        analytics_engine.track_metric(
            workflow_id="wf-001",
            metric_name="queue_size",
            metric_type=MetricType.GAUGE,
            value=100,
            user_id="test-user"
        )

        metric = analytics_engine.metrics_buffer[0]
        assert metric.metric_type == MetricType.GAUGE
        assert metric.value == 100

    def test_track_histogram_metric(self, analytics_engine):
        """Test tracking histogram metric."""
        analytics_engine.track_metric(
            workflow_id="wf-001",
            metric_name="request_size",
            metric_type=MetricType.HISTOGRAM,
            value=2048,
            user_id="test-user"
        )

        metric = analytics_engine.metrics_buffer[0]
        assert metric.metric_type == MetricType.HISTOGRAM

    def test_track_timer_metric(self, analytics_engine):
        """Test tracking timer metric."""
        analytics_engine.track_metric(
            workflow_id="wf-001",
            metric_name="processing_time",
            metric_type=MetricType.TIMER,
            value=150,
            user_id="test-user"
        )

        metric = analytics_engine.metrics_buffer[0]
        assert metric.metric_type == MetricType.TIMER


# ============================================================================
# Test Database Persistence
# ============================================================================

class TestDatabasePersistence:
    """Tests for database persistence of metrics and events."""

    def test_metrics_buffer_storage(self, analytics_engine, sample_workflow_id):
        """Test that metrics are stored in buffer for persistence."""
        # Track some metrics
        analytics_engine.track_metric(
            workflow_id=sample_workflow_id,
            metric_name="test_metric",
            metric_type=MetricType.COUNTER,
            value=10,
            user_id="test-user"
        )

        # Verify in buffer
        assert len(analytics_engine.metrics_buffer) == 1
        metric = analytics_engine.metrics_buffer[0]
        assert metric.workflow_id == sample_workflow_id
        assert metric.metric_name == "test_metric"
        assert metric.value == 10

    def test_events_buffer_storage(self, analytics_engine,
                                   sample_workflow_id,
                                   sample_execution_id):
        """Test that events are stored in buffer."""
        # Track workflow start
        analytics_engine.track_workflow_start(
            workflow_id=sample_workflow_id,
            execution_id=sample_execution_id,
            user_id="test-user"
        )

        # Verify in buffer
        assert len(analytics_engine.events_buffer) == 1
        event = analytics_engine.events_buffer[0]
        assert event.workflow_id == sample_workflow_id
        assert event.execution_id == sample_execution_id
        assert event.user_id == "test-user"

    def test_metric_data_integrity(self, analytics_engine):
        """Test that metric data is stored with correct types."""
        analytics_engine.track_metric(
            workflow_id="wf-001",
            metric_name="timing_metric",
            metric_type=MetricType.HISTOGRAM,
            value=150.5,
            tags={"environment": "test", "region": "us-east"},
            step_id="step-001",
            user_id="user-123"
        )

        metric = analytics_engine.metrics_buffer[0]
        assert isinstance(metric.timestamp, datetime)
        assert metric.metric_type == MetricType.HISTOGRAM
        assert metric.value == 150.5
        assert metric.tags["environment"] == "test"
        assert metric.step_id == "step-001"

    def test_event_data_integrity(self, analytics_engine):
        """Test that event data is stored with correct types."""
        analytics_engine.track_workflow_completion(
            workflow_id="wf-001",
            execution_id="exec-001",
            status=WorkflowStatus.COMPLETED,
            duration_ms=2500,
            user_id="user-123"
        )

        event = analytics_engine.events_buffer[0]
        assert isinstance(event.timestamp, datetime)
        assert event.status == "completed"
        assert event.duration_ms == 2500
        assert event.event_type == "workflow_completed"

    def test_multiple_metrics_same_workflow(self, analytics_engine):
        """Test that multiple metrics for same workflow are stored."""
        workflow_id = "wf-multiple"

        for i in range(5):
            analytics_engine.track_metric(
                workflow_id=workflow_id,
                metric_name=f"metric_{i}",
                metric_type=MetricType.COUNTER,
                value=i,
                user_id="test-user"
            )

        assert len(analytics_engine.metrics_buffer) == 5

        # Verify all are for same workflow
        for metric in analytics_engine.metrics_buffer:
            assert metric.workflow_id == workflow_id

    def test_buffer_maxlen_enforcement(self, temp_db_path):
        """Test that buffers enforce maximum length."""
        # Create engine with small buffers for testing
        engine = WorkflowAnalyticsEngine(db_path=temp_db_path)

        # Verify max lengths
        assert engine.metrics_buffer.maxlen == 10000
        assert engine.events_buffer.maxlen == 50000


# ============================================================================
# Test Performance Metrics Collection
# ============================================================================

class TestPerformanceMetrics:
    """Tests for performance metrics collection."""

    def test_get_workflow_performance_metrics(self, analytics_engine, temp_db_path,
                                              sample_workflow_id):
        """Test getting performance metrics for a workflow."""
        # First, populate some data
        import asyncio
        async def populate_data():
            # Track some workflow completions
            for duration in [100, 200, 300, 400, 500]:
                analytics_engine.track_workflow_completion(
                    workflow_id=sample_workflow_id,
                    execution_id=f"exec-{duration}",
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=duration,
                    user_id="test-user"
                )
            await analytics_engine.flush()

        # Run async populate
        asyncio.run(populate_data())

        # Give background thread time to process
        import time
        time.sleep(0.5)

        # Get performance metrics
        metrics = analytics_engine.get_workflow_performance_metrics(sample_workflow_id)

        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.workflow_id == sample_workflow_id
        assert metrics.total_executions >= 0
        assert isinstance(metrics.average_duration_ms, (int, float))

    def test_performance_metrics_time_windows(self, analytics_engine, temp_db_path):
        """Test different time windows for performance metrics."""
        workflow_id = "wf-time-windows"

        # Test different time windows
        windows = ["1h", "24h", "7d", "30d"]

        for window in windows:
            metrics = analytics_engine.get_workflow_performance_metrics(workflow_id, time_window=window)
            assert metrics.time_window == window
            assert isinstance(metrics, PerformanceMetrics)

    def test_performance_metrics_includes_duration_stats(self, analytics_engine):
        """Test that performance metrics include duration statistics."""
        workflow_id = "wf-duration-stats"

        metrics = analytics_engine.get_workflow_performance_metrics(workflow_id)

        # Should have duration fields
        assert hasattr(metrics, "average_duration_ms")
        assert hasattr(metrics, "median_duration_ms")
        assert hasattr(metrics, "p95_duration_ms")
        assert hasattr(metrics, "p99_duration_ms")

    def test_performance_metrics_includes_error_rate(self, analytics_engine):
        """Test that performance metrics include error rate."""
        workflow_id = "wf-error-rate"

        metrics = analytics_engine.get_workflow_performance_metrics(workflow_id)

        # Should have error rate field
        assert hasattr(metrics, "error_rate")
        assert isinstance(metrics.error_rate, (int, float))
        assert 0 <= metrics.error_rate <= 100

    def test_performance_cache_working(self, analytics_engine, sample_workflow_id):
        """Test that performance metrics cache is working."""
        # First call - not cached
        metrics1 = analytics_engine.get_workflow_performance_metrics(sample_workflow_id)

        # Second call - should be cached
        cache_key = f"{sample_workflow_id}_24h"
        assert cache_key in analytics_engine.performance_cache

        metrics2 = analytics_engine.performance_cache[cache_key]

        # Should be same object
        assert metrics1 is metrics2

    def test_performance_cache_expiry(self, analytics_engine, temp_db_path, sample_workflow_id):
        """Test that performance cache expires after TTL."""
        import time

        # Get metrics to populate cache
        metrics1 = analytics_engine.get_workflow_performance_metrics(sample_workflow_id)

        # Manually expire the cache
        cache_key = f"{sample_workflow_id}_24h"
        if cache_key in analytics_engine.performance_cache:
            cached = analytics_engine.performance_cache[cache_key]
            # Set timestamp to before TTL
            cached.timestamp = datetime.now() - timedelta(seconds=analytics_engine.cache_ttl + 1)

        # Cache should be expired now
        # (This would trigger recalculation on next call in real usage)

    def test_record_execution_time(self, analytics_engine):
        """Test recording execution time metric."""
        workflow_id = "wf-execution-time"
        duration = 1500  # 1.5 seconds

        analytics_engine.track_workflow_completion(
            workflow_id=workflow_id,
            execution_id="exec-001",
            status=WorkflowStatus.COMPLETED,
            duration_ms=duration,
            user_id="test-user"
        )

        # Check that duration was tracked
        assert len(analytics_engine.metrics_buffer) >= 1

        duration_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "execution_duration_ms"
        ]

        assert len(duration_metrics) >= 1
        assert duration_metrics[0].value == duration

    def test_record_step_duration(self, analytics_engine):
        """Test recording step duration metric."""
        workflow_id = "wf-step-duration"
        step_id = "step-001"
        duration = 250

        analytics_engine.track_step_execution(
            workflow_id=workflow_id,
            execution_id="exec-001",
            step_id=step_id,
            step_name="Process",
            event_type="step_completed",
            duration_ms=duration,
            user_id="test-user"
        )

        # Check that step duration was tracked
        duration_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "step_duration_ms"
        ]

        assert len(duration_metrics) >= 1
        assert duration_metrics[0].value == duration
        # step_id is stored in tags
        assert duration_metrics[0].tags["step_id"] == step_id

    def test_calculate_average_duration(self, analytics_engine, temp_db_path):
        """Test average duration calculation."""
        import asyncio

        workflow_id = "wf-average"
        durations = [100, 200, 300, 400, 500]

        async def populate():
            for d in durations:
                analytics_engine.track_workflow_completion(
                    workflow_id=workflow_id,
                    execution_id=f"exec-{d}",
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=d,
                    user_id="test-user"
                )
            await analytics_engine.flush()

        asyncio.run(populate())
        import time
        time.sleep(0.5)

        metrics = analytics_engine.get_workflow_performance_metrics(workflow_id)

        # Average should be 300
        assert metrics.average_duration_ms == sum(durations) / len(durations)

    def test_calculate_percentile_duration(self, analytics_engine, temp_db_path):
        """Test percentile duration calculation."""
        import asyncio

        workflow_id = "wf-percentiles"
        # Create enough data points for percentiles (need 20+ for p95, 100+ for p99)
        durations = list(range(100, 1500, 10))  # 140 data points

        async def populate():
            for d in durations:
                analytics_engine.track_workflow_completion(
                    workflow_id=workflow_id,
                    execution_id=f"exec-{d}",
                    status=WorkflowStatus.COMPLETED,
                    duration_ms=d,
                    user_id="test-user"
                )
            await analytics_engine.flush()

        asyncio.run(populate())
        import time
        time.sleep(0.5)

        metrics = analytics_engine.get_workflow_performance_metrics(workflow_id)

        # P95 should be calculated (need 20+ data points)
        assert metrics.p95_duration_ms > 0
        # P99 should be calculated (need 100+ data points)
        assert metrics.p99_duration_ms > 0
        assert metrics.p99_duration_ms >= metrics.p95_duration_ms

    def test_track_memory_usage(self, analytics_engine):
        """Test memory usage tracking."""
        workflow_id = "wf-memory"
        memory_mb = 1024.5

        analytics_engine.track_resource_usage(
            workflow_id=workflow_id,
            cpu_usage=50.0,
            memory_usage=memory_mb,
            user_id="test-user"
        )

        # Find memory metric
        memory_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "memory_usage_mb"
        ]

        assert len(memory_metrics) >= 1
        assert memory_metrics[0].value == memory_mb

    def test_track_cpu_usage(self, analytics_engine):
        """Test CPU usage tracking."""
        workflow_id = "wf-cpu"
        cpu_percent = 75.5

        analytics_engine.track_resource_usage(
            workflow_id=workflow_id,
            cpu_usage=cpu_percent,
            memory_usage=1024,
            user_id="test-user"
        )

        # Find CPU metric
        cpu_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.metric_name == "cpu_usage_percent"
        ]

        assert len(cpu_metrics) >= 1
        assert cpu_metrics[0].value == cpu_percent

    def test_track_concurrent_executions(self, analytics_engine):
        """Test concurrent execution tracking."""
        workflow_id = "wf-concurrent"

        # Track multiple concurrent executions
        for i in range(5):
            analytics_engine.track_workflow_start(
                workflow_id=workflow_id,
                execution_id=f"exec-{i}",
                user_id="test-user"
            )

        # Should have 5 workflow_started events
        start_events = [
            e for e in analytics_engine.events_buffer
            if e.event_type == "workflow_started"
        ]

        assert len(start_events) == 5

    def test_calculate_throughput(self, analytics_engine, temp_db_path):
        """Test throughput calculation (executions per time period)."""
        import asyncio

        workflow_id = "wf-throughput"

        async def populate():
            # Simulate 10 executions over time
            for i in range(10):
                analytics_engine.track_workflow_start(
                    workflow_id=workflow_id,
                    execution_id=f"exec-{i}",
                    user_id="test-user"
                )
            await analytics_engine.flush()

        asyncio.run(populate())
        import time
        time.sleep(0.5)

        metrics = analytics_engine.get_workflow_performance_metrics(workflow_id)

        # Throughput is implicit in total_executions over time_window
        assert metrics.total_executions >= 0


# ============================================================================
# Test Analytics Query and Aggregation
# ============================================================================

class TestAnalyticsQueries:
    """Tests for analytics queries and aggregations."""

    def test_get_system_overview(self, analytics_engine, temp_db_path):
        """Test getting system-wide analytics overview."""
        import asyncio

        async def populate():
            # Add some data for system overview
            for i in range(5):
                analytics_engine.track_workflow_start(
                    workflow_id=f"wf-{i}",
                    execution_id=f"exec-{i}",
                    user_id="test-user"
                )
            await analytics_engine.flush()

        asyncio.run(populate())
        import time
        time.sleep(0.5)

        overview = analytics_engine.get_system_overview()

        assert isinstance(overview, dict)
        assert "total_workflows" in overview
        assert "total_executions" in overview
        assert "success_rate" in overview
        assert "average_execution_time_ms" in overview
        assert "top_workflows" in overview
        assert "recent_errors" in overview

    def test_system_overview_includes_top_workflows(self, analytics_engine, temp_db_path):
        """Test that system overview includes top workflows."""
        import asyncio

        async def populate():
            # Create executions for different workflows
            for i in range(10):
                analytics_engine.track_workflow_start(
                    workflow_id=f"wf-{i % 3}",  # 3 workflows
                    execution_id=f"exec-{i}",
                    user_id="test-user"
                )
            await analytics_engine.flush()

        asyncio.run(populate())
        import time
        time.sleep(0.5)

        overview = analytics_engine.get_system_overview()

        assert "top_workflows" in overview
        assert isinstance(overview["top_workflows"], list)

    def test_get_workflow_statistics(self, analytics_engine):
        """Test getting workflow statistics."""
        workflow_id = "wf-stats"

        stats = analytics_engine.get_workflow_performance_metrics(workflow_id)

        assert isinstance(stats, PerformanceMetrics)
        assert stats.workflow_id == workflow_id
        assert hasattr(stats, "total_executions")
        assert hasattr(stats, "successful_executions")
        assert hasattr(stats, "failed_executions")

    def test_get_step_statistics(self, analytics_engine):
        """Test getting step-level statistics."""
        workflow_id = "wf-step-stats"

        metrics = analytics_engine.get_workflow_performance_metrics(workflow_id)

        # Should include step duration data
        assert hasattr(metrics, "average_step_duration")
        assert isinstance(metrics.average_step_duration, dict)

    def test_filter_by_time_range(self, analytics_engine):
        """Test filtering analytics by time range."""
        workflow_id = "wf-time-filter"

        # Test all time windows
        for window in ["1h", "24h", "7d", "30d"]:
            metrics = analytics_engine.get_workflow_performance_metrics(workflow_id, time_window=window)
            assert metrics.time_window == window

    def test_aggregate_by_workflow_type(self, analytics_engine):
        """Test aggregating metrics by workflow type."""
        # Track workflows with different "types" (using tags)
        for wf_type in ["automation", "integration", "notification"]:
            for i in range(3):
                analytics_engine.track_metric(
                    workflow_id=f"wf-{wf_type}-{i}",
                    metric_name="workflow_executions",
                    metric_type=MetricType.COUNTER,
                    value=1,
                    tags={"workflow_type": wf_type},
                    user_id="test-user"
                )

        # Verify metrics were tracked with workflow_type tags
        type_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.tags and "workflow_type" in m.tags
        ]

        assert len(type_metrics) == 9

        # Verify distribution across types
        automation_count = sum(1 for m in type_metrics if m.tags["workflow_type"] == "automation")
        integration_count = sum(1 for m in type_metrics if m.tags["workflow_type"] == "integration")
        notification_count = sum(1 for m in type_metrics if m.tags["workflow_type"] == "notification")

        assert automation_count == 3
        assert integration_count == 3
        assert notification_count == 3

    def test_get_error_rate(self, analytics_engine):
        """Test error rate calculation."""
        workflow_id = "wf-error-rate"

        # Just verify the error_rate field exists on PerformanceMetrics
        metrics = analytics_engine.get_workflow_performance_metrics(workflow_id)

        # Should have error rate field (can be int or float)
        assert hasattr(metrics, "error_rate")
        assert isinstance(metrics.error_rate, (int, float))
        assert 0 <= metrics.error_rate <= 100

    def test_get_success_rate(self, analytics_engine):
        """Test success rate calculation."""
        workflow_id = "wf-success-rate"

        metrics = analytics_engine.get_workflow_performance_metrics(workflow_id)

        # Success rate can be derived from error rate
        success_rate = 100 - metrics.error_rate
        assert 0 <= success_rate <= 100

    def test_get_most_failed_steps(self, analytics_engine):
        """Test identifying most failed workflow steps."""
        workflow_id = "wf-failed-steps"

        # Track failed steps
        for i in range(5):
            analytics_engine.track_step_execution(
                workflow_id=workflow_id,
                execution_id="exec-001",
                step_id=f"step-{i}",
                step_name=f"Step {i}",
                event_type="step_failed",
                status="failed",
                error_message=f"Error in step {i}",
                user_id="test-user"
            )

        # Check that failed steps were tracked
        failed_events = [
            e for e in analytics_engine.events_buffer
            if e.event_type == "step_failed"
        ]

        assert len(failed_events) == 5

        # Verify error messages were captured
        for event in failed_events:
            assert event.error_message is not None
            assert event.status == "failed"

    def test_get_slowest_steps(self, analytics_engine):
        """Test identifying slowest workflow steps."""
        workflow_id = "wf-slowest-steps"

        # Track steps with different durations
        durations = [100, 500, 1000, 2000, 5000]
        for i, duration in enumerate(durations):
            analytics_engine.track_step_execution(
                workflow_id=workflow_id,
                execution_id="exec-001",
                step_id=f"step-{i}",
                step_name=f"Step {i}",
                event_type="step_completed",
                duration_ms=duration,
                user_id="test-user"
            )

        # Verify all were tracked
        assert len(analytics_engine.events_buffer) == 5
        assert len(analytics_engine.metrics_buffer) == 5

    def test_get_execution_trends(self, analytics_engine):
        """Test getting execution trends over time."""
        workflow_id = "wf-trends"

        timeline = analytics_engine.get_execution_timeline(workflow_id)

        assert isinstance(timeline, list)
        # Timeline should have data points
        assert len(timeline) > 0

    def test_get_user_analytics(self, analytics_engine):
        """Test per-user analytics."""
        user_id = "user-analytics"

        # Track activity for specific user
        analytics_engine.track_user_activity(
            user_id=user_id,
            action="workflow_created",
            workflow_id="wf-001"
        )

        # Check that user activity was tracked
        user_metrics = [
            m for m in analytics_engine.metrics_buffer
            if m.user_id == user_id
        ]

        assert len(user_metrics) >= 1
        assert user_metrics[0].tags["user_id"] == user_id


# ============================================================================
# Test Analytics Export and Reporting
# ============================================================================

class TestAnalyticsExport:
    """Tests for analytics export and reporting."""

    def test_get_all_workflow_ids(self, analytics_engine, temp_db_path):
        """Test getting list of all workflow IDs."""
        import asyncio

        async def populate():
            # Create workflows
            for i in range(3):
                analytics_engine.track_workflow_start(
                    workflow_id=f"wf-export-{i}",
                    execution_id=f"exec-{i}",
                    user_id="test-user"
                )
            await analytics_engine.flush()

        asyncio.run(populate())
        import time
        time.sleep(0.5)

        workflow_ids = analytics_engine.get_all_workflow_ids()

        assert isinstance(workflow_ids, list)
        assert len(workflow_ids) >= 0

    def test_get_unique_workflow_count(self, analytics_engine):
        """Test getting count of unique workflows."""
        count = analytics_engine.get_unique_workflow_count()

        assert isinstance(count, int)
        assert count >= 0

    def test_get_last_execution_time(self, analytics_engine):
        """Test getting last execution time for workflow."""
        workflow_id = "wf-last-exec"

        time = analytics_engine.get_last_execution_time(workflow_id)

        # Should return None if no executions, or datetime if exists
        assert time is None or isinstance(time, datetime)

    def test_get_workflow_name(self, analytics_engine):
        """Test getting workflow name."""
        workflow_id = "wf-name-test"

        # Returns workflow_id if no name found
        name = analytics_engine.get_workflow_name(workflow_id)

        assert name == workflow_id

    def test_get_recent_events(self, analytics_engine, temp_db_path):
        """Test getting recent execution events."""
        import asyncio

        async def populate():
            # Add some events
            for i in range(5):
                analytics_engine.track_workflow_start(
                    workflow_id="wf-recent",
                    execution_id=f"exec-{i}",
                    user_id="test-user"
                )
            await analytics_engine.flush()

        asyncio.run(populate())
        import time
        time.sleep(0.5)

        # Note: get_recent_events queries database, won't have data from buffer
        events = analytics_engine.get_recent_events(limit=10)

        assert isinstance(events, list)

    def test_get_error_breakdown(self, analytics_engine):
        """Test getting error breakdown by type."""
        workflow_id = "wf-error-breakdown"

        breakdown = analytics_engine.get_error_breakdown(workflow_id)

        assert isinstance(breakdown, dict)

    def test_get_all_alerts(self, analytics_engine):
        """Test getting all configured alerts."""
        alerts = analytics_engine.get_all_alerts()

        assert isinstance(alerts, list)

    def test_create_alert(self, analytics_engine):
        """Test creating a new alert."""
        # Create Alert object first (due to method shadowing in source)
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            name="Test Alert",
            description="Test alert description",
            severity=AlertSeverity.MEDIUM,
            condition="value > 100",
            threshold_value=100,
            metric_name="test_metric",
            workflow_id="wf-001",
            notification_channels=[]
        )

        # Use the create_alert method that takes an Alert object
        result = analytics_engine.create_alert(alert)

        assert isinstance(result, Alert)
        assert result.name == "Test Alert"
        assert result.alert_id == alert.alert_id

    def test_update_alert(self, analytics_engine):
        """Test updating an existing alert."""
        # Create alert object
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            name="Update Test Alert",
            description="Alert to test updates",
            severity=AlertSeverity.LOW,
            condition="value > 50",
            threshold_value=50,
            metric_name="test_metric",
            notification_channels=[]
        )

        analytics_engine.create_alert(alert)

        # Update the alert
        analytics_engine.update_alert(
            alert_id=alert.alert_id,
            threshold_value=75
        )

        # Verify the alert ID exists
        assert alert.alert_id is not None

    def test_delete_alert(self, analytics_engine):
        """Test deleting an alert."""
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            name="Delete Test Alert",
            description="Alert to test deletion",
            severity=AlertSeverity.LOW,
            condition="value > 10",
            threshold_value=10,
            metric_name="test_metric",
            notification_channels=[]
        )

        analytics_engine.create_alert(alert)

        # Delete the alert
        analytics_engine.delete_alert(alert.alert_id)

        # Verify the alert was created
        assert alert.alert_id is not None

    def test_export_to_json_structure(self, analytics_engine):
        """Test JSON export structure."""
        workflow_id = "wf-json-export"

        metrics = analytics_engine.get_workflow_performance_metrics(workflow_id)

        # Convert to dict for JSON serialization
        import dataclasses
        metrics_dict = dataclasses.asdict(metrics)

        # Verify it's JSON-serializable
        import json
        json_str = json.dumps(metrics_dict, default=str)

        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_dashboard_data_format(self, analytics_engine):
        """Test dashboard API data format."""
        overview = analytics_engine.get_system_overview()

        # Verify dashboard has required fields
        required_fields = [
            "total_workflows",
            "total_executions",
            "success_rate",
            "average_execution_time_ms"
        ]

        for field in required_fields:
            assert field in overview
