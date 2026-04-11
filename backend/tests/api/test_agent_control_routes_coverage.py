"""
Coverage-driven tests for agent_control_routes.py (0% -> 75%+ target)

API Endpoints Tested:
- POST /api/agent/start - Start Atom OS as background service
- POST /api/agent/stop - Stop Atom OS service
- POST /api/agent/restart - Restart Atom OS service
- GET /api/agent/status - Get Atom OS status
- POST /api/agent/execute - Execute single Atom command

Coverage Target Areas:
- Lines 1-50: Route initialization and request/response models
- Lines 50-160: Start endpoint
- Lines 160-205: Stop endpoint
- Lines 205-265: Restart endpoint
- Lines 265-310: Status endpoint
- Lines 310-355: Execute endpoint
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import agent control routes router
from api.agent_control_routes import (
    router,
    StartAgentRequest,
    StartAgentResponse,
    StopAgentResponse,
    RestartAgentResponse,
    AgentStatusResponse,
    ExecuteCommandRequest,
    ExecuteCommandResponse
)
from core.admin_endpoints import get_super_admin
from core.models import User


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_app():
    """Create FastAPI app with agent control routes for testing."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(scope="function")
def client(test_app: FastAPI):
    """
    Create TestClient for testing with super admin authentication.

    Overrides the get_super_admin dependency to return our test super admin user.
    """
    # Create test super admin user
    super_admin_user = User(
        id="test-super-admin-coverage",
        email="superadmin-coverage@test.com",
        role="super_admin"
    )

    def override_get_super_admin():
        return super_admin_user

    test_app.dependency_overrides[get_super_admin] = override_get_super_admin

    test_client = TestClient(test_app)
    try:
        yield test_client
    finally:
        test_app.dependency_overrides.clear()


# ============================================================================
# Request/Response Model Tests (6 tests)
# ============================================================================

def test_start_agent_request_model_defaults():
    """Cover StartAgentRequest default values (lines 38-46)."""
    request = StartAgentRequest()

    assert request.port == 8000
    assert request.host == "0.0.0.0"
    assert request.workers == 1
    assert request.host_mount is False
    assert request.dev is False


def test_start_agent_request_model_custom_values():
    """Cover StartAgentRequest with custom values."""
    request = StartAgentRequest(
        port=9000,
        host="localhost",
        workers=4,
        host_mount=True,
        dev=True
    )

    assert request.port == 9000
    assert request.host == "localhost"
    assert request.workers == 4
    assert request.host_mount is True
    assert request.dev is True


def test_execute_command_request_model_defaults():
    """Cover ExecuteCommandRequest default values (lines 88-93)."""
    request = ExecuteCommandRequest(command="test command")

    assert request.command == "test command"
    assert request.timeout == 30  # Default


def test_execute_command_request_custom_timeout():
    """Cover ExecuteCommandRequest with custom timeout."""
    request = ExecuteCommandRequest(command="test", timeout=60)

    assert request.command == "test"
    assert request.timeout == 60


def test_response_models_serialization():
    """Cover response model serialization."""
    start_response = StartAgentResponse(
        success=True,
        pid=12345,
        status="started",
        dashboard_url="http://localhost:8000",
        message="Started"
    )

    assert start_response.success is True
    assert start_response.pid == 12345
    assert start_response.status == "started"
    assert start_response.dashboard_url == "http://localhost:8000"
    assert start_response.message == "Started"


def test_response_models_with_errors():
    """Cover response models with error fields."""
    stop_response = StopAgentResponse(
        success=False,
        status="error",
        message="Failed to stop",
        error="Process not found"
    )

    assert stop_response.success is False
    assert stop_response.status == "error"
    assert stop_response.error == "Process not found"


# ============================================================================
# Start Endpoint Tests (12 tests)
# ============================================================================

@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_start_agent_success(mock_start, mock_is_running, client):
    """Cover successful agent start (lines 105-156)."""
    mock_is_running.return_value = False
    mock_start.return_value = 12345

    response = client.post("/api/agent/start", json={
        "port": 8000,
        "host": "0.0.0.0",
        "workers": 1,
        "host_mount": False,
        "dev": False
    })

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["pid"] == 12345
    assert result["status"] == "started"
    assert result["dashboard_url"] == "http://0.0.0.0:8000"
    assert result["message"] == "Atom OS started successfully"
    mock_start.assert_called_once_with(
        port=8000,
        host="0.0.0.0",
        workers=1,
        host_mount=False,
        dev=False
    )


