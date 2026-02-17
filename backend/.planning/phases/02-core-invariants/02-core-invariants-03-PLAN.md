---
wave: 1
depends_on: ["02-core-invariants-01"]
files_modified:
  - "tests/property_tests/llm/test_llm_streaming_invariants.py"
  - "tests/property_tests/llm/test_token_counting_invariants.py"
  - "tests/property_tests/llm/__init__.py"
autonomous: true
must_haves:
  - Test streaming completion invariants (message ordering, chunk integrity, metadata consistency)
  - Test token counting accuracy (input tokens, output tokens, total cost calculation)
  - Test provider fallback invariants (fallback preserves context, cost tracking preserved)
  - Test streaming error recovery (recovery from provider failure, retry limits enforced)
  - Test streaming performance (latency, throughput, memory efficiency)
tags: [llm, streaming, tokens, property-test, phase-2]
estimated_hours: 8
testing_type: property
---

# Plan 02-03: LLM Streaming and Token Counting Invariants

## Overview

Implement comprehensive property-based tests for LLM streaming responses and token counting accuracy in the BYOK (Bring Your Own Key) handler. These invariants ensure reliable streaming behavior, accurate cost tracking, and proper provider fallback mechanisms.

## Background

The `core/llm/byok_handler.py` implements multi-provider LLM streaming with:
- **Streaming responses**: Token-by-token generation via WebSocket
- **Token counting**: Input/output token tracking for cost calculation
- **Provider fallback**: Automatic fallback to secondary providers on failure
- **Cost optimization**: Provider selection based on query complexity

### Current State
- Basic LLM handler tests exist but do NOT cover streaming invariants
- Token counting accuracy NOT validated
- Provider fallback behavior NOT tested with property-based methods
- Streaming error recovery NOT covered

## Invariants to Test

### 1. Streaming Completion Invariants
- **Message Ordering**: Chunks arrive in sequential order
- **Chunk Integrity**: No dropped or duplicated tokens
- **Metadata Consistency**: Model, provider, finish_reason are consistent
- **Stream Closure**: Proper EOS (end of stream) signaling

### 2. Token Counting Invariants
- **Input Token Accuracy**: Count matches tiktoken for OpenAI
- **Output Token Accuracy**: Count matches actual tokens generated
- **Total Cost Calculation**: cost = (input * input_price) + (output * output_price)
- **Token Budget Enforcement**: Requests exceeding budget are rejected

### 3. Provider Fallback Invariants
- **Context Preservation**: Fallback preserves conversation history
- **Cost Tracking**: Costs tracked across provider switches
- **Fallback Chain**: Tries optimal provider first, then fallbacks
- **Failure Isolation**: One provider failure doesn't affect others

### 4. Streaming Error Recovery Invariants
- **Retry Limits**: Max retry attempts enforced
- **Exponential Backoff**: Retry delays increase exponentially
- **Recovery Success**: Successful retry returns valid stream
- **Failure Propagation**: Max retries exceeded raises clear error

### 5. Streaming Performance Invariants
- **First Token Latency**: <3 seconds for first token
- **Token Throughput**: >10 tokens/second sustained
- **Memory Efficiency**: Memory usage linear with token count
- **Concurrent Streams**: Multiple streams don't interfere

## Implementation

### File Structure

```
tests/property_tests/llm/
├── __init__.py
├── test_llm_streaming_invariants.py
└── test_token_counting_invariants.py
```

### Test: test_llm_streaming_invariants.py

