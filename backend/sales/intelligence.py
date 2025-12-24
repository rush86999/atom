import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sales.models import Deal, DealStage
from core.automation_settings import get_automation_settings
from core.websockets import manager

logger = logging.getLogger(__name__)

try:
    from integrations.atom_communication_ingestion_pipeline import ingestion_pipeline, CommunicationAppType
    INGESTION_AVAILABLE = True
except ImportError:
    INGESTION_AVAILABLE = False
    logger.warning("Ingestion pipeline not available. Sales memory will be disabled.")

class SalesIntelligence:
    """
    Analyzes deals to detect risks and health scores.
    """
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_automation_settings()

    async def analyze_deal_health(self, deal: Deal) -> Dict[str, Any]:
        """
        Calculate a composite health score (0-100) for a deal.
        """
        if not self.settings.is_sales_enabled():
            return {"health_score": 0, "risk_level": "disabled"}

        health = 70.0 # Standard starting point
        risks = []

        # 1. Velocity Check (Days in Stage)
        now = datetime.now(timezone.utc)
        days_in_stage = (now - (deal.updated_at or deal.created_at)).days
        if days_in_stage > 14:
            health -= 15
            risks.append("Deal stalled in stage for > 14 days")
        
        # 2. Engagement Check
        if deal.last_engagement_at:
            days_since_engagement = (now - deal.last_engagement_at).days
            if days_since_engagement > 7:
                health -= 20
                risks.append("No engagement in over a week")
        else:
            health -= 30
            risks.append("No recorded engagement")

        # 3. Value Check
        if deal.value > 10000 and deal.probability < 0.3:
            health -= 10
            risks.append("High value deal with low win probability")

        # Clamp score
        deal.health_score = max(0, min(100, health))
        
        if deal.health_score < 40:
            deal.risk_level = "high"
        elif deal.health_score < 70:
            deal.risk_level = "medium"
        else:
            deal.risk_level = "low"

        self.db.commit()

        # Broadcast update
        try:
            await manager.broadcast(f"workspace:{deal.workspace_id}", {
                "type": "deal_update",
                "workspace_id": deal.workspace_id,
                "data": {
                    "id": deal.id,
                    "name": deal.name,
                    "health_score": deal.health_score,
                    "risk_level": deal.risk_level,
                    "risks": risks
                }
            })
        except Exception as e:
            logger.error(f"Failed to broadcast deal update: {e}")

        # Ingest into LanceDB Memory
        if INGESTION_AVAILABLE:
            try:
                ingestion_pipeline.ingest_message(
                    CommunicationAppType.CRM_DEAL.value,
                    {
                        "id": deal.id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "sender": "Sales Intelligence",
                        "subject": f"Deal Health: {deal.name}",
                        "content": f"Deal: {deal.name}. Health Score: {deal.health_score}. Risk Level: {deal.risk_level}. Risks: {', '.join(risks)}",
                        "metadata": {
                            "deal_id": deal.id,
                            "workspace_id": deal.workspace_id,
                            "health_score": deal.health_score,
                            "risk_level": deal.risk_level,
                            "risks": risks
                        }
                    }
                )
            except Exception as e:
                logger.error(f"Failed to ingest deal health into LanceDB: {e}")

        return {
            "health_score": deal.health_score,
            "risk_level": deal.risk_level,
            "risks": risks
        }

    def get_pipeline_forecast(self, workspace_id: str) -> Dict[str, Any]:
        """
        Generate a simple weighted forecast.
        """
        deals = self.db.query(Deal).filter(
            Deal.workspace_id == workspace_id,
            Deal.stage.notin_([DealStage.CLOSED_WON, DealStage.CLOSED_LOST])
        ).all()

        total_weighted = sum(d.value * (d.probability or 0.5) for d in deals)
        total_unweighted = sum(d.value for d in deals)

        return {
            "weighted_pipeline": total_weighted,
            "unweighted_pipeline": total_unweighted,
            "deal_count": len(deals)
        }
