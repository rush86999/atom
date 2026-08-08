"""
Coverage-push + TDD bug-hunt for api/byok_routes.py.

Bugs hunted (red -> green):
A. byok_health_v1 passes the BYOKManager as the positional ``current_user``
   of the module-global ``byok_health_check`` (whose name is shadowed by the
   /api/ai/health definition), so the v1 handler raises AttributeError on
   ``byok_manager.providers`` (a raw ``Depends`` marker) and always 503s.
B. GET /api/ai/keys returns three hardcoded fake keys (``sk-...1234``,
   count=3) regardless of what is actually stored.
C. POST /api/ai/keys validates then discards the key — a silent no-op that
   reports success while persisting nothing.
D. store_tenant_api_key persists the PLAINTEXT API key into tenant_settings
   (credentials at rest) instead of the Fernet-encrypted value.
E. GET /api/ai/usage/stats returns a bare dict (no ApiResponse envelope)
   when the requested tenant_id has no usage — inconsistent wire shape.

Plus exhaustive endpoint/manager coverage to push the module >= 80%.
"""
import asyncio
import json
import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.byok_routes as byok_routes
from api.byok_routes import APIKey, BYOKManager
from core.auth import get_current_user, get_current_tenant
from core.database import get_db


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tmp_byok_paths(tmp_path):
    """Redirect BYOK persistence files to a temp dir."""
    cfg = tmp_path / "byok_config.json"
    keys = tmp_path / "byok_keys.json"
    enc = tmp_path / "byok_encryption_key"
    with patch.object(byok_routes, "BYOK_CONFIG_FILE", str(cfg)), \
            patch.object(byok_routes, "BYOK_KEYS_FILE", str(keys)), \
            patch.object(byok_routes, "BYOK_ENC_KEY_FILE", str(enc)):
        yield cfg, keys, enc


@pytest.fixture
def manager(tmp_byok_paths):
    """Real BYOKManager with temp persistence files."""
    return BYOKManager()


@pytest.fixture
def app(manager, db_session):
    """FastAPI app with the real BYOK router and bound identity."""
    from core.models import Tenant

    tenant = Tenant(
        name="Cov Tenant",
        subdomain="cov-tenant",
        edition="personal",
        ai_mode="byok",
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    def _override_user():
        return SimpleNamespace(id="cov-user", tenant_id=tenant.id)

    def _override_tenant():
        return tenant

    def _override_db():
        try:
            yield db_session
        finally:
            pass

    app = FastAPI()
    app.include_router(byok_routes.router)
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_tenant] = _override_tenant
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[byok_routes.get_byok_manager] = lambda: manager
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def store_global_openai(manager):
    """Store global keys on the SAME manager the app uses."""
    manager.store_api_key("openai", "sk-proj-global-secret-1234567890")
    manager.store_api_key("anthropic", "sk-ant-global-secret-1234567890")
    return manager


# ============================================================================
# Bug A: /api/v1/byok/health shadowed-broken handler
# ============================================================================

class TestV1HealthHandler:

    def test_byok_health_v1_direct_call_returns_200(self, manager, app):
        result = asyncio.run(byok_routes.byok_health_v1(
            current_user=SimpleNamespace(id="u1"), byok_manager=manager
        ))
        assert result.success is True

    def test_byok_health_v1_via_http(self, client):
        response = client.get("/api/v1/byok/health")
        assert response.status_code == 200
        assert response.json()["success"] is True


# ============================================================================
# Bug B: GET /api/ai/keys returns real stored keys, not hardcoded fakes
# ============================================================================

class TestApiKeysListing:

    def test_get_api_keys_reflects_stored_keys(self, client, manager):
        manager.store_api_key("openai", "sk-proj-real-secret-9876543210")
        response = client.get("/api/ai/keys")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["count"] == 1
        assert data["keys"][0]["provider"] == "openai"
        assert data["keys"][0]["masked_key"] == "sk-p...3210"

    def test_get_api_keys_empty_when_nothing_stored(self, client):
        response = client.get("/api/ai/keys")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["count"] == 0
        assert data["keys"] == []

    def test_get_api_keys_masked_fallback_on_decrypt_failure(self, client, manager):
        manager.api_keys["openai_broken_production"] = APIKey(
            provider_id="openai", key_name="broken",
            encrypted_key="garbage-ciphertext", key_hash="abc123hash",
            created_at=datetime.now(),
        )
        response = client.get("/api/ai/keys")
        assert response.status_code == 200
        data = response.json()["data"]
        entry = data["keys"][0]
        assert entry["masked_key"] == "abc1...hash"


