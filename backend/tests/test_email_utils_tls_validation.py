"""Targeted TLS verification tests for core.email_utils.send_smtp_email.

No network: SMTP is mocked. These assert the real Python ssl default context
is passed to STARTTLS, and that certificate/hostname failures fail closed
before authentication or message send, with no retry/fallback.
"""
import smtplib
import ssl
from unittest.mock import MagicMock, patch

import pytest

import core.email_utils as eu


@pytest.fixture()
def configured(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    with patch.object(eu.smtplib, "SMTP", return_value=smtp) as factory:
        yield factory, smtp


def test_starttls_receives_real_default_context(configured):
    factory, smtp = configured
    assert eu.send_smtp_email("to@example.com", "Hello", "Body") is True
    smtp.starttls.assert_called_once()
    context = smtp.starttls.call_args.kwargs["context"]
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_chain_or_hostname_failure_stops_before_login_and_send(configured):
    factory, smtp = configured
    smtp.starttls.side_effect = ssl.SSLCertVerificationError(
        "certificate verify failed")
    assert eu.send_smtp_email("to@example.com", "Hello", "Body") is False
    smtp.starttls.assert_called_once()
    smtp.login.assert_not_called()
    smtp.send_message.assert_not_called()
    factory.assert_called_once()


def test_secure_success_authenticates_and_sends_exactly_once(configured):
    factory, smtp = configured
    assert eu.send_smtp_email("to@example.com", "Hello", "Body") is True
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("user@example.com", "secret")
    smtp.send_message.assert_called_once()
    factory.assert_called_once()


def test_tls_refusal_has_no_retry_or_plaintext_fallback(configured):
    factory, smtp = configured
    smtp.starttls.side_effect = ssl.SSLCertVerificationError(
        "hostname mismatch")
    assert eu.send_smtp_email("to@example.com", "Hello", "Body") is False
    assert factory.call_count == 1
    assert smtp.starttls.call_count == 1
    smtp.login.assert_not_called()
    smtp.send_message.assert_not_called()
