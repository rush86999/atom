"""
Trigger Interceptor with Maturity-Based Routing

Centralized interception point for all agent triggers with graduated routing
based on agent maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS).

Performance target: <5ms routing decision latency using GovernanceCache.
"""

from datetime import datetime
from enum import Enum
import logging
from typing import Any, Dict, Literal, Optional
import uuid
from sqlalchemy.orm import Session

from core.governance_cache import get_async_governance_cache
from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    ProposalStatus,
    ProposalType,
    SupervisionSession,
    SupervisionStatus,
    TriggerSource,
)
from core.student_training_service import StudentTrainingService

logger = logging.getLogger(__name__)


class MaturityLevel(str, Enum):
    """Agent maturity levels for routing decisions"""
    STUDENT = "student"       # <0.5 confidence → Training required
    INTERN = "intern"         # 0.5-0.7 confidence → Proposal required
    SUPERVISED = "supervised" # 0.7-0.9 confidence → Supervision required
    AUTONOMOUS = "autonomous" # >0.9 confidence → Full execution


class RoutingDecision(str, Enum):
    """Routing decision outcomes"""
    TRAINING = "training"           # Route to Meta Agent for training proposal
    PROPOSAL = "proposal"           # Generate proposal for human review (INTERN)
    SUPERVISION = "supervision"     # Execute with real-time monitoring
    EXECUTION = "execution"         # Full execution without oversight


class TriggerDecision:
    """Result of trigger interception and routing decision"""

    def __init__(
        self,
        routing_decision: RoutingDecision,
        execute: bool,
        agent_id: str,
        agent_maturity: str,
        confidence_score: float,
        trigger_source: TriggerSource,
        blocked_context: Optional[BlockedTriggerContext] = None,
        proposal: Optional[AgentProposal] = None,
        supervision_session: Optional[SupervisionSession] = None,
        reason: str = ""
    ):
        self.routing_decision = routing_decision
        self.execute = execute
        self.agent_id = agent_id
        self.agent_maturity = agent_maturity
        self.confidence_score = confidence_score
        self.trigger_source = trigger_source
        self.blocked_context = blocked_context
        self.proposal = proposal
        self.supervision_session = supervision_session
        self.reason = reason


