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


class TestPIIRedaction:
    """Test PII redaction from post content."""

    @pytest.mark.asyncio
    async def test_email_redaction(self):
        """Email addresses are redacted from posts."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        mock_agent.category = "engineering"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock PII redactor
        mock_redaction_result = Mock()
        mock_redaction_result.redacted_text = "Contact us at [REDACTED] for support"
        mock_redaction_result.has_secrets = True
        mock_redaction_result.redactions = [
            {"type": "EMAIL", "text": "support@atom.ai", "start": 14, "end": 28}
        ]

        mock_pii_redactor = Mock()
        mock_pii_redactor.redact = Mock(return_value=mock_redaction_result)

        with patch('core.agent_social_layer.get_pii_redactor', return_value=mock_pii_redactor):
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Contact us at support@atom.ai for support",
                db=mock_db
            )

            # Verify PII redactor was called
            mock_pii_redactor.redact.assert_called_once()
            # Verify redacted content was used
            assert post["content"] == mock_redaction_result.redacted_text

    @pytest.mark.asyncio
    async def test_phone_redaction(self):
        """Phone numbers are redacted from posts."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        mock_redaction_result = Mock()
        mock_redaction_result.redacted_text = "Call me at [REDACTED]"
        mock_redaction_result.has_secrets = True
        mock_redaction_result.redactions = [{"type": "PHONE_NUMBER", "text": "415-555-1234"}]

        mock_pii_redactor = Mock()
        mock_pii_redactor.redact = Mock(return_value=mock_redaction_result)

        with patch('core.agent_social_layer.get_pii_redactor', return_value=mock_pii_redactor):
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Call me at 415-555-1234",
                db=mock_db
            )

            mock_pii_redactor.redact.assert_called_once()
            assert post["content"] == mock_redaction_result.redacted_text

    @pytest.mark.asyncio
    async def test_ssn_redaction(self):
        """Social Security Numbers are redacted from posts."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        mock_redaction_result = Mock()
        mock_redaction_result.redacted_text = "SSN: [REDACTED]"
        mock_redaction_result.has_secrets = True
        mock_redaction_result.redactions = [{"type": "US_SSN", "text": "123-45-6789"}]

        mock_pii_redactor = Mock()
        mock_pii_redactor.redact = Mock(return_value=mock_redaction_result)

        with patch('core.agent_social_layer.get_pii_redactor', return_value=mock_pii_redactor):
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="SSN: 123-45-6789",
                db=mock_db
            )

            mock_pii_redactor.redact.assert_called_once()

    @pytest.mark.asyncio
    async def test_credit_card_redaction(self):
        """Credit card numbers are redacted from posts."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        mock_redaction_result = Mock()
        mock_redaction_result.redacted_text = "Card: [REDACTED]"
        mock_redaction_result.has_secrets = True
        mock_redaction_result.redactions = [{"type": "CREDIT_CARD", "text": "4111-1111-1111-1111"}]

        mock_pii_redactor = Mock()
        mock_pii_redactor.redact = Mock(return_value=mock_redaction_result)

        with patch('core.agent_social_layer.get_pii_redactor', return_value=mock_pii_redactor):
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Card: 4111-1111-1111-1111",
                db=mock_db
            )

            mock_pii_redactor.redact.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_pii_types_redaction(self):
        """Multiple PII types are redacted from single post."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        mock_redaction_result = Mock()
        mock_redaction_result.redacted_text = "Email: [REDACTED], Phone: [REDACTED]"
        mock_redaction_result.has_secrets = True
        mock_redaction_result.redactions = [
            {"type": "EMAIL", "text": "test@example.com"},
            {"type": "PHONE_NUMBER", "text": "555-1234"}
        ]

        mock_pii_redactor = Mock()
        mock_pii_redactor.redact = Mock(return_value=mock_redaction_result)

        with patch('core.agent_social_layer.get_pii_redactor', return_value=mock_pii_redactor):
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Email: test@example.com, Phone: 555-1234",
                db=mock_db
            )

            mock_pii_redactor.redact.assert_called_once()

    @pytest.mark.asyncio
    async def test_pii_redaction_failure_graceful(self):
        """If PII redaction fails, post is still created with original content."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        mock_pii_redactor = Mock()
        mock_pii_redactor.redact = Mock(side_effect=Exception("Redaction service down"))

        with patch('core.agent_social_layer.get_pii_redactor', return_value=mock_pii_redactor):
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Original content",
                db=mock_db
            )

            # Post should still be created with original content
            assert post["content"] == "Original content"

    @pytest.mark.asyncio
    async def test_skip_pii_redaction_flag(self):
        """Admin/debug posts can skip PII redaction."""
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
            post_type="status",
            content="Email: test@example.com",
            skip_pii_redaction=True,
            db=mock_db
        )

        # Original content should be preserved
        assert post["content"] == "Email: test@example.com"


