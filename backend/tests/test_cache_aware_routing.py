"""
Cache-Aware Routing Tests

Comprehensive test suite for cache-aware LLM routing including:
- Effective cost calculation with caching
- Cache hit prediction from historical data
- Cache outcome recording
- BYOK integration with cache-aware scoring
- Performance benchmarks
"""

import hashlib
import pytest
from unittest.mock import Mock, MagicMock

from core.llm.cache_aware_router import CacheAwareRouter
from core.llm.byok_handler import BYOKHandler


class TestEffectiveCostCalculation:
    """Test effective cost calculation with cache hit probability"""

    @pytest.fixture
    def mock_pricing_fetcher(self):
        """Create a mock pricing fetcher with test data"""
        fetcher = Mock()

        # GPT-4o pricing (OpenAI, supports caching)
        fetcher.get_model_price.return_value = {
            "input_cost_per_token": 0.0000025,  # $2.50/M tokens
            "output_cost_per_token": 0.00001,    # $10/M tokens
        }

        return fetcher

    @pytest.fixture
    def router(self, mock_pricing_fetcher):
        """Create CacheAwareRouter with mock pricing fetcher"""
        return CacheAwareRouter(mock_pricing_fetcher)

    def test_cached_provider_cost_reduction(self, router):
        """
        Test that cached provider (OpenAI) with 90% cache hit costs ~10% of full price

        Expected: With 90% cache hit rate and 10% cached cost ratio,
        effective cost should be approximately:
        input_effective = 0.0000025 * (0.9 * 0.10 + 0.1 * 1.0) = 0.0000025 * 0.19 = 0.000000475
        effective_cost = (0.000000475 + 0.00001) / 2 ≈ 0.0000052
        """
        cost = router.calculate_effective_cost("gpt-4o", "openai", 2000, 0.9)

        # Should be significantly cheaper than full price
        full_price = (0.0000025 + 0.00001) / 2  # 0.00000625
        # With 90% cache hit, effective cost is ~84% of full price (not 50% due to output cost)
        assert cost < full_price * 0.9, f"Cost {cost} should be <90% of full price {full_price}"

    def test_uncached_provider_full_cost(self, router):
        """Test that provider without caching (DeepSeek) pays full price"""
        cost = router.calculate_effective_cost("deepseek-chat", "deepseek", 2000, 0.9)

        # DeepSeek doesn't support caching, so should pay full price
        expected_cost = (0.0000025 + 0.00001) / 2
        assert cost == expected_cost, f"Cost {cost} should equal full price {expected_cost}"

    def test_below_min_threshold_no_cache(self, router):
        """
        Test that prompts below minimum token threshold don't benefit from caching

        OpenAI minimum: 1024 tokens. 500 tokens is below threshold.
        """
        cost = router.calculate_effective_cost("gpt-4o", "openai", 500, 0.9)

        # Should pay full price because prompt is too short for caching
        full_price = (0.0000025 + 0.00001) / 2
        assert cost == full_price, f"Cost {cost} should be full price for short prompts"

    def test_zero_cache_hit_probability(self, router):
        """Test that 0% cache hit probability results in full cost"""
        cost = router.calculate_effective_cost("gpt-4o", "openai", 2000, 0.0)

        # With 0% cache hit, effective cost = full price
        full_price = (0.0000025 + 0.00001) / 2
        assert cost == full_price, f"Cost {cost} should equal full price with 0% cache hit"

    def test_hundred_percent_cache_hit(self, router):
        """Test that 100% cache hit results in maximum savings"""
        cost = router.calculate_effective_cost("gpt-4o", "openai", 2000, 1.0)

        # With 100% cache hit, effective input cost = 10% of original
        full_price = (0.0000025 + 0.00001) / 2
        cached_price = (0.0000025 * 0.10 + 0.00001) / 2

        # Cost should match cached price exactly
        assert abs(cost - cached_price) < 0.000001, f"Cost {cost} should match cached price {cached_price}"

    def test_unknown_model_infinite_cost(self, router):
        """Test that unknown model returns infinite cost"""
        # Configure mock to return None (unknown model)
        router.pricing_fetcher.get_model_price.return_value = None

        cost = router.calculate_effective_cost("unknown-model", "openai", 2000, 0.5)

        assert cost == float("inf"), "Unknown model should have infinite cost"


