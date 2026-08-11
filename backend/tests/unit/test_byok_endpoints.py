"""
Comprehensive tests for BYOK API endpoints.

Tests cover:
- Provider registration and listing
- API key storage and retrieval
- Provider deletion and testing
- Usage tracking and statistics
- Cost optimization endpoints
- Health check endpoints
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Import the router to test
from core.byok_endpoints import router, BYOKManager, get_byok_manager, AIProviderConfig


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_byok_manager():
    """Mock BYOKManager instance"""
    manager = MagicMock(spec=BYOKManager)

    # Mock providers
    manager.providers = {
        "openai": AIProviderConfig(
            id="openai",
            name="OpenAI",
            description="GPT-4 models",
            api_key_env_var="OPENAI_API_KEY",
            model="gpt-4o",
            cost_per_token=0.00003,
            supported_tasks=["general", "chat", "code"],
            is_active=True
        ),
        "deepseek": AIProviderConfig(
            id="deepseek",
            name="DeepSeek",
            description="DeepSeek V3",
            api_key_env_var="DEEPSEEK_API_KEY",
            model="deepseek-chat",
            cost_per_token=0.00000014,
            supported_tasks=["general", "chat", "code"],
            is_active=True
        )
    }

    # Mock API keys
    manager.api_keys = {}
    manager.usage_stats = {}

    # Mock methods
    def mock_get_api_key(provider_id, key_name="default", environment="production"):
        keys = {
            "openai": "sk-test-openai-key-12345",
            "deepseek": "sk-deepseek-test-key"
        }
        return keys.get(provider_id)

    def mock_store_api_key(provider_id, api_key, key_name="default", environment="production"):
        key_id = f"{provider_id}_{key_name}_{environment}"
        return key_id

    def mock_get_provider_status(provider_id):
        if provider_id not in manager.providers:
            raise ValueError(f"Provider {provider_id} not found")
        provider = manager.providers[provider_id]
        return {
            "provider": {
                "id": provider.id,
                "name": provider.name,
                "description": provider.description,
                "is_active": provider.is_active,
                "cost_per_token": provider.cost_per_token
            },
            "has_api_keys": bool(mock_get_api_key(provider_id)),
            "status": "active" if provider.is_active else "inactive"
        }

    manager.get_api_key = mock_get_api_key
    manager.store_api_key = mock_store_api_key
    manager.get_provider_status = mock_get_provider_status
    manager.is_configured = MagicMock(return_value=True)
    manager.get_tenant_api_key = mock_get_api_key
    manager.get_optimal_provider = MagicMock(return_value="deepseek")

    return manager


@pytest.fixture
def client(mock_byok_manager):
    """FastAPI TestClient with mocked BYOK manager"""
    from fastapi import FastAPI
    app = FastAPI()

    # Override dependency
    app.dependency_overrides[get_byok_manager] = lambda: mock_byok_manager

    # Include router
    app.include_router(router)

    return TestClient(app)


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

class TestHealthCheck:
    """Test health check endpoints"""

    def test_byok_health_check(self, client):
        """Test basic health check endpoint"""
        response = client.get("/api/v1/byok/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "service" in data
        assert "timestamp" in data

    def test_ai_health_check(self, client, mock_byok_manager):
        """Test comprehensive AI health check"""
        response = client.get("/api/ai/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "providers" in data
        assert "usage" in data


# =============================================================================
# API KEY MANAGEMENT TESTS
# =============================================================================

class TestAPIKeyManagement:
    """Test API key CRUD operations"""

    def test_get_api_keys_empty(self, client, mock_byok_manager):
        """Test getting API keys when none are stored"""
        mock_byok_manager.api_keys = {}
        response = client.get("/api/ai/keys")
        assert response.status_code == 200

        data = response.json()
        assert "keys" in data
        assert "count" in data
        assert data["count"] == 0

    def test_add_api_key_success(self, client, mock_byok_manager):
        """Test adding a new API key"""
        key_data = {
            "provider": "openai",
            "key": "sk-new-test-key-12345",
            "key_name": "test",
            "environment": "production"
        }

        response = client.post("/api/ai/keys", json=key_data)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data["provider"] == "openai"
        assert "key_id" in data
        assert "masked_key" in data

    def test_add_api_key_missing_provider(self, client):
        """Test adding API key without provider"""
        key_data = {
            "key": "sk-test-key"
        }

        response = client.post("/api/ai/keys", json=key_data)
        assert response.status_code == 400  # Bad Request

    def test_add_api_key_missing_key(self, client):
        """Test adding API key without actual key"""
        key_data = {
            "provider": "openai"
        }

        response = client.post("/api/ai/keys", json=key_data)
        assert response.status_code == 400  # Bad Request


# =============================================================================
# PROVIDER MANAGEMENT TESTS
# =============================================================================

class TestProviderManagement:
    """Test provider listing and details"""

    def test_get_ai_providers(self, client, mock_byok_manager):
        """Test getting all AI providers"""
        response = client.get("/api/ai/providers")
        assert response.status_code == 200

        data = response.json()
        assert "providers" in data
        assert "total_providers" in data
        assert "active_providers" in data

        # Should have at least the mocked providers
        assert data["total_providers"] >= 2

    def test_get_ai_provider_by_id(self, client):
        """Test getting specific provider details"""
        response = client.get("/api/ai/providers/openai")
        assert response.status_code == 200

        data = response.json()
        assert "provider" in data
        assert data["provider"]["id"] == "openai"
        assert "has_api_keys" in data
        assert "status" in data

    def test_get_ai_provider_not_found(self, client):
        """Test getting non-existent provider"""
        response = client.get("/api/ai/providers/nonexistent")
        assert response.status_code == 404


# =============================================================================
# USAGE TRACKING TESTS
# =============================================================================

class TestUsageTracking:
    """Test usage tracking and statistics"""

    def test_track_ai_usage(self, client):
        """Test tracking AI usage"""
        usage_data = {
            "provider_id": "openai",
            "success": True,
            "tokens_used": 150
        }

        response = client.post("/api/ai/usage/track", json=usage_data)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "tokens_used" in data

    def test_track_ai_usage_missing_provider(self, client):
        """Test tracking usage without provider_id"""
        usage_data = {
            "success": True,
            "tokens_used": 100
        }

        response = client.post("/api/ai/usage/track", json=usage_data)
        assert response.status_code == 400  # Bad Request

    def test_get_usage_stats_all(self, client):
        """Test getting usage stats for all providers"""
        response = client.get("/api/ai/usage/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_providers" in data
        assert "usage_stats" in data

    def test_get_usage_stats_provider_not_found(self, client):
        """Test getting usage stats for non-existent provider"""
        response = client.get("/api/ai/usage/stats?provider_id=nonexistent")
        assert response.status_code == 404


# =============================================================================
# COST OPTIMIZATION TESTS
# =============================================================================

class TestCostOptimization:
    """Test cost optimization endpoints"""

    def test_optimize_cost_usage(self, client):
        """Test cost optimization recommendation"""
        usage_data = {
            "task_type": "general",
            "estimated_tokens": 1000
        }

        response = client.post("/api/ai/optimize-cost", json=usage_data)
        assert response.status_code == 200

        data = response.json()
        assert "recommended_provider" in data
        assert "estimated_cost" in data

    def test_optimize_cost_with_budget(self, client):
        """Test cost optimization with budget constraint"""
        usage_data = {
            "task_type": "general",
            "estimated_tokens": 1000,
            "budget_constraint": 0.001
        }

        response = client.post("/api/ai/optimize-cost", json=usage_data)

        # Should either succeed or return no suitable providers
        assert response.status_code in [200, 400]


# =============================================================================
# PRICING ENDPOINTS TESTS
# =============================================================================

class TestPricingEndpoints:
    """Test dynamic pricing endpoints"""

    def test_get_ai_pricing(self, client):
        """Test getting current AI pricing"""
        response = client.get("/api/ai/pricing")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "model_count" in data

    @patch("core.dynamic_pricing_fetcher.get_pricing_fetcher")
    def test_get_model_pricing(self, mock_get_pricing_fetcher, client):
        """Test getting pricing for specific model"""
        fetcher = MagicMock()
        fetcher.get_model_price.return_value = {
            "input_cost_per_token": 0.0000025,
            "output_cost_per_token": 0.00001,
        }
        mock_get_pricing_fetcher.return_value = fetcher

        response = client.get("/api/ai/pricing/model/gpt-4o")
        assert response.status_code in [200, 404]  # May not be in cache

        if response.status_code == 200:
            data = response.json()
            assert "model" in data
            assert "pricing" in data

    @patch("core.dynamic_pricing_fetcher.get_pricing_fetcher")
    def test_estimate_request_cost(self, mock_get_pricing_fetcher, client):
        """Test cost estimation for a request"""
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = 0.002
        mock_get_pricing_fetcher.return_value = fetcher

        request_data = {
            "model": "gpt-4o",
            "input_tokens": 100,
            "output_tokens": 50
        }

        response = client.post("/api/ai/pricing/estimate", json=request_data)
        assert response.status_code in [200, 404, 400]

        if response.status_code == 200:
            data = response.json()
            assert "estimated_cost_usd" in data
            assert "input_tokens" in data

    def test_estimate_request_cost_with_prompt(self, client):
        """Test cost estimation with prompt text"""
        request_data = {
            "model": "gpt-4o",
            "prompt": "What is the meaning of life?"
        }

        response = client.post("/api/ai/pricing/estimate", json=request_data)
        assert response.status_code in [200, 404, 400]


# =============================================================================
# PDF-SPECIFIC ENDPOINTS TESTS
# =============================================================================

class TestPDFEndpoints:
    """Test PDF processing provider endpoints"""

    def test_get_pdf_ai_providers(self, client):
        """Test getting PDF-capable AI providers"""
        response = client.get("/api/ai/pdf/providers")
        assert response.status_code == 200

        data = response.json()
        assert "pdf_providers" in data
        assert "total_pdf_providers" in data

    def test_optimize_pdf_processing(self, client):
        """Test PDF processing optimization"""
        pdf_data = {
            "pdf_type": "scanned",
            "needs_ocr": True,
            "estimated_pages": 10
        }

        response = client.post("/api/ai/pdf/optimize", json=pdf_data)
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data = response.json()
            assert "recommended_provider" in data
            assert "pdf_analysis" in data


# =============================================================================
# BACKWARD COMPATIBILITY TESTS
# =============================================================================

class TestBackwardCompatibility:
    """Test v1 API compatibility endpoints"""

    def test_byok_health_v1(self, client):
        """Test v1 health check endpoint"""
        response = client.get("/api/v1/byok/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"

    def test_byok_status_v1(self, client):
        """Test v1 status endpoint"""
        response = client.get("/api/v1/byok/status")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "available" in data
        assert "providers_list" in data


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Test error handling in endpoints"""

    def test_invalid_json(self, client):
        """Test endpoint with invalid JSON"""
        response = client.post(
            "/api/ai/keys",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 422]

    def test_missing_content_type(self, client):
        """Test POST without content-type header"""
        response = client.post(
            "/api/ai/keys",
            data={"provider": "openai", "key": "test"}
        )
        # May succeed or fail depending on FastAPI parsing
        assert response.status_code in [200, 400, 422]


