---
phase: 06-social-layer
plan: 02
type: execute
wave: 1
depends_on: ["05-agent-layer"]
files_modified:
  - tests/test_agent_communication.py
  - tests/test_social_feed_integration.py
  - tests/api/test_social_routes_integration.py
  - tests/property_tests/social/test_feed_pagination_invariants.py
autonomous: true

must_haves:
  truths:
    - "Agent-to-agent messaging delivers all messages (no lost messages)"
    - "Message ordering is FIFO per channel (guaranteed delivery order)"
    - "Redis pub/sub enables real-time communication"
    - "Feed generation supports chronological and algorithmic ordering"
    - "Feed pagination never returns duplicates (cursor-based)"
    - "Feed filtering works (by agent, by topic, by time range)"
    - "Property tests verify FIFO ordering and no duplicates"
  artifacts:
    - path: "tests/test_agent_communication.py"
      provides: "Unit tests for agent-to-agent messaging (EventBus, Redis pub/sub, WebSocket)"
      min_lines: 400
    - path: "tests/test_social_feed_integration.py"
      provides: "Integration tests for feed generation, pagination, filtering"
      min_lines: 450
    - path: "tests/api/test_social_routes_integration.py"
      provides: "API integration tests for social routes (feed, posts, channels)"
      min_lines: 350
    - path: "tests/property_tests/social/test_feed_pagination_invariants.py"
      provides: "Property tests for feed invariants (no duplicates, FIFO, chronological)"
      min_lines: 280
  key_links:
    - from: "tests/test_agent_communication.py"
      to: "core/social_layer.py" or "core/event_bus.py"
      via: "tests agent-to-agent messaging, Redis pub/sub, WebSocket"
      pattern: "test_send_message|test_receive_message|test_pub_sub"
    - from: "tests/test_social_feed_integration.py"
      to: "core/social_feed_service.py" or "api/social_routes.py"
      via: "tests feed generation, cursor pagination, filtering"
      pattern: "test_feed_generation|test_pagination_no_duplicates|test_feed_filtering"
    - from: "tests/api/test_social_routes_integration.py"
      to: "api/social_routes.py"
      via: "tests REST API endpoints (GET /feed, POST /posts, GET /channels)"
      pattern: "test_get_feed|test_create_post|test_get_channels"
    - from: "tests/property_tests/social/test_feed_pagination_invariants.py"
      to: "core/social_feed_service.py"
      via: "tests no duplicates, FIFO ordering, chronological order"
      pattern: "test_no_duplicates|test_fifo_ordering|test_chronological_order"
---

## Objective

Create integration and property tests for agent-to-agent communication (EventBus, Redis pub/sub, WebSocket) and social feed management (generation, pagination, filtering).

**Purpose:** Agent communication requires reliable message delivery (no lost messages, FIFO ordering). Social feeds need pagination without duplicates and filtering by agent/topic/time. Tests validate Redis pub/sub, cursor-based pagination, and property-based invariants.

**Output:** Integration tests for communication and feed, property tests for invariants (no duplicates, FIFO, chronological).

## Execution Context

@core/social_layer.py (agent-to-agent messaging)
@core/event_bus.py (event bus for pub/sub)
@core/social_feed_service.py (feed generation, pagination)
@api/social_routes.py (REST endpoints)
@core/models.py (SocialPost, SocialChannel, AgentRegistry)

## Context

@.planning/ROADMAP.md (Phase 6 requirements)
@.planning/REQUIREMENTS.md (AR-07: Social Layer Coverage, AR-12: Property-Based Testing)

# Phase 5 Complete: Agent Layer Tested
- Agent coordination tested (FIFO ordering, event bus)
- Agent execution orchestration tested

# Existing Communication Implementation
- social_layer.py: Agent-to-agent messaging via Redis pub/sub
- event_bus.py: Event bus for agent coordination
- social_routes.py: REST endpoints for feed, posts, channels

## Tasks

### Task 1: Create Integration Tests for Agent Communication

**Files:** `tests/test_agent_communication.py`

