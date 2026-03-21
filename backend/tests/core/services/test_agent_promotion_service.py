"""
Tests for AgentPromotionService

Tests for agent promotion service including:
- Promotion criteria evaluation
- Promotion suggestions
- Promotion path tracking
- Feedback analysis integration
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.agent_promotion_service import (
    AgentPromotionService,
    PromotionCriteria,
)
from core.models import (
    AgentRegistry,
    AgentExecution,
    AgentFeedback,
    AgentStatus,
)


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    from core.models import Base
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def promotion_service(db_session):
    """Create promotion service instance."""
    return AgentPromotionService(db_session)


@pytest.fixture
def test_agent(db_session):
    """Create a test agent."""
    agent = AgentRegistry(
        id="test-agent-1",
        name="Test Agent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.75,
    )
    db_session.add(agent)
    db_session.commit()
    return agent


@pytest.fixture
def test_feedback(db_session, test_agent):
    """Create test feedback entries."""
    # Create positive feedback
    for i in range(15):
        feedback = AgentFeedback(
            id=f"feedback-{i}",
            agent_id=test_agent.id,
            user_id="test-user",
            rating=5,  # Positive
            feedback_type="thumbs_up",
            created_at=datetime.now() - timedelta(days=i),
        )
        db_session.add(feedding)

    db_session.commit()


class TestAgentPromotionServiceInit:
    """Tests for AgentPromotionService initialization."""

    def test_init_with_db(self, db_session):
        """Test service initialization with database session."""
        service = AgentPromotionService(db_session)
        assert service.db == db_session
        assert service.feedback_analytics is not None


class TestPromotionCriteria:
    """Tests for PromotionCriteria class."""

    def test_min_feedback_count(self):
        """Test minimum feedback count threshold."""
        assert PromotionCriteria.MIN_FEEDBACK_COUNT == 10

    def test_positive_ratio_thresholds(self):
        """Test positive ratio thresholds."""
        assert PromotionCriteria.INTERN_TO_SUPERVISED_POSITIVE_RATIO == 0.75
        assert PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_POSITIVE_RATIO == 0.90

    def test_avg_rating_thresholds(self):
        """Test average rating thresholds."""
        assert PromotionCriteria.INTERN_TO_SUPERVISED_AVG_RATING == 3.8
        assert PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_AVG_RATING == 4.5

    def test_correction_count_thresholds(self):
        """Test correction count thresholds."""
        assert PromotionCriteria.INTERN_TO_SUPERVISED_MAX_CORRECTIONS == 5
        assert PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_MAX_CORRECTIONS == 2

    def test_confidence_thresholds(self):
        """Test confidence score thresholds."""
        assert PromotionCriteria.INTERN_MIN_CONFIDENCE == 0.5
        assert PromotionCriteria.SUPERVISED_MIN_CONFIDENCE == 0.7
        assert PromotionCriteria.AUTONOMOUS_MIN_CONFIDENCE == 0.9

    def test_execution_success_rate_threshold(self):
        """Test execution success rate threshold."""
        assert PromotionCriteria.MIN_EXECUTION_SUCCESS_RATE == 0.85

    def test_min_days_at_level(self):
        """Test minimum days at each level."""
        assert PromotionCriteria.MIN_DAYS_AT_LEVEL["INTERN"] == 7
        assert PromotionCriteria.MIN_DAYS_AT_LEVEL["SUPERVISED"] == 14


class TestGetPromotionSuggestions:
    """Tests for get_promotion_suggestions method."""

    def test_get_promotion_suggestions_empty_db(self, promotion_service):
        """Test getting suggestions with no agents."""
        suggestions = promotion_service.get_promotion_suggestions()
        assert suggestions == []

    def test_get_promotion_suggestions_with_limit(self, promotion_service, db_session, test_agent, test_feedback):
        """Test getting suggestions with limit."""
        # Add feedback analytics mock
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 14,
                "negative_count": 1,
                "average_rating": 4.8,
                "feedback_types": {"thumbs_up": 14, "correction": 0}
            }

            suggestions = promotion_service.get_promotion_suggestions(limit=5)

            assert len(suggestions) <= 5

    def test_get_promotion_suggestions_sorting(self, promotion_service, db_session, test_agent):
        """Test that suggestions are sorted by readiness score."""
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 15,
                "negative_count": 0,
                "average_rating": 5.0,
                "feedback_types": {"thumbs_up": 15, "correction": 0}
            }

            suggestions = promotion_service.get_promotion_suggestions()

            if len(suggestions) > 1:
                # Check sorted by readiness_score descending
                for i in range(len(suggestions) - 1):
                    assert suggestions[i]["readiness_score"] >= suggestions[i + 1]["readiness_score"]


class TestIsAgentReadyForPromotion:
    """Tests for is_agent_ready_for_promotion method."""

    def test_agent_ready_agent_not_found(self, promotion_service):
        """Test readiness check for non-existent agent."""
        result = promotion_service.is_agent_ready_for_promotion("non-existent-agent")
        assert result["ready"] is False
        assert "not found" in result["reason"].lower()

    def test_agent_ready_no_feedback(self, promotion_service, test_agent):
        """Test readiness check with no feedback."""
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.side_effect = ValueError("No feedback")

            result = promotion_service.is_agent_ready_for_promotion(test_agent.id)

            assert result["ready"] is False
            assert "feedback data" in result["reason"].lower()

    def test_agent_ready_auto_detect_target(self, promotion_service, test_agent):
        """Test auto-detection of target status."""
        # Agent is INTERN, should target SUPERVISED
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 12,
                "negative_count": 3,
                "average_rating": 4.0,
                "feedback_types": {"thumbs_up": 12, "correction": 2}
            }

            result = promotion_service.is_agent_ready_for_promotion(test_agent.id)

            assert result["target_status"] == "SUPERVISED"

    def test_agent_ready_already_autonomous(self, promotion_service, db_session):
        """Test readiness check for already autonomous agent."""
        agent = AgentRegistry(
            id="autonomous-agent",
            name="Autonomous Agent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        result = promotion_service.is_agent_ready_for_promotion(agent.id)

        assert result["ready"] is False
        assert "already" in result["reason"].lower()


class TestEvaluateAgentForPromotion:
    """Tests for _evaluate_agent_for_promotion method."""

    def test_evaluate_agent_meeting_all_criteria(self, promotion_service, test_agent):
        """Test evaluation of agent meeting all criteria."""
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 20,
                "positive_count": 19,
                "negative_count": 1,
                "average_rating": 4.9,
                "feedback_types": {"thumbs_up": 19, "correction": 1}
            }

            # Add successful executions
            execution = AgentExecution(
                id="exec-1",
                agent_id=test_agent.id,
                status="completed",
                started_at=datetime.now() - timedelta(days=1),
            )
            promotion_service.db.add(execution)
            promotion_service.db.commit()

            result = promotion_service._evaluate_agent_for_promotion(test_agent)

            assert result["agent_id"] == test_agent.id
            assert "criteria_met" in result
            assert "criteria_failed" in result
            assert result["readiness_score"] >= 0

    def test_evaluate_agent_insufficient_feedback(self, promotion_service, test_agent):
        """Test evaluation of agent with insufficient feedback."""
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 5,  # Below threshold
                "positive_count": 4,
                "negative_count": 1,
                "average_rating": 4.0,
                "feedback_types": {"thumbs_up": 4, "correction": 1}
            }

            result = promotion_service._evaluate_agent_for_promotion(test_agent)

            assert "feedback_count" in result["criteria_failed"]
            assert result["ready_for_promotion"] is False

    def test_evaluate_agent_low_positive_ratio(self, promotion_service, test_agent):
        """Test evaluation of agent with low positive ratio."""
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 8,  # Below 75%
                "negative_count": 7,
                "average_rating": 3.5,
                "feedback_types": {"thumbs_up": 8, "correction": 5}
            }

            result = promotion_service._evaluate_agent_for_promotion(test_agent)

            assert "positive_ratio" in result["criteria_failed"]

    def test_evaluate_agent_too_many_corrections(self, promotion_service, test_agent):
        """Test evaluation of agent with too many corrections."""
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 10,
                "negative_count": 5,
                "average_rating": 4.0,
                "feedback_types": {"thumbs_up": 10, "correction": 6}  # Above 5
            }

            result = promotion_service._evaluate_agent_for_promotion(test_agent)

            assert "correction_count" in result["criteria_failed"]

    def test_evaluate_agent_readiness_score_calculation(self, promotion_service, test_agent):
        """Test readiness score calculation."""
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 12,
                "negative_count": 3,
                "average_rating": 4.2,
                "feedback_types": {"thumbs_up": 12, "correction": 3}
            }

            result = promotion_service._evaluate_agent_for_promotion(test_agent)

            # Readiness score should be between 0 and 1
            assert 0 <= result["readiness_score"] <= 1

    def test_evaluate_agent_already_at_max_level(self, promotion_service, db_session):
        """Test evaluation of agent already at max level."""
        agent = AgentRegistry(
            id="max-level-agent",
            name="Max Level Agent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95,
        )
        db_session.add(agent)
        db_session.commit()

        result = promotion_service._evaluate_agent_for_promotion(agent)

        assert result["ready_for_promotion"] is False
        assert result["target_status"] is None
        assert "already at" in result["reason"].lower()


class TestGetPromotionPath:
    """Tests for get_promotion_path method."""

    def test_get_promotion_path_student_agent(self, promotion_service, db_session):
        """Test promotion path for STUDENT agent."""
        agent = AgentRegistry(
            id="student-agent",
            name="Student Agent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4,
        )
        db_session.add(agent)
        db_session.commit()

        result = promotion_service.get_promotion_path(agent.id)

        assert result["current_status"] == "STUDENT"
        assert len(result["promotion_path"]) == 3  # STUDENT->INTERN, INTERN->SUPERVISED, SUPERVISED->AUTONOMOUS

    def test_get_promotion_path_intern_agent(self, promotion_service, test_agent):
        """Test promotion path for INTERN agent."""
        with patch.object(promotion_service, '_evaluate_agent_for_promotion') as mock_eval:
            mock_eval.return_value = {
                "agent_id": test_agent.id,
                "agent_name": test_agent.name,
                "current_status": "INTERN",
                "target_status": "SUPERVISED",
                "ready_for_promotion": False,
                "readiness_score": 0.6,
                "reason": "Not ready yet",
                "criteria_met": {},
                "criteria_failed": {}
            }

            result = promotion_service.get_promotion_path(test_agent.id)

            assert result["current_status"] == "INTERN"
            assert len(result["promotion_path"]) == 2  # INTERN->SUPERVISED, SUPERVISED->AUTONOMOUS

    def test_get_promotion_path_agent_not_found(self, promotion_service):
        """Test promotion path for non-existent agent."""
        result = promotion_service.get_promotion_path("non-existent-agent")

        assert "error" in result

    def test_get_promotion_path_requirements(self, promotion_service, test_agent):
        """Test that promotion path includes requirements."""
        with patch.object(promotion_service, '_evaluate_agent_for_promotion') as mock_eval:
            mock_eval.return_value = {
                "agent_id": test_agent.id,
                "agent_name": test_agent.name,
                "current_status": "INTERN",
                "target_status": "SUPERVISED",
                "ready_for_promotion": False,
                "readiness_score": 0.6,
                "reason": "Not ready yet",
                "criteria_met": {},
                "criteria_failed": {}
            }

            result = promotion_service.get_promotion_path(test_agent.id)

            # Check that path includes requirements
            for path_item in result["promotion_path"]:
                if "requirements" in path_item:
                    assert isinstance(path_item["requirements"], list)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_zero_executions(self, promotion_service, test_agent):
        """Test agent with zero executions."""
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 12,
                "negative_count": 3,
                "average_rating": 4.0,
                "feedback_types": {"thumbs_up": 12, "correction": 2}
            }

            result = promotion_service._evaluate_agent_for_promotion(test_agent)

            # Should still compute readiness score
            assert "readiness_score" in result

    def test_average_rating_none(self, promotion_service, test_agent):
        """Test handling of None average rating."""
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 12,
                "negative_count": 3,
                "average_rating": None,  # No rating
                "feedback_types": {"thumbs_up": 12, "correction": 2}
            }

            result = promotion_service._evaluate_agent_for_promotion(test_agent)

            # Should not crash
            assert "readiness_score" in result

    def test_mixed_execution_status(self, promotion_service, test_agent, db_session):
        """Test agent with mixed execution results."""
        with patch.object(promotion_service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 12,
                "negative_count": 3,
                "average_rating": 4.0,
                "feedback_types": {"thumbs_up": 12, "correction": 2}
            }

            # Add mixed executions
            for i in range(10):
                execution = AgentExecution(
                    id=f"exec-{i}",
                    agent_id=test_agent.id,
                    status="completed" if i < 8 else "failed",
                    started_at=datetime.now() - timedelta(days=i),
                )
                db_session.add(execution)
            db_session.commit()

            result = promotion_service._evaluate_agent_for_promotion(test_agent)

            # 80% success rate should meet threshold
            success_rate = 8 / 10
            if success_rate >= 0.85:
                assert "execution_success_rate" in result.get("criteria_met", {})
            else:
                assert "execution_success_rate" in result.get("criteria_failed", {})


# Import for patch
from unittest.mock import patch
