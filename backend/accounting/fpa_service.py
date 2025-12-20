import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from accounting.models import Account, AccountType, Transaction, JournalEntry, EntryType, Bill, BillStatus, Invoice, InvoiceStatus

logger = logging.getLogger(__name__)

class FPAService:
    """
    Service for Strategic FP&A, including cash flow forecasting and scenario modeling.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_current_cash_balance(self, workspace_id: str) -> float:
        """Calculate the total current cash-on-hand"""
        cash_accounts = self.db.query(Account).filter(
            Account.workspace_id == workspace_id,
            Account.type == AccountType.ASSET,
            (Account.name.ilike("%cash%") | Account.name.ilike("%bank%"))
        ).all()

        total_cash = 0.0
        for acc in cash_accounts:
            # Sum of debits - credits for asset accounts
            debits = self.db.query(func.sum(JournalEntry.amount)).filter(
                JournalEntry.account_id == acc.id,
                JournalEntry.type == EntryType.DEBIT
            ).scalar() or 0.0
            
            credits = self.db.query(func.sum(JournalEntry.amount)).filter(
                JournalEntry.account_id == acc.id,
                JournalEntry.type == EntryType.CREDIT
            ).scalar() or 0.0
            
            total_cash += (debits - credits)
        
        return total_cash

    def get_13_week_forecast(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Generate a 13-week weekly cash flow forecast.
        """
        start_date = datetime.utcnow()
        current_cash = self.get_current_cash_balance(workspace_id)
        
        # 1. Analyze historical burn/profit (last 12 weeks)
        lookback = start_date - timedelta(weeks=12)
        historical_entries = self.db.query(JournalEntry).join(Transaction).filter(
            Transaction.workspace_id == workspace_id,
            Transaction.transaction_date >= lookback,
            Transaction.transaction_date < start_date
        ).all()

        weekly_avg_diff = 0.0
        if historical_entries:
            # Very simple: total change / 12 weeks
            # We only care about P&L accounts (Revenue - Expense)
            profit_loss = 0.0
            for entry in historical_entries:
                acc = entry.account
                if acc.type == AccountType.REVENUE:
                    profit_loss += entry.amount if entry.type == EntryType.CREDIT else -entry.amount
                elif acc.type == AccountType.EXPENSE:
                    profit_loss -= entry.amount if entry.type == EntryType.DEBIT else -entry.amount
            
            weekly_avg_diff = profit_loss / 12.0

        # 2. Get known future items
        open_bills = self.db.query(Bill).filter(
            Bill.workspace_id == workspace_id,
            Bill.status == BillStatus.OPEN,
            Bill.due_date >= start_date
        ).all()

        open_invoices = self.db.query(Invoice).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status == InvoiceStatus.OPEN,
            Invoice.due_date >= start_date
        ).all()

        forecast = []
        running_cash = current_cash

        for week in range(1, 14):
            week_start = start_date + timedelta(weeks=week-1)
            week_end = start_date + timedelta(weeks=week)
            
            # Start with historical average
            weekly_change = weekly_avg_diff
            
            # Add discrete known items
            bills_this_week = sum(b.amount for b in open_bills if week_start <= b.due_date < week_end)
            invoices_this_week = sum(i.amount for i in open_invoices if week_start <= i.due_date < week_end)
            
            weekly_change -= bills_this_week
            weekly_change += invoices_this_week
            
            running_cash += weekly_change
            
            forecast.append({
                "week": week,
                "date": week_end.strftime("%Y-%m-%d"),
                "projected_change": weekly_change,
                "projected_balance": running_cash,
                "details": {
                    "inflows": invoices_this_week,
                    "outflows": bills_this_week,
                    "average_burn": weekly_avg_diff
                }
            })

        return forecast

    def run_scenario(self, workspace_id: str, scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run a 'What-If' scenario analysis.
        scenarios: list of dicts like {"name": "Hire Engineer", "weekly_impact": -2000, "start_week": 4}
        """
        base_forecast = self.get_13_week_forecast(workspace_id)
        current_cash = self.get_current_cash_balance(workspace_id)
        
        scenario_forecast = []
        running_cash = current_cash
        
        for base_week in base_forecast:
            week_num = base_week["week"]
            weekly_change = base_week["projected_change"]
            
            # Apply scenario impacts
            impact_total = 0.0
            for scenario in scenarios:
                if week_num >= scenario.get("start_week", 1):
                    impact_total += scenario.get("weekly_impact", 0.0)
            
            weekly_change += impact_total
            running_cash += weekly_change
            
            scenario_forecast.append({
                "week": week_num,
                "date": base_week["date"],
                "projected_balance": running_cash,
                "impact": impact_total,
                "is_scenario": True
            })
            
        return scenario_forecast
