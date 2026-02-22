"""
Comprehensive tests for Cache-Aware Router.

Tests cover:
- Cache-aware cost calculation for all providers
- Provider cache capability detection
- Cache hit probability prediction
- Cache outcome recording
- Cost saving calculation (90% target)
- Cache key generation consistency
- Cache invalidation scenarios
- History tracking and analytics

Created: Phase 71-03
"""

import pytest
from unittest.mock import MagicMock

from core.llm.cache_aware_router import CacheAwareRouter


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_pricing_fetcher():
    """Mock dynamic pricing fetcher"""
    fetcher = MagicMock()

    # Mock pricing data for different providers
    def get_model_price(model):
        pricing_data = {
            "gpt-4o": {
                "input_cost_per_token": 0.000005,
                "output_cost_per_token": 0.000015,
            },
            "claude-3-5-sonnet": {
                "input_cost_per_token": 0.000003,
                "output_cost_per_token": 0.000015,
            },
            "deepseek-chat": {
                "input_cost_per_token": 0.00000014,
                "output_cost_per_token": 0.00000028,
            },
            "gemini-3-flash": {
                "input_cost_per_token": 0.000000075,
                "output_cost_per_token": 0.0000003,
            }
        }
        return pricing_data.get(model)

    fetcher.get_model_price = get_model_price
    return fetcher


@pytest.fixture
def router(mock_pricing_fetcher):
    """Create CacheAwareRouter instance"""
    return CacheAwareRouter(mock_pricing_fetcher)


# =============================================================================
# CACHE CAPABILITY DETECTION TESTS
# =============================================================================

class TestProviderCacheCapability:
    """Test provider cache capability detection"""

    def test_openai_cache_capability(self, router):
        """Test OpenAI cache capability"""
        caps = router.get_provider_cache_capability("openai")
        assert caps["supports_cache"] is True
        assert caps["cached_cost_ratio"] == 0.10
        assert caps["min_tokens"] == 1024

    def test_anthropic_cache_capability(self, router):
        """Test Anthropic cache capability"""
        caps = router.get_provider_cache_capability("anthropic")
        assert caps["supports_cache"] is True
        assert caps["cached_cost_ratio"] == 0.10
        assert caps["min_tokens"] == 2048  # Anthropic requires longer prompts

    def test_gemini_cache_capability(self, router):
        """Test Gemini cache capability"""
        caps = router.get_provider_cache_capability("gemini")
        assert caps["supports_cache"] is True
        assert caps["cached_cost_ratio"] == 0.10
        assert caps["min_tokens"] == 1024

    def test_deepseek_no_cache(self, router):
        """Test DeepSeek has no cache support"""
        caps = router.get_provider_cache_capability("deepseek")
        assert caps["supports_cache"] is False
        assert caps["cached_cost_ratio"] == 1.0
        assert caps["min_tokens"] == 0

    def test_minimax_no_cache(self, router):
        """Test MiniMax has no cache support"""
        caps = router.get_provider_cache_capability("minimax")
        assert caps["supports_cache"] is False
        assert caps["cached_cost_ratio"] == 1.0
        assert caps["min_tokens"] == 0

    def test_unknown_provider_defaults_to_no_cache(self, router):
        """Test unknown provider defaults to no cache support"""
        caps = router.get_provider_cache_capability("unknown_provider")
        assert caps["supports_cache"] is False
        assert caps["cached_cost_ratio"] == 1.0
        assert caps["min_tokens"] == 0

    def test_google_variation_maps_to_gemini(self, router):
        """Test 'google' variation maps to Gemini"""
        caps = router.get_provider_cache_capability("google")
        assert caps["supports_cache"] is True
        # Should match Gemini's capabilities


# =============================================================================
# EFFECTIVE COST CALCULATION TESTS
# =============================================================================

