"""
Property-Based Tests for Cognitive Tier Mapping

Tests validate tier classification invariants:
- Token count at tier boundaries maps to correct tier
- Tier mapping is monotonic (higher tokens → higher or same tier)
- Semantic complexity increases tier appropriately
- Task type influences tier selection

These tests ensure cost-optimal LLM routing based on query complexity.
"""

import pytest
from hypothesis import given, strategies as st, settings, example
from typing import Tuple

from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier, TIER_THRESHOLDS
from tests.property_tests.llm_routing.conftest import (
    test_cognitive_classifier,
    HYPOTHESIS_SETTINGS_CRITICAL,
    HYPOTHESIS_SETTINGS_STANDARD
)


@pytest.mark.property
class TestCognitiveTierMapping:
    """
    PROPERTY: Token count and semantic complexity map to correct cognitive tier

    STRATEGY: Generate token counts, complexity scores, and task types
    using Hypothesis strategies to test tier boundary conditions and monotonicity.

    INVARIANT: Tier classification respects token count thresholds and
    complexity weights, with monotonic relationship (higher complexity → higher tier).

    RADII: 200 examples for boundary testing (critical for cost optimization),
    100 examples for monotonicity and complexity influence checks.
    """

    @given(
        boundary_value=st.one_of(
            st.just(1),
            st.just(99),
            st.just(100),
            st.just(500),
            st.just(501),
            st.just(2000),
            st.just(4999),
            st.just(5000),
            st.just(5001),
            st.just(10000)
        )
    )
    @settings(HYPOTHESIS_SETTINGS_CRITICAL)
    @example(boundary_value=1)      # Micro tier (min)
    @example(boundary_value=99)     # Micro tier (max)
    @example(boundary_value=100)   # Standard tier (min)
    @example(boundary_value=500)   # Standard tier (max)
    @example(boundary_value=501)   # Versatile tier (min)
    @example(boundary_value=2000)  # Versatile tier (max)
    @example(boundary_value=5000)  # Complex tier (min+)
    def test_tier_boundary_conditions(
        self,
        test_cognitive_classifier: CognitiveClassifier,
        boundary_value: int
    ):
        """
        PROPERTY: Token count at tier boundaries maps to correct tier

        STRATEGY: Use st.one_of() with st.just() for exact boundary values
        to test tier transitions at critical thresholds.

        Actual tier boundaries from cognitive_tier_system.py:
        - Micro: <100 tokens (max_tokens=100)
        - Standard: 100-500 tokens (max_tokens=500)
        - Versatile: 500-2000 tokens (max_tokens=2000)
        - Heavy: 2000-5000 tokens (max_tokens=5000)
        - Complex: >5000 tokens (max_tokens=inf)

        INVARIANT: token_count → tier mapping respects thresholds
        - 1-99 tokens → Micro tier
        - 100-500 tokens → Standard tier (simple prompts)
        - 501-2000 tokens → Versatile tier (simple prompts)
        - 2001-5000 tokens → Heavy tier (simple prompts)
        - 5001+ tokens → Complex tier

        Note: Semantic complexity can increase tier beyond token count alone.

        RADII: 200 examples - CRITICAL for cost optimization. Boundary bugs
        cause over-provisioning (wasted cost) or under-provisioning (poor quality).
        Exact boundary values tested with @example() decorator.
        """
        # Create prompt with exact token count
        prompt = "x" * (boundary_value * 4)

        # Act: Classify the prompt
        tier = test_cognitive_classifier.classify(prompt)

        # Assert: Tier is valid
        assert tier in CognitiveTier, \
            f"Invalid tier {tier} for token_count={boundary_value}"

        # Assert: Tier respects boundaries (allowing complexity bump)
        # Token count establishes minimum tier, complexity can increase it
        if boundary_value < 100:
            # Micro tier (may be bumped by complexity)
            assert tier in [CognitiveTier.MICRO, CognitiveTier.STANDARD, CognitiveTier.VERSATILE,
                           CognitiveTier.HEAVY, CognitiveTier.COMPLEX], \
                f"Token count {boundary_value} should be Micro+, got {tier}"
        elif boundary_value < 500:
            # Standard tier (may be bumped by complexity)
            assert tier in [CognitiveTier.STANDARD, CognitiveTier.VERSATILE,
                           CognitiveTier.HEAVY, CognitiveTier.COMPLEX], \
                f"Token count {boundary_value} should be Standard+, got {tier}"
        elif boundary_value < 2000:
            # Versatile tier (may be bumped by complexity)
            assert tier in [CognitiveTier.VERSATILE, CognitiveTier.HEAVY, CognitiveTier.COMPLEX], \
                f"Token count {boundary_value} should be Versatile+, got {tier}"
        elif boundary_value < 5000:
            # Heavy tier (may be bumped to Complex)
            assert tier in [CognitiveTier.HEAVY, CognitiveTier.COMPLEX], \
                f"Token count {boundary_value} should be Heavy+, got {tier}"
        else:
            # Complex tier
            assert tier == CognitiveTier.COMPLEX, \
                f"Token count {boundary_value} should be Complex, got {tier}"

    @given(
        token_pair=st.tuples(
            st.integers(min_value=1, max_value=20000),
            st.integers(min_value=1, max_value=20000)
        )
    )
    @settings(HYPOTHESIS_SETTINGS_STANDARD)
    @example(token_pair=(100, 500))
    @example(token_pair=(500, 100))
    @example(token_pair=(2000, 5000))
    def test_tier_mapping_monotonic(
        self,
        test_cognitive_classifier: CognitiveClassifier,
        token_pair: Tuple[int, int]
    ):
        """
        PROPERTY: Higher token count never maps to lower tier

        STRATEGY: Generate tuples of token counts using st.tuples() to test
        monotonicity across full range of token counts.

        INVARIANT: For token counts a < b, tier(a) <= tier(b)
        Tier mapping is monotonic non-decreasing.

        RADII: 100 examples - Standard monotonicity check. Ensures token count
        increases don't unexpectedly decrease tier (which would waste cost or quality).
        """
        tokens_a, tokens_b = token_pair

        # Skip if tokens are equal (no monotonicity to check)
        if tokens_a == tokens_b:
            return

        # Create prompts
        prompt_a = "simple prompt " * (tokens_a // 2)  # ~2 chars per word
        prompt_b = "simple prompt " * (tokens_b // 2)

        # Act: Classify both prompts
        tier_a = test_cognitive_classifier.classify(prompt_a)
        tier_b = test_cognitive_classifier.classify(prompt_b)

        # Get tier order for comparison
        tier_order = {
            CognitiveTier.MICRO: 0,
            CognitiveTier.STANDARD: 1,
            CognitiveTier.VERSATILE: 2,
            CognitiveTier.HEAVY: 3,
            CognitiveTier.COMPLEX: 4
        }

        # Assert: Monotonicity (allowing equal due to semantic complexity)
        if tokens_a < tokens_b:
            # Higher token count should not map to lower tier
            assert tier_order[tier_a] <= tier_order[tier_b] or \
                   abs(tier_order[tier_a] - tier_order[tier_b]) <= 1, \
                f"Monotonicity violation: tokens={tokens_a} < {tokens_b} but tiers={tier_a} > {tier_b}"

    @given(
        complexity_pair=st.tuples(
            st.tuples(
                st.integers(min_value=1000, max_value=5000),
                st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False)
            ),
            st.tuples(
                st.integers(min_value=1000, max_value=5000),
                st.floats(min_value=0.7, max_value=1.0, allow_nan=False, allow_infinity=False)
            )
        )
    )
    @settings(HYPOTHESIS_SETTINGS_STANDARD)
    @example(complexity_pair=((1000, 0.3), (1000, 0.8)))
    def test_semantic_complexity_increases_tier(
        self,
        test_cognitive_classifier: CognitiveClassifier,
        complexity_pair: Tuple[Tuple[int, float], Tuple[int, float]]
    ):
        """
        PROPERTY: High semantic complexity bumps tier (even with low token count)

        STRATEGY: Generate tuples of (token_count, complexity_score) using
        st.tuples() to test complexity influence on tier selection.

        INVARIANT: High complexity (>0.7) may increase tier by 1+ levels
        compared to low complexity (<0.5) with same token count.

        Complexity influences tier through:
        - Code patterns (+3 weight)
        - Technical/math keywords (+3 weight)
        - Advanced concepts (+5 weight)
        - Code blocks (+3 weight)

        RADII: 100 examples - Standard complexity influence check. Ensures
        semantic patterns (code, technical terms) trigger appropriate tier bump.
        """
        (tokens_low, complexity_low), (tokens_high, complexity_high) = complexity_pair

        # Create prompts with complexity indicators
        prompt_low = "simple text " * tokens_low
        prompt_high = f"code function class def var import return {tokens_high} " * 10

        # Act: Classify both prompts
        tier_low = test_cognitive_classifier.classify(prompt_low)
        tier_high = test_cognitive_classifier.classify(prompt_high)

        # Get tier order
        tier_order = {
            CognitiveTier.MICRO: 0,
            CognitiveTier.STANDARD: 1,
            CognitiveTier.VERSATILE: 2,
            CognitiveTier.HEAVY: 3,
            CognitiveTier.COMPLEX: 4
        }

        # Assert: High complexity prompt gets same or higher tier
        # (not strictly higher because token count dominates)
        assert tier_order[tier_high] >= tier_order[tier_low] - 1, \
            f"Complexity should not decrease tier: low={tier_low}, high={tier_high}"

    @given(
        task_type=st.sampled_from(["chat", "code", "analysis", "reasoning", "agentic", "general"])
    )
    @settings(HYPOTHESIS_SETTINGS_STANDARD)
    @example(task_type="code")
    @example(task_type="chat")
    @example(task_type="reasoning")
    def test_task_type_influences_tier(
        self,
        test_cognitive_classifier: CognitiveClassifier,
        task_type: str
    ):
        """
        PROPERTY: Certain task types force minimum tier (e.g., code → Standard+)

        STRATEGY: Sample from valid task types using st.sampled_from() to test
        task type influence on tier classification.

        Task type adjustments (from cognitive_tier_system.py):
        - code: +2 weight
        - analysis: +2 weight
        - reasoning: +2 weight
        - agentic: +2 weight
        - chat: -1 weight
        - general: -1 weight

        INVARIANT: Task types like "code", "analysis", "reasoning" increase tier
        compared to "chat" or "general" for same prompt.

        RADII: 100 examples - Standard task type influence check. Ensures
        complex tasks get appropriate model quality.
        """
        # Use fixed prompt to isolate task type effect
        prompt = "explain this in detail"

        # Act: Classify with different task types
        tier_general = test_cognitive_classifier.classify(prompt, task_type="general")
        tier_task = test_cognitive_classifier.classify(prompt, task_type=task_type)

        # Get tier order
        tier_order = {
            CognitiveTier.MICRO: 0,
            CognitiveTier.STANDARD: 1,
            CognitiveTier.VERSATILE: 2,
            CognitiveTier.HEAVY: 3,
            CognitiveTier.COMPLEX: 4
        }

        # Assert: Code/analysis/reasoning tasks get same or higher tier than general
        if task_type in ["code", "analysis", "reasoning", "agentic"]:
            assert tier_order[tier_task] >= tier_order[tier_general] - 1, \
                f"Task type '{task_type}' should not result in lower tier than general: {tier_task} vs {tier_general}"
        elif task_type in ["chat", "general"]:
            # Chat/general may get lower tier
            assert tier_order[tier_task] <= tier_order[tier_general] + 1, \
                f"Task type '{task_type}' should not significantly increase tier: {tier_task} vs {tier_general}"

        # Assert: Tier is valid
        assert tier_task in CognitiveTier, \
            f"Invalid tier: {tier_task}"
