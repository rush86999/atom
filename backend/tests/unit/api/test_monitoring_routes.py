"""
Unit Tests for Monitoring Routes

Tests condition monitoring API endpoints:
- Create/update/delete condition monitors
- Monitor listing and retrieval
- Alert management
- Condition testing
- Preset configurations

The routes depend on ``get_db_session`` / ``get_current_user`` and delegate DB
work to ``ConditionMonitoringService``. Because FastAPI's ``Depends(...)``
captures the dependency callable at decoration time, patching a module-level
name (e.g. ``api.monitoring_routes.get_db_session``) has no effect. These
tests therefore use ``app.dependency_overrides`` and mock the service class so
they exercise the route layer (parsing, auth, response serialization) without
touching a database.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException

from api.monitoring_routes import (
    router,
    CreateMonitorRequest,
    UpdateMonitorRequest,
    MonitorResponse,
    AlertResponse,
    TestConditionResponse,
)
from core.auth import get_current_user
from core.database import get_db_session
from api.health_routes import router as health_router


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
    """Create test client (server exceptions surface as 5xx responses)."""
    return TestClient(app, raise_server_exceptions=False)


def _override_db(app):
    """Point the route's DB dependency at an inert mock session."""
    app.dependency_overrides[get_db_session] = lambda: Mock()


def _override_user(app):
    """Point the route's auth dependency at a fake authenticated user."""
    app.dependency_overrides[get_current_user] = lambda: Mock(id="user-1", role="admin")


def _monitor(**overrides):
    """Build a valid MonitorResponse, overriding any field."""
    base = dict(
        id="monitor-123",
        agent_id="agent-123",
        agent_name="Agent",
        name="Test Monitor",
        description=None,
        condition_type="inbox_volume",
        threshold_config={"max_emails": 100},
        composite_logic=None,
        composite_conditions=None,
        check_interval_seconds=300,
        platforms=[{"platform": "slack", "recipient_id": "channel-123"}],
        alert_template=None,
        throttle_minutes=30,
        last_alert_sent_at=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    base.update(overrides)
    return MonitorResponse(**base)


# =============================================================================
# Test Class: Create Condition Monitor
# =============================================================================

class TestCreateConditionMonitor:
    """Tests for POST /api/v1/monitoring/condition/create"""

    def test_creates_new_monitor(self, client, app):
        """Test creating a new condition monitor."""
        request_data = {
            "agent_id": "agent-123",
            "name": "Inbox Volume Monitor",
            "condition_type": "inbox_volume",
            "threshold_config": {"max_emails": 100},
            "platforms": [{"platform": "slack", "recipient_id": "channel-123"}],
            "check_interval_seconds": 300
        }

        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.create_monitor.return_value = _monitor(id="monitor-new", agent_id="agent-123")
            _override_db(app)
            _override_user(app)

            response = client.post("/api/v1/monitoring/condition/create", json=request_data)

            # Should return 201 or 200
            assert response.status_code in [200, 201]
            data = response.json()
            assert "id" in data or "agent_id" in data
            # The service must have been called with the request's fields
            mock_service.create_monitor.assert_called_once()
            assert mock_service.create_monitor.call_args.kwargs.get("agent_id") == "agent-123"

    def test_validates_required_fields(self, client, app):
        """Test that required fields are validated."""
        _override_db(app)
        _override_user(app)
        # Missing required fields
        request_data = {
            "agent_id": "agent-123"
            # Missing name, condition_type, threshold_config, platforms
        }

        response = client.post("/api/v1/monitoring/condition/create", json=request_data)

        # Should return validation error
        assert response.status_code == 422

    def test_accepts_check_interval(self, client, app):
        """Test that custom check interval is accepted."""
        request_data = {
            "agent_id": "agent-123",
            "name": "Frequent Check",
            "condition_type": "api_metrics",
            "threshold_config": {"max_latency_ms": 500},
            "platforms": [],
            "check_interval_seconds": 60  # 1 minute
        }

        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.create_monitor.return_value = _monitor()
            _override_db(app)
            _override_user(app)

            response = client.post("/api/v1/monitoring/condition/create", json=request_data)

            assert response.status_code in [200, 201]
            assert mock_service.create_monitor.call_args.kwargs.get("check_interval_seconds") == 60


# =============================================================================
# Test Class: List Conditions
# =============================================================================

class TestListConditions:
    """Tests for GET /api/v1/monitoring/condition/list"""

    def test_lists_all_monitors(self, client, app):
        """Test listing all condition monitors."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.get_monitors.return_value = []
            _override_db(app)

            response = client.get("/api/v1/monitoring/condition/list")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_filters_by_agent_id(self, client, app):
        """Test filtering monitors by agent ID."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.get_monitors.return_value = []
            _override_db(app)

            response = client.get("/api/v1/monitoring/condition/list?agent_id=agent-123")

            assert response.status_code == 200
            # The service must have been queried with the agent_id filter
            assert mock_service.get_monitors.call_args.kwargs.get("agent_id") == "agent-123"


# =============================================================================
# Test Class: Get Monitor Details
# =============================================================================

class TestGetMonitorDetails:
    """Tests for GET /api/v1/monitoring/condition/{monitor_id}"""

    def test_get_monitor_by_id(self, client, app):
        """Test getting monitor details by ID."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.get_monitor.return_value = _monitor(id="monitor-123", name="Test Monitor")
            _override_db(app)

            response = client.get("/api/v1/monitoring/condition/monitor-123")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "monitor-123"

    def test_returns_404_for_nonexistent_monitor(self, client, app):
        """Test 404 returned for nonexistent monitor."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.get_monitor.return_value = None
            _override_db(app)

            response = client.get("/api/v1/monitoring/condition/nonexistent")

            assert response.status_code == 404


# =============================================================================
# Test Class: Update Monitor
# =============================================================================

class TestUpdateMonitor:
    """Tests for PUT /api/v1/monitoring/condition/{monitor_id}"""

    def test_updates_monitor_name(self, client, app):
        """Test updating monitor name."""
        request_data = {
            "name": "Updated Monitor Name"
        }

        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.update_monitor.return_value = _monitor(name="Updated Monitor Name")
            _override_db(app)

            response = client.put("/api/v1/monitoring/condition/monitor-123", json=request_data)

            assert response.status_code in [200, 201]
            assert mock_service.update_monitor.call_args.kwargs.get("name") == "Updated Monitor Name"

    def test_updates_threshold_config(self, client, app):
        """Test updating threshold configuration."""
        request_data = {
            "threshold_config": {"new_threshold": 100}
        }

        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.update_monitor.return_value = _monitor(threshold_config={"new_threshold": 100})
            _override_db(app)

            response = client.put("/api/v1/monitoring/condition/monitor-123", json=request_data)

            assert response.status_code in [200, 201]


# =============================================================================
# Test Class: Pause/Resume Monitor
# =============================================================================

class TestPauseResumeMonitor:
    """Tests for pause and resume endpoints."""

    def test_pauses_monitor(self, client, app):
        """Test pausing an active monitor."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.pause_monitor.return_value = _monitor(status="paused")
            _override_db(app)

            response = client.post("/api/v1/monitoring/condition/monitor-123/pause")

            assert response.status_code in [200, 201]
            data = response.json()
            assert data.get("status") in ["paused", "active"]

    def test_resumes_paused_monitor(self, client, app):
        """Test resuming a paused monitor."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.resume_monitor.return_value = _monitor(status="active")
            _override_db(app)

            response = client.post("/api/v1/monitoring/condition/monitor-123/resume")

            assert response.status_code in [200, 201]
            data = response.json()
            assert data.get("status") in ["active", "paused"]


# =============================================================================
# Test Class: Delete Monitor
# =============================================================================

class TestDeleteMonitor:
    """Tests for DELETE /api/v1/monitoring/condition/{monitor_id}"""

    def test_deletes_existing_monitor(self, client, app):
        """Test deleting an existing monitor."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.delete_monitor.return_value = _monitor(id="monitor-123")
            _override_db(app)
            _override_user(app)

            response = client.delete("/api/v1/monitoring/condition/monitor-123")

            assert response.status_code == 200

    def test_returns_404_for_nonexistent_monitor(self, client, app):
        """Test 404 when deleting nonexistent monitor."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.delete_monitor.side_effect = HTTPException(
                status_code=404,
                detail="Condition monitor 'nonexistent' not found"
            )
            _override_db(app)
            _override_user(app)

            response = client.delete("/api/v1/monitoring/condition/nonexistent")

            assert response.status_code == 404


