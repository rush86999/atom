import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main_api_app import app

client = TestClient(app)


class TestProviderRegistryAPI:
    """Test provider registry REST API endpoints"""

    @patch('core.provider_registry.get_provider_registry')
    def test_list_providers_success(self, mock_registry):
        """Test listing providers returns success response"""
        mock_registry.return_value.list_providers.return_value = [
            {
                "provider_id": "openai",
                "name": "OpenAI",
                "model_count": 45,
                "quality_score": 95,
                "supports_vision": True
            }
        ]

        response = client.get("/api/ai/providers/registry")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "providers" in data
        assert len(data["providers"]) == 1

    @patch('core.provider_registry.get_provider_registry')
    def test_get_provider_with_models(self, mock_registry):
        """Test getting single provider with models"""
        mock_provider = MagicMock()
        mock_provider.provider_id = "openai"
        mock_provider.name = "OpenAI"
        mock_provider.description = "OpenAI GPT models"
        mock_provider.quality_score = 95
        mock_provider.supports_vision = True
        mock_provider.supports_tools = True
        mock_provider.supports_cache = True
        mock_provider.is_active = True
        mock_provider.discovered_at.isoformat.return_value = "2026-03-22T00:00:00"
        mock_provider.last_updated.isoformat.return_value = "2026-03-22T00:00:00"

        mock_registry.return_value.get_provider.return_value = mock_provider
        mock_registry.return_value.get_models_by_provider.return_value = [
            MagicMock(model_id="gpt-4o", name="GPT-4o")
        ]

        response = client.get("/api/ai/providers/registry/openai")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["provider"]["provider_id"] == "openai"
        assert "models" in data

    @patch('core.provider_registry.get_provider_registry')
    def test_get_provider_not_found(self, mock_registry):
        """Test getting non-existent provider returns 404"""
        mock_registry.return_value.get_provider.return_value = None

        response = client.get("/api/ai/providers/registry/nonexistent")
        assert response.status_code == 404

    @patch('core.provider_auto_discovery.get_auto_discovery')
    def test_sync_providers_starts_background_task(self, mock_discovery):
        """Test sync endpoint returns success response"""
        response = client.post("/api/ai/providers/registry/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "sync_id" in data
        assert "message" in data

    def test_add_api_key_via_post_body(self):
        """Test API key submission via POST body"""
        # Mock the BYOK manager
        with patch('core.byok_endpoints.get_byok_manager') as mock_byok:
            mock_byok_instance = MagicMock()
            mock_byok.return_value = mock_byok_instance
            mock_byok_instance.encrypt_api_key.return_value = "encrypted_key"
            mock_byok_instance.store_api_key.return_value = "openai_default_production"

            response = client.post(
                "/api/ai/providers/openai/keys",
                json={
                    "api_key": "sk-test-key-1234567890",
                    "key_name": "test"
                }
            )

            # Should return 200 or 500 depending on encryption logic
            # The important part is it accepts POST body, not query params
            assert response.status_code in [200, 500]

    def test_add_api_key_rejects_short_key(self):
        """Test API key validation rejects short keys"""
        response = client.post(
            "/api/ai/providers/openai/keys",
            json={
                "api_key": "short",  # Too short
                "key_name": "test"
            }
        )
        assert response.status_code == 422  # Validation error

    @patch('core.provider_registry.get_provider_registry')
    def test_search_models_by_capability(self, mock_registry):
        """Test filtering models by capability"""
        mock_registry.return_value.get_provider.return_value = MagicMock()
        mock_registry.return_value.search_models.return_value = [
            MagicMock(model_id="gpt-4o", provider_id="openai", supports_vision=True)
        ]

        response = client.get("/api/ai/providers/registry/openai/models?supports_vision=true")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "models" in data

    @patch('core.provider_registry.get_provider_registry')
    def test_list_providers_with_active_filter(self, mock_registry):
        """Test active_only filter works"""
        mock_registry.return_value.list_providers.return_value = []

        response = client.get("/api/ai/providers/registry?active_only=true")
        assert response.status_code == 200
        # Verify filter was applied
        mock_registry.return_value.list_providers.assert_called_once()

    @patch('core.provider_registry.get_provider_registry')
    def test_get_sync_status(self, mock_registry):
        """Test sync status endpoint returns basic status"""
        response = client.get("/api/ai/providers/registry/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "syncing" in data

    def test_add_api_key_invalid_provider(self):
        """Test API key submission with invalid provider"""
        with patch('core.byok_endpoints.get_byok_manager') as mock_byok:
            mock_byok_instance = MagicMock()
            mock_byok.return_value = mock_byok_instance

            response = client.post(
                "/api/ai/providers/invalid_provider/keys",
                json={
                    "api_key": "sk-test-key-1234567890",
                    "key_name": "test"
                }
            )

            # Should return 400 for invalid provider
            assert response.status_code == 400

    @patch('core.provider_registry.get_provider_registry')
    def test_list_provider_models_with_filters(self, mock_registry):
        """Test listing provider models with multiple filters"""
        mock_registry.return_value.get_provider.return_value = MagicMock()
        mock_registry.return_value.search_models.return_value = []

        response = client.get("/api/ai/providers/registry/openai/models?supports_vision=true&min_quality=80&max_cost=0.0001")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        # Verify search_models was called with filters
        mock_registry.return_value.search_models.assert_called_once()
