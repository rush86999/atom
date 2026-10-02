# -*- coding: utf-8 -*-
"""The empty-item answer guard — the 2026-10-02 bare-footer turns.

Live failures (conversation replay-retry2-20260923): workbook reads that
resolved ZERO items rendered "From the saved copy of X (saved D):" +
coverage footer + freshness verdict with NO body — twice on the same
conversation ("cross check what's already confirmed", then "clarify what
you mean for the other machinery you didn't mention"). The user's
question visibly went unanswered and nothing said so.

Contract pinned here:
1. The renderer never ships a silent empty block: a record whose
   targets survived but whose requested_items were dropped (broken
   inheritance, older record) renders ITS targets.
2. A both-empty read states the gap explicitly and names the way out.
3. The resolvers' behavior on the exact live follow-ups is pinned:
   outcome-reference and contrastive language that DOES resolve, and
   the plain continuation ("cross check what's already confirmed")
   that resolves through the ledger-objective fallback instead.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

from core import answer_presentation as ap
from core.target_set_resolution import (
    _OUTCOME_SUBSET_RE,
    detect_contrastive_reference,
    resolve_target_set,
)


def _ev(sheet, row, cell, values, alias=None):
    return {"sheet": sheet, "row": row, "cell": cell, "value": "hit",
            "column": "Model", "matched_alias": alias, "values": values,
            "prices": values}


def _v(cell, raw, basis):
    return {"cell": cell, "value": raw, "column": basis, "field": basis,
            "price_basis": basis}


OUTCOMES = {
    "M-1": {"target": "M-1", "status": "found", "evidence": [
        _ev("SheetA", 88, "A88", [_v("E88", "3254", "PRICE")]),
    ]},
    "M-2": {"target": "M-2", "status": "found", "evidence": [
        _ev("SheetB", 26, "C26", [_v("C26", "1777", "List Price")]),
    ]},
}


def _record(items=("M-1", "M-2"), targets=True):
    built = ap.build_targets_from_scan(list(items), OUTCOMES, {})
    rec = ap.build_structured_record(
        source_identity={"file_name": "w.xlsx",
                         "ingested_at": "2026-09-07"},
        evidence_revision="rev-1",
        attempt_id=ap.new_attempt_id(),
        evidence_action="new_read",
        requested_items=list(items),
        requested_fields=["price"],
        targets=built if targets else [],
        coverage={"indexed_sheets": 2},
    )
    return rec


class TestRendererNeverShipsSilentEmptyBlock:
    def test_record_with_dropped_items_renders_its_targets(self):
        """The 00:10/13:41 shape: targets exist in the record but
        requested_items came back empty — the targets ARE the objective
        and must render, not a bare header+footer."""
        rec = _record()
        assert rec["requested_items"], "fixture sanity"
        rec["requested_items"] = []
        out = ap.present_from_record(rec)
        assert "- **M-1**" in out["answer"]
        assert "- **M-2**" in out["answer"]
        assert out["answer"].rstrip().endswith(
            "not the live file.") or "Source:" in out["answer"]

    def test_both_empty_states_the_gap(self):
        """A truly item-less read says so and names the way out — the
        block is never a silent shell."""
        rec = _record(targets=False)
        rec["requested_items"] = []
        out = ap.present_from_record(rec)
        assert "No items were resolved" in out["answer"]
        assert "repeat the previous set" in out["answer"]

    def test_table_style_both_empty_states_the_gap(self):
        rec = _record(targets=False)
        rec["requested_items"] = []
        out = ap.present_from_record(rec, style="table")
        assert "No items were resolved" in out["answer"]
        assert "| item |" in out["answer"]

    def test_normal_render_unchanged(self):
        """The guard is invisible on healthy records: summary + item
        lines + footer exactly as before, no guard text."""
        rec = _record()
        out = ap.present_from_record(rec)
        assert "No items were resolved" not in out["answer"]
        assert "Checked 2 items" in out["answer"]
        assert "- **M-1**" in out["answer"]

    def test_direct_present_call_guards_too(self):
        """present() itself (not just the record path) normalizes empty
        items to the record's targets — every caller inherits the
        guard."""
        targets = ap.build_targets_from_scan(
            ["M-1", "M-2"], OUTCOMES, {})
        out = ap.present(
            requested_items=[], requested_fields=["price"],
            source={"file_name": "w.xlsx", "saved_copy_date":
                    "2026-09-07T23:06:19"},
            targets=targets, evidence_revision="rev-1")
        assert "- **M-1**" in out["answer"]
        assert "- **M-2**" in out["answer"]


class TestLiveFollowUpResolution:
    """The exact messages that produced the empty answers, pinned."""

    CROSS_CHECK = (
        "search the price list workbook to cross check what's already "
        "confirmed. price list workbook holds the most uptodate pricing "
        "but is not complete. ")
    OTHER_MACHINERY = (
        "clarify what you mean for the other machinery you didn't "
        "mention in the previous message")
    ONES_NOT_FOUND = (
        "update the prices that were found in the email . search email "
        "attachments for the ones not found. If still not found, find "
        "email for vendor pricing if possible.")

    def test_the_ones_not_found_is_an_outcome_reference(self):
        assert _OUTCOME_SUBSET_RE.search(self.ONES_NOT_FOUND)

    def test_cross_check_rides_the_ledger_fallback(self):
        """Documents WHY the ledger-objective fallback is load-bearing:
        this continuation is neither outcome-referenced ('not complete'
        is not the regex's 'incomplete') nor contrastive — without the
        fallback it read an empty target set and rendered the bare
        footer."""
        assert not _OUTCOME_SUBSET_RE.search(self.CROSS_CHECK)
        assert detect_contrastive_reference(self.CROSS_CHECK) is None

    def test_other_machinery_resolves_to_the_unserved_set(self):
        prior = ["381", "U-22", "622", "SLE24-16", "1624", "GSL48-16"]
        resolved = resolve_target_set(
            self.OTHER_MACHINERY,
            canvas_items=[],
            prior_items=prior,
            last_served_items=["381"],
        )
        assert resolved["kind"] == "resolved"
        assert "381" not in resolved["items"]
        assert "U-22" in resolved["items"]

    def test_contrastive_without_a_base_clarifies_instead_of_reading(
            self):
        resolved = resolve_target_set(
            self.OTHER_MACHINERY,
            canvas_items=[], prior_items=[], last_served_items=[],
        )
        assert resolved["kind"] in ("clarify", "none")
