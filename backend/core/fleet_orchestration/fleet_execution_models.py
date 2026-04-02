"""
Data models for fleet orchestration and parallel execution.

These models define the configuration and state structures for
coordinating multi-agent fleets with parallel execution capabilities.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum

class TaskStatus(str, Enum):
    """Status of a task execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class FleetExecutionConfig:
    """
    Configuration for parallel fleet execution.

    Attributes:
        parallel_mode: Whether to enable parallel execution of fleet members
        max_parallel_agents: Maximum number of agents that can execute simultaneously
        conflict_resolution_strategy: How to handle concurrent blackboard updates
        sync_channel: Redis pub/sub channel pattern for fleet synchronization
    """
    parallel_mode: bool = True
    max_parallel_agents: int = 10
    conflict_resolution_strategy: str = "optimistic_lock"  # options: optimistic_lock, last_write_wins, merge
    sync_channel: str = "fleet:{chain_id}"

    def __post_init__(self):
        """Validate configuration after initialization."""
        valid_strategies = ["optimistic_lock", "last_write_wins", "merge"]
        if self.conflict_resolution_strategy not in valid_strategies:
            raise ValueError(
                f"Invalid conflict_resolution_strategy: {self.conflict_resolution_strategy}. "
                f"Must be one of {valid_strategies}"
            )
        if self.max_parallel_agents < 1:
            raise ValueError("max_parallel_agents must be at least 1")

@dataclass
class BlackboardUpdate:
    """
    Represents a single update to the fleet blackboard.

    Attributes:
        agent_id: ID of the agent making the update
        update_type: Type of update (append, merge, replace)
        data: The actual update data
        version: Version number for optimistic locking
        timestamp: When the update was created
    """
    agent_id: str
    update_type: str  # append, merge, replace
    data: Dict[str, Any]
    version: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate update type after initialization."""
        valid_types = ["append", "merge", "replace"]
        if self.update_type not in valid_types:
            raise ValueError(
                f"Invalid update_type: {self.update_type}. "
                f"Must be one of {valid_types}"
            )

@dataclass
class FleetStateSnapshot:
    """
    Represents a point-in-time snapshot of fleet state.

    Attributes:
        chain_id: ID of the delegation chain (fleet)
        active_agents: List of agent IDs currently active in the fleet
        blackboard_version: Current version of the blackboard
        pending_tasks: List of task descriptions pending execution
        completed_tasks: List of task descriptions completed
        failed_tasks: List of task descriptions that failed
        timestamp: When the snapshot was captured
        metadata: Additional fleet metadata
    """
    chain_id: str
    active_agents: List[str] = field(default_factory=list)
    blackboard_version: int = 0
    pending_tasks: List[str] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary representation."""
        return {
            "chain_id": self.chain_id,
            "active_agents": self.active_agents,
            "blackboard_version": self.blackboard_version,
            "pending_tasks": self.pending_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

@dataclass
class ParallelExecutionRequest:
    """
    Request structure for parallel fleet execution.

    Attributes:
        chain_id: ID of the delegation chain
        task_groups: List of task groups where each group runs in parallel
        config: Execution configuration
    """
    chain_id: str
    task_groups: List[List[Dict[str, Any]]]
    config: Optional[FleetExecutionConfig] = None

    def __post_init__(self):
        """Validate request after initialization."""
        if not self.task_groups:
            raise ValueError("task_groups cannot be empty")
        if not self.config:
            self.config = FleetExecutionConfig()  # Use defaults

@dataclass
class RetryAttempt:
    """
    Represents a retry attempt with an alternative specialist.

    Attributes:
        retry_link_id: ID of the ChainLink created for retry
        alternative_agent_id: ID of the alternative agent used
        original_agent_id: ID of the original agent that failed
        reason: Why the retry was attempted
        timestamp: When the retry was created
    """
    retry_link_id: str
    alternative_agent_id: str
    original_agent_id: str
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "retry_link_id": self.retry_link_id,
            "alternative_agent_id": self.alternative_agent_id,
            "original_agent_id": self.original_agent_id,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class TaskExecutionResult:
    """
    Result of a single task execution.

    Attributes:
        agent_id: ID of the agent that executed the task
        task_description: Description of the task
        status: Final status of the task
        result: Task result data if successful
        error: Error message if failed
        retry_attempt: Information about retry if applicable
        group_index: Which execution group this task belonged to
        started_at: When task started
        completed_at: When task completed
    """
    agent_id: str
    task_description: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_attempt: Optional[RetryAttempt] = None
    group_index: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "agent_id": self.agent_id,
            "task_description": self.task_description,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "retry_attempt": self.retry_attempt.to_dict() if self.retry_attempt else None,
            "group_index": self.group_index,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

@dataclass
class FleetExecutionResult:
    """
    Result of a fleet execution with fault tolerance.

    Provides detailed breakdown of success/failure and retry attempts,
    enabling transparency into what was accomplished even when some
    agents fail.

    Attributes:
        chain_id: ID of the delegation chain
        total_tasks: Total number of tasks executed
        completed_count: Number of tasks that completed successfully
        failed_count: Number of tasks that failed (including retries)
        retried_count: Number of tasks that were retried with alternatives
        tasks: List of individual task results
        group_count: Number of execution groups processed
        execution_time_ms: Total execution time in milliseconds
        timestamp: When execution completed
        metadata: Additional execution metadata
    """
    chain_id: str
    total_tasks: int
    completed_count: int
    failed_count: int
    retried_count: int
    tasks: List[TaskExecutionResult] = field(default_factory=list)
    group_count: int = 0
    execution_time_ms: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage (0-100)."""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_count / self.total_tasks) * 100

    @property
    def has_failures(self) -> bool:
        """Check if any tasks failed."""
        return self.failed_count > 0

    @property
    def has_retries(self) -> bool:
        """Check if any tasks were retried."""
        return self.retried_count > 0

    def get_failed_tasks(self) -> List[TaskExecutionResult]:
        """Get list of failed tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]

    def get_retried_tasks(self) -> List[TaskExecutionResult]:
        """Get list of tasks that were retried."""
        return [t for t in self.tasks if t.retry_attempt is not None]

    def get_completed_tasks(self) -> List[TaskExecutionResult]:
        """Get list of successfully completed tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "chain_id": self.chain_id,
            "total_tasks": self.total_tasks,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "retried_count": self.retried_count,
            "success_rate": round(self.success_rate, 2),
            "has_failures": self.has_failures,
            "has_retries": self.has_retries,
            "tasks": [task.to_dict() for task in self.tasks],
            "group_count": self.group_count,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

@dataclass
class BatchExecutionRequest:
    """
    Request for batch fleet execution with fault tolerance.

    Attributes:
        chain_id: ID of the delegation chain
        task_groups: List of task groups where each group runs in parallel
        task_types: Optional list of task types for failure policy lookup
        enable_fault_tolerance: Whether to enable automatic retry with alternatives
    """
    chain_id: str
    task_groups: List[List[Dict[str, Any]]]
    task_types: Optional[List] = None
    enable_fault_tolerance: bool = True

    def __post_init__(self):
        """Validate request after initialization."""
        if not self.task_groups:
            raise ValueError("task_groups cannot be empty")
