from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.automation_insight_manager import get_insight_manager
from core.behavior_analyzer import get_behavior_analyzer

router = APIRouter(prefix="/api/v1/automation", tags=["automation_insights"])

@router.get("/insights")
async def get_automation_insights(current_user: Any = Depends(get_current_user)):
    """Get drift metrics and health insights for all workflows"""
    manager = get_insight_manager()
    insights = manager.generate_all_insights(current_user.id)
    return insights

@router.get("/suggestions")
async def get_automation_suggestions(current_user: Any = Depends(get_current_user)):
    """Get proactive workflow suggestions based on user behavior"""
    analyzer = get_behavior_analyzer()
    patterns = analyzer.detect_patterns(current_user.id)
    return {
        "suggestions": patterns,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/insights/track-override")
async def track_manual_override(
    payload: Dict[str, Any],
    current_user: Any = Depends(get_current_user)
):
    """Manually track an override (fallback if automatic tracking is missed)"""
    from core.workflow_analytics_engine import get_analytics_engine
    analytics = get_analytics_engine()
    
    workflow_id = payload.get("workflow_id")
    execution_id = payload.get("execution_id")
    resource_id = payload.get("resource_id")
    action = payload.get("action", "manual_override")
    
    if not all([workflow_id, resource_id]):
        raise HTTPException(status_code=400, detail="Missing workflow_id or resource_id")
        
    analytics.track_manual_override(
        workflow_id=workflow_id,
        execution_id=execution_id or "manual",
        resource_id=resource_id,
        action=action,
        user_id=current_user.id,
        metadata={"manual": True}
    )
    
    return {"success": True}
