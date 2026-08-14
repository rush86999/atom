"""
Tests for Slack webhook HMAC signature verification (core/webhook_handlers.py).

SlackWebhookHandler was instantiated with no signing secret and never read
SLACK_SIGNING_SECRET from env, so self.signing_secret was permanently None.
In non-production environments verify_signature returned True unconditionally,
accepting every forged webhook. These tests confirm the secret is loaded from
env and that a forged signature is rejected when a secret is configured.
"""

import hashlib
import hmac
import pytest

from core.webhook_handlers import SlackWebhookHandler


class TestSlackWebhookHmac:
    def test_loads_signing_secret_from_env(self, monkeypatch):
        """The handler MUST read SLACK_SIGNING_SECRET from env so a configured
        secret is actually used (previously hardcoded to None)."""
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret-8a3f")
        handler = SlackWebhookHandler()
        assert handler.signing_secret == "test-secret-8a3f", (
            "SlackWebhookHandler must load SLACK_SIGNING_SECRET from env"
        )

    def test_rejects_forged_signature_when_secret_configured(self, monkeypatch):
        """A bad signature MUST be rejected when a secret is configured."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        handler = SlackWebhookHandler(signing_secret="my-secret")
        body = b'{"type":"event_callback"}'
        result = handler.verify_signature("1234567890", "v0=forgedbadbignature", body)
        assert result is False, "Forged signature was accepted"

    def test_accepts_valid_signature_when_secret_configured(self, monkeypatch):
        """A correctly-computed signature MUST be accepted.

        Slack's spec signs ``v0:{timestamp}:{body}`` — the colon between
        timestamp and body is load-bearing (W85C fixed a bug where the handler
        omitted it and rejected every legitimate webhook).
        """
        monkeypatch.setenv("ENVIRONMENT", "development")
        secret = "my-secret"
        handler = SlackWebhookHandler(signing_secret=secret)
        timestamp = "1234567890"
        body = b'{"type":"event_callback"}'
        basestring = f"v0:{timestamp}:".encode() + body
        valid_sig = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
        result = handler.verify_signature(timestamp, valid_sig, body)
        assert result is True

    def test_does_not_bypass_in_dev_when_secret_configured(self, monkeypatch):
        """Even in development, if a secret IS configured, verification must
        actually run (not bypass). The bypass is only for the no-secret case."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        handler = SlackWebhookHandler(signing_secret="configured-secret")
        # A forged signature must still be rejected even in dev mode now that
        # a secret is present.
        result = handler.verify_signature("123", "v0=bad", b"{}")
        assert result is False
