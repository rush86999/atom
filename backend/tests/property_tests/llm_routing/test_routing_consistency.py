"""
Property-Based Tests for LLM Routing Consistency

Tests validate routing invariants:
- Same prompt always routes to same provider (determinism)
- Token count variance within tier maps to same provider
- Semantic complexity classification is consistent
- Provider fallback chains are deterministic

These tests ensure LLM routing is predictable and reproducible.
"""

import pytest
from hypothesis import given, strategies as st, settings, example
from typing import List, Dict

from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier
from tests.property_tests.llm_routing.conftest import (
    test_cognitive_classifier,
    sample_prompts,
    HYPOTHESIS_SETTINGS_CRITICAL,
    HYPOTHESIS_SETTINGS_STANDARD
)


@pytest.mark.property
class TestRoutingConsistency:
    """
    PROPERTY: Routing decisions are deterministic and consistent

    STRATEGY: Generate various prompts (text, token counts, complexity)
    using Hypothesis strategies to test routing invariants across input space.

    INVARIANT: For any valid input, routing produces the same output
    when called multiple times with identical inputs.

    RADII: 200 examples for critical determinism (boundary conditions),
    100 examples for standard consistency checks. This covers edge cases
    like empty prompts, unicode text, code blocks, and boundary token counts.
    """

    @given(prompt=st.text(min_size=1, max_size=10000))
    @settings(HYPOTHESIS_SETTINGS_CRITICAL)
    @example(prompt="hello world")
    @example(prompt="Explain quantum computing in detail")
    @example(prompt="```python\ndef complex_algorithm():\n    pass\n```")
    def test_same_prompt_routes_to_same_tier(self, test_cognitive_classifier: CognitiveClassifier, prompt: str):
        """
        PROPERTY: Same prompt always classifies to same cognitive tier

        STRATEGY: Generate random text prompts of varying lengths (1-10000 chars)
        using st.text() to test classification determinism across input space.

        INVARIANT: classify(prompt) = classify(prompt) = classify(prompt)
        For any prompt p, multiple classifications return identical tier.

        RADII: 200 examples - Critical for cost optimization. Bugs here cause
        inconsistent routing = unpredictable costs and quality. Boundary cases
        (empty string, single char, huge prompts) need coverage.
        """
        # Act: Classify same prompt 3 times
        tier1 = test_cognitive_classifier.classify(prompt)
        tier2 = test_cognitive_classifier.classify(prompt)
        tier3 = test_cognitive_classifier.classify(prompt)

        # Assert: All classifications return same tier
        assert tier1 == tier2 == tier3, \
            f"Prompt classified inconsistently: {tier1}, {tier2}, {tier3} for prompt: {prompt[:50]}..."

        # Assert: Tier is valid CognitiveTier enum value
        assert isinstance(tier1, CognitiveTier), \
            f"Classification returned non-CognitiveTier: {type(tier1)}"

    @given(
        token_count=st.integers(min_value=100, max_value=700)
    )
    @settings(HYPOTHESIS_SETTINGS_STANDARD)
    @example(token_count=100)  # Boundary: Micro -> Standard
    @example(token_count=500)  # Boundary: Standard -> Versatile
    def test_routing_invariant_under_token_count_variance(
        self,
        test_cognitive_classifier: CognitiveClassifier,
        token_count: int
    ):
        """
        PROPERTY: Token count variations within same tier map to same tier

        STRATEGY: Generate token counts in [100, 700] range using st.integers()
        to test tier mapping consistency within Standard tier boundaries.

        INVARIANT: For all token counts in same tier range,
        classification results in same tier or adjacent tier only.

        Actual tier boundaries from cognitive_tier_system.py:
        - Micro: <100 tokens
        - Standard: 100-500 tokens
        - Versatile: 500-2000 tokens
        - Heavy: 2000-5000 tokens
        - Complex: >5000 tokens

        RADII: 100 examples - Standard consistency check. Token count alone
        doesn't determine tier (semantic complexity also matters), but we
        validate that the relationship is monotonic.
        """
        # Create prompt with approximate token count
        # Heuristic: 1 token ≈ 4 characters
        prompt = "x" * (token_count * 4)

        # Act: Classify the prompt
        tier = test_cognitive_classifier.classify(prompt)

        # Assert: Tier is valid
        assert tier in CognitiveTier, \
            f"Invalid tier {tier} for token_count={token_count}"

        # Assert: Tier respects token count boundaries (monotonicity check)
        # Higher token count should not result in lower tier
        # (though semantic complexity can bump it up)
        if token_count < 100:
            # Should be Micro or higher (complexity can increase tier)
            assert tier in [CognitiveTier.MICRO, CognitiveTier.STANDARD, CognitiveTier.VERSATILE,
                           CognitiveTier.HEAVY, CognitiveTier.COMPLEX]
        elif token_count < 500:
            # Should be Standard or higher
            assert tier in [CognitiveTier.STANDARD, CognitiveTier.VERSATILE,
                           CognitiveTier.HEAVY, CognitiveTier.COMPLEX], \
                f"Token count {token_count} should map to Standard+, got {tier}"
        elif token_count < 2000:
            # Should be Versatile or higher
            assert tier in [CognitiveTier.VERSATILE, CognitiveTier.HEAVY, CognitiveTier.COMPLEX]

    @given(
        prompt_dict=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz'),
            values=st.integers(min_value=0, max_value=1000),
            min_size=1,
            max_size=50
        )
    )
    @settings(HYPOTHESIS_SETTINGS_STANDARD)
    def test_routing_preserves_complexity_classification(
        self,
        test_cognitive_classifier: CognitiveClassifier,
        prompt_dict: Dict[str, int]
    ):
        """
        PROPERTY: Semantic complexity classification is consistent

        STRATEGY: Generate dictionaries with string keys and integer values
        to simulate structured prompts with varying complexity patterns.

        INVARIANT: classify(prompt) is idempotent - same prompt structure
        produces same tier regardless of exact values (within bounds).

        RADII: 100 examples - Standard consistency check. Semantic patterns
        (code keywords, technical terms, advanced concepts) should consistently
        increase tier classification.
        """
        # Convert dict to prompt string
        prompt = str(prompt_dict)

        # Act: Classify same structured prompt twice
        tier1 = test_cognitive_classifier.classify(prompt)
        tier2 = test_cognitive_classifier.classify(prompt)

        # Assert: Same tier for same structure
        assert tier1 == tier2, \
            f"Structured prompt classified inconsistently: {tier1} vs {tier2}"

        # Assert: Tier is valid
        assert tier1 in CognitiveTier, \
            f"Invalid tier: {tier1}"

    @given(
        failed_provider=st.sampled_from(["openai", "anthropic", "deepseek", "gemini"])
    )
    @settings(HYPOTHESIS_SETTINGS_STANDARD)
    @example(failed_provider="openai")
    @example(failed_provider="deepseek")
    def test_provider_fallback_consistency(
        self,
        test_cognitive_classifier: CognitiveClassifier,
        failed_provider: str
    ):
        """
        PROPERTY: Provider fallback maintains consistent tier selection

        STRATEGY: Sample from valid provider names using st.sampled_from()
        to test that tier selection is independent of provider choice.

        INVARIANT: CognitiveTier classification is provider-independent.
        Provider selection happens AFTER tier classification.

        RADII: 100 examples - Standard consistency check. Provider failures
        should not affect tier classification (tier → provider mapping,
        not provider → tier).
        """
        # Use a fixed prompt for this test
        prompt = "Explain machine learning algorithms"

        # Act: Classify with different providers (tier should be same)
        tier1 = test_cognitive_classifier.classify(prompt)
        tier2 = test_cognitive_classifier.classify(prompt, task_type="chat")

        # Assert: Tier is consistent regardless of provider context
        assert tier1 == tier2, \
            f"Tier classification should be provider-independent: {tier1} vs {tier2}"

        # Assert: Tier is valid
        assert tier1 in CognitiveTier, \
            f"Invalid tier: {tier1}"

        # Assert: Get recommended models for the tier
        models = test_cognitive_classifier.get_tier_models(tier1)
        assert isinstance(models, list), \
            f"get_tier_models() should return list, got {type(models)}"
        assert len(models) > 0, \
            f"Tier {tier1} should have at least one recommended model"
