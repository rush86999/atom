# -*- coding: utf-8 -*-
"""Evidence-trim attribution and co-survival (incident closure item 5).

``_enforce_evidence_budget`` promises that a kept decisive line keeps "the
nearest preceding line carrying a ``full:``/``open:`` path, so a surviving row
never loses the citation that makes it checkable". The implementation checked
only ``idx - 1``: a row whose citation sat two lines up (a ``From:`` line, then
a ``Subject:`` line, then the row — the normal shape of a mailbox excerpt)
survived WITHOUT its citation while the elision note implied otherwise.

These tests require the answer, its citation, its units and its formula
dependencies to survive TOGETHER, or the note to state what was dropped.
"""
import pytest

import integrations.chat_orchestrator as co


@pytest.fixture()
def small_budget(monkeypatch):
    monkeypatch.setattr(co, "_EVIDENCE_BUDGET_CHARS", 1200)


BLOCK_HEADER = "- [ingested mailbox] From: Joel Seguin <joel@fintek.example>"
BLOCK_SUBJECT = "  Subject: F-5216 pricing | full: knowledge/conversations/msg-1"
ROW = ("R235 | Product Name=F-52\"x16G | LIST Price=7519.0 | "
       "Factory Price=5350 | $7,519.00")
FORMULAS = "FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9 | I235==H235+700"


class TestNearestAttribution:
    def test_citation_two_lines_above_the_row_survives(self, small_budget):
        """The documented contract: NEAREST preceding, not immediately
        preceding."""
        lines = [BLOCK_HEADER, BLOCK_SUBJECT]
        lines += [f"- [ingested mailbox] unrelated body {i} " + "y" * 90
                  for i in range(14)]
        lines += [ROW, FORMULAS]
        out = co._enforce_evidence_budget("\n".join(lines))
        assert "R235" in out, "the decisive row must survive"
        assert "full: knowledge/conversations/msg-1" in out, (
            "the row survived without the citation that makes it checkable")

    def test_citation_is_not_borrowed_across_a_blank_line(self, small_budget):
        """A blank line separates blocks; a row must not inherit the previous
        message's citation."""
        lines = [BLOCK_SUBJECT, BLOCK_HEADER, "", ROW, FORMULAS]
        lines += [f"- [ingested mailbox] filler {i} " + "z" * 90
                  for i in range(14)]
        out = co._enforce_evidence_budget("\n".join(lines))
        assert "R235" in out
        # The citation belongs to the block ABOVE the blank line, not this row.
        kept_section = out.split("R235")[0]
        assert "knowledge/conversations/msg-1" not in kept_section.split("\n")[-1]

    def test_row_with_no_citation_anywhere_still_survives(self, small_budget):
        lines = [f"- filler {i} " + "q" * 90 for i in range(14)]
        lines += [ROW, FORMULAS]
        out = co._enforce_evidence_budget("\n".join(lines))
        assert "R235" in out


class TestCoSurvival:
    def test_row_units_and_formula_dependencies_survive_together(self, small_budget):
        """A surviving citation alone does not establish a derivation: the row,
        its units and the formula chain that derives it must all be present."""
        lines = [BLOCK_HEADER, BLOCK_SUBJECT]
        lines += [f"- [ingested mailbox] noise {i} " + "n" * 95
                  for i in range(16)]
        lines += [
            ROW,
            "  Weight: 12.5 kg | Lead time: 6 weeks",
            FORMULAS,
        ]
        out = co._enforce_evidence_budget("\n".join(lines))
        assert "R235" in out, "decisive row dropped"
        assert "12.5 kg" in out, "unit dropped from the retained row"
        assert "G235==F235*0.9" in out, "formula dependency dropped"

    def test_note_states_what_was_dropped(self, small_budget):
        lines = [BLOCK_HEADER]
        lines += [f"- [ingested mailbox] body {i} " + "b" * 200
                  for i in range(20)]
        lines += [ROW]
        out = co._enforce_evidence_budget("\n".join(lines))
        assert "elided" in out
        assert "decisive line(s)" in out and "other line(s)" in out

    def test_output_respects_the_cap(self, small_budget):
        lines = [BLOCK_SUBJECT] + [
            f"R{i} | price=1000 | $1,000.00 | " + "x" * 300 for i in range(20)
        ]
        out = co._enforce_evidence_budget("\n".join(lines))
        assert len(out) <= co._EVIDENCE_BUDGET_CHARS

    def test_short_block_passes_through_untouched(self):
        assert co._enforce_evidence_budget("short block") == "short block"
        assert co._enforce_evidence_budget(None) is None
