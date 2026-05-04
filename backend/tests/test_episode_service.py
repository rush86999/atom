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
        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(mock_db)
                assert service.db is mock_db

    def test_episode_service_init_creates_lancedb_handler(self, mock_db):
        """EpisodeService lazy-loads LanceDB handler via _get_lancedb()."""
        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(mock_db)
                # LanceDB is lazy-loaded, so it's None initially
                assert service.lancedb is None
                # _get_lancedb() method exists for lazy initialization
                assert hasattr(service, '_get_lancedb')

    def test_episode_service_init_creates_embedding_service(self, mock_db):
        """EpisodeService lazy-loads embedding service via property."""
        with patch('core.lancedb_service.get_lancedb_handler'):
            # Mock the EmbeddingService constructor to avoid tenant_api_key error
            mock_embedding_instance = Mock()
            mock_embedding_instance.get_embedding_dimension.return_value = 384

            # Patch the actual class constructor
            with patch('core.episode_service.EmbeddingService', return_value=mock_embedding_instance):
                service = EpisodeService(mock_db)
                # embedding_service is a property that lazy-loads
                # Access it to trigger initialization
                embedding = service.embedding_service
                assert embedding is not None


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

    @pytest.mark.asyncio
    async def test_create_episode_from_execution(self, mock_db):
        """EpisodeService can create episode from agent execution."""
        # Mock agent registry
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "agent-001"
        mock_agent.status = AgentStatus.STUDENT
        mock_agent.confidence_score = 0.75
        mock_agent.tenant_id = "tenant-001"

        # Mock agent execution
        mock_execution = Mock(spec=AgentExecution)
        mock_execution.id = "exec-001"
        mock_execution.agent_id = "agent-001"
        mock_execution.tenant_id = "tenant-001"
        mock_execution.human_intervention_count = 0
        mock_execution.started_at = datetime.now(timezone.utc)
        mock_execution.completed_at = datetime.now(timezone.utc)
        mock_execution.metadata_json = {}

        # Mock query chain - production queries AgentExecution, AgentRegistry, then AgentReasoningStep
        mock_exec_query = Mock()
        mock_exec_query.filter.return_value.first.return_value = mock_execution

        mock_agent_query = Mock()
        mock_agent_query.filter.return_value.first.return_value = mock_agent

        # Mock reasoning steps query (for step efficiency calculation)
        mock_reasoning_query = Mock()
        mock_reasoning_query.filter.return_value.all.return_value = []  # No reasoning steps

        mock_db.query.side_effect = [mock_exec_query, mock_agent_query, mock_reasoning_query]

        # Mock episode creation
        mock_episode = Mock(spec=AgentEpisode)
        mock_episode.id = "ep-001"
        mock_episode.agent_id = "agent-001"
        mock_db.refresh.return_value = mock_episode

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                with patch.object(EpisodeService, '_extract_canvas_metadata', return_value={}):
                    service = EpisodeService(mock_db)

                    # Create episode using actual production method
                    episode = await service.create_episode_from_execution(
                        execution_id="exec-001",
                        task_description="Test task",
                        outcome="success",
                        success=True,
                        constitutional_violations=None,
                        metadata={}
                    )

                    assert episode.agent_id == "agent-001"
                    mock_db.add.assert_called()
                    mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_create_episode_with_metadata(self, mock_db):
        """EpisodeService creates episode with custom metadata."""
        # Mock agent registry
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "agent-002"
        mock_agent.status = AgentStatus.INTERN
        mock_agent.confidence_score = 0.80
        mock_agent.tenant_id = "tenant-001"

        # Mock agent execution
        mock_execution = Mock(spec=AgentExecution)
        mock_execution.id = "exec-002"
        mock_execution.agent_id = "agent-002"
        mock_execution.tenant_id = "tenant-001"
        mock_execution.human_intervention_count = 0
        mock_execution.started_at = datetime.now(timezone.utc)
        mock_execution.completed_at = datetime.now(timezone.utc)

        metadata = {
            "canvas_type": "chart",
            "presentation_summary": "Test summary",
            "visual_elements": ["chart1", "chart2"]
        }

        # Mock query chain - production queries AgentExecution, AgentRegistry, then AgentReasoningStep
        mock_exec_query = Mock()
        mock_exec_query.filter.return_value.first.return_value = mock_execution

        mock_agent_query = Mock()
        mock_agent_query.filter.return_value.first.return_value = mock_agent

        # Mock reasoning steps query (for step efficiency calculation)
        mock_reasoning_query = Mock()
        mock_reasoning_query.filter.return_value.all.return_value = []  # No reasoning steps

        mock_db.query.side_effect = [mock_exec_query, mock_agent_query, mock_reasoning_query]

        # Mock episode
        mock_episode = Mock(spec=AgentEpisode)
        mock_episode.id = "ep-002"
        mock_episode.agent_id = "agent-002"
        mock_episode.metadata_json = metadata
        mock_db.refresh.return_value = mock_episode

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                with patch.object(EpisodeService, '_extract_canvas_metadata', return_value=metadata):
                    service = EpisodeService(mock_db)

                    episode = await service.create_episode_from_execution(
                        execution_id="exec-002",
                        task_description="Create chart",
                        outcome="success",
                        success=True,
                        constitutional_violations=None,
                        metadata={}
                    )

                    # Metadata should be merged with canvas metadata
                    assert "canvas_type" in episode.metadata_json

    @pytest.mark.asyncio
    async def test_create_episode_validates_required_fields(self, mock_db):
        """EpisodeService validates required fields for episode creation."""
        # Mock query to return None (execution not found)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(mock_db)

                # Missing execution should raise ValueError
                with pytest.raises(ValueError, match="Execution .* not found"):
                    await service.create_episode_from_execution(
                        execution_id="nonexistent-exec",
                        task_description="Test",
                        outcome="success",
                        success=True,
                        constitutional_violations=None,
                        metadata={}
                    )


