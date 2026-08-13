"""Coverage wave 81 — core/websocket_manager.py (97% → 100%).

The pre-existing unit suite covers the lifecycle/API surface; the last gap was
the broadcast except branch (the old test triggered the failure during the
connect welcome send, so the broadcast loop's error path never executed) plus
channel-isolation semantics (no cross-stream leakage) and workspace broadcast
edge cases.
"""
import json
from unittest.mock import AsyncMock, Mock

import pytest

from core.websocket_manager import (
    DebuggingWebSocketManager,
    WebSocketConnectionManager,
)


def _ws(send_behavior=None):
    ws = Mock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock(side_effect=send_behavior)
    return ws


@pytest.mark.asyncio
async def test_broadcast_send_failure_skips_and_disconnects():
    """Broadcast must tolerate a dead connection mid-loop (lines 132-134):
    count only successful sends, drop the failed one, keep the stream."""
    manager = WebSocketConnectionManager()
    good = _ws()
    bad = _ws(send_behavior=[None, Exception("connection reset")])
    await manager.connect(good, "s1")
    await manager.connect(bad, "s1")

    sent = await manager.broadcast("s1", {"type": "update"})

    assert sent == 1
    assert good in manager.active_connections["s1"]
    assert bad not in manager.active_connections["s1"]
    assert manager.connection_streams.get(bad) is None
    assert manager.connection_info.get(bad) is None


@pytest.mark.asyncio
async def test_broadcast_send_failure_all_connections_dropped():
    manager = WebSocketConnectionManager()
    bad1 = _ws(send_behavior=[None, Exception("x")])
    bad2 = _ws(send_behavior=[None, Exception("y")])
    await manager.connect(bad1, "s2")
    await manager.connect(bad2, "s2")

    sent = await manager.broadcast("s2", {"type": "update"})

    assert sent == 0
    assert "s2" not in manager.active_connections


@pytest.mark.asyncio
async def test_broadcast_does_not_leak_across_streams():
    """Channel isolation: a broadcast to one stream must never reach a
    connection subscribed to a different stream."""
    manager = WebSocketConnectionManager()
    a = _ws()
    b = _ws()
    await manager.connect(a, "debug_session_1")
    await manager.connect(b, "debug_session_2")
    a.send_text.reset_mock()
    b.send_text.reset_mock()

    sent = await manager.broadcast("debug_session_1", {"type": "evt"})

    assert sent == 1
    assert a.send_text.call_count == 1
    assert b.send_text.call_count == 0


@pytest.mark.asyncio
async def test_debug_notify_does_not_leak_between_sessions():
    manager = WebSocketConnectionManager()
    debug = DebuggingWebSocketManager(manager)
    a = _ws()
    b = _ws()
    await manager.connect(a, "debug_session_s1")
    await manager.connect(b, "debug_session_s2")
    a.send_text.reset_mock()
    b.send_text.reset_mock()

    sent = await debug.notify_variable_changed("s1", "x", 1)

    assert sent == 1
    assert b.send_text.call_count == 0
    message = json.loads(a.send_text.call_args[0][0])
    assert message["type"] == "variable_changed"
    assert message["session_id"] == "s1"


@pytest.mark.asyncio
async def test_workspace_stream_prefix_matches_connect():
    manager = WebSocketConnectionManager()
    ws = _ws()
    await manager.connect(ws, "workspace_w1")

    sent = await manager.broadcast_to_workspace("w1", {"type": "update"})

    assert sent == 1
    message = json.loads(ws.send_text.call_args[0][0])
    assert message["type"] == "update"


@pytest.mark.asyncio
async def test_workspace_broadcast_no_connections_zero():
    manager = WebSocketConnectionManager()
    assert await manager.broadcast_to_workspace("ghost", {"type": "u"}) == 0


@pytest.mark.asyncio
async def test_debug_stream_trace_message_shape():
    manager = WebSocketConnectionManager()
    debug = DebuggingWebSocketManager(manager)
    ws = _ws()
    await manager.connect(ws, "trace_e1_s1")
    ws.send_text.reset_mock()

    sent = await debug.stream_trace("e1", "s1", {"node": "n1"})

    assert sent == 1
    message = json.loads(ws.send_text.call_args[0][0])
    assert message["type"] == "trace_update"
    assert message["execution_id"] == "e1"
    assert message["session_id"] == "s1"
    assert message["trace"] == {"node": "n1"}


@pytest.mark.asyncio
async def test_debug_breakpoint_and_step_messages():
    manager = WebSocketConnectionManager()
    debug = DebuggingWebSocketManager(manager)
    ws = _ws()
    await manager.connect(ws, "debug_session_s1")
    ws.send_text.reset_mock()

    await debug.notify_breakpoint_hit("s1", "bp1", "n1", 2)
    bp = json.loads(ws.send_text.call_args[0][0])
    assert bp["breakpoint"] == {"id": "bp1", "node_id": "n1", "hit_count": 2}

    ws.send_text.reset_mock()
    await debug.notify_step_completed("s1", "step_over", 4, "n2")
    step = json.loads(ws.send_text.call_args[0][0])
    assert step["type"] == "step_completed"
    assert step["action"] == "step_over"
    assert step["step_number"] == 4
    assert step["node_id"] == "n2"


@pytest.mark.asyncio
async def test_debug_session_state_messages():
    manager = WebSocketConnectionManager()
    debug = DebuggingWebSocketManager(manager)
    ws = _ws()
    await manager.connect(ws, "debug_session_s1")
    ws.send_text.reset_mock()

    await debug.notify_session_resumed("s1")
    resumed = json.loads(ws.send_text.call_args[0][0])
    assert resumed["type"] == "session_resumed"
    assert resumed["session_id"] == "s1"

    ws.send_text.reset_mock()
    await debug.notify_session_paused("s1", "breakpoint_hit", "n3")
    paused = json.loads(ws.send_text.call_args[0][0])
    assert paused["type"] == "session_paused"
    assert paused["reason"] == "breakpoint_hit"
    assert paused["node_id"] == "n3"


@pytest.mark.asyncio
async def test_connect_welcome_failure_does_not_raise():
    """connect() must tolerate a failed welcome send (send_personal swallows
    errors and cleans up the failed connection)."""
    manager = WebSocketConnectionManager()
    ws = _ws(send_behavior=Exception("welcome failed"))
    await manager.connect(ws, "s3")
    assert "s3" not in manager.active_connections
    assert manager.connection_streams.get(ws) is None
