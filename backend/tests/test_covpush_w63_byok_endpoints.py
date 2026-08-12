"""Coverage wave 63 — core/byok_endpoints.py (93% → 95%+).

Closes the remaining holes: AIProviderConfig __post_init__ defaults,
keys-file last_used deserialization + corrupt keys file, atomic-write
unlink failure, encryption key read/write failures, inactive-provider
filter + OpenAI fallback in optimal-provider, provider-list exception
tolerance, store-key 400/500 branches, usage-track 500, PDF-optimize
scenario exceptions, health active/with-keys counters, v1 health/status
direct calls, pricing refresh/model/provider/estimate error paths.
"""
import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.byok_endpoints as be
from core.byok_endpoints import (
    AIProviderConfig,
    APIKey,
    BYOKManager,
    AddAPIKeyRequest,
    ProviderUsage,
    get_byok_manager,
    byok_health_v1,
    byok_status_v1,
    get_ai_pricing,
    get_model_pricing,
    get_provider_pricing,
    refresh_ai_pricing,
    estimate_request_cost,
    store_api_key,
    track_ai_usage,
)


@pytest.fixture
def paths(tmp_path):
    cfg = str(tmp_path / "config.json")
    keys = str(tmp_path / "keys.json")
    enc = str(tmp_path / "enc.key")
    with patch.object(be, "BYOK_CONFIG_FILE", cfg), \
         patch.object(be, "BYOK_KEYS_FILE", keys), \
         patch.object(be, "BYOK_ENC_KEY_FILE", enc), \
         patch.dict(os.environ, {}, clear=True):
        yield cfg, keys, enc


@pytest.fixture
def manager(paths):
    return BYOKManager()


class TestDataClassDefaults:
    def test_provider_default_supported_tasks(self):
        p = AIProviderConfig(id="x", name="X", description="d",
                             api_key_env_var="X_KEY")
        assert p.supported_tasks == []
        assert p.cost_per_token == 0.0
        assert p.is_active is True

    def test_usage_tracking_defaults(self):
        u = ProviderUsage(provider_id="x")
        assert u.total_requests == 0
        assert u.cost_accumulated == 0.0


class TestConfigLoadEdges:
    def test_load_keys_with_last_used(self, paths):
        cfg, keys, enc = paths
        with open(cfg, "w") as f:
            json.dump({"providers": []}, f)
        with open(keys, "w") as f:
            json.dump({"keys": {"deepseek_default_production": {
                "provider_id": "deepseek", "key_name": "default",
                "encrypted_key": "abc", "key_hash": "h",
                "created_at": "2026-08-01T00:00:00",
                "last_used": "2026-08-02T12:00:00",
                "environment": "production",
            }}}, f)
        m = BYOKManager()
        k = m.api_keys["deepseek_default_production"]
        assert k.last_used == datetime(2026, 8, 2, 12, 0, 0)

    def test_load_corrupt_keys_tolerated(self, paths):
        cfg, keys, enc = paths
        with open(keys, "w") as f:
            f.write("{not json")
        m = BYOKManager()  # must not raise
        assert m.api_keys == {}

    def test_atomic_write_unlink_failure(self, manager, paths):
        with patch("os.replace", side_effect=OSError("boom")), \
             patch("os.unlink", side_effect=OSError("gone")):
            with pytest.raises(OSError):
                manager._atomic_write_json(str(paths[0]), {})


class TestEncryptionKeyEdges:
    def test_load_key_file_read_failure(self, manager, paths):
        enc = paths[2]
        with open(enc, "w") as f:
            f.write("persisted-key-123")
        with patch("builtins.open", side_effect=OSError("permission denied")):
            key = manager._load_or_create_encryption_key()
        assert key  # regenerated fallback still returned

    def test_persist_key_failure_tolerated(self, manager, paths):
        with patch("os.makedirs", side_effect=OSError("no space")):
            key = manager._load_or_create_encryption_key()
        assert key


