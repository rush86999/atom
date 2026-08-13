# -*- coding: utf-8 -*-
"""Coverage wave 87 — core/satellite_service (standalone, zero LLM spend,
no network, no real DB).

- Singleton: SatelliteService() identity + module-level instance.
- connect: accepts + registers per tenant; replaces an existing socket for the
  same tenant (H5 fix — old.close awaited); old close raising still replaces;
  keeps distinct tenants side by side.
- disconnect: removes registered tenant; removing an unknown tenant is a no-op.
- execute_local_tool: no connection → error dict; success path (uuid request
  id, pending future resolved via handle_message tool_result, response
  returned, pending entry cleaned up); timeout → error dict; send_json failure
  → error dict; pending future still cleaned after failures.
- handle_message: tool_result resolves only pending/undone futures (unknown id
  ignored, already-done future not re-set); heartbeat no-op; identify registers
  node via device_node_service with get_db_session and db.close; identify DB
  failure is swallowed (logged); unknown message types ignored.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.satellite_service import SatelliteService, satellite_service


@pytest.fixture()
def svc():
    """Fresh singleton with cleared state."""
    SatelliteService._instance = None
    instance = SatelliteService()
    instance.active_connections = {}
    instance.pending_requests = {}
    yield instance


class TestSingleton:
    def test_same_instance(self):
        assert SatelliteService() is satellite_service

    def test_instance_initializes_state(self):
        assert isinstance(satellite_service.active_connections, dict)
        assert isinstance(satellite_service.pending_requests, dict)


class TestConnect:
    def test_connect_registers_tenant(self, svc):
        ws = AsyncMock()
        asyncio.run(svc.connect(ws, "tenant-1"))
        ws.accept.assert_awaited_once()
        assert svc.active_connections["tenant-1"] is ws

    def test_connect_replaces_existing_connection(self, svc):
        old = AsyncMock()
        new = AsyncMock()
        asyncio.run(svc.connect(old, "tenant-1"))
        asyncio.run(svc.connect(new, "tenant-1"))
        old.close.assert_awaited_once()
        assert svc.active_connections["tenant-1"] is new
        assert len(svc.active_connections) == 1

    def test_connect_replaces_when_old_close_raises(self, svc):
        old = AsyncMock()
        old.close = AsyncMock(side_effect=RuntimeError("already closed"))
        new = AsyncMock()
        asyncio.run(svc.connect(old, "tenant-1"))
        asyncio.run(svc.connect(new, "tenant-1"))
        assert svc.active_connections["tenant-1"] is new

    def test_connect_keeps_distinct_tenants(self, svc):
        ws_a = AsyncMock()
        ws_b = AsyncMock()
        asyncio.run(svc.connect(ws_a, "tenant-a"))
        asyncio.run(svc.connect(ws_b, "tenant-b"))
        assert svc.active_connections["tenant-a"] is ws_a
        assert svc.active_connections["tenant-b"] is ws_b


class TestDisconnect:
    def test_disconnect_removes_tenant(self, svc):
        ws = AsyncMock()
        asyncio.run(svc.connect(ws, "tenant-1"))
        svc.disconnect("tenant-1")
        assert "tenant-1" not in svc.active_connections

    def test_disconnect_unknown_tenant_noop(self, svc):
        svc.disconnect("nobody")
        assert svc.active_connections == {}


class TestExecuteLocalTool:
    def test_no_connection_returns_error(self, svc):
        result = asyncio.run(svc.execute_local_tool("tenant-1", "run_terminal", {}))
        assert result["error"].startswith("Satellite not connected")

    def test_success_round_trip(self, svc):
        ws = AsyncMock()
        asyncio.run(svc.connect(ws, "tenant-1"))

        async def _run():
            task = asyncio.ensure_future(
                svc.execute_local_tool("tenant-1", "run_terminal", {"cmd": "ls"})
            )
            await asyncio.sleep(0)
            request_id = next(iter(svc.pending_requests))
            assert request_id.startswith("tenant-1-")
            await svc.handle_message("tenant-1", {
                "type": "tool_result", "request_id": request_id,
                "result": {"output": "ok"},
            })
            return await task

        result = asyncio.run(_run())
        assert result == {"output": "ok"}
        assert svc.pending_requests == {}
        sent = ws.send_json.await_args.args[0]
        assert sent["type"] == "tool_call"
        assert sent["tool"] == "run_terminal"
        assert sent["arguments"] == {"cmd": "ls"}

    def test_send_json_failure_returns_error(self, svc):
        ws = AsyncMock()
        ws.send_json = AsyncMock(side_effect=RuntimeError("socket closed"))
        asyncio.run(svc.connect(ws, "tenant-1"))
        result = asyncio.run(svc.execute_local_tool("tenant-1", "run_terminal", {}))
        assert "Satellite communication error" in result["error"]
        assert svc.pending_requests == {}

    def test_pending_request_cleaned_on_timeout(self, svc):
        ws = AsyncMock()
        asyncio.run(svc.connect(ws, "tenant-1"))
        with patch(
            "core.satellite_service.asyncio.wait_for",
            AsyncMock(side_effect=asyncio.TimeoutError()),
        ):
            result = asyncio.run(svc.execute_local_tool("tenant-1", "t", {}))
        assert "timed out" in result["error"]
        assert svc.pending_requests == {}


def _make_future():
    """Create a future bound to a running loop (no current loop on main thread)."""
    return asyncio.run(_new_future())


async def _new_future():
    return asyncio.get_running_loop().create_future()


def _context_db():
    """A get_db_session() result usable with `with ... as db:` — the with
    statement binds to __enter__()'s return, so return self from it."""
    db = MagicMock()
    db.__enter__.return_value = db
    db.__exit__.return_value = False
    return db


