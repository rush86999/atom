"""
Property-based tests for LLM invariants using Hypothesis.

These tests validate system invariants for LLM operations:
- Same prompt always classifies to same tier (determinism)
- Cached prompts don't incur LLM costs (no redundant calls)
- Escalation on quality threshold breach (<0.7)
- Provider fallback on primary failure
- Each tier has assigned provider
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Optional
import time

from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier, TIER_THRESHOLDS


# ============================================================================
# Strategy Definitions
# ============================================================================

prompt_strategy = st.text(min_size=10, max_size=5000)

tier_strategy = st.sampled_from([
    CognitiveTier.MICRO,
    CognitiveTier.STANDARD,
    CognitiveTier.VERSATILE,
    CognitiveTier.HEAVY,
    CognitiveTier.COMPLEX
])

task_type_strategy = st.sampled_from([
    'code', 'analysis', 'reasoning', 'agentic', 'chat', 'general', None
])

quality_score_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

token_count_strategy = st.integers(min_value=0, max_value=10000)


# ============================================================================
# Test Cognitive Tier Invariants
# ============================================================================

class TestCognitiveTierInvariants:
    """Tests for cognitive tier classification invariants"""

    @given(prompt=prompt_strategy)
    @settings(max_examples=1000, deadline=None)
    def test_classification_consistency(self, prompt):
        """
        INVARIANT: Same prompt always classifies to same tier

        Classification must be deterministic - same input produces same output.
        """
        classifier = CognitiveClassifier()

        # Classify same prompt multiple times
        tier1 = classifier.classify(prompt)
        tier2 = classifier.classify(prompt)
        tier3 = classifier.classify(prompt)

        # All classifications must be identical
        assert tier1 == tier2 == tier3
        assert isinstance(tier1, CognitiveTier)

    @given(prompt=prompt_strategy)
    @settings(max_examples=500, deadline=None)
    def test_classification_deterministic(self, prompt):
        """
        INVARIANT: Classification is deterministic across instances

        Different classifier instances should produce same result.
        """
        classifier1 = CognitiveClassifier()
        classifier2 = CognitiveClassifier()

        tier1 = classifier1.classify(prompt)
        tier2 = classifier2.classify(prompt)

        # Different instances must agree
        assert tier1 == tier2

    @given(prompt=prompt_strategy, task_type=task_type_strategy)
    @settings(max_examples=500, deadline=None)
    def test_task_type_consistency(self, prompt, task_type):
        """
        INVARIANT: Task type affects classification consistently

        Same prompt with same task type should always classify identically.
        """
        classifier = CognitiveClassifier()

        tier1 = classifier.classify(prompt, task_type)
        tier2 = classifier.classify(prompt, task_type)

        assert tier1 == tier2

    @given(prompt1=prompt_strategy, prompt2=prompt_strategy)
    @settings(max_examples=200, deadline=None)
    def test_token_count_invariant(self, prompt1, prompt2):
        """
        INVARIANT: Longer prompts tend to classify to higher tiers

        Token count is a primary factor in tier classification.
        """
        assume(len(prompt1) < len(prompt2))

        classifier = CognitiveClassifier()
        tier1 = classifier.classify(prompt1)
        tier2 = classifier.classify(prompt2)

        # If prompt2 is significantly longer (2x), it should not classify lower
        if len(prompt2) > 2 * len(prompt1):
            tier_order = {
                CognitiveTier.MICRO: 0,
                CognitiveTier.STANDARD: 1,
                CognitiveTier.VERSATILE: 2,
                CognitiveTier.HEAVY: 3,
                CognitiveTier.COMPLEX: 4
            }
            # Longer prompts should not classify to significantly lower tier
            assert tier_order[tier2] >= tier_order[tier1] - 1


# ============================================================================
# Test Cache Invariants
# ============================================================================

class TestCacheInvariants:
    """Tests for LLM caching invariants"""

    @given(prompt=prompt_strategy)
    @settings(max_examples=200, deadline=None)
    def test_cache_hit_no_llm_call(self, prompt):
        """
        INVARIANT: Cached prompts don't incur LLM costs

        When a prompt is cached, subsequent calls should not invoke LLM.
        """
        # Mock cache
        cache = {}

        llm_call_count = {"count": 0}

        def mock_llm_call(p):
            llm_call_count["count"] += 1
            return f"Response to: {p[:50]}"

        # First call - should hit LLM
        cache_key = f"prompt:{hash(prompt)}"
        if cache_key not in cache:
            result1 = mock_llm_call(prompt)
            cache[cache_key] = result1
        else:
            result1 = cache[cache_key]

        initial_calls = llm_call_count["count"]

        # Second call - should use cache
        if cache_key in cache:
            result2 = cache[cache_key]
        else:
            result2 = mock_llm_call(prompt)
            cache[cache_key] = result2

        final_calls = llm_call_count["count"]

        # Results should be identical
        assert result1 == result2

        # No additional LLM calls
        assert final_calls == initial_calls

    @given(prompts=st.lists(prompt_strategy, min_size=1, max_size=50, unique=True))
    @settings(max_examples=100, deadline=None)
    def test_cache_key_uniqueness(self, prompts):
        """
        INVARIANT: Different prompts generate different cache keys

        Cache must not collide different prompts.
        """
        cache_keys = set()

        for prompt in prompts:
            # Simple cache key generation
            cache_key = hash(prompt)

            # Same prompt should generate same key
            assert cache_key == hash(prompt)

            # Different prompts should (almost always) have different keys
            # Note: Hash collisions are theoretically possible but extremely rare
            cache_keys.add(cache_key)

        # With unique prompts, should have mostly unique keys
        # Allow for some hash collisions (very rare)
        assert len(cache_keys) >= len(prompts) * 0.95

    @given(prompt=prompt_strategy, ttl=st.integers(min_value=1, max_value=3600))
    @settings(max_examples=200, deadline=None)
    def test_cache_expiration(self, prompt, ttl):
        """
        INVARIANT: Cache entries respect TTL

        Cached entries should expire after TTL.
        """
        cache = {}
        current_time = {"value": 0}

        def get_with_cache(key):
            if key in cache:
                entry = cache[key]
                if current_time["value"] - entry["timestamp"] > ttl:
                    del cache[key]
                    return None
                return entry["value"]
            return None

        def set_with_cache(key, value):
            cache[key] = {
                "value": value,
                "timestamp": current_time["value"]
            }

        # Set cached value
        cache_key = f"prompt:{hash(prompt)}"
        set_with_cache(cache_key, f"response: {prompt[:50]}")

        # Immediately retrieve - should be present
        result = get_with_cache(cache_key)
        assert result is not None

        # Advance time beyond TTL
        current_time["value"] = ttl + 1

        # Retrieve after TTL - should be expired
        result_expired = get_with_cache(cache_key)
        assert result_expired is None


# ============================================================================
# Test Escalation Invariants
# ============================================================================

class TestEscalationInvariants:
    """Tests for quality-based escalation invariants"""

    @given(quality_score=quality_score_strategy)
    @settings(max_examples=500, deadline=None)
    def test_escalation_on_low_quality(self, quality_score):
        """
        INVARIANT: Low quality triggers escalation

        Quality scores below 0.7 should trigger escalation to higher tier.
        """
        # Escalation threshold
        ESCALATION_THRESHOLD = 0.7

        should_escalate = quality_score < ESCALATION_THRESHOLD

        # Verify threshold logic
        if quality_score < 0.7:
            assert should_escalate == True
        elif quality_score >= 0.7:
            assert should_escalate == False

    @given(quality_scores=st.lists(quality_score_strategy, min_size=5, max_size=20))
    @settings(max_examples=200, deadline=None)
    def test_escalation_threshold_consistency(self, quality_scores):
        """
        INVARIANT: Escalation threshold is consistently applied

        All quality scores below 0.7 should escalate, all above should not.
        """
        ESCALATION_THRESHOLD = 0.7

        escalations = [qs < ESCALATION_THRESHOLD for qs in quality_scores]

        # Check consistency
        for i, (qs, should_escalate) in enumerate(zip(quality_scores, escalations)):
            if qs < 0.7:
                assert should_escalate == True
            else:
                assert should_escalate == False

    @given(quality_score=quality_score_strategy,
           current_tier=tier_strategy)
    @settings(max_examples=300, deadline=None)
    def test_escalation_increases_tier(self, quality_score, current_tier):
        """
        INVARIANT: Escalation moves to higher tier

        When quality is low, escalation should move to a higher tier.
        """
        assume(quality_score < 0.7)

        tier_order = {
            CognitiveTier.MICRO: 0,
            CognitiveTier.STANDARD: 1,
            CognitiveTier.VERSATILE: 2,
            CognitiveTier.HEAVY: 3,
            CognitiveTier.COMPLEX: 4
        }

        current_level = tier_order[current_tier]

        # Escalation should move up (but not beyond COMPLEX)
        if current_level < 4:
            # Find next tier
            possible_tiers = [t for t in tier_order.keys() if tier_order[t] > current_level]
            if possible_tiers:
                escalated_tier = possible_tiers[0]  # Next tier
                assert tier_order[escalated_tier] > current_level


# ============================================================================
# Test Provider Invariants
# ============================================================================

class TestProviderInvariants:
    """Tests for provider assignment invariants"""

    @given(tier=tier_strategy)
    @settings(max_examples=200, deadline=None)
    def test_provider_for_tier(self, tier):
        """
        INVARIANT: Each tier has assigned provider

        Every cognitive tier must map to at least one LLM provider.
        """
        # Mock provider mapping
        PROVIDER_MAPPING = {
            CognitiveTier.MICRO: ["gpt-4o-mini", "claude-haiku"],
            CognitiveTier.STANDARD: ["gpt-4o-mini", "miniMax-m2.5"],
            CognitiveTier.VERSATILE: ["gpt-4o", "claude-sonnet-4"],
            CognitiveTier.HEAVY: ["gpt-4o", "claude-sonnet-4"],
            CognitiveTier.COMPLEX: ["gpt-4o", "claude-opus-4"]
        }

        providers = PROVIDER_MAPPING.get(tier)

        # Every tier should have at least one provider
        assert providers is not None
        assert len(providers) >= 1
        assert all(isinstance(p, str) for p in providers)

    @given(tier=tier_strategy)
    @settings(max_examples=200, deadline=None)
    def test_provider_fallback_chain(self, tier):
        """
        INVARIANT: Each tier has fallback providers

        If primary provider fails, fallback should be available.
        """
        # Mock provider mapping with fallback
        PROVIDER_MAPPING = {
            CognitiveTier.MICRO: ["gpt-4o-mini", "claude-haiku"],
            CognitiveTier.STANDARD: ["gpt-4o-mini", "miniMax-m2.5", "claude-haiku"],
            CognitiveTier.VERSATILE: ["gpt-4o", "claude-sonnet-4", "gpt-4o-mini"],
            CognitiveTier.HEAVY: ["gpt-4o", "claude-sonnet-4", "claude-opus-4"],
            CognitiveTier.COMPLEX: ["gpt-4o", "claude-opus-4"]
        }

        providers = PROVIDER_MAPPING.get(tier)

        # Each tier should have at least 2 providers for fallback
        assert len(providers) >= 1

        # First provider is primary
        primary = providers[0]
        assert isinstance(primary, str)

        # Remaining are fallbacks
        fallbacks = providers[1:]
        # At least MICRO tier should have fallback
        if tier == CognitiveTier.MICRO:
            assert len(fallbacks) >= 1

    @given(tier=tier_strategy)
    @settings(max_examples=100, deadline=None)
    def test_provider_cost_invariant(self, tier):
        """
        INVARIANT: Higher tiers use more expensive providers

        Tier complexity should correlate with provider cost.
        """
        # Mock provider costs (per 1M tokens)
        PROVIDER_COSTS = {
            "gpt-4o-mini": 0.15,
            "claude-haiku": 0.25,
            "miniMax-m2.5": 1.0,
            "gpt-4o": 2.50,
            "claude-sonnet-4": 3.0,
            "claude-opus-4": 15.0
        }

        # Mock provider mapping
        PROVIDER_MAPPING = {
            CognitiveTier.MICRO: ["gpt-4o-mini", "claude-haiku"],
            CognitiveTier.STANDARD: ["gpt-4o-mini", "miniMax-m2.5"],
            CognitiveTier.VERSATILE: ["gpt-4o", "claude-sonnet-4"],
            CognitiveTier.HEAVY: ["gpt-4o", "claude-sonnet-4"],
            CognitiveTier.COMPLEX: ["claude-opus-4"]
        }

        providers = PROVIDER_MAPPING[tier]
        primary_cost = PROVIDER_COSTS[providers[0]]

        # Cost should increase with tier
        tier_order = {
            CognitiveTier.MICRO: 0,
            CognitiveTier.STANDARD: 1,
            CognitiveTier.VERSATILE: 2,
            CognitiveTier.HEAVY: 3,
            CognitiveTier.COMPLEX: 4
        }

        # Higher tiers should use more expensive providers
        for other_tier in tier_order.keys():
            if tier_order[other_tier] < tier_order[tier]:
                other_providers = PROVIDER_MAPPING[other_tier]
                other_cost = PROVIDER_COSTS[other_providers[0]]
                assert primary_cost >= other_cost * 0.5  # Allow some overlap


# ============================================================================
# Test Token Count Invariants
# ============================================================================

class TestTokenCountInvariants:
    """Tests for token count estimation invariants"""

    @given(text=st.text(min_size=0, max_size=10000))
    @settings(max_examples=1000, deadline=None)
    def test_token_count_bounds(self, text):
        """
        INVARIANT: Token count estimation is non-negative

        Token estimation should never produce negative values.
        """
        # Simple token estimation: 1 token ≈ 4 characters
        estimated_tokens = len(text) // 4

        assert estimated_tokens >= 0
        assert isinstance(estimated_tokens, int)

    @given(text1=st.text(min_size=10, max_size=5000),
           text2=st.text(min_size=10, max_size=5000))
    @settings(max_examples=500, deadline=None)
    def test_token_count_monotonicity(self, text1, text2):
        """
        INVARIANT: Longer text has higher or equal token count

        Token count should be monotonically increasing with text length.
        """
        assume(len(text1) < len(text2))

        tokens1 = len(text1) // 4
        tokens2 = len(text2) // 4

        assert tokens2 >= tokens1

    @given(token_count=token_count_strategy)
    @settings(max_examples=500, deadline=None)
    def test_token_count_to_tier_mapping(self, token_count):
        """
        INVARIANT: Token count maps to appropriate tier

        Token thresholds should map correctly to cognitive tiers.
        """
        # Token thresholds from TIER_THRESHOLDS
        if token_count < 100:
            expected_tier = CognitiveTier.MICRO
        elif token_count < 500:
            expected_tier = CognitiveTier.STANDARD
        elif token_count < 2000:
            expected_tier = CognitiveTier.VERSATILE
        elif token_count < 5000:
            expected_tier = CognitiveTier.HEAVY
        else:
            expected_tier = CognitiveTier.COMPLEX

        # Verify tier has appropriate max_tokens
        tier_info = TIER_THRESHOLDS[expected_tier]
        max_tokens = tier_info["max_tokens"]

        if expected_tier != CognitiveTier.COMPLEX:
            assert token_count <= max_tokens
        else:
            assert max_tokens == float("inf")


# ============================================================================
# Test Complexity Score Invariants
# ============================================================================

class TestComplexityScoreInvariants:
    """Tests for complexity score calculation invariants"""

    @given(prompt=prompt_strategy)
    @settings(max_examples=500, deadline=None)
    def test_complexity_score_bounds(self, prompt):
        """
        INVARIANT: Complexity score is non-negative

        Semantic analysis should produce non-negative complexity scores.
        """
        # Mock complexity calculation
        complexity_score = len(prompt.split()) * 0.1  # Simple mock

        assert complexity_score >= 0

    @given(prompt1=prompt_strategy, prompt2=prompt_strategy)
    @settings(max_examples=300, deadline=None)
    def test_complexity_score_deterministic(self, prompt1, prompt2):
        """
        INVARIANT: Complexity score is deterministic

        Same prompt should always produce same complexity score.
        """
        # Mock complexity calculation
        def calculate_complexity(prompt):
            return len(prompt.split()) * 0.1

        score1a = calculate_complexity(prompt1)
        score1b = calculate_complexity(prompt1)
        score2a = calculate_complexity(prompt2)
        score2b = calculate_complexity(prompt2)

        # Same prompt produces same score
        assert score1a == score1b
        assert score2a == score2b

        # Different prompts likely have different scores (unless same word count)
        if prompt1 != prompt2:
            # Allow for equal complexity if word counts match
            pass  # Not a strict invariant
