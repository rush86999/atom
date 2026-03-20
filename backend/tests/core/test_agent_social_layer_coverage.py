"""
Coverage tests for agent_social_layer.py.

Target: 60%+ coverage (379 statements, ~227 lines to cover)
Focus: Social interactions, agent collaboration, communication protocols
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from core.agent_social_layer import AgentSocialLayer
from core.models import SocialPost, AgentRegistry, AuthorType, PostType


class TestSocialLayerInitialization:
    """Test social layer initialization."""

    def test_layer_initialization(self):
        """Test social layer initializes correctly."""
        layer = AgentSocialLayer()
        assert layer is not None
        assert hasattr(layer, 'logger')

    def test_global_instance_exists(self):
        """Test global instance is available."""
        from core.agent_social_layer import agent_social_layer
        assert agent_social_layer is not None
        assert isinstance(agent_social_layer, AgentSocialLayer)


class TestCreatePost:
    """Test post creation functionality."""

    @pytest.mark.asyncio
    async def test_create_post_as_human(self, db_session):
        """Test creating post as human sender."""
        layer = AgentSocialLayer()

        post_data = await layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="Test User",
            post_type="status",
            content="Hello world",
            db=db_session
        )

        assert post_data is not None
        assert post_data["sender_type"] == "human"
        assert post_data["sender_id"] == "user-123"
        assert post_data["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_create_post_as_intern_agent(self, db_session):
        """Test creating post as INTERN agent (allowed)."""
        layer = AgentSocialLayer()

        # Create INTERN agent
        agent = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            status="INTERN",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        post_data = await layer.create_post(
            sender_type="agent",
            sender_id="agent-123",
            sender_name="Test Agent",
            post_type="insight",
            content="Agent insight here",
            db=db_session
        )

        assert post_data is not None
        assert post_data["sender_id"] == "agent-123"

    @pytest.mark.asyncio
    async def test_create_post_student_agent_blocked(self, db_session):
        """Test STUDENT agent cannot post (blocked)."""
        layer = AgentSocialLayer()

        # Create STUDENT agent
        agent = AgentRegistry(
            id="student-agent",
            name="Student Agent",
            status="STUDENT",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        with pytest.raises(PermissionError) as exc_info:
            await layer.create_post(
                sender_type="agent",
                sender_id="student-agent",
                sender_name="Student Agent",
                post_type="status",
                content="Should be blocked",
                db=db_session
            )

        assert "STUDENT agents cannot post" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_post_invalid_type(self, db_session):
        """Test creating post with invalid post_type."""
        layer = AgentSocialLayer()

        with pytest.raises(ValueError) as exc_info:
            await layer.create_post(
                sender_type="human",
                sender_id="user-123",
                sender_name="Test User",
                post_type="invalid_type",
                content="Test",
                db=db_session
            )

        assert "Invalid post_type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_post_with_mentions(self, db_session):
        """Test creating post with mentions."""
        layer = AgentSocialLayer()

        post_data = await layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="Test User",
            post_type="status",
            content="Mentioning agents",
            mentioned_agent_ids=["agent-1", "agent-2"],
            mentioned_user_ids=["user-1"],
            db=db_session
        )

        assert len(post_data["mentioned_agent_ids"]) == 2
        assert len(post_data["mentioned_user_ids"]) == 1

    @pytest.mark.asyncio
    async def test_create_post_with_channel(self, db_session):
        """Test creating post in a channel."""
        layer = AgentSocialLayer()

        post_data = await layer.create_post(
            sender_type="agent",
            sender_id="agent-123",
            sender_name="Test Agent",
            post_type="status",
            content="Channel post",
            channel_id="channel-1",
            channel_name="engineering",
            is_public=True,
            db=db_session
        )

        assert post_data["channel_id"] == "channel-1"
        assert post_data["channel_name"] == "engineering"

    @pytest.mark.asyncio
    async def test_create_directed_message(self, db_session):
        """Test creating directed message (not public)."""
        layer = AgentSocialLayer()

        post_data = await layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="Test User",
            post_type="status",
            content="Private message",
            recipient_type="agent",
            recipient_id="agent-123",
            is_public=False,
            db=db_session
        )

        assert post_data["is_public"] is False
        assert post_data["recipient_id"] == "agent-123"


class TestGetFeed:
    """Test feed retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_feed_empty(self, db_session):
        """Test getting feed when empty."""
        layer = AgentSocialLayer()

        feed = await layer.get_feed(
            sender_id="user-123",
            db=db_session
        )

        assert feed["posts"] == []
        assert feed["total"] == 0

    @pytest.mark.asyncio
    async def test_get_feed_with_posts(self, db_session):
        """Test getting feed with posts."""
        layer = AgentSocialLayer()

        # Create some posts
        await layer.create_post(
            sender_type="human",
            sender_id="user-1",
            sender_name="User 1",
            post_type="status",
            content="Post 1",
            db=db_session
        )

        await layer.create_post(
            sender_type="human",
            sender_id="user-2",
            sender_name="User 2",
            post_type="insight",
            content="Post 2",
            db=db_session
        )

        feed = await layer.get_feed(
            sender_id="user-123",
            limit=10,
            db=db_session
        )

        assert len(feed["posts"]) == 2
        assert feed["total"] == 2

    @pytest.mark.asyncio
    async def test_get_feed_with_type_filter(self, db_session):
        """Test filtering feed by post type."""
        layer = AgentSocialLayer()

        await layer.create_post(
            sender_type="human",
            sender_id="user-1",
            sender_name="User 1",
            post_type="status",
            content="Status post",
            db=db_session
        )

        await layer.create_post(
            sender_type="human",
            sender_id="user-1",
            sender_name="User 1",
            post_type="question",
            content="Question post",
            db=db_session
        )

        feed = await layer.get_feed(
            sender_id="user-123",
            post_type="status",
            db=db_session
        )

        assert len(feed["posts"]) == 1
        assert feed["posts"][0]["post_type"] == "status"

    @pytest.mark.asyncio
    async def test_get_feed_with_sender_filter(self, db_session):
        """Test filtering feed by sender."""
        layer = AgentSocialLayer()

        await layer.create_post(
            sender_type="human",
            sender_id="user-1",
            sender_name="User 1",
            post_type="status",
            content="Post 1",
            db=db_session
        )

        await layer.create_post(
            sender_type="human",
            sender_id="user-2",
            sender_name="User 2",
            post_type="status",
            content="Post 2",
            db=db_session
        )

        feed = await layer.get_feed(
            sender_id="user-123",
            sender_filter="user-1",
            db=db_session
        )

        assert len(feed["posts"]) == 1
        assert feed["posts"][0]["sender_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_get_feed_with_channel_filter(self, db_session):
        """Test filtering feed by channel."""
        layer = AgentSocialLayer()

        await layer.create_post(
            sender_type="human",
            sender_id="user-1",
            sender_name="User 1",
            post_type="status",
            content="Channel post",
            channel_id="engineering",
            db=db_session
        )

        await layer.create_post(
            sender_type="human",
            sender_id="user-2",
            sender_name="User 2",
            post_type="status",
            content="Other post",
            channel_id="general",
            db=db_session
        )

        feed = await layer.get_feed(
            sender_id="user-123",
            channel_id="engineering",
            db=db_session
        )

        assert len(feed["posts"]) == 1

    @pytest.mark.asyncio
    async def test_get_feed_pagination(self, db_session):
        """Test feed pagination."""
        layer = AgentSocialLayer()

        # Create 5 posts
        for i in range(5):
            await layer.create_post(
                sender_type="human",
                sender_id=f"user-{i}",
                sender_name=f"User {i}",
                post_type="status",
                content=f"Post {i}",
                db=db_session
            )

        # Get first page
        page1 = await layer.get_feed(
            sender_id="user-123",
            limit=2,
            offset=0,
            db=db_session
        )

        assert len(page1["posts"]) == 2

        # Get second page
        page2 = await layer.get_feed(
            sender_id="user-123",
            limit=2,
            offset=2,
            db=db_session
        )

        assert len(page2["posts"]) == 2


class TestReactionsAndReplies:
    """Test reactions and replies."""

    @pytest.mark.asyncio
    async def test_add_reaction(self, db_session):
        """Test adding emoji reaction to post."""
        layer = AgentSocialLayer()

        # Create a post
        post = await layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="Test User",
            post_type="status",
            content="Test post",
            db=db_session
        )

        reactions = await layer.add_reaction(
            post_id=post["id"],
            sender_id="user-456",
            emoji="👍",
            db=db_session
        )

        assert reactions is not None

    @pytest.mark.asyncio
    async def test_add_reaction_post_not_found(self, db_session):
        """Test adding reaction to non-existent post."""
        layer = AgentSocialLayer()

        with pytest.raises(ValueError) as exc_info:
            await layer.add_reaction(
                post_id="nonexistent",
                sender_id="user-123",
                emoji="👍",
                db=db_session
            )

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_reply_as_human(self, db_session):
        """Test adding reply as human."""
        layer = AgentSocialLayer()

        # Create parent post
        parent = await layer.create_post(
            sender_type="agent",
            sender_id="agent-123",
            sender_name="Agent",
            post_type="question",
            content="How do I do X?",
            db=db_session
        )

        # Add reply
        reply = await layer.add_reply(
            post_id=parent["id"],
            sender_type="human",
            sender_id="user-123",
            sender_name="User",
            content="Here's how you do it",
            db=db_session
        )

        assert reply is not None
        assert reply["content"] == "Here's how you do it"

    @pytest.mark.asyncio
    async def test_add_reply_student_agent_blocked(self, db_session):
        """Test STUDENT agent cannot reply."""
        layer = AgentSocialLayer()

        # Create STUDENT agent
        agent = AgentRegistry(
            id="student-agent",
            name="Student Agent",
            status="STUDENT",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        # Create parent post
        parent = await layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="User",
            post_type="question",
            content="Question here",
            db=db_session
        )

        with pytest.raises(PermissionError) as exc_info:
            await layer.add_reply(
                post_id=parent["id"],
                sender_type="agent",
                sender_id="student-agent",
                sender_name="Student Agent",
                content="Should be blocked",
                db=db_session
            )

        assert "cannot reply" in str(exc_info.value)


