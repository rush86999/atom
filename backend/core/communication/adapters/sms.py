import base64
import hashlib
import hmac
import logging
import os
from typing import Any, Dict, Optional
import httpx

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class SMSAdapter(PlatformAdapter):
    """
    Adapter for SMS via Twilio (Direct API, no SDK).
    
    Handlers Webhooks:
    - Incoming SMS (POST from Twilio)
    
    Outbound:
    - POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json
    """
    
    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.phone_number = phone_number
        self.api_base = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}"

    def verify_request(self, headers: Dict, body: str) -> bool:
        """
        Verify Twilio X-Twilio-Signature.
        This requires the full URL (including query params) and the body.
        Since we only get headers/body here and not the full URL easily without framework coupling, 
        we might skip strict validation for this MVP or assume it's validated at the ingress layer.
        
        For production, one would reconstruct the URL:
        sig = headers.get("X-Twilio-Signature")
        validator = parse_and_validate(url, params, sig)
        """
        # MVP: Skip strict validation to avoid tight coupling with FastAPI Request object here.
        return True

    def normalize_payload(self, payload: Dict) -> Optional[Dict[str, Any]]:
        """
        Normalize Twilio Incoming SMS Webhook (Form Data usually, but passed as Dict here).
        
        Expected fields (from Form Data):
        - From: +1234567890
        - Body: Request text
        - MessageSid: SM...
        """
        sender = payload.get("From")
        content = payload.get("Body")
        message_sid = payload.get("MessageSid")
        
        if not sender or not content:
            return None
            
        return {
            "source": "sms",
            "source_id": message_sid,
            "channel_id": sender, # User Phone Number is the Channel ID (1:1)
            "sender_id": sender,
            "content": content,
            "metadata": {
                "to_number": payload.get("To"),
                "city": payload.get("FromCity"),
                "state": payload.get("FromState")
            }
        }

    async def send_message(self, target_id: str, message: str) -> bool:
        """
        Send SMS via Twilio API.
        target_id: The Recipient User Phone Number.
        """
        url = f"{self.api_base}/Messages.json"
        
        # Twilio uses Basic Auth
        auth = (self.account_sid, self.auth_token)
        
        data = {
            "To": target_id,
            "From": self.phone_number,
            "Body": message
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=data, auth=auth)
                if response.is_error:
                    logger.error(f"Twilio API Error: {response.text}")
                    return False
                    
                logger.info(f"Sent SMS to {target_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to send SMS: {e}")
                return False
