"""Backend depth wave 116 (2026-08-13) — coverage push for
core/byok_endpoints.py (72% -> 95%+).

Covers: corrupt-config tolerance, save failures, fernet fail-loud paths,
env-key fallback, decrypt failure, track_usage branches, optimal-provider
budget/reasoning/deepseek fallback, route branches for keys/providers/
optimize/usage-stats/pdf/pricing/estimate. Fully mocked — zero LLM spend.
"""

import asyncio
import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import core.byok_endpoints as be
from core.byok_endpoints import (
    AIProviderConfig,
    APIKey,
    BYOKManager,
    ProviderUsage,
)


def asyncio_run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


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


class TestConfigEdges:
    def test_corrupt_providers_config_tolerated(self, paths):
        cfg, keys, enc = paths
        with open(cfg, "w") as f:
            f.write("{broken")
        m = BYOKManager()
        assert m.providers  # defaults initialized

    def test_provider_save_failure_logged(self, manager, paths):
        with patch.object(manager, "_atomic_write_json",
                          side_effect=OSError("disk full")):
            manager._save_configuration()  # must not raise

    def test_keys_save_failure_logged(self, manager, paths):
        manager.store_api_key("deepseek", "sk-1234567890")
        with patch.object(manager, "_atomic_write_json",
                          side_effect=OSError("disk full")):
            manager._save_configuration()  # must not raise

    def test_update_provider_costs_failure_tolerated(self, manager):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("fetcher down")):
            manager.update_provider_costs()  # must not raise

    def test_update_provider_costs_updates_prices(self, manager):
        fetcher = Mock()
        fetcher.get_model_price.return_value = {
            "input_cost_per_token": 0.00002,
            "output_cost_per_token": 0.00006,
        }
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            manager.update_provider_costs()
        assert manager.providers["deepseek"].cost_per_token == pytest.approx(0.00004)


class TestAddAPIKeyRequest:
    def test_invalid_key_name_rejected(self):
        with pytest.raises(Exception):
            be.AddAPIKeyRequest(api_key="sk-1234567890", key_name="bad name!")

    def test_valid_key_name_accepted(self):
        req = be.AddAPIKeyRequest(api_key="sk-1234567890", key_name="prod_main")
        assert req.key_name == "prod_main"


class TestFernetEdges:
    def test_get_fernet_empty_key_raises(self, manager):
        manager.encryption_key = None
        with pytest.raises(Exception):
            manager._get_fernet()

    def test_get_fernet_invalid_key_raises(self, manager):
        manager.encryption_key = "not-a-valid-fernet-key"
        with pytest.raises(Exception):
            manager._get_fernet()


class TestKeyOps:
    def test_store_api_key_unknown_provider_raises(self, manager):
        with pytest.raises(ValueError):
            manager.store_api_key("ghost", "sk-1234567890")

    def test_get_api_key_env_fallback_stores(self, manager, paths):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-env-fallback-123"}):
            key = manager.get_api_key("deepseek")
        assert key == "sk-env-fallback-123"
        assert "deepseek_default_production" in manager.api_keys

    def test_get_api_key_no_key_no_env_returns_none(self, manager, paths):
        assert manager.get_api_key("deepseek") is None

    def test_get_api_key_decrypt_failure_returns_none(self, manager, paths):
        manager.api_keys["deepseek_default_production"] = APIKey(
            provider_id="deepseek", key_name="default", encrypted_key="garbage",
            key_hash="h", created_at=datetime.now(), environment="production")
        with patch.object(manager, "decrypt_api_key",
                          side_effect=Exception("bad token")):
            assert manager.get_api_key("deepseek") is None

    def test_get_tenant_api_key_alias(self, manager, paths):
        manager.store_api_key("deepseek", "sk-1234567890", key_name="tenant-9")
        assert manager.get_tenant_api_key("tenant-9", "deepseek") == "sk-1234567890"


