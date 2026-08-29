"""Coverage wave 53 — core/byok_endpoints.py BYOKManager (58% → 90%+).

Direct manager tests with temp config/key files + per-test fresh instances:
config load/save (valid/corrupt/missing, atomic write + cleanup), default
providers init, dynamic cost updates, encryption key lifecycle (env/generate/
persist/load), Fernet round-trips + empty-key failure, store/get key flows
(env fallback, usage bump, decrypt failure), usage tracking, optimal-provider
selection (filters/budget/reasoning/fallbacks), provider status, compatibility
aliases, key-part normalization, singleton.
"""
import json
import os
import tempfile
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

import core.byok_endpoints as be
from core.byok_endpoints import (
    AIProviderConfig,
    APIKey,
    BYOKManager,
    ProviderUsage,
    get_byok_manager,
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


class TestConfigLoadSave:
    def test_load_valid_config(self, paths):
        cfg, keys, enc = paths
        with open(cfg, "w") as f:
            json.dump({"providers": [{
                "id": "custom", "name": "C", "description": "d",
                "api_key_env_var": "C_KEY", "base_url": "https://x",
                "supported_tasks": ["chat"], "cost_per_token": 0.01,
                "model": "m", "reasoning_level": 1,
            }]}, f)
        with open(keys, "w") as f:
            json.dump({"keys": {"custom_default_production": {
                "provider_id": "custom", "key_name": "default",
                "encrypted_key": "abc", "key_hash": "h",
                "created_at": "2026-08-01T00:00:00",
                "environment": "production",
            }}}, f)
        m = BYOKManager()
        assert "custom" in m.providers
        assert "custom_default_production" in m.api_keys
        assert m.api_keys["custom_default_production"].created_at is not None

    def test_load_corrupt_config(self, paths):
        cfg, keys, enc = paths
        with open(cfg, "w") as f:
            f.write("{not json")
        m = BYOKManager()  # must not raise
        assert m.providers  # defaults still loaded

    def test_missing_files(self, paths):
        m = BYOKManager()
        assert "deepseek" in m.providers  # defaults

    def test_save_configuration_success(self, manager, paths):
        manager.providers["x"] = AIProviderConfig(
            id="x", name="X", description="d", api_key_env_var="X_KEY",
            base_url="https://x", supported_tasks=["chat"],
            cost_per_token=0.0, model="m", reasoning_level=1)
        manager._save_configuration()
        cfg, keys, enc = paths
        assert os.path.exists(cfg)
        assert os.path.exists(keys)

    def test_save_failure_tolerated(self, manager):
        with patch.object(be.BYOKManager, "_atomic_write_json",
                          side_effect=OSError("disk full")):
            manager._save_configuration()  # must not raise

    def test_atomic_write_cleanup_on_failure(self, manager, paths):
        with patch("os.replace", side_effect=OSError("boom")), \
             patch("os.unlink") as unlink:
            with pytest.raises(OSError):
                manager._atomic_write_json(str(paths[0]), {})
        unlink.assert_called_once()


class TestDefaultsAndCosts:
    def test_default_providers_populated(self, manager):
        assert len(manager.providers) >= 10
        assert "deepseek" in manager.providers
        assert "openai" in manager.providers

    def test_update_provider_costs(self, manager):
        fetcher = Mock()
        fetcher.get_model_price.return_value = {
            "input_cost_per_token": 0.0002, "output_cost_per_token": 0.0004}
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            manager.update_provider_costs()
        assert manager.providers["deepseek"].cost_per_token == pytest.approx(0.0003)

    def test_update_provider_costs_no_pricing(self, manager):
        fetcher = Mock()
        fetcher.get_model_price.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            manager.update_provider_costs()

    def test_update_provider_costs_exception(self, manager):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            manager.update_provider_costs()  # must not raise


class TestEncryption:
    def test_generate_key(self, manager):
        key = manager._generate_encryption_key()
        assert len(key) > 20

    def test_load_or_create_key(self, manager, paths):
        enc = paths[2]
        key = manager._load_or_create_encryption_key()
        assert os.path.exists(enc)
        assert manager._load_or_create_encryption_key() == key  # reused

    def test_load_or_create_key_env_wins(self, paths):
        cfg, keys, enc = paths
        with patch.dict(os.environ, {"BYOK_ENCRYPTION_KEY": "env-key"}, clear=True):
            m = BYOKManager()
        assert m.encryption_key == "env-key"

    def test_get_fernet_str_and_bytes(self, manager):
        f1 = manager._get_fernet()
        assert f1 is not None
        manager.encryption_key = manager.encryption_key.encode()
        assert manager._get_fernet() is not None

    def test_get_fernet_empty_raises(self, manager):
        manager.encryption_key = ""
        with pytest.raises(ValueError):
            manager._get_fernet()

    def test_encrypt_decrypt_roundtrip(self, manager):
        enc = manager.encrypt_api_key("sk-secret-123")
        assert enc != "sk-secret-123"
        assert manager.decrypt_api_key(enc) == "sk-secret-123"


class TestKeyStorage:
    def test_store_and_get(self, manager):
        key_id = manager.store_api_key("deepseek", "sk-ds-123", "work", "production")
        assert key_id == "deepseek_work_production"
        assert manager.get_api_key("deepseek", "work") == "sk-ds-123"

    def test_store_unknown_provider_raises(self, manager):
        with pytest.raises(ValueError):
            manager.store_api_key("ghost", "sk-x")

    def test_get_env_fallback_read_only(self, manager):
        """Env fallback resolves the key but must NOT persist it.

        Auto-storing env values here leaked test-suite fake keys
        (conftest sets OPENAI/ANTHROPIC dummies) into the live key store.
        """
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "env-ds-key"}, clear=True):
            key = manager.get_api_key("deepseek")
        assert key == "env-ds-key"
        assert "deepseek_default_production" not in manager.api_keys

    def test_get_missing_returns_none(self, manager):
        with patch.dict(os.environ, {}, clear=True):
            assert manager.get_api_key("openai") is None

    def test_get_bumps_usage(self, manager):
        manager.store_api_key("deepseek", "sk-1")
        manager.get_api_key("deepseek")
        obj = manager.api_keys["deepseek_default_production"]
        assert obj.usage_count == 1
        assert obj.last_used is not None

    def test_get_decrypt_failure_returns_none(self, manager):
        manager.api_keys["deepseek_default_production"] = APIKey(
            provider_id="deepseek", key_name="default", encrypted_key="garbage",
            key_hash="h", created_at=datetime.now(), environment="production")
        assert manager.get_api_key("deepseek") is None


