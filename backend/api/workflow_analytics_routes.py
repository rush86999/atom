"""
Workflow Analytics API Routes
"""

import logging
from typing import Any, Dict, Optional

from core.base_routes import BaseAPIRouter

logger = logging.getLogger(__name__)

router = BaseAPIRouter()

@router.get("/analytics")
async def get_workflow_analytics(days: int = 7):
    """Get workflow execution analytics summary"""
    from core.workflow_metrics import metrics
    return metrics.get_summary(days=days)

@router.get("/analytics/recent")
async def get_recent_executions(limit: int = 20):
    """Get recent workflow executions"""
    from core.workflow_metrics import metrics
    return metrics.get_recent_executions(limit=limit)

@router.get("/analytics/{workflow_id}")
async def get_workflow_stats(workflow_id: str):
    """Get stats for a specific workflow"""
    from core.workflow_metrics import metrics
    return metrics.get_workflow_stats(workflow_id)
