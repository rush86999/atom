"""Coverage push (wave 82a) for Auto-Dev + cost/benchmark modules.

Targets (>=95% statement coverage each, standalone):
  core/auto_dev/advisor_service.py
  core/auto_dev/alpha_evolver_engine.py
  core/auto_dev/capability_gate.py
  core/auto_dev/fitness_service.py
  core/auto_dev/memento_engine.py
  core/dynamic_benchmark_fetcher.py
  core/cost_config.py

Style: mocked deps, zero LLM spend, no network, no real DB (in-memory sqlite).
"""

import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
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
    from core.database import Base

    with db_engine.connect() as con:
        for table in reversed(Base.metadata.sorted_tables):
            con.execute(table.delete())
        con.commit()


def _empty_module(name: str) -> types.ModuleType:
    return types.ModuleType(name)


# =============================================================================
# AdvisorService
# =============================================================================


def _make_advisor(db, **kwargs):
    from core.auto_dev.advisor_service import AdvisorService

    return AdvisorService(db=db, **kwargs)


def _seed_advisor_data(db, n_mutations=1, n_passed=1, n_failed=0, fitness=0.8):
    for i in range(n_mutations):
        status = "passed" if i < n_passed else ("failed" if i < n_passed + n_failed else "pending")
        db.add(ToolMutation(
            tenant_id="t-adv", tool_name=f"tool-{i}", mutated_code=f"code-{i}",
            sandbox_status=status,
        ))
    for i in range(1 if fitness else 0):
        db.add(WorkflowVariant(
            tenant_id="t-adv", workflow_definition={}, fitness_score=fitness,
            evaluation_status="evaluated",
        ))
    db.commit()


class TestAdvisorService:
    def test_generate_guidance_no_data(self, db):
        svc = _make_advisor(db)
        result = asyncio.run(svc.generate_guidance(tenant_id="t-empty"))
        assert result["status"] == "success"
        assert result["readiness_score"] == 0
        assert "No evolutionary data" in result["message"]

    def test_generate_guidance_heuristic_when_no_llm(self, db, monkeypatch):
        _seed_advisor_data(db, n_mutations=2, n_passed=2, fitness=0.7)
        svc = _make_advisor(db, llm_service=None)
        monkeypatch.setattr(
            "core.auto_dev.advisor_service.AdvisorService._get_llm_service",
            lambda self: None,
        )
        result = asyncio.run(svc.generate_guidance(tenant_id="t-adv"))
        assert result["data_summary"]["num_mutations"] == 2
        assert result["data_summary"]["passed_mutations"] == 2
        assert result["data_summary"]["avg_fitness_score"] == 0.7
        assert result["readiness_score"] == 40
        assert "Strong results" in result["message"]

    def test_generate_guidance_with_llm(self, db):
        _seed_advisor_data(db, n_mutations=1, n_passed=1)
        llm = AsyncMock()
        llm.generate_completion = AsyncMock(
            return_value={"content": "Consider synthesizing findings."}
        )
        svc = _make_advisor(db, llm_service=llm)
        result = asyncio.run(svc.generate_guidance(tenant_id="t-adv"))
        assert result["message"] == "Consider synthesizing findings."
        llm.generate_completion.assert_awaited_once()
        kwargs = llm.generate_completion.await_args.kwargs
        assert kwargs["temperature"] == 0.5
        assert "t-adv" in kwargs["user_prompt"]

    def test_generate_guidance_llm_empty_content_default(self, db):
        _seed_advisor_data(db, n_mutations=1, n_passed=1)
        llm = AsyncMock()
        llm.generate_completion = AsyncMock(return_value={"tokens": 7})
        svc = _make_advisor(db, llm_service=llm)
        result = asyncio.run(svc.generate_guidance(tenant_id="t-adv"))
        assert result["message"] == "Evolution is progressing. Continue monitoring signals."

    def test_generate_guidance_llm_exception_falls_back(self, db):
        _seed_advisor_data(db, n_mutations=3, n_passed=1, n_failed=2)
        llm = AsyncMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("boom"))
        svc = _make_advisor(db, llm_service=llm)
        result = asyncio.run(svc.generate_guidance(tenant_id="t-adv"))
        assert "High failure rate" in result["message"]

    def test_data_summary_failed_and_pending_counts(self, db, monkeypatch):
        _seed_advisor_data(db, n_mutations=3, n_passed=1, n_failed=1)
        svc = _make_advisor(db)
        monkeypatch.setattr(
            "core.auto_dev.advisor_service.AdvisorService._get_llm_service",
            lambda self: None,
        )
        result = asyncio.run(svc.generate_guidance(tenant_id="t-adv"))
        assert result["data_summary"]["failed_mutations"] == 1
        assert result["data_summary"]["passed_mutations"] == 1
        assert result["data_summary"]["top_fitness_score"] == 0.8

    def test_heuristic_guidance_total_zero(self, db):
        svc = _make_advisor(db)
        msg = svc._generate_heuristic_guidance({
            "num_mutations": 0, "passed_mutations": 0, "failed_mutations": 0,
            "avg_fitness_score": 0.0,
        })
        assert "first evolution cycle" in msg

    def test_heuristic_guidance_moderate(self, db):
        svc = _make_advisor(db)
        msg = svc._generate_heuristic_guidance({
            "num_mutations": 4, "passed_mutations": 2, "failed_mutations": 2,
            "avg_fitness_score": 0.3,
        })
        assert "Moderate progress" in msg

    def test_heuristic_guidance_high_failure(self, db):
        svc = _make_advisor(db)
        msg = svc._generate_heuristic_guidance({
            "num_mutations": 4, "passed_mutations": 1, "failed_mutations": 3,
            "avg_fitness_score": 0.1,
        })
        assert "High failure rate" in msg

    def test_heuristic_guidance_strong_requires_both(self, db):
        svc = _make_advisor(db)
        msg = svc._generate_heuristic_guidance({
            "num_mutations": 4, "passed_mutations": 4, "failed_mutations": 0,
            "avg_fitness_score": 0.5,
        })
        assert "Moderate progress" in msg

    def test_get_llm_service_success(self, db, monkeypatch):
        svc = _make_advisor(db)
        monkeypatch.setattr(
            "core.llm_service.get_llm_service", lambda: "llm-instance"
        )
        assert svc._get_llm_service() == "llm-instance"

    def test_get_llm_service_import_error_returns_none(self, db, monkeypatch):
        svc = _make_advisor(db)
        monkeypatch.setitem(sys.modules, "core.llm_service", None)
        assert svc._get_llm_service() is None

    def test_get_llm_service_generic_exception_returns_none(self, db, monkeypatch):
        svc = _make_advisor(db)
        monkeypatch.setattr(
            "core.llm_service.get_llm_service",
            Mock(side_effect=RuntimeError("down")),
        )
        assert svc._get_llm_service() is None

    def test_generate_guidance_heuristic_branch_line111(self, db, monkeypatch):
        _seed_advisor_data(db, n_mutations=1, n_passed=1)
        svc = _make_advisor(db, llm_service=None)
        monkeypatch.setattr(
            "core.auto_dev.advisor_service.AdvisorService._get_llm_service",
            lambda self: None,
        )
        result = asyncio.run(svc.generate_guidance(tenant_id="t-adv"))
        assert result["status"] == "success"
        assert result["message"]  # heuristic output


# =============================================================================
# AlphaEvolverEngine
# =============================================================================


def _make_alpha(db, **kwargs):
    from core.auto_dev.alpha_evolver_engine import AlphaEvolverEngine

    return AlphaEvolverEngine(db=db, **kwargs)


def _ok_sandbox(results):
    sandbox = MagicMock()
    calls = {"n": 0}

    async def execute(tenant_id, code, input_params, **kw):
        r = results[min(calls["n"], len(results) - 1)] if results else {
            "status": "success", "output": "out", "execution_seconds": 0.1,
        }
        calls["n"] += 1
        return r

    sandbox.execute_raw_python = AsyncMock(side_effect=execute)
    return sandbox


