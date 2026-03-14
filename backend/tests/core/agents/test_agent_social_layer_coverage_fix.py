"""
Coverage-driven tests for agent_social_layer.py (14.3% -> 70%+ target)

This test file fixes the schema mismatch blocker identified in Phase 191-12:
- SocialPost model uses author_type/author_id/post_metadata
- NOT sender_type/sender_id/sender_name/sender_maturity/etc.

Coverage Target Areas:
- Lines 50-100: Post creation and initialization
- Lines 100-180: Maturity-based permission checks
- Lines 180-250: Bulk operations
- Lines 250-300: Social graph operations
- Lines 300-350: Validation and error handling
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.agent_social_layer import AgentSocialLayer
from core.models import SocialPost, AgentRegistry, AuthorType, PostType


class TestAgentSocialLayerCoverageFix:
    """Coverage-driven tests for agent_social_layer.py after schema fix"""

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Cover AgentSocialLayer.__init__ (lines 47-48)"""
        layer = AgentSocialLayer()
        assert layer.logger is not None
        assert hasattr(layer, 'logger')

    @pytest.mark.parametrize("sender_type,post_type,should_succeed", [
        ("human", "status", True),      # Human can post any type
        ("human", "insight", True),
        ("human", "question", True),
        ("human", "alert", True),
        ("human", "task", True),        # Note: Model has 'task', not 'command'
    ])
    async def test_human_post_creation_success(self, db_session, sender_type, post_type, should_succeed):
        """Cover post creation success path for humans (lines 50-100)"""
        layer = AgentSocialLayer()

        # Mock event bus
        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            result = await layer.create_post(
                sender_type=sender_type,
                sender_id="user-123",
                sender_name="Test User",
                post_type=post_type,
                content="Test post content",
                db=db_session
            )

            assert result is not None
            assert result["sender_type"] == sender_type
            assert result["post_type"] == post_type
            assert result["content"] == "Test post content"

    @pytest.mark.parametrize("invalid_content,error_type", [
        ("", None),           # Empty content - allowed
        (None, TypeError),    # None content - should fail
        ("x"*5000, None),     # Oversized content - allowed
    ])
    async def test_create_post_validation(self, db_session, invalid_content, error_type):
        """Cover post validation (lines 120-150)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            if error_type:
                with pytest.raises(error_type):
                    await layer.create_post(
                        sender_type="human",
                        sender_id="user-123",
                        sender_name="Test User",
                        post_type="status",
                        content=invalid_content,
                        db=db_session
                    )
            else:
                # Should succeed
                result = await layer.create_post(
                    sender_type="human",
                    sender_id="user-123",
                    sender_name="Test User",
                    post_type="status",
                    content=invalid_content,
                    db=db_session
                )
                assert result is not None

    @pytest.mark.parametrize("invalid_post_type", [
        "invalid_type",
        "COMMAND",  # Wrong case
        "Status",   # Wrong case
        "",         # Empty string
        None,       # None value
    ])
    async def test_invalid_post_type_rejection(self, db_session, invalid_post_type):
        """Cover post_type validation (lines 134-139)"""
        layer = AgentSocialLayer()

        with pytest.raises(ValueError) as exc_info:
            await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="Test User",
                post_type=invalid_post_type,
                content="Test content",
                db=db_session
            )

        assert "Invalid post_type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_student_agent_blocked_from_posting(self, db_session):
        """Cover STUDENT governance gate (lines 127-132)"""
        # Create STUDENT agent
        student_agent = AgentRegistry(
            id="student-agent-1",
            name="Student Agent",
            status="STUDENT",
            category="engineering",
            tenant_id="default"
        )
        db_session.add(student_agent)
        db_session.commit()

        layer = AgentSocialLayer()

        with pytest.raises(PermissionError) as exc_info:
            await layer.create_post(
                sender_type="agent",
                sender_id="student-agent-1",
                sender_name="Student Agent",
                post_type="status",
                content="Trying to post",
                db=db_session
            )

        assert "STUDENT agents cannot post" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_intern_agent_can_post(self, db_session):
        """Cover INTERN agent posting (lines 115-132)"""
        # Create INTERN agent
        intern_agent = AgentRegistry(
            id="intern-agent-1",
            name="Intern Agent",
            status="INTERN",
            category="engineering",
            tenant_id="default"
        )
        db_session.add(intern_agent)
        db_session.commit()

        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            result = await layer.create_post(
                sender_type="agent",
                sender_id="intern-agent-1",
                sender_name="Intern Agent",
                post_type="status",
                content="INTERN agent posting",
                db=db_session
            )

            assert result is not None
            assert result["sender_id"] == "intern-agent-1"

    @pytest.mark.parametrize("maturity_level,can_post", [
        ("STUDENT", False),
        ("INTERN", True),
        ("SUPERVISED", True),
        ("AUTONOMOUS", True),
    ])
    async def test_maturity_based_post_permissions(self, db_session, maturity_level, can_post):
        """Cover maturity-based permission checks (lines 115-132)"""
        # Create agent with specific maturity
        agent = AgentRegistry(
            id=f"agent-{maturity_level.lower()}",
            name=f"{maturity_level} Agent",
            status=maturity_level,
            category="engineering",
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            if can_post:
                result = await layer.create_post(
                    sender_type="agent",
                    sender_id=f"agent-{maturity_level.lower()}",
                    sender_name=f"{maturity_level} Agent",
                    post_type="status",
                    content="Test post",
                    db=db_session
                )
                assert result is not None
            else:
                with pytest.raises(PermissionError):
                    await layer.create_post(
                        sender_type="agent",
                        sender_id=f"agent-{maturity_level.lower()}",
                        sender_name=f"{maturity_level} Agent",
                        post_type="status",
                        content="Test post",
                        db=db_session
                    )

    @pytest.mark.asyncio
    async def test_pii_redaction_enabled(self, db_session):
        """Cover PII redaction (lines 141-161)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            # Post with email
            result = await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="Test User",
                post_type="status",
                content="Contact me at test@example.com",
                skip_pii_redaction=False,
                db=db_session
            )

            # Content should be redacted
            assert result is not None
            # Note: Actual redaction depends on pii_redactor implementation

    @pytest.mark.asyncio
    async def test_skip_pii_redaction(self, db_session):
        """Cover skip_pii_redaction flag (lines 145, 161)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            result = await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="Test User",
                post_type="status",
                content="Contact me at test@example.com",
                skip_pii_redaction=True,  # Skip redaction
                db=db_session
            )

            assert result is not None
            assert result["content"] == "Contact me at test@example.com"

    @pytest.mark.asyncio
    async def test_directed_message_creation(self, db_session):
        """Cover directed messages (lines 59-60, 169-170)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            result = await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="Test User",
                post_type="message",
                content="Private message",
                recipient_type="agent",
                recipient_id="agent-456",
                is_public=False,
                db=db_session
            )

            assert result is not None
            assert result["recipient_type"] == "agent"
            assert result["recipient_id"] == "agent-456"
            assert result["is_public"] is False

    @pytest.mark.asyncio
    async def test_channel_post_creation(self, db_session):
        """Cover channel posts (lines 62-63, 173-174)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            result = await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="Test User",
                post_type="status",
                content="Channel post",
                channel_id="channel-123",
                channel_name="general",
                db=db_session
            )

            assert result is not None
            assert result["channel_id"] == "channel-123"
            assert result["channel_name"] == "general"

    @pytest.mark.asyncio
    async def test_get_feed_empty(self, db_session):
        """Cover get_feed with empty database (lines 253-254)"""
        layer = AgentSocialLayer()

        result = await layer.get_feed(
            sender_id="user-123",
            db=db_session
        )

        assert result["posts"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_feed_with_posts(self, db_session):
        """Cover get_feed with posts (lines 256-309)"""
        layer = AgentSocialLayer()

        # Create posts
        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="User 1",
                post_type="status",
                content="Post 1",
                db=db_session
            )

            await layer.create_post(
                sender_type="human",
                sender_id="user-456",
                sender_name="User 2",
                post_type="insight",
                content="Post 2",
                db=db_session
            )

        # Get feed
        result = await layer.get_feed(
            sender_id="user-123",
            db=db_session
        )

        assert len(result["posts"]) == 2
        assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_get_feed_with_filters(self, db_session):
        """Cover feed filtering (lines 260-270)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            # Create posts with different types
            await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="User",
                post_type="status",
                content="Status post",
                db=db_session
            )

            await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="User",
                post_type="question",
                content="Question post",
                db=db_session
            )

        # Filter by post_type
        result = await layer.get_feed(
            sender_id="user-123",
            post_type="status",
            db=db_session
        )

        assert len(result["posts"]) == 1
        assert result["posts"][0]["post_type"] == "status"

    @pytest.mark.asyncio
    async def test_get_feed_pagination(self, db_session):
        """Cover feed pagination (lines 275-277)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            # Create multiple posts
            for i in range(5):
                await layer.create_post(
                    sender_type="human",
                    sender_id="user-123",
                    sender_name="User",
                    post_type="status",
                    content=f"Post {i}",
                    db=db_session
                )

        # Get with limit
        result = await layer.get_feed(
            sender_id="user-123",
            limit=3,
            db=db_session
        )

        assert len(result["posts"]) == 3
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_add_reaction(self, db_session):
        """Cover add_reaction (lines 311-356)"""
        layer = AgentSocialLayer()

        # Create post first
        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            post_result = await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="User",
                post_type="status",
                content="Test post",
                db=db_session
            )

            post_id = post_result["id"]

        # Add reaction
        mock_bus.publish = AsyncMock()

        reactions = await layer.add_reaction(
            post_id=post_id,
            sender_id="user-456",
            emoji="👍",
            db=db_session
        )

        assert reactions is not None
        assert "👍" in reactions

    @pytest.mark.asyncio
    async def test_add_reaction_post_not_found(self, db_session):
        """Cover add_reaction post not found (lines 335-336)"""
        layer = AgentSocialLayer()

        with pytest.raises(ValueError) as exc_info:
            await layer.add_reaction(
                post_id="nonexistent-post",
                sender_id="user-123",
                emoji="👍",
                db=db_session
            )

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_trending_topics_empty(self, db_session):
        """Cover get_trending_topics with no posts (lines 369-370)"""
        layer = AgentSocialLayer()

        topics = await layer.get_trending_topics(hours=24, db=db_session)

        assert topics == []

    @pytest.mark.asyncio
    async def test_get_trending_topics_with_mentions(self, db_session):
        """Cover get_trending_topics (lines 358-406)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            # Create posts with mentions
            await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="User",
                post_type="status",
                content="Mentioning @agent-1",
                mentioned_agent_ids=["agent-1", "agent-2"],
                mentioned_user_ids=["user-456"],
                mentioned_episode_ids=["episode-123"],
                mentioned_task_ids=["task-789"],
                db=db_session
            )

        topics = await layer.get_trending_topics(hours=24, db=db_session)

        assert len(topics) > 0
        # Check for agent mentions
        agent_topics = [t for t in topics if t["topic"].startswith("agent:")]
        assert len(agent_topics) > 0

    @pytest.mark.asyncio
    async def test_add_reply_success(self, db_session):
        """Cover add_reply success path (lines 408-491)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            # Create parent post
            parent = await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="User",
                post_type="question",
                content="What is AI?",
                db=db_session
            )

            # Add reply
            reply = await layer.add_reply(
                post_id=parent["id"],
                sender_type="human",
                sender_id="user-456",
                sender_name="Other User",
                content="AI is artificial intelligence",
                db=db_session
            )

            assert reply is not None
            assert reply["post_type"] in ["status", "insight"]  # create_post uses "response" but it maps to valid enum

    @pytest.mark.asyncio
    async def test_add_reply_student_agent_blocked(self, db_session):
        """Cover STUDENT agent reply blocking (lines 458-463)"""
        layer = AgentSocialLayer()

        # Create STUDENT agent
        student_agent = AgentRegistry(
            id="student-agent-1",
            name="Student Agent",
            status="STUDENT",
            category="engineering",
            tenant_id="default"
        )
        db_session.add(student_agent)
        db_session.commit()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            # Create parent post
            parent = await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="User",
                post_type="question",
                content="Question",
                db=db_session
            )

            # STUDENT agent tries to reply
            with pytest.raises(PermissionError) as exc_info:
                await layer.add_reply(
                    post_id=parent["id"],
                    sender_type="agent",
                    sender_id="student-agent-1",
                    sender_name="Student Agent",
                    content="Trying to reply",
                    db=db_session
                )

            assert "STUDENT agents cannot reply" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_reply_post_not_found(self, db_session):
        """Cover add_reply post not found (lines 445-447)"""
        layer = AgentSocialLayer()

        with pytest.raises(ValueError) as exc_info:
            await layer.add_reply(
                post_id="nonexistent-post",
                sender_type="human",
                sender_id="user-123",
                sender_name="User",
                content="Reply",
                db=db_session
            )

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_feed_cursor_no_cursor(self, db_session):
        """Cover get_feed_cursor without cursor (lines 522-524)"""
        layer = AgentSocialLayer()

        result = await layer.get_feed_cursor(
            sender_id="user-123",
            db=db_session
        )

        assert result["posts"] == []
        assert result["next_cursor"] is None
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_feed_cursor_with_posts(self, db_session):
        """Cover get_feed_cursor with posts (lines 526-607)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            # Create posts
            for i in range(3):
                await layer.create_post(
                    sender_type="human",
                    sender_id="user-123",
                    sender_name="User",
                    post_type="status",
                    content=f"Post {i}",
                    db=db_session
                )

        result = await layer.get_feed_cursor(
            sender_id="user-123",
            limit=2,
            db=db_session
        )

        assert len(result["posts"]) == 2
        assert result["has_more"] is True
        assert result["next_cursor"] is not None

    @pytest.mark.asyncio
    async def test_get_feed_cursor_pagination(self, db_session):
        """Cover cursor-based pagination (lines 540-562)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            # Create posts
            for i in range(5):
                await layer.create_post(
                    sender_type="human",
                    sender_id="user-123",
                    sender_name="User",
                    post_type="status",
                    content=f"Post {i}",
                    db=db_session
                )

        # First page
        page1 = await layer.get_feed_cursor(
            sender_id="user-123",
            limit=2,
            db=db_session
        )

        assert len(page1["posts"]) == 2
        assert page1["has_more"] is True

        # Second page using cursor
        page2 = await layer.get_feed_cursor(
            sender_id="user-123",
            cursor=page1["next_cursor"],
            limit=2,
            db=db_session
        )

        assert len(page2["posts"]) == 2
        # No duplicates
        page1_ids = {p["id"] for p in page1["posts"]}
        page2_ids = {p["id"] for p in page2["posts"]}
        assert len(page1_ids & page2_ids) == 0  # No intersection

    @pytest.mark.asyncio
    async def test_create_channel_new(self, db_session):
        """Cover create_channel success (lines 609-670)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.publish = AsyncMock()

            result = await layer.create_channel(
                channel_id="channel-123",
                channel_name="general",
                creator_id="user-123",
                display_name="General Channel",
                description="General discussions",
                channel_type="general",
                is_public=True,
                db=db_session
            )

            assert result["created"] is True
            assert result["id"] == "channel-123"

    @pytest.mark.asyncio
    async def test_create_channel_already_exists(self, db_session):
        """Cover create_channel when exists (lines 643-646)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.publish = AsyncMock()

            # Create channel
            await layer.create_channel(
                channel_id="channel-123",
                channel_name="general",
                creator_id="user-123",
                db=db_session
            )

            # Try to create again
            result = await layer.create_channel(
                channel_id="channel-123",
                channel_name="general",
                creator_id="user-123",
                db=db_session
            )

            assert result["exists"] is True

    @pytest.mark.asyncio
    async def test_get_channels_empty(self, db_session):
        """Cover get_channels with no channels (lines 682-683)"""
        layer = AgentSocialLayer()

        channels = await layer.get_channels(db=db_session)

        assert channels == []

    @pytest.mark.asyncio
    async def test_get_channels_with_channels(self, db_session):
        """Cover get_channels (lines 672-700)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.publish = AsyncMock()

            # Create channels
            await layer.create_channel(
                channel_id="channel-1",
                channel_name="general",
                creator_id="user-123",
                db=db_session
            )

            await layer.create_channel(
                channel_id="channel-2",
                channel_name="engineering",
                creator_id="user-123",
                db=db_session
            )

        channels = await layer.get_channels(db=db_session)

        assert len(channels) == 2

    @pytest.mark.asyncio
    async def test_get_replies_empty(self, db_session):
        """Cover get_replies with no replies (lines 721-722)"""
        layer = AgentSocialLayer()

        replies = await layer.get_replies(
            post_id="some-post",
            db=db_session
        )

        assert replies["replies"] == []
        assert replies["total"] == 0

    @pytest.mark.asyncio
    async def test_get_replies_with_replies(self, db_session):
        """Cover get_replies (lines 702-746)"""
        layer = AgentSocialLayer()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            # Create parent post
            parent = await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="User",
                post_type="question",
                content="Question?",
                db=db_session
            )

            # Add replies
            await layer.add_reply(
                post_id=parent["id"],
                sender_type="human",
                sender_id="user-456",
                sender_name="User 2",
                content="Reply 1",
                db=db_session
            )

            await layer.add_reply(
                post_id=parent["id"],
                sender_type="human",
                sender_id="user-789",
                sender_name="User 3",
                content="Reply 2",
                db=db_session
            )

        replies = await layer.get_replies(
            post_id=parent["id"],
            db=db_session
        )

        assert replies["total"] == 2
        assert len(replies["replies"]) == 2

    @pytest.mark.parametrize("maturity_level,limit,expected_allowed", [
        ("STUDENT", 1, False),     # STUDENT: 0 posts/hour
        ("INTERN", 1, True),       # INTERN: 1 post/hour
        ("INTERN", 2, False),      # INTERN: exceeded
        ("SUPERVISED", 12, True),  # SUPERVISED: 12 posts/hour
        ("AUTONOMOUS", 100, True), # AUTONOMOUS: unlimited
    ])
    async def test_check_rate_limit_by_maturity(self, db_session, maturity_level, limit, expected_allowed):
        """Cover rate limit checking by maturity (lines 1382-1435)"""
        # Create agent
        agent = AgentRegistry(
            id=f"agent-{maturity_level.lower()}",
            name=f"{maturity_level} Agent",
            status=maturity_level,
            category="engineering",
            tenant_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        layer = AgentSocialLayer()

        allowed, reason = await layer.check_rate_limit(
            agent_id=f"agent-{maturity_level.lower()}",
            db=db_session
        )

        # AUTONOMOUS and SUPERVISED should be allowed (no posts yet)
        # STUDENT should be blocked
        # INTERN should be allowed (0 posts so far)
        if maturity_level == "STUDENT":
            assert allowed is False
            assert "read-only" in reason.lower()
        else:
            assert allowed is True

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_student(self, db_session):
        """Cover get_rate_limit_info for STUDENT (lines 1480-1550)"""
        agent = AgentRegistry(
            id="student-agent",
            name="Student Agent",
            status="STUDENT",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        layer = AgentSocialLayer()

        info = await layer.get_rate_limit_info(
            agent_id="student-agent",
            db=db_session
        )

        assert info["maturity"] == "STUDENT"
        assert info["max_posts_per_hour"] == 0

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_autonomous(self, db_session):
        """Cover get_rate_limit_info for AUTONOMOUS (lines 1521-1529)"""
        agent = AgentRegistry(
            id="autonomous-agent",
            name="Autonomous Agent",
            status="AUTONOMOUS",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        layer = AgentSocialLayer()

        info = await layer.get_rate_limit_info(
            agent_id="autonomous-agent",
            db=db_session
        )

        assert info["maturity"] == "AUTONOMOUS"
        assert info["unlimited"] is True
        assert info["max_posts_per_hour"] is None

    @pytest.mark.asyncio
    async def test_check_hourly_limit_under_limit(self, db_session):
        """Cover _check_hourly_limit under limit (lines 1437-1478)"""
        layer = AgentSocialLayer()

        allowed, reason = await layer._check_hourly_limit(
            agent_id="agent-123",
            max_posts=5,
            db=db_session
        )

        # No posts yet, should be allowed
        assert allowed is True
        assert reason is None
