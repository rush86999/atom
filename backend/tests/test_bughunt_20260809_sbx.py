"""Bug hunt — sandbox gate coverage + KillRun propagation (2026-08-09).

TDD red tests for four enforcement gaps in the P9 sandbox layer:

T1  workflow_engine._execute_mcp_action dispatches via
    ``mcp_service.execute_tool`` directly, bypassing the P9 shared sandbox
    gate (and the P2 capability gate) that ``call_tool`` applies to every
    other dispatch path. An agent-invoked workflow run with a sandbox
    context executes MCP tools ungated.

T2  AtomMetaAgent.execute() never threads ``run_id``/``tier_at_issuance``
    into the dispatch context, so ``_meta_agent_sandbox_check`` (and the
    shared gate inside ``call_tool``) returns None — the sandbox is inert
    on the primary agent/chat surface.

T3a _execute_tool_with_governance swallows KillRunAborted in its catch-all
    (``except Exception`` -> "Tool error. Please try again."), so a
    tripwire kill never aborts the run; the loop keeps iterating and the
    run finalizes as "success".

T3b The parallel gather path (``asyncio.gather(..., return_exceptions=True)``)
    converts KillRunAborted into a "Tool error" record; the execute() body
    catch-all also re-raises instead of finalizing the killed run as
    ``killed_sandbox``.
"""
import asyncio
import pytest
from unittest.mock import MagicMock

pytestmark = pytest.mark.asyncio


class _Stub:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeQuery:
    def __init__(self, session, model):
        self._session = session
        self._model = model

    def filter(self, *a, **k):
        return self

    def with_for_update(self):
        return self

    def first(self):
        from core.models import AgentExecution, AgentRegistry, Workspace
        if self._model is Workspace:
            return self._session._workspace
        if self._model is AgentRegistry:
            return self._session._agent
        if self._model is AgentExecution:
            return self._session._execution
        return None


class _FakeSession:
    """Minimal SessionLocal stand-in: query-by-model + no-op write surface."""

    def __init__(self, workspace=None, agent=None, execution=None):
        self._workspace = workspace or _Stub(tenant_id="default")
        self._agent = agent or _Stub(
            id="atom_main", name="Atom", category="Meta",
            status="AUTONOMOUS", confidence_score=1.0,
        )
        self._execution = execution or _Stub(
            id="exec-1", status="running", result_summary="",
            error_message=None, duration_seconds=None, completed_at=None,
        )
        self.added = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def query(self, model):
        return _FakeQuery(self, model)

    def add(self, row):
        self.added.append(row)

    def commit(self):
        pass

    def refresh(self, row):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _make_atom_meta(monkeypatch):
    """Hermetic AtomMetaAgent instance with DB/LLM/tool surfaces stubbed."""
    from core import atom_meta_agent as am

    fake_db = _FakeSession()
    monkeypatch.setattr(am, "SessionLocal", lambda: fake_db)

    atom = am.AtomMetaAgent.__new__(am.AtomMetaAgent)
    atom.workspace_id = "default"
    atom.tenant_id = "default"
    atom.user = None
    atom.world_model = _Stub(
        recall_experiences=lambda *a, **k: _coro({}),
        recall_episodes=lambda *a, **k: _coro({}),
    )
    atom.mcp = _Stub(
        get_all_tools=lambda *a, **k: _coro([]),
        search_tools=lambda *a, **k: _coro([]),
        call_tool=lambda *a, **k: _coro("tool ok"),
    )
    atom.llm = _Stub()
    atom.canvas_provider = _Stub()
    atom.session_tools = []
    atom.spawned_agents = {}
    atom.queen = None
    atom.graduation_service = _Stub(
        get_maturity=MagicMock(return_value="autonomous"),
        record_usage=MagicMock(),
    )
    atom.orchestrator = _Stub()
    return atom


# ===========================================================================
# T1 — workflow MCP action must dispatch through the gated call_tool
# ===========================================================================


