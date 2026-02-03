"""
Enhanced Feedback System Tests

Comprehensive test suite for enhanced feedback functionality including:
- Thumbs up/down feedback
- Star ratings (1-5)
- Feedback types (correction, rating, approval, comment)
- Feedback analytics
- Confidence adjustments
- World model integration
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pytest
from sqlalchemy.orm import Session

from core.agent_learning_enhanced import AgentLearningEnhanced
from core.database import SessionLocal
from core.feedback_analytics import FeedbackAnalytics
from core.models import AgentExecution, AgentFeedback, AgentRegistry, User

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create a test database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    user = User(
        id=f"user-{uuid.uuid4()}",
        email="test@example.com",
        username="testuser",
        full_name="Test User"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    # Cleanup
    db.delete(user)
    db.commit()


@pytest.fixture
def test_agent(db):
    """Create a test agent."""
    agent = AgentRegistry(
        id=f"agent-{uuid.uuid4()}",
        name="Test Agent",
        category="Operations",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status="INTERN",
        confidence_score=0.7
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    yield agent
    # Cleanup
    db.query(AgentFeedback).filter(AgentFeedback.agent_id == agent.id).delete()
    db.delete(agent)
    db.commit()


@pytest.fixture
def test_execution(db, test_agent):
    """Create a test agent execution."""
    execution = AgentExecution(
        id=f"exec-{uuid.uuid4()}",
        agent_id=test_agent.id,
        workspace_id="default",
        status="completed",
        input_summary="Test execution",
        triggered_by="api"
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    yield execution
    # Cleanup
    db.delete(execution)
    db.commit()


# ============================================================================
# Feedback Submission Tests
# ============================================================================

class TestFeedbackSubmission:
    """Test enhanced feedback submission."""

    def test_submit_thumbs_up_feedback(self, db, test_agent, test_user, test_execution):
        """Test submitting thumbs up feedback."""
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            agent_execution_id=test_execution.id,
            user_id=test_user.id,
            input_context="Test input",
            original_output="Agent output",
            user_correction="",
            feedback_type="approval",
            thumbs_up_down=True,
            rating=None
        )

        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        assert feedback.id is not None
        assert feedback.thumbs_up_down is True
        assert feedback.feedback_type == "approval"
        assert feedback.agent_id == test_agent.id

        # Cleanup
        db.delete(feedback)
        db.commit()

    def test_submit_thumbs_down_feedback(self, db, test_agent, test_user):
        """Test submitting thumbs down feedback."""
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Agent output",
            user_correction="",
            thumbs_up_down=False,
            feedback_type="comment"
        )

        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        assert feedback.thumbs_up_down is False

        # Cleanup
        db.delete(feedback)
        db.commit()

    def test_submit_star_rating(self, db, test_agent, test_user):
        """Test submitting star rating."""
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Agent output",
            user_correction="",
            rating=5,
            feedback_type="rating"
        )

        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        assert feedback.rating == 5
        assert feedback.feedback_type == "rating"

        # Cleanup
        db.delete(feedback)
        db.commit()

    def test_submit_correction_feedback(self, db, test_agent, test_user):
        """Test submitting correction feedback."""
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            input_context="What is 2+2?",
            original_output="2+2=5",
            user_correction="2+2=4",
            feedback_type="correction"
        )

        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        assert feedback.feedback_type == "correction"
        assert "2+2=4" in feedback.user_correction

        # Cleanup
        db.delete(feedback)
        db.commit()

    def test_submit_mixed_feedback(self, db, test_agent, test_user):
        """Test submitting feedback with both rating and correction."""
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Agent output",
            user_correction="Better output",
            rating=3,
            thumbs_up_down=False,
            feedback_type="correction"
        )

        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        assert feedback.rating == 3
        assert feedback.thumbs_up_down is False
        assert feedback.feedback_type == "correction"

        # Cleanup
        db.delete(feedback)
        db.commit()


# ============================================================================
# Feedback Analytics Tests
# ============================================================================

class TestFeedbackAnalytics:
    """Test feedback analytics service."""

    def test_get_agent_feedback_summary(self, db, test_agent, test_user):
        """Test getting agent feedback summary."""
        # Create sample feedback
        for i in range(10):
            feedback = AgentFeedback(
                agent_id=test_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=(i % 2 == 0),  # 5 thumbs up, 5 thumbs down
                rating=None
            )
            db.add(feedback)

        db.commit()

        analytics = FeedbackAnalytics(db)
        summary = analytics.get_agent_feedback_summary(test_agent.id, days=30)

        assert summary["agent_id"] == test_agent.id
        assert summary["total_feedback"] == 10
        assert summary["thumbs_up_count"] == 5
        assert summary["thumbs_down_count"] == 5

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == test_agent.id).delete()
        db.commit()

    def test_get_feedback_statistics(self, db, test_agent, test_user):
        """Test getting overall feedback statistics."""
        # Create sample feedback
        for i in range(5):
            feedback = AgentFeedback(
                agent_id=test_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                rating=(i % 5) + 1,  # Ratings 1-5
                thumbs_up_down=None
            )
            db.add(feedback)

        db.commit()

        analytics = FeedbackAnalytics(db)
        stats = analytics.get_feedback_statistics(days=30)

        assert stats["total_feedback"] >= 5
        assert stats["overall_average_rating"] is not None

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == test_agent.id).delete()
        db.commit()

    def test_get_top_performing_agents(self, db, test_agent, test_user):
        """Test getting top performing agents."""
        # Create positive feedback
        for i in range(10):
            feedback = AgentFeedback(
                agent_id=test_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=True,
                rating=5
            )
            db.add(feedback)

        db.commit()

        analytics = FeedbackAnalytics(db)
        top_agents = analytics.get_top_performing_agents(days=30, limit=10)

        # Test agent should be in top agents
        agent_ids = [a["agent_id"] for a in top_agents]
        assert test_agent.id in agent_ids

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == test_agent.id).delete()
        db.commit()

    def test_get_most_corrected_agents(self, db, test_agent, test_user):
        """Test getting most corrected agents."""
        # Create correction feedback
        for i in range(5):
            feedback = AgentFeedback(
                agent_id=test_agent.id,
                user_id=test_user.id,
                original_output=f"Wrong output {i}",
                user_correction=f"Correct output {i}",
                feedback_type="correction"
            )
            db.add(feedback)

        db.commit()

        analytics = FeedbackAnalytics(db)
        most_corrected = analytics.get_most_corrected_agents(days=30, limit=10)

        # Test agent should be in most corrected
        agent_ids = [a["agent_id"] for a in most_corrected]
        assert test_agent.id in agent_ids

        # Should have 5 corrections
        for agent in most_corrected:
            if agent["agent_id"] == test_agent.id:
                assert agent["correction_count"] == 5

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == test_agent.id).delete()
        db.commit()

    def test_get_feedback_trends(self, db, test_agent, test_user):
        """Test getting feedback trends."""
        # Create feedback over multiple days
        for i in range(3):
            feedback = AgentFeedback(
                agent_id=test_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=True,
                rating=5,
                created_at=datetime.now() - timedelta(days=i)
            )
            db.add(feedback)

        db.commit()

        analytics = FeedbackAnalytics(db)
        trends = analytics.get_feedback_trends(days=30)

        assert len(trends) > 0
        assert "date" in trends[0]
        assert "total" in trends[0]
        assert "positive" in trends[0]
        assert "negative" in trends[0]

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == test_agent.id).delete()
        db.commit()


# ============================================================================
# Agent Learning Enhanced Tests
# ============================================================================

class TestAgentLearningEnhanced:
    """Test enhanced learning with feedback."""

    def test_adjust_confidence_with_thumbs_up(self, db, test_agent, test_user):
        """Test confidence adjustment with thumbs up."""
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Good output",
            user_correction="",
            thumbs_up_down=True
        )

        learning = AgentLearningEnhanced(db)
        new_confidence = learning.adjust_confidence_with_feedback(
            agent_id=test_agent.id,
            feedback=feedback,
            current_confidence=0.7
        )

        assert new_confidence > 0.7  # Should increase
        assert new_confidence <= 1.0  # Should not exceed 1.0

    def test_adjust_confidence_with_thumbs_down(self, db, test_agent, test_user):
        """Test confidence adjustment with thumbs down."""
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Bad output",
            user_correction="",
            thumbs_up_down=False
        )

        learning = AgentLearningEnhanced(db)
        new_confidence = learning.adjust_confidence_with_feedback(
            agent_id=test_agent.id,
            feedback=feedback,
            current_confidence=0.7
        )

        assert new_confidence < 0.7  # Should decrease
        assert new_confidence >= 0.0  # Should not go below 0.0

    def test_adjust_confidence_with_5_star_rating(self, db, test_agent, test_user):
        """Test confidence adjustment with 5-star rating."""
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Excellent output",
            user_correction="",
            rating=5
        )

        learning = AgentLearningEnhanced(db)
        new_confidence = learning.adjust_confidence_with_feedback(
            agent_id=test_agent.id,
            feedback=feedback,
            current_confidence=0.7
        )

        assert new_confidence > 0.7  # Should increase significantly

    def test_adjust_confidence_with_1_star_rating(self, db, test_agent, test_user):
        """Test confidence adjustment with 1-star rating."""
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Terrible output",
            user_correction="",
            rating=1
        )

        learning = AgentLearningEnhanced(db)
        new_confidence = learning.adjust_confidence_with_feedback(
            agent_id=test_agent.id,
            feedback=feedback,
            current_confidence=0.7
        )

        assert new_confidence < 0.7  # Should decrease significantly

    def test_adjust_confidence_with_correction(self, db, test_agent, test_user):
        """Test confidence adjustment with correction."""
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Wrong output",
            user_correction="Correct output",
            feedback_type="correction"
        )

        learning = AgentLearningEnhanced(db)
        new_confidence = learning.adjust_confidence_with_feedback(
            agent_id=test_agent.id,
            feedback=feedback,
            current_confidence=0.7
        )

        assert new_confidence < 0.7  # Should decrease

    def test_get_learning_signals(self, db, test_agent, test_user):
        """Test getting learning signals from feedback."""
        # Create mixed feedback
        for i in range(10):
            feedback = AgentFeedback(
                agent_id=test_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=(i < 7),  # 7 positive, 3 negative
                rating=5 if i < 7 else 2
            )
            db.add(feedback)

        db.commit()

        learning = AgentLearningEnhanced(db)
        signals = learning.get_learning_signals(test_agent.id, days=30)

        assert signals["agent_id"] == test_agent.id
        assert signals["total_feedback"] == 10
        assert signals["positive_ratio"] >= 0.6
        assert "learning_signals" in signals
        assert "improvement_suggestions" in signals

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == test_agent.id).delete()
        db.commit()

    def test_confidence_bounds(self, db, test_agent, test_user):
        """Test confidence adjustments stay within bounds."""
        learning = AgentLearningEnhanced(db)

        # Test upper bound
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Output",
            user_correction="",
            thumbs_up_down=True,
            rating=5
        )

        new_confidence = learning.adjust_confidence_with_feedback(
            agent_id=test_agent.id,
            feedback=feedback,
            current_confidence=0.95
        )

        assert new_confidence <= 1.0

        # Test lower bound
        feedback2 = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Output",
            user_correction="",
            thumbs_up_down=False,
            rating=1
        )

        new_confidence2 = learning.adjust_confidence_with_feedback(
            agent_id=test_agent.id,
            feedback=feedback2,
            current_confidence=0.05
        )

        assert new_confidence2 >= 0.0


# ============================================================================
# Integration Tests
# ============================================================================

class TestFeedbackIntegration:
    """Integration tests for feedback system."""

    def test_feedback_to_analytics_to_learning(self, db, test_agent, test_user):
        """Test full feedback lifecycle: submit -> analytics -> learning."""
        # Step 1: Submit feedback
        feedback = AgentFeedback(
            agent_id=test_agent.id,
            user_id=test_user.id,
            original_output="Test output",
            user_correction="",
            thumbs_up_down=True,
            rating=5
        )
        db.add(feedback)
        db.commit()

        # Step 2: Analytics
        analytics = FeedbackAnalytics(db)
        summary = analytics.get_agent_feedback_summary(test_agent.id, days=30)
        assert summary["total_feedback"] >= 1

        # Step 3: Learning
        learning = AgentLearningEnhanced(db)
        new_confidence = learning.adjust_confidence_with_feedback(
            agent_id=test_agent.id,
            feedback=feedback,
            current_confidence=test_agent.confidence_score
        )
        assert new_confidence != test_agent.confidence_score

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == test_agent.id).delete()
        db.commit()

    def test_batch_confidence_update(self, db, test_agent, test_user):
        """Test batch confidence update from multiple feedback."""
        # Create multiple feedback
        for i in range(20):
            feedback = AgentFeedback(
                agent_id=test_agent.id,
                user_id=test_user.id,
                original_output=f"Output {i}",
                user_correction="",
                thumbs_up_down=(i < 15),  # 15 positive, 5 negative
                rating=5 if i < 15 else 2,
                created_at=datetime.now() - timedelta(hours=i)
            )
            db.add(feedback)

        db.commit()

        learning = AgentLearningEnhanced(db)
        new_confidence = learning.batch_update_confidence_from_feedback(
            agent_id=test_agent.id,
            days=1
        )

        assert new_confidence is not None
        # Should increase because mostly positive feedback
        assert new_confidence > test_agent.confidence_score

        # Cleanup
        db.query(AgentFeedback).filter(AgentFeedback.agent_id == test_agent.id).delete()
        db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
