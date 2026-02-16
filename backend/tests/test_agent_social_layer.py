"""
Tests for AgentSocialLayer - agent-to-agent and human-to-agent communication.

OpenClaw Integration Tests:
- INTERN+ maturity gate for agent posting
- STUDENT agents are read-only
- Human posting with no maturity restriction
- Full communication matrix (directed messages, channels)
- Post type validation (7 types)
- WebSocket broadcasting
- Feed pagination and filtering
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.agent_social_layer import agent_social_layer
from core.agent_communication import agent_event_bus
from core.models import AgentPost


class TestMaturityGate:
    """Test INTERN+ maturity requirement for agent posting."""

    @pytest.mark.asyncio
    async def test_intern_agent_can_post(self):
        """INTERN agents can create posts."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        mock_agent.category = "engineering"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        post = await agent_social_layer.create_post(
            sender_type="agent",
            sender_id="test-agent",
            sender_name="TestAgent",
            post_type="status",
            content="Working on feature X",
            db=mock_db
        )

        assert post["sender_maturity"] == "INTERN"
        assert post["content"] == "Working on feature X"

    @pytest.mark.asyncio
    async def test_student_agent_cannot_post(self):
        """STUDENT agents cannot create posts."""
        mock_agent = Mock()
        mock_agent.status = "STUDENT"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))

        with pytest.raises(PermissionError) as exc_info:
            await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="I'm a student",
                db=mock_db
            )

        assert "STUDENT agents cannot post" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_supervised_agent_can_post(self):
        """SUPERVISED agents can create posts."""
        mock_agent = Mock()
        mock_agent.status = "SUPERVISED"
        mock_agent.category = "support"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        post = await agent_social_layer.create_post(
            sender_type="agent",
            sender_id="test-agent",
            sender_name="TestAgent",
            post_type="insight",
            content="Discovered a bug",
            db=mock_db
        )

        assert post["post_type"] == "insight"

    @pytest.mark.asyncio
    async def test_autonomous_agent_can_post(self):
        """AUTONOMOUS agents can create posts."""
        mock_agent = Mock()
        mock_agent.status = "AUTONOMOUS"
        mock_agent.category = "sales"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        post = await agent_social_layer.create_post(
            sender_type="agent",
            sender_id="test-agent",
            sender_name="TestAgent",
            post_type="alert",
            content="Critical issue detected",
            db=mock_db
        )

        assert post["sender_maturity"] == "AUTONOMOUS"


class TestHumanPosting:
    """Test human posting with no maturity restriction."""

    @pytest.mark.asyncio
    async def test_human_can_post_without_maturity_check(self):
        """Humans can post without maturity gate."""
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        post = await agent_social_layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="Alice",
            post_type="announcement",
            content="Team meeting at 3pm",
            db=mock_db
        )

        assert post["sender_type"] == "human"
        assert post["post_type"] == "announcement"
        assert post["content"] == "Team meeting at 3pm"


class TestPostTypes:
    """Test post type validation."""

    @pytest.mark.asyncio
    async def test_valid_post_types(self):
        """Valid post types: status, insight, question, alert, command, response, announcement."""
        valid_types = ["status", "insight", "question", "alert", "command", "response", "announcement"]

        for post_type in valid_types:
            mock_agent = Mock()
            mock_agent.status = "INTERN"

            mock_db = Mock()
            mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()

            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type=post_type,
                content="Test content",
                db=mock_db
            )

            assert post["post_type"] == post_type

    @pytest.mark.asyncio
    async def test_invalid_post_type_rejected(self):
        """Invalid post types are rejected."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))

        with pytest.raises(ValueError) as exc_info:
            await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="invalid_type",
                content="Test",
                db=mock_db
            )

        assert "Invalid post_type" in str(exc_info.value)


class TestDirectedMessages:
    """Test directed messaging (1:1 communication)."""

    @pytest.mark.asyncio
    async def test_directed_message_to_agent(self):
        """Create directed message to agent."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        post = await agent_social_layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="Alice",
            post_type="command",
            content="Please analyze this data",
            recipient_type="agent",
            recipient_id="agent-456",
            is_public=False,
            db=mock_db
        )

        assert post["is_public"] is False
        assert post["recipient_type"] == "agent"
        assert post["recipient_id"] == "agent-456"

    @pytest.mark.asyncio
    async def test_directed_message_to_user(self):
        """Create directed message to user."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        post = await agent_social_layer.create_post(
            sender_type="agent",
            sender_id="agent-123",
            sender_name="TestAgent",
            post_type="response",
            content="Here is the analysis",
            recipient_type="human",
            recipient_id="user-789",
            is_public=False,
            db=mock_db
        )

        assert post["is_public"] is False
        assert post["recipient_type"] == "human"
        assert post["recipient_id"] == "user-789"


class TestChannelPosts:
    """Test channel-specific posts."""

    @pytest.mark.asyncio
    async def test_post_to_channel(self):
        """Create post in specific channel."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        post = await agent_social_layer.create_post(
            sender_type="agent",
            sender_id="agent-123",
            sender_name="TestAgent",
            post_type="status",
            content="Working on project X",
            channel_id="channel-456",
            channel_name="engineering",
            db=mock_db
        )

        assert post["channel_id"] == "channel-456"
        assert post["channel_name"] == "engineering"


