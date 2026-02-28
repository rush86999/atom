"""
Budget Guardrail Validation Tests

Tests for configurable budget thresholds, enforcement actions, and threshold validation.
Validates that alerts fire at correct thresholds (warn, pause, block) and enforcement
actions match the expected status.
"""

import pytest
from decimal import Decimal
from core.financial_ops_engine import BudgetGuardrails, BudgetLimit, SpendStatus


class TestDefaultThresholds:
    """Test default threshold behavior (80% warn, 90% pause, 100% block)"""

    def test_default_thresholds_80_90_100(self):
        """Verify default thresholds are 80%, 90%, 100%"""
        limit = BudgetLimit("test", Decimal("1000"))
        assert limit.warn_threshold_pct == 80
        assert limit.pause_threshold_pct == 90
        assert limit.block_threshold_pct == 100

    def test_default_warn_at_80_percent(self):
        """Spend crosses 80% threshold -> status=PENDING"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        result = bg.check_spend("compute", Decimal("800"))
        assert result["status"] == SpendStatus.PENDING.value
        assert result["utilization_pct"] == 80.0

    def test_default_pause_at_90_percent(self):
        """Spend crosses 90% threshold -> status=PAUSED"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        result = bg.check_spend("compute", Decimal("900"))
        assert result["status"] == SpendStatus.PAUSED.value
        assert result["utilization_pct"] == 90.0

    def test_default_block_at_100_percent(self):
        """Spend crosses 100% threshold -> status=REJECTED"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        result = bg.check_spend("compute", Decimal("1000"))
        assert result["status"] == SpendStatus.REJECTED.value
        assert result["utilization_pct"] == 100.0


class TestConfigurableThresholds:
    """Test custom threshold configuration"""

    def test_custom_warn_threshold(self):
        """Set warn=70%, verify triggers at 70%"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"), warn_threshold_pct=70)
        bg.set_limit(limit)

        # At 69% - should be approved
        result = bg.check_spend("compute", Decimal("690"))
        assert result["status"] == SpendStatus.APPROVED.value

        # At 70% - should be pending
        result = bg.check_spend("compute", Decimal("700"))
        assert result["status"] == SpendStatus.PENDING.value

    def test_custom_pause_threshold(self):
        """Set pause=85%, verify triggers at 85%"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"), pause_threshold_pct=85)
        bg.set_limit(limit)

        # At 85% - should be paused
        result = bg.check_spend("compute", Decimal("850"))
        assert result["status"] == SpendStatus.PAUSED.value
        assert result["utilization_pct"] == 85.0

    def test_custom_block_threshold(self):
        """Set block=95%, verify triggers at 95%"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"), block_threshold_pct=95)
        bg.set_limit(limit)

        # At 95% - should be rejected
        result = bg.check_spend("compute", Decimal("950"))
        assert result["status"] == SpendStatus.REJECTED.value
        assert result["utilization_pct"] == 95.0

    def test_all_custom_thresholds(self):
        """Set 70/85/95, verify all trigger correctly"""
        bg = BudgetGuardrails()
        limit = BudgetLimit(
            "compute",
            Decimal("1000"),
            warn_threshold_pct=70,
            pause_threshold_pct=85,
            block_threshold_pct=95
        )
        bg.set_limit(limit)

        # Below warn - approved
        result = bg.check_spend("compute", Decimal("600"))
        assert result["status"] == SpendStatus.APPROVED.value

        # At warn - pending
        result = bg.check_spend("compute", Decimal("700"))
        assert result["status"] == SpendStatus.PENDING.value

        # At pause - paused
        result = bg.check_spend("compute", Decimal("850"))
        assert result["status"] == SpendStatus.PAUSED.value

        # At block - rejected
        result = bg.check_spend("compute", Decimal("950"))
        assert result["status"] == SpendStatus.REJECTED.value

    def test_update_thresholds(self):
        """update_thresholds() modifies existing limit"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Initially at 80% - should be pending with default thresholds
        result = bg.check_spend("compute", Decimal("800"))
        assert result["status"] == SpendStatus.PENDING.value

        # Update to warn=70%
        bg.update_thresholds("compute", warn=70)

        # Now at 80% - should still be pending (between 70% warn and 90% pause)
        result = bg.check_spend("compute", Decimal("800"))
        assert result["status"] == SpendStatus.PENDING.value
        assert limit.warn_threshold_pct == 70

    def test_reset_thresholds(self):
        """Reset restores defaults (80/90/100)"""
        bg = BudgetGuardrails()
        limit = BudgetLimit(
            "compute",
            Decimal("1000"),
            warn_threshold_pct=60,
            pause_threshold_pct=80,
            block_threshold_pct=90
        )
        bg.set_limit(limit)

        # Verify custom thresholds
        assert limit.warn_threshold_pct == 60
        assert limit.pause_threshold_pct == 80
        assert limit.block_threshold_pct == 90

        # Reset to defaults
        bg.reset_thresholds("compute")

        # Verify default thresholds restored
        assert limit.warn_threshold_pct == 80
        assert limit.pause_threshold_pct == 90
        assert limit.block_threshold_pct == 100


class TestThresholdValidation:
    """Test threshold validation and error handling"""

    def test_thresholds_must_be_ordered(self):
        """warn < pause < block required"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        with pytest.raises(ValueError, match="Invalid thresholds"):
            bg.update_thresholds("compute", warn=90, pause=80, block=100)

    def test_equal_thresholds_rejected(self):
        """warn=90, pause=90 raises error"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        with pytest.raises(ValueError, match="Invalid thresholds"):
            bg.update_thresholds("compute", warn=90, pause=90, block=100)

    def test_inverted_thresholds_rejected(self):
        """warn=90, pause=80 raises error"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        with pytest.raises(ValueError, match="Invalid thresholds"):
            bg.update_thresholds("compute", warn=90, pause=80, block=95)

    def test_negative_threshold_rejected(self):
        """Negative threshold raises error"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        with pytest.raises(ValueError, match="Invalid thresholds"):
            bg.update_thresholds("compute", warn=-10, pause=90, block=100)

    def test_threshold_over_100_rejected(self):
        """warn=110 raises error"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        with pytest.raises(ValueError, match="Invalid thresholds"):
            bg.update_thresholds("compute", warn=110, pause=90, block=100)

    def test_threshold_category_not_found(self):
        """Updating non-existent category raises KeyError"""
        bg = BudgetGuardrails()

        with pytest.raises(KeyError, match="not found in limits"):
            bg.update_thresholds("nonexistent", warn=70)

    def test_reset_category_not_found(self):
        """Resetting non-existent category raises KeyError"""
        bg = BudgetGuardrails()

        with pytest.raises(KeyError, match="not found in limits"):
            bg.reset_thresholds("nonexistent")


