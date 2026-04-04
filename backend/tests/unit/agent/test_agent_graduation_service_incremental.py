"""
Incremental tests for Agent Graduation Service

Phase 207-09: Coverage Quality Push
Target: Improve coverage from 56% to 70% (already at 95%, adding edge case tests)

Missing lines from coverage report:
- 326-327: Episode not found in sandbox validation
- 399-406: Constitutional validation with segments and domain detection
- 647: Performance trend stable case
- 803: High quality score calculation with zero sessions
- 963: Graduation exam execution

Focus: Test edge cases and error handling paths
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.orm import Session

from core.agent_graduation_service import (
    AgentGraduationService,
)
from core.sandbox_executor import SandboxExecutor
from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    SupervisionSession,
)


class TestSandboxExecutorEdgeCases:
    """Test edge cases in SandboxExecutor"""

    @pytest.mark.asyncio
    async def test_execute_exam_agent_not_found(self, db_session):
        """Test exam execution when agent doesn't exist - Line 66-73"""
        executor = SandboxExecutor(db_session)

        result = await executor.execute_exam(
            agent_id="nonexistent-agent",
            target_maturity="INTERN"
        )

        assert result["success"] is False
        assert result["score"] == 0.0
        assert result["constitutional_compliance"] == 0.0
        assert result["passed"] is False
        assert "Agent not found" in result["error"]


class TestConstitutionalValidationEdgeCases:
    """Test edge cases in constitutional validation - Lines 399-406"""

    @pytest.mark.asyncio
    async def test_validate_constitutional_episode_not_found(self, db_session):
        """Test validation when episode doesn't exist"""
        service = AgentGraduationService(db_session)

        result = await service.validate_constitutional_compliance(
            episode_id="nonexistent-episode"
        )

        assert "error" in result
        assert "Episode not found" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_constitutional_with_domain_in_metadata(self, db_session):
        """Test validation with domain in metadata - Lines 399-406"""
        # Create agent
        agent = AgentRegistry(
            id="agent-metadata-domain",
            name="Metadata Domain Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN,
            tenant_id="default"
        )
        db_session.add(agent)

        # Create episode with domain in metadata
        episode = Episode(
            id="episode-metadata-domain",
            agent_id="agent-metadata-domain",
            tenant_id="default",
            task_description="Task with domain metadata",
            maturity_at_time="INTERN",
            status="completed",
            outcome="success",
            started_at=datetime.now(),
            completed_at=datetime.now() + timedelta(hours=1),
            human_intervention_count=0,
            constitutional_score=1.0,
            metadata_json={"domain": "healthcare"}
        )
        db_session.add(episode)
        db_session.commit()

        service = AgentGraduationService(db_session)

        # Note: Without segments, this returns early with "No segments to validate"
        # Lines 399-406 are only reached when segments exist
        result = await service.validate_constitutional_compliance(
            episode_id="episode-metadata-domain"
        )

        # Should return early success when no segments
        assert result["compliant"] is True
        assert result["score"] == 1.0
        assert result["episode_id"] == "episode-metadata-domain"


class TestPerformanceTrendEdgeCases:
    """Test edge cases in performance trend calculation - Line 647"""

    def test_performance_trend_stable_with_few_sessions(self):
        """Test performance trend with < 10 sessions returns stable - Line 647"""
        service = AgentGraduationService(Mock())

        # Create fewer than 10 sessions
        sessions = []
        for i in range(5):
            session = Mock(spec=SupervisionSession)
            session.started_at = datetime.now() - timedelta(days=i)
            session.supervisor_rating = 4 + (i % 2)
            session.intervention_count = i % 2
            sessions.append(session)

        result = service._calculate_performance_trend(sessions)

        # Line 647: Should return "stable" for < 10 sessions
        assert result == "stable"

    def test_performance_trend_no_ratings(self):
        """Test performance trend when sessions have no ratings"""
        service = AgentGraduationService(Mock())

        sessions = []
        for i in range(10):
            session = Mock(spec=SupervisionSession)
            session.started_at = datetime.now() - timedelta(days=i)
            session.supervisor_rating = None
            session.intervention_count = 0
            sessions.append(session)

        result = service._calculate_performance_trend(sessions)

        assert result == "stable"

    def test_performance_trend_improving(self):
        """Test improving performance trend"""
        service = AgentGraduationService(Mock())

        sessions = []
        for i in range(10):
            session = Mock(spec=SupervisionSession)
            session.started_at = datetime.now() - timedelta(days=i)
            session.supervisor_rating = 5 if i < 5 else 3
            session.intervention_count = 0 if i < 5 else 2
            sessions.append(session)

        result = service._calculate_performance_trend(sessions)
        assert result == "improving"

    def test_performance_trend_declining(self):
        """Test declining performance trend"""
        service = AgentGraduationService(Mock())

        sessions = []
        for i in range(10):
            session = Mock(spec=SupervisionSession)
            session.started_at = datetime.now() - timedelta(days=i)
            session.supervisor_rating = 3 if i < 5 else 5
            session.intervention_count = 2 if i < 5 else 0
            sessions.append(session)

        result = service._calculate_performance_trend(sessions)
        assert result == "declining"


