"""
Comprehensive Unit Tests for Episode Service

Target: core/episode_service.py

Test Coverage Areas:
1. Episode Creation (10 tests)
2. Episode Retrieval (7 tests)
3. Graduation Readiness (4 tests)
4. Feedback System / RLHF (4 tests)
5. Canvas Integration (3 tests)
6. Skill Performance (2 tests)
7. LanceDB Integration (2 tests)
8. Edge Cases (6 tests)

The service persists through a real (temp-file) SQLite session created by the
``db`` fixture in tests/unit/conftest.py; LanceDB and the embedding service are
mocked so no external services are required. Methods that are ``async`` in
production are driven with ``asyncio.run``.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, timezone
import asyncio

from core.episode_service import (
    EpisodeService, ReadinessResponse, ReadinessThresholds, DetailLevel,
    PROGRESSIVE_QUERIES
)
from core.models import (
    AgentEpisode, AgentExecution, AgentRegistry, EpisodeOutcome,
    AgentStatus, GraduationExam, Episode, EpisodeSegment, CanvasAudit
)


# ========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def db_session(db):
    """Real SQLite session (tables created by tests/unit/conftest.py)."""
    return db


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB service.

    ``EpisodeService.archive_episode_to_cold_storage`` calls ``add_episode``
    synchronously, so the mock must be a plain Mock (not an AsyncMock).
    """
    lancedb = Mock()
    lancedb.connect = Mock(return_value=True)
    lancedb.get_or_create_episodes_table = Mock()
    lancedb.add_episode = Mock(return_value=True)
    lancedb.search_episodes = Mock(return_value=[])
    return lancedb


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service."""
    embedding = Mock()
    embedding.get_embedding_dimension = Mock(return_value=384)
    embedding.embed_text = Mock(return_value=[0.1] * 384)
    embedding.generate_embedding = AsyncMock(return_value=[0.1] * 384)
    return embedding


@pytest.fixture
def episode_service(db_session, mock_embedding_service, mock_lancedb):
    """Create episode service with mocked dependencies."""
    service = EpisodeService(db_session, embedding_service=mock_embedding_service)
    service.lancedb = mock_lancedb
    return service


@pytest.fixture
def test_agent(db_session):
    """Create a test agent."""
    agent = AgentRegistry(
        id="test-agent-1",
        name="TestAgent",
        category="test",
        module_path="test.module",
        class_name="TestAgent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        tenant_id="default"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def test_execution(db_session, test_agent):
    """Create a test agent execution (current AgentExecution schema)."""
    execution = AgentExecution(
        id="test-execution-1",
        agent_id=test_agent.id,
        tenant_id="default",
        status="completed",
        input_summary="Test task",
        result_summary="success",
        output_summary="success",
        metadata_json={"query": "test"},
        human_intervention_count=0,
        started_at=datetime.now(timezone.utc) - timedelta(hours=1),
        completed_at=datetime.now(timezone.utc)
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return execution


# ========================================================================
# Helpers
# =========================================================================

class _FakeRow:
    """Mimics a SQLAlchemy row object (exposes ``_mapping``)."""

    def __init__(self, mapping):
        self._mapping = mapping


class _FakeResult:
    """Mimics a SQLAlchemy result with ``fetchall``."""

    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


def _stub_progressive_query(db_session, rows):
    """Stub the Postgres-only progressive-detail SQL.

    ``recall_episodes_with_detail`` executes raw SQL that uses JSONB operators
    (``->>``, ``jsonb_array_length``), which SQLite cannot run. Only those
    exact query templates are stubbed; every other statement (including the
    tenant ownership check) still hits the real SQLite session, so agent
    scoping and ORM loading stay covered.
    """
    real_execute = db_session.execute
    progressive_sql = {q.strip() for q in PROGRESSIVE_QUERIES.values()}

    def execute(statement, *args, **kwargs):
        if str(statement).strip() in progressive_sql:
            return _FakeResult([_FakeRow(r) for r in rows])
        return real_execute(statement, *args, **kwargs)

    db_session.execute = execute


# ========================================================================
# 1. Episode Creation Tests (10 tests)
# =========================================================================

class TestEpisodeCreation:
    """Test episode creation from agent executions."""

    def test_create_episode_from_execution_success(self, db_session, test_execution, episode_service):
        """Test successful episode creation from execution."""
        episode = asyncio.run(episode_service.create_episode_from_execution(
            execution_id=test_execution.id,
            task_description="Test episode creation",
            outcome=EpisodeOutcome.SUCCESS.value,
            success=True
        ))

        assert episode is not None
        assert episode.id is not None
        assert episode.agent_id == test_execution.agent_id
        assert episode.execution_id == test_execution.id
        assert episode.task_description == "Test episode creation"
        assert episode.outcome == EpisodeOutcome.SUCCESS.value
        assert episode.success == True

        # Episode is persisted
        stored = db_session.query(AgentEpisode).filter(
            AgentEpisode.id == episode.id
        ).one()
        assert stored.outcome == EpisodeOutcome.SUCCESS.value

    def test_create_episode_with_context(self, db_session, test_execution, episode_service):
        """Test episode creation with context variables."""
        context = {
            "user_id": "test-user",
            "task_type": "analysis",
            "workspace_id": "workspace-1"
        }

        episode = asyncio.run(episode_service.create_episode_from_execution(
            execution_id=test_execution.id,
            task_description="Test with context",
            outcome=EpisodeOutcome.SUCCESS.value,
            success=True,
            metadata=context
        ))

        assert episode.metadata_json is not None
        assert episode.metadata_json.get("user_id") == "test-user"
        assert episode.metadata_json.get("task_type") == "analysis"

    def test_create_episode_with_agent_id(self, db_session, test_execution, episode_service):
        """Test episode creation linked to agent."""
        episode = asyncio.run(episode_service.create_episode_from_execution(
            execution_id=test_execution.id,
            task_description="Test agent linkage",
            outcome=EpisodeOutcome.SUCCESS.value,
            success=True
        ))

        assert episode.agent_id == test_execution.agent_id
        assert episode.maturity_at_time is not None
        assert episode.maturity_at_time == AgentStatus.INTERN.value

    def test_create_episode_invalid_agent_id(self, db_session, episode_service):
        """Test episode creation with invalid agent ID."""
        with pytest.raises(ValueError):
            asyncio.run(episode_service.create_episode_from_execution(
                execution_id="non-existent-execution",
                task_description="Test invalid agent",
                outcome=EpisodeOutcome.SUCCESS.value,
                success=True
            ))

    def test_create_episode_duplicate_id(self, db_session, test_execution, episode_service):
        """Test handling of duplicate episode ID."""
        # First episode
        episode1 = asyncio.run(episode_service.create_episode_from_execution(
            execution_id=test_execution.id,
            task_description="First episode",
            outcome=EpisodeOutcome.SUCCESS.value,
            success=True
        ))

        # Attempt to create duplicate - should handle gracefully
        # (actual implementation may create new episode with different ID)
        episode2 = asyncio.run(episode_service.create_episode_from_execution(
            execution_id=test_execution.id,
            task_description="Second episode",
            outcome=EpisodeOutcome.SUCCESS.value,
            success=True
        ))

        assert episode1.id != episode2.id

    def test_create_episode_with_metadata(self, db_session, test_execution, episode_service):
        """Test episode creation with metadata."""
        metadata = {
            "canvas_type": "chart",
            "presentation_summary": "Sales data visualization",
            "visual_elements": ["bar-chart", "legend"]
        }

        episode = asyncio.run(episode_service.create_episode_from_execution(
            execution_id=test_execution.id,
            task_description="Test with metadata",
            outcome=EpisodeOutcome.SUCCESS.value,
            success=True,
            metadata=metadata
        ))

        assert episode.metadata_json is not None
        assert episode.metadata_json.get("canvas_type") == "chart"

    def test_create_episode_performance_benchmark(self, db_session, test_execution, episode_service):
        """Test episode creation performance (target: <100ms)."""
        import time

        start = time.time()
        episode = asyncio.run(episode_service.create_episode_from_execution(
            execution_id=test_execution.id,
            task_description="Performance test",
            outcome=EpisodeOutcome.SUCCESS.value,
            success=True
        ))
        duration = (time.time() - start) * 1000  # Convert to ms

        assert episode is not None
        assert duration < 100, f"Episode creation took {duration}ms, target <100ms"

    def test_create_episode_with_failure_outcome(self, db_session, test_execution, episode_service):
        """Test episode creation with failure outcome."""
        episode = asyncio.run(episode_service.create_episode_from_execution(
            execution_id=test_execution.id,
            task_description="Failed task",
            outcome=EpisodeOutcome.FAILURE.value,
            success=False
        ))

        assert episode.outcome == EpisodeOutcome.FAILURE.value
        assert episode.success == False

    def test_create_episode_with_constitutional_violations(self, db_session, test_execution, episode_service):
        """Test episode creation with constitutional violations."""
        violations = [
            {"type": "safety", "description": "Unsafe action detected"},
            {"type": "policy", "description": "Policy violation"}
        ]

        episode = asyncio.run(episode_service.create_episode_from_execution(
            execution_id=test_execution.id,
            task_description="Task with violations",
            outcome=EpisodeOutcome.FAILURE.value,
            success=False,
            constitutional_violations=violations
        ))

        # Violations are folded into the constitutional compliance score
        # (2 unspecified-severity violations default to "low" = 0.1 penalty each)
        assert episode.constitutional_score is not None
        assert episode.constitutional_score == pytest.approx(0.8)

    def test_create_episode_auto_id_generation(self, db_session, test_execution, episode_service):
        """Test automatic episode ID generation."""
        episode = asyncio.run(episode_service.create_episode_from_execution(
            execution_id=test_execution.id,
            task_description="Test auto ID",
            outcome=EpisodeOutcome.SUCCESS.value,
            success=True
        ))

        assert episode.id is not None
        assert len(episode.id) > 0


# ========================================================================
# 2. Episode Retrieval Tests
# =========================================================================

class TestEpisodeRetrieval:
    """Test episode retrieval methods."""

    def test_get_agent_episodes_default_limit(self, db_session, test_agent, episode_service):
        """Test retrieving episodes with default limit."""
        # Create multiple episodes
        for i in range(5):
            episode = AgentEpisode(
                id=f"episode-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                status="active"
            )
            db_session.add(episode)
        db_session.commit()

        episodes = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default"
        )

        assert len(episodes) == 5
        assert len(episodes) <= 50  # Default limit

    def test_get_agent_episodes_with_limit(self, db_session, test_agent, episode_service):
        """Test retrieving episodes with custom limit."""
        # Create multiple episodes
        for i in range(10):
            episode = AgentEpisode(
                id=f"episode-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                status="active"
            )
            db_session.add(episode)
        db_session.commit()

        episodes = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default",
            limit=5
        )

        assert len(episodes) == 5

    def test_get_agent_episodes_empty_result(self, db_session, episode_service):
        """Test retrieving episodes when none exist."""
        episodes = episode_service.get_agent_episodes(
            agent_id="non-existent-agent",
            tenant_id="default"
        )

        assert len(episodes) == 0

    def test_get_agent_episodes_with_outcome_filter(self, db_session, test_agent, episode_service):
        """Test retrieving episodes filtered by outcome."""
        # Create episodes with different outcomes
        for i in range(3):
            episode = AgentEpisode(
                id=f"episode-success-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Success task {i}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                status="active"
            )
            db_session.add(episode)

        for i in range(2):
            episode = AgentEpisode(
                id=f"episode-failure-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Failure task {i}",
                maturity_at_time="intern",
                outcome="failure",
                success=False,
                status="active"
            )
            db_session.add(episode)
        db_session.commit()

        episodes = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default",
            outcome_filter="success"
        )

        assert len(episodes) == 3
        assert all(e.outcome == "success" for e in episodes)

    def test_recall_episodes_with_summary_detail(self, db_session, test_agent, episode_service):
        """Test recalling episodes with SUMMARY detail level."""
        # Create test episode
        episode = AgentEpisode(
            id="episode-summary-test",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="Summary test",
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active",
            metadata_json={
                "canvas_type": "chart",
                "presentation_summary": "Test summary"
            }
        )
        db_session.add(episode)
        db_session.commit()

        # The progressive-detail SQL uses Postgres JSONB operators, so serve
        # the rows the query would produce for the episode created above.
        _stub_progressive_query(db_session, [{
            "id": episode.id,
            "agent_id": test_agent.id,
            "task_description": episode.task_description,
            "outcome": episode.outcome,
            "success": episode.success,
            "constitutional_score": episode.constitutional_score,
            "human_intervention_count": episode.human_intervention_count,
            "started_at": episode.started_at,
            "completed_at": episode.completed_at,
            "canvas_type": "chart",
            "presentation_summary": "Test summary",
            "has_errors": False,
        }])

        episodes = asyncio.run(episode_service.recall_episodes_with_detail(
            agent_id=test_agent.id,
            tenant_id="default",
            detail_level=DetailLevel.SUMMARY,
            limit=10
        ))

        assert len(episodes) > 0
        # Summary detail should include basic fields
        assert episodes[0].get("id") == episode.id
        assert episodes[0].get("task_description") is not None
        assert episodes[0].get("canvas_type") == "chart"

        # Tenant ownership check is enforced against the real session
        other_tenant = asyncio.run(episode_service.recall_episodes_with_detail(
            agent_id=test_agent.id,
            tenant_id="not-our-tenant",
            detail_level=DetailLevel.SUMMARY,
            limit=10
        ))
        assert other_tenant == []

    def test_recall_episodes_with_standard_detail(self, db_session, test_agent, episode_service):
        """Test recalling episodes with STANDARD detail level."""
        episode = AgentEpisode(
            id="episode-standard-test",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="Standard test",
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active",
            metadata_json={
                "canvas_type": "chart",
                "presentation_summary": "Test summary",
                "visual_elements": ["bar-chart"],
                "critical_data_points": [{"x": 1, "y": 2}]
            }
        )
        db_session.add(episode)
        db_session.commit()

        _stub_progressive_query(db_session, [{
            "id": episode.id,
            "task_description": episode.task_description,
            "canvas_type": "chart",
            "presentation_summary": "Test summary",
            "visual_elements": ["bar-chart"],
            "critical_data_points": [{"x": 1, "y": 2}],
            "has_errors": False,
        }])

        episodes = asyncio.run(episode_service.recall_episodes_with_detail(
            agent_id=test_agent.id,
            tenant_id="default",
            detail_level=DetailLevel.STANDARD,
            limit=10
        ))

        assert len(episodes) > 0
        # Standard detail should include visual elements
        assert episodes[0].get("visual_elements") is not None

    def test_recall_episodes_performance_benchmark(self, db_session, test_agent, episode_service):
        """Test episode recall performance (target: <50ms)."""
        # Create test episodes
        for i in range(10):
            episode = AgentEpisode(
                id=f"episode-perf-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Performance test {i}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                status="active"
            )
            db_session.add(episode)
        db_session.commit()

        _stub_progressive_query(db_session, [
            {"id": f"episode-perf-{i}", "task_description": f"Performance test {i}"}
            for i in range(10)
        ])

        import time
        start = time.time()
        episodes = asyncio.run(episode_service.recall_episodes_with_detail(
            agent_id=test_agent.id,
            tenant_id="default",
            detail_level=DetailLevel.SUMMARY,
            limit=10
        ))
        duration = (time.time() - start) * 1000

        assert len(episodes) == 10
        assert duration < 50, f"Recall took {duration}ms, target <50ms"


# ========================================================================
# 3. Graduation Readiness Tests
# =========================================================================

class TestGraduationReadiness:
    """Test graduation readiness calculation."""

    def test_get_graduation_readiness_student_to_intern(self, db_session, test_agent, episode_service):
        """Test graduation readiness from STUDENT to INTERN."""
        # Create episodes meeting criteria
        for i in range(10):
            episode = AgentEpisode(
                id=f"episode-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time=AgentStatus.STUDENT.value,
                outcome="success",
                success=True,
                constitutional_score=0.8,
                human_intervention_count=0,
                confidence_score=0.6,
                status="active"
            )
            db_session.add(episode)
        db_session.commit()

        readiness = episode_service.get_graduation_readiness(
            agent_id=test_agent.id,
            tenant_id="default",
            episode_count=10,
            target_level=AgentStatus.INTERN.value
        )

        assert readiness is not None
        assert readiness.agent_id == test_agent.id
        assert readiness.current_level == AgentStatus.INTERN.value
        assert isinstance(readiness.readiness_score, float)
        assert readiness.episodes_analyzed == 10

    def test_get_graduation_readiness_insufficient_episodes(self, db_session, test_agent, episode_service):
        """Test graduation readiness with insufficient episodes."""
        # Create only 5 episodes (need 10)
        for i in range(5):
            episode = AgentEpisode(
                id=f"episode-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time=AgentStatus.STUDENT.value,
                outcome="success",
                success=True,
                status="active"
            )
            db_session.add(episode)
        db_session.commit()

        readiness = episode_service.get_graduation_readiness(
            agent_id=test_agent.id,
            tenant_id="default",
            episode_count=10,
            target_level=AgentStatus.INTERN.value
        )

        assert readiness.episodes_analyzed < 10
        assert readiness.threshold_met == False

    def test_calculate_readiness_metrics_success_rate(self, db_session, test_agent, episode_service):
        """Test calculating readiness metrics including success rate."""
        # Create mixed success/failure episodes
        for i in range(7):
            episode = AgentEpisode(
                id=f"episode-success-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Success {i}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                status="active"
            )
            db_session.add(episode)

        for i in range(3):
            episode = AgentEpisode(
                id=f"episode-failure-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Failure {i}",
                maturity_at_time="intern",
                outcome="failure",
                success=False,
                status="active"
            )
            db_session.add(episode)
        db_session.commit()

        episodes = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default",
            limit=10
        )

        assert len(episodes) == 10

        metrics = episode_service.calculate_readiness_metrics(episodes)

        assert metrics["success_rate"] == pytest.approx(0.7)
        assert metrics["episodes_by_outcome"] == {"success": 7, "failure": 3}

    def test_calculate_readiness_metrics_intervention_rate(self, db_session, test_agent, episode_service):
        """Test calculating intervention rate."""
        # Create episodes with interventions
        for i in range(5):
            episode = AgentEpisode(
                id=f"episode-no-intervention-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                human_intervention_count=0,
                status="active"
            )
            db_session.add(episode)

        for i in range(5):
            episode = AgentEpisode(
                id=f"episode-with-intervention-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Task {i+5}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                human_intervention_count=1,
                status="active"
            )
            db_session.add(episode)
        db_session.commit()

        episodes = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default",
            limit=10
        )

        metrics = episode_service.calculate_readiness_metrics(episodes)

        # 50% intervention rate
        assert metrics["zero_intervention_ratio"] == pytest.approx(0.5)
        assert metrics["total_interventions"] == 5

    def test_get_graduation_readiness_performance_benchmark(self, db_session, test_agent, episode_service):
        """Test graduation readiness calculation performance (target: <200ms)."""
        # Create test episodes
        for i in range(25):
            episode = AgentEpisode(
                id=f"episode-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                constitutional_score=0.85,
                human_intervention_count=0,
                confidence_score=0.7,
                status="active"
            )
            db_session.add(episode)
        db_session.commit()

        import time
        start = time.time()
        readiness = episode_service.get_graduation_readiness(
            agent_id=test_agent.id,
            tenant_id="default",
            episode_count=25,
            target_level=AgentStatus.SUPERVISED.value
        )
        duration = (time.time() - start) * 1000

        assert readiness is not None
        assert duration < 200, f"Readiness calculation took {duration}ms, target <200ms"


# ========================================================================
# 4. Feedback System Tests (RLHF)
# =========================================================================

class TestFeedbackSystem:
    """Test episode feedback and RLHF integration."""

    def test_update_episode_feedback_positive(self, db_session, test_agent, episode_service):
        """Test updating episode with positive feedback."""
        episode = AgentEpisode(
            id="episode-feedback-test",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="Feedback test",
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active"
        )
        db_session.add(episode)
        db_session.commit()

        feedback_id = episode_service.update_episode_feedback(
            episode_id=episode.id,
            feedback_score=1.0,
            feedback_notes="Excellent work!",
            provider_id="test-user"
        )

        assert feedback_id is not None

        feedback = episode_service.get_episode_feedback(episode.id)
        assert len(feedback) == 1
        assert feedback[0]["feedback_score"] == 1.0
        assert feedback[0]["feedback_notes"] == "Excellent work!"

        # Episode metadata carries the feedback reference
        db_session.refresh(episode)
        assert episode.metadata_json["feedback_id"] == feedback_id
        assert episode.metadata_json["feedback_score"] == 1.0

    def test_update_episode_feedback_negative(self, db_session, test_agent, episode_service):
        """Test updating episode with negative feedback."""
        episode = AgentEpisode(
            id="episode-negative-feedback",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="Negative feedback test",
            maturity_at_time="intern",
            outcome="failure",
            success=False,
            status="active"
        )
        db_session.add(episode)
        db_session.commit()

        feedback_id = episode_service.update_episode_feedback(
            episode_id=episode.id,
            feedback_score=-1.0,
            feedback_notes="Incorrect approach",
            provider_id="test-user"
        )

        assert feedback_id is not None

        feedback = episode_service.get_episode_feedback(episode.id)
        assert len(feedback) == 1
        assert feedback[0]["feedback_score"] == -1.0

    def test_get_episode_feedback(self, db_session, test_agent, episode_service):
        """Test retrieving episode feedback."""
        episode = AgentEpisode(
            id="episode-get-feedback",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="Get feedback test",
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active"
        )
        db_session.add(episode)
        db_session.commit()

        # Add feedback
        episode_service.update_episode_feedback(
            episode_id=episode.id,
            feedback_score=0.8,
            feedback_notes="Good job",
            provider_id="test-user"
        )

        feedback = episode_service.get_episode_feedback(episode.id)

        assert feedback is not None
        assert len(feedback) == 1
        assert feedback[0]["feedback_score"] == 0.8

    def test_get_domain_feedback_metrics(self, db_session, test_agent, episode_service):
        """Test retrieving feedback metrics for domain."""
        # Create episodes with feedback tagged to a capability domain
        for i in range(5):
            episode = AgentEpisode(
                id=f"episode-feedback-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Task {i}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                status="active"
            )
            db_session.add(episode)
        db_session.commit()

        for i in range(5):
            episode_service.update_episode_feedback(
                episode_id=f"episode-feedback-{i}",
                feedback_score=0.5 + (i * 0.1),
                feedback_notes=f"Feedback {i}",
                provider_id="test-user",
                capability_domain="test"
            )
        db_session.commit()

        metrics = episode_service.get_domain_feedback_metrics(
            tenant_id="default",
            domain="test",
            days=30
        )

        assert metrics is not None
        assert metrics["feedback_count"] == 5
        assert metrics["avg_rating"] == pytest.approx(0.7)
        assert "trend" in metrics


# ========================================================================
# 5. Canvas Integration Tests
# =========================================================================

class TestCanvasIntegration:
    """Test canvas and episode integration."""

    def test_extract_canvas_metadata(self, db_session, test_execution, episode_service):
        """Test extracting canvas metadata from execution."""
        metadata = asyncio.run(episode_service._extract_canvas_metadata(
            execution_id=test_execution.id,
            task_description="Test canvas metadata"
        ))

        assert metadata is not None
        assert isinstance(metadata, dict)
        # The test execution carries no canvas context
        assert metadata == {}

    def test_link_canvas_actions_to_episode(self, db_session, test_agent, episode_service):
        """Test linking canvas actions to episode."""
        episode = AgentEpisode(
            id="episode-canvas-link",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="Canvas link test",
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active"
        )
        db_session.add(episode)
        db_session.commit()

        canvas_action_ids = ["action-1", "action-2", "action-3"]
        linked = asyncio.run(episode_service.link_canvas_actions_to_episode(
            episode_id=episode.id,
            canvas_action_ids=canvas_action_ids
        ))

        assert linked is True

        stored = db_session.query(AgentEpisode).filter(
            AgentEpisode.id == episode.id
        ).one()
        assert stored.metadata_json["canvas_action_ids"] == canvas_action_ids
        assert len(stored.metadata_json["canvas_action_ids"]) == 3

    def test_get_canvas_actions_for_episode(self, db_session, test_agent, episode_service):
        """Test retrieving canvas actions for episode."""
        episode = AgentEpisode(
            id="episode-canvas-actions",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="Canvas actions test",
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active",
            canvas_action_count=2,
            metadata_json={"canvas_action_ids": ["canvas-audit-0", "canvas-audit-1"]}
        )
        db_session.add(episode)

        # Create canvas audit records
        for i in range(2):
            audit = CanvasAudit(
                id=f"canvas-audit-{i}",
                canvas_id=f"canvas-{i}",
                tenant_id="default",
                agent_id=test_agent.id,
                action_type="present",
                details_json={
                    'canvas_type': 'chart',
                },
            )
            db_session.add(audit)
        db_session.commit()

        actions = episode_service.get_canvas_actions_for_episode(episode.id)

        assert actions is not None
        assert len(actions) == 2
        assert {a["id"] for a in actions} == {"canvas-audit-0", "canvas-audit-1"}
        assert all(a["action_type"] == "present" for a in actions)


# ========================================================================
# 6. Skill Performance Tests
# =========================================================================

class TestSkillPerformance:
    """Test skill performance tracking."""

    def test_get_skill_performance_stats(self, db_session, test_agent, episode_service):
        """Test retrieving skill performance statistics."""
        # Create episodes with skill usage (skill_type marks OpenClaw runs)
        for i in range(5):
            episode = AgentEpisode(
                id=f"episode-skill-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Skill task {i}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                status="active",
                metadata_json={"skill_type": "openclaw", "skill_id": "data-analysis"}
            )
            db_session.add(episode)
        db_session.commit()

        stats = episode_service.get_skill_performance_stats(
            agent_id=test_agent.id,
            tenant_id="default",
            skill_id="data-analysis",
            limit=5
        )

        assert stats is not None
        assert stats.skill_id == "data-analysis"
        assert stats.total_executions == 5
        assert stats.successful_executions == 5
        assert stats.success_rate == pytest.approx(1.0)

    def test_get_agent_skill_usage(self, db_session, test_agent, episode_service):
        """Test retrieving agent skill usage history."""
        # Create episodes with different skills
        skills = ["data-analysis", "visualization", "reporting"]
        for i, skill in enumerate(skills):
            episode = AgentEpisode(
                id=f"episode-usage-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"{skill} task",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                status="active",
                metadata_json={"skill_type": "openclaw", "skill_id": skill}
            )
            db_session.add(episode)
        db_session.commit()

        usage = episode_service.get_agent_skill_usage(
            agent_id=test_agent.id,
            tenant_id="default",
            limit=10
        )

        assert usage is not None
        assert len(usage) == 3
        assert {u.skill_id for u in usage} == set(skills)
        assert all(u.execution_count == 1 for u in usage)


# ========================================================================
# 7. LanceDB Integration Tests
# =========================================================================

class TestLanceDBIntegration:
    """Test LanceDB integration for cold storage."""

    def test_archive_episode_to_cold_storage(self, db_session, test_agent, episode_service, mock_lancedb):
        """Test archiving episode to LanceDB cold storage."""
        episode = AgentEpisode(
            id="episode-archive-test",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="Archive test",
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active"
        )
        db_session.add(episode)
        db_session.commit()

        result = asyncio.run(episode_service.archive_episode_to_cold_storage(episode.id))

        assert result is True
        mock_lancedb.add_episode.assert_called_once()
        archived_episode, embedding = mock_lancedb.add_episode.call_args[0]
        assert archived_episode.id == episode.id

    def test_lancedb_connection_failure(self, db_session, test_agent, episode_service):
        """Test handling LanceDB connection failure."""
        episode = AgentEpisode(
            id="episode-conn-fail",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="Connection failure test",
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active"
        )
        db_session.add(episode)
        db_session.commit()

        # Force a cold-storage connection failure: no cached client and the
        # freshly initialised one fails to connect.
        episode_service.lancedb = None
        with patch("core.episode_service.LanceDBService") as mock_lancedb_cls:
            mock_lancedb_cls.return_value.connect.return_value = False

            # Should handle gracefully
            result = asyncio.run(episode_service.archive_episode_to_cold_storage(episode.id))

        mock_lancedb_cls.return_value.connect.assert_called_once()
        # Service should continue without LanceDB
        assert result is False or result is None


# ========================================================================
# 8. Edge Case Tests
# =========================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_episode_with_unicode_content(self, db_session, test_agent, episode_service):
        """Test episode with Unicode characters."""
        unicode_text = "Test with emoji 🎉 and 中文 characters"

        episode = AgentEpisode(
            id="episode-unicode",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description=unicode_text,
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active",
            metadata_json={"unicode_field": "日本語テスト"}
        )
        db_session.add(episode)
        db_session.commit()

        retrieved = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default",
            limit=1
        )

        assert len(retrieved) > 0
        assert retrieved[0].task_description == unicode_text
        assert retrieved[0].metadata_json["unicode_field"] == "日本語テスト"

    def test_episode_with_special_characters(self, db_session, test_agent, episode_service):
        """Test episode with special characters."""
        special_text = "Test with quotes \"', newlines\n, tabs\t"

        episode = AgentEpisode(
            id="episode-special-chars",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description=special_text,
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active"
        )
        db_session.add(episode)
        db_session.commit()

        retrieved = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default",
            limit=1
        )

        assert len(retrieved) > 0
        assert retrieved[0].task_description == special_text

    def test_episode_with_null_metadata(self, db_session, test_agent, episode_service):
        """Test episode with null metadata."""
        episode = AgentEpisode(
            id="episode-null-metadata",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="Null metadata test",
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active",
            metadata_json=None
        )
        db_session.add(episode)
        db_session.commit()

        retrieved = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default",
            limit=1
        )

        assert len(retrieved) > 0
        assert retrieved[0].metadata_json is None

    def test_episode_with_empty_task_description(self, db_session, test_agent, episode_service):
        """Test episode with empty task description."""
        episode = AgentEpisode(
            id="episode-empty-task",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description="",
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active"
        )
        db_session.add(episode)
        db_session.commit()

        retrieved = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default",
            limit=1
        )

        assert len(retrieved) > 0
        assert retrieved[0].task_description == ""

    def test_concurrent_episode_creation(self, db_session, test_agent, episode_service):
        """Test concurrent episode creation."""
        async def create_episode(i):
            return AgentEpisode(
                id=f"episode-concurrent-{i}",
                agent_id=test_agent.id,
                tenant_id="default",
                task_description=f"Concurrent task {i}",
                maturity_at_time="intern",
                outcome="success",
                success=True,
                status="active"
            )

        async def create_episodes():
            episodes = await asyncio.gather(*[create_episode(i) for i in range(10)])
            for ep in episodes:
                db_session.add(ep)
            db_session.commit()
            return episodes

        episodes = asyncio.run(create_episodes())

        assert len(episodes) == 10

        retrieved = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default",
            limit=10
        )
        assert len(retrieved) == 10

    def test_episode_with_very_long_content(self, db_session, test_agent, episode_service):
        """Test episode with very long content (>1MB)."""
        long_content = "x" * (1_000_000 + 1)  # >1MB

        episode = AgentEpisode(
            id="episode-long-content",
            agent_id=test_agent.id,
            tenant_id="default",
            task_description=long_content[:1000],  # Truncate for task description
            maturity_at_time="intern",
            outcome="success",
            success=True,
            status="active",
            metadata_json={"long_field": long_content}
        )
        db_session.add(episode)
        db_session.commit()

        retrieved = episode_service.get_agent_episodes(
            agent_id=test_agent.id,
            tenant_id="default",
            limit=1
        )

        assert len(retrieved) > 0
        assert len(retrieved[0].metadata_json["long_field"]) == len(long_content)
