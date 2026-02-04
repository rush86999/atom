import datetime
import logging
from datetime import timezone
from typing import List, Optional
from accounting.models import Account, AccountType, Entity, EntityType, EntryType, Invoice, InvoiceStatus, JournalEntry, Transaction
from service_delivery.models import Milestone, MilestoneStatus
from sqlalchemy.orm import Session

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

    def recognize_revenue(self, invoice_id: str) -> Optional[Invoice]:
        """
        Move from Deferred Revenue to Revenue upon delivery/acceptance.

        Creates accounting journal entries:
        - Credit Deferred Revenue (liability decreases)
        - Debit Revenue (revenue recognized)

        Updates invoice status to OPEN (ready for payment).
        """
        # Get the invoice
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            logger.warning(f"Invoice {invoice_id} not found")
            return None

        if invoice.status != InvoiceStatus.DRAFT:
            logger.warning(f"Invoice {invoice_id} is not in DRAFT status (current: {invoice.status})")
            return invoice

        # Find or create default accounts
        deferred_revenue_account = self.db.query(Account).filter(
            Account.workspace_id == invoice.workspace_id,
            Account.code == "2200",  # Standard deferred revenue code
        ).first()

        revenue_account = self.db.query(Account).filter(
            Account.workspace_id == invoice.workspace_id,
            Account.code == "4000",  # Standard revenue code
        ).first()

        # Create default accounts if they don't exist
        if not deferred_revenue_account:
            deferred_revenue_account = Account(
                workspace_id=invoice.workspace_id,
                name="Deferred Revenue",
                code="2200",
                type=AccountType.LIABILITY,
                description="Liability for services not yet delivered"
            )
            self.db.add(deferred_revenue_account)
            self.db.flush()

        if not revenue_account:
            revenue_account = Account(
                workspace_id=invoice.workspace_id,
                name="Service Revenue",
                code="4000",
                type=AccountType.REVENUE,
                description="Revenue from service delivery"
            )
            self.db.add(revenue_account)
            self.db.flush()

        # Create transaction header
        transaction = Transaction(
            workspace_id=invoice.workspace_id,
            external_id=invoice.invoice_number,
            source="billing_service",
            transaction_date=datetime.datetime.now(timezone.utc),
            description=f"Revenue recognition for invoice {invoice.invoice_number}",
            amount=invoice.amount,
            metadata_json={"invoice_id": invoice_id, "milestone_id": str(invoice.metadata_json.get("milestone_id"))} if invoice.metadata_json else {"invoice_id": invoice_id}
        )
        self.db.add(transaction)
        self.db.flush()

        # Create journal entries (double-entry)
        # DEBIT Revenue (increases revenue, which is a credit balance account, so we credit it)
        revenue_entry = JournalEntry(
            transaction_id=transaction.id,
            account_id=revenue_account.id,
            type=EntryType.CREDIT,
            amount=invoice.amount,
            description=f"Revenue recognized for invoice {invoice.invoice_number}"
        )
        self.db.add(revenue_entry)

        # CREDIT Deferred Revenue (decreases liability, which is a credit balance account, so we debit it)
        deferred_entry = JournalEntry(
            transaction_id=transaction.id,
            account_id=deferred_revenue_account.id,
            type=EntryType.DEBIT,
            amount=invoice.amount,
            description=f"Deferred revenue recognized for invoice {invoice.invoice_number}"
        )
        self.db.add(deferred_entry)

        # Update invoice status
        invoice.status = InvoiceStatus.OPEN
        invoice.transaction_id = transaction.id

        self.db.commit()
        logger.info(f"Recognized revenue for invoice {invoice.invoice_number}: {invoice.amount}")
        return invoice
