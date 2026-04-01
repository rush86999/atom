"""
TDD Tests for BYOK Pricing Endpoints

Tests for /api/ai/pricing/* endpoints that provide real-time AI model pricing
from external APIs (LiteLLM, OpenRouter).

Endpoints tested:
- GET /api/ai/pricing - Get current pricing cache
- POST /api/ai/pricing/refresh - Refresh pricing from external APIs
- GET /api/ai/pricing/model/{model} - Get specific model pricing
- GET /api/ai/pricing/provider/{provider} - Get provider models
- POST /api/ai/pricing/estimate - Estimate request cost

Run: pytest tests/api/test_byok_pricing_endpoints.py -v
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def pricing_app() -> FastAPI:
    """Create FastAPI app with BYOK routes for testing."""
    from fastapi import FastAPI
    from api.byok_routes import router as byok_router
    
    app = FastAPI()
    app.include_router(byok_router)
    return app


@pytest.fixture(scope="function")
def pricing_client(pricing_app: FastAPI) -> TestClient:
    """Create TestClient for pricing endpoint tests."""
    return TestClient(pricing_app)


@pytest.fixture
def mock_pricing_fetcher() -> MagicMock:
    """Create mock pricing fetcher with realistic test data."""
    fetcher = MagicMock()
    fetcher.pricing_cache = {
        "gpt-4o": {
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
            "max_tokens": 128000,
            "litellm_provider": "openai",
            "source": "litellm"
        },
        "gpt-4o-mini": {
            "input_cost_per_token": 0.00000015,
            "output_cost_per_token": 0.0000006,
            "max_tokens": 128000,
            "litellm_provider": "openai",
            "source": "litellm"
        },
        "claude-3-5-sonnet": {
            "input_cost_per_token": 0.000003,
            "output_cost_per_token": 0.000015,
            "max_tokens": 200000,
            "litellm_provider": "anthropic",
            "source": "litellm"
        },
        "deepseek-chat": {
            "input_cost_per_token": 0.00000014,
            "output_cost_per_token": 0.00000028,
            "max_tokens": 128000,
            "litellm_provider": "deepseek",
            "source": "litellm"
        }
    }
    fetcher.last_fetch = datetime.now() - timedelta(hours=2)
    fetcher._is_cache_valid.return_value = False  # Cache expired
    fetcher.get_cheapest_models.return_value = [
        {"model": "deepseek-chat", "input_cost_per_token": 0.00000014},
        {"model": "gpt-4o-mini", "input_cost_per_token": 0.00000015},
    ]
    fetcher.compare_providers.return_value = {
        "openai": {"avg_input_cost": 0.00000257, "model_count": 2},
        "anthropic": {"avg_input_cost": 0.000003, "model_count": 1},
        "deepseek": {"avg_input_cost": 0.00000014, "model_count": 1},
    }
    fetcher.get_provider_models.return_value = []
    # Mock get_model_price to return dict from cache
    def mock_get_model_price(model_name):
        return fetcher.pricing_cache.get(model_name)
    fetcher.get_model_price = mock_get_model_price
    # Mock estimate_cost
    def mock_estimate_cost(model, input_tokens=0, output_tokens=0):
        pricing = fetcher.pricing_cache.get(model)
        if pricing:
            return (pricing["input_cost_per_token"] * input_tokens + 
                    pricing["output_cost_per_token"] * output_tokens)
        return None
    fetcher.estimate_cost = mock_estimate_cost
    return fetcher


@pytest.fixture
def mock_pricing_fetcher_empty() -> MagicMock:
    """Create mock pricing fetcher with empty cache."""
    fetcher = MagicMock()
    fetcher.pricing_cache = {}
    fetcher.last_fetch = None
    fetcher._is_cache_valid.return_value = False
    fetcher.get_cheapest_models.return_value = []
    fetcher.compare_providers.return_value = {}
    fetcher.get_provider_models.return_value = []
    # Mock get_model_price to return None for all models
    fetcher.get_model_price = MagicMock(return_value=None)
    # Mock estimate_cost to return None (model not found)
    fetcher.estimate_cost = MagicMock(return_value=None)
    return fetcher


# ============================================================================
# GET /api/ai/pricing - Get Current Pricing
# ============================================================================

class TestGetPricing:
    """Tests for GET /api/ai/pricing endpoint."""

    def test_get_pricing_success(self, pricing_client, mock_pricing_fetcher):
        """Test successful pricing retrieval."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.get("/api/ai/pricing")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "data" in data
            assert data["data"]["model_count"] == 4
            assert data["data"]["cache_valid"] is False
            assert "cheapest_models" in data["data"]
            assert "provider_comparison" in data["data"]

    def test_get_pricing_empty_cache(self, pricing_client, mock_pricing_fetcher_empty):
        """Test pricing with empty cache."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher_empty):
            response = pricing_client.get("/api/ai/pricing")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["data"]["model_count"] == 0
            assert data["data"]["cheapest_models"] == []

    def test_get_pricing_error_handling(self, pricing_client):
        """Test error handling when fetcher fails."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', side_effect=Exception("Test error")):
            response = pricing_client.get("/api/ai/pricing")
            
            assert response.status_code == 200  # API returns error in response body
            data = response.json()
            
            assert data["success"] is False
            assert "message" in data
            assert "Test error" in data["message"]


