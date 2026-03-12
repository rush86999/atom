"""
Unit Tests for Escalation Manager Coverage

Comprehensive unit tests for EscalationManager class focusing on:
- Escalation decision logic (quality, rate limit, error, confidence)
- Cooldown period enforcement
- Escalation limit tracking
- Database persistence
- All escalation reasons

Target: 75%+ line coverage on escalation_manager.py
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from core.llm.escalation_manager import (
    EscalationManager,
    EscalationReason,
    ESCALATION_COOLDOWN,
    MAX_ESCALATION_LIMIT,
    TIER_ORDER,
    ESCALATION_THRESHOLDS
)
from core.llm.cognitive_tier_system import CognitiveTier


class TestEscalationDecision:
    """Test escalation decision logic for all trigger conditions."""

    @pytest.fixture
    def escalation_manager(self):
        """Create a fresh escalation manager for each test."""
        return EscalationManager(db_session=None)

    def test_should_escalate_false_at_complex_tier(self, escalation_manager):
        """Test that escalation returns False when already at COMPLEX tier."""
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.COMPLEX,
            response_quality=50,
            error="Some error",
            rate_limited=True
        )

        assert should is False, "Should not escalate when already at COMPLEX tier"
        assert reason is None, "Reason should be None when not escalating"
        assert target is None, "Target tier should be None when not escalating"

    def test_should_escalate_true_on_quality_threshold(self, escalation_manager):
        """Test that quality score < 80 triggers escalation."""
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,  # Below threshold of 80
            error=None,
            rate_limited=False
        )

        assert should is True, "Should escalate on low quality score"
        assert reason == EscalationReason.QUALITY_THRESHOLD, \
            f"Reason should be QUALITY_THRESHOLD, got {reason}"
        assert target == CognitiveTier.VERSATILE, \
            f"Target should be next tier (VERSATILE), got {target}"

    def test_should_escalate_true_on_rate_limit(self, escalation_manager):
        """Test that rate limit errors trigger immediate escalation."""
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.MICRO,
            response_quality=90,
            error=None,
            rate_limited=True
        )

        assert should is True, "Should escalate on rate limit error"
        assert reason == EscalationReason.RATE_LIMITED, \
            f"Reason should be RATE_LIMITED, got {reason}"
        assert target == CognitiveTier.STANDARD, \
            f"Target should be next tier (STANDARD), got {target}"

    def test_should_escalate_true_on_error_response(self, escalation_manager):
        """Test that error messages trigger escalation."""
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=None,
            error="Model returned invalid response",
            rate_limited=False
        )

        assert should is True, "Should escalate on error response"
        assert reason == EscalationReason.ERROR_RESPONSE, \
            f"Reason should be ERROR_RESPONSE, got {reason}"
        assert target == CognitiveTier.VERSATILE, \
            f"Target should be next tier, got {target}"

    def test_should_escalate_true_on_low_confidence(self, escalation_manager):
        """Test that confidence < 0.7 triggers escalation."""
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.VERSATILE,
            response_quality=None,
            error=None,
            rate_limited=False,
            confidence=0.5  # Below threshold of 0.7
        )

        assert should is True, "Should escalate on low confidence"
        assert reason == EscalationReason.LOW_CONFIDENCE, \
            f"Reason should be LOW_CONFIDENCE, got {reason}"
        assert target == CognitiveTier.HEAVY, \
            f"Target should be next tier, got {target}"

    def test_should_escalate_false_when_conditions_not_met(self, escalation_manager):
        """Test that good quality with no errors doesn't trigger escalation."""
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=85,  # Above threshold of 80
            error=None,
            rate_limited=False,
            confidence=0.8  # Above threshold of 0.7
        )

        assert should is False, "Should not escalate when conditions are good"
        assert reason is None, "Reason should be None when not escalating"
        assert target is None, "Target should be None when not escalating"

    def test_should_escalate_returns_next_tier(self, escalation_manager):
        """Test that escalation target is the next tier in order."""
        # Test from each tier (except COMPLEX)
        test_cases = [
            (CognitiveTier.MICRO, CognitiveTier.STANDARD),
            (CognitiveTier.STANDARD, CognitiveTier.VERSATILE),
            (CognitiveTier.VERSATILE, CognitiveTier.HEAVY),
            (CognitiveTier.HEAVY, CognitiveTier.COMPLEX),
        ]

        for current_tier, expected_target in test_cases:
            should, reason, target = escalation_manager.should_escalate(
                current_tier=current_tier,
                response_quality=70  # Trigger quality-based escalation
            )

            assert should is True, \
                f"Should escalate from {current_tier.value}"
            assert target == expected_target, \
                f"Expected target {expected_target.value} from {current_tier.value}, got {target.value if target else None}"

    def test_should_escalate_priority_order(self, escalation_manager):
        """Test escalation priority: rate limit > error > quality > confidence."""
        # When both rate_limited and low quality, rate limit takes priority
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=50,
            error="Some error",
            rate_limited=True  # Highest priority
        )

        assert should is True
        assert reason == EscalationReason.RATE_LIMITED, \
            "Rate limit should take priority over other reasons"

    def test_should_escalate_with_exact_thresholds(self, escalation_manager):
        """Test behavior at exact threshold boundaries."""
        # Quality exactly at threshold (80) should NOT escalate
        should, _, _ = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=80.0
        )
        assert should is False, "Quality at threshold should not escalate"

        # Quality just below threshold should escalate
        should, _, _ = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=79.9
        )
        assert should is True, "Quality just below threshold should escalate"

        # Confidence exactly at threshold (0.7) should NOT escalate
        should, _, _ = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            confidence=0.7
        )
        assert should is False, "Confidence at threshold should not escalate"

        # Confidence just below threshold should escalate
        should, _, _ = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            confidence=0.69
        )
        assert should is True, "Confidence just below threshold should escalate"

    def test_should_escalate_with_none_optional_params(self, escalation_manager):
        """Test that None values for optional parameters are handled correctly."""
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=None,
            error=None,
            rate_limited=False,
            confidence=None,
            request_id=None
        )

        # All None means no escalation triggers
        assert should is False, "Should not escalate when all params are None"
        assert reason is None
        assert target is None


