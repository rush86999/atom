
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from accounting.models import Invoice, InvoiceStatus
from sales.models import Deal, DealStage

logger = logging.getLogger(__name__)

class EarlyWarningSystem:
    def __init__(self, db: Session):
        self.db = db

    def monitor_financial_health(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Monitors valid leading indicators of trouble.
        1. AR Aging (invoices taking longer to pay).
        2. Booking Velocity Drops (sudden stop in new deals).
        """
        alerts = []
        
        # 1. Accounts Receivable (AR) Aging Check
        # Find overdue invoices
        overdue_invoices = self.db.query(Invoice).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status == InvoiceStatus.OVERDUE
        ).all()
        
        if overdue_invoices:
            # Calculate average days overdue
            total_days = 0
            for inv in overdue_invoices:
                due = inv.due_date.replace(tzinfo=None) if inv.due_date else datetime.utcnow()
                total_days += (datetime.utcnow() - due).days
            
            avg_overdue = total_days / len(overdue_invoices)
            
            if avg_overdue > 15: # Alert if avg overdue is > 2 weeks
                alerts.append({
                    "type": "ar_delay",
                    "severity": "medium",
                    "metric": "Average Days Overdue",
                    "current_value": round(avg_overdue, 1),
                    "threshold": 15,
                    "action": "Trigger automated dunning sequence."
                })

        # 2. Booking Velocity Drop
        # Compare deals created in last 7 days vs previous 7 days
        now = datetime.utcnow()
        last_7_days = self.db.query(func.count(Deal.id)).filter(
            Deal.workspace_id == workspace_id,
            Deal.created_at >= now - timedelta(days=7)
        ).scalar() or 0
        
        prev_7_days = self.db.query(func.count(Deal.id)).filter(
            Deal.workspace_id == workspace_id,
            Deal.created_at >= now - timedelta(days=14),
            Deal.created_at < now - timedelta(days=7)
        ).scalar() or 0
        
        if prev_7_days > 5 and last_7_days == 0: # Hard stop check
             alerts.append({
                "type": "booking_drop",
                "severity": "high",
                "details": "Zero new deals created in last 7 days (vs active previous week).",
                "action": "Check lead sources or sales team activity."
            })
            
        return alerts
