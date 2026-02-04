"""
Facebook Messenger Adapter for ATOM Messaging Platform

Provides integration with Facebook Messenger using Facebook Graph API.
"""

import hashlib
import hmac
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


class MessengerAdapter:
    """
    Adapter for Facebook Messenger platform.

    Uses Facebook Messenger Platform API for sending and receiving messages.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Messenger adapter.

        Args:
            config: Configuration dict with page_access_token, app_secret, verify_token
        """
        self.config = config or {}
        self.page_access_token = self.config.get(
            'page_access_token',
            os.getenv('FACEBOOK_PAGE_ACCESS_TOKEN')
        )
        self.app_secret = self.config.get(
            'app_secret',
            os.getenv('FACEBOOK_APP_SECRET')
        )
        self.verify_token = self.config.get(
            'verify_token',
            os.getenv('FACEBOOK_VERIFY_TOKEN', 'atom_verify_token')
        )
        self.graph_api_url = "https://graph.facebook.com/v18.0"

        self.is_enabled = bool(self.page_access_token) and HTTPX_AVAILABLE
        self.client = None

        if self.is_enabled:
            logger.info("Facebook Messenger adapter initialized")
        else:
            logger.warning("Facebook Messenger adapter not configured or httpx not available")

    async def _get_client(self) -> Optional['httpx.AsyncClient']:
        """Get HTTP client with lazy initialization."""
        if not HTTPX_AVAILABLE:
            return None

        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30.0
            )
        return self.client

    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    def verify_webhook(
        self,
        mode: str,
        token: str,
        challenge: str
    ) -> Dict[str, Any]:
        """
        Verify webhook subscription from Facebook.

        Args:
            mode: Hub mode (should be 'subscribe')
            token: Verify token
            challenge: Challenge string to return

        Returns:
            Dict with success status and challenge
        """
        try:
            # Verify the token matches our verify token
            if token != self.verify_token:
                logger.warning("Webhook verification failed: invalid token")
                return {
                    'ok': False,
                    'error': 'Invalid verification token'
                }

            # Verify mode is subscribe
            if mode != 'subscribe':
                logger.warning(f"Webhook verification failed: invalid mode {mode}")
                return {
                    'ok': False,
                    'error': 'Invalid mode'
                }

            return {
                'ok': True,
                'challenge': challenge
            }

        except Exception as e:
            logger.error(f"Error verifying webhook: {e}")
            return {'ok': False, 'error': str(e)}

    def verify_signature(
        self,
        payload: bytes,
        signature: str
    ) -> bool:
        """
        Verify X-Hub-Signature from Facebook.

        Args:
            payload: Raw request body
            signature: X-Hub-Signature header value

        Returns:
            True if signature is valid
        """
        try:
            if not self.app_secret:
                logger.warning("App secret not configured, skipping signature verification")
                return True

            # Parse signature
            if signature.startswith('sha1='):
                signature = signature[5:]

            # Compute expected signature
            expected_signature = hmac.new(
                self.app_secret.encode('utf-8'),
                payload,
                hashlib.sha1
            ).hexdigest()

            # Compare signatures
            return hmac.compare_digest(expected_signature, signature)

        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

    async def send_message(
        self,
        recipient_id: str,
        message: str,
        messaging_type: str = "RESPONSE",
        quick_replies: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send a message to Facebook Messenger recipient.

        Args:
            recipient_id: PSID (Page-Scoped ID) of the recipient
            message: Message text
            messaging_type: Message type (RESPONSE, UPDATE, MESSAGE_TAG)
            quick_replies: Optional quick reply buttons

        Returns:
            Dict with success status and message ID
        """
        try:
            client = await self._get_client()
            if not client:
                return {
                    'ok': False,
                    'error': 'httpx not available or Messenger not configured'
                }

            # Build message payload
            message_data = {
                "recipient": {"id": recipient_id},
                "message": {"text": message},
                "messaging_type": messaging_type
            }

            if quick_replies:
                message_data["message"]["quick_replies"] = quick_replies

            # Send message
            response = await client.post(
                f"{self.graph_api_url}/me/messages",
                params={"access_token": self.page_access_token},
                json=message_data
            )
            response.raise_for_status()

            result = response.json()

            return {
                'ok': True,
                'message_id': result.get('message_id'),
                'recipient_id': recipient_id
            }

        except Exception as e:
            logger.error(f"Error sending Messenger message: {e}")
            return {
                'ok': False,
                'error': str(e)
            }

    async def send_attachment(
        self,
        recipient_id: str,
        attachment_type: str,
        attachment_url: str,
        messaging_type: str = "RESPONSE"
    ) -> Dict[str, Any]:
        """
        Send an attachment (image, audio, video, file).

        Args:
            recipient_id: PSID of recipient
            attachment_type: Type (image, audio, video, file)
            attachment_url: URL of the attachment
            messaging_type: Message type

        Returns:
            Dict with success status
        """
        try:
            client = await self._get_client()
            if not client:
                return {'ok': False, 'error': 'Client not available'}

            message_data = {
                "recipient": {"id": recipient_id},
                "message": {
                    "attachment": {
                        "type": attachment_type,
                        "payload": {"url": attachment_url}
                    }
                },
                "messaging_type": messaging_type
            }

            response = await client.post(
                f"{self.graph_api_url}/me/messages",
                params={"access_token": self.page_access_token},
                json=message_data
            )
            response.raise_for_status()

            result = response.json()

            return {
                'ok': True,
                'message_id': result.get('message_id'),
                'attachment_id': result.get('attachment_id')
            }

        except Exception as e:
            logger.error(f"Error sending Messenger attachment: {e}")
            return {'ok': False, 'error': str(e)}

    async def get_user_info(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get information about a Messenger user.

        Args:
            user_id: PSID of the user

        Returns:
            Dict with user information
        """
        try:
            client = await self._get_client()
            if not client:
                return {'ok': False, 'error': 'Client not available'}

            response = await client.get(
                f"{self.graph_api_url}/{user_id}",
                params={
                    "access_token": self.page_access_token,
                    "fields": "first_name,last_name,profile_pic"
                }
            )
            response.raise_for_status()

            result = response.json()

            return {
                'ok': True,
                'user_id': user_id,
                'first_name': result.get('first_name'),
                'last_name': result.get('last_name'),
                'profile_pic': result.get('profile_pic')
            }

        except Exception as e:
            logger.error(f"Error getting Messenger user info: {e}")
            return {'ok': False, 'error': str(e)}

    async def handle_webhook_event(
        self,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle incoming webhook event from Facebook.

        Args:
            event_data: Webhook event data

        Returns:
            Processed event data
        """
        try:
            entry = event_data.get('entry', [])
            if not entry:
                return {'ok': False, 'error': 'No entry in webhook'}

            # Get messaging events
            messaging_events = []
            for ent in entry:
                messaging = ent.get('messaging', [])
                messaging_events.extend(messaging)

            if not messaging_events:
                return {
                    'ok': True,
                    'event_type': 'unknown',
                    'raw_data': event_data
                }

            # Process first messaging event
            event = messaging_events[0]

            sender_id = event.get('sender', {}).get('id')
            recipient_id = event.get('recipient', {}).get('id')

            # Check for message
            if 'message' in event:
                message = event['message']
                text = message.get('text', '')
                attachments = message.get('attachments', [])
                mid = message.get('mid')

                return {
                    'ok': True,
                    'event_type': 'message',
                    'sender_id': sender_id,
                    'recipient_id': recipient_id,
                    'message_id': mid,
                    'text': text,
                    'attachments': attachments,
                    'raw_data': event_data
                }

            # Check for delivery
            elif 'delivery' in event:
                delivery = event['delivery']
                watermark = delivery.get('watermark')
                mids = delivery.get('mids', [])

                return {
                    'ok': True,
                    'event_type': 'delivery',
                    'sender_id': sender_id,
                    'recipient_id': recipient_id,
                    'watermark': watermark,
                    'message_ids': mids,
                    'raw_data': event_data
                }

            # Check for read
            elif 'read' in event:
                read = event['read']
                watermark = read.get('watermark')

                return {
                    'ok': True,
                    'event_type': 'read',
                    'sender_id': sender_id,
                    'recipient_id': recipient_id,
                    'watermark': watermark,
                    'raw_data': event_data
                }

            # Check for postback
            elif 'postback' in event:
                postback = event['postback']
                payload = postback.get('payload')

                return {
                    'ok': True,
                    'event_type': 'postback',
                    'sender_id': sender_id,
                    'recipient_id': recipient_id,
                    'payload': payload,
                    'raw_data': event_data
                }

            else:
                return {
                    'ok': True,
                    'event_type': 'unknown',
                    'sender_id': sender_id,
                    'raw_data': event_data
                }

        except Exception as e:
            logger.error(f"Error handling Messenger webhook: {e}")
            return {'ok': False, 'error': str(e)}

    async def get_capabilities(self) -> Dict[str, Any]:
        """
        Get Messenger platform capabilities.

        Returns:
            Dict with platform capabilities
        """
        return {
            'platform': 'Facebook Messenger',
            'features': {
                'messaging': True,
                'attachments': True,
                'read_receipts': True,
                'delivery_receipts': True,
                'typing_indicators': True,
                'quick_replies': True,
                'webhooks': True,
                'user_info': True,
                'rate_limits': {
                    'messages_per_day': 1000
                }
            },
            'governance': {
                'student': {'blocked': True},
                'intern': {'requires_approval': True},
                'supervised': {'auto_approved': True, 'monitored': True},
                'autonomous': {'full_access': True}
            }
        }

    async def get_service_status(self) -> Dict[str, Any]:
        """
        Get service status.

        Returns:
            Dict with status information
        """
        return {
            'status': 'active' if self.is_enabled else 'inactive',
            'service': 'Facebook Messenger',
            'configured': self.is_enabled,
            'graph_api_version': 'v18.0'
        }


# Global Messenger adapter instance
messenger_adapter = MessengerAdapter()
