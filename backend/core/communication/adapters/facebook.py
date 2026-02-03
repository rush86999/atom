import logging
from typing import Any, Dict, Optional
import httpx

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class FacebookAdapter(PlatformAdapter):
    """
    Adapter for Facebook Messenger.
    """
    
    def __init__(self, page_access_token: str = None):
        self.page_access_token = page_access_token
        self.api_base = "https://graph.facebook.com/v19.0"

    def verify_request(self, headers: Dict, body: str) -> bool:
        # FB uses X-Hub-Signature-256 (HMAC-SHA256)
        return True

    def normalize_payload(self, payload: Dict) -> Optional[Dict[str, Any]]:
        """
        Normalize Messenger Webhook payload.
        {
          "object": "page",
          "entry": [{
            "messaging": [{
              "sender": { "id": "USER_ID" },
              "recipient": { "id": "PAGE_ID" },
              "message": { "text": "hello" }
            }]
          }]
        }
        """
        if payload.get("object") != "page":
            return None
            
        try:
            entry = payload.get("entry", [])[0]
            messaging = entry.get("messaging", [])[0]
            sender_id = messaging.get("sender", {}).get("id")
            message = messaging.get("message", {})
            text = message.get("text")
            
            if not sender_id or not text:
                return None
                
            return {
                "source": "facebook",
                "source_id": sender_id,
                "channel_id": sender_id,
                "sender_id": sender_id,
                "content": text
            }
        except Exception as e:
            logger.error(f"Failed to normalize Facebook payload: {e}", exc_info=True)
            return None

    async def send_message(self, target_id: str, message: str) -> bool:
        if not self.page_access_token:
            return False
            
        url = f"{self.api_base}/me/messages?access_token={self.page_access_token}"
        
        payload = {
            "recipient": { "id": target_id },
            "message": { "text": message },
            "messaging_type": "RESPONSE"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logger.info(f"Facebook: Sent message to {target_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to send Facebook message: {e}")
                return False
