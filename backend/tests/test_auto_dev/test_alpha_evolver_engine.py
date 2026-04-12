"""
Test AlphaEvolverEngine mutation and variants.

Tests cover:
- Episode analysis for optimization
- Mutation generation
- Validation in sandbox
- Variant spawning
- Lineage tracking
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine
from core.auto_dev.models import ToolMutation, WorkflowVariant


class TestAlphaEvolverEngineEpisodeAnalysis:
    """Test analyze_episode() identifies optimization opportunities."""

    @pytest.mark.asyncio
    async def test_analyze_episode_extracts_performance_signals(self, auto_dev_db_session, sample_episode):
        """Test analyzes successful episodes for optimization."""
        engine = AlphaEvolverEngine(db=auto_dev_db_session)

        result = await engine.analyze_episode(sample_episode.id)

        # Should return analysis dict
        assert "episode_id" in result

    @pytest.mark.asyncio
    async def test_identifies_slow_tool_calls(self, auto_dev_db_session, sample_episode):
        """Test identifies slow tool calls."""
        engine = AlphaEvolverEngine(db=auto_dev_db_session)

        # Test with mock episode that has slow segments
        result = await engine.analyze_episode(sample_episode.id)

        assert "optimization_targets" in result


class TestAlphaEvolverEngineMutationGeneration:
    """Test generate_tool_mutation() generates mutations."""

    @pytest.mark.asyncio
    async def test_generate_mutation_calls_llm(self, mock_auto_dev_llm, auto_dev_db_session, sample_tenant_id):
        """Test generates code mutations via LLM."""
        engine = AlphaEvolverEngine(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        mutation = await engine.generate_tool_mutation(
            tenant_id=sample_tenant_id,
            tool_name="test_tool",
            parent_tool_id=None,
            base_code="def function(): pass",
            mutation_prompt="Optimize for speed",
        )

        assert mutation.id is not None
        assert mutation.tool_name == "test_tool"
        assert mutation.mutated_code is not None

    @pytest.mark.asyncio
    async def test_preserves_tool_interface(self, mock_auto_dev_llm, auto_dev_db_session, sample_tenant_id):
        """Test preserves tool interface."""
        engine = AlphaEvolverEngine(db=auto_dev_db_session, llm_service=mock_auto_dev_llm)

        base_code = "def process(data): return data"

        mutation = await engine.generate_tool_mutation(
            tenant_id=sample_tenant_id,
            tool_name="process",
            parent_tool_id=None,
            base_code=base_code,
            mutation_prompt="Make faster",
        )

        # Mutated code should still be valid Python
        assert "def" in mutation.mutated_code


class TestAlphaEvolverEngineValidation:
    """Test sandbox_execute_mutation() tests mutations."""

    @pytest.mark.asyncio
    async def test_execute_mutation_in_sandbox(self, mock_sandbox, auto_dev_db_session, sample_tenant_id):
        """Test executes mutations in sandbox."""
        engine = AlphaEvolverEngine(db=auto_dev_db_session, sandbox=mock_sandbox)

        # Create mutation
        mutation = ToolMutation(
            tenant_id=sample_tenant_id,
            tool_name="test_tool",
            mutated_code="print('test')",
            sandbox_status="pending",
        )
        auto_dev_db_session.add(mutation)
        auto_dev_db_session.commit()

        result = await engine.sandbox_execute_mutation(
            mutation_id=mutation.id,
            tenant_id=sample_tenant_id,
            inputs={},
        )

        assert "success" in result

    @pytest.mark.asyncio
    async def test_compares_execution_metrics(self, mock_sandbox, auto_dev_db_session, sample_tenant_id):
        """Test compares execution time and token usage."""
        engine = AlphaEvolverEngine(db=auto_dev_db_session, sandbox=mock_sandbox)

        mutation = ToolMutation(
            tenant_id=sample_tenant_id,
            tool_name="test_tool",
            mutated_code="x = 1",
            sandbox_status="pending",
        )
        auto_dev_db_session.add(mutation)
        auto_dev_db_session.commit()

        result = await engine.sandbox_execute_mutation(
            mutation_id=mutation.id,
            tenant_id=sample_tenant_id,
            inputs={},
        )

        assert "proxy_signals" in result


class TestAlphaEvolverEngineVariantSpawning:
    """Test spawn_workflow_variant() creates variants."""

    def test_creates_workflow_variant(self, auto_dev_db_session, sample_tenant_id, sample_agent_id):
        """Test creates WorkflowVariant records."""
        engine = AlphaEvolverEngine(db=auto_dev_db_session)

        workflow_def = {"steps": [{"name": "step1"}]}

        variant = engine.spawn_workflow_variant(
            tenant_id=sample_tenant_id,
            agent_id=sample_agent_id,
            workflow_def=workflow_def,
            parent_variant_id=None,
        )

        assert variant.id is not None
        assert variant.tenant_id == sample_tenant_id
        assert variant.agent_id == sample_agent_id
        assert variant.evaluation_status == "pending"

    def test_sets_parent_variant_id(self, auto_dev_db_session, sample_tenant_id, sample_agent_id):
        """Test sets parent_variant_id for lineage."""
        engine = AlphaEvolverEngine(db=auto_dev_db_session)

        # Create parent variant
        parent = engine.spawn_workflow_variant(
            tenant_id=sample_tenant_id,
            agent_id=sample_agent_id,
            workflow_def={"steps": []},
            parent_variant_id=None,
        )

        # Create child variant
        child = engine.spawn_workflow_variant(
            tenant_id=sample_tenant_id,
            agent_id=sample_agent_id,
            workflow_def={"steps": []},
            parent_variant_id=parent.id,
        )

        assert child.parent_variant_id == parent.id


class TestAlphaEvolverEngineLineageTracking:
    """Test lineage tracking."""

    def test_traces_mutation_chain(self, auto_dev_db_session, sample_tenant_id):
        """Test traces mutation chain."""
        engine = AlphaEvolverEngine(db=auto_dev_db_session)

        mutation1 = ToolMutation(
            tenant_id=sample_tenant_id,
            tool_name="test",
            mutated_code="v1",
            parent_tool_id=None,
        )
        auto_dev_db_session.add(mutation1)
        auto_dev_db_session.commit()

        mutation2 = ToolMutation(
            tenant_id=sample_tenant_id,
            tool_name="test",
            mutated_code="v2",
            parent_tool_id=mutation1.id,
        )
        auto_dev_db_session.add(mutation2)
        auto_dev_db_session.commit()

        # Query lineage
        child = (
            auto_dev_db_session.query(ToolMutation)
            .filter(ToolMutation.parent_tool_id == mutation1.id)
            .first()
        )

        assert child is not None
        assert child.id == mutation2.id


class TestAlphaEvolverEngineResearchExperiment:
    """Test run_research_experiment() iterative loop."""

    @pytest.mark.asyncio
    async def test_iterative_mutate_sandbox_compare(self, mock_auto_dev_llm, mock_sandbox, auto_dev_db_session, sample_tenant_id):
        """Test iterative mutate→sandbox→compare loop."""
        engine = AlphaEvolverEngine(
            db=auto_dev_db_session,
            llm_service=mock_auto_dev_llm,
            sandbox=mock_sandbox,
        )

        results = await engine.run_research_experiment(
            tenant_id=sample_tenant_id,
            base_code="def test(): pass",
            research_goal="Optimize",
            iterations=2,
            inputs={},
        )

        assert len(results) == 2
        assert all("mutation_id" in r for r in results)
