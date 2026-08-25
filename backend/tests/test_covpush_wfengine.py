"""Coverage-push + bug-hunt tests for the workflow execution stack.

Modules under test (TDD: failing tests first, then minimal fixes):
- core.workflow_engine
- core.workflow_debugger
- core.workflow_analytics_engine
- core.workflow_versioning_system
"""

import asyncio
import json
import os
os.environ["TESTING"] = "1"

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.database import Base
from core.models import (
    DebugVariable,
    ExecutionTrace,
    User,
    WorkflowBreakpoint,
    WorkflowDebugSession,
    WorkflowExecution,
)
from core.workflow_analytics_engine import (
    Alert,
    AlertSeverity,
    MetricType,
    PerformanceMetrics,
    WorkflowAnalyticsEngine,
    WorkflowStatus,
)
from core.workflow_debugger import WorkflowDebugger
from core.workflow_engine import (
    MissingInputError,
    SchemaValidationError,
    StepTimeoutError,
    WorkflowEngine,
    get_workflow_engine,
)
from core.exceptions import AgentExecutionError
from core.workflow_versioning_system import (
    ChangeType,
    VersionType,
    WorkflowVersion,
    WorkflowVersioningSystem,
    WorkflowVersionManager,
)

NO_RETRY = lambda fn: fn


# ============================================================================
# Shared fakes for the workflow engine
# ============================================================================

class FakeStateManager:
    """In-memory stand-in for ExecutionStateManager (same async interface)."""

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

    def track_step_execution(self, **kw):
        self.calls.append(("step", kw))

    def track_workflow_execution(self, **kw):
        self.calls.append(("workflow", kw))


class FakeServiceFactory:
    @staticmethod
    def get_governance_service(db, tenant_id="default"):
        svc = MagicMock()
        svc.can_perform_action = AsyncMock(return_value=(True, "ok"))
        return svc


@pytest.fixture
def engine_env(monkeypatch):
    """Patch engine globals: state manager, ws manager, analytics, notifier,
    governance, event bus, and strip the retry wrapper for speed."""
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
    monkeypatch.setattr("core.workflow_engine.ServiceFactory", FakeServiceFactory)
    bus = MagicMock()
    monkeypatch.setattr("core.orchestration.event_bus.get_event_bus", lambda: bus)

    engine = WorkflowEngine()
    engine._execute_step = engine._execute_step.__wrapped__.__get__(engine, WorkflowEngine)  # no retries
    return {"sm": sm, "ws": ws, "analytics": analytics, "notifier": notifier, "engine": engine, "bus": bus}


def _step(sid, service="email", action="send", params=None, **kw):
    s = {"id": sid, "service": service, "action": action, "parameters": params or {}}
    s.update(kw)
    return s


def _workflow(steps, **kw):
    wf = {"id": "wf-1", "name": "Test WF", "steps": steps, "created_by": "user-1"}
    wf.update(kw)
    return wf


def _node_workflow(nodes, connections=None, **kw):
    wf = {"id": "wf-g", "name": "Graph WF", "nodes": nodes, "connections": connections or []}
    wf.update(kw)
    return wf


# ============================================================================
# workflow_engine — pure helpers
# ============================================================================

class TestConvertNodesToSteps:
    def test_basic_conversion(self):
        eng = WorkflowEngine()
        steps = eng._convert_nodes_to_steps(_node_workflow([
            {"id": "a", "title": "A", "type": "action", "config": {"service": "s", "action": "x", "parameters": {"p": 1}}},
            {"id": "b", "title": "B", "type": "trigger", "config": {"action": "manual_trigger"}},
        ], [{"source": "a", "target": "b"}]))
        assert [s["id"] for s in steps] == ["a", "b"]
        assert steps[0]["sequence_order"] == 1
        assert steps[1]["type"] == "trigger"
        assert steps[1]["action"] == "manual_trigger"

    def test_malformed_connection_skipped(self):
        eng = WorkflowEngine()
        steps = eng._convert_nodes_to_steps(_node_workflow([
            {"id": "a", "config": {}},
            {"id": "b", "config": {}},
        ], [{"source": "a"}, {"target": "b"}, {"source": "ghost", "target": "a"}]))
        assert [s["id"] for s in steps] == ["a", "b"]

    def test_cycle_raises_value_error(self):
        eng = WorkflowEngine()
        with pytest.raises(ValueError, match="circular"):
            eng._convert_nodes_to_steps(_node_workflow([
                {"id": "a", "config": {}},
                {"id": "b", "config": {}},
            ], [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]))

    def test_empty_nodes(self):
        eng = WorkflowEngine()
        assert eng._convert_nodes_to_steps(_node_workflow([])) == []

    def test_nodes_without_connections(self):
        eng = WorkflowEngine()
        steps = eng._convert_nodes_to_steps(_node_workflow([
            {"id": "a", "config": {}}, {"id": "b", "config": {}}
        ]))
        assert len(steps) == 2


class TestBuildExecutionGraph:
    def test_graph_structure(self):
        eng = WorkflowEngine()
        g = eng._build_execution_graph(_node_workflow([
            {"id": "a", "config": {}}, {"id": "b", "config": {}},
        ], [{"source": "a", "target": "b", "condition": "${a.ok}"}]))
        assert set(g["nodes"]) == {"a", "b"}
        assert g["adjacency"]["a"][0]["target"] == "b"
        assert g["reverse_adjacency"]["b"][0]["source"] == "a"

    def test_unknown_node_connection_ignored(self):
        eng = WorkflowEngine()
        g = eng._build_execution_graph(_node_workflow([
            {"id": "a", "config": {}}
        ], [{"source": "a", "target": "missing"}]))
        assert g["adjacency"]["a"] == []


class TestConditionEvaluation:
    def test_no_condition_returns_true(self):
        eng = WorkflowEngine()
        assert eng._has_conditional_connections({"connections": [{"source": "a", "target": "b"}]}) is False
        assert eng._has_conditional_connections({"connections": [{"condition": ""}]}) is False
        assert eng._has_conditional_connections({"connections": [{"condition": "${a} > 1"}]}) is True

    def test_evaluate_true_expression(self):
        eng = WorkflowEngine()
        state = {"outputs": {"step1": {"count": 7}}, "input_data": {"x": 3}}
        assert eng._evaluate_condition("${step1.count} > 5", state) is True

    def test_evaluate_false_expression(self):
        eng = WorkflowEngine()
        state = {"outputs": {"step1": {"count": 2}}}
        assert eng._evaluate_condition("${step1.count} > 5", state) is False

    def test_missing_variable_is_false(self):
        eng = WorkflowEngine()
        assert eng._evaluate_condition("${ghost.value} == 1", {"outputs": {}}) is False

    def test_string_comparison(self):
        eng = WorkflowEngine()
        state = {"outputs": {"step1": {"status": "completed"}}}
        assert eng._evaluate_condition("${step1.status} == 'completed'", state) is True

    def test_code_injection_blocked(self):
        eng = WorkflowEngine()
        assert eng._evaluate_condition("__import__('os').system('id')", {}) is False
        assert eng._evaluate_condition("${a.__class__.__base__} == 1", {"outputs": {"a": {}}}) is False


class TestResolveParameters:
    def test_passthrough_non_string(self):
        eng = WorkflowEngine()
        assert eng._resolve_parameters({"n": 5, "b": True}, {}) == {"n": 5, "b": True}

    def test_pure_reference_preserves_type(self):
        eng = WorkflowEngine()
        state = {"outputs": {"s1": {"n": 42}}}
        assert eng._resolve_parameters({"x": "${s1.n}"}, state) == {"x": 42}

    def test_interpolation_multiple_vars(self):
        eng = WorkflowEngine()
        state = {"input_data": {"name": "Ada"}, "outputs": {"s1": {"n": 7}}}
        assert eng._resolve_parameters({"msg": "Hello ${input.name} #${s1.n}!"}, state) == \
            {"msg": "Hello Ada #7!"}

    def test_missing_variable_raises(self):
        eng = WorkflowEngine()
        with pytest.raises(MissingInputError) as ei:
            eng._resolve_parameters({"x": "${missing.key}"}, {"input_data": {}})
        assert ei.value.missing_var == "missing.key"

    def test_get_value_from_path(self):
        eng = WorkflowEngine()
        state = {"input_data": {"a": {"b": 1}}, "outputs": {"s1": {"deep": {"v": "x"}}}}
        assert eng._get_value_from_path("input.a.b", state) == 1
        assert eng._get_value_from_path("s1.deep.v", state) == "x"
        assert eng._get_value_from_path("s1.missing", state) is None
        assert eng._get_value_from_path("ghost.x", state) is None


class TestSchemaValidation:
    def test_no_schema_passes(self):
        eng = WorkflowEngine()
        assert eng._validate_input_schema({"id": "s"}, {}) is None
        assert eng._validate_output_schema({"id": "s"}, {}) is None

    def test_valid_schema_passes(self):
        eng = WorkflowEngine()
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}
        assert eng._validate_input_schema({"id": "s", "input_schema": schema}, {"x": 1}) is None

    def test_invalid_input_raises(self):
        eng = WorkflowEngine()
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}
        with pytest.raises(SchemaValidationError) as ei:
            eng._validate_input_schema({"id": "s", "input_schema": schema}, {})
        assert ei.value.schema_type == "input"

    def test_invalid_output_raises(self):
        eng = WorkflowEngine()
        schema = {"type": "object", "properties": {"y": {"type": "string"}}}
        with pytest.raises(SchemaValidationError) as ei:
            eng._validate_output_schema({"id": "s", "output_schema": schema}, {"y": 1})
        assert ei.value.schema_type == "output"

    def test_errors_attr_defaults(self):
        assert SchemaValidationError("m", "input").errors == []


class TestDependencies:
    def test_dependencies_met(self):
        eng = WorkflowEngine()
        state = {"steps": {"s1": {"status": "COMPLETED"}}}
        assert eng._check_dependencies({"depends_on": ["s1"]}, state) is True

    def test_dependencies_not_met(self):
        eng = WorkflowEngine()
        state = {"steps": {"s1": {"status": "FAILED"}}}
        assert eng._check_dependencies({"depends_on": ["s1"]}, state) is False

    def test_no_dependencies(self):
        eng = WorkflowEngine()
        assert eng._check_dependencies({"depends_on": []}, state={}) is True


# ============================================================================
# workflow_engine — step execution
# ============================================================================

