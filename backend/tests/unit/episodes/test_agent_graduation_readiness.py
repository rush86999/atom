"""
Unit tests for Agent Graduation Readiness Score Calculation

Tests cover:
1. Readiness score calculation (40% episodes, 30% intervention, 30% constitutional)
2. INTERN graduation criteria (10 episodes, 50% intervention, 0.70 constitutional)
3. SUPERVISED graduation criteria (25 episodes, 20% intervention, 0.85 constitutional)
4. AUTONOMOUS graduation criteria (50 episodes, 0% intervention, 0.95 constitutional)
5. Gap identification for missing requirements
6. Recommendation generation based on scores
7. Edge cases (zero episodes, perfect agent, overflow scores)

Target: 55%+ coverage on agent_graduation_service.py
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from core.agent_graduation_service import AgentGraduationService, AgentStatus


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session."""
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
def graduation_service(db_session, mock_lancedb):
    """Create AgentGraduationService with mocked dependencies."""
    with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
        service = AgentGraduationService(db_session)
        service.lancedb = mock_lancedb
        return service


@pytest.fixture
def sample_student_agent():
    """Create sample STUDENT agent."""
    agent = Mock()
    agent.id = "student-agent-001"
    agent.name = "StudentAgent"
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
    mock_status = Mock()
    mock_status.value = "SUPERVISED"
    agent.status = mock_status
    agent.confidence_score = 0.8
    return agent


def create_episode(count, intervention_rate=0.3, constitutional_score=0.75):
    """Create mock episodes with specified parameters."""
    episodes = []
    for i in range(count):
        ep = Mock()
        ep.id = f"episode-{i}"
        ep.maturity_at_time = "INTERN"
        ep.status = "completed"
        ep.human_intervention_count = int(count * intervention_rate / count) if count > 0 else 0
        ep.constitutional_score = constitutional_score
        ep.started_at = datetime.now() - timedelta(days=i)
        episodes.append(ep)
    return episodes


# ============================================================================
# Test Readiness Score Calculation
# ============================================================================

class TestReadinessScoreCalculation:
    """Test readiness score calculation with 40/30/30 weighting."""

    @pytest.mark.asyncio
    async def test_score_calculation_all_factors(self, graduation_service, sample_intern_agent):
        """Test score calculation with all three factors."""
        episodes = create_episode(10, intervention_rate=0.3, constitutional_score=0.75)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # Verify score components (40/30/30 weighting)
        assert result["score"] >= 0.0
        assert result["score"] <= 100.0
        assert result["episode_count"] == 10
        assert "intervention_rate" in result
        assert result["avg_constitutional_score"] == 0.75

    @pytest.mark.asyncio
    async def test_score_weighting_episode_component(self, graduation_service, sample_intern_agent):
        """Test episode count component (40% weight)."""
        episodes = create_episode(20, intervention_rate=0.0, constitutional_score=1.0)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # Episode score should be high (20/25 = 0.8, 0.8 * 40 = 32 points)
        assert result["score"] > 50

    @pytest.mark.asyncio
    async def test_score_weighting_intervention_component(self, graduation_service, sample_intern_agent):
        """Test intervention rate component (30% weight)."""
        episodes = create_episode(25, intervention_rate=0.0, constitutional_score=0.85)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # Should score well with zero interventions
        assert result["intervention_rate"] == 0.0
        assert result["score"] > 60

    @pytest.mark.asyncio
    async def test_score_weighting_constitutional_component(self, graduation_service, sample_intern_agent):
        """Test constitutional score component (30% weight)."""
        episodes = create_episode(25, intervention_rate=0.04, constitutional_score=0.95)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # High constitutional score should boost overall score
        assert result["avg_constitutional_score"] == 0.95
        assert result["score"] > 60


# ============================================================================
# Test INTERN Graduation Criteria
# ============================================================================

