"""Coverage-push tests (part 1) for Auto-Dev modules.

Targets: advisor_service, alpha_evolver_engine, capability_gate,
container_sandbox, evolution_engine, evolution_pipeline, fitness_service.
"""

import asyncio
import sys
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auto_dev.models import SkillCandidate, ToolMutation, WorkflowVariant


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.database import Base

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db(db_engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _empty_module(name: str) -> types.ModuleType:
    return types.ModuleType(name)


# =============================================================================
# AdvisorService
# =============================================================================


class TestAdvisorServiceCoverage:
    def test_generate_guidance_no_data(self, db):
        from core.auto_dev.advisor_service import AdvisorService

        result = asyncio.run(
            AdvisorService(db).generate_guidance(tenant_id="t-empty")
        )
        assert result["status"] == "success"
        assert result["readiness_score"] == 0

    def test_heuristic_guidance_without_llm(self, db):
        from core.auto_dev.advisor_service import AdvisorService

        db.add(ToolMutation(
            tenant_id="t1", tool_name="tool", mutated_code="code",
            sandbox_status="passed",
        ))
        db.add(WorkflowVariant(
            tenant_id="t1", workflow_definition={}, fitness_score=0.8,
            evaluation_status="evaluated",
        ))
        db.commit()

        result = asyncio.run(
            AdvisorService(db, llm_service=None).generate_guidance(tenant_id="t1")
        )
        assert result["data_summary"]["num_mutations"] == 1
        assert result["data_summary"]["top_fitness_score"] == 0.8
        assert result["data_summary"]["avg_fitness_score"] == 0.8
        assert result["readiness_score"] == 20
        assert "Strong results" in result["message"]

    def test_ai_guidance_uses_llm_content(self, db):
        from core.auto_dev.advisor_service import AdvisorService

        db.add(ToolMutation(
            tenant_id="t-ai", tool_name="tool", mutated_code="code",
            sandbox_status="passed",
        ))
        db.add(WorkflowVariant(
            tenant_id="t-ai", workflow_definition={}, fitness_score=0.6,
            evaluation_status="evaluated",
        ))
        db.commit()

        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={"content": "AI advice"})
        result = asyncio.run(
            AdvisorService(db, llm_service=llm).generate_guidance(tenant_id="t-ai")
        )
        assert result["message"] == "AI advice"

    def test_ai_guidance_llm_error_falls_back(self, db):
        from core.auto_dev.advisor_service import AdvisorService

        db.add(ToolMutation(
            tenant_id="t-err", tool_name="tool", mutated_code="code",
            sandbox_status="failed",
        ))
        db.add(WorkflowVariant(
            tenant_id="t-err", workflow_definition={}, fitness_score=0.1,
            evaluation_status="evaluated",
        ))
        db.commit()

        llm = MagicMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("boom"))
        result = asyncio.run(
            AdvisorService(db, llm_service=llm).generate_guidance(tenant_id="t-err")
        )
        assert result["message"].startswith("High failure rate")

    def test_ai_guidance_missing_content_key(self, db):
        from core.auto_dev.advisor_service import AdvisorService

        db.add(ToolMutation(
            tenant_id="t-miss", tool_name="tool", mutated_code="code",
            sandbox_status="passed",
        ))
        db.add(WorkflowVariant(
            tenant_id="t-miss", workflow_definition={}, fitness_score=0.6,
            evaluation_status="evaluated",
        ))
        db.commit()

        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={"tokens": 5})
        result = asyncio.run(
            AdvisorService(db, llm_service=llm).generate_guidance(tenant_id="t-miss")
        )
        assert result["message"] == (
            "Evolution is progressing. Continue monitoring signals."
        )

    def test_heuristic_moderate_progress(self):
        from core.auto_dev.advisor_service import AdvisorService

        svc = AdvisorService(db=MagicMock())
        msg = svc._generate_heuristic_guidance({
            "num_mutations": 10, "passed_mutations": 5,
            "failed_mutations": 5, "avg_fitness_score": 0.4,
        })
        assert msg.startswith("Moderate progress")

    def test_heuristic_high_failure_rate(self):
        from core.auto_dev.advisor_service import AdvisorService

        svc = AdvisorService(db=MagicMock())
        msg = svc._generate_heuristic_guidance({
            "num_mutations": 10, "passed_mutations": 2,
            "failed_mutations": 8, "avg_fitness_score": 0.2,
        })
        assert msg.startswith("High failure rate")

    def test_heuristic_zero_total(self):
        from core.auto_dev.advisor_service import AdvisorService

        svc = AdvisorService(db=MagicMock())
        msg = svc._generate_heuristic_guidance({
            "num_mutations": 0, "passed_mutations": 0,
            "failed_mutations": 0, "avg_fitness_score": 0.0,
        })
        assert "first evolution cycle" in msg

    def test_get_llm_service_resolves(self, monkeypatch):
        from core.auto_dev.advisor_service import AdvisorService

        fake_llm = object()
        monkeypatch.setattr("core.llm_service.get_llm_service", lambda: fake_llm)
        assert AdvisorService(db=MagicMock())._get_llm_service() is fake_llm


# =============================================================================
# AlphaEvolverEngine
# =============================================================================


def _make_alpha_engine(db, **kwargs):
    from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine

    return AlphaEvolverEngine(db=db, **kwargs)


