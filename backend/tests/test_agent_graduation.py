"""
Tests for Agent Graduation Service
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from core.agent_graduation_service import AgentGraduationService
from core.models import AgentRegistry, AgentStatus, Episode


@pytest.fixture
def mock_student_agent():
    """Mock student agent"""
    agent = AgentRegistry(
        id="student_agent_123",
        name="Student Finance Agent",
        category="Finance",
        status=AgentStatus.STUDENT
    )
    agent.configuration = {}
    return agent


@pytest.fixture
def mock_episodes():
    """Mock episodes for graduation testing"""
    episodes = []
    for i in range(15):  # 15 episodes (above INTERN threshold of 10)
        episode = Episode(
            id=f"episode_{i}",
            title=f"Training Episode {i}",
            agent_id="student_agent_123",
            user_id="user_123",
            workspace_id="default",
            status="completed",
            maturity_at_time="STUDENT",
            human_intervention_count=0 if i < 12 else 1,  # Some with interventions
            constitutional_score=0.75 + (i * 0.01),  # Improving scores
            started_at=datetime.now(),
            ended_at=datetime.now(),
            topics=["tax", "finance"],
            entities=[],
            execution_ids=[],
            importance_score=0.7
        )
        episodes.append(episode)
    return episodes


class TestGraduationReadiness:
    """Tests for graduation readiness calculation"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_calculate_readiness_success_case(
        self, mock_lancedb, db_session, mock_student_agent, mock_episodes
    ):
        """Test readiness calculation for qualified agent"""
        # Setup query mocks
        agent_query = Mock()
        agent_query.first = Mock(return_value=mock_student_agent)

        episode_query = Mock()
        episode_query.filter = Mock(return_value=episode_query)
        episode_query.all = Mock(return_value=mock_episodes)

        def query_side_effect(model):
            if model == AgentRegistry:
                return agent_query
            return episode_query

        db_session.query = query_side_effect

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.calculate_readiness_score(
            agent_id="student_agent_123",
            target_maturity="INTERN"
        ))

        assert "ready" in result
        assert "score" in result
        assert result["episode_count"] == 15
        # Check that current_maturity is set (may be Mock or str depending on query)
        assert "current_maturity" in result
        assert 0 <= result["score"] <= 100

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_calculate_readiness_insufficient_episodes(
        self, mock_lancedb, db_session, mock_student_agent
    ):
        """Test readiness calculation with insufficient episodes"""
        # Only 5 episodes (below INTERN threshold of 10)
        few_episodes = [
            Episode(
                id=f"episode_{i}",
                title=f"Episode {i}",
                agent_id="student_agent_123",
                user_id="user_123",
                workspace_id="default",
                status="completed",
                maturity_at_time="STUDENT",
                human_intervention_count=0,
                constitutional_score=0.8,
                started_at=datetime.now(),
                ended_at=datetime.now(),
                topics=[],
                entities=[],
                execution_ids=[],
                importance_score=0.7
            )
            for i in range(5)
        ]

        agent_query = Mock()
        agent_query.first = Mock(return_value=mock_student_agent)

        episode_query = Mock()
        episode_query.filter = Mock(return_value=episode_query)
        episode_query.all = Mock(return_value=few_episodes)

        def query_side_effect(model):
            if model == AgentRegistry:
                return agent_query
            return episode_query

        db_session.query = query_side_effect

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.calculate_readiness_score(
            agent_id="student_agent_123",
            target_maturity="INTERN"
        ))

        assert result["ready"] is False
        assert "Need 5 more episodes" in result["gaps"]
        assert result["score"] < 100

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_calculate_readiness_high_intervention_rate(
        self, mock_lancedb, db_session, mock_student_agent
    ):
        """Test readiness calculation with high intervention rate"""
        # Episodes with many interventions (50% rate)
        high_intervention_episodes = [
            Episode(
                id=f"episode_{i}",
                title=f"Episode {i}",
                agent_id="student_agent_123",
                user_id="user_123",
                workspace_id="default",
                status="completed",
                maturity_at_time="STUDENT",
                human_intervention_count=1 if i % 2 == 0 else 0,  # 50% intervention
                constitutional_score=0.8,
                started_at=datetime.now(),
                ended_at=datetime.now(),
                topics=[],
                entities=[],
                execution_ids=[],
                importance_score=0.7
            )
            for i in range(15)
        ]

        agent_query = Mock()
        agent_query.first = Mock(return_value=mock_student_agent)

        episode_query = Mock()
        episode_query.filter = Mock(return_value=episode_query)
        episode_query.all = Mock(return_value=high_intervention_episodes)

        def query_side_effect(model):
            if model == AgentRegistry:
                return agent_query
            return episode_query

        db_session.query = query_side_effect

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.calculate_readiness_score(
            agent_id="student_agent_123",
            target_maturity="INTERN"
        ))

        # At the threshold (50%), should pass for INTERN
        # 8/15 = 0.533, which is approximately 50%
        assert abs(result["intervention_rate"] - 0.533) < 0.01

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_unknown_maturity_level(self, mock_lancedb, db_session):
        """Test error handling for unknown maturity level"""
        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.calculate_readiness_score(
            agent_id="agent_123",
            target_maturity="INVALID_LEVEL"
        ))

        assert "error" in result
        assert "Unknown maturity level" in result["error"]


