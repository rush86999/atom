"""Coverage wave w65 — ``core/llm/escalation_manager.py``.

This module (the reactive complement to the proactive stage router) had NO
dedicated tests. These cover every public method + branch, the cooldown /
request-cap machinery, graceful DB-logging failure, and a TDD red→green fix:
rate-limit errors are spec'd as "immediate / highest-priority escalation" yet
were silently blocked by the per-tier cooldown (cooldown was checked BEFORE
the rate-limit branch).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from core.llm.cognitive_tier_system import CognitiveTier
from core.llm.escalation_manager import (
    ESCALATION_COOLDOWN,
    ESCALATION_THRESHOLDS,
    MAX_ESCALATION_LIMIT,
    EscalationManager,
    EscalationReason,
    TIER_ORDER,
)


# ── should_escalate: trigger branches ────────────────────────────────────────


class TestShouldEscalateTriggers:
    def test_quality_below_threshold_escalates(self):
        m = EscalationManager()
        should, reason, target = m.should_escalate(
            CognitiveTier.STANDARD, response_quality=70
        )
        assert should is True
        assert reason == EscalationReason.QUALITY_THRESHOLD
        assert target == CognitiveTier.VERSATILE

    def test_quality_at_threshold_does_not_escalate(self):
        m = EscalationManager()
        threshold = ESCALATION_THRESHOLDS[EscalationReason.QUALITY_THRESHOLD][
            "min_quality_score"
        ]
        should, reason, target = m.should_escalate(
            CognitiveTier.STANDARD, response_quality=threshold
        )
        assert (should, reason, target) == (False, None, None)

    def test_confidence_below_threshold_escalates(self):
        m = EscalationManager()
        should, reason, target = m.should_escalate(
            CognitiveTier.MICRO, confidence=0.4
        )
        assert should is True
        assert reason == EscalationReason.LOW_CONFIDENCE
        assert target == CognitiveTier.STANDARD

    def test_error_escalates(self):
        m = EscalationManager()
        should, reason, target = m.should_escalate(
            CognitiveTier.STANDARD, error="boom"
        )
        assert should is True
        assert reason == EscalationReason.ERROR_RESPONSE
        assert target == CognitiveTier.VERSATILE

    def test_rate_limited_escalates(self):
        m = EscalationManager()
        should, reason, target = m.should_escalate(
            CognitiveTier.STANDARD, rate_limited=True
        )
        assert should is True
        assert reason == EscalationReason.RATE_LIMITED

    def test_no_signal_no_escalation(self):
        m = EscalationManager()
        assert m.should_escalate(CognitiveTier.STANDARD) == (False, None, None)

    def test_priority_error_beats_quality(self):
        """When both error and low quality are present, ERROR wins (checked first)."""
        m = EscalationManager()
        should, reason, _ = m.should_escalate(
            CognitiveTier.STANDARD, response_quality=10, error="err"
        )
        assert reason == EscalationReason.ERROR_RESPONSE


class TestComplexTierGuard:
    def test_complex_never_escalates_even_on_rate_limit(self):
        m = EscalationManager()
        # COMPLEX is the max tier — nothing above it.
        should, reason, target = m.should_escalate(
            CognitiveTier.COMPLEX, rate_limited=True, error="x", response_quality=0
        )
        assert (should, reason, target) == (False, None, None)


class TestRequestEscalationCap:
    def test_request_at_cap_does_not_escalate(self):
        m = EscalationManager()
        rid = "req-cap"
        m.request_escalations[rid] = MAX_ESCALATION_LIMIT
        should, reason, target = m.should_escalate(
            CognitiveTier.STANDARD, response_quality=10, request_id=rid
        )
        assert (should, reason, target) == (False, None, None)

    def test_request_below_cap_still_escalates(self):
        m = EscalationManager()
        rid = "req-ok"
        m.request_escalations[rid] = MAX_ESCALATION_LIMIT - 1
        should, _, _ = m.should_escalate(
            CognitiveTier.STANDARD, response_quality=10, request_id=rid
        )
        assert should is True

    def test_no_request_id_skips_cap_check(self):
        """No request_id → cap never engages (cooldown/quality still drive it)."""
        m = EscalationManager()
        should, _, _ = m.should_escalate(CognitiveTier.STANDARD, response_quality=10)
        assert should is True


# ── Cooldown ─────────────────────────────────────────────────────────────────


class TestCooldown:
    def test_recent_escalation_blocks_same_tier(self):
        m = EscalationManager()
        # Put STANDARD on cooldown (escalation just happened).
        m.escalation_log[CognitiveTier.STANDARD.value] = datetime.now(timezone.utc)
        should, reason, target = m.should_escalate(
            CognitiveTier.STANDARD, response_quality=10
        )
        assert (should, reason, target) == (False, None, None)

    def test_expired_cooldown_allows_escalation(self):
        m = EscalationManager()
        # Cooldown set well in the past → expired.
        m.escalation_log[CognitiveTier.STANDARD.value] = datetime.now(
            timezone.utc
        ) - timedelta(minutes=ESCALATION_COOLDOWN + 1)
        should, reason, _ = m.should_escalate(
            CognitiveTier.STANDARD, response_quality=10
        )
        assert should is True
        assert reason == EscalationReason.QUALITY_THRESHOLD

    def test_cooldown_is_per_source_tier(self):
        """Escalating STANDARD→VERSATILE cools STANDARD, not VERSATILE."""
        m = EscalationManager()
        m.should_escalate(CognitiveTier.STANDARD, response_quality=10)
        assert m._is_on_cooldown(CognitiveTier.STANDARD) is True
        assert m._is_on_cooldown(CognitiveTier.VERSATILE) is False

    def test_rate_limit_bypasses_cooldown(self):
        """SPEC: rate-limit is 'immediate / highest-priority escalation'.

        A rate-limited request on cooldown must STILL escalate — cooldown
        prevents rapid *quality/error* cycling, not a hard rate-limit wall.
        (RED before the fix: cooldown was checked before rate_limited.)
        """
        m = EscalationManager()
        m.escalation_log[CognitiveTier.STANDARD.value] = datetime.now(timezone.utc)
        should, reason, target = m.should_escalate(
            CognitiveTier.STANDARD, rate_limited=True
        )
        assert should is True
        assert reason == EscalationReason.RATE_LIMITED
        assert target == CognitiveTier.VERSATILE

    def test_rate_limit_still_respects_request_cap(self):
        """Rate limit bypasses cooldown but NOT the runaway-cost cap."""
        m = EscalationManager()
        rid = "req-capped"
        m.request_escalations[rid] = MAX_ESCALATION_LIMIT
        m.escalation_log[CognitiveTier.STANDARD.value] = datetime.now(timezone.utc)
        should, _, _ = m.should_escalate(
            CognitiveTier.STANDARD, rate_limited=True, request_id=rid
        )
        assert should is False


class TestIsOnCooldown:
    def test_tier_without_log_not_on_cooldown(self):
        assert EscalationManager()._is_on_cooldown(CognitiveTier.HEAVY) is False


class TestGetCooldownRemaining:
    def test_no_log_returns_zero(self):
        assert EscalationManager().get_cooldown_remaining(CognitiveTier.HEAVY) == 0.0

    def test_recent_log_returns_positive_within_window(self):
        m = EscalationManager()
        m.escalation_log[CognitiveTier.STANDARD.value] = datetime.now(timezone.utc)
        remaining = m.get_cooldown_remaining(CognitiveTier.STANDARD)
        assert 0 < remaining <= ESCALATION_COOLDOWN * 60

    def test_expired_log_clamped_to_zero(self):
        m = EscalationManager()
        m.escalation_log[CognitiveTier.STANDARD.value] = datetime.now(
            timezone.utc
        ) - timedelta(minutes=ESCALATION_COOLDOWN + 5)
        assert m.get_cooldown_remaining(CognitiveTier.STANDARD) == 0.0


class TestResetCooldown:
    def test_reset_clears_entry(self):
        m = EscalationManager()
        m.escalation_log[CognitiveTier.STANDARD.value] = datetime.now(timezone.utc)
        assert m._is_on_cooldown(CognitiveTier.STANDARD) is True
        m.reset_cooldown(CognitiveTier.STANDARD)
        assert m._is_on_cooldown(CognitiveTier.STANDARD) is False

    def test_reset_missing_tier_is_noop(self):
        m = EscalationManager()
        m.reset_cooldown(CognitiveTier.HEAVY)  # must not raise
        assert m._is_on_cooldown(CognitiveTier.HEAVY) is False


# ── _escalate_for_reason: tier selection ─────────────────────────────────────


class TestTargetTierSelection:
    @pytest.mark.parametrize(
        "start,target",
        [
            (CognitiveTier.MICRO, CognitiveTier.STANDARD),
            (CognitiveTier.STANDARD, CognitiveTier.VERSATILE),
            (CognitiveTier.VERSATILE, CognitiveTier.HEAVY),
            (CognitiveTier.HEAVY, CognitiveTier.COMPLEX),
        ],
    )
    def test_each_step_escalates_one_tier(self, start, target):
        m = EscalationManager()
        should, _, t = m.should_escalate(start, error="e")
        assert should is True
        assert t == target

    def test_escalation_sets_cooldown_and_count(self):
        m = EscalationManager()
        rid = "req-1"
        m.should_escalate(CognitiveTier.STANDARD, error="e", request_id=rid)
        assert m.get_escalation_count(rid) == 1
        assert m._is_on_cooldown(CognitiveTier.STANDARD)


# ── Escalation counting ──────────────────────────────────────────────────────


class TestEscalationCount:
    def test_unknown_request_returns_zero(self):
        assert EscalationManager().get_escalation_count("nope") == 0

    def test_count_accumulates_across_escalations(self):
        m = EscalationManager()
        rid = "req-acc"
        # Two escalations from different source tiers (each resets the source
        # cooldown so the second isn't blocked by the first).
        m.should_escalate(CognitiveTier.MICRO, error="e", request_id=rid)
        m.should_escalate(CognitiveTier.STANDARD, error="e", request_id=rid)
        assert m.get_escalation_count(rid) == 2


# ── DB logging (graceful failure) ────────────────────────────────────────────


class TestDatabaseLogging:
    def test_successful_db_log(self):
        db = MagicMock()
        m = EscalationManager(db_session=db, workspace_id="ws-1")
        m.should_escalate(
            CognitiveTier.STANDARD, error="e", request_id="req-db"
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
        rec = db.add.call_args[0][0]
        assert rec.from_tier == CognitiveTier.STANDARD.value
        assert rec.to_tier == CognitiveTier.VERSATILE.value
        assert rec.reason == EscalationReason.ERROR_RESPONSE.value
        assert rec.workspace_id == "ws-1"

    def test_db_failure_does_not_raise_and_rolls_back(self):
        db = MagicMock()
        db.commit.side_effect = RuntimeError("db down")
        m = EscalationManager(db_session=db)
        # The escalation decision still returns True; only logging failed.
        should, reason, target = m.should_escalate(
            CognitiveTier.STANDARD, error="e"
        )
        assert should is True
        assert reason == EscalationReason.ERROR_RESPONSE
        db.rollback.assert_called_once()

    def test_db_rollback_failure_swallowed(self):
        db = MagicMock()
        db.commit.side_effect = RuntimeError("commit")
        db.rollback.side_effect = RuntimeError("rollback")
        m = EscalationManager(db_session=db)
        # Neither commit nor rollback errors escape.
        m.should_escalate(CognitiveTier.STANDARD, error="e")

    def test_no_db_session_skips_logging(self):
        m = EscalationManager(db_session=None)
        should, _, _ = m.should_escalate(CognitiveTier.STANDARD, error="e")
        assert should is True  # decision unaffected


# ── Module-level config sanity ───────────────────────────────────────────────


class TestConfig:
    def test_tier_order_is_strictly_ascending(self):
        # Every adjacent pair must be one step apart in escalation power.
        assert TIER_ORDER[0] == CognitiveTier.MICRO
        assert TIER_ORDER[-1] == CognitiveTier.COMPLEX
        assert len(TIER_ORDER) == 5

    def test_quality_threshold_is_80(self):
        assert (
            ESCALATION_THRESHOLDS[EscalationReason.QUALITY_THRESHOLD][
                "min_quality_score"
            ]
            == 80
        )

    def test_confidence_threshold_is_07(self):
        assert (
            ESCALATION_THRESHOLDS[EscalationReason.LOW_CONFIDENCE]["confidence"]
            == 0.7
        )
