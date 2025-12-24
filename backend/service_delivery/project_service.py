import logging
import datetime
from sqlalchemy.orm import Session
from typing import Optional, Dict
from datetime import timezone

from sales.models import Deal, DealStage
from service_delivery.models import Contract, ContractType, Project, ProjectStatus, Milestone
from accounting.credit_risk_engine import CreditRiskEngine

logger = logging.getLogger(__name__)

class ProjectService:
    def __init__(self, db: Session):
        self.db = db
        self.risk_engine = CreditRiskEngine(db)

    def provision_project_from_deal(self, deal_id: str) -> Optional[Project]:
        """
        Automated Handover: Deal (Won) -> Contract -> Project
        """
        deal = self.db.query(Deal).filter(Deal.id == deal_id).first()
        if not deal:
            logger.error(f"Deal {deal_id} not found")
            return None
            
        if deal.stage != DealStage.CLOSED_WON:
             logger.warning(f"Deal {deal.name} is not Won. Skipping provision.")
             return None

        # 1. Prevent Duplicates
        existing = self.db.query(Contract).filter(Contract.deal_id == deal_id).first()
        if existing:
            logger.info(f"Contract already exists for Deal {deal.name}")
            # Identify the project linked?
            return existing.projects[0] if existing.projects else None

        # 2. Risk Check (Payment-Aware Delivery)
        # We need an entity_id to check risk. Assuming Deal has a pointer or we find it via metadata.
        # For Phase 16 MVP, we'll try to find an accounting Entity linked by name/email
        # Or simplistic: If Deal isn't linked, risk is unknown (low)
        
        initial_status = ProjectStatus.PENDING
        # TODO: Lookup accounting_entity via deal.customer connection
        # If risk > 50, initial_status = PAUSED_PAYMENT
        
        # 3. Create Contract
        contract = Contract(
            workspace_id=deal.workspace_id,
            deal_id=deal.id,
            name=f"Contract for {deal.name}",
            total_amount=deal.value,
            type=ContractType.FIXED_FEE, # Default
            start_date=datetime.datetime.now(timezone.utc)
        )
        self.db.add(contract)
        self.db.flush()
        
        # 4. Create Project
        project = Project(
            workspace_id=deal.workspace_id,
            contract_id=contract.id,
            name=f"Delivery: {deal.name}",
            status=initial_status,
            budget_hours=deal.value / 150.0 # Heuristic: $150/hr rate
        )
        self.db.add(project)
        self.db.flush()
        
        # 5. Create Default Milestone (Kickoff)
        milestone = Milestone(
            workspace_id=deal.workspace_id,
            project_id=project.id,
            name="Project Kickoff (50%)",
            amount=deal.value * 0.5,
            percentage=50.0
        )
        self.db.add(milestone)
        
        self.db.commit()
        self.db.refresh(project)
        
        logger.info(f"Provisioned Project {project.name} from Deal {deal.name}")
        return project

    def check_delivery_gating(self, project_id: str):
        """
        Check if project should be paused due to financial risk
        """
        from service_delivery.delivery_guard import delivery_guard
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project or project.status in [ProjectStatus.COMPLETED, ProjectStatus.CANCELED]:
            return
            
        if project.contract_id:
            risk_data = delivery_guard.check_overdue_risk(project.contract_id, self.db)
            if risk_data.get("risk") == "high":
                project.status = ProjectStatus.PAUSED_PAYMENT
                project.metadata_json = project.metadata_json or {}
                project.metadata_json["pause_reason"] = risk_data.get("reason")
                self.db.commit()
                logger.warning(f"Project {project.name} gated due to payment risk: {risk_data.get('reason')}")
                
                # Notify PM via TeamMessage
                from core.models import TeamMessage, Team
                # Find the team associated with the project's workspace (MVP simplification)
                team = self.db.query(Team).filter(Team.workspace_id == project.workspace_id).first()
                if team:
                    msg = TeamMessage(
                        team_id=team.id,
                        user_id="system", # Reserved system user
                        content=f"🚨 FINANCIAL GATING: Project '{project.name}' has been paused. Reason: {risk_data.get('reason')}",
                        context_type="project",
                        context_id=project.id
                    )
                    self.db.add(msg)
                    self.db.commit()