class TestEnforcementActions:
    """Test enforcement actions match expected status"""

    def test_approved_status_below_warn(self):
        """Below warn threshold -> status=APPROVED"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        result = bg.check_spend("compute", Decimal("700"))
        assert result["status"] == SpendStatus.APPROVED.value

    def test_pending_status_at_warn(self):
        """At warn threshold -> status=PENDING"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        result = bg.check_spend("compute", Decimal("800"))
        assert result["status"] == SpendStatus.PENDING.value

    def test_paused_status_at_pause(self):
        """At pause threshold -> status=PAUSED"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        result = bg.check_spend("compute", Decimal("900"))
        assert result["status"] == SpendStatus.PAUSED.value

    def test_rejected_status_at_block(self):
        """At block threshold -> status=REJECTED"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        result = bg.check_spend("compute", Decimal("1000"))
        assert result["status"] == SpendStatus.REJECTED.value

    def test_over_budget_still_rejected(self):
        """Above 100% -> status=REJECTED"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        result = bg.check_spend("compute", Decimal("1100"))
        assert result["status"] == SpendStatus.REJECTED.value
        assert result["utilization_pct"] == 110.0


class TestThresholdTransitions:
    """Test status transitions as spending increases"""

    def test_transition_approved_to_pending(self):
        """Cross warn threshold"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Start below warn
        result = bg.check_spend("compute", Decimal("500"))
        assert result["status"] == SpendStatus.APPROVED.value

        # Cross warn threshold
        result = bg.check_spend("compute", Decimal("800"))
        assert result["status"] == SpendStatus.PENDING.value

    def test_transition_pending_to_paused(self):
        """Cross pause threshold"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Start at warn
        result = bg.check_spend("compute", Decimal("800"))
        assert result["status"] == SpendStatus.PENDING.value

        # Cross pause threshold
        result = bg.check_spend("compute", Decimal("900"))
        assert result["status"] == SpendStatus.PAUSED.value

    def test_transition_paused_to_rejected(self):
        """Cross block threshold"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Start at pause
        result = bg.check_spend("compute", Decimal("900"))
        assert result["status"] == SpendStatus.PAUSED.value

        # Cross block threshold
        result = bg.check_spend("compute", Decimal("1000"))
        assert result["status"] == SpendStatus.REJECTED.value

    def test_no_transition_below_warn(self):
        """Below all thresholds -> approved"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Various values below 80%
        for amount in [100, 400, 700, 799]:
            result = bg.check_spend("compute", Decimal(str(amount)))
            assert result["status"] == SpendStatus.APPROVED.value

    def test_multiple_thresholds_crossed(self):
        """Large spend crossing all thresholds"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Jump from 0 to 100%+ in one check
        result = bg.check_spend("compute", Decimal("1200"))
        assert result["status"] == SpendStatus.REJECTED.value


