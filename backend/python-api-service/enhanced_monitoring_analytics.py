#!/usr/bin/env python3
"""
📊 ENHANCED MONITORING & ANALYTICS SYSTEM
Advanced monitoring, analytics, and performance optimization for all integrations
"""

import asyncio
import json
import logging
import statistics
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

# Third-party imports
try:
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logging.warning("Machine learning libraries not available")

try:
    import psutil

    SYSTEM_MONITORING_AVAILABLE = True
except ImportError:
    SYSTEM_MONITORING_AVAILABLE = False
    logging.warning("System monitoring not available")

# Local imports
from flask import Blueprint, jsonify, request, current_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint for enhanced monitoring
enhanced_monitoring_bp = Blueprint("enhanced_monitoring", __name__)


class ServiceHealthStatus(Enum):
    """Service health status enumeration"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ServiceMetrics:
    """Service performance metrics"""

    service_name: str
    response_time_ms: float
    success_rate: float
    error_count: int
    request_count: int
    last_checked: datetime
    health_score: float
    status: ServiceHealthStatus


@dataclass
class PerformanceAlert:
    """Performance alert definition"""

    alert_id: str
    service_name: str
    severity: AlertSeverity
    message: str
    metric: str
    threshold: float
    current_value: float
    timestamp: datetime
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class SystemHealth:
    """System health overview"""

    overall_score: float
    healthy_services: int
    total_services: int
    critical_alerts: int
    performance_trend: str  # improving, stable, degrading
    last_updated: datetime


class EnhancedMonitoringAnalytics:
    """
    Enhanced monitoring and analytics system for all integrations
    """

    def __init__(self):
        self.service_metrics: Dict[str, ServiceMetrics] = {}
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.performance_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self.anomaly_detectors: Dict[str, Any] = {}
        self.alert_thresholds = self._get_default_thresholds()
        self.monitoring_enabled = True
        self.initialized = False

    def _get_default_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Get default alert thresholds for different metrics"""
        return {
            "response_time": {
                "warning": 1000.0,  # 1 second
                "critical": 5000.0,  # 5 seconds
            },
            "success_rate": {
                "warning": 0.95,  # 95%
                "critical": 0.90,  # 90%
            },
            "error_rate": {
                "warning": 0.05,  # 5%
                "critical": 0.10,  # 10%
            },
        }

    async def initialize(self):
        """Initialize the enhanced monitoring system"""
        try:
            logger.info("📊 Initializing Enhanced Monitoring & Analytics System...")

            # Initialize ML models for anomaly detection
            if ML_AVAILABLE:
                await self._initialize_anomaly_detectors()

            # Load historical data (in production, this would come from database)
            await self._load_historical_metrics()

            # Start background monitoring tasks
            asyncio.create_task(self._background_monitoring_loop())

            self.initialized = True
            logger.info(
                "✅ Enhanced Monitoring & Analytics System initialized successfully"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize Enhanced Monitoring System: {e}")
            return False

    async def _initialize_anomaly_detectors(self):
        """Initialize ML models for anomaly detection"""
        if not ML_AVAILABLE:
            return

        try:
            # Initialize detectors for different metrics
            metrics_to_monitor = ["response_time", "success_rate", "error_rate"]

            for metric in metrics_to_monitor:
                self.anomaly_detectors[metric] = IsolationForest(
                    contamination=0.1,  # Expect 10% anomalies
                    random_state=42,
                )
                self.scalers[metric] = StandardScaler()

            logger.info("✅ Anomaly detection models initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize anomaly detectors: {e}")

    async def _load_historical_metrics(self):
        """Load historical metrics data"""
        # In production, this would load from a database
        # For now, we'll create sample historical data
        sample_services = [
            "slack",
            "github",
            "trello",
            "asana",
            "notion",
            "google_calendar",
        ]

        for service in sample_services:
            # Generate sample historical data
            base_response_time = 200 + (hash(service) % 300)  # Vary by service
            base_success_rate = 0.95 + (hash(service) % 10) / 100  # Vary by service

            historical_data = []
            for i in range(50):  # 50 historical data points
                response_time = base_response_time + np.random.normal(0, 50)
                success_rate = max(
                    0.7, min(1.0, base_success_rate + np.random.normal(0, 0.05))
                )

                historical_data.append(
                    {
                        "response_time": response_time,
                        "success_rate": success_rate,
                        "error_rate": 1 - success_rate,
                        "timestamp": datetime.now() - timedelta(hours=i),
                    }
                )

            self.performance_history[service] = deque(historical_data, maxlen=1000)

    async def _background_monitoring_loop(self):
        """Background monitoring loop that runs periodically"""
        while self.monitoring_enabled:
            try:
                # Check all services
                await self._check_all_services()

                # Generate system health report
                await self._generate_health_report()

                # Clean up old alerts
                await self._cleanup_old_alerts()

                # Wait before next check
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in background monitoring loop: {e}")
                await asyncio.sleep(30)  # Wait shorter time on error

    async def _check_all_services(self):
        """Check health of all registered services"""
        # This would make actual health checks to services
        # For now, we'll simulate the checks

        services_to_check = list(self.performance_history.keys())

        for service in services_to_check:
            try:
                # Simulate service health check
                metrics = await self._simulate_service_check(service)

                # Update metrics
                self.service_metrics[service] = metrics

                # Check for anomalies and generate alerts
                await self._check_service_anomalies(service, metrics)

                # Update performance history
                self.performance_history[service].append(
                    {
                        "response_time": metrics.response_time_ms,
                        "success_rate": metrics.success_rate,
                        "error_rate": 1 - metrics.success_rate,
                        "timestamp": metrics.last_checked,
                    }
                )

            except Exception as e:
                logger.error(f"Failed to check service {service}: {e}")

    async def _simulate_service_check(self, service_name: str) -> ServiceMetrics:
        """Simulate service health check (replace with actual API calls)"""
        # Get historical data for this service
        history = list(self.performance_history[service_name])

        if history:
            # Use recent history to simulate current state
            recent_data = history[-1]
            response_time = recent_data["response_time"] + np.random.normal(0, 20)
            success_rate = max(
                0.7, min(1.0, recent_data["success_rate"] + np.random.normal(0, 0.02))
            )
        else:
            # Initial values for new service
            response_time = 200 + (hash(service_name) % 300)
            success_rate = 0.95 + (hash(service_name) % 10) / 100

        # Calculate health score
        health_score = self._calculate_health_score(response_time, success_rate)
        status = self._determine_health_status(health_score)

        return ServiceMetrics(
            service_name=service_name,
            response_time_ms=max(50, response_time),  # Minimum 50ms
            success_rate=success_rate,
            error_count=int((1 - success_rate) * 100),  # Simulate error count
            request_count=100,  # Simulate request count
            last_checked=datetime.now(),
            health_score=health_score,
            status=status,
        )

    def _calculate_health_score(
        self, response_time: float, success_rate: float
    ) -> float:
        """Calculate overall health score for a service"""
        # Normalize response time (lower is better)
        response_score = max(0, 1 - (response_time / 5000))  # 5s max response time

        # Success rate is already normalized
        success_score = success_rate

        # Weighted combination
        health_score = (response_score * 0.4) + (success_score * 0.6)
        return round(health_score * 100, 2)  # Convert to percentage

    def _determine_health_status(self, health_score: float) -> ServiceHealthStatus:
        """Determine health status based on score"""
        if health_score >= 90:
            return ServiceHealthStatus.HEALTHY
        elif health_score >= 75:
            return ServiceHealthStatus.DEGRADED
        elif health_score >= 50:
            return ServiceHealthStatus.UNHEALTHY
        else:
            return ServiceHealthStatus.OFFLINE

    async def _check_service_anomalies(
        self, service_name: str, metrics: ServiceMetrics
    ):
        """Check for anomalies and generate alerts"""
        # Check threshold-based alerts
        await self._check_threshold_alerts(service_name, metrics)

        # Check ML-based anomaly detection
        if ML_AVAILABLE:
            await self._check_ml_anomalies(service_name, metrics)

    async def _check_threshold_alerts(self, service_name: str, metrics: ServiceMetrics):
        """Check for threshold-based alerts"""
        alerts = []

        # Response time alerts
        if (
            metrics.response_time_ms
            > self.alert_thresholds["response_time"]["critical"]
        ):
            alerts.append(
                PerformanceAlert(
                    alert_id=f"resp_crit_{service_name}_{int(time.time())}",
                    service_name=service_name,
                    severity=AlertSeverity.CRITICAL,
                    message=f"Critical response time for {service_name}: {metrics.response_time_ms}ms",
                    metric="response_time",
                    threshold=self.alert_thresholds["response_time"]["critical"],
                    current_value=metrics.response_time_ms,
                    timestamp=datetime.now(),
                )
            )
        elif (
            metrics.response_time_ms > self.alert_thresholds["response_time"]["warning"]
        ):
            alerts.append(
                PerformanceAlert(
                    alert_id=f"resp_warn_{service_name}_{int(time.time())}",
                    service_name=service_name,
                    severity=AlertSeverity.MEDIUM,
                    message=f"High response time for {service_name}: {metrics.response_time_ms}ms",
                    metric="response_time",
                    threshold=self.alert_thresholds["response_time"]["warning"],
                    current_value=metrics.response_time_ms,
                    timestamp=datetime.now(),
                )
            )

        # Success rate alerts
        if metrics.success_rate < self.alert_thresholds["success_rate"]["critical"]:
            alerts.append(
                PerformanceAlert(
                    alert_id=f"success_crit_{service_name}_{int(time.time())}",
                    service_name=service_name,
                    severity=AlertSeverity.CRITICAL,
                    message=f"Critical success rate for {service_name}: {metrics.success_rate:.1%}",
                    metric="success_rate",
                    threshold=self.alert_thresholds["success_rate"]["critical"],
                    current_value=metrics.success_rate,
                    timestamp=datetime.now(),
                )
            )
        elif metrics.success_rate < self.alert_thresholds["success_rate"]["warning"]:
            alerts.append(
                PerformanceAlert(
                    alert_id=f"success_warn_{service_name}_{int(time.time())}",
                    service_name=service_name,
                    severity=AlertSeverity.MEDIUM,
                    message=f"Low success rate for {service_name}: {metrics.success_rate:.1%}",
                    metric="success_rate",
                    threshold=self.alert_thresholds["success_rate"]["warning"],
                    current_value=metrics.success_rate,
                    timestamp=datetime.now(),
                )
            )

        # Add alerts to active alerts
        for alert in alerts:
            self.active_alerts[alert.alert_id] = alert
            logger.warning(f"🚨 {alert.severity.value.upper()} ALERT: {alert.message}")

    async def _check_ml_anomalies(self, service_name: str, metrics: ServiceMetrics):
        """Check for ML-based anomalies"""
        try:
            history = list(self.performance_history[service_name])
            if len(history) < 10:  # Need minimum data points
                return

            # Prepare features for anomaly detection
            features = []
            for metric_name in ["response_time", "success_rate", "error_rate"]:
                recent_values = [point[metric_name] for point in history[-10:]]
                features.extend(
                    [
                        np.mean(recent_values),
                        np.std(recent_values),
                        recent_values[-1],  # Current value
                    ]
                )

            features_array = np.array(features).reshape(1, -1)

            # Check each metric detector
            for metric_name, detector in self.anomaly_detectors.items():
                if hasattr(self, "scalers") and metric_name in self.scalers:
                    features_scaled = self.scalers[metric_name].transform(
                        features_array
                    )
                    prediction = detector.predict(features_scaled)

                    if prediction[0] == -1:  # Anomaly detected
                        alert = PerformanceAlert(
                            alert_id=f"ml_anomaly_{service_name}_{metric_name}_{int(time.time())}",
                            service_name=service_name,
                            severity=AlertSeverity.HIGH,
                            message=f"ML anomaly detected for {service_name} in {metric_name}",
                            metric=metric_name,
                            threshold=0,  # ML-based, no fixed threshold
                            current_value=getattr(metrics, metric_name, 0),
                            timestamp=datetime.now(),
                        )
                        self.active_alerts[alert.alert_id] = alert
                        logger.warning(f"🤖 ML ALERT: {alert.message}")

        except Exception as e:
            logger.error(f"ML anomaly detection failed for {service_name}: {e}")

    async def _generate_health_report(self):
        """Generate system health report"""
        # This would typically save to database or send to dashboard
        # For now, we'll just log it periodically
        if len(self.service_metrics) > 0:
            healthy_count = sum(
                1
                for m in self.service_metrics.values()
                if m.status == ServiceHealthStatus.HEALTHY
            )
            total_count = len(self.service_metrics)
            critical_alerts = sum(
                1
                for a in self.active_alerts.values()
                if a.severity == AlertSeverity.CRITICAL and not a.resolved
            )

            overall_score = (
                (healthy_count / total_count * 100) if total_count > 0 else 0
            )

            # Determine trend (simplified)
            trend = "stable"  # In production, this would analyze historical data

            self.system_health = SystemHealth(
                overall_score=overall_score,
                healthy_services=healthy_count,
                total_services=total_count,
                critical_alerts=critical_alerts,
                performance_trend=trend,
                last_updated=datetime.now(),
            )

    async def _cleanup_old_alerts(self):
        """Clean up old resolved alerts"""
        current_time = datetime.now()
        alerts_to_remove = []

        for alert_id, alert in self.active_alerts.items():
            # Remove alerts older than 24 hours or resolved for more than 1 hour
            age = current_time - alert.timestamp
            if age > timedelta(hours=24) or (
                alert.resolved and age > timedelta(hours=1)
            ):
                alerts_to_remove.append(alert_id)

        for alert_id in alerts_to_remove:
            del self.active_alerts[alert_id]

    def get_service_metrics(self, service_name: str) -> Optional[ServiceMetrics]:
        """Get metrics for a specific service"""
        return self.service_metrics.get(service_name)

    def get_all_metrics(self) -> Dict[str, ServiceMetrics]:
        """Get metrics for all services"""
        return self.service_metrics

    def get_active_alerts(
        self, severity: Optional[AlertSeverity] = None
    ) -> List[PerformanceAlert]:
        """Get active alerts, optionally filtered by severity"""
        if severity:
            return [
                alert
                for alert in self.active_alerts.values()
                if alert.severity == severity and not alert.resolved
            ]
        else:
            return [
                alert for alert in self.active_alerts.values() if not alert.resolved
            ]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolved = True
            return True
        return False

    def get_performance_history(
        self, service_name: str, metric: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get performance history for a service and metric"""
        if service_name not in self.performance_history:
            return []

        history = list(self.performance_history[service_name])
        cutoff_time = datetime.now() - timedelta(hours=hours)

        filtered_history = [
            point
            for point in history
            if point["timestamp"] >= cutoff_time and metric in point
        ]

        return filtered_history

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        return {
            "initialized": self.initialized,
            "monitoring_enabled": self.monitoring_enabled,
            "services_monitored": len(self.service_metrics),
            "active_alerts": len(
                [a for a in self.active_alerts.values() if not a.resolved]
            ),
            "critical_alerts": len(
                [
                    a
                    for a in self.active_alerts.values()
                    if a.severity == AlertSeverity.CRITICAL and not a.resolved
                ]
            ),
            "health_score": getattr(self.system_health, "overall_score", 0)
            if hasattr(self, "system_health")
            else 0,
        }
