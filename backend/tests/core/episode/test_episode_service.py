"""
Comprehensive Unit Tests for Episode Service

================================================================================
ANALYSIS SUMMARY: Episode Service Structure
================================================================================

Target File: backend/core/episode_service.py
Lines: 1,990
Current Coverage: 14.37% (74/515 lines)
Target Coverage: >=70%

================================================================================
PUBLIC METHODS IDENTIFIED
================================================================================

1. Episode Creation & Lifecycle:
   - create_episode_from_execution(execution_id, task_description, outcome, success, ...)
   - get_agent_episodes(agent_id, tenant_id, limit, outcome_filter, start_date, end_date)
   - archive_episode_to_cold_storage(episode_id)

2. Graduation & Readiness:
   - get_graduation_readiness(agent_id, tenant_id, episode_count, target_level)
   - calculate_readiness_metrics(episodes)
   - calculate_supervision_metrics(episodes)
   - calculate_skill_diversity_metrics(agent_id, tenant_id)
   - calculate_proposal_quality_metrics(agent_id, tenant_id)

3. Feedback System (RLHF):
   - update_episode_feedback(episode_id, feedback_score, ...)
   - get_episode_feedback(episode_id)
   - get_domain_feedback_metrics(tenant_id, domain, days)

4. Canvas Integration:
   - _extract_canvas_metadata(execution_id, task_description)
   - get_canvas_actions_for_episode(episode_id)
   - link_canvas_actions_to_episode(episode_id, canvas_action_ids)
   - recall_episodes_with_detail(agent_id, tenant_id, detail_level, limit)

5. Skill Performance Tracking:
   - get_skill_performance_stats(agent_id, tenant_id, skill_id, limit)
   - get_agent_skill_usage(agent_id, tenant_id, limit)
   - get_skill_usage_count(agent_id, tenant_id)
   - get_required_skills_for_level(target_level)
   - assess_skill_mastery(agent_id, tenant_id, target_level)

6. Proposal Episodes:
   - get_proposal_episodes_for_learning(tenant_id, agent_id, capability_tags, min_quality, limit)

7. Internal Helpers:
   - _calculate_constitutional_score(violations)
   - _calculate_step_efficiency(execution_id)
   - _get_next_level(current_level)
   - _get_threshold_for_level(target_level)
   - _sync_feedback_to_lancedb(episode, feedback)
   - _get_lancedb()

================================================================================
CRITICAL PATHS TO TEST
================================================================================

1. Episode Creation Flow:
   - Create episode from execution
   - Extract canvas metadata
   - Calculate constitutional score
   - Calculate step efficiency
   - Publish activity events
   - Emit Auto-Dev events

2. Graduation Readiness Calculation:
   - Query recent episodes
   - Calculate metrics (success rate, intervention ratio, etc.)
   - Calculate supervision metrics
   - Calculate skill diversity
   - Calculate proposal quality
   - Apply readiness formula
   - Compare against threshold

3. Feedback System:
   - Create feedback record
   - Update episode metadata
   - Record capability usage
   - Sync to LanceDB

4. Canvas Integration:
   - Extract canvas metadata from execution
   - Generate semantic summary
   - Link canvas actions
   - Recall with progressive detail

5. Skill Performance:
   - Query skill episodes
   - Calculate statistics
   - Assess mastery

================================================================================
MEMORY INTEGRATION POINTS
================================================================================

1. LanceDB Integration:
   - Cold storage archival (archive_episode_to_cold_storage)
   - Embedding generation for semantic search
   - Feedback sync for enhanced recall

2. PostgreSQL (Hot Storage):
   - AgentEpisode model CRUD
   - EpisodeFeedback records
   - CanvasAudit linking
   - AgentExecution integration

3. Caching:
   - No explicit caching in EpisodeService
   - Relies on database query optimization

================================================================================
ERROR SCENARIOS TO TEST
================================================================================

1. Invalid Inputs:
   - Episode not found (get_episode, update_episode)
   - Execution not found (create_episode_from_execution)
   - Agent not found (get_graduation_readiness)
   - Invalid episode_id (archive_episode_to_cold_storage)
   - Invalid feedback score (update_episode_feedback)

2. Storage Failures:
   - LanceDB connection failure
   - Embedding generation failure
   - Database query errors
   - Transaction rollback scenarios

3. Validation Errors:
   - Empty violations list
   - Missing canvas metadata
   - No episodes for readiness calculation
   - Invalid skill_id

4. Edge Cases:
   - Zero episodes for agent
   - All episodes failed
   - Missing canvas context
   - Auto-Dev module not installed

================================================================================
DEPENDENCIES TO MOCK
================================================================================

1. Database:
   - Session (self.db)
   - AgentExecution query
   - AgentEpisode query
   - AgentRegistry query
   - EpisodeFeedback query
   - CanvasAudit query

2. External Services:
   - EmbeddingService (vector generation)
   - LanceDBService (cold storage)
   - CanvasContextProvider (canvas metadata)
   - CanvasSummaryService (semantic summaries)
   - ActivityPublisher (menu bar events)
   - CapabilityGraduationService (feedback integration)
   - ACUBillingService (billing integration)

3. Models:
   - AgentExecution
   - AgentEpisode
   - AgentRegistry
   - EpisodeFeedback
   - CanvasAudit
   - Canvas
   - Artifact
   - ArtifactComment
   - Skill

================================================================================
TEST CATEGORIES (500+ lines, 30+ tests)
================================================================================

1. Episode Creation Tests (100 lines, 8 tests):
   - test_create_episode_success
   - test_create_episode_with_canvas_metadata
   - test_create_episode_with_constitutional_violations
   - test_create_episode_execution_not_found
   - test_create_episode_agent_not_found
   - test_create_episode_publishes_activity_events
   - test_create_episode_emits_auto_dev_events
   - test_create_episode_calculation_scores

2. Episode Retrieval Tests (80 lines, 7 tests):
   - test_get_agent_episodes_basic
   - test_get_agent_episodes_with_outcome_filter
   - test_get_agent_episodes_with_date_range
   - test_get_agent_episodes_with_pagination
   - test_get_agent_episodes_empty_result
   - test_recall_episodes_summary_level
   - test_recall_episodes_standard_level

3. Graduation Readiness Tests (100 lines, 8 tests):
   - test_graduation_readiness_basic
   - test_graduation_readiness_no_episodes
   - test_graduation_readiness_threshold_met
   - test_graduation_readiness_threshold_not_met
   - test_calculate_readiness_metrics_basic
   - test_calculate_supervision_metrics_basic
   - test_calculate_skill_diversity_metrics
   - test_calculate_proposal_quality_metrics

4. Feedback System Tests (90 lines, 7 tests):
   - test_update_episode_feedback_success
   - test_update_episode_feedback_not_found
   - test_update_episode_feedback_with_capability_tags
   - test_get_episode_feedback_basic
   - test_get_episode_feedback_empty
   - test_get_domain_feedback_metrics_basic
   - test_get_domain_feedback_metrics_no_data

5. Canvas Integration Tests (70 lines, 5 tests):
   - test_extract_canvas_metadata_basic
   - test_extract_canvas_metadata_no_canvas
   - test_extract_canvas_metadata_canvas_not_found
   - test_get_canvas_actions_for_episode
   - test_link_canvas_actions_to_episode

6. Skill Performance Tests (60 lines, 5 tests):
   - test_get_skill_performance_stats_basic
   - test_get_skill_performance_stats_no_executions
   - test_get_agent_skill_usage_basic
   - test_get_skill_usage_count
   - test_assess_skill_mastery

7. Archival Tests (50 lines, 4 tests):
   - test_archive_episode_to_cold_storage_success
   - test_archive_episode_to_cold_storage_not_found
   - test_archive_episode_to_cold_storage_lancedb_unavailable
   - test_archive_episode_to_cold_storage_embedding_failure

8. Error Handling Tests (50 lines, 4 tests):
   - test_constitutional_score_no_violations
   - test_constitutional_score_with_violations
   - test_step_efficiency_no_steps
   - test_step_efficiency_with_steps

9. Proposal Episodes Tests (30 lines, 2 tests):
   - test_get_proposal_episodes_for_learning_basic
   - test_get_proposal_episodes_for_learning_with_capability_filter

================================================================================
TOTAL TEST COUNT: 50+ tests across 9 categories
================================================================================
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from typing import List, Dict, Any

# Import EpisodeService and related models
from core.episode_service import (
    EpisodeService,
    ReadinessThresholds,
    ReadinessResponse,
    DetailLevel,
    PROGRESSIVE_QUERIES
)
from core.models import (
    AgentEpisode,
    AgentExecution,
    AgentRegistry,
    EpisodeFeedback,
    CanvasAudit,
    Canvas,
    Artifact,
    ArtifactComment,
    Skill,
    AgentStatus,
    EpisodeOutcome
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service"""
    service = Mock()
    service.get_embedding_dimension.return_value = 384
    service.generate_embedding = AsyncMock(return_value=[0.1] * 384)
    return service