class TestFeedPagination:
    """Test feed pagination and filtering."""

    @pytest.mark.asyncio
    async def test_feed_pagination(self):
        """Feed supports pagination with limit and offset."""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.count = Mock(return_value=100)
        
        # Mock the chaining properly
        mock_order_by = Mock(return_value=mock_query)
        mock_offset = Mock(return_value=mock_query)
        mock_limit = Mock(return_value=[])
        
        mock_query.order_by = Mock(return_value=mock_order_by)
        mock_order_by.offset = Mock(return_value=mock_offset)
        mock_offset.limit = Mock(return_value=mock_limit)
        mock_query.filter = Mock(return_value=mock_query)

        mock_db.query = Mock(return_value=mock_query)

        feed = await agent_social_layer.get_feed(
            sender_id="test-agent",
            limit=50,
            offset=0,
            db=mock_db
        )

        assert feed["total"] == 100
        assert feed["limit"] == 50
        assert feed["offset"] == 0

    @pytest.mark.asyncio
    async def test_feed_filtering_by_post_type(self):
        """Feed can be filtered by post type."""
        mock_db = Mock()
        mock_query = Mock()
        
        # Mock the chaining properly
        mock_order_by = Mock(return_value=mock_query)
        mock_offset = Mock(return_value=mock_query)
        mock_limit = Mock(return_value=[])
        
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.count = Mock(return_value=10)
        mock_query.order_by = Mock(return_value=mock_order_by)
        mock_order_by.offset = Mock(return_value=mock_offset)
        mock_offset.limit = Mock(return_value=mock_limit)

        mock_db.query = Mock(return_value=mock_query)

        feed = await agent_social_layer.get_feed(
            sender_id="test-agent",
            post_type="question",
            db=mock_db
        )

        assert feed["total"] == 10

    @pytest.mark.asyncio
    async def test_feed_filtering_by_channel(self):
        """Feed can be filtered by channel."""
        mock_db = Mock()
        mock_query = Mock()
        
        # Mock the chaining properly
        mock_order_by = Mock(return_value=mock_query)
        mock_offset = Mock(return_value=mock_query)
        mock_limit = Mock(return_value=[])
        
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.count = Mock(return_value=5)
        mock_query.order_by = Mock(return_value=mock_order_by)
        mock_order_by.offset = Mock(return_value=mock_offset)
        mock_offset.limit = Mock(return_value=mock_limit)

        mock_db.query = Mock(return_value=mock_query)

        feed = await agent_social_layer.get_feed(
            sender_id="test-agent",
            channel_id="channel-123",
            db=mock_db
        )

        assert feed["total"] == 5

    @pytest.mark.asyncio
    async def test_feed_filtering_public_private(self):
        """Feed can be filtered by public/private."""
        mock_db = Mock()
        mock_query = Mock()
        
        # Mock the chaining properly
        mock_order_by = Mock(return_value=mock_query)
        mock_offset = Mock(return_value=mock_query)
        mock_limit = Mock(return_value=[])
        
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.count = Mock(return_value=20)
        mock_query.order_by = Mock(return_value=mock_order_by)
        mock_order_by.offset = Mock(return_value=mock_offset)
        mock_offset.limit = Mock(return_value=mock_limit)

        mock_db.query = Mock(return_value=mock_query)

        feed = await agent_social_layer.get_feed(
            sender_id="test-agent",
            is_public=True,
            db=mock_db
        )

        assert feed["total"] == 20


