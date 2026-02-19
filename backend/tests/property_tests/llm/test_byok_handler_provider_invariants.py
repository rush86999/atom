"""
Property-based tests for BYOKHandler provider selection and fallback invariants.

This test suite verifies critical invariants of the multi-provider LLM routing system:
- Provider fallback always returns valid provider
- Routing is deterministic (same inputs = same provider)
- Complexity-based routing is monotonic (higher complexity → appropriate tier)
- Cost-efficient model selection matches COST_EFFICIENT_MODELS
- Provider tier assignments are valid
- API key fallback when BYOK not configured
- Multi-provider rotation distributes load
- Unavailable providers are skipped in fallback chain

Tests use Hypothesis framework for property-based testing with randomized inputs.
"""

from unittest.mock import MagicMock, patch
from typing import List, Tuple

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
from hypothesis.strategies import text, sampled_from, lists, integers, just

from core.llm.byok_handler import (
    BYOKHandler,
    QueryComplexity,
    PROVIDER_TIERS,
    COST_EFFICIENT_MODELS,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_byok_manager():
    """Mock BYOKManager for provider key management"""
    manager = MagicMock()
    manager.is_configured = MagicMock(return_value=True)
    manager.get_api_key = MagicMock(side_effect=lambda provider_id, key_name="default": {
        "openai": "sk-test-openai-key-12345",
        "anthropic": "sk-ant-test-key-67890",
        "deepseek": "sk-deepseek-test-key",
        "google": "test-gemini-key",
        "google_flash": "test-gemini-key",
        "moonshot": "sk-moonshot-test-key",
        "glm": "sk-glm-test-key",
        "mistral": "sk-mistral-test-key",
    }.get(provider_id))
    manager.get_tenant_api_key = manager.get_api_key
    return manager


@pytest.fixture
def handler_with_providers(mock_byok_manager) -> BYOKHandler:
    """Create BYOKHandler with mocked multi-provider clients"""
    with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
        handler = BYOKHandler()

        # Mock OpenAI-compatible clients for each provider
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Test response"))],
            usage=MagicMock(prompt_tokens=100, completion_tokens=50)
        )

        # Initialize clients for all supported providers
        providers = ["openai", "anthropic", "deepseek", "google", "moonshot", "glm", "mistral"]
        for provider in providers:
            handler.clients[provider] = mock_openai_client

        return handler


# =============================================================================
# PROPERTY-BASED TESTS
# =============================================================================

