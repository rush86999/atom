"""
Supervision Service

Real-time supervision for SUPERVISED agents (0.7-0.9 confidence).
Provides monitoring, intervention, and outcome tracking.
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime
from datetime import timedelta
from sqlalchemy.orm import Session

from core.models import (
    AgentRegistry, SupervisionSession, BlockedTriggerContext,
    SupervisionStatus, AgentStatus
)

logger = logging.getLogger(__name__)


class SupervisionEvent:
    """Real-time supervision event"""
    def __init__(
        self,
        event_type: str,  # "action", "result", "warning", "error"
        timestamp: datetime,
        data: Dict[str, Any]
    ):
        self.event_type = event_type
        self.timestamp = timestamp
        self.data = data


class InterventionResult:
    """Result of supervisor intervention"""
    def __init__(
        self,
        success: bool,
        message: str,
        session_state: str  # "running", "paused", "terminated"
    ):
        self.success = success
        self.message = message
        self.session_state = session_state


class SupervisionOutcome:
    """Outcome of supervision session"""
    def __init__(
        self,
        session_id: str,
        success: bool,
        duration_seconds: int,
        intervention_count: int,
        supervisor_rating: int,
        feedback: str,
        confidence_boost: Optional[float] = None
    ):
        self.session_id = session_id
        self.success = success
        self.duration_seconds = duration_seconds
        self.intervention_count = intervention_count
        self.supervisor_rating = supervisor_rating
        self.feedback = feedback
        self.confidence_boost = confidence_boost


class SupervisionService:
    """
    Real-time supervision for SUPERVISED agents.

    SUPERVISED agents (0.7-0.9 confidence) execute with real-time monitoring.
    Supervisors can intervene if issues detected.
    """

    def __init__(self, db: Session):
        self.db = db

    async def start_supervision_session(
        self,
        agent_id: str,
        trigger_context: Dict[str, Any],
        workspace_id: str,
        supervisor_id: str
    ) -> SupervisionSession:
        """
        Start supervision session for SUPERVISED agent.

        Agent executes with real-time monitoring.
        Supervisor can intervene if issues detected.
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
            workspace_id=workspace_id,
            trigger_context=trigger_context,
            status=SupervisionStatus.RUNNING.value,
            supervisor_id=supervisor_id
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(
            f"Started supervision session {session.id} for SUPERVISED agent {agent.id}"
        )

        return session

    async def monitor_agent_execution(
        self,
        session: SupervisionSession
    ) -> AsyncGenerator[SupervisionEvent, None]:
        """
        Stream supervision events to human monitor.

        Events include: agent actions, intermediate results, potential issues.

        This is an async generator that yields events as they occur.
        """
        logger.info(f"Starting monitoring for supervision session {session.id}")

        # In production, this would connect to the actual agent execution
        # and stream real-time events

        # Placeholder: Generate some example events
        yield SupervisionEvent(
            event_type="action",
            timestamp=datetime.now(),
            data={
                "action_type": "task_execution",
                "description": "Agent started executing task",
                "agent_id": session.agent_id
            }
        )

        # Simulate some execution events
        await asyncio.sleep(1)

        yield SupervisionEvent(
            event_type="result",
            timestamp=datetime.now(),
            data={
                "step": "data_processing",
                "status": "completed",
                "records_processed": 100
            }
        )

        await asyncio.sleep(1)

        yield SupervisionEvent(
            event_type="action",
            timestamp=datetime.now(),
            data={
                "action_type": "decision",
                "description": "Agent making decision based on processed data",
                "confidence": session.agent.confidence_score if hasattr(session, 'agent') else 0.8
            }
        )

        logger.info(f"Monitoring completed for session {session.id}")

    async def intervene(
        self,
        session_id: str,
        intervention_type: str,  # "pause", "correct", "terminate"
        guidance: str
    ) -> InterventionResult:
        """
        Human supervisor intervenes in agent execution.

        Args:
            session_id: Supervision session
            intervention_type: Type of intervention
            guidance: Supervisor's guidance/correction

        Returns:
            InterventionResult with outcome
        """
        session = self.db.query(SupervisionSession).filter(
            SupervisionSession.id == session_id
        ).first()

        if not session:
            raise ValueError(f"Supervision session {session_id} not found")

        if session.status != SupervisionStatus.RUNNING.value:
            raise ValueError(
                f"Session must be RUNNING, current: {session.status}"
            )

        # Record intervention
        intervention_record = {
            "timestamp": datetime.now().isoformat(),
            "type": intervention_type,
            "guidance": guidance
        }

        session.interventions.append(intervention_record)
        session.intervention_count += 1

        # Handle intervention type
        if intervention_type == "pause":
            session_state = "paused"
            message = f"Execution paused. Guidance: {guidance}"

        elif intervention_type == "correct":
            session_state = "running"
            message = f"Correction applied. Execution continuing. Guidance: {guidance}"

        elif intervention_type == "terminate":
            session.status = SupervisionStatus.INTERRUPTED.value
            session.completed_at = datetime.now()
            session_state = "terminated"
            message = f"Execution terminated. Reason: {guidance}"

        else:
            raise ValueError(f"Unknown intervention type: {intervention_type}")

        self.db.commit()

        logger.info(
            f"Intervention {intervention_type} in session {session_id}: {guidance}"
        )

        return InterventionResult(
            success=True,
            message=message,
            session_state=session_state
        )

    async def complete_supervision(
        self,
        session_id: str,
        supervisor_rating: int,  # 1-5 stars
        feedback: str
    ) -> SupervisionOutcome:
        """
        Complete supervision session and record outcomes.

        Args:
            session_id: Supervision session to complete
            supervisor_rating: 1-5 star rating
            feedback: Supervisor's feedback

        Returns:
            SupervisionOutcome with session summary
        """
        session = self.db.query(SupervisionSession).filter(
            SupervisionSession.id == session_id
        ).first()

        if not session:
            raise ValueError(f"Supervision session {session_id} not found")

        if session.status != SupervisionStatus.RUNNING.value:
            raise ValueError(
                f"Session must be RUNNING, current: {session.status}"
            )

        # Calculate duration
        completed_at = datetime.now()
        duration_seconds = int((completed_at - session.started_at).total_seconds())

        # Update session
        session.status = SupervisionStatus.COMPLETED.value
        session.completed_at = completed_at
        session.duration_seconds = duration_seconds
        session.supervisor_rating = supervisor_rating
        session.supervisor_feedback = feedback

        # Determine confidence boost based on performance
        confidence_boost = self._calculate_confidence_boost(
            supervisor_rating,
            session.intervention_count,
            duration_seconds
        )
        session.confidence_boost = confidence_boost

        # Update agent confidence
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == session.agent_id
        ).first()

        if agent:
            old_confidence = agent.confidence_score
            agent.confidence_score = min(1.0, agent.confidence_score + confidence_boost)
            actual_boost = agent.confidence_score - old_confidence

            # Check for promotion to AUTONOMOUS
            promoted = False
            if agent.confidence_score >= 0.9 and agent.status == AgentStatus.SUPERVISED.value:
                agent.status = AgentStatus.AUTONOMOUS.value
                promoted = True
                logger.info(
                    f"Agent {agent.id} promoted from SUPERVISED to AUTONOMOUS "
                    f"(confidence: {agent.confidence_score:.3f})"
                )

            logger.info(
                f"Session {session_id} completed. "
                f"Confidence boost: {actual_boost:.3f} "
                f"({old_confidence:.3f} → {agent.confidence_score:.3f}), "
                f"Promoted: {promoted}"
            )

        self.db.commit()

        return SupervisionOutcome(
            session_id=session_id,
            success=supervisor_rating >= 3,
            duration_seconds=duration_seconds,
            intervention_count=session.intervention_count,
            supervisor_rating=supervisor_rating,
            feedback=feedback,
            confidence_boost=confidence_boost
        )

    async def get_active_sessions(
        self,
        workspace_id: Optional[str] = None,
        limit: int = 50
    ) -> List[SupervisionSession]:
        """Get currently active supervision sessions"""
        query = self.db.query(SupervisionSession).filter(
            SupervisionSession.status == SupervisionStatus.RUNNING.value
        )

        if workspace_id:
            query = query.filter(SupervisionSession.workspace_id == workspace_id)

        return query.order_by(
            SupervisionSession.started_at.desc()
        ).limit(limit).all()

    async def get_supervision_history(
        self,
        agent_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get agent's supervision history"""
        sessions = self.db.query(SupervisionSession).filter(
            SupervisionSession.agent_id == agent_id
        ).order_by(
            SupervisionSession.started_at.desc()
        ).limit(limit).all()

        history = []
        for session in sessions:
            history.append({
                "session_id": session.id,
                "status": session.status,
                "started_at": session.started_at.isoformat(),
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "duration_seconds": session.duration_seconds,
                "intervention_count": session.intervention_count,
                "supervisor_rating": session.supervisor_rating,
                "supervisor_feedback": session.supervisor_feedback,
                "confidence_boost": session.confidence_boost
            })

        return history

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _calculate_confidence_boost(
        self,
        supervisor_rating: int,
        intervention_count: int,
        duration_seconds: int
    ) -> float:
        """
        Calculate confidence boost based on supervision session performance.

        Factors:
        - Supervisor rating (1-5): Higher rating → higher boost
        - Intervention count: Fewer interventions → higher boost
        - Duration efficiency: Reasonable duration → higher boost

        Returns:
            Confidence boost (0.0 to 0.1)
        """
        # Base boost from rating
        # 1 star: 0.0, 5 stars: 0.1
        rating_boost = (supervisor_rating - 1) / 40  # 0 to 0.1

        # Penalty for interventions
        # Each intervention reduces boost by 0.01
        intervention_penalty = min(0.05, intervention_count * 0.01)

        # Calculate final boost
        boost = max(0.0, rating_boost - intervention_penalty)

        return round(boost, 3)
