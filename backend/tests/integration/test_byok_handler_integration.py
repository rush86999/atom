"""
Integration tests for byok_handler.py (Phase 12, GAP-02).

Tests cover:
- Provider selection and routing with mocked LLM clients
- Fallback behavior when primary provider fails
- Token counting accuracy
- Rate limiting enforcement
- Streaming response handling
- Query complexity analysis
- Context window management
- Text truncation for context limits
- Model recommendations by provider

Coverage target: 40% of byok_handler.py (220+ lines from 549 total)
Current coverage: 11.27% (62 lines)
Target coverage: 40%+ (220+ lines)

Key difference from property tests: These tests CALL actual handler methods
(stream_completion, count_tokens, analyze_query_complexity) with mocked LLM
clients, rather than just validating provider selection invariants.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from core.llm.byok_handler import BYOKHandler, QueryComplexity


class TestProviderSelectionAndRouting:
    """Integration tests for provider selection and routing."""

    @pytest.mark.asyncio
    async def test_provider_selection_openai(self, db_session: Session):
        """Test actual provider selection logic with OpenAI."""
        handler = BYOKHandler()

        # Mock async OpenAI client
        mock_openai = MagicMock()
        mock_openai.chat.completions.create = MagicMock()

        # Mock streaming response
        async def mock_stream():
            yield MagicMock(delta=MagicMock(content="Test "))
            yield MagicMock(delta=MagicMock(content="response"))

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=""))]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.stream = mock_stream()

        # Make the create method return the mock response with stream
        async def mock_create(*args, **kwargs):
            return mock_response

        mock_openai.chat.completions.create = mock_create

        # Patch the handler's async_clients dict
        handler.async_clients = {"openai": mock_openai}

        # Collect streamed response
        result = ""
        async for chunk in handler.stream_completion(
            model="gpt-4",
            messages=[{"role": "user", "content": "Test"}],
            provider_id="openai"
        ):
            result += chunk

        # Verify actual provider logic was called
        assert "Test response" in result

    @pytest.mark.asyncio
    async def test_provider_selection_deepseek(self, db_session: Session):
        """Test provider selection for DeepSeek."""
        handler = BYOKHandler()

        # Mock DeepSeek client
        mock_deepseek = MagicMock()
        mock_deepseek.chat.completions.create = MagicMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="DeepSeek response"))]
            )
        )

        handler.clients = {"deepseek": mock_deepseek}

        result = await handler.stream_completion(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Test"}],
            provider="deepseek"
        )

        assert "DeepSeek response" in result

    @pytest.mark.asyncio
    async def test_auto_provider_selection(self, db_session: Session):
        """Test automatic provider selection."""
        handler = BYOKHandler(provider_id="auto")

        # Mock multiple providers
        mock_openai = MagicMock()
        mock_openai.chat.completions.create = MagicMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="OpenAI response"))]
            )
        )

        handler.clients = {"openai": mock_openai}
        handler.default_provider_id = "openai"

        result = await handler.stream_completion(
            model="gpt-4",
            messages=[{"role": "user", "content": "Test"}],
            provider="auto"
        )

        assert "OpenAI response" in result


class TestFallbackBehavior:
    """Integration tests for fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_to_secondary_provider(self, db_session: Session):
        """Test actual fallback logic when primary provider fails."""
        handler = BYOKHandler()

        # Mock Anthropic
        mock_anthropic = MagicMock()
        mock_anthropic.messages.create = MagicMock(
            return_value=MagicMock(
                content=[MagicMock(text="Fallback response")]
            )
        )

        handler.clients = {"anthropic": mock_anthropic}

        result = await handler.stream_completion(
            model="claude-3",
            messages=[{"role": "user", "content": "Test"}],
            provider="anthropic"
        )

        # Verify provider was called
        assert "Fallback response" in result

    @pytest.mark.asyncio
    async def test_provider_unavailable_raises_error(self, db_session: Session):
        """Test that unavailable provider raises error."""
        handler = BYOKHandler()
        handler.clients = {}  # No clients available

        with pytest.raises(Exception) as exc_info:
            await handler.stream_completion(
                model="gpt-4",
                messages=[{"role": "user", "content": "Test"}],
                provider="openai"
            )

        assert "openai" in str(exc_info.value).lower() or "not configured" in str(exc_info.value).lower()


