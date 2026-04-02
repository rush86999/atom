"""
Fleet orchestration package for parallel execution coordination.

This package provides services for coordinating multi-agent fleets
with parallel execution capabilities, Redis pub/sub state synchronization,
and distributed blackboard management.
"""

from .fleet_execution_models import (
    FleetExecutionConfig,
    BlackboardUpdate,
    FleetStateSnapshot,
    ParallelExecutionRequest
)
from .fleet_coordinator_service import FleetCoordinatorService, get_fleet_coordinator
from .distributed_blackboard_service import FleetStateNotifier, get_fleet_state_notifier
from .task_decomposition_service import (
    TaskDecompositionService,
    SubTask,
    TaskDecomposition
)
from .dependency_graph_service import (
    DependencyGraphService,
    build_graph,
    validate_cycles,
    get_execution_groups,
    detect_critical_path
)
from .fault_tolerance_service import FaultToleranceService
from .complexity_estimator import ComplexityEstimator, FLEET_SIZE_LIMITS
from .performance_metrics_service import (
    PerformanceMetricsService,
    PerformanceMetrics,
    PerformanceAlert,
    get_performance_metrics_service
)
from .scaling_proposal_service import (
    ScalingProposalService,
    ScalingProposal,
    ScalingProposalType,
    ScalingProposalStatus,
    get_scaling_proposal_service
)
from .fleet_scaler_service import (
    FleetScalerService,
    ScalingOperation,
    ScalingOperationStatus,
    get_fleet_scaler_service
)
from .overage_service import (
    OverageService,
    get_overage_service
)
from .auto_approval_service import (
    AutoApprovalService,
    get_auto_approval_service
)
from .predictive_scaling_service import (
    PredictiveScalingService,
    get_predictive_scaling_service
)

# Alias for backward compatibility with plan requirements
# FleetStateNotifier provides distributed blackboard functionality
DistributedBlackboardService = FleetStateNotifier
get_distributed_blackboard = get_fleet_state_notifier

__all__ = [
    # Models
    "FleetExecutionConfig",
    "BlackboardUpdate",
    "FleetStateSnapshot",
    "ParallelExecutionRequest",
    "SubTask",
    "TaskDecomposition",
    # Services
    "FleetCoordinatorService",
    "get_fleet_coordinator",
    "FleetStateNotifier",
    "get_fleet_state_notifier",
    "TaskDecompositionService",
    "DependencyGraphService",
    "FaultToleranceService",
    "ComplexityEstimator",
    "FLEET_SIZE_LIMITS",
    "PerformanceMetricsService",
    "PerformanceMetrics",
    "PerformanceAlert",
    "get_performance_metrics_service",
    "ScalingProposalService",
    "ScalingProposal",
    "ScalingProposalType",
    "ScalingProposalStatus",
    "get_scaling_proposal_service",
    "FleetScalerService",
    "ScalingOperation",
    "ScalingOperationStatus",
    "get_fleet_scaler_service",
    "OverageService",
    "get_overage_service",
    "AutoApprovalService",
    "get_auto_approval_service",
    "PredictiveScalingService",
    "get_predictive_scaling_service",
    "build_graph",
    "validate_cycles",
    "get_execution_groups",
    "detect_critical_path",
    # Aliases for plan compatibility
    "DistributedBlackboardService",
    "get_distributed_blackboard",
]