class TestTrackUsage:
    def test_track_usage_new_provider_success(self, manager):
        manager.track_usage("deepseek", success=True, tokens_used=1000)
        usage = manager.usage_stats["deepseek"]
        assert usage.total_requests == 1
        assert usage.successful_requests == 1
        assert usage.total_tokens_used == 1000
        assert usage.cost_accumulated > 0
        assert usage.failed_requests == 0

    def test_track_usage_failure(self, manager):
        manager.track_usage("openai", success=False, tokens_used=500)
        usage = manager.usage_stats["openai"]
        assert usage.failed_requests == 1
        assert usage.total_tokens_used == 0


class TestOptimalProviderBranches:
    def _provider_with_key(self, manager, pid, cost, tasks, reasoning=1):
        manager.providers[pid] = AIProviderConfig(
            id=pid, name=pid, description="d", api_key_env_var=f"{pid.upper()}_KEY",
            base_url="https://x", supported_tasks=tasks, cost_per_token=cost,
            model="m", reasoning_level=reasoning)
        manager.store_api_key(pid, f"sk-{pid}")

    def test_high_reasoning_required_no_providers_raises(self, manager):
        manager.providers["low"] = AIProviderConfig(
            id="low", name="low", description="d", api_key_env_var="L_KEY",
            supported_tasks=["chat"], reasoning_level=1)
        manager.store_api_key("low", "sk-low")
        with pytest.raises(ValueError, match="No high-reasoning providers"):
            manager.get_optimal_provider("chat", min_reasoning_level=4)

    def test_deepseek_fallback_for_missing_task(self, manager):
        self._provider_with_key(manager, "deepseek", 0.001, ["code"])
        assert manager.get_optimal_provider("chat") == "deepseek"

    def test_budget_constraint_filters_providers(self, manager):
        self._provider_with_key(manager, "expensive", 0.01, ["chat"])
        self._provider_with_key(manager, "cheap", 0.0005, ["chat"])
        assert manager.get_optimal_provider("chat", budget_constraint=0.001) == "cheap"

    def test_budget_constraint_eliminates_all(self, manager):
        self._provider_with_key(manager, "expensive", 0.01, ["chat"])
        assert manager.get_optimal_provider("chat", budget_constraint=0.0001) is None


class TestProviderStatus:
    def test_status_unknown_provider_raises(self, manager):
        with pytest.raises(ValueError):
            manager.get_provider_status("ghost")

    def test_status_reports_inactive_without_keys(self, manager):
        manager.providers["custom"] = AIProviderConfig(
            id="custom", name="C", description="d", api_key_env_var="C_KEY",
            supported_tasks=["chat"], is_active=False)
        status = manager.get_provider_status("custom")
        assert status["status"] == "inactive"
        assert status["has_api_keys"] is False

    def test_normalize_key_part_non_string(self):
        assert BYOKManager._normalize_key_part(123, "default") == "123"
        assert BYOKManager._normalize_key_part(None, "default") == "default"
        assert BYOKManager._normalize_key_part("", "default") == "default"
        assert BYOKManager._normalize_key_part(["bad"], "default") == "default"
        assert BYOKManager._normalize_key_part(0.5, "default") == "0.5"
        assert BYOKManager._normalize_key_part(True, "default") == "True"


