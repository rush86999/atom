import logging
import uuid
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from core.database import SessionLocal
from core.models import User, AgentExecution, UserIdentity
from core.agent_world_model import WorldModelService
from core.notification_manager import notification_manager
from core.atom_meta_agent import handle_manual_trigger, SpecialtyAgentTemplate
from core.communication.adapters.base import PlatformAdapter, GenericAdapter
from core.communication.adapters.slack import SlackAdapter
from core.communication.adapters.discord import DiscordAdapter
from core.communication.adapters.whatsapp import WhatsAppAdapter
from core.communication.adapters.email import EmailAdapter
from core.communication.adapters.sms import SMSAdapter
from core.communication.adapters.google_chat import GoogleChatAdapter
from core.communication.adapters.matrix import MatrixAdapter
from core.communication.adapters.facebook import FacebookAdapter
from core.communication.adapters.line import LineAdapter
from core.communication.adapters.signal import SignalAdapter
from core.communication.adapters.telegram import TelegramAdapter
from core.communication.adapters.teams import TeamsAdapter
from core.communication.adapters.intercom import IntercomAdapter
import os

logger = logging.getLogger(__name__)

class CommunicationService:
    """
    Service to handle universal communication from external platforms 
    (Slack, Discord, WhatsApp, etc.) to Atom Agents.
    """

    def __init__(self):
        self._adapters: Dict[str, PlatformAdapter] = {}
        self.register_adapter("slack", SlackAdapter())
        self.register_adapter("discord", DiscordAdapter())
        self.register_adapter("whatsapp", WhatsAppAdapter())
        self.register_adapter("telegram", TelegramAdapter())
        self.register_adapter("teams", TeamsAdapter())
        self.register_adapter("intercom", IntercomAdapter(
            access_token=os.getenv("INTERCOM_ACCESS_TOKEN", ""),
            client_secret=os.getenv("INTERCOM_CLIENT_SECRET", "")
        ))
        self.register_adapter("email", EmailAdapter(
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            source_email=os.getenv("SES_SOURCE_EMAIL")
        ))
        self.register_adapter("sms", SMSAdapter(
            account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            phone_number=os.getenv("TWILIO_PHONE_NUMBER", "")
        ))
        self.register_adapter("google_chat", GoogleChatAdapter())
        self.register_adapter("matrix", MatrixAdapter(
            homeserver_url=os.getenv("MATRIX_HOMESERVER"),
            access_token=os.getenv("MATRIX_ACCESS_TOKEN")
        ))
        self.register_adapter("facebook", FacebookAdapter(
            page_access_token=os.getenv("FACEBOOK_PAGE_TOKEN")
        ))
        self.register_adapter("line", LineAdapter(
            channel_access_token=os.getenv("LINE_CHANNEL_TOKEN")
        ))
        self.register_adapter("signal", SignalAdapter(
            api_url=os.getenv("SIGNAL_API_URL")
        ))
        self.register_adapter("generic", GenericAdapter())
        
    def register_adapter(self, name: str, adapter: PlatformAdapter):
        """Registers a communication adapter."""
        self._adapters[name] = adapter

    def get_adapter(self, source: str) -> PlatformAdapter:
        return self._adapters.get(source, self._adapters["generic"])

    async def handle_incoming_message(
        self, 
        source: str, 
        payload: Dict[str, Any], 
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """
        Process an incoming message (Post-Normalization).
        """
        logger.info(f"Received message from {source}: {payload.get('content')[:50]}...")
        
        sender_id = payload.get("sender_id")
        content = payload.get("content")
        channel_id = payload.get("channel_id")
        
        if not content:
            return {"status": "ignored", "reason": "empty_content"}

        # 1. Resolve User and Workspace
        db = SessionLocal()
        user = None
        workspace_id = "default"
        
        try:
            # Lookup User Identity
            from core.models import UserIdentity
            
            identity = db.query(UserIdentity).filter(
                UserIdentity.provider == source,
                UserIdentity.provider_user_id == sender_id
            ).first()
            
            if identity and identity.user:
                user = identity.user
                logger.info(f"Resolved user {user.email} from {source} ID {sender_id}")
                # Use first workspace for now
                if user.workspaces:
                    workspace_id = user.workspaces[0].id
            else:
                # Security: Reject messages from unknown identities instead of falling back to admin
                logger.error(f"No identity found for {source}:{sender_id}. Rejecting message for security.")
                return {"status": "error", "message": "User identity not found. Please link your account."}
                
        finally:
            db.close()

        if not user:
             logger.warning(f"Could not resolve user for {source} sender {sender_id}")
             return {"status": "error", "message": "User not resolved"}

        # 2. Intercept Slash Commands
        if content.startswith("/"):
            handled = await self._handle_slash_commands(
                command=content,
                user=user,
                workspace_id=workspace_id,
                source=source,
                channel_id=channel_id,
                background_tasks=background_tasks
            )
            if handled:
                return {"status": "command_executed"}

        # 3. Trigger Agent Processing
        # We assume the user wants to talk to Atom (Meta-Agent)
        # We run this in background to avoid valid webhook timeouts
        
        background_tasks.add_task(
            self._process_and_reply,
            user=user,
            workspace_id=workspace_id,
            request=content,
            source=source,
            channel_id=channel_id,
            metadata=payload.get("metadata")
        )
        
        return {"status": "processing", "message": "Message received"}

    async def _handle_slash_commands(
        self, 
        command: str, 
        user: User, 
        workspace_id: str, 
        source: str, 
        channel_id: str,
        background_tasks: BackgroundTasks
    ) -> bool:
        """
        Interprets and executes platform-native slash commands.
        Returns True if the message was handled as a command.
        """
        parts = command.split(" ", 1)
        base_cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if base_cmd == "/agents":
            # 1. Agent Discovery
            agents = SpecialtyAgentTemplate.TEMPLATES
            reply = "**Available Specialty Agents:**\n\n"
            for key, t in agents.items():
                reply += f"- **{t['name']}** (`{key}`): {t['description']}\n"
            reply += "\n*Tip: You can ask Atom to 'delegate task to [agent]' to involve these experts.*"
            
            await self.send_message(source, channel_id, reply, workspace_id)
            return True

        elif base_cmd == "/workflow" and args:
            # 2. Workflow Triggering
            workflow_id = args.split()[0]
            reply = f"🚀 Triggering workflow `{workflow_id}`..."
            await self.send_message(source, channel_id, reply, workspace_id)
            
            # Use AdvancedWorkflowOrchestrator or handle_manual_trigger with specific prompt
            background_tasks.add_task(
                self._process_and_reply,
                user=user,
                workspace_id=workspace_id,
                request=f"Trigger workflow {workflow_id} with default params",
                source=source,
                channel_id=channel_id
            )
            return True

        elif base_cmd == "/run" and args:
            # 3. Explicit Agent Run
            background_tasks.add_task(
                self._process_and_reply,
                user=user,
                workspace_id=workspace_id,
                request=args,
                source=source,
                channel_id=channel_id
            )
            return True
            
        return False

    async def _process_and_reply(
        self, 
        user: User, 
        workspace_id: str, 
        request: str, 
        source: str, 
        channel_id: str,
        metadata: Dict = None
    ):
        """
        Execute core Atom logic and send reply back to source.
        """
        try:
            logger.info(f"Processing request for user {user.email} via {source}")
            
            # --- Voice Processing ---
            actual_request = request
            if metadata and metadata.get("media_id") and metadata.get("media_type") in ["audio", "voice"]:
                logger.info(f"Detected voice input from {source}. Transcribing...")
                try:
                    adapter = self.get_adapter(source)
                    audio_bytes = await adapter.get_media(metadata["media_id"])

                    if audio_bytes:
                        from core.voice_service import get_voice_service
                        voice_svc = get_voice_service(workspace_id)
                        transcription = await voice_svc.transcribe_audio(
                            audio_bytes=audio_bytes,
                            audio_format="ogg" if source == "telegram" else "m4a"
                        )
                        actual_request = transcription.text
                        logger.info(f"Transcribed voice: {actual_request[:50]}...")
                except Exception as voice_err:
                    logger.warning(f"Voice transcription failed: {voice_err}. Using original request text.")
                    actual_request = request  # Fall back to text
            # ------------------------

            # Execute Atom Logic
            response = await handle_manual_trigger(
                request=actual_request,
                user=user,
                workspace_id=workspace_id,
                additional_context={"source": source, "channel_id": channel_id}
            )
            
            # Extract final answer
            reply_text = "I processed your request."
            if isinstance(response, dict):
                 # 1. Try formatted Final Answer
                 reply_text = response.get("final_output")
                 
                 # 2. Fallback to extracting from result summary (if stored)
                 if not reply_text:
                     reply_text = response.get("response") or response.get("output")
                     
                 # 3. If still empty, summarize actions
                 if not reply_text and response.get("actions_executed"):
                     actions = response["actions_executed"]
                     reply_text = f"I executed {len(actions)} actions: " + ", ".join([a.get('thought', '')[:50] for a in actions])
                     
                 if not reply_text:
                     reply_text = str(response)
            else:
                 reply_text = str(response)

            # Send Reply
            await self.send_message(
                target_source=source,
                target_id=channel_id,
                message=reply_text,
                workspace_id=workspace_id
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send_message(
                target_source=source,
                target_id=channel_id,
                message=f"I encountered an error processing your request: {str(e)}",
                workspace_id=workspace_id
            )

    async def send_message(self, target_source: str, target_id: str, message: str, workspace_id: str):
        """
        Dispatch outbound message to external platform.
        """
        logger.info(f"Sending outgoing message to {target_source}/{target_id}: {message[:50]}...")
        
        adapter = self.get_adapter(target_source)
        success = await adapter.send_message(target_id, message)
        
        if not success:
            logger.error(f"Failed to send message via {target_source}")

        # Also push to UI so user sees it in browser if open
        await notification_manager.broadcast({
            "type": "agent_message",
            "source": f"agent ({target_source})",
            "content": message
        }, workspace_id)

# Singleton
communication_service = CommunicationService()
