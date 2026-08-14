"""
Canvas Terminal Routes API Tests

Tests for terminal canvas endpoints including:
- Creating a terminal canvas
- Adding command output
- Getting a terminal canvas

Endpoints require authentication (core.auth.get_current_user), and output/read
access is gated by canvas ownership (R66), so these tests authenticate as a
real user and seed terminal CanvasAudit rows owned by that user.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from api.canvas_terminal_routes import router
from core.models import CanvasAudit, User


_current_test_user = None


@pytest.fixture
def client(db: Session):
    """Create test client with auth/db overrides."""
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.auth import get_current_user
    from core.database import get_db

    def override_get_db():
        yield db

    def override_get_current_user():
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def mock_user(db: Session):
    """Create test user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"terminal-{user_id}@example.com",
        first_name="Terminal",
        last_name="User",
        role="member",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_client(client, mock_user):
    """Client authenticated as mock_user."""
    global _current_test_user
    _current_test_user = mock_user
    return client


def _seed_terminal_canvas(db: Session, canvas_id: str, user_id: str):
    """Seed a terminal canvas audit row owned by user_id."""
    import uuid
    audit = CanvasAudit(
        id=str(uuid.uuid4()),
        canvas_id=canvas_id,
        tenant_id="default",
        canvas_type="terminal",
        action_type="create",
        user_id=user_id,
    )
    db.add(audit)
    db.commit()
    return audit


