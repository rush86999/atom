"""
Condition Monitoring API Routes

Provides REST endpoints for creating and managing condition monitors
that trigger alerts when business conditions exceed thresholds.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.condition_monitoring_service import ConditionMonitoringService
from core.database import get_db_session
from core.models import ConditionAlert, ConditionMonitor

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/v1/monitoring", tags=["condition-monitoring"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateMonitorRequest(BaseModel):
    """Request to create a condition monitor"""
    agent_id: str = Field(..., description="ID of the agent")
    name: str = Field(..., description="Human-readable name")
    condition_type: str = Field(..., description="inbox_volume, task_backlog, api_metrics, database_query, composite")
    threshold_config: dict = Field(..., description="Threshold configuration")
    platforms: List[dict] = Field(..., description="List of {platform, recipient_id}")
    check_interval_seconds: int = Field(300, description="Check interval in seconds (default: 300 = 5 min)")
    alert_template: Optional[str] = Field(None, description="Custom alert message template")
    composite_logic: Optional[str] = Field(None, description="AND or OR (for composite conditions)")
    composite_conditions: Optional[List[dict]] = Field(None, description="Sub-conditions (for composite)")
    governance_metadata: Optional[dict] = Field(None, description="Governance metadata")


class MonitorResponse(BaseModel):
    """Response for monitor operations"""
    id: str
    agent_id: str
    agent_name: str
    name: str
    description: Optional[str]
    condition_type: str
    threshold_config: dict
    composite_logic: Optional[str]
    composite_conditions: Optional[List[dict]]
    check_interval_seconds: int
    platforms: List[dict]
    alert_template: Optional[str]
    throttle_minutes: int
    last_alert_sent_at: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class UpdateMonitorRequest(BaseModel):
    """Request to update a monitor"""
    name: Optional[str] = None
    threshold_config: Optional[dict] = None
    check_interval_seconds: Optional[int] = None
    alert_template: Optional[str] = None
    platforms: Optional[List[dict]] = None


class AlertResponse(BaseModel):
    """Response for alert operations"""
    id: str
    monitor_id: str
    condition_value: dict
    threshold_value: dict
    alert_message: str
    platforms_sent: List[dict]
    status: str
    triggered_at: datetime
    sent_at: Optional[datetime]
    error_message: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class TestConditionResponse(BaseModel):
    """Response for testing a condition"""
    monitor_id: str
    monitor_name: str
    condition_type: str
    triggered: bool
    current_value: Any
    threshold: dict
    timestamp: str


class MetricsResponse(BaseModel):
    """Response for monitoring metrics"""
    total_monitors: int
    active_monitors: int
    total_alerts: int
    pending_alerts: int
    alerts_last_24h: int
    timestamp: str


# ============================================================================
# Condition Monitoring Endpoints
# ============================================================================

@router.post("/condition/create", response_model=MonitorResponse)
async def create_condition_monitor(
    request: CreateMonitorRequest,
    db: Session = Depends(get_db_session),
):
    """
    Create a new condition monitor.

    Condition types:
    - inbox_volume: Monitor unread message counts
    - task_backlog: Monitor pending task counts
    - api_metrics: Monitor API error rates, response times
    - database_query: Run custom database queries
    - composite: AND/OR logic for multiple conditions

    Threshold config example:
    ```json
    {
      "metric": "unread_count",
      "operator": ">",
      "value": 100
    }
    ```

    Platforms example:
    ```json
    [
      {"platform": "slack", "recipient_id": "C12345"},
      {"platform": "discord", "recipient_id": "G67890"}
    ]
    ```
    """
    service = ConditionMonitoringService(db)

    monitor = service.create_monitor(
        agent_id=request.agent_id,
        name=request.name,
        condition_type=request.condition_type,
        threshold_config=request.threshold_config,
        platforms=request.platforms,
        check_interval_seconds=request.check_interval_seconds,
        alert_template=request.alert_template,
        composite_logic=request.composite_logic,
        composite_conditions=request.composite_conditions,
        governance_metadata=request.governance_metadata,
    )

    return monitor


@router.get("/condition/list", response_model=List[MonitorResponse])
async def list_condition_monitors(
    agent_id: Optional[str] = None,
    condition_type: Optional[str] = None,
    monitor_status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db_session),
):
    """
    List condition monitors with optional filters.

    Can filter by:
    - agent_id: Only monitors from this agent
    - condition_type: Only monitors of this type
    - status: Only monitors with this status
    """
    service = ConditionMonitoringService(db)

    monitors = service.get_monitors(
        agent_id=agent_id,
        condition_type=condition_type,
        status=monitor_status,
        limit=limit,
    )

    return monitors


@router.get("/condition/{monitor_id}", response_model=MonitorResponse)
async def get_condition_monitor(
    monitor_id: str,
    db: Session = Depends(get_db_session),
):
    """Get a specific condition monitor by ID."""
    service = ConditionMonitoringService(db)

    monitor = service.get_monitor(monitor_id=monitor_id)

    if not monitor:
        raise router.not_found_error("Condition monitor", monitor_id)

    return monitor


@router.put("/condition/{monitor_id}", response_model=MonitorResponse)
async def update_condition_monitor(
    monitor_id: str,
    request: UpdateMonitorRequest,
    db: Session = Depends(get_db_session),
):
    """
    Update a condition monitor.

    Can update:
    - name: Monitor name
    - threshold_config: Threshold configuration
    - check_interval_seconds: Check frequency
    - alert_template: Alert message template
    - platforms: Alert destinations
    """
    service = ConditionMonitoringService(db)

    monitor = service.update_monitor(
        monitor_id=monitor_id,
        name=request.name,
        threshold_config=request.threshold_config,
        check_interval_seconds=request.check_interval_seconds,
        alert_template=request.alert_template,
        platforms=request.platforms,
    )

    return monitor


@router.post("/condition/{monitor_id}/pause", response_model=MonitorResponse)
async def pause_condition_monitor(
    monitor_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Pause a condition monitor.

    Paused monitors will not trigger alerts until resumed.
    """
    service = ConditionMonitoringService(db)

    monitor = service.pause_monitor(monitor_id=monitor_id)

    return monitor


