import logging
from typing import Dict, Any, List
from datetime import datetime
from core.database import SessionLocal
from accounting.models import Invoice, InvoiceStatus
from core.communication_intelligence import CommunicationIntelligenceService

logger = logging.getLogger(__name__)

class CollectionAgent:
    """
    Autonomous collection agent that handles overdue invoice escalations.
    """

    def __init__(self, db_session: Any = None, intel_service: Any = None):
        self.db = db_session
        self.intel_service = intel_service or CommunicationIntelligenceService(db_session=db_session)

    async def scan_and_collect(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Scans for overdue invoices and triggers appropriate collection actions.
        """
        db = self.db or SessionLocal()
        try:
            overdue_invoices = (
                db.query(Invoice)
                .filter(Invoice.workspace_id == workspace_id)
                .filter(Invoice.status == InvoiceStatus.OPEN)
                .filter(Invoice.due_date < datetime.utcnow())
                .all()
            )
            
            actions_taken = []
            for invoice in overdue_invoices:
                days_overdue = (datetime.utcnow() - invoice.due_date).days
                
                # Escalation logic
                if days_overdue >= 15:
                    intent = "FINAL_NOTICE"
                    priority = "high"
                elif days_overdue >= 8:
                    intent = "FIRM_REMINDER"
                    priority = "medium"
                else:
                    intent = "FRIENDLY_NUDGE"
                    priority = "low"
                
                logger.info(f"Triggering {intent} for Invoice {invoice.id} (Overdue {days_overdue} days)")
                
                comm_data = {
                    "content": f"[SYSTEM TRIGGER: COLLECTION {intent}]",
                    "metadata": {
                        "invoice_id": invoice.id,
                        "customer_id": invoice.customer_id,
                        "days_overdue": days_overdue,
                        "amount_due": invoice.amount,
                        "intent": intent
                    },
                    "app_type": "email" # Emails are better for formal documentation of debt
                }
                
                await self.intel_service.analyze_and_route(comm_data, "system")
                
                actions_taken.append({
                    "invoice_id": invoice.id,
                    "intent": intent,
                    "days_overdue": days_overdue
                })
                
            return actions_taken
        finally:
            if not self.db:
                db.close()
