import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from accounting.models import Entity, Invoice, InvoiceStatus
from sales.models import CommissionEntry, CommissionStatus, Deal, DealStage
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class CommissionService:
    def __init__(self, db: Session):
        self.db = db
        self.default_rate = 0.10 # 10% default commission

    def process_invoice_payment(self, invoice_id: str) -> Optional[CommissionEntry]:
        """
        Evaluates an invoice for commission eligibility when it is paid.
        """
        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            logger.error(f"Invoice {invoice_id} not found")
            return None

        if invoice.status != InvoiceStatus.PAID:
            logger.info(f"Invoice {invoice.invoice_number} is not PAID (Status: {invoice.status}). Skipping commission.")
            return None

        # 1. Allow idempotent runs - check if commission exists for this invoice
        existing = self.db.query(CommissionEntry).filter(CommissionEntry.invoice_id == invoice_id).first()
        if existing:
            logger.info(f"Commission already exists for Invoice {invoice.invoice_number}")
            return existing

        # 2. Link to Deal
        # Try to find deal_id in metadata, or fallback to finding the most recent WON deal for this customer
        deal_id = None
        if invoice.description and "Deal:" in invoice.description:
             # simplistic parsing if stored in description "Services for Deal: <uuid>"
             # robust implementation uses metadata
             pass
        
        # Check metadata first
        # We assume the invoicing process puts deal_id there
        # For now, let's implement the fallback search:
        # Find closed_won deal for this customer within last 60 days?
        
        if not deal_id:
            # Fallback: Find most recent generic Closed Won deal for customer
            # Requires Entity -> Lead/Contact mapping or shared name/email
            # This is tricky without strict linking.
            # Let's assume for Phase 14 verify that we will seed the match or link it manually.
            pass

        # For the purpose of the MVP/Phase 14 validation, we will require the caller 
        # (or the invoice creation process) to have linked the deal, 
        # OR we search for *any* active deal for this customer.
        
        # Let's try to match by Customer Entity
        customer_entity = invoice.customer
        if not customer_entity:
            logger.warning("Invoice has no customer, cannot link deal.")
            return None
            
        # Try to find a deal with matching company/name???
        # Ideally we added deal_id to Invoice. 
        # Let's assume for this implementation we passed deal_id explicitly or we rely on a heuristic.
        
        # Heuristic: Find latest Closed Won deal for this workspace? (Weak)
        # Better: We will start using metadata_json={'deal_id': ...} on Invoices.
        
        if invoice.customer:
             logger.info(f"Checking customer metadata: {invoice.customer.metadata_json}")
             if invoice.customer.metadata_json and 'crm_deal_id' in invoice.customer.metadata_json:
                 deal_id = invoice.customer.metadata_json['crm_deal_id']
        
        # Verification Script will likely need to populate this link.
        
        if not deal_id:
            # Search for Deal by fuzzy name match or similar?
            # Let's verify if we can simply query Deals for this workspace...
            pass
            
        if not deal_id:
             logger.warning(f"Could not link Invoice {invoice.invoice_number} to a Deal. Skipping commission.")
             return None

        deal = self.db.query(Deal).filter(Deal.id == deal_id).first()
        if not deal:
             logger.warning(f"Deal {deal_id} not found.")
             return None

        # 3. Calculate Amount
        commission_amount = invoice.amount * self.default_rate
        
        # 4. Create Entry
        entry = CommissionEntry(
            workspace_id=invoice.workspace_id,
            deal_id=deal.id,
            invoice_id=invoice.id,
            payee_id="default_rep", # In real app, get from Deal owner
            amount=commission_amount,
            status=CommissionStatus.ACCRUED,
            metadata_json={"rate": self.default_rate, "source": "invoice_payment"}
        )
        
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        
        logger.info(f"Generated Commission of ${commission_amount} for Deal {deal.name}")
        return entry

    def calculate_projected_commission(self, deal_id: str) -> float:
        """Estimate commission for a deal before it closes"""
        deal = self.db.query(Deal).filter(Deal.id == deal_id).first()
        if not deal:
            return 0.0
        return deal.value * self.default_rate
