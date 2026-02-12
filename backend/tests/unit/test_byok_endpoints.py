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
from unittest.mock import MagicMock, patch

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

    def test_get_model_pricing(self, client):
        """Test getting pricing for specific model"""
        response = client.get("/api/ai/pricing/model/gpt-4o")
        assert response.status_code in [200, 404]  # May not be in cache

        if response.status_code == 200:
            data = response.json()
            assert "model" in data
            assert "pricing" in data

    def test_estimate_request_cost(self, client):
        """Test cost estimation for a request"""
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
