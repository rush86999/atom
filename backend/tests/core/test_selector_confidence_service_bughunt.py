"""Bug-hunt tests for core.selector_confidence_service."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest

from core.selector_confidence_service import (
    SelectorCandidate,
    score_candidates,
    level_from_score,
    coerce_match_level_for_storage,
    MatchConfidence,
    MatchLevel,
    HIGH,
    PARTIAL,
    AMBIGUOUS,
)


def _cand(**kw):
    defaults = dict(
        selector="#id",
        match_count=1,
        is_text_only=False,
        appeared_after_ms=0,
        tag_hint="button",
    )
    defaults.update(kw)
    return SelectorCandidate(**defaults)


# ---------------------------------------------------------------------------
# BUG 1: A candidate that matched ZERO DOM nodes (match_count=0) is scored
#         as HIGH confidence with score 1.0 and rationale "single match".
#         A selector that found nothing must never report HIGH confidence.
# ---------------------------------------------------------------------------
def test_zero_matches_is_not_high_confidence():
    """BUG: match_count=0 candidate reported as HIGH confidence."""
    cand = _cand(match_count=0)
    result = score_candidates([cand])

    assert result.level != HIGH, (
        f"selector matching 0 nodes reported HIGH (score={result.score}); "
        f"zero matches must be ambiguous"
    )
    assert result.score < 1.0
    assert "single match" not in result.rationale


# ---------------------------------------------------------------------------
# Regression: a genuine single match is still HIGH.
# ---------------------------------------------------------------------------
def test_single_match_remains_high():
    """Sanity: exactly one match stays HIGH (guard against over-fixing)."""
    cand = _cand(match_count=1)
    result = score_candidates([cand])
    assert result.level == HIGH
    assert result.score == 1.0
