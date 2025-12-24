import logging
from sqlalchemy.orm import Session
from ecommerce.models import Subscription
from ecommerce.models import EcommerceCustomer
from saas.churn_detector import ChurnRiskDetector
from core.database import SessionLocal

logger = logging.getLogger(__name__)

class RetentionService:
    """
    Maintains customer health by monitoring churn signals.
    """

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    def run_daily_churn_check(self, workspace_id: str = None) -> int:
        """
        Check all active subscriptions for churn signals.
        """
        query = self.db.query(Subscription).filter(Subscription.status == "active")
        if workspace_id:
            query = query.filter(Subscription.workspace_id == workspace_id)
        
        subs = query.all()
        detector = ChurnRiskDetector(self.db)
        flagged_count = 0

        for sub in subs:
            risk_data = detector.predict_churn_risk(sub.id)
            if risk_data.get("risk_level") in ["high", "medium"]:
                customer = self.db.query(EcommerceCustomer).filter(EcommerceCustomer.id == sub.customer_id).first()
                if customer:
                    customer.risk_level = risk_data["risk_level"]
                    customer.risk_score = float(risk_data["risk_score"])
                    
                    if risk_data["risk_score"] > 70:
                        self._trigger_retention_playbook(sub, risk_data)
                    
                    flagged_count += 1
        
        self.db.commit()
        return flagged_count

    def _trigger_retention_playbook(self, sub: Subscription, risk_data: dict):
        """
        Triggers an automated retention workflow.
        """
        logger.warning(f"CRITICAL CHURN RISK for {sub.id}: {risk_data['reason']}")
        
        # Triggering via orchestrator (Conceptual integration)
        # In a real environment, we'd enqueue a background task
        # For MVP, we use the message system directly to notify CSM/Owner
        from core.models import TeamMessage, Team
        team = self.db.query(Team).filter(Team.workspace_id == sub.workspace_id).first()
        if team:
            msg = TeamMessage(
                team_id=team.id,
                user_id="system",
                content=f"🆘 RETENTION ALERT: Customer {sub.customer_id} is at high risk of churn! Reason: {risk_data['reason']}. Starting Retention Playbook."
            )
            self.db.add(msg)

retention_service = RetentionService()
