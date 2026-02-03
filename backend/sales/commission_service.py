import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from accounting.models import Entity, Invoice, InvoiceStatus
from sales.models import CommissionEntry, CommissionStatus, Deal, DealStage
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Feature flags
COMMISSION_AUTO_CALCULATE = os.getenv("COMMISSION_AUTO_CALCULATE", "true").lower() == "true"

class CommissionService:
    def __init__(self, db: Session):
        self.db = db
        self.default_rate = 0.10 # 10% default commission

    def process_invoice_payment(self, invoice_id: str) -> Optional[CommissionEntry]:
        """
        Evaluates an invoice for commission eligibility when it is paid.
        """
        # Check if commission calculation is enabled
        if not COMMISSION_AUTO_CALCULATE:
            logger.info(f"Commission auto-calculation is disabled (COMMISSION_AUTO_CALCULATE=false)")
            return None

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

        # Method 1: Parse deal_id from invoice description
        if invoice.description and "Deal:" in invoice.description:
            # Parse "Deal: UUID" format from description
            match = re.search(r'Deal:\s*([a-f0-9-]+)', invoice.description, re.IGNORECASE)
            if match:
                deal_id = match.group(1)
                logger.info(f"Extracted deal_id {deal_id} from invoice description")

        # Method 2: Check invoice metadata
        if not deal_id and invoice.metadata_json:
            deal_id = invoice.metadata_json.get('deal_id')
            if deal_id:
                logger.info(f"Found deal_id {deal_id} in invoice metadata")

        # Method 3: Check customer metadata for CRM deal link
        if not deal_id and invoice.customer and invoice.customer.metadata_json:
            deal_id = invoice.customer.metadata_json.get('crm_deal_id')
            if deal_id:
                logger.info(f"Found deal_id {deal_id} in customer metadata")

        # Method 4: Fallback - Find most recent Closed Won deal for this customer
        if not deal_id and invoice.customer:
            # Look for deals with matching customer name or within last 60 days
            sixty_days_ago = datetime.now(timezone.utc) - timedelta(days=60)

            # Try to match by customer name in deal metadata
            from sqlalchemy import or_
            deal = self.db.query(Deal).filter(
                Deal.workspace_id == invoice.workspace_id,
                Deal.stage == DealStage.CLOSED_WON,
                Deal.closed_date >= sixty_days_ago
            ).order_by(Deal.closed_date.desc()).first()

            if deal:
                # Check if deal is associated with this customer via metadata
                deal_customer_id = None
                if deal.metadata_json:
                    deal_customer_id = deal.metadata_json.get('customer_id')

                # Link if customer IDs match or if deal is in the same workspace
                if deal_customer_id == invoice.customer.id:
                    deal_id = deal.id
                    logger.info(f"Linked invoice to deal {deal_id} via customer match")

        # Verification Script will need to populate deal links for existing invoices
        # For now, if we still can't find a deal, skip commission
            
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
