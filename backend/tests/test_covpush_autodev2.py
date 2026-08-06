"""Coverage-push tests (part 2) for Auto-Dev modules.

Targets: memento_engine, reflection_engine, regression_validator,
behavior_analyzer, burnout_detection_engine.
"""

import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.auto_dev.event_hooks import event_bus
from core.auto_dev.models import SkillCandidate


@pytest.fixture(scope="module")
def db_engine2():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.database import Base

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db2(db_engine2):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine2)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _empty_module(name: str) -> types.ModuleType:
    return types.ModuleType(name)


# =============================================================================
# MementoEngine
# =============================================================================


def _make_memento_engine(db, **kwargs):
    from core.auto_dev.memento_engine import MementoEngine

    return MementoEngine(db=db, **kwargs)


class TestMementoEngineCoverage:
    def test_analyze_episode_tool_call_status_mapping(self, db2):
        from core.models import AgentEpisode, EpisodeSegment

        db2.add(AgentEpisode(
            id="ep-m-1", agent_id="ag-1", tenant_id="t-1",
            task_description="Summarize docs", maturity_at_time="intern",
            outcome="failure", success=False, status="active",
        ))
        db2.add(EpisodeSegment(
            id="seg-m-1", episode_id="ep-m-1", segment_type="skill_failure",
            sequence_order=1, content="Tool call: web_search - failed",
        ))
        db2.add(EpisodeSegment(
            id="seg-m-2", episode_id="ep-m-1", segment_type="error",
            sequence_order=2, content="Tool call: summarizer - success",
        ))
        db2.add(EpisodeSegment(
            id="seg-m-3", episode_id="ep-m-1", segment_type="error",
            sequence_order=3, content="Tool call: retriever",
        ))
        db2.commit()

        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.analyze_episode("ep-m-1"))
        assert result["error_segments_count"] == 3
        calls = {c["tool_name"]: c["status"] for c in result["tool_calls_attempted"]}
        assert calls["web_search"] == "failed"
        assert calls["summarizer"] == "success"
        assert calls["retriever"] == "unknown"
        assert result["suggested_skill_name"].startswith("auto_")

    def test_analyze_episode_not_found(self, db2):
        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.analyze_episode("ep-missing"))
        assert result["error"] == "Episode ep-missing not found"

    def test_analyze_episode_import_error(self, db2, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.models", _empty_module("core.models"))
        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.analyze_episode("ep-1"))
        assert result["error"] == "Episode models not available"

    def test_propose_code_change_no_llm(self, db2):
        engine = _make_memento_engine(db2)
        engine._get_llm_service = Mock(return_value=None)
        code = asyncio.run(engine.propose_code_change({"task_description": "t"}))
        assert code == "# Skill generation skipped: LLM unavailable"

    def test_propose_code_change_with_tools_and_failure(self, db2):
        llm = MagicMock()
        captured = {}

        async def fake_gen(**kwargs):
            captured["messages"] = kwargs["messages"]
            return {"content": "def skill():\n    pass"}

        llm.generate_completion = AsyncMock(side_effect=fake_gen)
        engine = _make_memento_engine(db2, llm_service=llm)
        code = asyncio.run(engine.propose_code_change({
            "task_description": "Parse CSV",
            "error_trace": "ValueError: bad row",
            "tool_calls_attempted": [{"tool_name": "csv_loader"}],
        }))
        assert code == "def skill():\n    pass"
        assert "csv_loader" in captured["messages"][1]["content"]

    def test_propose_code_change_llm_error(self, db2):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(side_effect=RuntimeError("down"))
        engine = _make_memento_engine(db2, llm_service=llm)
        code = asyncio.run(engine.propose_code_change({"task_description": "t"}))
        assert code.startswith("# Skill generation failed")

    def test_validate_change_no_sandbox(self, db2):
        engine = _make_memento_engine(db2)
        engine._get_sandbox = Mock(return_value=None)
        result = asyncio.run(engine.validate_change("code", [{}], "t-1"))
        assert result == {"passed": False, "error": "Sandbox unavailable"}

    def test_validate_change_sandbox_raises(self, db2):
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(side_effect=RuntimeError("sandbox"))
        engine = _make_memento_engine(db2, sandbox=sandbox)
        result = asyncio.run(engine.validate_change("code", [{"x": 1}], "t-1"))
        assert result["passed"] is False
        assert "Sandbox error" in result["test_results"][0]["output"]

    def test_validate_change_default_inputs(self, db2):
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "success", "output": "ok"}
        )
        engine = _make_memento_engine(db2, sandbox=sandbox)
        result = asyncio.run(engine.validate_change("code", None, "t-1"))
        assert result["passed"] is True

    def test_generate_skill_candidate_raises_on_bad_analysis(self, db2):
        engine = _make_memento_engine(db2)
        with pytest.raises(ValueError):
            asyncio.run(engine.generate_skill_candidate(
                tenant_id="t-1", agent_id="ag-1", episode_id="ep-x",
                failure_analysis={"error": "Episode ep-x not found"},
            ))

    def test_generate_skill_candidate_full(self, db2):
        llm = MagicMock()
        llm.generate_completion = AsyncMock(
            return_value={"content": "def new_skill():\n    return 1"}
        )
        engine = _make_memento_engine(db2, llm_service=llm)
        candidate = asyncio.run(engine.generate_skill_candidate(
            tenant_id="t-1", agent_id="ag-1", episode_id="ep-gen-1",
            failure_analysis={
                "task_description": "build csv parser",
                "error_trace": "err",
                "tool_calls_attempted": [],
                "failure_summary": "Failed: build csv parser",
                "suggested_skill_name": "auto_build_csv_parser",
            },
        ))
        assert candidate.validation_status == "pending"
        assert candidate.skill_name == "auto_build_csv_parser"
        assert candidate.agent_id == "ag-1"
        assert db2.query(SkillCandidate).count() == 1

    def test_validate_candidate_not_found(self, db2):
        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.validate_candidate("c-miss", "t-1"))
        assert "error" in result

    def test_validate_candidate_passed(self, db2):
        db2.add(SkillCandidate(
            id="c-val-1", tenant_id="t-1", agent_id="ag-1", skill_name="s",
            generated_code="code", validation_status="pending",
        ))
        db2.commit()
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "success", "output": "ok"}
        )
        engine = _make_memento_engine(db2, sandbox=sandbox)
        result = asyncio.run(engine.validate_candidate("c-val-1", "t-1"))
        assert result["passed"] is True
        row = db2.query(SkillCandidate).get("c-val-1")
        assert row.validation_status == "validated"
        assert row.fitness_score == 1.0

    def test_validate_candidate_failed(self, db2):
        db2.add(SkillCandidate(
            id="c-val-2", tenant_id="t-1", agent_id="ag-1", skill_name="s",
            generated_code="code", validation_status="pending",
        ))
        db2.commit()
        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(
            return_value={"status": "failed", "output": "boom"}
        )
        engine = _make_memento_engine(db2, sandbox=sandbox)
        result = asyncio.run(engine.validate_candidate("c-val-2", "t-1"))
        assert result["passed"] is False
        assert db2.query(SkillCandidate).get("c-val-2").validation_status == "failed"

    def test_promote_skill_not_validated(self, db2):
        db2.add(SkillCandidate(
            id="c-pro-1", tenant_id="t-1", agent_id="ag-1", skill_name="s",
            generated_code="code", validation_status="pending",
        ))
        db2.commit()
        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.promote_skill("c-pro-1", "t-1"))
        assert result == {"error": "Candidate not found or not validated"}

    def test_promote_skill_import_error(self, db2, monkeypatch):
        db2.add(SkillCandidate(
            id="c-pro-2", tenant_id="t-1", agent_id="ag-1", skill_name="s",
            generated_code="code", validation_status="validated",
        ))
        db2.commit()
        monkeypatch.setitem(
            sys.modules, "core.skill_builder_service",
            _empty_module("core.skill_builder_service"),
        )
        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.promote_skill("c-pro-2", "t-1"))
        assert result == {"error": "SkillBuilderService not available"}

    def test_promote_skill_success(self, db2, monkeypatch):
        db2.add(SkillCandidate(
            id="c-pro-3", tenant_id="t-1", agent_id="ag-1", skill_name="cool_skill",
            skill_description="A cool skill", generated_code="code",
            validation_status="validated",
        ))
        db2.commit()

        class FakeBuilder:
            def create_skill_package(self, tenant_id, metadata, scripts):
                return {"success": True, "skill_id": "sk-1"}

        monkeypatch.setattr(
            "core.skill_builder_service.SkillBuilderService", FakeBuilder,
        )
        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.promote_skill("c-pro-3", "t-1"))
        assert result["success"] is True
        row = db2.query(SkillCandidate).get("c-pro-3")
        assert row.validation_status == "promoted"
        assert row.promoted_at is not None

    def test_analyze_execution_success_trace(self, db2):
        from core.models import AgentExecution, AgentReasoningStep

        db2.add(AgentExecution(
            id="exec-1", agent_id="ag-1", tenant_id="t-1",
            status="completed", input_summary="Sort a list",
            result_summary="done", error_message="",
        ))
        db2.add(AgentReasoningStep(
            id="rs-1", execution_id="exec-1", step_number=1, step_type="thought",
            thought="think", verified="verified",
        ))
        db2.add(AgentReasoningStep(
            id="rs-2", execution_id="exec-1", step_number=2, step_type="action",
            action={"tool": "sort"}, verified="unverified",
        ))
        db2.commit()

        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.analyze_execution("exec-1"))
        assert result["status"] == "completed"
        assert result["step_count"] == 2
        assert result["tool_calls_attempted"] == [{"tool": "sort"}]
        assert result["suggested_skill_name"].startswith("auto_")

    def test_analyze_execution_with_error_message(self, db2):
        from core.models import AgentExecution

        db2.add(AgentExecution(
            id="exec-2", agent_id="ag-1", tenant_id="t-1",
            status="failed", input_summary="Crashy task",
            error_message="KeyError: 'x'",
        ))
        db2.commit()

        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.analyze_execution("exec-2"))
        assert "KeyError" in result["failure_summary"]

    def test_analyze_execution_not_found(self, db2):
        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.analyze_execution("exec-miss"))
        assert "error" in result

    def test_analyze_execution_import_error(self, db2, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.models", _empty_module("core.models"))
        engine = _make_memento_engine(db2)
        result = asyncio.run(engine.analyze_execution("exec-1"))
        assert result["error"] == "Execution models not available"

    def test_learn_from_execution_analysis_error(self, db2):
        engine = _make_memento_engine(db2)
        engine.analyze_execution = AsyncMock(return_value={"error": "not found"})
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
        ))
        assert result["success"] is False

    def test_learn_from_execution_llm_failed(self, db2):
        engine = _make_memento_engine(db2)
        engine.analyze_execution = AsyncMock(return_value={"status": "completed"})
        engine.propose_code_change = AsyncMock(
            return_value="# Skill generation failed: down"
        )
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
        ))
        assert result["success"] is False
        assert "LLM unavailable" in result["error"]

    def test_learn_from_execution_validation_failed(self, db2):
        engine = _make_memento_engine(db2)
        engine.analyze_execution = AsyncMock(return_value={"status": "completed"})
        engine.propose_code_change = AsyncMock(return_value="def x(): pass")
        engine.validate_change = AsyncMock(return_value={"passed": False})
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
        ))
        assert result["success"] is False
        assert "validation" in result

    def test_learn_from_execution_invalid_name(self, db2):
        engine = _make_memento_engine(db2)
        engine.analyze_execution = AsyncMock(return_value={"status": "completed"})
        engine.propose_code_change = AsyncMock(return_value="def x(): pass")
        engine.validate_change = AsyncMock(return_value={"passed": True})
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
            skill_name="!!!", description="d",
        ))
        assert result["success"] is False
        assert result["error"] == "Invalid skill name"

    def test_learn_from_execution_package_failed(self, db2, monkeypatch):
        engine = _make_memento_engine(db2)
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
        assert result["success"] is False
        assert result["error"] == "write failed"

    def test_learn_from_execution_success(self, db2, monkeypatch):
        engine = _make_memento_engine(db2)
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
                return {"success": True, "skill_id": "reg-1"}

        monkeypatch.setattr(
            "core.skill_builder_service.SkillBuilderService", FakeBuilder,
        )
        monkeypatch.setattr(
            "core.skill_registry_service.SkillRegistryService", FakeRegistry,
        )
        result = asyncio.run(engine.learn_from_execution(
            tenant_id="t-1", agent_id="ag-1", execution_id="exec-x",
        ))
        assert result["success"] is True
        assert result["skill_name"] == "auto_parser"
        assert result["registry"]["success"] is True

    def test_suggest_skill_name_fallback(self):
        from core.auto_dev.memento_engine import MementoEngine

        name = MementoEngine._suggest_skill_name("the and for with", "")
        assert name.startswith("auto_skill_")

    def test_suggest_skill_name_derived(self):
        from core.auto_dev.memento_engine import MementoEngine

        name = MementoEngine._suggest_skill_name("Analyze quarterly revenue", "")
        assert name == "auto_analyze_quarterly_revenue"