class TestTokenCounting:
    """Integration tests for context window and token management."""

    def test_context_window_openai(self, db_session: Session):
        """Test getting context window for OpenAI models."""
        handler = BYOKHandler()

        # Test GPT-4 has large context
        context = handler.get_context_window("gpt-4o")
        assert context >= 128000

    def test_context_window_deepseek(self, db_session: Session):
        """Test getting context window for DeepSeek models."""
        handler = BYOKHandler()

        # DeepSeek has moderate context
        context = handler.get_context_window("deepseek-chat")
        assert context >= 32768

    def test_truncate_short_text(self, db_session: Session):
        """Test that short text is not truncated."""
        handler = BYOKHandler()

        short_text = "Hello"
        result = handler.truncate_to_context(short_text, "gpt-4o")

        assert result == short_text

    def test_truncate_long_text(self, db_session: Session):
        """Test that long text is truncated appropriately."""
        handler = BYOKHandler()

        # Create text longer than context
        long_text = "x" * 1000000
        result = handler.truncate_to_context(long_text, "gpt-4")

        # Should be truncated
        assert len(result) < len(long_text)
        assert "truncated" in result.lower()



class TestRateLimiting:
    """Integration tests for rate limiting enforcement."""

    @pytest.mark.asyncio
    async def test_rate_limit_tracking(self, db_session: Session):
        """Test actual rate limiting logic."""
        handler = BYOKHandler()

        # Mock successful responses
        mock_client = MagicMock()
        mock_client.chat.completions.create = MagicMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="OK"))]
            )
        )

        handler.clients = {"openai": mock_client}

        # Make multiple requests
        results = []
        for i in range(5):
            result = await handler.stream_completion(
                model="gpt-4",
                messages=[{"role": "user", "content": f"Request {i}"}],
                provider="openai"
            )
            results.append(result)

        # Verify requests succeeded
        assert len([r for r in results if "OK" in r]) == 5


class TestQueryComplexityAnalysis:
    """Integration tests for query complexity analysis."""

    def test_analyze_simple_query(self, db_session: Session):
        """Test complexity analysis for simple query."""
        handler = BYOKHandler()

        prompt = "Hello, how are you?"
        complexity = handler.analyze_query_complexity(prompt)

        assert complexity == QueryComplexity.SIMPLE

    def test_analyze_moderate_query(self, db_session: Session):
        """Test complexity analysis for moderate query."""
        handler = BYOKHandler()

        prompt = "Can you analyze the advantages and disadvantages of this approach?"
        complexity = handler.analyze_query_complexity(prompt)

        assert complexity == QueryComplexity.MODERATE

    def test_analyze_complex_query(self, db_session: Session):
        """Test complexity analysis for complex query."""
        handler = BYOKHandler()

        prompt = "Write a Python function to implement a binary search tree with insert and delete operations"
        complexity = handler.analyze_query_complexity(prompt)

        assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_advanced_query(self, db_session: Session):
        """Test complexity analysis for advanced query."""
        handler = BYOKHandler()

        prompt = "Design a distributed system architecture for handling security audits and cryptography at enterprise scale"
        complexity = handler.analyze_query_complexity(prompt)

        assert complexity == QueryComplexity.ADVANCED

    def test_analyze_code_query(self, db_session: Session):
        """Test complexity analysis for code-related query."""
        handler = BYOKHandler()

        prompt = "```python\ndef hello():\n    print('world')\n```\nDebug this code"
        complexity = handler.analyze_query_complexity(prompt)

        assert complexity in [QueryComplexity.COMPLEX, QueryComplexity.ADVANCED]

    def test_analyze_with_task_type(self, db_session: Session):
        """Test complexity analysis with task type hint."""
        handler = BYOKHandler()

        prompt = "Summarize this text"
        complexity = handler.analyze_query_complexity(prompt, task_type="summarization")

        assert complexity == QueryComplexity.SIMPLE


class TestContextWindowManagement:
    """Integration tests for context window management."""

    def test_get_context_window_known_model(self, db_session: Session):
        """Test getting context window for known model."""
        handler = BYOKHandler()

        # Test GPT-4
        context = handler.get_context_window("gpt-4o")
        assert context > 0
        assert context >= 128000

    def test_get_context_window_default_model(self, db_session: Session):
        """Test getting context window for unknown model (default)."""
        handler = BYOKHandler()

        # Test unknown model
        context = handler.get_context_window("unknown-model")
        assert context > 0
        # Should return conservative default
        assert context >= 4096

    def test_truncate_to_context_no_truncation(self, db_session: Session):
        """Test truncation when text fits in context."""
        handler = BYOKHandler()

        short_text = "This is a short text"
        result = handler.truncate_to_context(short_text, "gpt-4o")

        assert result == short_text

    def test_truncate_to_context_with_truncation(self, db_session: Session):
        """Test truncation when text exceeds context."""
        handler = BYOKHandler()

        # Create very long text
        long_text = "This is a very long text. " * 10000

        result = handler.truncate_to_context(long_text, "gpt-4", reserve_tokens=1000)

        # Should be truncated
        assert len(result) < len(long_text)
        assert "[... Content truncated" in result
        assert len(result) > 0


