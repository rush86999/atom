"""
Selector Confidence Service — pre-action match-confidence scorer.

Answers the Reddit critique: Atom's hidden a11y / canvas state expresses
*structure*, not *uncertainty*. When an agent clicks a field that moved,
loaded late, or partially matched, it had no way to say *"I think this is
the target because…"* before acting. ``browser_click`` silently took the
first ``query_selector`` match.

This module mirrors the existing post-action tri-state in
``core/tool_outcome_verifier.py`` (VERIFIED / UNVERIFIED / FAILED_VERIFICATION)
but for *pre-action* selector resolution. The discriminator is:

  - ``high``      → exactly the kind of match the agent meant (proceed)
  - ``partial``   → multiple candidates; best one plausibly correct (tiebreak)
  - ``ambiguous`` → can't tell; route to a human via ProposalService

Design contract (see docs/architecture/MATCH_CONFIDENCE.md):
  - Pure functions: never raise, deterministic on inputs.
  - Score curve floored at 0.0 (no negative confidences).
  - Thresholds env-overridable for per-deployment tuning.
  - ``coerce_match_level_for_storage`` mirrors ``coerce_verified_for_storage``.

Feature flags:
  SELECTOR_CONFIDENCE_ENABLED              — master switch (default: on)
  MATCH_CONFIDENCE_HIGH_THRESHOLD          — >= this is high (default: 0.85)
  MATCH_CONFIDENCE_PARTIAL_THRESHOLD       — >= this is partial (default: 0.50)
  MATCH_CONFIDENCE_FORCE_PROPOSAL          — gate partial/ambiguous (default:
                                              false = shadow mode)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ===========================================================================
# Feature flags (defaults per CLAUDE.md "Pre-Action Match-Confidence Layer")
# ===========================================================================
SELECTOR_CONFIDENCE_ENABLED = (
    os.getenv("SELECTOR_CONFIDENCE_ENABLED", "true").lower() == "true"
)
MATCH_CONFIDENCE_HIGH_THRESHOLD = float(
    os.getenv("MATCH_CONFIDENCE_HIGH_THRESHOLD", "0.85")
)
MATCH_CONFIDENCE_PARTIAL_THRESHOLD = float(
    os.getenv("MATCH_CONFIDENCE_PARTIAL_THRESHOLD", "0.50")
)
# Shadow mode by default — computation + audit always on, gating off.
MATCH_CONFIDENCE_FORCE_PROPOSAL = (
    os.getenv("MATCH_CONFIDENCE_FORCE_PROPOSAL", "false").lower() == "true"
)


# ===========================================================================
# Tri-state discriminator values (mirror tool_outcome_verifier.py:33-35)
# ===========================================================================
HIGH = "high"
PARTIAL = "partial"
AMBIGUOUS = "ambiguous"

_VALID_LEVELS = {HIGH, PARTIAL, AMBIGUOUS}


class MatchLevel:
    """Namespace constants — mirrors the VerifiedOutcome pattern."""

    HIGH = HIGH
    PARTIAL = PARTIAL
    AMBIGUOUS = AMBIGUOUS


# ===========================================================================
# Penalty weights — exposed as module constants for test/audit visibility
# ===========================================================================
_PER_EXTRA_MATCH_PENALTY = 0.30   # 2 matches → -0.30, 3 → -0.60, ...
_TEXT_ONLY_PENALTY = 0.15         # selector has no #id / [data-testid / [aria-label / [role
_LATE_APPEARANCE_PENALTY = 0.10   # element appeared after >1000ms
_LATE_APPEARANCE_THRESHOLD_MS = 1000


# ===========================================================================
# Frozen dataclasses
# ===========================================================================
@dataclass(frozen=True)
class SelectorCandidate:
    """
    A single resolved candidate for a selector.

    ``match_count`` is the total number of DOM nodes the selector matched;
    we typically only enumerate attributes for the first few for cost reasons
    but the count itself drives the multiplicity penalty.
    """

    selector: str
    match_count: int
    is_text_only: bool
    appeared_after_ms: int
    tag_hint: str
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchConfidence:
    """
    Parsed pre-action confidence envelope.

    ``level`` is the tri-state: 'high' | 'partial' | 'ambiguous'.
    ``score`` is the raw 0.0–1.0 score (floored, never negative).
    ``rationale`` is a human/LLM-readable explanation — surfaced to the LLM
        via ``byok_handler`` stringification and to reviewers via the
        proposal description.
    ``candidates`` is the enumerated candidate list (capped).
    ``chosen_index`` is the index into ``candidates`` the scorer thinks is
        most likely correct (-1 if no candidates).
    """

    level: str
    score: float
    rationale: str
    candidates: List[SelectorCandidate] = field(default_factory=list)
    chosen_index: int = -1

    @property
    def is_high(self) -> bool:
        return self.level == HIGH

    @property
    def requires_review(self) -> bool:
        return self.level in {PARTIAL, AMBIGUOUS}

    def to_dict(self) -> Dict[str, Any]:
        """Serializable view — used in tool_result dicts + audit metadata."""
        from dataclasses import asdict

        return asdict(self)


# ===========================================================================
# Scorer
# ===========================================================================
def level_from_score(score: float) -> str:
    """
    Map a raw score to a level using current env thresholds.

    Boundaries (>=):
      high_threshold (default 0.85) → high
      partial_threshold (default 0.50) → partial
      below partial → ambiguous
    """
    if score >= MATCH_CONFIDENCE_HIGH_THRESHOLD:
        return HIGH
    if score >= MATCH_CONFIDENCE_PARTIAL_THRESHOLD:
        return PARTIAL
    return AMBIGUOUS


def score_candidates(candidates: List[SelectorCandidate]) -> MatchConfidence:
    """
    Score a list of selector candidates.

    The first candidate in the list is treated as the *primary* (the one the
    caller would have clicked under the old ``query_selector`` behavior). We
    score the *resolution* as a whole — typically the caller passes a single
    SelectorCandidate with ``match_count`` set to the number of DOM matches.

    Penalties (applied multiplicatively in rationale but additively to the
    score, floored at 0.0):
      - ``-0.30`` per extra match (N-1)
      - ``-0.15`` if selector is text-only (no structural anchor)
      - ``-0.10`` if element appeared after >1000ms (late load)

    Returns a ``MatchConfidence`` with ``level``, ``score``, ``rationale``,
    ``candidates``, and ``chosen_index`` set. Never raises.
    """
    if not candidates:
        return MatchConfidence(
            level=AMBIGUOUS,
            score=0.0,
            rationale="0 matches within timeout",
            candidates=[],
            chosen_index=-1,
        )

    primary = candidates[0]
    rationale_parts: List[str] = []
    score = 1.0

    # Multiplicity penalty
    extra = max(0, primary.match_count - 1)
    if extra > 0:
        score -= _PER_EXTRA_MATCH_PENALTY * extra
        rationale_parts.append(
            f"{primary.match_count} matches (-{_PER_EXTRA_MATCH_PENALTY * extra:.2f})"
        )
    else:
        rationale_parts.append("single match")

    # Text-only selector penalty
    if primary.is_text_only:
        score -= _TEXT_ONLY_PENALTY
        rationale_parts.append("text-only selector (-{_p:.2f})".format(_p=_TEXT_ONLY_PENALTY))

    # Late-appearance penalty
    if primary.appeared_after_ms > _LATE_APPEARANCE_THRESHOLD_MS:
        score -= _LATE_APPEARANCE_PENALTY
        rationale_parts.append(
            "appeared after {ms}ms (-{_p:.2f})".format(
                ms=primary.appeared_after_ms, _p=_LATE_APPEARANCE_PENALTY
            )
        )

    # Floor
    score = max(0.0, score)
    level = level_from_score(score)

    return MatchConfidence(
        level=level,
        score=round(score, 4),
        rationale="; ".join(rationale_parts),
        candidates=list(candidates),
        chosen_index=0,
    )


# ===========================================================================
# Storage coercion (mirror coerce_verified_for_storage)
# ===========================================================================
def coerce_match_level_for_storage(value: Optional[str]) -> str:
    """
    Coerce an arbitrary value into a valid stored level.

    Defaults to PARTIAL on any invalid input — the safe middle state that
    surfaces the row to reviewers without forcing a hard block.
    """
    if value in _VALID_LEVELS:
        return value
    return PARTIAL


# ===========================================================================
# Phase 3 — LLM tie-break attach point
# ===========================================================================
async def attach_tiebreak(
    confidence: MatchConfidence,
    page_context: Dict[str, Any],
    llm_service: Any,
) -> MatchConfidence:
    """
    Optionally attach an LLM tie-break to a partial-band confidence.

    Only fires when:
      - level == PARTIAL
      - SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED is true
      - llm_service is not None

    On any LLM failure / timeout / disabled flag, returns the original
    confidence unchanged (caller routes to ProposalService per Phase 4).

    On a successful tie-break with chosen_index >= 0, returns a new
    MatchConfidence with level=HIGH, rationale updated, and chosen_index
    pointing at the LLM-selected candidate.
    """
    if confidence.level != PARTIAL:
        return confidence
    if llm_service is None:
        return confidence

    try:
        # Import lazily to avoid circular imports at module load.
        from core.llm.match_confidence_tiebreaker import break_tie

        result = await break_tie(confidence.candidates, page_context, llm_service)
    except Exception as e:
        logger.debug(f"attach_tiebreak skipped: {e}")
        return confidence

    if not result.used_llm or result.chosen_index < 0:
        return confidence

    # LLM picked a candidate — upgrade to HIGH with the new rationale.
    return MatchConfidence(
        level=HIGH,
        score=confidence.score,  # keep raw score for audit
        rationale=f"LLM tiebreak: {result.rationale}",
        candidates=confidence.candidates,
        chosen_index=result.chosen_index,
    )
