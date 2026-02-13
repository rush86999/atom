"""
Unit tests for agent_graduation_service.py

Tests cover:
- Readiness score calculation
- Graduation criteria validation
- Episode count requirements
- Intervention rate thresholds
- Constitutional compliance scoring
- Agent promotion
- Audit trail generation
- Supervision metrics integration
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

from core.agent_graduation_service import AgentGraduationService
from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    EpisodeSegment,
    SupervisionSession
)


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    db.query = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.rollback = Mock()
    return db


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB handler"""
    handler = Mock()
    handler.db = Mock()
    handler.table_names = Mock(return_value=[])
    handler.create_table = Mock()
    handler.add_document = Mock()
    return handler


@pytest.fixture
def graduation_service(mock_db, mock_lancedb):
    """Create AgentGraduationService with mocked dependencies"""
    with patch('core.agent_graduation_service.get_lancedb_handler', return_value=mock_lancedb):
        return AgentGraduationService(mock_db)


@pytest.fixture
def sample_agent():
    """Create sample agent"""
    agent = AgentRegistry(
        id="agent_1",
        name="Test Agent",
        status=AgentStatus.INTERN,
        agent_type="assistant",
        confidence_score=0.65
    )
    return agent


@pytest.fixture
def sample_episodes():
    """Create sample episodes"""
    episodes = []
    for i in range(15):
        episode = Episode(
            id=f"episode_{i}",
            agent_id="agent_1",
            user_id="user_1",
            status="completed",
            maturity_at_time="INTERN",
            human_intervention_count=0 if i % 2 == 0 else 1,  # Half have interventions
            constitutional_score=0.8 + (i * 0.01)  # Varying scores
        )
        episodes.append(episode)
    return episodes


@pytest.fixture
def sample_supervision_sessions():
    """Create sample supervision sessions"""
    sessions = []
    for i in range(10):
        session = SupervisionSession(
            id=f"supervision_{i}",
            agent_id="agent_1",
            supervisor_id="user_1",
            status="completed",
            intervention_count=1 if i < 3 else 0,  # 3 have interventions
            supervisor_rating=4 if i < 7 else 5,  # Mix of ratings
            duration_seconds=3600
        )
        session.started_at = datetime.now()
        session.completed_at = datetime.now()
        sessions.append(session)
    return sessions


# ============================================================================
# Service Initialization Tests
# ============================================================================

class TestGraduationServiceInitialization:
    """Test service initialization"""

    def test_service_init(self, graduation_service, mock_db, mock_lancedb):
        """Test service initialization"""
        assert graduation_service.db == mock_db
        assert graduation_service.lancedb == mock_lancedb

    def test_graduation_criteria(self, graduation_service):
        """Test graduation criteria constants"""
        criteria = graduation_service.CRITERIA

        assert "INTERN" in criteria
        assert "SUPERVISED" in criteria
        assert "AUTONOMOUS" in criteria

        # INTERN criteria
        assert criteria["INTERN"]["min_episodes"] == 10
        assert criteria["INTERN"]["max_intervention_rate"] == 0.5
        assert criteria["INTERN"]["min_constitutional_score"] == 0.70

        # SUPERVISED criteria
        assert criteria["SUPERVISED"]["min_episodes"] == 25
        assert criteria["SUPERVISED"]["max_intervention_rate"] == 0.2
        assert criteria["SUPERVISED"]["min_constitutional_score"] == 0.85

        # AUTONOMOUS criteria
        assert criteria["AUTONOMOUS"]["min_episodes"] == 50
        assert criteria["AUTONOMOUS"]["max_intervention_rate"] == 0.0
        assert criteria["AUTONOMOUS"]["min_constitutional_score"] == 0.95


# ============================================================================
# Readiness Score Calculation Tests
# ============================================================================

