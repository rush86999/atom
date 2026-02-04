import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from accounting.models import Entity, Invoice, InvoiceStatus
from ecommerce.models import EcommerceCustomer
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class CreditRiskEngine:
    def __init__(self, db: Session):
        self.db = db

    def analyze_customer_risk(self, entity_id: str) -> Tuple[float, str]:
        """
        Analyzes payment history to determine risk score (0-100) and level.
        Higher score = Higher Risk.
        """
        # 1. Get all PAID invoices
        invoices = self.db.query(Invoice).filter(
            Invoice.customer_id == entity_id,
        ).all()
        
        if not invoices:
            return 0.0, "unknown" # No history = Neutral/Unknown risk

        total_invoices = len(invoices)
        late_invoices = 0
        total_days_late = 0
        
        open_invoices = [i for i in invoices if i.status != InvoiceStatus.PAID and i.status != InvoiceStatus.VOID]
        current_overdue_amount = 0.0
        
        now = datetime.now(timezone.utc)
        
        # Analyze Paid History
        paid_invoices = [i for i in invoices if i.status == InvoiceStatus.PAID]
        for inv in paid_invoices:
            # Simple logic: Was updated_at > due_date? 
            # (Assuming updated_at is payment date approx)
            if inv.updated_at and inv.due_date and inv.updated_at > inv.due_date:
                late_invoices += 1
                delta = (inv.updated_at - inv.due_date).days
                total_days_late += delta

        # Analyze Current Open
        for inv in open_invoices:
            if inv.due_date and now > inv.due_date:
                current_overdue_amount += inv.amount
                
        # Calculate Score
        # Factor 1: Late Payment Frequency (0-50 pts)
        late_rate = late_invoices / len(paid_invoices) if paid_invoices else 0
        score_freq = late_rate * 50
        
        # Factor 2: Current Overdue Magnitude (0-50 pts)
        # Arbitrary threshold: > $1000 overdue = high risk
        score_overdue = min(50, (current_overdue_amount / 1000) * 50)
        
        total_score = score_freq + score_overdue
        
        # Determine Level
        if total_score < 20:
            level = "low"
        elif total_score < 60:
            level = "medium"
        else:
            level = "high"
            
        logger.info(f"Risk analysis for Entity {entity_id}: Score {total_score} ({level})")
        return total_score, level

    def sync_risk_to_ecommerce(self, entity_id: str):
        """Propagate risk score to EcommerceCustomer linked to this accounting entity"""
        ecomm_customers = self.db.query(EcommerceCustomer).filter(
            EcommerceCustomer.accounting_entity_id == entity_id
        ).all()
        
        score, level = self.analyze_customer_risk(entity_id)
        
        for cust in ecomm_customers:
            cust.risk_score = score
            cust.risk_level = level
            logger.info(f"Updated EcommerceCustomer {cust.email} risk to {level}")
            
        self.db.commit()
