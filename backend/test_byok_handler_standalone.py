#!/usr/bin/env python3
"""
Standalone Tests for BYOK Handler (LLM Provider Management)

Coverage Target: 80%+
Priority: P0 (Critical LLM Infrastructure)
"""
import sys
import os
sys.path.insert(0, '.')
os.environ['ENVIRONMENT'] = 'development'

from core.llm.byok_handler import BYOKHandler, QueryComplexity, PROVIDER_TIERS, COST_EFFICIENT_MODELS
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


def test_query_complexity_enum():
    """Test QueryComplexity enum values"""
    print("Testing QueryComplexity enum...")
    assert QueryComplexity.SIMPLE.value == "simple"
    assert QueryComplexity.MODERATE.value == "moderate"
    assert QueryComplexity.COMPLEX.value == "complex"
    assert QueryComplexity.ADVANCED.value == "advanced"
    print("✓ QueryComplexity enum tests passed")


def test_provider_tiers_configuration():
    """Test PROVIDER_TIERS configuration"""
    print("Testing provider tiers configuration...")
    assert "deepseek" in PROVIDER_TIERS["budget"]
    assert "anthropic" in PROVIDER_TIERS["mid"]
    assert "openai" in PROVIDER_TIERS["premium"]
    print("✓ Provider tiers configuration tests passed")


def test_cost_efficient_models():
    """Test COST_EFFICIENT_MODELS recommendations"""
    print("Testing cost efficient models...")
    assert QueryComplexity.SIMPLE in COST_EFFICIENT_MODELS["openai"]
    assert QueryComplexity.ADVANCED in COST_EFFICIENT_MODELS["openai"]
    assert "claude" in COST_EFFICIENT_MODELS["anthropic"][QueryComplexity.SIMPLE].lower()
    print("✓ Cost efficient models tests passed")


def test_byok_handler_initialization():
    """Test BYOKHandler initialization"""
    print("Testing BYOKHandler initialization...")
    handler = BYOKHandler()
    assert hasattr(handler, 'async_clients')
    assert hasattr(handler, 'clients')
    assert hasattr(handler, 'workspace_id')
    assert hasattr(handler, 'health_monitor')
    print("✓ BYOKHandler initialization tests passed")


def test_analyze_query_complexity_simple():
    """Test query complexity analysis for simple queries"""
    print("Testing query complexity analysis (simple)...")
    handler = BYOKHandler()
    result = handler.analyze_query_complexity("What is 2+2?")
    assert result == QueryComplexity.SIMPLE
    print("✓ Query complexity analysis (simple) tests passed")


def test_analyze_query_complexity_advanced():
    """Test query complexity analysis for advanced queries"""
    print("Testing query complexity analysis (advanced)...")
    handler = BYOKHandler()
    result = handler.analyze_query_complexity(
        "Analyze this complex data and provide multi-step reasoning with code"
    )
    assert result in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]
    print("✓ Query complexity analysis (advanced) tests passed")


def test_get_optimal_provider():
    """Test optimal provider selection"""
    print("Testing optimal provider selection...")
    handler = BYOKHandler()
    provider = handler.get_optimal_provider("simple task", QueryComplexity.SIMPLE)
    assert provider is not None
    print("✓ Optimal provider selection tests passed")


def test_get_ranked_providers():
    """Test ranked providers"""
    print("Testing ranked providers...")
    handler = BYOKHandler()
    providers = handler.get_ranked_providers(QueryComplexity.SIMPLE)
    assert isinstance(providers, list)
    assert len(providers) > 0
    print("✓ Ranked providers tests passed")


def test_get_available_providers():
    """Test getting available providers"""
    print("Testing available providers...")
    handler = BYOKHandler()
    providers = handler.get_available_providers()
    assert isinstance(providers, list)
    print("✓ Available providers tests passed")


def test_get_provider_fallback_order():
    """Test provider fallback order"""
    print("Testing provider fallback order...")
    handler = BYOKHandler()
    fallbacks = handler._get_provider_fallback_order("openai")
    assert isinstance(fallbacks, list)
    assert fallbacks[0] == "openai"
    print("✓ Provider fallback order tests passed")