class TestEpisodeServiceRetrieval:
    """Test episode retrieval by agent."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_get_agent_episodes(self, mock_db):
        """EpisodeService can retrieve all episodes for an agent."""
        mock_episodes = [
            Mock(id="ep-001", agent_id="agent-001", tenant_id="tenant-001"),
            Mock(id="ep-002", agent_id="agent-001", tenant_id="tenant-001")
        ]

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_episodes
        mock_db.query.return_value = mock_query

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(mock_db)

                episodes = service.get_agent_episodes(
                    agent_id="agent-001",
                    tenant_id="tenant-001",
                    limit=10
                )
                assert len(episodes) == 2

    def test_get_agent_episodes_with_outcome_filter(self, mock_db):
        """EpisodeService can filter episodes by outcome."""
        mock_episodes = [
            Mock(id="ep-001", agent_id="agent-001", outcome="success"),
            Mock(id="ep-002", agent_id="agent-001", outcome="success")
        ]

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_episodes
        mock_db.query.return_value = mock_query

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(mock_db)

                episodes = service.get_agent_episodes(
                    agent_id="agent-001",
                    tenant_id="tenant-001",
                    limit=10,
                    outcome_filter="success"
                )
                assert len(episodes) == 2

    def test_get_agent_episodes_empty_result(self, mock_db):
        """EpisodeService returns empty list when no episodes found."""
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(mock_db)

                episodes = service.get_agent_episodes(
                    agent_id="nonexistent-agent",
                    tenant_id="tenant-001",
                    limit=10
                )
                assert len(episodes) == 0


class TestEpisodeServiceGraduationReadiness:
    """Test graduation readiness calculation."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_get_graduation_readiness_for_student(self, mock_db):
        """EpisodeService calculates readiness for STUDENT agent."""
        # Mock agent registry
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "agent-001"
        mock_agent.status = AgentStatus.STUDENT
        mock_agent.tenant_id = "tenant-001"

        # Mock episodes with step_efficiency attribute
        mock_episodes = [
            Mock(
                success=True,
                constitutional_score=0.80,
                human_intervention_count=0,
                confidence_score=0.60,
                step_efficiency=1.0,
                started_at=datetime.now(timezone.utc) - timedelta(days=1),
                outcome="success",
                proposal_id=None,
                supervision_decision=None,
                execution_followed_proposal=None,
                supervisor_type=None
            )
            for _ in range(10)
        ]

        # Mock query chain
        mock_agent_query = Mock()
        mock_agent_query.filter.return_value.first.return_value = mock_agent
        mock_episode_query = Mock()
        mock_episode_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_episodes
        mock_db.query.side_effect = [mock_agent_query, mock_episode_query]

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                with patch.object(EpisodeService, 'calculate_skill_diversity_metrics', return_value={"skill_diversity_score": 0.5}):
                    with patch.object(EpisodeService, 'calculate_proposal_quality_metrics', return_value={"proposal_quality_score": 0.8}):
                        service = EpisodeService(mock_db)

                        readiness = service.get_graduation_readiness(
                            agent_id="agent-001",
                            tenant_id="tenant-001",
                            episode_count=10
                        )

                        assert readiness.agent_id == "agent-001"
                        assert readiness.current_level == AgentStatus.STUDENT.value  # Use .value for enum
                        assert readiness.episodes_analyzed == 10

    def test_get_graduation_readiness_threshold_check(self, mock_db):
        """EpisodeService checks if readiness meets thresholds."""
        # Mock agent registry
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "agent-002"
        mock_agent.status = AgentStatus.INTERN
        mock_agent.tenant_id = "tenant-001"

        # Create episodes with high scores
        mock_episodes = [
            Mock(
                success=True,
                constitutional_score=0.90,
                human_intervention_count=0,
                confidence_score=0.80,
                step_efficiency=1.0,
                started_at=datetime.now(timezone.utc) - timedelta(days=1),
                outcome="success",
                proposal_id=None,
                supervision_decision=None,
                execution_followed_proposal=None,
                supervisor_type=None
            )
            for _ in range(25)
        ]

        # Mock query chain
        mock_agent_query = Mock()
        mock_agent_query.filter.return_value.first.return_value = mock_agent
        mock_episode_query = Mock()
        mock_episode_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_episodes
        mock_db.query.side_effect = [mock_agent_query, mock_episode_query]

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                with patch.object(EpisodeService, 'calculate_skill_diversity_metrics', return_value={"skill_diversity_score": 0.7}):
                    with patch.object(EpisodeService, 'calculate_proposal_quality_metrics', return_value={"proposal_quality_score": 0.9}):
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
        # Mock agent registry
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "agent-003"
        mock_agent.status = AgentStatus.STUDENT
        mock_agent.tenant_id = "tenant-001"
        mock_agent.confidence_score = 0.50

        # Mock query chain
        mock_agent_query = Mock()
        mock_agent_query.filter.return_value.first.return_value = mock_agent
        mock_episode_query = Mock()
        mock_episode_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.side_effect = [mock_agent_query, mock_episode_query]

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
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

    @pytest.mark.asyncio
    async def test_recall_episodes_with_detail_summary(self, mock_db):
        """EpisodeService retrieves episodes at SUMMARY detail level."""
        # Mock agent verification and episode query
        mock_check_result = Mock()
        mock_check_result.scalar_one_or_none.return_value = True

        mock_episode_result = Mock()
        mock_episode_result.fetchall.return_value = []  # Empty list for no episodes

        # Return different mocks for different calls
        mock_db.execute = AsyncMock(side_effect=[mock_check_result, mock_episode_result])

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(mock_db)

                episodes = await service.recall_episodes_with_detail(
                    agent_id="agent-001",
                    tenant_id="tenant-001",
                    detail_level=DetailLevel.SUMMARY,
                    limit=10
                )

                # Should execute query (may return empty list)
                assert isinstance(episodes, list)
                assert len(episodes) == 0

    @pytest.mark.asyncio
    async def test_recall_episodes_with_detail_standard(self, mock_db):
        """EpisodeService retrieves episodes at STANDARD detail level."""
        # Mock agent verification and episode query
        mock_check_result = Mock()
        mock_check_result.scalar_one_or_none.return_value = True

        mock_episode_result = Mock()
        mock_episode_result.fetchall.return_value = []

        # Return different mocks for different calls
        mock_db.execute = AsyncMock(side_effect=[mock_check_result, mock_episode_result])

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(mock_db)

                episodes = await service.recall_episodes_with_detail(
                    agent_id="agent-002",
                    tenant_id="tenant-001",
                    detail_level=DetailLevel.STANDARD,
                    limit=20
                )

                # Should execute query with standard template
                assert mock_db.execute.call_count == 2  # check + episode query
                assert isinstance(episodes, list)

    @pytest.mark.asyncio
    async def test_recall_episodes_with_detail_full(self, mock_db):
        """EpisodeService retrieves episodes at FULL detail level."""
        # Mock agent verification and episode query
        mock_check_result = Mock()
        mock_check_result.scalar_one_or_none.return_value = True

        mock_episode_result = Mock()
        mock_episode_result.fetchall.return_value = []

        # Return different mocks for different calls
        mock_db.execute = AsyncMock(side_effect=[mock_check_result, mock_episode_result])

        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(mock_db)

                episodes = await service.recall_episodes_with_detail(
                    agent_id="agent-003",
                    tenant_id="tenant-001",
                    detail_level=DetailLevel.FULL,
                    limit=5
                )

                # Should execute query with full template (includes audit trail)
                assert mock_db.execute.call_count == 2  # check + episode query
                assert isinstance(episodes, list)