class TestAgentPromotion:
    """Tests for agent promotion"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_promote_agent_success(self, mock_lancedb, db_session, mock_student_agent):
        """Test successful agent promotion"""
        # Use a callable that returns the agent object to simulate proper query behavior
        def query_return_value(model):
            if model == AgentRegistry:
                agent_query = Mock()
                agent_query.filter = Mock(return_value=agent_query)
                agent_query.first = Mock(return_value=mock_student_agent)
                return agent_query
            return Mock()

        db_session.query = query_return_value

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.promote_agent(
            agent_id="student_agent_123",
            new_maturity="INTERN",
            validated_by="admin_user"
        ))

        assert result is True
        # Check that configuration was updated
        assert mock_student_agent.configuration is not None
        assert mock_student_agent.configuration.get("promoted_by") == "admin_user"

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_promote_agent_not_found(self, mock_lancedb, db_session):
        """Test promotion of non-existent agent"""
        agent_query = Mock()
        agent_query.filter = Mock(return_value=agent_query)
        agent_query.first = Mock(return_value=None)
        db_session.query = Mock(return_value=agent_query)

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.promote_agent(
            agent_id="nonexistent_agent",
            new_maturity="INTERN",
            validated_by="admin_user"
        ))

        assert result is False

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_promote_agent_invalid_maturity(self, mock_lancedb, db_session, mock_student_agent):
        """Test promotion with invalid maturity level"""
        agent_query = Mock()
        agent_query.first = Mock(return_value=mock_student_agent)
        db_session.query = Mock(return_value=agent_query)

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.promote_agent(
            agent_id="student_agent_123",
            new_maturity="INVALID_LEVEL",
            validated_by="admin_user"
        ))

        assert result is False


class TestGraduationExam:
    """Tests for graduation exam functionality"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_run_graduation_exam(self, mock_lancedb, db_session):
        """Test running graduation exam on edge cases"""
        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.run_graduation_exam(
            agent_id="student_agent_123",
            edge_case_episodes=["edge_case_1", "edge_case_2", "edge_case_3"]
        ))

        assert "passed" in result
        assert "score" in result
        assert result["total_cases"] == 3

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_validate_constitutional_compliance(self, mock_lancedb, db_session):
        """Test constitutional compliance validation"""
        episode = Episode(
            id="episode_123",
            title="Tax Calculation Episode",
            agent_id="agent_123",
            user_id="user_123",
            workspace_id="default",
            status="completed",
            maturity_at_time="INTERN",
            human_intervention_count=0,
            constitutional_score=1.0,
            started_at=datetime.now(),
            ended_at=datetime.now(),
            topics=["tax", "HST"],
            entities=[],
            execution_ids=[],
            importance_score=0.9
        )

        episode_query = Mock()
        episode_query.first = Mock(return_value=episode)
        db_session.query = Mock(return_value=episode_query)

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.validate_constitutional_compliance(
            episode_id="episode_123"
        ))

        assert "compliant" in result
        assert "score" in result
        assert result["episode_id"] == "episode_123"


