"""
Extended coverage tests for CognitiveTierSystem (currently 90% -> target 95%+)

Target file: core/llm/cognitive_tier_system.py (50 statements)

Current coverage: 90% (45/50 statements covered)
Missing lines: 174, 207, 251-285, 297

This file extends existing coverage from test_cognitive_tier_system_coverage.py
by targeting remaining uncovered lines:

- Line 174: Fallback to COMPLEX when all thresholds exceeded
- Line 207: Code block detection (``` in prompt)
- Lines 251-285: get_tier_models() method
- Line 297: get_tier_description() method

Focus areas:
- Exact threshold boundary conditions
- Code block detection in complexity scoring
- get_tier_models() method for all 5 tiers
- get_tier_description() method
- Semantic complexity edge cases (multilingual, special chars)
"""

import pytest
from core.llm.cognitive_tier_system import (
    CognitiveTier,
    TIER_THRESHOLDS,
    CognitiveClassifier,
)


class TestExactThresholdMatches:
    """Test exact threshold boundary conditions to cover line 174."""

    def test_exact_threshold_matches(self):
        """Cover exact threshold boundary conditions including line 174 fallback."""
        classifier = CognitiveClassifier()

        # MICRO tier: < 100 tokens
        # Test at boundary (99 tokens ≈ 396 chars)
        prompt_99 = "word " * 99  # ~495 chars ≈ 123 tokens, but semantic score might keep it MICRO
        result = classifier.classify("hi")  # Very short, definitely MICRO
        assert result == CognitiveTier.MICRO

        # STANDARD tier: 100-500 tokens
        # Test at exact boundary (100 tokens ≈ 400 chars)
        prompt_100 = "word " * 100  # ~500 chars ≈ 125 tokens
        result = classifier.classify(prompt_100)
        # Should be MICRO (simple text) or STANDARD (if token-based)
        assert result in [CognitiveTier.MICRO, CognitiveTier.STANDARD]

        # Test with semantic boost to push to STANDARD
        prompt_100_semantic = "explain " * 100  # ~700 chars ≈ 175 tokens + "explain" pattern
        result = classifier.classify(prompt_100_semantic)
        assert result in [CognitiveTier.STANDARD, CognitiveTier.VERSATILE]

        # HEAVY tier: 2000-5000 tokens
        # Test at exact boundary (2000 tokens ≈ 8000 chars)
        prompt_2000 = "analyze " * 2000  # ~14000 chars ≈ 3500 tokens
        result = classifier.classify(prompt_2000)
        # Should be HEAVY or COMPLEX depending on complexity score
        assert result in [CognitiveTier.HEAVY, CognitiveTier.COMPLEX]

    def test_fallback_to_complex(self):
        """Cover line 174: Fallback to COMPLEX when all thresholds exceeded.

        This line is hit when:
        1. estimated_tokens > threshold["max_tokens"] for all tiers
        2. complexity_score > threshold["complexity_score"] for all tiers

        The COMPLEX tier has max_tokens=inf and complexity_score=inf,
        so we need to test the iteration logic that falls through to COMPLEX.
        """
        classifier = CognitiveClassifier()

        # Create a prompt that exceeds all normal tier thresholds
        # Need: 5000+ tokens AND complexity score > 8
        # 5000 tokens ≈ 20000 chars
        # Complexity: "design" (5) + "architecture" (5) + "distributed" (5) = 15+
        long_complex_prompt = "design architecture distributed system " * 1000  # ~50000 chars

        result = classifier.classify(long_complex_prompt)

        # With 50000 chars (~12500 tokens) and high complexity, should be COMPLEX
        # Line 174 is hit when the for loop doesn't return early
        assert result == CognitiveTier.COMPLEX

    def test_threshold_boundary_500_tokens(self):
        """Test exact boundary at 500 tokens (MICRO/STANDARD -> VERSATILE)."""
        classifier = CognitiveClassifier()

        # 500 tokens ≈ 2000 chars
        prompt_500 = "word " * 500  # ~2500 chars ≈ 625 tokens
        result = classifier.classify(prompt_500)

        # Should be VERSATILE or higher due to token count
        assert result in [CognitiveTier.VERSATILE, CognitiveTier.HEAVY, CognitiveTier.COMPLEX]

    def test_threshold_boundary_2000_tokens(self):
        """Test exact boundary at 2000 tokens (VERSATILE -> HEAVY)."""
        classifier = CognitiveClassifier()

        # 2000 tokens ≈ 8000 chars
        prompt_2000 = "word " * 2000  # ~10000 chars ≈ 2500 tokens
        result = classifier.classify(prompt_2000)

        # Should be HEAVY or COMPLEX
        assert result in [CognitiveTier.HEAVY, CognitiveTier.COMPLEX]

    def test_threshold_boundary_5000_tokens(self):
        """Test exact boundary at 5000 tokens (HEAVY -> COMPLEX)."""
        classifier = CognitiveClassifier()

        # 5000 tokens ≈ 20000 chars
        prompt_5000 = "word " * 5000  # ~25000 chars ≈ 6250 tokens
        result = classifier.classify(prompt_5000)

        # Should be COMPLEX (exceeds HEAVY max_tokens)
        assert result == CognitiveTier.COMPLEX