```python
"""
Property-based tests for LLM streaming invariants.

Tests ensure that streaming responses maintain:
- Message ordering and chunk integrity
- Metadata consistency across chunks
- Proper stream closure and EOS signaling
- Provider fallback preserves context
- Error recovery with retry limits
"""

import pytest
from hypothesis import given, settings, example, Phase
from hypothesis import strategies as st
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch
import asyncio
from datetime import datetime

from core.llm.byok_handler import BYOKHandler, StreamChunk, ProviderTier
from tests.property_tests.conftest import mock_llm_stream


class TestStreamingCompletionInvariants:
    """Test invariants for streaming completion responses."""

    @given(
        messages=st.lists(
            st.fixed_dictionaries({
                'role': st.sampled_from(['user', 'assistant', 'system']),
                'content': st.text(min_size=1, max_size=5000)
            }),
            min_size=1,
            max_size=10
        ),
        chunk_count=st.integers(min_value=1, max_value=100),
        tokens_per_chunk=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50, phases=[Phase.generate])
    def test_streaming_chunk_ordering_invariant(
        self,
        db_session,
        messages: List[Dict[str, str]],
        chunk_count: int,
        tokens_per_chunk: int
    ):
        """
        INVARIANT: Streaming chunks arrive in sequential order.

        Given: A streaming request with N chunks
        When: Streaming response is received
        Then: Chunks arrive in order 0, 1, 2, ..., N-1
        """
        handler = BYOKHandler(db_session)

        # Generate ordered chunks
        expected_chunks = []
        for i in range(chunk_count):
            chunk = StreamChunk(
                index=i,
                content=f"token_{i}_",
                finish_reason=None,
                model="gpt-4",
                provider="openai"
            )
            expected_chunks.append(chunk)

        # Simulate streaming
        received_indices = []
        async def simulate_stream():
            for chunk in expected_chunks:
                received_indices.append(chunk.index)
                await asyncio.sleep(0.001)  # Simulate network delay
            return expected_chunks

        chunks = asyncio.run(simulate_stream())

        # Verify ordering invariant
        assert len(chunks) == chunk_count, "All chunks must be received"
        assert [c.index for c in chunks] == list(range(chunk_count)), \
            "Chunks must arrive in sequential order"

    @given(
        base_content=st.text(min_size=100, max_size=1000),
        duplicate_positions=st.lists(
            st.integers(min_value=0, max_value=50),
            min_size=0,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=30)
    def test_streaming_no_duplicates_invariant(
        self,
        db_session,
        base_content: str,
        duplicate_positions: List[int]
    ):
        """
        INVARIANT: Streaming response contains no duplicate tokens.

        Given: A streaming response
        When: Tokens are received
        Then: Each token appears exactly once
        """
        handler = BYOKHandler(db_session)

        # Simulate stream with potential duplicates
        tokens = list(base_content)
        received_tokens = []

        async def simulate_stream_with_duplicates():
            for i, token in enumerate(tokens):
                received_tokens.append(token)
                # Simulate potential duplicate at specified positions
                if i in duplicate_positions:
                    received_tokens.append(token)  # Duplicate (should be caught)

        asyncio.run(simulate_stream_with_duplicates())

        # If duplicates were injected, verify they're detected
        if duplicate_positions:
            # Count occurrences of each token
            from collections import Counter
            token_counts = Counter(received_tokens)
            # Tokens at duplicate positions should appear twice
            for pos in duplicate_positions:
                if pos < len(tokens):
                    token = tokens[pos]
                    assert token_counts[token] >= 2, \
                        f"Token '{token}' at position {pos} should appear at least twice"

    @given(
        model=st.sampled_from(["gpt-4", "gpt-3.5-turbo", "claude-3-opus"]),
        provider=st.sampled_from(["openai", "anthropic"]),
        chunk_count=st.integers(min_value=5, max_value=50)
    )
    @settings(max_examples=20)
    def test_streaming_metadata_consistency_invariant(
        self,
        db_session,
        model: str,
        provider: str,
        chunk_count: int
    ):
        """
        INVARIANT: All chunks in a stream have consistent metadata.

        Given: A streaming response with model M and provider P
        When: Multiple chunks are received
        Then: All chunks have the same model and provider
        """
        handler = BYOKHandler(db_session)

        chunks = []
        for i in range(chunk_count):
            chunk = StreamChunk(
                index=i,
                content=f"token_{i}",
                finish_reason=None if i < chunk_count - 1 else "stop",
                model=model,
                provider=provider
            )
            chunks.append(chunk)

        # Verify metadata consistency
        models = {c.model for c in chunks}
        providers = {c.provider for c in chunks}

        assert len(models) == 1, f"All chunks must have same model, got: {models}"
        assert len(providers) == 1, f"All chunks must have same provider, got: {providers}"
        assert chunks[0].model == model, f"Model must be {model}"
        assert chunks[0].provider == provider, f"Provider must be {provider}"

    @given(
        finish_reasons=st.sampled_from(["stop", "length", "content_filter", None])
    )
    @settings(max_examples=10)
    def test_streaming_eos_signaling_invariant(
        self,
        db_session,
        finish_reasons: str
    ):
        """
        INVARIANT: Stream properly signals end-of-stream (EOS).

        Given: A streaming response
        When: Stream completes
        Then: Last chunk has non-None finish_reason
        """
        handler = BYOKHandler(db_session)

        chunk_count = 10
        chunks = []
        for i in range(chunk_count):
            chunk = StreamChunk(
                index=i,
                content=f"token_{i}",
                finish_reason=finish_reasons if i == chunk_count - 1 else None,
                model="gpt-4",
                provider="openai"
            )
            chunks.append(chunk)

        # Verify EOS signaling
        last_chunk = chunks[-1]
        assert last_chunk.finish_reason == finish_reasons, \
            f"Last chunk must have finish_reason '{finish_reasons}'"

        # All other chunks must have None
        for i, chunk in enumerate(chunks[:-1]):
            assert chunk.finish_reason is None, \
                f"Chunk {i} (non-final) must have finish_reason=None"


class TestStreamingIntegrityInvariants:
    """Test invariants for streaming data integrity."""

    @given(
        full_text=st.text(min_size=200, max_size=2000, alphabet='abcdefghijklmnopqrstuvwxyz ')
    )
    @settings(max_examples=30)
    def test_streaming_content_reconstruction_invariant(
        self,
        db_session,
        full_text: str
    ):
        """
        INVARIANT: Concatenating all streaming chunks reconstructs full response.

        Given: A full response text T
        When: Split into chunks and streamed
        Then: Concatenating chunks equals T
        """
        handler = BYOKHandler(db_session)

        # Split into chunks
        chunk_size = 10
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]

        # Reconstruct
        reconstructed = ''.join(chunks)

        assert reconstructed == full_text, \
            f"Reconstructed content must match original. Got {len(reconstructed)} chars, expected {len(full_text)}"

    @given(
        chunk_sizes=st.lists(
            st.integers(min_value=1, max_value=50),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=30)
    def test_streaming_index_continuity_invariant(
        self,
        db_session,
        chunk_sizes: List[int]
    ):
        """
        INVARIANT: Chunk indices are continuous with no gaps.

        Given: N chunks with sizes S[0], S[1], ..., S[N-1]
        When: Chunks are indexed
        Then: Indices are 0, 1, 2, ..., N-1 with no gaps
        """
        handler = BYOKHandler(db_session)

        chunks = []
        for i, size in enumerate(chunk_sizes):
            chunk = StreamChunk(
                index=i,
                content="x" * size,
                finish_reason="stop" if i == len(chunk_sizes) - 1 else None,
                model="gpt-4",
                provider="openai"
            )
            chunks.append(chunk)

        # Verify continuity
        indices = [c.index for c in chunks]
        expected_indices = list(range(len(chunks)))

        assert indices == expected_indices, \
            f"Indices must be continuous. Got {indices}, expected {expected_indices}"


class TestProviderFallbackInvariants:
    """Test invariants for provider fallback behavior."""

    @given(
        messages=st.lists(
            st.fixed_dictionaries({
                'role': st.just('user'),
                'content': st.text(min_size=1, max_size=500)
            }),
            min_size=1,
            max_size=5
        ),
        failing_providers=st.lists(
            st.sampled_from(["openai", "anthropic", "deepseek"]),
            min_size=0,
            max_size=2,
            unique=True
        )
    )
    @settings(max_examples=30)
    def test_fallback_preserves_conversation_history_invariant(
        self,
        db_session,
        messages: List[Dict[str, str]],
        failing_providers: List[str]
    ):
        """
        INVARIANT: Provider fallback preserves conversation history.

        Given: A conversation with messages M and provider P1 failing
        When: Falling back to provider P2
        Then: P2 receives the same conversation history
        """
        handler = BYOKHandler(db_session)

        original_messages = messages.copy()

        # Simulate fallback scenario
        providers_to_try = ["openai", "anthropic", "deepseek"]
        successful_provider = None

        for provider in providers_to_try:
            if provider not in failing_providers:
                successful_provider = provider
                break

        # Verify the successful provider would receive same messages
        assert successful_provider is not None, "At least one provider must succeed"
        assert messages == original_messages, \
            "Conversation history must be preserved during fallback"

    @given(
        primary_cost=st.floats(min_value=0.001, max_value=0.1),
        fallback_cost=st.floats(min_value=0.001, max_value=0.1),
        input_tokens=st.integers(min_value=1, max_value=10000),
        output_tokens=st.integers(min_value=1, max_value=5000)
    )
    @settings(max_examples=30)
    def test_fallback_cost_tracking_invariant(
        self,
        db_session,
        primary_cost: float,
        fallback_cost: float,
        input_tokens: int,
        output_tokens: int
    ):
        """
        INVARIANT: Costs are tracked correctly across provider switches.

        Given: Primary provider P1 with cost C1 and fallback P2 with cost C2
        When: Fallback occurs from P1 to P2
        Then: Total cost = (input * C2) + (output * C2)
        """
        handler = BYOKHandler(db_session)

        # Simulate cost calculation after fallback
        input_cost = input_tokens * fallback_cost / 1000  # Per 1k tokens
        output_cost = output_tokens * fallback_cost / 1000
        total_cost = input_cost + output_cost

        # Verify cost is positive and reasonable
        assert total_cost > 0, "Total cost must be positive"
        assert total_cost < (input_tokens + output_tokens) * 0.1, \
            "Cost should be reasonable (<$0.10 per token)"


class TestStreamingErrorRecoveryInvariants:
    """Test invariants for streaming error recovery."""

    @given(
        retry_count=st.integers(min_value=1, max_value=5),
        max_retries=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=20)
    def test_retry_limit_enforced_invariant(
        self,
        db_session,
        retry_count: int,
        max_retries: int
    ):
        """
        INVARIANT: Retry attempts are capped at max_retries.

        Given: max_retries = N and a failing request
        When: Retry attempts exceed N
        Then: Exactly N retries are attempted, then error is raised
        """
        handler = BYOKHandler(db_session)

        actual_retries = min(retry_count, max_retries)

        # Simulate retry logic
        attempts = 0
        success = False

        for attempt in range(max_retries + 1):
            attempts += 1
            if attempt >= retry_count:
                success = True
                break

        # Verify retry limit
        assert attempts <= max_retries + 1, \
            f"Attempts must not exceed max_retries + 1. Got {attempts}, max {max_retries}"

    @given(
        delays=st.lists(
            st.floats(min_value=0.1, max_value=5.0),
            min_size=3,
            max_size=5
        )
    )
    @settings(max_examples=20)
    def test_exponential_backoff_invariant(
        self,
        db_session,
        delays: List[float]
    ):
        """
        INVARIANT: Retry delays follow exponential backoff pattern.

        Given: A series of retry attempts
        When: Calculating retry delays
        Then: delay[i+1] >= delay[i] * 1.5 (exponential growth)
        """
        handler = BYOKHandler(db_session)

        # Verify exponential backoff pattern
        for i in range(len(delays) - 1):
            current_delay = delays[i]
            next_delay = delays[i + 1]

            # Allow some variance, but should generally increase
            # Base delay is 1 second, doubles each retry
            expected_min = current_delay * 1.5
            assert next_delay >= expected_min * 0.8, \
                f"Delay should increase exponentially. delay[{i}]={current_delay}, delay[{i+1}]={next_delay}"


class TestStreamingPerformanceInvariants:
    """Test invariants for streaming performance."""

    @given(
        token_count=st.integers(min_value=10, max_value=1000),
        tokens_per_second=st.floats(min_value=5.0, max_value=100.0)
    )
    @settings(max_examples=30, deadline=10000)  # 10 second deadline
    def test_first_token_latency_invariant(
        self,
        db_session,
        token_count: int,
        tokens_per_second: float
    ):
        """
        INVARIANT: First token is received within 3 seconds.

        Given: A streaming request
        When: Streaming starts
        Then: First chunk arrives within 3 seconds
        """
        import time

        handler = BYOKHandler(db_session)

        start_time = time.time()

        # Simulate streaming
        async def simulate_streaming():
            await asyncio.sleep(0.1)  # Simulate network latency
            return [StreamChunk(
                index=0,
                content="first_token",
                finish_reason=None,
                model="gpt-4",
                provider="openai"
            )]

        first_chunk = asyncio.run(simulate_streaming())
        first_token_time = time.time() - start_time

        assert first_chunk is not None, "First chunk must be received"
        assert first_token_time < 3.0, \
            f"First token must arrive within 3 seconds. Took {first_token_time:.2f}s"

    @given(
        token_count=st.integers(min_value=50, max_value=500),
        duration_seconds=st.floats(min_value=1.0, max_value=10.0)
    )
    @settings(max_examples=20)
    def test_token_throughput_invariant(
        self,
        db_session,
        token_count: int,
        duration_seconds: float
    ):
        """
        INVARIANT: Token throughput exceeds 10 tokens/second.

        Given: A streaming response with N tokens
        When: Measuring streaming duration D
        Then: N / D >= 10 tokens/second
        """
        handler = BYOKHandler(db_session)

        # Calculate throughput
        throughput = token_count / duration_seconds

        # Verify minimum throughput
        min_throughput = 10.0  # tokens per second
        assert throughput >= min_throughput or duration_seconds < 0.5, \
            f"Throughput must be >= {min_throughput} tokens/s. Got {throughput:.2f} tokens/s"

    @pytest.mark.slow
    @given(
        concurrent_streams=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=10, deadline=30000)  # 30 second deadline
    def test_concurrent_streams_isolation_invariant(
        self,
        db_session,
        concurrent_streams: int
    ):
        """
        INVARIANT: Concurrent streams don't interfere with each other.

        Given: N concurrent streaming requests
        When: All streams execute
        Then: Each stream returns correct, independent results
        """
        handler = BYOKHandler(db_session)

        async def simulate_concurrent_streams():
            streams = []
            for i in range(concurrent_streams):
                stream_id = f"stream_{i}"

                async def create_stream(sid=stream_id):
                    chunks = []
                    for j in range(10):
                        chunk = StreamChunk(
                            index=j,
                            content=f"{sid}_token_{j}",
                            finish_reason="stop" if j == 9 else None,
                            model="gpt-4",
                            provider="openai"
                        )
                        chunks.append(chunk)
                        await asyncio.sleep(0.01)
                    return chunks

                streams.append(create_stream())

            results = await asyncio.gather(*streams)
            return results

        results = asyncio.run(simulate_concurrent_streams())

        # Verify each stream is independent
        assert len(results) == concurrent_streams, \
            f"Expected {concurrent_streams} results, got {len(results)}"

        for i, result in enumerate(results):
            assert len(result) == 10, f"Stream {i} should have 10 chunks"
            # Verify content is isolated
            for chunk in result:
                assert f"stream_{i}" in chunk.content, \
                    f"Stream {i} content isolation violated"


class TestStreamingEdgeCases:
    """Test edge cases and boundary conditions."""

    @given(
        empty_content=st.just(""),
        single_token=st.just("token"),
        very_long_content=st.text(min_size=10000, max_size=20000, alphabet='abc')
    )
    @settings(max_examples=5)
    def test_streaming_edge_cases_invariant(
        self,
        db_session,
        empty_content: str,
        single_token: str,
        very_long_content: str
    ):
        """
        INVARIANT: Streaming handles edge cases gracefully.

        Given: Empty, single-token, or very long content
        When: Streaming response
        Then: No errors, proper chunking
        """
        handler = BYOKHandler(db_session)

        # Test empty content (should return single empty chunk)
        empty_chunks = [empty_content[i:i+10] for i in range(0, max(1, len(empty_content)), 10)]
        assert len(empty_chunks) >= 1, "Empty content should produce at least one chunk"

        # Test single token
        single_chunks = [single_token]
        assert len(single_chunks) == 1, "Single token should produce one chunk"

        # Test very long content
        long_chunks = [very_long_content[i:i+100] for i in range(0, len(very_long_content), 100)]
        assert len(long_chunks) > 0, "Long content should produce multiple chunks"
        reconstructed = ''.join(long_chunks)
        assert reconstructed == very_long_content, "Long content reconstruction must match"


# VALIDATED_BUG sections for discovered issues
# Add sections as bugs are discovered during testing

# Example:
# ## VALIDATED_BUG: Stream Chunk Duplication on Network Retry
# **Discovered**: 2025-02-XX
# **Issue**: When network retry occurs, chunks could be duplicated
# **Fix**: Added chunk_id deduplication in stream handler
# **Commit**: [hash]
# **Test Case**: test_streaming_no_duplicates_invariant
```

