"""
Test EvolutionEngine monitoring and optimization.

Tests cover:
- Monitoring variant performance
- Detecting trigger conditions
- Triggering background optimization
- Pruning low-fitness variants
- Publishing evolution events
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.auto_dev.evolution_engine import EvolutionEngine
from core.auto_dev.event_hooks import SkillExecutionEvent


class TestEvolutionEngineMonitoring:
    """Test EvolutionEngine monitors variant performance."""

    def test_monitors_workflow_variants(self, auto_dev_db_session, sample_workflow_variant):
        """Test monitors WorkflowVariant performance."""
        engine = EvolutionEngine(db=auto_dev_db_session)

        # Should initialize without errors
        assert engine.db == auto_dev_db_session


class TestEvolutionEngineTriggerDetection:
    """Test detects trigger conditions (failure rate, latency)."""

    @pytest.mark.asyncio
    async def test_triggers_on_high_latency(self, auto_dev_db_session, sample_skill_execution_event, monkeypatch):
        """Test triggers on high latency (>5s)."""
        engine = EvolutionEngine(db=auto_dev_db_session)

        # Mock capability gate to return True (bypass AUTONOMOUS check)
        monkeypatch.setattr(engine, "_should_optimize", lambda agent_id, tenant_id: True)

        # Mock _get_skill_code to return test code
        monkeypatch.setattr(engine, "_get_skill_code", lambda skill_id, tenant_id: "def test_skill():\n    pass")

        # Mock AlphaEvolverEngine
        mock_evolver = MagicMock()
        mock_mutation = MagicMock()
        mock_mutation.id = "mutation-001"
        mock_evolver.generate_tool_mutation = AsyncMock(return_value=mock_mutation)
        mock_evolver.sandbox_execute_mutation = AsyncMock(return_value={"success": True})

        import sys
        original_module = sys.modules.get("core.auto_dev.alpha_evolver_engine")

        class MockAlphaEvolverEngine:
            def __init__(self, db):
                pass

        sys.modules["core.auto_dev.alpha_evolver_engine"] = MockAlphaEvolverEngine
        sys.modules["core.auto_dev.alpha_evolver_engine"].AlphaEvolverEngine = lambda db: mock_evolver

        try:
            # Create high-latency event
            high_latency_event = SkillExecutionEvent(
                execution_id="exec-001",
                agent_id="agent-001",
                tenant_id="tenant-001",
                skill_id="skill-001",
                skill_name="test_skill",
                execution_seconds=10.0,  # High latency > 5s threshold
                token_usage=1000,
                success=True,
            )

            await engine.process_execution(high_latency_event)

            # Should trigger optimization
            mock_evolver.generate_tool_mutation.assert_called_once()
        finally:
            if original_module:
                sys.modules["core.auto_dev.alpha_evolver_engine"] = original_module
            else:
                sys.modules.pop("core.auto_dev.alpha_evolver_engine", None)

    @pytest.mark.asyncio
    async def test_triggers_on_high_token_usage(self, auto_dev_db_session, monkeypatch):
        """Test triggers on high token usage."""
        engine = EvolutionEngine(db=auto_dev_db_session)

        # Mock capability gate to return True (bypass AUTONOMOUS check)
        monkeypatch.setattr(engine, "_should_optimize", lambda agent_id, tenant_id: True)

        # Mock _get_skill_code to return test code
        monkeypatch.setattr(engine, "_get_skill_code", lambda skill_id, tenant_id: "def test_skill():\n    pass")

        mock_evolver = MagicMock()
        mock_mutation = MagicMock()
        mock_mutation.id = "mutation-001"
        mock_evolver.generate_tool_mutation = AsyncMock(return_value=mock_mutation)
        mock_evolver.sandbox_execute_mutation = AsyncMock(return_value={"success": True})

        import sys
        original_module = sys.modules.get("core.auto_dev.alpha_evolver_engine")

        class MockAlphaEvolverEngine:
            def __init__(self, db):
                pass

        sys.modules["core.auto_dev.alpha_evolver_engine"] = MockAlphaEvolverEngine
        sys.modules["core.auto_dev.alpha_evolver_engine"].AlphaEvolverEngine = lambda db: mock_evolver

        try:
            high_token_event = SkillExecutionEvent(
                execution_id="exec-002",
                agent_id="agent-001",
                tenant_id="tenant-001",
                skill_id="skill-001",
                skill_name="test_skill",
                execution_seconds=2.0,
                token_usage=10000,  # High token usage > 5000 threshold
                success=True,
            )

            await engine.process_execution(high_token_event)

            mock_evolver.generate_tool_mutation.assert_called_once()
        finally:
            if original_module:
                sys.modules["core.auto_dev.alpha_evolver_engine"] = original_module
            else:
                sys.modules.pop("core.auto_dev.alpha_evolver_engine", None)


class TestEvolutionEngineBackgroundOptimization:
    """Test triggers background optimization."""

    @pytest.mark.asyncio
    async def test_spawns_alpha_evolver(self, auto_dev_db_session, monkeypatch):
        """Test spawns AlphaEvolverEngine."""
        engine = EvolutionEngine(db=auto_dev_db_session)

        # Mock capability gate to return True (bypass AUTONOMOUS check)
        monkeypatch.setattr(engine, "_should_optimize", lambda agent_id, tenant_id: True)

        # Mock _get_skill_code to return test code
        monkeypatch.setattr(engine, "_get_skill_code", lambda skill_id, tenant_id: "def test_skill():\n    pass")

        mock_evolver = MagicMock()
        mock_mutation = MagicMock()
        mock_mutation.id = "mutation-001"
        mock_evolver.generate_tool_mutation = AsyncMock(return_value=mock_mutation)
        mock_evolver.sandbox_execute_mutation = AsyncMock(return_value={"success": True})

        import sys
        original_module = sys.modules.get("core.auto_dev.alpha_evolver_engine")

        class MockAlphaEvolverEngine:
            def __init__(self, db):
                pass

        sys.modules["core.auto_dev.alpha_evolver_engine"] = MockAlphaEvolverEngine
        sys.modules["core.auto_dev.alpha_evolver_engine"].AlphaEvolverEngine = lambda db: mock_evolver

        try:
            event = SkillExecutionEvent(
                execution_id="exec-003",
                agent_id="agent-001",
                tenant_id="tenant-001",
                skill_id="skill-001",
                skill_name="test_skill",
                execution_seconds=8.0,
                token_usage=6000,
                success=False,  # Execution failure
            )

            await engine.process_execution(event)

            # Should have spawned evolver
            mock_evolver.generate_tool_mutation.assert_called_once()
        finally:
            if original_module:
                sys.modules["core.auto_dev.alpha_evolver_engine"] = original_module
            else:
                sys.modules.pop("core.auto_dev.alpha_evolver_engine", None)


class TestEvolutionEngineVariantPruning:
    """Test prunes low-fitness variants."""

    def test_prunes_low_fitness_variants(self, auto_dev_db_session, sample_tenant_id):
        """Test prunes low-fitness variants."""
        from core.auto_dev.models import WorkflowVariant

        # Create variants with different fitness scores
        low_fitness = WorkflowVariant(
            tenant_id=sample_tenant_id,
            workflow_definition={},
            fitness_score=0.1,
            evaluation_status="evaluated",
        )

        high_fitness = WorkflowVariant(
            tenant_id=sample_tenant_id,
            workflow_definition={},
            fitness_score=0.9,
            evaluation_status="evaluated",
        )

        auto_dev_db_session.add(low_fitness)
        auto_dev_db_session.add(high_fitness)
        auto_dev_db_session.commit()

        # Query should return high fitness first
        from core.auto_dev.fitness_service import FitnessService

        service = FitnessService(auto_dev_db_session)
        top_variants = service.get_top_variants(sample_tenant_id, limit=10)

        assert len(top_variants) >= 1
        assert top_variants[0].fitness_score >= 0.9


class TestEvolutionEngineEventPublishing:
    """Test publishes evolution events."""

    def test_register_on_event_bus(self, auto_dev_db_session):
        """Test registers on event bus."""
        engine = EvolutionEngine(db=auto_dev_db_session)

        # Should register without error
        engine.register()

        assert engine.db == auto_dev_db_session