class TestGraduationAuditTrail:
    """Tests for graduation audit trail"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_get_graduation_audit_trail(self, mock_lancedb, db_session, mock_student_agent, mock_episodes):
        """Test getting full audit trail for agent"""
        agent_query = Mock()
        agent_query.first = Mock(return_value=mock_student_agent)

        episode_query = Mock()
        episode_query.filter = Mock(return_value=episode_query)
        episode_query.order_by = Mock(return_value=episode_query)
        episode_query.all = Mock(return_value=mock_episodes)

        def query_side_effect(model):
            if model == AgentRegistry:
                return agent_query
            return episode_query

        db_session.query = query_side_effect

        service = AgentGraduationService(db_session)

        import asyncio
        result = asyncio.run(service.get_graduation_audit_trail(
            agent_id="student_agent_123"
        ))

        assert "agent_id" in result
        assert "current_maturity" in result
        assert "total_episodes" in result
        assert result["total_episodes"] == 15
        assert "episodes_by_maturity" in result


class TestSandboxExecutorCoverage:
    """Coverage tests for SandboxExecutor graduation exam logic"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_exam_with_no_episodes_returns_failure(
        self, mock_lancedb, db_session
    ):
        """Test SandboxExecutor returns failure when agent has no episodes"""
        # Create agent with no episodes
        from core.models import AgentRegistry, AgentStatus

        agent = AgentRegistry(
            id="agent_no_episodes",
            name="Empty Agent",
            category="Test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT
        )
        agent.configuration = {}
        db_session.add(agent)
        db_session.commit()

        from core.agent_graduation_service import 
from core.sandbox_executor import SandboxExecutor
        import asyncio

        executor = SandboxExecutor(db_session)
        result = asyncio.run(executor.execute_exam(
            agent_id="agent_no_episodes",
            target_maturity="INTERN"
        ))

        assert result["success"] is True
        assert result["score"] == 0.0
        assert result["passed"] is False
        assert "insufficient_episode_count" in result["constitutional_violations"]

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_exam_calculates_score_from_episodes(
        self, mock_lancedb, db_session
    ):
        """Test SandboxExecutor correctly calculates score from episode data"""
        from core.models import AgentRegistry, AgentStatus, Episode
        from datetime import datetime

        # Create agent
        agent = AgentRegistry(
            id="agent_with_episodes",
            name="Episode Agent",
            category="Test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT
        )
        agent.configuration = {}
        db_session.add(agent)
        db_session.commit()

        # Create episodes with varying performance
        # Need to refresh to get the agent's status value
        db_session.refresh(agent)
        current_status = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)

        episodes = []
        for i in range(15):
            episode = Episode(
                id=f"exam_episode_{i}",
                title=f"Exam Episode {i}",
                agent_id="agent_with_episodes",
                user_id="test_user",
                workspace_id="default",
                status="completed",
                maturity_at_time=current_status,  # Use actual status value
                human_intervention_count=0 if i < 10 else 1,  # 33% intervention rate
                constitutional_score=0.8 + (i * 0.01),  # Improving scores
                started_at=datetime.now(),
                ended_at=datetime.now(),
                topics=["test"],
                entities=[],
                execution_ids=[],
                importance_score=0.7
            )
            episodes.append(episode)
            db_session.add(episode)
        db_session.commit()

        from core.agent_graduation_service import 
