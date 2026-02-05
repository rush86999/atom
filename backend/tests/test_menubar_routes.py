"""
Menu Bar Companion API Tests

Tests for menu bar companion app endpoints:
- Authentication
- Connection status
- Recent items (agents, canvases)
- Quick chat
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch

from core.models import (
    User,
    AgentRegistry,
    AgentExecution,
    CanvasAudit,
    DeviceNode,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def menubar_user(db_session: Session):
    """Create a test user for menu bar tests."""
    user = User(
        email="menubar@test.com",
        first_name="Menu",
        last_name="Bar User",
        password_hash="$2b$12$test_hashed_password",
        role="MEMBER"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def menubar_agents(db_session: Session, menubar_user):
    """Create test agents for menu bar."""
    agents = []

    # Create agents with different maturity levels
    for i, maturity in enumerate(["AUTONOMOUS", "SUPERVISED", "INTERN", "STUDENT"]):
        agent = AgentRegistry(
            name=f"Test Agent {maturity}",
            status=maturity,
            description=f"Test agent for {maturity} level",
            category="Testing",
            module_path="test.agents",
            class_name=f"TestAgent{maturity}",
            version="1.0.0",
            configuration={"capabilities": ["chat", "canvas"]},
            user_id=str(menubar_user.id),
            created_at=datetime.utcnow() - timedelta(days=i),
        )
        db_session.add(agent)
        agents.append(agent)

    db_session.commit()
    for agent in agents:
        db_session.refresh(agent)
    return agents


@pytest.fixture
def menubar_executions(db_session: Session, menubar_agents, menubar_user):
    """Create test agent executions."""
    executions = []

    for i, agent in enumerate(menubar_agents[:3]):
        # Create multiple executions for each agent
        for j in range(3):
            execution = AgentExecution(
                agent_id=str(agent.id),
                workspace_id="default",
                triggered_by="manual",
                status="completed",
                started_at=datetime.utcnow() - timedelta(days=i, hours=j),
                completed_at=datetime.utcnow() - timedelta(days=i, hours=j) + timedelta(minutes=5),
                duration_seconds=300,
            )
            db_session.add(execution)
            executions.append(execution)

    db_session.commit()
    return executions


@pytest.fixture
def menubar_canvases(db_session: Session, menubar_agents, menubar_user):
    """Create test canvas audits."""
    canvases = []

    for i, agent in enumerate(menubar_agents[:2]):
        canvas_types = ["sheets", "charts", "forms", "docs"]
        canvas = CanvasAudit(
            agent_id=str(agent.id),
            user_id=str(menubar_user.id),
            session_id=f"session_{i}",
            canvas_type=canvas_types[i % len(canvas_types)],
            component_type="chart",
            action="present",
            audit_metadata={"title": f"Test Canvas {i}"},
            created_at=datetime.utcnow() - timedelta(hours=i),
        )
        db_session.add(canvas)
        canvases.append(canvas)

    db_session.commit()
    for canvas in canvases:
        db_session.refresh(canvas)
    return canvases


# ============================================================================
# Authentication Tests
# ============================================================================

class TestMenuBarAuthentication:
    """Tests for menu bar authentication endpoints."""

    @patch("api.menubar_routes.verify_password")
    def test_menubar_login_success(self, mock_verify, client: TestClient, menubar_user):
        """Test successful menu bar login."""
        # Mock password verification to return True
        mock_verify.return_value = True

        response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
                "platform": "darwin",
            }
        )

        # Debug: print response if not 200
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data
        assert "device_id" in data
        assert data["user"]["email"] == "menubar@test.com"

    @patch("api.menubar_routes.verify_password")
    def test_menubar_login_invalid_credentials(self, mock_verify, client: TestClient):
        """Test login with invalid credentials."""
        # Mock password verification to return False
        mock_verify.return_value = False

        response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "invalid@test.com",
                "password": "wrong_password",
                "device_name": "MenuBar",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    @patch("api.menubar_routes.verify_password")
    def test_menubar_login_creates_device(self, mock_verify, client: TestClient, menubar_user, db_session: Session):
        """Test that login creates a DeviceNode entry."""
        mock_verify.return_value = True

        response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
                "platform": "darwin",
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify device was created
        device = db_session.query(DeviceNode).filter(
            DeviceNode.device_id == data["device_id"]
        ).first()

        assert device is not None
        assert device.app_type == "menubar"
        assert device.status == "online"
        assert "quick_chat" in device.capabilities

    @patch("api.menubar_routes.verify_password")
    def test_menubar_login_updates_existing_device(self, mock_verify, client: TestClient, menubar_user, db_session: Session):
        """Test that login updates existing device."""
        mock_verify.return_value = True

        # First login
        response1 = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
                "platform": "darwin",
                "app_version": "0.1.0",
            }
        )

        assert response1.status_code == 200
        device_id = response1.json()["device_id"]

        # Second login with updated info
        response2 = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar Updated",
                "platform": "darwin",
                "app_version": "0.2.0",
            }
        )

        assert response2.status_code == 200

        # Verify device was updated
        device = db_session.query(DeviceNode).filter(
            DeviceNode.device_id == device_id
        ).first()

        assert device is not None
        assert device.name == "MenuBar Updated"
        assert device.app_version == "0.2.0"


# ============================================================================
# Connection Status Tests
# ============================================================================

class TestMenuBarConnectionStatus:
    """Tests for connection status endpoint."""

    @patch("api.menubar_routes.verify_password")
    def test_get_connection_status_authenticated(self, mock_verify, client: TestClient, menubar_user):
        """Test getting connection status when authenticated."""
        mock_verify.return_value = True

        # Login first
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]

        # Get connection status
        response = client.get(
            "/api/menubar/status",
            headers={"Authorization": f"Bearer {token}", "X-Device-ID": device_id, "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["device_id"] == device_id
        assert "server_time" in data

    def test_get_connection_status_unauthenticated(self, client: TestClient):
        """Test getting connection status without authentication."""
        response = client.get("/api/menubar/status", headers={"Host": "localhost"})

        # Should return 401 or similar
        assert response.status_code == 401

    @patch("api.menubar_routes.verify_password")
    def test_connection_status_updates_last_seen(self, mock_verify, client: TestClient, menubar_user, db_session: Session):
        """Test that status check updates last_seen timestamp."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]

        # Get initial last_seen
        device = db_session.query(DeviceNode).filter(
            DeviceNode.device_id == device_id
        ).first()
        initial_last_seen = device.last_seen

        # Wait a bit and check status
        import time
        time.sleep(0.1)

        response = client.get(
            "/api/menubar/status",
            headers={"Authorization": f"Bearer {token}", "X-Device-ID": device_id, "Host": "localhost"}
        )

        assert response.status_code == 200

        # Verify last_seen was updated
        db_session.refresh(device)
        assert device.last_seen > initial_last_seen


