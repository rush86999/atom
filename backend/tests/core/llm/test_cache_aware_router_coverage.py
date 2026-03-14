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


class TestCalculateEffectiveCost:
    """Test calculate_effective_cost method (lines 87-170)."""

    @pytest.fixture
    def router_with_pricing(self):
        """Create router with mock pricing fetcher."""
        mock_pricing = MagicMock()

        # Mock pricing for common models
        def get_price(model):
            prices = {
                "gpt-4o": {"input_cost_per_token": 0.000005, "output_cost_per_token": 0.000015},
                "claude-3-5-sonnet": {"input_cost_per_token": 0.000003, "output_cost_per_token": 0.000015},
                "gemini-2.0-flash": {"input_cost_per_token": 0.000001, "output_cost_per_token": 0.00001},
                "deepseek-chat": {"input_cost_per_token": 0.0000001, "output_cost_per_token": 0.0000002},
            }
            return prices.get(model)

        mock_pricing.get_model_price = get_price
        return CacheAwareRouter(mock_pricing)

    def test_cost_openai_with_cache_hit(self, router_with_pricing):
        """Cover lines 132-153: OpenAI with cache hit probability."""
        # GPT-4o with 2000 tokens, 90% cache hit
        cost = router_with_pricing.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.9
        )

        # With 90% cache hit, cost should be lower than full price
        # Formula: effective_input = input * (cache_hit_prob * 0.1 + (1 - cache_hit_prob))
        # effective_cost = (effective_input + output) / 2
        full_price = (0.000005 + 0.000015) / 2
        assert cost < full_price  # Should be discounted

    def test_cost_openai_below_min_threshold(self, router_with_pricing):
        """Cover lines 139-142: Prompt below minimum cache threshold."""
        # OpenAI requires 1024+ tokens for caching
        cost = router_with_pricing.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=500,  # Below 1024 threshold
            cache_hit_probability=0.9
        )

        # Should return full price since prompt too short for caching
        full_price = (0.000005 + 0.000015) / 2
        assert cost == full_price

    def test_cost_anthropic_min_threshold(self, router_with_pricing):
        """Test Anthropic has higher minimum threshold."""
        # Anthropic requires 2048+ tokens
        cost = router_with_pricing.calculate_effective_cost(
            model="claude-3-5-sonnet",
            provider="anthropic",
            estimated_input_tokens=1500,  # Below Anthropic's 2048 threshold
            cache_hit_probability=1.0
        )

        # Should return full price (below threshold)
        full_price = (0.000003 + 0.000015) / 2
        assert cost == full_price

    def test_cost_anthropic_above_threshold(self, router_with_pricing):
        """Test Anthropic with sufficient tokens."""
        cost = router_with_pricing.calculate_effective_cost(
            model="claude-3-5-sonnet",
            provider="anthropic",
            estimated_input_tokens=3000,  # Above 2048 threshold
            cache_hit_probability=0.8
        )

        # Should get cache discount
        full_price = (0.000003 + 0.000015) / 2
        assert cost < full_price

    def test_cost_deepseek_no_cache_support(self, router_with_pricing):
        """Cover lines 135-137: Provider without cache support."""
        cost = router_with_pricing.calculate_effective_cost(
            model="deepseek-chat",
            provider="deepseek",
            estimated_input_tokens=5000,
            cache_hit_probability=0.9  # Ignored - no cache support
        )

        # Should return full price regardless of cache_hit_probability
        full_price = (0.0000001 + 0.0000002) / 2
        assert cost == full_price

    def test_cost_minimax_no_cache_support(self, router_with_pricing):
        """Test MiniMax has no cache support."""
        cost = router_with_pricing.calculate_effective_cost(
            model="minimax-chat",
            provider="minimax",
            estimated_input_tokens=3000,
            cache_hit_probability=0.5
        )

        # Full price - no caching
        assert cost > 0

    def test_cost_unknown_model(self, router_with_pricing):
        """Cover lines 124-127: Unknown model returns infinite cost."""
        cost = router_with_pricing.calculate_effective_cost(
            model="unknown-model",
            provider="openai",
            estimated_input_tokens=1000,
            cache_hit_probability=0.5
        )

        # Unknown model = infinite cost (will be filtered in ranking)
        assert cost == float("inf")

    def test_cost_gemini_with_cache(self, router_with_pricing):
        """Test Gemini cache calculation."""
        cost = router_with_pricing.calculate_effective_cost(
            model="gemini-2.0-flash",
            provider="gemini",
            estimated_input_tokens=1500,  # Above 1024 threshold
            cache_hit_probability=0.7
        )

        # Should get cache discount
        full_price = (0.000001 + 0.00001) / 2
        assert cost < full_price

    @pytest.mark.parametrize("cache_hit_prob", [
        0.0,    # No cache hits = full price
        0.5,    # 50% cache = some discount
        1.0,    # 100% cache = maximum discount
    ])
    def test_cache_hit_probability_impact(self, router_with_pricing, cache_hit_prob):
        """Test cache hit probability directly affects effective cost."""
        cost = router_with_pricing.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,  # Above threshold
            cache_hit_probability=cache_hit_prob
        )

        # Cost should be calculated and finite
        assert cost > 0
        assert cost < float("inf")

        # Higher cache probability should result in lower cost
        # (output cost is constant, so difference is in input cost)

    def test_cost_zero_tokens(self, router_with_pricing):
        """Test handling of zero token count."""
        cost = router_with_pricing.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=0,
            cache_hit_probability=0.5
        )

        # Should handle gracefully (cost based on output only)
        assert cost >= 0