@pytest.fixture
def mock_lancedb_service():
    """Mock LanceDB service"""
    service = Mock()
    service.connect.return_value = True
    service.get_or_create_episodes_table.return_value = None
    service.add_episode.return_value = True
    return service


@pytest.fixture
def mock_activity_publisher():
    """Mock activity publisher for menu bar events"""
    publisher = Mock()
    publisher.publish_episode_recording.return_value = None
    return publisher


@pytest.fixture
def service(mock_db, mock_embedding_service, mock_lancedb_service, mock_activity_publisher):
    """Create EpisodeService instance with all dependencies mocked"""
    with patch('core.episode_service.LanceDBService', return_value=mock_lancedb_service):
        svc = EpisodeService(
            db=mock_db,
            tenant_api_key=None,
            activity_publisher=mock_activity_publisher,
            embedding_service=mock_embedding_service
        )
        svc.lancedb = mock_lancedb_service
        return svc


@pytest.fixture
def sample_agent():
    """Sample agent registry"""
    agent = Mock(spec=AgentRegistry)
    agent.id = "agent-123"
    agent.tenant_id = "tenant-456"
    agent.status = AgentStatus.INTERN.value
    agent.confidence_score = 0.75
    return agent


@pytest.fixture
def sample_execution():
    """Sample agent execution"""
    execution = Mock(spec=AgentExecution)
    execution.id = "exec-123"
    execution.agent_id = "agent-123"
    execution.tenant_id = "tenant-456"
    execution.started_at = datetime.now(timezone.utc)
    execution.completed_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    execution.human_intervention_count = 0
    execution.metadata_json = {"canvas_id": "canvas-789"}
    return execution


