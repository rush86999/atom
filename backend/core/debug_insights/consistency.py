"""
Data Consistency Insights for AI Debug System

Analyzes data consistency across distributed components and detects:
- Data flow across distributed nodes
- State divergence (same data, different states)
- Replication completion verification
- Data synchronization issues

Example insights:
- "Data sent to 5 nodes, 4 confirmed, 1 pending"
- "Data X saved on Node 1 but not Node 2"
- "Replication lag detected across 3 nodes"
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.models import (
    DebugEvent,
    DebugInsight,
    DebugStateSnapshot,
    DebugInsightType,
    DebugInsightSeverity,
)
from core.structured_logger import StructuredLogger


class ConsistencyInsightGenerator:
    """
    Generates insights about data consistency across distributed components.

    Tracks data flow through the system and detects inconsistencies,
    replication delays, and synchronization issues.
    """

    def __init__(self, db_session: Session):
        """
        Initialize consistency insight generator.

        Args:
            db_session: SQLAlchemy database session
        """
        self.logger = StructuredLogger(__name__)
        self.db = db_session

    async def analyze_data_flow(
        self,
        operation_id: str,
        component_ids: List[str],
        component_type: str = "agent",
    ) -> Optional[DebugInsight]:
        """
        Analyze data flow across distributed components.

        Tracks how data propagates through the system and identifies
        any components that haven't received or acknowledged the data.

        Args:
            operation_id: Operation to analyze
            component_ids: Expected components in the flow
            component_type: Type of components

        Returns:
            Consistency insight or None
        """
        try:
            # Find all state snapshots for this operation
            snapshots = (
                self.db.query(DebugStateSnapshot)
                .filter(
                    and_(
                        DebugStateSnapshot.operation_id == operation_id,
                        DebugStateSnapshot.component_type == component_type,
                    )
                )
                .order_by(DebugStateSnapshot.captured_at)
                .all()
            )

            if not snapshots:
                return None

            # Track which components have snapshots
            components_with_snapshots = set(s.component_id for s in snapshots)

            # Find missing components
            missing_components = set(component_ids) - components_with_snapshots

            if missing_components:
                # Data hasn't reached all components yet
                return DebugInsight(
                    insight_type=DebugInsightType.CONSISTENCY.value,
                    severity=DebugInsightSeverity.WARNING.value,
                    title="Incomplete data propagation",
                    description=f"Data sent to {len(component_ids)} nodes but only "
                    f"{len(components_with_snapshots)} confirmed receipt",
                    summary=f"Data sent to {len(component_ids)} nodes, {len(missing_components)} pending",
                    evidence={
                        "operation_id": operation_id,
                        "expected_components": component_ids,
                        "confirmed_components": list(components_with_snapshots),
                        "missing_components": list(missing_components),
                        "propagation_rate": len(components_with_snapshots) / len(component_ids),
                    },
                    confidence_score=0.95,
                    suggestions=[
                        f"Check connectivity to missing nodes: {', '.join(missing_components)}",
                        "Verify message queues are processing",
                        "Check for network partitions",
                    ],
                    scope="distributed",
                    affected_components=[
                        {"type": component_type, "id": comp_id} for comp_id in component_ids
                    ],
                    generated_at=datetime.utcnow(),
                )

            # All components have data - check timing consistency
            capture_times = [s.captured_at for s in snapshots if s.captured_at]
            if len(capture_times) > 1:
                min_time = min(capture_times)
                max_time = max(capture_times)
                replication_lag = (max_time - min_time).total_seconds()

                if replication_lag > 5.0:  # 5 second threshold
                    return DebugInsight(
                        insight_type=DebugInsightType.CONSISTENCY.value,
                        severity=DebugInsightSeverity.WARNING.value,
                        title="Replication lag detected",
                        description=f"Data replicated to all {len(component_ids)} nodes but with "
                        f"{replication_lag:.1f}s delay between first and last",
                        summary=f"Replication lag of {replication_lag:.1f}s across {len(component_ids)} nodes",
                        evidence={
                            "operation_id": operation_id,
                            "replication_lag_seconds": replication_lag,
                            "first_confirmation": min_time.isoformat() if min_time else None,
                            "last_confirmation": max_time.isoformat() if max_time else None,
                        },
                        confidence_score=0.90,
                        suggestions=[
                            "Investigate slow components",
                            "Check network latency between nodes",
                            "Review resource utilization",
                        ],
                        scope="distributed",
                        affected_components=[
                            {"type": component_type, "id": comp_id} for comp_id in component_ids
                        ],
                        generated_at=datetime.utcnow(),
                    )

            # All good - data consistent
            return DebugInsight(
                insight_type=DebugInsightType.CONSISTENCY.value,
                severity=DebugInsightSeverity.INFO.value,
                title="Data consistent across all nodes",
                description=f"Data successfully propagated to all {len(component_ids)} components",
                summary=f"Data sent to {len(component_ids)} nodes, all confirmed",
                evidence={
                    "operation_id": operation_id,
                    "component_count": len(component_ids),
                    "replication_complete": True,
                },
                confidence_score=1.0,
                scope="distributed",
                affected_components=[
                    {"type": component_type, "id": comp_id} for comp_id in component_ids
                ],
                generated_at=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error(
                "Failed to analyze data flow",
                operation_id=operation_id,
                error=str(e),
            )
            return None

    async def detect_state_divergence(
        self,
        operation_id: str,
        component_type: str = "agent",
    ) -> Optional[DebugInsight]:
        """
        Detect state divergence across components.

        Identifies when the same data has different states on different nodes,
        indicating a synchronization issue.

        Args:
            operation_id: Operation to analyze
            component_type: Type of components

        Returns:
            Consistency insight or None
        """
        try:
            # Get all state snapshots for this operation
            snapshots = (
                self.db.query(DebugStateSnapshot)
                .filter(
                    and_(
                        DebugStateSnapshot.operation_id == operation_id,
                        DebugStateSnapshot.component_type == component_type,
                    )
                )
                .order_by(DebugStateSnapshot.captured_at.desc())
                .all()
            )

            if len(snapshots) < 2:
                return None  # Need at least 2 components to compare

            # Get latest snapshot for each component
            latest_snapshots = {}
            for snapshot in snapshots:
                if snapshot.component_id not in latest_snapshots:
                    latest_snapshots[snapshot.component_id] = snapshot

            # Compare states across components
            inconsistencies = self._compare_states(latest_snapshots)

            if inconsistencies:
                component_ids = list(latest_snapshots.keys())
                return DebugInsight(
                    insight_type=DebugInsightType.CONSISTENCY.value,
                    severity=DebugInsightSeverity.CRITICAL.value,
                    title="State divergence detected",
                    description=f"Found {len(inconsistencies)} state inconsistencies across "
                    f"{len(component_ids)} components",
                    summary=f"Data differs across {len(component_ids)} components for {len(inconsistencies)} keys",
                    evidence={
                        "operation_id": operation_id,
                        "inconsistencies": inconsistencies,
                        "affected_keys": list(inconsistencies.keys()),
                    },
                    confidence_score=0.92,
                    suggestions=[
                        "Review synchronization logic",
                        "Check for concurrent modifications",
                        "Verify conflict resolution mechanisms",
                        "Investigate data partitioning issues",
                    ],
                    scope="distributed",
                    affected_components=[
                        {"type": component_type, "id": comp_id} for comp_id in component_ids
                    ],
                    generated_at=datetime.utcnow(),
                )

            return None

        except Exception as e:
            self.logger.error(
                "Failed to detect state divergence",
                operation_id=operation_id,
                error=str(e),
            )
            return None

    async def verify_replication_completion(
        self,
        operation_id: str,
        expected_replicas: int,
        component_type: str = "agent",
    ) -> Optional[DebugInsight]:
        """
        Verify that data has been replicated to all expected nodes.

        Args:
            operation_id: Operation to verify
            expected_replicas: Number of expected replicas
            component_type: Type of components

        Returns:
            Consistency insight or None
        """
        try:
            # Count unique components that have data
            component_count = (
                self.db.query(DebugStateSnapshot)
                .filter(
                    and_(
                        DebugStateSnapshot.operation_id == operation_id,
                        DebugStateSnapshot.component_type == component_type,
                    )
                )
                .distinct(DebugStateSnapshot.component_id)
                .count()
            )

            if component_count < expected_replicas:
                return DebugInsight(
                    insight_type=DebugInsightType.CONSISTENCY.value,
                    severity=DebugInsightSeverity.WARNING.value,
                    title="Incomplete replication",
                    description=f"Expected {expected_replicas} replicas but only {component_count} confirmed",
                    summary=f"{expected_replicas - component_count} replicas missing",
                    evidence={
                        "operation_id": operation_id,
                        "expected_replicas": expected_replicas,
                        "actual_replicas": component_count,
                        "completion_rate": component_count / expected_replicas,
                    },
                    confidence_score=0.98,
                    suggestions=[
                        "Check replication logs",
                        "Verify network connectivity",
                        "Review replication configuration",
                    ],
                    scope="distributed",
                    affected_components=[{"type": component_type}],
                    generated_at=datetime.utcnow(),
                )

            # Replication complete
            return DebugInsight(
                insight_type=DebugInsightType.CONSISTENCY.value,
                severity=DebugInsightSeverity.INFO.value,
                title="Replication complete",
                description=f"Data successfully replicated to all {expected_replicas} nodes",
                summary=f"All {expected_replicas} replicas confirmed",
                evidence={
                    "operation_id": operation_id,
                    "replica_count": component_count,
                },
                confidence_score=1.0,
                scope="distributed",
                affected_components=[{"type": component_type}],
                generated_at=datetime.utcnow(),
            )

        except Exception as e:
            self.logger.error(
                "Failed to verify replication completion",
                operation_id=operation_id,
                error=str(e),
            )
            return None

    async def analyze_sync_patterns(
        self,
        time_range: str = "last_1h",
    ) -> List[DebugInsight]:
        """
        Analyze synchronization patterns across all operations.

        Identifies systemic issues with data synchronization.

        Args:
            time_range: Time range to analyze

        Returns:
            List of consistency insights
        """
        try:
            insights = []
            time_filter = self._parse_time_range(time_range)

            # Find operations with incomplete replication
            operations = (
                self.db.query(DebugStateSnapshot.operation_id)
                .filter(DebugStateSnapshot.captured_at >= time_filter)
                .group_by(DebugStateSnapshot.operation_id)
                .all()
            )

            for (operation_id,) in operations:
                # Count components per operation
                component_count = (
                    self.db.query(DebugStateSnapshot)
                    .filter(
                        and_(
                            DebugStateSnapshot.operation_id == operation_id,
                            DebugStateSnapshot.captured_at >= time_filter,
                        )
                    )
                    .distinct(DebugStateSnapshot.component_id)
                    .count()
                )

                # If an operation has only 1 component, it might not be replicating
                if component_count == 1:
                    insights.append(
                        DebugInsight(
                            insight_type=DebugInsightType.CONSISTENCY.value,
                            severity=DebugInsightSeverity.INFO.value,
                            title="Single-component operation detected",
                            description=f"Operation {operation_id} has data on only 1 component",
                            summary=f"Operation may not be configured for replication",
                            evidence={"operation_id": operation_id},
                            confidence_score=0.70,
                            suggestions=[
                                "Verify replication is configured",
                                "Check if this is a local-only operation",
                            ],
                            scope="distributed",
                            affected_components=[],
                            generated_at=datetime.utcnow(),
                        )
                    )

            return insights

        except Exception as e:
            self.logger.error("Failed to analyze sync patterns", error=str(e))
            return []

    def _compare_states(
        self,
        snapshots: Dict[str, DebugStateSnapshot],
    ) -> Dict[str, Any]:
        """
        Compare states across multiple components.

        Args:
            snapshots: Component ID -> Snapshot mapping

        Returns:
            Dictionary of inconsistent keys and their values
        """
        inconsistencies = {}

        # Get all keys from the first snapshot
        first_snapshot = list(snapshots.values())[0]
        all_keys = set(first_snapshot.state_data.keys()) if first_snapshot.state_data else set()

        # For each key, compare values across all snapshots
        for key in all_keys:
            values = {}
            for comp_id, snapshot in snapshots.items():
                if snapshot.state_data and key in snapshot.state_data:
                    values[comp_id] = snapshot.state_data[key]

            # Check if all values are the same
            unique_values = set(str(v) for v in values.values())
            if len(unique_values) > 1:
                inconsistencies[key] = {
                    "values": values,
                    "divergence_detected": True,
                }

        return inconsistencies

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
