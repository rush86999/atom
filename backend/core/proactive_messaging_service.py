"""
Proactive Messaging Service

Enables agents to initiate conversations (not just respond) with governance checks.
Integrates with AgentGovernanceService for maturity-based permissions.

Maturity Levels:
- STUDENT: Blocked from proactive messaging
- INTERN: Requires human approval before sending
- SUPERVISED: Sent with real-time monitoring
- AUTONOMOUS: Full access with audit trail
"""

from datetime import datetime, timezone
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from core.agent_integration_gateway import ActionType, agent_integration_gateway
from core.database import Base
from core.governance_cache import get_governance_cache
from core.models import AgentRegistry, AgentStatus, JSONColumn, ProactiveMessageStatus, User

logger = logging.getLogger(__name__)


class AgentProactiveMessage(Base):
    """Agent-initiated proactive message with governance lifecycle."""

    __tablename__ = "agent_proactive_messages"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), ForeignKey("agent_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(255), nullable=True)
    agent_maturity_level = Column(String(50), nullable=False)
    platform = Column(String(100), nullable=False)
    recipient_id = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    send_now = Column(Boolean, default=False)
    status = Column(String(50), default="pending", nullable=False)
    governance_metadata = Column(JSONColumn, nullable=True)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    platform_message_id = Column(String(255), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProactiveMessagingService:
    """
    Service for creating, approving, and sending proactive messages.

    Proactive messages are initiated by agents (not responses to incoming messages).
    All messages go through governance checks based on agent maturity level.
    """

    def __init__(self, db: Session):
        self.db = db
        self.cache = get_governance_cache()

    def create_proactive_message(
        self,
        agent_id: str,
        platform: str,
        recipient_id: str,
        content: str,
        scheduled_for: Optional[datetime] = None,
        send_now: bool = False,
        governance_metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentProactiveMessage:
        """
        Create a new proactive message from an agent.

        Args:
            agent_id: ID of the agent sending the message
            platform: Target platform (slack, discord, whatsapp, etc.)
            recipient_id: Target recipient (user ID, channel ID, phone number)
            content: Message content
            scheduled_for: Optional scheduled send time
            send_now: If True, send immediately (if approved)
            governance_metadata: Optional governance metadata

        Returns:
            Created ProactiveMessage object

        Raises:
            HTTPException: If agent is STUDENT level (blocked)
        """
        # Get agent
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )

        agent_maturity = agent.status  # STUDENT, INTERN, SUPERVISED, AUTONOMOUS

        # STUDENT agents are blocked from proactive messaging
        if agent_maturity == AgentStatus.STUDENT.value:
            logger.warning(
                f"STUDENT agent {agent.name} attempted to send proactive message. Blocked."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"STUDENT agents are not allowed to send proactive messages. "
                    f"Agent {agent.name} must graduate to INTERN level first."
                )
            )

        # Create the proactive message
        message = AgentProactiveMessage(
            agent_id=agent_id,
            agent_name=agent.name,
            agent_maturity_level=agent_maturity,
            platform=platform,
            recipient_id=recipient_id,
            content=content,
            scheduled_for=scheduled_for,
            send_now=send_now,
            status=ProactiveMessageStatus.PENDING.value,
            governance_metadata=governance_metadata or {},
        )

        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        logger.info(
            f"Created proactive message {message.id} from agent {agent.name} "
            f"(maturity: {agent_maturity}) to {platform}:{recipient_id}"
        )

        # Handle based on maturity level
        if agent_maturity == AgentStatus.INTERN.value:
            # INTERN requires approval - leave as PENDING
            logger.info(f"INTERN agent message {message.id} requires approval")

        elif agent_maturity in [AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]:
            # SUPERVISED and AUTONOMOUS are auto-approved (send when requested)
            message.status = ProactiveMessageStatus.APPROVED.value
            message.approved_at = datetime.now(timezone.utc)
            self.db.commit()

            if send_now and not scheduled_for:
                # Send in background when a loop is running; otherwise send
                # synchronously so the gateway is actually invoked (previously
                # the RuntimeError was swallowed and the message was stranded).
                import asyncio
                try:
                    asyncio.create_task(self._send_message(message.id))
                except RuntimeError:
                    logger.debug(f"No running event loop for message {message.id}; sending synchronously")
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(self._send_message(message.id))
                    except Exception as e:
                        logger.error(f"Failed to send proactive message {message.id} synchronously: {e}")
                    finally:
                        loop.close()

        return message

    def approve_message(
        self,
        message_id: str,
        approver_user_id: str,
    ) -> AgentProactiveMessage:
        """
        Approve a pending proactive message (for INTERN agents).

        Args:
            message_id: ID of the message to approve
            approver_user_id: ID of the user approving

        Returns:
            Updated ProactiveMessage

        Raises:
            HTTPException: If message not found or already processed
        """
        message = self.db.query(AgentProactiveMessage).filter(
            AgentProactiveMessage.id == message_id
        ).first()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proactive message {message_id} not found"
            )

        if message.status != ProactiveMessageStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Message is not in PENDING status (current: {message.status})"
            )

        # Verify approver exists
        approver = self.db.query(User).filter(User.id == approver_user_id).first()
        if not approver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approver user {approver_user_id} not found"
            )

        # Approve the message
        message.status = ProactiveMessageStatus.APPROVED.value
        message.approved_by = approver_user_id
        message.approved_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(message)

        logger.info(
            f"User {approver.email} approved proactive message {message_id} "
            f"from agent {message.agent_name}"
        )

        # Send if scheduled_for is None or in the past.
        # Compare against a timezone-aware "now"; the DB-loaded scheduled_for
        # may be offset-naive (SQLite/SQLAlchemy strip tzinfo on refresh), so
        # normalize both sides to aware UTC to avoid "can't compare offset-naive
        # and offset-aware datetimes" TypeError on scheduled INTERN messages.
        now_utc = datetime.now(timezone.utc)
        scheduled_for = message.scheduled_for
        if scheduled_for is not None and scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)

        if scheduled_for is None or scheduled_for <= now_utc:
            import asyncio
            try:
                # Fire-and-forget when an event loop is already running.
                asyncio.create_task(self._send_message(message.id))
            except RuntimeError:
                # No running event loop (sync / Celery / CLI call path):
                # actually send the message now instead of stranding it in
                # APPROVED with sent_at=None. The previous code logged a
                # "queued for background send" message but no such queue
                # existed, so the gateway was never invoked.
                # Use a freshly created+closed loop rather than asyncio.run(),
                # which is fragile when a prior run left the policy without a
                # current event loop (raises "There is no current event loop").
                logger.debug(f"No running event loop for message {message_id}; sending synchronously")
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self._send_message(message.id))
                except Exception as e:
                    logger.error(f"Failed to send proactive message {message_id} synchronously: {e}")
                finally:
                    loop.close()

        return message

    def reject_message(
        self,
        message_id: str,
        rejecter_user_id: str,
        rejection_reason: str,
    ) -> AgentProactiveMessage:
        """
        Reject a pending proactive message.

        Args:
            message_id: ID of the message to reject
            rejecter_user_id: ID of the user rejecting
            rejection_reason: Reason for rejection

        Returns:
            Updated ProactiveMessage
        """
        message = self.db.query(AgentProactiveMessage).filter(
            AgentProactiveMessage.id == message_id
        ).first()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proactive message {message_id} not found"
            )

        if message.status != ProactiveMessageStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Message is not in PENDING status (current: {message.status})"
            )

        message.status = ProactiveMessageStatus.CANCELLED.value
        message.rejection_reason = rejection_reason

        self.db.commit()
        self.db.refresh(message)

        logger.info(
            f"Proactive message {message_id} rejected by user {rejecter_user_id}. "
            f"Reason: {rejection_reason}"
        )

        return message

    def cancel_message(self, message_id: str) -> AgentProactiveMessage:
        """
        Cancel a scheduled or pending message.

        Args:
            message_id: ID of the message to cancel

        Returns:
            Updated ProactiveMessage
        """
        message = self.db.query(AgentProactiveMessage).filter(
            AgentProactiveMessage.id == message_id
        ).first()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proactive message {message_id} not found"
            )

        if message.status in [
            ProactiveMessageStatus.SENT.value,
            ProactiveMessageStatus.CANCELLED.value
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel message with status: {message.status}"
            )

        message.status = ProactiveMessageStatus.CANCELLED.value
        self.db.commit()
        self.db.refresh(message)

        logger.info(f"Proactive message {message_id} cancelled")

        return message

    def get_pending_messages(
        self,
        agent_id: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentProactiveMessage]:
        """
        Get pending messages awaiting approval or sending.

        Args:
            agent_id: Optional filter by agent
            platform: Optional filter by platform
            limit: Maximum number of messages to return

        Returns:
            List of pending ProactiveMessage objects
        """
        query = self.db.query(AgentProactiveMessage).filter(
            AgentProactiveMessage.status == ProactiveMessageStatus.PENDING.value
        )

        if agent_id:
            query = query.filter(AgentProactiveMessage.agent_id == agent_id)

        if platform:
            query = query.filter(AgentProactiveMessage.platform == platform)

        messages = query.order_by(AgentProactiveMessage.created_at.desc()).limit(limit).all()
        return messages

    def get_message_history(
        self,
        agent_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentProactiveMessage]:
        """
        Get message history with filters.

        Args:
            agent_id: Optional filter by agent
            recipient_id: Optional filter by recipient
            platform: Optional filter by platform
            status: Optional filter by status
            limit: Maximum number of messages

        Returns:
            List of ProactiveMessage objects
        """
        query = self.db.query(AgentProactiveMessage)

        if agent_id:
            query = query.filter(AgentProactiveMessage.agent_id == agent_id)

        if recipient_id:
            query = query.filter(AgentProactiveMessage.recipient_id == recipient_id)

        if platform:
            query = query.filter(AgentProactiveMessage.platform == platform)

        if status:
            query = query.filter(AgentProactiveMessage.status == status)

        messages = query.order_by(AgentProactiveMessage.created_at.desc()).limit(limit).all()
        return messages

    def get_message(self, message_id: str) -> Optional[AgentProactiveMessage]:
        """Get a specific proactive message by ID."""
        return self.db.query(AgentProactiveMessage).filter(
            AgentProactiveMessage.id == message_id
        ).first()

    async def _send_message(self, message_id: str) -> Dict[str, Any]:
        """
        Internal method to send a proactive message.

        Args:
            message_id: ID of the message to send

        Returns:
            Result dictionary
        """
        message = self.db.query(AgentProactiveMessage).filter(
            AgentProactiveMessage.id == message_id
        ).first()

        if not message:
            logger.error(f"Message {message_id} not found for sending")
            return {"status": "error", "message": "Message not found"}

        if message.status != ProactiveMessageStatus.APPROVED.value:
            logger.warning(
                f"Message {message_id} is not APPROVED (current: {message.status})"
            )
            return {"status": "error", "message": "Message not approved"}

        try:
            # Get workspace_id from agent context
            workspace_id = "default"  # Default fallback
            try:
                from core.models import AgentRegistry
                agent = self.db.query(AgentRegistry).filter(
                    AgentRegistry.id == message.agent_id
                ).first()
                if agent and agent.context:
                    workspace_id = agent.context.get("workspace_id", "default")
                    logger.debug(f"Retrieved workspace_id '{workspace_id}' from agent {message.agent_id} context")
            except Exception as e:
                logger.warning(f"Could not retrieve workspace_id from agent context: {e}, using default")

            # Send via AgentIntegrationGateway
            params = {
                "recipient_id": message.recipient_id,
                "content": message.content,
                "workspace_id": workspace_id,
            }

            result = await agent_integration_gateway.execute_action(
                ActionType.SEND_MESSAGE,
                message.platform,
                params
            )

            if result.get("status") == "success":
                # Update message as sent
                message.status = ProactiveMessageStatus.SENT.value
                message.sent_at = datetime.now(timezone.utc)
                message.platform_message_id = result.get("message_id")
                self.db.commit()

                logger.info(
                    f"Proactive message {message_id} sent successfully to "
                    f"{message.platform}:{message.recipient_id}"
                )
                return {"status": "success", "message_id": message_id}

            else:
                # Mark as failed
                message.status = ProactiveMessageStatus.FAILED.value
                message.error_message = result.get("error", "Unknown error")
                self.db.commit()

                logger.error(
                    f"Failed to send proactive message {message_id}: "
                    f"{message.error_message}"
                )
                return {"status": "error", "message": message.error_message}

        except Exception as e:
            # Mark as failed
            message.status = ProactiveMessageStatus.FAILED.value
            message.error_message = str(e)
            self.db.commit()

            logger.error(f"Error sending proactive message {message_id}: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def send_scheduled_messages(self) -> Dict[str, int]:
        """
        Background task to send scheduled messages whose time has come.

        Should be called periodically (e.g., every minute).

        Returns:
            Dictionary with counts: {"sent": X, "failed": Y}
        """
        now = datetime.now(timezone.utc)

        # Find approved messages scheduled for now or past
        messages = self.db.query(AgentProactiveMessage).filter(
            AgentProactiveMessage.status == ProactiveMessageStatus.APPROVED.value,
            AgentProactiveMessage.scheduled_for <= now,
        ).all()

        sent_count = 0
        failed_count = 0

        for message in messages:
            result = await self._send_message(message.id)
            if result.get("status") == "success":
                sent_count += 1
            else:
                failed_count += 1

        logger.info(
            f"Sent {sent_count} scheduled messages, {failed_count} failed"
        )

        return {"sent": sent_count, "failed": failed_count}
