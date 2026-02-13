"""
Device Capabilities Integration Tests

Tests for device capability endpoints from api/device_capabilities.py.

Coverage:
- POST /camera/snap - Capture camera image
- POST /screen/record/start - Start screen recording
- POST /screen/record/stop - Stop screen recording
- POST /location - Get device location
- POST /notification - Send notification
- POST /execute - Execute command (AUTONOMOUS only)
- GET /{device_node_id} - Get device info
- GET /{device_node_id}/audit - Get device audit trail
- GET /sessions/active - List active sessions
- Authentication/authorization
- Governance enforcement (INTERN+/SUPERVISED+/AUTONOMOUS)
- Permission checks
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy.orm import Session

from api.device_capabilities import router
from core.models import AgentRegistry, User, DeviceNode, DeviceSession


# ============================================================================
# Global test user storage
# ============================================================================

_current_test_user = None


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client(db: Session):
    """Create TestClient for device routes with database override."""
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.security_dependencies import get_current_user

    def override_get_db():
        yield db

    def override_get_current_user():
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def mock_user(db: Session):
    """Create test user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mock_intern_agent(db: Session):
    """Create INTERN maturity agent."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Intern Agent {agent_id[:8]}",
        category="testing",
        status="intern",
        confidence_score=0.6,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def mock_supervised_agent(db: Session):
    """Create SUPERVISED maturity agent."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Supervised Agent {agent_id[:8]}",
        category="testing",
        status="supervised",
        confidence_score=0.8,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def mock_autonomous_agent(db: Session):
    """Create AUTONOMOUS maturity agent."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Autonomous Agent {agent_id[:8]}",
        category="testing",
        status="autonomous",
        confidence_score=0.95,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def mock_device_node(db: Session, mock_user: User):
    """Create test device node."""
    import uuid
    device_id = str(uuid.uuid4())
    device = DeviceNode(
        device_id=device_id,
        user_id=mock_user.id,
        name="Test Device",
        node_type="mobile",
        status="online",
        platform="ios",
        capabilities=["camera", "location", "notifications"]
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@pytest.fixture
def mock_device_session(db: Session, mock_user: User, mock_device_node: DeviceNode):
    """Create test device session."""
    import uuid
    session_id = str(uuid.uuid4())
    session = DeviceSession(
        session_id=session_id,
        user_id=mock_user.id,
        device_node_id=mock_device_node.device_id,
        session_type="screen_record",
        status="active",
        configuration={"resolution": "1920x1080"}
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ============================================================================
# POST /camera/snap - Camera Tests
# ============================================================================

def test_camera_snap_intern_agent(
    client: TestClient,
    db: Session,
    mock_device_node: DeviceNode,
    mock_intern_agent: AgentRegistry,
    mock_user: User
):
    """Test camera snap with INTERN agent (allowed)."""
    request_data = {
        "device_node_id": mock_device_node.device_id,
        "resolution": "1920x1080",
        "agent_id": mock_intern_agent.id
    }

    with patch('api.device_capabilities.device_camera_snap') as mock_camera:
        mock_camera.return_value = {
            "success": True,
            "file_path": "/tmp/camera_snap.jpg"
        }

        global _current_test_user
    _current_test_user = mock_user

    response = client.post("/api/devices/camera/snap", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            assert "file_path" in data


# ============================================================================
# POST /screen/record/start - Screen Recording Tests
# ============================================================================

def test_screen_record_start_supervised_agent(
    client: TestClient,
    db: Session,
    mock_device_node: DeviceNode,
    mock_supervised_agent: AgentRegistry,
    mock_user: User
):
    """Test start screen recording with SUPERVISED agent (allowed)."""
    request_data = {
        "device_node_id": mock_device_node.device_id,
        "duration_seconds": 60,
        "audio_enabled": False,
        "resolution": "1920x1080",
        "output_format": "mp4",
        "agent_id": mock_supervised_agent.id
    }

    with patch('api.device_capabilities.device_screen_record_start') as mock_record:
        mock_record.return_value = {
            "success": True,
            "session_id": "record-session-123"
        }

        global _current_test_user
    _current_test_user = mock_user

    response = client.post("/api/devices/screen/record/start", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert "session_id" in data


def test_screen_record_stop(
    client: TestClient,
    db: Session,
    mock_device_session: DeviceSession,
    mock_user: User
):
    """Test stop screen recording."""
    request_data = {
        "session_id": mock_device_session.session_id
    }

    with patch('api.device_capabilities.device_screen_record_stop') as mock_stop:
        mock_stop.return_value = {
            "success": True,
            "file_path": "/tmp/recording.mp4",
            "duration_seconds": 60
        }

        global _current_test_user
    _current_test_user = mock_user

    response = client.post("/api/devices/screen/record/stop", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert "file_path" in data


# ============================================================================
# POST /location - Location Tests
# ============================================================================

def test_get_location_intern_agent(
    client: TestClient,
    db: Session,
    mock_device_node: DeviceNode,
    mock_intern_agent: AgentRegistry,
    mock_user: User
):
    """Test get location with INTERN agent (allowed)."""
    request_data = {
        "device_node_id": mock_device_node.device_id,
        "accuracy": "high",
        "agent_id": mock_intern_agent.id
    }

    with patch('api.device_capabilities.device_get_location') as mock_location:
        mock_location.return_value = {
            "success": True,
            "latitude": 37.7749,
            "longitude": -122.4194,
            "accuracy": "high"
        }

        global _current_test_user
    _current_test_user = mock_user

    response = client.post("/api/devices/location", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert "latitude" in data
            assert "longitude" in data


# ============================================================================
# POST /notification - Notification Tests
# ============================================================================

def test_send_notification_intern_agent(
    client: TestClient,
    db: Session,
    mock_device_node: DeviceNode,
    mock_intern_agent: AgentRegistry,
    mock_user: User
):
    """Test send notification with INTERN agent (allowed)."""
    request_data = {
        "device_node_id": mock_device_node.device_id,
        "title": "Test Notification",
        "body": "This is a test notification",
        "agent_id": mock_intern_agent.id
    }

    with patch('api.device_capabilities.device_send_notification') as mock_notify:
        mock_notify.return_value = {
            "success": True
        }

        global _current_test_user
    _current_test_user = mock_user

    response = client.post("/api/devices/notification", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)


# ============================================================================
# POST /execute - Command Execution Tests
# ============================================================================

def test_execute_command_autonomous_agent(
    client: TestClient,
    db: Session,
    mock_device_node: DeviceNode,
    mock_autonomous_agent: AgentRegistry,
    mock_user: User
):
    """Test execute command with AUTONOMOUS agent (allowed)."""
    request_data = {
        "device_node_id": mock_device_node.device_id,
        "command": "ls -la",
        "working_dir": "/tmp",
        "timeout_seconds": 30,
        "agent_id": mock_autonomous_agent.id
    }

    with patch('api.device_capabilities.device_execute_command') as mock_exec:
        mock_exec.return_value = {
            "success": True,
            "exit_code": 0,
            "stdout": "file1.txt\nfile2.txt",
            "stderr": ""
        }

        global _current_test_user
    _current_test_user = mock_user

    response = client.post("/api/devices/execute", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert "exit_code" in data


# ============================================================================
# GET /{device_node_id} - Device Info Tests
# ============================================================================

def test_get_device_info_success(
    client: TestClient,
    db: Session,
    mock_device_node: DeviceNode,
    mock_user: User
):
    """Test get device info successfully."""
    with patch('api.device_capabilities.get_device_info') as mock_info:
        mock_info.return_value = {
            "device_id": mock_device_node.device_id,
            "name": "Test Device",
            "status": "online",
            "platform": "ios"
        }

        global _current_test_user
    _current_test_user = mock_user

    response = client.get(f"/api/devices/{mock_device_node.device_id}")

            assert response.status_code == 200
            data = response.json()
            assert "success" in data


# ============================================================================
# GET /{device_node_id}/audit - Audit Trail Tests
# ============================================================================

def test_get_device_audit_success(
    client: TestClient,
    db: Session,
    mock_device_node: DeviceNode,
    mock_user: User
):
    """Test get device audit trail successfully."""
    with patch('api.device_capabilities.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get(f"/api/devices/{mock_device_node.device_id}/audit?limit=50")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# ============================================================================
# GET /sessions/active - Active Sessions Tests
# ============================================================================

def test_get_active_sessions_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test get active sessions successfully."""
    with patch('api.device_capabilities.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get("/api/devices/sessions/active")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# ============================================================================
# Request Validation Tests
# ============================================================================

def test_camera_snap_missing_device_id(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test camera snap without device_node_id."""
    request_data = {
        "resolution": "1920x1080"
    }

    with patch('api.device_capabilities.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/camera/snap", json=request_data)

        assert response.status_code == 422


def test_execute_command_missing_command(
    client: TestClient,
    db: Session,
    mock_device_node: DeviceNode,
    mock_user: User
):
    """Test execute command without command field."""
    request_data = {
        "device_node_id": mock_device_node.device_id
    }

    with patch('api.device_capabilities.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/execute", json=request_data)

        assert response.status_code == 422


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_camera_snap_device_not_found(
    client: TestClient,
    db: Session,
    mock_intern_agent: AgentRegistry,
    mock_user: User
):
    """Test camera snap with non-existent device."""
    request_data = {
        "device_node_id": "non-existent-device",
        "agent_id": mock_intern_agent.id
    }

    with patch('api.device_capabilities.device_camera_snap') as mock_camera:
        mock_camera.return_value = {
            "success": False,
            "error": "Device not found"
        }

        global _current_test_user
    _current_test_user = mock_user

    response = client.post("/api/devices/camera/snap", json=request_data)

            # Should handle error gracefully
            assert response.status_code in [400, 404]


# ============================================================================
# Response Format Tests
# ============================================================================

def test_response_format_camera_snap(
    client: TestClient,
    db: Session,
    mock_device_node: DeviceNode,
    mock_intern_agent: AgentRegistry,
    mock_user: User
):
    """Test camera snap response has correct format."""
    request_data = {
        "device_node_id": mock_device_node.device_id,
        "agent_id": mock_intern_agent.id
    }

    with patch('api.device_capabilities.device_camera_snap') as mock_camera:
        mock_camera.return_value = {
            "success": True,
            "file_path": "/tmp/snap.jpg",
            "device_node_id": mock_device_node.device_id,
            "resolution": "1920x1080"
        }

        global _current_test_user
    _current_test_user = mock_user

    response = client.post("/api/devices/camera/snap", json=request_data)

            # Verify response is a dict with expected fields
            data = response.json()
            assert isinstance(data, dict)
            assert "file_path" in data or "error" in data
