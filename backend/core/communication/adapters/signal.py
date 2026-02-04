import logging
from typing import Any, Dict, Optional
import httpx

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class SignalAdapter(PlatformAdapter):
    """
    Adapter for Signal (Simulated via signal-cli-rest-api or similar).
    """
    
    def __init__(self, api_url: str = None):
        self.api_url = api_url or "http://localhost:8080"

    def verify_request(self, headers: Dict, body: str) -> bool:
        return True

    def normalize_payload(self, payload: Dict) -> Optional[Dict[str, Any]]:
        """
        Assume payload from a Signal API bridge.
        """
        sender = payload.get("source")
        content = payload.get("message")
        
        if not sender or not content:
            return None
            
        return {
            "source": "signal",
            "source_id": sender,
            "channel_id": sender,
            "sender_id": sender,
            "content": content
        }

    async def send_message(self, target_id: str, message: str) -> bool:
        url = f"{self.api_url}/v2/send"
        
        payload = {
            "message": message,
            "number": "+YOUR_SIGNAL_NUMBER", # Configured at bridge level
            "recipients": [target_id]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # Use auth if bridge requires it
                response = await client.post(url, json=payload)
                # response.raise_for_status()
                logger.info(f"Signal: Sent message to {target_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to send Signal message: {e}")
                return False
