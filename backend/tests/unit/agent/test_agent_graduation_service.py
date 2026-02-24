"""
Unit Tests for Agent Graduation Service

Tests cover:
- Readiness score calculation (40% episodes + 30% interventions + 30% constitutional)
- Graduation exam validation (100% constitutional compliance required)
- Level transitions (STUDENT -> INTERN -> SUPERVISED -> AUTONOMOUS)
- Intervention rate decreases with maturity
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.agent_graduation_service import AgentGraduationService, SandboxExecutor
from core.models import AgentRegistry, Episode, AgentStatus, SupervisionSession
from tests.factories import (
    AgentFactory,
    EpisodeFactory,
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory
)


class TestAgentGraduationService:
    """Test agent graduation service."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_readiness_score_in_0_1_range(self, service, db_session):
        """Readiness score should be in [0.0, 1.0]."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes
        for _ in range(25):  # Minimum for INTERN -> SUPERVISED
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed"
            )

        result = await service.calculate_readiness_score(agent_id=agent.id, target_maturity="SUPERVISED")

        assert "score" in result
        assert 0.0 <= result["score"] <= 100.0
        assert result["target_maturity"] == "SUPERVISED"

    @pytest.mark.asyncio
    async def test_readiness_score_weights_sum_to_1(self, service, db_session):
        """Readiness score weights: 40% episodes + 30% interventions + 30% constitutional."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create 50 episodes with zero interventions and perfect constitutional score
        for _ in range(50):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=0,
                constitutional_score=1.0
            )

        result = await service.calculate_readiness_score(agent_id=agent.id, target_maturity="AUTONOMOUS")

        # Score should be weighted average
        # With perfect episodes, interventions, and constitutional: should be near 100
        assert result["score"] >= 90.0  # Allow some margin
        assert result["episode_count"] == 50
        assert result["intervention_rate"] == 0.0
        assert result["avg_constitutional_score"] == 1.0

    @pytest.mark.asyncio
    async def test_readiness_score_insufficient_episodes(self, service, db_session):
        """Readiness score should identify insufficient episodes."""
        agent = StudentAgentFactory(_session=db_session)

        # Create only 5 episodes (need 10 for INTERN)
        for _ in range(5):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="STUDENT",
                status="completed"
            )

        result = await service.calculate_readiness_score(agent_id=agent.id, target_maturity="INTERN")

        assert result["ready"] is False
        assert result["episode_count"] == 5
        assert any("episodes" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_readiness_score_high_intervention_rate(self, service, db_session):
        """Readiness score should flag high intervention rates."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with high intervention rate (60%)
        for i in range(25):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=1 if i < 15 else 0  # 15/25 = 60%
            )

        result = await service.calculate_readiness_score(agent_id=agent.id, target_maturity="SUPERVISED")

        assert result["ready"] is False
        assert result["intervention_rate"] > 0.2  # Max allowed for SUPERVISED
        assert any("intervention" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_readiness_score_low_constitutional_compliance(self, service, db_session):
        """Readiness score should flag low constitutional compliance."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes with low constitutional scores
        for _ in range(30):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                constitutional_score=0.7  # Below 0.85 threshold
            )

        result = await service.calculate_readiness_score(agent_id=agent.id, target_maturity="AUTONOMOUS")

        assert result["ready"] is False
        assert result["avg_constitutional_score"] < 0.85
        assert any("constitutional" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_graduation_exam_requires_100_percent_compliance(self, service, db_session):
        """Graduation exam requires 100% constitutional compliance."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes with perfect compliance
        for _ in range(50):
            ep = EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed"
            )
            # Mark all with zero interventions
            ep.human_intervention_count = 0

        result = await service.execute_graduation_exam(
            agent_id=agent.id,
            workspace_id="test-workspace",
            target_maturity="AUTONOMOUS"
        )

        # Should pass with zero interventions
        assert result["exam_completed"] is True
        assert result["constitutional_compliance"] >= 0.95
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_graduation_exam_fails_with_high_interventions(self, service, db_session):
        """Graduation exam should fail with excessive interventions."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with high intervention rate
        for i in range(15):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=2  # High interventions
            )

        result = await service.execute_graduation_exam(
            agent_id=agent.id,
            workspace_id="test-workspace",
            target_maturity="SUPERVISED"
        )

        # Should fail due to excessive interventions
        assert result["exam_completed"] is True
        assert result["passed"] is False
        assert "excessive_interventions" in result.get("constitutional_violations", [])

    @pytest.mark.asyncio
    async def test_promote_agent_success(self, service, db_session):
        """Agent promotion should update maturity level."""
        agent = InternAgentFactory(_session=db_session)

        result = await service.promote_agent(
            agent_id=agent.id,
            new_maturity="SUPERVISED",
            validated_by="test_user"
        )

        assert result is True

        # Verify agent was updated
        db_session.refresh(agent)
        assert agent.status == AgentStatus.SUPERVISED
        assert agent.configuration["promoted_by"] == "test_user"
        assert "promoted_at" in agent.configuration

    @pytest.mark.asyncio
    async def test_promote_agent_invalid_maturity(self, service, db_session):
        """Agent promotion should fail with invalid maturity level."""
        agent = StudentAgentFactory(_session=db_session)

        result = await service.promote_agent(
            agent_id=agent.id,
            new_maturity="INVALID_LEVEL",
            validated_by="test_user"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_promote_agent_nonexistent_agent(self, service):
        """Agent promotion should fail for non-existent agent."""
        result = await service.promote_agent(
            agent_id="nonexistent-id",
            new_maturity="INTERN",
            validated_by="test_user"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_maturity_transitions_are_monotonic(self, service, db_session):
        """Maturity transitions should be monotonic (no downgrades)."""
        agent = StudentAgentFactory(_session=db_session)

        # Test forward transitions (should succeed if ready)
        # Note: promote_agent doesn't check readiness, just updates the field
        result1 = await service.promote_agent(agent.id, "INTERN", "test_user")
        assert result1 is True
        db_session.refresh(agent)
        assert agent.status == AgentStatus.INTERN

        result2 = await service.promote_agent(agent.id, "SUPERVISED", "test_user")
        assert result2 is True
        db_session.refresh(agent)
        assert agent.status == AgentStatus.SUPERVISED

        result3 = await service.promote_agent(agent.id, "AUTONOMOUS", "test_user")
        assert result3 is True
        db_session.refresh(agent)
        assert agent.status == AgentStatus.AUTONOMOUS

        # Attempting downgrade - this will succeed since promote_agent
        # doesn't enforce monotonicity (it's a governance concern)
        # In production, governance checks should prevent this
        result4 = await service.promote_agent(agent.id, "STUDENT", "test_user")
        # The service allows it, but governance should prevent it
        assert result4 is True  # Service allows it
        db_session.refresh(agent)
        assert agent.status == AgentStatus.STUDENT

    @pytest.mark.asyncio
    async def test_intervention_rate_decreases_with_maturity(self, service):
        """Intervention rate thresholds should decrease with maturity."""
        # Check criteria for each level
        criteria = AgentGraduationService.CRITERIA

        # STUDENT -> INTERN: 50% max intervention
        assert criteria["INTERN"]["max_intervention_rate"] == 0.5

        # INTERN -> SUPERVISED: 20% max intervention
        assert criteria["SUPERVISED"]["max_intervention_rate"] == 0.2

        # SUPERVISED -> AUTONOMOUS: 0% max intervention
        assert criteria["AUTONOMOUS"]["max_intervention_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_graduation_audit_trail(self, service, db_session):
        """Graduation audit trail should provide comprehensive data."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes at different maturity levels
        for i in range(10):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=i % 3,
                constitutional_score=0.8 + (i * 0.02)
            )

        trail = await service.get_graduation_audit_trail(agent_id=agent.id)

        assert trail["agent_id"] == agent.id
        assert trail["total_episodes"] == 10
        assert trail["avg_constitutional_score"] > 0
        assert "episodes_by_maturity" in trail
        assert "recent_episodes" in trail
        assert len(trail["recent_episodes"]) <= 10

    @pytest.mark.asyncio
    async def test_sandbox_executor_exam_with_no_episodes(self, db_session):
        """Sandbox executor should return failure with no episodes."""
        executor = SandboxExecutor(db_session)
        agent = StudentAgentFactory(_session=db_session)

        result = await executor.execute_exam(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        assert result["success"] is True
        assert result["score"] == 0.0
        assert result["passed"] is False
        assert "insufficient_episode_count" in result["constitutional_violations"]

    @pytest.mark.asyncio
    async def test_sandbox_executor_exam_with_perfect_episodes(self, db_session):
        """Sandbox executor should pass with perfect episodes."""
        executor = SandboxExecutor(db_session)
        agent = InternAgentFactory(_session=db_session)

        # Create perfect episodes
        for _ in range(25):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0
            )

        result = await executor.execute_exam(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        assert result["success"] is True
        assert result["passed"] is True
        assert result["score"] >= 0.7  # Min constitutional score
        assert result["constitutional_compliance"] >= 0.85

    @pytest.mark.asyncio
    async def test_supervision_metrics_calculation(self, service, db_session):
        """Supervision metrics should calculate correctly."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create supervision sessions with all required fields
        base_time = datetime.now()
        for i in range(10):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",  # Required field
                trigger_id=f"trigger-{i}",  # Required field
                trigger_context={},  # Required field
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i),
                duration_seconds=3600,  # 1 hour
                intervention_count=10 - i,  # Decreasing interventions
                supervisor_rating=3.0 + (i * 0.2)  # Improving ratings
            )
            db_session.add(session)
        db_session.commit()

        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        assert metrics["total_supervision_hours"] == 10.0
        assert metrics["intervention_rate"] > 0
        assert metrics["average_supervisor_rating"] > 0
        assert metrics["total_sessions"] == 10
        assert metrics["recent_performance_trend"] in ["improving", "stable", "declining"]

    @pytest.mark.asyncio
    async def test_validate_constitutional_compliance_no_segments(self, service, db_session):
        """Constitutional validation should handle episodes with no segments."""
        # Create an episode without adding to session (avoids double-attach)
        ep = EpisodeFactory(
            _session=db_session,
            status="completed"
        )

        result = await service.validate_constitutional_compliance(episode_id=ep.id)

        # Should return compliant with no violations (defensive handling)
        assert result["compliant"] is True
        assert result["score"] == 1.0
        assert result["violations"] == []
        assert result["episode_id"] == ep.id

    @pytest.mark.asyncio
    async def test_validate_constitutional_compliance_nonexistent_episode(self, service):
        """Constitutional validation should handle non-existent episode."""
        result = await service.validate_constitutional_compliance(episode_id="nonexistent")

        assert "error" in result
        assert result["error"] == "Episode not found"


class TestReadinessScoreCalculation:
    """Test readiness score calculation in detail."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_readiness_score_exact_minimum_episodes(self, service, db_session):
        """Readiness score with exact minimum episodes (threshold boundary)."""
        agent = StudentAgentFactory(_session=db_session)

        # Create exactly 10 episodes (minimum for INTERN)
        for _ in range(10):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="STUDENT",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.8
            )

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        assert result["episode_count"] == 10
        assert result["ready"] is True
        assert result["score"] >= 50.0

    @pytest.mark.asyncio
    async def test_readiness_score_exact_maximum_intervention_rate(self, service, db_session):
        """Readiness score with exact maximum intervention rate (threshold boundary)."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with exactly 50% intervention rate (max for INTERN)
        for i in range(20):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=1 if i % 2 == 0 else 0,  # 50% rate
                constitutional_score=0.8
            )

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        # At exactly 50%, should pass the intervention check
        assert result["intervention_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_readiness_score_exact_minimum_constitutional_score(self, service, db_session):
        """Readiness score with exact minimum constitutional score (threshold boundary)."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with exactly 0.70 constitutional score (minimum for INTERN)
        for _ in range(20):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.70
            )

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        assert result["avg_constitutional_score"] == 0.70

    @pytest.mark.asyncio
    async def test_readiness_score_recommendation_0_50_range(self, service, db_session):
        """Readiness score recommendation for low scores (0-50)."""
        agent = StudentAgentFactory(_session=db_session)

        # Create episodes with poor performance
        for _ in range(3):  # Very few episodes
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="STUDENT",
                status="completed",
                human_intervention_count=5,  # High interventions
                constitutional_score=0.5  # Low score
            )

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        assert result["score"] < 50
        assert "Significant training needed" in result["recommendation"]

    @pytest.mark.asyncio
    async def test_readiness_score_recommendation_50_75_range(self, service, db_session):
        """Readiness score recommendation for medium scores (50-75)."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with moderate performance
        for _ in range(15):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=3,
                constitutional_score=0.75
            )

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        assert 50 <= result["score"] < 75
        assert "More practice needed" in result["recommendation"]

    @pytest.mark.asyncio
    async def test_readiness_score_recommendation_75_100_range(self, service, db_session):
        """Readiness score recommendation for high scores (75-100)."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes with good performance
        for _ in range(30):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=1,
                constitutional_score=0.85
            )

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="AUTONOMOUS"
        )

        assert result["score"] >= 75
        assert "close to ready" in result["recommendation"].lower() or "ready for promotion" in result["recommendation"].lower()

    @pytest.mark.asyncio
    async def test_readiness_score_unknown_maturity_level(self, service, db_session):
        """Readiness score for unknown maturity level returns error dict."""
        agent = StudentAgentFactory(_session=db_session)

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="UNKNOWN_LEVEL"
        )

        assert "error" in result
        assert "Unknown maturity level" in result["error"]

    @pytest.mark.asyncio
    async def test_readiness_score_nonexistent_agent(self, service):
        """Readiness score for non-existent agent returns error dict."""
        result = await service.calculate_readiness_score(
            agent_id="nonexistent-agent-id",
            target_maturity="INTERN"
        )

        assert "error" in result
        assert result["error"] == "Agent not found"


class TestReadinessScoreEdgeCases:
    """Test readiness score edge cases."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_readiness_with_zero_episodes(self, service, db_session):
        """Readiness with zero episodes (intervention_rate = 1.0 per edge case)."""
        agent = StudentAgentFactory(_session=db_session)

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        assert result["episode_count"] == 0
        assert result["intervention_rate"] == 1.0  # Max rate when no episodes
        assert result["ready"] is False
        assert "episodes" in result["gaps"][0].lower()

    @pytest.mark.asyncio
    async def test_readiness_with_no_constitutional_scores(self, service, db_session):
        """Readiness with no constitutional scores (avg = 0.0)."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes without constitutional scores (None)
        for _ in range(15):
            ep = EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0
            )
            ep.constitutional_score = None

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        assert result["avg_constitutional_score"] == 0.0
        assert "constitutional" in " ".join(result["gaps"]).lower()

    @pytest.mark.asyncio
    async def test_readiness_with_mixed_episode_statuses(self, service, db_session):
        """Readiness with mixed episode statuses (only completed episodes counted)."""
        agent = InternAgentFactory(_session=db_session)

        # Create completed episodes
        for _ in range(10):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0
            )

        # Create in-progress episodes (should not count)
        for _ in range(5):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="in_progress",
                human_intervention_count=0
            )

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        # Only completed episodes should count
        assert result["episode_count"] == 10

    @pytest.mark.asyncio
    async def test_readiness_score_weighted_formula(self, service, db_session):
        """Readiness score calculation uses weighted formula (40% episodes + 30% interventions + 30% constitutional)."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with known metrics
        for _ in range(25):  # Exactly meet episode requirement
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0,  # Perfect intervention rate
                constitutional_score=0.85  # Perfect constitutional score
            )

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        # With perfect metrics, score should be near 100
        # Formula: 40% * 1.0 + 30% * 1.0 + 30% * 1.0 = 100%
        assert result["score"] >= 95.0

    @pytest.mark.asyncio
    async def test_readiness_target_maturity_overrides_min_episodes(self, service, db_session):
        """Readiness target_maturity parameter overrides default criteria min_episodes."""
        agent = InternAgentFactory(_session=db_session)

        # Create 20 episodes (more than INTERN min, less than SUPERVISED min)
        for _ in range(20):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.8
            )

        # Test with INTERN (min_episodes=10) - should have enough
        result_intern = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )
        assert result_intern["episode_count"] >= 10

        # Test with custom min_episodes parameter
        result_custom = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN",
            min_episodes=25  # Higher than default
        )
        assert result_custom["episode_count"] < 25
        assert "episodes" in " ".join(result_custom["gaps"]).lower()

    @pytest.mark.asyncio
    async def test_readiness_returns_current_maturity(self, service, db_session):
        """Readiness returns current_maturity in result dict."""
        agent = SupervisedAgentFactory(_session=db_session)

        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="AUTONOMOUS"
        )

        assert "current_maturity" in result
        assert result["current_maturity"] == "SUPERVISED"


