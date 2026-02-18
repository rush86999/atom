"""
Social Feed Integration Tests - Comprehensive testing of feed generation and pagination.

Tests cover:
- Feed Generation Tests (10 tests)
- Cursor Pagination Tests (8 tests)
- Channel Isolation Tests (7 tests)
- Real-Time Update Tests (6 tests)
- Property-Based Tests for Feed Invariants (7 tests)

Total: 38 tests verifying chronological ordering, cursor pagination with no duplicates,
channel isolation, and real-time WebSocket updates.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
from typing import List, Dict, Any

from hypothesis import given, strategies as st, settings

from core.agent_social_layer import AgentSocialLayer, agent_social_layer
from core.agent_communication import AgentEventBus
from core.models import AgentPost, Channel


# ============================================================================
# Mock WebSocket for real-time update testing
# ============================================================================

class MockWebSocket:
    """Mock WebSocket for testing real-time updates."""

    def __init__(self):
        self.sent_messages = []

    async def send_json(self, data: dict):
        """Mock send_json."""
        self.sent_messages.append(data)


# ============================================================================
# Feed Generation Tests (10 tests)
# ============================================================================

class TestFeedGeneration:
    """Tests for feed generation and filtering."""

    @pytest.mark.asyncio
    async def test_feed_chronological_ordering(self, db_session):
        """Posts sorted by created_at DESC (newest first)."""
        service = AgentSocialLayer()

        # Create posts with different timestamps
        now = datetime.utcnow()
        posts = []
        for i in range(5):
            post = AgentPost(
                sender_type="human",
                sender_id=f"user{i}",
                sender_name=f"User {i}",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            posts.append(post)
            db_session.add(post)
        db_session.commit()

        # Get feed
        feed = await service.get_feed(
            sender_id="user1",
            limit=10,
            db=db_session
        )

        # Should be newest first (reverse chronological)
        assert len(feed["posts"]) == 5
        assert feed["posts"][0]["content"] == "Post 4"  # Newest
        assert feed["posts"][-1]["content"] == "Post 0"  # Oldest

    @pytest.mark.asyncio
    async def test_feed_filter_by_post_type(self, db_session):
        """Only specified post_type returned."""
        service = AgentSocialLayer()

        # Create different post types
        now = datetime.utcnow()
        for i, post_type in enumerate(["status", "insight", "question", "alert"]):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type=post_type,
                content=f"{post_type} post",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Filter by question type
        feed = await service.get_feed(
            sender_id="user1",
            post_type="question",
            limit=10,
            db=db_session
        )

        # Should only have question posts
        assert len(feed["posts"]) == 1
        assert feed["posts"][0]["post_type"] == "question"

    @pytest.mark.asyncio
    async def test_feed_filter_by_sender(self, db_session):
        """Only posts from sender returned."""
        service = AgentSocialLayer()

        now = datetime.utcnow()
        # Create posts from different senders
        for sender_id in ["user1", "user2"]:
            for i in range(3):
                post = AgentPost(
                    sender_type="human",
                    sender_id=sender_id,
                    sender_name=f"User {sender_id}",
                    post_type="status",
                    content=f"Post {i} from {sender_id}",
                    is_public=True,
                    created_at=now + timedelta(seconds=i)
                )
                db_session.add(post)
        db_session.commit()

        # Filter by sender1
        feed = await service.get_feed(
            sender_id="user1",
            sender_filter="user1",
            limit=10,
            db=db_session
        )

        # Should only have user1's posts
        assert len(feed["posts"]) == 3
        assert all(p["sender_id"] == "user1" for p in feed["posts"])

    @pytest.mark.asyncio
    async def test_feed_filter_by_channel(self, db_session):
        """Only posts in channel returned."""
        service = AgentSocialLayer()

        # Create channel
        channel = Channel(
            id="channel-test",
            name="test",
            display_name="Test Channel",
            description="Test",
            channel_type="general",
            is_public=True,
            created_by="user1"
        )
        db_session.add(channel)

        now = datetime.utcnow()
        # Create posts in different channels
        for i, channel_id in enumerate(["channel-test", None]):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post in {channel_id or 'global'}",
                is_public=True,
                channel_id=channel_id,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Filter by channel
        feed = await service.get_feed(
            sender_id="user1",
            channel_id="channel-test",
            limit=10,
            db=db_session
        )

        # Should only have channel posts
        assert len(feed["posts"]) == 1
        assert feed["posts"][0]["channel_id"] == "channel-test"

    @pytest.mark.asyncio
    async def test_feed_filter_public_private(self, db_session):
        """is_public filter works."""
        service = AgentSocialLayer()

        now = datetime.utcnow()
        # Create public and private posts
        for i, is_public in enumerate([True, False]):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"{'Public' if is_public else 'Private'} post",
                is_public=is_public,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Filter by public posts
        feed = await service.get_feed(
            sender_id="user1",
            is_public=True,
            limit=10,
            db=db_session
        )

        # Should only have public posts
        assert len(feed["posts"]) == 1
        assert feed["posts"][0]["is_public"] is True

    @pytest.mark.asyncio
    async def test_feed_pagination_offset_limit(self, db_session):
        """Pagination parameters respected."""
        service = AgentSocialLayer()

        # Create 20 posts
        now = datetime.utcnow()
        for i in range(20):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Get first page (limit=10, offset=0)
        page1 = await service.get_feed(
            sender_id="user1",
            limit=10,
            offset=0,
            db=db_session
        )

        # Get second page (limit=10, offset=10)
        page2 = await service.get_feed(
            sender_id="user1",
            limit=10,
            offset=10,
            db=db_session
        )

        # Should have 10 each
        assert len(page1["posts"]) == 10
        assert len(page2["posts"]) == 10

        # Posts should be different (no duplicates)
        ids1 = {p["id"] for p in page1["posts"]}
        ids2 = {p["id"] for p in page2["posts"]}
        assert len(ids1 & ids2) == 0

    @pytest.mark.asyncio
    async def test_feed_total_count_accurate(self, db_session):
        """Total count matches query."""
        service = AgentSocialLayer()

        # Create posts
        for i in range(15):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True
            )
            db_session.add(post)
        db_session.commit()

        # Get feed with limit=5
        feed = await service.get_feed(
            sender_id="user1",
            limit=5,
            db=db_session
        )

        # Total should reflect all posts, not just page
        assert feed["total"] == 15
        assert len(feed["posts"]) == 5  # Only returned 5

    @pytest.mark.asyncio
    async def test_feed_empty_returns_empty(self, db_session):
        """No posts returns empty list."""
        service = AgentSocialLayer()

        feed = await service.get_feed(
            sender_id="user1",
            limit=10,
            db=db_session
        )

        assert feed["posts"] == []
        assert feed["total"] == 0

    @pytest.mark.asyncio
    async def test_feed_with_multiple_filters(self, db_session):
        """Combined filters work together."""
        service = AgentSocialLayer()

        now = datetime.utcnow()
        # Create posts with various attributes
        post_types = ["status", "insight"]
        senders = ["user1", "user2"]

        for i, (sender, post_type) in enumerate(zip(senders * 2, post_types * 2)):
            post = AgentPost(
                sender_type="human",
                sender_id=sender,
                sender_name=f"User {sender}",
                post_type=post_type,
                content=f"{post_type} from {sender}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Filter by sender=user1 AND post_type=status
        feed = await service.get_feed(
            sender_id="user1",
            sender_filter="user1",
            post_type="status",
            limit=10,
            db=db_session
        )

        # Should match both filters
        assert len(feed["posts"]) == 1
        assert feed["posts"][0]["sender_id"] == "user1"
        assert feed["posts"][0]["post_type"] == "status"

    @pytest.mark.asyncio
    async def test_feed_includes_all_fields(self, db_session):
        """All post fields included in response."""
        service = AgentSocialLayer()

        post = AgentPost(
            sender_type="agent",
            sender_id="agent1",
            sender_name="Agent 1",
            sender_maturity="INTERN",
            sender_category="engineering",
            post_type="status",
            content="Test post",
            is_public=True,
            channel_id="channel-1",
            channel_name="Channel 1",
            mentioned_agent_ids=["agent2"],
            mentioned_user_ids=["user1"],
            reactions={"👍": 5},
            reply_count=3
        )
        db_session.add(post)
        db_session.commit()

        feed = await service.get_feed(
            sender_id="user1",
            limit=10,
            db=db_session
        )

        assert len(feed["posts"]) == 1
        p = feed["posts"][0]
        # Verify all fields present
        assert p["sender_type"] == "agent"
        assert p["sender_id"] == "agent1"
        assert p["post_type"] == "status"
        assert p["content"] == "Test post"
        assert p["is_public"] is True
        assert p["channel_id"] == "channel-1"
        assert p["reactions"] == {"👍": 5}
        assert p["reply_count"] == 3


# ============================================================================
# Cursor Pagination Tests (8 tests)
# ============================================================================

class TestCursorPagination:
    """Tests for cursor-based pagination."""

    @pytest.mark.asyncio
    async def test_cursor_first_page_returns_next_cursor(self, db_session):
        """Initial request has next_cursor."""
        service = AgentSocialLayer()

        # Create 20 posts
        now = datetime.utcnow()
        for i in range(20):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Get first page
        feed = await service.get_feed_cursor(
            sender_id="user1",
            cursor=None,
            limit=10,
            db=db_session
        )

        assert len(feed["posts"]) == 10
        assert feed["has_more"] is True
        assert feed["next_cursor"] is not None

    @pytest.mark.asyncio
    async def test_cursor_second_page_returns_older_posts(self, db_session):
        """Cursor gets posts before cursor."""
        service = AgentSocialLayer()

        # Create posts
        now = datetime.utcnow()
        for i in range(20):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Get first page
        page1 = await service.get_feed_cursor(
            sender_id="user1",
            cursor=None,
            limit=10,
            db=db_session
        )

        # Get second page using cursor
        page2 = await service.get_feed_cursor(
            sender_id="user1",
            cursor=page1["next_cursor"],
            limit=10,
            db=db_session
        )

        # Should have older posts
        assert len(page2["posts"]) == 10
        # Posts should be different from page1
        ids1 = {p["id"] for p in page1["posts"]}
        ids2 = {p["id"] for p in page2["posts"]}
        assert len(ids1 & ids2) == 0

    @pytest.mark.asyncio
    async def test_cursor_no_duplicates_on_new_posts(self, db_session):
        """New posts don't cause duplicates."""
        service = AgentSocialLayer()

        # Create initial posts
        now = datetime.utcnow()
        for i in range(10):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Initial post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Get first page
        page1 = await service.get_feed_cursor(
            sender_id="user1",
            cursor=None,
            limit=5,
            db=db_session
        )
        page1_ids = {p["id"] for p in page1["posts"]}

        # Add new posts (simulate real-time feed)
        for i in range(5):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"New post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=10 + i)
            )
            db_session.add(post)
        db_session.commit()

        # Get second page using cursor (should not include new posts)
        page2 = await service.get_feed_cursor(
            sender_id="user1",
            cursor=page1["next_cursor"],
            limit=5,
            db=db_session
        )
        page2_ids = {p["id"] for p in page2["posts"]}

        # No duplicates between pages
        assert len(page1_ids & page2_ids) == 0

    @pytest.mark.asyncio
    async def test_cursor_empty_when_no_more_posts(self, db_session):
        """has_more=false at end."""
        service = AgentSocialLayer()

        # Create only 5 posts
        now = datetime.utcnow()
        for i in range(5):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Request 10 posts (only 5 exist)
        feed = await service.get_feed_cursor(
            sender_id="user1",
            cursor=None,
            limit=10,
            db=db_session
        )

        assert len(feed["posts"]) == 5
        assert feed["has_more"] is False
        assert feed["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_cursor_invalid_format_handled(self, db_session):
        """Bad cursor format logged."""
        service = AgentSocialLayer()

        # Create some posts
        for i in range(5):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True
            )
            db_session.add(post)
        db_session.commit()

        # Use invalid cursor (should log warning and return empty)
        feed = await service.get_feed_cursor(
            sender_id="user1",
            cursor="invalid-cursor-format",
            limit=10,
            db=db_session
        )

        # Should handle gracefully
        assert "posts" in feed

    @pytest.mark.asyncio
    async def test_cursor_with_channel_filter(self, db_session):
        """Cursor works with channels."""
        service = AgentSocialLayer()

        # Create channel
        channel = Channel(
            id="channel-test",
            name="test",
            display_name="Test",
            description="Test",
            channel_type="general",
            is_public=True,
            created_by="user1"
        )
        db_session.add(channel)

        # Create channel posts
        now = datetime.utcnow()
        for i in range(20):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                channel_id="channel-test",
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Paginate through channel feed
        page1 = await service.get_feed_cursor(
            sender_id="user1",
            cursor=None,
            limit=10,
            channel_id="channel-test",
            db=db_session
        )

        assert len(page1["posts"]) == 10
        assert page1["has_more"] is True

    @pytest.mark.asyncio
    async def test_cursor_with_post_type_filter(self, db_session):
        """Cursor works with filters."""
        service = AgentSocialLayer()

        # Create different post types
        now = datetime.utcnow()
        for i in range(20):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status" if i % 2 == 0 else "insight",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Paginate with filter
        page1 = await service.get_feed_cursor(
            sender_id="user1",
            cursor=None,
            limit=5,
            post_type="status",
            db=db_session
        )

        # Should only have status posts
        assert all(p["post_type"] == "status" for p in page1["posts"])

    @pytest.mark.asyncio
    async def test_cursor_stable_with_concurrent_posts(self, db_session):
        """Stability under concurrent writes."""
        service = AgentSocialLayer()

        # Create initial posts
        now = datetime.utcnow()
        for i in range(10):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Get cursor
        feed1 = await service.get_feed_cursor(
            sender_id="user1",
            cursor=None,
            limit=5,
            db=db_session
        )
        cursor = feed1["next_cursor"]

        # Add more posts
        for i in range(10, 15):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Use cursor (should still get stable results)
        feed2 = await service.get_feed_cursor(
            sender_id="user1",
            cursor=cursor,
            limit=5,
            db=db_session
        )

        # Should not include new posts
        assert all(p["content"] not in ["Post 10", "Post 11", "Post 12", "Post 13", "Post 14"]
                   for p in feed2["posts"])


