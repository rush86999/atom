"""
Proposal Service

Manages action proposals from INTERN agents for human review.
Includes proposal creation, approval workflow, and execution.
"""

from datetime import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    Episode,
    EpisodeSegment,
    ProposalStatus,
    ProposalType,
)

logger = logging.getLogger(__name__)

# Feature flag for proposal execution
PROPOSAL_EXECUTION_ENABLED = os.getenv("PROPOSAL_EXECUTION_ENABLED", "true").lower() == "true"


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

        # NEW: Create learning episode from approved proposal
        await self._create_proposal_episode(
            proposal=proposal,
            outcome="approved",
            modifications=modifications,
            execution_result=execution_result
        )

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

        # NEW: Create learning episode from rejected proposal
        await self._create_proposal_episode(
            proposal=proposal,
            outcome="rejected",
            rejection_reason=reason
        )

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

        Integrates with the appropriate execution engine based on action type.
        Supports: browser_automate, canvas_present, integration_connect,
                  workflow_trigger, device_command, agent_execute

        Args:
            proposal: The proposal to execute

        Returns:
            Execution result with success status, output, and metadata
        """
        if not PROPOSAL_EXECUTION_ENABLED:
            logger.warning(f"Proposal execution disabled, skipping {proposal.id}")
            return {
                "success": False,
                "skipped": True,
                "message": "Proposal execution is disabled",
                "proposal_id": proposal.id
            }

        proposed_action = proposal.proposed_action or {}
        action_type = proposed_action.get("action_type", "unknown")

        logger.info(
            f"Executing action {action_type} from proposal {proposal.id}"
        )

        try:
            # Route to appropriate handler
            if action_type == "browser_automate":
                return await self._execute_browser_action(proposal, proposed_action)
            elif action_type == "canvas_present":
                return await self._execute_canvas_action(proposal, proposed_action)
            elif action_type == "integration_connect":
                return await self._execute_integration_action(proposal, proposed_action)
            elif action_type == "workflow_trigger":
                return await self._execute_workflow_action(proposal, proposed_action)
            elif action_type == "device_command":
                return await self._execute_device_action(proposal, proposed_action)
            elif action_type == "agent_execute":
                return await self._execute_agent_action(proposal, proposed_action)
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return {
                    "success": False,
                    "error": f"Unknown action type: {action_type}",
                    "action_type": action_type,
                    "executed_at": datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to execute action {action_type}: {e}")
            return {
                "success": False,
                "error": str(e),
                "action_type": action_type,
                "executed_at": datetime.now().isoformat(),
                "proposal_id": proposal.id
            }

    async def _execute_browser_action(
        self,
        proposal: AgentProposal,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute browser automation action.

        Action parameters:
        - url: Target URL
        - actions: List of browser actions (navigate, click, fill, etc.)
        - session_id: Optional existing browser session
        """
        try:
            # Import here to avoid circular dependency
            from tools.browser_tool import execute_browser_automation

            user_id = proposal.approved_by  # User who approved
            agent_id = proposal.agent_id

            # Create execution tracking
            execution = AgentExecution(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                workspace_id="default",
                status="running",
                input_summary=json.dumps({
                    "proposal_id": proposal.id,
                    "action": action
                }),
                triggered_by="proposal"
            )
            self.db.add(execution)
            self.db.commit()

            # Execute browser automation
            result = await execute_browser_automation(
                db=self.db,
                user_id=user_id,
                agent_id=agent_id,
                url=action.get("url"),
                actions=action.get("actions", []),
                session_id=action.get("session_id"),
                execution_id=execution.id
            )

            # Update execution
            execution.status = "completed" if result.get("success") else "failed"
            execution.output_summary = json.dumps(result) if isinstance(result, dict) else str(result)
            execution.completed_at = datetime.now()
            self.db.commit()

            return {
                "success": result.get("success", False),
                "action_type": "browser_automate",
                "execution_id": execution.id,
                "executed_at": datetime.now().isoformat(),
                "proposal_id": proposal.id,
                "result": result
            }

        except ImportError:
            logger.error("Browser tool not available")
            return {
                "success": False,
                "error": "Browser automation not available",
                "action_type": "browser_automate"
            }
        except Exception as e:
            logger.error(f"Browser action failed: {e}")
            raise

    async def _execute_canvas_action(
        self,
        proposal: AgentProposal,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute canvas presentation action.

        Action parameters:
        - canvas_type: Type of canvas (chart, markdown, form, etc.)
        - content: Canvas content
        - title: Optional title
        - canvas_id: Optional existing canvas
        """
        try:
            from tools.canvas_tool import present_to_canvas

            user_id = proposal.approved_by
            agent_id = proposal.agent_id

            # Create execution tracking
            execution = AgentExecution(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                workspace_id="default",
                status="running",
                input_summary=json.dumps({
                    "proposal_id": proposal.id,
                    "action": action
                }),
                triggered_by="proposal"
            )
            self.db.add(execution)
            self.db.commit()

            # Present to canvas
            canvas_id = await present_to_canvas(
                db=self.db,
                user_id=user_id,
                agent_id=agent_id,
                agent_execution_id=execution.id,
                canvas_type=action.get("canvas_type", "chart"),
                content=action.get("content", {}),
                title=action.get("title"),
                session_id=action.get("session_id")
            )

            # Update execution
            execution.status = "completed"
            execution.output_summary = json.dumps({"canvas_id": canvas_id}) if isinstance({"canvas_id": canvas_id}, dict) else str({"canvas_id": canvas_id})
            execution.completed_at = datetime.now()
            self.db.commit()

            return {
                "success": True,
                "action_type": "canvas_present",
                "execution_id": execution.id,
                "canvas_id": canvas_id,
                "executed_at": datetime.now().isoformat(),
                "proposal_id": proposal.id
            }

        except Exception as e:
            logger.error(f"Canvas action failed: {e}")
            raise

    async def _execute_integration_action(
        self,
        proposal: AgentProposal,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute integration connection action.

        Action parameters:
        - integration_type: Type of integration (gmail, slack, jira, etc.)
        - operation: Operation to perform
        - parameters: Operation parameters
        """
        try:
            from core.integrations import get_integration_service

            user_id = proposal.approved_by
            agent_id = proposal.agent_id
            integration_type = action.get("integration_type")

            # Create execution tracking
            execution = AgentExecution(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                workspace_id="default",
                status="running",
                input_summary=json.dumps({
                    "proposal_id": proposal.id,
                    "action": action
                }),
                triggered_by="proposal"
            )
            self.db.add(execution)
            self.db.commit()

            # Get integration service and execute
            service = get_integration_service(integration_type)
            result = await service.execute_operation(
                user_id=user_id,
                operation=action.get("operation"),
                parameters=action.get("parameters", {})
            )

            # Update execution
            execution.status = "completed" if result.get("success") else "failed"
            execution.output_summary = json.dumps(result) if isinstance(result, dict) else str(result)
            execution.completed_at = datetime.now()
            self.db.commit()

            return {
                "success": result.get("success", False),
                "action_type": "integration_connect",
                "integration_type": integration_type,
                "execution_id": execution.id,
                "executed_at": datetime.now().isoformat(),
                "proposal_id": proposal.id,
                "result": result
            }

        except Exception as e:
            logger.error(f"Integration action failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "action_type": "integration_connect"
            }

    async def _execute_workflow_action(
        self,
        proposal: AgentProposal,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute workflow trigger action.

        Action parameters:
        - workflow_id: Workflow to trigger
        - parameters: Workflow parameters
        """
        try:
            from core.workflow_engine import trigger_workflow

            user_id = proposal.approved_by
            agent_id = proposal.agent_id
            workflow_id = action.get("workflow_id")

            # Create execution tracking
            execution = AgentExecution(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                workspace_id="default",
                status="running",
                input_summary=json.dumps({
                    "proposal_id": proposal.id,
                    "action": action
                }),
                triggered_by="proposal"
            )
            self.db.add(execution)
            self.db.commit()

            # Trigger workflow
            result = await trigger_workflow(
                db=self.db,
                user_id=user_id,
                workflow_id=workflow_id,
                parameters=action.get("parameters", {}),
                triggered_by_agent=agent_id,
                execution_id=execution.id
            )

            # Update execution
            execution.status = "completed" if result.get("success") else "failed"
            execution.output_summary = json.dumps(result) if isinstance(result, dict) else str(result)
            execution.completed_at = datetime.now()
            self.db.commit()

            return {
                "success": result.get("success", False),
                "action_type": "workflow_trigger",
                "workflow_id": workflow_id,
                "execution_id": execution.id,
                "executed_at": datetime.now().isoformat(),
                "proposal_id": proposal.id,
                "result": result
            }

        except Exception as e:
            logger.error(f"Workflow action failed: {e}")
            raise

    async def _execute_device_action(
        self,
        proposal: AgentProposal,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute device command action.

        Action parameters:
        - device_id: Target device
        - command_type: Type of command (camera, location, etc.)
        - parameters: Command parameters
        """
        try:
            from tools.device_tool import execute_device_command

            user_id = proposal.approved_by
            agent_id = proposal.agent_id

            # Create execution tracking
            execution = AgentExecution(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                workspace_id="default",
                status="running",
                input_summary=json.dumps({
                    "proposal_id": proposal.id,
                    "action": action
                }),
                triggered_by="proposal"
            )
            self.db.add(execution)
            self.db.commit()

            # Execute device command
            result = await execute_device_command(
                db=self.db,
                user_id=user_id,
                agent_id=agent_id,
                device_id=action.get("device_id"),
                command_type=action.get("command_type"),
                parameters=action.get("parameters", {}),
                execution_id=execution.id
            )

            # Update execution
            execution.status = "completed" if result.get("success") else "failed"
            execution.output_summary = json.dumps(result) if isinstance(result, dict) else str(result)
            execution.completed_at = datetime.now()
            self.db.commit()

            return {
                "success": result.get("success", False),
                "action_type": "device_command",
                "execution_id": execution.id,
                "executed_at": datetime.now().isoformat(),
                "proposal_id": proposal.id,
                "result": result
            }

        except Exception as e:
            logger.error(f"Device action failed: {e}")
            raise

    async def _execute_agent_action(
        self,
        proposal: AgentProposal,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute agent command action.

        Action parameters:
        - target_agent_id: Agent to execute
        - prompt: Prompt/instruction for agent
        - parameters: Additional parameters
        """
        try:
            from core.generic_agent import execute_agent

            user_id = proposal.approved_by
            agent_id = proposal.agent_id
            target_agent_id = action.get("target_agent_id")

            # Create execution tracking
            execution = AgentExecution(
                id=str(uuid.uuid4()),
                agent_id=target_agent_id or agent_id,
                workspace_id="default",
                status="running",
                input_summary=json.dumps({
                    "proposal_id": proposal.id,
                    "action": action,
                    "triggered_by": agent_id
                }),
                triggered_by="proposal"
            )
            self.db.add(execution)
            self.db.commit()

            # Execute agent
            result = await execute_agent(
                db=self.db,
                user_id=user_id,
                agent_id=target_agent_id or agent_id,
                prompt=action.get("prompt"),
                parameters=action.get("parameters", {}),
                execution_id=execution.id
            )

            # Update execution
            execution.status = "completed" if result.get("success") else "failed"
            execution.output_summary = json.dumps(result) if isinstance(result, dict) else str(result)
            execution.completed_at = datetime.now()
            self.db.commit()

            return {
                "success": result.get("success", False),
                "action_type": "agent_execute",
                "target_agent_id": target_agent_id or agent_id,
                "execution_id": execution.id,
                "executed_at": datetime.now().isoformat(),
                "proposal_id": proposal.id,
                "result": result
            }

        except Exception as e:
            logger.error(f"Agent action failed: {e}")
            raise

    # ========================================================================
    # Proposal Episode Creation
    # ========================================================================

    async def _create_proposal_episode(
        self,
        proposal: AgentProposal,
        outcome: str,
        **kwargs
    ):
        """
        Create episode from proposal approval/rejection.

        Captures learning from proposal decisions to improve agent behavior.

        Args:
            proposal: The proposal that was approved/rejected
            outcome: "approved" or "rejected"
            **kwargs: Additional context (modifications, rejection_reason, execution_result)
        """
        try:
            from core.episode_segmentation_service import EpisodeSegmentationService

            episode_service = EpisodeSegmentationService(self.db)

            # Get agent to determine maturity
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == proposal.agent_id
            ).first()

            maturity_level = AgentStatus.INTERN.value
            if agent:
                if hasattr(agent.status, 'value'):
                    maturity_level = agent.status.value
                else:
                    maturity_level = str(agent.status)

            # Format proposal content
            proposal_content = self._format_proposal_content(proposal, outcome)

            # Format proposal outcome
            outcome_content = self._format_proposal_outcome(proposal, outcome, **kwargs)

            # Create episode
            episode = Episode(
                id=str(uuid.uuid4()),
                title=f"Proposal {outcome.capitalize()}: {proposal.title}",
                description=f"INTERN agent proposal {outcome} by human reviewer",
                summary=proposal_content[:200] + "..." if len(proposal_content) > 200 else proposal_content,
                agent_id=proposal.agent_id,
                user_id=proposal.approved_by or proposal.proposed_by,
                workspace_id="default",

                # Link to proposal (NEW)
                proposal_id=proposal.id,
                proposal_outcome=outcome,
                rejection_reason=kwargs.get("rejection_reason"),

                # Timing
                started_at=proposal.created_at,
                ended_at=proposal.completed_at or proposal.approved_at or datetime.now(),
                duration_seconds=int((
                    (proposal.completed_at or proposal.approved_at or datetime.now()) -
                    proposal.created_at
                ).total_seconds()) if proposal.created_at else None,
                status="completed",

                # Content
                topics=self._extract_proposal_topics(proposal),
                entities=self._extract_proposal_entities(proposal),
                importance_score=self._calculate_proposal_importance(outcome, proposal),

                # Graduation fields
                maturity_at_time=maturity_level,
                human_intervention_count=1,  # Human approval/rejection is an intervention
                human_edits=kwargs.get("modifications", []),
                constitutional_score=None,
                world_model_state="v1.0"
            )

            self.db.add(episode)
            self.db.commit()
            self.db.refresh(episode)

            # Create segments
            segment_order = 0

            # Proposal segment
            proposal_segment = EpisodeSegment(
                id=str(uuid.uuid4()),
                episode_id=episode.id,
                segment_type="proposal",
                sequence_order=segment_order,
                content=proposal_content,
                content_summary=f"{outcome.capitalize()} proposal: {proposal.title[:50]}",
                source_type="agent_proposal",
                source_id=proposal.id
            )
            self.db.add(proposal_segment)
            segment_order += 1

            # Outcome segment
            outcome_segment = EpisodeSegment(
                id=str(uuid.uuid4()),
                episode_id=episode.id,
                segment_type="reflection",
                sequence_order=segment_order,
                content=outcome_content,
                content_summary=f"Proposal {outcome} with modifications: {len(kwargs.get('modifications', []))}",
                source_type="agent_proposal",
                source_id=proposal.id
            )
            self.db.add(outcome_segment)

            self.db.commit()

            logger.info(
                f"Created proposal episode {episode.id} for proposal {proposal.id} (outcome: {outcome})"
            )

        except Exception as e:
            logger.error(f"Failed to create proposal episode: {e}")
            # Don't raise - episode creation shouldn't break proposal workflow

    def _format_proposal_content(self, proposal: AgentProposal, outcome: str) -> str:
        """Format proposal content for episode"""
        parts = []

        parts.append(f"Proposal Title: {proposal.title}")
        parts.append(f"Proposal Type: {proposal.proposal_type}")
        parts.append(f"Agent: {proposal.agent_name}")
        parts.append(f"Created: {proposal.created_at.isoformat() if proposal.created_at else 'Unknown'}")

        if proposal.reasoning:
            parts.append(f"\nReasoning:\n{proposal.reasoning}")

        if proposal.proposed_action:
            action_type = proposal.proposed_action.get("action_type", "unknown")
            parts.append(f"\nProposed Action Type: {action_type}")

        return "\n".join(parts)

    def _format_proposal_outcome(
        self,
        proposal: AgentProposal,
        outcome: str,
        **kwargs
    ) -> str:
        """Format proposal outcome for episode"""
        parts = []

        parts.append(f"Outcome: {outcome.upper()}")
        parts.append(f"Reviewed by: {proposal.approved_by or 'Unknown'}")
        parts.append(f"Reviewed at: {proposal.approved_at.isoformat() if proposal.approved_at else 'Unknown'}")

        if outcome == "approved":
            modifications = kwargs.get("modifications", [])
            if modifications:
                parts.append(f"\nModifications Applied: {len(modifications)}")
                for mod in modifications[:5]:  # Limit to first 5
                    parts.append(f"  - {mod}")

            execution_result = kwargs.get("execution_result", {})
            if execution_result:
                success = execution_result.get("success", False)
                parts.append(f"\nExecution Result: {'SUCCESS' if success else 'FAILED'}")

        elif outcome == "rejected":
            reason = kwargs.get("rejection_reason", "No reason provided")
            parts.append(f"\nRejection Reason: {reason}")

        return "\n".join(parts)

    def _extract_proposal_topics(self, proposal: AgentProposal) -> List[str]:
        """Extract topics from proposal"""
        topics = set()

        # Add proposal type
        topics.add(proposal.proposal_type)

        # Extract from title
        if proposal.title:
            words = proposal.title.lower().split()
            topics.update([w for w in words if len(w) > 4][:3])

        # Extract from reasoning
        if proposal.reasoning:
            words = proposal.reasoning.lower().split()
            topics.update([w for w in words if len(w) > 4][:3])

        # Extract from action type
        if proposal.proposed_action:
            action_type = proposal.proposed_action.get("action_type", "")
            if action_type:
                topics.add(action_type)

        return list(topics)[:5]

    def _extract_proposal_entities(self, proposal: AgentProposal) -> List[str]:
        """Extract entities from proposal"""
        entities = set()

        # Add IDs as entities
        entities.add(f"proposal:{proposal.id}")
        entities.add(f"agent:{proposal.agent_id}")

        if proposal.approved_by:
            entities.add(f"reviewer:{proposal.approved_by}")

        # Extract from proposed action
        if proposal.proposed_action:
            # Add action-specific entities
            for key, value in proposal.proposed_action.items():
                if isinstance(value, str) and len(value) < 50:
                    entities.add(value)

        return list(entities)

    def _calculate_proposal_importance(self, outcome: str, proposal: AgentProposal) -> float:
        """
        Calculate episode importance score based on proposal outcome.

        Higher importance for:
        - Rejected proposals (learning opportunities)
        - Approved proposals with modifications (corrections)
        - Complex action types

        Returns:
            Importance score (0.0 to 1.0)
        """
        # Base score
        score = 0.5

        # Outcome adjustment
        if outcome == "rejected":
            score += 0.3  # Rejections are important learning opportunities
        elif outcome == "approved":
            score += 0.1  # Approvals are less critical

        # Modifications boost
        if proposal.modifications:
            score += 0.1

        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))

    # ========================================================================
    # Autonomous Supervisor Integration
    # ========================================================================

    async def review_with_autonomous_supervisor(
        self,
        proposal: AgentProposal
    ) -> Optional[Dict[str, Any]]:
        """
        Review proposal with autonomous supervisor fallback.

        When human supervisor is unavailable, tries to find autonomous agent
        to review and approve/reject proposal.

        Args:
            proposal: Proposal to review

        Returns:
            Dict with supervisor type and review result, or None if no supervisor available
        """
        from core.autonomous_supervisor_service import AutonomousSupervisorService
        from core.user_activity_service import UserActivityService

        # First, try to find human supervisor
        user_activity_service = UserActivityService(self.db)
        available_supervisors = await user_activity_service.get_available_supervisors(
            category=proposal.agent_id
        )

        if available_supervisors:
            return {
                "supervisor_type": "human",
                "supervisor_id": available_supervisors[0]["user_id"],
                "available": True
            }

        # No human available, try autonomous supervisor
        autonomous_service = AutonomousSupervisorService(self.db)

        # Get the intern agent
        intern_agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == proposal.agent_id
        ).first()

        if not intern_agent:
            logger.error(f"Agent not found: {proposal.agent_id}")
            return None

        # Find autonomous supervisor
        supervisor = await autonomous_service.find_autonomous_supervisor(
            intern_agent=intern_agent
        )

        if not supervisor:
            logger.warning(f"No autonomous supervisor found for {proposal.agent_id}")
            return None

        # Perform review
        review = await autonomous_service.review_proposal(
            proposal=proposal,
            supervisor=supervisor
        )

        return {
            "supervisor_type": "autonomous",
            "supervisor_id": supervisor.id,
            "supervisor_name": supervisor.name,
            "review": {
                "approved": review.approved,
                "confidence_score": review.confidence_score,
                "risk_level": review.risk_level,
                "reasoning": review.reasoning,
                "suggested_modifications": review.suggested_modifications
            }
        }

    async def autonomous_approve_or_reject(
        self,
        proposal_id: str
    ) -> Dict[str, Any]:
        """
        Attempt autonomous approval/rejection of proposal.

        Args:
            proposal_id: Proposal to process

        Returns:
            Dict with approval result
        """
        proposal = self.db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id
        ).first()

        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        # Get autonomous supervisor review
        review_result = await self.review_with_autonomous_supervisor(proposal)

        if not review_result:
            return {
                "success": False,
                "message": "No supervisor available (human or autonomous)"
            }

        # If human supervisor available, wait for human approval
        if review_result["supervisor_type"] == "human":
            return {
                "success": False,
                "message": "Human supervisor available, awaiting manual approval",
                "supervisor_type": "human",
                "supervisor_id": review_result["supervisor_id"]
            }

        # Autonomous supervisor available
        from core.autonomous_supervisor_service import AutonomousSupervisorService, ProposalReview

        review_data = review_result["review"]
        review = ProposalReview(
            approved=review_data["approved"],
            confidence_score=review_data["confidence_score"],
            risk_level=review_data["risk_level"],
            reasoning=review_data["reasoning"],
            suggested_modifications=review_data.get("suggested_modifications", [])
        )

        autonomous_service = AutonomousSupervisorService(self.db)

        if review.approved:
            # Approve and execute
            success = await autonomous_service.approve_proposal(
                proposal_id=proposal_id,
                supervisor_id=review_result["supervisor_id"],
                review=review
            )

            if success:
                return {
                    "success": True,
                    "message": "Proposal approved and executed by autonomous supervisor",
                    "supervisor_type": "autonomous",
                    "supervisor_id": review_result["supervisor_id"],
                    "review": review_data
                }
        else:
            # Reject proposal
            proposal.status = ProposalStatus.REJECTED.value
            proposal.approved_by = review_result["supervisor_id"]
            proposal.approved_at = datetime.now()
            proposal.execution_result = {
                "autonomous_rejection": True,
                "supervisor_id": review_result["supervisor_id"],
                "review": review_data
            }
            self.db.commit()

            return {
                "success": False,
                "message": "Proposal rejected by autonomous supervisor",
                "supervisor_type": "autonomous",
                "supervisor_id": review_result["supervisor_id"],
                "review": review_data
            }

        return {
            "success": False,
            "message": "Failed to process autonomous approval"
        }
