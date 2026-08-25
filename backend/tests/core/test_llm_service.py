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
from unittest.mock import Mock, MagicMock, patch, AsyncMock
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


def _make_vote(winner="winner-obj"):
    """Build a VoteResult-like object for consensus tests."""
    from types import SimpleNamespace
    return SimpleNamespace(
        winner=winner, prompt_hash="hash-abc", sample_count=3, valid_count=3,
        winner_count=2, distinct_hashes=2, agreement_ratio=0.67,
        level="high", winner_hash="wh-1", hash_algo="sha256",
        temperatures=[0.2, 0.3, 0.4],
    )


@pytest.fixture
def personalized_service(mock_handler):
    """LLMService with continuous_learning enabled so personalization runs.

    The db arg makes ``continuous_learning`` non-None; we replace it with a
    Mock whose ``get_personalized_parameters`` returns a tuned temperature.
    """
    cl = Mock()
    cl.get_personalized_parameters.return_value = {"temperature": 0.5}
    with patch("core.llm_service.BYOKHandler", return_value=mock_handler), \
         patch("core.llm_service.ContinuousLearningService", return_value=cl):
        service = LLMService(db=Mock(), workspace_id="ws")
    service.handler = mock_handler
    service.continuous_learning = cl
    return service



class TestUtilitiesAndConsensus:
    """Cover estimate_tokens / estimate_cost / generate_speech and the
    self-consensus dispatch + audit machinery."""

    # --- personalization (the staged-fix region) -------------------------

    @pytest.mark.asyncio
    async def test_generate_applies_personalized_temperature_at_default(
        self, personalized_service, mock_handler
    ):
        """Default temperature (0.7) is overridden by the personalized value."""
        await personalized_service.generate("hi", agent_id="a1", user_id="u1")
        assert mock_handler.generate_response.call_args.kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_generate_keeps_caller_explicit_temperature(
        self, personalized_service, mock_handler
    ):
        """An explicit non-default temperature is NOT overridden by personalization."""
        await personalized_service.generate("hi", temperature=0.9, agent_id="a1")
        assert mock_handler.generate_response.call_args.kwargs["temperature"] == 0.9

    @pytest.mark.asyncio
    async def test_generate_pops_turn_index_avoiding_duplicate_kwarg(
        self, personalized_service, mock_handler
    ):
        """turn_index is popped from kwargs and passed positionally (no dup-key TypeError)."""
        await personalized_service.generate("hi", turn_index=3)
        kwargs = mock_handler.generate_response.call_args.kwargs
        assert kwargs["turn_index"] == 3
        # It must have been consumed from **kwargs (no duplicate).
        assert list(kwargs).count("turn_index") == 1

    @pytest.mark.asyncio
    async def test_structured_response_applies_personalized_temperature(
        self, personalized_service, mock_handler
    ):
        await personalized_service.generate_structured_response(
            "hi", response_model=Mock(), agent_id="a1"
        )
        assert mock_handler.generate_structured_response.call_args.kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_structured_response_forwards_explicit_temperature(
        self, personalized_service, mock_handler
    ):
        await personalized_service.generate_structured_response(
            "hi", response_model=Mock(), agent_id="a1", temperature=0.9
        )
        assert mock_handler.generate_structured_response.call_args.kwargs["temperature"] == 0.9

    # --- generate_structured (self-consistency dispatch + error paths) ---

    @pytest.mark.asyncio
    async def test_generate_structured_unavailable_returns_none(self, llm_service):
        with patch.object(llm_service, "is_available", return_value=False):
            assert await llm_service.generate_structured("p", response_model=Mock()) is None

    @pytest.mark.asyncio
    async def test_generate_structured_self_consistency_dispatch(self, llm_service):
        with patch.object(llm_service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled", return_value=True), \
             patch("core.hallucination_config.is_cascade_routing_enabled", return_value=False), \
             patch.object(llm_service, "_run_self_consistency_vote",
                          AsyncMock(return_value=("WIN", _make_vote()))) as m:
            result = await llm_service.generate_structured(
                "p", response_model=Mock(), enable_self_consistency=True
            )
        assert result == "WIN"
        m.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_structured_handler_exception_returns_none(self, llm_service, mock_handler):
        mock_handler.generate_structured_response = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(llm_service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled", return_value=False), \
             patch("core.hallucination_config.is_cascade_routing_enabled", return_value=False):
            assert await llm_service.generate_structured("p", response_model=Mock()) is None

    # --- estimate_tokens -------------------------------------------------

    def test_estimate_tokens_string(self, llm_service):
        with patch.object(llm_service._token_counter, "count_tokens", return_value=42):
            assert llm_service.estimate_tokens("hello") == 42

    def test_estimate_tokens_message_list(self, llm_service):
        msgs = [{"role": "user", "content": "hi"}]
        with patch.object(llm_service._context_validator, "estimate_request_tokens", return_value=7):
            assert llm_service.estimate_tokens(msgs) == 7

    def test_estimate_tokens_unknown_type_returns_zero(self, llm_service):
        assert llm_service.estimate_tokens(12345) == 0

    # --- estimate_cost ---------------------------------------------------

    def test_estimate_cost_delegates_to_cost_config(self, llm_service):
        with patch("core.cost_config.get_llm_cost", return_value=0.0123) as mocked:
            assert llm_service.estimate_cost(100, 50, "gpt-4o-mini") == 0.0123
            mocked.assert_called_once_with("gpt-4o-mini", 100, 50)

    def test_estimate_cost_fallback_when_cost_config_missing(self, llm_service, monkeypatch):
        """When get_llm_cost can't be imported, the hardcoded fallback runs."""
        import core.cost_config as cc
        # Removing the attribute makes `from core.cost_config import get_llm_cost`
        # raise ImportError, exercising the fallback pricing branch.
        if hasattr(cc, "get_llm_cost"):
            monkeypatch.delattr(cc, "get_llm_cost")
        cost = llm_service.estimate_cost(1_000_000, 1_000_000, "gpt-4o-mini")
        # gpt-4o-mini fallback: (1e6*0.15 + 1e6*0.6)/1e6 = 0.75
        assert cost == 0.75

    def test_estimate_cost_fallback_unknown_model(self, llm_service, monkeypatch):
        import core.cost_config as cc
        if hasattr(cc, "get_llm_cost"):
            monkeypatch.delattr(cc, "get_llm_cost")
        cost = llm_service.estimate_cost(1_000_000, 1_000_000, "mystery-model")
        # Unknown model fallback: (1e6*1.0 + 1e6*2.0)/1e6 = 3.0
        assert cost == 3.0

    # --- generate_speech -------------------------------------------------

    @pytest.mark.asyncio
    async def test_generate_speech_success(self, llm_service, mock_handler):
        fake_response = Mock()
        fake_response.read.return_value = b"audio-bytes"
        fake_client = Mock()
        fake_client.audio.speech.create = AsyncMock(return_value=fake_response)
        mock_handler.async_clients = {"openai": fake_client}
        mock_handler.clients = {}

        with patch.object(llm_service, "get_provider", return_value=Mock(value="openai")):
            result = await llm_service.generate_speech("hello world", voice="alloy")

        assert result == b"audio-bytes"
        fake_client.audio.speech.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_speech_no_client_raises(self, llm_service, mock_handler):
        mock_handler.async_clients = {}
        mock_handler.clients = {}
        with patch.object(llm_service, "get_provider", return_value=Mock(value="openai")):
            with pytest.raises(ValueError, match="No client"):
                await llm_service.generate_speech("hello")

    @pytest.mark.asyncio
    async def test_generate_speech_uses_sync_client_fallback(self, llm_service, mock_handler):
        """When no async client exists, the sync client is used."""
        fake_response = Mock()
        fake_response.read.return_value = b"sync-audio"
        sync_client = Mock()
        sync_client.audio.speech.create = AsyncMock(return_value=fake_response)
        mock_handler.async_clients = {}
        mock_handler.clients = {"openai": sync_client}

        with patch.object(llm_service, "get_provider", return_value=Mock(value="openai")):
            result = await llm_service.generate_speech("hi")
        assert result == b"sync-audio"

    # --- generate_structured_with_consensus ------------------------------

    @pytest.mark.asyncio
    async def test_consensus_returns_none_none_when_unavailable(self, llm_service):
        with patch.object(llm_service, "is_available", return_value=False):
            winner, vote = await llm_service.generate_structured_with_consensus(
                prompt="p", response_model=Mock()
            )
        assert winner is None and vote is None

    @pytest.mark.asyncio
    async def test_consensus_self_consistency_disabled_single_sample(self, llm_service, mock_handler):
        """When the flag is off, a single structured sample is returned with no vote."""
        sentinel = Mock()
        mock_handler.generate_structured_response = AsyncMock(return_value=sentinel)
        with patch.object(llm_service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled", return_value=False), \
             patch("core.hallucination_config.is_cascade_routing_enabled", return_value=False):
            result, vote = await llm_service.generate_structured_with_consensus(
                prompt="p", response_model=Mock()
            )
        assert result is sentinel
        assert vote is None

    @pytest.mark.asyncio
    async def test_consensus_dispatches_to_voter_when_enabled(self, llm_service):
        """When the flag is on, the vote path runs and returns (winner, vote)."""
        vote = _make_vote(winner="WIN")
        with patch.object(llm_service, "is_available", return_value=True), \
             patch("core.hallucination_config.is_self_consistency_enabled", return_value=True), \
             patch("core.hallucination_config.is_cascade_routing_enabled", return_value=True), \
             patch.object(llm_service, "_run_self_consistency_vote", AsyncMock(return_value=(vote.winner, vote))) as m:
            winner, returned_vote = await llm_service.generate_structured_with_consensus(
                prompt="p", response_model=Mock()
            )
        assert winner == "WIN"
        assert returned_vote is vote
        m.assert_awaited_once()

    # --- _run_self_consistency_vote --------------------------------------

    @pytest.mark.asyncio
    async def test_run_vote_success_persists_audit(self, llm_service):
        vote = _make_vote(winner="WIN")
        voter = Mock()
        voter.vote_with_consensus = AsyncMock(return_value=vote)
        with patch("core.llm.self_consistency_voter.SelfConsistencyVoter", return_value=voter), \
             patch.object(llm_service, "_write_self_consistency_audit") as mock_audit:
            winner, returned_vote = await llm_service._run_self_consistency_vote(
                prompt="p", response_model=Mock(), system_instruction="s", temperature=0.2,
                task_type=None, agent_id="a1", image_payload=None,
                cascade=True, session_id="s1", user_id="u1",
            )
        assert winner == "WIN"
        assert returned_vote is vote
        mock_audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_vote_voter_failure_returns_none(self, llm_service):
        with patch("core.llm.self_consistency_voter.SelfConsistencyVoter",
                   side_effect=RuntimeError("voter boom")):
            winner, vote = await llm_service._run_self_consistency_vote(
                prompt="p", response_model=Mock(), system_instruction="s", temperature=0.2,
                task_type=None, agent_id=None, image_payload=None,
                cascade=False, session_id=None, user_id=None,
            )
        assert winner is None and vote is None

    # --- _write_self_consistency_audit -----------------------------------

    def test_audit_write_uses_caller_db_when_provided(self, mock_handler):
        """When self._db is provided, the row is add+committed on it (not closed)."""
        db = Mock()
        with patch("core.llm_service.BYOKHandler", return_value=mock_handler):
            from core.llm_service import LLMService
            svc = LLMService(db=db, workspace_id="ws", tenant_id="tenant-1")
        svc._write_self_consistency_audit(
            vote=_make_vote(), agent_id="a1", session_id="s1", user_id="u1",
            response_model=Mock(__name__="MyModel"),
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_audit_write_caller_db_commit_failure_rolls_back(self, mock_handler):
        db = Mock()
        db.commit.side_effect = RuntimeError("commit failed")
        with patch("core.llm_service.BYOKHandler", return_value=mock_handler):
            from core.llm_service import LLMService
            svc = LLMService(db=db)
        svc._write_self_consistency_audit(
            vote=_make_vote(), agent_id=None, session_id=None, user_id=None,
            response_model=Mock(__name__="MyModel"),
        )
        db.rollback.assert_called_once()

    def test_audit_write_opens_own_session_when_no_caller_db(self, mock_handler):
        """With no caller db, get_db_session() is used."""
        own_db = Mock()
        ctx = MagicMock()
        ctx.__enter__.return_value = own_db
        ctx.__exit__.return_value = False
        with patch("core.llm_service.BYOKHandler", return_value=mock_handler):
            from core.llm_service import LLMService
            svc = LLMService(db=None)  # no caller session
        with patch("core.database.get_db_session", return_value=ctx) as mock_get:
            svc._write_self_consistency_audit(
                vote=_make_vote(), agent_id=None, session_id=None, user_id=None,
                response_model=Mock(__name__="MyModel"),
            )
        mock_get.assert_called_once()
        own_db.add.assert_called_once()
        own_db.commit.assert_called_once()