class TestINTERNGraduationCriteria:
    """Test STUDENT -> INTERN graduation requirements."""

    @pytest.mark.asyncio
    async def test_intern_graduation_with_sufficient_episodes(self, graduation_service, sample_student_agent):
        """Test graduation with 10 episodes meeting criteria."""
        episodes = create_episode(10, intervention_rate=0.3, constitutional_score=0.75)
        for ep in episodes:
            ep.maturity_at_time = "STUDENT"

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_student_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="student-agent-001",
            target_maturity="INTERN"
        )

        assert result["ready"] is True
        assert result["score"] >= 70.0
        assert len(result["gaps"]) == 0
        assert "ready for promotion" in result["recommendation"].lower()

    @pytest.mark.asyncio
    async def test_intern_graduation_insufficient_episodes(self, graduation_service, sample_student_agent):
        """Test graduation failure with insufficient episodes."""
        episodes = create_episode(5, intervention_rate=0.2, constitutional_score=0.80)
        for ep in episodes:
            ep.maturity_at_time = "STUDENT"

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_student_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="student-agent-001",
            target_maturity="INTERN"
        )

        assert result["ready"] is False
        assert any("5 more episodes" in gap for gap in result["gaps"])
        assert result["episode_count"] == 5

    @pytest.mark.asyncio
    async def test_intern_graduation_high_intervention_rate(self, graduation_service, sample_student_agent):
        """Test graduation failure with excessive interventions."""
        episodes = create_episode(10, intervention_rate=1.0, constitutional_score=0.80)
        for ep in episodes:
            ep.maturity_at_time = "STUDENT"
            ep.human_intervention_count = 10  # All episodes have intervention

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_student_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

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
        episodes = create_episode(10, intervention_rate=0.2, constitutional_score=0.65)
        for ep in episodes:
            ep.maturity_at_time = "STUDENT"

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_student_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

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
        episodes = create_episode(25, intervention_rate=0.08, constitutional_score=0.90)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        assert result["ready"] is True
        assert result["score"] >= 80.0
        assert len(result["gaps"]) == 0

    @pytest.mark.asyncio
    async def test_supervised_graduation_insufficient_episodes(self, graduation_service, sample_intern_agent):
        """Test graduation failure with insufficient episodes."""
        episodes = create_episode(15, intervention_rate=0.06, constitutional_score=0.90)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        assert result["ready"] is False
        assert any("10 more episodes" in gap for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_supervised_graduation_high_intervention_rate(self, graduation_service, sample_intern_agent):
        """Test graduation failure with excessive interventions."""
        episodes = create_episode(25, intervention_rate=1.0, constitutional_score=0.90)
        for ep in episodes:
            ep.human_intervention_count = 25  # All episodes have interventions

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

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
        episodes = create_episode(25, intervention_rate=0.08, constitutional_score=0.80)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

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
        episodes = create_episode(50, intervention_rate=0.0, constitutional_score=0.98)
        for ep in episodes:
            ep.maturity_at_time = "SUPERVISED"

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_supervised_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="supervised-agent-001",
            target_maturity="AUTONOMOUS"
        )

        assert result["ready"] is True
        assert result["score"] >= 90.0
        assert len(result["gaps"]) == 0

    @pytest.mark.asyncio
    async def test_autonomous_graduation_insufficient_episodes(self, graduation_service, sample_supervised_agent):
        """Test graduation failure with insufficient episodes."""
        episodes = create_episode(30, intervention_rate=0.0, constitutional_score=0.98)
        for ep in episodes:
            ep.maturity_at_time = "SUPERVISED"

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_supervised_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="supervised-agent-001",
            target_maturity="AUTONOMOUS"
        )

        assert result["ready"] is False
        assert any("20 more episodes" in gap for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_autonomous_graduation_any_interventions(self, graduation_service, sample_supervised_agent):
        """Test graduation failure with any interventions."""
        episodes = create_episode(50, intervention_rate=1.0, constitutional_score=0.98)
        for ep in episodes:
            ep.maturity_at_time = "SUPERVISED"
            ep.human_intervention_count = 50  # All episodes have interventions

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_supervised_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

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
        episodes = create_episode(50, intervention_rate=0.0, constitutional_score=0.93)
        for ep in episodes:
            ep.maturity_at_time = "SUPERVISED"

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_supervised_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

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
        episodes = create_episode(10, intervention_rate=0.5, constitutional_score=0.75)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

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
        episodes = create_episode(10, intervention_rate=0.2, constitutional_score=0.75)
        for ep in episodes:
            ep.maturity_at_time = "STUDENT"

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_student_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="student-agent-001",
            target_maturity="INTERN"
        )

        assert len(result["gaps"]) == 0
        assert result["ready"] is True


# ============================================================================
# Test Recommendation Generation
# ============================================================================

class TestRecommendationGeneration:
    """Test human-readable recommendation generation."""

    @pytest.mark.asyncio
    async def test_recommendation_ready(self, graduation_service, sample_intern_agent):
        """Test recommendation when agent is ready."""
        episodes = create_episode(25, intervention_rate=0.04, constitutional_score=0.90)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        assert "ready for promotion" in result["recommendation"].lower()

    @pytest.mark.asyncio
    async def test_recommendation_not_ready_low_score(self, graduation_service, sample_intern_agent):
        """Test recommendation when agent has low score."""
        episodes = create_episode(5, intervention_rate=1.0, constitutional_score=0.70)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        assert "not ready" in result["recommendation"].lower()
        assert result["score"] < 50

    @pytest.mark.asyncio
    async def test_recommendation_making_progress(self, graduation_service, sample_intern_agent):
        """Test recommendation when agent is making progress."""
        episodes = create_episode(10, intervention_rate=0.2, constitutional_score=0.75)

        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="SUPERVISED"
        )

        # Score should be in 50-75 range
        assert result["score"] >= 50 and result["score"] < 75


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases for readiness score calculation."""

    @pytest.mark.asyncio
    async def test_zero_episodes(self, graduation_service, sample_student_agent):
        """Test agent with zero episodes."""
        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_student_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = []

        result = await graduation_service.calculate_readiness_score(
            agent_id="student-agent-001",
            target_maturity="INTERN"
        )

        assert result["episode_count"] == 0
        assert result["ready"] is False
        assert result["score"] == 0.0

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
        graduation_service.db.query.return_value.filter.return_value.first.return_value = sample_intern_agent
        graduation_service.db.query.return_value.filter.return_value.all.return_value = []

        result = await graduation_service.calculate_readiness_score(
            agent_id="intern-agent-001",
            target_maturity="INVALID_LEVEL"
        )

        assert "error" in result
        assert "unknown maturity" in result["error"].lower()