class TestAlphaEvolverEngineCoverage:
    def test_analyze_episode_not_found(self, db):
        engine = _make_alpha_engine(db)
        result = asyncio.run(engine.analyze_episode("no-such-episode"))
        assert "error" in result

    def test_analyze_episode_import_error(self, db, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.models", _empty_module("core.models"))
        engine = _make_alpha_engine(db)
        result = asyncio.run(engine.analyze_episode("ep-1"))
        assert result["error"] == "Episode models not available"

    def test_analyze_episode_success_with_segments(self, db):
        from core.models import AgentEpisode, EpisodeSegment

        db.add(AgentEpisode(
            id="ep-alpha-1", agent_id="ag-1", tenant_id="t-1",
            task_description="Process invoices", maturity_at_time="autonomous",
            outcome="success", success=True, status="active",
            metadata_json={"duration": 4.2},
        ))
        db.add(EpisodeSegment(
            id="seg-1", episode_id="ep-alpha-1", segment_type="execution",
            sequence_order=1, content="did stuff",
            canvas_context={"execution_seconds": 6.0, "retry_count": 1},
        ))
        db.add(EpisodeSegment(
            id="seg-2", episode_id="ep-alpha-1", segment_type="execution",
            sequence_order=2, content="did more",
        ))
        db.commit()

        engine = _make_alpha_engine(db)
        result = asyncio.run(engine.analyze_episode("ep-alpha-1"))
        assert result["success"] is True
        assert result["total_segments"] == 2
        assert result["optimization_targets"][0]["reason"] == "high_latency"
        assert result["optimization_targets"][1]["reason"] == "retries"

    def test_propose_code_change_no_llm(self, db):
        engine = _make_alpha_engine(db)
        engine._get_llm_service = Mock(return_value=None)
        code = asyncio.run(engine.propose_code_change(
            {"base_code": "def f(): pass", "mutation_prompt": "go"}
        ))
        assert "# Mutation skipped" in code

    def test_propose_code_change_llm_error(self, db):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        engine = _make_alpha_engine(db, llm_service=llm)
        code = asyncio.run(engine.propose_code_change(
            {"base_code": "def f(): pass", "mutation_prompt": "go"}
        ))
        assert "# Mutation failed" in code

    def test_propose_code_change_strips_fences(self, db):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(
            return_value={"content": "```python\ndef f():\n    return 1\n```"}
        )
        engine = _make_alpha_engine(db, llm_service=llm)
        code = asyncio.run(engine.propose_code_change(
            {"base_code": "old", "mutation_prompt": "go"}
        ))
        assert code == "def f():\n    return 1"

    def test_validate_change_no_sandbox(self, db):
        engine = _make_alpha_engine(db)
        engine._get_sandbox = Mock(return_value=None)
        result = asyncio.run(engine.validate_change("code", [{}], "t-1"))
        assert result == {"passed": False, "error": "Sandbox unavailable"}

    def test_validate_change_sandbox_failure(self, db):
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "failed", "output": "RuntimeError",
                          "execution_seconds": 0.5}
        )
        engine = _make_alpha_engine(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_change(
            "bad code", [{"x": 1}, {"x": 2}], "t-1"
        ))
        assert result["passed"] is False
        assert result["proxy_signals"]["execution_success"] is False

    def test_validate_change_regression_reject(self, db):
        sandbox = MagicMock()

        async def exec_raw(tenant_id, code, input_params, **kwargs):
            if code.startswith("PARENT"):
                return {"status": "success", "output": "OUTPUT-A",
                        "execution_seconds": 0.1}
            return {"status": "success", "output": "OUTPUT-B",
                    "execution_seconds": 0.1}

        sandbox.execute_raw_python = AsyncMock(side_effect=exec_raw)
        engine = _make_alpha_engine(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_change(
            "CHILD code", [{"x": 1}], "t-1", parent_code="PARENT code"
        ))
        assert result["passed"] is False
        assert result["regression_result"]["mismatch_count"] == 1

    def test_validate_change_regression_validator_error_continues(self, db, monkeypatch):
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "success", "output": "same",
                          "execution_seconds": 0.1}
        )

        class BrokenValidator:
            def __init__(self, *a, **kw):
                raise RuntimeError("validator init failed")

        monkeypatch.setattr(
            "core.auto_dev.regression_validator.RegressionValidator",
            BrokenValidator,
        )
        engine = _make_alpha_engine(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_change(
            "child", [{"x": 1}], "t-1", parent_code="parent"
        ))
        assert result["passed"] is True

    def test_validate_change_passes_with_parent(self, db):
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "success", "output": "same output",
                          "execution_seconds": 0.1}
        )
        engine = _make_alpha_engine(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_change(
            "child", [{"x": 1}, {"x": 2}], "t-1", parent_code="parent"
        ))
        assert result["passed"] is True
        assert result["proxy_signals"]["pass_rate"] == 1.0

    def test_generate_tool_mutation_persists(self, db):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(
            return_value={"content": "def new(): return 42"}
        )
        engine = _make_alpha_engine(db, llm_service=llm)
        mutation = asyncio.run(engine.generate_tool_mutation(
            tenant_id="t-1", tool_name="my_tool", parent_tool_id="parent-1",
            base_code="old", mutation_prompt="optimize",
        ))
        assert mutation.sandbox_status == "pending"
        assert mutation.parent_tool_id == "parent-1"
        assert mutation.mutated_code == "def new(): return 42"
        assert db.query(ToolMutation).filter(
            ToolMutation.tenant_id == "t-1"
        ).count() == 1

    def test_sandbox_execute_mutation_not_found(self, db):
        engine = _make_alpha_engine(db)
        result = asyncio.run(engine.sandbox_execute_mutation(
            "missing-mutation", "t-1", {}
        ))
        assert "error" in result

    def test_sandbox_execute_mutation_no_sandbox(self, db):
        db.add(ToolMutation(
            id="m-exec-1", tenant_id="t-1", tool_name="t", mutated_code="code"
        ))
        db.commit()
        engine = _make_alpha_engine(db)
        engine._get_sandbox = Mock(return_value=None)
        result = asyncio.run(engine.sandbox_execute_mutation("m-exec-1", "t-1", {}))
        assert result == {"error": "Sandbox unavailable"}

    def test_sandbox_execute_mutation_passed(self, db):
        db.add(ToolMutation(
            id="m-exec-2", tenant_id="t-1", tool_name="t", mutated_code="code"
        ))
        db.commit()
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "success", "output": "ok",
                          "execution_seconds": 1.5, "environment": "mock"}
        )
        engine = _make_alpha_engine(db, sandbox=sandbox)
        result = asyncio.run(engine.sandbox_execute_mutation("m-exec-2", "t-1", {}))
        assert result["success"] is True
        assert result["proxy_signals"]["execution_latency_ms"] == 1500.0
        assert db.query(ToolMutation).get("m-exec-2").sandbox_status == "passed"

    def test_sandbox_execute_mutation_failed_syntax(self, db):
        db.add(ToolMutation(
            id="m-exec-3", tenant_id="t-1", tool_name="t", mutated_code="code"
        ))
        db.commit()
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "failed",
                          "output": "SyntaxError: invalid syntax",
                          "execution_seconds": 0.2}
        )
        engine = _make_alpha_engine(db, sandbox=sandbox)
        result = asyncio.run(engine.sandbox_execute_mutation("m-exec-3", "t-1", {}))
        assert result["success"] is False
        assert result["proxy_signals"]["syntax_error"] is True
        assert db.query(ToolMutation).get("m-exec-3").sandbox_status == "failed"

    def test_spawn_workflow_variant(self, db):
        engine = _make_alpha_engine(db)
        variant = engine.spawn_workflow_variant(
            tenant_id="t-1", agent_id="ag-1", workflow_def={"steps": []},
            parent_variant_id="pv-1",
        )
        assert variant.parent_variant_id == "pv-1"
        assert variant.evaluation_status == "pending"

    def test_check_auto_synthesis_readiness(self, db):
        db.add_all([
            ToolMutation(tenant_id="t-1", tool_name="synth",
                         mutated_code="a", sandbox_status="passed"),
            ToolMutation(tenant_id="t-1", tool_name="synth",
                         mutated_code="b", sandbox_status="passed"),
            ToolMutation(tenant_id="t-1", tool_name="synth",
                         mutated_code="c", sandbox_status="failed"),
        ])
        db.commit()
        engine = _make_alpha_engine(db)
        assert engine.check_auto_synthesis_readiness("t-1", "synth", threshold=2) is True
        assert engine.check_auto_synthesis_readiness("t-1", "synth", threshold=5) is False

    def test_run_research_experiment_promotes_winner(self, db):
        engine = _make_alpha_engine(db)
        calls = {"n": 0}

        async def fake_mutation(tenant_id, tool_name, parent_tool_id,
                                base_code, mutation_prompt):
            calls["n"] += 1
            return ToolMutation(
                id=f"rm-{calls['n']}", tenant_id=tenant_id, tool_name=tool_name,
                mutated_code=f"def v{calls['n']}():\n    return {calls['n']}",
            )

        async def fake_exec(mutation_id, tenant_id, inputs):
            return {"success": True, "output": f"result-{mutation_id}"}

        engine.generate_tool_mutation = AsyncMock(side_effect=fake_mutation)
        engine.sandbox_execute_mutation = AsyncMock(side_effect=fake_exec)

        results = asyncio.run(engine.run_research_experiment(
            tenant_id="t-1", base_code="def v0():\n    return 0",
            research_goal="go", iterations=2,
        ))
        assert len(results) == 2
        assert results[0]["success"] is True
        assert "code_preview" in results[0]

    def test_run_research_experiment_no_promote_on_empty_output(self, db):
        engine = _make_alpha_engine(db)
        calls = {"n": 0}

        async def fake_mutation(tenant_id, tool_name, parent_tool_id,
                                base_code, mutation_prompt):
            calls["n"] += 1
            return ToolMutation(
                id=f"rn-{calls['n']}", tenant_id=tenant_id, tool_name=tool_name,
                mutated_code=f"def v{calls['n']}():\n    return {calls['n']}",
            )

        async def fake_exec(mutation_id, tenant_id, inputs):
            return {"success": True, "output": ""}

        engine.generate_tool_mutation = AsyncMock(side_effect=fake_mutation)
        engine.sandbox_execute_mutation = AsyncMock(side_effect=fake_exec)
        results = asyncio.run(engine.run_research_experiment(
            tenant_id="t-1", base_code="base", research_goal="go", iterations=1,
        ))
        assert results[0]["success"] is True

    def test_run_arbor_experiment_success_path(self, db):
        engine = _make_alpha_engine(db)

        async def fake_mutation(tenant_id, tool_name, parent_tool_id,
                                base_code, mutation_prompt):
            return ToolMutation(
                id="arbor-1", tenant_id=tenant_id, tool_name=tool_name,
                mutated_code="def winner():\n    return 1",
            )

        async def fake_exec(mutation_id, tenant_id, inputs):
            return {"success": True, "output": "good",
                    "proxy_signals": {"execution_latency_ms": 200.0}}

        engine.generate_tool_mutation = AsyncMock(side_effect=fake_mutation)
        engine.sandbox_execute_mutation = AsyncMock(side_effect=fake_exec)

        result = asyncio.run(engine.run_arbor_experiment(
            tenant_id="t-1", base_code="base", research_goal="improve",
            iterations=2,
        ))
        assert result["winning_node_id"] is not None
        assert len(result["iterations"]) == 2
        assert result["tree"]["total_nodes"] == 2
        assert result["tree"]["winning_path"]

    def test_run_arbor_experiment_lint_failure_pruned(self, db):
        engine = _make_alpha_engine(db)

        async def fake_mutation(tenant_id, tool_name, parent_tool_id,
                                base_code, mutation_prompt):
            return ToolMutation(
                id="arbor-lint", tenant_id=tenant_id, tool_name=tool_name,
                mutated_code="def broken(:",
            )

        async def fake_exec(mutation_id, tenant_id, inputs):
            return {"success": True}

        engine.generate_tool_mutation = AsyncMock(side_effect=fake_mutation)
        engine.sandbox_execute_mutation = AsyncMock(side_effect=fake_exec)

        result = asyncio.run(engine.run_arbor_experiment(
            tenant_id="t-1", base_code="base", research_goal="improve",
            iterations=1,
        ))
        assert result["iterations"][0]["pruned"] is True
        assert result["iterations"][0]["prune_reason"] == "lint_failed"
        assert result["winning_node_id"] is None

    def test_run_arbor_experiment_sandbox_failure_pruned(self, db):
        engine = _make_alpha_engine(db)

        async def fake_mutation(tenant_id, tool_name, parent_tool_id,
                                base_code, mutation_prompt):
            return ToolMutation(
                id="arbor-fail", tenant_id=tenant_id, tool_name=tool_name,
                mutated_code="def x():\n    return 1",
            )

        async def fake_exec(mutation_id, tenant_id, inputs):
            return {"success": False, "output": "crash",
                    "proxy_signals": {"execution_latency_ms": 100.0}}

        engine.generate_tool_mutation = AsyncMock(side_effect=fake_mutation)
        engine.sandbox_execute_mutation = AsyncMock(side_effect=fake_exec)

        result = asyncio.run(engine.run_arbor_experiment(
            tenant_id="t-1", base_code="base", research_goal="improve",
            iterations=1,
        ))
        assert result["iterations"][0]["pruned"] is True
        assert result["iterations"][0]["prune_reason"] == "test_failed"
        assert result["winning_node_id"] is None

    def test_compute_proxy_signals_empty(self):
        from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine

        signals = AlphaEvolverEngine._compute_proxy_signals([])
        assert signals == {
            "execution_success": True,
            "pass_rate": 0,
            "avg_execution_seconds": 0,
            "syntax_error": False,
        }

    def test_compute_proxy_signals_mixed(self):
        from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine

        signals = AlphaEvolverEngine._compute_proxy_signals([
            {"passed": True, "execution_seconds": 1.0, "output": "ok"},
            {"passed": False, "execution_seconds": 2.0,
             "output": "SyntaxError: bad"},
        ])
        assert signals["pass_rate"] == 0.5
        assert signals["syntax_error"] is True
        assert signals["avg_execution_seconds"] == 1.5


