
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.database import get_db
from core.financial_forensics import get_forensics_services

router = APIRouter()

@router.get("/vendor-drift")
async def get_vendor_drift(
    workspace_id: str = "default",
    db: Session = Depends(get_db)
):
    """Detect vendors with increasing costs"""
    try:
        services = get_forensics_services(db)
        drift_data = await services["vendor"].detect_price_drift(workspace_id)
        return {"success": True, "data": drift_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pricing-opportunities")
async def get_pricing_opportunities(
    workspace_id: str = "default",
    db: Session = Depends(get_db)
):
    """Get recommendations for price optimization"""
    try:
        services = get_forensics_services(db)
        opportunities = await services["pricing"].get_pricing_recommendations(workspace_id)
        return {"success": True, "data": opportunities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subscription-waste")
async def get_subscription_waste(
    workspace_id: str = "default",
    db: Session = Depends(get_db)
):
    """Identify unused subscriptions"""
    try:
        services = get_forensics_services(db)
        waste_data = await services["waste"].find_zombie_subscriptions(workspace_id)
        return {"success": True, "data": waste_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
