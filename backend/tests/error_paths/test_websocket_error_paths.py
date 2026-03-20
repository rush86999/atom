"""
WebSocket Error Paths Tests

Comprehensive error path testing for WebSocketConnectionManager.
Target: 75%+ coverage on error handling paths.

Tests cover:
- send_text exception handling (disconnects and returns False)
- WebSocket accept() failures
- JSON encoding errors (non-serializable data)
- Unicode character handling in messages
- Oversized message handling
- Special characters in stream_id
- WebSocket disconnect during broadcast
- Manager state consistency after exceptions
- send_personal exception handling

Follows error_paths directory pattern from test_edge_case_error_paths.py.
"""

import pytest
import json
from unittest.mock import AsyncMock, Mock
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

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


# ============================================================================
# TestWebSocketErrorPaths
# ============================================================================

class TestWebSocketErrorPaths:
    """Test WebSocket error handling paths."""

    @pytest.mark.asyncio
    async def test_send_text_raises_exception(self, manager, mock_websocket):
        """
        Test that exception in send_text disconnects and returns False.

        Expected behavior:
        - send_personal() catches Exception
        - Calls disconnect() to clean up
        - Returns False to indicate failure

        Error path: Line 102-108 in websocket_manager.py
        """
        await manager.connect(mock_websocket, stream_id="stream1")

        # Mock send_text to raise exception
        mock_websocket.send_text = AsyncMock(side_effect=Exception("Connection broken"))

        # Send personal should handle exception
        success = await manager.send_personal(mock_websocket, {"type": "test"})

        # Should return False
        assert success is False

        # WebSocket should be disconnected
        assert mock_websocket not in manager.connection_streams
        assert mock_websocket not in manager.connection_info

    @pytest.mark.asyncio
    async def test_accept_raises_exception(self, manager, mock_websocket):
        """
        Test that failed accept() is handled gracefully.

        Expected behavior:
        - connect() calls await websocket.accept()
        - If accept() raises exception, connection not established
        - Exception propagates (no try/catch in connect())

        Error path: Line 47 in websocket_manager.py (no exception handler)
        """
        # Mock accept to raise exception
        mock_websocket.accept = AsyncMock(side_effect=Exception("Accept failed"))

        # connect() should raise exception (no try/catch in production code)
        with pytest.raises(Exception, match="Accept failed"):
            await manager.connect(mock_websocket, stream_id="stream1")

        # Connection should not be established
        assert mock_websocket not in manager.connection_streams
        assert "stream1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_json_encode_error_falls_back_to_string(self, manager, mock_websocket):
        """
        Test that non-JSON data is handled by json.dumps().

        Expected behavior:
        - json.dumps() handles serialization
        - Non-serializable data raises TypeError in json.dumps
        - Manager's send_personal() catches exception and disconnects
        - Returns False to indicate failure

        Error path: Line 102-108 in websocket_manager.py (exception handler)
        """
        await manager.connect(mock_websocket, stream_id="stream1")

        # JSON-serializable data works
        success = await manager.send_personal(mock_websocket, {"type": "test", "data": [1, 2, 3]})
        assert success is True

        # Non-serializable data (e.g., function) causes json.dumps to fail
        # Manager catches the TypeError, disconnects, and returns False
        success = await manager.send_personal(mock_websocket, {"type": "function", "data": lambda x: x})

        # Should return False (exception caught, connection disconnected)
        assert success is False
        assert mock_websocket not in manager.connection_streams

    @pytest.mark.asyncio
    async def test_unicode_in_message(self, manager, mock_websocket):
        """
        Test that unicode characters in messages are handled correctly.

        Expected behavior:
        - Unicode characters (emoji, Chinese, accented) work fine
        - JSON supports UTF-8 encoding
        - No errors or data corruption

        Error path: None (unicode is supported)
        """
        await manager.connect(mock_websocket, stream_id="stream1")

        # Unicode message (emoji, Chinese, accented chars)
        unicode_message = {
            "type": "test",
            "text": "Hello 世界 🎉 café 日本語",
            "emoji": "😀 🚀 🎯",
        }

        success = await manager.send_personal(mock_websocket, unicode_message)

        # Should succeed
        assert success is True

        # Verify message was serialized correctly
        # Note: send_text is called twice (welcome message + actual message)
        # Check the last call (the actual message)
        assert mock_websocket.send_text.call_count == 2
        call_args = mock_websocket.send_text.call_args[0][0]
        decoded = json.loads(call_args)
        assert decoded["text"] == "Hello 世界 🎉 café 日本語"
        assert decoded["emoji"] == "😀 🚀 🎯"

    @pytest.mark.asyncio
    async def test_oversized_message(self, manager, mock_websocket):
        """
        Test that large messages are handled without crashing.

        Expected behavior:
        - Large messages (10KB+) are serialized and sent
        - No size limit in manager (WebSocket/transport layer handles this)
        - send_text may fail if message too large (handled by exception path)

        Error path: Line 102-108 (exception handler in send_personal)
        """
        await manager.connect(mock_websocket, stream_id="stream1")

        # Create large message (100KB)
        large_message = {
            "type": "large_data",
            "data": "x" * 100_000,
        }

        # Mock send_text to succeed even with large data
        success = await manager.send_personal(mock_websocket, large_message)

        # Should succeed (no size limit in manager)
        assert success is True

    @pytest.mark.asyncio
    async def test_invalid_stream_id_characters(self, manager, mock_websocket):
        """
        Test that special characters in stream_id are handled.

        Expected behavior:
        - stream_id is just a string key for dict lookups
        - Special characters work fine (no sanitization needed)
        - Unicode, spaces, special chars all supported

        Error path: None (stream_id is just a dict key)
        """
        # Test various special character stream_ids
        special_stream_ids = [
            "stream/with/slashes",
            "stream with spaces",
            "stream-with-dashes",
            "stream_with_underscores",
            "stream.with.dots",
            "stream:with:colons",
            "stream¡with§accents",
            "流ID中文",
            "🎉stream🎯",
        ]

        for stream_id in special_stream_ids:
            # Create fresh WebSocket for each test
            mock_ws = Mock(spec=WebSocket)
            mock_ws.accept = AsyncMock()
            mock_ws.send_text = AsyncMock()

            # Connect with special stream_id
            await manager.connect(mock_ws, stream_id=stream_id)

            # Should work fine
            assert stream_id in manager.active_connections
            assert manager.connection_streams[mock_ws] == stream_id

            # Broadcast should work
            sent_count = await manager.broadcast(stream_id, {"type": "test"})
            assert sent_count == 1

            # Cleanup
            manager.disconnect(mock_ws)