# ============================================================================
# Recent Items Tests
# ============================================================================

class TestMenuBarRecentItems:
    """Tests for recent items endpoints."""

    @patch("api.menubar_routes.verify_password")
    def test_get_recent_agents(self, mock_verify, client: TestClient, menubar_user, menubar_executions):
        """Test getting recent agents."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Get recent agents
        response = client.get(
            "/api/menubar/recent/agents",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify structure
        agent = data[0]
        assert "id" in agent
        assert "name" in agent
        assert "maturity_level" in agent
        assert "execution_count" in agent

    @patch("api.menubar_routes.verify_password")
    def test_get_recent_canvases(self, mock_verify, client: TestClient, menubar_user, menubar_canvases):
        """Test getting recent canvases."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Get recent canvases
        response = client.get(
            "/api/menubar/recent/canvases",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify structure
        canvas = data[0]
        assert "id" in canvas
        assert "canvas_type" in canvas
        assert "created_at" in canvas

    @patch("api.menubar_routes.verify_password")
    def test_get_recent_items_combined(self, mock_verify, client: TestClient, menubar_user, menubar_executions, menubar_canvases):
        """Test getting both agents and canvases in one request."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Get all recent items
        response = client.get(
            "/api/menubar/recent",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "canvases" in data
        assert len(data["agents"]) > 0
        assert len(data["canvases"]) > 0

    @patch("api.menubar_routes.verify_password")
    def test_recent_agents_limit(self, mock_verify, client: TestClient, menubar_user):
        """Test limiting the number of recent agents."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Request only 2 agents
        response = client.get(
            "/api/menubar/recent/agents?limit=2",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2


# ============================================================================
# Quick Chat Tests
# ============================================================================

class TestMenuBarQuickChat:
    """Tests for quick chat endpoint."""

    @patch("api.menubar_routes.verify_password")
    def test_quick_chat_with_agent(self, mock_verify, client: TestClient, menubar_user, menubar_agents):
        """Test sending a quick chat message with specific agent."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]
        agent_id = str(menubar_agents[0].id)

        # Send quick chat
        response = client.post(
            "/api/menubar/quick/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Device-ID": device_id,
                "Host": "localhost",
            },
            json={
                "message": "Hello, agent!",
                "agent_id": agent_id,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "response" in data
        assert "execution_id" in data
        assert data["agent_id"] == agent_id

    @patch("api.menubar_routes.verify_password")
    def test_quick_chat_auto_select_agent(self, mock_verify, client: TestClient, menubar_user, menubar_agents):
        """Test quick chat without specifying an agent (auto-select)."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]

        # Send quick chat without agent_id
        response = client.post(
            "/api/menubar/quick/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Device-ID": device_id,
                "Host": "localhost",
            },
            json={
                "message": "Hello!",
            }
        )

        assert response.status_code == 200
        data = response.json()
        # Should auto-select an autonomous agent or fall back
        assert data["success"] is True or data["error"] is not None

    @patch("api.menubar_routes.verify_password")
    def test_quick_chat_updates_last_command_at(self, mock_verify, client: TestClient, menubar_user, menubar_agents, db_session: Session):
        """Test that quick chat updates last_command_at timestamp."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]
        agent_id = str(menubar_agents[0].id)

        # Send quick chat
        client.post(
            "/api/menubar/quick/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Device-ID": device_id,
                "Host": "localhost",
            },
            json={
                "message": "Test message",
                "agent_id": agent_id,
            }
        )

        # Verify last_command_at was updated
        device = db_session.query(DeviceNode).filter(
            DeviceNode.device_id == device_id
        ).first()

        assert device is not None
        assert device.last_command_at is not None


# ============================================================================
# Health Check Tests
# ============================================================================

class TestMenuBarHealth:
    """Tests for health check endpoint."""

    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/api/menubar/health", headers={"Host": "localhost"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


# ============================================================================
# Performance Tests
# ============================================================================

class TestMenuBarPerformance:
    """Performance tests for menu bar endpoints."""

    @patch("api.menubar_routes.verify_password")
    def test_login_performance(self, mock_verify, client: TestClient, menubar_user):
        """Test login performance."""
        mock_verify.return_value = True

        import time

        start = time.time()
        response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )
        end = time.time()

        assert response.status_code == 200
        # Should complete in less than 1 second
        assert (end - start) < 1.0

    @patch("api.menubar_routes.verify_password")
    def test_recent_items_performance(self, mock_verify, client: TestClient, menubar_user, menubar_executions, menubar_canvases):
        """Test recent items retrieval performance."""
        mock_verify.return_value = True

        import time

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        start = time.time()
        response = client.get(
            "/api/menubar/recent",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )
        end = time.time()

        assert response.status_code == 200
        # Should complete in less than 500ms
        assert (end - start) < 0.5

    @patch("api.menubar_routes.verify_password")
    def test_quick_chat_performance(self, mock_verify, client: TestClient, menubar_user, menubar_agents):
        """Test quick chat performance."""
        mock_verify.return_value = True

        import time

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]
        agent_id = str(menubar_agents[0].id)

        start = time.time()
        response = client.post(
            "/api/menubar/quick/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Device-ID": device_id,
                "Host": "localhost",
            },
            json={
                "message": "Test message",
                "agent_id": agent_id,
            }
        )
        end = time.time()

        assert response.status_code == 200
        # Should complete in less than 2 seconds
        assert (end - start) < 2.0


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestMenuBarEdgeCases:
    """Tests for edge cases and error handling."""

    @patch("api.menubar_routes.verify_password")
    def test_empty_recent_items(self, mock_verify, client: TestClient, menubar_user):
        """Test handling when no recent items exist."""
        mock_verify.return_value = True

        # Login (without creating any executions or canvases)
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Get recent items
        response = client.get(
            "/api/menubar/recent",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        # Should return empty lists, not error
        assert "agents" in data
        assert "canvases" in data

    def test_invalid_token(self, client: TestClient):
        """Test using invalid token."""
        response = client.get(
            "/api/menubar/recent",
            headers={"Authorization": "Bearer invalid_token", "Host": "localhost"}
        )

        assert response.status_code == 401

    @patch("api.menubar_routes.verify_password")
    def test_missing_device_id_header(self, mock_verify, client: TestClient, menubar_user):
        """Test quick chat without X-Device-ID header."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Send quick chat without device ID
        response = client.post(
            "/api/menubar/quick/chat",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"},
            json={
                "message": "Test",
            }
        )

        # Should still work (device_id is optional)
        assert response.status_code == 200