# =============================================================================
# ReflectionEngine
# =============================================================================


class TestReflectionEngineCoverage:
    def test_process_failure_triggers_memento(self, db2, monkeypatch):
        from core.auto_dev.event_hooks import TaskEvent
        from core.auto_dev.reflection_engine import ReflectionEngine

        gate = MagicMock()
        gate.can_use.return_value = True
        fake_candidate = MagicMock(skill_name="auto_skill")
        fake_memento = MagicMock()
        fake_memento.generate_skill_candidate = AsyncMock(
            return_value=fake_candidate
        )
        monkeypatch.setattr(
            "core.auto_dev.capability_gate.AutoDevCapabilityService",
            lambda session: gate,
        )
        monkeypatch.setattr(
            "core.auto_dev.memento_engine.MementoEngine",
            lambda db: fake_memento,
        )
        engine = ReflectionEngine(db2)
        engine._get_workspace_settings = Mock(return_value={})

        for i in range(2):
            asyncio.run(engine.process_failure(TaskEvent(
                episode_id=f"ep-{i}", agent_id="ag-r-1", tenant_id="t-r-1",
                task_description="Parse invoices from email",
                error_trace="TypeError: bad",
            )))
        assert fake_memento.generate_skill_candidate.await_count == 1
        assert engine._failure_buffer["ag-r-1"] == []

    def test_process_failure_below_threshold(self, db2):
        from core.auto_dev.event_hooks import TaskEvent
        from core.auto_dev.reflection_engine import ReflectionEngine

        gate = MagicMock()
        gate.can_use.return_value = True
        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService",
            return_value=gate,
        ):
            engine = ReflectionEngine(db2)
            engine._get_workspace_settings = Mock(return_value={})
            asyncio.run(engine.process_failure(TaskEvent(
                episode_id="ep-1", agent_id="ag-r-2", tenant_id="t-r-2",
                task_description="Unique task description here",
                error_trace="err",
            )))
            assert len(engine._failure_buffer["ag-r-2"]) == 1

    def test_process_failure_gate_blocks(self, db2):
        from core.auto_dev.event_hooks import TaskEvent
        from core.auto_dev.reflection_engine import ReflectionEngine

        gate = MagicMock()
        gate.can_use.return_value = False
        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService",
            return_value=gate,
        ):
            engine = ReflectionEngine(db2)
            engine._get_workspace_settings = Mock(return_value={})
            asyncio.run(engine.process_failure(TaskEvent(
                episode_id="ep-1", agent_id="ag-r-3", tenant_id="t-r-3",
                task_description="x", error_trace="e",
            )))
            assert "ag-r-3" not in engine._failure_buffer

    def test_trigger_memento_error_logged(self, db2):
        from core.auto_dev.reflection_engine import ReflectionEngine

        fake_memento = MagicMock()
        fake_memento.generate_skill_candidate = AsyncMock(
            side_effect=RuntimeError("memento down")
        )
        with patch(
            "core.auto_dev.memento_engine.MementoEngine",
            lambda db: fake_memento,
        ):
            engine = ReflectionEngine(db2)
            asyncio.run(engine._trigger_memento(
                agent_id="ag-1", tenant_id="t-1", episode_id="ep-1",
                similar_failures=[{"episode_id": "ep-1"}],
            ))

    def test_should_process_agent_exception(self, db2):
        from core.auto_dev.reflection_engine import ReflectionEngine

        class BrokenGate:
            def __init__(self, session):
                raise RuntimeError("gate down")

        with patch(
            "core.auto_dev.capability_gate.AutoDevCapabilityService", BrokenGate,
        ):
            engine = ReflectionEngine(db2)
            engine._get_workspace_settings = Mock(return_value={})
            assert engine._should_process_agent("ag-1", "t-1") is False

    def test_get_workspace_settings_exception(self):
        from core.auto_dev.reflection_engine import ReflectionEngine

        broken_db = MagicMock()
        broken_db.query.side_effect = RuntimeError("db down")
        engine = ReflectionEngine(broken_db)
        assert engine._get_workspace_settings("t-1") == {}

    def test_find_similar_failures_overlap(self):
        from core.auto_dev.reflection_engine import ReflectionEngine

        engine = ReflectionEngine(db=MagicMock())
        engine._failure_buffer["ag-1"] = [
            {"episode_id": "1", "task_description": "parse csv file data"},
            {"episode_id": "2", "task_description": "parse excel file data"},
            {"episode_id": "3", "task_description": "completely different"},
        ]
        similar = engine._find_similar_failures("ag-1", "parse csv file data")
        assert {f["episode_id"] for f in similar} == {"1", "2"}

    def test_find_similar_failures_empty_task(self):
        from core.auto_dev.reflection_engine import ReflectionEngine

        engine = ReflectionEngine(db=MagicMock())
        engine._failure_buffer["ag-1"] = [
            {"episode_id": "1", "task_description": "anything"},
        ]
        assert engine._find_similar_failures("ag-1", "") == []

    def test_clear_pattern_removes_only_matching(self):
        from core.auto_dev.reflection_engine import ReflectionEngine

        engine = ReflectionEngine(db=MagicMock())
        engine._failure_buffer["ag-1"] = [
            {"episode_id": "a", "task_description": "t1"},
            {"episode_id": "b", "task_description": "t2"},
        ]
        engine._clear_pattern("ag-1", [{"episode_id": "a"}])
        assert [f["episode_id"] for f in engine._failure_buffer["ag-1"]] == ["b"]

    def test_register_adds_handler(self):
        from core.auto_dev.reflection_engine import ReflectionEngine

        engine = ReflectionEngine(db=MagicMock())
        engine.register()
        assert len(event_bus._fail_handlers) > 0
        event_bus.clear()

    def test_workspace_settings_returned(self, db2):
        from core.models import Workspace

        db2.add(Workspace(
            id="ws-r-1", name="W", tenant_id="t-ws-r",
            metadata_json={"auto_dev": {"enabled": True}},
        ))
        db2.commit()
        from core.auto_dev.reflection_engine import ReflectionEngine

        engine = ReflectionEngine(db2)
        assert engine._get_workspace_settings("t-ws-r")["auto_dev"]["enabled"] is True


