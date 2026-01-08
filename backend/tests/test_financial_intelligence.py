import unittest
import os
import sys
from datetime import datetime, timedelta
sys.path.append(os.getcwd())

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers
from core.database import Base
import core.models
import ecommerce.models
import sales.models
import saas.models
import marketing.models
import accounting.models
import service_delivery.models
from core.models import Workspace
from accounting.models import Account, Transaction, AccountType, Bill, Invoice, BillStatus, InvoiceStatus
from core.cash_flow_forecaster import CashFlowForecastingService
from core.expense_optimizer import ExpenseOptimizer

class TestFinancialIntelligence(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace
        self.ws = Workspace(id="w_small_biz", name="Small Biz Inc")
        self.db.add(self.ws)
        
        # Setup Accounts
        self.acc_cash = Account(id="acc_cash", workspace_id="w_small_biz", name="Checking", code="1000", type=AccountType.ASSET)
        self.db.add(self.acc_cash)
        
        # Add historical burn (Transactions)
        # $15k per month burn
        for i in range(15):
             tx = Transaction(
                 workspace_id="w_small_biz", 
                 transaction_date=datetime.utcnow() - timedelta(days=5),
                 description=f"Expense {i}",
                 amount=-1000.0,
                 source="bank"
             )
             self.db.add(tx)
        
        # Add pending inflow (Open Invoices) - $50k
        inv = Invoice(
            id="inv_1", workspace_id="w_small_biz", customer_id="c_1", 
            amount=50000.0, status=InvoiceStatus.OPEN, 
            issue_date=datetime.utcnow(), due_date=datetime.utcnow()
        )
        self.db.add(inv)
        
        # Add pending outflow (Open Bills) - $5k
        bill = Bill(
            id="bill_1", workspace_id="w_small_biz", vendor_id="v_1",
            amount=5000.0, status=BillStatus.OPEN,
            issue_date=datetime.utcnow(), due_date=datetime.utcnow()
        )
        self.db.add(bill)
        
        self.db.commit()
        
        self.forecaster = CashFlowForecastingService(db_session=self.db)
        self.optimizer = ExpenseOptimizer(db_session=self.db)

    def tearDown(self):
        self.db.close()

    def test_runway_prediction(self):
        # Liquidity = Inflow (50k) - Outflow (5k) = 45k
        # Burn = 15k
        # Runway = 45k / 15k = 3.0 months
        prediction = self.forecaster.get_runway_prediction("w_small_biz")
        
        self.assertEqual(prediction["runway_months"], 3.0)
        self.assertEqual(prediction["risk_level"], "medium") # < 3 high, < 6 medium

    def test_scenario_simulation(self):
        # Base runway is 3.0
        # Add $10k recurring cost (Burn becomes 25k) -> Runway = 45 / 25 = 1.8
        simulation = self.forecaster.simulate_scenario("w_small_biz", monthly_cost_increase=10000.0)
        
        self.assertEqual(simulation["simulated_runway"], 1.8)

    def test_expense_optimization(self):
        # Add recurring AWS payments
        for i in range(5):
            tx = Transaction(
                workspace_id="w_small_biz",
                transaction_date=datetime.utcnow() - timedelta(days=i*30),
                description="AWS / Cloud Services",
                amount=-500.0,
                source="bank"
            )
            self.db.add(tx)
        self.db.commit()
        
        recommendations = self.optimizer.analyze_vendor_spend("w_small_biz")
        self.assertTrue(any("AWS" in r["vendor"] for r in recommendations))
        self.assertIn("reserved instances", recommendations[0]["recommendation"])

    def test_tax_deduction_identification(self):
        # Add "Team Dinner"
        tx = Transaction(
            workspace_id="w_small_biz",
            transaction_date=datetime.utcnow(),
            description="Dinner with Team @ Steakhouse",
            amount=-250.0,
            source="bank"
        )
        self.db.add(tx)
        self.db.commit()
        
        deductions = self.optimizer.identify_tax_deductions("w_small_biz")
        self.assertTrue(any("dinner" in d["reasoning"].lower() for d in deductions))

if __name__ == "__main__":
    unittest.main()