class TestSocialMediaAPIIntegration:
    """Test social media API integration (Twitter, LinkedIn, Slack)."""

    @pytest.mark.asyncio
    async def test_twitter_post_generation(self):
        """Generate post for Twitter with character limit."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock Twitter client
        mock_twitter_client = AsyncMock()
        mock_twitter_client.create_tweet = AsyncMock(return_value={"id": "123456789"})

        with patch('core.agent_social_layer.twitter_client', mock_twitter_client):
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Excited to announce our new feature! #AI #Automation",
                channel_id="twitter",
                db=mock_db
            )

            assert post["channel_id"] == "twitter"

    @pytest.mark.asyncio
    async def test_linkedin_post_generation(self):
        """Generate post for LinkedIn with professional formatting."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock LinkedIn client
        mock_linkedin_client = AsyncMock()
        mock_linkedin_client.create_post = AsyncMock(return_value={"id": "linkedin-123"})

        with patch('core.agent_social_layer.linkedin_client', mock_linkedin_client):
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="insight",
                content="Just published an article on AI best practices",
                channel_id="linkedin",
                db=mock_db
            )

            assert post["channel_id"] == "linkedin"

    @pytest.mark.asyncio
    async def test_slack_post_generation(self):
        """Generate post for Slack with markdown formatting."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock Slack client
        mock_slack_client = AsyncMock()
        mock_slack_client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "1234567890.123"})

        with patch('core.agent_social_layer.slack_client', mock_slack_client):
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="alert",
                content="*Deployment Alert*: Production update complete",
                channel_id="slack",
                db=mock_db
            )

            assert post["channel_id"] == "slack"


class TestRateLimiting:
    """Test rate limiting for social media platforms."""

    @pytest.mark.asyncio
    async def test_twitter_rate_limiting(self):
        """Twitter: 300 posts per day rate limit."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))

        # Mock recent posts count (299 today, 1 remaining)
        mock_query = Mock()
        mock_query.count = Mock(return_value=299)
        mock_db.query.return_value.filter.return_value = mock_query

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Should allow 300th post
        post = await agent_social_layer.create_post(
            sender_type="agent",
            sender_id="test-agent",
            sender_name="TestAgent",
            post_type="status",
            content="Post number 300",
            channel_id="twitter",
            db=mock_db
        )

        assert post["channel_id"] == "twitter"

    @pytest.mark.asyncio
    async def test_twitter_rate_limit_exceeded(self):
        """Twitter: Reject posts when daily limit exceeded."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))

        # Mock recent posts count (300 today, limit reached)
        mock_query = Mock()
        mock_query.count = Mock(return_value=300)
        mock_db.query.return_value.filter.return_value = mock_query

        with pytest.raises(ValueError) as exc_info:
            await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Post number 301",
                channel_id="twitter",
                db=mock_db
            )

        assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_linkedin_rate_limiting(self):
        """LinkedIn: 100 posts per day rate limit."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))

        # Mock recent posts count (99 today, 1 remaining)
        mock_query = Mock()
        mock_query.count = Mock(return_value=99)
        mock_db.query.return_value.filter.return_value = mock_query

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Should allow 100th post
        post = await agent_social_layer.create_post(
            sender_type="agent",
            sender_id="test-agent",
            sender_name="TestAgent",
            post_type="status",
            content="Post number 100",
            channel_id="linkedin",
            db=mock_db
        )

        assert post["channel_id"] == "linkedin"


