import logging
import datetime
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import timezone

from service_delivery.models import Milestone, MilestoneStatus
from accounting.models import Invoice, InvoiceStatus, Entity, EntityType

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self, db: Session):
        self.db = db

    def generate_invoice_for_milestone(self, milestone_id: str) -> Optional[Invoice]:
        """
        Triggered when Milestone is APPROVED.
        Generates a Draft Invoice.
        """
        milestone = self.db.query(Milestone).filter(Milestone.id == milestone_id).first()
        if not milestone:
            return None
            
        if milestone.status != MilestoneStatus.APPROVED:
            logger.warning(f"Milestone {milestone.name} is not APPROVED. Cannot invoice.")
            return None
            
        if milestone.invoice_id:
            logger.info(f"Milestone {milestone.name} already invoiced.")
            return self.db.query(Invoice).filter(Invoice.id == milestone.invoice_id).first()

        # Find Customer (via Project -> Contract -> Deal -> ??)
        # For Phase 16 MVP verification, we'll Create a placeholder customer or use a default one
        # Ideally, Project/Contract should store `customer_entity_id`
        
        # Placeholder Logic: Find ANY customer in workspace implementation
        customer = self.db.query(Entity).filter(
            Entity.workspace_id == milestone.workspace_id,
            Entity.type == EntityType.CUSTOMER
        ).first()
        
        if not customer:
            # Create a shell customer
            customer = Entity(
                workspace_id=milestone.workspace_id,
                name="Unknown Project Client", 
                type=EntityType.CUSTOMER
            )
            self.db.add(customer)
            self.db.flush()

        # Create Invoice
        invoice = Invoice(
            workspace_id=milestone.workspace_id,
            customer_id=customer.id,
            invoice_number=f"INV-MS-{milestone.id[:8]}",
            issue_date=datetime.datetime.now(timezone.utc),
            due_date=datetime.datetime.now(timezone.utc) + datetime.timedelta(days=30),
            amount=milestone.amount,
            status=InvoiceStatus.DRAFT,
            description=f"Billing for Milestone: {milestone.name}"
        )
        self.db.add(invoice)
        self.db.flush()
        
        # Update Milestone
        milestone.invoice_id = invoice.id
        milestone.status = MilestoneStatus.INVOICED
        
        self.db.commit()
        logger.info(f"Generated Invoice {invoice.invoice_number} for Milestone {milestone.name}")
        return invoice

    def recognize_revenue(self, invoice_id: str):
        """
        Move from Deferred Revenue to Revenue upon delivery/acceptance.
        (Skipping full ledger logic for this specific step to keep scope focused on Service Delivery flow)
        """
        pass
