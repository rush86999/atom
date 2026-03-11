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

# ============================================================================
# Broadcast Tests
# ============================================================================

class TestWebSocketBroadcast:
    """Test WebSocket broadcasting functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all_subscribers(self, manager):
        """Test that broadcast reaches all subscribers in a stream."""
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws1.accept = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws1.send_text = AsyncMock()
        mock_ws2.send_text = AsyncMock()

        await manager.connect(mock_ws1, stream_id="stream1")
        await manager.connect(mock_ws2, stream_id="stream1")

        message = {"type": "test", "data": "hello"}
        sent_count = await manager.broadcast("stream1", message)

        # Verify both received message
        assert sent_count == 2
        # send_text is called twice: once for welcome message, once for broadcast
        assert mock_ws1.send_text.call_count == 2
        assert mock_ws2.send_text.call_count == 2

        # Verify message format (last call is the broadcast)
        import json
        call_args = mock_ws1.send_text.call_args[0][0]
        sent_message = json.loads(call_args)
        assert sent_message["type"] == "test"
        assert sent_message["data"] == "hello"

    @pytest.mark.asyncio
    async def test_broadcast_handles_failed_connection(self, manager):
        """Test that broadcast handles connection failures gracefully."""
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws1.accept = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws1.send_text = AsyncMock()
        mock_ws2.send_text = AsyncMock(side_effect=Exception("Connection lost"))
        mock_ws1.send_json = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        await manager.connect(mock_ws1, stream_id="stream1")
        await manager.connect(mock_ws2, stream_id="stream1")

        # Broadcast (one will fail)
        sent_count = await manager.broadcast("stream1", {"type": "test"})

        # Should return successful sends only
        assert sent_count == 1

        # Failed connection should be disconnected
        assert mock_ws2 not in manager.active_connections.get("stream1", set())

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_stream(self, manager):
        """Test broadcast to stream with no subscribers."""
        sent_count = await manager.broadcast("empty_stream", {"type": "test"})

        assert sent_count == 0

    @pytest.mark.asyncio
    async def test_send_personal_succeeds(self, manager, mock_websocket):
        """Test sending a message to a specific connection."""
        mock_websocket.send_text = AsyncMock(return_value=True)

        success = await manager.send_personal(
            mock_websocket,
            {"type": "personal", "data": "test"}
        )

        assert success is True
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_personal_handles_failure(self, manager, mock_websocket):
        """Test send_personal handles send failure."""
        mock_websocket.send_text = AsyncMock(side_effect=Exception("Send failed"))

        success = await manager.send_personal(
            mock_websocket,
            {"type": "personal", "data": "test"}
        )

        assert success is False
        # WebSocket should be disconnected after failed send
        assert mock_websocket not in manager.connection_streams

    @pytest.mark.asyncio
    async def test_broadcast_trace_update(self, manager):
        """Test trace update broadcasting."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await manager.connect(mock_ws, stream_id="stream1")

        sent_count = await manager.broadcast_trace_update(
            "stream1",
            {"step": 1, "status": "running"}
        )

        assert sent_count == 1
        # Verify message structure
        call_args = mock_ws.send_text.call_args[0][0]
        import json
        message = json.loads(call_args)
        assert message["type"] == "trace_update"
        assert message["data"]["step"] == 1

    @pytest.mark.asyncio
    async def test_broadcast_session_update(self, manager):
        """Test debug session update broadcasting."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await manager.connect(mock_ws, stream_id="debug_session_test123")

        sent_count = await manager.broadcast_session_update(
            "test123",
            "variable_changed",
            {"var": "value"}
        )

        assert sent_count == 1
        # Verify message routed to correct stream
        assert "debug_session_test123" in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_to_workspace(self, manager):
        """Test workspace broadcast."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await manager.connect(mock_ws, stream_id="workspace_test_ws")

        sent_count = await manager.broadcast_to_workspace(
            "test_ws",
            {"type": "workspace_update"}
        )

        assert sent_count == 1

# ============================================================================
# Stream Info Tests
# ============================================================================

