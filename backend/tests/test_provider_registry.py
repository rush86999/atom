import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from core.provider_registry import ProviderRegistryService, get_provider_registry
from core.provider_auto_discovery import ProviderAutoDiscovery, get_auto_discovery
from core.models import ProviderRegistry, ModelCatalog
from core.database import get_db_session


@pytest.fixture
def db_session():
    """Provide a test database session"""
    with get_db_session() as db:
        yield db


class TestProviderRegistryService:
    """Test ProviderRegistryService CRUD operations"""

    def test_create_provider(self, db_session):
        """Test creating a new provider"""
        service = ProviderRegistryService(db_session)
        provider = service.create_provider({
            "provider_id": "test_provider",
            "name": "Test Provider",
            "quality_score": 90.0
        })
        assert provider.provider_id == "test_provider"
        assert provider.name == "Test Provider"
        assert provider.quality_score == 90.0
        assert provider.is_active is True

    def test_upsert_provider_updates_existing(self, db_session):
        """Test upsert updates existing provider"""
        service = ProviderRegistryService(db_session)
        service.create_provider({"provider_id": "test", "name": "Original"})
        updated = service.upsert_provider({"provider_id": "test", "name": "Updated", "quality_score": 95.0})
        assert updated.name == "Updated"
        assert updated.quality_score == 95.0

    def test_upsert_provider_creates_new(self, db_session):
        """Test upsert creates new provider if not exists"""
        service = ProviderRegistryService(db_session)
        provider = service.upsert_provider({
            "provider_id": "new_provider",
            "name": "New Provider",
            "quality_score": 85.0
        })
        assert provider.provider_id == "new_provider"
        assert provider.name == "New Provider"

    def test_create_model_with_relationship(self, db_session):
        """Test creating model with provider relationship"""
        service = ProviderRegistryService(db_session)
        service.create_provider({"provider_id": "test_prov", "name": "Test"})
        model = service.create_model({
            "model_id": "test-model",
            "provider_id": "test_prov",
            "input_cost_per_token": 0.0001
        })
        assert model.model_id == "test-model"
        assert model.provider_id == "test_prov"
        assert model.input_cost_per_token == 0.0001

    def test_upsert_model_updates_existing(self, db_session):
        """Test upsert updates existing model"""
        service = ProviderRegistryService(db_session)
        service.create_provider({"provider_id": "test", "name": "Test"})
        service.create_model({
            "model_id": "test-model",
            "provider_id": "test",
            "input_cost_per_token": 0.0001
        })
        updated = service.upsert_model({
            "model_id": "test-model",
            "provider_id": "test",
            "input_cost_per_token": 0.0002
        })
        assert updated.input_cost_per_token == 0.0002

    def test_list_providers_includes_model_count(self, db_session):
        """Test list_providers returns model counts"""
        service = ProviderRegistryService(db_session)
        service.create_provider({"provider_id": "test", "name": "Test Provider"})
        service.create_model({"model_id": "m1", "provider_id": "test", "mode": "chat"})
        service.create_model({"model_id": "m2", "provider_id": "test", "mode": "chat"})
        service.create_model({"model_id": "m3", "provider_id": "test", "mode": "vision"})

        providers = service.list_providers(active_only=True)
        assert len(providers) == 1
        assert providers[0]["provider_id"] == "test"
        assert providers[0]["model_count"] == 3

    def test_list_providers_active_only_filter(self, db_session):
        """Test list_providers filters by is_active"""
        service = ProviderRegistryService(db_session)
        service.create_provider({"provider_id": "active_provider", "name": "Active", "is_active": True})
        service.create_provider({"provider_id": "inactive_provider", "name": "Inactive", "is_active": False})

        active_providers = service.list_providers(active_only=True)
        all_providers = service.list_providers(active_only=False)

        assert len(active_providers) == 1
        assert active_providers[0]["provider_id"] == "active_provider"
        assert len(all_providers) == 2

    def test_search_models_by_capability(self, db_session):
        """Test search_models filters by capabilities"""
        service = ProviderRegistryService(db_session)
        service.create_provider({
            "provider_id": "vision_provider",
            "name": "Vision",
            "supports_vision": True,
            "quality_score": 90.0
        })
        service.create_model({
            "model_id": "vision-model",
            "provider_id": "vision_provider",
            "input_cost_per_token": 0.0001
        })

        results = service.search_models({"supports_vision": True})
        assert len(results) >= 1
        assert results[0].model_id == "vision-model"

    def test_search_models_by_min_quality(self, db_session):
        """Test search_models filters by quality score"""
        service = ProviderRegistryService(db_session)
        service.create_provider({
            "provider_id": "high_quality",
            "name": "High Quality",
            "quality_score": 95.0
        })
        service.create_provider({
            "provider_id": "low_quality",
            "name": "Low Quality",
            "quality_score": 70.0
        })
        service.create_model({"model_id": "high-model", "provider_id": "high_quality"})
        service.create_model({"model_id": "low-model", "provider_id": "low_quality"})

        results = service.search_models({"min_quality": 80.0})
        assert len(results) >= 1
        assert results[0].model_id == "high-model"

    def test_search_models_by_max_cost(self, db_session):
        """Test search_models filters by cost"""
        service = ProviderRegistryService(db_session)
        service.create_provider({"provider_id": "test", "name": "Test"})
        service.create_model({
            "model_id": "cheap-model",
            "provider_id": "test",
            "input_cost_per_token": 0.00001
        })
        service.create_model({
            "model_id": "expensive-model",
            "provider_id": "test",
            "input_cost_per_token": 0.001
        })

        results = service.search_models({"max_cost": 0.0001})
        model_ids = [m.model_id for m in results]
        assert "cheap-model" in model_ids
        assert "expensive-model" not in model_ids

    def test_get_provider_stats(self, db_session):
        """Test get_provider_stats returns statistics"""
        service = ProviderRegistryService(db_session)
        service.create_provider({
            "provider_id": "test",
            "name": "Test Provider",
            "supports_vision": True,
            "supports_tools": True,
            "quality_score": 88.0
        })
        service.create_model({
            "model_id": "m1",
            "provider_id": "test",
            "input_cost_per_token": 0.0001,
            "output_cost_per_token": 0.0002
        })
        service.create_model({
            "model_id": "m2",
            "provider_id": "test",
            "input_cost_per_token": 0.00015,
            "output_cost_per_token": 0.00025
        })

        stats = service.get_provider_stats("test")
        assert stats["provider_id"] == "test"
        assert stats["model_count"] == 2
        assert stats["avg_input_cost_per_token"] == 0.000125
        assert stats["avg_output_cost_per_token"] == 0.000225
        assert stats["supports_vision"] is True
        assert stats["quality_score"] == 88.0

    def test_soft_delete_provider(self, db_session):
        """Test delete_provider soft deletes (sets is_active=False)"""
        service = ProviderRegistryService(db_session)
        service.create_provider({"provider_id": "test", "name": "Test"})
        service.delete_provider("test")

        provider = service.get_provider("test")
        assert provider is not None
        assert provider.is_active is False

    def test_get_provider_returns_none_for_nonexistent(self, db_session):
        """Test get_provider returns None for non-existent provider"""
        service = ProviderRegistryService(db_session)
        provider = service.get_provider("nonexistent")
        assert provider is None

    def test_get_models_by_provider(self, db_session):
        """Test get_models_by_provider returns all models for provider"""
        service = ProviderRegistryService(db_session)
        service.create_provider({"provider_id": "test", "name": "Test"})
        service.create_model({"model_id": "m1", "provider_id": "test"})
        service.create_model({"model_id": "m2", "provider_id": "test"})

        models = service.get_models_by_provider("test")
        assert len(models) == 2
        model_ids = [m.model_id for m in models]
        assert "m1" in model_ids
        assert "m2" in model_ids

    def test_update_provider(self, db_session):
        """Test update_provider updates fields"""
        service = ProviderRegistryService(db_session)
        service.create_provider({
            "provider_id": "test",
            "name": "Original Name",
            "quality_score": 80.0
        })
        updated = service.update_provider("test", {
            "name": "Updated Name",
            "quality_score": 90.0
        })
        assert updated.name == "Updated Name"
        assert updated.quality_score == 90.0

    def test_singleton_pattern(self, db_session):
        """Test get_provider_registry returns singleton instance"""
        registry1 = get_provider_registry(db_session)
        registry2 = get_provider_registry(db_session)
        assert registry1 is registry2