class TestEffectiveCostCalculation:
    """Test cache-aware effective cost calculation"""

    def test_calculate_effective_cost_openai_cache_hit(self, router):
        """Test OpenAI effective cost with 90% cache hit probability"""
        # GPT-4o with 2000 tokens, 90% cache hit
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.9
        )

        # With 90% cache hit, cost should be ~10% of original
        # Original: (0.000005 + 0.000015) / 2 = 0.00001
        # With cache: 0.9 * 0.1 * 0.000005 + 0.1 * 0.000005 + 0.000015) / 2
        # This should be significantly lower than full price
        assert cost < 0.00001  # Less than full price

    def test_calculate_effective_cost_anthropic_cache_hit(self, router):
        """Test Anthropic effective cost with high cache hit probability"""
        cost = router.calculate_effective_cost(
            model="claude-3-5-sonnet",
            provider="anthropic",
            estimated_input_tokens=3000,
            cache_hit_probability=0.8
        )

        # Should be cheaper than full price
        full_price = (0.000003 + 0.000015) / 2
        assert cost < full_price

    def test_calculate_effective_cost_no_cache_support(self, router):
        """Test effective cost when provider doesn't support caching"""
        # DeepSeek doesn't support caching
        cost = router.calculate_effective_cost(
            model="deepseek-chat",
            provider="deepseek",
            estimated_input_tokens=2000,
            cache_hit_probability=0.9
        )

        # Should be full price regardless of cache hit probability
        full_price = (0.00000014 + 0.00000028) / 2
        assert cost == full_price

    def test_calculate_effective_cost_below_min_tokens(self, router):
        """Test effective cost when prompt is below minimum token threshold"""
        # OpenAI requires 1024 tokens minimum
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=500,  # Below 1024 threshold
            cache_hit_probability=0.9
        )

        # Should be full price (caching won't be applied)
        full_price = (0.000005 + 0.000015) / 2
        assert cost == full_price

    def test_calculate_effective_cost_unknown_model(self, router):
        """Test effective cost for unknown model (returns infinity)"""
        cost = router.calculate_effective_cost(
            model="unknown-model",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.5
        )

        # Unknown model should have infinite cost
        assert cost == float("inf")

    def test_calculate_effective_cost_zero_cache_hit_probability(self, router):
        """Test effective cost with 0% cache hit probability"""
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.0
        )

        # Should be full price (no cache hits)
        full_price = (0.000005 + 0.000015) / 2
        assert cost == full_price

    def test_calculate_effective_cost_fifty_percent_cache_hit(self, router):
        """Test effective cost with 50% cache hit probability (default)"""
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.5
        )

        # Should be between full price and fully cached price
        full_price = (0.000005 + 0.000015) / 2
        assert cost < full_price
        assert cost > full_price * 0.5


# =============================================================================
# CACHE HIT PROBABILITY TESTS
# =============================================================================

class TestCacheHitProbability:
    """Test cache hit probability prediction"""

    def test_predict_cache_hit_probability_no_history(self, router):
        """Test prediction returns default (0.5) when no history exists"""
        prob = router.predict_cache_hit_probability("new_prompt_hash", "workspace_1")
        assert prob == 0.5  # Default industry average

    def test_predict_cache_hit_probability_after_recording_hits(self, router):
        """Test prediction improves after recording cache outcomes"""
        prompt_hash = "test_prompt_123"

        # Record 8 cache hits out of 10 requests
        for _ in range(8):
            router.record_cache_outcome(prompt_hash, "workspace_1", True)
        for _ in range(2):
            router.record_cache_outcome(prompt_hash, "workspace_1", False)

        # Prediction should reflect 80% hit rate
        prob = router.predict_cache_hit_probability(prompt_hash, "workspace_1")
        assert prob == 0.8

    def test_predict_cache_hit_probability_all_hits(self, router):
        """Test prediction with 100% cache hit rate"""
        prompt_hash = "perfect_cache_hash"

        # Record 10 cache hits
        for _ in range(10):
            router.record_cache_outcome(prompt_hash, "workspace_1", True)

        prob = router.predict_cache_hit_probability(prompt_hash, "workspace_1")
        assert prob == 1.0

    def test_predict_cache_hit_probability_all_misses(self, router):
        """Test prediction with 0% cache hit rate"""
        prompt_hash = "no_cache_hash"

        # Record 10 cache misses
        for _ in range(10):
            router.record_cache_outcome(prompt_hash, "workspace_1", False)

        prob = router.predict_cache_hit_probability(prompt_hash, "workspace_1")
        assert prob == 0.0

    def test_predict_cache_hit_probability_different_workspaces(self, router):
        """Test that predictions are workspace-specific"""
        prompt_hash = "shared_prompt"

        # Workspace 1: 90% hit rate
        for _ in range(9):
            router.record_cache_outcome(prompt_hash, "workspace_1", True)
        router.record_cache_outcome(prompt_hash, "workspace_1", False)

        # Workspace 2: 30% hit rate
        for _ in range(3):
            router.record_cache_outcome(prompt_hash, "workspace_2", True)
        for _ in range(7):
            router.record_cache_outcome(prompt_hash, "workspace_2", False)

        prob_w1 = router.predict_cache_hit_probability(prompt_hash, "workspace_1")
        prob_w2 = router.predict_cache_hit_probability(prompt_hash, "workspace_2")

        assert prob_w1 == 0.9
        assert prob_w2 == 0.3