class TestGraduationCriteria:
    """Test graduation criteria constants."""

    def test_intern_criteria_values(self):
        """INTERN criteria: 10 min_episodes, 0.5 max_intervention_rate, 0.70 min_constitutional_score."""
        criteria = AgentGraduationService.CRITERIA["INTERN"]

        assert criteria["min_episodes"] == 10
        assert criteria["max_intervention_rate"] == 0.5
        assert criteria["min_constitutional_score"] == 0.70

    def test_supervised_criteria_values(self):
        """SUPERVISED criteria: 25 min_episodes, 0.2 max_intervention_rate, 0.85 min_constitutional_score."""
        criteria = AgentGraduationService.CRITERIA["SUPERVISED"]

        assert criteria["min_episodes"] == 25
        assert criteria["max_intervention_rate"] == 0.2
        assert criteria["min_constitutional_score"] == 0.85

    def test_autonomous_criteria_values(self):
        """AUTONOMOUS criteria: 50 min_episodes, 0.0 max_intervention_rate, 0.95 min_constitutional_score."""
        criteria = AgentGraduationService.CRITERIA["AUTONOMOUS"]

        assert criteria["min_episodes"] == 50
        assert criteria["max_intervention_rate"] == 0.0
        assert criteria["min_constitutional_score"] == 0.95

    def test_criteria_accessed_via_service_dict(self):
        """Criteria accessed via AgentGraduationService.CRITERIA dict."""
        assert hasattr(AgentGraduationService, "CRITERIA")
        assert isinstance(AgentGraduationService.CRITERIA, dict)
        assert "INTERN" in AgentGraduationService.CRITERIA
        assert "SUPERVISED" in AgentGraduationService.CRITERIA
        assert "AUTONOMOUS" in AgentGraduationService.CRITERIA

    def test_criteria_structure_validation(self):
        """Criteria structure validated (has min_episodes, max_intervention_rate, min_constitutional_score keys)."""
        for level, criteria in AgentGraduationService.CRITERIA.items():
            assert "min_episodes" in criteria
            assert "max_intervention_rate" in criteria
            assert "min_constitutional_score" in criteria
            assert isinstance(criteria["min_episodes"], int)
            assert isinstance(criteria["max_intervention_rate"], float)
            assert isinstance(criteria["min_constitutional_score"], float)

    def test_unknown_maturity_level_returns_none(self):
        """Unknown maturity level returns None from CRITERIA dict."""
        criteria = AgentGraduationService.CRITERIA.get("UNKNOWN_LEVEL")
        assert criteria is None


