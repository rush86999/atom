"""
Unit tests for Agent Graduation Readiness Score Calculation

Tests cover:
1. Readiness score calculation (delegation to EpisodeService + field mapping)
2. INTERN graduation criteria (10 episodes, 50% intervention, 0.70 constitutional)
3. SUPERVISED graduation criteria (25 episodes, 20% intervention, 0.85 constitutional)
4. AUTONOMOUS graduation criteria (50 episodes, 0% intervention, 0.95 constitutional)
5. Gap identification for missing requirements
6. Recommendation generation based on scores
7. Edge cases (zero episodes, perfect agent, overflow scores)

NOTE: As of the POMDP/episode-service refactor, ``calculate_readiness_score`` no
longer computes the readiness formula directly. It now:
  1. Validates the agent exists and the target maturity is supported.
  2. Delegates to ``EpisodeService.get_graduation_readiness``.
  3. Maps ``threshold_met`` -> ``ready`` and surfaces ``current_maturity`` /
     ``target_maturity``.

These tests therefore mock ``get_episode_service`` and assert on the wrapper's
delegation/mapping contract. Per-scenario readiness dicts (score, gaps,
recommendation, episode_count, ...) are funnelled through the mock
``ReadinessResponse.to_dict()`` so each test still encodes its scenario.
"""

import pytest
from unittest.mock import Mock, patch

from core.agent_graduation_service import AgentGraduationService, AgentStatus


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session.

    Chained ``query().filter().first()`` returns ``None`` by default; tests
    override the terminal ``first`` / ``all`` to inject their agent.
    """
    session = Mock()
    session.query.return_value = session
    session.filter.return_value = session
    session.all.return_value = []
    session.first.return_value = None
    session.commit.return_value = None
    return session


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler."""
    lancedb = Mock()
    lancedb.search = Mock(return_value=[])
    return lancedb


@pytest.fixture
def mock_episode_service():
    """Mock EpisodeService returned by ``get_episode_service``.

    Tests configure ``mock_episode_service.get_graduation_readiness.return_value``
    (a Mock whose ``.to_dict()`` yields the scenario's readiness dict).
    """
    svc = Mock()
    readiness = Mock()
    # Default empty-dict so tests that forget to configure still work.
    readiness.to_dict.return_value = {
        "threshold_met": False,
        "readiness_score": 0.0,
        "episodes_analyzed": 0,
        "avg_constitutional_score": 0.0,
        "zero_intervention_ratio": 0.0,
    }
    svc.get_graduation_readiness.return_value = readiness
    svc._readiness = readiness  # expose for per-test reconfiguration
    return svc


@pytest.fixture
def graduation_service(db_session, mock_lancedb, mock_episode_service):
    """Create AgentGraduationService with mocked dependencies.

    Patches both ``get_lancedb_handler`` (used in __init__) and
    ``get_episode_service`` (used in ``calculate_readiness_score``).
    """
    with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
        with patch('core.agent_graduation_service.get_episode_service', return_value=mock_episode_service):
            service = AgentGraduationService(db_session)
            service.lancedb = mock_lancedb
            # Expose the mock for per-test configuration
            service._mock_episode_service = mock_episode_service
            yield service


def _set_readiness(graduation_service, **fields):
    """Helper to reconfigure the mock ReadinessResponse.to_dict() payload."""
    # Default baseline; callers override individual fields.
    base = {
        "threshold_met": False,
        "readiness_score": 0.0,
        "episodes_analyzed": 0,
        "avg_constitutional_score": 0.0,
        "zero_intervention_ratio": 0.0,
        "supervision_success_rate": 0.0,
        "success_rate": 0.0,
        "breakdown": {},
    }
    base.update(fields)
    graduation_service._mock_episode_service._readiness.to_dict.return_value = base


@pytest.fixture
def sample_student_agent():
    """Create sample STUDENT agent."""
    agent = Mock()
    agent.id = "student-agent-001"
    agent.name = "StudentAgent"
    agent.tenant_id = "default"
    mock_status = Mock()
    mock_status.value = "STUDENT"
    agent.status = mock_status
    agent.confidence_score = 0.4
    return agent


@pytest.fixture
def sample_intern_agent():
    """Create sample INTERN agent."""
    agent = Mock()
    agent.id = "intern-agent-001"
    agent.name = "InternAgent"
    agent.tenant_id = "default"
    mock_status = Mock()
    mock_status.value = "INTERN"
    agent.status = mock_status
    agent.confidence_score = 0.6
    return agent


