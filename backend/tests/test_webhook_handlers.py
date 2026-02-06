"""
Unit Tests for Webhook Signature Verification

Tests for Slack, Teams, and Gmail webhook signature verification.
"""

import os
import pytest
from unittest.mock import patch, Mock
import hmac
import hashlib

from core.webhook_handlers import (
    SlackWebhookHandler,
    TeamsWebhookHandler,
    GmailWebhookHandler,
    WebhookProcessor,
    WebhookEvent
)


class TestSlackWebhookHandler:
    """Test cases for Slack webhook signature verification"""

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
        assert mock_logger.warning.called

    @patch('core.webhook_handlers.os.getenv')
    @patch('core.webhook_handlers.logger')
    def test_verify_signature_no_secret_production(self, mock_logger, mock_getenv):
        """Test signature verification rejected in production without secret"""
        mock_getenv.return_value = "production"
        handler = SlackWebhookHandler(signing_secret=None)
        result = handler.verify_signature("1234567890", "test-signature", b"test-body")
        assert result is False
        assert mock_logger.error.called

    def test_verify_signature_valid(self):
        """Test valid signature verification"""
        secret = "test-secret"
        timestamp = "1234567890"
        body = b"test-body"
        basestring = f"v0:{timestamp}".encode() + body
        expected_signature = "v0=" + hmac.new(
            secret.encode(), basestring, hashlib.sha256
        ).hexdigest()
        handler = SlackWebhookHandler(signing_secret=secret)
        result = handler.verify_signature(timestamp, expected_signature, body)
        assert result is True

    def test_verify_signature_invalid(self):
        """Test invalid signature verification"""
        secret = "test-secret"
        timestamp = "1234567890"
        body = b"test-body"
        invalid_signature = "v0=invalid"
        handler = SlackWebhookHandler(signing_secret=secret)
        result = handler.verify_signature(timestamp, invalid_signature, body)
        assert result is False


