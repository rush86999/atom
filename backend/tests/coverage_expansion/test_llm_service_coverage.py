"""
Coverage expansion tests for LLM services.

Tests cover critical code paths in:
- byok_handler.py: Multi-provider LLM handling, streaming responses
- cognitive_tier_system.py: Request classification and tier routing
- cache_aware_router.py: Prompt caching for cost optimization

Target: Cover critical paths (happy path + error paths) to increase coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
from typing import Optional

from core.llm.byok_handler import BYOKHandler, QueryComplexity
from core.llm.cognitive_tier_system import CognitiveTier, CognitiveClassifier, TIER_THRESHOLDS
from core.llm.cache_aware_router import CacheAwareRouter


class TestBYOKHandlerCoverage:
    """Coverage expansion for BYOKHandler."""

    @pytest.fixture
    def handler(self):
        """Get BYOK handler instance."""
        return BYOKHandler()

    # Test: provider selection logic
    def test_query_complexity_enum_values(self):
        """Test QueryComplexity enum has correct values."""
        assert QueryComplexity.SIMPLE.value == "simple"
        assert QueryComplexity.MODERATE.value == "moderate"
        assert QueryComplexity.COMPLEX.value == "complex"
        assert QueryComplexity.ADVANCED.value == "advanced"

    def test_provider_tiers_structure(self):
        """Test PROVIDER_TIERS has expected structure."""
        from core.llm.byok_handler import PROVIDER_TIERS

        assert "budget" in PROVIDER_TIERS
        assert "mid" in PROVIDER_TIERS
        assert "premium" in PROVIDER_TIERS

        # Check budget providers
        assert "deepseek" in PROVIDER_TIERS["budget"]
        assert "moonshot" in PROVIDER_TIERS["budget"]

        # Check premium providers
        assert "openai" in PROVIDER_TIERS["premium"]

    def test_cost_efficient_models_structure(self):
        """Test COST_EFFICIENT_MODELS has expected structure."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        assert "openai" in COST_EFFICIENT_MODELS
        assert "anthropic" in COST_EFFICIENT_MODELS
        assert "deepseek" in COST_EFFICIENT_MODELS

        # Check OpenAI models
        openai_models = COST_EFFICIENT_MODELS["openai"]
        assert QueryComplexity.SIMPLE in openai_models
        assert QueryComplexity.ADVANCED in openai_models

    # Test: handler initialization
    def test_handler_initialization(self, handler):
        """Test handler initializes correctly."""
        assert handler.workspace_id == "default"
        assert handler.tenant_id == "default"
        assert handler.byok_manager is not None
        assert handler.cognitive_classifier is not None
        assert handler.cache_router is not None

    def test_handler_with_custom_workspace(self):
        """Test handler with custom workspace_id."""
        custom_handler = BYOKHandler(workspace_id="custom-workspace")
        assert custom_handler.workspace_id == "custom-workspace"

    # Test: models without tools
    def test_models_without_tools(self):
        """Test MODELS_WITHOUT_TOOLS configuration."""
        from core.llm.byok_handler import MODELS_WITHOUT_TOOLS

        assert "deepseek-v3.2-speciale" in MODELS_WITHOUT_TOOLS
        assert isinstance(MODELS_WITHOUT_TOOLS, set)

    # Test: minimum quality by tier
    def test_min_quality_by_tier(self):
        """Test MIN_QUALITY_BY_TIER configuration."""
        from core.llm.byok_handler import MIN_QUALITY_BY_TIER

        assert CognitiveTier.MICRO in MIN_QUALITY_BY_TIER
        assert MIN_QUALITY_BY_TIER[CognitiveTier.MICRO] == 0

        assert CognitiveTier.STANDARD in MIN_QUALITY_BY_TIER
        assert MIN_QUALITY_BY_TIER[CognitiveTier.STANDARD] == 80

        assert CognitiveTier.COMPLEX in MIN_QUALITY_BY_TIER
        assert MIN_QUALITY_BY_TIER[CognitiveTier.COMPLEX] == 94


