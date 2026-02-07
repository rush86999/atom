"""
Device WebSocket Integration Tests

Tests the real WebSocket communication between backend and mobile devices.
These tests require WebSocket server to be running.
"""

import asyncio
import json
import uuid
from datetime import datetime
import pytest
from httpx import AsyncClient
from main import app
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import DeviceAudit, DeviceNode, User


# Test fixtures
@pytest.fixture
async def test_user(db: Session):
    """Create a test user."""
    user = User(
        id=str(uuid.uuid4()),
        email="device-test@example.com",
        username="devicetest",
        hashed_password="hashed_password_here",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
async def test_device_node(db: Session, test_user: User):
    """Create a test device node."""
    device = DeviceNode(
        id=str(uuid.uuid4()),
        device_id="test_mobile_device_001",
        user_id=test_user.id,
        name="Test Mobile Device",
        node_type="mobile",
        status="offline",
        platform="ios",
        platform_version="16.0",
        architecture="arm64",
        capabilities=["camera", "location", "notification"],
        last_seen=datetime.now(),
    )
    db.add(device)
    db.commit()
    return device


@pytest.fixture
def auth_token(test_user: User):
    """Generate auth token for test user."""
    from core.security_dependencies import create_access_token
    return create_access_token(data={"sub": test_user.id})


# ============================================================================
# Connection Tests
# ============================================================================

@pytest.mark.asyncio
async def test_device_websocket_connect(test_device_node: DeviceNode, auth_token: str):
    """Test device can connect via WebSocket."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect(
            f"/api/devices/ws?token={auth_token}"
        ) as websocket:
            # Send registration message
            register_msg = {
                "type": "register",
                "device_node_id": test_device_node.device_id,
                "device_info": {
                    "name": "Test Mobile Device",
                    "node_type": "mobile",
                    "platform": "ios",
                    "platform_version": "16.0",
                    "capabilities": ["camera", "location", "notification"],
                }
            }
            await websocket.send_json(register_msg)

            # Receive registration confirmation
            response = await websocket.receive_json()
            assert response["type"] == "registered"
            assert response["device_node_id"] == test_device_node.device_id


@pytest.mark.asyncio
async def test_device_websocket_invalid_token(test_device_node: DeviceNode):
    """Test WebSocket rejects invalid token."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        try:
            async with client.websocket_connect(
                "/api/devices/ws?token=invalid_token"
            ) as websocket:
                assert False, "Should have raised exception"
        except Exception as e:
            # Expected - invalid token should be rejected
            assert "1008" in str(e) or "Invalid token" in str(e)


# ============================================================================
# Command Tests (Mock Device)
# ============================================================================

@pytest.mark.asyncio
async def test_device_camera_snap_command(
    db: Session,
    test_user: User,
    test_device_node: DeviceNode,
    auth_token: str
):
    """Test camera snap command via WebSocket."""
    from api.device_websocket import get_device_connection_manager
    from tools.device_tool import device_camera_snap

    # Create a mock WebSocket connection
    manager = get_device_connection_manager()

    # Mock WebSocket class
    class MockWebSocket:
        def __init__(self):
            self.messages = []
            self.closed = False

        async def send_json(self, message):
            self.messages.append(message)

        async def receive_json(self, timeout=None):
            # Wait a bit then return a mock response
            await asyncio.sleep(0.1)
            return {
                "type": "result",
                "command_id": self.messages[-1]["command_id"] if self.messages else "unknown",
                "success": True,
                "data": {
                    "base64_data": "mock_base64_image_data"
                },
                "file_path": "/tmp/camera_test.jpg"
            }

        async def close(self, code=None, reason=None):
            self.closed = True

    # Register mock connection
    mock_ws = MockWebSocket()
    await manager.connect(
        mock_ws,
        test_device_node.device_id,
        test_user.id,
        {"name": "Test Device", "capabilities": ["camera"]}
    )

    try:
        # Test camera snap via tool
        result = await device_camera_snap(
            db=db,
            user_id=test_user.id,
            device_node_id=test_device_node.device_id,
            agent_id=None,
            camera_id="default",
            resolution="1920x1080"
        )

        assert result["success"] is True
        assert result["camera_id"] == "default"

        # Check audit entry was created
        audit = db.query(DeviceAudit).filter(
            DeviceAudit.action_type == "camera_snap"
        ).first()
        assert audit is not None
        assert audit.success is True

    finally:
        manager.disconnect(test_device_node.device_id, test_user.id)


@pytest.mark.asyncio
async def test_device_get_location_command(
    db: Session,
    test_user: User,
    test_device_node: DeviceNode,
    auth_token: str
):
    """Test get location command via WebSocket."""
    from api.device_websocket import get_device_connection_manager
    from tools.device_tool import device_get_location

    manager = get_device_connection_manager()

    # Mock WebSocket
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send_json(self, message):
            self.messages.append(message)

        async def receive_json(self, timeout=None):
            await asyncio.sleep(0.1)
            return {
                "type": "result",
                "command_id": self.messages[-1]["command_id"] if self.messages else "unknown",
                "success": True,
                "data": {
                    "latitude": 37.7749,
                    "longitude": -122.4194,
                    "altitude": None,
                    "timestamp": datetime.now().isoformat()
                }
            }

    mock_ws = MockWebSocket()
    await manager.connect(
        mock_ws,
        test_device_node.device_id,
        test_user.id,
        {"name": "Test Device", "capabilities": ["location"]}
    )

    try:
        result = await device_get_location(
            db=db,
            user_id=test_user.id,
            device_node_id=test_device_node.device_id,
            agent_id=None,
            accuracy="high"
        )

        assert result["success"] is True
        assert result["latitude"] == 37.7749
        assert result["longitude"] == -122.4194

        # Check audit entry
        audit = db.query(DeviceAudit).filter(
            DeviceAudit.action_type == "get_location"
        ).first()
        assert audit is not None
        assert audit.success is True

    finally:
        manager.disconnect(test_device_node.device_id, test_user.id)


@pytest.mark.asyncio
async def test_device_send_notification_command(
    db: Session,
    test_user: User,
    test_device_node: DeviceNode,
    auth_token: str
):
    """Test send notification command via WebSocket."""
    from api.device_websocket import get_device_connection_manager
    from tools.device_tool import device_send_notification

    manager = get_device_connection_manager()

    # Mock WebSocket
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send_json(self, message):
            self.messages.append(message)

        async def receive_json(self, timeout=None):
            await asyncio.sleep(0.1)
            return {
                "type": "result",
                "command_id": self.messages[-1]["command_id"] if self.messages else "unknown",
                "success": True
            }

    mock_ws = MockWebSocket()
    await manager.connect(
        mock_ws,
        test_device_node.device_id,
        test_user.id,
        {"name": "Test Device", "capabilities": ["notification"]}
    )

    try:
        result = await device_send_notification(
            db=db,
            user_id=test_user.id,
            device_node_id=test_device_node.device_id,
            title="Test Notification",
            body="Test notification body",
            agent_id=None
        )

        assert result["success"] is True
        assert result["title"] == "Test Notification"

        # Check audit entry
        audit = db.query(DeviceAudit).filter(
            DeviceAudit.action_type == "send_notification"
        ).first()
        assert audit is not None
        assert audit.success is True

    finally:
        manager.disconnect(test_device_node.device_id, test_user.id)


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_device_not_connected_error(db: Session, test_user: User, test_device_node: DeviceNode):
    """Test error when device is not connected."""
    # Make sure device is not connected
    from api.device_websocket import get_device_connection_manager
    from tools.device_tool import device_camera_snap
    manager = get_device_connection_manager()
    assert not manager.is_device_connected(test_device_node.device_id)

    # Try to use camera - should fail
    result = await device_camera_snap(
        db=db,
        user_id=test_user.id,
        device_node_id=test_device_node.device_id,
        agent_id=None
    )

    assert result["success"] is False
    assert "not connected" in result["error"].lower()


@pytest.mark.asyncio
async def test_device_command_failure(db: Session, test_user: User, test_device_node: DeviceNode):
    """Test handling of device command failure."""
    from api.device_websocket import get_device_connection_manager
    from tools.device_tool import device_camera_snap

    manager = get_device_connection_manager()

    # Mock WebSocket that returns failure
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send_json(self, message):
            self.messages.append(message)

        async def receive_json(self, timeout=None):
            await asyncio.sleep(0.1)
            return {
                "type": "result",
                "command_id": self.messages[-1]["command_id"] if self.messages else "unknown",
                "success": False,
                "error": "Camera permission denied"
            }

    mock_ws = MockWebSocket()
    await manager.connect(
        mock_ws,
        test_device_node.device_id,
        test_user.id,
        {"name": "Test Device", "capabilities": ["camera"]}
    )

    try:
        result = await device_camera_snap(
            db=db,
            user_id=test_user.id,
            device_node_id=test_device_node.device_id,
            agent_id=None
        )

        assert result["success"] is False
        assert "Camera permission denied" in result["error"]

        # Check audit entry records failure
        audit = db.query(DeviceAudit).filter(
            DeviceAudit.action_type == "camera_snap"
        ).first()
        assert audit is not None
        assert audit.success is False
        assert "Camera permission denied" in audit.error_message

    finally:
        manager.disconnect(test_device_node.device_id, test_user.id)


# ============================================================================
# Heartbeat Tests
# ============================================================================

@pytest.mark.asyncio
async def test_device_heartbeat(test_user: User, test_device_node: DeviceNode, auth_token: str):
    """Test heartbeat keep-alive messages."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect(
            f"/api/devices/ws?token={auth_token}"
        ) as websocket:
            # Register device
            register_msg = {
                "type": "register",
                "device_node_id": test_device_node.device_id,
                "device_info": {
                    "name": "Test Device",
                    "node_type": "mobile",
                    "platform": "ios",
                    "capabilities": ["camera"]
                }
            }
            await websocket.send_json(register_msg)
            await websocket.receive_json()  // registered

            # Send heartbeat
            heartbeat_msg = {
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_json(heartbeat_msg)

            # Receive heartbeat ack
            response = await websocket.receive_json()
            assert response["type"] == "heartbeat_ack"
            assert "timestamp" in response


# ============================================================================
# Governance Tests
# ============================================================================

@pytest.mark.asyncio
async def test_device_governance_check(
    db: Session,
    test_user: User,
    test_device_node: DeviceNode
):
    """Test that governance checks are performed for device actions."""
    from api.device_websocket import get_device_connection_manager

    # Create an agent with STUDENT maturity (should be blocked from command execution)
    from core.models import AgentRegistry
    from tools.device_tool import device_execute_command
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name="test_student_agent",
        description="Test agent",
        maturity_level="student",
        status="active",
        created_by=test_user.id,
    )
    db.add(agent)
    db.commit()

    manager = get_device_connection_manager()

    # Mock WebSocket
    class MockWebSocket:
        def __init__(self):
            self.messages = []

        async def send_json(self, message):
            self.messages.append(message)

        async def receive_json(self, timeout=None):
            await asyncio.sleep(0.1)
            return {
                "type": "result",
                "command_id": self.messages[-1]["command_id"] if self.messages else "unknown",
                "success": True,
                "data": {"exit_code": 0, "stdout": "", "stderr": ""}
            }

    mock_ws = MockWebSocket()
    await manager.connect(
        mock_ws,
        test_device_node.device_id,
        test_user.id,
        {"name": "Test Device", "capabilities": ["command_execution"]}
    )

    try:
        # Try to execute command with STUDENT agent
        result = await device_execute_command(
            db=db,
            user_id=test_user.id,
            device_node_id=test_device_node.device_id,
            command="ls",
            agent_id=agent.id
        )

        # Should be blocked by governance
        assert result["success"] is False
        assert result.get("governance_blocked") is True

    finally:
        manager.disconnect(test_device_node.device_id, test_user.id)


# ============================================================================
# Connection Manager Tests
# ============================================================================

def test_connection_manager_singleton():
    """Test that connection manager is a singleton."""
    from api.device_websocket import get_device_connection_manager
    manager1 = get_device_connection_manager()
    manager2 = get_device_connection_manager()
    assert manager1 is manager2


def test_connection_tracker():
    """Test connection tracking."""
    from api.device_websocket import get_device_connection_manager
    manager = get_device_connection_manager()

    # Initially no connections
    assert len(manager.active_connections) == 0
    assert len(manager.get_all_connected_devices()) == 0

    # Test is_device_connected
    assert not manager.is_device_connected("nonexistent_device")
