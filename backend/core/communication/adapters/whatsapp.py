import logging
import os
import httpx
import hashlib
import hmac
from typing import Dict, Any, Optional
from fastapi import Request

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class WhatsAppAdapter(PlatformAdapter):
    """
    Adapter for WhatsApp Cloud API (Direct).
    """
    def __init__(self):
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
        self.app_secret = os.getenv("WHATSAPP_APP_SECRET")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        self.api_version = "v17.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"

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
            
            # Handle text messages
            if message["type"] == "text":
                content = message["text"]["body"]
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
                "metadata": payload
            }
        except (KeyError, IndexError):
            # logger.warning("WhatsApp payload structure unknown") # Reduce noise
            return None

    async def send_message(self, target_id: str, message: str, metadata: Dict = None) -> bool:
        if not self.access_token or not self.phone_number_id:
            logger.error("WhatsApp credentials missing.")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
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
