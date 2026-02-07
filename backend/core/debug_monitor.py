"""
Debug Monitoring Service for AI Debug System

Provides real-time monitoring of system health and performance:
- Component health scores (0-100)
- Active operation counts
- Error rates by component
- Throughput measurements

Example:
    monitor = DebugMonitor(db_session)

    # Get health for all components
    health_status = await monitor.get_system_health()

    # Get health for specific component
    agent_health = await monitor.get_component_health("agent", "agent-123")
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugMetric,
    DebugInsightSeverity,
)
from core.structured_logger import StructuredLogger


class DebugMonitor:
    """
    Real-time monitoring service for debug data.

    Tracks health metrics, error rates, and throughput across
    all components in the system.
    """

    def __init__(self, db_session: Session):
        """
        Initialize debug monitor.

        Args:
            db_session: SQLAlchemy database session
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session

    async def get_system_health(
        self,
        time_range: str = "last_1h",
    ) -> Dict[str, Any]:
        """
        Get overall system health status.

        Args:
            time_range: Time range for analysis

        Returns:
            System health summary
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Get event statistics
            total_events = (
                self.db.query(func.count(DebugEvent.id))
                .filter(DebugEvent.timestamp >= time_filter)
                .scalar()
            )

            error_events = (
                self.db.query(func.count(DebugEvent.id))
                .filter(
                    and_(
                        DebugEvent.timestamp >= time_filter,
                        DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                    )
                )
                .scalar()
            )

            # Calculate overall health score
            health_score = 100
            if total_events > 0:
                error_rate = error_events / total_events
                health_score = max(0, 100 - (error_rate * 100))

            # Get active operations (events in last 5 minutes)
            recent_time = datetime.utcnow() - timedelta(minutes=5)
            active_operations = (
                self.db.query(
                    func.count(func.distinct(DebugEvent.correlation_id))
                )
                .filter(DebugEvent.timestamp >= recent_time)
                .scalar()
            )

            # Get component breakdown
            components = await self._get_component_breakdown(time_filter)

            return {
                "overall_health_score": health_score,
                "status": "healthy" if health_score >= 90 else "degraded" if health_score >= 70 else "unhealthy",
                "total_events": total_events or 0,
                "error_events": error_events or 0,
                "error_rate": (error_events / total_events * 100) if total_events > 0 else 0,
                "active_operations": active_operations or 0,
                "components": components,
                "time_range": time_range,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error("Failed to get system health", error=str(e))
            return {
                "overall_health_score": 0,
                "status": "error",
                "error": str(e),
            }

    async def get_component_health(
        self,
        component_type: str,
        component_id: str,
        time_range: str = "last_1h",
    ) -> Dict[str, Any]:
        """
        Get health status for a specific component.

        Args:
            component_type: Component type
            component_id: Component ID
            time_range: Time range for analysis

        Returns:
            Component health summary
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Get event statistics
            total_events = (
                self.db.query(func.count(DebugEvent.id))
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.timestamp >= time_filter,
                    )
                )
                .scalar()
            )

            error_events = (
                self.db.query(func.count(DebugEvent.id))
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.timestamp >= time_filter,
                        DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                    )
                )
                .scalar()
            )

            # Calculate health score
            health_score = 100
            if total_events and total_events > 0:
                error_rate = error_events / total_events
                health_score = max(0, 100 - (error_rate * 100))

            # Determine status
            if health_score >= 90:
                status = "healthy"
            elif health_score >= 70:
                status = "degraded"
            else:
                status = "unhealthy"

            # Get recent insights
            recent_insights = (
                self.db.query(DebugInsight)
                .filter(
                    and_(
                        DebugInsight.generated_at >= time_filter,
                        DebugInsight.scope.in_(["component", "distributed"]),
                    )
                )
                .order_by(DebugInsight.generated_at.desc())
                .limit(5)
                .all()
            )

            # Filter insights relevant to this component
            component_insights = []
            for insight in recent_insights:
                if insight.affected_components:
                    for comp in insight.affected_components:
                        if (
                            comp.get("type") == component_type
                            and comp.get("id") == component_id
                        ):
                            component_insights.append({
                                "id": insight.id,
                                "type": insight.insight_type,
                                "severity": insight.severity,
                                "title": insight.title,
                                "summary": insight.summary,
                            })
                            break

            return {
                "component_type": component_type,
                "component_id": component_id,
                "health_score": health_score,
                "status": status,
                "total_events": total_events or 0,
                "error_events": error_events or 0,
                "error_rate": (error_events / total_events * 100) if total_events and total_events > 0 else 0,
                "recent_insights": component_insights[:5],
                "time_range": time_range,
                "analyzed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.logger.error(
                "Failed to get component health",
                component_type=component_type,
                component_id=component_id,
                error=str(e),
            )
            return {
                "component_type": component_type,
                "component_id": component_id,
                "health_score": 0,
                "status": "error",
                "error": str(e),
            }

    async def get_active_operations(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get currently active operations.

        Args:
            limit: Maximum number of operations to return

        Returns:
            List of active operations
        """
        try:
            recent_time = datetime.utcnow() - timedelta(minutes=5)

            # Get operations with recent activity
            operations = (
                self.db.query(
                    DebugEvent.correlation_id,
                    func.min(DebugEvent.timestamp).label("start_time"),
                    func.max(DebugEvent.timestamp).label("last_activity"),
                    func.count(DebugEvent.id).label("event_count"),
                    func.sum(
                        case(
                            (DebugEvent.level.in_(["ERROR", "CRITICAL"]), 1),
                            else_=0
                        )
                    ).label("error_count"),
                )
                .filter(DebugEvent.timestamp >= recent_time)
                .group_by(DebugEvent.correlation_id)
                .order_by(func.max(DebugEvent.timestamp).desc())
                .limit(limit)
                .all()
            )

            result = []
            for correlation_id, start_time, last_activity, event_count, error_count in operations:
                # Determine status
                if error_count > 0:
                    status = "errors"
                elif (datetime.utcnow() - last_activity).total_seconds() > 60:
                    status = "stalled"
                else:
                    status = "active"

                result.append({
                    "correlation_id": correlation_id,
                    "start_time": start_time.isoformat() if start_time else None,
                    "last_activity": last_activity.isoformat() if last_activity else None,
                    "event_count": event_count,
                    "error_count": error_count or 0,
                    "status": status,
                })

            return result

        except Exception as e:
            self.logger.error("Failed to get active operations", error=str(e))
            return []

    async def get_error_rate_by_component(
        self,
        time_range: str = "last_1h",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get error rates grouped by component.

        Args:
            time_range: Time range for analysis
            limit: Maximum components to return

        Returns:
            List of components with error rates
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Get error counts by component
            error_stats = (
                self.db.query(
                    DebugEvent.component_type,
                    DebugEvent.component_id,
                    func.count(DebugEvent.id).label("total_events"),
                    func.sum(
                        case(
                            (DebugEvent.level.in_(["ERROR", "CRITICAL"]), 1),
                            else_=0
                        )
                    ).label("error_count"),
                )
                .filter(DebugEvent.timestamp >= time_filter)
                .group_by(DebugEvent.component_type, DebugEvent.component_id)
                .having(func.count(DebugEvent.id) > 10)  # At least 10 events
                .all()
            )

            # Calculate error rates and sort
            components_with_rates = []
            for comp_type, comp_id, total, errors in error_stats:
                error_rate = (errors / total * 100) if total > 0 else 0
                components_with_rates.append({
                    "component_type": comp_type,
                    "component_id": comp_id,
                    "total_events": total,
                    "error_count": errors or 0,
                    "error_rate": error_rate,
                })

            # Sort by error rate (descending)
            components_with_rates.sort(key=lambda x: x["error_rate"], reverse=True)

            return components_with_rates[:limit]

        except Exception as e:
            self.logger.error("Failed to get error rates", error=str(e))
            return []

    async def get_throughput_metrics(
        self,
        time_range: str = "last_1h",
    ) -> Dict[str, Any]:
        """
        Get throughput metrics for the system.

        Args:
            time_range: Time range for analysis

        Returns:
            Throughput metrics
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Get throughput by component type
            throughput_by_type = (
                self.db.query(
                    DebugEvent.component_type,
                    func.count(DebugEvent.id).label("event_count"),
                )
                .filter(DebugEvent.timestamp >= time_filter)
                .group_by(DebugEvent.component_type)
                .all()
            )

            # Calculate events per minute
            duration_minutes = self._get_duration_minutes(time_range)

            throughput = {}
            total_throughput = 0

            for comp_type, count in throughput_by_type:
                per_minute = count / duration_minutes if duration_minutes > 0 else 0
                throughput[comp_type] = {
                    "total_events": count,
                    "events_per_minute": per_minute,
                }
                total_throughput += count

            return {
                "throughput_by_component": throughput,
                "total_events": total_throughput,
                "events_per_minute": total_throughput / duration_minutes if duration_minutes > 0 else 0,
                "time_range": time_range,
            }

        except Exception as e:
            self.logger.error("Failed to get throughput metrics", error=str(e))
            return {}

    async def get_insight_summary(
        self,
        time_range: str = "last_24h",
    ) -> Dict[str, Any]:
        """
        Get summary of recent insights.

        Args:
            time_range: Time range for analysis

        Returns:
            Insight summary
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Count insights by type and severity
            insights_by_type = (
                self.db.query(
                    DebugInsight.insight_type,
                    DebugInsight.severity,
                    func.count(DebugInsight.id).label("count"),
                )
                .filter(DebugInsight.generated_at >= time_filter)
                .group_by(DebugInsight.insight_type, DebugInsight.severity)
                .all()
            )

            summary = {
                "by_type": defaultdict(lambda: defaultdict(int)),
                "total_count": 0,
                "resolved_count": 0,
                "unresolved_count": 0,
            }

            for insight_type, severity, count in insights_by_type:
                summary["by_type"][insight_type][severity] = count
                summary["total_count"] += count

            # Get resolved vs unresolved
            resolved = (
                self.db.query(func.count(DebugInsight.id))
                .filter(
                    and_(
                        DebugInsight.generated_at >= time_filter,
                        DebugInsight.resolved == True,
                    )
                )
                .scalar()
            )

            unresolved = (
                self.db.query(func.count(DebugInsight.id))
                .filter(
                    and_(
                        DebugInsight.generated_at >= time_filter,
                        DebugInsight.resolved == False,
                    )
                )
                .scalar()
            )

            summary["resolved_count"] = resolved or 0
            summary["unresolved_count"] = unresolved or 0

            return dict(summary)

        except Exception as e:
            self.logger.error("Failed to get insight summary", error=str(e))
            return {}

    async def _get_component_breakdown(
        self,
        time_filter: datetime,
    ) -> Dict[str, Dict[str, int]]:
        """Get component health breakdown."""
        try:
            # Get stats by component type
            component_stats = (
                self.db.query(
                    DebugEvent.component_type,
                    func.count(DebugEvent.id).label("total"),
                    func.sum(
                        case(
                            (DebugEvent.level.in_(["ERROR", "CRITICAL"]), 1),
                            else_=0
                        )
                    ).label("errors"),
                )
                .filter(DebugEvent.timestamp >= time_filter)
                .group_by(DebugEvent.component_type)
                .all()
            )

            breakdown = {}
            for comp_type, total, errors in component_stats:
                health_score = 100
                if total > 0:
                    error_rate = (errors or 0) / total
                    health_score = max(0, 100 - (error_rate * 100))

                breakdown[comp_type] = {
                    "total_events": total,
                    "error_events": errors or 0,
                    "health_score": health_score,
                }

            return breakdown

        except Exception as e:
            self.logger.error("Failed to get component breakdown", error=str(e))
            return {}

    def _parse_time_range(self, time_range: str) -> datetime:
        """Parse time range string to datetime."""
        now = datetime.utcnow()

        if time_range == "last_1h":
            return now - timedelta(hours=1)
        elif time_range == "last_24h":
            return now - timedelta(hours=24)
        elif time_range == "last_7d":
            return now - timedelta(days=7)
        else:
            return now - timedelta(hours=1)

    def _get_duration_minutes(self, time_range: str) -> float:
        """Get duration in minutes from time range string."""
        if time_range == "last_1h":
            return 60
        elif time_range == "last_24h":
            return 1440
        elif time_range == "last_7d":
            return 10080
        else:
            return 60
