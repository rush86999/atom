import asyncio
import unittest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch
import accounting.models
import sales.models
import service_delivery.models
from accounting.models import Entity, EntityType, Invoice, InvoiceStatus
from service_delivery.models import Contract, ContractType, Milestone, MilestoneStatus, Project
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.billing_orchestrator import BillingOrchestrator

# Import models
from core.database import Base


class TestMilestoneBilling(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Setup in-memory SQLite for testing
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        self.workspace_id = "test_ws_billing"
        
        # Patch SessionLocal
        self.patcher_db = patch("core.billing_orchestrator.SessionLocal", return_value=self.db)
        self.patcher_db.start()
        
        self.billing_orch = BillingOrchestrator()

    async def asyncTearDown(self):
        self.db.close()
        self.patcher_db.stop()

    async def test_percentage_billing(self):
        # 1. Setup Contract ($100,000)
        contract = Contract(
            id="cnt_test_1",
            workspace_id=self.workspace_id,
            name="Test Enterprise Contract",
            total_amount=100000.0,
            currency="USD",
            type=ContractType.FIXED_FEE
        )
        self.db.add(contract)
        
        # 2. Setup Project
        project = Project(
            id="proj_test_1",
            workspace_id=self.workspace_id,
            contract_id=contract.id,
            name="Billing Test Project"
        )
        self.db.add(project)
        
        # 3. Setup Milestone (25%)
        milestone = Milestone(
            id="ms_test_1",
            workspace_id=self.workspace_id,
            project_id=project.id,
            name="Phase 1: Kickoff",
            percentage=25.0, # Should be $25,000
            status=MilestoneStatus.COMPLETED
        )
        self.db.add(milestone)
        self.db.commit()
        
        m_id = milestone.id
        
        # 4. Execute Billing
        result = await self.billing_orch.process_milestone_completion(m_id, self.workspace_id)
        
        # 5. Verify Results
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["amount"], 25000.0)
        
        # Use a fresh session for verification to avoid DetachedInstanceError
        with self.SessionLocal() as verify_db:
            # Check DB for Invoice
            invoice = verify_db.query(Invoice).filter(Invoice.id == result["invoice_id"]).first()
            self.assertIsNotNone(invoice)
            self.assertEqual(invoice.amount, 25000.0)
            self.assertEqual(invoice.status, InvoiceStatus.DRAFT)
            
            # Check Milestone is updated
            db_milestone = verify_db.query(Milestone).filter(Milestone.id == m_id).first()
            self.assertEqual(db_milestone.status, MilestoneStatus.INVOICED)
            self.assertEqual(db_milestone.invoice_id, invoice.id)
            
            # Check Entity (Customer) was created
            entity = verify_db.query(Entity).filter(Entity.id == invoice.customer_id).first()
            self.assertIsNotNone(entity)
            self.assertEqual(entity.type, EntityType.CUSTOMER)

    async def test_fixed_amount_billing(self):
        # 1. Setup Contract
        contract = Contract(id="cnt_test_2", workspace_id=self.workspace_id, name="Fixed Fee Contract", total_amount=10000)
        self.db.add(contract)
        
        # 2. Project
        project = Project(id="proj_test_2", workspace_id=self.workspace_id, contract_id=contract.id, name="P2")
        self.db.add(project)
        
        # 3. Milestone ($1,500 fixed)
        milestone = Milestone(
            id="ms_test_2",
            workspace_id=self.workspace_id,
            project_id=project.id,
            name="Hardware Setup",
            amount=1500.0,
            status=MilestoneStatus.COMPLETED
        )
        self.db.add(milestone)
        self.db.commit()
        
        m_id = milestone.id
        
        # 4. Execute
        result = await self.billing_orch.process_milestone_completion(m_id, self.workspace_id)
        
        # 5. Verify
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["amount"], 1500.0)
        
        with self.SessionLocal() as verify_db:
            invoice = verify_db.query(Invoice).filter(Invoice.id == result["invoice_id"]).first()
            self.assertIsNotNone(invoice)
            self.assertEqual(invoice.amount, 1500.0)
        
        print("\n[SUCCESS] Milestone Billing Verified (Percentage & Fixed).")

if __name__ == "__main__":
    unittest.main()