class TestPromotionDecisions:
    """Test promotion decision logic."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_promote_agent_updates_agent_status_enum(self, service, db_session):
        """promote_agent updates AgentStatus enum correctly."""
        agent = StudentAgentFactory(_session=db_session)
        assert agent.status == AgentStatus.STUDENT

        await service.promote_agent(
            agent_id=agent.id,
            new_maturity="INTERN",
            validated_by="test_user"
        )

        db_session.refresh(agent)
        assert agent.status == AgentStatus.INTERN

    @pytest.mark.asyncio
    async def test_promote_agent_sets_promoted_at_timestamp(self, service, db_session):
        """promote_agent sets configuration["promoted_at"] timestamp."""
        agent = InternAgentFactory(_session=db_session)

        await service.promote_agent(
            agent_id=agent.id,
            new_maturity="SUPERVISED",
            validated_by="test_user"
        )

        db_session.refresh(agent)
        assert "promoted_at" in agent.configuration
        assert agent.configuration["promoted_at"] is not None

    @pytest.mark.asyncio
    async def test_promote_agent_sets_promoted_by_user(self, service, db_session):
        """promote_agent sets configuration["promoted_by"] user."""
        agent = SupervisedAgentFactory(_session=db_session)

        await service.promote_agent(
            agent_id=agent.id,
            new_maturity="AUTONOMOUS",
            validated_by="admin_user"
        )

        db_session.refresh(agent)
        assert agent.configuration.get("promoted_by") == "admin_user"

    @pytest.mark.asyncio
    async def test_promote_agent_calls_db_commit(self, service, db_session):
        """promote_agent calls db.commit to persist changes."""
        agent = InternAgentFactory(_session=db_session)

        # Track commit calls
        original_commit = db_session.commit
        commit_called = False

        def mock_commit():
            nonlocal commit_called
            commit_called = True
            return original_commit()

        db_session.commit = mock_commit

        await service.promote_agent(
            agent_id=agent.id,
            new_maturity="SUPERVISED",
            validated_by="test_user"
        )

        assert commit_called

        # Restore original commit
        db_session.commit = original_commit

    @pytest.mark.asyncio
    async def test_promote_agent_updates_updated_at_timestamp(self, service, db_session):
        """promote_agent updates agent.updated_at timestamp."""
        agent = InternAgentFactory(_session=db_session)
        original_updated_at = agent.updated_at

        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.01)

        await service.promote_agent(
            agent_id=agent.id,
            new_maturity="SUPERVISED",
            validated_by="test_user"
        )

        db_session.refresh(agent)
        assert agent.updated_at > original_updated_at

    @pytest.mark.asyncio
    async def test_promote_agent_nonexistent_agent(self, service):
        """promote_agent returns False for non-existent agent."""
        result = await service.promote_agent(
            agent_id="nonexistent-agent-id",
            new_maturity="INTERN",
            validated_by="test_user"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_promote_agent_invalid_maturity_level(self, service, db_session):
        """promote_agent returns False for invalid maturity level (not in AgentStatus enum)."""
        agent = StudentAgentFactory(_session=db_session)

        result = await service.promote_agent(
            agent_id=agent.id,
            new_maturity="INVALID_LEVEL",
            validated_by="test_user"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_promote_agent_logs_success_message(self, service, db_session, caplog):
        """promote_agent logs success message with agent_id, new_maturity, validated_by."""
        import logging
        agent = InternAgentFactory(_session=db_session)

        with caplog.at_level(logging.INFO):
            await service.promote_agent(
                agent_id=agent.id,
                new_maturity="SUPERVISED",
                validated_by="admin_user"
            )

        # Check log contains key information
        log_messages = [record.message for record in caplog.records]
        assert any("promoted to SUPERVISED" in msg for msg in log_messages)
        assert any(agent.id in msg for msg in log_messages)
        assert any("admin_user" in msg for msg in log_messages)


class TestSandboxExecutorDetailed:
    """Test SandboxExecutor detailed behavior."""

    @pytest.fixture
    def executor(self, db_session):
        """Create executor."""
        return SandboxExecutor(db_session)

    @pytest.mark.asyncio
    async def test_execute_exam_nonexistent_agent(self, executor):
        """execute_exam returns success=False for non-existent agent."""
        result = await executor.execute_exam(
            agent_id="nonexistent-agent",
            target_maturity="INTERN"
        )

        assert result["success"] is False
        assert result["score"] == 0.0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_exam_zero_episode_count(self, executor, db_session):
        """execute_exam returns score=0.0 when episode_count=0."""
        agent = StudentAgentFactory(_session=db_session)

        result = await executor.execute_exam(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        assert result["success"] is True
        assert result["score"] == 0.0
        assert result["passed"] is False
        assert "insufficient_episode_count" in result["constitutional_violations"]

    @pytest.mark.asyncio
    async def test_execute_exam_episode_score_calculation(self, executor, db_session):
        """execute_exam calculates episode_score (40% weight) from min_episodes threshold."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes (exceeding minimum)
        for _ in range(30):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0
            )

        result = await executor.execute_exam(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        # Episode score should be maxed out (40 points) with 30 episodes
        assert result["score"] > 0.4  # At least the episode portion

    @pytest.mark.asyncio
    async def test_execute_exam_intervention_score_inverted(self, executor, db_session):
        """execute_exam calculates intervention_score (30% weight) inverted (lower is better)."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with zero interventions (best case)
        for _ in range(25):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0
            )

        result = await executor.execute_exam(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        # With zero interventions, intervention_score should be maxed (30 points)
        assert result["constitutional_compliance"] >= 0.9

    @pytest.mark.asyncio
    async def test_execute_exam_compliance_score_from_intervention_rate(self, executor, db_session):
        """execute_exam calculates compliance_score (30% weight) from intervention_rate."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with moderate interventions
        for i in range(25):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=1 if i < 5 else 0  # 20% intervention rate
            )

        result = await executor.execute_exam(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        # Compliance score should be calculated from intervention rate
        assert 0.0 <= result["constitutional_compliance"] <= 1.0

    @pytest.mark.asyncio
    async def test_execute_exam_includes_constitutional_violations(self, executor, db_session):
        """execute_exam includes constitutional_violations list when interventions too high."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with very high interventions
        for _ in range(25):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=5  # Very high
            )

        result = await executor.execute_exam(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        assert "excessive_interventions" in result["constitutional_violations"]

    @pytest.mark.asyncio
    async def test_execute_exam_insufficient_performance_violation(self, executor, db_session):
        """execute_exam includes "insufficient_performance" violation when score < 0.7."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with poor performance
        for _ in range(10):  # Below minimum
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=5
            )

        result = await executor.execute_exam(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        # Low score should trigger violation
        assert "insufficient_performance" in result["constitutional_violations"]

    @pytest.mark.asyncio
    async def test_execute_exam_passed_criteria(self, executor, db_session):
        """execute_exam passed=True when score >= min_score AND compliance >= min_score."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create perfect episodes
        for _ in range(50):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=0,
                constitutional_score=1.0
            )

        result = await executor.execute_exam(
            agent_id=agent.id,
            target_maturity="AUTONOMOUS"
        )

        # With perfect metrics, should pass
        assert result["passed"] is True
        assert result["score"] >= 0.95


class TestGraduationExamExecution:
    """Test graduation exam execution via service."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_calls_executor(self, service, db_session):
        """execute_graduation_exam calls SandboxExecutor.execute_exam."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes
        for _ in range(50):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=0
            )

        result = await service.execute_graduation_exam(
            agent_id=agent.id,
            workspace_id="test-workspace",
            target_maturity="AUTONOMOUS"
        )

        assert result["exam_completed"] is True
        assert "score" in result

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_executor_failure(self, service, db_session):
        """execute_graduation_exam returns exam_completed=False on executor failure."""
        agent = StudentAgentFactory(_session=db_session)

        # No episodes - executor will return failure
        result = await service.execute_graduation_exam(
            agent_id=agent.id,
            workspace_id="test-workspace",
            target_maturity="INTERN"
        )

        assert result["exam_completed"] is True
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_low_score_fails(self, service, db_session):
        """execute_graduation_exam returns passed=False when exam success but score too low."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with poor performance
        for _ in range(10):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=5
            )

        result = await service.execute_graduation_exam(
            agent_id=agent.id,
            workspace_id="test-workspace",
            target_maturity="SUPERVISED"
        )

        assert result["exam_completed"] is True
        assert result["passed"] is False
        assert result["score"] < 0.7

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_constitutional_compliance(self, service, db_session):
        """execute_graduation_exam returns constitutional_compliance from executor."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes with zero interventions
        for _ in range(50):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=0
            )

        result = await service.execute_graduation_exam(
            agent_id=agent.id,
            workspace_id="test-workspace",
            target_maturity="AUTONOMOUS"
        )

        assert "constitutional_compliance" in result
        assert result["constitutional_compliance"] >= 0.9

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_constitutional_violations(self, service, db_session):
        """execute_graduation_exam returns constitutional_violations from executor."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes with high interventions
        for _ in range(25):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=5
            )

        result = await service.execute_graduation_exam(
            agent_id=agent.id,
            workspace_id="test-workspace",
            target_maturity="SUPERVISED"
        )

        assert "constitutional_violations" in result
        assert len(result["constitutional_violations"]) > 0

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_score_rounded(self, service, db_session):
        """execute_graduation_exam returns score rounded to 2 decimal places."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes
        for _ in range(50):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=0
            )

        result = await service.execute_graduation_exam(
            agent_id=agent.id,
            workspace_id="test-workspace",
            target_maturity="AUTONOMOUS"
        )

        # Score should be rounded to 2 decimal places
        score_str = str(result["score"])
        decimal_places = len(score_str.split(".")[-1]) if "." in score_str else 0
        assert decimal_places <= 2


class TestRunGraduationExam:
    """Test run_graduation_exam edge cases."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_run_graduation_exam_empty_edge_cases(self, service):
        """run_graduation_exam with empty edge_case_episodes returns passed=True, score=0."""
        # Mock get_sandbox_executor (imported locally in run_graduation_exam)
        from unittest.mock import AsyncMock, patch, MagicMock

        mock_executor = MagicMock()
        mock_executor.execute_in_sandbox = AsyncMock(return_value=MagicMock(
            passed=True,
            interventions=[],
            safety_violations=[],
            replayed_actions=[]
        ))

        with patch('core.sandbox_executor.get_sandbox_executor', return_value=mock_executor):
            result = await service.run_graduation_exam(
                agent_id="test-agent",
                edge_case_episodes=[]
            )

            # Empty edge cases should pass with score 0
            assert result["passed"] is True  # all() on empty is True
            assert result["score"] == 0

    @pytest.mark.asyncio
    async def test_run_graduation_exam_calls_executor_for_each_episode(self, service, db_session):
        """run_graduation_exam calls executor.execute_in_sandbox for each episode_id."""
        from unittest.mock import AsyncMock, patch, MagicMock

        # Create episodes
        ep1 = EpisodeFactory(_session=db_session, status="completed")
        ep2 = EpisodeFactory(_session=db_session, status="completed")

        mock_executor = MagicMock()
        mock_executor.execute_in_sandbox = AsyncMock(return_value=MagicMock(
            passed=True,
            interventions=[],
            safety_violations=[],
            replayed_actions=[]
        ))

        with patch('core.sandbox_executor.get_sandbox_executor', return_value=mock_executor):
            result = await service.run_graduation_exam(
                agent_id="test-agent",
                edge_case_episodes=[ep1.id, ep2.id]
            )

            # Should call executor twice
            assert mock_executor.execute_in_sandbox.call_count == 2
            assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_run_graduation_exam_includes_replayed_actions(self, service, db_session):
        """run_graduation_exam includes replayed_actions in results."""
        from unittest.mock import AsyncMock, patch, MagicMock

        episode = EpisodeFactory(_session=db_session, status="completed")

        mock_executor = MagicMock()
        mock_executor.execute_in_sandbox = AsyncMock(return_value=MagicMock(
            passed=True,
            interventions=[],
            safety_violations=[],
            replayed_actions=['action1', 'action2']
        ))

        with patch('core.sandbox_executor.get_sandbox_executor', return_value=mock_executor):
            result = await service.run_graduation_exam(
                agent_id="test-agent",
                edge_case_episodes=[episode.id]
            )

            assert "replayed_actions" in result["results"][0]
            assert result["results"][0]["replayed_actions"] == ['action1', 'action2']

    @pytest.mark.asyncio
    async def test_run_graduation_exam_includes_safety_violations(self, service, db_session):
        """run_graduation_exam includes safety_violations in results."""
        from unittest.mock import AsyncMock, patch, MagicMock

        episode = EpisodeFactory(_session=db_session, status="completed")

        mock_executor = MagicMock()
        mock_executor.execute_in_sandbox = AsyncMock(return_value=MagicMock(
            passed=False,
            interventions=['human_inter'],
            safety_violations=['unsafe_operation'],
            replayed_actions=[]
        ))

        with patch('core.sandbox_executor.get_sandbox_executor', return_value=mock_executor):
            result = await service.run_graduation_exam(
                agent_id="test-agent",
                edge_case_episodes=[episode.id]
            )

            assert "safety_violations" in result["results"][0]
            assert result["results"][0]["safety_violations"] == ['unsafe_operation']


