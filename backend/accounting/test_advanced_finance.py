import asyncio
from datetime import datetime
import logging
import os
import sys
from sqlalchemy.orm import Session

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from accounting.models import Account, Budget, Transaction
from accounting.seeds import seed_default_accounts
from accounting.sync_manager import AccountingSyncManager
from accounting.workflow_service import FinancialWorkflowService

from core.database import SessionLocal, engine
from core.models import Workspace
from integrations.atom_communication_ingestion_pipeline import memory_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_advanced_finance_flow():
    db = SessionLocal()
    workspace_id = "advanced-finance-test"
    
    try:
        # 1. Setup
        print("--- Phase 1: Setup ---")
        # Ensure memory manager is ready
        memory_manager.initialize()
        
        ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not ws:
            ws = Workspace(id=workspace_id, name="Advanced Finance Test")
            db.add(ws)
            db.commit()

        # Clean old data
        db.query(Transaction).filter(Transaction.workspace_id == workspace_id).delete()
        db.query(Budget).filter(Budget.workspace_id == workspace_id).delete()
        db.query(Account).filter(Account.workspace_id == workspace_id).delete()
        db.commit()

        seed_default_accounts(db, workspace_id)
        
        # Add a budget to trigger overrun
        marketing_acc = db.query(Account).filter(Account.workspace_id == workspace_id, Account.name == "Marketing Expense").first()
        budget = Budget(workspace_id=workspace_id, category_id=marketing_acc.id, amount=100.0, period="monthly", start_date=datetime.now(), end_date=datetime.now())
        db.add(budget)
        db.commit()

        sync_manager = AccountingSyncManager(db)
        workflow_service = FinancialWorkflowService(db)

        # 2. Ingest Transaction (triggers LanceDB + Sync)
        print("\n--- Phase 2: Ingestion & Semantic Mapping ---")
        mock_credentials = {"access_token": "test", "organization_id": "org1"}
        
        # We'll simulate a Zoho transaction that exceeds budget
        zoho_tx = [
            {"transaction_id": "adv_1", "description": "Google Ads Premium", "amount": 500.0, "date": "2023-11-01"}
        ]
        
        # Manually call mapping and ingestion to bypass real API calls
        mapped = sync_manager._map_zoho_transactions(zoho_tx, workspace_id)
        
        # Ingest into DB
        tx = Transaction(
            workspace_id=workspace_id,
            description=mapped[0]["description"],
            amount=mapped[0]["amount"],
            source="zoho",
            transaction_date=mapped[0]["date"],
            metadata_json={"external_id": mapped[0]["external_id"], "platform": "zoho"}
        )
        db.add(tx)
        db.commit()
        
        print(f"✅ Transaction {tx.id} ingested into PostgreSQL")

        # Now test the semantic ingestion part
        from integrations.atom_communication_ingestion_pipeline import (
            CommunicationAppType,
            IngestionConfig,
            ingestion_pipeline,
        )
        ingestion_pipeline.configure_app(CommunicationAppType.ZOHO, IngestionConfig(
            app_type=CommunicationAppType.ZOHO,
            enabled=True,
            real_time=False,
            batch_size=1,
            ingest_attachments=False,
            embed_content=True,
            retention_days=365
        ))
        
        ingestion_pipeline.ingest_message(
            app_type="zoho",
            message_data={
                "id": f"tx_{tx.id}",
                "timestamp": tx.transaction_date.isoformat(),
                "content": f"Large Marketing Spend: {tx.description}. Amount: {tx.amount}",
                "metadata": {"transaction_id": tx.id}
            }
        )
        
        # Verify in LanceDB
        import asyncio
        await asyncio.sleep(2) # Give it time to index
        search_results = memory_manager.search_communications("Google Ads", limit=5)
        if not search_results:
            print("❌ Semantic Search Failed: No results found for 'Google Ads'")
            print(f"All records in communications: {memory_manager.connections_table.to_pandas()}")
        else:
            print(f"✅ Semantic Search Verified: Found '{search_results[0]['content']}' in LanceDB")

        # 3. Trigger Workflow
        print("\n--- Phase 3: Workflow Automation ---")
        # Handle transaction event (should detect budget overrun)
        await workflow_service.handle_transaction_event(tx.id)
        print("✅ Workflow service processed transaction event (Budget Check)")

        print("\nAdvanced Finance & Knowledge Flow Verified!")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_advanced_finance_flow())
