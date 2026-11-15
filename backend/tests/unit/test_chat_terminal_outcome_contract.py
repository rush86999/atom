"""Chat boundary: an admitted terminal agent outcome owns the turn.

The feature loop previously treated every non-success response as unhandled and
started a duplicate ComputerUseAgent task. These tests drive the actual
``_route_to_features`` and ``_handle_agent_request`` with controlled,
network-free doubles and assert: terminal failed/denied/partial outcomes are
propagated without a second dispatch, genuine no-match still falls back, and a
real success still returns its answer.
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("TESTING", "1")

import pytest
from unittest.mock import patch

import integrations.chat_orchestrator as co


def _orch(agent_result):
    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    orch._cancelled_sessions = set()
    orch.feature_handlers = {co.FeatureType.AGENT: agent_result}
    return orch


def _run(orch, message="diagnose the failed fleet run"):
    fallback: list[str] = []

    async def fake_execute_task(goal, mode):
        fallback.append(goal)
        return {"id": "task-duplicate-1", "status": "pending"}

    original = co.agent_service.execute_task
    intent = {"primary_intent": co.ChatIntent.AGENT_REQUEST, "confidence": 0.9}
    with patch.object(co.agent_service, "execute_task", fake_execute_task):
        responses = asyncio.run(orch._route_to_features(
            message, intent, {"id": "session-1", "user_id": "user-1"}, {}))
    # Scoped patch: the module bound method is restored even on any exception.
    assert co.agent_service.execute_task.__func__ is original.__func__
    assert co.agent_service.execute_task.__self__ is original.__self__
    return fallback, intent, responses


def _terminal(**overrides):
    base = {
        "status": "failed", "success": False,
        "failure_reason": "fleet_specialists_failed",
        "handled": True, "terminal": True, "outcome": "failed",
        "execution_id": "exec-1", "chain_id": "chain-1",
        "message": "The recruited specialists could not complete this task.",
        "feature": "agent",
    }
    base.update(overrides)
    return base


def test_terminal_failure_is_propagated_without_fallback():
    async def handler(*_a):
        return _terminal()

    orch = _orch(handler)
    fallback, intent, responses = _run(orch)
    response = responses[co.FeatureType.AGENT]
    assert fallback == []
    assert response["success"] is False
    assert response["outcome"] == "failed"
    assert response["execution_id"] == "exec-1"
    assert response["chain_id"] == "chain-1"
    assert orch._generate_main_message(
        "diagnose the failed fleet run", intent, responses
    ) == "The recruited specialists could not complete this task."


@pytest.mark.parametrize("outcome,status,reason", [
    ("denied", "denied", "governance_denied"),
    ("partial", "failed", "fleet_routing_interrupted"),
])
def test_terminal_denial_and_partial_own_the_turn(outcome, status, reason):
    async def handler(*_a):
        return _terminal(status=status, failure_reason=reason,
                         outcome=outcome, message=f"{outcome} outcome")

    orch = _orch(handler)
    fallback, _intent, responses = _run(orch)
    response = responses[co.FeatureType.AGENT]
    assert fallback == []
    assert response["success"] is False
    assert response["outcome"] == outcome
    assert response["message"] == f"{outcome} outcome"


def test_genuine_no_match_still_falls_back():
    async def handler(*_a):
        return {"success": False, "error": "no_match"}

    orch = _orch(handler)
    fallback, _intent, responses = _run(orch)
    assert len(fallback) == 1
    assert responses[co.FeatureType.AGENT]["message"].startswith(
        "I'm working on that.")


def test_success_is_unchanged():
    async def handler(*_a):
        return {"status": "success", "success": True, "handled": True,
                "terminal": True, "outcome": "success",
                "message": "Here is the answer.", "feature": "agent"}

    orch = _orch(handler)
    fallback, _intent, responses = _run(orch)
    assert fallback == []
    assert responses[co.FeatureType.AGENT]["message"] == "Here is the answer."


def test_handle_agent_request_marks_terminal_outcome(monkeypatch):
    class FakeAtom:
        async def execute(self, **_kwargs):
            return {
                "status": "specialists_failed", "success": False,
                "failure_reason": "fleet_specialists_failed",
                "execution_id": "exec-atom", "chain_id": "chain-atom",
                "final_output": "The recruited specialists could not complete this task.",
            }

    import core.atom_meta_agent as ama
    import core.request_scope as rs
    monkeypatch.setattr(ama, "get_atom_agent", lambda *a, **k: FakeAtom())
    monkeypatch.setattr(rs, "current_request_scope", lambda: {})

    orch = _orch(None)
    async def noop(*_a, **_k):
        return None
    orch._emit_agent_status = noop
    orch._emit_agent_step = noop
    orch.feature_handlers = {co.FeatureType.AGENT: orch._handle_agent_request}

    fallback, intent, responses = _run(orch)
    response = responses[co.FeatureType.AGENT]
    assert fallback == []
    assert response["handled"] is True
    assert response["success"] is False
    assert response["outcome"] == "failed"
    assert response["execution_id"] == "exec-atom"
    assert response["chain_id"] == "chain-atom"
    assert orch._generate_main_message(
        "diagnose the failed fleet run", intent, responses
    ) == "The recruited specialists could not complete this task."


def test_agent_interruption_after_entry_is_partial_without_fallback(
        monkeypatch):
    class InterruptingAtom:
        async def execute(self, **kwargs):
            callback = kwargs.get("step_callback")
            if callback:
                await callback({"execution_id": "exec-seen"})
            raise RuntimeError("synthetic interruption after entry")

    import core.atom_meta_agent as ama
    import core.request_scope as rs
    monkeypatch.setattr(ama, "get_atom_agent", lambda *a, **k: InterruptingAtom())
    monkeypatch.setattr(rs, "current_request_scope", lambda: {})

    orch = _orch(None)
    async def noop(*_a, **_k):
        return None
    orch._emit_agent_status = noop
    orch._emit_agent_step = noop
    orch.feature_handlers = {co.FeatureType.AGENT: orch._handle_agent_request}

    fallback, _intent, responses = _run(orch)
    response = responses[co.FeatureType.AGENT]
    assert fallback == []
    assert response["handled"] is True
    assert response["outcome"] == "partial"
    assert response["execution_id"] == "exec-seen"
    assert response["failure_reason"] == "agent_execution_interrupted"
    assert "did not complete after it started" in response["message"]


def test_pre_entry_failure_still_uses_allowed_fallback(monkeypatch):
    import core.atom_meta_agent as ama
    import core.request_scope as rs
    monkeypatch.setattr(
        ama, "get_atom_agent",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no atom")))
    monkeypatch.setattr(rs, "current_request_scope", lambda: {})

    orch = _orch(None)
    async def noop(*_a, **_k):
        return None
    orch._emit_agent_status = noop
    orch._emit_agent_step = noop
    orch.feature_handlers = {co.FeatureType.AGENT: orch._handle_agent_request}

    fallback, _intent, responses = _run(orch)
    assert len(fallback) == 1
    assert responses[co.FeatureType.AGENT]["message"].startswith(
        "I'm working on that.")


def test_coordinated_response_aligns_terminal_and_preserves_ids():
    orch = _orch(None)
    responses = {co.FeatureType.AGENT: _terminal()}
    intent = {"primary_intent": co.ChatIntent.AGENT_REQUEST, "confidence": 0.9}
    result = orch._generate_coordinated_response(
        "diagnose the failed fleet run", intent, responses,
        {"id": "session-1"})
    assert result["success"] is False
    assert result["outcome"] == "failed"
    assert result["error_code"] == "fleet_specialists_failed"
    assert result["failure_reason"] == "fleet_specialists_failed"
    assert result["data"]["agent_execution_id"] == "exec-1"
    assert result["data"]["chain_id"] == "chain-1"
    assert result["data"]["terminal_outcome"]["state"] == "failed"


def test_no_match_fallback_global_restored_after_exception():
    original = co.agent_service.execute_task

    async def boom(**_kwargs):
        raise RuntimeError("synthetic")

    with patch.object(co.agent_service, "execute_task", boom):
        with pytest.raises(RuntimeError):
            asyncio.run(co.agent_service.execute_task(goal="x", mode="thinker"))
    assert co.agent_service.execute_task.__func__ is original.__func__
    assert co.agent_service.execute_task.__self__ is original.__self__
