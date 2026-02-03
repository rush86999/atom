"""
Webhook Handlers for Real-Time Communication Ingestion
Handles webhook events from Slack, Teams, and Gmail for real-time message processing.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class WebhookEvent:
    """Normalized webhook event from any platform"""

    def __init__(
        self,
        platform: str,
        event_type: str,
        event_data: Dict[str, Any],
        raw_payload: Dict[str, Any],
        timestamp: datetime = None
    ):
        self.platform = platform
        self.event_type = event_type
        self.event_data = event_data
        self.raw_payload = raw_payload
        self.timestamp = timestamp or datetime.now()
        self.processed = False

    def to_unified_message(self) -> Dict[str, Any]:
        """Convert webhook event to unified message format"""
        # This will be implemented per platform
        return {
            "app_type": self.platform,
            "raw_event": self.raw_payload,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat()
        }


class SlackWebhookHandler:
    """Handle Slack webhook events"""

    def __init__(self, signing_secret: Optional[str] = None):
        self.signing_secret = signing_secret

    def verify_signature(self, timestamp: str, signature: str, body: bytes) -> bool:
        """Verify Slack webhook signature"""
        if not self.signing_secret:
            logger.warning("No Slack signing secret configured, skipping signature verification")
            return True  # Allow in development

        # Create signature
        basestring = f"v0:{timestamp}".encode() + body
        expected_signature = "v0=" + hmac.new(
            self.signing_secret.encode(),
            basestring,
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, signature)

    def parse_event(self, raw_event: Dict[str, Any]) -> Optional[WebhookEvent]:
        """Parse Slack webhook event"""
        try:
            event_type = raw_event.get("type", "")

            # Handle URL verification challenge
            if event_type == "url_verification":
                return WebhookEvent(
                    platform="slack",
                    event_type="url_verification",
                    event_data={"challenge": raw_event.get("challenge")},
                    raw_payload=raw_event
                )

            # Handle event callback
            if event_type == "event_callback":
                slack_event = raw_event.get("event", {})
                event_subtype = slack_event.get("type", "")

                # Message event
                if event_subtype == "message":
                    # Normalize to unified message format
                    message_data = {
                        "id": slack_event.get("client_msg_id") or slack_event.get("ts"),
                        "app_type": "slack",
                        "content": slack_event.get("text", ""),
                        "content_type": "text",
                        "sender": slack_event.get("user", ""),
                        "recipient": slack_event.get("channel", ""),
                        "timestamp": slack_event.get("ts"),
                        "direction": "inbound",
                        "metadata": {
                            "channel_id": slack_event.get("channel"),
                            "team": slack_event.get("team"),
                            "event_id": slack_event.get("event_id"),
                            "thread_ts": slack_event.get("thread_ts"),
                            "parent_user_id": slack_event.get("parent_user_id")
                        },
                        "tags": ["slack", "webhook"],
                        "status": "active"
                    }

                    return WebhookEvent(
                        platform="slack",
                        event_type="message",
                        event_data=message_data,
                        raw_payload=raw_event
                    )

            logger.info(f"Unhandled Slack event type: {event_type}")
            return None

        except Exception as e:
            logger.error(f"Error parsing Slack event: {e}")
            return None


class TeamsWebhookHandler:
    """Handle Microsoft Teams webhook events"""

    def __init__(self, app_id: Optional[str] = None):
        self.app_id = app_id

    def verify_signature(self, auth_header: Optional[str]) -> bool:
        """Verify Teams webhook authorization"""
        # Teams uses Bearer token from Microsoft Graph
        # For now, we'll rely on the endpoint being secured
        return True

    def parse_event(self, raw_event: Dict[str, Any]) -> Optional[WebhookEvent]:
        """Parse Teams webhook event"""
        try:
            event_type = raw_event.get("type", "")

            # Teams resource data
            value = raw_event.get("value", [])
            if isinstance(value, dict):
                value = [value]

            for item in value:
                # Message event
                if item.get("@odata.type") == "#Microsoft.Graph.chatMessage":
                    message_data = {
                        "id": item.get("id"),
                        "app_type": "microsoft_teams",
                        "content": item.get("body", {}).get("content", ""),
                        "content_type": item.get("body", {}).get("contentType", "text"),
                        "sender": item.get("from", {}).get("user", {}).get("displayName", ""),
                        "sender_email": item.get("from", {}).get("user", {}).get("email", ""),
                        "recipient": item.get("chatId"),
                        "timestamp": item.get("createdDateTime"),
                        "direction": "inbound",
                        "metadata": {
                            "chat_id": item.get("chatId"),
                            "message_type": item.get("messageType"),
                            "web_url": item.get("webUrl"),
                            "importance": item.get("importance", "Normal")
                        },
                        "tags": ["teams", "webhook"],
                        "status": "active"
                    }

                    return WebhookEvent(
                        platform="teams",
                        event_type="message",
                        event_data=message_data,
                        raw_payload=raw_event
                    )

            logger.info(f"Unhandled Teams event type: {event_type}")
            return None

        except Exception as e:
            logger.error(f"Error parsing Teams event: {e}")
            return None


class GmailWebhookHandler:
    """Handle Gmail push notification webhook events"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def verify_signature(self, headers: Dict[str, str]) -> bool:
        """Verify Gmail webhook notification"""
        # Gmail uses Google's Pub/Sub verification
        # For now, we'll rely on the endpoint being secured
        return True

    def parse_event(self, raw_event: Dict[str, Any]) -> Optional[WebhookEvent]:
        """Parse Gmail webhook notification"""
        try:
            message_data = raw_event.get("message", {})
            data_str = message_data.get("data", "")

            if not data_str:
                logger.warning("Empty Gmail notification data")
                return None

            # Decode base64 data
            import base64
            decoded = base64.b64decode(data_str).decode()
            notification = json.loads(decoded)

            email_address = notification.get("emailAddress")
            history_id = notification.get("historyId")

            # This is a notification that something changed
            # We need to fetch the actual email using Gmail API
            event_data = {
                "app_type": "gmail",
                "email_address": email_address,
                "history_id": history_id,
                "notification_type": "history_notification",
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "notification": notification
                },
                "tags": ["gmail", "webhook", "push_notification"],
                "status": "pending_fetch"
            }

            return WebhookEvent(
                platform="gmail",
                event_type="push_notification",
                event_data=event_data,
                raw_payload=raw_event
            )

        except Exception as e:
            logger.error(f"Error parsing Gmail event: {e}")
            return None