async def test_workflow_mcp_action_routes_through_gated_call_tool(monkeypatch):
    """RED: ``_execute_mcp_action`` executes the tool via ``execute_tool``
    directly, skipping the P9 sandbox gate + P2 capability gate that
    ``call_tool`` applies. The workflow's run context (execution_id,
    workspace_id, tenant_id) must reach the gated entry point."""
    from core import workflow_engine as we

    monkeypatch.setattr(we, "get_state_manager", lambda: _Stub())
    engine = we.WorkflowEngine(max_concurrent_steps=1)

    from integrations.mcp_service import mcp_service

    calls = {}

    async def _fake_call_tool(tool_name, arguments, context=None):
        calls["call_tool"] = (tool_name, arguments, context)
        return {"ok": True, "tool": tool_name}

    async def _fake_execute_tool(server_id, tool_name, arguments, context=None):
        calls["execute_tool"] = (server_id, tool_name, arguments)
        return {"ok": True, "tool": tool_name}

    monkeypatch.setattr(mcp_service, "call_tool", _fake_call_tool)
    monkeypatch.setattr(mcp_service, "execute_tool", _fake_execute_tool)

    step = {
        "execution_id": "wf-run-1",
        "workspace_id": "default",
        "tenant_id": "t1",
    }
    result = await engine._execute_mcp_action(
        "danger_tool",
        {"server_id": "local-tools", "tool_name": "danger_tool",
         "arguments": {"path": "/etc/passwd"}},
        connection_id="c1",
        step=step,
    )

    assert "execute_tool" not in calls, (
        "direct execute_tool dispatch bypasses the sandbox gate"
    )
    assert "call_tool" in calls
    tool_name, arguments, context = calls["call_tool"]
    assert tool_name == "danger_tool"
    assert context is not None and context.get("run_id") == "wf-run-1"
    assert context.get("workspace_id") == "default"
    assert result["status"] == "success"


# ===========================================================================
# T2 — AtomMetaAgent.execute() must thread run_id + tier into context
# ===========================================================================


async def test_meta_agent_execute_threads_run_id_and_tier(monkeypatch):
    """RED: execute() leaves the dispatch context without ``run_id`` or
    ``tier_at_issuance``, so ``_meta_agent_sandbox_check`` returns None
    (no policy in scope) and the P9 gate is inert on the primary agent
    surface. After the fix the sandbox check must engage."""
    from core import atom_meta_agent as am

    atom = _make_atom_meta(monkeypatch)

    # Stub out the parts of execute() that would hit real services.
    async def _classify_route(self, request, tenant_id=None):
        from ai.nlp_engine import RouteCategory
        return _Stub(category=RouteCategory.ONE_OFF, reasoning="test")

    monkeypatch.setattr(am.NaturalLanguageEngine, "classify_route", _classify_route)
    monkeypatch.setattr(
        "core.field_guide_service.get_field_guide_service",
        lambda: _Stub(get_field_guide_context=lambda ws: ""),
    )
    monkeypatch.setattr(atom, "_check_budget_before_react", lambda: _coro(
        {"allowed": True, "reason": None}))
    monkeypatch.setattr(atom, "_record_execution", lambda *a, **k: _coro(None))
    monkeypatch.setattr(atom, "_get_atom_registry", lambda: _Stub(
        id="atom_main", name="Atom", category="Meta",
        status="AUTONOMOUS", confidence_score=1.0,
    ))

    async def _react_step(**kwargs):
        return am.ReActStep(final_answer="done", thought="done")

    monkeypatch.setattr(atom, "_react_step", _react_step)

    context = {"user_id": "u1"}
    await atom.execute(request="hello", context=context)

    assert context.get("run_id"), "execute() must set run_id in dispatch context"
    assert context.get("execution_id"), "execute() must set execution_id"
    assert context.get("tier_at_issuance"), "execute() must set tier_at_issuance"

    # The sandbox check must now engage on this context (not return None).
    from core.sandbox_policy import ALLOWED
    decision = am._meta_agent_sandbox_check(
        "browser_click", {}, context,
    )
    assert decision is not None, (
        "sandbox check must engage once run_id/tier are in context"
    )
    assert decision.decision == ALLOWED  # AUTONOMOUS whitelist is "*"


