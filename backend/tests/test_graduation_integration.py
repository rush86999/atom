"""
Property-based and unit tests for graduation integration with supervision.

Tests the integration of supervision metrics into agent graduation validation.
"""

import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from core.models import (
    AgentRegistry,
    AgentStatus,
    Episode,
    SupervisionSession,
    SupervisionStatus,
    User,
    Workspace,
)
from core.agent_graduation_service import AgentGraduationService


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create a test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def user(db: Session):
    """Create test user."""
    user = User(
        id="test_graduation_user",
        email="graduation_test@example.com",
        first_name="Graduation",
        last_name="Test User",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def workspace(db: Session, user: User):
    """Create test workspace."""
    workspace = Workspace(
        id="test_graduation_workspace",
        name="Graduation Test Workspace",
        
    )
    db.add(workspace)
    db.commit()
    return workspace


@pytest.fixture
def agent(db: Session, workspace: Workspace, user: User):
    """Create test agent."""
    agent = AgentRegistry(
        id="test_graduation_agent",
        name="Test Graduation Agent",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.65,
        
        
    )
    db.add(agent)
    db.commit()
    return agent


@pytest.fixture
def supervision_session_factory(db: Session, agent: AgentRegistry, user: User):
    """Factory to create supervision sessions."""
    def _create_session(
        intervention_count: int = 0,
        supervisor_rating: int = 4,
        started_at_days_ago: int = 1,
        duration_seconds: int = 300,
    ) -> SupervisionSession:
        started_at = datetime.now() - timedelta(days=started_at_days_ago, seconds=duration_seconds)

        session = SupervisionSession(
            id=f"supervision_{datetime.now().timestamp()}_{started_at_days_ago}",
            agent_id=agent.id,
            agent_name=agent.name,
            workspace_id=agent.workspace_id,
            supervisor_id=user.id,
            status=SupervisionStatus.COMPLETED.value,
            intervention_count=intervention_count,
            supervisor_rating=supervisor_rating,
            supervision_feedback=f"Feedback for session {started_at_days_ago} days ago",
            duration_seconds=duration_seconds,
            started_at=started_at,
            completed_at=started_at + timedelta(seconds=duration_seconds),
            interventions=[
                {
                    "timestamp": started_at.isoformat(),
                    "type": "correct",
                    "guidance": f"Intervention {i + 1}"
                }
                for i in range(intervention_count)
            ]
        )
        db.add(session)
        db.commit()
        return session

    return _create_session


@pytest.fixture
def episode_factory(db: Session, agent: AgentRegistry):
    """Factory to create episodes."""
    def _create_episode(
        maturity: str = AgentStatus.INTERN.value,
        intervention_count: int = 0,
        constitutional_score: float = 0.8,
        created_days_ago: int = 1,
    ) -> Episode:
        started_at = datetime.now() - timedelta(days=created_days_ago)

        episode = Episode(
            id=f"episode_{datetime.now().timestamp()}_{created_days_ago}",
            title=f"Test Episode {created_days_ago} days ago",
            description="Test episode description",
            summary="Test episode summary",
            agent_id=agent.id,
            user_id=agent.user_id,
            workspace_id=agent.workspace_id,
            status="completed",
            started_at=started_at,
            ended_at=started_at + timedelta(minutes=30),
            duration_seconds=1800,
            maturity_at_time=maturity,
            human_intervention_count=intervention_count,
            constitutional_score=constitutional_score,
            importance_score=0.7,
            topics=["test", "episode"],
            entities=["test_entity"],
        )
        db.add(episode)
        db.commit()
        return episode

    return _create_episode


# ============================================================================
# Unit Tests
# ============================================================================

class TestSupervisionMetricsCalculation:
    """Test supervision metrics calculation for graduation."""

    @pytest.mark.asyncio
    async def test_calculate_supervision_metrics_basic(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
    ):
        """Test basic supervision metrics calculation."""
        # Create supervision sessions
        for i in range(10):
            supervision_session_factory(
                intervention_count=i % 3,
                supervisor_rating=4 + (i % 2),
                started_at_days_ago=i,
            )

        service = AgentGraduationService(db)
        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.INTERN,
        )

        assert metrics["total_sessions"] == 10
        assert metrics["total_supervision_hours"] > 0
        assert 0 <= metrics["average_supervisor_rating"] <= 5
        assert metrics["intervention_rate"] >= 0
        assert metrics["high_rating_sessions"] >= 0
        assert metrics["low_intervention_sessions"] >= 0

    @pytest.mark.asyncio
    async def test_intervention_rate_calculation(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
    ):
        """Test intervention rate calculated correctly."""
        # Create sessions: 5 interventions over 1 hour
        supervision_session_factory(
            intervention_count=5,
            duration_seconds=3600,  # 1 hour
        )

        service = AgentGraduationService(db)
        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.INTERN,
        )

        # Intervention rate should be ~5 per hour
        assert metrics["intervention_rate"] > 4
        assert metrics["intervention_rate"] < 6

    @pytest.mark.asyncio
    async def test_high_rating_session_count(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
    ):
        """Test high-rating session counting."""
        # Create sessions with ratings 3, 4, 5, 5, 2
        ratings = [3, 4, 5, 5, 2]
        for rating in ratings:
            supervision_session_factory(supervisor_rating=rating)

        service = AgentGraduationService(db)
        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.INTERN,
        )

        # Should have 3 high-rating sessions (4, 5, 5)
        assert metrics["high_rating_sessions"] == 3

    @pytest.mark.asyncio
    async def test_low_intervention_session_count(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
    ):
        """Test low-intervention session counting."""
        # Create sessions: 0, 0, 1, 2, 5 interventions
        intervention_counts = [0, 0, 1, 2, 5]
        for count in intervention_counts:
            supervision_session_factory(intervention_count=count)

        service = AgentGraduationService(db)
        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.INTERN,
        )

        # Should have 3 low-intervention sessions (0, 0, 1)
        assert metrics["low_intervention_sessions"] == 3

    @pytest.mark.asyncio
    async def test_performance_trend_improving(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
    ):
        """Test performance trend detection for improving agent."""
        # Recent sessions (better)
        for i in range(5):
            supervision_session_factory(
                supervisor_rating=5,
                intervention_count=0,
                started_at_days_ago=i,
            )

        # Older sessions (worse)
        for i in range(5, 10):
            supervision_session_factory(
                supervisor_rating=3,
                intervention_count=3,
                started_at_days_ago=i,
            )

        service = AgentGraduationService(db)
        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.INTERN,
        )

        assert metrics["recent_performance_trend"] == "improving"

    @pytest.mark.asyncio
    async def test_performance_trend_declining(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
    ):
        """Test performance trend detection for declining agent."""
        # Recent sessions (worse)
        for i in range(5):
            supervision_session_factory(
                supervisor_rating=3,
                intervention_count=3,
                started_at_days_ago=i,
            )

        # Older sessions (better)
        for i in range(5, 10):
            supervision_session_factory(
                supervisor_rating=5,
                intervention_count=0,
                started_at_days_ago=i,
            )

        service = AgentGraduationService(db)
        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.INTERN,
        )

        assert metrics["recent_performance_trend"] == "declining"


