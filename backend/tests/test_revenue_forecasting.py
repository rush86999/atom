import unittest
import asyncio
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, configure_mappers
from datetime import datetime, timedelta
import uuid
import json

import os
import sys
sys.path.append(os.getcwd())

# Import models
from core.database import Base
import core.models
import service_delivery.models
import sales.models
import accounting.models
from core.models import User, Workspace, BusinessProductService, user_workspaces
from service_delivery.models import Contract, Project, Milestone, MilestoneStatus
from accounting.models import Account, AccountType, Transaction, JournalEntry, EntryType
from accounting.revenue_recognition import revenue_recognition_service
from accounting.fpa_service import FPAService
from accounting.seeds import seed_default_accounts

class TestRevenueForecasting(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Setup in-memory SQLite
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Patch SessionLocal for service
        self.patcher_db = patch("accounting.revenue_recognition.SessionLocal", return_value=self.db)
        self.patch_rr = self.patcher_db.start()
        
        # Prevent service from closing the test's main session
        self.original_close = self.db.close
        self.db.close = MagicMock()

        # 1. Setup Businesses (Workspaces)
        self.ws1 = Workspace(id="biz_a", name="Business A")
        self.ws2 = Workspace(id="biz_b", name="Business B")
        self.db.add_all([self.ws1, self.ws2])
        self.db.commit()

        # 2. Setup User in Multiple Businesses
        self.user = User(id="u1", email="owner@test.com", first_name="Owner")
        self.db.add(self.user)
        self.db.commit()
        
        # Associate user with both businesses
        self.db.execute(user_workspaces.insert().values(user_id="u1", workspace_id="biz_a", role="owner"))
        self.db.execute(user_workspaces.insert().values(user_id="u1", workspace_id="biz_b", role="owner"))
        self.db.commit()

        # 3. Setup Chart of Accounts
        seed_default_accounts(self.db, "biz_a")
        seed_default_accounts(self.db, "biz_b")

        # 4. Setup Products/Services
        self.prod_a = BusinessProductService(
            workspace_id="biz_a",
            name="Cloud Consulting",
            type="service",
            base_price=10000.0
        )
        self.db.add(self.prod_a)
        self.db.commit()

    async def asyncTearDown(self):
        self.patcher_db.stop()
        self.db.close()

    async def test_multi_business_access(self):
        # Verify user has access to both workspaces
        user = self.db.query(User).filter(User.id == "u1").first()
        self.assertEqual(len(user.workspaces), 2)
        workspace_ids = [ws.id for ws in user.workspaces]
        self.assertIn("biz_a", workspace_ids)
        self.assertIn("biz_b", workspace_ids)

    async def test_revenue_recognition_with_product(self):
        # Setup Contract -> Project -> Milestone
        contract = Contract(
            workspace_id="biz_a",
            name="Engagement Alpha",
            product_service_id=self.prod_a.id,
            total_amount=50000.0
        )
        self.db.add(contract)
        self.db.flush()

        project = Project(
            workspace_id="biz_a",
            contract_id=contract.id,
            name="Software Build"
        )
        self.db.add(project)
        self.db.flush()

        milestone = Milestone(
            workspace_id="biz_a",
            project_id=project.id,
            name="MVP Implementation",
            amount=20000.0,
            status=MilestoneStatus.PENDING
        )
        self.db.add(milestone)
        self.db.commit()

        # Run Revenue Recognition
        res = await revenue_recognition_service.record_revenue_recognition(milestone.id)
        
        if res.get("status") == "error":
            print(f"DEBUG REVENUE ERROR: {res.get('message')}")
            
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["product"], "Cloud Consulting")
        self.assertEqual(res["amount"], 20000.0)

        # Verify Ledger Entries
        tx = self.db.query(Transaction).filter(Transaction.id == res["transaction_id"]).first()
        self.assertEqual(tx.metadata_json["product_service_id"], self.prod_a.id)
        
        # Deferred Revenue (2100) should be Debited (Liability down)
        # Sales Revenue (4000) should be Credited (Revenue up)
        entries = tx.journal_entries
        self.assertEqual(len(entries), 2)
        
        rev_entry = [e for e in entries if e.account.code == "4000"][0]
        def_entry = [e for e in entries if e.account.code == "2100"][0]
        
        self.assertEqual(rev_entry.type, EntryType.CREDIT)
        self.assertEqual(rev_entry.amount, 20000.0)
        self.assertEqual(def_entry.type, EntryType.DEBIT)
        self.assertEqual(def_entry.amount, 20000.0)

    async def test_financial_forecasting_with_unbilled_milestones(self):
        fpa = FPAService(self.db)
        
        # Initial Forecast (should be zero or based on previous test tx if not cleared)
        # We'll use biz_b which is clean
        forecast_empty = fpa.get_13_week_forecast("biz_b")
        total_contracted_empty = sum(item["details"]["contracted_revenue"] for item in forecast_empty)
        self.assertEqual(total_contracted_empty, 0.0)

        # Setup unbilled milestone in biz_b for 4 weeks from now
        future_date = datetime.utcnow() + timedelta(weeks=4)
        contract = Contract(workspace_id="biz_b", name="Future Deal", total_amount=10000.0)
        self.db.add(contract)
        self.db.flush()
        
        project = Project(workspace_id="biz_b", contract_id=contract.id, name="Future Proj")
        self.db.add(project)
        self.db.flush()
        
        m1 = Milestone(
            workspace_id="biz_b",
            project_id=project.id,
            name="Phase 1",
            amount=5000.0,
            due_date=future_date,
            status=MilestoneStatus.PENDING
        )
        self.db.add(m1)
        self.db.commit()

        # Run Forecast
        forecast = fpa.get_13_week_forecast("biz_b")
        
        # Verify week 4 (index 3 or 4 depending on math) has the contracted revenue
        found = False
        for item in forecast:
            if item["details"]["contracted_revenue"] == 5000.0:
                found = True
                break
        
        self.assertTrue(found, "Unbilled milestone not found in forecast")
        
        # Test Product Filtering
        # Add another product and milestone
        prod_alt = BusinessProductService(workspace_id="biz_b", name="Alternative Prod", type="product")
        self.db.add(prod_alt)
        self.db.flush()
        
        contract2 = Contract(workspace_id="biz_b", name="Alt Contract", product_service_id=prod_alt.id)
        self.db.add(contract2)
        self.db.flush()
        project2 = Project(workspace_id="biz_b", contract_id=contract2.id, name="Alt Proj")
        self.db.add(project2)
        self.db.flush()
        m2 = Milestone(
            workspace_id="biz_b",
            project_id=project2.id,
            name="Alt Milestone",
            amount=777.0,
            due_date=future_date,
            status=MilestoneStatus.PENDING
        )
        self.db.add(m2)
        self.db.commit()

        # Forecast for prod_alt only
        forecast_filtered = fpa.get_13_week_forecast("biz_b", product_service_id=prod_alt.id)
        total_contracted_filtered = sum(item["details"]["contracted_revenue"] for item in forecast_filtered)
        self.assertEqual(total_contracted_filtered, 777.0)

        print("\n[SUCCESS] Phase 48 Verified (Multi-Business, Rev Rec, Forecasting).")

if __name__ == "__main__":
    unittest.main()
