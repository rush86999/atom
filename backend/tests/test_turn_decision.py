# -*- coding: utf-8 -*-
"""The structured turn-decision contract (2026-09-30 consolidation,
directive steps 1-3): ONE decision, MANY actions, composed from the
existing gates. The six incident transitions are the evaluation set —
the decision must represent the user's requested actions correctly
BEFORE any routing migrates onto it (step 4)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

from core.turn_decision import (
    AUTH_GRANTED,
    AUTH_NEEDS_CONFIRMATION,
    AUTH_NEEDS_GRANT,
    _user_grounded_edit_instruction,
    build_turn_decision,
)

ASK = ("find the prices of these 8 machines in Consolidated Price List "
       "2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, "
       "TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")
COMPOUND = ("repeat the search and learn to include tennsmith sheet for "
            "roper whitney searches")
CROSS_SOURCE = ("check Chandrakant's email and or description in workbook "
                "to find correct sheet and row from workbook for "
                "confirmation")
EDIT = ("as you found the latest price for the roper 381 roll bender, "
        "update the email price accordingly")
FORMAT = "make it cleaner"

SESSION = {
    "id": "s-dec",
    "_superseded_file_task_context": {
        "original_message": ASK,
        "mention": "consolidated price list 2019.xlsx",
        "resolved_file": {
            "file_name": "Consolidated Price List 2019.xlsx",
            "file_id": "wd-77", "content_hash": "ff2597d2"},
        "confirmed_mention": "consolidated price list 2019.xlsx",
    },
}


def _kinds(d):
    return [a["kind"] for a in d["requested_actions"]]


def test_transition_research_plus_learning():
    """The directive's canonical compound turn: research + learning, NO
    edit — one decision, many actions."""
    d = build_turn_decision(COMPOUND, SESSION, session_id="s-dec")
    kinds = _kinds(d)
    assert "research" in kinds and "learning" in kinds, kinds
    assert "canvas_edit" not in kinds, kinds
    research = next(a for a in d["requested_actions"]
                    if a["kind"] == "research")
    assert research["authorization"] == AUTH_GRANTED
    assert research["proposed_revision"]["retains_previous_objective"], (
        "the previous objective must survive until the revision commits")
    learning = next(a for a in d["requested_actions"]
                    if a["kind"] == "learning")
    assert learning["authorization"] == AUTH_NEEDS_CONFIRMATION
    assert learning["lesson"]
    assert learning["destination_candidates"], (
        "no agent attached: destination selection must be offered, not "
        "silently dropped")


def test_transition_cross_source_confirmation():
    """The workbook reference resolves EVEN THOUGH the request also
    needs email — sources are represented, not an exclusion."""
    d = build_turn_decision(CROSS_SOURCE, SESSION, session_id="s-dec")
    assert d["references"]["sources"], d["references"]
    assert "email" in d["references"]["sources"]
    assert d["references"]["file"], (
        "the workbook reference must resolve alongside the email source")
    assert "research" in _kinds(d)


def test_transition_retry_after_failure():
    """A bare retry of a failed edit is a user-grounded edit decision."""
    from unittest.mock import patch

    import integrations.chat_orchestrator as chat_mod

    with patch.object(chat_mod, "_failed_edit_retry_target",
                      return_value={"instruction": EDIT,
                                   "canvas_id": "c-1",
                                   "execution_id": "e-1"}):
        d = build_turn_decision(
            "try again", SESSION, session_id="s-dec",
            context={"canvas_id": "c-1"})
    edit = next(a for a in d["requested_actions"]
                if a["kind"] == "canvas_edit")
    assert edit["authorization"] == AUTH_GRANTED
    assert edit["user_grounded_instruction"] == EDIT


def test_transition_accepted_proposal_edit():
    """An explicit edit instruction is GRANTED on its own evidence; a mere
    nomination is not. (This test previously asserted the verdict was one
    of two values, which cannot fail — the incident replay showed 0 of 11
    explicit edits in the real transcript were grantable.)"""
    d = build_turn_decision(
        EDIT, SESSION, session_id="s-dec", context={"canvas_id": "c-1"})
    edit = next(a for a in d["requested_actions"] if a["kind"] == "canvas_edit")
    assert edit["authorization"] == AUTH_GRANTED, edit
    assert edit["user_grounded_instruction"], (
        "a granted edit must carry the user's own instruction, not a "
        "shape hint: authorization from a hint is the 'research became an "
        "edit' inversion")
    # a bare nomination without an explicit edit request stays ungated
    d2 = build_turn_decision(
        "the draft should mention the tennsmith sheet",
        SESSION, session_id="s-dec", context={"canvas_id": "c-1"})
    edit2 = next((a for a in d2["requested_actions"]
                  if a["kind"] == "canvas_edit"), None)
    if edit2 is not None:
        assert edit2["authorization"] == AUTH_NEEDS_GRANT, edit2


def test_learned_clause_never_grounds_an_edit():
    """"learn to INCLUDE the tennsmith sheet" is a request to remember a
    search rule, not to change a canvas. This is the general form of the
    teaching veto that was hard-coded into the shared edit gate on
    2026-09-30."""
    assert _user_grounded_edit_instruction(
        "repeat the search and learn to include tennsmith sheet for roper "
        "whitney searches") == ""
    assert _user_grounded_edit_instruction(
        "make sure to update the price in the table") == ""
    assert _user_grounded_edit_instruction(
        "rebuild the draft now with all eight machines") != ""
    assert _user_grounded_edit_instruction("tell me if the price changed") == ""


def test_transition_formatting():
    """Formatting-only: a PRESENTATION action over existing evidence —
    no research, no edit, no learning, and no re-read."""
    d = build_turn_decision(FORMAT, SESSION, session_id="s-dec")
    kinds = _kinds(d)
    assert kinds == ["presentation"], kinds


def test_transition_ambiguous_reference():
    """An unknown generic reference with no resolved identity: the
    decision must not invent a target."""
    d = build_turn_decision(
        "find this in the tracker", {"id": "s-bare"}, session_id="s-bare")
    assert d["references"]["file"] is None
    research = [a for a in d["requested_actions"]
                if a["kind"] == "research"]
    assert not research or research[0]["target"].get("kind") != (
        "spreadsheet"), research


def test_decision_is_pure_and_shadow_shaped():
    SESSION_COPY = dict(SESSION)
    d = build_turn_decision(COMPOUND, SESSION_COPY, session_id="s-dec",
                            routed_lane="read")
    assert d["schema"] == "turn-decision-1"
    assert d["routed_lane"] == "read"
    assert SESSION_COPY == SESSION, "the decision must never mutate state"
    assert d["provenance"]["signals"]


def test_learning_without_agent_resolves_a_destination(monkeypatch):
    """Activation behavior (2026-09-30 step 4): a learning request with
    no attached agent was silently dropped — the contract surfaced it
    as destination_candidates. The teaching channel now resolves the
    workspace chat assistant as the destination; the kill switch
    restores the drop."""
    from core.chat_teaching import detect_mid_message_cue, suggest_lesson

    lesson = detect_mid_message_cue(
        "repeat the search and learn to include tennsmith sheet for "
        "roper whitney searches")
    assert lesson

    class _Q:
        def __init__(self, *a, **k): pass
        def filter(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def first(self):
            class A:
                id = "chat-agent-1"
                name = "Chat Assistant"
                status = "intern"
                updated_at = 0
            return A()

    class _DB:
        def query(self, *a, **k): return _Q()

    sug = suggest_lesson(_DB(), agent_id=None, lesson=lesson)
    assert sug and (sug.get("agent") or {}).get("id") == "chat-agent-1"

    monkeypatch.setenv("ATOM_TEACHING_DEFAULT_DESTINATION", "off")
    assert suggest_lesson(_DB(), agent_id=None, lesson=lesson) is None
