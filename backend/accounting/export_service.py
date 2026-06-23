import csv
import io
import json
import logging
from datetime import datetime
from typing import Any, Dict, List
from accounting.models import Account, EntryType, JournalEntry, Transaction
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# CSV injection protection. Spreadsheet applications (Excel, LibreOffice, GSheets)
# interpret cell values beginning with = + - @ or containing tab/newline as formulas
# or actions. Prefixing with a single quote (') forces text interpretation and the
# quote is stripped on display by spreadsheet apps. See CWE-1236.
_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_csv_cell(value: object) -> object:
    """Neutralize CSV-injection payloads in a cell value.

    - Strings beginning with = + - @ or containing tab/CR are prefixed with a single quote.
    - Non-string values (numbers, None) are returned unchanged.
    """
    if not isinstance(value, str):
        return value
    if value.startswith(_CSV_INJECTION_PREFIXES):
        return "'" + value
    return value

class AccountExporter:
    """
    Service for exporting financial data in formats suitable for CPAs and external accountants.
    """

    def __init__(self, db: Session):
        self.db = db

    def export_general_ledger_csv(self, workspace_id: str) -> str:
        """Export all journal entries in a detailed flat CSV format"""
        entries = self.db.query(JournalEntry).join(Transaction).join(Account).filter(
            Account.workspace_id == workspace_id
        ).order_by(Transaction.transaction_date).all()

        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header with GAAP/IFRS context
        writer.writerow([
            "Date", "Transaction ID", "Account Code", "Account Name", 
            "GAAP Map", "IFRS Map", "Debit", "Credit", "Description", "Currency"
        ])

        for entry in entries:
            acc = entry.account
            tx = entry.transaction
            
            debit = entry.amount if entry.type == EntryType.DEBIT else 0
            credit = entry.amount if entry.type == EntryType.CREDIT else 0
            
            standards = acc.standards_mapping or {}
            
            writer.writerow([
                _sanitize_csv_cell(tx.transaction_date.strftime("%Y-%m-%d")),
                _sanitize_csv_cell(tx.id),
                _sanitize_csv_cell(acc.code),
                _sanitize_csv_cell(acc.name),
                _sanitize_csv_cell(standards.get("gaap", "")),
                _sanitize_csv_cell(standards.get("ifrs", "")),
                debit,
                credit,
                _sanitize_csv_cell(entry.description or tx.description),
                _sanitize_csv_cell(entry.currency)
            ])

        return output.getvalue()

    def export_trial_balance_json(self, workspace_id: str) -> Dict[str, Any]:
        """Export summarized balances for all accounts"""
        accounts = self.db.query(Account).filter(Account.workspace_id == workspace_id).all()
        
        report = {
            "workspace_id": workspace_id,
            "export_date": datetime.utcnow().isoformat(),
            "standard": "Multi-Standard (GAAP/IFRS Ready)",
            "accounts": []
        }

        for acc in accounts:
            debits = self.db.query(func.sum(JournalEntry.amount)).filter(
                JournalEntry.account_id == acc.id,
                JournalEntry.type == EntryType.DEBIT
            ).scalar() or 0.0
            
            credits = self.db.query(func.sum(JournalEntry.amount)).filter(
                JournalEntry.account_id == acc.id,
                JournalEntry.type == EntryType.CREDIT
            ).scalar() or 0.0
            
            balance = debits - credits
            
            report["accounts"].append({
                "code": acc.code,
                "name": acc.name,
                "type": acc.type.value,
                "debits": debits,
                "credits": credits,
                "net_balance": balance,
                "mapping": acc.standards_mapping
            })

        return report
