"""
Student Training Service

Manages training proposals, sessions, and maturity progression for STUDENT agents.
Provides AI-based training duration estimation and confidence boosting.
"""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    ProposalStatus,
    ProposalType,
    TrainingSession,
    TriggerSource,
)

logger = logging.getLogger(__name__)


class TrainingDurationEstimate:
    """AI-generated training duration estimate"""
    def __init__(
        self,
        estimated_hours: float,
        confidence: float,
        reasoning: str,
        similar_agents: List[Dict[str, Any]],
        min_hours: float,
        max_hours: float
    ):
        self.estimated_hours = estimated_hours
        self.confidence = confidence
        self.reasoning = reasoning
        self.similar_agents = similar_agents
        self.min_hours = min_hours
        self.max_hours = max_hours


class TrainingOutcome:
    """Result of a training session"""
    def __init__(
        self,
        performance_score: float,
        supervisor_feedback: str,
        errors_count: int,
        tasks_completed: int,
        total_tasks: int,
        capabilities_developed: List[str],
        capability_gaps_remaining: List[str]
    ):
        self.performance_score = performance_score
        self.supervisor_feedback = supervisor_feedback
        self.errors_count = errors_count
        self.tasks_completed = tasks_completed
        self.total_tasks = total_tasks
        self.capabilities_developed = capabilities_developed
        self.capability_gaps_remaining = capability_gaps_remaining


class StudentTrainingService:
    """
    Service for managing STUDENT agent training and maturity progression.

    Key responsibilities:
    - Create training proposals from blocked triggers
    - Approve training and create sessions
    - Complete training and update agent maturity
    - AI-based training duration estimation
    - Training history tracking
    """

    def __init__(self, db: Session):
        self.db = db

    async def create_training_proposal(
        self,
        blocked_trigger: BlockedTriggerContext
    ) -> AgentProposal:
        """
        Generate training proposal from blocked trigger for STUDENT agent.

        Process:
        1. Analyze blocked trigger context
        2. Identify capability gaps
        3. Generate learning objectives
        4. Estimate training duration (AI-based)
        5. Create proposal with clear steps
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == blocked_trigger.agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {blocked_trigger.agent_id} not found")

        # Identify capability gaps based on trigger context
        capability_gaps = await self._identify_capability_gaps(
            agent, blocked_trigger
        )

        # Generate learning objectives
        learning_objectives = await self._generate_learning_objectives(
            agent, blocked_trigger, capability_gaps
        )

        # AI-based duration estimation
        duration_estimate = await self.estimate_training_duration(
            agent_id=agent.id,
            capability_gaps=capability_gaps,
            target_maturity=AgentStatus.INTERN.value
        )

        # Determine training scenario template
        scenario_template = self._select_scenario_template(blocked_trigger)

        # Create proposal
        proposal = AgentProposal(
            agent_id=agent.id,
            agent_name=agent.name,
            proposal_type=ProposalType.TRAINING.value,
            title=f"Training Proposal: {agent.name} - {scenario_template} Fundamentals",
            description=f"""
This agent was blocked from executing an automated task because it's in STUDENT maturity level.
To proceed, this training will help the agent develop the necessary capabilities.

**Blocked Task:** {blocked_trigger.trigger_type}
**Capability Gaps:** {', '.join(capability_gaps)}