class TestOptimalProviderEdges:
    def _provider_with_key(self, manager, pid, cost, tasks, reasoning=1,
                           active=True):
        manager.providers[pid] = AIProviderConfig(
            id=pid, name=pid, description="d", api_key_env_var=f"{pid.upper()}_KEY",
            base_url="https://x", supported_tasks=tasks, cost_per_token=cost,
            model="m", reasoning_level=reasoning, is_active=active)
        manager.store_api_key(pid, f"sk-{pid}")

    def test_inactive_provider_skipped(self, manager):
        self._provider_with_key(manager, "dead", 0.001, ["chat"], active=False)
        assert manager.get_optimal_provider("chat") is None

    def test_fallback_openai_when_no_deepseek(self, manager):
        self._provider_with_key(manager, "openai", 0.01, ["code"])
        assert manager.get_optimal_provider("weird_task") == "openai"

    def test_optimal_provider_all_filtered_returns_none(self, manager):
        self._provider_with_key(manager, "low", 0.01, ["chat"], reasoning=1)
        self._provider_with_key(manager, "mid", 0.02, ["chat"], reasoning=2)
        # min_reasoning_level 3: no suitable -> no deepseek/openai keys -> None
        assert manager.get_optimal_provider("chat", min_reasoning_level=3) is None


class TestRouteEdges:
    def _client(self, manager):
        app = FastAPI()
        app.include_router(be.router)
        app.dependency_overrides[be.get_byok_manager] = lambda: manager
        return TestClient(app)

    def test_providers_list_tolerates_errors(self, manager):
        manager.providers["broken"] = AIProviderConfig(
            id="broken", name="B", description="d",
            api_key_env_var="B_KEY", supported_tasks=["chat"])
        manager.providers["ok"] = AIProviderConfig(
            id="ok", name="O", description="d", api_key_env_var="O_KEY",
            supported_tasks=["chat"])
        with patch.object(manager, "get_provider_status",
                          side_effect=RuntimeError("boom")):
            resp = self._client(manager).get("/api/ai/providers")
        assert resp.status_code == 200
        assert resp.json()["total_providers"] == 0

    def test_store_key_too_short_400(self, manager):
        request = AddAPIKeyRequest.model_construct(api_key="short", key_name="x")
        with pytest.raises(Exception) as exc:
            import asyncio
            asyncio.run(store_api_key(
                "openai", request, Mock(), byok_manager=manager))
        assert exc.value.status_code == 400

    def test_store_key_generic_500(self, manager):
        with patch.object(manager, "store_api_key",
                          side_effect=RuntimeError("boom")):
            resp = self._client(manager).post(
                "/api/ai/providers/openai/keys",
                json={"api_key": "sk-1234567890"})
        assert resp.status_code == 500

    def test_track_usage_background_failure_500(self, manager):
        bt = Mock()
        bt.add_task.side_effect = RuntimeError("boom")
        with pytest.raises(Exception) as exc:
            import asyncio
            asyncio.run(track_ai_usage(
                {"provider_id": "deepseek"}, bt, byok_manager=manager))
        assert exc.value.status_code == 500

    def test_ai_health_counts_active_and_keys(self, manager):
        manager.store_api_key("deepseek", "sk-1234567890")
        resp = self._client(manager).get("/api/ai/health")
        body = resp.json()
        assert body["providers"]["active"] == 1
        assert body["providers"]["with_keys"] == 1
        assert body["usage"]["total_requests"] == 0

    def test_v1_health_direct_call(self, manager):
        resp = asyncio_run(byok_health_v1(manager))
        assert resp["status"] == "healthy"

    def test_v1_status_tolerates_provider_errors(self, manager):
        manager.providers["broken"] = AIProviderConfig(
            id="broken", name="B", description="d",
            api_key_env_var="B_KEY", supported_tasks=["chat"])

        counter = {"n": 0}

        def _raise_on_second_loop(pid):
            counter["n"] += 1
            # first loop (health check) must pass for all providers; the
            # per-provider status loop in byok_status_v1 runs after it
            if pid == "broken" and counter["n"] > len(manager.providers):
                raise RuntimeError("boom")
            return be.BYOKManager.get_provider_status(manager, pid)

        with patch.object(manager, "get_provider_status",
                          side_effect=_raise_on_second_loop):
            resp = asyncio_run(byok_status_v1(manager))
        assert resp["status_code"] == 200
        assert all(p["id"] != "broken" for p in resp["providers_list"])

    def test_pdf_optimize_scenario_exceptions(self, manager):
        manager.store_api_key("deepseek", "sk-1234567890")
        # optimal succeeds on first call; both scenario calls raise
        with patch.object(manager, "get_optimal_provider",
                          side_effect=["deepseek", RuntimeError("hq"),
                                       RuntimeError("ce")]):
            resp = self._client(manager).post("/api/ai/pdf/optimize",
                                              json={"needs_ocr": True})
        assert resp.status_code == 200
        assert resp.json()["alternative_scenarios"] == {}