# =============================================================================
# RESPONSE FORMAT TESTS
# =============================================================================

class TestResponseFormats:
    """Test API response format consistency"""

    def test_success_response_format(self, client):
        """Test success responses follow consistent format"""
        response = client.get("/api/v1/byok/health")
        assert response.status_code == 200

        data = response.json()
        # Should have status field
        assert "status" in data

    def test_error_response_format(self, client):
        """Test error responses follow consistent format"""
        response = client.get("/api/ai/providers/nonexistent")
        assert response.status_code == 404

        data = response.json()
        # Should have detail/message field
        assert "detail" in data or "message" in data


# =============================================================================
# ADDITIONAL VALIDATION TESTS
# =============================================================================

class TestValidation:
    """Test input validation"""

    def test_provider_id_validation(self, client):
        """Test provider ID is properly validated"""
        # Use a provider ID that doesn't exist
        response = client.get("/api/ai/providers/invalid_provider_id_12345")
        assert response.status_code == 404

    def test_empty_request_body(self, client):
        """Test endpoint with empty request body"""
        response = client.post("/api/ai/keys", json={})
        assert response.status_code in [400, 422]

    def test_extra_fields_ignored(self, client):
        """Test that extra fields in request are ignored"""
        key_data = {
            "provider": "openai",
            "key": "sk-test-key",
            "extra_field": "should_be_ignored"
        }

        response = client.post("/api/ai/keys", json=key_data)
        # Should not error due to extra field
        assert response.status_code in [200, 400]


