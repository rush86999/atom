import logging
from typing import Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
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

        Implementation includes:
        1. Task-to-invoice mapping with rate lookup
        2. Hour-based vs fixed-price billing support
        3. Expense attachment to invoice
        4. Tax calculations
        5. Invoice line items with detailed breakdown

        Args:
            task_id: ID of the completed project task

        Returns:
            Invoice object if successful, None otherwise
        """
        from service_delivery.models import Project, Milestone

        db = self.db or SessionLocal()
        try:
            # Get task with relationships
            task = db.query(ProjectTask).filter(ProjectTask.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return None

            # Verify task is completed
            if task.status != "completed":
                logger.warning(f"Task {task_id} is not completed. Status: {task.status}")
                return None

            # Get project and milestone for billing info
            milestone = db.query(Milestone).filter(Milestone.id == task.milestone_id).first()
            if not milestone:
                logger.error(f"Milestone {task.milestone_id} not found for task {task_id}")
                return None

            project = db.query(Project).filter(Project.id == task.project_id).first()
            if not project:
                logger.error(f"Project {task.project_id} not found for task {task_id}")
                return None

            # Prevent double invoicing
            existing = db.query(Invoice).filter(
                Invoice.description.like(f"%Task {task_id}%")
            ).first()
            if existing:
                logger.info(f"Invoice already exists for Task {task_id}")
                return existing

            # Determine billing type and calculate amount
            billing_type = task.metadata_json.get("billing_type", "hourly") if task.metadata_json else "hourly"
            tax_rate = task.metadata_json.get("tax_rate", 0.0) if task.metadata_json else 0.0

            if billing_type == "fixed_price":
                # Fixed-price billing
                task_price = task.metadata_json.get("fixed_price", milestone.amount) if task.metadata_json else milestone.amount
                hours_worked = 0
                hourly_rate = 0
            else:
                # Hourly billing (default)
                # Get hourly rate from milestone or task metadata
                hourly_rate = task.metadata_json.get("hourly_rate", 100.0) if task.metadata_json else 100.0
                hours_worked = task.actual_hours or 0.0
                task_price = hours_worked * hourly_rate

            # Calculate subtotal and tax
            subtotal = task_price
            tax_amount = subtotal * (tax_rate / 100.0)
            total_amount = subtotal + tax_amount

            # Get customer from project's contract or workspace
            customer_id = None
            if project.contract_id:
                from service_delivery.models import Contract
                contract = db.query(Contract).filter(Contract.id == project.contract_id).first()
                if contract and hasattr(contract, 'customer_id'):
                    customer_id = contract.customer_id

            if not customer_id:
                # Fall back to workspace default customer
                customer_id = task.metadata_json.get("customer_id") if task.metadata_json else None

            if not customer_id:
                logger.warning(f"No customer_id found for task {task_id}, cannot create invoice")
                return None

            # Generate invoice number
            invoice_number = self._generate_invoice_number(db, task.workspace_id)

            # Store line item details in metadata (for future InvoiceLineItem table)
            line_items = [
                {
                    "type": "service",
                    "description": task.name,
                    "quantity": hours_worked if billing_type == "hourly" else 1,
                    "unit_price": hourly_rate if billing_type == "hourly" else task_price,
                    "amount": subtotal,
                    "task_id": task_id,
                    "billing_type": billing_type
                }
            ]

            # Add expenses if any
            if task.metadata_json and "expenses" in task.metadata_json:
                for expense in task.metadata_json["expenses"]:
                    expense_amount = expense.get("amount", 0.0)
                    line_items.append({
                        "type": "expense",
                        "description": expense.get("description", "Expense"),
                        "quantity": 1,
                        "unit_price": expense_amount,
                        "amount": expense_amount,
                        "expense_id": expense.get("id")
                    })
                    total_amount += expense_amount

            # Create invoice AFTER calculating total with expenses
            invoice = Invoice(
                workspace_id=task.workspace_id,
                customer_id=customer_id,
                invoice_number=invoice_number,
                issue_date=datetime.utcnow(),
                due_date=datetime.utcnow() + timedelta(days=30),  # Net-30 terms
                amount=total_amount,
                currency="USD",
                status=InvoiceStatus.OPEN,
                description=f"Task: {task.name}\nProject: {project.name}\nMilestone: {milestone.name}\nTask ID: {task_id}",
                # Store line item data in description for now (future: dedicated InvoiceLineItem table)
            )

            # Store line items in invoice metadata (temporary until InvoiceLineItem table exists)
            if not invoice.description:
                invoice.description = ""
            invoice.description += f"\n\nLine Items:\n" + "\n".join([
                f"- {item['description']}: ${item['amount']:.2f}"
                for item in line_items
            ])

            # Store full line items in metadata_json for future use
            if not hasattr(invoice, 'metadata_json'):
                # Add column if not exists (migration needed)
                pass
            else:
                invoice.metadata_json = {
                    "line_items": line_items,
                    "task_id": task_id,
                    "project_id": project.id,
                    "milestone_id": milestone.id,
                    "billing_type": billing_type,
                    "tax_rate": tax_rate,
                    "tax_amount": tax_amount,
                    "subtotal": subtotal
                }

            db.add(invoice)
            db.commit()
            db.refresh(invoice)

            # Update task to indicate it's been invoiced
            if task.metadata_json is None:
                task.metadata_json = {}
            task.metadata_json["invoice_id"] = invoice.id
            task.metadata_json["invoiced_at"] = datetime.utcnow().isoformat()
            db.commit()

            logger.info(
                f"Generated Invoice {invoice.invoice_number} (ID: {invoice.id}) "
                f"for Task {task_id}: ${total_amount:.2f} "
                f"({billing_type}, {hours_worked}h @ ${hourly_rate}/h)"
            )

            return invoice

        except Exception as e:
            logger.error(f"Error invoicing task {task_id}: {e}", exc_info=True)
            db.rollback()
            return None
        finally:
            if not self.db:
                db.close()

    def _generate_invoice_number(self, db: Session, workspace_id: str) -> str:
        """
        Generate a unique invoice number for a workspace.

        Format: INV-YYYYMMDD-XXXX
        Example: INV-20260201-0001

        Args:
            db: Database session
            workspace_id: Workspace ID

        Returns:
            Unique invoice number
        """
        from sqlalchemy import func

        today = datetime.utcnow().strftime("%Y%m%d")

        # Count existing invoices for today
        count = db.query(func.count(Invoice.id)).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.invoice_number.like(f"INV-{today}%")
        ).scalar() or 0

        # Generate sequential number
        sequence = count + 1
        return f"INV-{today}-{sequence:04d}"
