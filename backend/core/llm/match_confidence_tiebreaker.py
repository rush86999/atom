"""
Match-Confidence LLM Tie-breaker — disambiguates the partial band (0.50–0.85).

When the deterministic scorer returns ``level=partial`` (multiple candidates,
no clear winner), this module calls a budget-tier LLM to pick the best one.
Mirrors the pattern in ``core/llm/canvas_summary_service.py``: hard 2s
timeout, never raises, never blocks the agent turn.

Circuit breaker (ported from ``core/turn_fact_extractor.py``): 5 consecutive
failures → 120s cooldown → half-open probe → close-on-success. Prevents LLM
outages from cascading into proposal-storms.

Result cache: repeat selectors on the same hostname amortize to zero LLM
cost (cache_hit=True). Keyed on hash(selectors + URL hostname).

See docs/architecture/MATCH_CONFIDENCE.md § Phase 3.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from core.selector_confidence_service import SelectorCandidate

logger = logging.getLogger(__name__)


# ===========================================================================
# Feature flags
# ===========================================================================
SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED = (
    os.getenv("SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED", "true").lower() == "true"
)
SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS = float(
    os.getenv("SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS", "2.0")
)
SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED = (
    os.getenv("SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED", "true").lower() == "true"
)

# Circuit breaker tunables (mirror turn_fact_extractor)
_CB_THRESHOLD = 5
_CB_COOLDOWN_S = 120


# ===========================================================================
# Result type
# ===========================================================================
@dataclass(frozen=True)
class TiebreakResult:
    """Outcome of an LLM tie-break call."""

    chosen_index: int           # -1 = LLM couldn't decide
    rationale: str
    used_llm: bool              # True iff an LLM call actually fired
    cache_hit: bool = False


# ===========================================================================
# Circuit breaker (ported from turn_fact_extractor._CircuitBreaker)
# ===========================================================================
class _CircuitBreaker:
    """Closed → Open (after N consecutive failures) → Half-open (after cooldown)."""

    __slots__ = ("failures", "opened_at", "state")

    def __init__(self):
        self.failures = 0
        self.opened_at = 0.0
        self.state = "closed"  # closed | open | half_open

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= _CB_THRESHOLD and self.state != "open":
            self.state = "open"
            self.opened_at = time.time()
            logger.warning(
                "match_confidence tiebreaker circuit breaker OPENED after %d "
                "consecutive failures (cooldown=%.0fs) — tiebreaks skipped",
                self.failures, _CB_COOLDOWN_S,
            )

    def record_success(self) -> None:
        if self.state != "closed":
            logger.info(
                "match_confidence tiebreaker circuit breaker CLOSED (recovered "
                "after %d failures)",
                self.failures,
            )
        self.failures = 0
        self.state = "closed"
        self.opened_at = 0.0

    def is_tripped(self) -> bool:
        if self.state == "closed":
            return False
        if (time.time() - self.opened_at) >= _CB_COOLDOWN_S:
            if self.state == "open":
                self.state = "half_open"
                logger.info("match_confidence tiebreaker circuit breaker HALF-OPEN — probing")
            return False  # let the probe through
        return True  # still in cooldown

    def reset(self) -> None:
        """Test hook."""
        self.failures = 0
        self.state = "closed"
        self.opened_at = 0.0


_circuit_breaker = _CircuitBreaker()


# ===========================================================================
# In-process result cache (TTL-bounded, never grows unbounded)
# ===========================================================================
from collections import OrderedDict

_TIEBREAK_CACHE_MAX = 256
_TIEBREAK_CACHE_TTL_S = 600  # 10 min
_tiebreak_cache: "OrderedDict[str, tuple[TiebreakResult, float]]" = OrderedDict()


def _cache_key(candidates: List[SelectorCandidate], page_context: Dict[str, Any]) -> str:
    """Hash on selectors + URL hostname — repeat selectors amortize."""
    selectors_blob = "|".join(c.selector for c in candidates)
    hostname = urlparse(page_context.get("url", "")).hostname or ""
    raw = f"{selectors_blob}::{hostname}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _cache_get(key: str) -> Optional[TiebreakResult]:
    if key not in _tiebreak_cache:
        return None
    result, expires_at = _tiebreak_cache[key]
    if time.time() > expires_at:
        _tiebreak_cache.pop(key, None)
        return None
    _tiebreak_cache.move_to_end(key)
    return result


def _cache_put(key: str, result: TiebreakResult) -> None:
    _tiebreak_cache[key] = (result, time.time() + _TIEBREAK_CACHE_TTL_S)
    _tiebreak_cache.move_to_end(key)
    while len(_tiebreak_cache) > _TIEBREAK_CACHE_MAX:
        _tiebreak_cache.popitem(last=False)


# ===========================================================================
# Prompt
# ===========================================================================
def _build_prompt(candidates: List[SelectorCandidate], page_context: Dict[str, Any]) -> str:
    cand_lines = "\n".join(
        f"  {i}. <{c.tag_hint or 'unknown'}> "
        f"selector={c.selector!r} match_count={c.match_count} "
        f"attrs={json.dumps(c.attributes)[:120]}"
        for i, c in enumerate(candidates)
    )
    url = page_context.get("url", "(unknown)")
    surrounding_text = (page_context.get("surrounding_text") or "")[:500]
    return f"""You are a DOM selector tie-breaker. Given N candidate elements resolved by a CSS selector, return JSON indicating which one is the intended click/fill target.

