# -*- coding: utf-8 -*-
"""The legacy fallback is part of the request budget, not outside it.

WHAT WAS WRONG (measured 2026-09-16, frozen acceptance run D, source
`cf766a4110bf-dirty.efe192834a75`):

    [deadline] chat-request stage=reply-leg dur=84.2s turn_offset=20.9s
               elapsed=105.1s remaining=9.9s budget=115.0s
    [derivation] corrective retry on a different route: opencode-go/gemini-3-flash
    [verify-panel] skipped — turn budget exhausted
    [intent] using tool-plan routing fields: search_request (conf=0.90)
    Routing to features: [SEARCH, AI_ANALYTICS]          ← +120 s, unbounded
    … POST /api/chat/message 200 at 230.2 s

Every bounded stage behaved — the reply leg stopped inside the 115 s request
budget — and then the turn ran 120 s longer anyway, because the path that
handles "the reply leg produced nothing usable" makes its own NLU call and then
one or more feature-handler calls, none of them aware of the request's clock.

WHY THIS IS AN HONESTY ISSUE, NOT ONLY A LATENCY ONE: the client aborts at
120 s, so work started after that point is work nobody sees — and the canned
template text it eventually returns reads like an answer. A turn whose reply
could not be generated must report a FAILED DELIVERY with quality NOT evaluated
(objective item 5), not a late template.
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import integrations.chat_orchestrator as co  # noqa: E402


def _deadline_with_remaining(remaining_s: float):
    """A TurnDeadline whose clock is ``remaining_s`` from expiry."""
    d = co.TurnDeadline(100.0, label="test")
    d.started_at -= (100.0 - remaining_s)
    return d


class TestTheGateDecision:
    def test_the_reserve_is_positive_and_inside_the_budget(self):
        assert co._LEGACY_TAIL_RESERVE_SECONDS > 0
        assert co._LEGACY_TAIL_RESERVE_SECONDS < co.CHAT_TURN_BUDGET_DEFAULT_SECONDS

    def test_a_nearly_spent_request_does_not_start_the_fallback(self):
        d = _deadline_with_remaining(5.0)
        assert 0 < d.remaining() < co._LEGACY_TAIL_RESERVE_SECONDS
        assert d.expired(reserve=co._LEGACY_TAIL_RESERVE_SECONDS) is True

    def test_a_fresh_request_may_run_it(self):
        d = _deadline_with_remaining(80.0)
        assert d.expired(reserve=co._LEGACY_TAIL_RESERVE_SECONDS) is False

    def test_a_disabled_budget_never_blocks(self):
        d = co.TurnDeadline(0.0, label="test")   # 0 == budgeting off
        assert d.expired(reserve=co._LEGACY_TAIL_RESERVE_SECONDS) is False

    def test_the_feature_slice_is_capped_by_what_is_left(self):
        d = _deadline_with_remaining(10.0)
        assert d.slice(co._FEATURE_ROUTING_MAX_SECONDS) <= 10.0
        assert d.slice(co._FEATURE_ROUTING_MAX_SECONDS) > 9.9
        d2 = _deadline_with_remaining(80.0)
        assert d2.slice(co._FEATURE_ROUTING_MAX_SECONDS) == \
            co._FEATURE_ROUTING_MAX_SECONDS


class TestTheGateIsWiredIntoTheRequestPath:
    def _src(self) -> str:
        return inspect.getsource(co.ChatOrchestrator.process_chat_message)

    def test_the_gate_is_consulted_before_any_fallback_work(self):
        src = self._src()
        assert "_legacy_allowed = not _deadline.expired(" in src
        gate = src.index("_legacy_allowed = not _deadline.expired(")
        assert gate < src.index("if _legacy_allowed:\n                    intent_analysis"), (
            "the NLU completion is started before the budget is checked")
        assert gate < src.index("with _deadline.stage(\"legacy-features\")")

    def test_feature_routing_is_bounded(self):
        src = self._src()
        assert "asyncio.wait_for(" in src
        assert "_deadline.slice(_FEATURE_ROUTING_MAX_SECONDS)" in src
        assert "feature routing timed out" in src

    def test_the_nlu_completion_is_skipped_too(self):
        """The intent completion is the first thing this path would spend."""
        src = self._src()
        assert "intent_analysis = self._fallback_intent_analysis(message)" in src
        assert "an NLU completion is exactly the kind of work" in src

    def test_a_skipped_fallback_is_reported_as_a_budget_failure(self):
        src = self._src()
        assert "if _legacy_skipped_reason:" in src
        assert 'response["error_code"] = "turn_budget_exceeded"' in src
        assert 'response["failure_reason"] = _legacy_skipped_reason' in src
        assert '"stage": "legacy-fallback-skipped"' in src
        assert 'response["success"] = False' in src

    def test_the_canned_template_never_becomes_a_memory_fact(self):
        """`main_message` is the template when the reply leg produced nothing;
        extracting durable facts from it would write invented "facts"."""
        src = self._src()
        assert "if not budget_failure and not _legacy_skipped_reason and main_message:" in src


class TestEveryReplyLegGenerationIsBounded:
    def test_no_bare_completion_remains(self):
        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "= await self.llm_service.generate_completion(" not in src, (
            "a reply-leg generation bypasses the turn budget")
        # ...and the protocol-syntax retry (the one that used to be bare, and
        # that hands the turn to the legacy fallback when it fails) is wrapped.
        assert "_retry = await _guarded_regen(" in src

    def test_the_non_streaming_derivation_retry_is_wrapped(self):
        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "_fix_response = await _guarded_regen(" in src


class TestChainCompletenessGuard:
    """A derivation that walks PART of the chain has not answered the ask.

    Measured 2026-09-16 (frozen run `…071123c13d4b`, route
    `openai/gpt-5-mini`): the reply named the workbook, the row, the sheet and
    the discount/exchange/freight steps, every figure it stated matched the
    store, no fabricated value — and it omitted the margin and ROUNDUP steps
    that PRODUCE the listed price it had just quoted (3/6 chain steps). The case
    failed on completeness alone, so the guard is deterministic about exactly
    that: which of the row's formula cells the reply never states.
    """

    # A REALISTIC block: the matched-row section, another row's chain, and a
    # totals line. Only the MATCHED row's cells may be demanded — an earlier
    # revision scanned the whole block and asked for "R235, S235, D2, G2, H2,
    # I2" on a turn whose matched row was 235, which no reply can satisfy.
    BLOCK = ("SQL RESULT from 'PRICE VIPUL (6).xlsx' sheet 'Sheet1'\n"
             "R235 | Product Name=F-52\"x16G | LIST Price=7519.0\n"
             "FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9 | H235==G235 | "
             "I235==H235+700 | J235==I235 | K235==J235*1.02 | L235==K235/0.87 | "
             "M235==L235/0.86 | N235==ROUNDUP(M235,0)\n"
             "FORMULAS FOR ROW 2 (a computing row of this sheet): D2=P2 | G2=F2*0.9\n"
             "TOTALS ROW: R235==P235-K235 | S235==R235/P235")

    def test_partial_chain_is_detected_in_block_order(self):
        missing = co._missing_chain_cells(
            "Row 235 of Sheet1: G235 = 4815, H235 = 4815, I235 = 5515",
            self.BLOCK)
        assert missing == ["J235", "K235", "L235", "M235", "N235"]

    def test_a_complete_chain_is_not_flagged(self):
        reply = ("G235 4815 H235 4815 I235 5515 J235 5515 K235 5625.3 "
                 "L235 6465.86 M235 7518.44 N235 7519")
        assert co._missing_chain_cells(reply, self.BLOCK) == []

    def test_a_reply_that_cites_nothing_is_left_to_the_other_guard(self):
        """No cell at all is `_derivation_reply_ignored_the_row`'s case — the
        two guards must not both fire on one reply."""
        assert co._missing_chain_cells("I could not read the workbook", self.BLOCK) == []

    def test_one_missing_cell_is_not_worth_a_regeneration(self):
        reply = ("G235 H235 I235 J235 K235 L235 M235")   # N235 missing
        assert co._missing_chain_cells(reply, self.BLOCK) == []

    def test_a_block_without_a_chain_never_fires(self):
        assert co._missing_chain_cells("G235 = 1", "MAIL ONLY: - a message") == []

    def test_only_the_matched_row_is_demanded(self):
        """Other rows' chains and the totals line are not part of the answer."""
        missing = co._missing_chain_cells(
            "Row 235: G235 = 4815, H235 = 4815, I235 = 5515", self.BLOCK)
        assert missing == ["J235", "K235", "L235", "M235", "N235"]
        assert "R235" not in missing and "S235" not in missing
        assert "D2" not in missing and "G2" not in missing

    def test_the_sql_renderer_spelling_also_counts(self):
        """The SQL path writes `cell=formula`; the probe path writes
        `cell==formula`. Both are chain steps."""
        block = ("FORMULAS FOR THE MATCHED ROW(S) — the derivation the original "
                 "workbook computes (cell=formula): G235=F235*0.9 | H235=G235 | "
                 "I235=H235+700 | J235=I235")
        assert co._missing_chain_cells("G235 4815 H235 4815", block) == \
            ["I235", "J235"]

    def test_both_legs_carry_the_guard_and_only_once_per_turn(self):
        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert src.count("_missing_chain_cells(") >= 4      # 2 calls + 2 asserts
        assert "and not _chain_retry_done" in src
        assert src.count("_chain_retry_done = True") == 2
        assert "_chain_retry_done = False" in src
        # The common chain runs for streamed replies too — it must not repeat.
        assert "elif (_streamed is None and _is_derivation_ask and _tool_block" in src

    def test_the_demand_is_scoped_to_the_row_the_reply_answers(self):
        """A multi-row section must not push the regeneration at another row.

        Live 2026-09-16: `missing D169, G169, H169, I169, J169, K169` on a turn
        whose reply — and the acceptance's independent read-back — were about
        row 235.
        """
        block = ("R235 | LIST Price=7519.0\n"
                 "FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9 | H235==G235 | "
                 "I235==H235+700 | J235==I235 | K235==J235*1.02 | "
                 "D169==P169 | G169==F169*0.9 | H169==G169 | I169==H169+700")
        assert co._missing_chain_cells(
            "Row 235: G235 = 4815, H235 = 4815, I235 = 5515", block) == [
                "J235", "K235"]
        # The row-169 reply is judged against ITS row, not row 235's cells.
        assert co._missing_chain_cells(
            "Row 169: D169 = 100, G169 = 90, H169 = 100", block) == []

    def test_a_tie_keeps_the_row_the_block_led_with(self):
        """Equal cite counts fall back to the section's own order.

        Found in the 2026-09-16 review pass: the tie-break ran ``max`` over
        ``sorted(by_row)``, which sorts row keys as STRINGS — so a tie was
        decided lexicographically (row 169 over a block that leads with 235;
        `1000` before `999`), against the "block order breaks ties" intent.
        Dict keys iterate in insertion order, which IS block order.
        """
        block = ("FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9 | H235==G235 | "
                 "I235==H235+700 | D169==P169 | G169==F169*0.9 | H169==G169")
        # One cite each way — a tie. The block led with row 235, so row 235's
        # cells are what may be demanded, not row 169's.
        assert co._missing_chain_cells(
            "H235 = 4815, H169 = 100", block) == ["G235", "I235"]

    def test_a_winning_row_with_fewer_than_three_cells_never_fires(self):
        """Row scoping can shrink the offered set below the 3-cell floor.

        The reply is judged against the row it cites most — even when that
        row's slice of the section is too short to demand anything.
        """
        block = ("FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9 | H235==G235 | "
                 "I235==H235+700 | D169==P169 | G169==F169*0.9")
        assert co._missing_chain_cells(
            "Row 169: D169 = 100, G169 = 90", block) == []
