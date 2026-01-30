from typing import Dict, Any, Optional
import logging
import httpx
from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class LineAdapter(PlatformAdapter):
    """
    Adapter for Line (Messaging API).
    """
    
    def __init__(self, channel_access_token: str = None):
        self.channel_access_token = channel_access_token
        self.api_base = "https://api.line.me/v2/bot/message"

    def verify_request(self, headers: Dict, body: str) -> bool:
        # Line uses x-line-signature (HMAC-SHA256)
        return True

    def normalize_payload(self, payload: Dict) -> Optional[Dict[str, Any]]:
        """
        Normalize Line Webhook.
        {
          "events": [{
            "type": "message",
            "source": { "userId": "U1234..." },
            "message": { "type": "text", "text": "hello" }
          }]
        }
        """
        try:
            events = payload.get("events", [])
            if not events: return None
            
            event = events[0]
            if event.get("type") != "message": return None
            
            user_id = event.get("source", {}).get("userId")
            message_text = event.get("message", {}).get("text")
            
            if not user_id or not message_text: return None
            
            return {
                "source": "line",
                "source_id": user_id,
                "channel_id": user_id,
                "sender_id": user_id,
                "content": message_text
            }
        except:
            return None

    async def send_message(self, target_id: str, message: str) -> bool:
        if not self.channel_access_token:
            return False
            
        url = f"{self.api_base}/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.channel_access_token}"
        }
        
        payload = {
            "to": target_id,
            "messages": [{ "type": "text", "text": message }]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                logger.info(f"Line: Sent message to {target_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to send Line message: {e}")
                return False