# =============================================================================
# CapabilityGate
# =============================================================================


class TestCapabilityGateCoverage:
    def test_is_at_least_invalid_levels(self):
        from core.auto_dev.capability_gate import is_at_least

        assert is_at_least("god_mode", "intern") is False
        assert is_at_least("intern", "transcendent") is False

    def test_is_at_least_ordering(self):
        from core.auto_dev.capability_gate import is_at_least

        assert is_at_least("autonomous", "student") is True
        assert is_at_least("intern", "supervised") is False

    def test_graduation_property_import_error(self, db, monkeypatch):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        monkeypatch.setitem(
            sys.modules, "core.capability_graduation_service",
            _empty_module("core.capability_graduation_service"),
        )
        svc = AutoDevCapabilityService(db)
        assert svc.graduation is None

    def test_graduation_property_resolves(self, db, monkeypatch):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        fake_graduation = MagicMock()
        monkeypatch.setattr(
            "core.capability_graduation_service.CapabilityGraduationService",
            lambda session: fake_graduation,
        )
        svc = AutoDevCapabilityService(db)
        assert svc.graduation is fake_graduation

    def test_can_use_workspace_disabled(self, db):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        svc = AutoDevCapabilityService(db)
        assert svc.can_use(
            "ag-1", "auto_dev.memento_skills",
            {"auto_dev": {"enabled": False}},
        ) is False

    def test_can_use_capability_toggle_off(self, db):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        svc = AutoDevCapabilityService(db)
        assert svc.can_use(
            "ag-1", "auto_dev.memento_skills",
            {"auto_dev": {"enabled": True, "memento_skills": False}},
        ) is False

    def test_can_use_unknown_capability(self, db):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        svc = AutoDevCapabilityService(db)
        assert svc.can_use(
            "ag-1", "auto_dev.fancy_feature", {"auto_dev": {"enabled": True}},
        ) is False

    def test_can_use_maturity_gate(self, db, monkeypatch):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        fake_graduation = MagicMock()
        fake_graduation.get_maturity.return_value = "intern"
        monkeypatch.setattr(
            "core.capability_graduation_service.CapabilityGraduationService",
            lambda session: fake_graduation,
        )
        svc = AutoDevCapabilityService(db)
        settings = {"auto_dev": {"enabled": True}}
        assert svc.can_use("ag-1", "auto_dev.memento_skills", settings) is True
        assert svc.can_use("ag-1", "auto_dev.alpha_evolver", settings) is False

    def test_record_usage_error_swallowed(self, db, monkeypatch):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        fake_graduation = MagicMock()
        fake_graduation.record_usage.side_effect = RuntimeError("boom")
        monkeypatch.setattr(
            "core.capability_graduation_service.CapabilityGraduationService",
            lambda session: fake_graduation,
        )
        svc = AutoDevCapabilityService(db)
        svc.record_usage("ag-1", "auto_dev.memento_skills", True)

    def test_record_usage_without_graduation(self, db, monkeypatch):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        monkeypatch.setitem(
            sys.modules, "core.capability_graduation_service",
            _empty_module("core.capability_graduation_service"),
        )
        svc = AutoDevCapabilityService(db)
        svc.record_usage("ag-1", "auto_dev.memento_skills", True)

    def test_check_daily_limits_other_capability(self, db):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        svc = AutoDevCapabilityService(db)
        assert svc.check_daily_limits("ag-1", "auto_dev.background_evolution") is True

    def test_check_daily_limits_alpha_within(self, db):
        from core.models import AgentRegistry
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        db.add(AgentRegistry(
            id="ag-lim-1", name="A", category="ops", module_path="m",
            class_name="C", tenant_id="t-lim-1",
            updated_at=datetime.now(timezone.utc),
        ))
        db.add(ToolMutation(tenant_id="t-lim-1", tool_name="t", mutated_code="c"))
        db.commit()

        svc = AutoDevCapabilityService(db)
        assert svc.check_daily_limits(
            "ag-lim-1", "auto_dev.alpha_evolver",
            {"auto_dev": {"max_mutations_per_day": 10}},
        ) is True
        assert svc.check_daily_limits(
            "ag-lim-1", "auto_dev.alpha_evolver",
            {"auto_dev": {"max_mutations_per_day": 0}},
        ) is False

    def test_check_daily_limits_memento_within(self, db):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        db.add(SkillCandidate(
            tenant_id="t-lim-2", agent_id="ag-lim-2", skill_name="s",
            generated_code="c",
        ))
        db.commit()

        svc = AutoDevCapabilityService(db)
        assert svc.check_daily_limits(
            "ag-lim-2", "auto_dev.memento_skills",
            {"auto_dev": {"max_skill_candidates_per_day": 5}},
        ) is True

    def test_check_daily_limits_error_fail_closed(self):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        broken_db = MagicMock()
        broken_db.query.side_effect = RuntimeError("db down")
        svc = AutoDevCapabilityService(broken_db)
        assert svc.check_daily_limits("ag-1", "auto_dev.alpha_evolver") is False

    def test_notify_capability_unlocked(self):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        payload = AutoDevCapabilityService(MagicMock()).notify_capability_unlocked(
            "ag-1", "auto_dev.memento_skills"
        )
        assert payload["type"] == "auto_dev_capability_unlocked"
        assert payload["agent_id"] == "ag-1"
        assert payload["action_required"] is True

    def test_get_agent_tenant_not_found(self, db):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        svc = AutoDevCapabilityService(db)
        assert svc._get_agent_tenant("no-such-agent") is None

    def test_get_agent_tenant_found(self, db):
        from core.models import AgentRegistry
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        db.add(AgentRegistry(
            id="ag-tenant-1", name="A", category="ops", module_path="m",
            class_name="C", tenant_id="t-tenant-1",
            updated_at=datetime.now(timezone.utc),
        ))
        db.commit()
        svc = AutoDevCapabilityService(db)
        assert svc._get_agent_tenant("ag-tenant-1") == "t-tenant-1"

    def test_get_agent_tenant_exception(self, db, monkeypatch):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        monkeypatch.setitem(sys.modules, "core.models", _empty_module("core.models"))
        svc = AutoDevCapabilityService(db)
        assert svc._get_agent_tenant("ag-1") is None