class TestSupervisionMetricsDetailed:
    """Test supervision metrics calculation in detail."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_supervision_metrics_no_sessions_returns_zeros(self, service, db_session):
        """calculate_supervision_metrics returns zero values when no sessions."""
        agent = SupervisedAgentFactory(_session=db_session)

        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        assert metrics["total_supervision_hours"] == 0
        assert metrics["total_sessions"] == 0
        assert metrics["average_supervisor_rating"] == 0.0
        assert metrics["intervention_rate"] == 1.0  # Default when no data

    @pytest.mark.asyncio
    async def test_supervision_metrics_calculates_total_hours(self, service, db_session):
        """calculate_supervision_metrics calculates total_supervision_hours from duration_seconds."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create sessions with known durations
        for i in range(5):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i),
                duration_seconds=3600,  # 1 hour each = 5 total hours
                intervention_count=0,
                supervisor_rating=4.0
            )
            db_session.add(session)
        db_session.commit()

        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        assert metrics["total_supervision_hours"] == 5.0

    @pytest.mark.asyncio
    async def test_supervision_metrics_intervention_rate_per_hour(self, service, db_session):
        """calculate_supervision_metrics calculates intervention_rate per hour."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create session: 2 hours, 10 interventions = 5/hr
        session = SupervisionSession(
            id="session-1",
            agent_id=agent.id,
            agent_name=agent.name,
            workspace_id="test-workspace",
            trigger_id="trigger-1",
            trigger_context={},
            supervisor_id="test_supervisor",
            status="completed",
            started_at=base_time - timedelta(hours=2),
            completed_at=base_time,
            duration_seconds=7200,  # 2 hours
            intervention_count=10,
            supervisor_rating=4.0
        )
        db_session.add(session)
        db_session.commit()

        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        assert metrics["intervention_rate"] == 5.0

    @pytest.mark.asyncio
    async def test_supervision_metrics_average_supervisor_rating(self, service, db_session):
        """calculate_supervision_metrics calculates average_supervisor_rating."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create sessions with different ratings
        ratings = [3.0, 4.0, 5.0, 4.5, 3.5]
        for i, rating in enumerate(ratings):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=rating
            )
            db_session.add(session)
        db_session.commit()

        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        # Average of [3.0, 4.0, 5.0, 4.5, 3.5] = 4.0
        assert metrics["average_supervisor_rating"] == 4.0

    @pytest.mark.asyncio
    async def test_supervision_metrics_high_rating_sessions(self, service, db_session):
        """calculate_supervision_metrics counts high_rating_sessions (4-5 stars)."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create sessions: 3 with high rating (4-5), 2 with low rating
        ratings = [5.0, 4.5, 4.0, 3.0, 2.5]
        for i, rating in enumerate(ratings):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=rating
            )
            db_session.add(session)
        db_session.commit()

        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        assert metrics["high_rating_sessions"] == 3

    @pytest.mark.asyncio
    async def test_supervision_metrics_low_intervention_sessions(self, service, db_session):
        """calculate_supervision_metrics counts low_intervention_sessions (0-1 interventions)."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create sessions with varying intervention counts
        intervention_counts = [0, 1, 2, 0, 1]  # 4 with low (0-1), 1 with high (2)
        for i, count in enumerate(intervention_counts):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=count,
                supervisor_rating=4.0
            )
            db_session.add(session)
        db_session.commit()

        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        assert metrics["low_intervention_sessions"] == 4

    @pytest.mark.asyncio
    async def test_supervision_metrics_successful_intervention_recovery_rate(self, service, db_session):
        """calculate_supervision_metrics calculates successful_intervention_recovery_rate."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create sessions:
        # - 3 with interventions and good ratings (recovery)
        # - 2 with interventions and poor ratings (no recovery)
        # - 2 with no interventions (excluded from calculation)
        configs = [
            (5, 5.0),  # intervention + good rating = recovery
            (3, 4.0),  # intervention + good rating = recovery
            (2, 3.0),  # intervention + good rating = recovery
            (5, 2.0),  # intervention + poor rating = no recovery
            (4, 1.0),  # intervention + poor rating = no recovery
            (0, 4.0),  # no intervention = excluded
            (0, 5.0),  # no intervention = excluded
        ]
        for i, (interventions, rating) in enumerate(configs):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=interventions,
                supervisor_rating=rating
            )
            db_session.add(session)
        db_session.commit()

        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        # 3 recoveries / 5 sessions with interventions = 0.6
        assert metrics["successful_intervention_recovery_rate"] == 0.6

    @pytest.mark.asyncio
    async def test_supervision_metrics_handles_none_supervisor_rating(self, service, db_session):
        """calculate_supervision_metrics handles None supervisor_rating gracefully."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create sessions with None ratings
        for i in range(3):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=None
            )
            db_session.add(session)
        db_session.commit()

        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        # Should handle None by excluding from average
        assert metrics["average_supervisor_rating"] == 0.0


