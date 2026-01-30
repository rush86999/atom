
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

from core.database import get_db
from core.business_health_service import business_health_service

router = APIRouter()

class SimulationRequest(BaseModel):
    decision_type: str
    parameters: Dict[str, Any]

@router.get("/dashboard")
async def get_dashboard_data(
    db: Session = Depends(get_db)
):
    """Get all data for the Owner Cockpit"""
    try:
        # We inject DB into service instance if needed using dependency, 
        # but the service is currently a singleton managing its own sessions or receiving DB.
        # Ideally we refactor service to accept DB in methods.
        # For now, using the singleton pattern as defined.
        
        priorities = await business_health_service.get_daily_priorities("default")
        metrics = business_health_service.get_health_metrics("default")
        
        return {
            "success": True,
            "briefing": priorities,
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulate")
async def run_simulation(
    request: SimulationRequest
):
    """Run a business simulation"""
    try:
        result = await business_health_service.simulate_decision(
            "default", 
            request.decision_type, 
            request.parameters
        )
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
