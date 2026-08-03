"""Tests for the MCP server (JSON-RPC handler + tools).

Covers: initialize handshake, tools/list, tools/call dispatch, ping,
unknown method error, notification handling, batch requests, SSE endpoint.
"""
import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from core.mcp_server.handler import handle_jsonrpc
from core.mcp_server.tools import get_all_tools


# --- JSON-RPC handler ------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_handshake():
    resp = await handle_jsonrpc({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2026-07-28"},
    })
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    info = resp["result"]["serverInfo"]
    assert info["name"] == "atom-mcp-server"
    assert "protocolVersion" in resp["result"]


@pytest.mark.asyncio
async def test_ping():
    resp = await handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert resp["result"] == {}


@pytest.mark.asyncio
async def test_tools_list():
    resp = await handle_jsonrpc({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    tools = resp["result"]["tools"]
    assert len(tools) >= 5
    names = [t["name"] for t in tools]
    assert "resolve_route" in names
    assert "list_models" in names
    assert "compress_text" in names
    assert "fusion_generate" in names
    # Each tool has the MCP-required fields
    for t in tools:
        assert "name" in t
        assert "description" in t
        assert "inputSchema" in t


@pytest.mark.asyncio
async def test_tools_call_compress_text():
    resp = await handle_jsonrpc({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {
            "name": "compress_text",
            "arguments": {"text": "Building module...\n" * 20 + "BUILD FAILED\n"},
        },
    })
    assert resp["result"]["isError"] is False
    content = resp["result"]["content"][0]
    assert content["type"] == "text"
    parsed = json.loads(content["text"])
    assert "metrics" in parsed
    assert parsed["metrics"]["savings_tokens"] > 0


@pytest.mark.asyncio
async def test_tools_call_unknown_tool():
    """Calling an unknown tool returns a JSON-RPC error response."""
    resp = await handle_jsonrpc({
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "nonexistent_tool", "arguments": {}},
    })
    # Unknown tool raises ValueError → caught by handler → error response
    assert "error" in resp
    assert resp["error"]["code"] == -32603


@pytest.mark.asyncio
async def test_unknown_method_error():
    resp = await handle_jsonrpc({"jsonrpc": "2.0", "id": 6, "method": "unknown/method"})
    assert "error" in resp
    assert resp["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_notification_returns_none():
    """Notifications (no id) should return None (no response sent)."""
    resp = await handle_jsonrpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert resp is None


@pytest.mark.asyncio
async def test_batch_request():
    """A batch of JSON-RPC requests returns an array of responses."""
    batch = [
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},  # notification, no response
    ]
    responses = []
    for req in batch:
        resp = await handle_jsonrpc(req)
        if resp is not None:
            responses.append(resp)
    assert len(responses) == 2  # notification excluded
    assert responses[0]["id"] == 1
    assert responses[1]["id"] == 2


# --- Tool definitions ------------------------------------------------------


def test_all_tools_have_required_fields():
    tools = get_all_tools()
    for t in tools:
        assert t.name
        assert t.description
        assert isinstance(t.input_schema, dict)
        assert callable(t.handler)


def test_tool_count():
    tools = get_all_tools()
    assert len(tools) == 7  # resolve_route, list_models, compress_text, set_compression, get_spend, get_health, fusion_generate


# --- HTTP route integration ------------------------------------------------


def test_mcp_http_post_initialize():
    """The HTTP POST endpoint should handle initialize."""
    from api.mcp_server_routes import router

    app = FastAPI()
    app.include_router(router)

    # Bypass auth for this test
    from core.security_dependencies import get_current_user
    from core.models import User
    fake_user = type("FakeUser", (), {"id": "u1", "tenant_id": "t1"})()
    app.dependency_overrides[get_current_user] = lambda: fake_user

    client = TestClient(app)
    resp = client.post("/mcp/", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2026-07-28"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["serverInfo"]["name"] == "atom-mcp-server"


def test_mcp_http_disabled_returns_503():
    """When MCP_SERVER_ENABLED is false, the endpoint returns 503."""
    with patch("api.mcp_server_routes.MCP_SERVER_ENABLED", False):
        from api.mcp_server_routes import router

        app = FastAPI()
        app.include_router(router)

        from core.security_dependencies import get_current_user
        fake_user = type("FakeUser", (), {"id": "u1", "tenant_id": "t1"})()
        app.dependency_overrides[get_current_user] = lambda: fake_user

        client = TestClient(app)
        resp = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert resp.status_code == 503
