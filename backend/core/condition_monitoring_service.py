"""
Condition Monitoring Service

Monitors business conditions in real-time and sends alerts when thresholds are exceeded.
Supports inbox volume, task backlog, API metrics, database queries, and composite conditions.

Use Cases:
- Alert when unread message count > 100
- Alert when task backlog > 50
- Alert when API error rate > 5%
- Alert on composite conditions (AND/OR logic)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.models import (
    AgentRegistry,
    ConditionMonitor,
    ConditionAlert,
    ConditionAlertStatus,
    ConditionMonitorType,
)
from core.agent_integration_gateway import ActionType, agent_integration_gateway

logger = logging.getLogger(__name__)


class ConditionMonitoringService:
    """
    Service for creating and managing condition monitors.

    Monitors business conditions and triggers alerts when thresholds are exceeded.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_monitor(
        self,
        agent_id: str,
        name: str,
        condition_type: str,
        threshold_config: Dict[str, Any],
        platforms: List[Dict[str, str]],
        check_interval_seconds: int = 300,
        alert_template: Optional[str] = None,
        composite_logic: Optional[str] = None,
        composite_conditions: Optional[List[Dict[str, Any]]] = None,
        governance_metadata: Optional[Dict[str, Any]] = None,
    ) -> ConditionMonitor:
        """
        Create a new condition monitor.

        Args:
            agent_id: ID of the agent creating the monitor
            name: Human-readable name
            condition_type: inbox_volume, task_backlog, api_metrics, database_query, composite
            threshold_config: Threshold configuration
                Example: {"metric": "unread_count", "operator": ">", "value": 100}
            platforms: List of {platform, recipient_id} for alerts
            check_interval_seconds: How often to check (default: 300 = 5 minutes)
            alert_template: Optional custom alert message template
            composite_logic: "AND" or "OR" for composite conditions
            composite_conditions: List of sub-conditions for composite monitors
            governance_metadata: Optional governance metadata

        Returns:
            Created ConditionMonitor object

        Raises:
            HTTPException: If validation fails
        """
        # Validate agent
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )

        # Validate threshold_config
        if not threshold_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="threshold_config is required"
            )

        # Validate composite conditions
        if condition_type == ConditionMonitorType.COMPOSITE.value:
            if not composite_logic or not composite_conditions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="composite_logic and composite_conditions required for composite type"
                )
            if composite_logic not in ["AND", "OR"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="composite_logic must be 'AND' or 'OR'"
                )

        # Create the monitor
        monitor = ConditionMonitor(
            agent_id=agent_id,
            agent_name=agent.name,
            name=name,
            condition_type=condition_type,
            threshold_config=threshold_config,
            composite_logic=composite_logic,
            composite_conditions=composite_conditions,
            check_interval_seconds=check_interval_seconds,
            platforms=platforms,
            alert_template=alert_template,
            status="active",
            governance_metadata=governance_metadata or {},
        )

        self.db.add(monitor)
        self.db.commit()
        self.db.refresh(monitor)

        logger.info(
            f"Created condition monitor {monitor.id} ({name}) "
            f"of type {condition_type} for agent {agent.name}"
        )

        return monitor

    def update_monitor(
        self,
        monitor_id: str,
        name: Optional[str] = None,
        threshold_config: Optional[Dict[str, Any]] = None,
        check_interval_seconds: Optional[int] = None,
        alert_template: Optional[str] = None,
        platforms: Optional[List[Dict[str, str]]] = None,
    ) -> ConditionMonitor:
        """Update an existing condition monitor."""
        monitor = self.db.query(ConditionMonitor).filter(
            ConditionMonitor.id == monitor_id
        ).first()

        if not monitor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Condition monitor {monitor_id} not found"
            )

        # Update fields
        if name is not None:
            monitor.name = name
        if threshold_config is not None:
            monitor.threshold_config = threshold_config
        if check_interval_seconds is not None:
            monitor.check_interval_seconds = check_interval_seconds
        if alert_template is not None:
            monitor.alert_template = alert_template
        if platforms is not None:
            monitor.platforms = platforms

        self.db.commit()
        self.db.refresh(monitor)

        logger.info(f"Updated condition monitor {monitor_id}")

        return monitor

    def pause_monitor(self, monitor_id: str) -> ConditionMonitor:
        """Pause a condition monitor."""
        monitor = self.db.query(ConditionMonitor).filter(
            ConditionMonitor.id == monitor_id
        ).first()

        if not monitor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Condition monitor {monitor_id} not found"
            )

        monitor.status = "paused"
        self.db.commit()
        self.db.refresh(monitor)

        logger.info(f"Paused condition monitor {monitor_id}")

        return monitor

    def resume_monitor(self, monitor_id: str) -> ConditionMonitor:
        """Resume a paused condition monitor."""
        monitor = self.db.query(ConditionMonitor).filter(
            ConditionMonitor.id == monitor_id
        ).first()

        if not monitor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Condition monitor {monitor_id} not found"
            )

        monitor.status = "active"
        self.db.commit()
        self.db.refresh(monitor)

        logger.info(f"Resumed condition monitor {monitor_id}")

        return monitor

    def delete_monitor(self, monitor_id: str) -> ConditionMonitor:
        """Delete a condition monitor."""
        monitor = self.db.query(ConditionMonitor).filter(
            ConditionMonitor.id == monitor_id
        ).first()

        if not monitor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Condition monitor {monitor_id} not found"
            )

        self.db.delete(monitor)
        self.db.commit()

        logger.info(f"Deleted condition monitor {monitor_id}")

        return monitor

    def get_monitors(
        self,
        agent_id: Optional[str] = None,
        condition_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[ConditionMonitor]:
        """Get condition monitors with optional filters."""
        query = self.db.query(ConditionMonitor)

        if agent_id:
            query = query.filter(ConditionMonitor.agent_id == agent_id)
        if condition_type:
            query = query.filter(ConditionMonitor.condition_type == condition_type)
        if status:
            query = query.filter(ConditionMonitor.status == status)

        monitors = query.order_by(ConditionMonitor.created_at.desc()).limit(limit).all()
        return monitors

    def get_monitor(self, monitor_id: str) -> Optional[ConditionMonitor]:
        """Get a specific monitor by ID."""
        return self.db.query(ConditionMonitor).filter(
            ConditionMonitor.id == monitor_id
        ).first()

    def get_alerts(
        self,
        monitor_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[ConditionAlert]:
        """Get alerts with optional filters."""
        query = self.db.query(ConditionAlert)

        if monitor_id:
            query = query.filter(ConditionAlert.monitor_id == monitor_id)
        if status:
            query = query.filter(ConditionAlert.status == status)

        alerts = query.order_by(ConditionAlert.triggered_at.desc()).limit(limit).all()
        return alerts

    async def check_and_alert_monitors(self) -> Dict[str, int]:
        """
        Check all active monitors and send alerts for triggered conditions.

        Should be called periodically (e.g., every minute by scheduler).
        Implements throttling to prevent alert spam.

        Returns:
            Dictionary with counts: {"checked": X, "triggered": Y, "alerts_sent": Z}
        """
        now = datetime.now(timezone.utc)

        # Find active monitors
        monitors = self.db.query(ConditionMonitor).filter(
            ConditionMonitor.status == "active"
        ).all()

        checked_count = 0
        triggered_count = 0
        alerts_sent_count = 0

        for monitor in monitors:
            try:
                checked_count += 1

                # Check if should throttle (prevent alert spam)
                if monitor.last_alert_sent_at:
                    time_since_last_alert = (now - monitor.last_alert_sent_at).total_seconds()
                    throttle_seconds = monitor.throttle_minutes * 60

                    if time_since_last_alert < throttle_seconds:
                        logger.debug(
                            f"Monitor {monitor.id} throttled, "
                            f"last alert {time_since_last_alert}s ago"
                        )
                        continue

                # Check condition
                from core.condition_checkers import ConditionCheckers
                checkers = ConditionCheckers(self.db)

                condition_result = checkers.check_condition(monitor)

                if condition_result["triggered"]:
                    triggered_count += 1

                    # Create alert
                    alert = ConditionAlert(
                        monitor_id=monitor.id,
                        condition_value=condition_result["value"],
                        threshold_value=monitor.threshold_config,
                        alert_message=self._generate_alert_message(monitor, condition_result),
                        status=ConditionAlertStatus.PENDING.value,
                        triggered_at=now,
                    )
                    self.db.add(alert)
                    self.db.commit()

                    # Send alerts to all platforms
                    sent_count = await self._send_alert(monitor, alert, condition_result)

                    if sent_count > 0:
                        alerts_sent_count += sent_count
                        alert.status = ConditionAlertStatus.SENT.value
                        alert.sent_at = now
                        monitor.last_alert_sent_at = now
                        self.db.commit()

                        logger.info(
                            f"Alert sent for monitor {monitor.id} ({monitor.name}) "
                            f"to {sent_count} platforms"
                        )
                    else:
                        alert.status = ConditionAlertStatus.FAILED.value
                        alert.error_message = "Failed to send to any platform"
                        self.db.commit()

            except Exception as e:
                logger.error(f"Error checking monitor {monitor.id}: {e}", exc_info=True)

        logger.info(
            f"Checked {checked_count} monitors, "
            f"{triggered_count} triggered, "
            f"{alerts_sent_count} alerts sent"
        )

        return {
            "checked": checked_count,
            "triggered": triggered_count,
            "alerts_sent": alerts_sent_count,
        }

    def _generate_alert_message(
        self,
        monitor: ConditionMonitor,
        condition_result: Dict[str, Any],
    ) -> str:
        """Generate alert message from template or default."""
        # Use custom template if provided
        if monitor.alert_template:
            message = monitor.alert_template
            # Substitute condition values
            message = message.replace("{{value}}", str(condition_result["value"]))
            message = message.replace("{{threshold}}", str(monitor.threshold_config))
            return message

        # Generate default message
        value = condition_result["value"]
        threshold = monitor.threshold_config.get("value", monitor.threshold_config)
        operator = monitor.threshold_config.get("operator", ">")
        metric = monitor.threshold_config.get("metric", "")

        if condition_result["metric_name"]:
            metric_name = condition_result["metric_name"]
            return f"⚠️ Alert: {metric_name} is {value} (threshold: {operator} {threshold})"
        else:
            return f"⚠️ Alert: Condition '{monitor.name}' triggered (value: {value}, threshold: {operator} {threshold})"

    async def _send_alert(
        self,
        monitor: ConditionMonitor,
        alert: ConditionAlert,
        condition_result: Dict[str, Any],
    ) -> int:
        """
        Send alert to all configured platforms.

        Returns:
            Number of platforms successfully sent to
        """
        sent_count = 0
        platforms_sent = []

        for platform_config in monitor.platforms:
            platform = platform_config.get("platform")
            recipient_id = platform_config.get("recipient_id")

            if not platform or not recipient_id:
                logger.warning(f"Invalid platform config: {platform_config}")
                continue

            try:
                # Send via AgentIntegrationGateway
                params = {
                    "recipient_id": recipient_id,
                    "content": alert.alert_message,
                    "workspace_id": "default",
                }

                result = await agent_integration_gateway.execute_action(
                    ActionType.SEND_MESSAGE,
                    platform,
                    params
                )

                if result.get("status") == "success":
                    sent_count += 1
                    platforms_sent.append({
                        "platform": platform,
                        "status": "sent",
                        "message_id": result.get("message_id"),
                    })
                else:
                    platforms_sent.append({
                        "platform": platform,
                        "status": "failed",
                        "error": result.get("error"),
                    })

            except Exception as e:
                logger.error(f"Failed to send alert to {platform}: {e}")
                platforms_sent.append({
                    "platform": platform,
                    "status": "error",
                    "error": str(e),
                })

        # Update alert with platforms_sent
        alert.platforms_sent = platforms_sent
        self.db.commit()

        return sent_count

    def get_presets(self) -> List[Dict[str, Any]]:
        """
        Get pre-configured monitoring presets.

        Returns list of preset configurations for common monitoring scenarios.
        """
        presets = [
            {
                "name": "High Inbox Volume",
                "description": "Alert when unread message count exceeds threshold",
                "condition_type": "inbox_volume",
                "threshold_config": {
                    "metric": "unread_count",
                    "operator": ">",
                    "value": 100,
                },
                "check_interval_seconds": 300,
                "recommended_platforms": ["slack", "discord"],
            },
            {
                "name": "Task Backlog",
                "description": "Alert when pending tasks exceed threshold",
                "condition_type": "task_backlog",
                "threshold_config": {
                    "metric": "pending_count",
                    "operator": ">",
                    "value": 50,
                },
                "check_interval_seconds": 600,
                "recommended_platforms": ["slack", "teams"],
            },
            {
                "name": "High API Error Rate",
                "description": "Alert when API error rate exceeds threshold",
                "condition_type": "api_metrics",
                "threshold_config": {
                    "metric": "error_rate",
                    "operator": ">",
                    "value": 0.05,
                    "window": "5m",
                },
                "check_interval_seconds": 300,
                "recommended_platforms": ["slack", "discord"],
            },
            {
                "name": "Database Connection Pool",
                "description": "Alert when DB connections exceed threshold",
                "condition_type": "database_query",
                "threshold_config": {
                    "metric": "active_connections",
                    "operator": ">",
                    "value": 80,
                },
                "check_interval_seconds": 120,
                "recommended_platforms": ["slack", "discord"],
            },
        ]

        return presets

    def test_condition(self, monitor_id: str) -> Dict[str, Any]:
        """
        Test a condition monitor immediately without sending alerts.

        Useful for validating monitor configuration.

        Returns:
            Condition check result with current value and triggered status
        """
        monitor = self.db.query(ConditionMonitor).filter(
            ConditionMonitor.id == monitor_id
        ).first()

        if not monitor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Condition monitor {monitor_id} not found"
            )

        from core.condition_checkers import ConditionCheckers
        checkers = ConditionCheckers(self.db)

        result = checkers.check_condition(monitor)

        return {
            "monitor_id": monitor_id,
            "monitor_name": monitor.name,
            "condition_type": monitor.condition_type,
            "triggered": result["triggered"],
            "current_value": result["value"],
            "threshold": monitor.threshold_config,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get system metrics for monitoring.

        Returns overall statistics about the monitoring system.
        """
        from sqlalchemy import func

        total_monitors = self.db.query(func.count(ConditionMonitor.id)).scalar()
        active_monitors = self.db.query(func.count(ConditionMonitor.id)).filter(
            ConditionMonitor.status == "active"
        ).scalar()

        total_alerts = self.db.query(func.count(ConditionAlert.id)).scalar()
        pending_alerts = self.db.query(func.count(ConditionAlert.id)).filter(
            ConditionAlert.status == ConditionAlertStatus.PENDING.value
        ).scalar()

        recent_alerts = self.db.query(func.count(ConditionAlert.id)).filter(
            ConditionAlert.triggered_at >= datetime.now(timezone.utc) - timedelta(hours=24)
        ).scalar()

        return {
            "total_monitors": total_monitors,
            "active_monitors": active_monitors,
            "total_alerts": total_alerts,
            "pending_alerts": pending_alerts,
            "alerts_last_24h": recent_alerts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
