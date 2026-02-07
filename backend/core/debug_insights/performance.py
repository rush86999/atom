"""
Performance Insights for AI Debug System

Analyzes performance metrics and detects:
- Component latency breakdown (p50, p95, p99)
- Bottleneck identification
- Resource utilization tracking
- Performance degradation over time

Example insights:
- "Agent-456 response time increased by 200%"
- "Database queries taking 95th percentile of 2.5s"
- "CPU utilization at 95% on node-1"
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from core.models import (
    DebugEvent,
    DebugMetric,
    DebugInsight,
    DebugInsightType,
    DebugInsightSeverity,
)
from core.structured_logger import StructuredLogger


class PerformanceInsightGenerator:
    """
    Generates insights about system performance.

    Analyzes latency, throughput, and resource utilization to
    identify performance bottlenecks and degradation.
    """

    def __init__(self, db_session: Session):
        """
        Initialize performance insight generator.

        Args:
            db_session: SQLAlchemy database session
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session

    async def analyze_component_latency(
        self,
        component_type: str,
        component_id: str,
        time_range: str = "last_1h",
    ) -> Optional[DebugInsight]:
        """
        Analyze component latency with percentiles.

        Args:
            component_type: Component type
            component_id: Component ID
            time_range: Time range to analyze

        Returns:
            Performance insight or None
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Get events with duration data
            events_with_duration = (
                self.db.query(DebugEvent)
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.timestamp >= time_filter,
                        DebugEvent.data.isnot(None),
                    )
                )
                .all()
            )

            # Extract duration values
            durations = []
            for event in events_with_duration:
                if event.data and "duration_ms" in event.data:
                    durations.append(event.data["duration_ms"])

            if len(durations) < 10:
                return None  # Not enough data

            # Calculate percentiles
            durations.sort()
            p50 = durations[int(len(durations) * 0.5)]
            p95 = durations[int(len(durations) * 0.95)]
            p99 = durations[int(len(durations) * 0.99)]
            avg = sum(durations) / len(durations)

            # Check for performance issues
            if p95 > 5000:  # 5 second threshold
                return DebugInsight(
                    insight_type=DebugInsightType.PERFORMANCE.value,
                    severity=DebugInsightSeverity.WARNING.value,
                    title=f"High latency detected for {component_type}/{component_id}",
                    description=f"95th percentile latency is {p95:.0f}ms (avg: {avg:.0f}ms)",
                    summary=f"P95 latency {p95:.0f}ms exceeds 5s threshold",
                    evidence={
                        "component_type": component_type,
                        "component_id": component_id,
                        "p50_ms": p50,
                        "p95_ms": p95,
                        "p99_ms": p99,
                        "avg_ms": avg,
                        "sample_count": len(durations),
                    },
                    confidence_score=0.90,
                    suggestions=[
                        "Profile hot paths",
                        "Check for N+1 queries",
                        "Review external API calls",
                        "Add caching for frequently accessed data",
                    ],
                    scope="component",
                    affected_components=[{"type": component_type, "id": component_id}],
                    generated_at=datetime.utcnow(),
                )

            # Latency is acceptable
            return DebugInsight(
                insight_type=DebugInsightType.PERFORMANCE.value,
                severity=DebugInsightSeverity.INFO.value,
                title=f"Latency acceptable for {component_type}/{component_id}",
                description=f"P95 latency {p95:.0f}ms within acceptable range",
                summary=f"Performance: P50={p50:.0f}ms, P95={p95:.0f}ms, P99={p99:.0f}ms",
                evidence={
                    "component_type": component_type,
                    "component_id": component_id,
                    "p50_ms": p50,
                    "p95_ms": p95,
                    "p99_ms": p99,
                },
                confidence_score=0.95,
                scope="component",
                affected_components=[{"type": component_type, "id": component_id}],
                generated_at=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error(
                "Failed to analyze component latency",
                component_type=component_type,
                component_id=component_id,
                error=str(e),
            )
            return None

    async def identify_bottlenecks(
        self,
        correlation_id: str,
    ) -> Optional[DebugInsight]:
        """
        Identify performance bottlenecks in an operation.

        Args:
            correlation_id: Operation to analyze

        Returns:
            Performance insight or None
        """
        try:
            # Get all events for the operation
            events = (
                self.db.query(DebugEvent)
                .filter(DebugEvent.correlation_id == correlation_id)
                .order_by(DebugEvent.timestamp)
                .all()
            )

            if not events:
                return None

            # Find slowest steps
            slow_steps = []
            for event in events:
                if event.data and "duration_ms" in event.data:
                    slow_steps.append({
                        "component": f"{event.component_type}/{event.component_id}",
                        "message": event.message,
                        "duration_ms": event.data["duration_ms"],
                    })

            if not slow_steps:
                return None

            # Sort by duration
            slow_steps.sort(key=lambda x: x["duration_ms"], reverse=True)
            total_duration = sum(s["duration_ms"] for s in slow_steps)

            # Check if any step dominates the execution time
            if slow_steps:
                slowest = slow_steps[0]
                slowest_percentage = (slowest["duration_ms"] / total_duration * 100) if total_duration > 0 else 0

                if slowest_percentage > 50:  # One step takes >50% of time
                    return DebugInsight(
                        insight_type=DebugInsightType.PERFORMANCE.value,
                        severity=DebugInsightSeverity.WARNING.value,
                        title="Performance bottleneck identified",
                        description=f"{slowest['component']} - {slowest['message']} "
                        f"takes {slowest_percentage:.1f}% of total execution time",
                        summary=f"Bottleneck: {slowest['duration_ms']}ms ({slowest_percentage:.1f}% of total)",
                        evidence={
                            "correlation_id": correlation_id,
                            "slowest_step": slowest,
                            "slowest_percentage": slowest_percentage,
                            "total_duration_ms": total_duration,
                            "all_steps": slow_steps[:5],  # Top 5 steps
                        },
                        confidence_score=0.88,
                        suggestions=[
                            f"Optimize {slowest['component']} operation",
                            "Check for inefficient queries",
                            "Review algorithmic complexity",
                            "Consider parallelization",
                        ],
                        scope="component",
                        affected_components=[
                            {"type": e.component_type, "id": e.component_id} for e in events
                        ],
                        generated_at=datetime.utcnow(),
                    )

            return None

        except Exception as e:
            self.logger.error(
                "Failed to identify bottlenecks",
                correlation_id=correlation_id,
                error=str(e),
            )
            return None

    async def track_resource_utilization(
        self,
        time_range: str = "last_1h",
    ) -> List[DebugInsight]:
        """
        Track resource utilization across components.

        Args:
            time_range: Time range to analyze

        Returns:
            List of performance insights
        """
        try:
            insights = []
            time_filter = self._parse_time_range(time_range)

            # Get CPU usage metrics
            cpu_metrics = (
                self.db.query(DebugMetric)
                .filter(
                    and_(
                        DebugMetric.metric_name == "cpu_usage",
                        DebugMetric.timestamp >= time_filter,
                    )
                )
                .all()
            )

            # Group by component and calculate averages
            cpu_by_component = defaultdict(list)
            for metric in cpu_metrics:
                key = f"{metric.component_type}/{metric.component_id}"
                cpu_by_component[key].append(metric.value)

            # Check for high CPU usage
            for comp_key, values in cpu_by_component.items():
                avg_cpu = sum(values) / len(values)
                max_cpu = max(values)

                if avg_cpu > 80:  # 80% average threshold
                    component_type, component_id = comp_key.split("/")
                    insights.append(
                        DebugInsight(
                            insight_type=DebugInsightType.PERFORMANCE.value,
                            severity=DebugInsightSeverity.WARNING.value,
                            title=f"High CPU usage on {comp_key}",
                            description=f"Average CPU usage {avg_cpu:.1f}% (peak: {max_cpu:.1f}%)",
                            summary=f"CPU utilization at {avg_cpu:.1f}% on average",
                            evidence={
                                "component_type": component_type,
                                "component_id": component_id,
                                "avg_cpu_percent": avg_cpu,
                                "max_cpu_percent": max_cpu,
                                "sample_count": len(values),
                            },
                            confidence_score=0.92,
                            suggestions=[
                                "Scale up resources",
                                "Optimize code efficiency",
                                "Review for infinite loops",
                                "Check for background processes",
                            ],
                            scope="component",
                            affected_components=[{"type": component_type, "id": component_id}],
                            generated_at=datetime.utcnow(),
                        )
                    )

            # Get memory usage metrics
            memory_metrics = (
                self.db.query(DebugMetric)
                .filter(
                    and_(
                        DebugMetric.metric_name == "memory_usage",
                        DebugMetric.timestamp >= time_filter,
                    )
                )
                .all()
            )

            memory_by_component = defaultdict(list)
            for metric in memory_metrics:
                key = f"{metric.component_type}/{metric.component_id}"
                memory_by_component[key].append(metric.value)

            # Check for high memory usage
            for comp_key, values in memory_by_component.items():
                avg_mem = sum(values) / len(values)
                max_mem = max(values)

                if avg_mem > 80:  # 80% average threshold
                    component_type, component_id = comp_key.split("/")
                    insights.append(
                        DebugInsight(
                            insight_type=DebugInsightType.PERFORMANCE.value,
                            severity=DebugInsightSeverity.WARNING.value,
                            title=f"High memory usage on {comp_key}",
                            description=f"Average memory usage {avg_mem:.1f}% (peak: {max_mem:.1f}%)",
                            summary=f"Memory utilization at {avg_mem:.1f}% on average",
                            evidence={
                                "component_type": component_type,
                                "component_id": component_id,
                                "avg_memory_percent": avg_mem,
                                "max_memory_percent": max_mem,
                                "sample_count": len(values),
                            },
                            confidence_score=0.92,
                            suggestions=[
                                "Check for memory leaks",
                                "Review caching strategy",
                                "Optimize data structures",
                                "Consider memory profiling",
                            ],
                            scope="component",
                            affected_components=[{"type": component_type, "id": component_id}],
                            generated_at=datetime.utcnow(),
                        )
                    )

            return insights

        except Exception as e:
            self.logger.error("Failed to track resource utilization", error=str(e))
            return []

    async def detect_performance_degradation(
        self,
        component_type: str,
        component_id: str,
        time_range: str = "last_24h",
    ) -> Optional[DebugInsight]:
        """
        Detect performance degradation over time.

        Args:
            component_type: Component type
            component_id: Component ID
            time_range: Time range to analyze

        Returns:
            Performance insight or None
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Get events with duration data
            events = (
                self.db.query(DebugEvent)
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.component_id == component_id,
                        DebugEvent.timestamp >= time_filter,
                        DebugEvent.data.isnot(None),
                    )
                )
                .order_by(DebugEvent.timestamp)
                .all()
            )

            # Split into first half and second half
            mid_point = len(events) // 2
            first_half = events[:mid_point]
            second_half = events[mid_point:]

            if len(first_half) < 10 or len(second_half) < 10:
                return None

            # Calculate average duration for each half
            first_avg = 0
            first_count = 0
            for event in first_half:
                if event.data and "duration_ms" in event.data:
                    first_avg += event.data["duration_ms"]
                    first_count += 1

            second_avg = 0
            second_count = 0
            for event in second_half:
                if event.data and "duration_ms" in event.data:
                    second_avg += event.data["duration_ms"]
                    second_count += 1

            if first_count > 0 and second_count > 0:
                first_avg /= first_count
                second_avg /= second_count

                # Check for degradation (>20% slower)
                if second_avg > first_avg * 1.2:
                    degradation_percent = ((second_avg - first_avg) / first_avg) * 100

                    return DebugInsight(
                        insight_type=DebugInsightType.PERFORMANCE.value,
                        severity=DebugInsightSeverity.WARNING.value,
                        title=f"Performance degradation detected for {component_type}/{component_id}",
                        description=f"Average response time increased by {degradation_percent:.1f}% "
                        f"({first_avg:.0f}ms → {second_avg:.0f}ms)",
                        summary=f"Performance degraded by {degradation_percent:.1f}% over time range",
                        evidence={
                            "component_type": component_type,
                            "component_id": component_id,
                            "first_half_avg_ms": first_avg,
                            "second_half_avg_ms": second_avg,
                            "degradation_percent": degradation_percent,
                            "time_range": time_range,
                        },
                        confidence_score=0.85,
                        suggestions=[
                            "Review recent changes",
                            "Check for increased load",
                            "Analyze database query plans",
                            "Review external API performance",
                            "Consider recent deployments",
                        ],
                        scope="component",
                        affected_components=[{"type": component_type, "id": component_id}],
                        generated_at=datetime.utcnow(),
                    )

            return None

        except Exception as e:
            self.logger.error(
                "Failed to detect performance degradation",
                component_type=component_type,
                component_id=component_id,
                error=str(e),
            )
            return None

    async def analyze_throughput(
        self,
        component_type: str,
        time_range: str = "last_1h",
    ) -> Optional[DebugInsight]:
        """
        Analyze throughput metrics for a component type.

        Args:
            component_type: Component type to analyze
            time_range: Time range to analyze

        Returns:
            Performance insight or None
        """
        try:
            time_filter = self._parse_time_range(time_range)

            # Count events per minute
            events_per_minute = (
                self.db.query(
                    func.strftime("%Y-%m-%d %H:%M", DebugEvent.timestamp).label("minute"),
                    func.count(DebugEvent.id).label("count"),
                )
                .filter(
                    and_(
                        DebugEvent.component_type == component_type,
                        DebugEvent.timestamp >= time_filter,
                    )
                )
                .group_by(func.strftime("%Y-%m-%d %H:%M", DebugEvent.timestamp))
                .all()
            )

            if not events_per_minute:
                return None

            counts = [count for _, count in events_per_minute]
            avg_throughput = sum(counts) / len(counts)
            min_throughput = min(counts)
            max_throughput = max(counts)

            # Check for low throughput
            if avg_throughput < 10:  # Less than 10 events/min
                return DebugInsight(
                    insight_type=DebugInsightType.PERFORMANCE.value,
                    severity=DebugInsightSeverity.INFO.value,
                    title=f"Low throughput for {component_type}",
                    description=f"Average {avg_throughput:.1f} events/minute (min: {min_throughput}, max: {max_throughput})",
                    summary=f"Throughput: {avg_throughput:.1f} events/min",
                    evidence={
                        "component_type": component_type,
                        "avg_throughput_per_min": avg_throughput,
                        "min_throughput_per_min": min_throughput,
                        "max_throughput_per_min": max_throughput,
                    },
                    confidence_score=0.80,
                    suggestions=[
                        "Check if this is expected for the workload",
                        "Review scaling configuration",
                        "Consider horizontal scaling",
                    ],
                    scope="component",
                    affected_components=[{"type": component_type}],
                    generated_at=datetime.utcnow(),
                )

            # High throughput
            if avg_throughput > 1000:  # More than 1000 events/min
                return DebugInsight(
                    insight_type=DebugInsightType.PERFORMANCE.value,
                    severity=DebugInsightSeverity.INFO.value,
                    title=f"High throughput for {component_type}",
                    description=f"Average {avg_throughput:.1f} events/minute (min: {min_throughput}, max: {max_throughput})",
                    summary=f"High throughput: {avg_throughput:.1f} events/min",
                    evidence={
                        "component_type": component_type,
                        "avg_throughput_per_min": avg_throughput,
                        "min_throughput_per_min": min_throughput,
                        "max_throughput_per_min": max_throughput,
                    },
                    confidence_score=0.80,
                    suggestions=[
                        "Consider scaling up if resources are constrained",
                        "Monitor for errors under high load",
                    ],
                    scope="component",
                    affected_components=[{"type": component_type}],
                    generated_at=datetime.utcnow(),
                )

            return None

        except Exception as e:
            self.logger.error(
                "Failed to analyze throughput",
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
        else:
            return now - timedelta(hours=1)
