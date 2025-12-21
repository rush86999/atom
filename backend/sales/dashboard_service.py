import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from sales.models import Lead, Deal, DealStage, CallTranscript
from sales.intelligence import SalesIntelligence

logger = logging.getLogger(__name__)

class SalesDashboardService:
    """
    Service for aggregating sales metrics for the dashboard.
    """
    def __init__(self, db: Session):
        self.db = db
        self.intelligence = SalesIntelligence(db)

    def get_sales_summary(self, workspace_id: str) -> Dict[str, Any]:
        """
        Calculate high-level sales pipeline KPIs.
        """
        try:
            # Basic counts
            total_leads = self.db.query(func.count(Lead.id)).filter(Lead.workspace_id == workspace_id).scalar() or 0
            converted_leads = self.db.query(func.count(Lead.id)).filter(
                Lead.workspace_id == workspace_id,
                Lead.is_converted == True
            ).scalar() or 0
            
            conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0

            # Deal Pipeline
            active_deals = self.db.query(Deal).filter(
                Deal.workspace_id == workspace_id,
                Deal.stage.notin_([DealStage.CLOSED_WON, DealStage.CLOSED_LOST])
            ).all()

            total_pipeline_value = sum(d.value for d in active_deals)
            weighted_forecast = sum(d.value * (d.probability or 0.5) for d in active_deals)
            
            # High Risk Deals
            high_risk_deals = [d for d in active_deals if (d.health_score or 100) < 40]

            return {
                "total_leads": total_leads,
                "conversion_rate": round(conversion_rate, 1),
                "active_deals_count": len(active_deals),
                "pipeline_value": round(total_pipeline_value, 2),
                "weighted_forecast": round(weighted_forecast, 2),
                "high_risk_deals_count": len(high_risk_deals),
                "deals_by_stage": self._get_deals_by_stage(workspace_id)
            }
        except Exception as e:
            logger.error(f"Error calculating sales summary: {e}")
            return {
                "error": str(e),
                "total_leads": 0,
                "conversion_rate": 0,
                "active_deals_count": 0,
                "pipeline_value": 0,
                "weighted_forecast": 0,
                "high_risk_deals_count": 0
            }

    def _get_deals_by_stage(self, workspace_id: str) -> Dict[str, int]:
        """Helper to count deals in each stage"""
        results = self.db.query(Deal.stage, func.count(Deal.id)).filter(
            Deal.workspace_id == workspace_id
        ).group_by(Deal.stage).all()
        return {stage.value: count for stage, count in results}
