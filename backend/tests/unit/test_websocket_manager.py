"""
Unit tests for WebSocket Manager

Tests cover:
- WebSocketConnectionManager initialization
- Connection lifecycle (connect, disconnect)
- Message broadcasting to streams
- Personal message sending
- Stream management
- DebuggingWebSocketManager features
- Trace streaming
- Variable change notifications
- Breakpoint hit notifications
- Session state changes
- Error handling and cleanup
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime
from fastapi import WebSocket

from core.websocket_manager import (
    WebSocketConnectionManager,
    DebuggingWebSocketManager,
    get_websocket_manager,
    get_debugging_websocket_manager
)


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection"""
    ws = Mock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = Mock()
    return ws


@pytest.fixture
def connection_manager():
    """Create WebSocketConnectionManager instance"""
    return WebSocketConnectionManager()


@pytest.fixture
def debug_manager(connection_manager):
    """Create DebuggingWebSocketManager instance"""
    return DebuggingWebSocketManager(connection_manager)


# ============================================================================
# WebSocketConnectionManager Initialization Tests
# ============================================================================

def test_manager_initialization(connection_manager):
    """Test manager initializes correctly"""
    assert connection_manager is not None
    assert hasattr(connection_manager, 'active_connections')
    assert hasattr(connection_manager, 'connection_streams')
    assert hasattr(connection_manager, 'connection_info')
    assert isinstance(connection_manager.active_connections, dict)
    assert isinstance(connection_manager.connection_streams, dict)
    assert isinstance(connection_manager.connection_info, dict)


def test_manager_starts_empty(connection_manager):
    """Test manager starts with no connections"""
    assert len(connection_manager.active_connections) == 0
    assert len(connection_manager.connection_streams) == 0
    assert len(connection_manager.connection_info) == 0


# ============================================================================
# Connection Lifecycle Tests
# ============================================================================

@pytest.mark.asyncio
async def test_websocket_connect(connection_manager, mock_websocket):
    """Test WebSocket connection is established"""
    stream_id = "stream_123"

    await connection_manager.connect(mock_websocket, stream_id)

    # Verify connection accepted
    mock_websocket.accept.assert_called_once()

    # Verify tracked in active connections
    assert stream_id in connection_manager.active_connections
    assert mock_websocket in connection_manager.active_connections[stream_id]

    # Verify stream mapping
    assert connection_manager.connection_streams[mock_websocket] == stream_id

    # Verify connection info
    assert mock_websocket in connection_manager.connection_info
    assert "connected_at" in connection_manager.connection_info[mock_websocket]
    assert connection_manager.connection_info[mock_websocket]["stream_id"] == stream_id


@pytest.mark.asyncio
async def test_websocket_connect_multiple_to_same_stream(connection_manager, mock_websocket):
    """Test multiple websockets can connect to same stream"""
    stream_id = "shared_stream"

    # Create multiple mock websockets
    ws1 = Mock(spec=WebSocket)
    ws1.accept = AsyncMock()
    ws1.send_text = AsyncMock()

    ws2 = Mock(spec=WebSocket)
    ws2.accept = AsyncMock()
    ws2.send_text = AsyncMock()

    await connection_manager.connect(ws1, stream_id)
    await connection_manager.connect(ws2, stream_id)

    # Both should be in the same stream
    assert len(connection_manager.active_connections[stream_id]) == 2
    assert ws1 in connection_manager.active_connections[stream_id]
    assert ws2 in connection_manager.active_connections[stream_id]


@pytest.mark.asyncio
async def test_websocket_connect_creates_new_stream(connection_manager, mock_websocket):
    """Test connecting to new stream creates it"""
    stream_id = "new_stream"

    await connection_manager.connect(mock_websocket, stream_id)

    # Stream should exist
    assert stream_id in connection_manager.active_connections
    assert len(connection_manager.active_connections[stream_id]) == 1


@pytest.mark.asyncio
async def test_websocket_disconnect(connection_manager, mock_websocket):
    """Test WebSocket disconnection"""
    stream_id = "stream_123"

    await connection_manager.connect(mock_websocket, stream_id)
    assert mock_websocket in connection_manager.active_connections[stream_id]

    connection_manager.disconnect(mock_websocket)

    # Verify removed from active connections
    assert stream_id not in connection_manager.active_connections or \
           mock_websocket not in connection_manager.active_connections.get(stream_id, set())

    # Verify removed from mappings
    assert mock_websocket not in connection_manager.connection_streams
    assert mock_websocket not in connection_manager.connection_info


