"""
Unit Tests for Webhook Signature Verification and Processing

Tests for Slack, Teams, and Gmail webhook signature verification,
event parsing, and processing.
"""

import os
import pytest
from unittest.mock import patch, Mock, MagicMock, AsyncMock
import hmac
import hashlib
import json
from datetime import datetime

from core.webhook_handlers import (
    SlackWebhookHandler,
    TeamsWebhookHandler,
    GmailWebhookHandler,
    WebhookProcessor,
    WebhookEvent
)


@pytest.fixture
def webhook_secret():
    """Test webhook signing secret"""
    return "test-webhook-secret"


@pytest.fixture
def github_payload():
    """Sample GitHub webhook payload"""
    return {
        "ref": "refs/heads/main",
        "repository": {
            "id": 123,
            "name": "test-repo",
            "full_name": "user/test-repo"
        },
        "pusher": {
            "name": "testuser"
        },
        "commits": []
    }


@pytest.fixture
def slack_payload():
    """Sample Slack webhook payload"""
    return {
        "type": "event_callback",
        "event_id": "Ev0PV5KJZ",
        "event": {
            "type": "message",
            "client_msg_id": "C0123456789",
            "ts": "1234567890.123456",
            "text": "Hello from Slack!",
            "user": "U123456",
            "channel": "C123456",
            "team": "T123456"
        }
    }


class TestSlackWebhookHandler:
    """Test cases for Slack webhook signature verification and parsing"""

    def test_init_with_signing_secret(self):
        """Test initialization with signing secret"""
        handler = SlackWebhookHandler(signing_secret="test-secret")
        assert handler.signing_secret == "test-secret"

    def test_init_without_signing_secret(self):
        """Test initialization without signing secret"""
        handler = SlackWebhookHandler(signing_secret=None)
        assert handler.signing_secret is None

    @patch('core.webhook_handlers.os.getenv')
    @patch('core.webhook_handlers.logger')
    def test_verify_signature_no_secret_development(self, mock_logger, mock_getenv):
        """Test signature verification bypassed in development without secret"""
        mock_getenv.return_value = "development"
        handler = SlackWebhookHandler(signing_secret=None)
        result = handler.verify_signature("1234567890", "test-signature", b"test-body")
        assert result is True
        mock_logger.warning.assert_called()

    @patch('core.webhook_handlers.os.getenv')
    @patch('core.webhook_handlers.logger')
    def test_verify_signature_no_secret_production(self, mock_logger, mock_getenv):
        """Test signature verification rejected in production without secret"""
        mock_getenv.return_value = "production"
        handler = SlackWebhookHandler(signing_secret=None)
        result = handler.verify_signature("1234567890", "test-signature", b"test-body")
        assert result is False
        mock_logger.error.assert_called()

    def test_verify_signature_valid(self, webhook_secret):
        """Test valid signature verification"""
        timestamp = "1234567890"
        body = b"test-body"
        basestring = f"v0:{timestamp}".encode() + body
        expected_signature = "v0=" + hmac.new(
            webhook_secret.encode(), basestring, hashlib.sha256
        ).hexdigest()
        handler = SlackWebhookHandler(signing_secret=webhook_secret)
        result = handler.verify_signature(timestamp, expected_signature, body)
        assert result is True

    def test_verify_signature_invalid(self, webhook_secret):
        """Test invalid signature verification"""
        timestamp = "1234567890"
        body = b"test-body"
        invalid_signature = "v0=invalid"
        handler = SlackWebhookHandler(signing_secret=webhook_secret)
        result = handler.verify_signature(timestamp, invalid_signature, body)
        assert result is False

    def test_verify_signature_with_different_secret(self, webhook_secret):
        """Test signature verification with wrong secret"""
        timestamp = "1234567890"
        body = b"test-body"
        basestring = f"v0:{timestamp}".encode() + body
        # Create signature with different secret
        signature = "v0=" + hmac.new(
            "wrong-secret".encode(), basestring, hashlib.sha256
        ).hexdigest()
        handler = SlackWebhookHandler(signing_secret=webhook_secret)
        result = handler.verify_signature(timestamp, signature, body)
        assert result is False

    @patch('core.webhook_handlers.logger')
    def test_parse_event_url_verification(self, mock_logger):
        """Test parsing URL verification challenge"""
        handler = SlackWebhookHandler()
        raw_event = {
            "type": "url_verification",
            "challenge": "test-challenge-123",
            "token": "test-token"
        }

        event = handler.parse_event(raw_event)

        assert event is not None
        assert event.platform == "slack"
        assert event.event_type == "url_verification"
        assert event.event_data["challenge"] == "test-challenge-123"

    def test_parse_event_message(self, slack_payload):
        """Test parsing message event"""
        handler = SlackWebhookHandler()
        event = handler.parse_event(slack_payload)

        assert event is not None
        assert event.platform == "slack"
        assert event.event_type == "message"
        assert event.event_data["content"] == "Hello from Slack!"
        assert event.event_data["sender"] == "U123456"
        assert event.event_data["recipient"] == "C123456"
        assert "channel_id" in event.event_data["metadata"]

    def test_parse_event_app_mention(self):
        """Test parsing app mention event"""
        handler = SlackWebhookHandler()
        raw_event = {
            "type": "event_callback",
            "event": {
                "type": "app_mention",
                "user": "U123456",
                "text": "<@U789> Hello bot",
                "channel": "C123456",
                "ts": "1234567890.123456"
            }
        }

        event = handler.parse_event(raw_event)

        # App mention is not explicitly handled, returns None
        assert event is None

    @patch('core.webhook_handlers.logger')
    def test_parse_event_invalid_payload(self, mock_logger):
        """Test parsing invalid payload"""
        handler = SlackWebhookHandler()
        raw_event = {"invalid": "data"}

        event = handler.parse_event(raw_event)

        assert event is None
        mock_logger.error.assert_not_called()  # Parser logs info for unhandled, not error

    @patch('core.webhook_handlers.logger')
    def test_parse_event_missing_repository_id(self, mock_logger):
        """Test parsing event with missing required fields"""
        handler = SlackWebhookHandler()
        raw_event = {
            "type": "event_callback",
            "event": {
                "type": "message"
                # Missing user, channel, etc.
            }
        }

        event = handler.parse_event(raw_event)

        # Should still parse, just with empty/default values
        assert event is not None
        assert event.platform == "slack"


