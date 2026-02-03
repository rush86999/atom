import logging
from datetime import datetime
from typing import Any, Dict, Optional
from accounting.categorizer import AICategorizer
from accounting.ledger import EventSourcedLedger
from accounting.models import Account, AccountType, EntryType, Transaction, TransactionStatus
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class IngestionError(Exception):
    pass

class TransactionIngestor:
    """
    Main entry point for ingesting external financial data into the native ledger.
    Handles Stripe, Bank Feeds, etc.
    """

    def __init__(self, db: Session):
        self.db = db
        self.ledger = EventSourcedLedger(db)
        self.categorizer = AICategorizer(db)

    async def ingest_stripe_payment(
        self,
        workspace_id: str,
        stripe_data: Dict[str, Any]
    ) -> Transaction:
        """
        Convert a Stripe payment_intent.succeeded event into a ledger transaction.
        """
        payment_id = stripe_data.get("id")
        amount = stripe_data.get("amount", 0) / 100.0 # Stripe is in cents
        currency = stripe_data.get("currency", "usd").upper()
        description = stripe_data.get("description") or f"Stripe Payment {payment_id}"
        
        # 1. Check if already ingested
        existing = self.db.query(Transaction).filter(
            Transaction.workspace_id == workspace_id,
            Transaction.external_id == payment_id
        ).first()
        if existing:
            logger.info(f"Stripe payment {payment_id} already ingested.")
            return existing

        # 2. Get standard accounts
        # In a real app, these would be configured per workspace.
        # For now, we search by code or name.
        cash_account = self.db.query(Account).filter(
            Account.workspace_id == workspace_id,
            Account.code == "1000" # Default Cash
        ).first()
        
        if not cash_account:
            raise IngestionError("Cash account not found for workspace. Please seed CoA.")

        # 3. Create a pending transaction header
        # We start by putting it into a "Revenue" or "Uncategorized Income" account.
        # Then the AI categorizer can run and propose a better split if needed.
        
        # For now, we'll use a generic Sales account
        sales_account = self.db.query(Account).filter(
            Account.workspace_id == workspace_id,
            Account.code == "4000" # Default Sales
        ).first()
        
        if not sales_account:
            raise IngestionError("Sales account not found for workspace.")

        entries = [
            {"account_id": cash_account.id, "type": EntryType.DEBIT, "amount": amount},
            {"account_id": sales_account.id, "type": EntryType.CREDIT, "amount": amount}
        ]

        transaction = self.ledger.record_transaction(
            workspace_id=workspace_id,
            transaction_date=datetime.utcnow(),
            description=description,
            entries=entries,
            source="stripe",
            external_id=payment_id,
            metadata=stripe_data
        )

        # 4. Trigger AI Categorization Refinement
        # This runs asynchronously (or we await it here for the MVP)
        await self.categorizer.propose_categorization(transaction, workspace_id)

        return transaction