class TestCooldownLogic:
    """Test cooldown period enforcement and tracking."""

    @pytest.fixture
    def escalation_manager(self):
        """Create a fresh escalation manager for each test."""
        return EscalationManager(db_session=None)

    def test_cooldown_prevents_immediate_escalation(self, escalation_manager):
        """Test that escalation within cooldown period is blocked."""
        # Perform first escalation
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70
        )

        # Try to escalate again immediately (should be blocked by cooldown)
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70
        )

        assert should is False, "Should not escalate while on cooldown"
        assert reason is None, "Reason should be None when blocked by cooldown"
        assert target is None, "Target should be None when blocked by cooldown"

    def test_cooldown_allows_escalation_after_timeout(self, escalation_manager):
        """Test that escalation is allowed after cooldown expires."""
        # Perform first escalation
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70
        )

        # Manually clear cooldown to simulate time passing
        escalation_manager.reset_cooldown(CognitiveTier.STANDARD)

        # Try to escalate again (should succeed)
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70
        )

        assert should is True, "Should escalate after cooldown expires"
        assert reason == EscalationReason.QUALITY_THRESHOLD
        assert target == CognitiveTier.VERSATILE

    def test_reset_cooldown_clears_cooldown(self, escalation_manager):
        """Test that reset_cooldown removes cooldown status."""
        # Set cooldown by escalating
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70
        )

        # Verify cooldown is active
        assert escalation_manager._is_on_cooldown(CognitiveTier.STANDARD), \
            "Should be on cooldown after escalation"

        # Reset cooldown
        escalation_manager.reset_cooldown(CognitiveTier.STANDARD)

        # Verify cooldown is cleared
        assert not escalation_manager._is_on_cooldown(CognitiveTier.STANDARD), \
            "Should not be on cooldown after reset"

    def test_get_cooldown_remaining_returns_seconds(self, escalation_manager):
        """Test that get_cooldown_remaining returns correct remaining time."""
        # Set cooldown
        escalation_manager.escalation_log[CognitiveTier.STANDARD.value] = datetime.utcnow()

        # Get remaining time immediately (should be ~5 minutes)
        remaining = escalation_manager.get_cooldown_remaining(CognitiveTier.STANDARD)

        assert remaining > 0, "Should have positive remaining time"
        assert remaining <= ESCALATION_COOLDOWN * 60, \
            f"Remaining time should not exceed {ESCALATION_COOLDOWN} minutes"

    def test_get_cooldown_zero_when_not_on_cooldown(self, escalation_manager):
        """Test that get_cooldown_remaining returns 0 when not on cooldown."""
        # No escalation has occurred
        remaining = escalation_manager.get_cooldown_remaining(CognitiveTier.STANDARD)

        assert remaining == 0.0, \
            "Cooldown remaining should be 0 when no escalation has occurred"

    def test_cooldown_independent_per_tier(self, escalation_manager):
        """Test that cooldown is tracked independently per tier."""
        # Escalate from STANDARD
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70
        )

        # Verify STANDARD is on cooldown
        assert escalation_manager._is_on_cooldown(CognitiveTier.STANDARD)

        # Verify VERSATILE is NOT on cooldown
        assert not escalation_manager._is_on_cooldown(CognitiveTier.VERSATILE)

        # Should be able to escalate from VERSATILE
        should, _, _ = escalation_manager.should_escalate(
            current_tier=CognitiveTier.VERSATILE,
            response_quality=70
        )
        assert should, "Should be able to escalate from different tier"

    def test_cooldown_expiry_after_5_minutes(self, escalation_manager):
        """Test that cooldown expires after exactly 5 minutes."""
        # Set cooldown timestamp to 5 minutes ago
        past_time = datetime.utcnow() - timedelta(minutes=ESCALATION_COOLDOWN)
        escalation_manager.escalation_log[CognitiveTier.STANDARD.value] = past_time

        # Cooldown should have expired
        assert not escalation_manager._is_on_cooldown(CognitiveTier.STANDARD), \
            "Cooldown should expire after 5 minutes"

    def test_cooldown_still_active_4_minutes_59_seconds(self, escalation_manager):
        """Test that cooldown is still active just before expiry."""
        # Set cooldown timestamp to 4 minutes 59 seconds ago
        past_time = datetime.utcnow() - timedelta(minutes=4, seconds=59)
        escalation_manager.escalation_log[CognitiveTier.STANDARD.value] = past_time

        # Cooldown should still be active
        assert escalation_manager._is_on_cooldown(CognitiveTier.STANDARD), \
            "Cooldown should still be active at 4:59"

        # Remaining time should be > 0
        remaining = escalation_manager.get_cooldown_remaining(CognitiveTier.STANDARD)
        assert remaining > 0, "Should have positive remaining time"


