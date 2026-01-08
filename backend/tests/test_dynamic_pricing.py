import unittest
import os
import sys
from datetime import datetime, timezone
sys.path.append(os.getcwd())

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers
from core.database import Base
import core.models
import ecommerce.models
import saas.models
import sales.models
import accounting.models
import service_delivery.models
import marketing.models
from core.models import Workspace, BusinessProductService
from ecommerce.models import EcommerceCustomer
from ecommerce.dynamic_pricing import DynamicPricingService
from ecommerce.discount_optimizer import DiscountOptimizer

class TestDynamicPricingAndDiscounts(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace
        self.ws = Workspace(id="w1", name="Dynamic Corp")
        self.db.add(self.ws)
        
        # Setup Products
        self.p_scarcity = BusinessProductService(
            id="p1", workspace_id="w1", name="Scarce Widget", base_price=100.0,
            stock_quantity=5, unit_cost=50.0 # < 10 stock
        )
        self.p_liquidation = BusinessProductService(
            id="p2", workspace_id="w1", name="Excess Widget", base_price=100.0,
            stock_quantity=200, unit_cost=50.0 # > 100 stock
        )
        self.p_competitor = BusinessProductService(
            id="p3", workspace_id="w1", name="Competitive Widget", base_price=100.0,
            stock_quantity=50, unit_cost=50.0,
            metadata_json={"competitor_price": 90.0} # Target: 90 * 0.98 = 88.2
        )
        self.db.add_all([self.p_scarcity, self.p_liquidation, self.p_competitor])
        
        # Setup Customers
        self.c_high_risk = EcommerceCustomer(id="c_high", workspace_id="w1", email="high@risk.com", risk_score=85.0)
        self.c_loyal = EcommerceCustomer(id="c_loyal", workspace_id="w1", email="loyal@test.com", risk_score=5.0)
        self.db.add_all([self.c_high_risk, self.c_loyal])
        
        self.db.commit()
        self.pricing_service = DynamicPricingService(self.db)
        self.discount_optimizer = DiscountOptimizer(self.db)

    def tearDown(self):
        self.db.close()

    def test_dynamic_pricing_scarcity(self):
        price = self.pricing_service.get_adjusted_price("p1")
        self.assertEqual(price, 115.0) # 100 * 1.15

    def test_dynamic_pricing_liquidation(self):
        price = self.pricing_service.get_adjusted_price("p2")
        self.assertEqual(price, 90.0) # 100 * 0.90

    def test_dynamic_pricing_competitor(self):
        price = self.pricing_service.get_adjusted_price("p3")
        self.assertEqual(price, 88.2) # 90 * 0.98

    def test_discount_high_risk(self):
        # High risk (> 70) should get 0% discount
        discount = self.discount_optimizer.get_optimal_discount("c_high", 1000.0)
        self.assertEqual(discount, 0.0)

    def test_discount_volume_and_loyalty(self):
        # Base total 2000 => 10% discount
        # Risk score 5 => +2% loyalty
        # Total = 12%
        discount = self.discount_optimizer.get_optimal_discount("c_loyal", 2000.0)
        self.assertEqual(discount, 0.12)

    def test_discount_margin_floor(self):
        # Base total 1000 => 10% discount = 100. Total = 900.
        # But if margin floor is 950...
        discount = self.discount_optimizer.get_optimal_discount("c_loyal", 1000.0, margin_floor=950.0)
        # Available discount is 1000 - 950 = 50. 50/1000 = 0.05
        self.assertEqual(discount, 0.05)

if __name__ == "__main__":
    unittest.main()