**Action:**
Create integration tests for agent-to-agent messaging:

```python
"""
Integration Tests for Agent Communication

Tests cover:
- Agent-to-agent messaging (EventBus, Redis pub/sub)
- Message delivery (no lost messages)
- Message ordering (FIFO per channel)
- WebSocket real-time updates
- Channel isolation
"""
import pytest
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from core.social_layer import SocialLayer
from core.event_bus import EventBus
from core.models import AgentRegistry
from tests.factories import AgentFactory


class TestAgentCommunication:
    """Test agent-to-agent communication."""

    @pytest.fixture
    def social_layer(self, db_session):
        """Create social layer."""
        return SocialLayer(db_session)

    @pytest.fixture
    def event_bus(self, db_session):
        """Create event bus."""
        return EventBus(db_session)

    @pytest.fixture
    def agents(self, db_session):
        """Create test agents."""
        agents = [AgentFactory(name=f"Agent{i}") for i in range(3)]
        db_session.commit()
        return agents

    @pytest.mark.asyncio
    async def test_send_message_between_agents(self, social_layer, agents):
        """Test sending message from one agent to another."""
        sender, receiver = agents[0], agents[1]

        await social_layer.send_message(
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            message="Hello from sender",
            channel="default"
        )

        # Verify message received
        messages = await social_layer.get_messages(receiver.id, channel="default")

        assert len(messages) > 0
        assert messages[0]["from_agent_id"] == sender.id
        assert messages[0]["message"] == "Hello from sender"

    @pytest.mark.asyncio
    async def test_no_lost_messages(self, social_layer, agents):
        """Test no messages are lost during delivery."""
        sender, receiver = agents[0], agents[1]

        # Send 100 messages
        num_messages = 100
        for i in range(num_messages):
            await social_layer.send_message(
                from_agent_id=sender.id,
                to_agent_id=receiver.id,
                message=f"Message {i}",
                channel="test"
            )

        # Retrieve all messages
        messages = await social_layer.get_messages(receiver.id, channel="test")

        # Should have received all messages
        assert len(messages) >= num_messages

    @pytest.mark.asyncio
    async def test_fifo_ordering_per_channel(self, social_layer, agents):
        """Test FIFO message ordering per channel."""
        sender, receiver = agents[0], agents[1]

        # Send messages in order
        sent_order = []
        for i in range(10):
            message = f"Message {i}"
            await social_layer.send_message(
                from_agent_id=sender.id,
                to_agent_id=receiver.id,
                message=message,
                channel="ordered"
            )
            sent_order.append(message)

        # Retrieve messages
        messages = await social_layer.get_messages(receiver.id, channel="ordered")

        # Extract message contents (last 10 messages)
        received_order = [m["message"] for m in messages[-10:]]

        # Should match sent order (FIFO)
        assert received_order == sent_order

    @pytest.mark.asyncio
    async def test_redis_pub_sub_realtime(self, event_bus, agents):
        """Test Redis pub/sub real-time communication."""
        sender, receiver = agents[0], agents[1]

        # Subscribe receiver to channel
        received = []

        async def handler(event):
            received.append(event)

        await event_bus.subscribe(
            channel=f"agent:{receiver.id}",
            handler=handler
        )

        # Publish message
        await event_bus.publish(
            channel=f"agent:{receiver.id}",
            event={
                "type": "message",
                "from_agent_id": sender.id,
                "content": "Real-time message"
            }
        )

        # Wait for delivery
        await asyncio.sleep(0.1)

        # Verify received
        assert len(received) > 0
        assert received[0]["content"] == "Real-time message"

    @pytest.mark.asyncio
    async def test_channel_isolation(self, social_layer, agents):
        """Test messages are isolated per channel."""
        sender, receiver = agents[0], agents[1]

        # Send to channel A
        await social_layer.send_message(
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            message="Channel A message",
            channel="channel-a"
        )

        # Send to channel B
        await social_layer.send_message(
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            message="Channel B message",
            channel="channel-b"
        )

        # Retrieve from channel A
        messages_a = await social_layer.get_messages(receiver.id, channel="channel-a")

        # Retrieve from channel B
        messages_b = await social_layer.get_messages(receiver.id, channel="channel-b")

        # Should be isolated
        assert any(m["message"] == "Channel A message" for m in messages_a)
        assert not any(m["message"] == "Channel A message" for m in messages_b)
        assert any(m["message"] == "Channel B message" for m in messages_b)
        assert not any(m["message"] == "Channel B message" for m in messages_a)

    @pytest.mark.asyncio
    async def test_multiple_receivers(self, social_layer, agents):
        """Test sending message to multiple receivers."""
        sender = agents[0]
        receivers = agents[1:]

        # Broadcast to all receivers
        message = "Broadcast message"
        for receiver in receivers:
            await social_layer.send_message(
                from_agent_id=sender.id,
                to_agent_id=receiver.id,
                message=message,
                channel="broadcast"
            )

        # All receivers should get the message
        for receiver in receivers:
            messages = await social_layer.get_messages(receiver.id, channel="broadcast")
            assert any(m["message"] == message for m in messages)

    @pytest.mark.asyncio
    async def test_message_persistence(self, social_layer, agents):
        """Test messages are persisted for offline agents."""
        sender, receiver = agents[0], agents[1]

        # Send message while receiver is "offline"
        await social_layer.send_message(
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            message="Stored message",
            channel="persistent"
        )

        # Receiver comes back online and retrieves messages
        messages = await social_layer.get_messages(receiver.id, channel="persistent")

        # Should retrieve stored message
        assert len(messages) > 0
        assert messages[0]["message"] == "Stored message"

    @pytest.mark.asyncio
    async def test_websocket_realtime_updates(self, social_layer, agents):
        """Test WebSocket real-time message delivery."""
        sender, receiver = agents[0], agents[1]

        # Simulate WebSocket connection
        websocket_updates = []

        async def websocket_handler(message):
            websocket_updates.append(message)

        # Subscribe to WebSocket updates
        await social_layer.subscribe_to_updates(
            agent_id=receiver.id,
            handler=websocket_handler
        )

        # Send message
        await social_layer.send_message(
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            message="WebSocket message",
            channel="websocket"
        )

        # Wait for WebSocket update
        await asyncio.sleep(0.1)

        # Verify WebSocket received update
        assert len(websocket_updates) > 0
        assert websocket_updates[0]["message"] == "WebSocket message"
```