class TestEscalationLimits:
    """Test escalation count limits and request tracking."""

    @pytest.fixture
    def escalation_manager(self):
        """Create a fresh escalation manager for each test."""
        return EscalationManager(db_session=None)

    def test_max_escalation_limit_enforced(self, escalation_manager):
        """Test that max escalation limit (2) prevents further escalation."""
        request_id = "test-request-123"

        # First escalation (should succeed)
        should1, _, target1 = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            request_id=request_id
        )
        assert should1 is True, "First escalation should succeed"

        # Reset cooldown to allow second escalation
        escalation_manager.reset_cooldown(CognitiveTier.STANDARD)

        # Second escalation (should succeed)
        should2, _, target2 = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            request_id=request_id
        )
        assert should2 is True, "Second escalation should succeed"

        # Reset cooldown again
        escalation_manager.reset_cooldown(CognitiveTier.STANDARD)

        # Third escalation (should be blocked by limit)
        should3, _, target3 = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            request_id=request_id
        )
        assert should3 is False, "Third escalation should be blocked by limit"

    def test_escalation_count_increases_with_each_escalation(self, escalation_manager):
        """Test that escalation count is tracked correctly."""
        request_id = "test-request-count"

        # Initial count should be 0
        count = escalation_manager.get_escalation_count(request_id)
        assert count == 0, "Initial escalation count should be 0"

        # After first escalation
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            request_id=request_id
        )
        count = escalation_manager.get_escalation_count(request_id)
        assert count == 1, "Escalation count should be 1 after first escalation"

        # Reset cooldown and escalate again
        escalation_manager.reset_cooldown(CognitiveTier.STANDARD)
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            request_id=request_id
        )
        count = escalation_manager.get_escalation_count(request_id)
        assert count == 2, "Escalation count should be 2 after second escalation"

    def test_different_requests_independent_escalation_counts(self, escalation_manager):
        """Test that escalation counts are independent per request ID."""
        request1 = "request-1"
        request2 = "request-2"

        # Escalate request 1
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            request_id=request1
        )

        # Check counts
        count1 = escalation_manager.get_escalation_count(request1)
        count2 = escalation_manager.get_escalation_count(request2)

        assert count1 == 1, "Request 1 should have count of 1"
        assert count2 == 0, "Request 2 should have count of 0"

    def test_escalation_limit_with_no_request_id(self, escalation_manager):
        """Test that escalation limit is not enforced without request_id."""
        # Escalate without request_id multiple times (resetting cooldown each time)
        for i in range(5):
            escalation_manager.reset_cooldown(CognitiveTier.STANDARD)
            should, _, _ = escalation_manager.should_escalate(
                current_tier=CognitiveTier.STANDARD,
                response_quality=70
            )
            # Without request_id, limit is not enforced
            assert should is True, \
                f"Escalation {i+1} should succeed without request_id limit"

    def test_get_escalation_count_returns_zero_for_new_request(self, escalation_manager):
        """Test that new request IDs start with count 0."""
        new_request_id = "brand-new-request"
        count = escalation_manager.get_escalation_count(new_request_id)

        assert count == 0, "New request should have escalation count of 0"