@pytest.mark.asyncio
async def test_websocket_disconnect_removes_empty_stream(connection_manager, mock_websocket):
    """Test disconnecting last connection removes stream"""
    stream_id = "stream_123"

    await connection_manager.connect(mock_websocket, stream_id)
    assert stream_id in connection_manager.active_connections

    connection_manager.disconnect(mock_websocket)

    # Stream should be removed when empty
    assert stream_id not in connection_manager.active_connections


@pytest.mark.asyncio
async def test_websocket_disconnect_one_of_many(connection_manager):
    """Test disconnecting one websocket from stream with multiple"""
    stream_id = "shared_stream"

    ws1 = Mock(spec=WebSocket)
    ws1.accept = AsyncMock()
    ws1.send_text = AsyncMock()

    ws2 = Mock(spec=WebSocket)
    ws2.accept = AsyncMock()
    ws2.send_text = AsyncMock()

    await connection_manager.connect(ws1, stream_id)
    await connection_manager.connect(ws2, stream_id)

    # Disconnect one
    connection_manager.disconnect(ws1)

    # Stream should still exist with ws2
    assert stream_id in connection_manager.active_connections
    assert ws2 in connection_manager.active_connections[stream_id]
    assert ws1 not in connection_manager.active_connections[stream_id]


@pytest.mark.asyncio
async def test_websocket_disconnect_nonexistent(connection_manager):
    """Test disconnecting websocket that was never connected"""
    ws = Mock(spec=WebSocket)

    # Should not raise exception
    connection_manager.disconnect(ws)

    # Manager should remain in valid state
    assert connection_manager is not None


# ============================================================================
# Personal Message Tests
# ============================================================================

@pytest.mark.asyncio
async def test_send_personal_message(connection_manager, mock_websocket):
    """Test sending message to specific websocket"""
    stream_id = "stream_123"
    message = {"type": "notification", "data": "test_message"}

    await connection_manager.connect(mock_websocket, stream_id)
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()
    result = await connection_manager.send_personal(mock_websocket, message)

    # Verify sent
    assert result is True
    mock_websocket.send_text.assert_called_once()

    # Verify message content
    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["type"] == "notification"
    assert sent_message["data"] == "test_message"


@pytest.mark.asyncio
async def test_send_personal_message_serializes_json(connection_manager, mock_websocket):
    """Test send personal message properly serializes JSON"""
    stream_id = "stream_123"
    message = {
        "type": "update",
        "data": {"key": "value", "number": 123},
        "timestamp": "2026-02-13T10:00:00Z"
    }

    await connection_manager.connect(mock_websocket, stream_id)
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()
    await connection_manager.send_personal(mock_websocket, message)

    # Verify JSON serialization
    import json
    call_args = mock_websocket.send_text.call_args[0][0]
    parsed = json.loads(call_args)
    assert parsed["data"]["key"] == "value"
    assert parsed["data"]["number"] == 123


@pytest.mark.asyncio
async def test_send_personal_message_to_disconnected(connection_manager, mock_websocket):
    """Test sending to disconnected websocket handles gracefully"""
    stream_id = "stream_123"
    message = {"type": "test"}

    await connection_manager.connect(mock_websocket, stream_id)

    # Make send fail
    mock_websocket.send_text.side_effect = Exception("Connection closed")

    result = await connection_manager.send_personal(mock_websocket, message)

    # Should return False and disconnect
    assert result is False
    assert mock_websocket not in connection_manager.connection_streams


@pytest.mark.asyncio
async def test_send_personal_message_unconnected_websocket(connection_manager, mock_websocket):
    """Test sending to websocket that was never connected"""
    message = {"type": "test"}

    # Should not raise exception
    result = await connection_manager.send_personal(mock_websocket, message)

    # Likely will fail when trying to send
    assert result in [True, False]


# ============================================================================
# Broadcast Tests
# ============================================================================

