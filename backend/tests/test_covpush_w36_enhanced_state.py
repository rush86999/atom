"""Coverage wave 36 — core/enhanced_execution_state_manager.py (TDD, mocked db).

Drives the enhanced execution state machine: creation (with multi-output
config + step init), memory/DB state loading (incl. enhanced-data
rehydration + fallback), persistence upsert (insert/update paths),
step lifecycle (start/complete with aggregation + missing-input pause
callbacks/fail/skip), pause/resume (still-missing keeps paused),
missing-input checks with show-when conditions, output aggregation
(multiple/aggregated/stream), progress/step-detail queries, callbacks
and the singleton factory — no DB, zero spend.
"""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.enhanced_execution_state_manager import (
    EnhancedExecutionState,
    EnhancedExecutionStateManager,
    MultiOutputConfig,
    ParameterDefinition,
    StepState,
    WorkflowState,
    get_enhanced_state_manager,
)


def make_param(**kw):
    defaults = dict(name="p", type="string", label="Param", description="d",
                    required=True, default_value=None, validation_rules={},
                    options=[], depends_on=None, show_when=None,
                    multi_step=False)
    defaults.update(kw)
    return ParameterDefinition(**defaults)


def make_async_db(result_row=None):
    """Hybrid db mock: execute/commit async, everything else sync."""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    # AsyncMock's return_value defaults to AsyncMock — fetchone() would be a
    # coroutine; force a sync result mock.
    db.execute.return_value = MagicMock()
    db.execute.return_value.fetchone.return_value = result_row
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


def make_manager():
    with patch("core.enhanced_execution_state_manager.get_async_db_session"):
        mgr = EnhancedExecutionStateManager()
    mgr.create_execution = AsyncMock(return_value="ex-1")
    mgr.get_execution_state = AsyncMock(return_value=None)
    mgr.update_execution_status = AsyncMock()
    mgr.update_step_status = AsyncMock()
    return mgr


def make_state(ex_id="ex-1", wf_id="wf-1", **kw):
    state = EnhancedExecutionState(ex_id, wf_id)
    for k, v in kw.items():
        setattr(state, k, v)
    return state


class TestEnumsAndModels:
    def test_enums(self):
        assert WorkflowState.PAUSED.value == "paused"
        assert StepState.SKIPPED.value == "skipped"

    def test_parameter_definition(self):
        p = make_param(name="x", type="number", multi_step=True)
        assert p.name == "x"
        assert p.multi_step is True

    def test_multi_output_config(self):
        cfg = MultiOutputConfig(output_type="aggregated",
                                aggregation_method="merge",
                                step_outputs={"s1": ["a"]})
        assert cfg.output_type == "aggregated"
        assert cfg.step_outputs["s1"] == ["a"]

    def test_enhanced_state_init(self):
        state = make_state()
        assert state.state == WorkflowState.PENDING
        assert state.current_step_index == 0
        assert state.created_at is not None