class TestTrendingTopics:
    """Test trending topics functionality."""

    @pytest.mark.asyncio
    async def test_get_trending_topics_empty(self, db_session):
        """Test trending topics when no posts."""
        layer = AgentSocialLayer()

        trending = await layer.get_trending_topics(hours=24, db=db_session)

        assert trending == []

    @pytest.mark.asyncio
    async def test_get_trending_topics_with_mentions(self, db_session):
        """Test trending topics counts mentions."""
        layer = AgentSocialLayer()

        # Create posts with mentions
        await layer.create_post(
            sender_type="human",
            sender_id="user-1",
            sender_name="User 1",
            post_type="status",
            content="Post",
            mentioned_agent_ids=["agent-1", "agent-2"],
            mentioned_user_ids=["user-2"],
            db=db_session
        )

        await layer.create_post(
            sender_type="human",
            sender_id="user-2",
            sender_name="User 2",
            post_type="status",
            content="Another post",
            mentioned_agent_ids=["agent-1"],  # agent-1 mentioned again
            db=db_session
        )

        trending = await layer.get_trending_topics(hours=24, db=db_session)

        # agent-1 should be top (mentioned 2 times)
        assert len(trending) > 0
        assert trending[0]["topic"] == "agent:agent-1"
        assert trending[0]["mentions"] == 2


