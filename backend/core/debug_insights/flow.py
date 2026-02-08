"""
Execution Flow Insights for AI Debug System

Analyzes execution flow across components and detects:
- Operation tracing across components
- Blocking operations
- Deadlocks and race conditions
- Workflow execution patterns

Example insights:
- "Workflow waiting 30s for browser automation on session-789"
- "Agent-123 blocked on external API rate limit"
- "Circular dependency detected between components"
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugInsightType,
    DebugInsightSeverity,
)
from core.structured_logger import StructuredLogger


class FlowInsightGenerator:
    """
    Generates insights about execution flow through the system.

    Tracks operations as they flow through components and identifies
    bottlenecks, blocking operations, and flow anomalies.
    """

    def __init__(self, db_session: Session):
        """
        Initialize flow insight generator.

        Args:
            db_session: SQLAlchemy database session
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session

    async def trace_operation_flow(
        self,
        correlation_id: str,
    ) -> Optional[DebugInsight]:
        """
        Trace an operation's flow through the system.

        Analyzes how an operation moves through components and identifies
        any blocking or delay issues.

        Args:
            correlation_id: Operation correlation ID to trace

        Returns:
            Flow insight or None
        """
        try:
            # Get all events for this operation
            events = (
                self.db.query(DebugEvent)
                .filter(DebugEvent.correlation_id == correlation_id)
                .order_by(DebugEvent.timestamp)
                .all()
            )

            if not events:
                return None

            # Analyze the flow
            flow_analysis = await self._analyze_flow(events)

            if flow_analysis["blocked"]:
                return DebugInsight(
                    insight_type=DebugInsightType.FLOW.value,
                    severity=DebugInsightSeverity.WARNING.value,
                    title="Blocking operation detected",
                    description=f"Operation blocked for {flow_analysis['block_duration']:.1f}s",
                    summary=f"Operation waiting on {flow_analysis['blocking_component']}",
                    evidence={
                        "correlation_id": correlation_id,
                        "blocking_component": flow_analysis["blocking_component"],
                        "block_duration_seconds": flow_analysis["block_duration"],
                        "event_count": len(events),
                    },
                    confidence_score=0.88,
                    suggestions=[
                        f"Check {flow_analysis['blocking_component']} status",
                        "Review resource utilization",
                        "Investigate external dependencies",
                    ],
                    scope="component",
                    affected_components=[
                        {"type": e.component_type, "id": e.component_id} for e in events
                    ],
                    generated_at=datetime.utcnow(),
                )

            if flow_analysis["has_errors"]:
                return DebugInsight(
                    insight_type=DebugInsightType.FLOW.value,
                    severity=DebugInsightSeverity.ERROR.value,
                    title="Operation flow interrupted",
                    description=f"Operation encountered {flow_analysis['error_count']} errors during execution",
                    summary=f"{flow_analysis['error_count']} errors in operation flow",
                    evidence={
                        "correlation_id": correlation_id,
                        "error_count": flow_analysis["error_count"],
                        "error_messages": flow_analysis["error_messages"],
                        "components_touched": flow_analysis["components_touched"],
                    },
                    confidence_score=0.92,
                    suggestions=[
                        "Review error messages",
                        "Check component health",
                        "Retry operation with verbose logging",
                    ],
                    scope="component",
                    affected_components=[
                        {"type": e.component_type, "id": e.component_id} for e in events
                    ],
                    generated_at=datetime.utcnow(),
                )

            # Flow completed successfully
            return DebugInsight(
                insight_type=DebugInsightType.FLOW.value,
                severity=DebugInsightSeverity.INFO.value,
                title="Operation flow completed",
                description=f"Operation successfully flowed through {flow_analysis['components_touched']} components",
                summary=f"Flow completed in {flow_analysis['duration']:.1f}s",
                evidence={
                    "correlation_id": correlation_id,
                    "components_touched": flow_analysis["components_touched"],
                    "duration_seconds": flow_analysis["duration"],
                },
                confidence_score=0.95,
                scope="component",
                affected_components=[
                    {"type": e.component_type, "id": e.component_id} for e in events
                ],
                generated_at=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error(
                "Failed to trace operation flow",
                correlation_id=correlation_id,
                error=str(e),
            )
            return None

    async def detect_blocking_operations(
        self,
        component_type: str,
        component_id: str,
        time_range: str = "last_1h",
    ) -> List[DebugInsight]:
        """
        Detect operations that are blocking on this component.

        Args:
            component_type: Component type
            component_id: Component ID
            time_range: Time range to analyze

        Returns:
            List of flow insights about blocking operations
        """
        try:
            insights = []
            time_filter = self._parse_time_range(time_range)

            # Find operations with long execution times
            slow_operations = (
                self.db.query(
                    DebugEvent.correlation_id,
                    func.min(DebugEvent.timestamp).label("start_time"),
                    func.max(DebugEvent.timestamp).label("end_time"),
                )
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.timestamp >= time_filter,
                    )
                )
                .group_by(DebugEvent.correlation_id)
                .having(
                    func.julianday(func.max(DebugEvent.timestamp)) -
                    func.julianday(func.min(DebugEvent.timestamp)) > 0.0007  # ~60 seconds
                )
                .all()
            )

            for correlation_id, start_time, end_time in slow_operations:
                duration = (end_time - start_time).total_seconds() if (end_time and start_time) else 0

                insights.append(
                    DebugInsight(
                        insight_type=DebugInsightType.FLOW.value,
                        severity=DebugInsightSeverity.WARNING.value,
                        title=f"Long-running operation detected",
                        description=f"Operation {correlation_id} took {duration:.1f}s on {component_type}/{component_id}",
                        summary=f"Operation duration {duration:.1f}s exceeds threshold",
                        evidence={
                            "correlation_id": correlation_id,
                            "duration_seconds": duration,
                            "component_type": component_type,
                            "component_id": component_id,
                        },
                        confidence_score=0.85,
                        suggestions=[
                            "Profile the operation for bottlenecks",
                            "Check for external API calls",
                            "Review database query performance",
                            "Investigate resource contention",
                        ],
                        scope="component",
                        affected_components=[{"type": component_type, "id": component_id}],
                        generated_at=datetime.utcnow(),
                    )
                )

            return insights

        except Exception as e:
            self.logger.error(
                "Failed to detect blocking operations",
                component_type=component_type,
                component_id=component_id,
                error=str(e),
            )
            return []

    async def detect_deadlocks(
        self,
        time_range: str = "last_1h",
    ) -> List[DebugInsight]:
        """
        Detect potential deadlocks or circular dependencies.

        Args:
            time_range: Time range to analyze

        Returns:
            List of insights about potential deadlocks
        """
        try:
            insights = []
            time_filter = self._parse_time_range(time_range)

            # Look for operations that haven't completed in a long time
            # but have recent activity (still trying to complete)
            stuck_operations = (
                self.db.query(
                    DebugEvent.correlation_id,
                    func.min(DebugEvent.timestamp).label("first_seen"),
                    func.max(DebugEvent.timestamp).label("last_seen"),
                    func.count(DebugEvent.id).label("event_count"),
                )
                .filter(DebugEvent.timestamp >= time_filter)
                .group_by(DebugEvent.correlation_id)
                .having(
                    and_(
                        func.julianday(func.max(DebugEvent.timestamp)) -
                        func.julianday(func.min(DebugEvent.timestamp)) > 0.001,  # ~86 seconds
                        func.count(DebugEvent.id) > 10,  # Many retry attempts
                    )
                )
                .all()
            )

            for correlation_id, first_seen, last_seen, event_count in stuck_operations:
                duration = (last_seen - first_seen).total_seconds() if (last_seen and first_seen) else 0

                insights.append(
                    DebugInsight(
                        insight_type=DebugInsightType.FLOW.value,
                        severity=DebugInsightSeverity.CRITICAL.value,
                        title="Potential deadlock detected",
                        description=f"Operation {correlation_id} has been active for {duration:.1f}s "
                        f"with {event_count} events, suggesting a deadlock or retry loop",
                        summary=f"Operation stuck for {duration:.1f}s with {event_count} events",
                        evidence={
                            "correlation_id": correlation_id,
                            "duration_seconds": duration,
                            "event_count": event_count,
                            "first_seen": first_seen.isoformat() if first_seen else None,
                            "last_seen": last_seen.isoformat() if last_seen else None,
                        },
                        confidence_score=0.75,
                        suggestions=[
                            "Check for circular dependencies",
                            "Review lock acquisition order",
                            "Investigate resource contention",
                            "Consider timeout mechanisms",
                            "Manual intervention may be required",
                        ],
                        scope="distributed",
                        affected_components=[],
                        generated_at=datetime.utcnow(),
                    )
                )

            return insights

        except Exception as e:
            self.logger.error("Failed to detect deadlocks", error=str(e))
            return []

    async def analyze_workflow_patterns(
        self,
        time_range: str = "last_24h",
    ) -> List[DebugInsight]:
        """
        Analyze workflow execution patterns for systemic issues.

        Args:
            time_range: Time range to analyze

        Returns:
            List of insights about workflow patterns
        """
        try:
            insights = []
            time_filter = self._parse_time_range(time_range)

            # Find workflows with high failure rates
            workflow_stats = (
                self.db.query(
                    DebugEvent.component_id,
                    func.count(DebugEvent.id).label("total"),
                    func.sum(
                        func.case(
                            (DebugEvent.level.in_(["ERROR", "CRITICAL"]), 1),
                            else_=0
                        )
                    ).label("errors"),
                )
                .filter(
                    and_(
                        DebugEvent.component_type == "workflow",
                        DebugEvent.timestamp >= time_filter,
                    )
                )
                .group_by(DebugEvent.component_id)
                .having(func.count(DebugEvent.id) > 10)  # At least 10 executions
                .all()
            )

            for workflow_id, total, errors in workflow_stats:
                error_rate = errors / total if total > 0 else 0

                if error_rate > 0.3:  # 30% failure rate
                    insights.append(
                        DebugInsight(
                            insight_type=DebugInsightType.FLOW.value,
                            severity=DebugInsightSeverity.CRITICAL.value,
                            title=f"High failure rate for workflow {workflow_id}",
                            description=f"Workflow failing {error_rate*100:.1f}% of the time "
                            f"({errors}/{total} executions)",
                            summary=f"{error_rate*100:.1f}% failure rate requires attention",
                            evidence={
                                "workflow_id": workflow_id,
                                "total_executions": total,
                                "failed_executions": errors,
                                "error_rate": error_rate,
                            },
                            confidence_score=0.90,
                            suggestions=[
                                "Review workflow definition",
                                "Check integration dependencies",
                                "Analyze failure patterns",
                                "Consider rollback to stable version",
                            ],
                            scope="component",
                            affected_components=[{"type": "workflow", "id": workflow_id}],
                            generated_at=datetime.utcnow(),
                        )
                    )

            return insights

        except Exception as e:
            self.logger.error("Failed to analyze workflow patterns", error=str(e))
            return []

    async def _analyze_flow(self, events: List[DebugEvent]) -> Dict[str, Any]:
        """
        Analyze the flow of events through the system.

        Args:
            events: Ordered list of events

        Returns:
            Flow analysis dictionary
        """
        analysis = {
            "blocked": False,
            "block_duration": 0,
            "blocking_component": None,
            "has_errors": False,
            "error_count": 0,
            "error_messages": [],
            "components_touched": len(set((e.component_type, e.component_id) for e in events)),
            "duration": 0,
        }

        if not events:
            return analysis

        # Check for errors
        error_events = [e for e in events if e.level in ["ERROR", "CRITICAL"]]
        if error_events:
            analysis["has_errors"] = True
            analysis["error_count"] = len(error_events)
            analysis["error_messages"] = [e.message for e in error_events if e.message]

        # Calculate duration
        if events[0].timestamp and events[-1].timestamp:
            analysis["duration"] = (events[-1].timestamp - events[0].timestamp).total_seconds()

        # Check for blocking (long gaps between events)
        if len(events) > 1:
            for i in range(len(events) - 1):
                if events[i].timestamp and events[i + 1].timestamp:
                    gap = (events[i + 1].timestamp - events[i].timestamp).total_seconds()
                    if gap > 30:  # 30 second gap
                        analysis["blocked"] = True
                        analysis["block_duration"] = gap
                        analysis["blocking_component"] = f"{events[i].component_type}/{events[i].component_id}"
                        break

        return analysis

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
