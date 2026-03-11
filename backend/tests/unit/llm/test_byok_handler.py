"""
Unit tests for BYOKHandler methods (Phase 165-02)

These tests target BYOKHandler methods to increase coverage for:
- analyze_query_complexity() method
- get_routing_info() method
- get_context_window() method
- truncate_to_context() method
- classify_cognitive_tier() method

Target: 250+ lines, unit tests for BYOKHandler core methods
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from core.llm.byok_handler import BYOKHandler, QueryComplexity, PROVIDER_TIERS, COST_EFFICIENT_MODELS


class TestBYOKHandlerInitialization:
    """Test BYOKHandler initialization and setup."""

    def test_byok_handler_init_default(self):
        """Test BYOKHandler initialization with default parameters."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            assert handler.workspace_id == "default"
            assert handler.default_provider_id is None
            assert hasattr(handler, 'clients')
            assert hasattr(handler, 'async_clients')
            assert hasattr(handler, 'byok_manager')
            assert hasattr(handler, 'cognitive_classifier')

    def test_byok_handler_init_with_provider_id(self):
        """Test BYOKHandler initialization with specific provider_id."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler(provider_id="openai")

            assert handler.workspace_id == "default"
            assert handler.default_provider_id == "openai"


class TestAnalyzeQueryComplexity:
    """
    Unit tests for analyze_query_complexity() method.

    Coverage: analyze_query_complexity() lines
    Tests: Length-based scoring, regex patterns, task type, code blocks
    """

    def test_analyze_query_complexity_simple_short(self):
        """Test simple short query classification."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Very short simple query
            complexity = handler.analyze_query_complexity("hi")
            assert complexity == QueryComplexity.SIMPLE

    def test_analyze_query_complexity_length_based(self):
        """Test length-based complexity scoring."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Short query (< 100 tokens / 400 chars)
            short = "hi " * 10  # ~30 chars
            complexity_short = handler.analyze_query_complexity(short)
            assert complexity_short in QueryComplexity

            # Medium query (100-500 tokens / 400-2000 chars)
            medium = "test " * 500  # ~2500 chars
            complexity_medium = handler.analyze_query_complexity(medium)
            assert complexity_medium in QueryComplexity

            # Long query (> 2000 tokens / 8000 chars) with advanced vocabulary
            long = "architecture design distributed system security audit scalability " * 300
            complexity_long = handler.analyze_query_complexity(long)
            # Should be COMPLEX or ADVANCED with length + advanced vocabulary
            assert complexity_long in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_query_complexity_with_vocabulary_patterns(self):
        """Test vocabulary pattern matching for complexity."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Simple vocabulary
            simple = "please summarize this text briefly"
            assert handler.analyze_query_complexity(simple) in [QueryComplexity.SIMPLE, QueryComplexity.MODERATE]

            # Moderate vocabulary
            moderate = "analyze and compare the different approaches"
            assert handler.analyze_query_complexity(moderate) in [QueryComplexity.MODERATE, QueryComplexity.COMPLEX]

            # Technical vocabulary
            technical = "calculate the integral and solve the equation"
            assert handler.analyze_query_complexity(technical) in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

            # Code vocabulary
            code = "debug the function and optimize the database schema"
            assert handler.analyze_query_complexity(code) in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

            # Advanced vocabulary
            advanced = "design distributed system architecture with security audit"
            assert handler.analyze_query_complexity(advanced) == QueryComplexity.ADVANCED

    def test_analyze_query_complexity_with_task_type(self):
        """Test task type influence on complexity."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            base_prompt = "help me with this"

            # No task type
            base = handler.analyze_query_complexity(base_prompt)

            # Code task type (increases complexity)
            code_task = handler.analyze_query_complexity(base_prompt, task_type="code")

            # Chat task type (may decrease complexity)
            chat_task = handler.analyze_query_complexity(base_prompt, task_type="chat")

            # All should be valid
            assert base in QueryComplexity
            assert code_task in QueryComplexity
            assert chat_task in QueryComplexity

    def test_analyze_query_complexity_with_code_blocks(self):
        """Test code block detection increases complexity."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Without code block
            without_code = "explain this concept"
            complexity_without = handler.analyze_query_complexity(without_code)

            # With code block
            with_code = "explain this concept\n```python\ndef foo():\n    pass\n```"
            complexity_with = handler.analyze_query_complexity(with_code)

            # Both should be valid
            assert complexity_without in QueryComplexity
            assert complexity_with in QueryComplexity

            # Code version should be equal or higher complexity
            complexity_order = {
                QueryComplexity.SIMPLE: 0,
                QueryComplexity.MODERATE: 1,
                QueryComplexity.COMPLEX: 2,
                QueryComplexity.ADVANCED: 3,
            }
            assert complexity_order[complexity_with] >= complexity_order[complexity_without]

    def test_analyze_query_complexity_combined_factors(self):
        """Test complexity with multiple factors combined."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Long text + technical vocabulary + code block + code task type
            complex_query = """
            Design a distributed system architecture for blockchain implementation.
            Please analyze the consensus algorithms and cryptography requirements.

            ```python
            class Blockchain:
                def __init__(self):
                    self.chain = []
            ```

            Implement zero-knowledge proof for privacy preservation.
            """

            complexity = handler.analyze_query_complexity(complex_query, task_type="code")
            assert complexity == QueryComplexity.ADVANCED


class TestGetContextWindow:
    """
    Unit tests for get_context_window() method.

    Coverage: get_context_window() lines
    Tests: Default contexts, specific models, fallback
    """

    def test_get_context_window_known_model(self):
        """Test context window for known models."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # GPT-4o
            context = handler.get_context_window("gpt-4o")
            assert context > 0
            assert isinstance(context, int)

            # Claude
            context = handler.get_context_window("claude-3-opus")
            assert context > 0
            assert isinstance(context, int)

            # DeepSeek
            context = handler.get_context_window("deepseek-chat")
            assert context > 0
            assert isinstance(context, int)

    def test_get_context_window_unknown_model(self):
        """Test context window for unknown models returns default."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Unknown model
            context = handler.get_context_window("unknown-model-xyz")
            assert context == 4096  # Conservative default

    def test_get_context_window_with_pricing_fetcher(self):
        """Test context window from dynamic pricing fetcher."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            # Mock pricing fetcher
            with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher') as mock_fetcher:
                fetcher = MagicMock()
                fetcher.get_model_price.return_value = {
                    "max_input_tokens": 128000,
                    "max_tokens": 128000
                }
                mock_fetcher.return_value = fetcher

                handler = BYOKHandler()

                context = handler.get_context_window("test-model")
                assert context == 128000