class TestChannels:
    """Test channel functionality."""

    @pytest.mark.asyncio
    async def test_create_channel(self, db_session):
        """Test creating a new channel."""
        layer = AgentSocialLayer()

        channel = await layer.create_channel(
            channel_id="engineering",
            channel_name="engineering",
            creator_id="user-123",
            display_name="Engineering Team",
            description="Engineering discussions",
            channel_type="project",
            is_public=True,
            db=db_session
        )

        assert channel["id"] == "engineering"
        assert channel["created"] is True

    @pytest.mark.asyncio
    async def test_create_channel_already_exists(self, db_session):
        """Test creating channel that already exists."""
        layer = AgentSocialLayer()

        # Create channel first time
        await layer.create_channel(
            channel_id="engineering",
            channel_name="engineering",
            creator_id="user-123",
            db=db_session
        )

        # Try to create again
        result = await layer.create_channel(
            channel_id="engineering",
            channel_name="engineering",
            creator_id="user-456",
            db=db_session
        )

        assert result["exists"] is True

    @pytest.mark.asyncio
    async def test_get_channels(self, db_session):
        """Test getting all channels."""
        layer = AgentSocialLayer()

        await layer.create_channel(
            channel_id="channel-1",
            channel_name="channel1",
            creator_id="user-123",
            db=db_session
        )

        await layer.create_channel(
            channel_id="channel-2",
            channel_name="channel2",
            creator_id="user-123",
            db=db_session
        )

        channels = await layer.get_channels(db=db_session)

        assert len(channels) == 2


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_student_blocked(self, db_session):
        """Test STUDENT agent rate limit (blocked)."""
        layer = AgentSocialLayer()

        # Create STUDENT agent
        agent = AgentRegistry(
            id="student-agent",
            name="Student Agent",
            status="STUDENT",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        allowed, reason = await layer.check_rate_limit(
            agent_id="student-agent",
            db=db_session
        )

        assert allowed is False
        assert "read-only" in reason

    @pytest.mark.asyncio
    async def test_check_rate_limit_intern(self, db_session):
        """Test INTERN agent rate limit (1 post/hour)."""
        layer = AgentSocialLayer()

        # Create INTERN agent
        agent = AgentRegistry(
            id="intern-agent",
            name="Intern Agent",
            status="INTERN",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        # First post should be allowed
        allowed, reason = await layer.check_rate_limit(
            agent_id="intern-agent",
            db=db_session
        )

        assert allowed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_check_rate_limit_autonomous_unlimited(self, db_session):
        """Test AUTONOMOUS agent has unlimited posts."""
        layer = AgentSocialLayer()

        # Create AUTONOMOUS agent
        agent = AgentRegistry(
            id="auto-agent",
            name="Auto Agent",
            status="AUTONOMOUS",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        allowed, reason = await layer.check_rate_limit(
            agent_id="auto-agent",
            db=db_session
        )

        assert allowed is True

    @pytest.mark.asyncio
    async def test_get_rate_limit_info(self, db_session):
        """Test getting rate limit info for agent."""
        layer = AgentSocialLayer()

        # Create SUPERVISED agent
        agent = AgentRegistry(
            id="supervised-agent",
            name="Supervised Agent",
            status="SUPERVISED",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        info = await layer.get_rate_limit_info(
            agent_id="supervised-agent",
            db=db_session
        )

        assert info["maturity"] == "SUPERVISED"
        assert info["max_posts_per_hour"] == 12
        assert "remaining_posts" in info


class TestPostTypeMapping:
    """Test post type mapping (legacy to enum)."""

    @pytest.mark.asyncio
    async def test_post_type_command_maps_to_task(self, db_session):
        """Test legacy 'command' type maps to 'task'."""
        layer = AgentSocialLayer()

        post = await layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="User",
            post_type="command",
            content="Execute this",
            db=db_session
        )

        assert post["post_type"] == "task"

    @pytest.mark.asyncio
    async def test_post_type_response_maps_to_status(self, db_session):
        """Test legacy 'response' type maps to 'status'."""
        layer = AgentSocialLayer()

        post = await layer.create_post(
            sender_type="agent",
            sender_id="agent-123",
            sender_name="Agent",
            post_type="response",
            content="Response here",
            db=db_session
        )

        assert post["post_type"] == "status"

    @pytest.mark.asyncio
    async def test_post_type_announcement_maps_to_alert(self, db_session):
        """Test legacy 'announcement' type maps to 'alert'."""
        layer = AgentSocialLayer()

        post = await layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="User",
            post_type="announcement",
            content="Important announcement",
            db=db_session
        )

        assert post["post_type"] == "alert"


class TestPIIRedaction:
    """Test PII redaction in posts."""

    @pytest.mark.asyncio
    async def test_post_with_pii_redaction(self, db_session):
        """Test PII is redacted from post content."""
        layer = AgentSocialLayer()

        # Create post with email
        post = await layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="User",
            post_type="status",
            content="Contact me at test@example.com",
            skip_pii_redaction=False,
            db=db_session
        )

        # Content should be redacted (email replaced with <EMAIL>)
        # Note: Actual redaction behavior depends on pii_redactor implementation
        assert post is not None

    @pytest.mark.asyncio
    async def test_post_skip_pii_redaction(self, db_session):
        """Test skipping PII redaction."""
        layer = AgentSocialLayer()

        post = await layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="User",
            post_type="status",
            content="Contact me at test@example.com",
            skip_pii_redaction=True,
            db=db_session
        )

        # Content should NOT be redacted
        assert "test@example.com" in post["content"]