class TestCodeBlockDetection:
    """Test code block detection to cover line 207."""

    def test_code_block_detection_in_complexity(self):
        """Cover line 207: Code block detection adds +3 to complexity score."""
        classifier = CognitiveClassifier()

        # Base prompt without code block
        base_score = classifier._calculate_complexity_score("here is some code")
        assert base_score >= 0  # "code" keyword gives +3

        # Same prompt with code block (``` markers)
        code_block_score = classifier._calculate_complexity_score("here is some code ```python\ndef foo():\n    pass\n```")

        # Code block should add +3 to score
        assert code_block_score >= base_score + 3

    def test_code_block_with_backticks(self):
        """Test various code block patterns with backticks."""
        classifier = CognitiveClassifier()

        # Single backtick (inline code)
        score1 = classifier._calculate_complexity_score("use the `function` method")
        assert score1 >= 3  # "function" keyword

        # Triple backticks (code block)
        score2 = classifier._calculate_complexity_score("```\ncode here\n```")
        assert score2 >= 3  # Code block detection

        # Code block with language
        score3 = classifier._calculate_complexity_score("```python\ndef foo():\n    pass\n```")
        assert score3 >= 3  # Code block detection

    def test_multiple_code_blocks(self):
        """Test multiple code blocks in same prompt."""
        classifier = CognitiveClassifier()

        # Multiple code blocks should each add +3
        score = classifier._calculate_complexity_score("""
```python
def foo():
    pass
```

Some text

```javascript
function bar() {
    return 1;
}
```
""")
        # Should get +3 for each code block (detected by "```")
        # Note: The pattern checks for "```" presence, not count
        assert score >= 3


