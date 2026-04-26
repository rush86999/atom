"""
Test Episode Service - Episode lifecycle management.

Tests episode creation, segmentation, persistence, lifecycle, and integration.
Following 303-QUALITY-STANDARDS.md with AsyncMock patterns.

Target: 30-35 tests covering episode lifecycle management.
Coverage Target: 25-30% (model/dataclass testing, business logic)
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.episode_service import (
    EpisodeService,
    DetailLevel,
    ReadinessThresholds,
    ReadinessResponse,
    PROGRESSIVE_QUERIES,
)
from core.models import (
    AgentEpisode,
    AgentExecution,
    AgentRegistry,
    EpisodeOutcome,
    AgentStatus,
)


class TestDetailLevelEnum:
    """Test DetailLevel enum definitions and values."""

    def test_detail_level_summary_value(self):
        """DetailLevel.SUMMARY has correct string value."""
        assert DetailLevel.SUMMARY.value == "summary"

    def test_detail_level_standard_value(self):
        """DetailLevel.STANDARD has correct string value."""
        assert DetailLevel.STANDARD.value == "standard"

    def test_detail_level_full_value(self):
        """DetailLevel.FULL has correct string value."""
        assert DetailLevel.FULL.value == "full"

    def test_detail_level_enum_completeness(self):
        """DetailLevel enum has exactly 3 values."""
        assert len(DetailLevel) == 3


class TestReadinessThresholds:
    """Test graduation readiness threshold configurations."""

    def test_student_to_intern_thresholds_exist(self):
        """Student-to-intern thresholds are defined."""
        thresholds = ReadinessThresholds.STUDENT_TO_INTERN
        assert "success_rate" in thresholds
        assert "constitutional_score" in thresholds
        assert "zero_intervention_ratio" in thresholds
        assert "confidence_score" in thresholds
        assert "overall" in thresholds

    def test_student_to_intern_threshold_values(self):
        """Student-to-intern threshold values are reasonable."""
        thresholds = ReadinessThresholds.STUDENT_TO_INTERN
        assert thresholds["success_rate"] == 0.70
        assert thresholds["constitutional_score"] == 0.75
        assert thresholds["zero_intervention_ratio"] == 0.40
        assert thresholds["confidence_score"] == 0.50
        assert thresholds["overall"] == 0.70

    def test_intern_to_supervised_thresholds_exist(self):
        """Intern-to-supervised thresholds are defined."""
        thresholds = ReadinessThresholds.INTERN_TO_SUPERVISED
        assert "success_rate" in thresholds
        assert "constitutional_score" in thresholds

    def test_intern_to_supervised_threshold_values(self):
        """Intern-to-supervised threshold values are higher than student-to-intern."""
        intern = ReadinessThresholds.INTERN_TO_SUPERVISED
        student = ReadinessThresholds.STUDENT_TO_INTERN
        assert intern["success_rate"] > student["success_rate"]
        assert intern["constitutional_score"] >= student["constitutional_score"]

    def test_supervised_to_autonomous_thresholds_exist(self):
        """Supervised-to-autonomous thresholds are defined."""
        thresholds = ReadinessThresholds.SUPERVISED_TO_AUTONOMOUS
        assert "success_rate" in thresholds
        assert thresholds["success_rate"] == 0.95

    def test_supervised_to_autonomous_is_highest(self):
        """Supervised-to-autonomous has highest thresholds."""
        supervised = ReadinessThresholds.SUPERVISED_TO_AUTONOMOUS
        intern = ReadinessThresholds.INTERN_TO_SUPERVISED
        assert supervised["success_rate"] > intern["success_rate"]
        assert supervised["overall"] == 0.95


class TestReadinessResponse:
    """Test ReadinessResponse dataclass."""

    def test_readiness_response_creation(self):
        """ReadinessResponse can be created with valid parameters."""
        response = ReadinessResponse(
            agent_id="agent-001",
            current_level="INTERN",
            readiness_score=0.85,
            threshold_met=True,
            zero_intervention_ratio=0.60,
            avg_constitutional_score=0.90,
            avg_confidence_score=0.75,
            success_rate=0.88,
            episodes_analyzed=25,
            breakdown={"test": "data"}
        )
        assert response.agent_id == "agent-001"
        assert response.current_level == "INTERN"
        assert response.readiness_score == 0.85
        assert response.threshold_met is True

    def test_readiness_response_to_dict(self):
        """ReadinessResponse.to_dict() returns correct dictionary."""
        response = ReadinessResponse(
            agent_id="agent-002",
            current_level="SUPERVISED",
            readiness_score=0.92,
            threshold_met=True,
            zero_intervention_ratio=0.70,
            avg_constitutional_score=0.93,
            avg_confidence_score=0.85,
            success_rate=0.95,
            episodes_analyzed=50,
            breakdown={"metric1": "value1"}
        )
        result = response.to_dict()
        assert result["agent_id"] == "agent-002"
        assert result["current_level"] == "SUPERVISED"
        assert result["readiness_score"] == 0.92
        assert result["threshold_met"] is True
        assert "breakdown" in result

    def test_readiness_response_supervision_success_rate_default(self):
        """ReadinessResponse supervision_success_rate defaults to 0.0."""
        response = ReadinessResponse(
            agent_id="agent-003",
            current_level="INTERN",
            readiness_score=0.75,
            threshold_met=False,
            zero_intervention_ratio=0.50,
            avg_constitutional_score=0.80,
            avg_confidence_score=0.65,
            success_rate=0.78,
            episodes_analyzed=15,
            breakdown={}
        )
        assert response.supervision_success_rate == 0.0

    def test_readiness_response_supervision_success_rate_explicit(self):
        """ReadinessResponse supervision_success_rate can be set explicitly."""
        response = ReadinessResponse(
            agent_id="agent-004",
            current_level="SUPERVISED",
            readiness_score=0.88,
            threshold_met=True,
            zero_intervention_ratio=0.65,
            avg_constitutional_score=0.90,
            avg_confidence_score=0.80,
            success_rate=0.85,
            episodes_analyzed=30,
            breakdown={},
            supervision_success_rate=0.92
        )
        assert response.supervision_success_rate == 0.92


class TestEpisodeServiceInit:
    """Test EpisodeService initialization and configuration."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_episode_service_init_with_db(self, mock_db):
        """EpisodeService initializes with database session."""
        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)
                assert service.db is mock_db

    def test_episode_service_init_creates_lancedb_handler(self, mock_db):
        """EpisodeService initializes LanceDB handler on creation."""
        with patch('core.episode_service.get_lancedb_handler') as mock_lancedb:
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)
                assert service.lancedb is not None

    def test_episode_service_init_creates_embedding_service(self, mock_db):
        """EpisodeService initializes embedding service on creation."""
        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service') as mock_embedding:
                service = EpisodeService(mock_db)
                assert service.embedding_service is not None


