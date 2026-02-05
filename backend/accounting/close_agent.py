from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from accounting.models import (
    Bill,
    BillStatus,
    CategorizationProposal,
    FinancialClose,
    Invoice,
    InvoiceStatus,
    JournalEntry,
    Transaction,
    TransactionStatus,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class CloseChecklistAgent:
    """
    Agent responsible for monitoring readiness for the periodic financial close.
    """

    def __init__(self, db: Session):
        self.db = db

    async def run_close_check(self, workspace_id: str, period: str) -> Dict[str, Any]:
        """
        Evaluate if the workspace is ready for a financial close for the given period.
        """
        results = {
            "period": period,
            "is_ready": True,
            "checklist": [],
            "blockers": []
        }

        # 1. Check for Uncategorized Transactions
        uncategorized_count = self.db.query(Transaction).filter(
            Transaction.workspace_id == workspace_id,
            Transaction.status == TransactionStatus.PENDING
        ).count()

        if uncategorized_count > 0:
            results["is_ready"] = False
            results["blockers"].append(f"{uncategorized_count} transactions are still pending categorization.")
            results["checklist"].append({"task": "Categorize Transactions", "status": "blocked"})
        else:
            results["checklist"].append({"task": "Categorize Transactions", "status": "complete"})

        # 2. Check for Unbalanced Journal Entries
        # In our EventSourcedLedger, this shouldn't happen, but good to verify
        # SELECT transaction_id, SUM(CASE WHEN type='debit' THEN amount ELSE -amount END) as diff
        from sqlalchemy import case
        unbalanced = self.db.query(JournalEntry.transaction_id).group_by(JournalEntry.transaction_id).having(
            func.abs(func.sum(case((JournalEntry.type == 'debit', JournalEntry.amount), else_=-JournalEntry.amount))) > 0.001
        ).all()

        if unbalanced:
            results["is_ready"] = False
            results["blockers"].append(f"{len(unbalanced)} transactions are unbalanced in the ledger.")
            results["checklist"].append({"task": "Ledger Integrity Check", "status": "blocked"})
        else:
            results["checklist"].append({"task": "Ledger Integrity Check", "status": "complete"})

        # 3. Check for Open Invoices / Bills (Optional for soft close, blocker for hard close)
        open_bills = self.db.query(Bill).filter(
            Bill.workspace_id == workspace_id,
            Bill.status == BillStatus.OPEN
        ).count()
        
        if open_bills > 0:
            results["checklist"].append({"task": "Review Open Bills", "status": "warning", "note": f"{open_bills} bills are still open."})
        else:
            results["checklist"].append({"task": "Review Open Bills", "status": "complete"})

        # Update or create the Close record
        close_record = self.db.query(FinancialClose).filter(
            FinancialClose.workspace_id == workspace_id,
            FinancialClose.period == period
        ).first()

        if not close_record:
            close_record = FinancialClose(
                workspace_id=workspace_id,
                period=period,
                metadata_json=results
            )
            self.db.add(close_record)
        else:
            close_record.metadata_json = results
        
        self.db.commit()
        return results

    async def close_period(self, workspace_id: str, period: str, user_id: str) -> Dict[str, Any]:
        """
        Permanently close a period if ready.
        """
        check = await self.run_close_check(workspace_id, period)
        if not check["is_ready"]:
            return {"success": False, "message": "Cannot close period. Please resolve blockers.", "blockers": check["blockers"]}

        close_record = self.db.query(FinancialClose).filter(
            FinancialClose.workspace_id == workspace_id,
            FinancialClose.period == period
        ).first()

        close_record.is_closed = True
        close_record.closed_at = datetime.utcnow()
        close_record.closed_by = user_id
        
        self.db.commit()
        
        return {"success": True, "message": f"Period {period} has been closed successfully."}
