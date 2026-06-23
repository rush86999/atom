"""
Workflow Analytics API Routes
"""

import logging
from typing import Any, Dict, Optional

from fastapi import Depends

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/workflows", tags=["Workflow Analytics"])

@router.get("/analytics")
async def get_workflow_analytics(days: int = 7, current_user: User = Depends(get_current_user)):
    """Get workflow execution analytics summary"""
    from core.workflow_metrics import metrics
    return metrics.get_summary(days=days)

@router.get("/analytics/recent")
async def get_recent_executions(limit: int = 20, current_user: User = Depends(get_current_user)):
    """Get recent workflow executions"""
    from core.workflow_metrics import metrics
    return metrics.get_recent_executions(limit=limit)

@router.get("/analytics/{workflow_id}")
async def get_workflow_stats(workflow_id: str, current_user: User = Depends(get_current_user)):
    """Get stats for a specific workflow"""
    from core.workflow_metrics import metrics
    return metrics.get_workflow_stats(workflow_id)
