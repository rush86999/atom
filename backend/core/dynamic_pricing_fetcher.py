"""
Dynamic AI Provider Pricing Fetcher
Fetches real-time pricing from LiteLLM's maintained pricing database and OpenRouter API.
"""

import asyncio
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# LiteLLM pricing database URL (regularly maintained)
LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

# OpenRouter models endpoint
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Cache file path
PRICING_CACHE_PATH = Path("./data/ai_pricing_cache.json")

# Cache duration (24 hours)
CACHE_DURATION_HOURS = 24


class DynamicPricingFetcher:
    """
    Fetches and caches AI provider pricing from multiple sources.
    Primary: LiteLLM's model_prices database
    Fallback: OpenRouter API
    """
    
    def __init__(self):
        self.pricing_cache: Dict[str, Any] = {}
        self.last_fetch: Optional[datetime] = None
        self._load_cache()
    
    def _load_cache(self):
        """Load pricing from local cache file"""
        try:
            if PRICING_CACHE_PATH.exists():
                with open(PRICING_CACHE_PATH, 'r') as f:
                    data = json.load(f)
                    self.pricing_cache = data.get("pricing", {})
                    last_fetch_str = data.get("last_fetch")
                    if last_fetch_str:
                        self.last_fetch = datetime.fromisoformat(last_fetch_str)
                    logger.info(f"Loaded {len(self.pricing_cache)} model prices from cache")
        except Exception as e:
            logger.warning(f"Could not load pricing cache: {e}")
    
    def _save_cache(self):
        """Save pricing to local cache file"""
        try:
            PRICING_CACHE_PATH.parent.mkdir(exist_ok=True)
            data = {
                "pricing": self.pricing_cache,
                "last_fetch": self.last_fetch.isoformat() if self.last_fetch else None,
                "source": "litellm+openrouter"
            }
            with open(PRICING_CACHE_PATH, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.pricing_cache)} model prices to cache")
        except Exception as e:
            logger.error(f"Could not save pricing cache: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if not self.last_fetch or not self.pricing_cache:
            return False
        age = datetime.now() - self.last_fetch
        return age < timedelta(hours=CACHE_DURATION_HOURS)
    
    async def fetch_litellm_pricing(self) -> Dict[str, Any]:
        """Fetch pricing from LiteLLM's GitHub repository"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(LITELLM_PRICING_URL)
                response.raise_for_status()
                data = response.json()
                
                # Transform to our format
                pricing = {}
                for model_name, model_data in data.items():
                    if isinstance(model_data, dict):
                        pricing[model_name] = {
                            "input_cost_per_token": model_data.get("input_cost_per_token", 0),
                            "output_cost_per_token": model_data.get("output_cost_per_token", 0),
                            "max_tokens": model_data.get("max_tokens", 0),
                            "max_input_tokens": model_data.get("max_input_tokens", 0),
                            "max_output_tokens": model_data.get("max_output_tokens", 0),
                            "litellm_provider": model_data.get("litellm_provider", "unknown"),
                            "mode": model_data.get("mode", "chat"),
                            "source": "litellm"
                        }
                
                logger.info(f"Fetched {len(pricing)} model prices from LiteLLM")
                return pricing
                
        except Exception as e:
            logger.error(f"Failed to fetch LiteLLM pricing: {e}")
            return {}
    
    async def fetch_openrouter_pricing(self) -> Dict[str, Any]:
        """Fetch pricing from OpenRouter API"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(OPENROUTER_MODELS_URL)
                response.raise_for_status()
                data = response.json()
                
                pricing = {}
                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    model_pricing = model.get("pricing", {})
                    
                    pricing[model_id] = {
                        "input_cost_per_token": float(model_pricing.get("prompt", 0)),
                        "output_cost_per_token": float(model_pricing.get("completion", 0)),
                        "max_tokens": model.get("context_length", 0),
                        "name": model.get("name", model_id),
                        "description": model.get("description", ""),
                        "source": "openrouter"
                    }
                
                logger.info(f"Fetched {len(pricing)} model prices from OpenRouter")
                return pricing
                
        except Exception as e:
            logger.error(f"Failed to fetch OpenRouter pricing: {e}")
            return {}
    
    async def refresh_pricing(self, force: bool = False) -> Dict[str, Any]:
        """
        Refresh pricing data from all sources.
        Uses cache if valid unless force=True.
        """
        if not force and self._is_cache_valid():
            logger.info("Using cached pricing data")
            return self.pricing_cache
        
        # Fetch from both sources
        litellm_pricing = await self.fetch_litellm_pricing()
        openrouter_pricing = await self.fetch_openrouter_pricing()
        
        # Merge pricing (LiteLLM takes precedence)
        self.pricing_cache = {**openrouter_pricing, **litellm_pricing}
        self.last_fetch = datetime.now()
        
        # Save to cache
        self._save_cache()
        
        return self.pricing_cache
    
    def get_model_price(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get pricing for a specific model"""
        # Try exact match first
        if model_name in self.pricing_cache:
            return self.pricing_cache[model_name]
        
        # Try partial match (e.g., "gpt-4" matches "gpt-4-turbo")
        for cached_model, pricing in self.pricing_cache.items():
            if model_name in cached_model or cached_model in model_name:
                return pricing
        
        return None
    
    def get_provider_models(self, provider: str) -> List[Dict[str, Any]]:
        """Get all models for a specific provider"""
        models = []
        provider_lower = provider.lower()
        
        for model_name, pricing in self.pricing_cache.items():
            litellm_provider = pricing.get("litellm_provider", "").lower()
            if provider_lower in model_name.lower() or provider_lower in litellm_provider:
                models.append({
                    "model": model_name,
                    **pricing
                })
        
        # Sort by input cost
        models.sort(key=lambda x: x.get("input_cost_per_token", float("inf")))
        return models
    
    def get_cheapest_models(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the cheapest models across all providers"""
        models = []
        
        for model_name, pricing in self.pricing_cache.items():
            input_cost = pricing.get("input_cost_per_token", 0)
            output_cost = pricing.get("output_cost_per_token", 0)
            
            # Skip models with zero cost (usually local/self-hosted)
            if input_cost > 0 or output_cost > 0:
                models.append({
                    "model": model_name,
                    "avg_cost": (input_cost + output_cost) / 2,
                    **pricing
                })
        
        models.sort(key=lambda x: x.get("avg_cost", float("inf")))
        return models[:limit]
    
    def compare_providers(self) -> Dict[str, Dict[str, Any]]:
        """Compare average costs across providers"""
        provider_costs: Dict[str, List[float]] = {}
        
        for model_name, pricing in self.pricing_cache.items():
            provider = pricing.get("litellm_provider", "unknown")
            if not provider:
                # Try to extract from model name
                if "gpt" in model_name.lower() or "openai" in model_name.lower():
                    provider = "openai"
                elif "claude" in model_name.lower() or "anthropic" in model_name.lower():
                    provider = "anthropic"
                elif "deepseek" in model_name.lower():
                    provider = "deepseek"
                elif "gemini" in model_name.lower():
                    provider = "google"
                else:
                    provider = "other"
            
            input_cost = pricing.get("input_cost_per_token", 0)
            output_cost = pricing.get("output_cost_per_token", 0)
            
            if input_cost > 0:
                if provider not in provider_costs:
                    provider_costs[provider] = []
                provider_costs[provider].append((input_cost + output_cost) / 2)
        
        # Calculate averages and ranges
        comparison = {}
        for provider, costs in provider_costs.items():
            if costs:
                comparison[provider] = {
                    "avg_cost_per_token": sum(costs) / len(costs),
                    "min_cost_per_token": min(costs),
                    "max_cost_per_token": max(costs),
                    "model_count": len(costs)
                }
        
        return comparison
    
    def estimate_cost(self, model_name: str, input_tokens: int, output_tokens: int) -> Optional[float]:
        """Estimate cost for a specific request"""
        pricing = self.get_model_price(model_name)
        if not pricing:
            return None
        
        input_cost = pricing.get("input_cost_per_token", 0) * input_tokens
        output_cost = pricing.get("output_cost_per_token", 0) * output_tokens
        
        return input_cost + output_cost


# Singleton instance
_pricing_fetcher: Optional[DynamicPricingFetcher] = None


def get_pricing_fetcher() -> DynamicPricingFetcher:
    """Get the singleton pricing fetcher instance"""
    global _pricing_fetcher
    if _pricing_fetcher is None:
        _pricing_fetcher = DynamicPricingFetcher()
    return _pricing_fetcher


async def refresh_pricing_cache(force: bool = False) -> Dict[str, Any]:
    """Convenience function to refresh pricing cache"""
    fetcher = get_pricing_fetcher()
    return await fetcher.refresh_pricing(force=force)