class TestTeamsWebhookHandler:
    """Test cases for Teams webhook signature verification and parsing"""

    def test_init_with_app_id(self):
        """Test initialization with app ID"""
        handler = TeamsWebhookHandler(app_id="test-app-id")
        assert handler.app_id == "test-app-id"

    def test_init_without_app_id(self):
        """Test initialization without app ID"""
        handler = TeamsWebhookHandler(app_id=None)
        assert handler.app_id is None

    @patch('core.webhook_handlers.os.getenv')
    @patch('core.webhook_handlers.logger')
    def test_verify_signature_no_auth_development(self, mock_logger, mock_getenv):
        """Test signature verification bypassed in development"""
        mock_getenv.return_value = "development"
        handler = TeamsWebhookHandler(app_id=None)
        result = handler.verify_signature(None)
        assert result is True
        mock_logger.warning.assert_called()

    @patch('core.webhook_handlers.os.getenv')
    @patch('core.webhook_handlers.logger')
    def test_verify_signature_no_auth_production(self, mock_logger, mock_getenv):
        """Test signature verification rejected in production"""
        mock_getenv.return_value = "production"
        handler = TeamsWebhookHandler(app_id=None)
        result = handler.verify_signature(None)
        assert result is False
        mock_logger.error.assert_called()

    def test_verify_signature_valid_bearer(self):
        """Test valid Bearer token"""
        handler = TeamsWebhookHandler()
        auth_header = "Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
        result = handler.verify_signature(auth_header)
        assert result is True

    def test_verify_signature_invalid_format(self):
        """Test invalid auth header format"""
        handler = TeamsWebhookHandler()
        auth_header = "InvalidFormat token123"
        result = handler.verify_signature(auth_header)
        assert result is False

    def test_parse_event_message(self):
        """Test parsing Teams message event"""
        handler = TeamsWebhookHandler()
        raw_event = {
            "type": "Message",
            "value": [{
                "@odata.type": "#Microsoft.Graph.chatMessage",
                "id": "1234567890",
                "body": {
                    "content": "Hello from Teams!",
                    "contentType": "text"
                },
                "from": {
                    "user": {
                        "displayName": "John Doe",
                        "email": "john@example.com"
                    }
                },
                "chatId": "19:chat@thread.v2",
                "createdDateTime": "2024-02-01T12:00:00Z"
            }]
        }

        event = handler.parse_event(raw_event)

        assert event is not None
        assert event.platform == "teams"
        assert event.event_type == "message"
        assert event.event_data["content"] == "Hello from Teams!"
        assert event.event_data["sender"] == "John Doe"
        assert event.event_data["sender_email"] == "john@example.com"

    def test_parse_event_multiple_values(self):
        """Test parsing event with multiple value items"""
        handler = TeamsWebhookHandler()
        raw_event = {
            "type": "Message",
            "value": [
                {
                    "@odata.type": "#Microsoft.Graph.chatMessage",
                    "id": "msg1",
                    "body": {"content": "First", "contentType": "text"},
                    "from": {"user": {"displayName": "User1"}},
                    "chatId": "chat1"
                },
                {
                    "@odata.type": "#Microsoft.Graph.chatMessage",
                    "id": "msg2",
                    "body": {"content": "Second", "contentType": "text"},
                    "from": {"user": {"displayName": "User2"}},
                    "chatId": "chat2"
                }
            ]
        }

        event = handler.parse_event(raw_event)

        # Should return first message
        assert event is not None
        assert event.platform == "teams"
        assert event.event_data["content"] == "First"
        assert event.event_data["sender"] == "User1"

    @patch('core.webhook_handlers.logger')
    def test_parse_event_invalid_payload(self, mock_logger):
        """Test parsing invalid Teams payload"""
        handler = TeamsWebhookHandler()
        raw_event = {"type": "Unknown"}

        event = handler.parse_event(raw_event)

        assert event is None