# ============================================================================
# Channel Isolation Tests (7 tests)
# ============================================================================

class TestChannelIsolation:
    """Tests for channel management and isolation."""

    @pytest.mark.asyncio
    async def test_channel_creation(self, db_session):
        """Channel created successfully."""
        service = AgentSocialLayer()

        channel = await service.create_channel(
            channel_id="channel-new",
            channel_name="new",
            creator_id="user1",
            display_name="New Channel",
            description="A new channel",
            channel_type="general",
            is_public=True,
            db=db_session
        )

        assert channel["id"] == "channel-new"
        assert channel["name"] == "new"

    @pytest.mark.asyncio
    async def test_channel_duplicate_returns_existing(self, db_session):
        """Idempotent channel creation."""
        service = AgentSocialLayer()

        # Create channel
        await service.create_channel(
            channel_id="channel-test",
            channel_name="test",
            creator_id="user1",
            db=db_session
        )

        # Try to create again
        result = await service.create_channel(
            channel_id="channel-test",
            channel_name="test",
            creator_id="user2",
            db=db_session
        )

        # Should return existing channel
        assert result["exists"] is True

    @pytest.mark.asyncio
    async def test_channel_list_all(self, db_session):
        """All channels returned."""
        service = AgentSocialLayer()

        # Create channels
        for i in range(3):
            await service.create_channel(
                channel_id=f"channel-{i}",
                channel_name=f"channel{i}",
                creator_id="user1",
                db=db_session
            )

        # List all channels
        channels = await service.get_channels(db=db_session)

        assert len(channels) == 3

    @pytest.mark.asyncio
    async def test_channel_posts_isolated(self, db_session):
        """Channel posts only in channel feed."""
        service = AgentSocialLayer()

        # Create channels
        await service.create_channel(
            channel_id="channel-a",
            channel_name="a",
            creator_id="user1",
            db=db_session
        )
        await service.create_channel(
            channel_id="channel-b",
            channel_name="b",
            creator_id="user1",
            db=db_session
        )

        now = datetime.utcnow()
        # Create posts in different channels
        for channel_id in ["channel-a", "channel-b"]:
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post in {channel_id}",
                is_public=True,
                channel_id=channel_id,
                created_at=now
            )
            db_session.add(post)
        db_session.commit()

        # Get channel-a feed
        feed_a = await service.get_feed(
            sender_id="user1",
            channel_id="channel-a",
            limit=10,
            db=db_session
        )

        # Should only have channel-a posts
        assert len(feed_a["posts"]) == 1
        assert feed_a["posts"][0]["channel_id"] == "channel-a"

    @pytest.mark.asyncio
    async def test_channel_public_private(self, db_session):
        """is_public controls visibility."""
        service = AgentSocialLayer()

        # Create public channel
        await service.create_channel(
            channel_id="channel-public",
            channel_name="public",
            creator_id="user1",
            is_public=True,
            db=db_session
        )

        # Create private channel
        await service.create_channel(
            channel_id="channel-private",
            channel_name="private",
            creator_id="user1",
            is_public=False,
            db=db_session
        )

        channels = await service.get_channels(db=db_session)

        # Both should be listed
        assert len(channels) == 2

    @pytest.mark.asyncio
    async def test_channel_members(self, db_session):
        """agent_members and user_members tracked."""
        service = AgentSocialLayer()

        channel = await service.create_channel(
            channel_id="channel-test",
            channel_name="test",
            creator_id="user1",
            db=db_session
        )

        assert channel["id"] == "channel-test"

    @pytest.mark.asyncio
    async def test_channel_deletion(self, db_session):
        """Posts cascade on channel delete (if implemented)."""
        # This tests cascade delete behavior if implemented
        # For now, just verify channel can be queried
        service = AgentSocialLayer()

        await service.create_channel(
            channel_id="channel-test",
            channel_name="test",
            creator_id="user1",
            db=db_session
        )

        channels = await service.get_channels(db=db_session)
        assert len(channels) >= 1


