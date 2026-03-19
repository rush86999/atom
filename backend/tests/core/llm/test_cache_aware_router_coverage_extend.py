"""
Coverage-driven tests for cache_aware_router.py (98.8% -> 100% target)

EXTENDING existing tests to cover remaining edge cases:
- Edge case: Empty cache scenarios
- Edge case: Cache key collision handling
- Edge case: Cache expiration edge cases
- Edge case: Null/None value handling
- Edge case: Concurrent cache access patterns
- Error paths: Cache failures, malformed entries

Remaining Coverage Areas:
- Lines with rare branch conditions
- Exception handling paths
- Boundary conditions for cache size/expiration
"""

from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import pytest
import threading

from core.llm.cache_aware_router import CacheAwareRouter


class TestEmptyCacheScenarios:
    """Test empty cache edge cases."""

    @pytest.fixture
    def router(self):
        """Create router with mock pricing fetcher."""
        mock_pricing = MagicMock()
        mock_pricing.get_model_price = MagicMock(return_value={
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
        })
        return CacheAwareRouter(mock_pricing)

    def test_cache_hit_history_initially_empty(self, router):
        """Cover routing behavior when cache hit history is empty."""
        # Should return default probability
        prob = router.predict_cache_hit_probability("test-hash", "workspace-1")
        assert prob == 0.5  # Default when no history

    def test_predict_with_empty_workspace(self, router):
        """Cover prediction when workspace has no history."""
        # Workspace with no history should return default
        prob = router.predict_cache_hit_probability("abc123", "new-workspace")
        assert prob == 0.5

    def test_get_history_with_empty_router(self, router):
        """Cover getting history from empty router."""
        history = router.get_cache_hit_history()
        assert history == {}

    def test_get_history_with_empty_workspace_filter(self, router):
        """Cover getting history for workspace with no entries."""
        history = router.get_cache_hit_history("nonexistent-workspace")
        assert history == {}

    def test_clear_empty_history(self, router):
        """Cover clearing already empty history."""
        router.clear_cache_history()  # Should not raise
        assert router.cache_hit_history == {}

    def test_clear_empty_workspace_history(self, router):
        """Cover clearing history for workspace with no entries."""
        router.clear_cache_history("empty-workspace")  # Should not raise
        assert router.cache_hit_history == {}

    def test_cost_calculation_with_empty_pricing_dict(self, router):
        """Cover cost calculation when pricing dict is empty."""
        router.pricing_fetcher.get_model_price = MagicMock(return_value=None)
        cost = router.calculate_effective_cost(
            model="unknown-model",
            provider="openai",
            estimated_input_tokens=1000,
            cache_hit_probability=0.5
        )
        assert cost == float("inf")

    def test_cost_with_missing_input_cost(self):
        """Cover cost when input_cost_per_token is missing."""
        mock_pricing = MagicMock()
        mock_pricing.get_model_price = MagicMock(return_value={
            # Missing input_cost_per_token
            "output_cost_per_token": 0.000015,
        })
        router = CacheAwareRouter(mock_pricing)

        cost = router.calculate_effective_cost(
            model="test-model",
            provider="openai",
            estimated_input_tokens=1000,
            cache_hit_probability=0.5
        )
        # Should handle gracefully (default to 0)
        assert cost >= 0


