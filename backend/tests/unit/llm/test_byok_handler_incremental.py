"""
Incremental tests for BYOK Handler

Phase 207-09: Coverage Quality Push
Target: Improve coverage from 25% to 40%

Focus: Test error paths, provider selection logic, cache-aware routing, and escalation
Missing lines: Provider fallback, error handling, cache recording, tier escalation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from core.llm.byok_handler import (
    BYOKHandler,
    QueryComplexity,
    PROVIDER_TIERS,
    COST_EFFICIENT_MODELS,
)
from core.models import AgentRegistry, AgentStatus


class TestProviderFallback:
    """Test provider fallback logic"""

    def test_get_provider_fallback_order(self):
        """Test provider fallback order calculation"""
        handler = BYOKHandler()

        # Mock available providers
        handler.clients = {
            "deepseek": Mock(),
            "openai": Mock(),
            "moonshot": Mock()
        }

        fallback_order = handler._get_provider_fallback_order("deepseek")

        # Should prioritize requested provider first, then others in priority order
        assert fallback_order[0] == "deepseek"
        assert "openai" in fallback_order
        assert len(fallback_order) == 3

    def test_get_provider_fallback_order_no_clients(self):
        """Test provider fallback when no clients available"""
        handler = BYOKHandler()
        handler.clients = {}

        fallback_order = handler._get_provider_fallback_order("deepseek")

        # Should return empty list
        assert fallback_order == []

    def test_get_provider_fallback_order_unavailable_provider(self):
        """Test fallback when requested provider is not available"""
        handler = BYOKHandler()

        # Mock available providers (not including requested provider)
        handler.clients = {
            "openai": Mock(),
            "moonshot": Mock()
        }

        fallback_order = handler._get_provider_fallback_order("deepseek")

        # Should skip deepseek and use available providers in priority order
        assert "deepseek" not in fallback_order
        assert "openai" in fallback_order
        assert len(fallback_order) == 2


class TestQueryComplexityAnalysis:
    """Test query complexity analysis"""

    def test_analyze_complexity_simple_queries(self):
        """Test complexity analysis for simple queries"""
        handler = BYOKHandler()

        # Simple query
        complexity = handler.analyze_query_complexity("hello, how are you?")
        assert complexity == QueryComplexity.SIMPLE

        # Short query
        complexity = handler.analyze_query_complexity("summarize this")
        assert complexity == QueryComplexity.SIMPLE

    def test_analyze_complexity_code_queries(self):
        """Test complexity analysis for code queries"""
        handler = BYOKHandler()

        # Code query
        complexity = handler.analyze_query_complexity("write a function to sort an array")
        assert complexity == QueryComplexity.COMPLEX

        # With code block
        complexity = handler.analyze_query_complexity("```python\ndef hello():\n    print('hi')\n```")
        assert complexity == QueryComplexity.COMPLEX

    def test_analyze_complexity_advanced_queries(self):
        """Test complexity analysis for advanced queries"""
        handler = BYOKHandler()

        # Advanced query
        complexity = handler.analyze_query_complexity("design a scalable microservices architecture for enterprise systems")
        assert complexity == QueryComplexity.ADVANCED


class TestTrialRestriction:
    """Test trial restriction logic"""

    def test_is_trial_restricted_no_workspace(self, db_session):
        """Test trial restriction when workspace doesn't exist"""
        from core.llm.byok_handler import BYOKHandler

        handler = BYOKHandler()
        handler.workspace_id = "nonexistent-workspace"

        # Should return False (no restriction) when workspace not found
        result = handler._is_trial_restricted()
        assert result is False


class TestCognitiveTierClassification:
    """Test cognitive tier classification"""

    def test_classify_cognitive_tier_simple(self):
        """Test cognitive tier classification for simple queries"""
        handler = BYOKHandler()

        tier = handler.classify_cognitive_tier("hello world")
        # Simple queries should be MICRO tier
        assert tier.value in ["micro", "standard"]

    def test_classify_cognitive_tier_code(self):
        """Test cognitive tier classification for code queries"""
        handler = BYOKHandler()

        tier = handler.classify_cognitive_tier("write a python function", task_type="code")
        # Code queries should be higher tier
        assert tier.value in ["versatile", "heavy", "complex"]


