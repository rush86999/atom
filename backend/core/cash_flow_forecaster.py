import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from accounting.models import (
    Account,
    AccountType,
    Bill,
    BillStatus,
    Invoice,
    InvoiceStatus,
    Transaction,
)
from sqlalchemy import func

from core.database import get_db_session

logger = logging.getLogger(__name__)

class CashFlowForecastingService:
    """
    Provides autonomous financial forecasting for small businesses.
    """

    def __init__(self, db_session: Any = None):
        self.db = db_session

    def get_runway_prediction(self, workspace_id: str) -> Dict[str, Any]:
        """
        Calculates runway and burn rate based on ledger and open obligations.
        """
        db = self.db or get_db_session()
        try:
            # 1. Current Cash Balance (Asset accounts with 'cash' in name or mapped as such)
            cash_accounts = (
                db.query(Account)
                .filter(Account.workspace_id == workspace_id)
                .filter(Account.type == AccountType.ASSET)
                .all()
            )
            
            # Simple heuristic: sum of all asset accounts for now
            # In a real system, we'd check balances via JournalEntries
            total_cash = 0.0
            for acc in cash_accounts:
                # Mock balance sum for demonstration
                # In production, we'd query: select sum(amount) from journal_entries where account_id = acc.id
                pass
            
            # For the prototype, we search transactions in the last 30 days
            last_30_days = datetime.utcnow() - timedelta(days=30)
            
            # 2. Historical Monthly Burn (Expenses)
            monthly_expenses = (
                db.query(func.sum(Transaction.amount))
                .filter(Transaction.workspace_id == workspace_id)
                .filter(Transaction.transaction_date >= last_30_days)
                .filter(Transaction.amount < 0) # Assuming negative is outflow
                .scalar() or 0.0
            ) / 1.0 # 1 month
            
            monthly_burn = abs(monthly_expenses)
            
            # 3. Pending Inflow (Open Invoices)
            pending_inflow = (
                db.query(func.sum(Invoice.amount))
                .filter(Invoice.workspace_id == workspace_id)
                .filter(Invoice.status == InvoiceStatus.OPEN)
                .scalar() or 0.0
            )
            
            # 4. Pending Outflow (Open Bills)
            pending_outflow = (
                db.query(func.sum(Bill.amount))
                .filter(Bill.workspace_id == workspace_id)
                .filter(Bill.status == BillStatus.OPEN)
                .scalar() or 0.0
            )
            
            # 5. Runway Calculation
            # Simplified: (Cash + Pending Inflow - Pending Outflow) / Monthly Burn
            # Let's assume a starting cash for the prototype if none found in ledger
            current_liquidity = total_cash + pending_inflow - pending_outflow
            if total_cash == 0 and pending_inflow == 0:
                 # If no data, return neutral
                 current_liquidity = 0.0
            
            runway_months = current_liquidity / monthly_burn if monthly_burn > 0 else float('inf')
            
            return {
                "current_liquidity": current_liquidity,
                "monthly_burn": monthly_burn,
                "runway_months": round(runway_months, 1) if runway_months != float('inf') else "Indefinite",
                "risk_level": "high" if runway_months < 3 else "medium" if runway_months < 6 else "low"
            }
        finally:
            if not self.db:
                db.close()

    def simulate_scenario(self, workspace_id: str, monthly_cost_increase: float = 0.0, one_time_inflow: float = 0.0) -> Dict[str, Any]:
        """
        Simulates the impact of financial changes (e.g., hiring, new funding).
        """
        base_metrics = self.get_runway_prediction(workspace_id)
        
        new_burn = base_metrics["monthly_burn"] + monthly_cost_increase
        new_liquidity = base_metrics["current_liquidity"] + one_time_inflow
        
        new_runway = new_liquidity / new_burn if new_burn > 0 else float('inf')
        
        return {
            "original_runway": base_metrics["runway_months"],
            "simulated_runway": round(new_runway, 1) if new_runway != float('inf') else "Indefinite",
            "delta_months": (new_runway - base_metrics["runway_months"]) if isinstance(base_metrics["runway_months"], (int, float)) and new_runway != float('inf') else 0
        }
