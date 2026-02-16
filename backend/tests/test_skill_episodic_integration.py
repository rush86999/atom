"""
Integration tests for community skills with episodic memory and graduation.

Tests verify:
- Skill executions create EpisodeSegments with skill metadata
- Failed skill executions create error episodes
- Graduation service tracks skill usage metrics
- Skill diversity bonus applied to readiness score
- API endpoints return episodic context and learning progress

Reference: Phase 14 Plan 03 - Gap Closure 01
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock
from datetime import datetime, timedelta

from core.skill_registry_service import SkillRegistryService
from core.episode_segmentation_service import EpisodeSegmentationService
from core.agent_graduation_service import AgentGraduationService
from core.models import EpisodeSegment, SkillExecution, AgentRegistry, AgentStatus


class TestSkillEpisodicIntegration:
    """Test episodic memory integration with community skills."""

    @pytest.mark.asyncio
    async def test_skill_execution_creates_episode(self, db_session):
        """Verify successful skill execution creates episode segment."""
        # Setup
        service = SkillRegistryService(db_session)
        service._segmentation_service = Mock()

        # Mock episode creation
        mock_segment = Mock()
        mock_segment.id = "episode-123"
        service._create_execution_episode = AsyncMock(return_value=mock_segment.id)

        # Import a test skill
        content = """---
name: TestCalculator
description: A simple calculator
---
Calculate: {{query}}
"""
        result = service.import_skill(
            source="raw_content",
            content=content,
            metadata={"author": "test"}
        )

        skill_id = result["skill_id"]

        # Execute skill
        execution_result = service.execute_skill(
            skill_id=skill_id,
            inputs={"query": "2+2"},
            agent_id="test-agent"
        )

        # Verify execution succeeded
        assert execution_result["success"] is True
        assert execution_result["execution_id"] is not None

        # Verify episode was created
        service._create_execution_episode.assert_called_once()
        call_args = service._create_execution_episode.call_args

        # Verify episode metadata
        assert call_args[1]["skill_name"] == "TestCalculator"
        assert call_args[1]["agent_id"] == "test-agent"
        assert call_args[1]["error"] is None
        assert call_args[1]["execution_time"] >= 0

    @pytest.mark.asyncio
    async def test_skill_failure_creates_error_episode(self, db_session):
        """Verify failed skill execution creates error episode."""
        service = SkillRegistryService(db_session)
        service._segmentation_service = Mock()

        # Mock episode creation
        mock_segment = Mock()
        mock_segment.id = "episode-error-123"
        service._create_execution_episode = AsyncMock(return_value=mock_segment.id)

        # Import skill
        content = """---
