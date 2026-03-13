"""
Agent Control Routes Test Suite

Comprehensive TestClient-based coverage for agent_control_routes.py.
Tests all 5 endpoints: start, stop, restart, status, execute.

Coverage Target: 75%+ line coverage
Test Count: 30+ tests
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from typing import Dict, Any

# Import agent control routes
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from api.agent_control_routes import router


# ============================================================================
# FastAPI Test Client Setup
# ============================================================================

@pytest.fixture(scope="function")
def agent_control_client() -> TestClient:
    """
    Create TestClient with agent_control_routes router.

    Isolated app instance avoids SQLAlchemy metadata conflicts.
    """
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ============================================================================
# Test Agent Start Endpoint
# ============================================================================

class TestAgentStart:
    """Test suite for POST /api/agent/start endpoint."""

    def test_start_success(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test successful daemon start with default parameters."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            response = agent_control_client.post("/api/agent/start")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["pid"] == 12345
            assert data["status"] == "started"
            assert data["dashboard_url"] == "http://0.0.0.0:8000"
            assert "message" in data

    def test_start_with_custom_port(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test daemon start with custom port."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            response = agent_control_client.post(
                "/api/agent/start",
                json={"port": 9000}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["dashboard_url"] == "http://0.0.0.0:9000"
            mock_daemon_manager.start_daemon.assert_called_once_with(
                port=9000,
                host="0.0.0.0",
                workers=1,
                host_mount=False,
                dev=False
            )

    def test_start_with_custom_host(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test daemon start with custom host."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            response = agent_control_client.post(
                "/api/agent/start",
                json={"host": "127.0.0.1"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["dashboard_url"] == "http://127.0.0.1:8000"

    def test_start_with_workers(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test daemon start with multiple workers."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            response = agent_control_client.post(
                "/api/agent/start",
                json={"workers": 4}
            )

            assert response.status_code == 200
            mock_daemon_manager.start_daemon.assert_called_once_with(
                port=8000,
                host="0.0.0.0",
                workers=4,
                host_mount=False,
                dev=False
            )

    def test_start_with_host_mount(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test daemon start with host filesystem mount enabled."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            response = agent_control_client.post(
                "/api/agent/start",
                json={"host_mount": True}
            )

            assert response.status_code == 200
            mock_daemon_manager.start_daemon.assert_called_once_with(
                port=8000,
                host="0.0.0.0",
                workers=1,
                host_mount=True,
                dev=False
            )

    def test_start_with_dev_mode(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test daemon start with development mode enabled."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            response = agent_control_client.post(
                "/api/agent/start",
                json={"dev": True}
            )

            assert response.status_code == 200
            mock_daemon_manager.start_daemon.assert_called_once_with(
                port=8000,
                host="0.0.0.0",
                workers=1,
                host_mount=False,
                dev=True
            )

    def test_start_already_running(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test start returns 400 when daemon already running."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = True
            mock_daemon_manager.get_pid.return_value = 9999

            response = agent_control_client.post("/api/agent/start")

            assert response.status_code == 400
            data = response.json()
            assert "already running" in data["detail"].lower()
            assert "9999" in data["detail"]

    def test_start_returns_dashboard_url(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test start response includes dashboard URL."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            response = agent_control_client.post(
                "/api/agent/start",
                json={"host": "localhost", "port": 8080}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["dashboard_url"] == "http://localhost:8080"

    def test_start_invalid_port_too_high(self, agent_control_client: TestClient):
        """Test start returns 422 for port > 65535."""
        response = agent_control_client.post(
            "/api/agent/start",
            json={"port": 70000}
        )

        assert response.status_code == 422

    def test_start_invalid_port_zero(self, agent_control_client: TestClient):
        """Test start returns 422 for port 0."""
        response = agent_control_client.post(
            "/api/agent/start",
            json={"port": 0}
        )

        assert response.status_code == 422

    def test_start_invalid_port_negative(self, agent_control_client: TestClient):
        """Test start returns 422 for negative port."""
        response = agent_control_client.post(
            "/api/agent/start",
            json={"port": -1}
        )

        assert response.status_code == 422

    def test_start_invalid_workers_too_many(self, agent_control_client: TestClient):
        """Test start returns 422 for workers > 16."""
        response = agent_control_client.post(
            "/api/agent/start",
            json={"workers": 17}
        )

        assert response.status_code == 422

    def test_start_invalid_workers_zero(self, agent_control_client: TestClient):
        """Test start returns 422 for workers 0."""
        response = agent_control_client.post(
            "/api/agent/start",
            json={"workers": 0}
        )

        assert response.status_code == 422

    def test_start_boundary_port_values(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test start with boundary port values (1, 65535)."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            # Test port 1 (minimum valid)
            response1 = agent_control_client.post(
                "/api/agent/start",
                json={"port": 1}
            )
            assert response1.status_code == 200

            # Test port 65535 (maximum valid)
            response2 = agent_control_client.post(
                "/api/agent/start",
                json={"port": 65535}
            )
            assert response2.status_code == 200

    def test_start_runtime_error(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test start returns 500 on RuntimeError from start_daemon."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.side_effect = RuntimeError("Port already in use")

            response = agent_control_client.post("/api/agent/start")

            assert response.status_code == 500
            data = response.json()
            assert "Port already in use" in data["detail"]

    def test_start_io_error(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test start returns 500 on IOError from start_daemon."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.side_effect = IOError("Cannot write PID file")

            response = agent_control_client.post("/api/agent/start")

            assert response.status_code == 500
            data = response.json()
            assert "Cannot write PID file" in data["detail"]


# ============================================================================
# Test Agent Stop Endpoint
# ============================================================================

class TestAgentStop:
    """Test suite for POST /api/agent/stop endpoint."""

    def test_stop_success(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test successful daemon stop."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = True

            response = agent_control_client.post("/api/agent/stop")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["status"] == "stopped"
            assert "message" in data
            mock_daemon_manager.stop_daemon.assert_called_once()

    def test_stop_not_running(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test stop returns 400 when daemon not running."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False

            response = agent_control_client.post("/api/agent/stop")

            assert response.status_code == 400
            data = response.json()
            assert "not running" in data["detail"].lower()

    def test_stop_calls_stop_daemon(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test stop endpoint calls DaemonManager.stop_daemon()."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = True

            agent_control_client.post("/api/agent/stop")

            mock_daemon_manager.stop_daemon.assert_called_once()

    def test_stop_response_format(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test stop response has correct format."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = True

            response = agent_control_client.post("/api/agent/stop")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["status"] == "stopped"
            assert "message" in data
            assert data["message"] == "Atom OS stopped successfully"

    def test_stop_exception_handling(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test stop returns 500 on unexpected exception."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = True
            mock_daemon_manager.stop_daemon.side_effect = Exception("Unexpected error")

            response = agent_control_client.post("/api/agent/stop")

            assert response.status_code == 500
            data = response.json()
            assert "Unexpected error" in data["detail"]

    def test_stop_when_already_stopped(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test stop handles multiple stop calls gracefully (idempotency)."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False

            # First stop
            response1 = agent_control_client.post("/api/agent/stop")
            assert response1.status_code == 400

            # Second stop should also return 400
            response2 = agent_control_client.post("/api/agent/stop")
            assert response2.status_code == 400


# ============================================================================
# Test Agent Restart and Status Endpoints
# ============================================================================

class TestAgentRestart:
    """Test suite for POST /api/agent/restart endpoint."""

    def test_restart_when_running(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test restart stops then starts daemon when running."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = True
            mock_daemon_manager.start_daemon.return_value = 54321

            response = agent_control_client.post("/api/agent/restart")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["pid"] == 54321
            assert data["status"] == "restarted"
            assert data["was_running"] is True
            mock_daemon_manager.stop_daemon.assert_called_once()
            mock_daemon_manager.start_daemon.assert_called_once()

    def test_restart_when_not_running(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test restart starts daemon without stopping when not running."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 54321

            response = agent_control_client.post("/api/agent/restart")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["was_running"] is False
            mock_daemon_manager.stop_daemon.assert_not_called()
            mock_daemon_manager.start_daemon.assert_called_once()

    def test_restart_with_new_config(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test restart applies new port/host configuration."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 54321

            response = agent_control_client.post(
                "/api/agent/restart",
                json={"port": 9000, "host": "127.0.0.1"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["dashboard_url"] == "http://127.0.0.1:9000"

    def test_restart_was_running_true(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test restart returns was_running=True when daemon was running."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = True
            mock_daemon_manager.start_daemon.return_value = 54321

            response = agent_control_client.post("/api/agent/restart")

            assert response.status_code == 200
            data = response.json()
            assert data["was_running"] is True

    def test_restart_was_running_false(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test restart returns was_running=False when daemon was not running."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 54321

            response = agent_control_client.post("/api/agent/restart")

            assert response.status_code == 200
            data = response.json()
            assert data["was_running"] is False

    def test_restart_returns_new_pid(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test restart returns new PID after restart."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 54321

            response = agent_control_client.post("/api/agent/restart")

            assert response.status_code == 200
            data = response.json()
            assert data["pid"] == 54321

    def test_restart_exception_handling(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test restart returns 500 on unexpected exception."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.side_effect = Exception("Daemon error")

            response = agent_control_client.post("/api/agent/restart")

            assert response.status_code == 500
            data = response.json()
            assert "Daemon error" in data["detail"]


class TestAgentStatus:
    """Test suite for GET /api/agent/status endpoint."""

    def test_status_when_running(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock, test_daemon_status: dict):
        """Test status returns running status when daemon is running."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.get_status.return_value = test_daemon_status

            response = agent_control_client.get("/api/agent/status")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["status"]["running"] is True

    def test_status_when_not_running(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test status returns non-running status when daemon is not running."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.get_status.return_value = {
                "running": False,
                "pid": None,
                "uptime_seconds": None,
                "memory_mb": None,
                "cpu_percent": None,
                "status": "not_running"
            }

            response = agent_control_client.get("/api/agent/status")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["status"]["running"] is False

    def test_status_includes_pid(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock, test_daemon_status: dict):
        """Test status response includes PID."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.get_status.return_value = test_daemon_status

            response = agent_control_client.get("/api/agent/status")

            assert response.status_code == 200
            data = response.json()
            assert "pid" in data["status"]
            assert data["status"]["pid"] == 12345

    def test_status_includes_uptime(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock, test_daemon_status: dict):
        """Test status response includes uptime_seconds."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.get_status.return_value = test_daemon_status

            response = agent_control_client.get("/api/agent/status")

            assert response.status_code == 200
            data = response.json()
            assert "uptime_seconds" in data["status"]
            assert data["status"]["uptime_seconds"] == 3600

    def test_status_includes_memory(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock, test_daemon_status: dict):
        """Test status response includes memory_mb."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.get_status.return_value = test_daemon_status

            response = agent_control_client.get("/api/agent/status")

            assert response.status_code == 200
            data = response.json()
            assert "memory_mb" in data["status"]
            assert data["status"]["memory_mb"] == 256.5

    def test_status_includes_cpu(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock, test_daemon_status: dict):
        """Test status response includes cpu_percent."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.get_status.return_value = test_daemon_status

            response = agent_control_client.get("/api/agent/status")

            assert response.status_code == 200
            data = response.json()
            assert "cpu_percent" in data["status"]
            assert data["status"]["cpu_percent"] == 5.2

    def test_status_exception_handling(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test status returns 500 on get_status() exception."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.get_status.side_effect = Exception("Status error")

            response = agent_control_client.get("/api/agent/status")

            assert response.status_code == 500
            data = response.json()
            assert "Status error" in data["detail"]


# ============================================================================
# Test Agent Execute Endpoint
# ============================================================================

class TestAgentExecute:
    """Test suite for POST /api/agent/execute endpoint."""

    def test_execute_placeholder(self, agent_control_client: TestClient):
        """Test execute returns placeholder response (not yet implemented)."""
        response = agent_control_client.post(
            "/api/agent/execute",
            json={"command": "agent.chat('Hello')"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"] == "Command execution not yet implemented"

    def test_execute_response_format(self, agent_control_client: TestClient):
        """Test execute response has correct format."""
        response = agent_control_client.post(
            "/api/agent/execute",
            json={"command": "agent.status()"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "result" in data
        assert "note" in data
        assert "Use POST /api/agent/start" in data["note"]

    def test_execute_command_validation(self, agent_control_client: TestClient):
        """Test execute requires command field."""
        response = agent_control_client.post(
            "/api/agent/execute",
            json={}
        )

        assert response.status_code == 422

    def test_execute_timeout_validation(self, agent_control_client: TestClient):
        """Test execute validates timeout constraints (1-300 seconds)."""
        response = agent_control_client.post(
            "/api/agent/execute",
            json={"command": "agent.chat('Hello')", "timeout": 30}
        )

        assert response.status_code == 200

    def test_execute_invalid_timeout_low(self, agent_control_client: TestClient):
        """Test execute returns 422 for timeout < 1."""
        response = agent_control_client.post(
            "/api/agent/execute",
            json={"command": "agent.chat('Hello')", "timeout": 0}
        )

        assert response.status_code == 422

    def test_execute_invalid_timeout_high(self, agent_control_client: TestClient):
        """Test execute returns 422 for timeout > 300."""
        response = agent_control_client.post(
            "/api/agent/execute",
            json={"command": "agent.chat('Hello')", "timeout": 301}
        )

        assert response.status_code == 422

    def test_execute_boundary_timeout_values(self, agent_control_client: TestClient):
        """Test execute with boundary timeout values (1, 300)."""
        # Test timeout 1 (minimum valid)
        response1 = agent_control_client.post(
            "/api/agent/execute",
            json={"command": "agent.chat('Hello')", "timeout": 1}
        )
        assert response1.status_code == 200

        # Test timeout 300 (maximum valid)
        response2 = agent_control_client.post(
            "/api/agent/execute",
            json={"command": "agent.chat('Hello')", "timeout": 300}
        )
        assert response2.status_code == 200


# ============================================================================
# Test Error Paths and Edge Cases
# ============================================================================

class TestAgentControlErrorPaths:
    """Test error paths and edge cases for agent control routes."""

    def test_start_permission_error(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test start handles permission errors gracefully."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.side_effect = PermissionError("Permission denied")

            response = agent_control_client.post("/api/agent/start")

            assert response.status_code == 500

    def test_concurrent_start_requests(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test multiple simultaneous start requests (first wins)."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            # First request succeeds
            response1 = agent_control_client.post("/api/agent/start")
            assert response1.status_code == 200

            # Second request would see daemon as running (race condition simulation)
            mock_daemon_manager.is_running.return_value = True
            response2 = agent_control_client.post("/api/agent/start")
            assert response2.status_code == 400

    def test_very_long_host_name(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test start handles very long host names (1000+ characters)."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            long_host = "a" * 1000
            response = agent_control_client.post(
                "/api/agent/start",
                json={"host": long_host}
            )

            # Should succeed (FastAPI doesn't validate host length)
            assert response.status_code == 200

    def test_special_characters_in_command(self, agent_control_client: TestClient):
        """Test execute handles special characters in command."""
        special_command = "agent.chat('Hello\\nWorld\\t!'); system.run('rm -rf /')"
        response = agent_control_client.post(
            "/api/agent/execute",
            json={"command": special_command}
        )

        # Should succeed (endpoint is placeholder)
        assert response.status_code == 200

    def test_maximum_workers(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test start with 16 workers (maximum allowed)."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            response = agent_control_client.post(
                "/api/agent/start",
                json={"workers": 16}
            )

            assert response.status_code == 200

    def test_minimum_workers(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test start with 1 worker (minimum allowed)."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            response = agent_control_client.post(
                "/api/agent/start",
                json={"workers": 1}
            )

            assert response.status_code == 200

    def test_boundary_port_values(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test boundary port values (1, 65535)."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345

            # Port 1 (minimum valid)
            response1 = agent_control_client.post(
                "/api/agent/start",
                json={"port": 1}
            )
            assert response1.status_code == 200

            # Port 65535 (maximum valid)
            response2 = agent_control_client.post(
                "/api/agent/start",
                json={"port": 65535}
            )
            assert response2.status_code == 200


class TestAgentControlEdgeCases:
    """Test edge cases for agent control routes."""

    def test_restart_loop_protection(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test restart has built-in delay to prevent restart loops."""
        import time

        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = True
            mock_daemon_manager.start_daemon.return_value = 54321

            # Mock time.sleep to speed up test
            with patch('time.sleep') as mock_sleep:
                response = agent_control_client.post("/api/agent/restart")

                # Verify 2-second sleep was called
                mock_sleep.assert_called_once_with(2)

            assert response.status_code == 200

    def test_concurrent_stop_requests(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test multiple simultaneous stop requests (idempotent)."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = True

            # First stop
            response1 = agent_control_client.post("/api/agent/stop")
            assert response1.status_code == 200

            # Second stop (daemon no longer running)
            mock_daemon_manager.is_running.return_value = False
            response2 = agent_control_client.post("/api/agent/stop")
            assert response2.status_code == 400

    def test_status_with_stale_pid_file(self, agent_control_client: TestClient, mock_daemon_manager: MagicMock):
        """Test status handles stale PID file (process died)."""
        with patch('api.agent_control_routes.DaemonManager', mock_daemon_manager):
            mock_daemon_manager.get_status.return_value = {
                "running": False,
                "pid": 12345,
                "uptime_seconds": None,
                "memory_mb": None,
                "cpu_percent": None,
                "status": "stale_pid_file",
                "note": "Stale PID file"
            }

            response = agent_control_client.get("/api/agent/status")

            assert response.status_code == 200
            data = response.json()
            assert data["status"]["running"] is False
            assert data["status"]["status"] == "stale_pid_file"
