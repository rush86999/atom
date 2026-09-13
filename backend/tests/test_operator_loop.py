"""Computer-use operator — loop rails + surface wiring tests (Sept 2026).

Pins the OperatorLoop contract (the same rails LuxModel.run_task
established for the desktop path — see test_computer_use_gpt6_astra.py),
the browser session's guardrails, the goal-run computer_use_work step,
and the legacy browser bridge. All with fakes: no browser, no LLM, no
live DB.
"""

import os
os.environ["TESTING"] = "1"

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.operator.loop import (
    OperatorAction, OperatorLoop, JsonVisionDecider, _extract_json)
from core.operator.session import (
    Observation, OperatorSession, _guardrail_hit, encode_screenshot_for_model)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeBackend:
    """Scripted backend: fixed observation, records executed actions."""

    def __init__(self, *, actions_ok=True, observe_error=None):
        self.observation = Observation(
            screenshot_b64="abc", url="https://example.test/page",
            title="Example", page_text="hello world",
            viewport=(1920, 1080), error=observe_error)
        self.actions_ok = actions_ok
        self.executed = []
        self.closed = False

    async def observe(self):
        return self.observation

    async def execute(self, action):
        self.executed.append(action)
        if action.get("parameters", {}).get("fail"):
            return {"success": False, "action_type": action["action_type"],
                    "error": "scripted failure"}
        if action.get("parameters", {}).get("blocked"):
            return {"success": False, "action_type": action["action_type"],
                    "blocked_by_governance": True, "error": "policy says no"}
        return {"success": self.actions_ok, "action_type": action["action_type"]}

    async def close(self):
        self.closed = True


class ScriptedDecider:
    """Returns queued decisions in order; records (task, history) calls."""

    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []

    async def decide(self, task, observation, history=None):
        self.calls.append((task, list(history or [])))
        return self.decisions.pop(0) if self.decisions else {"done": True}


def _action(action_type, **params):
    return {"action": OperatorAction(action_type, params, 0.9, action_type)}


# ---------------------------------------------------------------------------
# Loop rails
# ---------------------------------------------------------------------------

async def test_loop_completes_on_done():
    backend = FakeBackend()
    decider = ScriptedDecider([
        _action("click", coordinates=[100, 200]),
        {"done": True, "action": None, "summary": "did the thing",
         "reasoning": ""},
    ])
    result = await OperatorLoop(backend=backend, decider=decider,
                                step_settle_seconds=0).run("do something")
    assert result["done"] is True
    assert result["summary"] == "did the thing"
    assert result["success"] is True
    assert result["steps"] == 1
    assert backend.executed == [
        {"action_type": "click", "parameters": {"coordinates": [100, 200]}}]
    # history reached the second decision
    assert decider.calls[1][1] == ["1. click({\"coordinates\": [100, 200]}) -> ok"]


async def test_loop_step_budget_bounds_runs():
    decisions = [_action("scroll", direction="down", amount=2)] * 50
    backend = FakeBackend()
    result = await OperatorLoop(backend=backend,
                                decider=ScriptedDecider(decisions),
                                max_steps=4,
                                step_settle_seconds=0).run("forever task")
    assert result["done"] is False
    assert result["steps"] == 4  # budget, not the 50 queued decisions
    # budget exhaustion is explicitly marked — distinguishable from a crash
    assert result["budget_exhausted"] is True
    assert result["stopped"] is False
    assert result["blocked"] is False


async def test_loop_aborts_after_three_consecutive_failures():
    decisions = [_action("click", fail=1)] * 10
    result = await OperatorLoop(backend=FakeBackend(actions_ok=False),
                                decider=ScriptedDecider(decisions),
                                max_steps=15,
                                step_settle_seconds=0).run("doom")
    assert result["done"] is False
    assert result["steps"] == 3


async def test_loop_governance_block_is_hard_stop():
    decisions = [
        _action("click", blocked=1),
        _action("click"),  # must never execute
    ]
    backend = FakeBackend()
    result = await OperatorLoop(backend=backend,
                                decider=ScriptedDecider(decisions),
                                step_settle_seconds=0).run("risky")
    assert result["blocked"] is True
    assert "policy says no" in result["error"]
    assert result["steps"] == 1
    assert len(backend.executed) == 1


