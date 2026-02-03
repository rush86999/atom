import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from accounting.models import Entity, EntityType, Invoice, InvoiceStatus
from sales.models import Deal
from service_delivery.models import Contract, ContractType, Milestone, MilestoneStatus, Project
from sqlalchemy.orm import Session

from core.database import get_db_session

logger = logging.getLogger(__name__)

class BillingOrchestrator:
    """
    Automates invoice generation from completed milestones.
    """

    async def process_milestone_completion(self, milestone_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        """
        Generates an invoice for a completed milestone if not already invoiced.
        """
        logger.info(f"Processing billing for milestone {milestone_id}")
        
        with get_db_session() as db:
            # 1. Fetch Milestone and context
            milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
            if not milestone:
                return {"status": "error", "message": "Milestone not found"}
            
            if milestone.status == MilestoneStatus.INVOICED:
                return {"status": "success", "message": "Milestone already invoiced", "invoice_id": milestone.invoice_id}

            project = db.query(Project).filter(Project.id == milestone.project_id).first()
            if not project:
                return {"status": "error", "message": "Project not found"}
            
            contract = db.query(Contract).filter(Contract.id == project.contract_id).first()
            if not contract:
                 # Internal projects might not have a contract
                 return {"status": "skipped", "message": "No contract associated with project"}

            # 2. Calculate Amount
            amount = milestone.amount
            if amount <= 0 and milestone.percentage > 0:
                amount = (milestone.percentage / 100.0) * contract.total_amount
            
            if amount <= 0:
                return {"status": "skipped", "message": "Milestone has no billable amount"}

            # 3. Resolve Customer (Entity)
            customer = self._get_or_create_customer(db, contract, workspace_id)
            
            # 4. Create Invoice
            invoice = Invoice(
                id=f"inv_{uuid.uuid4().hex[:8]}",
                workspace_id=workspace_id,
                customer_id=customer.id,
                invoice_number=f"INV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
                issue_date=datetime.now(),
                due_date=datetime.now() + timedelta(days=30),
                amount=amount,
                currency=contract.currency or "USD",
                status=InvoiceStatus.DRAFT,
                description=f"Automated Billing for Milestone: {milestone.name} (Project: {project.name})"
            )
            db.add(invoice)
            
            # 5. Link Milestone to Invoice
            milestone.invoice_id = invoice.id
            milestone.status = MilestoneStatus.INVOICED
            db.add(milestone)
            
            db.commit()
            
            logger.info(f"Successfully generated invoice {invoice.id} for milestone {milestone_id}")
            return {
                "status": "success",
                "invoice_id": invoice.id,
                "amount": amount,
                "customer_name": customer.name
            }

    def _get_or_create_customer(self, db: Session, contract: Contract, workspace_id: str = "default") -> Entity:
        """Finds or creates an accounting Entity for the client"""
        # Search by name first (simplified)
        customer_name = contract.name or "Unknown Customer"
        if contract.deal_id:
            deal = db.query(Deal).filter(Deal.id == contract.deal_id).first()
            if deal:
                customer_name = f"Client for {deal.name}"

        entity = db.query(Entity).filter(
            Entity.workspace_id == workspace_id,
            Entity.name == customer_name,
            Entity.type == EntityType.CUSTOMER
        ).first()

        if not entity:
            entity = Entity(
                id=f"ent_{uuid.uuid4().hex[:8]}",
                workspace_id=workspace_id,
                name=customer_name,
                type=EntityType.CUSTOMER
            )
            db.add(entity)
            db.flush()
        
        return entity

# Global Instance
billing_orchestrator = BillingOrchestrator()
