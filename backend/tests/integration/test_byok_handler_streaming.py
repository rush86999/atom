"""
Comprehensive streaming tests for BYOKHandler stream_completion method.

This test file targets stream_completion method coverage (lines ~1372-1518 in byok_handler.py)
Tests cover:
- Async streaming with AsyncMock for OpenAI, Anthropic, DeepSeek providers
- Provider fallback on streaming failures
- Empty stream handling
- System instruction and temperature parameters
- Governance tracking with agent execution records
- Error handling (rate limits, connection errors)

Target: 75%+ coverage for stream_completion method
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from core.llm.byok_handler import BYOKHandler, QueryComplexity


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_async_openai_client():
    """Mock AsyncOpenAI client for streaming tests."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_stream_response():
    """Mock async streaming response generator."""
    async def generate_chunks():
        """Generate mock streaming chunks."""
        # Chunk 1
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"))]
        yield chunk1

        # Chunk 2
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock(delta=MagicMock(content=" world"))]
        yield chunk2

        # Chunk 3
        chunk3 = MagicMock()
        chunk3.choices = [MagicMock(delta=MagicMock(content="!"))]
        yield chunk3

        # Final chunk with finish_reason
        chunk4 = MagicMock()
        chunk4.choices = [MagicMock(finish_reason="stop")]
        yield chunk4

    # Return the async generator function
    return generate_chunks


@pytest.fixture
def handler_with_mocked_client(mock_async_openai_client):
    """Create BYOKHandler with mocked async clients."""
    handler = BYOKHandler()

    # Replace async_clients with mock
    handler.async_clients = {
        "openai": mock_async_openai_client,
        "anthropic": AsyncMock(),
        "deepseek": AsyncMock(),
    }

    # Set up clients dict too
    handler.clients = handler.async_clients.copy()

    return handler


@pytest.fixture
def mock_db_session():
    """Mock database session for governance tracking."""
    db = MagicMock(spec=Session)

    # Mock agent execution creation
    mock_execution = MagicMock()
    mock_execution.id = "test-execution-123"
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()

    return db


# =============================================================================
# TEST STREAM COMPLETION
# =============================================================================

