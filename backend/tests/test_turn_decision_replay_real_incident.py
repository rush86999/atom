# -*- coding: utf-8 -*-
"""Step-3 evaluation, part 2: REPLAY the real incident conversation.

``test_turn_decision_incident_eval.py`` uses hand-written messages. This
file replays the actual 30-turn user history recorded from the live
incident session ``replay-retry2-20260923`` (read-only extract, hash-pinned
in ``fixtures/SHA256SUMS``), so the contract is measured on the turns that
actually broke rather than on a reconstruction of them.

Expectations are derived from each turn's OWN wording — what the user
asked for — never from what the broken pipeline happened to do (that
would ratify the defects). ``EXPECTED`` is keyed by 1-based user-turn
index and is deliberately explicit so a reviewer can audit every call.

Three properties are asserted, because they are the ones the incident
turned on:

1. EXACT action set per turn (omitted + unintended actions).
2. An explicit edit instruction is GRANTED. The live transcript shows
   nine near-identical "apply/rebuild/update the canvas" turns, several
   answered by a failed background continuation — the user was asking for
   an authorized edit and the pipeline could not authorize it.
3. An identical REPEAT is recognized as a re-run of the same operation
   rather than as new work.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest  # noqa: E402

from core.turn_decision import AUTH_GRANTED, build_turn_decision  # noqa: E402

FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "docs", "architecture", "orchestration_migration", "acceptance",
    "fixtures", "conversation_original_drift.json",
)

WORKBOOK = "Consolidated Price List 2019.xlsx"

# What each real user turn asks for, read off its own wording.
#   research    — look something up (workbook rows, an email thread)
#   canvas_edit — mutate the draft/canvas
#   conversation— supplied a reference or approval; requested no action
EXPECTED = {
    1:  {"research", "canvas_edit"},   # "consider chandrakant's email… rebuild the draft"
    2:  {"canvas_edit"},              # "rebuild the draft now with all eight machines"
    3:  {"canvas_edit"},
    4:  {"canvas_edit"},
    5:  {"canvas_edit"},              # "update with actual prices in the email"
    6:  {"canvas_edit"},              # "update the canvas"
    7:  {"canvas_edit"},
    8:  {"canvas_edit"},              # "apply that priced draft to the canvas now"
    9:  {"canvas_edit"},
    10: {"canvas_edit"},
    11: {"canvas_edit"},
    12: {"canvas_edit"},
    13: {"research"},                 # "find all these prices from price list 2019"
    # "Consolidated Price List 2019.xlsx is correct" supplies a reference
    # and asks for nothing — but it is the answer to a disambiguation the
    # pipeline asked, and `is_filename_confirmation` is DEFINED as a
    # resume of the previously asked task. Resuming the blocked read is
    # the honest reading; inventing a new action would not be.
    14: {"research"},
    15: {"research"},                 # "try excel file search again"
    16: {"research"},                 # "go ahead" (approves the pending read)
    17: {"research"},
    18: {"research"},
    19: {"research"},                 # "try search again"
    20: {"research"},
    21: {"research"},
    22: {"research"},                 # "find the prices of these 8 machines in …xlsx"
    23: {"research"},
    24: {"research"},
    25: {"research"},
    26: {"research"},
    27: {"research"},
    28: {"research"},
    29: {"research"},
    30: {"research"},
}

# Turns 2-4 and 9-11 and 22-30 are byte-identical repeats: the user re-asked
# because the previous turn did not serve them.
EDIT_REPEAT_GROUPS = ((2, 3, 4), (9, 10, 11), (22, 23, 24, 25, 26, 27, 28, 29, 30))


def _load_user_turns():
    if not os.path.exists(FIXTURE):
        pytest.skip("incident fixture not present: %s" % FIXTURE)
    with open(FIXTURE) as fh:
        data = json.load(fh)
    return [m.get("content") or "" for m in data["messages"]
            if m.get("role") == "user"]


def _session_for(index):
    """A faithful projection of the durable state at each point in the
    real conversation: the canvas is open throughout, and the workbook
    identity is established from turn 13 onward."""
    session = {"id": "replay-retry2-20260923"}
    if index >= 13:
        session["_pending_file_task"] = {
            "mention": WORKBOOK.lower(),
            "original_message": (
                "find the prices of these 8 machines in %s: No. 381, U-22, "
                "No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi "
                "Wheel Gang Slitter and GSL48-16" % WORKBOOK),
            "status": "retrieved",
            "resolved_file": {
                "file_name": WORKBOOK,
                "file_id": "wd-77",
                "content_hash": "ff2597d26fc6d0ea216c0fd9b933090dc64e3348",
            },
        }
    return session


def _decide(index, message, history):
    return build_turn_decision(
        message, _session_for(index), history, {"canvas_id": "canvas-381"},
        session_id="replay-retry2-20260923")


def _kinds(d):
    return sorted(a["kind"] for a in d["requested_actions"])


def _action(d, kind):
    for a in d["requested_actions"]:
        if a["kind"] == kind:
            return a
    return None


def test_fixture_has_the_expected_turn_count():
    turns = _load_user_turns()
    assert len(turns) == 30, len(turns)
    assert set(EXPECTED) == set(range(1, 31))
    assert "learn to include" not in " ".join(turns).lower(), (
        "the teaching half of the compound turn is not in this fixture; it "
        "is covered by the incident-eval file, not here")


def test_every_real_turn_proposes_exactly_what_was_asked():
    turns = _load_user_turns()
    history = []
    failures = []
    for i, message in enumerate(turns, start=1):
        d = _decide(i, message, list(history))
        got = set(_kinds(d))
        want = EXPECTED[i]
        if got != want:
            failures.append("turn %-2d expected %-28s got %-28s | %s" % (
                i, sorted(want), sorted(got), " ".join(message.split())[:70]))
        history.append({"role": "user", "content": message})
    assert not failures, "\n".join(failures)


def test_explicit_edit_instructions_in_the_real_transcript_are_authorized():
    """Turns 2-12 are eleven explicit edit requests. In the live
    transcript several were answered by a failed background continuation
    and one by "I can't apply the canvas edit". The contract must
    AUTHORIZE them: they are the user's own instructions, naming the
    artifact and the change."""
    turns = _load_user_turns()
    unauthorized = []
    for i in range(2, 13):
        d = _decide(i, turns[i - 1], [])
        edit = _action(d, "canvas_edit")
        if edit is None:
            unauthorized.append("turn %d: no canvas_edit action" % i)
        elif edit["authorization"] != AUTH_GRANTED:
            unauthorized.append("turn %d: %s" % (i, edit["authorization"]))
    assert not unauthorized, "\n".join(unauthorized)


def test_identical_repeats_do_not_change_the_decision():
    """A byte-identical repeat must resolve to the same actions. The live
    transcript's three repeat groups are how the user signalled that a
    turn had not served them; a contract that silently changed its mind
    between identical turns could not be debugged."""
    turns = _load_user_turns()
    for group in EDIT_REPEAT_GROUPS:
        decisions = [_kinds(_decide(i, turns[i - 1], [])) for i in group]
        assert len({tuple(d) for d in decisions}) == 1, (
            "turns %s decided inconsistently: %s" % (group, decisions))
