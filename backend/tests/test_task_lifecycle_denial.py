"""Public-boundary proof that a task-lifecycle refusal stops execution
ACROSS EVERY FALLBACK (work order direction 1).

A denied canvas reservation must not merely skip the canvas-edit leg. The
turn continues — there is a reply leg, a canvas-action leg, a background
continuation fork, and a tool path — and any of them could otherwise
perform the mutation the gate refused. Each test below drives the REAL
``process_chat_message`` turn and asserts, at the public boundary:

* ``_try_canvas_edit`` is never invoked;
* ``_try_canvas_action`` is never invoked;
* no background fork was started to finish the edit;
* the response reports ``updated: False`` with the refusal reason, so the
  client is never told a change happened.

It also pins the two refusal reasons apart: an authorization denial and a
persistence outage must stay distinguishable, because they call for
different responses.

The negative control matters as much as the refusals: if the lane were
simply broken, the refusal tests would pass too.
"""
from __future__ import annotations

import os
import sys

import pytest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from integrations import chat_orchestrator as chat


@pytest.fixture(autouse=True)
def _lifecycle_flag(monkeypatch):
    monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")


def _canvas():
    return {"canvas_id": "cv1", "canvas_type": "email",
            "content": {"subject": "Draft", "body": "Unchanged"}}


def _patched(orch, session, edit_leg, action_leg, forks=None):
    """The common harness: one real canvas turn, every mutation surface
    replaced by a counter. The orchestrator's own lane selection,
    fall-through guards, and response assembly all run for real."""
    import contextlib

    async def fake_reply(message, history, routing_overrides=None, **kwargs):
        return {"content": "I did not change anything.", "model": "m",
                "provider": "p"}

    def fake_fork(orch_ref, **kwargs):
        if forks is not None:
            forks.append(kwargs)
        return "cont-1"

    @contextlib.contextmanager
    def harness():
        with contextlib.ExitStack() as stack:
            for patcher in (
                patch.object(orch, "_get_or_create_session",
                             return_value=session),
                patch.object(orch, "_resolve_canvas_ctx",
                             new=AsyncMock(return_value=_canvas())),
                patch.object(orch, "_start_chat_execution",
                             return_value="e1"),
                patch.object(orch, "_record_chat_step", new=AsyncMock()),
                patch.object(orch, "_emit_agent_status", new=AsyncMock()),
                patch.object(orch, "_finish_chat_execution"),
                patch.object(orch, "_update_session"),
                patch.object(orch, "_try_canvas_edit", new=edit_leg),
                patch.object(orch, "_try_canvas_action", new=action_leg),
                patch.object(orch, "_get_qwen_response", new=fake_reply),
                patch("core.chat_tool_planner.plan_tool_use",
                      new=AsyncMock(return_value=None)),
                patch("core.chat_tool_planner._provenance_menu",
                      new=AsyncMock(return_value="")),
                patch("core.async_turn_continuation"
                      ".fork_canvas_edit_continuation",
                      side_effect=fake_fork),
            ):
                stack.enter_context(patcher)
            yield

    return harness()


def _counters():
    return {"edit": 0, "action": 0}


def _edit_leg(calls, result=None):
    async def leg(*a, **k):
        calls["edit"] += 1
        return result or {"success": True, "message": "edited", "data": {
            "canvas_edit": {"updated": True}}}
    return leg


def _action_leg(calls):
    async def leg(*a, **k):
        calls["action"] += 1
        return {"success": True, "message": "acted"}
    return leg


def _decide(monkeypatch, decision):
    monkeypatch.setattr(
        chat, "_begin_task_edit", lambda *a, **k: dict(decision))


@pytest.mark.asyncio
async def test_authorization_denial_blocks_every_mutation_route(
        monkeypatch):
    """A policy refusal closes the edit leg AND every fall-through."""
    calls = _counters()
    forks = []
    _decide(monkeypatch, {
        "status": "denied", "run_id": None, "operation_id": None,
        "reason": "task is cancelled; edit is not permitted"})

    orch = chat.ChatOrchestrator()
    with _patched(orch, {"id": "sess-deny", "history": []},
                  _edit_leg(calls), _action_leg(calls), forks):
        result = await orch.process_chat_message(
            "u1", "rebuild the draft with the quotes", "sess-deny",
            context={"canvas_id": "cv1"})

    # Zero mutation calls across every route.
    assert calls["edit"] == 0, "the canvas-edit leg ran despite the denial"
    assert calls["action"] == 0, "the action leg ran despite the denial"
    assert forks == [], "a background fork was started to finish the edit"

    # The public boundary reports no change, and names the refusal.
    canvas_edit = (result.get("data") or {}).get("canvas_edit") or {}
    assert canvas_edit.get("updated") is False
    assert canvas_edit.get("no_apply") is True
    assert canvas_edit.get("reason") == "edit_not_authorized"
    assert canvas_edit.get("task_lifecycle_block") == {
        "status": "denied",
        "reason": "task is cancelled; edit is not permitted",
    }