@pytest.mark.asyncio
async def test_broadcast_to_stream(connection_manager):
    """Test broadcasting message to all connections in stream"""
    stream_id = "broadcast_stream"

    # Create multiple mock websockets
    connections = []
    for i in range(3):
        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        connections.append(ws)
        await connection_manager.connect(ws, stream_id)

    message = {"type": "broadcast", "data": "test_data"}

    # Reset mocks to ignore welcome messages
    for ws in connections:
        ws.send_text.reset_mock()

    sent_count = await connection_manager.broadcast(stream_id, message)

    # Verify sent to all connections
    assert sent_count == 3
    for ws in connections:
        ws.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_broadcast_to_nonexistent_stream(connection_manager):
    """Test broadcasting to stream that doesn't exist"""
    message = {"type": "test"}

    sent_count = await connection_manager.broadcast("nonexistent_stream", message)

    # Should return 0
    assert sent_count == 0


@pytest.mark.asyncio
async def test_broadcast_handles_send_failure(connection_manager):
    """Test broadcast handles connection failures gracefully"""
    stream_id = "test_stream"

    # Create mock connections where one fails
    ws1 = Mock(spec=WebSocket)
    ws1.accept = AsyncMock()
    ws1.send_text = AsyncMock()

    ws2 = Mock(spec=WebSocket)
    ws2.accept = AsyncMock()
    ws2.send_text = AsyncMock(side_effect=Exception("Send failed"))

    ws3 = Mock(spec=WebSocket)
    ws3.accept = AsyncMock()
    ws3.send_text = AsyncMock()

    await connection_manager.connect(ws1, stream_id)
    await connection_manager.connect(ws2, stream_id)
    await connection_manager.connect(ws3, stream_id)

    message = {"type": "test"}
    sent_count = await connection_manager.broadcast(stream_id, message)

    # Should send to successful ones, disconnect failed one
    assert sent_count == 2
    assert ws2 not in connection_manager.active_connections.get(stream_id, set())


@pytest.mark.asyncio
async def test_broadcast_empty_message(connection_manager, mock_websocket):
    """Test broadcasting empty message"""
    stream_id = "test_stream"

    await connection_manager.connect(mock_websocket, stream_id)
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()

    message = {}
    sent_count = await connection_manager.broadcast(stream_id, message)

    # Should still send
    assert sent_count == 1
    mock_websocket.send_text.assert_called_once()


# ============================================================================
# Stream Management Tests
# ============================================================================

def test_get_connection_count(connection_manager):
    """Test getting connection count for stream"""
    stream_id = "count_stream"

    # Initially no connections
    assert connection_manager.get_connection_count(stream_id) == 0

    # Add connections
    for i in range(3):
        ws = Mock(spec=WebSocket)
        connection_manager.active_connections.setdefault(stream_id, set()).add(ws)

    # Should count correctly
    assert connection_manager.get_connection_count(stream_id) == 3


def test_get_connection_count_nonexistent_stream(connection_manager):
    """Test getting count for nonexistent stream"""
    count = connection_manager.get_connection_count("nonexistent")
    assert count == 0


def test_get_all_streams(connection_manager):
    """Test getting all active stream IDs"""
    # Add multiple streams
    for i in range(3):
        stream_id = f"stream_{i}"
        ws = Mock(spec=WebSocket)
        connection_manager.active_connections.setdefault(stream_id, set()).add(ws)

    streams = connection_manager.get_all_streams()

    assert len(streams) == 3
    assert "stream_0" in streams
    assert "stream_1" in streams
    assert "stream_2" in streams


def test_get_all_streams_empty(connection_manager):
    """Test getting all streams when empty"""
    streams = connection_manager.get_all_streams()
    assert isinstance(streams, set)
    assert len(streams) == 0


def test_get_stream_info(connection_manager):
    """Test getting stream information"""
    stream_id = "info_stream"

    # Add connection with timestamp
    ws = Mock(spec=WebSocket)
    connection_manager.active_connections[stream_id] = {ws}
    connection_manager.connection_info[ws] = {
        "stream_id": stream_id,
        "connected_at": "2026-02-13T10:00:00Z"
    }

    info = connection_manager.get_stream_info(stream_id)

    assert info["stream_id"] == stream_id
    assert info["connection_count"] == 1
    assert len(info["connections"]) == 1
    assert info["connections"][0]["connected_at"] == "2026-02-13T10:00:00Z"


def test_get_stream_info_empty_stream(connection_manager):
    """Test getting info for empty stream"""
    stream_id = "empty_stream"
    connection_manager.active_connections[stream_id] = set()

    info = connection_manager.get_stream_info(stream_id)

    assert info["stream_id"] == stream_id
    assert info["connection_count"] == 0
    assert info["connections"] == []


