"""
Round 72 — Workstream H: read-only tool-result memoization.

Tests the bounded LRU+TTL cache in ``core.mcp_service.MCPService.execute_tool``:
  * cacheable registry tools are memoized across identical calls
  * cache key is tenant-scoped (no cross-tenant result reuse)
  * TTL expiry re-executes the tool
  * state-changing tools (cacheable=False) are never cached
  * hardcoded read-only whitelist is honored (and mutators excluded)
  * error results are never cached
  * cache disabled by ATOM_TOOL_CACHE_ENABLED=false
  * cache is bounded (256 entries)
"""
import time

import pytest

import core.mcp_service as mcp_mod
from tools.registry import ToolRegistry


@pytest.fixture(autouse=True)
def _env_isolate(monkeypatch):
    """Isolate from dev env vars so R72 defaults (cache ON, sandbox OFF) apply."""
    monkeypatch.delenv("ATOM_TOOL_CACHE_ENABLED", raising=False)
    monkeypatch.delenv("ATOM_TOOL_CACHE_TTL", raising=False)
    monkeypatch.delenv("ATOM_SANDBOX_ENABLED", raising=False)
    monkeypatch.delenv("ATOM_SANDBOX_FORCE_ENFORCE", raising=False)


@pytest.fixture
def bare_service():
    """A fresh MCPService instance with an empty cache and no registry.

    Bypasses the singleton's heavy get_tool_registry() initialization; the
    test sets ``tool_registry`` explicitly per case. The class-level
    ``_instance`` is restored on teardown so the module-global ``mcp_service``
    consumers are unaffected.
    """
    original_instance = mcp_mod.MCPService._instance
    mcp_mod.MCPService._instance = None
    svc = mcp_mod.MCPService.__new__(mcp_mod.MCPService)
    svc.initialized = True
    svc.servers = {}
    svc.tools_cache = {}
    svc.workspace_tools = {}
    svc._tool_cache = {}
    svc.tool_registry = None
    yield svc
    mcp_mod.MCPService._instance = original_instance


def _register(svc: mcp_mod.MCPService, name: str, cacheable: bool, calls: list):
    """Register a stub read-only tool and attach it to the service registry."""
    async def stub(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "value": kwargs.get("path") or kwargs.get("i")}

    reg = ToolRegistry()
    reg.register(
        name=name,
        function=stub,
        category="test",
        complexity=1,
        cacheable=cacheable,
    )
    svc.tool_registry = reg
    return stub