def test_get_context_window():
    """Test context window retrieval"""
    print("Testing context window retrieval...")
    handler = BYOKHandler()
    context = handler.get_context_window("gpt-4")
    assert isinstance(context, int)
    assert context > 0
    print("✓ Context window retrieval tests passed")


def test_truncate_to_context():
    """Test text truncation to context limit"""
    print("Testing text truncation...")
    handler = BYOKHandler()
    long_text = "test " * 10000
    truncated = handler.truncate_to_context(long_text, "gpt-4")
    assert isinstance(truncated, str)
    assert len(truncated) <= len(long_text)
    print("✓ Text truncation tests passed")


def test_classify_cognitive_tier():
    """Test cognitive tier classification"""
    print("Testing cognitive tier classification...")
    handler = BYOKHandler()
    tier = handler.classify_cognitive_tier("simple question")
    assert tier is not None
    print("✓ Cognitive tier classification tests passed")


def test_get_routing_info():
    """Test routing info"""
    print("Testing routing info...")
    handler = BYOKHandler()
    info = handler.get_routing_info("test prompt")
    assert isinstance(info, dict)
    assert "provider" in info or "complexity" in info
    print("✓ Routing info tests passed")


def test_provider_tier_coverage():
    """Test that all major providers are covered"""
    print("Testing provider tier coverage...")
    major_providers = ["openai", "anthropic", "deepseek", "gemini"]
    all_tier_providers = set()
    for tier_providers in PROVIDER_TIERS.values():
        all_tier_providers.update(tier_providers)
    for provider in major_providers:
        assert provider in all_tier_providers
    print("✓ Provider tier coverage tests passed")


def test_model_recommendation_coverage():
    """Test model recommendations exist for all complexities"""
    print("Testing model recommendation coverage...")
    for provider, models in COST_EFFICIENT_MODELS.items():
        for complexity in QueryComplexity:
            assert complexity in models
            assert models[complexity] is not None
    print("✓ Model recommendation coverage tests passed")


async def test_health_monitor():
    """Test health monitor"""
    print("Testing health monitor...")
    handler = BYOKHandler()
    handler.health_monitor.record_call("test-provider", success=True, latency_ms=100)
    assert handler.health_monitor is not None
    print("✓ Health monitor tests passed")


async def test_refresh_pricing():
    """Test pricing refresh"""
    print("Testing pricing refresh...")
    handler = BYOKHandler()
    result = await handler.refresh_pricing(force=False)
    assert isinstance(result, dict)
    print("✓ Pricing refresh tests passed")


def test_get_provider_comparison():
    """Test provider comparison"""
    print("Testing provider comparison...")
    handler = BYOKHandler()
    comparison = handler.get_provider_comparison()
    assert isinstance(comparison, dict)
    print("✓ Provider comparison tests passed")


def test_get_cheapest_models():
    """Test getting cheapest models"""
    print("Testing cheapest models...")
    handler = BYOKHandler()
    cheapest = handler.get_cheapest_models(limit=5)
    assert isinstance(cheapest, list)
    print("✓ Cheapest models tests passed")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Running BYOK Handler Tests (Standalone)")
    print("=" * 60)
    
    try:
        # Sync tests
        test_query_complexity_enum()
        test_provider_tiers_configuration()
        test_cost_efficient_models()
        test_byok_handler_initialization()
        test_analyze_query_complexity_simple()
        test_analyze_query_complexity_advanced()
        test_get_optimal_provider()
        test_get_ranked_providers()
        test_get_available_providers()
        test_get_provider_fallback_order()
        test_get_context_window()
        test_truncate_to_context()
        test_classify_cognitive_tier()
        test_get_routing_info()
        test_provider_tier_coverage()
        test_model_recommendation_coverage()
        test_get_provider_comparison()
        test_get_cheapest_models()
        
        # Async tests
        await test_health_monitor()
        await test_refresh_pricing()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
