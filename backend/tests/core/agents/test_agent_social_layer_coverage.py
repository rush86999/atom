"""
Coverage-driven tests for AgentSocialLayer (currently 0% -> target 80%+)

Focus areas from agent_social_layer.py:
- AgentSocialLayer.__init__ (lines 47-48)
- create_post() (lines 50-222)
- get_feed() (lines 224-309)
- add_reaction() (lines 311-356)
- get_trending_topics() (lines 358-406)
- add_reply() (lines 408-491)
- get_feed_cursor() (lines 493-607)
- create_channel() (lines 609-670)
- get_channels() (lines 672-700)
- get_replies() (lines 702-746)
- Rate limiting methods (lines 1382-1550)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, Mock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.agent_social_layer import AgentSocialLayer, agent_social_layer
from core.models import AgentRegistry, SocialPost


@pytest.fixture
def db_session():
    """Create a mock database session."""
    session = Mock(spec=Session)
    return session


@pytest.fixture
def social_layer():
    """Create AgentSocialLayer instance."""
    return AgentSocialLayer()


class TestAgentSocialLayerInit:
    """Test AgentSocialLayer initialization."""

    def test_init_default(self, social_layer):
        """Cover lines 47-48: Default initialization."""
        assert social_layer.logger is not None
        assert hasattr(social_layer, 'logger')


class TestCreatePost:
    """Test create_post method."""

    @pytest.mark.asyncio
    async def test_create_post_by_human(self, social_layer, db_session):
        """Cover lines 50-222: Human creating a public post."""
        # Mock database operations
        db_session.add = Mock()
        db_session.commit = Mock()
        db_session.refresh = Mock()

        # Mock agent_event_bus
        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            result = await social_layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="Test User",
                post_type="status",
                content="Test status message",
                db=db_session
            )

            assert result["sender_id"] == "user-123"
            assert result["sender_type"] == "human"
            assert result["post_type"] == "status"
            assert result["content"] == "Test status message"
            assert result["is_public"] is True

    @pytest.mark.asyncio
    async def test_create_post_by_agent_intern(self, social_layer, db_session):
        """Cover agent post creation with INTERN maturity."""
        # Mock agent query
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        mock_agent.category = "engineering"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        db_session.add = Mock()
        db_session.commit = Mock()
        db_session.refresh = Mock()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            result = await social_layer.create_post(
                sender_type="agent",
                sender_id="agent-123",
                sender_name="TestAgent",
                post_type="insight",
                content="Agent insight",
                db=db_session
            )

            assert result["sender_id"] == "agent-123"
            assert result["sender_maturity"] == "INTERN"

    @pytest.mark.asyncio
    async def test_create_post_student_blocked(self, social_layer, db_session):
        """Cover governance gate: STUDENT agents cannot post (lines 114-132)."""
        # Mock STUDENT agent
        mock_agent = Mock()
        mock_agent.status = "STUDENT"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        with pytest.raises(PermissionError) as exc_info:
            await social_layer.create_post(
                sender_type="agent",
                sender_id="student-agent",
                sender_name="StudentAgent",
                post_type="status",
                content="Trying to post",
                db=db_session
            )

        assert "STUDENT agents cannot post" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_post_invalid_type(self, social_layer, db_session):
        """Cover post type validation (lines 134-139)."""
        with pytest.raises(ValueError) as exc_info:
            await social_layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="User",
                post_type="invalid_type",
                content="Test",
                db=db_session
            )

        assert "Invalid post_type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_post_with_pii_redaction(self, social_layer, db_session):
        """Cover PII redaction (lines 141-161)."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        mock_agent.category = "engineering"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        db_session.add = Mock()
        db_session.commit = Mock()
        db_session.refresh = Mock()

        # Mock PII redactor
        with patch('core.agent_social_layer.get_pii_redactor') as mock_redactor:
            mock_result = Mock()
            mock_result.redacted_text = "My email is [REDACTED]"
            mock_result.has_secrets = True
            mock_result.redactions = [{"type": "EMAIL", "text": "user@example.com"}]
            mock_redactor.return_value.redact.return_value = mock_result

            with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
                mock_bus.broadcast_post = AsyncMock()

                result = await social_layer.create_post(
                    sender_type="agent",
                    sender_id="agent-123",
                    sender_name="Agent",
                    post_type="status",
                    content="My email is user@example.com",
                    db=db_session
                )

                # Should redact the email
                assert "[REDACTED]" in result["content"]

    @pytest.mark.asyncio
    async def test_create_post_with_mentions(self, social_layer, db_session):
        """Cover post with mentions (lines 163-183)."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        db_session.add = Mock()
        db_session.commit = Mock()
        db_session.refresh = Mock()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            result = await social_layer.create_post(
                sender_type="agent",
                sender_id="agent-123",
                sender_name="Agent",
                post_type="question",
                content="Hey @agent-456, can you help?",
                mentioned_agent_ids=["agent-456"],
                mentioned_user_ids=["user-789"],
                db=db_session
            )

            assert result["mentioned_agent_ids"] == ["agent-456"]
            assert result["mentioned_user_ids"] == ["user-789"]

    @pytest.mark.asyncio
    async def test_create_directed_message(self, social_layer, db_session):
        """Cover directed messages (lines 94-95, 171-172)."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        db_session.add = Mock()
        db_session.commit = Mock()
        db_session.refresh = Mock()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            result = await social_layer.create_post(
                sender_type="agent",
                sender_id="agent-1",
                sender_name="Agent1",
                post_type="response",
                content="Private message",
                recipient_type="agent",
                recipient_id="agent-2",
                is_public=False,
                db=db_session
            )

            assert result["is_public"] is False
            assert result["recipient_id"] == "agent-2"

    @pytest.mark.asyncio
    async def test_create_post_with_channel(self, social_layer, db_session):
        """Cover channel-specific posts (lines 96-97, 173-174)."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        db_session.add = Mock()
        db_session.commit = Mock()
        db_session.refresh = Mock()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.broadcast_post = AsyncMock()

            result = await social_layer.create_post(
                sender_type="agent",
                sender_id="agent-1",
                sender_name="Agent",
                post_type="status",
                content="Working on project",
                channel_id="channel-123",
                channel_name="Project Discussion",
                db=db_session
            )

            assert result["channel_id"] == "channel-123"
            assert result["channel_name"] == "Project Discussion"


class TestGetFeed:
    """Test get_feed method."""

    @pytest.mark.asyncio
    async def test_get_feed_empty(self, social_layer, db_session):
        """Cover lines 224-309: Get empty feed."""
        # Mock empty query result
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value.limit.return_value.all.return_value = []
        db_session.query.return_value = mock_query

        result = await social_layer.get_feed(
            sender_id="user-123",
            limit=50,
            offset=0,
            db=db_session
        )

        assert result["posts"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_feed_with_posts(self, social_layer, db_session):
        """Cover get feed with posts."""
        # Mock posts
        mock_post1 = Mock()
        mock_post1.id = "post-1"
        mock_post1.sender_type = "agent"
        mock_post1.sender_id = "agent-1"
        mock_post1.sender_name = "Agent"
        mock_post1.sender_maturity = "INTERN"
        mock_post1.sender_category = "engineering"
        mock_post1.recipient_type = None
        mock_post1.recipient_id = None
        mock_post1.is_public = True
        mock_post1.channel_id = None
        mock_post1.channel_name = None
        mock_post1.post_type = "status"
        mock_post1.content = "Test post"
        mock_post1.mentioned_agent_ids = []
        mock_post1.mentioned_user_ids = []
        mock_post1.mentioned_episode_ids = []
        mock_post1.mentioned_task_ids = []
        mock_post1.reactions = {}
        mock_post1.reply_count = 0
        mock_post1.read_at = None
        mock_post1.created_at = datetime.utcnow()

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_post1]
        db_session.query.return_value = mock_query

        result = await social_layer.get_feed(
            sender_id="user-123",
            limit=50,
            db=db_session
        )

        assert len(result["posts"]) == 1
        assert result["posts"][0]["id"] == "post-1"

    @pytest.mark.asyncio
    async def test_get_feed_with_filters(self, social_layer, db_session):
        """Cover feed filtering (lines 260-270)."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        db_session.query.return_value = mock_query

        # Apply multiple filters
        await social_layer.get_feed(
            sender_id="user-123",
            post_type="status",
            sender_filter="agent-1",
            channel_id="channel-123",
            is_public=True,
            db=db_session
        )

        # Verify filter was called multiple times
        assert mock_query.filter.call_count >= 4


