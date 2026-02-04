"""
LINE Adapter for ATOM Messaging Platform

Provides integration with LINE messaging platform using LINE Messaging API.
"""

import hashlib
import logging
import os
import base64
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


class LineAdapter:
    """
    Adapter for LINE messaging platform.

    Uses LINE Messaging API for sending and receiving messages.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize LINE adapter.

        Args:
            config: Configuration dict with channel_access_token, channel_secret
        """
        self.config = config or {}
        self.channel_access_token = self.config.get(
            'channel_access_token',
            os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        )
        self.channel_secret = self.config.get(
            'channel_secret',
            os.getenv('LINE_CHANNEL_SECRET')
        )
        self.api_url = "https://api.line.me/v2/bot"

        self.is_enabled = bool(self.channel_access_token) and HTTPX_AVAILABLE
        self.client = None

        if self.is_enabled:
            logger.info("LINE adapter initialized")
        else:
            logger.warning("LINE adapter not configured or httpx not available")

    async def _get_client(self) -> Optional['httpx.AsyncClient']:
        """Get HTTP client with lazy initialization."""
        if not HTTPX_AVAILABLE:
            return None

        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {self.channel_access_token}",
                    "Content-Type": "application/json"
                }
            )
        return self.client

    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    def verify_signature(
        self,
        body: bytes,
        signature: str
    ) -> bool:
        """
        Verify X-Line-Signature from LINE.

        Args:
            body: Raw request body
            signature: X-Line-Signature header value

        Returns:
            True if signature is valid
        """
        try:
            if not self.channel_secret:
                logger.warning("Channel secret not configured, skipping signature verification")
                return True

            # Decode signature
            decoded_signature = base64.b64decode(signature)

            # Create hash
            hash_body = hmac.new(
                self.channel_secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).digest()

            # Compare signatures
            return hmac.compare_digest(decoded_signature, hash_body)

        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

    async def send_message(
        self,
        to: str,
        text: str,
        reply_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a text message to LINE user.

        Args:
            to: User ID or group ID or room ID
            text: Message text (max 2000 chars)
            reply_token: Optional reply token for replying to messages

        Returns:
            Dict with success status
        """
        try:
            client = await self._get_client()
            if not client:
                return {
                    'ok': False,
                    'error': 'httpx not available or LINE not configured'
                }

            # Build message payload
            message = {
                "type": "text",
                "text": text
            }

            # Send as reply if reply_token provided
            if reply_token:
                endpoint = f"{self.api_url}/message/reply"
                payload = {
                    "replyToken": reply_token,
                    "messages": [message]
                }
            else:
                endpoint = f"{self.api_url}/message/push"
                payload = {
                    "to": to,
                    "messages": [message]
                }

            response = await client.post(endpoint, json=payload)
            response.raise_for_status()

            return {
                'ok': True,
                'sent': True
            }

        except Exception as e:
            logger.error(f"Error sending LINE message: {e}")
            return {
                'ok': False,
                'error': str(e)
            }

    async def send_messages(
        self,
        to: str,
        messages: List[Dict[str, Any]],
        reply_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send multiple messages to LINE user.

        Args:
            to: User ID or group ID or room ID
            messages: List of message objects
            reply_token: Optional reply token for replying

        Returns:
            Dict with success status
        """
        try:
            client = await self._get_client()
            if not client:
                return {'ok': False, 'error': 'Client not available'}

            # Send as reply if reply_token provided
            if reply_token:
                endpoint = f"{self.api_url}/message/reply"
                payload = {
                    "replyToken": reply_token,
                    "messages": messages
                }
            else:
                endpoint = f"{self.api_url}/message/push"
                payload = {
                    "to": to,
                    "messages": messages
                }

            response = await client.post(endpoint, json=payload)
            response.raise_for_status()

            return {
                'ok': True,
                'sent': True,
                'count': len(messages)
            }

        except Exception as e:
            logger.error(f"Error sending LINE messages: {e}")
            return {'ok': False, 'error': str(e)}

    async def send_quick_reply(
        self,
        to: str,
        text: str,
        quick_reply_items: List[Dict[str, Any]],
        reply_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send message with quick reply buttons.

        Args:
            to: User ID
            text: Message text
            quick_reply_items: List of quick reply buttons
            reply_token: Optional reply token

        Returns:
            Dict with success status
        """
        try:
            message = {
                "type": "text",
                "text": text,
                "quickReply": {
                    "items": quick_reply_items
                }
            }

            return await self.send_messages(to, [message], reply_token)

        except Exception as e:
            logger.error(f"Error sending LINE quick reply: {e}")
            return {'ok': False, 'error': str(e)}

    async def send_template_message(
        self,
        to: str,
        alt_text: str,
        template: Dict[str, Any],
        reply_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a template message (buttons, carousel, etc.).

        Args:
            to: User ID
            alt_text: Alternative text
            template: Template object
            reply_token: Optional reply token

        Returns:
            Dict with success status
        """
        try:
            message = {
                "type": "template",
                "altText": alt_text,
                "template": template
            }

            return await self.send_messages(to, [message], reply_token)

        except Exception as e:
            logger.error(f"Error sending LINE template: {e}")
            return {'ok': False, 'error': str(e)}

    async def get_user_profile(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get user profile information.

        Args:
            user_id: LINE user ID

        Returns:
            Dict with user profile
        """
        try:
            client = await self._get_client()
            if not client:
                return {'ok': False, 'error': 'Client not available'}

            response = await client.get(f"{self.api_url}/profile/{user_id}")
            response.raise_for_status()

            result = response.json()

            return {
                'ok': True,
                'user_id': result.get('userId'),
                'display_name': result.get('displayName'),
                'picture_url': result.get('pictureUrl'),
                'status_message': result.get('statusMessage')
            }

        except Exception as e:
            logger.error(f"Error getting LINE user profile: {e}")
            return {'ok': False, 'error': str(e)}

    async def handle_webhook_event(
        self,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle incoming LINE webhook event.

        Args:
            event_data: Webhook event data

        Returns:
            Processed event data
        """
        try:
            events = event_data.get('events', [])
            if not events:
                return {'ok': False, 'error': 'No events in webhook'}

            # Process first event
            event = events[0]

            event_type = event.get('type')
            source = event.get('source', {})
            source_type = source.get('type')
            source_id = source.get('userId') or source.get('groupId') or source.get('roomId')
            reply_token = event.get('replyToken')
            timestamp = event.get('timestamp')

            # Message event
            if event_type == 'message':
                message = event.get('message', {})
                message_type = message.get('type')
                message_id = message.get('id')

                if message_type == 'text':
                    text = message.get('text')
                    return {
                        'ok': True,
                        'event_type': 'message',
                        'source_type': source_type,
                        'source_id': source_id,
                        'reply_token': reply_token,
                        'message_type': message_type,
                        'text': text,
                        'message_id': message_id,
                        'timestamp': timestamp,
                        'raw_data': event
                    }
                else:
                    # Image, video, audio, file, etc.
                    return {
                        'ok': True,
                        'event_type': 'message',
                        'source_type': source_type,
                        'source_id': source_id,
                        'reply_token': reply_token,
                        'message_type': message_type,
                        'message_id': message_id,
                        'content_provider': message.get('contentProvider'),
                        'timestamp': timestamp,
                        'raw_data': event
                    }

            # Follow event
            elif event_type == 'follow':
                return {
                    'ok': True,
                    'event_type': 'follow',
                    'source_type': source_type,
                    'source_id': source_id,
                    'reply_token': reply_token,
                    'timestamp': timestamp,
                    'raw_data': event
                }

            # Unfollow event
            elif event_type == 'unfollow':
                return {
                    'ok': True,
                    'event_type': 'unfollow',
                    'source_type': source_type,
                    'source_id': source_id,
                    'timestamp': timestamp,
                    'raw_data': event
                }

            # Join event
            elif event_type == 'join':
                return {
                    'ok': True,
                    'event_type': 'join',
                    'source_type': source_type,
                    'source_id': source_id,
                    'reply_token': reply_token,
                    'timestamp': timestamp,
                    'raw_data': event
                }

            # Leave event
            elif event_type == 'leave':
                return {
                    'ok': True,
                    'event_type': 'leave',
                    'source_type': source_type,
                    'source_id': source_id,
                    'timestamp': timestamp,
                    'raw_data': event
                }

            # Postback event
            elif event_type == 'postback':
                postback_data = event.get('postback', {})
                return {
                    'ok': True,
                    'event_type': 'postback',
                    'source_type': source_type,
                    'source_id': source_id,
                    'reply_token': reply_token,
                    'data': postback_data.get('data'),
                    'params': postback_data.get('params'),
                    'timestamp': timestamp,
                    'raw_data': event
                }

            # Beacon event
            elif event_type == 'beacon':
                beacon_data = event.get('beacon', {})
                return {
                    'ok': True,
                    'event_type': 'beacon',
                    'source_type': source_type,
                    'source_id': source_id,
                    'reply_token': reply_token,
                    'hwid': beacon_data.get('hwid'),
                    'type': beacon_data.get('type'),
                    'timestamp': timestamp,
                    'raw_data': event
                }

            else:
                return {
                    'ok': True,
                    'event_type': event_type,
                    'source_type': source_type,
                    'source_id': source_id,
                    'timestamp': timestamp,
                    'raw_data': event
                }

        except Exception as e:
            logger.error(f"Error handling LINE webhook: {e}")
            return {'ok': False, 'error': str(e)}

    async def get_capabilities(self) -> Dict[str, Any]:
        """
        Get LINE platform capabilities.

        Returns:
            Dict with platform capabilities
        """
        return {
            'platform': 'LINE',
            'features': {
                'messaging': True,
                'attachments': True,
                'quick_replies': True,
                'templates': True,
                'webhooks': True,
                'user_profiles': True,
                'rich_menus': True,
                'rate_limits': {
                    'messages_per_minute': 1000
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
            'service': 'LINE',
            'configured': self.is_enabled,
            'api_version': 'v2'
        }


# Import hmac after definition
import hmac

# Global LINE adapter instance
line_adapter = LineAdapter()
