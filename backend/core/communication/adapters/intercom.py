import hashlib
import hmac
import logging
import os
from typing import Any, Dict, Optional
import httpx

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class IntercomAdapter(PlatformAdapter):
    """
    Adapter for Intercom (Customer Support).
    
    Handlers Webhooks:
    - conversation.user.created
    - conversation.user.replied
    
    Outbound:
    - POST https://api.intercom.io/conversations/{id}/reply
    """
    
    def __init__(self, access_token: str, client_secret: str = None):
        self.access_token = access_token
        self.client_secret = client_secret
        self.api_base = "https://api.intercom.io"

    def verify_request(self, headers: Dict, body: str) -> bool:
        """
        Verify Intercom Webhook Signature (X-Hub-Signature).

        CRYPTOGRAPHY FIX: Supports both SHA256 (preferred) and SHA1 (legacy).
        Uses SHA256 for stronger security, falls back to SHA1 for compatibility.
        """
        if not self.client_secret:
            logger.warning("Intercom client_secret not configured. Skipping verification.")
            return True

        signature = headers.get("x-hub-signature")
        if not signature:
            logger.warning("Missing X-Hub-Signature header from Intercom")
            return False

        # Expected format: sha256=... or sha1=...
        try:
            algo, sig = signature.split("=", 1)
        except ValueError:
            logger.warning("Invalid signature format from Intercom")
            return False

        # Determine hash algorithm
        # Prefer SHA256 for security, support SHA1 for legacy compatibility
        if algo == "sha256":
            digestmod = hashlib.sha256
        elif algo == "sha1":
            # SHA1 is deprecated but support for backward compatibility
            logger.debug(
                "Intercom using SHA1 signature (deprecated). "
                "Consider upgrading to SHA256 if supported.",
                extra={"security_note": "SHA1 is deprecated"}
            )
            digestmod = hashlib.sha1
        else:
            logger.warning(f"Unsupported signature algorithm: {algo}")
            return False

        # Compute HMAC signature
        mac = hmac.new(
            self.client_secret.encode("utf-8"),
            msg=body.encode("utf-8"),
            digestmod=digestmod
        )
        expected_sig = mac.hexdigest()

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_sig, sig)

    def normalize_payload(self, payload: Dict) -> Optional[Dict[str, Any]]:
        """
        Normalize Intercom 'conversation.user.created' or 'conversation.user.replied'.
        
        Payload structure (simplified):
        {
          "topic": "conversation.user.created",
          "data": {
            "item": {
              "id": "123456",
              "user": { "id": "abc", "email": "user@example.com" },
              "conversation_message": { "body": "<p>Hello</p>" }
            }
          }
        }
        """
        topic = payload.get("topic")
        if topic not in ["conversation.user.created", "conversation.user.replied"]:
            logger.info(f"Ignoring Intercom topic: {topic}")
            return None
            
        item = payload.get("data", {}).get("item", {})
        conversation_id = item.get("id")
        
        # User details
        user_data = item.get("user", {})
        user_id = user_data.get("id") or user_data.get("email") # Use Email as fallback ID if external_id missing
        
        # Message Body (Intercom uses HTML)
        message_parts = item.get("conversation_message", {})
        # Simplistic HTML stripping or just pass raw. Better to strip tags ideally.
        # For now, we take raw body (client side agents might handle html or we strip it here)
        raw_body = message_parts.get("body", "")
        
        # Simple HTML tag stripper (optional but recommended for LLMs)
        import re
        clean_text = re.sub('<[^<]+?>', '', raw_body).strip()
        
        if not conversation_id or not clean_text:
            return None
            
        return {
            "source": "intercom",
            "source_id": conversation_id, # Channel ID is Conversation ID
            "sender_id": user_id,
            "content": clean_text,
            "metadata": {
                "topic": topic,
                "email": user_data.get("email"),
                "name": user_data.get("name")
            }
        }

    async def send_message(self, target_id: str, message: str) -> bool:
        """
        Reply to an Intercom conversation.
        POST /conversations/{id}/reply
        """
        url = f"{self.api_base}/conversations/{target_id}/reply"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Intercom-Version": "2.11"
        }
        
        payload = {
            "message_type": "comment",
            "type": "admin", # Reply as Admin (the bot)
            "admin_id": "me", # Use the token's admin context
            "body": message
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                logger.info(f"Sent Intercom reply to conversation {target_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to send Intercom message: {e}")
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Intercom Response: {e.response.text}")
                return False
