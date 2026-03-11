"""
ConnectionManager Coverage Tests

Comprehensive tests for core/websockets.py ConnectionManager.
Target: 70%+ line coverage on core/websockets.py (249 lines)

Tests use Mock for database session and authentication while testing
real connection tracking, channel subscriptions, and device broadcasting.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import WebSocket
import os

# Set testing environment before imports
os.environ["TESTING"] = "1"

from core.websockets import ConnectionManager, get_connection_manager

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock database session for authentication."""
    with patch('core.websockets.get_db_session') as mock_ctx:
        db = Mock()
        db.__enter__ = Mock(return_value=db)
        db.__exit__ = Mock(return_value=False)
        mock_ctx.return_value = db
        yield db


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket with AsyncMock."""
    mock_ws = Mock(spec=WebSocket)
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()
    return mock_ws


@pytest.fixture
def manager():
    """Create fresh ConnectionManager for each test."""
    return ConnectionManager()

# ============================================================================
# Authentication Tests
# ============================================================================

class TestConnectionManagerAuth:
    """Test ConnectionManager authentication and connection."""

    @pytest.mark.asyncio
    @patch('core.websockets.get_current_user_ws')
    async def test_connect_with_valid_token_authenticates(self, mock_get_user, manager, mock_websocket, mock_db_session):
        """Test successful connection with valid token."""
        # Mock user
        mock_user = Mock()
        mock_user.id = "user123"
        mock_user.email = "test@example.com"
        mock_user.teams = [Mock(id="team1")]
        mock_user.workspace_id = "workspace1"
        mock_get_user.return_value = mock_user

        result = await manager.connect(mock_websocket, "valid_token")

        # Verify connection accepted
        mock_websocket.accept.assert_called_once()
        assert result == mock_user

        # Verify user subscribed to channels
        assert "user:user123" in manager.active_connections
        assert "team:team1" in manager.active_connections
        assert "workspace:workspace1" in manager.active_connections

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    async def test_connect_with_dev_token_bypass(self, manager, mock_websocket, mock_db_session):
        """Test dev-token bypass in non-production environments."""
        result = await manager.connect(mock_websocket, "dev-token")

        # Verify connection accepted
        mock_websocket.accept.assert_called_once()
        assert result is not None
        assert result.id == "dev-user"

    @pytest.mark.asyncio
    @patch('core.websockets.get_current_user_ws')
    async def test_connect_with_invalid_token_rejects(self, mock_get_user, manager, mock_websocket, mock_db_session):
        """Test connection rejected with invalid token."""
        mock_get_user.return_value = None

        result = await manager.connect(mock_websocket, "invalid_token")

        # Verify connection closed
        mock_websocket.close.assert_called_once_with(code=4001)
        assert result is None

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_all_channels(self, manager, mock_websocket):
        """Test disconnect removes WebSocket from user and channel tracking."""
        # Setup: add connection to tracking
        manager.user_connections["user1"] = [mock_websocket]
        manager.active_connections["user:user1"] = [mock_websocket]
        manager.active_connections["team:team1"] = [mock_websocket]

        manager.disconnect(mock_websocket, "user1")

        # Verify removed from all tracking
        assert mock_websocket not in manager.user_connections.get("user1", [])
        assert mock_websocket not in manager.active_connections.get("user:user1", [])
        assert mock_websocket not in manager.active_connections.get("team:team1", [])

# ============================================================================
# Channel Management Tests
# ============================================================================

class TestConnectionManagerChannels:
    """Test channel subscription and management."""

    def test_subscribe_adds_to_channel(self, manager, mock_websocket):
        """Test subscribing to a channel."""
        manager.subscribe(mock_websocket, "test_channel")

        assert "test_channel" in manager.active_connections
        assert mock_websocket in manager.active_connections["test_channel"]

    def test_unsubscribe_removes_from_channel(self, manager, mock_websocket):
        """Test unsubscribing from a channel."""
        manager.active_connections["test_channel"] = [mock_websocket]

        manager.unsubscribe(mock_websocket, "test_channel")

        assert mock_websocket not in manager.active_connections.get("test_channel", [])

    @pytest.mark.asyncio
    async def test_broadcast_to_channel(self, manager):
        """Test broadcasting to a channel."""
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws1.send_json = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        manager.active_connections["test_channel"] = [mock_ws1, mock_ws2]

        await manager.broadcast("test_channel", {"type": "test", "data": "hello"})

        # Verify both connections received message
        mock_ws1.send_json.assert_called_once()
        mock_ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_personal_message(self, manager):
        """Test sending personal message to user."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()

        manager.user_connections["user1"] = [mock_ws]

        await manager.send_personal_message("user1", {"type": "personal", "data": "test"})

        mock_ws.send_json.assert_called_once()

    def test_get_stats(self, manager, mock_websocket):
        """Test getting connection statistics."""
        manager.active_connections = {
            "channel1": [mock_websocket],
            "channel2": [mock_websocket, Mock(spec=WebSocket)]
        }
        manager.user_connections = {"user1": [mock_websocket]}

        stats = manager.get_stats()

        assert stats["active_channels"] == 2
        assert stats["connected_users"] == 1
        assert stats["channels"]["channel1"] == 1
        assert stats["channels"]["channel2"] == 2

