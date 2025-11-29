from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel
import io
import csv
import logging

from core.analytics_engine import get_analytics_engine

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)

class WorkflowTrackRequest(BaseModel):
    workflow_id: str
    workflow_name: str
    success: bool
    duration_seconds: float
    time_saved_seconds: float = 0.0
    business_value: float = 0.0

class IntegrationTrackRequest(BaseModel):
    integration_name: str
    success: bool
    response_time_ms: float

@router.get("/workflows")
async def get_workflow_analytics():
    """Get workflow performance metrics"""
    engine = get_analytics_engine()
    return engine.get_workflow_analytics()

@router.get("/integrations")
async def get_integration_health():
    """Get integration health status"""
    engine = get_analytics_engine()
    return engine.get_integration_health()

@router.get("/business-value")
async def get_business_value():
    """Get business value metrics"""
    engine = get_analytics_engine()
    wf_analytics = engine.get_workflow_analytics()
    return {
        "total_value": wf_analytics["total_business_value"],
        "total_time_saved_hours": wf_analytics["total_time_saved_hours"],
        "currency": "USD"
    }

@router.get("/dashboard")
async def get_dashboard_data():
    """Get combined dashboard data"""
    engine = get_analytics_engine()
    wf_analytics = engine.get_workflow_analytics()
    int_health = engine.get_integration_health()
    
    return {
        "workflows": wf_analytics,
        "integrations": int_health,
        "summary": {
            "total_executions": wf_analytics["total_executions"],
            "total_value": wf_analytics["total_business_value"],
            "active_integrations": int_health["ready_count"]
        }
    }

@router.post("/track/workflow")
async def track_workflow(request: WorkflowTrackRequest, background_tasks: BackgroundTasks):
    """Track a workflow execution"""
    engine = get_analytics_engine()
    # Run in background to not block response
    background_tasks.add_task(
        engine.track_workflow_execution,
        workflow_id=request.workflow_id,
        success=request.success,
        duration_seconds=request.duration_seconds,
        time_saved_seconds=request.time_saved_seconds,
        business_value=request.business_value
    )
    return {"status": "queued"}

@router.post("/track/integration")
async def track_integration(request: IntegrationTrackRequest, background_tasks: BackgroundTasks):
    """Track an integration API call"""
    engine = get_analytics_engine()
    background_tasks.add_task(
        engine.track_integration_call,
        integration_name=request.integration_name,
        success=request.success,
        response_time_ms=request.response_time_ms
    )
    return {"status": "queued"}

@router.get("/export/csv")
async def export_analytics_csv(metric_type: str = Query(..., regex="^(workflow|integration)$")):
    """Export analytics data as CSV"""
    engine = get_analytics_engine()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if metric_type == "workflow":
        writer.writerow(["Workflow ID", "Executions", "Success Rate", "Avg Duration (s)", "Time Saved (s)", "Value ($)", "Last Executed"])
        for wf_id, metric in engine.workflow_metrics.items():
            writer.writerow([
                wf_id,
                metric.execution_count,
                f"{metric.success_rate:.1f}%",
                f"{metric.average_duration:.2f}",
                metric.total_time_saved_seconds,
                metric.total_business_value,
                metric.last_executed
            ])
            
    elif metric_type == "integration":
        writer.writerow(["Integration", "Calls", "Error Rate", "Avg Response (ms)", "Status", "Last Called"])
        for name, metric in engine.integration_metrics.items():
            writer.writerow([
                name,
                metric.call_count,
                f"{metric.error_rate:.1f}%",
                f"{metric.average_response_time:.1f}",
                metric.status,
                metric.last_called
            ])
            
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=atom_analytics_{metric_type}.csv"}
    )

@router.get("/health")
async def analytics_health():
    """System health check"""
    return {"status": "healthy", "service": "analytics"}
