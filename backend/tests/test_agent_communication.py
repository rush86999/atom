"""
Integration Tests for Agent Communication

Tests cover:
- Agent-to-agent messaging (EventBus, Redis pub/sub, WebSocket)
- Message delivery (no lost messages)
- Message ordering (FIFO per channel)
- WebSocket real-time updates
- Channel isolation
- Multiple receivers
- Message persistence for offline agents
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock
from sqlalchemy.orm import Session

from core.agent_communication import agent_event_bus, AgentEventBus
from core.agent_social_layer import AgentSocialLayer
from core.models import AgentRegistry
from tests.factories import AgentFactory


class TestAgentCommunication:
    """Test agent-to-agent communication."""

    @pytest.fixture
    def social_layer(self, db_session):
        """Create social layer."""
        return AgentSocialLayer()

    @pytest.fixture
    def event_bus(self):
        """Create fresh event bus for each test."""
        bus = AgentEventBus()  # Don't use global instance
        return bus

    @pytest.fixture
    def agents(self, db_session):
        """Create test agents."""
        agents = []
        for i in range(3):
            agent = AgentFactory(
                name=f"Agent{i}",
                status="INTERN",  # INTERN+ can post
                class_name="TestAgent",
                module_path="tests.test_agent_communication"
            )
            agents.append(agent)
            db_session.add(agent)
        db_session.commit()
        return agents

    @pytest.mark.asyncio
    async def test_send_message_between_agents(self, social_layer, agents):
        """Test sending message from one agent to another via social layer."""
        sender, receiver = agents[0], agents[1]

        # Create post (message)
        post = await social_layer.create_post(
            sender_type="agent",
            sender_id=sender.id,
            sender_name=sender.name,
            post_type="status",
            content="Hello from sender",
            sender_maturity=sender.status,
            sender_category=sender.category,
            db=db_session
        )

        # Verify message created
        assert post["sender_id"] == sender.id
        assert post["content"] == "Hello from sender"
        assert post["post_type"] == "status"

        # Verify message retrievable
        feed = await social_layer.get_feed(
            sender_id=receiver.id,
            limit=10,
            db=db_session
        )

        assert len(feed["posts"]) > 0
        assert feed["posts"][0]["sender_id"] == sender.id
        assert feed["posts"][0]["content"] == "Hello from sender"

    @pytest.mark.asyncio
    async def test_no_lost_messages(self, social_layer, agents):
        """Test no messages are lost during delivery."""
        sender, receiver = agents[0], agents[1]

        # Send 100 messages
        num_messages = 100
        for i in range(num_messages):
            await social_layer.create_post(
                sender_type="agent",
                sender_id=sender.id,
                sender_name=sender.name,
                post_type="status",
                content=f"Message {i}",
                sender_maturity=sender.status,
                sender_category=sender.category,
                db=db_session
            )

        # Retrieve all messages
        feed = await social_layer.get_feed(
            sender_id=receiver.id,
            limit=200,  # Large limit to get all
            db=db_session
        )

        # Should have received all messages
        assert feed["total"] >= num_messages
        assert len(feed["posts"]) >= num_messages

    @pytest.mark.asyncio
    async def test_fifo_ordering_per_channel(self, social_layer, agents):
        """Test FIFO message ordering per channel (chronological)."""
        sender, receiver = agents[0], agents[1]

        # Send messages in order
        sent_order = []
        for i in range(10):
            message = f"Message {i}"
            await social_layer.create_post(
                sender_type="agent",
                sender_id=sender.id,
                sender_name=sender.name,
                post_type="status",
                content=message,
                sender_maturity=sender.status,
                sender_category=sender.category,
                channel_id="ordered",
                channel_name="ordered",
                db=db_session
            )
            sent_order.append(message)

        # Retrieve messages (should be in reverse chronological order)
        feed = await social_layer.get_feed(
            sender_id=receiver.id,
            channel_id="ordered",
            limit=20,
            db=db_session
        )

        # Extract message contents (newest first)
        received_order = [p["content"] for p in feed["posts"]]

        # Should be reverse chronological (newest first)
        assert received_order == list(reversed(sent_order))

    @pytest.mark.asyncio
    async def test_redis_pub_sub_realtime(self, event_bus):
        """Test Redis pub/sub real-time communication pattern."""
        # Simulate WebSocket connections
        websocket1 = Mock()
        websocket1.send_json = AsyncMock()

        websocket2 = Mock()
        websocket2.send_json = AsyncMock()

        # Subscribe receiver to channel
        await event_bus.subscribe(
            agent_id="receiver1",
            websocket=websocket1,
            topics=["agent:receiver1"]
        )

        await event_bus.subscribe(
            agent_id="receiver2",
            websocket=websocket2,
            topics=["global"]
        )

        # Publish message
        await event_bus.publish(
            event={
                "type": "message",
                "from_agent_id": "sender",
                "content": "Real-time message"
            },
            topics=["agent:receiver1", "global"]
        )

        # Verify both receivers got the message
        websocket1.send_json.assert_called_once()
        websocket2.send_json.assert_called_once()

        # Check message content
        call_args = websocket1.send_json.call_args[0][0]
        assert call_args["content"] == "Real-time message"

    @pytest.mark.asyncio
    async def test_channel_isolation(self, social_layer, agents):
        """Test messages are isolated per channel."""
        sender, receiver = agents[0], agents[1]

        # Send to channel A
        await social_layer.create_post(
            sender_type="agent",
            sender_id=sender.id,
            sender_name=sender.name,
            post_type="status",
            content="Channel A message",
            sender_maturity=sender.status,
            sender_category=sender.category,
            channel_id="channel-a",
            channel_name="Channel A",
            db=db_session
        )

        # Send to channel B
        await social_layer.create_post(
            sender_type="agent",
            sender_id=sender.id,
            sender_name=sender.name,
            post_type="status",
            content="Channel B message",
            sender_maturity=sender.status,
            sender_category=sender.category,
            channel_id="channel-b",
            channel_name="Channel B",
            db=db_session
        )

        # Retrieve from channel A
        feed_a = await social_layer.get_feed(
            sender_id=receiver.id,
            channel_id="channel-a",
            limit=10,
            db=db_session
        )

        # Retrieve from channel B
        feed_b = await social_layer.get_feed(
            sender_id=receiver.id,
            channel_id="channel-b",
            limit=10,
            db=db_session
        )

        # Should be isolated
        assert any(p["content"] == "Channel A message" for p in feed_a["posts"])
        assert not any(p["content"] == "Channel A message" for p in feed_b["posts"])
        assert any(p["content"] == "Channel B message" for p in feed_b["posts"])
        assert not any(p["content"] == "Channel B message" for p in feed_a["posts"])

    @pytest.mark.asyncio
    async def test_multiple_receivers(self, social_layer, agents):
        """Test sending message to multiple receivers."""
        sender = agents[0]
        receivers = agents[1:]

        # Broadcast to all receivers (public post)
        await social_layer.create_post(
            sender_type="agent",
            sender_id=sender.id,
            sender_name=sender.name,
            post_type="announcement",
            content="Broadcast message",
            sender_maturity=sender.status,
            sender_category=sender.category,
            is_public=True,
            db=db_session
        )

        # All receivers should get the message
        for receiver in receivers:
            feed = await social_layer.get_feed(
                sender_id=receiver.id,
                limit=10,
                db=db_session
            )
            assert any(p["content"] == "Broadcast message" for p in feed["posts"])

    @pytest.mark.asyncio
    async def test_message_persistence(self, social_layer, agents):
        """Test messages are persisted for offline agents."""
        sender, receiver = agents[0], agents[1]

        # Send message while receiver is "offline"
        await social_layer.create_post(
            sender_type="agent",
            sender_id=sender.id,
            sender_name=sender.name,
            post_type="status",
            content="Stored message",
            sender_maturity=sender.status,
            sender_category=sender.category,
            db=db_session
        )

        # Receiver comes back online and retrieves messages
        feed = await social_layer.get_feed(
            sender_id=receiver.id,
            limit=10,
            db=db_session
        )

        # Should retrieve stored message
        assert len(feed["posts"]) > 0
        assert feed["posts"][0]["content"] == "Stored message"

    @pytest.mark.asyncio
    async def test_websocket_realtime_updates(self, event_bus):
        """Test WebSocket real-time message delivery via event bus."""
        # Simulate WebSocket connections
        websocket = Mock()
        websocket.send_json = AsyncMock()

        # Subscribe to event bus
        await event_bus.subscribe(
            agent_id="receiver",
            websocket=websocket,
            topics=["global", "alerts"]
        )

        # Broadcast new post event
        await event_bus.broadcast_post({
            "id": "post-123",
            "sender_id": "agent-1",
            "sender_name": "Agent 1",
            "post_type": "alert",
            "content": "WebSocket message",
            "sender_category": "engineering"
        })

        # Verify WebSocket received update
        websocket.send_json.assert_called_once()
        call_args = websocket.send_json.call_args[0][0]
        assert call_args["type"] == "agent_post"
        assert call_args["data"]["content"] == "WebSocket message"

    @pytest.mark.asyncio
    async def test_topic_filtering(self, event_bus):
        """Test topic-based message filtering."""
        # Create multiple websockets with different topic subscriptions
        websocket_global = Mock()
        websocket_global.send_json = AsyncMock()

        websocket_alerts = Mock()
        websocket_alerts.send_json = AsyncMock()

        websocket_engineering = Mock()
        websocket_engineering.send_json = AsyncMock()

        # Subscribe to different topics
        await event_bus.subscribe("agent1", websocket_global, ["global"])
        await event_bus.subscribe("agent2", websocket_alerts, ["alerts"])
        await event_bus.subscribe("agent3", websocket_engineering, ["category:engineering"])

        # Publish alert
        await event_bus.broadcast_post({
            "id": "post-1",
            "sender_id": "agent-1",
            "sender_name": "Agent 1",
            "post_type": "alert",
            "content": "Critical alert",
            "sender_category": "engineering"
        })

        # global subscriber should get it
        websocket_global.send_json.assert_called_once()

        # alerts subscriber should get it
        websocket_alerts.send_json.assert_called_once()

        # engineering category subscriber should get it
        websocket_engineering.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_bus_unsubscribe(self, event_bus):
        """Test unsubscribing from event bus."""
        websocket = Mock()
        websocket.send_json = AsyncMock()

        # Subscribe
        await event_bus.subscribe("agent1", websocket, ["global"])

        # Unsubscribe
        await event_bus.unsubscribe("agent1", websocket)

        # Publish event
        await event_bus.publish(
            event={"type": "test", "content": "Should not receive"},
            topics=["global"]
        )

        # Should not receive after unsubscribe
        websocket.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_directed_message(self, social_layer, agents):
        """Test directed (private) message between agents."""
        sender, receiver = agents[0], agents[1]

        # Send private message
        await social_layer.create_post(
            sender_type="agent",
            sender_id=sender.id,
            sender_name=sender.name,
            post_type="command",
            content="Private message for you",
            sender_maturity=sender.status,
            sender_category=sender.category,
            recipient_type="agent",
            recipient_id=receiver.id,
            is_public=False,
            db=db_session
        )

        # Retrieve directed messages
        feed = await social_layer.get_feed(
            sender_id=receiver.id,
            is_public=False,
            limit=10,
            db=db_session
        )

        # Should have private message
        assert len(feed["posts"]) > 0
        assert feed["posts"][0]["content"] == "Private message for you"
        assert feed["posts"][0]["is_public"] is False

    @pytest.mark.asyncio
    async def test_post_type_filtering(self, social_layer, agents):
        """Test filtering by post type."""
        sender = agents[0]

        # Create different post types
        for post_type in ["status", "insight", "question", "alert"]:
            await social_layer.create_post(
                sender_type="agent",
                sender_id=sender.id,
                sender_name=sender.name,
                post_type=post_type,
                content=f"{post_type.capitalize()} post",
                sender_maturity=sender.status,
                sender_category=sender.category,
                db=db_session
            )

        # Filter by question type
        feed = await social_layer.get_feed(
            sender_id=sender.id,
            post_type="question",
            limit=10,
            db=db_session
        )

        # Should only have question posts
        assert len(feed["posts"]) == 1
        assert feed["posts"][0]["post_type"] == "question"
        assert feed["posts"][0]["content"] == "Question post"

    @pytest.mark.asyncio
    async def test_sender_filtering(self, social_layer, agents):
        """Test filtering by specific sender."""
        sender1, sender2 = agents[0], agents[1]

        # Sender1 creates posts
        for i in range(3):
            await social_layer.create_post(
                sender_type="agent",
                sender_id=sender1.id,
                sender_name=sender1.name,
                post_type="status",
                content=f"Sender1 post {i}",
                sender_maturity=sender1.status,
                sender_category=sender1.category,
                db=db_session
            )

        # Sender2 creates posts
        for i in range(2):
            await social_layer.create_post(
                sender_type="agent",
                sender_id=sender2.id,
                sender_name=sender2.name,
                post_type="status",
                content=f"Sender2 post {i}",
                sender_maturity=sender2.status,
                sender_category=sender2.category,
                db=db_session
            )

        # Filter by sender1
        feed = await social_layer.get_feed(
            sender_id=sender1.id,
            sender_filter=sender1.id,
            limit=10,
            db=db_session
        )

        # Should only have sender1's posts
        assert len(feed["posts"]) == 3
        assert all(p["sender_id"] == sender1.id for p in feed["posts"])
        assert all("Sender1 post" in p["content"] for p in feed["posts"])

    @pytest.mark.asyncio
    async def test_governance_student_cannot_post(self, social_layer, db_session):
        """Test STUDENT agents cannot post to social feed."""
        # Create STUDENT agent
        student_agent = AgentFactory(
            name="StudentAgent",
            status="STUDENT",  # STUDENT maturity
            class_name="TestAgent",
            module_path="tests.test_agent_communication"
        )
        db_session.add(student_agent)
        db_session.commit()

        # Try to post as STUDENT agent
        with pytest.raises(PermissionError) as exc_info:
            await social_layer.create_post(
                sender_type="agent",
                sender_id=student_agent.id,
                sender_name=student_agent.name,
                post_type="status",
                content="I should not be able to post",
                sender_maturity=student_agent.status,
                sender_category=student_agent.category,
                db=db_session
            )

        # Verify error message
        assert "STUDENT agents cannot post" in str(exc_info.value)
        assert "INTERN+ maturity" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_pagination_offset(self, social_layer, agents):
        """Test offset-based pagination."""
        sender = agents[0]

        # Create 20 posts
        for i in range(20):
            await social_layer.create_post(
                sender_type="agent",
                sender_id=sender.id,
                sender_name=sender.name,
                post_type="status",
                content=f"Post {i}",
                sender_maturity=sender.status,
                sender_category=sender.category,
                db=db_session
            )

        # Get first page
        page1 = await social_layer.get_feed(
            sender_id=sender.id,
            limit=10,
            offset=0,
            db=db_session
        )

        # Get second page
        page2 = await social_layer.get_feed(
            sender_id=sender.id,
            limit=10,
            offset=10,
            db=db_session
        )

        # Should have 10 posts each
        assert len(page1["posts"]) == 10
        assert len(page2["posts"]) == 10

        # Posts should be different (no duplicates)
        ids1 = {p["id"] for p in page1["posts"]}
        ids2 = {p["id"] for p in page2["posts"]}
        assert len(ids1 & ids2) == 0  # No intersection
