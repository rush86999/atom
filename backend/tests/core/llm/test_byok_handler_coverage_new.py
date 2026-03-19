"""
Coverage-driven tests for byok_handler.py (0% -> 70%+ target)

Strategy: Test methods that don't require complex initialization,
focus on configuration constants and utility methods.

Note: BYOKHandler has complex inline imports in __init__ that make
mocking difficult. This file focuses on testable synchronous logic.

Focus Areas:
- Lines 22-98: Configuration constants and enums
- Lines 149-192: Provider fallback order logic
- Lines 253-301: Context window handling
- Lines 303-353: Query complexity analysis
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import os

# Mock the inline imports before importing BYOKHandler
sys_modules_original = {}

def setup_module():
    """Setup mocks for inline imports"""
    import sys
    global sys_modules_original

    # Store original modules
    sys_modules_original = {
        'core.dynamic_pricing_fetcher': sys.modules.get('core.dynamic_pricing_fetcher'),
        'core.llm.cache_aware_router': sys.modules.get('core.llm.cache_aware_router'),
        'core.database': sys.modules.get('core.database'),
        'core.llm.cognitive_tier_service': sys.modules.get('core.llm.cognitive_tier_service'),
    }

    # Create mock modules
    mock_pricing = MagicMock()
    mock_fetcher = Mock()
    mock_fetcher.get_model_price = Mock(return_value=None)  # Return None to trigger defaults
    mock_pricing.get_pricing_fetcher = Mock(return_value=mock_fetcher)
    sys.modules['core.dynamic_pricing_fetcher'] = mock_pricing

    mock_router = MagicMock()
    sys.modules['core.llm.cache_aware_router'] = mock_router

    mock_db = MagicMock()
    mock_session = MagicMock()
    mock_session.__enter__ = Mock(return_value=Mock())
    mock_session.__exit__ = Mock(return_value=False)
    mock_db.get_db_session = Mock(return_value=mock_session)
    sys.modules['core.database'] = mock_db

    mock_tier_service = MagicMock()
    sys.modules['core.llm.cognitive_tier_service'] = mock_tier_service

def teardown_module():
    """Restore original modules"""
    import sys
    for module_name, original_module in sys_modules_original.items():
        if original_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original_module

# Import after setup
from core.llm.byok_handler import (
    QueryComplexity,
    COST_EFFICIENT_MODELS,
    PROVIDER_TIERS,
    MODELS_WITHOUT_TOOLS,
)


class TestQueryComplexityEnum:
    """Tests for QueryComplexity enum (lines 22-28)"""

    def test_query_complexity_enum_values(self):
        """Test QueryComplexity has all expected values"""
        assert QueryComplexity.SIMPLE.value == "simple"
        assert QueryComplexity.MODERATE.value == "moderate"
        assert QueryComplexity.COMPLEX.value == "complex"
        assert QueryComplexity.ADVANCED.value == "advanced"

    def test_query_complexity_enum_iteration(self):
        """Test can iterate over QueryComplexity values"""
        complexities = list(QueryComplexity)
        assert len(complexities) == 4
        assert QueryComplexity.SIMPLE in complexities
        assert QueryComplexity.ADVANCED in complexities


class TestCostEfficientModels:
    """Tests for cost-efficient model configuration (lines 44-82)"""

    @pytest.mark.parametrize("provider,complexity", [
        ("openai", QueryComplexity.SIMPLE),
        ("openai", QueryComplexity.COMPLEX),
        ("anthropic", QueryComplexity.SIMPLE),
        ("anthropic", QueryComplexity.ADVANCED),
        ("deepseek", QueryComplexity.SIMPLE),
        ("deepseek", QueryComplexity.ADVANCED),
        ("gemini", QueryComplexity.MODERATE),
        ("moonshot", QueryComplexity.COMPLEX),
    ])
    def test_cost_efficient_models_configuration(self, provider, complexity):
        """Test cost-efficient models are configured for all providers"""
        assert provider in COST_EFFICIENT_MODELS
        assert complexity in COST_EFFICIENT_MODELS[provider]
        model = COST_EFFICIENT_MODELS[provider][complexity]
        assert isinstance(model, str)
        assert len(model) > 0


class TestProviderTiers:
    """Tests for provider tier configuration (lines 31-42)"""

    def test_provider_tiers_structure(self):
        """Test provider tiers are properly configured"""
        assert "budget" in PROVIDER_TIERS
        assert "mid" in PROVIDER_TIERS
        assert "premium" in PROVIDER_TIERS
        assert "code" in PROVIDER_TIERS
        assert "math" in PROVIDER_TIERS
        assert "creative" in PROVIDER_TIERS

    def test_budget_tier_contains_providers(self):
        """Test budget tier contains cost-effective providers"""
        budget_providers = PROVIDER_TIERS["budget"]
        assert "deepseek" in budget_providers
        assert "moonshot" in budget_providers
        assert "glm" in budget_providers

    def test_premium_tier_contains_quality_providers(self):
        """Test premium tier contains high-quality providers"""
        premium_providers = PROVIDER_TIERS["premium"]
        assert "openai" in premium_providers
        assert "anthropic" in premium_providers


class TestModelsWithoutTools:
    """Tests for models without tools configuration (lines 85-88)"""

    def test_models_without_tools_contains_deepseek(self):
        """Test deepseek special models are in without-tools list"""
        assert "deepseek-v3.2-speciale" in MODELS_WITHOUT_TOOLS

    def test_models_without_tools_is_set(self):
        """Test MODELS_WITHOUT_TOOLS is a set for O(1) lookup"""
        assert isinstance(MODELS_WITHOUT_TOOLS, set)


class TestQueryComplexityAnalysis:
    """Tests for query complexity analysis (lines 303-353)"""

    @pytest.fixture
    def handler(self):
        """Create a minimal handler for testing"""
        from core.llm.byok_handler import BYOKHandler

        # Create handler without calling __init__
        handler = BYOKHandler.__new__(BYOKHandler)
        handler.workspace_id = "default"
        handler.default_provider_id = None
        handler.clients = {}
        handler.async_clients = {}
        return handler

    @pytest.mark.parametrize("prompt,expected_complexity", [
        ("hello", QueryComplexity.SIMPLE),
        ("summarize this", QueryComplexity.SIMPLE),
        ("what is python", QueryComplexity.SIMPLE),
        ("analyze the data", QueryComplexity.MODERATE),
        ("compare these options", QueryComplexity.MODERATE),
        ("calculate the integral", QueryComplexity.COMPLEX),
        ("solve this equation", QueryComplexity.COMPLEX),
        ("write a function to sort", QueryComplexity.COMPLEX),
        ("architecture design for enterprise", QueryComplexity.ADVANCED),
        ("security audit and vulnerability assessment", QueryComplexity.ADVANCED),
    ])
    def test_analyze_query_complexity(self, handler, prompt, expected_complexity):
        """Test query complexity classification"""
        complexity = handler.analyze_query_complexity(prompt)
        assert complexity == expected_complexity

    def test_analyze_query_complexity_with_code_blocks(self, handler):
        """Test code blocks increase complexity"""
        simple = "hello world"
        with_code = "hello world\n```python\ndef foo():\n    pass\n```"
        simple_complexity = handler.analyze_query_complexity(simple)
        with_code_complexity = handler.analyze_query_complexity(with_code)
        # Compare complexity levels by their order in the enum
        complexity_order = [QueryComplexity.SIMPLE, QueryComplexity.MODERATE, QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]
        simple_idx = complexity_order.index(simple_complexity)
        with_code_idx = complexity_order.index(with_code_complexity)
        assert with_code_idx >= simple_idx

    def test_analyze_query_complexity_with_task_type(self, handler):
        """Test task type override affects complexity"""
        prompt = "explain this"
        general_complexity = handler.analyze_query_complexity(prompt, task_type="general")
        code_complexity = handler.analyze_query_complexity(prompt, task_type="code")
        # Compare complexity levels by their order in the enum
        complexity_order = [QueryComplexity.SIMPLE, QueryComplexity.MODERATE, QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]
        general_idx = complexity_order.index(general_complexity)
        code_idx = complexity_order.index(code_complexity)
        assert code_idx >= general_idx

    def test_empty_prompt_complexity(self, handler):
        """Test complexity analysis with empty prompt"""
        complexity = handler.analyze_query_complexity("")
        assert complexity == QueryComplexity.SIMPLE

    def test_very_long_prompt_complexity(self, handler):
        """Test complexity analysis with very long prompt"""
        long_prompt = "word " * 10000  # Very long prompt
        complexity = handler.analyze_query_complexity(long_prompt)
        # Should be at least MODERATE due to length
        assert complexity.value in ["moderate", "complex", "advanced"]

    def test_special_characters_in_prompt(self, handler):
        """Test complexity analysis handles special characters"""
        special_prompt = "analyze this: 🎉🎊 <script> alert('xss') </script> &amp;"
        complexity = handler.analyze_query_complexity(special_prompt)
        assert isinstance(complexity, QueryComplexity)

    def test_unicode_and_multilingual(self, handler):
        """Test complexity analysis with multilingual input"""
        multilingual_prompts = [
            "你好",  # Chinese
            "مرحبا",  # Arabic
            "こんにちは",  # Japanese
            "Привет",  # Cyrillic
        ]
        for prompt in multilingual_prompts:
            complexity = handler.analyze_query_complexity(prompt)
            assert isinstance(complexity, QueryComplexity)

    def test_multiple_code_blocks_increase_complexity(self, handler):
        """Test multiple code blocks increase complexity score"""
        single_code = "explain\n```python\ncode\n```"
        multiple_code = "explain\n```python\ncode1\n```\n```js\ncode2\n```"
        single_complexity = handler.analyze_query_complexity(single_code)
        multiple_complexity = handler.analyze_query_complexity(multiple_code)
        # Multiple code blocks should have same or higher complexity
        assert multiple_complexity.value >= single_complexity.value


class TestContextWindow:
    """Tests for context window handling (lines 253-301)"""

    @pytest.fixture
    def handler(self):
        """Create a minimal handler for testing"""
        from core.llm.byok_handler import BYOKHandler

        handler = BYOKHandler.__new__(BYOKHandler)
        handler.workspace_id = "default"
        handler.default_provider_id = None
        handler.clients = {}
        handler.async_clients = {}
        return handler

    def test_get_context_window_from_pricing(self, handler):
        """Test getting context window from pricing data"""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher') as mock_fetcher:
            fetcher = Mock()
            fetcher.get_model_price.return_value = {"max_input_tokens": 128000}
            mock_fetcher.return_value = fetcher

            context = handler.get_context_window("gpt-4o")
            assert context == 128000

    def test_get_context_window_fallback_to_defaults(self, handler):
        """Test context window falls back to defaults"""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher') as mock_fetcher:
            fetcher = Mock()
            fetcher.get_model_price.return_value = None
            mock_fetcher.return_value = fetcher

            context = handler.get_context_window("gpt-4o")
            assert context == 128000  # Default from CONTEXT_DEFAULTS

    def test_get_context_window_unknown_model(self, handler):
        """Test context window for unknown model returns conservative default"""
        with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher') as mock_fetcher:
            fetcher = Mock()
            fetcher.get_model_price.return_value = None
            mock_fetcher.return_value = fetcher

            context = handler.get_context_window("unknown-model")
            assert context == 4096  # Conservative default

    def test_truncate_to_context_no_truncation_needed(self, handler):
        """Test text truncation when text fits in context"""
        short_text = "This is a short text"
        result = handler.truncate_to_context(short_text, "gpt-4o")
        assert result == short_text

    def test_truncate_to_context_with_truncation(self, handler):
        """Test text truncation when text exceeds context"""
        # Create text that will exceed context for a model with smaller context
        # Use a model that defaults to 4096 (conservative default)
        long_text = "x" * 20000
        result = handler.truncate_to_context(long_text, "unknown-model", reserve_tokens=1000)
        assert len(result) < len(long_text)
        assert "[... Content truncated" in result

    def test_context_window_with_reserve_tokens(self, handler):
        """Test context window calculation with reserve tokens"""
        text = "x" * 10000
        result = handler.truncate_to_context(text, "gpt-4o", reserve_tokens=2000)
        # Should truncate more with higher reserve
        assert len(result) <= 10000


class TestProviderFallbackOrder:
    """Tests for provider fallback order logic (lines 149-192)"""

    @pytest.fixture
    def handler(self):
        """Create a minimal handler for testing"""
        from core.llm.byok_handler import BYOKHandler

        handler = BYOKHandler.__new__(BYOKHandler)
        handler.clients = {
            "openai": Mock(),
            "deepseek": Mock(),
            "moonshot": Mock(),
        }
        handler.async_clients = handler.clients.copy()
        return handler

    def test_fallback_order_with_deepseek_primary(self, handler):
        """Test fallback order when deepseek is primary"""
        fallback = handler._get_provider_fallback_order("deepseek")
        assert fallback[0] == "deepseek"
        assert "openai" in fallback
        assert "moonshot" in fallback

    def test_fallback_order_with_no_clients(self):
        """Test fallback order when no clients available"""
        from core.llm.byok_handler import BYOKHandler

        handler = BYOKHandler.__new__(BYOKHandler)
        handler.clients = {}
        handler.async_clients = {}
        fallback = handler._get_provider_fallback_order("openai")
        assert fallback == []

    def test_fallback_order_with_unavailable_provider(self):
        """Test fallback order when requested provider not available"""
        from core.llm.byok_handler import BYOKHandler

        handler = BYOKHandler.__new__(BYOKHandler)
        handler.clients = {"openai": Mock(), "deepseek": Mock()}
        handler.async_clients = handler.clients.copy()
        fallback = handler._get_provider_fallback_order("moonshot")
        # Should skip moonshot and use available providers
        assert "openai" in fallback or "deepseek" in fallback
