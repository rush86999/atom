
import logging
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.base_routes import BaseAPIRouter
from core.business_health_service import business_health_service
from core.database import get_db

router = BaseAPIRouter(prefix="/api/operations", tags=["Operations"])
logger = logging.getLogger(__name__)

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

        return router.success_response(
            data={
                "briefing": priorities,
                "metrics": metrics
            },
            message="Dashboard data retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise router.internal_error(
            message=f"Failed to get dashboard data: {str(e)}"
        )

@router.post("/simulate")
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="run_simulation",
    feature="operations"
)
async def run_simulation(
    request: SimulationRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Run a business simulation.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    - Business simulation is a moderate action
    - Requires INTERN maturity or higher
    """
    try:
        result = await business_health_service.simulate_decision(
            "default",
            request.decision_type,
            request.parameters
        )
        logger.info(f"Business simulation run: {request.decision_type}")
        return router.success_response(
            data=result,
            message="Simulation completed successfully"
        )
    except Exception as e:
        logger.error(f"Error running simulation: {e}")
        raise router.internal_error(
            message=f"Failed to run simulation: {str(e)}"
        )
