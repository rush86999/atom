"""
Complexity estimator for fleet sizing and duration estimation.

This service analyzes task decomposition to recommend optimal fleet sizes
and estimate completion duration based on critical path analysis.
"""

import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from .task_decomposition_service import TaskDecomposition
from .dependency_graph_service import DependencyGraphService
from analytics.fleet_analytics_service import FleetAnalyticsService

logger = logging.getLogger(__name__)

# Export FLEET_SIZE_LIMITS for direct import (plan requirement)
# Fleet size limit via MAX_FLEET_SIZE env var (upstream configuration-based)
# This is a HARD CAP enforced during scaling proposals
# Note: In upstream, this is configured via MAX_FLEET_SIZE environment variable
FLEET_SIZE_LIMITS = {
    "default": 100  # Default limit in upstream (configurable via MAX_FLEET_SIZE)
}

class ComplexityEstimator:
    """
    Estimator for task complexity and optimal fleet sizing.

    Analyzes task decomposition to recommend:
    - Optimal fleet size based on complexity factors
    - Estimated duration based on critical path analysis

    Fleet size factors:
    - Parallelizable ratio (more parallel = larger fleet)
    - Token complexity (more tokens = may need specialists)
    - Domain diversity (more domains = larger fleet)
    - Historical performance (low success = add buffer)
    - Configuration limits (hard cap via MAX_FLEET_SIZE env var)
    """

    # Fleet size limit via MAX_FLEET_SIZE env var (upstream configuration-based)
    # This is a HARD CAP enforced during scaling proposals
    FLEET_SIZE_LIMITS = {
        "default": 100  # Default limit in upstream (configurable via MAX_FLEET_SIZE)
    }

    def __init__(self, db: Session):
        """
        Initialize complexity estimator.

        Args:
            db: Database session for historical data
        """
        self.db = db
        self.analytics = FleetAnalyticsService(db)
        self.dependency_service = DependencyGraphService()
        self.logger = logger

    def estimate_fleet_size(
        self,
        decomposition: TaskDecomposition,
        tenant_plan: str) -> int:
        """
        Recommend optimal fleet size based on complexity analysis.

        Calculation formula:
            recommended = base_size * parallel_ratio * token_multiplier * domain_multiplier * historical_multiplier

        Args:
            decomposition: Task decomposition with subtasks
            tenant_plan: Not used in upstream (configuration-based via MAX_FLEET_SIZE)
            tenant_id: For historical data lookup (optional in upstream)

        Returns:
            Recommended fleet size (1 to MAX_FLEET_SIZE limit)
        """
        if not decomposition.subtasks:
            self.logger.warning("estimate_fleet_size: No subtasks, returning minimum fleet size 1")
            return 1

        # Start with subtask count as baseline
        base_size = len(decomposition.subtasks)

        # Factor 1: Parallelizable ratio (more parallel = larger fleet)
        parallel_count = sum(1 for s in decomposition.subtasks if s.can_parallelize)
        parallel_ratio = parallel_count / len(decomposition.subtasks) if decomposition.subtasks else 0

        # Factor 2: Token complexity (more tokens = may need specialists)
        total_tokens = sum(s.estimated_tokens for s in decomposition.subtasks)
        token_multiplier = 1.0
        if total_tokens > 100000:
            token_multiplier = 2.0  # Very complex
        elif total_tokens > 50000:
            token_multiplier = 1.5  # Complex task

        # Factor 3: Domain diversity (more domains = larger fleet)
        unique_domains = len(set(s.required_domain for s in decomposition.subtasks))
        domain_multiplier = 1.0 + (unique_domains * 0.1)

        # Factor 4: Historical performance (if available)
        historical_multiplier = 1.0
        if decomposition.subtasks:
            # Get performance for first subtask's domain
            domain = decomposition.subtasks[0].required_domain
            try:
                domain_perf = self.analytics.get_domain_performance_stats(tenant_id, domain)
                success_rate = domain_perf.get("success_rate", 1.0)
                if success_rate < 0.85:
                    historical_multiplier = 1.2  # Add buffer for low success
                    self.logger.info(
                        f"estimate_fleet_size: Low historical success rate ({success_rate:.0%}) "
                        f"for domain '{domain}', applying 1.2x multiplier"
                    )
            except Exception as e:
                self.logger.warning(f"estimate_fleet_size: Could not fetch historical data: {e}")

        # Calculate recommended size
        recommended = int(
            base_size
            * parallel_ratio
            * token_multiplier
            * domain_multiplier
            * historical_multiplier
        )

        # Enforce plan limits (hard cap)
        max_size = self.FLEET_SIZE_LIMITS.get(tenant_plan.lower(), 10)
        recommended = min(max(1, recommended), max_size)

        self.logger.info(
            f"estimate_fleet_size: Recommended {recommended} agents for {tenant_plan} plan "
            f"(base={base_size}, parallel_ratio={parallel_ratio:.2f}, "
            f"token_multiplier={token_multiplier:.2f}, domain_multiplier={domain_multiplier:.2f}, "
            f"historical_multiplier={historical_multiplier:.2f})"
        )

        return recommended

    def estimate_duration(
        self,
        decomposition: TaskDecomposition,
        fleet_size: int
    ) -> int:
        """
        Estimate completion time based on fleet size and critical path.

        Uses critical path analysis to determine minimum execution time.
        Parallelization reduces duration for non-critical tasks.

        Args:
            decomposition: Task decomposition
            fleet_size: Number of agents in fleet

        Returns:
            Estimated duration in seconds
        """
        if not decomposition.subtasks:
            self.logger.warning("estimate_duration: No subtasks, returning default 60 seconds")
            return 60

        # Build graph and find critical path
        try:
            graph = self.dependency_service.build_graph(decomposition.subtasks)
            critical_path, critical_tokens = self.dependency_service.detect_critical_path(
                graph,
                decomposition.subtasks
            )
        except Exception as e:
            self.logger.error(f"estimate_duration: Could not build graph: {e}, using token sum")
            critical_tokens = sum(s.estimated_tokens for s in decomposition.subtasks)

        # Assume 100 tokens/second processing rate (tunable)
        # This is a heuristic - actual rate depends on LLM model and task complexity
        base_duration = critical_tokens / 100

        # Calculate parallelizable ratio
        parallelizable_count = sum(1 for s in decomposition.subtasks if s.can_parallelize)
        parallelizable_ratio = parallelizable_count / len(decomposition.subtasks) if decomposition.subtasks else 0

        # More agents = faster parallel execution (diminishing returns)
        # Speedup formula: fleet_size * parallelizable_ratio, capped at total subtasks
        parallel_speedup = min(fleet_size * parallelizable_ratio, len(decomposition.subtasks))

        # Apply speedup to base duration
        # Formula: duration = base_duration / (1 + parallel_speedup * 0.5)
        # The 0.5 factor represents diminishing returns (2x fleet != 2x speedup)
        estimated_duration = base_duration / (1 + parallel_speedup * 0.5)

        # Ensure minimum duration of 60 seconds
        estimated_duration = max(60, int(estimated_duration))

        self.logger.info(
            f"estimate_duration: {estimated_duration}s (critical_tokens={critical_tokens}, "
            f"base_duration={base_duration:.0f}s, parallel_speedup={parallel_speedup:.2f}x)"
        )

        return estimated_duration