async def test_loop_first_step_unparseable_fails():
    decider = ScriptedDecider([None])
    result = await OperatorLoop(backend=FakeBackend(), decider=decider,
                                step_settle_seconds=0).run("x")
    assert result["success"] is False
    assert "no action could be decided" in result["error"]
    # single exit point: same keys as every other terminal state
    for key in ("actions", "steps", "done", "stopped", "blocked",
                "budget_exhausted", "summary", "final_url", "final_title",
                "execution_time", "timestamp"):
        assert key in result, key


async def test_loop_exception_path_has_full_result_shape():
    class ExplodingBackend(FakeBackend):
        async def execute(self, action):
            raise RuntimeError("boom")
    result = await OperatorLoop(
        backend=ExplodingBackend(),
        decider=ScriptedDecider([_action("click")]),
        step_settle_seconds=0).run("x")
    for key in ("actions", "steps", "done", "stopped", "blocked",
                "budget_exhausted", "summary", "final_url", "final_title",
                "execution_time", "timestamp"):
        assert key in result, key
    assert result["error"] == "boom"


async def test_loop_publishes_progress_mid_run():
    snapshots: list = []

    class RecorderDecider:
        def __init__(self):
            self.at_decide = []

        async def decide(self, task, observation, history=None):
            self.at_decide.append(
                (len(snapshots),
                 len(snapshots[-1]["steps"]) if snapshots else 0))
            if len(self.at_decide) == 1:
                return _action("click", coordinates=[1, 2])
            return {"done": True, "action": None, "summary": "ok"}

    decider = RecorderDecider()
    result = await OperatorLoop(backend=FakeBackend(), decider=decider,
                                progress_callback=snapshots.append,
                                step_settle_seconds=0).run("t")
    assert result["done"] is True
    # the SECOND decision already saw step 1 published — mid-run, not
    # only after the loop exits.
    assert decider.at_decide[1][0] >= 1
    assert decider.at_decide[1][1] == 1
    assert snapshots[-1]["last_screenshot_b64"] == "abc"
    assert snapshots[-1]["last_url"] == "https://example.test/page"


async def test_loop_stop_event_halts_between_steps():
    stop = asyncio.Event()
    stop.set()
    decisions = [_action("click")] * 5
    result = await OperatorLoop(backend=FakeBackend(),
                                decider=ScriptedDecider(decisions),
                                stop_event=stop,
                                step_settle_seconds=0).run("x")
    assert result["stopped"] is True
    assert result["steps"] == 0


async def test_loop_observation_error_breaks():
    backend = FakeBackend(observe_error="RuntimeError: browser died")
    result = await OperatorLoop(backend=backend,
                                decider=ScriptedDecider([]),
                                step_settle_seconds=0).run("x")
    assert result["success"] is False
    assert "browser died" in result["error"]


# ---------------------------------------------------------------------------
# Decider parsing (no LLM)
# ---------------------------------------------------------------------------

def test_extract_json_variants():
    assert _extract_json('{"done": true}')["done"] is True
    assert _extract_json('prose ```json\n{"done": false}\n``` more')[
        "done"] is False
    assert _extract_json('before {"a": {"b": 1}} after')["a"]["b"] == 1
    assert _extract_json("no json here") is None
    assert _extract_json("") is None


def test_decider_parses_model_reply():
    decider = JsonVisionDecider()
    reply = json.dumps({
        "reasoning": "go",
        "action": {"action_type": "navigate",
                   "parameters": {"url": "https://x.test"},
                   "confidence": 0.8},
        "done": False,
        "summary": "",
    })
    data = _extract_json(reply)
    assert data["action"]["action_type"] == "navigate"


# ---------------------------------------------------------------------------
# Session guardrails + helpers (no browser)
# ---------------------------------------------------------------------------

def test_guardrail_hits_money_keywords():
    assert _guardrail_hit("navigate", {"url": "https://shop.test/checkout"}) \
        == "checkout"
    assert _guardrail_hit("click", {"selector": "#pay-now"}) == "pay"
    assert _guardrail_hit("type", {"text": "hello"}) is None


def test_encode_screenshot_passthrough_without_pil(monkeypatch):
    import core.operator.session as session_mod
    monkeypatch.setattr(session_mod, "PIL_AVAILABLE", False)
    # raw base64 passthrough when PIL is unavailable
    out = encode_screenshot_for_model(b"\x89PNG fake")
    assert out  # non-empty, no crash