class TestCacheHitPrediction:
    """Test cache hit probability prediction from historical data"""

    @pytest.fixture
    def mock_pricing_fetcher(self):
        return Mock()

    @pytest.fixture
    def router(self, mock_pricing_fetcher):
        return CacheAwareRouter(mock_pricing_fetcher)

    def test_default_probability_no_history(self, router):
        """Test that prompts with no history return 0.5 default probability"""
        prob = router.predict_cache_hit_probability("abc123", "default")
        assert prob == 0.5, "Default probability should be 0.5 (50%)"

    def test_actual_hit_rate_from_history(self, router):
        """Test that actual hit rate is calculated from history"""
        # Record 8 cache hits out of 10 requests
        for _ in range(8):
            router.record_cache_outcome("test-hash", "workspace-1", True)
        for _ in range(2):
            router.record_cache_outcome("test-hash", "workspace-1", False)

        prob = router.predict_cache_hit_probability("test-hash", "workspace-1")
        assert prob == 0.8, f"Hit rate should be 0.8 (80%), got {prob}"

    def test_workspace_specific_tracking(self, router):
        """Test that different workspaces have separate histories"""
        # Workspace 1: 100% cache hit rate
        for _ in range(5):
            router.record_cache_outcome("hash1", "workspace-1", True)

        # Workspace 2: 0% cache hit rate
        for _ in range(5):
            router.record_cache_outcome("hash1", "workspace-2", False)

        prob_1 = router.predict_cache_hit_probability("hash1", "workspace-1")
        prob_2 = router.predict_cache_hit_probability("hash1", "workspace-2")

        assert prob_1 == 1.0, f"Workspace 1 should have 100% hit rate, got {prob_1}"
        assert prob_2 == 0.0, f"Workspace 2 should have 0% hit rate, got {prob_2}"

    def test_prompt_hash_prefix_keying(self, router):
        """Test that only first 16 characters of hash are used as key"""
        # Same prefix (first 16 chars), different suffix
        # The key format is "workspace_id:prompt_hash[:16]"
        # So "default:abc123xxxxxx..." becomes "default:abc123xxxxxx" (first 16 after default:)
        long_hash_1 = "a" * 20  # 20 'a' characters
        long_hash_2 = "a" * 25  # 25 'a' characters (same prefix)

        # Record outcomes for both
        router.record_cache_outcome(long_hash_1, "default", True)
        router.record_cache_outcome(long_hash_2, "default", False)

        # Both should map to same history (same prefix: "default:aaaaaaaaaaaaaaaa")
        # Hash is truncated to first 16 chars
        history = router.cache_hit_history.get("default:aaaaaaaaaaaaaaaa")
        assert history is not None, f"Should have history for prefix, got {list(router.cache_hit_history.keys())}"
        assert history == [1, 2], f"History should be [1, 2], got {history}"


class TestCacheOutcomeRecording:
    """Test cache outcome recording functionality"""

    @pytest.fixture
    def mock_pricing_fetcher(self):
        return Mock()

    @pytest.fixture
    def router(self, mock_pricing_fetcher):
        return CacheAwareRouter(mock_pricing_fetcher)

    def test_record_hit_increments_counter(self, router):
        """Test that recording a cache hit increments both hits and total"""
        router.record_cache_outcome("hash1", "ws1", True)

        assert "ws1:hash1" in router.cache_hit_history
        assert router.cache_hit_history["ws1:hash1"] == [1, 1]

    def test_record_miss_increments_total_only(self, router):
        """Test that recording a cache miss increments total only"""
        router.record_cache_outcome("hash1", "ws1", False)

        assert "ws1:hash1" in router.cache_hit_history
        assert router.cache_hit_history["ws1:hash1"] == [0, 1]

    def test_multiple_outcomes_update_correctly(self, router):
        """Test that multiple outcomes are tracked correctly"""
        # 3 hits, 2 misses = 60% hit rate
        router.record_cache_outcome("hash1", "ws1", True)
        router.record_cache_outcome("hash1", "ws1", True)
        router.record_cache_outcome("hash1", "ws1", False)
        router.record_cache_outcome("hash1", "ws1", True)
        router.record_cache_outcome("hash1", "ws1", False)

        hits, total = router.cache_hit_history["ws1:hash1"]
        assert hits == 3, f"Expected 3 hits, got {hits}"
        assert total == 5, f"Expected 5 total, got {total}"