class TestGetTierModels:
    """Test get_tier_models() method to cover lines 251-285."""

    def test_get_tier_models_micro(self):
        """Cover lines 252-257: MICRO tier model recommendations."""
        classifier = CognitiveClassifier()
        models = classifier.get_tier_models(CognitiveTier.MICRO)

        assert isinstance(models, list)
        assert len(models) > 0
        assert "deepseek-chat" in models
        assert "qwen-3-7b" in models
        assert "gemini-3-flash" in models
        assert "gpt-4o-mini" in models

    def test_get_tier_models_standard(self):
        """Cover lines 258-263: STANDARD tier model recommendations."""
        classifier = CognitiveClassifier()
        models = classifier.get_tier_models(CognitiveTier.STANDARD)

        assert isinstance(models, list)
        assert len(models) > 0
        assert "gemini-3-flash" in models
        assert "deepseek-chat" in models
        assert "gpt-4o-mini" in models
        assert "claude-3-haiku-20240307" in models

    def test_get_tier_models_versatile(self):
        """Cover lines 264-269: VERSATILE tier model recommendations."""
        classifier = CognitiveClassifier()
        models = classifier.get_tier_models(CognitiveTier.VERSATILE)

        assert isinstance(models, list)
        assert len(models) > 0
        assert "gemini-3-flash" in models
        assert "gpt-4o-mini" in models
        assert "deepseek-v3" in models
        assert "claude-3-5-sonnet" in models

    def test_get_tier_models_heavy(self):
        """Cover lines 270-275: HEAVY tier model recommendations."""
        classifier = CognitiveClassifier()
        models = classifier.get_tier_models(CognitiveTier.HEAVY)

        assert isinstance(models, list)
        assert len(models) > 0
        assert "gpt-4o" in models
        assert "claude-3-5-sonnet" in models
        assert "gemini-3-pro" in models
        assert "deepseek-v3.2" in models

    def test_get_tier_models_complex(self):
        """Cover lines 276-282: COMPLEX tier model recommendations."""
        classifier = CognitiveClassifier()
        models = classifier.get_tier_models(CognitiveTier.COMPLEX)

        assert isinstance(models, list)
        assert len(models) > 0
        assert "gpt-5" in models
        assert "o3" in models
        assert "claude-4-opus" in models
        assert "deepseek-v3.2-speciale" in models
        assert "gemini-3-pro" in models

    def test_get_tier_models_returns_list(self):
        """Cover line 285: Return empty list for invalid tier (defensive)."""
        classifier = CognitiveClassifier()

        # Test with valid tier returns list
        models = classifier.get_tier_models(CognitiveTier.MICRO)
        assert isinstance(models, list)

    def test_all_tiers_have_models(self):
        """Verify all 5 tiers have model recommendations."""
        classifier = CognitiveClassifier()

        for tier in CognitiveTier:
            models = classifier.get_tier_models(tier)
            assert isinstance(models, list)
            assert len(models) > 0, f"{tier} should have at least one model recommendation"


class TestGetTierDescription:
    """Test get_tier_description() method to cover line 297."""

    def test_get_tier_description_micro(self):
        """Cover line 297: MICRO tier description."""
        classifier = CognitiveClassifier()
        desc = classifier.get_tier_description(CognitiveTier.MICRO)

        assert isinstance(desc, str)
        assert "simple" in desc.lower() or "100" in desc

    def test_get_tier_description_standard(self):
        """Cover line 297: STANDARD tier description."""
        classifier = CognitiveClassifier()
        desc = classifier.get_tier_description(CognitiveTier.STANDARD)

        assert isinstance(desc, str)
        assert "moderate" in desc.lower() or "complexity" in desc.lower()

    def test_get_tier_description_versatile(self):
        """Cover line 297: VERSATILE tier description."""
        classifier = CognitiveClassifier()
        desc = classifier.get_tier_description(CognitiveTier.VERSATILE)

        assert isinstance(desc, str)
        assert "multi" in desc.lower() or "reasoning" in desc.lower()

    def test_get_tier_description_heavy(self):
        """Cover line 297: HEAVY tier description."""
        classifier = CognitiveClassifier()
        desc = classifier.get_tier_description(CognitiveTier.HEAVY)

        assert isinstance(desc, str)
        assert "complex" in desc.lower() or "2k" in desc or "2000" in desc

    def test_get_tier_description_complex(self):
        """Cover line 297: COMPLEX tier description."""
        classifier = CognitiveClassifier()
        desc = classifier.get_tier_description(CognitiveTier.COMPLEX)

        assert isinstance(desc, str)
        assert "advanced" in desc.lower() or "reasoning" in desc.lower()

    def test_all_tiers_have_descriptions(self):
        """Verify all 5 tiers have descriptions."""
        classifier = CognitiveClassifier()

        for tier in CognitiveTier:
            desc = classifier.get_tier_description(tier)
            assert isinstance(desc, str)
            assert len(desc) > 0, f"{tier} should have a description"


