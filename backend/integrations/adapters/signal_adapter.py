"""
Signal Adapter for ATOM Messaging Platform

Provides integration with Signal secure messaging platform using Signal REST API.
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


class SignalAdapter:
    """
    Adapter for Signal messaging platform.

    Uses Signal REST API for sending and receiving messages.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Signal adapter.

        Args:
            config: Configuration dict with signal_api_url, signal_phone_number
        """
        self.config = config or {}
        self.api_url = self.config.get(
            'signal_api_url',
            os.getenv('SIGNAL_API_URL', 'http://localhost:8080')
        )
        self.phone_number = self.config.get(
            'signal_phone_number',
            os.getenv('SIGNAL_PHONE_NUMBER')
        )
        self.account_number = self.config.get(
            'signal_account_number',
            os.getenv('SIGNAL_ACCOUNT_NUMBER')
        )

        self.is_enabled = bool(self.phone_number) and HTTPX_AVAILABLE
        self.client = None

        if self.is_enabled:
            logger.info(f"Signal adapter initialized for {self.phone_number}")
        else:
            logger.warning("Signal adapter not configured or httpx not available")

    async def _get_client(self) -> Optional['httpx.AsyncClient']:
        """Get HTTP client with lazy initialization."""
        if not HTTPX_AVAILABLE:
            return None

        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=30.0
            )
        return self.client

    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def send_message(
        self,
        recipient_number: str,
        message: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send a message to Signal recipient.

        Args:
            recipient_number: Phone number to send to (with country code, +1XXX)
            message: Text message content
            attachments: Optional list of attachments (filename, contentType, etc.)

        Returns:
            Dict with success status and message details
        """
        try:
            client = await self._get_client()
            if not client:
                return {
                    'ok': False,
                    'error': 'httpx not available or Signal not configured'
                }

            payload = {
                "message": message,
                "number": recipient_number,
                "recipients": [recipient_number]
            }

            if attachments:
                payload["attachments"] = attachments

            response = await client.post(
                "/v2/send",
                json=payload
            )
            response.raise_for_status()

            result = response.json()

            return {
                'ok': True,
                'message_id': result.get('timestamp', str(datetime.utcnow().timestamp())),
                'recipient': recipient_number,
                'timestamp': result.get('timestamp'),
                'payload': result
            }

        except Exception as e:
            logger.error(f"Error sending Signal message: {e}")
            return {
                'ok': False,
                'error': str(e)
            }

    async def send_receipt(
        self,
        recipient_number: str,
        message_timestamp: str,
        receipt_type: str = "read"
    ) -> Dict[str, Any]:
        """
        Send read/delivery receipt.

        Args:
            recipient_number: Phone number
            message_timestamp: Timestamp of message to acknowledge
            receipt_type: "read" or "delivery"

        Returns:
            Dict with success status
        """
        try:
            client = await self._get_client()
            if not client:
                return {'ok': False, 'error': 'Client not available'}

            payload = {
                "recipient": recipient_number,
                "timestamp": message_timestamp,
                "type": receipt_type
            }

            response = await client.post(
                "/v1/receipt",
                json=payload
            )
            response.raise_for_status()

            return {
                'ok': True,
                'recipient': recipient_number,
                'type': receipt_type
            }

        except Exception as e:
            logger.error(f"Error sending Signal receipt: {e}")
            return {'ok': False, 'error': str(e)}

    async def get_account_info(self) -> Dict[str, Any]:
        """
        Get information about the Signal account.

        Returns:
            Dict with account details
        """
        try:
            client = await self._get_client()
            if not client:
                return {'ok': False, 'error': 'Client not available'}

            response = await client.get("/v1/about")
            response.raise_for_status()

            result = response.json()

            return {
                'ok': True,
                'data': result
            }

        except Exception as e:
            logger.error(f"Error getting Signal account info: {e}")
            return {'ok': False, 'error': str(e)}

    async def verify_webhook(
        self,
        challenge: str
    ) -> Dict[str, Any]:
        """
        Verify webhook challenge for Signal REST API.

        Args:
            challenge: Challenge string from webhook

        Returns:
            Dict with challenge response
        """
        try:
            return {
                'ok': True,
                'challenge': challenge
            }

        except Exception as e:
            logger.error(f"Error verifying Signal webhook: {e}")
            return {'ok': False, 'error': str(e)}

    async def handle_webhook_event(
        self,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle incoming webhook event from Signal.

        Args:
            event_data: Webhook event data

        Returns:
            Processed event data
        """
        try:
            # Extract message data from webhook
            event_type = event_data.get('type', 'unknown')

            if event_type == 'message':
                envelope = event_data.get('envelope', {})
                data = envelope.get('data', {})

                source = data.get('source', {})
                source_number = source.get('number')

                message_data = data.get('message', {})
                text = message_data.get('body', '')

                return {
                    'ok': True,
                    'event_type': 'message',
                    'sender_number': source_number,
                    'message': text,
                    'timestamp': envelope.get('timestamp'),
                    'raw_data': event_data
                }

            elif event_type == 'receipt':
                envelope = event_data.get('envelope', {})
                data = envelope.get('data', {})
                receipt = data.get('receipt', {})

                return {
                    'ok': True,
                    'event_type': 'receipt',
                    'type': receipt.get('type'),
                    'timestamp': receipt.get('timestamp'),
                    'raw_data': event_data
                }

            else:
                return {
                    'ok': True,
                    'event_type': event_type,
                    'raw_data': event_data
                }

        except Exception as e:
            logger.error(f"Error handling Signal webhook: {e}")
            return {'ok': False, 'error': str(e)}

    async def get_capabilities(self) -> Dict[str, Any]:
        """
        Get Signal platform capabilities.

        Returns:
            Dict with platform capabilities
        """
        return {
            'platform': 'Signal',
            'features': {
                'messaging': True,
                'attachments': True,
                'read_receipts': True,
                'delivery_receipts': True,
                'typing_indicators': False,
                'interactive_components': False,
                'webhooks': True,
                'rate_limits': {
                    'messages_per_minute': 60,
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
        try:
            info = await self.get_account_info()

            return {
                'status': 'active' if self.is_enabled else 'inactive',
                'service': 'Signal',
                'phone_number': self.phone_number,
                'api_url': self.api_url,
                'configured': self.is_enabled,
                'account_info': info if info.get('ok') else None
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }


# Global Signal adapter instance
signal_adapter = SignalAdapter()
