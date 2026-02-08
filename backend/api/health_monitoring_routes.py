"""
Health Monitoring API Routes

Provides REST API endpoints for monitoring agent operations,
integration health, and system metrics.
"""

import logging
from typing import Optional
from fastapi import Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.health_monitoring_service import HealthMonitoringService, get_health_monitoring_service
from core.models import User

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/health", tags=["Health Monitoring"])


# Request/Response Models
class AcknowledgeAlertRequest(BaseModel):
    """Request to acknowledge an alert"""
    acknowledged: bool = Field(..., description="Whether alert is acknowledged")
    notes: Optional[str] = Field(None, description="Optional notes about resolution")


class AgentHealthResponse(BaseModel):
    """Agent health status"""
    agent_id: str
    agent_name: str
    status: str
    current_operation: Optional[str]
    operations_completed: int
    success_rate: float
    confidence_score: float
    last_active: str
    health_trend: str
    metrics: dict


class IntegrationHealthResponse(BaseModel):
    """Integration health status"""
    integration_id: str
    integration_name: str
    status: str
    last_used: str
    latency_ms: float
    error_rate: float
    health_trend: str
    connection_status: str


class SystemMetricsResponse(BaseModel):
    """System-wide metrics"""
    cpu_usage: float
    memory_usage: float
    active_operations: int
    queue_depth: int
    total_agents: int
    active_agents: int
    total_integrations: int
    healthy_integrations: int
    alerts: dict


class AlertResponse(BaseModel):
    """Alert details"""
    alert_id: str
    severity: str
    message: str
    source_type: str
    source_id: str
    timestamp: str
    action_required: bool
    acknowledged: bool


# Endpoints
@router.get("/agent/{agent_id}", response_model=AgentHealthResponse)
async def get_agent_health(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get comprehensive health status for an agent.

    Returns:
    - Agent status (active, idle, error, paused)
    - Current operation (if active)
    - Success rate and confidence score
    - Performance metrics (execution time, error rate)
    - Health trend (improving, stable, declining)
    """
    try:
        health_service = get_health_monitoring_service(db)

        health = await health_service.get_agent_health(agent_id)

        if "error" in health and health["status"] == "error":
            raise router.not_found_error(
                "Agent",
                agent_id,
                details={"error": health.get("error", "Agent not found")}
            )

        return AgentHealthResponse(**health)

    except Exception as e:
        logger.error(f"Failed to get agent health: {e}")
        raise router.internal_error(message=f"Failed to get agent health: {str(e)}")


@router.get("/integrations", response_model=list[IntegrationHealthResponse])
async def get_integrations_health(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get health status for all user's integrations.

    Returns list of integrations with:
    - Connection status
    - Latency metrics
    - Error rates
    - Health trends
    """
    try:
        health_service = get_health_monitoring_service(db)

        health_list = await health_service.get_all_integrations_health(user.id)

        return [IntegrationHealthResponse(**h) for h in health_list]

    except Exception as e:
        logger.error(f"Failed to get integrations health: {e}")
        raise router.internal_error(message=f"Failed to get integrations health: {str(e)}")


@router.get("/system", response_model=SystemMetricsResponse)
async def get_system_metrics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get system-wide health metrics.

    Returns:
    - CPU and memory usage
    - Active operations count
    - Queue depth
    - Agent and integration counts
    - Alert summary by severity
    """
    try:
        health_service = get_health_monitoring_service(db)

        metrics = await health_service.get_system_metrics()

        return SystemMetricsResponse(**metrics)

    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise router.internal_error(message=f"Failed to get system metrics: {str(e)}")


@router.get("/alerts", response_model=list[AlertResponse])
async def get_alerts(
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get active alerts for the user.

    Query Parameters:
    - severity: Optional filter by severity (critical, warning, info)

    Returns list of active alerts sorted by severity.
    """
    try:
        health_service = get_health_monitoring_service(db)

        alerts = await health_service.get_active_alerts(user.id)

        # Filter by severity if specified
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]

        # Sort by severity (critical first)
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 3))

        return [AlertResponse(**a) for a in alerts]

    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise router.internal_error(message=f"Failed to get alerts: {str(e)}")


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    request: AcknowledgeAlertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Acknowledge an alert (mark as resolved).

    - **alert_id**: Alert to acknowledge
    - **acknowledged**: Whether alert is acknowledged
    - **notes**: Optional resolution notes

    Broadcasts alert acknowledgment to connected clients.
    """
    try:
        health_service = get_health_monitoring_service(db)

        success = await health_service.acknowledge_alert(alert_id, user.id)

        if not success:
            raise router.not_found_error("Alert", alert_id)

        return router.success_response(message="Alert acknowledged")

    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}")
        raise router.internal_error(message=f"Failed to acknowledge alert: {str(e)}")


@router.get("/history/{health_type}")
async def get_health_history(
    health_type: str,  # "agent" | "integration" | "system"
    entity_id: Optional[str] = None,
    days: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get health history for trend analysis.

    Path Parameters:
    - **health_type**: Type of health history (agent, integration, system)

    Query Parameters:
    - **entity_id**: Optional entity ID (agent_id, integration_id)
    - **days**: Number of days to look back (default 30)

    Returns time-series health data for charting and analysis.
    """
    try:
        health_service = get_health_monitoring_service(db)

        history = await health_service.get_health_history(
            health_type=health_type,
            entity_id=entity_id,
            days=days
        )

        return {
            "health_type": health_type,
            "entity_id": entity_id,
            "days": days,
            "data_points": len(history),
            "history": history
        }

    except Exception as e:
        logger.error(f"Failed to get health history: {e}")
        raise router.internal_error(message=f"Failed to get health history: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return router.success_response(
        data={"status": "healthy", "service": "health_monitoring"},
        message="Health monitoring service is healthy"
    )
