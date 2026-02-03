import logging
import uuid
from typing import Any, Dict, Optional
import httpx

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class MatrixAdapter(PlatformAdapter):
    """
    Adapter for Matrix (Decentralized Communication).
    """
    
    def __init__(self, homeserver_url: str = None, access_token: str = None):
        self.homeserver_url = homeserver_url or "https://matrix.org"
        self.access_token = access_token

    def verify_request(self, headers: Dict, body: str) -> bool:
        """ Matrix webhooks are usually push rules or appservices. Verification varies. """
        return True

    def normalize_payload(self, payload: Dict) -> Optional[Dict[str, Any]]:
        """
        Normalize Matrix Event.
        {
          "type": "m.room.message",
          "sender": "@user:matrix.org",
          "content": { "msgtype": "m.text", "body": "hello" },
          "room_id": "!roomid:matrix.org"
        }
        """
        if payload.get("type") != "m.room.message":
            return None
            
        sender = payload.get("sender")
        content_obj = payload.get("content", {})
        body = content_obj.get("body")
        room_id = payload.get("room_id")
        
        if not sender or not body or not room_id:
            return None
            
        return {
            "source": "matrix",
            "source_id": room_id,
            "channel_id": room_id,
            "sender_id": sender,
            "content": body,
            "metadata": {
                "msgtype": content_obj.get("msgtype")
            }
        }

    async def send_message(self, target_id: str, message: str) -> bool:
        """ Send message to a Matrix Room. """
        if not self.access_token:
            return False
            
        txn_id = str(uuid.uuid4())
        url = f"{self.homeserver_url}/_matrix/client/v3/rooms/{target_id}/send/m.room.message/{txn_id}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "msgtype": "m.text",
            "body": message
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(url, json=payload, headers=headers)
                response.raise_for_status()
                logger.info(f"Matrix: Sent message to {target_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to send Matrix message: {e}")
                return False
