import logging
import json
import asyncio
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

# Import ChatOrchestrator (Lazy load to avoid circular imports)
logger = logging.getLogger(__name__)

class UnifiedIncomingMessage(BaseModel):
    """Standardized incoming message from any communication platform"""
    platform: str # slack, whatsapp, discord, etc.
    sender_id: str
    recipient_id: str # Bot ID or Channel ID
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    thread_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

class UniversalWebhookBridge:
    """
    Bridges incoming webhooks from various communication platforms
    to the internal ChatOrchestrator.
    """
    
    def __init__(self):
        self._orchestrator = None

    async def _get_agent_id_by_name(self, name: str) -> Optional[str]:
        """Look up agent ID by name (Registry or Template)"""
        try:
            from core.models import AgentRegistry
            from core.database import SessionLocal
            from core.atom_meta_agent import SpecialtyAgentTemplate
            
            db = SessionLocal()
            # Try exact match first
            agent = db.query(AgentRegistry).filter(AgentRegistry.name.ilike(name)).first()
            if agent:
                db.close()
                return agent.id
            
            # Try fuzzy match in registry
            agent = db.query(AgentRegistry).filter(AgentRegistry.name.ilike(f"%{name}%")).first()
            db.close()
            if agent:
                return agent.id
                
            # Try templates
            templates = SpecialtyAgentTemplate.TEMPLATES
            for key, t in templates.items():
                if name.lower() in t["name"].lower() or name.lower() == key:
                    return key
                    
            return None
        except Exception as e:
            logger.error(f"Agent look up failed: {e}")
            return None

    def _get_orchestrator(self):
        """Lazy load orchestrator to handle circular dependencies"""
        if self._orchestrator is None:
            try:
                from integrations.chat_orchestrator import ChatOrchestrator
                self._orchestrator = ChatOrchestrator(workspace_id="default")
            except Exception as e:
                logger.error(f"Failed to initialize ChatOrchestrator: {e}")
        return self._orchestrator

    async def process_incoming_message(self, platform: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an incoming webhook payload from a specific platform.
        """
        logger.info(f"Universal Bridge: Processing message from {platform}")
        
        try:
            unified_msg = self._standardize_message(platform, data)
            if not unified_msg:
                return {"status": "ignored", "reason": "non-message event or bot message"}

            # Log standardized message
            logger.info(f"Standardized message: {unified_msg.text[:50]} from {unified_msg.sender_id}")

            # Check for commands (e.g., /run hello)
            if unified_msg.text.startswith('/'):
                return await self._handle_command(unified_msg)

            # Pass to ChatOrchestrator
            orchestrator = self._get_orchestrator()
            if not orchestrator:
                return {"status": "error", "message": "Orchestrator not available"}

            # Build context for the orchestrator
            context = {
                "source": platform,
                "platform": platform,
                "sender_id": unified_msg.sender_id,
                "channel_id": unified_msg.recipient_id,
                "thread_id": unified_msg.thread_id,
                "external_message": True,
                "metadata": unified_msg.metadata
            }

            # Process via orchestrator
            # Note: We simulate a user session ID based on platform + sender
            session_id = f"{platform}_{unified_msg.sender_id}"
            
            response = await orchestrator.process_chat_message(
                message=unified_msg.text,
                session_id=session_id,
                user_id="external_agent_user", # Generic ID for external users
                context=context
            )

            # --- [NEW] Automatically send response back to platform ---
            if response and response.get("message"):
                try:
                    from core.agent_integration_gateway import agent_integration_gateway, ActionType
                    
                    # Determine recipient and thread
                    # For Slack, recipient is the user or channel, and we might want to thread
                    recipient_id = unified_msg.sender_id if platform == "whatsapp" else unified_msg.recipient_id
                    
                    send_params = {
                        "recipient_id": recipient_id,
                        "channel": unified_msg.recipient_id,
                        "content": response["message"],
                        "thread_ts": unified_msg.thread_id or unified_msg.metadata.get("ts")
                    }

                    await agent_integration_gateway.execute_action(
                        ActionType.SEND_MESSAGE,
                        platform,
                        send_params
                    )
                except Exception as route_err:
                    logger.error(f"Failed to route response back to {platform}: {route_err}")

            return {
                "status": "success",
                "message_id": unified_msg.metadata.get("ts") or unified_msg.metadata.get("id"),
                "orchestrator_response": response
            }

        except Exception as e:
            logger.error(f"Error in Universal Bridge ({platform}): {e}")
            return {"status": "error", "message": str(e)}

    def _standardize_message(self, platform: str, data: Dict[str, Any]) -> Optional[UnifiedIncomingMessage]:
        """Standardize platform-specific data into UnifiedIncomingMessage"""
        
        if platform == "slack":
            # Data is the 'event' part of the Slack callback
            if data.get("type") != "message" or data.get("subtype") in ["bot_message", "message_deleted"]:
                return None
            
            return UnifiedIncomingMessage(
                platform="slack",
                sender_id=data.get("user", "unknown"),
                recipient_id=data.get("channel", "unknown"),
                text=data.get("text", ""),
                thread_id=data.get("thread_ts"),
                metadata={"ts": data.get("ts")},
                raw_payload=data
            )
            
        elif platform == "whatsapp":
            # Basic WhatsApp standardization (based on _process_incoming_message in whatsapp_business_integration)
            return UnifiedIncomingMessage(
                platform="whatsapp",
                sender_id=data.get("from", "unknown"),
                recipient_id="whatsapp_business_id", # Hardcoded or dynamic
                text=data.get("text", {}).get("body", ""),
                metadata={"id": data.get("id")},
                raw_payload=data
            )
            
        elif platform == "discord":
            # Discord message event mapping
            author = data.get("author", {})
            if author.get("bot"):
                return None
                
            return UnifiedIncomingMessage(
                platform="discord",
                sender_id=author.get("id", "unknown"),
                recipient_id=data.get("channel_id", "unknown"),
                text=data.get("content", ""),
                metadata={
                    "id": data.get("id"),
                    "guild_id": data.get("guild_id"),
                    "author_name": author.get("username")
                },
                raw_payload=data
            )
            
        elif platform == "teams":
            # MS Teams message mapping
            from_account = data.get("from", {})
            if data.get("type") != "message":
                return None
                
            return UnifiedIncomingMessage(
                platform="teams",
                sender_id=from_account.get("id", "unknown"),
                recipient_id=data.get("channel_id", "unknown") or data.get("conversation", {}).get("id", "unknown"),
                text=data.get("text", ""),
                metadata={
                    "id": data.get("id"),
                    "team_id": data.get("channel_data", {}).get("team", {}).get("id"),
                    "tenant_id": data.get("tenant_id")
                },
                raw_payload=data
            )
            
        elif platform == "telegram":
            # Telegram message mapping
            from_user = data.get("from", {})
            if not data.get("text"):
                return None
                
            return UnifiedIncomingMessage(
                platform="telegram",
                sender_id=str(from_user.get("id", "unknown")),
                recipient_id=str(data.get("chat", {}).get("id", "unknown")),
                text=data.get("text", ""),
                metadata={
                    "message_id": data.get("message_id"),
                    "username": from_user.get("username")
                },
                raw_payload=data
            )
            
        elif platform == "google_chat":
            # Google Chat mapping
            sender = data.get("sender", {})
            if data.get("type") != "MESSAGE":
                return None
                
            return UnifiedIncomingMessage(
                platform="google_chat",
                sender_id=sender.get("name", "unknown"),
                recipient_id=data.get("space", {}).get("name", "unknown"),
                text=data.get("text", ""),
                metadata={
                    "name": data.get("name"),
                    "thread": data.get("thread", {}).get("name")
                },
                raw_payload=data
            )
            
        elif platform == "twilio":
            # Twilio SMS mapping
            return UnifiedIncomingMessage(
                platform="twilio",
                sender_id=data.get("From", data.get("from", "unknown")),
                recipient_id=data.get("To", data.get("to", "unknown")),
                text=data.get("Body", data.get("body", "")),
                metadata={"sms_sid": data.get("MessageSid", data.get("sid"))},
                raw_payload=data
            )
            
        elif platform == "matrix":
            # Matrix message mapping
            content = data.get("content", {})
            return UnifiedIncomingMessage(
                platform="matrix",
                sender_id=data.get("sender", "unknown"),
                recipient_id=data.get("room_id", "unknown"),
                text=content.get("body", ""),
                metadata={
                    "event_id": data.get("event_id"),
                    "msgtype": content.get("msgtype")
                },
                raw_payload=data
            )
            
        elif platform == "messenger":
            # Facebook Messenger mapping
            message = data.get("message", {})
            return UnifiedIncomingMessage(
                platform="messenger",
                sender_id=data.get("sender", {}).get("id", "unknown"),
                recipient_id=data.get("recipient", {}).get("id", "unknown"),
                text=message.get("text", ""),
                metadata={"mid": message.get("mid")},
                raw_payload=data
            )
            
        elif platform == "line":
            # Line message mapping
            message = data.get("message", {})
            source = data.get("source", {})
            return UnifiedIncomingMessage(
                platform="line",
                sender_id=source.get("userId", "unknown"),
                recipient_id=source.get("groupId") or source.get("roomId") or "direct",
                text=message.get("text", ""),
                metadata={"message_id": message.get("id"), "replyToken": data.get("replyToken")},
                raw_payload=data
            )
            
        elif platform == "signal":
            # signal-cli-rest-api envelope mapping
            envelope = data.get("envelope", {})
            data_message = envelope.get("dataMessage", {})
            if not data_message:
                sync_message = envelope.get("syncMessage", {})
                data_message = sync_message.get("sentMessage", {})
            
            return UnifiedIncomingMessage(
                platform="signal",
                sender_id=envelope.get("source", "unknown"),
                recipient_id=os.getenv("SIGNAL_SENDER_NUMBER", "unknown_bot"),
                text=data_message.get("message", "") if data_message else "",
                metadata={"timestamp": envelope.get("timestamp")},
                raw_payload=data
            )
            
        elif platform == "agent":
            # Direct messaging between agents
            return UnifiedIncomingMessage(
                platform="agent",
                sender_id=data.get("agent_id", "unknown"),
                recipient_id=data.get("target_id", "unknown"),
                text=data.get("message", ""),
                metadata=data.get("metadata", {}),
                raw_payload=data
            )
            
        elif platform == "openclaw":
            # OpenClaw webhook mapping
            return UnifiedIncomingMessage(
                platform="openclaw",
                sender_id=data.get("sender_id", "openclaw_user"),
                recipient_id=data.get("recipient_id", "atom_bot"),
                text=data.get("content", "") or data.get("text", ""),
                metadata={
                    "id": data.get("message_id") or data.get("id"),
                    "thread_ts": data.get("thread_ts")
                },
                thread_id=data.get("thread_ts"),
                raw_payload=data
            )
            
        return None

    async def _handle_command(self, msg: UnifiedIncomingMessage) -> Dict[str, Any]:
        """Handle special commands from external platforms"""
        parts = msg.text[1:].split(' ', 2)
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        logger.info(f"Universal Bridge: Handling command '{command}' with args {args}")

        if command == "run" and args:
            agent_name = args[0]
            task_input = args[1] if len(args) > 1 else "Run default task"
            
            agent_id = await self._get_agent_id_by_name(agent_name)
            if not agent_id:
                # Fallback for known IDs if name look up fails
                agent_id = agent_name 

            try:
                from api.agent_routes import execute_agent_task
                
                # Run in background
                params = {
                    "task_input": task_input,
                    "workspace_id": "default",
                    "source": f"{msg.platform}_command",
                    "source_platform": msg.platform,
                    "recipient_id": msg.sender_id if msg.platform == "whatsapp" else msg.recipient_id,
                    "channel_id": msg.recipient_id,
                    "thread_ts": msg.thread_id or msg.metadata.get("ts")
                }
                asyncio.create_task(execute_agent_task(agent_id, params))
                
                # Acknowledge back to platform
                from core.agent_integration_gateway import agent_integration_gateway, ActionType
                await agent_integration_gateway.execute_action(
                    ActionType.SEND_MESSAGE,
                    msg.platform,
                    {
                        "recipient_id": msg.sender_id if msg.platform == "whatsapp" else msg.recipient_id,
                        "channel": msg.recipient_id,
                        "content": f"🚀 Triggering agent *{agent_name}* (ID: {agent_id}) with task: {task_input}\nI will notify you here when the results are ready!",
                        "thread_ts": msg.thread_id or msg.metadata.get("ts")
                    }
                )

                return {
                    "status": "command_triggered",
                    "command": "run",
                    "agent": agent_name
                }
            except Exception as e:
                logger.error(f"Failed to trigger agent command: {e}")
                return {"status": "error", "message": str(e)}

        elif command == "workflow" and args:
            workflow_id = args[0]
            try:
                from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
                orchestrator = AdvancedWorkflowOrchestrator()
                
                # Trigger workflow by event
                event_data = {
                    "source_platform": msg.platform,
                    "sender_id": msg.sender_id,
                    "recipient_id": msg.recipient_id,
                    "text": msg.text,
                    "workflow_id": workflow_id
                }
                
                # If we have a specific execution method for ID, use it
                # Otherwise trigger by event
                asyncio.create_task(orchestrator.trigger_event(f"manual_trigger:{workflow_id}", event_data))
                
                from core.agent_integration_gateway import agent_integration_gateway, ActionType
                await agent_integration_gateway.execute_action(
                    ActionType.SEND_MESSAGE,
                    msg.platform,
                    {
                        "recipient_id": msg.sender_id if msg.platform == "whatsapp" else msg.recipient_id,
                        "channel": msg.recipient_id,
                        "content": f"⚙️ Triggering workflow *{workflow_id}*...",
                        "thread_ts": msg.thread_id or msg.metadata.get("ts")
                    }
                )

                return {
                    "status": "command_triggered",
                    "command": "workflow",
                    "workflow_id": workflow_id
                }
            except Exception as e:
                logger.error(f"Failed to trigger workflow: {e}")
                return {"status": "error", "message": str(e)}

        elif command == "agents":
            try:
                from core.models import AgentRegistry
                from core.database import SessionLocal
                from core.atom_meta_agent import SpecialtyAgentTemplate
                
                db = SessionLocal()
                db_agents = db.query(AgentRegistry).all()
                db.close()
                
                agent_list = [f"• *{a.name}* ({a.id}) - {a.description}" for a in db_agents]
                
                # Add templates
                templates = SpecialtyAgentTemplate.TEMPLATES
                template_list = [f"• *{t['name']}* (Template) - {t['description']}" for t in templates.values()]
                
                full_list = agent_list + template_list
                content = "🕵️ *Available Agents*:\n" + "\n".join(full_list) if full_list else "No agents found."
                
                from core.agent_integration_gateway import agent_integration_gateway, ActionType
                await agent_integration_gateway.execute_action(
                    ActionType.SEND_MESSAGE,
                    msg.platform,
                    {
                        "recipient_id": msg.sender_id if msg.platform == "whatsapp" or msg.platform == "agent" else msg.recipient_id,
                        "channel": msg.recipient_id,
                        "content": content,
                        "thread_ts": msg.thread_id or msg.metadata.get("ts")
                    }
                )
                return {"status": "agents_listed"}
            except Exception as e:
                logger.error(f"Failed to list agents: {e}")
                return {"status": "error", "message": str(e)}

        elif command == "help":
            help_content = (
                "🤖 *ATOM Universal Bridge Commands*:\n\n"
                "• `/run <agent> <task>`: Launch an agent task.\n"
                "• `/workflow <id>`: Trigger a predefined workflow.\n"
                "• `/agents`: List all available agents and templates.\n"
                "• `/status`: Check system and session health.\n"
                "• `/help`: Show this message."
            )
            from core.agent_integration_gateway import agent_integration_gateway, ActionType
            await agent_integration_gateway.execute_action(
                ActionType.SEND_MESSAGE,
                msg.platform,
                {
                    "recipient_id": msg.sender_id if msg.platform == "whatsapp" or msg.platform == "agent" else msg.recipient_id,
                    "channel": msg.recipient_id,
                    "content": help_content,
                    "thread_ts": msg.thread_id or msg.metadata.get("ts")
                }
            )
            return {"status": "help_sent"}

        elif command == "status":
            try:
                # In a real system, we'd query the DB for active jobs for this user
                # For MVP, we provide a generic status
                user_id = f"{msg.platform}_{msg.sender_id}"
                
                from core.agent_integration_gateway import agent_integration_gateway, ActionType
                await agent_integration_gateway.execute_action(
                    ActionType.SEND_MESSAGE,
                    msg.platform,
                    {
                        "recipient_id": msg.sender_id if msg.platform == "whatsapp" or msg.platform == "agent" else msg.recipient_id,
                        "channel": msg.recipient_id,
                        "content": f"📊 *System Status*: Online\nConnected via: {msg.platform.capitalize()}\nNo active background agents for session {user_id}.",
                        "thread_ts": msg.thread_id or msg.metadata.get("ts")
                    }
                )
                return {"status": "status_sent"}
            except Exception as e:
                logger.error(f"Failed to get status: {e}")
                return {"status": "error", "message": str(e)}
            
        return {"status": "unsupported_command", "command": command}


# Global instance
universal_webhook_bridge = UniversalWebhookBridge()
