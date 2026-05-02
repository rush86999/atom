"""
Unit Tests for Agent Promotion Service

Tests promotion readiness analysis:
- Feedback pattern analysis
- Performance metrics evaluation
- Confidence score validation
- Time at maturity level checks

Target Coverage: 80%
Target Branch Coverage: 50%+
Pass Rate Target: 95%+
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from core.agent_promotion_service import AgentPromotionService, PromotionCriteria
from core.models import AgentRegistry, AgentStatus, AgentFeedback, AgentExecution, FeedbackStatus


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def db():
    """Create database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def intern_agent(db):
    """Create INTERN level agent."""
    agent = AgentRegistry(
        id="intern-agent-123",
        name="Intern Agent",
        description="An intern agent testing",
        category="testing",
        status=AgentStatus.INTERN,
        confidence_score=0.65,
        module_path="agents.intern_agent",
        class_name="InternAgent",
        configuration={},
        schedule_config={},
        version=1,
        workspace_id="default",
        user_id="test-user-123",
        created_at=datetime.now(timezone.utc) - timedelta(days=10)
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def supervised_agent(db):
    """Create SUPERVISED level agent."""
    agent = AgentRegistry(
        id="supervised-agent-123",
        name="Supervised Agent",
        description="A supervised agent for testing",
        category="testing",
        status=AgentStatus.SUPERVISED,
        confidence_score=0.78,
        module_path="agents.supervised_agent",
        class_name="SupervisedAgent",
        configuration={},
        schedule_config={},
        version=1,
        workspace_id="default",
        user_id="test-user-123",
        created_at=datetime.now(timezone.utc) - timedelta(days=20)
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


# =============================================================================
# Test Class: Promotion Criteria Constants
# =============================================================================

class TestPromotionCriteria:
    """Tests for PromotionCriteria constants."""

    def test_min_feedback_count(self):
        """RED: Test minimum feedback count threshold."""
        assert PromotionCriteria.MIN_FEEDBACK_COUNT == 10

    def test_positive_ratio_thresholds(self):
        """RED: Test positive ratio thresholds for each level."""
        assert PromotionCriteria.INTERN_TO_SUPERVISED_POSITIVE_RATIO == 0.75
        assert PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_POSITIVE_RATIO == 0.90

    def test_avg_rating_thresholds(self):
        """RED: Test average rating thresholds."""
        assert PromotionCriteria.INTERN_TO_SUPERVISED_AVG_RATING == 3.8
        assert PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_AVG_RATING == 4.5

    def test_correction_thresholds(self):
        """RED: Test correction count thresholds."""
        assert PromotionCriteria.INTERN_TO_SUPERVISED_MAX_CORRECTIONS == 5
        assert PromotionCriteria.SUPERVISED_TO_AUTONOMOUS_MAX_CORRECTIONS == 2

    def test_confidence_thresholds(self):
        """RED: Test confidence score thresholds."""
        assert PromotionCriteria.INTERN_MIN_CONFIDENCE == 0.5
        assert PromotionCriteria.SUPERVISED_MIN_CONFIDENCE == 0.7
        assert PromotionCriteria.AUTONOMOUS_MIN_CONFIDENCE == 0.9

    def test_time_requirements(self):
        """RED: Test minimum days at each level."""
        assert PromotionCriteria.MIN_DAYS_AT_LEVEL["INTERN"] == 7
        assert PromotionCriteria.MIN_DAYS_AT_LEVEL["SUPERVISED"] == 14


# =============================================================================
# Test Class: Get Promotion Suggestions
# =============================================================================

class TestGetPromotionSuggestions:
    """Tests for get_promotion_suggestions method."""

    def test_returns_empty_list_when_no_promotable_agents(self, db):
        """RED: Test when no agents are ready for promotion."""
        service = AgentPromotionService(db)

        with patch.object(service, '_evaluate_agent_for_promotion') as mock_eval:
            mock_eval.return_value = {
                "ready_for_promotion": False,
                "readiness_score": 50.0
            }

            suggestions = service.get_promotion_suggestions()

            assert suggestions == []
            assert isinstance(suggestions, list)

    def test_returns_promotable_agents_sorted_by_score(self, db, intern_agent):
        """RED: Test that promotable agents are sorted by readiness score."""
        service = AgentPromotionService(db)

        with patch.object(service, '_evaluate_agent_for_promotion') as mock_eval:
            # Mock two agents with different scores
            mock_eval.side_effect = [
                {"ready_for_promotion": True, "readiness_score": 85.0, "agent_id": "agent-1"},
                {"ready_for_promotion": True, "readiness_score": 92.0, "agent_id": "agent-2"}
            ]

            suggestions = service.get_promotion_suggestions(limit=10)

            assert len(suggestions) == 2
            # Should be sorted by score descending
            assert suggestions[0]["readiness_score"] >= suggestions[1]["readiness_score"]

    def test_respects_limit_parameter(self, db, intern_agent):
        """RED: Test that limit parameter is respected."""
        service = AgentPromotionService(db)

        with patch.object(service, '_evaluate_agent_for_promotion') as mock_eval:
            mock_eval.return_value = {
                "ready_for_promotion": True,
                "readiness_score": 80.0,
                "agent_id": "test-agent"
            }

            suggestions = service.get_promotion_suggestions(limit=5)

            assert len(suggestions) <= 5


# =============================================================================
# Test Class: Is Agent Ready for Promotion
# =============================================================================

class TestIsAgentReadyForPromotion:
    """Tests for is_agent_ready_for_promotion method."""

    def test_returns_not_found_for_missing_agent(self, db):
        """RED: Test when agent doesn't exist."""
        service = AgentPromotionService(db)

        result = service.is_agent_ready_for_promotion("nonexistent-agent-id")

        assert result["ready"] is False
        assert "not found" in result["reason"].lower()

    def test_auto_detects_target_status_for_intern(self, db, intern_agent):
        """RED: Test auto-detection of target status from INTERN."""
        service = AgentPromotionService(db)

        with patch.object(service, '_evaluate_agent_for_promotion') as mock_eval:
            mock_eval.return_value = {
                "ready_for_promotion": True,
                "readiness_score": 85.0,
                "target_status": "SUPERVISED"
            }

            result = service.is_agent_ready_for_promotion(intern_agent.id)

            assert mock_eval.called
            call_args = mock_eval.call_args
            assert call_args[0][0] == intern_agent
            assert call_args[0][1] == "SUPERVISED"

    def test_auto_detects_target_status_for_supervised(self, db, supervised_agent):
        """RED: Test auto-detection of target status from SUPERVISED."""
        service = AgentPromotionService(db)

        with patch.object(service, '_evaluate_agent_for_promotion') as mock_eval:
            mock_eval.return_value = {
                "ready_for_promotion": True,
                "readiness_score": 92.0,
                "target_status": "AUTONOMOUS"
            }

            result = service.is_agent_ready_for_promotion(supervised_agent.id)

            assert mock_eval.called
            call_args = mock_eval.call_args
            assert call_args[0][1] == "AUTONOMOUS"

    def test_uses_explicit_target_status_if_provided(self, db, intern_agent):
        """RED: Test explicit target status parameter."""
        service = AgentPromotionService(db)

        with patch.object(service, '_evaluate_agent_for_promotion') as mock_eval:
            mock_eval.return_value = {
                "ready_for_promotion": False,
                "readiness_score": 70.0,
                "target_status": "SUPERVISED"
            }

            result = service.is_agent_ready_for_promotion(
                intern_agent.id,
                target_status="AUTONOMOUS"
            )

            # Should use explicit target
            call_args = mock_eval.call_args
            assert call_args[0][1] == "AUTONOMOUS"


# =============================================================================
# Test Class: Evaluation Logic
# =============================================================================

class TestEvaluateAgentForPromotion:
    """Tests for internal evaluation logic."""

    def test_checks_feedback_count_requirement(self, db, intern_agent):
        """RED: Test that feedback count is checked."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_count": 5,  # Below minimum
                "positive_ratio": 0.80,
                "average_rating": 4.2
            }

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should not be ready with insufficient feedback
            assert result["ready_for_promotion"] is False
            assert "feedback" in str(result.get("gaps", [])).lower()

    def test_checks_positive_ratio_requirement(self, db, intern_agent):
        """RED: Test that positive ratio is checked."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_count": 15,  # Above minimum
                "positive_ratio": 0.60,  # Below 0.75 threshold
                "average_rating": 4.0
            }

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should not be ready with low positive ratio
            assert result["ready_for_promotion"] is False

    def test_checks_average_rating_requirement(self, db, intern_agent):
        """RED: Test that average rating is checked."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_count": 15,
                "positive_ratio": 0.80,
                "average_rating": 3.5  # Below 3.8 threshold
            }

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should not be ready with low rating
            assert result["ready_for_promotion"] is False

    def test_checks_confidence_score_requirement(self, db, intern_agent):
        """RED: Test that confidence score is checked."""
        intern_agent.confidence_score = 0.40  # Below 0.5 threshold
        db.commit()

        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_count": 15,
                "positive_ratio": 0.80,
                "average_rating": 4.0
            }

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should not be ready with low confidence
            assert result["ready_for_promotion"] is False
            assert "confidence" in str(result.get("gaps", [])).lower()

    def test_checks_time_at_level_requirement(self, db, intern_agent):
        """RED: Test that time at current level is checked."""
        # Agent created 2 days ago (below 7 day minimum)
        intern_agent.created_at = datetime.now(timezone.utc) - timedelta(days=2)
        db.commit()

        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_count": 15,
                "positive_ratio": 0.80,
                "average_rating": 4.0
            }

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should not be ready with insufficient time
            assert result["ready_for_promotion"] is False
            assert "days" in str(result.get("gaps", [])).lower()

    def test_calculates_readiness_score_correctly(self, db, intern_agent):
        """RED: Test readiness score calculation."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_count": 20,
                "positive_ratio": 0.85,
                "average_rating": 4.2,
                "corrections_count": 3,
                "execution_success_rate": 0.90
            }

            intern_agent.confidence_score = 0.75
            intern_agent.created_at = datetime.now(timezone.utc) - timedelta(days=15)
            db.commit()

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should have a readiness score
            assert "readiness_score" in result
            assert 0 <= result["readiness_score"] <= 100

    def test_ready_agent_passes_all_criteria(self, db, intern_agent):
        """RED: Test that agent meeting all criteria is ready."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_count": 25,
                "positive_ratio": 0.90,
                "average_rating": 4.5,
                "corrections_count": 2,
                "execution_success_rate": 0.95
            }

            intern_agent.confidence_score = 0.80
            intern_agent.created_at = datetime.now(timezone.utc) - timedelta(days=15)
            db.commit()

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should be ready
            assert result["ready_for_promotion"] is True
            assert result["readiness_score"] >= 80.0


# =============================================================================
# Test Class: Feedback Analytics Integration
# =============================================================================

class TestFeedbackAnalyticsIntegration:
    """Tests for feedback analytics integration."""

    def test_calls_feedback_analytics_for_evaluation(self, db, intern_agent):
        """RED: Test that feedback analytics is called."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_count": 15,
                "positive_ratio": 0.80,
                "average_rating": 4.0
            }

            service._evaluate_agent_for_promotion(intern_agent)

            # Should call analytics for this agent
            mock_summary.assert_called_once()
            call_args = mock_summary.call_args
            assert call_args[0][0] == intern_agent.id


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