async def test_session_execute_unknown_action():
    session = OperatorSession()
    result = await session.execute({"action_type": "teleport", "parameters": {}})
    assert result["success"] is False
    assert "unknown action type" in result["error"]


async def test_session_execute_guardrail_blocks_checkout():
    # Audits persist WITHOUT a caller-supplied db (the session opens its
    # own short-lived one) — verified against the TESTING=1 scratch DB.
    from core.database import engine, get_db_session
    from core.models import BrowserAudit
    from core.models_registration import Base
    Base.metadata.create_all(bind=engine, checkfirst=True,
                             tables=[BrowserAudit.__table__])
    with get_db_session() as db:
        before = db.query(BrowserAudit).filter(
            BrowserAudit.user_id == "u-audit").count()

    session = OperatorSession(user_id="u-audit", agent_id="a-audit")
    result = await session.execute({
        "action_type": "navigate",
        "parameters": {"url": "https://shop.test/checkout?pay=1"}})
    assert result["success"] is False
    assert result.get("blocked_by_guardrail") is True

    with get_db_session() as db:
        rows = db.query(BrowserAudit).filter(
            BrowserAudit.user_id == "u-audit").all()
        assert len(rows) - before >= 1
        assert any(r.action == "operator_navigate"
                   and (r.metadata_json or {}).get("status") == "guardrail_blocked"
                   for r in rows)


def test_guardrail_scopes_free_text_vs_structured_fields():
    # Structured fields (url/selector) carry the full money keyword list.
    assert _guardrail_hit("navigate",
                          {"url": "https://shop.test/checkout"}) == "checkout"
    assert _guardrail_hit("click", {"selector": "#pay-now"}) == "pay"
    # Free text (typed values) is page content, not a money target: a tax
    # line or a payments@ email must NOT abort the task.
    assert _guardrail_hit("type", {"text": "Total tax: $5"}) is None
    assert _guardrail_hit("type",
                          {"text": "email payments@vendor.com"}) is None
    assert _guardrail_hit("type", {"text": "transfer memo: lunch"}) is None
    # ...but typing a 16-digit card number is high-signal and hard-stops.
    assert _guardrail_hit("type", {"text": "4111 1111 1111 1111"}) is not None
    assert _guardrail_hit("type", {"text": "4111111111111111"}) is not None
    assert _guardrail_hit("type", {"text": "hello"}) is None


async def test_session_execute_governance_hard_stop():
    gov = AsyncMock(return_value=False)
    session = OperatorSession(governance_callback=gov)
    result = await session.execute({
        "action_type": "click", "parameters": {"coordinates": [1, 2]}})
    assert result["success"] is False
    assert result.get("blocked_by_governance") is True
    gov.assert_awaited_once_with(action_type="click",
                                 details={"coordinates": [1, 2]})


# ---------------------------------------------------------------------------
# Goal-run computer_use_work step
# ---------------------------------------------------------------------------

class _FakeService:
    """Just enough GoalRunService for the executor."""
    workspace_id = "ws"
    tenant_id = "tn"

    def __init__(self):
        self.waits = []
        self.decisions = []

    def set_wait(self, run_id, spec):
        self.waits.append((run_id, spec))

    def append_decision(self, run_id, entry):
        self.decisions.append((run_id, entry))


async def test_goal_run_computer_use_work_step(monkeypatch):
    from core.goals.goal_run_executors import GoalRunExecutors

    captured = {}

    async def fake_start(**kwargs):
        captured.update(kwargs)
        return {"success": True, "operator_run_id": "operator-abc",
                "status": "running"}

    monkeypatch.setattr("core.operator.tools.operator_start_task",
                        fake_start)

    service = _FakeService()
    executors = GoalRunExecutors(service)
    step = {"id": "s1", "kind": "computer_use_work",
            "directive": "download the Q3 report",
            "start_url": "https://reports.test"}
    run = {"id": "run-1", "workspace_id": "ws", "tenant_id": "tn",
           "created_by": "user-1", "agent_id": "agent-1",
           "plan": [step], "cursor": "s1"}

    result = await executors.execute(run, {"decision": "ADVANCE",
                                           "target_step": "s1"})
    # ADVANCE routes the current step by kind
    assert result["operator_run_id"] == "operator-abc"
    assert captured["goal_run_id"] == "run-1"
    assert captured["goal_run_step_id"] == "s1"
    assert captured["agent_id"] == "agent-1"
    assert captured["task"] == "download the Q3 report"
    # the run waits on the operator's done event, matched by run id
    # (spec may carry additive keys such as the deadline watchdog — only
    # the event + match contract is pinned here)
    assert len(service.waits) == 1
    wait_run, wait_spec = service.waits[0]
    assert wait_run == "run-1"
    assert wait_spec["event"] == "operator_task_done"
    assert wait_spec["match"] == {"operator_run_id": "operator-abc"}