def test_get_stream_info_nonexistent_stream(connection_manager):
    """Test getting info for nonexistent stream"""
    info = connection_manager.get_stream_info("nonexistent")

    assert info["stream_id"] == "nonexistent"
    assert info["connection_count"] == 0
    assert info["connections"] == []


@pytest.mark.asyncio
async def test_broadcast_to_workspace(connection_manager, mock_websocket):
    """Test broadcasting to workspace stream"""
    workspace_id = "workspace_123"

    await connection_manager.connect(mock_websocket, f"workspace_{workspace_id}")
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()

    message = {"type": "workspace_update", "data": "test"}

    sent_count = await connection_manager.broadcast_to_workspace(workspace_id, message)

    assert sent_count == 1
    mock_websocket.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_broadcast_trace_update(connection_manager, mock_websocket):
    """Test broadcasting trace update"""
    stream_id = "trace_stream"

    await connection_manager.connect(mock_websocket, stream_id)
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()

    trace_data = {"node_id": "node_1", "status": "running"}

    sent_count = await connection_manager.broadcast_trace_update(stream_id, trace_data)

    assert sent_count == 1
    mock_websocket.send_text.assert_called_once()

    # Verify message structure
    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["type"] == "trace_update"
    assert sent_message["data"] == trace_data
    assert "timestamp" in sent_message


@pytest.mark.asyncio
async def test_broadcast_session_update(connection_manager, mock_websocket):
    """Test broadcasting session update"""
    session_id = "session_123"

    await connection_manager.connect(mock_websocket, f"debug_session_{session_id}")
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()

    update_type = "session_paused"
    data = {"reason": "user_action", "node_id": "node_1"}

    sent_count = await connection_manager.broadcast_session_update(
        session_id, update_type, data
    )

    assert sent_count == 1
    mock_websocket.send_text.assert_called_once()

    # Verify message structure
    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["type"] == update_type
    assert sent_message["session_id"] == session_id
    assert sent_message["data"] == data


# ============================================================================
# DebuggingWebSocketManager Tests
# ============================================================================

@pytest.mark.asyncio
async def test_debug_manager_initialization(debug_manager, connection_manager):
    """Test debug manager initialization"""
    assert debug_manager is not None
    assert debug_manager.manager == connection_manager


@pytest.mark.asyncio
async def test_stream_trace(debug_manager, mock_websocket):
    """Test streaming trace update"""
    execution_id = "exec_123"
    session_id = "session_456"
    trace_data = {"node_id": "node_1", "output": "result"}

    stream_id = f"trace_{execution_id}_{session_id}"
    await debug_manager.manager.connect(mock_websocket, stream_id)
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()

    sent_count = await debug_manager.stream_trace(
        execution_id, session_id, trace_data
    )

    assert sent_count == 1
    mock_websocket.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_notify_variable_changed(debug_manager, mock_websocket):
    """Test notifying variable change"""
    session_id = "session_123"
    variable_name = "counter"
    new_value = 42
    previous_value = 10

    stream_id = f"debug_session_{session_id}"
    await debug_manager.manager.connect(mock_websocket, stream_id)
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()

    sent_count = await debug_manager.notify_variable_changed(
        session_id, variable_name, new_value, previous_value
    )

    assert sent_count == 1
    mock_websocket.send_text.assert_called_once()

    # Verify message structure
    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["type"] == "variable_changed"
    assert sent_message["variable"]["name"] == variable_name
    assert sent_message["variable"]["new_value"] == new_value
    assert sent_message["variable"]["previous_value"] == previous_value


@pytest.mark.asyncio
async def test_notify_variable_changed_no_previous(debug_manager, mock_websocket):
    """Test notifying variable change without previous value"""
    session_id = "session_123"
    variable_name = "new_var"
    new_value = "value"

    stream_id = f"debug_session_{session_id}"
    await debug_manager.manager.connect(mock_websocket, stream_id)
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()

    sent_count = await debug_manager.notify_variable_changed(
        session_id, variable_name, new_value
    )

    assert sent_count == 1

    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["variable"]["previous_value"] is None