class TestUsageAndRouting:
    def test_track_usage_success_and_failure(self, manager):
        manager.track_usage("deepseek", success=True, tokens_used=100)
        manager.track_usage("deepseek", success=False, tokens_used=50)
        usage = manager.usage_stats["deepseek"]
        assert usage.total_requests == 2
        assert usage.successful_requests == 1
        assert usage.failed_requests == 1
        assert usage.total_tokens_used == 100  # only counted on success

    def _provider_with_key(self, manager, pid, cost, tasks, reasoning=1,
                           active=True):
        manager.providers[pid] = AIProviderConfig(
            id=pid, name=pid, description="d", api_key_env_var=f"{pid.upper()}_KEY",
            base_url="https://x", supported_tasks=tasks, cost_per_token=cost,
            model="m", reasoning_level=reasoning, is_active=active)
        manager.store_api_key(pid, f"sk-{pid}")

    def test_optimal_provider_cheapest(self, manager):
        self._provider_with_key(manager, "a", 0.10, ["chat"])
        self._provider_with_key(manager, "b", 0.02, ["chat"])
        assert manager.get_optimal_provider("chat") == "b"

    def test_optimal_provider_filters(self, manager):
        self._provider_with_key(manager, "low", 0.01, ["chat"], reasoning=1)
        with pytest.raises(ValueError):
            manager.get_optimal_provider("chat", min_reasoning_level=4)

    def test_optimal_provider_budget(self, manager):
        self._provider_with_key(manager, "cheap", 0.01, ["chat"])
        self._provider_with_key(manager, "pricy", 0.99, ["chat"])
        assert manager.get_optimal_provider("chat", budget_constraint=0.05) == "cheap"

    def test_optimal_provider_fallback_deepseek(self, manager):
        manager.store_api_key("deepseek", "sk-ds")
        assert manager.get_optimal_provider("weird_task") == "deepseek"

    def test_optimal_provider_none(self, manager):
        assert manager.get_optimal_provider("weird_task") is None

    def test_provider_status(self, manager):
        self._provider_with_key(manager, "a", 0.01, ["chat"])
        status = manager.get_provider_status("a")
        assert status["has_api_keys"] is True
        assert status["status"] == "active"

    def test_provider_status_unknown_raises(self, manager):
        with pytest.raises(ValueError):
            manager.get_provider_status("ghost")

    def test_compatibility_aliases(self, manager):
        self._provider_with_key(manager, "a", 0.01, ["chat"])
        assert manager.is_configured("default", "a") is True
        assert manager.get_tenant_api_key("default", "a") is not None