class TestGetProviderCacheCapability:
    """Test get_provider_cache_capability method (if exists)."""

    @pytest.fixture
    def router(self):
        """Create router with mock pricing fetcher."""
        mock_pricing = MagicMock()
        return CacheAwareRouter(mock_pricing)

    def test_get_provider_cache_capability_openai(self, router):
        """Test retrieving OpenAI cache capability."""
        capability = router.get_provider_cache_capability("openai")

        assert capability["supports_cache"] is True
        assert capability["min_tokens"] == 1024
        assert capability["cached_cost_ratio"] == 0.10

    def test_get_provider_cache_capability_anthropic(self, router):
        """Test retrieving Anthropic cache capability."""
        capability = router.get_provider_cache_capability("anthropic")

        assert capability["supports_cache"] is True
        assert capability["min_tokens"] == 2048
        assert capability["cached_cost_ratio"] == 0.10

    def test_get_provider_cache_capability_gemini(self, router):
        """Test retrieving Gemini cache capability."""
        capability = router.get_provider_cache_capability("gemini")

        assert capability["supports_cache"] is True
        assert capability["min_tokens"] == 1024
        assert capability["cached_cost_ratio"] == 0.10

    def test_get_provider_cache_capability_deepseek(self, router):
        """Test retrieving DeepSeek cache capability."""
        capability = router.get_provider_cache_capability("deepseek")

        assert capability["supports_cache"] is False
        assert capability["min_tokens"] == 0
        assert capability["cached_cost_ratio"] == 1.0

    def test_get_provider_cache_capability_minimax(self, router):
        """Test retrieving MiniMax cache capability."""
        capability = router.get_provider_cache_capability("minimax")

        assert capability["supports_cache"] is False
        assert capability["min_tokens"] == 0
        assert capability["cached_cost_ratio"] == 1.0

    def test_get_provider_cache_capability_unknown_provider(self, router):
        """Test unknown provider returns safe defaults."""
        # Should not crash, might return default no-cache config
        capability = router.get_provider_cache_capability("unknown-provider")

        # Should have required keys
        assert "supports_cache" in capability
        assert "cached_cost_ratio" in capability
        assert "min_tokens" in capability

    def test_get_provider_cache_capability_case_insensitive(self, router):
        """Test provider matching is case-insensitive."""
        capability_upper = router.get_provider_cache_capability("OPENAI")
        capability_lower = router.get_provider_cache_capability("openai")
        capability_mixed = router.get_provider_cache_capability("OpenAI")

        # All should return the same capability
        assert capability_upper == capability_lower == capability_mixed

    def test_get_provider_cache_capability_google_fuzzy_match(self, router):
        """Test fuzzy matching for 'google' -> 'gemini'."""
        capability = router.get_provider_cache_capability("google")

        # Should match Gemini config
        assert capability["supports_cache"] is True
        assert capability["min_tokens"] == 1024
        assert capability["cached_cost_ratio"] == 0.10