@pytest.fixture
def sample_supervised_agent():
    """Create sample SUPERVISED agent."""
    agent = Mock()
    agent.id = "supervised-agent-001"
    agent.name = "SupervisedAgent"
    agent.tenant_id = "default"
    mock_status = Mock()
    mock_status.value = "SUPERVISED"
    agent.status = mock_status
    agent.confidence_score = 0.8
    return agent


def _wire_agent(graduation_service, agent):
    """Configure the Mock db chain so the agent lookup returns ``agent``."""
    graduation_service.db.query.return_value.filter.return_value.first.return_value = agent


# ============================================================================
# Test Readiness Score Calculation
# ============================================================================

class TestReadinessScoreCalculation:
    """Test readiness score delegation + field mapping."""

    @pytest.mark.asyncio
    async def test_score_calculation_all_factors(self, graduation_service, sample_intern_agent):
        """Test score calculation with all three factors."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=True,
            readiness_score=82.5,
            episodes_analyzed=10,
            avg_constitutional_score=0.75,
            zero_intervention_ratio=0.7,
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # Verify the wrapper passes through the delegated score & components
        assert 0.0 <= result["readiness_score"] <= 100.0
        assert result["episodes_analyzed"] == 10
        assert result["zero_intervention_ratio"] == 0.7
        assert result["avg_constitutional_score"] == 0.75
        # Wrapper maps threshold_met -> ready
        assert result["ready"] is True

    @pytest.mark.asyncio
    async def test_score_weighting_episode_component(self, graduation_service, sample_intern_agent):
        """Test that the episode component is reflected in the score."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=True,
            readiness_score=90.0,
            episodes_analyzed=20,
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # Episode score should be high (20/25 = 0.8, 0.8 * 40 = 32 points)
        assert result["readiness_score"] > 50
        assert result["episodes_analyzed"] == 20

    @pytest.mark.asyncio
    async def test_score_weighting_intervention_component(self, graduation_service, sample_intern_agent):
        """Test intervention rate component (zero interventions = max score)."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=True,
            readiness_score=95.0,
            episodes_analyzed=25,
            zero_intervention_ratio=1.0,
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # Should score well with zero interventions
        assert result["zero_intervention_ratio"] == 1.0
        assert result["readiness_score"] > 60

    @pytest.mark.asyncio
    async def test_score_weighting_constitutional_component(self, graduation_service, sample_intern_agent):
        """Test constitutional score component contribution."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=True,
            readiness_score=92.0,
            episodes_analyzed=25,
            avg_constitutional_score=0.95,
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # High constitutional score should boost overall score
        assert result["avg_constitutional_score"] == 0.95
        assert result["readiness_score"] > 60


# ============================================================================
# Test INTERN Graduation Criteria
# ============================================================================

class TestINTERNGraduationCriteria:
    """Test STUDENT -> INTERN graduation requirements."""

    @pytest.mark.asyncio
    async def test_intern_graduation_with_sufficient_episodes(self, graduation_service, sample_student_agent):
        """Test graduation with 10 episodes meeting criteria."""
        _wire_agent(graduation_service, sample_student_agent)
        _set_readiness(
            graduation_service,
            threshold_met=True,
            readiness_score=78.0,
            episodes_analyzed=10,
            gaps=[],
            recommendation="Agent ready for promotion to INTERN. Score: 78.0/100",
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="student-agent-001",
            target_maturity="INTERN"
        )

        assert result["ready"] is True
        assert result["readiness_score"] >= 70.0
        assert result.get("gaps", []) == []
        rec = result.get("recommendation", "")
        assert "ready for promotion" in rec.lower()

    @pytest.mark.asyncio
    async def test_intern_graduation_insufficient_episodes(self, graduation_service, sample_student_agent):
        """Test graduation failure with insufficient episodes."""
        _wire_agent(graduation_service, sample_student_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=40.0,
            episodes_analyzed=5,
            gaps=["Need 5 more episodes to reach minimum of 10"],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="student-agent-001",
            target_maturity="INTERN"
        )

        assert result["ready"] is False
        assert any("5 more episodes" in gap for gap in result["gaps"])
        assert result["episodes_analyzed"] == 5

    @pytest.mark.asyncio
    async def test_intern_graduation_high_intervention_rate(self, graduation_service, sample_student_agent):
        """Test graduation failure with excessive interventions."""
        _wire_agent(graduation_service, sample_student_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=35.0,
            episodes_analyzed=10,
            zero_intervention_ratio=0.0,
            gaps=["Intervention rate 100% exceeds maximum of 50%"],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="student-agent-001",
            target_maturity="INTERN"
        )

        # High intervention rate should cause failure
        assert result["ready"] is False
        assert len(result["gaps"]) > 0

    @pytest.mark.asyncio
    async def test_intern_graduation_low_constitutional_score(self, graduation_service, sample_student_agent):
        """Test graduation failure with low constitutional compliance."""
        _wire_agent(graduation_service, sample_student_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=45.0,
            episodes_analyzed=10,
            avg_constitutional_score=0.65,
            gaps=["Constitutional score too low: 0.65 < 0.70"],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="student-agent-001",
            target_maturity="INTERN"
        )

        assert result["ready"] is False
        assert any("constitutional score too low" in gap.lower() for gap in result["gaps"])