class TestThresholdCalculations:
    """Test threshold calculation precision and boundary conditions"""

    def test_utilization_percentage_calculation(self):
        """usage_pct = (burn / limit) * 100"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        result = bg.check_spend("compute", Decimal("750"))
        assert result["utilization_pct"] == 75.0

    def test_remaining_until_threshold(self):
        """Calculate remaining until next threshold"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Set current spend to 70%
        limit.current_spend = Decimal("700")

        # Get status should calculate remaining until warn threshold (80%)
        status = bg.get_threshold_status(limit)
        # Warn threshold at 80% = 800, 800 - 700 = 100 remaining
        assert status["remaining_until_threshold"] == Decimal("100")

    def test_threshold_boundary_exact(self):
        """Exact threshold value triggers correctly"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Exact warn threshold
        result = bg.check_spend("compute", Decimal("800"))
        assert result["status"] == SpendStatus.PENDING.value

        # Exact pause threshold
        result = bg.check_spend("compute", Decimal("900"))
        assert result["status"] == SpendStatus.PAUSED.value

        # Exact block threshold
        result = bg.check_spend("compute", Decimal("1000"))
        assert result["status"] == SpendStatus.REJECTED.value

    def test_threshold_boundary_one_cent(self):
        """One cent over threshold triggers"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # One cent over warn threshold
        result = bg.check_spend("compute", Decimal("800.01"))
        assert result["status"] == SpendStatus.PENDING.value

        # One cent over pause threshold
        result = bg.check_spend("compute", Decimal("900.01"))
        assert result["status"] == SpendStatus.PAUSED.value

        # One cent over block threshold
        result = bg.check_spend("compute", Decimal("1000.01"))
        assert result["status"] == SpendStatus.REJECTED.value

    def test_decimal_precision(self):
        """Threshold calculations use Decimal precision"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000.00"))
        bg.set_limit(limit)

        # Precise calculation
        result = bg.check_spend("compute", Decimal("837.53"))
        assert result["utilization_pct"] == 83.753


class TestCategoryThresholds:
    """Test that different categories can have different thresholds"""

    def test_different_categories_different_thresholds(self):
        """Each category can have different thresholds"""
        bg = BudgetGuardrails()

        # Critical category: warn at 50%, pause at 75%
        critical_limit = BudgetLimit(
            "critical_compute",
            Decimal("1000"),
            warn_threshold_pct=50,
            pause_threshold_pct=75,
            block_threshold_pct=90
        )
        bg.set_limit(critical_limit)

        # Non-critical category: warn at 80%, pause at 90%
        normal_limit = BudgetLimit(
            "normal_compute",
            Decimal("1000"),
            warn_threshold_pct=80,
            pause_threshold_pct=90,
            block_threshold_pct=100
        )
        bg.set_limit(normal_limit)

        # At 70%: critical is pending (between 50% warn and 75% pause), normal is approved
        critical_result = bg.check_spend("critical_compute", Decimal("700"))
        normal_result = bg.check_spend("normal_compute", Decimal("700"))

        assert critical_result["status"] == SpendStatus.PENDING.value
        assert normal_result["status"] == SpendStatus.APPROVED.value

    def test_category_independent_enforcement(self):
        """One category paused doesn't affect others"""
        bg = BudgetGuardrails()

        limit1 = BudgetLimit("category_a", Decimal("1000"))
        limit2 = BudgetLimit("category_b", Decimal("1000"))
        bg.set_limit(limit1)
        bg.set_limit(limit2)

        # Pause category_a
        bg.check_spend("category_a", Decimal("900"))

        # Category_b should still work
        result = bg.check_spend("category_b", Decimal("500"))
        assert result["status"] == SpendStatus.APPROVED.value

    def test_no_limit_means_no_enforcement(self):
        """Category without limit always approved"""
        bg = BudgetGuardrails()

        # No limit set for this category
        result = bg.check_spend("unlimited_category", Decimal("999999"))
        assert result["status"] == SpendStatus.APPROVED.value
        assert result["reason"] == "No limit set"


class TestThresholdStatusReporting:
    """Test threshold status reporting and metadata"""

    def test_get_threshold_status(self):
        """Returns current status and next threshold"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Set current spend to 70%
        limit.current_spend = Decimal("700")

        status = bg.get_threshold_status(limit)

        assert status["status"] == SpendStatus.APPROVED.value
        assert status["usage_pct"] == Decimal("70")
        assert status["next_threshold"] == "Warn at 80%"

    def test_status_includes_remaining(self):
        """Report includes remaining until threshold"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Set current spend to 70%
        limit.current_spend = Decimal("700")

        status = bg.get_threshold_status(limit)

        # 100 remaining until 80% warn threshold
        assert status["remaining_until_threshold"] == Decimal("100")

    def test_status_includes_usage_pct(self):
        """Report includes utilization percentage"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Set current spend to 85%
        limit.current_spend = Decimal("850")

        status = bg.get_threshold_status(limit)

        assert status["usage_pct"] == Decimal("85")
        # At 85%, we're between warn (80%) and pause (90%), so status is pending
        assert status["status"] == SpendStatus.PENDING.value
        assert status["next_threshold"] == "Pause at 90%"

    def test_status_at_block_threshold(self):
        """Status report when at block threshold"""
        bg = BudgetGuardrails()
        limit = BudgetLimit("compute", Decimal("1000"))
        bg.set_limit(limit)

        # Set current spend to 100%
        limit.current_spend = Decimal("1000")

        status = bg.get_threshold_status(limit)

        assert status["status"] == SpendStatus.REJECTED.value
        assert status["next_threshold"] is None
        assert status["remaining_until_threshold"] == Decimal("0")