Page URL: {url}
Surrounding text: {surrounding_text}

Candidates:
{cand_lines}

Return ONLY JSON: {{"chosen_index": <0-based int or -1>, "rationale": "<one sentence>"}}
Return chosen_index=-1 if none clearly match the intended action."""


def _parse_llm_response(text: str) -> TiebreakResult:
    """Extract chosen_index + rationale from LLM output. Never raises."""
    if not text:
        return TiebreakResult(chosen_index=-1, rationale="empty LLM response", used_llm=True)
    # Find first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return TiebreakResult(chosen_index=-1, rationale="non-JSON response", used_llm=True)
    try:
        payload = json.loads(text[start : end + 1])
        idx = int(payload.get("chosen_index", -1))
        rationale = str(payload.get("rationale", ""))[:300]
        return TiebreakResult(chosen_index=idx, rationale=rationale, used_llm=True)
    except Exception as e:
        return TiebreakResult(
            chosen_index=-1,
            rationale=f"LLM JSON parse failed: {type(e).__name__}",
            used_llm=True,
        )


# ===========================================================================
# Public entrypoint
# ===========================================================================
async def break_tie(
    candidates: List[SelectorCandidate],
    page_context: Dict[str, Any],
    llm_service: Any,
) -> TiebreakResult:
    """
    Pick the best candidate via a budget-tier LLM call.

    Behavior:
      - Circuit breaker tripped → return chosen_index=-1, used_llm=False
      - Cache hit → return cached result with cache_hit=True
      - LLM timeout (>=SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS) → chosen_index=-1
      - LLM success → parsed result with used_llm=True

    Never raises.
    """
    if not SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED:
        return TiebreakResult(
            chosen_index=-1, rationale="tiebreaker disabled", used_llm=False
        )

    if _circuit_breaker.is_tripped():
        return TiebreakResult(
            chosen_index=-1,
            rationale="circuit breaker open — falling through to proposal",
            used_llm=False,
        )

    # Cache lookup
    if SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED:
        key = _cache_key(candidates, page_context)
        cached = _cache_get(key)
        if cached is not None:
            return TiebreakResult(
                chosen_index=cached.chosen_index,
                rationale=cached.rationale,
                used_llm=True,
                cache_hit=True,
            )
    else:
        key = ""

    prompt = _build_prompt(candidates, page_context)

    try:
        raw = await asyncio.wait_for(
            llm_service.generate_completion(
                messages=[
                    {"role": "system", "content": "You are a DOM selector tie-breaker. Return only JSON."},
                    {"role": "user", "content": prompt},
                ],
                model="auto",
                temperature=0.0,
                max_tokens=200,
            ),
            timeout=SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        _circuit_breaker.record_failure()
        logger.warning(
            "match_confidence tiebreaker timed out after %.1fs",
            SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS,
        )
        return TiebreakResult(
            chosen_index=-1,
            rationale=f"LLM timeout ({SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS}s) — falling through to proposal",
            used_llm=False,
        )
    except Exception as e:
        _circuit_breaker.record_failure()
        logger.warning(f"match_confidence tiebreaker LLM call failed: {e}")
        return TiebreakResult(
            chosen_index=-1,
            rationale=f"LLM error: {type(e).__name__}",
            used_llm=False,
        )

    # Parse
    text = ""
    if isinstance(raw, dict):
        text = raw.get("text") or raw.get("content") or ""
    elif isinstance(raw, str):
        text = raw
    result = _parse_llm_response(text)

    _circuit_breaker.record_success()

    if SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED and key:
        _cache_put(key, result)

    return result
