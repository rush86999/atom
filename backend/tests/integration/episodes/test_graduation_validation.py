"""
Integration tests for Graduation Exam and Constitutional Validation

Tests cover:
1. Graduation exam execution with SandboxExecutor
2. Constitutional compliance validation against Knowledge Graph rules
3. Episode-based readiness score calculation
4. Intervention rate calculation from episode history
5. Graduation scenarios for each maturity level

Tests validate the complete graduation pathway with episodic memory integration.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.agent_graduation_service import AgentGraduationService, AgentStatus
from core.models import (
    AgentRegistry,
    AgentExecution,
    Episode,
    EpisodeSegment,
    SupervisionSession,
    User,
)


# ============================================================================
# Test Configuration
# ============================================================================

@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    from core.models import Base
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_user(test_db):
    """Create sample user."""
    user = User(
        id="user-grad-123",
        email="graduation@test.com",
        name="Graduation Test User"
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def student_agent(test_db):
    """Create STUDENT level agent."""
    agent = AgentRegistry(
        id="agent-student-001",
        name="StudentAgent",
        status=AgentStatus.STUDENT,
        description="Student agent for graduation testing"
    )
    test_db.add(agent)
    test_db.commit()
    return agent


@pytest.fixture
def intern_agent(test_db):
    """Create INTERN level agent."""
    agent = AgentRegistry(
        id="agent-intern-001",
        name="InternAgent",
        status=AgentStatus.INTERN,
        description="Intern agent for graduation testing"
    )
    test_db.add(agent)
    test_db.commit()
    return agent


@pytest.fixture
def supervised_agent(test_db):
    """Create SUPERVISED level agent."""
    agent = AgentRegistry(
        id="agent-supervised-001",
        name="SupervisedAgent",
        status=AgentStatus.SUPERVISED,
        description="Supervised agent for graduation testing"
    )
    test_db.add(agent)
    test_db.commit()
    return agent


@pytest.fixture
def episodes_for_student_to_intern(test_db, student_agent, sample_user):
    """Create episodes meeting STUDENT->INTERN criteria."""
    now = datetime.now()
    episodes = []

    # STUDENT->INTERN: 10 episodes, 50% intervention rate, 0.70 constitutional score
    for i in range(12):  # 12 episodes (more than minimum 10)
        episode = Episode(
            id=f"episode-student-{i}",
            title=f"Student Learning Episode {i}",
            description=f"Learning task {i}",
            summary=f"Completed learning task {i}",
            agent_id=student_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=["learning", "training"],
            entities=[],
            importance_score=0.7,
            status="completed",
            started_at=now - timedelta(days=i * 2),
            ended_at=now - timedelta(days=i * 2) + timedelta(hours=1),
            duration_seconds=3600,
            maturity_at_time="STUDENT",
            human_intervention_count=1 if i % 2 == 0 else 0,  # ~50% intervention rate
            human_edits=[],
            constitutional_score=0.75,  # Above 0.70 threshold
            decay_score=1.0,
            access_count=5
        )
        test_db.add(episode)
        episodes.append(episode)

    test_db.commit()
    return episodes


@pytest.fixture
def episodes_for_intern_to_supervised(test_db, intern_agent, sample_user):
    """Create episodes meeting INTERN->SUPERVISED criteria."""
    now = datetime.now()
    episodes = []

    # INTERN->SUPERVISED: 25 episodes, 20% intervention rate, 0.85 constitutional score
    for i in range(28):  # 28 episodes (more than minimum 25)
        episode = Episode(
            id=f"episode-intern-{i}",
            title=f"Intern Practice Episode {i}",
            description=f"Practice task {i}",
            summary=f"Completed practice task {i}",
            agent_id=intern_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=["practice", "automation"],
            entities=[],
            importance_score=0.8,
            status="completed",
            started_at=now - timedelta(days=i),
            ended_at=now - timedelta(days=i) + timedelta(hours=1),
            duration_seconds=3600,
            maturity_at_time="INTERN",
            # 20% intervention rate = 1 in 5 episodes
            human_intervention_count=1 if i % 5 == 0 else 0,
            human_edits=[],
            constitutional_score=0.88,  # Above 0.85 threshold
            decay_score=1.0,
            access_count=8
        )
        test_db.add(episode)
        episodes.append(episode)

    test_db.commit()
    return episodes


@pytest.fixture
def episodes_for_supervised_to_autonomous(test_db, supervised_agent, sample_user):
    """Create episodes meeting SUPERVISED->AUTONOMOUS criteria."""
    now = datetime.now()
    episodes = []

    # SUPERVISED->AUTONOMOUS: 50 episodes, 0% intervention rate, 0.95 constitutional score
    for i in range(52):  # 52 episodes (more than minimum 50)
        episode = Episode(
            id=f"episode-supervised-{i}",
            title=f"Supervised Execution Episode {i}",
            description=f"Execution task {i}",
            summary=f"Completed execution task {i}",
            agent_id=supervised_agent.id,
            user_id=sample_user.id,
            workspace_id="default",
            topics=["execution", "automation"],
            entities=[],
            importance_score=0.9,
            status="completed",
            started_at=now - timedelta(days=i * 0.5),
            ended_at=now - timedelta(days=i * 0.5) + timedelta(hours=1),
            duration_seconds=3600,
            maturity_at_time="SUPERVISED",
            human_intervention_count=0,  # 0% intervention rate required
            human_edits=[],
            constitutional_score=0.96,  # Above 0.95 threshold
            decay_score=1.0,
            access_count=10
        )
        test_db.add(episode)
        episodes.append(episode)

    test_db.commit()
    return episodes


# ============================================================================
# Graduation Exam Execution Tests
# ============================================================================

class TestGraduationExamExecution:
    """Test graduation exam execution with SandboxExecutor."""

    @pytest.mark.asyncio
    async def test_graduation_exam_student_to_intern(self, test_db, student_agent,
                                                       episodes_for_student_to_intern):
        """Test graduation exam for STUDENT->INTERN promotion."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            # Mock sandbox executor
            mock_sandbox_result = Mock()
            mock_sandbox_result.passed = True
            mock_sandbox_result.interventions = []
            mock_sandbox_result.safety_violations = []
            mock_sandbox_result.replayed_actions = 5

            mock_executor = Mock()
            mock_executor.execute_in_sandbox = AsyncMock(return_value=mock_sandbox_result)

            with patch('core.agent_graduation_service.get_sandbox_executor', return_value=mock_executor):
                # Run graduation exam with edge case episodes
                edge_case_ids = [ep.id for ep in episodes_for_student_to_intern[:3]]

                result = await service.run_graduation_exam(
                    agent_id=student_agent.id,
                    edge_case_episodes=edge_case_ids
                )

                assert "passed" in result
                assert "score" in result
                assert "results" in result
                assert "total_cases" in result

                # Should pass all cases
                assert result["total_cases"] == len(edge_case_ids)

    @pytest.mark.asyncio
    async def test_graduation_exam_with_interventions(self, test_db, supervised_agent):
        """Test graduation exam that requires interventions."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            # Mock sandbox with interventions
            mock_sandbox_result = Mock()
            mock_sandbox_result.passed = False  # Failed due to interventions
            mock_sandbox_result.interventions = [
                {"type": "safety", "reason": "Unsafe action detected"}
            ]
            mock_sandbox_result.safety_violations = []
            mock_sandbox_result.replayed_actions = 3

            mock_executor = Mock()
            mock_executor.execute_in_sandbox = AsyncMock(return_value=mock_sandbox_result)

            with patch('core.agent_graduation_service.get_sandbox_executor', return_value=mock_executor):
                result = await service.run_graduation_exam(
                    agent_id=supervised_agent.id,
                    edge_case_episodes=["episode-1"]
                )

                assert result["passed"] is False
                assert len(result["results"]) == 1
                assert result["results"][0]["interventions"] > 0

    @pytest.mark.asyncio
    async def test_graduation_exam_with_safety_violations(self, test_db, supervised_agent):
        """Test graduation exam with safety violations."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            # Mock sandbox with safety violations
            mock_sandbox_result = Mock()
            mock_sandbox_result.passed = False
            mock_sandbox_result.interventions = []
            mock_sandbox_result.safety_violations = [
                {"type": "data_leak", "severity": "high"}
            ]
            mock_sandbox_result.replayed_actions = 2

            mock_executor = Mock()
            mock_executor.execute_in_sandbox = AsyncMock(return_value=mock_sandbox_result)

            with patch('core.agent_graduation_service.get_sandbox_executor', return_value=mock_executor):
                result = await service.run_graduation_exam(
                    agent_id=supervised_agent.id,
                    edge_case_episodes=["episode-2"]
                )

                assert result["passed"] is False
                assert result["results"][0]["safety_violations"]


