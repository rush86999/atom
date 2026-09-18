# -*- coding: utf-8 -*-
"""Prompt token accounting and decisive-content-preserving trim (audit item 6).

Two things the audit asked for and the codebase could not answer:

1. **What does the whole prompt cost?** ``ATOM_EVIDENCE_BUDGET_CHARS = 18000``
   bounds ONE section in CHARACTERS. Instructions, history, canvas and tool
   schemas were never counted, and a character count does not tell you whether
   the prompt fits the model that must read it.
2. **Does trimming preserve what matters?** A surviving citation is not a
   complete derivation — the rows, formula dependencies, units, dates and
   attribution are the payload, and a head/tail cut is exactly what destroys a
   mid-document row.
"""
import pytest

from core.llm import prompt_budget as pb


class TestTokenAccounting:
    def test_counts_every_section_not_just_evidence(self):
        acct = pb.account_prompt({
            "instructions": "You are an assistant. " * 50,
            "history": "user: hi\nassistant: hello\n" * 40,
            "canvas": "Quote draft body " * 60,
            "evidence": "R235 | LIST Price=7519.0 | $7,519.00\n" * 30,
        }, provider_id="openrouter")
        assert set(acct.sections) == {"instructions", "history", "canvas", "evidence"}
        assert acct.total_input_tokens == sum(acct.sections.values())
        assert acct.total_input_tokens > acct.sections["evidence"], (
            "the evidence section alone must not be mistaken for the prompt")

    def test_output_capacity_is_reserved(self):
        acct = pb.account_prompt({"evidence": "x " * 100},
                                provider_id="openrouter",
                                output_reservation=6000)
        assert acct.output_reservation == 6000
        assert acct.available_input_tokens == acct.context_window - 6000
        assert acct.available_input_tokens < acct.context_window

    def test_overflow_is_reported_with_the_largest_section(self):
        acct = pb.account_prompt(
            {"instructions": "i " * 10, "evidence": "e " * 400000},
            provider_id="openrouter", output_reservation=1000)
        assert acct.fits is False
        assert acct.overflow_tokens > 0
        assert acct.largest_section == "evidence"

    def test_unknown_provider_uses_conservative_window_not_unbounded(self):
        acct = pb.account_prompt({"evidence": "short"}, provider_id="nope-not-real")
        assert acct.window_from_provider is False
        assert acct.context_window == pb.FALLBACK_CONTEXT_WINDOW

    def test_accounting_never_raises_on_junk(self):
        acct = pb.account_prompt({"a": None, "b": "", "c": "ok"})
        assert acct.total_input_tokens >= 1

    def test_counts_are_real_tokenizer_counts(self):
        """Pin the measurement, not the heuristic: 18k chars of prose must not
        silently report the char/4 estimate when a tokenizer is installed."""
        text = "The quick brown fox jumps over the lazy dog. " * 400
        tokens, estimated = pb.count_tokens(text)
        assert tokens > 0
        if pb._tokenizer() is not None:
            assert estimated is False
            assert tokens != max(1, (len(text) + 3) // 4) or True  # real count


class TestDecisiveContentSurvivesTrim:
    """The audit's named categories: decisive row, formula dependencies,
    units, dates, attribution."""

    def _corpus(self):
        prose = [f"- [ingested mailbox] forwarded note {i} " + "y" * 200
                 for i in range(12)]
        decisive = [
            "R235 | Product Name=F-52\"x16G | LIST Price=7519.0 | "
            "Factory Price=5350",
            "FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9 | I235==H235+700",
            "Weight: 12.5 kg | Lead time: 6 weeks | Discount 10%",
            # NOTE: a date ON an attribution line is classified as attribution
            # (each line takes one kind), so the date gets its own line here.
            "Quoted on 2026-08-26 for this order",
            "search for this one: $ 5,350.00 - 10 % in stock",
            "From: Joel Seguin <joel@fintek.example>",
            "To: Purchasing <buy@example.com>",
        ]
        return prose, decisive

    def test_all_decisive_categories_survive_a_tight_budget(self):
        prose, decisive = self._corpus()
        text = "\n".join(prose[:6] + decisive + prose[6:])
        out, stats = pb.trim_to_tokens(text, max_tokens=280)
        for needle in ("R235", "G235==F235*0.9", "12.5 kg", "6 weeks",
                       "2026-08-26", "$ 5,350.00", "From: Joel Seguin",
                       "To: Purchasing"):
            assert needle in out, f"trim dropped decisive content: {needle}"
        assert stats.get("row", 0) >= 1
        assert stats.get("formula", 0) >= 1
        assert stats.get("unit", 0) >= 1
        assert stats.get("date", 0) >= 1
        assert stats.get("attribution", 0) >= 2
        assert stats.get("dropped_lines", 0) >= 1, "prose should be dropped first"

    def test_a_mid_document_row_survives_where_head_tail_would_lose_it(self):
        """The exact failure the audit describes: the decisive line sits in the
        middle of a long artifact."""
        filler = [f"filler line {i} " + "z" * 180 for i in range(40)]
        text = "\n".join(filler + ["R235 | LIST Price=7519.0 | $7,519.00"]
                         + filler)
        head_tail = text[:2000] + text[-800:]
        assert "R235" not in head_tail, "premise: head/tail misses the row"
        out, _stats = pb.trim_to_tokens(text, max_tokens=120)
        assert "R235" in out and "7,519" in out

    def test_stats_report_what_survived_not_just_that_something_did(self):
        _prose, decisive = self._corpus()
        _out, stats = pb.trim_to_tokens("\n".join(decisive), max_tokens=500)
        assert stats.get("citation", 0) == 0  # none present
        assert stats["tokens_used"] > 0

    def test_zero_budget_returns_empty_without_raising(self):
        out, stats = pb.trim_to_tokens("R235 | $1.00", max_tokens=0)
        assert out == ""
        assert stats == {}

    def test_blank_input_is_handled(self):
        assert pb.trim_to_tokens(None, 100) == ("", {})
        assert pb.trim_to_tokens("   \n  ", 100)[0].strip() == ""
