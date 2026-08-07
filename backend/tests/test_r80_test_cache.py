"""Round 80 — RegistryCacheService coverage.

``core/llm/registry/test_cache.py`` lives INSIDE the package, so pytest
(``testpaths = tests``) never collects it and the RegistryCacheService
implementation in ``core/llm/registry/cache.py`` has zero CI coverage.
This module moves that coverage into the discoverable suite: key shapes,
CRUD, TTLs, tenant invalidation, warm-cache, and the atomic-swap lock
lifecycle (acquire → release in ``finally``, held-lock rejection, and
graceful degradation when model writes fail).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from core.llm.registry.cache import (
    CACHE_TTL,
    LIST_KEY_PREFIX,
    LOCK_TTL,
    MODEL_KEY_PREFIX,
    SWAP_LOCK_KEY,
    RegistryCacheService,
)

TENANT = "r80-tenant"


def _model(provider="openai", name="gpt-4", ctx=8192):
    return {"provider": provider, "model_name": name, "context_window": ctx}


class TestKeyShapes:
    def test_model_key(self):
        svc = RegistryCacheService()
        assert svc._model_key(TENANT, "openai", "gpt-4") == f"{MODEL_KEY_PREFIX}:openai:gpt-4"

    def test_list_key_no_provider(self):
        svc = RegistryCacheService()
        assert svc._list_key(TENANT) == LIST_KEY_PREFIX

    def test_list_key_with_provider(self):
        svc = RegistryCacheService()
        assert svc._list_key(TENANT, "openai") == f"{LIST_KEY_PREFIX}:openai"


class TestModelCrud:
    async def test_set_model_uses_cache_ttl(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "set_async", new_callable=AsyncMock, return_value=True) as mock_set:
            ok = await svc.set_model(TENANT, "openai", "gpt-4", _model())
            assert ok is True
            key, value, ttl = mock_set.call_args[0]
            assert key == f"{MODEL_KEY_PREFIX}:openai:gpt-4"
            assert value["model_name"] == "gpt-4"
            assert ttl == CACHE_TTL

    async def test_get_model_hit_and_miss(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "get_async", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _model()
            assert (await svc.get_model(TENANT, "openai", "gpt-4"))["context_window"] == 8192
            mock_get.return_value = None
            assert await svc.get_model(TENANT, "openai", "gpt-4") is None

    async def test_set_model_cache_error_returns_false(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "set_async", new_callable=AsyncMock, side_effect=Exception("redis down")):
            assert await svc.set_model(TENANT, "openai", "gpt-4", _model()) is False

    async def test_get_model_cache_error_returns_none(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "get_async", new_callable=AsyncMock, side_effect=Exception("redis down")):
            assert await svc.get_model(TENANT, "openai", "gpt-4") is None

    async def test_set_get_models_list(self):
        svc = RegistryCacheService()
        models = [_model(), _model("anthropic", "claude-3-opus")]
        with patch.object(svc.cache, "set_async", new_callable=AsyncMock, return_value=True) as mock_set, \
             patch.object(svc.cache, "get_async", new_callable=AsyncMock) as mock_get:
            assert await svc.set_models_list(TENANT, models) is True
            assert mock_set.call_args[0][0] == LIST_KEY_PREFIX
            assert mock_set.call_args[0][2] == CACHE_TTL
            mock_get.return_value = models
            assert await svc.get_models_list(TENANT) == models
            mock_get.return_value = None
            assert await svc.get_models_list(TENANT) is None


class TestDeleteModel:
    async def test_delete_model_invalidates_list_caches(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "delete_async", new_callable=AsyncMock) as mock_delete:
            assert await svc.delete_model(TENANT, "openai", "gpt-4") is True
            keys = [c.args[0] for c in mock_delete.call_args_list]
            assert keys == [
                f"{MODEL_KEY_PREFIX}:openai:gpt-4",
                LIST_KEY_PREFIX,
                f"{LIST_KEY_PREFIX}:openai",
            ]

    async def test_delete_model_error_returns_false(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "delete_async", new_callable=AsyncMock, side_effect=Exception("redis down")):
            assert await svc.delete_model(TENANT, "openai", "gpt-4") is False


class TestInvalidateTenant:
    async def test_passes_through_delete_tenant_all(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "delete_tenant_all", new_callable=AsyncMock, return_value=7) as mock_del:
            assert await svc.invalidate_tenant(TENANT) == 7
            mock_del.assert_awaited_once_with(TENANT)

    async def test_error_returns_zero(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "delete_tenant_all", new_callable=AsyncMock, side_effect=Exception("redis down")):
            assert await svc.invalidate_tenant(TENANT) == 0


class TestWarmCache:
    async def test_no_lock_and_writes_models_and_lists(self):
        svc = RegistryCacheService()
        models = [_model(), _model("anthropic", "claude-3-opus", 200000)]
        with patch.object(svc.cache, "set_async", new_callable=AsyncMock, return_value=True) as mock_set, \
             patch.object(svc.cache, "get_async", new_callable=AsyncMock) as mock_get, \
             patch.object(svc.cache, "delete_async", new_callable=AsyncMock) as mock_delete:
            result = await svc.warm_cache(TENANT, models)
            assert result is None
            # 2 model keys + 1 all-list + 2 provider lists
            assert mock_set.call_count == 5
            keys = [c.args[0] for c in mock_set.call_args_list]
            assert f"{MODEL_KEY_PREFIX}:openai:gpt-4" in keys
            assert f"{MODEL_KEY_PREFIX}:anthropic:claude-3-opus" in keys
            assert keys.count(LIST_KEY_PREFIX) == 1
            assert f"{LIST_KEY_PREFIX}:anthropic" in keys
            # warm_cache must never touch the lock.
            assert mock_get.await_count == 0
            assert mock_delete.await_count == 0
            assert not any(SWAP_LOCK_KEY in k for k in keys)


class TestAtomicSwap:
    async def test_acquires_lock_and_releases_in_finally(self):
        svc = RegistryCacheService()
        models = [_model(), _model("anthropic", "claude-3-opus")]
        with patch.object(svc.cache, "get_async", new_callable=AsyncMock, return_value=None) as mock_get, \
             patch.object(svc.cache, "set_async", new_callable=AsyncMock, return_value=True) as mock_set, \
             patch.object(svc.cache, "delete_async", new_callable=AsyncMock) as mock_delete:
            assert await svc.atomic_swap_registry(TENANT, models) is True

            lock_key = f"{TENANT}:{SWAP_LOCK_KEY}"
            lock_set = next(c for c in mock_set.call_args_list if c.args[0] == lock_key)
            assert lock_set.args[1] == "swapping"
            assert lock_set.args[2] == LOCK_TTL
            assert mock_delete.await_count == 1
            assert mock_delete.call_args[0][0] == lock_key

            # Model + list writes all happened.
            keys = [c.args[0] for c in mock_set.call_args_list]
            assert f"{MODEL_KEY_PREFIX}:openai:gpt-4" in keys
            assert f"{MODEL_KEY_PREFIX}:anthropic:claude-3-opus" in keys
            assert keys.count(LIST_KEY_PREFIX) == 1
            assert f"{LIST_KEY_PREFIX}:anthropic" in keys
            assert f"{LIST_KEY_PREFIX}:openai" in keys

    async def test_held_lock_rejects_second_swap(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "get_async", new_callable=AsyncMock, return_value="swapping"):
            with pytest.raises(Exception, match="Swap in progress"):
                await svc.atomic_swap_registry(TENANT, [_model()])

    async def test_lock_set_failure_propagates_and_no_writes(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "get_async", new_callable=AsyncMock, return_value=None), \
             patch.object(svc.cache, "set_async", new_callable=AsyncMock, side_effect=Exception("redis down")), \
             patch.object(svc.cache, "delete_async", new_callable=AsyncMock) as mock_delete:
            with pytest.raises(Exception):
                await svc.atomic_swap_registry(TENANT, [_model()])
            # Nothing was written; nothing to release (lock set itself failed).
            assert mock_delete.await_count == 0

    async def test_model_write_failure_degrades_but_releases_lock(self):
        """set_model swallows cache errors (returns False), so the swap
        completes and — critically — the lock is still released."""
        svc = RegistryCacheService()

        async def fail_after_lock(key, value, ttl=None, tenant=None):
            if SWAP_LOCK_KEY not in key:
                raise Exception("redis down")
            return True

        with patch.object(svc.cache, "get_async", new_callable=AsyncMock, return_value=None), \
             patch.object(svc.cache, "set_async", side_effect=fail_after_lock), \
             patch.object(svc.cache, "delete_async", new_callable=AsyncMock) as mock_delete:
            assert await svc.atomic_swap_registry(TENANT, [_model()]) is True
            assert mock_delete.await_count == 1
            assert mock_delete.call_args[0][0] == f"{TENANT}:{SWAP_LOCK_KEY}"

    async def test_grouped_by_provider_lists(self):
        svc = RegistryCacheService()
        models = [
            _model("openai", "gpt-4"),
            _model("openai", "gpt-4-turbo"),
            _model("anthropic", "claude-3-opus"),
        ]
        with patch.object(svc.cache, "get_async", new_callable=AsyncMock, return_value=None), \
             patch.object(svc.cache, "set_async", new_callable=AsyncMock, return_value=True) as mock_set, \
             patch.object(svc.cache, "delete_async", new_callable=AsyncMock):
            await svc.atomic_swap_registry(TENANT, models)
            provider_lists = {c.args[0]: c.args[1] for c in mock_set.call_args_list}
            assert len(provider_lists[f"{LIST_KEY_PREFIX}:openai"]) == 2
            assert len(provider_lists[f"{LIST_KEY_PREFIX}:anthropic"]) == 1
            assert len(provider_lists[LIST_KEY_PREFIX]) == 3

    async def test_missing_provider_defaults_to_unknown(self):
        svc = RegistryCacheService()
        with patch.object(svc.cache, "get_async", new_callable=AsyncMock, return_value=None), \
             patch.object(svc.cache, "set_async", new_callable=AsyncMock, return_value=True) as mock_set, \
             patch.object(svc.cache, "delete_async", new_callable=AsyncMock):
            await svc.atomic_swap_registry(TENANT, [{"model_name": "no-provider"}])
            keys = [c.args[0] for c in mock_set.call_args_list]
            assert f"{MODEL_KEY_PREFIX}:unknown:no-provider" in keys