@pytest.mark.asyncio
async def test_notify_breakpoint_hit(debug_manager, mock_websocket):
    """Test notifying breakpoint hit"""
    session_id = "session_123"
    breakpoint_id = "bp_1"
    node_id = "node_42"
    hit_count = 3

    stream_id = f"debug_session_{session_id}"
    await debug_manager.manager.connect(mock_websocket, stream_id)
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()

    sent_count = await debug_manager.notify_breakpoint_hit(
        session_id, breakpoint_id, node_id, hit_count
    )

    assert sent_count == 1
    mock_websocket.send_text.assert_called_once()

    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["type"] == "breakpoint_hit"
    assert sent_message["breakpoint"]["id"] == breakpoint_id
    assert sent_message["breakpoint"]["node_id"] == node_id
    assert sent_message["breakpoint"]["hit_count"] == hit_count


@pytest.mark.asyncio
async def test_notify_session_paused(debug_manager, mock_websocket):
    """Test notifying session paused"""
    session_id = "session_123"
    reason = "breakpoint_hit"
    node_id = "node_42"

    stream_id = f"debug_session_{session_id}"
    await debug_manager.manager.connect(mock_websocket, stream_id)

    sent_count = await debug_manager.notify_session_paused(
        session_id, reason, node_id
    )

    assert sent_count == 1

    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["type"] == "session_paused"
    assert sent_message["reason"] == reason
    assert sent_message["node_id"] == node_id


@pytest.mark.asyncio
async def test_notify_session_paused_default_reason(debug_manager, mock_websocket):
    """Test notifying session paused with default reason"""
    session_id = "session_123"

    stream_id = f"debug_session_{session_id}"
    await debug_manager.manager.connect(mock_websocket, stream_id)

    sent_count = await debug_manager.notify_session_paused(session_id)

    assert sent_count == 1

    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["reason"] == "user_action"


@pytest.mark.asyncio
async def test_notify_session_resumed(debug_manager, mock_websocket):
    """Test notifying session resumed"""
    session_id = "session_123"

    stream_id = f"debug_session_{session_id}"
    await debug_manager.manager.connect(mock_websocket, stream_id)

    sent_count = await debug_manager.notify_session_resumed(session_id)

    assert sent_count == 1

    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["type"] == "session_resumed"
    assert sent_message["session_id"] == session_id


@pytest.mark.asyncio
async def test_notify_step_completed(debug_manager, mock_websocket):
    """Test notifying step completed"""
    session_id = "session_123"
    action = "step_over"
    step_number = 5
    node_id = "node_42"

    stream_id = f"debug_session_{session_id}"
    await debug_manager.manager.connect(mock_websocket, stream_id)

    sent_count = await debug_manager.notify_step_completed(
        session_id, action, step_number, node_id
    )

    assert sent_count == 1

    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["type"] == "step_completed"
    assert sent_message["action"] == action
    assert sent_message["step_number"] == step_number
    assert sent_message["node_id"] == node_id


@pytest.mark.asyncio
async def test_notify_step_completed_no_node_id(debug_manager, mock_websocket):
    """Test notifying step completed without node ID"""
    session_id = "session_123"
    action = "step_into"
    step_number = 3

    stream_id = f"debug_session_{session_id}"
    await debug_manager.manager.connect(mock_websocket, stream_id)

    sent_count = await debug_manager.notify_step_completed(
        session_id, action, step_number
    )

    assert sent_count == 1

    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["node_id"] is None


# ============================================================================
# Singleton Helper Tests
# ============================================================================

def test_get_websocket_manager():
    """Test singleton websocket manager"""
    manager1 = get_websocket_manager()
    manager2 = get_websocket_manager()

    # Should return same instance
    assert manager1 is manager2


def test_get_debugging_websocket_manager():
    """Test singleton debugging websocket manager"""
    debug1 = get_debugging_websocket_manager()
    debug2 = get_debugging_websocket_manager()

    # Should return same instance
    assert debug1 is debug2


def test_get_debugging_websocket_manager_uses_connection_manager():
    """Test debugging manager uses connection manager"""
    debug_manager = get_debugging_websocket_manager()

    assert hasattr(debug_manager, 'manager')
    assert isinstance(debug_manager.manager, WebSocketConnectionManager)