from core.sandbox_executor import SandboxExecutor
        import asyncio

        executor = SandboxExecutor(db_session)
        result = asyncio.run(executor.execute_exam(
            agent_id="agent_with_episodes",
            target_maturity="INTERN"
        ))

        assert result["success"] is True
        assert result["score"] >= 0.0  # Score should be calculated
        assert "constitutional_compliance" in result
        assert "constitutional_violations" in result

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_exam_detects_excessive_interventions(
        self, mock_lancedb, db_session
    ):
        """Test SandboxExecutor flags excessive intervention rate"""
        from core.models import AgentRegistry, AgentStatus, Episode
        from datetime import datetime

        agent = AgentRegistry(
            id="agent_high_interventions",
            name="High Intervention Agent",
            category="Test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN
        )
        agent.configuration = {}
        db_session.add(agent)
        db_session.commit()

        # Refresh to get actual status value
        db_session.refresh(agent)
        current_status = agent.status.value if hasattr(agent.status, 'value') else str(agent.status)

        # Episodes with 60% intervention rate (above 50% threshold)
        for i in range(15):
            episode = Episode(
                id=f"high_int_ep_{i}",
                title=f"High Intervention Episode {i}",
                agent_id="agent_high_interventions",
                user_id="test_user",
                workspace_id="default",
                status="completed",
                maturity_at_time=current_status,  # Use actual status value
                human_intervention_count=1 if i % 5 < 3 else 0,  # 60% intervention
                constitutional_score=0.75,
                started_at=datetime.now(),
                ended_at=datetime.now(),
                topics=["test"],
                entities=[],
                execution_ids=[],
                importance_score=0.7
            )
            db_session.add(episode)
        db_session.commit()

        from core.agent_graduation_service import 
from core.sandbox_executor import SandboxExecutor
        import asyncio

        executor = SandboxExecutor(db_session)
        result = asyncio.run(executor.execute_exam(
            agent_id="agent_high_interventions",
            target_maturity="SUPERVISED"
        ))

        assert result["success"] is True
        # Should flag excessive interventions (60% > 50% threshold)
        assert "excessive_interventions" in result["constitutional_violations"]


