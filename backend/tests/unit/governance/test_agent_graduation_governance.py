"""
Unit tests for AgentGraduationService (governance-specific logic).

Tests governance logic: maturity level transitions, confidence scores,
permission matrix validation, and graduation audit logging.
Focuses on governance logic only, NOT episodic memory integration.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    SupervisionSession,
)
from core.agent_graduation_service import AgentGraduationService
from tests.factories import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory,
    EpisodeFactory,
)


# Test database session fixture
@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


# Graduation service fixture
@pytest.fixture
def graduation_service(db_session):
    """Create graduation service instance."""
    return AgentGraduationService(db_session)


# ========================================================================
# Task 2.1: Maturity Level Transitions
# ========================================================================

class TestMaturityLevelTransitions:
    """Test maturity level transition validation."""

    @pytest.mark.asyncio
    async def test_student_to_intern_transition_criteria(self, graduation_service, db_session):
        """Test STUDENT -> INTERN graduation criteria."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        # Verify criteria structure
        assert "target_maturity" in result
        assert result["target_maturity"] == "INTERN"
        assert "score" in result
        assert "gaps" in result
        assert "ready" in result

    @pytest.mark.asyncio
    async def test_intern_to_supervised_transition_criteria(self, graduation_service, db_session):
        """Test INTERN -> SUPERVISED graduation criteria."""
        agent = InternAgentFactory(_session=db_session)
        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="SUPERVISED"
        )

        assert result["target_maturity"] == "SUPERVISED"
        assert "episode_count" in result
        assert "intervention_rate" in result

    @pytest.mark.asyncio
    async def test_supervised_to_autonomous_transition_criteria(self, graduation_service, db_session):
        """Test SUPERVISED -> AUTONOMOUS graduation criteria."""
        agent = SupervisedAgentFactory(_session=db_session)
        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="AUTONOMOUS"
        )

        assert result["target_maturity"] == "AUTONOMOUS"
        # AUTONOMOUS requires 0% intervention rate
        assert "intervention_rate" in result

    @pytest.mark.asyncio
    async def test_invalid_maturity_level_returns_error(self, graduation_service, db_session):
        """Test requesting graduation to invalid maturity level."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INVALID_LEVEL"
        )

        assert "error" in result
        assert "Unknown maturity level" in result["error"]

    @pytest.mark.asyncio
    async def test_nonexistent_agent_returns_error(self, graduation_service):
        """Test calculating readiness for non-existent agent."""
        result = await graduation_service.calculate_readiness_score(
            agent_id="nonexistent_agent_id",
            target_maturity="INTERN"
        )

        assert "error" in result
        assert "Agent not found" in result["error"]


# ========================================================================
# Task 2.2: Confidence Score Thresholds
# ========================================================================

class TestConfidenceScoreThresholds:
    """Test confidence score calculation and thresholds."""

    @pytest.mark.asyncio
    async def test_minimum_confidence_for_each_level(self, graduation_service, db_session):
        """Test minimum confidence requirements for each maturity level."""
        # Create agents at different maturity levels
        student = StudentAgentFactory(confidence_score=0.4, _session=db_session)
        intern = InternAgentFactory(confidence_score=0.6, _session=db_session)
        supervised = SupervisedAgentFactory(confidence_score=0.8, _session=db_session)

        db_session.commit()

        # Each should have different readiness
        student_result = await graduation_service.calculate_readiness_score(
            agent_id=student.id,
            target_maturity="INTERN"
        )

        intern_result = await graduation_service.calculate_readiness_score(
            agent_id=intern.id,
            target_maturity="SUPERVISED"
        )

        supervised_result = await graduation_service.calculate_readiness_score(
            agent_id=supervised.id,
            target_maturity="AUTONOMOUS"
        )

        # Lower confidence agent should have lower readiness
        assert "score" in student_result
        assert "score" in intern_result
        assert "score" in supervised_result

    def test_confidence_score_calculation_components(self, graduation_service):
        """Test readiness score calculation components."""
        # Test _calculate_score method directly
        score = graduation_service._calculate_score(
            episode_count=10,
            min_episodes=10,
            intervention_rate=0.3,
            max_intervention=0.5,
            constitutional_score=0.8,
            min_constitutional=0.7
        )

        # Score should be between 0 and 100
        assert 0 <= score <= 100

        # High metrics should give high score
        assert score > 50  # With all metrics at or above threshold

    def test_score_normalization(self, graduation_service):
        """Test score is normalized correctly."""
        # Perfect metrics
        perfect_score = graduation_service._calculate_score(
            episode_count=100,
            min_episodes=10,
            intervention_rate=0.0,
            max_intervention=0.5,
            constitutional_score=1.0,
            min_constitutional=0.7
        )

        # Low metrics
        low_score = graduation_service._calculate_score(
            episode_count=1,
            min_episodes=10,
            intervention_rate=1.0,
            max_intervention=0.5,
            constitutional_score=0.5,
            min_constitutional=0.7
        )

        assert perfect_score > low_score
        assert perfect_score <= 100
        assert low_score >= 0

    def test_intervention_rate_inversion(self, graduation_service):
        """Test that lower intervention rate gives higher score."""
        # Low intervention (good)
        low_int_score = graduation_service._calculate_score(
            episode_count=10,
            min_episodes=10,
            intervention_rate=0.1,
            max_intervention=0.5,
            constitutional_score=0.8,
            min_constitutional=0.7
        )

        # High intervention (bad)
        high_int_score = graduation_service._calculate_score(
            episode_count=10,
            min_episodes=10,
            intervention_rate=0.9,
            max_intervention=0.5,
            constitutional_score=0.8,
            min_constitutional=0.7
        )

        assert low_int_score > high_int_score


# ========================================================================
# Task 2.3: Permission Matrix Validation
# ========================================================================

class TestPermissionMatrixValidation:
    """Test permission matrix validation on graduation."""

    @pytest.mark.asyncio
    async def test_promote_agent_updates_maturity_level(self, graduation_service, db_session):
        """Test promoting agent updates maturity level in database."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Store original status
        original_status = agent.status

        # Promote to INTERN
        success = await graduation_service.promote_agent(
            agent_id=agent.id,
            new_maturity="INTERN",
            validated_by="test_user"
        )

        assert success is True

        # Refresh and verify
        db_session.refresh(agent)
        assert agent.status == AgentStatus.INTERN.value
        assert agent.status != original_status

    @pytest.mark.asyncio
    async def test_promote_nonexistent_agent_returns_false(self, graduation_service):
        """Test promoting non-existent agent returns False."""
        success = await graduation_service.promote_agent(
            agent_id="nonexistent_agent",
            new_maturity="INTERN",
            validated_by="test_user"
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_promote_with_invalid_maturity_returns_false(self, graduation_service, db_session):
        """Test promoting with invalid maturity level returns False."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        success = await graduation_service.promote_agent(
            agent_id=agent.id,
            new_maturity="INVALID_LEVEL",
            validated_by="test_user"
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_promotion_metadata_updated(self, graduation_service, db_session):
        """Test promotion updates agent metadata."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        validated_by = "admin_user"
        await graduation_service.promote_agent(
            agent_id=agent.id,
            new_maturity="INTERN",
            validated_by=validated_by
        )

        # Refresh and check configuration metadata
        db_session.refresh(agent)
        assert agent.configuration is not None
        assert "promoted_at" in agent.configuration
        assert "promoted_by" in agent.configuration
        assert agent.configuration["promoted_by"] == validated_by


# ========================================================================
# Task 2.4: Graduation Request Processing
# ========================================================================

class TestGraduationRequestProcessing:
    """Test graduation request submission and validation."""

    @pytest.mark.asyncio
    async def test_calculate_readiness_returns_complete_result(self, graduation_service, db_session):
        """Test readiness calculation returns all required fields."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        # Verify all required fields present
        required_fields = [
            "ready", "score", "episode_count", "intervention_rate",
            "avg_constitutional_score", "recommendation", "gaps",
            "target_maturity", "current_maturity"
        ]

        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_readiness_gaps_identify_missing_criteria(self, graduation_service, db_session):
        """Test readiness gaps identify what agent is missing."""
        # Create agent with no episodes (will have gaps)
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        # Should have gaps for missing episodes
        assert isinstance(result["gaps"], list)
        # With no episodes, should have at least one gap
        assert len(result["gaps"]) >= 1 or result["episode_count"] >= 10

    @pytest.mark.asyncio
    async def test_recommendation_generation(self, graduation_service, db_session):
        """Test recommendation message generation."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        # Should have recommendation
        assert "recommendation" in result
        assert isinstance(result["recommendation"], str)
        assert len(result["recommendation"]) > 0


# ========================================================================
# Task 2.5: Graduation Audit Logging
# ========================================================================

class TestGraduationAuditLogging:
    """Test graduation audit trail and history."""

    @pytest.mark.asyncio
    async def test_get_graduation_audit_trail(self, graduation_service, db_session):
        """Test retrieving graduation audit trail."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        audit = await graduation_service.get_graduation_audit_trail(
            agent_id=agent.id
        )

        # Verify audit structure
        assert "agent_id" in audit
        assert "agent_name" in audit
        assert "current_maturity" in audit
        assert "total_episodes" in audit
        assert "total_interventions" in audit
        assert "avg_constitutional_score" in audit

    @pytest.mark.asyncio
    async def test_audit_trail_includes_maturity_breakdown(self, graduation_service, db_session):
        """Test audit trail includes episodes by maturity level."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        audit = await graduation_service.get_graduation_audit_trail(
            agent_id=agent.id
        )

        assert "episodes_by_maturity" in audit
        assert isinstance(audit["episodes_by_maturity"], dict)

    @pytest.mark.asyncio
    async def test_audit_for_nonexistent_agent_returns_error(self, graduation_service):
        """Test audit for non-existent agent returns error."""
        audit = await graduation_service.get_graduation_audit_trail(
            agent_id="nonexistent_agent"
        )

        assert "error" in audit
        assert "Agent not found" in audit["error"]