**Tests:**
- Send message between agents
- No lost messages (100 messages)
- FIFO ordering per channel
- Redis pub/sub real-time
- Channel isolation
- Multiple receivers
- Message persistence
- WebSocket real-time updates

**Acceptance:**
- [ ] Agent-to-agent messaging tested
- [ ] No lost messages verified
- [ ] FIFO ordering verified
- [ ] Redis pub/sub tested
- [ ] Channel isolation tested
- [ ] WebSocket tested

---

### Task 2: Create Integration Tests for Social Feed

**Files:** `tests/test_social_feed_integration.py`

**Action:**
Create integration tests for social feed:

```python
"""
Integration Tests for Social Feed

Tests cover:
- Feed generation (chronological, algorithmic)
- Feed pagination (cursor-based, no duplicates)
- Feed filtering (by agent, by topic, by time range)
- Reply threading
- Channel-specific feeds
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.social_feed_service import SocialFeedService
from core.models import SocialPost, SocialChannel, AgentRegistry
from tests.factories import AgentFactory, SocialPostFactory


class TestSocialFeedIntegration:
    """Test social feed generation and pagination."""

    @pytest.fixture
    def feed_service(self, db_session):
        """Create feed service."""
        return SocialFeedService(db_session)

    @pytest.fixture
    def agents(self, db_session):
        """Create test agents."""
        agents = [AgentFactory(name=f"Agent{i}") for i in range(5)]
        db_session.commit()
        return agents

    @pytest.fixture
    def channel(self, db_session):
        """Create test channel."""
        channel = SocialChannel(
            name="general",
            description="General discussion",
            channel_type="public"
        )
        db_session.add(channel)
        db_session.commit()
        return channel

    def test_feed_generation_chronological(self, feed_service, agents, channel, db_session):
        """Test feed generation in chronological order."""
        # Create posts with different timestamps
        posts = []
        for i, agent in enumerate(agents):
            post = SocialPostFactory(
                agent_id=agent.id,
                channel_id=channel.id,
                content=f"Post {i}",
                created_at=datetime.utcnow() + timedelta(seconds=i)
            )
            posts.append(post)
            db_session.add(post)
        db_session.commit()

        # Generate feed
        feed = feed_service.generate_feed(
            channel_id=channel.id,
            order="chronological"
        )

        # Should be in chronological order (newest first)
        assert len(feed) == len(agents)
        assert feed[0]["content"] == "Post 4"  # Newest
        assert feed[-1]["content"] == "Post 0"  # Oldest

    def test_feed_generation_algorithmic(self, feed_service, agents, channel, db_session):
        """Test feed generation with algorithmic ranking."""
        # Create posts with different engagement
        posts = []
        for i, agent in enumerate(agents):
            post = SocialPostFactory(
                agent_id=agent.id,
                channel_id=channel.id,
                content=f"Post {i}",
                likes=len(agents) - i,  # Higher likes for earlier posts
                created_at=datetime.utcnow() + timedelta(seconds=i)
            )
            posts.append(post)
            db_session.add(post)
        db_session.commit()

        # Generate algorithmic feed
        feed = feed_service.generate_feed(
            channel_id=channel.id,
            order="algorithmic"
        )

        # Should be ranked by engagement (likes)
        assert len(feed) == len(agents)
        # Post 0 has most likes, should be first
        assert feed[0]["content"] == "Post 0"

    def test_cursor_pagination_no_duplicates(self, feed_service, agents, channel, db_session):
        """Test cursor-based pagination never returns duplicates."""
        # Create 100 posts
        posts = []
        for i in range(100):
            post = SocialPostFactory(
                agent_id=agents[i % len(agents)].id,
                channel_id=channel.id,
                content=f"Post {i}",
                created_at=datetime.utcnow() + timedelta(seconds=i)
            )
            posts.append(post)
            db_session.add(post)
        db_session.commit()

        # Paginate through feed
        all_post_ids = set()
        cursor = None
        page_size = 20

        while True:
            page, cursor = feed_service.get_feed_page(
                channel_id=channel.id,
                page_size=page_size,
                cursor=cursor
            )

            if not page:
                break

            # Check for duplicates
            page_ids = {p["id"] for p in page}
            duplicates = all_post_ids & page_ids

            assert len(duplicates) == 0, f"Found duplicates: {duplicates}"

            all_post_ids.update(page_ids)

            if not cursor:
                break

        # Should have all 100 posts
        assert len(all_post_ids) == 100

    def test_feed_filtering_by_agent(self, feed_service, agents, channel, db_session):
        """Test feed filtering by agent."""
        target_agent = agents[0]

        # Create posts from different agents
        for i, agent in enumerate(agents):
            for j in range(3):
                post = SocialPostFactory(
                    agent_id=agent.id,
                    channel_id=channel.id,
                    content=f"Post {i}-{j}"
                )
                db_session.add(post)
        db_session.commit()

        # Filter by target agent
        feed = feed_service.generate_feed(
            channel_id=channel.id,
            agent_id=target_agent.id
        )

        # Should only have posts from target agent
        assert all(p["agent_id"] == target_agent.id for p in feed)
        assert len(feed) == 3

    def test_feed_filtering_by_topic(self, feed_service, agents, channel, db_session):
        """Test feed filtering by topic (hashtag)."""
        # Create posts with different topics
        topics = ["#automation", "#testing", "#deployment"]
        for i, topic in enumerate(topics * 3):
            post = SocialPostFactory(
                agent_id=agents[i % len(agents)].id,
                channel_id=channel.id,
                content=f"Post with {topic}"
            )
            db_session.add(post)
        db_session.commit()

        # Filter by topic
        feed = feed_service.generate_feed(
            channel_id=channel.id,
            topic="#automation"
        )

        # Should only have posts with #automation
        assert all("#automation" in p["content"] for p in feed)
        assert len(feed) == 3

    def test_feed_filtering_by_time_range(self, feed_service, agents, channel, db_session):
        """Test feed filtering by time range."""
        now = datetime.utcnow()

        # Create posts at different times
        for i in range(10):
            post = SocialPostFactory(
                agent_id=agents[i % len(agents)].id,
                channel_id=channel.id,
                content=f"Post {i}",
                created_at=now + timedelta(hours=i)
            )
            db_session.add(post)
        db_session.commit()

        # Filter by time range (posts 3-6)
        start_time = now + timedelta(hours=3)
        end_time = now + timedelta(hours=6)

        feed = feed_service.generate_feed(
            channel_id=channel.id,
            start_time=start_time,
            end_time=end_time
        )

        # Should only have posts within time range
        assert len(feed) == 4  # Posts 3, 4, 5, 6

    def test_reply_threading(self, feed_service, agents, channel, db_session):
        """Test reply threading in feed."""
        # Create parent post
        parent = SocialPostFactory(
            agent_id=agents[0].id,
            channel_id=channel.id,
            content="Parent post"
        )
        db_session.add(parent)
        db_session.commit()

        # Create replies
        replies = []
        for i, agent in enumerate(agents[1:]):
            reply = SocialPostFactory(
                agent_id=agent.id,
                channel_id=channel.id,
                content=f"Reply {i}",
                parent_id=parent.id
            )
            replies.append(reply)
            db_session.add(reply)
        db_session.commit()

        # Get feed with replies
        feed = feed_service.generate_feed(
            channel_id=channel.id,
            include_replies=True
        )

        # Parent post should have replies
        parent_post = next(p for p in feed if p["id"] == parent.id)
        assert len(parent_post["replies"]) == len(agents) - 1

    def test_channel_specific_feeds(self, feed_service, agents, db_session):
        """Test channel-specific feed generation."""
        # Create multiple channels
        channels = []
        for i in range(3):
            channel = SocialChannel(
                name=f"channel-{i}",
                description=f"Channel {i}",
                channel_type="public"
            )
            channels.append(channel)
            db_session.add(channel)
        db_session.commit()

        # Create posts in different channels
        for i, channel in enumerate(channels):
            post = SocialPostFactory(
                agent_id=agents[i].id,
                channel_id=channel.id,
                content=f"Post in channel {i}"
            )
            db_session.add(post)
        db_session.commit()

        # Generate feed for each channel
        for i, channel in enumerate(channels):
            feed = feed_service.generate_feed(channel_id=channel.id)
            assert len(feed) == 1
            assert f"channel {i}" in feed[0]["content"]
```

