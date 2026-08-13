# -*- coding: utf-8 -*-
"""Coverage wave 91 — core/integration_registry_v2 (IntegrationRegistryV2).

Fully mocked: importlib.import_module for adapter loading, node_bridge for the
Pieces fallback, fake native services for execute_operation. Zero LLM spend,
no network, no real DB.

- get_service: cache hit, dynamic load via module_path:class_name, unknown
  connector → None, ImportError/AttributeError → None, unexpected exception
  → None, workspace_id default "default".
- _map_to_piece_auth: access_token (OAUTH2), api_key (SECRET_TEXT), plain
  config passthrough, None config.
- execute_operation: native success / native exception → EXECUTION_EXCEPTION,
  no native → Pieces details None → NOT_FOUND, Pieces success, Pieces
  exception → EXECUTION_EXCEPTION.
"""
import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.integration_registry_v2 import IntegrationRegistryV2, registry
from core.integration_service import IntegrationErrorCode, OperationResult


class _FakeAdapter:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.instances = []

    async def execute_operation(self, operation, parameters, context):
        self.instances.append((operation, parameters, context))
        return OperationResult(success=True, data={"echo": operation})


def _fake_module():
    return MagicMock(AsanaAdapter=_FakeAdapter)
# ============================================================================
# get_service
# ============================================================================

class _Module:
    """importlib stand-in: any requested class name resolves to _FakeAdapter."""

    def __getattr__(self, name):
        return _FakeAdapter


def test_get_service_dynamic_load_and_cache(monkeypatch):
    load = MagicMock(side_effect=lambda name: _Module())
    monkeypatch.setattr(importlib, "import_module", load)
    reg = IntegrationRegistryV2(workspace_id="ws-9")
    svc = reg.get_service("asana", {"api_key": "k"})
    assert isinstance(svc, _FakeAdapter)
    assert svc.kwargs == {"tenant_id": "ws-9", "config": {"api_key": "k"}}
    assert reg.get_service("asana") is svc  # cached singleton
    assert reg._service_cache["asana"] is svc
    assert load.call_count == 1


def test_get_service_default_workspace(monkeypatch):
    monkeypatch.setattr(importlib, "import_module", lambda name: _Module())
    reg = IntegrationRegistryV2()
    assert reg.workspace_id == "default"
    svc = reg.get_service("notion", {})
    assert svc.kwargs["tenant_id"] == "default"


def test_get_service_unknown_connector():
    reg = IntegrationRegistryV2()
    assert reg.get_service("salesforce") is None


def test_get_service_import_errors(monkeypatch):
    reg = IntegrationRegistryV2()

    def _boom(name):
        raise ImportError(f"no module {name}")

    monkeypatch.setattr(importlib, "import_module", _boom)
    assert reg.get_service("asana") is None

    class _NoAttrModule:
        pass

    monkeypatch.setattr(
        importlib, "import_module", lambda name: _NoAttrModule()
    )
    assert reg.get_service("asana") is None  # AttributeError → None


def test_get_service_unexpected_exception(monkeypatch):
    reg = IntegrationRegistryV2()

    class _BadCtor:
        def __init__(self, **kwargs):
            raise RuntimeError("ctor boom")

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: MagicMock(HubSpotAdapter=_BadCtor),
    )
    assert reg.get_service("hubspot") is None


# ============================================================================
# _map_to_piece_auth
# ============================================================================

def test_map_to_piece_auth_oauth2():
    reg = IntegrationRegistryV2()
    out = reg._map_to_piece_auth("x", {
        "access_token": "at",
        "refresh_token": "rt",
        "client_id": "cid",
        "client_secret": "cs",
    })
    assert out == {
        "type": "OAUTH2",
        "data": {"access_token": "at", "refresh_token": "rt",
                 "client_id": "cid", "client_secret": "cs"},
    }