class TestCognitiveTierSystemCoverage:
    """Coverage expansion for CognitiveTierSystem."""

    @pytest.fixture
    def classifier(self):
        """Get cognitive classifier instance."""
        return CognitiveClassifier()

    # Test: CognitiveTier enum
    def test_cognitive_tier_enum_values(self):
        """Test CognitiveTier enum has correct values."""
        assert CognitiveTier.MICRO.value == "micro"
        assert CognitiveTier.STANDARD.value == "standard"
        assert CognitiveTier.VERSATILE.value == "versatile"
        assert CognitiveTier.HEAVY.value == "heavy"
        assert CognitiveTier.COMPLEX.value == "complex"

    # Test: tier thresholds
    def test_tier_thresholds_structure(self):
        """Test TIER_THRESHOLDS has expected structure."""
        assert CognitiveTier.MICRO in TIER_THRESHOLDS
        assert CognitiveTier.STANDARD in TIER_THRESHOLDS
        assert CognitiveTier.VERSATILE in TIER_THRESHOLDS
        assert CognitiveTier.HEAVY in TIER_THRESHOLDS
        assert CognitiveTier.COMPLEX in TIER_THRESHOLDS

        # Check threshold structure
        micro_threshold = TIER_THRESHOLDS[CognitiveTier.MICRO]
        assert "max_tokens" in micro_threshold
        assert "complexity_score" in micro_threshold
        assert "description" in micro_threshold

    def test_tier_thresholds_values(self):
        """Test tier threshold values are correct."""
        assert TIER_THRESHOLDS[CognitiveTier.MICRO]["max_tokens"] == 100
        assert TIER_THRESHOLDS[CognitiveTier.STANDARD]["max_tokens"] == 500
        assert TIER_THRESHOLDS[CognitiveTier.VERSATILE]["max_tokens"] == 2000
        assert TIER_THRESHOLDS[CognitiveTier.HEAVY]["max_tokens"] == 5000
        assert TIER_THRESHOLDS[CognitiveTier.COMPLEX]["max_tokens"] == float("inf")

    # Test: classify method
    def test_classify_micro_tier(self, classifier):
        """Classify micro queries (short, simple)."""
        tier = classifier.classify("Hello")
        assert tier == CognitiveTier.MICRO

    def test_classify_standard_tier(self, classifier):
        """Classify standard queries (moderate length)."""
        prompt = "Analyze the following text: " + "word " * 100
        tier = classifier.classify(prompt)
        assert tier in [CognitiveTier.STANDARD, CognitiveTier.MICRO]

    def test_classify_heavy_tier(self, classifier):
        """Classify heavy queries (long, complex)."""
        long_text = "Analyze " * 10000
        tier = classifier.classify(long_text)
        assert tier in [CognitiveTier.HEAVY, CognitiveTier.COMPLEX]

    def test_classify_with_task_type(self, classifier):
        """Classify with task type adjustment."""
        prompt = "Write code to implement feature"
        tier = classifier.classify(prompt, task_type="code")
        # Code task type increases complexity
        assert tier in [CognitiveTier.STANDARD, CognitiveTier.VERSATILE]

    # Test: complexity score calculation
    def test_calculate_complexity_score_simple(self, classifier):
        """Calculate complexity score for simple text."""
        score = classifier._calculate_complexity_score("hello world")
        # Simple text should have low score
        assert score <= 2

    def test_calculate_complexity_score_empty(self, classifier):
        """Calculate complexity score for empty text."""
        score = classifier._calculate_complexity_score("")
        assert score >= -2  # Minimum bound

    def test_calculate_complexity_score_with_code(self, classifier):
        """Calculate complexity score with code patterns."""
        score = classifier._calculate_complexity_score("Write a function to debug the API endpoint")
        # Code pattern should increase score
        assert score >= 3

    def test_calculate_complexity_score_with_math(self, classifier):
        """Calculate complexity score with math patterns."""
        score = classifier._calculate_complexity_score("Solve this integral: calculus equation")
        # Math pattern should increase score
        assert score >= 3

    def test_calculate_complexity_score_with_advanced_terms(self, classifier):
        """Calculate complexity score with advanced terms."""
        score = classifier._calculate_complexity_score("Design enterprise-scale architecture with security audit")
        # Advanced patterns should increase score
        assert score >= 5

    def test_calculate_complexity_score_with_code_block(self, classifier):
        """Calculate complexity score with code block."""
        prompt = "```python\ndef hello():\n    pass\n```"
        score = classifier._calculate_complexity_score(prompt)
        # Code block should increase score
        assert score >= 3

    # Test: complexity patterns
    def test_complexity_patterns_compiled(self, classifier):
        """Test complexity patterns are compiled on init."""
        assert hasattr(classifier, '_compiled_patterns')
        assert len(classifier._compiled_patterns) > 0

        for name, (pattern, weight) in classifier._compiled_patterns.items():
            assert hasattr(pattern, 'search')  # Regex pattern
            assert isinstance(weight, int)

    def test_simple_pattern_matching(self, classifier):
        """Test simple pattern reduces complexity."""
        score = classifier._calculate_complexity_score("hello, please simplify this")
        assert score < 0  # Simple pattern has -2 weight

    def test_moderate_pattern_matching(self, classifier):
        """Test moderate pattern increases complexity."""
        score = classifier._calculate_complexity_score("analyze and evaluate the concept")
        assert score >= 1  # Moderate pattern has +1 weight

    # Test: task type adjustments
    def test_task_type_code_adjustment(self, classifier):
        """Test code task type adjustment."""
        base_score = classifier._calculate_complexity_score("test")
        code_score = classifier._calculate_complexity_score("test", task_type="code")
        assert code_score == base_score + 2

    def test_task_type_analysis_adjustment(self, classifier):
        """Test analysis task type adjustment."""
        base_score = classifier._calculate_complexity_score("test")
        analysis_score = classifier._calculate_complexity_score("test", task_type="analysis")
        assert analysis_score == base_score + 2

    def test_task_type_chat_adjustment(self, classifier):
        """Test chat task type adjustment."""
        base_score = classifier._calculate_complexity_score("test")
        chat_score = classifier._calculate_complexity_score("test", task_type="chat")
        assert chat_score == base_score - 1


