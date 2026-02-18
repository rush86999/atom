"""
Canvas Orchestration Routes API Tests

Tests for orchestration canvas endpoints including:
- Creating an orchestration canvas
- Adding integration nodes
- Connecting nodes
- Adding tasks
- Getting orchestration canvas
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from main_api_app import app
from api.canvas_orchestration_routes import TaskStatus


class TestCanvasOrchestrationRoutes:
    """Test orchestration canvas API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_create_orchestration_canvas_success(self, mock_service_class, client):
        """Test successful orchestration canvas creation."""
        mock_service = Mock()
        mock_service.create_orchestration_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-123",
            "title": "Project Workflow"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/create",
            json={
                "user_id": "user-123",
                "title": "Project Workflow"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "success" in data

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_create_orchestration_canvas_failure(self, mock_service_class, client):
        """Test orchestration canvas creation with service error."""
        mock_service = Mock()
        mock_service.create_orchestration_canvas.return_value = {
            "success": False,
            "error": "Invalid title"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/create",
            json={
                "user_id": "user-123",
                "title": ""
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_create_orchestration_with_tasks(self, mock_service_class, client):
        """Test creating orchestration canvas with initial tasks."""
        mock_service = Mock()
        mock_service.create_orchestration_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-tasks"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/create",
            json={
                "user_id": "user-456",
                "title": "Complex Workflow",
                "tasks": [
                    {"title": "Task 1", "status": "todo"},
                    {"title": "Task 2", "status": "in_progress"}
                ]
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_create_orchestration_with_all_params(self, mock_service_class, client):
        """Test creating orchestration canvas with all parameters."""
        mock_service = Mock()
        mock_service.create_orchestration_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-full"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/create",
            json={
                "user_id": "user-789",
                "title": "Full Orchestration",
                "canvas_id": "existing-canvas",
                "agent_id": "agent-123",
                "layout": "board",
                "tasks": [{"title": "Initial Task"}]
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_create_orchestration_calls_service(self, mock_service_class, client):
        """Test that create calls service correctly."""
        mock_service = Mock()
        mock_service.create_orchestration_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/create",
            json={
                "user_id": "user-call",
                "title": "Test Workflow"
            }
        )

        assert response.status_code == 200
        mock_service.create_orchestration_canvas.assert_called_once()

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_integration_node_success(self, mock_service_class, client):
        """Test successfully adding an integration node."""
        mock_service = Mock()
        mock_service.add_integration_node.return_value = {
            "success": True,
            "node_id": "node-123",
            "app_name": "slack"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-123/node",
            json={
                "user_id": "user-123",
                "app_name": "slack",
                "node_type": "source"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "node_id" in data or "success" in data

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_integration_node_failure(self, mock_service_class, client):
        """Test adding node with service error."""
        mock_service = Mock()
        mock_service.add_integration_node.return_value = {
            "success": False,
            "error": "Invalid app name"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-123/node",
            json={
                "user_id": "user-123",
                "app_name": "invalid_app",
                "node_type": "source"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_integration_node_with_config(self, mock_service_class, client):
        """Test adding node with configuration."""
        mock_service = Mock()
        mock_service.add_integration_node.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-123/node",
            json={
                "user_id": "user-456",
                "app_name": "salesforce",
                "node_type": "action",
                "config": {"api_key": "test-key"},
                "position": {"x": 100, "y": 200}
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_integration_node_calls_service(self, mock_service_class, client):
        """Test that add_integration_node calls service correctly."""
        mock_service = Mock()
        mock_service.add_integration_node.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-test/node",
            json={
                "user_id": "user-test",
                "app_name": "jira",
                "node_type": "action"
            }
        )

        assert response.status_code == 200
        mock_service.add_integration_node.assert_called_once_with(
            canvas_id="canvas-test",
            user_id="user-test",
            app_name="jira",
            node_type="action",
            config=None,
            position=None
        )

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_connect_nodes_success(self, mock_service_class, client):
        """Test successfully connecting nodes."""
        mock_service = Mock()
        mock_service.connect_nodes.return_value = {
            "success": True,
            "connection_id": "conn-123",
            "from_node": "node-1",
            "to_node": "node-2"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-123/connect",
            json={
                "user_id": "user-123",
                "from_node": "node-1",
                "to_node": "node-2"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "connection_id" in data or "success" in data

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_connect_nodes_failure(self, mock_service_class, client):
        """Test connecting nodes with service error."""
        mock_service = Mock()
        mock_service.connect_nodes.return_value = {
            "success": False,
            "error": "Node not found"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-123/connect",
            json={
                "user_id": "user-123",
                "from_node": "nonexistent",
                "to_node": "node-2"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_connect_nodes_with_condition(self, mock_service_class, client):
        """Test connecting nodes with condition."""
        mock_service = Mock()
        mock_service.connect_nodes.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-123/connect",
            json={
                "user_id": "user-456",
                "from_node": "node-a",
                "to_node": "node-b",
                "condition": "success"
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_connect_nodes_calls_service(self, mock_service_class, client):
        """Test that connect_nodes calls service correctly."""
        mock_service = Mock()
        mock_service.connect_nodes.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-test/connect",
            json={
                "user_id": "user-test",
                "from_node": "node-x",
                "to_node": "node-y"
            }
        )

        assert response.status_code == 200
        mock_service.connect_nodes.assert_called_once_with(
            canvas_id="canvas-test",
            user_id="user-test",
            from_node="node-x",
            to_node="node-y",
            condition=None
        )

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_task_success(self, mock_service_class, client):
        """Test successfully adding a task."""
        mock_service = Mock()
        mock_service.add_task.return_value = {
            "success": True,
            "task_id": "task-123",
            "title": "Review PR"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-123/task",
            json={
                "user_id": "user-123",
                "title": "Review PR"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data or "success" in data

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_task_failure(self, mock_service_class, client):
        """Test adding task with service error."""
        mock_service = Mock()
        mock_service.add_task.return_value = {
            "success": False,
            "error": "Invalid task data"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-123/task",
            json={
                "user_id": "user-123",
                "title": ""
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_task_with_status(self, mock_service_class, client):
        """Test adding task with different status."""
        mock_service = Mock()
        mock_service.add_task.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-123/task",
            json={
                "user_id": "user-456",
                "title": "In Progress Task",
                "status": "in_progress"
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_task_with_assignee(self, mock_service_class, client):
        """Test adding task with assignee."""
        mock_service = Mock()
        mock_service.add_task.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-123/task",
            json={
                "user_id": "user-789",
                "title": "Assigned Task",
                "assignee": "user-assignee",
                "integrations": ["jira", "slack"]
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_task_different_statuses(self, mock_service_class, client):
        """Test adding tasks with different statuses."""
        mock_service = Mock()
        mock_service.add_task.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        statuses = [
            TaskStatus.PENDING,
            TaskStatus.TODO,
            TaskStatus.IN_PROGRESS,
            TaskStatus.COMPLETED
        ]

        for status in statuses:
            response = client.post(
                "/api/canvas/orchestration/canvas-123/task",
                json={
                    "user_id": "user-status",
                    "title": f"Task with {status}",
                    "status": status
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_task_calls_service(self, mock_service_class, client):
        """Test that add_task calls service correctly."""
        mock_service = Mock()
        mock_service.add_task.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/orchestration/canvas-test/task",
            json={
                "user_id": "user-test",
                "title": "Service Test Task"
            }
        )

        assert response.status_code == 200
        mock_service.add_task.assert_called_once_with(
            canvas_id="canvas-test",
            user_id="user-test",
            title="Service Test Task",
            status=TaskStatus.TODO,
            assignee=None,
            integrations=None
        )

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_add_multiple_nodes(self, mock_service_class, client):
        """Test adding multiple integration nodes."""
        mock_service = Mock()
        mock_service.add_integration_node.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        nodes = [
            {"app_name": "slack", "node_type": "source"},
            {"app_name": "jira", "node_type": "action"},
            {"app_name": "salesforce", "node_type": "target"}
        ]

        for node in nodes:
            response = client.post(
                "/api/canvas/orchestration/canvas-multi/node",
                json={
                    "user_id": "user-multi",
                    "app_name": node["app_name"],
                    "node_type": node["node_type"]
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_connect_multiple_nodes(self, mock_service_class, client):
        """Test connecting multiple node pairs."""
        mock_service = Mock()
        mock_service.connect_nodes.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        connections = [
            {"from_node": "node-1", "to_node": "node-2"},
            {"from_node": "node-2", "to_node": "node-3"},
            {"from_node": "node-3", "to_node": "node-4"}
        ]

        for conn in connections:
            response = client.post(
                "/api/canvas/orchestration/canvas-connect/connect",
                json={
                    "user_id": "user-conn",
                    "from_node": conn["from_node"],
                    "to_node": conn["to_node"]
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_orchestration_routes.OrchestrationCanvasService')
    def test_orchestration_endpoints_return_json(self, mock_service_class, client):
        """Test that orchestration endpoints return JSON."""
        mock_service = Mock()
        mock_service.create_orchestration_canvas.return_value = {"success": True}
        mock_service.add_integration_node.return_value = {"success": True}
        mock_service.connect_nodes.return_value = {"success": True}
        mock_service.add_task.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        # Test create endpoint
        response = client.post(
            "/api/canvas/orchestration/create",
            json={"user_id": "u", "title": "T"}
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test add node endpoint
        response = client.post(
            "/api/canvas/orchestration/c/node",
            json={"user_id": "u", "app_name": "a", "node_type": "t"}
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test connect nodes endpoint
        response = client.post(
            "/api/canvas/orchestration/c/connect",
            json={"user_id": "u", "from_node": "f", "to_node": "t"}
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test add task endpoint
        response = client.post(
            "/api/canvas/orchestration/c/task",
            json={"user_id": "u", "title": "T"}
        )
        assert response.headers["content-type"].startswith("application/json")