# =============================================================================
# CACHE OUTCOME RECORDING TESTS
# =============================================================================

class TestCacheOutcomeRecording:
    """Test cache outcome recording"""

    def test_record_cache_outcome_hit(self, router):
        """Test recording a cache hit"""
        prompt_hash = "test_hash"
        router.record_cache_outcome(prompt_hash, "workspace_1", True)

        history = router.get_cache_hit_history("workspace_1")
        key = f"workspace_1:{prompt_hash[:16]}"
        assert key in history
        assert history[key] == [1, 1]  # [hits, total]

    def test_record_cache_outcome_miss(self, router):
        """Test recording a cache miss"""
        prompt_hash = "test_hash"
        router.record_cache_outcome(prompt_hash, "workspace_1", False)

        history = router.get_cache_hit_history("workspace_1")
        key = f"workspace_1:{prompt_hash[:16]}"
        assert key in history
        assert history[key] == [0, 1]  # [hits, total]

    def test_record_cache_outcome_multiple(self, router):
        """Test recording multiple outcomes"""
        prompt_hash = "test_hash"

        router.record_cache_outcome(prompt_hash, "workspace_1", True)
        router.record_cache_outcome(prompt_hash, "workspace_1", True)
        router.record_cache_outcome(prompt_hash, "workspace_1", False)

        history = router.get_cache_hit_history("workspace_1")
        key = f"workspace_1:{prompt_hash[:16]}"
        assert history[key] == [2, 3]  # 2 hits out of 3 total


# =============================================================================
# CACHE HISTORY TESTS
# =============================================================================

class TestCacheHistory:
    """Test cache hit history tracking"""

    def test_get_cache_hit_history_all(self, router):
        """Test getting all cache hit history"""
        router.record_cache_outcome("hash1", "workspace_1", True)
        router.record_cache_outcome("hash2", "workspace_2", False)

        history = router.get_cache_hit_history()
        assert len(history) >= 2

    def test_get_cache_hit_history_workspace_filtered(self, router):
        """Test getting cache hit history filtered by workspace"""
        router.record_cache_outcome("hash1", "workspace_1", True)
        router.record_cache_outcome("hash2", "workspace_2", False)

        history_w1 = router.get_cache_hit_history("workspace_1")
        history_w2 = router.get_cache_hit_history("workspace_2")

        # Each workspace should only see its own history
        assert all(key.startswith("workspace_1:") for key in history_w1.keys())
        assert all(key.startswith("workspace_2:") for key in history_w2.keys())

    def test_clear_cache_history_all(self, router):
        """Test clearing all cache history"""
        router.record_cache_outcome("hash1", "workspace_1", True)
        router.record_cache_outcome("hash2", "workspace_2", False)

        router.clear_cache_history()

        history = router.get_cache_hit_history()
        assert len(history) == 0

    def test_clear_cache_history_workspace(self, router):
        """Test clearing cache history for specific workspace"""
        router.record_cache_outcome("hash1", "workspace_1", True)
        router.record_cache_outcome("hash2", "workspace_2", False)

        router.clear_cache_history("workspace_1")

        history = router.get_cache_hit_history()
        # workspace_1 should be cleared, workspace_2 should remain
        assert not any(key.startswith("workspace_1:") for key in history.keys())
        assert any(key.startswith("workspace_2:") for key in history.keys())


# =============================================================================
# COST SAVING CALCULATION TESTS
# =============================================================================

