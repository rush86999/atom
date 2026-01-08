import sys
import os
import unittest
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from core.financial_ops_engine import (
    CostLeakDetector, SaaSSubscription,
    BudgetGuardrails, BudgetLimit,
    InvoiceReconciler, Invoice, Contract
)

class TestPhase37FinancialOps(unittest.TestCase):

    def test_cost_leak_detection(self):
        print("\n--- Phase 37: Cost Leak Detection Test ---")
        
        detector = CostLeakDetector(unused_threshold_days=30)
        
        # Add subscriptions
        detector.add_subscription(SaaSSubscription(
            id="slack", name="Slack", monthly_cost=50.0,
            last_used=datetime.now(), user_count=10, active_users=8, category="communication"
        ))
        detector.add_subscription(SaaSSubscription(
            id="old-tool", name="Old Tool", monthly_cost=100.0,
            last_used=datetime.now() - timedelta(days=60), user_count=5, active_users=0, category="analytics"
        ))
        detector.add_subscription(SaaSSubscription(
            id="teams", name="MS Teams", monthly_cost=40.0,
            last_used=datetime.now(), user_count=10, active_users=5, category="communication"
        ))
        
        report = detector.get_savings_report()
        
        self.assertEqual(len(report["unused_subscriptions"]), 1)
        self.assertEqual(report["unused_subscriptions"][0]["name"], "Old Tool")
        self.assertEqual(len(report["redundant_tools"]), 1)  # 2 in communication
        print(f"✅ Detected 1 unused, 1 redundant category")
        print(f"   Potential savings: ${report['potential_monthly_savings']}/month")

    def test_budget_guardrails(self):
        print("\n--- Phase 37: Budget Guardrails Test ---")
        
        guardrails = BudgetGuardrails()
        
        guardrails.set_limit(BudgetLimit(
            category="marketing",
            monthly_limit=5000.0,
            deal_stage_required="closed_won"
        ))
        
        # Should reject - wrong deal stage
        result = guardrails.check_spend("marketing", 500, deal_stage="negotiation")
        self.assertEqual(result["status"], "rejected")
        
        # Should approve - correct deal stage
        result = guardrails.check_spend("marketing", 500, deal_stage="closed_won")
        self.assertEqual(result["status"], "approved")
        
        # Should pause - exceeds limit
        result = guardrails.check_spend("marketing", 6000, deal_stage="closed_won")
        self.assertEqual(result["status"], "paused")
        
        print("✅ Budget guardrails work correctly")

    def test_invoice_reconciliation(self):
        print("\n--- Phase 37: Invoice Reconciliation Test ---")
        
        reconciler = InvoiceReconciler(tolerance_percent=5.0)
        
        # Add contract
        reconciler.add_contract(Contract(
            id="c1", vendor="AWS",
            monthly_amount=1000.0,
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now() + timedelta(days=335)
        ))
        
        # Matching invoice
        reconciler.add_invoice(Invoice(
            id="inv1", vendor="AWS", amount=1000.0,
            date=datetime.now(), contract_id="c1"
        ))
        
        # Discrepancy invoice (20% off)
        reconciler.add_invoice(Invoice(
            id="inv2", vendor="AWS", amount=1200.0,
            date=datetime.now(), contract_id="c1"
        ))
        
        result = reconciler.reconcile()
        
        self.assertEqual(result["summary"]["matched_count"], 1)
        self.assertEqual(result["summary"]["discrepancy_count"], 1)
        print(f"✅ Reconciliation: {result['summary']['matched_count']} matched, {result['summary']['discrepancy_count']} discrepancies")

if __name__ == "__main__":
    unittest.main()