class TestCreateAndLoad:
    async def test_create_execution(self):
        mgr = make_manager()
        ex_id = await mgr.create_enhanced_execution(
            "wf-1", {"x": 1},
            [{"step_id": "s1"}, {"step_id": "s2"}],
            [make_param(name="req").dict()],
            multi_output_config={"output_type": "multiple"})
        assert ex_id
        state = mgr.enhanced_states[ex_id]
        assert state.total_steps == 2
        assert state.collected_inputs == {"x": 1}
        assert state.step_states == {"s1": StepState.PENDING, "s2": StepState.PENDING}
        assert state.multi_output_config.output_type == "multiple"
        mgr.create_execution.assert_called_once()

    async def test_get_state_memory_hit(self):
        mgr = make_manager()
        state = make_state()
        mgr.enhanced_states["ex-1"] = state
        assert await mgr.get_enhanced_execution_state("ex-1") is state

    async def test_get_state_db_rehydrate(self):
        mgr = make_manager()
        mgr.get_execution_state = AsyncMock(
            return_value={"workflow_id": "wf-1", "input_data": {}, "status": "running"})
        db = make_async_db(result_row=(
            json.dumps({
                "state": "paused", "current_step_index": 1,
                "step_states": {"s1": "completed"}, "step_inputs": {"s1": {"a": 1}},
                "step_outputs": {}, "collected_inputs": {"x": 2},
                "missing_inputs": [], "execution_context": {},
                "aggregated_outputs": {}, "pause_reason": "waiting",
                "error_details": None,
                "multi_output_config": {"output_type": "stream"},
            }),))
        with patch("core.enhanced_execution_state_manager.get_async_db_session",
                   return_value=db):
            state = await mgr.get_enhanced_execution_state("ex-1")
        assert state.state == WorkflowState.PAUSED
        assert state.pause_reason == "waiting"
        assert state.step_states == {"s1": StepState.COMPLETED}
        assert state.multi_output_config.output_type == "stream"
        assert "ex-1" in mgr.enhanced_states

    async def test_get_state_not_found(self):
        mgr = make_manager()
        mgr.get_execution_state = AsyncMock(return_value=None)
        assert await mgr.get_enhanced_execution_state("ex-1") is None

    async def test_get_state_db_error_falls_back(self):
        mgr = make_manager()
        mgr.get_execution_state = AsyncMock(
            return_value={"workflow_id": "wf-1", "input_data": {"a": 1},
                          "status": "running"})
        with patch("core.enhanced_execution_state_manager.get_async_db_session",
                   side_effect=RuntimeError("db down")):
            state = await mgr.get_enhanced_execution_state("ex-1")
        assert state.state == WorkflowState.RUNNING
        assert state.collected_inputs == {"a": 1}

    async def test_save_insert_and_update(self):
        mgr = make_manager()
        db = make_async_db(result_row=None)
        with patch("core.enhanced_execution_state_manager.get_async_db_session",
                   return_value=db):
            await mgr._save_enhanced_state(make_state())
        insert_sql = str(db.execute.call_args.args[0])
        assert "INSERT INTO" in insert_sql

        db.execute.return_value.fetchone.return_value = ("ex-1",)
        with patch("core.enhanced_execution_state_manager.get_async_db_session",
                   return_value=db):
            await mgr._save_enhanced_state(make_state())
        update_sql = str(db.execute.call_args.args[0])
        assert "UPDATE" in update_sql

    async def test_ensure_table(self):
        mgr = make_manager()
        db = make_async_db()
        with patch("core.enhanced_execution_state_manager.get_async_db_session",
                   return_value=db):
            await mgr._ensure_enhanced_table()
        assert "CREATE TABLE IF NOT EXISTS" in str(db.execute.call_args.args[0])


class TestStepLifecycle:
    async def test_start_step(self):
        mgr = make_manager()
        state = make_state()
        state.step_states["s1"] = StepState.PENDING
        mgr.enhanced_states["ex-1"] = state
        with patch.object(mgr, "_save_enhanced_state", new=AsyncMock()):
            result = await mgr.start_step_execution("ex-1", "s1", {"a": 1})
        assert result is True
        assert state.step_states["s1"] == StepState.RUNNING
        assert state.state == WorkflowState.RUNNING
        mgr.update_step_status.assert_called_once_with("ex-1", "s1", "RUNNING")

    async def test_start_step_missing(self):
        mgr = make_manager()
        assert await mgr.start_step_execution("ghost", "s1", {}) is False

    async def test_complete_step_final(self):
        mgr = make_manager()
        state = make_state(total_steps=1)
        state.step_states["s1"] = StepState.RUNNING
        mgr.enhanced_states["ex-1"] = state
        with patch.object(mgr, "_save_enhanced_state", new=AsyncMock()):
            result = await mgr.complete_step("ex-1", "s1", {"out": 1})
        assert result is True
        assert state.state == WorkflowState.COMPLETED
        mgr.update_execution_status.assert_called_once_with("ex-1", "COMPLETED")

    async def test_complete_step_missing_input_pause_callback(self):
        mgr = make_manager()
        state = make_state(total_steps=2)
        state.step_states = {"s1": StepState.RUNNING, "s2": StepState.PENDING}
        state.required_inputs = [make_param(name="req")]
        mgr.enhanced_states["ex-1"] = state
        callback = AsyncMock()
        mgr.pause_callbacks["ex-1"] = callback
        with patch.object(mgr, "_save_enhanced_state", new=AsyncMock()):
            result = await mgr.complete_step("ex-1", "s1", {})
        assert result is True
        assert state.state == WorkflowState.WAITING_FOR_INPUT
        assert state.missing_inputs == ["req"]
        callback.assert_called_once()

    async def test_complete_step_callback_error_tolerated(self):
        mgr = make_manager()
        state = make_state(total_steps=2)
        state.step_states = {"s1": StepState.RUNNING, "s2": StepState.PENDING}
        state.required_inputs = [make_param(name="req")]
        mgr.enhanced_states["ex-1"] = state

        async def bad_callback(s):
            raise RuntimeError("boom")

        mgr.pause_callbacks["ex-1"] = bad_callback
        with patch.object(mgr, "_save_enhanced_state", new=AsyncMock()):
            result = await mgr.complete_step("ex-1", "s1", {})
        assert result is True

    async def test_complete_step_with_next_inputs_and_aggregation(self):
        mgr = make_manager()
        state = make_state(total_steps=2)
        state.step_states = {"s1": StepState.RUNNING, "s2": StepState.PENDING}
        state.required_inputs = [make_param(name="req")]
        state.multi_output_config = MultiOutputConfig(output_type="aggregated")
        mgr.enhanced_states["ex-1"] = state
        with patch.object(mgr, "_save_enhanced_state", new=AsyncMock()), \
             patch.object(mgr, "_aggregate_outputs", new=AsyncMock()) as agg:
            result = await mgr.complete_step("ex-1", "s1", {"o": 1},
                                             next_inputs={"req": "x"})
        assert result is True
        assert state.collected_inputs["req"] == "x"
        agg.assert_called_once()

    async def test_fail_step(self):
        mgr = make_manager()
        state = make_state()
        mgr.enhanced_states["ex-1"] = state
        with patch.object(mgr, "_save_enhanced_state", new=AsyncMock()):
            result = await mgr.fail_step("ex-1", "s1", "boom")
        assert result is True
        assert state.step_states["s1"] == StepState.FAILED
        assert state.error_details == "boom"

    async def test_skip_step(self):
        mgr = make_manager()
        state = make_state(total_steps=2)
        mgr.enhanced_states["ex-1"] = state
        with patch.object(mgr, "_save_enhanced_state", new=AsyncMock()):
            result = await mgr.skip_step("ex-1", "s1")
        assert result is True
        assert state.step_states["s1"] == StepState.SKIPPED
        assert state.current_step_index == 1


