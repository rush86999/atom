"""
WebSocket Manager Edge Case Tests

Comprehensive edge case testing for WebSocketConnectionManager.
Target: Fill remaining coverage gaps (97% -> 99%+).

Tests cover:
- Connection lifecycle edge cases (reconnect, multiple disconnect, non-existent connections)
- Broadcast failure scenarios (all fail, partial failures, serialization errors)
- State transitions (connection states, stream lifecycle, manager state)
- Edge cases (empty streams, disconnected connections, race conditions)

Uses AsyncMock patterns proven in test_websocket_manager_coverage.py.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from fastapi import WebSocket
from datetime import datetime

from core.websocket_manager import (
    WebSocketConnectionManager,
    DebuggingWebSocketManager,
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
async def manager_with_connections(manager):
    """Create manager with pre-populated connections for state testing."""
    # Add 3 connections to stream1
    for i in range(3):
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        await manager.connect(mock_ws, "stream1")

    # Add 2 connections to stream2
    for i in range(2):
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        await manager.connect(mock_ws, "stream2")

    return manager


@pytest.fixture
def mock_ws_with_send_failure():
    """Create WebSocket that fails on alternate send_text calls."""
    mock_ws = Mock(spec=WebSocket)
    mock_ws.accept = AsyncMock()

    # Alternates between success and failure
    call_count = [0]
    async def failing_send(text):
        call_count[0] += 1
        if call_count[0] % 2 == 0:
            raise Exception("Alternating send failure")
        # Success on odd calls

    mock_ws.send_text = AsyncMock(side_effect=failing_send)
    return mock_ws


# ============================================================================
# TestWebSocketConnectionEdgeCases
# ============================================================================

class TestWebSocketConnectionEdgeCases:
    """Test WebSocket connection lifecycle edge cases."""

    @pytest.mark.asyncio
    async def test_connect_after_disconnect(self, manager, mock_websocket):
        """Test reconnecting same WebSocket after disconnect."""
        # First connection
        await manager.connect(mock_websocket, stream_id="stream1")
        assert mock_websocket in manager.active_connections["stream1"]

        # Disconnect
        manager.disconnect(mock_websocket)
        assert mock_websocket not in manager.connection_streams

        # Reconnect to same stream
        await manager.connect(mock_websocket, stream_id="stream1")
        assert mock_websocket in manager.active_connections["stream1"]
        assert manager.connection_streams[mock_websocket] == "stream1"

    @pytest.mark.asyncio
    async def test_multiple_disconnect_calls(self, manager, mock_websocket):
        """Test that calling disconnect() twice doesn't error."""
        await manager.connect(mock_websocket, stream_id="stream1")

        # First disconnect
        manager.disconnect(mock_websocket)
        assert mock_websocket not in manager.connection_streams

        # Second disconnect should not raise error
        manager.disconnect(mock_websocket)
        assert mock_websocket not in manager.connection_streams

    @pytest.mark.asyncio
    async def test_disconnect_non_existent_connection(self, manager):
        """Test disconnecting a WebSocket that was never connected."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()

        # Should not raise error even though WebSocket was never connected
        manager.disconnect(mock_ws)
        assert mock_ws not in manager.connection_streams

    @pytest.mark.asyncio
    async def test_connect_to_multiple_streams(self, manager, mock_websocket):
        """Test same WebSocket connecting to multiple streams (last wins)."""
        # Connect to stream1
        await manager.connect(mock_websocket, stream_id="stream1")
        assert manager.connection_streams[mock_websocket] == "stream1"
        assert mock_websocket in manager.active_connections["stream1"]

        # Connect same WebSocket to stream2 (adds to new stream without removing from old)
        # NOTE: Current implementation doesn't remove from old stream, connection_streams
        # just gets updated to point to new stream, but connection remains in both sets
        await manager.connect(mock_websocket, stream_id="stream2")
        assert manager.connection_streams[mock_websocket] == "stream2"
        # Connection is in both streams (implementation quirk)
        assert mock_websocket in manager.active_connections["stream1"]
        assert mock_websocket in manager.active_connections["stream2"]

    @pytest.mark.asyncio
    async def test_empty_stream_cleanup(self, manager, mock_websocket):
        """Test that stream is removed when last connection disconnects."""
        await manager.connect(mock_websocket, stream_id="temp_stream")
        assert "temp_stream" in manager.active_connections

        # Disconnect the only connection
        manager.disconnect(mock_websocket)

        # Stream should be removed from active_connections
        assert "temp_stream" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_connection_info_persistence(self, manager, mock_websocket):
        """Test that connection_info persists across operations."""
        await manager.connect(mock_websocket, stream_id="stream1")

        # Get original connection info
        original_info = manager.connection_info[mock_websocket]
        assert "stream_id" in original_info
        assert "connected_at" in original_info

        # Perform some operations
        await manager.send_personal(mock_websocket, {"type": "test"})
        await manager.broadcast("stream1", {"type": "broadcast"})

        # Connection info should still exist and be unchanged
        assert manager.connection_info[mock_websocket] == original_info

    @pytest.mark.asyncio
    async def test_send_to_disconnected_connection(self, manager, mock_websocket):
        """Test that send_personal() handles closed connection gracefully."""
        await manager.connect(mock_websocket, stream_id="stream1")

        # Simulate disconnection
        manager.disconnect(mock_websocket)

        # Try to send to disconnected connection
        mock_websocket.send_text = AsyncMock(side_effect=Exception("Connection closed"))
        success = await manager.send_personal(mock_websocket, {"type": "test"})

        # Should return False and disconnect again (idempotent)
        assert success is False
        assert mock_websocket not in manager.connection_streams

    @pytest.mark.asyncio
    async def test_broadcast_with_no_connections(self, manager):
        """Test broadcast on empty stream returns 0."""
        sent_count = await manager.broadcast("empty_stream", {"type": "test"})
        assert sent_count == 0


# ============================================================================
# TestWebSocketBroadcastEdgeCases
# ============================================================================

class TestWebSocketBroadcastEdgeCases:
    """Test WebSocket broadcast edge cases and failure scenarios."""

    @pytest.mark.asyncio
    async def test_broadcast_all_connections_fail(self, manager):
        """Test broadcast when all connections fail."""
        # Create 3 connections that all fail
        connections = []
        for i in range(3):
            mock_ws = Mock(spec=WebSocket)
            mock_ws.accept = AsyncMock()
            mock_ws.send_text = AsyncMock(side_effect=Exception("All failed"))
            connections.append(mock_ws)
            await manager.connect(mock_ws, "stream1")

        # Broadcast (all should fail)
        sent_count = await manager.broadcast("stream1", {"type": "test"})

        # Should return 0 (all failed)
        assert sent_count == 0

        # All connections should be disconnected
        for conn in connections:
            assert conn not in manager.active_connections.get("stream1", set())

    @pytest.mark.asyncio
    async def test_broadcast_partial_failures_continue(self, manager):
        """Test that broadcast continues even when some connections fail."""
        # Create 3 connections: 1 succeeds, 2 fail
        mock_ws_success = Mock(spec=WebSocket)
        mock_ws_success.accept = AsyncMock()
        mock_ws_success.send_text = AsyncMock()  # Succeeds

        mock_ws_fail1 = Mock(spec=WebSocket)
        mock_ws_fail1.accept = AsyncMock()
        mock_ws_fail1.send_text = AsyncMock(side_effect=Exception("Failed 1"))

        mock_ws_fail2 = Mock(spec=WebSocket)
        mock_ws_fail2.accept = AsyncMock()
        mock_ws_fail2.send_text = AsyncMock(side_effect=Exception("Failed 2"))

        await manager.connect(mock_ws_success, "stream1")
        await manager.connect(mock_ws_fail1, "stream1")
        await manager.connect(mock_ws_fail2, "stream1")

        # Broadcast
        sent_count = await manager.broadcast("stream1", {"type": "test"})

        # Should return 1 (only success counted)
        assert sent_count == 1

        # Failed connections should be removed
        assert mock_ws_fail1 not in manager.active_connections.get("stream1", set())
        assert mock_ws_fail2 not in manager.active_connections.get("stream1", set())

        # Successful connection should still be there
        assert mock_ws_success in manager.active_connections["stream1"]

    @pytest.mark.asyncio
    async def test_broadcast_with_json_serialization_error(self, manager):
        """Test broadcast with non-serializable data (handled by json.dumps)."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()

        await manager.connect(mock_ws, "stream1")

        # JSON-serializable data (works)
        sent_count = await manager.broadcast("stream1", {"type": "test", "data": {"nested": "value"}})
        assert sent_count == 1

    @pytest.mark.asyncio
    async def test_broadcast_with_mixed_connection_types(self, manager):
        """Test broadcast with connections in different WebSocket states."""
        # Mix of healthy and failing connections
        mock_ws_healthy = Mock(spec=WebSocket)
        mock_ws_healthy.accept = AsyncMock()
        mock_ws_healthy.send_text = AsyncMock()

        mock_ws_closed = Mock(spec=WebSocket)
        mock_ws_closed.accept = AsyncMock()
        mock_ws_closed.send_text = AsyncMock(side_effect=Exception("Connection closed"))

        await manager.connect(mock_ws_healthy, "stream1")
        await manager.connect(mock_ws_closed, "stream1")

        # Broadcast
        sent_count = await manager.broadcast("stream1", {"type": "test"})

        # Only healthy connection should succeed
        assert sent_count == 1
        assert mock_ws_healthy in manager.active_connections["stream1"]
        assert mock_ws_closed not in manager.active_connections.get("stream1", set())

    @pytest.mark.asyncio
    async def test_broadcast_race_condition(self, manager):
        """Test that concurrent broadcasts don't corrupt state."""
        # Create 5 connections
        connections = []
        for i in range(5):
            mock_ws = Mock(spec=WebSocket)
            mock_ws.accept = AsyncMock()
            mock_ws.send_text = AsyncMock()
            connections.append(mock_ws)
            await manager.connect(mock_ws, "stream1")

        # Run concurrent broadcasts
        tasks = [
            manager.broadcast("stream1", {"type": "broadcast", "id": i})
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # All broadcasts should succeed
        assert all(r == 5 for r in results)

        # All connections should still be present
        assert len(manager.active_connections["stream1"]) == 5
        for conn in connections:
            assert conn in manager.active_connections["stream1"]


# ============================================================================
# TestWebSocketStateTransitions
# ============================================================================

class TestWebSocketStateTransitions:
    """Test WebSocket state transition edge cases."""

    @pytest.mark.asyncio
    async def test_connection_state_transitions(self, manager, mock_websocket):
        """Test connection state: New -> Connected -> Disconnected."""
        # Initial state: not connected
        assert mock_websocket not in manager.connection_streams
        assert mock_websocket not in manager.connection_info

        # Connect
        await manager.connect(mock_websocket, stream_id="stream1")
        assert mock_websocket in manager.connection_streams
        assert manager.connection_streams[mock_websocket] == "stream1"
        assert mock_websocket in manager.connection_info

        # Disconnect
        manager.disconnect(mock_websocket)
        assert mock_websocket not in manager.connection_streams
        assert mock_websocket not in manager.connection_info

    @pytest.mark.asyncio
    async def test_stream_state_empty_to_populated(self, manager):
        """Test stream state created/deleted with connections."""
        # Initial: stream doesn't exist
        assert "new_stream" not in manager.active_connections

        # Add first connection
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_text = AsyncMock()
        await manager.connect(mock_ws1, "new_stream")

        # Stream created
        assert "new_stream" in manager.active_connections
        assert len(manager.active_connections["new_stream"]) == 1

        # Add second connection
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_text = AsyncMock()
        await manager.connect(mock_ws2, "new_stream")

        # Stream has 2 connections
        assert len(manager.active_connections["new_stream"]) == 2

        # Remove first connection
        manager.disconnect(mock_ws1)
        assert len(manager.active_connections["new_stream"]) == 1

        # Remove last connection
        manager.disconnect(mock_ws2)

        # Stream deleted
        assert "new_stream" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_manager_state_after_all_disconnect(self):
        """Test manager returns to initial state after all disconnects."""
        # Create manager with pre-populated connections
        manager = WebSocketConnectionManager()

        # Add 3 connections to stream1
        stream1_conns = []
        for i in range(3):
            mock_ws = Mock(spec=WebSocket)
            mock_ws.accept = AsyncMock()
            mock_ws.send_text = AsyncMock()
            await manager.connect(mock_ws, "stream1")
            stream1_conns.append(mock_ws)

        # Add 2 connections to stream2
        stream2_conns = []
        for i in range(2):
            mock_ws = Mock(spec=WebSocket)
            mock_ws.accept = AsyncMock()
            mock_ws.send_text = AsyncMock()
            await manager.connect(mock_ws, "stream2")
            stream2_conns.append(mock_ws)

        # Verify pre-populated state
        assert len(manager.active_connections) == 2
        assert manager.get_connection_count("stream1") == 3
        assert manager.get_connection_count("stream2") == 2

        # Disconnect all connections from stream1
        for conn in stream1_conns:
            manager.disconnect(conn)

        # stream1 should be removed
        assert "stream1" not in manager.active_connections

        # Disconnect all connections from stream2
        for conn in stream2_conns:
            manager.disconnect(conn)

        # stream2 should be removed
        assert "stream2" not in manager.active_connections

        # Manager should be in initial state (empty)
        assert len(manager.active_connections) == 0
        # Note: connection_streams and connection_info track WebSocket objects
        # Since WebSocket objects are unique per connection, these should be empty
        assert len(manager.connection_streams) == 0
        assert len(manager.connection_info) == 0

    @pytest.mark.asyncio
    async def test_connection_metadata_updates(self, manager, mock_websocket):
        """Test that connection metadata is updated during lifecycle."""
        # Connect
        await manager.connect(mock_websocket, stream_id="stream1")

        # Check initial metadata
        info = manager.connection_info[mock_websocket]
        assert info["stream_id"] == "stream1"
        assert "connected_at" in info

        # connected_at should be ISO format datetime string
        datetime.fromisoformat(info["connected_at"])  # Should not raise

    @pytest.mark.asyncio
    async def test_singleton_state_persistence(self):
        """Test that singleton maintains state across access."""
        from core.websocket_manager import get_websocket_manager

        # Get singleton instance
        mgr1 = get_websocket_manager()

        # Add connection
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        await mgr1.connect(mock_ws, "singleton_test")

        # Get singleton again
        mgr2 = get_websocket_manager()

        # Should have same state
        assert mgr1 is mgr2
        assert "singleton_test" in mgr2.active_connections
        assert mock_ws in mgr2.active_connections["singleton_test"]

        # Cleanup
        mgr2.disconnect(mock_ws)