class TestGraduationValidationWithSupervision:
    """Test graduation validation with supervision data."""

    @pytest.mark.asyncio
    async def test_combined_validation_ready(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
        episode_factory,
    ):
        """Test graduation validation when ready with supervision data."""
        # Create excellent supervision history
        for i in range(15):
            supervision_session_factory(
                intervention_count=0,
                supervisor_rating=5,
            )

        # Create excellent episode history
        for i in range(15):
            episode_factory(
                intervention_count=0,
                constitutional_score=0.95,
            )

        service = AgentGraduationService(db)
        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.SUPERVISED,
        )

        assert result["ready"] is True
        assert result["score"] > 70
        assert len(result["gaps"]) == 0
        assert "supervision_metrics" in result
        assert "episode_metrics" in result

    @pytest.mark.asyncio
    async def test_combined_validation_not_ready_low_rating(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
        episode_factory,
    ):
        """Test graduation validation fails with low supervisor ratings."""
        # Create poor supervision history
        for i in range(10):
            supervision_session_factory(
                intervention_count=5,
                supervisor_rating=2,
            )

        # Create good episode history
        for i in range(15):
            episode_factory(
                intervention_count=0,
                constitutional_score=0.9,
            )

        service = AgentGraduationService(db)
        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.SUPERVISED,
        )

        assert result["ready"] is False
        assert any("rating" in gap.lower() for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_combined_score_calculation(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
        episode_factory,
    ):
        """Test combined score calculation (70% episode, 30% supervision)."""
        # Create moderate history
        for i in range(10):
            supervision_session_factory(
                intervention_count=2,
                supervisor_rating=4,
            )
            episode_factory(
                intervention_count=1,
                constitutional_score=0.85,
            )

        service = AgentGraduationService(db)
        result = await service.validate_graduation_with_supervision(
            agent_id=agent.id,
            target_maturity=AgentStatus.SUPERVISED,
        )

        # Score should be reasonable
        assert 0 <= result["score"] <= 100
        assert "episode_metrics" in result
        assert "supervision_metrics" in result


# ============================================================================
# Property-Based Tests
# ============================================================================

class TestSupervisionMetricsProperties:
    """Property-based tests for supervision metrics."""

    @given(
        st.lists(
            st.integers(min_value=0, max_value=10),
            min_size=10,
            max_size=50,
        ),
        st.lists(
            st.integers(min_value=1, max_value=5),
            min_size=10,
            max_size=50,
        ),
    )
    @settings(max_examples=10)
    @pytest.mark.asyncio
    async def test_intervention_rate_bounds(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
        intervention_counts,
        ratings,
    ):
        """Test intervention rate always within reasonable bounds."""
        # Create sessions
        for i, (interventions, rating) in enumerate(zip(intervention_counts, ratings)):
            supervision_session_factory(
                intervention_count=interventions,
                supervisor_rating=rating,
                started_at_days_ago=i,
                duration_seconds=3600,  # 1 hour each
            )

        service = AgentGraduationService(db)
        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.INTERN,
        )

        # Intervention rate should be non-negative
        assert metrics["intervention_rate"] >= 0
        # With 1-hour sessions, rate should equal total interventions
        expected_rate = sum(intervention_counts) / len(intervention_counts)
        assert abs(metrics["intervention_rate"] - expected_rate) < 0.1

    @given(
        st.lists(
            st.integers(min_value=1, max_value=5),
            min_size=10,
            max_size=50,
        ),
    )
    @settings(max_examples=10)
    @pytest.mark.asyncio
    async def test_average_rating_bounds(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
        ratings,
    ):
        """Test average rating always within [1, 5] bounds."""
        for i, rating in enumerate(ratings):
            supervision_session_factory(
                supervisor_rating=rating,
                started_at_days_ago=i,
            )

        service = AgentGraduationService(db)
        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.INTERN,
        )

        assert 1.0 <= metrics["average_supervisor_rating"] <= 5.0
        # Should match actual average
        expected_avg = sum(ratings) / len(ratings)
        assert abs(metrics["average_supervisor_rating"] - expected_avg) < 0.01

    @given(
        st.integers(min_value=0, max_value=10),
        st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=10)
    @pytest.mark.asyncio
    async def test_high_and_low_intervention_counts(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
        high_count,
        low_count,
    ):
        """Test high and low intervention session counting."""
        # Create high-intervention sessions
        for _ in range(high_count):
            supervision_session_factory(intervention_count=0)

        # Create low-intervention sessions
        for _ in range(low_count):
            supervision_session_factory(intervention_count=5)

        service = AgentGraduationService(db)
        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.INTERN,
        )

        # High-rating = low intervention (0-1)
        # Should equal high_count
        assert metrics["low_intervention_sessions"] == high_count

    @given(
        st.lists(
            st.integers(min_value=1, max_value=5),
            min_size=20,
            max_size=20,
        ),
    )
    @settings(max_examples=5)
    @pytest.mark.asyncio
    async def test_performance_trend_categories(
        self,
        db: Session,
        agent: AgentRegistry,
        supervision_session_factory,
        ratings,
    ):
        """Test performance trend always returns valid category."""
        for i, rating in enumerate(ratings):
            supervision_session_factory(
                supervisor_rating=rating,
                started_at_days_ago=i,
            )

        service = AgentGraduationService(db)
        metrics = await service.calculate_supervision_metrics(
            agent_id=agent.id,
            maturity_level=AgentStatus.INTERN,
        )

        assert metrics["recent_performance_trend"] in ["improving", "stable", "declining", "unknown"]
