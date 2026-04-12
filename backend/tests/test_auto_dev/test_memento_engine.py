"""
Test MementoEngine skill generation.

Tests cover:
- Episode analysis (extract failure patterns)
- Code proposal (generate skill code)
- Validation (execute in sandbox)
- Skill promotion (create CommunitySkill)
- Event subscription and triggering
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

from core.auto_dev.memento_engine import MementoEngine
from core.auto_dev.models import SkillCandidate


# =============================================================================
# Episode Analysis Tests
# =============================================================================

class TestMementoEngineEpisodeAnalysis:
    """Test analyze_episode() extracts failure pattern."""

    @pytest.mark.asyncio
    async def test_analyze_episode_extracts_task_description(self, auto_dev_db_session, sample_episode):
        """Test analyze_episode() extracts task_description."""
        if not sample_episode:
            pytest.skip("Episode model not available")

        engine = MementoEngine(db=auto_dev_db_session)
        result = await engine.analyze_episode(sample_episode.id)

        assert "task_description" in result
        assert result["task_description"] == "Analyze customer data and generate insights"

    @pytest.mark.asyncio
    async def test_analyze_episode_extracts_error_trace(self, auto_dev_db_session):
        """Test analyze_episode() extracts error_trace from failed steps."""
        try:
            from core.models import AgentEpisode, EpisodeSegment

            # Create test episode with error segments
            episode = AgentEpisode(
                id="ep-error-001",
                agent_id="agent-001",
                tenant_id="tenant-001",
                task_description="Process data",
                maturity_at_time="AUTONOMOUS",
                outcome="failure",
                success=False,
                status="active",
                confidence_score=0.5,
                constitutional_score=1.0,
                human_intervention_count=0,
                step_efficiency=1.0,
                access_count=0,
                importance_score=0.5,
                decay_score=1.0,
            )
            auto_dev_db_session.add(episode)
            auto_dev_db_session.flush()

            error_segment = EpisodeSegment(
                id="seg-error-001",
                episode_id=episode.id,
                segment_type="error",
                sequence_order=1,
                content="ValueError: Invalid data format",
            )
            auto_dev_db_session.add(error_segment)
            auto_dev_db_session.commit()

            engine = MementoEngine(db=auto_dev_db_session)
            result = await engine.analyze_episode(episode.id)

            assert "error_trace" in result
            assert "ValueError" in result["error_trace"]
        except ImportError:
            pytest.skip("Episode models not available")

    @pytest.mark.asyncio
    async def test_analyze_episode_extracts_tool_calls(self, auto_dev_db_session):
        """Test analyze_episode() extracts tool_calls from execution data."""
        try:
            from core.models import AgentEpisode, EpisodeSegment

            episode = AgentEpisode(
                id="ep-tools-001",
                agent_id="agent-001",
                tenant_id="tenant-001",
                task_description="Execute tools",
                maturity_at_time="AUTONOMOUS",
                outcome="failure",
                success=False,
                status="active",
                confidence_score=0.5,
                constitutional_score=1.0,
                human_intervention_count=0,
                step_efficiency=1.0,
                access_count=0,
                importance_score=0.5,
                decay_score=1.0,
            )
            auto_dev_db_session.add(episode)
            auto_dev_db_session.flush()

            segment = EpisodeSegment(
                id="seg-tool-001",
                episode_id=episode.id,
                segment_type="tool_call",
                sequence_order=1,
                content="Tool call: data_processor - failed",
            )
            auto_dev_db_session.add(segment)
            auto_dev_db_session.commit()

            engine = MementoEngine(db=auto_dev_db_session)
            result = await engine.analyze_episode(episode.id)

            assert "tool_calls_attempted" in result
            assert len(result["tool_calls_attempted"]) > 0
            assert result["tool_calls_attempted"][0]["tool_name"] == "data_processor"
        except ImportError:
            pytest.skip("Episode models not available")

    @pytest.mark.asyncio
    async def test_analyze_episode_identifies_failure_patterns(self, auto_dev_db_session):
        """Test analyze_episode() identifies failure patterns."""
        try:
            from core.models import AgentEpisode

            episode = AgentEpisode(
                id="ep-pattern-001",
                agent_id="agent-001",
                tenant_id="tenant-001",
                task_description="Process CSV data with invalid format",
                maturity_at_time="AUTONOMOUS",
                outcome="failure",
                success=False,
                status="active",
                confidence_score=0.5,
                constitutional_score=1.0,
                human_intervention_count=0,
                step_efficiency=1.0,
                access_count=0,
                importance_score=0.5,
                decay_score=1.0,
            )
            auto_dev_db_session.add(episode)
            auto_dev_db_session.commit()

            engine = MementoEngine(db=auto_dev_db_session)
            result = await engine.analyze_episode(episode.id)

            assert "failure_summary" in result
            assert "suggested_skill_name" in result
        except ImportError:
            pytest.skip("Episode models not available")

    @pytest.mark.asyncio
    async def test_analyze_episode_handles_missing_data_gracefully(self, auto_dev_db_session):
        """Test analyze_episode() handles missing data gracefully."""
        engine = MementoEngine(db=auto_dev_db_session)
        result = await engine.analyze_episode("nonexistent-episode-id")

        assert "error" in result


# =============================================================================
# Code Proposal Tests
# =============================================================================

class TestMementoEngineCodeProposal:
    """Test propose_code_change() generates skill code."""

    @pytest.mark.asyncio
    async def test_propose_code_change_calls_llm(self, mock_auto_dev_llm):
        """Test propose_code_change() calls LLM."""
        engine = MementoEngine(db=MagicMock(), llm_service=mock_auto_dev_llm)

        context = {
            "task_description": "Process sales data",
            "error_trace": "ValueError: Invalid format",
            "tool_calls_attempted": [],
        }

        result = await engine.propose_code_change(context)

        mock_auto_dev_llm.generate_completion.assert_called_once()
        assert "def" in result  # Should contain function definition

    @pytest.mark.asyncio
    async def test_propose_code_change_generates_python_code(self, mock_auto_dev_llm):
        """Test propose_code_change() generates Python code string."""
        engine = MementoEngine(db=MagicMock(), llm_service=mock_auto_dev_llm)

        context = {
            "task_description": "Analyze data",
            "error_trace": "Analysis failed",
        }

        result = await engine.propose_code_change(context)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_propose_code_change_includes_skill_description(self, mock_auto_dev_llm):
        """Test propose_code_change() includes skill description in prompt."""
        engine = MementoEngine(db=MagicMock(), llm_service=mock_auto_dev_llm)

        context = {
            "task_description": "Process CSV files",
            "error_trace": "CSV parsing error",
            "tool_calls_attempted": [{"tool_name": "csv_reader"}],
        }

        result = await engine.propose_code_change(context)

        # Verify LLM was called with proper context
        call_args = mock_auto_dev_llm.generate_completion.call_args
        messages = call_args[1]["messages"]
        user_prompt = messages[1]["content"]

        assert "Process CSV files" in user_prompt
        assert "csv_reader" in user_prompt

    @pytest.mark.asyncio
    async def test_propose_code_change_strips_markdown_fences(self, mock_auto_dev_llm):
        """Test propose_code_change() strips markdown fences."""
        engine = MementoEngine(db=MagicMock(), llm_service=mock_auto_dev_llm)

        # Mock LLM to return code with fences
        async def mock_return(**kwargs):
            return {"content": "```python\ndef function(): pass\n```"}

        mock_auto_dev_llm.generate_completion = AsyncMock(side_effect=mock_return)

        context = {"task_description": "Test"}

        result = await engine.propose_code_change(context)

        assert "```" not in result
        assert "def function(): pass" in result

    @pytest.mark.asyncio
    async def test_propose_code_change_handles_llm_errors(self):
        """Test propose_code_change() handles LLM errors."""
        # Mock LLM that raises error
        mock_llm = MagicMock()
        mock_llm.generate_completion = AsyncMock(side_effect=Exception("LLM error"))

        engine = MementoEngine(db=MagicMock(), llm_service=mock_llm)

        context = {"task_description": "Test"}

        result = await engine.propose_code_change(context)

        # Should return error comment
        assert "# Skill generation failed" in result


# =============================================================================
# Validation Tests
# =============================================================================

class TestMementoEngineValidation:
    """Test validate_change() executes in sandbox."""

    @pytest.mark.asyncio
    async def test_validate_change_calls_sandbox(self, mock_sandbox):
        """Test validate_change() calls sandbox."""
        engine = MementoEngine(db=MagicMock(), sandbox=mock_sandbox)

        code = "def test(): pass"
        test_inputs = [{"input": "test"}]

        result = await engine.validate_change(code, test_inputs, "tenant-001")

        mock_sandbox.execute_raw_python.assert_called()
        assert "passed" in result

    @pytest.mark.asyncio
    async def test_validate_change_passes_test_inputs_to_sandbox(self, mock_sandbox):
        """Test validate_change() passes test_inputs to sandbox."""
        engine = MementoEngine(db=MagicMock(), sandbox=mock_sandbox)

        code = "print('test')"
        test_inputs = [{"data": "value1"}, {"data": "value2"}]

        await engine.validate_change(code, test_inputs, "tenant-001")

        # Should be called twice (once per input)
        assert mock_sandbox.execute_raw_python.call_count == 2

    @pytest.mark.asyncio
    async def test_validate_change_returns_proxy_signals(self, mock_sandbox):
        """Test validate_change() returns proxy_signals."""
        engine = MementoEngine(db=MagicMock(), sandbox=mock_sandbox)

        code = "def test(): return True"
        test_inputs = [{}]

        result = await engine.validate_change(code, test_inputs, "tenant-001")

        assert "test_results" in result
        assert isinstance(result["test_results"], list)

    @pytest.mark.asyncio
    async def test_validate_change_handles_sandbox_errors(self):
        """Test validate_change() handles sandbox errors."""
        # Mock sandbox that raises error
        mock_sandbox = MagicMock()
        mock_sandbox.execute_raw_python = AsyncMock(side_effect=Exception("Sandbox error"))

        engine = MementoEngine(db=MagicMock(), sandbox=mock_sandbox)

        code = "def test(): pass"
        test_inputs = [{}]

        # Should not crash, but return error
        result = await engine.validate_change(code, test_inputs, "tenant-001")

        assert "passed" in result


# =============================================================================
# Skill Promotion Tests
# =============================================================================

class TestMementoEngineSkillPromotion:
    """Test promote_skill() creates CommunitySkill."""

    @pytest.mark.asyncio
    async def test_promote_skill_creates_community_skill(self, auto_dev_db_session, sample_skill_candidate):
        """Test promote_skill() creates CommunitySkill."""
        # Mock SkillBuilderService
        mock_builder = MagicMock()
        mock_builder.create_skill_package = MagicMock(return_value={"success": True})

        import sys
        original_module = sys.modules.get("core.skill_builder_service")

        class MockSkillBuilderService:
            def __init__(self):
                pass

        sys.modules["core.skill_builder_service"] = MockSkillBuilderService
        sys.modules["core.skill_builder_service"].SkillBuilderService = lambda: mock_builder

        try:
            engine = MementoEngine(db=auto_dev_db_session)

            # Update candidate to validated
            sample_skill_candidate.validation_status = "validated"
            auto_dev_db_session.commit()

            result = await engine.promote_skill(sample_skill_candidate.id, sample_skill_candidate.tenant_id)

            # Verify candidate was promoted
            auto_dev_db_session.refresh(sample_skill_candidate)
            assert sample_skill_candidate.validation_status == "promoted"
            assert sample_skill_candidate.promoted_at is not None
        finally:
            if original_module:
                sys.modules["core.skill_builder_service"] = original_module
            else:
                sys.modules.pop("core.skill_builder_service", None)

    @pytest.mark.asyncio
    async def test_promote_skill_handles_not_validated_candidate(self, auto_dev_db_session, sample_skill_candidate):
        """Test promote_skill() handles not validated candidate."""
        engine = MementoEngine(db=auto_dev_db_session)

        # Candidate is still pending
        result = await engine.promote_skill(sample_skill_candidate.id, sample_skill_candidate.tenant_id)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_promote_skill_handles_database_errors(self, auto_dev_db_session):
        """Test promote_skill() handles database errors."""
        engine = MementoEngine(db=auto_dev_db_session)

        result = await engine.promote_skill("nonexistent-id", "tenant-001")

        assert "error" in result


# =============================================================================
# Event Integration Tests
# =============================================================================

class TestMementoEngineEventIntegration:
    """Test event subscription and triggering."""

    def test_memento_engine_has_base_methods(self):
        """Test MementoEngine has all required BaseLearningEngine methods."""
        from core.auto_dev.base_engine import BaseLearningEngine

        assert issubclass(MementoEngine, BaseLearningEngine)

        # Check all abstract methods are implemented
        assert hasattr(MementoEngine, "analyze_episode")
        assert hasattr(MementoEngine, "propose_code_change")
        assert hasattr(MementoEngine, "validate_change")


# =============================================================================
# Full Pipeline Tests
# =============================================================================

class TestMementoEngineFullPipeline:
    """Test end-to-end MementoEngine pipeline."""

    @pytest.mark.asyncio
    async def test_generate_skill_candidate_full_pipeline(self, auto_dev_db_session, mock_auto_dev_llm, mock_sandbox, sample_tenant_id, sample_agent_id):
        """Test generate_skill_candidate() full pipeline."""
        try:
            from core.models import AgentEpisode

            episode = AgentEpisode(
                id="ep-pipeline-001",
                agent_id=sample_agent_id,
                tenant_id=sample_tenant_id,
                task_description="Process complex data",
                maturity_at_time="AUTONOMOUS",
                outcome="failure",
                success=False,
                status="active",
                confidence_score=0.5,
                constitutional_score=1.0,
                human_intervention_count=0,
                step_efficiency=1.0,
                access_count=0,
                importance_score=0.5,
                decay_score=1.0,
            )
            auto_dev_db_session.add(episode)
            auto_dev_db_session.commit()

            engine = MementoEngine(db=auto_dev_db_session, llm_service=mock_auto_dev_llm, sandbox=mock_sandbox)

            candidate = await engine.generate_skill_candidate(
                tenant_id=sample_tenant_id,
                agent_id=sample_agent_id,
                episode_id=episode.id,
            )

            assert candidate.id is not None
            assert candidate.validation_status == "pending"
            assert candidate.skill_name is not None
            assert candidate.generated_code is not None
        except ImportError:
            pytest.skip("Episode model not available")

    @pytest.mark.asyncio
    async def test_validate_candidate_full_pipeline(self, auto_dev_db_session, mock_sandbox, sample_skill_candidate):
        """Test validate_candidate() updates candidate status."""
        engine = MementoEngine(db=auto_dev_db_session, sandbox=mock_sandbox)

        result = await engine.validate_candidate(
            candidate_id=sample_skill_candidate.id,
            tenant_id=sample_skill_candidate.tenant_id,
            test_inputs=[{}],
        )

        assert result["candidate_id"] == sample_skill_candidate.id
        assert "passed" in result

        # Check candidate was updated
        auto_dev_db_session.refresh(sample_skill_candidate)
        assert sample_skill_candidate.validation_status in ["validated", "failed"]
        assert sample_skill_candidate.validated_at is not None