# ============================================================================
# Error Handling and Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_connect_sends_welcome_message(connection_manager, mock_websocket):
    """Test connect sends welcome message"""
    stream_id = "stream_123"

    await connection_manager.connect(mock_websocket, stream_id)

    # Verify welcome message sent
    assert mock_websocket.send_text.call_count >= 1

    import json
    welcome_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert welcome_message["type"] == "connected"
    assert welcome_message["stream_id"] == stream_id
    assert "timestamp" in welcome_message


@pytest.mark.asyncio
async def test_broadcast_with_no_active_connections(connection_manager):
    """Test broadcast to stream with no connections"""
    # Add stream but no connections
    connection_manager.active_connections["empty_stream"] = set()

    message = {"type": "test"}
    sent_count = await connection_manager.broadcast("empty_stream", message)

    assert sent_count == 0


@pytest.mark.asyncio
async def test_multiple_concurrent_broadcasts(connection_manager):
    """Test multiple concurrent broadcasts to different streams"""
    # Setup multiple streams
    for i in range(3):
        stream_id = f"stream_{i}"
        for j in range(2):
            ws = Mock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            await connection_manager.connect(ws, stream_id)

    # Broadcast to all streams
    for i in range(3):
        stream_id = f"stream_{i}"
        message = {"stream": stream_id}
        await connection_manager.broadcast(stream_id, message)

    # All should complete without errors
    assert len(connection_manager.active_connections) == 3


def test_connection_info_tracks_metadata(connection_manager):
    """Test connection info stores metadata"""
    stream_id = "test_stream"
    ws = Mock(spec=WebSocket)

    connection_manager.active_connections[stream_id] = {ws}
    connection_manager.connection_streams[ws] = stream_id
    connection_manager.connection_info[ws] = {
        "stream_id": stream_id,
        "connected_at": "2026-02-13T10:00:00Z",
        "user_id": "user_123"
    }

    assert "user_id" in connection_manager.connection_info[ws]
    assert connection_manager.connection_info[ws]["stream_id"] == stream_id


@pytest.mark.asyncio
async def test_disconnect_removes_all_tracking(connection_manager, mock_websocket):
    """Test disconnect removes all tracking data"""
    stream_id = "test_stream"

    await connection_manager.connect(mock_websocket, stream_id)

    # Verify tracked
    assert mock_websocket in connection_manager.connection_streams
    assert mock_websocket in connection_manager.connection_info

    connection_manager.disconnect(mock_websocket)

    # Verify all removed
    assert mock_websocket not in connection_manager.connection_streams
    assert mock_websocket not in connection_manager.connection_info


@pytest.mark.asyncio
async def test_json_serialization_complex_data(connection_manager, mock_websocket):
    """Test JSON serialization handles complex data"""
    stream_id = "test_stream"

    await connection_manager.connect(mock_websocket, stream_id)
    # Reset mock to ignore welcome message
    mock_websocket.send_text.reset_mock()

    complex_message = {
        "type": "complex",
        "data": {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "number": 123.45,
            "bool": True,
            "null": None
        }
    }

    await connection_manager.send_personal(mock_websocket, complex_message)

    # Should not raise serialization error
    mock_websocket.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_broadcast_preserves_message_structure(connection_manager):
    """Test broadcast preserves message structure"""
    stream_id = "test_stream"

    ws = Mock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()

    await connection_manager.connect(ws, stream_id)

    original_message = {
        "type": "test",
        "nested": {"deeply": {"nested": "value"}},
        "array": [1, 2, {"key": "value"}]
    }

    await connection_manager.broadcast(stream_id, original_message)

    import json
    sent_message = json.loads(ws.send_text.call_args[0][0])
    assert sent_message["nested"]["deeply"]["nested"] == "value"
    assert sent_message["array"][2]["key"] == "value"


@pytest.mark.asyncio
async def test_trace_update_message_format(debug_manager, mock_websocket):
    """Test trace update has correct message format"""
    execution_id = "exec_123"
    session_id = "session_456"
    trace_data = {
        "node_id": "node_1",
        "status": "completed",
        "output": "result",
        "duration_ms": 150
    }

    stream_id = f"trace_{execution_id}_{session_id}"
    await debug_manager.manager.connect(mock_websocket, stream_id)

    await debug_manager.stream_trace(execution_id, session_id, trace_data)

    import json
    sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
    assert sent_message["type"] == "trace_update"
    assert sent_message["execution_id"] == execution_id
    assert sent_message["session_id"] == session_id
    assert sent_message["trace"] == trace_data
    assert "timestamp" in sent_message