# =============================================================================
# ContainerSandbox
# =============================================================================


class TestContainerSandboxCoverage:
    def test_docker_available_file_not_found(self, monkeypatch):
        from core.auto_dev.container_sandbox import ContainerSandbox

        monkeypatch.setattr(
            "core.auto_dev.container_sandbox.subprocess.run",
            Mock(side_effect=FileNotFoundError("no docker")),
        )
        sandbox = ContainerSandbox()
        assert sandbox.docker_available is False
        assert sandbox._docker_available is False

    def test_docker_available_timeout(self, monkeypatch):
        from core.auto_dev.container_sandbox import ContainerSandbox

        import subprocess

        monkeypatch.setattr(
            "core.auto_dev.container_sandbox.subprocess.run",
            Mock(side_effect=subprocess.TimeoutExpired("docker info", 5)),
        )
        sandbox = ContainerSandbox()
        assert sandbox.docker_available is False

    def test_docker_available_true(self, monkeypatch):
        from core.auto_dev.container_sandbox import ContainerSandbox

        proc = Mock()
        proc.returncode = 0
        monkeypatch.setattr(
            "core.auto_dev.container_sandbox.subprocess.run",
            Mock(return_value=proc),
        )
        sandbox = ContainerSandbox()
        assert sandbox.docker_available is True

    def test_execute_docker_success(self, monkeypatch):
        from core.auto_dev.container_sandbox import ContainerSandbox

        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"hello world", b""))
        monkeypatch.setattr(
            "core.auto_dev.container_sandbox.asyncio.create_subprocess_exec",
            AsyncMock(return_value=proc),
        )
        sandbox = ContainerSandbox()
        sandbox._docker_available = True
        result = asyncio.run(sandbox.execute_raw_python("t-1", "print('hi')", {}))
        assert result["status"] == "success"
        assert result["output"] == "hello world"
        assert result["environment"] == "docker"

    def test_execute_docker_failure(self, monkeypatch):
        from core.auto_dev.container_sandbox import ContainerSandbox

        proc = AsyncMock()
        proc.returncode = 1
        proc.communicate = AsyncMock(
            return_value=(b"", b"NameError: name 'x' is not defined")
        )
        monkeypatch.setattr(
            "core.auto_dev.container_sandbox.asyncio.create_subprocess_exec",
            AsyncMock(return_value=proc),
        )
        sandbox = ContainerSandbox()
        sandbox._docker_available = True
        result = asyncio.run(sandbox.execute_raw_python("t-1", "raise", {}))
        assert result["status"] == "failed"
        assert "NameError" in result["output"]

    def test_execute_docker_timeout(self, monkeypatch):
        from core.auto_dev.container_sandbox import ContainerSandbox

        proc = AsyncMock()
        proc.kill = Mock()
        proc.wait = AsyncMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        monkeypatch.setattr(
            "core.auto_dev.container_sandbox.asyncio.create_subprocess_exec",
            AsyncMock(return_value=proc),
        )
        sandbox = ContainerSandbox(timeout=2)
        sandbox._docker_available = True
        result = asyncio.run(sandbox.execute_raw_python("t-1", "sleep", {}))
        assert result["status"] == "failed"
        assert "timed out" in result["output"]
        proc.kill.assert_called_once()

    def test_execute_subprocess_timeout(self, monkeypatch):
        from core.auto_dev.container_sandbox import ContainerSandbox

        proc = AsyncMock()
        proc.kill = Mock()
        proc.wait = AsyncMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        monkeypatch.setattr(
            "core.auto_dev.container_sandbox.asyncio.create_subprocess_exec",
            AsyncMock(return_value=proc),
        )
        sandbox = ContainerSandbox(timeout=2)
        sandbox._docker_available = False
        result = asyncio.run(sandbox.execute_raw_python("t-1", "sleep", {}))
        assert result["environment"] == "subprocess"
        assert result["status"] == "failed"

    def test_execution_wrapper_round_trip(self):
        from core.auto_dev.container_sandbox import ContainerSandbox

        params = {"key": "val with 'quotes'"}
        wrapper = ContainerSandbox._build_execution_wrapper(
            "print(_INPUT_PARAMS['key'])", params
        )
        assert "_b64.b64decode" in wrapper
        assert "val with 'quotes'" not in wrapper
        assert "_INPUT_PARAMS" in wrapper

    def test_execute_with_timeout_override(self, monkeypatch):
        from core.auto_dev.container_sandbox import ContainerSandbox

        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"ok", b""))
        monkeypatch.setattr(
            "core.auto_dev.container_sandbox.asyncio.create_subprocess_exec",
            AsyncMock(return_value=proc),
        )
        sandbox = ContainerSandbox()
        sandbox._docker_available = True
        result = asyncio.run(
            sandbox.execute_raw_python("t-1", "print(1)", {}, timeout=30)
        )
        assert result["status"] == "success"


