#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced Workflow Monitoring and Troubleshooting System
Real-time analytics, AI-powered diagnostics, and automated issue resolution
"""

import asyncio
import json
import logging
import re
import statistics
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
    """Workflow execution status"""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    WAITING = "waiting"


class MetricType(Enum):
    """Types of workflow metrics"""

    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    RESOURCE = "resource"
    BUSINESS = "business"
    CUSTOM = "custom"


@dataclass
class WorkflowMetric:
    """Enhanced workflow metric with intelligent tracking"""

    metric_id: str
    workflow_id: str
    metric_type: MetricType
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowAlert:
    """Enhanced workflow alert with intelligent routing"""

    alert_id: str
    workflow_id: str
    severity: AlertSeverity
    title: str
    description: str
    trigger_conditions: Dict[str, Any]
    current_values: Dict[str, Any]
    created_at: datetime
    acknowledged: bool = False
    resolved: bool = False
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None


@dataclass
class PerformanceInsight:
    """AI-powered performance insights"""

    insight_id: str
    workflow_id: str
    insight_type: str
    description: str
    confidence: float
    impact_score: float
    recommendations: List[str]
    evidence: List[str]
    generated_at: datetime


@dataclass
class TroubleshootingSession:
    """Enhanced troubleshooting session"""

    session_id: str
    workflow_id: str
    issues_detected: List[str]
    steps_completed: List[str]
    current_step: str
    recommendations: List[str]
    resolution_status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    session_metrics: Dict[str, Any] = field(default_factory=dict)


class EnhancedWorkflowMonitor:
    """
    AI-Powered Workflow Monitoring and Troubleshooting System
    Provides real-time analytics, intelligent alerts, and automated issue resolution
    """

    def __init__(self, monitoring_interval: int = 30):
        self.monitoring_interval = monitoring_interval
        self.workflow_metrics: Dict[str, List[WorkflowMetric]] = {}
        self.active_alerts: Dict[str, WorkflowAlert] = {}
        self.performance_insights: Dict[str, List[PerformanceInsight]] = {}
        self.troubleshooting_sessions: Dict[str, TroubleshootingSession] = {}
        self.monitoring_rules = self._initialize_monitoring_rules()
        self.alert_rules = self._initialize_alert_rules()
        self.is_monitoring = False
        self.monitoring_thread: Optional[threading.Thread] = None

        # Performance tracking
        self.performance_baselines: Dict[str, Dict[str, float]] = {}
        self.anomaly_detector = AnomalyDetectionEngine()
        self.insight_generator = InsightGenerationEngine()
        self.auto_resolver = AutoResolutionEngine()

    def _initialize_monitoring_rules(self) -> Dict[str, Any]:
        """Initialize intelligent monitoring rules"""
        return {
            "performance_degradation": {
                "description": "Detect performance degradation in workflows",
                "metrics": ["execution_time", "response_time"],
                "threshold": 2.0,  # 2x baseline
                "severity": AlertSeverity.HIGH,
                "cooldown": 300,  # 5 minutes
            },
            "error_rate_increase": {
                "description": "Detect increasing error rates",
                "metrics": ["error_rate", "failure_rate"],
                "threshold": 0.1,  # 10% error rate
                "severity": AlertSeverity.CRITICAL,
                "cooldown": 600,  # 10 minutes
            },
            "resource_exhaustion": {
                "description": "Detect resource exhaustion",
                "metrics": ["memory_usage", "cpu_usage"],
                "threshold": 0.8,  # 80% usage
                "severity": AlertSeverity.HIGH,
                "cooldown": 300,
            },
            "throughput_decrease": {
                "description": "Detect decreased throughput",
                "metrics": ["throughput", "completion_rate"],
                "threshold": 0.5,  # 50% decrease
                "severity": AlertSeverity.MEDIUM,
                "cooldown": 600,
            },
            "data_quality_issues": {
                "description": "Detect data quality issues",
                "metrics": ["data_validation_errors", "missing_data"],
                "threshold": 0.05,  # 5% error rate
                "severity": AlertSeverity.MEDIUM,
                "cooldown": 900,
            },
        }

    def _initialize_alert_rules(self) -> Dict[str, Any]:
        """Initialize intelligent alert routing rules"""
        return {
            "critical_alerts": {
                "severities": [AlertSeverity.CRITICAL],
                "channels": ["pagerduty", "slack_critical", "email"],
                "escalation_time": 300,  # 5 minutes
                "auto_acknowledge": False,
            },
            "high_alerts": {
                "severities": [AlertSeverity.HIGH],
                "channels": ["slack_high", "email"],
                "escalation_time": 900,  # 15 minutes
                "auto_acknowledge": False,
            },
            "medium_alerts": {
                "severities": [AlertSeverity.MEDIUM],
                "channels": ["slack_medium"],
                "escalation_time": 1800,  # 30 minutes
                "auto_acknowledge": True,
            },
            "low_alerts": {
                "severities": [AlertSeverity.LOW, AlertSeverity.INFO],
                "channels": ["slack_low"],
                "escalation_time": 3600,  # 1 hour
                "auto_acknowledge": True,
            },
        }

    def start_monitoring(self):
        """Start the enhanced monitoring system"""
        if self.is_monitoring:
            logger.warning("Monitoring is already running")
            return

        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.monitoring_thread.start()
        logger.info("Enhanced workflow monitoring started")

    def stop_monitoring(self):
        """Stop the monitoring system"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
        logger.info("Enhanced workflow monitoring stopped")

    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                self._collect_metrics()
                self._analyze_metrics()
                self._check_alerts()
                self._generate_insights()
                self._auto_resolve_issues()

                time.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                time.sleep(5)  # Brief pause on error

    def record_metric(self, metric: WorkflowMetric):
        """Record a workflow metric with enhanced tracking"""
        workflow_id = metric.workflow_id

        if workflow_id not in self.workflow_metrics:
            self.workflow_metrics[workflow_id] = []

        self.workflow_metrics[workflow_id].append(metric)

        # Keep only last 1000 metrics per workflow to prevent memory issues
        if len(self.workflow_metrics[workflow_id]) > 1000:
            self.workflow_metrics[workflow_id] = self.workflow_metrics[workflow_id][
                -1000:
            ]

        logger.debug(
            f"Recorded metric for workflow {workflow_id}: {metric.name}={metric.value}"
        )

    def _collect_metrics(self):
        """Collect metrics from workflow executions"""
        # This would integrate with actual workflow execution data
        # For now, we'll simulate metric collection
        pass

    def _analyze_metrics(self):
        """Analyze collected metrics for anomalies and trends"""
        for workflow_id, metrics in self.workflow_metrics.items():
            if len(metrics) < 10:  # Need sufficient data for analysis
                continue

            # Group metrics by type for analysis
            metric_groups = self._group_metrics_by_type(metrics)

            for metric_type, metric_list in metric_groups.items():
                # Update performance baselines
                self._update_performance_baseline(workflow_id, metric_type, metric_list)

                # Detect anomalies
                anomalies = self.anomaly_detector.detect_anomalies(metric_list)
                for anomaly in anomalies:
                    self._handle_anomaly(workflow_id, metric_type, anomaly)

    def _group_metrics_by_type(
        self, metrics: List[WorkflowMetric]
    ) -> Dict[str, List[WorkflowMetric]]:
        """Group metrics by their type for analysis"""
        groups = defaultdict(list)
        for metric in metrics:
            groups[metric.metric_type.value].append(metric)
        return dict(groups)

    def _update_performance_baseline(
        self, workflow_id: str, metric_type: str, metrics: List[WorkflowMetric]
    ):
        """Update performance baselines for intelligent thresholding"""
        if workflow_id not in self.performance_baselines:
            self.performance_baselines[workflow_id] = {}

        values = [metric.value for metric in metrics[-50:]]  # Use last 50 data points
        if values:
            baseline_value = statistics.median(values)
            self.performance_baselines[workflow_id][metric_type] = baseline_value

    def _handle_anomaly(
        self, workflow_id: str, metric_type: str, anomaly: Dict[str, Any]
    ):
        """Handle detected anomalies and create alerts"""
        alert_rule = self.monitoring_rules.get(metric_type)
        if not alert_rule:
            return

        # Check if similar alert already exists
        existing_alert = self._find_similar_alert(workflow_id, metric_type)
        if existing_alert:
            # Update existing alert
            self._update_existing_alert(existing_alert, anomaly)
        else:
            # Create new alert
            self._create_new_alert(workflow_id, metric_type, anomaly, alert_rule)

    def _find_similar_alert(
        self, workflow_id: str, metric_type: str
    ) -> Optional[WorkflowAlert]:
        """Find similar active alerts to prevent duplicates"""
        for alert in self.active_alerts.values():
            if (
                alert.workflow_id == workflow_id
                and metric_type in alert.trigger_conditions.get("metric_types", [])
                and not alert.resolved
            ):
                return alert
        return None

    def _update_existing_alert(self, alert: WorkflowAlert, anomaly: Dict[str, Any]):
        """Update existing alert with new anomaly data"""
        alert.current_values.update(anomaly.get("current_values", {}))
        alert.trigger_conditions["anomaly_count"] = (
            alert.trigger_conditions.get("anomaly_count", 0) + 1
        )

        # Escalate severity if multiple anomalies detected
        if alert.trigger_conditions.get("anomaly_count", 0) > 3:
            alert.severity = AlertSeverity.CRITICAL

    def _create_new_alert(
        self,
        workflow_id: str,
        metric_type: str,
        anomaly: Dict[str, Any],
        alert_rule: Dict[str, Any],
    ):
        """Create a new workflow alert"""
        alert_id = str(uuid.uuid4())

        alert = WorkflowAlert(
            alert_id=alert_id,
            workflow_id=workflow_id,
            severity=alert_rule["severity"],
            title=f"{metric_type.replace('_', ' ').title()} Alert - {workflow_id}",
            description=f"Detected {metric_type} anomaly in workflow {workflow_id}",
            trigger_conditions={
                "metric_type": metric_type,
                "threshold": alert_rule["threshold"],
                "anomaly_details": anomaly,
                "anomaly_count": 1,
            },
            current_values=anomaly.get("current_values", {}),
            created_at=datetime.now(),
        )

        self.active_alerts[alert_id] = alert
        self._route_alert(alert)
        logger.warning(f"Created alert: {alert.title}")

    def _route_alert(self, alert: WorkflowAlert):
        """Route alert to appropriate channels based on severity"""
        for rule_name, rule_config in self.alert_rules.items():
            if alert.severity in rule_config["severities"]:
                channels = rule_config["channels"]
                self._send_alert_to_channels(alert, channels)
                break

    def _send_alert_to_channels(self, alert: WorkflowAlert, channels: List[str]):
        """Send alert to specified channels"""
        # This would integrate with actual notification systems
        # For now, we'll log the alert routing
        logger.info(f"Routing alert {alert.alert_id} to channels: {channels}")

    def _check_alerts(self):
        """Check and process active alerts"""
        current_time = datetime.now()
        alerts_to_remove = []

        for alert_id, alert in self.active_alerts.items():
            # Check for alert escalation
            self._check_alert_escalation(alert, current_time)

            # Check for auto-resolution
            if self._should_auto_resolve(alert):
                self._auto_resolve_alert(alert)
                alerts_to_remove.append(alert_id)

        # Remove resolved alerts
        for alert_id in alerts_to_remove:
            del self.active_alerts[alert_id]

    def _check_alert_escalation(self, alert: WorkflowAlert, current_time: datetime):
        """Check if alert needs escalation"""
        alert_age = (current_time - alert.created_at).total_seconds()

        for rule_name, rule_config in self.alert_rules.items():
            if alert.severity in rule_config["severities"]:
                escalation_time = rule_config["escalation_time"]
                if alert_age > escalation_time and not alert.acknowledged:
                    # Escalate alert
                    self._escalate_alert(alert)
                break

    def _escalate_alert(self, alert: WorkflowAlert):
        """Escalate alert to higher severity"""
        severity_order = [
            AlertSeverity.INFO,
            AlertSeverity.LOW,
            AlertSeverity.MEDIUM,
            AlertSeverity.HIGH,
            AlertSeverity.CRITICAL,
        ]

        current_index = severity_order.index(alert.severity)
        if current_index < len(severity_order) - 1:
            alert.severity = severity_order[current_index + 1]
            logger.warning(
                f"Escalated alert {alert.alert_id} to {alert.severity.value}"
            )

    def _should_auto_resolve(self, alert: WorkflowAlert) -> bool:
        """Check if alert should be auto-resolved"""
        # Check if conditions that triggered alert have normalized
        if alert.trigger_conditions.get("auto_acknowledge", False):
            return True

        # Check if alert has been resolved manually
        return alert.resolved

    def _auto_resolve_alert(self, alert: WorkflowAlert):
        """Auto-resolve an alert"""
        alert.resolved = True
        alert.resolution_notes = "Auto-resolved by monitoring system"
        logger.info(f"Auto-resolved alert: {alert.alert_id}")

    def _generate_insights(self):
        """Generate AI-powered performance insights"""
        for workflow_id, metrics in self.workflow_metrics.items():
            if len(metrics) < 20:  # Need sufficient data for insights
                continue

            insights = self.insight_generator.generate_insights(workflow_id, metrics)

            for insight in insights:
                if workflow_id not in self.performance_insights:
                    self.performance_insights[workflow_id] = []

                self.performance_insights[workflow_id].append(insight)
                logger.info(
                    f"Generated insight for {workflow_id}: {insight.insight_type}"
                )

    def _auto_resolve_issues(self):
        """Attempt to auto-resolve detected issues"""
        for workflow_id, insights in self.performance_insights.items():
            resolvable_insights = [i for i in insights if i.impact_score > 0.7]

            for insight in resolvable_insights:
                resolution_result = self.auto_resolver.attempt_resolution(
                    workflow_id, insight
                )
                if resolution_result["success"]:
                    logger.info(
                        f"Auto-resolved issue for {workflow_id}: {insight.insight_type}"
                    )

    def get_workflow_health(self, workflow_id: str) -> Dict[str, Any]:
        """Get comprehensive health status for a workflow"""
        metrics = self.workflow_metrics.get(workflow_id, [])
        active_alerts = [
            a
            for a in self.active_alerts.values()
            if a.workflow_id == workflow_id and not a.resolved
        ]
        insights = self.performance_insights.get(workflow_id, [])

        # Calculate health score (0-100)
        health_score = self._