class TestWebSocketStreamInfo:
    """Test stream information and statistics."""

    def test_get_connection_count(self, manager):
        """Test getting connection count for a stream."""
        assert manager.get_connection_count("non_existent") == 0

        # Add mock connection
        manager.active_connections["stream1"] = {Mock(), Mock()}
        assert manager.get_connection_count("stream1") == 2

    def test_get_all_streams(self, manager):
        """Test getting all active stream IDs."""
        manager.active_connections = {
            "stream1": {Mock()},
            "stream2": {Mock(), Mock()}
        }

        streams = manager.get_all_streams()
        assert "stream1" in streams
        assert "stream2" in streams
        assert len(streams) == 2

    @pytest.mark.asyncio
    async def test_get_stream_info(self, manager, mock_websocket):
        """Test getting detailed information about a stream."""
        await manager.connect(mock_websocket, stream_id="test_stream")

        info = manager.get_stream_info("test_stream")

        assert info["stream_id"] == "test_stream"
        assert info["connection_count"] == 1
        assert "connected_at" in info["connections"][0]

    def test_get_stream_info_for_non_existent(self, manager):
        """Test get_stream_info for non-existent stream."""
        info = manager.get_stream_info("non_existent")

        assert info["stream_id"] == "non_existent"
        assert info["connection_count"] == 0
        assert info["connections"] == []

# ============================================================================
# DebuggingWebSocketManager Tests
# ============================================================================

class TestDebuggingWebSocketManager:
    """Test debugging-specific WebSocket manager functionality."""

    @pytest.mark.asyncio
    async def test_stream_trace(self, debug_manager):
        """Test trace streaming."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await debug_manager.manager.connect(mock_ws, stream_id="trace_exec1_session1")

        sent_count = await debug_manager.stream_trace(
            execution_id="exec1",
            session_id="session1",
            trace_data={"step": 1, "status": "running"}
        )

        assert sent_count == 1
        # Verify stream_id format
        assert "trace_exec1_session1" in debug_manager.manager.active_connections

    @pytest.mark.asyncio
    async def test_notify_variable_changed(self, debug_manager):
        """Test variable change notification."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await debug_manager.manager.connect(mock_ws, stream_id="debug_session_test123")

        sent_count = await debug_manager.notify_variable_changed(
            session_id="test123",
            variable_name="counter",
            new_value=42,
            previous_value=41
        )

        assert sent_count == 1
        # Verify message structure
        call_args = mock_ws.send_text.call_args[0][0]
        import json
        message = json.loads(call_args)
        assert message["type"] == "variable_changed"
        assert message["variable"]["name"] == "counter"
        assert message["variable"]["new_value"] == 42
        assert message["variable"]["previous_value"] == 41

    @pytest.mark.asyncio
    async def test_notify_breakpoint_hit(self, debug_manager):
        """Test breakpoint hit notification."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await debug_manager.manager.connect(mock_ws, stream_id="debug_session_test123")

        sent_count = await debug_manager.notify_breakpoint_hit(
            session_id="test123",
            breakpoint_id="bp1",
            node_id="node1",
            hit_count=5
        )

        assert sent_count == 1

    @pytest.mark.asyncio
    async def test_notify_session_paused(self, debug_manager):
        """Test session paused notification."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await debug_manager.manager.connect(mock_ws, stream_id="debug_session_test123")

        sent_count = await debug_manager.notify_session_paused(
            session_id="test123",
            reason="user_action",
            node_id="node1"
        )

        assert sent_count == 1

    @pytest.mark.asyncio
    async def test_notify_session_resumed(self, debug_manager):
        """Test session resumed notification."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await debug_manager.manager.connect(mock_ws, stream_id="debug_session_test123")

        sent_count = await debug_manager.notify_session_resumed("test123")

        assert sent_count == 1

    @pytest.mark.asyncio
    async def test_notify_step_completed(self, debug_manager):
        """Test step completed notification."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await debug_manager.manager.connect(mock_ws, stream_id="debug_session_test123")

        sent_count = await debug_manager.notify_step_completed(
            session_id="test123",
            action="step_over",
            step_number=5,
            node_id="node1"
        )

        assert sent_count == 1

# ============================================================================
# Singleton Tests
# ============================================================================

class TestWebSocketManagerSingleton:
    """Test WebSocket manager singleton pattern."""

    def test_get_websocket_manager_returns_singleton(self):
        """Test that get_websocket_manager returns same instance."""
        # Reset singleton
        import core.websocket_manager as ws_module
        ws_module._manager = None

        manager1 = get_websocket_manager()
        manager2 = get_websocket_manager()

        assert manager1 is manager2

    def test_get_debugging_websocket_manager_returns_singleton(self):
        """Test that get_debugging_websocket_manager returns same instance."""
        # Reset singletons
        import core.websocket_manager as ws_module
        ws_module._manager = None
        ws_module._debug_manager = None

        debug_mgr1 = get_debugging_websocket_manager()
        debug_mgr2 = get_debugging_websocket_manager()

        assert debug_mgr1 is debug_mgr2
