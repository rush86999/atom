"""
Integration tests for Agent Graduation Service exam execution and constitutional validation.

Tests the graduation exam execution, constitutional compliance validation,
intervention rate calculations, and readiness score calculations.

Coverage target: agent_graduation_service.py exam execution and constitutional validation logic
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.agent_graduation_service import AgentGraduationService
from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    EpisodeSegment,
    User,
    UserRole,
)

DEFAULT_TENANT = "default"


def _make_episode(agent_id, index, maturity, interventions=0,
                  constitutional=0.9, success=True, days_ago=None):
    """Build an AgentEpisode row on the current schema (agent_episodes)."""
    started = datetime.now() - timedelta(days=days_ago if days_ago is not None else index + 1)
    return Episode(
        id=f"episode-exam-{agent_id}-{index}",
        agent_id=agent_id,
        tenant_id=DEFAULT_TENANT,
        task_description=f"Exam preparation episode {index}",
        maturity_at_time=maturity,
        outcome="success" if success else "failure",
        success=success,
        status="completed",
        started_at=started,
        completed_at=started + timedelta(hours=1),
        duration_seconds=3600,
        human_intervention_count=interventions,
        constitutional_score=constitutional,
        confidence_score=0.5,
        topics=["training"],
        entities=[],
        importance_score=0.7,
        decay_score=1.0,
        access_count=0,
    )


def _mock_exam_executor(payload):
    """Mock GraduationExamSandboxExecutor whose execute_exam returns payload."""
    executor = MagicMock()
    executor.execute_exam = AsyncMock(return_value=payload)
    return executor


@pytest.fixture(scope="function")
def graduation_service(db_session: Session):
    """Create graduation service instance."""
    return AgentGraduationService(db_session)


@pytest.fixture(scope="function")
def student_agent(db_session: Session):
    """Create a STUDENT maturity agent."""
    agent = AgentRegistry(
        id="student_agent_graduation_test",
        name="Student Agent",
        category="testing",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.4,
        configuration={},
        tenant_id=DEFAULT_TENANT,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def intern_agent(db_session: Session):
    """Create an INTERN maturity agent."""
    agent = AgentRegistry(
        id="intern_agent_graduation_test",
        name="Intern Agent",
        category="testing",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        configuration={},
        tenant_id=DEFAULT_TENANT,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


class TestGraduationExamExecution:
    """Test graduation exam execution with the graduation exam sandbox executor."""

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_for_student_to_intern(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test executing graduation exam for STUDENT → INTERN transition.

        Covers: Graduation exam execution logic
        """
        # Create episodes to meet minimum requirement (10 episodes for STUDENT→INTERN)
        for i in range(10):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=0, constitutional=0.90)
            db_session.add(episode)
        db_session.commit()

        # Mock graduation exam executor
        mock_executor = _mock_exam_executor({
            "success": True,
            "score": 0.85,
            "constitutional_compliance": 0.90,
            "passed": True
        })

        with patch('core.agent_graduation_service.get_graduation_exam_executor',
                   return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
                workspace_id=DEFAULT_TENANT,
                target_maturity=AgentStatus.INTERN.value
            )

        # Verify exam executed
        assert result["exam_completed"] is True
        assert result["score"] >= 0.70  # Minimum passing score
        assert "constitutional_compliance" in result

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_for_intern_to_supervised(
        self, graduation_service, intern_agent, db_session
    ):
        """
        Test executing graduation exam for INTERN → SUPERVISED transition.

        Covers: Higher maturity level exam requirements
        """
        # Create episodes to meet requirement (25 episodes for INTERN→SUPERVISED)
        for i in range(25):
            episode = _make_episode(intern_agent.id, i, AgentStatus.INTERN.value,
                                    # 20% intervention rate
                                    interventions=1 if i % 5 == 0 else 0,
                                    constitutional=0.88)
            db_session.add(episode)
        db_session.commit()

        mock_executor = _mock_exam_executor({
            "success": True,
            "score": 0.88,
            "constitutional_compliance": 0.92,
            "passed": True
        })

        with patch('core.agent_graduation_service.get_graduation_exam_executor',
                   return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=intern_agent.id,
                workspace_id=DEFAULT_TENANT,
                target_maturity=AgentStatus.SUPERVISED.value
            )

        assert result["exam_completed"] is True
        assert result["score"] >= 0.70

    @pytest.mark.asyncio
    async def test_graduation_exam_failure_scenario(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test graduation exam that fails due to low score.

        Covers: Exam failure handling
        """
        # Create minimal episodes
        for i in range(10):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=0, constitutional=0.68)
            db_session.add(episode)
        db_session.commit()

        # Mock exam that fails
        mock_executor = _mock_exam_executor({
            "success": True,
            "score": 0.65,  # Below 0.70 threshold
            "constitutional_compliance": 0.68,
            "passed": False
        })

        with patch('core.agent_graduation_service.get_graduation_exam_executor',
                   return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
                workspace_id=DEFAULT_TENANT,
                target_maturity=AgentStatus.INTERN.value
            )

        assert result["exam_completed"] is True
        assert result["passed"] is False
        assert result["score"] < 0.70

    @pytest.mark.asyncio
    async def test_graduation_exam_insufficient_episodes(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test graduation exam does not pass with insufficient episode count.

        Covers: Episode count validation
        """
        # Create only 5 episodes (need 10 for STUDENT→INTERN); every episode
        # also required an intervention so the exam cannot scrape a pass.
        for i in range(5):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=1, constitutional=0.5)
            db_session.add(episode)
        db_session.commit()

        # Run against the real exam executor (no mocking)
        result = await graduation_service.execute_graduation_exam(
            agent_id=student_agent.id,
            workspace_id=DEFAULT_TENANT,
            target_maturity=AgentStatus.INTERN.value
        )

        assert result["exam_completed"] is True
        assert result["passed"] is False
        assert "insufficient_episode_count" in result["constitutional_violations"]