class TestToolCache:
    @pytest.mark.asyncio
    async def test_cacheable_tool_memoized(self, bare_service):
        calls: list = []
        _register(bare_service, "fake_read", cacheable=True, calls=calls)

        r1 = await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t1"}
        )
        r2 = await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t1"}
        )

        assert r1 == r2 == {"ok": True, "value": "/a"}
        assert len(calls) == 1, "second identical call should be a cache HIT"
        assert len(bare_service._tool_cache) == 1

    @pytest.mark.asyncio
    async def test_cache_key_is_tenant_scoped(self, bare_service):
        calls: list = []
        _register(bare_service, "fake_read", cacheable=True, calls=calls)

        await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t1"}
        )
        await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t2"}
        )

        assert len(calls) == 2, "different tenants must never share a result"
        assert len(bare_service._tool_cache) == 2

    @pytest.mark.asyncio
    async def test_ttl_zero_disables_memoization(self, bare_service, monkeypatch):
        calls: list = []
        _register(bare_service, "fake_read", cacheable=True, calls=calls)
        monkeypatch.setenv("ATOM_TOOL_CACHE_TTL", "0")  # TTL=0 -> no caching

        await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t1"}
        )
        await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t1"}
        )
        assert len(calls) == 2, "TTL 0 must disable memoization"
        assert len(bare_service._tool_cache) == 0

    @pytest.mark.asyncio
    async def test_ttl_expiry_with_sleep(self, bare_service, monkeypatch):
        calls: list = []
        _register(bare_service, "fake_read", cacheable=True, calls=calls)

        monkeypatch.setenv("ATOM_TOOL_CACHE_TTL", "1")
        await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t1"}
        )
        await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t1"}
        )
        assert len(calls) == 1  # still within TTL

        time.sleep(1.1)
        await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t1"}
        )
        assert len(calls) == 2, "expired entry must re-execute"

    @pytest.mark.asyncio
    async def test_state_changing_tool_never_cached(self, bare_service):
        calls: list = []
        _register(bare_service, "fake_write", cacheable=False, calls=calls)

        await bare_service.execute_tool(
            "fake_write", {"path": "/a"}, {"tenant_id": "t1"}
        )
        await bare_service.execute_tool(
            "fake_write", {"path": "/a"}, {"tenant_id": "t1"}
        )

        assert len(calls) == 2, "cacheable=False tools must never be memoized"
        assert len(bare_service._tool_cache) == 0

    @pytest.mark.asyncio
    async def test_error_results_never_cached(self, bare_service):
        async def failing(**kwargs):
            return {"error": "boom", "status": "error"}

        reg = ToolRegistry()
        reg.register(
            name="fake_flaky",
            function=failing,
            category="test",
            complexity=1,
            cacheable=True,
        )
        bare_service.tool_registry = reg

        r1 = await bare_service.execute_tool(
            "fake_flaky", {"path": "/a"}, {"tenant_id": "t1"}
        )
        r2 = await bare_service.execute_tool(
            "fake_flaky", {"path": "/a"}, {"tenant_id": "t1"}
        )

        assert r1 == r2 == {"error": "boom", "status": "error"}
        assert len(bare_service._tool_cache) == 0, "errors must never be cached"

    @pytest.mark.asyncio
    async def test_cache_disabled_by_flag(self, bare_service, monkeypatch):
        calls: list = []
        _register(bare_service, "fake_read", cacheable=True, calls=calls)
        monkeypatch.setenv("ATOM_TOOL_CACHE_ENABLED", "false")

        await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t1"}
        )
        await bare_service.execute_tool(
            "fake_read", {"path": "/a"}, {"tenant_id": "t1"}
        )

        assert len(calls) == 2, "flag off must disable memoization"
        assert len(bare_service._tool_cache) == 0

    @pytest.mark.asyncio
    async def test_cache_bounded_at_256(self, bare_service):
        calls: list = []
        _register(bare_service, "evict_tool", cacheable=True, calls=calls)

        for i in range(260):
            await bare_service.execute_tool(
                "evict_tool", {"i": i}, {"tenant_id": "t"}
            )

        assert len(bare_service._tool_cache) <= 256, "cache must stay bounded"

    def test_hardcoded_read_only_whitelist(self, bare_service):
        # tool_registry is None here — resolution falls back to the whitelist.
        assert bare_service._tool_is_cacheable("read_codebase") is True
        assert bare_service._tool_is_cacheable("list_directory_recursive") is True
        assert bare_service._tool_is_cacheable("get_all_tools") is True
        # Mutators are excluded.
        assert bare_service._tool_is_cacheable("write_code_file") is False
        assert bare_service._tool_is_cacheable("run_local_terminal") is False

    def test_registry_metadata_roundtrip_cacheable(self):
        """ToolMetadata.to_dict() surfaces the cacheable flag."""
        async def stub(**kwargs):
            return {"ok": True}

        reg = ToolRegistry()
        reg.register(name="read_thing", function=stub, category="test",
                     complexity=1, cacheable=True)
        reg.register(name="write_thing", function=stub, category="test",
                     complexity=2, cacheable=False)

        by_name = {t["name"]: t for t in reg.export_all()}
        assert by_name["read_thing"]["cacheable"] is True
        assert by_name["write_thing"]["cacheable"] is False