# ============================================================================
# Bug C: POST /api/ai/keys persists the key instead of being a no-op
# ============================================================================

class TestApiKeysRegistration:

    def test_post_api_keys_stores_key(self, client, manager):
        response = client.post(
            "/api/ai/keys",
            json={"provider": "openai", "key": "sk-proj-posted-1234567890"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["provider"] == "openai"
        assert data["masked_key"] == "sk-p...7890"
        assert manager.get_api_key("openai") == "sk-proj-posted-1234567890"

    def test_post_api_keys_rejects_unknown_provider(self, client):
        response = client.post(
            "/api/ai/keys",
            json={"provider": "nope", "key": "sk-proj-unknown-1234567890"},
        )
        assert response.status_code == 400

    def test_post_api_keys_requires_provider_and_key(self, client):
        assert client.post("/api/ai/keys", json={"key": "sk-x"}).status_code == 400
        assert client.post("/api/ai/keys", json={"provider": "openai"}).status_code == 400


# ============================================================================
# Bug D: tenant API keys are encrypted at rest
# ============================================================================

class TestTenantKeyEncryptionAtRest:

    def test_stored_tenant_key_not_plaintext_in_db(
        self, client, manager, db_session
    ):
        from core.models import Tenant, TenantSetting

        tenant = db_session.query(Tenant).first()
        plaintext = "sk-tenant-plaintext-1234567890"
        response = client.post(
            "/api/ai/providers/openai/keys",
            params={"api_key": plaintext, "key_name": "default"},
        )
        assert response.status_code == 200

        setting = db_session.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant.id,
            TenantSetting.setting_key == "OPENAI_API_KEY",
        ).first()
        assert setting is not None
        assert setting.setting_value != plaintext
        assert plaintext not in setting.setting_value

        decrypted = manager.get_tenant_api_key(
            tenant.id, "openai", db=db_session
        )
        assert decrypted == plaintext


# ============================================================================
# Bug E: GET /api/ai/usage/stats always returns the ApiResponse envelope
# ============================================================================

class TestUsageStatsShape:

    def test_usage_stats_unknown_tenant_is_api_response(self, client):
        response = client.get("/api/ai/usage/stats?tenant_id=ghost-tenant")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["total_providers"] == 0


# ============================================================================
# Endpoint coverage
# ============================================================================

class TestHealthEndpoints:

    def test_ai_health_reports_counts(self, client, manager, store_global_openai):
        manager.track_usage("t1", "openai", success=True, tokens_used=100)
        response = client.get("/api/ai/health")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["providers"]["total"] == len(manager.providers)
        assert data["providers"]["active"] == 2
        assert data["providers"]["with_keys"] == 2
        assert data["usage"]["total_requests"] == 1
        assert data["storage"]["encryption_enabled"] is True

    def test_ai_health_503_on_provider_failure(self, client, manager):
        with patch.object(
            manager, "get_provider_status", side_effect=RuntimeError("boom")
        ):
            response = client.get("/api/ai/health")
        assert response.status_code == 503


class TestProviderEndpoints:

    def test_list_providers_with_tenant_status(self, client, store_global_openai):
        response = client.get("/api/ai/providers")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_providers"] == len(
            store_global_openai.providers
        )
        assert data["active_providers"] >= 2
        assert data["ai_mode"] == "byok"

    def test_get_provider_success(self, client, store_global_openai):
        response = client.get("/api/ai/providers/openai")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["has_api_keys"] is True
        assert data["provider"]["id"] == "openai"

    def test_get_provider_unknown_404(self, client):
        response = client.get("/api/ai/providers/does-not-exist")
        assert response.status_code == 404

    def test_list_providers_handles_status_failure(self, client, manager):
        with patch.object(
            manager, "get_tenant_provider_status",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/ai/providers")
        assert response.status_code == 200
        assert response.json()["data"]["total_providers"] == 0

    def test_store_provider_key_short_key_422(self, client):
        response = client.post(
            "/api/ai/providers/openai/keys", params={"api_key": "short"}
        )
        assert response.status_code == 422

    def test_store_provider_key_unknown_provider_404(self, client):
        response = client.post(
            "/api/ai/providers/ghost/keys",
            params={"api_key": "sk-long-enough-1234567890"},
        )
        assert response.status_code == 404

    def test_store_provider_key_internal_error_500(self, client, manager):
        with patch.object(
            manager, "store_tenant_api_key",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post(
                "/api/ai/providers/openai/keys",
                params={"api_key": "sk-long-enough-1234567890"},
            )
        assert response.status_code == 500

    def test_get_key_status_found(self, client, manager):
        manager.store_api_key("openai", "sk-proj-status-1234567890", key_name="prod")
        response = client.get("/api/ai/providers/openai/keys/prod")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["has_key"] is True
        assert data["provider_id"] == "openai"

    def test_get_key_status_not_found(self, client):
        response = client.get("/api/ai/providers/openai/keys/nope")
        assert response.status_code == 404

    def test_delete_key_success(self, client, manager):
        manager.store_api_key("openai", "sk-proj-del-1234567890")
        response = client.delete("/api/ai/providers/openai/keys/default")
        assert response.status_code == 200
        assert manager.get_api_key("openai") is None

    def test_delete_key_not_found(self, client):
        response = client.delete("/api/ai/providers/openai/keys/nope")
        assert response.status_code == 404


class TestOptimizeCost:

    def test_optimize_cost_recommends(self, client, store_global_openai):
        response = client.post(
            "/api/ai/optimize-cost",
            json={"task_type": "general", "estimated_tokens": 1000},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["recommended_provider"] in ("openai", "anthropic")
        assert data["estimated_tokens"] == 1000
        assert len(data["alternatives"]) == 1

    def test_optimize_cost_no_suitable_provider(self, client):
        response = client.post(
            "/api/ai/optimize-cost",
            json={"task_type": "general", "estimated_tokens": 1000},
        )
        assert response.status_code == 400

    def test_optimize_cost_budget_excludes_all(self, client, store_global_openai):
        response = client.post(
            "/api/ai/optimize-cost",
            json={"task_type": "general", "budget_constraint": 0.000000001},
        )
        assert response.status_code == 400

    def test_optimize_cost_internal_error_500(self, client, manager):
        with patch.object(
            manager, "get_optimal_provider",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post(
                "/api/ai/optimize-cost",
                json={"task_type": "general"},
            )
        assert response.status_code == 500


class TestUsageEndpoints:

    def test_track_usage_success(self, client, manager, db_session):
        from core.models import Tenant

        tenant = db_session.query(Tenant).first()
        response = client.post(
            "/api/ai/usage/track",
            json={"provider_id": "openai", "success": True, "tokens_used": 500},
        )
        assert response.status_code == 200
        usage = manager.usage_stats.get(tenant.id, {}).get("openai")
        assert usage is not None
        assert usage.total_requests == 1
        assert usage.total_tokens_used == 500

    def test_track_usage_failure_path(self, client, manager):
        response = client.post(
            "/api/ai/usage/track",
            json={"provider_id": "deepseek", "success": False, "tokens_used": 0},
        )
        assert response.status_code == 200

    def test_track_usage_missing_provider_400(self, client):
        response = client.post("/api/ai/usage/track", json={"success": True})
        assert response.status_code == 400

    def test_usage_stats_all_tenants(self, client, manager):
        manager.track_usage("t1", "openai", success=True, tokens_used=100)
        response = client.get("/api/ai/usage/stats")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_tenants"] == 1

    def test_usage_stats_by_tenant(self, client, manager):
        manager.track_usage("t1", "openai", success=True, tokens_used=100)
        response = client.get("/api/ai/usage/stats?tenant_id=t1")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "openai" in data["usage_stats"]

    def test_usage_stats_by_tenant_and_provider(self, client, manager):
        manager.track_usage("t1", "openai", success=True, tokens_used=100)
        response = client.get("/api/ai/usage/stats?tenant_id=t1&provider_id=openai")
        assert response.status_code == 200
        assert response.json()["data"]["usage"]["total_requests"] == 1

    def test_usage_stats_provider_404(self, client, manager):
        manager.track_usage("t1", "openai", success=True)
        response = client.get("/api/ai/usage/stats?tenant_id=t1&provider_id=ghost")
        assert response.status_code == 404

    def test_usage_stats_500_on_bad_stats(self, client, manager):
        manager.usage_stats = {"t1": {"openai": object()}}
        response = client.get("/api/ai/usage/stats")
        assert response.status_code == 500

    def test_usage_calls_filters(self, client):
        from core.llm_call_tracker import get_llm_call_tracker

        tracker = get_llm_call_tracker()
        tracker.record(provider="openai", model="gpt-4o", success=True)
        tracker.record(provider="deepseek", model="deepseek-chat", success=False, error="x")
        response = client.get(
            "/api/ai/usage/calls",
            params={"provider": "openai", "model": "gpt-4o", "limit": 1},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["calls"][0]["provider"] == "openai"
        assert data["summary"]["total_calls"] >= 1

    def test_usage_calls_500_on_tracker_failure(self, client):
        with patch(
            "core.llm_call_tracker.get_llm_call_tracker",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/ai/usage/calls")
        assert response.status_code == 500


class TestPdfEndpoints:

    def test_pdf_providers_lists(self, client, store_global_openai):
        response = client.get("/api/ai/pdf/providers")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_pdf_providers"] >= 1
        assert "pdf_ocr" in data["supported_tasks"]

    def test_pdf_optimize_with_ocr(self, client, store_global_openai):
        response = client.post(
            "/api/ai/pdf/optimize",
            json={"pdf_type": "scanned", "needs_ocr": True, "estimated_pages": 5},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["recommended_provider"]["task_type"] == "pdf_ocr"
        assert data["pdf_analysis"]["estimated_tokens"] == 2500

    def test_pdf_optimize_image_comprehension(
        self, client, store_global_openai, manager
    ):
        manager.store_api_key("deepinfra", "sk-proj-di-secret-1234567890")
        response = client.post(
            "/api/ai/pdf/optimize",
            json={"needs_image_comprehension": True},
        )
        assert response.status_code == 200
        assert response.json()["data"]["recommended_provider"]["task_type"] == \
            "image_comprehension"

    def test_pdf_optimize_no_provider_400(self, client):
        response = client.post("/api/ai/pdf/optimize", json={"needs_ocr": True})
        assert response.status_code == 400

    def test_pdf_optimize_document_processing_400(self, client, store_global_openai):
        response = client.post(
            "/api/ai/pdf/optimize",
            json={"pdf_type": "searchable", "needs_ocr": False},
        )
        assert response.status_code == 400

    def test_pdf_optimize_scenario_warnings_swallowed(
        self, client, manager, store_global_openai
    ):
        def fake_optimal(tenant_id, task_type, budget_constraint=None,
                         min_reasoning_level=1, db=None):
            if task_type == "image_comprehension":
                raise RuntimeError("hq boom")
            if budget_constraint is not None:
                raise RuntimeError("ce boom")
            return "openai"

        with patch.object(manager, "get_tenant_optimal_provider", side_effect=fake_optimal):
            response = client.post(
                "/api/ai/pdf/optimize",
                json={"needs_ocr": True, "estimated_pages": 5},
            )
        assert response.status_code == 200
        assert response.json()["data"]["alternative_scenarios"] == {}

    def test_pdf_optimize_value_error_400(self, client, manager):
        with patch.object(
            manager, "get_tenant_optimal_provider",
            side_effect=ValueError("boom"),
        ):
            response = client.post("/api/ai/pdf/optimize", json={"needs_ocr": True})
        assert response.status_code == 400

    def test_pdf_optimize_internal_error_500(self, client, manager):
        with patch.object(
            manager, "get_tenant_optimal_provider",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post("/api/ai/pdf/optimize", json={"needs_ocr": True})
        assert response.status_code == 500


class TestPricingEndpoints:
    """Pricing endpoints with a stubbed fetcher."""

    class FakeFetcher:
        def __init__(self):
            self.pricing_cache = {
                "gpt-4o-mini": {
                    "input_cost_per_token": 1.5e-7,
                    "output_cost_per_token": 6e-7,
                }
            }
            self.last_fetch = None
            self._cache_valid = True

        def _is_cache_valid(self):
            return self._cache_valid

        def get_cheapest_models(self, limit):
            return [{"model": "gpt-4o-mini", "cost": 1.5e-7}][:limit]

        def compare_providers(self):
            return {"openai": {"avg_cost": 1e-7}}

        def get_model_price(self, name):
            return self.pricing_cache.get(name)

        def get_provider_models(self, provider):
            return [dict(m, litellm_provider=provider) for m in self.pricing_cache.values()]

        def estimate_cost(self, model, input_tokens, output_tokens):
            if model in self.pricing_cache:
                return input_tokens * 1.5e-7 + output_tokens * 6e-7
            return None

    @pytest.fixture
    def fetcher(self):
        return self.FakeFetcher()

    def test_get_pricing(self, client, fetcher):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            response = client.get("/api/ai/pricing")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["model_count"] == 1

    def test_get_pricing_failure(self, client):
        with patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/ai/pricing")
        assert response.status_code == 200
        assert response.json()["success"] is False

    def test_refresh_pricing(self, client):
        with patch(
            "core.dynamic_pricing_fetcher.refresh_pricing_cache",
            new_callable=AsyncMock,
            return_value={"gpt-4o-mini": {}},
        ):
            response = client.post("/api/ai/pricing/refresh")
        assert response.status_code == 200
        assert response.json()["data"]["models_fetched"] == 1

    def test_refresh_pricing_failure(self, client):
        with patch(
            "core.dynamic_pricing_fetcher.refresh_pricing_cache",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post("/api/ai/pricing/refresh")
        assert response.json()["success"] is False

    def test_model_pricing_found(self, client, fetcher):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            response = client.get("/api/ai/pricing/model/gpt-4o-mini")
        assert response.status_code == 200
        assert response.json()["data"]["pricing"] is not None

    def test_model_pricing_not_found(self, client, fetcher):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            response = client.get("/api/ai/pricing/model/unknown-model")
        assert response.json()["success"] is False

    def test_provider_pricing(self, client, fetcher):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            response = client.get("/api/ai/pricing/provider/openai")
        assert response.status_code == 200
        assert response.json()["data"]["model_count"] == 1

    def test_estimate_cost_with_estimate(self, client, fetcher):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            response = client.post(
                "/api/ai/pricing/estimate",
                json={"model": "gpt-4o-mini", "input_tokens": 100, "output_tokens": 200},
            )
        assert response.status_code == 200
        assert response.json()["data"]["estimated_cost_usd"] == 100 * 1.5e-7 + 200 * 6e-7

    def test_estimate_cost_with_prompt(self, client, fetcher):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            response = client.post(
                "/api/ai/pricing/estimate",
                json={"model": "gpt-4o-mini", "prompt": "x" * 400},
            )
        assert response.status_code == 200
        assert response.json()["data"]["input_tokens"] == 100

    def test_estimate_cost_fallback_to_model_price(self, client, fetcher):
        fetcher.estimate_cost = lambda m, i, o: None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            response = client.post(
                "/api/ai/pricing/estimate",
                json={"model": "gpt-4o-mini", "input_tokens": 100, "output_tokens": 100},
            )
        assert response.status_code == 200
        assert response.json()["data"]["estimated_cost_usd"] == \
            100 * 1.5e-7 + 100 * 6e-7

    def test_estimate_cost_model_unknown(self, client, fetcher):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=fetcher):
            response = client.post(
                "/api/ai/pricing/estimate",
                json={"model": "ghost-model", "input_tokens": 10, "output_tokens": 10},
            )
        assert response.json()["success"] is False

    def test_model_pricing_internal_failure(self, client):
        with patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/ai/pricing/model/gpt-4o-mini")
        assert response.json()["success"] is False

    def test_provider_pricing_internal_failure(self, client):
        with patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher",
            side_effect=RuntimeError("boom"),
        ):
            response = client.get("/api/ai/pricing/provider/openai")
        assert response.json()["success"] is False

    def test_estimate_cost_internal_failure(self, client):
        with patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher",
            side_effect=RuntimeError("boom"),
        ):
            response = client.post(
                "/api/ai/pricing/estimate",
                json={"model": "gpt-4o-mini"},
            )
        assert response.json()["success"] is False


# ============================================================================
# Manager-level coverage
# ============================================================================

class TestManagerCore:

    def test_providers_initialized_with_defaults(self, manager):
        assert "openai" in manager.providers
        assert "openrouter" in manager.providers
        assert manager.get_available_providers() == list(manager.providers.keys())

    def test_config_roundtrip_persists(self, tmp_byok_paths):
        m1 = BYOKManager()
        m1.store_api_key("openai", "sk-proj-roundtrip-1234567890", key_name="rt")
        m2 = BYOKManager()
        assert m2.get_api_key("openai", key_name="rt") == "sk-proj-roundtrip-1234567890"

    def test_load_configuration_filters_unknown_fields(self, tmp_byok_paths):
        cfg, keys, _ = tmp_byok_paths
        cfg.write_text(json.dumps({
            "providers": [{
                "id": "custom", "name": "Custom", "description": "d",
                "api_key_env_var": "CUSTOM_KEY",
                "unknown_field": "should-be-dropped",
            }]
        }))
        keys.write_text(json.dumps({
            "keys": {
                "custom_default_production": {
                    "provider_id": "custom",
                    "key_name": "default",
                    "encrypted_key": "bogus",
                    "key_hash": "h",
                    "created_at": "2026-01-01T00:00:00",
                    "is_active": True,
                    "usage_count": 0,
                    "environment": "production",
                    "unknown_field": "drop",
                }
            }
        }))
        m = BYOKManager()
        assert m.providers["custom"].name == "Custom"
        assert not hasattr(m.providers["custom"], "unknown_field")
        key = m.api_keys["custom_default_production"]
        assert key.created_at.year == 2026

    def test_load_configuration_corrupted_files(self, tmp_byok_paths, caplog):
        cfg, keys, _ = tmp_byok_paths
        cfg.write_text("{not json")
        keys.write_text("{also not json")
        m = BYOKManager()
        assert "openai" in m.providers

    def test_load_configuration_last_used_date(self, tmp_byok_paths):
        cfg, keys, _ = tmp_byok_paths
        cfg.write_text(json.dumps({"providers": []}))
        keys.write_text(json.dumps({
            "keys": {
                "custom_default_production": {
                    "provider_id": "custom",
                    "key_name": "default",
                    "encrypted_key": "bogus",
                    "key_hash": "h",
                    "created_at": "2026-01-01T00:00:00",
                    "last_used": "2026-06-01T12:30:00",
                    "is_active": True,
                    "usage_count": 0,
                    "environment": "production",
                }
            }
        }))
        m = BYOKManager()
        assert m.api_keys["custom_default_production"].last_used is not None

    def test_save_configuration_handles_write_failure(self, manager, caplog):
        with patch("builtins.open", side_effect=OSError("disk full")):
            manager._save_configuration()
        assert manager.providers  # still intact

    def test_save_configuration_serializes_last_used(self, manager):
        manager.store_api_key("openai", "sk-proj-lu-1234567890")
        manager.get_api_key("openai")  # sets last_used
        manager._save_configuration()

    def test_encrypt_decrypt_roundtrip(self, manager):
        encrypted = manager.encrypt_api_key("sk-secret-value-123")
        assert encrypted != "sk-secret-value-123"
        assert manager.decrypt_api_key(encrypted) == "sk-secret-value-123"

    def test_get_fernet_raises_on_invalid_key(self, tmp_byok_paths):
        with patch.dict(os.environ, {"BYOK_ENCRYPTION_KEY": "not-a-valid-fernet-key"}):
            m = BYOKManager()
        with pytest.raises(Exception):
            m.encrypt_api_key("sk-x")

    def test_load_or_create_encryption_key(self, tmp_byok_paths):
        cfg, keys, enc = tmp_byok_paths
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BYOK_ENCRYPTION_KEY", None)
            m = BYOKManager()
        assert enc.exists()
        assert m.encryption_key
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BYOK_ENCRYPTION_KEY", None)
            m2 = BYOKManager()
        assert m2.encryption_key == m.encryption_key

    def test_load_or_create_encryption_key_unreadable_file(self, tmp_byok_paths):
        cfg, keys, enc = tmp_byok_paths
        enc.write_text("MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
        os.chmod(enc, 0o000)
        try:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("BYOK_ENCRYPTION_KEY", None)
                m = BYOKManager()
            assert m.encryption_key
        finally:
            os.chmod(enc, 0o600)

    def test_get_fernet_empty_key_raises(self, manager):
        manager.encryption_key = ""
        with pytest.raises(ValueError):
            manager.encrypt_api_key("sk-x")

    def test_store_api_key_unknown_provider(self, manager):
        with pytest.raises(ValueError):
            manager.store_api_key("ghost", "sk-proj-x-1234567890")

    def test_is_configured(self, manager):
        assert manager.is_configured("ws1", "openai") is False
        manager.store_api_key("openai", "sk-proj-cfg-1234567890")
        assert manager.is_configured("ws1", "openai") is True
        manager.api_keys["tenant_ws1_anthropic_default_production"] = APIKey(
            provider_id="anthropic", key_name="default",
            encrypted_key=manager.encrypt_api_key("sk-tenant-1234567890"),
            key_hash="h", created_at=datetime.now(),
        )
        assert manager.is_configured("ws1", "anthropic") is True

    def test_get_api_key_missing_returns_none(self, manager):
        assert manager.get_api_key("openai") is None

    def test_get_api_key_decrypt_failure_returns_none(self, manager, caplog):
        manager.api_keys["openai_default_production"] = APIKey(
            provider_id="openai", key_name="default",
            encrypted_key="garbage-ciphertext", key_hash="h",
            created_at=__import__("datetime").datetime.now(),
        )
        assert manager.get_api_key("openai") is None

    def test_track_usage_success_and_cost(self, manager):
        manager.store_api_key("openai", "sk-proj-usage-1234567890")
        manager.track_usage("t1", "openai", success=True, tokens_used=1000)
        usage = manager.get_tenant_usage("t1")["openai"]
        assert usage.total_requests == 1
        assert usage.successful_requests == 1
        assert usage.total_tokens_used == 1000
        assert usage.cost_accumulated == 1000 * manager.providers["openai"].cost_per_token

    def test_track_usage_failure_and_default_tenant(self, manager):
        manager.track_usage("", "openai", success=False)
        assert manager.usage_stats["default"]["openai"].failed_requests == 1

    def test_get_tenant_usage_empty(self, manager):
        assert manager.get_tenant_usage("nope") == {}

    def test_optimal_provider_filters(self, manager):
        manager.store_api_key("openai", "sk-proj-opt-1234567890")
        manager.store_api_key("deepseek", "sk-ds-opt-1234567890")
        best = manager.get_optimal_provider("general")
        assert best == "deepseek"
        assert manager.get_optimal_provider("computer_use") is None
        assert manager.get_optimal_provider("general", min_reasoning_level=4) is None

    def test_optimal_provider_budget(self, manager):
        manager.store_api_key("openai", "sk-proj-opt-1234567890")
        assert manager.get_optimal_provider(
            "general", budget_constraint=0.0000000001
        ) is None

    def test_optimal_provider_inactive_skipped(self, manager):
        manager.store_api_key("openai", "sk-proj-opt-1234567890")
        manager.providers["openai"].is_active = False
        assert manager.get_optimal_provider("general") is None

    def test_tenant_optimal_provider_falls_back_to_global(self, manager, db_session):
        manager.store_api_key("openai", "sk-proj-topt-1234567890")
        assert manager.get_tenant_optimal_provider(
            "tenant-x", "general", db=db_session
        ) == "openai"

    def test_tenant_optimal_provider_filters(self, manager, db_session):
        manager.store_api_key("openai", "sk-proj-topt-1234567890")
        assert manager.get_tenant_optimal_provider(
            "tenant-x", "general", min_reasoning_level=4, db=db_session
        ) is None
        manager.providers["openai"].is_active = False
        manager.store_api_key("deepseek", "sk-ds-topt-1234567890")
        assert manager.get_tenant_optimal_provider(
            "tenant-x", "general", db=db_session
        ) == "deepseek"

    def test_tenant_optimal_provider_uses_tenant_keys(self, manager, db_session):
        manager.store_tenant_api_key(
            "tenant-x", "deepseek", "sk-ds-tenant-1234567890", db=db_session
        )
        assert manager.get_tenant_optimal_provider(
            "tenant-x", "general", db=db_session
        ) == "deepseek"

    def test_get_provider_status(self, manager):
        manager.store_api_key("openai", "sk-proj-status-1234567890")
        status = manager.get_provider_status("openai")
        assert status["status"] == "active"
        assert status["has_api_keys"] is True
        assert status["provider"]["id"] == "openai"

    def test_get_provider_status_unknown_raises(self, manager):
        with pytest.raises(ValueError):
            manager.get_provider_status("ghost")

    def test_has_tenant_keys_db(self, manager, db_session):
        from core.models import Tenant

        tenant = Tenant(
            name="Key Tenant", subdomain="key-tenant",
            edition="personal", ai_mode="byok",
        )
        db_session.add(tenant)
        db_session.commit()
        assert manager.has_tenant_keys(tenant.id, db=db_session) is False
        manager.store_tenant_api_key(
            tenant.id, "openai", "sk-proj-hk-1234567890", db=db_session
        )
        assert manager.has_tenant_keys(tenant.id, db=db_session) is True

    def test_has_tenant_keys_memory_prefix(self, manager):
        manager.api_keys["tenant_x_ghost_default_production"] = APIKey(
            provider_id="ghost", key_name="default",
            encrypted_key=manager.encrypt_api_key("sk-proj-x-1234567890"),
            key_hash="h", created_at=__import__("datetime").datetime.now(),
            tenant_id="x",
        )
        assert manager.has_tenant_keys("x") is True

    def test_get_tenant_provider_status_db_setting(self, manager, db_session):
        from core.models import Tenant

        tenant = Tenant(
            name="Status Tenant", subdomain="status-tenant",
            edition="personal", ai_mode="byok",
        )
        db_session.add(tenant)
        db_session.commit()
        manager.store_tenant_api_key(
            tenant.id, "openai", "sk-proj-ts-1234567890", db=db_session
        )
        status = manager.get_tenant_provider_status(
            tenant.id, "openai", db=db_session
        )
        assert status["has_tenant_key"] is True
        assert status["status"] == "active"

    def test_get_tenant_provider_status_unknown_raises(self, manager, db_session):
        with pytest.raises(ValueError):
            manager.get_tenant_provider_status("x", "ghost", db=db_session)

    def test_get_tenant_api_key_decrypt_failure(self, manager):
        manager.api_keys["tenant_x_openai_default_production"] = APIKey(
            provider_id="openai", key_name="default",
            encrypted_key="garbage", key_hash="h",
            created_at=__import__("datetime").datetime.now(),
            tenant_id="x",
        )
        assert manager.get_tenant_api_key("x", "openai") is None

    def test_store_tenant_api_key_without_db(self, manager):
        key_id = manager.store_tenant_api_key("t9", "openai", "sk-proj-ndb-1234567890")
        assert key_id == "tenant_t9_openai_default_production"
        assert manager.get_tenant_api_key("t9", "openai") == "sk-proj-ndb-1234567890"

    def test_store_tenant_api_key_unknown_provider(self, manager):
        with pytest.raises(ValueError):
            manager.store_tenant_api_key("t9", "ghost", "sk-proj-x-1234567890")

    def test_store_tenant_api_key_update_existing_setting(
        self, manager, db_session
    ):
        from core.models import Tenant, TenantSetting

        tenant = Tenant(
            name="Update Tenant", subdomain="update-tenant",
            edition="personal", ai_mode="byok",
        )
        db_session.add(tenant)
        db_session.commit()
        manager.store_tenant_api_key(
            tenant.id, "openai", "sk-proj-first-1234567890", db=db_session
        )
        manager.store_tenant_api_key(
            tenant.id, "openai", "sk-proj-second-1234567890", db=db_session
        )
        setting = db_session.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant.id,
            TenantSetting.setting_key == "OPENAI_API_KEY",
        ).first()
        assert setting is not None
        assert "second" not in setting.setting_value
        assert manager.get_tenant_api_key(
            tenant.id, "openai", db=db_session
        ) == "sk-proj-second-1234567890"

    def test_get_tenant_api_key_legacy_plaintext_fallback(
        self, manager, db_session
    ):
        from core.models import Tenant, TenantSetting

        tenant = Tenant(
            name="Legacy Tenant", subdomain="legacy-tenant",
            edition="personal", ai_mode="byok",
        )
        db_session.add(tenant)
        db_session.commit()
        setting = TenantSetting(
            tenant_id=tenant.id,
            setting_key="OPENAI_API_KEY",
            setting_value="sk-legacy-plaintext-1234567890",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(setting)
        db_session.commit()
        assert manager.get_tenant_api_key(
            tenant.id, "openai", db=db_session
        ) == "sk-legacy-plaintext-1234567890"

    def test_singleton_get_byok_manager(self, tmp_byok_paths):
        original = byok_routes._byok_manager
        byok_routes._byok_manager = None
        try:
            m = byok_routes.get_byok_manager()
            assert isinstance(m, BYOKManager)
            assert byok_routes.get_byok_manager() is m
        finally:
            byok_routes._byok_manager = original
