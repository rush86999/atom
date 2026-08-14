# -*- coding: utf-8 -*-
"""Coverage wave 84c (auto-dev part 2) — 8 core/auto_dev modules.

EXTENDS the w82a/w104/2026-08-08 auto_dev suites (before-% measured 100%
for 7 modules, 97% for container_sandbox). This file re-derives >=95%
standalone coverage for every module listed below:

  core/auto_dev/base_engine.py        (100% before)
  core/auto_dev/event_hooks.py        (100% before)
  core/auto_dev/evolution_engine.py   (100% before)
  core/auto_dev/models.py             (100% before)
  core/auto_dev/mutation_rollback.py  (100% before)
  core/auto_dev/reflection_engine.py  (100% before)
  core/auto_dev/regression_validator.py (100% before)
  core/auto_dev/container_sandbox.py  (97% before — closes 206/215-216:
                                       _kill_docker_container empty-cid + exception)

Style: mocked deps, zero LLM spend, no network, no real DB (in-memory
SQLAlchemy where a session is needed). Imports never fire Docker, LLM keys,
or the filesystem except under explicit tmp_path fixtures.
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.auto_dev.base_engine import BaseLearningEngine, SandboxProtocol
from core.auto_dev.container_sandbox import ContainerSandbox
from core.auto_dev.event_hooks import (
    EventBus,
    SkillExecutionEvent,
    TaskEvent,
    event_bus,
)
from core.auto_dev.evolution_engine import (
    LATENCY_THRESHOLD_SECONDS,
    TOKEN_THRESHOLD,
    EvolutionEngine,
)
from core.auto_dev.models import (
    HypothesisTreeRecord,
    SkillCandidate,
    ToolMutation,
    WorkflowVariant,
)
from core.auto_dev.mutation_rollback import (
    MutationRollbackRegistry,
    MutationSnapshot,
    get_rollback_registry,
)
from core.auto_dev.reflection_engine import ReflectionEngine
from core.auto_dev.regression_validator import (
    RegressionResult,
    RegressionValidator,
    TestMismatch,
)


# ============================================================================
# core/auto_dev/models.py — declarative models + default lambdas
# ============================================================================


@pytest.fixture(scope="module")
def db_engine():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from core.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db(db_engine):
    from sqlalchemy.orm import sessionmaker

    session = sessionmaker(bind=db_engine)()
    yield session
    session.rollback()
    session.close()


class TestModels:
    def test_tool_mutation_defaults_fire(self, db):
        m = ToolMutation(
            tenant_id="t1",
            tool_name="tool",
            mutated_code="print(1)",
        )
        db.add(m)
        db.flush()
        assert m.id and len(m.id) == 36
        assert m.sandbox_status == "pending"
        assert m.execution_error is None
        assert m.created_at is not None
        assert m.parent_tool_id is None

    def test_tool_mutation_all_fields(self):
        now = datetime.now(timezone.utc)
        m = ToolMutation(
            id="fixed-id",
            tenant_id="t1",
            parent_tool_id="parent-1",
            tool_name="tool",
            mutated_code="print(2)",
            sandbox_status="passed",
            execution_error="err",
            created_at=now,
        )
        assert m.id == "fixed-id"
        assert m.parent_tool_id == "parent-1"
        assert m.sandbox_status == "passed"
        assert m.execution_error == "err"
        assert m.created_at == now

    def test_workflow_variant_defaults_fire(self, db):
        v = WorkflowVariant(tenant_id="t1", workflow_definition={"steps": []})
        db.add(v)
        db.flush()
        assert v.id and len(v.id) == 36
        assert v.parent_variant_id is None
        assert v.agent_id is None
        assert v.fitness_score is None
        assert v.fitness_signals is None
        assert v.evaluation_status == "pending"
        assert v.created_at is not None
        assert v.last_evaluated_at is None

    def test_workflow_variant_all_fields(self):
        now = datetime.now(timezone.utc)
        v = WorkflowVariant(
            id="wf-1",
            tenant_id="t1",
            parent_variant_id="wf-0",
            agent_id="a1",
            workflow_definition={"x": 1},
            fitness_score=0.9,
            fitness_signals={"latency": 1.0},
            evaluation_status="evaluated",
            created_at=now,
            last_evaluated_at=now,
        )
        assert v.fitness_score == 0.9
        assert v.evaluation_status == "evaluated"
        assert v.last_evaluated_at == now

    def test_skill_candidate_defaults_fire(self, db):
        c = SkillCandidate(
            tenant_id="t1",
            skill_name="s1",
            generated_code="print(1)",
        )
        db.add(c)
        db.flush()
        assert c.id and len(c.id) == 36
        assert c.agent_id is None
        assert c.source_episode_id is None
        assert c.skill_description is None
        assert c.failure_pattern is None
        assert c.validation_status == "pending"
        assert c.validation_result is None
        assert c.fitness_score is None
        assert c.created_at is not None
        assert c.validated_at is None
        assert c.promoted_at is None

    def test_skill_candidate_all_fields(self):
        now = datetime.now(timezone.utc)
        c = SkillCandidate(
            id="c-1",
            tenant_id="t1",
            agent_id="a1",
            source_episode_id="e1",
            skill_name="s1",
            skill_description="desc",
            generated_code="print(1)",
            failure_pattern={"msg": "boom"},
            validation_status="promoted",
            validation_result={"ok": True},
            fitness_score=0.8,
            created_at=now,
            validated_at=now,
            promoted_at=now,
        )
        assert c.validation_status == "promoted"
        assert c.fitness_score == 0.8
        assert c.validated_at == now
        assert c.promoted_at == now

    def test_hypothesis_tree_record_defaults_fire(self, db):
        h = HypothesisTreeRecord(
            tenant_id="t1",
            task_description="task",
        )
        db.add(h)
        db.flush()
        assert h.id and len(h.id) == 36
        assert h.task_type == "coding"
        assert h.tier == "solo"
        assert h.session_id is None
        assert h.total_nodes == 0
        assert h.successful_nodes == 0
        assert h.pruned_nodes == 0
        assert h.total_tokens_used == 0
        assert h.total_cost_usd == 0.0
        assert h.optimization_score is None
        assert h.winning_path is None
        assert h.negative_constraints is None
        assert h.tree_snapshot is None
        assert h.created_at is not None
        assert h.completed_at is None

    def test_hypothesis_tree_record_all_fields(self):
        now = datetime.now(timezone.utc)
        h = HypothesisTreeRecord(
            id="h-1",
            tenant_id="t1",
            task_description="task",
            task_type="workflow",
            tier="enterprise",
            session_id="s-1",
            total_nodes=10,
            successful_nodes=5,
            pruned_nodes=3,
            total_tokens_used=100,
            total_cost_usd=0.5,
            optimization_score=0.9,
            winning_path=["a", "b"],
            negative_constraints=["x"],
            tree_snapshot={"nodes": []},
            created_at=now,
            completed_at=now,
        )
        assert h.optimization_score == 0.9
        assert h.completed_at == now

    def test_table_names(self):
        assert ToolMutation.__tablename__ == "tool_mutations"
        assert WorkflowVariant.__tablename__ == "workflow_variants"
        assert SkillCandidate.__tablename__ == "skill_candidates"
        assert HypothesisTreeRecord.__tablename__ == "hypothesis_trees"


# ============================================================================
# core/auto_dev/base_engine.py
# ============================================================================


class _ConcreteEngine(BaseLearningEngine):
    async def analyze_episode(self, episode_id: str, **kwargs) -> dict:
        return {"episode_id": episode_id}

    async def propose_code_change(self, context: dict, **kwargs) -> str:
        return "generated_code"

    async def validate_change(self, code: str, test_inputs: list, tenant_id: str, **kwargs) -> dict:
        return {"passed": True}


class _FakeSandbox:
    async def execute_raw_python(self, tenant_id, code, input_params, timeout=60, safety_level="MEDIUM_RISK", **kwargs):
        return {"status": "success", "output": "ok", "execution_seconds": 0.1, "execution_id": "e"}


class TestBaseLearningEngine:
    def test_init_attributes(self):
        db = object()
        llm = object()
        sandbox = object()
        engine = _ConcreteEngine(db=db, llm_service=llm, sandbox=sandbox)
        assert engine.db is db
        assert engine.llm is llm
        assert engine.sandbox is sandbox

    def test_init_defaults_none(self):
        engine = _ConcreteEngine(db=object())
        assert engine.llm is None
        assert engine.sandbox is None

    def test_abstract_methods_are_abstract(self):
        with pytest.raises(TypeError):
            BaseLearningEngine(db=object())  # type: ignore[abstract]

    def test_sandbox_protocol_is_runtime_checkable(self):
        assert isinstance(_FakeSandbox(), SandboxProtocol)
        assert issubclass(_FakeSandbox, SandboxProtocol)
        assert not isinstance(object(), SandboxProtocol)
        # Python 3.12-only protocol introspection helpers — tolerate 3.11.
        try:
            from typing import _is_protocol, _is_runtime_protocol

            assert _is_protocol(SandboxProtocol)
            assert _is_runtime_protocol(SandboxProtocol)
        except ImportError:  # pragma: no cover
            pass

    def test_concrete_engine_lifecycle(self):
        engine = _ConcreteEngine(db=object())

        async def run():
            analysis = await engine.analyze_episode("e-1")
            code = await engine.propose_code_change(analysis)
            result = await engine.validate_change(code, [{"x": 1}], "t1")
            return analysis, code, result

        analysis, code, result = asyncio.run(run())
        assert analysis == {"episode_id": "e-1"}
        assert code == "generated_code"
        assert result == {"passed": True}

    def test_get_llm_service_returns_injected(self):
        llm = object()
        engine = _ConcreteEngine(db=object(), llm_service=llm)
        assert engine._get_llm_service() is llm

    def test_get_llm_service_imports_global(self):
        engine = _ConcreteEngine(db=object())
        fake = object()
        with patch("core.llm_service.get_llm_service", return_value=fake):
            assert engine._get_llm_service() is fake
        assert engine.llm is fake  # cached

    def test_get_llm_service_fallback_none(self):
        engine = _ConcreteEngine(db=object())

        def boom():
            raise RuntimeError("no llm")

        with patch("core.llm_service.get_llm_service", side_effect=boom):
            assert engine._get_llm_service() is None

    def test_get_sandbox_returns_injected(self):
        sandbox = object()
        engine = _ConcreteEngine(db=object(), sandbox=sandbox)
        assert engine._get_sandbox() is sandbox

    def test_get_sandbox_constructs_container_sandbox(self):
        engine = _ConcreteEngine(db=object())
        fake_sandbox = _FakeSandbox()
        with patch("core.auto_dev.container_sandbox.ContainerSandbox", return_value=fake_sandbox):
            assert engine._get_sandbox() is fake_sandbox
        assert engine.sandbox is fake_sandbox  # cached

    def test_get_sandbox_fallback_none(self):
        engine = _ConcreteEngine(db=object())

        def boom():
            raise RuntimeError("no docker")

        with patch("core.auto_dev.container_sandbox.ContainerSandbox", side_effect=boom):
            assert engine._get_sandbox() is None

    def test_strip_markdown_fences_python(self):
        engine = _ConcreteEngine(db=object())
        assert engine._strip_markdown_fences("```python\nprint(1)\n```") == "print(1)"

    def test_strip_markdown_fences_generic(self):
        engine = _ConcreteEngine(db=object())
        assert engine._strip_markdown_fences("```\nprint(1)\n```") == "print(1)"

    def test_strip_markdown_fences_no_fence(self):
        engine = _ConcreteEngine(db=object())
        assert engine._strip_markdown_fences("  print(1)  ") == "print(1)"

    def test_strip_markdown_fences_trailing_only(self):
        engine = _ConcreteEngine(db=object())
        assert engine._strip_markdown_fences("print(1)\n```") == "print(1)"


# ============================================================================
# core/auto_dev/event_hooks.py
# ============================================================================


class TestEventBus:
    def test_task_event_defaults(self):
        ev = TaskEvent(episode_id="e1", agent_id="a1", tenant_id="t1")
        assert ev.task_description == ""
        assert ev.error_trace is None
        assert ev.outcome == ""
        assert ev.metadata == {}
        ev2 = TaskEvent(
            episode_id="e1",
            agent_id="a1",
            tenant_id="t1",
            task_description="d",
            error_trace="trace",
            outcome="failure",
            metadata={"k": "v"},
        )
        assert ev2.outcome == "failure"
        assert ev2.metadata == {"k": "v"}

    def test_skill_execution_event_defaults(self):
        ev = SkillExecutionEvent(execution_id="x1", agent_id="a1", tenant_id="t1", skill_id="s1")
        assert ev.skill_name == ""
        assert ev.execution_seconds == 0.0
        assert ev.token_usage == 0
        assert ev.success is False
        assert ev.output == ""
        assert ev.metadata == {}

    async def test_emit_with_no_handlers_is_noop(self):
        bus = EventBus()
        await bus.emit_task_fail(TaskEvent("e", "a", "t"))
        await bus.emit_task_success(TaskEvent("e", "a", "t"))
        await bus.emit_skill_execution(SkillExecutionEvent("x", "a", "t", "s"))

    def test_decorators_register_and_return_handler(self):
        bus = EventBus()

        async def h1(event):
            pass

        async def h2(event):
            pass

        async def h3(event):
            pass

        assert bus.on_task_fail(h1) is h1
        assert bus.on_task_success(h2) is h2
        assert bus.on_skill_execution(h3) is h3
        assert bus._fail_handlers == [h1]
        assert bus._success_handlers == [h2]
        assert bus._skill_handlers == [h3]

    async def test_emit_task_fail_dispatches(self):
        bus = EventBus()
        seen = []

        async def h(event):
            seen.append(event)

        bus.on_task_fail(h)
        event = TaskEvent("e", "a", "t")
        await bus.emit_task_fail(event)
        assert seen == [event]

    async def test_emit_task_success_dispatches(self):
        bus = EventBus()
        seen = []

        async def h(event):
            seen.append(event)

        bus.on_task_success(h)
        event = TaskEvent("e", "a", "t", outcome="success")
        await bus.emit_task_success(event)
        assert seen == [event]

    async def test_emit_skill_execution_dispatches(self):
        bus = EventBus()
        seen = []

        async def h(event):
            seen.append(event)

        bus.on_skill_execution(h)
        event = SkillExecutionEvent("x", "a", "t", "s", success=True)
        await bus.emit_skill_execution(event)
        assert seen == [event]

    async def test_dispatch_continues_after_handler_error(self):
        bus = EventBus()
        order = []

        async def boom(event):
            order.append("boom")
            raise RuntimeError("handler exploded")

        async def ok(event):
            order.append("ok")

        bus.on_task_fail(boom)
        bus.on_task_fail(ok)
        await bus.emit_task_fail(TaskEvent("e", "a", "t"))
        assert order == ["boom", "ok"]

    def test_clear_removes_all(self):
        bus = EventBus()

        async def h(event):
            pass

        bus.on_task_fail(h)
        bus.on_task_success(h)
        bus.on_skill_execution(h)
        bus.clear()
        assert bus._fail_handlers == []
        assert bus._success_handlers == []
        assert bus._skill_handlers == []

    def test_singleton_event_bus(self):
        assert isinstance(event_bus, EventBus)

    def test_register_through_event_bus(self):
        async def h(event):
            pass

        event_bus.clear()
        event_bus.on_skill_execution(h)
        assert event_bus._skill_handlers == [h]
        event_bus.clear()


# ============================================================================
# core/auto_dev/evolution_engine.py
# ============================================================================


def _skill_event(**overrides):
    defaults = dict(
        execution_id="x1",
        agent_id="agent-1",
        tenant_id="t1",
        skill_id="skill-1",
        skill_name="my_skill",
        execution_seconds=1.0,
        token_usage=100,
        success=True,
        output="ok",
    )
    defaults.update(overrides)
    return SkillExecutionEvent(**defaults)


class TestEvolutionEngine:
    def test_init_and_register(self):
        db = object()
        engine = EvolutionEngine(db)
        assert engine.db is db
        event_bus.clear()
        try:
            engine.register()
            assert event_bus._skill_handlers == [engine.process_execution]
        finally:
            event_bus.clear()

    def test_should_optimize_true(self):
        engine = EvolutionEngine(db=object())
        gate = MagicMock()
        gate.can_use.return_value = True
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate):
            with patch.object(engine, "_get_workspace_settings", return_value={"x": 1}):
                assert engine._should_optimize("agent-1", "t1") is True
        gate.can_use.assert_called_once_with(
            agent_id="agent-1",
            capability="auto_dev.background_evolution",
            workspace_settings={"x": 1},
        )

    def test_should_optimize_false(self):
        engine = EvolutionEngine(db=object())
        gate = MagicMock()
        gate.can_use.return_value = False
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate):
            assert engine._should_optimize("agent-1", "t1") is False

    def test_should_optimize_exception_returns_false(self):
        engine = EvolutionEngine(db=object())

        def boom(*a, **kw):
            raise RuntimeError("gate down")

        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", side_effect=boom):
            assert engine._should_optimize("agent-1", "t1") is False

    @pytest.mark.parametrize(
        "kwargs,expected",
        [
            (dict(execution_seconds=1.0, token_usage=100, success=True), None),
            (dict(execution_seconds=6.0, token_usage=100, success=True), "high_latency (6.0s)"),
            (dict(execution_seconds=1.0, token_usage=6000, success=True), "high_token_usage (6000)"),
            (dict(execution_seconds=1.0, token_usage=100, success=False), "execution_failure"),
            (
                dict(execution_seconds=6.0, token_usage=6000, success=False),
                "high_latency (6.0s), high_token_usage (6000), execution_failure",
            ),
        ],
    )
    def test_check_optimization_triggers(self, kwargs, expected):
        engine = EvolutionEngine(db=object())
        assert engine._check_optimization_triggers(_skill_event(**kwargs)) == expected

    def test_thresholds_constants(self):
        assert LATENCY_THRESHOLD_SECONDS == 5.0
        assert TOKEN_THRESHOLD == 5000

    async def test_process_execution_skipped_when_not_optimize(self):
        engine = EvolutionEngine(db=object())
        with patch.object(engine, "_should_optimize", return_value=False) as gate:
            with patch.object(engine, "_check_optimization_triggers") as triggers:
                await engine.process_execution(_skill_event())
        gate.assert_called_once()
        triggers.assert_not_called()

    async def test_process_execution_skipped_when_no_reason(self):
        engine = EvolutionEngine(db=object())
        with patch.object(engine, "_should_optimize", return_value=True):
            with patch.object(engine, "_check_optimization_triggers", return_value=None) as triggers:
                with patch.object(engine, "_trigger_alpha_evolver") as trigger:
                    await engine.process_execution(_skill_event())
        triggers.assert_called_once()
        trigger.assert_not_called()

    async def test_process_execution_triggers_optimization(self):
        engine = EvolutionEngine(db=object())
        event = _skill_event(execution_seconds=9.0)
        with patch.object(engine, "_should_optimize", return_value=True):
            with patch.object(engine, "_check_optimization_triggers", return_value="high_latency"):
                with patch.object(engine, "_trigger_alpha_evolver") as trigger:
                    await engine.process_execution(event)
        trigger.assert_awaited_once_with(event, "high_latency")

    async def test_trigger_alpha_evolver_success_passed(self):
        engine = EvolutionEngine(db=object())
        mutation = SimpleNamespace(id="mut-1")
        alpha = MagicMock()
        alpha.generate_tool_mutation = AsyncMock(return_value=mutation)
        alpha.sandbox_execute_mutation = AsyncMock(return_value={"success": True})
        fake_db = MagicMock()
        fake_db.close = Mock()
        with patch("core.database.SessionLocal", return_value=fake_db):
            with patch("core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine", return_value=alpha):
                with patch.object(engine, "_get_skill_code", return_value="print(1)"):
                    await engine._trigger_alpha_evolver(_skill_event(), "high_latency")
        alpha.generate_tool_mutation.assert_awaited_once()
        assert alpha.generate_tool_mutation.await_args.kwargs["base_code"] == "print(1)"
        assert "Optimize this skill for: high_latency." in alpha.generate_tool_mutation.await_args.kwargs["mutation_prompt"]
        alpha.sandbox_execute_mutation.assert_awaited_once_with(mutation_id="mut-1", tenant_id="t1", inputs={})
        fake_db.close.assert_called_once()

    async def test_trigger_alpha_evolver_success_failed(self):
        engine = EvolutionEngine(db=object())
        mutation = SimpleNamespace(id="mut-2")
        alpha = MagicMock()
        alpha.generate_tool_mutation = AsyncMock(return_value=mutation)
        alpha.sandbox_execute_mutation = AsyncMock(return_value={"success": False})
        fake_db = MagicMock()
        with patch("core.database.SessionLocal", return_value=fake_db):
            with patch("core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine", return_value=alpha):
                with patch.object(engine, "_get_skill_code", return_value="print(1)"):
                    await engine._trigger_alpha_evolver(_skill_event(), "execution_failure")
        alpha.sandbox_execute_mutation.assert_awaited_once()

    async def test_trigger_alpha_evolver_skill_code_missing(self):
        engine = EvolutionEngine(db=object())
        alpha = MagicMock()
        fake_db = MagicMock()
        with patch("core.database.SessionLocal", return_value=fake_db):
            with patch("core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine", return_value=alpha):
                with patch.object(engine, "_get_skill_code", return_value=None):
                    await engine._trigger_alpha_evolver(_skill_event(), "high_latency")
        alpha.generate_tool_mutation.assert_not_called()
        fake_db.close.assert_called_once()

    async def test_trigger_alpha_evolver_exception_logged(self):
        engine = EvolutionEngine(db=object())
        with patch("core.database.SessionLocal", side_effect=RuntimeError("db down")):
            await engine._trigger_alpha_evolver(_skill_event(), "high_latency")  # must not raise

    def test_get_skill_code_found(self, tmp_path):
        skill_dir = tmp_path / "skills" / "skill-1"
        skill_dir.mkdir(parents=True)
        (skill_dir / "tool_skill-1.py").write_text("print('hi')")
        (skill_dir / "readme.md").write_text("doc")
        engine = EvolutionEngine(db=object())
        builder = MagicMock()
        builder._get_tenant_skills_dir.return_value = skill_dir.parent
        with patch("core.skill_builder_service.SkillBuilderService", return_value=builder):
            assert engine._get_skill_code("skill-1", "t1") == "print('hi')"

    def test_get_skill_code_not_found(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        engine = EvolutionEngine(db=object())
        builder = MagicMock()
        builder._get_tenant_skills_dir.return_value = skills_dir
        with patch("core.skill_builder_service.SkillBuilderService", return_value=builder):
            assert engine._get_skill_code("missing", "t1") is None

    def test_get_skill_code_exception(self):
        engine = EvolutionEngine(db=object())
        with patch("core.skill_builder_service.SkillBuilderService", side_effect=ImportError("gone")):
            assert engine._get_skill_code("skill-1", "t1") is None

    def test_get_workspace_settings_with_metadata(self):
        db = MagicMock()
        workspace = SimpleNamespace(metadata_json={"auto_dev": {"enabled": True}})
        db.query.return_value.filter.return_value.first.return_value = workspace
        engine = EvolutionEngine(db=db)
        assert engine._get_workspace_settings("t1") == {"auto_dev": {"enabled": True}}

    def test_get_workspace_settings_no_metadata(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(metadata_json=None)
        engine = EvolutionEngine(db=db)
        assert engine._get_workspace_settings("t1") == {}

    def test_get_workspace_settings_no_workspace(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        engine = EvolutionEngine(db=db)
        assert engine._get_workspace_settings("t1") == {}

    def test_get_workspace_settings_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        engine = EvolutionEngine(db=db)
        assert engine._get_workspace_settings("t1") == {}


# ============================================================================
# core/auto_dev/reflection_engine.py
# ============================================================================


def _task_event(**overrides):
    defaults = dict(
        episode_id="e1",
        agent_id="agent-1",
        tenant_id="t1",
        task_description="parse the invoice file",
        error_trace="boom",
        outcome="failure",
    )
    defaults.update(overrides)
    return TaskEvent(**defaults)


class TestReflectionEngine:
    def test_init_defaults(self):
        db = object()
        engine = ReflectionEngine(db)
        assert engine.db is db
        assert engine.failure_threshold == 2
        assert engine._failure_buffer == {}

    def test_init_custom_threshold(self):
        engine = ReflectionEngine(db=object(), failure_threshold=3)
        assert engine.failure_threshold == 3

    def test_register(self):
        db = object()
        engine = ReflectionEngine(db)
        event_bus.clear()
        try:
            engine.register()
            assert event_bus._fail_handlers == [engine.process_failure]
        finally:
            event_bus.clear()

    async def test_process_failure_skipped_when_not_allowed(self):
        engine = ReflectionEngine(db=object())
        with patch.object(engine, "_should_process_agent", return_value=False) as gate:
            await engine.process_failure(_task_event())
        gate.assert_called_once()
        assert engine._failure_buffer == {}

    async def test_process_failure_below_threshold(self):
        engine = ReflectionEngine(db=object())
        with patch.object(engine, "_should_process_agent", return_value=True):
            with patch.object(engine, "_trigger_memento") as trigger:
                await engine.process_failure(_task_event(episode_id="e1"))
        trigger.assert_not_called()
        assert len(engine._failure_buffer["agent-1"]) == 1

    async def test_process_failure_triggers_and_clears(self):
        engine = ReflectionEngine(db=object())
        event = _task_event(episode_id="e2", task_description="parse the invoice file")
        with patch.object(engine, "_should_process_agent", return_value=True):
            with patch.object(engine, "_trigger_memento", new=AsyncMock()) as trigger:
                engine._failure_buffer["agent-1"].append(
                    {"episode_id": "e1", "task_description": "parse the invoice file", "error_trace": None, "tenant_id": "t1"}
                )
                await engine.process_failure(event)
        trigger.assert_awaited_once_with(
            agent_id="agent-1",
            tenant_id="t1",
            episode_id="e2",
            similar_failures=[
                {
                    "episode_id": "e1",
                    "task_description": "parse the invoice file",
                    "error_trace": None,
                    "tenant_id": "t1",
                },
                {
                    "episode_id": "e2",
                    "task_description": "parse the invoice file",
                    "error_trace": "boom",
                    "tenant_id": "t1",
                },
            ],
        )
        assert engine._failure_buffer["agent-1"] == []  # cleared

    async def test_trigger_memento_success(self):
        db = object()
        engine = ReflectionEngine(db)
        memento = MagicMock()
        candidate = SimpleNamespace(skill_name="parse_invoices")
        memento.generate_skill_candidate = AsyncMock(return_value=candidate)
        with patch("core.auto_dev.memento_engine.MementoEngine", return_value=memento):
            await engine._trigger_memento(
                agent_id="agent-1",
                tenant_id="t1",
                episode_id="e1",
                similar_failures=[],
            )
        memento.generate_skill_candidate.assert_awaited_once_with(
            tenant_id="t1", agent_id="agent-1", episode_id="e1"
        )

    async def test_trigger_memento_exception(self):
        db = object()
        engine = ReflectionEngine(db)
        with patch("core.auto_dev.memento_engine.MementoEngine", side_effect=RuntimeError("nope")):
            await engine._trigger_memento(
                agent_id="agent-1", tenant_id="t1", episode_id="e1", similar_failures=[]
            )  # must not raise

    def test_should_process_agent_true(self):
        engine = ReflectionEngine(db=object())
        gate = MagicMock()
        gate.can_use.return_value = True
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate):
            with patch.object(engine, "_get_workspace_settings", return_value={}):
                assert engine._should_process_agent("agent-1", "t1") is True
        gate.can_use.assert_called_once_with(
            agent_id="agent-1",
            capability="auto_dev.memento_skills",
            workspace_settings={},
        )

    def test_should_process_agent_false(self):
        engine = ReflectionEngine(db=object())
        gate = MagicMock()
        gate.can_use.return_value = False
        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate):
            assert engine._should_process_agent("agent-1", "t1") is False

    def test_should_process_agent_exception(self):
        engine = ReflectionEngine(db=object())

        def boom(*a, **kw):
            raise RuntimeError("gate down")

        with patch("core.auto_dev.capability_gate.AutoDevCapabilityService", side_effect=boom):
            assert engine._should_process_agent("agent-1", "t1") is False

    def test_get_workspace_settings_with_metadata(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            metadata_json={"auto_dev": {"memento": True}}
        )
        engine = ReflectionEngine(db=db)
        assert engine._get_workspace_settings("t1") == {"auto_dev": {"memento": True}}

    def test_get_workspace_settings_none_metadata(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(metadata_json=None)
        engine = ReflectionEngine(db=db)
        assert engine._get_workspace_settings("t1") == {}

    def test_get_workspace_settings_missing(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        engine = ReflectionEngine(db=db)
        assert engine._get_workspace_settings("t1") == {}

    def test_get_workspace_settings_exception(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        engine = ReflectionEngine(db=db)
        assert engine._get_workspace_settings("t1") == {}

    def test_find_similar_failures_high_overlap(self):
        engine = ReflectionEngine(db=object())
        engine._failure_buffer["agent-1"] = [
            {"episode_id": "e1", "task_description": "parse the invoice file", "error_trace": None, "tenant_id": "t1"},
            {"episode_id": "e2", "task_description": "send a welcome email", "error_trace": None, "tenant_id": "t1"},
        ]
        similar = engine._find_similar_failures("agent-1", "parse the invoice file")
        assert [f["episode_id"] for f in similar] == ["e1"]

    def test_find_similar_failures_low_overlap(self):
        engine = ReflectionEngine(db=object())
        engine._failure_buffer["agent-1"] = [
            {"episode_id": "e2", "task_description": "send a welcome email", "error_trace": None, "tenant_id": "t1"},
        ]
        assert engine._find_similar_failures("agent-1", "parse the invoice file") == []

    def test_find_similar_failures_empty_task_words(self):
        engine = ReflectionEngine(db=object())
        engine._failure_buffer["agent-1"] = [
            {"episode_id": "e1", "task_description": "parse the invoice file", "error_trace": None, "tenant_id": "t1"},
        ]
        assert engine._find_similar_failures("agent-1", "") == []

    def test_find_similar_failures_unknown_agent(self):
        engine = ReflectionEngine(db=object())
        assert engine._find_similar_failures("nobody", "anything") == []

    def test_clear_pattern_removes_processed(self):
        engine = ReflectionEngine(db=object())
        engine._failure_buffer["agent-1"] = [
            {"episode_id": "e1", "task_description": "a", "error_trace": None, "tenant_id": "t1"},
            {"episode_id": "e2", "task_description": "b", "error_trace": None, "tenant_id": "t1"},
        ]
        engine._clear_pattern("agent-1", [{"episode_id": "e1"}])
        assert [f["episode_id"] for f in engine._failure_buffer["agent-1"]] == ["e2"]


# ============================================================================
# core/auto_dev/regression_validator.py
# ============================================================================


class TestRegressionValidator:
    def test_regression_result_defaults(self):
        r = RegressionResult(passed=True)
        assert r.mismatches == []
        assert r.parent_results == []
        assert r.child_results == []
        assert r.total_tests == 0
        assert r.passed_tests == 0
        assert r.regression_detected is False

    def test_regression_detected_property(self):
        r = RegressionResult(passed=False, mismatches=[TestMismatch({"x": 1}, "a", "b")])
        assert r.regression_detected is True

    def test_to_dict(self):
        r = RegressionResult(
            passed=False,
            total_tests=2,
            passed_tests=1,
            mismatches=[
                TestMismatch({"x": 1}, "parent-out", "child-out"),
                TestMismatch({"y": 2}, "p" * 250, "c" * 250),
            ],
        )
        d = r.to_dict()
        assert d["passed"] is False
        assert d["mismatch_count"] == 2
        assert d["mismatches"][0]["parent_output"] == "parent-out"
        assert len(d["mismatches"][1]["parent_output"]) == 200  # truncated

    def test_to_dict_no_mismatches(self):
        r = RegressionResult(passed=True, total_tests=1, passed_tests=1)
        assert r.to_dict()["mismatch_count"] == 0

    async def test_validate_regression_empty_inputs(self):
        validator = RegressionValidator()
        result = await validator.validate_regression("p", "c", [], sandbox=object(), tenant_id="t1")
        assert result.passed is True
        assert result.total_tests == 0

    async def test_validate_regression_match(self):
        validator = RegressionValidator()
        sandbox = AsyncMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "success", "output": "same"}
        )
        result = await validator.validate_regression("p", "c", [{"x": 1}], sandbox=sandbox, tenant_id="t1")
        assert result.passed is True
        assert result.passed_tests == 1
        assert sandbox.execute_raw_python.await_count == 2

    async def test_validate_regression_mismatch(self):
        validator = RegressionValidator()
        sandbox = AsyncMock()

        async def fake_execute(tenant_id, code, input_params):
            return {"status": "success", "output": code}

        sandbox.execute_raw_python = fake_execute
        result = await validator.validate_regression("parent", "child", [{"x": 1}], sandbox=sandbox, tenant_id="t1")
        assert result.passed is False
        assert len(result.mismatches) == 1
        assert result.mismatches[0].parent_output == "parent"
        assert result.mismatches[0].child_output == "child"
        assert result.passed_tests == 0

    async def test_validate_regression_child_crash(self):
        validator = RegressionValidator()
        sandbox = AsyncMock()

        async def fake_execute(tenant_id, code, input_params):
            return {"status": "failed", "output": f"err for {code}"}

        sandbox.execute_raw_python = fake_execute
        result = await validator.validate_regression("p", "c", [{"x": 1}], sandbox=sandbox, tenant_id="t1")
        assert result.passed is False
        assert result.mismatches[0].child_output == "[CRASH] err for c"
        assert result.mismatches[0].parent_output == "err for p"

    async def test_validate_regression_parent_crash_is_improvement(self):
        validator = RegressionValidator()
        sandbox = AsyncMock()

        async def fake_execute(tenant_id, code, input_params):
            if code == "parent":
                return {"status": "failed", "output": "parent crash"}
            return {"status": "success", "output": "works"}

        sandbox.execute_raw_python = fake_execute
        result = await validator.validate_regression("parent", "child", [{"x": 1}], sandbox=sandbox, tenant_id="t1")
        assert result.passed is True
        assert result.passed_tests == 1

    async def test_run_in_sandbox_success(self):
        validator = RegressionValidator()
        sandbox = AsyncMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "success", "output": "out"}
        )
        result = await validator._run_in_sandbox(sandbox, "t1", "code", {"x": 1})
        assert result["_success"] is True
        sandbox.execute_raw_python.assert_awaited_once()

    async def test_run_in_sandbox_failure_status(self):
        validator = RegressionValidator()
        sandbox = AsyncMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "failed", "output": "boom"}
        )
        result = await validator._run_in_sandbox(sandbox, "t1", "code", {})
        assert result["_success"] is False

    async def test_run_in_sandbox_exception(self):
        validator = RegressionValidator()
        sandbox = AsyncMock()
        sandbox.execute_raw_python = AsyncMock(
            side_effect=RuntimeError("sandbox exploded")
        )
        result = await validator._run_in_sandbox(sandbox, "t1", "code", {})
        assert result["_success"] is False
        assert "sandbox exploded" in result["output"]

    def test_outputs_match_exact(self):
        validator = RegressionValidator()
        assert validator._outputs_match(" hello ", "hello")
        assert not validator._outputs_match("hello", "world")

    def test_outputs_match_fuzzy(self):
        validator = RegressionValidator(fuzzy_match=True, fuzzy_tolerance=0.8)
        assert validator._outputs_match("hello world", "hello world ")
        assert not validator._outputs_match("hello world", "completely different")

    def test_fuzzy_threshold_boundary(self):
        validator = RegressionValidator(fuzzy_match=True, fuzzy_tolerance=1.0)
        assert validator._outputs_match("abc", "abc")
        assert not validator._outputs_match("abc", "abd")

    async def test_validate_regression_multiple_inputs_mixed(self):
        validator = RegressionValidator()
        sandbox = AsyncMock()

        async def fake_execute(tenant_id, code, input_params):
            x = input_params["x"]
            if x == 1:
                return {"status": "success", "output": "same"}
            if x == 2:
                return {"status": "failed", "output": "crash"}
            return {"status": "success", "output": f"code-{code}-x{x}"}

        sandbox.execute_raw_python = fake_execute
        result = await validator.validate_regression(
            "p", "c", [{"x": 1}, {"x": 2}, {"x": 3}], sandbox=sandbox, tenant_id="t1"
        )
        assert result.total_tests == 3
        assert result.passed_tests == 1
        assert len(result.mismatches) == 2
        assert result.passed is False


# ============================================================================
# core/auto_dev/mutation_rollback.py
# ============================================================================


class TestMutationRollbackRegistry:
    def test_snapshot_returns_id_and_stores(self):
        reg = MutationRollbackRegistry()
        mid = reg.snapshot("agent-1", "system_prompt", "old", "new", source="alpha_evolver")
        assert mid.startswith("mut_")
        snap = reg.get_snapshot(mid)
        assert snap is not None
        assert snap.agent_id == "agent-1"
        assert snap.config_key == "system_prompt"
        assert snap.old_value == "old"
        assert snap.new_value == "new"
        assert snap.source == "alpha_evolver"
        assert snap.verified is False
        assert snap.timestamp  # default lambda fired

    def test_snapshot_lru_eviction(self):
        reg = MutationRollbackRegistry(max_snapshots=2)
        m1 = reg.snapshot("a", "k1", 1, 2)
        m2 = reg.snapshot("a", "k2", 1, 2)
        m3 = reg.snapshot("a", "k3", 1, 2)
        assert reg.get_snapshot(m1) is None  # evicted
        assert reg.get_snapshot(m2) is not None
        assert reg.get_snapshot(m3) is not None
        assert len(reg._snapshots) == 2

    def test_rollback_applies_old_value(self):
        reg = MutationRollbackRegistry()
        mid = reg.snapshot("agent-1", "system_prompt", "old-prompt", "new-prompt")
        config = {"system_prompt": "new-prompt", "other": 1}
        assert reg.rollback(mid, config) is True
        assert config["system_prompt"] == "old-prompt"

    def test_rollback_without_config(self):
        reg = MutationRollbackRegistry()
        mid = reg.snapshot("agent-1", "k", "old", "new")
        assert reg.rollback(mid) is True

    def test_rollback_unknown_id(self):
        reg = MutationRollbackRegistry()
        assert reg.rollback("mut_unknown") is False

    def test_rollback_agent_all_unverified(self):
        reg = MutationRollbackRegistry()
        m1 = reg.snapshot("agent-1", "k1", "o1", "n1")
        m2 = reg.snapshot("agent-1", "k2", "o2", "n2")
        reg.snapshot("agent-2", "kx", "o", "n")
        config = {"k1": "n1", "k2": "n2"}
        assert reg.rollback_agent("agent-1", config) == 2
        assert config == {"k1": "o1", "k2": "o2"}

    def test_rollback_agent_skips_verified(self):
        reg = MutationRollbackRegistry()
        m1 = reg.snapshot("agent-1", "k1", "o1", "n1")
        m2 = reg.snapshot("agent-1", "k2", "o2", "n2")
        reg.verify(m1)
        config = {}
        assert reg.rollback_agent("agent-1", config) == 1
        reg.verify(m2)

    def test_rollback_agent_without_config(self):
        reg = MutationRollbackRegistry()
        reg.snapshot("agent-1", "k1", "o1", "n1")
        assert reg.rollback_agent("agent-1") == 1

    def test_rollback_agent_unknown(self):
        reg = MutationRollbackRegistry()
        assert reg.rollback_agent("nobody") == 0

    def test_verify_marks_snapshot(self):
        reg = MutationRollbackRegistry()
        mid = reg.snapshot("agent-1", "k", "o", "n")
        assert reg.verify(mid) is True
        assert reg.get_snapshot(mid).verified is True

    def test_verify_unknown(self):
        reg = MutationRollbackRegistry()
        assert reg.verify("mut_unknown") is False

    def test_get_agent_mutations(self):
        reg = MutationRollbackRegistry()
        reg.snapshot("agent-1", "k1", "o", "n")
        reg.snapshot("agent-2", "k2", "o", "n")
        snaps = reg.get_agent_mutations("agent-1")
        assert len(snaps) == 1
        assert snaps[0].agent_id == "agent-1"

    def test_clear(self):
        reg = MutationRollbackRegistry()
        reg.snapshot("agent-1", "k", "o", "n")
        reg.clear()
        assert reg._snapshots == {}

    def test_default_max_snapshots(self):
        reg = MutationRollbackRegistry()
        assert reg._max_snapshots == 1000

    def test_mutation_snapshot_defaults(self):
        snap = MutationSnapshot(mutation_id="m", agent_id="a", config_key="k", old_value=1, new_value=2)
        assert snap.verified is False
        assert snap.source == "unknown"
        assert snap.timestamp  # default lambda fired


class TestGetRollbackRegistry:
    def test_singleton(self):
        first = get_rollback_registry()
        second = get_rollback_registry()
        assert first is second
        assert isinstance(first, MutationRollbackRegistry)


# ============================================================================
# core/auto_dev/container_sandbox.py
# ============================================================================


def _mock_process(stdout=b"", stderr=b"", returncode=0):
    proc = Mock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.wait = AsyncMock()
    proc.kill = Mock()
    proc.returncode = returncode
    return proc


class TestContainerSandboxDockerAvailable:
    def test_docker_available_true(self):
        sandbox = ContainerSandbox()
        assert sandbox._docker_available is None
        with patch("subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0)
            assert sandbox.docker_available is True
        assert sandbox._docker_available is True

    def test_docker_available_false_returncode(self):
        sandbox = ContainerSandbox()
        with patch("subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=1)
            assert sandbox.docker_available is False

    def test_docker_available_file_not_found(self):
        sandbox = ContainerSandbox()
        with patch("subprocess.run", side_effect=FileNotFoundError("no docker")):
            assert sandbox.docker_available is False

    def test_docker_available_timeout(self):
        sandbox = ContainerSandbox()
        with patch("subprocess.run", side_effect=subprocess_timeout()):
            assert sandbox.docker_available is False

    def test_docker_available_cached(self):
        sandbox = ContainerSandbox()
        sandbox._docker_available = True
        with patch("subprocess.run", side_effect=AssertionError("should not run")):
            assert sandbox.docker_available is True

    def test_init_defaults(self):
        sandbox = ContainerSandbox()
        assert sandbox.docker_image == "python:3.11-slim"
        assert sandbox.timeout == 60
        assert sandbox.memory_limit == "256m"
        assert sandbox.enable_network is False

    def test_init_custom(self):
        sandbox = ContainerSandbox(
            docker_image="img", timeout=10, memory_limit="128m", enable_network=True
        )
        assert sandbox.timeout == 10
        assert sandbox.enable_network is True


def subprocess_timeout():
    import subprocess

    return subprocess.TimeoutExpired(cmd="docker info", timeout=5)


class TestContainerSandboxExecution:
    async def test_execute_subprocess_success(self):
        sandbox = ContainerSandbox()
        sandbox._docker_available = False
        with patch("asyncio.create_subprocess_exec", return_value=_mock_process(stdout=b"hello\n")):
            result = await sandbox.execute_raw_python("t1", "print('hello')", {"x": 1}, timeout=30)
        assert result["status"] == "success"
        assert result["output"] == "hello"
        assert result["environment"] == "subprocess"
        assert isinstance(result["execution_seconds"], float)

    async def test_execute_subprocess_override_timeout_zero(self):
        sandbox = ContainerSandbox()
        sandbox._docker_available = False
        # timeout=0 is falsy → falls back to self.timeout
        with patch("asyncio.create_subprocess_exec", return_value=_mock_process(stdout=b"ok")):
            result = await sandbox.execute_raw_python("t1", "print(1)", timeout=0)
        assert result["status"] == "success"

    async def test_execute_subprocess_failure(self):
        sandbox = ContainerSandbox()
        sandbox._docker_available = False
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_mock_process(stdout=b"", stderr=b"Traceback: boom", returncode=1),
        ):
            result = await sandbox.execute_raw_python("t1", "raise ValueError()")
        assert result["status"] == "failed"
        assert "Traceback: boom" in result["output"]

    async def test_execute_subprocess_failure_empty_stderr(self):
        sandbox = ContainerSandbox()
        sandbox._docker_available = False
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_mock_process(stdout=b"partial", stderr=b"", returncode=2),
        ):
            result = await sandbox.execute_raw_python("t1", "exit(2)")
        assert result["status"] == "failed"
        assert result["output"] == "partial"

    async def test_execute_subprocess_timeout(self):
        sandbox = ContainerSandbox()
        sandbox._docker_available = False
        proc = _mock_process()
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                result = await sandbox.execute_raw_python("t1", "while True: pass", timeout=1)
        assert result["status"] == "failed"
        assert "timed out" in result["output"]
        assert result["environment"] == "subprocess"
        proc.kill.assert_called_once()
        proc.wait.assert_awaited_once()

    async def test_execute_docker_success(self):
        sandbox = ContainerSandbox()
        sandbox._docker_available = True
        with patch("asyncio.create_subprocess_exec", return_value=_mock_process(stdout=b"docker out")):
            result = await sandbox.execute_raw_python("t1", "print('docker out')")
        assert result["status"] == "success"
        assert result["environment"] == "docker"
        assert result["output"] == "docker out"

    async def test_execute_docker_network_enabled_no_network_flag(self):
        sandbox = ContainerSandbox(enable_network=True)
        sandbox._docker_available = True
        with patch("asyncio.create_subprocess_exec", return_value=_mock_process(stdout=b"ok")) as sub:
            result = await sandbox.execute_raw_python("t1", "print('ok')")
        assert result["status"] == "success"
        cmd = sub.await_args.args[0]
        assert "--network" not in cmd

    async def test_execute_docker_network_disabled_has_flag(self):
        sandbox = ContainerSandbox(enable_network=False)
        sandbox._docker_available = True
        with patch("asyncio.create_subprocess_exec", return_value=_mock_process(stdout=b"ok")) as sub:
            await sandbox.execute_raw_python("t1", "print('ok')")
        cmd = sub.await_args.args
        assert "--network" in cmd
        assert cmd[cmd.index("--network") + 1] == "none"

    async def test_execute_docker_failure(self):
        sandbox = ContainerSandbox()
        sandbox._docker_available = True
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=_mock_process(stderr=b"docker error", returncode=1),
        ):
            result = await sandbox.execute_raw_python("t1", "boom()")
        assert result["status"] == "failed"
        assert "docker error" in result["output"]

    async def test_execute_docker_timeout_kills_container(self):
        sandbox = ContainerSandbox()
        sandbox._docker_available = True
        proc = _mock_process()
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                with patch.object(sandbox, "_kill_docker_container", new=AsyncMock()) as kill:
                    result = await sandbox.execute_raw_python("t1", "while True: pass", timeout=1)
        assert result["status"] == "failed"
        assert result["environment"] == "docker"
        assert "timed out" in result["output"]
        proc.kill.assert_called_once()
        kill.assert_awaited_once()


class TestKillDockerContainer:
    async def test_kill_with_cid_file(self, tmp_path):
        sandbox = ContainerSandbox()
        cid_file = tmp_path / "script.cid"
        cid_file.write_text("abc123\n")
        kill_proc = _mock_process()
        sub = AsyncMock(return_value=kill_proc)
        with patch("asyncio.create_subprocess_exec", new=sub):
            await sandbox._kill_docker_container(str(cid_file))
        assert kill_proc.wait.await_count == 1
        args = sub.await_args.args
        assert args[0] == "docker"
        assert args[1] == "kill"
        assert args[2] == "abc123"

    async def test_kill_missing_cid_file(self):
        sandbox = ContainerSandbox()
        with patch("asyncio.create_subprocess_exec", side_effect=AssertionError("no subprocess")):
            await sandbox._kill_docker_container("/nonexistent/script.cid")

    async def test_kill_empty_cid_file(self, tmp_path):
        sandbox = ContainerSandbox()
        cid_file = tmp_path / "script.cid"
        cid_file.write_text("  \n")
        with patch("asyncio.create_subprocess_exec", side_effect=AssertionError("no subprocess")):
            await sandbox._kill_docker_container(str(cid_file))

    async def test_kill_exception_logged(self):
        sandbox = ContainerSandbox()
        with patch("os.path.exists", side_effect=OSError("io error")):
            await sandbox._kill_docker_container("/some/script.cid")


class TestResourceLimits:
    def test_preexec_win32_none(self):
        with patch("sys.platform", "win32"):
            assert ContainerSandbox._resource_limit_preexec() is None

    def test_preexec_applies_limits(self):
        fn = ContainerSandbox._resource_limit_preexec()
        assert callable(fn)
        with patch("resource.setrlimit") as setrlimit:
            fn()
        assert setrlimit.call_count == 2

    def test_preexec_ignores_exceptions(self):
        fn = ContainerSandbox._resource_limit_preexec()
        with patch("resource.setrlimit", side_effect=ValueError("no rlimits")):
            fn()  # must not raise


class TestBuildExecutionWrapper:
    def test_wrapper_contains_code(self):
        wrapper = ContainerSandbox._build_execution_wrapper("print(42)", {})
        assert "print(42)" in wrapper
        assert "json.loads(_b64.b64decode(" in wrapper

    def test_wrapper_params_round_trip(self):
        params = {"x": 1, "text": "it's ''' tricky", "nested": {"a": [1, 2]}}
        wrapper = ContainerSandbox._build_execution_wrapper("pass", params)
        # Extract the base64 blob and verify the JSON round-trips.
        match = re.search(r"b64decode\('([A-Za-z0-9+/=]+)'\)", wrapper)
        assert match is not None
        decoded = base64.b64decode(match.group(1)).decode("utf-8")
        assert json.loads(decoded) == params

    def test_wrapper_empty_params(self):
        wrapper = ContainerSandbox._build_execution_wrapper("pass", {})
        # base64 of '{}' — decoded to {} at runtime, never interpolated
        assert "e30=" in wrapper
        assert "{}" not in wrapper
