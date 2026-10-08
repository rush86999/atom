"""Drafting authorization: 'Prepare the draft' is an edit request.

Case-1 T_AUTH root cause (2026-10-08): the scope validator's verb
vocabulary lacked the drafting verbs, so the EXPLICITLY authorized
request was refused at the canvas-edit lane — no mutation ever ran
(canvas_audit for the fork holds only fork/agent_attached rows across
every trial), and the turn burned its budget on cascades before the
honest budget-exceeded reply. Two guards fixed together:

- ``_CANVAS_DRAFTING_ACTION_RE`` (verb+object) recognizes
  prepare/finalize/draft/compose + a document noun, without making the
  bare noun edit-shaped ("what does the draft say" stays a question).
- ``send`` is not a negated-EDIT verb: "prepare the draft and do not
  send anything" authorizes the edit while withholding shipping.
"""
from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")

from core.turn_decision import edit_authorization
from integrations.chat_orchestrator import _canvas_edit_shaped

T_AUTH = (
    "The comparison is approved. Prepare the draft on this fork using "
    "the applicable teaching and verified correspondence. Preserve "
    "approved manual prices, leave anything unresolved unasserted, "
    "and do not send anything."
)
CTX = {"canvas": {"canvas_id": "fork-1"}}


def test_authorized_drafting_request_is_edit_shaped():
    assert _canvas_edit_shaped(T_AUTH, CTX) is True


def test_authorized_drafting_request_is_granted():
    verdict, instruction = edit_authorization(T_AUTH, canvas_id="fork-1")
    assert verdict == "granted"
    assert instruction


def test_do_not_send_does_not_negate_the_edit():
    assert edit_authorization(
        "Finalize the quote and do not send anything.",
        canvas_id="fork-1")[0] == "granted"


def test_noop_decline_wording_variants_complete():
    """The no-changes-needed completion must catch real planner
    wordings, including intervening words ('No canvas changes were
    needed: the draft already preserves...')."""
    import re
    pat = re.compile(
        r"no\s+(?:\w+\s+){0,2}changes (?:were )?needed"
        r"|already (?:reflects|preserves|includes|contains|matches|uses)"
        r"|nothing to change|no canvas changes",
        re.IGNORECASE)
    for words in (
            "No canvas changes were needed: the draft already "
            "preserves the approved manual prices.",
            "The draft already reflects the approved manual prices and "
            "verified correspondence; no changes were needed.",
            "No changes needed.",
            "The draft already uses the verified correspondence."):
        assert pat.search(words), words
    # negatives: a genuine non-noop decline must NOT complete
    for words in ("I could not find that row on the canvas.",
                  "The requested section is outside my editable area."):
        assert not pat.search(words), words


def test_negated_change_still_refuses():
    assert _canvas_edit_shaped(
        "Research this; don't change the draft yet", CTX) is False
    assert edit_authorization(
        "Research this; don't change the draft yet",
        canvas_id="fork-1")[0] == "needs_grant"


def test_bare_draft_noun_is_not_an_edit():
    assert _canvas_edit_shaped(
        "What does the draft say about the roll bender?", CTX) is False


def test_teaching_cue_still_not_an_edit():
    assert _canvas_edit_shaped(
        "learn to include the tennsmith sheet for roper whitney "
        "searches", CTX) is False


def test_canvas_required_for_edit_shape():
    assert _canvas_edit_shaped(T_AUTH, {}) is False