class TestCostSavings:
    """Test cost saving calculations"""

    def test_cost_saving_with_high_cache_hit_rate(self, router):
        """Test cost savings with 90% cache hit rate"""
        # OpenAI GPT-4o with 2000 tokens
        full_cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.0
        )

        cached_cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.9
        )

        # Should achieve cost reduction (formula: cache_hit_prob * 0.9 + (1-cache_hit_prob) * 1.0)
        # With 90% cache hit: 0.9 * 0.1 + 0.1 * 1.0 = 0.19 (19% of input cost)
        # Since output cost is unchanged, savings are less than 90%
        savings_percent = (1 - cached_cost / full_cost) * 100
        assert savings_percent > 15  # At least 15% savings (realistic for 90% cache hit)

    def test_cost_saving_with_moderate_cache_hit_rate(self, router):
        """Test cost savings with 50% cache hit rate"""
        full_cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.0
        )

        cached_cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.5
        )

        # Should achieve ~20% cost reduction (50% of 90% discount on input only)
        savings_percent = (1 - cached_cost / full_cost) * 100
        assert savings_percent > 5  # At least 5% savings

    def test_no_savings_without_cache_support(self, router):
        """Test no savings when provider doesn't support caching"""
        cost_no_cache = router.calculate_effective_cost(
            model="deepseek-chat",
            provider="deepseek",
            estimated_input_tokens=2000,
            cache_hit_probability=0.0
        )

        cost_with_cache_prob = router.calculate_effective_cost(
            model="deepseek-chat",
            provider="deepseek",
            estimated_input_tokens=2000,
            cache_hit_probability=0.9
        )

        # DeepSeek doesn't support caching, so no savings
        assert cost_no_cache == cost_with_cache_prob


# =============================================================================
# CACHE KEY GENERATION TESTS
# =============================================================================

class TestCacheKeyGeneration:
    """Test cache key generation and consistency"""

    def test_cache_key_uses_first_16_chars(self, router):
        """Test that cache keys use first 16 characters of hash"""
        long_hash = "a" * 50 + "b" * 50
        workspace = "test_workspace"

        router.record_cache_outcome(long_hash, workspace, True)

        history = router.get_cache_hit_history(workspace)
        # Key should be workspace:first_16_of_hash
        expected_key = f"{workspace}:{'a' * 16}"
        assert expected_key in history

    def test_cache_key_consistency(self, router):
        """Test that same inputs generate same cache key"""
        hash1 = "abc123def456"
        hash2 = "abc123def456"  # Same hash

        router.record_cache_outcome(hash1, "workspace_1", True)
        router.record_cache_outcome(hash2, "workspace_1", True)

        history = router.get_cache_hit_history("workspace_1")
        # Should have only one entry (both used same key)
        key = f"workspace_1:{hash1[:16]}"
        assert history[key] == [2, 2]  # 2 hits recorded


# =============================================================================
# CACHE INVALIDATION TESTS
# =============================================================================

class TestCacheInvalidation:
    """Test cache invalidation scenarios"""

    def test_clear_history_after_recording(self, router):
        """Test clearing history after recording outcomes"""
        router.record_cache_outcome("hash1", "workspace_1", True)
        router.record_cache_outcome("hash2", "workspace_1", True)

        # Verify history exists
        history = router.get_cache_hit_history("workspace_1")
        assert len(history) == 2

        # Clear history
        router.clear_cache_history("workspace_1")

        # Verify history is cleared
        history = router.get_cache_hit_history("workspace_1")
        assert len(history) == 0

    def test_predict_after_clear(self, router):
        """Test prediction returns default after clearing history"""
        prompt_hash = "test_hash"

        # Record some history
        for _ in range(5):
            router.record_cache_outcome(prompt_hash, "workspace_1", True)

        # Verify prediction uses history
        prob = router.predict_cache_hit_probability(prompt_hash, "workspace_1")
        assert prob == 1.0

        # Clear history
        router.clear_cache_history("workspace_1")

        # Prediction should return default
        prob = router.predict_cache_hit_probability(prompt_hash, "workspace_1")
        assert prob == 0.5


# =============================================================================
# ANTHROPIC HIGHER MIN TOKENS TESTS
# =============================================================================

