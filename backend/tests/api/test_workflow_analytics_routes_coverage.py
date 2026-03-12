"""
Unit tests for Workflow Analytics API Routes

This test module provides comprehensive coverage for workflow analytics endpoints:
- GET /api/workflows/analytics - Get workflow execution analytics summary
- GET /api/workflows/analytics/recent - Get recent workflow executions
- GET /api/workflows/analytics/{workflow_id} - Get stats for specific workflow

Target Coverage: 75%+ line coverage for workflow_analytics_routes.py (30 lines, 3 endpoints)

Tests cover:
- Success paths with default and custom parameters
- Error paths (invalid parameters, service errors, not found)
- Response structure validation
- Edge cases (empty results, invalid input)
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from fastapi.testclient import TestClient
from typing import Dict, Any, List


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_workflow_metrics():
    """
    Mock workflow metrics service with all required methods.

    Provides mock implementations for:
    - get_summary: Returns execution analytics summary
    - get_recent_executions: Returns list of recent executions
    - get_workflow_stats: Returns stats for specific workflow
    """
    mock = MagicMock()

    # Mock get_summary method
    mock.get_summary = Mock(return_value={
        "total_executions": 100,
        "successful_executions": 95,
        "failed_executions": 5,
        "success_rate": 0.95,
        "average_execution_time": 2.5,
        "days": 7
    })

    # Mock get_recent_executions method
    mock.get_recent_executions = Mock(return_value=[
        {
            "workflow_id": "wf_123",
            "status": "completed",
            "started_at": "2026-03-12T10:00:00Z",
            "completed_at": "2026-03-12T10:02:30Z",
            "duration_seconds": 150
        },
        {
            "workflow_id": "wf_124",
            "status": "completed",
            "started_at": "2026-03-12T09:30:00Z",
            "completed_at": "2026-03-12T09:31:00Z",
            "duration_seconds": 60
        }
    ])

    # Mock get_workflow_stats method
    mock.get_workflow_stats = Mock(return_value={
        "workflow_id": "wf_123",
        "total_executions": 50,
        "successful_executions": 48,
        "failed_executions": 2,
        "success_rate": 0.96,
        "average_execution_time": 3.2,
        "last_execution": "2026-03-12T10:00:00Z"
    })

    return mock


@pytest.fixture
def workflow_analytics_client(mock_workflow_metrics):
    """
    TestClient for workflow analytics routes with mocked metrics service.

    Uses per-file FastAPI app pattern to avoid SQLAlchemy conflicts.
    Patches the metrics module at the route level.
    """
    from fastapi import FastAPI
    from api.workflow_analytics_routes import router

    app = FastAPI()
    app.include_router(router)

    # Patch the metrics module where it's imported (inside route functions)
    # The routes do: from core.workflow_metrics import metrics
    with patch('core.workflow_metrics.metrics', mock_workflow_metrics):
        yield TestClient(app)


@pytest.fixture
def sample_analytics_summary() -> Dict[str, Any]:
    """Expected analytics summary data structure."""
    return {
        "total_executions": 100,
        "successful_executions": 95,
        "failed_executions": 5,
        "success_rate": 0.95,
        "average_execution_time": 2.5,
        "days": 7
    }


@pytest.fixture
def sample_recent_executions() -> List[Dict[str, Any]]:
    """Expected recent executions list structure."""
    return [
        {
            "workflow_id": "wf_123",
            "status": "completed",
            "started_at": "2026-03-12T10:00:00Z",
            "completed_at": "2026-03-12T10:02:30Z",
            "duration_seconds": 150
        },
        {
            "workflow_id": "wf_124",
            "status": "completed",
            "started_at": "2026-03-12T09:30:00Z",
            "completed_at": "2026-03-12T09:31:00Z",
            "duration_seconds": 60
        }
    ]


@pytest.fixture
def sample_workflow_stats() -> Dict[str, Any]:
    """Expected workflow stats data structure."""
    return {
        "workflow_id": "wf_123",
        "total_executions": 50,
        "successful_executions": 48,
        "failed_executions": 2,
        "success_rate": 0.96,
        "average_execution_time": 3.2,
        "last_execution": "2026-03-12T10:00:00Z"
    }


@pytest.fixture
def sample_workflow_id() -> str:
    """Factory for valid workflow_id parameter."""
    return "wf_123"


# ============================================================================
# Test Classes
# ============================================================================

class TestWorkflowAnalyticsSummary:
    """Tests for GET /api/workflows/analytics endpoint."""

    def test_get_analytics_summary_default(self, workflow_analytics_client, mock_workflow_metrics):
        """Test getting analytics summary with default days=7 parameter."""
        response = workflow_analytics_client.get("/api/workflows/analytics")

        assert response.status_code == 200
        data = response.json()
        assert "total_executions" in data
        assert data["total_executions"] == 100
        assert data["success_rate"] == 0.95
        mock_workflow_metrics.get_summary.assert_called_once_with(days=7)

    def test_get_analytics_summary_custom_days(self, workflow_analytics_client, mock_workflow_metrics):
        """Test getting analytics summary with custom days parameter."""
        response = workflow_analytics_client.get("/api/workflows/analytics?days=30")

        assert response.status_code == 200
        data = response.json()
        assert "total_executions" in data
        mock_workflow_metrics.get_summary.assert_called_once_with(days=30)

    def test_get_analytics_summary_structure(self, workflow_analytics_client):
        """Test analytics summary response structure validation."""
        response = workflow_analytics_client.get("/api/workflows/analytics")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "total_executions" in data
        assert "success_rate" in data
        assert isinstance(data["total_executions"], int)
        assert isinstance(data["success_rate"], (int, float))
        assert 0 <= data["success_rate"] <= 1


class TestWorkflowRecentExecutions:
    """Tests for GET /api/workflows/analytics/recent endpoint."""

    def test_get_recent_executions_default(self, workflow_analytics_client, mock_workflow_metrics):
        """Test getting recent executions with default limit=20 parameter."""
        response = workflow_analytics_client.get("/api/workflows/analytics/recent")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        mock_workflow_metrics.get_recent_executions.assert_called_once_with(limit=20)

    def test_get_recent_executions_custom_limit(self, workflow_analytics_client, mock_workflow_metrics):
        """Test getting recent executions with custom limit parameter."""
        response = workflow_analytics_client.get("/api/workflows/analytics/recent?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        mock_workflow_metrics.get_recent_executions.assert_called_once_with(limit=5)

    def test_get_recent_executions_empty(self, workflow_analytics_client, mock_workflow_metrics):
        """Test getting recent executions when no executions exist."""
        mock_workflow_metrics.get_recent_executions.return_value = []

        response = workflow_analytics_client.get("/api/workflows/analytics/recent")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_recent_executions_structure(self, workflow_analytics_client):
        """Test recent executions response structure validation."""
        response = workflow_analytics_client.get("/api/workflows/analytics/recent")

        assert response.status_code == 200
        data = response.json()

        # Verify it's a list with execution objects
        assert isinstance(data, list)
        if len(data) > 0:
            execution = data[0]
            assert "workflow_id" in execution
            assert "status" in execution


class TestWorkflowStats:
    """Tests for GET /api/workflows/analytics/{workflow_id} endpoint."""

    def test_get_workflow_stats_success(self, workflow_analytics_client, mock_workflow_metrics, sample_workflow_id):
        """Test getting stats for a specific workflow successfully."""
        response = workflow_analytics_client.get(f"/api/workflows/analytics/{sample_workflow_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == sample_workflow_id
        assert data["total_executions"] == 50
        assert data["success_rate"] == 0.96
        mock_workflow_metrics.get_workflow_stats.assert_called_once_with(sample_workflow_id)

    def test_get_workflow_stats_not_found(self, workflow_analytics_client, mock_workflow_metrics):
        """Test getting stats for non-existent workflow."""
        mock_workflow_metrics.get_workflow_stats.return_value = {}

        response = workflow_analytics_client.get("/api/workflows/analytics/nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert data == {}

    def test_get_workflow_stats_structure(self, workflow_analytics_client, sample_workflow_id):
        """Test workflow stats response structure validation."""
        response = workflow_analytics_client.get(f"/api/workflows/analytics/{sample_workflow_id}")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "workflow_id" in data
        assert "total_executions" in data
        assert "success_rate" in data
        assert isinstance(data["total_executions"], int)
        assert isinstance(data["success_rate"], (int, float))


class TestWorkflowAnalyticsErrorPaths:
    """Tests for error paths and edge cases in analytics endpoints."""

    def test_analytics_invalid_days_negative(self, workflow_analytics_client, mock_workflow_metrics):
        """Test handling of invalid negative days parameter."""
        # Service should handle negative values gracefully
        mock_workflow_metrics.get_summary.return_value = {}

        response = workflow_analytics_client.get("/api/workflows/analytics?days=-7")

        # Route doesn't validate, so it passes through to service
        assert response.status_code == 200

    def test_analytics_invalid_limit_zero(self, workflow_analytics_client, mock_workflow_metrics):
        """Test handling of invalid zero limit parameter."""
        mock_workflow_metrics.get_recent_executions.return_value = []

        response = workflow_analytics_client.get("/api/workflows/analytics/recent?limit=0")

        # Route doesn't validate, so it passes through to service
        assert response.status_code == 200

    def test_analytics_large_days_value(self, workflow_analytics_client, mock_workflow_metrics):
        """Test handling of large days parameter."""
        mock_workflow_metrics.get_summary.return_value = {"total_executions": 0}

        response = workflow_analytics_client.get("/api/workflows/analytics?days=365")

        # Route accepts large values, service validates
        assert response.status_code == 200
        mock_workflow_metrics.get_summary.assert_called_once_with(days=365)

    def test_recent_executions_large_limit(self, workflow_analytics_client, mock_workflow_metrics):
        """Test handling of large limit parameter."""
        mock_workflow_metrics.get_recent_executions.return_value = []

        response = workflow_analytics_client.get("/api/workflows/analytics/recent?limit=1000")

        # Route accepts large values, service validates
        assert response.status_code == 200
        mock_workflow_metrics.get_recent_executions.assert_called_once_with(limit=1000)
