"""
Analytics Dashboard API Endpoints
Provides aggregated metrics and KPIs for the analytics dashboard
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import Query
from pydantic import BaseModel, Field

from core.base_routes import BaseAPIRouter
from core.database import SessionLocal
from core.workflow_analytics_engine import (
    AlertSeverity,
    MetricType,
    PerformanceMetrics,
    WorkflowAnalyticsEngine,
)

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/analytics", tags=["Analytics Dashboard"])

# Global analytics engine instance
_analytics_engine: Optional[WorkflowAnalyticsEngine] = None


def get_analytics_engine() -> WorkflowAnalyticsEngine:
    """Get or create analytics engine instance"""
    global _analytics_engine
    if _analytics_engine is None:
        _analytics_engine = WorkflowAnalyticsEngine()
    return _analytics_engine


# Request/Response Models
class TimeRangeParams(BaseModel):
    """Time range parameters for dashboard queries"""
    time_window: str = Field(default="24h", description="Time window: 1h, 24h, 7d, 30d")


class DashboardKPIs(BaseModel):
    """Dashboard key performance indicators"""
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    average_duration_ms: float
    average_duration_seconds: float
    unique_workflows: int
    unique_users: int
    error_rate: float


class WorkflowPerformanceRanking(BaseModel):
    """Workflow performance for ranking table"""
    workflow_id: str
    workflow_name: str
    total_executions: int
    success_rate: float
    average_duration_ms: float
    last_execution: Optional[datetime]
    trend: str  # "up", "down", "stable"


class ExecutionTimelineData(BaseModel):
    """Execution data for timeline chart"""
    timestamp: datetime
    count: int
    success_count: int
    failure_count: int
    average_duration_ms: float


class AlertConfiguration(BaseModel):
    """Alert configuration"""
    alert_id: str
    name: str
    description: str
    severity: str
    metric_name: str
    condition: str
    threshold_value: float
    workflow_id: Optional[str]
    enabled: bool


class RealtimeExecutionEvent(BaseModel):
    """Real-time execution event for feed"""
    event_id: str
    workflow_id: str
    workflow_name: str
    execution_id: str
    event_type: str
    timestamp: datetime
    status: Optional[str]
    duration_ms: Optional[int]
    user_id: str


# API Endpoints

@router.get("/api/analytics/dashboard/kpis", response_model=DashboardKPIs)
async def get_dashboard_kpis(
    time_window: str = Query(default="24h", description="Time window: 1h, 24h, 7d, 30d"),
    user_id: Optional[str] = Query(default=None, description="Filter by user ID")
):
    """
    Get key performance indicators for the dashboard

    Returns aggregated metrics including:
    - Total executions
    - Success/failure rates
    - Average execution duration
    - Unique workflows and users
    - Error rate
    """
    try:
        analytics = get_analytics_engine()

        # Get performance metrics
        metrics = analytics.get_performance_metrics(
            workflow_id="*",  # All workflows
            time_window=time_window
        )

        if not metrics:
            return DashboardKPIs(
                total_executions=0,
                successful_executions=0,
                failed_executions=0,
                success_rate=0.0,
                average_duration_ms=0.0,
                average_duration_seconds=0.0,
                unique_workflows=0,
                unique_users=0,
                error_rate=0.0
            )

        # Calculate KPIs
        total_executions = metrics.total_executions
        successful_executions = metrics.successful_executions
        failed_executions = metrics.failed_executions
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0.0
        error_rate = metrics.error_rate

        return DashboardKPIs(
            total_executions=total_executions,
            successful_executions=successful_executions,
            failed_executions=failed_executions,
            success_rate=round(success_rate, 2),
            average_duration_ms=round(metrics.average_duration_ms, 2),
            average_duration_seconds=round(metrics.average_duration_ms / 1000, 2),
            unique_workflows=analytics.get_unique_workflow_count(time_window),
            unique_users=metrics.unique_users,
            error_rate=round(error_rate, 2)
        )

    except Exception as e:
        logger.error(f"Error getting dashboard KPIs: {e}")
        raise router.internal_error(message=str(e))


@router.get("/api/analytics/dashboard/workflows/top-performing", response_model=List[WorkflowPerformanceRanking])
async def get_top_workflows(
    limit: int = Query(default=10, ge=1, le=100),
    time_window: str = Query(default="24h", description="Time window: 1h, 24h, 7d, 30d"),
    sort_by: str = Query(default="success_rate", description="Sort by: success_rate, executions, duration")
):
    """
    Get top-performing workflows ranked by performance metrics

    Returns workflows sorted by:
    - success_rate (default): Highest success rate first
    - executions: Most executions first
    - duration: Fastest average duration first
    """
    try:
        analytics = get_analytics_engine()

        # Get all workflow IDs
        workflow_ids = analytics.get_all_workflow_ids(time_window)

        rankings = []
        for workflow_id in workflow_ids:
            metrics = analytics.get_performance_metrics(
                workflow_id=workflow_id,
                time_window=time_window
            )

            if not metrics:
                continue

            # Calculate trend (simplified)
            recent_metrics = analytics.get_performance_metrics(
                workflow_id=workflow_id,
                time_window="1h"
            )
            trend = "stable"
            if recent_metrics and recent_metrics.total_executions > 0:
                if recent_metrics.success_rate > metrics.success_rate + 5:
                    trend = "up"
                elif recent_metrics.success_rate < metrics.success_rate - 5:
                    trend = "down"

            rankings.append(WorkflowPerformanceRanking(
                workflow_id=workflow_id,
                workflow_name=analytics.get_workflow_name(workflow_id) or workflow_id,
                total_executions=metrics.total_executions,
                success_rate=round(metrics.success_rate, 2),
                average_duration_ms=round(metrics.average_duration_ms, 2),
                last_execution=analytics.get_last_execution_time(workflow_id),
                trend=trend
            ))

        # Sort rankings
        if sort_by == "success_rate":
            rankings.sort(key=lambda x: x.success_rate, reverse=True)
        elif sort_by == "executions":
            rankings.sort(key=lambda x: x.total_executions, reverse=True)
        elif sort_by == "duration":
            rankings.sort(key=lambda x: x.average_duration_ms)

        return rankings[:limit]

    except Exception as e:
        logger.error(f"Error getting top workflows: {e}")
        raise router.internal_error(message=str(e))


@router.get("/api/analytics/dashboard/timeline", response_model=List[ExecutionTimelineData])
async def get_execution_timeline(
    time_window: str = Query(default="24h", description="Time window: 1h, 24h, 7d, 30d"),
    interval: str = Query(default="1h", description="Interval: 5m, 15m, 1h, 1d"),
    workflow_id: Optional[str] = Query(default=None, description="Filter by workflow ID")
):
    """
    Get execution timeline data for charts

    Returns time-series data grouped by interval:
    - Execution count
    - Success/failure counts
    - Average duration
    """
    try:
        analytics = get_analytics_engine()

        # Parse time window
        time_delta_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        time_delta = time_delta_map.get(time_window, timedelta(hours=24))

        # Parse interval
        interval_delta_map = {
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "1h": timedelta(hours=1),
            "1d": timedelta(days=1)
        }
        interval_delta = interval_delta_map.get(interval, timedelta(hours=1))

        # Get timeline data
        timeline_data = analytics.get_execution_timeline(
            workflow_id=workflow_id or "*",
            time_window=time_window,
            interval=interval
        )

        return timeline_data

    except Exception as e:
        logger.error(f"Error getting execution timeline: {e}")
        raise router.internal_error(message=str(e))


@router.get("/api/analytics/dashboard/errors/breakdown")
async def get_error_breakdown(
    time_window: str = Query(default="24h", description="Time window: 1h, 24h, 7d, 30d"),
    workflow_id: Optional[str] = Query(default=None, description="Filter by workflow ID")
):
    """
    Get error breakdown by type and workflow

    Returns:
    - Error types with counts
    - Workflows with most errors
    - Recent error messages
    """
    try:
        analytics = get_analytics_engine()

        breakdown = analytics.get_error_breakdown(
            workflow_id=workflow_id or "*",
            time_window=time_window
        )

        return breakdown

    except Exception as e:
        logger.error(f"Error getting error breakdown: {e}")
        raise router.internal_error(message=str(e))


@router.get("/api/analytics/alerts", response_model=List[AlertConfiguration])
async def get_alerts(
    workflow_id: Optional[str] = Query(default=None, description="Filter by workflow ID"),
    enabled_only: bool = Query(default=False, description="Only return enabled alerts")
):
    """
    Get all configured alerts

    Returns alert configurations with:
    - Alert ID and name
    - Severity and condition
    - Associated workflow/metric
    - Enabled status
    """
    try:
        analytics = get_analytics_engine()

        alerts = analytics.get_all_alerts(
            workflow_id=workflow_id,
            enabled_only=enabled_only
        )

        return [
            AlertConfiguration(
                alert_id=alert.alert_id,
                name=alert.name,
                description=alert.description,
                severity=alert.severity.value,
                metric_name=alert.metric_name,
                condition=alert.condition,
                threshold_value=float(alert.threshold_value) if alert.threshold_value else 0.0,
                workflow_id=alert.workflow_id,
                enabled=alert.enabled
            )
            for alert in alerts
        ]

    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise router.internal_error(message=str(e))


@router.post("/api/analytics/alerts")
async def create_alert(alert: AlertConfiguration):
    """
    Create a new analytics alert

    Alert conditions are evaluated as Python expressions.
    Example: "error_rate > 5" or "avg_duration_ms > 10000"
    """
    try:
        analytics = get_analytics_engine()

        from core.workflow_analytics_engine import Alert

        new_alert = Alert(
            alert_id=alert.alert_id,
            name=alert.name,
            description=alert.description,
            severity=AlertSeverity(alert.severity),
            condition=alert.condition,
            threshold_value=alert.threshold_value,
            metric_name=alert.metric_name,
            workflow_id=alert.workflow_id,
            enabled=alert.enabled,
            created_at=datetime.now(),
            notification_channels=[]
        )

        analytics.create_alert(new_alert)

        return router.success_response(
            data={"alert_id": alert.alert_id},
            message="Alert created successfully"
        )

    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise router.internal_error(message=str(e))


@router.put("/api/analytics/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    enabled: Optional[bool] = None,
    threshold_value: Optional[float] = None
):
    """
    Update an existing alert

    Can update:
    - Enabled status
    - Threshold value
    """
    try:
        analytics = get_analytics_engine()

        analytics.update_alert(
            alert_id=alert_id,
            enabled=enabled,
            threshold_value=threshold_value
        )

        return router.success_response(message="Alert updated successfully")

    except Exception as e:
        logger.error(f"Error updating alert: {e}")
        raise router.internal_error(message=str(e))


@router.delete("/api/analytics/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    """Delete an alert configuration"""
    try:
        analytics = get_analytics_engine()
        analytics.delete_alert(alert_id)
        return router.success_response(message="Alert deleted successfully")

    except Exception as e:
        logger.error(f"Error deleting alert: {e}")
        raise router.internal_error(message=str(e))


@router.get("/api/analytics/dashboard/realtime-feed", response_model=List[RealtimeExecutionEvent])
async def get_realtime_execution_feed(
    limit: int = Query(default=50, ge=1, le=500),
    workflow_id: Optional[str] = Query(default=None, description="Filter by workflow ID")
):
    """
    Get real-time execution feed

    Returns recent execution events:
    - Workflow started/completed/failed events
    - Step execution events
    - Error events
    """
    try:
        analytics = get_analytics_engine()

        events = analytics.get_recent_events(
            limit=limit,
            workflow_id=workflow_id
        )

        return [
            RealtimeExecutionEvent(
                event_id=event.event_id,
                workflow_id=event.workflow_id,
                workflow_name=analytics.get_workflow_name(event.workflow_id) or event.workflow_id,
                execution_id=event.execution_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                status=event.status,
                duration_ms=event.duration_ms,
                user_id=event.user_id
            )
            for event in events
        ]

    except Exception as e:
        logger.error(f"Error getting real-time feed: {e}")
        raise router.internal_error(message=str(e))


@router.get("/api/analytics/dashboard/metrics/summary")
async def get_metrics_summary(
    time_window: str = Query(default="24h", description="Time window: 1h, 24h, 7d, 30d")
):
    """
    Get comprehensive metrics summary for dashboard

    Returns aggregated data for:
    - KPI cards
    - Performance chart
    - Error breakdown
    - Top workflows
    """
    try:
        analytics = get_analytics_engine()

        # Get KPIs
        kpis = await get_dashboard_kpis(time_window=time_window)

        # Get top workflows
        top_workflows = await get_top_workflows(limit=10, time_window=time_window)

        # Get error breakdown
        error_breakdown = await get_error_breakdown(time_window=time_window)

        # Get timeline data
        timeline = await get_execution_timeline(time_window=time_window)

        return router.success_response(
            data={
                "kpis": kpis.dict(),
                "top_workflows": [w.dict() for w in top_workflows],
                "error_breakdown": error_breakdown,
                "timeline": [t.dict() for t in timeline]
            },
            message="Metrics summary retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        raise router.internal_error(message=str(e))


@router.get("/api/analytics/dashboard/workflow/{workflow_id}/performance")
async def get_workflow_performance_detail(
    workflow_id: str,
    time_window: str = Query(default="24h", description="Time window: 1h, 24h, 7d, 30d")
):
    """
    Get detailed performance metrics for a specific workflow

    Returns:
    - Execution metrics
    - Step-by-step breakdown
    - Error analysis
    - Performance trends
    """
    try:
        analytics = get_analytics_engine()

        metrics = analytics.get_performance_metrics(
            workflow_id=workflow_id,
            time_window=time_window
        )

        if not metrics:
            raise router.not_found_error("Workflow", workflow_id)

        return router.success_response(
            data={
                "workflow_id": workflow_id,
                "workflow_name": analytics.get_workflow_name(workflow_id),
                "metrics": {
                    "total_executions": metrics.total_executions,
                    "successful_executions": metrics.successful_executions,
                    "failed_executions": metrics.failed_executions,
                    "success_rate": round(metrics.success_rate, 2),
                    "average_duration_ms": round(metrics.average_duration_ms, 2),
                    "median_duration_ms": round(metrics.median_duration_ms, 2),
                    "p95_duration_ms": round(metrics.p95_duration_ms, 2),
                    "p99_duration_ms": round(metrics.p99_duration_ms, 2),
                    "error_rate": round(metrics.error_rate, 2)
                },
                "step_performance": metrics.average_step_duration,
                "common_errors": metrics.most_common_errors,
                "user_metrics": {
                    "unique_users": metrics.unique_users,
                    "executions_by_user": metrics.executions_by_user
                }
            },
            message="Workflow performance retrieved successfully"
        )

    except Exception as e:
        logger.error(f"Error getting workflow performance detail: {e}")
        raise router.internal_error(message=str(e))
