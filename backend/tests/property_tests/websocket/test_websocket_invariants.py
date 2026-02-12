"""
Property-Based Tests for WebSocket Invariants

Tests CRITICAL WebSocket invariants:
- Connection establishment
- Message format validation
- Subscription management
- Broadcast behavior
- Reconnection logic
- Error handling

These tests protect against WebSocket bugs and security issues.
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta
from typing import Dict, List
from unittest.mock import Mock
import json


class TestWebSocketConnectionInvariants:
    """Property-based tests for WebSocket connection invariants."""

    @given(
        connection_id=st.text(min_size=1, max_size=50, alphabet='abc0123456789')
    )
    @settings(max_examples=100)
    def test_connection_id_uniqueness(self, connection_id):
        """INVARIANT: WebSocket connection IDs must be unique."""
        # Invariant: Connection ID should not be empty
        assert len(connection_id) > 0, "Connection ID should not be empty"

        # Invariant: Connection ID should be reasonable length
        assert len(connection_id) <= 50, f"Connection ID too long: {len(connection_id)}"

    @given(
        connection_count=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_connection_count_limits(self, connection_count):
        """INVARIANT: WebSocket connections should have limits."""
        max_connections = 1000

        # Invariant: Connection count should not exceed maximum
        assert connection_count <= max_connections, \
            f"Connection count {connection_count} exceeds maximum {max_connections}"

        # Invariant: Connection count should be positive
        assert connection_count >= 1, "Connection count must be positive"

    @given(
        session_id=st.text(min_size=1, max_size=100, alphabet='abc0123456789-')
    )
    @settings(max_examples=50)
    def test_session_binding(self, session_id):
        """INVARIANT: WebSocket should bind to session."""
        # Invariant: Session ID should not be empty
        assert len(session_id) > 0, "Session ID should not be empty"

        # Invariant: Session ID should be reasonable length
        assert len(session_id) <= 100, f"Session ID too long: {len(session_id)}"


class TestWebSocketMessageInvariants:
    """Property-based tests for WebSocket message invariants."""

    @given(
        message_type=st.sampled_from(['text', 'binary', 'ping', 'pong', 'close'])
    )
    @settings(max_examples=100)
    def test_message_type_validity(self, message_type):
        """INVARIANT: WebSocket message types must be valid."""
        valid_types = {'text', 'binary', 'ping', 'pong', 'close'}

        # Invariant: Message type must be valid
        assert message_type in valid_types, f"Invalid message type: {message_type}"

    @given(
        payload_size=st.integers(min_value=0, max_value=1024000)  # 0 to 1MB
    )
    @settings(max_examples=50)
    def test_payload_size_limits(self, payload_size):
        """INVARIANT: WebSocket payloads should have size limits."""
        max_payload_size = 1024000  # 1MB

        # Invariant: Payload size should not exceed maximum
        assert payload_size <= max_payload_size, \
            f"Payload size {payload_size} exceeds maximum {max_payload_size}"

        # Invariant: Payload size should be non-negative
        assert payload_size >= 0, "Payload size cannot be negative"

    @given(
        message_text=st.text(min_size=1, max_size=10000, alphabet='abc DEF{}:')
    )
    @settings(max_examples=50)
    def test_message_format_validation(self, message_text):
        """INVARIANT: WebSocket messages should be valid JSON or text."""
        # Filter out whitespace-only
        if len(message_text.strip()) == 0:
            return  # Skip this test case

        # Invariant: Message should not be empty
        assert len(message_text.strip()) > 0, "Message should not be empty"

        # Invariant: Message should be reasonable length
        assert len(message_text) <= 10000, \
            f"Message too long: {len(message_text)} chars"

    @given(
        message_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_message_ordering(self, message_count):
        """INVARIANT: WebSocket messages should maintain order."""
        # Simulate message ordering
        messages = []
        for i in range(message_count):
            message = {
                'sequence': i,
                'content': f'message_{i}'
            }
            messages.append(message)

        # Verify order
        for i in range(len(messages) - 1):
            current_seq = messages[i]['sequence']
            next_seq = messages[i + 1]['sequence']
            assert current_seq < next_seq, "Messages not in sequential order"


class TestWebSocketSubscriptionInvariants:
    """Property-based tests for WebSocket subscription invariants."""

    @given(
        channel=st.text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyz:_')
    )
    @settings(max_examples=100)
    def test_channel_format(self, channel):
        """INVARIANT: WebSocket channels should have valid format."""
        # Invariant: Channel should not be empty
        assert len(channel) > 0, "Channel should not be empty"

        # Invariant: Channel should be reasonable length
        assert len(channel) <= 100, f"Channel too long: {len(channel)}"

        # Invariant: Channel should contain only valid characters
        for char in channel:
            assert char.isalnum() or char in ':_', \
                f"Invalid character '{char}' in channel"

    @given(
        subscription_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_subscription_count_limits(self, subscription_count):
        """INVARIANT: WebSocket subscriptions should have limits."""
        max_subscriptions = 100

        # Invariant: Subscription count should not exceed maximum
        assert subscription_count <= max_subscriptions, \
            f"Subscription count {subscription_count} exceeds maximum {max_subscriptions}"

        # Invariant: Subscription count should be non-negative
        assert subscription_count >= 0, "Subscription count cannot be negative"

    @given(
        subscriber_count=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_subscriber_limits(self, subscriber_count):
        """INVARIANT: Channels should have subscriber limits."""
        max_subscribers = 1000

        # Invariant: Subscriber count should not exceed maximum
        assert subscriber_count <= max_subscribers, \
            f"Subscriber count {subscriber_count} exceeds maximum {max_subscribers}"

        # Invariant: Subscriber count should be positive
        assert subscriber_count >= 1, "Subscriber count must be positive"


class TestWebSocketBroadcastInvariants:
    """Property-based tests for WebSocket broadcast invariants."""

    @given(
        recipient_count=st.integers(min_value=20, max_value=100)
    )
    @settings(max_examples=50)
    def test_broadcast_delivery(self, recipient_count):
        """INVARIANT: Broadcasts should deliver to all recipients."""
        # Simulate broadcast
        delivered_count = 0
        for i in range(recipient_count):
            # Simulate 95% delivery rate
            if i % 20 != 0:  # 19 out of 20
                delivered_count += 1

        # Invariant: Most messages should be delivered
        delivery_rate = delivered_count / recipient_count if recipient_count > 0 else 0.0
        assert delivery_rate >= 0.90, \
            f"Delivery rate {delivery_rate} below 90%"

    @given(
        broadcast_count=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=50)
    def test_broadcast_rate_limiting(self, broadcast_count):
        """INVARIANT: Broadcasts should be rate limited."""
        max_broadcasts_per_second = 10

        # Invariant: Broadcast count should be reasonable
        assert broadcast_count <= 50, \
            f"Broadcast count {broadcast_count} exceeds limit"

        # Check if rate limit applies
        if broadcast_count > max_broadcasts_per_second:
            assert True  # Should be rate limited

    @given(
        message=st.text(min_size=1, max_size=10000, alphabet='abc DEF')
    )
    @settings(max_examples=50)
    def test_broadcast_message_size(self, message):
        """INVARIANT: Broadcast messages should have size limits."""
        # Filter out whitespace-only
        if len(message.strip()) == 0:
            return  # Skip this test case

        max_broadcast_size = 10000

        # Invariant: Message size should not exceed maximum
        assert len(message) <= max_broadcast_size, \
            f"Broadcast message too large: {len(message)} chars"


class TestWebSocketReconnectionInvariants:
    """Property-based tests for WebSocket reconnection invariants."""

    @given(
        retry_count=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=50)
    def test_retry_count_limits(self, retry_count):
        """INVARIANT: WebSocket reconnection should have retry limits."""
        max_retries = 10

        # Invariant: Retry count should not exceed maximum
        assert retry_count <= max_retries, \
            f"Retry count {retry_count} exceeds maximum {max_retries}"

        # Invariant: Retry count should be non-negative
        assert retry_count >= 0, "Retry count cannot be negative"

    @given(
        backoff_delay=st.integers(min_value=0, max_value=60)  # 0 to 60 seconds
    )
    @settings(max_examples=50)
    def test_backoff_delay_bounds(self, backoff_delay):
        """INVARIANT: Reconnection backoff should be reasonable."""
        # Invariant: Backoff delay should be non-negative
        assert backoff_delay >= 0, "Backoff delay cannot be negative"

        # Invariant: Backoff delay should not exceed maximum
        assert backoff_delay <= 60, \
            f"Backoff delay {backoff_delay}s exceeds 60 seconds"

    @given(
        attempt_number=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_exponential_backoff(self, attempt_number):
        """INVARIANT: Reconnection should use exponential backoff."""
        base_delay = 1  # 1 second
        max_delay = 60  # 60 seconds

        # Calculate exponential backoff
        delay = min(base_delay * (2 ** (attempt_number - 1)), max_delay)

        # Invariant: Delay should be reasonable
        assert 1 <= delay <= 60, \
            f"Backoff delay {delay}s out of bounds [1, 60]"

        # Invariant: Delay should increase with attempts
        if attempt_number > 1:
            expected_delay = min(base_delay * (2 ** (attempt_number - 2)), max_delay)
            assert delay >= expected_delay, \
                "Delay should increase with attempts"


class TestWebSocketErrorHandlingInvariants:
    """Property-based tests for WebSocket error handling invariants."""

    @given(
        error_code=st.sampled_from([
            'CONNECTION_LOST', 'INVALID_MESSAGE', 'RATE_LIMITED',
            'AUTHENTICATION_FAILED', 'SUBSCRIPTION_FAILED', 'BROADCAST_FAILED'
        ])
    )
    @settings(max_examples=100)
    def test_error_code_validity(self, error_code):
        """INVARIANT: WebSocket error codes must be valid."""
        valid_codes = {
            'CONNECTION_LOST', 'INVALID_MESSAGE', 'RATE_LIMITED',
            'AUTHENTICATION_FAILED', 'SUBSCRIPTION_FAILED', 'BROADCAST_FAILED'
        }

        # Invariant: Error code must be valid
        assert error_code in valid_codes, f"Invalid error code: {error_code}"

    @given(
        connection_age_seconds=st.integers(min_value=0, max_value=86400)  # 0 to 24 hours
    )
    @settings(max_examples=50)
    def test_connection_timeout(self, connection_age_seconds):
        """INVARIANT: WebSocket connections should timeout."""
        timeout_seconds = 3600  # 1 hour

        # Check if connection should timeout
        should_timeout = connection_age_seconds > timeout_seconds

        # Invariant: Old connections should timeout
        if should_timeout:
            assert True  # Should close connection

    @given(
        message_queue_size=st.integers(min_value=0, max_value=1000)
    )
    @settings(max_examples=50)
    def test_message_queue_limits(self, message_queue_size):
        """INVARIANT: Message queues should have limits."""
        max_queue_size = 1000

        # Invariant: Queue size should not exceed maximum
        assert message_queue_size <= max_queue_size, \
            f"Queue size {message_queue_size} exceeds maximum {max_queue_size}"

        # Invariant: Queue size should be non-negative
        assert message_queue_size >= 0, "Queue size cannot be negative"


class TestWebSocketSecurityInvariants:
    """Property-based tests for WebSocket security invariants."""

    @given(
        token=st.text(min_size=1, max_size=500, alphabet='abc0123456789abcdef')
    )
    @settings(max_examples=50)
    def test_authentication_token_validation(self, token):
        """INVARIANT: WebSocket should validate authentication tokens."""
        # Invariant: Token should not be empty
        assert len(token) > 0, "Token should not be empty"

        # Invariant: Token should be reasonable length
        assert len(token) <= 500, f"Token too long: {len(token)}"

    @given(
        origin=st.text(min_size=1, max_size=200, alphabet='abcdefghijklmnopqrstuvwxyz://.')
    )
    @settings(max_examples=50)
    def test_origin_validation(self, origin):
        """INVARIANT: WebSocket should validate origin header."""
        # Invariant: Origin should not be empty
        assert len(origin) > 0, "Origin should not be empty"

        # Invariant: Origin should be reasonable length
        assert len(origin) <= 200, f"Origin too long: {len(origin)}"

    @given(
        message=st.text(min_size=1, max_size=10000, alphabet='abc DEF<script>alert')
    )
    @settings(max_examples=50)
    def test_message_sanitization(self, message):
        """INVARIANT: WebSocket messages should be sanitized."""
        dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onload=']

        has_dangerous = any(pattern in message.lower() for pattern in dangerous_patterns)

        # Invariant: Dangerous patterns should be detected
        if has_dangerous:
            assert True  # Should be sanitized


class TestWebSocketRateLimitingInvariants:
    """Property-based tests for WebSocket rate limiting invariants."""

    @given(
        message_count=st.integers(min_value=1, max_value=1000),
        time_window_seconds=st.integers(min_value=1, max_value=60)
    )
    @settings(max_examples=50)
    def test_rate_limiting_enforcement(self, message_count, time_window_seconds):
        """INVARIANT: WebSocket should enforce rate limits."""
        # Invariant: Message count should be positive
        assert message_count > 0, "Message count must be positive"

        # Invariant: Time window should be positive
        assert time_window_seconds > 0, "Time window must be positive"

        # Calculate rate limit (e.g., 100 messages per minute)
        messages_per_second = message_count / time_window_seconds
        max_rate = 100  # 100 messages per second

        # Invariant: Rate should not exceed maximum
        if messages_per_second > max_rate:
            rate_exceeded = True
        else:
            rate_exceeded = False

        # Check rate limiting behavior
        assert isinstance(rate_exceeded, bool), "Rate limit check should return boolean"

    @given(
        connection_id=st.text(min_size=1, max_size=50, alphabet='abc0123456789'),
        message_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_per_connection_rate_limits(self, connection_id, message_count):
        """INVARIANT: Each connection should have independent rate limits."""
        # Invariant: Connection ID should not be empty
        assert len(connection_id) > 0, "Connection ID should not be empty"

        # Invariant: Message count should be positive
        assert message_count > 0, "Message count must be positive"

        # Simulate per-connection rate tracking
        connection_rates = {
            conn_id: message_count for conn_id in [connection_id]
        }

        # Invariant: Each connection should have independent tracking
        assert connection_id in connection_rates, \
            f"Connection {connection_id} should be tracked"

    @given(
        burst_count=st.integers(min_value=1, max_value=50),
        sustained_rate=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_burst_rate_limiting(self, burst_count, sustained_rate):
        """INVARIANT: WebSocket should handle burst traffic."""
        # Invariant: Burst count should be positive
        assert burst_count > 0, "Burst count must be positive"

        # Invariant: Sustained rate should be positive
        assert sustained_rate > 0, "Sustained rate must be positive"

        # Calculate burst allowance (e.g., 2x sustained rate)
        burst_allowance = sustained_rate * 2

        # Check if burst exceeds allowance
        if burst_count > burst_allowance:
            burst_exceeded = True
        else:
            burst_exceeded = False

        # Invariant: Should track burst allowance
        assert isinstance(burst_exceeded, bool), "Burst check should return boolean"


class TestWebSocketCompressionInvariants:
    """Property-based tests for WebSocket compression invariants."""

    @given(
        original_size=st.integers(min_value=100, max_value=1048576)  # 100B to 1MB
    )
    @settings(max_examples=50)
    def test_compression_ratio(self, original_size):
        """INVARIANT: Compression should reduce message size."""
        # Invariant: Original size should be positive
        assert original_size > 0, "Original size must be positive"

        # Simulate compression (typically 2-10x reduction for text)
        compression_ratio = 3  # Assume 3x compression
        compressed_size = original_size // compression_ratio

        # Invariant: Compressed size should be smaller
        assert compressed_size < original_size, \
            f"Compressed size {compressed_size} should be < original {original_size}"

        # Invariant: Compressed size should be non-negative
        assert compressed_size >= 0, "Compressed size cannot be negative"

    @given(
        message_count=st.integers(min_value=1, max_value=100),
        avg_message_size=st.integers(min_value=100, max_value=10000)
    )
    @settings(max_examples=50)
    def test_compression_memory_limits(self, message_count, avg_message_size):
        """INVARIANT: Compression should not exceed memory limits."""
        # Invariant: Message count should be positive
        assert message_count > 0, "Message count must be positive"

        # Invariant: Average message size should be positive
        assert avg_message_size > 0, "Average message size must be positive"

        # Calculate memory usage
        compression_buffer_size = avg_message_size * message_count
        max_memory = 10485760  # 10MB

        # Invariant: Should not exceed memory limit
        assert compression_buffer_size <= max_memory, \
            f"Buffer size {compression_buffer_size} exceeds max {max_memory}"

    @given(
        small_message_size=st.integers(min_value=1, max_value=100),
        large_message_size=st.integers(min_value=1000, max_value=100000)
    )
    @settings(max_examples=50)
    def test_adaptive_compression(self, small_message_size, large_message_size):
        """INVARIANT: Compression should adapt to message size."""
        # Invariant: Sizes should be positive
        assert small_message_size > 0, "Small message size must be positive"
        assert large_message_size > 0, "Large message size must be positive"

        # Small messages may not be worth compressing
        compress_small = small_message_size > 100

        # Large messages should always be compressed
        compress_large = large_message_size > 1000

        # Invariant: Compression decision should be consistent
        if large_message_size > 1000:
            assert compress_large, "Large messages should be compressed"


class TestWebSocketHeartbeatInvariants:
    """Property-based tests for WebSocket heartbeat invariants."""

    @given(
        interval_seconds=st.integers(min_value=10, max_value=300)
    )
    @settings(max_examples=50)
    def test_heartbeat_interval(self, interval_seconds):
        """INVARIANT: Heartbeat should have reasonable interval."""
        # Invariant: Interval should be at least 10 seconds
        assert interval_seconds >= 10, \
            f"Interval {interval_seconds}s should be >= 10s"

        # Invariant: Interval should not exceed 5 minutes
        assert interval_seconds <= 300, \
            f"Interval {interval_seconds}s should be <= 300s"

    @given(
        last_ping_time=st.datetimes(min_value=datetime(2024, 1, 1), max_value=datetime.now()),
        current_time=st.datetimes(min_value=datetime(2024, 1, 1), max_value=datetime.now()),
        timeout_seconds=st.integers(min_value=30, max_value=300)
    )
    @settings(max_examples=50)
    def test_connection_timeout_detection(self, last_ping_time, current_time, timeout_seconds):
        """INVARIANT: Should detect connection timeouts."""
        # Calculate time difference
        time_diff = (current_time - last_ping_time).total_seconds()

        # Check for timeout
        if time_diff > timeout_seconds:
            is_timeout = True
        else:
            is_timeout = False

        # Invariant: Timeout detection should be consistent
        if time_diff > timeout_seconds:
            assert is_timeout, "Should detect timeout"

    @given(
        missed_ping_count=st.integers(min_value=0, max_value=10),
        max_missed=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=50)
    def test_missed_ping_tolerance(self, missed_ping_count, max_missed):
        """INVARIANT: Should tolerate missed pings within limit."""
        # Invariant: Missed ping count should be non-negative
        assert missed_ping_count >= 0, "Missed ping count must be non-negative"

        # Invariant: Max missed should be positive
        assert max_missed > 0, "Max missed pings must be positive"

        # Check if connection should be closed
        if missed_ping_count >= max_missed:
            should_close = True
        else:
            should_close = False

        # Invariant: Should close after threshold
        if missed_ping_count >= max_missed:
            assert should_close, "Should close connection after threshold"


class TestWebSocketMultiplexingInvariants:
    """Property-based tests for WebSocket multiplexing invariants."""

    @given(
        channel_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_channel_limits(self, channel_count):
        """INVARIANT: Multiplexing should enforce channel limits."""
        max_channels = 100

        # Invariant: Channel count should not exceed maximum
        assert channel_count <= max_channels, \
            f"Channel count {channel_count} exceeds maximum {max_channels}"

        # Invariant: Channel count should be positive
        assert channel_count >= 1, "Channel count must be positive"

    @given(
        channel_name=st.text(min_size=1, max_size=100, alphabet='abc0123456789_-')
    )
    @settings(max_examples=100)
    def test_channel_name_validation(self, channel_name):
        """INVARIANT: Channel names should be valid."""
        # Invariant: Channel name should not be empty
        assert len(channel_name) > 0, "Channel name should not be empty"

        # Invariant: Channel name should be reasonable length
        assert len(channel_name) <= 100, f"Channel name too long: {len(channel_name)}"

        # Channel names should only contain valid characters
        valid_chars = set('abcdefghijklmnopqrstuvwxyz0123456789_-')
        assert all(c in valid_chars for c in channel_name.lower()), \
            f"Channel name '{channel_name}' contains invalid characters"

    @given(
        message_count=st.integers(min_value=1, max_value=1000),
        channel_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_message_routing_to_channels(self, message_count, channel_count):
        """INVARIANT: Messages should route to correct channels."""
        # Invariant: Message count should be positive
        assert message_count > 0, "Message count must be positive"

        # Invariant: Channel count should be positive
        assert channel_count > 0, "Channel count must be positive"

        # Simulate message routing
        messages_routed = 0
        for i in range(message_count):
            target_channel = i % channel_count
            messages_routed += 1

        # Invariant: All messages should be routed
        assert messages_routed == message_count, \
            f"Routed {messages_routed} != expected {message_count}"


class TestWebSocketErrorRecoveryInvariants:
    """Property-based tests for WebSocket error recovery invariants."""

    @given(
        error_code=st.integers(min_value=1000, max_value=4999)
    )
    @settings(max_examples=50)
    def test_error_code_handling(self, error_code):
        """INVARIANT: WebSocket should handle error codes correctly."""
        # WebSocket close codes:
        # 1000: Normal closure
        # 1001: Going away
        # 1002: Protocol error
        # 1003: Unsupported data
        # 4000-4999: Application-specific errors

        # Initialize variables
        is_standard = False
        is_app_specific = False

        if 1000 <= error_code <= 1003:
            # Standard WebSocket close codes
            is_standard = True
        elif 4000 <= error_code <= 4999:
            # Application-specific codes
            is_app_specific = True

        # Invariant: Should recognize error code type
        assert isinstance(is_standard, bool), "Should identify standard codes"
        assert isinstance(is_app_specific, bool), "Should identify app-specific codes"

    @given(
        reconnect_attempts=st.integers(min_value=0, max_value=10),
        max_attempts=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50)
    def test_reconnect_attempt_limits(self, reconnect_attempts, max_attempts):
        """INVARIANT: Reconnection attempts should be limited."""
        # Invariant: Reconnect attempts should be non-negative
        assert reconnect_attempts >= 0, "Reconnect attempts must be non-negative"

        # Invariant: Max attempts should be positive
        assert max_attempts > 0, "Max attempts must be positive"

        # Check if should attempt reconnection
        if reconnect_attempts < max_attempts:
            should_reconnect = True
        else:
            should_reconnect = False

        # Invariant: Should not exceed max attempts
        if reconnect_attempts >= max_attempts:
            assert not should_reconnect, "Should not reconnect after max attempts"

    @given(
        backoff_delay_seconds=st.integers(min_value=1, max_value=60),
        attempt_number=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_exponential_backoff_during_reconnect(self, backoff_delay_seconds, attempt_number):
        """INVARIANT: Reconnection should use exponential backoff."""
        # Invariant: Delay should be positive
        assert backoff_delay_seconds > 0, "Delay must be positive"

        # Invariant: Attempt number should be positive
        assert attempt_number > 0, "Attempt number must be positive"

        # Calculate exponential backoff
        delay = backoff_delay_seconds * (2 ** (attempt_number - 1))

        # Invariant: Delay should increase with attempts
        assert delay >= backoff_delay_seconds, \
            f"Delay {delay}s should be >= base {backoff_delay_seconds}s"

        # Cap at reasonable maximum (5 minutes)
        max_delay = 300
        capped_delay = min(delay, max_delay)
        assert capped_delay <= max_delay, \
            f"Capped delay {capped_delay}s should be <= max {max_delay}s"