# =============================================================================
# RegressionValidator
# =============================================================================


class FakeRegressionSandbox:
    def __init__(self, outputs_by_code_prefix):
        self.outputs_by_code_prefix = outputs_by_code_prefix

    async def execute_raw_python(self, tenant_id, code, input_params, **kwargs):
        for prefix, result in self.outputs_by_code_prefix.items():
            if code.startswith(prefix):
                return dict(result)
        return {"status": "failed", "output": "no handler"}


class TestRegressionValidator:
    @pytest.mark.asyncio
    async def test_no_test_inputs_skips(self):
        from core.auto_dev.regression_validator import RegressionValidator

        result = await RegressionValidator().validate_regression(
            "parent", "child", [], sandbox=MagicMock(), tenant_id="t",
        )
        assert result.passed is True
        assert result.total_tests == 0

    @pytest.mark.asyncio
    async def test_child_crash_is_regression(self):
        from core.auto_dev.regression_validator import RegressionValidator

        sandbox = FakeRegressionSandbox({
            "PARENT": {"status": "success", "output": "out"},
            "CHILD": {"status": "failed", "output": "NameError: x"},
        })
        result = await RegressionValidator().validate_regression(
            "PARENT code", "CHILD code", [{"x": 1}], sandbox=sandbox,
            tenant_id="t",
        )
        assert result.passed is False
        assert result.regression_detected is True
        assert "[CRASH]" in result.mismatches[0].child_output
        assert result.passed_tests == 0

    @pytest.mark.asyncio
    async def test_parent_crash_child_fixed_is_improvement(self):
        from core.auto_dev.regression_validator import RegressionValidator

        sandbox = FakeRegressionSandbox({
            "PARENT": {"status": "failed", "output": "boom"},
            "CHILD": {"status": "success", "output": "fixed"},
        })
        result = await RegressionValidator().validate_regression(
            "PARENT code", "CHILD code", [{"x": 1}], sandbox=sandbox,
            tenant_id="t",
        )
        assert result.passed is True
        assert result.passed_tests == 1

    @pytest.mark.asyncio
    async def test_matching_outputs_pass(self):
        from core.auto_dev.regression_validator import RegressionValidator

        sandbox = FakeRegressionSandbox({
            "P": {"status": "success", "output": "result 42"},
            "C": {"status": "success", "output": "result 42"},
        })
        result = await RegressionValidator().validate_regression(
            "P code", "C code", [{"x": 1}, {"x": 2}], sandbox=sandbox,
            tenant_id="t",
        )
        assert result.passed is True
        assert result.passed_tests == 2
        assert result.total_tests == 2

    @pytest.mark.asyncio
    async def test_differing_outputs_mismatch(self):
        from core.auto_dev.regression_validator import RegressionValidator

        sandbox = FakeRegressionSandbox({
            "P": {"status": "success", "output": "alpha"},
            "C": {"status": "success", "output": "beta"},
        })
        result = await RegressionValidator().validate_regression(
            "P code", "C code", [{"x": 1}], sandbox=sandbox, tenant_id="t",
        )
        assert result.passed is False
        assert result.mismatches[0].parent_output == "alpha"
        assert result.mismatches[0].child_output == "beta"
        d = result.to_dict()
        assert d["mismatch_count"] == 1
        assert d["passed"] is False

    @pytest.mark.asyncio
    async def test_sandbox_raising_treated_as_crash(self):
        from core.auto_dev.regression_validator import RegressionValidator

        sandbox = MagicMock()
        sandbox.execute_raw_python = AsyncMock(side_effect=RuntimeError("sandbox"))
        result = await RegressionValidator().validate_regression(
            "P", "C", [{"x": 1}], sandbox=sandbox, tenant_id="t",
        )
        assert result.passed is False
        assert result.mismatches[0].child_output.startswith("[CRASH]")

    @pytest.mark.asyncio
    async def test_fuzzy_match_within_tolerance(self):
        from core.auto_dev.regression_validator import RegressionValidator

        sandbox = FakeRegressionSandbox({
            "P": {"status": "success", "output": "hello world foo"},
            "C": {"status": "success", "output": "hello world bar"},
        })
        result = await RegressionValidator(
            fuzzy_match=True, fuzzy_tolerance=0.5
        ).validate_regression(
            "P", "C", [{"x": 1}], sandbox=sandbox, tenant_id="t",
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_exact_match_strips_whitespace(self):
        from core.auto_dev.regression_validator import RegressionValidator

        sandbox = FakeRegressionSandbox({
            "P": {"status": "success", "output": "  result  "},
            "C": {"status": "success", "output": "result"},
        })
        result = await RegressionValidator().validate_regression(
            "P", "C", [{"x": 1}], sandbox=sandbox, tenant_id="t",
        )
        assert result.passed is True

    def test_outputs_match_exact_and_fuzzy(self):
        from core.auto_dev.regression_validator import RegressionValidator

        exact = RegressionValidator()
        assert exact._outputs_match("a b c", "a b c") is True
        assert exact._outputs_match("a b c", "a b d") is False

        fuzzy = RegressionValidator(fuzzy_match=True, fuzzy_tolerance=0.8)
        assert fuzzy._outputs_match("hello world", "hello world!") is True
        assert fuzzy._outputs_match("hello", "goodbye") is False


# =============================================================================
# BehaviorAnalyzer
# =============================================================================


class TestBehaviorAnalyzer:
    def _make(self, monkeypatch):
        analytics = MagicMock()
        monkeypatch.setattr(
            "core.behavior_analyzer.get_analytics_engine",
            lambda: analytics,
        )
        from core.behavior_analyzer import BehaviorAnalyzer

        return BehaviorAnalyzer(), analytics

    def test_log_user_action_creates_window(self, monkeypatch):
        analyzer, analytics = self._make(monkeypatch)
        analyzer.log_user_action("u-1", "meeting_ended", workspace_id="ws-1")
        assert "ws-1_u-1" in analyzer.user_action_windows
        analytics.track_user_activity.assert_called_once()
        key = "ws-1_u-1"
        assert analyzer.user_action_windows[key][0]["action_type"] == "meeting_ended"

    def test_log_user_action_default_workspace(self, monkeypatch):
        analyzer, _ = self._make(monkeypatch)
        analyzer.log_user_action("u-1", "task_created")
        assert "default_u-1" in analyzer.user_action_windows

    def test_log_user_action_window_capped(self, monkeypatch):
        analyzer, _ = self._make(monkeypatch)
        for i in range(15):
            analyzer.log_user_action("u-2", f"action_{i}", workspace_id="w")
        assert len(analyzer.user_action_windows["w_u-2"]) == analyzer.window_size
        assert analyzer.user_action_windows["w_u-2"][0]["action_type"] == "action_5"

    def test_detect_patterns_too_few_actions(self, monkeypatch):
        analyzer, _ = self._make(monkeypatch)
        analyzer.log_user_action("u-3", "a", workspace_id="w")
        analyzer.log_user_action("u-3", "b", workspace_id="w")
        assert analyzer.detect_patterns("u-3", "w") == []

    def test_detect_meeting_followup_pattern(self, monkeypatch):
        analyzer, _ = self._make(monkeypatch)
        for action in ["meeting_ended", "task_created", "meeting_ended"]:
            analyzer.log_user_action("u-4", action, workspace_id="w")
        patterns = analyzer.detect_patterns("u-4", "w")
        names = [p["name"] for p in patterns]
        assert "Meeting Follow-up Automation" in names

    def test_detect_document_ingestion_pattern(self, monkeypatch):
        analyzer, _ = self._make(monkeypatch)
        for action in ["document_uploaded", "knowledge_update", "document_uploaded"]:
            analyzer.log_user_action("u-5", action, workspace_id="w")
        patterns = analyzer.detect_patterns("u-5", "w")
        names = [p["name"] for p in patterns]
        assert "Automated Knowledge Extraction" in names

    def test_detect_patterns_with_metadata(self, monkeypatch):
        analyzer, _ = self._make(monkeypatch)
        for action in ["meeting_ended", "task_created", "meeting_ended"]:
            analyzer.log_user_action(
                "u-6", action, metadata={"meeting_id": 1}, workspace_id="w"
            )
        patterns = analyzer.detect_patterns("u-6", "w")
        assert patterns[0]["confidence"] == 0.8
        assert patterns[0]["suggested_actions"] == [
            "extract_action_items", "create_asana_task"
        ]

    def test_get_behavior_analyzer_singleton(self, monkeypatch):
        import core.behavior_analyzer as module

        monkeypatch.setattr(module, "_behavior_analyzer", None)
        a = module.get_behavior_analyzer()
        b = module.get_behavior_analyzer()
        assert a is b


# =============================================================================
# BurnoutDetectionEngine
# =============================================================================


class TestBurnoutDetectionEngine:
    @pytest.mark.asyncio
    async def test_burnout_critical_level(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine

        engine = BurnoutDetectionEngine()
        result = await engine.calculate_burnout_risk(
            meeting_metrics={"total_hours": 6.0, "day_count": 1},
            task_metrics={"open_tasks": 20, "previous_open_tasks": 10},
            comm_metrics={"avg_response_latency_hours": 6.0},
        )
        assert result.risk_level == "Critical"
        assert result.score >= 80
        assert result.type == "burnout"
        assert result.factors["meeting_density"] == 100.0

    @pytest.mark.asyncio
    async def test_burnout_high_level(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine

        engine = BurnoutDetectionEngine()
        result = await engine.calculate_burnout_risk(
            meeting_metrics={"total_hours": 3.0, "day_count": 1},
            task_metrics={"open_tasks": 8, "previous_open_tasks": 5},
            comm_metrics={"avg_response_latency_hours": 2.0},
        )
        assert result.risk_level == "High"

    @pytest.mark.asyncio
    async def test_burnout_medium_and_low(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine

        engine = BurnoutDetectionEngine()
        result = await engine.calculate_burnout_risk(
            meeting_metrics={"total_hours": 2.0, "day_count": 1},
            task_metrics={"open_tasks": 5, "previous_open_tasks": 5},
            comm_metrics={"avg_response_latency_hours": 1.0},
        )
        assert result.risk_level == "Medium"
        result = await engine.calculate_burnout_risk(
            meeting_metrics={"total_hours": 0.0, "day_count": 0},
            task_metrics={"open_tasks": 0, "previous_open_tasks": 0},
            comm_metrics={"avg_response_latency_hours": 0.0},
        )
        assert result.risk_level == "Low"
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_burnout_custom_settings(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine

        engine = BurnoutDetectionEngine(settings={
            "max_meeting_hours_daily": 10.0,
            "max_backlog_growth_rate": 2.0,
            "latency_threshold_hours": 8.0,
        })
        result = await engine.calculate_burnout_risk(
            meeting_metrics={"total_hours": 5.0, "day_count": 1},
            task_metrics={"open_tasks": 4, "previous_open_tasks": 2},
            comm_metrics={"avg_response_latency_hours": 2.0},
        )
        assert result.risk_level == "Medium"

    @pytest.mark.asyncio
    async def test_deadline_risk_critical_with_recs(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine

        engine = BurnoutDetectionEngine()
        now = datetime.now()
        tasks = [
            {
                "id": "1", "title": "Ship report",
                "due_date": (now + timedelta(hours=2)).isoformat(),
                "progress": 0.0, "estimated_hours": 20,
            },
        ]
        result = await engine.calculate_deadline_risk(tasks)
        assert result.type == "deadline"
        assert result.factors["at_risk_count"] == 1
        assert any("Ship report" in r for r in result.recommendations)
        assert result.risk_level in ("High", "Critical")

    @pytest.mark.asyncio
    async def test_deadline_risk_low_no_tasks(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine

        engine = BurnoutDetectionEngine()
        result = await engine.calculate_deadline_risk([])
        assert result.risk_level == "Low"
        assert result.score == 0.0
        assert result.recommendations == []

    @pytest.mark.asyncio
    async def test_deadline_risk_utc_z_string(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine

        engine = BurnoutDetectionEngine()
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat().replace(
            "+00:00", "Z"
        )
        result = await engine.calculate_deadline_risk([
            {
                "id": "2", "title": "Relax", "due_date": future,
                "progress": 0.9, "estimated_hours": 1,
            },
        ])
        assert result.risk_level == "Low"

    def test_generate_recommendations_all_factors(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine

        engine = BurnoutDetectionEngine()
        recs = engine._generate_recommendations("Critical", {
            "meeting_density": 80, "backlog_growth": 80, "comm_latency": 80,
        })
        assert len(recs) >= 5

    def test_generate_recommendations_critical_no_factors(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine

        engine = BurnoutDetectionEngine()
        recs = engine._generate_recommendations("Critical", {
            "meeting_density": 10, "backlog_growth": 10, "comm_latency": 10,
        })
        assert recs == ["Take a mandatory unplugged day."]

    def test_generate_recommendations_low_level(self):
        from core.burnout_detection_engine import BurnoutDetectionEngine

        engine = BurnoutDetectionEngine()
        assert engine._generate_recommendations("Low", {
            "meeting_density": 50, "backlog_growth": 50, "comm_latency": 50,
        }) == []

    def test_wellness_score_model_defaults(self):
        from core.burnout_detection_engine import WellnessScore

        score = WellnessScore(
            risk_level="Low", score=10.0, factors={},
            recommendations=[], timestamp=datetime.now(),
        )
        assert score.type == "burnout"
