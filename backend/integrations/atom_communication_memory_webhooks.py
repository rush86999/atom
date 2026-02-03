"""
ATOM Communication Memory - Webhook Endpoints
Real-time ingestion webhooks for all communication apps
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.jwt_verifier import verify_token as verify_jwt_token
from integrations.atom_communication_ingestion_pipeline import (
    CommunicationAppType,
    ingestion_pipeline,
)
from integrations.atom_communication_memory_production_api import atom_memory_production_api

logger = logging.getLogger(__name__)
security = HTTPBearer()


def verify_token(payload: Dict[str, Any] = Depends(verify_jwt_token)):
    """
    Verify JWT token using centralized verifier.

    Args:
        payload: Decoded JWT payload from centralized verifier

    Returns:
        Decoded JWT payload
    """
    # The actual verification is done by the verify_jwt_token dependency
    # from core.jwt_verifier which provides comprehensive validation
    return payload


class AtomCommunicationMemoryWebhooks:
    """Webhook endpoints for real-time communication ingestion"""

    def __init__(self):
        self.router = APIRouter(
            prefix="/api/webhooks/communication", tags=["Communication Webhooks"]
        )
        self.setup_routes()
        self.webhook_secrets = {
            "whatsapp": "atom_whatsapp_webhook_secret_2024",
            "slack": "atom_slack_webhook_secret_2024",
            "discord": "atom_discord_webhook_secret_2024",
            "telegram": "atom_telegram_webhook_secret_2024",
            "gmail": "atom_gmail_webhook_secret_2024",
            "outlook": "atom_outlook_webhook_secret_2024",
        }

    def verify_webhook_signature(
        self, app_name: str, request: Request, signature: str, body: bytes
    ) -> bool:
        """Verify webhook signature"""
        try:
            secret = self.webhook_secrets.get(app_name)
            if not secret:
                return False

            expected_signature = hmac.new(
                secret.encode(), body, hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False

    def setup_routes(self):
        """Setup webhook endpoints for all communication apps"""

        @self.router.post("/whatsapp")
        async def whatsapp_webhook(
            request: Request,
            background_tasks: BackgroundTasks,
            x_hub_signature_256: Optional[str] = None,
            token: str = Depends(verify_token),
        ):
            """WhatsApp webhook for real-time message ingestion"""
            try:
                # Get request body
                body = await request.body()

                # Verify signature
                if x_hub_signature_256:
                    if not self.verify_webhook_signature(
                        "whatsapp", request, x_hub_signature_256, body
                    ):
                        raise HTTPException(
                            status_code=401, detail="Invalid webhook signature"
                        )

                # Parse webhook data
                webhook_data = json.loads(body.decode())

                # Add background task for ingestion
                background_tasks.add_task(self._process_whatsapp_webhook, webhook_data)

                return {
                    "status": "received",
                    "message": "WhatsApp webhook processed successfully",
                    "timestamp": datetime.now().isoformat(),
                }

            except Exception as e:
                logger.error(f"Error processing WhatsApp webhook: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/slack")
        async def slack_webhook(
            request: Request,
            background_tasks: BackgroundTasks,
            x_slack_signature: Optional[str] = None,
            x_slack_request_timestamp: Optional[str] = None,
            token: str = Depends(verify_token),
        ):
            """Slack webhook for real-time message ingestion"""
            try:
                # Get request body
                body = await request.body()

                # Verify signature
                if x_slack_signature and x_slack_request_timestamp:
                    if not self.verify_webhook_signature(
                        "slack", request, x_slack_signature, body
                    ):
                        raise HTTPException(
                            status_code=401, detail="Invalid webhook signature"
                        )

                # Parse webhook data
                webhook_data = json.loads(body.decode())

                # Add background task for ingestion
                background_tasks.add_task(self._process_slack_webhook, webhook_data)

                return {
                    "status": "received",
                    "message": "Slack webhook processed successfully",
                    "timestamp": datetime.now().isoformat(),
                }

            except Exception as e:
                logger.error(f"Error processing Slack webhook: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/discord")
        async def discord_webhook(
            request: Request,
            background_tasks: BackgroundTasks,
            x_signature_ed25519: Optional[str] = None,
            x_signature_timestamp: Optional[str] = None,
            token: str = Depends(verify_token),
        ):
            """Discord webhook for real-time message ingestion"""
            try:
                # Get request body
                body = await request.body()

                # Verify signature
                if x_signature_ed25519 and x_signature_timestamp:
                    if not self.verify_webhook_signature(
                        "discord", request, x_signature_ed25519, body
                    ):
                        raise HTTPException(
                            status_code=401, detail="Invalid webhook signature"
                        )

                # Parse webhook data
                webhook_data = json.loads(body.decode())

                # Add background task for ingestion
                background_tasks.add_task(self._process_discord_webhook, webhook_data)

                return {
                    "status": "received",
                    "message": "Discord webhook processed successfully",
                    "timestamp": datetime.now().isoformat(),
                }

            except Exception as e:
                logger.error(f"Error processing Discord webhook: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/telegram")
        async def telegram_webhook(
            request: Request,
            background_tasks: BackgroundTasks,
            token: str = Depends(verify_token),
        ):
            """Telegram webhook for real-time message ingestion"""
            try:
                # Get request body
                body = await request.body()

                # Parse webhook data
                webhook_data = json.loads(body.decode())

                # Add background task for ingestion
                background_tasks.add_task(self._process_telegram_webhook, webhook_data)

                return {
                    "status": "received",
                    "message": "Telegram webhook processed successfully",
                    "timestamp": datetime.now().isoformat(),
                }

            except Exception as e:
                logger.error(f"Error processing Telegram webhook: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/gmail")
        async def gmail_webhook(
            request: Request,
            background_tasks: BackgroundTasks,
            authorization: Optional[str] = None,
            token: str = Depends(verify_token),
        ):
            """Gmail webhook for real-time message ingestion"""
            try:
                # Get request body
                body = await request.body()

                # Parse webhook data
                webhook_data = json.loads(body.decode())

                # Add background task for ingestion
                background_tasks.add_task(self._process_gmail_webhook, webhook_data)

                return {
                    "status": "received",
                    "message": "Gmail webhook processed successfully",
                    "timestamp": datetime.now().isoformat(),
                }

            except Exception as e:
                logger.error(f"Error processing Gmail webhook: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/outlook")
        async def outlook_webhook(
            request: Request,
            background_tasks: BackgroundTasks,
            client_state: Optional[str] = None,
            token: str = Depends(verify_token),
        ):
            """Outlook webhook for real-time message ingestion"""
            try:
                # Get request body
                body = await request.body()

                # Parse webhook data
                webhook_data = json.loads(body.decode())

                # Add background task for ingestion
                background_tasks.add_task(self._process_outlook_webhook, webhook_data)

                return {
                    "status": "received",
                    "message": "Outlook webhook processed successfully",
                    "timestamp": datetime.now().isoformat(),
                }

            except Exception as e:
                logger.error(f"Error processing Outlook webhook: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/health")
        async def webhook_health():
            """Webhook system health check"""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "webhooks": list(self.webhook_secrets.keys()),
            }

    async def _process_whatsapp_webhook(self, webhook_data: Dict[str, Any]):
        """Process WhatsApp webhook data"""
        try:
            # Extract message data from WhatsApp webhook
            if "entry" in webhook_data:
                for entry in webhook_data["entry"]:
                    if "changes" in entry:
                        for change in entry["changes"]:
                            if "messages" in change["value"]:
                                for message in change["value"]["messages"]:
                                    # Normalize WhatsApp message
                                    normalized_message = {
                                        "id": message.get("id"),
                                        "direction": "inbound",
                                        "from": message.get("from"),
                                        "to": change["value"]
                                        .get("metadata", {})
                                        .get("phone_number_id"),
                                        "content": message.get("text", {}).get(
                                            "body", ""
                                        ),
                                        "message_type": message.get("type", "text"),
                                        "status": "received",
                                        "timestamp": datetime.now().isoformat(),
                                        "metadata": {
                                            "whatsapp_webhook": True,
                                            "original_data": message,
                                        },
                                    }

                                    # Ingest to memory
                                    ingestion_pipeline.ingest_message(
                                        "whatsapp", normalized_message
                                    )

            logger.info(
                f"Processed WhatsApp webhook with {len(webhook_data.get('entry', []))} entries"
            )

        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {str(e)}")

    async def _process_slack_webhook(self, webhook_data: Dict[str, Any]):
        """Process Slack webhook data"""
        try:
            # Extract message data from Slack webhook
            if "event" in webhook_data:
                event = webhook_data["event"]
                if event.get("type") == "message":
                    # Normalize Slack message
                    normalized_message = {
                        "id": event.get("ts"),
                        "direction": "inbound",
                        "sender": event.get("user"),
                        "recipient": event.get("channel"),
                        "content": event.get("text", ""),
                        "message_type": "text",
                        "status": "received",
                        "timestamp": datetime.fromtimestamp(
                            float(event.get("ts", 0))
                        ).isoformat(),
                        "metadata": {
                            "slack_webhook": True,
                            "event_type": event.get("type"),
                            "channel_type": event.get("channel_type"),
                            "original_data": event,
                        },
                    }

                    # Ingest to memory
                    ingestion_pipeline.ingest_message("slack", normalized_message)

            logger.info(
                f"Processed Slack webhook: {webhook_data.get('event', {}).get('type', 'unknown')}"
            )

        except Exception as e:
            logger.error(f"Error processing Slack webhook: {str(e)}")

    async def _process_discord_webhook(self, webhook_data: Dict[str, Any]):
        """Process Discord webhook data"""
        try:
            # Extract message data from Discord webhook
            if "message" in webhook_data:
                message = webhook_data["message"]

                # Normalize Discord message
                normalized_message = {
                    "id": message.get("id"),
                    "direction": "inbound",
                    "sender": message.get("author", {}).get("id"),
                    "recipient": message.get("channel_id"),
                    "content": message.get("content", ""),
                    "message_type": "text",
                    "status": "received",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "discord_webhook": True,
                        "author": message.get("author"),
                        "channel_id": message.get("channel_id"),
                        "original_data": message,
                    },
                }

                # Ingest to memory
                ingestion_pipeline.ingest_message("discord", normalized_message)

            logger.info(
                f"Processed Discord webhook: {webhook_data.get('type', 'unknown')}"
            )

        except Exception as e:
            logger.error(f"Error processing Discord webhook: {str(e)}")

    async def _process_telegram_webhook(self, webhook_data: Dict[str, Any]):
        """Process Telegram webhook data"""
        try:
            # Extract message data from Telegram webhook
            if "message" in webhook_data:
                message = webhook_data["message"]

                # Normalize Telegram message
                normalized_message = {
                    "id": str(message.get("message_id")),
                    "direction": "inbound",
                    "sender": str(message.get("from", {}).get("id")),
                    "recipient": str(message.get("chat", {}).get("id")),
                    "content": message.get("text", ""),
                    "message_type": "text",
                    "status": "received",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "telegram_webhook": True,
                        "chat": message.get("chat"),
                        "from": message.get("from"),
                        "original_data": message,
                    },
                }

                # Ingest to memory
                ingestion_pipeline.ingest_message("telegram", normalized_message)

            logger.info(
                f"Processed Telegram webhook: message_id {webhook_data.get('message', {}).get('message_id', 'unknown')}"
            )

        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {str(e)}")

    async def _process_gmail_webhook(self, webhook_data: Dict[str, Any]):
        """Process Gmail webhook data"""
        try:
            # Extract email data from Gmail webhook
            if "message" in webhook_data:
                message = webhook_data["message"]

                # Normalize Gmail message
                normalized_message = {
                    "id": message.get("id"),
                    "direction": "inbound",
                    "from": message.get("sender"),
                    "to": message.get("to"),
                    "subject": message.get("subject"),
                    "content": message.get("body", ""),
                    "message_type": "email",
                    "status": "received",
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "gmail_webhook": True,
                        "thread_id": message.get("thread_id"),
                        "labels": message.get("labels", []),
                        "original_data": message,
                    },
                }

                # Ingest to memory
                ingestion_pipeline.ingest_message("gmail", normalized_message)

            logger.info(
                f"Processed Gmail webhook: message_id {webhook_data.get('message', {}).get('id', 'unknown')}"
            )

        except Exception as e:
            logger.error(f"Error processing Gmail webhook: {str(e)}")

    async def _process_outlook_webhook(self, webhook_data: Dict[str, Any]):
        """Process Outlook webhook data"""
        try:
            # Extract email data from Outlook webhook
            if "value" in webhook_data:
                for message in webhook_data["value"]:
                    # Normalize Outlook message
                    normalized_message = {
                        "id": message.get("id"),
                        "direction": "inbound",
                        "from": message.get("from", {}).get("emailAddress"),
                        "to": ", ".join(
                            [
                                to.get("emailAddress")
                                for to in message.get("toRecipients", [])
                            ]
                        ),
                        "subject": message.get("subject"),
                        "content": message.get("body", {}).get("content", ""),
                        "message_type": "email",
                        "status": "received",
                        "timestamp": datetime.now().isoformat(),
                        "metadata": {
                            "outlook_webhook": True,
                            "conversation_id": message.get("conversationId"),
                            "web_link": message.get("webLink"),
                            "original_data": message,
                        },
                    }

                    # Ingest to memory
                    ingestion_pipeline.ingest_message("outlook", normalized_message)

            logger.info(
                f"Processed Outlook webhook: {len(webhook_data.get('value', []))} messages"
            )

        except Exception as e:
            logger.error(f"Error processing Outlook webhook: {str(e)}")

    def get_router(self):
        """Get the configured webhook router"""
        return self.router


# Create global webhook instance
atom_memory_webhooks = AtomCommunicationMemoryWebhooks()
atom_memory_webhooks_router = atom_memory_webhooks.get_router()

# Export for use
__all__ = [
    "AtomCommunicationMemoryWebhooks",
    "atom_memory_webhooks",
    "atom_memory_webhooks_router",
]
