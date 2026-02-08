"""
Debug Insight Engine for Atom Platform

Generates abstracted insights from raw debug events.
Provides AI agents with high-level understanding without processing raw logs.

Features:
- Log aggregation by component (agent, browser, workflow)
- State diff detection ("Data X saved on Node 1 but not Node 2")
- Error pattern detection and causality analysis
- Basic anomaly detection
- Insight confidence scoring
"""

import asyncio
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugStateSnapshot,
    DebugEventType,
    DebugInsightType,
    DebugInsightSeverity,
)
from core.structured_logger import StructuredLogger


# Configuration
DEBUG_INSIGHT_CONFIDENCE_THRESHOLD = float(os.getenv("DEBUG_INSIGHT_CONFIDENCE_THRESHOLD", "0.7"))
DEBUG_INSIGHT_AUTO_GENERATE = os.getenv("DEBUG_INSIGHT_AUTO_GENERATE", "true").lower() == "true"
DEBUG_ANOMALY_DETECTION_ENABLED = os.getenv("DEBUG_ANOMALY_DETECTION_ENABLED", "true").lower() == "true"


class DebugInsightEngine:
    """
    Insight generation engine for debug data.

    Analyzes raw debug events and generates high-level insights
    for AI agents and human operators.

    Example:
        engine = DebugInsightEngine(db_session)

        # Generate insights from events
        insights = await engine.generate_insights_from_events(
            correlation_id="corr-456",
            component_type="agent",
        )

        # Analyze state consistency
        consistency_insight = await engine.analyze_state_consistency(
            operation_id="op-789",
            component_ids=["node-1", "node-2", "node-3"],
        )

        # Detect error patterns
        error_insights = await engine.detect_error_patterns(
            time_range="last_1h",
        )
    """

    def __init__(self, db_session: Session):
        """
        Initialize insight engine.

        Args:
            db_session: SQLAlchemy database session
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session

    # ========================================================================
    # Main Insight Generation
    # ========================================================================

    async def generate_insights_from_events(
        self,
        correlation_id: Optional[str] = None,
        component_type: Optional[str] = None,
        component_id: Optional[str] = None,
        time_range: Optional[str] = None,
    ) -> List[DebugInsight]:
        """
        Generate insights from debug events.

        Args:
            correlation_id: Filter by correlation ID
            component_type: Filter by component type
            component_id: Filter by component ID
            time_range: Time range filter (last_1h, last_24h, last_7d)

        Returns:
            List of generated insights
        """
        try:
            # Fetch events
            events = await self._query_events(
                correlation_id=correlation_id,
                component_type=component_type,
                component_id=component_id,
                time_range=time_range,
            )

            if not events:
                return []

            insights = []

            # Generate different types of insights
            # 1. Consistency insights
            consistency_insights = await self._generate_consistency_insights(events)
            insights.extend(consistency_insights)

            # 2. Flow insights
            flow_insights = await self._generate_flow_insights(events)
            insights.extend(flow_insights)

            # 3. Error insights
            error_insights = await self._generate_error_insights(events)
            insights.extend(error_insights)

            # 4. Performance insights
            performance_insights = await self._generate_performance_insights(events)
            insights.extend(performance_insights)

            # 5. Anomaly insights
            if DEBUG_ANOMALY_DETECTION_ENABLED:
                anomaly_insights = await self._generate_anomaly_insights(events)
                insights.extend(anomaly_insights)

            # Store insights
            for insight in insights:
                if insight.confidence_score >= DEBUG_INSIGHT_CONFIDENCE_THRESHOLD:
                    self.db.add(insight)

            self.db.commit()

            return insights

        except Exception as e:
            self.logger.error(
                "Failed to generate insights",
                error=str(e),
            )
            return []

    # ========================================================================
    # Consistency Insights
    # ========================================================================

    async def analyze_state_consistency(
        self,
        operation_id: str,
        component_ids: List[str],
        component_type: str = "agent",
    ) -> Optional[DebugInsight]:
        """
        Analyze state consistency across components.

        Detects if data is consistent across all components involved in an operation.

        Args:
            operation_id: Operation correlation ID
            component_ids: List of component IDs to compare
            component_type: Component type

        Returns:
            Consistency insight or None
        """
        try:
            # Fetch state snapshots for all components
            snapshots = (
                self.db.query(DebugStateSnapshot)
                .filter(
                    and_(
                        DebugStateSnapshot.operation_id == operation_id,
                        DebugStateSnapshot.component_type == component_type,
                        DebugStateSnapshot.component_id.in_(component_ids),
                    )
                )
                .order_by(DebugStateSnapshot.captured_at.desc())
                .all()
            )

            if not snapshots:
                return None

            # Group by component
            snapshots_by_component = defaultdict(list)
            for snapshot in snapshots:
                snapshots_by_component[snapshot.component_id].append(snapshot)

            # Check if all components have snapshots
            missing_components = set(component_ids) - set(snapshots_by_component.keys())
            if missing_components:
                return DebugInsight(
                    insight_type=DebugInsightType.CONSISTENCY.value,
                    severity=DebugInsightSeverity.WARNING.value,
                    title="Incomplete state coverage",
                    description=f"State snapshots missing for {len(missing_components)} components",
                    summary=f"{len(missing_components)} of {len(component_ids)} components have no state data",
                    evidence={"missing_components": list(missing_components)},
                    confidence_score=0.95,
                    suggestions=[
                        "Check if components are running",
                        "Verify state collection is enabled",
                    ],
                    scope="distributed",
                    affected_components=[
                        {"type": component_type, "id": comp_id}
                        for comp_id in missing_components
                    ],
                    generated_at=datetime.utcnow(),
                )

            # Compare latest state across components
            latest_snapshots = {
                comp_id: snapshots[0]
                for comp_id, snapshots in snapshots_by_component.items()
            }

            # Check for state differences
            inconsistencies = []
            for key in latest_snapshots[component_ids[0]].state_data.keys():
                values = [
                    snapshot.state_data.get(key)
                    for snapshot in latest_snapshots.values()
                ]
                if len(set(str(v) for v in values)) > 1:
                    inconsistencies.append(
                        {
                            "key": key,
                            "values": {
                                comp_id: snapshot.state_data.get(key)
                                for comp_id, snapshot in latest_snapshots.items()
                            },
                        }
                    )

            if inconsistencies:
                return DebugInsight(
                    insight_type=DebugInsightType.CONSISTENCY.value,
                    severity=DebugInsightSeverity.WARNING.value,
                    title="State inconsistency detected",
                    description=f"Found {len(inconsistencies)} inconsistent state values across components",
                    summary=f"State data differs across {len(component_ids)} components for {len(inconsistencies)} keys",
                    evidence={"inconsistencies": inconsistencies},
                    confidence_score=0.90,
                    suggestions=[
                        "Check replication mechanisms",
                        "Verify synchronization logic",
                        "Review component update timestamps",
                    ],
                    scope="distributed",
                    affected_components=[
                        {"type": component_type, "id": comp_id} for comp_id in component_ids
                    ],
                    generated_at=datetime.utcnow(),
                )

            # All consistent
            return DebugInsight(
                insight_type=DebugInsightType.CONSISTENCY.value,
                severity=DebugInsightSeverity.INFO.value,
                title="State consistent across all components",
                description=f"State data is consistent across all {len(component_ids)} components",
                summary=f"All {len(component_ids)} components have identical state",
                confidence_score=1.0,
                scope="distributed",
                affected_components=[
                    {"type": component_type, "id": comp_id} for comp_id in component_ids
                ],
                generated_at=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error(
                "Failed to analyze state consistency",
                operation_id=operation_id,
                error=str(e),
            )
            return None

    async def _generate_consistency_insights(
        self,
        events: List[DebugEvent],
    ) -> List[DebugInsight]:
        """Generate consistency insights from events."""
        insights = []

        try:
            # Group events by correlation
            events_by_correlation = defaultdict(list)
            for event in events:
                events_by_correlation[event.correlation_id].append(event)

            # Analyze each operation for consistency
            for correlation_id, correlation_events in events_by_correlation.items():
                # Check if all components have events
                components = set((e.component_type, e.component_id) for e in correlation_events)

                # Look for state snapshot events
                state_snapshots = [e for e in correlation_events if e.event_type == DebugEventType.STATE_SNAPSHOT.value]

                if state_snapshots:
                    # Analyze state consistency
                    # This is a simplified check - in production, use analyze_state_consistency
                    for snapshot in state_snapshots:
                        if snapshot.data:
                            insights.append(
                                DebugInsight(
                                    insight_type=DebugInsightType.CONSISTENCY.value,
                                    severity=DebugInsightSeverity.INFO.value,
                                    title=f"State snapshot captured for {snapshot.component_type}/{snapshot.component_id}",
                                    description=f"Component state captured at {snapshot.timestamp}",
                                    summary=f"State data available for {snapshot.component_type}",
                                    evidence={"snapshot_id": snapshot.id},
                                    confidence_score=0.85,
                                    suggestions=["Review state data for consistency"],
                                    scope="component",
                                    affected_components=[{"type": snapshot.component_type, "id": snapshot.component_id}],
                                    generated_at=datetime.utcnow(),
                                )
                            )

        except Exception as e:
            self.logger.error("Failed to generate consistency insights", error=str(e))

        return insights

    # ========================================================================
    # Flow Insights
    # ========================================================================

    async def _generate_flow_insights(
        self,
        events: List[DebugEvent],
    ) -> List[DebugInsight]:
        """Generate flow insights from events."""
        insights = []

        try:
            # Group events by correlation
            events_by_correlation = defaultdict(list)
            for event in events:
                events_by_correlation[event.correlation_id].append(event)

            # Analyze each operation flow
            for correlation_id, correlation_events in events_by_correlation.items():
                # Sort by timestamp
                correlation_events.sort(key=lambda e: e.timestamp or datetime.min)

                # Check for incomplete operations
                error_events = [e for e in correlation_events if e.level == "ERROR"]
                if error_events:
                    insights.append(
                        DebugInsight(
                            insight_type=DebugInsightType.FLOW.value,
                            severity=DebugInsightSeverity.WARNING.value,
                            title="Operation flow interrupted",
                            description=f"Operation {correlation_id} encountered {len(error_events)} errors",
                            summary=f"{len(error_events)} errors in operation flow",
                            evidence={
                                "correlation_id": correlation_id,
                                "error_count": len(error_events),
                                "error_messages": [e.message for e in error_events],
                            },
                            confidence_score=0.95,
                            suggestions=[
                                "Review error messages",
                                "Check component health",
                                "Retry operation",
                            ],
                            scope="component",
                            affected_components=[
                                {
                                    "type": e.component_type,
                                    "id": e.component_id,
                                }
                                for e in error_events
                            ],
                            generated_at=datetime.utcnow(),
                        )
                    )

        except Exception as e:
            self.logger.error("Failed to generate flow insights", error=str(e))

        return insights

    # ========================================================================
    # Error Insights
    # ========================================================================

    async def _generate_error_insights(
        self,
        events: List[DebugEvent],
    ) -> List[DebugInsight]:
        """Generate error insights from events."""
        insights = []

        try:
            # Find all error events
            error_events = [e for e in events if e.level in ["ERROR", "CRITICAL"]]

            if not error_events:
                return insights

            # Group by error pattern
            error_patterns = defaultdict(list)
            for event in error_events:
                # Create pattern key from message and component
                pattern_key = f"{event.component_type}:{event.message[:50]}"
                error_patterns[pattern_key].append(event)

            # Generate insights for repeated errors
            for pattern, pattern_events in error_patterns.items():
                if len(pattern_events) > 1:
                    insights.append(
                        DebugInsight(
                            insight_type=DebugInsightType.ERROR.value,
                            severity=DebugInsightSeverity.CRITICAL.value
                            if any(e.level == "CRITICAL" for e in pattern_events)
                            else DebugInsightSeverity.WARNING.value,
                            title=f"Repeated error pattern: {pattern_events[0].message[:50]}",
                            description=f"Same error occurred {len(pattern_events)} times",
                            summary=f"Error pattern repeated {len(pattern_events)} times across {len(set(e.component_id for e in pattern_events))} components",
                            evidence={
                                "pattern": pattern,
                                "occurrences": len(pattern_events),
                                "first_occurrence": pattern_events[0].timestamp.isoformat()
                                if pattern_events[0].timestamp
                                else None,
                                "last_occurrence": pattern_events[-1].timestamp.isoformat()
                                if pattern_events[-1].timestamp
                                else None,
                            },
                            confidence_score=0.90,
                            suggestions=[
                                "Review root cause",
                                "Implement error handling",
                                "Add monitoring for this error",
                            ],
                            scope="distributed",
                            affected_components=[
                                {"type": e.component_type, "id": e.component_id}
                                for e in pattern_events
                            ],
                            generated_at=datetime.utcnow(),
                        )
                    )

        except Exception as e:
            self.logger.error("Failed to generate error insights", error=str(e))

        return insights

    # ========================================================================
    # Performance Insights
    # ========================================================================

    async def _generate_performance_insights(
        self,
        events: List[DebugEvent],
    ) -> List[DebugInsight]:
        """Generate performance insights from events."""
        insights = []

        try:
            # Look for performance-related metadata
            slow_operations = []
            for event in events:
                if event.data and "duration_ms" in event.data:
                    duration = event.data["duration_ms"]
                    if duration > 5000:  # 5 second threshold
                        slow_operations.append(
                            {
                                "event": event,
                                "duration": duration,
                            }
                        )

            if slow_operations:
                insights.append(
                    DebugInsight(
                        insight_type=DebugInsightType.PERFORMANCE.value,
                        severity=DebugInsightSeverity.WARNING.value,
                        title=f"Slow operations detected",
                        description=f"Found {len(slow_operations)} operations exceeding 5s threshold",
                        summary=f"{len(slow_operations)} slow operations detected",
                        evidence={
                            "slow_operations": [
                                {
                                    "component": f"{op['event'].component_type}/{op['event'].component_id}",
                                    "duration_ms": op["duration"],
                                    "message": op["event"].message,
                                }
                                for op in slow_operations[:10]  # Limit to 10 examples
                            ]
                        },
                        confidence_score=0.85,
                        suggestions=[
                            "Profile slow operations",
                            "Optimize database queries",
                            "Add caching",
                            "Scale resources",
                        ],
                        scope="component",
                        affected_components=[
                            {"type": op["event"].component_type, "id": op["event"].component_id}
                            for op in slow_operations
                        ],
                        generated_at=datetime.utcnow(),
                    )
                )

        except Exception as e:
            self.logger.error("Failed to generate performance insights", error=str(e))

        return insights

    # ========================================================================
    # Anomaly Insights
    # ========================================================================

    async def _generate_anomaly_insights(
        self,
        events: List[DebugEvent],
    ) -> List[DebugInsight]:
        """Generate anomaly insights from events."""
        insights = []

        try:
            # Simple anomaly detection: event volume spikes
            events_by_minute = defaultdict(int)
            for event in events:
                if event.timestamp:
                    minute_key = event.timestamp.strftime("%Y-%m-%d %H:%M")
                    events_by_minute[minute_key] += 1

            if len(events_by_minute) > 1:
                avg_events_per_minute = sum(events_by_minute.values()) / len(events_by_minute)

                # Look for spikes (3x average)
                spikes = [
                    (minute, count)
                    for minute, count in events_by_minute.items()
                    if count > avg_events_per_minute * 3
                ]

                if spikes:
                    insights.append(
                        DebugInsight(
                            insight_type=DebugInsightType.ANOMALY.value,
                            severity=DebugInsightSeverity.WARNING.value,
                            title="Event volume spike detected",
                            description=f"Detected {len(spikes)} time periods with unusually high event volume",
                            summary=f"Event volume spiked to {max(spikes, key=lambda x: x[1])[1]} events/minute (avg: {avg_events_per_minute:.1f})",
                            evidence={
                                "average_per_minute": avg_events_per_minute,
                                "spikes": [
                                    {"minute": minute, "count": count} for minute, count in spikes
                                ],
                            },
                            confidence_score=0.75,
                            suggestions=[
                                "Check for error loops",
                                "Review system load",
                                "Investigate unusual activity",
                            ],
                            scope="system",
                            affected_components=[],
                            generated_at=datetime.utcnow(),
                        )
                    )

        except Exception as e:
            self.logger.error("Failed to generate anomaly insights", error=str(e))

        return insights

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _query_events(
        self,
        correlation_id: Optional[str] = None,
        component_type: Optional[str] = None,
        component_id: Optional[str] = None,
        time_range: Optional[str] = None,
    ) -> List[DebugEvent]:
        """Query debug events with filters."""
        try:
            query = self.db.query(DebugEvent)

            if correlation_id:
                query = query.filter(DebugEvent.correlation_id == correlation_id)
            if component_type:
                query = query.filter(DebugEvent.component_type == component_type)
            if component_id:
                query = query.filter(DebugEvent.component_id == component_id)

            if time_range:
                time_filter = self._parse_time_range(time_range)
                if time_filter:
                    query = query.filter(DebugEvent.timestamp >= time_filter)

            return query.order_by(DebugEvent.timestamp.desc()).all()

        except Exception as e:
            self.logger.error("Failed to query events", error=str(e))
            return []

    def _parse_time_range(self, time_range: str) -> Optional[datetime]:
        """Parse time range string to datetime."""
        now = datetime.utcnow()

        if time_range == "last_1h":
            return now - timedelta(hours=1)
        elif time_range == "last_24h":
            return now - timedelta(hours=24)
        elif time_range == "last_7d":
            return now - timedelta(days=7)
        elif time_range == "last_30d":
            return now - timedelta(days=30)
        else:
            return None