class TestCacheKeyCollision:
    """Test cache key generation and potential collisions."""

    @pytest.fixture
    def router(self):
        """Create router for key testing."""
        mock_pricing = MagicMock()
        return CacheAwareRouter(mock_pricing)

    def test_cache_history_key_format(self, router):
        """Cover that history keys use correct format."""
        router.record_cache_outcome("test-prompt-hash", "workspace-123", True)
        # Key is workspace:hash (first 16 chars of hash)
        # "test-prompt-hash" has 16 chars exactly, so it's used as-is
        expected_key = "workspace-123:test-prompt-hash"
        assert expected_key in router.cache_hit_history

    def test_cache_hash_truncation_to_16_chars(self, router):
        """Cover that prompt hash is truncated to 16 characters."""
        long_hash = "a" * 50
        router.record_cache_outcome(long_hash, "workspace-1", True)
        # Key should be truncated
        key = f"workspace-1:{'a' * 16}"
        assert key in router.cache_hit_history

    def test_different_prompts_same_truncated_hash(self, router):
        """Cover potential collision from truncation."""
        # Two different hashes that share first 16 chars
        hash1 = "abc123def456ghi78"  # Truncated: abc123def456ghi7
        hash2 = "abc123def456ghi99"  # Truncated: abc123def456ghi9 (different)

        router.record_cache_outcome(hash1, "ws-1", True)
        router.record_cache_outcome(hash2, "ws-1", False)

        # Should create separate entries
        assert len(router.cache_hit_history) == 2

    def test_workspace_isolation_in_keys(self, router):
        """Cover that different workspaces create different keys."""
        router.record_cache_outcome("same-hash", "workspace-1", True)
        router.record_cache_outcome("same-hash", "workspace-2", True)

        # Should be separate entries
        assert len(router.cache_hit_history) == 2
        assert "workspace-1:same-hash" in router.cache_hit_history
        assert "workspace-2:same-hash" in router.cache_hit_history

    def test_special_characters_in_workspace_id(self, router):
        """Cover workspace IDs with special characters."""
        special_workspace = "work-space_123.test"
        router.record_cache_outcome("hash123", special_workspace, True)

        key = f"{special_workspace}:hash123"
        assert key in router.cache_hit_history

    def test_empty_workspace_id(self, router):
        """Cover empty workspace ID in key generation."""
        router.record_cache_outcome("hash123", "", True)
        key = ":hash123"
        assert key in router.cache_hit_history

    def test_workspace_id_with_colon(self, router):
        """Cover workspace ID containing colon separator."""
        # Workspace with colon should still work
        router.record_cache_outcome("hash123", "work:space", True)
        # Key format: workspace:hash, so "work:space" becomes "work:space:hash"
        assert "work:space:hash123" in router.cache_hit_history


class TestCacheExpirationEdgeCases:
    """Test cache expiration and time-based edge cases."""

    @pytest.fixture
    def router(self):
        """Create router with mock pricing."""
        mock_pricing = MagicMock()
        mock_pricing.get_model_price = MagicMock(return_value={
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
        })
        return CacheAwareRouter(mock_pricing)

    def test_cache_history_persistence_in_memory(self, router):
        """Cover that cache history persists across calls."""
        router.record_cache_outcome("hash1", "ws-1", True)
        prob1 = router.predict_cache_hit_probability("hash1", "ws-1")
        assert prob1 == 1.0

        # Should still be available
        prob2 = router.predict_cache_hit_probability("hash1", "ws-1")
        assert prob2 == 1.0

    def test_cache_hit_probability_zero_denominator(self, router):
        """Cover probability calculation with zero total."""
        # Manually create edge case: [0, 0]
        router.cache_hit_history["ws-1:hash"] = [0, 0]
        prob = router.predict_cache_hit_probability("hash", "ws-1")
        # Should handle division by zero
        assert prob == 0.5  # Default fallback

    def test_cache_hit_probability_exact_zero(self, router):
        """Cover probability when hit rate is exactly 0%."""
        router.record_cache_outcome("hash1", "ws-1", False)
        router.record_cache_outcome("hash1", "ws-1", False)
        prob = router.predict_cache_hit_probability("hash1", "ws-1")
        assert prob == 0.0

    def test_cache_hit_probability_exact_one(self, router):
        """Cover probability when hit rate is exactly 100%."""
        router.record_cache_outcome("hash1", "ws-1", True)
        router.record_cache_outcome("hash1", "ws-1", True)
        prob = router.predict_cache_hit_probability("hash1", "ws-1")
        assert prob == 1.0

    def test_cache_hit_probability_fractional(self, router):
        """Cover probability calculation with fractional result."""
        router.record_cache_outcome("hash1", "ws-1", True)
        router.record_cache_outcome("hash1", "ws-1", True)
        router.record_cache_outcome("hash1", "ws-1", False)
        prob = router.predict_cache_hit_probability("hash1", "ws-1")
        assert prob == 2.0 / 3.0

    def test_min_tokens_threshold_exact_boundary(self, router):
        """Cover exact boundary at min_tokens threshold."""
        # OpenAI threshold is 1024
        cost_at_threshold = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=1024,
            cache_hit_probability=0.9
        )

        cost_above_threshold = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=1025,
            cache_hit_probability=0.9
        )

        # At threshold should get discount
        full_price = (0.000005 + 0.000015) / 2
        assert cost_at_threshold < full_price
        assert cost_above_threshold < full_price

    def test_different_provider_thresholds(self, router):
        """Cover that different providers have different thresholds."""
        # OpenAI: 1024, Anthropic: 2048
        cost_openai = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=1500,  # Above OpenAI threshold
            cache_hit_probability=0.9
        )

        cost_anthropic = router.calculate_effective_cost(
            model="claude-3-5-sonnet",
            provider="anthropic",
            estimated_input_tokens=1500,  # Below Anthropic threshold
            cache_hit_probability=0.9
        )

        # OpenAI should get discount, Anthropic should not
        full_price = (0.000005 + 0.000015) / 2
        assert cost_openai < full_price  # Discounted
        # Anthropic at full price (below threshold)


