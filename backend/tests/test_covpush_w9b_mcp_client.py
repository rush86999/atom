"""
Coverage wave 9b — core/mcp_client.py (41% -> 90%+ target) + the
core/mcp_service.py register_server / refresh_tools P6 handshake path.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Transport fakes (no real network)
# ============================================================================

class FakeResponse:
    def __init__(self, chunks, status=200):
        self.chunks = list(chunks)
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def aiter_bytes(self):
        for c in self.chunks:
            yield c


class FakeStreamCM:
    def __init__(self, resp):
        self.resp = resp

    async def __aenter__(self):
        return self.resp

    async def __aexit__(self, *a):
        return False


class FakeHTTPClient:
    def __init__(self, responses=None, **kwargs):
        self.responses = list(responses or [])
        self.kwargs = kwargs
        self.streams = []

    def stream(self, method, url, json=None):
        resp = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        self.streams.append((method, url, json))
        return FakeStreamCM(resp)

    async def aclose(self):
        self.closed = True


class FakeProc:
    def __init__(self, lines, stdout=None):
        self._lines = lines
        self.stdout = stdout or MagicMock()

    async def wait(self):
        return 0

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


@pytest.fixture
def client():
    from core.mcp_client import MCPClient

    return MCPClient("srv", {"transport": "http", "url": "http://x", "headers": {"X-A": "1"}})


# ============================================================================
# Transport setup
# ============================================================================

class TestTransportSetup:
    @pytest.mark.asyncio
    async def test_ensure_http_creates_and_caches(self, client, monkeypatch):
        import httpx

        monkeypatch.setattr(httpx, "AsyncClient", FakeHTTPClient)
        c1 = await client._ensure_http()
        c2 = await client._ensure_http()
        assert c1 is c2
        assert c1.kwargs["base_url"] == "http://x"
        assert c1.kwargs["headers"]["X-A"] == "1"
        assert c1.kwargs["timeout"] == 30.0

    @pytest.mark.asyncio
    async def test_ensure_stdio_missing_command(self, monkeypatch):
        from core.mcp_client import MCPClient, MCPClientError

        c = MCPClient("s", {"transport": "stdio"})
        with pytest.raises(MCPClientError):
            await c._ensure_stdio()

    @pytest.mark.asyncio
    async def test_ensure_stdio_spawns(self, monkeypatch):
        from core.mcp_client import MCPClient

        c = MCPClient("s", {"transport": "stdio", "command": "/bin/cat", "args": ["-"], "env": {"K": "V"}})

        fake_stdout = AsyncMock()
        fake_stdout.readline = AsyncMock(return_value=b'{"jsonrpc":"2.0","id":1,"result":{}}\n')
        fake_proc = MagicMock()
        fake_proc.stdout = fake_stdout
        fake_proc.stderr = MagicMock()
        fake_proc.stdin = AsyncMock()

        async def fake_spawn(*a, **kw):
            return fake_proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)
        await c._ensure_stdio()
        assert c._stdio_proc is fake_proc

    @pytest.mark.asyncio
    async def test_close_http_and_stdio(self, monkeypatch):
        from core.mcp_client import MCPClient

        c = MCPClient("s", {"transport": "stdio", "command": "/bin/cat"})
        fake_client = FakeHTTPClient([FakeResponse([b"{}"])])
        c._http_client = fake_client
        fake_stdout = AsyncMock()
        fake_proc = MagicMock()
        fake_proc.returncode = None
        fake_proc.wait = AsyncMock(return_value=0)
        fake_proc.terminate = MagicMock()
        c._stdio_proc = fake_proc
        c._stdio_reader = fake_stdout
        c._stdio_writer = MagicMock()

        await c.close()
        assert fake_client.closed is True
        fake_proc.terminate.assert_called_once()
        assert c._http_client is None
        assert c._stdio_proc is None

    @pytest.mark.asyncio
    async def test_close_stdio_terminate_timeout_kills(self, monkeypatch):
        from core.mcp_client import MCPClient

        c = MCPClient("s", {"transport": "stdio", "command": "/bin/cat"})
        fake_proc = MagicMock()
        fake_proc.returncode = None
        fake_proc.wait = AsyncMock(side_effect=asyncio.TimeoutError)
        fake_proc.kill = MagicMock()
        c._stdio_proc = fake_proc

        await c.close()
        fake_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_stdio_already_exited(self):
        from core.mcp_client import MCPClient

        c = MCPClient("s", {"transport": "stdio", "command": "/bin/cat"})
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        c._stdio_proc = fake_proc
        await c.close()
        fake_proc.terminate.assert_not_called()


# ============================================================================
# JSON-RPC core over HTTP
# ============================================================================

class TestRpcHTTP:
    @pytest.mark.asyncio
    async def test_rpc_http_success(self, client, monkeypatch):
        import httpx

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeHTTPClient(
            [FakeResponse([b'{"jsonrpc":"2.0","id":1,"result":{"ok":1}}'])]
        ))
        result = await client._rpc_http({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert result == {"ok": 1}

    @pytest.mark.asyncio
    async def test_rpc_http_chunked_assembly(self, client, monkeypatch):
        import httpx

        payload = b'{"jsonrpc":"2.0","id":2,"result":{"chunked":true}}'
        mid = len(payload) // 2
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeHTTPClient(
            [FakeResponse([payload[:mid], payload[mid:]])]
        ))
        result = await client._rpc_http({"jsonrpc": "2.0", "id": 2, "method": "x"})
        assert result == {"chunked": True}

    @pytest.mark.asyncio
    async def test_rpc_http_oversize_rejected(self, client, monkeypatch):
        import httpx

        from core.mcp_client import MCPClientError

        big = b"x" * (8 * 1024 * 1024 + 10)
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeHTTPClient(
            [FakeResponse([big])]
        ))
        with pytest.raises(MCPClientError):
            await client._rpc_http({"jsonrpc": "2.0", "id": 1, "method": "x"})

    @pytest.mark.asyncio
    async def test_rpc_http_error_envelope(self, client, monkeypatch):
        import httpx

        from core.mcp_client import MCPClientError

        resp = FakeResponse([b'{"jsonrpc":"2.0","id":1,"error":{"code":-32601,"message":"no such method"}}'])
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeHTTPClient([resp]))
        with pytest.raises(MCPClientError) as ei:
            await client._rpc_http({"jsonrpc": "2.0", "id": 1, "method": "x"})
        assert "-32601" in str(ei.value)
        assert "no such method" in str(ei.value)

    @pytest.mark.asyncio
    async def test_rpc_http_transport_failure_wrapped(self, client, monkeypatch):
        import httpx

        from core.mcp_client import MCPClientError

        class BoomClient:
            def stream(self, method, url, json=None):
                raise ConnectionError("refused")

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: BoomClient())
        with pytest.raises(MCPClientError) as ei:
            await client._rpc_http({"jsonrpc": "2.0", "id": 1, "method": "x"})
        assert "HTTP RPC failed" in str(ei.value)

    @pytest.mark.asyncio
    async def test_rpc_http_status_error(self, client, monkeypatch):
        import httpx

        from core.mcp_client import MCPClientError

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeHTTPClient(
            [FakeResponse([b"oops"], status=503)]
        ))
        with pytest.raises(MCPClientError):
            await client._rpc_http({"jsonrpc": "2.0", "id": 1, "method": "x"})

    @pytest.mark.asyncio
    async def test_rpc_dispatches_http_by_default(self, client, monkeypatch):
        import httpx

        captured = {}
        client._rpc_http = AsyncMock(return_value={"ok": 1})

        async def fake_ensure():
            return "http-client"

        client._ensure_http = fake_ensure
        result = await client._rpc("tools/list", {"x": 1})
        assert result == {"ok": 1}
        assert client._rpc_http.await_args.args[0]["method"] == "tools/list"
        assert client._rpc_http.await_args.args[0]["params"] == {"x": 1}
        assert client._rpc_http.await_args.args[0]["jsonrpc"] == "2.0"
        assert client._next_id == 2

    @pytest.mark.asyncio
    async def test_rpc_dispatches_stdio(self, monkeypatch):
        from core.mcp_client import MCPClient

        c = MCPClient("s", {"transport": "stdio", "command": "/bin/cat"})
        c._rpc_stdio = AsyncMock(return_value={"ok": 2})
        result = await c._rpc("initialize", {"protocolVersion": "2024-11-05"})
        assert result == {"ok": 2}


# ============================================================================
# JSON-RPC core over stdio
# ============================================================================

class TestRpcStdio:
    def make_stdio_client(self, lines):
        from core.mcp_client import MCPClient

        c = MCPClient("s", {"transport": "stdio", "command": "/bin/cat"})
        c._stdio_proc = MagicMock()
        reader = AsyncMock()
        reader.readline.side_effect = [l.encode() for l in lines] + [b""]
        writer = AsyncMock()
        writer.drain = AsyncMock()
        c._stdio_reader = reader
        c._stdio_writer = writer
        return c

    @pytest.mark.asyncio
    async def test_round_trip(self):
        c = self.make_stdio_client(['{"jsonrpc":"2.0","id":1,"result":{"t":["a"]}}'])
        result = await c._rpc_stdio({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert result == {"t": ["a"]}
        c._stdio_writer.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_ready(self):
        from core.mcp_client import MCPClient, MCPClientError

        c = MCPClient("s", {"transport": "stdio", "command": "/bin/cat"})
        c._stdio_proc = MagicMock()
        c._stdio_reader = None
        c._stdio_writer = None
        with pytest.raises(MCPClientError) as ei:
            await c._rpc_stdio({"jsonrpc": "2.0", "id": 1, "method": "x"})
        assert "not ready" in str(ei.value)

    @pytest.mark.asyncio
    async def test_timeout(self):
        from core.mcp_client import MCPClientError

        c = self.make_stdio_client([])
        c._stdio_reader.readline.side_effect = asyncio.TimeoutError
        with pytest.raises(MCPClientError) as ei:
            await c._rpc_stdio({"jsonrpc": "2.0", "id": 1, "method": "x"})
        assert "timed out" in str(ei.value)

    @pytest.mark.asyncio
    async def test_closed_connection(self):
        from core.mcp_client import MCPClientError

        c = self.make_stdio_client([])
        c._stdio_reader.readline = AsyncMock(return_value=b"")
        with pytest.raises(MCPClientError) as ei:
            await c._rpc_stdio({"jsonrpc": "2.0", "id": 1, "method": "x"})
        assert "closed" in str(ei.value)

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        from core.mcp_client import MCPClientError

        c = self.make_stdio_client(["not json at all"])
        with pytest.raises(MCPClientError) as ei:
            await c._rpc_stdio({"jsonrpc": "2.0", "id": 1, "method": "x"})
        assert "invalid stdio JSON" in str(ei.value)

    @pytest.mark.asyncio
    async def test_error_envelope(self):
        from core.mcp_client import MCPClientError

        c = self.make_stdio_client(['{"jsonrpc":"2.0","id":1,"error":{"code":-32603,"message":"internal"}}'])
        with pytest.raises(MCPClientError) as ei:
            await c._rpc_stdio({"jsonrpc": "2.0", "id": 1, "method": "x"})
        assert "-32603" in str(ei.value)


# ============================================================================
# MCP protocol methods
# ============================================================================

class TestProtocolMethods:
    @pytest.mark.asyncio
    async def test_initialize_sets_flag(self, client):
        client._rpc = AsyncMock(return_value={"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}})
        info = await client.initialize()
        assert info["protocolVersion"] == "2024-11-05"
        assert client._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, client):
        client._initialized = True
        client._rpc = AsyncMock(return_value={"should": "not run"})
        info = await client.initialize()
        assert info == {"protocolVersion": "cached", "capabilities": {}}
        client._rpc.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_empty_result_default(self, client):
        client._rpc = AsyncMock(return_value=None)
        info = await client.initialize()
        assert info["protocolVersion"] == "2024-11-05"

    @pytest.mark.asyncio
    async def test_list_tools_normalizes_input_schema(self, client):
        client._rpc = AsyncMock(return_value={
            "tools": [
                {"name": "a", "inputSchema": {"type": "object"}},
                {"name": "b", "parameters": {"type": "object"}},
            ]
        })
        tools = await client.list_tools()
        assert tools[0]["parameters"] == {"type": "object"}
        assert tools[1]["parameters"] == {"type": "object"}

    @pytest.mark.asyncio
    async def test_list_tools_empty(self, client):
        client._rpc = AsyncMock(return_value=None)
        assert await client.list_tools() == []

    @pytest.mark.asyncio
    async def test_call_tool_text_blocks(self, client):
        client._rpc = AsyncMock(return_value={
            "content": [{"type": "text", "text": "hello"}, {"type": "image", "data": "x"}],
            "isError": False,
        })
        result = await client.call_tool("t", {"q": 1})
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_call_tool_string_blocks(self, client):
        client._rpc = AsyncMock(return_value={"content": ["raw1", "raw2"]})
        result = await client.call_tool("t", {})
        assert result == "raw1\nraw2"

    @pytest.mark.asyncio
    async def test_call_tool_error_prefixed(self, client):
        client._rpc = AsyncMock(return_value={"content": [{"type": "text", "text": "boom"}], "isError": True})
        result = await client.call_tool("t", {})
        assert result == "Error: boom"

    @pytest.mark.asyncio
    async def test_call_tool_empty_result(self, client):
        client._rpc = AsyncMock(return_value=None)
        assert await client.call_tool("t", {}) == ""


# ============================================================================
# mcp_service: register_server → refresh_tools P6 handshake path
# ============================================================================

class TestMCPServiceHandshake:
    @pytest.mark.asyncio
    async def test_refresh_tools_no_config_skips(self):
        from core.mcp_service import MCPService

        svc = MCPService()
        svc.servers = {}
        await svc.refresh_tools("ext")
        assert "ext" not in svc.tools_cache

    @pytest.mark.asyncio
    async def test_refresh_tools_handshake_error_logged(self, monkeypatch):
        from core import mcp_service as ms
        from core.mcp_client import MCPClientError

        class FailingClient:
            def __init__(self, sid, cfg):
                pass

            async def initialize(self):
                raise MCPClientError("handshake failed")

        monkeypatch.setattr(ms, "MCPClient", FailingClient)
        svc = ms.MCPService()
        await svc.register_server("ext", {"transport": "http", "url": "http://x"})
        assert "ext" not in svc.tools_cache
        assert "ext" not in svc.external_clients

    @pytest.mark.asyncio
    async def test_refresh_tools_generic_exception_logged(self, monkeypatch):
        from core import mcp_service as ms

        class BoomClient:
            def __init__(self, sid, cfg):
                pass

            async def initialize(self):
                raise ValueError("boom")

        monkeypatch.setattr(ms, "MCPClient", BoomClient)
        svc = ms.MCPService()
        await svc.register_server("ext", {"transport": "http", "url": "http://x"})
        assert "ext" not in svc.tools_cache

    @pytest.mark.asyncio
    async def test_register_server_handshake_and_call(self, monkeypatch):
        from core import mcp_service as ms

        class FakeClient:
            def __init__(self, server_id, config):
                self.server_id = server_id

            async def initialize(self):
                return {"protocolVersion": "2024-11-05", "capabilities": {}}

            async def list_tools(self):
                return [
                    {"name": "ext_tool", "description": "d", "inputSchema": {"type": "object", "properties": {}}},
                    {"name": "other", "description": "d2", "parameters": {"type": "object"}},
                ]

            async def call_tool(self, name, args):
                return f"called {name}: {args}"

        monkeypatch.setattr(ms, "MCPClient", FakeClient)
        svc = ms.MCPService()
        await svc.register_server("ext", {"transport": "http", "url": "http://x"})
        assert "ext" in svc.tools_cache
        assert {t.name for t in svc.tools_cache["ext"]} == {"ext_tool", "other"}
        assert svc.tools_cache["ext"][0].server_id == "ext"
        assert svc.tools_cache["ext"][0].parameters == {"type": "object", "properties": {}}
        assert svc.external_clients["ext"] is not None

        result = await svc.call_external_tool("ext", "ext_tool", {"x": 1})
        assert result == "called ext_tool: {'x': 1}"

    @pytest.mark.asyncio
    async def test_call_external_tool_not_connected(self):
        from core.mcp_client import MCPClientError
        from core.mcp_service import MCPService

        svc = MCPService()
        with pytest.raises(MCPClientError):
            await svc.call_external_tool("nope", "t", {})

    @pytest.mark.asyncio
    async def test_register_tool_replaces_duplicate(self):
        from core.mcp_service import MCPService, MCPTool

        svc = MCPService()
        t1 = MCPTool(name="a", description="v1", server_id="srv")
        t2 = MCPTool(name="a", description="v2", server_id="srv")
        svc.register_tool(t1)
        svc.register_tool(t2)
        tools = svc.tools_cache["srv"]
        assert len(tools) == 1
        assert tools[0].description == "v2"