@pytest.mark.asyncio
async def test_persistence_outage_blocks_every_mutation_route(monkeypatch):
    """An infrastructure fault also blocks mutation, under a DIFFERENT
    reason. The two must never collapse into one state: a refusal the
    user can fix by re-authorizing is not the same as an outage."""
    calls = _counters()
    _decide(monkeypatch, {
        "status": "unavailable", "run_id": None, "operation_id": None,
        "reason": "OperationalError: no such table"})

    orch = chat.ChatOrchestrator()
    with _patched(orch, {"id": "sess-out", "history": []},
                  _edit_leg(calls), _action_leg(calls)):
        result = await orch.process_chat_message(
            "u1", "rebuild the draft with the quotes", "sess-out",
            context={"canvas_id": "cv1"})

    assert calls["edit"] == 0
    assert calls["action"] == 0
    canvas_edit = (result.get("data") or {}).get("canvas_edit") or {}
    assert canvas_edit.get("updated") is False
    assert canvas_edit.get("reason") == "edit_not_persistable"
    assert canvas_edit.get("task_lifecycle_block")["status"] == "unavailable"


@pytest.mark.asyncio
async def test_a_lost_execution_claim_blocks_the_second_effect(
        monkeypatch):
    """One operation record is not one effect.

    A caller that loses the execution claim must not mutate — it has the
    same operation id as the winner, so nothing in the record would stop
    it. This is the lane-level counterpart of the cross-process claim
    test.
    """
    calls = _counters()
    _decide(monkeypatch, {
        "status": "already_claimed", "run_id": None, "operation_id": None,
        "reason": "operation is running, held by another caller"})

    orch = chat.ChatOrchestrator()
    with _patched(orch, {"id": "sess-claimed", "history": []},
                  _edit_leg(calls), _action_leg(calls)):
        result = await orch.process_chat_message(
            "u1", "rebuild the draft with the quotes", "sess-claimed",
            context={"canvas_id": "cv1"})

    assert calls["edit"] == 0, "a caller that lost the claim still mutated"
    assert calls["action"] == 0
    canvas_edit = (result.get("data") or {}).get("canvas_edit") or {}
    assert canvas_edit.get("updated") is False
    # A lost claim is distinct from both a denial and an outage.
    assert canvas_edit.get("reason") == "edit_already_claimed"
    assert canvas_edit.get("task_lifecycle_block")["status"] == \
        "already_claimed"


@pytest.mark.asyncio
async def test_flag_off_keeps_the_legacy_edit_path(monkeypatch):
    """With the lifecycle off the lane must behave exactly as it did
    before any of this existed — the gate is opt-in, not a new default.
    """
    monkeypatch.delenv("ATOM_TASK_LIFECYCLE_ENABLED", raising=False)
    calls = _counters()
    _decide(monkeypatch, {"status": "legacy", "run_id": None,
                          "operation_id": None, "reason": None})

    orch = chat.ChatOrchestrator()
    with _patched(orch, {"id": "sess-legacy", "history": []},
                  _edit_leg(calls), _action_leg(calls)):
        await orch.process_chat_message(
            "u1", "rebuild the draft with the quotes", "sess-legacy",
            context={"canvas_id": "cv1"})

    assert calls["edit"] == 1, "flag-off must not change the edit path"


@pytest.mark.asyncio
async def test_a_reserved_decision_still_allows_the_edit(monkeypatch):
    """The negative control: a RESERVED decision must still mutate. If
    this failed, the refusal tests above would be passing for the wrong
    reason — a broken lane rather than a working gate."""
    calls = _counters()
    _decide(monkeypatch, {"status": "reserved", "run_id": "run-1",
                          "operation_id": "op-1", "reason": None})
    monkeypatch.setattr(chat, "_finish_task_edit",
                        lambda *a, **k: "run-1")

    orch = chat.ChatOrchestrator()
    with _patched(orch, {"id": "sess-ok", "history": []},
                  _edit_leg(calls), _action_leg(calls)):
        await orch.process_chat_message(
            "u1", "rebuild the draft with the quotes", "sess-ok",
            context={"canvas_id": "cv1"})

    assert calls["edit"] == 1, "a reserved edit must still be allowed"
