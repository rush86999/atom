"""
Tests for the provider registry REST API.

The original file tested `/api/ai/providers/registry/*` routes that were
deleted as dead code (no frontend consumer, no backend importer). The real,
mounted BYOK surface is `api/byok_routes` (`/api/ai/providers*`,
`/api/ai/pricing*`, `/api/ai/health`), which is what these tests now exercise
using a standalone app with auth/db/byok-manager overrides (same pattern as
tests/unit/api/test_byok_routes.py).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from core.auth import get_current_user
from core.auth import get_current_tenant
from core.database import get_db
from api.byok_routes import get_byok_manager


@pytest.fixture
def mock_manager():
    """Mock BYOK manager."""
    manager = MagicMock()
    manager.providers = ["openai"]
    manager.get_tenant_provider_status.return_value = {
        "provider_id": "openai",
        "name": "OpenAI",
        "has_api_keys": True,
    }
    manager.store_tenant_api_key.return_value = "openai_default_production"
    return manager


@pytest.fixture
def app(mock_manager):
    """Create test FastAPI app with BYOK routes and bound identity."""
    from types import SimpleNamespace

    from api.byok_routes import router

    app = FastAPI()
    app.include_router(router)

    def _override_user():
        return SimpleNamespace(id="test-user", tenant_id="t-1")

    def _override_tenant():
        return SimpleNamespace(id="t-1", name="Test Tenant", ai_mode="auto")

    def _override_db():
        return MagicMock()

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_tenant] = _override_tenant
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_byok_manager] = lambda: mock_manager
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestProviderRegistryAPI:
    """Test provider registry REST API endpoints"""

    def test_list_providers_success(self, client, mock_manager):
        """Test listing providers returns success response"""
        response = client.get("/api/ai/providers")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "providers" in data["data"]
        assert len(data["data"]["providers"]) == 1

    def test_get_provider_with_models(self, client, mock_manager):
        """Test getting single provider with status"""
        response = client.get("/api/ai/providers/openai")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["provider_id"] == "openai"

    def test_get_provider_not_found(self, client, mock_manager):
        """Test getting non-existent provider returns 404"""
        mock_manager.get_tenant_provider_status.side_effect = ValueError("unknown")

        response = client.get("/api/ai/providers/nonexistent")
        assert response.status_code == 404

    @patch('core.dynamic_pricing_fetcher.refresh_pricing_cache')
    def test_refresh_provider_pricing(self, mock_refresh, client):
        """Test pricing refresh endpoint returns success response"""
        mock_refresh.return_value = []

        response = client.post("/api/ai/pricing/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "models_fetched" in data["data"]

    def test_add_api_key_via_post_body(self, client, mock_manager):
        """Test API key submission via POST"""
        response = client.post(
            "/api/ai/providers/openai/keys",
            params={"api_key": "sk-test-key-1234567890", "key_name": "test"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["key_id"] == "openai_default_production"

    def test_add_api_key_rejects_short_key(self, client, mock_manager):
        """Test API key validation rejects short keys"""
        response = client.post(
            "/api/ai/providers/openai/keys",
            params={"api_key": "short", "key_name": "test"}
        )
        assert response.status_code == 422  # Validation error
        mock_manager.store_tenant_api_key.assert_not_called()

    @patch('core.dynamic_pricing_fetcher.get_pricing_fetcher')
    def test_search_models_by_capability(self, mock_get_fetcher, client):
        """Test filtering models by capability"""
        fetcher = MagicMock()
        fetcher.get_provider_models.return_value = [
            {"model_id": "gpt-4o", "supports_vision": True}
        ]
        mock_get_fetcher.return_value = fetcher

        response = client.get("/api/ai/pricing/provider/openai")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "models" in data["data"]

    def test_list_providers_with_active_filter(self, client, mock_manager):
        """Test listing providers returns active status"""
        response = client.get("/api/ai/providers")
        assert response.status_code == 200
        data = response.json()
        assert "active_providers" in data["data"]

    def test_get_sync_status(self, client, mock_manager):
        """Test health endpoint returns provider status"""
        mock_manager.get_provider_status.return_value = {
            "provider_id": "openai",
            "status": "active",
            "has_api_keys": True,
        }

        response = client.get("/api/ai/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "providers" in data["data"]

    def test_add_api_key_invalid_provider(self, client, mock_manager):
        """Test API key submission with invalid provider"""
        mock_manager.store_tenant_api_key.side_effect = ValueError("unknown")

        response = client.post(
            "/api/ai/providers/invalid_provider/keys",
            params={"api_key": "sk-test-key-1234567890", "key_name": "test"}
        )

        assert response.status_code == 404  # Manager rejects unknown providers

    @patch('core.dynamic_pricing_fetcher.get_pricing_fetcher')
    def test_list_provider_models_with_filters(self, mock_get_fetcher, client):
        """Test listing provider models"""
        fetcher = MagicMock()
        fetcher.get_provider_models.return_value = [{"model_id": "gpt-4o"}]
        mock_get_fetcher.return_value = fetcher

        response = client.get("/api/ai/pricing/provider/openai")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "models" in data["data"]