class TestPauseResume:
    async def test_pause(self):
        mgr = make_manager()
        state = make_state()
        mgr.enhanced_states["ex-1"] = state
        with patch.object(mgr, "_save_enhanced_state", new=AsyncMock()):
            result = await mgr.pause_execution("ex-1", "user pause",
                                               step_inputs={"a": 1})
        assert result is True
        assert state.state == WorkflowState.PAUSED
        assert state.pause_reason == "user pause"
        assert state.collected_inputs["a"] == 1

    async def test_pause_missing(self):
        mgr = make_manager()
        assert await mgr.pause_execution("ghost") is False

    async def test_resume_not_paused(self):
        mgr = make_manager()
        state = make_state(state=WorkflowState.RUNNING)
        mgr.enhanced_states["ex-1"] = state
        assert await mgr.resume_execution("ex-1") is False

    async def test_resume_still_missing(self):
        mgr = make_manager()
        state = make_state(state=WorkflowState.PAUSED)
        state.required_inputs = [make_param(name="still_missing")]
        mgr.enhanced_states["ex-1"] = state
        with patch.object(mgr, "_save_enhanced_state", new=AsyncMock()):
            result = await mgr.resume_execution("ex-1")
        assert result is False
        assert state.missing_inputs == ["still_missing"]

    async def test_resume_success(self):
        mgr = make_manager()
        state = make_state(state=WorkflowState.PAUSED, pause_reason="waiting")
        state.required_inputs = [make_param(name="req")]
        state.collected_inputs["req"] = "x"
        mgr.enhanced_states["ex-1"] = state
        with patch.object(mgr, "_save_enhanced_state", new=AsyncMock()):
            result = await mgr.resume_execution("ex-1", additional_inputs={"extra": 1})
        assert result is True
        assert state.state == WorkflowState.RUNNING
        assert state.pause_reason is None
        assert state.collected_inputs["extra"] == 1