# =============================================================================
# EvolutionEngine
# =============================================================================


class TestEvolutionEngineCoverage:
    def test_process_execution_gate_blocks(self, db):
        from core.auto_dev.event_hooks import SkillExecutionEvent
        from core.auto_dev.evolution_engine import EvolutionEngine

        gate = MagicMock()
        gate.can_use.return_value = False
        engine = EvolutionEngine(db)
        engine._get_workspace_settings = Mock(return_value={})
        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService",
            return_value=gate,
        ):
            event = SkillExecutionEvent(
                execution_id="e1", agent_id="ag-1", tenant_id="t-1",
                skill_id="s-1", execution_seconds=10.0, token_usage=9000,
                success=False,
            )
            asyncio.run(engine.process_execution(event))

    def test_process_execution_no_trigger(self, db):
        from core.auto_dev.event_hooks import SkillExecutionEvent
        from core.auto_dev.evolution_engine import EvolutionEngine

        gate = MagicMock()
        gate.can_use.return_value = True
        engine = EvolutionEngine(db)
        engine._get_workspace_settings = Mock(return_value={})
        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService",
            return_value=gate,
        ):
            event = SkillExecutionEvent(
                execution_id="e2", agent_id="ag-1", tenant_id="t-1",
                skill_id="s-1", execution_seconds=1.0, token_usage=10,
                success=True,
            )
            asyncio.run(engine.process_execution(event))

    def test_process_execution_trigger_full(self, db):
        from core.auto_dev.event_hooks import SkillExecutionEvent
        from core.auto_dev.evolution_engine import EvolutionEngine

        gate = MagicMock()
        gate.can_use.return_value = True
        fake_session = MagicMock()

        class FakeAlphaEvolver:
            def __init__(self, db):
                self.db = db

            async def generate_tool_mutation(self, **kwargs):
                return MagicMock(id="mut-1")

            async def sandbox_execute_mutation(self, **kwargs):
                return {"success": True, "output": "ok"}

        engine = EvolutionEngine(db)
        engine._get_workspace_settings = Mock(return_value={})
        engine._get_skill_code = Mock(return_value="def s():\n    return 1")
        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService",
            return_value=gate,
        ), patch(
            "core.database.SessionLocal", return_value=fake_session,
        ), patch(
            "core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine",
            FakeAlphaEvolver,
        ):
            event = SkillExecutionEvent(
                execution_id="e3", agent_id="ag-1", tenant_id="t-1",
                skill_id="s-1", skill_name="my_skill", execution_seconds=6.5,
                token_usage=6000, success=False,
            )
            asyncio.run(engine.process_execution(event))

    def test_trigger_alpha_evolver_sandbox_failure(self, db):
        from core.auto_dev.event_hooks import SkillExecutionEvent
        from core.auto_dev.evolution_engine import EvolutionEngine

        fake_session = MagicMock()

        class FakeAlphaEvolver:
            def __init__(self, db):
                self.db = db

            async def generate_tool_mutation(self, **kwargs):
                return MagicMock(id="mut-2")

            async def sandbox_execute_mutation(self, **kwargs):
                return {"success": False, "output": "crash"}

        engine = EvolutionEngine(db)
        engine._get_skill_code = Mock(return_value="code")
        with patch(
            "core.database.SessionLocal", return_value=fake_session,
        ), patch(
            "core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine",
            FakeAlphaEvolver,
        ):
            event = SkillExecutionEvent(
                execution_id="e4", agent_id="ag-1", tenant_id="t-1",
                skill_id="s-1", execution_seconds=6.0, token_usage=0,
                success=True,
            )
            asyncio.run(engine._trigger_alpha_evolver(event, "high_latency"))

    def test_trigger_alpha_evolver_missing_skill_code(self, db):
        from core.auto_dev.event_hooks import SkillExecutionEvent
        from core.auto_dev.evolution_engine import EvolutionEngine

        fake_session = MagicMock()

        class FakeAlphaEvolver:
            def __init__(self, db):
                self.db = db

            async def generate_tool_mutation(self, **kwargs):
                raise AssertionError("should not be called")

        engine = EvolutionEngine(db)
        engine._get_skill_code = Mock(return_value=None)
        with patch(
            "core.database.SessionLocal", return_value=fake_session,
        ), patch(
            "core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine",
            FakeAlphaEvolver,
        ):
            event = SkillExecutionEvent(
                execution_id="e5", agent_id="ag-1", tenant_id="t-1",
                skill_id="s-1", execution_seconds=6.0, token_usage=0,
                success=True,
            )
            asyncio.run(engine._trigger_alpha_evolver(event, "high_latency"))

    def test_trigger_alpha_evolver_exception_logged(self, db):
        from core.auto_dev.event_hooks import SkillExecutionEvent
        from core.auto_dev.evolution_engine import EvolutionEngine

        class FakeAlphaEvolver:
            def __init__(self, db):
                raise RuntimeError("construct failed")

        engine = EvolutionEngine(db)
        engine._get_skill_code = Mock(return_value="code")
        with patch(
            "core.database.SessionLocal", return_value=MagicMock(),
        ), patch(
            "core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine",
            FakeAlphaEvolver,
        ):
            event = SkillExecutionEvent(
                execution_id="e6", agent_id="ag-1", tenant_id="t-1",
                skill_id="s-1", execution_seconds=6.0, token_usage=0,
                success=True,
            )
            asyncio.run(engine._trigger_alpha_evolver(event, "high_latency"))

    def test_check_optimization_triggers_combined(self):
        from core.auto_dev.event_hooks import SkillExecutionEvent
        from core.auto_dev.evolution_engine import EvolutionEngine

        engine = EvolutionEngine(db=MagicMock())
        event = SkillExecutionEvent(
            execution_id="e7", agent_id="ag-1", tenant_id="t-1", skill_id="s-1",
            execution_seconds=5.5, token_usage=5500, success=False,
        )
        reason = engine._check_optimization_triggers(event)
        assert "high_latency" in reason
        assert "high_token_usage" in reason
        assert "execution_failure" in reason

    def test_check_optimization_triggers_none(self):
        from core.auto_dev.event_hooks import SkillExecutionEvent
        from core.auto_dev.evolution_engine import EvolutionEngine

        engine = EvolutionEngine(db=MagicMock())
        event = SkillExecutionEvent(
            execution_id="e8", agent_id="ag-1", tenant_id="t-1", skill_id="s-1",
            execution_seconds=1.0, token_usage=10, success=True,
        )
        assert engine._check_optimization_triggers(event) is None

    def test_should_optimize_exception(self, db):
        from core.auto_dev.evolution_engine import EvolutionEngine

        class BrokenGate:
            def __init__(self, session):
                raise RuntimeError("gate init failed")

        engine = EvolutionEngine(db)
        engine._get_workspace_settings = Mock(return_value={})
        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService", BrokenGate,
        ):
            assert engine._should_optimize("ag-1", "t-1") is False

    def test_get_skill_code_found(self, tmp_path, monkeypatch):
        from core.auto_dev.evolution_engine import EvolutionEngine

        skills_dir = tmp_path / "skills"
        (skills_dir / "skill-abc").mkdir(parents=True)
        (skills_dir / "skill-abc" / "skill_abc.py").write_text("def run(): pass")

        class FakeBuilder:
            def _get_tenant_skills_dir(self, tenant_id):
                return skills_dir

        monkeypatch.setattr(
            "core.skill_builder_service.SkillBuilderService", FakeBuilder,
        )
        engine = EvolutionEngine(db=MagicMock())
        assert "def run(): pass" in engine._get_skill_code("skill-abc", "t-1")

    def test_get_skill_code_not_found(self, tmp_path, monkeypatch):
        from core.auto_dev.evolution_engine import EvolutionEngine

        class FakeBuilder:
            def _get_tenant_skills_dir(self, tenant_id):
                return tmp_path

        monkeypatch.setattr(
            "core.skill_builder_service.SkillBuilderService", FakeBuilder,
        )
        engine = EvolutionEngine(db=MagicMock())
        assert engine._get_skill_code("nope", "t-1") is None

    def test_get_skill_code_exception(self, monkeypatch):
        from core.auto_dev.evolution_engine import EvolutionEngine

        class BrokenBuilder:
            def _get_tenant_skills_dir(self, tenant_id):
                raise RuntimeError("boom")

        monkeypatch.setattr(
            "core.skill_builder_service.SkillBuilderService", BrokenBuilder,
        )
        engine = EvolutionEngine(db=MagicMock())
        assert engine._get_skill_code("x", "t-1") is None

    def test_get_workspace_settings_with_metadata(self, db):
        from core.models import Workspace
        from core.auto_dev.evolution_engine import EvolutionEngine

        db.add(Workspace(
            id="ws-1", name="W", tenant_id="t-ws-1",
            metadata_json={"auto_dev": {"enabled": True}},
        ))
        db.commit()
        engine = EvolutionEngine(db)
        assert engine._get_workspace_settings("t-ws-1") == {
            "auto_dev": {"enabled": True}
        }

    def test_get_workspace_settings_missing(self, db):
        from core.auto_dev.evolution_engine import EvolutionEngine

        engine = EvolutionEngine(db)
        assert engine._get_workspace_settings("t-missing") == {}

    def test_get_workspace_settings_exception(self, db, monkeypatch):
        from core.auto_dev.evolution_engine import EvolutionEngine

        monkeypatch.setitem(sys.modules, "core.models", _empty_module("core.models"))
        engine = EvolutionEngine(db)
        assert engine._get_workspace_settings("t-1") == {}


