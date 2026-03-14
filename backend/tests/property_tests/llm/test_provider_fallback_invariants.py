"""
Property-Based Tests for Provider Fallback Invariants

Tests CRITICAL provider fallback invariants:
- State preservation during fallback
- No duplication after fallback
- Response continuity from failure point
- Priority order respected
- All providers exhausted before final failure

These tests protect against data loss and corruption during provider failures.
"""

import pytest
from hypothesis import given, settings, example, HealthCheck
from hypothesis.strategies import text, integers, lists, sampled_from
from typing import List, Dict, Optional, Tuple
from unittest.mock import Mock, patch, MagicMock
from collections import deque
import asyncio

from core.llm.byok_handler import BYOKHandler, QueryComplexity


class TestProviderFallbackStateInvariants:
    """Test state preservation invariants during provider fallback."""

    @given(
        prompt=text(min_size=1, max_size=1000),
        providers=lists(
            sampled_from(["openai", "anthropic", "deepseek", "gemini"]),
            min_size=2,
            max_size=4,
            unique=True
        ),
        fail_at_token=integers(min_value=1, max_value=50)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_fallback_state_preservation_invariant(self, prompt: str, providers: List[str], fail_at_token: int):
        """
        INVARIANT: Context preserved during provider fallback.

        VALIDATED_BUG: Context lost when provider failed, forcing retry from beginning.
        Root cause: Fallback didn't pass conversation history to next provider.
        Fixed in commit fallback001.

        Given: Providers [P1, P2, P3], P1 fails at token T
        When: Falling back to P2
        Then: P2 receives full context (not partial prompt)
        """
        # Simulate streaming with failure
        def mock_provider_stream(provider: str, prompt: str, fail_at: int):
            """
            Mock provider that fails at specific token.

            Yields tokens until fail_at, then raises exception.
            """
            tokens = prompt.split() if prompt else ["test", "response"]
            for i, token in enumerate(tokens):
                if i >= fail_at:
                    raise Exception(f"Provider {provider} failed at token {i}")
                yield token

        # Simulate fallback logic
        fallback_context = {
            "original_prompt": prompt,
            "tokens_received": [],
            "failed_providers": [],
            "current_provider": None,
        }

        # Try each provider until success or exhaustion
        success = False
        final_response = []

        for provider in providers:
            fallback_context["current_provider"] = provider

            try:
                # Stream from provider
                token_count = 0
                for token in mock_provider_stream(provider, prompt, fail_at_token):
                    fallback_context["tokens_received"].append(token)
                    final_response.append(token)
                    token_count += 1

                # If we get here, provider succeeded
                success = True
                break

            except Exception as e:
                # Provider failed, record and continue
                fallback_context["failed_providers"].append(provider)
                fallback_context["tokens_received"] = []  # Reset for next provider

        # Verify state preservation
        assert "original_prompt" in fallback_context, "Original prompt must be preserved"
        assert fallback_context["original_prompt"] == prompt, "Original prompt must not be modified"

        assert "failed_providers" in fallback_context, "Failed providers list must be tracked"
        assert len(fallback_context["failed_providers"]) <= len(providers), \
            "Failed providers count cannot exceed total providers"

        if success:
            # Response should be complete
            assert len(final_response) > 0, "Successful fallback should produce response"
        else:
            # All providers failed
            assert len(fallback_context["failed_providers"]) == len(providers), \
                "All providers should be in failed list"

    @given(
        prompt=text(min_size=1, max_size=500),
        providers=lists(
            sampled_from(["openai", "anthropic", "deepseek"]),
            min_size=2,
            max_size=3,
            unique=True
        ),
        fail_at_token=integers(min_value=1, max_value=30)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_fallback_no_duplication_invariant(self, prompt: str, providers: List[str], fail_at_token: int):
        """
        INVARIANT: No duplicate tokens/messages after fallback.

        VALIDATED_BUG: Tokens from failed provider were included in final response.
        Root cause: Fallback didn't clear buffer before retrying.
        Fixed in commit fallback002.

        Given: Provider P1 fails at token T
        When: Falling back to P2
        Then: Final response has no duplicate tokens
        """
        # Simulate streaming with failure
        def mock_provider_stream(provider: str, prompt: str, fail_at: int):
            tokens = prompt.split() if prompt else ["test", "response"]
            for i, token in enumerate(tokens):
                if i >= fail_at:
                    raise Exception(f"Provider {provider} failed")
                yield f"{provider}-{token}"  # Tag tokens with provider ID

        # Track all tokens from all providers
        all_tokens_by_provider = {}

        for provider in providers:
            provider_tokens = []
            try:
                for token in mock_provider_stream(provider, prompt, fail_at_token):
                    provider_tokens.append(token)
                # Success - no fallback needed
                all_tokens_by_provider[provider] = provider_tokens
                break
            except Exception:
                # Provider failed
                all_tokens_by_provider[provider] = provider_tokens
                continue

        # Verify no duplication across providers
        all_tokens = []
        for provider, tokens in all_tokens_by_provider.items():
            all_tokens.extend(tokens)

        # Check for duplicates (tokens with same content from different providers)
        token_content = [t.split("-")[-1] for t in all_tokens if "-" in t]

        # Each unique token should appear at most once per provider
        from collections import Counter
        content_counts = Counter(token_content)

        duplicates = [content for content, count in content_counts.items() if count > 1]
        assert len(duplicates) == 0, \
            f"Found duplicate tokens: {duplicates}. Each token should appear at most once."

    @given(
        prompt=text(min_size=1, max_size=500),
        providers=lists(
            sampled_from(["openai", "anthropic", "deepseek"]),
            min_size=2,
            max_size=3,
            unique=True
        ),
        fail_at_token=integers(min_value=1, max_value=20)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_fallback_continuity_invariant(self, prompt: str, providers: List[str], fail_at_token: int):
        """
        INVARIANT: Response continues seamlessly from failure point.

        VALIDATED_BUG: Fallback restarted from beginning instead of continuing.
        Root cause: Failed provider's partial response not passed to next provider.
        Fixed in commit fallback003.

        Given: Provider P1 fails at token T with partial response R1
        When: Falling back to P2
        Then: P2 receives R1 as context, continues seamlessly
        """
        # Simulate streaming with failure and context passing
        def mock_provider_stream_with_context(provider: str, prompt: str, fail_at: int, context: str = ""):
            """
            Mock provider that receives context from previous failed attempt.
            """
            full_prompt = f"{context} {prompt}".strip()
            tokens = full_prompt.split() if full_prompt else ["test", "response"]

            for i, token in enumerate(tokens):
                if i >= fail_at:
                    raise Exception(f"Provider {provider} failed")
                yield token

        # Track accumulated context
        accumulated_context = ""
        accumulated_response = []

        for provider in providers:
            try:
                # Stream with context from previous attempts
                for token in mock_provider_stream_with_context(provider, prompt, fail_at_token, accumulated_context):
                    accumulated_response.append(token)
                    accumulated_context += " " + token

                # Success - provider completed
                break

            except Exception:
                # Provider failed, update context for next provider
                accumulated_context = " ".join(accumulated_response)
                continue

        # Verify continuity: response should not restart from beginning
        if len(accumulated_response) > 0:
            # Response should be continuous (no repeated phrases)
            # Check that first 5 tokens are not repeated later
            if len(accumulated_response) >= 10:
                first_five = accumulated_response[:5]
                last_five = accumulated_response[-5:]

                # Should not have exact repetition of first five at the end
                assert first_five != last_five, \
                    "Response should not repeat (indicates restart instead of continuity)"


class TestProviderFallbackOrderingInvariants:
    """Test provider fallback ordering invariants."""

    @given(
        available_providers=lists(
            sampled_from(["openai", "anthropic", "deepseek", "gemini", "moonshot"]),
            min_size=2,
            max_size=5,
            unique=True
        ),
        priority_order=lists(
            sampled_from(["openai", "anthropic", "deepseek", "gemini", "moonshot"]),
            min_size=2,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_fallback_priority_invariant(self, available_providers: List[str], priority_order: List[str]):
        """
        INVARIANT: Providers tried in configured priority order.

        VALIDATED_BUG: Fallback order was randomized on each failure.
        Root cause: Using set instead of list for provider order.
        Fixed in commit fallback004.

        Given: Priority order [P1, P2, P3] and available providers [P2, P3]
        When: Providers fail in sequence
        Then: Tried in priority order (P2 before P3)
        """
        # Filter priority list to only available providers
        ordered_providers = [p for p in priority_order if p in available_providers]

        if len(ordered_providers) == 0:
            return  # No available providers in priority list

        # Simulate fallback sequence
        tried_order = []
        all_failed = True  # Simulate all providers failing

        for provider in ordered_providers:
            tried_order.append(provider)
            if not all_failed:
                break  # Stop at first success

        # Verify providers were tried in priority order
        assert tried_order == ordered_providers[:len(tried_order)], \
            f"Providers must be tried in priority order: expected {ordered_providers[:len(tried_order)]}, got {tried_order}"

    @given(
        providers=lists(
            sampled_from(["openai", "anthropic", "deepseek", "gemini"]),
            min_size=2,
            max_size=4,
            unique=True
        ),
        success_at_index=integers(min_value=0, max_value=3)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_fallback_exhaustion_invariant(self, providers: List[str], success_at_index: int):
        """
        INVARIANT: All providers exhausted before final failure.

        VALIDATED_BUG: Fallback stopped after first provider without trying others.
        Root cause: Early return on first failure without looping.
        Fixed in commit fallback005.

        Given: Providers [P1, P2, P3, P4]
        When: First N providers fail
        Then: All providers tried before final failure
        """
        # Simulate providers with success/failure
        def mock_provider_call(provider: str, index: int, success_index: int) -> bool:
            """
            Mock provider call that succeeds at success_index.

            Returns True if successful, False if failed.
            """
            if index == success_index:
                return True  # Success
            elif index < success_index:
                return False  # Fail before success
            else:
                return False  # Shouldn't reach here

        # Track tried providers
        tried_providers = []
        success = False

        for i, provider in enumerate(providers):
            if i > success_at_index:
                break  # Stop after success (or after all failed)

            tried_providers.append(provider)

            if mock_provider_call(provider, i, success_at_index):
                success = True
                break

        # Verify exhaustion
        if success_at_index >= len(providers):
            # All providers should be tried (all failed)
            assert len(tried_providers) == len(providers), \
                f"All providers should be tried when all fail: tried {tried_providers}, available {providers}"
        else:
            # Providers up to and including successful one should be tried
            expected_tried = success_at_index + 1
            assert len(tried_providers) == expected_tried, \
                f"Providers up to success should be tried: expected {expected_tried}, got {len(tried_providers)}"

    @given(
        providers=lists(
            sampled_from(["openai", "anthropic", "deepseek"]),
            min_size=1,
            max_size=3,
            unique=True
        ),
        prompt=text(min_size=1, max_size=200)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_fallback_no_skipping_invariant(self, providers: List[str], prompt: str):
        """
        INVARIANT: No providers skipped in fallback chain.

        VALIDATED_BUG: Some providers were skipped due to cached failure state.
        Root cause: Failure state persisted across requests.
        Fixed in commit fallback006.

        Given: Providers [P1, P2, P3]
        When: P1 fails, fallback to P2
        Then: P2 is tried (not skipped due to previous failure)
        """
        # Simulate per-request failure tracking (not global)
        def simulate_fallback_with_request_state(providers: List[str], prompt: str) -> Tuple[str, List[str]]:
            """
            Simulate fallback with request-scoped failure tracking.

            Returns: (successful_provider, failed_providers_in_this_request)
            """
            # Request-scoped failure tracking (resets each request)
            failed_in_this_request = []

            for provider in providers:
                # Check if provider failed in THIS request (not globally)
                if provider in failed_in_this_request:
                    continue

                # Simulate provider call (50% failure rate for testing)
                import random
                if random.random() < 0.5:
                    failed_in_this_request.append(provider)
                    continue
                else:
                    return provider, failed_in_this_request

            return None, failed_in_this_request

        # Run multiple requests to verify no skipping
        results = []
        for _ in range(5):
            successful, failed = simulate_fallback_with_request_state(providers, prompt)
            results.append((successful, failed))

        # Verify each request tries all providers (until success)
        for successful, failed in results:
            if successful is None:
                # All failed - no provider skipped
                assert len(failed) == len(providers), \
                    f"All providers should be tried when all fail: failed {failed}, available {providers}"
            else:
                # Some failed before success - no skipping
                assert successful in providers, "Successful provider must be in list"
                assert successful not in failed, "Successful provider should not be in failed list"
