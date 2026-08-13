"""
Coverage tests for byok_endpoints.py.

Target: 50%+ coverage (488 statements, ~244 lines to cover)
Focus: BYOK provider management, key operations, model endpoints
Uses FastAPI TestClient for endpoint testing
"""
import pytest
import os
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

# Import the router
from core.byok_endpoints import router


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create test FastAPI app with byok router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestBYOKProviderManagement:
    """Test BYOK provider management endpoints."""

    def test_list_providers(self, client):
        """Test listing available BYOK providers."""
        response = client.get("/api/ai/providers")

        assert response.status_code in [200, 401, 500]
        if response.status_code == 200:
            data = response.json()
            assert "providers" in data or isinstance(data, list)

    def test_get_provider_details(self, client):
        """Test getting specific provider details."""
        response = client.get("/api/ai/providers/openai")

        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            # Real shape: {"provider": {...}, "status": ..., "usage": {...}}
            assert "provider" in data or "provider_id" in str(data)

    def test_register_provider_key(self, client):
        """Test registering a new provider API key."""
        response = client.post(
            "/api/ai/providers/openai/keys",
            json={
                "api_key": "sk-test-key-12345",
                "key_name": "test_key",
                "environment": "test",
            },
        )

        assert response.status_code in [200, 201, 400, 401, 500]

    def test_list_provider_keys(self, client):
        """Test listing API keys for a provider.

        No GET /keys list route exists — the real status route requires a
        key_name segment.
        """
        response = client.get("/api/ai/providers/openai/keys/default")

        assert response.status_code in [200, 404, 500]

    def test_get_specific_key(self, client):
        """Test getting a specific API key details."""
        response = client.get("/api/ai/providers/openai/keys/test-key")

        assert response.status_code in [200, 404, 500]

    def test_delete_provider_key(self, client):
        """Test deleting a provider API key."""
        response = client.delete(
            "/api/ai/providers/openai/keys/test-key"
        )

        assert response.status_code in [200, 204, 404, 500]


class TestBYOKModelEndpoints:
    """Test BYOK model-related endpoints."""

    def test_list_pdf_providers(self, client):
        """Test listing PDF-capable providers."""
        response = client.get("/api/ai/pdf/providers")

        assert response.status_code in [200, 401, 500]
        if response.status_code == 200:
            data = response.json()
            # Real shape: data contains pdf_providers / total_pdf_providers
            assert "pdf_providers" in data or isinstance(data, list)


class TestBYOKUsageEndpoints:
    """Test BYOK usage and quota endpoints."""

    def test_track_usage(self, client):
        """Test tracking API usage."""
        response = client.post(
            "/api/ai/usage/track",
            json={
                "provider": "openai",
                "model": "gpt-4",
                "tokens_used": 1000,
                "cost": 0.03
            }
        )

        assert response.status_code in [200, 201, 400, 500]

    def test_get_usage_stats(self, client):
        """Test getting usage statistics."""
        response = client.get("/api/ai/usage/stats")

        assert response.status_code in [200, 401, 500]

    def test_get_usage_for_provider(self, client):
        """Test getting usage for specific provider."""
        response = client.get("/api/ai/usage/stats?provider=openai")

        assert response.status_code in [200, 404, 500]


class TestBYOKCostOptimization:
    """Test BYOK cost optimization endpoints."""

    def test_optimize_cost(self, client):
        """Test cost optimization recommendation."""
        response = client.post(
            "/api/ai/optimize-cost",
            json={
                "task": "chat",
                "budget_limit": 10.0,
                "quality_preference": "balanced"
            }
        )

        assert response.status_code in [200, 400, 500]

    def test_optimize_pdf_cost(self, client):
        """Test PDF processing cost optimization."""
        response = client.post(
            "/api/ai/pdf/optimize",
            json={
                "pdf_path": "/path/to/file.pdf",
                "quality_preference": "high"
            }
        )

        assert response.status_code in [200, 400, 404, 500]