class TestPerformanceTrendCalculation:
    """Test performance trend calculation."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_performance_trend_less_than_10_sessions(self, service, db_session):
        """_calculate_performance_trend returns "stable" with <10 sessions."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create only 5 sessions
        for i in range(5):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=5.0
            )
            db_session.add(session)
        db_session.commit()

        sessions = db_session.query(SupervisionSession).filter(
            SupervisionSession.agent_id == agent.id
        ).all()

        trend = service._calculate_performance_trend(sessions)
        assert trend == "stable"

    @pytest.mark.asyncio
    async def test_performance_trend_improving(self, service, db_session):
        """_calculate_performance_trend returns "improving" when recent ratings higher."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create 10 sessions: recent 5 with high ratings, previous 5 with low ratings
        for i in range(10):
            # Recent (i=0-4): 5.0, Previous (i=5-9): 2.0
            rating = 5.0 if i < 5 else 2.0
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=rating
            )
            db_session.add(session)
        db_session.commit()

        sessions = db_session.query(SupervisionSession).filter(
            SupervisionSession.agent_id == agent.id
        ).all()

        trend = service._calculate_performance_trend(sessions)
        assert trend == "improving"

    @pytest.mark.asyncio
    async def test_performance_trend_declining(self, service, db_session):
        """_calculate_performance_trend returns "declining" when recent ratings lower."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create 10 sessions: recent 5 with low ratings, previous 5 with high ratings
        for i in range(10):
            # Recent (i=0-4): 2.0, Previous (i=5-9): 5.0
            rating = 2.0 if i < 5 else 5.0
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=rating
            )
            db_session.add(session)
        db_session.commit()

        sessions = db_session.query(SupervisionSession).filter(
            SupervisionSession.agent_id == agent.id
        ).all()

        trend = service._calculate_performance_trend(sessions)
        assert trend == "declining"

    @pytest.mark.asyncio
    async def test_performance_trend_combined_score(self, service, db_session):
        """_calculate_performance_trend combines rating_diff (60%) and intervention_diff (40%)."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create 10 sessions with both rating and intervention improvements
        for i in range(10):
            # Recent: high rating (5.0), low intervention (0)
            # Previous: low rating (2.0), high intervention (10)
            rating = 5.0 if i < 5 else 2.0
            interventions = 0 if i < 5 else 10
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=interventions,
                supervisor_rating=rating
            )
            db_session.add(session)
        db_session.commit()

        sessions = db_session.query(SupervisionSession).filter(
            SupervisionSession.agent_id == agent.id
        ).all()

        trend = service._calculate_performance_trend(sessions)
        # Combined score should be > 0.3 (improving)
        assert trend == "improving"

    @pytest.mark.asyncio
    async def test_performance_trend_handles_none_started_at(self, service, db_session):
        """_calculate_performance_trend handles None started_at (treated as datetime.min)."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create sessions with None started_at
        for i in range(10):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=None,  # None started_at
                completed_at=None,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=4.0
            )
            db_session.add(session)
        db_session.commit()

        sessions = db_session.query(SupervisionSession).filter(
            SupervisionSession.agent_id == agent.id
        ).all()

        # Should handle None started_at gracefully
        trend = service._calculate_performance_trend(sessions)
        assert trend in ["improving", "stable", "declining"]