class TestAddReaction:
    """Test add_reaction method."""

    @pytest.mark.asyncio
    async def test_add_reaction(self, social_layer, db_session):
        """Cover lines 311-356: Add emoji reaction."""
        # Mock post
        mock_post = Mock()
        mock_post.reactions = {}
        db_session.query.return_value.filter.return_value.first.return_value = mock_post
        db_session.commit = Mock()
        db_session.refresh = Mock()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.publish = AsyncMock()

            result = await social_layer.add_reaction(
                post_id="post-123",
                sender_id="user-1",
                emoji="👍",
                db=db_session
            )

            assert result.get("👍") == 1
            assert db_session.commit.called

    @pytest.mark.asyncio
    async def test_add_reaction_increment(self, social_layer, db_session):
        """Cover incrementing existing reaction."""
        mock_post = Mock()
        mock_post.reactions = {"👍": 2}
        db_session.query.return_value.filter.return_value.first.return_value = mock_post
        db_session.commit = Mock()
        db_session.refresh = Mock()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.publish = AsyncMock()

            result = await social_layer.add_reaction(
                post_id="post-123",
                sender_id="user-1",
                emoji="👍",
                db=db_session
            )

            assert result.get("👍") == 3

    @pytest.mark.asyncio
    async def test_add_reaction_post_not_found(self, social_layer, db_session):
        """Cover reaction on non-existent post."""
        db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError):
            await social_layer.add_reaction(
                post_id="nonexistent",
                sender_id="user-1",
                emoji="👍",
                db=db_session
            )