class TestConstitutionalComplianceValidation:
    """Test constitutional compliance validation against Knowledge Graph rules."""

    @pytest.mark.asyncio
    async def test_constitutional_compliance_high_score(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test agent with high constitutional compliance score.

        Covers: Constitutional validation logic
        """
        # Create episodes with high compliance (0.95+)
        for i in range(10):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=0, constitutional=0.95)
            db_session.add(episode)
        db_session.commit()

        # Mock exam
        mock_executor = _mock_exam_executor({
            "success": True,
            "score": 0.90,
            "constitutional_compliance": 0.95,
            "passed": True,
            "constitutional_violations": []
        })

        with patch('core.agent_graduation_service.get_graduation_exam_executor',
                   return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
                workspace_id=DEFAULT_TENANT,
                target_maturity=AgentStatus.INTERN.value
            )

        assert result["constitutional_compliance"] >= 0.70
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_constitutional_compliance_low_score_failure(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test agent failing due to low constitutional compliance.

        Covers: Constitutional compliance threshold enforcement
        """
        for i in range(10):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=0, constitutional=0.65)
            db_session.add(episode)
        db_session.commit()

        mock_executor = _mock_exam_executor({
            "success": True,
            "score": 0.85,
            "constitutional_compliance": 0.65,  # Below threshold
            "passed": False,
            "constitutional_violations": ["unauthorized_data_access", "privacy_violation"]
        })

        with patch('core.agent_graduation_service.get_graduation_exam_executor',
                   return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
                workspace_id=DEFAULT_TENANT,
                target_maturity=AgentStatus.INTERN.value
            )

        # Should fail due to constitutional compliance
        assert result["constitutional_compliance"] < 0.70
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_constitutional_violations_tracking(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test tracking of specific constitutional violations.

        Covers: Violation reporting in exam results
        """
        for i in range(10):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=i, constitutional=0.60)
            db_session.add(episode)
        db_session.commit()

        violations = [
            "data_leak",
            "unauthorized_api_call",
            "bypass_governance"
        ]

        mock_executor = _mock_exam_executor({
            "success": True,
            "score": 0.75,
            "constitutional_compliance": 0.60,
            "passed": False,
            "constitutional_violations": violations
        })

        with patch('core.agent_graduation_service.get_graduation_exam_executor',
                   return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
                workspace_id=DEFAULT_TENANT,
                target_maturity=AgentStatus.INTERN.value
            )

        assert "constitutional_violations" in result
        assert len(result["constitutional_violations"]) > 0


class TestInterventionRateCalculation:
    """Test intervention rate calculation and thresholds."""

    @pytest.mark.asyncio
    async def test_intervention_rate_student_to_intern(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test intervention rate calculation for STUDENT → INTERN (max 50%).

        Covers: Intervention rate calculation logic
        """
        # Create episodes with 50% intervention rate (5 out of 10)
        for i in range(10):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=1 if i < 5 else 0,
                                    constitutional=0.75)
            db_session.add(episode)
        db_session.commit()

        # Calculate readiness score
        readiness = await graduation_service.calculate_readiness_score(
            agent_id=student_agent.id,
            target_maturity="INTERN"
        )

        score = readiness["score"]  # 0-100 scale
        assert 0.0 <= score <= 100.0
        assert readiness["intervention_rate"] <= 0.5
        # With 50% interventions (the allowed maximum), readiness stays reasonable
        assert score >= 50

    @pytest.mark.asyncio
    async def test_intervention_rate_intern_to_supervised(
        self, graduation_service, intern_agent, db_session
    ):
        """
        Test intervention rate for INTERN → SUPERVISED (max 20%).

        Covers: Stricter intervention threshold for higher maturity
        """
        # Create episodes with 20% intervention rate (5 out of 25)
        for i in range(25):
            episode = _make_episode(intern_agent.id, i, AgentStatus.INTERN.value,
                                    interventions=1 if i % 5 == 0 else 0,
                                    constitutional=0.85)
            db_session.add(episode)
        db_session.commit()

        readiness = await graduation_service.calculate_readiness_score(
            agent_id=intern_agent.id,
            target_maturity="SUPERVISED"
        )

        assert 0.0 <= readiness["score"] <= 100.0
        assert readiness["intervention_rate"] <= 0.2

    @pytest.mark.asyncio
    async def test_intervention_rate_too_high_failure(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test failure when intervention rate exceeds threshold.

        Covers: Intervention threshold enforcement
        """
        # Create episodes with 70% intervention rate (exceeds 50% max)
        for i in range(10):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=1 if i < 7 else 0,  # 7 out of 10
                                    constitutional=0.9)
            db_session.add(episode)
        db_session.commit()

        readiness = await graduation_service.calculate_readiness_score(
            agent_id=student_agent.id,
            target_maturity="INTERN"
        )

        # High intervention rate should lower readiness score and block readiness
        assert readiness["score"] < 70
        assert readiness["ready"] is False
        assert any("intervention" in gap.lower() for gap in readiness["gaps"])


class TestReadinessScoreCalculation:
    """Test readiness score calculation (weighted episode-derived factors)."""

    @pytest.mark.asyncio
    async def test_readiness_score_all_factors_excellent(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test readiness score with excellent metrics across all factors.

        Covers: Complete readiness score calculation
        """
        # Create perfect episodes
        for i in range(15):  # More than minimum 10
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=0,  # 0% intervention rate
                                    constitutional=0.95)
            db_session.add(episode)
        db_session.commit()

        readiness = await graduation_service.calculate_readiness_score(
            agent_id=student_agent.id,
            target_maturity="INTERN"
        )

        # Excellent episodes should clear the STUDENT→INTERN readiness threshold
        assert readiness["score"] >= 70
        assert readiness["ready"] is True

    @pytest.mark.asyncio
    async def test_readiness_score_mixed_factors(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test readiness score with mixed performance across factors.

        Covers: Weighted score calculation
        """
        # Create episodes with mixed performance
        for i in range(10):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=1 if i < 4 else 0,  # 40% intervention rate
                                    constitutional=0.75 + (i * 0.02))
            db_session.add(episode)
        db_session.commit()

        readiness = await graduation_service.calculate_readiness_score(
            agent_id=student_agent.id,
            target_maturity="INTERN"
        )

        # Should be moderate readiness
        assert 50 <= readiness["score"] <= 80

    @pytest.mark.asyncio
    async def test_readiness_score_breakdown(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test that readiness score includes breakdown of factors.

        Covers: Detailed readiness reporting
        """
        for i in range(12):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=i % 3, constitutional=0.8)
            db_session.add(episode)
        db_session.commit()

        readiness = await graduation_service.calculate_readiness_score(
            agent_id=student_agent.id,
            target_maturity="INTERN"
        )

        # Readiness score is a number on the 0-100 scale plus a breakdown dict
        assert isinstance(readiness["score"], (int, float))
        assert 0.0 <= readiness["score"] <= 100.0
        assert "breakdown" in readiness