# ============================================================================
# TestWebSocketFailureModes
# ============================================================================

class TestWebSocketFailureModes:
    """Test WebSocket failure scenarios and recovery."""

    @pytest.mark.asyncio
    async def test_connection_dropped_during_broadcast(self, manager):
        """
        Test WebSocketDisconnect during broadcast.

        Expected behavior:
        - Connection raises WebSocketDisconnect or Exception
        - broadcast() catches exception, logs error, disconnects connection
        - Continues broadcasting to remaining connections

        Error path: Line 132-134 in websocket_manager.py
        """
        # Create 3 connections
        connections = []
        for i in range(3):
            mock_ws = Mock(spec=WebSocket)
            mock_ws.accept = AsyncMock()
            mock_ws.send_text = AsyncMock()
            connections.append(mock_ws)
            await manager.connect(mock_ws, "stream1")

        # Make second connection fail during broadcast
        connections[1].send_text = AsyncMock(side_effect=WebSocketDisconnect(1000))

        # Broadcast
        sent_count = await manager.broadcast("stream1", {"type": "test"})

        # Should succeed for 2 connections (one failed)
        assert sent_count == 2

        # Failed connection should be removed
        assert connections[1] not in manager.active_connections.get("stream1", set())

        # Other connections should still be there
        assert connections[0] in manager.active_connections["stream1"]
        assert connections[2] in manager.active_connections["stream1"]

    @pytest.mark.asyncio
    async def test_all_connections_fail(self, manager):
        """
        Test broadcast when all connections fail.

        Expected behavior:
        - All connections raise exceptions during send_text
        - broadcast() returns 0 (no successful sends)
        - All connections are disconnected

        Error path: Line 132-134 (exception handler in broadcast)
        """
        # Create 3 connections that all fail
        connections = []
        for i in range(3):
            mock_ws = Mock(spec=WebSocket)
            mock_ws.accept = AsyncMock()
            mock_ws.send_text = AsyncMock(side_effect=Exception("Connection lost"))
            connections.append(mock_ws)
            await manager.connect(mock_ws, "stream1")

        # Broadcast (all will fail)
        sent_count = await manager.broadcast("stream1", {"type": "test"})

        # Should return 0 (all failed)
        assert sent_count == 0

        # All connections should be removed
        for conn in connections:
            assert conn not in manager.active_connections.get("stream1", set())

    @pytest.mark.asyncio
    async def test_manager_state_after_exception(self, manager, mock_websocket):
        """
        Test that manager state is consistent after exception.

        Expected behavior:
        - Exception in send_text triggers disconnect
        - Manager cleans up all tracking structures
        - No orphaned references to failed connection
        - Manager ready for new connections

        Error path: Line 102-108 (disconnect on send failure)
        """
        # Connect and send successfully first
        await manager.connect(mock_websocket, stream_id="stream1")
        assert "stream1" in manager.active_connections

        # Track initial connection count
        initial_count = manager.get_connection_count("stream1")
        assert initial_count == 1

        # Make send fail
        mock_websocket.send_text = AsyncMock(side_effect=Exception("Send failed"))

        # Send should fail and disconnect
        success = await manager.send_personal(mock_websocket, {"type": "test"})
        assert success is False

        # Manager state should be consistent
        assert mock_websocket not in manager.connection_streams
        assert mock_websocket not in manager.connection_info
        assert manager.get_connection_count("stream1") == 0

        # Stream should be cleaned up
        assert "stream1" not in manager.active_connections

        # Manager should accept new connections
        new_ws = Mock(spec=WebSocket)
        new_ws.accept = AsyncMock()
        new_ws.send_text = AsyncMock()
        await manager.connect(new_ws, stream_id="stream1")
        assert manager.get_connection_count("stream1") == 1

    @pytest.mark.asyncio
    async def test_exception_in_send_personal(self, manager, mock_websocket):
        """
        Test exception handling in send_personal method.

        Expected behavior:
        - send_text raises exception
        - send_personal catches exception
        - Calls disconnect() to clean up
        - Returns False to indicate failure
        - Exception is logged (logger.error)

        Error path: Line 102-108 in websocket_manager.py
        """
        await manager.connect(mock_websocket, stream_id="stream1")

        # Verify connection established
        assert mock_websocket in manager.connection_streams

        # Mock send_text to raise exception
        mock_websocket.send_text = AsyncMock(side_effect=RuntimeError("Broken pipe"))

        # Send personal should handle exception gracefully
        success = await manager.send_personal(mock_websocket, {"type": "test"})

        # Should return False (not raise exception)
        assert success is False

        # Connection should be cleaned up
        assert mock_websocket not in manager.connection_streams
        assert mock_websocket not in manager.connection_info

        # Stream should be removed if this was the last connection
        assert "stream1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_exception_in_disconnect(self, manager, mock_websocket):
        """
        Test that disconnect() handles missing keys gracefully.

        Expected behavior:
        - disconnect() uses .get() and .pop(key, None)
        - No KeyError if connection not found
        - Safe to call disconnect() multiple times

        Error path: Line 77-89 in websocket_manager.py (defensive coding)
        """
        # Don't connect the WebSocket

        # Disconnect should not raise error even though never connected
        manager.disconnect(mock_websocket)

        # No exceptions, clean operation
        assert mock_websocket not in manager.connection_streams

        # Call disconnect again (idempotent)
        manager.disconnect(mock_websocket)

    @pytest.mark.asyncio
    async def test_multiple_failures_in_broadcast(self, manager):
        """
        Test broadcast with multiple connection failures.

        Expected behavior:
        - Multiple connections fail during broadcast
        - Each failure is caught and logged
        - Failed connections are disconnected
        - Successful connections receive message
        - Returns count of successful sends

        Error path: Line 128-134 (exception handling in broadcast loop)
        """
        # Create 5 connections
        connections = []
        for i in range(5):
            mock_ws = Mock(spec=WebSocket)
            mock_ws.accept = AsyncMock()
            mock_ws.send_text = AsyncMock()
            connections.append(mock_ws)
            await manager.connect(mock_ws, "stream1")

        # Make connections 1, 3 fail (indices 1, 3)
        connections[1].send_text = AsyncMock(side_effect=Exception("Failed 1"))
        connections[3].send_text = AsyncMock(side_effect=Exception("Failed 3"))

        # Broadcast
        sent_count = await manager.broadcast("stream1", {"type": "test"})

        # Should succeed for 3 connections (0, 2, 4)
        assert sent_count == 3

        # Failed connections should be removed
        assert connections[1] not in manager.active_connections.get("stream1", set())
        assert connections[3] not in manager.active_connections.get("stream1", set())

        # Successful connections should still be there
        assert connections[0] in manager.active_connections["stream1"]
        assert connections[2] in manager.active_connections["stream1"]
        assert connections[4] in manager.active_connections["stream1"]

    @pytest.mark.asyncio
    async def test_exception_in_get_stream_info(self, manager):
        """
        Test get_stream_info with non-existent stream.

        Expected behavior:
        - get() returns empty set for missing stream
        - Returns dict with stream_id and zero connection_count
        - No exceptions raised

        Error path: Line 220-231 (defensive coding with .get())
        """
        # Non-existent stream
        info = manager.get_stream_info("non_existent_stream")

        # Should return valid structure
        assert info["stream_id"] == "non_existent_stream"
        assert info["connection_count"] == 0
        assert info["connections"] == []

        # No exceptions raised

    @pytest.mark.asyncio
    async def test_get_connection_count_with_missing_stream(self, manager):
        """
        Test get_connection_count with missing stream.

        Expected behavior:
        - Returns 0 for missing streams
        - No exceptions raised

        Error path: Line 199 (defensive coding with .get())
        """
        count = manager.get_connection_count("missing_stream")
        assert count == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_non_existent_stream(self, manager):
        """
        Test broadcast to stream that doesn't exist.

        Expected behavior:
        - Returns 0 (no connections to send to)
        - No exceptions raised
        - No streams created

        Error path: Line 121-122 (early return for missing stream)
        """
        sent_count = await manager.broadcast("non_existent", {"type": "test"})

        assert sent_count == 0
        assert "non_existent" not in manager.active_connections