# ============================================================================
# Device Event Broadcasting Tests
# ============================================================================

class TestConnectionManagerDeviceEvents:
    """Test device event broadcasting methods."""

    @pytest.mark.asyncio
    async def test_broadcast_device_registered(self, manager):
        """Test device registration broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        manager.active_connections["user:user1"] = [mock_ws]

        await manager.broadcast_device_registered("user1", {"device_id": "dev1"})

        mock_ws.send_json.assert_called_once()
        call_args = mock_ws.send_json.call_args[0][0]
        assert call_args["type"] == manager.DEVICE_REGISTERED

    @pytest.mark.asyncio
    async def test_broadcast_device_command(self, manager):
        """Test device command broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        manager.active_connections["user:user1"] = [mock_ws]

        await manager.broadcast_device_command("user1", {"command": "start"})

        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_device_camera_ready(self, manager):
        """Test camera ready broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        manager.active_connections["user:user1"] = [mock_ws]

        await manager.broadcast_device_camera_ready("user1", {"image": "data"})

        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_device_recording_complete(self, manager):
        """Test recording complete broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        manager.active_connections["user:user1"] = [mock_ws]

        await manager.broadcast_device_recording_complete("user1", {"recording": "data"})

        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_device_location_update(self, manager):
        """Test location update broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        manager.active_connections["user:user1"] = [mock_ws]

        await manager.broadcast_device_location_update("user1", {"lat": 37.77, "lng": -122.41})

        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_device_notification_sent(self, manager):
        """Test notification sent broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        manager.active_connections["user:user1"] = [mock_ws]

        await manager.broadcast_device_notification_sent("user1", {"notification": "sent"})

        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_device_command_output(self, manager):
        """Test command output broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        manager.active_connections["user:user1"] = [mock_ws]

        await manager.broadcast_device_command_output("user1", {"output": "result"})

        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_device_session_created(self, manager):
        """Test session created broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        manager.active_connections["user:user1"] = [mock_ws]

        await manager.broadcast_device_session_created("user1", {"session_id": "sess1"})

        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_device_session_closed(self, manager):
        """Test session closed broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        manager.active_connections["user:user1"] = [mock_ws]

        await manager.broadcast_device_session_closed("user1", {"session_id": "sess1"})

        mock_ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_device_audit_log(self, manager):
        """Test audit log broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()
        manager.active_connections["user:user1"] = [mock_ws]

        await manager.broadcast_device_audit_log("user1", {"audit": "log"})

        mock_ws.send_json.assert_called_once()