class TestEventBusIntegration:
    """Test WebSocket broadcasting through event bus."""

    @pytest.mark.asyncio
    async def test_post_broadcasts_to_event_bus(self):
        """New posts are broadcast to event bus subscribers."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        mock_agent.category = "engineering"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock event bus broadcast
        with patch.object(agent_event_bus, 'broadcast_post', new=AsyncMock()) as mock_broadcast:
            await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Test post",
                db=mock_db
            )

            # Verify broadcast was called
            assert mock_broadcast.called
            call_args = mock_broadcast.call_args[0][0]
            assert call_args["sender_id"] == "test-agent"
            assert call_args["content"] == "Test post"


class TestReactions:
    """Test emoji reactions on posts."""

    @pytest.mark.asyncio
    async def test_add_reaction(self):
        """Agents and humans can add emoji reactions to posts."""
        mock_post = Mock()
        mock_post.reactions = {}

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(first=Mock(return_value=mock_post)))
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        reactions = await agent_social_layer.add_reaction(
            post_id="post-123",
            sender_id="agent-456",
            emoji="👍",
            db=mock_db
        )

        assert reactions["👍"] == 1

    @pytest.mark.asyncio
    async def test_multiple_reactions(self):
        """Multiple reactions of same emoji increment count."""
        mock_post = Mock()
        mock_post.reactions = {"👍": 2}

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(first=Mock(return_value=mock_post)))
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        reactions = await agent_social_layer.add_reaction(
            post_id="post-123",
            sender_id="agent-789",
            emoji="👍",
            db=mock_db
        )

        assert reactions["👍"] == 3


class TestTrendingTopics:
    """Test trending topics calculation."""

    @pytest.mark.asyncio
    async def test_trending_topics(self):
        """Trending topics are calculated from recent posts."""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)

        # Mock posts with mentions
        mock_post1 = Mock()
        mock_post1.mentioned_agent_ids = ["agent-1", "agent-2"]
        mock_post1.mentioned_user_ids = ["user-1"]
        mock_post1.mentioned_episode_ids = ["episode-1"]
        mock_post1.mentioned_task_ids = []

        mock_post2 = Mock()
        mock_post2.mentioned_agent_ids = ["agent-1"]
        mock_post2.mentioned_user_ids = []
        mock_post2.mentioned_episode_ids = []
        mock_post2.mentioned_task_ids = ["task-1"]

        mock_query.all = Mock(return_value=[mock_post1, mock_post2])

        mock_db.query = Mock(return_value=mock_query)

        trending = await agent_social_layer.get_trending_topics(
            hours=24,
            db=mock_db
        )

        # agent-1 mentioned twice (should be top)
        assert any(t["topic"] == "agent:agent-1" and t["mentions"] == 2 for t in trending)
        # user-1 mentioned once
        assert any(t["topic"] == "user:user-1" and t["mentions"] == 1 for t in trending)
        # task-1 mentioned once
        assert any(t["topic"] == "task:task-1" and t["mentions"] == 1 for t in trending)


class TestMentions:
    """Test @mentions in posts."""

    @pytest.mark.asyncio
    async def test_agent_mentions(self):
        """Posts can mention other agents."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        post = await agent_social_layer.create_post(
            sender_type="agent",
            sender_id="agent-123",
            sender_name="AgentA",
            post_type="question",
            content="Hey @agent-456, can you help?",
            mentioned_agent_ids=["agent-456"],
            db=mock_db
        )

        assert post["mentioned_agent_ids"] == ["agent-456"]

    @pytest.mark.asyncio
    async def test_multiple_mentions(self):
        """Posts can mention agents, users, episodes, and tasks."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        post = await agent_social_layer.create_post(
            sender_type="agent",
            sender_id="agent-123",
            sender_name="AgentA",
            post_type="insight",
            content="Related to episode-456 and task-789",
            mentioned_agent_ids=["agent-456"],
            mentioned_user_ids=["user-123"],
            mentioned_episode_ids=["episode-456"],
            mentioned_task_ids=["task-789"],
            db=mock_db
        )

        assert post["mentioned_agent_ids"] == ["agent-456"]
        assert post["mentioned_user_ids"] == ["user-123"]
        assert post["mentioned_episode_ids"] == ["episode-456"]
        assert post["mentioned_task_ids"] == ["task-789"]
