"""
Debug Alerting Engine for AI Debug System

Provides intelligent alerting with:
- Threshold-based alerts (error rate >50%, latency >5s)
- Anomaly detection
- Smart alert grouping to reduce noise
- Integration with WebSocket notifications
- Alert history and deduplication

Example:
    alerting = DebugAlertingEngine(db_session)

    # Check and generate alerts
    alerts = await alerting.check_system_health()

    # Get active alerts
    active = await alerting.get_active_alerts()
"""

import asyncio
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugAlert,
    DebugEventType,
    DebugInsightSeverity,
)
from core.structured_logger import StructuredLogger


class DebugAlertingEngine:
    """
    Intelligent alerting engine for debug system.

    Generates alerts based on thresholds, anomalies, and patterns
    while reducing noise through smart grouping and deduplication.
    """

    def __init__(
        self,
        db_session: Session,
        error_rate_threshold: float = 0.5,  # 50%
        latency_threshold_ms: float = 5000,
        alert_cooldown_minutes: int = 15,
    ):
        """
        Initialize alerting engine.

        Args:
            db_session: SQLAlchemy database session
            error_rate_threshold: Error rate threshold for alerts (0-1)
            latency_threshold_ms: Latency threshold in milliseconds
            alert_cooldown_minutes: Cooldown period between similar alerts
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session
        self.error_rate_threshold = error_rate_threshold
        self.latency_threshold_ms = latency_threshold_ms
        self.alert_cooldown_minutes = alert_cooldown_minutes

    async def check_system_health(self) -> List[DebugInsight]:
        """
        Check system health and generate alerts if needed.

        Returns:
            List of alert insights
        """
        alerts = []

        try:
            # Check error rates
            error_alerts = await self._check_error_rates()
            alerts.extend(error_alerts)

            # Check performance
            perf_alerts = await self._check_performance()
            alerts.extend(perf_alerts)

            # Check for anomalies
            anomaly_alerts = await self._check_anomalies()
            alerts.extend(anomaly_alerts)

            return alerts

        except Exception as e:
            self.logger.error("Failed to check system health", error=str(e))
            return []

    async def check_component_health(
        self,
        component_type: str,
        component_id: str,
    ) -> Optional[DebugInsight]:
        """
        Check health of a specific component and alert if needed.

        Args:
            component_type: Component type
            component_id: Component ID

        Returns:
            Alert insight or None
        """
        try:
            time_filter = datetime.utcnow() - timedelta(hours=1)

            # Get error rate
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

            if total_events and total_events >= 10:  # Minimum sample size
                error_rate = (error_events or 0) / total_events

                if error_rate >= self.error_rate_threshold:
                    # Check if we recently alerted on this
                    recent_alert = await self._check_recent_alert(
                        component_type=component_type,
                        component_id=component_id,
                        alert_type="high_error_rate",
                    )

                    if not recent_alert:
                        return DebugInsight(
                            insight_type=DebugInsightType.ERROR.value,
                            severity=DebugInsightSeverity.CRITICAL.value,
                            title=f"High error rate alert: {component_type}/{component_id}",
                            description=f"Error rate {error_rate*100:.1f}% exceeds threshold {self.error_rate_threshold*100:.0f}%",
                            summary=f"Error rate {error_rate*100:.1f}% requires attention",
                            evidence={
                                "component_type": component_type,
                                "component_id": component_id,
                                "error_rate": error_rate,
                                "threshold": self.error_rate_threshold,
                                "total_events": total_events,
                                "error_events": error_events or 0,
                            },
                            confidence_score=0.95,
                            suggestions=[
                                "Investigate error logs immediately",
                                "Check component status",
                                "Consider scaling up if under load",
                                "Review recent deployments",
                            ],
                            scope="component",
                            affected_components=[{"type": component_type, "id": component_id}],
                            generated_at=datetime.utcnow(),
                        )

            return None

        except Exception as e:
            self.logger.error(
                "Failed to check component health",
                component_type=component_type,
                component_id=component_id,
                error=str(e),
            )
            return None

    async def get_active_alerts(
        self,
        limit: int = 50,
    ) -> List[DebugInsight]:
        """
        Get currently active alerts.

        Args:
            limit: Maximum alerts to return

        Returns:
            List of active alert insights
        """
        try:
            # Get unresolved critical and warning insights from last 24h
            time_filter = datetime.utcnow() - timedelta(hours=24)

            alerts = (
                self.db.query(DebugInsight)
                .filter(
                    and_(
                        DebugInsight.severity.in_(
                            [DebugInsightSeverity.CRITICAL.value, DebugInsightSeverity.WARNING.value]
                        ),
                        DebugInsight.resolved == False,
                        DebugInsight.generated_at >= time_filter,
                    )
                )
                .order_by(DebugInsight.generated_at.desc())
                .limit(limit)
                .all()
            )

            return alerts

        except Exception as e:
            self.logger.error("Failed to get active alerts", error=str(e))
            return []

    async def _check_error_rates(self) -> List[DebugInsight]:
        """Check error rates across all components."""
        alerts = []

        try:
            time_filter = datetime.utcnow() - timedelta(hours=1)

            # Get error rates by component
            error_stats = (
                self.db.query(
                    DebugEvent.component_type,
                    DebugEvent.component_id,
                    func.count(DebugEvent.id).label("total"),
                    func.sum(
                        func.case(
                            (DebugEvent.level.in_(["ERROR", "CRITICAL"]), 1),
                            else_=0
                        )
                    ).label("errors"),
                )
                .filter(DebugEvent.timestamp >= time_filter)
                .group_by(DebugEvent.component_type, DebugEvent.component_id)
                .having(func.count(DebugEvent.id) >= 10)  # Minimum sample size
                .all()
            )

            for comp_type, comp_id, total, errors in error_stats:
                error_rate = (errors or 0) / total

                if error_rate >= self.error_rate_threshold:
                    # Check for recent alert
                    recent_alert = await self._check_recent_alert(
                        component_type=comp_type,
                        component_id=comp_id,
                        alert_type="high_error_rate",
                    )

                    if not recent_alert:
                        alerts.append(
                            DebugInsight(
                                insight_type=DebugInsightType.ERROR.value,
                                severity=DebugInsightSeverity.CRITICAL.value,
                                title=f"High error rate alert: {comp_type}/{comp_id}",
                                description=f"Error rate {error_rate*100:.1f}% exceeds threshold",
                                summary=f"{errors}/{total} events were errors",
                                evidence={
                                    "component_type": comp_type,
                                    "component_id": comp_id,
                                    "error_rate": error_rate,
                                    "error_count": errors,
                                    "total_count": total,
                                },
                                confidence_score=0.95,
                                suggestions=[
                                    "Investigate immediately",
                                    "Check error logs",
                                    "Verify system status",
                                ],
                                scope="component",
                                affected_components=[{"type": comp_type, "id": comp_id}],
                                generated_at=datetime.utcnow(),
                            )
                        )

        except Exception as e:
            self.logger.error("Failed to check error rates", error=str(e))

        return alerts

    async def _check_performance(self) -> List[DebugInsight]:
        """Check performance metrics and generate alerts."""
        alerts = []

        try:
            time_filter = datetime.utcnow() - timedelta(hours=1)

            # Find slow operations
            slow_events = (
                self.db.query(DebugEvent)
                .filter(
                    and_(
                        DebugEvent.timestamp >= time_filter,
                        DebugEvent.data.isnot(None),
                    )
                )
                .all()
            )

            # Group by component and check for slow operations
            component_durations = defaultdict(list)
            for event in slow_events:
                if event.data and "duration_ms" in event.data:
                    key = f"{event.component_type}/{event.component_id}"
                    component_durations[key].append(event.data["duration_ms"])

            # Check for components exceeding threshold
            for comp_key, durations in component_durations.items():
                # Check 95th percentile
                durations.sort()
                p95_index = int(len(durations) * 0.95)
                p95 = durations[p95_index] if durations else 0

                if p95 > self.latency_threshold_ms:
                    comp_type, comp_id = comp_key.split("/")

                    # Check for recent alert
                    recent_alert = await self._check_recent_alert(
                        component_type=comp_type,
                        component_id=comp_id,
                        alert_type="high_latency",
                    )

                    if not recent_alert:
                        alerts.append(
                            DebugInsight(
                                insight_type=DebugInsightType.PERFORMANCE.value,
                                severity=DebugInsightSeverity.WARNING.value,
                                title=f"High latency alert: {comp_key}",
                                description=f"95th percentile latency {p95:.0f}ms exceeds threshold {self.latency_threshold_ms}ms",
                                summary=f"P95 latency {p95:.0f}ms requires attention",
                                evidence={
                                    "component_type": comp_type,
                                    "component_id": comp_id,
                                    "p95_latency_ms": p95,
                                    "threshold_ms": self.latency_threshold_ms,
                                    "sample_count": len(durations),
                                },
                                confidence_score=0.90,
                                suggestions=[
                                    "Profile hot paths",
                                    "Check for blocking operations",
                                    "Review resource utilization",
                                ],
                                scope="component",
                                affected_components=[{"type": comp_type, "id": comp_id}],
                                generated_at=datetime.utcnow(),
                            )
                        )

        except Exception as e:
            self.logger.error("Failed to check performance", error=str(e))

        return alerts

    async def _check_anomalies(self) -> List[DebugInsight]:
        """Check for anomalies in system behavior."""
        alerts = []

        try:
            time_filter = datetime.utcnow() - timedelta(hours=1)

            # Check for sudden spike in error rate
            previous_time = datetime.utcnow() - timedelta(hours=2)

            current_errors = (
                self.db.query(func.count(DebugEvent.id))
                .filter(
                    and_(
                        DebugEvent.timestamp >= time_filter,
                        DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                    )
                )
                .scalar() or 0
            )

            previous_errors = (
                self.db.query(func.count(DebugEvent.id))
                .filter(
                    and_(
                        DebugEvent.timestamp >= previous_time,
                        DebugEvent.timestamp < time_filter,
                        DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                    )
                )
                .scalar() or 0
            )

            # Check for 3x spike
            if previous_errors > 0 and current_errors > previous_errors * 3:
                # Check for recent alert
                recent_alert = await self._check_recent_alert(
                    alert_type="error_spike",
                )

                if not recent_alert:
                    alerts.append(
                        DebugInsight(
                            insight_type=DebugInsightType.ANOMALY.value,
                            severity=DebugInsightSeverity.CRITICAL.value,
                            title="Error rate spike detected",
                            description=f"Error rate increased by {(current_errors/previous_errors - 1)*100:.0f}% "
                            f"({previous_errors} → {current_errors} errors)",
                            summary=f"Error count spiked {current_errors/previous_errors:.1f}x",
                            evidence={
                                "current_errors": current_errors,
                                "previous_errors": previous_errors,
                                "spike_factor": current_errors / previous_errors,
                            },
                            confidence_score=0.85,
                            suggestions=[
                                "Investigate system-wide issues",
                                "Check for deployment failures",
                                "Review external dependencies",
                                "Consider emergency procedures if spike continues",
                            ],
                            scope="system",
                            affected_components=[],
                            generated_at=datetime.utcnow(),
                        )
                    )

        except Exception as e:
            self.logger.error("Failed to check anomalies", error=str(e))

        return alerts

    async def _check_recent_alert(
        self,
        component_type: Optional[str] = None,
        component_id: Optional[str] = None,
        alert_type: str = "generic",
    ) -> bool:
        """
        Check if there was a recent alert for the same issue.

        Implements deduplication to reduce alert noise.

        Args:
            component_type: Component type
            component_id: Component ID
            alert_type: Type of alert

        Returns:
            True if recent alert exists, False otherwise
        """
        try:
            cooldown_time = datetime.utcnow() - timedelta(minutes=self.alert_cooldown_minutes)

            query = self.db.query(DebugInsight).filter(
                and_(
                    DebugInsight.generated_at >= cooldown_time,
                    DebugInsight.resolved == False,
                )
            )

            # Add filters based on provided parameters
            if component_type and component_id:
                # Check if this component is in affected_components
                # This is a simplified check - in production, use JSON array queries
                insights = query.all()
                for insight in insights:
                    if insight.affected_components:
                        for comp in insight.affected_components:
                            if (
                                comp.get("type") == component_type
                                and comp.get("id") == component_id
                            ):
                                return True
                return False
            else:
                # Just check if any alert exists
                return query.first() is not None

        except Exception as e:
            self.logger.error("Failed to check recent alerts", error=str(e))
            return False

    async def group_similar_alerts(
        self,
        alerts: List[DebugInsight],
    ) -> List[List[DebugInsight]]:
        """
        Group similar alerts together to reduce noise.

        Args:
            alerts: List of alerts to group

        Returns:
            List of alert groups
        """
        try:
            groups = []
            used = set()

            for i, alert in enumerate(alerts):
                if i in used:
                    continue

                group = [alert]
                used.add(i)

                # Find similar alerts
                for j, other in enumerate(alerts):
                    if j in used:
                        continue

                    if self._alerts_are_similar(alert, other):
                        group.append(other)
                        used.add(j)

                groups.append(group)

            return groups

        except Exception as e:
            self.logger.error("Failed to group alerts", error=str(e))
            return [[alert] for alert in alerts]

    def _alerts_are_similar(
        self,
        alert1: DebugInsight,
        alert2: DebugInsight,
    ) -> bool:
        """
        Check if two alerts are similar enough to group together.

        Args:
            alert1: First alert
            alert2: Second alert

        Returns:
            True if similar, False otherwise
        """
        # Same insight type and severity
        if alert1.insight_type != alert2.insight_type:
            return False

        if alert1.severity != alert2.severity:
            return False

        # Similar titles (simple check)
        title1_words = set(alert1.title.lower().split())
        title2_words = set(alert2.title.lower().split())

        overlap = title1_words & title2_words
        if len(overlap) >= 3:  # At least 3 words in common
            return True

        return False

    async def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        description: str,
        summary: str,
        evidence: Dict[str, Any],
        suggestions: List[str],
        affected_components: List[Dict[str, str]],
        scope: str = "component",
    ) -> DebugInsight:
        """
        Create a new alert.

        Args:
            alert_type: Type of alert
            severity: Alert severity
            title: Alert title
            description: Full description
            summary: One-line summary
            evidence: Evidence data
            suggestions: Resolution suggestions
            affected_components: List of affected components
            scope: Alert scope

        Returns:
            Created alert insight
        """
        alert = DebugInsight(
            insight_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            summary=summary,
            evidence=evidence,
            confidence_score=1.0,
            suggestions=suggestions,
            scope=scope,
            affected_components=affected_components,
            generated_at=datetime.utcnow(),
        )

        self.db.add(alert)
        self.db.commit()

        self.logger.info(
            "Alert created",
            alert_type=alert_type,
            severity=severity,
            title=title,
        )

        return alert