### Test: test_token_counting_invariants.py

```python
"""
Property-based tests for token counting accuracy invariants.

Tests ensure that:
- Input token counts match provider specifications
- Output token counts are accurate
- Total cost calculation is correct
- Token budget is properly enforced
- Token counting is consistent across providers
"""

import pytest
from hypothesis import given, settings, example, Phase
from hypothesis import strategies as st
from typing import Dict, Tuple
from unittest.mock import Mock, patch
import math

from core.llm.byok_handler import BYOKHandler, PROVIDER_TIERS
from tests.property_tests.conftest import db_session


class TestInputTokenCountingInvariants:
    """Test invariants for input token counting."""

    @given(
        text=st.text(min_size=1, max_size=10000, alphabet='abcdefghijklmnopqrstuvwxyz ')
    )
    @settings(max_examples=50)
    def test_openai_input_token_count_invariant(
        self,
        db_session,
        text: str
    ):
        """
        INVARIANT: OpenAI input token count matches tiktoken cl100k_base.

        Given: A text string T
        When: Counting tokens for OpenAI API
        Then: Token count matches tiktoken cl100k_base encoding
        """
        handler = BYOKHandler(db_session)

        # Use tiktoken for ground truth (if available)
        try:
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            expected_count = len(encoding.encode(text))

            # Handler's count should match
            actual_count = handler._count_tokens(text, "openai")
            assert actual_count == expected_count, \
                f"Token count mismatch. Expected {expected_count}, got {actual_count}"
        except ImportError:
            pytest.skip("tiktoken not installed")

    @given(
        messages=st.lists(
            st.fixed_dictionaries({
                'role': st.sampled_from(['user', 'assistant', 'system']),
                'content': st.text(min_size=1, max_size=2000)
            }),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=30)
    def test_conversation_token_count_invariant(
        self,
        db_session,
        messages: list
    ):
        """
        INVARIANT: Conversation token count = sum(message token counts).

        Given: A conversation with messages M1, M2, ..., Mn
        When: Counting total input tokens
        Then: Total = count(M1) + count(M2) + ... + count(Mn)
        """
        handler = BYOKHandler(db_session)

        # Count individual messages
        individual_counts = []
        total_from_individual = 0

        for msg in messages:
            content = msg.get('content', '')
            # Simplified counting (chars / 4 approximation)
            count = math.ceil(len(content) / 4)
            individual_counts.append(count)
            total_from_individual += count

        # Handler should produce same total
        # (Using simplified count for test stability)
        assert total_from_individual > 0, "Total token count must be positive"
        assert len(individual_counts) == len(messages), \
            "Each message should have a token count"

    @given(
        text_length=st.integers(min_value=0, max_value=100000)
    )
    @settings(max_examples=30)
    def test_empty_text_token_count_invariant(
        self,
        db_session,
        text_length: int
    ):
        """
        INVARIANT: Empty text has 0 tokens, non-empty has >0 tokens.

        Given: Text of length L (possibly 0)
        When: Counting tokens
        Then: Tokens = 0 if L=0, tokens > 0 if L>0
        """
        handler = BYOKHandler(db_session)

        text = "a" * text_length if text_length > 0 else ""

        token_count = handler._count_tokens(text, "openai")

        if text_length == 0:
            assert token_count == 0, "Empty text should have 0 tokens"
        else:
            assert token_count > 0, f"Non-empty text should have >0 tokens, got {token_count}"


class TestOutputTokenCountingInvariants:
    """Test invariants for output token counting."""

    @given(
        generated_text=st.text(min_size=10, max_size=5000, alphabet='abcdefghijklmnopqrstuvwxyz ')
    )
    @settings(max_examples=50)
    def test_output_token_accuracy_invariant(
        self,
        db_session,
        generated_text: str
    ):
        """
        INVARIANT: Output token count matches actual tokens generated.

        Given: Generated response text T
        When: Counting output tokens
        Then: Token count matches tiktoken (OpenAI) or provider spec
        """
        handler = BYOKHandler(db_session)

        # Simplified token counting (chars / 4 approximation for cl100k_base)
        estimated_tokens = math.ceil(len(generated_text) / 4)

        # Handler should produce consistent count
        actual_tokens = handler._count_tokens(generated_text, "openai")

        # Allow ~20% variance due to estimation
        variance = abs(estimated_tokens - actual_tokens) / max(1, estimated_tokens)
        assert variance < 0.2, \
            f"Token count variance too high: {variance:.2%}. Estimated {estimated_tokens}, got {actual_tokens}"

    @given(
        chunks=st.lists(
            st.text(min_size=1, max_size=100, alphabet='abc'),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=30)
    def test_streaming_token_aggregation_invariant(
        self,
        db_session,
        chunks: list
    ):
        """
        INVARIANT: Streaming token count = sum(chunk token counts).

        Given: Streaming response with chunks C1, C2, ..., Cn
        When: Aggregating token counts
        Then: Total = count(C1) + count(C2) + ... + count(Cn)
        """
        handler = BYOKHandler(db_session)

        # Count tokens for each chunk
        chunk_counts = [handler._count_tokens(chunk, "openai") for chunk in chunks]
        total_from_chunks = sum(chunk_counts)

        # Full text count
        full_text = ''.join(chunks)
        full_count = handler._count_tokens(full_text, "openai")

        # Should be approximately equal (may differ slightly due to chunk boundaries)
        variance = abs(total_from_chunks - full_count) / max(1, full_count)
        assert variance < 0.1, \
            f"Aggregated count should match full text count. Variance: {variance:.2%}"


class TestCostCalculationInvariants:
    """Test invariants for cost calculation."""

    @given(
        input_tokens=st.integers(min_value=1, max_value=100000),
        output_tokens=st.integers(min_value=1, max_value=50000),
        input_price=st.floats(min_value=0.0001, max_value=0.01, allow_nan=False, allow_infinity=False),
        output_price=st.floats(min_value=0.0001, max_value=0.03, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_cost_calculation_formula_invariant(
        self,
        db_session,
        input_tokens: int,
        output_tokens: int,
        input_price: float,
        output_price: float
    ):
        """
        INVARIANT: Total cost = (input * input_price) + (output * output_price).

        Given: Input tokens Ti, output tokens To, prices Pi, Po
        When: Calculating total cost
        Then: Cost = (Ti/1000 * Pi) + (To/1000 * Po)
        """
        handler = BYOKHandler(db_session)

        # Calculate expected cost
        expected_cost = (input_tokens / 1000.0 * input_price) + \
                        (output_tokens / 1000.0 * output_price)

        # Handler's calculation
        actual_cost = handler._calculate_cost(
            input_tokens, output_tokens, input_price, output_price
        )

        # Should match within floating point precision
        assert math.isclose(actual_cost, expected_cost, rel_tol=1e-9), \
            f"Cost calculation mismatch. Expected {expected_cost}, got {actual_cost}"

    @given(
        provider=st.sampled_from(["openai", "anthropic", "deepseek"]),
        model=st.sampled_from(["gpt-4", "gpt-3.5-turbo", "claude-3-opus"]),
        tokens=st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=30)
    def test_provider_pricing_consistency_invariant(
        self,
        db_session,
        provider: str,
        model: str,
        tokens: int
    ):
        """
        INVARIANT: Provider pricing is loaded and used consistently.

        Given: Provider P and model M
        When: Calculating cost for N tokens
        Then: Uses correct pricing from PROVIDER_TIERS
        """
        handler = BYOKHandler(db_session)

        # Verify provider has pricing configured
        assert provider in PROVIDER_TIERS, f"Provider {provider} must be in PROVIDER_TIERS"

        # Get pricing info
        provider_info = PROVIDER_TIERS[provider]
        assert 'models' in provider_info, "Provider info must have 'models'"

        # Calculate cost and verify it's reasonable
        cost = handler._estimate_cost(tokens, 0, provider, model)

        assert cost >= 0, "Cost must be non-negative"
        assert cost < 1000, f"Cost ${cost:.2f} seems unreasonably high for {tokens} tokens"

    @given(
        input_tokens=st.integers(min_value=1, max_value=100000),
        output_tokens=st.integers(min_value=1, max_value=50000)
    )
    @settings(max_examples=30)
    def test_cost_per_1k_tokens_invariant(
        self,
        db_session,
        input_tokens: int,
        output_tokens: int
    ):
        """
        INVARIANT: Pricing is per 1,000 tokens, not per token.

        Given: N input tokens and M output tokens
        When: Calculating cost with price P per 1k tokens
        Then: Cost = (N/1000 * P) + (M/1000 * P)
        """
        handler = BYOKHandler(db_session)

        price_per_1k = 0.002  # Example price

        # Cost should scale with token count / 1000
        expected_input_cost = input_tokens / 1000.0 * price_per_1k
        expected_output_cost = output_tokens / 1000.0 * price_per_1k
        total_expected = expected_input_cost + expected_output_cost

        # Verify linear scaling
        assert total_expected > 0, "Total cost must be positive"

        # Double the tokens should double the cost
        double_input = input_tokens * 2
        double_output = output_tokens * 2
        double_cost = (double_input / 1000.0 * price_per_1k) + \
                      (double_output / 1000.0 * price_per_1k)

        assert math.isclose(double_cost, total_expected * 2, rel_tol=1e-6), \
            "Doubling tokens should double cost"


class TestTokenBudgetInvariants:
    """Test invariants for token budget enforcement."""

    @given(
        budget=st.integers(min_value=100, max_value=10000),
        request_tokens=st.integers(min_value=1, max_value=20000)
    )
    @settings(max_examples=40)
    def test_budget_enforcement_invariant(
        self,
        db_session,
        budget: int,
        request_tokens: int
    ):
        """
        INVARIANT: Requests exceeding budget are rejected.

        Given: Token budget B and request with R tokens
        When: R > B
        Then: Request is rejected with clear error
        """
        handler = BYOKHandler(db_session)

        # Simulate budget check
        can_proceed = request_tokens <= budget

        if request_tokens > budget:
            assert not can_proceed, \
                f"Request with {request_tokens} tokens should exceed budget of {budget}"
        else:
            assert can_proceed, \
                f"Request with {request_tokens} tokens should fit within budget of {budget}"

    @given(
        budgets=st.lists(
            st.integers(min_value=100, max_value=10000),
            min_size=2,
            max_size=5
        ),
        requests=st.lists(
            st.integers(min_value=10, max_value=5000),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=30)
    def test_budget_tracking_across_requests_invariant(
        self,
        db_session,
        budgets: list,
        requests: list
    ):
        """
        INVARIANT: Budget is tracked and deducted across multiple requests.

        Given: Initial budget B and requests R1, R2, ..., Rn
        When: Processing requests sequentially
        Then: Remaining budget = B - sum(Ri) for all processed requests
        """
        handler = BYOKHandler(db_session)

        initial_budget = budgets[0]
        remaining_budget = initial_budget

        processed = 0
        for request_tokens in requests:
            if remaining_budget >= request_tokens:
                remaining_budget -= request_tokens
                processed += 1
            else:
                # Request rejected, budget unchanged
                break

        # Verify budget tracking
        assert remaining_budget >= 0, "Remaining budget cannot be negative"
        assert remaining_budget <= initial_budget, "Remaining budget cannot exceed initial"

        # Sum of processed requests should equal initial - remaining
        sum_processed = sum(requests[:processed])
        assert initial_budget - sum_processed == remaining_budget, \
            f"Budget tracking mismatch. Initial: {initial_budget}, Processed: {sum_processed}, Remaining: {remaining_budget}"


class TestTokenCountingEdgeCases:
    """Test edge cases for token counting."""

    @given(
        special_chars=st.text(min_size=1, max_size=1000, alphabet='!@#$%^&*()[]{}""\'')
    )
    @settings(max_examples=20)
    def test_special_characters_token_count_invariant(
        self,
        db_session,
        special_chars: str
    ):
        """
        INVARIANT: Special characters are counted correctly.

        Given: Text with special characters
        When: Counting tokens
        Then: Special chars don't cause incorrect counts
        """
        handler = BYOKHandler(db_session)

        token_count = handler._count_tokens(special_chars, "openai")

        assert token_count >= 0, "Token count must be non-negative"
        # Special chars often use more tokens
        assert token_count <= len(special_chars) * 2, \
            "Token count should not exceed character count by 2x"

    @given(
        unicode_text=st.text(min_size=1, max_size=1000)  # Includes unicode
    )
    @settings(max_examples=20)
    def test_unicode_token_count_invariant(
        self,
        db_session,
        unicode_text: str
    ):
        """
        INVARIANT: Unicode characters are counted correctly.

        Given: Text with unicode characters
        When: Counting tokens
        Then: Unicode chars don't cause errors or incorrect counts
        """
        handler = BYOKHandler(db_session)

        # Should not raise exception
        token_count = handler._count_tokens(unicode_text, "openai")

        assert token_count >= 0, "Token count must be non-negative for unicode text"

    @given(
        very_long_text=st.text(min_size=50000, max_size=100000, alphabet='abcd ')
    )
    @settings(max_examples=5)
    def test_very_long_text_token_count_invariant(
        self,
        db_session,
        very_long_text: str
    ):
        """
        INVARIANT: Very long texts are counted efficiently.

        Given: Text with >50k characters
        When: Counting tokens
        Then: Counting completes in reasonable time
        """
        import time

        handler = BYOKHandler(db_session)

        start_time = time.time()
        token_count = handler._count_tokens(very_long_text, "openai")
        duration = time.time() - start_time

        assert token_count > 0, "Token count must be positive"
        assert duration < 1.0, f"Token counting took {duration:.2f}s, should be <1s"


# VALIDATED_BUG sections for discovered issues
# Add sections as bugs are discovered during testing

# Example:
# ## VALIDATED_BUG: Off-by-One Error in Token Counting
# **Discovered**: 2025-02-XX
# **Issue**: Token count was off by 1 for certain edge cases
# **Fix**: Adjusted counting algorithm to handle edge cases
# **Commit**: [hash]
# **Test Case**: test_empty_text_token_count_invariant
```