def test_map_to_piece_auth_secret_text():
    reg = IntegrationRegistryV2()
    out = reg._map_to_piece_auth("x", {"api_key": "sk-1"})
    assert out == {"type": "SECRET_TEXT", "secret": "sk-1"}


def test_map_to_piece_auth_passthrough_and_none():
    reg = IntegrationRegistryV2()
    out = reg._map_to_piece_auth("x", {"region": "eu"})
    assert out == {"region": "eu"}
    assert reg._map_to_piece_auth("x", {}) is None
    assert reg._map_to_piece_auth("x", None) is None


# ============================================================================
# execute_operation
# ============================================================================

@pytest.fixture()
def reg():
    return IntegrationRegistryV2(workspace_id="ws-1")


def test_execute_operation_native_success(monkeypatch, reg):
    import asyncio

    adapter = _FakeAdapter()
    monkeypatch.setattr(reg, "get_service", lambda c, config=None: adapter)
    result = OperationResult(success=True, data={"ok": True})

    async def _run(o, p, c):
        adapter.instances.append((o, p, c))
        return result

    adapter.execute_operation = _run
    out = asyncio.get_event_loop().run_until_complete(
        reg.execute_operation("asana", "create_task", {"name": "x"}, config={"api_key": "k"})
    )
    assert out is result
    assert adapter.instances == [("create_task", {"name": "x"}, None)]


def test_execute_operation_native_exception(monkeypatch, reg):
    adapter = _FakeAdapter()

    async def _boom(o, p, c):
        raise RuntimeError("native down")

    adapter.execute_operation = _boom
    monkeypatch.setattr(reg, "get_service", lambda c, config=None: adapter)
    import asyncio

    out = asyncio.get_event_loop().run_until_complete(
        reg.execute_operation("asana", "op", {})
    )
    assert out.success is False
    assert out.error == IntegrationErrorCode.EXECUTION_EXCEPTION
    assert out.message == "native down"


def test_execute_operation_pieces_fallback_success(monkeypatch, reg):
    import core.integration_registry_v2 as mod

    bridge = MagicMock()
    bridge.get_piece_details = AsyncMock(return_value={"name": "slack"})
    bridge.execute_action = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(mod, "node_bridge", bridge)
    import asyncio

    out = asyncio.get_event_loop().run_until_complete(
        reg.execute_operation("custom_connector", "post_message", {"text": "hi"},
                              config={"api_key": "sk"})
    )
    assert out.success is True
    assert out.data == {"ok": True}
    bridge.get_piece_details.assert_awaited_once_with("custom_connector")
    bridge.execute_action.assert_awaited_once_with(
        piece_name="custom_connector", action_name="post_message",
        props={"text": "hi"}, auth={"type": "SECRET_TEXT", "secret": "sk"},
    )


def test_execute_operation_pieces_not_found(monkeypatch, reg):
    import core.integration_registry_v2 as mod

    bridge = MagicMock()
    bridge.get_piece_details = AsyncMock(return_value=None)
    monkeypatch.setattr(mod, "node_bridge", bridge)
    import asyncio

    out = asyncio.get_event_loop().run_until_complete(
        reg.execute_operation("unknown_connector", "op", {})
    )
    assert out.success is False
    assert out.error == IntegrationErrorCode.NOT_FOUND


def test_execute_operation_pieces_exception(monkeypatch, reg):
    import core.integration_registry_v2 as mod

    bridge = MagicMock()
    bridge.get_piece_details = AsyncMock(
        side_effect=RuntimeError("pieces down")
    )
    monkeypatch.setattr(mod, "node_bridge", bridge)
    import asyncio

    out = asyncio.get_event_loop().run_until_complete(
        reg.execute_operation("custom_connector", "op", {})
    )
    assert out.success is False
    assert out.error == IntegrationErrorCode.EXECUTION_EXCEPTION
    assert out.message == "pieces down"


def test_registry_singleton():
    assert registry.workspace_id == "default"
    assert isinstance(registry, IntegrationRegistryV2)
