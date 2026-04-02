"""
FleetCoordinatorService for orchestrating parallel fleet execution.

This service provides high-level coordination for multi-agent fleets,
including batch recruitment, grouped parallel task execution, and
real-time state synchronization via Redis pub/sub.
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from core.agent_fleet_service import AgentFleetService
from core.models import DelegationChain, ChainLink
from .fleet_execution_models import (
    FleetExecutionConfig,
    FleetStateSnapshot,
    ParallelExecutionRequest,
    FleetExecutionResult,
    TaskExecutionResult,
    TaskStatus,
    RetryAttempt
)
from .fault_tolerance_service import FaultToleranceService
from .task_decomposition_service import TaskDecompositionService, TaskDecomposition
from .dependency_graph_service import DependencyGraphService
from .complexity_estimator import ComplexityEstimator
from .fleet_tracing_service import FleetTracingService, TraceContext
from core.fleet.fleet_task_types import FleetTaskType

logger = logging.getLogger(__name__)

class FleetCoordinatorService:
    """
    Orchestrates parallel execution of multi-agent fleets.

    Provides batch recruitment, grouped task execution with asyncio.gather,
    and real-time state change notifications via Redis pub/sub.

    Coordinates with AgentFleetService for fleet management and
    DistributedBlackboardService for state synchronization.
    """

    def __init__(
        self,
        db: Session,
        blackboard_service=None,
        decomposition_service=None,
        dependency_service=None,
        complexity_estimator=None,
        tracing_service=None
    ):
        """
        Initialize the fleet coordinator.

        Args:
            db: Database session for persistence
            blackboard_service: Optional DistributedBlackboardService for Redis pub/sub
            decomposition_service: Optional TaskDecompositionService for task decomposition
            dependency_service: Optional DependencyGraphService for graph operations
            complexity_estimator: Optional ComplexityEstimator for fleet sizing
            tracing_service: Optional FleetTracingService for distributed tracing
        """
        self.db = db
        self.blackboard_service = blackboard_service
        self.fleet_service = AgentFleetService(db)
        self.fault_tolerance = FaultToleranceService(db)

        # Initialize decomposition services (lazy initialization pattern)
        self.decomposition_service = decomposition_service
        self.dependency_service = dependency_service
        self.complexity_estimator = complexity_estimator

        # Initialize tracing service (lazy initialization pattern)
        self.tracing_service = tracing_service

    async def recruit_parallel_batch(
        self,
        chain_id: str,
        parent_agent_id: str,
        recruitments: List[Dict[str, Any]]
    ) -> List[ChainLink]:
        """
        Recruit multiple specialist agents to a fleet in a single batch operation.

        This is the primary method for parallel fleet expansion, allowing
        multiple specialists to be recruited simultaneously.

        Args:
            chain_id: The delegation chain to recruit to
            parent_agent_id: The agent doing the recruiting
            recruitments: List of recruitment dicts with keys:
                - child_agent_id: str (required)
                - task_description: str (required)
                - context_json: Dict[str, Any] (optional)
                - optimization_metadata: Dict[str, Any] (optional)

        Returns:
            List of created ChainLink objects

        Raises:
            ValueError: If chain not found or invalid recruitment data
        """
        logger.info(
            f"Recruiting parallel batch of {len(recruitments)} members "
            f"for chain {chain_id} by parent {parent_agent_id}"
        )

        # Start recruitment span (graceful degradation)
        recruitment_span = None
        try:
            if self.tracing_service:
                # Lazy initialize if needed
                if self.tracing_service is None:
                    self.tracing_service = FleetTracingService(self.db)

                recruitment_span = self.tracing_service.start_agent_span(
                    chain_id=chain_id,
                    agent_id=parent_agent_id,
                    task_description=f"Recruit {len(recruitments)} fleet members",
                    parent_context=None
                )
        except Exception as e:
            logger.warning(f"Failed to start recruitment span: {e}")

        # Use AgentFleetService.recruit_batch for atomic batch creation
        links = self.fleet_service.recruit_batch(
            chain_id=chain_id,
            parent_agent_id=parent_agent_id,
            recruitments=recruitments,
            link_order_start=0
        )

        # Publish fleet state update
        await self.notify_fleet_state_change(
            chain_id=chain_id,
            event_type="fleet_expanded",
            data={
                "new_members": len(links),
                "parent_agent_id": parent_agent_id,
                "recruited_at": datetime.now(timezone.utc).isoformat()
            }
        )

        # Finish recruitment span
        try:
            if recruitment_span and self.tracing_service:
                self.tracing_service.finish_span(
                    context=recruitment_span,
                    status="completed",
                    result_summary=f"Recruited {len(links)} fleet members"
                )
        except Exception as e:
            logger.warning(f"Failed to finish recruitment span: {e}")

        logger.info(f"Successfully recruited {len(links)} fleet members for chain {chain_id}")
        return links

    async def execute_parallel_task(
        self,
        chain_id: str,
        task_groups: List[List[Dict[str, Any]]],
        task_types: Optional[List[FleetTaskType]] = None,
        enable_fault_tolerance: bool = True
    ) -> FleetExecutionResult:
        """
        Execute tasks in grouped parallel fashion with fault tolerance.

        Tasks within each group execute in parallel using asyncio.gather.
        Failed tasks are retried with alternative specialists when policy allows.

        Args:
            chain_id: The delegation chain executing the tasks
            task_groups: List of task groups where each group runs in parallel
                Each task is a dict with at least: {agent_id, task_description}
            task_types: Optional list of task types corresponding to each task
                (used for failure policy lookup)
            enable_fault_tolerance: Whether to enable automatic retry with alternatives

        Returns:
            FleetExecutionResult with detailed breakdown of success/failure/retries

        Example:
            task_groups = [
                [  # Group 1: Run in parallel
                    {"agent_id": "agent-1", "task": "Analyze data"},
                    {"agent_id": "agent-2", "task": "Fetch external"}
                ],
                [  # Group 2: Run after Group 1 completes
                    {"agent_id": "agent-3", "task": "Synthesize results"}
                ]
            ]
        """
        import time
        start_time = time.time()

        # Get tenant_id from chain for tracing
        chain = self.db.query(DelegationChain).filter(
            DelegationChain.id == chain_id
        ).first()
        tenant_id = chain.tenant_id if chain else None

        # Start fleet trace (graceful degradation if tracing unavailable)
        fleet_trace_context = None
        try:
            if self.tracing_service:
                # Lazy initialize if needed
                if self.tracing_service is None:
                    self.tracing_service = FleetTracingService(self.db)

                # Get root task summary from first group
                root_task = f"{len(task_groups)} task groups, {sum(len(g) for g in task_groups)} total tasks"
                fleet_trace_context = self.tracing_service.start_fleet_trace(
                    chain_id=chain_id,
                    tenant_id=tenant_id or "unknown",
                    root_task=root_task
                )
        except Exception as e:
            logger.warning(f"Failed to start fleet trace: {e}")

        logger.info(
            f"Executing parallel tasks for chain {chain_id}: "
            f"{len(task_groups)} groups, "
            f"{sum(len(g) for g in task_groups)} total tasks"
        )

        # Track all task results
        all_task_results: List[TaskExecutionResult] = []
        retried_count = 0
        completed_count = 0
        failed_count = 0

        # Track agent spans for finishing
        agent_spans: Dict[str, TraceContext] = {}

        # Process each group sequentially
        for group_idx, group in enumerate(task_groups):
            logger.info(
                f"Starting group {group_idx + 1}/{len(task_groups)} "
                f"with {len(group)} parallel tasks"
            )

            # Record start time for this group
            group_start_time = datetime.now(timezone.utc)

            # Start agent spans for each task (graceful degradation)
            for task in group:
                agent_id = task.get("agent_id", "unknown")
                task_description = task.get("task_description", task.get("task", ""))
                try:
                    if self.tracing_service and fleet_trace_context:
                        agent_span = self.tracing_service.start_agent_span(
                            chain_id=chain_id,
                            agent_id=agent_id,
                            task_description=task_description,
                            parent_context=fleet_trace_context
                        )
                        agent_spans[agent_id] = agent_span
                except Exception as e:
                    logger.warning(f"Failed to start agent span for {agent_id}: {e}")

            # Execute all tasks in this group in parallel
            tasks = [
                self._execute_single_task(chain_id, task)
                for task in group
            ]

            # Wait for all tasks in group to complete
            group_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(group_results):
                task_info = group[i]
                agent_id = task_info.get("agent_id", "unknown")
                task_description = task_info.get("task_description", task_info.get("task", ""))
                task_type = task_types[i] if task_types and i < len(task_types) else None

                task_result = TaskExecutionResult(
                    agent_id=agent_id,
                    task_description=task_description,
                    status=TaskStatus.COMPLETED,
                    group_index=group_idx,
                    started_at=group_start_time
                )

                if isinstance(result, Exception):
                    # Task failed
                    error_msg = str(result)
                    task_result.status = TaskStatus.FAILED
                    task_result.error = error_msg
                    task_result.completed_at = datetime.now(timezone.utc)
                    failed_count += 1

                    # Finish agent span with failure
                    try:
                        if agent_id in agent_spans and self.tracing_service:
                            self.tracing_service.finish_span(
                                context=agent_spans[agent_id],
                                status="failed",
                                error=error_msg
                            )
                            del agent_spans[agent_id]
                    except Exception as span_error:
                        logger.warning(f"Failed to finish span for {agent_id}: {span_error}")

                    logger.error(
                        f"Task failed in group {group_idx + 1}: "
                        f"{agent_id} - {error_msg}"
                    )

                    # Attempt fault tolerance retry if enabled
                    retry_attempt = None
                    if enable_fault_tolerance:
                        retry_attempt = await self._attempt_fault_tolerance_retry(
                            chain_id=chain_id,
                            task_info=task_info,
                            task_type=task_type,
                            error=result
                        )

                    if retry_attempt:
                        retried_count += 1
                        task_result.retry_attempt = RetryAttempt(
                            retry_link_id=retry_attempt.id,
                            alternative_agent_id=retry_attempt.child_agent_id,
                            original_agent_id=agent_id,
                            reason=f"Fault tolerance retry: {error_msg[:100]}"
                        )
                        logger.info(
                            f"Created retry {retry_attempt.retry_link_id} for failed task"
                        )
                else:
                    # Task completed successfully
                    task_result.result = result
                    task_result.completed_at = datetime.now(timezone.utc)
                    completed_count += 1

                    # Finish agent span with success
                    try:
                        if agent_id in agent_spans and self.tracing_service:
                            result_summary = str(result)[:200] if result else None
                            self.tracing_service.finish_span(
                                context=agent_spans[agent_id],
                                status="completed",
                                result_summary=result_summary
                            )
                            del agent_spans[agent_id]
                    except Exception as span_error:
                        logger.warning(f"Failed to finish span for {agent_id}: {span_error}")

                    logger.debug(
                        f"Task completed in group {group_idx + 1}: {agent_id}"
                    )

                all_task_results.append(task_result)

            # Update blackboard with group progress
            await self._publish_group_progress(
                chain_id=chain_id,
                group_index=group_idx,
                total_groups=len(task_groups),
                completed_count=len([r for r in group_results if not isinstance(r, Exception)]),
                failed_count=len([r for r in group_results if isinstance(r, Exception)])
            )

        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)

        # Build trace context for metadata
        trace_context_dict = None
        if fleet_trace_context:
            trace_context_dict = fleet_trace_context.to_dict()

        # Build result
        execution_result = FleetExecutionResult(
            chain_id=chain_id,
            total_tasks=len(all_task_results),
            completed_count=completed_count,
            failed_count=failed_count,
            retried_count=retried_count,
            tasks=all_task_results,
            group_count=len(task_groups),
            execution_time_ms=execution_time_ms,
            metadata={
                "enable_fault_tolerance": enable_fault_tolerance,
                "has_retries": retried_count > 0,
                "trace_context": trace_context_dict
            }
        )

        logger.info(
            f"Parallel execution complete for chain {chain_id}: "
            f"{completed_count} completed, {failed_count} failed, "
            f"{retried_count} retried ({execution_result.success_rate:.1f}% success)"
        )

        # Publish completion event
        await self.notify_fleet_state_change(
            chain_id=chain_id,
            event_type="execution_complete",
            data={
                "total_tasks": execution_result.total_tasks,
                "completed_count": execution_result.completed_count,
                "failed_count": execution_result.failed_count,
                "retried_count": execution_result.retried_count,
                "success_rate": execution_result.success_rate,
                "execution_time_ms": execution_result.execution_time_ms
            }
        )

        # Finish fleet trace (graceful degradation)
        try:
            if fleet_trace_context and self.tracing_service:
                result_summary = (
                    f"{completed_count} completed, {failed_count} failed, "
                    f"{retried_count} retried ({execution_result.success_rate:.1f}% success)"
                )
                self.tracing_service.finish_span(
                    context=fleet_trace_context,
                    status="completed" if failed_count == 0 else "partial",
                    result_summary=result_summary
                )
        except Exception as e:
            logger.warning(f"Failed to finish fleet trace: {e}")

        return execution_result

    async def _execute_single_task(
        self,
        chain_id: str,
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single fleet task.

        This is a placeholder that wraps the actual task execution.
        In production, this would delegate to the appropriate agent
        or executor service.

        Args:
            chain_id: The delegation chain
            task: Task dict with agent_id and task_description

        Returns:
            Task execution result dict

        Raises:
            Exception: If task execution fails
        """
        agent_id = task.get("agent_id")
        task_description = task.get("task_description", task.get("task", ""))

        logger.debug(f"Executing task for agent {agent_id}: {task_description[:100]}...")

        # TODO: Integrate with actual agent execution service
        # For now, simulate execution with a small delay
        await asyncio.sleep(0.1)

        # Return mock result
        return {
            "agent_id": agent_id,
            "task": task_description,
            "status": "completed",
            "result": f"Executed: {task_description[:100]}",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }

    async def _publish_group_progress(
        self,
        chain_id: str,
        group_index: int,
        total_groups: int,
        completed_count: int,
        failed_count: int
    ):
        """
        Publish group execution progress to blackboard.

        Args:
            chain_id: The delegation chain
            group_index: Current group index (0-based)
            total_groups: Total number of groups
            completed_count: Number of completed tasks in this group
            failed_count: Number of failed tasks in this group
        """
        if not self.blackboard_service:
            return

        progress_update = {
            "type": "group_progress",
            "group_index": group_index,
            "total_groups": total_groups,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        try:
            await self.blackboard_service.publish_update(chain_id, progress_update)
            logger.debug(f"Published progress for group {group_index + 1}/{total_groups}")
        except Exception as e:
            logger.error(f"Failed to publish group progress: {e}")

    async def get_fleet_snapshot(self, chain_id: str) -> FleetStateSnapshot:
        """
        Get a point-in-time snapshot of fleet state.

        Queries active ChainLinks, blackboard version, and pending tasks
        to provide a comprehensive view of fleet status.

        Args:
            chain_id: The delegation chain to snapshot

        Returns:
            FleetStateSnapshot with current fleet state
        """
        logger.debug(f"Capturing fleet snapshot for chain {chain_id}")

        # Query chain and links
        chain = self.db.query(DelegationChain).filter(
            DelegationChain.id == chain_id
        ).first()

        if not chain:
            logger.warning(f"Chain {chain_id} not found for snapshot")
            return FleetStateSnapshot(
                chain_id=chain_id,
                active_agents=[],
                pending_tasks=[],
                metadata={"error": "Chain not found"}
            )

        # Get active links
        active_links = self.db.query(ChainLink).filter(
            ChainLink.chain_id == chain_id,
            ChainLink.status.in_(["pending", "processing"])
        ).all()

        # Get completed links
        completed_links = self.db.query(ChainLink).filter(
            ChainLink.chain_id == chain_id,
            ChainLink.status == "completed"
        ).all()

        # Get failed links
        failed_links = self.db.query(ChainLink).filter(
            ChainLink.chain_id == chain_id,
            ChainLink.status == "failed"
        ).all()

        # Extract blackboard version from metadata
        metadata = dict(chain.metadata_json or {})
        blackboard_version = metadata.get("_version", 0)

        # Build snapshot
        snapshot = FleetStateSnapshot(
            chain_id=chain_id,
            active_agents=[link.child_agent_id for link in active_links],
            blackboard_version=blackboard_version,
            pending_tasks=[link.task_description for link in active_links],
            completed_tasks=[link.task_description for link in completed_links],
            failed_tasks=[link.task_description for link in failed_links],
            metadata={
                "chain_status": chain.status,
                "total_links": chain.total_links,
                "root_agent_id": chain.root_agent_id,
                "root_task": chain.root_task
            }
        )

        logger.debug(
            f"Fleet snapshot for {chain_id}: "
            f"{len(snapshot.active_agents)} active, "
            f"{len(snapshot.completed_tasks)} completed, "
            f"{len(snapshot.failed_tasks)} failed"
        )

        return snapshot

    async def notify_fleet_state_change(
        self,
        chain_id: str,
        event_type: str,
        data: Dict[str, Any]
    ):
        """
        Publish fleet state change to Redis pub/sub.

        Notifies subscribers of fleet events like agents joining,
        completing tasks, or failing. Enables real-time monitoring
        and coordination.

        Args:
            chain_id: The delegation chain
            event_type: Type of event (agent_joined, agent_completed,
                        agent_failed, fleet_expanded, etc.)
            data: Event-specific data
        """
        if not self.blackboard_service:
            logger.debug("No blackboard service, skipping state notification")
            return

        valid_event_types = [
            "agent_joined",
            "agent_completed",
            "agent_failed",
            "fleet_expanded",
            "group_progress",
            "execution_complete",
            "decomposition_complete"
        ]

        if event_type not in valid_event_types:
            logger.warning(f"Unknown event type: {event_type}")
            return

        event = {
            "type": event_type,
            "chain_id": chain_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        try:
            await self.blackboard_service.publish_update(chain_id, event)
            logger.debug(f"Published fleet state change: {event_type} for chain {chain_id}")
        except Exception as e:
            logger.error(f"Failed to publish fleet state change: {e}")

    async def _attempt_fault_tolerance_retry(
        self,
        chain_id: str,
        task_info: Dict[str, Any],
        task_type: Optional[FleetTaskType],
        error: Exception
    ) -> Optional[ChainLink]:
        """
        Attempt to retry a failed task with an alternative specialist.

        Args:
            chain_id: The delegation chain
            task_info: Task information dict with agent_id and task_description
            task_type: Type of task for failure policy lookup
            error: The exception that caused failure

        Returns:
            New ChainLink if retry created, None otherwise
        """
        agent_id = task_info.get("agent_id")
        task_description = task_info.get("task_description", task_info.get("task", ""))

        if not agent_id:
            logger.warning("Cannot retry task: missing agent_id")
            return None

        # Find the failed ChainLink
        failed_link = self.db.query(ChainLink).filter(
            ChainLink.chain_id == chain_id,
            ChainLink.child_agent_id == agent_id,
            ChainLink.task_description == task_description,
            ChainLink.status == "failed"
        ).order_by(ChainLink.started_at.desc()).first()

        if not failed_link:
            logger.warning(
                f"Cannot retry task: no failed ChainLink found for agent {agent_id}"
            )
            return None

        # Use FaultToleranceService to retry with alternative
        retry_link = await self.fault_tolerance.retry_with_alternative_specialist(
            failed_link=failed_link,
            task_type=task_type
        )

        return retry_link

    async def decompose_and_execute(
        self,
        chain_id: str,
        task_description: str,
        
        tenant_plan: str = "solo",
        context: Dict[str, Any] = None,
        max_subtasks: int = 10
    ) -> Dict[str, Any]:
        """
        Decompose a complex task and execute it using the fleet.

        This is the primary integration method that combines:
        - Task decomposition (LLM-based or fallback)
        - Dependency validation (cycle detection)
        - Fleet sizing (complexity estimation)
        - Parallel execution (grouped by dependency depth)

        Args:
            chain_id: The delegation chain executing the task
            task_description: Complex task to decompose and execute
            tenant_id: Any ID for multi-tenancy
            tenant_plan: Subscription plan (free, solo, team, enterprise)
            context: Optional context dict for decomposition
            max_subtasks: Maximum number of subtasks to create

        Returns:
            Dict with keys:
                - decomposition: TaskDecomposition object
                - execution_result: FleetExecutionResult from execution
                - execution_groups: List[List[str]] subtask IDs by group
                - critical_path: List[str] subtask IDs on critical path
                - metadata: Dict with decomposition metadata

        Raises:
            ValueError: If circular dependencies detected
        """
        logger.info(
            f"Decomposing and executing task for chain {chain_id}: "
            f"{task_description[:100]}..."
        )

        # Lazy initialize services if not provided
        if not self.decomposition_service:
            from core.llm.byok_handler import BYOKHandler
            llm_service = BYOKHandler(self.db, tenant_id)
            self.decomposition_service = TaskDecompositionService(
                db=self.db,
                llm_service=llm_service
            )

        if not self.dependency_service:
            self.dependency_service = DependencyGraphService()

        if not self.complexity_estimator:
            self.complexity_estimator = ComplexityEstimator(self.db)

        # Step 1: Decompose task
        logger.info(f"Step 1: Decomposing task into subtasks (max {max_subtasks})")
        decomposition = await self.decomposition_service.decompose_task(
            task_description=task_description,
            tenant_id=tenant_id,
            context=context or {},
            max_subtasks=max_subtasks
        )

        logger.info(
            f"Decomposed into {len(decomposition.subtasks)} subtasks, "
            f"complexity={decomposition.complexity_score:.2f}, "
            f"suggested_fleet_size={decomposition.suggested_fleet_size}"
        )

        # Step 2: Build dependency graph and validate
        logger.info("Step 2: Building dependency graph and validating cycles")
        graph = self.dependency_service.build_graph(decomposition.subtasks)

        # Validate no circular dependencies
        try:
            cycles = self.dependency_service.validate_cycles(graph)
            logger.info("Dependency graph validated: no circular dependencies")
        except ValueError as e:
            logger.error(f"Circular dependencies detected: {e}")
            raise

        # Step 3: Detect critical path
        logger.info("Step 3: Detecting critical path")
        critical_path, critical_tokens = self.dependency_service.detect_critical_path(
            graph,
            decomposition.subtasks
        )
        logger.info(
            f"Critical path: {critical_path} "
            f"({critical_tokens} tokens)"
        )

        # Step 4: Get execution groups
        logger.info("Step 4: Generating execution groups")
        execution_groups = self.dependency_service.get_execution_groups(graph)
        logger.info(
            f"Generated {len(execution_groups)} execution groups: "
            f"{[len(g) for g in execution_groups]}"
        )

        # Step 5: Estimate fleet size
        logger.info("Step 5: Estimating optimal fleet size")
        estimated_fleet_size = self.complexity_estimator.estimate_fleet_size(
            decomposition=decomposition,
            tenant_plan=tenant_plan,
            tenant_id=tenant_id
        )
        logger.info(f"Estimated fleet size: {estimated_fleet_size} (plan: {tenant_plan})")

        # Step 6: Store decomposition in DelegationChain.metadata_json
        logger.info("Step 6: Storing decomposition metadata")
        await self._store_decomposition_metadata(
            chain_id=chain_id,
            decomposition=decomposition,
            execution_groups=execution_groups,
            critical_path=critical_path,
            critical_tokens=critical_tokens,
            estimated_fleet_size=estimated_fleet_size
        )

        # Step 7: Convert execution groups to task_groups format
        logger.info("Step 7: Converting to task_groups format for execution")
        task_groups = self._convert_to_task_groups(
            decomposition.subtasks,
            execution_groups
        )

        # Step 8: Publish decomposition events
        await self.notify_fleet_state_change(
            chain_id=chain_id,
            event_type="decomposition_complete",
            data={
                "subtask_count": len(decomposition.subtasks),
                "complexity_score": decomposition.complexity_score,
                "suggested_fleet_size": decomposition.suggested_fleet_size,
                "estimated_fleet_size": estimated_fleet_size,
                "group_count": len(execution_groups),
                "critical_path_length": len(critical_path),
                "decomposed_at": datetime.now(timezone.utc).isoformat()
            }
        )

        # Step 9: Execute using existing execute_parallel_task
        logger.info("Step 9: Executing decomposed tasks")
        execution_result = await self.execute_parallel_task(
            chain_id=chain_id,
            task_groups=task_groups,
            enable_fault_tolerance=True
        )

        # Return comprehensive result
        return {
            "decomposition": decomposition,
            "execution_result": execution_result,
            "execution_groups": execution_groups,
            "critical_path": critical_path,
            "metadata": {
                "subtask_count": len(decomposition.subtasks),
                "complexity_score": decomposition.complexity_score,
                "suggested_fleet_size": decomposition.suggested_fleet_size,
                "estimated_fleet_size": estimated_fleet_size,
                "critical_tokens": critical_tokens,
                "decomposed_at": datetime.now(timezone.utc).isoformat()
            }
        }

    async def execute_decomposed_task(
        self,
        chain_id: str,
        decomposition: TaskDecomposition) -> Dict[str, Any]:
        """
        Execute a pre-computed task decomposition.

        This method skips the LLM decomposition step and directly
        executes a TaskDecomposition object. Useful for testing
        and pre-computed decompositions.

        Args:
            chain_id: The delegation chain executing the task
            decomposition: Pre-computed TaskDecomposition object
            tenant_id: Any ID for multi-tenancy

        Returns:
            Dict with keys:
                - execution_result: FleetExecutionResult from execution
                - execution_groups: List[List[str]] subtask IDs by group
                - critical_path: List[str] subtask IDs on critical path

        Raises:
            ValueError: If circular dependencies detected
        """
        logger.info(
            f"Executing pre-computed decomposition for chain {chain_id}: "
            f"{len(decomposition.subtasks)} subtasks"
        )

        # Lazy initialize dependency service if not provided
        if not self.dependency_service:
            self.dependency_service = DependencyGraphService()

        # Step 1: Build dependency graph and validate
        graph = self.dependency_service.build_graph(decomposition.subtasks)

        # Validate no circular dependencies
        try:
            self.dependency_service.validate_cycles(graph)
        except ValueError as e:
            logger.error(f"Circular dependencies detected: {e}")
            raise

        # Step 2: Get execution groups
        execution_groups = self.dependency_service.get_execution_groups(graph)

        # Step 3: Detect critical path
        critical_path, critical_tokens = self.dependency_service.detect_critical_path(
            graph,
            decomposition.subtasks
        )

        logger.info(
            f"Execution groups: {len(execution_groups)}, "
            f"Critical path: {len(critical_path)} subtasks ({critical_tokens} tokens)"
        )

        # Step 4: Convert to task_groups format
        task_groups = self._convert_to_task_groups(
            decomposition.subtasks,
            execution_groups
        )

        # Step 5: Execute using existing execute_parallel_task
        execution_result = await self.execute_parallel_task(
            chain_id=chain_id,
            task_groups=task_groups,
            enable_fault_tolerance=True
        )

        return {
            "execution_result": execution_result,
            "execution_groups": execution_groups,
            "critical_path": critical_path
        }

    async def _store_decomposition_metadata(
        self,
        chain_id: str,
        decomposition: TaskDecomposition,
        execution_groups: List[List[str]],
        critical_path: List[str],
        critical_tokens: int,
        estimated_fleet_size: int
    ):
        """
        Store decomposition metadata in DelegationChain.metadata_json.

        Args:
            chain_id: The delegation chain
            decomposition: TaskDecomposition object
            execution_groups: List of execution groups (subtask IDs)
            critical_path: List of subtask IDs on critical path
            critical_tokens: Total tokens on critical path
            estimated_fleet_size: Estimated fleet size from ComplexityEstimator
        """
        chain = self.db.query(DelegationChain).filter(
            DelegationChain.id == chain_id
        ).first()

        if not chain:
            logger.warning(f"Chain {chain_id} not found, cannot store decomposition")
            return

        # Build decomposition metadata
        metadata = dict(chain.metadata_json or {})
        metadata["decomposition"] = {
            "subtask_count": len(decomposition.subtasks),
            "complexity_score": decomposition.complexity_score,
            "suggested_fleet_size": decomposition.suggested_fleet_size,
            "estimated_fleet_size": estimated_fleet_size,
            "execution_groups": execution_groups,
            "critical_path": critical_path,
            "critical_tokens": critical_tokens,
            "decomposed_at": datetime.now(timezone.utc).isoformat(),
            "decomposition_rationale": decomposition.decomposition_rationale
        }

        chain.metadata_json = metadata
        self.db.commit()

        logger.debug(f"Stored decomposition metadata for chain {chain_id}")

    def _convert_to_task_groups(
        self,
        subtasks: List[Any],
        execution_groups: List[List[str]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Convert execution groups to task_groups format for execute_parallel_task.

        Args:
            subtasks: List of SubTask objects
            execution_groups: List of lists containing subtask IDs

        Returns:
            List of task groups where each group is List[Dict] with
            agent_id and task_description keys
        """
        # Build subtask lookup map
        subtask_map = {s.id: s for s in subtasks}

        # Convert each group
        task_groups = []
        for group in execution_groups:
            group_tasks = []
            for subtask_id in group:
                if subtask_id not in subtask_map:
                    logger.warning(f"Subtask {subtask_id} not found in decomposition")
                    continue

                subtask = subtask_map[subtask_id]
                group_tasks.append({
                    "agent_id": subtask_id,
                    "task_description": subtask.description
                })

            task_groups.append(group_tasks)

        return task_groups

def get_fleet_coordinator(
    db: Session,
    blackboard_service=None,
    decomposition_service=None,
    dependency_service=None,
    complexity_estimator=None
) -> FleetCoordinatorService:
    """
    Factory function to get or create a FleetCoordinatorService instance.

    Args:
        db: Database session
        blackboard_service: Optional DistributedBlackboardService for Redis pub/sub
        decomposition_service: Optional TaskDecompositionService for task decomposition
        dependency_service: Optional DependencyGraphService for graph operations
        complexity_estimator: Optional ComplexityEstimator for fleet sizing

    Returns:
        FleetCoordinatorService instance
    """
    return FleetCoordinatorService(
        db,
        blackboard_service,
        decomposition_service,
        dependency_service,
        complexity_estimator
    )
