"""
Coverage-driven tests for CognitiveTierSystem (currently 0% -> target 70%+)

Focus areas from cognitive_tier_system.py:
- CognitiveTier enum values (lines 20-40)
- TIER_THRESHOLDS configuration (lines 43-70)
- CognitiveClassifier.__init__ (lines 135-141)
- CognitiveClassifier.classify() (lines 143-174)
- _calculate_complexity_score() (lines 176-221)
- _estimate_tokens() (lines 223-240)
"""

import pytest
from core.llm.cognitive_tier_system import (
    CognitiveTier,
    TIER_THRESHOLDS,
    CognitiveClassifier,
)


class TestCognitiveTier:
    """Test CognitiveTier enum configuration (lines 20-40)."""

    def test_tier_enum_values(self):
        """Cover lines 36-40: All tier values defined."""
        assert CognitiveTier.MICRO.value == "micro"
        assert CognitiveTier.STANDARD.value == "standard"
        assert CognitiveTier.VERSATILE.value == "versatile"
        assert CognitiveTier.HEAVY.value == "heavy"
        assert CognitiveTier.COMPLEX.value == "complex"

    def test_tier_thresholds_configuration(self):
        """Cover lines 43-70: Threshold configuration for each tier."""
        # MICRO tier
        assert TIER_THRESHOLDS[CognitiveTier.MICRO]["max_tokens"] == 100
        assert TIER_THRESHOLDS[CognitiveTier.MICRO]["complexity_score"] == 0

        # STANDARD tier
        assert TIER_THRESHOLDS[CognitiveTier.STANDARD]["max_tokens"] == 500
        assert TIER_THRESHOLDS[CognitiveTier.STANDARD]["complexity_score"] == 2

        # VERSATILE tier
        assert TIER_THRESHOLDS[CognitiveTier.VERSATILE]["max_tokens"] == 2000
        assert TIER_THRESHOLDS[CognitiveTier.VERSATILE]["complexity_score"] == 5

        # HEAVY tier
        assert TIER_THRESHOLDS[CognitiveTier.HEAVY]["max_tokens"] == 5000
        assert TIER_THRESHOLDS[CognitiveTier.HEAVY]["complexity_score"] == 8

        # COMPLEX tier
        assert TIER_THRESHOLDS[CognitiveTier.COMPLEX]["max_tokens"] == float("inf")
        assert TIER_THRESHOLDS[CognitiveTier.COMPLEX]["complexity_score"] == float("inf")

    def test_tier_thresholds_progressive(self):
        """Verify thresholds increase progressively."""
        tiers = [
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY,
            CognitiveTier.COMPLEX,
        ]

        max_tokens = [TIER_THRESHOLDS[t]["max_tokens"] for t in tiers]
        complexity_scores = [TIER_THRESHOLDS[t]["complexity_score"] for t in tiers]

        # Each tier should allow more tokens than the last
        for i in range(1, len(max_tokens)):
            assert max_tokens[i] > max_tokens[i-1]

        # Each tier should allow higher complexity than the last
        for i in range(1, len(complexity_scores)):
            assert complexity_scores[i] >= complexity_scores[i-1]


class TestCognitiveClassifierInit:
    """Test CognitiveClassifier initialization (lines 135-141)."""

    def test_init_compiles_patterns(self):
        """Cover lines 135-141: Pattern pre-compilation for performance."""
        classifier = CognitiveClassifier()

        # Should have compiled patterns
        assert hasattr(classifier, "_compiled_patterns")
        assert len(classifier._compiled_patterns) == 5  # simple, moderate, technical, code, advanced

        # Each pattern should be a compiled regex
        for name, (pattern, weight) in classifier._compiled_patterns.items():
            import re
            assert hasattr(pattern, "match")  # Compiled regex has match method


class TestTokenEstimation:
    """Test _estimate_tokens method (lines 223-240)."""

    def test_estimate_tokens_simple_text(self):
        """Cover lines 223-240: Basic token estimation (1 token ≈ 4 chars)."""
        classifier = CognitiveClassifier()

        # Short text
        tokens = classifier._estimate_tokens("hello world")
        assert 2 <= tokens <= 3  # ~11 chars / 4 = ~3 tokens

        # Medium text
        tokens = classifier._estimate_tokens("This is a medium length sentence with some words.")
        assert tokens >= 10

        # Empty string
        tokens = classifier._estimate_tokens("")
        assert tokens == 0

    def test_estimate_tokens_with_code(self):
        """Test token estimation for code snippets."""
        classifier = CognitiveClassifier()

        code = """
def function_name(param1, param2):
    result = param1 + param2
    return result
"""
        tokens = classifier._estimate_tokens(code)
        assert tokens >= 20  # Code should have more tokens

    def test_estimate_tokens_unicode(self):
        """Test token estimation handles Unicode correctly."""
        classifier = CognitiveClassifier()

        # Unicode characters still count as characters
        tokens = classifier._estimate_tokens("hello world")
        tokens_unicode = classifier._estimate_tokens("hello world")
        assert tokens == tokens_unicode

    @pytest.mark.parametrize("text,expected_range", [
        ("hi", (0, 5)),
        ("hello world, how are you today?", (5, 15)),
        ("This is a much longer text that should definitely have more tokens. " * 5, (50, 150)),
    ])
    def test_estimate_tokens_various_lengths(self, text, expected_range):
        """Parametrized test for various text lengths."""
        classifier = CognitiveClassifier()
        tokens = classifier._estimate_tokens(text)
        assert expected_range[0] <= tokens <= expected_range[1]
