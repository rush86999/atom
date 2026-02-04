import os
import sys
import unittest

sys.path.append(os.getcwd())

from datetime import datetime, timedelta
import accounting.models
import ecommerce.models
import saas.models
import sales.models
import service_delivery.models
from accounting.margin_service import margin_calculator
from accounting.models import Account, AccountType, Entity, Invoice, InvoiceStatus
from service_delivery.models import Contract, Project, ProjectStatus, ProjectTask
from service_delivery.project_service import ProjectService
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.database import Base
from core.models import Team, User, Workspace


class TestMarginIntelligence(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace
        self.ws = Workspace(id="w1", name="Test Business")
        self.db.add(self.ws)
        
        # Setup System User for notifications
        self.system_user = User(id="system", email="system@atom.ai", first_name="System", last_name="User")
        self.db.add(self.system_user)
        
        # Setup Team
        self.team = Team(id="t1", name="Engineering", workspace_id="w1")
        self.db.add(self.team)
        
        # Setup User with labor cost
        self.worker = User(id="u1", email="worker@test.com", first_name="Dev", hourly_cost_rate=50.0)
        self.db.add(self.worker)
        
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_margin_calculations(self):
        # 1. Setup Project & Contract
        contract = Contract(id="c1", workspace_id="w1", name="Big Deal", total_amount=10000.0)
        self.db.add(contract)
        
        project = Project(
            id="p1", 
            workspace_id="w1", 
            contract_id="c1", 
            name="Implementation", 
            budget_amount=10000.0,
            status=ProjectStatus.ACTIVE
        )
        self.db.add(project)
        self.db.commit()

        # 2. Add Tasks with actual hours
        t1 = ProjectTask(
            id="tk1", 
            workspace_id="w1", 
            project_id="p1", 
            milestone_id="m1", # Dummy
            name="Design", 
            assigned_to="u1", 
            actual_hours=40.0,
            metadata_json={}
        )
        t2 = ProjectTask(
            id="tk2", 
            workspace_id="w1", 
            project_id="p1", 
            milestone_id="m1", 
            name="Build", 
            assigned_to="u1", 
            actual_hours=60.0,
            metadata_json={}
        )
        self.db.add_all([t1, t2])
        self.db.commit()

        # 3. Verify Labor Cost (100 hours * $50 = $5000)
        labor_cost = margin_calculator.calculate_project_labor_cost("p1", self.db)
        self.assertEqual(labor_cost, 5000.0)

        # 4. Verify Margin (Revenue $10,000 - Cost $5,000 = $5,000 / 50%)
        margin_data = margin_calculator.get_project_margin("p1", self.db)
        self.assertEqual(margin_data["gross_margin"], 5000.0)
        self.assertEqual(margin_data["margin_percentage"], 50.0)

    def test_delivery_gating_with_overdue_invoice(self):
        # 1. Setup Contract linked to a customer
        contract = Contract(id="c2", workspace_id="w1", name="Service for ACME Corp", total_amount=5000.0)
        self.db.add(contract)
        
        project = Project(
            id="p2", 
            workspace_id="w1", 
            contract_id="c2", 
            name="ACME Project", 
            status=ProjectStatus.ACTIVE
        )
        self.db.add(project)
        
        # 2. Setup Customer and OVERDUE invoice
        customer = Entity(id="e1", workspace_id="w1", name="ACME Corp", type="customer")
        self.db.add(customer)
        
        invoice = Invoice(
            id="inv1", 
            workspace_id="w1", 
            customer_id="e1", 
            amount=2000.0, 
            status=InvoiceStatus.OVERDUE,
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() - timedelta(days=10)
        )
        self.db.add(invoice)
        self.db.commit()

        # 3. Trigger Delivery Gating
        service = ProjectService(self.db)
        service.check_delivery_gating("p2")
        
        # 4. Verify Project status is PAUSED_PAYMENT
        self.db.refresh(project)
        self.assertEqual(project.status, ProjectStatus.PAUSED_PAYMENT)
        self.assertIn("Customer has 1 overdue invoices", project.metadata_json["pause_reason"])

        # 5. Verify TeamMessage notification
        from core.models import TeamMessage
        msg = self.db.query(TeamMessage).filter(TeamMessage.context_id == "p2").first()
        self.assertIsNotNone(msg)
        self.assertIn("🚨 FINANCIAL GATING", msg.content)

if __name__ == "__main__":
    unittest.main()
