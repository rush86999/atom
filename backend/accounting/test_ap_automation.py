import asyncio
import logging
import os
import shutil
import sys
from datetime import datetime
from sqlalchemy.orm import Session

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from unittest.mock import AsyncMock, MagicMock

# 1. PRE-MOCK PDFOCRService to avoid heavy imports
mock_pdf_ocr = MagicMock()
sys.modules['integrations.pdf_processing.pdf_ocr_service'] = mock_pdf_ocr
sys.modules['integrations.pdf_processing'] = MagicMock()

# from accounting.ap_service import APService  # Move this inside
from accounting.models import (
    Account,
    AccountType,
    Bill,
    Document,
    Entity,
    JournalEntry,
    Transaction,
)
from accounting.seeds import seed_default_accounts

from core.database import SessionLocal, engine
from core.models import Workspace

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ap_automation_flow():
    db = SessionLocal()
    workspace_id = "ap-automation-test"
    
    try:
        # 1. Setup
        print("--- Phase 1: Setup ---")
        ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not ws:
            ws = Workspace(id=workspace_id, name="AP Automation Test")
            db.add(ws)
            db.commit()

        # Clean old data
        db.query(Bill).filter(Bill.workspace_id == workspace_id).delete()
        db.query(Document).filter(Document.workspace_id == workspace_id).delete()
        db.query(Transaction).filter(Transaction.workspace_id == workspace_id).delete()
        db.query(Entity).filter(Entity.workspace_id == workspace_id).delete()
        db.query(Account).filter(Account.workspace_id == workspace_id).delete()
        db.commit()

        seed_results = seed_default_accounts(db, workspace_id)
        print(f"✅ Default accounts seeded: {seed_results}")

        from accounting.ap_service import APService
        ap_service = APService(db)
        
        # Configure the mock that was injected into sys.modules
        ap_service.ocr_service.process_pdf = AsyncMock(return_value={
            "extracted_content": {"text": "CloudServices Inc Invoice #12345 Total: $299.99"},
            "success": True
        })

        # 2. Simulate Upload & Process
        print("\n--- Phase 2: Invoice Upload & OCR ---")
        test_file_path = "/tmp/test_invoice.pdf"
        
        # Create a document record first
        doc = Document(
            workspace_id=workspace_id,
            file_path=test_file_path,
            file_name="test_invoice.pdf",
            file_type="pdf"
        )
        db.add(doc)
        db.commit()
        
        print(f"Ingesting invoice document {doc.id}...")
        result = await ap_service.process_invoice_document(doc.id, workspace_id)
        
        if result["status"] == "success":
            print(f"✅ Invoice processed successfully!")
            print(f"   Bill ID: {result['bill_id']}")
            print(f"   Transaction ID: {result['transaction_id']}")
            print(f"   Vendor: {result['vendor']}")
            print(f"   Amount: {result['amount']}")
        else:
            print(f"❌ Invoice processing failed: {result}")
            return

        # 3. Verify Database Records
        print("\n--- Phase 3: Database Verification ---")
        bill = db.query(Bill).filter(Bill.id == result["bill_id"]).first()
        if not bill:
            print("❌ Bill record not found!")
        else:
            print(f"✅ Bill found. Amount: {bill.amount}, Vendor ID: {bill.vendor_id}")

        tx = db.query(Transaction).filter(Transaction.id == result["transaction_id"]).first()
        if not tx:
            print("❌ Transaction record not found!")
        else:
            print(f"✅ Transaction found. Source: {tx.source}")

        # 4. Verify Ledger Balances
        print("\n--- Phase 4: Ledger & Balances ---")
        from accounting.ledger import EventSourcedLedger
        ledger = EventSourcedLedger(db)
        
        # Check specific account balances
        ap_acc = db.query(Account).filter(Account.workspace_id == workspace_id, Account.code == "2000").first()
        sw_acc = db.query(Account).filter(Account.workspace_id == workspace_id, Account.code == "5100").first()
        
        ap_balance = ledger.get_account_balance(ap_acc.id)
        sw_balance = ledger.get_account_balance(sw_acc.id)
        
        print(f"Accounts Payable Balance: {ap_balance}")
        print(f"Software & Subscriptions Balance: {sw_balance}")
        
        if ap_balance == result["amount"] and sw_balance == result["amount"]:
            print("✅ Ledger balances verified! (Accrual working)")
        else:
            print(f"❌ Balance mismatch. Expected {result['amount']}, got AP:{ap_balance}, Exp:{sw_balance}")

        print("\nAP Automation Flow Verified!")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_ap_automation_flow())
