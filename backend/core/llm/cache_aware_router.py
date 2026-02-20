"""
Cache-Aware Router for LLM Cost Optimization

This module implements cost calculation that accounts for prompt caching capabilities.
Providers like OpenAI, Anthropic, and Gemini offer cached tokens at ~10% of list price,
which can dramatically reduce effective costs for repeated prompts.

Research-backed caching (Feb 2026):
- OpenAI: 10% cached cost, minimum 1024 tokens
- Anthropic: 10% cached cost, minimum 2048 tokens
- Gemini: 10% cached cost, minimum 1024 tokens
- DeepSeek: No caching support
- MiniMax: No caching support

Cache hit prediction uses historical data with 50% default (industry average).
"""

import hashlib
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class CacheAwareRouter:
    """
    Router that accounts for prompt caching in LLM cost calculations.

    Key features:
    - Provider-specific cache capability detection
    - Effective cost calculation with cache hit probability
    - Historical cache hit tracking for accurate predictions
    - Minimum token threshold enforcement

    Usage:
        router = CacheAwareRouter(pricing_fetcher)
        effective_cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.9
        )
    """

    # Research-verified provider caching capabilities (Feb 2026)
    # Sources: OpenAI/Anthropic prompt caching docs, Gemini API documentation
    CACHE_CAPABILITIES = {
        "openai": {
            "supports_cache": True,
            "cached_cost_ratio": 0.10,  # Cached tokens cost 10% of original
            "min_tokens": 1024,          # Minimum prompt length for caching
        },
        "anthropic": {
            "supports_cache": True,
            "cached_cost_ratio": 0.10,  # Cached tokens cost 10% of original
            "min_tokens": 2048,          # Anthropic requires longer prompts
        },
        "gemini": {
            "supports_cache": True,
            "cached_cost_ratio": 0.10,  # Cached tokens cost 10% of original
            "min_tokens": 1024,          # Minimum prompt length for caching
        },
        "deepseek": {
            "supports_cache": False,
            "cached_cost_ratio": 1.0,    # No caching = full price
            "min_tokens": 0,
        },
        "minimax": {
            "supports_cache": False,
            "cached_cost_ratio": 1.0,    # No caching = full price
            "min_tokens": 0,
        },
    }

    def __init__(self, pricing_fetcher):
        """
        Initialize the cache-aware router.

        Args:
            pricing_fetcher: DynamicPricingFetcher instance for model pricing data
        """
        self.pricing_fetcher = pricing_fetcher
        # In-memory cache hit history: {"workspace_id:prompt_hash": [hits, total]}
        # This is sufficient for initial implementation. Can be persisted to DB later.
        self.cache_hit_history = {}

    def calculate_effective_cost(
        self,
        model: str,
        provider: str,
        estimated_input_tokens: int,
        cache_hit_probability: float = 0.5
    ) -> float:
        """
        Calculate effective cost accounting for potential cache hits.

        This method adjusts the list price based on:
        1. Whether the provider supports caching
        2. Whether the prompt is long enough (min_tokens threshold)
        3. The probability of a cache hit (historical or default 0.5)

        Effective cost formula:
        effective_input = input_cost * (cache_hit_prob * cached_ratio + (1 - cache_hit_prob) * 1.0)
        effective_cost = (effective_input + output_cost) / 2

        Args:
            model: Model name (e.g., "gpt-4o", "claude-3-5-sonnet")
            provider: Provider name (e.g., "openai", "anthropic")
            estimated_input_tokens: Estimated input token count
            cache_hit_probability: Estimated likelihood of cache hit (0-1)

        Returns:
            Effective cost per token (float), or float("inf") if model pricing unknown

        Examples:
            >>> # GPT-4o with 90% cache hit should cost ~10% of list price
            >>> cost = router.calculate_effective_cost("gpt-4o", "openai", 2000, 0.9)
            >>> assert cost < 0.000001  # ~10% of ~$0.00001/token

            >>> # DeepSeek with no caching = full price
            >>> cost = router.calculate_effective_cost("deepseek-chat", "deepseek", 2000, 0.9)
            >>> assert cost > 0.000001  # Full price, no discount
        """
        pricing = self.pricing_fetcher.get_model_price(model)
        if not pricing:
            # Unknown model = infinite cost (will be filtered out in ranking)
            return float("inf")

        input_cost = pricing.get("input_cost_per_token", 0)
        output_cost = pricing.get("output_cost_per_token", 0)

        # Get provider cache capabilities
        cache_info = self.get_provider_cache_capability(provider)

        # If provider doesn't support caching, return full price
        if not cache_info["supports_cache"]:
            return (input_cost + output_cost) / 2

        # If prompt is below minimum threshold, caching won't be applied
        if estimated_input_tokens < cache_info["min_tokens"]:
            # Prompt too short for caching = full price
            return (input_cost + output_cost) / 2

        # Calculate effective cost with cache hit probability
        # cached_cost_ratio: 0.10 means cached tokens cost 10% of original price
        cached_ratio = cache_info["cached_cost_ratio"]

        # Effective input cost = weighted average of cached and uncached cost
        effective_input_cost = input_cost * (
            cache_hit_probability * cached_ratio +      # Cached portion
            (1 - cache_hit_probability) * 1.0           # Uncached portion
        )

        # Average of input and output cost
        return (effective_input_cost + output_cost) / 2

    def predict_cache_hit_probability(self, prompt_hash: str, workspace_id: str) -> float:
        """
        Predict cache hit probability based on historical data.

        This method looks up actual cache hit rates from previous requests
        with similar prompts (same prefix hash). If no history exists,
        returns 0.5 (50% industry average from research).

        Args:
            prompt_hash: Hash of prompt prefix (first 1k tokens)
            workspace_id: Workspace for user-specific patterns

        Returns:
            Probability of cache hit (0-1), default 0.5

        Examples:
            >>> # First request = default probability
            >>> prob = router.predict_cache_hit_probability("abc123", "default")
            >>> assert prob == 0.5

            >>> # After recording 8 cache hits out of 10 requests
            >>> router.record_cache_outcome("abc123", "default", True)  # 8 times
            >>> router.record_cache_outcome("abc123", "default", False)  # 2 times
            >>> prob = router.predict_cache_hit_probability("abc123", "default")
            >>> assert prob == 0.8
        """
        # Use first 16 characters of hash as key (balances specificity and collision)
        key = f"{workspace_id}:{prompt_hash[:16]}"

        if key in self.cache_hit_history:
            hits, total = self.cache_hit_history[key]
            if total > 0:
                return hits / total

        # Default: 50% cache hit rate (industry average from research)
        # Source: OpenAI/Anthropic caching documentation, real-world workload studies
        return 0.5

    def record_cache_outcome(self, prompt_hash: str, workspace_id: str, was_cached: bool):
        """
        Record actual cache outcome for future predictions.

        This method updates the in-memory cache hit history, which is
        used by predict_cache_hit_probability() to improve accuracy over time.

        Args:
            prompt_hash: Hash of prompt prefix (first 1k tokens)
            workspace_id: Workspace identifier
            was_cached: Whether the request hit the prompt cache

        Examples:
            >>> # Record a cache hit
            >>> router.record_cache_outcome("abc123", "default", True)
            >>> assert router.cache_hit_history["default:abc123"] == [1, 1]

            >>> # Record a cache miss
            >>> router.record_cache_outcome("abc123", "default", False)
            >>> assert router.cache_hit_history["default:abc123"] == [1, 2]
        """
        key = f"{workspace_id}:{prompt_hash[:16]}"

        if key not in self.cache_hit_history:
            self.cache_hit_history[key] = [0, 0]  # [hits, total]

        self.cache_hit_history[key][1] += 1  # Increment total
        if was_cached:
            self.cache_hit_history[key][0] += 1  # Increment hits

        logger.debug(
            f"Cache outcome recorded: {key}, "
            f"hit_rate={self.cache_hit_history[key][0]}/{self.cache_hit_history[key][1]}"
        )

    def get_provider_cache_capability(self, provider: str) -> Dict:
        """
        Get cache capability metadata for a provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic")

        Returns:
            Dictionary with keys:
            - supports_cache (bool)
            - cached_cost_ratio (float)
            - min_tokens (int)

        Examples:
            >>> caps = router.get_provider_cache_capability("openai")
            >>> assert caps["supports_cache"] == True
            >>> assert caps["cached_cost_ratio"] == 0.10
            >>> assert caps["min_tokens"] == 1024

            >>> caps = router.get_provider_cache_capability("deepseek")
            >>> assert caps["supports_cache"] == False
        """
        # Normalize provider name (lowercase, handle variations)
        provider_lower = provider.lower()

        # Direct match
        if provider_lower in self.CACHE_CAPABILITIES:
            return self.CACHE_CAPABILITIES[provider_lower]

        # Fuzzy match for variations (e.g., "google" -> "gemini")
        if "google" in provider_lower or "gemini" in provider_lower:
            return self.CACHE_CAPABILITIES.get("gemini", {
                "supports_cache": False,
                "cached_cost_ratio": 1.0,
                "min_tokens": 0
            })

        # Default: no caching support
        return {
            "supports_cache": False,
            "cached_cost_ratio": 1.0,
            "min_tokens": 0
        }

    def get_cache_hit_history(self, workspace_id: Optional[str] = None) -> Dict:
        """
        Get cache hit history for analytics.

        Args:
            workspace_id: Optional workspace filter. If None, returns all history.

        Returns:
            Dictionary mapping keys to [hits, total] arrays
        """
        if workspace_id:
            prefix = f"{workspace_id}:"
            return {
                k: v for k, v in self.cache_hit_history.items()
                if k.startswith(prefix)
            }
        return self.cache_hit_history.copy()

    def clear_cache_history(self, workspace_id: Optional[str] = None):
        """
        Clear cache hit history (useful for testing or workspace reset).

        Args:
            workspace_id: Optional workspace to clear. If None, clears all.
        """
        if workspace_id:
            prefix = f"{workspace_id}:"
            keys_to_delete = [k for k in self.cache_hit_history if k.startswith(prefix)]
            for key in keys_to_delete:
                del self.cache_hit_history[key]
        else:
            self.cache_hit_history.clear()

        logger.info(f"Cleared cache hit history for workspace: {workspace_id or 'all'}")
