"""
Workload Analyzer - Detects when additional agents would improve throughput.

Analyzes:
- Queue depth and pending tasks
- Task complexity and estimated processing time
- SLA pressure and deadlines
- Current agent utilization
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from core.models import AgentRegistry, AgentExecution

logger = logging.getLogger(__name__)


class WorkloadMetrics:
    """Metrics about current workload."""
    def __init__(
        self,
        queue_depth: int,
        avg_processing_time_seconds: float,
        sla_violation_count: int,
        agent_utilization_percent: float,
        pending_task_complexity: float
    ):
        self.queue_depth = queue_depth
        self.avg_processing_time = avg_processing_time_seconds
        self.sla_violation_count = sla_violation_count
        self.agent_utilization = agent_utilization_percent
        self.pending_task_complexity = pending_task_complexity


class WorkloadAnalyzer:
    """
    Analyzes workload to determine if spawning additional agents would help.

    Triggers spawning when:
    - Queue depth exceeds threshold AND agents are at capacity
    - SLA violations are increasing
    - Task complexity suggests parallelization would help
    """

    def __init__(self, db: Session):
        self.db = db

    # Thresholds for spawning decisions
    SPAWN_QUEUE_THRESHOLD = 10
    SPAWN_UTILIZATION_THRESHOLD = 0.8
    SPAWN_SLA_VIOLATION_THRESHOLD = 3
    SPAWN_COMPLEXITY_THRESHOLD = 0.7

    def analyze_workload(
        self,
        user_id: str,
        agent_category: Optional[str] = None
    ) -> WorkloadMetrics:
        """
        Analyze current workload for user/agent category.
        """
        # Count pending executions
        pending_query = self.db.query(AgentExecution).filter(
            AgentExecution.user_id == user_id,
            AgentExecution.status.in_(["pending", "running"])
        )

        if agent_category:
            pending_query = pending_query.join(AgentRegistry).filter(
                AgentRegistry.category == agent_category
            )

        queue_depth = pending_query.count()

        # Calculate average processing time (last hour)
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        avg_time_result = self.db.query(
            AgentExecution
        ).filter(
            AgentExecution.user_id == user_id,
            AgentExecution.status == "completed",
            AgentExecution.completed_at >= hour_ago
        ).all()

        if avg_time_result:
            total_time = sum([
                (e.completed_at - e.started_at).total_seconds()
                for e in avg_time_result
                if e.completed_at and e.started_at
            ])
            avg_processing_time = total_time / len(avg_time_result)
        else:
            avg_processing_time = 0.0

        # Count SLA violations
        sla_violations = self.db.query(AgentExecution).filter(
            AgentExecution.user_id == user_id,
            AgentExecution.completed_at >= hour_ago,
            AgentExecution.sla_deadline < AgentExecution.completed_at
        ).count()

        # Calculate utilization
        active_agents = self.db.query(AgentRegistry).filter(
            AgentRegistry.user_id == user_id,
            AgentRegistry.status == "active"
        ).count()

        running_agents = self.db.query(AgentExecution).filter(
            AgentExecution.user_id == user_id,
            AgentExecution.status == "running"
        ).distinct(AgentExecution.agent_id).count()

        agent_utilization = (
            running_agents / active_agents if active_agents > 0 else 0.0
        )

        task_complexity = min(avg_processing_time / 300.0, 1.0)

        return WorkloadMetrics(
            queue_depth=queue_depth,
            avg_processing_time_seconds=avg_processing_time,
            sla_violation_count=sla_violations,
            agent_utilization_percent=agent_utilization * 100,
            pending_task_complexity=task_complexity
        )

    def should_spawn_agent(
        self,
        metrics: WorkloadMetrics,
        max_agents: int = 10
    ) -> bool:
        """
        Determine if additional agent should be spawned.
        """
        # Sanitized count check
        current_agent_count = self.db.query(AgentRegistry).count()

        if current_agent_count >= max_agents:
            return False

        if (
            metrics.queue_depth >= self.SPAWN_QUEUE_THRESHOLD
            and metrics.agent_utilization >= self.SPAWN_UTILIZATION_THRESHOLD * 100
        ):
            return True

        if metrics.sla_violation_count >= self.SPAWN_SLA_VIOLATION_THRESHOLD:
            return True

        if (
            metrics.queue_depth >= 5
            and metrics.pending_task_complexity >= self.SPAWN_COMPLEXITY_THRESHOLD
        ):
            return True

        return False
