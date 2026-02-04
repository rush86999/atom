"""
Tests for Webhook Handlers
Tests real-time webhook event processing for Slack, Teams, and Gmail.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
import pytest

from core.webhook_handlers import (
    GmailWebhookHandler,
    SlackWebhookHandler,
    TeamsWebhookHandler,
    WebhookEvent,
    WebhookProcessor,
)


@pytest.fixture
def slack_handler():
    """Create Slack webhook handler"""
    return SlackWebhookHandler(signing_secret="test_secret")


@pytest.fixture
def teams_handler():
    """Create Teams webhook handler"""
    return TeamsWebhookHandler()


@pytest.fixture
def gmail_handler():
    """Create Gmail webhook handler"""
    return GmailWebhookHandler()


@pytest.fixture
def webhook_processor():
    """Create webhook processor"""
    return WebhookProcessor()


class TestSlackWebhookHandler:
    """Test Slack webhook handling"""

    def test_verify_signature_valid(self, slack_handler):
        """Test signature verification with valid signature"""
        timestamp = "1234567890"
        body = b"test_body"

        # Calculate expected signature
        import hashlib
        import hmac
        basestring = f"v0:{timestamp}".encode() + body
        expected_signature = "v0=" + hmac.new(
            slack_handler.signing_secret.encode(),
            basestring,
            hashlib.sha256
        ).hexdigest()

        assert slack_handler.verify_signature(timestamp, expected_signature, body) is True

    def test_verify_signature_invalid(self, slack_handler):
        """Test signature verification with invalid signature"""
        timestamp = "1234567890"
        body = b"test_body"

        assert slack_handler.verify_signature(timestamp, "invalid_signature", body) is False

    def test_parse_message_event(self, slack_handler):
        """Test parsing Slack message event"""
        raw_event = {
            "type": "event_callback",
            "event_id": "Ev12345",
            "event": {
                "type": "message",
                "user": "U123456",
                "channel": "C123456",
                "text": "Hello from Slack!",
                "ts": "1234567890.123456",
                "team": "T123456"
            }
        }

        event = slack_handler.parse_event(raw_event)

        assert event is not None
        assert event.platform == "slack"
        assert event.event_type == "message"
        assert event.event_data["content"] == "Hello from Slack!"
        assert event.event_data["sender"] == "U123456"
        assert event.event_data["recipient"] == "C123456"

    def test_parse_url_verification(self, slack_handler):
        """Test parsing Slack URL verification challenge"""
        raw_event = {
            "type": "url_verification",
            "challenge": "test_challenge_123"
        }

        event = slack_handler.parse_event(raw_event)

        assert event is not None
        assert event.event_type == "url_verification"
        assert event.event_data["challenge"] == "test_challenge_123"


class TestTeamsWebhookHandler:
    """Test Teams webhook handling"""

    def test_parse_message_event(self, teams_handler):
        """Test parsing Teams message event"""
        raw_event = {
            "type": "#Notification",
            "value": [{
                "@odata.type": "#Microsoft.Graph.chatMessage",
                "id": "1234567890",
                "createdDateTime": "2024-02-01T12:00:00Z",
                "from": {
                    "user": {
                        "displayName": "John Doe",
                        "email": "john@example.com"
                    }
                },
                "body": {
                    "content": "Hello from Teams!",
                    "contentType": "text"
                },
                "chatId": "19:chat_123@thread.v2",
                "messageType": "message"
            }]
        }

        event = teams_handler.parse_event(raw_event)

        assert event is not None
        assert event.platform == "teams"
        assert event.event_type == "message"
        assert event.event_data["content"] == "Hello from Teams!"
        assert event.event_data["sender"] == "John Doe"
        assert event.event_data["sender_email"] == "john@example.com"


class TestGmailWebhookHandler:
    """Test Gmail webhook handling"""

    def test_parse_push_notification(self, gmail_handler):
        """Test parsing Gmail push notification"""
        import base64
        import json

        notification_data = {
            "emailAddress": "me@example.com",
            "historyId": "123456789"
        }

        # Encode as base64 (as Google Pub/Sub does)
        notification_str = json.dumps(notification_data)
        encoded_data = base64.b64encode(notification_str.encode()).decode()

        raw_event = {
            "message": {
                "data": encoded_data,
                "messageId": "msg_123"
            }
        }

        event = gmail_handler.parse_event(raw_event)

        assert event is not None
        assert event.platform == "gmail"
        assert event.event_type == "push_notification"
        assert event.event_data["email_address"] == "me@example.com"
        assert event.event_data["history_id"] == "123456789"


class TestWebhookProcessor:
    """Test webhook event processing"""

    def test_duplicate_detection(self, webhook_processor):
        """Test duplicate event detection"""
        event_id = "test_event_123"

        assert webhook_processor._is_duplicate(event_id) is False

        webhook_processor._mark_processed(event_id)
        assert webhook_processor._is_duplicate(event_id) is True

    def test_mark_processed(self, webhook_processor):
        """Test marking events as processed"""
        event_id = "test_event_456"

        webhook_processor._mark_processed(event_id)

        assert event_id in webhook_processor.processed_events

    def test_register_callback(self, webhook_processor):
        """Test registering message callback"""
        callback = Mock()

        webhook_processor.register_message_callback(callback)

        assert webhook_processor.on_message_received is callback

    @pytest.mark.asyncio
    async def test_process_message_with_callback(self, webhook_processor):
        """Test processing message with registered callback"""
        # Create mock callback
        callback = AsyncMock()
        webhook_processor.register_message_callback(callback)

        # Create event
        event = WebhookEvent(
            platform="slack",
            event_type="message",
            event_data={"content": "Test message"},
            raw_payload={}
        )

        # Process message
        await webhook_processor._process_message(event)

        # Verify callback was called
        callback.assert_called_once()


class TestWebhookEvent:
    """Test WebhookEvent dataclass"""

    def test_webhook_event_creation(self):
        """Test creating a webhook event"""
        event = WebhookEvent(
            platform="slack",
            event_type="message",
            event_data={"content": "Test"},
            raw_payload={},
            timestamp=datetime.now(timezone.utc)
        )

        assert event.platform == "slack"
        assert event.event_type == "message"
        assert event.processed is False

    def test_to_unified_message(self):
        """Test converting webhook event to unified message format"""
        event = WebhookEvent(
            platform="slack",
            event_type="message",
            event_data={"content": "Test message"},
            raw_payload={}
        )

        unified = event.to_unified_message()

        assert unified["app_type"] == "slack"
        assert "raw_event" in unified
        assert unified["event_type"] == "message"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
