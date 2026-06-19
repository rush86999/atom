"""
Workflow State Machine with Rollback Support

Based on 2025-2026 research:
- Hierarchical Multi-Agent Taxonomy (arXiv:2508.12683)
- AgentOrchestra Case Study (arXiv:2506.12508v4)

Implements:
- State machine for workflow execution
- State transitions with validation
- Rollback planning and execution
- State persistence and recovery
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from functools import wraps

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class WorkflowState(Enum):
    """States in workflow lifecycle"""
    CREATED = "created"
    VALIDATED = "validated"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING = "waiting"  # Waiting for external input
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    SUSPENDED = "suspended"  # For retry or manual intervention


class StateTransitionType(Enum):
    """Types of state transitions"""
    AUTOMATIC = "automatic"  # System-controlled
    USER_INITIATED = "user_initiated"  # User-triggered
    CONDITION_BASED = "condition_based"  # Based on conditions
    ERROR_DRIVEN = "error_driven"  # Due to error
    TIMEOUT_DRIVEN = "timeout_driven"  # Due to timeout


class TransitionResult(Enum):
    """Result of a state transition"""
    SUCCESS = "success"
    FAILED = "failed"
    INVALID = "invalid"
    SKIPPED = "skipped"  # Transition not needed
    BLOCKED = "blocked"  # Transition blocked by guard


@dataclass
class StateMachineConfig:
    """Configuration for state machine"""
    # Transitions
    allow_invalid_transitions: bool = False
    require_validations: bool = True
    transition_timeout_seconds: int = 30

    # Rollback
    enable_auto_rollback: bool = True
    rollback_timeout_seconds: int = 300
    max_rollback_attempts: int = 3

    # Persistence
    enable_persistence: bool = True
    persistence_interval_ms: int = 1000

    # Recovery
    enable_recovery: bool = True
    recovery_check_interval_seconds: int = 60


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class StateTransition:
    """A transition between states"""
    transition_id: str = ""
    from_state: WorkflowState = WorkflowState.CREATED
    to_state: WorkflowState = WorkflowState.RUNNING
    transition_type: StateTransitionType = StateTransitionType.AUTOMATIC

    # Guards
    guard_condition: Optional[str] = None
    guard_function: Optional[Callable] = None

    # Actions
    pre_action: Optional[str] = None
    post_action: Optional[str] = None
    action_function: Optional[Callable] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None
    result: TransitionResult = TransitionResult.SUCCESS

    # Context
    context: Dict[str, Any] = field(default_factory=dict)

    def can_execute(self, current_context: Dict[str, Any]) -> bool:
        """Check if transition can execute"""
        if self.guard_function:
            return self.guard_function(current_context)
        return True


@dataclass
class RollbackPlan:
    """Plan for rolling back a workflow"""
    plan_id: str = ""
    workflow_id: str = ""
    current_state: WorkflowState = WorkflowState.RUNNING
    target_state: WorkflowState = WorkflowState.ROLLED_BACK

    # Rollback steps
    rollback_states: List[WorkflowState] = field(default_factory=list)
    compensation_actions: List[str] = field(default_factory=list)

    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None

    # Execution
    attempts: int = 0
    max_attempts: int = 3
    executed: bool = False
    result: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if rollback plan has expired"""
        if self.expires_at:
            return datetime.now() > self.expires_at
        return False