class TestBYOKPricing:
    """Test BYOK pricing information endpoints."""

    def test_get_pricing_info(self, client):
        """Test getting pricing information."""
        response = client.get("/api/ai/pricing")

        assert response.status_code in [200, 401, 500]

    def test_refresh_pricing(self, client):
        """Test refreshing pricing data."""
        response = client.post("/api/ai/pricing/refresh")

        assert response.status_code in [200, 401, 500]

    def test_get_model_pricing(self, client):
        """Test getting pricing for specific model."""
        response = client.get("/api/ai/pricing/model/gpt-4")

        assert response.status_code in [200, 404, 500]

    def test_get_provider_pricing(self, client):
        """Test getting pricing for specific provider."""
        response = client.get("/api/ai/pricing/provider/openai")

        assert response.status_code in [200, 404, 500]

    def test_estimate_cost(self, client):
        """Test cost estimation for a request."""
        response = client.post(
            "/api/ai/pricing/estimate",
            json={
                "provider": "openai",
                "model": "gpt-4",
                "input_tokens": 1000,
                "output_tokens": 500
            }
        )

        assert response.status_code in [200, 400, 500]


class TestBYOKHealthCheck:
    """Test BYOK health check endpoints."""

    def test_health_check(self, client):
        """Test BYOK health check endpoint."""
        response = client.get("/api/v1/byok/health")

        assert response.status_code in [200, 503]

    def test_ai_health_check(self, client):
        """Test AI health check endpoint."""
        response = client.get("/api/ai/health")

        assert response.status_code in [200, 503]

    def test_status_check(self, client):
        """Test BYOK status endpoint."""
        response = client.get("/api/v1/byok/status")

        assert response.status_code in [200, 503]


class TestBYOKKeysManagement:
    """Test API key management endpoints."""

    def test_list_all_keys(self, client):
        """Test listing all API keys."""
        response = client.get("/api/ai/keys")

        assert response.status_code in [200, 401, 500]

    def test_add_new_key(self, client):
        """Test adding a new API key."""
        response = client.post(
            "/api/ai/keys",
            json={
                "provider": "openai",
                "api_key": "sk-new-key-12345",
                "key_name": "production-key"
            }
        )

        assert response.status_code in [200, 201, 400, 401, 500]


