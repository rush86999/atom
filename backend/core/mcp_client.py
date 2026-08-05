"""
Real MCP Client — P6 (Cloudflare OS G6).

A real MCP client transport that speaks JSON-RPC 2.0 (initialize / tools/list /
tools/call) over HTTP+SSE, mirroring the wire format the hand-rolled SERVER at
``core/mcp_server/handler.py`` produces. Hand-rolled over ``httpx`` (no new SDK
dependency), consistent with the existing hand-rolled server.

Revives the dead-but-sandbox-aware ``core/mcp_service.py`` as the real hub: its
``register_server`` (never called today) now actually connects via this client,
and the ``# Placeholder for real MCP protocol handshake`` in ``refresh_tools``
becomes a real handshake.

Stdio transport is stubbed (subprocess-based) for parity with the config schema;
HTTP+SSE is the primary transport for this phase.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# JSON-RPC 2.0 error codes (mirror core/mcp_server/handler.py).
_JSONRPC_PARSE_ERROR = -32700
_JSONRPC_METHOD_NOT_FOUND = -32601
_JSONRPC_INTERNAL_ERROR = -32603


class MCPClientError(Exception):
    """Raised when an MCP client operation fails."""


class MCPClient:
    """JSON-RPC 2.0 client for an external MCP server (HTTP+SSE primary).

    Usage::

        client = MCPClient("my-server", {"transport": "http", "url": "http://..."})
        await client.initialize()
        tools = await client.list_tools()
        result = await client.call_tool("search", {"q": "x"})
    """

    def __init__(self, server_id: str, config: Dict[str, Any]) -> None:
        self.server_id = server_id
        self.config = config or {}
        self.transport = self.config.get("transport", "http").lower()
        self.url = self.config.get("url")
        self.headers = self.config.get("headers") or {}
        # Lazily-created transport objects.
        self._http_client: Any = None
        self._stdio_proc: Optional[asyncio.subprocess.Process] = None
        self._stdio_writer: Optional[asyncio.StreamWriter] = None
        self._stdio_reader: Optional[asyncio.StreamReader] = None
        self._next_id = 1
        self._initialized = False

    # ------------------------------------------------------------------------
    # Transport setup
    # ------------------------------------------------------------------------

    async def _ensure_http(self) -> Any:
        if self._http_client is None:
            import httpx
            self._http_client = httpx.AsyncClient(
                base_url=self.url or "",
                headers={"Content-Type": "application/json", **self.headers},
                timeout=30.0,
            )
        return self._http_client

    async def _ensure_stdio(self) -> None:
        if self._stdio_proc is not None:
            return
        command = self.config.get("command")
        args = self.config.get("args", [])
        env = self.config.get("env") or {}
        if not command:
            raise MCPClientError("stdio transport requires a 'command' in config")
        import os
        full_env = {**os.environ, **env}
        self._stdio_proc = await asyncio.create_subprocess_exec(
            command, *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )
        self._stdio_reader = self._stdio_proc.stdout
        self._stdio_writer = self._stdio_proc.stdin

    async def close(self) -> None:
        """Release transport resources."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        if self._stdio_proc is not None and self._stdio_proc.returncode is None:
            self._stdio_proc.terminate()
            try:
                await asyncio.wait_for(self._stdio_proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._stdio_proc.kill()
        self._stdio_proc = None
        self._stdio_writer = None
        self._stdio_reader = None

    # ------------------------------------------------------------------------
    # JSON-RPC core
    # ------------------------------------------------------------------------

    async def _rpc(self, method: str, params: Optional[Dict[str, Any]] = Any) -> Any:
        """Send a JSON-RPC 2.0 request and return the ``result`` field.

        Subclasses / tests monkeypatch THIS method to avoid real network I/O.
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params
        self._next_id += 1

        if self.transport == "stdio":
            return await self._rpc_stdio(request)
        return await self._rpc_http(request)

    async def _rpc_http(self, request: Dict[str, Any]) -> Any:
        client = await self._ensure_http()
        try:
            resp = await client.post("", json=request)
            resp.raise_for_status()
            envelope = resp.json()
        except Exception as e:
            raise MCPClientError(f"{self.server_id}: HTTP RPC failed ({e})") from e

        if "error" in envelope and envelope["error"]:
            err = envelope["error"]
            raise MCPClientError(
                f"{self.server_id}: JSON-RPC error {err.get('code')}: {err.get('message')}"
            )
        return envelope.get("result")

    async def _rpc_stdio(self, request: Dict[str, Any]) -> Any:
        await self._ensure_stdio()
        if self._stdio_writer is None or self._stdio_reader is None:
            raise MCPClientError(f"{self.server_id}: stdio transport not ready")
        payload = json.dumps(request) + "\n"
        self._stdio_writer.write(payload.encode())
        await self._stdio_writer.drain()
        try:
            line = await asyncio.wait_for(self._stdio_reader.readline(), timeout=30.0)
        except asyncio.TimeoutError as e:
            raise MCPClientError(f"{self.server_id}: stdio RPC timed out") from e
        if not line:
            raise MCPClientError(f"{self.server_id}: stdio server closed connection")
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError as e:
            raise MCPClientError(f"{self.server_id}: invalid stdio JSON") from e
        if "error" in envelope and envelope["error"]:
            err = envelope["error"]
            raise MCPClientError(
                f"{self.server_id}: JSON-RPC error {err.get('code')}: {err.get('message')}"
            )
        return envelope.get("result")

    # ------------------------------------------------------------------------
    # MCP protocol methods
    # ------------------------------------------------------------------------

    async def initialize(self) -> Dict[str, Any]:
        """Perform the MCP initialize handshake. Idempotent."""
        if self._initialized:
            return {"protocolVersion": "cached", "capabilities": {}}
        result = await self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "atom-mcp-client", "version": "1.0"},
        })
        self._initialized = True
        return result or {"protocolVersion": "2024-11-05", "capabilities": {}}

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Return the server's tool definitions (from tools/list)."""
        result = await self._rpc("tools/list", {})
        tools = (result or {}).get("tools", [])
        # Normalize: MCP servers may expose inputSchema (camel) or parameters.
        for t in tools:
            if "inputSchema" in t and "parameters" not in t:
                t["parameters"] = t["inputSchema"]
        return tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Invoke a tool by name. Returns the textual content of the result."""
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        result = result or {}
        is_error = bool(result.get("isError"))
        # Flatten content blocks to text.
        blocks = result.get("content", [])
        text_parts: List[str] = []
        for b in blocks:
            if isinstance(b, dict) and b.get("type") == "text":
                text_parts.append(b.get("text", ""))
            elif isinstance(b, str):
                text_parts.append(b)
        text = "\n".join(text_parts)
        if is_error:
            return f"Error: {text}"
        return text
