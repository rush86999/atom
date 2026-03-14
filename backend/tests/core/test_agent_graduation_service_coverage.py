"""
Coverage-driven tests for AgentGraduationService (currently 12.1% -> target 65%+)

Focus areas from coverage report:
- calculate_readiness_score (lines 172-258)
- _calculate_score helper (lines 260-281)
- _generate_recommendation (lines 283-293)
- run_graduation_exam (lines 295-353)
- promote_agent (lines 415-458)
- calculate_supervision_metrics (lines 533-617)
- get_graduation_audit_trail (lines 460-527)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from core.agent_graduation_service import (
    AgentGraduationService,
    SandboxExecutor,
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    SupervisionSession,
)


class TestCalculateReadinessScore:
    """Test calculate_readiness_score method (lines 172-258)."""

    @pytest.fixture
    def graduation_service(self, db_session):
        """Create service with mocked LanceDB."""
        with patch('core.agent_graduation_service.get_lancedb_handler') as mock_lancedb:
            mock_lancedb = MagicMock()
            mock_lancedb.return_value = mock_lancedb
            return AgentGraduationService(db_session)

    @pytest.mark.asyncio
    async def test_readiness_score_for_intern_level(self, graduation_service, db_session):
        """Cover lines 194-258: Full readiness calculation for INTERN target."""
        # Create agent at STUDENT level
        agent = AgentRegistry(
            id="agent-intern-ready",
            tenant_id="tenant-graduation",
            name="Intern Ready Agent",
            status=AgentStatus.STUDENT,
            confidence_score=0.75,
            category="test",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)

        # Create episodes meeting INTERN criteria
        # INTERN needs: 10 episodes, 50% intervention rate, 0.70 constitutional
        for i in range(15):  # Above minimum
            episode = Episode(
                id=f"episode-{i}",
                agent_id="agent-intern-ready",
                tenant_id="tenant-graduation",
                task_description=f"Episode {i}",
                maturity_at_time="student",  # Must match AgentStatus.STUDENT.value
                status="completed",
                started_at=datetime.now(timezone.utc) - timedelta(days=i),
                human_intervention_count=0 if i < 10 else 1,  # Total 5/15 = 33% < 50%
                constitutional_score=0.80,  # Above 0.70 threshold
                outcome="success",
            )
            db_session.add(episode)

        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id="agent-intern-ready",
            target_maturity="INTERN"
        )

        assert result["ready"] is True
        assert result["episode_count"] == 15
        assert result["intervention_rate"] < 0.5
        assert result["avg_constitutional_score"] >= 0.70
        assert result["score"] > 70  # Should be high

    @pytest.mark.asyncio
    async def test_readiness_score_gaps_identified(self, graduation_service, db_session):
        """Cover lines 227-237: Gap identification when criteria not met."""
        agent = AgentRegistry(
            id="agent-not-ready",
            tenant_id="tenant-graduation",
            name="Not Ready Agent",
            status=AgentStatus.INTERN,
            confidence_score=0.6,
            category="test",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)

        # Too few episodes, high interventions, low constitutional
        for i in range(5):  # Below 10 minimum
            episode = Episode(
                id=f"episode-bad-{i}",
                agent_id="agent-not-ready",
                tenant_id="tenant-graduation",
                task_description=f"Episode {i}",
                maturity_at_time="intern",  # Must match AgentStatus.INTERN.value
                status="completed",
                started_at=datetime.now(timezone.utc) - timedelta(days=i),
                human_intervention_count=10,  # Very high
                constitutional_score=0.50,  # Below threshold
                outcome="success",
            )
            db_session.add(episode)

        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id="agent-not-ready",
            target_maturity="SUPERVISED"
        )

        assert result["ready"] is False
        assert len(result["gaps"]) > 0
        assert result["score"] < 50

    @pytest.mark.asyncio
    async def test_readiness_agent_not_found(self, graduation_service):
        """Cover lines 205-206: Agent not found error."""
        result = await graduation_service.calculate_readiness_score(
            agent_id="nonexistent-agent",
            target_maturity="INTERN"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_readiness_unknown_maturity(self, graduation_service, db_session):
        """Cover lines 194-196: Unknown maturity level."""
        agent = AgentRegistry(
            id="agent-unknown",
            tenant_id="tenant-graduation",
            name="Unknown Agent",
            status=AgentStatus.STUDENT,
            category="test",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        result = await graduation_service.calculate_readiness_score(
            agent_id="agent-unknown",
            target_maturity="INVALID_LEVEL"
        )

        assert "error" in result
        assert "unknown" in result["error"].lower()


class TestScoreHelpers:
    """Test score calculation helpers (lines 260-293)."""

    def test_calculate_score_all_criteria_met(self):
        """Cover lines 260-281: Full score when all criteria met."""
        from core.agent_graduation_service import AgentGraduationService

        service = AgentGraduationService(MagicMock())

        score = service._calculate_score(
            episode_count=20,  # 2x min_episodes
            min_episodes=10,
            intervention_rate=0.1,  # Well below max
            max_intervention=0.5,
            constitutional_score=0.95,  # Above min
            min_constitutional=0.70
        )

        # Should be close to 100
        assert score >= 90
        assert score <= 100

    def test_calculate_score_minimal_passing(self):
        """Cover lines 260-281: Score calculation at threshold."""
        from core.agent_graduation_service import AgentGraduationService

        service = AgentGraduationService(MagicMock())

        score = service._calculate_score(
            episode_count=10,  # Exactly minimum
            min_episodes=10,
            intervention_rate=0.5,  # Exactly at max
            max_intervention=0.5,
            constitutional_score=0.70,  # Exactly at min
            min_constitutional=0.70
        )

        # Should be passing (70+)
        assert score >= 70

    def test_generate_recommendation_ready(self):
        """Cover lines 283-293: Recommendation generation."""
        from core.agent_graduation_service import AgentGraduationService

        service = AgentGraduationService(MagicMock())

        rec = service._generate_recommendation(True, 85, "SUPERVISED")
        assert "ready" in rec.lower()
        assert "supervised" in rec.lower()

        rec = service._generate_recommendation(False, 40, "SUPERVISED")
        assert "not ready" in rec.lower() or "training" in rec.lower()

        rec = service._generate_recommendation(False, 70, "SUPERVISED")
        assert "close" in rec.lower() or "address" in rec.lower()


class TestPromoteAgent:
    """Test promote_agent method (lines 415-458)."""

    @pytest.mark.asyncio
    async def test_promote_agent_success(self, db_session):
        """Cover lines 432-457: Successful agent promotion."""
        from core.agent_graduation_service import AgentGraduationService

        agent = AgentRegistry(
            id="agent-promote-me",
            tenant_id="tenant-promote",
            name="Promotable Agent",
            status=AgentStatus.INTERN,
            confidence_score=0.8,
            configuration={"old": "config"},
            category="test",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGraduationService(db_session)

        result = await service.promote_agent(
            agent_id="agent-promote-me",
            new_maturity="SUPERVISED",
            validated_by="user-123"
        )

        assert result is True

        # Verify promotion recorded
        db_session.refresh(agent)
        assert agent.status == AgentStatus.SUPERVISED
        assert agent.configuration["promoted_by"] == "user-123"
        assert "promoted_at" in agent.configuration

    @pytest.mark.asyncio
    async def test_promote_agent_not_found(self, db_session):
        """Cover lines 436-438: Agent not found."""
        from core.agent_graduation_service import AgentGraduationService

        service = AgentGraduationService(db_session)

        result = await service.promote_agent(
            agent_id="nonexistent",
            new_maturity="SUPERVISED",
            validated_by="user-123"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_promote_agent_invalid_level(self, db_session):
        """Cover lines 441-445: Invalid maturity level."""
        from core.agent_graduation_service import AgentGraduationService

        agent = AgentRegistry(
            id="agent-invalid",
            tenant_id="tenant-promote",
            name="Invalid Agent",
            status=AgentStatus.INTERN,
            category="test",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGraduationService(db_session)

        result = await service.promote_agent(
            agent_id="agent-invalid",
            new_maturity="INVALID_STATUS",
            validated_by="user-123"
        )

        assert result is False


class TestSupervisionMetrics:
    """Test calculate_supervision_metrics method (lines 533-617)."""

    @pytest.mark.asyncio
    async def test_supervision_metrics_with_sessions(self, db_session):
        """Cover lines 554-617: Full metrics calculation."""
        from core.agent_graduation_service import AgentGraduationService

        # Create supervision sessions
        agent = AgentRegistry(
            id="agent-supervised",
            tenant_id="tenant-supervision",
            name="Supervised Agent",
            status=AgentStatus.SUPERVISED,
            category="test",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)

        now = datetime.now(timezone.utc)
        for i in range(10):
            session = SupervisionSession(
                id=f"session-{i}",
                agent_id="agent-supervised",
                agent_name="Supervised Agent",
                tenant_id="tenant-supervision",
                workspace_id="workspace-1",
                status="completed",
                started_at=now - timedelta(hours=i+1),
                duration_seconds=3600,  # 1 hour each
                intervention_count=1 if i < 8 else 5,  # Most low intervention
                supervisor_rating=4 if i < 8 else 2,  # Most high rated
                trigger_context={},
                supervisor_id="supervisor-1",
            )
            db_session.add(session)

        db_session.commit()

        service = AgentGraduationService(db_session)
        metrics = await service.calculate_supervision_metrics(
            agent_id="agent-supervised",
            maturity_level=AgentStatus.SUPERVISED
        )

        assert metrics["total_supervision_hours"] == 10.0
        assert metrics["total_sessions"] == 10
        assert metrics["high_rating_sessions"] == 8
        assert metrics["low_intervention_sessions"] == 8
        assert 0 < metrics["average_supervisor_rating"] <= 5

    @pytest.mark.asyncio
    async def test_supervision_metrics_no_sessions(self, db_session):
        """Cover lines 559-569: No sessions returns defaults."""
        from core.agent_graduation_service import AgentGraduationService

        agent = AgentRegistry(
            id="agent-no-supervision",
            tenant_id="tenant-supervision",
            name="No Supervision Agent",
            status=AgentStatus.INTERN,
            category="test",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGraduationService(db_session)
        metrics = await service.calculate_supervision_metrics(
            agent_id="agent-no-supervision",
            maturity_level=AgentStatus.INTERN
        )

        assert metrics["total_supervision_hours"] == 0
        assert metrics["total_sessions"] == 0
        assert metrics["intervention_rate"] == 1.0  # Penalty for no data


class TestPerformanceTrend:
    """Test _calculate_performance_trend method (lines 619-671)."""

    def test_performance_trend_improving(self, db_session):
        """Cover lines 628-671: Detecting improving trend."""
        from core.agent_graduation_service import AgentGraduationService

        service = AgentGraduationService(db_session)

        # Create 10 sessions with improving ratings
        sessions = []
        now = datetime.now(timezone.utc)
        for i in range(10):
            session = SupervisionSession(
                id=f"session-trend-{i}",
                agent_id="agent-trend",
                agent_name="Trend Agent",
                tenant_id="tenant-trend",
                workspace_id="workspace-1",
                status="completed",
                started_at=now - timedelta(hours=10-i),
                supervisor_rating=2 + i * 0.3,  # Improving: 2 -> 5
                intervention_count=10 - i,  # Decreasing interventions
                trigger_context={},
                supervisor_id="supervisor-1",
            )
            sessions.append(session)

        trend = service._calculate_performance_trend(sessions)

        assert trend == "improving"

    def test_performance_trend_declining(self, db_session):
        """Cover lines 619-671: Detecting declining trend."""
        from core.agent_graduation_service import AgentGraduationService

        service = AgentGraduationService(db_session)

        # Create 10 sessions with declining ratings
        sessions = []
        now = datetime.now(timezone.utc)
        for i in range(10):
            session = SupervisionSession(
                id=f"session-declining-{i}",
                agent_id="agent-declining",
                agent_name="Declining Agent",
                tenant_id="tenant-declining",
                workspace_id="workspace-1",
                status="completed",
                started_at=now - timedelta(hours=10-i),
                supervisor_rating=5 - i * 0.3,  # Declining
                intervention_count=i,
                trigger_context={},
                supervisor_id="supervisor-1",
            )
            sessions.append(session)

        trend = service._calculate_performance_trend(sessions)

        assert trend == "declining"

    def test_performance_trend_insufficient_data(self, db_session):
        """Cover lines 628-629: Returns stable with <10 sessions."""
        from core.agent_graduation_service import AgentGraduationService

        service = AgentGraduationService(db_session)

        sessions = []
        for i in range(5):
            session = SupervisionSession(
                id=f"session-few-{i}",
                agent_id="agent-few",
                agent_name="Few Agent",
                tenant_id="tenant-few",
                workspace_id="workspace-1",
                status="completed",
                started_at=datetime.now(timezone.utc) - timedelta(hours=i),
                supervisor_rating=4,
                trigger_context={},
                supervisor_id="supervisor-1",
            )
            sessions.append(session)

        trend = service._calculate_performance_trend(sessions)

        assert trend == "stable"


class TestGraduationAuditTrail:
    """Test get_graduation_audit_trail method (lines 460-527)."""

    @pytest.mark.asyncio
    async def test_audit_trail_full_history(self, db_session):
        """Cover lines 480-527: Complete audit trail generation."""
        from core.agent_graduation_service import AgentGraduationService

        agent = AgentRegistry(
            id="agent-audit",
            tenant_id="tenant-audit",
            name="Audit Agent",
            status=AgentStatus.SUPERVISED,
            category="test",
            module_path="test.module",
            class_name="TestClass",
        )
        db_session.add(agent)

        # Create episodes across maturity levels
        for maturity in ["intern", "supervised"]:
            for i in range(5):
                episode = Episode(
                    id=f"episode-{maturity}-{i}",
                    agent_id="agent-audit",
                    tenant_id="tenant-audit",
                    task_description=f"{maturity} Episode {i}",
                    maturity_at_time=maturity,  # Use lowercase to match enum values
                    status="completed",
                    started_at=datetime.now(timezone.utc) - timedelta(days=10-i),
                    human_intervention_count=i,
                    constitutional_score=0.7 + i * 0.05,
                    outcome="success",
                )
                db_session.add(episode)

        db_session.commit()

        service = AgentGraduationService(db_session)
        trail = await service.get_graduation_audit_trail("agent-audit")

        assert trail["agent_id"] == "agent-audit"
        assert trail["agent_name"] == "Audit Agent"
        assert trail["total_episodes"] == 10
        assert trail["total_interventions"] == sum(range(5)) * 2  # Both maturity levels
        assert "INTERN" in trail["episodes_by_maturity"]
        assert "SUPERVISED" in trail["episodes_by_maturity"]
        assert trail["episodes_by_maturity"]["INTERN"] == 5

    @pytest.mark.asyncio
    async def test_audit_trail_agent_not_found(self, db_session):
        """Cover lines 484-486: Agent not found."""
        from core.agent_graduation_service import AgentGraduationService

        service = AgentGraduationService(db_session)
        trail = await service.get_graduation_audit_trail("nonexistent")

        assert "error" in trail
        assert "not found" in trail["error"].lower()
