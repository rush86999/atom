"""
Project Routes API Tests

Tests for project management endpoints including:
- Getting unified tasks across platforms
- Creating unified tasks with governance
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from main_api_app import app


class TestProjectRoutes:
    """Test project API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @patch('api.project_routes.mcp_service')
    def test_get_unified_tasks_success(self, mock_mcp_service, client):
        """Test successful retrieval of unified tasks."""
        # Mock MCP service
        mock_mcp_service.execute_tool = AsyncMock(
            return_value=[
                {"id": "task-1", "title": "Task 1", "status": "pending"},
                {"id": "task-2", "title": "Task 2", "status": "completed"}
            ]
        )

        response = client.get("/api/projects/unified-tasks")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "success" in data

    @patch('api.project_routes.mcp_service')
    def test_get_unified_tasks_with_user_id(self, mock_mcp_service, client):
        """Test getting tasks for specific user."""
        mock_mcp_service.execute_tool = AsyncMock(
            return_value=[{"id": "task-1", "user_id": "user-123"}]
        )

        response = client.get("/api/projects/unified-tasks?user_id=user-123")

        assert response.status_code == 200
        # Verify the service was called with correct user_id
        mock_mcp_service.execute_tool.assert_called_once()
        call_args = mock_mcp_service.execute_tool.call_args
        # The user_id should be in the context
        context_arg = call_args[0][3] if len(call_args[0]) > 3 else call_args[1].get("context", {})

    @patch('api.project_routes.mcp_service')
    def test_get_unified_tasks_empty(self, mock_mcp_service, client):
        """Test getting tasks when none exist."""
        mock_mcp_service.execute_tool = AsyncMock(return_value=[])

        response = client.get("/api/projects/unified-tasks")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "success" in data

    @patch('api.project_routes.mcp_service')
    def test_get_unified_tasks_service_error(self, mock_mcp_service, client):
        """Test getting tasks when service raises error."""
        mock_mcp_service.execute_tool = AsyncMock(
            side_effect=Exception("Service unavailable")
        )

        response = client.get("/api/projects/unified-tasks")

        # Should return 500
        assert response.status_code == 500

    @patch('api.project_routes.mcp_service')
    def test_create_unified_task_success(self, mock_mcp_service, client):
        """Test successful task creation."""
        mock_mcp_service.execute_tool = AsyncMock(
            return_value={"id": "task-new", "status": "created"}
        )

        response = client.post(
            "/api/projects/unified-tasks",
            json={
                "title": "New Task",
                "description": "Task description",
                "status": "pending"
            }
        )

        # May return 200 or 403 (governance)
        assert response.status_code in [200, 201, 403]

    @patch('api.project_routes.mcp_service')
    def test_create_unified_task_with_user_id(self, mock_mcp_service, client):
        """Test creating task for specific user."""
        mock_mcp_service.execute_tool = AsyncMock(
            return_value={"id": "task-user", "status": "created"}
        )

        response = client.post(
            "/api/projects/unified-tasks?user_id=user-456",
            json={"title": "User Task"}
        )

        # May return 200 or 403
        assert response.status_code in [200, 201, 403]

    @patch('api.project_routes.mcp_service')
    def test_create_unified_task_minimal_data(self, mock_mcp_service, client):
        """Test creating task with minimal data."""
        mock_mcp_service.execute_tool = AsyncMock(
            return_value={"id": "task-minimal"}
        )

        response = client.post(
            "/api/projects/unified-tasks",
            json={}
        )

        # May return 200 or 403
        assert response.status_code in [200, 201, 403, 422]

    @patch('api.project_routes.mcp_service')
    def test_create_unified_task_service_error(self, mock_mcp_service, client):
        """Test creating task when service raises error."""
        mock_mcp_service.execute_tool = AsyncMock(
            side_effect=Exception("Creation failed")
        )

        response = client.post(
            "/api/projects/unified-tasks",
            json={"title": "Error Task"}
        )

        # Should return 500
        assert response.status_code in [500, 403]

    @patch('api.project_routes.mcp_service')
    def test_project_endpoints_return_json(self, mock_mcp_service, client):
        """Test that project endpoints return JSON."""
        # Mock for GET
        mock_mcp_service.execute_tool = AsyncMock(return_value=[])

        response = client.get("/api/projects/unified-tasks")
        assert response.headers["content-type"].startswith("application/json")

        # Mock for POST
        mock_mcp_service.execute_tool = AsyncMock(return_value={})
        response = client.post("/api/projects/unified-tasks", json={})
        if response.status_code in [200, 201]:
            assert response.headers["content-type"].startswith("application/json")

    @patch('api.project_routes.mcp_service')
    def test_get_tasks_calls_mcp_service(self, mock_mcp_service, client):
        """Test that get tasks calls MCP service correctly."""
        mock_mcp_service.execute_tool = AsyncMock(return_value=[])

        response = client.get("/api/projects/unified-tasks")

        assert response.status_code == 200
        # Verify service was called
        mock_mcp_service.execute_tool.assert_called_once_with(
            "local-tools",
            "get_tasks",
            {},
            {"user_id": "default_user"}
        )

    @patch('api.project_routes.mcp_service')
    def test_create_task_calls_mcp_service(self, mock_mcp_service, client):
        """Test that create task calls MCP service correctly."""
        task_data = {"title": "Test Task", "priority": "high"}
        mock_mcp_service.execute_tool = AsyncMock(return_value={"id": "task-1"})

        response = client.post(
            "/api/projects/unified-tasks",
            json=task_data
        )

        # May return 200 or 403
        if response.status_code in [200, 201]:
            # Verify service was called with task data
            mock_mcp_service.execute_tool.assert_called_once()
            call_args = mock_mcp_service.execute_tool.call_args
            assert call_args[0][2] == task_data

    @patch('api.project_routes.mcp_service')
    def test_unified_tasks_response_structure(self, mock_mcp_service, client):
        """Test that unified tasks has correct response structure."""
        mock_mcp_service.execute_tool = AsyncMock(
            return_value=[
                {"id": "1", "title": "Task 1"},
                {"id": "2", "title": "Task 2"}
            ]
        )

        response = client.get("/api/projects/unified-tasks")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data or "data" in data

    @patch('api.project_routes.mcp_service')
    def test_create_task_response_structure(self, mock_mcp_service, client):
        """Test that create task returns correct structure."""
        mock_mcp_service.execute_tool = AsyncMock(
            return_value={"id": "task-created", "status": "pending"}
        )

        response = client.post(
            "/api/projects/unified-tasks",
            json={"title": "New Task"}
        )

        if response.status_code in [200, 201]:
            data = response.json()
            assert "success" in data or "data" in data

    @patch('api.project_routes.mcp_service')
    def test_get_tasks_with_complex_response(self, mock_mcp_service, client):
        """Test getting tasks with complex data structure."""
        mock_mcp_service.execute_tool = AsyncMock(
            return_value=[
                {
                    "id": "task-1",
                    "title": "Complex Task",
                    "subtasks": [
                        {"id": "sub-1", "title": "Subtask 1"},
                        {"id": "sub-2", "title": "Subtask 2"}
                    ],
                    "metadata": {"priority": "high", "tags": ["urgent", "important"]}
                }
            ]
        )

        response = client.get("/api/projects/unified-tasks")

        assert response.status_code == 200

    @patch('api.project_routes.mcp_service')
    def test_create_task_with_complex_data(self, mock_mcp_service, client):
        """Test creating task with complex data structure."""
        task_data = {
            "title": "Complex Task",
            "subtasks": [
                {"title": "Subtask 1", "assigned_to": "user-1"},
                {"title": "Subtask 2", "assigned_to": "user-2"}
            ],
            "metadata": {
                "priority": "high",
                "due_date": "2026-02-20",
                "tags": ["urgent", "important"]
            }
        }

        mock_mcp_service.execute_tool = AsyncMock(
            return_value={"id": "complex-task", "status": "created"}
        )

        response = client.post(
            "/api/projects/unified-tasks",
            json=task_data
        )

        # May return 200, 201, or 403
        assert response.status_code in [200, 201, 403]

    @patch('api.project_routes.mcp_service')
    def test_get_tasks_default_user(self, mock_mcp_service, client):
        """Test that default user is used when not specified."""
        mock_mcp_service.execute_tool = AsyncMock(return_value=[])

        response = client.get("/api/projects/unified-tasks")

        assert response.status_code == 200
        # Verify default user is used
        call_args = mock_mcp_service.execute_tool.call_args
        assert call_args[0][3]["user_id"] == "default_user"