# ===========================================================================
# T3a — KillRunAborted must propagate out of the tool-dispatch method
# ===========================================================================


async def test_killrun_aborted_propagates_from_tool_dispatch(monkeypatch):
    """RED: when a killed run's sandbox guard raises KillRunAborted inside
    ``_execute_tool_with_governance``, the catch-all converts it to a
    harmless "Tool error" string — the run never aborts, keeps paying LLM
    cost, and finalizes as success. KillRunAborted must propagate."""
    from core import atom_meta_agent as am
    from core.sandbox_killrun import KillRunAborted

    atom = _make_atom_meta(monkeypatch)

    from core.agent_governance_service import AgentGovernanceService

    async def _can_perform_action_async(self, agent_id, tool_name):
        return {"allowed": True, "action_complexity": 1}

    monkeypatch.setattr(
        AgentGovernanceService, "can_perform_action_async",
        _can_perform_action_async,
    )

    def _raise_kill(tool_name, args, context):
        raise KillRunAborted("run killed by sandbox: tripwire fired")

    monkeypatch.setattr(am, "_meta_agent_sandbox_check", _raise_kill)

    with pytest.raises(KillRunAborted):
        await atom._execute_tool_with_governance(
            "browser_click", {}, {}, step_callback=None,
        )


# ===========================================================================
# T3b — a killed run finalizes as killed_sandbox (no re-raise, no success)
# ===========================================================================


async def test_meta_agent_killed_run_finalizes_killed_sandbox(monkeypatch):
    """RED: a KillRunAborted escaping the tool loop is caught by the
    execute() catch-all which re-raises (500 at the API) instead of
    finalizing the run as ``killed_sandbox``. It must return a killed
    result payload with status killed_sandbox."""
    from core import atom_meta_agent as am
    from core.sandbox_killrun import KillRunAborted

    atom = _make_atom_meta(monkeypatch)

    async def _classify_route(self, request, tenant_id=None):
        from ai.nlp_engine import RouteCategory
        return _Stub(category=RouteCategory.ONE_OFF, reasoning="test")

    monkeypatch.setattr(am.NaturalLanguageEngine, "classify_route", _classify_route)
    monkeypatch.setattr(
        "core.field_guide_service.get_field_guide_service",
        lambda: _Stub(get_field_guide_context=lambda ws: ""),
    )
    monkeypatch.setattr(atom, "_check_budget_before_react",
                        lambda: _coro({"allowed": True, "reason": None}))
    monkeypatch.setattr(atom, "_record_execution", lambda *a, **k: _coro(None))
    monkeypatch.setattr(atom, "_get_atom_registry", lambda: _Stub(
        id="atom_main", name="Atom", category="Meta",
        status="AUTONOMOUS", confidence_score=1.0,
    ))

    def _react_step(**kwargs):
        return _coro(am.ReActStep(
            thought="killed", action=am.ToolCall(tool="browser_click", params={}),
        ))

    monkeypatch.setattr(atom, "_react_step", _react_step)

    async def _killed_tool(tool_name, args, context, step_callback=None,
                           pre_approved=False):
        raise KillRunAborted("run killed by sandbox: tripwire fired")

    monkeypatch.setattr(atom, "_execute_tool_with_governance", _killed_tool)

    result = await atom.execute(request="do the thing", context={"user_id": "u1"})

    assert result.get("status") == "killed_sandbox", (
        "killed run must finalize as killed_sandbox, got %r" % result.get("status")
    )
    assert "killed by sandbox" in str(result.get("final_output", ""))


def _coro(value):
    async def _inner():
        return value
    return _inner()
