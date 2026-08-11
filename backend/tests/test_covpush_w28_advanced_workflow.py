"""Coverage wave 28 — core/advanced_workflow_system.py (TDD).

Drives the definition model (missing-input logic, show-when conditions,
step outputs), StateManager (memory/file persistence, traversal-safe
ids, listing/filters/sort/pagination), ParameterValidator (all types +
rules), ExecutionEngine (create/validate/cycle-detection/start/plan/
execute/pause/resume/cancel/status) and the high-level system facade —
fully mocked, no I/O side effects beyond a temp dir, zero LLM spend.
"""
import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.advanced_workflow_system import (
    AdvancedWorkflowDefinition,
    AdvancedWorkflowSystem,
    ExecutionEngine,
    ExecutionResult,
    InputParameter,
    MultiOutputConfig,
    ParameterType,
    ParameterValidator,
    StateManager,
    WorkflowExecutionPlan,
    WorkflowResult,
    WorkflowState,
    WorkflowStep,
)


def param(**kw):
    defaults = dict(name="p", type=ParameterType.STRING, label="Param",
                    description="d", required=True, default_value=None,
                    validation_rules={}, options=[], depends_on=None,
                    show_when=None)
    defaults.update(kw)
    return InputParameter(**defaults)


def step(**kw):
    defaults = dict(step_id="s1", name="Step 1", description="d",
                    step_type="api_call", input_parameters=[],
                    output_schema={}, depends_on=[], condition=None,
                    retry_config={}, timeout_seconds=300, can_pause=True,
                    is_parallel=False)
    defaults.update(kw)
    return WorkflowStep(**defaults)


def workflow_def(**kw):
    defaults = dict(
        workflow_id="wf-1", name="Test WF", description="d", version="1.0",
        category="general", tags=[], input_schema=[], steps=[],
        step_connections=[], output_config=None,
        state=WorkflowState.DRAFT, current_step=None,
        execution_context={}, user_inputs={}, step_results={},
        created_by="u1")
    defaults.update(kw)
    return AdvancedWorkflowDefinition(**defaults)


# ---------------------------------------------------------------------------
# Definition model
# ---------------------------------------------------------------------------


class TestDefinitionModel:
    def test_advance_to_step(self):
        wf = workflow_def()
        wf.advance_to_step("s2")
        assert wf.current_step == "s2"

    def test_get_missing_inputs(self):
        wf = workflow_def(input_schema=[
            param(name="a", required=True),
            param(name="b", required=True, default_value="x"),
            param(name="c", required=False),
            param(name="hidden", required=True,
                  show_when={"a": "yes"}),
        ])
        missing = wf.get_missing_inputs({"a": "no"})
        names = [m["name"] for m in missing]
        assert "a" not in names  # provided
        assert "b" not in names  # has default
        assert "c" not in names  # not required
        assert "hidden" not in names  # hidden by show_when
        # With "a" = "yes", hidden becomes required
        missing2 = wf.get_missing_inputs({})
        assert "a" in [m["name"] for m in missing2]
        assert missing2[0]["type"] == "string"

    def test_should_show_parameter(self):
        wf = workflow_def()
        assert wf._should_show_parameter(param(name="p"), {}) is True
        p = param(name="p", show_when={"mode": ["fast", "slow"]})
        assert wf._should_show_parameter(p, {"mode": "fast"}) is True
        assert wf._should_show_parameter(p, {"mode": "other"}) is False
        assert wf._should_show_parameter(p, {}) is False
        p2 = param(name="p", show_when={"mode": "fast"})
        assert wf._should_show_parameter(p2, {"mode": "fast"}) is True
        assert wf._should_show_parameter(p2, {"mode": "slow"}) is False

    def test_step_outputs(self):
        wf = workflow_def()
        wf.add_step_output("s1", {"data": 1})
        assert wf.step_results["s1"]["output"] == {"data": 1}
        assert wf.get_all_outputs() == {"s1": {"data": 1}}

    def test_validate_step_ids(self):
        wf = AdvancedWorkflowDefinition(
            workflow_id="w", name="n", description="d",
            steps=[step(step_id="s1")])
        assert wf.steps[0].step_id == "s1"


# ---------------------------------------------------------------------------
# StateManager
# ---------------------------------------------------------------------------


