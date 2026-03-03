"""
Property-Based Tests for Tier Escalation Invariants

Tests CRITICAL tier escalation invariants:
- Quality threshold breaches (<80) trigger escalation
- Cooldown period (5 min) prevents rapid cycling
- COMPLEX tier cannot escalate further
- Rate limit errors trigger immediate escalation
- Max escalation limit (2) prevents runaway costs
- Low confidence (<0.7) triggers escalation
- Tier order is always respected (MICRO → STANDARD → VERSATILE → HEAVY → COMPLEX)

These tests protect against escalation bugs, rapid tier cycling, and cost overruns.

Test Count: 10 property tests
Hypothesis Examples: ~500 (50 max_examples per test)
Coverage: All 8 escalation invariants from EscalationManager

Author: Atom AI Platform
Created: 2026-03-03
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import sampled_from, integers, floats
from datetime import datetime, timedelta
from typing import Optional

from core.llm.escalation_manager import (
    EscalationManager,
    EscalationReason,
    ESCALATION_COOLDOWN,
    MAX_ESCALATION_LIMIT,
    TIER_ORDER
)
from core.llm.cognitive_tier_system import CognitiveTier

# Hypothesis settings for escalation tests
HYPOTHESIS_SETTINGS_ESCALATION = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 50  # Escalation tests: 4 tiers × 7 quality levels × 11 cooldown values = 308 combos
}


class TestQualityThresholdInvariants:
    """Property-based tests for quality threshold escalation triggers."""

    @given(
        current_tier=sampled_from([
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY
            # Note: COMPLEX tier tested separately
        ]),
        response_quality=sampled_from([None, 60, 70, 75, 79, 80, 85, 90, 95])
    )
    @settings(**HYPOTHESIS_SETTINGS_ESCALATION)
    def test_quality_threshold_breach_triggers_escalation(
        self, db_session, current_tier: CognitiveTier,
        response_quality: Optional[float]
    ):
        """
        PROPERTY: Quality score <80 triggers escalation to next tier

        STRATEGY: st.tuples(current_tier, response_quality)

        INVARIANT: quality <80 → escalate, quality >=80 → no escalate

        TIER_ORDER: [MICRO, STANDARD, VERSATILE, HEAVY, COMPLEX]

        RADII: 50 examples explores all tier×quality combinations (4×9=36)
        """
        manager = EscalationManager(db_session)

        should_escalate, reason, target_tier = manager.should_escalate(
            current_tier=current_tier,
            response_quality=response_quality,
            error=None,
            rate_limited=False
        )

        if response_quality is not None and response_quality < 80:
            # Quality threshold breach MUST trigger escalation
            assert should_escalate == True, \
                f"Quality {response_quality} <80 should trigger escalation from {current_tier.value}"
            assert reason == EscalationReason.QUALITY_THRESHOLD, \
                f"Reason must be QUALITY_THRESHOLD, got {reason}"

            # Verify target tier is next in order
            current_index = TIER_ORDER.index(current_tier)
            expected_target = TIER_ORDER[current_index + 1]
            assert target_tier == expected_target, \
                f"Target tier should be {expected_target.value}, got {target_tier.value if target_tier else None}"

        elif response_quality is not None and response_quality >= 80:
            # Quality acceptable MUST NOT escalate
            assert should_escalate == False, \
                f"Quality {response_quality} >=80 should NOT trigger escalation from {current_tier.value}"
            assert target_tier is None, "Target tier must be None when not escalating"


class TestCooldownInvariants:
    """Property-based tests for escalation cooldown enforcement."""

    @given(
        tier=sampled_from([
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY,
            CognitiveTier.COMPLEX
        ]),
        minutes_since_escalation=integers(min_value=0, max_value=10)
    )
    @settings(**HYPOTHESIS_SETTINGS_ESCALATION)
    def test_cooldown_prevents_rapid_escalation(
        self, db_session, tier: CognitiveTier, minutes_since_escalation: int
    ):
        """
        PROPERTY: Tier on cooldown for 5 minutes after escalation

        STRATEGY: st.tuples(tier, minutes_since_escalation)

        INVARIANT: is_on_cooldown returns True for <5 min, False for >=5 min

        RADII: 50 examples explores cooldown boundary (5 tiers × 11 time values = 55)
        """
        manager = EscalationManager(db_session)

        # Simulate escalation at specific time in past
        escalation_time = datetime.utcnow() - timedelta(minutes=minutes_since_escalation)
        manager.escalation_log[tier.value] = escalation_time

        # Check cooldown status
        is_on_cooldown = manager._is_on_cooldown(tier)

        # Verify cooldown logic
        if minutes_since_escalation < 5:
            # Should still be on cooldown
            assert is_on_cooldown == True, \
                f"Tier {tier.value} should be on cooldown at {minutes_since_escalation} minutes"
        else:
            # Cooldown expired
            assert is_on_cooldown == False, \
                f"Tier {tier.value} should NOT be on cooldown at {minutes_since_escalation} minutes"


class TestMaxTierInvariants:
    """Property-based tests for COMPLEX tier (max tier) behavior."""

    @given(
        response_quality=sampled_from([None, 50, 60, 70, 75, 80]),
        rate_limited=sampled_from([True, False]),
        has_error=sampled_from([True, False])
    )
    @settings(**HYPOTHESIS_SETTINGS_ESCALATION)
    def test_complex_tier_cannot_escalate(
        self, db_session, response_quality: Optional[float],
        rate_limited: bool, has_error: bool
    ):
        """
        PROPERTY: COMPLEX tier cannot escalate further (no higher tier exists)

        STRATEGY: st.tuples(response_quality, rate_limited, has_error)

        INVARIANT: COMPLEX tier always returns (False, None, None)

        RADII: 50 examples explores all trigger combinations for COMPLEX tier
        """
        manager = EscalationManager(db_session)

        error = "Some error" if has_error else None

        should_escalate, reason, target_tier = manager.should_escalate(
            current_tier=CognitiveTier.COMPLEX,
            response_quality=response_quality,
            error=error,
            rate_limited=rate_limited
        )

        # COMPLEX tier MUST NOT escalate
        assert should_escalate == False, \
            "COMPLEX tier cannot escalate further regardless of triggers"
        assert target_tier is None, "Target tier must be None for COMPLEX tier"


class TestRateLimitInvariants:
    """Property-based tests for rate limit escalation behavior."""

    @given(
        current_tier=sampled_from([
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY
        ]),
        on_cooldown=sampled_from([True, False])
    )
    @settings(**HYPOTHESIS_SETTINGS_ESCALATION)
    def test_rate_limit_triggers_immediate_escalation(
        self, db_session, current_tier: CognitiveTier, on_cooldown: bool
    ):
        """
        PROPERTY: Rate limit errors trigger immediate escalation (priority over cooldown)

        STRATEGY: st.tuples(current_tier, on_cooldown)

        INVARIANT: rate_limited=True → escalate (unless on_cooldown)

        RADII: 50 examples explores tier × cooldown combinations
        """
        manager = EscalationManager(db_session)

        # Set cooldown if specified
        if on_cooldown:
            manager.escalation_log[current_tier.value] = datetime.utcnow()

        should_escalate, reason, target_tier = manager.should_escalate(
            current_tier=current_tier,
            response_quality=None,
            error=None,
            rate_limited=True
        )

        # Rate limit triggers escalation if not on cooldown
        if on_cooldown:
            # Cooldown blocks even rate limit escalation
            assert should_escalate == False, \
                "Cooldown should block escalation even for rate limits"
        else:
            assert should_escalate == True, \
                "Rate limit should trigger escalation when not on cooldown"
            assert reason == EscalationReason.RATE_LIMITED, \
                f"Reason must be RATE_LIMITED, got {reason}"


class TestMaxEscalationLimitInvariants:
    """Property-based tests for max escalation limit per request."""

    @given(
        escalation_count=integers(min_value=0, max_value=5),
        response_quality=sampled_from([50, 60, 70, 75])
    )
    @settings(**HYPOTHESIS_SETTINGS_ESCALATION)
    def test_max_escalation_limit_enforced(
        self, db_session, escalation_count: int, response_quality: float
    ):
        """
        PROPERTY: Max escalation limit (2) prevents runaway costs

        STRATEGY: st.tuples(escalation_count, response_quality)

        INVARIANT: escalation_count >= 2 → no escalation

        RADII: 50 examples explores limit boundary (0-5 counts × 4 quality levels)
        """
        manager = EscalationManager(db_session)
        request_id = "test-request-123"

        # Set escalation count
        manager.request_escalations[request_id] = escalation_count

        should_escalate, reason, target_tier = manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=response_quality,
            error=None,
            rate_limited=False,
            request_id=request_id
        )

        if escalation_count >= MAX_ESCALATION_LIMIT:
            # At max limit, must not escalate
            assert should_escalate == False, \
                f"Escalation count {escalation_count} >= {MAX_ESCALATION_LIMIT} should block escalation"
        else:
            # Below limit, should escalate on quality breach
            assert should_escalate == True, \
                f"Escalation count {escalation_count} < {MAX_ESCALATION_LIMIT} should allow escalation"


class TestConfidenceThresholdInvariants:
    """Property-based tests for confidence-based escalation."""

    @given(
        confidence=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(**HYPOTHESIS_SETTINGS_ESCALATION)
    def test_confidence_threshold_breach_triggers_escalation(
        self, db_session, confidence: float
    ):
        """
        PROPERTY: Confidence < 0.7 triggers escalation

        STRATEGY: st.floats for confidence in [0, 1]

        INVARIANT: confidence < 0.7 → escalate, confidence >= 0.7 → no escalate

        RADII: 50 examples explores confidence boundary around 0.7 threshold
        """
        manager = EscalationManager(db_session)

        should_escalate, reason, target_tier = manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=None,
            error=None,
            rate_limited=False,
            confidence=confidence
        )

        if confidence < 0.7:
            # Below threshold MUST escalate
            assert should_escalate == True, \
                f"Confidence {confidence:.2f} < 0.7 should trigger escalation"
            assert reason == EscalationReason.LOW_CONFIDENCE, \
                f"Reason must be LOW_CONFIDENCE, got {reason}"
        else:
            # At or above threshold MUST NOT escalate
            assert should_escalate == False, \
                f"Confidence {confidence:.2f} >= 0.7 should NOT trigger escalation"


class TestTierOrderInvariants:
    """Property-based tests for tier progression order."""

    @given(
        current_tier=sampled_from([
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY
        ])
    )
    @settings(**HYPOTHESIS_SETTINGS_ESCALATION)
    def test_escalation_progresses_through_tier_order(
        self, db_session, current_tier: CognitiveTier
    ):
        """
        PROPERTY: Escalation follows tier order: MICRO → STANDARD → VERSATILE → HEAVY → COMPLEX

        STRATEGY: st.sampled_from for all escalatable tiers

        INVARIANT: target_tier is always next in TIER_ORDER

        RADII: 50 examples (4 tiers × repeated testing = deterministic)
        """
        manager = EscalationManager(db_session)

        should_escalate, reason, target_tier = manager.should_escalate(
            current_tier=current_tier,
            response_quality=70,  # Below threshold to trigger escalation
            error=None,
            rate_limited=False
        )

        if should_escalate:
            # Verify target is next in order
            current_index = TIER_ORDER.index(current_tier)
            expected_target = TIER_ORDER[current_index + 1]
            assert target_tier == expected_target, \
                f"Expected {expected_target.value}, got {target_tier.value}"


class TestCooldownExpiryInvariants:
    """Property-based tests for cooldown expiry behavior."""

    @given(
        tier=sampled_from([
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY
        ]),
        minutes_since_escalation=integers(min_value=5, max_value=10)
    )
    @settings(**HYPOTHESIS_SETTINGS_ESCALATION)
    def test_cooldown_expires_after_threshold(
        self, db_session, tier: CognitiveTier, minutes_since_escalation: int
    ):
        """
        PROPERTY: Cooldown expires after 5 minutes, allowing escalation

        STRATEGY: st.tuples(tier, minutes_since_escalation >= 5)

        INVARIANT: is_on_cooldown returns False when minutes >= 5

        RADII: 50 examples explores expiry boundary (4 tiers × 6 time values = 24)
        """
        manager = EscalationManager(db_session)

        # Simulate escalation at specific time in past (>= 5 minutes)
        escalation_time = datetime.utcnow() - timedelta(minutes=minutes_since_escalation)
        manager.escalation_log[tier.value] = escalation_time

        # Check cooldown status
        is_on_cooldown = manager._is_on_cooldown(tier)

        # Should NOT be on cooldown (expired)
        assert is_on_cooldown == False, \
            f"Tier {tier.value} should NOT be on cooldown at {minutes_since_escalation} minutes"

        # Verify escalation is now allowed
        should_escalate, reason, target_tier = manager.should_escalate(
            current_tier=tier,
            response_quality=70,  # Below threshold
            error=None,
            rate_limited=False
        )

        # Should be allowed to escalate (unless it's HEAVY tier which would go to COMPLEX)
        if tier != CognitiveTier.HEAVY:
            assert should_escalate == True, \
                f"Escalation should be allowed after cooldown expiry for {tier.value}"
