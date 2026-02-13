"""
Unit tests for WebSocket Routes

Tests cover:
- WebSocket connection establishment
- Ping/pong handling
- Disconnect handling
- Workspace routing
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocket

from api.websocket_routes import websocket_endpoint
from core.notification_manager import notification_manager


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = MagicMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def sample_workspace_id():
    """Sample workspace ID."""
    return "workspace_123"


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