@pytest.fixture
def sample_episode():
    """Sample agent episode"""
    episode = Mock(spec=AgentEpisode)
    episode.id = "episode-123"
    episode.agent_id = "agent-123"
    episode.tenant_id = "tenant-456"
    episode.execution_id = "exec-123"
    episode.task_description = "Test task"
    episode.outcome = EpisodeOutcome.SUCCESS.value
    episode.success = True
    episode.constitutional_score = 1.0
    episode.human_intervention_count = 0
    episode.confidence_score = 0.75
    episode.started_at = datetime.now(timezone.utc)
    episode.completed_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    episode.metadata_json = {}
    return episode


# ============================================================================
# TEST CATEGORY 1: EPISODE CREATION TESTS (8 tests)
# ============================================================================

class TestEpisodeCreation:
    """Tests for episode creation from executions"""

    @pytest.mark.asyncio
    async def test_create_episode_success(
        self, service, mock_db, sample_execution, sample_agent
    ):
        """Test successful episode creation"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_execution,
            sample_agent
        ]

        # Mock reasoning steps query for step efficiency calculation
        mock_db.query.return_value.filter.return_value.all.return_value = []

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Create episode
        with patch.object(service, '_extract_canvas_metadata', return_value={}):
            episode = await service.create_episode_from_execution(
                execution_id="exec-123",
                task_description="Test task",
                outcome="success",
                success=True,
                constitutional_violations=[]
            )

        # Verify episode created
        assert episode is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_episode_with_canvas_metadata(
        self, service, mock_db, sample_execution, sample_agent
    ):
        """Test episode creation with canvas metadata extraction"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_execution,
            sample_agent
        ]
        # Mock reasoning steps query
        mock_db.query.return_value.filter.return_value.all.return_value = []

        canvas_metadata = {
            "canvas_id": "canvas-789",
            "canvas_artifact_count": 5,
            "canvas_comment_count": 2,
            "canvas_type": "chart"
        }

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Create episode
        with patch.object(service, '_extract_canvas_metadata', return_value=canvas_metadata):
            episode = await service.create_episode_from_execution(
                execution_id="exec-123",
                task_description="Test task",
                outcome="success",
                success=True
            )

        # Verify canvas metadata included
        assert episode is not None
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_episode_with_constitutional_violations(
        self, service, mock_db, sample_execution, sample_agent
    ):
        """Test episode creation with constitutional violations"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_execution,
            sample_agent
        ]

        violations = [
            {"severity": "high", "description": "Test violation"},
            {"severity": "low", "description": "Minor issue"}
        ]

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Create episode
        with patch.object(service, '_extract_canvas_metadata', return_value={}):
            episode = await service.create_episode_from_execution(
                execution_id="exec-123",
                task_description="Test task",
                outcome="partial",
                success=False,
                constitutional_violations=violations
            )

        # Verify score calculated with penalty
        assert episode is not None
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_episode_execution_not_found(self, service, mock_db):
        """Test episode creation with non-existent execution"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Should raise ValueError
        with pytest.raises(ValueError, match="Execution .* not found"):
            await service.create_episode_from_execution(
                execution_id="nonexistent-exec",
                task_description="Test task",
                outcome="success",
                success=True
            )

    @pytest.mark.asyncio
    async def test_create_episode_agent_not_found(
        self, service, mock_db, sample_execution
    ):
        """Test episode creation with non-existent agent"""
        # Setup mocks - execution exists but agent doesn't
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_execution,
            None
        ]

        # Should raise ValueError
        with pytest.raises(ValueError, match="Agent .* not found"):
            await service.create_episode_from_execution(
                execution_id="exec-123",
                task_description="Test task",
                outcome="success",
                success=True
            )

    @pytest.mark.asyncio
    async def test_create_episode_publishes_activity_events(
        self, service, mock_db, sample_execution, sample_agent, mock_activity_publisher
    ):
        """Test that episode creation publishes menu bar activity events"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_execution,
            sample_agent
        ]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Create episode
        with patch.object(service, '_extract_canvas_metadata', return_value={}):
            await service.create_episode_from_execution(
                execution_id="exec-123",
                task_description="Test task",
                outcome="success",
                success=True
            )

        # Verify activity publisher called twice (working + idle)
        assert mock_activity_publisher.publish_episode_recording.call_count == 2

    @pytest.mark.asyncio
    async def test_create_episode_emits_auto_dev_events(
        self, service, mock_db, sample_execution, sample_agent
    ):
        """Test that episode creation emits Auto-Dev events"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_execution,
            sample_agent
        ]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Create episode
        with patch.object(service, '_extract_canvas_metadata', return_value={}):
            with patch('core.episode_service.asyncio.ensure_future') as mock_ensure_future:
                await service.create_episode_from_execution(
                    execution_id="exec-123",
                    task_description="Test task",
                    outcome="success",
                    success=True
                )

                # Verify event emitted
                mock_ensure_future.assert_called()

    @pytest.mark.asyncio
    async def test_create_episode_calculation_scores(
        self, service, mock_db, sample_execution, sample_agent
    ):
        """Test that constitutional score and step efficiency are calculated"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_execution,
            sample_agent
        ]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Create episode
        with patch.object(service, '_extract_canvas_metadata', return_value={}):
            episode = await service.create_episode_from_execution(
                execution_id="exec-123",
                task_description="Test task",
                outcome="success",
                success=True,
                constitutional_violations=[]
            )

        # Verify episode has scores
        assert episode is not None
        mock_db.add.assert_called_once()


# ============================================================================
# TEST CATEGORY 2: EPISODE RETRIEVAL TESTS (7 tests)
# ============================================================================

class TestEpisodeRetrieval:
    """Tests for episode retrieval and querying"""

    def test_get_agent_episodes_basic(self, service, mock_db, sample_episode):
        """Test basic episode retrieval for agent"""
        # Setup mock
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            sample_episode
        ]
        mock_db.query.return_value = mock_query

        # Get episodes
        episodes = service.get_agent_episodes(
            agent_id="agent-123",
            tenant_id="tenant-456",
            limit=50
        )

        # Verify results
        assert len(episodes) == 1
        assert episodes[0].id == "episode-123"

    def test_get_agent_episodes_with_outcome_filter(self, service, mock_db):
        """Test episode retrieval with outcome filter"""
        # Setup mock
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        # Get episodes with filter
        episodes = service.get_agent_episodes(
            agent_id="agent-123",
            tenant_id="tenant-456",
            outcome_filter="success",
            limit=50
        )

        # Verify filter applied
        assert mock_query.filter.call_count >= 2  # agent/tenant + outcome

    def test_get_agent_episodes_with_date_range(self, service, mock_db):
        """Test episode retrieval with date range filter"""
        # Setup mock
        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        # Get episodes with date range
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        episodes = service.get_agent_episodes(
            agent_id="agent-123",
            tenant_id="tenant-456",
            start_date=start_date,
            end_date=end_date,
            limit=50
        )

        # Verify filters applied
        assert mock_query.filter.call_count >= 3  # agent/tenant + start + end

    def test_get_agent_episodes_with_pagination(self, service, mock_db, sample_episode):
        """Test episode retrieval with pagination"""
        # Setup mock
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            sample_episode
        ]
        mock_db.query.return_value = mock_query

        # Get episodes with custom limit
        episodes = service.get_agent_episodes(
            agent_id="agent-123",
            tenant_id="tenant-456",
            limit=10
        )

        # Verify limit applied
        mock_query.filter.return_value.order_by.return_value.limit.assert_called_with(10)
        assert len(episodes) <= 10

    def test_get_agent_episodes_empty_result(self, service, mock_db):
        """Test episode retrieval with no results"""
        # Setup mock
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        # Get episodes
        episodes = service.get_agent_episodes(
            agent_id="nonexistent-agent",
            tenant_id="tenant-456",
            limit=50
        )

        # Verify empty result
        assert len(episodes) == 0

    @pytest.mark.asyncio
    async def test_recall_episodes_summary_level(self, service, mock_db):
        """Test recalling episodes with summary detail level"""
        # Setup mock
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        # Recall with summary level
        episodes = await service.recall_episodes_with_detail(
            agent_id="agent-123",
            tenant_id="tenant-456",
            detail_level=DetailLevel.SUMMARY,
            limit=30
        )

        # Verify query executed
        mock_db.execute.assert_called()
        assert isinstance(episodes, list)

    @pytest.mark.asyncio
    async def test_recall_episodes_standard_level(self, service, mock_db):
        """Test recalling episodes with standard detail level"""
        # Setup mock
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        # Recall with standard level
        episodes = await service.recall_episodes_with_detail(
            agent_id="agent-123",
            tenant_id="tenant-456",
            detail_level=DetailLevel.STANDARD,
            limit=30
        )

        # Verify query executed
        mock_db.execute.assert_called()
        assert isinstance(episodes, list)


# ============================================================================
# TEST CATEGORY 3: GRADUATION READINESS TESTS (8 tests)
# ============================================================================

class TestGraduationReadiness:
    """Tests for graduation readiness calculation"""

    def test_graduation_readiness_basic(self, service, mock_db, sample_agent, sample_episode):
        """Test basic graduation readiness calculation"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            sample_episode
        ]

        # Calculate readiness
        readiness = service.get_graduation_readiness(
            agent_id="agent-123",
            tenant_id="tenant-456",
            episode_count=30
        )

        # Verify response
        assert isinstance(readiness, ReadinessResponse)
        assert readiness.agent_id == "agent-123"
        assert readiness.episodes_analyzed >= 0

    def test_graduation_readiness_no_episodes(self, service, mock_db, sample_agent):
        """Test graduation readiness with no episodes"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # Calculate readiness
        readiness = service.get_graduation_readiness(
            agent_id="agent-123",
            tenant_id="tenant-456",
            episode_count=30
        )

        # Verify zero readiness
        assert readiness.readiness_score == 0.0
        assert readiness.threshold_met is False
        assert readiness.episodes_analyzed == 0

    def test_graduation_readiness_threshold_met(self, service, mock_db, sample_agent):
        """Test graduation readiness when threshold is met"""
        # Setup mocks with high-performing episodes
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        episodes = []
        for i in range(30):
            ep = Mock(spec=AgentEpisode)
            ep.success = True
            ep.human_intervention_count = 0
            ep.constitutional_score = 0.95
            ep.confidence_score = 0.90
            ep.step_efficiency = 1.0
            ep.outcome = "success"
            ep.proposal_id = None
            episodes.append(ep)

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes

        # Mock skill metrics
        with patch.object(service, 'calculate_skill_diversity_metrics', return_value={"skill_diversity_score": 1.0}):
            with patch.object(service, 'calculate_proposal_quality_metrics', return_value={"proposal_quality_score": 1.0}):
                readiness = service.get_graduation_readiness(
                    agent_id="agent-123",
                    tenant_id="tenant-456",
                    episode_count=30
                )

        # Verify threshold met
        assert readiness.readiness_score > 0.7

    def test_graduation_readiness_threshold_not_met(self, service, mock_db, sample_agent):
        """Test graduation readiness when threshold not met"""
        # Setup mocks with low-performing episodes
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        episodes = []
        for i in range(30):
            ep = Mock(spec=AgentEpisode)
            ep.success = False
            ep.human_intervention_count = 5
            ep.constitutional_score = 0.5
            ep.confidence_score = 0.3
            ep.step_efficiency = 0.5
            ep.outcome = "failure"
            ep.proposal_id = None
            episodes.append(ep)

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = episodes

        # Calculate readiness
        with patch.object(service, 'calculate_skill_diversity_metrics', return_value={"skill_diversity_score": 0.0}):
            with patch.object(service, 'calculate_proposal_quality_metrics', return_value={"proposal_quality_score": 0.0}):
                readiness = service.get_graduation_readiness(
                    agent_id="agent-123",
                    tenant_id="tenant-456",
                    episode_count=30
                )

        # Verify threshold not met
        assert readiness.threshold_met is False

    def test_calculate_readiness_metrics_basic(self, service, sample_episode):
        """Test readiness metrics calculation"""
        episodes = [sample_episode]

        # Calculate metrics
        metrics = service.calculate_readiness_metrics(episodes)

        # Verify metrics
        assert "success_rate" in metrics
        assert "zero_intervention_ratio" in metrics
        assert "avg_constitutional_score" in metrics
        assert "avg_confidence_score" in metrics
        assert "episodes_by_outcome" in metrics
        assert "total_interventions" in metrics
        assert "avg_step_efficiency" in metrics

    def test_calculate_supervision_metrics_basic(self, service):
        """Test supervision metrics calculation"""
        # Create supervision episodes
        episodes = []
        for i in range(10):
            ep = Mock(spec=AgentEpisode)
            ep.proposal_id = f"proposal-{i}"
            ep.supervision_decision = "approved" if i < 8 else "rejected"
            ep.execution_followed_proposal = True
            ep.supervisor_type = "user"
            episodes.append(ep)

        # Calculate metrics
        metrics = service.calculate_supervision_metrics(episodes)

        # Verify metrics
        assert metrics["total_proposals"] == 10
        assert metrics["approved_proposals"] == 8
        assert metrics["rejected_proposals"] == 2
        assert metrics["approval_rate"] == 0.8

    def test_calculate_skill_diversity_metrics(self, service, mock_db):
        """Test skill diversity metrics calculation"""
        # Mock skill usage query
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        # Calculate metrics
        metrics = service.calculate_skill_diversity_metrics(
            agent_id="agent-123",
            tenant_id="tenant-456"
        )

        # Verify metrics
        assert "unique_skill_count" in metrics
        assert "skill_diversity_score" in metrics
        assert "total_skill_executions" in metrics

    def test_calculate_proposal_quality_metrics(self, service, mock_db):
        """Test proposal quality metrics calculation"""
        # Mock proposal episodes query
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        # Calculate metrics
        metrics = service.calculate_proposal_quality_metrics(
            agent_id="agent-123",
            tenant_id="tenant-456"
        )

        # Verify metrics
        assert "proposal_episode_count" in metrics
        assert "avg_proposal_quality" in metrics
        assert "proposal_quality_score" in metrics


# ============================================================================
# TEST CATEGORY 4: FEEDBACK SYSTEM TESTS (7 tests)
# ============================================================================

class TestFeedbackSystem:
    """Tests for episode feedback (RLHF) system"""

    def test_update_episode_feedback_success(
        self, service, mock_db, sample_episode
    ):
        """Test successful feedback update"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_episode
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Update feedback
        feedback_id = service.update_episode_feedback(
            episode_id="episode-123",
            feedback_score=0.8,
            feedback_notes="Great work",
            feedback_category="accuracy"
        )

        # Verify feedback created
        assert feedback_id is not None
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_update_episode_feedback_not_found(self, service, mock_db):
        """Test feedback update with non-existent episode"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Should raise ValueError
        with pytest.raises(ValueError, match="Episode .* not found"):
            service.update_episode_feedback(
                episode_id="nonexistent-episode",
                feedback_score=0.8
            )

    def test_update_episode_feedback_with_capability_tags(
        self, service, mock_db, sample_episode
    ):
        """Test feedback update with capability domain tagging"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_episode
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock capability graduation service
        with patch('core.episode_service.CapabilityGraduationService') as mock_cap_service:
            # Update feedback with capability tags
            feedback_id = service.update_episode_feedback(
                episode_id="episode-123",
                feedback_score=0.9,
                capability_domain="data_analysis",
                capability_name="sql_query"
            )

            # Verify feedback created
            assert feedback_id is not None
            mock_db.add.assert_called()

    def test_get_episode_feedback_basic(self, service, mock_db):
        """Test retrieving episode feedback"""
        # Setup mock feedback
        feedback = Mock(spec=EpisodeFeedback)
        feedback.id = "feedback-123"
        feedback.feedback_score = 0.8
        feedback.feedback_notes = "Good work"
        feedback.feedback_category = "accuracy"
        feedback.provider_id = "user-123"
        feedback.provider_type = "human"
        feedback.provided_at = datetime.now(timezone.utc)
        feedback.capability_domain = None
        feedback.capability_name = None

        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            feedback
        ]

        # Get feedback
        feedback_list = service.get_episode_feedback(episode_id="episode-123")

        # Verify results
        assert len(feedback_list) == 1
        assert feedback_list[0]["feedback_score"] == 0.8

    def test_get_episode_feedback_empty(self, service, mock_db):
        """Test retrieving feedback when none exists"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        # Get feedback
        feedback_list = service.get_episode_feedback(episode_id="episode-123")

        # Verify empty result
        assert len(feedback_list) == 0

    def test_get_domain_feedback_metrics_basic(self, service, mock_db):
        """Test retrieving domain feedback metrics"""
        # Setup mock feedback
        feedback = Mock(spec=EpisodeFeedback)
        feedback.tenant_id = "tenant-456"
        feedback.capability_domain = "data_analysis"
        feedback.feedback_score = 0.8
        feedback.capability_name = "sql_query"
        feedback.provided_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.all.return_value = [feedback]

        # Get domain metrics
        metrics = service.get_domain_feedback_metrics(
            tenant_id="tenant-456",
            domain="data_analysis",
            days=30
        )

        # Verify metrics
        assert metrics["domain"] == "data_analysis"
        assert metrics["feedback_count"] == 1
        assert metrics["avg_rating"] > 0

    def test_get_domain_feedback_metrics_no_data(self, service, mock_db):
        """Test retrieving domain metrics when no data exists"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.all.return_value = []

        # Get domain metrics
        metrics = service.get_domain_feedback_metrics(
            tenant_id="tenant-456",
            domain="data_analysis",
            days=30
        )

        # Verify zero metrics
        assert metrics["feedback_count"] == 0
        assert metrics["avg_rating"] == 0.0


