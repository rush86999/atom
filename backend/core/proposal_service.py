"""
Proposal Service

Manages action proposals from INTERN agents for human review.
Includes proposal creation, approval workflow, and execution.
"""

from datetime import datetime
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
                user_id=user_id,
                agent_name=proposal.agent_name,
                status="running",
                input_data={
                    "proposal_id": proposal.id,
                    "action": action
                }
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
            execution.output_data = result
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
                user_id=user_id,
                agent_name=proposal.agent_name,
                status="running",
                input_data={
                    "proposal_id": proposal.id,
                    "action": action
                }
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
            execution.output_data = {"canvas_id": canvas_id}
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
                user_id=user_id,
                agent_name=proposal.agent_name,
                status="running",
                input_data={
                    "proposal_id": proposal.id,
                    "action": action
                }
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
            execution.output_data = result
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
                user_id=user_id,
                agent_name=proposal.agent_name,
                status="running",
                input_data={
                    "proposal_id": proposal.id,
                    "action": action
                }
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
            execution.output_data = result
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
                user_id=user_id,
                agent_name=proposal.agent_name,
                status="running",
                input_data={
                    "proposal_id": proposal.id,
                    "action": action
                }
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
            execution.output_data = result
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
                user_id=user_id,
                agent_name=action.get("agent_name", proposal.agent_name),
                status="running",
                input_data={
                    "proposal_id": proposal.id,
                    "action": action,
                    "triggered_by": agent_id
                }
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
            execution.output_data = result
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
