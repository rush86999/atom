"""
Tests for Agent Communication (AgentEventBus)

Tests for agent-to-agent communication including:
- WebSocket subscription
- Event publishing
- Topic filtering
- Redis pub/sub integration
- Broadcast operations
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock
from unittest.mock import patch

import json


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket connection."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def event_bus():
    """Create agent event bus instance."""
    from core.agent_communication import AgentEventBus
    return AgentEventBus(redis_url=None)  # Disable Redis for testing


class TestAgentEventBusInit:
    """Tests for AgentEventBus initialization."""

    def test_init_default(self):
        """Test default initialization."""
        from core.agent_communication import AgentEventBus
        bus = AgentEventBus()

        assert bus._subscribers == {}
        assert "global" in bus._topics
        assert bus._redis_enabled is False

    def test_init_with_redis(self):
        """Test initialization with Redis URL."""
        from core.agent_communication import AgentEventBus
        bus = AgentEventBus(redis_url="redis://localhost:6379")

        assert bus._redis_url == "redis://localhost:6379"

    @patch('core.agent_communication.REDIS_AVAILABLE', True)
    @patch('core.agent_communication.redis')
    def test_init_redis_available(self, mock_redis):
        """Test initialization when Redis is available."""
        from core.agent_communication import AgentEventBus
        bus = AgentEventBus(redis_url="redis://localhost:6379")

        assert bus._redis_enabled is True


class TestSubscribe:
    """Tests for subscribe method."""

    @pytest.mark.asyncio
    async def test_subscribe_basic(self, event_bus, mock_websocket):
        """Test basic subscription."""
        await event_bus.subscribe(
            agent_id="agent-1",
            websocket=mock_websocket
        )

        assert "agent-1" in event_bus._subscribers
        assert mock_websocket in event_bus._subscribers["agent-1"]

    @pytest.mark.asyncio
    async def test_subscribe_with_topics(self, event_bus, mock_websocket):
        """Test subscription with custom topics."""
        await event_bus.subscribe(
            agent_id="agent-1",
            websocket=mock_websocket,
            topics=["alerts", "category:automation"]
        )

        assert "alerts" in event_bus._topics
        assert "agent-1" in event_bus._topics["alerts"]
        assert "agent-1" in event_bus._topics["category:automation"]

    @pytest.mark.asyncio
    async def test_subscribe_multiple_connections(self, event_bus, mock_websocket):
        """Test subscribing multiple connections for same agent."""
        ws1 = mock_websocket
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()

        await event_bus.subscribe("agent-1", ws1)
        await event_bus.subscribe("agent-1", ws2)

        assert len(event_bus._subscribers["agent-1"]) == 2


class TestUnsubscribe:
    """Tests for unsubscribe method."""

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus, mock_websocket):
        """Test unsubscribing a WebSocket."""
        await event_bus.subscribe("agent-1", mock_websocket)
        await event_bus.unsubscribe("agent-1", mock_websocket)

        assert "agent-1" not in event_bus._subscribers

    @pytest.mark.asyncio
    async def test_unsubscribe_multiple_connections(self, event_bus, mock_websocket):
        """Test unsubscribing one of multiple connections."""
        ws1 = mock_websocket
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()

        await event_bus.subscribe("agent-1", ws1)
        await event_bus.subscribe("agent-1", ws2)
        await event_bus.unsubscribe("agent-1", ws1)

        assert len(event_bus._subscribers["agent-1"]) == 1
        assert ws2 in event_bus._subscribers["agent-1"]

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_from_topics(self, event_bus, mock_websocket):
        """Test that unsubscribe removes agent from all topics."""
        await event_bus.subscribe(
            "agent-1",
            mock_websocket,
            topics=["alerts", "updates"]
        )
        await event_bus.unsubscribe("agent-1", mock_websocket)

        assert "agent-1" not in event_bus._topics["alerts"]
        assert "agent-1" not in event_bus._topics["updates"]


class TestPublish:
    """Tests for publish method."""

    @pytest.mark.asyncio
    async def test_publish_basic(self, event_bus, mock_websocket):
        """Test basic event publishing."""
        await event_bus.subscribe("agent-1", mock_websocket)

        event = {"type": "test", "data": "message"}
        await event_bus.publish(event, topics=["global"])

        mock_websocket.send_json.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_publish_multiple_subscribers(self, event_bus):
        """Test publishing to multiple subscribers."""
        ws1 = MagicMock()
        ws1.send_json = AsyncMock()
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()

        await event_bus.subscribe("agent-1", ws1)
        await event_bus.subscribe("agent-2", ws2)

        event = {"type": "broadcast", "data": "test"}
        await event_bus.publish(event, topics=["global"])

        # Both should receive
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_topic_filtering(self, event_bus):
        """Test topic-based filtering."""
        ws_all = MagicMock()
        ws_all.send_json = AsyncMock()
        ws_alerts = MagicMock()
        ws_alerts.send_json = AsyncMock()

        await event_bus.subscribe("agent-all", ws_all, topics=["global"])
        await event_bus.subscribe("agent-alerts", ws_alerts, topics=["alerts"])

        event = {"type": "alert", "data": "warning"}
        await event_bus.publish(event, topics=["alerts"])

        # Only alerts subscriber should receive
        ws_alerts.send_json.assert_called_once()
        ws_all.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_dead_connection(self, event_bus, mock_websocket):
        """Test publishing to dead WebSocket connection."""
        mock_websocket.send_json = AsyncMock(side_effect=Exception("Connection closed"))

        await event_bus.subscribe("agent-1", mock_websocket)

        event = {"type": "test", "data": "message"}
        await event_bus.publish(event, topics=["global"])

        # Should handle error gracefully and remove dead connection
        assert "agent-1" not in event_bus._subscribers

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self, event_bus):
        """Test publishing with no subscribers."""
        event = {"type": "test", "data": "message"}

        # Should not raise
        await event_bus.publish(event, topics=["global"])


class TestBroadcastPost:
    """Tests for broadcast_post method."""

    @pytest.mark.asyncio
    async def test_broadcast_post_basic(self, event_bus, mock_websocket):
        """Test broadcasting agent post."""
        await event_bus.subscribe("agent-1", mock_websocket)

        post_data = {
            "sender_id": "agent-1",
            "post_type": "question",
            "content": "Test question"
        }

        await event_bus.broadcast_post(post_data)

        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "agent_post"

    @pytest.mark.asyncio
    async def test_broadcast_post_alert(self, event_bus, mock_websocket):
        """Test broadcasting alert post."""
        await event_bus.subscribe("agent-1", mock_websocket)

        post_data = {
            "sender_id": "agent-2",
            "post_type": "alert",
            "content": "Important alert"
        }

        await event_bus.broadcast_post(post_data)

        # Should receive (subscribed to global and agent:agent-2)
        mock_websocket.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_broadcast_post_with_category(self, event_bus):
        """Test broadcasting post with category."""
        ws = MagicMock()
        ws.send_json = AsyncMock()

        await event_bus.subscribe(
            "agent-1",
            ws,
            topics=["category:automation"]
        )

        post_data = {
            "sender_id": "agent-2",
            "post_type": "question",
            "sender_category": "automation",
            "content": "Automation question"
        }

        await event_bus.broadcast_post(post_data)

        ws.send_json.assert_called()


class TestRedisIntegration:
    """Tests for Redis pub/sub integration."""

    @patch('core.agent_communication.REDIS_AVAILABLE', True)
    @pytest.mark.asyncio
    async def test_ensure_redis(self):
        """Test Redis connection initialization."""
        from core.agent_communication import AgentEventBus

        with patch('core.agent_communication.redis.from_url') as mock_from_url:
            mock_redis = MagicMock()
            mock_from_url.return_value = mock_redis

            bus = AgentEventBus(redis_url="redis://localhost")
            await bus._ensure_redis()

            assert bus._redis == mock_redis

    @pytest.mark.asyncio
    async def test_publish_to_redis(self, event_bus):
        """Test publishing to Redis."""
        with patch('core.agent_communication.REDIS_AVAILABLE', True):
            event_bus._redis_enabled = True
            event_bus._redis = MagicMock()
            event_bus._redis.publish = AsyncMock()

            event = {"type": "test"}
            await event_bus.publish(event, topics=["alerts"])

            # Should publish to Redis
            event_bus._redis.publish.assert_called()

    @pytest.mark.asyncio
    async def test_subscribe_to_redis(self):
        """Test subscribing to Redis pub/sub."""
        from core.agent_communication import AgentEventBus

        with patch('core.agent_communication.REDIS_AVAILABLE', True):
            bus = AgentEventBus(redis_url="redis://localhost")

            mock_pubsub = MagicMock()
            mock_pubsub.psubscribe = AsyncMock()
            bus._pubsub = mock_pubsub

            await bus.subscribe_to_redis()

            mock_pubsub.psubscribe.assert_called_once_with("agent_events:*")

    @pytest.mark.asyncio
    async def test_close_redis(self):
        """Test closing Redis connection."""
        from core.agent_communication import AgentEventBus

        with patch('core.agent_communication.REDIS_AVAILABLE', True):
            bus = AgentEventBus(redis_url="redis://localhost")

            mock_redis = MagicMock()
            mock_redis.close = AsyncMock()
            bus._redis = mock_redis

            mock_pubsub = MagicMock()
            mock_pubsub.close = AsyncMock()
            bus._pubsub = mock_pubsub

            await bus.close_redis()

            mock_pubsub.close.assert_called_once()
            mock_redis.close.assert_called_once()


class TestGlobalInstance:
    """Tests for global event bus instance."""

    def test_global_event_bus(self):
        """Test that global event bus instance exists."""
        from core.agent_communication import agent_event_bus

        assert agent_event_bus is not None
        assert isinstance(agent_event_bus, object)


class TestTopicManagement:
    """Tests for topic management."""

    @pytest.mark.asyncio
    async def test_topic_creation(self, event_bus):
        """Test that new topics are created as needed."""
        ws = MagicMock()
        ws.send_json = AsyncMock()

        await event_bus.subscribe(
            "agent-1",
            ws,
            topics=["new_topic"]
        )

        assert "new_topic" in event_bus._topics
        assert "agent-1" in event_bus._topics["new_topic"]

    @pytest.mark.asyncio
    async def test_global_topic_always_exists(self, event_bus):
        """Test that global topic always exists."""
        assert "global" in event_bus._topics


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, event_bus):
        """Test handling Redis connection failure."""
        with patch('core.agent_communication.REDIS_AVAILABLE', True):
            event_bus._redis_enabled = True

            with patch('core.agent_communication.redis.from_url', side_effect=Exception("Connection failed")):
                await event_bus._ensure_redis()

            # Should fall back to disabled
            assert event_bus._redis_enabled is False

    @pytest.mark.asyncio
    async def test_redis_publish_failure(self, event_bus, mock_websocket):
        """Test handling Redis publish failure."""
        event_bus._redis_enabled = True
        event_bus._redis = MagicMock()
        event_bus._redis.publish = AsyncMock(side_effect=Exception("Publish failed"))

        await event_bus.subscribe("agent-1", mock_websocket)

        event = {"type": "test"}
        await event_bus.publish(event, topics=["global"])

        # Should still deliver to local subscribers
        mock_websocket.send_json.assert_called_once()


class TestConcurrentOperations:
    """Tests for concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_subscribe_unsubscribe(self, event_bus):
        """Test concurrent subscribe and unsubscribe operations."""
        ws1 = MagicMock()
        ws1.send_json = AsyncMock()
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()

        # Run concurrent operations
        await asyncio.gather(
            event_bus.subscribe("agent-1", ws1),
            event_bus.subscribe("agent-2", ws2),
            event_bus.publish({"type": "test"}, topics=["global"]),
        )

        # Both should receive
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_publish(self, event_bus):
        """Test concurrent publish operations."""
        ws = MagicMock()
        ws.send_json = AsyncMock()

        await event_bus.subscribe("agent-1", ws)

        # Publish multiple events concurrently
        events = [{"type": f"test-{i}", "data": i} for i in range(10)]
        await asyncio.gather(*[
            event_bus.publish(event, topics=["global"])
            for event in events
        ])

        # All should be delivered
        assert ws.send_json.call_count == 10
