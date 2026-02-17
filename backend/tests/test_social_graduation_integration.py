"""
Integration tests for Social Layer and Graduation linkage.

Tests verify that positive interactions are tracked, agent reputation
is calculated, rate limits are enforced, and graduation milestones
are posted to the social feed.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from unittest.mock import Mock, AsyncMock, patch

from core.agent_social_layer import agent_social_layer
from core.models import (
    AgentPost, AgentRegistry, AgentFeedback
)


@pytest.fixture
def db_session(test_db: Session):
    """Database session fixture."""
    return test_db


@pytest.fixture
def test_agent_intern(db_session: Session):
    """Create test INTERN agent."""
    agent = AgentRegistry(
        id="test-agent-intern-grad",
        name="Test Agent Intern Grad",
        status="INTERN",
        category="testing",
        class_name="TestAgent",
        module_path="test.test_agent"
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_agent_supervised(db_session: Session):
    """Create test SUPERVISED agent."""
    agent = AgentRegistry(
        id="test-agent-supervised-grad",
        name="Test Agent Supervised Grad",
        status="SUPERVISED",
        category="testing",
        class_name="TestAgent",
        module_path="test.test_agent"
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_agent_student(db_session: Session):
    """Create test STUDENT agent."""
    agent = AgentRegistry(
        id="test-agent-student-grad",
        name="Test Agent Student Grad",
        status="STUDENT",
        category="testing",
        class_name="TestAgent",
        module_path="test.test_agent"
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_post(db_session: Session, test_agent_intern):
    """Create test post."""
    post = AgentPost(
        sender_type="agent",
        sender_id=test_agent_intern.id,
        sender_name=test_agent_intern.name,
        sender_maturity="INTERN",
        sender_category="testing",
        post_type="status",
        content="Test post for graduation testing",
        created_at=datetime.utcnow()
    )
    db_session.add(post)
    db_session.commit()
    return post


class TestReactionCounting:
    """Tests for tracking positive interactions."""

    @pytest.mark.asyncio
    async def test_track_positive_interaction_reaction(
        self, db_session: Session, test_post
    ):
        """Test that emoji reactions are tracked."""
        await agent_social_layer.track_positive_interaction(
            post_id=test_post.id,
            interaction_type="👍",
            user_id="user-123",
            db=db_session
        )

        # Verify feedback record created
        feedback = db_session.query(AgentFeedback).filter(
            AgentFeedback.agent_id == test_post.sender_id,
            AgentFeedback.feedback_type == "social_interaction"
        ).first()

        assert feedback is not None
        assert feedback.rating == 1.0
        assert "👍" in feedback.comment

    @pytest.mark.asyncio
    async def test_track_positive_interaction_reply(
        self, db_session: Session, test_post
    ):
        """Test that helpful replies are tracked."""
        await agent_social_layer.track_positive_interaction(
            post_id=test_post.id,
            interaction_type="thanks! that was helpful",
            user_id="user-456",
            db=db_session
        )

        # Verify feedback record created
        feedback = db_session.query(AgentFeedback).filter(
            AgentFeedback.agent_id == test_post.sender_id
        ).first()

        assert feedback is not None
        assert feedback.rating == 1.0

    @pytest.mark.asyncio
    async def test_negative_interaction_ignored(
        self, db_session: Session, test_post
    ):
        """Test that negative interactions are not counted."""
        await agent_social_layer.track_positive_interaction(
            post_id=test_post.id,
            interaction_type="this is wrong",
            user_id="user-789",
            db=db_session
        )

        # Verify no feedback created (negative interaction)
        feedback = db_session.query(AgentFeedback).filter(
            AgentFeedback.agent_id == test_post.sender_id
        ).first()

        assert feedback is None

    @pytest.mark.asyncio
    async def test_multiple_reactions_tracked(
        self, db_session: Session, test_post
    ):
        """Test that all reactions are counted."""
        # Add multiple reactions
        await agent_social_layer.track_positive_interaction(
            post_id=test_post.id,
            interaction_type="👍",
            user_id="user-1",
            db=db_session
        )

        await agent_social_layer.track_positive_interaction(
            post_id=test_post.id,
            interaction_type="❤️",
            user_id="user-2",
            db=db_session
        )

        # Verify both feedback records created
        feedbacks = db_session.query(AgentFeedback).filter(
            AgentFeedback.agent_id == test_post.sender_id
        ).all()

        assert len(feedbacks) == 2


class TestReputationScoring:
    """Tests for agent reputation calculation."""

    @pytest.mark.asyncio
    async def test_reputation_score_calculated(
        self, db_session: Session, test_agent_intern, test_post
    ):
        """Test that reputation score is calculated correctly."""
        # Create some reactions (simulated via feedback)
        for i in range(5):
            feedback = AgentFeedback(
                agent_id=test_agent_intern.id,
                user_id=f"user-{i}",
                feedback_type="social_interaction",
                rating=1.0,
                comment=f"Positive reaction {i}"
            )
            db_session.add(feedback)

        db_session.commit()

        # Get reputation
        reputation = await agent_social_layer.get_agent_reputation(
            agent_id=test_agent_intern.id,
            db=db_session
        )

        assert "reputation_score" in reputation
        assert reputation["post_count"] >= 1
        assert reputation["agent_id"] == test_agent_intern.id

    @pytest.mark.asyncio
    async def test_reputation_breakdown(
        self, db_session: Session, test_agent_intern
    ):
        """Test that reputation breakdown includes all metrics."""
        reputation = await agent_social_layer.get_agent_reputation(
            agent_id=test_agent_intern.id,
            db=db_session
        )

        assert "total_reactions" in reputation
        assert "total_replies" in reputation
        assert "helpful_replies" in reputation
        assert "post_count" in reputation

    @pytest.mark.asyncio
    async def test_reputation_zero_new_agent(
        self, db_session: Session
    ):
        """Test that new agents have reputation score of 0."""
        # Create new agent with no posts
        agent = AgentRegistry(
            id="new-agent-no-posts",
            name="New Agent",
            status="INTERN",
            category="testing",
            class_name="NewAgent",
            module_path="test.new_agent"
        )
        db_session.add(agent)
        db_session.commit()

        reputation = await agent_social_layer.get_agent_reputation(
            agent_id=agent.id,
            db=db_session
        )

        assert reputation["reputation_score"] == 0
        assert reputation["post_count"] == 0

    @pytest.mark.asyncio
    async def test_reputation_trend(
        self, db_session: Session, test_agent_intern
    ):
        """Test that 30-day trend is returned."""
        reputation = await agent_social_layer.get_agent_reputation(
            agent_id=test_agent_intern.id,
            db=db_session
        )

        assert "trend" in reputation
        assert isinstance(reputation["trend"], list)


class TestRateLimitEnforcement:
    """Tests for maturity-based rate limiting."""

    @pytest.mark.asyncio
    async def test_student_blocked(
        self, db_session: Session, test_agent_student
    ):
        """Test that STUDENT agents are blocked from posting."""
        allowed, reason = await agent_social_layer.check_rate_limit(
            agent_id=test_agent_student.id,
            db=db_session
        )

        assert allowed is False
        assert "read-only" in reason.lower()

    @pytest.mark.asyncio
    async def test_intern_hourly_limit(
        self, db_session: Session, test_agent_intern
    ):
        """Test that INTERN agents are limited to 1 post per hour."""
        # First post should be allowed
        allowed1, reason1 = await agent_social_layer.check_rate_limit(
            agent_id=test_agent_intern.id,
            db=db_session
        )
        assert allowed1 is True

        # Create a post
        post = AgentPost(
            sender_type="agent",
            sender_id=test_agent_intern.id,
            sender_name=test_agent_intern.name,
            sender_maturity="INTERN",
            post_type="status",
            content="First post",
            created_at=datetime.utcnow()
        )
        db_session.add(post)
        db_session.commit()

        # Second post should be blocked
        allowed2, reason2 = await agent_social_layer.check_rate_limit(
            agent_id=test_agent_intern.id,
            db=db_session
        )
        assert allowed2 is False
        assert "rate limit exceeded" in reason2.lower()

    @pytest.mark.asyncio
    async def test_supervised_five_min_limit(
        self, db_session: Session, test_agent_supervised
    ):
        """Test that SUPERVISED agents are limited to 12 posts per hour."""
        # Should be allowed initially
        allowed, reason = await agent_social_layer.check_rate_limit(
            agent_id=test_agent_supervised.id,
            db=db_session
        )
        assert allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_info(
        self, db_session: Session, test_agent_intern
    ):
        """Test that rate limit info is returned."""
        info = await agent_social_layer.get_rate_limit_info(
            agent_id=test_agent_intern.id,
            db=db_session
        )

        assert "max_posts_per_hour" in info
        assert "posts_last_hour" in info
        assert "remaining_posts" in info
        assert "maturity" in info

    @pytest.mark.asyncio
    async def test_rate_limit_unlimited_autonomous(
        self, db_session: Session
    ):
        """Test that AUTONOMOUS agents have unlimited posting."""
        agent = AgentRegistry(
            id="test-agent-autonomous",
            name="Autonomous Agent",
            status="AUTONOMOUS",
            category="testing",
            class_name="AutoAgent",
            module_path="test.auto_agent"
        )
        db_session.add(agent)
        db_session.commit()

        info = await agent_social_layer.get_rate_limit_info(
            agent_id=agent.id,
            db=db_session
        )

        assert info["unlimited"] is True
        assert info["max_posts_per_hour"] is None


class TestGraduationMilestonePosting:
    """Tests for graduation milestone posting."""

    @pytest.mark.asyncio
    async def test_post_graduation_milestone(
        self, db_session: Session, test_agent_intern
    ):
        """Test that graduation milestones are posted."""
        post = await agent_social_layer.post_graduation_milestone(
            agent_id=test_agent_intern.id,
            from_maturity="INTERN",
            to_maturity="SUPERVISED",
            db=db_session
        )

        assert post["id"] is not None
        assert post["post_type"] == "announcement"
        assert "graduated" in post["content"].lower()
        assert "INTERN" in post["content"]
        assert "SUPERVISED" in post["content"]

    @pytest.mark.asyncio
    async def test_milestone_includes_emoji(
        self, db_session: Session, test_agent_intern
    ):
        """Test that milestone post includes celebration emoji."""
        post = await agent_social_layer.post_graduation_milestone(
            agent_id=test_agent_intern.id,
            from_maturity="INTERN",
            to_maturity="SUPERVISED",
            db=db_session
        )

        assert "🎉" in post["content"] or "💪" in post["content"]

    @pytest.mark.asyncio
    async def test_milestone_post_public(
        self, db_session: Session, test_agent_intern
    ):
        """Test that milestone post is public."""
        post = await agent_social_layer.post_graduation_milestone(
            agent_id=test_agent_intern.id,
            from_maturity="INTERN",
            to_maturity="SUPERVISED",
            db=db_session
        )

        assert post["is_public"] is True

    @pytest.mark.asyncio
    async def test_milestone_broadcast(
        self, db_session: Session, test_agent_intern
    ):
        """Test that milestone is broadcast to all agents."""
        with patch('core.agent_social_layer.agent_event_bus') as mock_bus:
            mock_bus.publish = AsyncMock()

            await agent_social_layer.post_graduation_milestone(
                agent_id=test_agent_intern.id,
                from_maturity="INTERN",
                to_maturity="SUPERVISED",
                db=db_session
            )

            # Verify broadcast was called
            mock_bus.publish.assert_called_once()
            call_args = mock_bus.publish.call_args
            assert call_args[0][0]["type"] == "graduation_milestone"
            assert "global" in call_args[1][0]  # topics

    @pytest.mark.asyncio
    async def test_milestone_agent_not_found(
        self, db_session: Session
    ):
        """Test that milestone posting fails for non-existent agent."""
        with pytest.raises(ValueError, match="not found"):
            await agent_social_layer.post_graduation_milestone(
                agent_id="non-existent-agent",
                from_maturity="INTERN",
                to_maturity="SUPERVISED",
                db=db_session
            )


class TestRateLimitReset:
    """Tests for rate limit reset behavior."""

    @pytest.mark.asyncio
    async def test_rate_limit_reset_after_hour(
        self, db_session: Session, test_agent_intern
    ):
        """Test that rate limits reset after 1 hour."""
        # Create post 1 hour ago
        old_post = AgentPost(
            sender_type="agent",
            sender_id=test_agent_intern.id,
            sender_name=test_agent_intern.name,
            sender_maturity="INTERN",
            post_type="status",
            content="Old post",
            created_at=datetime.utcnow() - timedelta(hours=1, seconds=1)
        )
        db_session.add(old_post)
        db_session.commit()

        # Should be allowed now (old post outside 1-hour window)
        allowed, reason = await agent_social_layer.check_rate_limit(
            agent_id=test_agent_intern.id,
            db=db_session
        )

        assert allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_message(
        self, db_session: Session, test_agent_intern
    ):
        """Test that clear error message returned when limit exceeded."""
        # Create post within last hour
        post = AgentPost(
            sender_type="agent",
            sender_id=test_agent_intern.id,
            sender_name=test_agent_intern.name,
            sender_maturity="INTERN",
            post_type="status",
            content="Recent post",
            created_at=datetime.utcnow() - timedelta(minutes=30)
        )
        db_session.add(post)
        db_session.commit()

        # Should be blocked with clear message
        allowed, reason = await agent_social_layer.check_rate_limit(
            agent_id=test_agent_intern.id,
            db=db_session
        )

        assert allowed is False
        assert "rate limit exceeded" in reason.lower()
        assert "1 post" in reason.lower()


class TestAgentReputationCalculations:
    """Tests for reputation score calculations."""

    @pytest.mark.asyncio
    async def test_reactions_weighted_correctly(
        self, db_session: Session, test_agent_intern, test_post
    ):
        """Test that reactions contribute 2 points each."""
        # Add feedback for reactions
        for i in range(10):
            feedback = AgentFeedback(
                agent_id=test_agent_intern.id,
                user_id=f"user-{i}",
                feedback_type="social_interaction",
                rating=1.0,
                comment="👍"
            )
            db_session.add(feedback)

        db_session.commit()

        reputation = await agent_social_layer.get_agent_reputation(
            agent_id=test_agent_intern.id,
            db=db_session
        )

        # 10 reactions * 2 points = 20 points minimum
        assert reputation["reputation_score"] >= 20

    @pytest.mark.asyncio
    async def test_helpful_replies_weighted_correctly(
        self, db_session: Session, test_agent_intern
    ):
        """Test that helpful replies contribute 5 points each."""
        # Add high-rating feedback (helpful replies)
        for i in range(5):
            feedback = AgentFeedback(
                agent_id=test_agent_intern.id,
                user_id=f"user-{i}",
                feedback_type="social_interaction",
                rating=0.9,  # High rating
                comment=f"Helpful reply {i}"
            )
            db_session.add(feedback)

        db_session.commit()

        reputation = await agent_social_layer.get_agent_reputation(
            agent_id=test_agent_intern.id,
            db=db_session
        )

        # Should reflect helpful reply scoring
        assert "helpful_replies" in reputation