# ============================================================================
# POST /api/ai/pricing/refresh - Refresh Pricing Cache
# ============================================================================

class TestRefreshPricing:
    """Tests for POST /api/ai/pricing/refresh endpoint."""

    def test_refresh_pricing_success(self, pricing_client):
        """Test successful pricing refresh."""
        mock_refresh = AsyncMock(return_value={
            "gpt-4o": {"input_cost_per_token": 0.000005},
            "claude-3-5-sonnet": {"input_cost_per_token": 0.000003},
        })
        
        with patch('core.dynamic_pricing_fetcher.refresh_pricing_cache', mock_refresh):
            response = pricing_client.post("/api/ai/pricing/refresh")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["data"]["models_fetched"] == 2
            mock_refresh.assert_called_once()

    def test_refresh_pricing_with_force_flag(self, pricing_client):
        """Test pricing refresh with force=true parameter."""
        mock_refresh = AsyncMock(return_value={"model1": {}})
        
        with patch('core.dynamic_pricing_fetcher.refresh_pricing_cache', mock_refresh):
            response = pricing_client.post("/api/ai/pricing/refresh?force=true")
            
            assert response.status_code == 200
            mock_refresh.assert_called_once_with(force=True)

    def test_refresh_pricing_error(self, pricing_client):
        """Test error handling during refresh."""
        mock_refresh = AsyncMock(side_effect=Exception("Network error"))
        
        with patch('core.dynamic_pricing_fetcher.refresh_pricing_cache', mock_refresh):
            response = pricing_client.post("/api/ai/pricing/refresh")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is False
            assert "Network error" in data["message"]


# ============================================================================
# GET /api/ai/pricing/model/{model} - Get Model Pricing
# ============================================================================