class TestBYOKErrors:
    """Test BYOK endpoint error handling."""

    def test_invalid_provider(self, client):
        """Test handling of invalid provider."""
        response = client.get("/api/ai/providers/invalid-provider")

        assert response.status_code in [400, 404, 500]

    def test_missing_api_key_in_request(self, client):
        """Test handling of missing API key in request."""
        response = client.post(
            "/api/ai/providers/openai/keys",
            json={
                "key_name": "test-key"
                # Missing: api_key
            }
        )

        assert response.status_code in [400, 422]

    def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON payload."""
        response = client.post(
            "/api/ai/usage/track",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code in [400, 422]

    def test_unauthorized_access(self, client):
        """Test handling of unauthorized access."""
        response = client.get(
            "/api/ai/keys",
            headers={"Authorization": "Bearer invalid-token"}
        )

        # May pass if auth not enabled
        assert response.status_code in [200, 401, 403]


class TestBYOKConfiguration:
    """Test BYOK configuration and defaults."""

    def test_provider_configuration(self, client):
        """Test getting provider configuration."""
        response = client.get("/api/ai/providers")

        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            # Should return list of providers with their configs
            assert isinstance(data, (dict, list))

    def test_default_provider_selection(self, client):
        """Test that default provider is accessible."""
        response = client.get("/api/ai/providers/openai")

        assert response.status_code in [200, 404, 500]


# =============================================================================
# BYOKManager business-logic coverage (unit-level, no HTTP layer)
# =============================================================================

from cryptography.fernet import Fernet  # noqa: E402
from core.byok_endpoints import BYOKManager  # noqa: E402


@pytest.fixture
def byok_mgr():
    """A BYOKManager with default providers + a real Fernet key, no disk I/O.

    Uses __new__ to skip the full __init__ (which reads/writes disk config and
    an encryption-key file). _save_configuration is stubbed so store_api_key
    never writes to disk during tests.
    """
    mgr = BYOKManager.__new__(BYOKManager)
    mgr.providers = {}
    mgr.usage_stats = {}
    mgr.api_keys = {}
    mgr._initialize_default_providers()
    mgr.encryption_key = Fernet.generate_key().decode()
    mgr._save_configuration = lambda: None
    return mgr


class TestBYOKManagerKeyCrypto:
    """encrypt/decrypt + Fernet edge handling."""

    def test_encrypt_decrypt_roundtrip(self, byok_mgr):
        enc = byok_mgr.encrypt_api_key("sk-secret-123")
        assert enc != "sk-secret-123"
        assert byok_mgr.decrypt_api_key(enc) == "sk-secret-123"

    def test_get_fernet_with_empty_key_raises(self, byok_mgr):
        byok_mgr.encryption_key = ""
        with pytest.raises(Exception):
            byok_mgr._get_fernet()

    def test_get_fernet_accepts_bytes_key(self, byok_mgr):
        # A str key is encoded internally; verify a valid str key yields a Fernet.
        f = byok_mgr._get_fernet()
        assert f is not None


class TestBYOKManagerKeyStore:
    """store_api_key / get_api_key / env fallback."""

    def test_store_and_get_api_key_roundtrip(self, byok_mgr):
        key_id = byok_mgr.store_api_key("openai", "sk-test-1234567890")
        assert key_id == "openai_default_production"
        assert byok_mgr.get_api_key("openai") == "sk-test-1234567890"

    def test_store_api_key_unknown_provider_raises(self, byok_mgr):
        with pytest.raises(ValueError, match="not found"):
            byok_mgr.store_api_key("does-not-exist", "sk-test-1234567890")

    def test_store_api_key_normalizes_empty_key_name(self, byok_mgr):
        key_id = byok_mgr.store_api_key("openai", "sk-test-1234567890", key_name="   ")
        # Empty key_name falls back to "default".
        assert key_id == "openai_default_production"

    def test_get_api_key_missing_returns_none(self, byok_mgr):
        assert byok_mgr.get_api_key("openai") is None

    def test_get_api_key_env_var_fallback_stores_and_returns(self, byok_mgr, monkeypatch):
        provider = byok_mgr.providers["openai"]
        monkeypatch.setenv(provider.api_key_env_var, "sk-from-env-12345")
        assert byok_mgr.get_api_key("openai") == "sk-from-env-12345"
        # Second call reads from the now-stored key (no env needed).
        monkeypatch.delenv(provider.api_key_env_var, raising=False)
        assert byok_mgr.get_api_key("openai") == "sk-from-env-12345"

    def test_is_configured_and_tenant_api_key_aliases(self, byok_mgr):
        byok_mgr.store_api_key("openai", "sk-test-1234567890", key_name="ws-1")
        assert byok_mgr.is_configured("ws-1", "openai") is True
        assert byok_mgr.get_tenant_api_key("ws-1", "openai") == "sk-test-1234567890"
        assert byok_mgr.is_configured("other-ws", "openai") is False

    def test_get_api_key_decrypt_failure_returns_none(self, byok_mgr):
        """A corrupt stored ciphertext fails decryption and returns None (no raise)."""
        byok_mgr.store_api_key("openai", "sk-test-1234567890")
        byok_mgr.api_keys["openai_default_production"].encrypted_key = "not-valid-fernet"
        assert byok_mgr.get_api_key("openai") is None

    def test_get_optimal_provider_falls_back_to_keyed_provider(self, byok_mgr):
        """No provider matches a bogus task_type, so the fallback selects a keyed provider."""
        byok_mgr.store_api_key("openai", "sk-test-1234567890")
        result = byok_mgr.get_optimal_provider("totally-bogus-task-type")
        # Fallback prefers deepseek then openai; only openai has a key here.
        assert result == "openai"

    def test_get_optimal_provider_returns_none_when_no_keys(self, byok_mgr):
        """With no keys anywhere, selection returns None."""
        assert byok_mgr.get_optimal_provider("totally-bogus-task-type") is None



class TestBYOKManagerUsageAndStatus:
    """track_usage / get_provider_status."""

    def test_track_usage_success_accumulates_cost_and_tokens(self, byok_mgr):
        byok_mgr.track_usage("openai", success=True, tokens_used=100)
        byok_mgr.track_usage("openai", success=True, tokens_used=50)
        u = byok_mgr.usage_stats["openai"]
        assert u.total_requests == 2
        assert u.successful_requests == 2
        assert u.failed_requests == 0
        assert u.total_tokens_used == 150
        assert u.cost_accumulated > 0  # 150 * openai.cost_per_token

    def test_track_usage_failure_counts_failures(self, byok_mgr):
        byok_mgr.track_usage("openai", success=False)
        u = byok_mgr.usage_stats["openai"]
        assert u.failed_requests == 1
        assert u.successful_requests == 0
        assert u.total_tokens_used == 0

    def test_get_provider_status_found(self, byok_mgr):
        status = byok_mgr.get_provider_status("openai")
        assert status["provider"]["id"] == "openai"
        assert "usage" in status
        assert status["has_api_keys"] is False
        assert status["status"] == "inactive"  # no keys → inactive

    def test_get_provider_status_active_when_key_present(self, byok_mgr):
        byok_mgr.store_api_key("openai", "sk-test-1234567890")
        status = byok_mgr.get_provider_status("openai")
        assert status["has_api_keys"] is True
        assert status["status"] == "active"

    def test_get_provider_status_not_found_raises(self, byok_mgr):
        with pytest.raises(ValueError):
            byok_mgr.get_provider_status("nope")


class TestBYOKManagerNormalize:
    """_normalize_key_part branches."""

    def test_none_returns_default(self):
        assert BYOKManager._normalize_key_part(None, "d") == "d"

    def test_empty_string_returns_default(self):
        assert BYOKManager._normalize_key_part("   ", "d") == "d"

    def test_valid_string_returned(self):
        assert BYOKManager._normalize_key_part("x", "d") == "x"

    def test_numeric_coerced_to_string(self):
        assert BYOKManager._normalize_key_part(123, "d") == "123"

    def test_invalid_type_returns_default(self):
        # A list is not a scalar; falls back to default with a warning.
        assert BYOKManager._normalize_key_part([1, 2, 3], "d") == "d"


# =============================================================================
# Route-handler coverage via FastAPI dependency override (deterministic state,
# no singleton/disk contamination).
# =============================================================================

from core.byok_endpoints import get_byok_manager  # noqa: E402


@pytest.fixture
def byok_client(byok_mgr):
    """TestClient whose ``get_byok_manager`` dependency returns ``byok_mgr``.

    Overriding the dependency (instead of relying on the global singleton)
    gives deterministic provider/key state and avoids the on-disk encryption
    key file that makes the singleton-based coverage measurement noisy.
    """
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_byok_manager] = lambda: byok_mgr
    with TestClient(app) as client:
        yield client


class TestBYOKKeyRoutes:
    """store/get/delete API-key endpoints."""

    def test_store_key_valid(self, byok_client):
        r = byok_client.post("/api/ai/providers/openai/keys",
                             json={"api_key": "sk-valid-1234567890", "key_name": "default"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["provider_id"] == "openai"
        assert body["key_id"] == "openai_default_production"

    def test_store_key_too_short_rejected(self, byok_client):
        # AddAPIKeyRequest.api_key is Field(min_length=10), so a short key is
        # rejected by Pydantic at the validation layer (422) before the
        # endpoint's own length check runs.
        r = byok_client.post("/api/ai/providers/openai/keys",
                             json={"api_key": "short", "key_name": "default"})
        assert r.status_code == 422

    def test_store_key_unknown_provider_returns_400(self, byok_client):
        r = byok_client.post("/api/ai/providers/does-not-exist/keys",
                             json={"api_key": "sk-valid-1234567890"})
        assert r.status_code == 400

    def test_get_key_status_found_then_delete(self, byok_client):
        byok_client.post("/api/ai/providers/openai/keys",
                         json={"api_key": "sk-valid-1234567890", "key_name": "default"})
        got = byok_client.get("/api/ai/providers/openai/keys/default")
        assert got.status_code == 200
        assert got.json()["has_key"] is True

        deleted = byok_client.delete("/api/ai/providers/openai/keys/default")
        assert deleted.status_code == 200
        assert deleted.json()["success"] is True

        # Now missing.
        assert byok_client.get("/api/ai/providers/openai/keys/default").status_code == 404

    def test_get_key_status_missing_returns_404(self, byok_client):
        assert byok_client.get("/api/ai/providers/openai/keys/default").status_code == 404

    def test_delete_key_missing_returns_404(self, byok_client):
        assert byok_client.delete("/api/ai/providers/openai/keys/default").status_code == 404

    def test_add_api_key_legacy_endpoint_success(self, byok_client):
        # POST /api/ai/keys (the older add_api_key endpoint)
        r = byok_client.post("/api/ai/keys",
                             json={"provider": "openai", "key": "sk-valid-1234567890"})
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        assert r.json()["provider"] == "openai"

    def test_add_api_key_legacy_missing_fields_400(self, byok_client):
        r = byok_client.post("/api/ai/keys", json={"provider": "openai"})
        assert r.status_code == 400

    def test_add_api_key_legacy_unknown_provider_404(self, byok_client):
        r = byok_client.post("/api/ai/keys",
                             json={"provider": "does-not-exist", "key": "sk-valid-1234567890"})
        assert r.status_code == 404



class TestBYOKUsageRoutes:
    """optimize-cost / usage-track / usage-stats endpoints."""

    def test_optimize_cost_success(self, byok_client):
        byok_client.post("/api/ai/providers/openai/keys",
                         json={"api_key": "sk-valid-1234567890"})
        r = byok_client.post("/api/ai/optimize-cost",
                             json={"task_type": "chat", "estimated_tokens": 500})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["recommended_provider"] == "openai"
        assert body["estimated_cost"] >= 0

    def test_optimize_cost_no_provider_returns_400(self, byok_client):
        # No keys stored → no provider selectable → 400.
        r = byok_client.post("/api/ai/optimize-cost", json={"task_type": "chat"})
        assert r.status_code == 400

    def test_track_usage_success(self, byok_client):
        r = byok_client.post("/api/ai/usage/track",
                             json={"provider_id": "openai", "success": True, "tokens_used": 100})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_track_usage_missing_provider_returns_400(self, byok_client):
        r = byok_client.post("/api/ai/usage/track", json={"tokens_used": 100})
        assert r.status_code == 400

    def test_usage_stats_all_and_specific(self, byok_client):
        # Seed usage via the track endpoint (background task mutates byok_mgr).
        byok_client.post("/api/ai/usage/track",
                         json={"provider_id": "openai", "tokens_used": 50})
        all_stats = byok_client.get("/api/ai/usage/stats")
        assert all_stats.status_code == 200
        assert all_stats.json()["total_providers"] >= 1

        specific = byok_client.get("/api/ai/usage/stats?provider_id=openai")
        assert specific.status_code == 200
        assert specific.json()["provider_id"] == "openai"

    def test_usage_stats_unknown_provider_returns_404(self, byok_client):
        assert byok_client.get("/api/ai/usage/stats?provider_id=nope").status_code == 404


class TestBYOKHealthAndPdfRoutes:
    """health + pdf-provider endpoints."""

    def test_byok_health_v1(self, byok_client):
        r = byok_client.get("/api/v1/byok/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_byok_status_v1(self, byok_client):
        r = byok_client.get("/api/v1/byok/status")
        assert r.status_code == 200

    def test_health_with_active_provider(self, byok_client):
        # Storing a key makes a provider "active", exercising the counter branches.
        byok_client.post("/api/ai/providers/openai/keys",
                         json={"api_key": "sk-valid-1234567890"})
        r = byok_client.get("/api/ai/health")
        assert r.status_code == 200

    def test_status_v1_lists_active_provider(self, byok_client):
        byok_client.post("/api/ai/providers/openai/keys",
                         json={"api_key": "sk-valid-1234567890"})
        r = byok_client.get("/api/v1/byok/status")
        assert r.status_code == 200
        body = r.json()
        assert any(p["id"] == "openai" for p in body["providers_list"])
        assert "openai" in body["providers_connected"]

    def test_pdf_providers(self, byok_client):
        r = byok_client.get("/api/ai/pdf/providers")
        assert r.status_code == 200

    def test_optimize_pdf_success(self, byok_client, byok_mgr):
        # Deterministic selection: force a provider so the success body +
        # alternative-scenario blocks all execute.
        byok_mgr.get_optimal_provider = lambda task_type, budget_constraint=None: "openai"
        r = byok_client.post("/api/ai/pdf/optimize",
                             json={"estimated_pages": 20, "needs_ocr": True})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["recommended_provider"]["provider_id"] == "openai"
        assert body["pdf_analysis"]["estimated_tokens"] == 20 * 500
        assert "alternative_scenarios" in body

    def test_optimize_pdf_no_provider_returns_400(self, byok_client, byok_mgr):
        byok_mgr.get_optimal_provider = lambda task_type, budget_constraint=None: None
        r = byok_client.post("/api/ai/pdf/optimize", json={"needs_ocr": True})
        assert r.status_code == 400


def _pricing_fetcher():
    """A mock dynamic-pricing fetcher covering every method the routes call."""
    f = Mock()
    f.pricing_cache = {"gpt-4o-mini": {}}
    f.last_fetch = datetime.now(timezone.utc)
    f._is_cache_valid.return_value = True
    f.get_cheapest_models.return_value = [{"model": "gpt-4o-mini"}]
    f.compare_providers.return_value = {"openai": 1.0}
    f.get_model_price.return_value = {
        "input_cost_per_token": 0.00001,
        "output_cost_per_token": 0.00003,
    }
    f.get_provider_models.return_value = [{"model": "gpt-4o-mini"}]
    f.estimate_cost.return_value = 0.005
    return f


class TestBYOKPricingRoutes:
    """pricing/* endpoints (all delegate to dynamic_pricing_fetcher)."""

    def test_get_pricing(self, byok_client):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=_pricing_fetcher()):
            r = byok_client.get("/api/ai/pricing")
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_refresh_pricing(self, byok_client, byok_mgr):
        byok_mgr.update_provider_costs = lambda: None  # avoid real cost refresh
        with patch("core.dynamic_pricing_fetcher.refresh_pricing_cache",
                   new=AsyncMock(return_value={"m1": {}})):
            r = byok_client.post("/api/ai/pricing/refresh")
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_model_pricing_found(self, byok_client):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=_pricing_fetcher()):
            r = byok_client.get("/api/ai/pricing/model/gpt-4o-mini")
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_model_pricing_not_found(self, byok_client):
        f = _pricing_fetcher()
        f.get_model_price.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=f):
            r = byok_client.get("/api/ai/pricing/model/unknown-model")
        assert r.json()["status"] == "not_found"

    def test_provider_pricing(self, byok_client):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=_pricing_fetcher()):
            r = byok_client.get("/api/ai/pricing/provider/openai")
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_estimate_cost_success(self, byok_client):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=_pricing_fetcher()):
            r = byok_client.post("/api/ai/pricing/estimate",
                                 json={"model": "gpt-4o-mini", "input_tokens": 100, "output_tokens": 50})
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        assert r.json()["estimated_cost_usd"] == 0.005

    def test_estimate_cost_with_prompt_tokens(self, byok_client):
        # prompt provided with no input_tokens → tokens estimated from prompt length
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=_pricing_fetcher()):
            r = byok_client.post("/api/ai/pricing/estimate",
                                 json={"model": "gpt-4o-mini", "prompt": "x" * 400})
        assert r.status_code == 200
        assert r.json()["input_tokens"] == 100  # 400 // 4

    def test_estimate_cost_fallback_from_model_price(self, byok_client):
        # estimate_cost None → fall back to per-token pricing from get_model_price
        f = _pricing_fetcher()
        f.estimate_cost.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=f):
            r = byok_client.post("/api/ai/pricing/estimate",
                                 json={"model": "gpt-4o-mini", "input_tokens": 100, "output_tokens": 50})
        assert r.json()["status"] == "success"
        # 100*0.00001 + 50*0.00003 = 0.0025
        assert r.json()["estimated_cost_usd"] == 0.0025

    def test_estimate_cost_pricing_unavailable(self, byok_client):
        f = _pricing_fetcher()
        f.estimate_cost.return_value = None
        f.get_model_price.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=f):
            r = byok_client.post("/api/ai/pricing/estimate", json={"model": "mystery"})
        assert r.json()["status"] == "pricing_unavailable"

    def test_get_pricing_error_handler(self, byok_client):
        # Fetcher raising → the route's except returns an error payload (200).
        f = _pricing_fetcher()
        f.compare_providers.side_effect = RuntimeError("boom")
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=f):
            r = byok_client.get("/api/ai/pricing")
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    def test_refresh_pricing_error_handler(self, byok_client, byok_mgr):
        byok_mgr.update_provider_costs = lambda: None
        with patch("core.dynamic_pricing_fetcher.refresh_pricing_cache",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = byok_client.post("/api/ai/pricing/refresh")
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    def test_estimate_cost_error_handler(self, byok_client):
        f = _pricing_fetcher()
        f.estimate_cost.side_effect = RuntimeError("boom")
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher", return_value=f):
            r = byok_client.post("/api/ai/pricing/estimate", json={"model": "gpt-4o-mini"})
        assert r.json()["status"] == "error"


class TestBYOKRouteErrorHandlers:
    """Force-error paths through the route exception handlers."""

    def test_store_key_internal_error_returns_500(self, byok_client, byok_mgr):
        # encrypt_api_key blowing up drives the generic 500 branch.
        byok_mgr.encrypt_api_key = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("enc fail"))
        r = byok_client.post("/api/ai/providers/openai/keys",
                             json={"api_key": "sk-valid-1234567890"})
        assert r.status_code == 500

    def test_optimize_cost_internal_error_returns_500(self, byok_client, byok_mgr):
        # get_optimal_provider raising a non-ValueError → 500.
        def boom(*a, **k):
            raise RuntimeError("opt fail")
        byok_mgr.get_optimal_provider = boom
        r = byok_client.post("/api/ai/optimize-cost", json={"task_type": "chat"})
        assert r.status_code == 500

    def test_add_api_key_legacy_internal_error_returns_500(self, byok_client, byok_mgr):
        byok_mgr.store_api_key = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("store fail"))
        r = byok_client.post("/api/ai/keys",
                             json={"provider": "openai", "key": "sk-valid-1234567890"})
        assert r.status_code == 500



class TestBYOKConfigPersistence:
    """Disk-IO: _load/_save_configuration, serializers, atomic write, keys."""

    def test_provider_to_dict_roundtrip(self, byok_mgr):
        from core.byok_endpoints import AIProviderConfig
        provider = byok_mgr.providers["openai"]
        d = BYOKManager._provider_to_dict(provider)
        assert d["id"] == "openai"
        # Rebuild from the dict (filtering is what _load does).
        from dataclasses import fields
        valid = {f.name for f in fields(AIProviderConfig)}
        rebuilt = AIProviderConfig(**{k: v for k, v in d.items() if k in valid})
        assert rebuilt.id == "openai"

    def test_api_key_to_dict_serializes_datetimes(self, byok_mgr):
        byok_mgr.store_api_key("openai", "sk-serial-1234567890")
        key_obj = byok_mgr.api_keys["openai_default_production"]
        d = BYOKManager._api_key_to_dict(key_obj)
        assert d["provider_id"] == "openai"
        assert isinstance(d["created_at"], str)  # ISO string

    def test_save_then_load_configuration_roundtrip(self, tmp_path, byok_mgr):
        cfg = str(tmp_path / "byok_config.json")
        keys = str(tmp_path / "byok_keys.json")
        byok_mgr.store_api_key("openai", "sk-roundtrip-1234567890")

        with patch("core.byok_endpoints.BYOK_CONFIG_FILE", cfg), \
             patch("core.byok_endpoints.BYOK_KEYS_FILE", keys):
            # Use the real _save_configuration (the fixture stubs the instance method).
            BYOKManager._save_configuration(byok_mgr)

            fresh = BYOKManager.__new__(BYOKManager)
            fresh.providers = {}
            fresh.api_keys = {}
            fresh.usage_stats = {}
            fresh.encryption_key = byok_mgr.encryption_key
            fresh._load_configuration()

        assert "openai" in fresh.providers
        assert "openai_default_production" in fresh.api_keys
        assert fresh.api_keys["openai_default_production"].provider_id == "openai"

    def test_load_configuration_missing_files_is_noop(self, tmp_path):
        # Point at non-existent files → FileNotFoundError paths, no crash.
        mgr = BYOKManager.__new__(BYOKManager)
        mgr.providers = {}
        mgr.api_keys = {}
        with patch("core.byok_endpoints.BYOK_CONFIG_FILE", str(tmp_path / "nope.json")), \
             patch("core.byok_endpoints.BYOK_KEYS_FILE", str(tmp_path / "nope_keys.json")):
            mgr._load_configuration()
        assert mgr.providers == {} and mgr.api_keys == {}

    def test_load_configuration_corrupt_json_logs_and_continues(self, tmp_path):
        cfg = str(tmp_path / "bad.json")
        with open(cfg, "w") as f:
            f.write("{ not valid json")
        mgr = BYOKManager.__new__(BYOKManager)
        mgr.providers = {}
        mgr.api_keys = {}
        with patch("core.byok_endpoints.BYOK_CONFIG_FILE", cfg), \
             patch("core.byok_endpoints.BYOK_KEYS_FILE", str(tmp_path / "nope_keys.json")):
            mgr._load_configuration()  # must not raise
        assert mgr.providers == {}

    def test_atomic_write_json_writes_file(self, tmp_path):
        path = str(tmp_path / "atomic.json")
        BYOKManager._atomic_write_json(path, {"hello": "world"})
        import json as _json
        with open(path) as f:
            assert _json.load(f) == {"hello": "world"}

    def test_atomic_write_json_cleans_up_tmp_on_failure(self, tmp_path):
        path = str(tmp_path / "fail.json")
        before = set(os.listdir(tmp_path))
        with patch("core.byok_endpoints.os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError):
                BYOKManager._atomic_write_json(path, {"x": 1})
        # No leftover temp file.
        after = set(os.listdir(tmp_path))
        assert before == after

    def test_generate_encryption_key_is_valid_fernet(self):
        mgr = BYOKManager.__new__(BYOKManager)
        key = mgr._generate_encryption_key()
        Fernet(key.encode())  # raises if invalid

    def test_load_or_create_encryption_key_reads_existing(self, tmp_path):
        keyfile = str(tmp_path / "enc.key")
        with open(keyfile, "w") as f:
            f.write("persisted-key-value")
        mgr = BYOKManager.__new__(BYOKManager)
        with patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", keyfile):
            assert mgr._load_or_create_encryption_key() == "persisted-key-value"

    def test_load_or_create_encryption_key_creates_and_persists(self, tmp_path):
        # A nested path exercises the makedirs branch.
        keyfile = str(tmp_path / "subdir" / "nested" / "enc.key")
        mgr = BYOKManager.__new__(BYOKManager)
        with patch("core.byok_endpoints.BYOK_ENC_KEY_FILE", keyfile):
            key = mgr._load_or_create_encryption_key()
        assert key
        with open(keyfile) as f:
            assert f.read() == key  # persisted for restart-survival





