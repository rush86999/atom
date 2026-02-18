"""
Canvas Coding Routes API Tests

Tests for coding canvas endpoints including:
- Creating a coding canvas
- Adding a file
- Adding a diff view
- Getting a coding canvas
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from main_api_app import app


class TestCanvasCodingRoutes:
    """Test coding canvas API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_create_coding_canvas_success(self, mock_service_class, client):
        """Test successful coding canvas creation."""
        mock_service = Mock()
        mock_service.create_coding_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-123",
            "repo": "github.com/user/repo"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/coding/create",
            json={
                "user_id": "user-123",
                "repo": "github.com/user/repo",
                "branch": "main"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "success" in data

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_create_coding_canvas_failure(self, mock_service_class, client):
        """Test coding canvas creation with service error."""
        mock_service = Mock()
        mock_service.create_coding_canvas.return_value = {
            "success": False,
            "error": "Invalid repository URL"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/coding/create",
            json={
                "user_id": "user-123",
                "repo": "invalid-url",
                "branch": "main"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_create_coding_canvas_with_all_params(self, mock_service_class, client):
        """Test creating coding canvas with all parameters."""
        mock_service = Mock()
        mock_service.create_coding_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-full"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/coding/create",
            json={
                "user_id": "user-456",
                "repo": "github.com/org/project",
                "branch": "develop",
                "canvas_id": "existing-canvas",
                "agent_id": "agent-789",
                "layout": "repo_view"
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_create_coding_canvas_different_branches(self, mock_service_class, client):
        """Test creating coding canvases with different branches."""
        mock_service = Mock()
        mock_service.create_coding_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        branches = ["main", "develop", "feature/test", "hotfix/bug-123"]

        for branch in branches:
            response = client.post(
                "/api/canvas/coding/create",
                json={
                    "user_id": "user-branches",
                    "repo": "github.com/user/repo",
                    "branch": branch
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_create_coding_canvas_calls_service(self, mock_service_class, client):
        """Test that create calls service correctly."""
        mock_service = Mock()
        mock_service.create_coding_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/coding/create",
            json={
                "user_id": "user-call",
                "repo": "github.com/test/repo",
                "branch": "main"
            }
        )

        assert response.status_code == 200
        mock_service.create_coding_canvas.assert_called_once()

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_add_file_success(self, mock_service_class, client):
        """Test successfully adding a file."""
        mock_service = Mock()
        mock_service.add_file.return_value = {
            "success": True,
            "file_path": "src/main.py",
            "language": "python"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/coding/canvas-123/file",
            json={
                "user_id": "user-123",
                "path": "src/main.py",
                "content": "print('Hello, World!')",
                "language": "python"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "success" in data

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_add_file_failure(self, mock_service_class, client):
        """Test adding file with service error."""
        mock_service = Mock()
        mock_service.add_file.return_value = {
            "success": False,
            "error": "Invalid file path"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/coding/canvas-123/file",
            json={
                "user_id": "user-123",
                "path": "../../../etc/passwd",
                "content": "malicious"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_add_file_different_languages(self, mock_service_class, client):
        """Test adding files with different languages."""
        mock_service = Mock()
        mock_service.add_file.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        files = [
            {"path": "app.py", "language": "python"},
            {"path": "index.js", "language": "javascript"},
            {"path": "style.css", "language": "css"},
            {"path": "component.tsx", "language": "typescript"}
        ]

        for file_info in files:
            response = client.post(
                "/api/canvas/coding/canvas-123/file",
                json={
                    "user_id": "user-456",
                    "path": file_info["path"],
                    "content": "// code",
                    "language": file_info["language"]
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_add_file_calls_service(self, mock_service_class, client):
        """Test that add_file calls service correctly."""
        mock_service = Mock()
        mock_service.add_file.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/coding/canvas-test/file",
            json={
                "user_id": "user-test",
                "path": "test.py",
                "content": "def test(): pass"
            }
        )

        assert response.status_code == 200
        mock_service.add_file.assert_called_once_with(
            canvas_id="canvas-test",
            user_id="user-test",
            path="test.py",
            content="def test(): pass",
            language="text"
        )

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_add_diff_success(self, mock_service_class, client):
        """Test successfully adding a diff view."""
        mock_service = Mock()
        mock_service.add_diff.return_value = {
            "success": True,
            "file_path": "src/main.py",
            "changes": 10
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/coding/canvas-123/diff",
            json={
                "user_id": "user-123",
                "file_path": "src/main.py",
                "old_content": "def old(): pass",
                "new_content": "def new(): pass"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "success" in data

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_add_diff_failure(self, mock_service_class, client):
        """Test adding diff with service error."""
        mock_service = Mock()
        mock_service.add_diff.return_value = {
            "success": False,
            "error": "Cannot create diff"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/coding/canvas-123/diff",
            json={
                "user_id": "user-123",
                "file_path": "file.py",
                "old_content": "",
                "new_content": ""
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_add_diff_different_files(self, mock_service_class, client):
        """Test adding diffs for different files."""
        mock_service = Mock()
        mock_service.add_diff.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        files = ["app.py", "utils.py", "config.py"]

        for file_path in files:
            response = client.post(
                "/api/canvas/coding/canvas-123/diff",
                json={
                    "user_id": "user-789",
                    "file_path": file_path,
                    "old_content": "old",
                    "new_content": "new"
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_add_diff_calls_service(self, mock_service_class, client):
        """Test that add_diff calls service correctly."""
        mock_service = Mock()
        mock_service.add_diff.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/coding/canvas-test/diff",
            json={
                "user_id": "user-test",
                "file_path": "test.py",
                "old_content": "before",
                "new_content": "after"
            }
        )

        assert response.status_code == 200
        mock_service.add_diff.assert_called_once_with(
            canvas_id="canvas-test",
            user_id="user-test",
            file_path="test.py",
            old_content="before",
            new_content="after"
        )

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_add_multiple_files(self, mock_service_class, client):
        """Test adding multiple files to same canvas."""
        mock_service = Mock()
        mock_service.add_file.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        files = [
            {"path": "main.py", "content": "import sys"},
            {"path": "utils.py", "content": "def helper(): pass"},
            {"path": "config.py", "content": "DEBUG = True"}
        ]

        for file_info in files:
            response = client.post(
                "/api/canvas/coding/canvas-multi/file",
                json={
                    "user_id": "user-multi",
                    "path": file_info["path"],
                    "content": file_info["content"]
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_create_multiple_canvases(self, mock_service_class, client):
        """Test creating multiple coding canvases."""
        mock_service = Mock()
        mock_service.create_coding_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        repos = [
            {"repo": "github.com/user/repo1", "branch": "main"},
            {"repo": "github.com/user/repo2", "branch": "develop"},
            {"repo": "github.com/org/repo3", "branch": "feature"}
        ]

        for repo_info in repos:
            response = client.post(
                "/api/canvas/coding/create",
                json={
                    "user_id": "user-repos",
                    "repo": repo_info["repo"],
                    "branch": repo_info["branch"]
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_coding_routes.CodingCanvasService')
    def test_coding_endpoints_return_json(self, mock_service_class, client):
        """Test that coding endpoints return JSON."""
        mock_service = Mock()
        mock_service.create_coding_canvas.return_value = {"success": True}
        mock_service.add_file.return_value = {"success": True}
        mock_service.add_diff.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        # Test create endpoint
        response = client.post(
            "/api/canvas/coding/create",
            json={"user_id": "u", "repo": "r", "branch": "b"}
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test add file endpoint
        response = client.post(
            "/api/canvas/coding/c/file",
            json={"user_id": "u", "path": "p", "content": "c"}
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test add diff endpoint
        response = client.post(
            "/api/canvas/coding/c/diff",
            json={"user_id": "u", "file_path": "f", "old_content": "o", "new_content": "n"}
        )
        assert response.headers["content-type"].startswith("application/json")