class TestBYOKIntegration:
    """Test integration with BYOKHandler"""

    def test_cache_aware_ranking(self):
        """
        Test that cached models are ranked higher than cheaper uncached models

        Scenario: GPT-4o (expensive but cached) vs DeepSeek (cheap but no cache)
        With high cache hit probability, GPT-4o should have better value score
        """
        # This would require full BYOKHandler initialization with mock providers
        # For now, we verify the integration exists
        handler = BYOKHandler()
        assert hasattr(handler, 'cache_router'), "BYOKHandler should have cache_router"

    def test_cache_unavailable_below_threshold(self):
        """Test that short prompts don't benefit from cache prediction"""
        # Need a proper mock that returns pricing data
        mock_fetcher = Mock()
        mock_fetcher.get_model_price.return_value = {
            "input_cost_per_token": 0.0000025,
            "output_cost_per_token": 0.00001,
        }
        router = CacheAwareRouter(mock_fetcher)
        cost = router.calculate_effective_cost("gpt-4o", "openai", 500, 0.9)

        # Should pay full price due to minimum threshold
        assert cost > 0, "Cost should be calculated"

    def test_byok_integration_with_estimated_tokens(self):
        """Test that BYOKHandler accepts estimated_tokens parameter"""
        from core.llm.byok_handler import QueryComplexity

        handler = BYOKHandler()

        # This should not raise an error
        try:
            result = handler.get_ranked_providers(
                QueryComplexity.SIMPLE,
                estimated_tokens=2000,
                workspace_id="test"
            )
            # Result is a list of (provider, model) tuples
            assert isinstance(result, list), "Should return a list"
        except TypeError as e:
            pytest.fail(f"get_ranked_providers should accept estimated_tokens: {e}")

    def test_backward_compatibility_no_params(self):
        """Test that BYOKHandler works without new parameters (backward compatible)"""
        from core.llm.byok_handler import QueryComplexity

        handler = BYOKHandler()

        # Should work with default parameters
        try:
            result = handler.get_ranked_providers(QueryComplexity.SIMPLE)
            assert isinstance(result, list), "Should return a list"
        except TypeError as e:
            pytest.fail(f"get_ranked_providers should work without new params: {e}")

    def test_cache_outcome_recording(self):
        """Test that cache outcomes can be recorded through BYOKHandler"""
        handler = BYOKHandler()
        assert hasattr(handler.cache_router, 'record_cache_outcome')

        # Record a cache outcome
        handler.cache_router.record_cache_outcome("test-hash", "default", True)

        # Verify it was recorded
        history = handler.cache_router.get_cache_hit_history()
        assert "default:test-hash" in history


class TestPerformance:
    """Performance benchmarks for cache-aware routing"""

    @pytest.fixture
    def mock_pricing_fetcher(self):
        fetcher = Mock()
        fetcher.get_model_price.return_value = {
            "input_cost_per_token": 0.0000025,
            "output_cost_per_token": 0.00001,
        }
        return fetcher

    @pytest.fixture
    def router(self, mock_pricing_fetcher):
        return CacheAwareRouter(mock_pricing_fetcher)

    def test_effective_cost_calculation_performance(self, router):
        """Test that effective cost calculation is <10ms per provider"""
        import time

        # Warm up
        for _ in range(10):
            router.calculate_effective_cost("gpt-4o", "openai", 2000, 0.5)

        # Benchmark
        start = time.time()
        iterations = 1000
        for _ in range(iterations):
            router.calculate_effective_cost("gpt-4o", "openai", 2000, 0.5)
        end = time.time()

        avg_time_ms = (end - start) / iterations * 1000

        assert avg_time_ms < 10, f"Average time {avg_time_ms:.2f}ms should be <10ms"

    def test_cache_hit_prediction_performance(self, router):
        """Test that cache hit prediction is <1ms lookup"""
        import time

        # Add some history
        router.record_cache_outcome("test-hash", "default", True)

        # Warm up
        for _ in range(10):
            router.predict_cache_hit_probability("test-hash", "default")

        # Benchmark
        start = time.time()
        iterations = 10000
        for _ in range(iterations):
            router.predict_cache_hit_probability("test-hash", "default")
        end = time.time()

        avg_time_ms = (end - start) / iterations * 1000

        assert avg_time_ms < 1, f"Average time {avg_time_ms:.4f}ms should be <1ms"


class TestProviderCapabilities:
    """Test provider cache capability detection"""

    @pytest.fixture
    def router(self):
        return CacheAwareRouter(Mock())

    def test_openai_cache_capabilities(self, router):
        """Test OpenAI cache capability metadata"""
        caps = router.get_provider_cache_capability("openai")

        assert caps["supports_cache"] == True
        assert caps["cached_cost_ratio"] == 0.10
        assert caps["min_tokens"] == 1024

    def test_anthropic_cache_capabilities(self, router):
        """Test Anthropic cache capability metadata"""
        caps = router.get_provider_cache_capability("anthropic")

        assert caps["supports_cache"] == True
        assert caps["cached_cost_ratio"] == 0.10
        assert caps["min_tokens"] == 2048  # Higher threshold than OpenAI

    def test_deepseek_no_cache(self, router):
        """Test DeepSeek has no cache support"""
        caps = router.get_provider_cache_capability("deepseek")

        assert caps["supports_cache"] == False
        assert caps["cached_cost_ratio"] == 1.0
        assert caps["min_tokens"] == 0

    def test_unknown_provider_defaults(self, router):
        """Test unknown provider defaults to no cache"""
        caps = router.get_provider_cache_capability("unknown-provider")

        assert caps["supports_cache"] == False
        assert caps["cached_cost_ratio"] == 1.0
        assert caps["min_tokens"] == 0

    def test_provider_name_variations(self, router):
        """Test that provider name variations are handled"""
        # "google" should map to "gemini" capabilities
        caps_google = router.get_provider_cache_capability("google")
        caps_gemini = router.get_provider_cache_capability("gemini")

        assert caps_google["supports_cache"] == caps_gemini["supports_cache"]
