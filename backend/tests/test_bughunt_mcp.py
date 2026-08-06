"""
TDD bug-hunt for the MCP dispatch + capability-binding layer.

Territory under test: core/capability_resolver.py, integrations/mcp_service.py,
core/mcp_client.py.

Bugs targeted:
1. is_tool_allowed((), name) returned True — an agent whose declared
   capabilities intersect its tier floor to an EMPTY set was granted EVERYTHING
   (the empty tuple is falsy; `if not allowed: return True` widened to allow-all).
2. is_tool_allowed granted ANY dotted tool name a pass, even names that are not
   registered action-registry actions — a malicious external MCP server (or a
   prompt-injected agent) could name a tool `memory_remember.get` or `x.y` and
   evade the per-agent whitelist.
3. integrations/mcp_service.call_tool returned early for entity-bound contexts
   BEFORE the capability gate and the P9 sandbox gate, so an entity_id in
   context silently disabled per-agent tool scoping.
4. core/mcp_client._rpc_http parsed the entire HTTP response body without a
   size cap — a compromised/garbage MCP server could push an unbounded JSON
   payload straight into agent context.
5. integrations/mcp_service.execute_tool splatted `**arguments, **context`
   into registry tool functions — duplicate keys and unexpected context keys
   (agent_id/tenant_id/...) blew up typed tool functions with TypeError.
6. is_tool_allowed accepted non-str tool names (unkind dict/None could crash
   the membership + dot checks or slip past the gate).
"""
import asyncio
import json

import pytest
from unittest.mock import MagicMock


# ============================================================================
# capability_resolver: empty intersection & dotted-name bypass
# ============================================================================


class TestIsToolAllowed:
    def test_empty_allowed_set_must_not_grant_everything(self):
        """A resolved empty whitelist (declared caps outside the tier floor)
        must DENY, never become allow-all via falsy-emptiness."""
        from core.capability_resolver import is_tool_allowed

        assert is_tool_allowed((), "memory_remember") is False
        assert is_tool_allowed((), "canvas_render") is False

    def test_unknown_dotted_tool_name_does_not_bypass_whitelist(self):
        """Only names REGISTERED as action-registry actions may skip the raw
        tool whitelist. Unregistered dotted names (e.g. a malicious external
        MCP server naming a tool 'x.y') must be denied."""
        from core.capability_resolver import is_tool_allowed

        allowed = ("canvas_render", "memory_search")
        assert is_tool_allowed(allowed, "evil.injected_tool") is False

    def test_registered_dotted_action_still_allowed(self):
        """Dotted action-registry actions (documents.search, mini_app_run, ...)
        must keep working for restricted agents."""
        from core.capability_resolver import is_tool_allowed
        from core.action_registry import action_registry

        async def _handler(args, context):
            return {"ok": True}

        action_registry.register("bughunt.registered_action", _handler)
        assert is_tool_allowed(("canvas_render",), "bughunt.registered_action") is True

    def test_non_string_tool_name_is_denied(self):
        from core.capability_resolver import is_tool_allowed

        assert is_tool_allowed(("*",), {"name": "x"}) is False
        assert is_tool_allowed(("*",), None) is False


@pytest.mark.asyncio
class TestCallToolCapabilityGate:
    async def test_empty_intersection_blocks_dispatch(self, monkeypatch):
        """An agent whose declared caps vanish against the student floor must be
        BLOCKED at call_tool — not silently granted every tool."""
        from integrations.mcp_service import MCPService

        agent = MagicMock()
        agent.capabilities = ["memory_remember"]  # NOT in the student floor
        agent.status = "STUDENT"
        monkeypatch.setattr(
            "core.capability_resolver.get_agent_for_context", lambda context: agent
        )

        svc = MCPService()
        result = await svc.call_tool(
            "memory_remember",
            {"fact_text": "x", "category": "general"},
            context={"agent_id": "a1", "tier": "student"},
        )
        assert isinstance(result, dict)
        assert result.get("executed") is not True
        assert result.get("blocked_by") == "capability_gate"

    async def test_entity_context_cannot_bypass_capability_gate(self, monkeypatch):
        """entity_id in context must NOT skip the capability gate: a restricted
        agent calling a tool outside its whitelist is blocked even when the
        context looks entity-bound."""
        from integrations.mcp_service import MCPService

        agent = MagicMock()
        agent.capabilities = ["canvas_render"]
        agent.status = "STUDENT"
        monkeypatch.setattr(
            "core.capability_resolver.get_agent_for_context", lambda context: agent
        )

        svc = MCPService()
        executed = []

        async def _fake_entity(context, tool, args):
            executed.append(tool)
            return {"executed": True}

        monkeypatch.setattr(svc, "execute_entity_tool", _fake_entity)

        result = await svc.call_tool(
            "memory_remember",
            {"content": "x"},
            context={
                "agent_id": "a1",
                "tier": "student",
                "entity_id": "e1",
                "entity_type_slug": "vendor",
                "tenant_id": "t1",
            },
        )
        assert executed == []
        assert isinstance(result, dict)
        assert result.get("success") is False

    async def test_entity_bound_call_still_routes_for_unrestricted_agent(
        self, monkeypatch
    ):
        """The entity path keeps working for an unrestricted agent."""
        from integrations.mcp_service import MCPService

        agent = MagicMock()
        agent.capabilities = []
        agent.status = "AUTONOMOUS"
        monkeypatch.setattr(
            "core.capability_resolver.get_agent_for_context", lambda context: agent
        )

        svc = MCPService()
        executed = []

        async def _fake_entity(context, tool, args):
            executed.append(tool)
            return {"result": "ok"}

        monkeypatch.setattr(svc, "execute_entity_tool", _fake_entity)

        result = await svc.call_tool(
            "canvas_render",
            {},
            context={
                "agent_id": "a1",
                "entity_id": "e1",
                "entity_type_slug": "vendor",
                "tenant_id": "t1",
            },
        )
        assert executed == ["canvas_render"]
        assert result["result"] == "ok"


