# -*- coding: utf-8 -*-
"""Coverage wave 100 — verified gaps only.

- core/smarthome/home_assistant_service.py (was 38%)
- core/mini_app_integration_dispatch.py (was 79%)

All other modules in the wave-100 list were verified already >=80% via
existing suites (see final report).

Standalone: each module reaches >=80% line coverage from this file alone.
No network / no LLM / no real DB: httpx boundaries mocked, plain mocks for
dispatch dependencies.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _hresp(status=200, json_data=None, content=None):
    r = httpx.Response(
        status,
        json=json_data if json_data is not None else {},
        request=httpx.Request("GET", "http://ha.local/api/x"),
    )
    if content is not None:
        r._content = content
    return r


# ============================================================================
# core/smarthome/home_assistant_service.py
# ============================================================================
from core.feature_flags import FeatureFlags
from core.smarthome.home_assistant_service import (
    HomeAssistantService,
    create_home_assistant_service,
)


def _ha(client=None):
    svc = HomeAssistantService("http://ha.local:8123/", "tok123")
    if client is not None:
        svc.client = client
    return svc


async def test_init_strips_trailing_slash_and_sets_headers():
    svc = _ha()
    try:
        assert svc.base_url == "http://ha.local:8123"
        assert svc.token == "tok123"
        assert svc.client.headers["Authorization"] == "Bearer tok123"
    finally:
        await svc.close()


async def test_init_requires_base_url_and_token():
    with pytest.raises(ValueError):
        HomeAssistantService("", "tok")
    with pytest.raises(ValueError):
        HomeAssistantService("http://ha", "")


async def test_get_states_ok():
    client = AsyncMock()
    client.get.return_value = _hresp(
        200, [{"entity_id": "light.a", "state": "on"}]
    )
    svc = _ha(client)
    states = await svc.get_states()
    assert states[0]["entity_id"] == "light.a"
    client.get.assert_awaited_once_with("http://ha.local:8123/api/states")


async def test_get_states_401_404_other_and_conn_error():
    for status, exc in ((401, PermissionError), (404, ConnectionError), (500, httpx.HTTPStatusError)):
        client = AsyncMock()
        client.get.return_value = _hresp(status)
        svc = _ha(client)
        with pytest.raises(exc):
            await svc.get_states()
    client = AsyncMock()
    client.get.side_effect = RuntimeError("boom")
    svc = _ha(client)
    with pytest.raises(ConnectionError):
        await svc.get_states()


async def test_get_states_disabled_feature_flag():
    svc = _ha()
    try:
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await svc.get_states()
    finally:
        await svc.close()


async def test_get_state_ok_and_errors():
    client = AsyncMock()
    client.get.return_value = _hresp(200, {"entity_id": "sensor.t", "state": "21"})
    svc = _ha(client)
    st = await svc.get_state("sensor.t")
    assert st["state"] == "21"
    client.get.assert_awaited_once_with("http://ha.local:8123/api/states/sensor.t")

    for status, exc in ((401, PermissionError), (404, ValueError), (500, httpx.HTTPStatusError)):
        client = AsyncMock()
        client.get.return_value = _hresp(status)
        svc = _ha(client)
        with pytest.raises(exc):
            await svc.get_state("sensor.t")

    client = AsyncMock()
    client.get.side_effect = OSError("net down")
    svc = _ha(client)
    with pytest.raises(OSError):
        await svc.get_state("sensor.t")

    svc = _ha()
    try:
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await svc.get_state("x.y")
    finally:
        await svc.close()


async def test_call_service_ok_variants():
    # with entity + data
    client = AsyncMock()
    client.post.return_value = _hresp(200, {"ok": True})
    svc = _ha(client)
    res = await svc.call_service("light", "turn_on", "light.a", {"brightness_pct": 80})
    assert res == {"ok": True}
    client.post.assert_awaited_once_with(
        "http://ha.local:8123/api/services/light/turn_on",
        json={"entity_id": "light.a", "brightness_pct": 80},
    )

    # empty body / empty response content
    client = AsyncMock()
    client.post.return_value = _hresp(200, content=b"")
    svc = _ha(client)
    res = await svc.call_service("switch", "toggle")
    assert res == {}
    client.post.assert_awaited_once_with(
        "http://ha.local:8123/api/services/switch/toggle", json={}
    )


async def test_call_service_errors():
    for status, exc in (
        (401, PermissionError),
        (404, ValueError),
        (400, ValueError),
        (500, httpx.HTTPStatusError),
    ):
        client = AsyncMock()
        client.post.return_value = _hresp(status)
        svc = _ha(client)
        with pytest.raises(exc):
            await svc.call_service("light", "turn_on", "light.a")

    client = AsyncMock()
    client.post.side_effect = RuntimeError("post boom")
    svc = _ha(client)
    with pytest.raises(RuntimeError):
        await svc.call_service("light", "turn_on")

    svc = _ha()
    try:
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await svc.call_service("light", "turn_on")
    finally:
        await svc.close()


async def test_trigger_automation_ok_and_error():
    client = AsyncMock()
    client.post.return_value = _hresp(200, {"result": "triggered"})
    svc = _ha(client)
    res = await svc.trigger_automation("automation.bedtime")
    assert res == {"result": "triggered"}
    client.post.assert_awaited_once_with(
        "http://ha.local:8123/api/services/automation/trigger",
        json={"entity_id": "automation.bedtime"},
    )

    client = AsyncMock()
    client.post.side_effect = RuntimeError("nope")
    svc = _ha(client)
    with pytest.raises(RuntimeError):
        await svc.trigger_automation("automation.x")

    svc = _ha()
    try:
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await svc.trigger_automation("automation.x")
    finally:
        await svc.close()


async def test_get_entities_by_domain_and_convenience():
    client = AsyncMock()
    client.get.return_value = _hresp(
        200,
        [
            {"entity_id": "light.a", "state": "on"},
            {"entity_id": "switch.s", "state": "off"},
            {"entity_id": "group.g", "state": "on"},
        ],
    )
    svc = _ha(client)
    lights = await svc.get_lights()
    assert [e["entity_id"] for e in lights] == ["light.a"]
    svc2 = _ha(AsyncMock())
    svc2.client.get.return_value = _hresp(
        200,
        [
            {"entity_id": "switch.s"},
            {"entity_id": "group.all_lights"},
        ],
    )
    switches = await svc2.get_switches()
    assert [e["entity_id"] for e in switches] == ["switch.s"]
    groups = await svc2.get_groups()
    assert [e["entity_id"] for e in groups] == ["group.all_lights"]

    # error propagation from get_states
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("refused")
    svc = _ha(client)
    with pytest.raises(Exception):
        await svc.get_entities_by_domain("light")

    svc = _ha()
    try:
        with patch.object(FeatureFlags, "SMART_HOME_CONTROL_ENABLED", False):
            with pytest.raises(PermissionError):
                await svc.get_entities_by_domain("light")
    finally:
        await svc.close()


async def test_create_home_assistant_service_factory():
    svc = await create_home_assistant_service("http://x:8123", "t")
    try:
        assert isinstance(svc, HomeAssistantService)
        assert svc.base_url == "http://x:8123"
    finally:
        await svc.close()


# ============================================================================
# core/mini_app_integration_dispatch.py
# ============================================================================
import core.mini_app_integration_dispatch as disp
from core.mini_app_integration_dispatch import (
    MCP,
    NATIVE,
    PIECE,
    dispatch,
    execute_mcp,
    execute_native,
    execute_piece,
    resolve_backend,
)


class TestMiniAppDispatchHelpers:
    def test_to_piece_name(self):
        assert disp._to_piece_name("slack") == "@activepieces/piece-slack"
        assert (
            disp._to_piece_name("@activepieces/piece-x") == "@activepieces/piece-x"
        )

    def test_mcp_tool_candidates(self):
        assert disp._mcp_tool_candidates("s", "a") == ("s_a", "s.a", "a")

    def test_resolve_native_true_false_and_error(self):
        import core.integration_registry as ireg

        with patch.object(ireg, "DEFAULT_SERVICE_REGISTRY", {"slack": object()}):
            assert disp._resolve_native("slack") is True
        # not registered
        assert disp._resolve_native("definitely-not-a-service-xyz") is False
        with patch.dict(
            "sys.modules", {"core.integration_registry": None}
        ):
            assert disp._resolve_native("slack") is False

    @pytest.mark.anyio
    async def test_resolve_piece_true_false(self):
        import core.external_integration_service as eis

        with patch.object(
            eis.ExternalIntegrationService,
            "get_piece_details",
            AsyncMock(return_value={"name": "x"}),
        ):
            assert await disp._resolve_piece("slack") is True
        with patch.object(
            eis.ExternalIntegrationService,
            "get_piece_details",
            AsyncMock(side_effect=RuntimeError("bridge down")),
        ):
            assert await disp._resolve_piece("slack") is False

    def test_resolve_mcp_objects_dicts_and_none(self):
        import core.mcp_service as ms

        obj_tool = SimpleNamespace(name="slack_send")
        cache = {
            "srv1": [obj_tool],
            "srv2": [{"name": "gh.run"}],
        }
        with patch.object(ms.mcp_service, "tools_cache", cache):
            assert disp._resolve_mcp("slack", "send") == "srv1"
            assert disp._resolve_mcp("gh", "run") == "srv2"
            assert disp._resolve_mcp("nope", "x") is None
        with patch.object(ms.mcp_service, "tools_cache", None):
            assert disp._resolve_mcp("a", "b") is None

    @pytest.mark.anyio
    async def test_resolve_backend_order(self):
        import core.integration_registry as ireg
        import core.mcp_service as ms

        with patch.object(ireg, "DEFAULT_SERVICE_REGISTRY", {"slack": object()}):
            assert await resolve_backend("slack", "x") == (NATIVE, None)

        with patch.object(ireg, "DEFAULT_SERVICE_REGISTRY", set()):
            import core.external_integration_service as eis

            with patch.object(
                eis.ExternalIntegrationService,
                "get_piece_details",
                AsyncMock(return_value={"x": 1}),
            ):
                assert await resolve_backend("svc", "x") == (PIECE, None)
            with patch.object(
                eis.ExternalIntegrationService,
                "get_piece_details",
                AsyncMock(return_value=None),
            ):
                with patch.object(
                    ms.mcp_service, "tools_cache", {"srv": [{"name": "svc_x"}]}
                ):
                    assert await resolve_backend("svc", "x") == (MCP, "srv")
                with patch.object(ms.mcp_service, "tools_cache", {}):
                    assert await resolve_backend("svc", "x") == (None, None)


class TestMiniAppDispatchExecution:
    def _db(self, row=None):
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value.order_by.return_value.first.return_value = row
        return db

    def test_load_token_row_ok_and_error(self):
        db = self._db(row=SimpleNamespace(access_token="a"))
        assert disp._load_token_row("t", "slack", db) is not None
        db2 = MagicMock()
        db2.query.side_effect = RuntimeError("db down")
        assert disp._load_token_row("t", "slack", db2) is None

    def test_creds_dict_decrypted_and_fallback(self):
        import core.privsec.token_encryption as te

        row = SimpleNamespace(
            access_token="enc",
            refresh_token="renc",
            token_type="bearer",
            instance_url="http://i",
        )
        with patch.object(te, "decrypt_token", lambda s: f"dec:{s}"):
            d = disp._creds_dict(row)
            assert d["access_token"] == "dec:enc"
            assert d["refresh_token"] == "dec:renc"
            assert d["token_type"] == "bearer"
        # decrypt raises -> plaintext fallback
        with patch.object(te, "decrypt_token", side_effect=RuntimeError("no key")):
            d = disp._creds_dict(row)
            assert d["access_token"] == "enc"
            assert d["refresh_token"] == "renc"
        row2 = SimpleNamespace(
            access_token="enc", refresh_token=None, token_type=None, instance_url=None
        )
        with patch.object(te, "decrypt_token", lambda s: s):
            d = disp._creds_dict(row2)
            assert d["refresh_token"] is None

    @pytest.mark.anyio
    async def test_execute_native_success_and_variants(self):
        import core.integration_registry as ireg

        row = SimpleNamespace(
            access_token="a", refresh_token=None, token_type="b", instance_url=None
        )
        db = self._db(row=row)
        inst = MagicMock()
        inst.execute_operation = AsyncMock(return_value={"result": 1})

        class Svc:
            def __init__(self, tenant_id=None, config=None):
                pass

            async def execute_operation(self, action, params, context=None):
                return await inst.execute_operation(action, params, context=context)

        class SvcNoKw:
            def __init__(self, config=None):
                pass

            async def execute_operation(self, action, params, context=None):
                return {"fallback": True}

        reg = MagicMock()
        reg.get_service_class.return_value = Svc
        with patch.object(ireg, "IntegrationRegistry", lambda: reg):
            res = await execute_native("slack", "send", {}, "t1", db)
        assert res["ok"] is True and res["data"] == {"result": 1}

        reg2 = MagicMock()
        reg2.get_service_class.return_value = SvcNoKw
        with patch.object(ireg, "IntegrationRegistry", lambda: reg2):
            res = await execute_native("slack", "send", {}, "t1", db)
        assert res["ok"] is True and res["data"] == {"fallback": True}

        # no token row -> default config
        db_notok = self._db(row=None)
        with patch.object(ireg, "IntegrationRegistry", lambda: reg):
            res = await execute_native("slack", "send", {}, "t1", db_notok)
        assert res["ok"] is True

        # service class not found
        reg3 = MagicMock()
        reg3.get_service_class.return_value = None
        with patch.object(ireg, "IntegrationRegistry", lambda: reg3):
            res = await execute_native("slack", "send", {}, "t1", db)
        assert res == {"ok": False, "error": "native_service_not_found"}

        # unexpected exception -> isolated failure
        reg4 = MagicMock()
        reg4.get_service_class.side_effect = RuntimeError("boom")
        with patch.object(ireg, "IntegrationRegistry", lambda: reg4):
            res = await execute_native("slack", "send", {}, "t1", db)
        assert res["ok"] is False and res["error"] == "failed"

    @pytest.mark.anyio
    async def test_execute_piece_variants(self):
        import core.external_integration_service as eis

        db = self._db(row=None)
        # attribute-shaped result
        with patch.object(
            eis.ExternalIntegrationService,
            "execute_integration_action",
            AsyncMock(return_value=SimpleNamespace(data={"a": 1})),
        ):
            res = await execute_piece("slack", "send", {}, "t1", db)
        assert res["ok"] is True and res["data"] == {"a": 1}

        # dict-shaped result
        with patch.object(
            eis.ExternalIntegrationService,
            "execute_integration_action",
            AsyncMock(return_value={"data": {"b": 2}}),
        ):
            res = await execute_piece("slack", "send", {}, "t1", db)
        assert res["data"] == {"b": 2}

        # raw result
        with patch.object(
            eis.ExternalIntegrationService,
            "execute_integration_action",
            AsyncMock(return_value={"raw": 3}),
        ):
            res = await execute_piece("slack", "send", {}, "t1", db)
        assert res["data"] == {"raw": 3}

        # with token row creds
        db_row = self._db(
            row=SimpleNamespace(
                access_token="a", refresh_token=None, token_type=None, instance_url=None
            )
        )
        m = AsyncMock(return_value={"data": 1})
        with patch.object(
            eis.ExternalIntegrationService, "execute_integration_action", m
        ):
            await execute_piece("slack", "send", {}, "t1", db_row)
        assert m.await_args.kwargs["credentials"]["access_token"] == "a"

        # failure
        with patch.object(
            eis.ExternalIntegrationService,
            "execute_integration_action",
            AsyncMock(side_effect=RuntimeError("bridge down")),
        ):
            res = await execute_piece("slack", "send", {}, "t1", db)
        assert res["ok"] is False and res["error"] == "failed"

    @pytest.mark.anyio
    async def test_execute_mcp_variants(self):
        import core.mcp_service as ms

        with patch.object(
            ms.mcp_service,
            "call_external_tool",
            AsyncMock(return_value={"out": 1}),
        ):
            res = await execute_mcp("srv", "tool", {})
        assert res["ok"] is True and res["data"] == {"out": 1}

        with patch.object(
            ms.mcp_service,
            "call_external_tool",
            AsyncMock(side_effect=RuntimeError("mcp down")),
        ):
            res = await execute_mcp("srv", "tool", {})
        assert res["ok"] is False and res["backend"] == MCP

    @pytest.mark.anyio
    async def test_dispatch_routes_all_backends_and_not_found(self):
        import core.integration_registry as ireg
        import core.mcp_service as ms

        db = self._db(row=None)
        # native route
        with patch.object(ireg, "DEFAULT_SERVICE_REGISTRY", {"slack": object()}):
            reg = MagicMock()
            inst = MagicMock()
            inst.execute_operation = AsyncMock(return_value={"n": 1})
            cls = lambda **kw: inst
            reg.get_service_class.return_value = cls
            with patch.object(ireg, "IntegrationRegistry", lambda: reg):
                res = await dispatch("slack", "send", {}, tenant_id="t1", db=db)
        assert res["ok"] is True and res["backend"] == NATIVE

        # piece route
        import core.external_integration_service as eis

        with patch.object(ireg, "DEFAULT_SERVICE_REGISTRY", set()):
            with patch.object(
                eis.ExternalIntegrationService,
                "get_piece_details",
                AsyncMock(return_value={"x": 1}),
            ):
                with patch.object(
                    eis.ExternalIntegrationService,
                    "execute_integration_action",
                    AsyncMock(return_value={"data": "p"}),
                ):
                    res = await dispatch("svc", "act", {}, tenant_id="t1", db=db)
        assert res["ok"] is True and res["backend"] == PIECE

        # mcp route
        with patch.object(ireg, "DEFAULT_SERVICE_REGISTRY", set()):
            with patch.object(
                eis.ExternalIntegrationService,
                "get_piece_details",
                AsyncMock(return_value=None),
            ):
                with patch.object(
                    ms.mcp_service, "tools_cache", {"srv": [{"name": "svc_act"}]}
                ):
                    with patch.object(
                        ms.mcp_service,
                        "call_external_tool",
                        AsyncMock(return_value={"m": 1}),
                    ) as call:
                        res = await dispatch("svc", "act", {}, tenant_id="t1", db=db)
        assert res["ok"] is True and res["backend"] == MCP
        assert call.await_args.args == ("srv", "svc_act", {})

        # not found
        with patch.object(ireg, "DEFAULT_SERVICE_REGISTRY", set()):
            with patch.object(
                eis.ExternalIntegrationService,
                "get_piece_details",
                AsyncMock(return_value=None),
            ):
                with patch.object(ms.mcp_service, "tools_cache", {}):
                    res = await dispatch("svc", "act", {}, tenant_id="t1", db=db)
        assert res["ok"] is False and res["error"] == "not_found"

        # resolve_backend itself raises -> defensive wrap
        with patch.object(
            disp, "resolve_backend", AsyncMock(side_effect=RuntimeError("kaboom"))
        ):
            res = await dispatch("svc", "act", {}, tenant_id="t1", db=db)
        assert res["ok"] is False and res["error"] == "failed"