class TestPostScheduling:
    """Test post scheduling and queueing."""

    @pytest.mark.asyncio
    async def test_schedule_future_post(self):
        """Posts can be scheduled for future delivery."""
        from datetime import datetime, timedelta

        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        scheduled_time = datetime.utcnow() + timedelta(hours=2)

        post = await agent_social_layer.create_post(
            sender_type="agent",
            sender_id="test-agent",
            sender_name="TestAgent",
            post_type="status",
            content="Scheduled post",
            scheduled_for=scheduled_time.isoformat(),
            db=mock_db
        )

        assert post["scheduled_for"] == scheduled_time.isoformat()

    @pytest.mark.asyncio
    async def test_queue_overflow_handling(self):
        """Handle queue overflow when too many posts scheduled."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))

        # Mock queue size at limit (1000 posts)
        mock_query = Mock()
        mock_query.count = Mock(return_value=1000)
        mock_db.query.return_value.filter.return_value = mock_query

        with pytest.raises(ValueError) as exc_info:
            await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Overflow post",
                scheduled_for="2026-04-26T10:00:00Z",
                db=mock_db
            )

        assert "queue" in str(exc_info.value).lower() or "limit" in str(exc_info.value).lower()


class TestErrorHandling:
    """Test error handling for API failures."""

    @pytest.mark.asyncio
    async def test_twitter_api_timeout(self):
        """Handle Twitter API timeout gracefully."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock Twitter client timeout
        mock_twitter_client = AsyncMock()
        mock_twitter_client.create_tweet = AsyncMock(side_effect=asyncio.TimeoutError("Twitter API timeout"))

        with patch('core.agent_social_layer.twitter_client', mock_twitter_client):
            # Should not raise exception, post should be created locally
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Test post",
                channel_id="twitter",
                db=mock_db
            )

            # Post should still be created in database
            assert post["content"] == "Test post"

    @pytest.mark.asyncio
    async def test_linkedin_api_500_error(self):
        """Handle LinkedIn API 500 error gracefully."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock LinkedIn client 500 error
        mock_linkedin_client = AsyncMock()
        mock_linkedin_client.create_post = AsyncMock(side_effect=Exception("LinkedIn API 500 Error"))

        with patch('core.agent_social_layer.linkedin_client', mock_linkedin_client):
            # Should not raise exception
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Test post",
                channel_id="linkedin",
                db=mock_db
            )

            assert post["content"] == "Test post"

    @pytest.mark.asyncio
    async def test_slack_api_rate_limit_429(self):
        """Handle Slack API 429 rate limit error."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"

        mock_db = Mock()
        mock_db.query = Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_agent)))))
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock Slack client 429 error
        mock_slack_client = AsyncMock()
        mock_slack_client.chat_postMessage = AsyncMock(
            side_effect=Exception("Slack API 429: Rate Limit Exceeded")
        )

        with patch('core.agent_social_layer.slack_client', mock_slack_client):
            # Should not raise exception
            post = await agent_social_layer.create_post(
                sender_type="agent",
                sender_id="test-agent",
                sender_name="TestAgent",
                post_type="status",
                content="Test post",
                channel_id="slack",
                db=mock_db
            )

            assert post["content"] == "Test post"


class TestAutoGeneratedPosts:
    """Test auto-generated posts from operation tracker."""

    @pytest.mark.asyncio
    async def test_auto_generated_post_flag(self):
        """Posts auto-generated from operation tracker are marked."""
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
            post_type="status",
            content="Auto-generated status update",
            auto_generated=True,
            db=mock_db
        )

        assert post["auto_generated"] is True

    @pytest.mark.asyncio
    async def test_auto_generated_posts_skip_pii_check(self):
        """Auto-generated posts may skip PII checks (system-generated)."""
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
            post_type="status",
            content="System: Task completed successfully",
            auto_generated=True,
            skip_pii_redaction=True,
            db=mock_db
        )

        assert post["auto_generated"] is True
        assert post["content"] == "System: Task completed successfully"


class TestTenantIsolation:
    """Test tenant_id handling for multi-tenant deployments."""

    @pytest.mark.asyncio
    async def test_agent_tenant_id_preserved(self):
        """Agent posts preserve tenant_id from agent registry."""
        mock_agent = Mock()
        mock_agent.status = "INTERN"
        mock_agent.tenant_id = "tenant-abc123"

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
            content="Test post",
            db=mock_db
        )

        # Verify tenant_id is preserved in metadata
        assert post.get("tenant_id") == "tenant-abc123"

    @pytest.mark.asyncio
    async def test_human_post_default_tenant(self):
        """Human posts use default tenant_id."""
        mock_db = Mock()
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        post = await agent_social_layer.create_post(
            sender_type="human",
            sender_id="user-123",
            sender_name="Alice",
            post_type="status",
            content="Test post",
            db=mock_db
        )

        # Should use default tenant
        assert post.get("tenant_id") == "default"
