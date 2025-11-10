import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import redis
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(Enum):
    """Types of workflow automation alerts"""

    PERFORMANCE_DEGRADATION = "performance_degradation"
    ERROR_RATE_INCREASE = "error_rate_increase"
    WORKFLOW_STALLED = "workflow_stalled"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    CONNECTIVITY_ISSUE = "connectivity_issue"
    DATA_QUALITY_ISSUE = "data_quality_issue"
    SECURITY_ISSUE = "security_issue"
    CUSTOM_METRIC_ALERT = "custom_metric_alert"


class MonitoringStatus(Enum):
    """Monitoring system status"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class WorkflowAlert:
    """Represents a workflow automation alert"""

    alert_id: str
    workflow_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    trigger_conditions: Dict[str, Any]
    current_values: Dict[str, Any]
    created_at: datetime = None
    acknowledged: bool = False
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolution_notes: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class WorkflowMetric:
    """Represents a workflow metric being monitored"""

    metric_id: str
    workflow_id: str
    metric_name: str
    value: float
    unit: str
    tags: Dict[str, str]
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class MonitoringRule:
    """Monitoring rule for workflow automation"""

    rule_id: str
    workflow_id: str
    metric_name: str
    condition: str
    threshold: float
    alert_type: AlertType
    severity: AlertSeverity
    description: str
    cooldown_minutes: int = 5
    is_active: bool = True
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class WorkflowMonitoringSystem:
    """
    Comprehensive Workflow Automation Monitoring and Alerting System
    Provides real-time monitoring, alerting, and health checks for workflow automation
    """

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis_client = redis.Redis(
            host=redis_host, port=redis_port, decode_responses=True
        )
        self.monitoring_rules: Dict[str, MonitoringRule] = {}
        self.active_alerts: Dict[str, WorkflowAlert] = {}
        self.metric_history: Dict[str, List[WorkflowMetric]] = {}

        # Prometheus metrics
        self._initialize_prometheus_metrics()

        # Alert handlers
        self.alert_handlers = self._initialize_alert_handlers()

        # Health check intervals
        self.health_check_interval = 60  # seconds

        logger.info("Workflow Monitoring System initialized")

    def _initialize_prometheus_metrics(self):
        """Initialize Prometheus metrics for monitoring"""
        # Workflow execution metrics
        self.workflow_execution_counter = Counter(
            "workflow_executions_total",
            "Total number of workflow executions",
            ["workflow_id", "status"],
        )

        self.workflow_execution_duration = Histogram(
            "workflow_execution_duration_seconds",
            "Workflow execution duration in seconds",
            ["workflow_id"],
        )

        self.workflow_error_rate = Gauge(
            "workflow_error_rate", "Workflow error rate percentage", ["workflow_id"]
        )

        self.workflow_response_time = Gauge(
            "workflow_response_time_seconds",
            "Workflow response time in seconds",
            ["workflow_id"],
        )

        # Alert metrics
        self.active_alerts_gauge = Gauge(
            "workflow_active_alerts",
            "Number of active workflow alerts",
            ["severity", "workflow_id"],
        )

        self.alert_fired_counter = Counter(
            "workflow_alerts_fired_total",
            "Total number of workflow alerts fired",
            ["alert_type", "severity", "workflow_id"],
        )

    def _initialize_alert_handlers(self) -> Dict[AlertType, callable]:
        """Initialize alert handlers for different alert types"""
        return {
            AlertType.PERFORMANCE_DEGRADATION: self._handle_performance_alert,
            AlertType.ERROR_RATE_INCREASE: self._handle_error_rate_alert,
            AlertType.WORKFLOW_STALLED: self._handle_stalled_workflow_alert,
            AlertType.RESOURCE_EXHAUSTION: self._handle_resource_alert,
            AlertType.CONNECTIVITY_ISSUE: self._handle_connectivity_alert,
            AlertType.DATA_QUALITY_ISSUE: self._handle_data_quality_alert,
            AlertType.SECURITY_ISSUE: self._handle_security_alert,
            AlertType.CUSTOM_METRIC_ALERT: self._handle_custom_metric_alert,
        }

    async def start_monitoring_server(self, port: int = 8000):
        """Start Prometheus metrics server"""
        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")

    def add_monitoring_rule(self, rule: MonitoringRule) -> str:
        """Add a new monitoring rule"""
        self.monitoring_rules[rule.rule_id] = rule
        logger.info(
            f"Added monitoring rule: {rule.description} for workflow {rule.workflow_id}"
        )
        return rule.rule_id

    def remove_monitoring_rule(self, rule_id: str) -> bool:
        """Remove a monitoring rule"""
        if rule_id in self.monitoring_rules:
            del self.monitoring_rules[rule_id]
            logger.info(f"Removed monitoring rule: {rule_id}")
            return True
        return False

    async def record_workflow_metric(self, metric: WorkflowMetric) -> bool:
        """Record a workflow metric"""
        try:
            # Store in memory
            if metric.workflow_id not in self.metric_history:
                self.metric_history[metric.workflow_id] = []
            self.metric_history[metric.workflow_id].append(metric)

            # Keep only last 1000 metrics per workflow to prevent memory issues
            if len(self.metric_history[metric.workflow_id]) > 1000:
                self.metric_history[metric.workflow_id] = self.metric_history[
                    metric.workflow_id
                ][-1000:]

            # Store in Redis for persistence
            redis_key = f"workflow_metric:{metric.workflow_id}:{metric.metric_name}"
            metric_data = {
                "value": metric.value,
                "unit": metric.unit,
                "timestamp": metric.timestamp.isoformat(),
                "tags": json.dumps(metric.tags),
            }
            self.redis_client.hset(redis_key, mapping=metric_data)
            self.redis_client.expire(redis_key, 3600)  # Keep for 1 hour

            # Update Prometheus metrics
            self._update_prometheus_metrics(metric)

            # Check for alert conditions
            await self._check_alert_conditions(metric)

            return True

        except Exception as e:
            logger.error(f"Failed to record workflow metric: {e}")
            return False

    def _update_prometheus_metrics(self, metric: WorkflowMetric):
        """Update Prometheus metrics based on workflow metric"""
        if metric.metric_name == "error_rate":
            self.workflow_error_rate.labels(workflow_id=metric.workflow_id).set(
                metric.value
            )
        elif metric.metric_name == "response_time":
            self.workflow_response_time.labels(workflow_id=metric.workflow_id).set(
                metric.value
            )
        elif metric.metric_name == "execution_count":
            status = metric.tags.get("status", "unknown")
            self.workflow_execution_counter.labels(
                workflow_id=metric.workflow_id, status=status
            ).inc(metric.value)

    async def _check_alert_conditions(self, metric: WorkflowMetric):
        """Check if any monitoring rules are triggered by the metric"""
        for rule in self.monitoring_rules.values():
            if not rule.is_active:
                continue

            if (
                rule.workflow_id != metric.workflow_id
                or rule.metric_name != metric.metric_name
            ):
                continue

            # Check if rule condition is met
            if self._evaluate_condition(metric.value, rule.condition, rule.threshold):
                # Check cooldown period
                if await self._is_in_cooldown(rule.rule_id):
                    continue

                # Create and fire alert
                await self._fire_alert(rule, metric)

    def _evaluate_condition(
        self, value: float, condition: str, threshold: float
    ) -> bool:
        """Evaluate monitoring condition"""
        if condition == "greater_than":
            return value > threshold
        elif condition == "greater_than_equal":
            return value >= threshold
        elif condition == "less_than":
            return value < threshold
        elif condition == "less_than_equal":
            return value <= threshold
        elif condition == "equal":
            return value == threshold
        elif condition == "not_equal":
            return value != threshold
        else:
            logger.warning(f"Unknown condition: {condition}")
            return False

    async def _is_in_cooldown(self, rule_id: str) -> bool:
        """Check if rule is in cooldown period"""
        cooldown_key = f"alert_cooldown:{rule_id}"
        cooldown_exists = self.redis_client.exists(cooldown_key)
        return cooldown_exists

    async def _fire_alert(self, rule: MonitoringRule, metric: WorkflowMetric):
        """Fire an alert based on monitoring rule"""
        try:
            alert_id = str(uuid.uuid4())

            alert = WorkflowAlert(
                alert_id=alert_id,
                workflow_id=rule.workflow_id,
                alert_type=rule.alert_type,
                severity=rule.severity,
                title=f"{rule.alert_type.value.replace('_', ' ').title()} - {rule.workflow_id}",
                description=rule.description,
                trigger_conditions={
                    "metric_name": rule.metric_name,
                    "condition": rule.condition,
                    "threshold": rule.threshold,
                    "current_value": metric.value,
                },
                current_values={rule.metric_name: metric.value},
            )

            # Store alert
            self.active_alerts[alert_id] = alert

            # Set cooldown
            cooldown_key = f"alert_cooldown:{rule.rule_id}"
            self.redis_client.setex(
                cooldown_key, rule.cooldown_minutes * 60, "cooldown"
            )

            # Update Prometheus metrics
            self.active_alerts_gauge.labels(
                severity=rule.severity.value, workflow_id=rule.workflow_id
            ).inc()

            self.alert_fired_counter.labels(
                alert_type=rule.alert_type.value,
                severity=rule.severity.value,
                workflow_id=rule.workflow_id,
            ).inc()

            # Call alert handler
            handler = self.alert_handlers.get(rule.alert_type)
            if handler:
                await handler(alert)

            logger.warning(
                f"Alert fired: {alert.title} (Severity: {alert.severity.value})"
            )

        except Exception as e:
            logger.error(f"Failed to fire alert: {e}")

    async def _handle_performance_alert(self, alert: WorkflowAlert):
        """Handle performance degradation alerts"""
        # In production, this would send notifications to appropriate channels
        logger.warning(f"Performance alert: {alert.title}")
        # Example: Send to Slack, PagerDuty, email, etc.

    async def _handle_error_rate_alert(self, alert: WorkflowAlert):
        """Handle error rate increase alerts"""
        logger.warning(f"Error rate alert: {alert.title}")

    async def _handle_stalled_workflow_alert(self, alert: WorkflowAlert):
        """Handle stalled workflow alerts"""
        logger.warning(f"Stalled workflow alert: {alert.title}")

    async def _handle_resource_alert(self, alert: WorkflowAlert):
        """Handle resource exhaustion alerts"""
        logger.warning(f"Resource alert: {alert.title}")

    async def _handle_connectivity_alert(self, alert: WorkflowAlert):
        """Handle connectivity issue alerts"""
        logger.warning(f"Connectivity alert: {alert.title}")

    async def _handle_data_quality_alert(self, alert: WorkflowAlert):
        """Handle data quality issue alerts"""
        logger.warning(f"Data quality alert: {alert.title}")

    async def _handle_security_alert(self, alert: WorkflowAlert):
        """Handle security issue alerts"""
        logger.error(f"Security alert: {alert.title}")

    async def _handle_custom_metric_alert(self, alert: WorkflowAlert):
        """Handle custom metric alerts"""
        logger.warning(f"Custom metric alert: {alert.title}")

    async def acknowledge_alert(
        self, alert_id: str, acknowledged_by: str, notes: str = ""
    ) -> bool:
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.acknowledged = True
            alert.acknowledged_by = acknowledged_by
            alert.resolution_notes = notes

            # Update Prometheus metrics
            self.active_alerts_gauge.labels(
                severity=alert.severity.value, workflow_id=alert.workflow_id
            ).dec()

            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return True
        return False

    async def resolve_alert(self, alert_id: str, resolution_notes: str = "") -> bool:
        """Resolve an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved_at = datetime.now()
            alert.resolution_notes = resolution_notes

            # Remove from active alerts
            del self.active_alerts[alert_id]

            logger.info(f"Alert {alert_id} resolved")
            return True
        return False

    def get_workflow_metrics(
        self,
        workflow_id: str,
        metric_name: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
    ) -> List[WorkflowMetric]:
        """Get workflow metrics with optional filtering"""
        if workflow_id not in self.metric_history:
            return []

        metrics = self.metric_history[workflow_id]

        # Apply filters
        if metric_name:
            metrics = [m for m in metrics if m.metric_name == metric_name]

        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]

        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]

        return sorted(metrics, key=lambda x: x.timestamp)

    def get_active_alerts(
        self, workflow_id: str = None, severity: AlertSeverity = None
    ) -> List[WorkflowAlert]:
        """Get active alerts with optional filtering"""
        alerts = list(self.active_alerts.values())

        if workflow_id:
            alerts = [a for a in alerts if a.workflow_id == workflow_id]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda x: x.created_at)

    async def get_workflow_health_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get comprehensive health status for a workflow"""
        try:
            # Get recent metrics
            recent_metrics = self.get_workflow_metrics(
                workflow_id, start_time=datetime.now() - timedelta(hours=1)
            )

            # Calculate health score
            health_score = self._calculate_health_score(workflow_id, recent_metrics)

            # Get active alerts
            active_alerts = self.get_active_alerts(workflow_id)

            # Determine overall status
            if any(
                alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]
                for alert in active_alerts
            ):
                status = MonitoringStatus.UNHEALTHY
            elif active_alerts:
                status = MonitoringStatus.DEGRADED
            elif health_score >= 80:
                status = MonitoringStatus.HEALTHY
            else:
                status = MonitoringStatus.DEGRADED

            return {
                "workflow_id": workflow_id,
                "status": status.value,
                "health_score": health_score,
                "active_alerts_count": len(active_alerts),
                "critical_alerts": len(
                    [a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]
                ),
                "last_updated": datetime.now().isoformat(),
                "metrics_collected": len(recent_metrics),
            }

        except Exception as e:
            logger.error(f"Failed to get workflow health status: {e}")
            return {
                "workflow_id": workflow_id,
                "status": MonitoringStatus.UNKNOWN.value,
                "health_score": 0,
                "reason": f"Error: {str(e)}",
                "last_updated": datetime.now().isoformat(),
                "active_alerts_count": 0,
                "critical_alerts": 0,
                "metrics_collected": 0,
            }

    def _calculate_health_score(
        self, workflow_id: str, recent_metrics: List[WorkflowMetric]
    ) -> float:
        """Calculate health score based on recent metrics"""
        if not recent_metrics:
            return 100.0

        # Start with perfect score
        base_score = 100.0

        # Analyze response times
        response_times = [
            m.value for m in recent_metrics if m.metric_name == "response_time"
        ]
        if response_times:
            avg_response = sum(response_times) / len(response_times)
            if avg_response > 10.0:
                base_score -= 30
            elif avg_response > 5.0:
                base_score -= 15
            elif avg_response > 2.0:
                base_score -= 5

        # Analyze error rates
        error_rates = [m.value for m in recent_metrics if m.metric_name == "error_rate"]
        if error_rates:
            avg_error_rate = sum(error_rates) / len(error_rates)
            if avg_error_rate > 0.1:
                base_score -= 40
            elif avg_error_rate > 0.05:
                base_score -= 20
            elif avg_error_rate > 0.01:
                base_score -= 10

        # Analyze throughput
        throughputs = [m.value for m in recent_metrics if m.metric_name == "throughput"]
        if throughputs:
            avg_throughput = sum(throughputs) / len(throughputs)
            if avg_throughput < 10:
                base_score -= 20
            elif avg_throughput < 50:
                base_score -= 10

        # Ensure score is within bounds
        return max(0.0, min(100.0, base_score))

    async def cleanup_old_data(self, retention_days: int = 30):
        """Clean up old monitoring data"""
        try:
            cutoff_time = datetime.now() - timedelta(days=retention_days)

            # Clean up old metrics from memory
            for workflow_id in list(self.metric_history.keys()):
                self.metric_history[workflow_id] = [
                    m
                    for m in self.metric_history[workflow_id]
                    if m.timestamp >= cutoff_time
                ]

                # Remove empty workflow entries
                if not self.metric_history[workflow_id]:
                    del self.metric_history[workflow_id]

            # Clean up resolved alerts older than retention period
            resolved_alerts_to_remove = []
            for alert_id, alert in self.active_alerts.items():
                if alert.resolved_at and alert.resolved_at < cutoff_time:
                    resolved_alerts_to_remove.append(alert_id)

            for alert_id in resolved_alerts_to_remove:
                del self.active_alerts[alert_id]

            logger.info(f"Cleaned up monitoring data older than {retention_days} days")

        except Exception as e:
            logger.error(f"Failed to cleanup old monitoring data: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        total_workflows = len(
            set(
                m.workflow_id
                for metrics in self.metric_history.values()
                for m in metrics
            )
        )

        total_alerts = len(self.active_alerts)
        critical_alerts = len(
            [
                a
                for a in self.active_alerts.values()
                if a.severity == AlertSeverity.CRITICAL
            ]
        )

        return {
            "total_workflows_monitored": total_workflows,
            "total_active_alerts": total_alerts,
            "critical_alerts": critical_alerts,
            "monitoring_rules_count": len(self.monitoring_rules),
            "system_status": "healthy" if critical_alerts == 0 else "degraded",
            "last_updated": datetime.now().isoformat(),
        }