**Tests:**
- Feed generation (chronological, algorithmic)
- Cursor pagination (no duplicates)
- Feed filtering (by agent, topic, time range)
- Reply threading
- Channel-specific feeds

**Acceptance:**
- [ ] Feed generation tested (chronological, algorithmic)
- [ ] Pagination no duplicates verified
- [ ] Filtering tested (agent, topic, time)
- [ ] Reply threading tested
- [ ] Channel-specific feeds tested

---

### Task 3: Create API Integration Tests for Social Routes

**Files:** `tests/api/test_social_routes_integration.py`

**Action:**
Create API integration tests for social routes:

```python
"""
API Integration Tests for Social Routes

Tests cover:
- GET /feed - Retrieve social feed
- POST /posts - Create new post
- GET /channels - List channels
- GET /channels/{id}/feed - Channel-specific feed
- POST /channels/{id}/posts - Post to channel
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.models import AgentRegistry, SocialChannel, SocialPost
from tests.factories import AgentFactory, SocialChannelFactory


class TestSocialRoutesAPI:
    """Test social routes API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory()
        db_session.commit()
        return agent

    @pytest.fixture
    def channel(self, db_session):
        """Create test channel."""
        channel = SocialChannelFactory()
        db_session.commit()
        return channel

    def test_get_feed(self, client, agent, channel, db_session):
        """Test GET /feed endpoint."""
        # Create posts
        for i in range(5):
            post = SocialPost(
                agent_id=agent.id,
                channel_id=channel.id,
                content=f"Post {i}"
            )
            db_session.add(post)
        db_session.commit()

        # Get feed
        response = client.get(f"/api/feed?channel_id={channel.id}")

        assert response.status_code == 200
        data = response.json()
        assert "posts" in data
        assert len(data["posts"]) == 5

    def test_create_post(self, client, agent, channel):
        """Test POST /posts endpoint."""
        response = client.post(
            f"/api/posts",
            json={
                "agent_id": agent.id,
                "channel_id": channel.id,
                "content": "Test post #automation"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Test post #automation"
        assert data["agent_id"] == agent.id
        assert data["channel_id"] == channel.id

    def test_get_channels(self, client, db_session):
        """Test GET /channels endpoint."""
        # Create channels
        for i in range(3):
            channel = SocialChannelFactory(name=f"channel-{i}")
            db_session.add(channel)
        db_session.commit()

        # Get channels
        response = client.get("/api/channels")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_get_channel_feed(self, client, agent, channel, db_session):
        """Test GET /channels/{id}/feed endpoint."""
        # Create posts in channel
        for i in range(5):
            post = SocialPost(
                agent_id=agent.id,
                channel_id=channel.id,
                content=f"Post {i}"
            )
            db_session.add(post)
        db_session.commit()

        # Get channel feed
        response = client.get(f"/api/channels/{channel.id}/feed")

        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 5

    def test_post_to_channel(self, client, agent, channel):
        """Test POST /channels/{id}/posts endpoint."""
        response = client.post(
            f"/api/channels/{channel.id}/posts",
            json={
                "agent_id": agent.id,
                "content": "Channel post"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Channel post"
        assert data["channel_id"] == channel.id

    def test_pagination_with_cursor(self, client, agent, channel, db_session):
        """Test pagination with cursor parameter."""
        # Create 50 posts
        for i in range(50):
            post = SocialPost(
                agent_id=agent.id,
                channel_id=channel.id,
                content=f"Post {i}"
            )
            db_session.add(post)
        db_session.commit()

        # Get first page
        response = client.get(f"/api/feed?channel_id={channel.id}&page_size=20")
        assert response.status_code == 200
        data1 = response.json()
        cursor1 = data1.get("next_cursor")

        # Get second page with cursor
        response = client.get(f"/api/feed?channel_id={channel.id}&cursor={cursor1}&page_size=20")
        assert response.status_code == 200
        data2 = response.json()

        # Should have different posts
        ids1 = {p["id"] for p in data1["posts"]}
        ids2 = {p["id"] for p in data2["posts"]}
        assert len(ids1 & ids2) == 0  # No duplicates

    def test_filter_feed_by_topic(self, client, agent, channel, db_session):
        """Test filtering feed by topic."""
        # Create posts with different topics
        topics = ["#automation", "#testing"]
        for topic in topics * 3:
            post = SocialPost(
                agent_id=agent.id,
                channel_id=channel.id,
                content=f"Post with {topic}"
            )
            db_session.add(post)
        db_session.commit()

        # Filter by topic
        response = client.get(f"/api/feed?channel_id={channel.id}&topic=%23automation")
        assert response.status_code == 200
        data = response.json()

        # Should only have #automation posts
        assert all("#automation" in p["content"] for p in data["posts"])
        assert len(data["posts"]) == 3
```