class TestInputChecksAndAggregation:
    async def test_check_missing_inputs(self):
        mgr = make_manager()
        state = make_state()
        state.required_inputs = [
            make_param(name="a", required=True),
            make_param(name="b", required=True, show_when={"mode": "x"}),
            make_param(name="c", required=False),
        ]
        missing = await mgr._check_missing_inputs(state)
        assert "a" in missing
        assert "b" in missing  # trigger absent → param still shown → required
        assert "c" not in missing

    def test_should_show_parameter(self):
        mgr = make_manager()
        assert mgr._should_show_parameter(make_param(), {}) is True
        p = make_param(show_when={"mode": "fast"})
        assert mgr._should_show_parameter(p, {"mode": "fast"}) is True
        assert mgr._should_show_parameter(p, {"mode": "slow"}) is False
        assert mgr._should_show_parameter(p, {}) is True  # missing trigger → skip
        p2 = make_param(show_when={"mode": {"equals": "fast"}})
        assert mgr._should_show_parameter(p2, {"mode": "fast"}) is True
        assert mgr._should_show_parameter(p2, {"mode": "slow"}) is False
        p3 = make_param(show_when={"mode": {"not_equals": "fast"}})
        assert mgr._should_show_parameter(p3, {"mode": "slow"}) is True
        p4 = make_param(show_when={"mode": {"contains": "ast"}})
        assert mgr._should_show_parameter(p4, {"mode": "fast"}) is True
        assert mgr._should_show_parameter(p4, {"mode": "slow"}) is False

    async def test_aggregate_multiple(self):
        mgr = make_manager()
        state = make_state()
        state.multi_output_config = MultiOutputConfig(output_type="multiple")
        await mgr._aggregate_outputs(state, "s1", {"a": 1})
        await mgr._aggregate_outputs(state, "s1", {"a": 2})
        assert state.aggregated_outputs["s1"] == [{"a": 1}, {"a": 2}]

    async def test_aggregate_aggregated(self):
        mgr = make_manager()
        state = make_state()
        state.multi_output_config = MultiOutputConfig(output_type="aggregated")
        await mgr._aggregate_outputs(state, "s1", {"k": 1})
        await mgr._aggregate_outputs(state, "s2", {"k": 2})
        assert state.aggregated_outputs["k"] == [1, 2]

    async def test_aggregate_stream(self):
        mgr = make_manager()
        state = make_state()
        state.multi_output_config = MultiOutputConfig(output_type="stream")
        await mgr._aggregate_outputs(state, "s1", {"v": 9})
        assert state.aggregated_outputs["stream_s1"] == {"v": 9}

    async def test_aggregate_no_config(self):
        mgr = make_manager()
        state = make_state()
        await mgr._aggregate_outputs(state, "s1", {"a": 1})  # no crash
        assert state.aggregated_outputs == {}


class TestQueriesAndCallbacks:
    async def test_get_progress(self):
        mgr = make_manager()
        state = make_state(total_steps=4)
        state.step_states = {
            "s1": StepState.COMPLETED, "s2": StepState.SKIPPED,
            "s3": StepState.RUNNING, "s4": StepState.PENDING}
        state.current_step_index = 2
        state.missing_inputs = ["x"]
        state.pause_reason = None
        mgr.enhanced_states["ex-1"] = state
        progress = await mgr.get_progress("ex-1")
        assert progress["completed_steps"] == 2
        assert progress["progress_percentage"] == 50.0
        assert progress["step_states"]["s1"] == "completed"

    async def test_get_progress_missing(self):
        mgr = make_manager()
        assert "error" in await mgr.get_progress("ghost")

    async def test_get_step_details(self):
        mgr = make_manager()
        state = make_state(total_steps=2)
        state.step_states = {"s1": StepState.COMPLETED, "s2": StepState.PENDING}
        state.step_inputs = {"s1": {"a": 1}}
        state.step_outputs = {"s1": {"o": 2}}
        mgr.enhanced_states["ex-1"] = state
        details = await mgr.get_step_details("ex-1", "s1")
        assert details["state"] == "completed"
        assert details["inputs"] == {"a": 1}
        assert details["is_current"] is True  # index 0 → s1
        details2 = await mgr.get_step_details("ex-1", "ghost")
        assert details2["state"] == "unknown"

    async def test_get_step_details_missing(self):
        mgr = make_manager()
        assert "error" in await mgr.get_step_details("ghost", "s1")

    def test_register_callbacks(self):
        mgr = make_manager()
        cb = lambda s: None
        mgr.register_pause_callback("ex-1", cb)
        mgr.register_step_completion_callback("ex-1", cb)
        assert mgr.pause_callbacks["ex-1"] is cb
        assert mgr.step_completion_callbacks["ex-1"] is cb


class TestSingleton:
    def test_get_enhanced_state_manager(self):
        from core.enhanced_execution_state_manager import _enhanced_state_manager
        _enhanced_state_manager = None
        s1 = get_enhanced_state_manager()
        s2 = get_enhanced_state_manager()
        assert s1 is s2
        _enhanced_state_manager = None
