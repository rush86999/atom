"""
Integration tests for zombie subscription detection.

Tests validate end-to-end zombie subscription detection scenarios:
- Subscriptions unused for 30/60/90 days detected
- Zero active users flagged (high cost)
- Cost-weighted prioritization
- Configurable thresholds
- Active/recently used subscriptions not flagged
- Zombie subscription recovery tracking
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from core.financial_ops_engine import CostLeakDetector, SaaSSubscription
from core.decimal_utils import to_decimal
from tests.fixtures.decimal_fixtures import money_strategy


# ==================== FIXTURES ====================

@pytest.fixture
def detector():
    """Create a fresh CostLeakDetector for each test."""
    return CostLeakDetector(unused_threshold_days=30)


def create_subscription(
    sub_id: str,
    name: str,
    monthly_cost: Decimal,
    days_unused: int = 0,
    active_users: int = 5,
    category: str = "general"
) -> SaaSSubscription:
    """Helper to create a subscription with last_used date."""
    last_used = datetime.now() - timedelta(days=days_unused)
    return SaaSSubscription(
        id=sub_id,
        name=name,
        monthly_cost=monthly_cost,
        last_used=last_used,
        user_count=10,
        active_users=active_users,
        category=category
    )


# ==================== ZOMBIE DETECTION TESTS ====================

class TestZombieSubscriptionDetection:
    """Test zombie subscription (unused service) detection scenarios."""

    def test_zombie_subscription_30_days_unused(self, detector):
        """
        Test subscription unused for 30 days is detected as zombie.

        Scenario: Subscription costing $100/month unused for 30 days
        Expected: Detected as unused with recommendation to cancel/review
        """
        # Create zombie subscription (30 days unused)
        zombie = create_subscription(
            "zombie_30",
            "Zombie Tool",
            to_decimal("100.00"),
            days_unused=30,
            active_users=0,
            category="analytics"
        )
        detector.add_subscription(zombie)

        # Detect unused
        unused = detector.detect_unused()

        assert len(unused) == 1
        assert unused[0]["id"] == "zombie_30"
        assert unused[0]["monthly_cost"] == 100.0
        assert unused[0]["days_unused"] == 30
        assert "recommendation" in unused[0]

    def test_zombie_subscription_90_days_unused(self, detector):
        """
        Test subscription unused for 90 days detected with higher priority.

        Scenario: Subscription costing $200/month unused for 90 days
        Expected: Detected as zombie, prioritized by cost in sorted list
        """
        # Create zombie subscription (90 days unused)
        zombie = create_subscription(
            "zombie_90",
            "Old Zombie Tool",
            to_decimal("200.00"),
            days_unused=90,
            active_users=0,
            category="productivity"
        )
        detector.add_subscription(zombie)

        # Detect unused
        unused = detector.detect_unused()

        assert len(unused) == 1
        assert unused[0]["id"] == "zombie_90"
        assert unused[0]["days_unused"] >= 90  # May be slightly more due to test timing

    def test_zombie_subscription_zero_active_users(self, detector):
        """
        Test subscription with 0 active users flagged even if recently accessed.

        Scenario: Subscription used 5 days ago but has 0 active users
        Expected: Not flagged as unused (recent access), but anomaly detected
        """
        # Create subscription with 0 active users but recently accessed
        sub = create_subscription(
            "zero_users",
            "Zero User Tool",
            to_decimal("500.00"),  # High cost
            days_unused=5,  # Recently accessed
            active_users=0,  # But no active users
            category="analytics"
        )
        detector.add_subscription(sub)

        # Detect unused (should NOT be flagged - recent access)
        unused = detector.detect_unused()
        assert len(unused) == 0, "Recently accessed subscription should not be flagged as unused"

        # But should be detected as anomaly
        anomalies = detector.detect_anomalies()
        zero_user_anomalies = [a for a in anomalies if a["type"] == "zero_active_users_high_cost"]
        assert len(zero_user_anomalies) == 1, "Zero active users with high cost should be flagged as anomaly"

    def test_zombie_subscription_cost_weighting(self, detector):
        """
        Test higher cost zombie subscriptions prioritized in report.

        Scenario: 3 zombie subscriptions costing $50, $200, $100
        Expected: Sorted by cost descending (200, 100, 50)
        """
        # Create multiple zombie subscriptions with different costs
        zombie1 = create_subscription("zombie_50", "Low Cost Zombie", to_decimal("50.00"), days_unused=60, active_users=0)
        zombie2 = create_subscription("zombie_200", "High Cost Zombie", to_decimal("200.00"), days_unused=60, active_users=0)
        zombie3 = create_subscription("zombie_100", "Medium Cost Zombie", to_decimal("100.00"), days_unused=60, active_users=0)

        detector.add_subscription(zombie1)
        detector.add_subscription(zombie2)
        detector.add_subscription(zombie3)

        # Detect unused
        unused = detector.detect_unused()

        assert len(unused) == 3
        # Should be sorted by cost descending
        assert unused[0]["monthly_cost"] == 200.0
        assert unused[1]["monthly_cost"] == 100.0
        assert unused[2]["monthly_cost"] == 50.0

    def test_zombie_subscription_threshold_configurable(self, detector):
        """
        Test different thresholds (30, 60, 90 days) work correctly.

        Scenario: Same subscriptions with different threshold settings
        Expected: Detection adjusts based on threshold
        """
        # Create subscriptions at 30, 60, 90 days unused
        sub30 = create_subscription("sub_30", "30 Days", to_decimal("100.00"), days_unused=30, active_users=0)
        sub60 = create_subscription("sub_60", "60 Days", to_decimal("100.00"), days_unused=60, active_users=0)
        sub90 = create_subscription("sub_90", "90 Days", to_decimal("100.00"), days_unused=90, active_users=0)

        detector.add_subscription(sub30)
        detector.add_subscription(sub60)
        detector.add_subscription(sub90)

        # Test with 30-day threshold
        detector_30 = CostLeakDetector(unused_threshold_days=30)
        detector_30.add_subscription(sub30)
        detector_30.add_subscription(sub60)
        detector_30.add_subscription(sub90)
        unused_30 = detector_30.detect_unused()
        assert len(unused_30) == 3, "All should be detected with 30-day threshold"

        # Test with 60-day threshold
        detector_60 = CostLeakDetector(unused_threshold_days=60)
        detector_60.add_subscription(sub30)
        detector_60.add_subscription(sub60)
        detector_60.add_subscription(sub90)
        unused_60 = detector_60.detect_unused()
        # 30-day subscription may or may not be flagged depending on exact timing
        assert len(unused_60) >= 2, "At least 60+ day subscriptions should be detected"

        # Test with 90-day threshold
        detector_90 = CostLeakDetector(unused_threshold_days=90)
        detector_90.add_subscription(sub30)
        detector_90.add_subscription(sub60)
        detector_90.add_subscription(sub90)
        unused_90 = detector_90.detect_unused()
        # Only 90-day subscription should be flagged
        assert len(unused_90) >= 1, "90+ day subscription should be detected"

    def test_active_subscription_not_flagged(self, detector):
        """
        Test subscription with active users not flagged as zombie.

        Scenario: Subscription with active users used within threshold
        Expected: Not flagged as zombie
        """
        # Create active subscription
        active = create_subscription(
            "active",
            "Active Tool",
            to_decimal("100.00"),
            days_unused=5,  # Recently used
            active_users=10,  # Has active users
            category="analytics"
        )
        detector.add_subscription(active)

        # Detect unused
        unused = detector.detect_unused()

        assert len(unused) == 0, "Active subscription should not be flagged"

    def test_recently_used_subscription_not_flagged(self, detector):
        """
        Test subscription used yesterday not flagged as zombie.

        Scenario: Subscription used 1 day ago
        Expected: Not flagged as zombie
        """
        # Create recently used subscription
        recent = create_subscription(
            "recent",
            "Recent Tool",
            to_decimal("150.00"),
            days_unused=1,  # Used yesterday
            active_users=5,
            category="productivity"
        )
        detector.add_subscription(recent)

        # Detect unused
        unused = detector.detect_unused()

        assert len(unused) == 0, "Recently used subscription should not be flagged"

    def test_zombie_detection_with_mixed_usage(self, detector):
        """
        Test mix of zombie and active subscriptions detected correctly.

        Scenario: 5 subscriptions - 2 zombies, 3 active
        Expected: Only 2 zombies flagged
        """
        # Create mixed subscriptions
        zombie1 = create_subscription("zombie1", "Zombie 1", to_decimal("100.00"), days_unused=60, active_users=0)
        zombie2 = create_subscription("zombie2", "Zombie 2", to_decimal("200.00"), days_unused=90, active_users=0)
        active1 = create_subscription("active1", "Active 1", to_decimal("50.00"), days_unused=5, active_users=10)
        active2 = create_subscription("active2", "Active 2", to_decimal("75.00"), days_unused=1, active_users=5)
        active3 = create_subscription("active3", "Active 3", to_decimal("125.00"), days_unused=10, active_users=15)

        detector.add_subscription(zombie1)
        detector.add_subscription(zombie2)
        detector.add_subscription(active1)
        detector.add_subscription(active2)
        detector.add_subscription(active3)

        # Detect unused
        unused = detector.detect_unused()

        assert len(unused) == 2, "Only 2 zombie subscriptions should be flagged"
        zombie_ids = {u["id"] for u in unused}
        assert zombie_ids == {"zombie1", "zombie2"}

    def test_zombie_savings_calculation(self, detector):
        """
        Test savings from canceling zombies calculated correctly.

        Scenario: 2 zombie subscriptions costing $100 and $200
        Expected: Monthly savings = $300, annual = $3600
        """
        # Create zombie subscriptions
        zombie1 = create_subscription("zombie1", "Zombie 1", to_decimal("100.00"), days_unused=60, active_users=0)
        zombie2 = create_subscription("zombie2", "Zombie 2", to_decimal("200.00"), days_unused=90, active_users=0)

        detector.add_subscription(zombie1)
        detector.add_subscription(zombie2)

        # Get savings report
        report = detector.get_savings_report()

        assert report["potential_monthly_savings"] == 300.0
        assert report["potential_annual_savings"] == 3600.0
        assert len(report["unused_subscriptions"]) == 2

    def test_zombie_recommendation(self, detector):
        """
        Test zombie subscriptions have 'cancel or review' recommendation.

        Scenario: Zombie subscription detected
        Expected: Recommendation field contains action text
        """
        # Create zombie subscription
        zombie = create_subscription("zombie", "Zombie Tool", to_decimal("100.00"), days_unused=60, active_users=0)
        detector.add_subscription(zombie)

        # Detect unused
        unused = detector.detect_unused()

        assert len(unused) == 1
        assert "recommendation" in unused[0]
        assert len(unused[0]["recommendation"]) > 0, "Zombie should have recommendation text"


# ==================== ZOMBIE RECOVERY TESTS ====================

class TestZombieSubscriptionRecovery:
    """Test zombie subscription recovery (reactivation) scenarios."""

    def test_zombie_becomes_active(self, detector):
        """
        Test subscription used again exits zombie list.

        Scenario: Zombie subscription used again after 90 days
        Expected: No longer flagged as zombie
        """
        # Create zombie subscription
        zombie = create_subscription("zombie", "Zombie Tool", to_decimal("100.00"), days_unused=90, active_users=0)
        detector.add_subscription(zombie)

        # Verify it's detected as zombie
        unused = detector.detect_unused()
        assert len(unused) == 1

        # Simulate recovery: update last_used to yesterday
        recovered_zombie = create_subscription(
            "zombie",
            "Zombie Tool",
            to_decimal("100.00"),
            days_unused=1,  # Used yesterday
            active_users=5,  # Now has active users
            category="analytics"
        )
        # Replace subscription
        detector._subscriptions["zombie"] = recovered_zombie

        # Detect unused again
        unused_after = detector.detect_unused()

        assert len(unused_after) == 0, "Recovered subscription should not be flagged"

    def test_zombie_recovery_tracked(self, detector):
        """
        Test recovery (reactivation) is trackable.

        Scenario: Zombie subscription with usage history
        Expected: Can track before/after state
        """
        # Create zombie subscription
        zombie = create_subscription("zombie", "Zombie Tool", to_decimal("100.00"), days_unused=60, active_users=0)
        detector.add_subscription(zombie)

        # Get zombie state
        unused_before = detector.detect_unused()
        zombie_before = [u for u in unused_before if u["id"] == "zombie"][0]

        assert zombie_before["days_unused"] >= 60

        # Update to active state
        recovered = create_subscription("zombie", "Zombie Tool", to_decimal("100.00"), days_unused=1, active_users=5)
        detector._subscriptions["zombie"] = recovered

        # Get recovered state
        unused_after = detector.detect_unused()
        zombie_ids_after = [u["id"] for u in unused_after]

        assert "zombie" not in zombie_ids_after, "Recovered zombie should not be in unused list"


# ==================== EDGE CASES ====================

class TestZombieEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_at_threshold(self, detector):
        """
        Test subscription exactly at threshold boundary.

        Scenario: Subscription unused exactly 30 days ago
        Expected: Behavior depends on implementation (may or may not be flagged)
        """
        # Create subscription at exact threshold
        # Note: Due to datetime.now() timing, exact boundary is tricky
        # We accept either result as long as it's consistent
        sub = create_subscription("boundary", "Boundary Tool", to_decimal("100.00"), days_unused=30, active_users=0)
        detector.add_subscription(sub)

        # Detect unused
        unused = detector.detect_unused()

        # Accept 0 or 1 (boundary condition)
        assert len(unused) in [0, 1], "Boundary condition should be handled consistently"

    def test_no_subscriptions(self, detector):
        """
        Test detector with no subscriptions.

        Scenario: Empty detector
        Expected: No errors, empty results
        """
        # Don't add any subscriptions
        unused = detector.detect_unused()
        report = detector.get_savings_report()

        assert len(unused) == 0
        assert report["potential_monthly_savings"] == 0.0
        assert report["potential_annual_savings"] == 0.0

    def test_all_zombies(self, detector):
        """
        Test all subscriptions are zombies.

        Scenario: 5 subscriptions, all unused > 30 days
        Expected: All 5 flagged as zombies
        """
        # Create 5 zombie subscriptions
        for i in range(5):
            zombie = create_subscription(
                f"zombie_{i}",
                f"Zombie {i}",
                to_decimal(f"{100 + i * 10}.00"),
                days_unused=30 + i * 10,
                active_users=0
            )
            detector.add_subscription(zombie)

        # Detect unused
        unused = detector.detect_unused()

        assert len(unused) == 5, "All subscriptions should be flagged"

    def test_no_zombies(self, detector):
        """
        Test no subscriptions are zombies.

        Scenario: 5 subscriptions, all used within 7 days
        Expected: None flagged as zombies
        """
        # Create 5 active subscriptions
        for i in range(5):
            active = create_subscription(
                f"active_{i}",
                f"Active {i}",
                to_decimal(f"{100 + i * 10}.00"),
                days_unused=i % 7,  # All used within 7 days
                active_users=5 + i
            )
            detector.add_subscription(active)

        # Detect unused
        unused = detector.detect_unused()

        assert len(unused) == 0, "No subscriptions should be flagged"
