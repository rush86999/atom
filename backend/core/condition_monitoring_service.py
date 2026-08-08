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

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.agent_integration_gateway import ActionType, agent_integration_gateway
from core.condition_checkers import CONDITION_TYPE_COMPOSITE
from core.models import (
    AgentRegistry,
    ConditionAlert,
    ConditionMonitor,
)

logger = logging.getLogger(__name__)


class ConditionMonitoringService:
    """
    Service for creating and managing condition monitors.

    Monitors business conditions and triggers alerts when thresholds are exceeded.
    """

    def __init__(self, db: Session):
        self.db = db

    def _hydrate_config(self, monitor: ConditionMonitor) -> ConditionMonitor:
        """Mirror the JSON ``condition_config`` onto plain attributes.

        The stub ``ConditionMonitor`` model only persists ``condition_config``;
        readers like ``ConditionCheckers.check_condition`` still access
        ``monitor.threshold_config``/``composite_logic``/... directly. After a
        DB re-fetch those attributes don't exist, so restore them from the
        persisted config. Non-persisted convenience attrs (``status``,
        ``agent_id``, ``agent_name``) are set to stable defaults.
        """
        cfg = monitor.condition_config or {}
        monitor.agent_id = getattr(monitor, "agent_id", None)
        monitor.agent_name = getattr(monitor, "agent_name", None)
        monitor.threshold_config = cfg.get("threshold_config", {})
        monitor.platforms = cfg.get("platforms", [])
        monitor.check_interval_seconds = cfg.get("check_interval_seconds", 300)
        monitor.alert_template = cfg.get("alert_template")
        monitor.composite_logic = cfg.get("composite_logic")
        monitor.composite_conditions = cfg.get("composite_conditions", [])
        monitor.governance_metadata = cfg.get("governance_metadata", {})
        monitor.status = "active" if monitor.is_active else "paused"
        return monitor

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

        # Validate threshold_config. Composite monitors carry their thresholds
        # inside ``composite_conditions``, so an empty threshold_config is
        # legitimate for them (the composite validation below covers the rest).
        if not threshold_config and condition_type != CONDITION_TYPE_COMPOSITE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="threshold_config is required"
            )

        # Validate composite conditions.
        # NOTE: ``ConditionMonitorType`` is a SQLAlchemy table model, NOT an
        # enum — ``ConditionMonitorType.COMPOSITE.value`` raises AttributeError.
        # Use the string constant from condition_checkers (mirrors the fix
        # applied there in the latent-NameError sweep).
        if condition_type == CONDITION_TYPE_COMPOSITE:
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

        # Create the monitor.
        #
        # The ``ConditionMonitor`` model (core/models.py) is a stub with only
        # ``name``/``user_id``/``condition_type``/``condition_config``/
        # ``is_active`` columns — it has no threshold_config/platforms/...
        # columns, so passing them as constructor kwargs raises TypeError.
        # The rich config is persisted inside the JSON ``condition_config``
        # column, and mirrored onto plain instance attributes so existing
        # readers (ConditionCheckers, _generate_alert_message, _send_alert)
        # keep working on the returned object.
        config: Dict[str, Any] = {
            "threshold_config": threshold_config,
            "platforms": platforms,
            "check_interval_seconds": check_interval_seconds,
            "alert_template": alert_template,
            "composite_logic": composite_logic,
            "composite_conditions": composite_conditions,
            "governance_metadata": governance_metadata or {},
        }
        monitor = ConditionMonitor(
            user_id=agent.user_id or agent_id,
            name=name,
            condition_type=condition_type,
            condition_config=config,
            is_active=True,
        )
        monitor.agent_id = agent_id
        monitor.agent_name = agent.name
        monitor.threshold_config = threshold_config
        monitor.platforms = platforms
        monitor.check_interval_seconds = check_interval_seconds
        monitor.alert_template = alert_template
        monitor.composite_logic = composite_logic
        monitor.composite_conditions = composite_conditions
        monitor.governance_metadata = governance_metadata or {}
        monitor.status = "active"

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

        self._hydrate_config(monitor)

        # Update fields. The JSON ``condition_config`` column is not
        # mutation-tracked, so always assign a fresh dict rather than mutating
        # in place (in-place changes are silently dropped on commit).
        if name is not None:
            monitor.name = name
        cfg = dict(monitor.condition_config or {})
        if check_interval_seconds is not None:
            monitor.check_interval_seconds = check_interval_seconds
            cfg["check_interval_seconds"] = check_interval_seconds
        if alert_template is not None:
            monitor.alert_template = alert_template
            cfg["alert_template"] = alert_template
        if platforms is not None:
            monitor.platforms = platforms
            cfg["platforms"] = platforms
        if threshold_config is not None:
            monitor.threshold_config = threshold_config
            cfg["threshold_config"] = threshold_config
        monitor.condition_config = cfg

        self.db.commit()
        self.db.refresh(monitor)
        self._hydrate_config(monitor)

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

        monitor.is_active = False
        monitor.status = "paused"
        self.db.commit()
        self.db.refresh(monitor)
        self._hydrate_config(monitor)

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

        monitor.is_active = True
        monitor.status = "active"
        self.db.commit()
        self.db.refresh(monitor)
        self._hydrate_config(monitor)

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

        # The stub model has no ``agent_id`` column — monitors are linked via
        # ``user_id`` (set to the creating agent's id/owner at creation).
        if agent_id:
            query = query.filter(ConditionMonitor.user_id == agent_id)
        if condition_type:
            query = query.filter(ConditionMonitor.condition_type == condition_type)
        if status is not None:
            query = query.filter(ConditionMonitor.is_active == (status == "active"))

        monitors = query.order_by(ConditionMonitor.created_at.desc()).limit(limit).all()
        for monitor in monitors:
            self._hydrate_config(monitor)
        return monitors

    def get_monitor(self, monitor_id: str) -> Optional[ConditionMonitor]:
        """Get a specific monitor by ID."""
        monitor = self.db.query(ConditionMonitor).filter(
            ConditionMonitor.id == monitor_id
        ).first()
        if monitor:
            self._hydrate_config(monitor)
        return monitor

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
        if status is not None:
            if status == "resolved":
                query = query.filter(ConditionAlert.is_resolved == True)  # noqa: E712
            elif status == "unresolved":
                query = query.filter(ConditionAlert.is_resolved == False)  # noqa: E712

        alerts = query.order_by(ConditionAlert.created_at.desc()).limit(limit).all()

        # Hydrate the plain attributes the stub alert model can't persist so
        # the monitoring routes' AlertResponse (from_attributes) serializes.
        for alert in alerts:
            alert.condition_value = getattr(alert, "condition_value", {})
            alert.threshold_value = getattr(alert, "threshold_value", {})
            alert.alert_message = getattr(alert, "alert_message", alert.message)
            alert.platforms_sent = getattr(alert, "platforms_sent", [])
            alert.status = getattr(alert, "status", "sent")
            alert.triggered_at = getattr(alert, "triggered_at", alert.created_at)
            alert.sent_at = getattr(alert, "sent_at", None)
            alert.error_message = getattr(alert, "error_message", None)
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
            ConditionMonitor.is_active == True  # noqa: E712
        ).all()

        checked_count = 0
        triggered_count = 0
        alerts_sent_count = 0

        for monitor in monitors:
            try:
                checked_count += 1
                self._hydrate_config(monitor)

                # Check if should throttle (prevent alert spam)
                last_alert_sent_at = getattr(monitor, "last_alert_sent_at", None)
                if last_alert_sent_at:
                    # Normalize a naive timestamp to UTC before subtracting.
                    # ``now`` is timezone-aware (UTC); subtracting a naive
                    # datetime raises TypeError, which the broad ``except``
                    # below would swallow and silently skip this monitor's
                    # condition check (i.e. silently disable monitoring for it).
                    last_sent = last_alert_sent_at
                    if last_sent.tzinfo is None:
                        last_sent = last_sent.replace(tzinfo=timezone.utc)
                    time_since_last_alert = (now - last_sent).total_seconds()
                    throttle_seconds = getattr(monitor, "throttle_minutes", 30) * 60

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

                    # Create alert. The stub ``ConditionAlert`` model only has
                    # monitor_id/alert_type/message/is_resolved columns; the
                    # richer fields are carried as plain attributes so the
                    # monitoring routes' AlertResponse can still serialize them.
                    alert_message = self._generate_alert_message(monitor, condition_result)
                    alert = ConditionAlert(
                        monitor_id=monitor.id,
                        alert_type="warning",
                        message=alert_message,
                        is_resolved=False,
                    )
                    alert.status = "pending"
                    alert.condition_value = condition_result["value"]
                    alert.threshold_value = monitor.threshold_config
                    alert.alert_message = alert_message
                    alert.triggered_at = now
                    alert.platforms_sent = []
                    alert.sent_at = None
                    alert.error_message = None
                    self.db.add(alert)
                    self.db.commit()

                    # Send alerts to all platforms
                    sent_count = await self._send_alert(monitor, alert, condition_result)

                    if sent_count > 0:
                        alerts_sent_count += sent_count
                        alert.status = "sent"
                        alert.sent_at = now
                        monitor.last_alert_sent_at = now
                        self.db.commit()

                        logger.info(
                            f"Alert sent for monitor {monitor.id} ({monitor.name}) "
                            f"to {sent_count} platforms"
                        )
                    else:
                        alert.status = "failed"
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
                    "content": alert.message,
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
        monitor = self.get_monitor(monitor_id)

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
            ConditionAlert.is_resolved == False  # noqa: E712
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