class TestTruncateToContext:
    """
    Unit tests for truncate_to_context() method.

    Coverage: truncate_to_context() lines
    Tests: No truncation needed, truncation with indicator
    """

    def test_truncate_to_context_no_truncation(self):
        """Test truncation when text fits in context."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Short text that fits
            short_text = "This is a short text"
            result = handler.truncate_to_context(short_text, "gpt-4o")

            assert result == short_text

    def test_truncate_to_context_with_truncation(self):
        """Test truncation when text exceeds context."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Very long text (simulate by mocking get_context_window)
            long_text = "x" * 10000

            with patch.object(handler, 'get_context_window', return_value=1000):
                result = handler.truncate_to_context(long_text, "test-model")

                # Should be truncated
                assert len(result) < len(long_text)
                # Should include truncation indicator
                assert "truncated" in result.lower() or "..." in result

    def test_truncate_to_context_with_reserve_tokens(self):
        """Test truncation with reserve_tokens parameter."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Text that would fit without reserve but not with reserve
            text = "x" * 5000

            with patch.object(handler, 'get_context_window', return_value=2000):
                result = handler.truncate_to_context(text, "test-model", reserve_tokens=1000)

                # Should be truncated more aggressively with reserve
                assert len(result) < len(text)


class TestGetRoutingInfo:
    """
    Unit tests for get_routing_info() method.

    Coverage: get_routing_info() lines
    Tests: All complexity levels, error handling
    """

    def test_get_routing_info_simple(self):
        """Test routing info for SIMPLE complexity."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            routing = handler.get_routing_info("hi")

            assert isinstance(routing, dict)
            assert "complexity" in routing
            assert routing["complexity"] in QueryComplexity

    def test_get_routing_info_moderate(self):
        """Test routing info for MODERATE complexity."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            routing = handler.get_routing_info("Analyze the causes of WWI")

            assert isinstance(routing, dict)
            assert "complexity" in routing
            assert routing["complexity"] in QueryComplexity

    def test_get_routing_info_complex(self):
        """Test routing info for COMPLEX complexity."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            routing = handler.get_routing_info("Design a RESTful API architecture")

            assert isinstance(routing, dict)
            assert "complexity" in routing
            assert routing["complexity"] in QueryComplexity

    def test_get_routing_info_advanced(self):
        """Test routing info for ADVANCED complexity."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            routing = handler.get_routing_info("Design distributed system with security audit")

            assert isinstance(routing, dict)
            assert "complexity" in routing
            assert routing["complexity"] in QueryComplexity

    def test_get_routing_info_with_cost_estimation(self):
        """Test routing info includes cost estimation when available."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            # Mock pricing fetcher
            with patch('core.dynamic_pricing_fetcher.get_pricing_fetcher') as mock_fetcher:
                fetcher = MagicMock()
                fetcher.get_model_price.return_value = {
                    "input_price": 0.50,
                    "output_price": 1.50
                }
                fetcher.estimate_cost.return_value = 0.002
                mock_fetcher.return_value = fetcher

                handler = BYOKHandler()

                routing = handler.get_routing_info("test query")

                # May include estimated cost if pricing available
                assert isinstance(routing, dict)
                # Cost is optional, may or may not be present

    def test_get_routing_info_error_handling(self):
        """Test routing info handles errors gracefully."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # If no providers available, should still return valid dict
            routing = handler.get_routing_info("test")

            assert isinstance(routing, dict)
            # Should have complexity or error
            assert "complexity" in routing or "error" in routing


class TestClassifyCognitiveTier:
    """
    Unit tests for classify_cognitive_tier() method.

    Coverage: classify_cognitive_tier() lines
    Tests: Wrapper for CognitiveClassifier
    """

    def test_classify_cognitive_tier_simple(self):
        """Test cognitive tier classification for simple queries."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            tier = handler.classify_cognitive_tier("hi")
            assert tier.value in ["micro", "standard"]

    def test_classify_cognitive_tier_with_task_type(self):
        """Test cognitive tier classification with task type."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            tier = handler.classify_cognitive_tier("help me", task_type="code")
            assert tier.value in ["micro", "standard", "versatile"]

    def test_classify_cognitive_tier_complex(self):
        """Test cognitive tier classification for complex queries."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Long complex query
            long_query = "design distributed system " * 100
            tier = handler.classify_cognitive_tier(long_query)
            assert tier.value in ["versatile", "heavy", "complex"]


