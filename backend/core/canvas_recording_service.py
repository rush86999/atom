"""
Canvas Recording Service

Records canvas sessions for autonomous agent actions, providing
audit trails, compliance evidence, and user review capabilities.

Features:
- Session recording with full context capture
- Autonomous action tagging
- Recording lifecycle management
- Playback and review support
"""

import logging
import uuid
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.websockets import manager as ws_manager
from core.models import (
    CanvasRecording,
    AgentRegistry,
    CanvasAudit,
    User
)
from core.agent_governance_service import AgentGovernanceService

logger = logging.getLogger(__name__)


# Feature flags
import os
CANVAS_RECORDING_ENABLED = os.getenv("CANVAS_RECORDING_ENABLED", "true").lower() == "true"
RECORDING_RETENTION_DAYS = int(os.getenv("RECORDING_RETENTION_DAYS", "90"))


class CanvasRecordingService:
    """
    Canvas session recording for governance and audit.

    Records canvas interactions for:
    - Audit trail compliance
    - Autonomous action review
    - User transparency
    - Training and improvement
    """

    def __init__(self, db: Session):
        self.db = db
        self.governance = AgentGovernanceService(db)

    async def start_recording(
        self,
        user_id: str,
        agent_id: str,
        canvas_id: Optional[str],
        reason: str,
        session_id: Optional[str] = None,
        tags: Optional[list] = None
    ) -> str:
        """
        Start recording a canvas session.

        Args:
            user_id: User ID
            agent_id: Agent ID performing actions
            canvas_id: Optional canvas ID being recorded
            reason: Why recording is initiated (governance, autonomous_action, etc.)
            session_id: Optional session ID
            tags: Optional tags for categorization

        Returns:
            recording_id: Unique recording ID
        """
        if not CANVAS_RECORDING_ENABLED:
            return str(uuid.uuid4())

        try:
            # Check governance
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if agent and agent.status != "autonomous":
                # Only autonomous agents require automatic recording
                # Others can record manually
                logger.info(f"Non-autonomous agent {agent_id} starting manual recording")

            # Generate recording ID
            recording_id = str(uuid.uuid4())

            # Create recording entry
            recording = CanvasRecording(
                id=str(uuid.uuid4()),
                recording_id=recording_id,
                agent_id=agent_id,
                user_id=user_id,
                canvas_id=canvas_id,
                session_id=session_id,
                reason=reason,
                status="recording",
                tags=tags or [],
                events=[],
                recording_metadata={
                    "agent_name": agent.name if agent else "Unknown",
                    "agent_maturity": agent.status if agent else None,
                    "started_at": datetime.utcnow().isoformat()
                }
            )

            self.db.add(recording)
            self.db.commit()

            # Notify user that recording has started
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "canvas:recording_started",
                    "data": {
                        "recording_id": recording_id,
                        "agent_id": agent_id,
                        "agent_name": agent.name if agent else "Unknown",
                        "reason": reason,
                        "canvas_id": canvas_id
                    }
                }
            )

            # Create audit entry
            await self._create_audit(
                agent_id=agent_id,
                user_id=user_id,
                recording_id=recording_id,
                action="start_recording"
            )

            logger.info(
                f"Started canvas recording {recording_id} for agent {agent_id}, "
                f"user {user_id}, reason: {reason}"
            )

            return recording_id

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return str(uuid.uuid4())

    async def record_event(
        self,
        recording_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ):
        """
        Record an event during canvas session.

        Args:
            recording_id: Recording ID
            event_type: Type of event (operation_start, update, complete, etc.)
            event_data: Event data
        """
        if not CANVAS_RECORDING_ENABLED:
            return

        try:
            # Expire session to ensure we get fresh data
            self.db.expire_all()

            # Get recording
            recording = self.db.query(CanvasRecording).filter(
                CanvasRecording.recording_id == recording_id,
                CanvasRecording.status == "recording"
            ).first()

            if not recording:
                logger.warning(f"Recording {recording_id} not found or not active")
                return

            # Add event
            event = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                "data": event_data
            }

            # Get current events list and append
            events_list = list(recording.events) if recording.events else []
            events_list.append(event)
            recording.events = events_list

            recording.updated_at = datetime.utcnow()
            self.db.commit()
            # Don't refresh here - let the next query get fresh data

            logger.debug(f"Recorded event {event_type} for {recording_id}")

        except Exception as e:
            logger.error(f"Failed to record event: {e}")

    async def stop_recording(
        self,
        recording_id: str,
        status: str = "completed",
        summary: Optional[str] = None
    ):
        """
        Stop recording and finalize.

        Args:
            recording_id: Recording ID
            status: Final status (completed, failed, etc.)
            summary: Optional summary of the session
        """
        if not CANVAS_RECORDING_ENABLED:
            return

        try:
            # Get recording
            recording = self.db.query(CanvasRecording).filter(
                CanvasRecording.recording_id == recording_id
            ).first()

            if not recording:
                logger.warning(f"Recording {recording_id} not found")
                return

            # Calculate duration
            started_at = recording.started_at
            duration_seconds = (datetime.utcnow() - started_at).total_seconds()

            # Update recording
            recording.status = status
            recording.stopped_at = datetime.utcnow()
            recording.duration_seconds = duration_seconds
            recording.summary = summary or self._generate_summary(recording)
            recording.event_count = len(recording.events)

            # Calculate retention date
            recording.expires_at = datetime.utcnow() + timedelta(days=RECORDING_RETENTION_DAYS)

            self.db.commit()

            # Notify user
            await ws_manager.broadcast(
                f"user:{recording.user_id}",
                {
                    "type": "canvas:recording_stopped",
                    "data": {
                        "recording_id": recording_id,
                        "status": status,
                        "duration_seconds": duration_seconds,
                        "event_count": len(recording.events),
                        "summary": recording.summary,
                        "expires_at": recording.expires_at.isoformat()
                    }
                }
            )

            # Create audit
            await self._create_audit(
                agent_id=recording.agent_id,
                user_id=recording.user_id,
                recording_id=recording_id,
                action="stop_recording"
            )

            logger.info(
                f"Stopped recording {recording_id} after {duration_seconds:.1f}s, "
                f"{len(recording.events)} events"
            )

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")

    async def get_recording(
        self,
        recording_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get recording details with events.

        Args:
            recording_id: Recording ID

        Returns:
            Recording details or None
        """
        try:
            recording = self.db.query(CanvasRecording).filter(
                CanvasRecording.recording_id == recording_id
            ).first()

            if not recording:
                return None

            return {
                "recording_id": recording.recording_id,
                "agent_id": recording.agent_id,
                "user_id": recording.user_id,
                "canvas_id": recording.canvas_id,
                "session_id": recording.session_id,
                "reason": recording.reason,
                "status": recording.status,
                "tags": recording.tags,
                "started_at": recording.started_at.isoformat(),
                "stopped_at": recording.stopped_at.isoformat() if recording.stopped_at else None,
                "duration_seconds": recording.duration_seconds,
                "event_count": recording.event_count,
                "summary": recording.summary,
                "events": recording.events,
                "recording_metadata": recording.recording_metadata,
                "expires_at": recording.expires_at.isoformat() if recording.expires_at else None
            }

        except Exception as e:
            logger.error(f"Failed to get recording: {e}")
            return None

    async def list_recordings(
        self,
        user_id: str,
        agent_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list:
        """
        List recordings for user.

        Args:
            user_id: User ID
            agent_id: Optional agent ID filter
            limit: Max results
            offset: Pagination offset

        Returns:
            List of recordings
        """
        try:
            query = self.db.query(CanvasRecording).filter(
                CanvasRecording.user_id == user_id
            )

            if agent_id:
                query = query.filter(CanvasRecording.agent_id == agent_id)

            query = query.order_by(CanvasRecording.started_at.desc())

            recordings = query.limit(limit).offset(offset).all()

            return [
                {
                    "recording_id": r.recording_id,
                    "agent_id": r.agent_id,
                    "canvas_id": r.canvas_id,
                    "reason": r.reason,
                    "status": r.status,
                    "started_at": r.started_at.isoformat(),
                    "duration_seconds": r.duration_seconds,
                    "event_count": r.event_count,
                    "summary": r.summary,
                    "tags": r.tags
                }
                for r in recordings
            ]

        except Exception as e:
            logger.error(f"Failed to list recordings: {e}")
            return []

    async def auto_record_autonomous_action(
        self,
        agent_id: str,
        user_id: str,
        action: str,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Automatically start recording for autonomous agent actions.

        Args:
            agent_id: Agent ID
            user_id: User ID
            action: Action being performed
            context: Action context

        Returns:
            recording_id if started, None otherwise
        """
        if not CANVAS_RECORDING_ENABLED:
            return None

        try:
            # Check if agent is autonomous
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent or agent.status != "autonomous":
                # Only autonomous agents require auto-recording
                return None

            # Check if there's already an active recording for this session
            existing = self.db.query(CanvasRecording).filter(
                CanvasRecording.agent_id == agent_id,
                CanvasRecording.user_id == user_id,
                CanvasRecording.session_id == context.get("session_id"),
                CanvasRecording.status == "recording"
            ).first()

            if existing:
                # Already recording, return existing recording_id
                return existing.recording_id

            # Start new recording with autonomous_action tag
            recording_id = await self.start_recording(
                user_id=user_id,
                agent_id=agent_id,
                canvas_id=context.get("canvas_id"),
                reason="autonomous_action",
                session_id=context.get("session_id"),
                tags=["autonomous", "governance", action]
            )

            logger.info(
                f"Auto-started recording {recording_id} for autonomous action "
                f"by agent {agent_id}"
            )

            return recording_id

        except Exception as e:
            logger.error(f"Failed to auto-start recording: {e}")
            return None

    async def flag_for_review(
        self,
        recording_id: str,
        flag_reason: str,
        flagged_by: str
    ):
        """
        Flag a recording for human review.

        Args:
            recording_id: Recording ID
            flag_reason: Why it's flagged
            flagged_by: User ID who flagged it
        """
        try:
            recording = self.db.query(CanvasRecording).filter(
                CanvasRecording.recording_id == recording_id
            ).first()

            if recording:
                recording.flagged_for_review = True
                recording.flag_reason = flag_reason
                recording.flagged_by = flagged_by
                recording.flagged_at = datetime.utcnow()

                # Update tags list
                tags_list = recording.tags if recording.tags else []
                if "flagged_review" not in tags_list:
                    tags_list.append("flagged_review")
                recording.tags = tags_list

                self.db.commit()
                self.db.refresh(recording)

                logger.info(
                    f"Recording {recording_id} flagged for review by {flagged_by}: "
                    f"{flag_reason}"
                )

        except Exception as e:
            logger.error(f"Failed to flag recording for review: {e}")

    def _generate_summary(self, recording: CanvasRecording) -> str:
        """Generate summary of recording."""
        event_types = [e.get("event_type") for e in recording.events]

        summary_parts = []
        summary_parts.append(f"{len(event_types)} events recorded")

        if "operation_complete" in event_types:
            summary_parts.append("operation completed")
        if "error" in event_types:
            summary_parts.append("errors occurred")

        return ", ".join(summary_parts)

    async def _create_audit(
        self,
        agent_id: str,
        user_id: str,
        recording_id: str,
        action: str
    ):
        """Create audit entry for recording."""
        try:
            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=agent_id,
                agent_execution_id=None,
                user_id=user_id,
                canvas_id=None,
                session_id=None,
                component_type="canvas_recording",
                component_name="canvas_recording_service",
                action=action,
                audit_metadata={"recording_id": recording_id},
                governance_check_passed=True
            )
            self.db.add(audit)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to create audit: {e}")


# Singleton instance helper
def get_canvas_recording_service(db: Session) -> CanvasRecordingService:
    """Get or create canvas recording service instance."""
    return CanvasRecordingService(db)
