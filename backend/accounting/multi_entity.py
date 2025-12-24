import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from accounting.models import Transaction, Account, AccountType, JournalEntry, EntryType

logger = logging.getLogger(__name__)

class IntercompanyManager:
    """
    Manager for handling multi-entity transactions and intercompany eliminations.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_intercompany_transactions(self, workspace_id: str) -> List[Transaction]:
        """Fetch all transactions involving other workspaces"""
        return self.db.query(Transaction).filter(
            Transaction.workspace_id == workspace_id,
            Transaction.is_intercompany == True
        ).all()

    def find_unmatched_intercompany(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Identify intercompany transactions that don't have a matching 
        entry in the counterparty workspace.
        """
        txs = self.get_intercompany_transactions(workspace_id)
        unmatched = []

        for tx in txs:
            if not tx.counterparty_workspace_id:
                continue
            
            # Look for a transaction in the counterparty workspace with same external_id or matching amount
            # This is a simplified check
            matching = self.db.query(Transaction).filter(
                Transaction.workspace_id == tx.counterparty_workspace_id,
                Transaction.is_intercompany == True,
                Transaction.counterparty_workspace_id == workspace_id
            ).first()

            if not matching:
                unmatched.append({
                    "transaction_id": tx.id,
                    "target_workspace": tx.counterparty_workspace_id,
                    "date": tx.transaction_date,
                    "description": tx.description
                })
        
        return unmatched

    def generate_elimination_report(self, workspace_id: str) -> Dict[str, Any]:
        """
        Calculate total intercompany volume to be eliminated for consolidation.
        """
        txs = self.get_intercompany_transactions(workspace_id)
        
        total_volume = 0.0
        by_counterparty = {}

        for tx in txs:
            # We determine volume by summing journal entry amounts (one side)
            amount = sum(je.amount for je in tx.journal_entries if je.type == EntryType.DEBIT)
            total_volume += amount
            
            cp = tx.counterparty_workspace_id or "Unknown"
            by_counterparty[cp] = by_counterparty.get(cp, 0.0) + amount

        return {
            "total_elimination_volume": total_volume,
            "breakdown_by_counterparty": by_counterparty,
            "transaction_count": len(txs)
        }
