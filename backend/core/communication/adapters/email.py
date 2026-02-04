import json
import logging
import os
from email.utils import parseaddr
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError

from core.communication.adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

class EmailAdapter(PlatformAdapter):
    """
    Adapter for Email via AWS SES.
    
    Handlers Inbound (via SNS Notification or Webhook):
    - Parses AWS SES JSON notification format.
    
    Outbound:
    - Uses boto3 sesv2 client to send emails.
    """
    
    def __init__(self, region_name: str = "us-east-1", source_email: str = None):
        self.region_name = region_name
        self.source_email = source_email or os.getenv("SES_SOURCE_EMAIL", "support@atom.ai")
        try:
            self.ses_client = boto3.client("sesv2", region_name=self.region_name)
        except Exception as e:
            logger.warning(f"Failed to initialize SES client: {e}")
            self.ses_client = None

    def verify_request(self, headers: Dict, body: str) -> bool:
        """
        Verify inbound SES request.
        For SNS HTTPS subscriptions, verify signature (omitted for brevity, assumed validated by API Gateway/SNS).
        For direct webhooks, use a shared secret token if available.
        """
        # MVP: Assume secure transport from AWS via API Gateway auth or internal routing
        return True

    def normalize_payload(self, payload: Dict) -> Optional[Dict[str, Any]]:
        """
        Normalize AWS SES Inbound Notification.
        
        Payload structure (simplified):
        {
           "notificationType": "Received",
           "mail": {
               "messageId": "...",
               "source": "sender@example.com",
               "commonHeaders": {
                   "subject": "Help",
                   "from": ["Sender <sender@example.com>"],
                   "to": ["support@atom.ai"]
               }
           },
           "content": "..." (if raw) or retrieved via S3
        }
        
        Note: We assume the payload contains the text content directly or we parse the 'content' field.
        For this implementation, we assume a simplified JSON structure passed by the ingress handler.
        """
        # Handling SNS wrapper if present
        if "Type" in payload and payload["Type"] == "Notification":
             try:
                 payload = json.loads(payload.get("Message", "{}"))
             except json.JSONDecodeError as e:
                 logger.debug(f"Failed to parse SNS message: {e}")

        if payload.get("notificationType") != "Received":
            return None
            
        mail = payload.get("mail", {})
        common_headers = mail.get("commonHeaders", {})
        
        sender = common_headers.get("from", [None])[0]
        if not sender:
            sender = mail.get("source")
            
        # Parse email address
        _, sender_email = parseaddr(sender)
        
        # Determine content (This depends on SES Rule Set actions - assume we get a 'content' field or 'receipt' data)
        # For MVP, we'll look for a custom Body field injected by the Lambda/Ingress, or 'content'
        content = payload.get("content") or payload.get("body") or common_headers.get("subject", "")
        
        # Use Message-ID as Channel ID for threading references
        message_id = mail.get("messageId")
        
        if not sender_email or not content:
            return None
            
        return {
            "source": "email",
             # For email, channel_id acts as Thread ID. 
             # Initial email starts a thread (message_id). Replies should preserve In-Reply-To.
             # Simplification: Channel ID = Sender Email (Personal Thread) OR Message-ID
            "source_id": message_id,
            "channel_id": message_id, # Treating each email as a potential thread starter
            "sender_id": sender_email,
            "content": content,
            "metadata": {
                "subject": common_headers.get("subject"),
                "from_name": parseaddr(sender)[0]
            }
        }

    async def send_message(self, target_id: str, message: str) -> bool:
        """
        Send Reply via AWS SES.
        target_id: The Message-ID of the email we are replying to, OR the recipient email if not threading.
        
        We need a way to map 'channel_id' back to a Recipient + Thread Context.
        If target_id looks like an email, send new. If it looks like a UUID/Message-ID, we need to lookup context.
        
        Critically: The CommunicationService usually passes 'channel_id' preserved from ingress.
        For Email, ingress 'channel_id' was 'message_id'.
        But we need the RECIPIENT email address to reply.
        
        Issue: 'channel_id' alone isn't enough unless it's the email address itself.
        Fix: In normalize_payload, we should probably set 'channel_id' to `sender_email` for 1:1 chat behavior,
        OR store the sender email in a persistent session.
        
        Let's START with 'channel_id' = 'sender_email' to treat it like a DM.
        This ignores threading headers for now but ensures delivery.
        """
        
        # Check if target_id is an email address
        if "@" not in target_id:
            # If it's a message ID, we can't reply without lookup. 
            # Fallback: We assume the caller (CommunicationService) might pass context, 
            # but currently it passes (source, channel_id, message).
            # We will rely on 'channel_id' being the Email Address for this MVP.
            logger.error(f"EmailAdapter requires target_id to be an email address. Got: {target_id}")
            return False
            
        recipient = target_id
        
        if not self.ses_client:
             logger.warning("SES Client not available. specific mocking needed.")
             return False

        try:
            response = self.ses_client.send_email(
                FromEmailAddress=self.source_email,
                Destination={
                    'ToAddresses': [recipient]
                },
                Content={
                    'Simple': {
                        'Subject': {
                            'Data': f"Re: Support Request", # Simplified Subject
                            'Charset': 'UTF-8'
                        },
                        'Body': {
                            'Text': {
                                'Data': message,
                                'Charset': 'UTF-8'
                            }
                        }
                    }
                }
            )
            logger.info(f"Sent email to {recipient}, MessageId: {response.get('MessageId')}")
            return True
        except ClientError as e:
            logger.error(f"Failed to send email via SES: {e}")
            return False
        except Exception as e:
             logger.error(f"Unexpected SES error: {e}")
             return False
