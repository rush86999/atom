"""
Comprehensive test coverage for GraduationExamService.

Tests cover:
- Exam creation and execution
- Readiness score calculation
- Edge case simulation
- Constitutional guardrail checks
- Skill performance evaluation
- Manual promotion and demotion
- Promotion history tracking
- GEA evaluation stage

Target: 60%+ coverage (136+ lines of 227 total)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

# Mock EpisodeService before importing graduation_exam
sys = __import__('sys')

# Create mock EpisodeService module
mock_episode_service = Mock()
mock_episode_service.EpisodeService = Mock
mock_episode_service.ReadinessThresholds = Mock
sys.modules['core.episode_service'] = mock_episode_service

from core.graduation_exam import (
    GraduationExamService,
    ExamResult,
    PromotionResult
)
from core.models import (
    AgentRegistry,
    AgentEpisode,
    GraduationExam,
    PromotionHistory,
    EdgeCaseLibrary,
    AgentStatus,
    PromotionType,
    EpisodeOutcome
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def db_session():
    """Mock database session."""
    session = Mock(spec=Session)
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def mock_agent_registry():
    """Mock agent registry."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "test-agent-1"
    agent.tenant_id = "tenant-1"
    agent.status = AgentStatus.STUDENT.value
    agent.last_promotion_at = datetime.utcnow() - timedelta(days=30)
    agent.promotion_count = 0
    agent.last_exam_id = None
    agent.exam_eligible_at = None
    return agent


@pytest.fixture
def mock_episode_service():
    """Mock episode service."""
    with patch('core.graduation_exam.EpisodeService') as mock:
        service = Mock()
        service.get_graduation_readiness = Mock()
        service.assess_skill_mastery = Mock()
        mock.return_value = service
        yield service


@pytest.fixture
def graduation_service(db_session):
    """Graduation exam service fixture."""
    return GraduationExamService(db_session)


# =============================================================================
# TestGraduationExam - Exam Creation and Execution
# =============================================================================