class TestGetModelPricing:
    """Tests for GET /api/ai/pricing/model/{model} endpoint."""

    def test_get_model_pricing_found(self, pricing_client, mock_pricing_fetcher):
        """Test getting pricing for existing model."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.get("/api/ai/pricing/model/gpt-4o")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["data"]["model"] == "gpt-4o"
            assert data["data"]["pricing"]["input_cost_per_token"] == 0.000005
            assert data["data"]["pricing"]["output_cost_per_token"] == 0.000015

    def test_get_model_pricing_not_found(self, pricing_client, mock_pricing_fetcher):
        """Test getting pricing for non-existent model."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.get("/api/ai/pricing/model/unknown-model")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is False
            assert "not found" in data["message"].lower()
            assert data["data"]["model"] == "unknown-model"

    def test_get_model_pricing_with_path_encoding(self, pricing_client, mock_pricing_fetcher):
        """Test model name with special characters (path encoding)."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            # Test with model name containing hyphens
            response = pricing_client.get("/api/ai/pricing/model/claude-3-5-sonnet")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["data"]["model"] == "claude-3-5-sonnet"
            assert data["data"]["pricing"]["litellm_provider"] == "anthropic"


# ============================================================================
# GET /api/ai/pricing/provider/{provider} - Get Provider Models
# ============================================================================

class TestGetProviderPricing:
    """Tests for GET /api/ai/pricing/provider/{provider} endpoint."""

    def test_get_provider_pricing(self, pricing_client, mock_pricing_fetcher):
        """Test getting all models for a provider."""
        # Add more models to mock
        mock_pricing_fetcher.get_provider_models = MagicMock(return_value=[
            {"model": "gpt-4o", "input_cost_per_token": 0.000005},
            {"model": "gpt-4o-mini", "input_cost_per_token": 0.00000015},
        ])
        
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.get("/api/ai/pricing/provider/openai")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["data"]["provider"] == "openai"
            assert data["data"]["model_count"] == 2
            assert len(data["data"]["models"]) <= 10  # Default limit

    def test_get_provider_pricing_with_limit(self, pricing_client, mock_pricing_fetcher):
        """Test provider pricing with custom limit."""
        mock_pricing_fetcher.get_provider_models = MagicMock(return_value=[
            {"model": f"model-{i}", "input_cost_per_token": 0.000001}
            for i in range(20)
        ])
        
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.get("/api/ai/pricing/provider/openai?limit=5")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["data"]["model_count"] <= 5

    def test_get_provider_pricing_unknown_provider(self, pricing_client, mock_pricing_fetcher):
        """Test getting models for unknown provider."""
        mock_pricing_fetcher.get_provider_models = MagicMock(return_value=[])
        
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.get("/api/ai/pricing/provider/unknown-provider")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["data"]["model_count"] == 0


# ============================================================================
# POST /api/ai/pricing/estimate - Estimate Request Cost
# ============================================================================

class TestEstimateCost:
    """Tests for POST /api/ai/pricing/estimate endpoint."""

    def test_estimate_cost_with_tokens(self, pricing_client, mock_pricing_fetcher):
        """Test cost estimation with explicit token counts."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.post(
                "/api/ai/pricing/estimate",
                json={
                    "model": "gpt-4o",
                    "input_tokens": 1000,
                    "output_tokens": 500
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "estimated_cost_usd" in data["data"]
            # gpt-4o: 0.000005 * 1000 + 0.000015 * 500 = 0.005 + 0.0075 = 0.0125
            assert abs(data["data"]["estimated_cost_usd"] - 0.0125) < 0.0001

    def test_estimate_cost_with_prompt(self, pricing_client, mock_pricing_fetcher):
        """Test cost estimation with prompt text (auto token estimation)."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.post(
                "/api/ai/pricing/estimate",
                json={
                    "model": "gpt-4o",
                    "prompt": "Hello, how are you?" * 100  # ~600 chars ≈ 150 tokens
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "estimated_cost_usd" in data["data"]

    def test_estimate_cost_default_model(self, pricing_client, mock_pricing_fetcher):
        """Test cost estimation with default model."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.post(
                "/api/ai/pricing/estimate",
                json={
                    "input_tokens": 1000,
                    "output_tokens": 500
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            # Should use default model (gpt-4o-mini)

    def test_estimate_cost_model_not_found(self, pricing_client, mock_pricing_fetcher_empty):
        """Test cost estimation when model pricing not available."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher_empty):
            response = pricing_client.post(
                "/api/ai/pricing/estimate",
                json={
                    "model": "unknown-model",
                    "input_tokens": 1000
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is False
            assert "not found" in data["message"].lower()


# ============================================================================
# Integration Tests
# ============================================================================

class TestPricingIntegration:
    """Integration tests for pricing endpoints."""

    def test_pricing_workflow(self, pricing_client, mock_pricing_fetcher):
        """Test complete pricing workflow: check → refresh → estimate."""
        # 1. Check current pricing
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.get("/api/ai/pricing")
            assert response.status_code == 200
            assert response.json()["data"]["model_count"] == 4
        
        # 2. Estimate cost for a request
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.post(
                "/api/ai/pricing/estimate",
                json={
                    "model": "gpt-4o",
                    "input_tokens": 2000,
                    "output_tokens": 1000
                }
            )
            assert response.status_code == 200
            estimate = response.json()["data"]["estimated_cost_usd"]
            assert estimate > 0
        
        # 3. Get specific model pricing
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.get("/api/ai/pricing/model/deepseek-chat")
            assert response.status_code == 200
            assert response.json()["data"]["pricing"]["litellm_provider"] == "deepseek"

    def test_multi_provider_comparison(self, pricing_client, mock_pricing_fetcher):
        """Test comparing pricing across providers."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            # Get provider comparison
            response = pricing_client.get("/api/ai/pricing")
            data = response.json()
            
            providers = data["data"]["provider_comparison"]
            assert "openai" in providers
            assert "anthropic" in providers
            assert "deepseek" in providers
            
            # DeepSeek should be cheapest
            assert providers["deepseek"]["avg_input_cost"] < providers["openai"]["avg_input_cost"]


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestPricingEdgeCases:
    """Edge case tests for pricing endpoints."""

    def test_zero_tokens_estimate(self, pricing_client, mock_pricing_fetcher):
        """Test cost estimation with zero tokens."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.post(
                "/api/ai/pricing/estimate",
                json={
                    "model": "gpt-4o",
                    "input_tokens": 0,
                    "output_tokens": 0
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["data"]["estimated_cost_usd"] == 0

    def test_very_large_token_estimate(self, pricing_client, mock_pricing_fetcher):
        """Test cost estimation with very large token count."""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher', return_value=mock_pricing_fetcher):
            response = pricing_client.post(
                "/api/ai/pricing/estimate",
                json={
                    "model": "gpt-4o",
                    "input_tokens": 1000000,  # 1M tokens
                    "output_tokens": 100000
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["data"]["estimated_cost_usd"] > 0

    def test_invalid_json_body(self, pricing_client):
        """Test handling of invalid JSON body."""
        response = pricing_client.post(
            "/api/ai/pricing/estimate",
            content="invalid json"
        )
        
        # FastAPI should handle this with 422
        assert response.status_code in [200, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