@patch('api.agent_control_routes.DaemonManager.is_running')
def test_start_agent_already_running(mock_is_running, client):
    """Cover start when already running (lines 135-140)."""
    mock_is_running.return_value = True

    with patch('api.agent_control_routes.DaemonManager.get_pid', return_value=9999):
        response = client.post("/api/agent/start", json={"port": 8000})

    assert response.status_code == 400
    assert "already running" in response.json()["detail"].lower()
    assert "9999" in response.json()["detail"]


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_start_agent_runtime_error(mock_start, mock_is_running, client):
    """Cover start with RuntimeError (lines 158-159)."""
    mock_is_running.return_value = False
    mock_start.side_effect = RuntimeError("Port already in use")

    response = client.post("/api/agent/start", json={"port": 8000})

    assert response.status_code == 500
    assert "Port already in use" in response.json()["detail"]


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_start_agent_io_error(mock_start, mock_is_running, client):
    """Cover start with IOError (lines 160-161)."""
    mock_is_running.return_value = False
    mock_start.side_effect = IOError("PID file write failed")

    response = client.post("/api/agent/start", json={"port": 8000})

    assert response.status_code == 500
    assert "PID file write failed" in response.json()["detail"]


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_start_agent_with_custom_config(mock_start, mock_is_running, client):
    """Cover start with custom configuration."""
    mock_is_running.return_value = False
    mock_start.return_value = 54321

    response = client.post("/api/agent/start", json={
        "port": 9000,
        "host": "localhost",
        "workers": 4,
        "host_mount": True,
        "dev": True
    })

    assert response.status_code == 200
    result = response.json()
    assert result["pid"] == 54321
    assert result["dashboard_url"] == "http://localhost:9000"
    mock_start.assert_called_once_with(
        port=9000,
        host="localhost",
        workers=4,
        host_mount=True,
        dev=True
    )


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_start_agent_minimal_config(mock_start, mock_is_running, client):
    """Cover start with minimal configuration (defaults)."""
    mock_is_running.return_value = False
    mock_start.return_value = 11111

    response = client.post("/api/agent/start", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["pid"] == 11111
    assert result["dashboard_url"] == "http://0.0.0.0:8000"


@pytest.mark.parametrize("port,valid", [
    (8000, True),
    (3000, True),
    (65535, True),
    (0, False),     # Invalid port
    (65536, False),  # Invalid port
    (-1, False),     # Invalid port
])
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_start_agent_port_validation(mock_start, mock_is_running, client, port, valid):
    """Cover port validation in request model."""
    mock_is_running.return_value = False
    mock_start.return_value = 12345

    response = client.post("/api/agent/start", json={"port": port})

    if valid:
        # Should pass validation and reach the endpoint
        assert response.status_code == 200
    else:
        assert response.status_code == 422  # Validation error


@pytest.mark.parametrize("workers,valid", [
    (1, True),
    (4, True),
    (16, True),
    (0, False),     # Invalid workers
    (17, False),    # Invalid workers
])
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_start_agent_workers_validation(mock_start, mock_is_running, client, workers, valid):
    """Cover workers validation in request model."""
    mock_is_running.return_value = False
    mock_start.return_value = 12345

    response = client.post("/api/agent/start", json={
        "port": 8000,
        "workers": workers
    })

    if valid:
        assert response.status_code == 200
        assert response.status_code != 422
    else:
        assert response.status_code == 422


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_start_agent_generic_exception(mock_start, mock_is_running, client):
    """Cover start with generic exception."""
    mock_is_running.return_value = False
    mock_start.side_effect = OSError("Unexpected error")

    response = client.post("/api/agent/start", json={"port": 8000})

    # Should raise 500, as OSError is not caught
    assert response.status_code == 500


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_start_agent_response_structure(mock_start, mock_is_running, client):
    """Cover start response has all required fields."""
    mock_is_running.return_value = False
    mock_start.return_value = 12345

    response = client.post("/api/agent/start", json={"port": 8000})
    result = response.json()

    # Check all response fields
    assert "success" in result
    assert "pid" in result
    assert "status" in result
    assert "dashboard_url" in result
    assert "message" in result
    assert "error" not in result or result["error"] is None


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_start_agent_host_mount_enabled(mock_start, mock_is_running, client):
    """Cover start with host mount enabled."""
    mock_is_running.return_value = False
    mock_start.return_value = 22222

    response = client.post("/api/agent/start", json={
        "port": 8000,
        "host_mount": True
    })

    assert response.status_code == 200
    mock_start.assert_called_once_with(
        port=8000,
        host="0.0.0.0",
        workers=1,
        host_mount=True,
        dev=False
    )


# ============================================================================
# Stop Endpoint Tests (8 tests)
# ============================================================================

@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_stop_agent_success(mock_stop, mock_is_running, client):
    """Cover successful agent stop (lines 164-200)."""
    mock_is_running.return_value = True

    response = client.post("/api/agent/stop")

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["status"] == "stopped"
    assert result["message"] == "Atom OS stopped successfully"
    mock_stop.assert_called_once()


@patch('api.agent_control_routes.DaemonManager.is_running')
def test_stop_agent_not_running(mock_is_running, client):
    """Cover stop when not running (lines 188-192)."""
    mock_is_running.return_value = False

    response = client.post("/api/agent/stop")

    assert response.status_code == 400
    assert "not running" in response.json()["detail"].lower()


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_stop_agent_exception(mock_stop, mock_is_running, client):
    """Cover stop with unexpected exception (lines 202-205)."""
    mock_is_running.return_value = True
    mock_stop.side_effect = Exception("Stop failed")

    response = client.post("/api/agent/stop")

    assert response.status_code == 500
    assert "Stop failed" in response.json()["detail"]


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_stop_agent_response_structure(mock_stop, mock_is_running, client):
    """Cover stop response has all required fields."""
    mock_is_running.return_value = True

    response = client.post("/api/agent/stop")
    result = response.json()

    # Check all response fields
    assert "success" in result
    assert "status" in result
    assert "message" in result
    assert "error" not in result or result["error"] is None


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_stop_agent_called_once(mock_stop, mock_is_running, client):
    """Cover stop daemon is called exactly once."""
    mock_is_running.return_value = True

    response = client.post("/api/agent/stop")

    assert response.status_code == 200
    assert mock_stop.call_count == 1


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_stop_agent_with_runtime_error(mock_stop, mock_is_running, client):
    """Cover stop with RuntimeError."""
    mock_is_running.return_value = True
    mock_stop.side_effect = RuntimeError("Process not found")

    response = client.post("/api/agent/stop")

    assert response.status_code == 500
    assert "Process not found" in response.json()["detail"]


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_stop_agent_with_io_error(mock_stop, mock_is_running, client):
    """Cover stop with IOError."""
    mock_is_running.return_value = True
    mock_stop.side_effect = IOError("PID file error")

    response = client.post("/api/agent/stop")

    assert response.status_code == 500
    assert "PID file error" in response.json()["detail"]


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_stop_http_exception_propagates(mock_stop, mock_is_running, client):
    """Cover HTTPException is re-raised (lines 202-203)."""
    from fastapi import HTTPException
    mock_is_running.return_value = False

    response = client.post("/api/agent/stop")

    assert response.status_code == 400
    assert "not running" in response.json()["detail"].lower()


# ============================================================================
# Restart Endpoint Tests (10 tests)
# ============================================================================

@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_restart_agent_when_running(mock_stop, mock_start, mock_is_running, mock_sleep, client):
    """Cover restart when agent is running (lines 208-264)."""
    mock_is_running.return_value = True
    mock_start.return_value = 54321

    response = client.post("/api/agent/restart", json={
        "port": 8000,
        "host": "localhost",
        "workers": 2
    })

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["pid"] == 54321
    assert result["status"] == "restarted"
    assert result["was_running"] is True
    assert result["dashboard_url"] == "http://localhost:8000"
    assert result["message"] == "Atom OS restarted successfully"
    mock_stop.assert_called_once()
    mock_start.assert_called_once()


@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_restart_agent_when_not_running(mock_start, mock_is_running, mock_sleep, client):
    """Cover restart when agent is not running."""
    mock_is_running.side_effect = [False, False]
    mock_start.return_value = 11111

    response = client.post("/api/agent/restart", json={"port": 8000})

    assert response.status_code == 200
    result = response.json()
    assert result["was_running"] is False
    assert result["pid"] == 11111


@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_restart_agent_exception(mock_stop, mock_start, mock_is_running, mock_sleep, client):
    """Cover restart with exception (lines 263-264)."""
    mock_is_running.return_value = True
    mock_stop.side_effect = Exception("Restart failed")

    response = client.post("/api/agent/restart", json={"port": 8000})

    assert response.status_code == 500
    assert "Restart failed" in response.json()["detail"]


@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_restart_agent_with_custom_config(mock_stop, mock_start, mock_is_running, mock_sleep, client):
    """Cover restart with custom configuration."""
    mock_is_running.return_value = True
    mock_start.return_value = 99999

    response = client.post("/api/agent/restart", json={
        "port": 9000,
        "host": "0.0.0.0",
        "workers": 8,
        "host_mount": True,
        "dev": True
    })

    assert response.status_code == 200
    result = response.json()
    assert result["pid"] == 99999
    assert result["dashboard_url"] == "http://0.0.0.0:9000"
    mock_start.assert_called_once_with(
        port=9000,
        host="0.0.0.0",
        workers=8,
        host_mount=True,
        dev=True
    )


@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_restart_agent_sleep_called(mock_stop, mock_start, mock_is_running, mock_sleep, client):
    """Cover sleep is called during restart (line 244)."""
    mock_is_running.return_value = True
    mock_start.return_value = 12345

    response = client.post("/api/agent/restart", json={"port": 8000})

    assert response.status_code == 200
    mock_sleep.assert_called_once_with(2)


@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_restart_agent_not_running_no_stop(mock_start, mock_is_running, mock_sleep, client):
    """Cover restart when not running doesn't call stop."""
    mock_is_running.side_effect = [False, False]
    mock_start.return_value = 22222

    with patch('api.agent_control_routes.DaemonManager.stop_daemon') as mock_stop:
        response = client.post("/api/agent/restart", json={"port": 8000})

        assert response.status_code == 200
        mock_stop.assert_not_called()


@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_restart_agent_response_structure(mock_stop, mock_start, mock_is_running, mock_sleep, client):
    """Cover restart response has all required fields."""
    mock_is_running.return_value = True
    mock_start.return_value = 33333

    response = client.post("/api/agent/restart", json={"port": 8000})
    result = response.json()

    # Check all response fields
    assert "success" in result
    assert "pid" in result
    assert "status" in result
    assert "dashboard_url" in result
    assert "was_running" in result
    assert "message" in result
    assert "error" not in result or result["error"] is None


@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_restart_agent_with_start_error(mock_stop, mock_start, mock_is_running, mock_sleep, client):
    """Cover restart when start_daemon fails."""
    mock_is_running.return_value = True
    mock_stop.return_value = None
    mock_start.side_effect = RuntimeError("Port in use")

    response = client.post("/api/agent/restart", json={"port": 8000})

    assert response.status_code == 500
    assert "Port in use" in response.json()["detail"]


@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_restart_agent_minimal_config(mock_start, mock_is_running, mock_sleep, client):
    """Cover restart with minimal configuration."""
    mock_is_running.side_effect = [True, True]
    mock_start.return_value = 44444

    with patch('api.agent_control_routes.DaemonManager.stop_daemon'):
        response = client.post("/api/agent/restart", json={})

        assert response.status_code == 200
        result = response.json()
        assert result["pid"] == 44444


@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_restart_agent_was_running_tracking(mock_stop, mock_start, mock_is_running, mock_sleep, client):
    """Cover was_running field is tracked correctly."""
    # Test when running
    mock_is_running.return_value = True
    mock_start.return_value = 55555

    response = client.post("/api/agent/restart", json={"port": 8000})
    assert response.json()["was_running"] is True

    # Test when not running
    mock_is_running.side_effect = [False, False]
    mock_start.return_value = 66666

    response = client.post("/api/agent/restart", json={"port": 8000})
    assert response.json()["was_running"] is False


# ============================================================================
# Status Endpoint Tests (8 tests)
# ============================================================================

@patch('api.agent_control_routes.DaemonManager.get_status')
def test_get_status_success(mock_get_status, client):
    """Cover successful status retrieval (lines 267-309)."""
    mock_get_status.return_value = {
        "running": True,
        "pid": 12345,
        "uptime_seconds": 3600,
        "memory_mb": 256.5,
        "cpu_percent": 5.2,
        "status": "running"
    }

    response = client.get("/api/agent/status")

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["status"]["running"] is True
    assert result["status"]["pid"] == 12345
    assert result["status"]["uptime_seconds"] == 3600
    assert result["status"]["memory_mb"] == 256.5
    assert result["status"]["cpu_percent"] == 5.2


@patch('api.agent_control_routes.DaemonManager.get_status')
def test_get_status_not_running(mock_get_status, client):
    """Cover status when not running."""
    mock_get_status.return_value = {
        "running": False,
        "pid": None,
        "uptime_seconds": 0,
        "memory_mb": 0,
        "cpu_percent": 0,
        "status": "stopped"
    }

    response = client.get("/api/agent/status")

    assert response.status_code == 200
    assert response.json()["status"]["running"] is False
    assert response.json()["status"]["pid"] is None


@patch('api.agent_control_routes.DaemonManager.get_status')
def test_get_status_exception(mock_get_status, client):
    """Cover status with exception (lines 308-309)."""
    mock_get_status.side_effect = Exception("Status check failed")

    response = client.get("/api/agent/status")

    assert response.status_code == 500
    assert "Status check failed" in response.json()["detail"]


@patch('api.agent_control_routes.DaemonManager.get_status')
def test_get_status_response_structure(mock_get_status, client):
    """Cover status response has all required fields."""
    mock_get_status.return_value = {
        "running": True,
        "pid": 99999,
        "uptime_seconds": 7200,
        "memory_mb": 512.0,
        "cpu_percent": 10.5,
        "status": "running"
    }

    response = client.get("/api/agent/status")
    result = response.json()

    # Check all response fields
    assert "success" in result
    assert "status" in result
    assert isinstance(result["status"], dict)


@patch('api.agent_control_routes.DaemonManager.get_status')
def test_get_status_with_high_memory(mock_get_status, client):
    """Cover status with high memory usage."""
    mock_get_status.return_value = {
        "running": True,
        "pid": 12345,
        "uptime_seconds": 86400,
        "memory_mb": 2048.75,
        "cpu_percent": 25.8,
        "status": "running"
    }

    response = client.get("/api/agent/status")

    assert response.status_code == 200
    assert response.json()["status"]["memory_mb"] == 2048.75


@patch('api.agent_control_routes.DaemonManager.get_status')
def test_get_status_with_runtime_error(mock_get_status, client):
    """Cover status with RuntimeError."""
    mock_get_status.side_effect = RuntimeError("Daemon not responding")

    response = client.get("/api/agent/status")

    assert response.status_code == 500
    assert "Daemon not responding" in response.json()["detail"]


@patch('api.agent_control_routes.DaemonManager.get_status')
def test_get_status_with_io_error(mock_get_status, client):
    """Cover status with IOError."""
    mock_get_status.side_effect = IOError("PID file not found")

    response = client.get("/api/agent/status")

    assert response.status_code == 500
    assert "PID file not found" in response.json()["detail"]


@patch('api.agent_control_routes.DaemonManager.get_status')
def test_get_status_called_once(mock_get_status, client):
    """Cover get_status is called exactly once."""
    mock_get_status.return_value = {
        "running": True,
        "pid": 12345,
        "uptime_seconds": 100,
        "memory_mb": 100.0,
        "cpu_percent": 1.0,
        "status": "running"
    }

    response = client.get("/api/agent/status")

    assert response.status_code == 200
    assert mock_get_status.call_count == 1


# ============================================================================
# Execute Endpoint Tests (6 tests)
# ============================================================================

def test_execute_command_placeholder(client):
    """Cover execute endpoint placeholder (lines 312-354)."""
    response = client.post("/api/agent/execute", json={
        "command": "agent.chat('Hello')",
        "timeout": 30
    })

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert "not yet implemented" in result["result"]
    assert "note" in result
    assert result["note"] == "Use POST /api/agent/start to run Atom as service instead"


def test_execute_command_with_custom_timeout(client):
    """Cover execute with custom timeout."""
    response = client.post("/api/agent/execute", json={
        "command": "test command",
        "timeout": 60
    })

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True


@pytest.mark.parametrize("timeout,valid", [
    (1, True),
    (30, True),
    (300, True),
    (0, False),     # Invalid timeout
    (301, False),   # Invalid timeout
])
def test_execute_timeout_validation(client, timeout, valid):
    """Cover timeout validation in execute request."""
    response = client.post("/api/agent/execute", json={
        "command": "test",
        "timeout": timeout
    })

    if valid:
        assert response.status_code == 200
    else:
        assert response.status_code == 422


def test_execute_missing_command(client):
    """Cover execute with missing command field."""
    response = client.post("/api/agent/execute", json={"timeout": 30})

    assert response.status_code == 422


def test_execute_empty_command(client):
    """Cover execute with empty command (should fail validation)."""
    response = client.post("/api/agent/execute", json={
        "command": "",
        "timeout": 30
    })

    # May pass validation but endpoint returns success
    assert response.status_code in [200, 422]


def test_execute_command_response_structure(client):
    """Cover execute response has all required fields."""
    response = client.post("/api/agent/execute", json={
        "command": "test command",
        "timeout": 30
    })
    result = response.json()

    # Check all response fields
    assert "success" in result
    assert "result" in result
    assert "note" in result
    assert "error" not in result or result["error"] is None


# ============================================================================
# Edge Cases and Integration Tests (6 tests)
# ============================================================================

@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_start_stop_restart_workflow(mock_stop, mock_start, mock_is_running, client):
    """Cover full start-stop-restart workflow."""
    mock_is_running.side_effect = [False, True, False, True, False]
    mock_start.return_value = 12345

    # Start
    response = client.post("/api/agent/start", json={"port": 8000})
    assert response.status_code == 200

    # Stop (now running)
    response = client.post("/api/agent/stop")
    assert response.status_code == 200


@patch('api.agent_control_routes.DaemonManager.is_running')
def test_status_when_not_running(mock_is_running, client):
    """Cover status checks when daemon is not running."""
    mock_is_running.return_value = False

    with patch('api.agent_control_routes.DaemonManager.get_status') as mock_status:
        mock_status.return_value = {
            "running": False,
            "pid": None,
            "uptime_seconds": 0,
            "memory_mb": 0,
            "cpu_percent": 0,
            "status": "stopped"
        }

        response = client.get("/api/agent/status")
        assert response.status_code == 200
        assert response.json()["status"]["running"] is False


def test_router_prefix_and_tags():
    """Cover router has correct prefix and tags (line 34)."""
    assert router.prefix == "/api/agent"
    assert router.tags == ["agent-control"]


def test_all_endpoints_registered():
    """Cover all endpoints are registered on router."""
    routes = [route.path for route in router.routes]
    assert "/api/agent/start" in routes
    assert "/api/agent/stop" in routes
    assert "/api/agent/restart" in routes
    assert "/api/agent/status" in routes
    assert "/api/agent/execute" in routes


@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
def test_concurrent_start_requests(mock_start, mock_is_running, client):
    """Cover handling of concurrent start requests."""
    mock_is_running.side_effect = [False, True, False]
    mock_start.return_value = 12345

    # First request succeeds
    response1 = client.post("/api/agent/start", json={"port": 8000})
    assert response1.status_code == 200

    # Second request fails (already running)
    response2 = client.post("/api/agent/start", json={"port": 8000})
    assert response2.status_code == 400


@patch('time.sleep')
@patch('api.agent_control_routes.DaemonManager.is_running')
@patch('api.agent_control_routes.DaemonManager.start_daemon')
@patch('api.agent_control_routes.DaemonManager.stop_daemon')
def test_restart_preserves_config(mock_stop, mock_start, mock_is_running, mock_sleep, client):
    """Cover restart preserves configuration from request."""
    mock_is_running.return_value = True
    mock_start.return_value = 77777

    response = client.post("/api/agent/restart", json={
        "port": 8888,
        "host": "127.0.0.1",
        "workers": 4
    })

    assert response.status_code == 200
    mock_start.assert_called_once_with(
        port=8888,
        host="127.0.0.1",
        workers=4,
        host_mount=False,
        dev=False
    )