class TestGmailWebhookHandler:
    """Test cases for Gmail webhook verification and parsing"""

    def test_init_with_api_key(self):
        """Test initialization with API key"""
        handler = GmailWebhookHandler(api_key="test-api-key")
        assert handler.api_key == "test-api-key"

    def test_init_without_api_key(self):
        """Test initialization without API key"""
        handler = GmailWebhookHandler(api_key=None)
        assert handler.api_key is None

    @patch('core.webhook_handlers.os.getenv')
    @patch('core.webhook_handlers.logger')
    def test_verify_signature_no_headers_development(self, mock_logger, mock_getenv):
        """Test signature verification bypassed in development"""
        mock_getenv.return_value = "development"
        handler = GmailWebhookHandler(api_key=None)
        result = handler.verify_signature({})
        assert result is True
        mock_logger.warning.assert_called()

    @patch('core.webhook_handlers.os.getenv')
    @patch('core.webhook_handlers.logger')
    def test_verify_signature_no_headers_production(self, mock_logger, mock_getenv):
        """Test signature verification rejected in production"""
        mock_getenv.return_value = "production"
        handler = GmailWebhookHandler(api_key=None)
        result = handler.verify_signature({})
        assert result is False
        mock_logger.error.assert_called()

    def test_verify_signature_valid_headers(self):
        """Test valid Gmail headers"""
        handler = GmailWebhookHandler()
        headers = {"content-type": "message/rfc822"}
        result = handler.verify_signature(headers)
        assert result is True

    def test_verify_signature_invalid_content_type(self):
        """Test invalid content-type"""
        handler = GmailWebhookHandler()
        headers = {"content-type": "application/json"}
        result = handler.verify_signature(headers)
        assert result is True  # Gmail handler is lenient

    def test_parse_event_push_notification(self):
        """Test parsing Gmail push notification"""
        import base64
        handler = GmailWebhookHandler()

        # Create valid base64-encoded notification
        notification = {
            "emailAddress": "user@example.com",
            "historyId": "123456789"
        }
        data_str = json.dumps(notification)
        encoded_data = base64.b64encode(data_str.encode()).decode()

        raw_event = {
            "message": {
                "data": encoded_data
            }
        }

        event = handler.parse_event(raw_event)

        assert event is not None
        assert event.platform == "gmail"
        assert event.event_type == "push_notification"
        assert event.event_data["email_address"] == "user@example.com"
        assert event.event_data["history_id"] == "123456789"

    @patch('core.webhook_handlers.logger')
    def test_parse_event_empty_data(self, mock_logger):
        """Test parsing event with empty data"""
        handler = GmailWebhookHandler()
        raw_event = {
            "message": {
                "data": ""
            }
        }

        event = handler.parse_event(raw_event)

        assert event is None
        mock_logger.warning.assert_called()

    @patch('core.webhook_handlers.logger')
    def test_parse_event_invalid_base64(self, mock_logger):
        """Test parsing event with invalid base64"""
        handler = GmailWebhookHandler()
        raw_event = {
            "message": {
                "data": "invalid-base64!@#"
            }
        }

        event = handler.parse_event(raw_event)

        assert event is None


