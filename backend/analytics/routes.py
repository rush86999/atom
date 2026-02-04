from typing import Any, Dict, List
from analytics.models import WorkflowExecutionLog
from analytics.optimizer import WorkflowOptimizer
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db

# Router prefix is just "/analytics". 
# The plugin registers it under "/api/v1", resulting in "/api/v1/analytics".
router = APIRouter(prefix="/analytics", tags=["Workflow DNA"])

class OptimizeRequest(BaseModel):
    workflow: Dict[str, Any]

class OptimizeResponse(BaseModel):
    suggestions: List[Dict[str, Any]]

@router.get("/workflows/{workflow_id}/heatmap")
def get_workflow_heatmap(workflow_id: str, db: Session = Depends(get_db)):
    """
    Get aggregated performance metrics for a specific workflow's steps.
    Used to generate the 'Workflow DNA' heatmap.
    """
    # SQL: SELECT step_id, AVG(duration_ms), COUNT(*) ... GROUP BY step_id
    stats = db.query(
        WorkflowExecutionLog.step_id,
        func.avg(WorkflowExecutionLog.duration_ms).label("avg_duration"),
        func.count(WorkflowExecutionLog.id).label("total_runs"),
        func.sum(func.case((WorkflowExecutionLog.status == 'FAILED', 1), else_=0)).label("fail_count")
    ).filter(
        WorkflowExecutionLog.workflow_id == workflow_id
    ).group_by(
        WorkflowExecutionLog.step_id
    ).all()
    
    # Format as a dictionary map: { step_id: { metrics } }
    heatmap = {}
    for step_id, avg, total, fails in stats:
        heatmap[step_id] = {
            "avg_duration": round(avg or 0, 2),
            "total_runs": total,
            "failure_rate": round(fails / total, 2) if total > 0 else 0,
            "status": "red" if (avg > 5000 or (fails/total) > 0.1) else "green" 
            # Simple heuristic: >5s or >10% fail = Red
        }
        
    return heatmap

@router.get("/workflows/{workflow_id}/logs")
def get_workflow_logs(workflow_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """
    Get detailed execution logs for a specific workflow.
    """
    logs = db.query(WorkflowExecutionLog).filter(
        WorkflowExecutionLog.workflow_id == workflow_id
    ).order_by(
        WorkflowExecutionLog.created_at.desc()
    ).limit(limit).all()
    
    return [
        {
            "id": log.id,
            "step_id": log.step_id,
            "status": log.status,
            "duration_ms": log.duration_ms,
            "created_at": log.created_at,
            "trigger_data": log.trigger_data,  # Now supported
            "results": log.results             # Now supported
        }
        for log in logs
    ]

@router.get("/stats/glance")
def get_global_stats(db: Session = Depends(get_db)):
    """Quick stats for the dashboard"""
    total = db.query(func.count(WorkflowExecutionLog.id)).scalar()
    return {"total_steps_analyzed": total}

@router.post("/optimize")
def optimize_workflow(request: OptimizeRequest):
    """
    Analyze a workflow definition and return optimization suggestions.
    This is a static analysis that doesn't run the workflow.
    """
    try:
        optimizer = WorkflowOptimizer()
        suggestions = optimizer.analyze(request.workflow)
        
        # Convert dataclasses to dicts for JSON response
        results = [
            {
                "type": s.type,
                "description": s.description,
                "affected_nodes": s.affected_nodes,
                "savings_estimate_ms": s.savings_estimate_ms,
                "action": s.action
            }
            for s in suggestions
        ]
        
        return OptimizeResponse(suggestions=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
