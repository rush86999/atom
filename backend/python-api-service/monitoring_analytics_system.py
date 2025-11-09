"""
Comprehensive Monitoring and Analytics System

This module provides enterprise-grade monitoring, analytics, and alerting capabilities
for the Atom Platform. It includes real-time metrics collection, performance monitoring,
usage analytics, and automated alerting for production environments.
"""

import asyncio
import json
import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics that can be collected"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertSeverity(Enum):
    """Alert severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Metric:
    """Base metric definition"""

    name: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    tags: Dict[str, str]
    unit: Optional[str] = None


@dataclass
class Alert:
    """Alert definition"""

    alert_id: str
    name: str
    description: str
    severity: AlertSeverity
    metric_name: str
    threshold: float
    current_value: float
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    is_active: bool = True


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""

    timestamp: datetime
    cpu_percent: float
    memory_usage_mb: float
    memory_percent: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_received: int
    active_connections: int
    request_count: int
    error_rate: float
    average_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float


@dataclass
class UsageAnalytics:
    """Usage analytics data"""

    timestamp: datetime
    active_users: int
    new_users: int
    total_workflows: int
    workflow_executions: int
    integration_calls: Dict[str, int]
    memory_usage_mb: int
    search_queries: int
    api_calls: int
    error_count: int


class MonitoringAnalyticsSystem:
    """
    Comprehensive monitoring and analytics system for the Atom Platform.
    Provides real-time metrics collection, performance monitoring, usage analytics,
    and automated alerting capabilities.
    """

    def __init__(self, retention_days: int = 30, alert_check_interval: int = 60):
        self.retention_days = retention_days
        self.alert_check_interval = alert_check_interval

        # Data storage
        self.metrics: Dict[str, List[Metric]] = defaultdict(list)
        self.alerts: Dict[str, Alert] = {}
        self.performance_history: deque = deque(maxlen=1000)
        self.usage_analytics: deque = deque(maxlen=1000)

        # Alert rules
        self.alert_rules: Dict[str, Dict[str, Any]] = {}

        # Monitoring state
        self.is_monitoring = False
        self.monitoring_thread = None

        # Initialize default alert rules
        self._initialize_default_alert_rules()

        logger.info("Monitoring and Analytics System initialized")

    def _initialize_default_alert_rules(self):
        """Initialize default alert rules for common scenarios"""
        self.alert_rules = {
            "high_cpu_usage": {
                "name": "High CPU Usage",
                "description": "CPU usage exceeds 80% for more than 5 minutes",
                "metric_name": "system.cpu.percent",
                "threshold": 80.0,
                "duration": 300,  # 5 minutes
                "severity": AlertSeverity.HIGH,
            },
            "high_memory_usage": {
                "name": "High Memory Usage",
                "description": "Memory usage exceeds 85% for more than 5 minutes",
                "metric_name": "system.memory.percent",
                "threshold": 85.0,
                "duration": 300,
                "severity": AlertSeverity.HIGH,
            },
            "high_disk_usage": {
                "name": "High Disk Usage",
                "description": "Disk usage exceeds 90%",
                "metric_name": "system.disk.usage_percent",
                "threshold": 90.0,
                "duration": 0,
                "severity": AlertSeverity.MEDIUM,
            },
            "high_error_rate": {
                "name": "High Error Rate",
                "description": "Error rate exceeds 5% for more than 10 minutes",
                "metric_name": "application.error_rate",
                "threshold": 5.0,
                "duration": 600,
                "severity": AlertSeverity.CRITICAL,
            },
            "slow_response_time": {
                "name": "Slow Response Time",
                "description": "Average response time exceeds 1000ms",
                "metric_name": "application.response_time.avg",
                "threshold": 1000.0,
                "duration": 300,
                "severity": AlertSeverity.MEDIUM,
            },
        }

    def start_monitoring(self):
        """Start the monitoring system"""
        if self.is_monitoring:
            logger.warning("Monitoring is already running")
            return

        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.monitoring_thread.start()
        logger.info("Monitoring system started")

    def stop_monitoring(self):
        """Stop the monitoring system"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
        logger.info("Monitoring system stopped")

    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                # Collect system metrics
                self._collect_system_metrics()

                # Collect application metrics
                self._collect_application_metrics()

                # Check alert rules
                self._check_alert_rules()

                # Clean up old data
                self._cleanup_old_data()

                # Wait for next cycle
                time.sleep(self.alert_check_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(30)  # Wait before retrying

    def _collect_system_metrics(self):
        """Collect system-level metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric(
                "system.cpu.percent",
                MetricType.GAUGE,
                cpu_percent,
                tags={"type": "system"},
                unit="percent",
            )

            # Memory metrics
            memory = psutil.virtual_memory()
            self.record_metric(
                "system.memory.usage_mb",
                MetricType.GAUGE,
                memory.used / (1024 * 1024),
                tags={"type": "system"},
                unit="mb",
            )
            self.record_metric(
                "system.memory.percent",
                MetricType.GAUGE,
                memory.percent,
                tags={"type": "system"},
                unit="percent",
            )

            # Disk metrics
            disk = psutil.disk_usage("/")
            self.record_metric(
                "system.disk.usage_percent",
                MetricType.GAUGE,
                (disk.used / disk.total) * 100,
                tags={"type": "system"},
                unit="percent",
            )

            # Network metrics
            net_io = psutil.net_io_counters()
            self.record_metric(
                "system.network.bytes_sent",
                MetricType.COUNTER,
                net_io.bytes_sent,
                tags={"type": "system"},
                unit="bytes",
            )
            self.record_metric(
                "system.network.bytes_received",
                MetricType.COUNTER,
                net_io.bytes_recv,
                tags={"type": "system"},
                unit="bytes",
            )

        except Exception as e:
            logger.error(f"Error collecting system metrics: {str(e)}")

    def _collect_application_metrics(self):
        """Collect application-level metrics"""
        try:
            # This would integrate with the actual application metrics
            # For now, we'll record some mock metrics

            # Record performance metrics
            performance_metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=psutil.cpu_percent(),
                memory_usage_mb=psutil.virtual_memory().used / (1024 * 1024),
                memory_percent=psutil.virtual_memory().percent,
                disk_usage_percent=(
                    psutil.disk_usage("/").used / psutil.disk_usage("/").total
                )
                * 100,
                network_bytes_sent=psutil.net_io_counters().bytes_sent,
                network_bytes_received=psutil.net_io_counters().bytes_recv,
                active_connections=0,  # Would come from actual application
                request_count=0,  # Would come from actual application
                error_rate=0.0,  # Would come from actual application
                average_response_time_ms=0.0,  # Would come from actual application
                p95_response_time_ms=0.0,  # Would come from actual application
                p99_response_time_ms=0.0,  # Would come from actual application
            )

            self.performance_history.append(performance_metrics)

        except Exception as e:
            logger.error(f"Error collecting application metrics: {str(e)}")

    def record_metric(
        self,
        name: str,
        metric_type: MetricType,
        value: float,
        tags: Dict[str, str] = None,
        unit: str = None,
    ):
        """Record a metric"""
        if tags is None:
            tags = {}

        metric = Metric(
            name=name,
            metric_type=metric_type,
            value=value,
            timestamp=datetime.now(),
            tags=tags,
            unit=unit,
        )

        self.metrics[name].append(metric)

        # Keep only recent metrics (based on retention policy)
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        self.metrics[name] = [
            m for m in self.metrics[name] if m.timestamp > cutoff_time
        ]

    def _check_alert_rules(self):
        """Check all alert rules and trigger alerts if needed"""
        for rule_id, rule in self.alert_rules.items():
            try:
                metric_name = rule["metric_name"]
                threshold = rule["threshold"]
                duration = rule["duration"]

                # Get recent metrics for this rule
                recent_metrics = self._get_recent_metrics(metric_name, duration)

                if not recent_metrics:
                    continue

                # Calculate average value over the duration
                values = [m.value for m in recent_metrics]
                avg_value = statistics.mean(values)

                # Check if threshold is exceeded
                if avg_value > threshold:
                    # Check if alert already exists
                    active_alert = self._get_active_alert(rule_id)

                    if not active_alert:
                        # Create new alert
                        self._create_alert(rule_id, rule, avg_value)
                    else:
                        # Update existing alert
                        active_alert.current_value = avg_value
                else:
                    # Resolve alert if it exists
                    self._resolve_alert(rule_id)

            except Exception as e:
                logger.error(f"Error checking alert rule {rule_id}: {str(e)}")

    def _get_recent_metrics(
        self, metric_name: str, duration_seconds: int
    ) -> List[Metric]:
        """Get metrics from the last N seconds"""
        if metric_name not in self.metrics:
            return []

        cutoff_time = datetime.now() - timedelta(seconds=duration_seconds)
        return [m for m in self.metrics[metric_name] if m.timestamp > cutoff_time]

    def _get_active_alert(self, rule_id: str) -> Optional[Alert]:
        """Get active alert for a rule"""
        for alert in self.alerts.values():
            if alert.name == self.alert_rules[rule_id]["name"] and alert.is_active:
                return alert
        return None

    def _create_alert(self, rule_id: str, rule: Dict[str, Any], current_value: float):
        """Create a new alert"""
        alert_id = f"alert_{rule_id}_{int(time.time())}"

        alert = Alert(
            alert_id=alert_id,
            name=rule["name"],
            description=rule["description"],
            severity=rule["severity"],
            metric_name=rule["metric_name"],
            threshold=rule["threshold"],
            current_value=current_value,
            triggered_at=datetime.now(),
            is_active=True,
        )

        self.alerts[alert_id] = alert

        # Log the alert
        logger.warning(
            f"ALERT TRIGGERED: {alert.name} - {alert.description} "
            f"(Current: {current_value:.2f}, Threshold: {alert.threshold:.2f})"
        )

        # Here you would integrate with notification systems (email, Slack, etc.)
        self._send_alert_notification(alert)

    def _resolve_alert(self, rule_id: str):
        """Resolve an alert"""
        active_alert = self._get_active_alert(rule_id)
        if active_alert:
            active_alert.is_active = False
            active_alert.resolved_at = datetime.now()

            logger.info(f"ALERT RESOLVED: {active_alert.name}")

    def _send_alert_notification(self, alert: Alert):
        """Send alert notification (to be implemented with actual notification system)"""
        # This would integrate with email, Slack, PagerDuty, etc.
        # For now, just log the notification
        logger.info(f"Would send notification for alert: {alert.name}")

    def _cleanup_old_data(self):
        """Clean up old metrics and alerts"""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)

        # Clean up old metrics
        for metric_name in list(self.metrics.keys()):
            self.metrics[metric_name] = [
                m for m in self.metrics[metric_name] if m.timestamp > cutoff_time
            ]
            if not self.metrics[metric_name]:
                del self.metrics[metric_name]

        # Clean up resolved alerts older than retention period
        alerts_to_remove = []
        for alert_id, alert in self.alerts.items():
            if (
                not alert.is_active
                and alert.resolved_at
                and alert.resolved_at < cutoff_time
            ):
                alerts_to_remove.append(alert_id)

        for alert_id in alerts_to_remove:
            del self.alerts[alert_id]

    def record_usage_analytics(self, analytics_data: UsageAnalytics):
        """Record usage analytics data"""
        self.usage_analytics.append(analytics_data)

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        try:
            # Get recent performance metrics
            if self.performance_history:
                latest_performance = self.performance_history[-1]
            else:
                latest_performance = None

            # Count active alerts by severity
            active_alerts = {severity.value: 0 for severity in AlertSeverity}
            for alert in self.alerts.values():
                if alert.is_active:
                    active_alerts[alert.severity.value] += 1

            return {
                "timestamp": datetime.now().isoformat(),
                "status": "healthy" if sum(active_alerts.values()) == 0 else "degraded",
                "active_alerts": active_alerts,
                "system_metrics": {
                    "cpu_percent": latest_performance.cpu_percent
                    if latest_performance
                    else 0,
                    "memory_percent": latest_performance.memory_percent
                    if latest_performance
                    else 0,
                    "disk_usage_percent": latest_performance.disk_usage_percent
                    if latest_performance
                    else 0,
                }
                if latest_performance
                else {},
                "total_metrics_collected": sum(
                    len(metrics) for metrics in self.metrics.values()
                ),
                "performance_history_count": len(self.performance_history),
                "usage_analytics_count": len(self.usage_analytics),
            }

        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "unknown",
                "error": str(e),
            }

    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance report for the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_performance = [
            p for p in self.performance_history if p.timestamp > cutoff_time
        ]

        if not recent_performance:
            return {"error": "No performance data available for the specified period"}

        # Calculate statistics
        cpu_values = [p.cpu_percent for p in recent_performance]
        memory_values = [p.memory_percent for p in recent_performance]
        response_times = [
            p.average_response_time_ms
            for p in recent_performance
            if p.average_response_time_ms > 0
        ]

        return {
            "period": f"last_{hours}_hours",
            "from": cutoff_time.isoformat(),
            "to": datetime.now().isoformat(),
            "summary": {
                "cpu_usage": {
                    "average": statistics.mean(cpu_values) if cpu_values else 0,
                    "max": max(cpu_values) if cpu_values else 0,
                    "min": min(cpu_values) if cpu_values else 0,
                    "p95": statistics.quantiles(cpu_values, n=20)[18]
                    if len(cpu_values) >= 20
                    else 0,
                },
                "memory_usage": {
                    "average": statistics.mean(memory_values) if memory_values else 0,
                    "max": max(memory_values) if memory_values else 0,
                    "min": min(memory_values) if memory_values else 0,
                },
                "response_times": {
                    "average": statistics.mean(response_times) if response_times else 0,
                    "p95": statistics.quantiles(response_times, n=20)[18]
                    if len(response_times) >= 20
                    else 0,
                    "p99": statistics.quantiles(response_times, n=100)[98]
                    if len(response_times) >= 100
                    else 0,
                    "max": max(response_times) if response_times else 0,
                    "min": min(response_times) if response_times else 0,
                },
            },
        }
