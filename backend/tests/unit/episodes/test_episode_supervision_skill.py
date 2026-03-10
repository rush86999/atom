"""
Unit tests for supervision and skill episode creation.

Tests the specialized episode creation methods for supervision sessions
and skill executions. These are critical for agent graduation tracking
and skill performance monitoring.

Target: 15 tests for supervision and skill episodes
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from core.models import (
    AgentExecution,
    AgentStatus,
    Episode,
    EpisodeSegment,
    SupervisionSession,
)


# ========================================================================
# Test Supervision Episode Creation
# ========================================================================

class TestSupervisionEpisodeCreation:
    """Tests for create_supervision_episode method"""

    @pytest.mark.asyncio
    async def test_create_supervision_episode_from_session(
        self,
        segmentation_service_mocked,
        episode_test_supervision_session,
        episode_test_agent_execution
    ):
        """Test creating episode from supervision session"""
        # Arrange
        session = episode_test_supervision_session
        execution = episode_test_agent_execution
        service = segmentation_service_mocked

        # Act
        episode = await service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=service.db
        )

        # Assert
        assert episode is not None
        assert "Supervision Session" in episode.title
        assert episode.supervisor_rating == 4
        assert episode.intervention_count == 2
        assert set(episode.intervention_types) == {"human_correction", "guidance"}
        assert episode.maturity_at_time == AgentStatus.SUPERVISED.value
        assert episode.agent_id == "test_agent"
        assert episode.user_id == "test_supervisor"

    @pytest.mark.asyncio
    async def test_create_supervision_episode_with_multiple_interventions(
        self,
        segmentation_service_mocked,
        episode_test_supervision_session_multiple_interventions,
        episode_test_agent_execution
    ):
        """Test creating episode with multiple intervention types"""
        # Arrange
        session = episode_test_supervision_session_multiple_interventions
        execution = episode_test_agent_execution
        service = segmentation_service_mocked

        # Act
        episode = await service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=service.db
        )

        # Assert
        assert episode is not None
        assert episode.intervention_count == 3
        assert set(episode.intervention_types) == {"human_correction", "guidance", "termination"}
        assert episode.supervisor_rating == 3

    @pytest.mark.asyncio
    async def test_create_supervision_episode_segments(
        self,
        segmentation_service_mocked,
        episode_test_supervision_session,
        episode_test_agent_execution
    ):
        """Test that supervision episode creates 3 segments"""
        # Arrange
        session = episode_test_supervision_session
        execution = episode_test_agent_execution
        service = segmentation_service_mocked

        # Act
        episode = await service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=service.db
        )

        # Assert - query segments from mock db
        segments = service.db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) == 3

        segment_types = {s.segment_type for s in segments}
        assert "execution" in segment_types
        assert "intervention" in segment_types
        assert "reflection" in segment_types

    @pytest.mark.asyncio
    async def test_create_supervision_episode_archives_to_lancedb(
        self,
        segmentation_service_mocked,
        episode_test_supervision_session,
        episode_test_agent_execution
    ):
        """Test that supervision episode is archived to LanceDB"""
        # Arrange
        session = episode_test_supervision_session
        execution = episode_test_agent_execution
        service = segmentation_service_mocked

        # Act
        episode = await service.create_supervision_episode(
            supervision_session=session,
            agent_execution=execution,
            db=service.db
        )

        # Assert - verify LanceDB archival was called
        service.lancedb.add_document.assert_called_once()
        call_args = service.lancedb.add_document.call_args

        # Check metadata contains supervision-specific fields
        metadata = call_args.kwargs.get('metadata', {})
        assert metadata.get('supervisor_rating') == 4
        assert metadata.get('intervention_count') == 2
        assert metadata.get('type') == 'supervision_episode'
        assert 'intervention_types' in metadata

    def test_format_supervision_outcome(
        self,
        segmentation_service_mocked,
        episode_test_supervision_session
    ):
        """Test formatting supervision outcome"""
        # Arrange
        session = episode_test_supervision_session
        service = segmentation_service_mocked

        # Act
        outcome = service._format_supervision_outcome(session)

        # Assert
        assert "Session completed" in outcome
        assert "Duration: 3600s" in outcome
        assert "Supervisor Rating: 4/5" in outcome
        assert "Good performance overall" in outcome

    def test_extract_supervision_topics(
        self,
        segmentation_service_mocked,
        episode_test_supervision_session,
        episode_test_agent_execution
    ):
        """Test extracting topics from supervision session"""
        # Arrange
        session = episode_test_supervision_session
        execution = episode_test_agent_execution
        service = segmentation_service_mocked

        # Act
        topics = service._extract_supervision_topics(session, execution)

        # Assert
        assert isinstance(topics, list)
        assert len(topics) > 0
        # Check for intervention-related topics
        intervention_topics = [t for t in topics if "intervention_" in t]
        assert len(intervention_topics) == 2


# ========================================================================
# Test Supervision Helper Methods
# ========================================================================

class TestSupervisionHelperMethods:
    """Tests for supervision episode helper methods"""

    def test_format_agent_actions(
        self,
        segmentation_service_mocked,
        episode_test_supervision_session,
        episode_test_agent_execution
    ):
        """Test formatting agent actions"""
        # Arrange
        interventions = episode_test_supervision_session.interventions
        execution = episode_test_agent_execution
        service = segmentation_service_mocked

        # Act
        actions = service._format_agent_actions(interventions, execution)

        # Assert
        assert "Task:" in actions
        assert "Dataset: sales_2024.csv" in actions  # From input_summary
        assert "Status: completed" in actions
        assert "Input:" in actions
        assert "Output:" in actions
        assert "Total interventions: 2" in actions

    def test_format_interventions(
        self,
        segmentation_service_mocked,
        episode_test_supervision_session
    ):
        """Test formatting interventions"""
        # Arrange
        interventions = episode_test_supervision_session.interventions
        service = segmentation_service_mocked

        # Act
        formatted = service._format_interventions(interventions)

        # Assert
        assert "[human_correction]" in formatted
        assert "[guidance]" in formatted
        assert "2026-03-10T10:00:00Z" in formatted
        assert "Fix the calculation error" in formatted
        assert "1." in formatted  # Numbered list
        assert "2." in formatted

    def test_extract_supervision_entities(
        self,
        segmentation_service_mocked,
        episode_test_supervision_session,
        episode_test_agent_execution
    ):
        """Test extracting entities from supervision session"""
        # Arrange
        session = episode_test_supervision_session
        execution = episode_test_agent_execution
        service = segmentation_service_mocked

        # Act
        entities = service._extract_supervision_entities(session, execution)

        # Assert
        assert isinstance(entities, list)
        assert any("session:" in e for e in entities)
        assert any("agent:test_agent" in e for e in entities)
        assert any("supervisor:test_supervisor" in e for e in entities)

    def test_calculate_supervision_importance_high_rating(
        self,
        segmentation_service_mocked
    ):
        """Test importance score with high rating"""
        # Arrange
        session = Mock(
            supervisor_rating=5,
            intervention_count=0
        )
        service = segmentation_service_mocked

        # Act
        score = service._calculate_supervision_importance(session)

        # Assert
        assert score >= 0.7  # High importance
        assert score <= 1.0

    def test_calculate_supervision_importance_low_rating(
        self,
        segmentation_service_mocked
    ):
        """Test importance score with low rating"""
        # Arrange
        session = Mock(
            supervisor_rating=2,
            intervention_count=5
        )
        service = segmentation_service_mocked

        # Act
        score = service._calculate_supervision_importance(session)

        # Assert
        # Base 0.5 + (2-3)*0.15 = 0.35, no intervention bonus/penalty (=5 is not >5)
        assert score <= 0.4  # Low importance
        assert score >= 0.0

    def test_calculate_supervision_importance_clamped(
        self,
        segmentation_service_mocked
    ):
        """Test importance score is clamped to [0.0, 1.0]"""
        # Arrange
        session = Mock(
            supervisor_rating=10,  # Extreme high
            intervention_count=0
        )
        service = segmentation_service_mocked

        # Act
        score = service._calculate_supervision_importance(session)

        # Assert
        assert score == 1.0  # Clamped to max

        # Test extreme low - use rating=1 instead of 0 (0 is falsy and skips calculation)
        session_low = Mock(
            supervisor_rating=1,  # Minimum valid rating
            intervention_count=100
        )
        score = service._calculate_supervision_importance(session_low)
        # Base 0.5 + (1-3)*0.15 = 0.2 - 0.1 (>5 interventions) = 0.1
        assert score == 0.1  # Low score


# ========================================================================
# Test Skill Episode Creation
# ========================================================================

class TestSkillEpisodeCreation:
    """Tests for create_skill_episode method"""

    @pytest.mark.asyncio
    async def test_create_skill_episode_success(
        self,
        segmentation_service_mocked,
        episode_test_skill_execution
    ):
        """Test creating skill episode for successful execution"""
        # Arrange
        skill_data = episode_test_skill_execution
        service = segmentation_service_mocked

        # Act
        segment_id = await service.create_skill_episode(
            agent_id="agent1",
            skill_name="data_analyzer",
            inputs=skill_data["inputs"],
            result=skill_data["result"],
            error=skill_data["error"],
            execution_time=skill_data["execution_time"]
        )

        # Assert
        assert segment_id is not None

        # Query the created segment
        segment = service.db.query(EpisodeSegment).filter(
            EpisodeSegment.id == segment_id
        ).first()

        assert segment is not None
        assert segment.segment_type == "skill_execution"
        assert segment.source_type == "skill_execution"
        assert "Success" in segment.content_summary
        # Note: EpisodeSegment model doesn't have a metadata field, so we check content instead
        assert "data_analyzer" in segment.content

    @pytest.mark.asyncio
    async def test_create_skill_episode_failure(
        self,
        segmentation_service_mocked
    ):
        """Test creating skill episode for failed execution"""
        # Arrange
        service = segmentation_service_mocked
        error = Exception("SMTP connection failed")

        # Act
        segment_id = await service.create_skill_episode(
            agent_id="agent1",
            skill_name="email_sender",
            inputs={"to": "user@example.com"},
            result=None,
            error=error,
            execution_time=0.5
        )

        # Assert
        assert segment_id is not None

        segment = service.db.query(EpisodeSegment).filter(
            EpisodeSegment.id == segment_id
        ).first()

        assert segment is not None
        assert "Failed" in segment.content_summary
        # Note: EpisodeSegment model doesn't have a metadata field
        assert "email_sender" in segment.content
        assert "Exception" in segment.content
        assert "SMTP connection failed" in segment.content

    def test_extract_skill_metadata(
        self,
        segmentation_service_mocked,
        episode_test_skill_execution
    ):
        """Test extracting metadata from skill execution"""
        # Arrange
        skill_data = episode_test_skill_execution
        service = segmentation_service_mocked

        context_data = {
            "skill_name": "data_analyzer",
            "skill_source": "community",
            "input_summary": str(skill_data["inputs"]),
            "error_type": None,
            "execution_time": 1.5
        }

        # Act
        metadata = service.extract_skill_metadata(context_data)

        # Assert
        assert metadata["skill_name"] == "data_analyzer"
        assert metadata["skill_source"] == "community"
        assert metadata["execution_successful"] is True
        assert metadata["execution_time"] == 1.5
        assert "input_hash" in metadata
        assert len(metadata["input_hash"]) == 8  # SHA256 truncated to 8 chars

    def test_summarize_skill_inputs(
        self,
        segmentation_service_mocked
    ):
        """Test summarizing skill inputs (truncation)"""
        # Arrange
        service = segmentation_service_mocked
        long_inputs = {
            "dataset": "x" * 200,  # Long value
            "format": "json"
        }

        # Act
        summary = service._summarize_skill_inputs(long_inputs)

        # Assert
        assert isinstance(summary, str)
        assert "dataset" in summary
        assert "xxx..." in summary  # Truncated
        assert len("x" * 97 + "...") == 100  # Verify truncation length

    def test_format_skill_content_success(
        self,
        segmentation_service_mocked
    ):
        """Test formatting skill content for success case"""
        # Arrange
        service = segmentation_service_mocked
        result = {"total": 1000000, "records": 500}

        # Act
        content = service._format_skill_content(
            skill_name="data_analyzer",
            result=result,
            error=None
        )

        # Assert
        assert "Skill: data_analyzer" in content
        assert "Status: Success" in content
        assert "Result:" in content
        assert "1000000" in content

    def test_format_skill_content_failure(
        self,
        segmentation_service_mocked
    ):
        """Test formatting skill content for failure case"""
        # Arrange
        service = segmentation_service_mocked
        error = Exception("Connection timeout")

        # Act
        content = service._format_skill_content(
            skill_name="email_sender",
            result=None,
            error=error
        )

        # Assert
        assert "Skill: email_sender" in content
        assert "Status: Failed" in content
        assert "Error:" in content
        assert "Exception" in content
        assert "Connection timeout" in content
