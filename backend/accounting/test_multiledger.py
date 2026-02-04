import asyncio
import logging
import os
import sys
from datetime import datetime
from sqlalchemy.orm import Session

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from accounting.models import Account, CategorizationProposal, CategorizationRule, Transaction
from accounting.seeds import seed_default_accounts
from accounting.sync_manager import AccountingSyncManager

from core.database import SessionLocal, engine
from core.models import User, Workspace

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_multi_ledger_sync():
    db = SessionLocal()
    workspace_id = "multiledger-test-ws"
    
    try:
        # 1. Setup
        print("Setting up test data...")
        ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not ws:
            ws = Workspace(id=workspace_id, name="MultiLedger Test")
            db.add(ws)
            db.commit()

        # Clean old data
        db.query(CategorizationProposal).filter(CategorizationProposal.transaction_id.in_(
            db.query(Transaction.id).filter(Transaction.workspace_id == workspace_id)
        )).delete(synchronize_session=False)
        db.query(Transaction).filter(Transaction.workspace_id == workspace_id).delete()
        db.query(Account).filter(Account.workspace_id == workspace_id).delete()
        db.commit()

        seed_default_accounts(db, workspace_id)
        
        sync_manager = AccountingSyncManager(db)

        # 2. Mock Zoho Sync
        print("\nTesting Zoho Books mapping...")
        zoho_raw = [
            {"transaction_id": "z1", "description": "Cloud Services Monthly", "amount": 299.0, "date": "2023-10-01"},
            {"transaction_id": "z2", "description": "Coffee Shop", "amount": 15.0, "date": "2023-10-02"}
        ]
        # We manually call a part of the sync for testing without hitting real APIs
        mapped = sync_manager._map_zoho_transactions(zoho_raw, workspace_id)
        print(f"✅ Mapped {len(mapped)} Zoho transactions")
        assert mapped[0]["amount"] == 299.0
        assert mapped[0]["external_id"] == "z1"

        # 3. Mock Xero Sync
        print("Testing Xero mapping...")
        xero_raw = [
            {"InvoiceID": "x1", "InvoiceNumber": "INV-001", "Total": 1200.0, "DateString": "2023-10-05T10:00:00"}
        ]
        mapped = sync_manager._map_xero_transactions(xero_raw, workspace_id)
        print(f"✅ Mapped {len(mapped)} Xero transactions")
        assert mapped[0]["amount"] == 1200.0
        assert "INV-001" in mapped[0]["description"]

        # 4. Mock QBO Sync
        print("Testing QuickBooks mapping...")
        qbo_raw = [
            {"Id": "q1", "PrivateNote": "Marketing Pro", "TotalAmt": 500.0, "TxnDate": "2023-10-10"}
        ]
        mapped = sync_manager._map_qbo_transactions(qbo_raw, workspace_id)
        print(f"✅ Mapped {len(mapped)} QBO transactions")
        assert mapped[0]["amount"] == 500.0
        assert mapped[0]["external_id"] == "q1"

        print("\nMulti-Ledger Mapping logic verified!")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_multi_ledger_sync())
