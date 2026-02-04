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
