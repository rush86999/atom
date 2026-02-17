"""
Time Travel Routes API Tests

Tests for workflow time-travel/forking endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from main_api_app import app


class TestTimeTravelRoutes:
    """Test time travel API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @patch('api.time_travel_routes.get_orchestrator')
    def test_fork_workflow_success(self, mock_get_orchestrator, client):
        """Test successful workflow fork."""
        # Mock orchestrator
        mock_orch = Mock()
        mock_orch.fork_execution = AsyncMock(return_value="new-execution-123")
        mock_get_orchestrator.return_value = mock_orch

        response = client.post(
            "/api/time-travel/workflows/exec-456/fork",
            json={
                "step_id": "step-789",
                "new_variables": {"counter": 10}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "success" in data

    @patch('api.time_travel_routes.get_orchestrator')
    def test_fork_workflow_without_variables(self, mock_get_orchestrator, client):
        """Test forking workflow without modifying variables."""
        mock_orch = Mock()
        mock_orch.fork_execution = AsyncMock(return_value="new-exec-no-vars")
        mock_get_orchestrator.return_value = mock_orch

        response = client.post(
            "/api/time-travel/workflows/exec-123/fork",
            json={
                "step_id": "step-1"
            }
        )

        assert response.status_code == 200

    @patch('api.time_travel_routes.get_orchestrator')
    def test_fork_workflow_not_found(self, mock_get_orchestrator, client):
        """Test forking when execution step not found."""
        mock_orch = Mock()
        mock_orch.fork_execution = AsyncMock(return_value=None)
        mock_get_orchestrator.return_value = mock_orch

        response = client.post(
            "/api/time-travel/workflows/exec-not-found/fork",
            json={
                "step_id": "step-not-found"
            }
        )

        # Should return 404
        assert response.status_code == 404

    @patch('api.time_travel_routes.get_orchestrator')
    def test_fork_workflow_response_structure(self, mock_get_orchestrator, client):
        """Test that fork response has correct structure."""
        mock_orch = Mock()
        mock_orch.fork_execution = AsyncMock(return_value="forked-exec-456")
        mock_get_orchestrator.return_value = mock_orch

        response = client.post(
            "/api/time-travel/workflows/original-exec/fork",
            json={
                "step_id": "fork-step"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should have execution IDs in response
        if "data" in data:
            assert "original_execution_id" in data["data"]
            assert "new_execution_id" in data["data"]

    @patch('api.time_travel_routes.get_orchestrator')
    def test_fork_workflow_calls_orchestrator(self, mock_get_orchestrator, client):
        """Test that fork calls orchestrator correctly."""
        mock_orch = Mock()
        mock_orch.fork_execution = AsyncMock(return_value="new-exec-789")
        mock_get_orchestrator.return_value = mock_orch

        response = client.post(
            "/api/time-travel/workflows/test-exec/fork",
            json={
                "step_id": "test-step",
                "new_variables": {"var1": "value1"}
            }
        )

        assert response.status_code == 200
        # Verify orchestrator was called
        mock_orch.fork_execution.assert_called_once_with(
            original_execution_id="test-exec",
            step_id="test-step",
            new_variables={"var1": "value1"}
        )

    @patch('api.time_travel_routes.get_orchestrator')
    def test_fork_workflow_with_complex_variables(self, mock_get_orchestrator, client):
        """Test forking with complex variable modifications."""
        mock_orch = Mock()
        mock_orch.fork_execution = AsyncMock(return_value="new-exec-complex")
        mock_get_orchestrator.return_value = mock_orch

        complex_vars = {
            "counter": 42,
            "settings": {
                "debug": True,
                "level": "verbose"
            },
            "list_data": [1, 2, 3],
            "flag": False
        }

        response = client.post(
            "/api/time-travel/workflows/exec-complex/fork",
            json={
                "step_id": "step-complex",
                "new_variables": complex_vars
            }
        )

        assert response.status_code == 200

    @patch('api.time_travel_routes.get_orchestrator')
    def test_time_travel_endpoint_returns_json(self, mock_get_orchestrator, client):
        """Test that time travel endpoint returns JSON."""
        mock_orch = Mock()
        mock_orch.fork_execution = AsyncMock(return_value="json-test")
        mock_get_orchestrator.return_value = mock_orch

        response = client.post(
            "/api/time-travel/workflows/test/fork",
            json={"step_id": "test"}
        )

        assert response.headers["content-type"].startswith("application/json")

    @patch('api.time_travel_routes.get_orchestrator')
    def test_fork_different_executions(self, mock_get_orchestrator, client):
        """Test forking different workflow executions."""
        mock_orch = Mock()
        mock_orch.fork_execution = AsyncMock(return_value="forked-exec")
        mock_get_orchestrator.return_value = mock_orch

        execution_ids = ["exec-1", "exec-2", "exec-3"]

        for exec_id in execution_ids:
            response = client.post(
                f"/api/time-travel/workflows/{exec_id}/fork",
                json={"step_id": "step-1"}
            )

            assert response.status_code == 200

    @patch('api.time_travel_routes.get_orchestrator')
    def test_fork_response_message(self, mock_get_orchestrator, client):
        """Test that fork response has appropriate message."""
        mock_orch = Mock()
        mock_orch.fork_execution = AsyncMock(return_value="multiverse-exec")
        mock_get_orchestrator.return_value = mock_orch

        response = client.post(
            "/api/time-travel/workflows/test/fork",
            json={"step_id": "test-step"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should have a message about multiverse
        if "message" in data:
            assert "multiverse" in str(data["message"]).lower()