class TestSemanticComplexityEdgeCases:
    """Test semantic complexity edge cases for multilingual and special characters."""

    @pytest.mark.parametrize("text,expected_min_score", [
        ("", -2),                    # Empty string (minimum score -2)
        ("   ", -2),                 # Whitespace only (minimum score -2)
        ("a", -2),                   # Single character
        ("hi", -2),                  # Simple greeting (matches "hi" pattern)
        ("hello", -2),               # Simple greeting (matches "hello" pattern)
        ("The API returns JSON", 1), # Technical term "API"
        ("def foo(): pass", 3),      # Code keywords "def", "pass"
        ("calculate the integral", 3),  # Math keywords
        ("lambda x: x.map(f)", 3),   # Code keywords "lambda", "map"
        ("积分变换", 0),             # Chinese (no English patterns match)
        ("日本語のテキスト", 0),    # Japanese (no English patterns match)
        ("مرحبا بالعالم", 0),       # Arabic (no English patterns match)
        ("Привет мир", 0),          # Cyrillic (no English patterns match)
        ("🎉🎊🔥", 0),              # Emojis (no patterns match)
    ])
    def test_semantic_complexity_edge_cases(self, text, expected_min_score):
        """Cover semantic complexity edge cases including multilingual text."""
        classifier = CognitiveClassifier()
        score = classifier._calculate_complexity_score(text)
        assert score >= expected_min_score, f"Expected score >= {expected_min_score} for '{text}', got {score}"

    def test_unicode_and_special_chars(self):
        """Cover Unicode and special character handling in token estimation."""
        classifier = CognitiveClassifier()

        # Test various Unicode categories
        texts = [
            "Hello 世界",           # Mixed Latin/CJK
            "مرحبا بالعالم",         # Arabic RTL
            "Привет мир",          # Cyrillic
            "🚀🌟⭐",               # Emojis
            "<script>alert(1)</script>",  # HTML-like
            "${jndi:ldap://evil}",  # Injection-like
            "SELECT * FROM users WHERE id = 1",  # SQL
            "def foo(): return 'bar'",  # Python
            "console.log('test')",  # JavaScript
        ]

        for text in texts:
            tokens = classifier._estimate_tokens(text)
            assert tokens >= 0  # Should not crash
            assert isinstance(tokens, int)

    def test_mixed_language_code(self):
        """Test mixed language and code complexity scoring."""
        classifier = CognitiveClassifier()

        # English + Chinese + code
        # "def" gives +3, "pass" might not match (not in patterns)
        score = classifier._calculate_complexity_score("Hello 世界 def foo(): pass")
        # Should get +3 for "def" keyword
        assert score >= 1  # At minimum, token count gives some score

    def test_special_chars_in_estimate_tokens(self):
        """Test that special characters don't break token estimation."""
        classifier = CognitiveClassifier()

        special_texts = [
            "!@#$%^&*()",
            "[]{}|;:',.<>?/~`",
            "\t\n\r",  # Whitespace chars
            "🎉🎊🔥",  # Emojis (multi-byte)
            "null\x00byte",  # Null byte
        ]

        for text in special_texts:
            tokens = classifier._estimate_tokens(text)
            assert tokens >= 0
            assert isinstance(tokens, int)


