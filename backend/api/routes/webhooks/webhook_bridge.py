import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from core.integration_registry import IntegrationRegistry
from core.circuit_breaker import circuit_breaker
from core.universal_communication_bridge import UniversalCommunicationBridge
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class UnifiedIncomingMessage(BaseModel):
    """Standardized incoming message from any communication platform"""
    platform: str
    sender_id: str
    recipient_id: str
    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    thread_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

class WebhookBridge:
    """
    Standardized bridge for incoming webhooks dispatching events 
    to the IntegrationRegistry and ChatOrchestrator.
    """
    
    def __init__(self):
        self._orchestrator = None

    def _get_orchestrator(self):
        """Lazy logic to handle circular dependencies."""
        if self._orchestrator is None:
            try:
                from integrations.chat_orchestrator import ChatOrchestrator
                self._orchestrator = ChatOrchestrator(workspace_id="default")
            except Exception as e:
                logger.error(f"Failed to initialize ChatOrchestrator: {e}")
        return self._orchestrator

    async def process_event(
        self, 
        platform: str, 
        tenant_id: str, 
        data: Dict[str, Any], 
        registry: IntegrationRegistry,
        db: Session
    ) -> Dict[str, Any]:
        """Process an incoming platform event via the UniversalCommunicationBridge."""
        logger.info(f"Webhook Bridge: Dispatching event from {platform} for tenant {tenant_id}")
        
        # 0. Circuit Breaker Check
        cb_key = f"{platform}:{tenant_id}"
        if not await circuit_breaker.is_enabled(cb_key):
            logger.warning(f"Webhook Bridge: Circuit breaker OPEN for {cb_key}. Ignoring event.")
            return {"status": "ignored", "reason": "circuit_breaker_open"}

        try:
            # 1. Use UniversalCommunicationBridge for standardized normalization
            ucb = UniversalCommunicationBridge(db)
            ucb_result = await ucb.receive_message(
                tenant_id=tenant_id,
                platform=platform,
                payload=data
            )
            
            if not ucb_result:
                return {"status": "ignored", "reason": "ucb_ignored_or_error"}
                
            # Handle standardized interactions (buttons, etc.)
            if ucb_result.get("type") == "interaction":
                return {
                    "status": "success",
                    "processed": True,
                    "type": "interaction",
                    "result": ucb_result.get("result")
                }

            # Handle standard text messages
            if ucb_result.get("type") != "message":
                return {"status": "ignored", "reason": "unsupported_ucb_type"}

            unified_msg = ucb_result["message"]
            text_content = unified_msg.content
            sender_id = unified_msg.sender_id

            # 2. Command Handling (e.g., /run)
            if text_content.startswith('/'):
                # Convert to local model for compatibility with _handle_command
                compat_msg = UnifiedIncomingMessage(
                    platform=platform,
                    sender_id=sender_id,
                    recipient_id=unified_msg.recipient_id or "bot",
                    text=text_content,
                    thread_id=unified_msg.thread_id,
                    metadata=unified_msg.metadata or {}
                )
                return await self._handle_command(compat_msg, tenant_id, registry)

            # 3. Chat Orchestrator Integration
            orchestrator = self._get_orchestrator()
            if not orchestrator:
                return {"status": "error", "message": "ChatOrchestrator unavailable"}

            session_id = f"{platform}_{sender_id}"
            response = await orchestrator.process_chat_message(
                message=text_content,
                session_id=session_id,
                user_id=f"ext_{sender_id}",
                context={
                    "platform": platform,
                    "tenant_id": tenant_id,
                    "sender_id": sender_id,
                    "recipient_id": unified_msg.recipient_id,
                    "thread_id": unified_msg.thread_id
                }
            )

            # 4. Auto-Response Dispatch (Optional based on response)
            if response and response.get("message"):
                # Use UCB for standard response
                ucb = UniversalCommunicationBridge(db)
                await ucb.send_message(
                    tenant_id=tenant_id,
                    platform=platform,
                    target_id=sender_id,
                    content=response["message"],
                    metadata={"thread_ts": unified_msg.thread_id}
                )

            return {
                "status": "success",
                "processed": True,
                "orchestrator_response": response
            }

        except Exception as e:
            logger.error(f"Webhook Bridge Error ({platform}): {e}")
            return {"status": "error", "message": str(e)}

    async def _handle_command(self, msg: UnifiedIncomingMessage, tenant_id: str, registry: IntegrationRegistry) -> Dict[str, Any]:
        """Handle platform commands (e.g., /run) via Registry."""
        parts = msg.text[1:].split(' ', 2)
        command = parts[0].lower()
        
        if command == "run" and len(parts) > 1:
            agent_name = parts[1]
            task_input = parts[2] if len(parts) > 2 else "Run Default"
            
            # Use registry to trigger agent task (simulated execution)
            # In production, we'd use core.agent_routes.execute_agent_task
            return {"status": "command_triggered", "command": "run", "agent": agent_name}
            
        return {"status": "command_ignored", "command": command}

# Global instance
webhook_bridge = WebhookBridge()
