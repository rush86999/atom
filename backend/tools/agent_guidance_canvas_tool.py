"""
Agent Guidance Canvas Tool

Provides real-time agent operation broadcasting to canvas for transparency
and visibility into what agents are doing.

Features:
- Operation start/update/complete broadcasting
- Real-time progress tracking
- Context explanations (what/why/next)
- Operation logging
- Full governance integration
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentExecution, AgentOperationTracker, AgentRegistry, CanvasAudit
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)


# Feature flags
import os

AGENT_GUIDANCE_ENABLED = os.getenv("AGENT_GUIDANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"


class AgentGuidanceSystem:
    """
    Real-time agent operation broadcasting system for canvas visibility.

    Provides transparency into agent operations with live progress tracking,
    contextual explanations, and operation logs.
    """

    def __init__(self, db: Session):
        self.db = db
        self.resolver = AgentContextResolver(db)
        self.governance = AgentGovernanceService(db)

    async def start_operation(
        self,
        user_id: str,
        agent_id: str,
        operation_type: str,
        context: Dict[str, Any],
        total_steps: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a new agent operation and broadcast to canvas.

        Args:
            user_id: User ID to broadcast to
            agent_id: Agent ID performing the operation
            operation_type: Type of operation (integration_connect, browser_automate, etc.)
            context: Context dict with what/why/next explanations
            total_steps: Total number of steps (if known)
            metadata: Optional metadata about the operation

        Returns:
            operation_id: Unique operation ID for tracking
        """
        if not AGENT_GUIDANCE_ENABLED:
            return str(uuid.uuid4())

        try:
            # Generate operation ID
            operation_id = str(uuid.uuid4())

            # Governance check
            agent = None
            governance_check = None
            if AGENT_GUIDANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
                agent = self.db.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id
                ).first()

                if agent:
                    # Check if agent can present operations (INTERN+)
                    governance_check = await self.governance.check_action_permission(
                        agent_id=agent_id,
                        action="present_canvas",
                        action_complexity=2  # MODERATE - presenting information
                    )

                    if not governance_check.get("allowed"):
                        logger.warning(
                            f"Agent {agent_id} not allowed to start operation: "
                            f"{governance_check.get('reason')}"
                        )
                        # Create tracker but don't broadcast - operation will be blocked
                        return {
                            "success": False,
                            "error": f"Operation not allowed: {governance_check.get('reason')}",
                            "governance_check": governance_check
                        }

            # Get workspace_id
            workspace_id = "default"
            if agent and agent.workspace_id:
                workspace_id = agent.workspace_id

            # Create operation tracker
            tracker = AgentOperationTracker(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                user_id=user_id,
                workspace_id=workspace_id,
                operation_type=operation_type,
                operation_id=operation_id,
                current_step="Initializing",
                total_steps=total_steps,
                current_step_index=0,
                status="running",
                progress=0,
                what_explanation=context.get("what", ""),
                why_explanation=context.get("why", ""),
                next_steps=context.get("next", ""),
                operation_metadata=metadata or {},
                logs=[]
            )

            self.db.add(tracker)
            self.db.commit()

            # Create audit entry
            await self._create_audit(
                agent_id=agent_id,
                user_id=user_id,
                operation_id=operation_id,
                action="start_operation",
                governance_check_passed=governance_check.get("allowed") if governance_check else True,
                metadata={
                    "operation_type": operation_type,
                    "context": context
                }
            )

            # Broadcast to canvas
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "canvas:update",
                    "data": {
                        "action": "present",
                        "component": "agent_operation_tracker",
                        "data": {
                            "operation_id": operation_id,
                            "agent_id": agent_id,
                            "agent_name": agent.name if agent else "Agent",
                            "operation_type": operation_type,
                            "status": "running",
                            "current_step": "Initializing",
                            "total_steps": total_steps,
                            "current_step_index": 0,
                            "progress": 0,
                            "context": {
                                "what": context.get("what", ""),
                                "why": context.get("why", ""),
                                "next": context.get("next", "")
                            },
                            "metadata": metadata or {},
                            "logs": [],
                            "started_at": datetime.utcnow().isoformat()
                        }
                    }
                }
            )

            logger.info(
                f"Started operation {operation_id} for agent {agent_id}, "
                f"user {user_id}"
            )

            return operation_id

        except Exception as e:
            logger.error(f"Failed to start operation: {e}")
            return str(uuid.uuid4())

    async def update_step(
        self,
        user_id: str,
        operation_id: str,
        step: str,
        progress: Optional[int] = None,
        add_log: Optional[Dict[str, Any]] = None
    ):
        """
        Update operation step and progress.

        Args:
            user_id: User ID
            operation_id: Operation ID
            step: Current step description
            progress: Progress percentage (0-100)
            add_log: Optional log entry to add
        """
        if not AGENT_GUIDANCE_ENABLED:
            return

        try:
            # Get tracker
            tracker = self.db.query(AgentOperationTracker).filter(
                AgentOperationTracker.operation_id == operation_id
            ).first()

            if not tracker:
                logger.warning(f"Operation {operation_id} not found")
                return

            # Update tracker
            tracker.current_step = step
            tracker.current_step_index += 1

            if progress is not None:
                tracker.progress = min(100, max(0, progress))

            # Add log if provided
            if add_log:
                log_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": add_log.get("level", "info"),
                    "message": add_log.get("message", "")
                }
                tracker.logs.append(log_entry)

            self.db.commit()

            # Calculate progress if not provided
            if progress is None and tracker.total_steps:
                progress = int((tracker.current_step_index / tracker.total_steps) * 100)
                tracker.progress = progress
                self.db.commit()

            # Broadcast update
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "canvas:update",
                    "data": {
                        "action": "update",
                        "component": "agent_operation_tracker",
                        "operation_id": operation_id,
                        "updates": {
                            "current_step": step,
                            "current_step_index": tracker.current_step_index,
                            "progress": tracker.progress,
                            "logs": tracker.logs if add_log else None
                        }
                    }
                }
            )

            logger.debug(f"Updated operation {operation_id}: {step} ({tracker.progress}%)")

        except Exception as e:
            logger.error(f"Failed to update operation step: {e}")

    async def update_context(
        self,
        user_id: str,
        operation_id: str,
        what: Optional[str] = None,
        why: Optional[str] = None,
        next_steps: Optional[str] = None
    ):
        """
        Update operation context explanations.

        Args:
            user_id: User ID
            operation_id: Operation ID
            what: What agent is doing
            why: Why agent is doing this
            next_steps: What happens next
        """
        if not AGENT_GUIDANCE_ENABLED:
            return

        try:
            # Get tracker
            tracker = self.db.query(AgentOperationTracker).filter(
                AgentOperationTracker.operation_id == operation_id
            ).first()

            if not tracker:
                logger.warning(f"Operation {operation_id} not found")
                return

            # Update context
            if what:
                tracker.what_explanation = what
            if why:
                tracker.why_explanation = why
            if next_steps:
                tracker.next_steps = next_steps

            self.db.commit()

            # Broadcast update
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "canvas:update",
                    "data": {
                        "action": "update",
                        "component": "agent_operation_tracker",
                        "operation_id": operation_id,
                        "updates": {
                            "context": {
                                "what": tracker.what_explanation,
                                "why": tracker.why_explanation,
                                "next": tracker.next_steps
                            }
                        }
                    }
                }
            )

            logger.debug(f"Updated context for operation {operation_id}")

        except Exception as e:
            logger.error(f"Failed to update operation context: {e}")

    async def complete_operation(
        self,
        user_id: str,
        operation_id: str,
        status: str = "completed",
        final_message: Optional[str] = None
    ):
        """
        Mark operation as completed or failed.

        Args:
            user_id: User ID
            operation_id: Operation ID
            status: Final status (completed or failed)
            final_message: Optional final message
        """
        if not AGENT_GUIDANCE_ENABLED:
            return

        try:
            # Get tracker
            tracker = self.db.query(AgentOperationTracker).filter(
                AgentOperationTracker.operation_id == operation_id
            ).first()

            if not tracker:
                logger.warning(f"Operation {operation_id} not found")
                return

            # Update tracker
            tracker.status = status
            tracker.completed_at = datetime.utcnow()
            tracker.progress = 100 if status == "completed" else tracker.progress

            if final_message:
                tracker.current_step = final_message

            self.db.commit()

            # Broadcast update
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "canvas:update",
                    "data": {
                        "action": "update",
                        "component": "agent_operation_tracker",
                        "operation_id": operation_id,
                        "updates": {
                            "status": status,
                            "progress": tracker.progress,
                            "current_step": final_message or tracker.current_step,
                            "completed_at": tracker.completed_at.isoformat()
                        }
                    }
                }
            )

            logger.info(f"Completed operation {operation_id} with status {status}")

        except Exception as e:
            logger.error(f"Failed to complete operation: {e}")

    async def add_log_entry(
        self,
        user_id: str,
        operation_id: str,
        level: str,
        message: str
    ):
        """
        Add a log entry to the operation.

        Args:
            user_id: User ID
            operation_id: Operation ID
            level: Log level (info, warning, error)
            message: Log message
        """
        if not AGENT_GUIDANCE_ENABLED:
            return

        await self.update_step(
            user_id=user_id,
            operation_id=operation_id,
            step=None,  # Don't update step
            add_log={
                "level": level,
                "message": message
            }
        )

    async def _create_audit(
        self,
        agent_id: str,
        user_id: str,
        operation_id: str,
        action: str,
        governance_check_passed: bool,
        metadata: Dict[str, Any]
    ):
        """
        Create canvas audit entry for governance tracking.
        """
        try:
            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=agent_id,
                agent_execution_id=None,
                user_id=user_id,
                canvas_id=None,
                session_id=None,
                component_type="agent_operation_tracker",
                component_name="agent_guidance",
                action=action,
                audit_metadata={
                    "operation_id": operation_id,
                    **metadata
                },
                governance_check_passed=governance_check_passed
            )
            self.db.add(audit)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to create audit: {e}")


# Singleton instance helper
def get_agent_guidance_system(db: Session) -> AgentGuidanceSystem:
    """Get or create agent guidance system instance."""
    return AgentGuidanceSystem(db)
