"""
Universal Communication Bridge Service
Enables agents to send and receive messages across multiple communication platforms.
Standardized interface for Slack, Discord, Microsoft Teams, WhatsApp, etc.
"""

import logging
import re
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.models import (
    CommunicationChannel,
    UnifiedMessage,
    MessageRoutingRule,
    AgentRegistry
)
# Upstream specific adapter imports
from core.communication.adapters.slack import SlackAdapter
from core.communication.adapters.discord import DiscordAdapter
from core.communication.adapters.teams import TeamsAdapter
from core.communication.adapters.whatsapp import WhatsAppAdapter
from core.communication.adapters.email import EmailAdapter
from core.communication.adapters.sms import SMSAdapter
from core.communication.adapters.base import PlatformAdapter

from core.messaging_action_dispatcher import get_messaging_action_dispatcher

logger = logging.getLogger(__name__)

class UniversalCommunicationBridge:
    """
    Central service for managing cross-platform communication in Upstream.
    """

    ADAPTERS = {
        "whatsapp": WhatsAppAdapter,
        "discord": DiscordAdapter,
        "slack": SlackAdapter,
        "teams": TeamsAdapter,
        "email": EmailAdapter,
        "sms": SMSAdapter,
    }

    def __init__(self, db: Session):
        self.db = db

    def get_adapter(self, platform: str) -> Optional[PlatformAdapter]:
        """Get platform adapter instance."""
        adapter_class = self.ADAPTERS.get(platform)
        if adapter_class:
            return adapter_class()
        logger.warning(f"No adapter found for platform: {platform}")
        return None

    async def receive_message(
        self,
        tenant_id: str,
        platform: str,
        payload: Dict[str, Any],
        raw_body: bytes = None
    ) -> Optional[Dict[str, Any]]:
        """
        Receive and normalize incoming message from any platform.
        """
        try:
            adapter = self.get_adapter(platform)
            if not adapter:
                return None

            # Handle verification challenge if any
            normalized = adapter.normalize_payload(payload)
            if not normalized:
                return None

            # --- STANDARDIZED INTERACTION HANDLING ---
            # Upstream adapters use 'is_interaction' or 'type == interaction'
            if normalized.get("is_interaction") or normalized.get("type") == "interaction":
                logger.info(f"Processing interactive callback from {platform}")
                dispatcher = get_messaging_action_dispatcher(self.db)
                result = await dispatcher.dispatch_action(
                    platform=platform,
                    tenant_id=tenant_id,
                    user_id=normalized.get("sender_id") or normalized.get("user_id"),
                    action_id=normalized.get("action_id") or normalized.get("value"),
                    payload=normalized
                )
                return {"type": "interaction", "result": result, "normalized": normalized}

            # Standard message handling
            sender_id = normalized.get("sender_id")
            content = normalized.get("content")
            channel_id = normalized.get("channel_id", sender_id)
            metadata = normalized.get("metadata", {})

            # Find or create channel
            channel = self.db.query(CommunicationChannel).filter(
                and_(
                    CommunicationChannel.tenant_id == tenant_id,
                    CommunicationChannel.platform == platform,
                    CommunicationChannel.channel_id == channel_id
                )
            ).first()

            if not channel:
                channel = CommunicationChannel(
                    tenant_id=tenant_id,
                    platform=platform,
                    channel_id=channel_id,
                    channel_name=metadata.get("channel_name", f"{platform.title()} Channel"),
                    is_active=True
                )
                self.db.add(channel)
                self.db.commit()

            # Create unified message
            unified_msg = UnifiedMessage(
                tenant_id=tenant_id,
                channel_id=channel.id,
                platform=platform,
                platform_message_id=metadata.get("message_id"),
                sender_id=sender_id,
                sender_name=metadata.get("sender_name"),
                content=content,
                direction="inbound",
                status="pending",
                metadata=metadata,
                platform_timestamp=metadata.get("timestamp")
            )

            self.db.add(unified_msg)

            # Update metrics
            channel.last_message_at = datetime.now(timezone.utc)
            channel.message_count += 1

            self.db.commit()

            logger.info(f"Received message from {platform}: {content[:50]}...")
            return {"type": "message", "message_id": unified_msg.id, "normalized": normalized}

        except Exception as e:
            logger.error(f"Error receiving message from {platform}: {e}")
            self.db.rollback()
            return None

    async def send_message(
        self,
        tenant_id: str,
        platform: str,
        target_id: str,
        content: str,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send code to platform adapter."""
        try:
            adapter = self.get_adapter(platform)
            if not adapter: return False

            success = await adapter.send_message(target_id, content, **(metadata or {}))
            if success:
                self._record_outbound(tenant_id, platform, target_id, content, agent_id, metadata)
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending message to {platform}: {e}")
            return False

    def _record_outbound(self, tenant_id, platform, target_id, content, agent_id, metadata):
        """Helper to record outbound messages."""
        channel = self.db.query(CommunicationChannel).filter(
            and_(
                CommunicationChannel.tenant_id == tenant_id,
                CommunicationChannel.platform == platform,
                CommunicationChannel.channel_id == target_id
            )
        ).first()

        if channel:
            unified_msg = UnifiedMessage(
                tenant_id=tenant_id,
                channel_id=channel.id,
                platform=platform,
                sender_id="agent",
                content=content,
                direction="outbound",
                status="processed",
                agent_id=agent_id,
                metadata=metadata
            )
            self.db.add(unified_msg)
            self.db.commit()
