"""
BYOKHandler Unit Tests

Tests cover:
- Provider selection and fallback logic
- Token counting and context window management
- Cost calculation and pricing comparison
- Query complexity analysis and cognitive tier classification
- Error handling and edge cases
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from typing import Dict, Any

from core.llm.byok_handler import BYOKHandler, QueryComplexity, CognitiveTier


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """Mock configuration for BYOKHandler."""
    return {
        "openai": {
            "api_key": "sk-test-openai",
            "models": ["gpt-4", "gpt-3.5-turbo"],
            "enabled": True
        },
        "anthropic": {
            "api_key": "sk-test-anthropic",
            "models": ["claude-3-opus", "claude-3-sonnet"],
            "enabled": True
        },
        "deepseek": {
            "api_key": "sk-test-deepseek",
            "models": ["deepseek-chat"],
            "enabled": True
        }
    }


@pytest.fixture
def handler(mock_config):
    """Create BYOKHandler instance with mocked configuration."""
    with patch('core.llm.byok_handler.CognitiveTierService'):
        return BYOKHandler(mock_config, tenant_id="test-tenant")


# ============================================================================
# Provider Selection Tests
# ============================================================================

class TestProviderSelection:
    """Test provider selection and fallback logic."""

    def test_get_provider_fallback_order_primary_available(self, handler):
        """Test fallback order when primary provider is available."""
        fallback = handler._get_provider_fallback_order("openai")
        assert "openai" in fallback
        assert fallback[0] == "openai"

    def test_get_provider_fallback_order_secondary_fallback(self, handler):
        """Test fallback order includes secondary providers."""
        fallback = handler._get_provider_fallback_order("openai")
        assert len(fallback) > 1
        assert "anthropic" in fallback or "deepseek" in fallback

    def test_get_available_providers(self, handler):
        """Test getting list of available providers."""
        providers = handler.get_available_providers()
        assert isinstance(providers, list)
        assert len(providers) >= 2
        assert "openai" in providers
        assert "anthropic" in providers

    @pytest.mark.asyncio
    async def test_get_optimal_provider_returns_provider(self, handler):
        """Test that optimal provider selection returns a valid provider."""
        with patch.object(handler, '_filter_by_health', return_value=True):
            provider = await handler.get_optimal_provider("test prompt")
            assert provider in ["openai", "anthropic", "deepseek"]

    @pytest.mark.asyncio
    async def test_get_ranked_providers_returns_list(self, handler):
        """Test that ranked providers returns a list."""
        with patch.object(handler, '_filter_by_health', return_value=True):
            ranked = await handler.get_ranked_providers("test prompt")
            assert isinstance(ranked, list)
            assert len(ranked) >= 2

    def test_filter_by_capabilities_approved_model(self, handler):
        """Test filtering by capabilities returns True for approved models."""
        result = handler._filter_by_capabilities("gpt-4", required_capability=None)
        assert result is True

    def test_filter_by_capabilities_unapproved_model(self, handler):
        """Test filtering by capabilities returns False for unapproved models."""
        result = handler._filter_by_capabilities("unknown-model", required_capability=None)
        assert result is False

    def test_filter_by_health_healthy_provider(self, handler):
        """Test health filter returns True for healthy providers."""
        with patch.object(handler, '_health_monitor', get_health_status=lambda x: "healthy"):
            result = handler._filter_by_health("openai")
            assert result is True


# ============================================================================
# Token Counting & Context Window Tests
# ============================================================================

class TestTokenCounting:
    """Test token counting and context window management."""

    def test_get_context_window_known_model(self, handler):
        """Test getting context window for known models."""
        # GPT-4 has 8192 context window
        window = handler.get_context_window("gpt-4")
        assert window > 0
        assert isinstance(window, int)

    def test_get_context_window_unknown_model_defaults(self, handler):
        """Test that unknown models get a default context window."""
        window = handler.get_context_window("unknown-model")
        assert window > 0
        assert window >= 4096  # Minimum default

    def test_truncate_to_context_short_text(self, handler):
        """Test truncation with short text (no truncation needed)."""
        short_text = "This is a short text"
        result = handler.truncate_to_context(short_text, "gpt-4")
        assert result == short_text

    def test_truncate_to_context_long_text(self, handler):
        """Test truncation with very long text."""
        # Create text longer than context window
        long_text = "word " * 10000  # ~50,000 characters
        result = handler.truncate_to_context(long_text, "gpt-4", reserve_tokens=1000)
        # Should be truncated to fit context window
        assert len(result) < len(long_text)
        assert len(result) > 0


# ============================================================================
# Cost Calculation & Pricing Tests
# ============================================================================

class TestCostCalculation:
    """Test cost calculation and pricing comparison."""

    @pytest.mark.asyncio
    async def test_refresh_pricing_returns_dict(self, handler):
        """Test that pricing refresh returns a dictionary."""
        pricing = await handler.refresh_pricing()
        assert isinstance(pricing, dict)
        assert len(pricing) > 0

    def test_get_provider_comparison_returns_comparison(self, handler):
        """Test getting provider comparison returns structured data."""
        comparison = handler.get_provider_comparison()
        assert isinstance(comparison, dict)
        assert "providers" in comparison or "comparison" in comparison

    def test_get_cheapest_models_returns_list(self, handler):
        """Test getting cheapest models returns a list."""
        with patch.object(handler, '_pricing_data', {
            "gpt-4": {"input_cost": 0.03},
            "gpt-3.5-turbo": {"input_cost": 0.001},
            "claude-3-opus": {"input_cost": 0.015}
        }):
            cheapest = handler.get_cheapest_models(limit=5)
            assert isinstance(cheapest, list)
            assert len(cheapest) <= 5
            assert len(cheapest) > 0


# ============================================================================
# Query Complexity & Cognitive Tier Tests
# ============================================================================

class TestQueryComplexity:
    """Test query complexity analysis and cognitive tier classification."""

    def test_analyze_query_complexity_simple_query(self, handler):
        """Test complexity analysis for simple queries."""
        complexity = handler.analyze_query_complexity("hello world", None)
        assert complexity in [QueryComplexity.LOW, QueryComplexity.MEDIUM]

    def test_analyze_query_complexity_complex_query(self, handler):
        """Test complexity analysis for complex queries."""
        complex_query = "Analyze the following data and provide detailed insights: " + \
                        "large dataset with multiple variables and correlations"
        complexity = handler.analyze_query_complexity(complex_query, "analysis")
        assert complexity in [QueryComplexity.MEDIUM, QueryComplexity.HIGH]

    def test_classify_cognitive_tier_low_complexity(self, handler):
        """Test cognitive tier classification for low complexity."""
        with patch.object(handler, 'analyze_query_complexity', return_value=QueryComplexity.LOW):
            tier = handler.classify_cognitive_tier("simple query", None)
            assert tier in [CognitiveTier.MICRO, CognitiveTier.STANDARD]

    def test_classify_cognitive_tier_high_complexity(self, handler):
        """Test cognitive tier classification for high complexity."""
        with patch.object(handler, 'analyze_query_complexity', return_value=QueryComplexity.HIGH):
            tier = handler.classify_cognitive_tier("complex analysis query", "analysis")
            assert tier in [CognitiveTier.HEAVY, CognitiveTier.COMPLEX]


# ============================================================================
# Routing Tests
# ============================================================================

class TestRouting:
    """Test routing logic and decision making."""

    def test_get_routing_info_returns_dict(self, handler):
        """Test that routing info returns structured dictionary."""
        routing = handler.get_routing_info("test prompt", None)
        assert isinstance(routing, dict)
        assert "primary_provider" in routing or "recommended_provider" in routing

    def test_get_routing_info_includes_complexity(self, handler):
        """Test that routing info includes complexity analysis."""
        routing = handler.get_routing_info("test prompt", "chat")
        assert "complexity" in routing or "tier" in routing or "provider" in routing


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_is_trial_restricted_detects_trial(self, handler):
        """Test trial restriction detection."""
        with patch.object(handler, '_tenant_plan', "trial"):
            assert handler._is_trial_restricted() is True

    def test_is_trial_restricted_allows_enterprise(self, handler):
        """Test that enterprise plans are not restricted."""
        with patch.object(handler, '_tenant_plan', "enterprise"):
            assert handler._is_trial_restricted() is False

    def test_get_provider_fallback_order_handles_unknown_provider(self, handler):
        """Test fallback order with unknown primary provider."""
        fallback = handler._get_provider_fallback_order("unknown-provider")
        assert isinstance(fallback, list)
        assert len(fallback) > 0  # Should still have fallback options


# ============================================================================
# Initialization Tests
# ============================================================================

class TestInitialization:
    """Test BYOKHandler initialization and setup."""

    def test_initialization_creates_clients(self, mock_config):
        """Test that initialization creates provider clients."""
        with patch('core.llm.byok_handler.CognitiveTierService'):
            handler = BYOKHandler(mock_config, tenant_id="test-tenant")
            assert handler is not None
            assert handler._tenant_id == "test-tenant"

    def test_initialization_with_empty_config(self):
        """Test initialization with empty configuration."""
        with patch('core.llm.byok_handler.CognitiveTierService'):
            handler = BYOKHandler({}, tenant_id="test-tenant")
            assert handler is not None
            assert handler.get_available_providers() == []


# ============================================================================
# Streaming Tests
# ============================================================================

class TestStreaming:
    """Test streaming completion functionality."""

    @pytest.mark.asyncio
    async def test_stream_completion_streams_tokens(self, handler):
        """Test that stream completion yields tokens."""
        with patch.object(handler, '_clients', {
            "openai": Mock()
        }):
            # Mock streaming response
            mock_response = AsyncMock()
            mock_response.__aiter__.return_value = iter(["token1", "token2", "token3"])

            with patch.object(handler, '_get_client', return_value=Mock(
                stream=AsyncMock(return_value=mock_response)
            )):
                tokens = []
                async for token in handler.stream_completion("test", "openai"):
                    tokens.append(token)
                assert len(tokens) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