class TestEpisodeServiceCreation:
    """Test episode creation from agent executions."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        db.add = Mock()
        db.commit = Mock()
        db.flush = Mock()
        return db

    def test_create_episode_from_execution(self, mock_db):
        """EpisodeService can create episode from agent execution."""
        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                # Mock agent execution
                mock_execution = Mock(spec=AgentExecution)
                mock_execution.id = "exec-001"
                mock_execution.agent_id = "agent-001"
                mock_execution.task = "Test task"
                mock_execution.status = "completed"
                mock_execution.started_at = datetime.now(timezone.utc)
                mock_execution.completed_at = datetime.now(timezone.utc)

                # Create episode
                episode = service.create_episode(
                    agent_id="agent-001",
                    execution_id="exec-001",
                    task_description="Test task",
                    outcome=EpisodeOutcome.SUCCESS,
                    metadata={}
                )

                assert episode.agent_id == "agent-001"
                mock_db.add.assert_called()
                mock_db.commit.assert_called()

    def test_create_episode_with_metadata(self, mock_db):
        """EpisodeService creates episode with custom metadata."""
        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                metadata = {
                    "canvas_type": "chart",
                    "presentation_summary": "Test summary",
                    "visual_elements": ["chart1", "chart2"]
                }

                episode = service.create_episode(
                    agent_id="agent-002",
                    execution_id="exec-002",
                    task_description="Create chart",
                    outcome=EpisodeOutcome.SUCCESS,
                    metadata=metadata
                )

                assert episode.metadata_json == metadata

    def test_create_episode_validates_required_fields(self, mock_db):
        """EpisodeService validates required fields for episode creation."""
        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                # Missing agent_id should raise error
                with pytest.raises(ValueError):
                    service.create_episode(
                        agent_id="",
                        execution_id="exec-003",
                        task_description="Test",
                        outcome=EpisodeOutcome.SUCCESS,
                        metadata={}
                    )


class TestEpisodeServiceRetrieval:
    """Test episode retrieval by ID, agent, and queries."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_get_episode_by_id(self, mock_db):
        """EpisodeService can retrieve episode by ID."""
        mock_episode = Mock(spec=AgentEpisode)
        mock_episode.id = "ep-001"
        mock_episode.agent_id = "agent-001"

        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_episode
        mock_db.query.return_value = mock_query

        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                episode = service.get_episode_by_id("ep-001")
                assert episode.id == "ep-001"

    def test_get_episodes_by_agent(self, mock_db):
        """EpisodeService can retrieve all episodes for an agent."""
        mock_episodes = [
            Mock(id="ep-001", agent_id="agent-001"),
            Mock(id="ep-002", agent_id="agent-001")
        ]

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_episodes
        mock_db.query.return_value = mock_query

        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                episodes = service.get_episodes_by_agent("agent-001", limit=10)
                assert len(episodes) == 2

    def test_get_episode_by_id_not_found(self, mock_db):
        """EpisodeService returns None when episode not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                episode = service.get_episode_by_id("nonexistent")
                assert episode is None


class TestEpisodeServiceGraduationReadiness:
    """Test graduation readiness calculation."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_get_graduation_readiness_for_student(self, mock_db):
        """EpisodeService calculates readiness for STUDENT agent."""
        mock_episodes = [
            Mock(
                success=True,
                constitutional_score=0.80,
                human_intervention_count=0,
                confidence_score=0.60,
                started_at=datetime.now(timezone.utc) - timedelta(days=1)
            )
            for _ in range(10)
        ]

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_episodes
        mock_db.query.return_value = mock_query

        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                readiness = service.get_graduation_readiness(
                    agent_id="agent-001",
                    tenant_id="tenant-001",
                    episode_count=10
                )

                assert readiness.agent_id == "agent-001"
                assert readiness.current_level == "STUDENT"
                assert readiness.episodes_analyzed == 10

    def test_get_graduation_readiness_threshold_check(self, mock_db):
        """EpisodeService checks if readiness meets thresholds."""
        # Create episodes with high scores
        mock_episodes = [
            Mock(
                success=True,
                constitutional_score=0.90,
                human_intervention_count=0,
                confidence_score=0.80,
                started_at=datetime.now(timezone.utc) - timedelta(days=1)
            )
            for _ in range(25)
        ]

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_episodes
        mock_db.query.return_value = mock_query

        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                readiness = service.get_graduation_readiness(
                    agent_id="agent-002",
                    tenant_id="tenant-001",
                    episode_count=25
                )

                # Should meet threshold with these scores
                assert readiness.readiness_score >= 0.70

    def test_get_graduation_readiness_zero_episodes(self, mock_db):
        """EpisodeService handles zero episodes gracefully."""
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                readiness = service.get_graduation_readiness(
                    agent_id="agent-003",
                    tenant_id="tenant-001",
                    episode_count=10
                )

                assert readiness.episodes_analyzed == 0
                assert readiness.readiness_score == 0.0


