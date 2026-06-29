# -*- coding: utf-8 -*-
"""
TDD tests for Phase 3 — match-confidence LLM tie-breaker.

The tiebreaker fires in the partial band (0.50–0.85) where a deterministic
score can't distinguish the right candidate. Calls a budget-tier LLM with
a 2s timeout and a circuit breaker ported from turn_fact_extractor.
"""
from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.match_confidence_tiebreaker import (  # noqa: E402
    TiebreakResult,
    break_tie,
    _circuit_breaker,
    _tiebreak_cache,
)
from core.selector_confidence_service import (  # noqa: E402
    AMBIGUOUS,
    HIGH,
    PARTIAL,
    MatchConfidence,
    SelectorCandidate,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear tiebreaker cache + circuit breaker between tests."""
    _tiebreak_cache.clear()
    _circuit_breaker.reset()


def _candidate(match_count: int = 2) -> SelectorCandidate:
    return SelectorCandidate(
        selector="button",
        match_count=match_count,
        is_text_only=True,
        appeared_after_ms=0,
        tag_hint="BUTTON",
        attributes={},
    )


def _partial_confidence() -> MatchConfidence:
    return MatchConfidence(
        level=PARTIAL,
        score=0.70,
        rationale="2 matches (-0.30); text-only (-0.15)",
        candidates=[_candidate(match_count=2)],
        chosen_index=0,
    )


# ===========================================================================
# Tiebreaker behavior
# ===========================================================================
class TestBreakTie:
    @pytest.mark.asyncio
    async def test_tiebreaker_picks_correct_candidate_from_partial(self):
        """LLM returns chosen_index=1 → result with chosen_index=1 + used_llm=True."""
        candidates = [_candidate(match_count=2), _candidate(match_count=2)]
        # Patch the underlying LLM call
        llm_service = MagicMock()
        llm_service.generate_completion = AsyncMock(
            return_value={
                "text": '{"chosen_index": 1, "rationale": "second is submit button"}',
                "success": True,
            }
        )

        _circuit_breaker.reset()
        with patch(
            "core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED",
            True,
        ):
            result = await break_tie(
                candidates=candidates,
                page_context={"url": "https://example.com/form"},
                llm_service=llm_service,
            )

        assert result.used_llm is True
        assert result.chosen_index == 1
        assert "submit" in result.rationale.lower()

    @pytest.mark.asyncio
    async def test_tiebreaker_returns_minus_one_on_llm_uncertainty(self):
        """LLM returns chosen_index=-1 → propagated as -1 (caller routes to proposal)."""
        candidates = [_candidate(match_count=3)]
        llm_service = MagicMock()
        llm_service.generate_completion = AsyncMock(
            return_value={
                "text": '{"chosen_index": -1, "rationale": "none clearly match"}',
                "success": True,
            }
        )

        _circuit_breaker.reset()
        with patch(
            "core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED",
            True,
        ):
            result = await break_tie(
                candidates=candidates,
                page_context={"url": "https://example.com"},
                llm_service=llm_service,
            )

        assert result.chosen_index == -1
        assert result.used_llm is True

    @pytest.mark.asyncio
    async def test_tiebreaker_caches_on_repeat_selector(self):
        """Same selector+URL → second call returns cache_hit=True, no LLM call."""
        candidates = [_candidate(match_count=2)]
        llm_service = MagicMock()
        llm_service.generate_completion = AsyncMock(
            return_value={
                "text": '{"chosen_index": 0, "rationale": "first one"}',
                "success": True,
            }
        )

        _circuit_breaker.reset()
        with patch(
            "core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED",
            True,
        ), patch(
            "core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED",
            True,
        ):
            r1 = await break_tie(
                candidates=candidates,
                page_context={"url": "https://example.com/form"},
                llm_service=llm_service,
            )
            r2 = await break_tie(
                candidates=candidates,
                page_context={"url": "https://example.com/form"},
                llm_service=llm_service,
            )

        assert r1.cache_hit is False
        assert r2.cache_hit is True
        # LLM only called once
        assert llm_service.generate_completion.call_count == 1


# ===========================================================================
# Circuit breaker (ported from turn_fact_extractor)
# ===========================================================================
class TestCircuitBreaker:
    def test_circuit_breaker_opens_after_5_failures(self):
        from core.llm.match_confidence_tiebreaker import _CircuitBreaker, _CB_THRESHOLD

        cb = _CircuitBreaker()
        for _ in range(_CB_THRESHOLD):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.is_tripped() is True

    def test_circuit_breaker_half_open_probe_after_cooldown(self):
        import time
        from core.llm.match_confidence_tiebreaker import _CircuitBreaker, _CB_THRESHOLD, _CB_COOLDOWN_S

        cb = _CircuitBreaker()
        for _ in range(_CB_THRESHOLD):
            cb.record_failure()
        assert cb.state == "open"

        # Simulate cooldown elapsed
        cb.opened_at = time.time() - (_CB_COOLDOWN_S + 1)
        assert cb.is_tripped() is False  # half-open probe allowed
        assert cb.state == "half_open"

    @pytest.mark.asyncio
    async def test_tiebreaker_timeout_falls_through_to_proposal(self):
        """2s timeout exceeded → returns chosen_index=-1, used_llm=False."""
        candidates = [_candidate(match_count=2)]
        llm_service = MagicMock()

        async def slow_call(*args, **kwargs):
            await asyncio.sleep(10)
            return {"text": "{}", "success": True}

        llm_service.generate_completion = slow_call

        with patch(
            "core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED",
            True,
        ), patch(
            "core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS",
            0.1,
        ):
            result = await break_tie(
                candidates=candidates,
                page_context={"url": "https://example.com"},
                llm_service=llm_service,
            )

        # Timed out → no decision, fall through to proposal
        assert result.chosen_index == -1
        assert result.used_llm is False
