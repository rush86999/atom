"""
Integration Dashboard API Routes
Provides endpoints for monitoring and managing communication platform integrations.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.base_routes import BaseAPIRouter
from core.integration_dashboard import (
    IntegrationDashboard,
    IntegrationStatus,
    get_integration_dashboard,
)

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/integrations/dashboard", tags=["integration-dashboard"])


# Request/Response Models
class IntegrationMetricsResponse(BaseModel):
    """Response model for integration metrics"""
    integration: str
    metrics: Dict[str, Any]


class IntegrationHealthResponse(BaseModel):
    """Response model for integration health"""
    integration: str
    health: Dict[str, Any]


class OverallStatusResponse(BaseModel):
    """Response model for overall status"""
    overall_status: str
    total_integrations: int
    healthy_count: int
    degraded_count: int
    error_count: int
    disabled_count: int
    total_messages_fetched: int
    total_messages_processed: int
    total_messages_failed: int
    overall_success_rate: float
    integrations: Dict[str, Dict[str, Any]]


class AlertResponse(BaseModel):
    """Response model for alerts"""
    integration: str
    severity: str  # critical, warning, info
    type: str
    message: str
    value: float
    threshold: float
    timestamp: str


class ConfigurationUpdateRequest(BaseModel):
    """Request model for configuration updates"""
    enabled: Optional[bool] = None
    configured: Optional[bool] = None
    has_valid_token: Optional[bool] = None
    has_required_permissions: Optional[bool] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class MetricsResetRequest(BaseModel):
    """Request model for resetting metrics"""
    integration: Optional[str] = None


# Endpoints

@router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics(
    integration: Optional[str] = Query(None, description="Specific integration name")
) -> Dict[str, Any]:
    """
    Get metrics for integrations.

    Args:
        integration: Optional integration name (slack, teams, gmail, outlook)

    Returns:
        Dictionary of metrics for all integrations or specific integration
    """
    dashboard = get_integration_dashboard()

    try:
        metrics = dashboard.get_metrics(integration)

        return router.success_response(
            data=metrics,
            message="Metrics retrieved successfully",
            metadata={"timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise router.internal_error(message=str(e))


@router.get("/health", response_model=Dict[str, Any])
async def get_health(
    integration: Optional[str] = Query(None, description="Specific integration name")
) -> Dict[str, Any]:
    """
    Get health status for integrations.

    Args:
        integration: Optional integration name (slack, teams, gmail, outlook)

    Returns:
        Dictionary of health status for all integrations or specific integration
    """
    dashboard = get_integration_dashboard()

    try:
        health = dashboard.get_health(integration)

        return router.success_response(
            data=health,
            message="Health status retrieved successfully",
            metadata={"timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        raise router.internal_error(message=str(e))


@router.get("/status/overall", response_model=OverallStatusResponse)
async def get_overall_status() -> OverallStatusResponse:
    """
    Get overall system status.

    Returns:
        Overall system status including counts and aggregates
    """
    dashboard = get_integration_dashboard()

    try:
        status = dashboard.get_overall_status()

        return OverallStatusResponse(**status)
    except Exception as e:
        logger.error(f"Error getting overall status: {e}")
        raise router.internal_error(message=str(e))


@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity (critical, warning)")
) -> List[AlertResponse]:
    """
    Get active alerts based on thresholds.

    Args:
        severity: Optional severity filter

    Returns:
        List of active alerts
    """
    dashboard = get_integration_dashboard()

    try:
        alerts = dashboard.get_alerts()

        # Filter by severity if requested
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]

        return [AlertResponse(**alert) for alert in alerts]
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise router.internal_error(message=str(e))


@router.get("/alerts/count")
async def get_alerts_count() -> Dict[str, int]:
    """
    Get count of alerts by severity.

    Returns:
        Dictionary with alert counts
    """
    dashboard = get_integration_dashboard()

    try:
        alerts = dashboard.get_alerts()

        critical_count = sum(1 for a in alerts if a["severity"] == "critical")
        warning_count = sum(1 for a in alerts if a["severity"] == "warning")

        return router.success_response(
            data={
                "total": len(alerts),
                "critical": critical_count,
                "warning": warning_count
            },
            message="Alert counts retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting alert counts: {e}")
        raise router.internal_error(message=str(e))


@router.get("/statistics/summary")
async def get_statistics_summary() -> Dict[str, Any]:
    """
    Get summary statistics for dashboard.

    Returns:
        Summary statistics including recent activity
    """
    dashboard = get_integration_dashboard()

    try:
        summary = dashboard.get_statistics_summary()

        return router.success_response(
            data=summary,
            message="Statistics summary retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting statistics summary: {e}")
        raise router.internal_error(message=str(e))


@router.get("/configuration")
async def get_configuration(
    integration: Optional[str] = Query(None, description="Specific integration name")
) -> Dict[str, Any]:
    """
    Get configuration for integrations.

    Args:
        integration: Optional integration name

    Returns:
        Configuration dictionary
    """
    dashboard = get_integration_dashboard()

    try:
        config = dashboard.get_configuration(integration)

        return router.success_response(
            data=config,
            message="Configuration retrieved successfully",
            metadata={"timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        raise router.internal_error(message=str(e))


@router.post("/configuration/{integration}")
async def update_configuration(
    integration: str,
    request: ConfigurationUpdateRequest
) -> Dict[str, Any]:
    """
    Update configuration for an integration.

    Args:
        integration: Integration name (slack, teams, gmail, outlook)
        request: Configuration update request

    Returns:
        Success status
    """
    dashboard = get_integration_dashboard()

    try:
        # Update health status if provided
        if any([
            request.enabled is not None,
            request.configured is not None,
            request.has_valid_token is not None,
            request.has_required_permissions is not None
        ]):
            dashboard.update_health(
                integration=integration,
                enabled=request.enabled,
                configured=request.configured,
                has_valid_token=request.has_valid_token,
                has_required_permissions=request.has_required_permissions
            )

        # Update configuration if provided
        if request.config:
            dashboard.update_configuration(integration, request.config)

        return router.success_response(
            message=f"Configuration updated for {integration}",
            metadata={"timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise router.internal_error(message=str(e))


@router.post("/metrics/reset")
async def reset_metrics(request: MetricsResetRequest) -> Dict[str, Any]:
    """
    Reset metrics for integration(s).

    Args:
        request: Reset request with optional integration name

    Returns:
        Success status
    """
    dashboard = get_integration_dashboard()

    try:
        dashboard.reset_metrics(request.integration)

        integration_msg = f" for {request.integration}" if request.integration else " for all integrations"

        return router.success_response(
            message=f"Metrics reset{integration_msg}",
            metadata={"timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error resetting metrics: {e}")
        raise router.internal_error(message=str(e))


@router.get("/integrations")
async def list_integrations() -> Dict[str, Any]:
    """
    List all available integrations with their status.

    Returns:
        List of integrations with basic status
    """
    dashboard = get_integration_dashboard()

    try:
        health = dashboard.get_health()
        metrics = dashboard.get_metrics()

        integrations = []
        for name in health.keys():
            integrations.append({
                "name": name,
                "status": health[name].get("status"),
                "enabled": health[name].get("enabled", False),
                "configured": health[name].get("configured", False),
                "messages_fetched": metrics[name].get("messages_fetched", 0),
                "last_fetch": metrics[name].get("last_fetch_time")
            })

        return router.success_response(
            data={
                "integrations": integrations,
                "count": len(integrations)
            },
            message="Integrations listed successfully"
        )
    except Exception as e:
        logger.error(f"Error listing integrations: {e}")
        raise router.internal_error(message=str(e))


@router.get("/integrations/{integration}/details")
async def get_integration_details(integration: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific integration.

    Args:
        integration: Integration name

    Returns:
        Detailed integration information
    """
    dashboard = get_integration_dashboard()

    try:
        health = dashboard.get_health(integration)
        metrics = dashboard.get_metrics(integration)
        config = dashboard.get_configuration(integration)

        if not health:
            raise router.not_found_error("Integration", integration)

        return router.success_response(
            data={
                "integration": integration,
                "health": health,
                "metrics": metrics,
                "configuration": config
            },
            message="Integration details retrieved successfully",
            metadata={"timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error getting integration details: {e}")
        raise router.internal_error(message=str(e))


@router.post("/health/{integration}/check")
async def check_integration_health(integration: str) -> Dict[str, Any]:
    """
    Trigger a health check for a specific integration.

    This endpoint can be called to manually trigger a health check
    (e.g., after reconfiguration or recovery).

    Args:
        integration: Integration name

    Returns:
        Health check result
    """
    dashboard = get_integration_dashboard()

    try:
        # Update last check time
        dashboard.update_health(integration)

        health = dashboard.get_health(integration)

        return router.success_response(
            data={
                "integration": integration,
                "health": health
            },
            message="Health check completed successfully",
            metadata={"timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error checking integration health: {e}")
        raise router.internal_error(message=str(e))


@router.get("/performance")
async def get_performance_metrics() -> Dict[str, Any]:
    """
    Get performance metrics across all integrations.

    Returns:
        Performance metrics including timing data
    """
    dashboard = get_integration_dashboard()

    try:
        metrics = dashboard.get_metrics()

        performance = {}
        for integration, integration_metrics in metrics.items():
            performance[integration] = {
                "avg_fetch_time_ms": integration_metrics.get("avg_fetch_time_ms", 0),
                "p99_fetch_time_ms": integration_metrics.get("p99_fetch_time_ms", 0),
                "avg_process_time_ms": integration_metrics.get("avg_process_time_ms", 0),
                "p99_process_time_ms": integration_metrics.get("p99_process_time_ms", 0),
                "fetch_size_bytes": integration_metrics.get("fetch_size_bytes", 0),
                "attachment_count": integration_metrics.get("attachment_count", 0)
            }

        return router.success_response(
            data=performance,
            message="Performance metrics retrieved successfully",
            metadata={"timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise router.internal_error(message=str(e))


@router.get("/data-quality")
async def get_data_quality_metrics() -> Dict[str, Any]:
    """
    Get data quality metrics.

    Returns:
        Data quality metrics including duplicates and success rates
    """
    dashboard = get_integration_dashboard()

    try:
        metrics = dashboard.get_metrics()

        quality = {}
        for integration, integration_metrics in metrics.items():
            quality[integration] = {
                "messages_fetched": integration_metrics.get("messages_fetched", 0),
                "messages_processed": integration_metrics.get("messages_processed", 0),
                "messages_failed": integration_metrics.get("messages_failed", 0),
                "messages_duplicate": integration_metrics.get("messages_duplicate", 0),
                "success_rate": integration_metrics.get("success_rate", 100.0),
                "duplicate_rate": integration_metrics.get("duplicate_rate", 0.0)
            }

        return router.success_response(
            data=quality,
            message="Data quality metrics retrieved successfully",
            metadata={"timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error getting data quality metrics: {e}")
        raise router.internal_error(message=str(e))
