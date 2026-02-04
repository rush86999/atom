import logging
from typing import Any, Dict, List
from core.base_routes import BaseAPIRouter
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from integrations.mcp_service import mcp_service

router = BaseAPIRouter(prefix="/api/sales", tags=["sales"])
logger = logging.getLogger(__name__)

@router.get("/pipeline")
async def get_sales_pipeline(
    user_id: str = "default_user",
    db: Session = Depends(get_db)
):
    """
    Fetch aggregated sales pipeline from Postgres Cache (Sync Strategy).
    Aggregates data from all connected CRMs (Salesforce, HubSpot, etc).
    """
    try:
        from saas.models import IntegrationMetric

        # Query cached metrics
        metrics = db.query(IntegrationMetric).filter(
            IntegrationMetric.workspace_id == "default",
            IntegrationMetric.metric_key.in_(["pipeline_value", "active_opportunities_count", "active_deals_count"])
        ).all()

        total_value = 0.0
        total_deals = 0

        for m in metrics:
            if m.metric_key == "pipeline_value":
                total_value += float(m.value) if m.value else 0.0
            elif m.metric_key in ["active_opportunities_count", "active_deals_count"]:
                total_deals += int(m.value) if m.value else 0
        
        return {
            "pipeline_value": total_value,
            "active_deals": total_deals,
            "currency": "USD",
            "source": "synced_database"
        }
            
    except Exception as e:
        logger.error(f"Error fetching sales pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/summary")
async def get_sales_dashboard_summary(user_id: str = "default_user"):
    """
    Alias for pipeline stats (Synced), matching Frontend expectations.
    """
    return await get_sales_pipeline(user_id)

