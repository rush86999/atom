import datetime
import os
import sys
import unittest
import uuid
from datetime import timezone

# Add project root
sys.path.append(os.getcwd())

from ecommerce.models import EcommerceCustomer, Subscription
from saas.billing_engine import TieredBillingService
from saas.churn_detector import ChurnRiskDetector
from saas.models import SaaSTier, UsageEvent
from saas.usage_service import UsageMeteringService

from core.database import SessionLocal
from core.models import Workspace


class TestPhase17SaaS(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.workspace_id = "default"
        self.unique_id = uuid.uuid4().hex[:8]

    def tearDown(self):
        self.db.close()

    def test_saas_intelligence_flow(self):
        print("\n--- Phase 17: SaaS Intelligence Flow ---")
        
        # 1. Setup Tier
        tier = SaaSTier(
            workspace_id=self.workspace_id,
            name="Pro Plan",
            base_price=100.0,
            included_api_calls=100,
            overage_rate_api=0.50
        )
        self.db.add(tier)
        self.db.flush()
        
        # 2. Setup Subscription
        # Need a customer first
        customer = EcommerceCustomer(
            workspace_id=self.workspace_id, 
            email=f"saas_user_{self.unique_id}@test.com"
        )
        self.db.add(customer)
        self.db.flush()
        
        sub = Subscription(
            workspace_id=self.workspace_id,
            customer_id=customer.id,
            tier_id=tier.id,
            status="active"
        )
        self.db.add(sub)
        self.db.commit()
        print(f"✅ Created Subscription on {tier.name}")
        
        # 3. Usage Metering
        usage_service = UsageMeteringService(self.db)
        # Ingest 150 calls (50 overage)
        usage_service.ingest_event(sub.id, "api_call", 150)
        
        self.db.refresh(sub)
        # Verify Cache
        self.assertEqual(sub.current_period_usage.get("api_call"), 150)
        print("✅ Usage Ingested and Cached: 150 calls")
        
        # 4. Tiered Billing
        billing_engine = TieredBillingService(self.db)
        # Helper to get usage dict from cache or agg
        usage_data = sub.current_period_usage
        
        bill = billing_engine.calculate_billable_amount(sub, usage_data)
        
        # Expect: 100 Base + (50 * 0.50) = 125.0
        self.assertEqual(bill["total"], 125.0)
        self.assertTrue(any(i["amount"] == 25.0 for i in bill["breakdown"]))
        print(f"✅ Calculated Bill: ${bill['total']} (Expected $125.00)")
        
        # 5. Churn Detection
        churn_detector = ChurnRiskDetector()
        current_usage = {"api_call": 10} # Big drop from 150
        previous_usage = {"api_call": 150}
        
        risk = churn_detector.analyze_usage_trend(current_usage, previous_usage)
        self.assertEqual(risk["risk_level"], "high")
        print(f"✅ Churn Risk Detected: {risk['reason']}")

if __name__ == "__main__":
    unittest.main()
