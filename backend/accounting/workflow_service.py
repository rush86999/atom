import logging
from typing import Any, Dict, List
from accounting.models import Account, JournalEntry, Transaction
from sqlalchemy.orm import Session

from core.cross_system_reasoning import get_reasoning_engine
from integrations.asana_service import AsanaService
from integrations.slack_service_unified import SlackUnifiedService

logger = logging.getLogger(__name__)

class FinancialWorkflowService:
    """
    Automates cross-system workflows triggered by financial events.
    Bridges Finance (Zoho/Xero/QBO) with Operations (Asana/Slack/HubSpot).
    """

    def __init__(self, db: Session):
        self.db = db
        self.reasoning = get_reasoning_engine()
        self.asana = AsanaService()
        self.slack = SlackUnifiedService()

    async def handle_transaction_event(self, transaction_id: str):
        """
        Triggered when a new transaction is ingested or its status changes.
        """
        tx = self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not tx:
            return

        # 1. Check for Task Completion
        # If the transaction metadata links to a task (e.g., from Knowledge Graph extraction)
        task_id = tx.metadata_json.get("task_id")
        if task_id:
            logger.info(f"Financial Event: Transaction {tx.id} matches Task {task_id}")
            # Workflow: Mark task as completed if it was a payment for a service
            if tx.amount > 0: # Assuming positive is payment out or incoming revenue
                 # In a real app, we'd check if this is an AR or AP event
                 pass

        # 2. Check for Budget Alerts
        alerts = await self.reasoning.check_financial_integrity(self.db, tx.workspace_id)
        for alert in alerts:
            if alert["type"] == "FINANCIAL_BUDGET_OVERRUN":
                # Workflow: Notify Slack about budget overrun
                # Note: In real scenarios, use slack.post_message with a valid token
                logger.info(f"Workflow Triggered: Slack alert for budget overrun in {tx.workspace_id}")

    async def automate_invoice_to_task(self, workspace_id: str, invoice_data: Dict[str, Any]):
        """
        Example Workflow: When an invoice is created in Zoho, create a reminder task in Asana.
        """
        invoice_no = invoice_data.get("invoice_number")
        amount = invoice_data.get("total")
        
        # Create task in Asana
        result = await self.asana.create_task(
            workspace_id=workspace_id,
            name=f"Follow up on Invoice {invoice_no}",
            notes=f"Payment of ${amount} expected. Linked to Zoho Books invoice."
        )
        return result
