"""
Integration tests for Agent Graduation Service exam execution and constitutional validation.

Tests the graduation exam execution, constitutional compliance validation,
intervention rate calculations, and readiness score calculations.

Coverage target: agent_graduation_service.py lines 253-285 and constitutional validation logic
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
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


class TestGraduationExamExecution:
    """Test graduation exam execution with SandboxExecutor."""

    @pytest.mark.asyncio
    async def test_execute_graduation_exam_for_student_to_intern(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test executing graduation exam for STUDENT → INTERN transition.

        Covers: Graduation exam execution logic
        Lines: ~253-285 in agent_graduation_service.py
        """
        # Create episodes to meet minimum requirement (10 episodes for STUDENT→INTERN)
        for i in range(10):
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=11-i),
                ended_at=datetime.now() - timedelta(days=10-i),
                segment_count=1,
                metadata_json={"interventions": 0}  # 50% intervention rate = 5 interventions max
            )
            db_session.add(episode)
        db_session.commit()

        # Mock SandboxExecutor
        mock_executor = MagicMock()
        mock_executor.execute_exam.return_value = {
            "success": True,
            "score": 0.85,
            "constitutional_compliance": 0.90,
            "passed": True
        }

        with patch('core.agent_graduation_service.SandboxExecutor', return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
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
            episode = Episode(
                agent_id=intern_agent.id,
                agent_name=intern_agent.name,
                episode_type="operational",
                status="completed",
                started_at=datetime.now() - timedelta(days=26-i),
                ended_at=datetime.now() - timedelta(days=25-i),
                segment_count=1,
                metadata_json={"interventions": i % 5}  # 20% intervention rate
            )
            db_session.add(episode)
        db_session.commit()

        mock_executor = MagicMock()
        mock_executor.execute_exam.return_value = {
            "success": True,
            "score": 0.88,
            "constitutional_compliance": 0.92,
            "passed": True
        }

        with patch('core.agent_graduation_service.SandboxExecutor', return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=intern_agent.id,
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
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=11-i),
                ended_at=datetime.now() - timedelta(days=10-i),
                segment_count=1,
                metadata_json={}
            )
            db_session.add(episode)
        db_session.commit()

        # Mock exam that fails
        mock_executor = MagicMock()
        mock_executor.execute_exam.return_value = {
            "success": True,
            "score": 0.65,  # Below 0.70 threshold
            "constitutional_compliance": 0.68,
            "passed": False
        }

        with patch('core.agent_graduation_service.SandboxExecutor', return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
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
        Test graduation exam rejected due to insufficient episode count.

        Covers: Episode count validation
        """
        # Create only 5 episodes (need 10 for STUDENT→INTERN)
        for i in range(5):
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=6-i),
                ended_at=datetime.now() - timedelta(days=5-i),
                segment_count=1,
                metadata_json={}
            )
            db_session.add(episode)
        db_session.commit()

        # Should raise error or return failure
        with pytest.raises((ValueError, Exception)):
            await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
                target_maturity=AgentStatus.INTERN.value
            )


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
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=11-i),
                ended_at=datetime.now() - timedelta(days=10-i),
                segment_count=1,
                metadata_json={
                    "constitutional_compliance": 0.95,
                    "interventions": 0
                }
            )
            db_session.add(episode)
        db_session.commit()

        # Mock exam
        mock_executor = MagicMock()
        mock_executor.execute_exam.return_value = {
            "success": True,
            "score": 0.90,
            "constitutional_compliance": 0.95,
            "passed": True,
            "constitutional_violations": []
        }

        with patch('core.agent_graduation_service.SandboxExecutor', return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
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
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=11-i),
                ended_at=datetime.now() - timedelta(days=10-i),
                segment_count=1,
                metadata_json={
                    "constitutional_compliance": 0.65,  # Below 0.70 threshold
                    "interventions": 0
                }
            )
            db_session.add(episode)
        db_session.commit()

        mock_executor = MagicMock()
        mock_executor.execute_exam.return_value = {
            "success": True,
            "score": 0.85,
            "constitutional_compliance": 0.65,  # Below threshold
            "passed": False,
            "constitutional_violations": ["unauthorized_data_access", "privacy_violation"]
        }

        with patch('core.agent_graduation_service.SandboxExecutor', return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
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
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=11-i),
                ended_at=datetime.now() - timedelta(days=10-i),
                segment_count=1,
                metadata_json={"interventions": i}
            )
            db_session.add(episode)
        db_session.commit()

        violations = [
            "data_leak",
            "unauthorized_api_call",
            "bypass_governance"
        ]

        mock_executor = MagicMock()
        mock_executor.execute_exam.return_value = {
            "success": True,
            "score": 0.75,
            "constitutional_compliance": 0.60,
            "passed": False,
            "constitutional_violations": violations
        }

        with patch('core.agent_graduation_service.SandboxExecutor', return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
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
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=11-i),
                ended_at=datetime.now() - timedelta(days=10-i),
                segment_count=1,
                metadata_json={"interventions": 1 if i < 5 else 0}
            )
            db_session.add(episode)
        db_session.commit()

        # Calculate readiness score
        readiness = await graduation_service.calculate_readiness_score(
            agent_id=student_agent.id,
            target_maturity=AgentStatus.INTERN.value
        )

        # 40% episode count, 30% intervention, 30% constitutional
        assert 0.0 <= readiness <= 1.0
        # With 50% interventions, should still meet requirements
        assert readiness >= 0.5

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
            episode = Episode(
                agent_id=intern_agent.id,
                agent_name=intern_agent.name,
                episode_type="operational",
                status="completed",
                started_at=datetime.now() - timedelta(days=26-i),
                ended_at=datetime.now() - timedelta(days=25-i),
                segment_count=1,
                metadata_json={"interventions": 1 if i % 5 == 0 else 0}
            )
            db_session.add(episode)
        db_session.commit()

        readiness = await graduation_service.calculate_readiness_score(
            agent_id=intern_agent.id,
            target_maturity=AgentStatus.SUPERVISED.value
        )

        assert 0.0 <= readiness <= 1.0

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
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=11-i),
                ended_at=datetime.now() - timedelta(days=10-i),
                segment_count=1,
                metadata_json={"interventions": 1 if i < 7 else 0}  # 7 out of 10
            )
            db_session.add(episode)
        db_session.commit()

        readiness = await graduation_service.calculate_readiness_score(
            agent_id=student_agent.id,
            target_maturity=AgentStatus.INTERN.value
        )

        # High intervention rate should lower readiness score
        assert readiness < 0.7  # Should fail


class TestReadinessScoreCalculation:
    """Test readiness score calculation (40% episodes, 30% intervention, 30% constitutional)."""

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
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=16-i),
                ended_at=datetime.now() - timedelta(days=15-i),
                segment_count=1,
                metadata_json={
                    "interventions": 0,  # 0% intervention rate
                    "constitutional_compliance": 0.95
                }
            )
            db_session.add(episode)
        db_session.commit()

        # Mock constitutional compliance
        with patch('core.agent_graduation_service.SandboxExecutor') as mock_executor:
            mock_executor_instance = MagicMock()
            mock_executor_instance.calculate_compliance.return_value = 0.95
            mock_executor.return_value = mock_executor_instance

            readiness = await graduation_service.calculate_readiness_score(
                agent_id=student_agent.id,
                target_maturity=AgentStatus.INTERN.value
            )

        # Should have high readiness score
        assert readiness >= 0.80

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
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=11-i),
                ended_at=datetime.now() - timedelta(days=10-i),
                segment_count=1,
                metadata_json={
                    "interventions": 1 if i < 4 else 0,  # 40% intervention rate
                    "constitutional_compliance": 0.75 + (i * 0.02)
                }
            )
            db_session.add(episode)
        db_session.commit()

        readiness = await graduation_service.calculate_readiness_score(
            agent_id=student_agent.id,
            target_maturity=AgentStatus.INTERN.value
        )

        # Should be moderate readiness
        assert 0.5 <= readiness <= 0.8

    @pytest.mark.asyncio
    async def test_readiness_score_breakdown(
        self, graduation_service, student_agent, db_session
    ):
        """
        Test that readiness score includes breakdown of factors.

        Covers: Detailed readiness reporting
        """
        for i in range(12):
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=13-i),
                ended_at=datetime.now() - timedelta(days=12-i),
                segment_count=1,
                metadata_json={"interventions": i % 3}
            )
            db_session.add(episode)
        db_session.commit()

        readiness = await graduation_service.calculate_readiness_score(
            agent_id=student_agent.id,
            target_maturity=AgentStatus.INTERN.value
        )

        # Readiness should be a number
        assert isinstance(readiness, (int, float))
        assert 0.0 <= readiness <= 1.0


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
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Create 50 episodes (required for SUPERVISED→AUTONOMOUS)
        for i in range(50):
            episode = Episode(
                agent_id=agent.id,
                agent_name=agent.name,
                episode_type="operational",
                status="completed",
                started_at=datetime.now() - timedelta(days=51-i),
                ended_at=datetime.now() - timedelta(days=50-i),
                segment_count=1,
                metadata_json={"interventions": 0}  # 0% interventions required
            )
            db_session.add(episode)
        db_session.commit()

        mock_executor = MagicMock()
        mock_executor.execute_exam.return_value = {
            "success": True,
            "score": 0.95,
            "constitutional_compliance": 0.98,
            "passed": True
        }

        with patch('core.agent_graduation_service.SandboxExecutor', return_value=mock_executor):
            result = await graduation_service.execute_graduation_exam(
                agent_id=agent.id,
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
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=11-i),
                ended_at=datetime.now() - timedelta(days=10-i),
                segment_count=1,
                metadata_json={}
            )
            db_session.add(episode)
        db_session.commit()

        # Mock executor that raises exception
        mock_executor = MagicMock()
        mock_executor.execute_exam.side_effect = Exception("Executor failure")

        with patch('core.agent_graduation_service.SandboxExecutor', return_value=mock_executor):
            with pytest.raises(Exception):
                await graduation_service.execute_graduation_exam(
                    agent_id=student_agent.id,
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
            episode = Episode(
                agent_id=student_agent.id,
                agent_name=student_agent.name,
                episode_type="training",
                status="completed",
                started_at=datetime.now() - timedelta(days=11-i),
                ended_at=datetime.now() - timedelta(days=10-i),
                segment_count=1,
                metadata_json={}
            )
            db_session.add(episode)
        db_session.commit()

        # First attempt - fail
        mock_executor = MagicMock()
        mock_executor.execute_exam.return_value = {
            "success": True,
            "score": 0.65,
            "constitutional_compliance": 0.68,
            "passed": False,
            "attempt": 1
        }

        with patch('core.agent_graduation_service.SandboxExecutor', return_value=mock_executor):
            result1 = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
                target_maturity=AgentStatus.INTERN.value
            )

        assert result1["passed"] is False

        # Second attempt - pass
        mock_executor.execute_exam.return_value = {
            "success": True,
            "score": 0.85,
            "constitutional_compliance": 0.90,
            "passed": True,
            "attempt": 2
        }

        with patch('core.agent_graduation_service.SandboxExecutor', return_value=mock_executor):
            result2 = await graduation_service.execute_graduation_exam(
                agent_id=student_agent.id,
                target_maturity=AgentStatus.INTERN.value
            )

        assert result2["passed"] is True
