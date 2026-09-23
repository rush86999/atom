"""Typed termination reasons from core.operator.loop — the contract the
env-curriculum adapter's harness/agent classification depends on.

The adapter must be able to distinguish infrastructure failures (exception /
observation_failed / stopped) from agent-attributable outcomes
(no_valid_action / unparseable_step / repeated_action_failure / action_blocked /
budget_exhausted / completed). These tests pin the loop's reason per exit
path using a stub backend — no Chromium, no model.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.operator.loop import OperatorLoop  # noqa: E402


class Observation:
    def __init__(self, error=None, url="http://x/", title="t", page_text="p"):
        self.url, self.title, self.page_text = url, title, page_text
        self.screenshot_b64 = None
        self.viewport = (1280, 720)
        self.error = error


def _decider(responses):
    """Pop-driven decider: each call returns the next value."""
    calls = {"n": 0}

    class D:
        async def decide(self, task, observation, history=None):
            i = calls["n"]
            calls["n"] += 1
            return responses[i] if i < len(responses) else None

    return D()


class StubBackend:
    def __init__(self, observe_error=None, execute_ok=True):
        self.observe_error = observe_error
        self.execute_ok = execute_ok
        self.executed = []

    async def observe(self):
        return Observation(error=self.observe_error)

    async def execute(self, action):
        self.executed.append(action)
        return {"success": self.execute_ok}

    async def close(self):
        pass


def _run_loop(backend, decider, max_steps=5, settle=0.0):
    loop = OperatorLoop(backend=backend, decider=decider,
                        max_steps=max_steps)
    loop.step_settle_seconds = settle
    return asyncio.run(loop.run("do the thing"))


def _decision(action_type=None, done=False, summary="s"):
    from types import SimpleNamespace
    d = {"done": done, "reasoning": "r", "summary": summary}
    if action_type:
        # The loop consumes the action by ATTRIBUTE access (it normally
        # receives an OperatorAction built by the real decider).
        d["action"] = SimpleNamespace(
            action_type=action_type, parameters={"p": 1},
            confidence=0.9, description=action_type)
    return d


def test_completed_when_decider_reports_done():
    result = _run_loop(StubBackend(), _decider([_decision(done=True)]))
    assert result["termination_reason"] == "completed"
    assert result["done"] is True and result["error"] is None


def test_budget_exhausted_when_decider_keeps_acting():
    wait = _decision("wait")
    result = _run_loop(StubBackend(), _decider([wait] * 10), max_steps=3)
    assert result["termination_reason"] == "budget_exhausted"
    assert result["budget_exhausted"] is True


def test_observation_failure_is_typed_infrastructure():
    result = _run_loop(StubBackend(observe_error="browser died"),
                       _decider([_decision(done=True)]))
    assert result["termination_reason"] == "observation_failed"
    assert result["error"] and "browser died" in result["error"]


def test_no_valid_action_on_first_unparseable_decision():
    # Model produced no valid decision at all: AGENT-attributable, and the
    # reason must say so (this was previously laundered into a bare error).
    result = _run_loop(StubBackend(), _decider([None]))
    assert result["termination_reason"] == "no_valid_action"
    assert result["error"]  # the loop still reports a human-readable error


def test_exception_is_typed_infrastructure():
    class DeadBackend(StubBackend):
        async def observe(self):
            raise RuntimeError("playwright exploded")

    result = _run_loop(DeadBackend(), _decider([_decision(done=True)]))
    assert result["termination_reason"] == "exception"
    assert "playwright exploded" in result["error"]


def test_executed_actions_carry_parameters():
    result = _run_loop(StubBackend(), _decider(
        [_decision("wait"), _decision(done=True)]))
    assert result["actions"], "expected at least one executed action"
    assert result["actions"][0]["parameters"] == {"p": 1}