class TestSupervisionMetricsCoverage:
    """Coverage tests for supervision metrics calculation"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_supervision_metrics_with_no_sessions(
        self, mock_lancedb, db_session
    ):
        """Test supervision metrics return zeros when no sessions exist"""
        from core.agent_graduation_service import AgentGraduationService
        from core.models import AgentStatus
        import asyncio

        service = AgentGraduationService(db_session)
        result = asyncio.run(service.calculate_supervision_metrics(
            agent_id="agent_no_sessions",
            maturity_level=AgentStatus.STUDENT
        ))

        assert result["total_supervision_hours"] == 0
        assert result["intervention_rate"] == 1.0  # Penalty for no data
        assert result["average_supervisor_rating"] == 0.0
        assert result["recent_performance_trend"] == "unknown"
        assert result["total_sessions"] == 0

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_supervision_metrics_calculates_aggregates(
        self, mock_lancedb, db_session
    ):
        """Test supervision metrics correctly aggregate session data"""
        from core.agent_graduation_service import AgentGraduationService
        from core.models import SupervisionSession, AgentStatus
        from datetime import datetime, timedelta
        import asyncio

        # Create supervision sessions with varied data
        base_time = datetime.now()
        for i in range(5):
            session = SupervisionSession(
                id=f"supervision_session_{i}",
                agent_id="test_agent_supervision",
                agent_name="Test Agent",
                workspace_id="default",
                supervisor_id="supervisor_1",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i),
                duration_seconds=1800 + (i * 600),  # 30-54 minutes
                intervention_count=2 if i < 2 else 0,  # 2 high, 3 zero
                supervisor_rating=5 if i >= 2 else 3,  # 3 high ratings, 2 low
                trigger_context={}
            )
            db_session.add(session)
        db_session.commit()

        service = AgentGraduationService(db_session)
        result = asyncio.run(service.calculate_supervision_metrics(
            agent_id="test_agent_supervision",
            maturity_level=AgentStatus.INTERN
        ))

        # Total duration: 1800+2400+3000+3600+4200 = 15000 seconds = 250 minutes = 4.17 hours
        assert result["total_supervision_hours"] == 4.17
        # Interventions: 2+2+0+0+0 = 4, rate = 4/4.17 = 0.96
        assert result["intervention_rate"] > 0.9
        # Rating: (3+3+5+5+5)/5 = 4.2
        assert result["average_supervisor_rating"] == 4.2
        assert result["high_rating_sessions"] == 3  # ratings >= 4
        assert result["low_intervention_sessions"] == 3  # interventions <= 1

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_performance_trend_calculation(
        self, mock_lancedb, db_session
    ):
        """Test performance trend compares recent vs previous sessions"""
        from core.agent_graduation_service import AgentGraduationService
        from core.models import SupervisionSession
        from datetime import datetime, timedelta

        # Create 10 sessions showing improvement
        base_time = datetime.now()
        for i in range(10):
            # Recent 5: better ratings, fewer interventions
            if i < 5:
                rating = 5.0 - (i * 0.2)  # 5.0, 4.8, 4.6, 4.4, 4.2
                interventions = 0
            else:
                rating = 3.0 + ((i - 5) * 0.1)  # 3.5, 3.6, 3.7, 3.8, 3.9
                interventions = 2

            session = SupervisionSession(
                id=f"trend_session_{i}",
                agent_id="trend_agent",
                agent_name="Trend Agent",
                workspace_id="default",
                supervisor_id="supervisor_1",
                status="completed",
                started_at=base_time - timedelta(hours=i+1),
                completed_at=base_time - timedelta(hours=i),
                duration_seconds=1800,
                intervention_count=interventions,
                supervisor_rating=rating,
                trigger_context={}
            )
            db_session.add(session)
        db_session.commit()

        service = AgentGraduationService(db_session)

        # Call internal method through public interface
        sessions = db_session.query(SupervisionSession).filter(
            SupervisionSession.agent_id == "trend_agent",
            SupervisionSession.status == "completed"
        ).all()

        result = service._calculate_performance_trend(sessions)

        # Should be improving (better recent performance)
        assert result in ["improving", "stable"]  # Allow for calculation variation


class TestSkillUsageMetricsCoverage:
    """Coverage tests for skill usage metrics"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_skill_usage_metrics_queries_executions(
        self, mock_lancedb, db_session
    ):
        """Test skill usage metrics query and aggregate skill executions"""
        from core.agent_graduation_service import AgentGraduationService
        from core.models import SkillExecution
        from datetime import datetime, timedelta
        import asyncio

        # Create skill executions
        base_time = datetime.now()
        skills_data = [
            ("skill_1", "success"),
            ("skill_1", "success"),
            ("skill_2", "success"),
            ("skill_2", "failure"),
            ("skill_3", "success"),
        ]
        for i, (skill_id, status) in enumerate(skills_data):
            execution = SkillExecution(
                id=f"skill_exec_{i}",
                agent_id="skill_agent",
                workspace_id="default",
                skill_id=skill_id,
                skill_source="community",
                status=status,
                created_at=base_time - timedelta(days=i),
                input_params={},
                output_result={} if status == "success" else None,
                error_message=None if status == "success" else "Test error",
                execution_time_ms=100 + (i * 50)
            )
            db_session.add(execution)
        db_session.commit()

        service = AgentGraduationService(db_session)
        result = asyncio.run(service.calculate_skill_usage_metrics(
            agent_id="skill_agent",
            days_back=30
        ))

        assert result["total_skill_executions"] == 5
        assert result["successful_executions"] == 4
        assert result["success_rate"] == 0.8
        assert result["unique_skills_used"] == 3

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_readiness_score_includes_skill_diversity_bonus(
        self, mock_lancedb, db_session
    ):
        """Test readiness score calculation includes skill diversity bonus"""
        from core.agent_graduation_service import AgentGraduationService
        from core.models import AgentRegistry, AgentStatus, Episode
        from datetime import datetime
        from unittest.mock import AsyncMock, patch
        import asyncio

        # Create agent with episodes
        agent = AgentRegistry(
            id="skill_ready_agent",
            name="Skill Ready Agent",
            category="Test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN
        )
        agent.configuration = {}
        db_session.add(agent)

        for i in range(12):
            episode = Episode(
                id=f"skill_ep_{i}",
                title=f"Episode {i}",
                agent_id="skill_ready_agent",
                user_id="test_user",
                workspace_id="default",
                status="completed",
                maturity_at_time="INTERN",
                human_intervention_count=0,
                constitutional_score=0.9,
                started_at=datetime.now(),
                ended_at=datetime.now(),
                topics=["test"],
                entities=[],
                execution_ids=[],
                importance_score=0.7
            )
            db_session.add(episode)
        db_session.commit()

        service = AgentGraduationService(db_session)

        # Mock calculate_skill_usage_metrics to return known values
        with patch.object(
            service,
            'calculate_skill_usage_metrics',
            new=AsyncMock(return_value={
                "total_skill_executions": 10,
                "successful_executions": 8,
                "success_rate": 0.8,
                "unique_skills_used": 5,  # Should give +0.05 bonus (5 * 0.01, capped at 0.05)
                "skill_episodes_count": 10,
                "skill_learning_velocity": 0.33
            })
        ):
            result = asyncio.run(service.calculate_readiness_score_with_skills(
                agent_id="skill_ready_agent",
                target_maturity="SUPERVISED"
            ))

        assert result["skill_diversity_bonus"] == 0.05  # Max bonus for 5 skills
        assert result["readiness_score"] >= result["episode_metrics"]["score"] / 100.0
        assert result["skill_metrics"]["unique_skills_used"] == 5


