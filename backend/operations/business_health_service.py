
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from ecommerce.models import EcommerceOrder
from sales.models import Lead, LeadStatus
from accounting.models import Bill, Invoice, BillStatus, InvoiceStatus

logger = logging.getLogger(__name__)

class BusinessHealthService:
    def __init__(self, db: Session):
        self.db = db

    def get_business_health_score(self, workspace_id: str = "default") -> Dict[str, Any]:
        """
        Calculates a 0-100 health score based on key operational metrics.
        """
        score = 100
        deductions = []

        # 1. Cash Flow Check (Simulated for now, real implementation would check Bank Account balances)
        # For now, we check if there are more overdue bills than open invoices
        overdue_bills = self.db.query(func.count(Bill.id)).filter(
            Bill.workspace_id == workspace_id,
            Bill.status == BillStatus.OPEN,
            Bill.due_date < datetime.utcnow()
        ).scalar() or 0

        open_invoices_amt = self.db.query(func.sum(Invoice.amount)).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status == InvoiceStatus.OPEN
        ).scalar() or 0.0
        
        pending_bills_amt = self.db.query(func.sum(Bill.amount)).filter(
            Bill.workspace_id == workspace_id,
            Bill.status == BillStatus.OPEN
        ).scalar() or 0.0

        if overdue_bills > 0:
            penalty = min(overdue_bills * 5, 20)
            score -= penalty
            deductions.append(f"Overdue Bills (-{penalty})")

        if pending_bills_amt > (open_invoices_amt * 1.2): # If payables are significantly higher than receivables
            score -= 10
            deductions.append("High Payables Ratio (-10)")

        # 2. Pipeline Velocity
        stagnant_leads = self.db.query(func.count(Lead.id)).filter(
            Lead.workspace_id == workspace_id,
            Lead.status == LeadStatus.NEW,
            Lead.updated_at < datetime.utcnow() - timedelta(days=7)
        ).scalar() or 0
        
        if stagnant_leads > 5:
            score -= 10
            deductions.append("Stagnant Leads (-10)")

        # 3. Fulfillment Bottlenecks
        unfulfilled_orders = self.db.query(func.count(EcommerceOrder.id)).filter(
            EcommerceOrder.workspace_id == workspace_id,
            EcommerceOrder.status == 'paid', # Paid but not yet fulfilled
            EcommerceOrder.updated_at < datetime.utcnow() - timedelta(days=3)
        ).scalar() or 0
        
        if unfulfilled_orders > 0:
            penalty = min(unfulfilled_orders * 5, 20)
            score -= penalty
            deductions.append(f"Delayed Fulfillment (-{penalty})")

        return {
            "score": max(0, score),
            "deductions": deductions,
            "metrics": {
                "overdue_bills_count": overdue_bills,
                "cash_ratio": round(open_invoices_amt / (pending_bills_amt + 1), 2),
                "stagnant_leads": stagnant_leads,
                "delayed_orders": unfulfilled_orders
            }
        }

    def get_daily_priorities(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        """
        Returns a sorted list of actionable items for the business owner.
        """
        priorities = []

        # 1. Critical: Orders Awaiting Review (Safety Gate)
        review_orders = self.db.query(EcommerceOrder).filter(
            EcommerceOrder.workspace_id == workspace_id,
            EcommerceOrder.status == 'awaiting_review'
        ).all()
        
        for order in review_orders:
            priorities.append({
                "type": "order_review",
                "priority": "critical", # Top of list
                "title": f"Review Draft Order {order.order_number}",
                "description": f"AI Confidence: {order.confidence_score}. Requires approval.",
                "link": f"/orders/{order.id}",
                "timestamp": order.created_at
            })

        # 2. High: Overdue Bills
        overdue_bills = self.db.query(Bill).filter(
            Bill.workspace_id == workspace_id,
            Bill.status == BillStatus.OPEN,
            Bill.due_date < datetime.utcnow()
        ).all()
        
        for bill in overdue_bills:
            priorities.append({
                "type": "overdue_bill",
                "priority": "high",
                "title": f"Pay Overdue Bill {bill.bill_number}",
                "description": f"Due on {bill.due_date.strftime('%Y-%m-%d')} Amount: ${bill.amount}",
                "link": f"/finance/bills/{bill.id}",
                "timestamp": bill.due_date
            })

        # 3. Medium: Hot Leads
        hot_leads = self.db.query(Lead).filter(
            Lead.workspace_id == workspace_id,
            Lead.status == LeadStatus.NEW,
            Lead.ai_score > 0.8
        ).limit(5).all()
        
        for lead in hot_leads:
            priorities.append({
                "type": "hot_lead",
                "priority": "medium",
                "title": f"Contact Hot Lead: {lead.email}",
                "description": f"AI Score: {lead.ai_score}. {lead.ai_qualification_summary[:50] if lead.ai_qualification_summary else ''}...",
                "link": f"/sales/leads/{lead.id}",
                "timestamp": lead.created_at
            })

        # Sort by urgency (manual mapping)
        priority_map = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        priorities.sort(key=lambda x: priority_map.get(x["priority"], 99))
        
        return priorities

    def calculate_cash_runway(self, workspace_id: str = "default") -> Dict[str, Any]:
        """
        Estimates runway days. 
        Note: This is a simplifed projection. Real implementation requires bank integration.
        """
        # 1. Calculate average monthly burn (Expense transactions last 30 days)
        # For simplicity, we'll sum posted Bill amounts for now, or use a mock logic if transaction data is sparse
        
        # Mock logic for the prototype
        current_balance = 50000.0 # Placeholder
        monthly_burn = 10000.0 # Placeholder
        
        days_runway = int((current_balance / monthly_burn) * 30)
        
        return {
            "days_runway": days_runway,
            "estimated_balance": current_balance,
            "monthly_burn_rate": monthly_burn,
            "status": "healthy" if days_runway > 90 else "warning" if days_runway > 30 else "critical"
        }
