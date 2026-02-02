"""
Proposal Service

Manages action proposals from INTERN agents for human review.
Includes proposal creation, approval workflow, and execution.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from core.models import (
    AgentRegistry, AgentProposal, BlockedTriggerContext,
    ProposalStatus, ProposalType, AgentStatus
)

logger = logging.getLogger(__name__)


class ProposalService:
    """
    Manage action proposals from INTERN agents.

    INTERN agents generate proposals instead of executing directly.
    Humans review and approve/reject proposals before execution.
    """

    def __init__(self, db: Session):
        self.db = db

    async def create_action_proposal(
        self,
        intern_agent_id: str,
        trigger_context: Dict[str, Any],
        proposed_action: Dict[str, Any],
        reasoning: str
    ) -> AgentProposal:
        """
        Create proposal from INTERN agent for human review.

        Intern agents generate proposals instead of executing directly.
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == intern_agent_id
        ).first()

        if not agent:
            raise ValueError(f"Agent {intern_agent_id} not found")

        if agent.status != AgentStatus.INTERN.value:
            logger.warning(
                f"Agent {intern_agent_id} is not an INTERN agent (status: {agent.status})"
            )

        proposal = AgentProposal(
            agent_id=agent.id,
            agent_name=agent.name,
            proposal_type=ProposalType.ACTION.value,
            title=f"Action Proposal: {agent.name}",
            description=f"""
Agent is proposing an action for your review.

**Agent:** {agent.name}
**Category:** {agent.category}
**Confidence:** {agent.confidence_score:.2f}

**Proposed Action:** {proposed_action.get('action_type', 'Unknown')}

**Reasoning:**
{reasoning}

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

    async def submit_for_approval(
        self,
        proposal: AgentProposal
    ) -> None:
        """
        Submit proposal to human supervisor for review.

        Marks proposal as ready for review and notifies supervisors.
        """
        if proposal.status != ProposalStatus.PROPOSED.value:
            raise ValueError(
                f"Proposal must be in PROPOSED status, current: {proposal.status}"
            )

        # Proposal is already in PROPOSED status, just log
        logger.info(
            f"Proposal {proposal.id} submitted for approval by {proposal.proposed_by}"
        )

        # In production, this would send notification to supervisors
        # via WebSocket or other mechanism

    async def approve_proposal(
        self,
        proposal_id: str,
        user_id: str,
        modifications: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Approve proposal and execute the proposed action.

        Args:
            proposal_id: Proposal to approve
            user_id: User approving the proposal
            modifications: Optional modifications to proposed action

        Returns:
            Execution result
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

        # Update proposal
        proposal.status = ProposalStatus.APPROVED.value
        proposal.approved_by = user_id
        proposal.approved_at = datetime.now()

        if modifications:
            # Apply modifications to proposed action
            if proposal.proposed_action:
                proposal.proposed_action.update(modifications)
            proposal.modifications = modifications

        # Execute the proposed action
        # (In production, this would trigger the actual execution)
        execution_result = await self._execute_proposed_action(proposal)

        proposal.execution_result = execution_result
        proposal.status = ProposalStatus.EXECUTED.value
        proposal.completed_at = datetime.now()

        self.db.commit()
        self.db.refresh(proposal)

        logger.info(
            f"Approved and executed proposal {proposal_id} by user {user_id}"
        )

        return execution_result

    async def reject_proposal(
        self,
        proposal_id: str,
        user_id: str,
        reason: str
    ) -> None:
        """
        Reject proposal with feedback.

        Args:
            proposal_id: Proposal to reject
            user_id: User rejecting the proposal
            reason: Reason for rejection
        """
        proposal = self.db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id
        ).first()

        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        proposal.status = ProposalStatus.REJECTED.value
        proposal.approved_by = user_id
        proposal.approved_at = datetime.now()

        # Store rejection reason in execution_result
        proposal.execution_result = {
            "rejected": True,
            "rejected_by": user_id,
            "rejected_at": datetime.now().isoformat(),
            "reason": reason
        }

        self.db.commit()

        logger.info(
            f"Rejected proposal {proposal_id} by user {user_id}. Reason: {reason}"
        )

    async def get_pending_proposals(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50
    ) -> List[AgentProposal]:
        """Get pending proposals awaiting review"""
        query = self.db.query(AgentProposal).filter(
            AgentProposal.status == ProposalStatus.PROPOSED.value
        )

        if agent_id:
            query = query.filter(AgentProposal.agent_id == agent_id)

        return query.order_by(
            AgentProposal.created_at.desc()
        ).limit(limit).all()

    async def get_proposal_history(
        self,
        agent_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get agent's proposal history"""
        proposals = self.db.query(AgentProposal).filter(
            AgentProposal.agent_id == agent_id
        ).order_by(
            AgentProposal.created_at.desc()
        ).limit(limit).all()

        history = []
        for proposal in proposals:
            history.append({
                "proposal_id": proposal.id,
                "proposal_type": proposal.proposal_type,
                "title": proposal.title,
                "status": proposal.status,
                "created_at": proposal.created_at.isoformat(),
                "approved_at": proposal.approved_at.isoformat() if proposal.approved_at else None,
                "approved_by": proposal.approved_by,
                "execution_result": proposal.execution_result
            })

        return history

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _execute_proposed_action(
        self,
        proposal: AgentProposal
    ) -> Dict[str, Any]:
        """
        Execute the proposed action.

        In production, this would integrate with the appropriate
        execution engine based on the action type.

        For now, returns a placeholder result.
        """
        proposed_action = proposal.proposed_action or {}
        action_type = proposed_action.get("action_type", "unknown")

        logger.info(
            f"Executing action {action_type} from proposal {proposal.id}"
        )

        # Placeholder execution
        # In production, this would:
        # - Trigger the agent with the proposed action
        # - Monitor execution
        # - Return actual results

        return {
            "success": True,
            "action_type": action_type,
            "executed_at": datetime.now().isoformat(),
            "proposal_id": proposal.id,
            "agent_id": proposal.agent_id,
            "message": f"Action {action_type} executed successfully"
        }
