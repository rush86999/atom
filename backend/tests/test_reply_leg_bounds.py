# -*- coding: utf-8 -*-
"""Bounds on the REPLY LEG's verification stage, and the SC fan-out pins.

TWO DEFECTS MEASURED LIVE 2026-09-16 (one derivation turn, clean single
instance, source `cf766a4110bf-dirty.af8586830a60`):

1. The reply was STREAMED in 5.6 s and the reply leg finished in 9.6 s, yet the
   POST took **180.0 s** end to end. The difference was the verification panel:
   it ran AFTER the reply existed, unbounded, and its judge samples walked a
   ladder of routes that each truncated ("Structured attempt failed for
   openrouter/…: The output is incomplete due to a max_tokens length limit.").
   The panel judges a COMPLETE reply — provenance, not a gate — so it may not
   hold the request past the turn budget. ``ran=False`` is the contract's
   existing "verification unavailable", which is neither "verified" nor a turn
   failure.

2. Every fan-out logged "SC fan-out: ranking failed (BYOKHandler
   .get_ranked_providers() missing 1 required positional argument: 'complexity');
   samples unpinned" — the voter called a signature that REQUIRES the query
   complexity, so the diversity pins never engaged and the samples fell back to
   blind routing. (The TypeError was swallowed by a broad except, which is why
   it survived: a degraded-but-quiet path looks like a working one.)
"""
import inspect

import pytest


class TestSelfConsistencyFanoutPins:
    """The pins must come from a REAL ranking call, not from a TypeError."""

    def _voter(self, handler):
        from core.llm.self_consistency_voter import SelfConsistencyVoter

        return SelfConsistencyVoter(handler)

    def test_the_complexity_argument_is_actually_passed(self):
        """A handler with the production signature must be rankable."""
        calls = []

        class Handler:
            def analyze_query_complexity(self, prompt, task_type=None):
                calls.append(("analyze", prompt))
                return "MODERATE"

            def get_ranked_providers(self, complexity, **_kw):
                calls.append(("rank", complexity))
                return [("openrouter", "m1"), ("deepseek", "m2")]

        pins = self._voter(Handler())._resolve_fanout_targets(3, prompt="how is x derived")
        assert pins == [("openrouter", "m1"), ("deepseek", "m2"), ("openrouter", "m1")]
        assert ("rank", "MODERATE") in calls, (
            "the ranking call did not receive the complexity it requires")
        assert ("analyze", "how is x derived") in calls

    def test_a_handler_without_an_analyzer_still_ranks(self):
        from core.llm.byok_handler import QueryComplexity

        seen = {}

        class Handler:
            def get_ranked_providers(self, complexity, **_kw):
                seen["complexity"] = complexity
                return [("p1", "m1"), ("p2", "m2")]

        pins = self._voter(Handler())._resolve_fanout_targets(2, prompt="x")
        assert pins == [("p1", "m1"), ("p2", "m2")]
        assert seen["complexity"] == QueryComplexity.MODERATE

    def test_the_old_bug_would_now_be_caught_as_degradation(self):
        """A ranker that raises still degrades to unpinned — silently, but the
        failure is no longer the REQUIRED argument."""
        class Handler:
            def get_ranked_providers(self, complexity, **_kw):
                raise RuntimeError("no candidates")

        assert self._voter(Handler())._resolve_fanout_targets(3, prompt="x") == [None] * 3

    def test_fanout_off_means_unpinned(self, monkeypatch):
        class Handler:
            def get_ranked_providers(self, complexity, **_kw):
                raise AssertionError("must not rank when fan-out is off")

        monkeypatch.setenv("ATOM_SC_FANOUT", "false")
        assert self._voter(Handler())._resolve_fanout_targets(2, prompt="x") == [None] * 2

    def test_a_single_candidate_degrades_to_unpinned(self):
        class Handler:
            def get_ranked_providers(self, complexity, **_kw):
                return [("only", "one")]

        assert self._voter(Handler())._resolve_fanout_targets(2, prompt="x") == [None] * 2

    def test_both_call_sites_pass_the_prompt(self):
        """The complexity can only be derived if the prompt travels with the
        call — a no-prompt call silently ranks MODERATE for every fan-out."""
        from core.llm import self_consistency_voter as scv

        src = inspect.getsource(scv)
        assert src.count("_resolve_fanout_targets(n, prompt=prompt)") == 2