async def test_goal_run_computer_use_work_start_failure(monkeypatch):
    from core.goals.goal_run_executors import GoalRunExecutors

    async def fake_start(**kwargs):
        return {"success": False, "error": "agent not permitted"}

    monkeypatch.setattr("core.operator.tools.operator_start_task",
                        fake_start)
    service = _FakeService()
    executors = GoalRunExecutors(service)
    step = {"id": "s1", "kind": "computer_use_work"}
    run = {"id": "run-1", "agent_id": "agent-1",
           "plan": [step], "cursor": "s1"}

    result = await executors.execute(run, {"decision": "ADVANCE",
                                           "target_step": "s1"})
    assert result["error"] == "agent not permitted"
    assert service.waits == []  # no wait when the operator never started


# ---------------------------------------------------------------------------
# Operator run registry + tool surface (fakes; no browser spawned)
# ---------------------------------------------------------------------------

async def test_operator_start_task_spawns_and_tracks(monkeypatch):
    import core.operator.tools as op_tools

    async def fake_run_body(state, start_url, max_steps):
        state.status = "done"
        state.result = {"done": True, "success": True, "summary": "ok"}

    monkeypatch.setattr(op_tools, "_run_operator_task", fake_run_body)
    monkeypatch.setattr(op_tools, "_governance_allows",
                        AsyncMock(return_value=True))

    result = await op_tools.operator_start_task(
        task="find the pricing page", user_id="u1", agent_id="a1")
    assert result["success"] is True
    run_id = result["operator_run_id"]

    # let the spawned background task finish
    for _ in range(20):
        await asyncio.sleep(0)
    status = op_tools.operator_get_status(run_id, user_id="u1")
    assert status["status"] == "done"
    assert status["result"]["summary"] == "ok"

    shot = op_tools.operator_get_screenshot(run_id, user_id="u1")
    assert shot["success"] is True


async def test_operator_start_task_governance_denied(monkeypatch):
    import core.operator.tools as op_tools
    monkeypatch.setattr(op_tools, "_governance_allows",
                        AsyncMock(return_value=False))
    result = await op_tools.operator_start_task(task="x", user_id="u1",
                                                agent_id="a1")
    assert result["success"] is False
    assert "not permitted" in result["error"]


async def test_governance_entry_gate_opens_own_db(monkeypatch):
    # The entry gate must consult governance WITHOUT a caller-supplied db
    # (MCP dispatch never forwards one) — it opens its own session.
    import core.operator.tools as op_tools

    monkeypatch.setattr(op_tools.FeatureFlags,
                        "should_enforce_governance",
                        staticmethod(lambda surface: True))

    class _FakeResolver:
        def __init__(self, db):
            pass

        async def resolve_agent_for_request(self, user_id,
                                            requested_agent_id,
                                            action_type):
            return (type("Agent", (), {"id": "agent-1"})(), None)

    class _FakeGovernance:
        def __init__(self, db):
            pass

        def can_perform_action(self, agent_id, action_type):
            return {"allowed": False, "reason": "browser blocked"}

    import core.agent_context_resolver as acr
    import core.service_factory as sf
    monkeypatch.setattr(acr, "AgentContextResolver", _FakeResolver)
    monkeypatch.setattr(sf.ServiceFactory, "get_governance_service",
                        staticmethod(lambda db: _FakeGovernance(db)))

    assert await op_tools._governance_allows(None, "u1", "a1") is False


