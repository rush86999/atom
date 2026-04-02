"""
FaultToleranceService for resilient multi-agent fleet execution.

Provides automatic retry with alternative specialist selection when agents fail,
respecting failure policies and using circuit breakers to prevent cascading failures.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session

from core.models import AgentRegistry, ChainLink
from core.fleet.fleet_task_types import FailurePolicy, FleetTaskType, DEFAULT_FAILURE_POLICIES
from core.llm.fallback.circuit_breaker import CircuitBreaker, CircuitBreakerState

logger = logging.getLogger(__name__)

class FaultToleranceService:
    """
    Manages fault tolerance for multi-agent fleet execution.

    When an agent fails, this service:
    1. Checks FailurePolicy to determine if retry is allowed
    2. Queries AgentRegistry for alternative specialists in the same domain
    3. Uses CircuitBreaker to avoid unhealthy agents
    4. Creates new ChainLink with alternative agent
    5. Records FleetHealingEvent for audit trail
    """

    def __init__(
        self,
        db: Session,
        circuit_breakers: Optional[Dict[str, CircuitBreaker]] = None
    ):
        """
        Initialize fault tolerance service.

        Args:
            db: Database session for persistence
            circuit_breakers: Optional dict of agent_id -> CircuitBreaker instances
        """
        self.db = db
        self.circuit_breakers: Dict[str, CircuitBreaker] = circuit_breakers or {}

    def should_retry(
        self,
        task_type: Optional[FleetTaskType],
        failure_policy: Optional[FailurePolicy]
    ) -> bool:
        """
        Determine if task should be retried based on failure policy.

        Args:
            task_type: Type of task that failed
            failure_policy: Policy override (if specified)

        Returns:
            True if retry allowed, False otherwise
        """
        policy = failure_policy or DEFAULT_FAILURE_POLICIES.get(task_type)

        if policy == FailurePolicy.RETRY_THEN_STOP:
            return True
        elif policy in (FailurePolicy.STOP_ON_FAILURE, FailurePolicy.CONTINUE_ON_FAILURE):
            return False

        return False

    async def find_alternative_specialist(
        self,
        failed_agent_id: str,
        chain_id: str,
        exclude_agent_ids: Optional[Set[str]] = None
    ) -> Optional[AgentRegistry]:
        """
        Find an alternative specialist in the same domain as the failed agent.

        Args:
            failed_agent_id: ID of the agent that failed
            chain_id: Delegation chain for tenant isolation
            exclude_agent_ids: Set of agent IDs to exclude (already tried)

        Returns:
            Alternative AgentRegistry entry or None if none available
        """
        # Get original agent to determine domain
        original_agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == failed_agent_id
        ).first()

        if not original_agent:
            logger.error(f"Original agent {failed_agent_id} not found")
            return None

        domain = original_agent.category  # e.g., "Finance", "Operations"
        
        # Build exclusion set
        exclude_ids = exclude_agent_ids or {failed_agent_id}

        # Query for alternatives in same domain
        alternatives = self.db.query(AgentRegistry).filter(
            AgentRegistry.category == domain,
            AgentRegistry.id.notin_(exclude_ids),
            AgentRegistry.            AgentRegistry.status == "active"  # Only active agents
        ).all()

        if not alternatives:
            logger.warning(
                f"No alternative specialists for domain {domain} "
                f"(excluded: {exclude_ids})"
            )
            return None

        # Select best alternative using circuit breaker health
        best_alternative = await self._select_best_alternative(alternatives)

        logger.info(
            f"Found alternative specialist: {best_alternative.name} "
            f"(domain: {domain}, original: {original_agent.name})"
        )

        return best_alternative

    async def _select_best_alternative(
        self,
        alternatives: List[AgentRegistry]
    ) -> AgentRegistry:
        """
        Select best alternative from list of candidates.

        Strategy: Pick agent with best circuit breaker health.
        Fallback: First available if no metrics.

        Args:
            alternatives: List of candidate AgentRegistry entries

        Returns:
            Selected AgentRegistry entry
        """
        # Score each alternative based on circuit breaker health
        scored_alternatives = []

        for agent in alternatives:
            breaker = self.circuit_breakers.get(agent.id)
            if breaker:
                state = await breaker.get_state()
                metrics = await breaker.get_metrics()

                # Score: CLOSED=100, HALF_OPEN=50, OPEN=0
                state_score = {
                    CircuitBreakerState.CLOSED: 100,
                    CircuitBreakerState.HALF_OPEN: 50,
                    CircuitBreakerState.OPEN: 0
                }.get(state, 0)

                # Penalize for high failure count
                failure_penalty = metrics.get("failure_count", 0) * 10
                score = state_score - failure_penalty

                scored_alternatives.append((score, agent))
            else:
                # No circuit breaker data, use neutral score
                scored_alternatives.append((50, agent))

        # Sort by score descending and return best
        scored_alternatives.sort(key=lambda x: x[0], reverse=True)

        best_score, best_agent = scored_alternatives[0]
        logger.debug(
            f"Selected alternative {best_agent.name} with score {best_score}"
        )

        return best_agent

    async def retry_with_alternative_specialist(
        self,
        failed_link: ChainLink,
        task_type: Optional[FleetTaskType] = None,
        failure_policy_override: Optional[FailurePolicy] = None
    ) -> Optional[ChainLink]:
        """
        Retry a failed task with an alternative specialist.

        Args:
            failed_link: The ChainLink that failed
            task_type: Type of task for policy lookup
            failure_policy_override: Override default failure policy

        Returns:
            New ChainLink if alternative found and retry created, None otherwise
        """
        # Check if retry is allowed by policy
        if not self.should_retry(task_type, failure_policy_override):
            logger.info(
                f"Retry not allowed for link {failed_link.id} "
                f"(task_type: {task_type}, policy: {failure_policy_override})"
            )
            return None

        # Check circuit breaker for original agent
        original_breaker = self.circuit_breakers.get(failed_link.child_agent_id)
        if original_breaker:
            state = await original_breaker.get_state()
            if state == CircuitBreakerState.OPEN:
                logger.warning(
                    f"Circuit breaker OPEN for agent {failed_link.child_agent_id}, "
                    f"will attempt alternative"
                )

        # Get list of agents already tried (walk retry chain)
        tried_agent_ids = self._get_tried_agent_ids(failed_link)

        # Find alternative specialist
        alternative = await self.find_alternative_specialist(
            failed_agent_id=failed_link.child_agent_id,
            chain_id=failed_link.chain_id,
            exclude_agent_ids=tried_agent_ids
        )

        if not alternative:
            logger.warning(
                f"No alternative specialist available for retry of {failed_link.id}"
            )
            return None

        # Import inside method to avoid circular dependency
        from core.agent_fleet_service import AgentFleetService
        fleet_service = AgentFleetService(self.db)

        # Prepare context for retry
        new_context = (failed_link.context_json or {}).copy()
        new_context.update({
            "is_fault_tolerance_retry": True,
            "original_failed_link_id": failed_link.id,
            "retry_agent_id": alternative.id,
            "retry_attempt": len(tried_agent_ids) + 1
        })

        # Create new ChainLink with alternative agent
        new_link = fleet_service.recruit_member(
            chain_id=failed_link.chain_id,
            parent_agent_id=failed_link.parent_agent_id,
            child_agent_id=alternative.id,
            task_description=failed_link.task_description,
            context_json=new_context,
            link_order=failed_link.link_order
        )

        # Update original link to indicate it was retried
        failed_link.context_json = failed_link.context_json or {}
        failed_link.context_json["retried_with_link_id"] = new_link.id
        self.db.commit()

        # Record healing event for audit
        self._record_retry_event(
            original_link=failed_link,
            retry_link=new_link,
            alternative_agent=alternative
        )

        logger.info(
            f"Created retry link {new_link.id} for failed link {failed_link.id} "
            f"using alternative agent {alternative.name}"
        )

        return new_link

    def _get_tried_agent_ids(self, link: ChainLink) -> Set[str]:
        """
        Get set of agent IDs already tried for this task.

        Walks the retry chain to collect all agent IDs that have
        been attempted for this task.

        Args:
            link: Current ChainLink

        Returns:
            Set of agent IDs already tried
        """
        tried_ids = {link.child_agent_id}
        context = link.context_json or {}

        # Check if this is already a retry
        if "original_failed_link_id" in context:
            original_link = self.db.query(ChainLink).filter(
                ChainLink.id == context["original_failed_link_id"]
            ).first()
            if original_link:
                tried_ids.add(original_link.child_agent_id)

                # Recursively walk further back if needed
                tried_ids.update(self._get_tried_agent_ids(original_link))

        return tried_ids

    def _record_retry_event(
        self,
        original_link: ChainLink,
        retry_link: ChainLink,
        alternative_agent: AgentRegistry
    ) -> None:
        """
        Record FleetHealingEvent for audit trail.

        Args:
            original_link: Original failed ChainLink
            retry_link: New retry ChainLink
            alternative_agent: Alternative agent used for retry
        """
        try:
            # Import FleetHealingEvent dynamically to avoid import errors
            # if it doesn't exist yet
            from core.models import FleetHealingEvent

            healing_event = FleetHealingEvent(
                                chain_id=original_link.chain_id,
                link_id=original_link.id,
                trigger_type="failed_link",
                trigger_reason="Fault tolerance retry with alternative specialist",
                recovery_action="alternative_specialist",
                status="in_progress",
                retry_link_id=retry_link.id,
                metadata_json={
                    "original_agent_id": original_link.child_agent_id,
                    "alternative_agent_id": alternative_agent.id,
                    "alternative_agent_name": alternative_agent.name,
                    "domain": alternative_agent.category
                }
            )
            self.db.add(healing_event)
            self.db.commit()
            logger.debug(f"Recorded healing event {healing_event.id}")
        except ImportError:
            # FleetHealingEvent doesn't exist yet, skip recording
            logger.debug("FleetHealingEvent not yet implemented, skipping recording")
        except Exception as e:
            logger.error(f"Failed to record healing event: {e}")
            self.db.rollback()

    def get_or_create_circuit_breaker(
        self,
        agent_id: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0
    ) -> CircuitBreaker:
        """
        Get or create circuit breaker for an agent.

        Args:
            agent_id: Agent ID to track
            failure_threshold: Consecutive failures to trip circuit
            recovery_timeout: Seconds before attempting recovery

        Returns:
            CircuitBreaker instance for this agent
        """
        if agent_id not in self.circuit_breakers:
            from core.llm.fallback.circuit_breaker import CircuitBreaker
            self.circuit_breakers[agent_id] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
            logger.debug(f"Created circuit breaker for agent {agent_id}")

        return self.circuit_breakers[agent_id]

    async def handle_failed_task(
        self,
        chain_id: str,
        agent_id: str,
        task_description: str,
        task_type: Optional[FleetTaskType] = None,
        error: Optional[Exception] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Handle a failed task during parallel execution.

        Convenience method that finds the failed ChainLink and attempts
        retry with alternative specialist in one call.

        Args:
            chain_id: The delegation chain
            agent_id: ID of the agent that failed
            task_description: Description of the failed task
            task_type: Type of task for failure policy lookup
            error: The exception that caused failure (for logging)

        Returns:
            Dict with keys:
                - retried: bool - Whether retry was attempted
                - retry_link_id: str - ID of new ChainLink if retried
                - alternative_agent_id: str - ID of alternative agent if retried
                - reason: str - Reason if retry not attempted
            Returns None if ChainLink not found
        """
        # Find the failed ChainLink
        failed_link = self.db.query(ChainLink).filter(
            ChainLink.chain_id == chain_id,
            ChainLink.child_agent_id == agent_id,
            ChainLink.task_description == task_description,
            ChainLink.status.in_(["failed", "processing"])  # Include in_progress for stuck tasks
        ).order_by(ChainLink.started_at.desc()).first()

        if not failed_link:
            logger.warning(
                f"Cannot handle failed task: no ChainLink found for "
                f"chain={chain_id}, agent={agent_id}, task={task_description[:50]}"
            )
            return {"retried": False, "reason": "ChainLink not found"}

        # Check if retry is allowed by policy
        if not self.should_retry(task_type, None):
            logger.info(
                f"Retry not allowed for task_type={task_type}, policy=STOP/CONTINUE"
            )
            return {
                "retried": False,
                "reason": f"Failure policy for {task_type} does not allow retry"
            }

        # Attempt retry with alternative specialist
        retry_link = await self.retry_with_alternative_specialist(
            failed_link=failed_link,
            task_type=task_type
        )

        if retry_link:
            return {
                "retried": True,
                "retry_link_id": retry_link.id,
                "alternative_agent_id": retry_link.child_agent_id
            }
        else:
            return {
                "retried": False,
                "reason": "No alternative specialist available"
            }
