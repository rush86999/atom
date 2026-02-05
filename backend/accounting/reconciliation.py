from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Tuple
from accounting.models import Account, Transaction, TransactionStatus
from sqlalchemy.orm import Session

from integrations.stripe_service import stripe_service

logger = logging.getLogger(__name__)

class ReconciliationService:
    """
    Service for ensuring the internal ledger matches external sources.
    Detects missing transactions, duplicates, and timing differences.
    """

    def __init__(self, db: Session):
        self.db = db

    async def reconcile_stripe(
        self,
        workspace_id: str,
        stripe_access_token: str,
        days_to_look_back: int = 30
    ) -> Dict[str, Any]:
        """
        Compare Stripe charges with internal transactions.
        """
        # 1. Fetch external transactions from Stripe
        created_filter = {
            "gte": int((datetime.utcnow() - timedelta(days=days_to_look_back)).timestamp())
        }
        stripe_charges = stripe_service.list_payments(
            stripe_access_token,
            limit=100,
            created=created_filter
        ).get("data", [])

        # 2. Fetch internal transactions for the same period
        internal_transactions = self.db.query(Transaction).filter(
            Transaction.workspace_id == workspace_id,
            Transaction.source == "stripe",
            Transaction.transaction_date >= (datetime.utcnow() - timedelta(days=days_to_look_back))
        ).all()

        internal_ids = {tx.external_id for tx in internal_transactions}
        
        missing_in_ledger = []
        matched = []
        duplicates = [] # Internal transactions with the same external_id
        
        seen_external_ids = set()
        for tx in internal_transactions:
            if tx.external_id in seen_external_ids:
                duplicates.append({
                    "id": tx.id,
                    "external_id": tx.external_id,
                    "description": tx.description
                })
            seen_external_ids.add(tx.external_id)

        # 3. Match and detect missing
        for charge in stripe_charges:
            charge_id = charge.get("id")
            if charge_id in internal_ids:
                matched.append(charge_id)
            else:
                missing_in_ledger.append({
                    "id": charge_id,
                    "amount": charge.get("amount", 0) / 100.0,
                    "currency": charge.get("currency"),
                    "description": charge.get("description"),
                    "created": charge.get("created")
                })

        summary = {
            "workspace_id": workspace_id,
            "period_days": days_to_look_back,
            "stripe_count": len(stripe_charges),
            "internal_count": len(internal_transactions),
            "matched_count": len(matched),
            "missing_count": len(missing_in_ledger),
            "duplicate_count": len(duplicates),
            "missing_transactions": missing_in_ledger,
            "duplicates": duplicates
        }

        logger.info(f"Reconciliation for {workspace_id}: {summary['matched_count']} matched, {summary['missing_count']} missing")
        return summary

    def flag_anomaly(self, transaction_id: str, reason: str):
        """Flag a transaction for manual review"""
        transaction = self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if transaction:
            if not transaction.metadata_json:
                transaction.metadata_json = {}
            transaction.metadata_json["anomaly_flag"] = True
            transaction.metadata_json["anomaly_reason"] = reason
            self.db.commit()
            return True
        return False