After completing this training, the agent will be able to handle similar tasks autonomously.
            """.strip(),
            learning_objectives=learning_objectives,
            capability_gaps=capability_gaps,
            training_scenario_template=scenario_template,
            estimated_duration_hours=duration_estimate.estimated_hours,
            duration_estimation_confidence=duration_estimate.confidence,
            duration_estimation_reasoning=duration_estimate.reasoning,
            status=ProposalStatus.PROPOSED.value,
            proposed_by="atom_meta_agent"
        )

        self.db.add(proposal)
        self.db.commit()
        self.db.refresh(proposal)

        # Link blocked trigger to proposal
        blocked_trigger.proposal_id = proposal.id
        self.db.commit()

        logger.info(
            f"Created training proposal {proposal.id} for agent {agent.id} "
            f"with {len(capability_gaps)} capability gaps, "
            f"estimated {duration_estimate.estimated_hours:.1f} hours"
        )

        return proposal

    async def approve_training(
        self,
        proposal_id: str,
        user_id: str,
        modifications: Optional[Dict[str, Any]] = None
    ) -> TrainingSession:
        """
        Approve training proposal and create training session.

        Args:
            proposal_id: Training proposal to approve
            user_id: User approving the training
            modifications: Optional modifications to duration, schedule, etc.

        Returns:
            Created training session
        """
        proposal = self.db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id
        ).first()

        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ProposalStatus.PROPOSED.value:
            raise ValueError(
                f"Proposal must be in PROPOSED status, current: {proposal.status}"
            )

        # Apply modifications if provided
        if modifications:
            if "duration_override_hours" in modifications:
                proposal.user_override_duration_hours = modifications[
                    "duration_override_hours"
                ]
            if "hours_per_day_limit" in modifications:
                proposal.hours_per_day_limit = modifications["hours_per_day_limit"]

        # Calculate training schedule
        duration_hours = (
            proposal.user_override_duration_hours or proposal.estimated_duration_hours
        )
        if proposal.hours_per_day_limit:
            days_needed = duration_hours / proposal.hours_per_day_limit
        else:
            days_needed = duration_hours / 8  # Assume 8 hours/day

        start_date = datetime.now()
        end_date = start_date + timedelta(days=days_needed)

        proposal.training_start_date = start_date
        proposal.training_end_date = end_date
        proposal.status = ProposalStatus.APPROVED.value
        proposal.approved_by = user_id
        proposal.approved_at = datetime.now()

        # Create training session
        session = TrainingSession(
            proposal_id=proposal.id,
            agent_id=proposal.agent_id,
            agent_name=proposal.agent_name,
            status="scheduled",
            supervisor_id=user_id,
            total_tasks=len(proposal.learning_objectives or [])
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(
            f"Approved training proposal {proposal_id}, created session {session.id}, "
            f"duration: {duration_hours:.1f} hours, ends: {end_date.isoformat()}"
        )

        return session

    async def complete_training_session(
        self,
        session_id: str,
        outcome: TrainingOutcome
    ) -> Dict[str, Any]:
        """
        Process training completion and update agent maturity.

        Process:
        1. Calculate performance score (0.0 to 1.0)
        2. Determine confidence boost (0.05 to 0.20 based on performance)
        3. Check if ready for maturity transition
        4. Update agent confidence score
        5. If new confidence >= 0.5, promote to INTERN
        6. Record in world model (via AgentGovernanceService)
        7. Allow retry of original blocked trigger

        Returns:
            Dict with maturity_update, confidence_boost, promoted_to_intern, etc.
        """
        session = self.db.query(TrainingSession).filter(
            TrainingSession.id == session_id
        ).first()

        if not session:
            raise ValueError(f"Training session {session_id} not found")

        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == session.agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {session.agent_id} not found")

        # Update session with outcomes
        session.status = "completed"
        session.completed_at = datetime.now()
        session.duration_seconds = int(
            (session.completed_at - session.started_at).total_seconds()
        ) if session.started_at else 0
        session.outcomes = {
            "performance_score": outcome.performance_score,
            "tasks_completed": outcome.tasks_completed,
            "total_tasks": outcome.total_tasks
        }
        session.performance_score = outcome.performance_score
        session.supervisor_feedback = outcome.supervisor_feedback
        session.errors_count = outcome.errors_count
        session.tasks_completed = outcome.tasks_completed
        session.capabilities_developed = outcome.capabilities_developed
        session.capability_gaps_remaining = outcome.capability_gaps_remaining

        # Calculate confidence boost based on performance
        confidence_boost = self._calculate_confidence_boost(outcome.performance_score)
        session.confidence_boost = confidence_boost

        # Update agent confidence
        old_confidence = agent.confidence_score
        agent.confidence_score = min(1.0, agent.confidence_score + confidence_boost)
        actual_boost = agent.confidence_score - old_confidence

        # Check for maturity transition to INTERN
        promoted_to_intern = False
        if agent.confidence_score >= 0.5 and agent.status == AgentStatus.STUDENT.value:
            agent.status = AgentStatus.INTERN.value
            session.promoted_to_intern = True
            promoted_to_intern = True
            logger.info(
                f"Agent {agent.id} promoted from STUDENT to INTERN "
                f"(confidence: {agent.confidence_score:.3f})"
            )

        # Update proposal execution result
        proposal = self.db.query(AgentProposal).filter(
            AgentProposal.id == session.proposal_id
        ).first()
        if proposal:
            proposal.status = ProposalStatus.EXECUTED.value
            proposal.completed_at = datetime.now()
            proposal.execution_result = {
                "session_id": session_id,
                "performance_score": outcome.performance_score,
                "confidence_boost": actual_boost,
                "promoted_to_intern": promoted_to_intern,
                "capabilities_developed": outcome.capabilities_developed
            }

        # Resolve blocked trigger if exists
        blocked_trigger = self.db.query(BlockedTriggerContext).filter(
            BlockedTriggerContext.proposal_id == session.proposal_id
        ).first()
        if blocked_trigger:
            blocked_trigger.resolved = True
            blocked_trigger.resolved_at = datetime.now()
            blocked_trigger.resolution_outcome = (
                f"Training completed. Performance: {outcome.performance_score:.2f}, "
                f"Confidence boost: {actual_boost:.3f}, "
                f"Promoted to INTERN: {promoted_to_intern}"
            )

        self.db.commit()
        self.db.refresh(session)

        logger.info(
            f"Completed training session {session_id} for agent {agent.id}. "
            f"Performance: {outcome.performance_score:.2f}, "
            f"Confidence boost: {actual_boost:.3f} ({old_confidence:.3f} → {agent.confidence_score:.3f}), "
            f"Promoted: {promoted_to_intern}"
        )

        return {
            "session_id": session_id,
            "agent_id": agent.id,
            "performance_score": outcome.performance_score,
            "confidence_boost": actual_boost,
            "old_confidence": old_confidence,
            "new_confidence": agent.confidence_score,
            "promoted_to_intern": promoted_to_intern,
            "new_status": agent.status,
            "capabilities_developed": outcome.capabilities_developed
        }

    async def get_training_history(
        self,
        agent_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve agent's training history"""
        sessions = self.db.query(TrainingSession).filter(
            TrainingSession.agent_id == agent_id
        ).order_by(TrainingSession.created_at.desc()).limit(limit).all()

        history = []
        for session in sessions:
            proposal = self.db.query(AgentProposal).filter(
                AgentProposal.id == session.proposal_id
            ).first()

            history.append({
                "session_id": session.id,
                "proposal_id": session.proposal_id,
                "status": session.status,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "performance_score": session.performance_score,
                "confidence_boost": session.confidence_boost,
                "promoted_to_intern": session.promoted_to_intern,
                "training_duration_hours": session.duration_seconds / 3600 if session.duration_seconds else None,
                "proposal_title": proposal.title if proposal else None,
                "capability_gaps": proposal.capability_gaps if proposal else []
            })

        return history

    async def estimate_training_duration(
        self,
        agent_id: str,
        capability_gaps: List[str],
        target_maturity: str
    ) -> TrainingDurationEstimate:
        """
        AI-generated training duration estimate based on multiple factors.

        Factors considered:
        - Agent's current confidence score (lower confidence → longer training)
        - Capability gaps identified (more gaps → longer training)
        - Historical training data (how long similar agents took)
        - Complexity of target tasks
        - Agent's learning rate (from previous training sessions)

        Returns:
            TrainingDurationEstimate with hours, confidence, reasoning
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Base estimation: 40 hours for student → intern transition
        base_hours = 40.0

        # Factor 1: Current confidence score (lower → longer training)
        # Confidence 0.0 → +20 hours, Confidence 0.4 → +4 hours
        confidence_factor = (0.5 - agent.confidence_score) * 50

        # Factor 2: Number of capability gaps
        # Each gap adds ~4 hours of training
        gaps_factor = len(capability_gaps) * 4

        # Factor 3: Historical data from similar agents
        similar_agents = await self._get_similar_agents_training_history(
            agent.category,
            target_maturity
        )

        if similar_agents:
            avg_hours = sum(a["duration_hours"] for a in similar_agents) / len(similar_agents)
            historical_factor = avg_hours
        else:
            historical_factor = base_hours

        # Factor 4: Agent's learning rate (from previous sessions)
        learning_rate = await self._calculate_learning_rate(agent_id)
        learning_factor = base_hours / learning_rate if learning_rate > 0 else base_hours

        # Calculate final estimate (weighted average)
        estimated_hours = (
            base_hours * 0.2 +
            confidence_factor * 0.2 +
            gaps_factor * 0.25 +
            historical_factor * 0.25 +
            learning_factor * 0.1
        )

        # Calculate confidence in estimate
        # Higher confidence if we have more historical data
        confidence = min(0.9, 0.5 + len(similar_agents) * 0.05)

        # Min/max bounds (10th/90th percentile)
        min_hours = estimated_hours * 0.7
        max_hours = estimated_hours * 1.5

        # Generate reasoning
        reasoning = f"""