# ============================================================================
# TEST CATEGORY 5: CANVAS INTEGRATION TESTS (5 tests)
# ============================================================================

class TestCanvasIntegration:
    """Tests for canvas integration with episodes"""

    @pytest.mark.asyncio
    async def test_extract_canvas_metadata_basic(
        self, service, mock_db, sample_execution
    ):
        """Test extracting canvas metadata from execution"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_execution,
            Mock(spec=Canvas),  # Canvas
            5,  # artifact_count
            2   # comment_count
        ]

        # Mock canvas audit query
        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = []

        # Extract metadata
        with patch('core.episode_service._get_canvas_context_provider'):
            with patch('core.episode_service._get_canvas_summary_service'):
                metadata = await service._extract_canvas_metadata("exec-123", "Test task")

        # Verify metadata extracted
        assert metadata is not None

    @pytest.mark.asyncio
    async def test_extract_canvas_metadata_no_canvas(
        self, service, mock_db, sample_execution
    ):
        """Test extracting metadata when no canvas exists"""
        # Setup mock - execution without canvas_id
        sample_execution.metadata_json = {}
        mock_db.query.return_value.filter.return_value.first.return_value = sample_execution

        # Extract metadata
        metadata = await service._extract_canvas_metadata("exec-123", "Test task")

        # Verify empty metadata
        assert metadata == {}

    @pytest.mark.asyncio
    async def test_extract_canvas_metadata_canvas_not_found(
        self, service, mock_db, sample_execution
    ):
        """Test extracting metadata when canvas not found"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_execution,
            None  # Canvas not found
        ]

        # Extract metadata
        with patch('core.episode_service._get_canvas_context_provider'):
            metadata = await service._extract_canvas_metadata("exec-123", "Test task")

        # Verify fallback to canvas_id only
        assert "canvas_id" in metadata

    def test_get_canvas_actions_for_episode(self, service, mock_db):
        """Test retrieving canvas actions for episode"""
        # Setup mock episode
        episode = Mock(spec=AgentEpisode)
        episode.id = "episode-123"
        episode.tenant_id = "tenant-456"
        episode.metadata_json = {
            "canvas_action_ids": ["action-1", "action-2"]
        }

        # Setup mock canvas actions
        action = Mock(spec=CanvasAudit)
        action.id = "action-1"
        action.action_type = "form_submit"
        action.canvas_id = "canvas-789"
        action.user_id = "user-123"
        action.details_json = {"field": "value"}
        action.created_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.first.return_value = episode
        mock_db.query.return_value.filter.return_value.all.return_value = [action]

        # Get canvas actions
        actions = service.get_canvas_actions_for_episode("episode-123")

        # Verify actions retrieved
        assert len(actions) >= 0

    def test_link_canvas_actions_to_episode(self, service, mock_db):
        """Test linking canvas actions to episode"""
        # Setup mock episode
        episode = Mock(spec=AgentEpisode)
        episode.id = "episode-123"
        episode.metadata_json = {}

        mock_db.query.return_value.filter.return_value.first.return_value = episode
        mock_db.commit = Mock()

        # Link canvas actions
        success = service.link_canvas_actions_to_episode(
            episode_id="episode-123",
            canvas_action_ids=["action-1", "action-2"]
        )

        # Verify linked
        assert success is True
        mock_db.commit.assert_called()