class TestGraduationExam:
    """Test graduation exam creation and execution lifecycle."""

    def test_execute_graduation_exam_student_to_intern_passed(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test successful exam execution from STUDENT to INTERN."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.75
        readiness.threshold_met = True
        readiness.zero_intervention_ratio = 0.95
        readiness.avg_constitutional_score = 0.92
        readiness.avg_confidence_score = 0.80
        readiness.success_rate = 0.90
        readiness.episodes_analyzed = 30
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock edge case simulator
        with patch('core.graduation_exam.EdgeCaseSimulator') as mock_sim_class:
            mock_sim = Mock()
            mock_sim.simulate_agent_behavior = Mock(return_value={
                "passed": True,
                "violations": []
            })
            mock_sim_class.return_value = mock_sim

            # Mock asyncio.run for edge case simulation
            with patch('core.graduation_exam.asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = {"passed": True, "violations": []}

                # Mock query for edge cases (return empty)
                mock_query_edge = Mock()
                mock_query_edge.filter = Mock(return_value=mock_query_edge)
                mock_query_edge.order_by = Mock(return_value=mock_query_edge)
                mock_query_edge.limit = Mock(return_value=mock_query_edge)
                mock_query_edge.all = Mock(return_value=[])

                # Patch db.query to return different mocks
                original_query = db_session.query
                def query_side_effect(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect)

                # Execute exam
                result = graduation_service.execute_graduation_exam(
                    agent_id="test-agent-1",
                    tenant_id="tenant-1",
                    target_level=AgentStatus.INTERN.value
                )

                # Verify
                assert result.agent_id == "test-agent-1"
                assert result.passed is True
                assert result.promoted is True
                assert result.readiness_score == 0.75
                assert result.constitutional_check_passed is True

    def test_execute_graduation_exam_student_to_intern_failed(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test failed exam execution due to low readiness."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock (low score)
        readiness = Mock()
        readiness.readiness_score = 0.45
        readiness.threshold_met = False
        readiness.zero_intervention_ratio = 0.70
        readiness.avg_constitutional_score = 0.75
        readiness.avg_confidence_score = 0.60
        readiness.success_rate = 0.70
        readiness.episodes_analyzed = 25
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock edge case simulator
        with patch('core.graduation_exam.EdgeCaseSimulator') as mock_sim_class:
            mock_sim = Mock()
            mock_sim_class.return_value = mock_sim

            # Mock asyncio.run
            with patch('core.graduation_exam.asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = {"passed": True, "violations": []}

                # Mock query for edge cases (return empty)
                mock_query_edge = Mock()
                mock_query_edge.filter = Mock(return_value=mock_query_edge)
                mock_query_edge.order_by = Mock(return_value=mock_query_edge)
                mock_query_edge.limit = Mock(return_value=mock_query_edge)
                mock_query_edge.all = Mock(return_value=[])

                # Patch db.query to return different mocks
                original_query = db_session.query
                def query_side_effect(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect)

                # Execute exam
                result = graduation_service.execute_graduation_exam(
                    agent_id="test-agent-1",
                    tenant_id="tenant-1"
                )

                # Verify
                assert result.passed is False
                assert result.promoted is False
                assert "readiness score below threshold" in result.failure_reason

    def test_execute_graduation_exam_autonomous_agent_blocked(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test exam execution blocked for AUTONOMOUS agents."""
        # Setup agent as AUTONOMOUS
        mock_agent_registry.status = AgentStatus.AUTONOMOUS.value

        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Execute exam
        result = graduation_service.execute_graduation_exam(
            agent_id="test-agent-1",
            tenant_id="tenant-1"
        )

        # Verify
        assert result.passed is False
        assert "already at maximum level" in result.failure_reason

    def test_execute_graduation_exam_agent_not_found(
        self, graduation_service, db_session
    ):
        """Test exam execution with non-existent agent."""
        # Setup query mock (agent not found)
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        db_session.query.return_value = mock_query

        # Execute exam - should raise ValueError
        with pytest.raises(ValueError, match="Agent .* not found"):
            graduation_service.execute_graduation_exam(
                agent_id="nonexistent-agent",
                tenant_id="tenant-1"
            )

    def test_execute_graduation_exam_custom_episode_count(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test exam execution with custom episode count."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.80
        readiness.threshold_met = True
        readiness.zero_intervention_ratio = 0.95
        readiness.avg_constitutional_score = 0.95
        readiness.avg_confidence_score = 0.85
        readiness.success_rate = 0.92
        readiness.episodes_analyzed = 50  # Custom count
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock edge case simulator
        with patch('core.graduation_exam.EdgeCaseSimulator') as mock_sim_class:
            mock_sim = Mock()
            mock_sim_class.return_value = mock_sim

            # Mock asyncio.run
            with patch('core.graduation_exam.asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = {"passed": True, "violations": []}

                # Mock query for edge cases (return empty)
                mock_query_edge = Mock()
                mock_query_edge.filter = Mock(return_value=mock_query_edge)
                mock_query_edge.order_by = Mock(return_value=mock_query_edge)
                mock_query_edge.limit = Mock(return_value=mock_query_edge)
                mock_query_edge.all = Mock(return_value=[])

                # Patch db.query
                original_query = db_session.query
                def query_side_effect(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect)

                # Execute exam with custom episode count
                result = graduation_service.execute_graduation_exam(
                    agent_id="test-agent-1",
                    tenant_id="tenant-1",
                    episode_count=50
                )

                # Verify episode_service was called with custom count
                mock_episode_service.get_graduation_readiness.assert_called()
                call_args = mock_episode_service.get_graduation_readiness.call_args
                assert call_args[1]['episode_count'] == 50

    def test_execute_graduation_exam_manual_promoter(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test exam execution with manual promoter specified."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.85
        readiness.threshold_met = True
        readiness.zero_intervention_ratio = 0.95
        readiness.avg_constitutional_score = 0.95
        readiness.avg_confidence_score = 0.85
        readiness.success_rate = 0.92
        readiness.episodes_analyzed = 30
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock edge case simulator
        with patch('core.graduation_exam.EdgeCaseSimulator') as mock_sim_class:
            mock_sim = Mock()
            mock_sim_class.return_value = mock_sim

            # Mock asyncio.run
            with patch('core.graduation_exam.asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = {"passed": True, "violations": []}

                # Mock query for edge cases (return empty)
                mock_query_edge = Mock()
                mock_query_edge.filter = Mock(return_value=mock_query_edge)
                mock_query_edge.order_by = Mock(return_value=mock_query_edge)
                mock_query_edge.limit = Mock(return_value=mock_query_edge)
                mock_query_edge.all = Mock(return_value=[])

                # Patch db.query
                original_query = db_session.query
                def query_side_effect(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect)

                # Execute exam with manual promoter
                result = graduation_service.execute_graduation_exam(
                    agent_id="test-agent-1",
                    tenant_id="tenant-1",
                    promoted_by="admin-user-123"
                )

                # Verify exam was created and agent promoted
                assert result.passed is True
                assert result.promoted is True

    def test_exam_result_to_dict(self):
        """Test ExamResult to_dict conversion."""
        result = ExamResult(
            exam_id="exam-1",
            agent_id="agent-1",
            passed=True,
            promoted=True,
            readiness_score=0.85,
            edge_case_results={"total": 5, "passed": 5},
            constitutional_check_passed=True,
            failure_reason=None
        )

        result_dict = result.to_dict()

        assert result_dict["exam_id"] == "exam-1"
        assert result_dict["agent_id"] == "agent-1"
        assert result_dict["passed"] is True
        assert result_dict["promoted"] is True
        assert result_dict["readiness_score"] == 0.85
        assert result_dict["constitutional_check_passed"] is True


# =============================================================================
# TestExamValidation - Readiness Scoring and Eligibility
# =============================================================================

class TestExamValidation:
    """Test exam validation and eligibility checks."""

    def test_calculate_readiness_score_success(
        self, graduation_service, mock_episode_service
    ):
        """Test successful readiness score calculation."""
        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.78
        readiness.threshold_met = True
        readiness.episodes_analyzed = 30
        readiness.to_dict = Mock(return_value={
            "readiness_score": 0.78,
            "threshold_met": True,
            "episodes_analyzed": 30
        })
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Calculate readiness
        result = graduation_service.calculate_readiness_score(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            episode_count=30
        )

        # Verify
        assert result["readiness_score"] == 0.78
        assert result["threshold_met"] is True
        assert result["episodes_analyzed"] == 30

    def test_calculate_readiness_score_custom_episode_count(
        self, graduation_service, mock_episode_service
    ):
        """Test readiness calculation with custom episode count."""
        readiness = Mock()
        readiness.readiness_score = 0.82
        readiness.to_dict = Mock(return_value={"readiness_score": 0.82})
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Calculate with custom count
        result = graduation_service.calculate_readiness_score(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            episode_count=50
        )

        # Verify service was called with custom count
        mock_episode_service.get_graduation_readiness.assert_called_once_with(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            episode_count=50
        )

    def test_execute_graduation_exam_target_level_auto_detection(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test automatic target level detection based on current level."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.75
        readiness.threshold_met = True
        readiness.zero_intervention_ratio = 0.95
        readiness.avg_constitutional_score = 0.92
        readiness.avg_confidence_score = 0.80
        readiness.success_rate = 0.90
        readiness.episodes_analyzed = 30
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock edge case simulator
        with patch('core.graduation_exam.EdgeCaseSimulator') as mock_sim_class:
            mock_sim = Mock()
            mock_sim_class.return_value = mock_sim

            # Mock asyncio.run
            with patch('core.graduation_exam.asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = {"passed": True, "violations": []}

                # Mock query for edge cases (return empty)
                mock_query_edge = Mock()
                mock_query_edge.filter = Mock(return_value=mock_query_edge)
                mock_query_edge.order_by = Mock(return_value=mock_query_edge)
                mock_query_edge.limit = Mock(return_value=mock_query_edge)
                mock_query_edge.all = Mock(return_value=[])

                # Patch db.query
                original_query = db_session.query
                def query_side_effect(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect)

                # Execute exam without target_level (should auto-detect)
                result = graduation_service.execute_graduation_exam(
                    agent_id="test-agent-1",
                    tenant_id="tenant-1"
                )

                # Verify auto-detection worked (STUDENT -> INTERN)
                assert result.passed is True

    def test_exam_eligibility_cooldown_after_failure(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test that failed exams set eligibility cooldown."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock (fail)
        readiness = Mock()
        readiness.readiness_score = 0.40
        readiness.threshold_met = False
        readiness.zero_intervention_ratio = 0.70
        readiness.avg_constitutional_score = 0.75
        readiness.avg_confidence_score = 0.60
        readiness.success_rate = 0.70
        readiness.episodes_analyzed = 25
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock edge case simulator
        with patch('core.graduation_exam.EdgeCaseSimulator') as mock_sim_class:
            mock_sim = Mock()
            mock_sim_class.return_value = mock_sim

            # Mock asyncio.run
            with patch('core.graduation_exam.asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = {"passed": True, "violations": []}

                # Mock query for edge cases (return empty)
                mock_query_edge = Mock()
                mock_query_edge.filter = Mock(return_value=mock_query_edge)
                mock_query_edge.order_by = Mock(return_value=mock_query_edge)
                mock_query_edge.limit = Mock(return_value=mock_query_edge)
                mock_query_edge.all = Mock(return_value=[])

                # Patch db.query
                original_query = db_session.query
                def query_side_effect(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect)

                # Execute exam (will fail)
                result = graduation_service.execute_graduation_exam(
                    agent_id="test-agent-1",
                    tenant_id="tenant-1"
                )

                # Verify exam_eligible_at was set (6 hour cooldown)
                assert result.passed is False
                assert mock_agent_registry.exam_eligible_at is not None


# =============================================================================
# TestExamScoring - Score Calculation and Pass/Fail
# =============================================================================

class TestExamScoring:
    """Test exam scoring logic and pass/fail determination."""

    def test_exam_scoring_all_checks_passed(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test exam passes when all checks pass."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock (all passing)
        readiness = Mock()
        readiness.readiness_score = 0.85
        readiness.threshold_met = True
        readiness.zero_intervention_ratio = 0.95
        readiness.avg_constitutional_score = 0.95
        readiness.avg_confidence_score = 0.88
        readiness.success_rate = 0.95
        readiness.episodes_analyzed = 30
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock edge case simulator
        with patch('core.graduation_exam.EdgeCaseSimulator') as mock_sim_class:
            mock_sim = Mock()
            mock_sim_class.return_value = mock_sim

            # Mock asyncio.run
            with patch('core.graduation_exam.asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = {"passed": True, "violations": []}

                # Mock query for edge cases (return empty)
                mock_query_edge = Mock()
                mock_query_edge.filter = Mock(return_value=mock_query_edge)
                mock_query_edge.order_by = Mock(return_value=mock_query_edge)
                mock_query_edge.limit = Mock(return_value=mock_query_edge)
                mock_query_edge.all = Mock(return_value=[])

                # Patch db.query
                original_query = db_session.query
                def query_side_effect(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect)

                # Execute exam
                result = graduation_service.execute_graduation_exam(
                    agent_id="test-agent-1",
                    tenant_id="tenant-1"
                )

                # Verify pass
                assert result.passed is True
                assert result.promoted is True

    def test_exam_scoring_edge_case_failure(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test exam fails when edge case simulations fail."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.85
        readiness.threshold_met = True
        readiness.zero_intervention_ratio = 0.95
        readiness.avg_constitutional_score = 0.95
        readiness.avg_confidence_score = 0.88
        readiness.success_rate = 0.95
        readiness.episodes_analyzed = 30
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock edge case simulator (FAIL)
        with patch('core.graduation_exam.EdgeCaseSimulator') as mock_sim_class:
            mock_sim = Mock()
            mock_sim_class.return_value = mock_sim

            # Mock asyncio.run (edge case FAIL)
            with patch('core.graduation_exam.asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = {"passed": False, "violations": ["violation-1"]}

                # Mock query for edge cases (return one)
                edge_case = Mock(spec=EdgeCaseLibrary)
                edge_case.id = "edge-1"
                edge_case.name = "Test Edge Case"
                edge_case.violation_type = "safety"
                edge_case.times_tested = 0
                edge_case.times_passed = 0

                mock_query_edge = Mock()
                mock_query_edge.filter = Mock(return_value=mock_query_edge)
                mock_query_edge.order_by = Mock(return_value=mock_query_edge)
                mock_query_edge.limit = Mock(return_value=mock_query_edge)
                mock_query_edge.all = Mock(return_value=[edge_case])

                # Patch db.query
                original_query = db_session.query
                def query_side_effect(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect)

                # Execute exam
                result = graduation_service.execute_graduation_exam(
                    agent_id="test-agent-1",
                    tenant_id="tenant-1"
                )

                # Verify fail due to edge cases
                assert result.passed is False
                assert "edge case simulations" in result.failure_reason

    def test_exam_scoring_constitutional_violations(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test exam fails with constitutional violations."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.85
        readiness.threshold_met = True
        readiness.zero_intervention_ratio = 0.95
        readiness.avg_constitutional_score = 0.95
        readiness.avg_confidence_score = 0.88
        readiness.success_rate = 0.95
        readiness.episodes_analyzed = 30
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock edge case simulator
        with patch('core.graduation_exam.EdgeCaseSimulator') as mock_sim_class:
            mock_sim = Mock()
            mock_sim_class.return_value = mock_sim

            # Mock asyncio.run
            with patch('core.graduation_exam.asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = {"passed": True, "violations": []}

                # Mock query for edge cases (return empty)
                mock_query_edge = Mock()
                mock_query_edge.filter = Mock(return_value=mock_query_edge)
                mock_query_edge.order_by = Mock(return_value=mock_query_edge)
                mock_query_edge.limit = Mock(return_value=mock_query_edge)
                mock_query_edge.all = Mock(return_value=[])

                # Patch db.query
                original_query = db_session.query
                def query_side_effect(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect)

                # Mock episode query for constitutional check (low score)
                episode = Mock(spec=AgentEpisode)
                episode.id = "ep-1"
                episode.constitutional_score = 0.85  # Below 0.95 threshold
                episode.human_intervention_count = 0
                episode.started_at = datetime.utcnow()

                mock_query_ep = Mock()
                mock_query_ep.filter = Mock(return_value=mock_query_ep)
                mock_query_ep.order_by = Mock(return_value=mock_query_ep)
                mock_query_ep.limit = Mock(return_value=mock_query_ep)
                mock_query_ep.all = Mock(return_value=[episode])

                # Update query side effect
                def query_side_effect_with_ep(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    elif model == AgentEpisode:
                        return mock_query_ep
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect_with_ep)

                # Execute exam
                result = graduation_service.execute_graduation_exam(
                    agent_id="test-agent-1",
                    tenant_id="tenant-1"
                )

                # Verify fail due to constitutional violations
                assert result.passed is False
                assert "constitutional violations" in result.failure_reason

    def test_exam_scoring_skill_performance_failure(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test exam fails when skill performance is insufficient."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.85
        readiness.threshold_met = True
        readiness.zero_intervention_ratio = 0.95
        readiness.avg_constitutional_score = 0.95
        readiness.avg_confidence_score = 0.88
        readiness.success_rate = 0.95
        readiness.episodes_analyzed = 30
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock skill mastery (low performance)
        mastery = Mock()
        mastery.mastery_score = 0.35  # Below 0.5 threshold
        mastery.skill_diversity = 0.40
        mastery.skills_used = ["skill1"]
        mastery.skill_execution_count = 10
        mastery.required_skills_for_level = 3
        mastery.skill_success_rate = 0.50
        mock_episode_service.assess_skill_mastery.return_value = mastery

        # Mock edge case simulator
        with patch('core.graduation_exam.EdgeCaseSimulator') as mock_sim_class:
            mock_sim = Mock()
            mock_sim_class.return_value = mock_sim

            # Mock asyncio.run
            with patch('core.graduation_exam.asyncio.run') as mock_asyncio:
                mock_asyncio.return_value = {"passed": True, "violations": []}

                # Mock query for edge cases (return empty)
                mock_query_edge = Mock()
                mock_query_edge.filter = Mock(return_value=mock_query_edge)
                mock_query_edge.order_by = Mock(return_value=mock_query_edge)
                mock_query_edge.limit = Mock(return_value=mock_query_edge)
                mock_query_edge.all = Mock(return_value=[])

                # Patch db.query
                original_query = db_session.query
                def query_side_effect(model):
                    if model == EdgeCaseLibrary:
                        return mock_query_edge
                    return original_query.return_value
                db_session.query = Mock(side_effect=query_side_effect)

                # Execute exam
                result = graduation_service.execute_graduation_exam(
                    agent_id="test-agent-1",
                    tenant_id="tenant-1"
                )

                # Verify fail due to skill mastery
                assert result.passed is False
                assert "skill mastery" in result.failure_reason


# =============================================================================
# TestPromotionAndDemotion - Manual Promotion/Demotion
# =============================================================================

class TestPromotionAndDemotion:
    """Test manual promotion and demotion operations."""

    def test_promote_agent_manually_success(
        self, graduation_service, db_session, mock_agent_registry, mock_episode_service
    ):
        """Test successful manual promotion."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.75
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Promote manually
        result = graduation_service.promote_agent_manually(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            new_level=AgentStatus.INTERN.value,
            promoted_by="admin-123",
            justification="Admin override for testing"
        )

        # Verify
        assert result.success is True
        assert result.from_level == AgentStatus.STUDENT.value
        assert result.to_level == AgentStatus.INTERN.value
        assert result.promotion_type == PromotionType.MANUAL.value

    def test_promote_agent_manually_agent_not_found(
        self, graduation_service, db_session
    ):
        """Test manual promotion with non-existent agent."""
        # Setup query mock (agent not found)
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=None)
        db_session.query.return_value = mock_query

        # Try to promote
        result = graduation_service.promote_agent_manually(
            agent_id="nonexistent-agent",
            tenant_id="tenant-1",
            new_level=AgentStatus.INTERN.value,
            promoted_by="admin-123",
            justification="Test"
        )

        # Verify
        assert result.success is False
        assert "not found" in result.message

    def test_promote_agent_manually_invalid_level(
        self, graduation_service, db_session, mock_agent_registry
    ):
        """Test manual promotion with invalid maturity level."""
        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.first = Mock(return_value=mock_agent_registry)
        db_session.query.return_value = mock_query

        # Try to promote to invalid level
        result = graduation_service.promote_agent_manually(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            new_level="invalid_level",
            promoted_by="admin-123",
            justification="Test"
        )

        # Verify
        assert result.success is False
        assert "Invalid maturity level" in result.message

    def test_promotion_result_to_dict(self):
        """Test PromotionResult to_dict conversion."""
        result = PromotionResult(
            agent_id="agent-1",
            from_level=AgentStatus.STUDENT.value,
            to_level=AgentStatus.INTERN.value,
            promotion_type=PromotionType.AUTOMATIC.value,
            success=True,
            message="Promoted successfully"
        )

        result_dict = result.to_dict()

        assert result_dict["agent_id"] == "agent-1"
        assert result_dict["from_level"] == AgentStatus.STUDENT.value
        assert result_dict["to_level"] == AgentStatus.INTERN.value
        assert result_dict["promotion_type"] == PromotionType.AUTOMATIC.value
        assert result_dict["success"] is True


# =============================================================================
# TestPromotionHistory - History Tracking
# =============================================================================

class TestPromotionHistory:
    """Test promotion history tracking and retrieval."""

    def test_get_promotion_history(
        self, graduation_service, db_session
    ):
        """Test retrieving promotion history."""
        # Create mock history records
        history1 = Mock(spec=PromotionHistory)
        history1.id = "hist-1"
        history1.from_level = AgentStatus.STUDENT.value
        history1.to_level = AgentStatus.INTERN.value
        history1.promotion_type = PromotionType.AUTOMATIC.value
        history1.promoted_at = datetime.utcnow()

        history2 = Mock(spec=PromotionHistory)
        history2.id = "hist-2"
        history2.from_level = AgentStatus.INTERN.value
        history2.to_level = AgentStatus.SUPERVISED.value
        history2.promotion_type = PromotionType.MANUAL.value
        history2.promoted_at = datetime.utcnow()

        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.order_by = Mock(return_value=mock_query)
        mock_query.limit = Mock(return_value=mock_query)
        mock_query.all = Mock(return_value=[history1, history2])
        db_session.query.return_value = mock_query

        # Get history
        history = graduation_service.get_promotion_history(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            limit=20
        )

        # Verify
        assert len(history) == 2
        assert history[0].from_level == AgentStatus.STUDENT.value
        assert history[1].from_level == AgentStatus.INTERN.value

    def test_get_promotion_history_custom_limit(
        self, graduation_service, db_session
    ):
        """Test retrieving promotion history with custom limit."""
        # Create mock history record
        history = Mock(spec=PromotionHistory)
        history.id = "hist-1"

        # Setup query mock
        mock_query = Mock()
        mock_query.filter = Mock(return_value=mock_query)
        mock_query.order_by = Mock(return_value=mock_query)
        mock_query.limit = Mock(return_value=mock_query)
        mock_query.all = Mock(return_value=[history])
        db_session.query.return_value = mock_query

        # Get history with custom limit
        history_list = graduation_service.get_promotion_history(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            limit=10
        )

        # Verify limit was applied
        mock_query.limit.assert_called_once_with(10)
        assert len(history_list) == 1


# =============================================================================
# TestGEAEvaluation - GEA Evaluation Stage
# =============================================================================

class TestGEAEvaluation:
    """Test GEA (Gradual Evolution Agent) evaluation stage."""

    def test_evaluate_evolved_agent_success(
        self, graduation_service, mock_episode_service
    ):
        """Test successful evaluation of evolved agent config."""
        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.75
        readiness.to_dict = Mock(return_value={"readiness_score": 0.75})
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock evolved config
        evolved_config = {
            "system_prompt": "You are a helpful assistant with extensive knowledge and capabilities.",
            "evolution_history": ["evolution-1", "evolution-2"]
        }

        # Evaluate
        result = graduation_service.evaluate_evolved_agent(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            evolved_config=evolved_config,
            episode_count=20
        )

        # Verify
        assert "benchmark_score" in result
        assert "benchmark_passed" in result
        assert "readiness_score" in result
        assert result["readiness_score"] == 0.75

    def test_evaluate_evolved_agent_low_readiness(
        self, graduation_service, mock_episode_service
    ):
        """Test evaluation with low readiness score."""
        # Setup readiness mock (low score)
        readiness = Mock()
        readiness.readiness_score = 0.35
        readiness.to_dict = Mock(return_value={"readiness_score": 0.35})
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock evolved config
        evolved_config = {
            "system_prompt": "You are helpful.",
            "evolution_history": []
        }

        # Evaluate
        result = graduation_service.evaluate_evolved_agent(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            evolved_config=evolved_config
        )

        # Verify failure due to low readiness
        assert result["benchmark_passed"] is False
        assert len(result["failure_reasons"]) > 0

    def test_evaluate_evolved_agent_short_prompt(
        self, graduation_service, mock_episode_service
    ):
        """Test evaluation with too-short system prompt."""
        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.70
        readiness.to_dict = Mock(return_value={"readiness_score": 0.70})
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock evolved config with short prompt
        evolved_config = {
            "system_prompt": "Hi",  # Too short (<50 chars)
            "evolution_history": []
        }

        # Evaluate
        result = graduation_service.evaluate_evolved_agent(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            evolved_config=evolved_config
        )

        # Verify failure due to short prompt
        assert result["prompt_quality_score"] == 0.0
        assert "too short" in str(result["failure_reasons"])

    def test_evaluate_evolved_agent_deep_evolution_penalty(
        self, graduation_service, mock_episode_service
    ):
        """Test evaluation with excessive evolution depth."""
        # Setup readiness mock
        readiness = Mock()
        readiness.readiness_score = 0.75
        readiness.to_dict = Mock(return_value={"readiness_score": 0.75})
        mock_episode_service.get_graduation_readiness.return_value = readiness

        # Mock evolved config with deep history (>10 cycles)
        evolved_config = {
            "system_prompt": "You are a helpful assistant.",
            "evolution_history": [f"evolution-{i}" for i in range(15)]  # 15 cycles
        }

        # Evaluate
        result = graduation_service.evaluate_evolved_agent(
            agent_id="test-agent-1",
            tenant_id="tenant-1",
            evolved_config=evolved_config
        )

        # Verify depth penalty applied
        assert result["evolution_depth"] == 15
        # Score should be lower due to depth penalty
        assert result["benchmark_score"] < 0.75
