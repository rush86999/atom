from typing import Dict, List, Any, Optional
import asyncio
import logging
from core.dynamic_pricing_fetcher import get_pricing_fetcher
from core.provider_registry import get_provider_registry

logger = logging.getLogger(__name__)


class ProviderAutoDiscovery:
    """Orchestrates automatic provider discovery from DynamicPricingFetcher to ProviderRegistry"""

    def __init__(self):
        self.pricing_fetcher = get_pricing_fetcher()
        self.registry = get_provider_registry()

    async def sync_providers(self) -> Dict[str, int]:
        """Fetch latest pricing and sync to registry

        Returns:
            Dictionary with providers_synced and models_synced counts
        """
        logger.info("Starting provider sync from DynamicPricingFetcher")

        # 1. Refresh pricing cache
        await self.pricing_fetcher.refresh_pricing(force=True)
        logger.info(f"Pricing cache refreshed: {len(self.pricing_fetcher.pricing_cache)} models")

        # 2. Extract unique providers from pricing_cache
        providers_synced = 0
        models_synced = 0
        seen_providers = set()

        for model_id, pricing in self.pricing_fetcher.pricing_cache.items():
            # Extract and upsert provider
            provider = self._extract_provider_from_model(model_id, pricing)
            if provider and provider['provider_id'] not in seen_providers:
                try:
                    self.registry.upsert_provider(provider)
                    seen_providers.add(provider['provider_id'])
                    providers_synced += 1
                except Exception as e:
                    logger.error(f"Failed to upsert provider {provider.get('provider_id')}: {e}")

            # Extract and upsert model
            model = self._extract_model_from_pricing(model_id, pricing)
            if model:
                try:
                    self.registry.upsert_model(model)
                    models_synced += 1
                except Exception as e:
                    logger.error(f"Failed to upsert model {model_id}: {e}")

        logger.info(f"Synced {providers_synced} providers, {models_synced} models")
        return {"providers_synced": providers_synced, "models_synced": models_synced}

    async def sync_single_provider(self, provider_id: str) -> Dict[str, int]:
        """Sync only models for a specific provider

        Args:
            provider_id: Provider identifier (e.g., "openai", "anthropic")

        Returns:
            Dictionary with models_synced count
        """
        logger.info(f"Syncing single provider: {provider_id}")

        # 1. Refresh pricing cache
        await self.pricing_fetcher.refresh_pricing(force=True)

        # 2. Filter models by provider
        models_synced = 0
        litellm_provider = provider_id  # Map directly

        for model_id, pricing in self.pricing_fetcher.pricing_cache.items():
            if pricing.get('litellm_provider') == litellm_provider:
                model = self._extract_model_from_pricing(model_id, pricing)
                if model:
                    try:
                        self.registry.upsert_model(model)
                        models_synced += 1
                    except Exception as e:
                        logger.error(f"Failed to upsert model {model_id}: {e}")

        logger.info(f"Synced {models_synced} models for provider {provider_id}")
        return {"provider_id": provider_id, "models_synced": models_synced}

    def _extract_provider_from_model(self, model_name: str, pricing: Dict) -> Optional[Dict[str, Any]]:
        """Extract provider dict from model pricing data

        Args:
            model_name: Model identifier
            pricing: Pricing dictionary from DynamicPricingFetcher

        Returns:
            Provider dictionary for upsert or None
        """
        litellm_provider = pricing.get("litellm_provider", "unknown")
        if litellm_provider == "unknown":
            return None

        return {
            "provider_id": litellm_provider,
            "name": litellm_provider.title(),
            "litellm_provider": litellm_provider,
            "supports_cache": pricing.get("supports_cache", False),
            "supports_vision": pricing.get("supports_vision", False),
            "supports_tools": pricing.get("supports_function_calling", False),
            "is_active": True,
        }

    def _extract_model_from_pricing(self, model_name: str, pricing: Dict) -> Optional[Dict[str, Any]]:
        """Extract model dict from pricing data

        Args:
            model_name: Model identifier
            pricing: Pricing dictionary from DynamicPricingFetcher

        Returns:
            Model dictionary for upsert or None
        """
        litellm_provider = pricing.get("litellm_provider", "unknown")
        if litellm_provider == "unknown":
            return None

        return {
            "model_id": model_name,
            "provider_id": litellm_provider,
            "name": model_name,
            "description": pricing.get("description"),
            "input_cost_per_token": pricing.get("input_cost_per_token"),
            "output_cost_per_token": pricing.get("output_cost_per_token"),
            "max_tokens": pricing.get("max_tokens"),
            "max_input_tokens": pricing.get("max_input_tokens"),
            "context_window": pricing.get("context_window"),
            "mode": pricing.get("mode", "chat"),
            "source": pricing.get("source", "litellm"),
        }


# Singleton instance
_auto_discovery_instance: Optional[ProviderAutoDiscovery] = None


def get_auto_discovery() -> ProviderAutoDiscovery:
    """Get singleton ProviderAutoDiscovery instance

    Returns:
        ProviderAutoDiscovery instance
    """
    global _auto_discovery_instance
    if _auto_discovery_instance is None:
        _auto_discovery_instance = ProviderAutoDiscovery()
    return _auto_discovery_instance
