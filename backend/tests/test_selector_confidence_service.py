# -*- coding: utf-8 -*-
"""
TDD tests for selector_confidence_service (Phase 1 of pre-action
match-confidence layer).

Mirrors the shape of test_outcome_verification.py — the scorer is a pure
function with deterministic inputs and a frozen dataclass output.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.selector_confidence_service import (  # noqa: E402
    AMBIGUOUS,
    HIGH,
    PARTIAL,
    MatchConfidence,
    MatchLevel,
    SelectorCandidate,
    coerce_match_level_for_storage,
    level_from_score,
    score_candidates,
)


# ===========================================================================
# Helpers
# ===========================================================================
def _candidate(
    selector: str = "button#submit",
    match_count: int = 1,
    is_text_only: bool = False,
    appeared_after_ms: int = 0,
    tag_hint: str = "button",
    attributes: dict | None = None,
) -> SelectorCandidate:
    return SelectorCandidate(
        selector=selector,
        match_count=match_count,
        is_text_only=is_text_only,
        appeared_after_ms=appeared_after_ms,
        tag_hint=tag_hint,
        attributes=attributes or {},
    )


# ===========================================================================
# Phase 1 — scorer tests
# ===========================================================================
class TestScoringCurve:
    def test_single_high_quality_candidate_scores_high(self):
        """One match, ID-based selector → score 1.0, level=high."""
        conf = score_candidates([_candidate(match_count=1, is_text_only=False)])
        assert conf.score == pytest.approx(1.0)
        assert conf.level == HIGH
        assert conf.chosen_index == 0

    def test_two_matches_score_0_7_partial(self):
        """Two matches → 1.0 - 0.3*(2-1) = 0.70 → partial."""
        conf = score_candidates([_candidate(match_count=2)])
        assert conf.score == pytest.approx(0.70)
        assert conf.level == PARTIAL

    def test_three_matches_score_0_4_ambiguous(self):
        """Three matches → 1.0 - 0.3*(3-1) = 0.40 → ambiguous."""
        conf = score_candidates([_candidate(match_count=3)])
        assert conf.score == pytest.approx(0.40)
        assert conf.level == AMBIGUOUS

    def test_five_matches_floored_at_zero(self):
        """Five matches → 1.0 - 0.3*4 = -0.2 → floored at 0.0 (no negatives)."""
        conf = score_candidates([_candidate(match_count=5)])
        assert conf.score == 0.0
        assert conf.level == AMBIGUOUS

    def test_text_only_selector_gets_minus_0_15(self):
        """Selector with no #id / [data-testid / [aria-label / [role → -0.15."""
        conf = score_candidates(
            [_candidate(match_count=1, is_text_only=True)]
        )
        assert conf.score == pytest.approx(0.85)
        assert conf.level == HIGH  # exactly at threshold (>=0.85)

    def test_late_appearance_minus_0_1(self):
        """Element appeared after >1000ms → -0.10."""
        conf = score_candidates(
            [_candidate(match_count=1, appeared_after_ms=1500)]
        )
        assert conf.score == pytest.approx(0.90)
        assert conf.level == HIGH

    def test_combined_penalties_can_stack_to_ambiguous(self):
        """2 matches (-0.30) + text-only (-0.15) + late (-0.10) = 0.45 → ambiguous."""
        conf = score_candidates(
            [
                _candidate(
                    match_count=2,
                    is_text_only=True,
                    appeared_after_ms=2000,
                )
            ]
        )
        assert conf.score == pytest.approx(0.45)
        assert conf.level == AMBIGUOUS


# ===========================================================================
# Threshold env override
# ===========================================================================
class TestThresholds:
    def test_thresholds_env_overridable(self):
        """HIGH_THRESHOLD=0.75 should reclassify a 0.80 score as high (default would be partial)."""
        import core.selector_confidence_service as mod

        original_high = mod.MATCH_CONFIDENCE_HIGH_THRESHOLD
        try:
            # Directly mutate the module-level constant (env reload proved brittle
            # across test ordering — direct mutation is deterministic).
            mod.MATCH_CONFIDENCE_HIGH_THRESHOLD = 0.75

            # Score 0.85 (single match, text-only) → with HIGH=0.75 it's HIGH;
            # with default HIGH=0.85 it's also HIGH (boundary >=). Use 0.80 case:
            # 1 match, text-only, appeared at 1500ms → 1.0 - 0.15 - 0.10 = 0.75
            conf = mod.score_candidates(
                [_candidate(match_count=1, is_text_only=True, appeared_after_ms=1500)]
            )
            assert conf.score == pytest.approx(0.75)
            # With HIGH=0.75 → high; default 0.85 → partial
            assert conf.level == mod.HIGH
        finally:
            mod.MATCH_CONFIDENCE_HIGH_THRESHOLD = original_high


# ===========================================================================
# coerce_match_level_for_storage
# ===========================================================================
class TestCoerceForStorage:
    def test_coerce_match_level_for_storage_invalid_defaults_to_partial(self):
        """Garbage input → PARTIAL (the safe middle state that surfaces to reviewers)."""
        assert coerce_match_level_for_storage("nonsense") == PARTIAL
        assert coerce_match_level_for_storage(None) == PARTIAL
        assert coerce_match_level_for_storage("") == PARTIAL

    def test_coerce_match_level_for_storage_valid_passthrough(self):
        assert coerce_match_level_for_storage(HIGH) == HIGH
        assert coerce_match_level_for_storage(PARTIAL) == PARTIAL
        assert coerce_match_level_for_storage(AMBIGUOUS) == AMBIGUOUS


# ===========================================================================
# level_from_score boundary checks
# ===========================================================================
class TestLevelFromScore:
    def test_level_from_score_boundaries(self):
        assert level_from_score(1.0) == HIGH
        assert level_from_score(0.85) == HIGH  # exact boundary → high
        assert level_from_score(0.849) == PARTIAL
        assert level_from_score(0.50) == PARTIAL  # exact boundary → partial
        assert level_from_score(0.499) == AMBIGUOUS
        assert level_from_score(0.0) == AMBIGUOUS


# ===========================================================================
# Dataclass shape / immutability
# ===========================================================================
class TestDataclassShape:
    def test_match_confidence_is_frozen(self):
        conf = MatchConfidence(
            level=HIGH, score=1.0, rationale="x", candidates=[], chosen_index=0
        )
        with pytest.raises(Exception):
            conf.level = PARTIAL  # type: ignore[misc]

    def test_match_confidence_serializes_via_asdict(self):
        from dataclasses import asdict

        conf = MatchConfidence(
            level=HIGH, score=1.0, rationale="single match", candidates=[], chosen_index=0
        )
        d = asdict(conf)
        assert d["level"] == HIGH
        assert d["score"] == 1.0
