import logging
from typing import Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from core.database import get_db_session
from service_delivery.models import Appointment, AppointmentStatus, ProjectTask
from accounting.models import Invoice, InvoiceStatus, Entity
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
        db = self.db or get_db_session()
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

            # Calculate amount using dynamic price lookup
            amount = self._resolve_appointment_price(appt, db)
            if amount is None or amount <= 0:
                logger.warning(
                    f"Cannot determine price for Appointment {appointment_id}. "
                    f"Deposit: ${appt.deposit_amount}, Service: {appt.service_id}. "
                    f"Skipping invoice generation."
                )
                return None
            
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
        db = self.db or get_db_session()
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

            # Resolve or create accounting entity
            customer_id = self._resolve_accounting_entity(order, db)
            if not customer_id:
                logger.error(f"Cannot resolve accounting entity for Order {order_id}")
                return None

            invoice = Invoice(
                workspace_id=order.workspace_id,
                customer_id=customer_id,
                amount=order.total_price,
                status=InvoiceStatus.OPEN,
                issue_date=datetime.utcnow(),
                due_date=datetime.utcnow() + timedelta(days=3),
                description=f"Invoice for Ecommerce Order {order_id} (Status: {order.status})"
            )
            
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

        db = self.db or get_db_session()
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

    def _resolve_appointment_price(self, appointment: Appointment, db: Session) -> Optional[float]:
        """
        Resolve appointment price using priority order:
        1. Deposit amount (if > 0)
        2. Service price from linked BusinessProductService
        3. Appointment metadata (service_price field)
        4. Workspace default service price
        5. Return None if no price found

        Args:
            appointment: Appointment object
            db: Database session

        Returns:
            Price as float, or None if no price found
        """
        # Priority 1: Use deposit amount if set
        if appointment.deposit_amount and appointment.deposit_amount > 0:
            logger.debug(f"Using deposit amount ${appointment.deposit_amount} for appointment {appointment.id}")
            return appointment.deposit_amount

        # Priority 2: Check linked service price
        if appointment.service_id:
            from core.models import BusinessProductService
            service = db.query(BusinessProductService).filter(
                BusinessProductService.id == appointment.service_id
            ).first()
            if service and service.base_price and service.base_price > 0:
                logger.debug(
                    f"Using service price ${service.base_price} from {service.name} "
                    f"for appointment {appointment.id}"
                )
                return service.base_price

        # Priority 3: Check appointment metadata for service_price
        if appointment.metadata_json and isinstance(appointment.metadata_json, dict):
            metadata_price = appointment.metadata_json.get("service_price")
            if metadata_price and metadata_price > 0:
                logger.debug(f"Using metadata price ${metadata_price} for appointment {appointment.id}")
                return metadata_price

        # Priority 4: Check workspace default service price
        if appointment.workspace and appointment.workspace.metadata_json:
            workspace_default = appointment.workspace.metadata_json.get("default_service_price")
            if workspace_default and workspace_default > 0:
                logger.debug(
                    f"Using workspace default price ${workspace_default} "
                    f"for appointment {appointment.id}"
                )
                return workspace_default

        # No price found
        logger.warning(
            f"No price found for appointment {appointment.id} "
            f"(deposit=${appointment.deposit_amount}, service={appointment.service_id})"
        )
        return None

    def _resolve_accounting_entity(self, order: EcommerceOrder, db: Session) -> Optional[str]:
        """
        Resolve or create accounting entity for ecommerce order.

        Priority order:
        1. Use existing accounting_entity_id from customer
        2. Find existing entity by email match
        3. Create new accounting entity from customer data
        4. Return None if cannot resolve

        Args:
            order: EcommerceOrder object
            db: Database session

        Returns:
            Accounting entity ID, or None if cannot resolve
        """
        if not order.customer:
            logger.warning(f"Order {order.id} has no customer linked")
            return None

        # Priority 1: Use existing accounting entity
        if order.customer.accounting_entity_id:
            # Verify it still exists
            entity = db.query(Entity).filter(
                Entity.id == order.customer.accounting_entity_id
            ).first()
            if entity:
                logger.debug(
                    f"Using existing accounting entity {entity.id} "
                    f"for customer {order.customer.email}"
                )
                return entity.id
            else:
                logger.warning(
                    f"Accounting entity {order.customer.accounting_entity_id} "
                    f"not found for customer {order.customer.email}"
                )

        # Priority 2: Try to find existing entity by email
        if order.customer.email:
            existing_entity = db.query(Entity).filter(
                Entity.workspace_id == order.workspace_id,
                Entity.email == order.customer.email,
                Entity.type == "customer"
            ).first()

            if existing_entity:
                # Link it to the ecommerce customer
                order.customer.accounting_entity_id = existing_entity.id
                db.commit()

                logger.info(
                    f"Found and linked existing accounting entity {existing_entity.id} "
                    f"for customer {order.customer.email}"
                )
                return existing_entity.id

        # Priority 3: Create new accounting entity
        try:
            from accounting.models import EntityType

            new_entity = Entity(
                workspace_id=order.workspace_id,
                name=f"{order.customer.first_name or ''} {order.customer.last_name or ''}".strip() or order.customer.email,
                email=order.customer.email,
                phone=order.customer.phone,
                type=EntityType.CUSTOMER,
            )
            db.add(new_entity)
            db.commit()
            db.refresh(new_entity)

            # Link to ecommerce customer
            order.customer.accounting_entity_id = new_entity.id
            db.commit()

            logger.info(
                f"Created new accounting entity {new_entity.id} "
                f"for customer {order.customer.email}"
            )
            return new_entity.id

        except Exception as e:
            logger.error(f"Failed to create accounting entity for order {order.id}: {e}")
            db.rollback()
            return None

        # Priority 4: Cannot resolve
        logger.error(f"Cannot resolve accounting entity for order {order.id}")
        return None

