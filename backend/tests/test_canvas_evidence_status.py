# -*- coding: utf-8 -*-
"""The typed canvas-evidence status: one transition, exhaustive precedence.

Replaces the independent booleans whose OR-merge let "evidence judged
unrelated" ship as "a required live-data lookup failed" (live 2026-09-22).
A small explicit status makes contradictions structurally impossible ON THE
REPLY PATH; the transition function is the ONLY place flags become status,
and its precedence is pinned here against conflicting inputs.
"""
from core.chat_canvas_editor import (
    CanvasEvidenceStatus,
    canvas_evidence_note,
    canvas_evidence_status,
)


def _flags(planning=None, evidence=None, declined=None):
    d = {}
    if planning is not None:
        d["canvas_planning_unavailable"] = planning
    if evidence is not None:
        d["canvas_evidence_unavailable"] = evidence
    if declined is not None:
        d["canvas_evidence_declined"] = declined
    return d


class TestTransitionPrecedence:
    def test_empty_flags_with_clean_gate_is_ok(self):
        assert canvas_evidence_status({}) is CanvasEvidenceStatus.OK
        assert canvas_evidence_status(None) is CanvasEvidenceStatus.OK

    def test_single_flags_map_directly(self):
        assert canvas_evidence_status(
            _flags(planning=True)) is CanvasEvidenceStatus.PLANNER_UNAVAILABLE
        assert canvas_evidence_status(
            _flags(evidence=True)) is CanvasEvidenceStatus.LOOKUP_FAILED
        assert canvas_evidence_status(
            _flags(declined=True)) is CanvasEvidenceStatus.FETCH_DECLINED

    def test_gate_verdicts_map_to_withheld_statuses(self):
        assert canvas_evidence_status(
            {}, "unproven") is CanvasEvidenceStatus.RELEVANCE_UNPROVEN
        assert canvas_evidence_status(
            {}, "mismatch") is CanvasEvidenceStatus.MISMATCH
        assert canvas_evidence_status(
            {}, "addresses") is CanvasEvidenceStatus.OK

    def test_conflicting_flags_resolve_by_precedence(self):
        # The planner-down path sets BOTH flags; the note must be the one
        # that forbids claiming a search failed because planning failed.
        assert canvas_evidence_status(_flags(
            planning=True, evidence=True)) is CanvasEvidenceStatus.PLANNER_UNAVAILABLE
        # A retrieval failure outranks a declined fetch.
        assert canvas_evidence_status(_flags(
            evidence=True, declined=True)) is CanvasEvidenceStatus.LOOKUP_FAILED
        # Everything at once: planner-unavailable still leads.
        assert canvas_evidence_status(_flags(
            planning=True, evidence=True, declined=True)
        ) is CanvasEvidenceStatus.PLANNER_UNAVAILABLE

    def test_gate_verdict_cannot_mask_a_genuine_failure(self):
        # An unrelated block does NOT make a failed lookup a success.
        assert canvas_evidence_status(
            _flags(evidence=True), "unproven"
        ) is CanvasEvidenceStatus.LOOKUP_FAILED
        assert canvas_evidence_status(
            _flags(evidence=True), "mismatch"
        ) is CanvasEvidenceStatus.LOOKUP_FAILED


class TestNotes:
    def test_ok_has_no_note(self):
        assert canvas_evidence_note(CanvasEvidenceStatus.OK) == ""

    def test_lookup_failed_keeps_the_honest_no_edit_wording(self):
        note = canvas_evidence_note(CanvasEvidenceStatus.LOOKUP_FAILED)
        assert "NO CANVAS EDIT WAS APPLIED" in note
        assert "lookup" in note and "failed" in note

    def test_fetch_declined_never_claims_a_failure(self):
        note = canvas_evidence_note(CanvasEvidenceStatus.FETCH_DECLINED)
        assert "NO CANVAS EDIT WAS APPLIED" in note
        assert "no live-data lookup ran" in note
        assert "do NOT report a lookup failure" in note

    def test_withheld_notes_claim_no_retrieval_outcome(self):
        # The 2026-09-22 correction: uncertainty stays uncertainty — a
        # nonempty rejected block may be partial or an error payload, so the
        # note must not assert "the live lookup SUCCEEDED" either.
        for status in (CanvasEvidenceStatus.RELEVANCE_UNPROVEN,
                       CanvasEvidenceStatus.MISMATCH):
            note = canvas_evidence_note(status)
            assert "WITHHELD" in note
            assert "do NOT characterize" in note.lower().replace(
                "do NOT", "do not").replace(
                "Do NOT", "do not") or "do not characterize" in note.lower()
            assert "SUCCEEDED" not in note
            assert "lookup failed" not in note

    def test_string_value_is_coerced(self):
        assert canvas_evidence_note("fetch_declined") == canvas_evidence_note(
            CanvasEvidenceStatus.FETCH_DECLINED)


def test_canvas_target_evidence_is_not_quarantined_for_a_real_edit():
    from integrations.chat_orchestrator import _evidence_relevance

    block = (
        "LIVE TOOL RESULTS (outlook.search, "
        "query='Chandrakant amacisaac alternatives roll bender bead roller "
        "flanger slitter TK 16'):\n"
        "Roper Whitney No. 381 $2,902.00"
    )
    canvas = {
        "canvas_id": "cv-quote",
        "title": "Quote - Roper Whitney Roll Bender, Linmac Bead Roller, Slitters",
        "content": {"body": "<table><tr><td>Roper Whitney No. 381</td></tr></table>"},
    }
    assert _evidence_relevance(
        block,
        "update with actual prices in the email",
        [],
        canvas=canvas,
        allow_canvas_target=True,
    ) == "addresses"
    assert _evidence_relevance(
        block,
        "update with actual prices in the email",
        [],
        canvas=canvas,
        allow_canvas_target=False,
    ) != "addresses"