# ============================================================================
# Constitutional Compliance Validation Tests
# ============================================================================

class TestConstitutionalValidation:
    """Test constitutional compliance validation."""

    @pytest.mark.asyncio
    async def test_validate_constitutional_compliance_passing(self, test_db,
                                                                sample_user,
                                                                supervised_agent):
        """Test validation of compliant episode."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            # Create episode with segments
            episode = Episode(
                id="episode-compliant-001",
                title="Compliant Episode",
                description="Follows all rules",
                summary="Compliant execution",
                agent_id=supervised_agent.id,
                user_id=sample_user.id,
                workspace_id="default",
                topics=["compliance"],
                entities=[],
                importance_score=0.9,
                status="completed",
                started_at=datetime.now() - timedelta(days=1),
                ended_at=datetime.now() - timedelta(days=1) + timedelta(hours=1),
                maturity_at_time="SUPERVISED",
                human_intervention_count=0,
                constitutional_score=0.98,
                decay_score=1.0,
                access_count=10
            )
            test_db.add(episode)

            # Add compliant segments
            for i in range(3):
                segment = EpisodeSegment(
                    id=f"segment-compliant-{i}",
                    episode_id=episode.id,
                    segment_type="execution",
                    sequence_order=i,
                    content=f"Compliant action {i}",
                    content_summary=f"Action {i}",
                    source_type="agent_execution",
                    source_id=f"exec-{i}"
                )
                test_db.add(segment)

            test_db.commit()

            # Mock constitutional validator
            mock_validator = Mock()
            mock_validator.validate_actions = Mock(return_value={
                "compliant": True,
                "score": 0.98,
                "violations": [],
                "total_actions": 3,
                "checked_actions": 3
            })

            with patch('core.agent_graduation_service.ConstitutionalValidator', return_value=mock_validator):
                result = await service.validate_constitutional_compliance(episode.id)

                assert result["compliant"] is True
                assert result["score"] >= 0.95
                assert len(result["violations"]) == 0

    @pytest.mark.asyncio
    async def test_validate_constitutional_compliance_failing(self, test_db,
                                                               sample_user,
                                                               supervised_agent):
        """Test validation of non-compliant episode."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            # Create non-compliant episode
            episode = Episode(
                id="episode-noncompliant-001",
                title="Non-Compliant Episode",
                description="Violates rules",
                summary="Non-compliant execution",
                agent_id=supervised_agent.id,
                user_id=sample_user.id,
                workspace_id="default",
                topics=["violation"],
                entities=[],
                importance_score=0.5,
                status="completed",
                started_at=datetime.now() - timedelta(days=1),
                ended_at=datetime.now() - timedelta(days=1) + timedelta(hours=1),
                maturity_at_time="SUPERVISED",
                human_intervention_count=2,
                constitutional_score=0.65,
                decay_score=1.0,
                access_count=5
            )
            test_db.add(episode)

            # Add non-compliant segments
            for i in range(3):
                segment = EpisodeSegment(
                    id=f"segment-violation-{i}",
                    episode_id=episode.id,
                    segment_type="execution",
                    sequence_order=i,
                    content=f"Violation action {i}",
                    content_summary=f"Violation {i}",
                    source_type="agent_execution",
                    source_id=f"exec-{i}"
                )
                test_db.add(segment)

            test_db.commit()

            # Mock constitutional validator
            mock_validator = Mock()
            mock_validator.validate_actions = Mock(return_value={
                "compliant": False,
                "score": 0.65,
                "violations": [
                    "PII data exposed in output",
                    "Missing data encryption"
                ],
                "total_actions": 3,
                "checked_actions": 3
            })

            with patch('core.agent_graduation_service.ConstitutionalValidator', return_value=mock_validator):
                result = await service.validate_constitutional_compliance(episode.id)

                assert result["compliant"] is False
                assert result["score"] < 0.70
                assert len(result["violations"]) > 0

    @pytest.mark.asyncio
    async def test_validate_constitutional_no_segments(self, test_db, supervised_agent):
        """Test validation when episode has no segments."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            # Create episode with no segments
            episode = Episode(
                id="episode-no-segments-001",
                title="No Segments Episode",
                description="No segments to validate",
                summary="Empty episode",
                agent_id=supervised_agent.id,
                user_id="test-user",
                workspace_id="default",
                topics=["test"],
                entities=[],
                importance_score=0.5,
                status="completed",
                started_at=datetime.now() - timedelta(days=1),
                ended_at=datetime.now() - timedelta(days=1) + timedelta(hours=1),
                maturity_at_time="SUPERVISED",
                human_intervention_count=0,
                constitutional_score=None,
                decay_score=1.0,
                access_count=0
            )
            test_db.add(episode)
            test_db.commit()

            result = await service.validate_constitutional_compliance(episode.id)

            # Should handle gracefully
            assert "compliant" in result
            assert result.get("note") == "No segments to validate"


# ============================================================================
# Readiness Score Calculation Tests
# ============================================================================

class TestReadinessScoreCalculation:
    """Test episode-based readiness score calculation."""

    @pytest.mark.asyncio
    async def test_readiness_score_student_ready(self, test_db, student_agent,
                                                   episodes_for_student_to_intern):
        """Test readiness score for STUDENT agent ready for INTERN."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            result = await service.calculate_readiness_score(
                agent_id=student_agent.id,
                target_maturity="INTERN"
            )

            assert "ready" in result
            assert "score" in result
            assert "episode_count" in result
            assert "intervention_rate" in result
            assert "avg_constitutional_score" in result
            assert "gaps" in result

            # Should meet INTERN criteria
            assert result["episode_count"] >= 10
            assert result["avg_constitutional_score"] >= 0.70

    @pytest.mark.asyncio
    async def test_readiness_score_not_enough_episodes(self, test_db, student_agent):
        """Test readiness score when episode count is insufficient."""
        mock_lancedb = Mock()

        # Create only 5 episodes (need 10)
        now = datetime.now()
        for i in range(5):
            episode = Episode(
                id=f"episode-few-{i}",
                title=f"Episode {i}",
                description="Test",
                summary="Test",
                agent_id=student_agent.id,
                user_id="test-user",
                workspace_id="default",
                topics=["test"],
                entities=[],
                importance_score=0.7,
                status="completed",
                started_at=now - timedelta(days=i),
                ended_at=now - timedelta(days=i) + timedelta(hours=1),
                maturity_at_time="STUDENT",
                human_intervention_count=0,
                constitutional_score=0.9,
                decay_score=1.0,
                access_count=0
            )
            test_db.add(episode)
        test_db.commit()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            result = await service.calculate_readiness_score(
                agent_id=student_agent.id,
                target_maturity="INTERN"
            )

            assert result["ready"] is False
            assert any("episode" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_readiness_score_intervention_rate_too_high(self, test_db, intern_agent):
        """Test readiness score when intervention rate is too high."""
        mock_lancedb = Mock()

        # Create episodes with 60% intervention rate (need <50%)
        now = datetime.now()
        for i in range(15):
            episode = Episode(
                id=f"episode-high-intervention-{i}",
                title=f"Episode {i}",
                description="Test",
                summary="Test",
                agent_id=intern_agent.id,
                user_id="test-user",
                workspace_id="default",
                topics=["test"],
                entities=[],
                importance_score=0.7,
                status="completed",
                started_at=now - timedelta(days=i),
                ended_at=now - timedelta(days=i) + timedelta(hours=1),
                maturity_at_time="INTERN",
                human_intervention_count=1,  # 100% intervention rate
                constitutional_score=0.9,
                decay_score=1.0,
                access_count=0
            )
            test_db.add(episode)
        test_db.commit()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            result = await service.calculate_readiness_score(
                agent_id=intern_agent.id,
                target_maturity="SUPERVISED"
            )

            assert result["ready"] is False
            assert any("intervention" in gap.lower() for gap in result["gaps"])


# ============================================================================
# Graduation Scenarios Tests
# ============================================================================

class TestGraduationScenarios:
    """Test graduation scenarios for each maturity level."""

    @pytest.mark.asyncio
    async def test_student_to_intern_promotion(self, test_db, student_agent,
                                                episodes_for_student_to_intern):
        """Test complete STUDENT->INTERN promotion scenario."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            # Check readiness
            readiness = await service.calculate_readiness_score(
                agent_id=student_agent.id,
                target_maturity="INTERN"
            )

            # Verify criteria
            assert readiness["episode_count"] >= 10
            assert readiness["intervention_rate"] <= 0.5
            assert readiness["avg_constitutional_score"] >= 0.70

    @pytest.mark.asyncio
    async def test_intern_to_supervised_promotion(self, test_db, intern_agent,
                                                   episodes_for_intern_to_supervised):
        """Test complete INTERN->SUPERVISED promotion scenario."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            # Check readiness
            readiness = await service.calculate_readiness_score(
                agent_id=intern_agent.id,
                target_maturity="SUPERVISED"
            )

            # Verify criteria
            assert readiness["episode_count"] >= 25
            assert readiness["intervention_rate"] <= 0.2
            assert readiness["avg_constitutional_score"] >= 0.85

    @pytest.mark.asyncio
    async def test_supervised_to_autonomous_promotion(self, test_db, supervised_agent,
                                                       episodes_for_supervised_to_autonomous):
        """Test complete SUPERVISED->AUTONOMOUS promotion scenario."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            # Check readiness
            readiness = await service.calculate_readiness_score(
                agent_id=supervised_agent.id,
                target_maturity="AUTONOMOUS"
            )

            # Verify criteria
            assert readiness["episode_count"] >= 50
            assert readiness["intervention_rate"] == 0.0
            assert readiness["avg_constitutional_score"] >= 0.95

    @pytest.mark.asyncio
    async def test_promote_agent_updates_status(self, test_db, student_agent):
        """Test promoting agent updates maturity status."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            # Promote agent
            result = await service.promote_agent(
                agent_id=student_agent.id,
                new_maturity="INTERN",
                validated_by="test-user"
            )

            assert result is True

            # Verify status updated
            test_db.refresh(student_agent)
            assert student_agent.status == AgentStatus.INTERN

    @pytest.mark.asyncio
    async def test_promote_nonexistent_agent(self, test_db):
        """Test promoting nonexistent agent returns False."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            result = await service.promote_agent(
                agent_id="nonexistent-agent",
                new_maturity="INTERN",
                validated_by="test-user"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_promote_invalid_maturity(self, test_db, student_agent):
        """Test promoting with invalid maturity level."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            result = await service.promote_agent(
                agent_id=student_agent.id,
                new_maturity="INVALID_LEVEL",
                validated_by="test-user"
            )

            assert result is False


# ============================================================================
# Graduation Audit Trail Tests
# ============================================================================

class TestGraduationAuditTrail:
    """Test graduation audit trail generation."""

    @pytest.mark.asyncio
    async def test_get_graduation_audit_trail(self, test_db, supervised_agent,
                                               episodes_for_supervised_to_autonomous):
        """Test retrieving full graduation audit trail."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            trail = await service.get_graduation_audit_trail(
                agent_id=supervised_agent.id
            )

            assert "agent_id" in trail
            assert "agent_name" in trail
            assert "current_maturity" in trail
            assert "total_episodes" in trail
            assert "total_interventions" in trail
            assert "avg_constitutional_score" in trail
            assert "episodes_by_maturity" in trail
            assert "recent_episodes" in trail

            assert trail["agent_id"] == supervised_agent.id
            assert trail["total_episodes"] >= 50

    @pytest.mark.asyncio
    async def test_audit_trail_nonexistent_agent(self, test_db):
        """Test audit trail for nonexistent agent."""
        mock_lancedb = Mock()

        with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
            service = AgentGraduationService(test_db)
            service.lancedb = mock_lancedb

            trail = await service.get_graduation_audit_trail(
                agent_id="nonexistent-agent"
            )

            assert "error" in trail