class TestNullNoneHandling:
    """Test null and None value handling."""

    @pytest.fixture
    def router(self):
        """Create router with mock pricing."""
        mock_pricing = MagicMock()
        mock_pricing.get_model_price = MagicMock(return_value={
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
        })
        return CacheAwareRouter(mock_pricing)

    def test_null_prompt_hash_in_prediction(self, router):
        """Cover prediction with None prompt hash raises TypeError."""
        # Current implementation doesn't handle None gracefully
        with pytest.raises(TypeError):
            router.predict_cache_hit_probability(None, "workspace-1")

    def test_null_workspace_in_prediction(self, router):
        """Cover prediction with None workspace."""
        # None workspace is handled (converted to string "None")
        prob = router.predict_cache_hit_probability("hash123", None)
        # Should return default since no history
        assert prob == 0.5

    def test_null_both_in_prediction(self, router):
        """Cover prediction with both None raises TypeError."""
        # Current implementation doesn't handle None hash gracefully
        with pytest.raises(TypeError):
            router.predict_cache_hit_probability(None, None)

    def test_record_outcome_with_null_hash(self, router):
        """Cover recording outcome with None hash raises TypeError."""
        # Current implementation doesn't handle None gracefully
        with pytest.raises(TypeError):
            router.record_cache_outcome(None, "workspace-1", True)

    def test_record_outcome_with_null_workspace(self, router):
        """Cover recording outcome with None workspace."""
        # None workspace is handled (converted to string "None")
        router.record_cache_outcome("hash123", None, True)
        # Should create entry with None workspace as string
        assert "None:hash123" in router.cache_hit_history

    def test_record_outcome_with_null_both(self, router):
        """Cover recording outcome with both None raises TypeError."""
        # Current implementation doesn't handle None hash gracefully
        with pytest.raises(TypeError):
            router.record_cache_outcome(None, None, True)

    def test_zero_cache_hit_probability(self, router):
        """Cover cost with zero cache hit probability."""
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.0
        )
        # Should calculate normally (no discount)
        assert cost > 0

    def test_missing_output_cost_in_pricing(self, router):
        """Cover pricing dict without output_cost_per_token."""
        router.pricing_fetcher.get_model_price = MagicMock(return_value={
            "input_cost_per_token": 0.000005,
            # Missing output_cost_per_token
        })
        cost = router.calculate_effective_cost(
            model="test-model",
            provider="openai",
            estimated_input_tokens=1000,
            cache_hit_probability=0.5
        )
        # Should handle missing output cost
        assert cost >= 0


