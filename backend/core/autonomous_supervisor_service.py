"""
Autonomous Supervisor Service

Provides autonomous agent fallback supervision when users are unavailable.
AUTONOMOUS agents supervise INTERN and SUPERVISED agents via LLM-based analysis.
"""

import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    ProposalStatus,
    SupervisionSession,
    SupervisionStatus,
)

logger = logging.getLogger(__name__)


class ProposalReview:
    """Result of autonomous proposal review"""

    def __init__(
        self,
        approved: bool,
        confidence_score: float,
        risk_level: str,  # "safe", "medium", "high"
        reasoning: str,
        suggested_modifications: Optional[List[str]] = None
    ):
        self.approved = approved
        self.confidence_score = confidence_score
        self.risk_level = risk_level
        self.reasoning = reasoning
        self.suggested_modifications = suggested_modifications or []


class SupervisionEvent:
    """Real-time supervision event from autonomous monitoring"""

    def __init__(
        self,
        event_type: str,
        timestamp: datetime,
        data: Dict[str, Any]
    ):
        self.event_type = event_type
        self.timestamp = timestamp
        self.data = data


class AutonomousSupervisorService:
    """
    Manage autonomous agent fallback supervision.

    When human supervisors are unavailable, AUTONOMOUS agents can supervise:
    - INTERN agents: Review proposals and approve/reject
    - SUPERVISED agents: Monitor execution and intervene if needed

    Matching Strategy:
    - Same category/specialty preferred
    - Higher confidence score preferred
    - Must be AUTONOMOUS maturity (>0.9 confidence)
    """

    def __init__(self, db: Session):
        self.db = db

    async def find_autonomous_supervisor(
        self,
        intern_agent: AgentRegistry,
        category: Optional[str] = None
    ) -> Optional[AgentRegistry]:
        """
        Find autonomous agent with matching category/specialty.

        Args:
            intern_agent: Agent needing supervision
            category: Optional category filter

        Returns:
            Autonomous agent capable of supervision, or None
        """
        # Build query for autonomous agents
        query = self.db.query(AgentRegistry).filter(
            AgentRegistry.status == AgentStatus.AUTONOMOUS.value,
            AgentRegistry.confidence_score >= 0.9
        )

        # Filter by category
        target_category = category or intern_agent.category
        if target_category:
            query = query.filter(AgentRegistry.category == target_category)

        # Order by confidence (highest first) and get first match
        supervisor = query.order_by(
            AgentRegistry.confidence_score.desc()
        ).first()

        if supervisor:
            logger.info(
                f"Found autonomous supervisor for {intern_agent.id}: "
                f"{supervisor.id} ({supervisor.name}, "
                f"confidence: {supervisor.confidence_score:.3f})"
            )
        else:
            logger.warning(
                f"No autonomous supervisor found for {intern_agent.id} "
                f"(category: {target_category})"
            )

        return supervisor

    async def review_proposal(
        self,
        proposal: AgentProposal,
        supervisor: AgentRegistry
    ) -> ProposalReview:
        """
        LLM-based proposal review with confidence scoring.

        Args:
            proposal: Proposal to review
            supervisor: Autonomous agent reviewing the proposal

        Returns:
            ProposalReview with approval decision and reasoning
        """
        # Extract proposal details
        proposed_action = proposal.proposed_action or {}
        action_type = proposed_action.get("action_type", "unknown")
        reasoning = proposal.reasoning or ""

        # Perform LLM-based analysis
        analysis = await self._analyze_proposal_with_llm(
            supervisor=supervisor,
            proposal=proposal,
            action_type=action_type,
            reasoning=reasoning
        )

        # Calculate risk level
        risk_level = self._calculate_risk_level(action_type, analysis)

        # Make approval decision
        approved = self._should_approve_proposal(
            analysis=analysis,
            risk_level=risk_level,
            supervisor_confidence=supervisor.confidence_score
        )

        review = ProposalReview(
            approved=approved,
            confidence_score=analysis.get("confidence", 0.5),
            risk_level=risk_level,
            reasoning=analysis.get("reasoning", "No reasoning provided"),
            suggested_modifications=analysis.get("modifications", [])
        )

        logger.info(
            f"Autonomous proposal review: {proposal.id} → "
            f"{'APPROVED' if approved else 'REJECTED'} "
            f"(risk: {risk_level}, supervisor: {supervisor.id})"
        )

        return review

    async def monitor_execution(
        self,
        execution_id: str,
        supervisor: AgentRegistry
    ) -> AsyncGenerator[SupervisionEvent, None]:
        """
        Monitor supervised agent execution (real-time events).

        Args:
            execution_id: Execution to monitor
            supervisor: Autonomous agent monitoring

        Yields:
            SupervisionEvent objects with real-time updates
        """
        logger.info(
            f"Starting autonomous monitoring: execution={execution_id}, "
            f"supervisor={supervisor.id}"
        )

        # Initial check event
        yield SupervisionEvent(
            event_type="monitoring_started",
            timestamp=datetime.now(),
            data={
                "execution_id": execution_id,
                "supervisor_id": supervisor.id,
                "supervisor_name": supervisor.name
            }
        )

        # Poll execution status
        import asyncio

        max_duration_seconds = 30 * 60  # 30 minutes max
        start_time = datetime.now()
        poll_interval = 2  # Poll every 2 seconds

        try:
            while (datetime.now() - start_time).total_seconds() < max_duration_seconds:
                # Refresh execution from database
                execution = self.db.query(AgentExecution).filter(
                    AgentExecution.id == execution_id
                ).first()

                if not execution:
                    yield SupervisionEvent(
                        event_type="error",
                        timestamp=datetime.now(),
                        data={
                            "error": f"Execution not found: {execution_id}"
                        }
                    )
                    break

                # Check execution status
                if execution.status == "completed":
                    # Analyze execution result
                    await self._analyze_execution_result(execution, supervisor)

                    yield SupervisionEvent(
                        event_type="execution_completed",
                        timestamp=datetime.now(),
                        data={
                            "execution_id": execution.id,
                            "duration_seconds": execution.duration_seconds,
                            "output_summary": execution.output_summary
                        }
                    )
                    break

                elif execution.status == "failed":
                    # Execution failed - analyze error
                    error_analysis = await self._analyze_execution_error(
                        execution, supervisor
                    )

                    yield SupervisionEvent(
                        event_type="execution_failed",
                        timestamp=datetime.now(),
                        data={
                            "execution_id": execution.id,
                            "error_message": execution.error_message,
                            "error_analysis": error_analysis
                        }
                    )
                    break

                elif execution.status == "running":
                    # Check for concerning patterns
                    analysis = await self._check_execution_concerns(
                        execution, supervisor
                    )

                    if analysis.get("has_concerns"):
                        yield SupervisionEvent(
                            event_type="concern_detected",
                            timestamp=datetime.now(),
                            data={
                                "execution_id": execution.id,
                                "concerns": analysis.get("concerns", []),
                                "severity": analysis.get("severity", "low")
                            }
                        )

                # Wait before next poll
                await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"Error in autonomous monitoring: {e}", exc_info=True)
            yield SupervisionEvent(
                event_type="monitoring_error",
                timestamp=datetime.now(),
                data={
                    "error": str(e),
                    "execution_id": execution_id
                }
            )

        logger.info(f"Autonomous monitoring completed: {execution_id}")

    async def approve_proposal(
        self,
        proposal_id: str,
        supervisor_id: str,
        review: ProposalReview
    ) -> bool:
        """
        Approve proposal as autonomous supervisor.

        Args:
            proposal_id: Proposal to approve
            supervisor_id: Autonomous agent approving
            review: Review results

        Returns:
            True if approved successfully
        """
        proposal = self.db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id
        ).first()

        if not proposal:
            logger.error(f"Proposal not found: {proposal_id}")
            return False

        if proposal.status != ProposalStatus.PROPOSED.value:
            logger.warning(
                f"Proposal {proposal_id} not in PROPOSED status: {proposal.status}"
            )
            return False

        # Update proposal
        proposal.status = ProposalStatus.APPROVED.value
        proposal.approved_by = supervisor_id
        proposal.approved_at = datetime.now()

        # Store review results
        proposal.execution_result = {
            "autonomous_approval": True,
            "supervisor_id": supervisor_id,
            "review": {
                "approved": review.approved,
                "confidence_score": review.confidence_score,
                "risk_level": review.risk_level,
                "reasoning": review.reasoning,
                "suggested_modifications": review.suggested_modifications
            }
        }

        # TODO: Execute the proposed action
        # For now, just mark as executed
        proposal.status = ProposalStatus.EXECUTED.value
        proposal.completed_at = datetime.now()

        self.db.commit()

        logger.info(
            f"Autonomous supervisor {supervisor_id} approved proposal {proposal_id}"
        )

        return True

    async def get_available_supervisors(
        self,
        category: Optional[str] = None
    ) -> List[AgentRegistry]:
        """
        Get list of available autonomous supervisors.

        Args:
            category: Optional category filter

        Returns:
            List of autonomous agents available for supervision
        """
        query = self.db.query(AgentRegistry).filter(
            AgentRegistry.status == AgentStatus.AUTONOMOUS.value,
            AgentRegistry.confidence_score >= 0.9
        )

        if category:
            query = query.filter(AgentRegistry.category == category)

        return query.order_by(
            AgentRegistry.confidence_score.desc()
        ).all()

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _analyze_proposal_with_llm(
        self,
        supervisor: AgentRegistry,
        proposal: AgentProposal,
        action_type: str,
        reasoning: str
    ) -> Dict[str, Any]:
        """
        Perform LLM-based analysis of proposal.

        Uses autonomous agent's LLM capabilities to analyze proposal.
        """
        # TODO: Integrate with actual LLM
        # For now, return mock analysis

        # Simple heuristic-based analysis
        confidence = supervisor.confidence_score

        # Risk assessment by action type
        action_risks = {
            "browser_automate": "medium",
            "canvas_present": "safe",
            "integration_connect": "medium",
            "workflow_trigger": "safe",
            "device_command": "high",
            "agent_execute": "medium"
        }

        risk = action_risks.get(action_type, "medium")

        # Adjust confidence based on risk
        if risk == "high":
            confidence = max(0.5, confidence - 0.2)
        elif risk == "safe":
            confidence = min(1.0, confidence + 0.1)

        return {
            "confidence": confidence,
            "risk": risk,
            "reasoning": f"Proposal analysis by {supervisor.name}. "
                        f"Action type: {action_type}, Risk level: {risk}. "
                        f"Original reasoning: {reasoning[:200]}...",
            "modifications": []
        }

    def _calculate_risk_level(
        self,
        action_type: str,
        analysis: Dict[str, Any]
    ) -> str:
        """Calculate risk level for proposal."""
        action_risks = {
            "browser_automate": "medium",
            "canvas_present": "safe",
            "integration_connect": "medium",
            "workflow_trigger": "safe",
            "device_command": "high",
            "agent_execute": "medium",
            "delete": "high",
            "update": "medium",
            "create": "safe"
        }

        return action_risks.get(action_type, "medium")

    def _should_approve_proposal(
        self,
        analysis: Dict[str, Any],
        risk_level: str,
        supervisor_confidence: float
    ) -> bool:
        """
        Decide whether to approve proposal.

        High-risk actions require higher confidence.
        """
        confidence = analysis.get("confidence", 0.5)

        # Risk thresholds
        if risk_level == "high":
            return confidence >= 0.95 and supervisor_confidence >= 0.95
        elif risk_level == "medium":
            return confidence >= 0.85 and supervisor_confidence >= 0.90
        else:  # safe
            return confidence >= 0.75 and supervisor_confidence >= 0.85

    async def _analyze_execution_result(
        self,
        execution: AgentExecution,
        supervisor: AgentRegistry
    ) -> Dict[str, Any]:
        """Analyze execution result for quality/compliance."""
        # TODO: Implement LLM-based result analysis
        return {
            "success": execution.status == "completed",
            "quality_score": 0.8,
            "compliant": True
        }

    async def _analyze_execution_error(
        self,
        execution: AgentExecution,
        supervisor: AgentRegistry
    ) -> Dict[str, Any]:
        """Analyze execution error for root cause."""
        # TODO: Implement LLM-based error analysis
        return {
            "error_type": "execution_error",
            "root_cause": "unknown",
            "suggestions": ["retry", "check_inputs"]
        }

    async def _check_execution_concerns(
        self,
        execution: AgentExecution,
        supervisor: AgentRegistry
    ) -> Dict[str, Any]:
        """Check for concerning patterns during execution."""
        # TODO: Implement concern detection
        return {
            "has_concerns": False,
            "concerns": [],
            "severity": "low"
        }