def asyncio_run(coro):
    import asyncio
    return asyncio.new_event_loop().run_until_complete(coro)


class TestPricingErrorPaths:
    def test_pricing_refresh_failure(self, manager):
        with patch("core.dynamic_pricing_fetcher.refresh_pricing_cache",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = asyncio_run(refresh_ai_pricing(byok_manager=manager))
        assert resp["status"] == "error"

    def test_model_pricing_failure(self):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            resp = asyncio_run(get_model_pricing("gpt-4o"))
        assert resp["status"] == "error"

    def test_provider_pricing_failure(self):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            resp = asyncio_run(get_provider_pricing("openai"))
        assert resp["status"] == "error"

    def test_estimate_cost_failure(self):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            resp = asyncio_run(estimate_request_cost({"model": "gpt-4o"}))
        assert resp["status"] == "error"

    def test_estimate_cost_prompt_estimates_tokens(self):
        fetcher = Mock()
        fetcher.estimate_cost.return_value = None
        fetcher.get_model_price.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = asyncio_run(estimate_request_cost(
                {"model": "m", "prompt": "abcdefghijkl"}))
        assert resp["status"] == "pricing_unavailable"


class TestMaskingAndStatus:
    def test_masked_key_without_hash(self, manager, paths):
        manager.api_keys["deepseek_default_production"] = APIKey(
            provider_id="deepseek", key_name="default", encrypted_key="enc",
            key_hash="", created_at=datetime.now(), environment="production")
        app = FastAPI()
        app.include_router(be.router)
        app.dependency_overrides[be.get_byok_manager] = lambda: manager
        resp = TestClient(app).get("/api/ai/keys")
        assert resp.json()["keys"][0]["masked_key"] == "****"


class TestStoreKeyWhitelistDrift:
    """Every default provider must be keyable via the secure route.

    The route's valid_providers whitelist drifted from the default provider
    list: providers added later (xai, cerebras, fireworks, huggingface,
    nvidia_nim, zai, ollama) exist in BYOKManager.providers but were
    rejected with 400 before the manager could store them.
    """

    @pytest.mark.parametrize("pid", [
        "xai", "cerebras", "fireworks", "huggingface",
        "nvidia_nim", "zai", "ollama", "openrouter", "moonshot",
    ])
    def test_newer_default_providers_accept_keys(self, manager, pid):
        app = FastAPI()
        app.include_router(be.router)
        app.dependency_overrides[be.get_byok_manager] = lambda: manager
        resp = TestClient(app).post(
            f"/api/ai/providers/{pid}/keys",
            json={"api_key": "sk-1234567890", "key_name": "work"})
        assert resp.status_code == 200, \
            f"provider {pid} rejected: {resp.text}"
        assert resp.json()["key_id"] == f"{pid}_work_production"