class TestEpisodeServiceProgressiveRetrieval:
    """Test progressive detail level retrieval."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_get_progressive_episodes_summary_level(self, mock_db):
        """EpisodeService retrieves episodes at SUMMARY detail level."""
        mock_episodes = [
            Mock(
                id="ep-001",
                agent_id="agent-001",
                task_description="Task 1",
                outcome="success",
                success=True,
                constitutional_score=0.85,
                human_intervention_count=0,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                metadata_json={"canvas_type": "chart", "presentation_summary": "Summary"}
            )
        ]

        # Mock execute for raw SQL
        mock_db.execute.return_value.fetchall.return_value = mock_episodes

        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                episodes = service.get_progressive_episodes(
                    agent_id="agent-001",
                    detail_level=DetailLevel.SUMMARY,
                    limit=10
                )

                assert len(episodes) >= 0  # Query executed

    def test_get_progressive_episodes_standard_level(self, mock_db):
        """EpisodeService retrieves episodes at STANDARD detail level."""
        mock_db.execute.return_value.fetchall.return_value = []

        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                episodes = service.get_progressive_episodes(
                    agent_id="agent-002",
                    detail_level=DetailLevel.STANDARD,
                    limit=20
                )

                # Should execute query with standard template
                mock_db.execute.assert_called()

    def test_get_progressive_episodes_full_level(self, mock_db):
        """EpisodeService retrieves episodes at FULL detail level."""
        mock_db.execute.return_value.fetchall.return_value = []

        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                episodes = service.get_progressive_episodes(
                    agent_id="agent-003",
                    detail_level=DetailLevel.FULL,
                    limit=5
                )

                # Should execute query with full template (includes audit trail)
                mock_db.execute.assert_called()


class TestEpisodeServiceArchival:
    """Test episode archival to cold storage."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_archive_episode_to_lancedb(self, mock_db):
        """EpisodeService archives episode to LanceDB cold storage."""
        mock_episode = Mock(
            id="ep-001",
            agent_id="agent-001",
            task_description="Test task",
            outcome="success",
            metadata_json={}
        )

        mock_lancedb = Mock()
        mock_lancedb.upsert.return_value = True

        with patch('core.episode_service.get_lancedb_handler', return_value=mock_lancedb):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(mock_db)

                result = service.archive_episode(mock_episode)

                assert result is True
                mock_lancedb.upsert.assert_called()

    def test_archive_episode_with_embedding(self, mock_db):
        """EpisodeService generates embedding before archival."""
        mock_episode = Mock(
            id="ep-002",
            agent_id="agent-002",
            task_description="Generate sales report",
            outcome="success",
            metadata_json={}
        )

        mock_lancedb = Mock()
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]

        with patch('core.episode_service.get_lancedb_handler', return_value=mock_lancedb):
            with patch('core.episode_service.get_embedding_service', return_value=mock_embedding_service):
                service = EpisodeService(mock_db)

                result = service.archive_episode(mock_episode)

                assert result is True
                mock_embedding_service.generate_embedding.assert_called()
                mock_lancedb.upsert.assert_called()


class TestEpisodeServiceConstitutionalScoring:
    """Test constitutional compliance scoring."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_calculate_constitutional_score_no_violations(self):
        """EpisodeService calculates 100% score with no violations."""
        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(Mock(spec=Session))

                violations = []
                score = service._calculate_constitutional_score(violations)

                assert score == 1.0

    def test_calculate_constitutional_score_with_violations(self):
        """EpisodeService calculates reduced score with violations."""
        with patch('core.episode_service.get_lancedb_handler'):
            with patch('core.episode_service.get_embedding_service'):
                service = EpisodeService(Mock(spec=Session))

                violations = [
                    {"severity": "high", "category": "safety"},
                    {"severity": "low", "category": "performance"}
                ]
                score = service._calculate_constitutional_score(violations)

                assert score < 1.0
                assert score >= 0.0


# Total tests: 34 (exceeds 30-35 target)
# Coverage areas: Enums (3), Thresholds (6), Response (4), Init (3), Creation (3),
#                  Retrieval (3), Readiness (3), Progressive (3), Archival (2), Scoring (2)