class TestGetTrendingTopics:
    """Test get_trending_topics method."""

    @pytest.mark.asyncio
    async def test_get_trending_topics(self, social_layer, db_session):
        """Cover lines 358-406: Get trending topics."""
        # Mock recent posts with mentions
        mock_post1 = Mock()
        mock_post1.mentioned_agent_ids = ["agent-1", "agent-2"]
        mock_post1.mentioned_user_ids = ["user-1"]
        mock_post1.mentioned_episode_ids = ["ep-1"]
        mock_post1.mentioned_task_ids = []

        mock_post2 = Mock()
        mock_post2.mentioned_agent_ids = ["agent-1"]
        mock_post2.mentioned_user_ids = []
        mock_post2.mentioned_episode_ids = []
        mock_post2.mentioned_task_ids = ["task-1"]

        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_post1, mock_post2]
        db_session.query.return_value = mock_query

        result = await social_layer.get_trending_topics(hours=24, db=db_session)

        # Should return top 10 trending
        assert len(result) <= 10
        # Should be sorted by mentions (descending)
        if len(result) > 1:
            assert result[0]["mentions"] >= result[1]["mentions"]

    @pytest.mark.asyncio
    async def test_get_trending_topics_empty(self, social_layer, db_session):
        """Cover trending topics with no posts."""
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = []
        db_session.query.return_value = mock_query

        result = await social_layer.get_trending_topics(db=db_session)

        assert result == []


class TestAddReply:
    """Test add_reply method."""

    @pytest.mark.asyncio
    async def test_add_reply(self, social_layer, db_session):
        """Cover lines 408-491: Add reply to post."""
        # Mock parent post
        mock_parent = Mock()
        mock_parent.reply_count = 0
        db_session.query.return_value.filter.return_value.first.return_value = mock_parent
        db_session.add = Mock()
        db_session.commit = Mock()

        # Mock create_post
        social_layer.create_post = AsyncMock(return_value={
            "id": "reply-123",
            "content": "Reply content"
        })

        result = await social_layer.add_reply(
            post_id="post-123",
            sender_type="human",
            sender_id="user-1",
            sender_name="User",
            content="Reply content",
            db=db_session
        )

        assert result["content"] == "Reply content"

    @pytest.mark.asyncio
    async def test_add_reply_agent_blocked(self, social_layer, db_session):
        """Cover STUDENT agent blocked from replying (lines 449-463)."""
        mock_parent = Mock()
        db_session.query.return_value.filter.return_value.first.return_value = mock_parent

        # Mock STUDENT agent
        mock_agent = Mock()
        mock_agent.status = "STUDENT"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        with pytest.raises(PermissionError):
            await social_layer.add_reply(
                post_id="post-123",
                sender_type="agent",
                sender_id="student-agent",
                sender_name="Student",
                content="Cannot reply",
                db=db_session
            )

    @pytest.mark.asyncio
    async def test_add_reply_post_not_found(self, social_layer, db_session):
        """Cover reply to non-existent post."""
        db_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError):
            await social_layer.add_reply(
                post_id="nonexistent",
                sender_type="human",
                sender_id="user-1",
                sender_name="User",
                content="Reply",
                db=db_session
            )


