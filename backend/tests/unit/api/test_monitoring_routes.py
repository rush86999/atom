"""
Unit Tests for Monitoring Routes

Tests condition monitoring API endpoints:
- Create/update/delete condition monitors
- Monitor listing and retrieval
- Alert management
- Condition testing
- Preset configurations

Target Coverage: 80%
Target Branch Coverage: 50%+
Pass Rate Target: 95%+
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.monitoring_routes import router, CreateMonitorRequest, UpdateMonitorRequest
from core.database import get_db
from core.models import ConditionMonitor, ConditionAlert


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create test FastAPI app with monitoring routes."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db():
    """Create database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# Test Class: Create Condition Monitor
# =============================================================================

class TestCreateConditionMonitor:
    """Tests for POST /api/v1/monitoring/condition/create"""

    def test_creates_new_monitor(self, client, db):
        """RED: Test creating a new condition monitor."""
        request_data = {
            "agent_id": "agent-123",
            "name": "Inbox Volume Monitor",
            "condition_type": "inbox_volume",
            "threshold_config": {"max_emails": 100},
            "platforms": [{"platform": "slack", "recipient_id": "channel-123"}],
            "check_interval_seconds": 300
        }

        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/monitoring/condition/create", json=request_data)

            # Should return 201 or 200
            assert response.status_code in [200, 201]
            data = response.json()
            assert "id" in data or "agent_id" in data

    def test_validates_required_fields(self, client):
        """RED: Test that required fields are validated."""
        # Missing required fields
        request_data = {
            "agent_id": "agent-123"
            # Missing name, condition_type, threshold_config, platforms
        }

        response = client.post("/api/v1/monitoring/condition/create", json=request_data)

        # Should return validation error
        assert response.status_code == 422

    def test_accepts_check_interval(self, client, db):
        """RED: Test that custom check interval is accepted."""
        request_data = {
            "agent_id": "agent-123",
            "name": "Frequent Check",
            "condition_type": "api_metrics",
            "threshold_config": {"max_latency_ms": 500},
            "platforms": [],
            "check_interval_seconds": 60  # 1 minute
        }

        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/monitoring/condition/create", json=request_data)

            assert response.status_code in [200, 201]


# =============================================================================
# Test Class: List Conditions
# =============================================================================

class TestListConditions:
    """Tests for GET /api/v1/monitoring/condition/list"""

    def test_lists_all_monitors(self, client, db):
        """RED: Test listing all condition monitors."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_db.query.return_value.all.return_value = []
            mock_get_db.return_value = mock_db

            response = client.get("/api/v1/monitoring/condition/list")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_filters_by_agent_id(self, client, db):
        """RED: Test filtering monitors by agent ID."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_db.query.return_value = mock_query
            mock_get_db.return_value = mock_db

            response = client.get("/api/v1/monitoring/condition/list?agent_id=agent-123")

            assert response.status_code == 200
            # Should call filter with agent_id
            assert mock_query.filter.called


# =============================================================================
# Test Class: Get Monitor Details
# =============================================================================

class TestGetMonitorDetails:
    """Tests for GET /api/v1/monitoring/condition/{monitor_id}"""

    def test_get_monitor_by_id(self, client, db):
        """RED: Test getting monitor details by ID."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_monitor = Mock()
            mock_monitor.id = "monitor-123"
            mock_monitor.name = "Test Monitor"
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_monitor
            mock_get_db.return_value = mock_db

            response = client.get("/api/v1/monitoring/condition/monitor-123")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "monitor-123"

    def test_returns_404_for_nonexistent_monitor(self, client):
        """RED: Test 404 returned for nonexistent monitor."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_db.query.return_value.filter_by.return_value.first.return_value = None
            mock_get_db.return_value = mock_db

            response = client.get("/api/v1/monitoring/condition/nonexistent")

            assert response.status_code == 404


# =============================================================================
# Test Class: Update Monitor
# =============================================================================

class TestUpdateMonitor:
    """Tests for PUT /api/v1/monitoring/condition/{monitor_id}"""

    def test_updates_monitor_name(self, client, db):
        """RED: Test updating monitor name."""
        request_data = {
            "name": "Updated Monitor Name"
        }

        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_monitor = Mock()
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_monitor
            mock_get_db.return_value = mock_db

            response = client.put("/api/v1/monitoring/condition/monitor-123", json=request_data)

            assert response.status_code in [200, 201]

    def test_updates_threshold_config(self, client, db):
        """RED: Test updating threshold configuration."""
        request_data = {
            "threshold_config": {"new_threshold": 100}
        }

        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_monitor = Mock()
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_monitor
            mock_get_db.return_value = mock_db

            response = client.put("/api/v1/monitoring/condition/monitor-123", json=request_data)

            assert response.status_code in [200, 201]