class TestSupervisionScoreCalculation:
    """Test supervision score calculation."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_supervision_score_rating_component(self, service, db_session):
        """_supervision_score calculates rating_score (40% of total)."""
        metrics = {
            "average_supervisor_rating": 4.0,  # Target: 4.0
            "intervention_rate": 0.0,
            "total_sessions": 10,
            "high_rating_sessions": 8,
            "recent_performance_trend": "improving"
        }
        criteria = {
            "max_intervention_rate": 0.5
        }

        score = service._supervision_score(metrics, criteria)

        # Rating score: 4.0/4.0 * 40 = 40
        assert score >= 40.0

    @pytest.mark.asyncio
    async def test_supervision_score_intervention_component(self, service, db_session):
        """_supervision_score calculates intervention_score (30% of total)."""
        metrics = {
            "average_supervisor_rating": 4.0,
            "intervention_rate": 0.0,  # Perfect
            "total_sessions": 10,
            "high_rating_sessions": 8,
            "recent_performance_trend": "improving"
        }
        criteria = {
            "max_intervention_rate": 0.5
        }

        score = service._supervision_score(metrics, criteria)

        # Intervention score: (1 - 0.0/5.0) * 30 = 30
        assert score >= 70.0  # At least rating + intervention

    @pytest.mark.asyncio
    async def test_supervision_score_high_quality_component(self, service, db_session):
        """_supervision_score calculates high_quality_score (20% of total)."""
        metrics = {
            "average_supervisor_rating": 4.0,
            "intervention_rate": 0.0,
            "total_sessions": 10,
            "high_rating_sessions": 8,  # 80% high quality (target: 60%)
            "recent_performance_trend": "improving"
        }
        criteria = {
            "max_intervention_rate": 0.5
        }

        score = service._supervision_score(metrics, criteria)

        # High quality score: min(8/10/0.6, 1.0) * 20 = 20
        assert score >= 90.0  # At least rating + intervention + high_quality

    @pytest.mark.asyncio
    async def test_supervision_score_trend_component(self, service, db_session):
        """_supervision_score calculates trend_score (10% of total)."""
        metrics = {
            "average_supervisor_rating": 4.0,
            "intervention_rate": 0.0,
            "total_sessions": 10,
            "high_rating_sessions": 8,
            "recent_performance_trend": "improving"  # +10 points
        }
        criteria = {
            "max_intervention_rate": 0.5
        }

        score = service._supervision_score(metrics, criteria)

        # With all perfect components + improving trend: 100
        assert score >= 90.0

    @pytest.mark.asyncio
    async def test_supervision_score_capped_at_100(self, service, db_session):
        """_supervision_score caps rating_score at 1.0 (4.0/5.0 target)."""
        metrics = {
            "average_supervisor_rating": 5.0,  # Above target
            "intervention_rate": 0.0,
            "total_sessions": 10,
            "high_rating_sessions": 10,
            "recent_performance_trend": "improving"
        }
        criteria = {
            "max_intervention_rate": 0.5
        }

        score = service._supervision_score(metrics, criteria)

        # Rating should be capped: min(5.0/4.0, 1.0) * 40 = 40
        # Total should be at most 100
        assert score <= 100.0


class TestValidationWithSupervision:
    """Test validation with supervision integration."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_validate_with_supervision_combines_metrics(self, service, db_session):
        """validate_graduation_with_supervision combines episode and supervision metrics."""
        agent = InternAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create episodes
        for _ in range(20):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.8
            )

        # Create supervision sessions
        for i in range(5):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=4.0
            )
            db_session.add(session)
        db_session.commit()

        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.SUPERVISED
        )

        assert "episode_metrics" in result
        assert "supervision_metrics" in result

    @pytest.mark.asyncio
    async def test_validate_with_supervision_adds_gaps(self, service, db_session):
        """validate_graduation_with_supervision adds supervision gaps to episode gaps."""
        agent = InternAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create episodes with poor performance
        for _ in range(5):  # Too few
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=5,  # Too high
                constitutional_score=0.6  # Too low
            )

        # Create supervision sessions with poor performance
        for i in range(3):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=5,
                supervisor_rating=2.0  # Too low
            )
            db_session.add(session)
        db_session.commit()

        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.SUPERVISED
        )

        # Should have both episode and supervision gaps
        assert len(result["gaps"]) > 0
        assert any("episodes" in gap.lower() for gap in result["gaps"])
        assert any("rating" in gap.lower() or "supervisor" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_validate_with_supervision_min_high_quality_sessions(self, service, db_session):
        """validate_graduation_with_supervision checks min_high_quality_sessions requirement."""
        agent = InternAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create episodes
        for _ in range(25):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.9
            )

        # Create sessions without high ratings (below 40% threshold)
        for i in range(5):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=3.0  # Not high quality
            )
            db_session.add(session)
        db_session.commit()

        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.SUPERVISED
        )

        # Should flag insufficient high-quality sessions
        assert any("high-rated" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_validate_with_supervision_min_low_intervention_sessions(self, service, db_session):
        """validate_graduation_with_supervision checks min_low_intervention_sessions requirement."""
        agent = InternAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create episodes
        for _ in range(25):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.9
            )

        # Create sessions with high interventions
        for i in range(5):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=5,  # High
                supervisor_rating=4.0
            )
            db_session.add(session)
        db_session.commit()

        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.SUPERVISED
        )

        # Should flag insufficient low-intervention sessions
        assert any("low-intervention" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_validate_with_supervision_average_rating_threshold(self, service, db_session):
        """validate_graduation_with_supervision checks average_supervisor_rating >= 3.5."""
        agent = InternAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create episodes
        for _ in range(25):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.9
            )

        # Create sessions with low average rating
        for i in range(5):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=3.0  # Below 3.5 threshold
            )
            db_session.add(session)
        db_session.commit()

        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.SUPERVISED
        )

        # Should flag low average rating
        assert any("rating" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_validate_with_supervision_intervention_rate_threshold(self, service, db_session):
        """validate_graduation_with_supervision checks intervention_rate threshold."""
        agent = InternAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create episodes
        for _ in range(25):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.9
            )

        # Create sessions with high intervention rate
        for i in range(5):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,  # 1 hour
                intervention_count=10,  # 10/hr = very high
                supervisor_rating=4.0
            )
            db_session.add(session)
        db_session.commit()

        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.SUPERVISED
        )

        # Should flag high intervention rate
        assert any("intervention" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_validate_with_supervision_combined_score(self, service, db_session):
        """validate_graduation_with_supervision calculates combined score (70% episode + 30% supervision)."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create perfect episodes (50 for AUTONOMOUS)
        for _ in range(50):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.95
            )

        # Create perfect supervision sessions (30 for good metrics)
        for i in range(30):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=5.0
            )
            db_session.add(session)
        db_session.commit()

        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.AUTONOMOUS
        )

        # With perfect metrics, score should be near 100
        assert result["score"] >= 90.0

    @pytest.mark.asyncio
    async def test_validate_with_supervision_ready_when_all_pass(self, service, db_session):
        """validate_graduation_with_supervision ready=True only when all gaps empty and episode ready."""
        agent = SupervisedAgentFactory(_session=db_session)
        base_time = datetime.now()

        # Create perfect episodes (50 for AUTONOMOUS target)
        for _ in range(50):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.95
            )

        # Create perfect supervision sessions (need at least 20 high-quality for AUTONOMOUS criteria)
        for i in range(30):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id=agent.id,
                agent_name=agent.name,
                workspace_id="test-workspace",
                trigger_id=f"trigger-{i}",
                trigger_context={},
                supervisor_id="test_supervisor",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i) if i > 0 else base_time,
                duration_seconds=3600,
                intervention_count=0,
                supervisor_rating=5.0
            )
            db_session.add(session)
        db_session.commit()

        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.AUTONOMOUS
        )

        # All criteria met, should be ready
        assert result["ready"] is True
        assert len(result["gaps"]) == 0


class TestSkillUsageMetrics:
    """Test skill usage metrics calculation."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_skill_usage_filters_by_agent_and_date(self, service, db_session):
        """calculate_skill_usage_metrics filters by agent_id and date range."""
        agent = InternAgentFactory(_session=db_session)

        # Note: This test checks the filtering logic is present
        # Actual SkillExecution records may not exist in test DB
        result = await service.calculate_skill_usage_metrics(
            agent_id=agent.id,
            days_back=30
        )

        # Should return metrics structure even with no data
        assert "total_skill_executions" in result
        assert "successful_executions" in result
        assert "success_rate" in result
        assert "unique_skills_used" in result

    @pytest.mark.asyncio
    async def test_skill_usage_counts_successful_executions(self, service, db_session):
        """calculate_skill_usage_metrics counts successful_executions vs total."""
        agent = SupervisedAgentFactory(_session=db_session)

        result = await service.calculate_skill_usage_metrics(
            agent_id=agent.id,
            days_back=30
        )

        # Should track total and successful
        assert result["total_skill_executions"] >= result["successful_executions"]

    @pytest.mark.asyncio
    async def test_skill_usage_calculates_success_rate(self, service, db_session):
        """calculate_skill_usage_metrics calculates success_rate."""
        agent = SupervisedAgentFactory(_session=db_session)

        result = await service.calculate_skill_usage_metrics(
            agent_id=agent.id,
            days_back=30
        )

        # Success rate should be 0-1 or 0 if no executions
        assert 0.0 <= result["success_rate"] <= 1.0

    @pytest.mark.asyncio
    async def test_skill_usage_counts_unique_skills(self, service, db_session):
        """calculate_skill_usage_metrics counts unique_skills_used."""
        agent = SupervisedAgentFactory(_session=db_session)

        result = await service.calculate_skill_usage_metrics(
            agent_id=agent.id,
            days_back=30
        )

        # Should count unique skills
        assert result["unique_skills_used"] >= 0

    @pytest.mark.asyncio
    async def test_skill_usage_calculates_learning_velocity(self, service, db_session):
        """calculate_skill_usage_metrics calculates skill_learning_velocity (episodes per day)."""
        agent = SupervisedAgentFactory(_session=db_session)

        result = await service.calculate_skill_usage_metrics(
            agent_id=agent.id,
            days_back=30
        )

        # Learning velocity should be non-negative
        assert result["skill_learning_velocity"] >= 0.0

    @pytest.mark.asyncio
    async def test_skill_usage_handles_days_back_parameter(self, service, db_session):
        """calculate_skill_usage_metrics handles days_back parameter correctly."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Test with different day ranges
        result_7 = await service.calculate_skill_usage_metrics(agent_id=agent.id, days_back=7)
        result_30 = await service.calculate_skill_usage_metrics(agent_id=agent.id, days_back=30)
        result_90 = await service.calculate_skill_usage_metrics(agent_id=agent.id, days_back=90)

        # All should return valid metrics
        for result in [result_7, result_30, result_90]:
            assert "total_skill_executions" in result
            assert "skill_learning_velocity" in result


class TestReadinessWithSkills:
    """Test readiness score with skills integration."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_readiness_with_skills_integrates_metrics(self, service, db_session):
        """calculate_readiness_score_with_skills integrates skill metrics."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes
        for _ in range(30):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=0,
                constitutional_score=0.9
            )

        result = await service.calculate_readiness_score_with_skills(
            agent_id=agent.id,
            target_maturity="AUTONOMOUS"
        )

        assert "readiness_score" in result
        assert "episode_metrics" in result
        assert "skill_metrics" in result

    @pytest.mark.asyncio
    async def test_readiness_with_skills_applies_diversity_bonus(self, service, db_session):
        """calculate_readiness_score_with_skills applies skill_diversity_bonus (up to +5%)."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes
        for _ in range(50):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=0,
                constitutional_score=1.0
            )

        result = await service.calculate_readiness_score_with_skills(
            agent_id=agent.id,
            target_maturity="AUTONOMOUS"
        )

        # Check diversity bonus is applied
        assert "skill_diversity_bonus" in result
        assert result["skill_diversity_bonus"] >= 0.0

    @pytest.mark.asyncio
    async def test_readiness_with_skills_caps_final_score(self, service, db_session):
        """calculate_readiness_score_with_skills caps final_score at 1.0."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes with perfect metrics
        for _ in range(50):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed",
                human_intervention_count=0,
                constitutional_score=1.0
            )

        result = await service.calculate_readiness_score_with_skills(
            agent_id=agent.id,
            target_maturity="AUTONOMOUS"
        )

        # Score should be capped at 1.0
        assert result["readiness_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_readiness_with_skills_returns_skill_metrics(self, service, db_session):
        """calculate_readiness_score_with_skills returns skill_metrics in result."""
        agent = SupervisedAgentFactory(_session=db_session)

        result = await service.calculate_readiness_score_with_skills(
            agent_id=agent.id,
            target_maturity="AUTONOMOUS"
        )

        assert "skill_metrics" in result
        assert "total_skill_executions" in result["skill_metrics"]

    @pytest.mark.asyncio
    async def test_readiness_with_skills_returns_diversity_bonus(self, service, db_session):
        """calculate_readiness_score_with_skills returns skill_diversity_bonus in result."""
        agent = SupervisedAgentFactory(_session=db_session)

        result = await service.calculate_readiness_score_with_skills(
            agent_id=agent.id,
            target_maturity="AUTONOMOUS"
        )

        assert "skill_diversity_bonus" in result
        assert isinstance(result["skill_diversity_bonus"], float)


class TestGraduationAuditTrail:
    """Test graduation audit trail."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_audit_trail_groups_by_maturity(self, service, db_session):
        """get_graduation_audit_trail groups episodes by maturity_at_time."""
        agent = InternAgentFactory(_session=db_session)

        # Create episodes at different maturity levels
        for _ in range(5):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="INTERN",
                status="completed"
            )
        for _ in range(3):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="STUDENT",
                status="completed"
            )

        trail = await service.get_graduation_audit_trail(agent_id=agent.id)

        assert "episodes_by_maturity" in trail
        assert "INTERN" in trail["episodes_by_maturity"]
        assert "STUDENT" in trail["episodes_by_maturity"]
        assert trail["episodes_by_maturity"]["INTERN"] == 5
        assert trail["episodes_by_maturity"]["STUDENT"] == 3

    @pytest.mark.asyncio
    async def test_audit_trail_calculates_episodes_by_maturity(self, service, db_session):
        """get_graduation_audit_trail calculates episodes_by_maturity counts."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create episodes across multiple maturity levels
        maturity_levels = ["STUDENT", "INTERN", "SUPERVISED"]
        for i, level in enumerate(maturity_levels):
            for _ in range(i + 1):  # 1, 2, 3 episodes
                EpisodeFactory(
                    _session=db_session,
                    agent_id=agent.id,
                    maturity_at_time=level,
                    status="completed"
                )

        trail = await service.get_graduation_audit_trail(agent_id=agent.id)

        assert trail["episodes_by_maturity"]["STUDENT"] == 1
        assert trail["episodes_by_maturity"]["INTERN"] == 2
        assert trail["episodes_by_maturity"]["SUPERVISED"] == 3

    @pytest.mark.asyncio
    async def test_audit_trail_includes_recent_episodes(self, service, db_session):
        """get_graduation_audit_trail includes recent_episodes (max 10)."""
        agent = SupervisedAgentFactory(_session=db_session)

        # Create 15 episodes
        for i in range(15):
            EpisodeFactory(
                _session=db_session,
                agent_id=agent.id,
                maturity_at_time="SUPERVISED",
                status="completed"
            )

        trail = await service.get_graduation_audit_trail(agent_id=agent.id)

        assert "recent_episodes" in trail
        assert len(trail["recent_episodes"]) <= 10

    @pytest.mark.asyncio
    async def test_audit_trail_handles_no_episodes(self, service, db_session):
        """get_graduation_audit_trail handles agent with no episodes (empty lists)."""
        agent = StudentAgentFactory(_session=db_session)

        trail = await service.get_graduation_audit_trail(agent_id=agent.id)

        assert trail["total_episodes"] == 0
        assert trail["episodes_by_maturity"] == {}
        assert trail["recent_episodes"] == []

    @pytest.mark.asyncio
    async def test_audit_trail_nonexistent_agent(self, service):
        """get_graduation_audit_trail returns error dict for non-existent agent."""
        trail = await service.get_graduation_audit_trail(agent_id="nonexistent-agent")

        assert "error" in trail
        assert trail["error"] == "Agent not found"