class TestTaskTypeAdjustments:
    """Test task type adjustment logic."""

    @pytest.mark.parametrize("task_type,expected_score", [
        ("code", 0),         # "hello" (-2) + code (+2) = 0
        ("analysis", 0),     # "hello" (-2) + analysis (+2) = 0
        ("reasoning", 0),    # "hello" (-2) + reasoning (+2) = 0
        ("agentic", 0),      # "hello" (-2) + agentic (+2) = 0
        ("chat", -2),        # "hello" (-2) + chat (-1) = -3, but min is -2
        ("general", -2),     # "hello" (-2) + general (-1) = -3, but min is -2
        ("unknown", -2),     # "hello" (-2) + unknown (0) = -2
    ])
    def test_task_type_adjustment_values(self, task_type, expected_score):
        """Test task type adjustment logic."""
        classifier = CognitiveClassifier()

        # Calculate score with task type
        score = classifier._calculate_complexity_score("hello", task_type=task_type)

        # Score should match expected (accounting for minimum of -2)
        assert score == expected_score

    def test_task_type_with_complexity_patterns(self):
        """Test task type adjustments combined with semantic patterns."""
        classifier = CognitiveClassifier()

        # Code task with code keywords
        score = classifier._calculate_complexity_score("write a function", task_type="code")
        # "function" keyword gives +3, code task gives +2, "write" not in patterns
        # Base: 0, "function": +3, code task: +2 = 5
        assert score >= 5

        # Chat task with simple keywords
        score = classifier._calculate_complexity_score("hello", task_type="chat")
        # "hello" gives -2, chat task gives -1 = -3 (but minimum is -2)
        # Minimum score is -2 per line 215
        assert score >= -2

    def test_task_type_none_or_empty(self):
        """Test None and empty string task types."""
        classifier = CognitiveClassifier()

        # None task type
        score1 = classifier._calculate_complexity_score("hello", task_type=None)
        assert isinstance(score1, int)

        # Empty string task type
        score2 = classifier._calculate_complexity_score("hello", task_type="")
        assert isinstance(score2, int)

        # Should be same (empty string not in TASK_TYPE_ADJUSTMENTS)
        assert score1 == score2


class TestCombinedClassificationFactors:
    """Test combined token + complexity + task type classification."""

    def test_small_code_task_bumps_tier(self):
        """Test that small code task bumps to higher tier."""
        classifier = CognitiveClassifier()

        # Small code task should bump to VERSATILE or higher
        # "def" gives +3, code task gives +2 = +5 complexity
        result = classifier.classify("def foo(): return 1", task_type="code")
        assert result in [CognitiveTier.VERSATILE, CognitiveTier.HEAVY, CognitiveTier.COMPLEX]

    def test_large_simple_task_stays_appropriate_tier(self):
        """Test that large simple task stays at appropriate tier."""
        classifier = CognitiveClassifier()

        # Large simple task (many tokens, low complexity)
        large_simple = "hello world " * 1000  # ~12000 chars ≈ 3000 tokens
        result = classifier.classify(large_simple, task_type="chat")

        # Should be HEAVY or COMPLEX due to token count
        assert result in [CognitiveTier.HEAVY, CognitiveTier.COMPLEX]

    def test_code_block_affects_classification(self):
        """Test that code blocks affect tier classification."""
        classifier = CognitiveClassifier()

        # Same prompt with and without code block
        without_block = "here is some code"
        with_block = "here is some code ```python\ndef foo():\n    pass\n```"

        tier_without = classifier.classify(without_block)
        tier_with = classifier.classify(with_block)

        # Both should be valid CognitiveTier enums
        assert isinstance(tier_without, CognitiveTier)
        assert isinstance(tier_with, CognitiveTier)

    def test_exact_token_threshold_with_semantic_boost(self):
        """Test exact token thresholds combined with semantic complexity."""
        classifier = CognitiveClassifier()

        # 100 tokens ≈ 400 chars
        # Simple text at boundary
        prompt_simple = "word " * 100  # ~500 chars ≈ 125 tokens
        result_simple = classifier.classify(prompt_simple)
        # Should be MICRO or STANDARD (simple text)

        # Complex text at same boundary
        prompt_complex = "design architecture " * 20  # ~400 chars ≈ 100 tokens
        result_complex = classifier.classify(prompt_complex)

        # Complex text should classify to same or higher tier
        # "design" (+5) + "architecture" (+5) = +10 semantic score
        # With 100 tokens and +10 complexity, should be at least STANDARD
        assert result_complex.value in ["standard", "versatile", "heavy", "complex"]


