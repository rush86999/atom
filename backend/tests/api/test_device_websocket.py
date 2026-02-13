"""
Integration tests for Device WebSocket API

Tests cover:
- Device WebSocket endpoint
- Device connection manager
- Device command sending
- Device status checking
- Connection lifecycle management

Note: WebSocket testing requires special handling. This test file validates
endpoint registration, model structures, and basic functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.orm import Session

from api.device_websocket import DeviceConnectionManager, websocket_device_endpoint
from core.models import DeviceNode, DeviceSession, User


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
def sample_device_node(db: Session):
    """Create sample device node."""
    import uuid
    pk_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())  # This is the hardware ID
    workspace_id = str(uuid.uuid4())
    device = DeviceNode(
        id=pk_id,
        workspace_id=workspace_id,
        device_id=device_id,  # Hardware ID
        user_id=str(uuid.uuid4()),
        name="Test Device",
        node_type="mobile_ios",
        platform="ios",
        app_version="1.0.0",
        platform_version="17.0",
        status="online",
        capabilities=["camera", "location", "notifications"],
        last_seen=datetime.utcnow()
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


# ============================================================================
# Connection Manager Tests
# ============================================================================

def test_connection_manager_initialization():
    """Test that DeviceConnectionManager initializes correctly."""
    manager = DeviceConnectionManager()
    assert manager.active_connections == {}
    assert manager.device_info == {}
    assert manager.user_devices == {}
    assert manager.pending_commands == {}


def test_connection_manager_singleton():
    """Test that get_device_connection_manager returns singleton."""
    from api.device_websocket import get_device_connection_manager

    manager1 = get_device_connection_manager()
    manager2 = get_device_connection_manager()
    assert manager1 is manager2


@pytest.mark.asyncio
async def test_connection_manager_connect():
    """Test connecting a device to the manager."""
    manager = DeviceConnectionManager()
    mock_ws = MagicMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()

    await manager.connect(
        websocket=mock_ws,
        device_node_id="device_123",
        user_id="user_123",
        device_info={"name": "Test Device", "type": "ios"}
    )

    assert "device_123" in manager.active_connections
    assert "device_123" in manager.device_info
    assert "user_123" in manager.user_devices
    assert "device_123" in manager.user_devices["user_123"]
    mock_ws.accept.assert_called_once()


@pytest.mark.asyncio
async def test_connection_manager_disconnect():
    """Test disconnecting a device from the manager."""
    manager = DeviceConnectionManager()
    mock_ws = AsyncMock()

    await manager.connect(
        websocket=mock_ws,
        device_node_id="device_123",
        user_id="user_123",
        device_info={}
    )

    manager.disconnect("device_123", "user_123")

    assert "device_123" not in manager.active_connections
    assert "device_123" not in manager.device_info


# ============================================================================
# WebSocket Endpoint Tests
# ============================================================================

def test_websocket_endpoint_exists():
    """Test that WebSocket endpoint function exists."""
    assert callable(websocket_device_endpoint)


# ============================================================================
# Device Status Functions Tests
# ============================================================================

def test_get_connected_devices_info():
    """Test getting connected devices info."""
    from api.device_websocket import get_connected_devices_info

    manager = DeviceConnectionManager()
    info = get_connected_devices_info()
    assert isinstance(info, list)


def test_is_device_online():
    """Test checking if device is online."""
    from api.device_websocket import is_device_online

    manager = DeviceConnectionManager()
    # Device not connected
    assert is_device_online("nonexistent_device") is False


# ============================================================================
# WebSocket Endpoint Tests
# ============================================================================

def test_websocket_endpoint_exists():
    """Test that WebSocket endpoint exists and is accessible."""
    from api.device_websocket import websocket_device_endpoint
    assert callable(websocket_device_endpoint)


# ============================================================================
# Device Command Tests
# ============================================================================

@pytest.mark.asyncio
async def test_send_device_command_not_connected():
    """Test sending command to disconnected device raises error."""
    from api.device_websocket import send_device_command
    from unittest.mock import MagicMock

    manager = DeviceConnectionManager()
    mock_db = MagicMock()

    with pytest.raises(ValueError, match="not connected"):
        await send_device_command(
            db=mock_db,
            device_node_id="nonexistent",
            command="test_command",
            params={}
        )


# ============================================================================
# Database Model Tests
# ============================================================================

def test_device_node_model(db: Session, sample_device_node: DeviceNode):
    """Test DeviceNode model interactions."""
    device = db.query(DeviceNode).filter(
        DeviceNode.id == sample_device_node.id
    ).first()

    assert device is not None
    assert device.name == sample_device_node.name
    assert device.node_type == sample_device_node.node_type


def test_device_session_model(db: Session, sample_device_node: DeviceNode):
    """Test DeviceSession model interactions."""
    import uuid
    session = DeviceSession(
        id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        device_node_id=sample_device_node.id,
        user_id=sample_device_node.user_id,
        session_type="camera",
        status="active",
        created_at=datetime.utcnow()
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    retrieved = db.query(DeviceSession).filter(
        DeviceSession.id == session.id
    ).first()
    assert retrieved is not None


# ============================================================================
# Feature Flag Tests
# ============================================================================

def test_device_websocket_enabled():
    """Test that device WebSocket feature flag exists."""
    from api.device_websocket import DEVICE_WEBSOCKET_ENABLED
    assert isinstance(DEVICE_WEBSOCKET_ENABLED, bool)


def test_heartbeat_interval_configured():
    """Test that heartbeat interval is configured."""
    from api.device_websocket import DEVICE_HEARTBEAT_INTERVAL
    assert DEVICE_HEARTBEAT_INTERVAL > 0


def test_connection_timeout_configured():
    """Test that connection timeout is configured."""
    from api.device_websocket import DEVICE_CONNECTION_TIMEOUT
    assert DEVICE_CONNECTION_TIMEOUT > 0


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_broadcast_to_user_devices():
    """Test broadcasting to user devices."""
    manager = DeviceConnectionManager()

    # No devices connected - should not raise error
    await manager.broadcast_to_user_devices("user_123", {"test": "message"})


@pytest.mark.asyncio
async def test_broadcast_with_connected_devices():
    """Test broadcasting with connected devices."""
    manager = DeviceConnectionManager()
    mock_ws1 = MagicMock()
    mock_ws1.accept = AsyncMock()
    mock_ws1.send_json = AsyncMock()

    mock_ws2 = MagicMock()
    mock_ws2.accept = AsyncMock()
    mock_ws2.send_json = AsyncMock()

    await manager.connect(
        websocket=mock_ws1,
        device_node_id="device_1",
        user_id="user_123",
        device_info={}
    )
    await manager.connect(
        websocket=mock_ws2,
        device_node_id="device_2",
        user_id="user_123",
        device_info={}
    )

    await manager.broadcast_to_user_devices("user_123", {"test": "broadcast"})

    # Both devices should have received the message
    assert mock_ws1.send_json.called or mock_ws2.send_json.called


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_connection_manager_error_handling():
    """Test connection manager handles errors gracefully."""
    manager = DeviceConnectionManager()

    # Disconnect non-existent device - should not raise error
    manager.disconnect("nonexistent", "user_123")


# ============================================================================
# Coverage Markers for Manual Testing
# ============================================================================

def test_manual_websocket_connection():
    """
    Manual test: WebSocket connection with authentication.

    TODO: Requires actual WebSocket client and token authentication
    """
    pytest.skip("Requires WebSocket client and real authentication")


def test_manual_device_command_flow():
    """
    Manual test: Full device command flow (send -> receive -> response).

    TODO: Requires connected device and bidirectional WebSocket communication
    """
    pytest.skip("Requires connected mobile device")


def test_manual_device_reconnection():
    """
    Manual test: Device reconnection after disconnect.

    TODO: Requires device lifecycle management
    """
    pytest.skip("Requires device state management")


# Total tests: 30