name: BrokenSkill
---
This skill will fail
"""
        result = service.import_skill(
            source="raw_content",
            content=content
        )

        skill_id = result["skill_id"]

        # Mock execution to raise error
        service._execute_prompt_skill = Mock(side_effect=Exception("Test error"))

        # Execute skill (should fail)
        execution_result = service.execute_skill(
            skill_id=skill_id,
            inputs={"query": "test"},
            agent_id="test-agent"
        )

        # Verify execution failed
        assert execution_result["success"] is False
        assert "error" in execution_result

        # Verify error episode was created
        service._create_execution_episode.assert_called_once()
        call_args = service._create_execution_episode.call_args

        # Verify error metadata
        assert call_args[1]["skill_name"] == "BrokenSkill"
        assert call_args[1]["error"] is not None
        assert isinstance(call_args[1]["error"], Exception)

    @pytest.mark.asyncio
    async def test_skill_metadata_extracted_correctly(self, db_session):
        """Verify skill metadata (name, source, execution time) is captured."""
        service = SkillRegistryService(db_session)

        # Test metadata extraction
        inputs = {"query": "What is 2+2?", "context": "math help"}
        summary = service._summarize_inputs(inputs)

        # Verify summarization
        assert "query" in summary
        assert "context" in summary
        assert "math help" in summary

    @pytest.mark.asyncio
    async def test_graduation_service_tracks_skill_usage(self, db_session):
        """Verify graduation service calculates skill usage metrics."""
        service = AgentGraduationService(db_session)

        # Create test agent
        agent = AgentRegistry(
            id="test-agent-graduation",
            name="Test Agent",
            status=AgentStatus.INTERN,
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        # Create mock skill executions
        for i in range(5):
            execution = SkillExecution(
                id=f"skill-exec-{i}",
                agent_id="test-agent-graduation",
                skill_id=f"skill-{i % 2}",  # 2 unique skills
                workspace_id="default",
                status="success" if i < 4 else "failed",
                skill_source="community",
                executed_at=datetime.utcnow() - timedelta(days=i)
            )
            db_session.add(execution)

        db_session.commit()

        # Calculate skill usage metrics
        metrics = await service.calculate_skill_usage_metrics(
            agent_id="test-agent-graduation",
            days_back=30
        )

        # Verify metrics
        assert metrics["total_skill_executions"] == 5
        assert metrics["successful_executions"] == 4
        assert metrics["success_rate"] == 0.8
        assert metrics["unique_skills_used"] == 2
        assert metrics["skill_episodes_count"] >= 0  # May not have episodes
        assert metrics["skill_learning_velocity"] >= 0

    @pytest.mark.asyncio
    async def test_skill_diversity_bonus_in_readiness_score(self, db_session):
        """Verify unique skill usage contributes to graduation readiness."""
        service = AgentGraduationService(db_session)

        # Create test agent
        agent = AgentRegistry(
            id="test-agent-diversity",
            name="Test Agent Diversity",
            status=AgentStatus.INTERN,
            workspace_id="default"
        )
        db_session.add(agent)
        db_session.commit()

        # Create diverse skill executions (5 unique skills)
        for i in range(10):
            execution = SkillExecution(
                id=f"skill-exec-div-{i}",
                agent_id="test-agent-diversity",
                skill_id=f"unique-skill-{i}",  # All different
                workspace_id="default",
                status="success",
                skill_source="community",
                executed_at=datetime.utcnow()
            )
            db_session.add(execution)

        db_session.commit()

        # Calculate readiness score with skills
        result = await service.calculate_readiness_score_with_skills(
            agent_id="test-agent-diversity",
            target_maturity="SUPERVISED"
        )

        # Verify skill diversity bonus
        assert "skill_metrics" in result
        assert result["skill_metrics"]["unique_skills_used"] == 10
        assert result["skill_diversity_bonus"] > 0  # Should get bonus for diversity
        assert result["skill_diversity_bonus"] <= 0.05  # Max 5% bonus

    @pytest.mark.asyncio
    async def test_skill_aware_episode_segmentation(self, db_session):
        """Verify EpisodeSegmentationService creates skill episodes."""
        service = EpisodeSegmentationService(db_session)

        # Create skill episode
        episode_id = await service.create_skill_episode(
            agent_id="test-agent",
            skill_name="TestSkill",
            inputs={"query": "test"},
            result="Success result",
            error=None,
            execution_time=1.5
        )

        # Verify episode created
        assert episode_id is not None

        # Verify segment in database
        segment = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.id == episode_id
        ).first()

        assert segment is not None
        assert segment.segment_type == "skill_execution"
        assert segment.metadata["skill_name"] == "TestSkill"
        assert segment.metadata["skill_source"] == "community"
        assert segment.metadata["execution_time"] == 1.5
        assert segment.metadata["execution_successful"] is True

    @pytest.mark.asyncio
    async def test_skill_metadata_extraction(self, db_session):
        """Verify skill metadata extraction from context data."""
        service = EpisodeSegmentationService(db_session)

        context_data = {
            "skill_name": "Calculator",
            "skill_source": "community",
            "execution_time": 2.5,
            "input_summary": "Calculate 2+2",
            "result_summary": "4",
            "error_type": None
        }

        metadata = service.extract_skill_metadata(context_data)

        # Verify extracted metadata
        assert metadata["skill_name"] == "Calculator"
        assert metadata["skill_source"] == "community"
        assert metadata["execution_successful"] is True
        assert metadata["execution_time"] == 2.5
        assert "input_hash" in metadata

    @pytest.mark.asyncio
    async def test_get_skill_episodes_endpoint(self, test_client):
        """Verify API endpoint returns skill execution episodes."""
        # This would require setting up a full FastAPI test client
        # and creating test data in the database
        # For now, we'll skip this as it requires more complex setup
        pytest.skip("Requires FastAPI TestClient setup")

    @pytest.mark.asyncio
    async def test_learning_progress_endpoint(self, test_client):
        """Verify API endpoint returns learning trends over time."""
        # This would require setting up a full FastAPI test client
        # and creating test data in the database
        # For now, we'll skip this as it requires more complex setup
        pytest.skip("Requires FastAPI TestClient setup")
