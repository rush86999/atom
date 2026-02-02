import logging
from typing import Optional, Any
from datetime import datetime, timedelta
from core.database import SessionLocal
from service_delivery.models import Appointment, AppointmentStatus, ProjectTask
from accounting.models import Invoice, InvoiceStatus
from ecommerce.models import EcommerceOrder

logger = logging.getLogger(__name__)

class AutoInvoicer:
    """
    Automates invoice generation for service completions.
    """

    def __init__(self, db_session: Any = None):
        self.db = db_session

    def invoice_appointment(self, appointment_id: str) -> Optional[Invoice]:
        """
        Creates an invoice for a completed appointment.
        """
        db = self.db or SessionLocal()
        try:
            appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appt:
                logger.error(f"Appointment {appointment_id} not found")
                return None

            if appt.status != AppointmentStatus.COMPLETED:
                logger.warning(f"Appointment {appointment_id} is not COMPLETED. Status: {appt.status}")
                return None

            # Prevent double invoicing
            existing = db.query(Invoice).filter(Invoice.description.like(f"%Appointment {appointment_id}%")).first()
            if existing:
                logger.info(f"Invoice already exists for Appointment {appointment_id}")
                return existing

            # Calculate amount
            # If deposit was 0, we might need to look up service price.
            # For the prototype, we use deposit_amount or a default.
            amount = appt.deposit_amount if appt.deposit_amount > 0 else 100.0 # Default fallback
            
            invoice = Invoice(
                workspace_id=appt.workspace_id,
                customer_id=appt.customer_id,
                amount=amount,
                status=InvoiceStatus.OPEN,
                issue_date=datetime.utcnow(),
                due_date=datetime.utcnow() + timedelta(days=7),
                description=f"Service for Appointment {appointment_id} on {appt.start_time.date()}"
            )
            
            db.add(invoice)
            db.commit()
            db.refresh(invoice)
            
            logger.info(f"Generated Invoice {invoice.id} for Appointment {appointment_id}")
            return invoice
        finally:
            if not self.db:
                db.close()

    def invoice_ecommerce_order(self, order_id: str) -> Optional[Invoice]:
        """
        Creates an invoice for a pending ecommerce order.
        """
        db = self.db or SessionLocal()
        try:
            order = db.query(EcommerceOrder).filter(EcommerceOrder.id == order_id).first()
            if not order:
                logger.error(f"EcommerceOrder {order_id} not found")
                return None

            # Support invoicing for 'pending' (pre-payment) or 'fulfilled' (post-shipping)
            # Most product businesses invoice after fulfillment (shipping).
            if order.status not in ["pending", "fulfilled"]:
                logger.warning(f"Order {order_id} is in status {order.status}. Skipping invoicing.")
                return None

            # Prevent double invoicing
            existing = db.query(Invoice).filter(Invoice.description.like(f"%Order {order_id}%")).first()
            if existing:
                return existing

            invoice = Invoice(
                workspace_id=order.workspace_id,
                customer_id=order.customer.accounting_entity_id if order.customer else None,
                amount=order.total_price,
                status=InvoiceStatus.OPEN,
                issue_date=datetime.utcnow(),
                due_date=datetime.utcnow() + timedelta(days=3),
                description=f"Invoice for Ecommerce Order {order_id} (Status: {order.status})"
            )
            
            # If the order doesn't have an accounting entity linked yet, we might need a resolver step.
            # For the prototype, we assume the link exists or will be handled.
            
            db.add(invoice)
            db.commit()
            db.refresh(invoice)
            
            logger.info(f"Generated Invoice {invoice.id} for Order {order_id}")
            return invoice
        finally:
            if not self.db:
                db.close()

    def invoice_project_task(self, task_id: str) -> Optional[Invoice]:
        """
        Creates an invoice for a completed billable task.

        TODO: Implement task-to-invoice mapping logic
        This requires:
        1. Mapping task billable hours to invoice line items
        2. Applying task rates and pricing rules
        3. Handling task metadata and custom fields

        For now, this method is a placeholder for future implementation.

        Args:
            task_id: ID of the completed project task

        Returns:
            Invoice object if implemented, None currently

        Raises:
            NotImplementedError: Until task invoicing is fully implemented
        """
        from core.exceptions import NotImplementedError

        logger.warning(
            f"Task invoicing not yet implemented for task {task_id}. "
            "Using placeholder logic - see invoice_project_task() for details"
        )

        db = self.db or SessionLocal()
        try:
            task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
            if not task:
                return None

            if task.status != "completed":
                return None

            # TODO: Implement task-to-invoice mapping
            # For MVP, we're creating a basic invoice structure
            # Full implementation requires:
            # - Task rate lookup
            # - Hour-based vs fixed-price billing
            # - Expense attachment
            # - Tax calculations

            # Placeholder: Return None to indicate not yet implemented
            return None

        finally:
            if not self.db:
                db.close()
