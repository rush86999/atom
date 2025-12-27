from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from integrations.mcp_service import mcp_service
import logging

router = APIRouter(prefix="/api/sales", tags=["sales"])
logger = logging.getLogger(__name__)

@router.get("/pipeline")
async def get_sales_pipeline(user_id: str = "default_user"):
    """
    Fetch aggregated sales pipeline across Salesforce and HubSpot.
    """
    try:
        pipeline = await mcp_service.execute_tool(
            "local-tools",
            "get_sales_pipeline",
            {},
            {"user_id": user_id}
        )
        return pipeline
    except Exception as e:
        logger.error(f"Error fetching sales pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))