def test_operator_status_user_isolation():
    import core.operator.tools as op_tools
    state = op_tools.get_operator_run_registry().create(
        task="t", user_id="owner-1")
    ok = op_tools.operator_get_status(state.run_id, user_id="owner-1")
    assert ok["success"] is True
    denied = op_tools.operator_get_status(state.run_id, user_id="intruder")
    assert denied["success"] is False


def test_operator_reads_require_context_identity():
    # No-context callers are DENIED, not served: identity comes from the
    # dispatch context only (mcp_service strips argument-supplied
    # user_id/agent_id for operator_* tools).
    import core.operator.tools as op_tools
    state = op_tools.get_operator_run_registry().create(
        task="t", user_id="owner-1")
    assert op_tools.operator_get_status(state.run_id)["success"] is False
    assert op_tools.operator_get_screenshot(
        state.run_id)["success"] is False


async def test_operator_identity_args_stripped_at_mcp_dispatch():
    # A model-supplied user_id argument must never shape run ownership:
    # dispatch strips it; context identity (when present) is what flows in.
    import integrations.mcp_service as mcp_mod

    captured = {}

    async def fake_get_status(run_id, user_id=None):
        captured.update({"run_id": run_id, "user_id": user_id})
        return {"success": True}

    class _Reg:
        def get(self, name):
            return name == "operator_get_status"

        def get_function(self, name):
            return fake_get_status

    svc = mcp_mod.MCPService.__new__(mcp_mod.MCPService)
    svc.initialized = True
    svc.config = {}
    svc.tenant_id = "default"
    svc.active_servers = {}
    svc.search_api_key = None
    with patch.object(mcp_mod, "get_tool_registry", return_value=_Reg()):
        result = await svc.execute_tool(
            "local-tools", "operator_get_status",
            {"run_id": "op-1", "user_id": "victim", "agent_id": "evil"},
            {"user_id": "ctx-user", "agent_id": "ctx-agent"})
        assert result["success"] is True
        assert captured["user_id"] == "ctx-user"
        # and with no context at all, argument identity is dropped —
        # tools.py then denies the no-identity read.
        await svc.execute_tool(
            "local-tools", "operator_get_status",
            {"run_id": "op-1", "user_id": "victim"}, None)
        assert captured["user_id"] is None


def test_run_registry_bounded_and_screenshot_ttl():
    from datetime import datetime, timedelta
    import core.operator.tools as op_tools
    reg = op_tools.OperatorRunRegistry(max_runs=3, screenshot_ttl_seconds=0)
    ids = []
    for _ in range(5):
        state = reg.create(task="t", user_id="u1")
        state.status = "done"
        state.touch()
        ids.append(state.run_id)
    # oldest runs evicted beyond the capacity (honest not-found, no KeyError)
    assert reg.get(ids[0]) is None
    assert reg.get(ids[1]) is None
    assert reg.get(ids[4]) is not None
    assert op_tools.operator_get_status(
        "operator-doesnotexist", user_id="u1")["success"] is False

    # terminal screenshots drop after the TTL; summary/result stay —
    # exercised through the GLOBAL registry the tools read
    global_reg = op_tools.get_operator_run_registry()
    state = global_reg.create(task="t2", user_id="u2")
    state.last_screenshot = "abc"
    state.status = "done"
    state.touch()
    state.terminal_at = datetime.now() - timedelta(
        seconds=global_reg.screenshot_ttl_seconds + 1)
    fetched = global_reg.get(state.run_id)  # lazy TTL drop on access
    assert fetched.screenshot_dropped is True
    assert fetched.last_screenshot == ""
    shot = op_tools.operator_get_screenshot(state.run_id, user_id="u2")
    assert shot["success"] is False
    assert "expired" in shot["error"]
    status = op_tools.operator_get_status(state.run_id, user_id="u2")
    assert status["success"] is True
    assert status["has_screenshot"] is False


def test_run_registry_never_evicts_running_runs():
    import core.operator.tools as op_tools
    reg = op_tools.OperatorRunRegistry(max_runs=2)
    running = reg.create(task="r", user_id="u1")  # stays "running"
    for i in range(4):
        state = reg.create(task=f"t{i}", user_id="u1")
        state.status = "done"
        state.touch()
    assert reg.get(running.run_id) is not None
    # the newest terminal runs were kept, older terminals evicted
    assert len(reg._runs) <= 3