class TestRoutes:
    @staticmethod
    def _client(manager):
        app = FastAPI()
        app.include_router(be.router)
        app.dependency_overrides[be.get_byok_manager] = lambda: manager
        return TestClient(app)

    def test_add_api_key_missing_fields_400(self, manager):
        resp = self._client(manager).post("/api/ai/keys", json={})
        assert resp.status_code == 400

    def test_add_api_key_success(self, manager):
        resp = self._client(manager).post(
            "/api/ai/keys",
            json={"provider": "deepseek", "key": "sk-1234567890", "key_name": "work"})
        assert resp.status_code == 200
        assert resp.json()["key_id"] == "deepseek_work_production"

    def test_add_api_key_unknown_provider_404(self, manager):
        resp = self._client(manager).post(
            "/api/ai/keys",
            json={"provider": "ghost", "key": "sk-1234567890"})
        assert resp.status_code == 404

    def test_add_api_key_generic_500(self, manager):
        with patch.object(manager, "store_api_key",
                          side_effect=RuntimeError("boom")):
            resp = self._client(manager).post(
                "/api/ai/keys",
                json={"provider": "deepseek", "key": "sk-1234567890"})
        assert resp.status_code == 500

    def test_get_ai_providers_mixed_status(self, manager):
        manager.providers["custom"] = AIProviderConfig(
            id="custom", name="C", description="d", api_key_env_var="C_KEY",
            supported_tasks=["chat"])
        manager.store_api_key("custom", "sk-custom")
        resp = self._client(manager).get("/api/ai/providers")
        body = resp.json()
        assert body["total_providers"] == len(manager.providers)
        assert body["active_providers"] >= 1

    def test_get_ai_provider_success(self, manager):
        resp = self._client(manager).get("/api/ai/providers/deepseek")
        assert resp.status_code == 200
        assert resp.json()["provider"]["id"] == "deepseek"

    def test_get_ai_provider_404(self, manager):
        resp = self._client(manager).get("/api/ai/providers/ghost")
        assert resp.status_code == 404

    def test_store_key_route_invalid_provider_400(self, manager):
        resp = self._client(manager).post(
            "/api/ai/providers/ghost/keys", json={"api_key": "sk-1234567890"})
        assert resp.status_code == 400

    def test_store_key_route_value_error_404(self, manager):
        with patch.object(manager, "store_api_key",
                          side_effect=ValueError("nope")):
            resp = self._client(manager).post(
                "/api/ai/providers/deepseek/keys",
                json={"api_key": "sk-1234567890"})
        assert resp.status_code == 404

    def test_get_api_key_status_not_found_404(self, manager):
        resp = self._client(manager).get("/api/ai/providers/deepseek/keys/default")
        assert resp.status_code == 404

    def test_get_api_key_status_success(self, manager):
        manager.store_api_key("deepseek", "sk-1234567890")
        resp = self._client(manager).get("/api/ai/providers/deepseek/keys/default")
        body = resp.json()
        assert body["has_key"] is True
        assert body["provider_id"] == "deepseek"

    def test_delete_api_key_not_found_404(self, manager):
        resp = self._client(manager).delete("/api/ai/providers/deepseek/keys/default")
        assert resp.status_code == 404

    def test_delete_api_key_success(self, manager):
        manager.store_api_key("deepseek", "sk-1234567890")
        resp = self._client(manager).delete("/api/ai/providers/deepseek/keys/default")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_optimize_cost_success_with_alternatives(self, manager):
        manager.store_api_key("deepseek", "sk-1234567890")
        manager.providers["openai"] = AIProviderConfig(
            id="openai", name="OpenAI", description="d", api_key_env_var="O_KEY",
            supported_tasks=["chat"], cost_per_token=0.03)
        manager.store_api_key("openai", "sk-openai-123")
        resp = self._client(manager).post(
            "/api/ai/optimize-cost",
            json={"task_type": "chat", "budget_constraint": 0.05,
                  "estimated_tokens": 1000})
        body = resp.json()
        assert body["success"] is True
        assert body["recommended_provider"] == "deepseek"
        assert len(body["alternatives"]) >= 1

    def test_optimize_cost_no_provider_400(self, manager):
        resp = self._client(manager).post(
            "/api/ai/optimize-cost", json={"task_type": "nonexistent_task"})
        assert resp.status_code == 400

    def test_optimize_cost_value_error_400(self, manager):
        with patch.object(manager, "get_optimal_provider",
                          side_effect=ValueError("bad")):
            resp = self._client(manager).post(
                "/api/ai/optimize-cost", json={"task_type": "chat"})
        assert resp.status_code == 400

    def test_optimize_cost_generic_500(self, manager):
        with patch.object(manager, "get_optimal_provider",
                          side_effect=RuntimeError("boom")):
            resp = self._client(manager).post(
                "/api/ai/optimize-cost", json={"task_type": "chat"})
        assert resp.status_code == 500

    def test_track_usage_missing_provider_400(self, manager):
        resp = self._client(manager).post(
            "/api/ai/usage/track", json={"success": True})
        assert resp.status_code == 400

    def test_track_usage_success(self, manager):
        resp = self._client(manager).post(
            "/api/ai/usage/track",
            json={"provider_id": "deepseek", "success": True, "tokens_used": 100})
        assert resp.status_code == 200
        assert resp.json()["tokens_used"] == 100

    def test_usage_stats_provider_not_found_404(self, manager):
        resp = self._client(manager).get("/api/ai/usage/stats?provider_id=ghost")
        assert resp.status_code == 404

    def test_usage_stats_single_provider(self, manager):
        manager.track_usage("deepseek", success=True, tokens_used=50)
        resp = self._client(manager).get("/api/ai/usage/stats?provider_id=deepseek")
        assert resp.status_code == 200
        assert resp.json()["usage"]["total_requests"] == 1

    def test_usage_stats_all(self, manager):
        manager.track_usage("deepseek", success=True, tokens_used=50)
        manager.track_usage("openai", success=False, tokens_used=0)
        resp = self._client(manager).get("/api/ai/usage/stats")
        assert resp.json()["total_providers"] == 2

    def test_usage_stats_generic_500(self, manager):
        class BoomStats(dict):
            def items(self):
                raise RuntimeError("boom")

        with patch.object(manager, "usage_stats", BoomStats()):
            resp = self._client(manager).get("/api/ai/usage/stats")
        assert resp.status_code == 500

    def test_pdf_providers_filters(self, manager):
        resp = self._client(manager).get("/api/ai/pdf/providers")
        body = resp.json()
        assert body["total_pdf_providers"] >= 1
        assert "pdf_ocr" in body["supported_tasks"]

    def test_pdf_optimize_image_comprehension(self, manager):
        manager.store_api_key("deepseek", "sk-1234567890")
        resp = self._client(manager).post(
            "/api/ai/pdf/optimize",
            json={"needs_image_comprehension": True, "estimated_pages": 5})
        assert resp.status_code == 200
        assert resp.json()["recommended_provider"]["task_type"] == "image_comprehension"

    def test_pdf_optimize_document_processing_default(self, manager):
        manager.store_api_key("deepseek", "sk-1234567890")
        resp = self._client(manager).post("/api/ai/pdf/optimize", json={})
        assert resp.status_code == 200
        assert resp.json()["recommended_provider"]["task_type"] == "document_processing"

    def test_pdf_optimize_no_provider_400(self, manager):
        resp = self._client(manager).post(
            "/api/ai/pdf/optimize", json={"needs_ocr": True})
        assert resp.status_code == 400

    def test_pdf_optimize_scenarios_populated(self, manager):
        manager.store_api_key("deepseek", "sk-1234567890")
        resp = self._client(manager).post(
            "/api/ai/pdf/optimize",
            json={"needs_ocr": True, "budget_constraint": 0.01})
        assert resp.status_code == 200
        assert "high_quality" in resp.json()["alternative_scenarios"]

    def test_pdf_optimize_value_error_400(self, manager):
        manager.store_api_key("deepseek", "sk-1234567890")
        with patch.object(manager, "get_optimal_provider",
                          side_effect=ValueError("bad")):
            resp = self._client(manager).post(
                "/api/ai/pdf/optimize", json={"needs_ocr": True})
        assert resp.status_code == 400

    def test_pdf_optimize_generic_500(self, manager):
        manager.store_api_key("deepseek", "sk-1234567890")
        with patch.object(manager, "get_optimal_provider",
                          side_effect=RuntimeError("boom")):
            resp = self._client(manager).post(
                "/api/ai/pdf/optimize", json={"needs_ocr": True})
        assert resp.status_code == 500

    def test_health_route_exception_503(self, manager):
        with patch.object(manager, "get_provider_status",
                          side_effect=RuntimeError("boom")):
            resp = self._client(manager).get("/api/ai/health")
        assert resp.status_code == 503


