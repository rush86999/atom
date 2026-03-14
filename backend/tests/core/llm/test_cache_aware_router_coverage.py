"""
Coverage-driven tests for CacheAwareRouter (currently 0% -> target 70%+)

Focus areas from cache_aware_router.py:
- CACHE_CAPABILITIES constant (lines 45-73)
- __init__ (lines 75-85)
- get_provider_cache_capability (lines 230-272)
- calculate_effective_cost (lines 87-170)
"""

import pytest
from unittest.mock import MagicMock

from core.llm.cache_aware_router import CacheAwareRouter


class TestCacheCapabilities:
    """Test CACHE_CAPABILITIES configuration (lines 45-73)."""

    def test_cache_capabilities_openai(self):
        """Cover lines 48-52: OpenAI cache configuration."""
        openai_config = CacheAwareRouter.CACHE_CAPABILITIES["openai"]

        assert openai_config["supports_cache"] is True
        assert openai_config["cached_cost_ratio"] == 0.10  # 10% of original price
        assert openai_config["min_tokens"] == 1024

    def test_cache_capabilities_anthropic(self):
        """Cover lines 53-57: Anthropic cache configuration."""
        anthropic_config = CacheAwareRouter.CACHE_CAPABILITIES["anthropic"]

        assert anthropic_config["supports_cache"] is True
        assert anthropic_config["cached_cost_ratio"] == 0.10
        assert anthropic_config["min_tokens"] == 2048  # Higher than OpenAI

    def test_cache_capabilities_gemini(self):
        """Cover lines 58-62: Gemini cache configuration."""
        gemini_config = CacheAwareRouter.CACHE_CAPABILITIES["gemini"]

        assert gemini_config["supports_cache"] is True
        assert gemini_config["cached_cost_ratio"] == 0.10
        assert gemini_config["min_tokens"] == 1024

    def test_cache_capabilities_deepseek(self):
        """Cover lines 63-67: DeepSeek no cache support."""
        deepseek_config = CacheAwareRouter.CACHE_CAPABILITIES["deepseek"]

        assert deepseek_config["supports_cache"] is False
        assert deepseek_config["cached_cost_ratio"] == 1.0  # Full price
        assert deepseek_config["min_tokens"] == 0

    def test_cache_capabilities_minimax(self):
        """Cover lines 68-72: MiniMax no cache support."""
        minimax_config = CacheAwareRouter.CACHE_CAPABILITIES["minimax"]

        assert minimax_config["supports_cache"] is False
        assert minimax_config["cached_cost_ratio"] == 1.0
        assert minimax_config["min_tokens"] == 0

    def test_cache_capabilities_all_providers(self):
        """Verify all expected providers are configured."""
        expected_providers = ["openai", "anthropic", "gemini", "deepseek", "minimax"]

        for provider in expected_providers:
            assert provider in CacheAwareRouter.CACHE_CAPABILITIES
            assert "supports_cache" in CacheAwareRouter.CACHE_CAPABILITIES[provider]
            assert "cached_cost_ratio" in CacheAwareRouter.CACHE_CAPABILITIES[provider]
            assert "min_tokens" in CacheAwareRouter.CACHE_CAPABILITIES[provider]


class TestCacheAwareRouterInit:
    """Test CacheAwareRouter initialization (lines 75-85)."""

    def test_init_with_pricing_fetcher(self):
        """Cover lines 75-85: Initialize with pricing fetcher."""
        mock_pricing = MagicMock()

        router = CacheAwareRouter(mock_pricing)

        assert router.pricing_fetcher is mock_pricing
        assert router.cache_hit_history == {}  # Empty history initially

    def test_init_creates_history_dict(self):
        """Verify cache hit history is initialized as dict."""
        mock_pricing = MagicMock()
        router = CacheAwareRouter(mock_pricing)

        assert isinstance(router.cache_hit_history, dict)
        assert len(router.cache_hit_history) == 0