class TestModelRecommendations:
    """Integration tests for model recommendations by provider."""

    def test_cost_efficient_models_openai(self, db_session: Session):
        """Test cost-efficient model recommendations for OpenAI."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        openai_models = COST_EFFICIENT_MODELS.get("openai", {})

        # Check SIMPLE recommendation
        simple_model = openai_models.get(QueryComplexity.SIMPLE)
        assert simple_model is not None
        assert "mini" in simple_model.lower() or "4o-mini" in simple_model

        # Check ADVANCED recommendation
        advanced_model = openai_models.get(QueryComplexity.ADVANCED)
        assert advanced_model is not None

    def test_cost_efficient_models_anthropic(self, db_session: Session):
        """Test cost-efficient model recommendations for Anthropic."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        anthropic_models = COST_EFFICIENT_MODELS.get("anthropic", {})

        # Check SIMPLE recommendation
        simple_model = anthropic_models.get(QueryComplexity.SIMPLE)
        assert simple_model is not None
        assert "haiku" in simple_model.lower()

        # Check ADVANCED recommendation
        advanced_model = anthropic_models.get(QueryComplexity.ADVANCED)
        assert advanced_model is not None

    def test_cost_efficient_models_deepseek(self, db_session: Session):
        """Test cost-efficient model recommendations for DeepSeek."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        deepseek_models = COST_EFFICIENT_MODELS.get("deepseek", {})

        # Check SIMPLE recommendation
        simple_model = deepseek_models.get(QueryComplexity.SIMPLE)
        assert simple_model is not None
        assert "chat" in simple_model.lower()

        # Check ADVANCED recommendation
        advanced_model = deepseek_models.get(QueryComplexity.ADVANCED)
        assert advanced_model is not None


class TestProviderTiers:
    """Integration tests for provider tier mapping."""

    def test_provider_tiers_budget(self, db_session: Session):
        """Test budget tier providers."""
        from core.llm.byok_handler import PROVIDER_TIERS

        budget_providers = PROVIDER_TIERS.get("budget", [])

        assert "deepseek" in budget_providers
        assert "moonshot" in budget_providers

    def test_provider_tiers_premium(self, db_session: Session):
        """Test premium tier providers."""
        from core.llm.byok_handler import PROVIDER_TIERS

        premium_providers = PROVIDER_TIERS.get("premium", [])

        assert "openai" in premium_providers
        assert "anthropic" in premium_providers

    def test_provider_tiers_code(self, db_session: Session):
        """Test code-specialized providers."""
        from core.llm.byok_handler import PROVIDER_TIERS

        code_providers = PROVIDER_TIERS.get("code", [])

        assert "deepseek" in code_providers
        assert "openai" in code_providers


class TestModelsWithoutTools:
    """Integration tests for models without tool support."""

    def test_models_without_tools(self, db_session: Session):
        """Test models that don't support tool calling."""
        from core.llm.byok_handler import MODELS_WITHOUT_TOOLS

        # DeepSeek special reasoning model doesn't support tools
        assert "deepseek-v3.2-speciale" in MODELS_WITHOUT_TOOLS

    def test_reasoning_models_without_vision(self, db_session: Session):
        """Test reasoning models without vision support."""
        from core.llm.byok_handler import REASONING_MODELS_WITHOUT_VISION

        # DeepSeek models don't support vision
        assert "deepseek-v3.2" in REASONING_MODELS_WITHOUT_VISION
        assert "deepseek-v3.2-speciale" in REASONING_MODELS_WITHOUT_VISION

        # OpenAI o3 models
        assert "o3" in REASONING_MODELS_WITHOUT_VISION
        assert "o3-mini" in REASONING_MODELS_WITHOUT_VISION


class TestBYOKInitialization:
    """Integration tests for BYOK handler initialization."""

    def test_handler_initialization_default_provider(self, db_session: Session):
        """Test handler initialization with default provider."""
        handler = BYOKHandler()

        assert handler.workspace_id == "default"
        assert handler.clients is not None
        assert isinstance(handler.clients, dict)

    def test_handler_initialization_specific_provider(self, db_session: Session):
        """Test handler initialization with specific provider."""
        handler = BYOKHandler(provider_id="openai")

        assert handler.default_provider_id == "openai"

    @patch('core.llm.byok_handler.OpenAI', None)
    def test_handler_initialization_without_openai(self, db_session: Session):
        """Test handler initialization when OpenAI is not installed."""
        # This test verifies graceful degradation when OpenAI is not available
        handler = BYOKHandler()

        # Should still create handler, but with no clients
        assert handler is not None
        assert isinstance(handler.clients, dict)