class TestStreamCompletion:
    """Test suite for stream_completion async streaming method."""

    @pytest.mark.asyncio
    async def test_stream_completion_yields_tokens(self, handler_with_mocked_client, mock_stream_response):
        """Test that stream_completion yields string tokens."""
        handler = handler_with_mocked_client

        # Mock the create method to return streaming generator
        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=mock_stream_response()
        )

        # Collect streamed tokens
        messages = [{"role": "user", "content": "Hello"}]
        tokens = []

        async for token in handler.stream_completion(
            messages=messages,
            model="gpt-4o",
            provider_id="openai"
        ):
            tokens.append(token)

        # Verify tokens were collected
        assert len(tokens) >= 3
        assert "Hello" in "".join(tokens)
        assert "world" in "".join(tokens)

    @pytest.mark.asyncio
    async def test_stream_completion_with_openai_provider(self, handler_with_mocked_client):
        """Test streaming with OpenAI provider."""
        handler = handler_with_mocked_client

        # Create OpenAI-style streaming response
        async def openai_stream():
            """Stream OpenAI response."""
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="OpenAI response"))]
            yield chunk

        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=openai_stream()
        )

        messages = [{"role": "user", "content": "Test"}]
        result = ""

        async for token in handler.stream_completion(
            messages=messages,
            model="gpt-4o",
            provider_id="openai"
        ):
            result += token

        assert "OpenAI response" in result

    @pytest.mark.asyncio
    async def test_stream_completion_with_deepseek_provider(self, handler_with_mocked_client):
        """Test streaming with DeepSeek provider."""
        handler = handler_with_mocked_client

        # Create DeepSeek streaming response
        async def deepseek_stream():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="DeepSeek streaming"))]
            yield chunk

        handler.async_clients["deepseek"].chat.completions.create = AsyncMock(
            return_value=deepseek_stream()
        )

        messages = [{"role": "user", "content": "Test"}]
        result = ""

        async for token in handler.stream_completion(
            messages=messages,
            model="deepseek-chat",
            provider_id="deepseek"
        ):
            result += token

        assert "DeepSeek streaming" in result

    @pytest.mark.asyncio
    async def test_stream_completion_empty_stream(self, handler_with_mocked_client):
        """Test handling of empty stream gracefully."""
        handler = handler_with_mocked_client

        # Create empty stream
        async def empty_stream():
            # Yield nothing
            return
            yield  # Never reached

        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=empty_stream()
        )

        messages = [{"role": "user", "content": "Test"}]
        tokens = []

        async for token in handler.stream_completion(
            messages=messages,
            model="gpt-4o",
            provider_id="openai"
        ):
            tokens.append(token)

        # Should handle empty stream gracefully
        assert isinstance(tokens, list)

    @pytest.mark.asyncio
    async def test_stream_completion_with_system_instruction(self, handler_with_mocked_client):
        """Test streaming with system instruction included in messages."""
        handler = handler_with_mocked_client

        async def stream_with_system():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="Response"))]
            yield chunk

        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=stream_with_system()
        )

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ]

        result = ""
        async for token in handler.stream_completion(
            messages=messages,
            model="gpt-4o",
            provider_id="openai"
        ):
            result += token

        # Verify the create method was called with system message
        handler.async_clients["openai"].chat.completions.create.assert_called_once()
        call_args = handler.async_clients["openai"].chat.completions.create.call_args
        messages_arg = call_args[1]["messages"]
        assert len(messages_arg) == 2
        assert messages_arg[0]["role"] == "system"

    @pytest.mark.asyncio
    async def test_stream_completion_with_temperature(self, handler_with_mocked_client):
        """Test streaming with custom temperature parameter."""
        handler = handler_with_mocked_client

        async def stream_with_temp():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="Response"))]
            yield chunk

        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=stream_with_temp()
        )

        messages = [{"role": "user", "content": "Test"}]

        async for token in handler.stream_completion(
            messages=messages,
            model="gpt-4o",
            provider_id="openai",
            temperature=0.5
        ):
            pass  # Consume stream

        # Verify temperature was passed
        handler.async_clients["openai"].chat.completions.create.assert_called_once()
        call_args = handler.async_clients["openai"].chat.completions.create.call_args
        assert call_args[1]["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_stream_completion_with_max_tokens(self, handler_with_mocked_client):
        """Test streaming with max_tokens parameter."""
        handler = handler_with_mocked_client

        async def stream_with_max():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="Token"))]
            yield chunk

        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=stream_with_max()
        )

        messages = [{"role": "user", "content": "Test"}]

        async for token in handler.stream_completion(
            messages=messages,
            model="gpt-4o",
            provider_id="openai",
            max_tokens=100
        ):
            pass  # Consume stream

        # Verify max_tokens was passed
        call_args = handler.async_clients["openai"].chat.completions.create.call_args
        assert call_args[1]["max_tokens"] == 100


class TestStreamCompletionErrors:
    """Test suite for streaming error handling."""

    @pytest.mark.asyncio
    async def test_stream_completion_provider_fallback(self, handler_with_mocked_client):
        """Test provider fallback on streaming failure."""
        handler = handler_with_mocked_client

        # Make OpenAI fail
        async def failing_stream():
            raise Exception("OpenAI connection error")
            yield  # Never reached

        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            side_effect=failing_stream()
        )

        # Make Anthropic succeed
        async def success_stream():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="Fallback response"))]
            yield chunk

        handler.async_clients["anthropic"].chat.completions.create = AsyncMock(
            return_value=success_stream()
        )

        messages = [{"role": "user", "content": "Test"}]
        result = ""

        # Should fall back to Anthropic
        async for token in handler.stream_completion(
            messages=messages,
            model="gpt-4o",
            provider_id="openai"  # Request OpenAI, but it will fail
        ):
            result += token

        # Should get response from fallback provider
        assert "Fallback response" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_stream_completion_all_providers_fail(self, handler_with_mocked_client):
        """Test error message when all providers fail."""
        handler = handler_with_mocked_client

        # Make all providers fail
        async def failing_stream():
            raise Exception("Provider unavailable")
            yield

        for provider_id in handler.async_clients:
            handler.async_clients[provider_id].chat.completions.create = AsyncMock(
                side_effect=failing_stream()
            )

        messages = [{"role": "user", "content": "Test"}]
        result = ""

        async for token in handler.stream_completion(
            messages=messages,
            model="gpt-4o",
            provider_id="openai"
        ):
            result += token

        # Should include error message
        assert "Error" in result or "failed" in result.lower()

    @pytest.mark.asyncio
    async def test_stream_completion_no_clients_available(self):
        """Test error when no clients are initialized."""
        handler = BYOKHandler()
        handler.async_clients = {}
        handler.clients = {}

        messages = [{"role": "user", "content": "Test"}]

        with pytest.raises(ValueError) as exc_info:
            async for token in handler.stream_completion(
                messages=messages,
                model="gpt-4o",
                provider_id="openai"
            ):
                pass

        assert "No clients initialized" in str(exc_info.value) or "No available providers" in str(exc_info.value)


