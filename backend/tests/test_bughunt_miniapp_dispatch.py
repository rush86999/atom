"""TDD bug-hunt: mini-app integration dispatch native path (R80 follow-up).

``execute_native`` in ``core/mini_app_integration_dispatch.py`` calls
``instance.execute_operation(...)`` without ``await`` — every native
integration's ``execute_operation`` is async, so the native dispatch path
returned a coroutine as ``data`` and mini-app integration pre-fetch silently
broke (RuntimeWarning: coroutine ... was never awaited).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_async_service():
    class FakeService:
        def __init__(self, *args, **kwargs):
            pass

        async def execute_operation(self, action, params, context=None):
            return {"pages": 1}

    return FakeService


@pytest.mark.asyncio
async def test_execute_native_awaits_async_operation(fake_async_service, monkeypatch):
    from core import mini_app_integration_dispatch as dispatch_mod

    registry = MagicMock()
    registry.get_service_class.return_value = fake_async_service
    monkeypatch.setattr("core.integration_registry.IntegrationRegistry", lambda: registry)
    monkeypatch.setattr(
        dispatch_mod, "_load_token_row", lambda tenant_id, service, db: None
    )

    result = await dispatch_mod.execute_native(
        "notion", "search", {"q": 1}, tenant_id="t1", db=None
    )

    assert result.get("ok") is True
    assert result.get("data") == {"pages": 1}
    assert not hasattr(result.get("data"), "__await__"), (
        "execute_native must await execute_operation; got a coroutine"
    )


@pytest.mark.asyncio
async def test_dispatch_native_backend_resolves_data(fake_async_service, monkeypatch):
    from core import mini_app_integration_dispatch as dispatch_mod

    registry = MagicMock()
    registry.get_service_class.return_value = fake_async_service
    monkeypatch.setattr("core.integration_registry.IntegrationRegistry", lambda: registry)
    monkeypatch.setattr(
        dispatch_mod, "_load_token_row", lambda tenant_id, service, db: None
    )
    async def fake_resolve(service, action, tenant_id=None, db=None):
        return ("native", None)

    monkeypatch.setattr(dispatch_mod, "resolve_backend", fake_resolve)

    result = await dispatch_mod.dispatch("notion", "search", {"q": 1}, tenant_id="t1", db=None)

    assert result.get("ok") is True
    assert result.get("data") == {"pages": 1}


@pytest.mark.asyncio
async def test_execute_native_exception_returns_fail_closed(fake_async_service, monkeypatch):
    from core import mini_app_integration_dispatch as dispatch_mod

    class ExplodingService:
        def __init__(self, *args, **kwargs):
            pass

        async def execute_operation(self, action, params, context=None):
            raise RuntimeError("boom")

    registry = MagicMock()
    registry.get_service_class.return_value = ExplodingService
    monkeypatch.setattr("core.integration_registry.IntegrationRegistry", lambda: registry)
    monkeypatch.setattr(
        dispatch_mod, "_load_token_row", lambda tenant_id, service, db: None
    )

    result = await dispatch_mod.execute_native("notion", "search", {}, tenant_id="t1", db=None)

    assert result.get("ok") is False
    assert "error" in result