class TestEpisodeServiceArchival:
    """Test episode archival to cold storage."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.mark.asyncio
    async def test_archive_episode_to_cold_storage(self, mock_db):
        """EpisodeService archives episode to LanceDB cold storage."""
        mock_episode = Mock(
            spec=AgentEpisode,
            id="ep-001",
            agent_id="agent-001",
            tenant_id="tenant-001",
            task_description="Test task",
            outcome="success",
            metadata_json={}
        )

        # Mock query to return episode
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_episode
        mock_db.query.return_value = mock_query

        # Mock LanceDB service
        mock_lancedb = Mock()
        mock_lancedb.add_episode.return_value = True

        # Mock embedding service
        mock_embedding = Mock()
        mock_embedding.get_embedding_dimension.return_value = 384
        mock_embedding.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

        with patch('core.episode_service.LanceDBService', return_value=mock_lancedb):
            service = EpisodeService(mock_db, embedding_service=mock_embedding)

            result = await service.archive_episode_to_cold_storage("ep-001")

            assert result is True
            mock_lancedb.add_episode.assert_called()

    @pytest.mark.asyncio
    async def test_archive_episode_with_embedding(self, mock_db):
        """EpisodeService generates embedding before archival."""
        mock_episode = Mock(
            spec=AgentEpisode,
            id="ep-002",
            agent_id="agent-002",
            tenant_id="tenant-001",
            task_description="Generate sales report",
            outcome="success",
            metadata_json={}
        )

        # Mock query to return episode
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_episode
        mock_db.query.return_value = mock_query

        # Mock LanceDB service
        mock_lancedb = Mock()
        mock_lancedb.add_episode.return_value = True

        # Mock embedding service
        mock_embedding = Mock()
        mock_embedding.get_embedding_dimension.return_value = 384
        mock_embedding.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])

        with patch('core.episode_service.LanceDBService', return_value=mock_lancedb):
            service = EpisodeService(mock_db, embedding_service=mock_embedding)

            result = await service.archive_episode_to_cold_storage("ep-002")

            assert result is True
            mock_embedding.generate_embedding.assert_called_once()
            mock_lancedb.add_episode.assert_called()


class TestEpisodeServiceConstitutionalScoring:
    """Test constitutional compliance scoring."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_calculate_constitutional_score_no_violations(self):
        """EpisodeService calculates 100% score with no violations."""
        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(Mock(spec=Session))

                violations = []
                score = service._calculate_constitutional_score(violations)

                assert score == 1.0

    def test_calculate_constitutional_score_with_violations(self):
        """EpisodeService calculates reduced score with violations."""
        with patch('core.lancedb_service.get_lancedb_handler'):
            with patch('core.embedding_service.EmbeddingService'):
                service = EpisodeService(Mock(spec=Session))

                violations = [
                    {"severity": "high", "category": "safety"},
                    {"severity": "low", "category": "performance"}
                ]
                score = service._calculate_constitutional_score(violations)

                assert score < 1.0
                assert score >= 0.0


# Total tests: 33 (meets 30-35 target)
# Coverage areas: Enums (3), Thresholds (6), Response (4), Init (3), Creation (3),
#                  Retrieval (3), Readiness (3), Progressive (3), Archival (2), Scoring (2)