class TestEscalationLogging:
    """Test escalation logging and database persistence."""

    @pytest.fixture
    def escalation_manager(self):
        """Create escalation manager with mocked database."""
        mock_db = Mock(spec=Session)
        return EscalationManager(db_session=mock_db)

    @pytest.fixture
    def escalation_manager_no_db(self):
        """Create escalation manager without database."""
        return EscalationManager(db_session=None)

    def test_record_escalation_increases_count(self, escalation_manager_no_db):
        """Test that escalation recording increases request count."""
        request_id = "test-request-record"

        # Record escalation manually
        escalation_manager_no_db._record_escalation(
            from_tier=CognitiveTier.STANDARD,
            to_tier=CognitiveTier.VERSATILE,
            reason=EscalationReason.QUALITY_THRESHOLD,
            request_id=request_id
        )

        count = escalation_manager_no_db.get_escalation_count(request_id)
        assert count == 1, "Escalation count should be 1 after recording"

    def test_escalation_log_timestamp_recorded(self, escalation_manager_no_db):
        """Test that escalation timestamp is recorded for cooldown."""
        # Perform escalation
        escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70
        )

        # Check that timestamp was recorded
        assert CognitiveTier.STANDARD.value in escalation_manager_no_db.escalation_log, \
            "Escalation log should contain timestamp for tier"

        timestamp = escalation_manager_no_db.escalation_log[CognitiveTier.STANDARD.value]
        assert isinstance(timestamp, datetime), \
            "Escalation log timestamp should be datetime object"

    def test_escalation_logged_to_database_when_db_available(self, escalation_manager):
        """Test that escalation is persisted to database when session is available."""
        # Perform escalation
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            request_id="test-request-db"
        )

        # Verify DB add was called
        escalation_manager.db.add.assert_called_once()

        # Verify DB commit was called
        escalation_manager.db.commit.assert_called_once()

    def test_database_logging_failure_does_not_fail_escalation(self, escalation_manager):
        """Test that DB logging failures are handled gracefully."""
        # Make DB operations raise exception
        escalation_manager.db.add.side_effect = Exception("DB connection failed")
        escalation_manager.db.rollback = Mock()

        # Escalation should still succeed
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70
        )

        assert should is True, "Escalation should succeed despite DB failure"
        assert reason == EscalationReason.QUALITY_THRESHOLD
        assert target == CognitiveTier.VERSATILE

        # Rollback should have been attempted
        escalation_manager.db.rollback.assert_called_once()

    def test_escalation_with_all_reasons(self, escalation_manager_no_db):
        """Test escalation with all different reason types."""
        reasons_to_test = [
            (EscalationReason.QUALITY_THRESHOLD, {"response_quality": 70}),
            (EscalationReason.RATE_LIMITED, {"rate_limited": True}),
            (EscalationReason.ERROR_RESPONSE, {"error": "Model error"}),
            (EscalationReason.LOW_CONFIDENCE, {"confidence": 0.5}),
        ]

        for expected_reason, params in reasons_to_test:
            # Reset cooldown between tests
            escalation_manager_no_db.reset_cooldown(CognitiveTier.STANDARD)

            should, reason, target = escalation_manager_no_db.should_escalate(
                current_tier=CognitiveTier.STANDARD,
                **params
            )

            assert should is True, \
                f"Should escalate for reason {expected_reason.value}"
            assert reason == expected_reason, \
                f"Expected reason {expected_reason.value}, got {reason.value if reason else None}"

    def test_escalate_for_reason_calculates_correct_target_tier(self, escalation_manager_no_db):
        """Test that _escalate_for_reason calculates next tier correctly."""
        # Test each tier transition
        transitions = [
            (CognitiveTier.MICRO, CognitiveTier.STANDARD),
            (CognitiveTier.STANDARD, CognitiveTier.VERSATILE),
            (CognitiveTier.VERSATILE, CognitiveTier.HEAVY),
            (CognitiveTier.HEAVY, CognitiveTier.COMPLEX),
        ]

        for current_tier, expected_target in transitions:
            should, reason, target = escalation_manager_no_db._escalate_for_reason(
                current_tier=current_tier,
                reason=EscalationReason.QUALITY_THRESHOLD
            )

            assert should is True, \
                f"_escalate_for_reason should return True for {current_tier.value}"
            assert target == expected_target, \
                f"Expected target {expected_target.value} from {current_tier.value}, got {target.value if target else None}"

    def test_escalate_for_reason_returns_false_at_max_tier(self, escalation_manager_no_db):
        """Test that _escalate_for_reason returns False at COMPLEX tier."""
        should, reason, target = escalation_manager_no_db._escalate_for_reason(
            current_tier=CognitiveTier.COMPLEX,
            reason=EscalationReason.QUALITY_THRESHOLD
        )

        assert should is False, "Cannot escalate beyond COMPLEX tier"
        assert reason == EscalationReason.QUALITY_THRESHOLD, \
            "Reason should still be returned even when can't escalate"
        assert target is None, "Target should be None when at max tier"

    def test_escalate_for_reason_sets_cooldown_timestamp(self, escalation_manager_no_db):
        """Test that _escalate_for_reason sets cooldown timestamp."""
        escalation_manager_no_db._escalate_for_reason(
            current_tier=CognitiveTier.STANDARD,
            reason=EscalationReason.QUALITY_THRESHOLD
        )

        # Verify cooldown was set
        assert escalation_manager_no_db._is_on_cooldown(CognitiveTier.STANDARD), \
            "Cooldown should be set after escalation"

    def test_record_escalation_with_all_parameters(self, escalation_manager):
        """Test _record_escalation with all optional parameters."""
        escalation_manager._record_escalation(
            from_tier=CognitiveTier.STANDARD,
            to_tier=CognitiveTier.VERSATILE,
            reason=EscalationReason.ERROR_RESPONSE,
            trigger_value=0.5,
            request_id="test-request-all-params",
            provider_id="openai",
            model="gpt-4o",
            error_message="Rate limit exceeded"
        )

        # Verify DB add was called
        escalation_manager.db.add.assert_called_once()

        # Get the EscalationLog object that was added
        call_args = escalation_manager.db.add.call_args
        escalation_record = call_args[0][0]

        # Verify all fields were set
        assert escalation_record.from_tier == "standard"
        assert escalation_record.to_tier == "versatile"
        assert escalation_record.reason == "error_response"
        assert escalation_record.trigger_value == 0.5
        assert escalation_record.request_id == "test-request-all-params"
        assert escalation_record.provider_id == "openai"
        assert escalation_record.model == "gpt-4o"
        assert escalation_record.error_message == "Rate limit exceeded"

    def test_record_escalation_without_db_session(self, escalation_manager_no_db):
        """Test that _record_escalation works without database session."""
        # Should not raise exception
        escalation_manager_no_db._record_escalation(
            from_tier=CognitiveTier.STANDARD,
            to_tier=CognitiveTier.VERSATILE,
            reason=EscalationReason.QUALITY_THRESHOLD,
            request_id="test-no-db"
        )

        # In-memory tracking should still work
        count = escalation_manager_no_db.get_escalation_count("test-no-db")
        assert count == 1, "Request escalation count should be tracked even without DB"


