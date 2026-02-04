import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
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
            await self._handle_payment_task_completion(tx, task_id)

        # 2. Check for Budget Alerts
        alerts = await self.reasoning.check_financial_integrity(self.db, tx.workspace_id)
        for alert in alerts:
            if alert["type"] == "FINANCIAL_BUDGET_OVERRUN":
                # Workflow: Notify Slack about budget overrun
                # Note: In real scenarios, use slack.post_message with a valid token
                logger.info(f"Workflow Triggered: Slack alert for budget overrun in {tx.workspace_id}")

    async def _handle_payment_task_completion(self, tx: Transaction, task_id: str):
        """
        Handle task completion when a payment is received.

        This method checks if the transaction represents an Accounts Receivable (AR) payment
        and marks the associated task as completed.

        Args:
            tx: The transaction that triggered this workflow
            task_id: The ID of the linked task
        """
        try:
            # Check transaction type from metadata
            tx_type = tx.metadata_json.get("transaction_type", "").lower()
            is_payment_received = (
                tx_type == "ar_payment" or
                tx_type == "payment_received" or
                tx.metadata_json.get("is_ar_payment", False) or
                (tx.amount > 0 and tx.description and any(
                    keyword in tx.description.lower() for keyword in
                    ["payment received", "invoice payment", "customer payment"]
                ))
            )

            if not is_payment_received:
                logger.info(f"Transaction {tx.id} is not an AR payment, skipping task completion")
                return

            logger.info(f"Processing AR payment {tx.id} for task {task_id} completion")

            # Get task details from Asana
            try:
                task_result = await self.asana.get_task(task_id)
                if not task_result or task_result.get("completed"):
                    logger.info(f"Task {task_id} already completed or not found")
                    return
            except Exception as e:
                logger.warning(f"Could not fetch task {task_id} from Asana: {e}")
                # Continue anyway - try to mark as completed

            # Mark task as completed in Asana
            completion_result = await self.asana.complete_task(
                task_id=task_id,
                completed_at=datetime.now().isoformat()
            )

            if completion_result.get("success"):
                logger.info(f"Successfully marked task {task_id} as completed due to payment {tx.id}")

                # Update transaction metadata with completion audit trail
                if not tx.metadata_json:
                    tx.metadata_json = {}

                tx.metadata_json.update({
                    "task_completion": {
                        "task_id": task_id,
                        "completed_at": datetime.now().isoformat(),
                        "completed_by": "workflow_automation",
                        "trigger_transaction_id": tx.id,
                        "completion_reason": "payment_received"
                    }
                })

                self.db.commit()

                # Optionally notify in Slack
                workspace_id = tx.workspace_id
                message = (
                    f"✅ Task {task_id} automatically marked as completed\n"
                    f"Payment: {tx.amount} ({tx.description or 'No description'})\n"
                    f"Transaction ID: {tx.id}"
                )
                logger.info(f"Workflow completion: {message}")

            else:
                logger.warning(f"Failed to mark task {task_id} as completed: {completion_result}")

        except Exception as e:
            logger.error(f"Error handling payment task completion for transaction {tx.id}, task {task_id}: {e}")
            # Don't raise - we don't want to fail the transaction processing
            # due to workflow automation issues

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