class TestAlphaEvolverEngine:
    def test_analyze_episode_full(self, db):
        from core.models import AgentEpisode, EpisodeSegment

        db.add(AgentEpisode(
            id="ep-a-1", agent_id="ag-1", tenant_id="t-1",
            task_description="Optimize pipeline", maturity_at_time="supervised",
            outcome="success", success=True, status="completed",
            metadata_json={"cost": 5},
        ))
        db.add(EpisodeSegment(
            id="seg-a-1", episode_id="ep-a-1", segment_type="execution",
            sequence_order=1, content="ran",
            canvas_context={"execution_seconds": 6.0},
        ))
        db.add(EpisodeSegment(
            id="seg-a-2", episode_id="ep-a-1", segment_type="execution",
            sequence_order=2, content="retried",
            canvas_context={"retry_count": 2},
        ))
        db.add(EpisodeSegment(
            id="seg-a-3", episode_id="ep-a-1", segment_type="execution",
            sequence_order=3, content="fast",
            canvas_context={"execution_seconds": 1.0},
        ))
        db.commit()

        engine = _make_alpha(db)
        result = asyncio.run(engine.analyze_episode("ep-a-1"))
        assert result["total_segments"] == 3
        assert result["metadata"] == {"cost": 5}
        targets = result["optimization_targets"]
        assert {t["reason"] for t in targets} == {"high_latency", "retries"}

    def test_analyze_episode_not_found(self, db):
        engine = _make_alpha(db)
        result = asyncio.run(engine.analyze_episode("ep-a-missing"))
        assert "not found" in result["error"]

    def test_analyze_episode_import_error(self, db, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.models", _empty_module("core.models"))
        engine = _make_alpha(db)
        result = asyncio.run(engine.analyze_episode("ep-1"))
        assert result["error"] == "Episode models not available"

    def test_propose_code_change_no_llm(self, db, monkeypatch):
        engine = _make_alpha(db)
        monkeypatch.setattr(engine, "_get_llm_service", lambda: None)
        code = asyncio.run(engine.propose_code_change(
            context={"base_code": "def f(): pass", "mutation_prompt": "speed up"},
        ))
        assert code.startswith("def f(): pass")
        assert "Mutation skipped" in code

    def test_propose_code_change_llm_strips_fences(self, db):
        llm = AsyncMock()
        llm.generate_completion = AsyncMock(return_value={
            "content": "```python\ndef new():\n    return 2\n```",
        })
        engine = _make_alpha(db, llm_service=llm)
        code = asyncio.run(engine.propose_code_change(
            context={"base_code": "old", "mutation_prompt": "opt"},
        ))
        assert code == "def new():\n    return 2"
        llm.generate_completion.assert_awaited_once()

    def test_propose_code_change_llm_error(self, db):
        llm = AsyncMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        engine = _make_alpha(db, llm_service=llm)
        code = asyncio.run(engine.propose_code_change(
            context={"base_code": "def f(): pass", "mutation_prompt": "opt"},
        ))
        assert "Mutation failed" in code

    def test_validate_change_no_sandbox(self, db, monkeypatch):
        engine = _make_alpha(db)
        monkeypatch.setattr(engine, "_get_sandbox", lambda: None)
        result = asyncio.run(engine.validate_change(
            code="code", test_inputs=[{}], tenant_id="t-1",
        ))
        assert result["passed"] is False
        assert "Sandbox unavailable" in result["error"]

    def test_validate_change_all_pass(self, db):
        sandbox = _ok_sandbox([
            {"status": "success", "output": "1", "execution_seconds": 0.1},
            {"status": "success", "output": "2", "execution_seconds": 0.2},
        ])
        engine = _make_alpha(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_change(
            code="code", test_inputs=[{"a": 1}, {"a": 2}], tenant_id="t-1",
        ))
        assert result["passed"] is True
        assert len(result["test_results"]) == 2
        assert result["proxy_signals"]["execution_success"] is True
        assert result["proxy_signals"]["pass_rate"] == 1.0
        assert result["proxy_signals"]["avg_execution_seconds"] == 0.15

    def test_validate_change_some_fail(self, db):
        sandbox = _ok_sandbox([
            {"status": "failed", "output": "SyntaxError: bad", "execution_seconds": 0.1},
            {"status": "success", "output": "ok", "execution_seconds": 0.2},
        ])
        engine = _make_alpha(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_change(
            code="code", test_inputs=[{"a": 1}, {"a": 2}], tenant_id="t-1",
        ))
        assert result["passed"] is False
        assert result["proxy_signals"]["syntax_error"] is True
        assert result["proxy_signals"]["pass_rate"] == 0.5
        assert result["proxy_signals"]["execution_success"] is False

    def test_validate_change_regression_pass(self, db):
        sandbox = _ok_sandbox([{"status": "success", "output": "same", "execution_seconds": 0.1}])
        engine = _make_alpha(db, sandbox=sandbox)
        with patch("core.auto_dev.regression_validator.RegressionValidator") as RV:
            rv = RV.return_value
            rv.validate_regression = AsyncMock(return_value=SimpleNamespace(
                passed=True, mismatches=[], total_tests=1, to_dict=lambda: {"passed": True},
            ))
            result = asyncio.run(engine.validate_change(
                code="child", test_inputs=[{"a": 1}], tenant_id="t-1",
                parent_code="parent",
            ))
        assert result["passed"] is True

    def test_validate_change_regression_reject(self, db):
        sandbox = _ok_sandbox([{"status": "success", "output": "changed", "execution_seconds": 0.1}])
        engine = _make_alpha(db, sandbox=sandbox)
        with patch("core.auto_dev.regression_validator.RegressionValidator") as RV:
            rv = RV.return_value
            rv.validate_regression = AsyncMock(return_value=SimpleNamespace(
                passed=False, mismatches=[1], total_tests=1,
                to_dict=lambda: {"passed": False, "mismatches": 1},
            ))
            result = asyncio.run(engine.validate_change(
                code="child", test_inputs=[{"a": 1}], tenant_id="t-1",
                parent_code="parent",
            ))
        assert result["passed"] is False
        assert result["regression_result"]["passed"] is False

    def test_validate_change_regression_validator_raises(self, db):
        sandbox = _ok_sandbox([{"status": "success", "output": "out", "execution_seconds": 0.1}])
        engine = _make_alpha(db, sandbox=sandbox)
        with patch("core.auto_dev.regression_validator.RegressionValidator") as RV:
            RV.side_effect = RuntimeError("validator missing")
            result = asyncio.run(engine.validate_change(
                code="child", test_inputs=[{"a": 1}], tenant_id="t-1",
                parent_code="parent",
            ))
        assert result["passed"] is True

    def test_generate_tool_mutation_persists(self, db):
        llm = AsyncMock()
        llm.generate_completion = AsyncMock(return_value={
            "content": "def m():\n    return 1",
        })
        engine = _make_alpha(db, llm_service=llm)
        mutation = asyncio.run(engine.generate_tool_mutation(
            tenant_id="t-1", tool_name="tool", parent_tool_id="pt-1",
            base_code="base", mutation_prompt="go",
        ))
        assert mutation.sandbox_status == "pending"
        assert mutation.parent_tool_id == "pt-1"
        row = db.query(ToolMutation).filter(ToolMutation.id == mutation.id).first()
        assert row is not None

    def test_sandbox_execute_mutation_not_found(self, db):
        engine = _make_alpha(db)
        result = asyncio.run(engine.sandbox_execute_mutation(
            mutation_id="nope", tenant_id="t-1", inputs={},
        ))
        assert "not found" in result["error"]

    def test_sandbox_execute_mutation_no_sandbox(self, db, monkeypatch):
        db.add(ToolMutation(
            id="m-sb-1", tenant_id="t-1", tool_name="t", mutated_code="code",
            sandbox_status="pending",
        ))
        db.commit()
        engine = _make_alpha(db)
        monkeypatch.setattr(engine, "_get_sandbox", lambda: None)
        result = asyncio.run(engine.sandbox_execute_mutation(
            mutation_id="m-sb-1", tenant_id="t-1", inputs={},
        ))
        assert "Sandbox unavailable" in result["error"]

    def test_sandbox_execute_mutation_success(self, db):
        db.add(ToolMutation(
            id="m-sb-2", tenant_id="t-1", tool_name="t", mutated_code="code",
            sandbox_status="pending",
        ))
        db.commit()
        sandbox = _ok_sandbox([{
            "status": "success", "output": "ok", "execution_seconds": 0.25,
            "environment": "docker",
        }])
        engine = _make_alpha(db, sandbox=sandbox)
        result = asyncio.run(engine.sandbox_execute_mutation(
            mutation_id="m-sb-2", tenant_id="t-1", inputs={"x": 1},
        ))
        assert result["success"] is True
        assert result["proxy_signals"]["execution_success"] is True
        assert result["proxy_signals"]["execution_latency_ms"] == 250.0
        assert result["proxy_signals"]["environment"] == "docker"
        row = db.query(ToolMutation).get("m-sb-2")
        assert row.sandbox_status == "passed"

    def test_sandbox_execute_mutation_failure_syntax_error(self, db):
        db.add(ToolMutation(
            id="m-sb-3", tenant_id="t-1", tool_name="t", mutated_code="bad(",
            sandbox_status="pending",
        ))
        db.commit()
        sandbox = _ok_sandbox([{
            "status": "failed", "output": "SyntaxError: bad input",
            "execution_seconds": 0.1, "environment": "docker",
        }])
        engine = _make_alpha(db, sandbox=sandbox)
        result = asyncio.run(engine.sandbox_execute_mutation(
            mutation_id="m-sb-3", tenant_id="t-1", inputs={},
        ))
        assert result["success"] is False
        assert result["proxy_signals"]["syntax_error"] is True
        assert result["proxy_signals"]["execution_success"] is False
        row = db.query(ToolMutation).get("m-sb-3")
        assert row.sandbox_status == "failed"
        assert row.execution_error == "SyntaxError: bad input"

    def test_sandbox_execute_mutation_failure_non_syntax(self, db):
        db.add(ToolMutation(
            id="m-sb-4", tenant_id="t-1", tool_name="t", mutated_code="code",
            sandbox_status="pending",
        ))
        db.commit()
        sandbox = _ok_sandbox([{"status": "failed", "output": "crash", "execution_seconds": 0.1}])
        engine = _make_alpha(db, sandbox=sandbox)
        result = asyncio.run(engine.sandbox_execute_mutation(
            mutation_id="m-sb-4", tenant_id="t-1", inputs={},
        ))
        assert result["proxy_signals"]["syntax_error"] is False

    def test_spawn_workflow_variant(self, db):
        engine = _make_alpha(db)
        variant = engine.spawn_workflow_variant(
            tenant_id="t-1", agent_id="ag-1", workflow_def={"steps": []},
            parent_variant_id="pv-1",
        )
        assert variant.evaluation_status == "pending"
        assert variant.parent_variant_id == "pv-1"
        assert db.query(WorkflowVariant).get(variant.id) is not None

    def test_spawn_workflow_variant_no_parent(self, db):
        engine = _make_alpha(db)
        variant = engine.spawn_workflow_variant(
            tenant_id="t-1", agent_id="ag-1", workflow_def={"steps": []},
        )
        assert variant.parent_variant_id is None

    def test_check_auto_synthesis_readiness_below_threshold(self, db):
        for i in range(3):
            db.add(ToolMutation(
                tenant_id="t-1", tool_name="tool-x", mutated_code=f"c{i}",
                sandbox_status="passed",
            ))
        db.add(ToolMutation(
            tenant_id="t-1", tool_name="tool-x", mutated_code="c4",
            sandbox_status="failed",
        ))
        db.commit()
        engine = _make_alpha(db)
        assert engine.check_auto_synthesis_readiness("t-1", "tool-x") is False

    def test_check_auto_synthesis_readiness_at_threshold(self, db):
        for i in range(5):
            db.add(ToolMutation(
                tenant_id="t-1", tool_name="tool-x", mutated_code=f"c{i}",
                sandbox_status="passed",
            ))
        db.commit()
        engine = _make_alpha(db)
        assert engine.check_auto_synthesis_readiness("t-1", "tool-x") is True
        assert engine.check_auto_synthesis_readiness("t-1", "tool-x", threshold=10) is False

    def test_run_research_experiment_promotes(self, db):
        engine = _make_alpha(db)
        calls = {"n": 0}

        async def fake_mutation(tenant_id, tool_name, parent_tool_id,
                                base_code, mutation_prompt):
            calls["n"] += 1
            return ToolMutation(
                id=f"r-{calls['n']}", tenant_id=tenant_id, tool_name=tool_name,
                mutated_code=f"def v{calls['n']}():\n    return {calls['n']}",
            )

        async def fake_exec(mutation_id, tenant_id, inputs):
            return {"success": True, "output": f"out-{mutation_id}"}

        engine.generate_tool_mutation = AsyncMock(side_effect=fake_mutation)
        engine.sandbox_execute_mutation = AsyncMock(side_effect=fake_exec)
        results = asyncio.run(engine.run_research_experiment(
            tenant_id="t-1", base_code="base", research_goal="go", iterations=2,
            inputs={"x": 1},
        ))
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[0]["code_preview"].endswith("...")

    def test_run_research_experiment_no_promote_empty_output(self, db):
        engine = _make_alpha(db)

        async def fake_mutation(tenant_id, tool_name, parent_tool_id,
                                base_code, mutation_prompt):
            return ToolMutation(
                id="r-e", tenant_id=tenant_id, tool_name=tool_name,
                mutated_code="def v1():\n    return 1",
            )

        async def fake_exec(mutation_id, tenant_id, inputs):
            return {"success": True, "output": "   "}

        engine.generate_tool_mutation = AsyncMock(side_effect=fake_mutation)
        engine.sandbox_execute_mutation = AsyncMock(side_effect=fake_exec)
        results = asyncio.run(engine.run_research_experiment(
            tenant_id="t-1", base_code="base", research_goal="go", iterations=1,
        ))
        assert results[0]["success"] is True

    def test_run_research_experiment_no_promote_comment_only(self, db):
        engine = _make_alpha(db)

        async def fake_mutation(tenant_id, tool_name, parent_tool_id,
                                base_code, mutation_prompt):
            return ToolMutation(
                id="r-c", tenant_id=tenant_id, tool_name=tool_name,
                mutated_code="# only a comment",
            )

        async def fake_exec(mutation_id, tenant_id, inputs):
            return {"success": True, "output": "out"}

        engine.generate_tool_mutation = AsyncMock(side_effect=fake_mutation)
        engine.sandbox_execute_mutation = AsyncMock(side_effect=fake_exec)
        results = asyncio.run(engine.run_research_experiment(
            tenant_id="t-1", base_code="base", research_goal="go", iterations=1,
        ))
        assert results[0]["success"] is True

    def test_run_research_experiment_failure_iteration(self, db):
        engine = _make_alpha(db)

        async def fake_mutation(tenant_id, tool_name, parent_tool_id,
                                base_code, mutation_prompt):
            return ToolMutation(
                id="r-f", tenant_id=tenant_id, tool_name=tool_name,
                mutated_code="def v1():\n    return 1",
            )

        async def fake_exec(mutation_id, tenant_id, inputs):
            return {"success": False, "output": "crash"}

        engine.generate_tool_mutation = AsyncMock(side_effect=fake_mutation)
        engine.sandbox_execute_mutation = AsyncMock(side_effect=fake_exec)
        results = asyncio.run(engine.run_research_experiment(
            tenant_id="t-1", base_code="base", research_goal="go", iterations=1,
        ))
        assert results[0]["success"] is False

    def _arbor_engine(self, db, mutated_code="def winner():\n    return 1", exec_result=None):
        engine = _make_alpha(db)

        async def fake_mutation(tenant_id, tool_name, parent_tool_id,
                                base_code, mutation_prompt):
            return ToolMutation(
                id="arbor-m", tenant_id=tenant_id, tool_name=tool_name,
                mutated_code=mutated_code,
            )

        async def fake_exec(mutation_id, tenant_id, inputs):
            return exec_result or {
                "success": True, "output": "good",
                "proxy_signals": {"execution_latency_ms": 200.0},
            }

        engine.generate_tool_mutation = AsyncMock(side_effect=fake_mutation)
        engine.sandbox_execute_mutation = AsyncMock(side_effect=fake_exec)
        return engine

    def test_run_arbor_experiment_success(self, db):
        engine = self._arbor_engine(db)
        result = asyncio.run(engine.run_arbor_experiment(
            tenant_id="t-1", base_code="base", research_goal="improve",
            iterations=2, language="python",
        ))
        assert result["winning_node_id"] is not None
        assert len(result["iterations"]) == 2
        assert result["tree"]["winning_path"]

    def test_run_arbor_experiment_lint_failure(self, db):
        engine = self._arbor_engine(db, mutated_code="def broken(:")
        result = asyncio.run(engine.run_arbor_experiment(
            tenant_id="t-1", base_code="base", research_goal="improve", iterations=1,
        ))
        assert result["iterations"][0]["pruned"] is True
        assert result["iterations"][0]["prune_reason"] == "lint_failed"
        assert result["winning_node_id"] is None

    def test_run_arbor_experiment_sandbox_failure(self, db):
        engine = self._arbor_engine(db, exec_result={
            "success": False, "output": "crash",
            "proxy_signals": {"execution_latency_ms": 100.0},
        })
        result = asyncio.run(engine.run_arbor_experiment(
            tenant_id="t-1", base_code="base", research_goal="improve", iterations=1,
        ))
        assert result["iterations"][0]["pruned"] is True
        assert result["iterations"][0]["prune_reason"] == "test_failed"
        assert result["winning_node_id"] is None

    def test_run_arbor_experiment_tree_budget_exhausted(self, db, monkeypatch):
        import core.hypothesis_tree as ht_mod

        class FakeTree:
            def __init__(self, id, task_description, tier):
                self.id = id
                self.max_nodes = 5
                self.nodes = 0
                self.winning_path = None

            def add_node(self, node):
                self.nodes += 1
                return self.nodes < 2  # budget exhausted at iteration 2

            def prune_branch(self, node_id, reason):
                pass

            def get_path_to_root(self, node_id):
                return [node_id]

            def get_statistics(self):
                return {"total_nodes": self.nodes, "successful_nodes": 0,
                        "pruned_nodes": 0, "promise_scores": []}

        monkeypatch.setattr(ht_mod, "HypothesisTree", FakeTree)
        engine = self._arbor_engine(db)
        result = asyncio.run(engine.run_arbor_experiment(
            tenant_id="t-1", base_code="base", research_goal="improve", iterations=3,
        ))
        assert len(result["iterations"]) == 1  # broke on budget exhaustion

    def test_identify_optimization_targets(self, db):
        engine = _make_alpha(db)
        segs = [
            SimpleNamespace(id="s1", canvas_context={"execution_seconds": 6.0}),
            SimpleNamespace(id="s2", canvas_context={"retry_count": 1}),
            SimpleNamespace(id="s3", canvas_context={"execution_seconds": 1.0}),
        ]
        targets = engine._identify_optimization_targets(segs)
        assert {t["reason"] for t in targets} == {"high_latency", "retries"}
        assert targets[0]["value"] == 6.0

    def test_identify_optimization_targets_no_canvas_context(self, db):
        engine = _make_alpha(db)
        segs = [SimpleNamespace(id="s1", canvas_context=None)]
        assert engine._identify_optimization_targets(segs) == []

    def test_compute_proxy_signals_empty(self, db):
        engine = _make_alpha(db)
        sig = engine._compute_proxy_signals([])
        assert sig["execution_success"] is True
        assert sig["pass_rate"] == 0
        assert sig["avg_execution_seconds"] == 0

    def test_compute_proxy_signals_mixed(self, db):
        engine = _make_alpha(db)
        sig = engine._compute_proxy_signals([
            {"passed": True, "execution_seconds": 0.1, "output": "ok"},
            {"passed": False, "execution_seconds": 0.3, "output": "SyntaxError: x"},
        ])
        assert sig["execution_success"] is False
        assert sig["pass_rate"] == 0.5
        assert sig["avg_execution_seconds"] == 0.2
        assert sig["syntax_error"] is True


# =============================================================================
# CapabilityGate
# =============================================================================


def _make_gate(db):
    from core.auto_dev.capability_gate import AutoDevCapabilityService

    return AutoDevCapabilityService(db)


class TestCapabilityGate:
    def test_is_at_least_valid(self):
        from core.auto_dev.capability_gate import is_at_least

        assert is_at_least("student", "student") is True
        assert is_at_least("autonomous", "intern") is True
        assert is_at_least("intern", "supervised") is False
        assert is_at_least("supervised", "autonomous") is False

    def test_is_at_least_invalid(self):
        from core.auto_dev.capability_gate import is_at_least

        assert is_at_least("god-mode", "intern") is False
        assert is_at_least("intern", "god-mode") is False

    def test_can_use_workspace_disabled(self, db):
        gate = _make_gate(db)
        assert gate.can_use("ag-1", "auto_dev.memento_skills",
                            {"auto_dev": {"enabled": False}}) is False

    def test_can_use_capability_toggle_off(self, db):
        gate = _make_gate(db)
        assert gate.can_use("ag-1", "auto_dev.memento_skills",
                            {"auto_dev": {"enabled": True, "memento_skills": False}}) is False

    def test_can_use_unknown_capability(self, db):
        gate = _make_gate(db)
        assert gate.can_use("ag-1", "auto_dev.nope",
                            {"auto_dev": {"enabled": True}}) is False

    def test_can_use_no_settings_requires_enabled(self, db):
        gate = _make_gate(db)
        assert gate.can_use("ag-1", "auto_dev.memento_skills", None) is False

    def test_can_use_maturity_ok(self, db, monkeypatch):
        gate = _make_gate(db)
        monkeypatch.setattr(gate, "_get_agent_maturity", lambda a, c: "supervised")
        assert gate.can_use("ag-1", "auto_dev.alpha_evolver",
                            {"auto_dev": {"enabled": True}}) is True

    def test_can_use_maturity_insufficient(self, db, monkeypatch):
        gate = _make_gate(db)
        monkeypatch.setattr(gate, "_get_agent_maturity", lambda a, c: "student")
        assert gate.can_use("ag-1", "auto_dev.alpha_evolver",
                            {"auto_dev": {"enabled": True}}) is False

    def test_graduation_property_lazy_load(self, db):
        gate = _make_gate(db)
        from core.auto_dev.capability_gate import AutoDevCapabilityService
        fake_grad = Mock()
        with patch.object(AutoDevCapabilityService, "_graduation_service", None, create=True), \
             patch("core.capability_graduation_service.CapabilityGraduationService",
                   return_value=fake_grad):
            assert gate.graduation is fake_grad

    def test_graduation_property_import_error(self, db, monkeypatch):
        monkeypatch.setitem(
            sys.modules, "core.capability_graduation_service",
            _empty_module("core.capability_graduation_service"),
        )
        gate = _make_gate(db)
        assert gate.graduation is None

    def test_record_usage_no_graduation(self, db, monkeypatch):
        monkeypatch.setitem(
            sys.modules, "core.capability_graduation_service",
            _empty_module("core.capability_graduation_service"),
        )
        gate = _make_gate(db)
        gate.record_usage("ag-1", "auto_dev.memento_skills", True)

    def test_record_usage_success(self, db, monkeypatch):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        fake_grad = Mock()
        gate = _make_gate(db)
        monkeypatch.setattr(
            AutoDevCapabilityService, "graduation", property(lambda self: fake_grad)
        )
        gate.record_usage("ag-1", "auto_dev.memento_skills", True)
        fake_grad.record_usage.assert_called_once_with(
            "ag-1", "auto_dev.memento_skills", True
        )

    def test_record_usage_graduation_raises(self, db, monkeypatch):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        fake_grad = Mock()
        fake_grad.record_usage.side_effect = RuntimeError("grad down")
        gate = _make_gate(db)
        monkeypatch.setattr(
            AutoDevCapabilityService, "graduation", property(lambda self: fake_grad)
        )
        gate.record_usage("ag-1", "auto_dev.memento_skills", True)

    def test_check_daily_limits_other_capability_true(self, db):
        gate = _make_gate(db)
        assert gate.check_daily_limits("ag-1", "auto_dev.background_evolution") is True

    def test_check_daily_limits_alpha_under(self, db):
        for i in range(3):
            db.add(ToolMutation(
                tenant_id="t-1", tool_name="t", mutated_code=f"c{i}",
                sandbox_status="pending",
            ))
        db.add(AgentRegistryRow(db, "ag-1", "t-1"))
        db.commit()
        gate = _make_gate(db)
        assert gate.check_daily_limits(
            "ag-1", "auto_dev.alpha_evolver",
            {"auto_dev": {"max_mutations_per_day": 10}},
        ) is True

    def test_check_daily_limits_alpha_over(self, db):
        for i in range(3):
            db.add(ToolMutation(
                tenant_id="t-1", tool_name="t", mutated_code=f"c{i}",
                sandbox_status="pending",
            ))
        db.add(AgentRegistryRow(db, "ag-1", "t-1"))
        db.commit()
        gate = _make_gate(db)
        assert gate.check_daily_limits(
            "ag-1", "auto_dev.alpha_evolver",
            {"auto_dev": {"max_mutations_per_day": 2}},
        ) is False

    def test_check_daily_limits_memento(self, db):
        for i in range(4):
            db.add(SkillCandidate(
                tenant_id="t-1", agent_id="ag-1", skill_name=f"s{i}",
                generated_code="code", validation_status="pending",
            ))
        db.commit()
        gate = _make_gate(db)
        assert gate.check_daily_limits(
            "ag-1", "auto_dev.memento_skills",
            {"auto_dev": {"max_skill_candidates_per_day": 5}},
        ) is True
        assert gate.check_daily_limits(
            "ag-1", "auto_dev.memento_skills",
            {"auto_dev": {"max_skill_candidates_per_day": 3}},
        ) is False

    def test_check_daily_limits_defaults(self, db):
        gate = _make_gate(db)
        assert gate.check_daily_limits(
            "ag-1", "auto_dev.alpha_evolver", None
        ) is True

    def test_check_daily_limits_exception_fails_closed(self, db, monkeypatch):
        gate = _make_gate(db)
        monkeypatch.setattr(db, "query", Mock(side_effect=RuntimeError("db down")))
        assert gate.check_daily_limits(
            "ag-1", "auto_dev.alpha_evolver",
            {"auto_dev": {"max_mutations_per_day": 10}},
        ) is False

    def test_notify_capability_unlocked(self, db):
        gate = _make_gate(db)
        payload = gate.notify_capability_unlocked("ag-1", "auto_dev.memento_skills")
        assert payload["type"] == "auto_dev_capability_unlocked"
        assert payload["action_required"] is True
        assert "Memento Skills" in payload["message"]

    def test_get_agent_maturity_no_graduation(self, db, monkeypatch):
        monkeypatch.setitem(
            sys.modules, "core.capability_graduation_service",
            _empty_module("core.capability_graduation_service"),
        )
        gate = _make_gate(db)
        assert gate._get_agent_maturity("ag-1", "auto_dev.memento_skills") == "student"

    def test_get_agent_maturity_success(self, db, monkeypatch):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        fake_grad = Mock()
        fake_grad.get_maturity = Mock(return_value="intern")
        gate = _make_gate(db)
        monkeypatch.setattr(
            AutoDevCapabilityService, "graduation", property(lambda self: fake_grad)
        )
        assert gate._get_agent_maturity("ag-1", "auto_dev.memento_skills") == "intern"

    def test_get_agent_maturity_raises_returns_student(self, db, monkeypatch):
        from core.auto_dev.capability_gate import AutoDevCapabilityService

        fake_grad = Mock()
        fake_grad.get_maturity = Mock(side_effect=RuntimeError("grad down"))
        gate = _make_gate(db)
        monkeypatch.setattr(
            AutoDevCapabilityService, "graduation", property(lambda self: fake_grad)
        )
        assert gate._get_agent_maturity("ag-1", "auto_dev.memento_skills") == "student"

    def test_get_agent_tenant_found(self, db):
        db.add(AgentRegistryRow(db, "ag-1", "t-1"))
        db.commit()
        gate = _make_gate(db)
        assert gate._get_agent_tenant("ag-1") == "t-1"

    def test_get_agent_tenant_not_found(self, db):
        gate = _make_gate(db)
        assert gate._get_agent_tenant("ag-missing") is None

    def test_get_agent_tenant_exception(self, db, monkeypatch):
        gate = _make_gate(db)
        monkeypatch.setattr(db, "query", Mock(side_effect=RuntimeError("db down")))
        assert gate._get_agent_tenant("ag-1") is None


def AgentRegistryRow(db, agent_id, tenant_id):
    from core.models import AgentRegistry

    return AgentRegistry(
        id=agent_id, tenant_id=tenant_id, name="Agent", category="Operations",
        module_path="core.agents.generic_agent", class_name="GenericAgent",
    )


# =============================================================================
# FitnessService
# =============================================================================


def _make_fitness(db):
    from core.auto_dev.fitness_service import FitnessService

    return FitnessService(db)


def _seed_variant(db, variant_id="v-1", tenant_id="t-1", score=None, signals=None):
    db.add(WorkflowVariant(
        id=variant_id, tenant_id=tenant_id, workflow_definition={},
        fitness_score=score, fitness_signals=signals, evaluation_status="pending",
    ))
    db.commit()
    return variant_id


class TestFitnessService:
    def test_initial_proxy_variant_missing(self, db):
        svc = _make_fitness(db)
        assert svc.evaluate_initial_proxy("v-missing", "t-1", {}) == 0.0

    def test_initial_proxy_success_approved(self, db):
        _seed_variant(db)
        svc = _make_fitness(db)
        score = svc.evaluate_initial_proxy("v-1", "t-1", {
            "syntax_error": False, "execution_success": True,
            "user_approved_proposal": True,
        })
        assert score == 1.0
        row = db.query(WorkflowVariant).get("v-1")
        assert row.fitness_score == 1.0
        assert row.evaluation_status == "pending"
        assert row.fitness_signals["proxy"]["execution_success"] is True
        assert row.last_evaluated_at is not None

    def test_initial_proxy_syntax_error_no_bonus(self, db):
        _seed_variant(db)
        svc = _make_fitness(db)
        score = svc.evaluate_initial_proxy("v-1", "t-1", {
            "syntax_error": True, "execution_success": True,
        })
        assert score == 0.0  # -1.0 + 0.3 clamped

    def test_initial_proxy_neutral_execution_failed(self, db):
        _seed_variant(db)
        svc = _make_fitness(db)
        score = svc.evaluate_initial_proxy("v-1", "t-1", {
            "syntax_error": False, "execution_success": False,
        })
        assert score == 0.0

    def test_initial_proxy_rejected_drops_score(self, db):
        _seed_variant(db)
        svc = _make_fitness(db)
        score = svc.evaluate_initial_proxy("v-1", "t-1", {
            "execution_success": True, "user_approved_proposal": False,
        })
        assert score == 0.0  # 0.5 - 0.5 clamped

    def test_initial_proxy_no_delayed_eval(self, db):
        _seed_variant(db)
        svc = _make_fitness(db)
        svc.evaluate_initial_proxy("v-1", "t-1", {
            "execution_success": True, "expects_delayed_eval": False,
        })
        row = db.query(WorkflowVariant).get("v-1")
        assert row.evaluation_status == "evaluated"

    def test_delayed_webhook_variant_missing(self, db):
        svc = _make_fitness(db)
        assert svc.evaluate_delayed_webhook("v-missing", "t-1", {}) == 0.0

    def test_delayed_webhook_positive_signals(self, db):
        _seed_variant(db, score=0.3)
        svc = _make_fitness(db)
        score = svc.evaluate_delayed_webhook("v-1", "t-1", {
            "invoice_created": True, "crm_conversion": True,
            "conversion_success": True,
        })
        assert score == 1.0  # 0.3 + 1.5 clamped

    def test_delayed_webhook_negative_signals(self, db):
        _seed_variant(db, score=0.9)
        svc = _make_fitness(db)
        score = svc.evaluate_delayed_webhook("v-1", "t-1", {
            "email_bounce": True, "error_signal": True,
        })
        assert score == pytest.approx(0.1)  # 0.9 - 0.8

    def test_delayed_webhook_conversion_value_scaling(self, db):
        _seed_variant(db, score=0.5)
        svc = _make_fitness(db)
        score = svc.evaluate_delayed_webhook("v-1", "t-1", {
            "conversion_value": 200.0,
        })
        assert score == 0.7  # 0.5 + 0.2

    def test_delayed_webhook_conversion_value_clamp(self, db):
        _seed_variant(db, score=0.5)
        svc = _make_fitness(db)
        score = svc.evaluate_delayed_webhook("v-1", "t-1", {
            "conversion_value": 50000.0,
        })
        assert score == 1.0  # 0.5 + min(0.5, 50) clamped

    def test_delayed_webhook_keeps_previous_signals(self, db):
        _seed_variant(db, score=0.4, signals={"proxy": {"execution_success": True}})
        svc = _make_fitness(db)
        svc.evaluate_delayed_webhook("v-1", "t-1", {"error_signal": True})
        row = db.query(WorkflowVariant).get("v-1")
        assert row.evaluation_status == "evaluated"
        assert row.fitness_signals["proxy"]["execution_success"] is True
        assert row.fitness_signals["external"]["error_signal"] is True

    def test_get_top_variants_filters_and_orders(self, db):
        _seed_variant(db, variant_id="v-top-1", score=0.9)
        _seed_variant(db, variant_id="v-top-2", score=0.4)
        _seed_variant(db, variant_id="v-top-3", score=None)
        svc = _make_fitness(db)
        top = svc.get_top_variants("t-1", limit=1)
        assert [v.id for v in top] == ["v-top-1"]

    def test_get_top_variants_all(self, db):
        _seed_variant(db, variant_id="v-a", score=0.2)
        _seed_variant(db, variant_id="v-b", score=0.8)
        svc = _make_fitness(db)
        ids = [v.id for v in svc.get_top_variants("t-1")]
        assert ids == ["v-b", "v-a"]


# =============================================================================
# MementoEngine
# =============================================================================


def _make_memento(db, **kwargs):
    from core.auto_dev.memento_engine import MementoEngine

    return MementoEngine(db=db, **kwargs)


class TestMementoEngine:
    def test_analyze_episode_full_parse(self, db):
        from core.models import AgentEpisode, EpisodeSegment

        db.add(AgentEpisode(
            id="ep-m-1", agent_id="ag-1", tenant_id="t-1",
            task_description="Summarize docs", maturity_at_time="intern",
            outcome="failure", success=False, status="failed",
        ))
        db.add(EpisodeSegment(
            id="seg-m-1", episode_id="ep-m-1", segment_type="skill_failure",
            sequence_order=1, content="Tool call: web_search - failed",
        ))
        db.add(EpisodeSegment(
            id="seg-m-2", episode_id="ep-m-1", segment_type="error",
            sequence_order=2, content="Tool call: summarizer - success",
        ))
        db.add(EpisodeSegment(
            id="seg-m-3", episode_id="ep-m-1", segment_type="error",
            sequence_order=3, content="Tool call: retriever",
        ))
        db.add(EpisodeSegment(
            id="seg-m-4", episode_id="ep-m-1", segment_type="error",
            sequence_order=4, content="failed with ValueError",
        ))
        db.commit()

        engine = _make_memento(db)
        result = asyncio.run(engine.analyze_episode("ep-m-1"))
        assert result["error_segments_count"] == 4
        calls = {c["tool_name"]: c["status"] for c in result["tool_calls_attempted"]}
        assert calls["web_search"] == "failed"
        assert calls["summarizer"] == "success"
        assert calls["retriever"] == "unknown"
        assert "ValueError" in result["error_trace"]
        assert result["tenant_id"] is None  # no user_id attr on model
        assert result["agent_id"] == "ag-1"
        assert result["suggested_skill_name"].startswith("auto_")

    def test_analyze_episode_with_user_id_attr(self, db, monkeypatch):
        engine = _make_memento(db)
        fake_q = MagicMock()
        fake_ep = SimpleNamespace(
            id="ep-x", agent_id="ag-1", user_id="u-9",
            task_description="task",
        )
        fake_q.filter.return_value.first.return_value = fake_ep
        fake_q.filter.return_value.all.return_value = []
        monkeypatch.setattr(db, "query", Mock(return_value=fake_q))
        result = asyncio.run(engine.analyze_episode("ep-x"))
        assert result["tenant_id"] == "u-9"

    def test_analyze_episode_not_found(self, db):
        engine = _make_memento(db)
        result = asyncio.run(engine.analyze_episode("ep-missing"))
        assert "not found" in result["error"]

    def test_analyze_episode_import_error(self, db, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.models", _empty_module("core.models"))
        engine = _make_memento(db)
        result = asyncio.run(engine.analyze_episode("ep-1"))
        assert result["error"] == "Episode models not available"

    def test_propose_code_change_no_llm(self, db, monkeypatch):
        engine = _make_memento(db)
        monkeypatch.setattr(engine, "_get_llm_service", lambda: None)
        code = asyncio.run(engine.propose_code_change({"task_description": "t"}))
        assert "LLM unavailable" in code

    def test_propose_code_change_with_tools(self, db):
        llm = AsyncMock()
        llm.generate_completion = AsyncMock(return_value={
            "content": "```python\ndef skill(x):\n    return x\n```",
        })
        engine = _make_memento(db, llm_service=llm)
        code = asyncio.run(engine.propose_code_change({
            "task_description": "Fix billing",
            "error_trace": "ValueError",
            "tool_calls_attempted": [{"tool_name": "billing_api"}],
        }))
        assert code == "def skill(x):\n    return x"
        prompt = llm.generate_completion.await_args.kwargs["messages"][1]["content"]
        assert "billing_api" in prompt

    def test_propose_code_change_no_tools(self, db):
        llm = AsyncMock()
        llm.generate_completion = AsyncMock(return_value={"content": "code"})
        engine = _make_memento(db, llm_service=llm)
        code = asyncio.run(engine.propose_code_change({
            "task_description": "Fix billing",
            "error_trace": "",
            "tool_calls_attempted": [],
        }))
        assert code == "code"

    def test_propose_code_change_llm_error(self, db):
        llm = AsyncMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        engine = _make_memento(db, llm_service=llm)
        code = asyncio.run(engine.propose_code_change({"task_description": "t"}))
        assert "Skill generation failed" in code

    def test_validate_change_no_sandbox(self, db, monkeypatch):
        engine = _make_memento(db)
        monkeypatch.setattr(engine, "_get_sandbox", lambda: None)
        result = asyncio.run(engine.validate_change("code", [{}], "t-1"))
        assert result["passed"] is False
        assert "Sandbox unavailable" in result["error"]

    def test_validate_change_all_pass(self, db):
        sandbox = _ok_sandbox([
            {"status": "success", "output": "1", "execution_seconds": 0.1},
        ])
        engine = _make_memento(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_change("code", [{"a": 1}], "t-1"))
        assert result["passed"] is True
        assert result["test_results"][0]["passed"] is True

    def test_validate_change_default_empty_inputs(self, db):
        sandbox = _ok_sandbox([{"status": "success", "output": "1", "execution_seconds": 0.1}])
        engine = _make_memento(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_change("code", None, "t-1"))
        assert result["passed"] is True

    def test_validate_change_some_fail(self, db):
        sandbox = _ok_sandbox([
            {"status": "success", "output": "1", "execution_seconds": 0.1},
            {"status": "failed", "output": "crash", "execution_seconds": 0.2},
        ])
        engine = _make_memento(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_change("code", [{"a": 1}, {"a": 2}], "t-1"))
        assert result["passed"] is False

    def test_validate_change_sandbox_raises(self, db):
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(side_effect=RuntimeError("sandbox died"))
        engine = _make_memento(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_change("code", [{"a": 1}], "t-1"))
        assert result["passed"] is False
        assert "Sandbox error" in result["test_results"][0]["output"]

    def test_generate_skill_candidate_with_analysis(self, db):
        engine = _make_memento(db)
        analysis = {
            "suggested_skill_name": "auto_parser",
            "failure_summary": "Failed: parse",
        }
        engine.propose_code_change = AsyncMock(return_value="def parser(): pass")
        candidate = asyncio.run(engine.generate_skill_candidate(
            tenant_id="t-1", agent_id="ag-1", episode_id="ep-1",
            failure_analysis=analysis,
        ))
        assert candidate.skill_name == "auto_parser"
        assert candidate.validation_status == "pending"
        assert candidate.generated_code == "def parser(): pass"
        assert db.query(SkillCandidate).get(candidate.id) is not None

    def test_generate_skill_candidate_runs_analysis(self, db):
        engine = _make_memento(db)
        engine.analyze_episode = AsyncMock(return_value={
            "suggested_skill_name": "auto_thing", "failure_summary": "s",
        })
        engine.propose_code_change = AsyncMock(return_value="code")
        candidate = asyncio.run(engine.generate_skill_candidate(
            tenant_id="t-1", agent_id="ag-1", episode_id="ep-1",
        ))
        engine.analyze_episode.assert_awaited_once_with("ep-1")
        assert candidate.source_episode_id == "ep-1"

    def test_generate_skill_candidate_default_name(self, db):
        engine = _make_memento(db)
        engine.analyze_episode = AsyncMock(return_value={"failure_summary": "s"})
        engine.propose_code_change = AsyncMock(return_value="code")
        candidate = asyncio.run(engine.generate_skill_candidate(
            tenant_id="t-1", agent_id="ag-1", episode_id="ep-1",
        ))
        assert candidate.skill_name.startswith("auto_skill_")

    def test_generate_skill_candidate_analysis_error_raises(self, db):
        engine = _make_memento(db)
        with pytest.raises(ValueError, match="Episode analysis failed"):
            asyncio.run(engine.generate_skill_candidate(
                tenant_id="t-1", agent_id="ag-1", episode_id="ep-1",
                failure_analysis={"error": "Episode ep-1 not found"},
            ))

    def test_validate_candidate_not_found(self, db):
        engine = _make_memento(db)
        result = asyncio.run(engine.validate_candidate("c-missing", "t-1"))
        assert "not found" in result["error"]

    def test_validate_candidate_passed(self, db):
        db.add(SkillCandidate(
            id="c-1", tenant_id="t-1", skill_name="s", generated_code="code",
            validation_status="pending",
        ))
        db.commit()
        sandbox = _ok_sandbox([{"status": "success", "output": "ok", "execution_seconds": 0.1}])
        engine = _make_memento(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_candidate("c-1", "t-1"))
        assert result["passed"] is True
        row = db.query(SkillCandidate).get("c-1")
        assert row.validation_status == "validated"
        assert row.fitness_score == 1.0
        assert row.validated_at is not None

    def test_validate_candidate_failed(self, db):
        db.add(SkillCandidate(
            id="c-2", tenant_id="t-1", skill_name="s", generated_code="bad(",
            validation_status="pending",
        ))
        db.commit()
        sandbox = _ok_sandbox([{"status": "failed", "output": "SyntaxError", "execution_seconds": 0.1}])
        engine = _make_memento(db, sandbox=sandbox)
        result = asyncio.run(engine.validate_candidate("c-2", "t-1"))
        assert result["passed"] is False
        row = db.query(SkillCandidate).get("c-2")
        assert row.validation_status == "failed"
        assert row.fitness_score is None

    def test_promote_skill_not_validated(self, db):
        db.add(SkillCandidate(
            id="c-3", tenant_id="t-1", skill_name="s", generated_code="code",
            validation_status="pending",
        ))
        db.commit()
        engine = _make_memento(db)
        result = asyncio.run(engine.promote_skill("c-3", "t-1"))
        assert result["error"] == "Candidate not found or not validated"

    def test_promote_skill_success(self, db, monkeypatch):
        db.add(SkillCandidate(
            id="c-4", tenant_id="t-1", skill_name="cool_skill",
            skill_description="desc", generated_code="code",
            validation_status="validated", source_episode_id="ep-1",
        ))
        db.commit()

        class FakeBuilder:
            def create_skill_package(self, tenant_id, metadata, scripts):
                assert metadata.name == "cool_skill"
                assert "cool_skill.py" in scripts
                return {"success": True, "skill_id": "sk-1"}

        monkeypatch.setattr(
            "core.skill_builder_service.SkillBuilderService", FakeBuilder,
        )
        engine = _make_memento(db)
        result = asyncio.run(engine.promote_skill("c-4", "t-1"))
        assert result["success"] is True
        row = db.query(SkillCandidate).get("c-4")
        assert row.validation_status == "promoted"
        assert row.promoted_at is not None

    def test_promote_skill_import_error(self, db, monkeypatch):
        db.add(SkillCandidate(
            id="c-5", tenant_id="t-1", skill_name="s", generated_code="code",
            validation_status="validated",
        ))
        db.commit()
        monkeypatch.setitem(
            sys.modules, "core.skill_builder_service",
            _empty_module("core.skill_builder_service"),
        )
        engine = _make_memento(db)
        result = asyncio.run(engine.promote_skill("c-5", "t-1"))
        assert result["error"] == "SkillBuilderService not available"

    def test_analyze_execution_full_trace(self, db):
        from core.models import AgentExecution, AgentReasoningStep

        db.add(AgentExecution(
            id="exec-1", agent_id="ag-1", tenant_id="t-1",
            status="completed", input_summary="Sort a list",
            result_summary="done", error_message="",
        ))
        db.add(AgentReasoningStep(
            id="rs-1", execution_id="exec-1", step_number=1, step_type="thought",
            thought="think", verified="verified",
        ))
        db.add(AgentReasoningStep(
            id="rs-2", execution_id="exec-1", step_number=2, step_type="action",
            action={"tool": "sort"}, verified="unverified",
        ))
        db.commit()

        engine = _make_memento(db)
        result = asyncio.run(engine.analyze_execution("exec-1"))
        assert result["status"] == "completed"
        assert result["step_count"] == 2
        assert result["result_summary"] == "done"
        assert result["tool_calls_attempted"] == [{"tool": "sort"}]
        assert result["failure_summary"] == "completed: Sort a list"
        assert result["suggested_skill_name"].startswith("auto_")

    def test_analyze_execution_with_error(self, db):
        from core.models import AgentExecution

        db.add(AgentExecution(
            id="exec-2", agent_id="ag-1", tenant_id="t-1",
            status="failed", input_summary="Crashy task",
            error_message="KeyError: 'x'",
        ))
        db.commit()
        engine = _make_memento(db)
        result = asyncio.run(engine.analyze_execution("exec-2"))
        assert "KeyError" in result["failure_summary"]

    def test_analyze_execution_not_found(self, db):
        engine = _make_memento(db)
        result = asyncio.run(engine.analyze_execution("exec-miss"))
        assert "not found" in result["error"]

    def test_analyze_execution_import_error(self, db, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.models", _empty_module("core.models"))
        engine = _make_memento(db)
        result = asyncio.run(engine.analyze_execution("exec-1"))
        assert result["error"] == "Execution models not available"

    def test_learn_from_execution_analysis_error(self, db):
        engine = _make_memento(db)
        engine.analyze_execution = AsyncMock(return_value={"error": "nope"})
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
        ))
        assert result["success"] is False

    def test_learn_from_execution_llm_failed(self, db):
        engine = _make_memento(db)
        engine.analyze_execution = AsyncMock(return_value={"status": "completed"})
        engine.propose_code_change = AsyncMock(
            return_value="# Skill generation failed: down",
        )
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
        ))
        assert result["success"] is False
        assert "LLM unavailable" in result["error"]

    def test_learn_from_execution_validation_failed(self, db):
        engine = _make_memento(db)
        engine.analyze_execution = AsyncMock(return_value={"status": "completed"})
        engine.propose_code_change = AsyncMock(return_value="def x(): pass")
        engine.validate_change = AsyncMock(return_value={"passed": False})
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
        ))
        assert result["success"] is False
        assert "validation" in result

    def test_learn_from_execution_invalid_name(self, db):
        engine = _make_memento(db)
        engine.analyze_execution = AsyncMock(return_value={"status": "completed"})
        engine.propose_code_change = AsyncMock(return_value="def x(): pass")
        engine.validate_change = AsyncMock(return_value={"passed": True})
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
            skill_name="!!!", description="d",
        ))
        assert result["error"] == "Invalid skill name"

    def test_learn_from_execution_package_failed(self, db, monkeypatch):
        engine = _make_memento(db)
        engine.analyze_execution = AsyncMock(return_value={
            "status": "completed", "suggested_skill_name": "auto_x",
            "failure_summary": "summary",
        })
        engine.propose_code_change = AsyncMock(return_value="def x(): pass")
        engine.validate_change = AsyncMock(return_value={"passed": True})

        class FakeBuilder:
            def create_skill_package(self, tenant_id, metadata, scripts):
                return {"success": False, "message": "write failed"}

        monkeypatch.setattr(
            "core.skill_builder_service.SkillBuilderService", FakeBuilder,
        )
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
        ))
        assert result["error"] == "write failed"

    def test_learn_from_execution_success(self, db, monkeypatch):
        engine = _make_memento(db)
        engine.analyze_execution = AsyncMock(return_value={
            "status": "completed", "suggested_skill_name": "auto_parser",
            "failure_summary": "summary",
        })
        engine.propose_code_change = AsyncMock(return_value="def x(): pass")
        engine.validate_change = AsyncMock(return_value={"passed": True})

        class FakeBuilder:
            def create_skill_package(self, tenant_id, metadata, scripts):
                return {"success": True, "skill_id": "sk-9"}

        class FakeRegistry:
            def __init__(self, session):
                pass

            async def import_skill(self, source, content, metadata):
                assert "Generated from execution exec-x" in content
                return {"success": True, "skill_id": "reg-1"}

        monkeypatch.setattr(
            "core.skill_builder_service.SkillBuilderService", FakeBuilder,
        )
        monkeypatch.setattr(
            "core.skill_registry_service.SkillRegistryService", FakeRegistry,
        )
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
            skill_name="My Custom Skill!", description="custom desc",
        ))
        assert result["success"] is True
        assert result["skill_name"] == "My Custom Skill!"
        assert result["registry"]["success"] is True

    def test_suggest_skill_name_derived(self):
        name = _make_memento(None)._suggest_skill_name("parse csv files quickly", "")
        assert name == "auto_parse_files_quickly"

    def test_suggest_skill_name_fallback(self):
        name = _make_memento(None)._suggest_skill_name("the and for with", "")
        assert name.startswith("auto_skill_")


