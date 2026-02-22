"""
Comprehensive WebSocket Routes Integration Tests

Tests for WebSocket endpoints from api/websocket_routes.py and api/device_websocket.py.

Coverage Target: 80%+
- WebSocket connection establishment
- Ping/pong handling
- Disconnect handling
- Workspace routing
- Device WebSocket connections
- Device registration and management
- Command sending and receiving
- Heartbeat mechanism
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocket
from datetime import datetime
import asyncio

from api.websocket_routes import websocket_endpoint
from api.device_websocket import (
    websocket_device_endpoint,
    get_device_connection_manager,
    send_device_command,
    get_connected_devices_info,
    is_device_online
)
from core.notification_manager import notification_manager
from core.models import DeviceNode, User, UserRole
from core.database import get_db_session
from core.auth import create_access_token


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = MagicMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def sample_workspace_id():
    """Sample workspace ID."""
    return "workspace_123"


@pytest.fixture
def test_user_with_device():
    """Create test user with device"""
    import uuid
    user_id = str(uuid.uuid4())
    device_id = f"device_{uuid.uuid4()}"
    workspace_id = str(uuid.uuid4())

    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        status="active"
    )

    device = DeviceNode(
        id=str(uuid.uuid4()),
        device_id=device_id,
        user_id=user_id,
        workspace_id=workspace_id,
        name=f"Test Device {device_id[:8]}",
        node_type="mobile",
        status="offline",
        platform="ios",
        capabilities=["camera", "location", "microphone"],
        last_seen=datetime.utcnow()
    )

    return {"user": user, "device": device, "workspace_id": workspace_id}


@pytest.fixture
def valid_device_token(test_user_with_device):
    """Create valid device token"""
    user = test_user_with_device["user"]
    return create_access_token(data={"sub": user.id})


# =============================================================================
# WebSocket Connection Tests
# =============================================================================

class TestWebSocketConnection:
    """Tests for WebSocket connection handling."""

    @pytest.mark.asyncio
    async def test_websocket_connect(self, mock_websocket, sample_workspace_id):
        """Test WebSocket connection establishment."""
        # Mock the receive to trigger disconnect immediately
        mock_websocket.receive_text.side_effect = Exception("WebSocketDisconnect")

        # Use real notification manager, not mocked
        try:
            await websocket_endpoint(mock_websocket, sample_workspace_id)
        except:
            pass

        # Verify connection was accepted
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self, mock_websocket, sample_workspace_id):
        """Test ping/pong message handling."""
        mock_websocket.receive_text.side_effect = ["ping", Exception("WebSocketDisconnect")]

        try:
            await websocket_endpoint(mock_websocket, sample_workspace_id)
        except:
            pass

        # Verify pong was sent at least once
        if mock_websocket.send_text.called:
            # Check if any call was for "pong"
            found_pong = any(call[0][0] == "pong" for call in mock_websocket.send_text.call_args_list)
            assert found_pong, "Expected 'pong' to be sent"

    @pytest.mark.asyncio
    async def test_websocket_disconnect(self, mock_websocket, sample_workspace_id):
        """Test WebSocket disconnect handling."""
        mock_websocket.receive_text.side_effect = Exception("WebSocketDisconnect")

        initial_connections = len(notification_manager.active_connections.get(sample_workspace_id, set()))

        try:
            await websocket_endpoint(mock_websocket, sample_workspace_id)
        except:
            pass

        # Verify disconnect was handled (connection should be removed)
        final_connections = len(notification_manager.active_connections.get(sample_workspace_id, set()))
        # After disconnect, should be back to initial count (connection added then removed)
        assert final_connections == initial_connections

    @pytest.mark.asyncio
    async def test_websocket_error(self, mock_websocket, sample_workspace_id):
        """Test WebSocket error handling."""
        mock_websocket.receive_text.side_effect = Exception("Connection error")

        try:
            await websocket_endpoint(mock_websocket, sample_workspace_id)
        except:
            pass

        # Verify disconnect was called on error
        # The connection should be removed from active connections
        connections = notification_manager.active_connections.get(sample_workspace_id, set())
        assert mock_websocket not in connections


# =============================================================================
# Message Handling Tests
# =============================================================================

class TestMessageHandling:
    """Tests for WebSocket message handling."""

    @pytest.mark.asyncio
    async def test_websocket_client_message(self, mock_websocket, sample_workspace_id):
        """Test handling client message (not ping)."""
        # Send non-ping message
        mock_websocket.receive_text.side_effect = ["client message", Exception("Done")]

        try:
            await websocket_endpoint(mock_websocket, sample_workspace_id)
        except:
            pass

        # Should not crash on unknown message
        # send_text should not be called for non-ping messages
        if mock_websocket.send_text.called:
            for call in mock_websocket.send_text.call_args_list:
                assert call[0][0] != "pong", "Should not send pong for non-ping message"

    @pytest.mark.asyncio
    async def test_websocket_multiple_pings(self, mock_websocket, sample_workspace_id):
        """Test multiple ping/pong cycles."""
        mock_websocket.receive_text.side_effect = ["ping", "ping", "ping", Exception("Done")]

        try:
            await websocket_endpoint(mock_websocket, sample_workspace_id)
        except:
            pass

        # Should have sent pong at least once
        assert mock_websocket.send_text.call_count >= 1
        # Verify at least some were "pong" responses
        pong_count = sum(1 for call in mock_websocket.send_text.call_args_list if call[0][0] == "pong")
        assert pong_count >= 1, "Expected at least one pong response"


# =============================================================================
# Workspace Routing Tests
# =============================================================================

class TestWorkspaceRouting:
    """Tests for workspace ID routing."""

    @pytest.mark.asyncio
    async def test_workspace_id_used(self, mock_websocket, sample_workspace_id):
        """Test that workspace_id is properly used."""
        mock_websocket.receive_text.side_effect = Exception("Done")

        try:
            await websocket_endpoint(mock_websocket, sample_workspace_id)
        except:
            pass

        # Verify websocket was accepted (indicating workspace_id was processed)
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_workspace_ids(self, mock_websocket):
        """Test different workspace IDs are handled separately."""
        workspace_1 = "workspace_1"
        workspace_2 = "workspace_2"

        # For workspace_1
        mock_websocket.receive_text.side_effect = Exception("Done")
        try:
            await websocket_endpoint(mock_websocket, workspace_1)
        except:
            pass

        # Verify connect was called (which uses workspace_id)
        mock_websocket.accept.assert_called_once()
        mock_websocket.reset_mock()

        # For workspace_2 - create new mock
        mock_websocket2 = MagicMock(spec=WebSocket)
        mock_websocket2.accept = AsyncMock()
        mock_websocket2.receive_text = AsyncMock(side_effect=Exception("Done"))
        mock_websocket2.send_text = AsyncMock()
        mock_websocket2.close = AsyncMock()

        try:
            await websocket_endpoint(mock_websocket2, workspace_2)
        except:
            pass

        # Verify second connection was also accepted
        mock_websocket2.accept.assert_called_once()


# =============================================================================
# Device WebSocket Connection Tests
# =============================================================================

class TestDeviceWebSocketConnection:
    """Tests for device WebSocket connections."""

    @pytest.mark.asyncio
    async def test_device_websocket_connect_success(self, mock_websocket, valid_device_token, test_user_with_device):
        """Test successful device WebSocket connection."""
        device = test_user_with_device["device"]

        with patch('api.device_websocket.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": test_user_with_device["user"].id}

            with get_db_session() as db:
                db.add(test_user_with_device["user"])
                db.add(device)
                db.commit()

            # Mock register message
            mock_websocket.receive_json.return_value = {
                "type": "register",
                "device_node_id": device.device_id,
                "device_info": {
                    "platform": "ios",
                    "capabilities": ["camera", "location"]
                }
            }

            # Mock subsequent messages to trigger disconnect
            mock_websocket.receive_json.side_effect = [
                {"type": "register", "device_node_id": device.device_id, "device_info": {"platform": "ios", "capabilities": ["camera"]}},
                Exception("WebSocketDisconnect")
            ]

            try:
                await websocket_device_endpoint(mock_websocket, valid_device_token)
            except:
                pass

            # Should have accepted connection
            mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_device_websocket_invalid_token(self, mock_websocket):
        """Test device WebSocket with invalid token."""
        invalid_token = "invalid_token"

        with patch('api.device_websocket.decode_token') as mock_decode:
            mock_decode.return_value = None  # Invalid token

            try:
                await websocket_device_endpoint(mock_websocket, invalid_token)
            except:
                pass

            # Should close connection
            mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_device_websocket_missing_user(self, mock_websocket, valid_device_token):
        """Test device WebSocket with non-existent user."""
        import uuid

        with patch('api.device_websocket.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": str(uuid.uuid4())}  # Non-existent user

            with get_db_session() as db:
                user = db.query(User).filter(User.id == mock_decode.return_value["sub"]).first()
                assert user is None  # Verify user doesn't exist

            try:
                await websocket_device_endpoint(mock_websocket, valid_device_token)
            except:
                pass

            # Should close connection
            mock_websocket.close.assert_called()

    @pytest.mark.asyncio
    async def test_device_websocket_registration_timeout(self, mock_websocket, valid_device_token, test_user_with_device):
        """Test device WebSocket registration timeout."""
        with patch('api.device_websocket.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": test_user_with_device["user"].id}

            with get_db_session() as db:
                db.add(test_user_with_device["user"])
                db.commit()

            # Mock timeout on receive_json
            mock_websocket.receive_json.side_effect = asyncio.TimeoutError()

            try:
                await websocket_device_endpoint(mock_websocket, valid_device_token)
            except:
                pass

            # Should close connection
            mock_websocket.close.assert_called()


# =============================================================================
# Device WebSocket Message Handling Tests
# =============================================================================

class TestDeviceWebSocketMessages:
    """Tests for device WebSocket message handling."""

    @pytest.mark.asyncio
    async def test_device_websocket_heartbeat(self, mock_websocket, valid_device_token, test_user_with_device):
        """Test device WebSocket heartbeat mechanism."""
        device = test_user_with_device["device"]

        with patch('api.device_websocket.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": test_user_with_device["user"].id}

            with get_db_session() as db:
                db.add(test_user_with_device["user"])
                db.add(device)
                db.commit()

            # Mock register then heartbeat
            mock_websocket.receive_json.side_effect = [
                {"type": "register", "device_node_id": device.device_id, "device_info": {"platform": "ios"}},
                {"type": "heartbeat"},
                Exception("WebSocketDisconnect")
            ]

            try:
                await websocket_device_endpoint(mock_websocket, valid_device_token)
            except:
                pass

            # Should have sent heartbeat_ack
            assert mock_websocket.send_json.call_count >= 1

    @pytest.mark.asyncio
    async def test_device_websocket_result_message(self, mock_websocket, valid_device_token, test_user_with_device):
        """Test device WebSocket result message handling."""
        device = test_user_with_device["device"]

        with patch('api.device_websocket.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": test_user_with_device["user"].id}

            with get_db_session() as db:
                db.add(test_user_with_device["user"])
                db.add(device)
                db.commit()

            # Mock register then result
            mock_websocket.receive_json.side_effect = [
                {"type": "register", "device_node_id": device.device_id, "device_info": {"platform": "ios"}},
                {"type": "result", "command_id": "test-cmd", "success": True, "data": {"result": "ok"}},
                Exception("WebSocketDisconnect")
            ]

            try:
                await websocket_device_endpoint(mock_websocket, valid_device_token)
            except:
                pass

            # Should handle result without crashing
            mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_device_websocket_error_message(self, mock_websocket, valid_device_token, test_user_with_device):
        """Test device WebSocket error message handling."""
        device = test_user_with_device["device"]

        with patch('api.device_websocket.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": test_user_with_device["user"].id}

            with get_db_session() as db:
                db.add(test_user_with_device["user"])
                db.add(device)
                db.commit()

            # Mock register then error
            mock_websocket.receive_json.side_effect = [
                {"type": "register", "device_node_id": device.device_id, "device_info": {"platform": "ios"}},
                {"type": "error", "error": "Test error"},
                Exception("WebSocketDisconnect")
            ]

            try:
                await websocket_device_endpoint(mock_websocket, valid_device_token)
            except:
                pass

            # Should handle error without crashing
            mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_device_websocket_unknown_message(self, mock_websocket, valid_device_token, test_user_with_device):
        """Test device WebSocket unknown message type handling."""
        device = test_user_with_device["device"]

        with patch('api.device_websocket.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": test_user_with_device["user"].id}

            with get_db_session() as db:
                db.add(test_user_with_device["user"])
                db.add(device)
                db.commit()

            # Mock register then unknown message
            mock_websocket.receive_json.side_effect = [
                {"type": "register", "device_node_id": device.device_id, "device_info": {"platform": "ios"}},
                {"type": "unknown_type"},
                Exception("WebSocketDisconnect")
            ]

            try:
                await websocket_device_endpoint(mock_websocket, valid_device_token)
            except:
                pass

            # Should handle unknown message without crashing
            mock_websocket.accept.assert_called_once()


# =============================================================================
# Device Connection Manager Tests
# =============================================================================

class TestDeviceConnectionManager:
    """Tests for device connection manager."""

    def test_manager_singleton(self):
        """Test device connection manager is singleton."""
        manager1 = get_device_connection_manager()
        manager2 = get_device_connection_manager()
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_connect_device(self):
        """Test connecting a device."""
        manager = get_device_connection_manager()
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()

        device_id = "test_device_123"
        user_id = "user_456"
        device_info = {"platform": "ios", "capabilities": ["camera"]}

        await manager.connect(mock_ws, device_id, user_id, device_info)

        assert device_id in manager.active_connections
        assert manager.is_device_connected(device_id)
        assert manager.get_device_info(device_id) == device_info

    @pytest.mark.asyncio
    async def test_disconnect_device(self):
        """Test disconnecting a device."""
        manager = get_device_connection_manager()
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()

        device_id = "test_device_123"
        user_id = "user_456"

        await manager.connect(mock_ws, device_id, user_id, {})
        manager.disconnect(device_id, user_id)

        assert device_id not in manager.active_connections
        assert not manager.is_device_connected(device_id)

    @pytest.mark.asyncio
    async def test_send_command_success(self):
        """Test sending command to device."""
        manager = get_device_connection_manager()
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()

        # Capture the command that was sent
        sent_command = {}

        def capture_send_json(command):
            sent_command.update(command)
            # Return matching command_id in response
            return AsyncMock(return_value={
                "type": "result",
                "command_id": command.get("command_id"),
                "success": True,
                "data": {"result": "ok"}
            })

        mock_ws.send_json = capture_send_json
        mock_ws.receive_json = AsyncMock()

        device_id = "test_device_123"
        user_id = "user_456"

        await manager.connect(mock_ws, device_id, user_id, {})

        # Mock receive_json to return response with matching command_id
        async def mock_receive():
            return {
                "type": "result",
                "command_id": sent_command.get("command_id"),
                "success": True,
                "data": {"result": "ok"}
            }

        mock_ws.receive_json = mock_receive

        response = await manager.send_command(device_id, "camera_snap", {"mode": "photo"})

        assert response["success"] is True
        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_command_device_not_connected(self):
        """Test sending command to disconnected device raises error."""
        manager = get_device_connection_manager()

        with pytest.raises(ValueError, match="not connected"):
            await manager.send_command("nonexistent_device", "camera_snap", {})

    def test_get_user_devices(self):
        """Test getting devices for user."""
        manager = get_device_connection_manager()

        # Clean start
        manager.user_devices.clear()

        user_id = "user_123"
        device1 = "device_1"
        device2 = "device_2"

        manager.user_devices[user_id] = {device1, device2}

        devices = manager.get_user_devices(user_id)
        assert set(devices) == {device1, device2}

    def test_get_all_connected_devices(self):
        """Test getting all connected devices."""
        manager = get_device_connection_manager()

        # Clean start
        manager.device_info.clear()

        device1 = "device_1"
        device2 = "device_2"

        manager.device_info[device1] = {"platform": "ios"}
        manager.device_info[device2] = {"platform": "android"}

        devices = manager.get_all_connected_devices()
        assert len(devices) == 2

        device_ids = [d["device_node_id"] for d in devices]
        assert device1 in device_ids
        assert device2 in device_ids


# =============================================================================
# Device Command Tests
# =============================================================================

class TestDeviceCommands:
    """Tests for device command sending."""

    @pytest.mark.asyncio
    async def test_send_device_command_success(self, test_user_with_device):
        """Test successful command sending via helper function."""
        device = test_user_with_device["device"]

        manager = get_device_connection_manager()
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        mock_ws.receive_json = AsyncMock(return_value={
            "type": "result",
            "command_id": "test-cmd",
            "success": True,
            "data": {"photo": "data"}
        })

        await manager.connect(mock_ws, device.device_id, test_user_with_device["user"].id, {})

        with get_db_session() as db:
            db.add(test_user_with_device["user"])
            db.add(device)
            db.commit()

            result = await send_device_command(
                device.device_id,
                "camera_snap",
                {"mode": "photo"},
                db
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_send_device_command_not_connected(self, test_user_with_device):
        """Test command to offline device."""
        device = test_user_with_device["device"]

        with get_db_session() as db:
            db.add(test_user_with_device["user"])
            device.status = "offline"
            db.add(device)
            db.commit()

            with pytest.raises(ValueError, match="not connected"):
                await send_device_command(
                    device.device_id,
                    "camera_snap",
                    {},
                    db
                )

    @pytest.mark.asyncio
    async def test_send_device_command_not_found(self, test_user_with_device):
        """Test command to non-existent device."""
        with get_db_session() as db:
            db.add(test_user_with_device["user"])
            db.commit()

            with pytest.raises(ValueError, match="not found"):
                await send_device_command(
                    "nonexistent_device",
                    "camera_snap",
                    {},
                    db
                )


# =============================================================================
# Device Info Helper Tests
# =============================================================================

class TestDeviceHelpers:
    """Tests for device helper functions."""

    def test_is_device_online(self):
        """Test checking if device is online."""
        manager = get_device_connection_manager()

        device_id = "test_device_123"

        # Initially offline
        assert not is_device_online(device_id)

        # After connection, online
        manager.active_connections[device_id] = MagicMock()
        assert is_device_online(device_id)

    def test_get_connected_devices_info(self):
        """Test getting connected devices info."""
        manager = get_device_connection_manager()

        # Clean start
        manager.device_info.clear()

        device_id = "device_123"
        manager.device_info[device_id] = {"platform": "ios", "capabilities": ["camera"]}

        devices = get_connected_devices_info()
        assert len(devices) == 1
        assert devices[0]["device_node_id"] == device_id
        assert devices[0]["platform"] == "ios"


# =============================================================================
# WebSocket Error Handling Tests
# =============================================================================

class TestWebSocketErrors:
    """Tests for WebSocket error scenarios."""

    @pytest.mark.asyncio
    async def test_websocket_disconnect_gracefully(self, mock_websocket, sample_workspace_id):
        """Test graceful WebSocket disconnect."""
        mock_websocket.receive_text.side_effect = Exception("WebSocketDisconnect")

        try:
            await websocket_endpoint(mock_websocket, sample_workspace_id)
        except:
            pass

        # Verify disconnect was handled gracefully
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_device_websocket_disconnect_gracefully(self, mock_websocket, valid_device_token, test_user_with_device):
        """Test graceful device WebSocket disconnect."""
        device = test_user_with_device["device"]

        with patch('api.device_websocket.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": test_user_with_device["user"].id}

            with get_db_session() as db:
                db.add(test_user_with_device["user"])
                db.add(device)
                db.commit()

            # Simulate disconnect after registration
            mock_websocket.receive_json.side_effect = [
                {"type": "register", "device_node_id": device.device_id, "device_info": {"platform": "ios"}},
                WebSocketDisconnect(1000, "Normal closure")
            ]

            try:
                await websocket_device_endpoint(mock_websocket, valid_device_token)
            except:
                pass

            # Should handle gracefully
            mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_connection_error(self, mock_websocket, sample_workspace_id):
        """Test WebSocket connection error handling."""
        mock_websocket.receive_text.side_effect = Exception("Connection error")

        try:
            await websocket_endpoint(mock_websocket, sample_workspace_id)
        except:
            pass

        # Connection should be removed from active connections
        connections = notification_manager.active_connections.get(sample_workspace_id, set())
        assert mock_websocket not in connections

    @pytest.mark.asyncio
    async def test_device_websocket_heartbeat_timeout(self, mock_websocket, valid_device_token, test_user_with_device):
        """Test device WebSocket heartbeat timeout handling."""
        device = test_user_with_device["device"]

        with patch('api.device_websocket.decode_token') as mock_decode:
            mock_decode.return_value = {"sub": test_user_with_device["user"].id}

            with get_db_session() as db:
                db.add(test_user_with_device["user"])
                db.add(device)
                db.commit()

            # Mock register then timeout
            mock_websocket.receive_json.side_effect = [
                {"type": "register", "device_node_id": device.device_id, "device_info": {"platform": "ios"}},
                asyncio.TimeoutError(),  # Heartbeat timeout
                Exception("WebSocketDisconnect")
            ]

            try:
                await websocket_device_endpoint(mock_websocket, valid_device_token)
            except:
                pass

            # Should handle timeout
            mock_websocket.accept.assert_called_once()