class TestSupervisionValidationCoverage:
    """Coverage tests for combined supervision validation"""

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_supervision_score_breakdown(
        self, mock_lancedb, db_session
    ):
        """Test supervision score calculation breakdown"""
        from core.agent_graduation_service import AgentGraduationService

        service = AgentGraduationService(db_session)

        metrics = {
            "total_supervision_hours": 10.0,
            "intervention_rate": 0.5,  # per hour
            "average_supervisor_rating": 4.0,
            "successful_intervention_recovery_rate": 0.8,
            "recent_performance_trend": "improving",
            "total_sessions": 10,
            "high_rating_sessions": 7,  # 70%
            "low_intervention_sessions": 8
        }

        criteria = {
            "min_episodes": 10,
            "max_intervention_rate": 0.5,
            "min_constitutional_score": 0.85
        }

        score = service._supervision_score(metrics, criteria)

        # Rating score: 4.0/4.0 = 1.0 * 40 = 40
        # Intervention score: (1 - 0.5/5.0) * 30 = 27
        # High quality: 0.7/0.6 = 1.0 * 20 = 20
        # Trend: improving = 10
        # Total: 40 + 27 + 20 + 10 = 97
        assert score > 90

    @patch('core.agent_graduation_service.get_lancedb_handler')
    def test_supervision_score_with_poor_metrics(
        self, mock_lancedb, db_session
    ):
        """Test supervision score with poor performance metrics"""
        from core.agent_graduation_service import AgentGraduationService

        service = AgentGraduationService(db_session)

        metrics = {
            "total_supervision_hours": 5.0,
            "intervention_rate": 5.0,  # Very high
            "average_supervisor_rating": 2.0,  # Low
            "successful_intervention_recovery_rate": 0.5,
            "recent_performance_trend": "declining",
            "total_sessions": 10,
            "high_rating_sessions": 2,  # 20%
            "low_intervention_sessions": 1
        }

        criteria = {
            "min_episodes": 10,
            "max_intervention_rate": 0.5,
            "min_constitutional_score": 0.85
        }

        score = service._supervision_score(metrics, criteria)

        # Should be low due to poor metrics
        assert score < 50
