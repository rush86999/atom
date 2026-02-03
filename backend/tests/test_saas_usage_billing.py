import os
import sys
import unittest

sys.path.append(os.getcwd())

from datetime import datetime, timedelta, timezone
import accounting.models
import ecommerce.models
import saas.models
import sales.models
import service_delivery.models
from accounting.margin_service import margin_calculator
from ecommerce.models import EcommerceCustomer, EcommerceOrder, EcommerceOrderItem, Subscription
from ecommerce.subscription_service import SubscriptionService
from saas.billing_engine import TieredBillingService
from saas.models import SaaSTier, UsageEvent
from saas.usage_service import UsageMeteringService
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.database import Base
from core.models import BusinessProductService, User, Workspace


class TestSaaSUsageAndTangibleBilling(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace
        self.ws = Workspace(id="w1", name="Mixed Business")
        self.db.add(self.ws)
        
        # 1. Setup Intangible (SaaS) Product
        self.tier = SaaSTier(
            id="tier_pro",
            workspace_id="w1",
            name="Pro Plan",
            base_price=100.0,
            included_api_calls=1000,
            overage_rate_api=0.01,
            pricing_config={
                "api_call": [
                    {"limit": 500, "rate": 0.01},  # First 500 overages at $0.01
                    {"limit": -1, "rate": 0.005}   # Rest at $0.005
                ]
            }
        )
        self.db.add(self.tier)
        
        # 2. Setup Tangible (Physical) Product
        self.physical_prod = BusinessProductService(
            id="p_t-shirt",
            workspace_id="w1",
            name="Atom T-Shirt",
            type="product",
            base_price=25.0,
            unit_cost=10.0, # COGS
            stock_quantity=100
        )
        self.db.add(self.physical_prod)
        
        # 3. Setup Customer
        self.customer = EcommerceCustomer(id="c1", workspace_id="w1", email="test@user.com")
        self.db.add(self.customer)
        
        # 4. Setup Subscription
        self.sub = Subscription(
            id="s1",
            workspace_id="w1",
            customer_id="c1",
            tier_id="tier_pro",
            mrr=100.0,
            status="active"
        )
        self.db.add(self.sub)
        
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_tiered_usage_billing(self):
        # Ingest 1600 API calls (1000 included, 600 overage)
        metering = UsageMeteringService(self.db)
        metering.ingest_event("s1", "api_call", 1600)
        
        # Calculate bill: 
        # Base: $100
        # Overage 600: First 500 * 0.01 = $5.00, Next 100 * 0.005 = $0.50
        # Total: $105.50
        billing = TieredBillingService(self.db)
        self.db.refresh(self.sub)
        result = billing.calculate_billable_amount(self.sub, self.sub.current_period_usage)
        
        self.assertEqual(result["total"], 105.50)
        self.assertEqual(len(result["breakdown"]), 2) # Base + 1 Overage item

    def test_renewal_generation_and_rollover(self):
        metering = UsageMeteringService(self.db)
        metering.ingest_event("s1", "api_call", 1200) # 200 overage * 0.01 = $2.00
        
        sub_service = SubscriptionService(self.db)
        order = sub_service.generate_renewal_order("s1")
        
        self.assertIsNotNone(order)
        self.assertEqual(order.total_price, 102.0)
        
        # Verify usage reset
        self.db.refresh(self.sub)
        self.assertEqual(self.sub.current_period_usage, {})

    def test_tangible_product_margin(self):
        # Create an order for 10 T-Shirts
        order = EcommerceOrder(
            id="o1",
            workspace_id="w1",
            customer_id="c1",
            total_price=250.0,
            status="paid"
        )
        self.db.add(order)
        
        item = EcommerceOrderItem(
            id="oi1",
            order_id="o1",
            product_id="p_t-shirt",
            title="Atom T-Shirt",
            quantity=10,
            price=25.0
        )
        self.db.add(item)
        self.db.commit()
        
        # Verify Margin: 
        # Revenue: $250
        # Cost: 10 * $10 = $100
        # Margin: $150 / 60%
        margins = margin_calculator.get_product_margins("w1", self.db)
        tshirt_margin = next(m for m in margins if m["product_id"] == "p_t-shirt")
        
        self.assertEqual(tshirt_margin["total_revenue"], 250.0)
        self.assertEqual(tshirt_margin["total_labor_cost"], 100.0) # Used 'total_labor_cost' field name but it represents COGS here
        self.assertEqual(tshirt_margin["gross_margin"], 150.0)
        self.assertEqual(tshirt_margin["margin_percentage"], 60.0)

if __name__ == "__main__":
    unittest.main()