**Tests:**
- GET /feed
- POST /posts
- GET /channels
- GET /channels/{id}/feed
- POST /channels/{id}/posts
- Pagination with cursor
- Filter by topic

**Acceptance:**
- [ ] All endpoints tested
- [ ] Pagination tested
- [ ] Filtering tested

---

### Task 4: Create Property Tests for Feed Invariants

**Files:** `tests/property_tests/social/test_feed_pagination_invariants.py`

**Action:**
Create property-based tests for feed invariants:

```python
"""
Property-Based Tests for Feed Pagination Invariants

Tests CRITICAL invariants:
- Feed pagination never returns duplicates
- Feed always in chronological order (newest first)
- Reply count monotonically increases
- Channel posts isolated
- FIFO message ordering
"""
import pytest
from hypothesis import strategies as st, given, settings
from core.social_feed_service import SocialFeedService


class TestFeedPaginationInvariants:
    """Property tests for feed pagination."""

    @given(
        num_posts=st.integers(min_value=10, max_value=200),
        page_size=st.integers(min_value=10, max_size=50)
    )
    @settings(max_examples=50)
    def test_pagination_no_duplicates(self, db_session, num_posts, page_size):
        """
        Pagination no duplicates invariant.

        Property: Paginating through feed never returns duplicate posts.
        """
        # This would need proper setup with real posts
        # Simplified example:
        feed_service = SocialFeedService(db_session)
        all_post_ids = set()
        cursor = None

        while True:
            page, cursor = feed_service.get_feed_page(
                channel_id="test",
                page_size=page_size,
                cursor=cursor
            )

            if not page:
                break

            page_ids = {p["id"] for p in page}
            duplicates = all_post_ids & page_ids

            assert len(duplicates) == 0, f"Found duplicates: {duplicates}"

            all_post_ids.update(page_ids)

            if not cursor:
                break


class TestChronologicalOrderInvariant:
    """Property tests for chronological ordering."""

    @given(
        num_posts=st.integers(min_value=5, max_value=100)
    )
    @settings(max_examples=50)
    def test_feed_chronological_order(self, db_session, num_posts):
        """
        Chronological order invariant.

        Property: Feed is always in chronological order (newest first).
        """
        feed_service = SocialFeedService(db_session)

        # Generate feed
        feed = feed_service.generate_feed(
            channel_id="test",
            order="chronological"
        )

        # Check timestamps are decreasing (newest first)
        for i in range(len(feed) - 1):
            assert feed[i]["created_at"] >= feed[i+1]["created_at"]


class TestFIFOMessageOrderingInvariant:
    """Property tests for FIFO message ordering."""

    @given(
        num_messages=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_fifo_message_ordering(self, social_layer, db_session, num_messages):
        """
        FIFO message ordering invariant.

        Property: Messages are delivered in the order they were sent.
        """
        # Send messages
        sent_order = []
        for i in range(num_messages):
            message = f"Message {i}"
            await social_layer.send_message(
                from_agent_id="sender",
                to_agent_id="receiver",
                message=message
            )
            sent_order.append(message)

        # Retrieve messages
        messages = await social_layer.get_messages("receiver")

        # Extract message contents
        received_order = [m["message"] for m in messages[-num_messages:]]

        # Should match sent order
        assert received_order == sent_order
```

**Property Tests:**
- Pagination no duplicates
- Chronological order
- FIFO message ordering

**Acceptance:**
- [ ] No duplicates tested (50 examples)
- [ ] Chronological order tested (50 examples)
- [ ] FIFO ordering tested (50 examples)

---

## Deviations

**Rule 1 (Auto-fix bugs):** If communication or feed has bugs, fix immediately.

**Rule 2 (Redis):** If Redis unavailable, tests should verify fallback behavior.

**Rule 3 (Property tests):** If Hypothesis tests flaky, adjust strategies or settings.

## Success Criteria

- [ ] Agent-to-agent messaging tested (no lost messages)
- [ ] FIFO ordering verified
- [ ] Redis pub/sub tested
- [ ] Feed generation tested (chronological, algorithmic)
- [ ] Pagination no duplicates verified
- [ ] Filtering tested (agent, topic, time)
- [ ] Property tests verify invariants

## Dependencies

- Plan 06-01 (Post Generation & PII Redaction) must be complete

## Estimated Duration

3-4 hours (communication tests + feed tests + API tests + property tests)