class TriggerInterceptor:
    """
    Centralized trigger interception with maturity-based routing.

    Decision Flow:
    1. Check agent maturity level (cached <1ms lookup)
    2. Apply maturity-based routing rules:
       - STUDENT (<0.5) → Block → Route to training
       - INTERN (0.5-0.7) → Generate proposal → Await approval
       - SUPERVISED (0.7-0.9) → Execute with supervision
       - AUTONOMOUS (>0.9) → Full execution
    3. For MANUAL triggers: Always allow with maturity-based warnings
    4. Log to audit trail
    5. Return decision with appropriate context

    Performance: <5ms routing decision using GovernanceCache
    """

    def __init__(self, db: Session, workspace_id: str):
        self.db = db
        self.workspace_id = workspace_id
        self.training_service = StudentTrainingService(db)

    async def intercept_trigger(
        self,
        agent_id: str,
        trigger_source: TriggerSource,
        trigger_context: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> TriggerDecision:
        """
        Intercept agent trigger and route based on maturity level.

        Args:
            agent_id: Agent being triggered
            trigger_source: Source of trigger (MANUAL, DATA_SYNC, WORKFLOW_ENGINE, AI_COORDINATOR)
            trigger_context: Full trigger payload
            user_id: User who initiated trigger (for MANUAL triggers)

        Returns:
            TriggerDecision with routing information
        """
        # Fast path: Check cache for agent maturity (<1ms)
        agent_maturity, confidence_score = await self._get_agent_maturity_cached(agent_id)

        # Determine maturity level
        maturity_level = self._determine_maturity_level(agent_maturity, confidence_score)

        # Apply routing logic
        if trigger_source == TriggerSource.MANUAL:
            # Manual triggers always allowed, but with warnings
            return await self._handle_manual_trigger(
                agent_id, maturity_level, confidence_score, trigger_context, user_id
            )

        # Automated triggers apply maturity rules
        if maturity_level == MaturityLevel.STUDENT:
            return await self._route_student_agent(
                agent_id, trigger_source, trigger_context, confidence_score
            )

        elif maturity_level == MaturityLevel.INTERN:
            return await self._route_intern_agent(
                agent_id, trigger_source, trigger_context, confidence_score
            )

        elif maturity_level == MaturityLevel.SUPERVISED:
            return await self._route_supervised_agent(
                agent_id, trigger_source, trigger_context, confidence_score
            )

        else:  # AUTONOMOUS
            return await self._allow_execution(
                agent_id, trigger_source, trigger_context, confidence_score
            )

    async def route_to_training(
        self,
        blocked_trigger: BlockedTriggerContext
    ) -> AgentProposal:
        """
        Route STUDENT agent trigger to Meta Agent for training proposal.

        Creates training proposal via StudentTrainingService.
        """
        logger.info(
            f"Routing agent {blocked_trigger.agent_id} to training "
            f"(trigger: {blocked_trigger.trigger_type})"
        )

        proposal = await self.training_service.create_training_proposal(blocked_trigger)

        logger.info(
            f"Created training proposal {proposal.id} for agent {blocked_trigger.agent_id}"
        )

        return proposal

    async def create_proposal(
        self,
        intern_agent_id: str,
        trigger_context: Dict[str, Any],
        proposed_action: Dict[str, Any],
        reasoning: str
    ) -> AgentProposal:
        """
        Generate action proposal from INTERN agent for human review.

        INTERN agents must propose actions instead of executing directly.
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == intern_agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {intern_agent_id} not found")

        proposal = AgentProposal(
            agent_id=agent.id,
            agent_name=agent.name,
            proposal_type=ProposalType.ACTION.value,
            title=f"Action Proposal: {agent.name}",
            description=f"""
Agent is proposing an action for your review.

**Proposed Action:** {proposed_action.get('action_type', 'Unknown')}

**Reasoning:** {reasoning}

Please review and approve or reject this proposal.
            """.strip(),
            proposed_action=proposed_action,
            reasoning=reasoning,
            status=ProposalStatus.PROPOSED.value,
            proposed_by=agent.id
        )

        self.db.add(proposal)
        self.db.commit()
        self.db.refresh(proposal)

        logger.info(
            f"Created action proposal {proposal.id} for INTERN agent {agent.id}"
        )

        return proposal

    async def execute_with_supervision(
        self,
        trigger_context: Dict[str, Any],
        agent_id: str,
        user_id: str
    ) -> SupervisionSession:
        """
        Execute SUPERVISED agent with real-time monitoring.

        Creates supervision session for human monitoring.
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Create supervision session
        session = SupervisionSession(
            agent_id=agent.id,
            agent_name=agent.name,
            workspace_id=self.workspace_id,
            trigger_context=trigger_context,
            status=SupervisionStatus.RUNNING.value,
            supervisor_id=user_id
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(
            f"Started supervision session {session.id} for SUPERVISED agent {agent.id}"
        )

        return session

    async def allow_execution(
        self,
        agent_id: str,
        trigger_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Proceed with normal agent execution (AUTONOMOUS or approved MANUAL triggers).

        Returns execution context for caller to proceed.
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        logger.info(
            f"Allowing execution for AUTONOMOUS agent {agent.id} "
            f"(confidence: {agent.confidence_score:.3f})"
        )

        return {
            "allowed": True,
            "agent_id": agent.id,
            "agent_maturity": agent.status,
            "confidence_score": agent.confidence_score,
            "trigger_context": trigger_context
        }

    # ========================================================================
    # Private Routing Methods
    # ========================================================================

    async def _handle_manual_trigger(
        self,
        agent_id: str,
        maturity_level: MaturityLevel,
        confidence_score: float,
        trigger_context: Dict[str, Any],
        user_id: Optional[str]
    ) -> TriggerDecision:
        """
        Handle MANUAL trigger (user-initiated).

        Manual triggers always allowed, but show maturity-based warnings.
        """
        reason = f"Manual trigger by user {user_id or 'unknown'}"

        if maturity_level == MaturityLevel.STUDENT:
            reason += ". Warning: Agent is in STUDENT mode and may produce unreliable results"
        elif maturity_level == MaturityLevel.INTERN:
            reason += ". Note: Agent is in INTERN learning mode"
        elif maturity_level == MaturityLevel.SUPERVISED:
            reason += ". Agent will execute under SUPERVISION mode"

        return TriggerDecision(
            routing_decision=RoutingDecision.EXECUTION,
            execute=True,
            agent_id=agent_id,
            agent_maturity=maturity_level.value,
            confidence_score=confidence_score,
            trigger_source=TriggerSource.MANUAL,
            reason=reason
        )

    async def _route_student_agent(
        self,
        agent_id: str,
        trigger_source: TriggerSource,
        trigger_context: Dict[str, Any],
        confidence_score: float
    ) -> TriggerDecision:
        """
        Route STUDENT agent to training.

        STUDENT agents are blocked from automated triggers and routed to Meta Agent.
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        # Create blocked trigger record
        blocked_context = BlockedTriggerContext(
            agent_id=agent_id,
            agent_name=agent.name if agent else "Unknown",
            agent_maturity_at_block=AgentStatus.STUDENT.value,
            confidence_score_at_block=confidence_score,
            trigger_source=trigger_source.value,
            trigger_type=trigger_context.get("action_type", "unknown"),
            trigger_context=trigger_context,
            routing_decision=RoutingDecision.TRAINING.value,
            block_reason=f"STUDENT agent (confidence {confidence_score:.2f} < 0.5) cannot execute automated triggers. Training required."
        )

        self.db.add(blocked_context)
        self.db.commit()
        self.db.refresh(blocked_context)

        # Route to training
        proposal = await self.route_to_training(blocked_context)

        return TriggerDecision(
            routing_decision=RoutingDecision.TRAINING,
            execute=False,
            agent_id=agent_id,
            agent_maturity=AgentStatus.STUDENT.value,
            confidence_score=confidence_score,
            trigger_source=trigger_source,
            blocked_context=blocked_context,
            proposal=proposal,
            reason=f"STUDENT agent blocked. Training proposal {proposal.id} created."
        )

    async def _route_intern_agent(
        self,
        agent_id: str,
        trigger_source: TriggerSource,
        trigger_context: Dict[str, Any],
        confidence_score: float
    ) -> TriggerDecision:
        """
        Route INTERN agent to proposal generation.

        INTERN agents must generate proposals for human review instead of executing.
        """
        # Create blocked trigger record
        blocked_context = BlockedTriggerContext(
            agent_id=agent_id,
            agent_name="Intern Agent",
            agent_maturity_at_block=AgentStatus.INTERN.value,
            confidence_score_at_block=confidence_score,
            trigger_source=trigger_source.value,
            trigger_type=trigger_context.get("action_type", "unknown"),
            trigger_context=trigger_context,
            routing_decision=RoutingDecision.PROPOSAL.value,
            block_reason=f"INTERN agent (confidence {confidence_score:.2f}) requires proposal approval before execution."
        )

        self.db.add(blocked_context)
        self.db.commit()
        self.db.refresh(blocked_context)

        return TriggerDecision(
            routing_decision=RoutingDecision.PROPOSAL,
            execute=False,
            agent_id=agent_id,
            agent_maturity=AgentStatus.INTERN.value,
            confidence_score=confidence_score,
            trigger_source=trigger_source,
            blocked_context=blocked_context,
            reason=f"INTERN agent must generate proposal for human review before execution."
        )

    async def _route_supervised_agent(
        self,
        agent_id: str,
        trigger_source: TriggerSource,
        trigger_context: Dict[str, Any],
        confidence_score: float
    ) -> TriggerDecision:
        """
        Route SUPERVISED agent to execution with supervision.

        SUPERVISED agents can execute but require real-time monitoring.
        If user is unavailable, execution is queued for later.
        """
        from core.user_activity_service import UserActivityService
        from core.supervised_queue_service import SupervisedQueueService

        # Get agent to find user_id
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            return TriggerDecision(
                routing_decision=RoutingDecision.SUPERVISION,
                execute=False,
                agent_id=agent_id,
                agent_maturity=AgentStatus.SUPERVISED.value,
                confidence_score=confidence_score,
                trigger_source=trigger_source,
                reason=f"Agent not found: {agent_id}"
            )

        # Check if user is available for supervision
        user_activity_service = UserActivityService(self.db)
        user_state = await user_activity_service.get_user_state(agent.user_id)

        if user_activity_service.should_supervise(
            type('obj', (object,), {'state': user_state})()
        ):
            # User available: Execute with supervision
            return TriggerDecision(
                routing_decision=RoutingDecision.SUPERVISION,
                execute=True,
                agent_id=agent_id,
                agent_maturity=AgentStatus.SUPERVISED.value,
                confidence_score=confidence_score,
                trigger_source=trigger_source,
                reason=f"SUPERVISED agent will execute with real-time monitoring (user available)"
            )
        else:
            # User unavailable: Queue for later execution
            queue_service = SupervisedQueueService(self.db)
            await queue_service.enqueue_execution(
                agent_id=agent_id,
                user_id=agent.user_id,
                trigger_type=trigger_source.value,
                execution_context=trigger_context
            )

            return TriggerDecision(
                routing_decision=RoutingDecision.SUPERVISION,
                execute=False,
                agent_id=agent_id,
                agent_maturity=AgentStatus.SUPERVISED.value,
                confidence_score=confidence_score,
                trigger_source=trigger_source,
                reason=f"SUPERVISED agent queued for later execution (user unavailable)"
            )

    async def _allow_execution(
        self,
        agent_id: str,
        trigger_source: TriggerSource,
        trigger_context: Dict[str, Any],
        confidence_score: float
    ) -> TriggerDecision:
        """
        Allow AUTONOMOUS agent full execution without oversight.

        AUTONOMOUS agents (>0.9 confidence) can execute freely.
        """
        return TriggerDecision(
            routing_decision=RoutingDecision.EXECUTION,
            execute=True,
            agent_id=agent_id,
            agent_maturity=AgentStatus.AUTONOMOUS.value,
            confidence_score=confidence_score,
            trigger_source=trigger_source,
            reason=f"AUTONOMOUS agent (confidence {confidence_score:.2f}) approved for full execution."
        )

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _get_agent_maturity_cached(
        self,
        agent_id: str
    ) -> tuple[str, float]:
        """
        Get agent maturity status and confidence score from cache.

        Uses GovernanceCache for <1ms lookups.

        Returns:
            (status, confidence_score) tuple
        """
        # Get async governance cache
        cache = await get_async_governance_cache()

        # Try cache first
        cache_key = f"agent_maturity:{agent_id}"

        # Check governance cache
        cached_value = await cache.get(cache_key)
        if cached_value:
            return cached_value["status"], cached_value["confidence"]

        # Cache miss - query database
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Cache for 5 minutes (300 seconds)
        cache_value = {
            "status": agent.status,
            "confidence": agent.confidence_score
        }
        await cache.set(cache_key, cache_value, ttl=300)

        return agent.status, agent.confidence_score

    def _determine_maturity_level(
        self,
        status: str,
        confidence_score: float
    ) -> MaturityLevel:
        """
        Determine maturity level from status and confidence score.

        Priority: Status enum > Confidence score ranges
        """
        # If status is explicitly set, use it
        status_mapping = {
            AgentStatus.STUDENT.value: MaturityLevel.STUDENT,
            AgentStatus.INTERN.value: MaturityLevel.INTERN,
            AgentStatus.SUPERVISED.value: MaturityLevel.SUPERVISED,
            AgentStatus.AUTONOMOUS.value: MaturityLevel.AUTONOMOUS
        }

        if status in status_mapping:
            return status_mapping[status]

        # Fallback to confidence score ranges
        if confidence_score < 0.5:
            return MaturityLevel.STUDENT
        elif confidence_score < 0.7:
            return MaturityLevel.INTERN
        elif confidence_score < 0.9:
            return MaturityLevel.SUPERVISED
        else:
            return MaturityLevel.AUTONOMOUS