class TestContextWindow:
    """Test context window handling"""

    def test_get_context_window_known_model(self):
        """Test getting context window for known models"""
        handler = BYOKHandler()

        # Mock pricing fetcher
        with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
            mock_pricing = Mock()
            mock_pricing.get_model_price.return_value = {
                "max_input_tokens": 128000
            }
            mock_fetcher.return_value = mock_pricing

            context_window = handler.get_context_window("gpt-4o")
            assert context_window == 128000

    def test_get_context_window_unknown_model(self):
        """Test getting context window for unknown models"""
        handler = BYOKHandler()

        # Mock pricing fetcher to return None
        with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
            mock_pricing = Mock()
            mock_pricing.get_model_price.return_value = None
            mock_fetcher.return_value = mock_pricing

            context_window = handler.get_context_window("unknown-model")
            # Should return safe default
            assert context_window == 4096

    def test_truncate_to_context_no_truncation(self):
        """Test text truncation when within limits"""
        handler = BYOKHandler()

        text = "a" * 100
        truncated = handler.truncate_to_context(text, "gpt-4o", reserve_tokens=1000)

        # Should not truncate
        assert len(truncated) == 100

    def test_truncate_to_context_with_truncation(self):
        """Test text truncation when exceeding limits"""
        handler = BYOKHandler()

        # Create text that exceeds context window
        # gpt-4o has 128000 tokens, with reserve 1000 = 127000 tokens max input
        # At 4 chars per token, that's 508000 characters
        text = "a" * 600000  # Exceeds limit
        truncated = handler.truncate_to_context(text, "gpt-4o", reserve_tokens=1000)

        # Should truncate
        assert len(truncated) < 600000
        assert "truncated" in truncated.lower()


class TestRoutingInfo:
    """Test routing information"""

    def test_get_routing_info_success(self, db_session):
        """Test getting routing information"""
        handler = BYOKHandler()

        # Mock clients
        handler.clients = {"deepseek": Mock()}

        routing_info = handler.get_routing_info("test query")

        assert "complexity" in routing_info
        assert "selected_provider" in routing_info
        assert "selected_model" in routing_info
        assert "available_providers" in routing_info

    def test_get_routing_info_no_providers(self):
        """Test routing info when no providers available"""
        handler = BYOKHandler()
        handler.clients = {}

        routing_info = handler.get_routing_info("test query")

        assert "complexity" in routing_info
        assert "error" in routing_info
        assert routing_info["available_providers"] == []


class TestProviderComparison:
    """Test provider comparison"""

    def test_get_provider_comparison_success(self):
        """Test getting provider comparison"""
        handler = BYOKHandler()

        with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
            mock_pricing = Mock()
            mock_pricing.compare_providers.return_value = {
                "openai": {"avg_cost_per_token": 0.00003, "tier": "premium"},
                "deepseek": {"avg_cost_per_token": 0.000002, "tier": "budget"}
            }
            mock_fetcher.return_value = mock_pricing

            comparison = handler.get_provider_comparison()

            assert "openai" in comparison
            assert "deepseek" in comparison

    def test_get_provider_comparison_error(self):
        """Test provider comparison error handling"""
        handler = BYOKHandler()

        with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
            mock_fetcher.return_value = Mock(**{
                'compare_providers.side_effect': Exception("Pricing error")
            })

            comparison = handler.get_provider_comparison()

            # Should return static fallback
            assert "openai" in comparison
            assert "deepseek" in comparison


class TestCheapestModels:
    """Test cheapest models retrieval"""

    def test_get_cheapest_models(self):
        """Test getting cheapest models"""
        handler = BYOKHandler()

        with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
            mock_pricing = Mock()
            mock_pricing.get_cheapest_models.return_value = [
                {"model": "deepseek-chat", "cost": 0.000002},
                {"model": "gpt-4o-mini", "cost": 0.00001}
            ]
            mock_fetcher.return_value = mock_pricing

            models = handler.get_cheapest_models(limit=5)

            assert len(models) == 2

    def test_get_cheapest_models_error(self):
        """Test cheapest models error handling"""
        handler = BYOKHandler()

        with patch('core.llm.byok_handler.get_pricing_fetcher') as mock_fetcher:
            mock_fetcher.return_value = Mock(**{
                'get_cheapest_models.side_effect': Exception("Error")
            })

            models = handler.get_cheapest_models(limit=5)

            # Should return empty list on error
            assert models == []


class TestAvailableProviders:
    """Test available providers listing"""

    def test_get_available_providers(self):
        """Test getting list of available providers"""
        handler = BYOKHandler()

        # Mock clients
        handler.clients = {
            "deepseek": Mock(),
            "openai": Mock(),
            "anthropic": Mock()
        }

        providers = handler.get_available_providers()

        assert len(providers) == 3
        assert "deepseek" in providers
        assert "openai" in providers
        assert "anthropic" in providers

    def test_get_available_providers_empty(self):
        """Test getting available providers when none configured"""
        handler = BYOKHandler()
        handler.clients = {}

        providers = handler.get_available_providers()

        assert providers == []