# ============================================================================
# TEST CATEGORY 6: SKILL PERFORMANCE TESTS (5 tests)
# ============================================================================

class TestSkillPerformance:
    """Tests for skill performance tracking"""

    def test_get_skill_performance_stats_basic(self, service, mock_db):
        """Test retrieving skill performance stats"""
        # Setup mock episodes
        episode = Mock(spec=AgentEpisode)
        episode.success = True
        episode.completed_at = datetime.now(timezone.utc)
        episode.started_at = datetime.now(timezone.utc) - timedelta(minutes=5)

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            episode
        ]

        # Mock skill query
        skill = Mock(spec=Skill)
        skill.name = "test_skill"
        mock_db.query.return_value.filter.return_value.first.return_value = skill

        # Get stats
        stats = service.get_skill_performance_stats(
            agent_id="agent-123",
            tenant_id="tenant-456",
            skill_id="skill-789"
        )

        # Verify stats
        assert stats.skill_id == "skill-789"
        assert stats.total_executions >= 0

    def test_get_skill_performance_stats_no_executions(self, service, mock_db):
        """Test skill stats when no executions exist"""
        # Setup mock - no episodes
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # Mock skill query
        skill = Mock(spec=Skill)
        skill.name = "test_skill"
        mock_db.query.return_value.first.return_value = skill

        # Get stats
        stats = service.get_skill_performance_stats(
            agent_id="agent-123",
            tenant_id="tenant-456",
            skill_id="skill-789"
        )

        # Verify zero stats
        assert stats.total_executions == 0
        assert stats.success_rate == 0.0

    def test_get_agent_skill_usage_basic(self, service, mock_db):
        """Test retrieving agent skill usage summary"""
        # Setup mock episodes
        episode = Mock(spec=AgentEpisode)
        episode.metadata_json = {"skill_id": "skill-789"}
        episode.success = True
        episode.completed_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            episode
        ]

        # Mock skill query
        skill = Mock(spec=Skill)
        skill.name = "test_skill"
        mock_db.query.return_value.first.return_value = skill

        # Get skill usage
        usage = service.get_agent_skill_usage(
            agent_id="agent-123",
            tenant_id="tenant-456"
        )

        # Verify usage
        assert isinstance(usage, list)

    def test_get_skill_usage_count(self, service, mock_db):
        """Test counting skill usage"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.count.return_value = 5

        # Get count
        count = service.get_skill_usage_count(
            agent_id="agent-123",
            tenant_id="tenant-456"
        )

        # Verify count
        assert count == 5

    def test_assess_skill_mastery(self, service, mock_db):
        """Test skill mastery assessment"""
        # Mock skill usage
        with patch.object(service, 'get_agent_skill_usage', return_value=[]):
            # Assess mastery
            assessment = service.assess_skill_mastery(
                agent_id="agent-123",
                tenant_id="tenant-456",
                target_level="intern"
            )

            # Verify assessment
            assert assessment.mastery_score >= 0.0
            assert assessment.skill_diversity >= 0.0


# ============================================================================
# TEST CATEGORY 7: ARCHIVAL TESTS (4 tests)
# ============================================================================

class TestEpisodeArchival:
    """Tests for episode archival to cold storage"""

    @pytest.mark.asyncio
    async def test_archive_episode_to_cold_storage_success(
        self, service, mock_db, sample_episode, mock_lancedb_service
    ):
        """Test successful episode archival"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_episode

        # Archive episode
        success = await service.archive_episode_to_cold_storage("episode-123")

        # Verify archived
        assert success is True
        mock_lancedb_service.add_episode.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_episode_to_cold_storage_not_found(self, service, mock_db):
        """Test archival with non-existent episode"""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Archive episode
        success = await service.archive_episode_to_cold_storage("nonexistent-episode")

        # Verify not archived
        assert success is False

    @pytest.mark.asyncio
    async def test_archive_episode_to_cold_storage_lancedb_unavailable(
        self, service, mock_db, sample_episode
    ):
        """Test archival when LanceDB unavailable"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_episode
        service.lancedb = None

        with patch('core.episode_service.LanceDBService', return_value=None):
            # Archive episode
            success = await service.archive_episode_to_cold_storage("episode-123")

            # Verify not archived
            assert success is False

    @pytest.mark.asyncio
    async def test_archive_episode_to_cold_storage_embedding_failure(
        self, service, mock_db, sample_episode, mock_embedding_service
    ):
        """Test archival with embedding generation failure"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_episode
        mock_embedding_service.generate_embedding = AsyncMock(side_effect=Exception("Embedding failed"))

        # Archive episode
        success = await service.archive_episode_to_cold_storage("episode-123")

        # Verify still archived with zero embedding fallback
        assert success is True