class TestStateManager:
    def test_save_and_load_memory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        assert sm.save_state("wf-1", {"name": "W"}) is True
        state = sm.load_state("wf-1")
        assert state["name"] == "W"
        assert "saved_at" in state

    def test_load_from_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        import os
        os.makedirs("workflow_states", exist_ok=True)
        with open("workflow_states/wf-2.json", "w") as f:
            json.dump({"name": "FromFile"}, f)
        sm = StateManager()
        state = sm.load_state("wf-2")
        assert state["name"] == "FromFile"
        assert "wf-2" in sm.state_store  # cached

    def test_load_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        assert sm.load_state("ghost") is None

    def test_persist_sanitizes_id(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        sm.save_state("../evil", {"x": 1})
        assert sm.load_state("..evil") is not None or "evil" in sm.state_store

    def test_persist_invalid_id_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        with pytest.raises(ValueError, match="alphanumeric"):
            sm._persist_to_file("!!!", {})

    def test_load_invalid_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        import os
        os.makedirs("workflow_states", exist_ok=True)
        with open("workflow_states/bad.json", "w") as f:
            f.write("{not json")
        sm = StateManager()
        assert sm.load_state("bad") is None

    def test_save_exception_returns_false(self):
        sm = StateManager()
        with patch.object(sm, "_persist_to_file", side_effect=RuntimeError("disk full")):
            assert sm.save_state("wf-1", {}) is False

    def test_list_workflows_memory_and_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        import os
        os.makedirs("workflow_states", exist_ok=True)
        sm = StateManager()
        sm.state_store["mem-1"] = {"name": "Memory WF", "steps": [{"id": "a"}],
                                   "state": WorkflowState.RUNNING, "category": "ops",
                                   "tags": ["a", "b"], "created_at": "t1", "updated_at": "t2"}
        with open("workflow_states/file-1.json", "w") as f:
            json.dump({"name": "File WF", "steps": [], "state": "draft",
                       "category": "general", "tags": [], "updated_at": "t3"}, f)
        results = sm.list_workflows()
        ids = {r["workflow_id"] for r in results}
        assert "mem-1" in ids and "file-1" in ids

    def test_list_workflows_filters_and_pagination(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        for i in range(3):
            sm.state_store[f"wf-{i}"] = {
                "name": f"W{i}", "steps": [], "state": "draft",
                "category": "general", "tags": ["x"] if i == 0 else [],
                "created_at": f"t{i}", "updated_at": f"t{i}"}
        results = sm.list_workflows(status="draft", category="general",
                                    tags=["x"], sort_by="name", sort_order="asc",
                                    limit=1, offset=0)
        assert len(results) == 1
        assert results[0]["workflow_id"] == "wf-0"

    def test_list_workflows_offset(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        for i in range(3):
            sm.state_store[f"wf-{i}"] = {"name": f"W{i}", "steps": [],
                                         "state": "draft", "category": "g",
                                         "tags": [], "updated_at": f"t{i}"}
        results = sm.list_workflows(offset=2)
        assert len(results) == 1

    def test_list_workflows_bad_sort_key(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        sm.state_store["wf-1"] = {"name": "W", "steps": [], "state": "draft",
                                  "category": "g", "tags": [], "updated_at": "t"}
        results = sm.list_workflows(sort_by="bogus")
        assert len(results) == 1

    def test_list_workflows_exception(self):
        sm = StateManager()
        with patch.object(sm, "_create_workflow_summary", side_effect=RuntimeError("boom")):
            assert sm.list_workflows() == []

    def test_create_summary_enum_state(self):
        sm = StateManager()
        summary = sm._create_workflow_summary("wf-1", {
            "name": "W", "steps": [1, 2], "state": WorkflowState.RUNNING,
            "tags": ["a"], "version": "2.0", "created_by": "u"})
        assert summary["state"] == "running"
        assert summary["total_steps"] == 2
        assert summary["version"] == "2.0"

    def test_delete_state(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        import os
        os.makedirs("workflow_states", exist_ok=True)
        with open("workflow_states/del-1.json", "w") as f:
            json.dump({"name": "X"}, f)
        sm = StateManager()
        sm.state_store["del-1"] = {"name": "X"}
        assert sm.delete_state("del-1") is True
        assert "del-1" not in sm.state_store

    def test_delete_state_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        sm.state_store["mem-only"] = {"name": "X"}
        assert sm.delete_state("mem-only") is False

    def test_delete_state_invalid_id(self):
        sm = StateManager()
        assert sm.delete_state("!!!") is False

    def test_delete_state_exception(self):
        sm = StateManager()
        with patch("os.path.exists", side_effect=RuntimeError("boom")):
            assert sm.delete_state("wf-1") is False


# ---------------------------------------------------------------------------
# ParameterValidator
# ---------------------------------------------------------------------------


class TestParameterValidator:
    def test_required_missing(self):
        p = param(name="a", label="Alpha")
        ok, err = ParameterValidator.validate_parameter(p, None)
        assert ok is False
        assert "Alpha is required" in err

    def test_default_used(self):
        p = param(name="a", type=ParameterType.NUMBER, default_value=5)
        ok, err = ParameterValidator.validate_parameter(p, None)
        assert ok is True

    def test_optional_none_valid(self):
        p = param(name="a", required=False)
        assert ParameterValidator.validate_parameter(p, None) == (True, None)

    def test_string_type(self):
        p = param(name="a", type=ParameterType.STRING)
        assert ParameterValidator.validate_parameter(p, "x")[0] is True
        assert ParameterValidator.validate_parameter(p, 5)[0] is False

    def test_number_type(self):
        p = param(name="a", type=ParameterType.NUMBER)
        assert ParameterValidator.validate_parameter(p, 5)[0] is True
        assert ParameterValidator.validate_parameter(p, 5.5)[0] is True
        assert ParameterValidator.validate_parameter(p, True)[0] is False
        assert ParameterValidator.validate_parameter(p, "x")[0] is False

    def test_boolean_type(self):
        p = param(name="a", type=ParameterType.BOOLEAN)
        assert ParameterValidator.validate_parameter(p, True)[0] is True
        assert ParameterValidator.validate_parameter(p, "yes")[0] is False

    def test_array_type(self):
        p = param(name="a", type=ParameterType.ARRAY)
        assert ParameterValidator.validate_parameter(p, [1])[0] is True
        assert ParameterValidator.validate_parameter(p, "x")[0] is False

    def test_select_type(self):
        p = param(name="a", type=ParameterType.SELECT, options=["x", "y"])
        assert ParameterValidator.validate_parameter(p, "x")[0] is True
        assert ParameterValidator.validate_parameter(p, "z")[0] is False

    def test_multiselect_type(self):
        p = param(name="a", type=ParameterType.MULTISELECT, options=["x", "y"])
        assert ParameterValidator.validate_parameter(p, ["x"])[0] is True
        assert ParameterValidator.validate_parameter(p, "x")[0] is False
        assert ParameterValidator.validate_parameter(p, ["x", "z"])[0] is False

    def test_length_rules(self):
        p = param(name="a", validation_rules={"min_length": 3, "max_length": 5})
        assert ParameterValidator.validate_parameter(p, "abc")[0] is True
        assert ParameterValidator.validate_parameter(p, "ab")[0] is False
        assert ParameterValidator.validate_parameter(p, "abcdef")[0] is False

    def test_value_rules(self):
        p = param(name="a", type=ParameterType.NUMBER,
                  validation_rules={"min_value": 1, "max_value": 10})
        assert ParameterValidator.validate_parameter(p, 5)[0] is True
        assert ParameterValidator.validate_parameter(p, 0)[0] is False
        assert ParameterValidator.validate_parameter(p, 11)[0] is False

    def test_pattern_rule(self):
        p = param(name="a", validation_rules={"pattern": r"^[a-z]+$"})
        assert ParameterValidator.validate_parameter(p, "abc")[0] is True
        assert ParameterValidator.validate_parameter(p, "ABC")[0] is False

    def test_pattern_too_complex(self):
        p = param(name="a", validation_rules={"pattern": "x" * 1000})
        ok, err = ParameterValidator.validate_parameter(p, "abc")
        assert ok is False
        assert "too complex" in err

    def test_exception_returns_validation_failed(self):
        p = param(name="a", validation_rules={"min_length": 3})
        with patch("core.advanced_workflow_system.isinstance",
                   side_effect=RuntimeError("boom")):
            ok, err = ParameterValidator.validate_parameter(p, "abc")
        assert ok is False
        assert err == "Validation failed"


# ---------------------------------------------------------------------------
# ExecutionEngine
# ---------------------------------------------------------------------------


class TestExecutionEngine:
    async def test_create_workflow_success(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        wf = await engine.create_workflow({
            "workflow_id": "wf-1", "name": "W", "description": "d",
            "steps": [step().dict()]})
        assert wf.workflow_id == "wf-1"

    async def test_create_workflow_invalid(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        with pytest.raises(ValueError, match="Invalid workflow"):
            await engine.create_workflow({
                "workflow_id": "wf-1", "name": "W", "description": "d",
                "steps": [step(depends_on=["ghost"]).dict()]})

    def test_validate_workflow_missing_dep(self):
        engine = ExecutionEngine(StateManager())
        ok, err = engine._validate_workflow(
            workflow_def(steps=[step(depends_on=["ghost"])]))
        assert ok is False
        assert "non-existent" in err

    def test_validate_workflow_circular(self):
        engine = ExecutionEngine(StateManager())
        wf = workflow_def(steps=[
            step(step_id="a", depends_on=["b"]),
            step(step_id="b", depends_on=["a"]),
        ])
        ok, err = engine._validate_workflow(wf)
        assert ok is False
        assert "circular" in err

    def test_validate_workflow_ok(self):
        engine = ExecutionEngine(StateManager())
        ok, err = engine._validate_workflow(workflow_def(steps=[step()]))
        assert ok is True

    def test_validate_workflow_exception(self):
        engine = ExecutionEngine(StateManager())
        with patch.object(engine, "_has_circular_dependencies",
                          side_effect=RuntimeError("boom")):
            ok, err = engine._validate_workflow(workflow_def(steps=[step()]))
        assert ok is False
        assert "Validation error" in err

    def test_has_circular_dependencies(self):
        engine = ExecutionEngine(StateManager())
        assert engine._has_circular_dependencies([step()]) is False
        assert engine._has_circular_dependencies([
            step(step_id="a", depends_on=["b"]),
            step(step_id="b", depends_on=["a"]),
        ]) is True
        # self-dependency
        assert engine._has_circular_dependencies([
            step(step_id="a", depends_on=["a"])]) is True

    async def test_start_workflow_not_found(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        with pytest.raises(ValueError, match="not found"):
            await engine.start_workflow("ghost", {})

    async def test_start_workflow_already_running(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        sm.state_store["wf-1"] = workflow_def().dict()
        engine.running_workflows["wf-1"] = MagicMock()
        with pytest.raises(ValueError, match="already running"):
            await engine.start_workflow("wf-1", {})

    async def test_start_workflow_missing_inputs(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        wf = workflow_def(input_schema=[param(name="required_field", label="RF")])
        sm.state_store["wf-1"] = wf.dict()
        result = await engine.start_workflow("wf-1", {})
        assert result["status"] == "waiting_for_input"
        assert result["missing_parameters"]

    async def test_start_workflow_validation_errors(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        wf = workflow_def(input_schema=[param(name="count", label="Count",
                                              type=ParameterType.NUMBER)])
        sm.state_store["wf-1"] = wf.dict()
        result = await engine.start_workflow("wf-1", {"count": "not-a-number"})
        assert result["status"] == "waiting_for_input"
        assert "count" in result["validation_errors"]

    async def test_start_workflow_success(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        wf = workflow_def(steps=[step()])
        sm.state_store["wf-1"] = wf.dict()
        with patch.object(engine, "_execute_workflow", new=AsyncMock()):
            result = await engine.start_workflow("wf-1", {})
        assert result["status"] == "started"
        assert result["execution_id"]
        task = engine.running_workflows.pop("wf-1", None)
        if task:
            task.cancel()

    def test_get_missing_inputs_global_and_step(self):
        engine = ExecutionEngine(StateManager())
        wf = workflow_def(
            input_schema=[param(name="g1", label="G1")],
            current_step="s1",
            steps=[step(step_id="s1", input_parameters=[
                param(name="s1p", label="S1P")])])
        missing = engine._get_missing_inputs(wf, {})
        assert {m.name for m in missing} == {"g1", "s1p"}
        missing2 = engine._get_missing_inputs(wf, {"g1": "x", "s1p": "y"})
        assert missing2 == []

    def test_should_show_parameter_complex(self):
        engine = ExecutionEngine(StateManager())
        p = param(name="p", show_when={"mode": {"equals": "fast"}})
        assert engine._should_show_parameter(p, {"mode": "fast"}) is True
        assert engine._should_show_parameter(p, {"mode": "slow"}) is False
        p2 = param(name="p", show_when={"mode": {"not_equals": "fast"}})
        assert engine._should_show_parameter(p2, {"mode": "slow"}) is True
        p3 = param(name="p", show_when={"mode": {"contains": "ast"}})
        assert engine._should_show_parameter(p3, {"mode": "fast"}) is True
        assert engine._should_show_parameter(p3, {"mode": "slow"}) is False
        assert engine._should_show_parameter(p3, {}) is False

    def test_create_execution_plan(self):
        engine = ExecutionEngine(StateManager())
        wf = workflow_def(steps=[
            step(step_id="a"),
            step(step_id="b", depends_on=["a"]),
            step(step_id="c", depends_on=["a"]),
        ])
        plan = engine._create_execution_plan(wf)
        assert plan.planned_steps[0] == "a"
        assert set(plan.planned_steps[1:]) == {"b", "c"}
        assert len(plan.parallel_groups) == 1  # b,c parallel

    def test_create_execution_plan_cycle_marker(self):
        engine = ExecutionEngine(StateManager())
        wf = workflow_def(steps=[
            step(step_id="a", depends_on=["b"]),
            step(step_id="b", depends_on=["a"]),
        ])
        plan = engine._create_execution_plan(wf)
        assert plan.estimated_duration == -1

    async def test_execute_workflow_completed(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        wf = workflow_def(steps=[step(step_id="s1"), step(step_id="s2")])
        with patch.object(engine, "_execute_step",
                          new=AsyncMock(return_value={"status": "success",
                                                      "result": {"ok": 1}})):
            await engine._execute_workflow(wf, engine._create_execution_plan(wf))
        assert wf.state == WorkflowState.COMPLETED
        assert "s1" in wf.step_results and "s2" in wf.step_results

    async def test_execute_workflow_error_step_fails(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        wf = workflow_def(steps=[step(step_id="s1")])
        with patch.object(engine, "_execute_step",
                          new=AsyncMock(return_value={"status": "error",
                                                      "error": "boom"})):
            await engine._execute_workflow(wf, engine._create_execution_plan(wf))
        assert wf.state == WorkflowState.FAILED

    async def test_execute_workflow_paused_breaks(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        wf = workflow_def(steps=[step(step_id="s1"), step(step_id="s2")])
        sm.state_store["wf-1"] = {"state": WorkflowState.PAUSED, "name": "W"}
        with patch.object(engine, "_execute_step", new=AsyncMock()):
            await engine._execute_workflow(wf, engine._create_execution_plan(wf))
        assert "s1" not in wf.step_results  # broke before executing

    async def test_execute_workflow_skips_completed(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        wf = workflow_def(steps=[step(step_id="s1")])
        wf.step_results["s1"] = {"old": True}
        with patch.object(engine, "_execute_step", new=AsyncMock()) as exec_mock:
            await engine._execute_workflow(wf, engine._create_execution_plan(wf))
        exec_mock.assert_not_called()

    async def test_execute_workflow_exception(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        wf = workflow_def(steps=[step(step_id="s1")])
        with patch.object(engine, "_execute_step",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            await engine._execute_workflow(wf, engine._create_execution_plan(wf))
        assert wf.state == WorkflowState.FAILED

    async def test_execute_step_all_types(self):
        engine = ExecutionEngine(StateManager())
        wf = workflow_def(user_inputs={"x": 1},
                          step_results={"dep1": {"output": 5}})
        for stype in ["api_call", "data_transform", "user_input", "condition", "custom"]:
            s = step(step_id=f"st-{stype}", step_type=stype, depends_on=["dep1"])
            result = await engine._execute_step(wf, s)
            assert result["status"] == "success"
        assert wf.step_results["dep1"]

    async def test_execute_step_exception(self):
        engine = ExecutionEngine(StateManager())
        wf = workflow_def()
        s = step(step_id="s1", step_type="api_call")
        with patch.object(engine, "_execute_api_call",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await engine._execute_step(wf, s)
        assert result["status"] == "error"
        assert "boom" in result["error"]

    async def test_step_executors(self):
        engine = ExecutionEngine(StateManager())
        s = step()
        assert (await engine._execute_api_call(s, {"a": 1}))["message"]
        assert (await engine._execute_data_transform(s, {}))["message"]
        assert (await engine._execute_user_input(s, {}))["message"]
        assert (await engine._execute_condition(s, {}))["message"]
        r = await engine._execute_custom_step(step(step_type="x"), {})
        assert r["step_type"] == "x"

    def test_pause_workflow(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        assert engine.pause_workflow("ghost") is False
        sm.state_store["wf-1"] = {"state": WorkflowState.DRAFT}
        assert engine.pause_workflow("wf-1") is False
        sm.state_store["wf-1"] = {"state": WorkflowState.RUNNING}
        assert engine.pause_workflow("wf-1") is True
        assert sm.state_store["wf-1"]["state"] == WorkflowState.PAUSED

    def test_pause_workflow_cancels_task(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        sm.state_store["wf-1"] = {"state": WorkflowState.RUNNING}
        task = MagicMock()
        engine.running_workflows["wf-1"] = task
        assert engine.pause_workflow("wf-1") is True
        task.cancel.assert_called_once()
        assert "wf-1" not in engine.running_workflows

    def test_resume_workflow_not_paused(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        sm.state_store["wf-1"] = {"state": WorkflowState.RUNNING}
        with pytest.raises(ValueError, match="not paused"):
            engine.resume_workflow("wf-1")

    async def test_resume_workflow_paused(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        sm.state_store["wf-1"] = {"state": WorkflowState.PAUSED,
                                  "workflow_id": "wf-1",
                                  "user_inputs": {}, "steps": [step().dict()],
                                  "name": "W", "description": "d"}
        with patch.object(engine, "_execute_workflow", new=AsyncMock()):
            result = engine.resume_workflow("wf-1", {"extra": 1})
        assert result["status"] == "resumed"
        assert sm.state_store["wf-1"]["user_inputs"]["extra"] == 1
        task = engine.running_workflows.pop("wf-1", None)
        if task:
            task.cancel()

    def test_cancel_workflow(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        assert engine.cancel_workflow("ghost") is False
        sm.state_store["wf-1"] = {"state": WorkflowState.RUNNING}
        task = MagicMock()
        engine.running_workflows["wf-1"] = task
        assert engine.cancel_workflow("wf-1") is True
        assert sm.state_store["wf-1"]["state"] == WorkflowState.CANCELLED
        task.cancel.assert_called_once()

    def test_get_workflow_status(self):
        sm = StateManager()
        engine = ExecutionEngine(sm)
        assert engine.get_workflow_status("ghost") is None
        sm.state_store["wf-1"] = {"state": WorkflowState.RUNNING,
                                  "current_step": "s1",
                                  "steps": [{"id": "s1"}, {"id": "s2"}],
                                  "step_results": {"s1": {}},
                                  "user_inputs": {}, "updated_at": "t"}
        status = engine.get_workflow_status("wf-1")
        assert status["state"] == WorkflowState.RUNNING
        assert status["progress"] == 50.0

    def test_calculate_progress(self):
        engine = ExecutionEngine(StateManager())
        assert engine._calculate_progress({"steps": [], "step_results": {}}) == 0.0
        assert engine._calculate_progress(
            {"steps": [1, 2], "step_results": {"a": 1}}) == 50.0


# ---------------------------------------------------------------------------
# High-level facade
# ---------------------------------------------------------------------------


class TestAdvancedWorkflowSystem:
    def test_create_parallel(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        system = AdvancedWorkflowSystem()
        result = system.create_parallel({
            "name": "P",
            "parallel_branches": [
                {"steps": ["a", "b"]},
                {"steps": ["c"]},
            ]})
        assert result.workflow_id
        assert result.execution_mode == "parallel"
        assert result.branches == 2
        state = system.state_manager.load_state(result.workflow_id)
        assert len(state["steps"]) == 3

    def test_create_conditional(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        system = AdvancedWorkflowSystem()
        result = system.create_conditional({
            "name": "C",
            "conditions": [{"if": "x > 1"}, {"if": "y < 2"}]})
        assert result.execution_mode == "conditional"
        assert result.conditions == 2

    def test_execute_with_retry(self):
        system = AdvancedWorkflowSystem()
        result = system.execute_with_retry("wf-1", {"max_retries": 3})
        assert result.workflow_id == "wf-1"
        assert result.retry_policy == {"max_retries": 3}
        assert result.attempts == 1
        assert result.status == "pending"

    def test_result_objects(self):
        r = WorkflowResult("wf-1", "parallel", branches=2)
        assert r.branches == 2
        assert r.conditions == 0
        e = ExecutionResult("ex-1", "wf-1", {"max_retries": 2})
        assert e.execution_id == "ex-1"
        assert e.attempts == 1
