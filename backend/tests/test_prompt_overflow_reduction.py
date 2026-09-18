# -*- coding: utf-8 -*-
"""Over-budget evidence reduction (incident closure item 4).

When the assembled prompt exceeds the model's window, the orchestrator shrinks
the EVIDENCE section — the only section the harness may drop. The first
implementation did it with ``overflow_tokens × 4`` characters and a front
``[:_reduced]`` slice, so a decisive row sitting anywhere but the very front was
removed *before* the preservation logic ran. Measured separately: the char/4
rule understates formula-dense evidence by up to 83%.

These tests pin the replacement: reduce in TOKENS, keep the decisive lines
first, never go below the floor, and hand the caller stats saying what survived.
"""
import pytest

from integrations.chat_orchestrator import reduce_evidence_for_overflow

ROW = ("R235 | Product Name=F-52\"x16G | LIST Price=7519.0 | "
       "Factory Price=5350 | $7,519.00")
FORMULAS = ("FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9 | "
            "I235==H235+700 | K235==J235*1.02")


def _block():
    prose = [f"- [ingested mailbox] forwarded note {i} " + "y" * 200
             for i in range(30)]
    # Rows sit DEEP in the block (~5.1k chars in) so a 2k-char front slice
    # provably misses them — the shape that made the old trim destructive.
    return "\n".join(prose[:25] + [ROW, FORMULAS] + prose[25:])


class TestDecisiveLinesSurviveTheReduction:
    def test_row_and_formulas_survive_a_large_overflow(self):
        body = _block()
        trimmed, stats = reduce_evidence_for_overflow(body, 2000)
        assert "R235" in trimmed, "the decisive row was removed by the trim"
        assert "G235==F235*0.9" in trimmed, "the formula chain was removed"
        assert stats.get("row", 0) >= 1
        assert stats.get("formula", 0) >= 1

    def test_the_result_is_smaller_than_the_input(self):
        body = _block()
        trimmed, _ = reduce_evidence_for_overflow(body, 2000)
        assert len(trimmed) < len(body)

    def test_front_slice_would_have_lost_the_row(self):
        """Premise check: if this stops holding, the trim is no longer the
        thing keeping the row."""
        body = _block()
        assert "R235" not in body[: len(body) - 2000]

    def test_zero_overflow_keeps_the_block_intact(self):
        body = _block()
        trimmed, _ = reduce_evidence_for_overflow(body, 0)
        assert "R235" in trimmed and "G235==F235*0.9" in trimmed


class TestFloorIsExplicit:
    def test_evidence_is_never_deleted_outright(self):
        """An overflow larger than the block must not reduce the evidence to
        nothing; the floor is what makes the remaining over-budget case
        explicit rather than a silent deletion of the sources."""
        body = _block()
        trimmed, _ = reduce_evidence_for_overflow(body, 10_000_000)
        assert trimmed, "the evidence was deleted instead of floored"
        assert "R235" in trimmed

    def test_floor_is_honoured_in_tokens(self):
        from core.llm.prompt_budget import count_tokens

        body = _block()
        trimmed, _ = reduce_evidence_for_overflow(
            body, 10_000_000, floor_tokens=120)
        tokens, _est = count_tokens(trimmed)
        # The hard char bound may pad slightly; the point is that the floor is
        # a token floor, not a "keep the first 200 chars" rule.
        assert tokens <= 400

    def test_empty_input_is_handled(self):
        assert reduce_evidence_for_overflow("", 500)[0] == ""
        assert reduce_evidence_for_overflow(None, 500)[0] == ""
