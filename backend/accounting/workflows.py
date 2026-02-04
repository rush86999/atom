import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List
from accounting.models import Entity, Invoice, InvoiceStatus
from sqlalchemy.orm import Session

from core.websockets import manager

logger = logging.getLogger(__name__)

class CollectionAgent:
    """
    Automated agent for monitoring Accounts Receivable and sending follow-ups.
    """

    def __init__(self, db: Session):
        self.db = db

    async def check_overdue_invoices(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Identify invoices that are past their due date and trigger follow-ups.
        """
        now = datetime.utcnow()
        overdue_invoices = self.db.query(Invoice).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status == InvoiceStatus.OPEN,
            Invoice.due_date < now
        ).all()

        reminders_sent = []

        for invoice in overdue_invoices:
            # 1. Update status to OVERDUE
            invoice.status = InvoiceStatus.OVERDUE
            
            # 2. Generate Reminder
            reminder = self._generate_reminder_message(invoice)
            
            # 3. "Send" Reminder (Mock: log and broadcast to UI)
            logger.info(f"Sending reminder for Invoice {invoice.invoice_number} to {invoice.customer.name}")
            
            # Internal notification for the user
            await manager.broadcast(f"workspace:{workspace_id}", {
                "type": "accounting.reminder_sent",
                "data": {
                    "invoice_id": invoice.id,
                    "customer": invoice.customer.name,
                    "amount": invoice.amount,
                    "reminder": reminder
                }
            })

            reminders_sent.append({
                "invoice_id": invoice.id,
                "customer": invoice.customer.name,
                "amount": invoice.amount
            })

        self.db.commit()
        return reminders_sent

    def _generate_reminder_message(self, invoice: Invoice) -> str:
        """AI-assisted (template for now) reminder generation"""
        days_overdue = (datetime.utcnow() - invoice.due_date).days
        return (
            f"Hello {invoice.customer.name}, this is a reminder that Invoice {invoice.invoice_number} "
            f"for ${invoice.amount:,.2f} is now {days_overdue} days overdue. "
            "Please process the payment at your earliest convenience."
        )

    def generate_aging_report(self, workspace_id: str) -> Dict[str, Any]:
        """Generate a summary of AR aging"""
        invoices = self.db.query(Invoice).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.OVERDUE])
        ).all()

        now = datetime.utcnow()
        report = {
            "current": 0.0,      # 0-30 days
            "overdue_30": 0.0,   # 31-60 days
            "overdue_60": 0.0,   # 61-90 days
            "overdue_90": 0.0,   # 90+ days
            "total_ar": 0.0
        }

        for inv in invoices:
            days = (now - inv.due_date).days
            report["total_ar"] += inv.amount
            if days <= 0:
                report["current"] += inv.amount
            elif days <= 30:
                report["overdue_30"] += inv.amount
            elif days <= 60:
                report["overdue_60"] += inv.amount
            else:
                report["overdue_90"] += inv.amount

        return report
