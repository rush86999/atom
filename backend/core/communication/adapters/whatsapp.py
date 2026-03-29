import hashlib
import hmac
import logging
import os
from typing import Any, Dict, Optional
from fastapi import Request
import httpx

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class WhatsAppAdapter(PlatformAdapter):
    """
    Adapter for WhatsApp Cloud API (Direct).
    """
    def __init__(
        self,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        self.access_token = access_token or os.getenv("WHATSAPP_ACCESS_TOKEN")
        self.app_secret = app_secret or os.getenv("WHATSAPP_APP_SECRET")
        self.phone_number_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        self.api_version = "v17.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"

    async def _get_access_token(self) -> str:
        """Get the current access token, refreshing if necessary."""
        from core.token_refresher import token_refresher
        # If registered, the refresher might have a better token than env
        status = token_refresher.get_status().get("whatsapp")
        if status and status.get("access_token"):
             # In a real impl, we'd fetch from token_storage
             return status.get("access_token")
        return self.access_token

    async def verify_request(self, request: Request, body_bytes: bytes) -> bool:
        if not self.app_secret:
             # Dev mode or misconfiguration
             if os.getenv("ENVIRONMENT") == "development":
                 return True
             return False

        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            # WhatsApp verification challenge (GET) is handled by router usually, 
            # but for POSTs we need signature.
            return False
            
        # Signature format: "sha256=<sig>"
        if not signature.startswith("sha256="):
            return False
            
        sig_hash = signature.split("=")[1]
        
        # Calculate HMAC
        expected_hash = hmac.new(
            self.app_secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(sig_hash, expected_hash)

    def normalize_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalize WhatsApp Cloud API JSON payload.
        """
        # Basic structure check for messages
        try:
            entry = payload.get("entry", [])[0]
            changes = entry["changes"][0]
            value = changes["value"]
            if "messages" not in value:
                # Could be status update, ignore for now
                return None
                
            message = value["messages"][0]
            sender_id = message["from"] # Phone number
            is_interaction = False
            metadata = payload
            
            # Handle text messages
            if message["type"] == "text":
                content = message["text"]["body"]
            elif message["type"] == "interactive":
                is_interaction = True
                interactive = message["interactive"]
                if interactive["type"] == "button_reply":
                    content = interactive["button_reply"]["id"] # e.g. "APPROVE action_123"
                else:
                    content = "[Interactive Message]"
            elif message["type"] == "audio":
                content = "[Audio Message]"
                metadata["media_id"] = message["audio"]["id"]
                metadata["media_type"] = "audio"
            else:
                content = f"[Non-text message: {message['type']}]"
                
            return {
                "source": "whatsapp",
                "sender_id": sender_id,
                "channel_id": sender_id, # DM
                "content": content,
                "is_interaction": is_interaction,
                "metadata": metadata
            }
        except (KeyError, IndexError):
            return None

    async def send_message(self, target_id: str, message: str, metadata: Dict = None) -> bool:
        access_token = await self._get_access_token()
        if not access_token or not self.phone_number_id:
            logger.error("WhatsApp credentials missing.")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": target_id,
                    "type": "text",
                    "text": {"body": message}
                }
                
                response = await client.post(f"{self.base_url}/messages", json=payload, headers=headers)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False

    async def send_approval_request(self, target_id: str, action_id: str, details: Dict[str, Any], priority: str) -> bool:
        """Send a WhatsApp Interactive Message with Approve/Reject buttons"""
        access_token = await self._get_access_token()
        if not access_token or not self.phone_number_id:
            return await super().send_approval_request(target_id, action_id, details, priority)

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                
                header_text = f"Approval Required ({priority})"
                body_text = f"Action: {details.get('action_type')}\nReason: {details.get('reason')}\nID: {action_id}"
                
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": target_id,
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "header": {"type": "text", "text": header_text},
                        "body": {"text": body_text},
                        "action": {
                            "buttons": [
                                {
                                    "type": "reply",
                                    "reply": {"id": f"APPROVE {action_id}", "title": "Approve"}
                                },
                                {
                                    "type": "reply",
                                    "reply": {"id": f"REJECT {action_id}", "title": "Reject"}
                                }
                            ]
                        }
                    }
                }
                
                response = await client.post(f"{self.base_url}/messages", json=payload, headers=headers)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp interactive message: {e}")
            # Fallback to text
            return await super().send_approval_request(target_id, action_id, details, priority)

    async def get_media(self, media_id: str) -> Optional[bytes]:
        """Downloads media from WhatsApp Cloud API."""
        if not self.access_token:
            return None
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                # 1. Get media URL
                res = await client.get(
                    f"https://graph.facebook.com/{self.api_version}/{media_id}", 
                    headers=headers
                )
                res.raise_for_status()
                url = res.json().get("url")
                if not url:
                    return None
                
                # 2. Download media
                media_res = await client.get(url, headers=headers)
                media_res.raise_for_status()
                return media_res.content
        except Exception as e:
            logger.error(f"WhatsApp media download failed: {e}")
            return None