class TestVerifyPanelIsBounded:
    """The panel may not hold the request open past the turn budget."""

    def _src(self):
        import integrations.chat_orchestrator as co

        return inspect.getsource(co.ChatOrchestrator._get_qwen_response)

    def test_every_panel_call_is_wrapped(self):
        src = self._src()
        assert "async def _bounded_verify(" in src
        assert src.count("await _bounded_verify(verify_reply(") == 2, (
            "a verification call is unbounded — the reply is already complete "
            "and the panel is provenance, not a gate")

    def test_a_timeout_is_unavailable_never_verified(self):
        src = self._src()
        block = src[src.index("async def _bounded_verify("):]
        block = block[:block.index("async def _trace(")]
        assert '"ran": False' in block
        assert "verify_panel_timeout" in block
        assert "turn_budget_exhausted" in block
        assert "asyncio.wait_for" in block

    def test_it_uses_the_turn_budget_clock(self):
        src = self._src()
        block = src[src.index("async def _bounded_verify("):]
        block = block[:block.index("async def _trace(")]
        assert "_remaining_budget(_plan_t0, _turn_budget)" in block

    def test_a_panel_error_still_ships_the_reply(self):
        src = self._src()
        block = src[src.index("async def _bounded_verify("):]
        block = block[:block.index("async def _trace(")]
        assert "verify_panel_error" in block

    def test_the_panel_has_its_own_hard_cap(self):
        """Bounded only by the turn, the panel spent the remainder and timed
        out anyway: reply at 21.1 s, response at 95.5 s, no verdict. Its own
        cap decides how much provenance is worth paying for."""
        import integrations.chat_orchestrator as co

        assert co._VERIFY_PANEL_MAX_SECONDS > 0
        assert co._VERIFY_PANEL_MAX_SECONDS < co.CHAT_TURN_BUDGET_DEFAULT_SECONDS
        src = self._src()
        block = src[src.index("async def _bounded_verify("):]
        block = block[:block.index("async def _trace(")]
        assert "_cap = min(_left, _VERIFY_PANEL_MAX_SECONDS)" in block
        assert "timeout=_cap" in block

    def test_a_zero_cap_falls_back_to_the_turn_budget(self, monkeypatch):
        import integrations.chat_orchestrator as co

        monkeypatch.setattr(co, "_VERIFY_PANEL_MAX_SECONDS", 0.0)
        # The resolver-style read keeps 0 meaning "no extra cap".
        src = self._src()
        assert "if _VERIFY_PANEL_MAX_SECONDS > 0 else _left" in src


class TestDerivationGuardScope:
    """The row-use guard must fire on DERIVATION asks only, exactly once.

    Measured on the 8004 acceptance run (case 2, the directional ask,
    `ask=False matched-row-evidence=True`): the evidence carried the matched
    row's formulas — the ingested workbook text reaches the tool block on
    non-derivation asks too — so the guard fired and recorded
    `evidence_ignored` against a reply that had answered the actual question
    correctly. Worse, the guard fired TWICE in that turn: the common
    post-reply chain runs for STREAMED replies as well, so the corrective
    retry was dispatched a second time (and both times ran into the budget).
    """

    def _src(self):
        import integrations.chat_orchestrator as co

        return inspect.getsource(co.ChatOrchestrator._get_qwen_response)

    def test_the_streaming_guard_requires_a_derivation_ask(self):
        src = self._src()
        assert "if (_is_derivation_ask and _tool_block\n" in src
        assert "_derivation_reply_ignored_the_row(\n" in src

    def test_the_common_chain_guard_requires_a_derivation_ask(self):
        src = self._src()
        assert "elif (_streamed is None and _is_derivation_ask" in src, (
            "the post-reply chain re-runs for streamed replies, so without the "
            "streamed-gate the corrective retry fires twice per turn")

    def test_the_evidence_ignored_verdict_is_recorded_only_there(self):
        """One record site per leg, both inside the gated branch."""
        src = self._src()
        assert src.count("await record_evidence_ignored(") == 2
        assert src.count("_cross_route_retry_route(") == 2  # one per leg

    def test_a_non_derivation_turn_with_workbook_text_is_not_flagged(self):
        """The predicate itself is unchanged — the ASK is the gate."""
        import integrations.chat_orchestrator as co

        block = ("SQL RESULT from 'PRICE VIPUL (6).xlsx'\n"
                 "R235 | Product Name=F-52\"x16G | LIST Price=7519.0 | "
                 "FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9")
        assert co._derivation_reply_ignored_the_row(
            "The attachment was forwarded internally on brennan.ca.", block) is True
        assert co._derivation_ask("who sent the PRICE VIPUL attachment?") is False


class TestPanelRegenerationIsBounded:
    """The panel's own corrective regeneration must spend the turn budget.

    Measured 2026-09-16 on the frozen acceptance build: the panel returned
    `grounded=False` after 8.5 s, its regeneration was a BARE await, and the
    turn went on to walk routes for ~150 s more (a 401, two zero-visible
    streams, one length-truncated completion) — 213.1 s for a reply the user
    already had at 55 s. A corrective regeneration is a quality improvement on a
    complete reply, exactly like the guard regenerations, so it uses the same
    bounded path.
    """

    def _src(self):
        import integrations.chat_orchestrator as co

        return inspect.getsource(co.ChatOrchestrator._get_qwen_response)

    def test_the_panel_regeneration_goes_through_the_guard(self):
        src = self._src()
        assert "_panel_fix = await _guarded_regen(" in src
        assert "VERIFICATION FAILURE" in src

    def test_a_skipped_regeneration_ships_the_reply_with_the_note(self):
        src = self._src()
        assert "corrective regeneration " in src and "turn budget" in src
        assert "the reply ships " in src

    def test_no_unbounded_completion_remains_after_the_panel(self):
        """Every reply-leg generation is wrapped: streaming, non-streaming and
        both guard/panel regenerations."""
        src = self._src()
        assert "response_data = await self.llm_service.generate_completion(" not in src

    def test_a_skipped_panel_closes_its_coroutine(self):
        """Returning without awaiting leaves a never-awaited coroutine — live
        `RuntimeWarning: coroutine 'verify_reply' was never awaited` on every
        budget-exhausted turn (and a real leak under load)."""
        src = self._src()
        block = src[src.index("async def _bounded_verify("):]
        block = block[:block.index("async def _trace(")]
        assert "_coro.close()" in block
        # ...and the timeout branch lets wait_for cancel it, which is correct.
        assert "asyncio.wait_for(_coro, timeout=_cap)" in block
