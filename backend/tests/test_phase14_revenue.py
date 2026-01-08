import sys
import os
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from core.database import SessionLocal
from core.models import Workspace
from sales.models import Deal, DealStage, CommissionStatus
from accounting.models import Invoice, InvoiceStatus, Entity, EntityType
from ecommerce.models import EcommerceCustomer
from ecommerce.subscription_service import SubscriptionService
from sales.commission_service import CommissionService
from accounting.credit_risk_engine import CreditRiskEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_phase14_flow():
    db = SessionLocal()
    unique_id = uuid.uuid4().hex[:8]
    workspace_id = "default"
    
    try:
        print(f"\n--- Phase 1: Subscription & MRR Verification ---")
        sub_service = SubscriptionService(db)
        
        # 1. Create Customer
        cust = EcommerceCustomer(
            workspace_id=workspace_id,
            email=f"sub_user_{unique_id}@example.com",
            first_name="Sub",
            last_name="Scriber"
        )
        db.add(cust)
        db.flush()
        
        # 2. Create Subscription
        sub = sub_service.create_or_update_subscription(
            workspace_id=workspace_id,
            customer_id=cust.id,
            external_id=f"sub_ext_{unique_id}",
            plan_name="Pro Plan",
            price=100.0,
            interval="month"
        )
        
        assert sub.mrr == 100.0
        assert sub.status == "active"
        print("✅ Subscription created correctly with MRR 100.0")
        
        # 3. Upgrade Subscription
        sub = sub_service.create_or_update_subscription(
            workspace_id=workspace_id,
            customer_id=cust.id,
            external_id=f"sub_ext_{unique_id}",
            plan_name="Enterprise Plan",
            price=2000.0,
            interval="year"
        )
        # 2000 / 12 = 166.66
        assert abs(sub.mrr - 166.66) < 0.1
        print("✅ Subscription upgrade correctly recalculated MRR")

        print(f"\n--- Phase 2: Commission Logic Verification ---")
        comm_service = CommissionService(db)
        
        # 1. Create Deal & Entity
        deal = Deal(workspace_id=workspace_id, name=f"Big Deal {unique_id}", value=5000.0, stage=DealStage.CLOSED_WON)
        db.add(deal)
        db.flush() # Generate ID
        
        entity = Entity(workspace_id=workspace_id, name=f"Big Client {unique_id}", type=EntityType.CUSTOMER)
        # Store deal_id in metadata so CommissionService can find it (heuristic impl)
        entity.metadata_json = {"crm_deal_id": deal.id} 
        db.add(entity)
        db.flush()
        
        # 2. Create PAiD Invoice
        invoice = Invoice(
            workspace_id=workspace_id,
            customer_id=entity.id,
            amount=5000.0,
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            status=InvoiceStatus.PAID,
            invoice_number=f"INV-{unique_id}"
        )
        db.add(invoice)
        db.commit() # Commit so service can find it
        
        # 3. Process Commission
        print(f"Processing commission for Invoice {invoice.id}...")
        comm = comm_service.process_invoice_payment(invoice.id)
        
        assert comm is not None
        assert comm.amount == 500.0 # 10% of 5000
        assert comm.deal_id == deal.id
        assert comm.status == CommissionStatus.ACCRUED
        print(f"✅ Commission accrued: ${comm.amount} for Deal {deal.name}")

        print(f"\n--- Phase 3: Credit Risk Engine Verification ---")
        risk_engine = CreditRiskEngine(db)
        
        # Simulate a generic 'risk' scenario?
        # Let's check current risk (should be low/neutral)
        score, level = risk_engine.analyze_customer_risk(entity.id)
        print(f"Initial Risk: {score} ({level})")
        assert level == "low"
        
        # Create an OPEN OLD invoice to trigger risk
        risky_invoice = Invoice(
            workspace_id=workspace_id,
            customer_id=entity.id,
            amount=20000.0, # High amount
            issue_date=datetime.now(timezone.utc) - timedelta(days=60),
            due_date=datetime.now(timezone.utc) - timedelta(days=30), # Overdue by 30 days
            status=InvoiceStatus.OPEN,
            invoice_number=f"INV-RISK-{unique_id}"
        )
        db.add(risky_invoice)
        db.commit()
        
        score_high, level_high = risk_engine.analyze_customer_risk(entity.id)
        print(f"Risk after overdue invoice: {score_high} ({level_high})")
        
        # overdue amount 20k -> (20000/1000)*50 = capped at 50 pts
        # + assume 0 late payments frequency (since only 1 paid on time) -> 50 pts total
        # Should be Medium/High
        assert score_high >= 50
        print("✅ Risk Engine correctly detected high risk customer behavior")

    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    verify_phase14_flow()
