"""Completed fleet results must reach the turn answer, not the fast reply."""
from __future__ import annotations

import ast
import os
from pathlib import Path

os.environ.setdefault("TESTING", "1")

import pytest

import integrations.chat_orchestrator as co

A = "DIRECT_FAST_ANSWER_A"
B = "FLEET_SYNTHESIS_ANSWER_B"


def _agent(**overrides):
    base = {"success": True, "handled": True, "terminal": True,
            "message": B, "model": "fleet-core", "provider": "atom"}
    base.update(overrides)
    return base


def test_completed_fleet_answer_wins_over_direct_fast_reply():
    assert A != B
    chosen = co.ChatOrchestrator._completed_agent_message(
        {co.FeatureType.AGENT: _agent()})
    assert chosen["message"] == B


@pytest.mark.parametrize("overrides", [
    {"success": False},
    {"handled": False},
    {"terminal": False},
    {"message": ""},
])
def test_noncompleted_or_unadmitted_agent_does_not_override(overrides):
    assert co.ChatOrchestrator._completed_agent_message(
        {co.FeatureType.AGENT: _agent(**overrides)}) is None


def test_no_agent_response_keeps_fast_path():
    assert co.ChatOrchestrator._completed_agent_message({}) is None


def test_full_long_result_is_not_truncated_to_db_summary_bound():
    long_b = B + ":" + ("x" * 900)
    chosen = co.ChatOrchestrator._completed_agent_message(
        {co.FeatureType.AGENT: _agent(message=long_b)})
    assert chosen["message"] == long_b
    assert len(chosen["message"]) > 500


def test_fleet_answer_provenance_is_only_actual_reported_identity():
    chosen = co.ChatOrchestrator._completed_agent_message(
        {co.FeatureType.AGENT: _agent()})
    assert chosen.get("model") == "fleet-core"
    assert chosen.get("provider") == "atom"
    unknown = co.ChatOrchestrator._completed_agent_message(
        {co.FeatureType.AGENT: _agent(model=None, provider=None)})
    assert unknown.get("model") is None
    assert unknown.get("provider") is None


def test_inline_consumer_calls_actual_carrier_and_guards_later_direct_route():
    src = Path(__file__).resolve().parents[2] / "integrations/chat_orchestrator.py"
    tree = ast.parse(src.read_text())
    carrier_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_initial_turn_carrier"
    ]
    assert len(carrier_calls) == 1
    guarded = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                and test.left.id == "_agent_done"
                and any(isinstance(op, ast.Is) for op in test.ops)):
            for child in ast.walk(node):
                if (isinstance(child, ast.Assign)
                        and any(isinstance(t, ast.Name)
                                and t.id == "used_model" for t in child.targets)):
                    guarded = True
    assert guarded, "later direct model assignment must be guarded"


def test_actual_initial_carrier_replaces_direct_metadata_and_unknown_route():
    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    direct = {"content": A, "model": "direct-model",
              "provider": "direct-provider", "review_summary": "old"}
    main, carrier, model, provider, done = orch._initial_turn_carrier(
        direct, {co.FeatureType.AGENT: _agent(model=None, provider=None)})
    assert main == B
    assert carrier == {"content": B, "success": True}
    assert "review_summary" not in carrier
    assert model is None and provider is None
    assert done["message"] == B


def test_actual_initial_carrier_forwards_reported_fleet_identity():
    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    main, carrier, model, provider, _done = orch._initial_turn_carrier(
        {"content": A, "model": "direct-model", "provider": "direct-provider"},
        {co.FeatureType.AGENT: _agent()})
    assert main == B and carrier["content"] == B
    assert model == "fleet-core" and provider == "atom"


def test_actual_initial_carrier_keeps_fast_reply_without_completed_agent():
    orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
    main, carrier, model, provider, done = orch._initial_turn_carrier(
        {"content": A, "model": "direct-model", "provider": "direct-provider"},
        {})
    assert main == A and carrier["content"] == A
    assert model is None and provider is None and done is None