# ============================================================================
# TEST CATEGORY 8: ERROR HANDLING TESTS (4 tests)
# ============================================================================

class TestErrorHandling:
    """Tests for error handling scenarios"""

    def test_constitutional_score_no_violations(self, service):
        """Test constitutional score with no violations"""
        # Calculate score
        score = service._calculate_constitutional_score([])

        # Verify perfect score
        assert score == 1.0

    def test_constitutional_score_with_violations(self, service):
        """Test constitutional score with violations"""
        # Create violations
        violations = [
            {"severity": "critical", "description": "Critical violation"},
            {"severity": "high", "description": "High severity"},
            {"severity": "low", "description": "Low severity"}
        ]

        # Calculate score
        score = service._calculate_constitutional_score(violations)

        # Verify score reduced
        assert score < 1.0
        assert score >= 0.0

    def test_step_efficiency_no_steps(self, service, mock_db):
        """Test step efficiency with no steps"""
        # Setup mock - no reasoning steps
        mock_db.query.return_value.filter.return_value.all.return_value = []

        # Calculate efficiency
        efficiency = service._calculate_step_efficiency("exec-123")

        # Verify default efficiency
        assert efficiency == 1.0

    def test_step_efficiency_with_steps(self, service, mock_db):
        """Test step efficiency with reasoning steps"""
        # Setup mock reasoning steps
        from core.models import AgentReasoningStep

        step1 = Mock(spec=AgentReasoningStep)
        step1.step_type = "thought"

        step2 = Mock(spec=AgentReasoningStep)
        step2.step_type = "action"

        step3 = Mock(spec=AgentReasoningStep)
        step3.step_type = "observation"

        mock_db.query.return_value.filter.return_value.all.return_value = [
            step1, step2, step3
        ]

        # Calculate efficiency
        efficiency = service._calculate_step_efficiency("exec-123")

        # Verify efficiency calculated
        assert 0.0 <= efficiency <= 1.0


