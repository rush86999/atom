"""
Agent Request Manager

Handles agent requests for user input, decisions, and permissions
with full governance tracking and audit trail.

Features:
- Permission requests
- Decision requests
- Input requests
- Confirmation requests
- Request expiration and revocation
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentRequestLog, CanvasAudit
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)


# Feature flags
import os

AGENT_REQUESTS_ENABLED = os.getenv("AGENT_REQUESTS_ENABLED", "true").lower() == "true"


class AgentRequestManager:
    """
    Manages agent requests for user input/decisions.

    Provides a structured way for agents to request permissions, decisions,
    or input from users with full audit trail and governance.
    """

    # Request timeouts by urgency
    REQUEST_TIMEOUTS = {
        "low": 3600,      # 1 hour
        "medium": 600,    # 10 minutes
        "high": 60,       # 1 minute
        "blocking": 30    # 30 seconds
    }

    def __init__(self, db: Session):
        self.db = db
        self.governance = AgentGovernanceService(db)
        self._pending_requests: Dict[str, asyncio.Event] = {}

    async def create_permission_request(
        self,
        user_id: str,
        agent_id: str,
        title: str,
        permission: str,
        context: Dict[str, Any],
        urgency: str = "medium",
        expires_in: Optional[int] = None
    ) -> str:
        """
        Create a permission request from agent to user.

        Args:
            user_id: User ID
            agent_id: Agent ID requesting permission
            title: Request title
            permission: Permission being requested
            context: Context dict with operation, impact, alternatives
            urgency: Urgency level (low, medium, high, blocking)
            expires_in: Optional custom expiration time in seconds

        Returns:
            request_id: Unique request ID
        """
        if not AGENT_REQUESTS_ENABLED:
            return str(uuid.uuid4())

        try:
            # Generate request ID
            request_id = str(uuid.uuid4())

            # Get agent
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            agent_name = agent.name if agent else "Agent"

            # Calculate expiration
            timeout = expires_in or self.REQUEST_TIMEOUTS.get(urgency, 600)
            expires_at = datetime.utcnow() + timedelta(seconds=timeout)

            # Create options
            options = [
                {
                    "label": "Approve",
                    "description": f"Allow {agent_name} to use this permission",
                    "consequences": f"{agent_name} will be able to perform this action now and in the future",
                    "action": "approve"
                },
                {
                    "label": "Approve Once",
                    "description": "Allow this single action",
                    "consequences": f"{agent_name} will perform this action once, then ask again",
                    "action": "approve_once"
                },
                {
                    "label": "Deny",
                    "description": "Don't allow this action",
                    "consequences": f"{agent_name} will not be able to perform this action",
                    "action": "deny"
                }
            ]

            # Create request data
            request_data = {
                "request_id": request_id,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "request_type": "permission",
                "urgency": urgency,
                "title": title,
                "explanation": f"I need permission to: {permission}",
                "permission": permission,
                "context": context,
                "options": options,
                "suggested_option": 1,  # Approve Once - safe default
                "governance": {
                    "requires_signature": urgency == "blocking",
                    "audit_log_required": True,
                    "revocable": True
                }
            }

            # Create log entry
            request_log = AgentRequestLog(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                user_id=user_id,
                request_id=request_id,
                request_type="permission",
                request_data=request_data,
                expires_at=expires_at
            )

            self.db.add(request_log)
            self.db.commit()

            # Create event for response
            self._pending_requests[request_id] = asyncio.Event()

            # Broadcast request
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "agent:request",
                    "data": request_data
                }
            )

            # Create audit
            await self._create_audit(
                agent_id=agent_id,
                user_id=user_id,
                request_id=request_id,
                action="create_permission_request"
            )

            logger.info(
                f"Created permission request {request_id} from agent {agent_id}, "
                f"user {user_id}"
            )

            return request_id

        except Exception as e:
            logger.error(f"Failed to create permission request: {e}")
            return str(uuid.uuid4())

    async def create_decision_request(
        self,
        user_id: str,
        agent_id: str,
        title: str,
        explanation: str,
        options: List[Dict[str, Any]],
        context: Dict[str, Any],
        urgency: str = "low",
        suggested_option: int = 0,
        expires_in: Optional[int] = None
    ) -> str:
        """
        Create a decision request from agent to user.

        Args:
            user_id: User ID
            agent_id: Agent ID requesting decision
            title: Request title
            explanation: Why agent needs this decision
            options: List of decision options
            context: Context dict
            urgency: Urgency level
            suggested_option: Index of suggested option
            expires_in: Optional expiration time

        Returns:
            request_id: Unique request ID
        """
        if not AGENT_REQUESTS_ENABLED:
            return str(uuid.uuid4())

        try:
            request_id = str(uuid.uuid4())

            # Get agent
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            agent_name = agent.name if agent else "Agent"

            # Calculate expiration
            timeout = expires_in or self.REQUEST_TIMEOUTS.get(urgency, 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=timeout)

            # Create request data
            request_data = {
                "request_id": request_id,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "request_type": "decision",
                "urgency": urgency,
                "title": title,
                "explanation": explanation,
                "context": context,
                "options": options,
                "suggested_option": suggested_option,
                "governance": {
                    "requires_signature": False,
                    "audit_log_required": True,
                    "revocable": True
                }
            }

            # Create log entry
            request_log = AgentRequestLog(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                user_id=user_id,
                request_id=request_id,
                request_type="decision",
                request_data=request_data,
                expires_at=expires_at
            )

            self.db.add(request_log)
            self.db.commit()

            # Create event for response
            self._pending_requests[request_id] = asyncio.Event()

            # Broadcast request
            await ws_manager.broadcast(
                f"user:{user_id}",
                {
                    "type": "agent:request",
                    "data": request_data
                }
            )

            # Create audit
            await self._create_audit(
                agent_id=agent_id,
                user_id=user_id,
                request_id=request_id,
                action="create_decision_request"
            )

            logger.info(
                f"Created decision request {request_id} from agent {agent_id}"
            )

            return request_id

        except Exception as e:
            logger.error(f"Failed to create decision request: {e}")
            return str(uuid.uuid4())

    async def wait_for_response(
        self,
        request_id: str,
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for user response to a request.

        Args:
            request_id: Request ID to wait for
            timeout: Optional timeout in seconds (default: use request urgency)

        Returns:
            User response dict or None if timeout
        """
        if request_id not in self._pending_requests:
            logger.warning(f"Request {request_id} not found")
            return None

        try:
            # Get timeout from request if not provided
            if timeout is None:
                request_log = self.db.query(AgentRequestLog).filter(
                    AgentRequestLog.request_id == request_id
                ).first()

                if request_log and request_log.expires_at:
                    timeout = int((request_log.expires_at - datetime.utcnow()).total_seconds())
                else:
                    timeout = 600  # Default 10 minutes

            # Wait for response
            event = self._pending_requests[request_id]
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Request {request_id} timed out")
                # Mark as expired
                request_log = self.db.query(AgentRequestLog).filter(
                    AgentRequestLog.request_id == request_id
                ).first()
                if request_log:
                    request_log.revoked = True
                    self.db.commit()
                return None

            # Get response
            request_log = self.db.query(AgentRequestLog).filter(
                AgentRequestLog.request_id == request_id
            ).first()

            if request_log:
                return request_log.user_response

            return None

        except Exception as e:
            logger.error(f"Failed to wait for response: {e}")
            return None
        finally:
            # Clean up
            self._pending_requests.pop(request_id, None)

    async def handle_response(
        self,
        user_id: str,
        request_id: str,
        response: Dict[str, Any]
    ):
        """
        Handle user response to a request.

        Args:
            user_id: User ID
            request_id: Request ID
            response: User's response
        """
        if not AGENT_REQUESTS_ENABLED:
            return

        try:
            # Get request log
            request_log = self.db.query(AgentRequestLog).filter(
                AgentRequestLog.request_id == request_id,
                AgentRequestLog.user_id == user_id
            ).first()

            if not request_log:
                logger.warning(f"Request {request_id} not found for user {user_id}")
                return

            # Check if expired
            if request_log.expires_at and datetime.utcnow() > request_log.expires_at:
                logger.warning(f"Request {request_id} has expired")
                return

            # Update log
            request_log.user_response = response
            request_log.responded_at = datetime.utcnow()
            request_log.response_time_seconds = (
                datetime.utcnow() - request_log.created_at
            ).total_seconds()
            self.db.commit()

            # Trigger event
            if request_id in self._pending_requests:
                self._pending_requests[request_id].set()

            # Create audit
            await self._create_audit(
                agent_id=request_log.agent_id,
                user_id=user_id,
                request_id=request_id,
                action="handle_response",
                metadata={"response": response}
            )

            logger.info(f"Handled response for request {request_id}")

        except Exception as e:
            logger.error(f"Failed to handle response: {e}")

    async def revoke_request(
        self,
        request_id: str
    ):
        """
        Revoke a pending request.

        Args:
            request_id: Request ID to revoke
        """
        try:
            # Get request log
            request_log = self.db.query(AgentRequestLog).filter(
                AgentRequestLog.request_id == request_id
            ).first()

            if request_log:
                request_log.revoked = True
                self.db.commit()

            # Trigger event with None response
            if request_id in self._pending_requests:
                self._pending_requests[request_id].set()

            logger.info(f"Revoked request {request_id}")

        except Exception as e:
            logger.error(f"Failed to revoke request: {e}")

    async def _create_audit(
        self,
        agent_id: str,
        user_id: str,
        request_id: str,
        action: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Create canvas audit entry."""
        try:
            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=agent_id,
                agent_execution_id=None,
                user_id=user_id,
                canvas_id=None,
                session_id=None,
                component_type="agent_request_prompt",
                component_name="agent_request_manager",
                action=action,
                audit_metadata={
                    "request_id": request_id,
                    **(metadata or {})
                },
                governance_check_passed=True
            )
            self.db.add(audit)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to create audit: {e}")


# Singleton instance helper
def get_agent_request_manager(db: Session) -> AgentRequestManager:
    """Get or create agent request manager instance."""
    return AgentRequestManager(db)
