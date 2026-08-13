# -*- coding: utf-8 -*-
"""Coverage wave 84 — core/integration_registry_v2 (standalone; importlib and
node_bridge fully mocked, OperationResult from core.integration_service).

- ctor: workspace_id override + default.
- get_service: cached singleton reuse, unknown connector → None, import
  error → None, missing class attr → None, instantiation raise → None,
  success (ctor receives tenant_id=workspace_id + config), per-connector
  cache keyed by connector_id.
- _map_to_piece_auth: access_token → OAUTH2 mapping, api_key → SECRET_TEXT,
  neither → config passthrough, empty config → None.
- execute_operation: native success, native raise → EXECUTION_EXCEPTION,
  missing native → Pieces fallback (no details → NOT_FOUND), Pieces success
  (auth mapping passed), Pieces raise → EXECUTION_EXCEPTION.
- module-level `registry` singleton.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.integration_registry_v2 as mod
from core.integration_registry_v2 import IntegrationRegistryV2, UPSTREAM_SERVICE_REGISTRY
from core.integration_service import IntegrationErrorCode, OperationResult


@pytest.fixture()
def registry():
    return IntegrationRegistryV2(workspace_id="ws-1")


class _FakeService:
    def __init__(self, tenant_id=None, config=None, *, execute_result=None, raise_on_execute=False):
        self.tenant_id = tenant_id
        self.config = config
        self.execute_result = execute_result
        self.raise_on_execute = raise_on_execute

    async def execute_operation(self, operation, parameters, context):
        if self.raise_on_execute:
            raise RuntimeError("boom")
        return self.execute_result


class _NoAttr:
    def __getattr__(self, name):
        raise AttributeError(name)


def _patch_import(registry, service_class=None, exc=None, attr_exc=None):
    if attr_exc is not None:
        module = _NoAttr()
    elif service_class is not None:
        module = type("FakeModule", (), {})()
        for _cid, _path in UPSTREAM_SERVICE_REGISTRY.items():
            setattr(module, _path.split(":")[1], service_class)
    else:
        module = MagicMock()
    return patch("core.integration_registry_v2.importlib.import_module",
                 side_effect=exc if exc else lambda path: module)


# ============================================================================
# ctor
# ============================================================================

class TestInit:
    def test_default_workspace(self):
        assert IntegrationRegistryV2().workspace_id == "default"

    def test_explicit_workspace(self):
        assert IntegrationRegistryV2(workspace_id="custom").workspace_id == "custom"

    def test_empty_service_cache(self):
        assert IntegrationRegistryV2()._service_cache == {}


# ============================================================================
# get_service
# ============================================================================

class TestGetService:
    def test_success_instantiates_with_workspace(self):
        registry = IntegrationRegistryV2(workspace_id="ws-9")
        captured = {}
        def factory(tenant_id=None, config=None):
            captured["tenant_id"] = tenant_id
            captured["config"] = config
            return _FakeService()
        with _patch_import(registry, service_class=factory):
            service = registry.get_service("asana", config={"key": "v"})
        assert service is not None
        assert captured == {"tenant_id": "ws-9", "config": {"key": "v"}}

    def test_unknown_connector_returns_none(self, registry):
        assert registry.get_service("no_such_connector") is None

    def test_caches_instance(self, registry):
        with _patch_import(registry, service_class=_FakeService):
            first = registry.get_service("asana")
            second = registry.get_service("asana")
        assert first is second

    def test_import_error_returns_none(self, registry):
        with _patch_import(registry, exc=ImportError("no module")):
            assert registry.get_service("asana") is None

    def test_attribute_error_returns_none(self, registry):
        with _patch_import(registry, attr_exc=AttributeError("no attr")):
            assert registry.get_service("asana") is None

    def test_instantiation_error_returns_none(self, registry):
        def bad_factory(**kwargs):
            raise RuntimeError("ctor fail")
        with _patch_import(registry, service_class=bad_factory):
            assert registry.get_service("asana") is None

    def test_cache_separate_per_connector(self, registry):
        with _patch_import(registry, service_class=_FakeService):
            asana = registry.get_service("asana")
            notion = registry.get_service("notion")
        assert asana is not None and notion is not None
        assert asana is not notion
        assert len(registry._service_cache) == 2


# ============================================================================
# _map_to_piece_auth
# ============================================================================

class TestMapToPieceAuth:
    def test_access_token_oauth2(self, registry):
        auth = registry._map_to_piece_auth("slack", {
            "access_token": "tok", "refresh_token": "ref",
            "client_id": "cid", "client_secret": "sec"})
        assert auth == {
            "type": "OAUTH2",
            "data": {"access_token": "tok", "refresh_token": "ref",
                     "client_id": "cid", "client_secret": "sec"},
        }

    def test_access_token_missing_optional_fields(self, registry):
        auth = registry._map_to_piece_auth("slack", {"access_token": "tok"})
        assert auth["type"] == "OAUTH2"
        assert auth["data"]["refresh_token"] is None

    def test_api_key_secret_text(self, registry):
        auth = registry._map_to_piece_auth("openai", {"api_key": "sk-123"})
        assert auth == {"type": "SECRET_TEXT", "secret": "sk-123"}

    def test_access_token_wins_over_api_key(self, registry):
        auth = registry._map_to_piece_auth("x", {"access_token": "t", "api_key": "k"})
        assert auth["type"] == "OAUTH2"

    def test_no_credentials_returns_config(self, registry):
        config = {"foo": "bar"}
        assert registry._map_to_piece_auth("x", config) == config

    def test_empty_config_returns_none(self, registry):
        assert registry._map_to_piece_auth("x", {}) is None


# ============================================================================
# execute_operation
# ============================================================================

class TestExecuteOperation:
    async def test_native_success(self, registry):
        result = OperationResult(success=True, data={"ok": 1})
        with _patch_import(registry, service_class=lambda **kw: _FakeService(execute_result=result)):
            outcome = await registry.execute_operation("asana", "create_task", {"a": 1})
        assert outcome is result

    async def test_native_raise_returns_execution_exception(self, registry):
        with _patch_import(registry, service_class=lambda **kw: _FakeService(raise_on_execute=True)):
            outcome = await registry.execute_operation("asana", "create_task", {})
        assert outcome.success is False
        assert outcome.error == IntegrationErrorCode.EXECUTION_EXCEPTION
        assert outcome.message == "boom"

    async def test_pieces_fallback_no_details(self, registry):
        with patch.object(mod.node_bridge, "get_piece_details",
                          new=AsyncMock(return_value=None)) as get_details:
            outcome = await registry.execute_operation("unknown_conn", "op", {})
        get_details.assert_awaited_once_with("unknown_conn")
        assert outcome.success is False
        assert outcome.error == IntegrationErrorCode.NOT_FOUND
        assert "not found" in outcome.message

    async def test_pieces_fallback_success(self, registry):
        get_details = AsyncMock(return_value={"name": "x"})
        execute_action = AsyncMock(return_value={"result": 42})
        with patch.object(mod.node_bridge, "get_piece_details", new=get_details), \
                patch.object(mod.node_bridge, "execute_action", new=execute_action):
            outcome = await registry.execute_operation(
                "unknown_conn", "op", {"p": 1}, context={"c": 2},
                config={"access_token": "tok"})
        assert outcome.success is True
        assert outcome.data == {"result": 42}
        execute_action.assert_awaited_once_with(
            piece_name="unknown_conn", action_name="op", props={"p": 1},
            auth={"type": "OAUTH2", "data": {"access_token": "tok", "refresh_token": None,
                                             "client_id": None, "client_secret": None}})

    async def test_pieces_fallback_raise(self, registry):
        with patch.object(mod.node_bridge, "get_piece_details",
                          new=AsyncMock(side_effect=RuntimeError("bridge down"))):
            outcome = await registry.execute_operation("unknown_conn", "op", {})
        assert outcome.success is False
        assert outcome.error == IntegrationErrorCode.EXECUTION_EXCEPTION

    async def test_pieces_execute_action_raise(self, registry):
        get_details = AsyncMock(return_value={"name": "x"})
        execute_action = AsyncMock(side_effect=ValueError("bad op"))
        with patch.object(mod.node_bridge, "get_piece_details", new=get_details), \
                patch.object(mod.node_bridge, "execute_action", new=execute_action):
            outcome = await registry.execute_operation("unknown_conn", "op", {})
        assert outcome.success is False
        assert outcome.error == IntegrationErrorCode.EXECUTION_EXCEPTION


# ============================================================================
# module-level registry
# ============================================================================

class TestModuleRegistry:
    def test_singleton_exists(self):
        assert isinstance(mod.registry, IntegrationRegistryV2)

    def test_registry_contents(self):
        assert UPSTREAM_SERVICE_REGISTRY["asana"].endswith(":AsanaAdapter")
        assert "slack" in UPSTREAM_SERVICE_REGISTRY
        assert len(UPSTREAM_SERVICE_REGISTRY) == 4
