import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from accounting.models import Invoice, Entity, TaxNexus, InvoiceStatus

logger = logging.getLogger(__name__)

class TaxService:
    """
    Automated service for tax compliance and nexus detection.
    """

    def __init__(self, db: Session):
        self.db = db

    async def detect_nexus(self, workspace_id: str) -> List[str]:
        """
        Identify jurisdictions where the business may have a tax nexus 
        based on customer locations and sales volume.
        """
        # 1. Group sales by region (assuming address is in Entity)
        # For MVP, we'll parse the address field for state/country keywords
        invoices = self.db.query(Invoice).join(Entity, Invoice.customer_id == Entity.id).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status != InvoiceStatus.VOID
        ).all()

        region_sales = {}
        for inv in invoices:
            address = inv.customer.address or ""
            # Simple heuristic: last part of address might be State/Country
            parts = [p.strip() for p in address.split(",") if p.strip()]
            region = parts[-1] if parts else "Unknown"
            
            region_sales[region] = region_sales.get(region, 0) + inv.amount

        new_nexuses = []
        # Example threshold: $500 in sales in a region triggers nexus warning
        THRESHOLD = 500.0 
        
        for region, total in region_sales.items():
            if region == "Unknown": continue
            
            if total >= THRESHOLD:
                # Check if nexus already exists
                existing = self.db.query(TaxNexus).filter(
                    TaxNexus.workspace_id == workspace_id,
                    TaxNexus.region == region
                ).first()
                
                if not existing:
                    logger.info(f"New Tax Nexus detected in {region} (Sales: ${total})")
                    nexus = TaxNexus(
                        workspace_id=workspace_id,
                        region=region,
                        tax_type="Sales Tax"
                    )
                    self.db.add(nexus)
                    new_nexuses.append(region)

        self.db.commit()
        return new_nexuses

    def estimate_tax_liability(self, workspace_id: str, period: str = None) -> Dict[str, Any]:
        """
        Estimate outstanding sales tax liability.
        """
        # For MVP, we'll assume a flat 7% tax for regions where nexus exists
        # and sales haven't explicitly recorded tax yet.
        nexuses = self.db.query(TaxNexus).filter(
            TaxNexus.workspace_id == workspace_id,
            TaxNexus.is_active == True
        ).all()
        
        nexus_regions = [n.region for n in nexuses]
        
        invoices = self.db.query(Invoice).join(Entity, Invoice.customer_id == Entity.id).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status != InvoiceStatus.VOID
        ).all()

        total_liability = 0.0
        breakdown = {}

        for inv in invoices:
            address = inv.customer.address or ""
            parts = [p.strip() for p in address.split(",") if p.strip()]
            region = parts[-1] if parts else "Unknown"
            
            if region in nexus_regions:
                # Mock calculation: 7% of invoice amount
                tax = inv.amount * 0.07 
                total_liability += tax
                breakdown[region] = breakdown.get(region, 0) + tax

        return {
            "total_estimated_liability": total_liability,
            "currency": "USD",
            "breakdown": breakdown
        }
