#!/usr/bin/env python3
"""
🚀 ENHANCED MONITORING ROUTES
API endpoints for advanced monitoring, analytics, and performance optimization
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

# Import the enhanced monitoring system
try:
    from enhanced_monitoring_analytics import (
        AlertSeverity,
        EnhancedMonitoringAnalytics,
        PerformanceAlert,
        ServiceHealthStatus,
        ServiceMetrics,
        SystemHealth,
    )

    ENHANCED_MONITORING_AVAILABLE = True
except ImportError as e:
    ENHANCED_MONITORING_AVAILABLE = False
    logging.warning(f"Enhanced Monitoring System not available: {e}")

# Create blueprint for enhanced monitoring routes
enhanced_monitoring_routes = Blueprint("enhanced_monitoring_routes", __name__)

# Global instance of the monitoring system
monitoring_system = None


def get_monitoring_system():
    """Get or initialize the enhanced monitoring system"""
    global monitoring_system
    if monitoring_system is None and ENHANCED_MONITORING_AVAILABLE:
        monitoring_system = EnhancedMonitoringAnalytics()
        # Initialize asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(monitoring_system.initialize())
    return monitoring_system


@enhanced_monitoring_routes.route("/api/v2/monitoring/status", methods=["GET"])
def get_monitoring_status():
    """Get status of enhanced monitoring system"""
    try:
        system = get_monitoring_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "available": False,
                    "message": "Enhanced Monitoring System not available",
                }
            ), 503

        return jsonify(
            {
                "success": True,
                "available": True,
                "initialized": system.initialized,
                "monitoring_enabled": system.monitoring_enabled,
                "services_monitored": len(system.service_metrics),
                "active_alerts": len(
                    [a for a in system.active_alerts.values() if not a.resolved]
                ),
                "system_status": "active" if system.initialized else "initializing",
            }
        )

    except Exception as e:
        logging.error(f"Error getting monitoring status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@enhanced_monitoring_routes.route("/api/v2/monitoring/services", methods=["GET"])
def get_all_service_metrics():
    """Get metrics for all monitored services"""
    try:
        system = get_monitoring_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "Enhanced Monitoring System not available",
                }
            ), 503

        metrics_data = {}
        for service_name, metrics in system.service_metrics.items():
            metrics_data[service_name] = {
                "service_name": metrics.service_name,
                "response_time_ms": metrics.response_time_ms,
                "success_rate": metrics.success_rate,
                "error_count": metrics.error_count,
                "request_count": metrics.request_count,
                "last_checked": metrics.last_checked.isoformat(),
                "health_score": metrics.health_score,
                "status": metrics.status.value,
            }

        return jsonify(
            {
                "success": True,
                "services": metrics_data,
                "total_services": len(metrics_data),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting service metrics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@enhanced_monitoring_routes.route(
    "/api/v2/monitoring/services/<service_name>", methods=["GET"]
)
def get_service_metrics(service_name):
    """Get detailed metrics for a specific service"""
    try:
        system = get_monitoring_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "Enhanced Monitoring System not available",
                }
            ), 503

        metrics = system.get_service_metrics(service_name)
        if not metrics:
            return jsonify({"success": False, "error": "Service not found"}), 404

        # Get performance history
        history = list(system.performance_history.get(service_name, []))
        recent_history = history[-50:] if history else []  # Last 50 data points

        return jsonify(
            {
                "success": True,
                "service": {
                    "service_name": metrics.service_name,
                    "response_time_ms": metrics.response_time_ms,
                    "success_rate": metrics.success_rate,
                    "error_count": metrics.error_count,
                    "request_count": metrics.request_count,
                    "last_checked": metrics.last_checked.isoformat(),
                    "health_score": metrics.health_score,
                    "status": metrics.status.value,
                },
                "performance_history": recent_history,
                "history_count": len(recent_history),
            }
        )

    except Exception as e:
        logging.error(f"Error getting service metrics for {service_name}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@enhanced_monitoring_routes.route("/api/v2/monitoring/alerts", methods=["GET"])
def get_active_alerts():
    """Get all active alerts"""
    try:
        system = get_monitoring_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "Enhanced Monitoring System not available",
                }
            ), 503

        severity_filter = request.args.get("severity")
        if severity_filter:
            try:
                severity = AlertSeverity(severity_filter.lower())
                alerts = system.get_active_alerts(severity)
            except ValueError:
                return jsonify(
                    {"success": False, "error": "Invalid severity filter"}
                ), 400
        else:
            alerts = system.get_active_alerts()

        alerts_data = []
        for alert in alerts:
            alerts_data.append(
                {
                    "alert_id": alert.alert_id,
                    "service_name": alert.service_name,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "metric": alert.metric,
                    "threshold": alert.threshold,
                    "current_value": alert.current_value,
                    "timestamp": alert.timestamp.isoformat(),
                    "acknowledged": alert.acknowledged,
                    "resolved": alert.resolved,
                }
            )

        return jsonify(
            {
                "success": True,
                "alerts": alerts_data,
                "total_alerts": len(alerts_data),
                "critical_count": len(
                    [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
                ),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting active alerts: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@enhanced_monitoring_routes.route(
    "/api/v2/monitoring/alerts/<alert_id>/acknowledge", methods=["POST"]
)
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    try:
        system = get_monitoring_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "Enhanced Monitoring System not available",
                }
            ), 503

        success = system.acknowledge_alert(alert_id)
        if not success:
            return jsonify({"success": False, "error": "Alert not found"}), 404

        return jsonify(
            {
                "success": True,
                "message": f"Alert {alert_id} acknowledged",
                "alert_id": alert_id,
                "acknowledged": True,
            }
        )

    except Exception as e:
        logging.error(f"Error acknowledging alert {alert_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@enhanced_monitoring_routes.route(
    "/api/v2/monitoring/alerts/<alert_id>/resolve", methods=["POST"]
)
def resolve_alert(alert_id):
    """Resolve an alert"""
    try:
        system = get_monitoring_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "Enhanced Monitoring System not available",
                }
            ), 503

        success = system.resolve_alert(alert_id)
        if not success:
            return jsonify({"success": False, "error": "Alert not found"}), 404

        return jsonify(
            {
                "success": True,
                "message": f"Alert {alert_id} resolved",
                "alert_id": alert_id,
                "resolved": True,
            }
        )

    except Exception as e:
        logging.error(f"Error resolving alert {alert_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@enhanced_monitoring_routes.route("/api/v2/monitoring/health", methods=["GET"])
def get_system_health():
    """Get overall system health overview"""
    try:
        system = get_monitoring_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "Enhanced Monitoring System not available",
                }
            ), 503

        # Calculate system health if not already calculated
        if not hasattr(system, "system_health"):
            await system._generate_health_report()

        health_data = system.system_health if hasattr(system, "system_health") else None

        if health_data:
            health_response = {
                "overall_score": health_data.overall_score,
                "healthy_services": health_data.healthy_services,
                "total_services": health_data.total_services,
                "critical_alerts": health_data.critical_alerts,
                "performance_trend": health_data.performance_trend,
                "last_updated": health_data.last_updated.isoformat(),
            }
        else:
            # Fallback calculation
            healthy_count = sum(
                1
                for m in system.service_metrics.values()
                if m.status == ServiceHealthStatus.HEALTHY
            )
            total_count = len(system.service_metrics)
            critical_alerts = sum(
                1
                for a in system.active_alerts.values()
                if a.severity == AlertSeverity.CRITICAL and not a.resolved
            )

            health_response = {
                "overall_score": (healthy_count / total_count * 100)
                if total_count > 0
                else 0,
                "healthy_services": healthy_count,
                "total_services": total_count,
                "critical_alerts": critical_alerts,
                "performance_trend": "stable",
                "last_updated": datetime.now().isoformat(),
            }

        return jsonify(
            {
                "success": True,
                "system_health": health_response,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting system health: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@enhanced_monitoring_routes.route("/api/v2/monitoring/analytics", methods=["GET"])
def get_analytics_dashboard():
    """Get comprehensive analytics for dashboard display"""
    try:
        system = get_monitoring_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "Enhanced Monitoring System not available",
                }
            ), 503

        # Service performance summary
        service_summary = {}
        for service_name, metrics in system.service_metrics.items():
            service_summary[service_name] = {
                "health_score": metrics.health_score,
                "status": metrics.status.value,
                "response_time": metrics.response_time_ms,
                "success_rate": metrics.success_rate,
            }

        # Alert summary by severity
        alert_summary = {}
        for severity in AlertSeverity:
            alerts = system.get_active_alerts(severity)
            alert_summary[severity.value] = len(alerts)

        # Performance trends (simplified)
        performance_trends = {}
        for service_name in system.service_metrics.keys():
            history = list(system.performance_history.get(service_name, []))
            if len(history) >= 2:
                recent_trend = "stable"
                if len(history) >= 5:
                    recent_scores = [
                        point.get("success_rate", 0) for point in history[-5:]
                    ]
                    if recent_scores[-1] > recent_scores[0] + 0.05:
                        recent_trend = "improving"
                    elif recent_scores[-1] < recent_scores[0] - 0.05:
                        recent_trend = "degrading"
                performance_trends[service_name] = recent_trend
            else:
                performance_trends[service_name] = "unknown"

        return jsonify(
            {
                "success": True,
                "analytics": {
                    "service_summary": service_summary,
                    "alert_summary": alert_summary,
                    "performance_trends": performance_trends,
                    "total_services": len(system.service_metrics),
                    "monitoring_enabled": system.monitoring_enabled,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting analytics dashboard: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@enhanced_monitoring_routes.route("/api/v2/monitoring/thresholds", methods=["GET"])
def get_alert_thresholds():
    """Get current alert thresholds"""
    try:
        system = get_monitoring_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "Enhanced Monitoring System not available",
                }
            ), 503

        return jsonify(
            {
                "success": True,
                "thresholds": system.alert_thresholds,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error getting alert thresholds: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@enhanced_monitoring_routes.route("/api/v2/monitoring/thresholds", methods=["PUT"])
def update_alert_thresholds():
    """Update alert thresholds"""
    try:
        system = get_monitoring_system()
        if not system:
            return jsonify(
                {
                    "success": False,
                    "error": "Enhanced Monitoring System not available",
                }
            ), 503

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        # Validate and update thresholds
        for metric, thresholds in data.items():
            if metric in system.alert_thresholds:
                for level, value in thresholds.items():
                    if level in system.alert_thresholds[metric]:
                        try:
                            system.alert_thresholds[metric][level] = float(value)
                        except (ValueError, TypeError):
                            return jsonify(
                                {
                                    "success": False,
                                    "error": f"Invalid threshold value for {metric}.{level}",
                                }
                            ), 400

        return jsonify(
            {
                "success": True,
                "message": "Alert thresholds updated successfully",
                "thresholds": system.alert_thresholds,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error updating alert thresholds: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# Health check endpoint
@enhanced_monitoring_routes.route("/api/v2/monitoring/health-check", methods=["GET"])
def monitoring_health_check():
    """Health check for enhanced monitoring system"""
    try:
        system = get_monitoring_system()

        if not system:
            return jsonify(
                {
                    "status": "unavailable",
                    "message": "Enhanced Monitoring System not available",
                    "timestamp": datetime.now().isoformat(),
                }
            ), 503

        return jsonify(
            {
                "status": "healthy" if system.initialized else "initializing",
                "message": "Enhanced Monitoring System is operational",
                "services_monitored": len(system.service_metrics),
                "active_alerts": len(
                    [a for a in system.active_alerts.values() if not a.resolved]
                ),
                "monitoring_enabled": system.monitoring_enabled,
                "initialized": system.initialized,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Monitoring health check failed: {e}")
        return jsonify(
            {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        ), 500