def test_tier_floors_pin_operator_ladder():
    # The documented ladder: start/stop SUPERVISED+, reads STUDENT —
    # enforced at dispatch via caps ∩ tier floor.
    from core.capability_resolver import is_tool_allowed, resolve_allowed_tools

    class _Agent:
        capabilities = None  # unrestricted -> bounded by the tier floor

        def __init__(self, status):
            self.status = status

    reads = ("operator_get_status", "operator_get_screenshot")
    ladder = {"student": (True, False), "intern": (True, False),
              "supervised": (True, True), "autonomous": (True, True)}
    for tier, (expect_reads, expect_start) in ladder.items():
        allowed = resolve_allowed_tools(_Agent(tier))
        for tool in reads:
            assert is_tool_allowed(allowed, tool) is expect_reads, (tier, tool)
        assert is_tool_allowed(allowed, "operator_start_task") is expect_start, tier
        assert is_tool_allowed(allowed, "operator_stop_task") is expect_start, tier


# ---------------------------------------------------------------------------
# Legacy bridge
# ---------------------------------------------------------------------------

async def test_legacy_bridge_retires_unknown_and_old_names():
    from core.operator.legacy_bridge import dispatch_legacy_browser_tool
    res = await dispatch_legacy_browser_tool("browser_set_proxy", {}, {})
    assert res["retired"] is True
    res = await dispatch_legacy_browser_tool("browser_monitor", {}, {})
    assert res["retired"] is True


async def test_legacy_bridge_delegates_navigate(monkeypatch):
    import core.operator.legacy_bridge as bridge
    funcs = MagicMock()
    funcs.browser_create_session = AsyncMock(
        return_value={"success": True, "session_id": "s1"})
    funcs.browser_navigate = AsyncMock(
        return_value={"success": True, "url": "https://x.test"})
    mgr = MagicMock()
    mgr.get_session.return_value = MagicMock()
    funcs.get_browser_manager.return_value = mgr
    monkeypatch.setattr(bridge, "_funcs", lambda: funcs)
    monkeypatch.setattr(bridge, "_shared_sessions", {})

    res = await bridge.dispatch_legacy_browser_tool(
        "browser_navigate", {"url": "https://x.test"},
        {"user_id": "u1", "agent_id": "a1"})
    assert res["success"] is True
    funcs.browser_navigate.assert_awaited_once_with(
        "s1", "https://x.test", user_id="u1")


async def test_legacy_bridge_coordinate_click_validates_and_clamps(monkeypatch):
    import core.operator.legacy_bridge as bridge
    funcs = MagicMock()
    funcs.browser_create_session = AsyncMock(
        return_value={"success": True, "session_id": "s1"})
    mgr = MagicMock()
    session = MagicMock()
    session.page.mouse.click = AsyncMock()
    mgr.get_session.return_value = session
    funcs.get_browser_manager.return_value = mgr
    monkeypatch.setattr(bridge, "_funcs", lambda: funcs)
    monkeypatch.setattr(bridge, "_shared_sessions", {})

    # non-numeric coordinates: honest error, never an uncaught ValueError
    res = await bridge.dispatch_legacy_browser_tool(
        "browser_click", {"x": "left", "y": 10}, {"user_id": "u1"})
    assert res["success"] is False
    assert "numeric" in res["error"]

    # out-of-range coordinates clamp to the viewport on BOTH axes
    res = await bridge.dispatch_legacy_browser_tool(
        "browser_click", {"x": 99999, "y": -5}, {"user_id": "u1"})
    assert res["success"] is True
    assert res["coordinates"] == [1919, 0]
    session.page.mouse.click.assert_awaited_with(1919, 0)


async def test_legacy_bridge_type_appends_not_replaces(monkeypatch):
    import core.operator.legacy_bridge as bridge
    funcs = MagicMock()
    funcs.browser_create_session = AsyncMock(
        return_value={"success": True, "session_id": "s1"})
    funcs.browser_fill_form = AsyncMock(return_value={"success": True})
    mgr = MagicMock()
    mgr.get_session.return_value = MagicMock()
    funcs.get_browser_manager.return_value = mgr
    monkeypatch.setattr(bridge, "_funcs", lambda: funcs)
    monkeypatch.setattr(bridge, "_shared_sessions", {})

    res = await bridge.dispatch_legacy_browser_tool(
        "browser_type", {"text": "hi", "selector": "#i"}, {"user_id": "u1"})
    assert res["success"] is True
    call = funcs.browser_fill_form.await_args
    assert call.args[1] == {"#i": "hi"}
    assert call.kwargs.get("append") is True  # legacy type-append semantics