class TestCanvasTerminalRoutes:
    """Test terminal canvas API endpoints."""

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_create_terminal_canvas_success(self, mock_service_class, auth_client):
        """Test successful terminal canvas creation."""
        mock_service = Mock()
        mock_service.create_terminal_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-123",
            "command": "ls -la"
        }
        mock_service_class.return_value = mock_service

        response = auth_client.post(
            "/api/canvas/terminal/create",
            json={
                "user_id": "user-123",
                "command": "ls -la",
                "working_dir": "/home/user"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "success" in data

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_create_terminal_canvas_failure(self, mock_service_class, auth_client):
        """Test terminal canvas creation with service error."""
        mock_service = Mock()
        mock_service.create_terminal_canvas.return_value = {
            "success": False,
            "error": "Database connection failed"
        }
        mock_service_class.return_value = mock_service

        response = auth_client.post(
            "/api/canvas/terminal/create",
            json={
                "user_id": "user-123",
                "command": "invalid-command"
            }
        )

        assert response.status_code == 400
        data = response.json()
        # Error responses are nested under 'detail' key
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_create_terminal_canvas_with_all_params(self, mock_service_class, auth_client):
        """Test creating terminal canvas with all parameters."""
        mock_service = Mock()
        mock_service.create_terminal_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-full"
        }
        mock_service_class.return_value = mock_service

        response = auth_client.post(
            "/api/canvas/terminal/create",
            json={
                "user_id": "user-456",
                "command": "npm install",
                "canvas_id": "existing-canvas",
                "agent_id": "agent-789",
                "working_dir": "/project"
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_create_terminal_canvas_calls_service(self, mock_service_class, auth_client, mock_user):
        """Test that create calls service correctly."""
        mock_service = Mock()
        mock_service.create_terminal_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = auth_client.post(
            "/api/canvas/terminal/create",
            json={
                "user_id": "user-call",
                "command": "echo test"
            }
        )

        assert response.status_code == 200
        mock_service.create_terminal_canvas.assert_called_once_with(
            user_id=mock_user.id,
            command="echo test",
            canvas_id=None,
            agent_id=None,
            working_dir="."
        )

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_add_output_success(self, mock_service_class, auth_client, db, mock_user):
        """Test successfully adding command output."""
        _seed_terminal_canvas(db, "canvas-123", mock_user.id)

        mock_service = Mock()
        mock_service.add_output.return_value = {
            "success": True,
            "canvas_id": "canvas-123"
        }
        mock_service_class.return_value = mock_service

        response = auth_client.post(
            "/api/canvas/terminal/canvas-123/output",
            json={
                "user_id": "user-123",
                "command": "ls",
                "output": "file1.txt\nfile2.txt",
                "exit_code": 0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "success" in data

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_add_output_failure(self, mock_service_class, auth_client, db, mock_user):
        """Test adding output with service error."""
        _seed_terminal_canvas(db, "invalid-canvas", mock_user.id)

        mock_service = Mock()
        mock_service.add_output.return_value = {
            "success": False,
            "error": "Canvas not found"
        }
        mock_service_class.return_value = mock_service

        response = auth_client.post(
            "/api/canvas/terminal/invalid-canvas/output",
            json={
                "user_id": "user-123",
                "command": "ls",
                "output": ""
            }
        )

        assert response.status_code == 400
        data = response.json()
        # Error responses are nested under 'detail' key
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_add_output_with_nonzero_exit(self, mock_service_class, auth_client, db, mock_user):
        """Test adding output with non-zero exit code."""
        _seed_terminal_canvas(db, "canvas-123", mock_user.id)

        mock_service = Mock()
        mock_service.add_output.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = auth_client.post(
            "/api/canvas/terminal/canvas-123/output",
            json={
                "user_id": "user-123",
                "command": "false",
                "output": "",
                "exit_code": 1
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_add_output_calls_service(self, mock_service_class, auth_client, db, mock_user):
        """Test that add_output calls service correctly."""
        _seed_terminal_canvas(db, "canvas-test", mock_user.id)

        mock_service = Mock()
        mock_service.add_output.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = auth_client.post(
            "/api/canvas/terminal/canvas-test/output",
            json={
                "user_id": "user-test",
                "command": "echo test",
                "output": "test"
            }
        )

        assert response.status_code == 200
        # The route attributes output to the authenticated user, not the
        # request-supplied user_id.
        mock_service.add_output.assert_called_once_with(
            canvas_id="canvas-test",
            user_id=mock_user.id,
            command="echo test",
            output="test",
            exit_code=0
        )

    def test_get_terminal_canvas_not_found(self, auth_client):
        """Test getting a non-existent terminal canvas."""
        response = auth_client.get("/api/canvas/terminal/nonexistent")

        assert response.status_code == 404

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_terminal_endpoints_return_json(self, mock_service_class, auth_client, db, mock_user):
        """Test that terminal endpoints return JSON."""
        _seed_terminal_canvas(db, "c", mock_user.id)

        mock_service = Mock()
        mock_service.create_terminal_canvas.return_value = {"success": True}
        mock_service.add_output.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        # Test create endpoint
        response = auth_client.post(
            "/api/canvas/terminal/create",
            json={"user_id": "u", "command": "test"}
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test add output endpoint
        response = auth_client.post(
            "/api/canvas/terminal/c/output",
            json={"user_id": "u", "command": "test", "output": "test"}
        )
        assert response.headers["content-type"].startswith("application/json")

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_create_multiple_terminals(self, mock_service_class, auth_client):
        """Test creating multiple terminal canvases."""
        mock_service = Mock()
        mock_service.create_terminal_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        commands = ["ls", "pwd", "echo test"]

        for cmd in commands:
            response = auth_client.post(
                "/api/canvas/terminal/create",
                json={
                    "user_id": "user-multi",
                    "command": cmd
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_add_output_multiple_times(self, mock_service_class, auth_client, db, mock_user):
        """Test adding output multiple times."""
        _seed_terminal_canvas(db, "canvas-multi", mock_user.id)

        mock_service = Mock()
        mock_service.add_output.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        for i in range(3):
            response = auth_client.post(
                "/api/canvas/terminal/canvas-multi/output",
                json={
                    "user_id": "user-123",
                    "command": f"echo {i}",
                    "output": f"{i}"
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_terminal_routes.TerminalCanvasService')
    def test_create_terminal_with_various_commands(self, mock_service_class, auth_client):
        """Test creating terminals with various command types."""
        mock_service = Mock()
        mock_service.create_terminal_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        commands = [
            "ls -la",
            "cd /home/user",
            "npm install",
            "git status",
            "docker ps"
        ]

        for cmd in commands:
            response = auth_client.post(
                "/api/canvas/terminal/create",
                json={
                    "user_id": "user-cmd",
                    "command": cmd
                }
            )
            assert response.status_code == 200