class TestHandleMessage:
    def test_tool_result_resolves_pending_future(self, svc):
        future = _make_future()
        svc.pending_requests["tenant-1-req1"] = future
        asyncio.run(svc.handle_message("tenant-1", {
            "type": "tool_result", "request_id": "tenant-1-req1",
            "result": {"output": "done"},
        }))
        assert future.done()
        assert future.result() == {"output": "done"}

    def test_tool_result_unknown_request_ignored(self, svc):
        future = MagicMock()
        svc.pending_requests["tenant-1-req1"] = future
        asyncio.run(svc.handle_message("tenant-1", {
            "type": "tool_result", "request_id": "tenant-1-other",
            "result": {"x": 1},
        }))
        future.set_result.assert_not_called()

    def test_tool_result_does_not_override_done_future(self, svc):
        future = _make_future()
        future.set_result("first")
        svc.pending_requests["tenant-1-req1"] = future
        asyncio.run(svc.handle_message("tenant-1", {
            "type": "tool_result", "request_id": "tenant-1-req1",
            "result": "second",
        }))
        assert future.result() == "first"

    def test_heartbeat_is_noop(self, svc):
        asyncio.run(svc.handle_message("tenant-1", {"type": "heartbeat"}))
        assert svc.pending_requests == {}

    def test_unknown_message_type_is_noop(self, svc):
        asyncio.run(svc.handle_message("tenant-1", {"type": "banana"}))
        assert svc.pending_requests == {}

    def test_identify_registers_node(self, svc):
        db = _context_db()
        fake_service = MagicMock()
        message = {
            "type": "identify",
            "metadata": {"hostname": "mac-1"},
            "capabilities": ["terminal", "browser"],
        }
        with patch(
            "ai.device_node_service.device_node_service", fake_service
        ), patch(
            "core.database.get_db_session", return_value=db
        ):
            asyncio.run(svc.handle_message("tenant-9", message))
        fake_service.register_node.assert_called_once()
        node_data = fake_service.register_node.call_args.args[2]
        assert node_data["deviceId"] == "mac-1"
        assert node_data["type"] == "satellite_bridge"
        db.close.assert_called_once()

    def test_identify_defaults_hostname_from_tenant(self, svc):
        db = _context_db()
        fake_service = MagicMock()
        with patch(
            "ai.device_node_service.device_node_service", fake_service
        ), patch(
            "core.database.get_db_session", return_value=db
        ):
            asyncio.run(svc.handle_message("tenant-9", {
                "type": "identify", "metadata": {}, "capabilities": [],
            }))
        node_data = fake_service.register_node.call_args.args[2]
        assert node_data["deviceId"] == "node-tenant-9"

    def test_identify_db_failure_swallowed(self, svc):
        fake_service = MagicMock()
        fake_service.register_node.side_effect = RuntimeError("db down")
        with patch(
            "ai.device_node_service.device_node_service", fake_service
        ), patch(
            "core.database.get_db_session", return_value=MagicMock()
        ):
            asyncio.run(svc.handle_message("tenant-9", {
                "type": "identify", "metadata": {}, "capabilities": [],
            }))
        fake_service.register_node.assert_called_once()