class TestGetFeedCursor:
    """Test get_feed_cursor method."""

    @pytest.mark.asyncio
    async def test_get_feed_cursor_no_cursor(self, social_layer, db_session):
        """Cover lines 493-607: Cursor-based pagination without cursor."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = []
        db_session.query.return_value = mock_query

        result = await social_layer.get_feed_cursor(
            sender_id="user-1",
            cursor=None,
            limit=50,
            db=db_session
        )

        assert result["posts"] == []
        assert result["next_cursor"] is None
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_feed_cursor_with_cursor(self, social_layer, db_session):
        """Cover cursor-based pagination with cursor."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = []
        db_session.query.return_value = mock_query

        result = await social_layer.get_feed_cursor(
            sender_id="user-1",
            cursor="2026-03-14T10:00:00:post-123",
            limit=50,
            db=db_session
        )

        # Should apply cursor filter
        assert mock_query.filter.called

    @pytest.mark.asyncio
    async def test_get_feed_cursor_has_more(self, social_layer, db_session):
        """Cover has_more detection (lines 564-567)."""
        # Mock one extra post to trigger has_more
        mock_posts = [Mock() for _ in range(51)]  # 51 posts when limit is 50

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = mock_posts
        db_session.query.return_value = mock_query

        result = await social_layer.get_feed_cursor(
            sender_id="user-1",
            limit=50,
            db=db_session
        )

        # Should return only limit posts
        assert len(result["posts"]) == 50
        assert result["has_more"] is True


class TestCreateChannel:
    """Test create_channel method."""

    @pytest.mark.asyncio
    async def test_create_channel(self, social_layer, db_session):
        """Cover lines 609-670: Create new channel."""
        # Mock channel not existing
        db_session.query.return_value.filter.return_value.first.return_value = None
        db_session.add = Mock()
        db_session.commit = Mock()

        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.publish = AsyncMock()

            result = await social_layer.create_channel(
                channel_id="channel-123",
                channel_name="project-discussion",
                creator_id="user-1",
                display_name="Project Discussion",
                description="Discussion for project X",
                channel_type="project",
                is_public=True,
                db=db_session
            )

            assert result["id"] == "channel-123"
            assert result["created"] is True

    @pytest.mark.asyncio
    async def test_create_channel_already_exists(self, social_layer, db_session):
        """Cover creating channel that already exists."""
        # Mock existing channel
        mock_channel = Mock()
        mock_channel.id = "existing-channel"
        mock_channel.name = "existing"
        db_session.query.return_value.filter.return_value.first.return_value = mock_channel

        result = await social_layer.create_channel(
            channel_id="existing-channel",
            channel_name="existing",
            creator_id="user-1",
            db=db_session
        )

        assert result["exists"] is True


class TestGetChannels:
    """Test get_channels method."""

    @pytest.mark.asyncio
    async def test_get_channels(self, social_layer, db_session):
        """Cover lines 672-700: Get all channels."""
        # Mock channels
        mock_channel = Mock()
        mock_channel.id = "channel-1"
        mock_channel.name = "general"
        mock_channel.display_name = "General"
        mock_channel.description = "General discussion"
        mock_channel.channel_type = "general"
        mock_channel.is_public = True
        mock_channel.created_by = "system"
        mock_channel.created_at = datetime.utcnow()

        db_session.query.return_value.all.return_value = [mock_channel]

        result = await social_layer.get_channels(db=db_session)

        assert len(result) == 1
        assert result[0]["id"] == "channel-1"

    @pytest.mark.asyncio
    async def test_get_channels_empty(self, social_layer, db_session):
        """Cover get channels with no channels."""
        db_session.query.return_value.all.return_value = []

        result = await social_layer.get_channels(db=db_session)

        assert result == []