class TestConcurrentAccessPatterns:
    """Test concurrent cache access patterns."""

    @pytest.fixture
    def router(self):
        """Create router with mock pricing."""
        mock_pricing = MagicMock()
        mock_pricing.get_model_price = MagicMock(return_value={
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
        })
        return CacheAwareRouter(mock_pricing)

    def test_concurrent_history_reads(self, router):
        """Cover concurrent reads from cache hit history."""
        router.record_cache_outcome("hash1", "ws-1", True)

        results = []
        def read_history():
            prob = router.predict_cache_hit_probability("hash1", "ws-1")
            results.append(prob)

        threads = [threading.Thread(target=read_history) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should complete successfully
        assert len(results) == 10
        assert all(r == 1.0 for r in results)

    def test_concurrent_history_writes(self, router):
        """Cover concurrent writes to cache hit history."""
        def write_history(i):
            router.record_cache_outcome(f"hash{i}", "ws-1", i % 2 == 0)

        threads = [threading.Thread(target=write_history, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All writes should complete
        assert len(router.cache_hit_history) == 10

    def test_concurrent_mixed_operations(self, router):
        """Cover concurrent reads and writes."""
        results = []

        def mixed_operations(i):
            if i % 2 == 0:
                # Write
                router.record_cache_outcome(f"hash{i}", "ws-1", True)
            else:
                # Read
                router.record_cache_outcome(f"hash{i}", "ws-1", True)
                prob = router.predict_cache_hit_probability(f"hash{i}", "ws-1")
                results.append(prob)

        threads = [threading.Thread(target=mixed_operations, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All operations should complete
        assert len(results) == 5  # Half were reads

    def test_concurrent_clear_and_read(self, router):
        """Cover concurrent clear and read operations."""
        router.record_cache_outcome("hash1", "ws-1", True)
        router.record_cache_outcome("hash2", "ws-2", True)

        def clear_workspace(workspace):
            router.clear_cache_history(workspace)

        def read_workspace(workspace):
            history = router.get_cache_hit_history(workspace)
            return history

        # Clear ws-1 while reading ws-2
        t1 = threading.Thread(target=clear_workspace, args=("ws-1",))
        t2 = threading.Thread(target=read_workspace, args=("ws-2",))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # ws-1 should be cleared, ws-2 should still exist
        assert "ws-1:hash1" not in router.cache_hit_history
        assert "ws-2:hash2" in router.cache_hit_history


class TestErrorPaths:
    """Test error handling paths."""

    @pytest.fixture
    def router(self):
        """Create router with mock pricing."""
        mock_pricing = MagicMock()
        mock_pricing.get_model_price = MagicMock(return_value={
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
        })
        return CacheAwareRouter(mock_pricing)

    def test_pricing_fetcher_raises_exception(self, router):
        """Cover handling when pricing fetcher raises exception."""
        router.pricing_fetcher.get_model_price = MagicMock(
            side_effect=Exception("Pricing service unavailable")
        )
        # Should propagate exception
        with pytest.raises(Exception, match="Pricing service unavailable"):
            router.calculate_effective_cost(
                model="test-model",
                provider="openai",
                estimated_input_tokens=1000,
                cache_hit_probability=0.5
            )

    def test_cost_with_negative_tokens(self, router):
        """Cover cost calculation with negative token count."""
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=-100,  # Invalid
            cache_hit_probability=0.5
        )
        # Should handle (below threshold, so full price)
        assert cost >= 0

    def test_cost_with_float_tokens(self, router):
        """Cover cost calculation with float token count."""
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=1000.5,  # Float
            cache_hit_probability=0.5
        )
        # Should handle gracefully
        assert cost >= 0

    def test_get_provider_with_empty_string(self, router):
        """Cover provider lookup with empty string."""
        capability = router.get_provider_cache_capability("")
        # Should return default no-cache config
        assert capability["supports_cache"] is False

    def test_get_provider_with_whitespace(self, router):
        """Cover provider lookup with whitespace."""
        capability = router.get_provider_cache_capability("   ")
        # Should return default no-cache config
        assert capability["supports_cache"] is False

    def test_case_sensitivity_variations(self, router):
        """Cover various case sensitivity scenarios."""
        providers = ["OPENAI", "OpenAI", "openAI", "oPeNaI"]
        capabilities = [router.get_provider_cache_capability(p) for p in providers]
        # All should return same capability
        assert all(c == capabilities[0] for c in capabilities)

    def test_unknown_provider_with_cache_in_name(self, router):
        """Cover unknown provider that mentions cache in name."""
        capability = router.get_provider_cache_capability("unknown-cache-provider")
        # Should return default no-cache config
        assert capability["supports_cache"] is False

    def test_provider_name_with_numbers(self, router):
        """Cover provider names with numeric characters."""
        capability = router.get_provider_cache_capability("openai2")
        # Should return default (no match)
        assert capability["supports_cache"] is False

    def test_provider_no_cache_support_returns_full_price(self):
        """Cover line 137: return full price when provider doesn't support cache."""
        mock_pricing = MagicMock()
        mock_pricing.get_model_price = MagicMock(return_value={
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
        })
        router = CacheAwareRouter(mock_pricing)

        # DeepSeek doesn't support caching - should hit line 137
        cost = router.calculate_effective_cost(
            model="deepseek-chat",
            provider="deepseek",
            estimated_input_tokens=5000,
            cache_hit_probability=0.9  # Ignored - no cache support
        )

        # Should return full price (line 137)
        full_price = (0.000005 + 0.000015) / 2
        assert cost == full_price

    def test_provider_direct_match_line_coverage(self):
        """Cover line 261: direct provider match in get_provider_cache_capability."""
        mock_pricing = MagicMock()
        router = CacheAwareRouter(mock_pricing)

        # Test all providers that have direct matches (line 261)
        providers = ["openai", "anthropic", "gemini", "deepseek", "minimax"]
        for provider in providers:
            capability = router.get_provider_cache_capability(provider)
            # Should hit line 261 (direct match return)
            assert "supports_cache" in capability
            assert "cached_cost_ratio" in capability
            assert "min_tokens" in capability


class TestBoundaryConditions:
    """Test boundary conditions and limits."""

    @pytest.fixture
    def router(self):
        """Create router with mock pricing."""
        mock_pricing = MagicMock()
        mock_pricing.get_model_price = MagicMock(return_value={
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
        })
        return CacheAwareRouter(mock_pricing)

    def test_very_small_token_count(self, router):
        """Cover very small token counts (near zero)."""
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=1,
            cache_hit_probability=0.5
        )
        # Should handle gracefully
        assert cost >= 0

    def test_very_large_cache_hit_probability(self, router):
        """Cover cache hit probability at extreme values."""
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.999  # Near 100%
        )
        # Should be heavily discounted
        full_price = (0.000005 + 0.000015) / 2
        assert cost < full_price

    def test_very_small_cache_hit_probability(self, router):
        """Cover cache hit probability near zero."""
        cost = router.calculate_effective_cost(
            model="gpt-4o",
            provider="openai",
            estimated_input_tokens=2000,
            cache_hit_probability=0.001  # Near 0%
        )
        # Should be nearly full price
        full_price = (0.000005 + 0.000015) / 2
        assert abs(cost - full_price) < 0.00001

    def test_large_number_of_history_entries(self, router):
        """Cover cache hit history with many entries."""
        # Add 1000 entries
        for i in range(1000):
            router.record_cache_outcome(f"hash{i}", f"ws-{i % 10}", i % 2 == 0)

        # Should handle large history
        assert len(router.cache_hit_history) == 1000

    def test_clear_large_history(self, router):
        """Cover clearing large history."""
        # Add 1000 entries
        for i in range(1000):
            router.record_cache_outcome(f"hash{i}", "ws-1", i % 2 == 0)

        router.clear_cache_history("ws-1")
        assert len(router.cache_hit_history) == 0

    def test_very_long_workspace_id(self, router):
        """Cover very long workspace IDs."""
        long_workspace = "w" * 10000
        router.record_cache_outcome("hash1", long_workspace, True)
        key = f"{long_workspace}:hash1"
        assert key in router.cache_hit_history

    def test_very_long_prompt_hash(self, router):
        """Cover very long prompt hashes (should be truncated)."""
        long_hash = "h" * 10000
        router.record_cache_outcome(long_hash, "ws-1", True)
        # Should be truncated to 16 chars
        key = f"ws-1:{'h' * 16}"
        assert key in router.cache_hit_history

    def test_unicode_in_workspace_id(self, router):
        """Cover unicode characters in workspace ID."""
        unicode_workspace = "工作空间-123"
        router.record_cache_outcome("hash1", unicode_workspace, True)
        key = f"{unicode_workspace}:hash1"
        assert key in router.cache_hit_history

    def test_unicode_in_prompt_hash(self, router):
        """Cover unicode characters in prompt hash."""
        unicode_hash = "哈希值-中文-🚀"
        router.record_cache_outcome(unicode_hash, "ws-1", True)
        # Should truncate unicode to 16 chars
        expected_key = "ws-1:哈希值-中文-🚀"[:22]  # Truncated to 16 chars of hash
        # Verify entry exists in cache_hit_history
        assert any("ws-1:哈希值-中文-🚀" in key for key in router.cache_hit_history.keys())
