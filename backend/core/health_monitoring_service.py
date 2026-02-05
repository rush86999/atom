"""
Health Monitoring Service

Monitors agent operations, integration health, and system metrics.
Provides real-time health status with proactive alerting.
"""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentRegistry,
    CanvasRecording,
    IntegrationCatalog,
    IntegrationHealthMetrics,
    User,
    UserConnection,
)
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)


# Feature flags
import os

HEALTH_POLLING_INTERVAL = int(os.getenv("HEALTH_POLLING_INTERVAL", "30"))  # seconds
ALERT_ERROR_RATE_THRESHOLD = float(os.getenv("ALERT_ERROR_RATE_THRESHOLD", "0.5"))  # 50%
ALERT_LATENCY_THRESHOLD = int(os.getenv("ALERT_LATENCY_THRESHOLD", "5000"))  # 5s
ALERT_QUEUE_DEPTH_THRESHOLD = int(os.getenv("ALERT_QUEUE_DEPTH_THRESHOLD", "100"))


class HealthMonitoringService:
    """
    Health monitoring service for agents and integrations.

    Features:
    - Real-time agent status monitoring
    - Integration health tracking
    - System metrics collection
    - Proactive alert generation
    - Health history for trend analysis
    """

    def __init__(self, db: Session):
        self.db = db
        self._alert_cache = {}  # In-memory cache for recent alerts

    async def get_agent_health(
        self,
        agent_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive health status for an agent.

        Returns:
            {
                "agent_id": str,
                "agent_name": str,
                "status": "active" | "idle" | "error" | "paused",
                "current_operation": str | None,
                "operations_completed": int,
                "success_rate": float (0-1),
                "confidence_score": float (0-1),
                "last_active": ISO8601,
                "health_trend": "improving" | "stable" | "declining",
                "metrics": {
                    "avg_execution_time": float (ms),
                    "error_rate": float (0-1),
                    "recent_executions": int
                }
            }
        """
        try:
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                return {
                    "agent_id": agent_id,
                    "status": "error",
                    "error": "Agent not found"
                }

            # Get recent executions
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            recent_executions = self.db.query(AgentExecution).filter(
                and_(
                    AgentExecution.agent_id == agent_id,
                    AgentExecution.started_at >= cutoff_time
                )
            ).all()

            # Calculate metrics
            total_executions = len(recent_executions)
            completed_executions = sum(1 for e in recent_executions if e.status == "completed")
            error_executions = sum(1 for e in recent_executions if e.status == "failed")

            success_rate = completed_executions / max(total_executions, 1)
            error_rate = error_executions / max(total_executions, 1)

            # Calculate avg execution time
            execution_times = [
                (e.completed_at - e.started_at).total_seconds() * 1000
                for e in recent_executions
                if e.completed_at and e.started_at
            ]
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else None

            # Determine current status
            current_operation = None
            if total_executions > 0:
                latest_execution = recent_executions[-1]
                if latest_execution.status == "running":
                    current_operation = latest_execution.input_summary
                    status = "active"
                elif latest_execution.status == "failed":
                    status = "error"
                elif agent.status == "paused":
                    status = "paused"
                else:
                    status = "idle"
            else:
                status = "idle" if agent.status != "paused" else "paused"

            # Calculate health trend
            health_trend = await self._calculate_health_trend(agent_id)

            return {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "status": status,
                "current_operation": current_operation,
                "operations_completed": completed_executions,
                "success_rate": round(success_rate, 3),
                "confidence_score": round(agent.confidence_score or 0.5, 3),
                "last_active": recent_executions[-1].started_at.isoformat() if recent_executions else agent.updated_at.isoformat(),
                "health_trend": health_trend,
                "metrics": {
                    "avg_execution_time": round(avg_execution_time, 2) if avg_execution_time else None,
                    "error_rate": round(error_rate, 3),
                    "recent_executions": total_executions
                }
            }

        except Exception as e:
            logger.error(f"Failed to get agent health for {agent_id}: {e}")
            return {
                "agent_id": agent_id,
                "status": "error",
                "error": str(e)
            }

    async def get_all_integrations_health(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get health status for all user's integrations.

        Returns:
            [
                {
                    "integration_id": str,
                    "integration_name": str,
                    "status": "healthy" | "degraded" | "error",
                    "last_used": ISO8601,
                    "latency_ms": float,
                    "error_rate": float (0-1),
                    "health_trend": "improving" | "stable" | "declining",
                    "connection_status": "connected" | "disconnected" | "error"
                },
                ...
            ]
        """
        try:
            # Get user's connections
            connections = self.db.query(UserConnection).filter(
                UserConnection.user_id == user_id
            ).all()

            health_list = []

            for connection in connections:
                # Get integration catalog info
                integration = self.db.query(IntegrationCatalog).filter(
                    IntegrationCatalog.id == connection.integration_id
                ).first()

                if not integration:
                    continue

                # Calculate health metrics
                health = await self._calculate_integration_health(connection, integration)
                health_list.append(health)

            return health_list

        except Exception as e:
            logger.error(f"Failed to get integrations health: {e}")
            return []

    async def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system-wide health metrics.

        Returns:
            {
                "cpu_usage": float (0-100),
                "memory_usage": float (0-100),
                "active_operations": int,
                "queue_depth": int,
                "total_agents": int,
                "active_agents": int,
                "total_integrations": int,
                "healthy_integrations": int,
                "alerts": {
                    "critical": int,
                    "warning": int,
                    "info": int
                }
            }
        """
        try:
            # Count agents
            total_agents = self.db.query(AgentRegistry).count()
            active_agents = self.db.query(AgentRegistry).filter(
                AgentRegistry.status.in_(["active", "autonomous", "supervised"])
            ).count()

            # Count active operations
            active_operations = self.db.query(AgentExecution).filter(
                AgentExecution.status == "running"
            ).count()

            # Count operations in queue (pending/created)
            queue_depth = self.db.query(AgentExecution).filter(
                AgentExecution.status.in_(["pending", "created"])
            ).count()

            # Get integration health
            # Define healthy: active status with successful connection within last 5 minutes
            recent_success_threshold = datetime.now() - timedelta(minutes=5)
            total_integrations = self.db.query(IntegrationCatalog).count()
            healthy_integrations = self.db.query(IntegrationCatalog).filter(
                IntegrationCatalog.last_successful_connection >= recent_success_threshold,
                IntegrationCatalog.status == "active"
            ).count()

            # Get alert counts
            alerts = await self.get_active_alerts_summary()

            # System metrics using psutil
            cpu_usage = 0
            memory_usage = 0
            disk_usage = 0

            try:
                import psutil

                # CPU usage (0-100%)
                cpu_usage = psutil.cpu_percent(interval=0.1)

                # Memory usage (0-100%)
                memory = psutil.virtual_memory()
                memory_usage = memory.percent

                # Disk usage (0-100%)
                disk = psutil.disk_usage('/')
                disk_usage = disk.percent

                # Additional metrics
                process_count = len(psutil.pids())

            except ImportError:
                logger.warning("psutil not installed - system metrics unavailable")
                cpu_usage = 0
                memory_usage = 0
                disk_usage = 0
            except Exception as e:
                logger.error(f"Failed to get system metrics from psutil: {e}")
                cpu_usage = 0
                memory_usage = 0
                disk_usage = 0

            return {
                "cpu_usage": round(cpu_usage, 2),
                "memory_usage": round(memory_usage, 2),
                "disk_usage": round(disk_usage, 2),
                "active_operations": active_operations,
                "queue_depth": queue_depth,
                "total_agents": total_agents,
                "active_agents": active_agents,
                "total_integrations": total_integrations,
                "healthy_integrations": healthy_integrations,
                "alerts": alerts,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {
                "cpu_usage": 0,
                "memory_usage": 0,
                "disk_usage": 0,
                "active_operations": 0,
                "queue_depth": 0,
                "total_agents": 0,
                "active_agents": 0,
                "total_integrations": 0,
                "healthy_integrations": 0,
                "alerts": {"critical": 0, "warning": 0, "info": 0},
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    async def get_active_alerts(
        self,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get active alerts for user or system-wide.

        Args:
            user_id: Optional user filter (if None, return system alerts)

        Returns:
            [
                {
                    "alert_id": str,
                    "severity": "critical" | "warning" | "info",
                    "message": str,
                    "source_type": "agent" | "integration" | "system",
                    "source_id": str,
                    "timestamp": ISO8601,
                    "action_required": bool,
                    "acknowledged": bool
                },
                ...
            ]
        """
        try:
            alerts = []

            # Check for system alerts
            system_metrics = await self.get_system_metrics()

            # CPU alert
            if system_metrics["cpu_usage"] > 80:
                alerts.append({
                    "alert_id": str(uuid.uuid4()),
                    "severity": "warning" if system_metrics["cpu_usage"] < 90 else "critical",
                    "message": f"High CPU usage: {system_metrics['cpu_usage']}%",
                    "source_type": "system",
                    "source_id": "system",
                    "timestamp": datetime.utcnow().isoformat(),
                    "action_required": True,
                    "acknowledged": False
                })

            # Memory alert
            if system_metrics["memory_usage"] > 80:
                alerts.append({
                    "alert_id": str(uuid.uuid4()),
                    "severity": "warning" if system_metrics["memory_usage"] < 90 else "critical",
                    "message": f"High memory usage: {system_metrics['memory_usage']}%",
                    "source_type": "system",
                    "source_id": "system",
                    "timestamp": datetime.utcnow().isoformat(),
                    "action_required": True,
                    "acknowledged": False
                })

            # Queue depth alert
            if system_metrics["queue_depth"] > ALERT_QUEUE_DEPTH_THRESHOLD:
                alerts.append({
                    "alert_id": str(uuid.uuid4()),
                    "severity": "warning",
                    "message": f"High queue depth: {system_metrics['queue_depth']} operations pending",
                    "source_type": "system",
                    "source_id": "system",
                    "timestamp": datetime.utcnow().isoformat(),
                    "action_required": False,
                    "acknowledged": False
                })

            # Check agent health if user_id provided
            if user_id:
                agents = self.db.query(AgentRegistry).filter(
                    AgentRegistry.user_id == user_id
                ).all()

                for agent in agents:
                    agent_health = await self.get_agent_health(agent.id)

                    # Agent error alert
                    if agent_health.get("metrics", {}).get("error_rate", 0) > ALERT_ERROR_RATE_THRESHOLD:
                        alerts.append({
                            "alert_id": str(uuid.uuid4()),
                            "severity": "warning",
                            "message": f"Agent {agent.name} has high error rate: {agent_health['metrics']['error_rate']:.1%}",
                            "source_type": "agent",
                            "source_id": agent.id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "action_required": True,
                            "acknowledged": False
                        })

            return alerts

        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return []

    async def get_active_alerts_summary(self) -> Dict[str, int]:
        """Get summary of active alerts by severity."""
        try:
            alerts = await self.get_active_alerts()

            summary = {
                "critical": 0,
                "warning": 0,
                "info": 0
            }

            for alert in alerts:
                if not alert.get("acknowledged", False):
                    severity = alert.get("severity", "info")
                    summary[severity] = summary.get(severity, 0) + 1

            return summary

        except Exception as e:
            logger.error(f"Failed to get alert summary: {e}")
            return {"critical": 0, "warning": 0, "info": 0}

    async def acknowledge_alert(
        self,
        alert_id: str,
        user_id: str
    ) -> bool:
        """
        Acknowledge an alert (mark as resolved).

        Args:
            alert_id: Alert to acknowledge
            user_id: User acknowledging the alert

        Returns:
            True if acknowledged successfully
        """
        try:
            # In a real implementation, this would update an alerts table
            # For now, we'll just log it
            logger.info(f"Alert {alert_id} acknowledged by user {user_id}")

            # Broadcast update
            await ws_manager.broadcast(
                "system:alerts",
                {
                    "type": "alert_acknowledged",
                    "data": {
                        "alert_id": alert_id,
                        "acknowledged_by": user_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False

    async def get_health_history(
        self,
        health_type: str,  # "agent" | "integration" | "system"
        entity_id: Optional[str],
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get health history for trend analysis.

        Args:
            health_type: Type of health history
            entity_id: Optional entity ID (agent_id, integration_id)
            days: Number of days to look back

        Returns:
            [
                {
                    "timestamp": ISO8601,
                    "health_score": float (0-1),
                    "status": str,
                    "metrics": {...}
                },
                ...
            ]
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            history = []

            if health_type == "agent" and entity_id:
                # Get agent execution history
                executions = self.db.query(AgentExecution).filter(
                    and_(
                        AgentExecution.agent_id == entity_id,
                        AgentExecution.started_at >= cutoff_date
                    )
                ).order_by(AgentExecution.started_at).all()

                # Group by day
                daily_stats = {}
                for execution in executions:
                    date_str = execution.started_at.date().isoformat()
                    if date_str not in daily_stats:
                        daily_stats[date_str] = {
                            "total": 0,
                            "completed": 0,
                            "failed": 0
                        }

                    daily_stats[date_str]["total"] += 1
                    if execution.status == "completed":
                        daily_stats[date_str]["completed"] += 1
                    elif execution.status == "failed":
                        daily_stats[date_str]["failed"] += 1

                # Convert to history format
                for date_str, stats in daily_stats.items():
                    success_rate = stats["completed"] / max(stats["total"], 1)
                    history.append({
                        "timestamp": f"{date_str}T00:00:00Z",
                        "health_score": round(success_rate, 3),
                        "status": "healthy" if success_rate >= 0.8 else "degraded" if success_rate >= 0.5 else "error",
                        "metrics": {
                            "total_executions": stats["total"],
                            "completed": stats["completed"],
                            "failed": stats["failed"]
                        }
                    })

            # Sort by timestamp
            history.sort(key=lambda x: x["timestamp"])

            return history

        except Exception as e:
            logger.error(f"Failed to get health history: {e}")
            return []

    async def _calculate_integration_health(
        self,
        connection: UserConnection,
        integration: IntegrationCatalog
    ) -> Dict[str, Any]:
        """Calculate health status for a single integration."""
        try:
            # Determine status
            if connection.status == "active":
                status = "healthy"
                connection_status = "connected"
            elif connection.status == "error":
                status = "error"
                connection_status = "error"
            else:
                status = "degraded"
                connection_status = "disconnected"

            # Get health metrics from historical data
            metrics = self.db.query(IntegrationHealthMetrics).filter(
                IntegrationHealthMetrics.connection_id == connection.id
            ).order_by(IntegrationHealthMetrics.created_at.desc()).limit(100).all()

            # Calculate health trend, latency, and error rate from metrics
            if metrics and len(metrics) >= 2:
                # Calculate average latency
                avg_latency = sum(m.latency_ms for m in metrics if m.latency_ms) / max(len([m for m in metrics if m.latency_ms]), 1)
                latency_ms = round(avg_latency, 2)

                # Calculate error rate
                total_requests = sum(m.request_count for m in metrics)
                total_errors = sum(m.error_count for m in metrics)
                error_rate = round(total_errors / max(total_requests, 1), 4)

                # Calculate trend based on recent vs older success rates
                recent_metrics = metrics[:10]  # Most recent 10
                older_metrics = metrics[10:20] if len(metrics) > 10 else metrics[10:]

                recent_success_rate = sum(m.success_rate for m in recent_metrics) / max(len(recent_metrics), 1)
                older_success_rate = sum(m.success_rate for m in older_metrics) / max(len(older_metrics), 1)

                # Determine trend
                if recent_success_rate > older_success_rate + 0.1:
                    health_trend = "improving"
                elif recent_success_rate < older_success_rate - 0.1:
                    health_trend = "declining"
                else:
                    health_trend = "stable"
            else:
                # Default values when no historical data
                latency_ms = 0.0
                error_rate = 0.0
                health_trend = "stable"

            # Get last used time
            last_used = connection.updated_at or connection.created_at

            return {
                "integration_id": integration.id,
                "integration_name": integration.name,
                "status": status,
                "last_used": last_used.isoformat(),
                "latency_ms": latency_ms,
                "error_rate": error_rate,
                "health_trend": health_trend,
                "connection_status": connection_status
            }

        except Exception as e:
            logger.error(f"Failed to calculate integration health: {e}")
            return {
                "integration_id": integration.id,
                "integration_name": integration.name,
                "status": "error",
                "last_used": datetime.utcnow().isoformat(),
                "latency_ms": 0,
                "error_rate": 1.0,
                "health_trend": "declining",
                "connection_status": "error"
            }

    async def _calculate_health_trend(
        self,
        agent_id: str,
        days: int = 7
    ) -> str:
        """
        Calculate health trend for an agent.

        Returns:
            "improving" | "stable" | "declining"
        """
        try:
            # Get health history for the past week
            history = await self.get_health_history("agent", agent_id, days)

            if len(history) < 2:
                return "stable"

            # Calculate trend
            recent_score = history[-1]["health_score"]
            old_score = history[0]["health_score"]

            if recent_score > old_score + 0.1:
                return "improving"
            elif recent_score < old_score - 0.1:
                return "declining"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"Failed to calculate health trend: {e}")
            return "stable"

    async def start_health_monitoring(self, user_id: str):
        """
        Start real-time health monitoring for a user.

        Broadcasts health updates every HEALTH_POLLING_INTERVAL seconds.
        """
        try:
            import asyncio

            while True:
                # Get user's agents
                agents = self.db.query(AgentRegistry).filter(
                    AgentRegistry.user_id == user_id
                ).all()

                # Get health for all agents
                agent_health_list = []
                for agent in agents:
                    health = await self.get_agent_health(agent.id)
                    agent_health_list.append(health)

                # Get integration health
                integration_health = await self.get_all_integrations_health(user_id)

                # Get alerts
                alerts = await self.get_active_alerts(user_id)

                # Broadcast health update
                await ws_manager.broadcast(
                    f"user:{user_id}",
                    {
                        "type": "health:update",
                        "data": {
                            "agents": agent_health_list,
                            "integrations": integration_health,
                            "alerts": alerts[:5],  # Limit to top 5
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )

                # Wait before next poll
                await asyncio.sleep(HEALTH_POLLING_INTERVAL)

        except Exception as e:
            logger.error(f"Health monitoring error: {e}")


# Singleton helper
def get_health_monitoring_service(db: Session) -> HealthMonitoringService:
    """Get or create health monitoring service instance."""
    return HealthMonitoringService(db)