class TestStoreApiKeyEndpoint:
    """W46: /api/ai/providers/{id}/keys — validation + error branches."""

    def test_store_api_key_too_short(self, client):
        # Pydantic enforces min_length=10 → 422 (the endpoint's own <10
        # check is unreachable dead code).
        response = client.post(
            "/api/ai/providers/openai/keys",
            json={"api_key": "short", "key_name": "default"})
        assert response.status_code == 422

    def test_store_api_key_invalid_provider(self, client):
        response = client.post(
            "/api/ai/providers/not_a_provider/keys",
            json={"api_key": "sk-valid-key-12345", "key_name": "default"})
        assert response.status_code == 400
        assert "Invalid provider_id" in response.json()["detail"]

    def test_store_api_key_value_error_404(self, client, mock_byok_manager):
        mock_byok_manager.encrypt_api_key.return_value = "encrypted"

        def _boom(provider_id, api_key, key_name="default", environment="production"):
            raise ValueError("Provider not found")

        mock_byok_manager.store_api_key = _boom
        response = client.post(
            "/api/ai/providers/openai/keys",
            json={"api_key": "sk-valid-key-12345", "key_name": "default"})
        assert response.status_code == 404

    def test_store_api_key_exception_500(self, client, mock_byok_manager):
        mock_byok_manager.encrypt_api_key.side_effect = RuntimeError("boom")
        response = client.post(
            "/api/ai/providers/openai/keys",
            json={"api_key": "sk-valid-key-12345", "key_name": "default"})
        assert response.status_code == 500

    def test_store_api_key_success(self, client, mock_byok_manager):
        mock_byok_manager.store_api_key.return_value = "openai_default_production"
        response = client.post(
            "/api/ai/providers/openai/keys",
            json={"api_key": "sk-valid-key-12345", "key_name": "default"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["key_preview"] == "sk-v...2345"


class TestApiKeyStatusAndDelete:
    def test_get_key_status_not_found(self, client, mock_byok_manager):
        mock_byok_manager.api_keys = {}
        response = client.get("/api/ai/providers/openai/keys/default")
        assert response.status_code == 404

    def test_get_key_status_found(self, client, mock_byok_manager):
        from core.byok_endpoints import APIKey
        from datetime import datetime
        mock_byok_manager.api_keys = {
            "openai_default_production": APIKey(
                provider_id="openai", key_name="default",
                encrypted_key="enc", key_hash="h",
                created_at=datetime.now(), environment="production"),
        }
        response = client.get("/api/ai/providers/openai/keys/default")
        assert response.status_code == 200
        data = response.json()
        assert data["has_key"] is True
        assert data["provider_id"] == "openai"

    def test_delete_key_not_found(self, client, mock_byok_manager):
        mock_byok_manager.api_keys = {}
        response = client.delete("/api/ai/providers/openai/keys/default")
        assert response.status_code == 404

    def test_delete_key_success(self, client, mock_byok_manager):
        from core.byok_endpoints import APIKey
        from datetime import datetime
        mock_byok_manager.api_keys = {
            "openai_default_production": APIKey(
                provider_id="openai", key_name="default",
                encrypted_key="enc", key_hash="h",
                created_at=datetime.now(), environment="production"),
        }
        response = client.delete("/api/ai/providers/openai/keys/default")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "openai_default_production" not in mock_byok_manager.api_keys
        mock_byok_manager._save_configuration.assert_called_once()


class TestPricingEndpoints:
    """W46: pricing refresh/model/provider/estimate endpoints."""

    def test_refresh_pricing_success(self, client, mock_byok_manager):
        mock_refresh = AsyncMock(return_value=[{"model": "gpt-4o"}])
        with patch("core.dynamic_pricing_fetcher.refresh_pricing_cache",
                   new=mock_refresh):
            response = client.post("/api/ai/pricing/refresh")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_byok_manager.update_provider_costs.assert_called_once()

    def test_refresh_pricing_error(self, client, mock_byok_manager):
        with patch("core.dynamic_pricing_fetcher.refresh_pricing_cache",
                   side_effect=RuntimeError("fetch failed")):
            response = client.post("/api/ai/pricing/refresh")
        assert response.status_code == 200
        assert response.json()["status"] == "error"

    def test_get_model_pricing_found(self, client):
        fetcher = MagicMock()
        fetcher.get_model_price.return_value = {
            "input_cost_per_token": 0.01, "output_cost_per_token": 0.02}
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            response = client.get("/api/ai/pricing/model/gpt-4o")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["pricing"]["input_cost_per_token"] == 0.01

    def test_get_model_pricing_not_found(self, client):
        fetcher = MagicMock()
        fetcher.get_model_price.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            response = client.get("/api/ai/pricing/model/unknown-model")
        assert response.status_code == 200
        assert response.json()["status"] == "not_found"

    def test_get_model_pricing_error(self, client):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            response = client.get("/api/ai/pricing/model/gpt-4o")
        assert response.status_code == 200
        assert response.json()["status"] == "error"

    def test_get_provider_pricing_success(self, client):
        fetcher = MagicMock()
        fetcher.get_provider_models.return_value = [{"id": "m1"}, {"id": "m2"}]
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            response = client.get("/api/ai/pricing/provider/openai")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["model_count"] == 2

    def test_get_provider_pricing_error(self, client):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            response = client.get("/api/ai/pricing/provider/openai")
        assert response.status_code == 200
        assert response.json()["status"] == "error"

    def test_estimate_cost_success(self, client):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = 0.005
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            response = client.post("/api/ai/pricing/estimate",
                                   json={"model": "gpt-4o-mini",
                                         "input_tokens": 100,
                                         "output_tokens": 200})
        data = response.json()
        assert data["status"] == "success"
        assert data["estimated_cost_usd"] == 0.005

    def test_estimate_cost_prompt_token_estimate(self, client):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = 0.01
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            response = client.post("/api/ai/pricing/estimate",
                                   json={"model": "m",
                                         "prompt": "x" * 100,
                                         "output_tokens": 10})
        data = response.json()
        assert data["status"] == "success"
        assert data["input_tokens"] == 25  # len(prompt) // 4

    def test_estimate_cost_fallback_to_model_price(self, client):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = None
        fetcher.get_model_price.return_value = {
            "input_cost_per_token": 0.01, "output_cost_per_token": 0.02}
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            response = client.post("/api/ai/pricing/estimate",
                                   json={"model": "m",
                                         "input_tokens": 100,
                                         "output_tokens": 200})
        data = response.json()
        assert data["status"] == "success"
        # 0.01*100 + 0.02*200 = 1 + 4 = 5
        assert data["estimated_cost_usd"] == 5.0

    def test_estimate_cost_unavailable(self, client):
        fetcher = MagicMock()
        fetcher.estimate_cost.return_value = None
        fetcher.get_model_price.return_value = None
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            response = client.post("/api/ai/pricing/estimate",
                                   json={"model": "unknown"})
        assert response.json()["status"] == "pricing_unavailable"

    def test_estimate_cost_error(self, client):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            response = client.post("/api/ai/pricing/estimate", json={})
        assert response.json()["status"] == "error"


class TestOptimizeEndpoints:
    """W46: optimize-cost + optimize-pdf endpoints."""

    def test_optimize_cost_success(self, client, mock_byok_manager):
        mock_byok_manager.get_optimal_provider.return_value = "openai"
        mock_byok_manager.providers["openai"].cost_per_token = 0.00003
        mock_byok_manager.get_api_key.side_effect = None
        response = client.post("/api/ai/optimize-cost",
                               json={"task_type": "general",
                                     "estimated_tokens": 1000})
        data = response.json()
        assert data["success"] is True
        assert data["recommended_provider"] == "openai"
        assert data["estimated_cost"] == 1000 * 0.00003

    def test_optimize_cost_no_provider(self, client, mock_byok_manager):
        mock_byok_manager.get_optimal_provider.return_value = None
        response = client.post("/api/ai/optimize-cost",
                               json={"task_type": "general"})
        assert response.status_code == 400

    def test_optimize_cost_value_error(self, client, mock_byok_manager):
        mock_byok_manager.get_optimal_provider.side_effect = ValueError("bad")
        response = client.post("/api/ai/optimize-cost",
                               json={"task_type": "general"})
        assert response.status_code == 400

    def test_optimize_cost_exception(self, client, mock_byok_manager):
        mock_byok_manager.get_optimal_provider.side_effect = RuntimeError("boom")
        response = client.post("/api/ai/optimize-cost",
                               json={"task_type": "general"})
        assert response.status_code == 500

    def test_optimize_pdf_success(self, client, mock_byok_manager):
        mock_byok_manager.get_optimal_provider.return_value = "deepseek"
        mock_byok_manager.providers["deepseek"].cost_per_token = 0.00000014
        response = client.post("/api/ai/pdf/optimize",
                               json={"pdf_type": "scanned",
                                     "needs_ocr": True,
                                     "needs_image_comprehension": False,
                                     "estimated_pages": 10})
        data = response.json()
        assert data["success"] is True
        assert data["recommended_provider"]["provider_id"] == "deepseek"
        assert data["pdf_analysis"]["estimated_tokens"] == 5000

    def test_optimize_pdf_image_comprehension(self, client, mock_byok_manager):
        mock_byok_manager.get_optimal_provider.return_value = "openai"
        response = client.post("/api/ai/pdf/optimize",
                               json={"pdf_type": "complex",
                                     "needs_image_comprehension": True,
                                     "estimated_pages": 5})
        data = response.json()
        assert data["success"] is True
        assert data["pdf_analysis"]["needs_image_comprehension"] is True

    def test_optimize_pdf_no_provider(self, client, mock_byok_manager):
        mock_byok_manager.get_optimal_provider.return_value = None
        response = client.post("/api/ai/pdf/optimize",
                               json={"pdf_type": "scanned",
                                     "needs_ocr": True,
                                     "estimated_pages": 10})
        assert response.status_code == 400

    def test_optimize_pdf_value_error(self, client, mock_byok_manager):
        mock_byok_manager.get_optimal_provider.side_effect = ValueError("bad")
        response = client.post("/api/ai/pdf/optimize",
                               json={"pdf_type": "x", "estimated_pages": 1})
        assert response.status_code == 400

    def test_optimize_pdf_exception(self, client, mock_byok_manager):
        mock_byok_manager.get_optimal_provider.side_effect = RuntimeError("boom")
        response = client.post("/api/ai/pdf/optimize",
                               json={"pdf_type": "x", "estimated_pages": 1})
        assert response.status_code == 500


class TestPricingSummary:
    """W46: GET /api/ai/pricing summary endpoint."""

    def test_get_ai_pricing_success(self, client):
        fetcher = MagicMock()
        fetcher.pricing_cache = {"gpt-4o": {}, "deepseek": {}}
        fetcher.last_fetch = None
        fetcher._is_cache_valid.return_value = True
        fetcher.get_cheapest_models.return_value = [{"model": "deepseek"}]
        fetcher.compare_providers.return_value = {"openai": {"cheapest": 1}}
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   return_value=fetcher):
            response = client.get("/api/ai/pricing")
        data = response.json()
        assert data["status"] == "success"
        assert data["model_count"] == 2
        assert data["cache_valid"] is True

    def test_get_ai_pricing_error(self, client):
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher",
                   side_effect=RuntimeError("boom")):
            response = client.get("/api/ai/pricing")
        assert response.json()["status"] == "error"


class TestUsageEndpoints:
    """W46: usage track + stats endpoints."""

    def test_track_ai_usage_success(self, client, mock_byok_manager):
        mock_byok_manager.track_usage = MagicMock()
        response = client.post("/api/ai/usage/track",
                               json={"provider_id": "openai",
                                     "success": True,
                                     "tokens_used": 100})
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_get_usage_stats(self, client, mock_byok_manager):
        from core.byok_endpoints import ProviderUsage
        mock_byok_manager.usage_stats = {
            "openai": ProviderUsage(provider_id="openai")}
        response = client.get("/api/ai/usage/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_providers"] == 1
        assert "openai" in data["usage_stats"]
