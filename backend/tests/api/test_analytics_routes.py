"""
Analytics and Workflow Routes Integration Tests

Tests for analytics dashboard and workflow control endpoints.

Coverage:
- GET /analytics/workflows - Get workflow analytics
- GET /analytics/steps - Get step analytics
- GET /analytics/errors - Get error reports
- GET /analytics/performance - Get performance metrics
- GET /analytics/export - Export analytics data
- GET /workflows/{execution_id}/status - Get workflow status
- POST /workflows/{execution_id}/pause - Pause workflow
- POST /workflows/{execution_id}/resume - Resume workflow
- POST /workflows/{execution_id}/cancel - Cancel workflow
- Authentication/authorization
- Analytics queries
- Workflow control
- Export formats
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.workflow_analytics_routes import router
from core.models import User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create TestClient for analytics routes."""
    return TestClient(router)


@pytest.fixture
def mock_user(db: Session):
    """Create test user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mock_execution_id():
    """Create mock workflow execution ID."""
    import uuid
    return str(uuid.uuid4())


# ============================================================================
# GET /analytics/workflows - Workflow Analytics Tests
# ============================================================================

def test_get_workflow_analytics_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting workflow analytics successfully."""
    with patch('api.workflow_analytics_routes.get_analytics_engine') as mock_analytics:
        mock_engine = MagicMock()
        mock_engine.get_workflow_statistics.return_value = {
            "total_workflows": 100,
            "successful": 85,
            "failed": 10,
            "running": 5
        }
        mock_analytics.return_value = mock_engine

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/analytics/workflows")

            assert response.status_code == 200
            data = response.json()
            assert "total_workflows" in data or "data" in data