class TestExamScenarios:
    """Test various exam scenarios for each maturity level transition."""

    @pytest.mark.asyncio
    async def test_supervised_to_autonomous_exam(
        self, graduation_service, db_session
    ):
        """
        Test SUPERVISED → AUTONOMOUS graduation exam.

        Covers: Highest maturity transition requirements
        """
        # Create SUPERVISED agent
        agent = AgentRegistry(
            id="supervised_agent_test",
            name="Supervised Agent",
            category="testing",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8,
            configuration={},
            tenant_id=DEFAULT_TENANT,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Create 50 episodes (required for SUPERVISED→AUTONOMOUS)
        for i in range(50):
            episode = _make_episode(agent.id, i, AgentStatus.SUPERVISED.value,
                                    interventions=0,  # 0% interventions required
                                    constitutional=0.96)
            db_session.add(episode)
        db_session.commit()

        mock_executor = _mock_exam_executor({
            "success": True,
            "score": 0.95,
            "constitutional_compliance": 0.98,
            "passed": True
        })

        with patch('core.agent_graduation_service.get_graduation_exam_executor',
                   return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=agent.id,
                workspace_id=DEFAULT_TENANT,
                target_maturity=AgentStatus.AUTONOMOUS.value
            )

        assert result["exam_completed"] is True
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_exam_execution_error_handling(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test error handling during exam execution.

        Covers: Exception handling in exam execution
        """
        for i in range(10):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=0, constitutional=0.8)
            db_session.add(episode)
        db_session.commit()

        # Mock executor that raises exception
        mock_executor = MagicMock()
        mock_executor.execute_exam = AsyncMock(side_effect=Exception("Executor failure"))

        with patch('core.agent_graduation_service.get_graduation_exam_executor',
                   return_value=mock_executor):
            with pytest.raises(Exception):
                await graduation_service.execute_graduation_exam(
                    agent_id=student_agent.id,
                    workspace_id=DEFAULT_TENANT,
                    target_maturity=AgentStatus.INTERN.value
                )

    @pytest.mark.asyncio
    async def test_exam_multiple_attempts_tracking(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test tracking of multiple exam attempts.

        Covers: Exam attempt history
        """
        for i in range(10):
            episode = _make_episode(student_agent.id, i, AgentStatus.STUDENT.value,
                                    interventions=0, constitutional=0.8)
            db_session.add(episode)
        db_session.commit()

        # First attempt - fail
        mock_executor = _mock_exam_executor({
            "success": True,
            "score": 0.65,
            "constitutional_compliance": 0.68,
            "passed": False,
            "attempt": 1
        })

        with patch('core.agent_graduation_service.get_graduation_exam_executor',
                   return_value=mock_executor):
            result1 = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
                workspace_id=DEFAULT_TENANT,
                target_maturity=AgentStatus.INTERN.value
            )

        assert result1["passed"] is False

        # Second attempt - pass
        mock_executor.execute_exam = AsyncMock(return_value={
            "success": True,
            "score": 0.85,
            "constitutional_compliance": 0.90,
            "passed": True,
            "attempt": 2
        })

        with patch('core.agent_graduation_service.get_graduation_exam_executor',
                   return_value=mock_executor):
            result2 = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
                workspace_id=DEFAULT_TENANT,
                target_maturity=AgentStatus.INTERN.value
            )

        assert result2["passed"] is True
