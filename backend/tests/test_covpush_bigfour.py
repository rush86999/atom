"""Coverage-push tests for core.workflow_engine, core.atom_meta_agent and
integrations.mcp_service (tests-only; read-only source modules)."""

import asyncio
import itertools
import json
import os
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.database import SessionLocal
from core.workflow_engine import (
    MissingInputError,
    SchemaValidationError,
    StepTimeoutError,
    WorkflowEngine,
)
from core.exceptions import AgentExecutionError, AuthenticationError, ExternalServiceError, ValidationError as AtomValidationError

os.environ.setdefault("TESTING", "1")


class FakeStateManager:
    def __init__(self):
        self.executions = {}
        self._seq = 0

    async def create_execution(self, workflow_id, input_data):
        self._seq += 1
        eid = f"exec-{self._seq}"
        self.executions[eid] = {
            "execution_id": eid,
            "workflow_id": workflow_id,
            "status": "PENDING",
            "steps": {},
            "outputs": {},
            "input_data": dict(input_data),
            "context": {},
            "error": None,
        }
        return eid

    async def get_execution_state(self, eid):
        return self.executions.get(eid)

    async def update_execution_status(self, eid, status, error=None):
        if eid in self.executions:
            self.executions[eid]["status"] = status
            self.executions[eid]["error"] = error

    async def update_step_status(self, eid, sid, status, output=None, error=None):
        if eid not in self.executions:
            raise ValueError(f"Execution {eid} not found")
        state = self.executions[eid]
        steps = state["steps"]
        if sid not in steps:
            steps[sid] = {}
        steps[sid]["status"] = status
        if output is not None:
            steps[sid]["output"] = output
            state["outputs"][sid] = output
        if error is not None:
            steps[sid]["error"] = error

    async def update_execution_inputs(self, eid, new_inputs):
        self.executions[eid]["input_data"].update(new_inputs)

    async def get_step_output(self, eid, sid):
        state = self.executions.get(eid)
        if not state:
            return None
        return state["outputs"].get(sid)


class FakeWSManager:
    def __init__(self):
        self.events = []

    async def notify_workflow_status(self, user_id, execution_id, status, data=None):
        self.events.append((execution_id, status, data))


class FakeAnalytics:
    def __init__(self):
        self.calls = []

    def track_workflow_execution(self, **kw):
        self.calls.append(("workflow", kw))


@pytest.fixture
def wf_env(monkeypatch):
    sm = FakeStateManager()
    ws = FakeWSManager()
    analytics = FakeAnalytics()
    notifier = MagicMock()
    notifier.notify_failure = AsyncMock()
    notifier.notify_completion = AsyncMock()

    monkeypatch.setattr("core.workflow_engine.get_state_manager", lambda: sm)
    monkeypatch.setattr("core.workflow_engine.get_connection_manager", lambda: ws)
    monkeypatch.setattr("core.analytics_engine.get_analytics_engine", lambda: analytics)
    monkeypatch.setattr("core.workflow_engine.notifier", notifier)
    monkeypatch.setattr("core.orchestration.event_bus.get_event_bus", lambda: MagicMock())

    engine = WorkflowEngine()
    engine._execute_step = engine._execute_step.__wrapped__.__get__(engine, WorkflowEngine)
    return {"sm": sm, "ws": ws, "analytics": analytics, "notifier": notifier, "engine": engine}


def _step(sid, service="email", action="send", params=None, **kw):
    s = {"id": sid, "service": service, "action": action, "parameters": params or {}}
    s.update(kw)
    return s


def _wf(steps, **kw):
    wf = {"id": "wf-1", "name": "Test WF", "steps": steps, "created_by": "user-1"}
    wf.update(kw)
    return wf


def _node_wf(nodes, connections=None, **kw):
    wf = {"id": "wf-g", "name": "Graph WF", "nodes": nodes, "connections": connections or []}
    wf.update(kw)
    return wf


# ============================================================================
# workflow_engine — orchestration events + graph execution edge paths
# ============================================================================


class TestOrchestrationEvents:
    def test_unknown_event_type_is_noop(self, wf_env):
        wf_env["engine"]._publish_orchestration_event("NOT_A_REAL_EVENT", "wf", "exec")

    def test_event_bus_exception_swallowed(self, wf_env, monkeypatch):
        def _boom():
            raise RuntimeError("bus down")

        monkeypatch.setattr("core.orchestration.event_bus.get_event_bus", _boom)
        wf_env["engine"]._publish_orchestration_event("WORKFLOW_STARTED", "wf", "exec")