# ---------------------------------------------------------------------------
# Egress allowlist on in-loop navigations (P2-7)
# ---------------------------------------------------------------------------

async def test_session_navigate_egress_enforced_when_enabled(monkeypatch):
    from core import sandbox_config
    monkeypatch.setattr(sandbox_config, "is_sandbox_egress_enabled",
                        lambda: True)
    session = OperatorSession(user_id="u1", agent_id="a1")
    session.session_id = "s-egress"

    blocked = await session.execute({
        "action_type": "navigate",
        "parameters": {"url": "https://evil.example.com/exfil"}})
    assert blocked["success"] is False
    assert blocked.get("blocked_by_governance") is True
    assert "egress" in blocked["error"]

    # allowlisted host passes the egress check (browser_navigate mocked —
    # no real browser under TESTING)
    nav = AsyncMock(return_value={"success": True})
    monkeypatch.setattr("tools.browser_tool.browser_navigate", nav)
    ok = await session.execute({
        "action_type": "navigate",
        "parameters": {"url": "https://api.anthropic.com/v1"}})
    assert ok["success"] is True
    nav.assert_awaited_once()


async def test_session_navigate_egress_off_by_default(monkeypatch):
    from core import sandbox_config
    monkeypatch.setattr(sandbox_config, "is_sandbox_egress_enabled",
                        lambda: False)
    session = OperatorSession(user_id="u1")
    session.session_id = "s-egress-off"
    nav = AsyncMock(return_value={"success": True})
    monkeypatch.setattr("tools.browser_tool.browser_navigate", nav)
    ok = await session.execute({
        "action_type": "navigate",
        "parameters": {"url": "https://evil.example.com/anywhere"}})
    assert ok["success"] is True  # opt-in: no allowlist, no denial


async def test_session_start_url_egress_denial(monkeypatch):
    from core import sandbox_config
    monkeypatch.setattr(sandbox_config, "is_sandbox_egress_enabled",
                        lambda: True)
    session = OperatorSession(user_id="u1", agent_id="a1")
    fake_manager = MagicMock()
    fake_manager.create_session = AsyncMock(
        return_value=MagicMock(session_id="s1"))
    monkeypatch.setattr("tools.browser_tool.get_browser_manager",
                        lambda: fake_manager)
    started = await session.start(start_url="https://evil.example.com/x")
    nav = started["navigate"]
    assert nav.get("blocked_by_governance") is True
    assert "egress" in nav["error"]


# ---------------------------------------------------------------------------
# Runner wiring: real governance callback + budget-exhaustion mapping
# ---------------------------------------------------------------------------

class _RunnerFakes:
    """Fakes for _run_operator_task's in-function imports."""

    def __init__(self, loop_result):
        self.captured = {}
        self.loop_result = loop_result

    def install(self, monkeypatch):
        import core.operator.loop as loop_mod
        import core.operator.session as session_mod
        outer = self

        class FakeSession:
            def __init__(self, user_id="system", agent_id=None, db=None,
                         governance_callback=None):
                outer.captured["governance_callback"] = governance_callback

            async def start(self, start_url=None):
                return {}

            async def observe(self):
                return Observation(screenshot_b64="abc")

            async def execute(self, action):
                callback = outer.captured.get("governance_callback")
                if callback is not None and not await callback(
                        action["action_type"], action.get("parameters")):
                    return {"success": False,
                            "action_type": action["action_type"],
                            "blocked_by_governance": True,
                            "error": "blocked by governance policy"}
                return {"success": True,
                        "action_type": action["action_type"]}

            async def close(self):
                pass

        class FakeLoop:
            def __init__(self, backend=None, decider=None, max_steps=None,
                         stop_event=None, progress_callback=None):
                outer.captured["backend"] = backend
                outer.captured["progress"] = progress_callback

            async def run(self, task):
                if outer.captured.get("governance_callback") is not None:
                    await outer.captured["backend"].execute(
                        {"action_type": "click", "parameters": {}})
                return dict(outer.loop_result)

        monkeypatch.setattr(session_mod, "OperatorSession", FakeSession)
        monkeypatch.setattr(loop_mod, "OperatorLoop", FakeLoop)
        monkeypatch.setattr(loop_mod, "JsonVisionDecider",
                            lambda **kwargs: None)