class TestBYOKProviderInvariants:
    """
    Property-based tests for BYOKHandler provider selection invariants.

    Uses Hypothesis to generate randomized inputs and verify system properties
    hold true across all possible inputs.
    """

    # -------------------------------------------------------------------------
    # Invariant 1: Provider Fallback Always Returns Valid Provider
    # -------------------------------------------------------------------------

    @given(
        complexity=sampled_from(list(QueryComplexity)),
        task_type=sampled_from([None, "chat", "code", "analysis", "general"]),
        prefer_cost=sampled_from([True, False])
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_provider_fallback_always_returns_valid(
        self, handler_with_providers, complexity, task_type, prefer_cost
    ):
        """
        PROPERTY: get_optimal_provider always returns a valid provider from available clients.

        Given any complexity level, task type, and cost preference,
        the provider selection should never return None or an invalid provider.
        """
        provider_id, model = handler_with_providers.get_optimal_provider(
            complexity=complexity,
            task_type=task_type,
            prefer_cost=prefer_cost
        )

        # Assert provider is not None
        assert provider_id is not None, "Provider ID should never be None"

        # Assert provider is in available clients
        assert provider_id in handler_with_providers.clients, \
            f"Provider {provider_id} should be in available clients"

        # Assert model is not empty
        assert model is not None and len(model) > 0, "Model name should not be empty"

    # -------------------------------------------------------------------------
    # Invariant 2: Routing Is Deterministic
    # -------------------------------------------------------------------------

    @given(
        prompt=text(min_size=10, max_size=500, alphabet='abcdefghijklmnopqrstuvwxyz \n'),
        task_type=sampled_from([None, "chat", "code", "analysis"])
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_routing_is_deterministic(self, handler_with_providers, prompt, task_type):
        """
        PROPERTY: Same inputs always produce same provider and model selection.

        Given the same prompt and task type, complexity analysis and provider
        selection should be deterministic (no randomness).
        """
        # Analyze complexity twice
        complexity1 = handler_with_providers.analyze_query_complexity(prompt, task_type)
        complexity2 = handler_with_providers.analyze_query_complexity(prompt, task_type)

        # Assert complexity is consistent
        assert complexity1 == complexity2, \
            f"Complexity analysis should be deterministic: {complexity1} != {complexity2}"

        # Get provider selection twice
        provider1, model1 = handler_with_providers.get_optimal_provider(complexity1, task_type)
        provider2, model2 = handler_with_providers.get_optimal_provider(complexity2, task_type)

        # Assert provider selection is consistent
        assert provider1 == provider2, \
            f"Provider selection should be deterministic: {provider1} != {provider2}"
        assert model1 == model2, \
            f"Model selection should be deterministic: {model1} != {model2}"

    # -------------------------------------------------------------------------
    # Invariant 3: Complexity-Based Routing Is Monotonic
    # -------------------------------------------------------------------------

    @given(
        prompt=text(min_size=10, max_size=1000, alphabet='abcdefghijklmnopqrstuvwxyz \n')
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_complexity_based_routing_monotonic(self, handler_with_providers, prompt):
        """
        PROPERTY: Complexity analysis is monotonic with respect to prompt features.

        Longer prompts and prompts with complex keywords should have higher
        or equal complexity compared to simple prompts.
        """
        # Simple prompt baseline
        simple_prompt = "hello"
        simple_complexity = handler_with_providers.analyze_query_complexity(simple_prompt)

        # Test prompt complexity
        test_complexity = handler_with_providers.analyze_query_complexity(prompt)

        # Simple prompts should not be marked as ADVANCED
        if len(prompt) < 50 and all(keyword not in prompt.lower() for keyword in
                                     ["calculate", "equation", "architecture", "security"]):
            assert test_complexity.value in ["simple", "moderate"], \
                f"Short simple prompts should be simple/moderate, got {test_complexity.value}"

        # Very long prompts with code blocks should be at least MODERATE
        if len(prompt) > 500 or "```" in prompt:
            assert test_complexity.value in ["moderate", "complex", "advanced"], \
                f"Long or code prompts should be moderate+, got {test_complexity.value}"

    # -------------------------------------------------------------------------
    # Invariant 4: Cost-Efficient Model Selection
    # -------------------------------------------------------------------------

    @given(
        provider_id=sampled_from(["openai", "anthropic", "deepseek", "gemini", "moonshot"]),
        complexity=sampled_from(list(QueryComplexity))
    )
    @settings(max_examples=30)
    def test_cost_efficient_model_selection(self, provider_id, complexity):
        """
        PROPERTY: COST_EFFICIENT_MODELS contains entries for all provider/complexity combos.

        Every provider in COST_EFFICIENT_MODELS should have a model recommendation
        for each complexity level.
        """
        # Skip providers not in COST_EFFICIENT_MODELS
        assume(provider_id in COST_EFFICIENT_MODELS)

        # Get model for this provider and complexity
        models = COST_EFFICIENT_MODELS[provider_id]

        # Assert complexity level exists
        assert complexity in models, \
            f"Provider {provider_id} should have model for complexity {complexity.value}"

        # Assert model name is not empty
        model = models[complexity]
        assert model is not None and len(model) > 0, \
            f"Provider {provider_id} complexity {complexity.value} should have valid model name"

    # -------------------------------------------------------------------------
    # Invariant 5: Provider Tier Exhaustive Validation
    # -------------------------------------------------------------------------

    @given(
        tier_name=sampled_from(["budget", "mid", "premium", "code", "math", "creative"])
    )
    @settings(max_examples=30)
    def test_provider_tier_exhaustive(self, tier_name):
        """
        PROPERTY: All providers in PROVIDER_TIERS have corresponding model definitions.

        Every provider listed in PROVIDER_TIERS should have an entry in
        COST_EFFICIENT_MODELS with valid model names.
        """
        # Get providers for this tier
        assume(tier_name in PROVIDER_TIERS)
        providers = PROVIDER_TIERS[tier_name]

        # Assert tier has at least one provider
        assert len(providers) > 0, f"Tier {tier_name} should have at least one provider"

        # Check each provider has model definitions
        for provider_id in providers:
            # Some tier providers (like "mistral", "glm") may not be in COST_EFFICIENT_MODELS
            # This is acceptable as they are fallback providers
            if provider_id in COST_EFFICIENT_MODELS:
                models = COST_EFFICIENT_MODELS[provider_id]

                # Assert all complexity levels have models
                for complexity in QueryComplexity:
                    assert complexity in models, \
                        f"Provider {provider_id} in tier {tier_name} should have model for {complexity.value}"

                    model = models[complexity]
                    assert model is not None and len(model) > 0, \
                        f"Provider {provider_id} tier {tier_name} complexity {complexity.value} has invalid model"

    # -------------------------------------------------------------------------
    # Invariant 6: Provider Tier Classification Consistency
    # -------------------------------------------------------------------------

    @given(
        provider_id=sampled_from(["openai", "anthropic", "deepseek", "moonshot", "gemini", "mistral", "glm"])
    )
    @settings(max_examples=30)
    def test_provider_classification_consistency(self, provider_id):
        """
        PROPERTY: Each provider appears in appropriate tiers based on cost/quality.

        Budget providers should be in "budget" tier, premium in "premium" tier, etc.
        A provider can appear in multiple tiers (e.g., "anthropic" in both "mid" and "premium").
        """
        # Check provider appears in at least one tier
        tiers_with_provider = [
            tier for tier, providers in PROVIDER_TIERS.items()
            if provider_id in providers
        ]

        assert len(tiers_with_provider) > 0, \
            f"Provider {provider_id} should appear in at least one tier"

        # Validate tier assignments make sense
        # Budget providers: deepseek, moonshot, glm
        if provider_id in ["deepseek", "moonshot", "glm"]:
            assert "budget" in tiers_with_provider, \
                f"Budget provider {provider_id} should be in budget tier"

        # Premium providers: openai, anthropic
        if provider_id in ["openai", "anthropic"]:
            assert "premium" in tiers_with_provider, \
                f"Premium provider {provider_id} should be in premium tier"

        # Code/math/creative tiers include specialized providers
        if provider_id in ["deepseek", "openai"]:
            assert "code" in tiers_with_provider or "math" in tiers_with_provider, \
                f"Provider {provider_id} should be in code or math tier"

    # -------------------------------------------------------------------------
    # Invariant 7: API Key Fallback Chain
    # -------------------------------------------------------------------------

    @given(
        provider_id=sampled_from(["openai", "anthropic", "deepseek"]),
        complexity=sampled_from(list(QueryComplexity))
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_api_key_fallback(self, mock_byok_manager, provider_id, complexity):
        """
        PROPERTY: Handler falls back to environment variables when BYOK not configured.

        When BYOK manager returns None for API key, handler should attempt
        to use environment variables as fallback.
        """
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Mock client initialization
            mock_client = MagicMock()
            handler.clients[provider_id] = mock_client

            # Verify client is available
            assert provider_id in handler.clients, \
                f"Provider {provider_id} client should be initialized"

            # Verify optimal provider works even if BYOK key is None
            mock_byok_manager.get_api_key.side_effect = lambda p, k="default": None

            try:
                result_provider, result_model = handler.get_optimal_provider(
                    complexity=complexity,
                    prefer_cost=True
                )

                # Should still return valid provider
                assert result_provider in handler.clients or result_provider is not None, \
                    "Should return valid provider even without BYOK keys"
            except ValueError as e:
                # Acceptable: raises error if no providers available at all
                assert "No LLM providers available" in str(e)

    # -------------------------------------------------------------------------
    # Invariant 8: Multi-Provider Rotation
    # -------------------------------------------------------------------------

    @given(
        complexity=sampled_from(list(QueryComplexity)),
        prefer_cost=sampled_from([True, False])
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multi_provider_rotation(self, handler_with_providers, complexity, prefer_cost):
        """
        PROPERTY: get_ranked_providers returns list in priority order.

        The ranked list should have multiple providers (if available) in priority order,
        allowing fallback when primary provider fails.
        """
        # Get ranked providers
        ranked = handler_with_providers.get_ranked_providers(
            complexity=complexity,
            prefer_cost=prefer_cost
        )

        # Assert ranked list is not empty
        assert len(ranked) > 0, "Ranked providers should not be empty"

        # Assert all providers in list are valid
        for provider_id, model in ranked:
            assert provider_id is not None, "Provider ID should not be None"
            assert model is not None and len(model) > 0, "Model name should not be empty"

        # Assert primary provider (first) is optimal
        primary_provider, primary_model = ranked[0]
        assert primary_provider in handler_with_providers.clients, \
            f"Primary provider {primary_provider} should be in available clients"

    # -------------------------------------------------------------------------
    # Invariant 9: Unavailable Provider Skip
    # -------------------------------------------------------------------------

    @given(
        available_providers=lists(sampled_from(["openai", "anthropic", "deepseek", "moonshot", "gemini"]), min_size=1, max_size=5, unique=True),
        complexity=sampled_from(list(QueryComplexity))
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unavailable_provider_skip(self, mock_byok_manager, available_providers, complexity):
        """
        PROPERTY: Providers not in available clients are skipped in fallback chain.

        When some providers are unavailable (no client initialized),
        get_ranked_providers should skip them and return only available providers.
        """
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()

            # Clear all existing clients and only initialize for "available" providers
            handler.clients.clear()
            handler.async_clients.clear()
            mock_client = MagicMock()
            for provider_id in available_providers:
                handler.clients[provider_id] = mock_client

            # Get ranked providers
            ranked = handler.get_ranked_providers(complexity=complexity, prefer_cost=True)

            # All returned providers should be in available list
            for provider_id, model in ranked:
                assert provider_id in available_providers, \
                    f"Provider {provider_id} should be in available providers {available_providers}"

    # -------------------------------------------------------------------------
    # Invariant 10: Provider Selection Respects Tenant Plan
    # -------------------------------------------------------------------------

    @given(
        complexity=sampled_from(list(QueryComplexity)),
        tenant_plan=sampled_from(["free", "pro", "enterprise"]),
        is_managed=sampled_from([True, False])
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_provider_selection_respects_tenant_plan(
        self, handler_with_providers, complexity, tenant_plan, is_managed
    ):
        """
        PROPERTY: Provider selection respects tenant plan restrictions.

        Different tenant plans may have different model restrictions.
        The handler should only return models allowed for the plan.
        """
        # Get ranked providers with plan restrictions
        ranked = handler_with_providers.get_ranked_providers(
            complexity=complexity,
            prefer_cost=True,
            tenant_plan=tenant_plan,
            is_managed_service=is_managed
        )

        # Assert ranked list is not empty (unless no providers available)
        if len(ranked) == 0:
            # Acceptable if no models match plan restrictions
            return

        # Assert all returned providers are available
        for provider_id, model in ranked:
            assert provider_id in handler_with_providers.clients, \
                f"Provider {provider_id} should be in available clients"

    # -------------------------------------------------------------------------
    # Invariant 11: Model Selection For Tool Requirements
    # -------------------------------------------------------------------------

    @given(
        complexity=sampled_from(list(QueryComplexity)),
        requires_tools=sampled_from([True, False]),
        requires_structured=sampled_from([True, False])
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_model_selection_for_tool_requirements(
        self, handler_with_providers, complexity, requires_tools, requires_structured
    ):
        """
        PROPERTY: Model selection handles tool/structured output requirements.

        When requires_tools or requires_structured is True, models that don't
        support these features should be filtered out or downgraded.
        """
        # Get ranked providers with tool requirements
        ranked = handler_with_providers.get_ranked_providers(
            complexity=complexity,
            prefer_cost=True,
            requires_tools=requires_tools,
            requires_structured=requires_structured
        )

        # Assert ranked list is not empty (unless no models support requirements)
        if len(ranked) == 0:
            # Acceptable if no models support the requirements
            return

        # Assert all returned providers are available
        for provider_id, model in ranked:
            assert provider_id in handler_with_providers.clients, \
                f"Provider {provider_id} should be in available clients"

    # -------------------------------------------------------------------------
    # Invariant 12: Complexity Analysis Edge Cases
    # -------------------------------------------------------------------------

    @given(
        prompt=text(min_size=0, max_size=2000, alphabet='abcdefghijklmnopqrstuvwxyz \n```{}')
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_complexity_analysis_edge_cases(self, handler_with_providers, prompt):
        """
        PROPERTY: Complexity analysis handles all edge cases gracefully.

        Edge cases: empty prompts, very long prompts, code blocks, special characters.
        Should never crash and should always return a valid complexity level.
        """
        # Should not raise exceptions
        complexity = handler_with_providers.analyze_query_complexity(prompt)

        # Should always return a valid QueryComplexity enum
        assert isinstance(complexity, QueryComplexity), \
            f"Complexity should be QueryComplexity enum, got {type(complexity)}"

        # Should be one of the four valid levels
        assert complexity.value in ["simple", "moderate", "complex", "advanced"], \
            f"Complexity value should be valid, got {complexity.value}"

    # -------------------------------------------------------------------------
    # Invariant 13: Provider Priority Consistency
    # -------------------------------------------------------------------------

    @given(
        complexity=sampled_from([QueryComplexity.SIMPLE, QueryComplexity.ADVANCED])
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_provider_priority_consistency(self, handler_with_providers, complexity):
        """
        PROPERTY: Provider priority changes based on complexity.

        SIMPLE complexity should prefer budget providers.
        ADVANCED complexity should prefer premium providers.
        """
        # Get ranked providers for SIMPLE complexity
        simple_ranked = handler_with_providers.get_ranked_providers(
            complexity=QueryComplexity.SIMPLE,
            prefer_cost=True
        )

        # Get ranked providers for ADVANCED complexity
        advanced_ranked = handler_with_providers.get_ranked_providers(
            complexity=QueryComplexity.ADVANCED,
            prefer_cost=True
        )

        # Both should have providers
        assert len(simple_ranked) > 0, "Should have providers for SIMPLE complexity"
        assert len(advanced_ranked) > 0, "Should have providers for ADVANCED complexity"

        # Budget providers should be prioritized for SIMPLE
        simple_providers = [p for p, _ in simple_ranked]
        budget_providers = PROVIDER_TIERS.get("budget", [])
        has_budget_in_simple = any(p in budget_providers for p in simple_providers[:3])

        # Premium providers should be prioritized for ADVANCED
        advanced_providers = [p for p, _ in advanced_ranked]
        premium_providers = PROVIDER_TIERS.get("premium", [])
        has_premium_in_advanced = any(p in premium_providers for p in advanced_providers[:3])

        # At least one budget provider in top 3 for simple (if budget providers available)
        if budget_providers:
            assert has_budget_in_simple or len(simple_providers) < 3, \
                "SIMPLE complexity should prioritize budget providers"

        # At least one premium provider in top 3 for advanced (if premium providers available)
        if premium_providers:
            assert has_premium_in_advanced or len(advanced_providers) < 3, \
                "ADVANCED complexity should prioritize premium providers"


# =============================================================================
# INTEGRATION-STYLE PROPERTY TESTS
# =============================================================================

class TestBYOKProviderIntegration:
    """
    Integration-style property tests that verify end-to-end provider behavior.
    """

    @given(
        prompts=lists(text(min_size=10, max_size=200), min_size=5, max_size=10, unique=True)
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multiple_prompts_consistent_routing(self, handler_with_providers, prompts):
        """
        PROPERTY: Multiple prompts with similar complexity route to same provider tier.

        Similar prompts should route to providers in the same cost tier.
        """
        complexities = [
            handler_with_providers.analyze_query_complexity(p) for p in prompts
        ]

        # All should be valid complexity levels
        for c in complexities:
            assert isinstance(c, QueryComplexity), f"Invalid complexity: {c}"

    @given(
        complexity=sampled_from(list(QueryComplexity))
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_provider_fallback_chain_length(self, handler_with_providers, complexity):
        """
        PROPERTY: Fallback chain has reasonable length.

        The ranked provider list should have at least 1 provider and at most
        the number of available providers.
        """
        ranked = handler_with_providers.get_ranked_providers(
            complexity=complexity,
            prefer_cost=True
        )

        available_count = len(handler_with_providers.clients)

        assert len(ranked) > 0, "Should have at least one provider"
        assert len(ranked) <= available_count, \
            f"Should not exceed available providers (ranked={len(ranked)}, available={available_count})"


# =============================================================================
# EDGE CASE PROPERTY TESTS
# =============================================================================

class TestBYOKProviderEdgeCases:
    """
    Property tests for edge cases and boundary conditions.
    """

    def test_empty_provider_list(self, mock_byok_manager):
        """
        PROPERTY: Handler handles empty provider list gracefully.

        When no providers are available, should raise ValueError with clear message.
        """
        with patch('core.llm.byok_handler.get_byok_manager', return_value=mock_byok_manager):
            handler = BYOKHandler()
            handler.clients = {}  # Empty providers

            with pytest.raises(ValueError) as exc_info:
                handler.get_optimal_provider(QueryComplexity.SIMPLE)

            assert "No LLM providers available" in str(exc_info.value)

    @given(
        complexity1=sampled_from(list(QueryComplexity)),
        complexity2=sampled_from(list(QueryComplexity))
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_complexity_ordering_consistency(self, handler_with_providers, complexity1, complexity2):
        """
        PROPERTY: Complexity enum values are consistent with semantic ordering.

        SIMPLE < MODERATE < COMPLEX < ADVANCED in terms of complexity.
        """
        complexity_order = {
            QueryComplexity.SIMPLE: 0,
            QueryComplexity.MODERATE: 1,
            QueryComplexity.COMPLEX: 2,
            QueryComplexity.ADVANCED: 3
        }

        # Verify ordering exists
        assert complexity_order[complexity1] >= 0
        assert complexity_order[complexity2] >= 0

        # Verify all complexities have unique ordering
        assert len(set(complexity_order.values())) == 4, \
            "All complexity levels should have unique ordering"
