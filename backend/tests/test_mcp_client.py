"""
P6 — Real MCP Client tests (G6).

Atom connects to arbitrary external MCP servers (Cloudflare "MCP Server Portals"
equivalent), not just the 3 hardcoded pseudo-servers. The client speaks JSON-RPC
2.0 (initialize / tools/list / tools/call) over HTTP+SSE, mirroring the wire
format the hand-rolled SERVER at ``core/mcp_server/handler.py`` produces.

Revives the dead-but-sandbox-aware ``core/mcp_service.py`` as the real hub: its
``register_server`` (never called today) now actually connects via the client,
and the ``# Placeholder for real MCP protocol handshake`` in ``refresh_tools``
becomes a real handshake.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# MCPClient — JSON-RPC transport over HTTP
# ============================================================================

class TestMCPClientHTTP:
    @pytest.mark.asyncio
    async def test_initialize_handshake(self, monkeypatch):
        """initialize() returns the server's protocolVersion + capabilities."""
        from core.mcp_client import MCPClient

        async def fake_post(client_self, method, params=None):
            assert method == "initialize"
            return {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ext", "version": "1.0"},
            }
        monkeypatch.setattr(MCPClient, "_rpc", fake_post)

        client = MCPClient("ext", {"transport": "http", "url": "http://x"})
        info = await client.initialize()
        assert info["protocolVersion"] == "2024-11-05"
        assert "tools" in info["capabilities"]

    @pytest.mark.asyncio
    async def test_list_tools_returns_tool_definitions(self, monkeypatch):
        from core.mcp_client import MCPClient

        async def fake_post(client_self, method, params=None):
            assert method == "tools/list"
            return {"tools": [{"name": "search", "description": "search the web",
                                "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}}}]}
        monkeypatch.setattr(MCPClient, "_rpc", fake_post)

        client = MCPClient("ext", {"transport": "http", "url": "http://x"})
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "search"

    @pytest.mark.asyncio
    async def test_call_tool_round_trip(self, monkeypatch):
        from core.mcp_client import MCPClient

        captured = {}

        async def fake_post(client_self, method, params=None):
            captured["method"] = method
            captured["params"] = params
            return {"content": [{"type": "text", "text": "result-data"}], "isError": False}
        monkeypatch.setattr(MCPClient, "_rpc", fake_post)

        client = MCPClient("ext", {"transport": "http", "url": "http://x"})
        result = await client.call_tool("search", {"q": "hello"})
        assert captured["method"] == "tools/call"
        assert captured["params"]["name"] == "search"
        assert captured["params"]["arguments"] == {"q": "hello"}
        assert "result-data" in result

    @pytest.mark.asyncio
    async def test_call_tool_surfaces_error(self, monkeypatch):
        from core.mcp_client import MCPClient

        async def fake_post(client_self, method, params=None):
            return {"content": [{"type": "text", "text": "boom"}], "isError": True}
        monkeypatch.setattr(MCPClient, "_rpc", fake_post)

        client = MCPClient("ext", {"transport": "http", "url": "http://x"})
        result = await client.call_tool("bad", {})
        assert "boom" in result
        assert "error" in result.lower() or "Error".lower() in result.lower()


# ============================================================================
# Revived core/mcp_service.register_server + refresh_tools
# ============================================================================

class TestRegisterServerRevived:
    @pytest.mark.asyncio
    async def test_register_server_connects_via_client(self, monkeypatch):
        """register_server must use the real MCPClient for non-hardcoded servers
        (replacing the 'Placeholder for real MCP protocol handshake' warning)."""
        from core import mcp_service as ms

        svc = ms.MCPService()

        connected = []

        class FakeClient:
            def __init__(self, server_id, config):
                self.server_id = server_id
            async def initialize(self):
                connected.append("init")
                return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}
            async def list_tools(self):
                connected.append("list")
                return [{"name": "ext_tool", "description": "d",
                         "inputSchema": {"type": "object", "properties": {}}}]
            async def call_tool(self, name, args):
                return {"result": "ok"}

        monkeypatch.setattr(ms, "MCPClient", FakeClient)

        await svc.register_server("ext-svc", {"transport": "http", "url": "http://x"})
        # refresh_tools ran the handshake + tools/list and cached the tool.
        assert "ext-svc" in svc.tools_cache
        tool_names = [t.name for t in svc.tools_cache["ext-svc"]]
        assert "ext_tool" in tool_names
        assert "init" in connected and "list" in connected

    @pytest.mark.asyncio
    async def test_call_external_tool_via_client(self, monkeypatch):
        """A registered external server's tools are callable through the client."""
        from core import mcp_service as ms

        svc = ms.MCPService()

        class FakeClient:
            def __init__(self, server_id, config):
                pass
            async def initialize(self):
                return {"protocolVersion": "2024-11-05", "capabilities": {}}
            async def list_tools(self):
                return [{"name": "ext_tool", "description": "d",
                         "inputSchema": {"type": "object", "properties": {}}}]
            async def call_tool(self, name, args):
                return f"called {name} with {args}"

        monkeypatch.setattr(ms, "MCPClient", FakeClient)
        await svc.register_server("ext-svc", {"transport": "http", "url": "http://x"})

        # The cached client instance should be reused for calls.
        result = await svc.call_external_tool("ext-svc", "ext_tool", {"x": 1})
        assert "ext_tool" in result
        assert "x" in result
