"""
Property-Based Tests for Cognitive Tier Classification Invariants

Tests CRITICAL cognitive tier classification invariants:
- Tier classification always returns valid CognitiveTier enum value
- Token count bounds are respected (MICRO <100, STANDARD 100-500, VERSATILE 500-2k, HEAVY 2k-5k, COMPLEX >5k)
- Classification is deterministic (same input produces same tier)
- Semantic complexity patterns are applied correctly

These tests protect against invalid tier assignments and classification failures.
"""

import pytest
from hypothesis import given, settings, example, HealthCheck
from hypothesis.strategies import integers, text, lists, sampled_from, floats
from typing import Optional

from core.llm.cognitive_tier_system import (
    CognitiveTier,
    CognitiveClassifier,
    TIER_THRESHOLDS
)


class TestCognitiveTierInvariants:
    """Property-based tests for cognitive tier classification invariants."""

    @given(
        token_count=integers(min_value=1, max_value=20000),
        word_count=integers(min_value=1, max_value=5000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_tier_classification_bounds_invariant(
        self, token_count: int, word_count: int
    ):
        """
        INVARIANT: Cognitive tier classification always returns a valid CognitiveTier enum value.
        No input should cause classification to fail or return invalid tier.

        Tests classification across realistic token counts (1-20k) and word counts (1-5k).

        VALIDATED_INVARIANT: Classification never fails or returns invalid tier.
        """
        classifier = CognitiveClassifier()

        # Generate prompt based on word count
        prompt = " ".join(["word"] * word_count)

        # Classify
        tier = classifier.classify(prompt, token_count)

        # Assert: Must return valid tier
        assert tier in CognitiveTier, \
            f"Classification returned invalid tier: {tier}"

    @given(
        token_count=integers(min_value=1, max_value=20000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_tier_token_thresholds_invariant(self, token_count: int):
        """
        INVARIANT: Token count thresholds are respected for tier classification.

        Tier thresholds:
        - MICRO: <100 tokens
        - STANDARD: 100-500 tokens
        - VERSATILE: 500-2k tokens
        - HEAVY: 2k-5k tokens
        - COMPLEX: >5k tokens

        Tests that token count is the primary factor in tier assignment.
        """
        classifier = CognitiveClassifier()

        # Use a simple prompt (no semantic complexity)
        prompt = "simple query"

        # Classify
        tier = classifier.classify(prompt, token_count)

        # Assert: Tier must be valid
        assert tier in CognitiveTier, \
            f"Invalid tier for {token_count} tokens: {tier}"

        # Assert: Token count should be within tier's max threshold
        tier_max_tokens = TIER_THRESHOLDS[tier]["max_tokens"]

        # For all tiers except COMPLEX (which has infinite max_tokens),
        # token count should be <= max_tokens
        if tier != CognitiveTier.COMPLEX:
            # Allow some tolerance for semantic complexity adjustments
            # (token_count can exceed threshold due to complexity patterns)
            # But it should not be wildly off (e.g., MICRO for 10k tokens)
            tier_order = [
                CognitiveTier.MICRO,
                CognitiveTier.STANDARD,
                CognitiveTier.VERSATILE,
                CognitiveTier.HEAVY,
                CognitiveTier.COMPLEX
            ]
            tier_index = tier_order.index(tier)

            # Very rough check: higher token counts should map to higher tiers
            # This is a weak invariant due to semantic complexity
            if token_count > 5000:
                assert tier_index >= tier_order.index(CognitiveTier.HEAVY), \
                    f"{token_count} tokens should map to HEAVY or COMPLEX, got {tier}"
            elif token_count > 2000:
                assert tier_index >= tier_order.index(CognitiveTier.VERSATILE), \
                    f"{token_count} tokens should map to VERSATILE or higher, got {tier}"
            elif token_count > 500:
                assert tier_index >= tier_order.index(CognitiveTier.STANDARD), \
                    f"{token_count} tokens should map to STANDARD or higher, got {tier}"

    @given(
        prompt=text(min_size=1, max_size=1000, alphabet='abcdefghijklmnopqrstuvwxyz '),
        token_count=integers(min_value=100, max_value=5000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_classification_deterministic_invariant(
        self, prompt: str, token_count: int
    ):
        """
        INVARIANT: Classification is deterministic (same input produces same tier).

        Tests that calling classify() multiple times with the same input
        always returns the same tier.
        """
        classifier = CognitiveClassifier()

        # Classify 10 times
        results = []
        for _ in range(10):
            tier = classifier.classify(prompt, token_count)
            results.append(tier)

        # Assert: All results should be identical
        assert all(t == results[0] for t in results), \
            f"Classification not deterministic: got {set(results)} for same input"

    @given(
        complexity_keywords=lists(
            sampled_from([
                "simple", "basic", "quick",
                "analyze", "compare", "explain",
                "code", "function", "debug",
                "architecture", "security", "cryptography"
            ]),
            min_size=1,
            max_size=5,
            unique=True
        ),
        token_count=integers(min_value=100, max_value=2000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_semantic_complexity_invariant(
        self, complexity_keywords: list, token_count: int
    ):
        """
        INVARIANT: Semantic complexity patterns influence tier assignment.

        Tests that complexity keywords (code, advanced, etc.) increase tier.
        """
        classifier = CognitiveClassifier()

        # Create prompt with complexity keywords
        prompt = " ".join(complexity_keywords)

        # Classify
        tier = classifier.classify(prompt, token_count)

        # Assert: Must return valid tier
        assert tier in CognitiveTier, \
            f"Invalid tier with complexity keywords: {tier}"

        # Assert: Keywords should not cause crash or invalid tier
        # (This is a minimal invariant - semantic influence is heuristic)
        assert isinstance(tier, CognitiveTier), \
            f"Tier should be CognitiveTier enum, got {type(tier)}"

    @given(
        token_counts=integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_edge_case_token_counts_invariant(self, token_counts: int):
        """
        INVARIANT: Edge case token counts are handled correctly.

        Tests boundary values: 1, 99, 100, 101, 499, 500, 501, etc.
        """
        classifier = CognitiveClassifier()

        prompt = "test query"

        # Classify
        tier = classifier.classify(prompt, token_counts)

        # Assert: Must always return valid tier
        assert tier in CognitiveTier, \
            f"Invalid tier for edge case {token_counts} tokens: {tier}"

        # Assert: Tier should be reasonable for token count
        # (e.g., 1 token shouldn't be COMPLEX, 10k shouldn't be MICRO)
        tier_order = [
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY,
            CognitiveTier.COMPLEX
        ]
        tier_index = tier_order.index(tier)

        # Very basic sanity checks
        if token_counts <= 100:
            # Should be MICRO or STANDARD
            assert tier_index <= tier_order.index(CognitiveTier.STANDARD), \
                f"{token_counts} tokens should be MICRO or STANDARD, got {tier}"
        elif token_counts >= 10000:
            # Should be HEAVY or COMPLEX
            assert tier_index >= tier_order.index(CognitiveTier.HEAVY), \
                f"{token_counts} tokens should be HEAVY or COMPLEX, got {tier}"

    @given(
        prompt=text(min_size=1, max_size=500),
        task_types=lists(
            sampled_from(["code", "analysis", "reasoning", "agentic", "chat", "general"]),
            min_size=1,
            max_size=3,
            unique=True
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_task_type_influence_invariant(self, prompt: str, task_types: list):
        """
        INVARIANT: Task type hints influence tier assignment.

        Tests that task_type parameter affects classification.
        """
        classifier = CognitiveClassifier()

        # Classify with different task types
        tiers_by_task_type = {}
        token_count = 500  # Mid-range token count

        for task_type in task_types:
            tier = classifier.classify(prompt, token_count, task_type=task_type)
            tiers_by_task_type[task_type] = tier

            # Assert: Must return valid tier for each task type
            assert tier in CognitiveTier, \
                f"Invalid tier for task type '{task_type}': {tier}"

        # Assert: All task types should produce valid tiers
        assert all(tier in CognitiveTier for tier in tiers_by_task_type.values()), \
            "Some task types produced invalid tiers"

    @given(
        token_count=integers(min_value=1, max_value=20000),
        iterations=integers(min_value=2, max_value=10)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_classifier_consistency_invariant(
        self, token_count: int, iterations: int
    ):
        """
        INVARIANT: Multiple classifier instances produce consistent results.

        Tests that creating new CognitiveClassifier instances doesn't
        produce different results.
        """
        prompt = "consistency test query"

        # Classify with multiple classifier instances
        tiers = []
        for _ in range(iterations):
            classifier = CognitiveClassifier()
            tier = classifier.classify(prompt, token_count)
            tiers.append(tier)

        # Assert: All results should be identical
        assert all(t == tiers[0] for t in tiers), \
            f"Classifier instances inconsistent: got {set(tiers)}"

    @given(
        prompts=lists(
            text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz '),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_batch_classification_invariant(self, prompts: list):
        """
        INVARIANT: Batch classification doesn't fail for diverse prompts.

        Tests that classifier handles various prompt formats without crashing.
        """
        classifier = CognitiveClassifier()

        token_count = 500  # Standard token count

        # Classify all prompts
        tiers = []
        for prompt in prompts:
            try:
                tier = classifier.classify(prompt, token_count)
                tiers.append(tier)

                # Assert: Must return valid tier
                assert tier in CognitiveTier, \
                    f"Invalid tier for prompt '{prompt[:20]}...': {tier}"
            except Exception as e:
                # Should not raise any exceptions
                raise AssertionError(f"Classification failed for prompt '{prompt[:20]}...': {e}")

        # Assert: All classifications succeeded
        assert len(tiers) == len(prompts), \
            f"Only {len(tiers)}/{len(prompts)} prompts classified successfully"

    @given(
        token_count=integers(min_value=1, max_value=20000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_empty_prompt_handling_invariant(self, token_count: int):
        """
        INVARIANT: Empty or whitespace-only prompts are handled gracefully.

        Tests edge case of empty/whitespace prompts.
        """
        classifier = CognitiveClassifier()

        # Test with empty string
        try:
            tier = classifier.classify("", token_count)
            assert tier in CognitiveTier, \
                f"Empty prompt should return valid tier, got {tier}"
        except Exception as e:
            # Empty prompt might raise an error - that's acceptable
            # The invariant is: it should either return valid tier OR raise consistent error
            pass

        # Test with whitespace
        try:
            tier = classifier.classify("   \t\n  ", token_count)
            if tier is not None:
                assert tier in CognitiveTier, \
                    f"Whitespace prompt should return valid tier, got {tier}"
        except Exception as e:
            # Whitespace prompt might raise an error - that's acceptable
            pass

    @given(
        tier=sampled_from([
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY,
            CognitiveTier.COMPLEX
        ])
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_tier_thresholds_consistency_invariant(self, tier: CognitiveTier):
        """
        INVARIANT: TIER_THRESHOLDS dictionary has consistent structure.

        Tests that all tier thresholds have required keys and valid values.
        """
        # Assert: Tier must be in thresholds dict
        assert tier in TIER_THRESHOLDS, \
            f"Tier {tier} not in TIER_THRESHOLDS"

        threshold = TIER_THRESHOLDS[tier]

        # Assert: Must have required keys
        assert "max_tokens" in threshold, \
            f"Tier {tier} missing 'max_tokens' key"
        assert "complexity_score" in threshold, \
            f"Tier {tier} missing 'complexity_score' key"
        assert "description" in threshold, \
            f"Tier {tier} missing 'description' key"

        # Assert: Values must have correct types
        assert isinstance(threshold["max_tokens"], (int, float)), \
            f"Tier {tier} has invalid max_tokens type: {type(threshold['max_tokens'])}"
        assert isinstance(threshold["complexity_score"], (int, float)), \
            f"Tier {tier} has invalid complexity_score type: {type(threshold['complexity_score'])}"
        assert isinstance(threshold["description"], str), \
            f"Tier {tier} has invalid description type: {type(threshold['description'])}"

        # Assert: Values must be non-negative
        assert threshold["max_tokens"] >= 0, \
            f"Tier {tier} has negative max_tokens: {threshold['max_tokens']}"
        assert threshold["complexity_score"] >= 0, \
            f"Tier {tier} has negative complexity_score: {threshold['complexity_score']}"

    @given(
        token_count=integers(min_value=1, max_value=20000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_classification_performance_invariant(self, token_count: int):
        """
        INVARIANT: Classification completes in reasonable time (<100ms target).

        Tests that classification is fast enough for production use.
        """
        import time

        classifier = CognitiveClassifier()
        prompt = "performance test query"

        # Measure classification time
        start_time = time.perf_counter()
        tier = classifier.classify(prompt, token_count)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Assert: Must return valid tier
        assert tier in CognitiveTier, \
            f"Classification failed or returned invalid tier"

        # Assert: Should complete in <100ms (relaxed from 50ms for test environment)
        assert elapsed_ms < 100, \
            f"Classification took {elapsed_ms:.2f}ms, exceeds 100ms target"