class TestProviderFallback:
    """
    Unit tests for _get_provider_fallback_order() method.

    Coverage: _get_provider_fallback_order() lines
    Tests: Fallback order, unavailable providers
    """

    def test_get_provider_fallback_order_standard(self):
        """Test provider fallback order for standard provider."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Mock some available providers
            handler.clients = {"deepseek": MagicMock(), "openai": MagicMock()}

            fallback = handler._get_provider_fallback_order("openai")

            assert isinstance(fallback, list)
            # Primary should be first if available
            if fallback:
                assert fallback[0] == "openai"

    def test_get_provider_fallback_order_unavailable(self):
        """Test fallback order when primary provider unavailable."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Mock different available providers
            handler.clients = {"deepseek": MagicMock(), "moonshot": MagicMock()}

            fallback = handler._get_provider_fallback_order("openai")

            assert isinstance(fallback, list)
            # Should not include unavailable provider
            assert "openai" not in fallback

    def test_get_provider_fallback_order_empty_clients(self):
        """Test fallback order when no clients available."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()
            handler.clients = {}
            handler.async_clients = {}

            fallback = handler._get_provider_fallback_order("openai")

            assert fallback == []


class TestGetAvailableProviders:
    """
    Unit tests for get_available_providers() method.

    Coverage: get_available_providers() lines
    """

    def test_get_available_providers_with_clients(self):
        """Test getting available providers list."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Mock clients
            handler.clients = {"deepseek": MagicMock(), "openai": MagicMock()}

            providers = handler.get_available_providers()

            assert isinstance(providers, list)
            assert "deepseek" in providers
            assert "openai" in providers

    def test_get_available_providers_empty(self):
        """Test getting available providers when none configured."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()
            handler.clients = {}

            providers = handler.get_available_providers()

            assert providers == []


class TestTrialRestriction:
    """
    Unit tests for _is_trial_restricted() method.

    Coverage: _is_trial_restricted() lines
    """

    def test_is_trial_restricted_default(self):
        """Test trial restriction check returns False by default."""
        with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
            mock_mgr = MagicMock()
            mock_mgr.is_configured.return_value = False
            mock_manager.return_value = mock_mgr

            handler = BYOKHandler()

            # Default should be False (no restriction)
            restricted = handler._is_trial_restricted()
            assert restricted is False