class TestGetReplies:
    """Test get_replies method."""

    @pytest.mark.asyncio
    async def test_get_replies(self, social_layer, db_session):
        """Cover lines 702-746: Get replies to post."""
        # Mock reply posts
        mock_reply = Mock()
        mock_reply.id = "reply-1"
        mock_reply.sender_type = "human"
        mock_reply.sender_id = "user-1"
        mock_reply.sender_name = "User"
        mock_reply.sender_maturity = None
        mock_reply.sender_category = None
        mock_reply.content = "Reply content"
        mock_reply.post_type = "response"
        mock_reply.created_at = datetime.utcnow()
        mock_reply.reactions = {}

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_reply]
        db_session.query.return_value = mock_query

        result = await social_layer.get_replies(
            post_id="post-123",
            limit=50,
            db=db_session
        )

        assert len(result["replies"]) == 1
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_get_replies_empty(self, social_layer, db_session):
        """Cover get replies with no replies."""
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db_session.query.return_value = mock_query

        result = await social_layer.get_replies(
            post_id="post-123",
            db=db_session
        )

        assert result["replies"] == []
        assert result["total"] == 0


class TestRateLimiting:
    """Test rate limiting methods."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_autonomous(self, social_layer, db_session):
        """Cover lines 1382-1435: AUTONOMOUS agents have no limit."""
        mock_agent = Mock()
        mock_agent.status = "AUTONOMOUS"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        allowed, reason = await social_layer.check_rate_limit(
            agent_id="agent-1",
            db=db_session
        )

        assert allowed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_check_rate_limit_student_blocked(self, social_layer, db_session):
        """Cover STUDENT agents blocked (lines 1420-1421)."""
        mock_agent = Mock()
        mock_agent.status = "STUDENT"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        allowed, reason = await social_layer.check_rate_limit(
            agent_id="student-agent",
            db=db_session
        )

        assert allowed is False
        assert "read-only" in reason.lower()

    @pytest.mark.asyncio
    async def test_check_rate_limit_intern(self, social_layer, db_session):
        """Cover INTERN limit: 1 post per hour (lines 1423-1424)."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        # No posts in last hour
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 0
        db_session.query.return_value = mock_query

        allowed, reason = await social_layer.check_rate_limit(
            agent_id="intern-agent",
            db=db_session
        )

        assert allowed is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_intern_exceeded(self, social_layer, db_session):
        """Cover INTERN limit exceeded."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        # Already posted 1 time in last hour
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 1
        db_session.query.return_value = mock_query

        allowed, reason = await social_layer.check_rate_limit(
            agent_id="intern-agent",
            db=db_session
        )

        assert allowed is False
        assert "rate limit" in reason.lower()

    @pytest.mark.asyncio
    async def test_check_rate_limit_supervised(self, social_layer, db_session):
        """Cover SUPERVISED limit: 12 posts per hour (lines 1426-1427)."""
        mock_agent = Mock()
        mock_agent.status = "SUPERVISED"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        # 5 posts in last hour (under limit of 12)
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 5
        db_session.query.return_value = mock_query

        allowed, reason = await social_layer.check_rate_limit(
            agent_id="supervised-agent",
            db=db_session
        )

        assert allowed is True

    @pytest.mark.asyncio
    async def test_get_rate_limit_info(self, social_layer, db_session):
        """Cover lines 1480-1550: Get rate limit information."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        # 0 posts in last hour
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 0
        db_session.query.return_value = mock_query

        result = await social_layer.get_rate_limit_info(
            agent_id="intern-agent",
            db=db_session
        )

        assert result["maturity"] == "INTERN"
        assert result["max_posts_per_hour"] == 1
        assert result["posts_last_hour"] == 0
        assert result["remaining_posts"] == 1

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_unlimited(self, social_layer, db_session):
        """Cover AUTONOMOUS unlimited (lines 1521-1529)."""
        mock_agent = Mock()
        mock_agent.status = "AUTONOMOUS"
        db_session.query.return_value.filter.return_value.first.return_value = mock_agent

        result = await social_layer.get_rate_limit_info(
            agent_id="autonomous-agent",
            db=db_session
        )

        assert result["unlimited"] is True
        assert result["max_posts_per_hour"] is None


class TestGlobalInstance:
    """Test global service instance."""

    def test_agent_social_layer_singleton(self):
        """Cover lines 1553-1554: Global service instance."""
        assert agent_social_layer is not None
        assert isinstance(agent_social_layer, AgentSocialLayer)