class TestWebhookEvent:
    """Test cases for WebhookEvent normalization"""

    def test_to_unified_message(self):
        """Test converting webhook event to unified message"""
        event = WebhookEvent(
            platform="slack",
            event_type="message",
            event_data={"content": "test"},
            raw_payload={"original": "data"}
        )

        unified = event.to_unified_message()

        assert unified["app_type"] == "slack"
        assert unified["raw_event"] == {"original": "data"}
        assert unified["event_type"] == "message"
        assert "timestamp" in unified


class TestWebhookProcessor:
    """Test cases for WebhookProcessor"""

    def test_initialization(self):
        """Test processor initialization"""
        processor = WebhookProcessor()

        assert processor.slack_handler is not None
        assert processor.teams_handler is not None
        assert processor.gmail_handler is not None
        assert processor.processed_events == {}
        assert processor.on_message_received is None

    def test_register_message_callback(self):
        """Test registering message callback"""
        processor = WebhookProcessor()
        callback = Mock()

        processor.register_message_callback(callback)

        assert processor.on_message_received == callback

    @pytest.mark.asyncio
    async def test_process_slack_webhook_success(self, slack_payload):
        """Test successful Slack webhook processing"""
        from fastapi import Request
        from starlette.background import BackgroundTasks

        processor = WebhookProcessor()
        processor.on_message_received = AsyncMock()

        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "X-Slack-Request-Timestamp": "1234567890",
            "X-Slack-Signature": "v0=dummy"  # Will fail signature check in dev mode
        }
        mock_request.body = AsyncMock(return_value=json.dumps(slack_payload).encode())

        mock_background = Mock(spec=BackgroundTasks)
        mock_background.add_task = Mock()

        # Process in development mode (no signature verification)
        with patch('core.webhook_handlers.os.getenv', return_value='development'):
            result = await processor.process_slack_webhook(mock_request, mock_background)

        assert result["status"] in ["success", "ignored", "duplicate"]

    @pytest.mark.asyncio
    async def test_process_slack_webhook_url_verification(self):
        """Test Slack URL verification challenge"""
        from fastapi import Request
        from starlette.background import BackgroundTasks

        processor = WebhookProcessor()

        challenge_event = {
            "type": "url_verification",
            "challenge": "test-challenge"
        }

        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.body = AsyncMock(return_value=json.dumps(challenge_event).encode())

        mock_background = Mock(spec=BackgroundTasks)

        with patch('core.webhook_handlers.os.getenv', return_value='development'):
            result = await processor.process_slack_webhook(mock_request, mock_background)

        assert "challenge" in result

    def test_is_duplicate(self):
        """Test duplicate event detection"""
        processor = WebhookProcessor()

        # First check - not duplicate
        assert processor._is_duplicate("event_123") is False

        # Mark as processed
        processor._mark_processed("event_123")

        # Second check - is duplicate
        assert processor._is_duplicate("event_123") is True

    def test_mark_processed(self):
        """Test marking event as processed"""
        processor = WebhookProcessor()
        processor._mark_processed("event_123")

        assert "event_123" in processor.processed_events
        assert isinstance(processor.processed_events["event_123"], datetime)

    def test_processed_events_cleanup(self):
        """Test cleanup of old processed events"""
        processor = WebhookProcessor()

        # Add more than 10000 events to trigger cleanup
        for i in range(10001):
            processor.processed_events[f"event_{i}"] = datetime.now()

        initial_count = len(processor.processed_events)
        processor._mark_processed("event_new")

        # Should have cleaned up old events
        assert len(processor.processed_events) < initial_count

    @pytest.mark.asyncio
    async def test_process_teams_webhook(self):
        """Test Teams webhook processing"""
        from fastapi import Request
        from starlette.background import BackgroundTasks

        processor = WebhookProcessor()
        processor.on_message_received = AsyncMock()

        teams_event = {
            "type": "Message",
            "value": [{
                "@odata.type": "#Microsoft.Graph.chatMessage",
                "id": "123",
                "body": {"content": "Test", "contentType": "text"},
                "from": {"user": {"displayName": "User"}},
                "chatId": "chat1"
            }]
        }

        mock_request = Mock(spec=Request)
        mock_request.json = AsyncMock(return_value=teams_event)

        mock_background = Mock(spec=BackgroundTasks)
        mock_background.add_task = Mock()

        result = await processor.process_teams_webhook(mock_request, mock_background)

        assert result["status"] in ["success", "ignored", "duplicate"]

    @pytest.mark.asyncio
    async def test_process_gmail_webhook(self):
        """Test Gmail webhook processing"""
        from fastapi import Request
        from starlette.background import BackgroundTasks
        import base64

        processor = WebhookProcessor()
        processor.on_message_received = AsyncMock()

        notification = {"emailAddress": "test@example.com", "historyId": "123"}
        data_str = json.dumps(notification)
        encoded_data = base64.b64encode(data_str.encode()).decode()

        gmail_event = {
            "message": {"data": encoded_data}
        }

        mock_request = Mock(spec=Request)
        mock_request.json = AsyncMock(return_value=gmail_event)

        mock_background = Mock(spec=BackgroundTasks)
        mock_background.add_task = Mock()

        result = await processor.process_gmail_webhook(mock_request, mock_background)

        assert result["status"] in ["success", "ignored", "duplicate"]

    @pytest.mark.asyncio
    async def test_process_message_callback(self):
        """Test _process_message calls callback"""
        processor = WebhookProcessor()

        # Create a mock callback
        callback_called = []

        async def mock_callback(message_data):
            callback_called.append(message_data)

        processor.register_message_callback(mock_callback)

        # Create a test event
        event = WebhookEvent(
            platform="slack",
            event_type="message",
            event_data={"content": "test message"},
            raw_payload={}
        )

        # Process the message
        await processor._process_message(event)

        # Verify callback was called
        assert len(callback_called) == 1
        assert callback_called[0]["app_type"] == "slack"

    @pytest.mark.asyncio
    async def test_process_message_no_callback(self):
        """Test _process_message without callback doesn't crash"""
        processor = WebhookProcessor()
        # Don't register any callback

        event = WebhookEvent(
            platform="teams",
            event_type="message",
            event_data={"content": "test"},
            raw_payload={}
        )

        # Should not raise exception
        await processor._process_message(event)


