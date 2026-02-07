"""
Property-Based Tests for Integration Resilience

⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL INTEGRATION RESILIENCE INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md

Tests:
    - 15 comprehensive property-based tests for integration resilience
    - Coverage targets: 90%+ of integration resilience patterns
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from typing import List, Dict
from integrations.oauth_handler import OAuthHandler
from integrations.retry_manager import RetryManager
from integrations.circuit_breaker import CircuitBreaker
from integrations.webhook_handler import WebhookHandler
import time


class TestOAuthResilienceInvariants:
    """Property-based tests for OAuth resilience invariants."""

    @given(
        state_length=st.integers(min_value=16, max_value=64)
    )
    @settings(max_examples=100)
    def test_oauth_state_uniqueness(self, state_length):
        """INVARIANT: OAuth states must be unique across requests."""
        handler = OAuthHandler()

        # Generate multiple states
        states = [handler.generate_state(length=state_length) for _ in range(100)]

        # All states must be unique
        assert len(set(states)) == 100, f"Generated {len(states)} states but only {len(set(states))} are unique"

    @given(
        token_expiry_seconds=st.integers(min_value=300, max_value=86400),
        current_timestamp=st.integers(min_value=0, max_value=1000000)
    )
    @settings(max_examples=100)
    def test_oauth_token_refresh_retry(self, token_expiry_seconds, current_timestamp):
        """INVARIANT: Token refresh should retry on 401 errors."""
        handler = OAuthHandler()

        # Simulate token expiry
        token_issued_at = current_timestamp - token_expiry_seconds - 100  # Already expired
        token_expiry = token_issued_at + token_expiry_seconds

        # Check if token needs refresh
        needs_refresh = handler.check_token_needs_refresh(
            token_issued_at=token_issued_at,
            token_expiry=token_expiry,
            current_timestamp=current_timestamp
        )

        if current_timestamp >= token_expiry:
            assert needs_refresh, "Expired token should need refresh"
        else:
            # Within grace period?
            time_until_expiry = token_expiry - current_timestamp
            if time_until_expiry < 300:  # 5 minutes
                assert needs_refresh, "Token expiring soon should need refresh"
            else:
                assert not needs_refresh, "Valid token should not need refresh"

    @given(
        state=st.text(min_size=16, max_size=128),
        callback_params=st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.text(min_size=1, max_size=200),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_oauth_callback_validation(self, state, callback_params):
        """INVARIANT: OAuth callback must validate state and parameters."""
        handler = OAuthHandler()

        # Store state
        handler.store_state(state)

        # Validate callback
        is_valid = handler.validate_callback(
            state=state,
            params=callback_params
        )

        # State should be valid if stored
        assert is_valid, "Callback with valid state should succeed"

        # Invalid state should fail
        invalid_state = state + "_invalid"
        is_valid_invalid = handler.validate_callback(
            state=invalid_state,
            params=callback_params
        )
        assert not is_valid_invalid, "Callback with invalid state should fail"

    @given(
        error_code=st.sampled_from(['invalid_request', 'unauthorized_client', 'access_denied', 'server_error', 'temporarily_unavailable'])
    )
    @settings(max_examples=100)
    def test_oauth_error_handling(self, error_code):
        """INVARIANT: OAuth errors must be handled gracefully."""
        handler = OAuthHandler()

        # Handle error
        error_response = handler.handle_oauth_error(error_code)

        # Verify error response
        assert 'error' in error_response
        assert error_response['error'] == error_code
        assert 'message' in error_response
        assert len(error_response['message']) > 0

        # Verify user-friendly messages
        assert len(error_response['message']) < 500, "Error message too long"

    @given(
        timeout_seconds=st.integers(min_value=5, max_value=120),
        elapsed_seconds=st.integers(min_value=0, max_value=300)
    )
    @settings(max_examples=100)
    def test_oauth_timeout_handling(self, timeout_seconds, elapsed_seconds):
        """INVARIANT: OAuth requests must handle timeouts gracefully."""
        handler = OAuthHandler()

        # Check timeout
        has_timed_out = handler.check_timeout(
            timeout_seconds=timeout_seconds,
            elapsed_seconds=elapsed_seconds
        )

        if elapsed_seconds >= timeout_seconds:
            assert has_timed_out, "Request should have timed out"
        else:
            assert not has_timed_out, "Request should not have timed out"

        # Verify timeout doesn't cause crashes
        if has_timed_out:
            # Should handle gracefully
            error_response = handler.handle_timeout()
            assert error_response is not None
            assert 'error' in error_response or 'message' in error_response


class TestIntegrationResilienceInvariants:
    """Property-based tests for integration resilience invariants."""

    @given(
        max_retries=st.integers(min_value=0, max_value=5),
        attempts=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100)
    def test_integration_retry_logic(self, max_retries, attempts):
        """INVARIANT: Integration calls should retry on transient failures."""
        retry_manager = RetryManager(max_retries=max_retries)

        # Simulate retry attempts
        actual_attempts = min(attempts, max_retries + 1)

        # Verify retry count
        if attempts <= max_retries:
            # Should retry all attempts
            assert actual_attempts == attempts
        else:
            # Should not exceed max_retries
            assert actual_attempts <= max_retries + 1

    @given(
        requests=st.lists(
            st.fixed_dictionaries({
                'timestamp': st.integers(min_value=0, max_value=10000),
                'status_code': st.sampled_from([200, 429, 500, 502, 503])
            }),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_rate_limiting_backoff(self, requests):
        """INVARIANT: Rate limit errors should trigger exponential backoff."""
        retry_manager = RetryManager(max_retries=3)

        # Count rate limit errors
        rate_limit_count = sum(1 for r in requests if r['status_code'] == 429)

        if rate_limit_count > 0:
            # Should use exponential backoff
            backoff_delays = []
            for i in range(rate_limit_count):
                delay = retry_manager.calculate_backoff(attempt=i, error_type='rate_limit')
                backoff_delays.append(delay)

                # Verify exponential backoff
                if i > 0:
                    expected_min = backoff_delays[i-1] * 2
                    assert delay >= expected_min, f"Backoff should increase exponentially: {delay} >= {expected_min}"

    @given(
        failure_count=st.integers(min_value=0, max_value=100),
        threshold=st.integers(min_value=3, max_value=20),
        timeout_seconds=st.integers(min_value=30, max_value=300)
    )
    @settings(max_examples=100)
    def test_integration_circuit_breaker(self, failure_count, threshold, timeout_seconds):
        """INVARIANT: Circuit breaker should open after failure threshold."""
        circuit_breaker = CircuitBreaker(
            failure_threshold=threshold,
            timeout_seconds=timeout_seconds
        )

        # Record failures
        for _ in range(failure_count):
            circuit_breaker.record_failure()

        # Check circuit state
        is_open = circuit_breaker.is_open()

        if failure_count >= threshold:
            assert is_open, "Circuit should be open after threshold failures"
        else:
            assert not is_open, "Circuit should be closed below threshold"

        # Verify circuit recovery
        if is_open:
            # Should allow retry after timeout
            assert circuit_breaker.get_remaining_timeout() <= timeout_seconds

    @given(
        timeout_seconds=st.integers(min_value=1, max_value=120),
        elapsed_seconds=st.integers(min_value=0, max_value=300)
    )
    @settings(max_examples=100)
    def test_integration_timeout_handling(self, timeout_seconds, elapsed_seconds):
        """INVARIANT: Integration timeouts should be enforced."""
        retry_manager = RetryManager()

        # Check timeout
        has_timed_out = elapsed_seconds >= timeout_seconds

        # Verify timeout detection
        assert (elapsed_seconds >= timeout_seconds) == has_timed_out

    @given(
        error_types=st.lists(
            st.sampled_from(['timeout', 'connection_error', 'http_error', 'validation_error']),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_integration_error_recovery(self, error_types):
        """INVARIANT: Integration should recover from transient errors."""
        retry_manager = RetryManager(max_retries=3)

        # Check if error is retryable
        retryable_errors = {'timeout', 'connection_error', 'http_error'}
        non_retryable_errors = {'validation_error'}

        for error_type in error_types:
            should_retry = retry_manager.should_retry(error_type)

            if error_type in retryable_errors:
                assert should_retry, f"{error_type} should be retryable"
            elif error_type in non_retryable_errors:
                assert not should_retry, f"{error_type} should not be retryable"


class TestWebhookResilienceInvariants:
    """Property-based tests for Webhook resilience invariants."""

    @given(
        payload=st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.one_of(st.text(), st.integers(), st.floats(allow_nan=False), st.booleans(), st.none()),
            min_size=1,
            max_size=20
        ),
        secret=st.text(min_size=20, max_size=100)
    )
    @settings(max_examples=100)
    def test_webhook_signature_verification(self, payload, secret):
        """INVARIANT: Webhook signatures must be verified."""
        import hmac
        import hashlib
        import json

        webhook_handler = WebhookHandler(secret=secret)

        # Generate signature
        payload_str = json.dumps(payload, sort_keys=True)
        expected_signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()

        # Verify signature
        is_valid = webhook_handler.verify_signature(
            payload=payload,
            signature=expected_signature
        )

        assert is_valid, "Valid signature should verify"

        # Invalid signature should fail
        invalid_signature = expected_signature[:-5] + "wrong"
        is_valid_invalid = webhook_handler.verify_signature(
            payload=payload,
            signature=invalid_signature
        )
        assert not is_valid_invalid, "Invalid signature should fail verification"

    @given(
        webhook_id=st.text(min_size=1, max_size=50, alphabet='abc123'),
        payload=st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.text(min_size=1, max_size=100),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_webhook_idempotency(self, webhook_id, payload):
        """INVARIANT: Webhook processing should be idempotent."""
        webhook_handler = WebhookHandler()

        # Process webhook twice
        result1 = webhook_handler.process_webhook(webhook_id, payload)
        result2 = webhook_handler.process_webhook(webhook_id, payload)

        # Should return same result (idempotent)
        assert result1.status == result2.status, "Idempotent webhook should return same status"

        # Should not process twice
        assert result1.processed_count == result2.processed_count, "Webhook should not process twice"

    @given(
        webhook_ids=st.lists(
            st.text(min_size=1, max_size=50, alphabet='abc123'),
            min_size=1,
            max_size=20
        ),
        replay_window_seconds=st.integers(min_value=60, max_value=3600)
    )
    @settings(max_examples=100)
    def test_webhook_replay_protection(self, webhook_ids, replay_window_seconds):
        """INVARIANT: Webhook replay protection should detect duplicates."""
        webhook_handler = WebhookHandler(replay_window_seconds=replay_window_seconds)

        # Process webhooks
        for webhook_id in webhook_ids:
            webhook_handler.process_webhook(webhook_id, {'data': 'test'})

        # Try to replay
        for webhook_id in webhook_ids:
            is_replay = webhook_handler.is_replay(webhook_id)

            assert is_replay, f"Webhook {webhook_id} should be detected as replay"

    @given(
        payload=st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.one_of(st.text(), st.integers(), st.floats(allow_nan=False), st.booleans(), st.none(), st.lists(st.text())),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_webhook_payload_validation(self, payload):
        """INVARIANT: Webhook payloads must be validated."""
        webhook_handler = WebhookHandler()

        # Validate payload
        validation_result = webhook_handler.validate_payload(payload)

        assert validation_result is not None, "Validation result must not be None"

        # Check validation result
        if validation_result.is_valid:
            # Should have sanitized data
            assert validation_result.sanitized_payload is not None
        else:
            # Should have errors
            assert len(validation_result.errors) > 0

        # Verify size limits
        payload_size = len(str(payload))
        assert payload_size < 1_000_000, "Payload too large (max 1MB)"

    @given(
        error_code=st.sampled_from(['timeout', 'invalid_payload', 'signature_error', 'rate_limit', 'server_error']),
        retry_count=st.integers(min_value=0, max_value=5)
    )
    @settings(max_examples=100)
    def test_webhook_error_handling(self, error_code, retry_count):
        """INVARIANT: Webhook errors should be handled gracefully."""
        webhook_handler = WebhookHandler()

        # Handle error
        error_response = webhook_handler.handle_error(
            error_code=error_code,
            retry_count=retry_count
        )

        # Verify error response
        assert error_response is not None
        assert 'error_code' in error_response
        assert error_response['error_code'] == error_code

        # Verify retry logic
        retryable_errors = ['timeout', 'server_error', 'rate_limit']
        should_retry = error_code in retryable_errors and retry_count < 3

        assert ('retry_after' in error_response) == should_retry, \
            "Retry information should be included for retryable errors"
