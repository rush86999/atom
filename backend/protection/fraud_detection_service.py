
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from accounting.models import Transaction, TransactionStatus

logger = logging.getLogger(__name__)

class FraudDetectionService:
    def __init__(self, db: Session):
        self.db = db

    def detect_payment_anomalies(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        """
        Scans for irregular payment patterns.
        1. Duplicate charges (same amount, same day).
        2. Excessive short-term refunds.
        """
        alerts = []
        
        # 1. Duplicate Charge Detection
        # Find transactions with same amount and date (ignoring time)
        # Simplified for prototype: Group by (amount, date_str)
        recent_txs = self.db.query(Transaction).filter(
            Transaction.workspace_id == workspace_id,
            Transaction.transaction_date >= datetime.utcnow() - timedelta(days=7),
            Transaction.status == TransactionStatus.POSTED
        ).all()
        
        # Grouping
        seen = {}
        for tx in recent_txs:
            key = (tx.amount, tx.transaction_date.strftime("%Y-%m-%d"), tx.description)
            if key not in seen:
                seen[key] = []
            seen[key].append(tx)
            
        for (amt, date, desc), tx_list in seen.items():
            if len(tx_list) > 1 and amt > 0:
                alerts.append({
                    "type": "duplicate_charge",
                    "severity": "high",
                    "details": f"Potential duplicate charge of ${amt} on {date} for '{desc}'.",
                    "count": len(tx_list)
                })

        # 2. Refund Velocity Check
        refunds = self.db.query(Transaction).filter(
            Transaction.workspace_id == workspace_id,
            Transaction.amount < 0, # Refunds are negative
            Transaction.transaction_date >= datetime.utcnow() - timedelta(hours=24)
        ).all()
        
        if len(refunds) >= 3:
            total_refunded = abs(sum(r.amount for r in refunds))
            alerts.append({
                "type": "refund_spike",
                "severity": "critical",
                "details": f"{len(refunds)} refunds processed in last 24h totaling ${total_refunded}.",
                "action": "halt_payments"
            })
            
        return alerts