# =============================================================================
# EvolutionPipeline
# =============================================================================


class TestEvolutionPipelineCoverage:
    def _request(self, **kwargs):
        from core.auto_dev.evolution_pipeline import MutationRequest

        defaults = dict(
            agent_id="a1", tenant_id="t1", source="alpha_evolver",
            config_key="system_prompt", old_value="old", new_value="new",
        )
        defaults.update(kwargs)
        return MutationRequest(**defaults)

    @pytest.mark.asyncio
    async def test_submit_deploy_dict_new_value(self, monkeypatch):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline

        governance = MagicMock()
        governance.validate_evolution_directive = AsyncMock(return_value=True)
        monkeypatch.setattr(
            "core.agent_governance_service.AgentGovernanceService",
            lambda session: governance,
        )
        gate = MagicMock()
        gate.check_daily_limits = Mock(return_value=True)
        monkeypatch.setattr(
            "core.auto_dev.capability_gate.AutoDevCapabilityService",
            lambda session: gate,
        )
        pipeline = UnifiedEvolutionPipeline(db=MagicMock())
        result = await pipeline.submit_and_deploy(self._request(
            new_value={"system_prompt": "x", "extra_key": 1},
        ))
        assert result.passed is True
        assert result.stage == "validated"
        assert result.rollback_mutation_id is not None

    @pytest.mark.asyncio
    async def test_submit_deploy_governance_error_blocks(self, monkeypatch):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline

        def broken_svc(session):
            raise RuntimeError("gov init failed")

        monkeypatch.setattr(
            "core.agent_governance_service.AgentGovernanceService", broken_svc,
        )
        pipeline = UnifiedEvolutionPipeline(db=MagicMock())
        result = await pipeline.submit_and_deploy(self._request())
        assert result.passed is False
        assert result.stage == "governance"

    @pytest.mark.asyncio
    async def test_submit_deploy_governance_rejects(self, monkeypatch):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline

        governance = MagicMock()
        governance.validate_evolution_directive = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "core.agent_governance_service.AgentGovernanceService",
            lambda session: governance,
        )
        pipeline = UnifiedEvolutionPipeline(db=MagicMock())
        result = await pipeline.submit_and_deploy(self._request())
        assert result.passed is False
        assert result.stage == "governance"

    @pytest.mark.asyncio
    async def test_submit_deploy_daily_limit_exceeded(self, monkeypatch):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline

        governance = MagicMock()
        governance.validate_evolution_directive = AsyncMock(return_value=True)
        monkeypatch.setattr(
            "core.agent_governance_service.AgentGovernanceService",
            lambda session: governance,
        )
        gate = MagicMock()
        gate.check_daily_limits = Mock(return_value=False)
        monkeypatch.setattr(
            "core.auto_dev.capability_gate.AutoDevCapabilityService",
            lambda session: gate,
        )
        pipeline = UnifiedEvolutionPipeline(db=MagicMock())
        result = await pipeline.submit_and_deploy(self._request())
        assert result.passed is False
        assert result.stage == "daily_limit"

    @pytest.mark.asyncio
    async def test_submit_deploy_daily_limit_error_blocks(self, monkeypatch):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline

        governance = MagicMock()
        governance.validate_evolution_directive = AsyncMock(return_value=True)
        monkeypatch.setattr(
            "core.agent_governance_service.AgentGovernanceService",
            lambda session: governance,
        )

        def broken_gate(session):
            raise RuntimeError("gate failed")

        monkeypatch.setattr(
            "core.auto_dev.capability_gate.AutoDevCapabilityService", broken_gate,
        )
        pipeline = UnifiedEvolutionPipeline(db=MagicMock())
        result = await pipeline.submit_and_deploy(self._request())
        assert result.passed is False
        assert result.stage == "daily_limit"

    @pytest.mark.asyncio
    async def test_rollback_error_returns_false(self, monkeypatch):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline

        def broken_registry():
            raise RuntimeError("registry down")

        monkeypatch.setattr(
            "core.auto_dev.mutation_rollback.get_rollback_registry",
            broken_registry,
        )
        pipeline = UnifiedEvolutionPipeline(db=MagicMock())
        assert await pipeline.rollback("m1", {}) is False

    @pytest.mark.asyncio
    async def test_rollback_success(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        from core.auto_dev.mutation_rollback import get_rollback_registry

        registry = get_rollback_registry()
        mutation_id = registry.snapshot(
            agent_id="a-rb", config_key="configuration", old_value={},
            new_value={"x": 1}, source="test",
        )
        pipeline = UnifiedEvolutionPipeline(db=MagicMock())
        assert await pipeline.rollback(mutation_id, {}) is True

    @pytest.mark.asyncio
    async def test_verify_success_and_error(self):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline
        from core.auto_dev.mutation_rollback import get_rollback_registry

        registry = get_rollback_registry()
        mutation_id = registry.snapshot(
            agent_id="a-vf", config_key="configuration", old_value={},
            new_value={"x": 1}, source="test",
        )
        pipeline = UnifiedEvolutionPipeline(db=MagicMock())
        assert await pipeline.verify(mutation_id) is True
        assert await pipeline.verify("no-such-mutation") is False

    @pytest.mark.asyncio
    async def test_verify_error(self, monkeypatch):
        from core.auto_dev.evolution_pipeline import UnifiedEvolutionPipeline

        def broken_registry():
            raise RuntimeError("registry down")

        monkeypatch.setattr(
            "core.auto_dev.mutation_rollback.get_rollback_registry",
            broken_registry,
        )
        pipeline = UnifiedEvolutionPipeline(db=MagicMock())
        assert await pipeline.verify("m1") is False

    def test_dataclass_defaults(self):
        from core.auto_dev.evolution_pipeline import MutationRequest, PipelineResult

        req = MutationRequest(
            agent_id="a", tenant_id="t", source="gea",
            config_key="k", old_value=1, new_value=2,
        )
        assert req.parent_code is None
        assert req.test_inputs == []
        result = PipelineResult(mutation_id="m", passed=False)
        assert result.stage == ""
        assert result.rollback_mutation_id is None


# =============================================================================
# FitnessService
# =============================================================================


class TestFitnessServiceCoverage:
    def test_evaluate_initial_proxy_variant_not_found(self, db):
        from core.auto_dev.fitness_service import FitnessService

        score = FitnessService(db).evaluate_initial_proxy("v-miss", "t-1", {})
        assert score == 0.0

    def test_evaluate_initial_proxy_no_delayed_eval(self, db):
        from core.auto_dev.fitness_service import FitnessService

        db.add(WorkflowVariant(
            id="v-1", tenant_id="t-1", workflow_definition={},
            fitness_signals={"proxy": {}}, fitness_score=0.5,
            evaluation_status="pending",
        ))
        db.commit()

        score = FitnessService(db).evaluate_initial_proxy(
            "v-1", "t-1",
            {"execution_success": True, "syntax_error": False,
             "expects_delayed_eval": False},
        )
        assert score == 0.5
        assert db.query(WorkflowVariant).get("v-1").evaluation_status == "evaluated"

    def test_evaluate_initial_proxy_syntax_error_and_rejection(self, db):
        from core.auto_dev.fitness_service import FitnessService

        db.add(WorkflowVariant(
            id="v-2", tenant_id="t-1", workflow_definition={},
            fitness_score=0.5, evaluation_status="pending",
        ))
        db.commit()

        score = FitnessService(db).evaluate_initial_proxy(
            "v-2", "t-1",
            {"syntax_error": True, "execution_success": False,
             "user_approved_proposal": False, "expects_delayed_eval": False},
        )
        assert score == 0.0
        assert db.query(WorkflowVariant).get("v-2").fitness_signals["proxy"][
            "syntax_error"
        ] is True

    def test_evaluate_initial_proxy_full_bonuses(self, db):
        from core.auto_dev.fitness_service import FitnessService

        db.add(WorkflowVariant(
            id="v-3", tenant_id="t-1", workflow_definition={}, fitness_score=0.0,
            evaluation_status="pending",
        ))
        db.commit()

        score = FitnessService(db).evaluate_initial_proxy(
            "v-3", "t-1",
            {"execution_success": True, "syntax_error": False,
             "user_approved_proposal": True},
        )
        assert score == 1.0

    def test_evaluate_delayed_webhook_not_found(self, db):
        from core.auto_dev.fitness_service import FitnessService

        assert FitnessService(db).evaluate_delayed_webhook("v-miss", "t-1", {}) == 0.0

    def test_evaluate_delayed_webhook_all_signals(self, db):
        from core.auto_dev.fitness_service import FitnessService

        db.add(WorkflowVariant(
            id="v-4", tenant_id="t-1", workflow_definition={}, fitness_score=0.4,
            fitness_signals={"proxy": {}}, evaluation_status="pending",
        ))
        db.commit()

        score = FitnessService(db).evaluate_delayed_webhook(
            "v-4", "t-1",
            {"invoice_created": True, "crm_conversion": True,
             "conversion_success": True, "email_bounce": True,
             "error_signal": True, "conversion_value": 500.0},
        )
        assert score == 1.0
        variant = db.query(WorkflowVariant).get("v-4")
        assert variant.evaluation_status == "evaluated"
        assert "external" in variant.fitness_signals

    def test_evaluate_delayed_webhook_negative_clamp(self, db):
        from core.auto_dev.fitness_service import FitnessService

        db.add(WorkflowVariant(
            id="v-5", tenant_id="t-1", workflow_definition={}, fitness_score=0.1,
            evaluation_status="pending",
        ))
        db.commit()

        score = FitnessService(db).evaluate_delayed_webhook(
            "v-5", "t-1", {"email_bounce": True, "error_signal": True},
        )
        assert score == 0.0

    def test_evaluate_delayed_webhook_conversion_value_capped(self, db):
        from core.auto_dev.fitness_service import FitnessService

        db.add(WorkflowVariant(
            id="v-6", tenant_id="t-1", workflow_definition={}, fitness_score=0.0,
            evaluation_status="pending",
        ))
        db.commit()

        score = FitnessService(db).evaluate_delayed_webhook(
            "v-6", "t-1", {"conversion_value": 50000.0},
        )
        assert score == 0.5

    def test_get_top_variants_filters(self, db):
        from core.auto_dev.fitness_service import FitnessService

        db.add_all([
            WorkflowVariant(id="v-top-1", tenant_id="t-top",
                            workflow_definition={}, fitness_score=0.9,
                            evaluation_status="evaluated"),
            WorkflowVariant(id="v-top-2", tenant_id="t-top",
                            workflow_definition={}, fitness_score=0.3,
                            evaluation_status="evaluated"),
            WorkflowVariant(id="v-top-3", tenant_id="t-top",
                            workflow_definition={}, fitness_score=0.0,
                            evaluation_status="evaluated"),
            WorkflowVariant(id="v-top-4", tenant_id="t-other",
                            workflow_definition={}, fitness_score=0.9,
                            evaluation_status="evaluated"),
        ])
        db.commit()
        top = FitnessService(db).get_top_variants("t-top", limit=5)
        assert [v.id for v in top] == ["v-top-1", "v-top-2"]
