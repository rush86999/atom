from typing import Any, Dict, List, Optional
from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.resource_manager import resource_monitor
from core.staffing_advisor import staffing_advisor

router = BaseAPIRouter(prefix="/resources", tags=["Resource Management"])

class StaffingRequest(BaseModel):
    description: str
    workspace_id: str
    limit: int = 3

@router.get("/utilization/user/{user_id}")
async def get_user_utilization(user_id: str):
    """Get real-time utilization for a specific user."""
    result = resource_monitor.calculate_utilization(user_id)
    if result.get("status") == "error":
        raise router.not_found_error("User", user_id, details={"reason": result.get("message")})
    return router.success_response(data=result)

@router.get("/utilization/team/{team_id}")
async def get_team_utilization(team_id: str):
    """Get aggregated utilization for an entire team."""
    result = resource_monitor.get_team_utilization(team_id)
    if result.get("status") == "error":
        raise router.not_found_error("Team", team_id, details={"reason": result.get("message")})
    return router.success_response(data=result)

@router.post("/recommend-staff")
async def recommend_staff(request: StaffingRequest):
    """AI-powered staffing recommendation for a project description."""
    recommendations = await staffing_advisor.recommend_staff(request.description, request.workspace_id, request.limit)
    return router.success_response(
        data=recommendations,
        message="Staffing recommendations generated"
    )

@router.get("/summary")
async def get_workspace_resource_summary(workspace_id: str, db: Session = Depends(get_db)):
    """Summary of utilization across the workspace."""
    from core.models import User
    users = db.query(User).filter(User.workspace_id == workspace_id, User.status == "active").all()
    
    summaries = []
    for user in users:
        summaries.append(resource_monitor.calculate_utilization(user.id, db=db))
    
    avg_util = sum(s.get("utilization_percentage", 0) for s in summaries) / len(summaries) if summaries else 0
    high_risk_count = sum(1 for s in summaries if s.get("risk_level") == "high")

    return router.success_response(
        data={
            "workspace_id": workspace_id,
            "average_utilization": round(avg_util, 2),
            "high_risk_count": high_risk_count,
            "resource_count": len(users),
            "details": summaries
        }
    )
