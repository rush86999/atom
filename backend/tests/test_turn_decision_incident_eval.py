# -*- coding: utf-8 -*-
"""Step-3 evaluation: the incident transitions, with EXACT action sets.

Why a separate harness from ``test_turn_decision.py``: that file asserts
contract *shape* (fields exist, a verdict is one of two values). This file
asserts the thing the directive actually requires — that ONE decision
proposes the user's REAL requested actions and nothing else. Subset
assertions cannot see an omitted action, and permissive verdicts cannot see
an over-authorized one; both defects this harness exists to pin were
invisible to the shape tests.

Exact-set assertions are deliberate: "omitted actions" and "unintended
mutations" are the two failure modes the directive names, and both are
invisible to a subset check.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core.turn_decision import (  # noqa: E402
    AUTH_GRANTED,
    AUTH_NEEDS_CONFIRMATION,
    build_turn_decision,
)

ASK = ("find the prices of these 8 machines in Consolidated Price List "
       "2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, "
       "TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")

SESSION = {
    "id": "s-eval",
    "_superseded_file_task_context": {
        "original_message": ASK,
        "mention": "consolidated price list 2019.xlsx",
        "resolved_file": {
            "file_name": "Consolidated Price List 2019.xlsx",
            "file_id": "wd-77", "content_hash": "ff2597d2",
        },
        "confirmed_mention": "consolidated price list 2019.xlsx",
    },
}


def decide(message, session=None, context=None, history=None):
    return build_turn_decision(
        message, session if session is not None else SESSION,
        history or [], context or {}, session_id="s-eval")


def kinds(d):
    return sorted(a["kind"] for a in d["requested_actions"])


def action(d, kind):
    for a in d["requested_actions"]:
        if a["kind"] == kind:
            return a
    return None


# --------------------------------------------------------------------------
# The incident transitions. Each is (id, message, session, context,
# expected_action_kinds) — the EXACT set the user asked for.
# --------------------------------------------------------------------------
TRANSITIONS = [
    ("research_plus_learning",
     "repeat the search and learn to include tennsmith sheet for roper "
     "whitney searches", SESSION, {}, ["learning", "research"]),

    ("cross_source_confirmation",
     "check Chandrakant's email and or description in workbook to find "
     "correct sheet and row from workbook for confirmation",
     SESSION, {}, ["research"]),

    # "as you found the latest price" refers to evidence already obtained,
    # but the repo's own tested resolver (`_continuation_decision`)
    # resolves this turn to `read`. The contract composes that rather than
    # second-guessing it — and the outcome is strictly better: the edit
    # then writes VERIFIED evidence instead of the user's recollection.
    # Reads are authorized and mutate nothing.
    ("explicit_edit_instruction",
     "as you found the latest price for the roper 381 roll bender, update "
     "the email price accordingly",
     SESSION, {"canvas_id": "c-1"}, ["canvas_edit", "research"]),

    # An advisory sentence requests nothing. It resolves to an explicit
    # `conversation` action — the no-op is REPRESENTED, not merely absent,
    # so "we decided to do nothing" stays distinguishable from "we never
    # looked".
    ("nomination_is_never_authorized",
     "the draft should mention the tennsmith sheet",
     SESSION, {"canvas_id": "c-1"}, ["conversation"]),

    ("formatting_only", "make it cleaner", SESSION, {}, ["presentation"]),

    ("bare_retry_is_a_rerun_not_a_reformat",
     "try again", SESSION, {}, ["research"]),

    ("teaching_alone", "remember that roper whitney ships from tulare",
     SESSION, {}, ["learning"]),

    ("teaching_with_agent_attached",
     "learn to include the tennsmith sheet for roper whitney searches",
     SESSION, {"agent_id": "a-9"}, ["learning"]),

    ("ambiguous_reference_invents_no_target",
     "find this in the tracker", {"id": "s-bare"}, {}, ["conversation"]),

    ("supersession_of_genuinely_new_work",
     "now find the warranty terms in the service manual",
     SESSION, {}, ["research"]),
]


def test_every_incident_transition_proposes_exactly_the_requested_actions():
    """One assertion per incident transition, exact set, all failures
    reported together (a per-case loop so one defect does not hide the
    next)."""
    failures = []
    for case_id, message, session, context, expected in TRANSITIONS:
        d = decide(message, session, context)
        got = kinds(d)
        if got != sorted(expected):
            failures.append("%s: expected %s, got %s" % (
                case_id, sorted(expected), got))
    assert not failures, "\n".join(failures)


def test_presentation_is_only_proposed_when_a_preference_was_expressed():
    """A presentation action is legitimate — the directive is ONE decision,
    MANY actions, and "search again AND give me a clean response" needs
    both a re-run and a re-render. What is never legitimate is a
    presentation the user did not ask for.

    ``_continuation_decision`` reports ``style='default'`` as the
    sentinel for "no preference expressed", and ``'default'`` is a
    TRUTHY string: testing ``pref.get('style') or pref.get('field')``
    therefore invents a re-render on every rerun/refresh turn. Measured on
    the recorded incident that added 8 spurious presentation actions to 30
    turns ("try search again" x5, plus three edit turns).
    """
    for case_id, message, session, context, expected in TRANSITIONS:
        d = decide(message, session, context)
        pres = [a for a in d["requested_actions"] if a["kind"] == "presentation"]
        for p in pres:
            expressed = (
                (p.get("style") not in (None, "default"))
                or p.get("field") is not None)
            assert expressed, (
                "%s: presentation proposed with no expressed preference "
                "(style=%r field=%r) for %r" % (
                    case_id, p.get("style"), p.get("field"),
                    " ".join(message.split())[:60]))


def test_no_unrequested_mutation_is_ever_authorized():
    """Only an explicit user edit instruction or a retry of a previously
    authorized one may carry a granted canvas_edit."""
    for case_id, message, session, context, _ in TRANSITIONS:
        d = decide(message, session, context)
        edit = action(d, "canvas_edit")
        if edit is None:
            continue
        assert edit["authorization"] in (AUTH_GRANTED, "needs_grant"), (
            "%s: unexpected verdict %r" % (case_id, edit["authorization"]))
        if edit["authorization"] == AUTH_GRANTED:
            assert edit["user_grounded_instruction"], (
                "%s: a granted edit must carry the user's own instruction, "
                "not a shape hint (authorization from a hint is the "
                "'research became an edit' inversion)" % case_id)


def test_cross_source_resolves_the_workbook_alongside_email():
    d = decide("check Chandrakant's email and or description in workbook "
               "to find correct sheet and row from workbook for "
               "confirmation")
    assert "email" in d["references"]["sources"], d["references"]
    assert d["references"]["file"], (
        "the workbook reference must resolve even when the request also "
        "needs email: a communication-source word is a requested SOURCE, "
        "not a reason to refuse resolution")


def test_learning_without_a_destination_is_surfaced_not_dropped():
    d = decide("remember that roper whitney ships from tulare")
    learning = action(d, "learning")
    assert learning is not None
    assert learning["authorization"] == AUTH_NEEDS_CONFIRMATION
    assert learning["destination_candidates"], (
        "no agent attached: offer destination selection, never drop it")
    d2 = decide("learn to include the tennsmith sheet",
                context={"agent_id": "a-9"})
    learning2 = action(d2, "learning")
    assert learning2["destination"] == "agent:a-9", learning2


def test_previous_objective_survives_every_proposed_revision():
    """Directive boundary #1: a proposal never pops state. Verified
    against the real session object, not a copy."""
    before = repr(SESSION)
    decide("repeat the search and learn to include tennsmith sheet for "
           "roper whitney searches")
    assert repr(SESSION) == before, "the decision mutated durable state"


def test_retry_of_a_failed_edit_is_user_grounded_and_granted():
    """The one path that may grant an edit from prior state — a retry of
    an edit the user already authorized. The detector is exercised
    unmocked elsewhere; here only the composition is under test."""
    from unittest.mock import patch

    import integrations.chat_orchestrator as chat_mod

    with patch.object(chat_mod, "_failed_edit_retry_target",
                      return_value={"instruction": "update the price",
                                    "canvas_id": "c-1",
                                    "execution_id": "e-1"}):
        d = decide("try again", context={"canvas_id": "c-1"})
    edit = action(d, "canvas_edit")
    assert edit is not None
    assert edit["authorization"] == AUTH_GRANTED
    assert edit["user_grounded_instruction"] == "update the price"
    assert kinds(d) == ["canvas_edit"], (
        "a bare retry is ONE action: it must not also re-read")
