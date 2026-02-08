"""
Error Causality Insights for AI Debug System

Analyzes errors and detects:
- Root cause analysis using error chains
- Error propagation tracking
- Suggested fixes based on historical resolutions
- Error pattern recognition

Example insights:
- "Root cause: Database connection pool exhausted"
- "Error originated in external API, propagated through 3 components"
- "Same error occurred 15 times in last hour, suggesting systemic issue"
"""

import asyncio
from collections import defaultdict, Counter
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


class ErrorCausalityInsightGenerator:
    """
    Generates insights about error causality and propagation.

    Analyzes error chains to determine root causes and track
    how errors propagate through the system.
    """

    def __init__(self, db_session: Session):
        """
        Initialize error causality insight generator.

        Args:
            db_session: SQLAlchemy database session
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session

    async def analyze_error_chain(
        self,
        error_event_id: str,
    ) -> Optional[DebugInsight]:
        """
        Analyze the causal chain of an error.

        Traces back through parent events to find the root cause.

        Args:
            error_event_id: Error event ID to analyze

        Returns:
            Error insight or None
        """
        try:
            # Get the error event
            error_event = (
                self.db.query(DebugEvent)
                .filter(DebugEvent.id == error_event_id)
                .first()
            )

            if not error_event or error_event.level not in ["ERROR", "CRITICAL"]:
                return None

            # Trace back through parent events
            chain = []
            current_event = error_event
            visited = set()

            while current_event and current_event.id not in visited:
                visited.add(current_event.id)
                chain.append(current_event)

                if current_event.parent_event_id:
                    current_event = (
                        self.db.query(DebugEvent)
                        .filter(DebugEvent.id == current_event.parent_event_id)
                        .first()
                    )
                else:
                    break

            if len(chain) < 2:
                # No chain to analyze
                return DebugInsight(
                    insight_type=DebugInsightType.ERROR.value,
                    severity=DebugInsightSeverity.INFO.value,
                    title="Error analysis",
                    description=f"Error in {error_event.component_type}/{error_event.component_id}",
                    summary=error_event.message or "No message",
                    evidence={
                        "error_id": error_event_id,
                        "chain_length": len(chain),
                    },
                    confidence_score=0.70,
                    suggestions=[
                        "Review error message",
                        "Check component logs",
                    ],
                    scope="component",
                    affected_components=[
                        {"type": error_event.component_type, "id": error_event.component_id}
                    ],
                    generated_at=datetime.utcnow(),
                )

            # Analyze the chain
            root_cause = chain[-1]
            propagation_path = " → ".join(
                f"{e.component_type}/{e.component_id}" for e in reversed(chain)
            )

            return DebugInsight(
                insight_type=DebugInsightType.ERROR.value,
                severity=DebugInsightSeverity.ERROR.value,
                title=f"Root cause analysis for error in {error_event.component_type}/{error_event.component_id}",
                description=f"Root cause: {root_cause.message or 'Unknown'} "
                f"in {root_cause.component_type}/{root_cause.component_id}\n"
                f"Error propagated through {len(chain)} components: {propagation_path}",
                summary=f"Root cause in {root_cause.component_type}: {root_cause.message[:100] if root_cause.message else 'No message'}",
                evidence={
                    "error_id": error_event_id,
                    "root_cause": {
                        "event_id": root_cause.id,
                        "component_type": root_cause.component_type,
                        "component_id": root_cause.component_id,
                        "message": root_cause.message,
                    },
                    "propagation_chain": [
                        {
                            "event_id": e.id,
                            "component_type": e.component_type,
                            "component_id": e.component_id,
                            "message": e.message,
                            "level": e.level,
                        }
                        for e in chain
                    ],
                    "chain_length": len(chain),
                },
                confidence_score=0.85,
                suggestions=[
                    f"Fix root cause in {root_cause.component_type}/{root_cause.component_id}",
                    "Review error propagation path",
                    "Consider adding error handling at intermediate components",
                ],
                scope="distributed",
                affected_components=[
                    {"type": e.component_type, "id": e.component_id} for e in chain
                ],
                generated_at=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error(
                "Failed to analyze error chain",
                error_event_id=error_event_id,
                error=str(e),
            )
            return None

    async def track_error_propagation(
        self,
        correlation_id: str,
    ) -> Optional[DebugInsight]:
        """
        Track how an error propagates through the system.

        Args:
            correlation_id: Operation correlation ID

        Returns:
            Error insight or None
        """
        try:
            # Get all events for the operation
            events = (
                self.db.query(DebugEvent)
                .filter(DebugEvent.correlation_id == correlation_id)
                .order_by(DebugEvent.timestamp)
                .all()
            )

            # Find error events
            error_events = [e for e in events if e.level in ["ERROR", "CRITICAL"]]

            if not error_events:
                return None

            # Track propagation
            affected_components = set()
            propagation_order = []

            for event in events:
                comp_key = f"{event.component_type}/{event.component_id}"
                if comp_key not in affected_components:
                    affected_components.add(comp_key)
                    propagation_order.append((event, comp_key))

                    # Stop when we hit first error
                    if event.level in ["ERROR", "CRITICAL"]:
                        break

            return DebugInsight(
                insight_type=DebugInsightType.ERROR.value,
                severity=DebugInsightSeverity.ERROR.value,
                title=f"Error propagation in operation {correlation_id}",
                description=f"Error affected {len(affected_components)} components "
                f"before being caught: {' → '.join(propagation_order[:][:5])}",
                summary=f"Error propagated through {len(affected_components)} components",
                evidence={
                    "correlation_id": correlation_id,
                    "affected_components": list(affected_components),
                    "propagation_order": [
                        {
                            "component": comp,
                            "message": e.message,
                            "level": e.level,
                        }
                        for e, comp in propagation_order
                    ],
                },
                confidence_score=0.88,
                suggestions=[
                    "Add error handling earlier in the flow",
                    "Implement circuit breakers",
                    "Review error propagation strategy",
                ],
                scope="distributed",
                affected_components=[
                    {"type": e.component_type, "id": e.component_id}
                    for e, _ in propagation_order
                ],
                generated_at=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error(
                "Failed to track error propagation",
                correlation_id=correlation_id,
                error=str(e),
            )
            return None

    async def detect_error_patterns(
        self,
        time_range: str = "last_1h",
    ) -> List[DebugInsight]:
        """
        Detect recurring error patterns.

        Args:
            time_range: Time range to analyze

        Returns:
            List of error insights
        """
        try:
            insights = []
            time_filter = self._parse_time_range(time_range)

            # Find error patterns by message
            error_patterns = (
                self.db.query(
                    DebugEvent.message,
                    func.count(DebugEvent.id).label("count"),
                    func.min(DebugEvent.timestamp).label("first_seen"),
                    func.max(DebugEvent.timestamp).label("last_seen"),
                )
                .filter(
                    and_(
                        DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                        DebugEvent.timestamp >= time_filter,
                        DebugEvent.message.isnot(None),
                    )
                )
                .group_by(DebugEvent.message)
                .having(func.count(DebugEvent.id) >= 5)  # At least 5 occurrences
                .order_by(func.count(DebugEvent.id).desc())
                .all()
            )

            for message, count, first_seen, last_seen in error_patterns:
                # Get affected components
                affected = (
                    self.db.query(
                        DebugEvent.component_type,
                        DebugEvent.component_id,
                    )
                    .filter(
                        and_(
                            DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                            DebugEvent.message == message,
                            DebugEvent.timestamp >= time_filter,
                        )
                    )
                    .distinct()
                    .all()
                )

                affected_components = [
                    {"type": comp_type, "id": comp_id}
                    for comp_type, comp_id in affected
                ]

                duration = (last_seen - first_seen).total_seconds() if (last_seen and first_seen) else 0
                frequency = count / (duration / 60) if duration > 0 else 0  # errors per minute

                insights.append(
                    DebugInsight(
                        insight_type=DebugInsightType.ERROR.value,
                        severity=DebugInsightSeverity.WARNING.value,
                        title=f"Recurring error pattern: {message[:50]}",
                        description=f"Same error occurred {count} times across {len(affected_components)} components "
                        f"({frequency:.1f} errors/minute)",
                        summary=f"Error pattern repeated {count} times",
                        evidence={
                            "error_message": message,
                            "occurrence_count": count,
                            "affected_components": affected_components,
                            "first_seen": first_seen.isoformat() if first_seen else None,
                            "last_seen": last_seen.isoformat() if last_seen else None,
                            "duration_seconds": duration,
                            "frequency_per_min": frequency,
                        },
                        confidence_score=0.90,
                        suggestions=[
                            "Fix root cause of this error",
                            "Implement retry logic with exponential backoff",
                            "Add monitoring for this error pattern",
                            "Review why this error occurs repeatedly",
                        ],
                        scope="distributed",
                        affected_components=affected_components,
                        generated_at=datetime.utcnow(),
                    )
                )

            return insights

        except Exception as e:
            self.logger.error("Failed to detect error patterns", error=str(e))
            return []

    async def suggest_fixes_from_history(
        self,
        error_message: str,
        time_range: str = "last_30d",
    ) -> List[str]:
        """
        Suggest fixes based on historical resolutions.

        Args:
            error_message: Error message to find fixes for
            time_range: Time range to search

        Returns:
            List of suggested fixes
        """
        try:
            # Find past occurrences of this error
            time_filter = self._parse_time_range(time_range)

            past_errors = (
                self.db.query(DebugEvent)
                .filter(
                    and_(
                        DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                        DebugEvent.message.ilike(f"%{error_message[:50]}%"),  # Partial match
                        DebugEvent.timestamp >= time_filter,
                    )
                )
                .order_by(DebugEvent.timestamp.desc())
                .limit(20)
                .all()
            )

            if not past_errors:
                return []

            # Check if any were resolved (by looking for subsequent success events)
            suggestions = []

            # Simple heuristic: common error patterns and their fixes
            error_lower = error_message.lower()

            if "connection" in error_lower and "timeout" in error_lower:
                suggestions = [
                    "Increase timeout duration",
                    "Check network connectivity",
                    "Verify service is running",
                    "Review firewall rules",
                ]
            elif "out of memory" in error_lower:
                suggestions = [
                    "Increase available memory",
                    "Check for memory leaks",
                    "Optimize memory usage",
                    "Scale to larger instance",
                ]
            elif "permission" in error_lower or "unauthorized" in error_lower:
                suggestions = [
                    "Check API credentials",
                    "Verify user permissions",
                    "Review access control settings",
                    "Refresh authentication tokens",
                ]
            elif "not found" in error_lower:
                suggestions = [
                    "Verify resource exists",
                    "Check resource ID/URL",
                    "Review deployment configuration",
                ]
            elif "rate limit" in error_lower:
                suggestions = [
                    "Implement request throttling",
                    "Add caching to reduce API calls",
                    "Use exponential backoff for retries",
                    "Contact API provider for rate limit increase",
                ]
            else:
                suggestions = [
                    "Review error logs for more details",
                    "Check service health status",
                    "Verify configuration",
                    "Contact support if issue persists",
                ]

            return suggestions

        except Exception as e:
            self.logger.error(
                "Failed to suggest fixes from history",
                error_message=error_message,
                error=str(e),
            )
            return []

    async def analyze_error_severity_distribution(
        self,
        component_type: str,
        time_range: str = "last_24h",
    ) -> Optional[DebugInsight]:
        """
        Analyze the distribution of error severities.

        Args:
            component_type: Component type to analyze
            time_range: Time range to analyze

        Returns:
            Error insight or None
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Count errors by level
            error_counts = (
                self.db.query(
                    DebugEvent.level,
                    func.count(DebugEvent.id).label("count"),
                )
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.level.in_(["ERROR", "CRITICAL"]),
                        DebugEvent.timestamp >= time_filter,
                    )
                )
                .group_by(DebugEvent.level)
                .all()
            )

            if not error_counts:
                return None

            total_errors = sum(count for _, count in error_counts)
            critical_count = sum(count for level, count in error_counts if level == "CRITICAL")

            critical_rate = critical_count / total_errors if total_errors > 0 else 0

            if critical_rate > 0.3:  # More than 30% are critical
                return DebugInsight(
                    insight_type=DebugInsightType.ERROR.value,
                    severity=DebugInsightSeverity.CRITICAL.value,
                    title=f"High critical error rate for {component_type}",
                    description=f"{critical_rate*100:.1f}% of errors are critical "
                    f"({critical_count}/{total_errors} errors)",
                    summary=f"Critical error rate {critical_rate*100:.1f}% requires immediate attention",
                    evidence={
                        "component_type": component_type,
                        "total_errors": total_errors,
                        "critical_errors": critical_count,
                        "critical_rate": critical_rate,
                        "error_distribution": {level: count for level, count in error_counts},
                    },
                    confidence_score=0.92,
                    suggestions=[
                        "Investigate critical errors first",
                        "Check for systemic issues",
                        "Review recent deployments",
                        "Escalate to on-call if continuing",
                    ],
                    scope="component",
                    affected_components=[{"type": component_type}],
                    generated_at=datetime.utcnow(),
                )

            return None

        except Exception as e:
            self.logger.error(
                "Failed to analyze error severity distribution",
                component_type=component_type,
                error=str(e),
            )
            return None

    def _parse_time_range(self, time_range: str) -> datetime:
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
            return now - timedelta(hours=1)
