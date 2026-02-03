import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from accounting.dashboard_service import AccountingDashboardService
from accounting.models import (
    Account,
    AccountType,
    Bill,
    BillStatus,
    Entity,
    EntityType,
    EntryType,
    Invoice,
    InvoiceStatus,
    JournalEntry,
    Transaction,
)
from sales.dashboard_service import SalesDashboardService
from sales.models import Deal, DealStage, Lead

from core.database import SessionLocal, engine
from core.models import Workspace

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_dashboard_aggregation():
    db = SessionLocal()
    # Use a unique workspace for this run
    unique_id = uuid.uuid4().hex[:8]
    workspace_id = f"test-ws-{unique_id}"
    
    try:
        # 1. Setup / Seed Data
        print(f"--- Phase 1: Seeding Dashboard Data (WS: {workspace_id}) ---")
        ws = Workspace(id=workspace_id, name=f"Test Workspace {unique_id}")
        db.add(ws)
        db.commit()

        # Seed Accounts
        cash_acc = Account(workspace_id=workspace_id, name="Bank Account", type=AccountType.ASSET, code=f"1001-{unique_id}")
        rev_acc = Account(workspace_id=workspace_id, name="Service Revenue", type=AccountType.REVENUE, code=f"4001-{unique_id}")
        exp_acc = Account(workspace_id=workspace_id, name="Office Rent", type=AccountType.EXPENSE, code=f"6001-{unique_id}")
        db.add_all([cash_acc, rev_acc, exp_acc])
        db.commit()
        
        # Refresh to get IDs
        db.refresh(cash_acc)
        db.refresh(rev_acc)
        db.refresh(exp_acc)

        # Seed Transactions
        # $10k initial cash
        tx1 = Transaction(workspace_id=workspace_id, transaction_date=datetime.now(timezone.utc) - timedelta(days=95), description="Opening Balance", amount=10000, source="manual")
        db.add(tx1)
        db.commit()
        db.refresh(tx1)
        db.add(JournalEntry(transaction_id=tx1.id, account_id=cash_acc.id, type=EntryType.DEBIT, amount=10000))
        
        # $3k revenue last month
        tx2 = Transaction(workspace_id=workspace_id, transaction_date=datetime.now(timezone.utc) - timedelta(days=30), description="Sale", amount=3000, source="manual")
        db.add(tx2)
        db.commit()
        db.refresh(tx2)
        db.add(JournalEntry(transaction_id=tx2.id, account_id=cash_acc.id, type=EntryType.DEBIT, amount=3000))
        db.add(JournalEntry(transaction_id=tx2.id, account_id=rev_acc.id, type=EntryType.CREDIT, amount=3000))

        # $6k expense (Burn) last month
        tx3 = Transaction(workspace_id=workspace_id, transaction_date=datetime.now(timezone.utc) - timedelta(days=30), description="Rent", amount=6000, source="manual")
        db.add(tx3)
        db.commit()
        db.refresh(tx3)
        db.add(JournalEntry(transaction_id=tx3.id, account_id=exp_acc.id, type=EntryType.DEBIT, amount=6000))
        db.add(JournalEntry(transaction_id=tx3.id, account_id=cash_acc.id, type=EntryType.CREDIT, amount=6000))

        # Seed Entities
        vendor = Entity(workspace_id=workspace_id, name="Vendor A", type=EntityType.VENDOR)
        customer = Entity(workspace_id=workspace_id, name="Cust A", type=EntityType.CUSTOMER)
        db.add_all([vendor, customer])
        db.commit()
        db.refresh(vendor)
        db.refresh(customer)

        # Seed Bills and Invoices
        db.add(Bill(
            workspace_id=workspace_id, 
            vendor_id=vendor.id, 
            amount=500, 
            status=BillStatus.OPEN, 
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=10)
        ))
        db.add(Invoice(
            workspace_id=workspace_id, 
            customer_id=customer.id, 
            amount=1200, 
            status=InvoiceStatus.OPEN, 
            issue_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=10)
        ))

        # Seed Leads and Deals
        db.add(Lead(workspace_id=workspace_id, first_name="Lead", last_name="A", email=f"l1_{unique_id}@ex.com", ai_score=85, is_converted=True))
        db.add(Lead(workspace_id=workspace_id, first_name="Lead", last_name="B", email=f"l2_{unique_id}@ex.com", ai_score=40, is_converted=False))
        
        db.add(Deal(workspace_id=workspace_id, name="Deal Large", value=10000, probability=0.8, stage=DealStage.DISCOVERY, health_score=90))
        db.add(Deal(workspace_id=workspace_id, name="Deal Risky", value=5000, probability=0.2, stage=DealStage.NEGOTIATION, health_score=35))
        
        db.commit()

        # 2. Verify Accounting Summary
        print("\n--- Phase 2: Verifying Accounting Summary ---")
        acc_service = AccountingDashboardService(db)
        fin_summary = acc_service.get_financial_summary(workspace_id)
        print(f"Financial Summary: {fin_summary}")
        
        assert fin_summary["total_cash"] == 7000
        assert fin_summary["accounts_payable"] == 500
        assert fin_summary["accounts_receivable"] == 1200
        assert fin_summary["monthly_burn"] == 1000
        assert fin_summary["runway_months"] == 7.0
        print("✅ Accounting Summary Verified!")

        # 3. Verify Sales Summary
        print("\n--- Phase 3: Verifying Sales Summary ---")
        sales_service = SalesDashboardService(db)
        sales_summary = sales_service.get_sales_summary(workspace_id)
        print(f"Sales Summary: {sales_summary}")
        
        assert sales_summary["total_leads"] == 2
        assert sales_summary["conversion_rate"] == 50.0
        assert sales_summary["pipeline_value"] == 15000
        assert sales_summary["weighted_forecast"] == 9000
        assert sales_summary["high_risk_deals_count"] == 1
        print("✅ Sales Summary Verified!")

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_dashboard_aggregation())