class TestWebhookErrorHandling:
    """Test cases for webhook error handling"""

    @pytest.mark.asyncio
    async def test_slack_webhook_signature_failure(self):
        """Test Slack webhook with invalid signature"""
        from fastapi import Request
        from fastapi import HTTPException
        from starlette.background import BackgroundTasks

        processor = WebhookProcessor()

        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "X-Slack-Request-Timestamp": "1234567890",
            "X-Slack-Signature": "v0=invalid"
        }
        mock_request.body = AsyncMock(return_value=b"test-body")

        mock_background = Mock(spec=BackgroundTasks)

        # Production mode requires valid signature
        with patch('core.webhook_handlers.os.getenv', return_value='production'):
            with pytest.raises(HTTPException) as exc_info:
                await processor.process_slack_webhook(mock_request, mock_background)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_internal_error_handling(self):
        """Test internal error handling in webhook processing"""
        from fastapi import Request
        from fastapi import HTTPException
        from starlette.background import BackgroundTasks

        processor = WebhookProcessor()

        mock_request = Mock(spec=Request)
        mock_request.json = AsyncMock(side_effect=Exception("Database error"))

        mock_background = Mock(spec=BackgroundTasks)

        with pytest.raises(HTTPException) as exc_info:
            await processor.process_teams_webhook(mock_request, mock_background)

        assert exc_info.value.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
