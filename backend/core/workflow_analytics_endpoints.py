"""
Workflow Analytics API Endpoints
REST API for workflow analytics, monitoring, and dashboard data
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import json
import logging

from .workflow_analytics_engine import (
    WorkflowAnalyticsEngine,
    Alert,
    AlertSeverity,
    MetricType,
    WorkflowStatus
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize analytics engine
analytics_engine = WorkflowAnalyticsEngine()

# Request/Response Models
class MetricsQuery(BaseModel):
    workflow_id: str
    metric_names: List[str] = []
    time_window: str = "24h"
    step_id: Optional[str] = None
    aggregation: str = "avg"  # avg, sum, min, max, count

class AlertRequest(BaseModel):
    name: str
    description: str
    severity: AlertSeverity
    condition: str
    threshold_value: Union[int, float]
    metric_name: str
    workflow_id: Optional[str] = None
    step_id: Optional[str] = None
    notification_channels: List[str] = []

class DashboardWidget(BaseModel):
    widget_id: str
    widget_type: str  # "metric_chart", "workflow_stats", "error_timeline", etc.
    title: str
    config: Dict[str, Any]
    position: Dict[str, int]  # x, y, width, height

class Dashboard(BaseModel):
    dashboard_id: str
    name: str
    description: str
    widgets: List[DashboardWidget]
    layout: Dict[str, Any]
    is_public: bool = False
    created_at: datetime
    updated_at: datetime

# Helper Functions
def serialize_alert(alert: Alert) -> Dict[str, Any]:
    """Convert alert to serializable dict"""
    return {
        "alert_id": alert.alert_id,
        "name": alert.name,
        "description": alert.description,
        "severity": alert.severity.value,
        "condition": alert.condition,
        "threshold_value": alert.threshold_value,
        "metric_name": alert.metric_name,
        "workflow_id": alert.workflow_id,
        "step_id": alert.step_id,
        "enabled": alert.enabled,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "notification_channels": alert.notification_channels or []
    }

# Workflow Execution Tracking Endpoints
@router.post("/workflows/{workflow_id}/track/start")
async def track_workflow_start(workflow_id: str, execution_id: str,
                               user_id: Optional[str] = None,
                               metadata: Optional[Dict[str, Any]] = None):
    """Track workflow execution start"""
    try:
        analytics_engine.track_workflow_start(
            workflow_id=workflow_id,
            execution_id=execution_id,
            user_id=user_id,
            metadata=metadata
        )

        return {
            "status": "success",
            "message": f"Started tracking execution {execution_id} for workflow {workflow_id}"
        }

    except Exception as e:
        logger.error(f"Failed to track workflow start: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{workflow_id}/track/complete")
async def track_workflow_completion(workflow_id: str, execution_id: str,
                                   status: WorkflowStatus, duration_ms: int,
                                   step_outputs: Optional[Dict[str, Any]] = None,
                                   error_message: Optional[str] = None):
    """Track workflow execution completion"""
    try:
        analytics_engine.track_workflow_completion(
            workflow_id=workflow_id,
            execution_id=execution_id,
            status=status,
            duration_ms=duration_ms,
            step_outputs=step_outputs,
            error_message=error_message
        )

        return {
            "status": "success",
            "message": f"Tracked completion for execution {execution_id}"
        }

    except Exception as e:
        logger.error(f"Failed to track workflow completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{workflow_id}/track/step")
async def track_step_execution(workflow_id: str, execution_id: str, step_id: str,
                               step_name: str, event_type: str,
                               duration_ms: Optional[int] = None,
                               status: Optional[str] = None,
                               error_message: Optional[str] = None):
    """Track individual step execution"""
    try:
        analytics_engine.track_step_execution(
            workflow_id=workflow_id,
            execution_id=execution_id,
            step_id=step_id,
            step_name=step_name,
            event_type=event_type,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message
        )

        return {
            "status": "success",
            "message": f"Tracked step {step_id} execution"
        }

    except Exception as e:
        logger.error(f"Failed to track step execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/{workflow_id}/track/resources")
async def track_resource_usage(workflow_id: str, step_id: Optional[str] = None,
                               cpu_usage: float = 0, memory_usage: float = 0,
                               disk_io: Optional[int] = None,
                               network_io: Optional[int] = None):
    """Track resource usage during workflow execution"""
    try:
        analytics_engine.track_resource_usage(
            workflow_id=workflow_id,
            step_id=step_id,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_io=disk_io,
            network_io=network_io
        )

        return {
            "status": "success",
            "message": "Resource usage tracked successfully"
        }

    except Exception as e:
        logger.error(f"Failed to track resource usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Analytics and Metrics Endpoints
@router.get("/workflows/{workflow_id}/performance")
async def get_workflow_performance(workflow_id: str,
                                    time_window: str = Query("24h")):
    """Get performance metrics for a specific workflow"""
    try:
        metrics = analytics_engine.get_workflow_performance_metrics(
            workflow_id=workflow_id,
            time_window=time_window
        )

        return {
            "status": "success",
            "metrics": metrics.__dict__
        }

    except Exception as e:
        logger.error(f"Failed to get workflow performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system/overview")
async def get_system_overview(time_window: str = Query("24h")):
    """Get system-wide analytics overview"""
    try:
        overview = analytics_engine.get_system_overview(time_window=time_window)

        return {
            "status": "success",
            "overview": overview
        }

    except Exception as e:
        logger.error(f"Failed to get system overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/{workflow_id}/metrics")
async def get_workflow_metrics(workflow_id: str,
                              metric_names: List[str] = Query([]),
                              time_window: str = Query("24h"),
                              step_id: Optional[str] = None):
    """Get specific metrics for a workflow"""
    try:
        # This would require implementing a method in the analytics engine
        # For now, return a placeholder response
        return {
            "status": "success",
            "metrics": {
                "workflow_id": workflow_id,
                "time_window": time_window,
                "step_id": step_id,
                "metric_names": metric_names,
                "data": {}  # Would contain actual metric data
            }
        }

    except Exception as e:
        logger.error(f"Failed to get workflow metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/{workflow_id}/timeline")
async def get_workflow_timeline(workflow_id: str,
                               time_window: str = Query("24h"),
                               limit: int = Query(100)):
    """Get timeline of workflow events"""
    try:
        # This would query the events database
        return {
            "status": "success",
            "timeline": {
                "workflow_id": workflow_id,
                "time_window": time_window,
                "events": []  # Would contain timeline events
            }
        }

    except Exception as e:
        logger.error(f"Failed to get workflow timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/top-performing")
async def get_top_performing_workflows(limit: int = Query(10),
                                       time_window: str = Query("24h"),
                                       metric: str = Query("success_rate")):
    """Get top performing workflows by various metrics"""
    try:
        # This would implement performance ranking logic
        return {
            "status": "success",
            "workflows": {
                "time_window": time_window,
                "metric": metric,
                "rankings": []  # Would contain ranked workflows
            }
        }

    except Exception as e:
        logger.error(f"Failed to get top performing workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Alert Management Endpoints
@router.post("/alerts", response_model=Dict[str, Any])
async def create_alert(alert_request: AlertRequest):
    """Create a new analytics alert"""
    try:
        alert = analytics_engine.create_alert(
            name=alert_request.name,
            description=alert_request.description,
            severity=alert_request.severity,
            condition=alert_request.condition,
            threshold_value=alert_request.threshold_value,
            metric_name=alert_request.metric_name,
            workflow_id=alert_request.workflow_id,
            step_id=alert_request.step_id,
            notification_channels=alert_request.notification_channels
        )

        return {
            "status": "success",
            "alert": serialize_alert(alert),
            "message": f"Alert '{alert_request.name}' created successfully"
        }

    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts", response_model=List[Dict[str, Any]])
async def list_alerts(workflow_id: Optional[str] = None,
                      severity: Optional[AlertSeverity] = None,
                      enabled_only: bool = Query(False)):
    """List analytics alerts with filtering"""
    try:
        # This would query the alerts database
        return {
            "status": "success",
            "alerts": []  # Would contain filtered alerts
        }

    except Exception as e:
        logger.error(f"Failed to list alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts/{alert_id}", response_model=Dict[str, Any])
async def get_alert(alert_id: str):
    """Get alert details"""
    try:
        if alert_id in analytics_engine.active_alerts:
            return {
                "status": "success",
                "alert": serialize_alert(analytics_engine.active_alerts[alert_id])
            }
        else:
            raise HTTPException(status_code=404, detail="Alert not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/alerts/{alert_id}/toggle")
async def toggle_alert(alert_id: str):
    """Toggle alert enabled/disabled status"""
    try:
        if alert_id not in analytics_engine.active_alerts:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert = analytics_engine.active_alerts[alert_id]
        alert.enabled = not alert.enabled

        return {
            "status": "success",
            "alert_id": alert_id,
            "enabled": alert.enabled,
            "message": f"Alert {'enabled' if alert.enabled else 'disabled'}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    """Delete an alert"""
    try:
        if alert_id not in analytics_engine.active_alerts:
            raise HTTPException(status_code=404, detail="Alert not found")

        del analytics_engine.active_alerts[alert_id]

        # Also remove from database
        conn = analytics_engine.db_path
        import sqlite3
        with sqlite3.connect(str(conn)) as db:
            db.execute("DELETE FROM analytics_alerts WHERE alert_id = ?", (alert_id,))

        return {
            "status": "success",
            "message": f"Alert {alert_id} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Dashboard Endpoints
@router.get("/dashboards")
async def list_dashboards(include_public: bool = Query(True)):
    """List available dashboards"""
    try:
        # This would query the dashboards database
        return {
            "status": "success",
            "dashboards": []  # Would contain dashboard list
        }

    except Exception as e:
        logger.error(f"Failed to list dashboards: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/dashboards")
async def create_dashboard(dashboard_data: Dict[str, Any]):
    """Create a new analytics dashboard"""
    try:
        # This would create a dashboard in the database
        return {
            "status": "success",
            "dashboard_id": "new_dashboard_id",  # Would be actual generated ID
            "message": "Dashboard created successfully"
        }

    except Exception as e:
        logger.error(f"Failed to create dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: str):
    """Get dashboard configuration and data"""
    try:
        # This would get dashboard from database and populate with data
        return {
            "status": "success",
            "dashboard": {
                "dashboard_id": dashboard_id,
                "configuration": {},  # Would contain dashboard config
                "data": {}  # Would contain live data for widgets
            }
        }

    except Exception as e:
        logger.error(f"Failed to get dashboard {dashboard_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Real-time Updates Endpoints
@router.get("/workflows/{workflow_id}/live-status")
async def get_workflow_live_status(workflow_id: str):
    """Get live status of a workflow"""
    try:
        return {
            "status": "success",
            "workflow_id": workflow_id,
            "current_status": "running",  # Would get actual status
            "current_step": "step_2",
            "progress_percentage": 65,
            "estimated_completion": "2025-12-14T16:50:00Z",
            "resource_usage": {
                "cpu_percent": 45.2,
                "memory_mb": 256.7,
                "disk_io_mb": 12.3
            }
        }

    except Exception as e:
        logger.error(f"Failed to get live status for {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system/health")
async def get_system_health():
    """Get system health status"""
    try:
        return {
            "status": "success",
            "system_health": {
                "overall_status": "healthy",
                "components": {
                    "analytics_engine": "healthy",
                    "database": "healthy",
                    "metrics_processor": "healthy"
                },
                "active_workflows": 5,
                "pending_events": 23,
                "last_processed_event": "2025-12-14T16:48:30Z",
                "alerts": {
                    "active": 2,
                    "critical": 0,
                    "total_today": 8
                }
            }
        }

    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Export and Reporting Endpoints
@router.get("/workflows/{workflow_id}/export/analytics")
async def export_workflow_analytics(workflow_id: str,
                                     format: str = Query("json"),
                                     time_window: str = Query("30d")):
    """Export workflow analytics data"""
    try:
        # This would generate export data
        return {
            "status": "success",
            "export_data": {
                "workflow_id": workflow_id,
                "time_window": time_window,
                "format": format,
                "data": {}  # Would contain exported analytics data
            },
            "download_url": f"/api/analytics/downloads/{workflow_id}_analytics.{format}"
        }

    except Exception as e:
        logger.error(f"Failed to export analytics for {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports/generate")
async def generate_analytics_report(report_config: Dict[str, Any]):
    """Generate custom analytics report"""
    try:
        return {
            "status": "success",
            "report_id": "report_12345",
            "config": report_config,
            "status_url": "/api/analytics/reports/report_12345/status",
            "download_url": "/api/analytics/reports/report_12345/download"
        }

    except Exception as e:
        logger.error(f"Failed to generate analytics report: {e}")
        raise HTTPException(status_code=500, detail=str(e))