Based on multiple factors:

1. **Current Confidence:** {agent.confidence_score:.2f} (target: 0.5 for INTERN)
   - Gap: {(0.5 - agent.confidence_score):.2f} confidence points

2. **Capability Gaps:** {len(capability_gaps)} identified
   - {', '.join(capability_gaps[:3])}
   {f'... and {len(capability_gaps) - 3} more' if len(capability_gaps) > 3 else ''}

3. **Historical Data:** {len(similar_agents)} similar {agent.category} agents
   - Average: {historical_factor:.1f} hours to reach INTERN level

4. **Learning Rate:** {learning_rate:.2f}x
   - {"Fast learner" if learning_rate > 1.0 else "Average pace" if learning_rate > 0.8 else "Needs more practice"}

**Estimated Duration:** {estimated_hours:.1f} hours
**Confidence Range:** {min_hours:.1f} - {max_hours:.1f} hours
        """.strip()

        return TrainingDurationEstimate(
            estimated_hours=round(estimated_hours, 1),
            confidence=round(confidence, 2),
            reasoning=reasoning,
            similar_agents=similar_agents,
            min_hours=round(min_hours, 1),
            max_hours=round(max_hours, 1)
        )

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _identify_capability_gaps(
        self,
        agent: AgentRegistry,
        blocked_trigger: BlockedTriggerContext
    ) -> List[str]:
        """Identify capability gaps based on blocked trigger"""
        # Analyze trigger context to determine what capabilities were needed
        trigger_type = blocked_trigger.trigger_type
        trigger_context = blocked_trigger.trigger_context

        gaps = []

        # Common capability gaps by trigger type
        capability_mapping = {
            "agent_message": ["task_execution", "context_understanding", "response_generation"],
            "workflow_trigger": ["workflow_automation", "decision_making", "task_coordination"],
            "form_submit": ["data_validation", "form_processing", "state_management"],
            "canvas_update": ["data_visualization", "presentation", "chart_generation"]
        }

        # Add base gaps for trigger type
        if trigger_type in capability_mapping:
            gaps.extend(capability_mapping[trigger_type])

        # Category-specific gaps
        category_mapping = {
            "Finance": ["financial_analysis", "reconciliation", "reporting"],
            "Sales": ["lead_management", "crm_operations", "sales_process"],
            "Operations": ["process_automation", "inventory_management", "logistics"],
            "HR": ["policy_knowledge", "onboarding", "employee_data"],
            "Support": ["ticket_resolution", "customer_communication", "escalation_handling"]
        }

        if agent.category in category_mapping:
            gaps.extend(category_mapping[agent.category])

        # Dedupe while preserving order
        seen = set()
        return [x for x in gaps if not (x in seen or seen.add(x))]

    async def _generate_learning_objectives(
        self,
        agent: AgentRegistry,
        blocked_trigger: BlockedTriggerContext,
        capability_gaps: List[str]
    ) -> List[str]:
        """Generate learning objectives for training proposal"""
        objectives = []

        # Base objectives for all training
        objectives.extend([
            f"Understand {blocked_trigger.trigger_type} execution flow",
            "Demonstrate reliable task completion with minimal errors",
            "Show consistent decision-making patterns"
        ])

        # Capability-specific objectives
        for gap in capability_gaps[:5]:  # Max 5 gaps for focused training
            objectives.append(f"Develop proficiency in {gap.replace('_', ' ')}")

        # Category-specific objectives
        category_objectives = {
            "Finance": [
                "Accurately process financial data",
                "Identify and flag anomalies",
                "Generate compliant reports"
            ],
            "Sales": [
                "Effectively manage leads through pipeline",
                "Update CRM records accurately",
                "Follow sales process guidelines"
            ]
        }

        if agent.category in category_objectives:
            objectives.extend(category_objectives[agent.category])

        return objectives

    def _select_scenario_template(self, blocked_trigger: BlockedTriggerContext) -> str:
        """Select appropriate training scenario template"""
        # Map trigger context to scenario template
        scenario_mapping = {
            "Finance": "Finance Fundamentals",
            "Sales": "Sales Operations",
            "Operations": "Process Automation",
            "HR": "HR Management",
            "Support": "Customer Support"
        }

        # Try to determine category from trigger context
        if "category" in blocked_trigger.trigger_context:
            category = blocked_trigger.trigger_context["category"]
            if category in scenario_mapping:
                return scenario_mapping[category]

        # Default to general training
        return "General Operations"

    def _calculate_confidence_boost(self, performance_score: float) -> float:
        """
        Calculate confidence boost based on performance score.

        Performance 0.0-0.3: 0.05 boost (poor)
        Performance 0.3-0.5: 0.10 boost (below average)
        Performance 0.5-0.7: 0.15 boost (good)
        Performance 0.7-1.0: 0.20 boost (excellent)
        """
        if performance_score < 0.3:
            return 0.05
        elif performance_score < 0.5:
            return 0.10
        elif performance_score < 0.7:
            return 0.15
        else:
            return 0.20

    async def _get_similar_agents_training_history(
        self,
        category: str,
        target_maturity: str
    ) -> List[Dict[str, Any]]:
        """Get training history from similar agents"""
        # Find agents in same category that reached target maturity
        similar_agents = self.db.query(AgentRegistry).filter(
            AgentRegistry.category == category,
            AgentRegistry.status == target_maturity,
            AgentRegistry.confidence_score >= 0.5
        ).all()

        history = []
        for agent in similar_agents[:5]:  # Max 5 similar agents
            # Get their training sessions
            sessions = self.db.query(TrainingSession).filter(
                TrainingSession.agent_id == agent.id,
                TrainingSession.status == "completed"
            ).all()

            if sessions:
                total_hours = sum(
                    s.duration_seconds / 3600 for s in sessions if s.duration_seconds
                )
                history.append({
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "duration_hours": total_hours,
                    "session_count": len(sessions)
                })

        return history

    async def _calculate_learning_rate(self, agent_id: str) -> float:
        """
        Calculate agent's learning rate from previous training sessions.

        Returns:
            Learning rate multiplier (1.0 = average, >1.0 = fast learner, <1.0 = slow)
        """
        sessions = self.db.query(TrainingSession).filter(
            TrainingSession.agent_id == agent_id,
            TrainingSession.status == "completed",
            TrainingSession.performance_score.isnot(None)
        ).all()

        if not sessions:
            return 1.0  # Average for new agents

        # Calculate average performance improvement over time
        avg_performance = sum(
            s.performance_score for s in sessions
        ) / len(sessions)

        # Learning rate: performance_score / expected_performance (0.7)
        # 0.7 is expected performance for average agent
        learning_rate = avg_performance / 0.7

        # Clamp to reasonable range
        return max(0.5, min(2.0, learning_rate))
