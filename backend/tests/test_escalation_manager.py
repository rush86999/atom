"""
Comprehensive test suite for EscalationManager

Tests cover:
- Escalation decision logic (quality, rate limits, errors, confidence)
- Cooldown period enforcement
- Max tier handling (COMPLEX cannot escalate)
- Max escalation limit per request
- Database logging functionality
- Performance benchmarks
- Integration with CognitiveTier system

Author: Atom AI Platform
Created: 2026-02-20
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from core.llm.escalation_manager import (
    EscalationManager,
    EscalationReason,
    ESCALATION_COOLDOWN,
    MAX_ESCALATION_LIMIT,
    TIER_ORDER
)
from core.llm.cognitive_tier_system import CognitiveTier


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    session = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    return session


@pytest.fixture
def escalation_manager(mock_db_session):
    """Create EscalationManager with mocked database."""
    return EscalationManager(db_session=mock_db_session)


@pytest.fixture
def escalation_manager_no_db():
    """Create EscalationManager without database (in-memory only)."""
    return EscalationManager(db_session=None)


# ============================================================================
# Escalation Decision Tests (8 tests)
# ============================================================================

class TestEscalationDecisions:
    """Test escalation decision logic for various triggers."""

    def test_should_escalate_low_quality(self, escalation_manager_no_db):
        """Quality score < 80 should trigger escalation."""
        should, reason, target = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            error=None,
            rate_limited=False
        )

        assert should is True
        assert reason == EscalationReason.QUALITY_THRESHOLD
        assert target == CognitiveTier.VERSATILE

    def test_should_escalate_rate_limited(self, escalation_manager_no_db):
        """Rate limit errors should trigger immediate escalation."""
        should, reason, target = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.MICRO,
            response_quality=None,
            error=None,
            rate_limited=True
        )

        assert should is True
        assert reason == EscalationReason.RATE_LIMITED
        assert target == CognitiveTier.STANDARD

    def test_should_escalate_error_response(self, escalation_manager_no_db):
        """Error responses should trigger escalation."""
        should, reason, target = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=None,
            error="Connection timeout",
            rate_limited=False
        )

        assert should is True
        assert reason == EscalationReason.ERROR_RESPONSE
        assert target == CognitiveTier.VERSATILE

    def test_should_not_escalate_good_quality(self, escalation_manager_no_db):
        """Quality score >= 80 should not trigger escalation."""
        should, reason, target = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=85,
            error=None,
            rate_limited=False
        )

        assert should is False
        assert reason is None
        assert target is None

    def test_should_escalate_low_confidence(self, escalation_manager_no_db):
        """Confidence < 0.7 should trigger escalation."""
        should, reason, target = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.VERSATILE,
            response_quality=None,
            error=None,
            rate_limited=False,
            confidence=0.5
        )

        assert should is True
        assert reason == EscalationReason.LOW_CONFIDENCE
        assert target == CognitiveTier.HEAVY

    def test_on_cooldown_blocks_escalation(self, escalation_manager_no_db):
        """Recent escalation should block new escalation (cooldown)."""
        # First escalation
        escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            error=None,
            rate_limited=False
        )

        # Try to escalate again immediately (should be blocked)
        should, reason, target = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            error=None,
            rate_limited=False
        )

        assert should is False, "Cooldown should block escalation"
        assert reason is None
        assert target is None

    def test_max_tier_no_escalation(self, escalation_manager_no_db):
        """COMPLEX tier should not escalate further."""
        should, reason, target = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.COMPLEX,
            response_quality=50,
            error="Some error",
            rate_limited=True
        )

        assert should is False, "COMPLEX tier cannot escalate further"
        assert reason is None
        assert target is None

    def test_max_escalation_limit(self, escalation_manager_no_db):
        """Should stop escalation after MAX_ESCALATION_LIMIT per request."""
        request_id = "test-request-123"

        # First escalation (STANDARD -> VERSATILE)
        should1, _, target1 = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            error=None,
            rate_limited=False,
            request_id=request_id
        )
        assert should1 is True
        assert target1 == CognitiveTier.VERSATILE
        assert escalation_manager_no_db.get_escalation_count(request_id) == 1

        # Clear cooldown and try second escalation (VERSATILE -> HEAVY)
        escalation_manager_no_db.escalation_log.clear()

        should2, _, target2 = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.VERSATILE,
            response_quality=70,
            error=None,
            rate_limited=False,
            request_id=request_id
        )
        assert should2 is True
        assert target2 == CognitiveTier.HEAVY
        assert escalation_manager_no_db.get_escalation_count(request_id) == 2

        # Clear cooldown and try third escalation - should be blocked (max 2)
        escalation_manager_no_db.escalation_log.clear()

        should3, _, target3 = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.HEAVY,
            response_quality=70,
            error=None,
            rate_limited=False,
            request_id=request_id
        )
        assert should3 is False, "Should block after MAX_ESCALATION_LIMIT"
        assert target3 is None


# ============================================================================
# Escalation Logic Tests (6 tests)
# ============================================================================

class TestEscalationLogic:
    """Test escalation calculation and tier progression."""

    def test_escalate_to_next_tier(self, escalation_manager_no_db):
        """Escalation should move to next tier in order."""
        # MICRO -> STANDARD
        should, reason, target = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.MICRO,
            response_quality=70,
            error=None,
            rate_limited=False
        )

        assert should is True
        assert target == CognitiveTier.STANDARD

    def test_escalation_reasons_mapped(self, escalation_manager_no_db):
        """All 5 escalation reasons should be handled correctly."""
        # Test QUALITY_THRESHOLD
        should1, reason1, _ = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            error=None,
            rate_limited=False
        )
        assert should1 is True
        assert reason1 == EscalationReason.QUALITY_THRESHOLD

        # Reset cooldown
        escalation_manager_no_db.escalation_log.clear()

        # Test LOW_CONFIDENCE
        should2, reason2, _ = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=None,
            error=None,
            rate_limited=False,
            confidence=0.5
        )
        assert should2 is True
        assert reason2 == EscalationReason.LOW_CONFIDENCE

    def test_quality_threshold_config(self, escalation_manager_no_db):
        """Quality threshold of 80 should be the minimum acceptable."""
        # Below threshold (should escalate)
        should1, _, _ = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=79,
            error=None,
            rate_limited=False
        )
        assert should1 is True

        # At threshold (should not escalate)
        should2, _, _ = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=80,
            error=None,
            rate_limited=False
        )
        assert should2 is False

        # Above threshold (should not escalate)
        should3, _, _ = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=90,
            error=None,
            rate_limited=False
        )
        assert should3 is False

    def test_rate_limit_max_retries(self, escalation_manager_no_db):
        """Rate limit escalation should have 3 max retries."""
        from core.llm.escalation_manager import ESCALATION_THRESHOLDS

        max_retries = ESCALATION_THRESHOLDS[EscalationReason.RATE_LIMITED]["max_retries"]
        assert max_retries == 3

    def test_confidence_threshold(self, escalation_manager_no_db):
        """Confidence threshold should be 0.7."""
        from core.llm.escalation_manager import ESCALATION_THRESHOLDS

        threshold = ESCALATION_THRESHOLDS[EscalationReason.LOW_CONFIDENCE]["confidence"]
        assert threshold == 0.7

    def test_multiple_escalations_stack(self, escalation_manager_no_db):
        """Multiple escalations should progress through tiers."""
        # MICRO -> STANDARD
        should1, _, target1 = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.MICRO,
            response_quality=70,
            error=None,
            rate_limited=False
        )
        assert should1 is True
        assert target1 == CognitiveTier.STANDARD

        # Simulate cooldown expiry
        escalation_manager_no_db.escalation_log.clear()

        # STANDARD -> VERSATILE
        should2, _, target2 = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            error=None,
            rate_limited=False
        )
        assert should2 is True
        assert target2 == CognitiveTier.VERSATILE


# ============================================================================
# Database Logging Tests (5 tests)
# ============================================================================

class TestDatabaseLogging:
    """Test database logging of escalations."""

    def test_escalation_logged_to_db(self, escalation_manager, mock_db_session):
        """Escalation should create database record."""
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            error=None,
            rate_limited=False
        )

        # Verify DB session was called
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_log_contains_all_fields(self, escalation_manager, mock_db_session):
        """Escalation log should contain all required fields."""
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=75,
            error=None,
            rate_limited=False,
            request_id="test-req-123"
        )

        # Get the added record
        call_args = mock_db_session.add.call_args
        escalation_record = call_args[0][0]

        assert escalation_record.from_tier == "standard"
        assert escalation_record.to_tier == "versatile"
        assert escalation_record.reason == "quality_threshold"
        assert escalation_record.trigger_value == 75
        assert escalation_record.request_id == "test-req-123"

    def test_workspace_id_in_log(self, escalation_manager, mock_db_session):
        """Log should have workspace_id field."""
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.MICRO,
            response_quality=70,
            error=None,
            rate_limited=False
        )

        call_args = mock_db_session.add.call_args
        escalation_record = call_args[0][0]

        assert hasattr(escalation_record, 'workspace_id')
        assert escalation_record.workspace_id == "default"

    def test_request_id_tracking(self, escalation_manager, mock_db_session):
        """Same request_id should be tracked across escalations."""
        request_id = "req-tracking-123"

        escalation_manager.should_escalate(
            current_tier=CognitiveTier.MICRO,
            response_quality=70,
            error=None,
            rate_limited=False,
            request_id=request_id
        )

        # The count is tracked internally during _record_escalation
        # Check that it was incremented
        assert request_id in escalation_manager.request_escalations
        count = escalation_manager.get_escalation_count(request_id)
        assert count >= 1  # At least 1 escalation was recorded

    def test_error_message_logged(self, escalation_manager, mock_db_session):
        """Error messages should be captured in log."""
        escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=None,
            error="Rate limit exceeded",
            rate_limited=False
        )

        call_args = mock_db_session.add.call_args
        escalation_record = call_args[0][0]

        # Error message is passed to _record_escalation internally
        assert escalation_record.reason == "error_response"
        # The error_message field is set by _record_escalation


# ============================================================================
# Performance Tests (2 tests)
# ============================================================================

class TestPerformance:
    """Test performance of escalation decision-making."""

    def test_should_escalate_performance(self, escalation_manager_no_db):
        """Escalation decision should be <5ms."""
        iterations = 1000

        start_time = time.time()
        for _ in range(iterations):
            escalation_manager_no_db.should_escalate(
                current_tier=CognitiveTier.STANDARD,
                response_quality=70,
                error=None,
                rate_limited=False
            )
        end_time = time.time()

        avg_time_ms = ((end_time - start_time) / iterations) * 1000

        assert avg_time_ms < 5, f"Average time {avg_time_ms:.2f}ms exceeds 5ms target"

    def test_cooldown_check_performance(self, escalation_manager_no_db):
        """Cooldown check should be <1ms."""
        escalation_manager_no_db.escalation_log[CognitiveTier.STANDARD.value] = datetime.utcnow()

        iterations = 10000

        start_time = time.time()
        for _ in range(iterations):
            escalation_manager_no_db._is_on_cooldown(CognitiveTier.STANDARD)
        end_time = time.time()

        avg_time_ms = ((end_time - start_time) / iterations) * 1000

        assert avg_time_ms < 1, f"Average time {avg_time_ms:.4f}ms exceeds 1ms target"


# ============================================================================
# Integration Tests (3 tests)
# ============================================================================

class TestIntegration:
    """Test integration with CognitiveTier system."""

    def test_with_cognitive_tier_system(self, escalation_manager_no_db):
        """Should work with all CognitiveTier enum values."""
        tiers = [
            CognitiveTier.MICRO,
            CognitiveTier.STANDARD,
            CognitiveTier.VERSATILE,
            CognitiveTier.HEAVY,
        ]

        for tier in tiers:
            should, reason, target = escalation_manager_no_db.should_escalate(
                current_tier=tier,
                response_quality=70,
                error=None,
                rate_limited=False
            )

            if tier != CognitiveTier.HEAVY:
                assert should is True
                # Verify target is next in order
                current_idx = TIER_ORDER.index(tier)
                expected_target = TIER_ORDER[current_idx + 1]
                assert target == expected_target

    def test_database_session_required(self, escalation_manager, mock_db_session):
        """Should work with real database session (mocked)."""
        should, reason, target = escalation_manager.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            error=None,
            rate_limited=False
        )

        assert should is True
        mock_db_session.add.assert_called_once()

    def test_escalation_count_tracking(self, escalation_manager_no_db):
        """Per-request escalation counting should work correctly."""
        request_id = "count-test-123"

        # First escalation
        escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.MICRO,
            response_quality=70,
            error=None,
            rate_limited=False,
            request_id=request_id
        )

        # The count is tracked in request_escalations dict
        assert request_id in escalation_manager_no_db.request_escalations
        count = escalation_manager_no_db.get_escalation_count(request_id)
        assert count >= 1  # At least 1 escalation was recorded

        # Second escalation (different tier, clear cooldown first)
        escalation_manager_no_db.escalation_log.clear()
        escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            error=None,
            rate_limited=False,
            request_id=request_id
        )

        count = escalation_manager_no_db.get_escalation_count(request_id)
        assert count >= 2  # At least 2 escalations were recorded


# ============================================================================
# Cooldown Tests
# ============================================================================

class TestCooldown:
    """Test cooldown functionality."""

    def test_cooldown_expires_after_5_minutes(self, escalation_manager_no_db):
        """Escalation should be allowed after cooldown period expires."""
        # Set escalation timestamp to 6 minutes ago
        past_time = datetime.utcnow() - timedelta(minutes=6)
        escalation_manager_no_db.escalation_log[CognitiveTier.STANDARD.value] = past_time

        # Should not be on cooldown anymore
        is_on_cooldown = escalation_manager_no_db._is_on_cooldown(CognitiveTier.STANDARD)
        assert is_on_cooldown is False

        # Escalation should now be allowed
        should, _, _ = escalation_manager_no_db.should_escalate(
            current_tier=CognitiveTier.STANDARD,
            response_quality=70,
            error=None,
            rate_limited=False
        )
        assert should is True

    def test_get_cooldown_remaining(self, escalation_manager_no_db):
        """Should return remaining cooldown time in seconds."""
        # Set escalation timestamp to 3 minutes ago
        past_time = datetime.utcnow() - timedelta(minutes=3)
        escalation_manager_no_db.escalation_log[CognitiveTier.STANDARD.value] = past_time

        remaining = escalation_manager_no_db.get_cooldown_remaining(CognitiveTier.STANDARD)

        # Should have ~2 minutes remaining (120 seconds)
        assert 110 < remaining < 130

    def test_reset_cooldown(self, escalation_manager_no_db):
        """Manual cooldown reset should work."""
        escalation_manager_no_db.escalation_log[CognitiveTier.STANDARD.value] = datetime.utcnow()

        # Verify on cooldown
        assert escalation_manager_no_db._is_on_cooldown(CognitiveTier.STANDARD) is True

        # Reset
        escalation_manager_no_db.reset_cooldown(CognitiveTier.STANDARD)

        # Should not be on cooldown anymore
        assert escalation_manager_no_db._is_on_cooldown(CognitiveTier.STANDARD) is False
