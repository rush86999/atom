"""
Conductor Agent Pattern for Complex Workflows

Based on 2025-2026 research:
- Hierarchical Multi-Agent Taxonomy (arXiv:2508.12683)
- AgentOrchestra Case Study (arXiv:2506.12508v4)
- Enterprise Agent Workflows

The Conductor Agent is a centralized orchestrator that:
- Coordinates complex multi-step workflows
- Manages event-driven triggers
- Handles parallel and sequential execution
- Provides atomic execution with rollback
- Monitors and adapts to execution changes
"""

import asyncio
import hashlib
import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Awaitable
from concurrent.futures import ThreadPoolExecutor
from functools import partial

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class ExecutionStrategy(Enum):
    """Workflow execution strategies"""
    SEQUENTIAL = "sequential"  # Execute steps one by one
    PARALLEL = "parallel"  # Execute independent steps in parallel
    HYBRID = "hybrid"  # Mix of sequential and parallel
    ADAPTIVE = "adaptive"  # Adapt based on runtime conditions
    ROLLBACK_SAFE = "rollback_safe"  # Execute with rollback support


class ExecutionStatus(Enum):
    """Status of workflow execution"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class StepType(Enum):
    """Types of workflow steps"""
    TRIGGER = "trigger"  # Event trigger
    AGENT = "agent"  # Agent execution
    INTEGRATION = "integration"  # External service call
    CONDITION = "condition"  # Conditional branch
    PARALLEL = "parallel"  # Parallel execution block
    MERGE = "merge"  # Merge parallel branches
    COMPENSATION = "compensation"  # Rollback compensation
    NOTIFY = "notify"  # Notification step


@dataclass
class ConductorConfig:
    """Configuration for Conductor Agent"""
    # Execution
    max_concurrent_steps: int = 5
    step_timeout_seconds: int = 300
    workflow_timeout_seconds: int = 3600

    # Retry
    max_retries: int = 3
    retry_backoff_ms: int = 1000
    retry_jitter: float = 0.1

    # Rollback
    enable_rollback: bool = True
    rollback_on_failure: bool = False
    compensation_timeout_seconds: int = 120

    # Monitoring
    enable_monitoring: bool = True
    heartbeat_interval_ms: int = 5000
    metrics_collection: bool = True

    # Adaptive execution
    enable_adaptive: bool = True
    adaptation_threshold: float = 0.7  # Confidence threshold

    # Event-driven
    enable_events: bool = True
    event_timeout_seconds: int = 30


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class WorkflowStep:
    """A step in a workflow"""
    step_id: str = ""
    step_type: StepType = StepType.AGENT
    name: str = ""
    description: str = ""

    # Execution
    agent_id: Optional[str] = None
    capability: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)

    # Conditions
    condition: Optional[str] = None  # Python expression
    condition_met: bool = True

    # Parallel execution
    parallel_group: Optional[str] = None
    is_parallel_root: bool = False

    # Compensation (rollback)
    compensation_step_id: Optional[str] = None
    compensation_parameters: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300

    # State
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def can_execute(self, completed_steps: Set[str]) -> bool:
        """Check if step can be executed"""
        if not self.condition_met:
            return False
        return all(dep in completed_steps for dep in self.depends_on)


@dataclass
class WorkflowExecutionContext:
    """Context for workflow execution"""
    workflow_id: str = ""
    execution_id: str = ""
    tenant_id: str = ""
    user_id: str = ""
    workspace_id: str = ""

    # Steps
    steps: List[WorkflowStep] = field(default_factory=list)
    start_step: str = ""

    # State tracking
    completed_steps: Set[str] = field(default_factory=set)
    failed_steps: Set[str] = field(default_factory=set)
    current_step: Optional[str] = None

    # Data flow
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    shared_context: Dict[str, Any] = field(default_factory=dict)

    # Execution
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Strategy
    strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL

    # Rollback
    rollback_stack: List[str] = field(default_factory=list)
    compensation_enabled: bool = True

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """Get step by ID"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_next_steps(self, step_id: str) -> List[WorkflowStep]:
        """Get next steps after a given step"""
        step = self.get_step(step_id)
        if not step:
            return []

        next_steps = []
        for next_id in step.next_steps:
            next_step = self.get_step(next_id)
            if next_step:
                next_steps.append(next_step)
        return next_steps

    def get_ready_steps(self) -> List[WorkflowStep]:
        """Get steps that are ready to execute"""
        ready = []
        for step in self.steps:
            if step.status == ExecutionStatus.PENDING and step.can_execute(self.completed_steps):
                ready.append(step)
        return ready

    def is_complete(self) -> bool:
        """Check if workflow is complete"""
        # Either all steps are complete, or we've reached a terminal state
        if self.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            return True

        # Check if all steps are completed or failed (allow partial completion)
        all_terminal = all(
            s.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]
            for s in self.steps
        )
        return all_terminal

    def get_progress(self) -> float:
        """Get workflow progress (0-1)"""
        if not self.steps:
            return 0.0
        completed = len([s for s in self.steps if s.status == ExecutionStatus.COMPLETED])
        return completed / len(self.steps)