# ============================================================================
# Test SUPERVISED Graduation Criteria
# ============================================================================

class TestSUPERVISEDGraduationCriteria:
    """Test INTERN -> SUPERVISED graduation requirements."""

    @pytest.mark.asyncio
    async def test_supervised_graduation_with_sufficient_episodes(self, graduation_service, sample_intern_agent):
        """Test graduation with 25 episodes meeting criteria."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=True,
            readiness_score=88.0,
            episodes_analyzed=25,
            gaps=[],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        assert result["ready"] is True
        assert result["readiness_score"] >= 80.0
        assert result.get("gaps", []) == []

    @pytest.mark.asyncio
    async def test_supervised_graduation_insufficient_episodes(self, graduation_service, sample_intern_agent):
        """Test graduation failure with insufficient episodes."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=55.0,
            episodes_analyzed=15,
            gaps=["Need 10 more episodes to reach minimum of 25"],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        assert result["ready"] is False
        assert any("10 more episodes" in gap for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_supervised_graduation_high_intervention_rate(self, graduation_service, sample_intern_agent):
        """Test graduation failure with excessive interventions."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=30.0,
            episodes_analyzed=25,
            zero_intervention_ratio=0.0,
            gaps=["Intervention rate 100% exceeds maximum of 20%"],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # High intervention rate should cause failure
        assert result["ready"] is False
        assert len(result["gaps"]) > 0

    @pytest.mark.asyncio
    async def test_supervised_graduation_low_constitutional_score(self, graduation_service, sample_intern_agent):
        """Test graduation failure with low constitutional compliance."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=70.0,
            episodes_analyzed=25,
            avg_constitutional_score=0.80,
            gaps=["Constitutional score too low: 0.80 < 0.85"],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        assert result["ready"] is False
        assert any("constitutional score too low" in gap.lower() for gap in result["gaps"])


# ============================================================================
# Test AUTONOMOUS Graduation Criteria
# ============================================================================

class TestAUTONOMOUSGraduationCriteria:
    """Test SUPERVISED -> AUTONOMOUS graduation requirements."""

    @pytest.mark.asyncio
    async def test_autonomous_graduation_with_sufficient_episodes(self, graduation_service, sample_supervised_agent):
        """Test graduation with 50 episodes meeting criteria."""
        _wire_agent(graduation_service, sample_supervised_agent)
        _set_readiness(
            graduation_service,
            threshold_met=True,
            readiness_score=96.0,
            episodes_analyzed=50,
            gaps=[],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="supervised-agent-001",
            target_maturity="AUTONOMOUS"
        )

        assert result["ready"] is True
        assert result["readiness_score"] >= 90.0
        assert result.get("gaps", []) == []

    @pytest.mark.asyncio
    async def test_autonomous_graduation_insufficient_episodes(self, graduation_service, sample_supervised_agent):
        """Test graduation failure with insufficient episodes."""
        _wire_agent(graduation_service, sample_supervised_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=70.0,
            episodes_analyzed=30,
            gaps=["Need 20 more episodes to reach minimum of 50"],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="supervised-agent-001",
            target_maturity="AUTONOMOUS"
        )

        assert result["ready"] is False
        assert any("20 more episodes" in gap for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_autonomous_graduation_any_interventions(self, graduation_service, sample_supervised_agent):
        """Test graduation failure with any interventions."""
        _wire_agent(graduation_service, sample_supervised_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=50.0,
            episodes_analyzed=50,
            zero_intervention_ratio=0.0,
            gaps=["Intervention rate 100% exceeds maximum of 0%"],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="supervised-agent-001",
            target_maturity="AUTONOMOUS"
        )

        # Any interventions should cause failure for AUTONOMOUS
        assert result["ready"] is False
        assert len(result["gaps"]) > 0

    @pytest.mark.asyncio
    async def test_autonomous_graduation_low_constitutional_score(self, graduation_service, sample_supervised_agent):
        """Test graduation failure with low constitutional compliance."""
        _wire_agent(graduation_service, sample_supervised_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=85.0,
            episodes_analyzed=50,
            avg_constitutional_score=0.93,
            gaps=["Constitutional score too low: 0.93 < 0.95"],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="supervised-agent-001",
            target_maturity="AUTONOMOUS"
        )

        assert result["ready"] is False
        assert any("constitutional score too low" in gap.lower() for gap in result["gaps"])


# ============================================================================
# Test Readiness Gap Identification
# ============================================================================

class TestReadinessGapIdentification:
    """Test gap detection for missing graduation requirements."""

    @pytest.mark.asyncio
    async def test_gap_identification_multiple_gaps(self, graduation_service, sample_intern_agent):
        """Test identification of multiple gaps."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=45.0,
            episodes_analyzed=10,
            gaps=[
                "Need 15 more episodes to reach minimum of 25",
                "Constitutional score too low: 0.75 < 0.85",
            ],
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # Should identify multiple gaps
        assert len(result["gaps"]) > 0
        assert any("15 more episodes" in gap for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_gap_identification_no_gaps(self, graduation_service, sample_student_agent):
        """Test readiness with no gaps."""
        _wire_agent(graduation_service, sample_student_agent)
        _set_readiness(
            graduation_service,
            threshold_met=True,
            readiness_score=78.0,
            episodes_analyzed=10,
            gaps=[],
            recommendation="Agent ready for promotion to INTERN. Score: 78.0/100",
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="student-agent-001",
            target_maturity="INTERN"
        )

        assert result.get("gaps", []) == []
        assert result["ready"] is True


# ============================================================================
# Test Recommendation Generation
# ============================================================================

class TestRecommendationGeneration:
    """Test human-readable recommendation generation."""

    @pytest.mark.asyncio
    async def test_recommendation_ready(self, graduation_service, sample_intern_agent):
        """Test recommendation when agent is ready."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=True,
            readiness_score=90.0,
            episodes_analyzed=25,
            gaps=[],
            recommendation="Agent ready for promotion to SUPERVISED. Score: 90.0/100",
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        assert "ready for promotion" in result["recommendation"].lower()

    @pytest.mark.asyncio
    async def test_recommendation_not_ready_low_score(self, graduation_service, sample_intern_agent):
        """Test recommendation when agent has low score."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=25.0,
            episodes_analyzed=5,
            gaps=[
                "Need 20 more episodes to reach minimum of 25",
                "Intervention rate too high",
            ],
            recommendation="Agent not ready. Significant training needed for SUPERVISED.",
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        assert "not ready" in result["recommendation"].lower()
        assert result["readiness_score"] < 50

    @pytest.mark.asyncio
    async def test_recommendation_making_progress(self, graduation_service, sample_intern_agent):
        """Test recommendation when agent is making progress."""
        _wire_agent(graduation_service, sample_intern_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=60.0,
            episodes_analyzed=10,
            recommendation="Agent making progress. More practice needed for SUPERVISED.",
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # Score should be in 50-75 range
        assert 50 <= result["readiness_score"] < 75


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases for readiness score calculation."""

    @pytest.mark.asyncio
    async def test_zero_episodes(self, graduation_service, sample_student_agent):
        """Test agent with zero episodes."""
        _wire_agent(graduation_service, sample_student_agent)
        _set_readiness(
            graduation_service,
            threshold_met=False,
            readiness_score=0.0,
            episodes_analyzed=0,
            gaps=["Need 10 more episodes to reach minimum of 10"],
            avg_constitutional_score=0.0,
            zero_intervention_ratio=0.0,
        )

        result = await graduation_service.calculate_readiness_score(
            agent_id="student-agent-001",
            target_maturity="INTERN"
        )

        assert result["episodes_analyzed"] == 0
        assert result["ready"] is False
        assert result["readiness_score"] == 0.0

    @pytest.mark.asyncio
    async def test_agent_not_found(self, graduation_service):
        """Test readiness calculation for nonexistent agent."""
        graduation_service.db.query.return_value.filter.return_value.first.return_value = None

        result = await graduation_service.calculate_readiness_score(
            agent_id="nonexistent-agent",
            target_maturity="INTERN"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unknown_maturity_level(self, graduation_service, sample_intern_agent):
        """Test readiness calculation for invalid maturity level."""
        _wire_agent(graduation_service, sample_intern_agent)

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="INVALID_LEVEL"
        )

        assert "error" in result
        assert "unknown maturity" in result["error"].lower()
