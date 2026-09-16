# -*- coding: utf-8 -*-
"""Streaming dispatch-time window check — wiring contract (item 4).

The streaming path had no context-window check at all: it iterated providers
for the requested model and let the provider reject an oversized prompt. The
non-streaming path already filters candidates by
``estimated_tokens + output reservation``.

The fix is only as good as its plumbing: a measured token count has to travel
from the orchestrator's accounting, through ``LLMService.stream_completion``,
into ``BYOKHandler.stream_completion``, or the check silently reverts to
"nothing was measured" and never fires. These tests pin that chain, because a
regression here is invisible — the turn still succeeds, just without the guard.
"""
import inspect

import pytest


class TestMeasuredTokensReachTheStreamingHandler:
    def test_llm_service_stream_completion_accepts_it(self):
        from core.llm_service import LLMService

        params = inspect.signature(LLMService.stream_completion).parameters
        assert "estimated_tokens" in params, (
            "LLMService.stream_completion dropped estimated_tokens; the "
            "streaming window check can never fire")

    def test_byok_handler_stream_completion_accepts_it(self):
        from core.llm.byok_handler import BYOKHandler

        params = inspect.signature(BYOKHandler.stream_completion).parameters
        assert "estimated_tokens" in params

    def test_llm_service_forwards_it_to_the_handler(self):
        """Shape pin: the parameter existing is not enough — it must be passed
        on, or the handler always sees None."""
        from core.llm_service import LLMService

        src = inspect.getsource(LLMService.stream_completion)
        assert "estimated_tokens=estimated_tokens" in src, (
            "LLMService accepts estimated_tokens but does not forward it")

    def test_orchestrator_supplies_the_measured_count(self):
        """The orchestrator computes the account; it must hand the measured
        total to the streaming dispatch."""
        import integrations.chat_orchestrator as co

        src = inspect.getsource(co)
        assert "estimated_tokens=(" in src
        assert "_acct.total_input_tokens" in src, (
            "the streaming dispatch no longer passes the measured token count")

    def test_non_streaming_path_still_has_its_override(self):
        from core.llm.byok_handler import BYOKHandler

        params = inspect.signature(BYOKHandler.generate_response).parameters
        assert "estimated_tokens" in params


class TestWindowCheckIsDestructiveOnlyWhenMeasured:
    """The guard must never be the reason a turn produces nothing."""

    def test_primary_is_never_skipped(self):
        """Source-level invariant: the skip condition excludes the first
        candidate, so a single-provider install cannot be skipped into
        silence."""
        from core.llm.byok_handler import BYOKHandler

        src = inspect.getsource(BYOKHandler.stream_completion)
        assert "provider_order[0]" in src, (
            "the window check no longer exempts the primary candidate — an "
            "over-window install could now be skipped into no answer")