# =============================================================================
# DynamicBenchmarkFetcher
# =============================================================================


@pytest.fixture()
def bench_env(tmp_path, monkeypatch):
    import core.dynamic_benchmark_fetcher as dbf

    monkeypatch.setattr(dbf, "BENCHMARK_CACHE_PATH", tmp_path / "benchmark_cache.json")
    fake_lmsys = MagicMock()
    fake_lmsys.fetch_leaderboard = AsyncMock(return_value={"gpt-4o": 100.0})
    fake_lmsys.elo_to_quality_score = Mock(side_effect=lambda elo: elo)
    fake_lmsys.close = AsyncMock()
    monkeypatch.setattr(dbf, "LMSYSClient", MagicMock(return_value=fake_lmsys))
    monkeypatch.setattr(dbf, "UniversalCacheService", MagicMock(return_value=MagicMock()))
    return dbf, fake_lmsys


class TestDynamicBenchmarkFetcher:
    def test_init_and_default_client(self, bench_env):
        dbf, fake_lmsys = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        assert fetcher.benchmark_cache == {}
        assert fetcher.last_fetch is None
        assert isinstance(fetcher.lmsys_client, MagicMock)
        fetcher2 = dbf.DynamicBenchmarkFetcher(cache_service=MagicMock())
        assert fetcher2.cache is not None

    def test_load_cache_valid(self, bench_env):
        dbf, _ = bench_env
        dbf.BENCHMARK_CACHE_PATH.write_text(
            '{"benchmarks": {"gpt-4o": 90.5}, "last_fetch": "2026-08-01T10:00:00"}'
        )
        fetcher = dbf.DynamicBenchmarkFetcher()
        assert fetcher.benchmark_cache == {"gpt-4o": 90.5}
        assert fetcher.last_fetch is not None

    def test_load_cache_no_last_fetch(self, bench_env):
        dbf, _ = bench_env
        dbf.BENCHMARK_CACHE_PATH.write_text('{"benchmarks": {"gpt-4o": 90.5}}')
        fetcher = dbf.DynamicBenchmarkFetcher()
        assert fetcher.last_fetch is None

    def test_load_cache_corrupt(self, bench_env):
        dbf, _ = bench_env
        dbf.BENCHMARK_CACHE_PATH.write_text("{not json")
        fetcher = dbf.DynamicBenchmarkFetcher()
        assert fetcher.benchmark_cache == {}

    def test_save_cache(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        fetcher.benchmark_cache = {"gpt-4o": 88.0}
        fetcher.last_fetch = datetime(2026, 8, 1, 12, 0, 0)
        fetcher._save_cache()
        data = __import__("json").loads(dbf.BENCHMARK_CACHE_PATH.read_text())
        assert data["benchmarks"] == {"gpt-4o": 88.0}
        assert data["source"] == "multi_source"

    def test_save_cache_exception(self, bench_env, monkeypatch):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        monkeypatch.setattr(
            "builtins.open", Mock(side_effect=OSError("disk full"))
        )
        fetcher._save_cache()  # must not raise

    def test_is_cache_valid(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        assert fetcher._is_cache_valid() is False  # no last_fetch
        fetcher.last_fetch = datetime.now()
        assert fetcher._is_cache_valid() is False  # no cache
        fetcher.benchmark_cache = {"gpt-4o": 1.0}
        assert fetcher._is_cache_valid() is True  # fresh
        fetcher.last_fetch = datetime.now() - timedelta(hours=7)
        assert fetcher._is_cache_valid() is False  # stale

    def test_get_client_reuses(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        client = asyncio.run(fetcher._get_client())
        assert fetcher._client is client
        assert asyncio.run(fetcher._get_client()) is client

    def test_get_client_no_ssl_default(self, bench_env, monkeypatch):
        dbf, _ = bench_env
        monkeypatch.delenv("BENCHMARK_FETCHER_INSECURE", raising=False)
        fetcher = dbf.DynamicBenchmarkFetcher()
        with patch("httpx.AsyncClient") as AC:
            asyncio.run(fetcher._get_client_no_ssl())
            assert AC.call_args.kwargs["verify"] is True

    def test_get_client_no_ssl_insecure(self, bench_env, monkeypatch):
        dbf, _ = bench_env
        monkeypatch.setenv("BENCHMARK_FETCHER_INSECURE", "true")
        fetcher = dbf.DynamicBenchmarkFetcher()
        with patch("httpx.AsyncClient") as AC:
            asyncio.run(fetcher._get_client_no_ssl())
            assert AC.call_args.kwargs["verify"] is False

    def test_close_with_client(self, bench_env):
        dbf, fake_lmsys = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        client = MagicMock()
        client.aclose = AsyncMock()
        fetcher._client = client
        asyncio.run(fetcher.close())
        client.aclose.assert_awaited_once()
        assert fetcher._client is None
        fake_lmsys.close.assert_awaited_once()

    def test_close_without_client(self, bench_env):
        dbf, fake_lmsys = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        asyncio.run(fetcher.close())
        fake_lmsys.close.assert_awaited_once()

    def test_fetch_from_lmsys_success(self, bench_env):
        dbf, fake_lmsys = bench_env
        fake_lmsys.fetch_leaderboard = AsyncMock(
            return_value={"gpt-4o": 92.5, "claude-3.5-sonnet": 91.2}
        )
        fetcher = dbf.DynamicBenchmarkFetcher()
        scores = asyncio.run(fetcher.fetch_from_lmsys())
        assert scores == {"gpt-4o": 92.5, "claude-3.5-sonnet": 91.2}
        fake_lmsys.fetch_leaderboard.assert_awaited_once_with(use_cache=True)

    def test_fetch_from_lmsys_exception(self, bench_env):
        dbf, fake_lmsys = bench_env
        fake_lmsys.fetch_leaderboard = AsyncMock(side_effect=RuntimeError("lmsys down"))
        fetcher = dbf.DynamicBenchmarkFetcher()
        assert asyncio.run(fetcher.fetch_from_lmsys()) == {}

    def _client_with_response(self, data):
        resp = MagicMock()
        resp.raise_for_status = Mock()
        resp.json = Mock(return_value=data)
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        return client

    def test_fetch_from_artificial_analysis_success(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        client = self._client_with_response({"models": [
            {"name": "gpt-4o", "rating": 92.5},
            {"name": "claude-3.5-sonnet", "score": 91.2},
            {"name": "gemini", "performance": 85.0},
        ]})
        with patch.object(fetcher, "_get_client", AsyncMock(return_value=client)):
            scores = asyncio.run(fetcher.fetch_from_artificial_analysis())
        assert scores["gpt-4o"] == 92.5
        assert scores["claude-3.5-sonnet"] == 91.2
        assert scores["gemini"] == 85.0
        client.get.assert_awaited_once_with(dbf.ARTIFICIAL_ANALYSIS_URL)

    def test_fetch_from_artificial_analysis_normalize_and_skip(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        client = self._client_with_response({"models": [
            {"name": "big-model", "rating": 950.0},   # > 100 → /10 → 95
            {"name": "bad-model", "rating": "n/a"},   # ValueError → skipped
            {"name": "no-rating"},                     # no rating → skipped
        ]})
        with patch.object(fetcher, "_get_client", AsyncMock(return_value=client)):
            scores = asyncio.run(fetcher.fetch_from_artificial_analysis())
        assert scores == {"big-model": 95.0}

    def test_fetch_from_artificial_analysis_exception(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("http fail"))
        with patch.object(fetcher, "_get_client", AsyncMock(return_value=client)):
            assert asyncio.run(fetcher.fetch_from_artificial_analysis()) == {}

    def test_fetch_from_benchmark_moe_success(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        client = self._client_with_response({"models": [
            {"id": "model-a", "benchmarks": {"mmlu": 90.0, "gsm8k": 80.0}},
            {"name": "model-b", "benchmarks": {"bbh": 70.0, "str": "x"}},
            {"id": "model-c", "benchmarks": {}},
            {"id": "model-d"},
        ]})
        with patch.object(fetcher, "_get_client_no_ssl", AsyncMock(return_value=client)):
            scores = asyncio.run(fetcher.fetch_from_benchmark_moe())
        assert scores["model-a"] == 85.0
        assert scores["model-b"] == 70.0
        assert "model-c" not in scores
        client.get.assert_awaited_once_with(dbf.BENCHMARK_MOE_URL)

    def test_fetch_from_benchmark_moe_clamp(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        client = self._client_with_response({"models": [
            {"id": "huge", "benchmarks": {"x": 500.0, "y": 200.0}},
        ]})
        with patch.object(fetcher, "_get_client_no_ssl", AsyncMock(return_value=client)):
            scores = asyncio.run(fetcher.fetch_from_benchmark_moe())
        assert scores["huge"] == 100.0

    def test_fetch_from_benchmark_moe_exception(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("moe down"))
        with patch.object(fetcher, "_get_client_no_ssl", AsyncMock(return_value=client)):
            assert asyncio.run(fetcher.fetch_from_benchmark_moe()) == {}

    def test_merge_benchmark_scores_empty(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        assert fetcher.merge_benchmark_scores([]) == {}

    def test_merge_benchmark_scores_single(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        merged = fetcher.merge_benchmark_scores([{"gpt-4o": 90.0}])
        assert merged["gpt-4o"] == 90.0

    def test_merge_benchmark_scores_weighted(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        merged = fetcher.merge_benchmark_scores([
            {"gpt-4o": 90.0, "claude": 80.0},
            {"gpt-4o": 70.0},
        ])
        # gpt-4o: (90*0.6 + 70*0.3)/0.9 = (54+21)/0.9 = 83.33
        assert merged["gpt-4o"] == pytest.approx(83.33, abs=0.01)
        # claude: only in source 0 → 80.0
        assert merged["claude"] == 80.0

    def test_merge_benchmark_scores_four_sources(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        merged = fetcher.merge_benchmark_scores([
            {"m": 100.0}, {}, {}, {"m": 0.0},
        ])
        # source index 3 → weight 0.1 → (100*0.6 + 0*0.1)/0.7
        assert merged["m"] == pytest.approx(85.714, abs=0.01)

    def test_refresh_benchmarks_uses_cache(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        fetcher.last_fetch = datetime.now()
        fetcher.benchmark_cache = {"gpt-4o": 88.0}
        scores = asyncio.run(fetcher.refresh_benchmarks())
        assert scores == {"gpt-4o": 88.0}

    def test_refresh_benchmarks_lmsys_success(self, bench_env):
        dbf, fake_lmsys = bench_env
        fake_lmsys.fetch_leaderboard = AsyncMock(return_value={
            f"model-{i}": float(i) for i in range(12)
        })
        fetcher = dbf.DynamicBenchmarkFetcher()
        scores = asyncio.run(fetcher.refresh_benchmarks(force=True))
        assert len(scores) == 12
        assert fetcher.last_fetch is not None
        assert dbf.BENCHMARK_CACHE_PATH.exists()

    def test_refresh_benchmarks_lmsys_too_few_uses_alternatives(self, bench_env):
        dbf, fake_lmsys = bench_env
        fake_lmsys.fetch_leaderboard = AsyncMock(return_value={"gpt-4o": 90.0})
        fetcher = dbf.DynamicBenchmarkFetcher()
        with patch.object(fetcher, "fetch_from_artificial_analysis",
                          AsyncMock(return_value={"gpt-4o": 95.0, "claude": 80.0})), \
             patch.object(fetcher, "fetch_from_benchmark_moe",
                          AsyncMock(return_value={"gpt-4o": 70.0})):
            scores = asyncio.run(fetcher.refresh_benchmarks(force=True))
        assert "gpt-4o" in scores
        assert "claude" in scores
        assert fetcher.last_fetch is not None

    def test_refresh_benchmarks_alternative_exception_results(self, bench_env):
        dbf, fake_lmsys = bench_env
        fake_lmsys.fetch_leaderboard = AsyncMock(return_value={})
        fetcher = dbf.DynamicBenchmarkFetcher()
        with patch.object(fetcher, "fetch_from_artificial_analysis",
                          AsyncMock(side_effect=RuntimeError("aa down"))), \
             patch.object(fetcher, "fetch_from_benchmark_moe",
                          AsyncMock(return_value={"m": 50.0})):
            scores = asyncio.run(fetcher.refresh_benchmarks(force=True))
        assert scores == {"m": 50.0}

    def test_refresh_benchmarks_static_fallback(self, bench_env):
        dbf, fake_lmsys = bench_env
        fake_lmsys.fetch_leaderboard = AsyncMock(return_value={})
        fetcher = dbf.DynamicBenchmarkFetcher()
        with patch.object(fetcher, "fetch_from_artificial_analysis", AsyncMock(return_value={})), \
             patch.object(fetcher, "fetch_from_benchmark_moe", AsyncMock(return_value={})):
            scores = asyncio.run(fetcher.refresh_benchmarks(force=True))
        from core.benchmarks import MODEL_QUALITY_SCORES

        assert scores == MODEL_QUALITY_SCORES
        assert dbf.BENCHMARK_CACHE_PATH.exists()

    def test_refresh_benchmarks_no_fallback(self, bench_env):
        dbf, fake_lmsys = bench_env
        fake_lmsys.fetch_leaderboard = AsyncMock(return_value={})
        fetcher = dbf.DynamicBenchmarkFetcher()
        with patch.object(fetcher, "fetch_from_artificial_analysis", AsyncMock(return_value={})), \
             patch.object(fetcher, "fetch_from_benchmark_moe", AsyncMock(return_value={})):
            scores = asyncio.run(fetcher.refresh_benchmarks(force=True, use_static_fallback=False))
        assert scores == {}

    def test_get_static_benchmarks_import_error(self, bench_env, monkeypatch):
        dbf, _ = bench_env
        monkeypatch.setitem(sys.modules, "core.benchmarks", _empty_module("core.benchmarks"))
        fetcher = dbf.DynamicBenchmarkFetcher()
        assert fetcher._get_static_benchmarks() == {}

    def test_get_benchmark_score_exact(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        fetcher.benchmark_cache = {"gpt-4o": 92.0}
        assert fetcher.get_benchmark_score("gpt-4o") == 92.0

    def test_get_benchmark_score_partial(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        fetcher.benchmark_cache = {"GPT-4o-2024-05-13": 92.0}
        assert fetcher.get_benchmark_score("gpt-4o") == 92.0
        assert fetcher.get_benchmark_score("gpt-4o-2024-05-13") == 92.0

    def test_get_benchmark_score_missing(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        fetcher.benchmark_cache = {"claude": 90.0}
        assert fetcher.get_benchmark_score("gemini") is None

    def test_get_capability_score_no_adjustment(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        fetcher.benchmark_cache = {"gpt-4o": 90.0}
        assert fetcher.get_capability_score("gpt-4o", "vision") == 95.0  # +5
        assert fetcher.get_capability_score("gpt-4o", "unknown_cap") == 90.0

    def test_get_capability_score_base_none_with_adjustment(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        fetcher.benchmark_cache = {}
        assert fetcher.get_capability_score("lux-1.0", "computer_use") == 75.0  # 70 + 5
        assert fetcher.get_capability_score("gemini-2.0-flash", "vision") == 73.0
        assert fetcher.get_capability_score("claude-3.5-sonnet", "tools") == 74.0
        assert fetcher.get_capability_score("unknown", "vision") is None

    def test_get_capability_score_clamp(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        fetcher.benchmark_cache = {"claude-3.5-sonnet": 99.0}
        assert fetcher.get_capability_score("claude-3.5-sonnet", "computer_use") == 100.0

    def test_get_top_models(self, bench_env):
        dbf, _ = bench_env
        fetcher = dbf.DynamicBenchmarkFetcher()
        fetcher.benchmark_cache = {
            "a": 90.0, "b": 95.0, "c": 50.0, "d": 85.0,
        }
        top = fetcher.get_top_models(limit=2, min_score=80.0)
        assert top == [("b", 95.0), ("a", 90.0)]
        assert len(fetcher.get_top_models()) == 3

    def test_get_benchmark_fetcher_singleton(self, bench_env, monkeypatch):
        dbf, _ = bench_env
        monkeypatch.setattr(dbf, "_benchmark_fetcher", None)
        f1 = dbf.get_benchmark_fetcher()
        f2 = dbf.get_benchmark_fetcher()
        assert f1 is f2

    def test_refresh_benchmark_cache_convenience(self, bench_env, monkeypatch):
        dbf, _ = bench_env
        fake = MagicMock()
        fake.refresh_benchmarks = AsyncMock(return_value={"m": 1.0})
        monkeypatch.setattr(dbf, "get_benchmark_fetcher", lambda: fake)
        result = asyncio.run(dbf.refresh_benchmark_cache(force=True))
        assert result == {"m": 1.0}
        fake.refresh_benchmarks.assert_awaited_once_with(force=True)


# =============================================================================
# CostConfig
# =============================================================================


class TestCostConfig:
    def test_get_llm_cost_exact(self):
        from core.cost_config import get_llm_cost

        cost = get_llm_cost("gpt-4o", 1000, 500)
        assert cost == pytest.approx(1000 * 0.00003 + 500 * 0.00006)

    def test_get_llm_cost_suffix_normalized(self):
        from core.cost_config import get_llm_cost

        cost = get_llm_cost("gpt-4o-2024-05-13", 1000, 500)
        assert cost == pytest.approx(1000 * 0.00003 + 500 * 0.00006)

    def test_get_llm_cost_unknown_model_none(self):
        from core.cost_config import get_llm_cost

        assert get_llm_cost("brand-new-model", 10, 10) is None

    def test_get_llm_cost_zero_tokens(self):
        from core.cost_config import get_llm_cost

        assert get_llm_cost("gpt-4o", 0, 0) == 0.0

    def test_get_llm_cost_partial_prefix(self):
        from core.cost_config import get_llm_cost

        # "claude-3-5-sonnet" appears in "claude-3-5-sonnet-20241022"
        cost = get_llm_cost("claude-3-5-sonnet-20241022", 1000, 1000)
        assert cost == pytest.approx(1000 * 0.000015 + 1000 * 0.000075)

    def test_get_model_tier_free(self):
        from core.cost_config import get_model_tier

        tier = get_model_tier("free")
        assert "gpt-4o-mini" in tier
        assert "gpt-4o" not in tier

    def test_get_model_tier_pro_case_insensitive(self):
        from core.cost_config import get_model_tier

        tier = get_model_tier("PRO")
        assert "gpt-4o" in tier
        assert "gpt-4o-mini" in tier

    def test_get_model_tier_enterprise_wildcard(self):
        from core.cost_config import get_model_tier

        assert get_model_tier("enterprise") == "*"

    def test_get_model_tier_unknown_defaults_free(self):
        from core.cost_config import get_model_tier

        tier = get_model_tier("ultra-plan")
        assert tier == get_model_tier("free")

    def test_is_byok_enabled(self):
        from core.cost_config import is_byok_enabled

        assert is_byok_enabled("enterprise") is True
        assert is_byok_enabled("Pro") is True
        assert is_byok_enabled("free") is False
        assert is_byok_enabled("trial") is False
