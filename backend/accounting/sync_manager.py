from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from accounting.categorizer import AICategorizer
from accounting.models import Account, EntryType, JournalEntry, Transaction
from sqlalchemy.orm import Session

from integrations.atom_communication_ingestion_pipeline import (
    CommunicationAppType,
    ingestion_pipeline,
)
from integrations.quickbooks_service import QuickBooksService
from integrations.xero_service import XeroService
from integrations.zoho_books_service import ZohoBooksService

logger = logging.getLogger(__name__)

class AccountingSyncManager:
    """
    Unified manager for synchronizing data across multiple accounting ledgers 
    (Zoho, Xero, QuickBooks, Stripe/Plaid).
    """

    def __init__(self, db: Session):
        self.db = db
        self.zoho = ZohoBooksService()
        self.xero = XeroService()
        self.qbo = QuickBooksService()
        self.categorizer = AICategorizer(db)

    async def sync_external_transactions(
        self, 
        workspace_id: str, 
        platform: str, 
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Pull transactions from an external platform and ingest into ATOM's ledger.
        """
        raw_transactions = []
        
        if platform == "zoho":
            raw_transactions = await self.zoho.get_bank_transactions(
                credentials["access_token"], 
                credentials["organization_id"],
                credentials.get("account_id")
            )
            mapped_txs = self._map_zoho_transactions(raw_transactions, workspace_id)
            
        elif platform == "xero":
            raw_transactions = await self.xero.get_invoices(
                credentials["access_token"],
                credentials["tenant_id"]
            )
            mapped_txs = self._map_xero_transactions(raw_transactions, workspace_id)
            
        elif platform == "quickbooks":
            raw_transactions = await self.qbo.get_expenses(
                credentials["realm_id"],
                credentials["access_token"]
            )
            mapped_txs = self._map_qbo_transactions(raw_transactions, workspace_id)
        
        else:
            raise ValueError(f"Unsupported platform: {platform}")

        ingested_count = 0
        for tx_data in mapped_txs:
            # Check for existing
            exists = self.db.query(Transaction).filter(
                Transaction.workspace_id == workspace_id,
                Transaction.metadata_json.contains(tx_data["external_id"])
            ).first()
            
            if not exists:
                tx = Transaction(
                    workspace_id=workspace_id,
                    description=tx_data["description"],
                    amount=tx_data["amount"],
                    transaction_date=tx_data["date"],
                    metadata_json={"external_id": tx_data["external_id"], "platform": platform}
                )
                self.db.add(tx)
                self.db.flush()
                
                # Auto-categorize
                self.categorizer.categorize_transaction(tx.id)
                ingested_count += 1

                # Ingest into semantic memory (LanceDB + Knowledge Graph)
                try:
                    ingestion_pipeline.ingest_message(
                        app_type=platform if platform != "quickbooks" else "quickbooks",
                        message_data={
                            "id": f"tx_{tx.id}",
                            "timestamp": tx.transaction_date.isoformat(),
                            "sender": platform,
                            "content": f"Financial Transaction: {tx.description}. Amount: {tx.amount}. Merchant: {tx.metadata_json.get('merchant', 'Unknown')}",
                            "metadata": {
                                "transaction_id": tx.id,
                                "workspace_id": workspace_id,
                                "amount": tx.amount,
                                "external_id": tx_data["external_id"]
                            }
                        }
                    )
                except Exception as ex:
                    logger.error(f"Failed to ingest transaction {tx.id} into semantic memory: {ex}")

        self.db.commit()
        return {"status": "success", "ingested": ingested_count, "platform": platform}

    def _map_zoho_transactions(self, raw: List[Dict], ws_id: str) -> List[Dict]:
        return [{
            "description": t.get("description", "Zoho Transaction"),
            "amount": float(t.get("amount", 0)),
            "date": datetime.strptime(t["date"], "%Y-%m-%d") if "date" in t else datetime.now(),
            "external_id": str(t.get("transaction_id", ""))
        } for t in raw]

    def _map_xero_transactions(self, raw: List[Dict], ws_id: str) -> List[Dict]:
        return [{
            "description": f"Xero Invoice: {t.get('InvoiceNumber','')}",
            "amount": float(t.get("Total", 0)),
            "date": datetime.strptime(t["DateString"], "%Y-%m-%dT%H:%M:%S") if "DateString" in t else datetime.now(),
            "external_id": str(t.get("InvoiceID", ""))
        } for t in raw]

    def _map_qbo_transactions(self, raw: List[Dict], ws_id: str) -> List[Dict]:
        return [{
            "description": t.get("PrivateNote", "QBO Expense"),
            "amount": float(t.get("TotalAmt", 0)),
            "date": datetime.strptime(t["TxnDate"], "%Y-%m-%d") if "TxnDate" in t else datetime.now(),
            "external_id": str(t.get("Id", ""))
        } for t in raw]