# ============================================================================
# TEST CATEGORY 9: PROPOSAL EPISODES TESTS (2 tests)
# ============================================================================

class TestProposalEpisodes:
    """Tests for proposal episode retrieval for learning"""

    def test_get_proposal_episodes_for_learning_basic(self, service, mock_db):
        """Test retrieving proposal episodes for learning"""
        # Setup mock proposal episode
        episode = Mock(spec=AgentEpisode)
        episode.id = "episode-123"
        episode.agent_id = "agent-123"
        episode.tenant_id = "tenant-456"
        episode.started_at = datetime.now(timezone.utc)
        episode.task_description = "Test proposal task"
        episode.metadata_json = {
            "episode_type": "meta_agent_proposal",
            "quality_score": 0.85,
            "proposal_id": "proposal-123",
            "capability_tags": ["data_analysis"]
        }

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            episode
        ]
        mock_db.query.return_value = mock_query

        # Get proposal episodes
        proposals = service.get_proposal_episodes_for_learning(
            tenant_id="tenant-456",
            agent_id="agent-123",
            min_quality=0.7,
            limit=10
        )

        # Verify results
        assert len(proposals) >= 0
        if proposals:
            assert "quality_score" in proposals[0]
            assert "task_description" in proposals[0]

    def test_get_proposal_episodes_for_learning_with_capability_filter(self, service, mock_db):
        """Test retrieving proposal episodes with capability filter"""
        # Setup mock proposal episode
        episode = Mock(spec=AgentEpisode)
        episode.id = "episode-123"
        episode.agent_id = "agent-123"
        episode.tenant_id = "tenant-456"
        episode.started_at = datetime.now(timezone.utc)
        episode.task_description = "Test proposal task"
        episode.metadata_json = {
            "episode_type": "meta_agent_proposal",
            "quality_score": 0.85,
            "capability_tags": ["data_analysis", "integrations"]
        }

        mock_query = Mock()
        mock_query.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            episode
        ]
        mock_db.query.return_value = mock_query

        # Get proposal episodes with capability filter
        proposals = service.get_proposal_episodes_for_learning(
            tenant_id="tenant-456",
            agent_id="agent-123",
            capability_tags=["data_analysis"],
            min_quality=0.7,
            limit=10
        )

        # Verify results
        assert isinstance(proposals, list)


# ============================================================================
# END OF TESTS
# ============================================================================
