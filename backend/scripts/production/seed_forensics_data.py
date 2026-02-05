from datetime import datetime, timedelta
import os
import sys
import uuid

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from accounting.models import Bill, BillStatus, Entity, EntityType, Transaction, TransactionStatus
from ecommerce.models import EcommerceCustomer, EcommerceOrder, EcommerceOrderItem, Subscription
from marketing.models import ChannelType, MarketingChannel
from saas.models import SaaSTier
from sales.models import Deal, Lead
from service_delivery.models import Contract, Milestone, Project

from core.database import SessionLocal, engine
from core.models import AgentJob, Workspace


def seed_forensics():
    workspace_id = "default-workspace"

    with SessionLocal() as db:
        # 1. Ensure workspace exists
        ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not ws:
            # Use raw SQL for Workspace to avoid matches on learning_phase_completed if column missing
            from sqlalchemy import text
            db.execute(text("INSERT INTO workspaces (id, name, status) VALUES (:id, :name, :status)"),
                       {"id": workspace_id, "name": "Forensics Demo", "status": "active"})
            db.commit()

        # 2. Vendor Price Drift
        vendor = Entity(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            name="Global Logistics Inc",
            type=EntityType.VENDOR
        )
        db.add(vendor)
        db.flush()

        # Historical bills (avg $1000)
        for i in range(5):
            bill = Bill(
                workspace_id=workspace_id,
                vendor_id=vendor.id,
                amount=1000.0,
                issue_date=datetime.now() - timedelta(days=30 * (i + 2)),
                due_date=datetime.now() - timedelta(days=30 * (i + 1)),
                status=BillStatus.PAID
            )
            db.add(bill)

        # Recent drifted bill ($1200 -> 20% drift)
        drifted_bill = Bill(
            workspace_id=workspace_id,
            vendor_id=vendor.id,
            amount=1200.0,
            issue_date=datetime.now() - timedelta(days=5),
            due_date=datetime.now() + timedelta(days=25),
            status=BillStatus.OPEN,
            description="Monthly Shipping - Surcharge applied"
        )
        db.add(drifted_bill)

        # 3. Underpricing
        customer = EcommerceCustomer(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            email="owner@theshop.com",
            first_name="Store",
            last_name="Owner"
        )
        db.add(customer)
        db.flush()

        order = EcommerceOrder(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            customer_id=customer.id,
            total_price=45.0,
            status="paid"
        )
        db.add(order)
        db.flush()

        item = EcommerceOrderItem(
            id=str(uuid.uuid4()),
            order_id=order.id,
            sku="WIDGET-001",
            title="Eco-Friendly Widget",
            price=45.0,
            quantity=1
        )
        db.add(item)

        # 4. Subscription Waste (Zombie)
        sub = Subscription(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            customer_id=customer.id,
            plan_name="Project Management Pro",
            mrr=99.0,
            status="canceled",
            canceled_at=datetime.now() - timedelta(days=10)
        )
        db.add(sub)
        db.flush()

        # Recent transaction for this canceled sub
        tx = Transaction(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            source="bank_feed",
            status=TransactionStatus.POSTED,
            transaction_date=datetime.now() - timedelta(days=2),
            description="Project Management Pro Periodic",
            amount=99.0
        )
        db.add(tx)

        db.commit()
        print("✅ Forensics test data seeded successfully.")

if __name__ == "__main__":
    seed_forensics()
