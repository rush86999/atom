
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import logging

from core.database import get_db
from core.business_health_service import business_health_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Governance feature flags
OPERATIONS_GOVERNANCE_ENABLED = os.getenv("OPERATIONS_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

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
    request: SimulationRequest,
    agent_id: Optional[str] = None
):
    """
    Run a business simulation.

    **Governance**: Requires INTERN+ maturity for business simulations.
    """
    # Governance check for business simulations
    if OPERATIONS_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="run_simulation",
                resource_type="business_simulation",
                complexity=2  # MODERATE - business simulation
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for run_simulation by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    try:
        result = await business_health_service.simulate_decision(
            "default",
            request.decision_type,
            request.parameters
        )
        logger.info(f"Business simulation run by agent {agent_id or 'system'}: {request.decision_type}")
        return {"success": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
