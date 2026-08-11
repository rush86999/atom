"""Coverage wave 31 — core/atom_saas_client.py (TDD, mocked httpx + websockets).

Drives the marketplace client: config loading (env, token-derived
instance id, missing-token warning), the shared HTTP client factory,
every marketplace endpoint (skills/agents/workflows/domains/components/
analytics/health) with success + HTTPError branches, search pass-through,
WebSocket connect/disconnect (missing dep, missing token, already
connected, handshake failure, dispatch loop with JSON + non-JSON +
handler-error, server-close), sync wrappers, close() and the
AtomSaaSClient alias — zero network, zero spend.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.atom_saas_client import (
    AtomAgentOSMarketplaceClient,
    AtomSaaSClient,
    AtomSaaSConfig,
)


def make_client(config=None, **kw):
    cfg = config or AtomSaaSConfig(
        ws_url="wss://example.com/ws", api_url="https://example.com/api",
        api_token="tok-123", instance_id="inst-1")
    return AtomAgentOSMarketplaceClient(cfg)


class _FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "err", request=MagicMock(), response=MagicMock())
        return None

    def json(self):
        return self._data


class TestConfig:
    def test_load_config_with_token(self, monkeypatch):
        monkeypatch.setenv("ATOM_SAAS_API_TOKEN", "abc123")
        monkeypatch.setenv("ATOM_INSTANCE_ID", "inst-42")
        cfg = AtomAgentOSMarketplaceClient._load_config()
        assert cfg.instance_id == "inst-42"
        assert cfg.api_token == "abc123"
        assert cfg.ws_url == "wss://atomagentos.com/api/ws/satellite/connect"
        monkeypatch.delenv("ATOM_SAAS_API_TOKEN")
        monkeypatch.delenv("ATOM_INSTANCE_ID")

    def test_load_config_derives_instance_id(self, monkeypatch):
        monkeypatch.setenv("ATOM_SAAS_API_TOKEN", "xyz")
        monkeypatch.delenv("ATOM_INSTANCE_ID", raising=False)
        cfg = AtomAgentOSMarketplaceClient._load_config()
        assert cfg.instance_id and len(cfg.instance_id) == 32
        monkeypatch.delenv("ATOM_SAAS_API_TOKEN")

    def test_load_config_missing_token(self, monkeypatch):
        monkeypatch.delenv("ATOM_SAAS_API_TOKEN", raising=False)
        monkeypatch.delenv("ATOM_INSTANCE_ID", raising=False)
        cfg = AtomAgentOSMarketplaceClient._load_config()
        assert cfg.api_token == ""
        assert cfg.instance_id is None

    def test_client_uses_env_config(self, monkeypatch):
        monkeypatch.setenv("ATOM_SAAS_API_TOKEN", "env-tok")
        monkeypatch.delenv("ATOM_INSTANCE_ID", raising=False)
        client = AtomAgentOSMarketplaceClient()
        assert client.config.api_token == "env-tok"
        monkeypatch.delenv("ATOM_SAAS_API_TOKEN")


class TestHttpClientFactory:
    async def test_creates_and_reuses(self):
        client = make_client()
        with patch("core.atom_saas_client.httpx.AsyncClient") as ac:
            c1 = await client._get_http_client()
            c2 = await client._get_http_client()
        assert c1 is c2
        assert client._http_client is c1
        ac.assert_called_once()
        kwargs = ac.call_args.kwargs
        assert kwargs["base_url"] == "https://example.com/api"
        assert kwargs["headers"]["X-API-Token"] == "tok-123"
        assert kwargs["headers"]["X-Instance-ID"] == "inst-1"


class _HttpEnv:
    """Context manager providing a mocked http client with a canned response."""

    def __init__(self, client, response, side_effect=None):
        self.client = client
        self.response = response
        self.side_effect = side_effect
        self.mock_ac = None

    async def __aenter__(self):
        self.mock_ac = AsyncMock()
        method_mock = AsyncMock(return_value=self.response,
                                side_effect=self.side_effect)
        for verb in ["get", "post", "delete", "put"]:
            setattr(self.mock_ac, verb, method_mock)
        patcher = patch.object(self.client, "_get_http_client",
                               new=AsyncMock(return_value=self.mock_ac))
        self._patch = patcher
        patcher.start()
        return self.mock_ac

    async def __aexit__(self, *exc):
        self._patch.stop()


async def _run_with(method, response=None, side_effect=None, client=None, *args, **kwargs):
    client = client or make_client()
    env = _HttpEnv(client, response, side_effect)
    await env.__aenter__()
    try:
        return await method(*args, **kwargs)
    finally:
        await env.__aexit__()


class TestMarketplaceEndpoints:
    async def test_fetch_skills_success(self):
        client = make_client()
        result = await _run_with(
            client.fetch_skills, _FakeResponse({"skills": [{"id": "s1"}], "total": 1}),
            client=client, query="q", category="cat", skill_type="type", page=2, page_size=10)
        assert result["skills"][0]["id"] == "s1"

    async def test_fetch_skills_error(self):
        client = make_client()
        result = await _run_with(
            client.fetch_skills, side_effect=httpx.ConnectError("down"),
            client=client)
        assert result == {"skills": [], "total": 0, "page": 1, "page_size": 20}

    async def test_get_skill_by_id(self):
        client = make_client()
        result = await _run_with(
            client.get_skill_by_id, _FakeResponse({"id": "s1"}), client=client,
            skill_id="s1")
        assert result["id"] == "s1"
        result2 = await _run_with(
            client.get_skill_by_id, side_effect=httpx.HTTPStatusError(
                "e", request=MagicMock(), response=MagicMock()),
            client=client, skill_id="missing")
        assert result2 is None

    async def test_get_categories(self):
        client = make_client()
        result = await _run_with(
            client.get_categories, _FakeResponse(["cat1"]), client=client)
        assert result == ["cat1"]
        result2 = await _run_with(
            client.get_categories, side_effect=httpx.ConnectError("x"), client=client)
        assert result2 == []

    async def test_rate_skill_invalid_rating(self):
        client = make_client()
        result = await client.rate_skill("s1", "u1", 6)
        assert result["success"] is False
        assert "between 1 and 5" in result["error"]

    async def test_rate_skill_success_and_error(self):
        client = make_client()
        result = await _run_with(
            client.rate_skill, _FakeResponse({"success": True}), client=client,
            skill_id="s1", user_id="u1", rating=5, comment="good")
        assert result["success"] is True
        result2 = await _run_with(
            client.rate_skill, side_effect=httpx.ConnectError("x"), client=client,
            skill_id="s1", user_id="u1", rating=3)
        assert result2["success"] is False

    async def test_install_uninstall_skill(self):
        client = make_client()
        result = await _run_with(
            client.install_skill, _FakeResponse({"ok": True}), client=client,
            skill_id="s1", agent_id="ag-1", auto_install_deps=False)
        assert result["ok"] is True
        result2 = await _run_with(
            client.uninstall_skill, _FakeResponse({"ok": True}), client=client,
            skill_id="s1", agent_id="ag-1")
        assert result2["ok"] is True
        result3 = await _run_with(
            client.uninstall_skill, side_effect=httpx.ConnectError("x"), client=client,
            skill_id="s1", agent_id="ag-1")
        assert result3["success"] is False

    async def test_fetch_agents(self):
        client = make_client()
        result = await _run_with(
            client.fetch_agents, _FakeResponse({"agents": [], "total": 0}), client=client,
            category="sales")
        assert result["total"] == 0
        result2 = await _run_with(
            client.fetch_agents, side_effect=httpx.ConnectError("x"), client=client)
        assert result2["agents"] == []

    async def test_agent_template_and_install(self):
        client = make_client()
        result = await _run_with(
            client.get_agent_template, _FakeResponse({"id": "t1"}), client=client,
            template_id="t1")
        assert result["id"] == "t1"
        result2 = await _run_with(
            client.get_agent_template, side_effect=httpx.ConnectError("x"), client=client,
            template_id="t1")
        assert result2 is None
        result3 = await _run_with(
            client.install_agent, _FakeResponse({"ok": True}), client=client,
            template_id="t1", tenant_id="tn")
        assert result3["ok"] is True

    async def test_fetch_workflows_and_template(self):
        client = make_client()
        result = await _run_with(
            client.fetch_workflows, _FakeResponse({"workflows": [1]}), client=client)
        assert result["workflows"] == [1]
        result2 = await _run_with(
            client.fetch_workflows, side_effect=httpx.ConnectError("x"), client=client)
        assert result2["workflows"] == []
        result3 = await _run_with(
            client.get_workflow_template, _FakeResponse({"id": "w1"}), client=client,
            template_id="w1")
        assert result3["id"] == "w1"
        result4 = await _run_with(
            client.get_workflow_template, side_effect=httpx.ConnectError("x"), client=client,
            template_id="w1")
        assert result4 is None

    async def test_fetch_domains_and_template(self):
        client = make_client()
        result = await _run_with(
            client.fetch_domains, _FakeResponse({"domains": []}), client=client)
        assert result["domains"] == []
        result2 = await _run_with(
            client.fetch_domains, side_effect=httpx.ConnectError("x"), client=client)
        assert result2["domains"] == []
        result3 = await _run_with(
            client.get_domain_template, _FakeResponse({"id": "d1"}), client=client,
            domain_id="d1")
        assert result3["id"] == "d1"
        result4 = await _run_with(
            client.install_domain, _FakeResponse({"ok": True}), client=client,
            domain_id="d1", tenant_id="tn")
        assert result4["ok"] is True

    async def test_search_skills_passthrough(self):
        client = make_client()
        with patch.object(client, "fetch_skills", new=AsyncMock(return_value={"skills": []})) as fs:
            await client.search_skills("q", {"category": "cat", "skill_type": "type"})
            fs.assert_called_once_with(query="q", category="cat", skill_type="type")
            await client.search_skills("q2", None)
            assert fs.call_args.kwargs["category"] is None

    async def test_register_instance(self):
        client = make_client()
        result = await _run_with(
            client.register_instance, _FakeResponse({"instance_id": "i1"}), client=client,
            instance_name="my-box", version="2.0", platform="mac")
        assert result["instance_id"] == "i1"
        result2 = await _run_with(
            client.register_instance, side_effect=httpx.ConnectError("x"), client=client)
        assert result2["success"] is False

    async def test_push_analytics_empty(self):
        client = make_client()
        result = await client.push_analytics("i1", [])
        assert result == {"success": True, "count": 0}

    async def test_push_analytics(self):
        client = make_client()
        result = await _run_with(
            client.push_analytics, _FakeResponse({"ok": True}), client=client,
            instance_id="i1", reports=[{"r": 1}])
        assert result["ok"] is True
        result2 = await _run_with(
            client.push_analytics, side_effect=httpx.ConnectError("x"), client=client,
            instance_id="i1", reports=[{"r": 1}])
        assert result2["success"] is False

    async def test_fetch_components(self):
        client = make_client()
        result = await _run_with(
            client.fetch_components, _FakeResponse({"components": [{"id": "c1"}]}),
            client=client, category="charts", page=2, page_size=5)
        assert result["components"][0]["id"] == "c1"
        result2 = await _run_with(
            client.fetch_components, side_effect=httpx.ConnectError("x"), client=client)
        assert result2["components"] == []

    async def test_component_details_and_install(self):
        client = make_client()
        result = await _run_with(
            client.get_component_details, _FakeResponse({"id": "c1"}), client=client,
            component_id="c1")
        assert result["id"] == "c1"
        result2 = await _run_with(
            client.get_component_details, side_effect=httpx.ConnectError("x"), client=client,
            component_id="c1")
        assert result2 is None
        result3 = await _run_with(
            client.install_component, _FakeResponse({"ok": True}), client=client,
            component_id="c1", canvas_id="cv")
        assert result3["ok"] is True

    async def test_health_check(self):
        client = make_client()
        assert await _run_with(client.health_check, _FakeResponse({}), client=client) is True
        assert await _run_with(
            client.health_check, side_effect=httpx.ConnectError("x"), client=client) is False


class TestWebSocket:
    async def test_missing_dependency(self):
        client = make_client()
        with patch.dict("sys.modules", {"websockets": None}):
            with patch("builtins.__import__", side_effect=ImportError("no websockets")):
                with pytest.raises(RuntimeError, match="websockets"):
                    await client.connect_websocket(lambda p: None)

    async def test_missing_token(self):
        cfg = AtomSaaSConfig(ws_url="wss://x", api_url="https://x", api_token="")
        client = make_client(cfg)
        with patch.dict("sys.modules", {"websockets": MagicMock()}):
            with pytest.raises(RuntimeError, match="API_TOKEN"):
                await client.connect_websocket(lambda p: None)

    async def test_already_connected(self):
        client = make_client()
        client._connected = True
        client._ws_connection = MagicMock()
        with patch.dict("sys.modules", {"websockets": MagicMock()}):
            await client.connect_websocket(lambda p: None)  # no-op

    async def test_connection_failure(self):
        client = make_client()
        ws_mod = MagicMock()
        ws_mod.connect = AsyncMock(side_effect=ConnectionError("refused"))
        with patch.dict("sys.modules", {"websockets": ws_mod}):
            with pytest.raises(RuntimeError, match="connection failed"):
                await client.connect_websocket(lambda p: None)
        assert client._connected is False

    async def test_dispatch_loop(self):
        client = make_client()
        ws_mod = MagicMock()
        connection = MagicMock()
        connection.__aiter__ = lambda s: _Iter([b'{"type": "update", "x": 1}', "not-json",
                                               b'{"ok": true}'])
        ws_mod.connect = AsyncMock(return_value=connection)
        ws_mod.exceptions.ConnectionClosed = type("CC", (Exception,), {})
        handled = []
        async def handler(payload):
            handled.append(payload)
        with patch.dict("sys.modules", {"websockets": ws_mod}):
            await client.connect_websocket(handler)
        assert len(handled) == 3
        assert handled[0]["type"] == "update"
        assert handled[1] == "not-json"
        assert client._connected is False  # loop ended → reset
        assert client._ws_connection is None

    async def test_handler_error_tolerated(self):
        client = make_client()
        ws_mod = MagicMock()
        connection = MagicMock()
        connection.__aiter__ = lambda s: _Iter([b'{"a": 1}'])
        ws_mod.connect = AsyncMock(return_value=connection)
        ws_mod.exceptions.ConnectionClosed = type("CC", (Exception,), {})
        async def handler(payload):
            raise RuntimeError("handler boom")
        with patch.dict("sys.modules", {"websockets": ws_mod}):
            await client.connect_websocket(handler)  # no crash

    async def test_connection_closed_by_server(self):
        client = make_client()
        ws_mod = MagicMock()
        connection = MagicMock()
        cc = type("ConnectionClosed", (Exception,), {})
        ws_mod.exceptions.ConnectionClosed = cc

        class _RaiseCC:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise cc("closed")

        ws_mod.connect = AsyncMock(return_value=_RaiseCC())
        with patch.dict("sys.modules", {"websockets": ws_mod}):
            await client.connect_websocket(lambda p: None)  # handled gracefully

    async def test_disconnect(self):
        client = make_client()
        conn = MagicMock()
        conn.close = AsyncMock()
        client._ws_connection = conn
        client._connected = True
        await client.disconnect_websocket()
        conn.close.assert_called_once()
        assert client._ws_connection is None
        assert client._connected is False
        await client.disconnect_websocket()  # no connection — no crash

    async def test_close(self):
        client = make_client()
        http = MagicMock()
        http.aclose = AsyncMock()
        client._http_client = http
        await client.close()
        http.aclose.assert_called_once()
        assert client._http_client is None


class _Iter:
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


class TestSyncWrappers:
    def test_sync_wrappers(self):
        client = make_client()
        with patch.object(client, "fetch_skills", new=AsyncMock(return_value={"skills": []})):
            assert client.fetch_skills_sync() == {"skills": []}
        with patch.object(client, "get_skill_by_id", new=AsyncMock(return_value={"id": "s"})):
            assert client.get_skill_by_id_sync("s") == {"id": "s"}
        with patch.object(client, "get_categories", new=AsyncMock(return_value=[])):
            assert client.get_categories_sync() == []
        with patch.object(client, "rate_skill", new=AsyncMock(return_value={"success": True})):
            assert client.rate_skill_sync("s", "u", 4)["success"] is True
        with patch.object(client, "install_skill", new=AsyncMock(return_value={"ok": True})):
            assert client.install_skill_sync("s", "a")["ok"] is True
        with patch.object(client, "uninstall_skill", new=AsyncMock(return_value={"ok": True})):
            assert client.uninstall_skill_sync("s", "a")["ok"] is True
        with patch.object(client, "search_skills", new=AsyncMock(return_value={})):
            assert client.search_skills_sync("q") == {}
        with patch.object(client, "fetch_agents", new=AsyncMock(return_value={})):
            assert client.fetch_agents_sync() == {}
        with patch.object(client, "get_agent_template", new=AsyncMock(return_value={})):
            assert client.get_agent_template_sync("t") == {}
        with patch.object(client, "install_agent", new=AsyncMock(return_value={})):
            assert client.install_agent_sync("t", "tn") == {}
        with patch.object(client, "fetch_workflows", new=AsyncMock(return_value={})):
            assert client.fetch_workflows_sync() == {}
        with patch.object(client, "get_workflow_template", new=AsyncMock(return_value={})):
            assert client.get_workflow_template_sync("w") == {}
        with patch.object(client, "fetch_domains", new=AsyncMock(return_value={})):
            assert client.fetch_domains_sync() == {}
        with patch.object(client, "get_domain_template", new=AsyncMock(return_value={})):
            assert client.get_domain_template_sync("d") == {}
        with patch.object(client, "install_domain", new=AsyncMock(return_value={})):
            assert client.install_domain_sync("d", "tn") == {}
        with patch.object(client, "fetch_components", new=AsyncMock(return_value={})):
            assert client.fetch_components_sync() == {}
        with patch.object(client, "get_component_details", new=AsyncMock(return_value={})):
            assert client.get_component_details_sync("c") == {}
        with patch.object(client, "install_component", new=AsyncMock(return_value={})):
            assert client.install_component_sync("c") == {}
        with patch.object(client, "register_instance", new=AsyncMock(return_value={})):
            assert client.register_instance_sync() == {}
        with patch.object(client, "push_analytics", new=AsyncMock(return_value={})):
            assert client.push_analytics_sync("i", []) == {}
        with patch.object(client, "health_check", new=AsyncMock(return_value=True)):
            assert client.health_check_sync() is True

    def test_alias(self):
        assert AtomSaaSClient is AtomAgentOSMarketplaceClient
