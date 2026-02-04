import datetime
import os
import sys
import unittest
import uuid
from datetime import timezone

# Add project root
sys.path.append(os.getcwd())

from accounting.models import Entity, EntityType, Invoice
from sales.models import Deal, DealStage
from service_delivery.billing_service import BillingService
from service_delivery.models import Contract, Milestone, MilestoneStatus, Project, ProjectStatus
from service_delivery.project_service import ProjectService

from core.database import SessionLocal
from core.models import Workspace


class TestPhase16ServiceDelivery(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.workspace_id = "default" # Assuming default workspace exists
        self.unique_id = uuid.uuid4().hex[:8]

    def tearDown(self):
        self.db.close()

    def test_end_to_end_delivery_flow(self):
        print("\n--- Phase 16: End-to-End Service Delivery Flow ---")
        
        # 1. Setup: Create a Closed Won Deal
        deal = Deal(
            workspace_id=self.workspace_id,
            name=f"Service Deal {self.unique_id}",
            value=10000.0,
            stage=DealStage.CLOSED_WON
        )
        self.db.add(deal)
        self.db.commit()
        print(f"✅ Created Closed Won Deal: {deal.name}")
        
        # 2. Provision Project (Automated Handover)
        project_service = ProjectService(self.db)
        project = project_service.provision_project_from_deal(deal.id)
        
        self.assertIsNotNone(project)
        self.assertEqual(project.status, ProjectStatus.PENDING)
        self.assertEqual(project.contract.total_amount, 10000.0)
        print(f"✅ Provisioned Project: {project.name} linked to Contract")
        
        # Verify Milestone was created
        self.db.refresh(project)
        self.assertTrue(len(project.milestones) > 0)
        kickoff_ms = project.milestones[0]
        print(f"✅ Default Milestone Created: {kickoff_ms.name}")
        
        # 3. Simulate Delivery: Approve Milestone
        kickoff_ms.status = MilestoneStatus.APPROVED
        self.db.commit()
        print(f"✅ Milestone Approved")
        
        # 4. Trigger Billing
        billing_service = BillingService(self.db)
        invoice = billing_service.generate_invoice_for_milestone(kickoff_ms.id)
        
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.amount, 5000.0) # 50% of 10k
        self.assertEqual(kickoff_ms.invoice_id, invoice.id)
        print(f"✅ Invoice Generated: {invoice.invoice_number} for ${invoice.amount}")

if __name__ == "__main__":
    unittest.main()