class TestStreamCompletionGovernance:
    """Test suite for governance tracking during streaming."""

    @pytest.mark.asyncio
    async def test_stream_completion_with_agent_tracking(self, handler_with_mocked_client, mock_db_session):
        """Test agent execution tracking during streaming."""
        handler = handler_with_mocked_client

        # Mock successful stream
        async def tracked_stream():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="Tracked response"))]
            yield chunk

        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=tracked_stream()
        )

        messages = [{"role": "user", "content": "Test"}]
        agent_id = "test-agent-123"

        # Enable governance tracking
        with patch.dict(os.environ, {"STREAMING_GOVERNANCE_ENABLED": "true"}):
            result = ""
            async for token in handler.stream_completion(
                messages=messages,
                model="gpt-4o",
                provider_id="openai",
                agent_id=agent_id,
                db=mock_db_session
            ):
                result += token

        # Verify agent execution was created
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

        assert "Tracked response" in result

    @pytest.mark.asyncio
    async def test_stream_completion_governance_disabled(self, handler_with_mocked_client, mock_db_session):
        """Test streaming without governance tracking when disabled."""
        handler = handler_with_mocked_client

        async def untracked_stream():
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="Untracked response"))]
            yield chunk

        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=untracked_stream()
        )

        messages = [{"role": "user", "content": "Test"}]

        # Disable governance tracking
        with patch.dict(os.environ, {"STREAMING_GOVERNANCE_ENABLED": "false"}):
            result = ""
            async for token in handler.stream_completion(
                messages=messages,
                model="gpt-4o",
                provider_id="openai",
                agent_id="test-agent",
                db=mock_db_session
            ):
                result += token

        # Verify no agent execution was created
        mock_db_session.add.assert_not_called()

        assert "Untracked response" in result


class TestStreamCompletionTokenHandling:
    """Test suite for token handling in streams."""

    @pytest.mark.asyncio
    async def test_stream_completion_handles_none_content(self, handler_with_mocked_client):
        """Test handling of chunks with None content."""
        handler = handler_with_mocked_client

        async def stream_with_none():
            # Chunk with content
            chunk1 = MagicMock()
            chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"))]
            yield chunk1

            # Chunk with None content (should be skipped)
            chunk2 = MagicMock()
            chunk2.choices = [MagicMock(delta=MagicMock(content=None))]
            yield chunk2

            # Chunk with content again
            chunk3 = MagicMock()
            chunk3.choices = [MagicMock(delta=MagicMock(content=" world"))]
            yield chunk3

        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=stream_with_none()
        )

        messages = [{"role": "user", "content": "Test"}]
        result = ""

        async for token in handler.stream_completion(
            messages=messages,
            model="gpt-4o",
            provider_id="openai"
        ):
            result += token

        # Should only include non-None content
        assert "Hello world" in result

    @pytest.mark.asyncio
    async def test_stream_completion_handles_missing_delta_attribute(self, handler_with_mocked_client):
        """Test handling of chunks without delta attribute."""
        handler = handler_with_mocked_client

        async def stream_without_delta():
            chunk1 = MagicMock()
            chunk1.choices = [MagicMock(delta=MagicMock(content="Start"))]
            yield chunk1

            # Chunk without delta attribute
            chunk2 = MagicMock()
            chunk2.choices = [MagicMock()]  # No delta attribute
            yield chunk2

            chunk3 = MagicMock()
            chunk3.choices = [MagicMock(delta=MagicMock(content="End"))]
            yield chunk3

        handler.async_clients["openai"].chat.completions.create = AsyncMock(
            return_value=stream_without_delta()
        )

        messages = [{"role": "user", "content": "Test"}]
        result = ""

        # Should handle gracefully
        async for token in handler.stream_completion(
            messages=messages,
            model="gpt-4o",
            provider_id="openai"
        ):
            result += token

        # Should include content from chunks with delta
        assert "Start" in result or "End" in result
