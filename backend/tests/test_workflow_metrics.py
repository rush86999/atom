"""
Tests for Workflow Analytics Metrics
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from core.database import get_db_session
from core.models import AgentExecution
from main_api_app import app


class TestWorkflowMetrics:
    """Test workflow metrics endpoint returns real data"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def db(self):
        """Create database session"""
        db = get_db_session()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture
    def sample_executions(self, db):
        """Create sample executions for testing"""
        workflow_id = "test-workflow-123"

        # Create successful executions
        for i in range(5):
            exec = AgentExecution(
                id=f"exec-success-{i}",
                agent_id="agent-1",
                session_id="session-1",
                task_description=f"Task {i}",
                status="completed",
                started_at=datetime.now() - timedelta(hours=2),
                completed_at=datetime.now() - timedelta(hours=2, minutes=-5),
                result_summary=f"Task {i} completed",
                metadata_json={"workflow_id": workflow_id}
            )
            db.add(exec)

        # Create failed execution
        exec_failed = AgentExecution(
            id="exec-failed-1",
            agent_id="agent-1",
            session_id="session-1",
            task_description="Failed task",
            status="failed",
            started_at=datetime.now() - timedelta(hours=1),
            completed_at=datetime.now() - timedelta(hours=1, minutes=-2),
            metadata_json={"workflow_id": workflow_id}
        )
        db.add(exec_failed)

        # Create cancelled execution
        exec_cancelled = AgentExecution(
            id="exec-cancelled-1",
            agent_id="agent-1",
            session_id="session-1",
            task_description="Cancelled task",
            status="cancelled",
            started_at=datetime.now() - timedelta(minutes=30),
            completed_at=datetime.now() - timedelta(minutes=29),
            metadata_json={"workflow_id": workflow_id}
        )
        db.add(exec_cancelled)

        db.commit()

        yield workflow_id

        # Cleanup
        db.query(AgentExecution).filter(
            AgentExecution.metadata_json["workflow_id"].astext == workflow_id
        ).delete()
        db.commit()

    def test_workflow_metrics_success_response(self, client, sample_executions):
        """Test endpoint returns success response"""
        workflow_id = sample_executions

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")

        assert response.status_code == 200
        data = response.json()

        assert "success" in data
        assert data["success"] is True
        assert "metrics" in data

    def test_workflow_metrics_contains_summary(self, client, sample_executions):
        """Test metrics contain summary information"""
        workflow_id = sample_executions

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")
        data = response.json()

        metrics = data["metrics"]

        # Verify summary section
        assert "summary" in metrics
        summary = metrics["summary"]

        assert "total_runs" in summary
        assert "successful_runs" in summary
        assert "failed_runs" in summary
        assert "cancelled_runs" in summary
        assert "success_rate" in summary

    def test_workflow_metrics_calculates_correct_counts(self, client, sample_executions):
        """Test metrics calculate correct execution counts"""
        workflow_id = sample_executions

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")
        data = response.json()

        summary = data["metrics"]["summary"]

        # We created 5 successful, 1 failed, 1 cancelled
        assert summary["total_runs"] == 7
        assert summary["successful_runs"] == 5
        assert summary["failed_runs"] == 1
        assert summary["cancelled_runs"] == 1

    def test_workflow_metrics_calculates_success_rate(self, client, sample_executions):
        """Test metrics calculate correct success rate"""
        workflow_id = sample_executions

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")
        data = response.json()

        summary = data["metrics"]["summary"]

        # Success rate = 5/7 ≈ 0.714
        expected_rate = 5 / 7
        assert abs(summary["success_rate"] - expected_rate) < 0.01

    def test_workflow_metrics_contains_performance(self, client, sample_executions):
        """Test metrics contain performance information"""
        workflow_id = sample_executions

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")
        data = response.json()

        metrics = data["metrics"]

        # Verify performance section
        assert "performance" in metrics
        performance = metrics["performance"]

        assert "avg_duration_seconds" in performance
        assert "min_duration_seconds" in performance
        assert "max_duration_seconds" in performance
        assert "total_duration_seconds" in performance

    def test_workflow_metrics_calculates_durations(self, client, sample_executions):
        """Test metrics calculate correct durations"""
        workflow_id = sample_executions

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")
        data = response.json()

        performance = data["metrics"]["performance"]

        # All successful executions should have durations (~5 minutes each)
        assert performance["avg_duration_seconds"] > 0
        assert performance["min_duration_seconds"] > 0
        assert performance["max_duration_seconds"] > 0
        assert performance["total_duration_seconds"] > 0

        # Max should be >= min
        assert performance["max_duration_seconds"] >= performance["min_duration_seconds"]

    def test_workflow_metrics_time_window_filter(self, client, sample_executions):
        """Test time window parameter filters correctly"""
        workflow_id = sample_executions

        # Query with 1h window (should exclude some older executions)
        response = client.get(
            f"/api/analytics/workflows/{workflow_id}/metrics?time_window=1h"
        )
        data = response.json()

        summary = data["metrics"]["summary"]

        # Should have fewer executions in 1h window
        assert summary["total_runs"] < 7

    def test_workflow_metrics_timestamps(self, client, sample_executions):
        """Test metrics include timestamp information"""
        workflow_id = sample_executions

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")
        data = response.json()

        metrics = data["metrics"]

        # Verify timestamps
        assert "timestamps" in metrics
        timestamps = metrics["timestamps"]

        assert "first_run" in timestamps
        assert "last_run" in timestamps

        # Should have actual timestamps
        assert timestamps["first_run"] is not None
        assert timestamps["last_run"] is not None

    def test_workflow_metrics_specific_metrics(self, client, sample_executions):
        """Test requesting specific metric names"""
        workflow_id = sample_executions

        response = client.get(
            f"/api/analytics/workflows/{workflow_id}/metrics?metric_names=total_runs&metric_names=success_rate"
        )
        data = response.json()

        metrics = data["metrics"]

        # Should include requested_metrics section
        assert "requested_metrics" in metrics

        requested = metrics["requested_metrics"]
        assert "total_runs" in requested
        assert "success_rate" in requested

    def test_workflow_metrics_nonexistent_workflow(self, client):
        """Test metrics for non-existent workflow"""
        workflow_id = "nonexistent-workflow"

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")

        # Should still return 200, but with zero metrics
        assert response.status_code == 200
        data = response.json()

        summary = data["metrics"]["summary"]
        assert summary["total_runs"] == 0
        assert summary["successful_runs"] == 0
        assert summary["success_rate"] == 0.0

    def test_workflow_metrics_different_time_windows(self, client, sample_executions):
        """Test different time window options"""
        workflow_id = sample_executions

        time_windows = ["1h", "24h", "7d", "30d"]

        for window in time_windows:
            response = client.get(
                f"/api/analytics/workflows/{workflow_id}/metrics?time_window={window}"
            )

            assert response.status_code == 200
            data = response.json()

            # Verify time_window is reflected in response
            assert data["metrics"]["time_window"] == window

    def test_workflow_metrics_performance_aggregation(self, client, sample_executions):
        """Test performance metrics are properly aggregated"""
        workflow_id = sample_executions

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")
        data = response.json()

        performance = data["metrics"]["performance"]

        # Verify aggregation makes sense
        # Average should be between min and max
        avg = performance["avg_duration_seconds"]
        min_dur = performance["min_duration_seconds"]
        max_dur = performance["max_duration_seconds"]

        assert min_dur <= avg <= max_dur


class TestWorkflowMetricsEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_empty_workflow_metrics(self, client):
        """Test metrics when workflow has no executions"""
        workflow_id = "empty-workflow"

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")

        assert response.status_code == 200
        data = response.json()

        summary = data["metrics"]["summary"]
        assert summary["total_runs"] == 0
        assert summary["success_rate"] == 0.0

        performance = data["metrics"]["performance"]
        assert performance["avg_duration_seconds"] == 0
        assert performance["min_duration_seconds"] == 0
        assert performance["max_duration_seconds"] == 0

    def test_invalid_time_window(self, client):
        """Test with invalid time window"""
        workflow_id = "test-workflow"

        response = client.get(
            f"/api/analytics/workflows/{workflow_id}/metrics?time_window=invalid"
        )

        # Should default to 24h or handle gracefully
        assert response.status_code == 200

    def test_workflow_id_with_special_characters(self, client):
        """Test workflow ID with special characters"""
        workflow_id = "workflow-with-special_chars.123"

        response = client.get(f"/api/analytics/workflows/{workflow_id}/metrics")

        # Should handle without error
        assert response.status_code in [200, 404]