class TestNormalizeAndSingleton:
    def test_normalize_key_part(self, manager):
        assert manager._normalize_key_part(None, "d") == "d"
        assert manager._normalize_key_part("  x  ", "d") == "x"
        assert manager._normalize_key_part("", "d") == "d"
        assert manager._normalize_key_part(42, "d") == "42"
        assert manager._normalize_key_part({"a": 1}, "d") == "d"

    def test_singleton(self, paths):
        with patch.object(be, "_byok_manager", None):
            m1 = get_byok_manager()
            assert m1 is get_byok_manager()


# ============================================================================
# Routes layer
# ============================================================================

from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def route_client(paths):
    app = FastAPI()
    app.include_router(be.router)
    m = BYOKManager()
    app.dependency_overrides[be.get_byok_manager] = lambda: m
    yield TestClient(app), m


class TestHealthRoutes:
    def test_health_no_deps(self):
        app = FastAPI()
        app.include_router(be.router)
        resp = TestClient(app).get("/api/v1/byok/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_ai_health(self, route_client):
        c, m = route_client
        resp = c.get("/api/ai/health")
        assert resp.status_code == 200
        assert resp.json()["providers"]["total"] == len(m.providers)

    def test_ai_health_exception_503(self, route_client):
        c, m = route_client
        with patch.object(m, "get_provider_status", side_effect=RuntimeError("boom")):
            resp = c.get("/api/ai/health")
        assert resp.status_code == 503

    def test_v1_status(self, route_client):
        c, m = route_client
        resp = c.get("/api/v1/byok/status")
        assert resp.status_code == 200
        assert resp.json()["status_code"] == 200
        assert "providers_list" in resp.json()


class TestKeysRoutes:
    def test_get_keys_empty_and_with_keys(self, route_client):
        c, m = route_client
        assert c.get("/api/ai/keys").json()["count"] == 0
        m.store_api_key("deepseek", "sk-1234567890")
        data = c.get("/api/ai/keys").json()
        assert data["count"] == 1
        assert data["keys"][0]["masked_key"].startswith("****")

    def test_add_key_success(self, route_client):
        c, m = route_client
        resp = c.post("/api/ai/keys", json={
            "provider": "deepseek", "key": "sk-1234567890", "key_name": "work"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_add_key_validation_400(self, route_client):
        c, m = route_client
        assert c.post("/api/ai/keys", json={"key": "sk-1234567890"}).status_code == 400

    def test_add_key_value_error_404(self, route_client):
        c, m = route_client
        with patch.object(m, "store_api_key", side_effect=ValueError("no provider")):
            resp = c.post("/api/ai/keys", json={
                "provider": "ghost", "key": "sk-1234567890"})
        assert resp.status_code == 404

    def test_add_key_generic_500(self, route_client):
        c, m = route_client
        with patch.object(m, "store_api_key", side_effect=RuntimeError("boom")):
            resp = c.post("/api/ai/keys", json={
                "provider": "deepseek", "key": "sk-1234567890"})
        assert resp.status_code == 500

    def test_store_provider_key_routes(self, route_client):
        c, m = route_client
        resp = c.post("/api/ai/providers/openai/keys",
                      json={"api_key": "sk-1234567890", "key_name": "work"})
        assert resp.status_code == 200
        assert resp.json()["key_id"] == "openai_work_production"
        # status route
        assert c.get("/api/ai/providers/openai/keys/work").status_code == 200
        assert c.get("/api/ai/providers/openai/keys/nope").status_code == 404
        # delete
        assert c.delete("/api/ai/providers/openai/keys/work").status_code == 200
        assert c.delete("/api/ai/providers/openai/keys/work").status_code == 404

    def test_store_invalid_provider_400(self, route_client):
        c, m = route_client
        resp = c.post("/api/ai/providers/ghost/keys",
                      json={"api_key": "sk-1234567890"})
        assert resp.status_code == 400

    def test_store_short_key_422(self, route_client):
        c, m = route_client
        resp = c.post("/api/ai/providers/openai/keys", json={"api_key": "short"})
        assert resp.status_code == 422

    def test_store_bad_key_name_422(self, route_client):
        c, m = route_client
        resp = c.post("/api/ai/providers/openai/keys", json={
            "api_key": "sk-1234567890", "key_name": "bad name!"})
        assert resp.status_code == 422

    def test_store_value_error_404(self, route_client):
        c, m = route_client
        with patch.object(m, "store_api_key", side_effect=ValueError("boom")):
            resp = c.post("/api/ai/providers/openai/keys",
                          json={"api_key": "sk-1234567890"})
        assert resp.status_code == 404


class TestProvidersRoutes:
    def test_list_providers(self, route_client):
        c, m = route_client
        m.store_api_key("deepseek", "sk-1234567890")
        resp = c.get("/api/ai/providers")
        assert resp.status_code == 200
        assert resp.json()["total_providers"] == len(m.providers)
        assert resp.json()["active_providers"] >= 1

    def test_provider_detail_200_and_404(self, route_client):
        c, m = route_client
        assert c.get("/api/ai/providers/deepseek").status_code == 200
        assert c.get("/api/ai/providers/ghost").status_code == 404


class TestOptimizeRoutes:
    def test_optimize_success_with_alternatives(self, route_client):
        c, m = route_client
        m.store_api_key("deepseek", "sk-1234567890")
        m.store_api_key("openai", "sk-1234567890")
        resp = c.post("/api/ai/optimize-cost", json={
            "task_type": "chat", "estimated_tokens": 1000})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert "alternatives" in resp.json()

    def test_optimize_no_provider_400(self, route_client):
        c, m = route_client
        resp = c.post("/api/ai/optimize-cost", json={"task_type": "weird_task"})
        assert resp.status_code == 400

    def test_optimize_value_error_400(self, route_client):
        c, m = route_client
        with patch.object(m, "get_optimal_provider",
                          side_effect=ValueError("bad")):
            resp = c.post("/api/ai/optimize-cost", json={"task_type": "chat"})
        assert resp.status_code == 400

    def test_optimize_generic_500(self, route_client):
        c, m = route_client
        with patch.object(m, "get_optimal_provider",
                          side_effect=RuntimeError("boom")):
            resp = c.post("/api/ai/optimize-cost", json={"task_type": "chat"})
        assert resp.status_code == 500


class TestUsageRoutes:
    def test_track_usage_success_and_missing(self, route_client):
        c, m = route_client
        resp = c.post("/api/ai/usage/track", json={
            "provider_id": "deepseek", "success": True, "tokens_used": 100})
        assert resp.status_code == 200
        assert resp.json()["tokens_used"] == 100
        assert c.post("/api/ai/usage/track", json={}).status_code == 400

    def test_usage_stats_all_and_single(self, route_client):
        c, m = route_client
        m.track_usage("deepseek", success=True, tokens_used=10)
        all_stats = c.get("/api/ai/usage/stats").json()
        assert all_stats["total_providers"] == 1
        single = c.get("/api/ai/usage/stats", params={"provider_id": "deepseek"}).json()
        assert single["usage"]["total_tokens_used"] == 10
        assert c.get("/api/ai/usage/stats",
                     params={"provider_id": "ghost"}).status_code == 404

    def test_usage_stats_exception_500(self, route_client):
        c, m = route_client
        m.track_usage("deepseek", success=True)
        with patch("core.byok_endpoints.asdict", side_effect=RuntimeError("boom")):
            resp = c.get("/api/ai/usage/stats")
        assert resp.status_code == 500


class TestPdfRoutes:
    def test_pdf_providers(self, route_client):
        c, m = route_client
        resp = c.get("/api/ai/pdf/providers")
        assert resp.status_code == 200
        assert "pdf_providers" in resp.json()

    def test_pdf_optimize_success(self, route_client):
        c, m = route_client
        m.store_api_key("deepseek", "sk-1234567890")
        resp = c.post("/api/ai/pdf/optimize", json={
            "pdf_type": "scanned", "needs_ocr": True, "estimated_pages": 10})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["recommended_provider"]["task_type"] == "pdf_ocr"

    def test_pdf_optimize_image_comprehension(self, route_client):
        c, m = route_client
        m.store_api_key("deepseek", "sk-1234567890")
        resp = c.post("/api/ai/pdf/optimize", json={"needs_image_comprehension": True})
        assert resp.json()["recommended_provider"]["task_type"] == "image_comprehension"

    def test_pdf_optimize_no_provider_400(self, route_client):
        c, m = route_client
        resp = c.post("/api/ai/pdf/optimize", json={"pdf_type": "scanned"})
        assert resp.status_code == 400

    def test_pdf_optimize_value_error_400(self, route_client):
        c, m = route_client
        with patch.object(m, "get_optimal_provider", side_effect=ValueError("bad")):
            resp = c.post("/api/ai/pdf/optimize", json={})
        assert resp.status_code == 400

    def test_pdf_optimize_generic_500(self, route_client):
        c, m = route_client
        with patch.object(m, "get_optimal_provider", side_effect=RuntimeError("boom")):
            resp = c.post("/api/ai/pdf/optimize", json={})
        assert resp.status_code == 500


class TestPricingRoutes:
    def test_pricing_success(self, route_client):
        fetcher = Mock()
        fetcher.pricing_cache = {"m": 1}
        fetcher.last_fetch = None
        fetcher._is_cache_valid.return_value = True
        fetcher.get_cheapest_models.return_value = []
        fetcher.compare_providers.return_value = {}
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = route_client[0].get("/api/ai/pricing")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_pricing_error(self, route_client):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            resp = route_client[0].get("/api/ai/pricing")
        assert resp.json()["status"] == "error"

    def test_pricing_refresh(self, route_client):
        with patch("core.dynamic_pricing_fetcher.refresh_pricing_cache",
                   new=AsyncMock(return_value={"m1": {}})):
            resp = route_client[0].post("/api/ai/pricing/refresh")
        assert resp.json()["status"] == "success"

    def test_model_pricing(self, route_client):
        fetcher = Mock()
        fetcher.get_model_price.return_value = {"input_cost_per_token": 1e-6}
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            ok = route_client[0].get("/api/ai/pricing/model/gpt-4o").json()
            fetcher.get_model_price.return_value = None
            nf = route_client[0].get("/api/ai/pricing/model/x").json()
        assert ok["status"] == "success"
        assert nf["status"] == "not_found"

    def test_provider_pricing(self, route_client):
        fetcher = Mock()
        fetcher.get_provider_models.return_value = [{"id": "m1"}]
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = route_client[0].get("/api/ai/pricing/provider/openai").json()
        assert resp["status"] == "success"
        assert resp["model_count"] == 1

    def test_estimate_cost(self, route_client):
        fetcher = Mock()
        fetcher.estimate_cost.return_value = 0.5
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = route_client[0].post("/api/ai/pricing/estimate",
                                        json={"model": "gpt-4o"}).json()
        assert resp["status"] == "success"
        assert resp["estimated_cost_usd"] == 0.5

    def test_estimate_cost_fallback_and_unavailable(self, route_client):
        fetcher = Mock()
        fetcher.estimate_cost.return_value = None
        fetcher.get_model_price.return_value = {
            "input_cost_per_token": 0.001, "output_cost_per_token": 0.002}
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            fallback = route_client[0].post("/api/ai/pricing/estimate",
                                            json={"model": "m", "input_tokens": 10,
                                                  "output_tokens": 20}).json()
            fetcher.get_model_price.return_value = None
            unavail = route_client[0].post("/api/ai/pricing/estimate",
                                           json={"model": "m"}).json()
        assert fallback["status"] == "success"
        assert fallback["estimated_cost_usd"] == pytest.approx(0.01 + 0.04)
        assert unavail["status"] == "pricing_unavailable"

    def test_estimate_cost_prompt_based_tokens(self, route_client):
        fetcher = Mock()
        fetcher.estimate_cost.return_value = 0.1
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = route_client[0].post("/api/ai/pricing/estimate",
                                        json={"model": "m", "prompt": "hello world"}).json()
        assert resp["input_tokens"] == 2  # len // 4