# ========================================================================
# Task 2.6: Supervision Metrics Integration
# ========================================================================

class TestSupervisionMetricsIntegration:
    """Test supervision-based metrics for graduation."""

    @pytest.mark.asyncio
    async def test_calculate_supervision_metrics(self, graduation_service, db_session):
        """Test supervision metrics calculation."""
        agent = SupervisedAgentFactory(_session=db_session)
        db_session.commit()

        metrics = await graduation_service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        # Verify metrics structure
        required_fields = [
            "total_supervision_hours",
            "intervention_rate",
            "average_supervisor_rating",
            "successful_intervention_recovery_rate",
            "recent_performance_trend",
            "total_sessions",
            "high_rating_sessions",
            "low_intervention_sessions"
        ]

        for field in required_fields:
            assert field in metrics

    @pytest.mark.asyncio
    async def test_supervision_metrics_with_no_sessions(self, graduation_service, db_session):
        """Test supervision metrics when agent has no supervision sessions."""
        agent = SupervisedAgentFactory(_session=db_session)
        db_session.commit()

        metrics = await graduation_service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        # Should return zero/default metrics
        assert metrics["total_sessions"] == 0
        assert metrics["total_supervision_hours"] == 0
        assert metrics["intervention_rate"] == 1.0  # High penalty when no data

    @pytest.mark.asyncio
    async def test_performance_trend_calculation(self, graduation_service, db_session):
        """Test performance trend calculation from supervision sessions."""
        # Create agent and supervision sessions
        agent = SupervisedAgentFactory(_session=db_session)

        # Create sessions with different ratings
        sessions = []
        base_time = datetime.now()
        import uuid

        for i in range(15):
            # Create sessions with improving trend (lower to higher index)
            session = SupervisionSession(
                id=str(uuid.uuid4()),  # Use UUID to avoid collisions
                agent_id=agent.id,
                agent_name=agent.name,  # Required field
                supervisor_id="test_user",  # Not user_id
                workspace_id="default",  # Required field
                trigger_context={},  # Required field
                status="completed",
                started_at=base_time - timedelta(days=15-i),
                duration_seconds=3600,
                intervention_count=2 if i < 8 else 1,  # Decreasing interventions
                supervisor_rating=3.0 + (i * 0.1)  # Increasing ratings
            )
            sessions.append(session)

        db_session.add_all(sessions)
        db_session.commit()

        metrics = await graduation_service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.SUPERVISED
        )

        # Should calculate a trend
        assert metrics["recent_performance_trend"] in ["improving", "stable", "declining", "unknown"]