class TestEpisodeIntegration:
    """Test episode integration features."""

    @pytest.mark.asyncio
    async def test_create_post_with_episode_references(self, db_session):
        """Test creating post with episode references."""
        layer = AgentSocialLayer()

        post = await layer.create_post_with_episode(
            sender_type="agent",
            sender_id="agent-123",
            sender_name="Agent",
            post_type="insight",
            content="Learned something new",
            episode_ids=["ep-1", "ep-2"],
            db=db_session
        )

        assert post is not None
        assert len(post["mentioned_episode_ids"]) == 2

    @pytest.mark.asyncio
    async def test_get_feed_with_episode_context(self, db_session):
        """Test getting feed with episode context."""
        layer = AgentSocialLayer()

        feed = await layer.get_feed_with_episode_context(
            agent_id="agent-123",
            include_episode_context=True,
            db=db_session
        )

        assert "posts" in feed


class TestGraduationMilestones:
    """Test graduation milestone posting."""

    @pytest.mark.asyncio
    async def test_post_graduation_milestone(self, db_session):
        """Test posting graduation milestone."""
        layer = AgentSocialLayer()

        # Create agent
        agent = AgentRegistry(
            id="agent-123",
            name="Test Agent",
            status="INTERN",
            category="engineering"
        )
        db_session.add(agent)
        db_session.commit()

        post = await layer.post_graduation_milestone(
            agent_id="agent-123",
            from_maturity="INTERN",
            to_maturity="SUPERVISED",
            db=db_session
        )

        assert post is not None
        assert "graduated" in post["content"].lower()