class TestEscalationManagerInitialization:
    """Test EscalationManager initialization and setup."""

    def test_initialization_without_db(self):
        """Test initialization without database session."""
        manager = EscalationManager(db_session=None)

        assert manager.db is None, "DB session should be None"
        assert manager.escalation_log == {}, "Escalation log should be empty dict"
        assert manager.request_escalations == {}, "Request escalations should be empty dict"

    def test_initialization_with_db(self):
        """Test initialization with database session."""
        mock_db = Mock(spec=Session)
        manager = EscalationManager(db_session=mock_db)

        assert manager.db == mock_db, "DB session should be set"
        assert isinstance(manager.escalation_log, dict), "Escalation log should be dict"
        assert isinstance(manager.request_escalations, dict), "Request escalations should be dict"

    def test_initialization_creates_independent_managers(self):
        """Test that multiple manager instances are independent."""
        manager1 = EscalationManager()
        manager2 = EscalationManager()

        # Modify manager1
        manager1.escalation_log["standard"] = datetime.utcnow()

        # Verify manager2 is unaffected
        assert "standard" not in manager2.escalation_log, \
            "Manager instances should be independent"


class TestTierOrderAndConstants:
    """Test tier order and escalation constants."""

    def test_tier_order_is_complete(self):
        """Test that TIER_ORDER contains all 5 tiers in correct order."""
        expected_order = [
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY,
            CognitiveTier.COMPLEX
        ]

        assert TIER_ORDER == expected_order, \
            f"TIER_ORDER should be {expected_order}, got {TIER_ORDER}"

    def test_max_escalation_limit_value(self):
        """Test that MAX_ESCALATION_LIMIT is set correctly."""
        assert MAX_ESCALATION_LIMIT == 2, \
            f"MAX_ESCALATION_LIMIT should be 2, got {MAX_ESCALATION_LIMIT}"

    def test_escalation_cooldown_value(self):
        """Test that ESCALATION_COOLDOWN is set correctly."""
        assert ESCALATION_COOLDOWN == 5, \
            f"ESCALATION_COOLDOWN should be 5 minutes, got {ESCALATION_COOLDOWN}"

    def test_escalation_thresholds_structure(self):
        """Test that ESCALATION_THRESHOLDS has all required keys."""
        required_reasons = [
            EscalationReason.LOW_CONFIDENCE,
            EscalationReason.QUALITY_THRESHOLD,
            EscalationReason.RATE_LIMITED,
            EscalationReason.ERROR_RESPONSE,
            EscalationReason.USER_REQUEST
        ]

        for reason in required_reasons:
            assert reason in ESCALATION_THRESHOLDS, \
                f"ESCALATION_THRESHOLDS missing {reason.value}"

            threshold = ESCALATION_THRESHOLDS[reason]
            assert "max_retries" in threshold, \
                f"{reason.value} missing max_retries in thresholds"