class TestPricingRoutes:
    @staticmethod
    def _client(manager):
        app = FastAPI()
        app.include_router(be.router)
        app.dependency_overrides[be.get_byok_manager] = lambda: manager
        return TestClient(app)

    def test_get_ai_pricing_success(self):
        fetcher = Mock()
        fetcher.pricing_cache = {"gpt-4o": {}}
        fetcher.last_fetch = datetime(2026, 8, 1, 12, 0, 0)
        fetcher._is_cache_valid.return_value = True
        fetcher.get_cheapest_models.return_value = ["gpt-4o"]
        fetcher.compare_providers.return_value = {}
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = asyncio_run(be.get_ai_pricing())
        assert resp["status"] == "success"
        assert resp["model_count"] == 1

    def test_get_ai_pricing_error(self):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            resp = asyncio_run(be.get_ai_pricing())
        assert resp["status"] == "error"

    def test_refresh_pricing_success(self, manager):
        with patch("core.dynamic_pricing_fetcher.refresh_pricing_cache",
                   new=AsyncMock(return_value=[{"id": "m1"}])), \
             patch.object(manager, "update_provider_costs") as updater:
            resp = asyncio_run(be.refresh_ai_pricing(byok_manager=manager))
        assert resp["status"] == "success"
        assert resp["models_fetched"] == 1
        updater.assert_called_once()

    def test_get_model_pricing_found(self):
        fetcher = Mock()
        fetcher.get_model_price.return_value = {"input_cost_per_token": 0.01}
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = asyncio_run(be.get_model_pricing("gpt-4o"))
        assert resp["status"] == "success"
        assert resp["pricing"]["input_cost_per_token"] == 0.01

    def test_get_model_pricing_not_found(self):
        fetcher = Mock()
        fetcher.get_model_price.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = asyncio_run(be.get_model_pricing("unknown-model"))
        assert resp["status"] == "not_found"

    def test_get_provider_pricing_success(self):
        fetcher = Mock()
        fetcher.get_provider_models.return_value = ["m1", "m2", "m3"]
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = asyncio_run(be.get_provider_pricing("openai", limit=2))
        assert resp["status"] == "success"
        assert resp["model_count"] == 2

    def test_estimate_request_cost_success(self):
        fetcher = Mock()
        fetcher.estimate_cost.return_value = 0.00123
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = asyncio_run(be.estimate_request_cost(
                {"model": "m", "input_tokens": 100, "output_tokens": 50}))
        assert resp["status"] == "success"
        assert resp["estimated_cost_usd"] == 0.00123

    def test_estimate_request_cost_fallback_pricing(self):
        fetcher = Mock()
        fetcher.estimate_cost.return_value = None
        fetcher.get_model_price.return_value = {
            "input_cost_per_token": 0.0001,
            "output_cost_per_token": 0.0002,
        }
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = asyncio_run(be.estimate_request_cost(
                {"model": "m", "input_tokens": 10, "output_tokens": 5}))
        assert resp["status"] == "success"
        assert resp["estimated_cost_usd"] == pytest.approx(0.0001 * 10 + 0.0002 * 5)

    def test_estimate_request_cost_unavailable(self):
        fetcher = Mock()
        fetcher.estimate_cost.return_value = None
        fetcher.get_model_price.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            resp = asyncio_run(be.estimate_request_cost({"model": "m"}))
        assert resp["status"] == "pricing_unavailable"
