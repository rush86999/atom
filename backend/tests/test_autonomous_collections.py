import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

import accounting.models
import ecommerce.models
import marketing.models
import saas.models
import sales.models
import service_delivery.models
from accounting.models import Entity, EntityType, Invoice, InvoiceStatus
from ecommerce.models import EcommerceCustomer, EcommerceOrder
from service_delivery.models import Appointment, AppointmentStatus
from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers, sessionmaker

import core.models
from core.auto_invoicer import AutoInvoicer
from core.collection_agent import CollectionAgent
from core.database import Base
from core.models import Workspace


class MockIntelService:
    def __init__(self, db_session):
        self.recorded_calls = []

    async def analyze_and_route(self, data, source):
        self.recorded_calls.append({"data": data, "source": source})
        return {"status": "success"}

class TestAutonomousCollections(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        configure_mappers()
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()
        
        # Setup Workspace
        self.ws = Workspace(id="w_multi", name="Multi Biz")
        self.db.add(self.ws)
        
        # Setup Entity
        self.entity = Entity(
            id="e_bob", workspace_id="w_multi", name="Bob Client", 
            email="bob@example.com", type=EntityType.BOTH
        )
        self.db.add(self.entity)
        
        self.db.commit()
        
        self.invoicer = AutoInvoicer(db_session=self.db)
        self.intel = MockIntelService(self.db)
        self.collector = CollectionAgent(db_session=self.db, intel_service=self.intel)

    def tearDown(self):
        self.db.close()

    def test_instant_service_invoicing(self):
        # Create COMPLETED appointment
        appt = Appointment(
            id="a_done", workspace_id="w_multi", customer_id="e_bob",
            start_time=datetime.utcnow(), end_time=datetime.utcnow(),
            status=AppointmentStatus.COMPLETED, deposit_amount=150.0
        )
        self.db.add(appt)
        self.db.commit()
        
        self.invoicer.invoice_appointment("a_done")
        
        # Verify invoice exists
        invoice = self.db.query(Invoice).filter(Invoice.customer_id == "e_bob").first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.amount, 150.0)
        self.assertIn("Appointment a_done", invoice.description)

    def test_instant_product_invoicing(self):
        # Setup Ecommerce
        cust = EcommerceCustomer(id="ec_bob", workspace_id="w_multi", email="bob@example.com", accounting_entity_id="e_bob")
        self.db.add(cust)
        self.db.commit()
        
        order = EcommerceOrder(
            id="o_unpaid", workspace_id="w_multi", customer_id="ec_bob",
            total_price=299.99, status="pending"
        )
        self.db.add(order)
        self.db.commit()
        
        self.invoicer.invoice_ecommerce_order("o_unpaid")
        
        invoice = self.db.query(Invoice).filter(Invoice.amount == 299.99).first()
        self.assertIsNotNone(invoice)
        self.assertIn("Order o_unpaid", invoice.description)
        self.assertIn("Status: pending", invoice.description)

    def test_product_invoicing_on_fulfillment(self):
        # Create a fulfilled (shipped) order
        cust = EcommerceCustomer(id="ec_shipped", workspace_id="w_multi", email="shipped@example.com", accounting_entity_id="e_bob")
        self.db.add(cust)
        self.db.commit()
        
        order = EcommerceOrder(
            id="o_shipped", workspace_id="w_multi", customer_id="ec_shipped",
            total_price=500.0, status="fulfilled"
        )
        self.db.add(order)
        self.db.commit()
        
        self.invoicer.invoice_ecommerce_order("o_shipped")
        
        invoice = self.db.query(Invoice).filter(Invoice.amount == 500.0).first()
        self.assertIsNotNone(invoice)
        self.assertIn("Order o_shipped", invoice.description)
        self.assertIn("Status: fulfilled", invoice.description)

    def test_collection_escalation_sequence(self):
        # 1. Friendly (2 days overdue)
        inv1 = Invoice(
            workspace_id="w_multi", customer_id="e_bob", amount=100.0,
            status=InvoiceStatus.OPEN, issue_date=datetime.utcnow() - timedelta(days=10),
            due_date=datetime.utcnow() - timedelta(days=2),
            description="Late Inv 1"
        )
        # 2. Firm (10 days overdue)
        inv2 = Invoice(
            workspace_id="w_multi", customer_id="e_bob", amount=200.0,
            status=InvoiceStatus.OPEN, issue_date=datetime.utcnow() - timedelta(days=20),
            due_date=datetime.utcnow() - timedelta(days=10),
            description="Late Inv 2"
        )
        # 3. Final (20 days overdue)
        inv3 = Invoice(
            workspace_id="w_multi", customer_id="e_bob", amount=300.0,
            status=InvoiceStatus.OPEN, issue_date=datetime.utcnow() - timedelta(days=30),
            due_date=datetime.utcnow() - timedelta(days=20),
            description="Late Inv 3"
        )
        self.db.add_all([inv1, inv2, inv3])
        self.db.commit()
        
        loop = asyncio.get_event_loop()
        actions = loop.run_until_complete(self.collector.scan_and_collect("w_multi"))
        
        self.assertEqual(len(actions), 3)
        intents = [a["intent"] for a in actions]
        self.assertIn("FRIENDLY_NUDGE", intents)
        self.assertIn("FIRM_REMINDER", intents)
        self.assertIn("FINAL_NOTICE", intents)
        
        self.assertEqual(len(self.intel.recorded_calls), 3)

if __name__ == "__main__":
    unittest.main()