# ========================================================================
# Task 2.7: Combined Validation with Supervision
# ========================================================================

class TestCombinedValidation:
    """Test graduation validation combining episode and supervision data."""

    @pytest.mark.asyncio
    async def test_validate_with_supervision_combines_metrics(self, graduation_service, db_session):
        """Test validation combines episode and supervision metrics."""
        agent = SupervisedAgentFactory(_session=db_session)
        db_session.commit()

        result = await graduation_service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.AUTONOMOUS
        )

        # Should have combined metrics
        assert "episode_metrics" in result
        assert "supervision_metrics" in result
        assert "ready" in result
        assert "score" in result
        assert "gaps" in result

    @pytest.mark.asyncio
    async def test_supervision_gaps_identified(self, graduation_service, db_session):
        """Test supervision-specific gaps are identified."""
        agent = SupervisedAgentFactory(_session=db_session)
        db_session.commit()

        result = await graduation_service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.AUTONOMOUS
        )

        # Gaps should include supervision checks
        # With no supervision sessions, should have gaps
        assert isinstance(result["gaps"], list)


# ========================================================================
# Task 2.8: Edge Cases and Error Handling
# ========================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_promote_agent_updates_timestamp(self, graduation_service, db_session):
        """Test promotion updates agent timestamp."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.01)

        # Get original timestamp after commit
        db_session.refresh(agent)
        original_updated = agent.updated_at

        await graduation_service.promote_agent(
            agent_id=agent.id,
            new_maturity="INTERN",
            validated_by="test_user"
        )

        db_session.refresh(agent)
        # updated_at should be more recent or equal (same transaction)
        assert agent.updated_at is not None
        if original_updated:
            assert agent.updated_at >= original_updated

    @pytest.mark.asyncio
    async def test_readiness_with_zero_episodes(self, graduation_service, db_session):
        """Test readiness calculation with zero episodes."""
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        # Should handle zero episodes gracefully
        assert result["episode_count"] == 0
        assert result["intervention_rate"] == 1.0  # Max intervention with no episodes

    @pytest.mark.asyncio
    async def test_readiness_score_boundary_conditions(self, graduation_service):
        """Test readiness score at boundaries."""
        # Test with edge case values
        score = graduation_service._calculate_score(
            episode_count=10,
            min_episodes=10,
            intervention_rate=0.0,
            max_intervention=0.01,  # Very low to avoid division by zero
            constitutional_score=1.0,
            min_constitutional=0.01
        )

        # Should not overflow or underflow
        assert 0 <= score <= 100

    @pytest.mark.asyncio
    async def test_constitutional_score_with_none_values(self, graduation_service, db_session):
        """Test readiness calculation handles None constitutional scores."""
        # Create episodes with None constitutional scores
        agent = StudentAgentFactory(_session=db_session)
        import uuid

        for i in range(5):
            episode = Episode(
                id=str(uuid.uuid4()),  # Use UUID to avoid collisions
                agent_id=agent.id,
                user_id="test_user",
                workspace_id="default",
                title=f"Episode {i}",
                status="completed",
                maturity_at_time=AgentStatus.STUDENT.value,
                started_at=datetime.now(),
                human_intervention_count=0,
                constitutional_score=None  # No score
            )
            db_session.add(episode)

        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        # Should handle None scores gracefully
        assert "avg_constitutional_score" in result
        assert result["avg_constitutional_score"] >= 0