class TestProviderAutoDiscovery:
    """Test ProviderAutoDiscovery sync logic"""

    def test_extract_provider_from_model(self):
        """Test _extract_provider_from_model extracts correct data"""
        discovery = ProviderAutoDiscovery()
        pricing = {
            "litellm_provider": "openai",
            "supports_cache": True,
            "supports_vision": False,
            "supports_function_calling": True
        }
        provider = discovery._extract_provider_from_model("gpt-4o", pricing)
        assert provider is not None
        assert provider["provider_id"] == "openai"
        assert provider["name"] == "Openai"
        assert provider["supports_cache"] is True
        assert provider["supports_vision"] is False
        assert provider["supports_tools"] is True

    def test_extract_provider_returns_none_for_unknown(self):
        """Test _extract_provider_from_model returns None for unknown provider"""
        discovery = ProviderAutoDiscovery()
        pricing = {"litellm_provider": "unknown"}
        provider = discovery._extract_provider_from_model("unknown-model", pricing)
        assert provider is None

    def test_extract_model_from_pricing(self):
        """Test _extract_model_from_pricing extracts correct data"""
        discovery = ProviderAutoDiscovery()
        pricing = {
            "litellm_provider": "anthropic",
            "input_cost_per_token": 0.00001,
            "output_cost_per_token": 0.00002,
            "max_tokens": 4096,
            "context_window": 200000,
            "mode": "chat",
            "source": "litellm"
        }
        model = discovery._extract_model_from_pricing("claude-3-5-sonnet", pricing)
        assert model is not None
        assert model["model_id"] == "claude-3-5-sonnet"
        assert model["provider_id"] == "anthropic"
        assert model["input_cost_per_token"] == 0.00001
        assert model["output_cost_per_token"] == 0.00002
        assert model["max_tokens"] == 4096
        assert model["context_window"] == 200000
        assert model["mode"] == "chat"
        assert model["source"] == "litellm"

    def test_extract_model_returns_none_for_unknown_provider(self):
        """Test _extract_model_from_pricing returns None for unknown provider"""
        discovery = ProviderAutoDiscovery()
        pricing = {"litellm_provider": "unknown"}
        model = discovery._extract_model_from_pricing("unknown-model", pricing)
        assert model is None

    @patch('core.provider_auto_discovery.get_pricing_fetcher')
    @patch('core.provider_auto_discovery.get_provider_registry')
    @pytest.mark.asyncio
    async def test_sync_providers_from_pricing_fetcher(self, mock_registry, mock_fetcher):
        """Test sync_providers processes pricing cache correctly"""
        # Mock DynamicPricingFetcher
        mock_fetcher_instance = Mock()
        mock_fetcher_instance.pricing_cache = {
            "gpt-4o": {
                "litellm_provider": "openai",
                "input_cost_per_token": 0.00001,
                "output_cost_per_token": 0.00002,
                "supports_cache": True,
                "mode": "chat"
            },
            "claude-3-5-sonnet": {
                "litellm_provider": "anthropic",
                "input_cost_per_token": 0.000003,
                "output_cost_per_token": 0.000015,
                "supports_cache": True,
                "mode": "chat"
            }
        }
        mock_fetcher_instance.refresh_pricing = AsyncMock()
        mock_fetcher.return_value = mock_fetcher_instance

        # Mock ProviderRegistry
        mock_registry_instance = Mock()
        mock_registry_instance.upsert_provider = Mock()
        mock_registry_instance.upsert_model = Mock()
        mock_registry.return_value = mock_registry_instance

        # Run sync
        discovery = ProviderAutoDiscovery()
        result = await discovery.sync_providers()

        # Verify results
        assert "providers_synced" in result
        assert "models_synced" in result
        assert result["providers_synced"] == 2  # openai, anthropic
        assert result["models_synced"] == 2  # gpt-4o, claude-3-5-sonnet

    @patch('core.provider_auto_discovery.get_pricing_fetcher')
    @patch('core.provider_auto_discovery.get_provider_registry')
    @pytest.mark.asyncio
    async def test_sync_single_provider_filters_correctly(self, mock_registry, mock_fetcher):
        """Test sync_single_provider only syncs specified provider"""
        # Mock DynamicPricingFetcher
        mock_fetcher_instance = Mock()
        mock_fetcher_instance.pricing_cache = {
            "gpt-4o": {"litellm_provider": "openai"},
            "gpt-4o-mini": {"litellm_provider": "openai"},
            "claude-3-5-sonnet": {"litellm_provider": "anthropic"}
        }
        mock_fetcher_instance.refresh_pricing = AsyncMock()
        mock_fetcher.return_value = mock_fetcher_instance

        # Mock ProviderRegistry
        mock_registry_instance = Mock()
        mock_registry_instance.upsert_model = Mock()
        mock_registry.return_value = mock_registry_instance

        # Run sync for openai only
        discovery = ProviderAutoDiscovery()
        result = await discovery.sync_single_provider("openai")

        # Verify only openai models synced
        assert result["provider_id"] == "openai"
        assert result["models_synced"] == 2  # gpt-4o, gpt-4o-mini
        assert mock_registry_instance.upsert_model.call_count == 2

    def test_singleton_pattern_auto_discovery(self):
        """Test get_auto_discovery returns singleton instance"""
        discovery1 = get_auto_discovery()
        discovery2 = get_auto_discovery()
        assert discovery1 is discovery2