async def _run_to_completion(out):
    import core.operator.tools as op_tools
    run_id = out["operator_run_id"]
    for _ in range(50):
        state = op_tools.get_operator_run_registry().get(run_id)
        if state.status != "running":
            return state
        await asyncio.sleep(0)
    raise AssertionError("operator run never reached a terminal state")


async def test_operator_runner_wires_real_governance_callback(monkeypatch):
    import core.operator.tools as op_tools

    permits = AsyncMock(return_value=False)  # governance DENIES
    monkeypatch.setattr(op_tools, "_browser_governance_permits", permits)
    monkeypatch.setattr(op_tools, "_governance_allows",
                        AsyncMock(return_value=True))
    fakes = _RunnerFakes({"success": False, "done": False, "stopped": False,
                          "blocked": True, "error": "blocked by governance "
                          "policy", "actions": [], "steps": 0,
                          "budget_exhausted": False})
    fakes.install(monkeypatch)

    out = await op_tools.operator_start_task(task="t", user_id="u1",
                                             agent_id="a1")
    assert out["success"] is True
    state = await _run_to_completion(out)
    # the loop's per-action callback ran the REAL permission check and its
    # denial hard-stopped the run as 'blocked'
    permits.assert_awaited_with("u1", "a1")
    assert fakes.captured["governance_callback"] is not None
    assert state.status == "blocked"
    assert fakes.captured["progress"] is not None  # observability wired


async def test_operator_runner_maps_budget_exhaustion_to_stopped(monkeypatch):
    import core.operator.tools as op_tools
    monkeypatch.setattr(op_tools, "_governance_allows",
                        AsyncMock(return_value=True))
    fakes = _RunnerFakes({"success": True, "done": False, "stopped": False,
                          "blocked": False, "actions": [{"step": 1}],
                          "steps": 1, "budget_exhausted": True,
                          "summary": ""})
    fakes.install(monkeypatch)

    out = await op_tools.operator_start_task(task="t", user_id="u1")
    state = await _run_to_completion(out)
    # budget exhaustion is an honest 'stopped' with a reason — NOT 'failed'
    assert state.status == "stopped"
    assert state.result["budget_exhausted"] is True
    assert state.result["stop_reason"] == "step budget exhausted"


# ---------------------------------------------------------------------------
# Browser session hygiene (TESTING refusal + periodic cleanup)
# ---------------------------------------------------------------------------

async def test_browser_session_start_refused_under_testing():
    from tools.browser_tool import BrowserSession
    with pytest.raises(RuntimeError, match="TESTING"):
        await BrowserSession("s", "u").start()


def test_browser_cleanup_task_refused_under_testing():
    from tools.browser_tool import BrowserSessionManager
    assert BrowserSessionManager().start_cleanup_task() is None


async def test_browser_manager_cleanup_loop_evicts_expired(monkeypatch):
    from tools.browser_tool import BrowserSession, BrowserSessionManager
    manager = BrowserSessionManager(session_timeout_minutes=0)  # instant TTL
    with patch.object(BrowserSession, "start", new_callable=AsyncMock), \
         patch.object(BrowserSession, "close", new_callable=AsyncMock):
        session = await manager.create_session(user_id="u1")
        assert manager.get_session(session.session_id) is not None
        task = asyncio.get_running_loop().create_task(
            manager._cleanup_loop(interval_seconds=0.05))
        try:
            for _ in range(200):
                if manager.get_session(session.session_id) is None:
                    break
                await asyncio.sleep(0.01)
            assert manager.get_session(session.session_id) is None
        finally:
            task.cancel()


async def test_browser_cleanup_task_starts_when_testing_disabled(monkeypatch):
    from tools.browser_tool import BrowserSessionManager
    monkeypatch.setenv("TESTING", "0")
    manager = BrowserSessionManager()
    task = manager.start_cleanup_task(interval_seconds=60)
    try:
        assert task is not None
        assert manager.start_cleanup_task() is task  # idempotent
    finally:
        if task is not None:
            task.cancel()
