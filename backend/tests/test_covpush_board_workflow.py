"""Coverage-push tests for core.advanced_workflow_system (StateManager, ExecutionEngine, facade)."""

import asyncio
import json
import os
from datetime import datetime
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


def _param(
    name="p1",
    type=ParameterType.STRING,
    required=True,
    default_value=None,
    validation_rules=None,
    options=None,
    show_when=None,
    label=None,
    description="",
):
    return InputParameter(
        name=name,
        type=type,
        label=label or name,
        description=description,
        required=required,
        default_value=default_value,
        validation_rules=validation_rules or {},
        options=options or [],
        show_when=show_when,
    )


def _step(step_id="s1", step_type="api_call", depends_on=None, input_parameters=None):
    return WorkflowStep(
        step_id=step_id,
        name=step_id,
        description="",
        step_type=step_type,
        depends_on=depends_on or [],
        input_parameters=input_parameters or [],
    )


def _workflow_def(workflow_id="wf1", steps=None, input_schema=None, **kw):
    base = {
        "workflow_id": workflow_id,
        "name": "WF",
        "description": "",
        "steps": [s.dict() for s in steps] if steps else [],
        "input_schema": [p.dict() for p in input_schema] if input_schema else [],
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# StateManager
# --------------------------------------------------------------------------- #

class TestStateManager:
    @pytest.fixture
    def sm(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        return StateManager()

    def test_save_and_load_memory(self, sm):
        assert sm.save_state("wf1", {"name": "n"}) is True
        assert sm.load_state("wf1")["name"] == "n"
        assert "saved_at" in sm.load_state("wf1")

    def test_save_failure_returns_false(self, sm):
        with patch.object(sm, "_persist_to_file", side_effect=OSError("disk full")):
            assert sm.save_state("wf1", {"name": "n"}) is False

    def test_load_missing_returns_none(self, sm):
        assert sm.load_state("missing") is None

    def test_load_from_file(self, sm):
        sm.save_state("wf1", {"name": "n"})
        sm.state_store.pop("wf1")
        state = sm.load_state("wf1")
        assert state["name"] == "n"
        assert "wf1" in sm.state_store

    def test_load_corrupt_file(self, sm):
        os.makedirs("workflow_states", exist_ok=True)
        with open("workflow_states/wf1.json", "w") as f:
            f.write("{not json")
        assert sm.load_state("wf1") is None

    def test_persist_sanitizes_path(self, sm):
        sm.save_state("../../etc/passwd", {"name": "x"})
        assert os.path.exists("workflow_states/etcpasswd.json")
        assert not os.path.exists("workflow_states/../../etc/passwd.json")

    def test_persist_empty_id_raises(self, sm):
        assert sm.save_state("!!", {"name": "x"}) is False

    def test_load_sanitized_empty_id(self, sm):
        assert sm.load_state("!!!") is None

    def test_list_workflows_memory_and_file(self, sm):
        sm.save_state("wf1", {"name": "A", "state": "running", "category": "ops", "tags": ["x"]})
        sm.save_state("wf2", {"name": "B", "state": "completed", "category": "dev", "tags": ["x", "y"]})
        rows = sm.list_workflows()
        assert {r["workflow_id"] for r in rows} == {"wf1", "wf2"}

    def test_list_filters(self, sm):
        sm.save_state("wf1", {"name": "A", "state": "running", "category": "ops", "tags": ["x"]})
        sm.save_state("wf2", {"name": "B", "state": "completed", "category": "dev", "tags": ["x", "y"]})
        assert [r["workflow_id"] for r in sm.list_workflows(status="running")] == ["wf1"]
        assert [r["workflow_id"] for r in sm.list_workflows(category="dev")] == ["wf2"]
        assert [r["workflow_id"] for r in sm.list_workflows(tags=["x", "y"])] == ["wf2"]
        assert [r["workflow_id"] for r in sm.list_workflows(tags=["z"])] == []

    def test_list_sort_and_pagination(self, sm):
        sm.save_state("wf1", {"name": "A", "state": "draft"})
        sm.save_state("wf2", {"name": "b", "state": "draft"})
        by_name_asc = sm.list_workflows(sort_by="name", sort_order="asc")
        assert [r["name"] for r in by_name_asc] == ["A", "b"]
        by_name_desc = sm.list_workflows(sort_by="name", sort_order="desc")
        assert [r["name"] for r in by_name_desc] == ["b", "A"]
        paginated = sm.list_workflows(offset=1, limit=1)
        assert len(paginated) == 1

    def test_list_invalid_sort_field(self, sm):
        sm.save_state("wf1", {"name": "A", "state": "draft", "created_at": "2026-01-01"})
        rows = sm.list_workflows(sort_by="bogus")
        assert len(rows) == 1

    def test_list_exception_returns_empty(self, sm, monkeypatch):
        sm.save_state("wf1", {"name": "A"})
        monkeypatch.setattr(
            sm, "_create_workflow_summary", MagicMock(side_effect=RuntimeError("x"))
        )
        assert sm.list_workflows() == []

    def test_list_ignores_corrupt_dir_files(self, sm):
        os.makedirs("workflow_states", exist_ok=True)
        with open("workflow_states/bad.json", "w") as f:
            f.write("{nope")
        assert sm.list_workflows() == []

    def test_summary_enum_state(self, sm):
        summary = sm._create_workflow_summary(
            "wf1",
            {"name": "A", "state": WorkflowState.RUNNING, "steps": [], "tags": [], "category": "g"},
        )
        assert summary["state"] == "running"
        assert summary["status"] == "running"
        assert summary["total_steps"] == 0

    def test_delete_state(self, sm):
        sm.save_state("wf1", {"name": "A"})
        assert sm.delete_state("wf1") is True
        assert sm.load_state("wf1") is None
        assert sm.delete_state("wf1") is False

    def test_delete_state_memory_only(self, sm):
        sm.state_store["wf1"] = {"name": "A"}
        assert sm.delete_state("wf1") is False

    def test_delete_state_empty_id(self, sm):
        assert sm.delete_state("###") is False

    def test_delete_state_exception(self, sm):
        sm.state_store["wf1"] = {"name": "A"}
        with patch("os.remove", side_effect=OSError("denied")):
            assert sm.delete_state("wf1") is False


# --------------------------------------------------------------------------- #
# ParameterValidator
# --------------------------------------------------------------------------- #

class TestParameterValidator:
    def test_required_missing_no_default(self):
        ok, err = ParameterValidator.validate_parameter(_param(), None)
        assert (ok, err) == (False, "p1 is required")

    def test_required_missing_with_default(self):
        ok, _ = ParameterValidator.validate_parameter(_param(default_value="d"), None)
        assert ok is True

    def test_optional_none(self):
        ok, _ = ParameterValidator.validate_parameter(_param(required=False), None)
        assert ok is True

    def test_string_type(self):
        ok, err = ParameterValidator.validate_parameter(_param(type=ParameterType.STRING), 42)
        assert (ok, err) == (False, "p1 must be a string")
        ok, _ = ParameterValidator.validate_parameter(_param(type=ParameterType.STRING), "s")
        assert ok is True

    def test_number_type(self):
        ok, err = ParameterValidator.validate_parameter(_param(type=ParameterType.NUMBER), True)
        assert err == "p1 must be a number"
        ok, _ = ParameterValidator.validate_parameter(_param(type=ParameterType.NUMBER), 5)
        assert ok is True
        ok, _ = ParameterValidator.validate_parameter(_param(type=ParameterType.NUMBER), 1.5)
        assert ok is True

    def test_boolean_type(self):
        ok, err = ParameterValidator.validate_parameter(_param(type=ParameterType.BOOLEAN), "yes")
        assert err == "p1 must be true or false"
        ok, _ = ParameterValidator.validate_parameter(_param(type=ParameterType.BOOLEAN), True)
        assert ok is True

    def test_array_type(self):
        ok, err = ParameterValidator.validate_parameter(_param(type=ParameterType.ARRAY), "no")
        assert err == "p1 must be an array"
        ok, _ = ParameterValidator.validate_parameter(_param(type=ParameterType.ARRAY), [1])
        assert ok is True

    def test_object_and_file_pass(self):
        ok, _ = ParameterValidator.validate_parameter(_param(type=ParameterType.OBJECT), {"a": 1})
        assert ok is True
        ok, _ = ParameterValidator.validate_parameter(_param(type=ParameterType.FILE), "path")
        assert ok is True

    def test_select_type(self):
        p = _param(type=ParameterType.SELECT, options=["a", "b"])
        ok, err = ParameterValidator.validate_parameter(p, "c")
        assert "must be one of" in err
        ok, _ = ParameterValidator.validate_parameter(p, "a")
        assert ok is True

    def test_multiselect_type(self):
        p = _param(type=ParameterType.MULTISELECT, options=["a", "b"])
        ok, err = ParameterValidator.validate_parameter(p, "a")
        assert err == "p1 must be an array"
        ok, err = ParameterValidator.validate_parameter(p, ["a", "z"])
        assert "must be from" in err
        ok, _ = ParameterValidator.validate_parameter(p, ["a", "b"])
        assert ok is True

    def test_validation_rules(self):
        p = _param(validation_rules={"min_length": 3, "max_length": 5})
        assert ParameterValidator.validate_parameter(p, "ab")[0] is False
        assert ParameterValidator.validate_parameter(p, "abcdef")[0] is False
        assert ParameterValidator.validate_parameter(p, "abcd")[0] is True

        n = _param(type=ParameterType.NUMBER, validation_rules={"min_value": 1, "max_value": 10})
        assert ParameterValidator.validate_parameter(n, 0)[0] is False
        assert ParameterValidator.validate_parameter(n, 11)[0] is False
        assert ParameterValidator.validate_parameter(n, 5)[0] is True

        pat = _param(validation_rules={"pattern": r"^[A-Z]+$"})
        assert ParameterValidator.validate_parameter(pat, "abc")[0] is False
        assert ParameterValidator.validate_parameter(pat, "ABC")[0] is True

    def test_exception_returns_false(self):
        p = _param(validation_rules={"min_value": 1})
        ok, err = ParameterValidator.validate_parameter(p, "abc")
        assert (ok, err) == (False, "Validation failed")


# --------------------------------------------------------------------------- #
# ExecutionEngine
# --------------------------------------------------------------------------- #

@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return ExecutionEngine(StateManager())


class TestExecutionEngine:
    @pytest.fixture
    def engine(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        return ExecutionEngine(StateManager())

    @pytest.mark.asyncio
    async def test_create_workflow_ok(self, engine):
        wf = await engine.create_workflow(_workflow_def(steps=[_step()]))
        assert wf.workflow_id == "wf1"
        assert engine.state_manager.load_state("wf1") is not None

    @pytest.mark.asyncio
    async def test_create_workflow_invalid(self, engine):
        steps = [_step(step_id="s1", depends_on=["ghost"])]
        with pytest.raises(ValueError) as ei:
            await engine.create_workflow(_workflow_def(steps=steps))
        assert "non-existent step" in str(ei.value)

    def test_validate_workflow_circular(self, engine):
        steps = [_step(step_id="a", depends_on=["b"]), _step(step_id="b", depends_on=["a"])]
        ok, err = engine._validate_workflow(AdvancedWorkflowDefinition(**_workflow_def(steps=steps)))
        assert ok is False
        assert "circular" in err

    def test_validate_workflow_self_cycle(self, engine):
        steps = [_step(step_id="a", depends_on=["a"])]
        assert engine._has_circular_dependencies(steps) is True

    def test_validate_workflow_ok(self, engine):
        steps = [_step(step_id="a", depends_on=["b"]), _step(step_id="b")]
        ok, _ = engine._validate_workflow(AdvancedWorkflowDefinition(**_workflow_def(steps=steps)))
        assert ok is True

    def test_has_cycle_missing_step(self, engine):
        assert engine._has_circular_dependencies([_step(step_id="a", depends_on=["zzz"])]) is False

    @pytest.mark.asyncio
    async def test_start_workflow_missing(self, engine):
        with pytest.raises(ValueError):
            await engine.start_workflow("nope", {})

    @pytest.mark.asyncio
    async def test_start_workflow_waiting_for_input(self, engine):
        params = [_param(name="a")]
        await engine.create_workflow(_workflow_def(input_schema=params))
        result = await engine.start_workflow("wf1", {})
        assert result["status"] == "waiting_for_input"
        assert result["missing_parameters"][0].name == "a"
        state = engine.state_manager.load_state("wf1")
        assert state["state"] == WorkflowState.WAITING_FOR_INPUT

    @pytest.mark.asyncio
    async def test_start_workflow_validation_errors(self, engine):
        params = [_param(name="a", type=ParameterType.NUMBER)]
        await engine.create_workflow(_workflow_def(input_schema=params))
        result = await engine.start_workflow("wf1", {"a": "not-a-number"})
        assert result["status"] == "waiting_for_input"
        assert "a" in result["validation_errors"]

    @pytest.mark.asyncio
    async def test_start_workflow_success(self, engine):
        await engine.create_workflow(_workflow_def(steps=[_step()]))
        result = await engine.start_workflow("wf1", {})
        assert result["status"] == "started"
        assert result["execution_id"]
        task = engine.running_workflows["wf1"]
        await asyncio.wait_for(task, timeout=5)
        status = engine.get_workflow_status("wf1")
        assert status["state"] == WorkflowState.COMPLETED

    @pytest.mark.asyncio
    async def test_start_workflow_already_running(self, engine):
        await engine.create_workflow(_workflow_def(steps=[_step()]))
        await engine.start_workflow("wf1", {})
        with pytest.raises(ValueError) as ei:
            await engine.start_workflow("wf1", {})
        assert "already running" in str(ei.value)
        task = engine.running_workflows.pop("wf1")
        task.cancel()

    def test_get_missing_inputs_global_and_step(self, engine):
        params = [_param(name="g")]
        step_params = [_param(name="s")]
        wf = AdvancedWorkflowDefinition(
            **_workflow_def(
                input_schema=params,
                steps=[_step(step_id="s1", input_parameters=step_params)],
            )
        )
        wf.current_step = "s1"
        missing = engine._get_missing_inputs(wf, {})
        assert {m.name for m in missing} == {"g", "s"}
        missing = engine._get_missing_inputs(wf, {"g": 1, "s": 2})
        assert missing == []

    def test_get_missing_inputs_hidden(self, engine):
        params = [
            _param(name="trigger"),
            _param(name="hidden", show_when={"trigger": "yes"}),
        ]
        wf = AdvancedWorkflowDefinition(**_workflow_def(input_schema=params))
        missing = engine._get_missing_inputs(wf, {"trigger": "no"})
        assert [m.name for m in missing] == []
        missing = engine._get_missing_inputs(wf, {})
        assert [m.name for m in missing] == ["trigger"]

    def test_should_show_parameter_variants(self, engine):
        assert engine._should_show_parameter(_param(), {}) is True
        assert engine._should_show_parameter(_param(show_when={"x": "a"}), {}) is False
        assert engine._should_show_parameter(_param(show_when={"x": ["a", "b"]}), {"x": "c"}) is False
        assert engine._should_show_parameter(_param(show_when={"x": ["a", "b"]}), {"x": "a"}) is True
        assert engine._should_show_parameter(
            _param(show_when={"x": {"equals": "a"}}), {"x": "b"}
        ) is False
        assert engine._should_show_parameter(
            _param(show_when={"x": {"not_equals": "a"}}), {"x": "a"}
        ) is False
        assert engine._should_show_parameter(
            _param(show_when={"x": {"contains": "sub"}}), {"x": "substr"}
        ) is True
        assert engine._should_show_parameter(
            _param(show_when={"x": {"bogus": "a"}}), {"x": "a"}
        ) is True

    def test_create_execution_plan(self, engine):
        steps = [
            _step(step_id="a"),
            _step(step_id="b", depends_on=["a"]),
            _step(step_id="c", depends_on=["a"]),
            _step(step_id="d", depends_on=["b", "c"]),
        ]
        wf = AdvancedWorkflowDefinition(**_workflow_def(steps=steps))
        plan = engine._create_execution_plan(wf)
        assert plan.planned_steps[0] == "a"
        assert set(plan.planned_steps[1:3]) == {"b", "c"}
        assert plan.planned_steps[3] == "d"
        assert set(plan.parallel_groups[0]) == {"b", "c"}
        assert plan.workflow_id == "wf1"
        assert plan.execution_id

    @pytest.mark.asyncio
    async def test_execute_workflow_paused_break(self, engine):
        steps = [_step(step_id="a"), _step(step_id="b")]
        wf = AdvancedWorkflowDefinition(**_workflow_def(steps=steps))
        engine.state_manager.save_state("wf1", {**wf.dict(), "state": WorkflowState.PAUSED})
        plan = engine._create_execution_plan(wf)
        await engine._execute_workflow(wf, plan)
        assert wf.step_results == {}

    @pytest.mark.asyncio
    async def test_execute_workflow_skips_completed(self, engine):
        steps = [_step(step_id="a"), _step(step_id="b")]
        wf = AdvancedWorkflowDefinition(**_workflow_def(steps=steps))
        wf.step_results["a"] = {"status": "success"}
        plan = engine._create_execution_plan(wf)
        await engine._execute_workflow(wf, plan)
        assert "b" in wf.step_results

    @pytest.mark.asyncio
    async def test_execute_workflow_step_error_fails(self, engine):
        steps = [_step(step_id="a")]
        wf = AdvancedWorkflowDefinition(**_workflow_def(steps=steps))
        plan = engine._create_execution_plan(wf)
        with patch.object(engine, "_execute_step", new=AsyncMock(side_effect=RuntimeError("boom"))):
            await engine._execute_workflow(wf, plan)
        assert wf.state == WorkflowState.FAILED
        assert engine.state_manager.load_state("wf1")["state"] == WorkflowState.FAILED

    @pytest.mark.asyncio
    async def test_execute_workflow_result_error_fails(self, engine):
        steps = [_step(step_id="a")]
        wf = AdvancedWorkflowDefinition(**_workflow_def(steps=steps))
        plan = engine._create_execution_plan(wf)
        with patch.object(
            engine, "_execute_step", new=AsyncMock(return_value={"status": "error"})
        ):
            await engine._execute_workflow(wf, plan)
        assert wf.state == WorkflowState.FAILED

    @pytest.mark.asyncio
    async def test_execute_step_types(self, engine):
        wf = AdvancedWorkflowDefinition(**_workflow_def(steps=[_step()]))
        wf.user_inputs = {"k": "v"}
        for step_type in ("api_call", "data_transform", "user_input", "condition", "custom"):
            step = _step(step_id=f"s_{step_type}", step_type=step_type, depends_on=["prev"])
            wf.step_results["prev"] = {"status": "success", "result": "r"}
            result = await engine._execute_step(wf, step)
            assert result["status"] == "success"
            assert result["execution_time"] >= 0

    @pytest.mark.asyncio
    async def test_execute_step_error(self, engine):
        wf = AdvancedWorkflowDefinition(**_workflow_def(steps=[_step()]))
        with patch.object(engine, "_execute_custom_step", side_effect=RuntimeError("x")):
            result = await engine._execute_step(wf, _step(step_id="x", step_type="custom"))
        assert result["status"] == "error"
        assert "x" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_api_call(self, engine):
        result = await engine._execute_api_call(_step(), {"a": 1})
        assert result["inputs"] == {"a": 1}

    @pytest.mark.asyncio
    async def test_execute_data_transform_and_user_input(self, engine):
        result = await engine._execute_data_transform(_step(), {"a": 1})
        assert result["message"] == "Data transformed"
        result = await engine._execute_user_input(_step(), {})
        assert result["message"] == "User input required"

    @pytest.mark.asyncio
    async def test_execute_condition_and_custom(self, engine):
        result = await engine._execute_condition(_step(), {})
        assert result["message"] == "Condition evaluated"
        step = _step(step_id="c", step_type="weird")
        result = await engine._execute_custom_step(step, {"i": 1})
        assert result["step_type"] == "weird"

    def test_pause_workflow(self, engine):
        assert engine.pause_workflow("missing") is False
        engine.state_manager.save_state("wf1", {"state": WorkflowState.RUNNING})
        assert engine.pause_workflow("wf1") is True
        assert engine.state_manager.load_state("wf1")["state"] == WorkflowState.PAUSED
        assert engine.pause_workflow("wf1") is False

    @pytest.mark.asyncio
    async def test_pause_cancels_running_task(self, engine):
        task = asyncio.create_task(asyncio.sleep(10))
        engine.running_workflows["wf1"] = task
        engine.state_manager.save_state("wf1", {"state": WorkflowState.RUNNING})
        assert engine.pause_workflow("wf1") is True
        assert "wf1" not in engine.running_workflows

    @pytest.mark.asyncio
    async def test_resume_workflow(self, engine):
        engine.state_manager.save_state("wf1", {"state": WorkflowState.DRAFT})
        with pytest.raises(ValueError):
            engine.resume_workflow("wf1")
        wf = AdvancedWorkflowDefinition(**_workflow_def())
        engine.state_manager.save_state("wf1", {**wf.dict(), "state": WorkflowState.PAUSED})
        result = engine.resume_workflow("wf1")
        assert result["status"] == "resumed"
        assert "wf1" in engine.running_workflows
        engine.running_workflows.pop("wf1").cancel()

    @pytest.mark.asyncio
    async def test_resume_workflow_with_inputs(self, engine):
        wf = AdvancedWorkflowDefinition(**_workflow_def())
        engine.state_manager.save_state(
            "wf1", {**wf.dict(), "state": WorkflowState.PAUSED}
        )
        result = engine.resume_workflow("wf1", {"extra": 1})
        assert result["status"] == "resumed"
        assert engine.state_manager.load_state("wf1")["user_inputs"] == {"extra": 1}
        engine.running_workflows.pop("wf1").cancel()

    def test_cancel_workflow(self, engine):
        assert engine.cancel_workflow("missing") is False
        engine.state_manager.save_state("wf1", {"state": WorkflowState.RUNNING})
        assert engine.cancel_workflow("wf1") is True
        assert engine.state_manager.load_state("wf1")["state"] == WorkflowState.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_cancels_task(self, engine):
        task = asyncio.create_task(asyncio.sleep(10))
        engine.running_workflows["wf1"] = task
        engine.state_manager.save_state("wf1", {"state": WorkflowState.RUNNING})
        assert engine.cancel_workflow("wf1") is True
        assert "wf1" not in engine.running_workflows

    def test_get_workflow_status_missing(self, engine):
        assert engine.get_workflow_status("nope") is None

    def test_get_workflow_status_present(self, engine):
        engine.state_manager.save_state(
            "wf1",
            {"state": WorkflowState.RUNNING, "current_step": "s1",
             "steps": [{"step_id": "s1"}], "step_results": {}, "user_inputs": {},
             "updated_at": "2026-01-01"},
        )
        status = engine.get_workflow_status("wf1")
        assert status["state"] == WorkflowState.RUNNING
        assert status["current_step"] == "s1"
        assert status["progress"] == 0.0

    def test_calculate_progress(self, engine):
        assert engine._calculate_progress({}) == 0.0
        state = {"steps": [1, 2, 3], "step_results": {"a": 1}}
        assert engine._calculate_progress(state) == pytest.approx(100.0 / 3)


# --------------------------------------------------------------------------- #
# AdvancedWorkflowSystem facade
# --------------------------------------------------------------------------- #

class TestAdvancedWorkflowSystem:
    def test_create_parallel(self):
        aws = AdvancedWorkflowSystem()
        result = aws.create_parallel({"name": "P", "parallel_branches": [{"steps": ["a", "b"]}]})
        assert result.execution_mode == "parallel"
        assert result.branches == 1
        state = aws.state_manager.load_state(result.workflow_id)
        assert len(state["steps"]) == 2
        assert state["steps"][0]["is_parallel"] is True

    def test_create_parallel_no_branches(self):
        aws = AdvancedWorkflowSystem()
        result = aws.create_parallel({"name": "P"})
        assert result.branches == 0

    def test_create_conditional(self):
        aws = AdvancedWorkflowSystem()
        result = aws.create_conditional({"name": "C", "conditions": [{"if": "x > 1"}, {"if": "y"}]})
        assert result.execution_mode == "conditional"
        assert result.conditions == 2
        state = aws.state_manager.load_state(result.workflow_id)
        assert state["steps"][0]["step_type"] == "condition"

    def test_create_conditional_empty(self):
        aws = AdvancedWorkflowSystem()
        result = aws.create_conditional({"name": "C"})
        assert result.conditions == 0

    def test_execute_with_retry(self):
        aws = AdvancedWorkflowSystem()
        result = aws.execute_with_retry("wf1", {"max_retries": 3, "backoff": 1.5})
        assert result.workflow_id == "wf1"
        assert result.retry_policy == {"max_retries": 3, "backoff": 1.5}
        assert result.attempts == 1
        assert result.status == "pending"

    def test_workflow_result_defaults(self):
        r = WorkflowResult("w", "parallel")
        assert r.branches == 0
        assert r.conditions == 0
        assert isinstance(r.created_at, datetime)

    def test_execution_result_defaults(self):
        r = ExecutionResult("e", "w", {})
        assert r.attempts == 1
        assert r.status == "pending"


class TestWorkflowEdgeCases:
    def test_validate_step_ids_single_instance(self):
        step = _step()
        step.step_id = 123
        with pytest.raises(Exception):
            AdvancedWorkflowDefinition(
                workflow_id="w", name="n", description="d", steps=step
            )

    def test_definition_get_missing_inputs_skips_hidden(self):
        wf = AdvancedWorkflowDefinition(
            **_workflow_def(input_schema=[_param(name="trigger"), _param(name="h", show_when={"trigger": "yes"})])
        )
        missing = wf.get_missing_inputs({"trigger": "no"})
        assert [m["name"] for m in missing] == []

    def test_definition_should_show_variants(self):
        wf = AdvancedWorkflowDefinition(**_workflow_def())
        p = _param(show_when={"x": "a"})
        assert wf._should_show_parameter(p, {"x": "b"}) is False
        assert wf._should_show_parameter(p, {}) is False
        assert wf._should_show_parameter(p, {"x": "a"}) is True
        plist = _param(show_when={"x": ["a", "b"]})
        assert wf._should_show_parameter(plist, {"x": "c"}) is False
        assert wf._should_show_parameter(_param(), {}) is True

    def test_definition_add_step_output_and_get_all(self):
        wf = AdvancedWorkflowDefinition(**_workflow_def())
        wf.add_step_output("s1", {"k": "v"})
        assert wf.get_all_outputs() == {"s1": {"k": "v"}}
        assert wf.step_results["s1"]["timestamp"]
        wf.add_step_output("s2", {"k": 2})
        assert set(wf.get_all_outputs()) == {"s1", "s2"}

    def test_load_state_file_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        sm.state_store["wf1"] = {"name": "x"}
        with patch.object(sm, "_load_from_file", side_effect=OSError("corrupt")):
            sm.state_store.pop("wf1")
            assert sm.load_state("wf1") is None

    def test_list_workflows_from_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        sm.save_state("wf1", {"name": "A", "state": "draft", "tags": [], "category": "g"})
        fresh = StateManager()
        rows = fresh.list_workflows()
        assert [r["workflow_id"] for r in rows] == ["wf1"]
        rows = fresh.list_workflows(status="running")
        assert rows == []

    def test_delete_state_file_remove_failure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sm = StateManager()
        sm.save_state("wf1", {"name": "A"})
        with patch("os.remove", side_effect=OSError("denied")):
            assert sm.delete_state("wf1") is False

    def test_validator_default_value_used(self):
        p = _param(required=False, default_value="d")
        ok, _ = ParameterValidator.validate_parameter(p, None)
        assert ok is True

    def test_validate_workflow_internal_exception(self, engine):
        steps = [_step(step_id="a")]
        wf = AdvancedWorkflowDefinition(**_workflow_def(steps=steps))
        with patch.object(
            engine, "_has_circular_dependencies", side_effect=RuntimeError("x")
        ):
            ok, err = engine._validate_workflow(wf)
        assert ok is False
        assert "Validation error" in err

    @pytest.mark.asyncio
    async def test_start_workflow_skips_unprovided_params(self, engine):
        params = [_param(name="a"), _param(name="b")]
        await engine.create_workflow(_workflow_def(input_schema=params))
        result = await engine.start_workflow("wf1", {"a": "x", "b": "y"})
        assert result["status"] == "started"

    def test_should_show_contains_miss(self, engine):
        assert engine._should_show_parameter(
            _param(show_when={"x": {"contains": "sub"}}), {"x": "zzz"}
        ) is False

    @pytest.mark.asyncio
    async def test_execute_workflow_failure_block(self, engine):
        steps = [_step(step_id="a")]
        wf = AdvancedWorkflowDefinition(**_workflow_def(steps=steps))
        plan = engine._create_execution_plan(wf)
        with patch.object(
            engine, "_execute_step", new=AsyncMock(return_value={"status": "error"})
        ):
            await engine._execute_workflow(wf, plan)
        state = engine.state_manager.load_state("wf1")
        assert state["state"] == WorkflowState.FAILED
        assert state["current_step"] is None

    @pytest.mark.asyncio
    async def test_start_workflow_skips_optional_unprovided(self, engine):
        params = [
            _param(name="req"),
            _param(name="opt", required=False),
        ]
        await engine.create_workflow(_workflow_def(input_schema=params))
        result = await engine.start_workflow("wf1", {"req": "x"})
        assert result["status"] == "started"
        await asyncio.wait_for(engine.running_workflows["wf1"], timeout=5)
