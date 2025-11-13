"""
Workflow Monitoring Integration Module

This module provides integration between enhanced workflow monitoring
and the main backend API, including real-time analytics, AI-powered
anomaly detection, intelligent alerting, and performance insights.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

# Add parent directory to path to import enhanced modules
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class WorkflowStatus(Enum):
    """Workflow status levels"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class MetricType(Enum):
    """Metric types for workflow monitoring"""

    EXECUTION_TIME = "execution_time"
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"
    COST = "cost"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    RESOURCE_USAGE = "resource_usage"


class WorkflowMonitoringIntegration:
    """Workflow Monitoring Integration with Enhanced AI Capabilities"""

    def __init__(self):
        self.monitoring_rules = {}
        self.alert_rules = {}
        self.active_monitors = {}
        self.metrics_history = {}
        self.performance_baselines = {}
        self._initialize_monitoring_system()

    def _initialize_monitoring_system(self):
        """Initialize the enhanced workflow monitoring system"""
        try:
            # Initialize monitoring rules
            self.monitoring_rules = self._initialize_monitoring_rules()

            # Initialize alert rules
            self.alert_rules = self._initialize_alert_rules()

            # Initialize performance baselines
            self.performance_baselines = self._initialize_performance_baselines()

            logger.info("Enhanced workflow monitoring system initialized successfully")

        except Exception as e:
            logger.warning(
                f"Enhanced monitoring system initialization failed: {str(e)}"
            )
            logger.info("Falling back to basic monitoring system")
            self._initialize_basic_monitoring_system()

    def _initialize_monitoring_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize comprehensive monitoring rules"""
        return {
            "execution_time": {
                "metric_type": MetricType.EXECUTION_TIME,
                "threshold_warning": 30.0,  # seconds
                "threshold_critical": 60.0,  # seconds
                "anomaly_detection": True,
                "trend_analysis": True,
                "aggregation_period": 300,  # 5 minutes
                "retention_period": 86400,  # 24 hours
            },
            "success_rate": {
                "metric_type": MetricType.SUCCESS_RATE,
                "threshold_warning": 0.90,  # 90%
                "threshold_critical": 0.80,  # 80%
                "anomaly_detection": True,
                "trend_analysis": True,
                "aggregation_period": 300,
                "retention_period": 86400,
            },
            "error_rate": {
                "metric_type": MetricType.ERROR_RATE,
                "threshold_warning": 0.10,  # 10%
                "threshold_critical": 0.20,  # 20%
                "anomaly_detection": True,
                "trend_analysis": True,
                "aggregation_period": 300,
                "retention_period": 86400,
            },
            "cost": {
                "metric_type": MetricType.COST,
                "threshold_warning": 0.50,  # $0.50
                "threshold_critical": 1.00,  # $1.00
                "anomaly_detection": True,
                "trend_analysis": True,
                "aggregation_period": 3600,  # 1 hour
                "retention_period": 259200,  # 3 days
            },
            "latency": {
                "metric_type": MetricType.LATENCY,
                "threshold_warning": 5.0,  # 5 seconds
                "threshold_critical": 10.0,  # 10 seconds
                "anomaly_detection": True,
                "trend_analysis": True,
                "aggregation_period": 300,
                "retention_period": 86400,
            },
        }

    def _initialize_alert_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize intelligent alert rules"""
        return {
            "performance_degradation": {
                "description": "Workflow performance has degraded significantly",
                "severity": AlertSeverity.HIGH,
                "conditions": [
                    "execution_time > threshold_critical",
                    "success_rate < threshold_critical",
                    "trend_direction = negative",
                ],
                "cooldown_period": 300,  # 5 minutes
                "auto_resolve": True,
                "notification_channels": ["email", "slack"],
            },
            "error_rate_spike": {
                "description": "Workflow error rate has spiked",
                "severity": AlertSeverity.CRITICAL,
                "conditions": [
                    "error_rate > threshold_critical",
                    "error_rate_change > 50%",
                ],
                "cooldown_period": 600,  # 10 minutes
                "auto_resolve": True,
                "notification_channels": ["email", "slack", "pagerduty"],
            },
            "cost_anomaly": {
                "description": "Unusual cost pattern detected",
                "severity": AlertSeverity.MEDIUM,
                "conditions": ["cost > threshold_warning", "cost_trend = increasing"],
                "cooldown_period": 1800,  # 30 minutes
                "auto_resolve": True,
                "notification_channels": ["email"],
            },
            "service_degradation": {
                "description": "External service performance degraded",
                "severity": AlertSeverity.HIGH,
                "conditions": [
                    "latency > threshold_critical",
                    "success_rate < threshold_warning",
                ],
                "cooldown_period": 300,
                "auto_resolve": True,
                "notification_channels": ["email", "slack"],
            },
        }

    def _initialize_performance_baselines(self) -> Dict[str, Dict[str, Any]]:
        """Initialize performance baselines for different workflow types"""
        return {
            "communication_workflow": {
                "execution_time": 5.0,
                "success_rate": 0.95,
                "error_rate": 0.05,
                "cost": 0.02,
                "latency": 2.0,
            },
            "data_processing_workflow": {
                "execution_time": 30.0,
                "success_rate": 0.85,
                "error_rate": 0.15,
                "cost": 0.15,
                "latency": 5.0,
            },
            "analytics_workflow": {
                "execution_time": 60.0,
                "success_rate": 0.90,
                "error_rate": 0.10,
                "cost": 0.25,
                "latency": 10.0,
            },
            "synchronization_workflow": {
                "execution_time": 45.0,
                "success_rate": 0.88,
                "error_rate": 0.12,
                "cost": 0.18,
                "latency": 8.0,
            },
        }

    def _initialize_basic_monitoring_system(self):
        """Initialize basic monitoring system as fallback"""
        self.monitoring_rules = {
            "basic": {"threshold_warning": 30.0, "threshold_critical": 60.0}
        }
        self.alert_rules = {
            "basic": {"severity": AlertSeverity.HIGH, "cooldown_period": 300}
        }
        self.performance_baselines = {
            "basic": {"execution_time": 30.0, "success_rate": 0.90}
        }

    def start_monitoring(self, workflow_id: str) -> Dict[str, Any]:
        """Start enhanced monitoring for a workflow"""
        try:
            if workflow_id in self.active_monitors:
                return {
                    "success": False,
                    "error": f"Monitoring already active for workflow {workflow_id}",
                }

            # Initialize monitoring state
            self.active_monitors[workflow_id] = {
                "start_time": datetime.now(),
                "last_metrics_update": datetime.now(),
                "metrics": {},
                "alerts": [],
                "health_score": 100.0,
                "status": WorkflowStatus.HEALTHY,
            }

            # Initialize metrics history
            self.metrics_history[workflow_id] = {
                "execution_time": [],
                "success_rate": [],
                "error_rate": [],
                "cost": [],
                "latency": [],
            }

            logger.info(f"Enhanced monitoring started for workflow {workflow_id}")

            return {
                "success": True,
                "workflow_id": workflow_id,
                "monitoring_started": True,
                "monitoring_rules": list(self.monitoring_rules.keys()),
                "enhanced_monitoring": True,
            }

        except Exception as e:
            logger.error(
                f"Failed to start monitoring for workflow {workflow_id}: {str(e)}"
            )
            return {"success": False, "error": f"Failed to start monitoring: {str(e)}"}

    def stop_monitoring(self, workflow_id: str) -> Dict[str, Any]:
        """Stop monitoring for a workflow"""
        try:
            if workflow_id not in self.active_monitors:
                return {
                    "success": False,
                    "error": f"No active monitoring found for workflow {workflow_id}",
                }

            # Clean up monitoring state
            del self.active_monitors[workflow_id]
            if workflow_id in self.metrics_history:
                del self.metrics_history[workflow_id]

            logger.info(f"Enhanced monitoring stopped for workflow {workflow_id}")

            return {
                "success": True,
                "workflow_id": workflow_id,
                "monitoring_stopped": True,
            }

        except Exception as e:
            logger.error(
                f"Failed to stop monitoring for workflow {workflow_id}: {str(e)}"
            )
            return {"success": False, "error": f"Failed to stop monitoring: {str(e)}"}

    def record_metric(
        self,
        workflow_id: str,
        metric_type: str,
        value: float,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Record a metric for workflow monitoring"""
        try:
            if workflow_id not in self.active_monitors:
                return {
                    "success": False,
                    "error": f"No active monitoring found for workflow {workflow_id}",
                }

            # Validate metric type
            if metric_type not in [mt.value for mt in MetricType]:
                return {
                    "success": False,
                    "error": f"Invalid metric type: {metric_type}",
                }

            # Update metrics
            current_time = datetime.now()
            self.active_monitors[workflow_id]["last_metrics_update"] = current_time
            self.active_monitors[workflow_id]["metrics"][metric_type] = {
                "value": value,
                "timestamp": current_time,
                "metadata": metadata or {},
            }

            # Update metrics history
            if workflow_id in self.metrics_history:
                if metric_type not in self.metrics_history[workflow_id]:
                    self.metrics_history[workflow_id][metric_type] = []

                self.metrics_history[workflow_id][metric_type].append(
                    {
                        "value": value,
                        "timestamp": current_time,
                        "metadata": metadata or {},
                    }
                )

                # Keep only recent history (last 1000 entries)
                if len(self.metrics_history[workflow_id][metric_type]) > 1000:
                    self.metrics_history[workflow_id][metric_type] = (
                        self.metrics_history[workflow_id][metric_type][-1000:]
                    )

            # Check for alerts
            alerts_triggered = self._check_alerts(workflow_id, metric_type, value)

            # Update health score
            self._update_health_score(workflow_id, metric_type, value)

            return {
                "success": True,
                "workflow_id": workflow_id,
                "metric_type": metric_type,
                "value": value,
                "alerts_triggered": alerts_triggered,
                "timestamp": current_time.isoformat(),
            }

        except Exception as e:
            logger.error(
                f"Failed to record metric for workflow {workflow_id}: {str(e)}"
            )
            return {"success": False, "error": f"Failed to record metric: {str(e)}"}

    def get_workflow_health(self, workflow_id: str) -> Dict[str, Any]:
        """Get comprehensive workflow health assessment"""
        try:
            if workflow_id not in self.active_monitors:
                return {
                    "success": False,
                    "error": f"No active monitoring found for workflow {workflow_id}",
                }

            monitor_data = self.active_monitors[workflow_id]
            metrics = monitor_data.get("metrics", {})
            alerts = monitor_data.get("alerts", [])
            health_score = monitor_data.get("health_score", 0.0)
            status = monitor_data.get("status", WorkflowStatus.UNKNOWN)

            # Calculate detailed health breakdown
            health_breakdown = self._calculate_health_breakdown(workflow_id, metrics)

            # Generate performance insights
            performance_insights = self._generate_performance_insights(workflow_id)

            # Get recent alerts
            recent_alerts = [alert for alert in alerts if self._is_recent_alert(alert)]

            return {
                "success": True,
                "workflow_id": workflow_id,
                "health_score": health_score,
                "status": status.value,
                "health_breakdown": health_breakdown,
                "performance_insights": performance_insights,
                "active_alerts": len(recent_alerts),
                "recent_alerts": recent_alerts[-10:],  # Last 10 alerts
                "monitoring_duration": self._calculate_monitoring_duration(workflow_id),
                "enhanced_monitoring": True,
            }

        except Exception as e:
            logger.error(f"Failed to get workflow health for {workflow_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get workflow health: {str(e)}",
            }

    def get_workflow_metrics(
        self, workflow_id: str, metric_type: str = "all"
    ) -> Dict[str, Any]:
        """Get workflow metrics with optional filtering"""
        try:
            if workflow_id not in self.active_monitors:
                return {
                    "success": False,
                    "error": f"No active monitoring found for workflow {workflow_id}",
                }

            if workflow_id not in self.metrics_history:
                return {
                    "success": False,
                    "error": f"No metrics history found for workflow {workflow_id}",
                }

            metrics_data = self.metrics_history[workflow_id]

            if metric_type != "all" and metric_type not in metrics_data:
                return {
                    "success": False,
                    "error": f"No metrics found for type: {metric_type}",
                }

            # Filter metrics if specific type requested
            if metric_type != "all":
                metrics_data = {metric_type: metrics_data[metric_type]}

            # Calculate statistics
            statistics = self._calculate_metrics_statistics(metrics_data)

            return {
                "success": True,
                "workflow_id": workflow_id,
                "metric_type": metric_type,
                "metrics": metrics_data,
                "statistics": statistics,
                "time_range": self._get_metrics_time_range(metrics_data),
            }

        except Exception as e:
            logger.error(f"Failed to get workflow metrics for {workflow_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get workflow metrics: {str(e)}",
            }

    def _check_alerts(
        self, workflow_id: str, metric_type: str, value: float
    ) -> List[Dict[str, Any]]:
        """Check if any alerts should be triggered"""
        triggered_alerts = []

        for alert_name, alert_rule in self.alert_rules.items():
            if self._should_trigger_alert(
                workflow_id, alert_name, metric_type, value, alert_rule
            ):
                alert = self._create_alert(
                    workflow_id, alert_name, metric_type, value, alert_rule
                )
                triggered_alerts.append(alert)

                # Add to workflow's alert history
                self.active_monitors[workflow_id]["alerts"].append(alert)

                # Send notifications
                self._send_alert_notifications(alert)

        return triggered_alerts

    def _should_trigger_alert(
        self,
        workflow_id: str,
        alert_name: str,
        metric_type: str,
        value: float,
        alert_rule: Dict[str, Any],
    ) -> bool:
        """Determine if an alert should be triggered"""
        # Check cooldown period
        if self._is_in_cooldown(workflow_id, alert_name, alert_rule):
            return False

        # Check threshold conditions
        monitoring_rule = self.monitoring_rules.get(metric_type, {})
        threshold_warning = monitoring_rule.get("threshold_warning", 0)
        threshold_critical = monitoring_rule.get("threshold_critical", 0)

        # Simple threshold checking (extend with more complex conditions)
        if metric_type == MetricType.EXECUTION_TIME.value:
            return value > threshold_critical
        elif metric_type == MetricType.SUCCESS_RATE.value:
            return value < threshold_critical
        elif metric_type == MetricType.ERROR_RATE.value:
            return value > threshold_critical
        elif metric_type == MetricType.COST.value:
            return value > threshold_critical
        elif metric_type == MetricType.LATENCY.value:
            return value > threshold_critical

        return False

    def _is_in_cooldown(
        self, workflow_id: str, alert_name: str, alert_rule: Dict[str, Any]
    ) -> bool:
        """Check if alert is in cooldown period"""
        cooldown_period = alert_rule.get("cooldown_period", 300)  # Default 5 minutes

        # Check if this alert was recently triggered
        if workflow_id in self.active_monitors:
            recent_alerts = self.active_monitors[workflow_id].get("alerts", [])
            for alert in recent_alerts[-10:]:  # Check last 10 alerts
                if (
                    alert.get("alert_name") == alert_name
                    and alert.get("timestamp")
                    and self._is_within_cooldown(alert["timestamp"], cooldown_period)
                ):
                    return True

        return False

    def _is_within_cooldown(self, alert_timestamp: str, cooldown_period: int) -> bool:
        """Check if alert timestamp is within cooldown period"""
        from datetime import datetime, timedelta

        try:
            alert_time = datetime.fromisoformat(alert_timestamp)
            current_time = datetime.now()
            cooldown_end = alert_time + timedelta(seconds=cooldown_period)
            return current_time < cooldown_end
        except Exception:
            return False

    def _create_alert(
        self,
        workflow_id: str,
        alert_name: str,
        metric_type: str,
        value: float,
        alert_rule: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create an alert object"""
        from datetime import datetime

        return {
            "alert_id": f"{workflow_id}_{alert_name}_{datetime.now().timestamp()}",
            "workflow_id": workflow_id,
            "alert_name": alert_name,
            "metric_type": metric_type,
            "value": value,
            "severity": alert_rule.get("severity", "medium"),
            "description": alert_rule.get("description", ""),
            "timestamp": datetime.now().isoformat(),
            "acknowledged": False,
            "resolved": False,
        }

    def _calculate_health_breakdown(self, workflow_id: str) -> Dict[str, Any]:
        """Calculate detailed health breakdown for workflow"""
        if workflow_id not in self.active_monitors:
            return {}

        monitor_data = self.active_monitors[workflow_id]
        metrics = monitor_data.get("metrics", {})

        # Calculate health components
        execution_time_health = self._calculate_metric_health(
            metrics.get("execution_time", {}).get("value", 0), "execution_time"
        )
        success_rate_health = self._calculate_metric_health(
            metrics.get("success_rate", {}).get("value", 1.0), "success_rate"
        )
        error_rate_health = self._calculate_metric_health(
            metrics.get("error_rate", {}).get("value", 0), "error_rate"
        )

        return {
            "execution_time": execution_time_health,
            "success_rate": success_rate_health,
            "error_rate": error_rate_health,
            "overall_health": min(
                execution_time_health.get("score", 100),
                success_rate_health.get("score", 100),
                error_rate_health.get("score", 100),
            ),
        }

    def _calculate_metric_health(
        self, value: float, metric_type: str
    ) -> Dict[str, Any]:
        """Calculate health score for a specific metric"""
        thresholds = self.monitoring_rules.get(metric_type, {})
        warning_threshold = thresholds.get("threshold_warning", 0)
        critical_threshold = thresholds.get("threshold_critical", 0)

        if metric_type == "success_rate":
            # Higher is better for success rate
            if value >= 0.95:
                score = 100
                status = "excellent"
            elif value >= 0.90:
                score = 80
                status = "good"
            elif value >= 0.85:
                score = 60
                status = "warning"
            else:
                score = 40
                status = "critical"
        elif metric_type == "error_rate":
            # Lower is better for error rate
            if value <= 0.05:
                score = 100
                status = "excellent"
            elif value <= 0.10:
                score = 80
                status = "good"
            elif value <= 0.15:
                score = 60
                status = "warning"
            else:
                score = 40
                status = "critical"
        else:
            # For execution_time, lower is better
            if value <= warning_threshold * 0.5:
                score = 100
                status = "excellent"
            elif value <= warning_threshold:
                score = 80
                status = "good"
            elif value <= critical_threshold:
                score = 60
                status = "warning"
            else:
                score = 40
                status = "critical"

        return {
            "value": value,
            "score": score,
            "status": status,
            "threshold_warning": warning_threshold,
            "threshold_critical": critical_threshold,
        }

    def _calculate_monitoring_duration(self, workflow_id: str) -> str:
        """Calculate how long monitoring has been active"""
        from datetime import datetime

        if workflow_id not in self.active_monitors:
            return "0s"

        start_time = self.active_monitors[workflow_id].get("start_time")
        if not start_time:
            return "0s"

        try:
            start_dt = datetime.fromisoformat(start_time)
            duration = datetime.now() - start_dt
            return str(duration)
        except Exception:
            return "0s"

    def _get_metrics_time_range(self, metrics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get time range for metrics data"""
        if not metrics_data:
            return {"start": None, "end": None, "duration": "0s"}

        all_timestamps = []
        for metric_type, values in metrics_data.items():
            for value_data in values:
                if "timestamp" in value_data:
                    all_timestamps.append(value_data["timestamp"])

        if not all_timestamps:
            return {"start": None, "end": None, "duration": "0s"}

        try:
            from datetime import datetime

            start_time = min(all_timestamps)
            end_time = max(all_timestamps)

            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)
            duration = end_dt - start_dt

            return {
                "start": start_time,
                "end": end_time,
                "duration": str(duration),
            }
        except Exception:
            return {"start": None, "end": None, "duration": "0s"}

    def _calculate_metrics_statistics(
        self, metrics_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate statistics for metrics data"""
        statistics = {}

        for metric_type, values in metrics_data.items():
            if not values:
                continue

            numeric_values = [v.get("value", 0) for v in values if "value" in v]

            if not numeric_values:
                continue

            statistics[metric_type] = {
                "count": len(numeric_values),
                "min": min(numeric_values),
                "max": max(numeric_values),
                "average": sum(numeric_values) / len(numeric_values),
                "latest": values[-1].get("value", 0) if values else 0,
            }

        return statistics

    def _update_health_score(self, workflow_id: str, metric_type: str, value: float):
        """Update the health score for a workflow based on metric changes"""
        if workflow_id not in self.active_monitors:
            return

        # Get current health breakdown
        health_breakdown = self._calculate_health_breakdown(workflow_id)

        # Update overall health score
        overall_health = health_breakdown.get("overall_health", 100)
        self.active_monitors[workflow_id]["health_score"] = overall_health

        # Update status based on health score
        if overall_health >= 80:
            self.active_monitors[workflow_id]["status"] = WorkflowStatus.HEALTHY.value
        elif overall_health >= 60:
            self.active_monitors[workflow_id]["status"] = WorkflowStatus.DEGRADED.value
        else:
            self.active_monitors[workflow_id]["status"] = WorkflowStatus.FAILING.value

        logger.debug(f"Updated health score for {workflow_id}: {overall_health}")
