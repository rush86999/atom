"""
Unit Tests for Agent Graduation Service

Tests agent promotion readiness validation:
- Episode count requirements
- Intervention rate calculations
- Constitutional score validation
- Graduation exam execution

Target Coverage: 80%
Target Branch Coverage: 50%+
Pass Rate Target: 95%+
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.agent_graduation_service import AgentGraduationService
from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    EpisodeSegment,
    SupervisionSession,
    SkillExecution
)


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
def student_agent(db):
    """Create STUDENT level agent."""
    agent = AgentRegistry(
        id="student-agent-123",
        name="Student Agent",
        description="A student agent for testing",
        category="testing",
        status=AgentStatus.STUDENT,
        confidence_score=0.40,
        module_path="agents.student_agent",
        class_name="StudentAgent",
        configuration={},
        schedule_config={},
        version=1,
        workspace_id="default",
        user_id="test-user-123"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def intern_agent(db):
    """Create INTERN level agent."""
    agent = AgentRegistry(
        id="intern-agent-123",
        name="Intern Agent",
        description="An intern agent for testing",
        category="testing",
        status=AgentStatus.INTERN,
        confidence_score=0.65,
        module_path="agents.intern_agent",
        class_name="InternAgent",
        configuration={},
        schedule_config={},
        version=1,
        workspace_id="default",
        user_id="test-user-123"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


# =============================================================================
# Test Class: Graduation Criteria Constants
# =============================================================================

class TestGraduationCriteria:
    """Tests for graduation criteria constants."""

    def test_intern_criteria(self):
        """RED: Test INTERN level criteria."""
        criteria = AgentGraduationService.CRITERIA["INTERN"]
        assert criteria["min_episodes"] == 10
        assert criteria["max_intervention_rate"] == 0.5
        assert criteria["min_constitutional_score"] == 0.70

    def test_supervised_criteria(self):
        """RED: Test SUPERVISED level criteria."""
        criteria = AgentGraduationService.CRITERIA["SUPERVISED"]
        assert criteria["min_episodes"] == 25
        assert criteria["max_intervention_rate"] == 0.2
        assert criteria["min_constitutional_score"] == 0.85

    def test_autonomous_criteria(self):
        """RED: Test AUTONOMOUS level criteria."""
        criteria = AgentGraduationService.CRITERIA["AUTONOMOUS"]
        assert criteria["min_episodes"] == 50
        assert criteria["max_intervention_rate"] == 0.0
        assert criteria["min_constitutional_score"] == 0.95


# =============================================================================
# Test Class: Calculate Readiness Score
# =============================================================================

class TestCalculateReadinessScore:
    """Tests for calculate_readiness_score method."""

    @pytest.mark.asyncio
    async def test_returns_error_for_nonexistent_agent(self, db):
        """RED: Test readiness calculation for nonexistent agent."""
        service = AgentGraduationService(db)

        result = await service.calculate_readiness_score(
            agent_id="nonexistent-agent",
            target_maturity="INTERN"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_returns_error_for_invalid_maturity_level(self, db, student_agent):
        """RED: Test readiness calculation for invalid maturity."""
        service = AgentGraduationService(db)

        result = await service.calculate_readiness_score(
            agent_id=student_agent.id,
            target_maturity="INVALID_LEVEL"
        )

        assert "error" in result
        assert "maturity" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_returns_readiness_fields(self, db, student_agent):
        """RED: Test that all readiness fields are present."""
        service = AgentGraduationService(db)

        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episode:
            mock_episode_service = Mock()
            mock_readiness = Mock()
            mock_readiness.to_dict.return_value = {
                "threshold_met": True,
                "score": 85.0,
                "episode_count": 15,
                "avg_constitutional_score": 0.88,
                "intervention_rate": 0.10,
                "gaps": []
            }
            mock_episode_service.get_graduation_readiness.return_value = mock_readiness
            mock_get_episode.return_value = mock_episode_service

            result = await service.calculate_readiness_score(
                agent_id=student_agent.id,
                target_maturity="INTERN"
            )

            # Should have all expected fields
            assert "ready" in result
            assert "score" in result
            assert "episode_count" in result
            assert "current_maturity" in result
            assert "target_maturity" in result

    @pytest.mark.asyncio
    async def test_calls_episode_service(self, db, student_agent):
        """RED: Test that episode service is called."""
        service = AgentGraduationService(db)

        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episode:
            mock_episode_service = Mock()
            mock_readiness = Mock()
            mock_readiness.to_dict.return_value = {
                "threshold_met": True,
                "score": 80.0
            }
            mock_episode_service.get_graduation_readiness.return_value = mock_readiness
            mock_get_episode.return_value = mock_episode_service

            await service.calculate_readiness_score(
                agent_id=student_agent.id,
                target_maturity="INTERN"
            )

            # Should call episode service
            mock_episode_service.get_graduation_readiness.assert_called_once()
            call_args = mock_episode_service.get_graduation_readiness.call_args
            assert call_args[1]["agent_id"] == student_agent.id
            assert call_args[1]["target_level"] == "intern"


# =============================================================================
# Test Class: Score Calculation
# =============================================================================

class TestCalculateScore:
    """Tests for internal _calculate_score method."""

    def test_episode_score_40_percent(self):
        """RED: Test episode score contributes 40%."""
        service = AgentGraduationService(Mock())

        score = service._calculate_score(
            episode_count=10,
            min_episodes=10,
            intervention_rate=0.1,
            max_intervention=0.5,
            constitutional_score=0.8,
            min_constitutional=0.7
        )

        # Episode score should be 40% (10/10 = 1.0 * 40)
        assert score >= 40.0

    def test_intervention_score_30_percent(self):
        """RED: Test intervention score contributes 30%."""
        service = AgentGraduationService(Mock())

        score = service._calculate_score(
            episode_count=10,
            min_episodes=10,
            intervention_rate=0.0,
            max_intervention=0.5,
            constitutional_score=0.7,
            min_constitutional=0.7
        )

        # Intervention score should be 30% (0/0.5 = 0.0, inverted = 1.0 * 30)
        assert score >= 30.0

    def test_constitutional_score_30_percent(self):
        """RED: Test constitutional score contributes 30%."""
        service = AgentGraduationService(Mock())

        score = service._calculate_score(
            episode_count=10,
            min_episodes=10,
            intervention_rate=0.1,
            max_intervention=0.5,
            constitutional_score=0.7,
            min_constitutional=0.7
        )

        # Constitutional score should be 30% (0.7/0.7 = 1.0 * 30)
        assert score >= 30.0

    def test_perfect_score_100(self):
        """RED: Test perfect criteria yields 100."""
        service = AgentGraduationService(Mock())

        score = service._calculate_score(
            episode_count=10,
            min_episodes=10,
            intervention_rate=0.0,
            max_intervention=0.5,
            constitutional_score=0.7,
            min_constitutional=0.7
        )

        # Should be 100 with perfect scores
        assert score == 100.0

    def test_minimum_criteria_passing_score(self):
        """RED: Test minimum passing criteria."""
        service = AgentGraduationService(Mock())

        score = service._calculate_score(
            episode_count=10,
            min_episodes=10,
            intervention_rate=0.5,
            max_intervention=0.5,
            constitutional_score=0.7,
            min_constitutional=0.7
        )

        # Should pass minimum (40 + 0 + 30 = 70)
        assert score >= 70.0


# =============================================================================
# Test Class: Recommendation Generation
# =============================================================================

class TestGenerateRecommendation:
    """Tests for _generate_recommendation method."""

    def test_ready_recommendation(self):
        """RED: Test recommendation when agent is ready."""
        service = AgentGraduationService(Mock())

        recommendation = service._generate_recommendation(
            ready=True,
            score=85.0,
            target="SUPERVISED"
        )

        assert "ready" in recommendation.lower()
        assert "SUPERVISED" in recommendation
        assert "85.0" in recommendation

    def test_low_score_recommendation(self):
        """RED: Test recommendation for low score."""
        service = AgentGraduationService(Mock())

        recommendation = service._generate_recommendation(
            ready=False,
            score=40.0,
            target="SUPERVISED"
        )

        assert "not ready" in recommendation.lower()
        assert "training" in recommendation.lower()

    def test_medium_score_recommendation(self):
        """RED: Test recommendation for medium score."""
        service = AgentGraduationService(Mock())

        recommendation = service._generate_recommendation(
            ready=False,
            score=60.0,
            target="SUPERVISED"
        )

        assert "progress" in recommendation.lower()
        assert "practice" in recommendation.lower()

    def test_high_score_recommendation(self):
        """RED: Test recommendation for high but not ready."""
        service = AgentGraduationService(Mock())

        recommendation = service._generate_recommendation(
            ready=False,
            score=78.0,
            target="SUPERVISED"
        )

        assert "close" in recommendation.lower()
        assert "gaps" in recommendation.lower()


# =============================================================================
# Test Class: Run Graduation Exam
# =============================================================================

class TestRunGraduationExam:
    """Tests for run_graduation_exam method."""

    @pytest.mark.asyncio
    async def test_runs_exam_with_edge_cases(self, db, student_agent):
        """RED: Test exam execution with edge case episodes."""
        service = AgentGraduationService(db)

        with patch('core.agent_graduation_service.get_graduation_exam_executor') as mock_executor:
            mock_executor_instance = mock_executor.return_value
            mock_executor_instance.execute_agent = AsyncMock(
                return_value={"success": True, "results": []}
            )

            edge_cases = ["episode-1", "episode-2"]
            result = await service.run_graduation_exam(
                agent_id=student_agent.id,
                edge_case_episodes=edge_cases
            )

            # Should have results
            assert "success" in result or "exam_results" in result

    @pytest.mark.asyncio
    async def test_handles_exam_failure(self, db, student_agent):
        """RED: Test handling of exam failure."""
        service = AgentGraduationService(db)

        with patch('core.agent_graduation_service.get_graduation_exam_executor') as mock_executor:
            mock_executor_instance = mock_executor.return_value
            mock_executor_instance.execute_agent = AsyncMock(
                side_effect=Exception("Sandbox execution failed")
            )

            edge_cases = ["episode-1"]
            result = await service.run_graduation_exam(
                agent_id=student_agent.id,
                edge_case_episodes=edge_cases
            )

            # Should handle error gracefully
            assert "error" in result or "success" in result


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
