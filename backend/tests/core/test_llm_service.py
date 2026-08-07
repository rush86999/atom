"""
Unit Tests for LLM Service

Tests LLMService wrapper around BYOKHandler:
- LLMService class initialization (workspace/tenant defaults, handler injection)
- generate(prompt, max_tokens, temperature) - Text generation
- generate_completion(messages, max_tokens, temperature) - Chat generation
- is_available() - Service availability check
- Provider selection seams (AwaitableResult, handler setter, embedding delegation)

Target Coverage: 90%+ (thin wrapper around BYOKHandler)
Target Branch Coverage: 60%+
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict

from core.llm_service import LLMService
from core.llm.byok_handler import AwaitableResult


@pytest.fixture
def mock_handler():
    """Mock BYOKHandler."""
    handler = Mock()
    handler.clients = {"openai": Mock()}
    handler.generate_response = AsyncMock(return_value="Generated response")
    handler.generate_structured_response = AsyncMock(return_value=None)
    handler.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    handler.generate_embeddings_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    handler.get_optimal_provider = Mock(
        return_value=AwaitableResult(("anthropic", "claude-3-5-sonnet"))
    )
    handler._last_used_model = "gpt-4o"
    handler._last_used_provider = "openai"
    return handler


@pytest.fixture
def llm_service(mock_handler):
    """Create LLMService with mocked handler."""
    with patch("core.llm_service.BYOKHandler", return_value=mock_handler):
        service = LLMService(workspace_id="test")
        service.handler = mock_handler
        return service


class TestLLMServiceInitialization:
    """Tests for LLMService initialization."""

    def test_init_default_values(self, mock_handler):
        """Test LLMService initializes with defaults."""
        with patch("core.llm_service.BYOKHandler", return_value=mock_handler):
            service = LLMService()

        assert service.workspace_id == "default"
        assert service.tenant_id == "default"
        assert service.handler is mock_handler
        assert service.continuous_learning is None

    def test_init_with_custom_workspace(self, mock_handler):
        """Test LLMService with custom workspace."""
        with patch("core.llm_service.BYOKHandler", return_value=mock_handler):
            service = LLMService(workspace_id="ws-1")

        assert service.workspace_id == "ws-1"
        assert service.handler is mock_handler

    def test_init_with_tenant(self, mock_handler):
        """Test LLMService with tenant identifier."""
        with patch("core.llm_service.BYOKHandler", return_value=mock_handler):
            service = LLMService(tenant_id="tenant-1")

        assert service.tenant_id == "tenant-1"
        assert service.handler is mock_handler

    def test_handler_property_alias(self, llm_service, mock_handler):
        """Test handler property exposes the injected handler."""
        assert llm_service.handler is mock_handler

    def test_handler_setter_injection(self, mock_handler):
        """Test handler setter allows injecting a mock handler."""
        with patch("core.llm_service.BYOKHandler", return_value=mock_handler):
            service = LLMService()

        replacement = Mock()
        service.handler = replacement
        assert service.handler is replacement


class TestGenerate:
    """Tests for text generation."""

    @pytest.mark.asyncio
    async def test_generate_default_params(self, llm_service, mock_handler):
        """Test generate with default parameters."""
        result = await llm_service.generate("Hello, world!")

        assert result == "Generated response"
        mock_handler.generate_response.assert_called_once()
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["prompt"] == "Hello, world!"
        assert call_kwargs["system_instruction"] == "You are a helpful assistant."
        assert call_kwargs["model_type"] == "auto"
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["turn_index"] == 0

    @pytest.mark.asyncio
    async def test_generate_with_custom_max_tokens(self, llm_service, mock_handler):
        """Test generate with custom max_tokens."""
        result = await llm_service.generate("Test prompt", max_tokens=500)

        assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_generate_with_custom_temperature(self, llm_service, mock_handler):
        """Test generate with custom temperature."""
        result = await llm_service.generate("Test prompt", temperature=0.5)

        assert result == "Generated response"
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_generate_with_all_params(self, llm_service, mock_handler):
        """Test generate with all parameters."""
        result = await llm_service.generate(
            prompt="Test prompt",
            max_tokens=1000,
            temperature=0.7,
            top_p=0.9,
            frequency_penalty=0.5
        )

        assert result == "Generated response"
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["top_p"] == 0.9
        assert call_kwargs["frequency_penalty"] == 0.5

    @pytest.mark.asyncio
    async def test_generate_with_empty_prompt(self, llm_service, mock_handler):
        """Test generate with empty prompt."""
        result = await llm_service.generate("")

        assert result == "Generated response"
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["prompt"] == ""

    @pytest.mark.asyncio
    async def test_generate_with_long_prompt(self, llm_service, mock_handler):
        """Test generate with long prompt."""
        long_prompt = "Test " * 1000
        result = await llm_service.generate(long_prompt)

        assert result == "Generated response"
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["prompt"] == long_prompt

    @pytest.mark.asyncio
    async def test_generate_return_type(self, llm_service, mock_handler):
        """Test generate returns string."""
        result = await llm_service.generate("Test")

        assert isinstance(result, str)


class TestGenerateCompletion:
    """Tests for chat-style generation with message history."""

    @pytest.mark.asyncio
    async def test_generate_with_history_default_params(self, llm_service, mock_handler):
        """Test generate_completion with defaults."""
        messages = [
            {"role": "user", "content": "Hello"}
        ]

        result = await llm_service.generate_completion(messages)

        assert result["success"] is True
        assert result["content"] == "Generated response"
        assert result["text"] == "Generated response"
        assert result["model"] == "gpt-4o"
        assert result["provider"] == "openai"
        assert "usage" in result
        mock_handler.generate_response.assert_called_once()
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["prompt"] == "Hello"
        assert call_kwargs["model_type"] == "auto"

    @pytest.mark.asyncio
    async def test_generate_with_history_conversation(self, llm_service, mock_handler):
        """Test generate_completion with conversation."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]

        result = await llm_service.generate_completion(messages)

        assert result["content"] == "Generated response"
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["prompt"] == "How are you?"

    @pytest.mark.asyncio
    async def test_generate_with_history_custom_max_tokens(self, llm_service):
        """Test generate_completion with custom max_tokens."""
        messages = [{"role": "user", "content": "Test"}]

        result = await llm_service.generate_completion(messages, max_tokens=100)

        assert result["success"] is True
        assert result["content"] == "Generated response"

    @pytest.mark.asyncio
    async def test_generate_with_history_custom_temperature(self, llm_service, mock_handler):
        """Test generate_completion with custom temperature."""
        messages = [{"role": "user", "content": "Test"}]

        result = await llm_service.generate_completion(messages, temperature=0.3)

        assert result["content"] == "Generated response"
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_generate_with_history_all_params(self, llm_service, mock_handler):
        """Test generate_completion with all parameters."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"}
        ]

        result = await llm_service.generate_completion(
            messages=messages,
            max_tokens=500,
            temperature=0.8,
            top_p=0.95
        )

        assert result["content"] == "Generated response"
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["system_instruction"] == "You are helpful."
        assert call_kwargs["prompt"] == "Hello"

    @pytest.mark.asyncio
    async def test_generate_with_history_empty_messages(self, llm_service, mock_handler):
        """Test generate_completion with empty messages."""
        result = await llm_service.generate_completion([])

        assert result["success"] is True
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["prompt"] == ""
        assert call_kwargs["system_instruction"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_generate_with_history_single_message(self, llm_service):
        """Test generate_completion with single message."""
        messages = [{"role": "user", "content": "Test"}]

        result = await llm_service.generate_completion(messages)

        assert result["content"] == "Generated response"

    @pytest.mark.asyncio
    async def test_generate_with_history_many_messages(self, llm_service, mock_handler):
        """Test generate_completion with many messages."""
        messages = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(100)
        ]

        result = await llm_service.generate_completion(messages)

        assert result["content"] == "Generated response"
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["prompt"] == "Message 99"

    @pytest.mark.asyncio
    async def test_generate_with_history_return_type(self, llm_service):
        """Test generate_completion returns dict."""
        messages = [{"role": "user", "content": "Test"}]

        result = await llm_service.generate_completion(messages)

        assert isinstance(result, dict)
        assert result["success"] is True
        assert isinstance(result["content"], str)


class TestIsAvailable:
    """Tests for service availability check."""

    def test_is_available_returns_false(self, mock_handler):
        """Test is_available returns False when no clients."""
        with patch("core.llm_service.BYOKHandler", return_value=mock_handler):
            service = LLMService()
        service.handler.clients = {}

        available = service.is_available()

        assert available is False

    def test_is_available_with_custom_model(self, llm_service):
        """Test is_available returns True when handler has clients."""
        available = llm_service.is_available()

        assert available is True

    def test_is_available_with_api_key(self, llm_service, mock_handler):
        """Test is_available reflects handler client population."""
        llm_service.handler.clients = {"openai": Mock(), "anthropic": Mock()}

        assert llm_service.is_available() is True

        llm_service.handler.clients = {}

        assert llm_service.is_available() is False

    def test_is_available_multiple_calls(self, llm_service):
        """Test is_available returns same result on multiple calls."""
        result1 = llm_service.is_available()
        result2 = llm_service.is_available()
        result3 = llm_service.is_available()

        assert result1 is True
        assert result2 is True
        assert result3 is True

    def test_is_available_return_type(self, llm_service):
        """Test is_available returns boolean."""
        available = llm_service.is_available()

        assert isinstance(available, bool)
        assert available is True


class TestLLMServiceIntegration:
    """Integration tests for LLMService."""

    @pytest.mark.asyncio
    async def test_complete_workflow_generate_then_history(self, llm_service, mock_handler):
        """Test complete workflow: generate, then generate_completion."""
        result1 = await llm_service.generate("Hello")
        assert result1 == "Generated response"

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": result1}
        ]
        result2 = await llm_service.generate_completion(messages)
        assert result2["content"] == "Generated response"

        assert mock_handler.generate_response.call_count == 2

    @pytest.mark.asyncio
    async def test_check_availability_before_generate(self, llm_service):
        """Test checking availability before generation."""
        available = llm_service.is_available()
        assert available is True

        result = await llm_service.generate("Test")
        assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_multiple_generations_same_service(self, llm_service, mock_handler):
        """Test multiple generations with same service instance."""
        result1 = await llm_service.generate("Prompt 1")
        result2 = await llm_service.generate("Prompt 2")
        result3 = await llm_service.generate("Prompt 3")

        assert result1 == "Generated response"
        assert result2 == "Generated response"
        assert result3 == "Generated response"
        assert mock_handler.generate_response.call_count == 3

    @pytest.mark.asyncio
    async def test_service_state_persistence(self, llm_service):
        """Test service state persists across operations."""
        assert llm_service.workspace_id == "test"

        await llm_service.generate("Test")
        await llm_service.generate_completion([{"role": "user", "content": "Test"}])
        llm_service.is_available()

        assert llm_service.workspace_id == "test"
        assert llm_service.tenant_id == "default"


class TestLLMServiceEdgeCases:
    """Edge case tests for LLMService."""

    @pytest.mark.asyncio
    async def test_generate_with_none_prompt(self, llm_service, mock_handler):
        """Test generate with None prompt (edge case)."""
        result = await llm_service.generate(None)  # type: ignore

        assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_generate_with_special_characters(self, llm_service):
        """Test generate with special characters in prompt."""
        result = await llm_service.generate("Test \n\t\r\x00")

        assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_generate_with_unicode(self, llm_service):
        """Test generate with unicode characters."""
        result = await llm_service.generate("Hello 世界 🌍")

        assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_generate_with_zero_max_tokens(self, llm_service):
        """Test generate with zero max_tokens."""
        result = await llm_service.generate("Test", max_tokens=0)

        assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_generate_with_negative_temperature(self, llm_service, mock_handler):
        """Test generate with negative temperature."""
        result = await llm_service.generate("Test", temperature=-0.5)

        assert result == "Generated response"
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["temperature"] == -0.5

    @pytest.mark.asyncio
    async def test_generate_with_high_temperature(self, llm_service, mock_handler):
        """Test generate with temperature > 1.0."""
        result = await llm_service.generate("Test", temperature=2.0)

        assert result == "Generated response"
        call_kwargs = mock_handler.generate_response.call_args.kwargs
        assert call_kwargs["temperature"] == 2.0


class TestLLMServiceSeams:
    """Tests for the AwaitableResult / handler setter / embedding seams."""

    def test_get_optimal_provider_returns_awaitable_result(self, llm_service, mock_handler):
        """Test get_optimal_provider wraps result in AwaitableResult."""
        result = llm_service.get_optimal_provider(complexity="simple")

        assert isinstance(result, AwaitableResult)
        provider, model = result
        assert provider == "anthropic"
        assert model == "claude-3-5-sonnet"

    @pytest.mark.asyncio
    async def test_get_optimal_provider_is_awaitable(self, llm_service):
        """Test get_optimal_provider result can be awaited."""
        result = llm_service.get_optimal_provider(complexity="moderate")

        provider, model = await result

        assert provider == "anthropic"
        assert model == "claude-3-5-sonnet"

    @pytest.mark.asyncio
    async def test_generate_embedding_delegates_to_handler(self, llm_service, mock_handler):
        """Test generate_embedding delegates to handler.generate_embedding."""
        embedding = await llm_service.generate_embedding(
            "text to embed", model="text-embedding-3-small"
        )

        assert embedding == [0.1, 0.2, 0.3]
        mock_handler.generate_embedding.assert_awaited_once()
        call_kwargs = mock_handler.generate_embedding.call_args.kwargs
        assert call_kwargs["text"] == "text to embed"
        assert call_kwargs["model"] == "text-embedding-3-small"
        assert call_kwargs["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_generate_embedding_cohere_provider(self, llm_service, mock_handler):
        """Test generate_embedding maps embed-english models to cohere."""
        await llm_service.generate_embedding(
            "text", model="embed-english-v3.0"
        )

        call_kwargs = mock_handler.generate_embedding.call_args.kwargs
        assert call_kwargs["provider"] == "cohere"
