"""
Training WebSocket Events

WebSocket events for training, proposals, and supervision notifications.
Integrates with existing WebSocket infrastructure.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from core.models import (
    AgentProposal, TrainingSession, SupervisionSession,
    ProposalStatus, SupervisionStatus
)

logger = logging.getLogger(__name__)


class TrainingWebSocketEvents:
    """
    WebSocket event notifications for training/proposal/supervision system.

    In production, this would integrate with the existing WebSocket manager
    to send real-time notifications to frontend clients.
    """

    def __init__(self, db: Session):
        self.db = db
        # In production, would inject WebSocket manager here
        # self.websocket_manager = get_websocket_manager()

    # ========================================================================
    # Training Events (STUDENT agents)
    # ========================================================================

    async def notify_training_proposed(
        self,
        agent_id: str,
        proposal: AgentProposal
    ) -> None:
        """Notify when training proposal created for STUDENT agent"""
        event = {
            "event_type": "training_proposed",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "agent_id": agent_id,
                "agent_name": proposal.agent_name,
                "proposal_id": proposal.id,
                "title": proposal.title,
                "description": proposal.description,
                "estimated_duration_hours": proposal.estimated_duration_hours,
                "capability_gaps": proposal.capability_gaps,
                "learning_objectives": proposal.learning_objectives
            }
        }

        logger.info(
            f"Training proposal notification: {proposal.id} for agent {agent_id}"
        )

        # In production: await self.websocket_manager.broadcast(event)
        # For now, just log
        await self._log_event("training_proposed", event)

    async def notify_training_approved(
        self,
        proposal_id: str,
        session_id: str,
        approved_by: str
    ) -> None:
        """Notify when training proposal approved"""
        proposal = self.db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id
        ).first()

        event = {
            "event_type": "training_approved",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "proposal_id": proposal_id,
                "session_id": session_id,
                "approved_by": approved_by,
                "agent_id": proposal.agent_id if proposal else None,
                "training_start_date": proposal.training_start_date.isoformat() if proposal and proposal.training_start_date else None,
                "training_end_date": proposal.training_end_date.isoformat() if proposal and proposal.training_end_date else None
            }
        }

        logger.info(
            f"Training approved: {proposal_id} by {approved_by}, session: {session_id}"
        )

        await self._log_event("training_approved", event)

    async def notify_training_completed(
        self,
        session_id: str,
        maturity_update: Dict[str, Any]
    ) -> None:
        """Notify when training session completed"""
        session = self.db.query(TrainingSession).filter(
            TrainingSession.id == session_id
        ).first()

        event = {
            "event_type": "training_completed",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "session_id": session_id,
                "agent_id": session.agent_id if session else None,
                "performance_score": session.performance_score if session else None,
                "confidence_boost": session.confidence_boost if session else None,
                "promoted_to_intern": session.promoted_to_intern if session else False,
                "maturity_update": maturity_update
            }
        }

        logger.info(
            f"Training completed: {session_id}, "
            f"promoted: {maturity_update.get('promoted_to_intern', False)}"
        )

        await self._log_event("training_completed", event)

    # ========================================================================
    # Proposal Events (INTERN agents)
    # ========================================================================

    async def notify_proposal_created(
        self,
        agent_id: str,
        proposal: AgentProposal
    ) -> None:
        """Notify when INTERN agent creates action proposal"""
        event = {
            "event_type": "proposal_created",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "agent_id": agent_id,
                "agent_name": proposal.agent_name,
                "proposal_id": proposal.id,
                "title": proposal.title,
                "description": proposal.description,
                "proposed_action": proposal.proposed_action,
                "reasoning": proposal.reasoning
            }
        }

        logger.info(
            f"Action proposal created: {proposal.id} by agent {agent_id}"
        )

        await self._log_event("proposal_created", event)

    async def notify_proposal_reviewed(
        self,
        proposal_id: str,
        review: Dict[str, Any]
    ) -> None:
        """Notify when Meta Agent reviews INTERN proposal"""
        event = {
            "event_type": "proposal_reviewed",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "proposal_id": proposal_id,
                "recommendation": review.get("recommendation"),
                "confidence": review.get("confidence"),
                "reasoning": review.get("reasoning"),
                "suggested_modifications": review.get("suggested_modifications")
            }
        }

        logger.info(
            f"Proposal reviewed: {proposal_id}, "
            f"recommendation: {review.get('recommendation')}"
        )

        await self._log_event("proposal_reviewed", event)

    async def notify_proposal_approved(
        self,
        proposal_id: str,
        execution_result: Dict[str, Any]
    ) -> None:
        """Notify when proposal approved and executed"""
        proposal = self.db.query(AgentProposal).filter(
            AgentProposal.id == proposal_id
        ).first()

        event = {
            "event_type": "proposal_approved",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "proposal_id": proposal_id,
                "agent_id": proposal.agent_id if proposal else None,
                "approved_by": proposal.approved_by if proposal else None,
                "execution_result": execution_result
            }
        }

        logger.info(f"Proposal approved and executed: {proposal_id}")

        await self._log_event("proposal_approved", event)

    async def notify_proposal_rejected(
        self,
        proposal_id: str,
        rejected_by: str,
        reason: str
    ) -> None:
        """Notify when proposal rejected"""
        event = {
            "event_type": "proposal_rejected",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "proposal_id": proposal_id,
                "rejected_by": rejected_by,
                "reason": reason
            }
        }

        logger.info(f"Proposal rejected: {proposal_id} by {rejected_by}")

        await self._log_event("proposal_rejected", event)

    # ========================================================================
    # Supervision Events (SUPERVISED agents)
    # ========================================================================

    async def notify_supervision_started(
        self,
        session_id: str,
        agent_id: str
    ) -> None:
        """Notify when supervision session starts"""
        session = self.db.query(SupervisionSession).filter(
            SupervisionSession.id == session_id
        ).first()

        event = {
            "event_type": "supervision_started",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "session_id": session_id,
                "agent_id": agent_id,
                "agent_name": session.agent_name if session else None,
                "workspace_id": session.workspace_id if session else None,
                "supervisor_id": session.supervisor_id if session else None
            }
        }

        logger.info(f"Supervision started: {session_id} for agent {agent_id}")

        await self._log_event("supervision_started", event)

    async def notify_supervision_event(
        self,
        session_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> None:
        """Stream real-time supervision event"""
        event = {
            "event_type": "supervision_event",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "session_id": session_id,
                "supervision_event_type": event_type,
                "event_data": event_data
            }
        }

        # Log verbose events at debug level
        if event_type in ["action", "result"]:
            log_level = logger.debug
        else:
            log_level = logger.info

        await log_level(f"Supervision event: {session_id} - {event_type}")
        await self._log_event("supervision_event", event, debug=True)

    async def notify_supervision_intervention(
        self,
        session_id: str,
        intervention_type: str,
        guidance: str
    ) -> None:
        """Notify when supervisor intervenes"""
        event = {
            "event_type": "supervision_intervention",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "session_id": session_id,
                "intervention_type": intervention_type,
                "guidance": guidance
            }
        }

        logger.info(
            f"Supervision intervention: {session_id} - {intervention_type}"
        )

        await self._log_event("supervision_intervention", event)

    async def notify_supervision_completed(
        self,
        session_id: str,
        outcome: Dict[str, Any]
    ) -> None:
        """Notify when supervision session completes"""
        event = {
            "event_type": "supervision_completed",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "session_id": session_id,
                "success": outcome.get("success"),
                "duration_seconds": outcome.get("duration_seconds"),
                "intervention_count": outcome.get("intervention_count"),
                "supervisor_rating": outcome.get("supervisor_rating"),
                "feedback": outcome.get("feedback"),
                "confidence_boost": outcome.get("confidence_boost")
            }
        }

        logger.info(
            f"Supervision completed: {session_id}, "
            f"rating: {outcome.get('supervisor_rating')}/5"
        )

        await self._log_event("supervision_completed", event)

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _log_event(
        self,
        event_name: str,
        event_data: Dict[str, Any],
        debug: bool = False
    ) -> None:
        """
        Log WebSocket event (placeholder for actual WebSocket broadcast).

        In production, this would integrate with the WebSocket manager:
        await self.websocket_manager.broadcast(event_data)

        For now, just log the event structure.
        """
        if debug:
            logger.debug(f"WebSocket Event [{event_name}]: {event_data}")
        else:
            logger.info(f"WebSocket Event [{event_name}]: {event_data}")

        # Placeholder for WebSocket integration
        # TODO: Integrate with existing WebSocket infrastructure
        # Example:
        # from core.websocket_manager import websocket_manager
        # await websocket_manager.broadcast_to_workspace(
        #     workspace_id=event_data["data"]["workspace_id"],
        #     message=event_data
        # )