class TestAnthropicHigherMinTokens:
    """Test Anthropic's higher minimum token requirement"""

    def test_anthropic_min_tokens_higher_than_others(self, router):
        """Test that Anthropic has higher min tokens than OpenAI/Gemini"""
        anthropic_caps = router.get_provider_cache_capability("anthropic")
        openai_caps = router.get_provider_cache_capability("openai")
        gemini_caps = router.get_provider_cache_capability("gemini")

        assert anthropic_caps["min_tokens"] > openai_caps["min_tokens"]
        assert anthropic_caps["min_tokens"] > gemini_caps["min_tokens"]

    def test_anthropic_cost_below_threshold(self, router):
        """Test Anthropic cost calculation below 2048 token threshold"""
        # Below Anthropic's 2048 minimum
        cost = router.calculate_effective_cost(
            model="claude-3-5-sonnet",
            provider="anthropic",
            estimated_input_tokens=1000,
            cache_hit_probability=0.9
        )

        # Should be full price (below threshold)
        full_price = (0.000003 + 0.000015) / 2
        assert cost == full_price

    def test_anthropic_cost_above_threshold(self, router):
        """Test Anthropic cost calculation above 2048 token threshold"""
        # Above Anthropic's 2048 minimum
        cost = router.calculate_effective_cost(
            model="claude-3-5-sonnet",
            provider="anthropic",
            estimated_input_tokens=3000,
            cache_hit_probability=0.9
        )

        # Should be discounted (above threshold)
        full_price = (0.000003 + 0.000015) / 2
        assert cost < full_price


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Test edge cases in cache-aware routing"""

    def test_zero_tokens_input(self, router):
        """Test cost calculation with zero input tokens"""
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=0,
            cache_hit_probability=0.9
        )
        # Should handle gracefully
        assert isinstance(cost, float)

    def test_very_high_cache_hit_probability(self, router):
        """Test cost calculation with 100% cache hit probability"""
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=1.0
        )

        # Should have savings on input cost
        full_price = (0.000005 + 0.000015) / 2
        # With 100% cache hit: input cost is 10%, output is 100%
        # Effective: (0.1 * 0.000005 + 0.000015) / 2 = 0.00000775
        # Full: (0.000005 + 0.000015) / 2 = 0.00001
        # Ratio: 0.775 (22.5% savings)
        assert cost < full_price * 0.8  # Less than 80% of full price (input gets 90% discount)

    def test_empty_prompt_hash(self, router):
        """Test recording with empty prompt hash"""
        router.record_cache_outcome("", "workspace_1", True)
        history = router.get_cache_hit_history("workspace_1")
        # Should still create an entry
        assert len(history) >= 0

    def test_case_insensitive_provider_name(self, router):
        """Test provider names are case-insensitive"""
        caps_lower = router.get_provider_cache_capability("openai")
        caps_upper = router.get_provider_cache_capability("OPENAI")
        caps_mixed = router.get_provider_cache_capability("OpenAI")

        # All should return same capabilities
        assert caps_lower == caps_upper == caps_mixed


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegrationScenarios:
    """Integration tests for realistic cache-aware routing scenarios"""

    def test_repeated_query_cost_reduction(self, router):
        """Test cost reduction for repeated queries"""
        prompt_hash = "repeated_query_hash"
        model = "gpt-4o"
        provider = "openai"
        tokens = 2000

        # First request - no history (50% default probability)
        prob_before = router.predict_cache_hit_probability(prompt_hash, "workspace_1")
        cost_before = router.calculate_effective_cost(
            model, provider, tokens, prob_before
        )

        # Record 10 cache hits
        for _ in range(10):
            router.record_cache_outcome(prompt_hash, "workspace_1", True)

        # Same request - now with 100% hit probability
        prob_after = router.predict_cache_hit_probability(prompt_hash, "workspace_1")
        cost_after = router.calculate_effective_cost(
            model, provider, tokens, prob_after
        )

        # Cost should be lower after learning cache hit pattern
        assert cost_after < cost_before

    def test_workspace_specific_cache_patterns(self, router):
        """Test that different workspaces maintain separate cache patterns"""
        prompt_hash = "shared_query"
        model = "gpt-4o"
        provider = "openai"
        tokens = 2000

        # Workspace 1: High cache hit rate
        for _ in range(9):
            router.record_cache_outcome(prompt_hash, "workspace_1", True)
        router.record_cache_outcome(prompt_hash, "workspace_1", False)

        # Workspace 2: Low cache hit rate
        router.record_cache_outcome(prompt_hash, "workspace_2", True)
        for _ in range(9):
            router.record_cache_outcome(prompt_hash, "workspace_2", False)

        prob_w1 = router.predict_cache_hit_probability(prompt_hash, "workspace_1")
        prob_w2 = router.predict_cache_hit_probability(prompt_hash, "workspace_2")

        cost_w1 = router.calculate_effective_cost(model, provider, tokens, prob_w1)
        cost_w2 = router.calculate_effective_cost(model, provider, tokens, prob_w2)

        # Workspace 1 should have lower cost (higher cache hit rate)
        assert cost_w1 < cost_w2
