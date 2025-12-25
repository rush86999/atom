
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.database import get_db
from core.risk_prevention import get_risk_services

router = APIRouter()

@router.get("/churn")
async def get_churn_risk(
    workspace_id: str = "default",
    db: Session = Depends(get_db)
):
    """Predict customer churn risks"""
    try:
        services = get_risk_services(db)
        data = await services["churn"].predict_churn_risk(workspace_id)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/financial")
async def get_financial_risk(
    workspace_id: str = "default",
    db: Session = Depends(get_db)
):
    """Get AR delays and Fraud alerts"""
    try:
        services = get_risk_services(db)
        ar_risks = await services["warning"].detect_ar_delays(workspace_id)
        booking_drops = await services["warning"].monitor_booking_drops(workspace_id)
        fraud_alerts = await services["fraud"].detect_anomalies(workspace_id)
        
        return {
            "success": True,
            "data": {
                "ar_delays": ar_risks,
                "booking_anomaly": booking_drops,
                "fraud_alerts": fraud_alerts
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/growth")
async def get_growth_readiness(
    workspace_id: str = "default",
    db: Session = Depends(get_db)
):
    """Check scaling readiness"""
    try:
        services = get_risk_services(db)
        readiness = await services["growth"].check_scaling_readiness(workspace_id)
        return {"success": True, "data": readiness}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
