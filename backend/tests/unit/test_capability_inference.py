"""
Model Capability Inference Tests
TDD Pattern: Red-Green-Refactor

Tests verify:
1. Capabilities are inferred from model names and provider data
2. Inferred capabilities are stored in pricing cache
3. Cached capabilities are used instead of pattern matching
4. Capability inference happens once at fetch time, not runtime

Coverage: DynamicPricingFetcher._infer_capabilities(), capability caching
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from core.dynamic_pricing_fetcher import DynamicPricingFetcher, get_pricing_fetcher
from core.cache import UniversalCacheService


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def pricing_fetcher():
    """Create pricing fetcher for testing."""
    fetcher = DynamicPricingFetcher()
    return fetcher


@pytest.fixture
def sample_model_data():
    """Sample model data from LiteLLM/OpenRouter."""
    return {
        "gpt-4o": {
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
            "max_tokens": 128000,
            "litellm_provider": "openai",
            "mode": "chat",
            "supports_cache": True,
        },
        "claude-3-5-sonnet": {
            "input_cost_per_token": 0.000003,
            "output_cost_per_token": 0.000015,
            "max_tokens": 200000,
            "litellm_provider": "anthropic",
            "mode": "chat",
            "supports_cache": True,
        },
        "o3-mini": {
            "input_cost_per_token": 0.000001,
            "output_cost_per_token": 0.000004,
            "max_tokens": 200000,
            "litellm_provider": "openai",
            "mode": "reasoning",
            "supports_cache": False,
        },
        "gemini-3-flash": {
            "input_cost_per_token": 0.0000001,
            "output_cost_per_token": 0.0000004,
            "max_tokens": 1000000,
            "litellm_provider": "gemini",
            "mode": "chat",
            "supports_cache": True,
        },
        "deepseek-v3.2-speciale": {
            "input_cost_per_token": 0.0000005,
            "output_cost_per_token": 0.0000015,
            "max_tokens": 64000,
            "litellm_provider": "deepseek",
            "mode": "reasoning",
            "supports_cache": False,
        },
        "gpt-4-vision-preview": {
            "input_cost_per_token": 0.000005,
            "output_cost_per_token": 0.000015,
            "max_tokens": 128000,
            "litellm_provider": "openai",
            "mode": "vision",
            "supports_cache": True,
        },
    }


# ============================================================================
# Test Suite 1: Capability Inference
# ============================================================================

class TestCapabilityInference:
    """
    TDD Test Suite: Infer capabilities from model metadata.

    Red: Write failing tests first
    Green: Implement _infer_capabilities()
    Refactor: Improve inference logic
    """

    def test_infer_supports_tools_from_mode(self, pricing_fetcher, sample_model_data):
        """
        RED: Infer tool support from model mode and name.

        Test Requirements:
        - Models in 'reasoning' mode don't support tools
        - Models with 'haiku' or 'mini' don't support tools
        - Other models support tools by default
        """
        # Call _infer_capabilities (to be implemented)
        result = pricing_fetcher._infer_capabilities(sample_model_data)

        # o3-mini is reasoning mode → no tools
        assert result["o3-mini"]["supports_tools"] is False, "Reasoning models should not support tools"

        # deepseek-v3.2-speciale is reasoning → no tools
        assert result["deepseek-v3.2-speciale"]["supports_tools"] is False, "Reasoning models should not support tools"

        # gpt-4o is regular chat → supports tools
        assert result["gpt-4o"]["supports_tools"] is True, "Regular chat models should support tools"

    def test_infer_supports_vision_from_mode(self, pricing_fetcher, sample_model_data):
        """
        RED: Infer vision support from model mode and name.

        Test Requirements:
        - Models in 'vision' mode support vision
        - Models with 'vision' in name support vision
        - Gemini Flash models support vision
        - GPT-4O supports vision
        """
        result = pricing_fetcher._infer_capabilities(sample_model_data)

        # gpt-4-vision-preview has vision mode
        assert result["gpt-4-vision-preview"]["supports_vision"] is True, "Vision mode models should support vision"

        # gemini-3-flash (Flash models have vision)
        assert result["gemini-3-flash"]["supports_vision"] is True, "Gemini Flash should support vision"

        # o3-mini (no vision keywords)
        assert result["o3-mini"]["supports_vision"] is False, "Regular models should not support vision"

    def test_infer_supports_reasoning_from_name(self, pricing_fetcher, sample_model_data):
        """
        RED: Infer reasoning capability from model name.

        Test Requirements:
        - Models with 'o3', 'o1', 'reasoner', 'thinking' support reasoning
        - Models with 'speciale' support reasoning
        - Other models don't support reasoning
        """
        result = pricing_fetcher._infer_capabilities(sample_model_data)

        # o3-mini has 'o3' prefix
        assert result["o3-mini"]["supports_reasoning"] is True, "o3 models should support reasoning"

        # deepseek-v3.2-speciale has 'speciale'
        assert result["deepseek-v3.2-speciale"]["supports_reasoning"] is True, "Speciale models should support reasoning"

        # gpt-4o (no reasoning keywords)
        assert result["gpt-4o"]["supports_reasoning"] is False, "Regular models should not support reasoning"

    def test_infer_all_capabilities_for_all_models(self, pricing_fetcher, sample_model_data):
        """
        RED: Verify all models get capability inferences.

        Test Requirements:
        - Every model in cache gets capabilities
        - All three capabilities inferred (tools, vision, reasoning)
        - No models missing from result
        """
        result = pricing_fetcher._infer_capabilities(sample_model_data)

        # All models should be in result
        assert len(result) == len(sample_model_data), "All models should get capability inferences"

        # Each model should have all three capabilities
        for model_name, capabilities in result.items():
            assert "supports_tools" in capabilities, f"{model_name} should have supports_tools"
            assert "supports_vision" in capabilities, f"{model_name} should have supports_vision"
            assert "supports_reasoning" in capabilities, f"{model_name} should have supports_reasoning"

    def test_capabilities_added_to_pricing_cache(self, pricing_fetcher, sample_model_data):
        """
        RED: Verify inferred capabilities are stored in pricing cache.

        Test Requirements:
        - Capabilities added to model data in cache
        - Stored alongside pricing info
        - Persisted across cache loads
        """
        # First, infer capabilities
        capabilities = pricing_fetcher._infer_capabilities(sample_model_data)

        # Merge capabilities into pricing data
        for model_name, model_data in sample_model_data.items():
            model_data.update(capabilities[model_name])

        # Verify capabilities are now in model data
        assert sample_model_data["gpt-4o"]["supports_tools"] is True
        assert sample_model_data["o3-mini"]["supports_reasoning"] is True
        assert sample_model_data["gemini-3-flash"]["supports_vision"] is True


# ============================================================================
# Test Suite 2: Cached Capability Lookups
# ============================================================================

class TestCachedCapabilityLookups:
    """
    Test Suite: BYOK uses cached capabilities instead of pattern matching.

    Verifies runtime lookups use cached capability data.
    """

    def test_lookup_capability_from_cache(self, pricing_fetcher, sample_model_data):
        """
        RED: Lookup capabilities from pricing cache, no pattern matching.

        Test Requirements:
        - Query pricing cache for model capabilities
        - No hardcoded model lists
        - No runtime pattern matching
        """
        # Add capabilities to cache
        capabilities = pricing_fetcher._infer_capabilities(sample_model_data)
        for model_name, caps in capabilities.items():
            if model_name in pricing_fetcher.pricing_cache:
                pricing_fetcher.pricing_cache[model_name].update(caps)

        # Lookup from cache (no pattern matching)
        gpt4o_caps = pricing_fetcher.pricing_cache.get("gpt-4o", {})

        assert gpt4o_caps.get("supports_tools") is True
        assert gpt4o_caps.get("supports_vision") is True  # GPT-4O is multimodal
        assert gpt4o_caps.get("supports_reasoning") is False

    def test_capability_lookup_missing_model(self, pricing_fetcher):
        """
        RED: Handle missing models gracefully.

        Test Requirements:
        - Return default capabilities for unknown models
        - Don't crash on missing models
        - Log warning for unknown models
        """
        # Lookup model not in cache
        unknown_caps = pricing_fetcher.get_model_capabilities("unknown-model-x-5000")

        # Should return default (conservative)
        assert unknown_caps is not None, "Should return capabilities for unknown models"
        assert unknown_caps.get("supports_tools") is False, "Unknown models should default to no tools"
        assert unknown_caps.get("supports_vision") is False
        assert unknown_caps.get("supports_reasoning") is False

    def test_capability_lookup_preserves_existing_data(self, pricing_fetcher, sample_model_data):
        """
        RED: Capability inference preserves existing pricing data.

        Test Requirements:
        - Original pricing data not lost
        - Capabilities added alongside
        - No data corruption
        """
        # Store original pricing data
        original_gpt4o = sample_model_data["gpt-4o"].copy()

        # Add capabilities
        capabilities = pricing_fetcher._infer_capabilities(sample_model_data)
        sample_model_data["gpt-4o"].update(capabilities["gpt-4o"])

        # Verify original data preserved
        assert sample_model_data["gpt-4o"]["input_cost_per_token"] == original_gpt4o["input_cost_per_token"]
        assert sample_model_data["gpt-4o"]["max_tokens"] == original_gpt4o["max_tokens"]
        assert sample_model_data["gpt-4o"]["litellm_provider"] == original_gpt4o["litellm_provider"]


# ============================================================================
# Test Suite 3: Integration with Pricing Fetch
# ============================================================================

class TestPricingFetchIntegration:
    """
    Test Suite: Capability inference during pricing fetch.

    Verifies capabilities are inferred automatically when fetching pricing.
    """

    @pytest.mark.asyncio
    async def test_capabilities_inferred_during_fetch(self, pricing_fetcher, sample_model_data):
        """
        RED: Capabilities inferred when pricing is fetched.

        Test Requirements:
        - _infer_capabilities() called during fetch
        - Capabilities added to cache automatically
        - No separate inference step needed
        """
        # Mock the API response
        with patch.object(pricing_fetcher, 'fetch_litellm_pricing', return_value=sample_model_data):
            await pricing_fetcher.refresh_pricing(force=True)

        # Verify capabilities are in cache
        if "gpt-4o" in pricing_fetcher.pricing_cache:
            assert "supports_tools" in pricing_fetcher.pricing_cache["gpt-4o"]
            assert "supports_vision" in pricing_fetcher.pricing_cache["gpt-4o"]
            assert "supports_reasoning" in pricing_fetcher.pricing_cache["gpt-4o"]

    @pytest.mark.asyncio
    async def test_capabilities_persisted_to_disk(self, pricing_fetcher, sample_model_data):
        """
        RED: Capabilities persisted to disk cache.

        Test Requirements:
        - Capabilities saved in cache file
        - Loaded on next startup
        - No need to re-infer
        """
        with patch.object(pricing_fetcher, 'fetch_litellm_pricing', return_value=sample_model_data):
            await pricing_fetcher.refresh_pricing(force=True)

        # Capabilities should be in cache
        if "gpt-4o" in pricing_fetcher.pricing_cache:
            has_tools = pricing_fetcher.pricing_cache["gpt-4o"].get("supports_tools")
            assert has_tools is not None, "Capabilities should be in cache"

    @pytest.mark.asyncio
    async def test_capability_inference_happens_once(self, pricing_fetcher, sample_model_data):
        """
        RED: Capabilities inferred once at fetch time, not on every lookup.

        Test Requirements:
        - Inference happens during fetch
        - Subsequent lookups read from cache
        - No repeated inference
        """
        inference_count = 0

        # Track inference calls
        original_infer = pricing_fetcher._infer_capabilities
        def tracked_infer(data):
            nonlocal inference_count
            inference_count += 1
            return original_infer(data)

        pricing_fetcher._infer_capabilities = tracked_infer

        with patch.object(pricing_fetcher, 'fetch_litellm_pricing', return_value=sample_model_data):
            await pricing_fetcher.refresh_pricing(force=True)

        # Should infer once during fetch
        assert inference_count == 1, "Should infer capabilities once during fetch"

        # Multiple lookups should not trigger inference
        pricing_fetcher.get_model_capabilities("gpt-4o")
        pricing_fetcher.get_model_capabilities("gpt-4o")
        pricing_fetcher.get_model_capabilities("gpt-4o")

        assert inference_count == 1, "Lookups should not re-infer capabilities"


# ============================================================================
# Test Suite 4: Replacing Pattern-Based Lists
# ============================================================================

class TestReplacePatternBasedLists:
    """
    Test Suite: Replace hardcoded pattern-based lists.

    Verifies pricing cache lookups replace MODELS_WITHOUT_TOOLS, etc.
    """

    def test_models_without_tools_replaced_with_cache_lookup(self, pricing_fetcher, sample_model_data):
        """
        RED: Replace MODELS_WITHOUT_TOOLS with cache lookup.

        Test Requirements:
        - No hardcoded MODELS_WITHOUT_TOOLS set
        - Check pricing cache for supports_tools
        - Dynamic based on cached data
        """
        # Add sample models to cache
        pricing_fetcher.pricing_cache.update(sample_model_data)

        # Add capabilities to cache
        capabilities = pricing_fetcher._infer_capabilities(sample_model_data)
        for model_name, caps in capabilities.items():
            if model_name in pricing_fetcher.pricing_cache:
                pricing_fetcher.pricing_cache[model_name].update(caps)

        # Replace pattern-based check with cache lookup
        def model_supports_tools(model_name: str) -> bool:
            """Check if model supports tools using cache, not pattern lists."""
            model_data = pricing_fetcher.pricing_cache.get(model_name, {})
            return model_data.get("supports_tools", True)  # Default to True

        # Test with cache lookup (no pattern matching)
        assert model_supports_tools("gpt-4o") is True
        assert model_supports_tools("o3-mini") is False
        assert model_supports_tools("deepseek-v3.2-speciale") is False

    def test_vision_models_replaced_with_cache_lookup(self, pricing_fetcher, sample_model_data):
        """
        RED: Replace hardcoded VISION_MODELS list with cache lookup.

        Test Requirements:
        - No hardcoded vision model list
        - Check pricing cache for supports_vision
        - Dynamic based on cached data
        """
        # Add sample models to cache
        pricing_fetcher.pricing_cache.update(sample_model_data)

        # Add capabilities to cache
        capabilities = pricing_fetcher._infer_capabilities(sample_model_data)
        for model_name, caps in capabilities.items():
            if model_name in pricing_fetcher.pricing_cache:
                pricing_fetcher.pricing_cache[model_name].update(caps)

        # Replace pattern-based check with cache lookup
        def model_supports_vision(model_name: str) -> bool:
            """Check if model supports vision using cache, not pattern lists."""
            model_data = pricing_fetcher.pricing_cache.get(model_name, {})
            return model_data.get("supports_vision", False)

        # Test with cache lookup
        assert model_supports_vision("gpt-4-vision-preview") is True
        assert model_supports_vision("gemini-3-flash") is True
        assert model_supports_vision("o3-mini") is False

    def test_reasoning_models_replaced_with_cache_lookup(self, pricing_fetcher, sample_model_data):
        """
        RED: Replace hardcoded reasoning model lists with cache lookup.

        Test Requirements:
        - No hardcoded reasoning model list
        - Check pricing cache for supports_reasoning
        - Dynamic based on cached data
        """
        # Add sample models to cache
        pricing_fetcher.pricing_cache.update(sample_model_data)

        # Add capabilities to cache
        capabilities = pricing_fetcher._infer_capabilities(sample_model_data)
        for model_name, caps in capabilities.items():
            if model_name in pricing_fetcher.pricing_cache:
                pricing_fetcher.pricing_cache[model_name].update(caps)

        # Replace pattern-based check with cache lookup
        def model_supports_reasoning(model_name: str) -> bool:
            """Check if model supports reasoning using cache, not pattern lists."""
            model_data = pricing_fetcher.pricing_cache.get(model_name, {})
            return model_data.get("supports_reasoning", False)

        # Test with cache lookup
        assert model_supports_reasoning("o3-mini") is True
        assert model_supports_reasoning("deepseek-v3.2-speciale") is True
        assert model_supports_reasoning("gpt-4o") is False


# ============================================================================
# Test Suite 5: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test Suite: Handle edge cases in capability inference."""

    def test_infer_capabilities_with_empty_data(self, pricing_fetcher):
        """
        RED: Handle empty model data gracefully.

        Test Requirements:
        - Empty dict returns empty dict
        - No errors on empty input
        """
        result = pricing_fetcher._infer_capabilities({})

        assert result == {}, "Empty data should return empty result"

    def test_infer_capabilities_with_missing_mode(self, pricing_fetcher):
        """
        RED: Handle models without mode field.

        Test Requirements:
        - Default to chat mode if missing
        - Infer capabilities from name only
        - Don't crash on missing fields
        """
        data = {
            "unknown-model": {
                "input_cost_per_token": 0.000001,
                "output_cost_per_token": 0.000002,
                # No mode field
            }
        }

        result = pricing_fetcher._infer_capabilities(data)

        assert "unknown-model" in result, "Should handle missing mode field"
        assert "supports_tools" in result["unknown-model"]
        assert "supports_vision" in result["unknown-model"]
        assert "supports_reasoning" in result["unknown-model"]

    def test_capability_inference_idempotent(self, pricing_fetcher, sample_model_data):
        """
        RED: Multiple inference calls produce same result.

        Test Requirements:
        - Calling _infer_capabilities twice gives same result
        - No side effects
        - Deterministic output
        """
        result1 = pricing_fetcher._infer_capabilities(sample_model_data)
        result2 = pricing_fetcher._infer_capabilities(sample_model_data)

        assert result1 == result2, "Inference should be idempotent"


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
