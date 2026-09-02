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
from core.agent_learning_enhanced import AgentLearningEnhanced

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
        reasoning: str,
        canvas_id: Optional[str] = None,
        session_id: Optional[str] = None,
        title: Optional[str] = None
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
            # Bug 8 fix: was a warning only — non-INTERN agents could still
            # create proposals. Now enforced as a hard block.
            raise PermissionError(
                f"Agent {intern_agent_id} is not an INTERN agent (status: {agent.status}). "
                f"Only INTERN agents can create proposals."
            )
        # Fetch agent name for denormalization
        # The agent object is already fetched above, so we can use it directly.
        agent_name = agent.name if agent else "Unknown Agent"

        # Phase 4 — match-confidence gate: if selector_candidates are present,
        # append a reviewer-visible block showing alternatives + rationale.
        candidates_block = ""
        sel_candidates = proposed_action.get("selector_candidates") or []
        if sel_candidates:
            cand_lines = []
            for i, c in enumerate(sel_candidates[:5]):
                if isinstance(c, dict):
                    cand_lines.append(
                        f"  {i}. `{c.get('selector', '?')}` — "
                        f"match_count={c.get('match_count', '?')}, "
                        f"text_only={c.get('is_text_only', '?')}"
                    )
                else:
                    cand_lines.append(f"  {i}. {c}")
            candidates_block = f"""

**Selector candidates ({len(sel_candidates)}):**
{chr(10).join(cand_lines)}

**Match rationale:** {proposed_action.get('match_rationale', 'n/a')}
**Match score:** {proposed_action.get('match_score', 'n/a')}
**Chosen index:** {proposed_action.get('chosen_index', 'n/a')}
"""
            if proposed_action.get("per_field_confidence"):
                pf = proposed_action["per_field_confidence"]
                pf_lines = [
                    f"  - `{sel}`: level={data.get('level', '?')} score={data.get('score', '?')}"
                    for sel, data in pf.items()
                ]
                candidates_block += "\n**Per-field confidence:**\n" + "\n".join(pf_lines)

        proposal = AgentProposal(
            tenant_id=getattr(agent, 'tenant_id', None) or 'default',
            user_id=getattr(agent, 'user_id', None) or 'system',
            agent_id=agent.id,
            agent_name=agent_name, # Added agent_name
            canvas_id=canvas_id,
            session_id=session_id,
            proposal_type=ProposalType.ACTION.value,
            title=title or f"Action Proposal: {agent.name}",
            description=f"""
Agent is proposing an action for your review.

**Agent:** {agent.name}
**Category:** {agent.category}
**Confidence:** {agent.confidence_score or 0:.2f}

**Proposed Action:** {proposed_action.get('action_type', 'Unknown')}
{candidates_block}
**Reasoning:**
{reasoning}

Please review and approve or reject this proposal.
            """.strip(),
            proposal_data=proposed_action,
            status=ProposalStatus.PENDING_APPROVAL.value
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
        if proposal.status != ProposalStatus.PENDING_APPROVAL.value:
            raise ValueError(
                f"Proposal must be in PENDING_APPROVAL status, current: {proposal.status}"
            )

        # Proposal is already in PENDING_APPROVAL status, just log
        logger.info(
            f"Proposal {proposal.id} submitted for approval by {proposal.user_id}"
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
        learning = AgentLearningEnhanced(self.db)
        
        proposal = self.db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id
        ).first()

        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ProposalStatus.PENDING_APPROVAL.value:
            raise ValueError(
                f"Proposal must be in PENDING_APPROVAL status, current: {proposal.status}"
            )

        # Update proposal
        proposal.status = ProposalStatus.APPROVED.value
        proposal.approved_by = user_id
        proposal.approved_at = datetime.now()

        if modifications:
            # Bug 12 fix: capture original BEFORE mutation, then apply on a
            # COPY so a failed execution doesn't leave the proposal row in
            # a partially-mutated state.
            original_action = proposal.proposed_action.copy() if proposal.proposed_action else {}
            # Don't mutate proposal.proposed_action yet — build the action to
            # execute first, then persist only after execution succeeds.
            _action_to_execute = dict(proposal.proposed_action) if proposal.proposed_action else {}
            _action_to_execute.update(modifications)
        else:
            original_action = None
            _action_to_execute = proposal.proposed_action

        # Execute the proposed action using the prepared (possibly modified) copy
        try:
            execution_result = await self._execute_proposed_action_with(proposal, _action_to_execute)
        except Exception as e:
            logger.error(f"Failed to execute proposal {proposal.id}: {e}")
            proposal.execution_result = {
                "success": False,
                "error": "Proposal execution failed",
                "proposal_id": proposal.id
            }
            proposal.status = ProposalStatus.EXECUTION_FAILED.value
            proposal.executed_at = datetime.now()
            self.db.commit()
            raise

        # Bug 12 fix: only now (after successful execution) apply mutations
        # to the persisted proposal row. Previously mutations were applied
        # BEFORE execution, so a failure left the row in an inconsistent state.
        # Reassign proposal_data (the JSON column) with a NEW dict — in-place
        # mutation of the JSON value is not tracked by SQLAlchemy, so it would
        # silently fail to persist the modified action.
        if modifications:
            if proposal.proposed_action:
                merged_action = dict(proposal.proposed_action)
                merged_action.update(modifications)
                proposal.proposal_data = merged_action
            proposal.modifications = modifications

        proposal.execution_result = execution_result
        if execution_result.get("success"):
            proposal.status = ProposalStatus.EXECUTED.value
        else:
            proposal.status = ProposalStatus.EXECUTION_FAILED.value
        proposal.executed_at = datetime.now()

        self.db.commit()
        self.db.refresh(proposal)

        # NEW: Create learning episode from approved proposal
        await self._create_proposal_episode(
            proposal=proposal,
            outcome="approved" if execution_result.get("success") else "failed",
            modifications=modifications,
            execution_result=execution_result
        )

        # NEW: Record correction if modifications were made
        if modifications:
            await learning.record_user_correction(
                agent_id=proposal.agent_id,
                tenant_id=getattr(proposal, 'tenant_id', 'default'),
                original_action=original_action, # Captured before update
                corrected_action=proposal.proposed_action, # Current updated action
                context=f"Modification during proposal {proposal.id} approval"
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
        learning = AgentLearningEnhanced(self.db)
        proposal = self.db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id
        ).first()

        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        # Guard the state machine like approve_proposal does: a proposal that
        # was already approved/executed must not be flipped to REJECTED — that
        # would rewrite the audit trail of an action that already ran.
        if proposal.status != ProposalStatus.PENDING_APPROVAL.value:
            raise ValueError(
                f"Proposal must be in PENDING_APPROVAL status, current: {proposal.status}"
            )

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

        # NEW: Record rejection for learning
        await learning.record_rejection(
            agent_id=proposal.agent_id,
            tenant_id=getattr(proposal, 'tenant_id', 'default'),
            action_type=proposal.proposed_action.get("action_type", "unknown") if proposal.proposed_action else "unknown",
            action_data=proposal.proposed_action or {},
            reason=reason,
            context=f"Rejection of proposal {proposal.id}"
        )

        logger.info(
            f"Rejected proposal {proposal_id} by user {user_id}. Reason: {reason}"
        )

    async def get_pending_proposals(
        self,
        agent_id: Optional[str] = None,
        canvas_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50
    ) -> List[AgentProposal]:
        """Get pending proposals awaiting review"""
        query = self.db.query(AgentProposal).filter(
            AgentProposal.status == ProposalStatus.PENDING_APPROVAL.value
        )

        if agent_id:
            query = query.filter(AgentProposal.agent_id == agent_id)
        
        if canvas_id:
            query = query.filter(AgentProposal.canvas_id == canvas_id)
            
        if tenant_id:
            query = query.filter(AgentProposal.tenant_id == tenant_id)

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
                "execution_result": getattr(proposal, "execution_result", None)
            })

        return history

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _execute_proposed_action_with(
        self, proposal: AgentProposal, action: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute using a prepared action dict (Bug 12 — avoids mutating the
        proposal row before execution). Falls back to proposal.proposed_action.
        Note: ``proposed_action`` is a read-only property on the model — swap
        the underlying ``proposal_data`` column instead."""
        if action is not None:
            _original = proposal.proposal_data
            proposal.proposal_data = action
            try:
                return await self._execute_proposed_action(proposal)
            finally:
                proposal.proposal_data = _original
        return await self._execute_proposed_action(proposal)

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
            elif action_type == "send_email":
                # Canvas co-editor HITL: the approved send executes through
                # the same deterministic email policy as a human-clicked send
                # (sensitivity blocks, audit trail, live broadcast).
                return await self._execute_send_email_action(proposal, proposed_action)
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
                "error": "Action execution failed",
                "action_type": action_type,
                "executed_at": datetime.now().isoformat(),
                "proposal_id": proposal.id
            }

    def _record_execution_episode(
        self, execution, proposal, action_type: str
    ) -> None:
        """R81f (G12): persist an episode for approved-proposal executions so
        INTERN-supervised state changes feed episodic memory and the
        episode-count graduation criteria — create_episode_from_execution
        previously had zero production callers. Never raises."""
        try:
            from core.episode_service import EpisodeService

            success = (execution.status or "") == "completed"

            async def _write() -> None:
                try:
                    await EpisodeService(self.db).create_episode_from_execution(
                        execution_id=execution.id,
                        task_description=f"Approved proposal {proposal.id} ({action_type})",
                        outcome=execution.status or "completed",
                        success=success,
                        metadata={"proposal_id": proposal.id, "source": "proposal"},
                    )
                    logger.info(
                        "Episode recorded for proposal execution %s (%s)",
                        execution.id, action_type,
                    )
                except Exception as e:  # noqa: BLE001 — never break the proposal flow
                    logger.debug("Proposal episode write failed for %s: %s", execution.id, e)

            # R83: create_episode_from_execution is a coroutine — a bare call
            # here was silently garbage-collected, so NONE of the six proposal
            # surfaces ever persisted an episode. Fire-and-forget when a loop
            # is running; otherwise run to completion inline.
            import asyncio as _asyncio

            try:
                _loop = _asyncio.get_running_loop()
            except RuntimeError:
                _loop = None
            if _loop is not None:
                _loop.create_task(_write())
            else:
                _asyncio.run(_write())
        except Exception as e:
            logger.warning(f"Episode creation skipped for {execution.id}: {e}")

    async def _execute_send_email_action(
        self,
        proposal: AgentProposal,
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an approved send_email proposal through the deterministic
        email policy (EmailCanvasService) — same path as a human-clicked
        send, so sensitivity blocks and the CanvasAudit trail apply.

        The send also records an EXECUTION-BACKED episode (like browser and
        canvas-present actions). This is the one path where a STUDENT's
        approved work becomes measured evidence: without it, hires on the
        co-editor flow accumulated only chat-derived and decision episodes —
        their constitutional readiness factor could never activate."""
        execution = AgentExecution(
            id=str(uuid.uuid4()),
            agent_id=proposal.agent_id,
            workspace_id="default",
            status="running",
            input_summary=json.dumps({
                "proposal_id": proposal.id,
                "action": action,
            }),
            triggered_by="proposal",
            tenant_id=getattr(proposal, "tenant_id", None) or "default",
        )
        self.db.add(execution)
        self.db.commit()

        try:
            from core.canvas_email_service import EmailCanvasService

            to_raw = str(action.get("to") or "")
            recipients = [r.strip() for r in to_raw.replace(";", ",").split(",") if r.strip()]
            if not recipients:
                return {
                    "success": False,
                    "error": "No recipient specified in the approved proposal",
                }
            cc_recipients = [
                r.strip()
                for r in str(action.get("cc") or "").replace(";", ",").split(",")
                if r.strip()
            ]

            body = str(action.get("body") or "")
            if not body and action.get("canvas_id"):
                # Fall back to the canvas draft the proposal was raised on.
                from core.models import Canvas
                canvas = self.db.query(Canvas).filter(Canvas.id == action["canvas_id"]).first()
                if canvas is not None and isinstance(canvas.content, dict):
                    body = str(canvas.content.get("content") or "")
                elif canvas is not None and isinstance(canvas.content, str):
                    body = canvas.content

            service = EmailCanvasService(self.db)
            result = await service.send_email(
                canvas_id=action.get("canvas_id") or proposal.canvas_id,
                user_id=proposal.user_id,
                to_emails=recipients,
                cc_emails=cc_recipients,
                subject=str(action.get("subject") or ""),
                body=body,
                agent_id=proposal.agent_id,
                # Threaded reply params survive the HITL round-trip so an
                # approved "reply on the thread" proposal replays as one.
                thread_id=(str(action.get("thread_id") or "").strip() or None),
                reply_all=bool(action.get("reply_all")),
            )
            if not (result or {}).get("success"):
                execution.status = "failed"
                execution.output_summary = json.dumps({
                    "success": False,
                    "error": (result or {}).get("error", "Email policy refused the send"),
                })
                execution.completed_at = datetime.now()
                self.db.commit()
                self._record_execution_episode(execution, proposal, "send_email")
                return {
                    "success": False,
                    "error": (result or {}).get("error", "Email policy refused the send"),
                    "policy_result": result,
                }
            execution.status = "completed"
            execution.output_summary = json.dumps({
                "success": True,
                "status": result.get("status", "sent"),
                "to": recipients,
                "subject": str(action.get("subject") or ""),
            })
            execution.completed_at = datetime.now()
            self.db.commit()
            self._record_execution_episode(execution, proposal, "send_email")
            return {
                "success": True,
                "status": result.get("status", "sent"),
                "message": f"Email {result.get('status', 'sent')} to {', '.join(recipients)}",
            }
        except Exception as e:
            logger.error(f"send_email proposal execution failed: {e}")
            try:
                execution.status = "failed"
                execution.output_summary = json.dumps({"success": False, "error": str(e)})
                execution.completed_at = datetime.now()
                self.db.commit()
                self._record_execution_episode(execution, proposal, "send_email")
            except Exception as episode_err:  # noqa: BLE001 — never mask the real error
                logger.debug(f"send_email failure episode skipped: {episode_err}")
            return {"success": False, "error": str(e)}

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
            from tools.browser_tool import (
                browser_click,
                browser_close_session,
                browser_create_session,
                browser_execute_script,
                browser_fill_form,
                browser_navigate,
            )

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
                triggered_by="proposal",
                tenant_id=proposal.tenant_id or "default",
            )
            self.db.add(execution)
            self.db.commit()

            # Execute browser automation (real API: session + action loop)
            if not action.get("url") and not action.get("session_id"):
                raise ValueError("Browser automation requires a url or session_id")
            session = await browser_create_session(
                user_id=user_id, agent_id=agent_id, db=self.db
            )
            session_id = session.get("session_id") or session.get("id")
            if action.get("url"):
                await browser_navigate(
                    session_id=session_id, url=action["url"], user_id=user_id
                )
            for step in action.get("actions", []):
                step_type = step.get("type", "")
                if step_type == "click":
                    await browser_click(session_id=session_id, user_id=user_id, **{
                        k: v for k, v in step.items() if k != "type"
                    })
                elif step_type == "fill":
                    await browser_fill_form(session_id=session_id, user_id=user_id, **{
                        k: v for k, v in step.items() if k != "type"
                    })
                elif step_type == "script":
                    await browser_execute_script(
                        session_id=session_id, script=step.get("script", ""), user_id=user_id
                    )
            result = {"success": True, "session_id": session_id}

            # Update execution
            execution.status = "completed" if result.get("success") else "failed"
            execution.output_summary = json.dumps(result) if isinstance(result, dict) else str(result)
            execution.completed_at = datetime.now()
            self.db.commit()
            self._record_execution_episode(execution, proposal, "browser_automate")


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
                triggered_by="proposal",
                tenant_id=proposal.tenant_id or "default",
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
            self._record_execution_episode(execution, proposal, "canvas_present")


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
            from integrations.universal_integration_service import (
                UniversalIntegrationService,
            )

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
                triggered_by="proposal",
                tenant_id=proposal.tenant_id or "default",
            )
            self.db.add(execution)
            self.db.commit()

            # Get integration service and execute (real API: unified dispatch)
            service = UniversalIntegrationService()
            result = await service.execute(
                service=integration_type,
                action=action.get("operation", "execute"),
                params=action.get("parameters", {}),
                context={"user_id": user_id, "agent_id": agent_id, "proposal_id": proposal.id},
            )
            if not isinstance(result, dict):
                result = {"ok": True, "data": result}

            # Update execution
            execution.status = "completed" if result.get("success") else "failed"
            execution.output_summary = json.dumps(result) if isinstance(result, dict) else str(result)
            execution.completed_at = datetime.now()
            self.db.commit()
            self._record_execution_episode(execution, proposal, "integration_call")


            return {
                "success": result.get("success", result.get("ok", False)),
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
                "error": "Integration action failed",
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
            from core.workflow_endpoints import load_workflows
            from core.workflow_engine import WorkflowEngine

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
                triggered_by="proposal",
                tenant_id=proposal.tenant_id or "default",
            )
            self.db.add(execution)
            self.db.commit()

            # Trigger workflow (real API: load def by id -> start_workflow)
            wf_def = next(
                (w for w in load_workflows() if str(w.get("id")) == str(workflow_id)),
                None,
            )
            if not wf_def:
                raise ValueError(f"Workflow {workflow_id} not found")
            wf_execution_id = await WorkflowEngine().start_workflow(
                workflow=wf_def,
                input_data=action.get("parameters", {}),
            )
            result = {"success": True, "execution_id": wf_execution_id}

            # Update execution
            execution.status = "completed" if result.get("success") else "failed"
            execution.output_summary = json.dumps(result) if isinstance(result, dict) else str(result)
            execution.completed_at = datetime.now()
            self.db.commit()
            self._record_execution_episode(execution, proposal, "trigger_workflow")


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
                triggered_by="proposal",
                tenant_id=proposal.tenant_id or "default",
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
            self._record_execution_episode(execution, proposal, "device_command")


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
            from core.models import AgentRegistry
            from core.generic_agent import GenericAgent

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
                triggered_by="proposal",
                tenant_id=proposal.tenant_id or "default",
            )
            self.db.add(execution)
            self.db.commit()

            # Execute agent (real API: GenericAgent(agent_model=...).execute)
            registry_agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == (target_agent_id or agent_id)
            ).first()
            if not registry_agent:
                raise ValueError(f"Agent {target_agent_id or agent_id} not found")
            agent = GenericAgent(agent_model=registry_agent, workspace_id="default")
            result = await agent.execute(
                task_input=action.get("prompt", ""),
                context={
                    "proposal_id": proposal.id,
                    "execution_id": execution.id,
                    "parameters": action.get("parameters", {}),
                },
            )
            if not isinstance(result, dict):
                result = {"success": True, "response": str(result)}

            # Update execution
            execution.status = "completed" if result.get("success") else "failed"
            execution.output_summary = json.dumps(result) if isinstance(result, dict) else str(result)
            execution.completed_at = datetime.now()
            self.db.commit()
            self._record_execution_episode(execution, proposal, "delegate_agent")


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

            # approve_proposal passes ``modifications`` as a Dict[str, Any]
            # (field overrides), but downstream code (human_edits, summaries,
            # outcome formatting) expects a list. Normalize once so every
            # consumer sees a list; otherwise dict[:5] / iteration semantics
            # would raise or behave incorrectly.
            raw_modifications = kwargs.get("modifications")
            if isinstance(raw_modifications, dict):
                kwargs["modifications"] = [
                    {k: v} for k, v in raw_modifications.items()
                ]
            elif raw_modifications is None:
                kwargs["modifications"] = []

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
                task_description=f"Proposal {outcome.capitalize()}: {proposal.title}",
                agent_id=proposal.agent_id,
                tenant_id=getattr(proposal, 'tenant_id', None) or 'default',
                workspace_id="default",

                # Link to proposal (supervision schema)
                proposal_id=proposal.id,
                supervision_decision=outcome,
                supervisor_id=proposal.approved_by or proposal.user_id,
                supervision_reasoning=kwargs.get("rejection_reason"),

                # Timing
                started_at=proposal.created_at,
                completed_at=(
                    getattr(proposal, "completed_at", None)
                    or proposal.executed_at
                    or proposal.approved_at
                    or datetime.now()
                ),
                duration_seconds=int((
                    (getattr(proposal, "completed_at", None)
                     or proposal.executed_at
                     or proposal.approved_at
                     or datetime.now()) -
                    proposal.created_at
                ).total_seconds()) if proposal.created_at else None,
                status="completed",

                # Outcome
                outcome="success" if outcome == "approved" else "failure",
                success=outcome == "approved",

                # Content
                topics=self._extract_proposal_topics(proposal),
                entities=self._extract_proposal_entities(proposal),
                importance_score=self._calculate_proposal_importance(outcome, proposal),

                # Graduation fields
                maturity_at_time=maturity_level,
                human_intervention_count=1,  # Human approval/rejection is an intervention
                constitutional_score=None,
                metadata_json={
                    "proposal_outcome": outcome,
                    "proposal_title": proposal.title,
                    "rejection_reason": kwargs.get("rejection_reason"),
                    "human_edits": kwargs.get("modifications", []),
                    "content": proposal_content,
                    "outcome_content": outcome_content,
                }
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
            # approve_proposal passes ``modifications`` as a Dict[str, Any]
            # (field overrides), but older callers may pass a list of change
            # descriptions. Normalize to a list of human-readable change labels
            # so we don't try to slice/iterate a dict (which raises TypeError
            # on ``dict[:5]`` and would silently skip episode creation).
            if isinstance(modifications, dict):
                mod_items = [f"{k}: {v}" for k, v in modifications.items()]
            else:
                mod_items = list(modifications or [])
            if mod_items:
                parts.append(f"\nModifications Applied: {len(mod_items)}")
                for mod in mod_items[:5]:  # Limit to first 5
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
        important_topics = []
        topics = set()

        # Add proposal type (important - always include first)
        important_topics.append(proposal.proposal_type)

        # Extract from title
        if proposal.title:
            words = proposal.title.lower().split()
            topics.update([w for w in words if len(w) > 4][:3])

        # Extract from reasoning
        if proposal.reasoning:
            words = proposal.reasoning.lower().split()
            topics.update([w for w in words if len(w) > 4][:3])

        # Extract from action type (important - always include second)
        if proposal.proposed_action:
            action_type = proposal.proposed_action.get("action_type", "")
            if action_type:
                important_topics.append(action_type)

        # Combine important topics with extracted topics, limit to 5 total
        all_topics = important_topics + list(topics)
        return all_topics[:5]

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
        if getattr(proposal, "modifications", None):
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
            # Reject proposal — never rewrite the audit trail of a proposal
            # that already ran (same guard as reject_proposal).
            if proposal.status != ProposalStatus.PENDING_APPROVAL.value:
                raise ValueError(
                    f"Proposal must be in PENDING_APPROVAL status, current: {proposal.status}"
                )
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
