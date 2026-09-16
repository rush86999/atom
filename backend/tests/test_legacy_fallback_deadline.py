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