@dataclass
class StateSnapshot:
    """Snapshot of workflow state for recovery"""
    snapshot_id: str = ""
    workflow_id: str = ""
    execution_id: str = ""

    # State
    current_state: WorkflowState = WorkflowState.CREATED
    step_states: Dict[str, str] = field(default_factory=dict)

    # Data
    context_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage"""
        return {
            "snapshot_id": self.snapshot_id,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "current_state": self.current_state.value,
            "step_states": self.step_states,
            "context_data": self.context_data,
            "output_data": self.output_data,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class TransitionLog:
    """Log of state transitions"""
    log_id: str = ""
    workflow_id: str = ""
    execution_id: str = ""

    from_state: WorkflowState = WorkflowState.CREATED
    to_state: WorkflowState = WorkflowState.RUNNING
    transition_type: StateTransitionType = StateTransitionType.AUTOMATIC
    result: TransitionResult = TransitionResult.SUCCESS

    triggered_by: str = "system"  # system, user, or specific agent
    reason: Optional[str] = None

    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0


# ============================================================================
# Workflow State Machine
# ============================================================================

class WorkflowStateMachine:
    """
    State machine for workflow execution lifecycle.

    Features:
    - Validated state transitions
    - Guard conditions
    - Pre/post transition actions
    - Rollback planning
    - State persistence
    - Recovery from failures
    """

    # Valid state transitions
    VALID_TRANSITIONS: Dict[WorkflowState, Set[WorkflowState]] = {
        WorkflowState.CREATED: {WorkflowState.VALIDATED, WorkflowState.CANCELLED},
        WorkflowState.VALIDATED: {WorkflowState.QUEUED, WorkflowState.CANCELLED},
        WorkflowState.QUEUED: {WorkflowState.RUNNING, WorkflowState.CANCELLED},
        WorkflowState.RUNNING: {WorkflowState.PAUSED, WorkflowState.WAITING, WorkflowState.COMPLETED, WorkflowState.FAILED, WorkflowState.CANCELLED},
        WorkflowState.PAUSED: {WorkflowState.RUNNING, WorkflowState.CANCELLED, WorkflowState.SUSPENDED},
        WorkflowState.WAITING: {WorkflowState.RUNNING, WorkflowState.FAILED, WorkflowState.CANCELLED},
        WorkflowState.COMPLETED: set(),  # Terminal state
        WorkflowState.FAILED: {WorkflowState.QUEUED, WorkflowState.SUSPENDED, WorkflowState.ROLLED_BACK, WorkflowState.CANCELLED},
        WorkflowState.CANCELLED: set(),  # Terminal state
        WorkflowState.ROLLING_BACK: {WorkflowState.ROLLED_BACK, WorkflowState.FAILED},
        WorkflowState.ROLLED_BACK: set(),  # Terminal state
        WorkflowState.SUSPENDED: {WorkflowState.QUEUED, WorkflowState.CANCELLED},
    }

    def __init__(self, config: Optional[StateMachineConfig] = None):
        self.config = config or StateMachineConfig()

        # State tracking
        self._workflow_states: Dict[str, WorkflowState] = {}
        self._transition_logs: Dict[str, List[TransitionLog]] = defaultdict(list)
        self._rollback_plans: Dict[str, RollbackPlan] = {}
        self._snapshots: Dict[str, List[StateSnapshot]] = defaultdict(list)

        # Guard functions
        self._guards: Dict[Tuple[WorkflowState, WorkflowState], Callable] = {}

        # Action functions
        self._pre_actions: Dict[Tuple[WorkflowState, WorkflowState], Callable] = {}
        self._post_actions: Dict[Tuple[WorkflowState, WorkflowState], Callable] = {}

    def initialize_state(
        self,
        workflow_id: str,
        execution_id: str,
        initial_state: WorkflowState = WorkflowState.CREATED
    ) -> None:
        """Initialize state for a workflow"""
        self._workflow_states[workflow_id] = initial_state

        # Log initial state
        log = TransitionLog(
            log_id=f"log_{workflow_id}_{initial_state.value}",
            workflow_id=workflow_id,
            execution_id=execution_id,
            from_state=initial_state,
            to_state=initial_state,
            result=TransitionResult.SUCCESS
        )
        self._transition_logs[workflow_id].append(log)

        logger.info(f"Initialized state for {workflow_id}: {initial_state.value}")

    def get_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """Get current state of workflow"""
        return self._workflow_states.get(workflow_id)

    def can_transition(
        self,
        workflow_id: str,
        to_state: WorkflowState
    ) -> bool:
        """Check if transition is valid"""
        current_state = self.get_state(workflow_id)
        if current_state is None:
            return False

        if self.config.allow_invalid_transitions:
            return True

        valid_targets = self.VALID_TRANSITIONS.get(current_state, set())
        return to_state in valid_targets

    def transition(
        self,
        workflow_id: str,
        execution_id: str,
        to_state: WorkflowState,
        transition_type: StateTransitionType = StateTransitionType.AUTOMATIC,
        triggered_by: str = "system",
        reason: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> TransitionResult:
        """
        Execute a state transition.

        Args:
            workflow_id: Workflow identifier
            execution_id: Execution identifier
            to_state: Target state
            transition_type: Type of transition
            triggered_by: Who triggered the transition
            reason: Reason for transition
            context: Additional context

        Returns:
            Transition result
        """
        current_state = self.get_state(workflow_id)
        if current_state is None:
            return TransitionResult.FAILED

        # Validate transition
        if not self.can_transition(workflow_id, to_state):
            logger.warning(
                f"Invalid transition: {workflow_id} {current_state.value} -> {to_state.value}"
            )
            return TransitionResult.INVALID

        # Check guards
        guard_key = (current_state, to_state)
        if guard_key in self._guards:
            if not self._guards[guard_key](context or {}):
                logger.info(f"Transition blocked by guard: {workflow_id}")
                return TransitionResult.BLOCKED

        start_time = datetime.now()

        # Execute pre-action
        if guard_key in self._pre_actions:
            try:
                self._pre_actions[guard_key](workflow_id, context or {})
            except Exception as e:
                logger.error(f"Pre-action failed: {e}")
                return TransitionResult.FAILED

        # Execute transition
        self._workflow_states[workflow_id] = to_state

        # Execute post-action
        if guard_key in self._post_actions:
            try:
                self._post_actions[guard_key](workflow_id, context or {})
            except Exception as e:
                logger.error(f"Post-action failed: {e}")

        # Calculate duration
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Log transition
        log = TransitionLog(
            log_id=f"log_{workflow_id}_{to_state.value}_{datetime.now().isoformat()}",
            workflow_id=workflow_id,
            execution_id=execution_id,
            from_state=current_state,
            to_state=to_state,
            transition_type=transition_type,
            result=TransitionResult.SUCCESS,
            triggered_by=triggered_by,
            reason=reason,
            duration_ms=duration_ms
        )
        self._transition_logs[workflow_id].append(log)

        logger.info(
            f"Transition: {workflow_id} {current_state.value} -> {to_state.value} "
            f"({duration_ms:.2f}ms)"
        )

        # Create snapshot after transition
        if self.config.enable_persistence:
            self._create_snapshot(workflow_id, execution_id)

        return TransitionResult.SUCCESS

    def add_guard(
        self,
        from_state: WorkflowState,
        to_state: WorkflowState,
        guard_function: Callable
    ) -> None:
        """Add guard condition for transition"""
        self._guards[(from_state, to_state)] = guard_function
        logger.debug(f"Added guard: {from_state.value} -> {to_state.value}")

    def add_pre_action(
        self,
        from_state: WorkflowState,
        to_state: WorkflowState,
        action_function: Callable
    ) -> None:
        """Add pre-transition action"""
        self._pre_actions[(from_state, to_state)] = action_function
        logger.debug(f"Added pre-action: {from_state.value} -> {to_state.value}")

    def add_post_action(
        self,
        from_state: WorkflowState,
        to_state: WorkflowState,
        action_function: Callable
    ) -> None:
        """Add post-transition action"""
        self._post_actions[(from_state, to_state)] = action_function
        logger.debug(f"Added post-action: {from_state.value} -> {to_state.value}")

    def create_rollback_plan(
        self,
        workflow_id: str,
        execution_id: str,
        compensation_actions: List[str]
    ) -> RollbackPlan:
        """Create a rollback plan for the workflow"""
        current_state = self.get_state(workflow_id)
        if current_state is None:
            raise ValueError(f"Workflow {workflow_id} not found")

        plan_id = f"rollback_{workflow_id}_{datetime.now().isoformat()}"

        # Calculate rollback path
        rollback_states = [
            WorkflowState.RUNNING,
            WorkflowState.ROLLING_BACK,
            WorkflowState.ROLLED_BACK
        ]

        plan = RollbackPlan(
            plan_id=plan_id,
            workflow_id=workflow_id,
            current_state=current_state,
            target_state=WorkflowState.ROLLED_BACK,
            rollback_states=rollback_states,
            compensation_actions=compensation_actions,
            expires_at=datetime.now() + timedelta(seconds=self.config.rollback_timeout_seconds)
        )

        self._rollback_plans[workflow_id] = plan
        logger.info(f"Created rollback plan: {plan_id}")

        return plan

    async def execute_rollback(
        self,
        workflow_id: str,
        execution_id: str
    ) -> TransitionResult:
        """Execute rollback plan"""
        plan = self._rollback_plans.get(workflow_id)
        if not plan:
            logger.warning(f"No rollback plan for {workflow_id}")
            return TransitionResult.FAILED

        if plan.is_expired():
            logger.warning(f"Rollback plan expired for {workflow_id}")
            return TransitionResult.FAILED

        plan.attempts += 1

        # Transition to rolling back
        result = self.transition(
            workflow_id,
            execution_id,
            WorkflowState.ROLLING_BACK,
            transition_type=StateTransitionType.ERROR_DRIVEN,
            reason="Executing rollback plan"
        )

        if result != TransitionResult.SUCCESS:
            return result

        # Execute compensation actions
        for action in plan.compensation_actions:
            try:
                # In production, execute actual compensation
                logger.info(f"Executing compensation: {action}")
                await asyncio.sleep(0.1)  # Simulate execution
            except Exception as e:
                logger.error(f"Compensation failed: {action} - {e}")
                if plan.attempts >= plan.max_attempts:
                    return TransitionResult.FAILED

        # Transition to rolled back
        result = self.transition(
            workflow_id,
            execution_id,
            WorkflowState.ROLLED_BACK,
            transition_type=StateTransitionType.ERROR_DRIVEN,
            reason="Rollback complete"
        )

        plan.executed = True
        plan.result = "success" if result == TransitionResult.SUCCESS else "failed"

        return result

    def _create_snapshot(
        self,
        workflow_id: str,
        execution_id: str
    ) -> StateSnapshot:
        """Create snapshot of current state"""
        current_state = self.get_state(workflow_id)
        if current_state is None:
            return None

        snapshot = StateSnapshot(
            snapshot_id=f"snap_{workflow_id}_{datetime.now().isoformat()}",
            workflow_id=workflow_id,
            execution_id=execution_id,
            current_state=current_state
        )

        self._snapshots[workflow_id].append(snapshot)

        # Keep only last 100 snapshots
        if len(self._snapshots[workflow_id]) > 100:
            self._snapshots[workflow_id] = self._snapshots[workflow_id][-100:]

        return snapshot

    def get_snapshots(
        self,
        workflow_id: str,
        limit: int = 10
    ) -> List[StateSnapshot]:
        """Get snapshots for a workflow"""
        return self._snapshots.get(workflow_id, [])[-limit:]

    def restore_from_snapshot(
        self,
        workflow_id: str,
        snapshot: StateSnapshot
    ) -> bool:
        """Restore state from snapshot"""
        try:
            self._workflow_states[workflow_id] = snapshot.current_state
            logger.info(f"Restored state for {workflow_id} from snapshot")
            return True
        except Exception as e:
            logger.error(f"Failed to restore snapshot: {e}")
            return False

    def get_transition_history(
        self,
        workflow_id: str,
        limit: int = 100
    ) -> List[TransitionLog]:
        """Get transition history for a workflow"""
        return self._transition_logs.get(workflow_id, [])[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get state machine statistics"""
        state_counts = defaultdict(int)
        for state in self._workflow_states.values():
            state_counts[state.value] += 1

        return {
            "total_workflows": len(self._workflow_states),
            "state_distribution": dict(state_counts),
            "total_transitions": sum(len(logs) for logs in self._transition_logs.values()),
            "rollback_plans": len(self._rollback_plans),
            "total_snapshots": sum(len(snaps) for snaps in self._snapshots.values())
        }


# ============================================================================
# Factory
# ============================================================================

_state_machine_instance: Optional[WorkflowStateMachine] = None


def get_state_machine(config: Optional[StateMachineConfig] = None) -> WorkflowStateMachine:
    """Get or create state machine instance"""
    global _state_machine_instance
    if _state_machine_instance is None:
        _state_machine_instance = WorkflowStateMachine(config)
    return _state_machine_instance