# ============================================================================
# integrations/mcp_service.execute_tool: registry kwargs splat crash
# ============================================================================


class TestExecuteToolRegistryKwargs:
    @pytest.mark.asyncio
    async def test_context_kwargs_do_not_crash_typed_registry_tool(self, monkeypatch):
        """Context keys the tool function does not accept must never be splatted
        onto it (agent_id/tenant_id/... previously raised TypeError)."""
        from integrations.mcp_service import MCPService

        calls = {}

        def _typed(x=1):
            calls["x"] = x
            return "ok"

        fake_meta = MagicMock()
        fake_meta.function = _typed
        fake_registry = MagicMock()
        fake_registry.get.return_value = fake_meta
        fake_registry.get_function.return_value = _typed
        monkeypatch.setattr(
            "integrations.mcp_service.get_tool_registry", lambda: fake_registry
        )

        svc = MCPService()
        result = await svc.execute_tool(
            "local-tools",
            "bughunt_typed_fn",
            {"x": 5},
            {"agent_id": "a1", "user_id": "u1", "tenant_id": "t1"},
        )
        assert result == "ok"
        assert calls["x"] == 5

    @pytest.mark.asyncio
    async def test_explicit_arguments_win_over_context(self, monkeypatch):
        """A key present in both arguments and context must take the argument
        value — no 'multiple values' TypeError."""
        from integrations.mcp_service import MCPService

        calls = {}

        def _typed(x=1, agent_id=None):
            calls["x"] = x
            calls["agent_id"] = agent_id
            return "ok"

        fake_meta = MagicMock()
        fake_meta.function = _typed
        fake_registry = MagicMock()
        fake_registry.get.return_value = fake_meta
        fake_registry.get_function.return_value = _typed
        monkeypatch.setattr(
            "integrations.mcp_service.get_tool_registry", lambda: fake_registry
        )

        svc = MCPService()
        result = await svc.execute_tool(
            "local-tools",
            "bughunt_dup_fn",
            {"x": 5, "agent_id": "from-args"},
            {"agent_id": "from-context"},
        )
        assert result == "ok"
        assert calls["x"] == 5
        assert calls["agent_id"] == "from-args"


# ============================================================================
# core/mcp_client: unbounded HTTP response body
# ============================================================================


class _StubHTTPServer:
    """Tiny async HTTP/1.1 stub that always 200s with a fixed JSON body."""

    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.server = None
        self.port = None

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def _handle(self, reader, writer) -> None:
        try:
            await reader.read(65536)
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Connection: close\r\n\r\n"
            )
            for i in range(0, len(self.payload), 65536):
                writer.write(self.payload[i : i + 65536])
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    async def close(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


class TestMCPClientResponseSizeLimit:
    @pytest.mark.asyncio
    async def test_oversized_response_is_rejected(self):
        from core.mcp_client import MCPClient, MCPClientError

        oversized = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": "x" * (11 * 1024 * 1024)}]},
            }
        ).encode()
        stub = _StubHTTPServer(oversized)
        await stub.start()
        try:
            client = MCPClient(
                "big-server",
                {"transport": "http", "url": f"http://127.0.0.1:{stub.port}"},
            )
            with pytest.raises(MCPClientError):
                await client._rpc_http(
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}}
                )
        finally:
            await stub.close()

    @pytest.mark.asyncio
    async def test_well_sized_response_still_parsed(self):
        from core.mcp_client import MCPClient

        small = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"ok": 1}}).encode()
        stub = _StubHTTPServer(small)
        await stub.start()
        try:
            client = MCPClient(
                "small-server",
                {"transport": "http", "url": f"http://127.0.0.1:{stub.port}"},
            )
            result = await client._rpc_http(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
            )
            assert result == {"ok": 1}
        finally:
            await stub.close()