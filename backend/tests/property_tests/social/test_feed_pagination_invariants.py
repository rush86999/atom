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
from datetime import datetime, timedelta
from hypothesis import strategies as st, given, settings, example, HealthCheck
from sqlalchemy.orm import Session

from core.agent_social_layer import AgentSocialLayer
from core.models import AgentPost, Channel, AgentRegistry
from tests.factories import AgentFactory


class TestFeedPaginationInvariants:
    """Property tests for feed pagination."""

    @given(
        num_posts=st.integers(min_value=10, max_value=200),
        page_size=st.integers(min_value=10, max_value=50)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_pagination_no_duplicates(self, db_session, num_posts, page_size):
        """
        Pagination no duplicates invariant.

        Property: Paginating through feed never returns duplicate posts,
        regardless of number of posts or page size.
        """
        import uuid
        test_id = str(uuid.uuid4())[:8]

        # Create test agent with unique ID
        agent = AgentRegistry(
            id=f"test-agent-{test_id}",
            name=f"TestAgent_{num_posts}_{page_size}_{test_id}",
            status="INTERN",
            class_name="TestAgent",
            module_path="tests.property_tests.social.test_feed_pagination_invariants",
            category="testing"
        )
        db_session.add(agent)

        # Create channel with unique ID
        channel = Channel(
            id=f"test-channel-{test_id}",
            name=f"test-{test_id}",
            display_name="Test",
            channel_type="general",
            is_public=True,
            created_by=agent.id  # Required field
        )
        db_session.add(channel)
        db_session.commit()

        try:
            # Create posts
            now = datetime.utcnow()
            created_posts = []
            for i in range(num_posts):
                post = AgentPost(
                    sender_type="agent",
                    sender_id=agent.id,
                    sender_name=agent.name,
                    sender_maturity=agent.status,
                    sender_category=agent.category,
                    post_type="status",
                    content=f"Post {i}",
                    channel_id=channel.id,
                    channel_name=channel.name,
                    is_public=True,
                    created_at=now + timedelta(milliseconds=i*10)
                )
                db_session.add(post)
                created_posts.append(post)
            db_session.commit()

            # Paginate through feed
            feed_service = AgentSocialLayer()
            all_post_ids = set()
            cursor = None

            while True:
                page_data = await feed_service.get_feed_cursor(
                    sender_id=agent.id,
                    cursor=cursor,
                    limit=page_size,
                    channel_id=channel.id,
                    db=db_session
                )

                page = page_data["posts"]
                if not page:
                    break

                # Check for duplicates
                page_ids = {p["id"] for p in page}
                duplicates = all_post_ids & page_ids

                # INVARIANT: No duplicates across pages
                assert len(duplicates) == 0, f"Found {len(duplicates)} duplicates: {duplicates}"

                all_post_ids.update(page_ids)

                if not page_data["has_more"]:
                    break

                cursor = page_data["next_cursor"]

            # INVARIANT: All posts retrieved exactly once
            assert len(all_post_ids) == num_posts, f"Expected {num_posts} posts, got {len(all_post_ids)}"
        finally:
            # Cleanup: Delete all created posts by this test run
            for post in created_posts:
                if post.id:
                    db_session.query(AgentPost).filter(AgentPost.id == post.id).delete(synchronize_session=False)
            # Delete channel and agent
            db_session.query(Channel).filter(Channel.id == channel.id).delete(synchronize_session=False)
            db_session.query(AgentRegistry).filter(AgentRegistry.id == agent.id).delete(synchronize_session=False)
            db_session.commit()


class TestChronologicalOrderInvariant:
    """Property tests for chronological ordering."""

    @given(
        num_posts=st.integers(min_value=5, max_value=100)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_feed_chronological_order(self, db_session, num_posts):
        """
        Chronological order invariant.

        Property: Feed is always in chronological order (newest first),
        regardless of number of posts.
        """
        import uuid
        test_id = str(uuid.uuid4())[:8]

        # Create test agent with unique ID
        agent = AgentRegistry(
            id=f"test-agent-{test_id}",
            name=f"TestAgent_{num_posts}_{test_id}",
            status="INTERN",
            class_name="TestAgent",
            module_path="tests.property_tests.social.test_feed_pagination_invariants",
            category="testing"
        )
        db_session.add(agent)

        # Create channel with unique ID
        channel = Channel(
            id=f"test-channel-{test_id}",
            name=f"test-{test_id}",
            display_name="Test",
            channel_type="general",
            is_public=True,
            created_by=agent.id  # Required field
        )
        db_session.add(channel)
        db_session.commit()

        try:
            # Create posts with varying timestamps
            now = datetime.utcnow()
            created_posts = []
            for i in range(num_posts):
                post = AgentPost(
                    sender_type="agent",
                    sender_id=agent.id,
                    sender_name=agent.name,
                    sender_maturity=agent.status,
                    sender_category=agent.category,
                    post_type="status",
                    content=f"Post {i}",
                    channel_id=channel.id,
                    channel_name=channel.name,
                    is_public=True,
                    created_at=now + timedelta(milliseconds=i*10)
                )
                db_session.add(post)
                created_posts.append(post)
            db_session.commit()

            # Generate feed
            feed_service = AgentSocialLayer()
            feed = await feed_service.get_feed(
                sender_id=agent.id,
                channel_id=channel.id,
                limit=200,
                db=db_session
            )

            # INVARIANT: Timestamps are decreasing (newest first)
            for i in range(len(feed["posts"]) - 1):
                current_time = datetime.fromisoformat(feed["posts"][i]["created_at"])
                next_time = datetime.fromisoformat(feed["posts"][i+1]["created_at"])
                assert current_time >= next_time, \
                    f"Post {i} ({current_time}) should be >= post {i+1} ({next_time})"
        finally:
            # Cleanup
            for post in created_posts:
                if post.id:
                    db_session.query(AgentPost).filter(AgentPost.id == post.id).delete()
            db_session.query(Channel).filter(Channel.id == channel.id).delete()
            db_session.query(AgentRegistry).filter(AgentRegistry.id == agent.id).delete()
            db_session.commit()


class TestFIFOMessageOrderingInvariant:
    """Property tests for FIFO message ordering."""

    @given(
        num_messages=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_fifo_message_ordering(self, db_session, num_messages):
        """
        FIFO message ordering invariant.

        Property: Messages are delivered in the order they were sent
        (reverse chronological when retrieved).
        """
        import uuid
        test_id = str(uuid.uuid4())[:8]

        # Create test agent with unique ID
        agent = AgentRegistry(
            id=f"test-agent-{test_id}",
            name=f"TestAgent_{num_messages}_{test_id}",
            status="INTERN",
            class_name="TestAgent",
            module_path="tests.property_tests.social.test_feed_pagination_invariants",
            category="testing"
        )
        db_session.add(agent)

        # Create channel with unique ID
        channel = Channel(
            id=f"test-channel-{test_id}",
            name=f"test-{test_id}",
            display_name="Test",
            channel_type="general",
            is_public=True,
            created_by=agent.id  # Required field
        )
        db_session.add(channel)
        db_session.commit()

        try:
            # Send messages in order
            feed_service = AgentSocialLayer()
            sent_order = []
            now = datetime.utcnow()

            for i in range(num_messages):
                message = f"Message {i}"
                await feed_service.create_post(
                    sender_type="agent",
                    sender_id=agent.id,
                    sender_name=agent.name,
                    post_type="status",
                    content=message,
                    sender_maturity=agent.status,
                    sender_category=agent.category,
                    channel_id=channel.id,
                    channel_name=channel.name,
                    db=db_session
                )
                sent_order.append(message)

            # Retrieve messages
            feed = await feed_service.get_feed(
                sender_id=agent.id,
                channel_id=channel.id,
                limit=200,
                db=db_session
            )

            # Extract message contents (should be reverse chronological)
            received_order = [m["content"] for m in feed["posts"]]

            # INVARIANT: Received order is reverse of sent order (newest first)
            assert received_order == list(reversed(sent_order)), \
                f"Order mismatch: sent {sent_order[:5]}..., got {received_order[:5]}..."
        finally:
            # Cleanup
            db_session.query(AgentPost).filter(AgentPost.channel_id == channel.id).delete()
            db_session.query(Channel).filter(Channel.id == channel.id).delete()
            db_session.query(AgentRegistry).filter(AgentRegistry.id == agent.id).delete()
            db_session.commit()


class TestChannelIsolationInvariant:
    """Property tests for channel isolation."""

    @given(
        num_channels=st.integers(min_value=2, max_value=10),
        num_posts=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_channel_isolation(self, db_session, num_channels, num_posts):
        """
        Channel isolation invariant.

        Property: Posts in one channel never appear in another channel's feed.
        """
        import uuid
        test_id = str(uuid.uuid4())[:8]

        # Create test agent with unique ID
        agent = AgentRegistry(
            id=f"test-agent-{test_id}",
            name=f"TestAgent_{num_channels}_{num_posts}_{test_id}",
            status="INTERN",
            class_name="TestAgent",
            module_path="tests.property_tests.social.test_feed_pagination_invariants",
            category="testing"
        )
        db_session.add(agent)

        # Create channels with unique IDs
        channels = []
        for i in range(num_channels):
            channel = Channel(
                id=f"channel-{i}-{test_id}",
                name=f"channel-{i}-{test_id}",
                display_name=f"Channel {i}",
                channel_type="general",
                is_public=True,
                created_by=agent.id  # Required field
            )
            channels.append(channel)
            db_session.add(channel)
        db_session.commit()

        try:
            # Create posts in different channels
            feed_service = AgentSocialLayer()
            now = datetime.utcnow()

            for i in range(num_posts):
                channel_idx = i % num_channels
                await feed_service.create_post(
                    sender_type="agent",
                    sender_id=agent.id,
                    sender_name=agent.name,
                    post_type="status",
                    content=f"Post {i} in channel {channel_idx}",
                    sender_maturity=agent.status,
                    sender_category=agent.category,
                    channel_id=channels[channel_idx].id,
                    channel_name=channels[channel_idx].name,
                    db=db_session
                )

            # Verify channel isolation
            for i, channel in enumerate(channels):
                feed = await feed_service.get_feed(
                    sender_id=agent.id,
                    channel_id=channel.id,
                    limit=100,
                    db=db_session
                )

                # INVARIANT: All posts belong to this channel
                for post in feed["posts"]:
                    assert post["channel_id"] == channel.id, \
                        f"Post {post['id']} in wrong channel: {post['channel_id']} != {channel.id}"

                    # Verify content matches channel
                    expected_channel_idx = int(post["content"].split(" in channel ")[1])
                    assert expected_channel_idx == i, \
                        f"Post content claims channel {expected_channel_idx}, but feed is for channel {i}"
        finally:
            # Cleanup
            for channel in channels:
                db_session.query(AgentPost).filter(AgentPost.channel_id == channel.id).delete()
                db_session.query(Channel).filter(Channel.id == channel.id).delete()
            db_session.query(AgentRegistry).filter(AgentRegistry.id == agent.id).delete()
            db_session.commit()


class TestReplyCountMonotonicInvariant:
    """Property tests for reply count monotonicity."""

    @given(
        num_replies=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_reply_count_monotonic_increase(self, db_session, num_replies):
        """
        Reply count monotonic invariant.

        Property: Reply count never decreases, only increases or stays same.
        """
        import uuid
        test_id = str(uuid.uuid4())[:8]

        # Create test agent with unique ID
        agent = AgentRegistry(
            id=f"test-agent-{test_id}",
            name=f"TestAgent_{num_replies}_{test_id}",
            status="INTERN",
            class_name="TestAgent",
            module_path="tests.property_tests.social.test_feed_pagination_invariants",
            category="testing"
        )
        db_session.add(agent)

        # Create channel with unique ID
        channel = Channel(
            id=f"test-channel-{test_id}",
            name=f"test-{test_id}",
            display_name="Test",
            channel_type="general",
            is_public=True,
            created_by=agent.id  # Required field
        )
        db_session.add(channel)
        db_session.commit()

        try:
            # Create parent post
            now = datetime.utcnow()
            parent = AgentPost(
                sender_type="agent",
                sender_id=agent.id,
                sender_name=agent.name,
                sender_maturity=agent.status,
                sender_category=agent.category,
                post_type="question",
                content="Parent post",
                channel_id=channel.id,
                channel_name=channel.name,
                is_public=True,
                reply_count=0,
                created_at=now
            )
            db_session.add(parent)
            db_session.commit()

            # Track reply counts over time
            feed_service = AgentSocialLayer()
            previous_count = 0
            created_replies = []

            # Add replies one by one
            for i in range(num_replies):
                reply = await feed_service.add_reply(
                    post_id=parent.id,
                    sender_type="agent",
                    sender_id=agent.id,
                    sender_name=agent.name,
                    content=f"Reply {i}",
                    sender_maturity=agent.status,
                    sender_category=agent.category,
                    db=db_session
                )
                created_replies.append(reply["id"])

                # Refresh parent post
                db_session.refresh(parent)
                current_count = parent.reply_count

                # INVARIANT: Reply count never decreases
                assert current_count >= previous_count, \
                    f"Reply count decreased from {previous_count} to {current_count}"

                # INVARIANT: Reply count increases by exactly 1
                assert current_count == previous_count + 1, \
                    f"Reply count should increase by 1, but went from {previous_count} to {current_count}"

                previous_count = current_count

            # Final count should match number of replies
            assert parent.reply_count == num_replies, \
                f"Expected {num_replies} replies, got {parent.reply_count}"
        finally:
            # Cleanup
            if created_replies:
                db_session.query(AgentPost).filter(AgentPost.id.in_(created_replies)).delete()
            if parent.id:
                db_session.query(AgentPost).filter(AgentPost.id == parent.id).delete()
            db_session.query(Channel).filter(Channel.id == channel.id).delete()
            db_session.query(AgentRegistry).filter(AgentRegistry.id == agent.id).delete()
            db_session.commit()


class TestFeedFilteringInvariants:
    """Property tests for feed filtering."""

    @given(
        num_posts=st.integers(min_value=20, max_value=100),
        filter_post_type=st.sampled_from(["status", "insight", "question", "alert"])
    )
    @settings(max_examples=40, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_feed_filtering_by_type_matches_all(self, db_session, num_posts, filter_post_type):
        """
        Feed filtering invariant.

        Property: When filtering by post type, all returned posts match that type.
        """
        import uuid
        test_id = str(uuid.uuid4())[:8]

        # Create test agent with unique ID
        agent = AgentRegistry(
            id=f"test-agent-{test_id}",
            name=f"TestAgent_{num_posts}_{filter_post_type}_{test_id}",
            status="INTERN",
            class_name="TestAgent",
            module_path="tests.property_tests.social.test_feed_pagination_invariants",
            category="testing"
        )
        db_session.add(agent)

        # Create channel with unique ID
        channel = Channel(
            id=f"test-channel-{test_id}",
            name=f"test-{test_id}",
            display_name="Test",
            channel_type="general",
            is_public=True,
            created_by=agent.id  # Required field
        )
        db_session.add(channel)
        db_session.commit()

        try:
            # Create posts with different types
            post_types = ["status", "insight", "question", "alert"]
            feed_service = AgentSocialLayer()
            now = datetime.utcnow()

            for i in range(num_posts):
                post_type = post_types[i % len(post_types)]
                await feed_service.create_post(
                    sender_type="agent",
                    sender_id=agent.id,
                    sender_name=agent.name,
                    post_type=post_type,
                    content=f"{post_type} post {i}",
                    sender_maturity=agent.status,
                    sender_category=agent.category,
                    channel_id=channel.id,
                    channel_name=channel.name,
                    db=db_session
                )

            # Filter by post type
            feed = await feed_service.get_feed(
                sender_id=agent.id,
                channel_id=channel.id,
                post_type=filter_post_type,
                limit=200,
                db=db_session
            )

            # INVARIANT: All filtered posts match the filter type
            for post in feed["posts"]:
                assert post["post_type"] == filter_post_type, \
                    f"Post type mismatch: expected {filter_post_type}, got {post['post_type']}"
        finally:
            # Cleanup
            db_session.query(AgentPost).filter(AgentPost.channel_id == channel.id).delete()
            db_session.query(Channel).filter(Channel.id == channel.id).delete()
            db_session.query(AgentRegistry).filter(AgentRegistry.id == agent.id).delete()
            db_session.commit()