class TestGraphExecution:
    @pytest.mark.asyncio
    async def test_graph_step_missing_input_pauses(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-g", {"ok": 1})
        wf = _node_wf([
            {"id": "n1", "title": "N1", "type": "action",
             "config": {"service": "email", "action": "send", "parameters": {"to": "${input.missing}"}}},
        ], [], created_by="u1")
        await wf_env["engine"]._execute_workflow_graph(
            eid, wf, await sm.get_execution_state(eid), ws, "u1", datetime.now(timezone.utc)
        )
        state = await sm.get_execution_state(eid)
        assert state["status"] == "PAUSED"
        assert "missing" in (state["error"] or "")

    @pytest.mark.asyncio
    async def test_graph_step_exception_fails_workflow(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-g", {"ok": 1})
        wf = _node_wf([
            {"id": "n1", "title": "N1", "type": "action",
             "config": {"service": "boom", "action": "x"}},
        ], [], created_by="u1")

        async def _boom(step, params):
            raise RuntimeError("kaboom")

        wf_env["engine"]._execute_step = _boom
        await wf_env["engine"]._execute_workflow_graph(
            eid, wf, await sm.get_execution_state(eid), ws, "u1", datetime.now(timezone.utc)
        )
        state = await sm.get_execution_state(eid)
        assert state["status"] == "FAILED"
        assert any(e[1] == "FAILED" for e in ws.events)

    @pytest.mark.asyncio
    async def test_graph_continue_on_error_activates_downstream(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-g", {"ok": 1})
        wf = _node_wf([
            {"id": "n1", "title": "N1", "type": "action",
             "config": {"service": "boom", "action": "x", "continue_on_error": True}},
            {"id": "n2", "title": "N2", "type": "action",
             "config": {"service": "email", "action": "send"}},
        ], [{"source": "n1", "target": "n2"}], created_by="u1")

        async def _boom(step, params):
            raise RuntimeError("kaboom")

        async def _ok(step, params):
            return {"status": "success", "result": {"id": "x"}}

        engine = wf_env["engine"]
        engine._execute_step = _boom
        engine._execute_step = _ok if False else engine._execute_step
        engine._execute_step = _boom

        async def _step_dispatch(step, params):
            if step["id"] == "n1":
                raise RuntimeError("kaboom")
            return {"status": "success", "result": {"id": "x"}}

        engine._execute_step = _step_dispatch
        await engine._execute_workflow_graph(
            eid, wf, await sm.get_execution_state(eid), ws, "u1", datetime.now(timezone.utc)
        )
        state = await sm.get_execution_state(eid)
        assert state["status"] == "PARTIAL"
        assert state["steps"]["n1"]["status"] == "FAILED"
        assert state["steps"]["n2"]["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_graph_cancelled_execution(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-g", {})
        wf = _node_wf([
            {"id": "n1", "title": "N1", "type": "action",
             "config": {"service": "email", "action": "send"}},
        ], [], created_by="u1")
        engine = wf_env["engine"]
        engine.cancellation_requests.add(eid)
        await engine._execute_workflow_graph(
            eid, wf, await sm.get_execution_state(eid), ws, "u1", datetime.now(timezone.utc)
        )
        state = await sm.get_execution_state(eid)
        assert state["status"] == "CANCELLED"
        assert eid not in engine.cancellation_requests


# ============================================================================
# workflow_engine — linear run edge paths
# ============================================================================


class TestLinearRun:
    @pytest.mark.asyncio
    async def test_resume_skips_completed_step(self, wf_env):
        sm = wf_env["sm"]
        eid = await sm.create_execution("wf-1", {})
        await sm.update_step_status(eid, "s1", "COMPLETED", output={"done": True})
        wf = _wf([_step("s1", service="email", action="send")])
        engine = wf_env["engine"]
        await engine._run_execution(eid, wf)
        state = await sm.get_execution_state(eid)
        assert state["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_cancellation_mid_run(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})
        engine = wf_env["engine"]
        engine.cancellation_requests.add(eid)
        wf = _wf([_step("s1", service="email", action="send")])
        await engine._run_execution(eid, wf)
        assert (await sm.get_execution_state(eid))["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_dependencies_not_met_skips_step(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})
        wf = _wf([_step("s1", service="email", action="send", depends_on=["ghost"])])
        await wf_env["engine"]._run_execution(eid, wf)
        state = await sm.get_execution_state(eid)
        assert state["steps"]["s1"]["status"] == "SKIPPED"
        assert state["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_condition_not_met_skips_step(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {"n": 1})
        wf = _wf([_step("s1", service="email", action="send",
                        condition="${input.n} > 5")])
        await wf_env["engine"]._run_execution(eid, wf)
        state = await sm.get_execution_state(eid)
        assert state["steps"]["s1"]["status"] == "SKIPPED"
        assert state["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_missing_input_pauses_linear(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})
        wf = _wf([_step("s1", service="email", action="send",
                        parameters={"to": "${input.missing}"})])
        await wf_env["engine"]._run_execution(eid, wf)
        state = await sm.get_execution_state(eid)
        assert state["status"] == "PAUSED"

    @pytest.mark.asyncio
    async def test_governance_denied_blocks_step(self, wf_env, monkeypatch):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})

        class DenyFactory:
            @staticmethod
            def get_governance_service(db, tenant_id="default"):
                svc = MagicMock()
                svc.can_perform_action_async = AsyncMock(
                    return_value={"allowed": False, "reason": "tier too low"}
                )
                return svc

        monkeypatch.setattr("core.workflow_engine.ServiceFactory", DenyFactory)

        class FakeAgent:
            id = "agent-1"

        def _first():
            return FakeAgent()

        monkeypatch.setattr("core.workflow_engine.get_db_session", lambda: _session_factory(_first))
        wf = _wf([_step("s1", service="email", action="send")], agent_id="agent-1")
        await wf_env["engine"]._run_execution(eid, wf)
        state = await sm.get_execution_state(eid)
        assert state["status"] == "FAILED"
        assert "Governance" in (state["error"] or "")

    @pytest.mark.asyncio
    async def test_governance_check_error_fails_open(self, wf_env, monkeypatch):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})

        class BoomFactory:
            @staticmethod
            def get_governance_service(db, tenant_id="default"):
                raise RuntimeError("db down")

        monkeypatch.setattr("core.workflow_engine.ServiceFactory", BoomFactory)
        monkeypatch.setattr("core.workflow_engine.get_db_session", lambda: _session_factory(None))
        wf = _wf([_step("s1", service="email", action="send")], agent_id="agent-1")
        await wf_env["engine"]._run_execution(eid, wf)
        state = await sm.get_execution_state(eid)
        assert state["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_step_exec_record_creation_failure_continues(self, wf_env, monkeypatch):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})

        def _boom_session():
            class _Ctx:
                def __enter__(self):
                    raise RuntimeError("db full")

                def __exit__(self, *a):
                    return False

            return _Ctx()

        monkeypatch.setattr("core.workflow_engine.get_db_session", _boom_session)
        wf = _wf([_step("s1", service="email", action="send")])
        await wf_env["engine"]._run_execution(eid, wf)
        state = await sm.get_execution_state(eid)
        assert state["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_step_error_status_envelope_fails_step(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})

        async def _err(step, params):
            return {"status": "error", "error": "nope"}

        wf_env["engine"]._execute_step = _err
        wf = _wf([_step("s1", service="email", action="send")])
        await wf_env["engine"]._run_execution(eid, wf)
        state = await sm.get_execution_state(eid)
        assert state["status"] == "FAILED"

    @pytest.mark.asyncio
    async def test_snapshot_failure_logged(self, wf_env, monkeypatch):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})
        monkeypatch.setattr("core.workflow_engine.get_db_session", lambda: _session_factory(None))
        wf = _wf([_step("s1", service="email", action="send")])
        await wf_env["engine"]._run_execution(eid, wf)
        state = await sm.get_execution_state(eid)
        assert state["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_continue_on_error_ends_partial(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})

        async def _err(step, params):
            raise RuntimeError("flaky")

        async def _dispatch(step, params):
            if step["id"] == "s1":
                raise RuntimeError("flaky")
            return {"status": "success", "result": {"id": "x"}}

        wf_env["engine"]._execute_step = _dispatch
        wf = _wf([_step("s1", service="email", action="send", continue_on_error=True),
                  _step("s2", service="email", action="send")])
        await wf_env["engine"]._run_execution(eid, wf)
        state = await sm.get_execution_state(eid)
        assert state["status"] == "PARTIAL"
        assert state["steps"]["s1"]["status"] == "FAILED"
        assert state["steps"]["s2"]["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_template_usage_tracked_on_failure(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})

        async def _err(step, params):
            raise RuntimeError("flaky")

        wf_env["engine"]._execute_step = _err
        tracker = MagicMock()
        with patch("core.workflow_engine.MarketplaceUsageTracker", tracker):
            wf = _wf([_step("s1", service="email", action="send")],
                     created_from_template="tpl-1")
            await wf_env["engine"]._run_execution(eid, wf)
        assert tracker.track_usage.called

    @pytest.mark.asyncio
    async def test_outer_exception_finalizes_failed(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})

        async def _err(step, params):
            raise RuntimeError("flaky")

        wf_env["engine"]._execute_step = _err
        monkeypatch = None
        wf = _wf([_step("s1", service="email", action="send")])
        original = wf_env["engine"].state_manager
        wf_env["engine"].state_manager = sm
        await wf_env["engine"]._run_execution(eid, wf)
        assert (await sm.get_execution_state(eid))["status"] == "FAILED"


def _session_factory(first_value):
    db = MagicMock()
    db.query.side_effect = [_query_first(value=first_value)]

    class _Ctx:
        def __enter__(self):
            return db

        def __exit__(self, *a):
            return False

    return _Ctx()


def _query_first(value=None):
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = value
    return q


# ============================================================================
# workflow_engine — pure helpers
# ============================================================================


class TestEvaluateCondition:
    def test_empty_condition_true(self, wf_env):
        assert wf_env["engine"]._evaluate_condition("", {}) is True
        assert wf_env["engine"]._evaluate_condition(None, {}) is True

    def test_missing_var_returns_false(self, wf_env):
        assert wf_env["engine"]._evaluate_condition("${a.b} == 1", {}) is False

    def test_non_bool_result_coerced(self, wf_env):
        state = {"input_data": {"n": 5}}
        assert wf_env["engine"]._evaluate_condition("${input.n}", state) is True

    def test_string_and_none_values(self, wf_env):
        state = {"input_data": {"s": "hello", "z": None}}
        assert wf_env["engine"]._evaluate_condition("${input.s} == 'hello'", state) is True
        assert wf_env["engine"]._evaluate_condition("${input.z}", state) is False

    def test_complex_object_repr(self, wf_env):
        state = {"outputs": {"st": {"o": {"k": [1, 2]}}}}
        assert wf_env["engine"]._evaluate_condition(
            "${st.o.k} == [1, 2]", state) is True

    def test_injection_blocked_returns_false(self, wf_env):
        assert wf_env["engine"]._evaluate_condition(
            "1 == 1 and __import__('os').system('echo hi') == 0", {}) is False

    def test_exception_returns_false(self, wf_env, monkeypatch):
        monkeypatch.setattr("core.safe_evaluator.safe_eval",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bad")))
        assert wf_env["engine"]._evaluate_condition("${a.b}", {}) is False


class TestResolveParameters:
    def test_dict_list_and_plain(self, wf_env):
        state = {"input_data": {"name": "Rishi"}, "outputs": {"st": {"id": 7}}}
        params = {
            "nested": {"k": "${input.name}"},
            "items": ["${input.name}", "literal"],
            "plain": "no refs here",
            "num": 42,
        }
        resolved = wf_env["engine"]._resolve_parameters(params, state)
        assert resolved["nested"]["k"] == "Rishi"
        assert resolved["items"] == ["Rishi", "literal"]
        assert resolved["plain"] == "no refs here"
        assert resolved["num"] == 42

    def test_pure_single_ref_preserves_type(self, wf_env):
        state = {"outputs": {"st": {"id": 7}}}
        assert wf_env["engine"]._resolve_parameter_value("${st.id}", state) == 7

    def test_interpolation_with_text(self, wf_env):
        state = {"input_data": {"name": "Rishi"}}
        assert wf_env["engine"]._resolve_parameter_value(
            "Hello ${input.name}!", state) == "Hello Rishi!"

    def test_interpolated_missing_raises(self, wf_env):
        with pytest.raises(MissingInputError):
            wf_env["engine"]._resolve_parameter_value(
                "Hello ${input.ghost}!", {})

    def test_none_value_preserved_when_path_exists(self, wf_env):
        state = {"outputs": {"st": {"id": None}}}
        assert wf_env["engine"]._resolve_parameter_value("${st.id}", state) is None


class TestPathHelpers:
    def test_path_exists_nested(self, wf_env):
        state = {"outputs": {"st": {"a": {"b": 1}}}}
        assert wf_env["engine"]._path_exists("st.a.b", state) is True
        assert wf_env["engine"]._path_exists("st.a.c", state) is False
        assert wf_env["engine"]._path_exists("ghost.a", state) is False

    def test_get_value_from_path_non_dict(self, wf_env):
        state = {"outputs": {"st": 5}}
        assert wf_env["engine"]._get_value_from_path("st.a.b", state) is None
        assert wf_env["engine"]._get_value_from_path("input", state) == {}


class TestSchemaValidation:
    def test_input_schema_violation(self, wf_env):
        step = {"id": "s1", "input_schema": {
            "type": "object",
            "required": ["to"],
            "properties": {"to": {"type": "string"}},
        }}
        with pytest.raises(SchemaValidationError) as exc:
            wf_env["engine"]._validate_input_schema(step, {"from": "x"})
        assert exc.value.schema_type == "input"

    def test_output_schema_violation(self, wf_env):
        step = {"id": "s1", "output_schema": {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "string"}},
        }}
        with pytest.raises(SchemaValidationError) as exc:
            wf_env["engine"]._validate_output_schema(step, {"id": 1})
        assert exc.value.schema_type == "output"

    def test_no_schema_noop(self, wf_env):
        wf_env["engine"]._validate_input_schema({"id": "s1"}, {})
        wf_env["engine"]._validate_output_schema({"id": "s1"}, {})


# ============================================================================
# workflow_engine — _execute_step dispatch
# ============================================================================


class TestExecuteStep:
    @pytest.mark.asyncio
    async def test_fallback_error_dict_raises(self, wf_env):
        engine = wf_env["engine"]
        engine._execute_slack_action = AsyncMock(
            side_effect=AuthenticationError("no token"))
        engine._execute_discord_action = AsyncMock(
            return_value={"status": "error", "error": "nope"})
        step = {"id": "s1", "service": "slack", "action": "x",
                "fallback_service": "discord"}
        with pytest.raises(ValueError, match="fallback"):
            await engine._execute_step(step, {})

    @pytest.mark.asyncio
    async def test_unknown_service_raises(self, wf_env):
        engine = wf_env["engine"]
        engine._execute_generic_action = AsyncMock(
            side_effect=ValueError("not in catalog"))
        with pytest.raises(ValueError, match="Unknown service"):
            await engine._execute_step({"id": "s1", "service": "nope", "action": "x"}, {})

    @pytest.mark.asyncio
    async def test_unknown_service_with_working_fallback(self, wf_env):
        engine = wf_env["engine"]
        engine._execute_generic_action = AsyncMock(
            side_effect=ValueError("not in catalog"))
        engine._execute_email_action = AsyncMock(
            return_value={"status": "success", "result": {"ok": True}})
        result = await engine._execute_step({
            "id": "s1", "service": "nope", "action": "x",
            "fallback_service": "email",
        }, {})
        assert result["execution_method"] == "fallback_service"
        assert result["fallback_used"] is True

    @pytest.mark.asyncio
    async def test_timeout_raises_step_timeout(self, wf_env):
        engine = wf_env["engine"]

        async def _slow(*a, **k):
            await asyncio.sleep(5)

        engine._execute_email_action = _slow
        with pytest.raises(StepTimeoutError):
            await engine._execute_step(
                {"id": "s1", "service": "email", "action": "send", "timeout": 0.01}, {})

    @pytest.mark.asyncio
    async def test_timeout_fallback_raises_step_timeout(self, wf_env):
        engine = wf_env["engine"]
        engine._execute_slack_action = AsyncMock(side_effect=RuntimeError("down"))

        async def _slow(*a, **k):
            await asyncio.sleep(5)

        engine._execute_email_action = _slow
        with pytest.raises(ValueError):
            await engine._execute_step({
                "id": "s1", "service": "slack", "action": "x",
                "fallback_service": "email", "timeout": 0.01,
            }, {})

    @pytest.mark.asyncio
    async def test_executor_non_success_status_raises(self, wf_env):
        engine = wf_env["engine"]
        engine._execute_email_action = AsyncMock(
            return_value={"status": "timeout", "error": "sub-wf timed out"})
        with pytest.raises(Exception, match="timed out"):
            await engine._execute_step({"id": "s1", "service": "email", "action": "x"}, {})

    @pytest.mark.asyncio
    async def test_success_wraps_result(self, wf_env):
        engine = wf_env["engine"]
        engine._execute_email_action = AsyncMock(
            return_value={"status": "success", "result": {"ok": True}})
        result = await engine._execute_step(
            {"id": "s1", "service": "email", "action": "send"}, {})
        assert result["status"] == "success"
        assert result["execution_method"] == "service_registry"


# ============================================================================
# workflow_engine — service executors
# ============================================================================


class TestSlackExecutor:
    @pytest.mark.asyncio
    async def test_no_token_raises(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = None
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        with pytest.raises(AuthenticationError):
            await wf_env["engine"]._execute_slack_action("chat_postMessage", {"channel": "c", "text": "t"}, connection_id="conn-1")

    @pytest.mark.asyncio
    async def test_token_fallback_by_service_name(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.side_effect = [None, {"access_token": "tok"}]
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        svc = MagicMock()
        svc.list_channels = AsyncMock(return_value=[{"id": "c1"}])
        monkeypatch.setattr("integrations.slack_service_unified.slack_unified_service", svc)
        result = await wf_env["engine"]._execute_slack_action(
            "chat_getChannels", {"types": "public"}, connection_id="conn-1")
        assert result["status"] == "success"
        assert ts.get_token.call_count == 2

    @pytest.mark.asyncio
    async def test_missing_channel_info_params(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        with pytest.raises(ValueError):
            await wf_env["engine"]._execute_slack_action("get_channel_info", {}, connection_id="conn-1")
        with pytest.raises(ValueError):
            await wf_env["engine"]._execute_slack_action("get_channel_history", {}, connection_id="conn-1")

    @pytest.mark.asyncio
    async def test_update_delete_search_files(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        svc = MagicMock()
        svc.update_message = AsyncMock(return_value={"ok": True})
        svc.delete_message = AsyncMock(return_value={"ok": True})
        svc.search_messages = AsyncMock(return_value=[{"ts": "1"}])
        svc.list_files = AsyncMock(return_value=[{"id": "f1"}])
        monkeypatch.setattr("integrations.slack_service_unified.slack_unified_service", svc)
        engine = wf_env["engine"]
        assert (await engine._execute_slack_action("update_message", {"channel_id": "c", "message_ts": "1", "text": "t"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_slack_action("delete_message", {"channel_id": "c", "message_ts": "1"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_slack_action("search_messages", {"query": "q"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_slack_action("files_list", {}, connection_id="conn-1"))["status"] == "success"
        r = await engine._execute_slack_action("files_get_upload_url_external", {}, connection_id="conn-1")
        assert r["result"]["ok"] is False
        r = await engine._execute_slack_action("reactions_add", {}, connection_id="conn-1")
        assert r["result"]["ok"] is False
        with pytest.raises(ValueError, match="Unsupported Slack action"):
            await engine._execute_slack_action("bogus_action", {}, connection_id="conn-1")

    @pytest.mark.asyncio
    async def test_send_message_and_users(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        svc = MagicMock()
        svc.post_message = AsyncMock(return_value={"ok": True})
        svc.get_team_info = AsyncMock(return_value={"team": "x"})
        monkeypatch.setattr("integrations.slack_service_unified.slack_unified_service", svc)
        engine = wf_env["engine"]
        r = await engine._execute_slack_action("chat_postMessage", {"channel": "c", "text": "t"}, connection_id="conn-1")
        assert r["status"] == "success"
        r = await engine._execute_slack_action("chat_getUsers", {}, connection_id="conn-1")
        assert r["status"] == "success"


class TestAsanaExecutor:
    @pytest.mark.asyncio
    async def test_env_token_and_auth_error(self, wf_env, monkeypatch):
        monkeypatch.setenv("ASANA_ACCESS_TOKEN", "")
        monkeypatch.setattr("core.workflow_engine.token_storage", MagicMock())
        with pytest.raises(AuthenticationError):
            await wf_env["engine"]._execute_asana_action("create_task", {})
        monkeypatch.setenv("ASANA_ACCESS_TOKEN", "tok")
        svc = MagicMock()
        svc.create_task = AsyncMock(return_value={"gid": "g1"})
        monkeypatch.setattr("integrations.asana_service.asana_service", svc)
        r = await wf_env["engine"]._execute_asana_action(
            "create_task", {"name": "t", "workspace": "w", "projects": ["p"], "notes": "n", "due_on": "2026-01-01", "assignee": "a"})
        assert r["status"] == "success"

    @pytest.mark.asyncio
    async def test_actions_and_errors(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        svc = MagicMock()
        svc.get_tasks = AsyncMock(return_value=[])
        svc.get_projects = AsyncMock(return_value=[])
        svc.update_task = AsyncMock(return_value={})
        svc.add_task_comment = AsyncMock(return_value={})
        svc.get_workspaces = AsyncMock(return_value=[])
        svc.get_users = AsyncMock(return_value=[])
        svc.get_teams = AsyncMock(return_value=[])
        svc.search_tasks = AsyncMock(return_value=[])
        monkeypatch.setattr("integrations.asana_service.asana_service", svc)
        engine = wf_env["engine"]
        assert (await engine._execute_asana_action("get_tasks", {"project": "p"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_asana_action("get_projects", {}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_asana_action("update_task", {"task_gid": "g"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_asana_action("add_comment", {"task_gid": "g", "text": "x"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_asana_action("get_workspaces", {}, connection_id="conn-1"))["status"] == "success"
        with pytest.raises(ValueError):
            await engine._execute_asana_action("get_users", {}, connection_id="conn-1")
        with pytest.raises(ValueError):
            await engine._execute_asana_action("get_teams", {}, connection_id="conn-1")
        with pytest.raises(ValueError):
            await engine._execute_asana_action("search_tasks", {"workspace": "w"}, connection_id="conn-1")
        r = await engine._execute_asana_action("create_project", {}, connection_id="conn-1")
        assert r["result"]["ok"] is False
        with pytest.raises(ValueError, match="Unsupported Asana action"):
            await engine._execute_asana_action("bogus", {}, connection_id="conn-1")
        with pytest.raises(ValueError):
            await engine._execute_asana_action("update_task", {}, connection_id="conn-1")


class TestDiscordHubspotSalesforce:
    @pytest.mark.asyncio
    async def test_discord(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = None
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        svc = MagicMock()
        svc.bot_token = ""
        monkeypatch.setattr("integrations.discord_service.discord_service", svc)
        with pytest.raises(AuthenticationError):
            await wf_env["engine"]._execute_discord_action("send_message", {}, connection_id="conn-1")
        ts.get_token.return_value = {"access_token": "tok"}
        svc.send_message = AsyncMock(return_value={"ok": True})
        assert (await wf_env["engine"]._execute_discord_action("send_message", {"channel_id": "c", "content": "hi"}, connection_id="conn-1"))["status"] == "success"
        assert (await wf_env["engine"]._execute_discord_action("custom_action", {}, connection_id="conn-1"))["status"] == "success"
        svc.send_message = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            await wf_env["engine"]._execute_discord_action("send_message", {"channel_id": "c", "content": "hi"}, connection_id="conn-1")

    @pytest.mark.asyncio
    async def test_hubspot(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = None
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        svc_cls = MagicMock()
        inst = MagicMock()
        inst.access_token = ""
        svc_cls.return_value = inst
        monkeypatch.setattr("integrations.hubspot_service.HubSpotService", svc_cls)
        with pytest.raises(AuthenticationError):
            await wf_env["engine"]._execute_hubspot_action("create_contact", {}, connection_id="conn-1")
        ts.get_token.return_value = {"access_token": "tok"}
        inst.create_contact = AsyncMock(return_value={"id": "c1"})
        inst.create_deal = AsyncMock(return_value={"id": "d1"})
        engine = wf_env["engine"]
        assert (await engine._execute_hubspot_action("create_contact", {"email": "e"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_hubspot_action("create_deal", {"dealname": "n"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_hubspot_action("custom", {}, connection_id="conn-1"))["status"] == "success"
        inst.create_contact = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            await engine._execute_hubspot_action("create_contact", {}, connection_id="conn-1")

    @pytest.mark.asyncio
    async def test_salesforce(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = None
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        svc_cls = MagicMock()
        inst = MagicMock()
        svc_cls.return_value = inst
        monkeypatch.setattr("integrations.salesforce_service.SalesforceService", svc_cls)
        with pytest.raises(AuthenticationError):
            await wf_env["engine"]._execute_salesforce_action("create_lead", {}, connection_id="conn-1")
        ts.get_token.return_value = {"access_token": "tok", "instance_url": "https://x"}
        client = MagicMock()
        inst.create_client = MagicMock(return_value=client)
        inst.create_lead = AsyncMock(return_value={"id": "l"})
        inst.create_contact = AsyncMock(return_value={"id": "c"})
        inst.create_opportunity = AsyncMock(return_value={"id": "o"})
        engine = wf_env["engine"]
        assert (await engine._execute_salesforce_action("create_lead", {"lastname": "x", "company": "y"}, connection_id="conn-1"))["authenticated"] is True
        assert (await engine._execute_salesforce_action("create_contact", {"lastname": "x"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_salesforce_action("create_opportunity", {"name": "n"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_salesforce_action("custom", {}, connection_id="conn-1"))["status"] == "success"


class TestGithubZoomNotion:
    @pytest.mark.asyncio
    async def test_github(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        svc_cls = MagicMock()
        inst = MagicMock()
        svc_cls.return_value = inst
        monkeypatch.setattr("integrations.github_service.GitHubService", svc_cls)
        engine = wf_env["engine"]
        assert (await engine._execute_github_action("create_issue", {"owner": "o", "repo": "r", "title": "t"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_github_action("custom", {}, connection_id="conn-1"))["status"] == "success"
        inst.create_issue.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await engine._execute_github_action("create_issue", {}, connection_id="conn-1")

    @pytest.mark.asyncio
    async def test_zoom(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        svc_cls = MagicMock()
        inst = MagicMock()
        inst.create_meeting = AsyncMock(return_value={"id": "m"})
        svc_cls.return_value = inst
        monkeypatch.setattr("integrations.zoom_service.ZoomService", svc_cls)
        engine = wf_env["engine"]
        assert (await engine._execute_zoom_action("create_meeting", {"topic": "t"}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_zoom_action("custom", {}, connection_id="conn-1"))["status"] == "success"
        inst.create_meeting = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            await engine._execute_zoom_action("create_meeting", {}, connection_id="conn-1")

    @pytest.mark.asyncio
    async def test_notion(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        svc_cls = MagicMock()
        inst = MagicMock()
        svc_cls.return_value = inst
        monkeypatch.setattr("integrations.notion_service.NotionService", svc_cls)
        engine = wf_env["engine"]
        assert (await engine._execute_notion_action("create_page", {"parent": {"database_id": "d"}, "properties": {}}, connection_id="conn-1"))["status"] == "success"
        assert (await engine._execute_notion_action("custom", {}, connection_id="conn-1"))["status"] == "success"
        inst.create_page.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await engine._execute_notion_action("create_page", {}, connection_id="conn-1")


class TestGetToken:
    def test_fallback_by_service_name(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.side_effect = [None, {"access_token": "tok"}]
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        assert wf_env["engine"]._get_token("conn-1", "github") == "tok"

    def test_no_token_returns_none(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = None
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        assert wf_env["engine"]._get_token("conn-1", "github") is None
        assert wf_env["engine"]._get_token(None, "github") is None


class TestGmailExecutor:
    @pytest.mark.asyncio
    async def test_google_fallback_and_actions(self, wf_env, monkeypatch):
        calls = {"n": 0}

        def _get_token(cid):
            calls["n"] += 1
            if calls["n"] == 1:
                return None
            return {"access_token": "tok"}

        ts = MagicMock()
        ts.get_token.side_effect = _get_token
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        inst = MagicMock()
        inst.send_message = MagicMock(return_value={"id": "m"})
        inst.draft_message = MagicMock(return_value={"id": "d"})
        svc_cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.gmail_service.GmailService", svc_cls)
        engine = wf_env["engine"]
        r = await engine._execute_gmail_action("send_email", {"to": "a@b.c", "subject": "s", "body": "b"}, connection_id="c1")
        assert r["status"] == "success"
        assert ts.get_token.call_count == 2
        r = await engine._execute_gmail_action("create_draft", {"to": "a@b.c"}, connection_id="c1")
        assert r["status"] == "success"
        r = await engine._execute_gmail_action("custom", {}, connection_id="c1")
        assert r["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_email_errors(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = None
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        inst = MagicMock()
        svc_cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.gmail_service.GmailService", svc_cls)
        engine = wf_env["engine"]
        with pytest.raises(AuthenticationError):
            await engine._execute_gmail_action("send_email", {"to": "a@b.c"}, connection_id="c1")
        with pytest.raises(AuthenticationError):
            await engine._execute_gmail_action("create_draft", {}, connection_id="c1")

    @pytest.mark.asyncio
    async def test_send_email_failure_raises_external_error(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        inst = MagicMock()
        inst.send_message = MagicMock(return_value=None)
        svc_cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.gmail_service.GmailService", svc_cls)
        with pytest.raises(ExternalServiceError):
            await wf_env["engine"]._execute_gmail_action("send_email", {"to": "a@b.c"}, connection_id="c1")


class TestEmailCalendarDatabaseAiWebhook:
    @pytest.mark.asyncio
    async def test_simple_executors(self, wf_env):
        engine = wf_env["engine"]
        assert (await engine._execute_email_action("send", {}))["status"] == "success"
        assert (await engine._execute_calendar_action("list", {}))["status"] == "success"
        assert (await engine._execute_database_action("query", {}))["status"] == "success"
        assert (await engine._execute_ai_action("analyze", {}))["status"] == "success"
        assert (await engine._execute_webhook_action("fire", {}))["status"] == "success"


class TestMCPAndMainAgent:
    @pytest.mark.asyncio
    async def test_mcp_action_success_and_error(self, wf_env, monkeypatch):
        svc = MagicMock()
        svc.execute_tool = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr("integrations.mcp_service.mcp_service", svc)
        engine = wf_env["engine"]
        r = await engine._execute_mcp_action("run", {"server_id": "srv", "tool_name": "t", "arguments": {"a": 1}})
        assert r["status"] == "success"
        r = await engine._execute_mcp_action("run", {})
        assert r["status"] == "error"

    @pytest.mark.asyncio
    async def test_main_agent_with_mcp_servers(self, wf_env, monkeypatch):
        svc = MagicMock()
        svc.get_active_connections = AsyncMock(return_value=[
            {"server_id": "s1", "connected_at": "now"},
        ])
        svc.get_server_tools = AsyncMock(return_value=[{"name": "tool_a", "description": "d"}])
        monkeypatch.setattr("integrations.mcp_service.mcp_service", svc)
        engine = wf_env["engine"]
        engine._execute_agent_with_mcp = AsyncMock(return_value={"done": True})
        r = await engine._execute_main_agent_action(
            "act", {"agent_action": "aa", "mcp_servers": ["s1"], "input_data": {}})
        assert r["status"] == "success"
        assert r["mcp_servers_used"] == ["s1"]

    @pytest.mark.asyncio
    async def test_main_agent_exception_returns_error(self, wf_env):
        engine = wf_env["engine"]
        engine._execute_agent_with_mcp = AsyncMock(side_effect=RuntimeError("boom"))
        r = await engine._execute_main_agent_action("act", {})
        assert r["status"] == "error"


class TestExecuteAgentWithMCP:
    @pytest.mark.asyncio
    async def test_agent_not_found(self, wf_env, monkeypatch):
        def _session():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = None

            class _Ctx:
                def __enter__(self):
                    return db

                def __exit__(self, *a):
                    return False

            return _Ctx()

        monkeypatch.setattr("core.database.get_db_session", _session)
        result = await wf_env["engine"]._execute_agent_with_mcp(
            {"action": "x", "agent_id": "ghost"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_llm_success_path(self, wf_env, monkeypatch):
        fake_agent = MagicMock()
        fake_agent.llm_provider = "openai"
        fake_agent.llm_model = "gpt-4o"

        def _session():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = fake_agent

            class _Ctx:
                def __enter__(self):
                    return db

                def __exit__(self, *a):
                    return False

            return _Ctx()

        monkeypatch.setattr("core.database.get_db_session", _session)
        handler = MagicMock()
        handler.chat_completion = AsyncMock(
            return_value={"content": "done", "tool_calls": []})
        llm_svc = MagicMock()
        llm_svc.handler = handler
        monkeypatch.setattr("core.llm_service.get_llm_service", lambda db=None: llm_svc)
        result = await wf_env["engine"]._execute_agent_with_mcp({
            "action": "x", "agent_id": "a1", "input_data": {},
            "available_tools": [{"name": "t", "description": "d", "input_schema": {}}],
        })
        assert result["success"] is True
        assert result["execution_method"] == "main_agent_with_mcp"

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back(self, wf_env, monkeypatch):
        fake_agent = MagicMock()
        fake_agent.llm_provider = "openai"
        fake_agent.llm_model = "gpt-4o"

        def _session():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = fake_agent

            class _Ctx:
                def __enter__(self):
                    return db

                def __exit__(self, *a):
                    return False

            return _Ctx()

        monkeypatch.setattr("core.database.get_db_session", _session)
        handler = MagicMock()
        handler.chat_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        llm_svc = MagicMock()
        llm_svc.handler = handler
        monkeypatch.setattr("core.llm_service.get_llm_service", lambda db=None: llm_svc)
        result = await wf_env["engine"]._execute_agent_with_mcp(
            {"action": "x", "agent_id": "a1"})
        assert result["success"] is True
        assert result["execution_method"] == "fallback"

    @pytest.mark.asyncio
    async def test_outer_exception_wraps(self, wf_env, monkeypatch):
        def _session():
            raise RuntimeError("db gone")

        monkeypatch.setattr("core.database.get_db_session", _session)
        with pytest.raises(AgentExecutionError):
            await wf_env["engine"]._execute_agent_with_mcp({"agent_id": "a1"})


class TestEmailAutomation:
    @pytest.mark.asyncio
    async def test_detect_followups(self, wf_env, monkeypatch):
        engine = MagicMock()
        engine.days_threshold = 3
        engine.detect_missing_replies = AsyncMock(return_value=[])
        monkeypatch.setattr("core.email_followup_engine.followup_engine", engine)
        r = await wf_env["engine"]._execute_email_automation_action("detect_followups", {"days_threshold": 2})
        assert r["status"] == "success"

    @pytest.mark.asyncio
    async def test_draft_nudge_and_unknown(self, wf_env):
        engine = wf_env["engine"]
        r = await engine._execute_email_automation_action("draft_nudge", {"subject": "S"})
        assert r["status"] == "success"
        r = await engine._execute_email_automation_action("bogus", {})
        assert r["status"] == "error"


class TestWorkflowAction:
    @pytest.mark.asyncio
    async def test_missing_workflow_id(self, wf_env):
        r = await wf_env["engine"]._execute_workflow_action("run", {})
        assert r["status"] == "error"

    @pytest.mark.asyncio
    async def test_workflow_not_found(self, wf_env):
        wf_env["engine"]._load_workflow_by_id = lambda wid: None
        r = await wf_env["engine"]._execute_workflow_action("run", {"workflow_id": "wf-x"})
        assert r["status"] == "error"

    @pytest.mark.asyncio
    async def test_completed_subworkflow(self, wf_env):
        engine = wf_env["engine"]
        engine._load_workflow_by_id = lambda wid: {"id": "sub", "steps": []}
        engine.start_workflow = AsyncMock(return_value="sub-exec")
        sm = wf_env["sm"]
        await sm.create_execution("sub", {})
        sm.executions["sub-exec"] = sm.executions.pop(list(sm.executions.keys())[0])
        sm.executions["sub-exec"]["status"] = "COMPLETED"
        sm.executions["sub-exec"]["outputs"] = {"x": 1}
        r = await engine._execute_workflow_action("run", {"workflow_id": "wf-x"})
        assert r["status"] == "success"
        assert r["result"] == {"x": 1}

    @pytest.mark.asyncio
    async def test_failed_and_cancelled_and_paused(self, wf_env):
        engine = wf_env["engine"]
        engine._load_workflow_by_id = lambda wid: {"id": "sub", "steps": []}
        engine.start_workflow = AsyncMock(return_value="sub-exec")
        sm = wf_env["sm"]
        await sm.create_execution("sub", {})
        sm.executions["sub-exec"] = sm.executions.pop(list(sm.executions.keys())[0])
        for status in ["FAILED", "CANCELLED", "PAUSED", "RUNNING"]:
            sm.executions["sub-exec"]["status"] = status
            r = await engine._execute_workflow_action("run", {"workflow_id": "wf-x", "timeout": 0.001})
            assert r["status"] in ["error", "cancelled", "paused", "timeout"]
            assert r["status"] != "success"

    @pytest.mark.asyncio
    async def test_state_not_found_and_unknown_status(self, wf_env):
        engine = wf_env["engine"]
        engine._load_workflow_by_id = lambda wid: {"id": "sub", "steps": []}
        engine.start_workflow = AsyncMock(return_value="sub-exec")
        sm = wf_env["sm"]
        await sm.create_execution("sub", {})
        sm.executions.pop(list(sm.executions.keys())[0])
        r = await engine._execute_workflow_action("run", {"workflow_id": "wf-x", "timeout": 0.001})
        assert r["status"] == "error"
        await sm.create_execution("sub", {})
        sm.executions["sub-exec"] = sm.executions.pop(list(sm.executions.keys())[0])
        sm.executions["sub-exec"]["status"] = "WEIRD"
        r = await engine._execute_workflow_action("run", {"workflow_id": "wf-x", "timeout": 0.001})
        assert r["status"] == "timeout"


class TestLoadWorkflowById:
    def test_file_missing(self, monkeypatch):
        monkeypatch.setattr("core.workflow_engine.os.path.exists", lambda p: False)
        assert WorkflowEngine()._load_workflow_by_id("x") is None

    def test_not_found_in_file(self, monkeypatch):
        monkeypatch.setattr("core.workflow_engine.os.path.exists", lambda p: True)
        with patch("builtins.open") as m:
            m.return_value.__enter__.return_value.read.return_value = json.dumps([{"id": "a"}])
            assert WorkflowEngine()._load_workflow_by_id("b") is None

    def test_parse_error_returns_none(self, monkeypatch):
        monkeypatch.setattr("core.workflow_engine.os.path.exists", lambda p: True)
        with patch("builtins.open") as m:
            m.return_value.__enter__.return_value.read.return_value = "not json"
            assert WorkflowEngine()._load_workflow_by_id("b") is None

    def test_found(self, monkeypatch):
        monkeypatch.setattr("core.workflow_engine.os.path.exists", lambda p: True)
        with patch("builtins.open") as m:
            m.return_value.__enter__.return_value.read.return_value = json.dumps([{"id": "a"}])
            assert WorkflowEngine()._load_workflow_by_id("a") == {"id": "a"}


class TestOutlookJiraTrelloStripe:
    @pytest.mark.asyncio
    async def test_outlook(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        inst = MagicMock(spec=["send_email", "create_calendar_event", "get_user_emails", "custom_method"])
        inst.send_email = AsyncMock(return_value={"id": "m"})
        inst.create_calendar_event = AsyncMock(return_value={"id": "e"})
        inst.get_user_emails = AsyncMock(return_value=[])
        inst.custom_method = AsyncMock(return_value={"ok": 1})
        svc_cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.outlook_service.OutlookService", svc_cls)
        engine = wf_env["engine"]
        assert (await engine._execute_outlook_action("send_email", {"to_recipients": ["a@b.c"]}))["status"] == "success"
        assert (await engine._execute_outlook_action("create_event", {"subject": "s"}))["status"] == "success"
        assert (await engine._execute_outlook_action("get_emails", {}))["status"] == "success"
        assert (await engine._execute_outlook_action("custom_method", {}))["status"] == "success"
        with pytest.raises(ValueError):
            await engine._execute_outlook_action("bogus_method", {})
        inst.send_email = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            await engine._execute_outlook_action("send_email", {})

    @pytest.mark.asyncio
    async def test_jira(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        inst = MagicMock(spec=["get_issue"])
        inst.get_issue = MagicMock(return_value={"key": "K-1"})
        svc_cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.jira_service.JiraService", svc_cls)
        engine = wf_env["engine"]
        assert (await engine._execute_jira_action("get_issue", {"key": "K-1"}))["status"] == "success"
        with pytest.raises(ValueError):
            await engine._execute_jira_action("bogus", {})
        inst.get_issue.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await engine._execute_jira_action("get_issue", {})

    @pytest.mark.asyncio
    async def test_trello(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        inst = MagicMock(spec=["get_cards"])
        inst.get_cards = MagicMock(return_value=[])
        svc_cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.trello_service.TrelloService", svc_cls)
        engine = wf_env["engine"]
        assert (await engine._execute_trello_action("get_cards", {}))["status"] == "success"
        with pytest.raises(ValueError):
            await engine._execute_trello_action("bogus", {})

    @pytest.mark.asyncio
    async def test_stripe_not_available(self, wf_env, monkeypatch):
        monkeypatch.setattr("core.workflow_engine.HAS_STRIPE", False)
        monkeypatch.setattr("core.workflow_engine.StripeService", None)
        with pytest.raises(AtomValidationError):
            await wf_env["engine"]._execute_stripe_action("charge", {})

    @pytest.mark.asyncio
    async def test_stripe_no_token(self, wf_env, monkeypatch):
        monkeypatch.setattr("core.workflow_engine.HAS_STRIPE", True)
        monkeypatch.setattr("core.workflow_engine.StripeService", MagicMock())
        ts = MagicMock()
        ts.get_token.return_value = None
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        r = await wf_env["engine"]._execute_stripe_action("charge", {}, connection_id="c1")
        assert r["status"] == "error"

    @pytest.mark.asyncio
    async def test_stripe_success(self, wf_env, monkeypatch):
        inst = MagicMock(spec=["charge"])
        inst.charge = MagicMock(return_value={"id": "ch1"})
        monkeypatch.setattr("core.workflow_engine.HAS_STRIPE", True)
        monkeypatch.setattr("core.workflow_engine.StripeService", MagicMock(return_value=inst))
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        engine = wf_env["engine"]
        assert (await engine._execute_stripe_action("charge", {}, connection_id="c1"))["status"] == "success"
        with pytest.raises(ValueError):
            await engine._execute_stripe_action("bogus", {}, connection_id="c1")


class TestShopifyZoho:
    @pytest.mark.asyncio
    async def test_shopify(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok", "shop_url": "https://s.myshopify.com"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        inst = MagicMock(spec=["list_orders"])
        inst.list_orders = MagicMock(return_value=[{"order_number": 1, "total_price": "10", "currency": "USD"}])
        svc_cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.shopify_service.ShopifyService", svc_cls)
        engine = wf_env["engine"]
        r = await engine._execute_shopify_action("list_orders", {}, connection_id="c1")
        assert r["status"] == "success"
        assert r["result"] == [{"order_number": 1, "total_price": "10", "currency": "USD"}]
        with pytest.raises(ValueError):
            await engine._execute_shopify_action("bogus", {}, connection_id="c1")
        inst.list_orders.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await engine._execute_shopify_action("list_orders", {}, connection_id="c1")

    @pytest.mark.asyncio
    async def test_shopify_async_method(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok", "shop": "https://s.myshopify.com"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        inst = MagicMock()
        inst.sync_orders = AsyncMock(return_value={"ok": True})
        svc_cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.shopify_service.ShopifyService", svc_cls)
        r = await wf_env["engine"]._execute_shopify_action("sync_orders", {}, connection_id="c1")
        assert r["status"] == "success"

    @pytest.mark.asyncio
    async def test_zoho_crm(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        inst = MagicMock(spec=["create_lead"])
        inst.create_lead = MagicMock(return_value={"id": "l"})
        svc_cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.zoho_crm_service.ZohoCRMService", svc_cls)
        engine = wf_env["engine"]
        assert (await engine._execute_zoho_crm_action("create_lead", {}, connection_id="c1"))["status"] == "success"
        with pytest.raises(ValueError):
            await engine._execute_zoho_crm_action("bogus", {}, connection_id="c1")
        inst.create_lead.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            await engine._execute_zoho_crm_action("create_lead", {}, connection_id="c1")

    @pytest.mark.asyncio
    async def test_zoho_books_and_inventory(self, wf_env, monkeypatch):
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok", "organization_id": "org1"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        inst = MagicMock(spec=["get_invoices"])
        inst.get_invoices = MagicMock(return_value=[])
        svc_cls = MagicMock(return_value=inst)
        monkeypatch.setattr("integrations.zoho_books_service.ZohoBooksService", svc_cls)
        engine = wf_env["engine"]
        r = await engine._execute_zoho_books_action("get_invoices", {}, connection_id="c1")
        assert r["status"] == "success"
        assert r["result"] == []
        with pytest.raises(ValueError):
            await engine._execute_zoho_books_action("bogus", {}, connection_id="c1")
        inst2 = MagicMock(spec=["get_items"])
        inst2.get_items = MagicMock(return_value=[])
        svc_cls2 = MagicMock(return_value=inst2)
        monkeypatch.setattr("integrations.zoho_inventory_service.ZohoInventoryService", svc_cls2)
        r = await engine._execute_zoho_inventory_action("get_items", {}, connection_id="c1")
        assert r["status"] == "success"
        with pytest.raises(ValueError):
            await engine._execute_zoho_inventory_action("bogus", {}, connection_id="c1")


class TestGenericAction:
    @pytest.mark.asyncio
    async def test_catalog_lookup_and_request(self, wf_env, monkeypatch):
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=True)
        monkeypatch.setattr("core.cache.cache", cache)

        item = MagicMock()
        item.id = "svc"
        item.actions = [{
            "name": "list_users",
            "url": "https://api.example.com/users/{uid}",
            "method": "GET",
        }]

        def _session():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = item

            class _Ctx:
                def __enter__(self):
                    return db

                def __exit__(self, *a):
                    return False

            return _Ctx()

        monkeypatch.setattr("core.workflow_engine.get_db_session", _session)
        engine = wf_env["engine"]

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"users": []}

        async def _request(method, url, **kw):
            assert url == "https://api.example.com/users/42"
            assert kw["params"] == {"verbose": "1"}
            return FakeResponse()

        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.request = _request
            r = await engine._execute_generic_action("svc", "list_users", {"uid": 42, "verbose": "1"})
        assert r == {"users": []}
        cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_and_post_body(self, wf_env, monkeypatch):
        cache = MagicMock()
        cache.get = AsyncMock(return_value={"actions": [{"name": "create", "path": "/v1/things", "method": "POST"}]})
        cache.set = AsyncMock(return_value=True)
        monkeypatch.setattr("core.cache.cache", cache)
        ts = MagicMock()
        ts.get_token.return_value = {"access_token": "tok"}
        monkeypatch.setattr("core.workflow_engine.token_storage", ts)
        engine = wf_env["engine"]

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"created": True}

        async def _request(method, url, **kw):
            assert kw["json"] == {"name": "x"}
            assert kw["headers"]["Authorization"] == "Bearer tok"
            return FakeResponse()

        with patch("httpx.AsyncClient") as client_cls:
            client_cls.return_value.__aenter__.return_value.request = _request
            r = await engine._execute_generic_action("svc", "create", {"name": "x"}, connection_id="c1")
        assert r == {"created": True}

    @pytest.mark.asyncio
    async def test_errors(self, wf_env, monkeypatch):
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=True)
        monkeypatch.setattr("core.cache.cache", cache)
        engine = wf_env["engine"]

        def _session_no_item():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = None

            class _Ctx:
                def __enter__(self):
                    return db

                def __exit__(self, *a):
                    return False

            return _Ctx()

        monkeypatch.setattr("core.workflow_engine.get_db_session", _session_no_item)
        with pytest.raises(ValueError, match="not found in Integration Catalog"):
            await engine._execute_generic_action("svc", "x", {})

        def _session_err():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.workflow_engine.get_db_session", _session_err)
        with pytest.raises(RuntimeError):
            await engine._execute_generic_action("svc", "x", {})

        cache.get = AsyncMock(return_value={"actions": []})
        with pytest.raises(ValueError, match="not found in catalog"):
            await engine._execute_generic_action("svc", "x", {})

        cache.get = AsyncMock(return_value={"actions": [{"name": "x", "method": "GET"}]})
        with pytest.raises(ValueError, match="No URL"):
            await engine._execute_generic_action("svc", "x", {})

        cache.get = AsyncMock(return_value={"actions": [{"name": "x", "url": "/v/{id}", "method": "GET"}]})
        with pytest.raises(ValueError, match="Missing path parameter"):
            await engine._execute_generic_action("svc", "x", {})


class TestGoalManagement:
    @pytest.mark.asyncio
    async def test_create_goal_and_missing_params(self, wf_env, monkeypatch):
        engine = MagicMock()
        engine.create_goal_from_text = AsyncMock(return_value=MagicMock(**{"dict.return_value": {"id": "g1"}}))
        monkeypatch.setattr("core.goal_engine.goal_engine", engine)
        r = await wf_env["engine"]._execute_goal_management_action(
            "create_goal", {"title": "t", "target_date": "2026-12-31T00:00:00Z"})
        assert r == {"id": "g1"}
        with pytest.raises(ValueError):
            await wf_env["engine"]._execute_goal_management_action("create_goal", {"title": "t"})

    @pytest.mark.asyncio
    async def test_check_escalations(self, wf_env, monkeypatch):
        engine = MagicMock()
        engine.check_for_escalations = AsyncMock(return_value=[])
        monkeypatch.setattr("core.goal_engine.goal_engine", engine)
        r = await wf_env["engine"]._execute_goal_management_action("check_escalations", {})
        assert r == {"escalations": []}

    @pytest.mark.asyncio
    async def test_update_subtask(self, wf_env, monkeypatch):
        goal = MagicMock()
        st = MagicMock()
        st.id = "st1"
        goal.sub_tasks = [st]
        engine = MagicMock()
        engine.goals = {"g1": goal}
        engine.update_goal_progress = AsyncMock(return_value=None)
        goal.dict = MagicMock(return_value={"id": "g1"})
        monkeypatch.setattr("core.goal_engine.goal_engine", engine)
        r = await wf_env["engine"]._execute_goal_management_action(
            "update_subtask", {"goal_id": "g1", "sub_task_id": "st1", "status": "done"})
        assert r == {"id": "g1"}
        assert st.status == "done"
        with pytest.raises(ValueError):
            await wf_env["engine"]._execute_goal_management_action(
                "update_subtask", {"goal_id": "ghost", "sub_task_id": "st1", "status": "done"})
        with pytest.raises(ValueError, match="Unknown goal_management"):
            await wf_env["engine"]._execute_goal_management_action("bogus", {})


class TestArborRefinement:
    @pytest.mark.asyncio
    async def test_success_run(self, wf_env, monkeypatch):
        sm = wf_env["sm"]
        eid = await sm.create_execution("wf-1", {})
        sm.executions[eid]["status"] = "COMPLETED"
        engine = wf_env["engine"]
        engine.start_workflow = AsyncMock(return_value=eid)
        persist = AsyncMock()
        monkeypatch.setattr("core.hypothesis_tree_endpoints._persist_tree", persist)

        class FakeTree:
            def __init__(self, *a, **k):
                self.negative_constraints = []
                self.nodes = []

            def add_node(self, n):
                self.nodes.append(n)

            def get_domain_statistics(self):
                return {}

            def get_path_to_root(self, nid):
                return [nid]

            def prune_branch(self, *a, **k):
                pass

        node_cls = MagicMock()
        inst_node = MagicMock()
        inst_node.id = "node-1"
        inst_node.calculate_promise_score = MagicMock(return_value=0.9)
        inst_node.metrics = MagicMock()
        inst_node.status = None
        inst_node.promise_score = None
        node_cls.return_value = inst_node
        with patch("core.hypothesis_tree.OptimizationTree", FakeTree), \
             patch("core.hypothesis_tree.WorkflowHypothesisNode", node_cls), \
             patch("core.hypothesis_tree.NodeStatus") as ns, \
             patch("core.hypothesis_tree.PruningReason") as pr, \
             patch("core.hypothesis_tree.TaskType") as tt, \
             patch("core.hypothesis_tree.NodeMetrics") as nm:
            ns.SUCCESS = "SUCCESS"
            pr.TEST_FAILED = "TEST_FAILED"
            result = await engine.run_workflow_with_arbor_refinement(
                "t1", {"name": "WF", "steps": [{"id": "s1", "config": {}}]}, {})
        assert result["success"] is True
        assert result["promise_score"] == 0.9

    @pytest.mark.asyncio
    async def test_failed_run_prunes(self, wf_env, monkeypatch):
        sm = wf_env["sm"]
        eid = await sm.create_execution("wf-1", {})
        sm.executions[eid]["status"] = "FAILED"
        sm.executions[eid]["error"] = "nope"
        engine = wf_env["engine"]
        engine.start_workflow = AsyncMock(return_value=eid)
        persist = AsyncMock()
        monkeypatch.setattr("core.hypothesis_tree_endpoints._persist_tree", persist)

        class FakeTree:
            def __init__(self, *a, **k):
                self.negative_constraints = []
                self.nodes = []
                self.pruned = []

            def add_node(self, n):
                self.nodes.append(n)

            def get_domain_statistics(self):
                return {}

            def prune_branch(self, nid, reason):
                self.pruned.append((nid, reason))

        node_cls = MagicMock()
        inst_node = MagicMock()
        inst_node.id = "node-1"
        inst_node.metrics = MagicMock()
        inst_node.status = None
        inst_node.promise_score = None
        node_cls.return_value = inst_node
        with patch("core.hypothesis_tree.OptimizationTree", FakeTree), \
             patch("core.hypothesis_tree.WorkflowHypothesisNode", node_cls), \
             patch("core.hypothesis_tree.NodeStatus") as ns, \
             patch("core.hypothesis_tree.PruningReason") as pr, \
             patch("core.hypothesis_tree.TaskType") as tt, \
             patch("core.hypothesis_tree.NodeMetrics") as nm:
            pr.TEST_FAILED = "TEST_FAILED"
            result = await engine.run_workflow_with_arbor_refinement(
                "t1", {"name": "WF", "steps": []}, {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_exception_raises_and_prunes(self, wf_env, monkeypatch):
        engine = wf_env["engine"]
        engine.start_workflow = AsyncMock(side_effect=RuntimeError("boom"))
        persist = AsyncMock()
        persist.side_effect = [None, RuntimeError("persist failed")]
        monkeypatch.setattr("core.hypothesis_tree_endpoints._persist_tree", persist)

        class FakeTree:
            def __init__(self, *a, **k):
                self.negative_constraints = []
                self.nodes = []

            def add_node(self, n):
                self.nodes.append(n)

            def prune_branch(self, *a, **k):
                pass

        node_cls = MagicMock()
        inst_node = MagicMock()
        inst_node.id = "node-1"
        inst_node.metrics = MagicMock()
        node_cls.return_value = inst_node
        with patch("core.hypothesis_tree.OptimizationTree", FakeTree), \
             patch("core.hypothesis_tree.WorkflowHypothesisNode", node_cls), \
             patch("core.hypothesis_tree.NodeStatus") as ns, \
             patch("core.hypothesis_tree.PruningReason") as pr, \
             patch("core.hypothesis_tree.TaskType") as tt, \
             patch("core.hypothesis_tree.NodeMetrics") as nm:
            with pytest.raises(RuntimeError):
                await engine.run_workflow_with_arbor_refinement(
                    "t1", {"name": "WF", "steps": []}, {})


# ============================================================================
# core.atom_meta_agent
# ============================================================================

import core.atom_meta_agent as ama
from core.atom_meta_agent import (
    AtomMetaAgent,
    ReActStep,
    ToolCall,
    _is_error_observation,
    _meta_agent_sandbox_check,
)
from ai.nlp_engine import RouteCategory, RouteClassification


@pytest.fixture
def meta_agent(monkeypatch):
    wm = MagicMock()
    monkeypatch.setattr(ama, "WorldModelService", MagicMock(return_value=wm))
    monkeypatch.setattr(ama, "AdvancedWorkflowOrchestrator", MagicMock())
    monkeypatch.setattr(ama, "CapabilityGraduationService", MagicMock())
    cp = MagicMock()
    cp.get_canvas_context = AsyncMock(return_value=None)
    monkeypatch.setattr(ama, "get_canvas_provider", MagicMock(return_value=cp))
    monkeypatch.setattr(ama, "mcp_service", MagicMock())
    monkeypatch.setattr(ama, "AgentGovernanceService", MagicMock())
    monkeypatch.setattr(ama, "AgentFleetService", MagicMock())
    monkeypatch.setattr(ama, "FleetOptimizationService", MagicMock())
    monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", False)
    monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", False)

    class _FakeSL:
        def __init__(self):
            self.db = MagicMock()

        def __enter__(self):
            return self.db

        def __exit__(self, *a):
            return False

        def close(self):
            pass

        def rollback(self):
            self.db.rollback()

        def commit(self):
            self.db.commit()

        def add(self, *a):
            self.db.add(*a)

        def query(self, *a):
            return self.db.query(*a)

    sl = _FakeSL()
    monkeypatch.setattr(ama, "SessionLocal", lambda: sl)

    sf = MagicMock()
    sf.get_llm_service.return_value = MagicMock()
    monkeypatch.setattr("core.service_factory.ServiceFactory", sf)

    agent = ama.AtomMetaAgent()
    agent.llm = MagicMock()
    agent.world_model = wm
    return agent, sl


def _prepare_execute(agent, sl, monkeypatch, route_category=None, tools=None):
    workspace = SimpleNamespace(tenant_id="default")
    db = sl.db
    db.query.return_value.filter.return_value.first.return_value = workspace

    nlu = MagicMock()
    nlu.classify_route = AsyncMock(return_value=RouteClassification(
        category=route_category or RouteCategory.ONE_OFF,
        reasoning="r", confidence=0.9,
    ))
    monkeypatch.setattr(ama, "NaturalLanguageEngine", MagicMock(return_value=nlu))

    agent.world_model.recall_experiences = AsyncMock(return_value={"experiences": []})
    agent.mcp.get_all_tools = AsyncMock(return_value=tools or [
        {"name": "trigger_workflow", "description": "d", "parameters": {}},
    ])
    monkeypatch.setattr("core.field_guide_service.get_field_guide_service",
                        lambda: MagicMock(get_field_guide_context=lambda w: "guide"))
    agent._check_budget_before_react = AsyncMock(return_value={"allowed": True})
    agent._persist_reasoning_step = MagicMock(return_value="step-id")
    agent._record_execution = AsyncMock()
    return nlu


class TestMetaSandboxCheck:
    def _cfg(self, enabled=True, fs=False, tripwires=False, caps=False):
        cfg = MagicMock()
        cfg.is_sandbox_enabled.return_value = enabled
        cfg.is_sandbox_fs_enabled.return_value = fs
        cfg.is_sandbox_tripwires_enabled.return_value = tripwires
        cfg.is_sandbox_caps_enabled.return_value = caps
        return cfg

    def _patch_core_attr(self, monkeypatch, name, obj):
        import core as _core_pkg
        monkeypatch.setattr(_core_pkg, name, obj, raising=False)
        monkeypatch.setitem(sys.modules, f"core.{name}", obj)

    def test_disabled_returns_none(self, monkeypatch):
        self._patch_core_attr(monkeypatch, "sandbox_config", self._cfg(enabled=False))
        assert _meta_agent_sandbox_check("tool", {}, {"run_id": "r", "tier": "autonomous"}) is None

    def test_missing_run_id_or_tier(self, monkeypatch):
        self._patch_core_attr(monkeypatch, "sandbox_config", self._cfg())
        assert _meta_agent_sandbox_check("tool", {}, {}) is None
        assert _meta_agent_sandbox_check("tool", {}, {"run_id": "r"}) is None
        assert _meta_agent_sandbox_check("tool", {}, {"run_id": "r", "tier": ""}) is None

    def test_blocked_decision_writes_violation(self, monkeypatch):
        self._patch_core_attr(monkeypatch, "sandbox_config", self._cfg())

        decision = MagicMock()
        decision.is_allowed = False
        decision.requires_review = True
        decision.enforced = True
        decision.violation_detail = "nope"
        decision.decision = "blocked"
        issuer = MagicMock()
        issuer.issue.return_value = MagicMock()
        issuer.check.return_value = decision
        policy_mod = types.ModuleType("core.sandbox_policy")
        policy_mod.PolicyIssuer = MagicMock(return_value=issuer)
        policy_mod.ALLOWED = "allowed"
        policy_mod.SandboxDecision = MagicMock
        monkeypatch.setitem(sys.modules, "core.sandbox_policy", policy_mod)
        write_violation = MagicMock()
        audit_mod = types.ModuleType("core.sandbox_audit")
        audit_mod.write_violation = write_violation
        monkeypatch.setitem(sys.modules, "core.sandbox_audit", audit_mod)
        killrun_mod = types.ModuleType("core.sandbox_killrun")
        killrun_mod.guard = MagicMock()
        monkeypatch.setitem(sys.modules, "core.sandbox_killrun", killrun_mod)
        self._patch_core_attr(monkeypatch, "sandbox_killrun", killrun_mod)
        result = _meta_agent_sandbox_check("tool", {}, {"run_id": "r", "tier": "student"})
        assert result is decision
        write_violation.assert_called_once()

    def test_fs_and_caps_requires_review(self, monkeypatch):
        self._patch_core_attr(monkeypatch, "sandbox_config",
                              self._cfg(fs=True, tripwires=True, caps=True))

        allowed = MagicMock()
        allowed.is_allowed = True
        allowed.requires_review = False
        allowed.args_hash = "h"
        fs_decision = MagicMock()
        fs_decision.requires_review = True
        tw_decision = MagicMock()
        tw_decision.decision = "allowed"
        cap_decision = MagicMock()
        cap_decision.requires_review = True
        issuer = MagicMock()
        issuer.issue.return_value = MagicMock()
        issuer.check.return_value = allowed
        policy_mod = types.ModuleType("core.sandbox_policy")
        policy_mod.PolicyIssuer = MagicMock(return_value=issuer)
        policy_mod.ALLOWED = "allowed"
        policy_mod.SandboxDecision = MagicMock
        monkeypatch.setitem(sys.modules, "core.sandbox_policy", policy_mod)
        fs_mod = types.ModuleType("core.sandbox_fs")
        fs_mod.validate = lambda *a, **k: fs_decision
        monkeypatch.setitem(sys.modules, "core.sandbox_fs", fs_mod)
        tw_mod = types.ModuleType("core.sandbox_tripwire")
        tw_mod.check = lambda *a, **k: tw_decision
        monkeypatch.setitem(sys.modules, "core.sandbox_tripwire", tw_mod)
        self._patch_core_attr(monkeypatch, "sandbox_tripwire", tw_mod)
        caps_mod = types.ModuleType("core.sandbox_caps")
        caps_mod.check_caps = lambda *a, **k: cap_decision
        monkeypatch.setitem(sys.modules, "core.sandbox_caps", caps_mod)
        self._patch_core_attr(monkeypatch, "sandbox_caps", caps_mod)
        killrun_mod = types.ModuleType("core.sandbox_killrun")
        killrun_mod.guard = MagicMock()
        monkeypatch.setitem(sys.modules, "core.sandbox_killrun", killrun_mod)
        self._patch_core_attr(monkeypatch, "sandbox_killrun", killrun_mod)
        audit_mod = types.ModuleType("core.sandbox_audit")
        audit_mod.write_violation = MagicMock()
        monkeypatch.setitem(sys.modules, "core.sandbox_audit", audit_mod)
        result = _meta_agent_sandbox_check("tool", {}, {"run_id": "r", "tier": "student"})
        assert result is cap_decision

    def test_killrun_aborted_propagates(self, monkeypatch):
        self._patch_core_attr(monkeypatch, "sandbox_config", self._cfg())
        policy_mod = types.ModuleType("core.sandbox_policy")
        policy_mod.PolicyIssuer = MagicMock(side_effect=RuntimeError("x"))
        policy_mod.SandboxDecision = MagicMock
        policy_mod.ALLOWED = "allowed"
        monkeypatch.setitem(sys.modules, "core.sandbox_policy", policy_mod)
        killrun_mod = types.ModuleType("core.sandbox_killrun")
        killrun_mod.KillRunAborted = RuntimeError
        monkeypatch.setitem(sys.modules, "core.sandbox_killrun", killrun_mod)
        self._patch_core_attr(monkeypatch, "sandbox_killrun", killrun_mod)
        with pytest.raises(RuntimeError):
            _meta_agent_sandbox_check("tool", {}, {"run_id": "r", "tier": "student"})

    def test_exception_fails_open_allowed(self, monkeypatch):
        self._patch_core_attr(monkeypatch, "sandbox_config", self._cfg())
        policy_mod = types.ModuleType("core.sandbox_policy")
        policy_mod.PolicyIssuer = MagicMock(side_effect=RuntimeError("x"))
        policy_mod.SandboxDecision = MagicMock
        policy_mod.ALLOWED = "allowed"
        monkeypatch.setitem(sys.modules, "core.sandbox_policy", policy_mod)
        killrun_mod = types.ModuleType("core.sandbox_killrun")
        killrun_mod.KillRunAborted = type("KillRunAborted", (Exception,), {})
        monkeypatch.setitem(sys.modules, "core.sandbox_killrun", killrun_mod)
        self._patch_core_attr(monkeypatch, "sandbox_killrun", killrun_mod)
        result = _meta_agent_sandbox_check("tool", {}, {"run_id": "r", "tier": "student"})
        assert result.decision == "allowed"


class TestMetaExecuteEdges:
    @pytest.mark.asyncio
    async def test_vector_recall_prefetch_failure(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", True)

        def _boom(workspace_id, query, limit):
            raise RuntimeError("lancedb down")

        monkeypatch.setattr(ama, "_prefetch_relevant_facts", _boom)
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_field_guide_failure(self, meta_agent, monkeypatch):
        agent, sl = meta_agent

        def _boom():
            raise RuntimeError("fs error")

        monkeypatch.setattr("core.field_guide_service.get_field_guide_service", _boom)
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_agent_execution_create_failure(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        db = sl.db
        db.commit.side_effect = RuntimeError("db down")
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_canvas_episode_recall_failure(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        canvas_state = SimpleNamespace(canvas_id="c1", comments=[], artifact_count=1)
        agent.canvas_provider.get_canvas_context = AsyncMock(return_value=canvas_state)
        agent.canvas_provider.format_for_agent = MagicMock(return_value="canvas text")
        agent.world_model.recall_episodes = AsyncMock(side_effect=RuntimeError("no episodes"))
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute(
            "hello", canvas_context={"canvas_id": "c1", "tenant_id": "t"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_canvas_recall_success(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        canvas_state = SimpleNamespace(canvas_id="c1", comments=[], artifact_count=1)
        agent.canvas_provider.get_canvas_context = AsyncMock(return_value=canvas_state)
        agent.canvas_provider.format_for_agent = MagicMock(return_value="canvas text")
        agent.world_model.recall_episodes = AsyncMock(return_value=[{"canvas_id": "c1"}])
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute(
            "hello", canvas_context={"canvas_id": "c1", "tenant_id": "t"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_tool_descriptions_serialization_failure(self, meta_agent, monkeypatch):
        agent, sl = meta_agent

        class _Bad:
            pass

        _prepare_execute(agent, sl, monkeypatch, tools=[
            {"name": "trigger_workflow", "description": _Bad()},
        ])
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_fleet_routing_config_import_failure(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setitem(sys.modules, "core.fleet_routing_config", None)
        _prepare_execute(agent, sl, monkeypatch, route_category=RouteCategory.ONE_OFF)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("x" * 50)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_fleet_force_enforce_returns_recruitment(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        cfg = types.ModuleType("core.fleet_routing_config")
        cfg.fleet_routing_enabled = lambda: True
        cfg.fleet_routing_force_enforce = lambda: True
        monkeypatch.setitem(sys.modules, "core.fleet_routing_config", cfg)
        _prepare_execute(agent, sl, monkeypatch, route_category=RouteCategory.ONE_OFF)
        agent.route_with_governance = AsyncMock(return_value={
            "specialists_count": 2, "chain_id": "chain-1", "status": "fleet_recruited",
        })
        result = await agent.execute("x" * 50, context={"user_id": "u1"})
        assert result["status"] == "fleet_recruited"
        assert result["chain_id"] == "chain-1"

    @pytest.mark.asyncio
    async def test_fleet_shadow_mode_falls_through(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        cfg = types.ModuleType("core.fleet_routing_config")
        cfg.fleet_routing_enabled = lambda: True
        cfg.fleet_routing_force_enforce = lambda: False
        monkeypatch.setitem(sys.modules, "core.fleet_routing_config", cfg)
        _prepare_execute(agent, sl, monkeypatch, route_category=RouteCategory.ONE_OFF)
        agent.route_with_governance = AsyncMock(return_value={
            "specialists_count": 2, "chain_id": "chain-1",
        })
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("x" * 50, context={"user_id": "u1"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_fleet_route_error_falls_back(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        cfg = types.ModuleType("core.fleet_routing_config")
        cfg.fleet_routing_enabled = lambda: True
        cfg.fleet_routing_force_enforce = lambda: True
        monkeypatch.setitem(sys.modules, "core.fleet_routing_config", cfg)
        _prepare_execute(agent, sl, monkeypatch, route_category=RouteCategory.ONE_OFF)
        agent.route_with_governance = AsyncMock(side_effect=RuntimeError("boom"))
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("x" * 50, context={"user_id": "u1"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_radio_drain_breaks_nothing(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        monkeypatch.setattr("core.agent_radio.radio_service.inbox_drain_text",
                            lambda *a, **k: "[mention] hi @atom")
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello", context={"radio_thread_id": "th-1"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_radio_drain_exception_swallowed(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        monkeypatch.setattr("core.agent_radio.radio_service.inbox_drain_text",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("radio down")))
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello", context={"radio_thread_id": "th-1"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_turn_fact_on_session_end(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", True)
        _prepare_execute(agent, sl, monkeypatch)
        extractor = MagicMock()
        extractor.extract_from_turn = AsyncMock(return_value=None)
        monkeypatch.setattr(ama, "get_turn_fact_extractor", lambda **kw: extractor)
        monkeypatch.setattr(ama, "_pending_extraction_tasks", set())
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello", context={"session_id": "s1", "user_id": "u1"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_turn_fact_on_session_end_failure(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", True)
        _prepare_execute(agent, sl, monkeypatch)

        def _boom(**kw):
            raise RuntimeError("extractor init failed")

        monkeypatch.setattr(ama, "get_turn_fact_extractor", _boom)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_finalize_failure_and_rollback(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))

        db2 = sl.db
        db2.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = SimpleNamespace(status="running")
        db2.commit.side_effect = RuntimeError("commit failed")
        db2.rollback = MagicMock()
        result = await agent.execute("hello")
        assert result["status"] == "success"
        db2.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_body_exception_finalizes_failed(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(side_effect=RuntimeError("react crashed"))
        with pytest.raises(RuntimeError):
            await agent.execute("hello")

    @pytest.mark.asyncio
    async def test_parallel_tools_failed_verification_critique(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._execute_parallel_tools = AsyncMock(return_value=[{
            "tool_name": "tool_a", "params": {}, "output": "bad",
            "verified_kind": "failed_verification",
            "verified_evidence": "output mismatch",
        }])
        seen = []

        async def cb(record):
            seen.append(record)

        agent._react_step = AsyncMock(side_effect=[ReActStep(
            thought="t", actions=[ToolCall(tool="tool_a", params={})]),
            ReActStep(thought="t", final_answer="done")])
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                            lambda: True)
        result = await agent.execute("hello", step_callback=cb)
        assert result["status"] == "success"
        assert any("[CRITIQUE]" in (r.get("output") or "") or r.get("step_type") == "parallel"
                   for r in seen)

    @pytest.mark.asyncio
    async def test_parallel_tools_error_observation_critique(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._execute_parallel_tools = AsyncMock(return_value=[{
            "tool_name": "tool_a", "params": {}, "output": "Tool error. retry",
            "verified_kind": "unverified", "verified_evidence": None,
        }])
        agent._react_step = AsyncMock(side_effect=[ReActStep(
            thought="t", actions=[ToolCall(tool="tool_a", params={})]),
            ReActStep(thought="t", final_answer="done")])
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                            lambda: True)
        result = await agent.execute("hello")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_parallel_tools_parse_exception(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._execute_parallel_tools = AsyncMock(return_value=[{
            "tool_name": "tool_a", "params": {}, "output": "ok",
            "verified_kind": "unverified", "verified_evidence": None,
        }])
        monkeypatch.setattr(ama, "parse_tool_outcome",
                            lambda obs: (_ for _ in ()).throw(RuntimeError("parse fail")))
        agent._react_step = AsyncMock(side_effect=[ReActStep(
            thought="t", actions=[ToolCall(tool="tool_a", params={})]),
            ReActStep(thought="t", final_answer="done")])
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                            lambda: True)
        result = await agent.execute("hello")
        assert result["status"] == "success"


class TestMetaToolExecution:
    @pytest.mark.asyncio
    async def test_tool_rejected_path(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": True, "action_complexity": 1,
        })
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        agent.mcp.call_tool = AsyncMock(return_value={"ok": True})
        result = await agent._execute_tool_with_governance("some_tool", {}, {"user_id": "u"}, None)
        assert result == "{'ok': True}"

    @pytest.mark.asyncio
    async def test_tool_requires_approval_rejected(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": False, "action_complexity": 3,
        })
        gov.request_approval.return_value = "action-1"
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        agent._wait_for_approval = AsyncMock(return_value=False)
        result = await agent._execute_tool_with_governance("some_tool", {}, {}, None)
        assert "REJECTED" in result

    @pytest.mark.asyncio
    async def test_tool_governance_blocked(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": False, "action_complexity": 1, "reason": "nope",
        })
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        result = await agent._execute_tool_with_governance("some_tool", {}, {}, None)
        assert "Governance blocked" in result

    @pytest.mark.asyncio
    async def test_tool_exception_returns_error(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": True, "action_complexity": 1,
        })
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        agent.mcp.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
        result = await agent._execute_tool_with_governance("some_tool", {}, {}, None)
        assert "Tool error" in result

    @pytest.mark.asyncio
    async def test_invoke_capability_student_blocked(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        agent.graduation_service.get_maturity = MagicMock(return_value="student")
        result = await agent._execute_tool_with_governance(
            "invoke_capability", {"capability_name": "cap_x"}, {}, None, pre_approved=True)
        assert "STUDENT" in result

    @pytest.mark.asyncio
    async def test_invoke_capability_executes(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        agent.graduation_service.get_maturity = MagicMock(return_value="autonomous")
        agent.mcp.call_tool = AsyncMock(return_value="result-x")
        agent.graduation_service.record_usage = MagicMock()
        result = await agent._execute_tool_with_governance(
            "invoke_capability", {"capability_name": "cap_x", "params": {"a": 1}},
            {}, None, pre_approved=True)
        assert result == "result-x"

    @pytest.mark.asyncio
    async def test_action_judge_escalate_approved(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": True, "action_complexity": 1,
        })
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        judge_cls = MagicMock()
        judge_inst = MagicMock()
        judge_inst.evaluate = AsyncMock(return_value=SimpleNamespace(
            verdict="ESCALATE", rationale="be careful"))
        judge_cls.return_value = judge_inst
        monkeypatch.setattr("core.llm.action_judge.ActionJudge", judge_cls)
        monkeypatch.setattr("core.llm.action_judge.JudgeVerdict",
                            SimpleNamespace(BLOCK="BLOCK", ESCALATE="ESCALATE"))
        sc = MagicMock()
        sc.is_sandbox_judge_enabled.return_value = True
        import core.sandbox_config as _sc_mod2
        monkeypatch.setattr("core.sandbox_config", sc)
        gov.request_approval.return_value = "a1"
        agent._wait_for_approval = AsyncMock(return_value=True)
        agent.mcp.call_tool = AsyncMock(return_value="ok")
        result = await agent._execute_tool_with_governance("some_tool", {}, {}, None)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_action_judge_blocked(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": True, "action_complexity": 1,
        })
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        judge_cls = MagicMock()
        judge_inst = MagicMock()
        judge_inst.evaluate = AsyncMock(return_value=SimpleNamespace(
            verdict="BLOCK", rationale="not safe"))
        judge_cls.return_value = judge_inst
        monkeypatch.setattr("core.llm.action_judge.ActionJudge", judge_cls)
        monkeypatch.setattr("core.llm.action_judge.JudgeVerdict",
                            SimpleNamespace(BLOCK="BLOCK", ESCALATE="ESCALATE"))
        sc = MagicMock()
        sc.is_sandbox_judge_enabled.return_value = True
        import core.sandbox_config as _sc_mod2
        monkeypatch.setattr("core.sandbox_config", sc)
        result = await agent._execute_tool_with_governance("some_tool", {}, {}, None)
        assert "blocked by the safety judge" in result

    @pytest.mark.asyncio
    async def test_action_judge_error_skipped(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": True, "action_complexity": 1,
        })
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        judge_cls = MagicMock()
        judge_cls.side_effect = RuntimeError("judge down")
        monkeypatch.setattr("core.llm.action_judge.ActionJudge", judge_cls)
        sc = MagicMock()
        sc.is_sandbox_judge_enabled.return_value = True
        import core.sandbox_config as _sc_mod2
        monkeypatch.setattr("core.sandbox_config", sc)
        agent.mcp.call_tool = AsyncMock(return_value="ok")
        result = await agent._execute_tool_with_governance("some_tool", {}, {}, None)
        assert result == "ok"


class TestMetaParallelTools:
    @pytest.mark.asyncio
    async def test_sequential_fallback(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                            lambda: False)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools",
                            lambda: 4)
        agent._execute_tool_with_governance = AsyncMock(return_value="obs")
        records = await agent._execute_parallel_tools(
            [ToolCall(tool="t1", params={}), ToolCall(tool="t2", params={})], {}, None)
        assert len(records) == 2
        assert records[0]["verified_kind"] == "unverified"

    @pytest.mark.asyncio
    async def test_batch_blocked(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                            lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools",
                            lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": False, "action_complexity": 1,
        })
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        records = await agent._execute_parallel_tools(
            [ToolCall(tool="t1", params={})], {}, None)
        assert records[0]["verified_kind"] == "blocked"

    @pytest.mark.asyncio
    async def test_batch_rejected_by_hitl(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                            lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools",
                            lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": True, "action_complexity": 3,
        })
        gov.request_approval.return_value = "a1"
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        agent._wait_for_all_approvals = AsyncMock(return_value=False)
        records = await agent._execute_parallel_tools(
            [ToolCall(tool="t1", params={})], {}, None)
        assert records[0]["verified_kind"] == "rejected"

    @pytest.mark.asyncio
    async def test_batch_approved_executes(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                            lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools",
                            lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": True, "action_complexity": 3,
        })
        gov.request_approval.return_value = "a1"
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        agent._wait_for_all_approvals = AsyncMock(return_value=True)
        agent._execute_tool_with_governance = AsyncMock(return_value="obs")
        records = await agent._execute_parallel_tools(
            [ToolCall(tool="t1", params={})], {}, None)
        assert records[0]["output"] == "obs"

    @pytest.mark.asyncio
    async def test_tool_search_serial(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                            lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools",
                            lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": True, "action_complexity": 1,
        })
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        agent.mcp.search_tools = AsyncMock(return_value=[
            {"name": "new_tool", "description": "d", "parameters": {}}])
        records = await agent._execute_parallel_tools(
            [ToolCall(tool="mcp_tool_search", params={"query": "q"})], {}, None)
        assert "new_tool" in records[0]["output"]
        assert "new_tool" in [t["name"] for t in agent.session_tools]


class TestMetaMisc:
    @pytest.mark.asyncio
    async def test_spawn_agent_persist_without_db(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        registered = MagicMock()
        registered.id = "spawned_x_1"
        gov.register_or_update_agent.return_value = registered
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda *a, **k: gov)
        agent.graduation_service.reset_maturity = MagicMock()
        spawned = await agent.spawn_agent("finance_analyst", persist=True)
        assert spawned.id == "spawned_x_1"

    @pytest.mark.asyncio
    async def test_spawn_agent_persist_with_db(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        gov = MagicMock()
        registered = MagicMock()
        registered.id = "spawned_x_2"
        gov.register_or_update_agent.return_value = registered
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda *a, **k: gov)
        agent.graduation_service.reset_maturity = MagicMock()
        spawned = await agent.spawn_agent("custom", {"name": "N"}, persist=True, db=MagicMock())
        assert spawned.id == "spawned_x_2"

    @pytest.mark.asyncio
    async def test_spawn_agent_unknown_template(self, meta_agent):
        agent, _ = meta_agent
        with pytest.raises(ValueError):
            await agent.spawn_agent("nope")

    @pytest.mark.asyncio
    async def test_spawn_agent_ephemeral(self, meta_agent):
        agent, _ = meta_agent
        spawned = await agent.spawn_agent("custom", {"name": "N"})
        assert spawned.id.startswith("spawned_custom_")
        assert agent.spawned_agents[spawned.id] is spawned

    @pytest.mark.asyncio
    async def test_mentorship_guidance_supervisor_exists(self, meta_agent, monkeypatch):
        agent, sl = meta_agent

        def _session():
            db = MagicMock()
            student = MagicMock()
            student.category = "General"
            db.query.return_value.filter.return_value.first.return_value = student
            db.query.return_value.filter.return_value.filter.return_value.count.return_value = 1

            class _Ctx:
                def __enter__(self):
                    return db

                def __exit__(self, *a):
                    return False

            return _Ctx()

        monkeypatch.setattr(ama, "SessionLocal", _session)
        agent.llm.generate_response = AsyncMock(return_value="Guidance text")
        result = await agent.generate_mentorship_guidance("student-1", "act", {}, "why")
        assert "Guidance text" in result

    @pytest.mark.asyncio
    async def test_mentorship_guidance_supervisor_check_fails(self, meta_agent, monkeypatch):
        agent, sl = meta_agent

        def _session():
            raise RuntimeError("db down")

        monkeypatch.setattr(ama, "SessionLocal", _session)
        agent.llm.generate_response = AsyncMock(return_value="Guidance text")
        result = await agent.generate_mentorship_guidance("student-1", "act", {}, "why")
        assert "Guidance text" in result

    @pytest.mark.asyncio
    async def test_recruit_fleet_radio_thread(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        chain = MagicMock()
        chain.id = "chain-9"
        fleet = MagicMock()
        fleet.initialize_fleet.return_value = chain
        link = MagicMock()
        link.context_json = {"a": 1}
        db_inst = MagicMock()
        db_inst.query.return_value.filter.return_value.all.return_value = [link]
        monkeypatch.setattr(ama, "AgentFleetService", lambda db: fleet)
        monkeypatch.setattr(ama, "FleetOptimizationService", lambda db: MagicMock(
            get_optimization_parameters=MagicMock(
                return_value={"optimization_reason": "why", "x": 1})))
        class _Ctx:
            def __enter__(self):
                return db_inst

            def __exit__(self, *a):
                return None

        monkeypatch.setattr(ama, "SessionLocal", lambda: _Ctx())
        mod = types.ModuleType("core.business_agents")
        mod.get_specialized_agent = lambda name, workspace_id: SimpleNamespace(
            id=f"ag_{name}", name=name)
        monkeypatch.setitem(sys.modules, "core.business_agents", mod)
        link = MagicMock()
        link.context_json = {"a": 1}
        db_inst.query.return_value.filter.return_value.all.return_value = [link]
        radio = MagicMock()
        radio.attach_thread_for_chain = AsyncMock(return_value=SimpleNamespace(id="th-1"))
        monkeypatch.setattr("core.agent_radio.radio_adapter.attach_thread_for_chain", radio)
        result = await agent._recruit_fleet(
            "Big goal", [{"domain": "sales", "task": "Do x"}], {}, None)
        assert "Fleet Successfully Recruited" in result

    @pytest.mark.asyncio
    async def test_recruit_fleet_radio_error_skipped(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        chain = MagicMock()
        chain.id = "chain-9"
        fleet = MagicMock()
        fleet.initialize_fleet.return_value = chain
        fleet.recruit_member.return_value = MagicMock()
        db_inst = MagicMock()
        monkeypatch.setattr(ama, "AgentFleetService", lambda db: fleet)
        monkeypatch.setattr(ama, "FleetOptimizationService", lambda db: MagicMock(
            get_optimization_parameters=MagicMock(
                return_value={"optimization_reason": "why", "x": 1})))
        class _Ctx2:
            def __enter__(self):
                return db_inst

            def __exit__(self, *a):
                return None

        monkeypatch.setattr(ama, "SessionLocal", lambda: _Ctx2())
        mod2 = types.ModuleType("core.business_agents")
        mod2.get_specialized_agent = lambda name, workspace_id: SimpleNamespace(
            id=f"ag_{name}", name=name)
        monkeypatch.setitem(sys.modules, "core.business_agents", mod2)
        monkeypatch.setattr("core.agent_radio.radio_adapter.attach_thread_for_chain",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("radio down")))
        result = await agent._recruit_fleet(
            "Big goal", [{"domain": "sales", "task": "Do x"}], {}, None)
        assert "Fleet Successfully Recruited" in result

    @pytest.mark.asyncio
    async def test_recruit_fleet_failure(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr(ama, "AgentFleetService",
                            lambda db: (_ for _ in ()).throw(RuntimeError("fleet down")))
        result = await agent._recruit_fleet("Goal", [], {}, None)
        assert "Fleet recruitment failed" in result


# ============================================================================
# workflow_engine — second-pass edge coverage
# ============================================================================


class TestGraphExceptionPath:
    @pytest.mark.asyncio
    async def test_state_manager_error_fails_workflow(self, wf_env):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-g", {})
        wf = _node_wf([
            {"id": "n1", "title": "N1", "type": "action",
             "config": {"service": "email", "action": "send"}},
        ], [], created_by="u1")
        engine = wf_env["engine"]
        engine._execute_step = AsyncMock(
            return_value={"status": "success", "result": {"id": "x"}})
        orig = sm.get_execution_state
        calls = {"n": 0}

        async def _flaky(eid_):
            calls["n"] += 1
            if 3 <= calls["n"] <= 4:
                raise RuntimeError("state store down")
            return await orig(eid_)

        sm.get_execution_state = _flaky
        await engine._execute_workflow_graph(
            eid, wf, await sm.get_execution_state(eid), ws, "u1",
            datetime.now(timezone.utc))
        state = await sm.get_execution_state(eid)
        assert state["status"] == "FAILED"
        assert calls["n"] >= 4


class TestStepRecordUpdateFailure:
    @pytest.mark.asyncio
    async def test_step_record_update_failure_continues(self, wf_env, monkeypatch):
        sm, ws = wf_env["sm"], wf_env["ws"]
        eid = await sm.create_execution("wf-1", {})
        calls = {"n": 0}

        def _session():
            calls["n"] += 1
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = None
            if calls["n"] == 4:
                db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                    start_time=datetime.now(timezone.utc))
                db.commit.side_effect = RuntimeError("update failed")

            class _Ctx:
                def __enter__(self):
                    return db

                def __exit__(self, *a):
                    return False

            return _Ctx()

        monkeypatch.setattr("core.workflow_engine.get_db_session", _session)
        wf = _wf([_step("s1", service="email", action="send")])
        await wf_env["engine"]._run_execution(eid, wf)
        assert (await sm.get_execution_state(eid))["status"] == "COMPLETED"


class TestEvaluateConditionException:
    def test_generic_eval_exception(self, wf_env, monkeypatch):
        monkeypatch.setattr("core.safe_evaluator.safe_eval",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bad")))
        state = {"input_data": {"n": 5}}
        assert wf_env["engine"]._evaluate_condition("${input.n} == 5", state) is False


class TestPathHelpers2:
    def test_get_value_input_non_dict(self, wf_env):
        state = {"input_data": 5}
        assert wf_env["engine"]._get_value_from_path("input.a.b", state) is None


class TestArborPreviousTree:
    @pytest.mark.asyncio
    async def test_previous_tree_constraints(self, wf_env, monkeypatch):
        sm = wf_env["sm"]
        eid = await sm.create_execution("wf-1", {})
        sm.executions[eid]["status"] = "COMPLETED"
        engine = wf_env["engine"]
        engine.start_workflow = AsyncMock(return_value=eid)
        persist = AsyncMock()
        monkeypatch.setattr("core.hypothesis_tree_endpoints._persist_tree", persist)

        db = MagicMock()
        prev = SimpleNamespace(negative_constraints=["no_parallel"])
        db.query.return_value.filter.return_value.first.return_value = prev
        monkeypatch.setattr("core.database.get_db_session",
                            ctx_factory(db))

        class FakeTree:
            def __init__(self, *a, **k):
                self.negative_constraints = []
                self.nodes = []

            def add_node(self, n):
                self.nodes.append(n)

            def get_domain_statistics(self):
                return {}

            def get_path_to_root(self, nid):
                return [nid]

            def prune_branch(self, *a, **k):
                pass

        node_cls = MagicMock()
        inst_node = MagicMock()
        inst_node.id = "node-1"
        inst_node.calculate_promise_score = MagicMock(return_value=0.9)
        inst_node.metrics = MagicMock()
        inst_node.status = None
        inst_node.promise_score = None
        node_cls.return_value = inst_node
        with patch("core.hypothesis_tree.OptimizationTree", FakeTree), \
             patch("core.hypothesis_tree.WorkflowHypothesisNode", node_cls), \
             patch("core.hypothesis_tree.NodeStatus") as ns, \
             patch("core.hypothesis_tree.PruningReason") as pr, \
             patch("core.hypothesis_tree.TaskType") as tt, \
             patch("core.hypothesis_tree.NodeMetrics") as nm:
            ns.SUCCESS = "SUCCESS"
            result = await engine.run_workflow_with_arbor_refinement(
                "t1", {"name": "WF", "steps": [{"id": "s1", "config": {}}]}, {},
                previous_tree_id="tree-9")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_state_not_found_breaks(self, wf_env, monkeypatch):
        sm = wf_env["sm"]
        eid = await sm.create_execution("wf-1", {})
        sm.executions[eid]["status"] = "RUNNING"
        engine = wf_env["engine"]
        engine.start_workflow = AsyncMock(return_value="ghost-exec")
        persist = AsyncMock()
        monkeypatch.setattr("core.hypothesis_tree_endpoints._persist_tree", persist)

        class FakeTree:
            def __init__(self, *a, **k):
                self.nodes = []
                self.pruned = []

            def add_node(self, n):
                self.nodes.append(n)

            def get_domain_statistics(self):
                return {}

            def prune_branch(self, nid, reason):
                self.pruned.append((nid, reason))

        node_cls = MagicMock()
        inst_node = MagicMock()
        inst_node.id = "node-1"
        inst_node.metrics = MagicMock()
        inst_node.status = None
        inst_node.promise_score = None
        node_cls.return_value = inst_node
        with patch("core.hypothesis_tree.OptimizationTree", FakeTree), \
             patch("core.hypothesis_tree.WorkflowHypothesisNode", node_cls), \
             patch("core.hypothesis_tree.NodeStatus") as ns, \
             patch("core.hypothesis_tree.PruningReason") as pr, \
             patch("core.hypothesis_tree.TaskType") as tt, \
             patch("core.hypothesis_tree.NodeMetrics") as nm:
            pr.TEST_FAILED = "TEST_FAILED"
            result = await engine.run_workflow_with_arbor_refinement(
                "t1", {"name": "WF", "steps": []}, {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_persist_failure_swallowed_on_error(self, wf_env, monkeypatch):
        engine = wf_env["engine"]
        engine.start_workflow = AsyncMock(side_effect=RuntimeError("boom"))
        persist = Mock(side_effect=RuntimeError("persist down"))
        monkeypatch.setattr("core.hypothesis_tree_endpoints._persist_tree", persist)
        monkeypatch.setattr("core.database.get_db_session", ctx_factory(MagicMock()))

        class FakeTree:
            def __init__(self, *a, **k):
                self.nodes = []

            def add_node(self, n):
                self.nodes.append(n)

            def prune_branch(self, *a, **k):
                pass

        node_cls = MagicMock()
        inst_node = MagicMock()
        inst_node.id = "node-1"
        inst_node.metrics = MagicMock()
        node_cls.return_value = inst_node
        with patch("core.hypothesis_tree.OptimizationTree", FakeTree), \
             patch("core.hypothesis_tree.WorkflowHypothesisNode", node_cls), \
             patch("core.hypothesis_tree.NodeStatus") as ns, \
             patch("core.hypothesis_tree.PruningReason") as pr, \
             patch("core.hypothesis_tree.TaskType") as tt, \
             patch("core.hypothesis_tree.NodeMetrics") as nm:
            with pytest.raises(RuntimeError):
                await engine.run_workflow_with_arbor_refinement(
                    "t1", {"name": "WF", "steps": []}, {})


def ctx_factory(db):
    class _Ctx:
        def __enter__(self):
            return db

        def __exit__(self, *a):
            return False

    return lambda: _Ctx()


# ============================================================================
# atom_meta_agent — second-pass edge coverage
# ============================================================================


class TestMetaExecuteEdges2:
    @pytest.mark.asyncio
    async def test_vector_recall_prefetch_success(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr(ama, "_TURN_FACT_VECTOR_RECALL_ENABLED", True)
        _prepare_execute(agent, sl, monkeypatch)
        monkeypatch.setattr(ama, "_prefetch_relevant_facts",
                            lambda **kw: [{"fact_text": "x", "category": "preference"}])
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello", context={"user_id": "u1"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_field_guide_failure(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)

        def _boom():
            raise RuntimeError("fs error")

        monkeypatch.setattr("core.field_guide_service.get_field_guide_service", _boom)
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_tool_descriptions_dumps_failure(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        dumps_calls = {"n": 0}

        def _flaky(*a, **k):
            dumps_calls["n"] += 1
            if dumps_calls["n"] == 1:
                raise TypeError("not serializable")
            return "[]"

        monkeypatch.setattr(ama, "json", MagicMock(dumps=_flaky))
        agent._react_step = AsyncMock(return_value=ReActStep(thought="t", final_answer="done"))
        result = await agent.execute("hello")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_fleet_step_callback_emitted(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        cfg = types.ModuleType("core.fleet_routing_config")
        cfg.fleet_routing_enabled = lambda: True
        cfg.fleet_routing_force_enforce = lambda: True
        monkeypatch.setitem(sys.modules, "core.fleet_routing_config", cfg)
        _prepare_execute(agent, sl, monkeypatch, route_category=RouteCategory.ONE_OFF)
        agent.route_with_governance = AsyncMock(return_value={
            "specialists_count": 3, "chain_id": "chain-2", "status": "fleet_recruited",
        })
        seen = []

        async def cb(record):
            seen.append(record)

        result = await agent.execute("x" * 50, context={"user_id": "u1"}, step_callback=cb)
        assert result["status"] == "fleet_recruited"
        assert any(r.get("step_type") == "fleet_recruitment" for r in seen)

    @pytest.mark.asyncio
    async def test_single_action_failed_verification_critique(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._execute_tool_with_governance = AsyncMock(return_value="{\"ok\": false}")
        monkeypatch.setattr(ama, "parse_tool_outcome",
                            lambda obs: SimpleNamespace(kind="failed_verification",
                                                        evidence="mismatch"))
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="tool_a", params={})),
            ReActStep(thought="t", final_answer="done")])
        result = await agent.execute("hello")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_single_action_parse_exception(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._execute_tool_with_governance = AsyncMock(return_value="obs")
        monkeypatch.setattr(ama, "parse_tool_outcome",
                            lambda obs: (_ for _ in ()).throw(RuntimeError("parse fail")))
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="t", action=ToolCall(tool="tool_a", params={})),
            ReActStep(thought="t", final_answer="done")])
        result = await agent.execute("hello")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_parallel_tools_parse_exception_direct(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr("core.hallucination_config.is_parallel_tools_enabled",
                            lambda: True)
        monkeypatch.setattr("core.hallucination_config.get_max_parallel_tools",
                            lambda: 4)
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={
            "allowed": True, "action_complexity": 1,
        })
        monkeypatch.setattr(ama, "AgentGovernanceService", lambda db: gov)
        agent._execute_tool_with_governance = AsyncMock(return_value="obs")
        monkeypatch.setattr(ama, "parse_tool_outcome",
                            lambda obs: (_ for _ in ()).throw(RuntimeError("parse fail")))
        records = await agent._execute_parallel_tools(
            [ToolCall(tool="t1", params={})], {}, None)
        assert records[0]["verified_kind"] == "unverified"

    @pytest.mark.asyncio
    async def test_on_session_end_digest_with_output(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        monkeypatch.setattr(ama, "_TURN_FACT_EXTRACTION_ENABLED", True)
        _prepare_execute(agent, sl, monkeypatch)
        extractor = MagicMock()
        extractor.extract_from_turn = AsyncMock(return_value=None)
        monkeypatch.setattr(ama, "get_turn_fact_extractor", lambda **kw: extractor)
        agent._execute_tool_with_governance = AsyncMock(return_value="observation text")
        agent._react_step = AsyncMock(side_effect=[
            ReActStep(thought="think", action=ToolCall(tool="tool_a", params={})),
            ReActStep(thought="t2", final_answer="done")])
        result = await agent.execute("hello", context={"session_id": "s1", "user_id": "u1"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_body_exception_finalizer_db_error(self, meta_agent, monkeypatch):
        agent, sl = meta_agent
        _prepare_execute(agent, sl, monkeypatch)
        agent._react_step = AsyncMock(side_effect=RuntimeError("react crashed"))
        db = sl.db
        db.commit.side_effect = RuntimeError("finalize commit failed")
        sl.close = MagicMock(side_effect=RuntimeError("close failed"))
        with pytest.raises(RuntimeError):
            await agent.execute("hello")


# ============================================================================
# integrations.mcp_service — second-pass edge coverage
# ============================================================================


class TestMCPBrowserCloud:
    @pytest.fixture(autouse=True)
    def _neutralize_registry(self, monkeypatch):
        _no_registry(monkeypatch)

    def _enterprise_session(self):
        from core.models import PlanType
        ws = SimpleNamespace(tenant_id="t1")
        tenant = SimpleNamespace(plan_type=PlanType.ENTERPRISE)
        db = MagicMock()
        firsts = itertools.cycle([ws, tenant])

        def fake_query(model):
            q = Mock()
            q.filter.return_value.first.side_effect = lambda: next(firsts)
            return q

        db.query.side_effect = fake_query
        return _session_factory2(db)

    @pytest.mark.asyncio
    async def test_cloud_browser_all_tools(self, svc, monkeypatch):
        cloud = MagicMock()
        cloud.navigate = AsyncMock(return_value={"ok": True})
        cloud.click = AsyncMock(return_value={"ok": True})
        cloud.type_text = AsyncMock(return_value={"ok": True})
        cloud.screenshot = AsyncMock(return_value={"ok": True})
        cloud.new_tab = AsyncMock(return_value={"ok": True})
        cloud.switch_tab = AsyncMock(return_value={"ok": True})
        cloud.click_coords = AsyncMock(return_value={"ok": True})
        cloud.list_tabs = AsyncMock(return_value=[{"id": 1}])
        cloud.wait_for_selector = AsyncMock(return_value={"ok": True})
        cloud.save_session = AsyncMock(return_value={"ok": True})
        cloud.set_proxy = AsyncMock(return_value={"ok": True})
        cloud.start_monitoring = AsyncMock(return_value={"ok": True})
        cloud.stop_monitoring = AsyncMock(return_value={"ok": True})
        cloud.wait_for_selector = AsyncMock(return_value={"ok": True})
        cloud.extract_content = AsyncMock(return_value={"ok": True})
        cloud.upload_file = AsyncMock(return_value={"ok": True})
        cloud.download_file = AsyncMock(return_value={"ok": True})
        _fake_module(monkeypatch, "core.cloud_browser_service", cloud_browser=cloud)
        monkeypatch.setattr("core.database.SessionLocal", self._enterprise_session())
        ctx = {"computer_use_mode": "cloud", "workspace_id": "ws-1", "agent_id": "ag-1"}
        cases = [
            ("browser_navigate", {"url": "http://x"}, {"ok": True}),
            ("browser_click", {"selector": "#a"}, {"ok": True}),
            ("browser_type", {"text": "hi", "selector": "#b"}, {"ok": True}),
            ("browser_screenshot", {}, {"ok": True}),
            ("browser_new_tab", {"url": "http://y"}, {"ok": True}),
            ("browser_switch_tab", {"index": 1}, {"ok": True}),
            ("browser_click_coords", {"x": 10, "y": 20}, {"ok": True}),
            ("list_browser_tabs", {}, [{"id": 1}]),
            ("browser_save_session", {}, {"ok": True}),
            ("browser_set_proxy", {"server": "http://p"}, {"ok": True}),
            ("browser_monitor", {"active": True}, {"ok": True}),
            ("browser_wait_for_selector", {"selector": "#c"}, {"ok": True}),
            ("browser_extract_content", {"selector": "#d"}, {"ok": True}),
            ("browser_upload_file", {"selector": "#e", "file_path": "/tmp/f"}, {"ok": True}),
            ("browser_download_file", {"url": "http://f"}, {"ok": True}),
        ]
        for tool, args, expected in cases:
            result = await svc.execute_tool("local-tools", tool, args, ctx)
            assert result == expected, tool
        result = await svc.execute_tool(
            "local-tools", "browser_monitor", {"active": False}, ctx)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_browser_click_desktop_unsent(self, svc, monkeypatch):
        nm = MagicMock()
        nm.send_to_desktop = AsyncMock(return_value=False)
        monkeypatch.setattr("core.notification_manager.notification_manager", nm)
        result = await svc.execute_tool(
            "local-tools", "browser_click", {"selector": "#a", "x": 1, "y": 2}, {})
        assert "[SIMULATION] Clicked" in result

    @pytest.mark.asyncio
    async def test_browser_type_desktop_paths(self, svc, monkeypatch):
        nm = MagicMock()
        nm.send_to_desktop = AsyncMock(return_value=True)
        monkeypatch.setattr("core.notification_manager.notification_manager", nm)
        result = await svc.execute_tool(
            "local-tools", "browser_type", {"text": "hi", "selector": "#b"}, {})
        assert "Command sent to Desktop App: Type" in result
        nm.send_to_desktop = AsyncMock(return_value=False)
        result = await svc.execute_tool(
            "local-tools", "browser_type", {"text": "hi", "selector": "#b"}, {})
        assert "[SIMULATION] Typed" in result

    @pytest.mark.asyncio
    async def test_cloud_denied_messages(self, svc, monkeypatch):
        ws = SimpleNamespace(tenant_id="t1")
        tenant = SimpleNamespace(plan_type="free")
        db = MagicMock()
        firsts = itertools.cycle([ws, tenant])

        def fake_query(model):
            q = Mock()
            q.filter.return_value.first.side_effect = lambda: next(firsts)
            return q

        db.query.side_effect = fake_query
        monkeypatch.setattr("core.database.SessionLocal", _session_factory2(db))
        ctx = {"computer_use_mode": "cloud", "workspace_id": "ws-1"}
        tools = [
            "browser_navigate", "browser_click", "browser_type",
            "browser_screenshot", "browser_new_tab", "browser_switch_tab",
            "browser_click_coords", "list_browser_tabs", "browser_save_session",
            "browser_set_proxy", "browser_monitor", "browser_wait_for_selector",
            "browser_extract_content", "browser_upload_file", "browser_download_file",
        ]
        for tool in tools:
            result = await svc.execute_tool("local-tools", tool, {}, ctx)
            assert "Enterprise" in result or "restricted" in result, tool

    @pytest.mark.asyncio
    async def test_search_tasks_provider_failure(self, svc, monkeypatch):
        cls = MagicMock()
        inst = MagicMock()
        inst.search = AsyncMock(side_effect=RuntimeError("down"))
        cls.return_value = inst
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool("local-tools", "search_tasks", {"query": "q"}, {})
        assert result == {}

    @pytest.mark.asyncio
    async def test_unified_knowledge_search_empty_query(self, svc, monkeypatch):
        engine = MagicMock()
        entity = SimpleNamespace(
            canonical_name="Vendor Acme",
            entity_id="e1",
            entity_type=SimpleNamespace(value="vendor"),
            source_platforms=[SimpleNamespace(value="quickbooks")],
            updated_at=datetime(2026, 1, 1),
        )
        engine.entity_registry = {"e1": entity}
        monkeypatch.setattr("ai.data_intelligence.DataIntelligenceEngine", MagicMock(return_value=engine))
        result = await svc.execute_tool("local-tools", "unified_knowledge_search",
                                        {"query": "vendor"}, {})
        assert result[0]["id"] == "e1"

    @pytest.mark.asyncio
    async def test_ingest_knowledge_file_with_formulas(self, svc, monkeypatch):
        processor = MagicMock()
        processor.process_document = AsyncMock(return_value={
            "success": True, "content": "text content", "page_count": 1,
            "total_chars": 100, "tables": [],
        })
        ingestion = MagicMock()
        ingestion.process_document = AsyncMock(return_value={"docs": 1})
        extractor = MagicMock()
        extractor.extract_from_file = MagicMock(return_value=[
            {"name": "f1", "expression": "=1+1", "domain": "finance"}])
        _fake_module(monkeypatch, "core.docling_processor",
                     get_docling_processor=lambda: processor)
        _fake_module(monkeypatch, "core.knowledge_ingestion",
                     get_knowledge_ingestion=lambda: ingestion)
        _fake_module(monkeypatch, "core.formula_extractor",
                     get_formula_extractor=lambda ws: extractor)
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: True)
        monkeypatch.setattr("integrations.mcp_service.os.path.splitext",
                            lambda p: (p, ".xlsx"))
        result = await svc.execute_tool(
            "local-tools", "ingest_knowledge_from_file",
            {"file_path": "/tmp/book.xlsx"}, {})
        assert result["success"] is True
        assert result["extracted_formulas"][0]["name"] == "f1"

    @pytest.mark.asyncio
    async def test_ingest_knowledge_file_formula_failure(self, svc, monkeypatch):
        processor = MagicMock()
        processor.process_document = AsyncMock(return_value={
            "success": True, "content": "text", "page_count": 1,
            "total_chars": 50, "tables": [],
        })
        ingestion = MagicMock()
        ingestion.process_document = AsyncMock(return_value={"docs": 1})
        _fake_module(monkeypatch, "core.docling_processor",
                     get_docling_processor=lambda: processor)
        _fake_module(monkeypatch, "core.knowledge_ingestion",
                     get_knowledge_ingestion=lambda: ingestion)
        _fake_module(monkeypatch, "core.formula_extractor",
                     get_formula_extractor=lambda ws: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: True)
        monkeypatch.setattr("integrations.mcp_service.os.path.splitext",
                            lambda p: (p, ".xlsx"))
        result = await svc.execute_tool(
            "local-tools", "ingest_knowledge_from_file",
            {"file_path": "/tmp/book.xlsx"}, {})
        assert result["success"] is True

    def test_permission_cache_init_path(self, svc, monkeypatch):
        skill_service = MagicMock()
        skill_service.check_skill_permission.return_value = {"allowed": True, "reason": "ok"}
        monkeypatch.setattr("core.entity_skill_service.get_entity_skill_service",
                            lambda: skill_service)
        monkeypatch.setattr("core.database.SessionLocal", _session_factory2(MagicMock()))
        if hasattr(svc, "_permission_cache"):
            del svc._permission_cache
        result = svc.check_entity_skill_permission("t1", "vendor", "sk-2")
        assert result["allowed"] is True
        assert any("sk-2" in k for k in svc._permission_cache)


# ============================================================================
# integrations.mcp_service
# ============================================================================

import integrations.mcp_service as mcp_mod
from integrations.mcp_service import MCPService


@pytest.fixture
def svc():
    return MCPService()


def _no_registry(monkeypatch):
    reg = MagicMock()
    reg.get.return_value = None
    monkeypatch.setattr("integrations.mcp_service.get_tool_registry", lambda: reg)


def _fake_module(monkeypatch, name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


def _session_factory2(db):
    class _Ctx:
        def __enter__(self):
            return db

        def __exit__(self, *a):
            return False

    return lambda: _Ctx()


def _q_first(value=None, all_value=None):
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = value
    q.all.return_value = all_value
    return q


class TestMCPExecuteIntegrationTool:
    @pytest.mark.asyncio
    async def test_invalid_format_no_underscore(self, svc):
        result = await svc.execute_integration_tool("badtool", {}, {"tenant_id": "t", "agent_id": "a"})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_missing_tenant_or_agent(self, svc):
        result = await svc.execute_integration_tool("conn_op", {}, {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_delegates_to_universal(self, svc, monkeypatch):
        cls = MagicMock()
        inst = MagicMock()
        inst.execute = AsyncMock(return_value={"status": "success", "data": []})
        cls.return_value = inst
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_integration_tool(
            "salesforce_create", {"a": 1},
            {"tenant_id": "t", "agent_id": "a", "user_id": "u", "workspace_id": "w"})
        assert result["status"] == "success"
        inst.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_error(self, svc, monkeypatch):
        cls = MagicMock()
        inst = MagicMock()
        inst.execute = AsyncMock(side_effect=RuntimeError("boom"))
        cls.return_value = inst
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_integration_tool(
            "conn_op", {}, {"tenant_id": "t", "agent_id": "a"})
        assert result["status"] == "error"


class TestMCPLocalToolsExtra:
    @pytest.fixture(autouse=True)
    def _neutralize_registry(self, monkeypatch):
        _no_registry(monkeypatch)

    @pytest.mark.asyncio
    async def test_collaboration_hub_tools(self, svc, monkeypatch):
        hub = MagicMock()
        hub.update_ai_analysis = MagicMock(return_value={"ok": True})
        hub.save_draft_response = MagicMock(return_value={"ok": True})
        hub.approve_draft = AsyncMock(return_value={"ok": True})
        _fake_module(monkeypatch, "core.collaboration_hub_service",
                     get_collaboration_hub_service=lambda db: hub)
        monkeypatch.setattr("core.database.SessionLocal", _session_factory2(MagicMock()))
        result = await svc.execute_tool("local-tools", "analyze_message",
                                        {"message_id": "m1", "analysis": {}}, {})
        assert result == {"ok": True}
        result = await svc.execute_tool("local-tools", "draft_response",
                                        {"message_id": "m1", "content": "c"}, {})
        assert result == {"ok": True}
        result = await svc.execute_tool("local-tools", "approve_draft",
                                        {"message_id": "m1", "edited_content": "c"}, {})
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_collaboration_hub_import_error(self, svc, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.collaboration_hub_service", None)
        result = await svc.execute_tool("local-tools", "analyze_message", {}, {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_ingest_message_attachment(self, svc):
        result = await svc.execute_tool("local-tools", "ingest_message_attachment",
                                        {"file_name": "f.pdf"}, {})
        assert "Successfully ingested" in result

    @pytest.mark.asyncio
    async def test_unified_knowledge_search_query_skip(self, svc, monkeypatch):
        engine = MagicMock()
        entity = SimpleNamespace(
            canonical_name="Vendor Acme",
            entity_id="e1",
            entity_type=SimpleNamespace(value="vendor"),
            source_platforms=[SimpleNamespace(value="quickbooks")],
            updated_at=datetime(2026, 1, 1),
        )
        engine.entity_registry = {"e1": entity}
        monkeypatch.setattr("ai.data_intelligence.DataIntelligenceEngine", MagicMock(return_value=engine))
        result = await svc.execute_tool("local-tools", "unified_knowledge_search",
                                        {"query": "zzz-no-match"}, {})
        assert result == []

    @pytest.mark.asyncio
    async def test_verify_citation_path_denied(self, svc):
        result = await svc.execute_tool("local-tools", "verify_citation",
                                        {"path": "/etc/passwd"}, {})
        assert "Access denied" in result

    @pytest.mark.asyncio
    async def test_verify_citation_missing_and_exists(self, svc, monkeypatch):
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: False)
        result = await svc.execute_tool("local-tools", "verify_citation",
                                        {"path": "/tmp/nope.txt"}, {})
        assert "NOT found" in result
        monkeypatch.setattr("integrations.mcp_service.os.path.exists", lambda p: True)
        from unittest.mock import mock_open
        monkeypatch.setattr("builtins.open", mock_open(read_data="snippet"))
        result = await svc.execute_tool("local-tools", "verify_citation",
                                        {"path": "/tmp/x.txt"}, {})
        assert "Verified" in result

    @pytest.mark.asyncio
    async def test_create_ticket(self, svc, monkeypatch):
        cls, inst = _fake_universal("create")
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool("local-tools", "create_ticket",
                                        {"platform": "zendesk"}, {})
        assert result == {"created": 1}
        result = await svc.execute_tool("local-tools", "create_ticket", {}, {})
        assert result["error"] == "platform is required"

    @pytest.mark.asyncio
    async def test_get_inventory_levels_zoho(self, svc, monkeypatch):
        conn = MagicMock()
        conn.piece_name = "zoho_inventory"
        conn.credentials = {"access_token": "t"}
        conn.metadata = {"organization_id": "org1"}
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[conn])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        zoho = MagicMock()
        zoho.get_inventory_levels = AsyncMock(return_value=[{"item_id": "i1"}])
        monkeypatch.setattr("integrations.zoho_inventory_service.zoho_inventory_service", zoho)
        result = await svc.execute_tool("local-tools", "get_inventory_levels", {}, {})
        assert result == [{"item_id": "i1"}]

    @pytest.mark.asyncio
    async def test_sales_agent_tools(self, svc, monkeypatch):
        agent = MagicMock()
        agent.score_lead = AsyncMock(return_value={"score": 80})
        agent.prepare_outreach = AsyncMock(return_value={"draft": "hi"})
        agent.audit_pipeline = AsyncMock(return_value={"warnings": []})
        _fake_module(monkeypatch, "core.sales_agent", SalesAgent=lambda: agent)
        result = await svc.execute_tool("local-tools", "score_lead", {"lead_data": {}}, {"workspace_id": "w"})
        assert result == {"score": 80}
        result = await svc.execute_tool("local-tools", "draft_sales_outreach", {}, {"workspace_id": "w"})
        assert result == {"draft": "hi"}
        result = await svc.execute_tool("local-tools", "monitor_pipeline_health", {}, {"workspace_id": "w"})
        assert result == {"warnings": []}

    @pytest.mark.asyncio
    async def test_sales_agent_import_error(self, svc, monkeypatch):
        monkeypatch.setitem(sys.modules, "core.sales_agent", None)
        result = await svc.execute_tool("local-tools", "score_lead", {}, {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_search_tasks_no_platform(self, svc, monkeypatch):
        cls, inst = _fake_universal("search", search_result={"found": []})
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool("local-tools", "search_tasks", {"query": "q"}, {})
        assert result["jira"] == {"found": []}

    @pytest.mark.asyncio
    async def test_get_sales_pipeline_hubspot_failure(self, svc, monkeypatch):
        cls = MagicMock()
        inst = MagicMock()
        inst.execute = AsyncMock(side_effect=RuntimeError("sf down"))
        cls.return_value = inst
        monkeypatch.setattr("integrations.universal_integration_service.UniversalIntegrationService", cls)
        result = await svc.execute_tool("local-tools", "get_sales_pipeline", {}, {"user_id": "u"})
        assert result == []

    @pytest.mark.asyncio
    async def test_whatsapp_list_templates_exception(self, svc, monkeypatch):
        conn = MagicMock()
        conn.integration_id = "whatsapp"
        conn.credentials = {"access_token": "t", "waba_id": "w1"}
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[conn])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        monkeypatch.setattr("httpx.AsyncClient", MagicMock(
            side_effect=RuntimeError("net down")))
        result = await svc.execute_tool("local-tools", "whatsapp_list_templates", {}, {})
        assert "Failed to list WhatsApp templates" in result["error"]

    @pytest.mark.asyncio
    async def test_whatsapp_list_templates_no_conn(self, svc, monkeypatch):
        conn_cls = MagicMock()
        conn_cls.return_value.list_connections = AsyncMock(return_value=[])
        monkeypatch.setattr("core.connection_service.ConnectionService", conn_cls)
        result = await svc.execute_tool("local-tools", "whatsapp_list_templates", {}, {})
        assert result["error"] == "WhatsApp Business not connected."

    @pytest.mark.asyncio
    async def test_entity_permission_cache_initialized(self, svc, monkeypatch):
        skill_service = MagicMock()
        skill_service.check_skill_permission.return_value = {"allowed": True, "reason": "ok"}
        monkeypatch.setattr("core.entity_skill_service.get_entity_skill_service",
                            lambda: skill_service)
        monkeypatch.setattr("core.database.SessionLocal", _session_factory2(MagicMock()))
        result = svc.check_entity_skill_permission("t1", "vendor", "sk-1")
        assert result["allowed"] is True
        assert hasattr(svc, "_permission_cache")

    @pytest.mark.asyncio
    async def test_entity_permission_cache_hit(self, svc, monkeypatch):
        svc._permission_cache = {"t1:vendor:sk-1": (10**20, {"allowed": False})}
        result = svc.check_entity_skill_permission("t1", "vendor", "sk-1")
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_entity_permission_error(self, svc, monkeypatch):
        monkeypatch.setattr("core.entity_skill_service.get_entity_skill_service",
                            lambda: (_ for _ in ()).throw(RuntimeError("svc down")))
        result = svc.check_entity_skill_permission("t1", "vendor", "sk-1")
        assert result["allowed"] is False


def _fake_universal(action, execute_result=None, search_result=None):
    inst = MagicMock()
    if action == "create":
        inst.execute = AsyncMock(return_value={"created": 1})
    if action == "search":
        inst.search = AsyncMock(return_value=search_result or {"found": []})
    cls = MagicMock(return_value=inst)
    return cls, inst
