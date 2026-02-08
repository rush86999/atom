"""
Supervision Service

Real-time supervision for SUPERVISED agents (0.7-0.9 confidence).
Provides monitoring, intervention, and outcome tracking.
"""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    SupervisionSession,
    SupervisionStatus,
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
        session: SupervisionSession,
        db: Session
    ) -> AsyncGenerator[SupervisionEvent, None]:
        """
        Stream supervision events to human monitor.

        Events include: agent actions, intermediate results, potential issues.

        This is an async generator that yields events as they occur.
        Polls AgentExecution table for real-time updates.
        """
        logger.info(f"Starting monitoring for supervision session {session.id}")

        # Track the execution ID we're monitoring
        execution_id = None
        last_status = "running"
        poll_interval = 0.5  # Poll every 500ms
        max_duration = timedelta(minutes=30)  # Maximum supervision duration
        start_time = datetime.now()

        try:
            while datetime.now() - start_time < max_duration:
                # Check if session is still active
                db.refresh(session)
                if session.status != SupervisionStatus.RUNNING.value:
                    logger.info(f"Supervision session {session.id} is no longer running")
                    break

                # Find the most recent execution for this agent
                execution = db.query(AgentExecution).filter(
                    AgentExecution.agent_id == session.agent_id,
                    AgentExecution.started_at >= session.started_at
                ).order_by(AgentExecution.started_at.desc()).first()

                if execution:
                    # First time seeing this execution
                    if execution_id != execution.id:
                        execution_id = execution.id
                        yield SupervisionEvent(
                            event_type="action",
                            timestamp=datetime.now(),
                            data={
                                "action_type": "execution_started",
                                "description": f"Agent execution started: {execution.id}",
                                "agent_id": session.agent_id,
                                "execution_id": execution.id,
                                "input_summary": execution.input_summary
                            }
                        )

                    # Check for status changes
                    if execution.status != last_status:
                        last_status = execution.status

                        if execution.status == "completed":
                            yield SupervisionEvent(
                                event_type="result",
                                timestamp=datetime.now(),
                                data={
                                    "step": "execution_completed",
                                    "status": "completed",
                                    "execution_id": execution.id,
                                    "output_summary": execution.output_summary,
                                    "duration_seconds": execution.duration_seconds
                                }
                            )
                            break  # Execution completed, stop monitoring

                        elif execution.status == "failed":
                            yield SupervisionEvent(
                                event_type="error",
                                timestamp=datetime.now(),
                                data={
                                    "step": "execution_failed",
                                    "status": "failed",
                                    "execution_id": execution.id,
                                    "error_message": execution.error_message
                                }
                            )
                            break  # Execution failed, stop monitoring

                        elif execution.status == "running":
                            # Still running, send progress update
                            yield SupervisionEvent(
                                event_type="action",
                                timestamp=datetime.now(),
                                data={
                                    "action_type": "execution_progress",
                                    "description": f"Agent execution in progress: {execution.id}",
                                    "execution_id": execution.id,
                                    "duration_so_far": (datetime.now() - execution.started_at).total_seconds()
                                }
                            )

                # Wait before next poll
                await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"Error monitoring agent execution: {e}")
            yield SupervisionEvent(
                event_type="error",
                timestamp=datetime.now(),
                data={
                    "error_type": "monitoring_error",
                    "error_message": str(e),
                    "session_id": session.id
                }
            )

        logger.info(f"Monitoring completed for supervision session {session.id}")

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

    # ========================================================================
    # Autonomous Supervisor Integration
    # ========================================================================

    async def start_supervision_with_fallback(
        self,
        agent_id: str,
        trigger_context: Dict[str, Any],
        workspace_id: str,
        user_id: str
    ) -> SupervisionSession:
        """
        Start supervision with autonomous fallback.

        Tries to use human supervisor first, falls back to autonomous agent
        if human is unavailable.

        Args:
            agent_id: SUPERVISED agent to execute
            trigger_context: Execution context
            workspace_id: Workspace ID
            user_id: User who owns the agent

        Returns:
            SupervisionSession with appropriate supervisor
        """
        from core.user_activity_service import UserActivityService
        from core.autonomous_supervisor_service import AutonomousSupervisorService

        # Check if user is available
        user_activity_service = UserActivityService(self.db)
        user_state = await user_activity_service.get_user_state(user_id)

        supervisor_id = user_id
        supervisor_type = "user"

        # If user unavailable, try to find autonomous supervisor
        if user_state not in ["online", "away"]:
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if agent:
                autonomous_service = AutonomousSupervisorService(self.db)
                autonomous_supervisor = await autonomous_service.find_autonomous_supervisor(
                    intern_agent=agent
                )

                if autonomous_supervisor:
                    supervisor_id = autonomous_supervisor.id
                    supervisor_type = "autonomous_agent"
                    logger.info(
                        f"Using autonomous supervisor {autonomous_supervisor.id} "
                        f"for agent {agent_id} (user unavailable)"
                    )
                else:
                    logger.warning(
                        f"No autonomous supervisor found for {agent_id}, "
                        f"queuing execution"
                    )
                    # Queue the execution for later
                    from core.supervised_queue_service import SupervisedQueueService
                    queue_service = SupervisedQueueService(self.db)
                    await queue_service.enqueue_execution(
                        agent_id=agent_id,
                        user_id=user_id,
                        trigger_type=trigger_context.get("trigger_type", "automated"),
                        execution_context=trigger_context
                    )
                    raise ValueError("User unavailable and no autonomous supervisor - execution queued")

        # Create supervision session
        session = SupervisionSession(
            agent_id=agent_id,
            agent_name=agent.name if agent else "Unknown",
            workspace_id=workspace_id,
            trigger_context=trigger_context,
            status=SupervisionStatus.RUNNING.value,
            supervisor_id=supervisor_id
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(
            f"Started supervision session {session.id} with {supervisor_type} supervisor"
        )

        return session

    async def monitor_with_autonomous_fallback(
        self,
        session: SupervisionSession
    ):
        """
        Monitor execution with autonomous supervisor.

        Args:
            session: Supervision session to monitor
        """
        from core.autonomous_supervisor_service import AutonomousSupervisorService

        # Check supervisor type
        is_autonomous = session.supervisor_id != session.trigger_context.get("user_id")

        if is_autonomous:
            # Use autonomous monitoring
            autonomous_service = AutonomousSupervisorService(self.db)

            # Get supervisor agent
            supervisor = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == session.supervisor_id
            ).first()

            if not supervisor:
                logger.error(f"Autonomous supervisor not found: {session.supervisor_id}")
                return

            # Get execution ID
            execution = self.db.query(AgentExecution).filter(
                AgentExecution.agent_id == session.agent_id,
                AgentExecution.started_at >= session.started_at
            ).order_by(AgentExecution.started_at.desc()).first()

            if not execution:
                logger.warning(f"No execution found for session {session.id}")
                return

            # Monitor with autonomous supervisor
            async for event in autonomous_service.monitor_execution(
                execution_id=execution.id,
                supervisor=supervisor
            ):
                # Log events
                logger.info(
                    f"Autonomous supervision event: {event.event_type} "
                    f"(session: {session.id})"
                )

                # Handle concern detection
                if event.event_type == "concern_detected":
                    # Could implement autonomous intervention here
                    pass
        else:
            # Use existing human monitoring
            pass  # Already handled by existing monitor_agent_execution method

        return round(boost, 3)
