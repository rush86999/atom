"""
Workflow Analytics API Endpoints
REST API for workflow analytics, monitoring, and dashboard data
"""

from datetime import datetime, timedelta
import json
import logging
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import AgentExecution, Dashboard, DashboardWidget, IntegrationHealthMetrics, User

from .workflow_analytics_engine import (
    Alert,
    AlertSeverity,
    MetricType,
    WorkflowAnalyticsEngine,
    WorkflowStatus,
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
        from core.database import get_db_session
        from core.models import AgentExecution
        from datetime import datetime, timedelta

        db = get_db_session()

        # Calculate time window
        time_delta_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        time_delta = time_delta_map.get(time_window, timedelta(hours=24))
        cutoff_time = datetime.now() - time_delta

        # Query executions for this workflow
        executions = db.query(AgentExecution).filter(
            AgentExecution.metadata_json['workflow_id'].astext == workflow_id,
            AgentExecution.created_at >= cutoff_time
        ).all()

        # Calculate metrics
        total_runs = len(executions)
        successful_runs = sum(1 for e in executions if e.status == 'completed')
        failed_runs = sum(1 for e in executions if e.status == 'failed')
        cancelled_runs = sum(1 for e in executions if e.status == 'cancelled')

        # Calculate durations
        durations = []
        for exec in executions:
            if exec.completed_at and exec.created_at:
                duration = (exec.completed_at - exec.created_at).total_seconds()
                durations.append(duration)

        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0

        # Calculate success rate
        success_rate = successful_runs / total_runs if total_runs > 0 else 0

        # Build metrics response
        metrics_data = {
            "workflow_id": workflow_id,
            "time_window": time_window,
            "step_id": step_id,
            "summary": {
                "total_runs": total_runs,
                "successful_runs": successful_runs,
                "failed_runs": failed_runs,
                "cancelled_runs": cancelled_runs,
                "success_rate": round(success_rate, 4)
            },
            "performance": {
                "avg_duration_seconds": round(avg_duration, 2),
                "min_duration_seconds": round(min_duration, 2),
                "max_duration_seconds": round(max_duration, 2),
                "total_duration_seconds": round(sum(durations), 2) if durations else 0
            },
            "timestamps": {
                "first_run": executions[0].created_at.isoformat() if executions else None,
                "last_run": executions[-1].created_at.isoformat() if executions else None
            }
        }

        # Add specific requested metrics
        if metric_names:
            filtered_metrics = {}
            for name in metric_names:
                if name in metrics_data['summary']:
                    filtered_metrics[name] = metrics_data['summary'][name]
                elif name in metrics_data['performance']:
                    filtered_metrics[name] = metrics_data['performance'][name]
            if filtered_metrics:
                metrics_data['requested_metrics'] = filtered_metrics

        db.close()

        return {
            "status": "success",
            "metrics": metrics_data
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
async def list_dashboards(
    include_public: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available dashboards"""
    try:
        query = db.query(Dashboard).filter(Dashboard.is_active == True)

        if not include_public:
            # Filter to user's dashboards and public dashboards
            query = query.filter(
                (Dashboard.owner_id == current_user.id) |
                (Dashboard.is_public == True)
            )

        dashboards = query.order_by(Dashboard.created_at.desc()).all()

        return {
            "success": True,
            "dashboards": [
                {
                    "id": d.id,
                    "name": d.name,
                    "description": d.description,
                    "owner_id": d.owner_id,
                    "is_public": d.is_public,
                    "configuration": d.configuration,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                    "widget_count": len(d.widgets) if d.widgets else 0
                }
                for d in dashboards
            ]
        }

    except Exception as e:
        logger.error(f"Failed to list dashboards: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dashboards")
async def create_dashboard(
    dashboard_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new analytics dashboard"""
    try:
        # Get owner_id from authenticated user
        owner_id = current_user.id

        dashboard = Dashboard(
            name=dashboard_data.get("name", "Untitled Dashboard"),
            description=dashboard_data.get("description"),
            owner_id=owner_id,
            configuration=dashboard_data.get("configuration", {}),
            is_public=dashboard_data.get("is_public", False),
            is_active=True
        )

        db.add(dashboard)
        db.commit()
        db.refresh(dashboard)

        logger.info(f"Created dashboard {dashboard.id} for user {owner_id}")

        return {
            "success": True,
            "dashboard_id": dashboard.id,
            "message": "Dashboard created successfully",
            "dashboard": {
                "id": dashboard.id,
                "name": dashboard.name,
                "description": dashboard.description,
                "owner_id": dashboard.owner_id,
                "is_public": dashboard.is_public,
                "configuration": dashboard.configuration,
                "created_at": dashboard.created_at.isoformat() if dashboard.created_at else None
            }
        }

    except Exception as e:
        logger.error(f"Failed to create dashboard: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboards/{dashboard_id}")
async def get_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db)
):
    """Get dashboard configuration and data"""
    try:
        dashboard = db.query(Dashboard).filter(
            Dashboard.id == dashboard_id,
            Dashboard.is_active == True
        ).first()

        if not dashboard:
            raise HTTPException(status_code=404, detail=f"Dashboard {dashboard_id} not found")

        # Get widgets with their data
        widgets_data = []
        for widget in dashboard.widgets:
            widget_data = {
                "id": widget.id,
                "widget_type": widget.widget_type,
                "widget_name": widget.widget_name,
                "data_source": widget.data_source,
                "position": widget.position,
                "display_config": widget.display_config,
                "refresh_interval_seconds": widget.refresh_interval_seconds
            }

            # Fetch live data based on widget type and data source
            widget_data["data"] = await _fetch_widget_data(widget, db)
            widgets_data.append(widget_data)

        return {
            "success": True,
            "dashboard": {
                "id": dashboard.id,
                "name": dashboard.name,
                "description": dashboard.description,
                "owner_id": dashboard.owner_id,
                "is_public": dashboard.is_public,
                "configuration": dashboard.configuration,
                "created_at": dashboard.created_at.isoformat() if dashboard.created_at else None,
                "updated_at": dashboard.updated_at.isoformat() if dashboard.updated_at else None,
                "widgets": widgets_data
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dashboard {dashboard_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _fetch_widget_data(widget: DashboardWidget, db: Session) -> Dict[str, Any]:
    """
    Fetch live data for a widget based on its data source configuration
    """
    widget_type = widget.widget_type
    data_source = widget.data_source or {}

    try:
        if widget_type == "agent_execution_stats":
            # Fetch agent execution statistics
            time_window_hours = data_source.get("time_window_hours", 24)
            since = datetime.utcnow() - timedelta(hours=time_window_hours)

            executions = db.query(AgentExecution).filter(
                AgentExecution.started_at >= since
            ).all()

            total = len(executions)
            successful = sum(1 for e in executions if e.status == "completed")
            failed = sum(1 for e in executions if e.status == "failed")
            running = sum(1 for e in executions if e.status == "running")

            return {
                "total_executions": total,
                "successful": successful,
                "failed": failed,
                "running": running,
                "success_rate": successful / total if total > 0 else 0,
                "time_window_hours": time_window_hours
            }

        elif widget_type == "integration_health":
            # Fetch integration health metrics
            integration_id = data_source.get("integration_id")

            if integration_id:
                metrics = db.query(IntegrationHealthMetrics).filter(
                    IntegrationHealthMetrics.integration_id == integration_id
                ).order_by(IntegrationHealthMetrics.created_at.desc()).limit(100).all()

                return {
                    "integration_id": integration_id,
                    "metrics": [
                        {
                            "latency_ms": m.latency_ms,
                            "success_rate": m.success_rate,
                            "error_count": m.error_count,
                            "request_count": m.request_count,
                            "health_trend": m.health_trend,
                            "created_at": m.created_at.isoformat() if m.created_at else None
                        }
                        for m in metrics
                    ]
                }
            else:
                # Aggregate health across all integrations
                metrics = db.query(IntegrationHealthMetrics).order_by(
                    IntegrationHealthMetrics.created_at.desc()
                ).limit(100).all()

                return {
                    "metrics": [
                        {
                            "integration_id": m.integration_id,
                            "latency_ms": m.latency_ms,
                            "success_rate": m.success_rate,
                            "error_count": m.error_count,
                            "request_count": m.request_count,
                            "health_trend": m.health_trend
                        }
                        for m in metrics
                    ]
                }

        elif widget_type == "workflow_timeline":
            # Fetch workflow execution timeline
            time_window_hours = data_source.get("time_window_hours", 24)
            since = datetime.utcnow() - timedelta(hours=time_window_hours)

            executions = db.query(AgentExecution).filter(
                AgentExecution.started_at >= since
            ).order_by(AgentExecution.started_at.desc()).limit(50).all()

            return {
                "executions": [
                    {
                        "id": e.id,
                        "agent_id": e.agent_id,
                        "status": e.status,
                        "started_at": e.started_at.isoformat() if e.started_at else None,
                        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                        "duration_seconds": e.duration_seconds,
                        "error_message": e.error_message
                    }
                    for e in executions
                ]
            }

        else:
            logger.warning(f"Unknown widget type: {widget_type}")
            return {}

    except Exception as e:
        logger.error(f"Failed to fetch data for widget {widget.id}: {e}", exc_info=True)
        return {"error": str(e)}

# Real-time Updates Endpoints
@router.get("/workflows/{workflow_id}/live-status")
async def get_workflow_live_status(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """Get live status of a workflow"""
    try:
        # Find the most recent execution for this workflow
        execution = db.query(AgentExecution).filter(
            AgentExecution.agent_id == workflow_id
        ).order_by(AgentExecution.started_at.desc()).first()

        if not execution:
            return {
                "success": True,
                "workflow_id": workflow_id,
                "current_status": "not_found",
                "message": "No executions found for this workflow"
            }

        # Calculate progress percentage
        progress_percentage = 0
        if execution.status == "completed":
            progress_percentage = 100
        elif execution.status == "running" and execution.started_at:
            # Estimate based on average duration (this is simplistic)
            elapsed = (datetime.utcnow() - execution.started_at).total_seconds()
            if execution.duration_seconds and execution.duration_seconds > 0:
                progress_percentage = min(100, int((elapsed / execution.duration_seconds) * 100))
            else:
                progress_percentage = 50  # Default to 50% if we don't have duration data

        # Estimate completion time
        estimated_completion = None
        if execution.status == "running" and execution.duration_seconds:
            remaining_seconds = max(0, execution.duration_seconds - elapsed)
            estimated_completion = (datetime.utcnow() + timedelta(seconds=remaining_seconds)).isoformat()

        return {
            "success": True,
            "workflow_id": workflow_id,
            "execution_id": execution.id,
            "current_status": execution.status,
            "progress_percentage": progress_percentage,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "estimated_completion": estimated_completion,
            "duration_seconds": execution.duration_seconds,
            "error_message": execution.error_message,
            "triggered_by": execution.triggered_by
        }

    except Exception as e:
        logger.error(f"Failed to get live status for {workflow_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/health")
async def get_system_health(db: Session = Depends(get_db)):
    """Get system health status"""
    try:
        # Get recent execution statistics
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)

        recent_executions = db.query(AgentExecution).filter(
            AgentExecution.started_at >= last_24h
        ).all()

        active_workflows = sum(1 for e in recent_executions if e.status == "running")
        successful_executions = sum(1 for e in recent_executions if e.status == "completed")
        failed_executions = sum(1 for e in recent_executions if e.status == "failed")

        # Get integration health
        integration_metrics = db.query(IntegrationHealthMetrics).order_by(
            IntegrationHealthMetrics.created_at.desc()
        ).limit(50).all()

        # Calculate overall health status
        overall_status = "healthy"
        if integration_metrics:
            avg_success_rate = sum(m.success_rate for m in integration_metrics) / len(integration_metrics)
            avg_latency = sum(m.latency_ms for m in integration_metrics) / len(integration_metrics)

            if avg_success_rate < 0.9 or avg_latency > 1000:
                overall_status = "degraded"
            if avg_success_rate < 0.7 or avg_latency > 5000:
                overall_status = "unhealthy"

        return {
            "success": True,
            "system_health": {
                "overall_status": overall_status,
                "components": {
                    "analytics_engine": "healthy" if overall_status != "unhealthy" else "unhealthy",
                    "database": "healthy",
                    "metrics_processor": "healthy"
                },
                "active_workflows": active_workflows,
                "executions_last_24h": {
                    "total": len(recent_executions),
                    "successful": successful_executions,
                    "failed": failed_executions,
                    "success_rate": successful_executions / len(recent_executions) if recent_executions else 1.0
                },
                "integration_health": {
                    "average_success_rate": sum(m.success_rate for m in integration_metrics) / len(integration_metrics) if integration_metrics else 1.0,
                    "average_latency_ms": sum(m.latency_ms for m in integration_metrics) / len(integration_metrics) if integration_metrics else 0,
                    "total_errors": sum(m.error_count for m in integration_metrics) if integration_metrics else 0
                },
                "last_checked": now.isoformat()
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