def test_get_workflow_analytics_with_time_filter(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test workflow analytics with time range filter."""
    with patch('api.workflow_analytics_routes.get_analytics_engine') as mock_analytics:
        mock_engine = MagicMock()
        mock_engine.get_workflow_statistics.return_value = {
            "total_workflows": 50,
            "time_range": "7d"
        }
        mock_analytics.return_value = mock_engine

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/analytics/workflows?time_range=7d")

            assert response.status_code == 200


# ============================================================================
# GET /analytics/steps - Step Analytics Tests
# ============================================================================

def test_get_step_analytics_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting step analytics successfully."""
    with patch('api.workflow_analytics_routes.get_analytics_engine') as mock_analytics:
        mock_engine = MagicMock()
        mock_engine.get_step_statistics.return_value = {
            "total_steps": 500,
            "average_duration": 2.5,
            "success_rate": 0.95
        }
        mock_analytics.return_value = mock_engine

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/analytics/steps")

            assert response.status_code == 200
            data = response.json()
            assert "total_steps" in data or "data" in data


# ============================================================================
# GET /analytics/errors - Error Reports Tests
# ============================================================================

def test_get_error_report_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting error report successfully."""
    with patch('api.workflow_analytics_routes.get_analytics_engine') as mock_analytics:
        mock_engine = MagicMock()
        mock_engine.get_error_report.return_value = {
            "total_errors": 25,
            "errors_by_type": {
                "validation": 10,
                "timeout": 8,
                "system": 7
            }
        }
        mock_analytics.return_value = mock_engine

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/analytics/errors")

            assert response.status_code == 200
            data = response.json()
            assert "total_errors" in data or "data" in data


# ============================================================================
# GET /analytics/performance - Performance Metrics Tests
# ============================================================================

def test_get_performance_metrics_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting performance metrics successfully."""
    with patch('api.workflow_analytics_routes.get_analytics_engine') as mock_analytics:
        mock_engine = MagicMock()
        mock_engine.get_performance_metrics.return_value = {
            "avg_workflow_duration": 120.5,
            "p95_duration": 300.0,
            "p99_duration": 450.0,
            "throughput_per_hour": 50
        }
        mock_analytics.return_value = mock_engine

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/analytics/performance")

            assert response.status_code == 200
            data = response.json()
            assert "avg_workflow_duration" in data or "data" in data


# ============================================================================
# GET /analytics/export - Export Analytics Tests
# ============================================================================

def test_export_analytics_csv(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test exporting analytics as CSV."""
    with patch('api.workflow_analytics_routes.get_analytics_engine') as mock_analytics:
        mock_engine = MagicMock()
        mock_engine.export_analytics.return_value = {
            "format": "csv",
            "data": "workflow_id,status,duration\n1,success,120\n2,failed,60"
        }
        mock_analytics.return_value = mock_engine

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/analytics/export?format=csv")

            assert response.status_code == 200


def test_export_analytics_json(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test exporting analytics as JSON."""
    with patch('api.workflow_analytics_routes.get_analytics_engine') as mock_analytics:
        mock_engine = MagicMock()
        mock_engine.export_analytics.return_value = {
            "format": "json",
            "data": [
                {"workflow_id": "1", "status": "success"},
                {"workflow_id": "2", "status": "failed"}
            ]
        }
        mock_analytics.return_value = mock_engine

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/analytics/export?format=json")

            assert response.status_code == 200
            data = response.json()
            assert "data" in data


# ============================================================================
# GET /workflows/{execution_id}/status - Workflow Status Tests
# ============================================================================

def test_get_workflow_status_success(
    client: TestClient,
    db: Session,
    mock_execution_id: str,
    mock_user: User
):
    """Test getting workflow status successfully."""
    with patch('api.workflow_analytics_routes.get_workflow_execution') as mock_get:
        mock_get.return_value = {
            "execution_id": mock_execution_id,
            "status": "running",
            "current_step": "process_data",
            "progress": 0.6
        }

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get(f"/workflows/{mock_execution_id}/status")

            assert response.status_code == 200
            data = response.json()
            assert "status" in data or "data" in data


def test_get_workflow_status_not_found(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting status for non-existent workflow."""
    import uuid
    non_existent_id = str(uuid.uuid4())

    with patch('api.workflow_analytics_routes.get_workflow_execution') as mock_get:
        mock_get.return_value = None

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get(f"/workflows/{non_existent_id}/status")

            assert response.status_code == 404


# ============================================================================
# POST /workflows/{execution_id}/pause - Pause Workflow Tests
# ============================================================================

def test_pause_workflow_success(
    client: TestClient,
    db: Session,
    mock_execution_id: str,
    mock_user: User
):
    """Test pausing workflow successfully."""
    with patch('api.workflow_analytics_routes.pause_workflow_execution') as mock_pause:
        mock_pause.return_value = {
            "success": True,
            "execution_id": mock_execution_id,
            "status": "paused"
        }

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post(f"/workflows/{mock_execution_id}/pause")

            assert response.status_code == 200
            data = response.json()
            assert "success" in data or "status" in data


# ============================================================================
# POST /workflows/{execution_id}/resume - Resume Workflow Tests
# ============================================================================

def test_resume_workflow_success(
    client: TestClient,
    db: Session,
    mock_execution_id: str,
    mock_user: User
):
    """Test resuming workflow successfully."""
    with patch('api.workflow_analytics_routes.resume_workflow_execution') as mock_resume:
        mock_resume.return_value = {
            "success": True,
            "execution_id": mock_execution_id,
            "status": "running"
        }

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post(f"/workflows/{mock_execution_id}/resume")

            assert response.status_code == 200
            data = response.json()
            assert "success" in data or "status" in data


# ============================================================================
# POST /workflows/{execution_id}/cancel - Cancel Workflow Tests
# ============================================================================

def test_cancel_workflow_success(
    client: TestClient,
    db: Session,
    mock_execution_id: str,
    mock_user: User
):
    """Test cancelling workflow successfully."""
    with patch('api.workflow_analytics_routes.cancel_workflow_execution') as mock_cancel:
        mock_cancel.return_value = {
            "success": True,
            "execution_id": mock_execution_id,
            "status": "cancelled"
        }

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post(f"/workflows/{mock_execution_id}/cancel")

            assert response.status_code == 200
            data = response.json()
            assert "success" in data or "status" in data


# ============================================================================
# Request Validation Tests
# ============================================================================

def test_export_analytics_invalid_format(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test export with invalid format."""
    with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get("/analytics/export?format=xml")

        assert response.status_code == 400


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_get_workflow_analytics_error(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test error handling in workflow analytics."""
    with patch('api.workflow_analytics_routes.get_analytics_engine') as mock_analytics:
        mock_engine = MagicMock()
        mock_engine.get_workflow_statistics.side_effect = Exception("Database error")
        mock_analytics.return_value = mock_engine

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/analytics/workflows")

            assert response.status_code == 500


# ============================================================================
# Response Format Tests
# ============================================================================

def test_analytics_response_format(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test analytics response has correct format."""
    with patch('api.workflow_analytics_routes.get_analytics_engine') as mock_analytics:
        mock_engine = MagicMock()
        mock_engine.get_workflow_statistics.return_value = {
            "total_workflows": 100,
            "successful": 85
        }
        mock_analytics.return_value = mock_engine

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/analytics/workflows")

            data = response.json()
            assert isinstance(data, dict)
            assert "total_workflows" in data or "data" in data


def test_workflow_status_response_format(
    client: TestClient,
    db: Session,
    mock_execution_id: str,
    mock_user: User
):
    """Test workflow status response has correct format."""
    with patch('api.workflow_analytics_routes.get_workflow_execution') as mock_get:
        mock_get.return_value = {
            "execution_id": mock_execution_id,
            "status": "running",
            "progress": 0.5
        }

        with patch('api.workflow_analytics_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get(f"/workflows/{mock_execution_id}/status")

            data = response.json()
            assert isinstance(data, dict)
            assert "status" in data or "data" in data