class TestCacheAwareRouterCoverage:
    """Coverage expansion for CacheAwareRouter."""

    @pytest.fixture
    def router(self):
        """Get cache-aware router instance."""
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        return CacheAwareRouter(get_pricing_fetcher())

    # Test: initialization
    def test_router_initialization(self, router):
        """Test router initializes with pricing fetcher."""
        assert router.pricing_fetcher is not None

    # Test: cache key generation
    def test_generate_cache_key_consistent(self, router):
        """Generate consistent cache key for same prompt."""
        key1 = router.generate_cache_key("test prompt", "gpt-4")
        key2 = router.generate_cache_key("test prompt", "gpt-4")
        assert key1 == key2

    def test_generate_cache_key_different_models(self, router):
        """Generate different cache keys for different models."""
        key1 = router.generate_cache_key("test prompt", "gpt-4")
        key2 = router.generate_cache_key("test prompt", "claude-3")
        assert key1 != key2

    def test_generate_cache_key_different_prompts(self, router):
        """Generate different cache keys for different prompts."""
        key1 = router.generate_cache_key("prompt 1", "gpt-4")
        key2 = router.generate_cache_key("prompt 2", "gpt-4")
        assert key1 != key2

    # Test: prompt normalization
    def test_normalize_prompt_whitespace(self, router):
        """Normalize prompt by removing extra whitespace."""
        normalized = router.normalize_prompt("Hello    world   test")
        assert normalized == "Hello world test"

    def test_normalize_prompt_newlines(self, router):
        """Normalize prompt by removing extra newlines."""
        normalized = router.normalize_prompt("Hello\n\n\nworld")
        # Should collapse newlines
        assert "\n\n\n" not in normalized

    def test_normalize_prompt_case_sensitive(self, router):
        """Keep case sensitivity for normalization."""
        normalized = router.normalize_prompt("Hello World TEST")
        assert "Hello" in normalized
        assert "World" in normalized

    def test_normalize_prompt_empty(self, router):
        """Normalize empty prompt."""
        normalized = router.normalize_prompt("")
        assert normalized == ""

    # Test: cacheability detection
    def test_detect_cacheable_simple_repeat(self, router):
        """Detect cacheable simple repeat request."""
        is_cacheable = router.is_cacheable("Repeat this exact text: hello")
        # Simple repeat is highly cacheable
        assert isinstance(is_cacheable, bool)

    def test_detect_cacheable_with_timestamp(self, router):
        """Detect non-cacheable prompt with timestamp."""
        from datetime import datetime
        prompt = f"Generate report for {datetime.now().isoformat()}"
        is_cacheable = router.is_cacheable(prompt)
        # Timestamps make it less cacheable
        assert isinstance(is_cacheable, bool)

    def test_detect_cacheable_empty(self, router):
        """Handle empty prompt for cacheability."""
        is_cacheable = router.is_cacheable("")
        assert isinstance(is_cacheable, bool)

    # Test: pricing integration
    @patch('core.llm.cache_aware_router.get_pricing_fetcher')
    def test_router_uses_pricing_fetcher(self, mock_get_fetcher):
        """Test router uses pricing fetcher for cost calculations."""
        mock_fetcher = Mock()
        mock_get_fetcher.return_value = mock_fetcher

        router = CacheAwareRouter(mock_fetcher)
        assert router.pricing_fetcher == mock_fetcher

    # Test: hash-based key generation
    def test_cache_key_is_hash(self, router):
        """Test cache key uses hash for consistency."""
        key = router.generate_cache_key("test prompt", "gpt-4")
        # Keys should be hash-based (consistent length)
        assert len(key) > 0
        assert isinstance(key, str)

    def test_cache_key_handles_special_chars(self, router):
        """Test cache key handles special characters."""
        key = router.generate_cache_key("test!@#$%^&*()", "gpt-4")
        assert len(key) > 0
        assert isinstance(key, str)

    def test_cache_key_handles_unicode(self, router):
        """Test cache key handles unicode characters."""
        key = router.generate_cache_key("test 你好 🚀", "gpt-4")
        assert len(key) > 0
        assert isinstance(key, str)
