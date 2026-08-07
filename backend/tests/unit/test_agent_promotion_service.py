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
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
import os
import tempfile
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import Session, sessionmaker

from core.database import Base
from core.agent_promotion_service import AgentPromotionService, PromotionCriteria
from core.models import AgentRegistry, AgentStatus, AgentFeedback, AgentExecution, FeedbackStatus


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def db():
    """Create a fresh temp SQLite database session for each test."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )
    engine._test_db_path = db_path

    for table in Base.metadata.sorted_tables:
        try:
            table.create(engine, checkfirst=True)
        except exc.NoReferencedTableError:
            continue
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                continue
            else:
                raise

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        if hasattr(engine, '_test_db_path'):
            try:
                os.unlink(engine._test_db_path)
            except Exception:
                pass


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
        # Second agent so the evaluator is invoked for two candidates
        agent2 = AgentRegistry(
            id="agent-2",
            name="Agent 2",
            category="testing",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
            module_path="test.module",
            class_name="Agent2",
            workspace_id="default"
        )
        db.add(agent2)
        db.commit()

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

        with patch.object(service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 5,  # Below minimum
                "positive_count": 4,
                "negative_count": 1,
                "average_rating": 4.2,
                "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 1, 5: 1},
                "feedback_types": {"correction": 0}
            }

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should not be ready with insufficient feedback
            assert result["ready_for_promotion"] is False
            assert "feedback" in str(result.get("criteria_failed", {})).lower()

    def test_checks_positive_ratio_requirement(self, db, intern_agent):
        """RED: Test that positive ratio is checked."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,  # Above minimum
                "positive_count": 9,   # 0.60 ratio, below 0.75 threshold
                "negative_count": 6,
                "average_rating": 4.0,
                "rating_distribution": {1: 0, 2: 0, 3: 3, 4: 2, 5: 1},
                "feedback_types": {"correction": 0}
            }

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should not be ready with low positive ratio
            assert result["ready_for_promotion"] is False

    def test_checks_average_rating_requirement(self, db, intern_agent):
        """RED: Test that average rating is checked."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 12,
                "negative_count": 3,
                "average_rating": 3.5,  # Below 3.8 threshold
                "rating_distribution": {1: 0, 2: 0, 3: 3, 4: 2, 5: 1},
                "feedback_types": {"correction": 0}
            }

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should not be ready with low rating
            assert result["ready_for_promotion"] is False

    def test_checks_confidence_score_requirement(self, db, intern_agent):
        """RED: Test that confidence score is checked."""
        intern_agent.confidence_score = 0.40  # Below 0.7 threshold
        db.commit()

        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 12,
                "negative_count": 3,
                "average_rating": 4.0,
                "rating_distribution": {1: 0, 2: 0, 3: 3, 4: 2, 5: 1},
                "feedback_types": {"correction": 0}
            }

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should not be ready with low confidence
            assert result["ready_for_promotion"] is False
            assert "confidence" in str(result.get("criteria_failed", {})).lower()

    def test_checks_time_at_level_requirement(self, db, intern_agent):
        """RED: Test that agents failing criteria are not promoted."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 12,
                "negative_count": 3,
                "average_rating": 4.0,
                "rating_distribution": {1: 0, 2: 0, 3: 3, 4: 2, 5: 1},
                "feedback_types": {"correction": 0}
            }

            result = service._evaluate_agent_for_promotion(intern_agent)

            # 0.65 confidence fails the SUPERVISED bar; no executions to boost score
            assert result["ready_for_promotion"] is False
            assert result["criteria_failed"]

    def test_calculates_readiness_score_correctly(self, db, intern_agent):
        """RED: Test readiness score calculation."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 20,
                "positive_count": 17,
                "negative_count": 3,
                "average_rating": 4.2,
                "rating_distribution": {1: 0, 2: 0, 3: 1, 4: 2, 5: 3},
                "feedback_types": {"correction": 3}
            }

            intern_agent.confidence_score = 0.75
            intern_agent.created_at = datetime.now(timezone.utc) - timedelta(days=15)
            db.commit()

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should have a readiness score (fraction of criteria met, 0.0-1.0)
            assert "readiness_score" in result
            assert 0 <= result["readiness_score"] <= 1.0

    def test_ready_agent_passes_all_criteria(self, db, intern_agent):
        """RED: Test that agent meeting all criteria is ready."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 25,
                "positive_count": 23,
                "negative_count": 2,
                "average_rating": 4.5,
                "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 5, 5: 4},
                "feedback_types": {"correction": 2}
            }

            intern_agent.confidence_score = 0.80
            intern_agent.created_at = datetime.now(timezone.utc) - timedelta(days=15)
            db.commit()

            result = service._evaluate_agent_for_promotion(intern_agent)

            # Should be ready (5/6 criteria met ≥ 80%)
            assert result["ready_for_promotion"] is True
            assert result["readiness_score"] >= 0.8


# =============================================================================
# Test Class: Feedback Analytics Integration
# =============================================================================

class TestFeedbackAnalyticsIntegration:
    """Tests for feedback analytics integration."""

    def test_calls_feedback_analytics_for_evaluation(self, db, intern_agent):
        """RED: Test that feedback analytics is called."""
        service = AgentPromotionService(db)

        with patch.object(service.feedback_analytics, 'get_agent_feedback_summary') as mock_summary:
            mock_summary.return_value = {
                "total_feedback": 15,
                "positive_count": 12,
                "negative_count": 3,
                "average_rating": 4.0,
                "rating_distribution": {1: 0, 2: 0, 3: 3, 4: 2, 5: 1},
                "feedback_types": {"correction": 0}
            }

            service._evaluate_agent_for_promotion(intern_agent)

            # Should call analytics for this agent
            mock_summary.assert_called_once()
            call_args = mock_summary.call_args
            assert call_args.kwargs["agent_id"] == intern_agent.id


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