class TestExecuteStep:
    async def _exec(self, engine_env, step, params=None):
        return await engine_env["engine"]._execute_step(step, params or {})

    def test_registry_service_success(self, engine_env):
        async def run():
            out = await self._exec(engine_env, _step("s1", service="email", action="send"))
            assert out["status"] == "success"
            assert out["execution_method"] == "service_registry"
        asyncio.run(run())

    def test_generic_executor_unknown_service(self, engine_env):
        async def run():
            with patch.object(engine_env["engine"], "_execute_generic_action",
                              new=AsyncMock(return_value={"ok": True})):
                out = await self._exec(engine_env, _step("s1", service="custom_thing", action="go"))
                assert out["execution_method"] == "generic_catalog_executor"
        asyncio.run(run())

    def test_unknown_service_no_fallback_raises(self, engine_env):
        async def run():
            with pytest.raises(ValueError):
                await self._exec(engine_env, _step("s1", service="no_such_service", action="go"))
        asyncio.run(run())

    def test_fallback_service_used(self, engine_env):
        async def run():
            step = _step("s1", service="slack", action="chat_postMessage",
                         fallback_service="email", parameters={"channel": "c", "text": "t"})
            out = await self._exec(engine_env, step)
            assert out["fallback_used"] is True
            assert out["service"] == "email"
        asyncio.run(run())

    def test_primary_and_fallback_fail_raises(self, engine_env):
        async def run():
            step = _step("s1", service="slack", action="chat_postMessage", fallback_service="stripe")
            with patch("core.workflow_engine.HAS_STRIPE", False):
                with pytest.raises(ValueError, match="also failed"):
                    await self._exec(engine_env, step)
        asyncio.run(run())

    def test_timeout_raises_step_timeout_error(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            async def slow(action, params, connection_id=None):
                await asyncio.sleep(5)
            engine._execute_email_action = slow
            step = _step("s1", service="email", action="send", timeout=0.05)
            with pytest.raises(StepTimeoutError) as ei:
                await self._exec(engine_env, step)
            assert ei.value.step_id == "s1"
        asyncio.run(run())

    def test_fallback_timeout_raises(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            async def slow(action, params, connection_id=None):
                await asyncio.sleep(5)
            engine._execute_email_action = slow
            step = _step("s1", service="slack", action="chat_postMessage",
                         fallback_service="email", timeout=0.05)
            with pytest.raises(Exception, match="timed out"):
                await self._exec(engine_env, step)
        asyncio.run(run())

    def test_status_error_dict_fails_step(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            async def err(action, params, connection_id=None):
                return {"status": "error", "error": "boom"}
            engine._execute_email_action = err
            step = _step("s1", service="email", action="send")
            with pytest.raises(Exception, match="boom"):
                await self._exec(engine_env, step)
        asyncio.run(run())

    def test_ai_service_executes_without_type_error(self, engine_env):
        """BUG: 2-arg executors were called with a 3rd positional arg."""
        async def run():
            out = await self._exec(engine_env, _step("s1", service="ai", action="summarize"))
            assert out["status"] == "success"
            assert out["execution_method"] == "service_registry"
        asyncio.run(run())

    def test_calendar_database_webhook_services_work(self, engine_env):
        async def run():
            for svc in ("calendar", "database", "webhook"):
                out = await self._exec(engine_env, _step("s1", service=svc, action="run"))
                assert out["status"] == "success", svc
        asyncio.run(run())

    def test_mcp_service_error_surfaces_as_failure(self, engine_env):
        async def run():
            with pytest.raises(Exception, match="MCP action failed"):
                await self._exec(engine_env, _step("s1", service="mcp", action="do"))
        asyncio.run(run())

    def test_email_automation_unknown_action_raises(self, engine_env):
        async def run():
            with pytest.raises(Exception, match="Unknown email_automation action"):
                await self._exec(engine_env, _step("s1", service="email_automation", action="nope"))
        asyncio.run(run())

    def test_email_automation_draft_nudge(self, engine_env):
        async def run():
            out = await self._exec(engine_env, _step("s1", service="email_automation", action="draft_nudge"))
            assert out["status"] == "success"
            assert "Following up" in out["result"]["draft"]
        asyncio.run(run())

    def test_gmail_no_token_raises_auth_error(self, engine_env):
        async def run():
            step = _step("s1", service="gmail", action="send_email", params={"to": "a@b.c"})
            with pytest.raises(Exception) as ei:
                await self._exec(engine_env, step)
            assert "authentication" in str(ei.value).lower() or "Authentication" in str(ei.value)
        asyncio.run(run())

    def test_slack_unsupported_action_raises(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token",
                       return_value={"access_token": "x"}):
                step = _step("s1", service="slack", action="totally_unknown", connection_id="c1")
                with pytest.raises(ValueError, match="Unsupported Slack action"):
                    await self._exec(engine_env, step)
        asyncio.run(run())

    def test_outlook_unknown_action_raises(self, engine_env):
        async def run():
            with pytest.raises(ValueError, match="Unknown Outlook action"):
                await self._exec(engine_env, _step("s1", service="outlook", action="nope"))
        asyncio.run(run())

    def test_jira_unknown_action_raises(self, engine_env):
        async def run():
            with pytest.raises(ValueError, match="Unknown Jira action"):
                await self._exec(engine_env, _step("s1", service="jira", action="nope"))
        asyncio.run(run())

    def test_trello_unknown_action_raises(self, engine_env):
        async def run():
            with pytest.raises(ValueError, match="Unknown Trello action"):
                await self._exec(engine_env, _step("s1", service="trello", action="nope"))
        asyncio.run(run())

    def test_zoho_unknown_action_raises(self, engine_env):
        async def run():
            for svc in ("zoho_crm", "zoho_books", "zoho_inventory"):
                with pytest.raises(ValueError, match="Unknown"):
                    await self._exec(engine_env, _step("s1", service=svc, action="nope"))
        asyncio.run(run())

    def test_shopify_unknown_action_raises(self, engine_env):
        async def run():
            with pytest.raises(ValueError, match="Unknown Shopify action"):
                await self._exec(engine_env, _step("s1", service="shopify", action="nope"))
        asyncio.run(run())

    def test_goal_management_unknown_action_raises(self, engine_env):
        async def run():
            with pytest.raises(ValueError, match="Unknown goal_management action"):
                await self._exec(engine_env, _step("s1", service="goal_management", action="nope"))
        asyncio.run(run())

    def test_stripe_unavailable_raises(self, engine_env):
        async def run():
            with patch("core.workflow_engine.HAS_STRIPE", False):
                with pytest.raises(Exception):
                    await self._exec(engine_env, _step("s1", service="stripe", action="x"))
        asyncio.run(run())


class TestExecuteAgentWithMcp:
    def test_agent_execution_without_db_crash(self, engine_env):
        """BUG: _execute_agent_with_mcp referenced self.db which was never set."""
        async def run():
            engine = engine_env["engine"]
            out = await engine._execute_agent_with_mcp({
                "action": "do", "input_data": {}, "mcp_connections": {},
                "available_tools": [], "agent_id": "agent-xyz",
            })
            assert out.get("success") is False
        asyncio.run(run())

    def test_agent_not_found_returns_error(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            out = await engine._execute_agent_with_mcp({
                "action": "do", "input_data": {}, "mcp_connections": {},
                "available_tools": [], "agent_id": None,
            })
            assert out.get("success") is False
        asyncio.run(run())


class TestExecuteWorkflowAction:
    def test_missing_workflow_id(self, engine_env):
        async def run():
            out = await engine_env["engine"]._execute_workflow_action("run", {})
            assert out["status"] == "error"
        asyncio.run(run())

    def test_subworkflow_completes(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            engine._load_workflow_by_id = lambda wid: {"id": wid, "steps": []}
            async def fake_start(wf, data):
                return "sub-exec"
            engine.start_workflow = fake_start
            async def fake_state(eid):
                return {"status": "COMPLETED", "outputs": {"x": 1}}
            engine.state_manager.get_execution_state = fake_state
            out = await engine._execute_workflow_action("run", {"workflow_id": "wf-sub"})
            assert out["status"] == "success"
            assert out["execution_id"] == "sub-exec"
        asyncio.run(run())

    def test_subworkflow_fails(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            engine._load_workflow_by_id = lambda wid: {"id": wid, "steps": []}
            async def fake_start(wf, data):
                return "sub-exec"
            engine.start_workflow = fake_start
            async def fake_state(eid):
                return {"status": "FAILED", "error": "nope"}
            engine.state_manager.get_execution_state = fake_state
            out = await engine._execute_workflow_action("run", {"workflow_id": "wf-sub"})
            assert out["status"] == "error"
        asyncio.run(run())

    def test_subworkflow_cancelled_and_paused(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            engine._load_workflow_by_id = lambda wid: {"id": wid, "steps": []}
            engine.start_workflow = AsyncMock(return_value="sub-exec")
            statuses = iter(["CANCELLED", "PAUSED"])
            async def fake_state(eid):
                return {"status": next(statuses)}
            engine.state_manager.get_execution_state = fake_state
            out = await engine._execute_workflow_action("run", {"workflow_id": "wf-sub"})
            assert out["status"] == "cancelled"
            out = await engine._execute_workflow_action("run", {"workflow_id": "wf-sub"})
            assert out["status"] == "paused"
        asyncio.run(run())

    def test_subworkflow_timeout(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            engine._load_workflow_by_id = lambda wid: {"id": wid, "steps": []}
            engine.start_workflow = AsyncMock(return_value="sub-exec")
            engine.state_manager.get_execution_state = AsyncMock(return_value={"status": "RUNNING"})
            out = await engine._execute_workflow_action("run", {"workflow_id": "wf-sub", "timeout": 0.05})
            assert out["status"] == "timeout"
        asyncio.run(run())

    def test_load_workflow_by_id(self, engine_env, tmp_path, monkeypatch):
        workflows_file = tmp_path / "workflows.json"
        workflows_file.write_text(json.dumps([{"id": "w1", "steps": []}, {"id": "w2", "steps": []}]))
        monkeypatch.setattr("core.workflow_engine.os.path.dirname", lambda p: str(tmp_path))
        with patch("core.workflow_engine.os.path.exists", return_value=True), \
             patch("builtins.open", return_value=open(str(workflows_file))):
            wf = engine_env["engine"]._load_workflow_by_id("w2")
        assert wf["id"] == "w2"

    def test_load_workflow_by_id_missing_file(self, engine_env, tmp_path, monkeypatch):
        monkeypatch.setattr("core.workflow_engine.os.path.dirname", lambda p: str(tmp_path))
        with patch("core.workflow_engine.os.path.exists", return_value=False):
            assert engine_env["engine"]._load_workflow_by_id("w1") is None


# ============================================================================
# workflow_engine — lifecycle
# ============================================================================

class TestWorkflowLifecycle:
    def test_start_workflow_background_tasks(self, engine_env):
        async def run():
            tasks = MagicMock()
            eid = await engine_env["engine"].start_workflow(_workflow([]), {"a": 1}, tasks)
            tasks.add_task.assert_called_once()
            assert engine_env["sm"].executions[eid]["status"] == "PENDING"
        asyncio.run(run())

    def test_start_workflow_normalizes_workflow_id_key(self, engine_env):
        async def run():
            tasks = MagicMock()
            wf = {"workflow_id": "wf-x", "steps": [], "name": "n"}
            eid = await engine_env["engine"].start_workflow(wf, {}, tasks)
            assert wf["id"] == "wf-x"
            assert engine_env["sm"].executions[eid]["workflow_id"] == "wf-x"
        asyncio.run(run())

    def test_resume_workflow(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            eid = await engine.state_manager.create_execution("wf", {})
            await engine.state_manager.update_execution_status(eid, "PAUSED")
            assert await engine.resume_workflow(eid, _workflow([]), {"x": 2}) is True
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "RUNNING"
            assert state["input_data"]["x"] == 2
        asyncio.run(run())

    def test_resume_workflow_not_found(self, engine_env):
        async def run():
            with pytest.raises(ValueError):
                await engine_env["engine"].resume_workflow("missing", {}, {})
        asyncio.run(run())

    def test_resume_workflow_not_paused(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            eid = await engine.state_manager.create_execution("wf", {})
            assert await engine.resume_workflow(eid, _workflow([]), {}) is False
        asyncio.run(run())

    def test_cancel_execution(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            eid = await engine.state_manager.create_execution("wf", {})
            assert await engine.cancel_execution(eid) is True
            assert eid in engine.cancellation_requests
        asyncio.run(run())

    def test_singleton_engine(self):
        assert get_workflow_engine() is get_workflow_engine()


class TestRunExecutionLinear:
    def test_successful_run(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s1", action="send"), _step("s2", action="send")])
            eid = await engine.start_workflow(wf, {"k": "v"})
            await asyncio.gather(*[t for t in engine._background_tasks])
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "COMPLETED"
            assert state["steps"]["s1"]["status"] == "COMPLETED"
            assert state["steps"]["s2"]["status"] == "COMPLETED"
        asyncio.run(run())

    def test_successful_run_single_task(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s1", action="send")])
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            assert engine_env["sm"].executions[eid]["status"] == "COMPLETED"
        asyncio.run(run())

    def test_step_failure_marks_workflow_failed(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s1", service="slack", action="chat_postMessage")])
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "FAILED"
            assert state["steps"]["s1"]["status"] == "FAILED"
        asyncio.run(run())

    def test_missing_input_pauses(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s1", params={"x": "${input.missing_var}"})])
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "PAUSED"
            assert state["steps"]["s1"]["status"] == "PAUSED"
        asyncio.run(run())

    def test_cancellation_stops_run(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s1")])
            eid = await engine.start_workflow(wf, {})
            await engine.cancel_execution(eid)
            await asyncio.gather(*list(engine._background_tasks))
            assert engine_env["sm"].executions[eid]["status"] == "CANCELLED"
        asyncio.run(run())

    def test_dependency_not_met_skips_step(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s2", depends_on=["s1"])])
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["steps"]["s2"]["status"] == "SKIPPED"
        asyncio.run(run())

    def test_condition_not_met_skips_step(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s1", condition="${input.x} == 99")])
            eid = await engine.start_workflow(wf, {"x": 1})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["steps"]["s1"]["status"] == "SKIPPED"
            assert any(e[1] == "STEP_SKIPPED" for e in engine_env["ws"].events)
        asyncio.run(run())

    def test_completed_step_skipped_on_resume(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s1")])
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            await engine.resume_workflow(eid, wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "COMPLETED"
        asyncio.run(run())

    def test_governance_block_pauses_workflow_for_hitl(self, engine_env, monkeypatch):
        async def run():
            engine = engine_env["engine"]
            blocked = MagicMock()
            blocked.can_perform_action_async = AsyncMock(
                return_value={"allowed": False, "reason": "not allowed"}
            )
            blocked.request_approval = MagicMock(return_value="hitl-1")

            class BlockedFactory:
                @staticmethod
                def get_governance_service(db, tenant_id="default"):
                    return blocked

            # The interlock governs registry-backed agents only — make the
            # registry lookup return a record for the workflow's agent.
            import contextlib
            from types import SimpleNamespace

            @contextlib.contextmanager
            def _db_cm():
                db = MagicMock()
                q = MagicMock()
                q.filter.return_value = q
                q.first.return_value = SimpleNamespace(id="agent-1")
                db.query.return_value = q
                yield db

            monkeypatch.setattr("core.workflow_engine.get_db_session", _db_cm)
            import core.workflow_engine as wfmod
            old = wfmod.ServiceFactory
            wfmod.ServiceFactory = BlockedFactory
            try:
                wf = _workflow([_step("s1")], agent_id="agent-1")
                eid = await engine.start_workflow(wf, {})
                await asyncio.gather(*list(engine._background_tasks))
                state = await engine.state_manager.get_execution_state(eid)
                # Trust-policy denial pauses for HITL review instead of failing
                assert state["status"] == "PAUSED"
                assert "Governance approval required" in (state["error"] or "")
                blocked.request_approval.assert_called_once()
            finally:
                wfmod.ServiceFactory = old
        asyncio.run(run())

    def test_output_error_dict_fails_run(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            async def err(action, params, connection_id=None):
                return {"status": "error", "error": "inner boom"}
            engine._execute_email_action = err
            wf = _workflow([_step("s1", service="email", action="send")])
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "FAILED"
            assert "inner boom" in (state["error"] or "")
        asyncio.run(run())

    def test_marketplace_tracking_called(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            with patch("core.workflow_engine.MarketplaceUsageTracker.track_usage") as tu:
                wf = _workflow([_step("s1")], created_from_template="tpl-1")
                eid = await engine.start_workflow(wf, {})
                await asyncio.gather(*list(engine._background_tasks))
                assert engine_env["sm"].executions[eid]["status"] == "COMPLETED"
                tu.assert_called()
        asyncio.run(run())


class TestRunExecutionGraph:
    def test_graph_completion(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _node_workflow(
                [{"id": "a", "config": {"service": "email", "action": "send"}},
                 {"id": "b", "config": {"service": "email", "action": "send"}}],
                [{"source": "a", "target": "b", "condition": "${a.status} == 'success'"}],
            )
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "COMPLETED"
            assert state["steps"]["a"]["status"] == "COMPLETED"
            assert state["steps"]["b"]["status"] == "COMPLETED"
        asyncio.run(run())

    def test_graph_conditional_branch_not_activated(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _node_workflow(
                [{"id": "a", "config": {"service": "email", "action": "send"}},
                 {"id": "b", "config": {"service": "email", "action": "send"}}],
                [{"source": "a", "target": "b", "condition": "${a.status} == 'failed'"}],
            )
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "PARTIAL"
            assert state["steps"]["a"]["status"] == "COMPLETED"
            assert state["steps"].get("b", {}).get("status") in (None, "PENDING")
        asyncio.run(run())

    def test_graph_step_failure_fails_workflow(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _node_workflow(
                [{"id": "a", "config": {"service": "slack", "action": "chat_postMessage"}}],
                [{"source": "a", "target": "b", "condition": "${a.status} == 'success'"}],
            )
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "FAILED"
        asyncio.run(run())

    def test_graph_continue_on_error_activates_downstream(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _node_workflow(
                [{"id": "a", "config": {"service": "slack", "action": "chat_postMessage",
                                        "continue_on_error": True}},
                 {"id": "b", "config": {"service": "email", "action": "send"}}],
                [{"source": "a", "target": "b", "condition": "1 == 1"}],
            )
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "PARTIAL"
            assert state["steps"]["a"]["status"] == "FAILED"
            assert state["steps"]["b"]["status"] == "COMPLETED"
        asyncio.run(run())

    def test_graph_cancellation(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _node_workflow(
                [{"id": "a", "config": {"service": "email", "action": "send"}}],
                [{"source": "a", "target": "b", "condition": "${a.status} == 'success'"}],
            )
            eid = await engine.start_workflow(wf, {})
            await engine.cancel_execution(eid)
            await asyncio.gather(*list(engine._background_tasks))
            assert engine_env["sm"].executions[eid]["status"] == "CANCELLED"
        asyncio.run(run())

    def test_graph_resume_completed_steps_activate_connections(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _node_workflow(
                [{"id": "a", "config": {"service": "email", "action": "send"}},
                 {"id": "b", "config": {"service": "email", "action": "send"}}],
                [{"source": "a", "target": "b"}],
            )
            eid = await engine.state_manager.create_execution("wf-g", {})
            await engine.state_manager.update_step_status(eid, "a", "COMPLETED", output={"x": 1})
            await engine.state_manager.update_execution_status(eid, "RUNNING")
            state = await engine.state_manager.get_execution_state(eid)
            await engine._execute_workflow_graph(eid, wf, state, engine_env["ws"], "u1", datetime.now(timezone.utc))
            final = await engine.state_manager.get_execution_state(eid)
            assert final["status"] == "COMPLETED"
        asyncio.run(run())

    def test_graph_execution_timeout_cleanup(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _node_workflow(
                [{"id": "a", "config": {"service": "slack", "action": "chat_postMessage"}}],
            )
            eid = await engine.state_manager.create_execution("wf-g", {})
            await engine.state_manager.update_execution_status(eid, "RUNNING")
            state = await engine.state_manager.get_execution_state(eid)
            await engine._execute_workflow_graph(eid, wf, state, engine_env["ws"], "u1", datetime.now(timezone.utc))
            final = await engine.state_manager.get_execution_state(eid)
            assert final["status"] == "FAILED"
        asyncio.run(run())


class TestRunWorkflowArborRefinement:
    def test_success_path(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s1"), _step("s2")])
            with patch("core.hypothesis_tree_endpoints._persist_tree") as persist:
                result = await engine.run_workflow_with_arbor_refinement("tenant-1", wf, {"k": "v"})
            assert result["success"] is True
            assert result["parallel_ratio"] == 1.0
            assert result["promise_score"] > 0
            persist.assert_called()
        asyncio.run(run())

    def test_failure_path(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s1", service="slack", action="chat_postMessage")])
            with patch("core.hypothesis_tree_endpoints._persist_tree"):
                result = await engine.run_workflow_with_arbor_refinement("tenant-1", wf, {})
            assert result["success"] is False
            assert result["promise_score"] == 0.0
        asyncio.run(run())


# ============================================================================
# workflow_debugger
# ============================================================================

@pytest.fixture
def debugger_env():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[
        User.__table__,
        WorkflowExecution.__table__,
        WorkflowDebugSession.__table__,
        WorkflowBreakpoint.__table__,
        ExecutionTrace.__table__,
        DebugVariable.__table__,
    ])
    db = Session(engine)
    db.add(User(id="user-1", email="u@x.com", hashed_password="x",
                first_name="U", last_name="One", role="admin", status="active"))
    db.add(User(id="user-2", email="v@x.com", hashed_password="x",
                first_name="V", last_name="Two", role="admin", status="active"))
    db.commit()
    debugger = WorkflowDebugger(db)
    yield debugger, db
    db.close()
    engine.dispose()


class TestDebugSessions:
    def test_create_and_get(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1", session_name="My Session")
        assert s.id and s.status == "active"
        assert debugger.get_debug_session(s.id).id == s.id
        assert debugger.get_debug_session("nope") is None

    def test_create_default_name(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        assert "Debug session" in s.session_name

    def test_active_sessions_filter(self, debugger_env):
        debugger, db = debugger_env
        debugger.create_debug_session("wf-1", "user-1")
        debugger.create_debug_session("wf-1", "user-2")
        assert len(debugger.get_active_debug_sessions("wf-1")) == 2
        assert len(debugger.get_active_debug_sessions("wf-1", "user-1")) == 1
        assert debugger.get_active_debug_sessions("wf-x") == []

    def test_pause_resume_complete(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        assert debugger.pause_debug_session(s.id) is True
        db.refresh(s)
        assert s.status == "paused"
        assert debugger.resume_debug_session(s.id) is True
        db.refresh(s)
        assert s.status == "active"
        assert debugger.complete_debug_session(s.id) is True
        db.refresh(s)
        assert s.status == "completed"
        assert debugger.pause_debug_session("missing") is False
        assert debugger.resume_debug_session("missing") is False
        assert debugger.complete_debug_session("missing") is False


class TestBreakpoints:
    def test_add_remove_toggle_get(self, debugger_env):
        debugger, db = debugger_env
        bp = debugger.add_breakpoint("wf-1", "node-a", "user-1", condition="x > 5", hit_limit=3,
                                     log_message="hit node-a")
        assert bp.hit_count == 0 and bp.is_active
        assert debugger.remove_breakpoint(bp.id, "user-2") is False
        assert debugger.remove_breakpoint(bp.id, "user-1") is True
        bp2 = debugger.add_breakpoint("wf-1", "node-a", "user-1")
        assert debugger.toggle_breakpoint(bp2.id, "user-1") is False
        assert debugger.toggle_breakpoint(bp2.id, "user-1") is True
        assert debugger.toggle_breakpoint("nope", "user-1") is None
        assert debugger.remove_breakpoint("nope", "user-1") is False

    def test_get_breakpoints_filters(self, debugger_env):
        debugger, db = debugger_env
        debugger.add_breakpoint("wf-1", "n1", "user-1")
        debugger.add_breakpoint("wf-1", "n2", "user-2")
        assert len(debugger.get_breakpoints("wf-1")) == 2
        assert len(debugger.get_breakpoints("wf-1", user_id="user-1")) == 1
        assert len(debugger.get_breakpoints("wf-1", active_only=False)) == 2

    def test_check_breakpoint_hit_pauses(self, debugger_env):
        debugger, db = debugger_env
        bp = debugger.add_breakpoint("wf-1", "node-a", "user-1")
        should_pause, msg = debugger.check_breakpoint_hit("node-a", {})
        assert should_pause is True and msg is None
        db.refresh(bp)
        assert bp.hit_count == 1

    def test_check_breakpoint_hit_log_message(self, debugger_env):
        debugger, db = debugger_env
        debugger.add_breakpoint("wf-1", "node-a", "user-1", log_message="logged!")
        should_pause, msg = debugger.check_breakpoint_hit("node-a", {})
        assert should_pause is False and msg == "logged!"

    def test_check_breakpoint_hit_condition_false(self, debugger_env):
        debugger, db = debugger_env
        debugger.add_breakpoint("wf-1", "node-a", "user-1", condition="x > 5")
        should_pause, msg = debugger.check_breakpoint_hit("node-a", {"x": 1})
        assert should_pause is False

    def test_check_breakpoint_hit_condition_true(self, debugger_env):
        debugger, db = debugger_env
        debugger.add_breakpoint("wf-1", "node-a", "user-1", condition="x > 5")
        should_pause, msg = debugger.check_breakpoint_hit("node-a", {"x": 10})
        assert should_pause is True

    def test_check_breakpoint_hit_limit(self, debugger_env):
        debugger, db = debugger_env
        debugger.add_breakpoint("wf-1", "node-a", "user-1", hit_limit=1)
        assert debugger.check_breakpoint_hit("node-a", {})[0] is True
        should_pause, _ = debugger.check_breakpoint_hit("node-a", {})
        assert should_pause is False  # hit limit exhausted

    def test_check_breakpoint_session_scoped(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        debugger.add_breakpoint("wf-1", "node-a", "user-1", debug_session_id=s.id)
        assert debugger.check_breakpoint_hit("node-a", {}, session_id=s.id)[0] is True
        assert debugger.check_breakpoint_hit("node-a", {}, session_id="other-session")[0] is False

    def test_disabled_breakpoint_ignored(self, debugger_env):
        debugger, db = debugger_env
        bp = debugger.add_breakpoint("wf-1", "node-a", "user-1")
        debugger.toggle_breakpoint(bp.id, "user-1")
        assert debugger.check_breakpoint_hit("node-a", {})[0] is False


class TestStepControl:
    def test_step_over(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        r = debugger.step_over(s.id)
        assert r["current_step"] == 1
        assert debugger.step_over("missing") is None

    def test_step_into(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        r = debugger.step_into(s.id, node_id="nested-1")
        assert r["call_stack_depth"] == 1
        assert r["current_node_id"] == "nested-1"
        db.refresh(s)
        assert s.call_stack[0]["workflow_id"] == "wf-1"
        assert debugger.step_into("missing") is None

    def test_step_out(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        debugger.step_into(s.id, node_id="n1")
        r = debugger.step_out(s.id)
        assert r["action"] == "step_out"
        assert debugger.step_out("missing") is None
        assert debugger.step_out(s.id) is None  # empty stack

    def test_continue_and_pause_execution(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        assert debugger.continue_execution(s.id)["status"] == "running"
        assert debugger.pause_execution(s.id)["status"] == "paused"
        assert debugger.continue_execution("missing") is None
        assert debugger.pause_execution("missing") is None


class TestTraces:
    def test_create_and_complete_trace(self, debugger_env):
        debugger, db = debugger_env
        tr = debugger.create_trace("wf-1", "exec-1", 1, "node-a", "action", {"in": 1})
        assert tr.status == "started"
        assert debugger.complete_trace(tr.id, output_data={"out": 2}, variables_after={"v": 2}) is True
        db.refresh(tr)
        assert tr.status == "completed"
        assert tr.output_data == {"out": 2}

    def test_complete_trace_error(self, debugger_env):
        debugger, db = debugger_env
        tr = debugger.create_trace("wf-1", "exec-1", 1, "node-a", "action")
        assert debugger.complete_trace(tr.id, error_message="boom") is True
        db.refresh(tr)
        assert tr.status == "failed"
        assert tr.error_message == "boom"
        assert debugger.complete_trace("missing") is False

    def test_get_execution_traces(self, debugger_env):
        debugger, db = debugger_env
        debugger.create_trace("wf-1", "exec-1", 1, "n1", "action")
        debugger.create_trace("wf-1", "exec-1", 2, "n2", "action", debug_session_id="sess-1")
        assert len(debugger.get_execution_traces("exec-1")) == 2
        assert len(debugger.get_execution_traces("exec-1", debug_session_id="sess-1")) == 1

    def test_calculate_variable_changes(self, debugger_env):
        debugger, db = debugger_env
        changes = debugger._calculate_variable_changes({"a": 1, "b": 2}, {"a": 3, "c": 4})
        by_type = {c["type"] for c in changes}
        assert by_type == {"changed", "added", "removed"}

    def test_complete_trace_duration_and_changes(self, debugger_env):
        debugger, db = debugger_env
        tr = debugger.create_trace("wf-1", "exec-1", 1, "n1", "action",
                                   variables_before={"x": 1})
        assert debugger.complete_trace(tr.id, variables_after={"x": 2}) is True
        db.refresh(tr)
        assert tr.variable_changes and tr.duration_ms is not None


class TestVariables:
    def test_create_snapshot_and_previews(self, debugger_env):
        debugger, db = debugger_env
        tr = debugger.create_trace("wf-1", "exec-1", 1, "n1", "action")
        v = debugger.create_variable_snapshot(tr.id, "count", "count", "int", 5)
        assert v.value_preview == "5"
        v2 = debugger.create_variable_snapshot(tr.id, "data", "data", "dict", {"a": 1})
        assert v2.value_preview == "dict(1 keys)"
        v3 = debugger.create_variable_snapshot(tr.id, "lst", "lst", "list", [1, 2])
        assert v3.value_preview == "list(2 items)"
        assert debugger._generate_value_preview(None) == "null"
        assert debugger._generate_value_preview({1, 2}) == "set(2 items)"

    def test_get_variables_and_watch(self, debugger_env):
        debugger, db = debugger_env
        tr = debugger.create_trace("wf-1", "exec-1", 1, "n1", "action", debug_session_id="s1")
        debugger.create_variable_snapshot(tr.id, "a", "a", "int", 1)
        debugger.create_variable_snapshot(tr.id, "w", "w", "int", 2, is_watch=True, debug_session_id="s1")
        assert len(debugger.get_variables_for_trace(tr.id)) == 2
        assert len(debugger.get_watch_variables("s1")) == 1

    def test_modify_and_bulk_modify(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        v = debugger.modify_variable(s.id, "x", 42)
        assert v.value == 42 and v.is_changed
        db.refresh(s)
        assert s.variables["x"] == 42
        assert debugger.modify_variable("missing", "x", 1) is None
        results = debugger.bulk_modify_variables(s.id, [{"variable_name": "y", "new_value": 2},
                                                        {"variable_name": None, "new_value": 9}])
        assert len(results) == 1


class TestSessionPersistence:
    def test_export_and_import(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        debugger.add_breakpoint("wf-1", "n1", "user-1", debug_session_id=s.id)
        debugger.create_trace("wf-1", "exec-1", 1, "n1", "action", debug_session_id=s.id)
        exported = debugger.export_session(s.id)
        assert exported["session"]["id"] == s.id
        assert exported["breakpoints"][0]["node_id"] == "n1"
        new = debugger.import_session(exported)
        assert new.id != s.id
        assert "(Imported)" in new.session_name
        assert debugger.export_session("missing") is None

    def test_import_restore_variables_and_breakpoints(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        debugger.modify_variable(s.id, "v", 7)
        debugger.add_breakpoint("wf-1", "n1", "user-1", debug_session_id=s.id)
        exported = debugger.export_session(s.id)
        new = debugger.import_session(exported, restore_breakpoints=True, restore_variables=True)
        assert new.variables.get("v") == 7
        bps = debugger.get_breakpoints("wf-1", user_id="user-1")
        assert any(bp.debug_session_id == new.id for bp in bps)


class TestProfiling:
    def test_start_profiling(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        assert debugger.start_performance_profiling(s.id) is True
        assert debugger.start_performance_profiling("missing") is False

    def test_record_step_timing_and_report(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        debugger.start_performance_profiling(s.id)
        assert debugger.record_step_timing(s.id, "n1", "action", 100) is True
        assert debugger.record_step_timing(s.id, "n1", "action", 300) is True
        assert debugger.record_step_timing(s.id, "n2", "action", 50) is True
        assert debugger.record_step_timing(s.id, "n1", "action", 200) is True
        report = debugger.get_performance_report(s.id)
        assert report["total_steps"] == 4
        assert report["total_duration_ms"] == 650
        assert report["slowest_nodes"][0]["node_id"] == "n1"
        assert report["slowest_nodes"][0]["avg_ms"] == 200
        assert debugger.get_performance_report("missing") is None
        assert debugger.record_step_timing("missing", "n1", "action", 1) is False


class TestCollaboration:
    def test_add_remove_collaborators(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        assert debugger.add_collaborator(s.id, "user-2", "viewer") is True
        assert debugger.add_collaborator("missing", "user-2") is False
        assert debugger.remove_collaborator(s.id, "user-2") is True
        assert debugger.remove_collaborator(s.id, "user-2") is False
        assert debugger.remove_collaborator("missing", "user-2") is False

    def test_permission_hierarchy(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        debugger.add_collaborator(s.id, "user-2", "viewer")
        assert debugger.check_collaborator_permission(s.id, "user-2", "viewer") is True
        assert debugger.check_collaborator_permission(s.id, "user-2", "operator") is False
        assert debugger.check_collaborator_permission(s.id, "user-1", "owner") is True  # owner
        assert debugger.check_collaborator_permission(s.id, "unknown", "viewer") is False
        assert debugger.check_collaborator_permission("missing", "user-1", "viewer") is False

    def test_get_session_collaborators(self, debugger_env):
        debugger, db = debugger_env
        s = debugger.create_debug_session("wf-1", "user-1")
        debugger.add_collaborator(s.id, "user-2", "operator")
        collabs = debugger.get_session_collaborators(s.id)
        assert collabs[0]["permission"] == "operator"
        assert debugger.get_session_collaborators("missing") == []


class TestTraceStreaming:
    def test_stream_lifecycle(self, debugger_env):
        debugger, db = debugger_env
        stream_id = debugger.create_trace_stream("s1", "exec-1")
        assert stream_id.startswith("trace_s1_exec-1_")
        ws = MagicMock()
        assert debugger.stream_trace_update(stream_id, {"x": 1}, ws) is True
        ws.broadcast.assert_called_once()
        assert debugger.stream_trace_update(stream_id, {"x": 1}) is False
        assert debugger.close_trace_stream(stream_id, ws) is True
        assert debugger.close_trace_stream(stream_id) is True

    def test_async_websocket_helpers(self, debugger_env):
        debugger, db = debugger_env
        async def coro():
            return 7
        assert debugger._run_async_websocket(coro()) == 7
        with patch("core.workflow_debugger.get_debugging_websocket_manager") as gm:
            mgr = MagicMock()
            gm.return_value = mgr
            debugger.notify_variable_changed("s1", "v", 1, 0)
            debugger.notify_breakpoint_hit("s1", "bp", "n1", 2)
            debugger.notify_session_paused("s1", "why", "n1")
            debugger.notify_session_resumed("s1")
            debugger.notify_step_completed("s1", "step_over", 3, "n1")
            debugger.stream_trace_with_manager("exec-1", "s1", {"x": 1})
        assert debugger._run_async_websocket(coro()) == 7  # idempotent


# ============================================================================
# workflow_analytics_engine
# ============================================================================

@pytest.fixture
def analytics(tmp_path):
    eng = WorkflowAnalyticsEngine(db_path=str(tmp_path / "an.db"))
    yield eng
    eng._stop_event = None


class TestAnalyticsInit:
    def test_init_creates_db(self, tmp_path):
        dbp = tmp_path / "an.db"
        eng = WorkflowAnalyticsEngine(db_path=str(dbp))
        assert dbp.exists()
        assert eng.metrics_buffer.maxlen == 10000
        assert eng.events_buffer.maxlen == 50000
        assert eng.cache_ttl == 300

    def test_tilde_path_expansion(self, tmp_path, monkeypatch):
        """BUG: expanduser().absolute() result was discarded, breaking ~ paths."""
        monkeypatch.setenv("HOME", str(tmp_path))
        eng = WorkflowAnalyticsEngine(db_path="~/an2.db")
        assert str(eng.db_path) == str(tmp_path / "an2.db")
        assert (tmp_path / "an2.db").exists()


class TestAnalyticsTracking:
    def test_track_workflow_start(self, analytics):
        analytics.track_workflow_start("w1", "e1", metadata={"k": 1})
        assert len(analytics.events_buffer) == 1
        assert len(analytics.metrics_buffer) == 1

    def test_track_completion_statuses(self, analytics):
        analytics.track_workflow_completion("w1", "e1", WorkflowStatus.COMPLETED, 500, {"s": 1})
        analytics.track_workflow_completion("w1", "e2", WorkflowStatus.FAILED, 100,
                                            error_message="boom")
        assert len(analytics.events_buffer) == 2
        assert len(analytics.metrics_buffer) == 4

    def test_track_step_execution_with_and_without_duration(self, analytics):
        analytics.track_step_execution("w1", "e1", "s1", "step", "step_started")
        analytics.track_step_execution("w1", "e1", "s1", "step", "step_completed", duration_ms=50,
                                       status="completed", resource_id="r1", error_message=None)
        assert len(analytics.events_buffer) == 2
        assert len(analytics.metrics_buffer) == 1

    def test_track_manual_override(self, analytics):
        analytics.track_manual_override("w1", "e1", "r1", "modify", 1, 2)
        assert analytics.events_buffer[0].event_type == "manual_override"
        assert analytics.events_buffer[0].status == "OVERRIDDEN"
        assert analytics.metrics_buffer[-1].metric_name == "manual_override_count"

    def test_track_resource_usage(self, analytics):
        analytics.track_resource_usage("w1", 40.0, 512.0, step_id="s1", disk_io=1000, network_io=2000)
        assert len(analytics.metrics_buffer) == 4
        analytics.track_resource_usage("w1", 40.0, 512.0)
        assert len(analytics.metrics_buffer) == 6

    def test_track_user_activity(self, analytics):
        analytics.track_user_activity("u1", "viewed")
        assert analytics.metrics_buffer[0].workflow_id == "system"

    def test_track_metric(self, analytics):
        analytics.track_metric("w1", "custom", MetricType.GAUGE, 3.5, tags={"t": "1"})
        assert analytics.metrics_buffer[0].value == 3.5

    def test_flush_persists_buffers(self, analytics):
        analytics.track_workflow_start("w1", "e1")
        analytics.track_metric("w1", "m", MetricType.COUNTER, 1)

        async def run():
            await analytics.flush()
        asyncio.run(run())
        assert len(analytics.metrics_buffer) == 0
        assert len(analytics.events_buffer) == 0
        assert len(analytics.get_recent_events()) == 1
        assert len(analytics.get_all_workflow_ids("24h")) == 1


class TestAnalyticsPerformance:
    def _seed(self, analytics, n=1):
        for i in range(n):
            analytics.track_workflow_start("w1", f"e{i}")
            analytics.track_workflow_completion("w1", f"e{i}", WorkflowStatus.COMPLETED, 100 * (i + 1))

        async def run():
            await analytics.flush()
        asyncio.run(run())

    def test_empty_db_metrics(self, analytics):
        m = analytics.get_workflow_performance_metrics("nope", "24h")
        assert m.total_executions == 0
        assert m.average_duration_ms == 0
        assert m.error_rate == 0

    def test_performance_metrics_aggregation(self, analytics):
        self._seed(analytics, n=2)
        m = analytics.get_workflow_performance_metrics("w1", "24h")
        assert m.total_executions == 2
        assert m.successful_executions == 2
        assert m.average_duration_ms == 150
        assert m.median_duration_ms == 150

    def test_cached_metrics_returned(self, analytics):
        self._seed(analytics, n=1)
        m1 = analytics.get_workflow_performance_metrics("w1", "24h")
        m2 = analytics.get_workflow_performance_metrics("w1", "24h")
        assert m1 is m2

    def test_stale_cache_not_returned(self, analytics):
        """BUG: cache freshness used timedelta.seconds (wraps >24h), returning
        stale data for anything cached more than a day ago."""
        self._seed(analytics, n=1)
        from core.workflow_analytics_engine import PerformanceMetrics
        stale = PerformanceMetrics(
            workflow_id="w1", time_window="24h", total_executions=999,
            successful_executions=999, failed_executions=0, average_duration_ms=0,
            median_duration_ms=0, p95_duration_ms=0, p99_duration_ms=0, error_rate=0,
            most_common_errors=[], average_cpu_usage=0, peak_memory_usage=0,
            average_step_duration={}, unique_users=0, executions_by_user={},
            timestamp=datetime.now() - timedelta(days=2),
        )
        analytics.performance_cache["w1_24h"] = stale
        m = analytics.get_workflow_performance_metrics("w1", "24h")
        assert m.total_executions == 1
        assert m is not stale

    def test_failed_executions_and_errors(self, analytics):
        analytics.track_workflow_start("w1", "e1")
        analytics.track_workflow_completion("w1", "e1", WorkflowStatus.FAILED, 50, error_message="oops")

        async def run():
            await analytics.flush()
        asyncio.run(run())
        m = analytics.get_workflow_performance_metrics("w1", "24h")
        assert m.failed_executions == 1
        assert m.error_rate == 100.0
        assert m.most_common_errors[0]["error"] == "oops"

    def test_all_workflows_metrics(self, analytics):
        analytics.track_workflow_start("w1", "e1", user_id="alice")
        analytics.track_workflow_completion("w1", "e1", WorkflowStatus.COMPLETED, 50, user_id="alice")

        async def run():
            await analytics.flush()
        asyncio.run(run())
        m = analytics.get_performance_metrics("*", "24h")
        assert m.total_executions == 1
        assert m.unique_users == 1
        assert m.most_common_errors == []

    def test_all_workflows_error_breakdown(self, analytics):
        """BUG: all-workflows metric computed 'most_common_errors' from the
        user_id column — error messages were never selected."""
        analytics.track_workflow_start("w1", "e1", user_id="alice")
        analytics.track_workflow_completion("w1", "e1", WorkflowStatus.FAILED, 50,
                                            error_message="real error", user_id="alice")

        async def run():
            await analytics.flush()
        asyncio.run(run())
        m = analytics._get_all_workflows_metrics("24h")
        assert m.most_common_errors == [{"error": "real error", "count": 1, "percentage": 100.0}]

    def test_get_performance_metrics_specific(self, analytics):
        assert analytics.get_performance_metrics("w1", "24h").total_executions == 0


class TestAnalyticsSystemOverview:
    def test_system_overview(self, analytics):
        analytics.track_workflow_start("w1", "e1")
        analytics.track_workflow_completion("w1", "e1", WorkflowStatus.COMPLETED, 100)
        analytics.track_workflow_start("w2", "e2")
        analytics.track_workflow_completion("w2", "e2", WorkflowStatus.FAILED, 50, error_message="x")

        async def run():
            await analytics.flush()
        asyncio.run(run())
        ov = analytics.get_system_overview("24h")
        assert ov["total_workflows"] == 2
        assert ov["total_executions"] == 2
        assert ov["success_rate"] == 50.0
        assert ov["average_execution_time_ms"] == 75.0
        assert len(ov["top_workflows"]) == 2
        assert len(ov["recent_errors"]) == 1

    def test_system_overview_empty(self, analytics):
        ov = analytics.get_system_overview("24h")
        assert ov["total_executions"] == 0
        assert ov["success_rate"] == 0


class TestAnalyticsAlerts:
    def test_create_alert_and_get_all(self, analytics):
        alert = Alert(
            alert_id="a1", name="High failures", description="d", severity=AlertSeverity.HIGH,
            condition="failed > 5", threshold_value=5, metric_name="failed_executions",
            workflow_id="w1", notification_channels=["email"],
        )
        returned = analytics.create_alert(alert)
        assert returned.alert_id == "a1"
        alerts = analytics.get_all_alerts()
        assert len(alerts) == 1
        assert len(analytics.get_all_alerts(workflow_id="w1")) == 1
        assert len(analytics.get_all_alerts(workflow_id="other")) == 0
        assert len(analytics.get_all_alerts(enabled_only=True)) == 1

    def test_check_alerts_trigger_and_resolve(self, analytics):
        alert = Alert(
            alert_id="a1", name="Spike", description="d", severity=AlertSeverity.CRITICAL,
            condition="", threshold_value=10, metric_name="execution_duration_ms",
        )
        analytics.create_alert(alert)
        analytics.track_metric("w1", "execution_duration_ms", MetricType.HISTOGRAM, 50)

        async def run():
            await analytics.flush()
        asyncio.run(run())
        analytics.check_alerts()
        assert alert.triggered_at is not None
        analytics.track_metric("w1", "execution_duration_ms", MetricType.HISTOGRAM, 1)
        asyncio.run(run())
        analytics.check_alerts()
        assert alert.resolved_at is not None

    def test_update_and_delete_alert(self, analytics):
        alert = Alert(alert_id="a1", name="N", description="d", severity=AlertSeverity.LOW,
                      condition="", threshold_value=1, metric_name="m")
        analytics.create_alert(alert)
        analytics.update_alert("a1", enabled=False, threshold_value=5.0)
        assert len(analytics.get_all_alerts(enabled_only=True)) == 0
        analytics.update_alert("a1", enabled=True)
        assert len(analytics.get_all_alerts(enabled_only=True)) == 1
        analytics.delete_alert("a1")
        assert analytics.get_all_alerts() == []


class TestAnalyticsQueries:
    def test_unique_workflow_count(self, analytics):
        analytics.track_workflow_start("w1", "e1")
        analytics.track_workflow_start("w2", "e2")

        async def run():
            await analytics.flush()
        asyncio.run(run())
        assert analytics.get_unique_workflow_count("24h") == 2

    def test_workflow_name_and_ids(self, analytics):
        analytics.track_workflow_start("w9", "e1")
        asyncio.run(analytics.flush())
        assert analytics.get_workflow_name("w9") == "w9"
        assert analytics.get_all_workflow_ids("24h") == ["w9"]

    def test_last_execution_time(self, analytics):
        assert analytics.get_last_execution_time("w1") is None
        analytics.track_workflow_start("w1", "e1")
        asyncio.run(analytics.flush())
        assert analytics.get_last_execution_time("w1") is not None

    def test_execution_timeline(self, analytics):
        analytics.track_workflow_start("w1", "e1")
        analytics.track_workflow_completion("w1", "e1", WorkflowStatus.COMPLETED, 100)
        analytics.track_workflow_start("w2", "e2")
        analytics.track_workflow_completion("w2", "e2", WorkflowStatus.FAILED, 50)
        asyncio.run(analytics.flush())
        tl = analytics.get_execution_timeline("w1", "24h", "1h")
        assert sum(d["count"] for d in tl) == 1
        assert sum(d["success_count"] for d in tl) == 1
        tl_all = analytics.get_execution_timeline("*", "24h", "1h")
        assert sum(d["count"] for d in tl_all) == 2
        assert analytics.get_execution_timeline("w1", "24h", "bad-interval")[0]["timestamp"] is not None

    def test_error_breakdown_all(self, analytics):
        analytics.track_workflow_start("w1", "e1")
        analytics.track_workflow_completion("w1", "e1", WorkflowStatus.FAILED, 10, error_message="type A error")
        analytics.track_workflow_start("w2", "e2")
        analytics.track_workflow_completion("w2", "e2", WorkflowStatus.FAILED, 10, error_message="type B error")
        asyncio.run(analytics.flush())
        bd = analytics.get_error_breakdown("*", "24h")
        assert len(bd["workflows_with_errors"]) == 2
        assert len(bd["error_types"]) == 2
        assert len(bd["recent_errors"]) == 2

    def test_error_breakdown_specific(self, analytics):
        analytics.track_workflow_start("w1", "e1")
        analytics.track_workflow_completion("w1", "e1", WorkflowStatus.FAILED, 10,
                                            error_message="specific error", user_id="u1")
        asyncio.run(analytics.flush())
        bd = analytics.get_error_breakdown("w1", "24h")
        assert bd["workflow_id"] == "w1"
        assert bd["error_types"][0]["type"] == "specific error"

    def test_recent_events(self, analytics):
        analytics.track_workflow_start("w1", "e1")
        analytics.track_workflow_start("w2", "e2")
        asyncio.run(analytics.flush())
        events = analytics.get_recent_events(limit=10)
        assert len(events) == 2
        assert len(analytics.get_recent_events(limit=1, workflow_id="w1")) == 1
        assert events[0].event_type == "workflow_started"

    def test_background_processing_enabled(self, tmp_path):
        eng = WorkflowAnalyticsEngine(db_path=str(tmp_path / "bg.db"), enable_background_thread=True)
        assert eng._background_thread is not None and eng._background_thread.is_alive()


# ============================================================================
# workflow_versioning_system
# ============================================================================

@pytest.fixture
def versioner(tmp_path):
    return WorkflowVersioningSystem(db_path=str(tmp_path / "versions.db"))


class TestVersioningBasics:
    def test_checksum_and_change_type(self, versioner):
        data = {"steps": [{"id": "a", "parameters": {"x": 1}}]}
        cs1 = versioner._calculate_checksum(data)
        cs2 = versioner._calculate_checksum(dict(data))
        assert cs1 == cs2 and len(cs1) == 64
        assert versioner._determine_change_type(None, data) == ChangeType.STRUCTURAL
        assert versioner._determine_change_type(data, data) == ChangeType.METADATA

    def test_change_type_detection(self, versioner):
        base = {"steps": [{"id": "a", "parameters": {"x": 1}, "execution_logic": {}}],
                "dependencies": ["d1"], "name": "n"}
        assert versioner._determine_change_type(base, {**base, "name": "new"}) == ChangeType.METADATA
        params_changed = {**base, "steps": [{"id": "a", "parameters": {"x": 2}, "execution_logic": {}}]}
        assert versioner._determine_change_type(base, params_changed) == ChangeType.PARAMETRIC
        exec_changed = {**base, "steps": [{"id": "a", "parameters": {"x": 1}, "execution_logic": {"code": "x"}}]}
        assert versioner._determine_change_type(base, exec_changed) == ChangeType.EXECUTION
        deps_changed = {**base, "dependencies": ["d2"]}
        assert versioner._determine_change_type(base, deps_changed) == ChangeType.DEPENDENCY

    def test_bump_version(self, versioner):
        assert versioner._bump_version("1.0.0", VersionType.MAJOR) == "2.0.0"
        assert versioner._bump_version("1.0.0", VersionType.MINOR) == "1.1.0"
        assert versioner._bump_version("1.0.0", VersionType.PATCH) == "1.0.1"
        assert versioner._bump_version("1.0.0", VersionType.HOTFIX) == "1.0.1"
        assert versioner._bump_version("1.0.0", VersionType.BETA) == "1.0.0-beta.1"
        assert versioner._bump_version("1.0.0-beta.1", VersionType.BETA) == "1.0.0-beta.2"
        assert versioner._bump_version("1.0.0", VersionType.ALPHA) == "1.0.0-alpha.1"
        assert versioner._bump_version("garbage", VersionType.MAJOR) == "2.0.0"


class TestVersionCRUD:
    def test_create_version_chain(self, versioner):
        wf = {"steps": [{"id": "a"}]}

        async def run():
            v1 = await versioner.create_version("w1", wf, VersionType.MAJOR, "u1", "init")
            assert v1.version == "1.0.0"
            assert v1.parent_version is None
            v2 = await versioner.create_version("w1", {**wf, "name": "x"}, VersionType.MINOR, "u1", "feat")
            assert v2.version == "1.1.0"
            assert v2.parent_version == "1.0.0"
            assert v2.change_type == ChangeType.METADATA
            v3 = await versioner.create_version("w1", {**wf, "steps": [{"id": "b"}]}, VersionType.PATCH, "u1", "fix")
            assert v3.version == "1.1.1"
            assert v3.change_type == ChangeType.STRUCTURAL
        asyncio.run(run())

    def test_duplicate_checksum_rejected(self, versioner):
        wf = {"steps": []}

        async def run():
            await versioner.create_version("w1", wf, VersionType.MAJOR, "u1", "init")
            with pytest.raises(ValueError, match="already exists"):
                await versioner.create_version("w1", wf, VersionType.PATCH, "u1", "dup")
        asyncio.run(run())

    def test_get_version_and_history(self, versioner):
        wf = {"steps": [{"id": "a"}]}

        async def run():
            await versioner.create_version("w1", wf, VersionType.MAJOR, "u1", "init")
            await versioner.create_version("w1", {**wf, "name": "x"}, VersionType.MINOR, "u2", "feat")
            v = await versioner.get_version("w1", "1.0.0")
            assert v.workflow_id == "w1" and v.created_by == "u1"
            assert await versioner.get_version("w1", "9.9.9") is None
            latest = await versioner.get_latest_version("w1")
            assert latest.version == "1.1.0"
            assert await versioner.get_latest_version("w-missing") is None
            history = await versioner.get_version_history("w1")
            assert [h.version for h in history] == ["1.1.0", "1.0.0"]
            assert await versioner.get_version_history("w-missing") == []
        asyncio.run(run())

    def test_rollback_to_version(self, versioner):
        wf = {"steps": [{"id": "a", "parameters": {"x": 1}}]}

        async def run():
            await versioner.create_version("w1", wf, VersionType.MAJOR, "u1", "init")
            await versioner.create_version("w1", {**wf, "name": "new"}, VersionType.MINOR, "u1", "feat")
            rb = await versioner.rollback_to_version("w1", "1.0.0", "u1", "bad change")
            assert rb.version == "1.1.1"
            assert rb.change_type == ChangeType.METADATA
            assert "Rollback" in rb.commit_message
            assert rb.tags == ["rollback", "from-1.0.0"]
            with pytest.raises(ValueError, match="not found"):
                await versioner.rollback_to_version("w1", "9.9.9", "u1", "x")
        asyncio.run(run())


class TestVersionDiff:
    def test_compare_versions_with_modified_steps(self, versioner):
        """BUG: _calculate_version_diff crashed on any modified step
        (iterating dict keys instead of items)."""
        base = {"steps": [{"id": "a", "parameters": {"x": 1}}], "name": "n"}
        changed = {"steps": [{"id": "a", "parameters": {"x": 2}}], "name": "n"}

        async def run():
            await versioner.create_version("w1", base, VersionType.MAJOR, "u1", "init")
            await versioner.create_version("w1", changed, VersionType.MINOR, "u1", "mod")
            diff = await versioner.compare_versions("w1", "1.0.0", "1.1.0")
            assert diff.impact_level == "low"
            assert len(diff.modified_steps) == 1
            assert diff.modified_steps[0]["step_id"] == "a"
            assert "x" in diff.parametric_changes["a"][1]
        asyncio.run(run())

    def test_compare_added_removed_steps(self, versioner):
        base = {"steps": [{"id": "a"}], "name": "n"}
        changed = {"steps": [{"id": "a"}, {"id": "c"}], "name": "n"}

        async def run():
            await versioner.create_version("w1", base, VersionType.MAJOR, "u1", "init")
            await versioner.create_version("w1", changed, VersionType.MINOR, "u1", "mod")
            diff = await versioner.compare_versions("w1", "1.0.0", "1.1.0")
            assert [s["id"] for s in diff.added_steps] == ["c"]
            assert diff.removed_steps == []
            assert any("Step count" in s for s in diff.structural_changes)
        asyncio.run(run())

    def test_compare_missing_version_raises(self, versioner):
        async def run():
            with pytest.raises(ValueError, match="not found"):
                await versioner.compare_versions("w1", "1.0.0", "2.0.0")
        asyncio.run(run())

    def test_diff_cached_second_call(self, versioner):
        base = {"steps": [{"id": "a"}]}
        changed = {"steps": [{"id": "a"}, {"id": "b"}]}

        async def run():
            await versioner.create_version("w1", base, VersionType.MAJOR, "u1", "init")
            await versioner.create_version("w1", changed, VersionType.MINOR, "u1", "mod")
            d1 = await versioner.compare_versions("w1", "1.0.0", "1.1.0")
            d2 = await versioner.compare_versions("w1", "1.0.0", "1.1.0")
            assert d1.impact_level == d2.impact_level
            assert d1.from_version == d2.from_version == "1.0.0"
        asyncio.run(run())

    def test_find_step_changes(self, versioner):
        old_step = {"id": "a", "parameters": {"x": 1}, "execution_logic": {"c": 1}, "title": "t", "type": "action"}
        new_step = {"id": "a", "parameters": {"x": 2}, "execution_logic": {"c": 2}, "title": "t", "type": "trigger"}
        changes = versioner._find_step_changes(old_step, new_step)
        assert changes["parameters"]["x"] == {"old": 1, "new": 2}
        assert changes["execution_logic"] == {"old": {"c": 1}, "new": {"c": 2}}
        assert changes["structural"] is True


class TestBranches:
    def test_create_branch_and_get_branches(self, versioner):
        wf = {"steps": [{"id": "a"}]}

        async def run():
            await versioner.create_version("w1", wf, VersionType.MAJOR, "u1", "init")
            b = await versioner.create_branch("w1", "feature-x", "1.0.0", "u2", merge_strategy="squash")
            assert b.current_version == "1.0.0"
            assert b.merge_strategy == "squash"
            branches = await versioner.get_branches("w1")
            assert len(branches) == 2  # main (auto-created) + feature-x
            assert await versioner.get_branches("w-other") == []
            with pytest.raises(ValueError, match="already exists"):
                await versioner.create_branch("w1", "feature-x", "1.0.0", "u2")
            with pytest.raises(ValueError, match="not found"):
                await versioner.create_branch("w1", "feature-y", "9.9.9", "u2")
        asyncio.run(run())

    def test_merge_branch(self, versioner):
        wf = {"steps": [{"id": "a", "parameters": {"x": 1}}]}

        async def run():
            await versioner.create_version("w1", wf, VersionType.MAJOR, "u1", "init")
            await versioner.create_branch("w1", "feat", "1.0.0", "u2")
            await versioner.create_version("w1", {**wf, "name": "branch-work"}, VersionType.MINOR,
                                           "u2", "branch change", branch_name="feat")
            merged = await versioner.merge_branch("w1", "feat", "main", "u1", "ship it")
            assert merged.branch_name == "main"
            assert "ship it" in merged.commit_message
            # Branch continues from base 1.0.0 → first branch version 1.1.0;
            # merge onto main bumps past it → 1.2.0 (UNIQUE workflow_id+version).
            assert merged.version == "1.2.0"
            with pytest.raises(ValueError, match="not found"):
                await versioner.merge_branch("w1", "ghost", "main", "u1", "x")
            with pytest.raises(ValueError, match="not found"):
                await versioner.merge_branch("w1", "feat", "ghost", "u1", "x")
        asyncio.run(run())


class TestVersionMetrics:
    def test_update_and_get_metrics(self, versioner):
        wf = {"steps": [{"id": "a"}]}

        async def run():
            await versioner.create_version("w1", wf, VersionType.MAJOR, "u1", "init")
            assert await versioner.update_version_metrics("w1", "1.0.0",
                                                          {"success": True, "execution_time": 100}) is True
            assert await versioner.update_version_metrics("w1", "1.0.0",
                                                          {"success": False, "execution_time": 200}) is True
            m = await versioner.get_version_metrics("w1", "1.0.0")
            assert m["execution_count"] == 2
            assert m["error_count"] == 1
            assert m["success_rate"] == 50.0
            assert await versioner.get_version_metrics("w1", "9.9.9") is None
        asyncio.run(run())

    def test_get_version_metrics_performance_score(self, versioner):
        """BUG: get_version_metrics returned last_execution as performance_score
        (wrong column index)."""
        wf = {"steps": [{"id": "a"}]}

        async def run():
            await versioner.create_version("w1", wf, VersionType.MAJOR, "u1", "init")
            await versioner.update_version_metrics("w1", "1.0.0", {"success": True, "execution_time": 100})
            m = await versioner.get_version_metrics("w1", "1.0.0")
            assert isinstance(m["performance_score"], float)
            assert m["performance_score"] != m["last_execution"]
        asyncio.run(run())


class TestDeleteVersion:
    def test_delete_version(self, versioner):
        wf = {"steps": [{"id": "a"}]}

        async def run():
            await versioner.create_version("w1", wf, VersionType.MAJOR, "u1", "init")
            await versioner.create_version("w1", {**wf, "name": "x"}, VersionType.MINOR, "u1", "feat")
            assert await versioner.delete_version("w1", "1.0.0", "u1", "cleanup") is True
            v = await versioner.get_version("w1", "1.0.0")
            assert v.is_active is False
            assert await versioner.delete_version("w-missing", "1.0.0", "u1", "x") is False
        asyncio.run(run())

    def test_delete_in_use_version_rejected(self, versioner):
        wf = {"steps": [{"id": "a"}]}

        async def run():
            await versioner.create_version("w1", wf, VersionType.MAJOR, "u1", "init")
            await versioner.create_branch("w1", "feat", "1.0.0", "u2")
            assert await versioner.delete_version("w1", "1.0.0", "u1", "x") is False
        asyncio.run(run())


class TestVersionManager:
    def test_create_workflow_version(self, versioner, tmp_path):
        mgr = WorkflowVersionManager()
        mgr.versioning_system = versioner
        wf = {"steps": [{"id": "a"}]}

        async def run():
            r1 = await mgr.create_workflow_version("w1", wf, "u1", "first", version_type="major")
            assert r1["version"] == "1.0.0"
            assert r1["version_type"] == "major"
            r2 = await mgr.create_workflow_version("w1", {**wf, "name": "n"}, "u1", "change",
                                                   version_type="auto")
            assert r2["version"] == "1.0.1"
            assert r2["change_type"] == "metadata"
            r3 = await mgr.create_workflow_version("w1", {**wf, "steps": [{"id": "b"}]}, "u1", "big",
                                                   version_type="patch")
            assert r3["version"] == "1.0.2"
        asyncio.run(run())

    def test_rollback_workflow_and_changes(self, versioner, tmp_path):
        mgr = WorkflowVersionManager()
        mgr.versioning_system = versioner
        wf = {"steps": [{"id": "a"}]}

        async def run():
            await mgr.create_workflow_version("w1", wf, "u1", "first", version_type="major")
            await mgr.create_workflow_version("w1", {**wf, "name": "n"}, "u1", "change")
            rb = await mgr.rollback_workflow("w1", "1.0.0", "u1", "revert")
            assert rb["rollback_successful"] is True
            changes = await mgr.get_workflow_changes("w1", "1.0.0", "1.1.0")
            assert changes["from_version"] == "1.0.0"
            assert changes["to_version"] == "1.1.0"
            assert "impact_level" in changes
        asyncio.run(run())


# ============================================================================
# workflow_engine — per-service executors (token provided, services mocked)
# ============================================================================

TOKEN = {"access_token": "tok-123", "instance_url": "https://x.salesforce.com"}


class TestServiceExecutors:
    def _exec(self, engine_env, service, action, params=None, connection_id="c1"):
        params = params or {}
        return engine_env["engine"]._execute_step(
            _step("s1", service=service, action=action, params=params, connection_id=connection_id),
            params)

    def test_slack_actions(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                svc = MagicMock()
                svc.post_message = AsyncMock(return_value={"ok": True})
                svc.list_channels = AsyncMock(return_value={"ok": True})
                svc.get_team_info = AsyncMock(return_value={"ok": True})
                svc.get_channel_info = AsyncMock(return_value={"ok": True})
                svc.get_channel_history = AsyncMock(return_value={"ok": True})
                svc.update_message = AsyncMock(return_value={"ok": True})
                svc.delete_message = AsyncMock(return_value={"ok": True})
                svc.search_messages = AsyncMock(return_value={"ok": True})
                svc.list_files = AsyncMock(return_value={"ok": True})
                with patch("integrations.slack_service_unified.slack_unified_service", svc):
                    for action, params in [
                        ("chat_postMessage", {"channel": "c", "text": "hi"}),
                        ("list_channels", {}),
                        ("chat_getUsers", {}),
                        ("get_channel_info", {"channel_id": "c1"}),
                        ("get_channel_history", {"channel_id": "c1"}),
                        ("update_message", {"channel_id": "c", "message_ts": "1", "text": "x"}),
                        ("delete_message", {"channel_id": "c", "message_ts": "1"}),
                        ("search_messages", {"query": "q"}),
                        ("files_list", {}),
                    ]:
                        out = await self._exec(engine_env, "slack", action, params)
                        assert out["status"] == "success", action
                    out = await self._exec(engine_env, "slack", "files_get_upload_url_external")
                    assert out["result"]["result"]["ok"] is False
                    out = await self._exec(engine_env, "slack", "reactions_add")
                    assert out["result"]["result"]["ok"] is False
        asyncio.run(run())

    def test_slack_missing_params_raise(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                with patch("integrations.slack_service_unified.slack_unified_service", MagicMock()):
                    for action in ("get_channel_info", "get_channel_history", "delete_message", "search_messages"):
                        with pytest.raises(Exception):
                            await self._exec(engine_env, "slack", action, {})
                    with pytest.raises(Exception):
                        await self._exec(engine_env, "slack", "update_message", {"channel_id": "c"})
        asyncio.run(run())

    def test_asana_actions(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                svc = MagicMock()
                svc.create_task = AsyncMock(return_value={"gid": "t1"})
                svc.get_tasks = AsyncMock(return_value=[])
                svc.get_projects = AsyncMock(return_value=[])
                svc.update_task = AsyncMock(return_value={})
                svc.add_task_comment = AsyncMock(return_value={})
                svc.get_workspaces = AsyncMock(return_value=[])
                svc.get_users = AsyncMock(return_value=[])
                svc.get_teams = AsyncMock(return_value=[])
                svc.search_tasks = AsyncMock(return_value=[])
                with patch("integrations.asana_service.asana_service", svc):
                    for action, params in [
                        ("create_task", {"name": "n", "workspace": "w"}),
                        ("get_tasks", {}),
                        ("get_projects", {"workspace": "w"}),
                        ("update_task", {"task_gid": "t1", "name": "x"}),
                        ("add_comment", {"task_gid": "t1", "text": "hi"}),
                        ("get_workspaces", {}),
                        ("get_users", {"workspace": "w"}),
                        ("get_teams", {"workspace": "w"}),
                        ("search_tasks", {"workspace": "w", "query": "q"}),
                    ]:
                        out = await self._exec(engine_env, "asana", action, params)
                        assert out["status"] == "success", action
                    out = await self._exec(engine_env, "asana", "create_project")
                    assert out["result"]["result"]["ok"] is False
        asyncio.run(run())

    def test_asana_missing_params_raise(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                with patch("integrations.asana_service.asana_service", MagicMock()):
                    with pytest.raises(Exception):
                        await self._exec(engine_env, "asana", "update_task", {})
                    with pytest.raises(Exception):
                        await self._exec(engine_env, "asana", "add_comment", {})
                    with pytest.raises(Exception):
                        await self._exec(engine_env, "asana", "get_users", {})
                    with pytest.raises(Exception):
                        await self._exec(engine_env, "asana", "search_tasks", {})
        asyncio.run(run())

    def test_discord_action(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                svc = MagicMock()
                svc.bot_token = "bot"
                svc.send_message = AsyncMock(return_value={"ok": True})
                with patch("integrations.discord_service.discord_service", svc):
                    out = await self._exec(engine_env, "discord", "send_message", {"channel_id": "c", "content": "hi"})
                    assert out["status"] == "success"
        asyncio.run(run())

    def test_hubspot_actions(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                svc = MagicMock()
                svc.access_token = "x"
                svc.create_contact = AsyncMock(return_value={"id": 1})
                svc.create_deal = AsyncMock(return_value={"id": 2})
                with patch("integrations.hubspot_service.HubSpotService", return_value=svc):
                    assert (await self._exec(engine_env, "hubspot", "create_contact", {"email": "a@b.c"}))["status"] == "success"
                    assert (await self._exec(engine_env, "hubspot", "create_deal", {"dealname": "d"}))["status"] == "success"
        asyncio.run(run())

    def test_salesforce_actions(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                sf_svc = MagicMock()
                sf_svc.create_client.return_value = MagicMock()
                sf_svc.create_lead = AsyncMock(return_value={"id": 1})
                sf_svc.create_contact = AsyncMock(return_value={"id": 2})
                sf_svc.create_opportunity = AsyncMock(return_value={"id": 3})
                with patch("integrations.salesforce_service.SalesforceService", return_value=sf_svc):
                    assert (await self._exec(engine_env, "salesforce", "create_lead", {"lastname": "L"}))["status"] == "success"
                    assert (await self._exec(engine_env, "salesforce", "create_contact", {"lastname": "L"}))["status"] == "success"
                    assert (await self._exec(engine_env, "salesforce", "create_opportunity", {"name": "o"}))["status"] == "success"
        asyncio.run(run())

    def test_salesforce_no_token_raises(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=None):
                with patch("integrations.salesforce_service.SalesforceService", MagicMock()):
                    with pytest.raises(Exception, match="authentication"):
                        await self._exec(engine_env, "salesforce", "create_lead", {"lastname": "L"})
        asyncio.run(run())

    def test_github_create_issue(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                gh_cls = MagicMock()
                gh_cls.return_value.create_issue.return_value = {"number": 1}
                with patch("integrations.github_service.GitHubService", gh_cls):
                    out = await self._exec(engine_env, "github", "create_issue",
                                           {"owner": "o", "repo": "r", "title": "t", "body": "b"})
                    assert out["status"] == "success"
        asyncio.run(run())

    def test_zoom_create_meeting(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                svc = MagicMock()
                svc.create_meeting = AsyncMock(return_value={"id": 1})
                with patch("integrations.zoom_service.ZoomService", return_value=svc):
                    assert (await self._exec(engine_env, "zoom", "create_meeting", {"topic": "t"}))["status"] == "success"
        asyncio.run(run())

    def test_notion_create_page(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                n_cls = MagicMock()
                n_cls.return_value.create_page.return_value = {"id": 1}
                with patch("integrations.notion_service.NotionService", n_cls):
                    out = await self._exec(engine_env, "notion", "create_page", {"parent": {"database_id": "d"}})
                    assert out["status"] == "success"
        asyncio.run(run())

    def test_outlook_actions(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                class _FakeOutlook:
                    async def send_email(self, **kw):
                        return {}
                    async def create_calendar_event(self, **kw):
                        return {}
                    async def get_user_emails(self, **kw):
                        return []
                    async def list_messages(self, **kw):
                        return []
                svc = _FakeOutlook()
                with patch("integrations.outlook_service.OutlookService", return_value=svc):
                    assert (await self._exec(engine_env, "outlook", "send_email", {"to_recipients": ["a@b.c"]}))["status"] == "success"
                    assert (await self._exec(engine_env, "outlook", "create_event", {}))["status"] == "success"
                    assert (await self._exec(engine_env, "outlook", "get_emails", {}))["status"] == "success"
                    assert (await self._exec(engine_env, "outlook", "list_messages", {}))["status"] == "success"
                    with pytest.raises(ValueError, match="Unknown Outlook action"):
                        await self._exec(engine_env, "outlook", "nope", {})
        asyncio.run(run())

    def test_jira_trello_actions(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                with patch("integrations.jira_service.JiraService") as j_cls:
                    j_svc = MagicMock(spec=["issue_create"])
                    j_svc.issue_create.return_value = {"key": "J-1"}
                    j_cls.return_value = j_svc
                    assert (await self._exec(engine_env, "jira", "issue_create", {}))["status"] == "success"
                    with pytest.raises(ValueError, match="Unknown Jira action"):
                        await self._exec(engine_env, "jira", "nope", {})
                with patch("integrations.trello_service.TrelloService") as t_cls:
                    t_svc = MagicMock(spec=["create_card"])
                    t_svc.create_card.return_value = {"id": 1}
                    t_cls.return_value = t_svc
                    assert (await self._exec(engine_env, "trello", "create_card", {}))["status"] == "success"
                    with pytest.raises(ValueError, match="Unknown Trello action"):
                        await self._exec(engine_env, "trello", "nope", {})
        asyncio.run(run())

    def test_stripe_actions(self, engine_env):
        async def run():
            with patch("core.workflow_engine.HAS_STRIPE", True), \
                 patch("core.workflow_engine.StripeService") as s_cls:
                s_svc = MagicMock(spec=["payment_intents_create"])
                s_svc.payment_intents_create.return_value = {"id": "pi_1"}
                s_cls.return_value = s_svc
                with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                    out = await self._exec(engine_env, "stripe", "payment_intents_create", {})
                    assert out["status"] == "success"
                with patch("core.workflow_engine.token_storage.get_token", return_value=None):
                    with pytest.raises(Exception, match="Stripe access token not found"):
                        await self._exec(engine_env, "stripe", "payment_intents_create", {})
                with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                    with pytest.raises(ValueError, match="Unknown Stripe action"):
                        await self._exec(engine_env, "stripe", "nope", {})
        asyncio.run(run())

    def test_shopify_actions(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                with patch("integrations.shopify_service.ShopifyService") as s_cls:
                    s_svc = MagicMock(spec=["orders_create"])
                    s_svc.orders_create.return_value = {"id": 1}
                    s_cls.return_value = s_svc
                    assert (await self._exec(engine_env, "shopify", "orders_create", {}))["status"] == "success"
                    async def _async_method(**kw):
                        return {"id": 2}
                    s_svc.async_method = _async_method
                    assert (await self._exec(engine_env, "shopify", "async_method", {}))["status"] == "success"
                    with pytest.raises(ValueError, match="Unknown Shopify action"):
                        await self._exec(engine_env, "shopify", "nope", {})
        asyncio.run(run())

    def test_zoho_actions(self, engine_env):
        async def run():
            with patch("core.workflow_engine.token_storage.get_token", return_value=TOKEN):
                for mod, svc_name, svc_key in [
                    ("integrations.zoho_crm_service", "ZohoCRMService", "zoho_crm"),
                    ("integrations.zoho_books_service", "ZohoBooksService", "zoho_books"),
                    ("integrations.zoho_inventory_service", "ZohoInventoryService", "zoho_inventory"),
                ]:
                    with patch(f"{mod}.{svc_name}") as z_cls:
                        z_svc = MagicMock(spec=["list_records"])
                        z_svc.list_records.return_value = []
                        z_cls.return_value = z_svc
                        assert (await self._exec(engine_env, svc_key, "list_records", {}))["status"] == "success"
                        async def _async_list(**kw):
                            return []
                        z_svc.async_list = _async_list
                        assert (await self._exec(engine_env, svc_key, "async_list", {}))["status"] == "success"
                        with pytest.raises(ValueError, match="Unknown"):
                            await self._exec(engine_env, svc_key, "nope", {})
        asyncio.run(run())

    def test_goal_management_actions(self, engine_env):
        async def run():
            with patch("core.goal_engine.goal_engine") as ge:
                ge.create_goal_from_text = AsyncMock(return_value=MagicMock(dict=lambda: {"id": 1}))
                out = await self._exec(engine_env, "goal_management", "create_goal",
                                       {"title": "t", "target_date": "2026-12-31T00:00:00Z"})
                assert out["status"] == "success"
                with pytest.raises(Exception, match="Missing title"):
                    await self._exec(engine_env, "goal_management", "create_goal", {})
                ge.check_for_escalations = AsyncMock(return_value=[])
                assert (await self._exec(engine_env, "goal_management", "check_escalations", {}))["status"] == "success"
        asyncio.run(run())

    def test_email_followup_detect(self, engine_env):
        async def run():
            with patch("core.email_followup_engine.followup_engine") as fe:
                fe.detect_missing_replies = AsyncMock(return_value=[])
                out = await self._exec(engine_env, "email_automation", "detect_followups", {"days_threshold": 5})
                assert out["status"] == "success"
                assert out["result"]["count"] == 0
        asyncio.run(run())

    def test_main_agent_error_dict(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            async def boom(context):
                raise AgentExecutionError(agent_id="a", reason="x")
            engine._execute_agent_with_mcp = boom
            out = await engine._execute_main_agent_action("do", {})
            assert out["status"] == "error"
        asyncio.run(run())

    def test_email_and_webhook_simulated(self, engine_env):
        async def run():
            assert (await self._exec(engine_env, "email", "send"))["status"] == "success"
            assert (await self._exec(engine_env, "webhook", "call"))["status"] == "success"
        asyncio.run(run())


class TestAgentWithMcpSuccess:
    def test_full_agent_execution(self, engine_env, tmp_path, monkeypatch):
        async def run():
            engine = engine_env["engine"]
            agent = MagicMock()
            agent.llm_provider = "openai"
            agent.llm_model = "gpt-4o"
            from contextlib import contextmanager

            @contextmanager
            def fake_db():
                db = MagicMock()
                db.query.return_value.filter.return_value.first.return_value = agent
                yield db

            handler = AsyncMock()
            handler.chat_completion.return_value = {"content": "done", "tool_calls": []}
            llm_svc = MagicMock()
            llm_svc.handler = handler

            with patch("core.database.get_db_session", fake_db), \
                 patch("core.llm_service.get_llm_service", return_value=llm_svc):
                out = await engine._execute_agent_with_mcp({
                    "action": "do", "input_data": {"k": 1},
                    "mcp_connections": {}, "available_tools": [
                        {"name": "t1", "description": "d", "input_schema": {}}],
                    "agent_id": "agent-1",
                })
            assert out["success"] is True
            assert out["execution_method"] == "main_agent_with_mcp"
            assert out["tools_available"] == 1
        asyncio.run(run())

    def test_llm_failure_falls_back(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            agent = MagicMock()
            agent.llm_provider = "openai"
            agent.llm_model = "gpt-4o"
            from contextlib import contextmanager

            @contextmanager
            def fake_db():
                db = MagicMock()
                db.query.return_value.filter.return_value.first.return_value = agent
                yield db

            handler = MagicMock()
            handler.chat_completion = AsyncMock(side_effect=RuntimeError("llm down"))
            llm_svc = MagicMock()
            llm_svc.handler = handler

            with patch("core.database.get_db_session", fake_db), \
                 patch("core.llm_service.get_llm_service", return_value=llm_svc):
                out = await engine._execute_agent_with_mcp({
                    "action": "do", "input_data": {}, "mcp_connections": {},
                    "available_tools": [], "agent_id": "agent-1",
                })
            assert out["success"] is True
            assert out["execution_method"] == "fallback"
        asyncio.run(run())


# ============================================================================
# workflow_engine — remaining edge paths
# ============================================================================

class TestEngineEdges:
    def test_publish_orchestration_unknown_event(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            engine._publish_orchestration_event("NOT_A_REAL_EVENT", "w", "e")
            assert True
        asyncio.run(run())

    def test_publish_orchestration_bus_exception(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            engine_env["bus"].publish.side_effect = RuntimeError("bus down")
            engine._publish_orchestration_event("WORKFLOW_STARTED", "w", "e")
            assert True
        asyncio.run(run())

    def test_graph_missing_input_pauses(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _node_workflow(
                [{"id": "a", "config": {"service": "email", "action": "send",
                                        "parameters": {"x": "${input.missing}"}}}],
            )
            eid = await engine.state_manager.create_execution("wf-g", {})
            await engine.state_manager.update_execution_status(eid, "RUNNING")
            state = await engine.state_manager.get_execution_state(eid)
            await engine._execute_workflow_graph(eid, wf, state, engine_env["ws"], "u1",
                                                 datetime.now(timezone.utc))
            final = await engine.state_manager.get_execution_state(eid)
            assert final["status"] == "PAUSED"
        asyncio.run(run())

    def test_run_execution_outer_exception_fails(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = {"id": "wf-1", "steps": [{"service": "email"}], "created_by": "u1"}
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            state = await engine.state_manager.get_execution_state(eid)
            assert state["status"] == "FAILED"
        asyncio.run(run())

    def test_governance_exception_fails_open(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            raising = MagicMock()
            raising.can_perform_action = AsyncMock(side_effect=RuntimeError("gov down"))

            class RaisingFactory:
                @staticmethod
                def get_governance_service(db, tenant_id="default"):
                    return raising

            import core.workflow_engine as wfmod
            old = wfmod.ServiceFactory
            wfmod.ServiceFactory = RaisingFactory
            try:
                wf = _workflow([_step("s1")])
                eid = await engine.start_workflow(wf, {})
                await asyncio.gather(*list(engine._background_tasks))
                state = await engine.state_manager.get_execution_state(eid)
                assert state["status"] == "COMPLETED"
            finally:
                wfmod.ServiceFactory = old
        asyncio.run(run())

    def test_non_system_agent_lookup(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            wf = _workflow([_step("s1")], agent_id="agent-1")
            eid = await engine.start_workflow(wf, {})
            await asyncio.gather(*list(engine._background_tasks))
            assert engine_env["sm"].executions[eid]["status"] == "COMPLETED"
        asyncio.run(run())

    def test_marketplace_failure_tracking(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            with patch("core.workflow_engine.MarketplaceUsageTracker.track_usage") as tu:
                wf = _workflow([_step("s1", service="slack", action="chat_postMessage")],
                               created_from_template="tpl-9")
                eid = await engine.start_workflow(wf, {})
                await asyncio.gather(*list(engine._background_tasks))
                assert engine_env["sm"].executions[eid]["status"] == "FAILED"
                tu.assert_called_once()
        asyncio.run(run())

    def test_condition_non_bool_result(self, engine_env):
        eng = engine_env["engine"]
        state = {"outputs": {"s1": {"count": 5}}}
        assert eng._evaluate_condition("${s1.count}", state) is True

    def test_condition_safe_eval_error_path(self, engine_env):
        eng = engine_env["engine"]
        assert eng._evaluate_condition("${s1.count} < ${s2.count}", {"outputs": {}}) is False

    def test_resolve_parameters_nested_path_through_scalar(self, engine_env):
        eng = engine_env["engine"]
        state = {"outputs": {"s1": 5}}
        assert eng._get_value_from_path("s1.deep.key", state) is None

    def test_load_workflow_corrupt_json(self, engine_env, tmp_path, monkeypatch):
        bad = tmp_path / "workflows.json"
        bad.write_text("{not json")
        monkeypatch.setattr("core.workflow_engine.os.path.dirname", lambda p: str(tmp_path))
        with patch("core.workflow_engine.os.path.exists", return_value=True), \
             patch("builtins.open", return_value=open(str(bad))):
            assert engine_env["engine"]._load_workflow_by_id("w1") is None

    def test_subworkflow_polls_running_then_completes(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            engine._load_workflow_by_id = lambda wid: {"id": wid, "steps": []}
            engine.start_workflow = AsyncMock(return_value="sub-exec")
            statuses = iter(["RUNNING", "PENDING", "COMPLETED"])
            async def fake_state(eid):
                return {"status": next(statuses), "outputs": {}}
            engine.state_manager.get_execution_state = fake_state
            out = await engine._execute_workflow_action("run", {"workflow_id": "wf-sub"})
            assert out["status"] == "success"
        asyncio.run(run())

    def test_arbor_refinement_wrapper_failure(self, engine_env):
        async def run():
            engine = engine_env["engine"]
            async def boom(wf, data):
                raise RuntimeError("start failed")
            engine.start_workflow = boom
            with patch("core.hypothesis_tree_endpoints._persist_tree"):
                with pytest.raises(RuntimeError):
                    await engine.run_workflow_with_arbor_refinement("t1", _workflow([_step("s1")]), {})
        asyncio.run(run())

    def test_goal_management_update_subtask(self, engine_env):
        async def run():
            from core.goal_engine import goal_engine
            goal = MagicMock()
            goal.id = "g1"
            goal.dict.return_value = {"id": "g1", "sub_tasks": [], "status": "success"}
            sub = MagicMock()
            sub.id = "st1"
            goal.sub_tasks = [sub]
            with patch("core.goal_engine.goal_engine.goals", {"g1": goal}), \
                 patch("core.goal_engine.goal_engine.update_goal_progress", new=AsyncMock()):
                out = await engine_env["engine"]._execute_goal_management_action(
                    "update_subtask", {"goal_id": "g1", "sub_task_id": "st1", "status": "done"})
                assert out["status"] == "success"
                sub.status = "done"
                with pytest.raises(ValueError, match="not found"):
                    await engine_env["engine"]._execute_goal_management_action(
                        "update_subtask", {"goal_id": "gx", "sub_task_id": "st1", "status": "done"})
        asyncio.run(run())