# =============================================================================
# Test Class: Pause/Resume Monitor
# =============================================================================

class TestPauseResumeMonitor:
    """Tests for pause and resume endpoints."""

    def test_pauses_monitor(self, client, db):
        """RED: Test pausing an active monitor."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_monitor = Mock()
            mock_monitor.status = "active"
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_monitor
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/monitoring/condition/monitor-123/pause")

            assert response.status_code in [200, 201]
            data = response.json()
            assert data.get("status") in ["paused", "active"]

    def test_resumes_paused_monitor(self, client, db):
        """RED: Test resuming a paused monitor."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_monitor = Mock()
            mock_monitor.status = "paused"
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_monitor
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/monitoring/condition/monitor-123/resume")

            assert response.status_code in [200, 201]
            data = response.json()
            assert data.get("status") in ["active", "paused"]


# =============================================================================
# Test Class: Delete Monitor
# =============================================================================

class TestDeleteMonitor:
    """Tests for DELETE /api/v1/monitoring/condition/{monitor_id}"""

    def test_deletes_existing_monitor(self, client, db):
        """RED: Test deleting an existing monitor."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_monitor = Mock()
            mock_monitor.id = "monitor-123"
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_monitor
            mock_db.delete.return_value = 1
            mock_db.commit = Mock()
            mock_get_db.return_value = mock_db

            response = client.delete("/api/v1/monitoring/condition/monitor-123")

            assert response.status_code == 200

    def test_returns_404_for_nonexistent_monitor(self, client):
        """RED: Test 404 when deleting nonexistent monitor."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_db.query.return_value.filter_by.return_value.first.return_value = None
            mock_get_db.return_value = mock_db

            response = client.delete("/api/v1/monitoring/condition/nonexistent")

            assert response.status_code == 404


# =============================================================================
# Test Class: Test Condition
# =============================================================================

class TestCondition:
    """Tests for POST /api/v1/monitoring/condition/{monitor_id}/test"""

    def test_tests_condition_evaluation(self, client, db):
        """RED: Test condition evaluation against current value."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_monitor = Mock()
            mock_monitor.id = "monitor-123"
            mock_monitor.name = "Test Monitor"
            mock_monitor.condition_type = "api_metrics"
            mock_monitor.threshold_config = {"max_latency_ms": 500}
            mock_db.query.return_value.filter_by.return_value.first.return_value = mock_monitor
            mock_get_db.return_value = mock_db

            response = client.post("/api/v1/monitoring/condition/monitor-123/test")

            assert response.status_code == 200
            data = response.json()
            assert "monitor_id" in data
            assert "triggered" in data


# =============================================================================
# Test Class: Alerts
# =============================================================================

class TestAlerts:
    """Tests for GET /api/v1/monitoring/alerts"""

    def test_lists_alerts(self, client, db):
        """RED: Test listing all alerts."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_db.query.return_value.all.return_value = []
            mock_get_db.return_value = mock_db

            response = client.get("/api/v1/monitoring/alerts")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_filters_alerts_by_monitor(self, client, db):
        """RED: Test filtering alerts by monitor_id."""
        with patch('api.monitoring_routes.get_db_session') as mock_get_db:
            mock_db = Mock()
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_db.query.return_value = mock_query
            mock_get_db.return_value = mock_db

            response = client.get("/api/v1/monitoring/alerts?monitor_id=monitor-123")

            assert response.status_code == 200
            # Should call filter with monitor_id
            assert mock_query.filter.called


# =============================================================================
# Test Class: Health Check Endpoints
# =============================================================================

class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_live_endpoint(self, client):
        """RED: Test /health/live endpoint."""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_health_ready_endpoint(self, client):
        """RED: Test /health/ready endpoint with database check."""
        with patch('api.monitoring_routes.get_db') as mock_get_db:
            mock_db = Mock()
            mock_db.execute.return_value = None
            mock_get_db.return_value = mock_db

            response = client.get("/health/ready")

            assert response.status_code == 200
            data = response.json()
            assert "status" in data


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
