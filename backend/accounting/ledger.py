import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from accounting.models import Account, Transaction, JournalEntry, EntryType, TransactionStatus, AccountType

logger = logging.getLogger(__name__)

class LedgerError(Exception):
    """Base class for ledger exceptions"""
    pass

class UnbalancedTransactionError(LedgerError):
    """Raised when debits and credits do not match"""
    pass

class EventSourcedLedger:
    """
    Service for recording immutable financial events.
    Ensures every transaction follows double-entry principles.
    """

    def __init__(self, db: Session):
        self.db = db

    def record_transaction(
        self,
        workspace_id: str,
        transaction_date: datetime,
        description: str,
        entries: List[Dict[str, Any]],
        source: str = "manual",
        external_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """
        Record a double-entry transaction.
        'entries' should be a list of dicts: [
            {"account_id": "...", "type": EntryType.DEBIT, "amount": 100.0},
            {"account_id": "...", "type": EntryType.CREDIT, "amount": 100.0}
        ]
        """
        # 1. Validate balance
        debits = sum(e["amount"] for e in entries if e["type"] == EntryType.DEBIT)
        credits = sum(e["amount"] for e in entries if e["type"] == EntryType.CREDIT)

        if abs(debits - credits) > 0.00001: # Avoid floating point issues
            raise UnbalancedTransactionError(f"Debits ({debits}) do not match Credits ({credits})")

        # 2. Create Transaction Header
        transaction = Transaction(
            workspace_id=workspace_id,
            transaction_date=transaction_date,
            description=description,
            source=source,
            external_id=external_id,
            status=TransactionStatus.POSTED,
            metadata_json=metadata
        )
        self.db.add(transaction)
        self.db.flush() # Get transaction ID

        # 3. Create Journal Entries
        for entry_data in entries:
            journal_entry = JournalEntry(
                transaction_id=transaction.id,
                account_id=entry_data["account_id"],
                type=entry_data["type"],
                amount=entry_data["amount"],
                description=entry_data.get("description")
            )
            self.db.add(journal_entry)

        try:
            self.db.commit()
            logger.info(f"Recorded transaction {transaction.id} for workspace {workspace_id}")
            return transaction
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to record transaction: {e}")
            raise LedgerError(f"Database error: {str(e)}")

    def get_account_balance(self, account_id: str) -> float:
        """
        Calculate the current balance of an account.
        Asset/Expense: Debit - Credit
        Liability/Equity/Revenue: Credit - Debit
        """
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return 0.0

        # Sum debits and credits
        totals = self.db.query(
            JournalEntry.type,
            func.sum(JournalEntry.amount).label("total")
        ).filter(JournalEntry.account_id == account_id).group_by(JournalEntry.type).all()

        debit_total = 0.0
        credit_total = 0.0
        for t in totals:
            if t.type == EntryType.DEBIT:
                debit_total = t.total
            else:
                credit_total = t.total

        # Assets and Expenses are typically debit accounts
        if account.type in [AccountType.ASSET, AccountType.EXPENSE]:
            return debit_total - credit_total
        else:
            # Liabilities, Equities, and Revenues are typically credit accounts
            return credit_total - debit_total

    def get_trial_balance(self, workspace_id: str) -> Dict[str, float]:
        """Returns the balances of all accounts in the workspace"""
        accounts = self.db.query(Account).filter(Account.workspace_id == workspace_id).all()
        return {acc.name: self.get_account_balance(acc.id) for acc in accounts}

class DoubleEntryEngine:
    """Helper for common accounting patterns"""
    
    @staticmethod
    def create_payment_entry(
        cash_account_id: str,
        expense_account_id: str,
        amount: float,
        description: str
    ) -> List[Dict[str, Any]]:
        """Pattern: Pay for an expense with cash"""
        return [
            {"account_id": expense_account_id, "type": EntryType.DEBIT, "amount": amount},
            {"account_id": cash_account_id, "type": EntryType.CREDIT, "amount": amount}
        ]

    @staticmethod
    def create_invoice_entry(
        receivable_account_id: str,
        revenue_account_id: str,
        amount: float,
        description: str
    ) -> List[Dict[str, Any]]:
        """Pattern: Issue an invoice (Revenue earned, but not yet received)"""
        return [
            {"account_id": receivable_account_id, "type": EntryType.DEBIT, "amount": amount},
            {"account_id": revenue_account_id, "type": EntryType.CREDIT, "amount": amount}
        ]
