from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict
from accounting.fpa_service import FPAService
from accounting.models import (
    Account,
    AccountType,
    Bill,
    BillStatus,
    EntryType,
    Invoice,
    InvoiceStatus,
    JournalEntry,
    Transaction,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class AccountingDashboardService:
    """
    Service for aggregating accounting metrics for the dashboard.
    """
    def __init__(self, db: Session):
        self.db = db
        self.fpa_service = FPAService(db)

    def get_financial_summary(self, workspace_id: str) -> Dict[str, Any]:
        """
        Calculate high-level financial health KPIs.
        """
        try:
            total_cash = self.fpa_service.get_current_cash_balance(workspace_id)
            
            # Accounts Payable (Open Bills)
            ap_total = self.db.query(func.sum(Bill.amount)).filter(
                Bill.workspace_id == workspace_id,
                Bill.status == BillStatus.OPEN
            ).scalar() or 0.0

            # Accounts Receivable (Open Invoices)
            ar_total = self.db.query(func.sum(Invoice.amount)).filter(
                Invoice.workspace_id == workspace_id,
                Invoice.status == InvoiceStatus.OPEN
            ).scalar() or 0.0

            # Monthly Burn (Average net cash flow over last 3 months)
            # We'll use a simplified version: (Profit/Loss for last 90 days) / 3
            now = datetime.now(timezone.utc)
            three_months_ago = now - timedelta(days=90)
            
            historical_entries = self.db.query(JournalEntry).join(Transaction).filter(
                Transaction.workspace_id == workspace_id,
                Transaction.transaction_date >= three_months_ago,
                Transaction.transaction_date < now
            ).all()

            profit_loss = 0.0
            for entry in historical_entries:
                acc = entry.account
                if acc.type == AccountType.REVENUE:
                    profit_loss += entry.amount if entry.type == EntryType.CREDIT else -entry.amount
                elif acc.type == AccountType.EXPENSE:
                    profit_loss -= entry.amount if entry.type == EntryType.DEBIT else -entry.amount
            
            avg_monthly_net = profit_loss / 3.0
            burn_rate = abs(avg_monthly_net) if avg_monthly_net < 0 else 0
            
            runway_months = (total_cash / burn_rate) if burn_rate > 0 else (12.0 if avg_monthly_net >= 0 else 0)

            return {
                "total_cash": round(total_cash, 2),
                "accounts_payable": round(ap_total, 2),
                "accounts_receivable": round(ar_total, 2),
                "monthly_burn": round(burn_rate, 2),
                "net_profit_avg": round(avg_monthly_net, 2),
                "runway_months": round(runway_months, 1),
                "currency": "USD"
            }
        except Exception as e:
            logger.error(f"Error calculating financial summary: {e}")
            return {
                "error": str(e),
                "total_cash": 0,
                "accounts_payable": 0,
                "accounts_receivable": 0,
                "monthly_burn": 0,
                "runway_months": 0
            }