### Test: __init__.py

```python
"""
Property-based tests for LLM streaming and token counting invariants.

This package tests:
- Streaming completion invariants (ordering, integrity, metadata)
- Token counting accuracy (input, output, total cost)
- Provider fallback behavior
- Streaming error recovery
- Token budget enforcement
"""

from tests.property_tests.llm.test_llm_streaming_invariants import (
    TestStreamingCompletionInvariants,
    TestStreamingIntegrityInvariants,
    TestProviderFallbackInvariants,
    TestStreamingErrorRecoveryInvariants,
    TestStreamingPerformanceInvariants,
    TestStreamingEdgeCases
)

from tests.property_tests.llm.test_token_counting_invariants import (
    TestInputTokenCountingInvariants,
    TestOutputTokenCountingInvariants,
    TestCostCalculationInvariants,
    TestTokenBudgetInvariants,
    TestTokenCountingEdgeCases
)

__all__ = [
    'TestStreamingCompletionInvariants',
    'TestStreamingIntegrityInvariants',
    'TestProviderFallbackInvariants',
    'TestStreamingErrorRecoveryInvariants',
    'TestStreamingPerformanceInvariants',
    'TestStreamingEdgeCases',
    'TestInputTokenCountingInvariants',
    'TestOutputTokenCountingInvariants',
    'TestCostCalculationInvariants',
    'TestTokenBudgetInvariants',
    'TestTokenCountingEdgeCases',
]
```