@router.post("/condition/{monitor_id}/resume", response_model=MonitorResponse)
async def resume_condition_monitor(
    monitor_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Resume a paused condition monitor.

    Resumed monitors will trigger alerts based on their configuration.
    """
    service = ConditionMonitoringService(db)

    monitor = service.resume_monitor(monitor_id=monitor_id)

    return monitor


@router.delete("/condition/{monitor_id}", response_model=MonitorResponse)
async def delete_condition_monitor(
    monitor_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Delete a condition monitor.

    Deleted monitors will no longer trigger alerts.
    """
    service = ConditionMonitoringService(db)

    monitor = service.delete_monitor(monitor_id=monitor_id)

    return monitor


@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    monitor_id: Optional[str] = None,
    alert_status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db_session),
):
    """
    Get alert history with optional filters.

    Can filter by:
    - monitor_id: Only alerts from this monitor
    - status: Only alerts with this status
    """
    service = ConditionMonitoringService(db)

    alerts = service.get_alerts(
        monitor_id=monitor_id,
        status=alert_status,
        limit=limit,
    )

    return alerts


@router.post("/condition/{monitor_id}/test", response_model=TestConditionResponse)
async def test_condition(
    monitor_id: str,
    db: Session = Depends(get_db_session),
):
    """
    Test a condition monitor immediately without sending alerts.

    Useful for validating monitor configuration before activating.
    Returns current value and whether condition would trigger.
    """
    service = ConditionMonitoringService(db)

    result = service.test_condition(monitor_id=monitor_id)

    return result


@router.get("/presets")
async def get_monitor_presets(
    db: Session = Depends(get_db_session),
):
    """
    Get pre-configured monitoring presets.

    Returns common monitoring scenarios with recommended configurations.
    """
    service = ConditionMonitoringService(db)

    presets = service.get_presets()

    return presets


@router.post("/presets/apply")
async def apply_preset(
    agent_id: str,
    preset_name: str,
    platforms: List[dict],
    custom_overrides: Optional[dict] = None,
    db: Session = Depends(get_db_session),
):
    """
    Apply a monitoring preset with optional customizations.

    Args:
        agent_id: ID of the agent creating the monitor
        preset_name: Name of the preset to apply
        platforms: List of {platform, recipient_id} for alerts
        custom_overrides: Optional overrides for preset values

    Returns:
        Created monitor
    """
    service = ConditionMonitoringService(db)

    # Get preset
    presets = service.get_presets()
    preset = next((p for p in presets if p["name"] == preset_name), None)

    if not preset:
        raise router.not_found_error(
            resource="Monitoring preset",
            resource_id=preset_name,
            details={"available_presets": [p['name'] for p in presets]}
        )

    # Apply overrides if provided
    threshold_config = preset["threshold_config"]
    if custom_overrides:
        threshold_config.update(custom_overrides)

    # Create monitor from preset
    monitor = service.create_monitor(
        agent_id=agent_id,
        name=preset["name"],
        condition_type=preset["condition_type"],
        threshold_config=threshold_config,
        platforms=platforms,
        check_interval_seconds=preset["check_interval_seconds"],
    )

    return monitor


@router.get("/metrics", response_model=MetricsResponse)
async def get_monitoring_metrics(
    db: Session = Depends(get_db_session),
):
    """
    Get overall monitoring system metrics.

    Returns statistics about monitors and alerts.
    """
    service = ConditionMonitoringService(db)

    metrics = service.get_metrics()

    return metrics


@router.post("/_check-monitors")
async def check_all_monitors(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
):
    """
    Internal endpoint to check all active monitors and send alerts.

    This should be called by a background scheduler (e.g., cron or APScheduler).
    Typically runs every minute to check all active monitors.

    Returns counts of checked, triggered, and alerts sent.
    """
    service = ConditionMonitoringService(db)

    result = await service.check_and_alert_monitors()

    return result