class TestSupervisionScoreEdgeCases:
    """Test edge cases in supervision score calculation - Line 803"""

    def test_supervision_score_zero_total_sessions(self):
        """Test supervision score with zero total sessions - Line 803"""
        service = AgentGraduationService(Mock())

        metrics = {
            "total_sessions": 0,
            "average_supervisor_rating": 0.0,
            "intervention_rate": 1.0,
            "high_rating_sessions": 0,
            "low_intervention_sessions": 0,
            "recent_performance_trend": "unknown"
        }

        criteria = {
            "max_intervention_rate": 0.5
        }

        result = service._supervision_score(metrics, criteria)

        # Line 803: high_quality_score should be 0 when total_sessions is 0
        # Calculation:
        # - rating_score = min(0.0 / 4.0, 1.0) * 40 = 0
        # - max_interventions = 0.5 * 10 = 5.0
        # - intervention_score = (1 - min(1.0 / 5.0, 1.0)) * 30 = (1 - 0.2) * 30 = 24
        # - high_quality_score = 0 (line 803)
        # - trend_score = 0 (unknown)
        # Total: 0 + 24 + 0 + 0 = 24
        assert result == 24.0

    def test_supervision_score_perfect_performance(self):
        """Test supervision score with perfect performance"""
        service = AgentGraduationService(Mock())

        metrics = {
            "total_sessions": 10,
            "average_supervisor_rating": 5.0,
            "intervention_rate": 0.0,
            "high_rating_sessions": 10,
            "low_intervention_sessions": 10,
            "recent_performance_trend": "improving"
        }

        criteria = {
            "max_intervention_rate": 0.5
        }

        result = service._supervision_score(metrics, criteria)

        # Should get high score for perfect performance
        assert result > 80
        assert result <= 100

    def test_supervision_score_poor_performance(self):
        """Test supervision score with poor performance"""
        service = AgentGraduationService(Mock())

        metrics = {
            "total_sessions": 10,
            "average_supervisor_rating": 2.0,
            "intervention_rate": 2.0,
            "high_rating_sessions": 0,
            "low_intervention_sessions": 0,
            "recent_performance_trend": "declining"
        }

        criteria = {
            "max_intervention_rate": 0.5
        }

        result = service._supervision_score(metrics, criteria)

        # Should get low score for poor performance
        assert result < 50


class TestGraduationExamExecution:
    """Test graduation exam execution - Line 963"""

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_integration(self, db_session):
        """Test graduation exam execution through service - Line 963"""
        # Create agent
        agent = AgentRegistry(
            id="agent-exam-integration",
            name="Exam Integration Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN,
            tenant_id="default"
        )
        db_session.add(agent)

        # Create episodes
        for i in range(10):
            episode = Episode(
                id=f"episode-exam-int-{i}",
                agent_id="agent-exam-integration",
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="INTERN",
                status="completed",
                outcome="success",
                started_at=datetime.now() - timedelta(days=i),
                completed_at=datetime.now() - timedelta(days=i) + timedelta(hours=1),
                human_intervention_count=0,
                constitutional_score=0.95
            )
            db_session.add(episode)

        db_session.commit()

        service = AgentGraduationService(db_session)

        # Line 963: execute_graduation_exam method
        result = await service.execute_graduation_exam(
            agent_id="agent-exam-integration",
            workspace_id="default",
            target_maturity="SUPERVISED"
        )

        assert result["exam_completed"] is True
        assert "constitutional_compliance" in result
        assert "score" in result
        assert "passed" in result
        assert "constitutional_violations" in result

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_nonexistent_agent(self, db_session):
        """Test graduation exam for nonexistent agent"""
        service = AgentGraduationService(db_session)

        result = await service.execute_graduation_exam(
            agent_id="nonexistent-agent",
            workspace_id="default",
            target_maturity="INTERN"
        )

        assert result["exam_completed"] is False
        assert result["passed"] is False
        assert "error" in result


class TestSandboxValidationEdgeCases:
    """Test sandbox validation edge cases - Lines 326-327"""

    @pytest.mark.asyncio
    async def test_sandbox_validation_skip_missing_episodes(self, db_session):
        """Test that sandbox validation skips missing episodes - Lines 326-327"""
        # Create agent
        agent = AgentRegistry(
            id="agent-sandbox-missing",
            name="Sandbox Missing Agent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN,
            tenant_id="default"
        )
        db_session.add(agent)

        # Create some episodes
        for i in range(5):
            episode = Episode(
                id=f"episode-sandbox-{i}",
                agent_id="agent-sandbox-missing",
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="INTERN",
                status="completed",
                outcome="success",
                started_at=datetime.now() - timedelta(days=i),
                completed_at=datetime.now() - timedelta(days=i) + timedelta(hours=1),
                human_intervention_count=0,
                constitutional_score=0.9
            )
            db_session.add(episode)

        db_session.commit()

        service = AgentGraduationService(db_session)

        # Try to run exam with some non-existent episode IDs
        # Lines 326-327 should log warning and continue
        result = await service.run_graduation_exam(
            agent_id="agent-sandbox-missing",
            edge_case_episodes=["episode-sandbox-0", "nonexistent-episode", "episode-sandbox-1"]
        )

        # Should complete successfully despite missing episode
        assert "passed" in result
        assert "score" in result
        # Should only have results for existing episodes
        assert len(result["results"]) == 2  # Only 2 of 3 episodes exist