@dataclass
class OrchestrationResult:
    """Result of workflow orchestration"""
    workflow_id: str = ""
    execution_id: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Dict[str, Any] = field(default_factory=dict)

    # Metrics
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0

    # Rollback
    rolled_back: bool = False
    rollback_reason: Optional[str] = None

    # Errors
    errors: List[str] = field(default_factory=list)

    def was_successful(self) -> bool:
        """Check if orchestration was successful"""
        return (
            self.status == ExecutionStatus.COMPLETED
            and self.failed_steps == 0
            and not self.rolled_back
        )


# ============================================================================
# Conductor Agent
# ============================================================================

class ConductorAgent:
    """
    Centralized conductor for complex workflow orchestration.

    The Conductor Agent provides:
    - Complex workflow coordination
    - Event-driven triggering
    - Parallel and sequential execution
    - Atomic execution with rollback
    - Adaptive execution based on runtime conditions

    Hierarchy:
    - Queen Agent: Blueprint generation
    - Conductor Agent: Workflow execution coordination
    - Specialist Agents: Task execution
    """

    def __init__(self, config: Optional[ConductorConfig] = None):
        self.config = config or ConductorConfig()
        # Injectable step executor. Defaults to the mock stub; the conductor
        # endpoint injects the real WorkflowEngine step dispatcher so the
        # Conductor runs actual AI/webhook/tool steps instead of mock sleep.
        self._step_executor: Optional[Callable] = None

        # Execution tracking
        self._active_workflows: Dict[str, WorkflowExecutionContext] = {}
        self._completed_workflows: Dict[str, OrchestrationResult] = {}
        self._rollback_plans: Dict[str, List[str]] = {}

        # Executor for parallel steps
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_steps)

        # Event subscriptions
        self._event_subscriptions: Dict[str, List[Callable]] = defaultdict(list)

    async def execute_workflow(
        self,
        steps: List[WorkflowStep],
        start_step: str,
        context: Optional[WorkflowExecutionContext] = None,
        strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL
    ) -> OrchestrationResult:
        """
        Execute a workflow with the given steps.

        Args:
            steps: List of workflow steps
            start_step: ID of the starting step
            context: Optional existing context
            strategy: Execution strategy

        Returns:
            Orchestration result
        """
        # Create or update context
        if not context:
            execution_id = f"exec_{uuid.uuid4().hex[:16]}"
            context = WorkflowExecutionContext(
                workflow_id=f"wf_{uuid.uuid4().hex[:16]}",
                execution_id=execution_id,
                steps=steps,
                start_step=start_step,
                strategy=strategy
            )

        context.started_at = datetime.now()
        context.status = ExecutionStatus.RUNNING
        context.current_step = start_step

        self._active_workflows[context.execution_id] = context

        result = OrchestrationResult(
            workflow_id=context.workflow_id,
            execution_id=context.execution_id,
            started_at=context.started_at,
            total_steps=len(steps)
        )

        try:
            # Execute based on strategy
            if strategy == ExecutionStrategy.SEQUENTIAL:
                await self._execute_sequential(context, result)
            elif strategy == ExecutionStrategy.PARALLEL:
                await self._execute_parallel(context, result)
            elif strategy == ExecutionStrategy.HYBRID:
                await self._execute_hybrid(context, result)
            elif strategy == ExecutionStrategy.ADAPTIVE:
                await self._execute_adaptive(context, result)
            else:
                await self._execute_rollback_safe(context, result)

            # Check final status
            if context.is_complete() and not result.failed_steps:
                context.status = ExecutionStatus.COMPLETED
                result.status = ExecutionStatus.COMPLETED
            elif result.failed_steps > 0:
                context.status = ExecutionStatus.FAILED
                result.status = ExecutionStatus.FAILED

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            context.status = ExecutionStatus.FAILED
            result.status = ExecutionStatus.FAILED
            result.errors.append(str(e))

            # Rollback if enabled
            if self.config.enable_rollback and self.config.rollback_on_failure:
                await self._rollback_workflow(context, result)

        finally:
            context.completed_at = datetime.now()
            result.completed_at = context.completed_at
            result.duration_seconds = (
                context.completed_at - context.started_at
            ).total_seconds() if context.completed_at and context.started_at else 0

            # Move to completed
            self._active_workflows.pop(context.execution_id, None)
            self._completed_workflows[context.execution_id] = result

        return result

    async def _execute_sequential(
        self,
        context: WorkflowExecutionContext,
        result: OrchestrationResult
    ) -> None:
        """Execute workflow steps sequentially"""
        current_id = context.start_step

        while current_id and not context.is_complete():
            step = context.get_step(current_id)
            if not step:
                break

            # Check if step can execute
            if not step.can_execute(context.completed_steps):
                current_id = None
                break

            # Mark as running
            step.status = ExecutionStatus.RUNNING
            step.started_at = datetime.now()
            context.current_step = current_id

            try:
                # Execute step with timeout
                step_result = await asyncio.wait_for(
                    self._execute_step(step, context),
                    timeout=step.timeout_seconds
                )

                step.status = ExecutionStatus.COMPLETED
                step.completed_at = datetime.now()
                step.result = step_result
                context.completed_steps.add(current_id)
                result.completed_steps += 1

                # Merge result into output
                if step_result:
                    context.output_data.update(step_result)

            except asyncio.TimeoutError:
                step.status = ExecutionStatus.FAILED
                step.error = "Timeout"
                result.failed_steps += 1
                current_id = None
                break

            except Exception as e:
                step.status = ExecutionStatus.FAILED
                step.error = str(e)
                result.failed_steps += 1
                result.errors.append(f"Step {current_id} failed: {e}")

                if step.retry_count < step.max_retries:
                    step.retry_count += 1
                    step.status = ExecutionStatus.PENDING
                    # Retry this step
                    continue
                else:
                    current_id = None
                    break

            # Move to next step
            next_steps = context.get_next_steps(current_id)
            if next_steps:
                current_id = next_steps[0].step_id
            else:
                current_id = None

    async def _execute_parallel(
        self,
        context: WorkflowExecutionContext,
        result: OrchestrationResult
    ) -> None:
        """Execute workflow steps in parallel where possible"""
        # Find all ready steps
        ready_steps = context.get_ready_steps()

        while ready_steps and not context.is_complete():
            # Execute ready steps in parallel
            tasks = []
            for step in ready_steps:
                task = asyncio.create_task(
                    self._execute_and_track(step, context, result)
                )
                tasks.append(task)

            # Wait for batch
            await asyncio.gather(*tasks, return_exceptions=True)

            # Get next ready steps
            ready_steps = context.get_ready_steps()

    async def _execute_hybrid(
        self,
        context: WorkflowExecutionContext,
        result: OrchestrationResult
    ) -> None:
        """Execute workflow with hybrid strategy (parallel + sequential)"""
        # Identify parallel blocks
        parallel_blocks = self._identify_parallel_blocks(context)

        for block in parallel_blocks:
            if len(block) == 1:
                # Single step - sequential execution
                step = block[0]
                await self._execute_single_step(step, context, result)
            else:
                # Parallel block - execute in parallel
                tasks = []
                for step in block:
                    task = asyncio.create_task(
                        self._execute_and_track(step, context, result)
                    )
                    tasks.append(task)

                await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_adaptive(
        self,
        context: WorkflowExecutionContext,
        result: OrchestrationResult
    ) -> None:
        """Execute workflow with adaptive strategy based on conditions"""
        current_id = context.start_step

        while current_id and not context.is_complete():
            step = context.get_step(current_id)
            if not step:
                break

            # Check condition
            if step.condition:
                condition_met = self._evaluate_condition(step.condition, context)
                if not condition_met:
                    # Skip this step and its branch
                    step.status = ExecutionStatus.COMPLETED
                    step.condition_met = False
                    context.completed_steps.add(current_id)
                    result.skipped_steps += 1

                    # Try next branch
                    next_steps = context.get_next_steps(current_id)
                    if next_steps:
                        current_id = next_steps[0].step_id
                    else:
                        current_id = None
                    continue

            # Execute based on step type and dependencies
            if step.parallel_group and self._can_execute_parallel_group(step, context):
                # Execute entire parallel group
                await self._execute_parallel_group(step, context, result)
            else:
                await self._execute_single_step(step, context, result)

            # Move to next step
            next_steps = context.get_next_steps(current_id)
            if next_steps:
                current_id = next_steps[0].step_id
            else:
                current_id = None

    async def _execute_rollback_safe(
        self,
        context: WorkflowExecutionContext,
        result: OrchestrationResult
    ) -> None:
        """Execute workflow with rollback support"""
        # Execute sequentially but track compensation
        current_id = context.start_step

        while current_id and not context.is_complete():
            step = context.get_step(current_id)
            if not step:
                break

            if not step.can_execute(context.completed_steps):
                current_id = None
                break

            # Add to rollback stack
            if step.compensation_step_id:
                context.rollback_stack.append(step.step_id)

            await self._execute_single_step(step, context, result)

            if result.failed_steps > 0 and self.config.rollback_on_failure:
                # Trigger rollback
                await self._rollback_workflow(context, result)
                break

            # Move to next step
            next_steps = context.get_next_steps(current_id)
            if next_steps:
                current_id = next_steps[0].step_id
            else:
                current_id = None

    async def _execute_step(
        self,
        step: WorkflowStep,
        context: WorkflowExecutionContext
    ) -> Dict[str, Any]:
        """Execute a single workflow step.

        If a real step executor was injected (via ``set_step_executor``),
        delegates to it so the Conductor runs actual AI/webhook/tool steps.
        Otherwise falls back to the mock stub (for tests and standalone use).
        """
        if self._step_executor is not None:
            try:
                result = self._step_executor(step, context)
                if asyncio.iscoroutine(result):
                    result = await result
                if isinstance(result, dict):
                    return result
                return {"step_id": step.step_id, "status": "completed", "output": str(result)}
            except Exception as e:
                logger.error(f"Injected step executor failed for {step.step_id}: {e}")
                return {"step_id": step.step_id, "status": "failed", "error": str(e)}

        # Mock fallback (original behavior)
        logger.info(f"Executing step (mock): {step.step_id} ({step.name})")
        await asyncio.sleep(0.1)
        return {
            "step_id": step.step_id,
            "status": "completed",
            "output": f"Result from {step.name}"
        }

    def set_step_executor(self, executor: Callable) -> None:
        """Inject a real step executor (e.g. WorkflowEngine._execute_step).

        When set, the Conductor delegates step execution to this callable
        instead of the mock stub, so it runs actual AI/webhook/tool steps.
        """
        self._step_executor = executor

    async def _execute_and_track(
        self,
        step: WorkflowStep,
        context: WorkflowExecutionContext,
        result: OrchestrationResult
    ) -> None:
        """Execute step and track result"""
        step.status = ExecutionStatus.RUNNING
        step.started_at = datetime.now()

        try:
            step_result = await asyncio.wait_for(
                self._execute_step(step, context),
                timeout=step.timeout_seconds
            )

            step.status = ExecutionStatus.COMPLETED
            step.completed_at = datetime.now()
            step.result = step_result
            context.completed_steps.add(step.step_id)
            result.completed_steps += 1

        except Exception as e:
            step.status = ExecutionStatus.FAILED
            step.error = str(e)
            result.failed_steps += 1
            result.errors.append(f"Step {step.step_id} failed: {e}")

    async def _execute_single_step(
        self,
        step: WorkflowStep,
        context: WorkflowExecutionContext,
        result: OrchestrationResult
    ) -> None:
        """Execute a single step with tracking"""
        await self._execute_and_track(step, context, result)

    async def _execute_parallel_group(
        self,
        step: WorkflowStep,
        context: WorkflowExecutionContext,
        result: OrchestrationResult
    ) -> None:
        """Execute a parallel group of steps"""
        # Find all steps in the same parallel group
        group_steps = [
            s for s in context.steps
            if s.parallel_group == step.parallel_group
            and s.status == ExecutionStatus.PENDING
            and s.can_execute(context.completed_steps)
        ]

        tasks = []
        for group_step in group_steps:
            task = asyncio.create_task(
                self._execute_and_track(group_step, context, result)
            )
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    def _identify_parallel_blocks(
        self,
        context: WorkflowExecutionContext
    ) -> List[List[WorkflowStep]]:
        """Identify parallel execution blocks"""
        blocks = []
        processed = set()

        for step in context.steps:
            if step.step_id in processed:
                continue

            if step.is_parallel_root:
                # Find all steps in this parallel block
                block = [step]
                processed.add(step.step_id)

                for other in context.steps:
                    if other.parallel_group == step.parallel_group and other.step_id not in processed:
                        block.append(other)
                        processed.add(other.step_id)

                blocks.append(block)
            else:
                # Sequential block
                blocks.append([step])
                processed.add(step.step_id)

        return blocks

    def _can_execute_parallel_group(
        self,
        step: WorkflowStep,
        context: WorkflowExecutionContext
    ) -> bool:
        """Check if all steps in parallel group can execute"""
        group_steps = [
            s for s in context.steps
            if s.parallel_group == step.parallel_group
        ]

        return all(s.can_execute(context.completed_steps) for s in group_steps)

    def _evaluate_condition(
        self,
        condition: str,
        context: WorkflowExecutionContext
    ) -> bool:
        """Evaluate a condition expression.

        SECURITY: uses AST-validated safe_eval to prevent code injection
        via workflow conditions. Raw eval() — even with __builtins__={}
        — is bypassable via attribute access on context objects.
        """
        try:
            from core.safe_evaluator import safe_eval, SafeEvalError
            try:
                return bool(safe_eval(condition, context.shared_context))
            except SafeEvalError as e:
                logger.warning(f"Condition rejected by safe_eval: {e}")
                return False
        except Exception as e:
            logger.warning(f"Condition evaluation failed: {e}")
            return False

    async def _rollback_workflow(
        self,
        context: WorkflowExecutionContext,
        result: OrchestrationResult
    ) -> None:
        """Execute compensation actions for rollback"""
        logger.info(f"Rolling back workflow {context.workflow_id}")

        # Execute compensation in reverse order
        for step_id in reversed(context.rollback_stack):
            step = context.get_step(step_id)
            if not step or not step.compensation_step_id:
                continue

            comp_step = context.get_step(step.compensation_step_id)
            if not comp_step:
                continue

            try:
                await asyncio.wait_for(
                    self._execute_step(comp_step, context),
                    timeout=self.config.compensation_timeout_seconds
                )
                logger.info(f"Compensation executed: {comp_step.step_id}")
            except Exception as e:
                logger.error(f"Compensation failed: {comp_step.step_id} - {e}")
                result.errors.append(f"Compensation failed: {e}")

        result.rolled_back = True
        result.rollback_reason = "Workflow execution failed"

    def pause_workflow(self, execution_id: str) -> bool:
        """Pause a running workflow"""
        if execution_id not in self._active_workflows:
            return False

        context = self._active_workflows[execution_id]
        context.status = ExecutionStatus.PAUSED
        logger.info(f"Paused workflow {execution_id}")
        return True

    def resume_workflow(self, execution_id: str) -> bool:
        """Resume a paused workflow"""
        if execution_id not in self._active_workflows:
            return False

        context = self._active_workflows[execution_id]
        if context.status != ExecutionStatus.PAUSED:
            return False

        context.status = ExecutionStatus.RUNNING
        logger.info(f"Resumed workflow {execution_id}")
        return True

    def cancel_workflow(self, execution_id: str) -> bool:
        """Cancel a running workflow"""
        if execution_id in self._active_workflows:
            context = self._active_workflows[execution_id]
            context.status = ExecutionStatus.CANCELLED
            logger.info(f"Cancelled workflow {execution_id}")
            return True
        return False

    def get_workflow_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a workflow"""
        if execution_id in self._active_workflows:
            context = self._active_workflows[execution_id]
            return {
                "execution_id": execution_id,
                "workflow_id": context.workflow_id,
                "status": context.status.value,
                "progress": context.get_progress(),
                "current_step": context.current_step,
                "completed_steps": len(context.completed_steps),
                "total_steps": len(context.steps)
            }
        elif execution_id in self._completed_workflows:
            result = self._completed_workflows[execution_id]
            return {
                "execution_id": execution_id,
                "workflow_id": result.workflow_id,
                "status": result.status.value,
                "completed_steps": result.completed_steps,
                "failed_steps": result.failed_steps,
                "duration_seconds": result.duration_seconds
            }
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get conductor statistics"""
        return {
            "active_workflows": len(self._active_workflows),
            "completed_workflows": len(self._completed_workflows),
            "event_subscriptions": sum(len(subs) for subs in self._event_subscriptions.values()),
            "config": {
                "max_concurrent_steps": self.config.max_concurrent_steps,
                "enable_rollback": self.config.enable_rollback,
                "enable_adaptive": self.config.enable_adaptive
            }
        }


# ============================================================================
# Factory
# ============================================================================

_conductor_instance: Optional[ConductorAgent] = None


def get_conductor_agent(config: Optional[ConductorConfig] = None) -> ConductorAgent:
    """Get or create conductor agent instance"""
    global _conductor_instance
    if _conductor_instance is None:
        _conductor_instance = ConductorAgent(config)
    return _conductor_instance
