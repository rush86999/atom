import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from accounting.models import Entity, Invoice, InvoiceStatus
from service_delivery.models import Contract, Project, ProjectStatus
from sqlalchemy.orm import Session

from core.database import SessionLocal

logger = logging.getLogger(__name__)

class DeliveryGuard:
    """
    Service for protecting delivery margins by gating work based on payment status.
    """

    def check_overdue_risk(self, contract_id: str, db: Session = None) -> Dict[str, Any]:
        """Checks for OVERDUE invoices linked to the contract's customer."""
        if not db:
            db = SessionLocal()
        
        try:
            contract = db.query(Contract).filter(Contract.id == contract_id).first()
            if not contract:
                return {"risk": "unknown", "reason": "Contract not found"}

            # For MVP, we look for entities with the same name as the contract or deal
            # In a real system, there would be a direct customer_id mapping
            customer_name = contract.name.split("for")[-1].strip() if "for" in contract.name else None
            
            if not customer_name:
                return {"risk": "low", "reason": "No customer associated with contract"}

            overdue_invoices = db.query(Invoice).join(Entity).filter(
                Entity.name.ilike(f"%{customer_name}%"),
                Invoice.status == InvoiceStatus.OVERDUE,
                Invoice.workspace_id == contract.workspace_id
            ).all()

            if overdue_invoices:
                total_overdue = sum(inv.amount for inv in overdue_invoices)
                return {
                    "risk": "high",
                    "reason": f"Customer has {len(overdue_invoices)} overdue invoices totaling ${total_overdue}",
                    "overdue_amount": total_overdue
                }
            
            return {"risk": "low", "reason": "No overdue invoices found"}
        finally:
            if not db:
                db.close()

    def pause_high_risk_projects(self, workspace_id: str, db: Session = None) -> List[str]:
        """Iterates through projects and pauses those with high payment risk."""
        if not db:
            db = SessionLocal()
        
        paused_projects = []
        try:
            projects = db.query(Project).filter(
                Project.workspace_id == workspace_id,
                Project.status == ProjectStatus.ACTIVE
            ).all()

            for project in projects:
                if project.contract_id:
                    risk_data = self.check_overdue_risk(project.contract_id, db)
                    if risk_data.get("risk") == "high":
                        project.status = ProjectStatus.PAUSED_PAYMENT
                        project.metadata_json = project.metadata_json or {}
                        project.metadata_json["pause_reason"] = risk_data.get("reason")
                        paused_projects.append(project.id)
                        logger.warning(f"Project {project.name} paused due to financial risk: {risk_data.get('reason')}")
            
            if paused_projects:
                db.commit()
            return paused_projects
        finally:
            if not db:
                db.close()

delivery_guard = DeliveryGuard()