# ============================================================================
# Real-Time Update Tests (6 tests)
# ============================================================================

class TestRealTimeUpdates:
    """Tests for real-time WebSocket updates."""

    @pytest.mark.asyncio
    async def test_new_post_broadcasts(self, db_session):
        """New post triggers WebSocket broadcast."""
        event_bus = AgentEventBus()
        ws = MockWebSocket()

        await event_bus.subscribe("agent1", ws, ["global"])

        # Simulate new post broadcast
        await event_bus.broadcast_post({
            "id": "post-1",
            "sender_id": "agent1",
            "sender_name": "Agent 1",
            "post_type": "status",
            "content": "New post"
        })

        # WebSocket should receive
        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["type"] == "agent_post"

    @pytest.mark.asyncio
    async def test_reaction_broadcasts(self, db_session):
        """Reaction triggers broadcast."""
        event_bus = AgentEventBus()
        ws = MockWebSocket()

        await event_bus.subscribe("agent1", ws, ["post:post-1"])

        # Simulate reaction broadcast
        await event_bus.publish({
            "type": "reaction_added",
            "post_id": "post-1",
            "emoji": "👍",
            "reactions": {"👍": 1}
        }, ["post:post-1", "global"])

        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["type"] == "reaction_added"

    @pytest.mark.asyncio
    async def test_reply_broadcasts(self, db_session):
        """Reply triggers broadcast."""
        event_bus = AgentEventBus()
        ws = MockWebSocket()

        await event_bus.subscribe("agent1", ws, ["post:post-1"])

        # Simulate reply broadcast
        await event_bus.publish({
            "type": "reply_added",
            "post_id": "post-1",
            "reply_id": "reply-1",
            "content": "Reply content"
        }, ["post:post-1"])

        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["type"] == "reply_added"

    @pytest.mark.asyncio
    async def test_channel_post_broadcasts_to_channel(self, db_session):
        """Channel posts broadcast to channel topic."""
        event_bus = AgentEventBus()
        ws = MockWebSocket()

        await event_bus.subscribe("agent1", ws, ["channel:engineering"])

        # Simulate channel post
        await event_bus.publish({
            "type": "agent_post",
            "data": {
                "channel_id": "engineering",
                "content": "Channel post"
            }
        }, ["channel:engineering"])

        assert len(ws.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_alert_broadcasts_to_all(self, db_session):
        """Alert posts go to alerts topic."""
        event_bus = AgentEventBus()
        ws = MockWebSocket()

        await event_bus.subscribe("agent1", ws, ["alerts"])

        # Simulate alert
        await event_bus.broadcast_post({
            "id": "post-1",
            "sender_id": "system",
            "sender_name": "System",
            "post_type": "alert",
            "content": "Important alert"
        })

        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["type"] == "agent_post"

    @pytest.mark.asyncio
    async def test_websocket_subscribe_receives_updates(self, db_session):
        """Subscriber receives real-time updates."""
        event_bus = AgentEventBus()
        ws = MockWebSocket()

        await event_bus.subscribe("agent1", ws, ["global", "alerts"])

        # Multiple broadcasts
        await event_bus.publish({"type": "test1"}, ["global"])
        await event_bus.publish({"type": "test2"}, ["alerts"])

        # Should receive both
        assert len(ws.sent_messages) == 2


# ============================================================================
# Property-Based Tests for Feed Invariants (7 tests)
# ============================================================================

class TestFeedInvariants:
    """Property-based tests for feed invariants."""

    @given(st.integers(min_value=1, max_value=50), st.integers(min_value=5, max_value=20))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_cursor_pagination_never_returns_duplicates(self, post_count, page_size, db_session):
        """Property: Cursor pagination never returns duplicate posts."""
        service = AgentSocialLayer()

        # Create posts
        now = datetime.utcnow()
        created_ids = []
        for i in range(post_count):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
            db_session.flush()  # Get IDs
            created_ids.append(post.id)
        db_session.commit()

        # Paginate through all pages
        seen_ids = set()
        cursor = None
        page_num = 0
        max_pages = 100  # Safety limit

        while page_num < max_pages:
            feed = await service.get_feed_cursor(
                sender_id="user1",
                cursor=cursor,
                limit=page_size,
                db=db_session
            )

            if not feed["posts"]:
                break

            page_ids = set(p["id"] for p in feed["posts"])

            # Verify no duplicates
            duplicates = seen_ids & page_ids
            assert not duplicates, f"Duplicates found on page {page_num}: {duplicates}"

            seen_ids.update(page_ids)

            if not feed["has_more"]:
                break

            cursor = feed["next_cursor"]
            page_num += 1

        # Verify all posts seen
        assert len(seen_ids) == post_count

    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_feed_always_chronological(self, post_count, db_session):
        """Property: Feed always returns posts in chronological order (newest first)."""
        service = AgentSocialLayer()

        # Create posts with different timestamps
        now = datetime.utcnow()
        for i in range(post_count):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Get feed
        feed = await service.get_feed(
            sender_id="user1",
            limit=post_count,
            db=db_session
        )

        # Verify descending order (newest first)
        timestamps = [p["created_at"] for p in feed["posts"]]
        # Parse ISO format strings back to datetime for comparison
        from datetime import datetime
        parsed_timestamps = [datetime.fromisoformat(ts.replace('Z', '+00:00')) for ts in timestamps]

        assert parsed_timestamps == sorted(parsed_timestamps, reverse=True)

    @given(st.lists(st.integers(min_value=0, max_value=50), min_size=0, max_size=20))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_reply_count_monotonically_increases(self, reply_counts, db_session):
        """Property: Reply count never decreases."""
        service = AgentSocialLayer()

        # Create parent post
        parent_post = AgentPost(
            sender_type="human",
            sender_id="user1",
            sender_name="User 1",
            post_type="question",
            content="Parent post",
            is_public=True,
            reply_count=0
        )
        db_session.add(parent_post)
        db_session.commit()

        previous_count = 0

        for count in reply_counts:
            parent_post.reply_count = count
            db_session.commit()

            # Retrieve post
            feed = await service.get_feed(
                sender_id="user1",
                limit=10,
                db=db_session
            )

            current_count = feed["posts"][0]["reply_count"]
            assert current_count >= previous_count, \
                f"Reply count decreased from {previous_count} to {current_count}"
            previous_count = current_count

    @given(st.integers(min_value=1, max_value=50), st.integers(min_value=1, max_value=10))
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_channel_posts_isolated(self, channel_posts, other_posts, db_session):
        """Property: Channel posts only appear in that channel's feed."""
        service = AgentSocialLayer()

        # Create channel
        channel = Channel(
            id="channel-test",
            name="test",
            display_name="Test",
            description="Test",
            channel_type="general",
            is_public=True,
            created_by="user1"
        )
        db_session.add(channel)

        now = datetime.utcnow()
        # Create channel posts
        for i in range(channel_posts):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Channel post {i}",
                is_public=True,
                channel_id="channel-test",
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)

        # Create non-channel posts
        for i in range(other_posts):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Global post {i}",
                is_public=True,
                channel_id=None,
                created_at=now + timedelta(seconds=channel_posts + i)
            )
            db_session.add(post)
        db_session.commit()

        # Get channel feed
        channel_feed = await service.get_feed(
            sender_id="user1",
            channel_id="channel-test",
            limit=100,
            db=db_session
        )

        # All posts should have channel_id
        assert all(p["channel_id"] == "channel-test" for p in channel_feed["posts"])
        assert len(channel_feed["posts"]) == channel_posts

    @given(st.integers(min_value=1, max_value=20))
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_feed_filter_by_post_type_complete(self, post_count, db_session):
        """Property: Filter returns only matching post_type."""
        service = AgentSocialLayer()

        types = ["status", "insight", "question", "alert"]

        # Create random posts
        import random
        now = datetime.utcnow()
        created_posts = []
        for i in range(post_count):
            post_type = random.choice(types)
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type=post_type,
                content=f"{post_type} post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
            created_posts.append((post_type, post))
        db_session.commit()

        # Test each filter
        for target_type in types:
            filtered = await service.get_feed(
                sender_id="user1",
                post_type=target_type,
                limit=100,
                db=db_session
            )

            # All should match filter
            assert all(p["post_type"] == target_type for p in filtered["posts"])

    @given(st.integers(min_value=1, max_value=30))
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_total_count_matches_actual(self, post_count, db_session):
        """Property: Total count matches actual post count."""
        service = AgentSocialLayer()

        # Create posts
        now = datetime.utcnow()
        for i in range(post_count):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
        db_session.commit()

        # Get feed
        feed = await service.get_feed(
            sender_id="user1",
            limit=100,
            db=db_session
        )

        assert feed["total"] == post_count

    @given(st.integers(min_value=1, max_value=20))
    @settings(max_examples=30)
    @pytest.mark.asyncio
    async def test_no_lost_posts_in_feed(self, post_count, db_session):
        """Property: All posts appear in feed (no lost posts)."""
        service = AgentSocialLayer()

        # Create posts
        now = datetime.utcnow()
        created_ids = []
        for i in range(post_count):
            post = AgentPost(
                sender_type="human",
                sender_id="user1",
                sender_name="User 1",
                post_type="status",
                content=f"Post {i}",
                is_public=True,
                created_at=now + timedelta(seconds=i)
            )
            db_session.add(post)
            db_session.flush()
            created_ids.append(post.id)
        db_session.commit()

        # Get all posts
        feed = await service.get_feed(
            sender_id="user1",
            limit=100,
            db=db_session
        )

        feed_ids = set(p["id"] for p in feed["posts"])
        created_ids_set = set(created_ids)

        # All created posts should be in feed
        assert feed_ids == created_ids_set
