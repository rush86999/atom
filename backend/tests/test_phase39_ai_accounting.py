import os
import sys
import unittest
from datetime import datetime

sys.path.append(os.getcwd())

from core.ai_accounting_engine import AIAccountingEngine, Transaction, TransactionSource


class TestPhase39AIAccounting(unittest.TestCase):

    def test_transaction_ingestion(self):
        print("\n--- Phase 39: Transaction Ingestion Test ---")
        
        engine = AIAccountingEngine()
        
        tx = Transaction(
            id="tx001",
            date=datetime.now(),
            amount=-150.00,
            description="Monthly Slack subscription",
            merchant="Slack Technologies"
        )
        
        result = engine.ingest_transaction(tx)
        
        self.assertEqual(result.id, "tx001")
        self.assertIsNotNone(result.category_name)
        self.assertGreater(result.confidence, 0)
        print(f"✅ Categorized as: {result.category_name} ({result.confidence:.0%})")
        print(f"   Reasoning: {result.reasoning}")

    def test_high_confidence_auto_categorization(self):
        print("\n--- Phase 39: High Confidence Auto-Categorization Test ---")
        
        engine = AIAccountingEngine()
        
        # Merchant pattern should give high confidence
        tx = Transaction(
            id="tx002",
            date=datetime.now(),
            amount=-99.00,
            description="GitHub Team subscription",
            merchant="GitHub"
        )
        
        result = engine.ingest_transaction(tx)
        
        self.assertEqual(result.category_name, "Software")
        self.assertGreaterEqual(result.confidence, 0.85)
        self.assertEqual(result.status.value, "categorized")
        print(f"✅ High confidence categorization: {result.confidence:.0%}")

    def test_low_confidence_review_queue(self):
        print("\n--- Phase 39: Low Confidence Review Queue Test ---")
        
        engine = AIAccountingEngine()
        
        # Unknown merchant should require review
        tx = Transaction(
            id="tx003",
            date=datetime.now(),
            amount=-500.00,
            description="Payment to XYZ Corp",
            merchant="XYZ Corp"
        )
        
        result = engine.ingest_transaction(tx)
        
        pending = engine.get_pending_review()
        self.assertEqual(len(pending), 1)
        print(f"✅ Low confidence transaction sent to review queue")

    def test_coa_learning(self):
        print("\n--- Phase 39: Chart of Accounts Learning Test ---")
        
        engine = AIAccountingEngine()
        
        # First transaction - unknown
        tx1 = Transaction(
            id="tx004",
            date=datetime.now(),
            amount=-200.00,
            description="Acme Corp payment",
            merchant="Acme Corp"
        )
        engine.ingest_transaction(tx1)
        
        # User categorizes it
        engine.learn_categorization("tx004", "6800", "user123")  # Professional Services
        
        # Second transaction from same merchant - should learn
        tx2 = Transaction(
            id="tx005",
            date=datetime.now(),
            amount=-300.00,
            description="Acme Corp consulting",
            merchant="Acme Corp"
        )
        result = engine.ingest_transaction(tx2)
        
        self.assertEqual(result.category_name, "Professional Services")
        self.assertGreater(result.confidence, 0.7)
        print(f"✅ Learned from user categorization: {result.category_name}")

    def test_audit_trail(self):
        print("\n--- Phase 39: Audit Trail Test ---")
        
        engine = AIAccountingEngine()
        
        tx = Transaction(
            id="tx006",
            date=datetime.now(),
            amount=-50.00,
            description="Test transaction"
        )
        engine.ingest_transaction(tx)
        
        audit = engine.get_audit_log("tx006")
        
        self.assertGreater(len(audit), 0)
        self.assertEqual(audit[0]["transaction_id"], "tx006")
        print(f"✅ Audit log has {len(audit)} entries for transaction")

if __name__ == "__main__":
    unittest.main()