class TestReadinessScoreCalculation:
    """Test readiness score calculation"""

    @pytest.mark.asyncio
    async def test_calculate_readiness_score_ready(
        self,
        graduation_service,
        mock_db,
        sample_agent,
        sample_episodes
    ):
        """Test readiness score when agent is ready"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = sample_episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="agent_1",
            target_maturity="SUPERVISED"
        )

        assert result is not None
        assert "ready" in result
        assert "score" in result
        assert "episode_count" in result
        assert "intervention_rate" in result
        assert "recommendation" in result
        assert result["episode_count"] == 15

    @pytest.mark.asyncio
    async def test_calculate_readiness_score_not_enough_episodes(
        self,
        graduation_service,
        mock_db,
        sample_agent
    ):
        """Test readiness score with insufficient episodes"""
        # Only 5 episodes (need 10 for INTERN)
        few_episodes = [
            Episode(
                id=f"episode_{i}",
                agent_id="agent_1",
                status="completed",
                maturity_at_time="INTERN",
                human_intervention_count=0,
                constitutional_score=0.8
            )
            for i in range(5)
        ]

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = few_episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="agent_1",
            target_maturity="INTERN"
        )

        assert result["ready"] is False
        assert result["episode_count"] == 5
        assert len(result["gaps"]) > 0
        assert any("more episodes" in gap for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_calculate_readiness_score_high_intervention_rate(
        self,
        graduation_service,
        mock_db,
        sample_agent
    ):
        """Test readiness score with high intervention rate"""
        # Create episodes with high intervention rate
        high_intervention_episodes = []
        for i in range(15):
            episode = Episode(
                id=f"episode_{i}",
                agent_id="agent_1",
                status="completed",
                maturity_at_time="INTERN",
                human_intervention_count=10,  # Very high
                constitutional_score=0.9
            )
            high_intervention_episodes.append(episode)

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = high_intervention_episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="agent_1",
            target_maturity="SUPERVISED"
        )

        assert result["ready"] is False
        assert result["intervention_rate"] > 0.2  # Above SUPERVISED threshold

    @pytest.mark.asyncio
    async def test_calculate_readiness_score_low_constitutional_score(
        self,
        graduation_service,
        mock_db,
        sample_agent
    ):
        """Test readiness score with low constitutional score"""
        # Create episodes with low constitutional scores
        low_score_episodes = []
        for i in range(15):
            episode = Episode(
                id=f"episode_{i}",
                agent_id="agent_1",
                status="completed",
                maturity_at_time="INTERN",
                human_intervention_count=0,
                constitutional_score=0.5  # Below 0.70 threshold
            )
            low_score_episodes.append(episode)

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = low_score_episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="agent_1",
            target_maturity="INTERN"
        )

        assert result["ready"] is False
        assert any("constitutional" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_calculate_readiness_score_agent_not_found(
        self,
        graduation_service,
        mock_db
    ):
        """Test readiness score when agent not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await graduation_service.calculate_readiness_score(
            agent_id="nonexistent",
            target_maturity="INTERN"
        )

        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_calculate_readiness_score_invalid_maturity(
        self,
        graduation_service,
        mock_db,
        sample_agent
    ):
        """Test readiness score with invalid maturity level"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        result = await graduation_service.calculate_readiness_score(
            agent_id="agent_1",
            target_maturity="INVALID_LEVEL"
        )

        assert "error" in result

    def test_calculate_score_weighting(self, graduation_service):
        """Test readiness score calculation weighting"""
        # Episode score (40%), Intervention score (30%), Constitutional score (30%)
        score = graduation_service._calculate_score(
            episode_count=10,  # Exactly meets requirement
            min_episodes=10,
            intervention_rate=0.3,  # Below 0.5 threshold
            max_intervention=0.5,
            constitutional_score=0.8,  # Above 0.7 threshold
            min_constitutional=0.7
        )

        # Should be close to 100 since all criteria met
        assert score >= 90

    def test_calculate_score_partial_meeting(self, graduation_service):
        """Test score calculation with partial criteria meeting"""
        score = graduation_service._calculate_score(
            episode_count=5,  # Half of required
            min_episodes=10,
            intervention_rate=0.6,  # Above 0.5 threshold
            max_intervention=0.5,
            constitutional_score=0.65,  # Below 0.7 threshold
            min_constitutional=0.7
        )

        # Should be lower since not all criteria met
        assert score < 70

    def test_generate_recommendation_ready(self, graduation_service):
        """Test recommendation generation for ready agent"""
        recommendation = graduation_service._generate_recommendation(
            ready=True,
            score=85.0,
            target="SUPERVISED"
        )

        assert "ready" in recommendation.lower()
        assert "SUPERVISED" in recommendation

    def test_generate_recommendation_not_ready_low_score(self, graduation_service):
        """Test recommendation for agent with low score"""
        recommendation = graduation_service._generate_recommendation(
            ready=False,
            score=30.0,
            target="INTERN"
        )

        assert "not ready" in recommendation.lower()

    def test_generate_recommendation_making_progress(self, graduation_service):
        """Test recommendation for agent making progress"""
        recommendation = graduation_service._generate_recommendation(
            ready=False,
            score=60.0,
            target="SUPERVISED"
        )

        assert "progress" in recommendation.lower()

    def test_generate_recommendation_close_to_ready(self, graduation_service):
        """Test recommendation for agent close to ready"""
        recommendation = graduation_service._generate_recommendation(
            ready=False,
            score=80.0,
            target="AUTONOMOUS"
        )

        assert "close" in recommendation.lower() or "address" in recommendation.lower()


# ============================================================================
# Graduation Exam Tests
# ============================================================================

class TestGraduationExam:
    """Test graduation exam execution"""

    @pytest.mark.asyncio
    async def test_run_graduation_exam_success(
        self,
        graduation_service,
        mock_db
    ):
        """Test successful graduation exam"""
        # Mock episodes
        episodes = [
            Episode(
                id="episode_1",
                agent_id="agent_1",
                status="completed"
            ),
            Episode(
                id="episode_2",
                agent_id="agent_1",
                status="completed"
            )
        ]

        mock_db.query.return_value.filter.return_value.first.side_effect = episodes

        # Mock sandbox executor
        mock_sandbox_result = Mock()
        mock_sandbox_result.passed = True
        mock_sandbox_result.interventions = []
        mock_sandbox_result.safety_violations = []
        mock_sandbox_result.replayed_actions = []

        with patch('core.agent_graduation_service.get_sandbox_executor') as mock_get_sandbox:
            mock_executor = Mock()
            mock_executor.execute_in_sandbox = AsyncMock(return_value=mock_sandbox_result)
            mock_get_sandbox.return_value = mock_executor

            result = await graduation_service.run_graduation_exam(
                agent_id="agent_1",
                edge_case_episodes=["episode_1", "episode_2"]
            )

            assert result["passed"] is True
            assert result["score"] == 100.0
            assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_run_graduation_exam_partial_failure(
        self,
        graduation_service,
        mock_db
    ):
        """Test graduation exam with some failures"""
        episodes = [
            Episode(id="ep1", title="Case 1", agent_id="agent_1", status="completed"),
            Episode(id="ep2", title="Case 2", agent_id="agent_1", status="completed"),
        ]

        mock_db.query.return_value.filter.return_value.first.side_effect = episodes

        # Mock sandbox executor with mixed results
        def mock_execute(*args, **kwargs):
            result = Mock()
            episode_id = kwargs.get("episode_id", "")
            if episode_id == "ep1":
                result.passed = True
            else:
                result.passed = False
            result.interventions = []
            result.safety_violations = []
            result.replayed_actions = []
            return result

        with patch('core.agent_graduation_service.get_sandbox_executor') as mock_get_sandbox:
            mock_executor = Mock()
            mock_executor.execute_in_sandbox = AsyncMock(side_effect=mock_execute)
            mock_get_sandbox.return_value = mock_executor

            result = await graduation_service.run_graduation_exam(
                agent_id="agent_1",
                edge_case_episodes=["ep1", "ep2"]
            )

            assert result["passed"] is False
            assert result["score"] == 50.0  # 1 out of 2 passed


# ============================================================================
# Constitutional Compliance Tests
# ============================================================================

class TestConstitutionalCompliance:
    """Test constitutional compliance validation"""

    @pytest.mark.asyncio
    async def test_validate_constitutional_compliance_compliant(
        self,
        graduation_service,
        mock_db
    ):
        """Test validation of compliant episode"""
        episode = Episode(
            id="episode_1",
            agent_id="agent_1",
            status="completed",
            metadata_json={"domain": "finance"}
        )

        mock_db.query.return_value.filter.return_value.first.return_value = episode

        # Mock segments
        segments = [
            EpisodeSegment(
                id="seg_1",
                episode_id="episode_1",
                segment_type="execution"
            )
        ]

        mock_db.query.return_value.filter.return_value.all.return_value = segments

        # Mock validator
        with patch('core.agent_graduation_service.ConstitutionalValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_actions.return_value = {
                "compliant": True,
                "score": 1.0,
                "violations": [],
                "total_actions": 5,
                "checked_actions": 5
            }
            mock_validator_class.return_value = mock_validator

            result = await graduation_service.validate_constitutional_compliance(
                episode_id="episode_1"
            )

            assert result["compliant"] is True
            assert result["score"] == 1.0
            assert len(result["violations"]) == 0

    @pytest.mark.asyncio
    async def test_validate_constitutional_compliance_violations(
        self,
        graduation_service,
        mock_db
    ):
        """Test validation with compliance violations"""
        episode = Episode(
            id="episode_1",
            agent_id="agent_1",
            status="completed"
        )

        mock_db.query.return_value.filter.return_value.first.return_value = episode

        segments = [
            EpisodeSegment(
                id="seg_1",
                episode_id="episode_1",
                segment_type="execution"
            )
        ]

        mock_db.query.return_value.filter.return_value.all.return_value = segments

        with patch('core.agent_graduation_service.ConstitutionalValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_actions.return_value = {
                "compliant": False,
                "score": 0.6,
                "violations": ["Tax law violation", "HIPAA violation"],
                "total_actions": 5,
                "checked_actions": 5
            }
            mock_validator_class.return_value = mock_validator

            result = await graduation_service.validate_constitutional_compliance(
                episode_id="episode_1"
            )

            assert result["compliant"] is False
            assert result["score"] == 0.6
            assert len(result["violations"]) == 2

    @pytest.mark.asyncio
    async def test_validate_constitutional_compliance_episode_not_found(
        self,
        graduation_service,
        mock_db
    ):
        """Test validation when episode not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await graduation_service.validate_constitutional_compliance(
            episode_id="nonexistent"
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_validate_constitutional_compliance_no_segments(
        self,
        graduation_service,
        mock_db
    ):
        """Test validation with no segments"""
        episode = Episode(
            id="episode_1",
            agent_id="agent_1",
            status="completed"
        )

        mock_db.query.return_value.filter.return_value.first.return_value = episode
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = await graduation_service.validate_constitutional_compliance(
            episode_id="episode_1"
        )

        # Should return compliant with note
        assert result["compliant"] is True
        assert "note" in result


# ============================================================================
# Agent Promotion Tests
# ============================================================================

class TestAgentPromotion:
    """Test agent promotion logic"""

    @pytest.mark.asyncio
    async def test_promote_agent_success(
        self,
        graduation_service,
        mock_db,
        sample_agent
    ):
        """Test successful agent promotion"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        result = await graduation_service.promote_agent(
            agent_id="agent_1",
            new_maturity="SUPERVISED",
            validated_by="admin_1"
        )

        assert result is True
        assert mock_db.commit.called

        # Verify agent status was updated
        assert sample_agent.status == AgentStatus.SUPERVISED
        assert "promoted_at" in sample_agent.metadata_json
        assert sample_agent.metadata_json["promoted_by"] == "admin_1"

    @pytest.mark.asyncio
    async def test_promote_agent_not_found(
        self,
        graduation_service,
        mock_db
    ):
        """Test promotion when agent not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await graduation_service.promote_agent(
            agent_id="nonexistent",
            new_maturity="SUPERVISED",
            validated_by="admin_1"
        )

        assert result is False
        assert not mock_db.commit.called

    @pytest.mark.asyncio
    async def test_promote_agent_invalid_maturity(
        self,
        graduation_service,
        mock_db,
        sample_agent
    ):
        """Test promotion with invalid maturity level"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        result = await graduation_service.promote_agent(
            agent_id="agent_1",
            new_maturity="INVALID_LEVEL",
            validated_by="admin_1"
        )

        assert result is False
        assert not mock_db.commit.called


# ============================================================================
# Audit Trail Tests
# ============================================================================

class TestGraduationAuditTrail:
    """Test graduation audit trail generation"""

    @pytest.mark.asyncio
    async def test_get_graduation_audit_trail(
        self,
        graduation_service,
        mock_db,
        sample_agent,
        sample_episodes
    ):
        """Test getting full audit trail"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.order_by.return_value.all.return_value = sample_episodes

        trail = await graduation_service.get_graduation_audit_trail(agent_id="agent_1")

        assert trail is not None
        assert trail["agent_id"] == "agent_1"
        assert trail["agent_name"] == sample_agent.name
        assert "total_episodes" in trail
        assert "total_interventions" in trail
        assert "avg_constitutional_score" in trail

    @pytest.mark.asyncio
    async def test_get_graduation_audit_trail_agent_not_found(
        self,
        graduation_service,
        mock_db
    ):
        """Test audit trail when agent not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        trail = await graduation_service.get_graduation_audit_trail(agent_id="nonexistent")

        assert "error" in trail


# ============================================================================
# Supervision Metrics Tests
# ============================================================================

class TestSupervisionMetrics:
    """Test supervision-based graduation metrics"""

    @pytest.mark.asyncio
    async def test_calculate_supervision_metrics(
        self,
        graduation_service,
        mock_db,
        sample_supervision_sessions
    ):
        """Test supervision metrics calculation"""
        mock_db.query.return_value.filter.return_value.all.return_value = sample_supervision_sessions

        metrics = await graduation_service.calculate_supervision_metrics(
            agent_id="agent_1",
            maturity_level=AgentStatus.SUPERVISED
        )

        assert metrics is not None
        assert "total_supervision_hours" in metrics
        assert "intervention_rate" in metrics
        assert "average_supervisor_rating" in metrics
        assert "total_sessions" in metrics
        assert metrics["total_sessions"] == 10

    @pytest.mark.asyncio
    async def test_calculate_supervision_metrics_no_sessions(
        self,
        graduation_service,
        mock_db
    ):
        """Test supervision metrics with no sessions"""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        metrics = await graduation_service.calculate_supervision_metrics(
            agent_id="agent_1",
            maturity_level=AgentStatus.SUPERVISED
        )

        assert metrics["total_sessions"] == 0
        assert metrics["intervention_rate"] == 1.0  # High penalty for no data

    def test_calculate_performance_trend_improving(self, graduation_service):
        """Test performance trend calculation - improving"""
        sessions = []
        for i in range(10):
            session = Mock(spec=SupervisionSession)
            session.started_at = datetime.now()
            session.supervisor_rating = 3 + i  # Increasing ratings
            session.intervention_count = max(0, 5 - i)  # Decreasing interventions
            sessions.append(session)

        trend = graduation_service._calculate_performance_trend(sessions)

        assert trend == "improving"

    def test_calculate_performance_trend_declining(self, graduation_service):
        """Test performance trend calculation - declining"""
        sessions = []
        for i in range(10):
            session = Mock(spec=SupervisionSession)
            session.started_at = datetime.now()
            session.supervisor_rating = 5 - i  # Decreasing ratings
            session.intervention_count = i  # Increasing interventions
            sessions.append(session)

        trend = graduation_service._calculate_performance_trend(sessions)

        assert trend == "declining"

    def test_calculate_performance_trend_stable(self, graduation_service):
        """Test performance trend calculation - stable"""
        sessions = []
        for i in range(10):
            session = Mock(spec=SupervisionSession)
            session.started_at = datetime.now()
            session.supervisor_rating = 4  # Consistent rating
            session.intervention_count = 2  # Consistent interventions
            sessions.append(session)

        trend = graduation_service._calculate_performance_trend(sessions)

        assert trend == "stable"

    def test_calculate_performance_trend_insufficient_data(self, graduation_service):
        """Test performance trend with insufficient data"""
        sessions = [Mock(spec=SupervisionSession) for _ in range(5)]

        trend = graduation_service._calculate_performance_trend(sessions)

        assert trend == "stable"  # Default when insufficient data


# ============================================================================
# Combined Validation Tests
# ============================================================================

class TestCombinedValidation:
    """Test combined episode and supervision validation"""

    @pytest.mark.asyncio
    async def test_validate_graduation_with_supervision_ready(
        self,
        graduation_service,
        mock_db,
        sample_agent
    ):
        """Test combined validation when ready"""
        # Create episodes meeting criteria
        episodes = []
        for i in range(25):  # Meet SUPERVISED requirement
            episode = Episode(
                id=f"ep_{i}",
                agent_id="agent_1",
                status="completed",
                maturity_at_time="INTERN",
                human_intervention_count=0,
                constitutional_score=0.9
            )
            episodes.append(episode)

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            episodes,  # Episodes
            []  # No supervision sessions (will create gaps)
        ]

        result = await graduation_service.validate_graduation_with_supervision(
            agent_id="agent_1",
            target_maturity=AgentStatus.SUPERVISED
        )

        assert result is not None
        assert "ready" in result
        assert "episode_metrics" in result
        assert "supervision_metrics" in result


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_zero_episodes(self, graduation_service, mock_db, sample_agent):
        """Test readiness calculation with zero episodes"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = await graduation_service.calculate_readiness_score(
            agent_id="agent_1",
            target_maturity="INTERN"
        )

        # Should handle gracefully
        assert result["episode_count"] == 0
        assert result["intervention_rate"] == 1.0  # Max penalty

    @pytest.mark.asyncio
    async def test_episodes_without_constitutional_scores(
        self,
        graduation_service,
        mock_db,
        sample_agent
    ):
        """Test readiness with missing constitutional scores"""
        episodes = []
        for i in range(15):
            episode = Episode(
                id=f"ep_{i}",
                agent_id="agent_1",
                status="completed",
                maturity_at_time="INTERN",
                human_intervention_count=0,
                constitutional_score=None  # Missing scores
            )
            episodes.append(episode)

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = episodes

        result = await graduation_service.calculate_readiness_score(
            agent_id="agent_1",
            target_maturity="INTERN"
        )

        # Should handle missing scores
        assert result["avg_constitutional_score"] == 0.0

    def test_supervision_score_calculation(self, graduation_service):
        """Test supervision-based score calculation"""
        metrics = {
            "average_supervisor_rating": 4.5,  # High rating
            "intervention_rate": 0.5,  # Low
            "total_sessions": 10,
            "recent_performance_trend": "improving"
        }

        criteria = {
            "max_intervention_rate": 1.0
        }

        score = graduation_service._supervision_score(metrics, criteria)

        # Should be high with good metrics
        assert score > 70