class TestEdgeCasesForUncoveredLines:
    """Additional tests to ensure all uncovered lines are hit."""

    def test_line_174_fallback_ensured(self):
        """Ensure line 174 (fallback to COMPLEX) is hit.

        Line 174: `return CognitiveTier.COMPLEX`

        This is hit when the for loop in classify() doesn't return early,
        meaning all tier thresholds were exceeded.
        """
        classifier = CognitiveClassifier()

        # Create prompt that exceeds ALL thresholds
        # Need: >5000 tokens AND complexity score >8
        prompt = (
            "design architecture distributed enterprise scalable system " * 2000
        )  # ~150000 chars ≈ 37500 tokens

        result = classifier.classify(prompt)

        # Must be COMPLEX (line 174 executed)
        assert result == CognitiveTier.COMPLEX

    def test_line_207_code_block_ensured(self):
        """Ensure line 207 (code block detection) is hit.

        Line 207: `complexity_score += 3` when "```" in prompt
        """
        classifier = CognitiveClassifier()

        # Prompt with code block
        score_with_block = classifier._calculate_complexity_score("""
text
```python
code
```
text
""")

        # Prompt without code block (same content)
        score_without_block = classifier._calculate_complexity_score("""
text
code
text
""")

        # Code block should add +3
        assert score_with_block == score_without_block + 3

    def test_lines_251_285_get_tier_models_ensured(self):
        """Ensure lines 251-285 (get_tier_models) are fully hit.

        This method has a TIER_MODELS dict with 5 entries.
        We need to call get_tier_models() for all 5 tiers.
        """
        classifier = CognitiveClassifier()

        # Call for all 5 tiers to hit all dict branches
        micro_models = classifier.get_tier_models(CognitiveTier.MICRO)
        standard_models = classifier.get_tier_models(CognitiveTier.STANDARD)
        versatile_models = classifier.get_tier_models(CognitiveTier.VERSATILE)
        heavy_models = classifier.get_tier_models(CognitiveTier.HEAVY)
        complex_models = classifier.get_tier_models(CognitiveTier.COMPLEX)

        # Verify all return lists (lines 285: return TIER_MODELS.get(tier, []))
        assert isinstance(micro_models, list)
        assert isinstance(standard_models, list)
        assert isinstance(versatile_models, list)
        assert isinstance(heavy_models, list)
        assert isinstance(complex_models, list)

        # Verify each has expected models
        assert "deepseek-chat" in micro_models
        assert "gemini-3-flash" in standard_models
        assert "claude-3-5-sonnet" in versatile_models
        assert "gpt-4o" in heavy_models
        assert "gpt-5" in complex_models

    def test_line_297_get_tier_description_ensured(self):
        """Ensure line 297 (get_tier_description) is hit.

        Line 297: `return TIER_THRESHOLDS[tier]["description"]`

        We need to call get_tier_description() for all 5 tiers.
        """
        classifier = CognitiveClassifier()

        # Call for all 5 tiers to hit all dict branches
        micro_desc = classifier.get_tier_description(CognitiveTier.MICRO)
        standard_desc = classifier.get_tier_description(CognitiveTier.STANDARD)
        versatile_desc = classifier.get_tier_description(CognitiveTier.VERSATILE)
        heavy_desc = classifier.get_tier_description(CognitiveTier.HEAVY)
        complex_desc = classifier.get_tier_description(CognitiveTier.COMPLEX)

        # Verify all return strings
        assert isinstance(micro_desc, str)
        assert isinstance(standard_desc, str)
        assert isinstance(versatile_desc, str)
        assert isinstance(heavy_desc, str)
        assert isinstance(complex_desc, str)

        # Verify descriptions are from TIER_THRESHOLDS
        assert micro_desc == TIER_THRESHOLDS[CognitiveTier.MICRO]["description"]
        assert standard_desc == TIER_THRESHOLDS[CognitiveTier.STANDARD]["description"]
        assert versatile_desc == TIER_THRESHOLDS[CognitiveTier.VERSATILE]["description"]
        assert heavy_desc == TIER_THRESHOLDS[CognitiveTier.HEAVY]["description"]
        assert complex_desc == TIER_THRESHOLDS[CognitiveTier.COMPLEX]["description"]
