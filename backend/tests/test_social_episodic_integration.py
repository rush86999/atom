"""
Integration tests for Social Layer and Episodic Memory linkage.

Tests verify that social posts create episode segments, retrieve relevant
episodes for context, and include episode context in feeds.
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from unittest.mock import Mock, AsyncMock, patch

from core.agent_social_layer import agent_social_layer
from core.models import (
    AgentPost, AgentRegistry, Episode, EpisodeSegment
)


@pytest.fixture
def db_session(test_db: Session):
    """Database session fixture."""
    return test_db


@pytest.fixture
def test_agent(db_session: Session):
    """Create test agent."""
    agent = AgentRegistry(
        id="test-agent-episodic",
        name="Test Agent Episodic",
        status="INTERN",
        category="testing",
        class_name="TestAgent",
        module_path="test.test_agent"
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_episodes(db_session: Session, test_agent):
    """Create test episodes."""
    episodes = []
    for i in range(3):
        episode = Episode(
            id=f"episode-{i}",
            agent_id=test_agent.id,
            title=f"Test Episode {i}",
            summary=f"Test episode summary {i} with some content",
            status="completed",
            created_at=datetime.utcnow()
        )
        db_session.add(episode)
        episodes.append(episode)

    db_session.commit()
    return episodes


class TestSocialPostEpisodeCreation:
    """Tests for episode creation when social posts are created."""

    @pytest.mark.asyncio
    async def test_create_post_creates_episode_segment(
        self, db_session: Session, test_agent, test_episodes
    ):
        """Test that creating a post creates an episode segment."""
        episode_ids = [ep.id for ep in test_episodes[:1]]

        post = await agent_social_layer.create_post_with_episode(
            sender_type="agent",
            sender_id=test_agent.id,
            sender_name=test_agent.name,
            post_type="status",
            content="Just finished processing data",
            episode_ids=episode_ids,
            db=db_session
        )

        # Verify post created
        assert post["id"] is not None
        assert post["content"] == "Just finished processing data"

        # Verify episode segment created
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode_ids[0]
        ).all()

        assert len(segments) == 1
        assert segments[0].segment_type == "social_post"
        assert segments[0].agent_id == test_agent.id

    @pytest.mark.asyncio
    async def test_create_post_links_episodes(
        self, db_session: Session, test_agent, test_episodes
    ):
        """Test that mentioned_episode_ids is populated."""
        episode_ids = [ep.id for ep in test_episodes]

        post = await agent_social_layer.create_post_with_episode(
            sender_type="agent",
            sender_id=test_agent.id,
            sender_name=test_agent.name,
            post_type="status",
            content="Working on data analysis",
            episode_ids=episode_ids,
            db=db_session
        )

        # Verify post links to episodes
        assert post.get("mentioned_episode_ids") == episode_ids

    @pytest.mark.asyncio
    async def test_create_post_without_episodes(
        self, db_session: Session, test_agent
    ):
        """Test that posts work without episode references."""
        post = await agent_social_layer.create_post_with_episode(
            sender_type="agent",
            sender_id=test_agent.id,
            sender_name=test_agent.name,
            post_type="status",
            content="Quick status update",
            episode_ids=None,
            db=db_session
        )

        # Verify post created successfully
        assert post["id"] is not None
        assert post.get("mentioned_episode_ids") == []

    @pytest.mark.asyncio
    async def test_episode_segment_metadata(
        self, db_session: Session, test_agent, test_episodes
    ):
        """Test that episode segment has correct metadata."""
        import json

        episode_ids = [ep.id for ep in test_episodes[:1]]

        post = await agent_social_layer.create_post_with_episode(
            sender_type="agent",
            sender_id=test_agent.id,
            sender_name=test_agent.name,
            post_type="insight",
            content="Discovered interesting pattern",
            episode_ids=episode_ids,
            db=db_session
        )

        # Get segment
        segment = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode_ids[0]
        ).first()

        assert segment is not None
        metadata = json.loads(segment.metadata)
        assert metadata["sender_type"] == "agent"
        assert metadata["sender_id"] == test_agent.id
        assert metadata["post_type"] == "insight"
        assert "timestamp" in metadata


class TestEpisodeRetrievalForPosts:
    """Tests for episode retrieval when creating posts."""

    @pytest.mark.asyncio
    async def test_retrieve_episodes_by_content(
        self, db_session: Session, test_agent, test_episodes
    ):
        """Test retrieving episodes by content similarity."""
        # Mock retrieval service
        with patch('core.agent_social_layer.EpisodeRetrievalService') as MockRetrieval:
            mock_service = Mock()
            mock_service.retrieve_episodes = AsyncMock(return_value=test_episodes[:2])
            MockRetrieval.return_value = mock_service

            episode_ids = await agent_social_layer._retrieve_relevant_episodes(
                test_agent.id,
                "data analysis workflow",
                limit=3,
                db=db_session
            )

            assert len(episode_ids) == 2
            mock_service.retrieve_episodes.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_episodes_empty_no_db(
        self, test_agent
    ):
        """Test that empty list returned when no DB session."""
        episode_ids = await agent_social_layer._retrieve_relevant_episodes(
            test_agent.id,
            "workflow execution",
            limit=3,
            db=None
        )

        assert episode_ids == []

    @pytest.mark.asyncio
    async def test_retrieve_episodes_fallback_on_error(
        self, db_session: Session, test_agent
    ):
        """Test fallback to empty list on retrieval error."""
        with patch('core.agent_social_layer.EpisodeRetrievalService') as MockRetrieval:
            MockRetrieval.side_effect = Exception("Retrieval service error")

            episode_ids = await agent_social_layer._retrieve_relevant_episodes(
                test_agent.id,
                "workflow execution",
                limit=3,
                db=db_session
            )

            assert episode_ids == []


class TestFeedWithEpisodeContext:
    """Tests for feed with episode context."""

    @pytest.mark.asyncio
    async def test_feed_includes_episode_context(
        self, db_session: Session, test_agent, test_episodes
    ):
        """Test that feed includes episode context for posts."""
        # Create post with episode references
        post = await agent_social_layer.create_post_with_episode(
            sender_type="agent",
            sender_id=test_agent.id,
            sender_name=test_agent.name,
            post_type="status",
            content="Processing data",
            episode_ids=[ep.id for ep in test_episodes],
            db=db_session
        )

        # Get feed with episode context
        feed = await agent_social_layer.get_feed_with_episode_context(
            agent_id=test_agent.id,
            include_episode_context=True,
            db=db_session
        )

        assert len(feed["posts"]) > 0
        assert "episode_context" in feed["posts"][0]

    @pytest.mark.asyncio
    async def test_feed_without_episode_context(
        self, db_session: Session, test_agent
    ):
        """Test that feed works without episode context."""
        # Create post without episodes
        await agent_social_layer.create_post(
            sender_type="agent",
            sender_id=test_agent.id,
            sender_name=test_agent.name,
            post_type="status",
            content="Quick update",
            db=db_session
        )

        # Get feed
        feed = await agent_social_layer.get_feed_with_episode_context(
            agent_id=test_agent.id,
            include_episode_context=True,
            db=db_session
        )

        assert len(feed["posts"]) > 0

    @pytest.mark.asyncio
    async def test_get_episode_summaries(
        self, db_session: Session, test_episodes
    ):
        """Test getting episode summaries."""
        episode_ids = [ep.id for ep in test_episodes]

        summaries = await agent_social_layer._get_episode_summaries(
            episode_ids,
            db=db_session
        )

        assert len(summaries) == 3
        assert summaries[0]["id"] == test_episodes[0].id
        assert summaries[0]["title"] == test_episodes[0].title
        assert summaries[0]["summary"] is not None

    @pytest.mark.asyncio
    async def test_get_episode_summaries_empty(
        self, db_session: Session
    ):
        """Test episode summaries with empty list."""
        summaries = await agent_social_layer._get_episode_summaries(
            [],
            db=db_session
        )

        assert summaries == []

    @pytest.mark.asyncio
    async def test_get_episode_summaries_no_db(
        self
    ):
        """Test episode summaries without DB session."""
        summaries = await agent_social_layer._get_episode_summaries(
            ["episode-1", "episode-2"],
            db=None
        )

        assert summaries == []

    @pytest.mark.asyncio
    async def test_feed_episode_context_filterable(
        self, db_session: Session, test_agent, test_episodes
    ):
        """Test that episode context can be filtered."""
        # Create post with episode
        await agent_social_layer.create_post_with_episode(
            sender_type="agent",
            sender_id=test_agent.id,
            sender_name=test_agent.name,
            post_type="status",
            content="Analysis complete",
            episode_ids=[test_episodes[0].id],
            db=db_session
        )

        # Get feed
        feed = await agent_social_layer.get_feed_with_episode_context(
            agent_id=test_agent.id,
            include_episode_context=True,
            db=db_session
        )

        # Verify episode context included
        post_with_context = feed["posts"][0]
        if post_with_context.get("mentioned_episode_ids"):
            assert "episode_context" in post_with_context


class TestSocialPostGeneratorWithEpisodes:
    """Tests for SocialPostGenerator with episode retrieval."""

    @pytest.mark.asyncio
    async def test_generate_post_with_episode_context(
        self, db_session: Session, test_agent, test_episodes
    ):
        """Test generating post with episode context."""
        from core.social_post_generator import social_post_generator

        # Mock episode retrieval
        with patch.object(
            social_post_generator,
            '_retrieve_relevant_episodes',
            return_value=test_episodes[:2]
        ):
            # Mock LLM generation
            with patch.object(
                social_post_generator,
                '_generate_with_llm_and_context',
                return_value="Building on my previous work, I've completed the data analysis! 📊"
            ):
                result = await social_post_generator.generate_with_episode_context(
                    agent_id=test_agent.id,
                    operation={
                        "operation_type": "workflow_execute",
                        "what_explanation": "Data analysis workflow",
                        "why_explanation": "Business insights"
                    },
                    db=db_session,
                    limit=3
                )

                assert "content" in result
                assert "mentioned_episode_ids" in result
                assert len(result["mentioned_episode_ids"]) == 2

    @pytest.mark.asyncio
    async def test_format_episode_context(self):
        """Test episode context formatting."""
        from core.social_post_generator import social_post_generator

        # Create mock episodes
        mock_episodes = [
            Mock(summary="Analyzed Q4 sales data and found trends"),
            Mock(summary="Integrated with API endpoint for data sync"),
            Mock(summary="Processed customer feedback survey")
        ]

        context = social_post_generator._format_episode_context(mock_episodes)

        assert "Similar to past experiences:" in context
        assert "Q4 sales data" in context
        assert "API endpoint" in context

    @pytest.mark.asyncio
    async def test_format_episode_context_truncated(self):
        """Test that episode context is truncated to 280 chars."""
        from core.social_post_generator import social_post_generator

        # Create long summary
        long_summary = "A" * 300
        mock_episodes = [Mock(summary=long_summary)]

        context = social_post_generator._format_episode_context(mock_episodes)

        assert len(context) <= 283  # 280 + "..."

    @pytest.mark.asyncio
    async def test_format_episode_context_empty(self):
        """Test formatting empty episode list."""
        from core.social_post_generator import social_post_generator

        context = social_post_generator._format_episode_context([])

        assert context == ""

    @pytest.mark.asyncio
    async def test_build_system_prompt_with_episodes(self):
        """Test system prompt with episode guidance."""
        from core.social_post_generator import social_post_generator

        prompt = social_post_generator._build_system_prompt(with_episodes=True)

        assert "reference similar past experiences" in prompt
        assert "Building on my previous work" in prompt

    @pytest.mark.asyncio
    async def test_build_system_prompt_without_episodes(self):
        """Test system prompt without episode guidance."""
        from core.social_post_generator import social_post_generator

        prompt = social_post_generator._build_system_prompt(with_episodes=False)

        assert "reference similar past experiences" not in prompt

    @pytest.mark.asyncio
    async def test_build_user_prompt(self):
        """Test user prompt building."""
        from core.social_post_generator import social_post_generator

        operation = {
            "operation_type": "workflow_execute",
            "what_explanation": "Data processing",
            "why_explanation": "Generate insights"
        }

        prompt = social_post_generator._build_user_prompt(operation)

        assert "workflow_execute" in prompt
        assert "Data processing" in prompt
        assert "Generate insights" in prompt
