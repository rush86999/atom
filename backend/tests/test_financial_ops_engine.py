"""
Comprehensive test suite for Financial Operations Engine

Tests cost leak detection, budget guardrails, invoice reconciliation,
SaaS subscription management, spending approvals, and financial calculations.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.append(os.getcwd())

from core.financial_ops_engine import (
    SaaSSubscription,
    CostLeakDetector,
    BudgetLimit,
    BudgetGuardrails,
    SpendStatus,
    Invoice,
    Contract,
    InvoiceReconciler
)


class TestSaaSSubscription(unittest.TestCase):
    """Test suite for SaaSSubscription dataclass"""

    def test_subscription_creation(self):
        """Test creating a SaaS subscription"""
        sub = SaaSSubscription(
            id="sub-1",
            name="GitHub",
            monthly_cost=Decimal("29.99"),
            last_used=datetime.now(),
            user_count=5,
            active_users=3,
            category="development"
        )

        self.assertEqual(sub.id, "sub-1")
        self.assertEqual(sub.name, "GitHub")
        self.assertEqual(sub.monthly_cost, Decimal("29.99"))
        self.assertEqual(sub.active_users, 3)


class TestCostLeakDetector(unittest.TestCase):
    """Test suite for CostLeakDetector"""

    def setUp(self):
        """Setup detector with test subscriptions"""
        self.detector = CostLeakDetector(unused_threshold_days=30)

    def test_add_subscription(self):
        """Test adding subscription to detector"""
        sub = SaaSSubscription(
            id="sub-1",
            name="Test Tool",
            monthly_cost=Decimal("100.00"),
            last_used=datetime.now(),
            user_count=5
        )
        self.detector.add_subscription(sub)

        self.assertEqual(len(self.detector._subscriptions), 1)
        self.assertIsNotNone(self.detector.get_subscription_by_id("sub-1"))

    def test_detect_unused_subscriptions(self):
        """Test detection of unused subscriptions"""
        # Unused subscription (last used 60 days ago)
        unused_sub = SaaSSubscription(
            id="sub-1",
            name="Unused Tool",
            monthly_cost=Decimal("50.00"),
            last_used=datetime.now() - timedelta(days=60),
            user_count=5
        )

        # Active subscription (last used yesterday)
        active_sub = SaaSSubscription(
            id="sub-2",
            name="Active Tool",
            monthly_cost=Decimal("100.00"),
            last_used=datetime.now() - timedelta(days=1),
            user_count=5
        )

        self.detector.add_subscription(unused_sub)
        self.detector.add_subscription(active_sub)

        unused = self.detector.detect_unused()

        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0]["id"], "sub-1")
        self.assertGreater(unused[0]["days_unused"], 30)

    def test_detect_redundant_subscriptions(self):
        """Test detection of redundant subscriptions in same category"""
        sub1 = SaaSSubscription(
            id="sub-1",
            name="Tool A",
            monthly_cost=Decimal("50.00"),
            last_used=datetime.now(),
            user_count=5,
            category="communication"
        )

        sub2 = SaaSSubscription(
            id="sub-2",
            name="Tool B",
            monthly_cost=Decimal("75.00"),
            last_used=datetime.now(),
            user_count=3,
            category="communication"
        )

        self.detector.add_subscription(sub1)
        self.detector.add_subscription(sub2)

        redundant = self.detector.detect_redundant()

        self.assertEqual(len(redundant), 1)
        self.assertEqual(redundant[0]["category"], "communication")
        self.assertEqual(len(redundant[0]["tools"]), 2)
        self.assertEqual(redundant[0]["total_monthly_cost"], 125.00)

    def test_get_savings_report(self):
        """Test generation of savings report"""
        # Add unused subscription
        unused_sub = SaaSSubscription(
            id="sub-1",
            name="Unused Expensive Tool",
            monthly_cost=Decimal("200.00"),
            last_used=datetime.now() - timedelta(days=45),
            user_count=5
        )

        # Add redundant subscriptions
        sub1 = SaaSSubscription(
            id="sub-2",
            name="Tool A",
            monthly_cost=Decimal("50.00"),
            last_used=datetime.now(),
            user_count=5,
            category="communication"
        )

        sub2 = SaaSSubscription(
            id="sub-3",
            name="Tool B",
            monthly_cost=Decimal("75.00"),
            last_used=datetime.now(),
            user_count=3,
            category="communication"
        )

        self.detector.add_subscription(unused_sub)
        self.detector.add_subscription(sub1)
        self.detector.add_subscription(sub2)

        report = self.detector.get_savings_report()

        self.assertEqual(len(report["unused_subscriptions"]), 1)
        self.assertEqual(len(report["redundant_tools"]), 1)
        self.assertEqual(report["potential_monthly_savings"], 200.00)
        self.assertEqual(report["potential_annual_savings"], 2400.00)

    def test_validate_categorization_all_valid(self):
        """Test categorization validation with all valid"""
        sub1 = SaaSSubscription(
            id="sub-1",
            name="Tool A",
            monthly_cost=Decimal("50.00"),
            last_used=datetime.now(),
            user_count=5,
            category="development"
        )

        sub2 = SaaSSubscription(
            id="sub-2",
            name="Tool B",
            monthly_cost=Decimal("75.00"),
            last_used=datetime.now(),
            user_count=3,
            category="communication"
        )

        self.detector.add_subscription(sub1)
        self.detector.add_subscription(sub2)

        result = self.detector.validate_categorization()

        self.assertTrue(result["valid"])
        self.assertEqual(len(result["uncategorized"]), 0)
        self.assertEqual(len(result["invalid"]), 0)

    def test_validate_categorization_uncategorized(self):
        """Test categorization validation with empty category"""
        sub = SaaSSubscription(
            id="sub-1",
            name="Tool",
            monthly_cost=Decimal("50.00"),
            last_used=datetime.now(),
            user_count=5,
            category=""  # Empty category
        )

        self.detector.add_subscription(sub)

        result = self.detector.validate_categorization()

        self.assertFalse(result["valid"])
        self.assertEqual(len(result["uncategorized"]), 1)

    def test_get_subscription_by_id(self):
        """Test retrieving subscription by ID"""
        sub = SaaSSubscription(
            id="sub-1",
            name="Test Tool",
            monthly_cost=Decimal("100.00"),
            last_used=datetime.now(),
            user_count=5
        )

        self.detector.add_subscription(sub)

        retrieved = self.detector.get_subscription_by_id("sub-1")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Test Tool")

    def test_get_subscription_by_id_not_found(self):
        """Test retrieving non-existent subscription"""
        retrieved = self.detector.get_subscription_by_id("nonexistent")

        self.assertIsNone(retrieved)

    def test_calculate_total_cost(self):
        """Test calculation of total monthly cost"""
        sub1 = SaaSSubscription(
            id="sub-1",
            name="Tool A",
            monthly_cost=Decimal("50.00"),
            last_used=datetime.now(),
            user_count=5
        )

        sub2 = SaaSSubscription(
            id="sub-2",
            name="Tool B",
            monthly_cost=Decimal("75.50"),
            last_used=datetime.now(),
            user_count=3
        )

        self.detector.add_subscription(sub1)
        self.detector.add_subscription(sub2)

        total = self.detector.calculate_total_cost()

        self.assertEqual(total, Decimal("125.50"))

    def test_verify_savings_calculation(self):
        """Test verification of savings calculation"""
        unused_sub = SaaSSubscription(
            id="sub-1",
            name="Unused Tool",
            monthly_cost=Decimal("200.00"),
            last_used=datetime.now() - timedelta(days=45),
            user_count=5
        )

        self.detector.add_subscription(unused_sub)

        verification = self.detector.verify_savings_calculation()

        self.assertTrue(verification["match"])
        self.assertEqual(verification["expected"], Decimal("200.00"))
        self.assertEqual(verification["actual"], Decimal("200.00"))
        self.assertEqual(verification["diff"], Decimal("0.00"))

    def test_detect_anomalies_zero_users_high_cost(self):
        """Test anomaly detection for high cost with no active users"""
        sub = SaaSSubscription(
            id="sub-1",
            name="Expensive Unused Tool",
            monthly_cost=Decimal("500.00"),
            last_used=datetime.now(),
            user_count=10,
            active_users=0  # No active users but high cost
        )

        self.detector.add_subscription(sub)

        anomalies = self.detector.detect_anomalies()

        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["type"], "zero_active_users_high_cost")

    def test_detect_anomalies_high_cost_unused(self):
        """Test anomaly detection for high cost unused subscription"""
        sub = SaaSSubscription(
            id="sub-1",
            name="Expensive Unused Tool",
            monthly_cost=Decimal("600.00"),
            last_used=datetime.now() - timedelta(days=45),
            user_count=5,
            active_users=0
        )

        self.detector.add_subscription(sub)

        anomalies = self.detector.detect_anomalies()

        # Should have 2 anomalies: zero_users_high_cost and high_cost_unused
        self.assertGreaterEqual(len(anomalies), 1)
        high_cost_anomalies = [a for a in anomalies if a["type"] == "high_cost_unused"]
        self.assertEqual(len(high_cost_anomalies), 1)


class TestBudgetGuardrails(unittest.TestCase):
    """Test suite for BudgetGuardrails"""

    def setUp(self):
        """Setup budget guardrails"""
        self.guardrails = BudgetGuardrails()

    def test_set_limit(self):
        """Test setting budget limit"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00")
        )

        self.guardrails.set_limit(limit)

        self.assertIn("marketing", self.guardrails._limits)

    def test_check_spend_no_limit(self):
        """Test spend check when no limit is set"""
        result = self.guardrails.check_spend("uncategorized", 500.00)

        self.assertEqual(result["status"], SpendStatus.APPROVED.value)
        self.assertEqual(result["reason"], "No limit set")

    def test_check_spend_paused_category(self):
        """Test spend check when category is paused"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00")
        )
        self.guardrails.set_limit(limit)
        self.guardrails._paused_categories.add("marketing")

        result = self.guardrails.check_spend("marketing", 500.00)

        self.assertEqual(result["status"], SpendStatus.PAUSED.value)

    def test_check_spend_approved(self):
        """Test spend check approved (under threshold)"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00"),
            current_spend=Decimal("3000.00")
        )
        self.guardrails.set_limit(limit)

        result = self.guardrails.check_spend("marketing", 1000.00)

        self.assertEqual(result["status"], SpendStatus.APPROVED.value)
        self.assertLess(result["utilization_pct"], 80)

    def test_check_spend_warn_threshold(self):
        """Test spend check at warn threshold"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00"),
            current_spend=Decimal("7500.00")  # 75% utilized
        )
        self.guardrails.set_limit(limit)

        result = self.guardrails.check_spend("marketing", 1000.00)  # Will reach 85%

        self.assertEqual(result["status"], SpendStatus.PENDING.value)
        self.assertIn("Warn threshold", result["reason"])

    def test_check_spend_pause_threshold(self):
        """Test spend check at pause threshold"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00"),
            current_spend=Decimal("8500.00")  # 85% utilized
        )
        self.guardrails.set_limit(limit)

        result = self.guardrails.check_spend("marketing", 1000.00)  # Will reach 95%

        self.assertEqual(result["status"], SpendStatus.PAUSED.value)
        self.assertIn("Pause threshold", result["reason"])

    def test_check_spend_block_threshold(self):
        """Test spend check at block threshold"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00"),
            current_spend=Decimal("9500.00")  # 95% utilized
        )
        self.guardrails.set_limit(limit)

        result = self.guardrails.check_spend("marketing", 1000.00)  # Will exceed 100%

        self.assertEqual(result["status"], SpendStatus.REJECTED.value)
        self.assertIn("block threshold", result["reason"])
        self.assertIn("marketing", self.guardrails._paused_categories)

    def test_check_spend_deal_stage_requirement(self):
        """Test spend check with deal stage requirement"""
        limit = BudgetLimit(
            category="enterprise",
            monthly_limit=Decimal("50000.00"),
            deal_stage_required="closed_won"
        )
        self.guardrails.set_limit(limit)

        result = self.guardrails.check_spend(
            "enterprise",
            5000.00,
            deal_stage="proposal"  # Wrong stage
        )

        self.assertEqual(result["status"], SpendStatus.REJECTED.value)
        self.assertIn("deal stage", result["reason"])

    def test_check_spend_milestone_requirement(self):
        """Test spend check with milestone requirement"""
        limit = BudgetLimit(
            category="enterprise",
            monthly_limit=Decimal("50000.00"),
            milestone_required="kickoff_complete"
        )
        self.guardrails.set_limit(limit)

        result = self.guardrails.check_spend(
            "enterprise",
            5000.00,
            milestone="pending"  # Milestone not complete
        )

        self.assertEqual(result["status"], SpendStatus.PENDING.value)
        self.assertIn("milestone", result["reason"])

    def test_record_spend(self):
        """Test recording approved spend"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00"),
            current_spend=Decimal("3000.00")
        )
        self.guardrails.set_limit(limit)

        self.guardrails.record_spend("marketing", 1000.00)

        self.assertEqual(self.guardrails._limits["marketing"].current_spend, Decimal("4000.00"))

    def test_get_threshold_status_approved(self):
        """Test getting threshold status for approved limit"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00"),
            current_spend=Decimal("5000.00")  # 50% utilized
        )

        status = self.guardrails.get_threshold_status(limit)

        self.assertEqual(status["status"], SpendStatus.APPROVED.value)
        self.assertEqual(status["usage_pct"], Decimal("50"))
        self.assertIn("Warn at", status["next_threshold"])

    def test_get_threshold_status_pending(self):
        """Test getting threshold status for pending limit"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00"),
            current_spend=Decimal("8500.00")  # 85% utilized
        )

        status = self.guardrails.get_threshold_status(limit)

        self.assertEqual(status["status"], SpendStatus.PENDING.value)
        self.assertIn("Pause at", status["next_threshold"])

    def test_get_threshold_status_paused(self):
        """Test getting threshold status for paused limit"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00"),
            current_spend=Decimal("9200.00")  # 92% utilized
        )

        status = self.guardrails.get_threshold_status(limit)

        self.assertEqual(status["status"], SpendStatus.PAUSED.value)
        self.assertIn("Block at", status["next_threshold"])

    def test_update_thresholds_success(self):
        """Test updating threshold configuration"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00")
        )
        self.guardrails.set_limit(limit)

        self.guardrails.update_thresholds(
            "marketing",
            warn=70,
            pause=85,
            block=95
        )

        updated_limit = self.guardrails._limits["marketing"]
        self.assertEqual(updated_limit.warn_threshold_pct, 70)
        self.assertEqual(updated_limit.pause_threshold_pct, 85)
        self.assertEqual(updated_limit.block_threshold_pct, 95)

    def test_update_thresholds_invalid_order(self):
        """Test updating thresholds with invalid order"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00")
        )
        self.guardrails.set_limit(limit)

        with self.assertRaises(ValueError) as context:
            self.guardrails.update_thresholds(
                "marketing",
                warn=90,  # warn > pause - invalid!
                pause=80,
                block=100
            )

        self.assertIn("Invalid thresholds", str(context.exception))

    def test_update_thresholds_nonexistent_category(self):
        """Test updating thresholds for non-existent category"""
        with self.assertRaises(KeyError):
            self.guardrails.update_thresholds("nonexistent", warn=70)

    def test_reset_thresholds(self):
        """Test resetting thresholds to defaults"""
        limit = BudgetLimit(
            category="marketing",
            monthly_limit=Decimal("10000.00"),
            warn_threshold_pct=60,
            pause_threshold_pct=80,
            block_threshold_pct=90
        )
        self.guardrails.set_limit(limit)

        self.guardrails.reset_thresholds("marketing")

        reset_limit = self.guardrails._limits["marketing"]
        self.assertEqual(reset_limit.warn_threshold_pct, 80)
        self.assertEqual(reset_limit.pause_threshold_pct, 90)
        self.assertEqual(reset_limit.block_threshold_pct, 100)


class TestInvoiceReconciler(unittest.TestCase):
    """Test suite for InvoiceReconciler"""

    def setUp(self):
        """Setup reconciler"""
        self.reconciler = InvoiceReconciler(tolerance_percent=5.0)

    def test_add_invoice(self):
        """Test adding invoice"""
        invoice = Invoice(
            id="inv-1",
            vendor="AWS",
            amount=Decimal("1000.00"),
            date=datetime.now()
        )

        self.reconciler.add_invoice(invoice)

        self.assertEqual(len(self.reconciler._invoices), 1)

    def test_add_contract(self):
        """Test adding contract"""
        contract = Contract(
            id="contract-1",
            vendor="AWS",
            monthly_amount=Decimal("950.00"),
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=365)
        )

        self.reconciler.add_contract(contract)

        self.assertIn("contract-1", self.reconciler._contracts)

    def test_reconcile_matched(self):
        """Test reconciliation with matched invoice"""
        contract = Contract(
            id="contract-1",
            vendor="AWS",
            monthly_amount=Decimal("1000.00"),
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=365)
        )

        invoice = Invoice(
            id="inv-1",
            vendor="AWS",
            amount=Decimal("1000.00"),
            date=datetime.now(),
            contract_id="contract-1"
        )

        self.reconciler.add_contract(contract)
        self.reconciler.add_invoice(invoice)

        result = self.reconciler.reconcile()

        self.assertEqual(len(result["matched"]), 1)
        self.assertEqual(result["summary"]["matched_count"], 1)
        self.assertEqual(result["summary"]["discrepancy_count"], 0)

    def test_reconcile_discrepancy(self):
        """Test reconciliation with amount discrepancy"""
        contract = Contract(
            id="contract-1",
            vendor="AWS",
            monthly_amount=Decimal("1000.00"),
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=365)
        )

        invoice = Invoice(
            id="inv-1",
            vendor="AWS",
            amount=Decimal("1100.00"),  # 10% difference - exceeds 5% tolerance
            date=datetime.now(),
            contract_id="contract-1"
        )

        self.reconciler.add_contract(contract)
        self.reconciler.add_invoice(invoice)

        result = self.reconciler.reconcile()

        self.assertEqual(len(result["discrepancies"]), 1)
        self.assertEqual(result["discrepancies"][0]["status"], "discrepancy")
        self.assertEqual(result["discrepancies"][0]["difference_percent"], 10.0)

    def test_reconcile_unmatched(self):
        """Test reconciliation with unmatched invoice"""
        invoice = Invoice(
            id="inv-1",
            vendor="Unknown Vendor",
            amount=Decimal("500.00"),
            date=datetime.now()
        )

        self.reconciler.add_invoice(invoice)

        result = self.reconciler.reconcile()

        self.assertEqual(len(result["unmatched"]), 1)
        self.assertEqual(result["unmatched"][0]["status"], "unmatched")
        self.assertIn("No matching contract", result["unmatched"][0]["reason"])

    def test_reconcile_vendor_match(self):
        """Test reconciliation by vendor name (without contract_id)"""
        contract = Contract(
            id="contract-1",
            vendor="AWS",
            monthly_amount=Decimal("1000.00"),
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=365)
        )

        invoice = Invoice(
            id="inv-1",
            vendor="aws",  # Lowercase - should still match
            amount=Decimal("1000.00"),
            date=datetime.now()
            # No contract_id - should match by vendor
        )

        self.reconciler.add_contract(contract)
        self.reconciler.add_invoice(invoice)

        result = self.reconciler.reconcile()

        self.assertEqual(len(result["matched"]), 1)

    def test_reconcile_summary(self):
        """Test reconciliation summary"""
        # Add matched invoice
        contract = Contract(
            id="contract-1",
            vendor="AWS",
            monthly_amount=Decimal("1000.00"),
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=365)
        )

        invoice1 = Invoice(
            id="inv-1",
            vendor="AWS",
            amount=Decimal("1000.00"),
            date=datetime.now(),
            contract_id="contract-1"
        )

        # Add unmatched invoice
        invoice2 = Invoice(
            id="inv-2",
            vendor="Unknown",
            amount=Decimal("500.00"),
            date=datetime.now()
        )

        self.reconciler.add_contract(contract)
        self.reconciler.add_invoice(invoice1)
        self.reconciler.add_invoice(invoice2)

        result = self.reconciler.reconcile()

        self.assertEqual(result["summary"]["total_invoices"], 2)
        self.assertEqual(result["summary"]["matched_count"], 1)
        self.assertEqual(result["summary"]["unmatched_count"], 1)


if __name__ == "__main__":
    unittest.main()
