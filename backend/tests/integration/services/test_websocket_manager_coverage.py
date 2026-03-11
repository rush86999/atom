"""
WebSocket Manager Coverage Tests

Comprehensive tests for WebSocketConnectionManager and DebuggingWebSocketManager
using AsyncMock patterns proven in Phase 169.
Target: 70%+ line coverage on core/websocket_manager.py (473 lines)

Tests use AsyncMock for all WebSocket async operations while testing real
connection tracking, broadcast logic, and debugging features.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi import WebSocket
from datetime import datetime

from core.websocket_manager import (
    WebSocketConnectionManager,
    DebuggingWebSocketManager,
    get_websocket_manager,
    get_debugging_websocket_manager,
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_websocket():
    """Create mock WebSocket with AsyncMock for async methods."""
    mock_ws = Mock(spec=WebSocket)
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()
    return mock_ws


@pytest.fixture
def manager():
    """Create fresh WebSocket manager for each test."""
    return WebSocketConnectionManager()


@pytest.fixture
def debug_manager(manager):
    """Create debugging manager with base manager."""
    return DebuggingWebSocketManager(manager)

# ============================================================================
# Connection Lifecycle Tests
# ============================================================================

class TestWebSocketConnectionLifecycle:
    """Test WebSocket connection lifecycle management."""

    @pytest.mark.asyncio
    async def test_connect_and_track_connection(self, manager, mock_websocket):
        """Test that WebSocket connections are tracked properly after connect."""
        await manager.connect(mock_websocket, stream_id="test_stream")

        # Verify connection was accepted
        mock_websocket.accept.assert_called_once()

        # Verify connection is tracked
        assert "test_stream" in manager.active_connections
        assert mock_websocket in manager.active_connections["test_stream"]

        # Verify connection metadata
        assert mock_websocket in manager.connection_streams
        assert manager.connection_streams[mock_websocket] == "test_stream"
        assert "connected_at" in manager.connection_info[mock_websocket]

    @pytest.mark.asyncio
    async def test_connect_sends_welcome_message(self, manager, mock_websocket):
        """Test that connect sends a welcome message to the client."""
        await manager.connect(mock_websocket, stream_id="test_stream")

        # Verify welcome message sent
        mock_websocket.send_text.assert_called()
        call_args = mock_websocket.send_text.call_args
        import json
        message = json.loads(call_args[0][0])
        assert message["type"] == "connected"
        assert message["stream_id"] == "test_stream"
        assert "timestamp" in message

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_streams(self, manager, mock_websocket):
        """Test that disconnecting removes WebSocket from all tracking structures."""
        await manager.connect(mock_websocket, stream_id="stream1")
        manager.disconnect(mock_websocket)

        # Verify removal from active connections
        assert mock_websocket not in manager.active_connections.get("stream1", set())

        # Verify removal from connection streams
        assert mock_websocket not in manager.connection_streams

        # Verify removal from connection info
        assert mock_websocket not in manager.connection_info

    @pytest.mark.asyncio
    async def test_multiple_connections_per_stream(self, manager):
        """Test that multiple WebSockets can subscribe to the same stream."""
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws1.accept = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws1.send_text = AsyncMock()
        mock_ws2.send_text = AsyncMock()

        await manager.connect(mock_ws1, stream_id="shared_stream")
        await manager.connect(mock_ws2, stream_id="shared_stream")

        # Both connections tracked
        assert len(manager.active_connections["shared_stream"]) == 2
        assert mock_ws1 in manager.active_connections["shared_stream"]
        assert mock_ws2 in manager.active_connections["shared_stream"]

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_empty_stream(self, manager, mock_websocket):
        """Test that empty streams are removed from active_connections."""
        await manager.connect(mock_websocket, stream_id="temp_stream")
        assert "temp_stream" in manager.active_connections

        # Disconnect the only connection
        manager.disconnect(mock_websocket)

        # Stream should be removed
        assert "temp_stream" not in manager.active_connections
