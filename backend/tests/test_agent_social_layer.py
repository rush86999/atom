"""
Tests for AgentSocialLayer - agent-to-agent communication.

OpenClaw Integration Tests:
- INTERN+ maturity gate for posting
- STUDENT agents are read-only
- Post type validation
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
    """Test INTERN+ maturity requirement for posting."""

    @pytest.mark.asyncio
    async def test_intern_agent_can_post(self):
        """INTERN agents can create posts."""
        with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
            # get_governance_cache returns a GovernanceCache instance
            mock_cache_instance = Mock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "INTERN",
                "name": "TestAgent"
            })
            mock_cache.return_value = mock_cache_instance

            mock_db = Mock()
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()

            post = await agent_social_layer.create_post(
                agent_id="test-agent",
                post_type="status",
                content="Working on feature X",
                db=mock_db
            )

            assert post["agent_maturity"] == "INTERN"
            assert post["content"] == "Working on feature X"

    @pytest.mark.asyncio
    async def test_student_agent_cannot_post(self):
        """STUDENT agents cannot create posts."""
        with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
            mock_cache_instance = Mock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "STUDENT",
                "name": "TestAgent"
            })
            mock_cache.return_value = mock_cache_instance

            mock_db = Mock()

            with pytest.raises(PermissionError) as exc_info:
                await agent_social_layer.create_post(
                    agent_id="test-agent",
                    post_type="status",
                    content="I'm a student",
                    db=mock_db
                )

            assert "STUDENT agents cannot post" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_supervised_agent_can_post(self):
        """SUPERVISED agents can create posts."""
        with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
            mock_cache_instance = Mock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "SUPERVISED",
                "name": "TestAgent"
            })
            mock_cache.return_value = mock_cache_instance

            mock_db = Mock()
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()

            post = await agent_social_layer.create_post(
                agent_id="test-agent",
                post_type="insight",
                content="Discovered a bug",
                db=mock_db
            )

            assert post["post_type"] == "insight"


class TestPostTypes:
    """Test post type validation."""

    @pytest.mark.asyncio
    async def test_valid_post_types(self):
        """Valid post types: status, insight, question, alert."""
        valid_types = ["status", "insight", "question", "alert"]

        for post_type in valid_types:
            with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
                mock_cache_instance = Mock()
                mock_cache_instance.get = AsyncMock(return_value={
                    "agent_id": "test-agent",
                    "maturity_level": "INTERN"
                })
                mock_cache.return_value = mock_cache_instance

                mock_db = Mock()
                mock_db.add = Mock()
                mock_db.commit = Mock()
                mock_db.refresh = Mock()

                post = await agent_social_layer.create_post(
                    agent_id="test-agent",
                    post_type=post_type,
                    content="Test content",
                    db=mock_db
                )

                assert post["post_type"] == post_type

    @pytest.mark.asyncio
    async def test_invalid_post_type_rejected(self):
        """Invalid post types are rejected."""
        with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
            mock_cache_instance = Mock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "INTERN"
            })
            mock_cache.return_value = mock_cache_instance

            mock_db = Mock()

            with pytest.raises(ValueError) as exc_info:
                await agent_social_layer.create_post(
                    agent_id="test-agent",
                    post_type="invalid_type",
                    content="Test",
                    db=mock_db
                )

            assert "Invalid post_type" in str(exc_info.value)


class TestFeedPagination:
    """Test feed pagination and filtering."""

    @pytest.mark.asyncio
    async def test_feed_pagination(self):
        """Feed supports pagination with limit and offset."""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.count = Mock(return_value=100)
        mock_query.order_by = Mock(return_value=mock_query)
        mock_query.offset = Mock(return_value=mock_query)
        mock_query.limit = Mock(return_value=mock_query)
        mock_query.all = Mock(return_value=[])

        mock_db.query = Mock(return_value=mock_query)

        feed = await agent_social_layer.get_feed(
            agent_id="test-agent",
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
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.count = Mock(return_value=10)
        mock_query.order_by = Mock(return_value=mock_query)
        mock_query.offset = Mock(return_value=mock_query)
        mock_query.limit = Mock(return_value=mock_query)
        mock_query.all = Mock(return_value=[])

        mock_db.query = Mock(return_value=mock_query)

        feed = await agent_social_layer.get_feed(
            agent_id="test-agent",
            post_type="question",
            db=mock_db
        )

        assert feed["total"] == 10


class TestEventBusIntegration:
    """Test WebSocket broadcasting through event bus."""

    @pytest.mark.asyncio
    async def test_post_broadcasts_to_event_bus(self):
        """New posts are broadcast to event bus subscribers."""
        with patch('core.agent_social_layer.get_governance_cache') as mock_cache:
            mock_cache_instance = Mock()
            mock_cache_instance.get = AsyncMock(return_value={
                "agent_id": "test-agent",
                "maturity_level": "INTERN",
                "name": "TestAgent"
            })
            mock_cache.return_value = mock_cache_instance

            mock_db = Mock()
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_db.refresh = Mock()

            # Mock event bus broadcast
            with patch.object(agent_event_bus, 'broadcast_post', new=AsyncMock()) as mock_broadcast:
                await agent_social_layer.create_post(
                    agent_id="test-agent",
                    post_type="status",
                    content="Test post",
                    db=mock_db
                )

                # Verify broadcast was called
                assert mock_broadcast.called
                call_args = mock_broadcast.call_args[0][0]
                assert call_args["agent_id"] == "test-agent"
                assert call_args["content"] == "Test post"


class TestReactions:
    """Test emoji reactions on posts."""

    @pytest.mark.asyncio
    async def test_add_reaction(self):
        """Agents can add emoji reactions to posts."""
        # Create a simple object instead of Mock to avoid attribute access issues
        class FakePost:
            def __init__(self):
                self.reactions = None

        mock_post = FakePost()

        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_post
        mock_db.query.return_value = mock_query
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        result = await agent_social_layer.add_reaction(
            post_id="post-123",
            agent_id="agent-456",
            emoji="👍",
            db=mock_db
        )

        assert result["👍"] == 1

    @pytest.mark.asyncio
    async def test_multiple_reactions(self):
        """Multiple reactions of same emoji increment count."""
        # Create a simple object with existing reactions
        class FakePost:
            def __init__(self):
                self.reactions = {"👍": 2, "🎉": 1}

        mock_post = FakePost()

        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_post
        mock_db.query.return_value = mock_query
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        result = await agent_social_layer.add_reaction(
            post_id="post-123",
            agent_id="agent-789",
            emoji="👍",
            db=mock_db
        )

        assert result["👍"] == 3
        assert result["🎉"] == 1  # Other reaction preserved


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
        mock_post1.mentioned_episode_ids = ["episode-1"]
        mock_post1.mentioned_task_ids = []

        mock_post2 = Mock()
        mock_post2.mentioned_agent_ids = ["agent-1"]
        mock_post2.mentioned_episode_ids = []
        mock_post2.mentioned_task_ids = ["task-1"]

        mock_query.all = Mock(return_value=[mock_post1, mock_post2])

        from datetime import timedelta
        from unittest.mock import patch
        with patch('core.agent_social_layer.timedelta') as mock_timedelta:
            mock_timedelta.return_value = timedelta(hours=24)

            mock_db.query = Mock(return_value=mock_query)

            trending = await agent_social_layer.get_trending_topics(
                hours=24,
                db=mock_db
            )

            # agent-1 mentioned twice (should be top)
            assert any(t["topic"] == "agent:agent-1" and t["mentions"] == 2 for t in trending)
