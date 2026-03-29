import hashlib
import hmac
import logging
import os
import time
from typing import Any, Dict, Optional
from fastapi import Request

from .base import PlatformAdapter

logger = logging.getLogger(__name__)

class SlackAdapter(PlatformAdapter):
    """Adapter for Slack Events API"""
    
    def __init__(self):
        self.signing_secret = os.environ.get("SLACK_SIGNING_SECRET")
        self.bot_token = os.environ.get("SLACK_BOT_TOKEN") 
        
        try:
            from slack_sdk import WebClient
            self.client = WebClient(token=self.bot_token) if self.bot_token else None
        except ImportError:
            self.client = None
            logger.warning("slack_sdk not installed. Outbound messaging disabled.")

    async def verify_request(self, request: Request, body_bytes: bytes) -> bool:
        """
        Verify Slack request signature.
        Reference: https://api.slack.com/authentication/verifying-requests-from-slack
        """
        if not self.signing_secret:
            logger.warning("SLACK_SIGNING_SECRET not set. Skipping verification (INSECURE).")
            return True # Allow for dev if secret missing, but warn
            
        timestamp = request.headers.get("X-Slack-Request-Timestamp")
        signature = request.headers.get("X-Slack-Signature")
        
        if not timestamp or not signature:
            return False
            
        # Check timestamp to prevent replay attacks (5 minutes)
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
            
        sig_basestring = f"v0:{timestamp}:{body_bytes.decode('utf-8')}".encode('utf-8')
        my_signature = "v0=" + hmac.new(
            self.signing_secret.encode('utf-8'),
            sig_basestring,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(my_signature, signature)

    def normalize_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize Slack Event payload"""
        event = payload.get("event", {})
        
        # URL Verification Challenge (Handled in route, but good to have helper)
        if "challenge" in payload:
            return {"type": "challenge", "challenge": payload["challenge"]}
        
        if event.get("type") == "message":
            # Ignore bot messages and message edits for now
            if event.get("bot_id") or event.get("subtype"): 
                return None
                
            return {
                "sender_id": event.get("user"),
                "content": event.get("text"),
                "channel_id": event.get("channel"),
                "metadata": payload
            }
            
        # Handle Block Actions (Interactive Buttons)
        if payload.get("type") == "block_actions":
            actions = payload.get("actions", [])
            if not actions:
                return None
                
            action = actions[0]
            action_id = action.get("action_id") # e.g., "approve_123"
            value = action.get("value") # The actual action ID
            
            return {
                "sender_id": payload.get("user", {}).get("id"),
                "content": f"{action_id.upper()} {value}",
                "channel_id": payload.get("channel", {}).get("id"),
                "metadata": payload,
                "is_interaction": True
            }
            
        return None

    async def send_message(self, target_id: str, message: str, **kwargs) -> bool:
        if not self.client:
            logger.error("Cannot send Slack message: Client not initialized.")
            return False
            
        try:
            self.client.chat_postMessage(channel=target_id, text=message)
            return True
        except Exception as e:
            logger.error(f"Slack outbound error: {e}")
            return False

    async def send_approval_request(self, target_id: str, action_id: str, details: Dict[str, Any], priority: str) -> bool:
        """Send interactive approval request using Slack Blocks"""
        if not self.client:
            return False
            
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🚨 *HITL Approval Required* ({priority})\n*Action:* {details.get('action_type')}\n*Reason:* {details.get('reason')}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve ✅"},
                        "style": "primary",
                        "action_id": f"approve_{action_id}",
                        "value": action_id
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject ❌"},
                        "style": "danger",
                        "action_id": f"reject_{action_id}",
                        "value": action_id
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Action ID: `{action_id}` | Priority: {priority}"
                    }
                ]
            }
        ]
        
        try:
            self.client.chat_postMessage(channel=target_id, blocks=blocks, text=f"HITL Approval Required: {action_id}")
            return True
        except Exception as e:
            logger.error(f"Slack interactive send error: {e}")
            return False

    async def send_direct_message(self, target_id: str, message: str, agent_name: Optional[str] = None) -> bool:
        """Send a proactive message from a specific agent"""
        if not self.client:
            return False
            
        prefix = f"*[{agent_name}]* " if agent_name else ""
        try:
            self.client.chat_postMessage(channel=target_id, text=f"{prefix}{message}")
            return True
        except Exception as e:
            logger.error(f"Slack direct message error: {e}")
            return False
