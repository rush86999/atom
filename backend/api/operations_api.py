
import logging
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.auth import User, get_current_user
from core.base_routes import BaseAPIRouter
from core.business_health_service import business_health_service
from core.database import get_db
from core.personal_scope import (
    DocumentScopeResolutionError,
    DocumentScopeUnavailable,
    resolve_document_workspace_id,
)

router = BaseAPIRouter(prefix="/api/operations", tags=["Operations"])
logger = logging.getLogger(__name__)

class SimulationRequest(BaseModel):
    decision_type: str
    parameters: Dict[str, Any]


def _resolve_workspace_or_403(current_user: User) -> str:
    """Authoritative workspace for an authenticated dashboard read.

    Mirrors the direct forensics endpoints: persisted binding first,
    bootstrap-only Personal Edition fallback, and a hard failure for any other
    unbound account instead of a literal ``"default"`` workspace.
    """
    try:
        workspace_id = resolve_document_workspace_id(current_user)
    except (DocumentScopeUnavailable, DocumentScopeResolutionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No workspace scope is bound to this account",
        ) from exc
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No workspace scope is bound to this account",
        )
    return str(workspace_id)


@router.get("/dashboard")
async def get_dashboard_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all data for the Owner Cockpit"""
    workspace_id = _resolve_workspace_or_403(current_user)
    try:
        # We inject DB into service instance if needed using dependency,
        # but the service is currently a singleton managing its own sessions or receiving DB.
        # Ideally we refactor service to accept DB in methods.
        # For now, using the singleton pattern as defined.

        priorities = await business_health_service.get_daily_priorities(workspace_id)
        metrics = business_health_service.get_health_metrics(workspace_id)

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
            message="Failed to get dashboard data"
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
    current_user: User = Depends(get_current_user),
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
            message="Failed to run simulation"
        )