# =============================================================================
# Test Class: Test Condition
# =============================================================================

class TestCondition:
    """Tests for POST /api/v1/monitoring/condition/{monitor_id}/test"""

    def test_tests_condition_evaluation(self, client, app):
        """Test condition evaluation against current value."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.test_condition.return_value = TestConditionResponse(
                monitor_id="monitor-123",
                monitor_name="Test Monitor",
                condition_type="api_metrics",
                triggered=False,
                current_value={},
                threshold={"max_latency_ms": 500},
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            _override_db(app)

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

    def test_lists_alerts(self, client, app):
        """Test listing all alerts."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.get_alerts.return_value = []
            _override_db(app)

            response = client.get("/api/v1/monitoring/alerts")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_filters_alerts_by_monitor(self, client, app):
        """Test filtering alerts by monitor_id."""
        with patch('api.monitoring_routes.ConditionMonitoringService') as mock_cls:
            mock_service = mock_cls.return_value
            mock_service.get_alerts.return_value = []
            _override_db(app)

            response = client.get("/api/v1/monitoring/alerts?monitor_id=monitor-123")

            assert response.status_code == 200
            assert mock_service.get_alerts.call_args.kwargs.get("monitor_id") == "monitor-123"


# =============================================================================
# Test Class: Health Check Endpoints
# =============================================================================

class TestHealthEndpoints:
    """Tests for health check endpoints (mounted from api.health_routes)."""

    def test_health_live_endpoint(self):
        """Test /health/live endpoint."""
        app = FastAPI()
        app.include_router(health_router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_health_ready_endpoint(self):
        """Test /health/ready endpoint with database check."""
        app = FastAPI()
        app.include_router(health_router)
        client = TestClient(app, raise_server_exceptions=False)

        with patch('api.health_routes._check_database') as mock_db_check, \
             patch('api.health_routes._check_disk_space') as mock_disk_check:
            mock_db_check.return_value = {"healthy": True, "message": "ok", "latency_ms": 1.0}
            mock_disk_check.return_value = {"healthy": True, "message": "ok", "free_gb": 25.5}

            response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
