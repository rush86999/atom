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

    def _assess_project_risk_and_set_status(self, deal) -> 'ProjectStatus':
        """
        Assess project risk and return appropriate initial status.
        Considers multiple factors to determine if project should be gated.

        Risk Factors:
        1. Deal risk_level (from sales intelligence)
        2. Deal value (higher value = higher risk)
        3. Deal health_score (lower health = higher risk)
        4. Customer payment history (if available)
        5. Deal probability at close (low probability = uncertain commitment)

        Returns:
            ProjectStatus: PENDING (normal), PAUSED_PAYMENT (high risk), or ON_HOLD (very high risk)
        """
        from service_delivery.models import ProjectStatus

        risk_score = 0
        risk_factors = []

        # Factor 1: Deal risk_level (0-30 points)
        deal_risk_level = deal.risk_level or "low"
        if deal_risk_level == "high":
            risk_score += 30
            risk_factors.append("high_deal_risk")
        elif deal_risk_level == "medium":
            risk_score += 15
            risk_factors.append("medium_deal_risk")
        # low risk adds 0 points

        # Factor 2: Deal value (0-25 points)
        # Higher value deals have more financial exposure
        deal_value = deal.value or 0
        if deal_value > 100000:  # >$100K
            risk_score += 25
            risk_factors.append("high_value_deal")
        elif deal_value > 50000:  # >$50K
            risk_score += 15
            risk_factors.append("medium_value_deal")
        elif deal_value > 10000:  # >$10K
            risk_score += 5
            risk_factors.append("moderate_value_deal")

        # Factor 3: Deal health_score (0-20 points)
        # Lower health score indicates customer engagement issues
        health_score = deal.health_score or 50
        if health_score < 30:
            risk_score += 20
            risk_factors.append("very_low_health_score")
        elif health_score < 50:
            risk_score += 10
            risk_factors.append("low_health_score")
        elif health_score < 70:
            risk_score += 5
            risk_factors.append("moderate_health_score")

        # Factor 4: Deal probability at close (0-15 points)
        # Low probability even at close indicates uncertain commitment
        probability = deal.probability or 100
        if probability < 70:
            risk_score += 15
            risk_factors.append("low_close_probability")
        elif probability < 90:
            risk_score += 5
            risk_factors.append("moderate_close_probability")

        # Factor 5: Check for customer payment history if accounting entity linked
        # (0-10 points)
        try:
            # Try to find accounting entity by deal name or metadata
            from accounting.models import Entity
            entity = self.db.query(Entity).filter(
                Entity.name.ilike(f"%{deal.name}%")
            ).first()

            if entity:
                # Check credit risk from accounting module
                credit_risk = self.risk_engine.get_entity_risk_score(entity.id)
                if credit_risk > 70:  # High credit risk
                    risk_score += 10
                    risk_factors.append("high_credit_risk")
                elif credit_risk > 50:  # Medium credit risk
                    risk_score += 5
                    risk_factors.append("medium_credit_risk")
        except Exception as e:
            # If accounting entity check fails, continue without this factor
            logger.debug(f"Could not check accounting entity risk: {e}")

        # Determine status based on risk score
        # Total possible risk score: 100
        # Thresholds:
        # - 0-40: LOW risk -> PENDING (normal flow)
        # - 41-60: MEDIUM risk -> PENDING with monitoring (metadata flag)
        # - 61+: HIGH/CRITICAL risk -> PAUSED_PAYMENT (gated)

        if risk_score >= 61:
            status = ProjectStatus.PAUSED_PAYMENT
            logger.warning(
                f"HIGH/CRITICAL RISK detected for deal {deal.name}: "
                f"score={risk_score}, factors={risk_factors}. "
                f"Project status set to PAUSED_PAYMENT pending risk mitigation."
            )
        elif risk_score >= 41:
            status = ProjectStatus.PENDING
            logger.info(
                f"MEDIUM risk detected for deal {deal.name}: "
                f"score={risk_score}, factors={risk_factors}. "
                f"Project will proceed with enhanced monitoring."
            )
        else:
            status = ProjectStatus.PENDING
            logger.info(
                f"LOW risk for deal {deal.name}: "
                f"score={risk_score}. Project proceeding normally."
            )

        return status

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

        # 2. Risk Assessment (Payment-Aware Delivery)
        # Evaluate project risk based on multiple factors to determine appropriate gating
        initial_status = self._assess_project_risk_and_set_status(deal)
        
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