class WebhookProcessor:
    """Process webhook events and integrate with message pipeline"""

    def __init__(self):
        self.slack_handler = SlackWebhookHandler()
        self.teams_handler = TeamsWebhookHandler()
        self.gmail_handler = GmailWebhookHandler()

        # Event deduplication cache
        self.processed_events: Dict[str, datetime] = {}

        # Callback for when events are processed
        self.on_message_received = None

    def register_message_callback(self, callback):
        """Register callback for new messages"""
        self.on_message_received = callback

    async def process_slack_webhook(
        self,
        request: Request,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """Process incoming Slack webhook"""
        try:
            body = await request.body()

            # Get headers
            timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
            signature = request.headers.get("X-Slack-Signature", "")

            # Verify signature
            if not self.slack_handler.verify_signature(timestamp, signature, body):
                raise HTTPException(status_code=401, detail="Invalid signature")

            # Parse event
            raw_event = json.loads(body)
            event = self.slack_handler.parse_event(raw_event)

            if not event:
                return {"status": "ignored", "reason": "Unhandled event type"}

            # Handle URL verification challenge
            if event.event_type == "url_verification":
                return {"challenge": event.event_data.get("challenge")}

            # Check for duplicate
            event_id = f"slack_{raw_event.get('event_id', '')}"
            if self._is_duplicate(event_id):
                return {"status": "duplicate", "event_id": event_id}

            # Mark as processed
            self._mark_processed(event_id)

            # Process in background
            if self.on_message_received and event.event_type == "message":
                background_tasks.add_task(self._process_message, event)

            return {
                "status": "success",
                "event_id": event_id,
                "platform": "slack"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing Slack webhook: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def process_teams_webhook(
        self,
        request: Request,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """Process incoming Teams webhook"""
        try:
            raw_event = await request.json()

            # Parse event
            event = self.teams_handler.parse_event(raw_event)

            if not event:
                return {"status": "ignored", "reason": "Unhandled event type"}

            # Check for duplicate
            event_id = f"teams_{raw_event.get('id', '')}"
            if self._is_duplicate(event_id):
                return {"status": "duplicate", "event_id": event_id}

            # Mark as processed
            self._mark_processed(event_id)

            # Process in background
            if self.on_message_received and event.event_type == "message":
                background_tasks.add_task(self._process_message, event)

            return {
                "status": "success",
                "event_id": event_id,
                "platform": "teams"
            }

        except Exception as e:
            logger.error(f"Error processing Teams webhook: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def process_gmail_webhook(
        self,
        request: Request,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """Process incoming Gmail webhook notification"""
        try:
            raw_event = await request.json()

            # Parse event
            event = self.gmail_handler.parse_event(raw_event)

            if not event:
                return {"status": "ignored", "reason": "Invalid notification"}

            # Check for duplicate
            history_id = raw_event.get("message", {}).get("data", "")
            event_id = f"gmail_{history_id}"
            if self._is_duplicate(event_id):
                return {"status": "duplicate", "event_id": event_id}

            # Mark as processed
            self._mark_processed(event_id)

            # Process in background
            if self.on_message_received:
                background_tasks.add_task(self._process_message, event)

            return {
                "status": "success",
                "event_id": event_id,
                "platform": "gmail"
            }

        except Exception as e:
            logger.error(f"Error processing Gmail webhook: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def _is_duplicate(self, event_id: str) -> bool:
        """Check if event has already been processed"""
        return event_id in self.processed_events

    def _mark_processed(self, event_id: str):
        """Mark event as processed"""
        self.processed_events[event_id] = datetime.now()

        # Clean old events (keep last 10000)
        if len(self.processed_events) > 10000:
            # Remove oldest 1000
            sorted_events = sorted(
                self.processed_events.items(),
                key=lambda x: x[1]
            )
            for event_id, _ in sorted_events[:1000]:
                del self.processed_events[event_id]

    async def _process_message(self, event: WebhookEvent):
        """Process webhook message event"""
        try:
            # Convert to unified message format
            message_data = event.to_unified_message()

            # Call callback if registered
            if self.on_message_received:
                await self.on_message_received(message_data)

            logger.info(f"Processed webhook message from {event.platform}: {event.event_type}")

        except Exception as e:
            logger.error(f"Error processing webhook message: {e}")


# Singleton instance
webhook_processor = WebhookProcessor()


def get_webhook_processor() -> WebhookProcessor:
    """Get the singleton webhook processor"""
    return webhook_processor