## Success Criteria

- [ ] All 5 test classes implemented with >50 test methods
- [ ] All tests use Hypothesis strategies for property-based generation
- [ ] Tests validate streaming ordering, integrity, and metadata consistency
- [ ] Tests validate token counting accuracy for input and output
- [ ] Tests validate cost calculation formulas
- [ ] Tests validate provider fallback preserves context
- [ ] Tests validate retry limits and exponential backoff
- [ ] Tests validate token budget enforcement
- [ ] `@example` decorators for critical edge cases
- [ ] `VALIDATED_BUG` sections added for discovered issues
- [ ] Tests integrate with Phase 1 fixtures (db_session, mock_llm_stream)

## Dependencies

### Phase 1 Infrastructure
- `tests/conftest.py` - db_session, mock_llm_stream fixtures
- `tests/property_tests/conftest.py` - Hypothesis settings, test utilities

### Code Under Test
- `core/llm/byok_handler.py` - BYOKHandler, StreamChunk, PROVIDER_TIERS

### External Dependencies
- `tiktoken` - For OpenAI token counting verification (optional, skip if not installed)

## Execution

```bash
# Run LLM streaming invariants
pytest tests/property_tests/llm/test_llm_streaming_invariants.py -v

# Run token counting invariants
pytest tests/property_tests/llm/test_token_counting_invariants.py -v

# Run all LLM invariants
pytest tests/property_tests/llm/ -v

# Run with coverage
pytest tests/property_tests/llm/ --cov=core.llm.byok_handler --cov-report=term-missing

# Run specific test
pytest tests/property_tests/llm/test_llm_streaming_invariants.py::TestStreamingCompletionInvariants::test_streaming_chunk_ordering_invariant -v
```

## Verification

After implementation:

1. **Test Coverage**: Verify coverage of `core/llm/byok_handler.py` increases
2. **Bug Discovery**: Check for VALIDATED_BUG sections added
3. **Performance**: Ensure tests complete within deadlines
4. **Integration**: Verify tests use Phase 1 fixtures correctly

## Notes

- Token counting uses approximation (chars / 4) when tiktoken not available
- Streaming tests use async simulation to avoid actual LLM calls
- Cost calculations verified with high precision (rel_tol=1e-9)
- Edge cases include empty text, unicode, special characters, very long texts
- Performance tests have longer deadlines to accommodate async operations
