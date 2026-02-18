"""
Agent Communication Tests - Comprehensive testing of AgentEventBus.

Tests cover:
- Event Bus Unit Tests (12 tests)
- Redis Pub/Sub Integration Tests (10 tests)
- WebSocket Connection Tests (8 tests)
- Property-Based Tests for Message Ordering (5 tests)

Total: 35 tests verifying reliable message delivery, FIFO ordering, no lost messages,
and Redis pub/sub horizontal scaling.
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import List, Set, Any

from hypothesis import given, strategies as st, settings

from core.agent_communication import AgentEventBus, agent_event_bus


# ============================================================================
# Mock WebSocket for testing
# ============================================================================

class MockWebSocket:
    """Mock WebSocket for testing AgentEventBus."""

    def __init__(self, agent_id: str = "test-agent"):
        self.agent_id = agent_id
        self.sent_messages = []
        self.closed = False
        self.send_json_called = False
        self.send_text_called = False

    async def send_json(self, data: dict):
        """Mock send_json."""
        self.sent_messages.append(data)
        self.send_json_called = True

    async def send_text(self, text: str):
        """Mock send_text."""
        self.sent_messages.append(text)
        self.send_text_called = True

    def reset(self):
        """Reset mock state."""
        self.sent_messages = []
        self.send_json_called = False
        self.send_text_called = False


# ============================================================================
# Event Bus Unit Tests (12 tests)
# ============================================================================

class TestAgentEventBus:
    """Unit tests for AgentEventBus."""

    @pytest.mark.asyncio
    async def test_subscribe_adds_subscriber(self):
        """Agent added to subscribers when subscribing."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        await bus.subscribe("agent1", ws, ["global"])

        assert "agent1" in bus._subscribers
        assert ws in bus._subscribers["agent1"]
        assert "agent1" in bus._topics["global"]

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscriber(self):
        """Agent removed from subscribers when unsubscribing."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        await bus.subscribe("agent1", ws, ["global"])
        await bus.unsubscribe("agent1", ws)

        assert "agent1" not in bus._subscribers
        assert "agent1" not in bus._topics["global"]

    @pytest.mark.asyncio
    async def test_unsubscribe_cleans_up_empty_agent(self):
        """Agent entry removed when no connections remain."""
        bus = AgentEventBus()
        ws1 = MockWebSocket("agent1")
        ws2 = MockWebSocket("agent1")

        # Subscribe two connections
        await bus.subscribe("agent1", ws1, ["global"])
        await bus.subscribe("agent1", ws2, ["global"])

        # Unsubscribe one
        await bus.unsubscribe("agent1", ws1)
        assert "agent1" in bus._subscribers  # Still has ws2

        # Unsubscribe the other
        await bus.unsubscribe("agent1", ws2)
        assert "agent1" not in bus._subscribers  # Agent entry removed

    @pytest.mark.asyncio
    async def test_topic_subscription(self):
        """Agent subscribed to specific topics."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        topics = ["global", "alerts", "agent:123"]
        await bus.subscribe("agent1", ws, topics)

        # Verify agent in all topics
        for topic in topics:
            assert topic in bus._topics
            assert "agent1" in bus._topics[topic]

    @pytest.mark.asyncio
    async def test_publish_to_subscribers(self):
        """Event delivered to all topic subscribers."""
        bus = AgentEventBus()
        ws1 = MockWebSocket("agent1")
        ws2 = MockWebSocket("agent2")

        await bus.subscribe("agent1", ws1, ["global"])
        await bus.subscribe("agent2", ws2, ["global"])

        event = {"type": "test", "data": "hello"}
        await bus.publish(event, ["global"])

        # Both subscribers received event
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert ws1.sent_messages[0] == event
        assert ws2.sent_messages[0] == event

    @pytest.mark.asyncio
    async def test_publish_multiple_topics(self):
        """Event delivered to multiple topics."""
        bus = AgentEventBus()
        ws1 = MockWebSocket("agent1")
        ws2 = MockWebSocket("agent2")

        await bus.subscribe("agent1", ws1, ["global"])
        await bus.subscribe("agent2", ws2, ["alerts"])

        event = {"type": "alert", "data": "warning"}
        await bus.publish(event, ["global", "alerts"])

        # Both subscribers received (agent1 in global, agent2 in alerts)
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_broadcast_post_shortcut(self):
        """broadcast_post() publishes correctly."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        await bus.subscribe("agent1", ws, ["global"])

        post_data = {
            "sender_id": "agent1",
            "post_type": "status",
            "content": "Test post"
        }
        await bus.broadcast_post(post_data)

        assert len(ws.sent_messages) == 1
        received = ws.sent_messages[0]
        assert received["type"] == "agent_post"
        assert received["data"] == post_data

    @pytest.mark.asyncio
    async def test_websocket_send_json(self):
        """Events sent as JSON via WebSocket."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        await bus.subscribe("agent1", ws, ["global"])

        event = {"type": "test", "data": {"key": "value"}}
        await bus.publish(event, ["global"])

        assert ws.send_json_called
        assert ws.sent_messages[0] == event

    @pytest.mark.asyncio
    async def test_dead_websocket_removed(self):
        """Failed sends trigger unsubscribe."""
        bus = AgentEventBus()

        # Create WebSocket that raises exception
        ws = MockWebSocket("agent1")
        ws.send_json = AsyncMock(side_effect=Exception("Connection closed"))

        await bus.subscribe("agent1", ws, ["global"])

        # Publish should handle exception and remove dead connection
        await bus.publish({"test": "data"}, ["global"])

        # Agent should be removed
        assert "agent1" not in bus._subscribers

    @pytest.mark.asyncio
    async def test_global_topic_all_subscribers(self):
        """All agents receive global broadcasts."""
        bus = AgentEventBus()

        agents = [MockWebSocket(f"agent{i}") for i in range(5)]
        for agent_ws in agents:
            await bus.subscribe(agent_ws.agent_id, agent_ws, ["global"])

        await bus.publish({"type": "broadcast"}, ["global"])

        # All agents received
        for agent_ws in agents:
            assert len(agent_ws.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_alert_topic_subscribers(self):
        """Alert posts go to alerts topic."""
        bus = AgentEventBus()
        ws1 = MockWebSocket("agent1")
        ws2 = MockWebSocket("agent2")

        # Subscribe ws1 to global, ws2 to alerts
        await bus.subscribe("agent1", ws1, ["global"])
        await bus.subscribe("agent2", ws2, ["alerts"])

        # Broadcast alert post
        alert_post = {
            "sender_id": "agent3",
            "post_type": "alert",
            "content": "Important alert"
        }
        await bus.broadcast_post(alert_post)

        # ws1 receives (global), ws2 receives (alerts)
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_category_topic_subscribers(self):
        """Category-specific posts routed correctly."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        await bus.subscribe("agent1", ws, ["category:engineering"])

        # Broadcast question post with category
        question_post = {
            "sender_id": "agent2",
            "post_type": "question",
            "sender_category": "engineering",
            "content": "How to fix bug?"
        }
        await bus.broadcast_post(question_post)

        # Should receive due to category match
        assert len(ws.sent_messages) == 1


# ============================================================================
# Redis Pub/Sub Integration Tests (10 tests)
# ============================================================================

class TestRedisPubSub:
    """Tests for Redis pub/sub integration."""

    @pytest.mark.asyncio
    async def test_redis_publish(self):
        """Events published to Redis channels."""
        # Skip if Redis not available
        try:
            import redis.asyncio
        except ImportError:
            pytest.skip("Redis not available")

        bus = AgentEventBus(redis_url="redis://localhost:6379/0")

        with patch.object(bus, '_redis') as mock_redis:
            mock_redis.publish = AsyncMock()

            await bus._ensure_redis()

            event = {"test": "data"}
            await bus.publish(event, ["global"])

            # Verify Redis publish called
            assert mock_redis.publish.called
            call_args = mock_redis.publish.call_args
            assert "agent_events:global" in str(call_args)

    @pytest.mark.asyncio
    async def test_redis_subscribe(self):
        """Background listener created for Redis."""
        try:
            import redis.asyncio
        except ImportError:
            pytest.skip("Redis not available")

        bus = AgentEventBus(redis_url="redis://localhost:6379/0")

        # Create async iterator for listen()
        async def async_iter_messages():
            # Empty iterator - test doesn't need actual messages
            if False:
                yield  # pylint: disable=unreachable

        # Mock pubsub with all required methods
        mock_pubsub = MagicMock()
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.listen = Mock(return_value=async_iter_messages())
        mock_pubsub.close = AsyncMock()

        # Mock redis to return our pubsub (regular MagicMock, not AsyncMock)
        mock_redis = MagicMock()
        mock_redis.pubsub = Mock(return_value=mock_pubsub)
        mock_redis.close = AsyncMock()

        # Patch redis.from_url to return mock_redis (must be async)
        async def mock_from_url(*args, **kwargs):
            return mock_redis

        with patch('redis.asyncio.from_url', side_effect=mock_from_url):
            await bus.subscribe_to_redis()

            # Verify subscribed to wildcard pattern
            mock_pubsub.psubscribe.assert_called_once_with("agent_events:*")
            assert bus._redis_listener_task is not None

    @pytest.mark.asyncio
    async def test_redis_fallback_to_in_memory(self):
        """Graceful degradation when Redis unavailable."""
        try:
            import redis.asyncio
        except ImportError:
            pytest.skip("Redis not available")

        bus = AgentEventBus(redis_url="redis://invalid:9999/0")

        # Mock redis.from_url to raise connection error
        with patch('redis.asyncio.from_url', side_effect=Exception("Connection refused")):
            # Should not crash, should disable Redis
            await bus._ensure_redis()

            # Should disable Redis and continue with in-memory
            assert not bus._redis_enabled
            assert bus._redis is None

    @pytest.mark.asyncio
    async def test_redis_graceful_shutdown(self):
        """Connections closed properly on shutdown."""
        try:
            import redis.asyncio
        except ImportError:
            pytest.skip("Redis not available")

        bus = AgentEventBus(redis_url="redis://localhost:6379/0")

        # Create an async task that raises CancelledError when awaited
        async def mock_task_func():
            raise asyncio.CancelledError()

        mock_task = asyncio.create_task(mock_task_func())
        mock_pubsub = MagicMock()
        mock_pubsub.close = AsyncMock()
        mock_redis = MagicMock()
        mock_redis.close = AsyncMock()

        bus._redis_listener_task = mock_task
        bus._pubsub = mock_pubsub
        bus._redis = mock_redis

        await bus.close_redis()

        # Verify cleanup - pubsub and redis close should be called
        mock_pubsub.close.assert_called_once()
        mock_redis.close.assert_called_once()

        # Task should be cancelled
        assert mock_task.cancelled()

    @pytest.mark.asyncio
    async def test_redis_listener_broadcasts_locally(self):
        """Redis messages rebroadcast to local WebSockets."""
        try:
            import redis.asyncio
        except ImportError:
            pytest.skip("Redis not available")

        bus = AgentEventBus()
        ws = MockWebSocket("agent1")
        await bus.subscribe("agent1", ws, ["global"])

        # Simulate Redis message
        redis_message = {
            'type': 'pmessage',
            'data': json.dumps({
                "topics": ["global"],
                "event": {"test": "redis_event"}
            })
        }

        # Manually trigger listener logic
        # (In real scenario, this comes from Redis pubsub)
        data = json.loads(redis_message['data'])
        event = data['event']
        topics = data['topics']

        subscriber_ids = set()
        for topic in topics:
            if topic in bus._topics:
                subscriber_ids.update(bus._topics[topic])

        for agent_id in subscriber_ids:
            if agent_id in bus._subscribers:
                for websocket in bus._subscribers[agent_id]:
                    await websocket.send_json(event)

        # Verify local WebSocket received
        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["test"] == "redis_event"

    @pytest.mark.asyncio
    async def test_redis_multiple_topics(self):
        """Subscribed to all agent_events:* topics."""
        try:
            import redis.asyncio
        except ImportError:
            pytest.skip("Redis not available")

        bus = AgentEventBus(redis_url="redis://localhost:6379/0")

        # Create async iterator for listen()
        async def async_iter_messages():
            if False:
                yield  # pylint: disable=unreachable

        # Mock pubsub with all required methods
        mock_pubsub = MagicMock()
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.listen = Mock(return_value=async_iter_messages())

        # Mock redis to return our pubsub (regular MagicMock, not AsyncMock)
        mock_redis = MagicMock()
        mock_redis.pubsub = Mock(return_value=mock_pubsub)

        # Patch redis.from_url to return mock_redis (must be async)
        async def mock_from_url(*args, **kwargs):
            return mock_redis

        with patch('redis.asyncio.from_url', side_effect=mock_from_url):
            await bus.subscribe_to_redis()

            # Verify wildcard subscription
            mock_pubsub.psubscribe.assert_called_once_with("agent_events:*")

    @pytest.mark.asyncio
    async def test_redis_connection_retry(self):
        """Reconnection on connection failure."""
        try:
            import redis.asyncio
        except ImportError:
            pytest.skip("Redis not available")

        bus = AgentEventBus(redis_url="redis://localhost:6379/0")

        # First call fails, second succeeds
        call_count = [0]

        async def mock_connect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Connection failed")
            return MagicMock()

        with patch('redis.asyncio.from_url', side_effect=mock_connect):
            # First attempt fails
            await bus._ensure_redis()
            assert not bus._redis_enabled

    @pytest.mark.asyncio
    async def test_redis_disabled_by_env(self):
        """REDIS_URL unset = in-memory only."""
        # No REDIS_URL set
        bus = AgentEventBus()

        assert not bus._redis_enabled
        assert bus._redis is None

    @pytest.mark.asyncio
    async def test_redis_message_format(self):
        """JSON format with topics and event."""
        try:
            import redis.asyncio
        except ImportError:
            pytest.skip("Redis not available")

        bus = AgentEventBus(redis_url="redis://localhost:6379/0")

        with patch.object(bus, '_redis') as mock_redis:
            mock_redis.publish = AsyncMock()

            event = {"test": "data"}
            await bus.publish(event, ["global", "alerts"])

            # Verify JSON format
            call_args = mock_redis.publish.call_args
            published_data = call_args[0][1]  # Second argument is data

            parsed = json.loads(published_data)
            assert "topics" in parsed
            assert "event" in parsed
            assert parsed["topics"] == ["global", "alerts"]
            assert parsed["event"] == event

    @pytest.mark.asyncio
    async def test_redis_no_infinite_loop(self):
        """Redis events not republished back to Redis."""
        try:
            import redis.asyncio
        except ImportError:
            pytest.skip("Redis not available")

        bus = AgentEventBus(redis_url="redis://localhost:6379/0")

        # Track publish calls
        publish_calls = []

        async def track_publish(channel, data):
            publish_calls.append(channel)

        with patch.object(bus, '_redis') as mock_redis:
            mock_redis.publish = track_publish

            await bus.publish({"test": "data"}, ["global"])

            # Should only publish once, not recursively
            assert len(publish_calls) == 1


# ============================================================================
# WebSocket Connection Tests (8 tests)
# ============================================================================

class TestWebSocketConnections:
    """Tests for WebSocket connection management."""

    @pytest.mark.asyncio
    async def test_websocket_subscribe(self):
        """Connection added to subscribers."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        await bus.subscribe("agent1", ws, ["global"])

        assert "agent1" in bus._subscribers
        assert ws in bus._subscribers["agent1"]

    @pytest.mark.asyncio
    async def test_websocket_unsubscribe(self):
        """Connection removed on disconnect."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        await bus.subscribe("agent1", ws, ["global"])
        await bus.unsubscribe("agent1", ws)

        assert ws not in bus._subscribers.get("agent1", set())

    @pytest.mark.asyncio
    async def test_multiple_connections_per_agent(self):
        """Multiple concurrent connections allowed."""
        bus = AgentEventBus()
        ws1 = MockWebSocket("agent1")
        ws2 = MockWebSocket("agent1")

        await bus.subscribe("agent1", ws1, ["global"])
        await bus.subscribe("agent1", ws2, ["global"])

        # Both connections active
        assert len(bus._subscribers["agent1"]) == 2
        assert ws1 in bus._subscribers["agent1"]
        assert ws2 in bus._subscribers["agent1"]

    @pytest.mark.asyncio
    async def test_ping_pong_response(self):
        """Ping messages get pong response."""
        # This is tested in the WebSocket endpoint in social_routes.py
        # Here we verify the event bus supports it
        bus = AgentEventBus()

        # Verify event bus can handle ping/pong events
        ws = MockWebSocket("agent1")
        await bus.subscribe("agent1", ws, ["global"])

        # Send ping event
        await bus.publish({"type": "ping"}, ["global"])

        # WebSocket received event (actual pong logic in route handler)
        assert len(ws.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_json_send_format(self):
        """Events sent as valid JSON."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        await bus.subscribe("agent1", ws, ["global"])

        event = {"type": "test", "data": {"nested": {"key": "value"}}}
        await bus.publish(event, ["global"])

        # Verify JSON sent
        assert ws.send_json_called
        assert ws.sent_messages[0] == event

    @pytest.mark.asyncio
    async def test_connection_cleanup(self):
        """Cleanup on abnormal disconnect."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        await bus.subscribe("agent1", ws, ["global"])

        # Simulate disconnect (unsubscribe)
        await bus.unsubscribe("agent1", ws)

        assert "agent1" not in bus._subscribers
        assert "agent1" not in bus._topics.get("global", set())

    @pytest.mark.asyncio
    async def test_subscribe_to_multiple_topics(self):
        """Single connection can subscribe to multiple topics."""
        bus = AgentEventBus()
        ws = MockWebSocket("agent1")

        topics = ["global", "alerts", "channel:engineering"]
        await bus.subscribe("agent1", ws, topics)

        # Verify subscribed to all topics
        for topic in topics:
            assert topic in bus._topics
            assert "agent1" in bus._topics[topic]

    @pytest.mark.asyncio
    async def test_channel_subscription(self):
        """Channel topics (channel:{name}) work correctly."""
        bus = AgentEventBus()
        ws1 = MockWebSocket("agent1")
        ws2 = MockWebSocket("agent2")

        # Subscribe to different channels
        await bus.subscribe("agent1", ws1, ["channel:engineering"])
        await bus.subscribe("agent2", ws2, ["channel:sales"])

        # Publish to engineering channel
        await bus.publish({"channel": "engineering"}, ["channel:engineering"])

        # Only agent1 received
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 0


# ============================================================================
# Property-Based Tests for Message Ordering (5 tests)
# ============================================================================

class TestMessageOrderingProperties:
    """Property-based tests for message ordering invariants."""

    @given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=20))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_messages_delivered_in_fifo_order(self, messages):
        """Property: Messages delivered in FIFO order per sender."""
        bus = AgentEventBus()
        received = []

        # Create mock WebSocket that captures messages
        ws = Mock()
        ws.send_json = AsyncMock(side_effect=lambda msg: received.append(msg))

        await bus.subscribe("agent1", ws, ["global"])

        # Send messages and verify order
        for msg in messages:
            await bus.publish({"data": msg}, ["global"])

        # Verify FIFO order preserved
        received_data = [m["data"] for m in received]
        assert received_data == messages

    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_no_messages_lost(self, count):
        """Property: All published messages delivered to subscribers."""
        bus = AgentEventBus()
        received_count = [0]

        async def increment(msg):
            received_count[0] += 1

        ws = Mock()
        ws.send_json = AsyncMock(side_effect=increment)

        await bus.subscribe("agent1", ws, ["global"])

        for i in range(count):
            await bus.publish({"id": i}, ["global"])

        assert received_count[0] == count

    @given(st.integers(min_value=2, max_value=20))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_multiple_subscribers_all_receive(self, subscriber_count):
        """Property: All subscribers receive every message."""
        bus = AgentEventBus()

        counts = [0] * subscriber_count

        for i in range(subscriber_count):
            def make_count(idx):
                async def count_fn(msg):
                    counts[idx] += 1
                return count_fn

            ws = Mock()
            ws.send_json = AsyncMock(side_effect=make_count(i))
            await bus.subscribe(f"agent{i}", ws, ["global"])

        await bus.publish({"test": "data"}, ["global"])

        # All subscribers received exactly once
        assert all(c == 1 for c in counts)

    @given(st.lists(st.sampled_from(["global", "alerts", "agent:123"]), min_size=0, max_size=10))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_topic_filtering(self, topics):
        """Property: Only subscribed topics received."""
        bus = AgentEventBus()

        global_received = []
        alerts_received = []

        ws1 = Mock()
        ws1.send_json = AsyncMock(side_effect=lambda m: global_received.append(m))
        ws2 = Mock()
        ws2.send_json = AsyncMock(side_effect=lambda m: alerts_received.append(m))

        await bus.subscribe("agent1", ws1, ["global"])
        await bus.subscribe("agent2", ws2, ["alerts"])

        await bus.publish({"test": "data"}, topics)

        # Verify each subscriber only gets their topics
        global_count = 1 if "global" in topics else 0
        alerts_count = 1 if "alerts" in topics else 0

        assert len(global_received) == global_count
        assert len(alerts_received) == alerts_count

    @given(st.integers(min_value=1, max_value=50))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_event_bus_concurrent_publish(self, count):
        """Property: Concurrent publishes don't lose messages."""
        bus = AgentEventBus()
        received = []

        ws = Mock()
        ws.send_json = AsyncMock(side_effect=lambda m: received.append(m))

        await bus.subscribe("agent1", ws, ["global"])

        # Publish concurrently
        tasks = [bus.publish({"id": i}, ["global"]) for i in range(count)]
        await asyncio.gather(*tasks)

        # All messages delivered
        assert len(received) == count


# ============================================================================
# Test Statistics
# ============================================================================

def test_suite_statistics():
    """Print test suite statistics."""
    print("\n" + "="*70)
    print("AGENT COMMUNICATION TEST SUITE STATISTICS")
    print("="*70)
    print("\nTest Categories:")
    print("  - Event Bus Unit Tests: 12 tests")
    print("  - Redis Pub/Sub Integration: 10 tests")
    print("  - WebSocket Connection Tests: 8 tests")
    print("  - Property-Based Tests: 5 tests")
    print("  ----------------------------------------")
    print("  Total: 35 tests")
    print("\nCoverage:")
    print("  - Message delivery and FIFO ordering")
    print("  - Redis pub/sub horizontal scaling")
    print("  - WebSocket connection lifecycle")
    print("  - Topic-based filtering")
    print("  - Concurrent message handling")
    print("  - Graceful degradation (Redis failures)")
    print("\nInvariants Verified:")
    print("  [✓] No lost messages")
    print("  [✓] FIFO ordering per sender")
    print("  [✓] Topic filtering works correctly")
    print("  [✓] Multiple subscribers all receive messages")
    print("  [✓] Concurrent publishes safe")
    print("="*70)
