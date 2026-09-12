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
from unittest.mock import AsyncMock, MagicMock

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


async def test_session_execute_guardrail_blocks_checkout(monkeypatch):
    session = OperatorSession()
    # audit is best-effort: db=None skips it entirely
    result = await session.execute({
        "action_type": "navigate",
        "parameters": {"url": "https://shop.test/checkout?pay=1"}})
    assert result["success"] is False
    assert result.get("blocked_by_guardrail") is True


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
    assert service.waits == [("run-1", {
        "event": "operator_task_done",
        "match": {"operator_run_id": "operator-abc"},
    })]


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
    status = op_tools.operator_get_status(run_id)
    assert status["status"] == "done"
    assert status["result"]["summary"] == "ok"

    shot = op_tools.operator_get_screenshot(run_id)
    assert shot["success"] is True


async def test_operator_start_task_governance_denied(monkeypatch):
    import core.operator.tools as op_tools
    monkeypatch.setattr(op_tools, "_governance_allows",
                        AsyncMock(return_value=False))
    result = await op_tools.operator_start_task(task="x", user_id="u1",
                                                agent_id="a1")
    assert result["success"] is False
    assert "not permitted" in result["error"]


def test_operator_status_user_isolation():
    import core.operator.tools as op_tools
    state = op_tools.get_operator_run_registry().create(
        task="t", user_id="owner-1")
    ok = op_tools.operator_get_status(state.run_id, user_id="owner-1")
    assert ok["success"] is True
    denied = op_tools.operator_get_status(state.run_id, user_id="intruder")
    assert denied["success"] is False


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
