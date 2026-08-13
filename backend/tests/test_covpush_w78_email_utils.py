# -*- coding: utf-8 -*-
"""Coverage wave 78 — core/email_utils (SMTP send + validators). No network —
smtplib.SMTP fully mocked.

Bug-driven TDD (wave 78):
- RED: validate_email accepted "user@example.com\n" (regex `$` matches before a
  final newline) — a header-injection-adjacent false-accept. Fixed with
  re.fullmatch anchoring.
- RED: send_smtp_email accepted CR/LF in `subject` (and unvalidated `to_email`),
  allowing SMTP header injection (e.g. subject "hi\nBcc: attacker@evil.com").
  Fixed: newline subject → refused (fail-closed), invalid recipient → refused.

Coverage:
- send_smtp_email: unconfigured env (mock email to logs), configured success
  with/without html_body, SMTP exception → False, injected subject → False,
  invalid recipient → False.
- validate_email / validate_email_strict: valid, invalid, empty, non-string,
  trailing-newline rejection, exactly-one-@ errors, missing local/domain/extension.
- validate_email_with_plus_addressing: plus-tag accepted, invalid rejected.
- validate_url / validate_url_with_params: scheme checks, ports, paths, queries,
  fragments, unicode rejection, error branches.
- validate_url_secure: https ok, http rejected, empty rejected.
- validate_phone / validate_phone_international: formatting variants, + prefix,
  length bounds.
- validate_uuid / validate_uuid_any_version: v4 variant bits, any version.
- validate_boolean / parse_boolean: all truthy/falsy tokens + invalid.
- validate_integer / validate_float: range bounds, ValueError branches.
- validate_json: valid/invalid/non-string.
"""
import json
import os
import re
import smtplib
from unittest.mock import MagicMock, patch

import pytest

import core.email_utils as eu
from core.email_utils import (
    parse_boolean,
    send_smtp_email,
    validate_boolean,
    validate_email,
    validate_email_strict,
    validate_email_with_plus_addressing,
    validate_float,
    validate_integer,
    validate_json,
    validate_phone,
    validate_phone_international,
    validate_url,
    validate_url_secure,
    validate_url_with_params,
    validate_uuid,
    validate_uuid_any_version,
)


class TestSendSmtpEmail:
    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        for var in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"]:
            monkeypatch.delenv(var, raising=False)

    def test_unconfigured_logs_mock_email_and_returns_true(self, caplog):
        assert send_smtp_email("a@b.com", "Subject", "Body") is True
        assert "MOCK EMAIL START" in caplog.text
        assert "Subject: Subject" in caplog.text
        assert "Body: Body" in caplog.text

    def test_unconfigured_with_html(self, caplog):
        assert send_smtp_email("a@b.com", "S", "B", html_body="<b>B</b>") is True
        assert "MOCK EMAIL START" in caplog.text

    def test_configured_success_with_html(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        with patch.object(eu.smtplib, "SMTP", return_value=smtp):
            assert send_smtp_email(
                "to@example.com", "Hello", "plain body", html_body="<p>html</p>"
            ) is True
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("user@example.com", "secret")
        sent = smtp.send_message.call_args.args[0]
        assert sent["To"] == "to@example.com"
        assert sent["Subject"] == "Hello"
        payloads = [part.get_payload() for part in sent.walk() if part.get_content_type() == "text/plain"]
        assert "plain body" in payloads
        assert "text/html" in str(sent)

    def test_configured_success_without_html(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "25")
        monkeypatch.setenv("SMTP_USER", "u")
        monkeypatch.setenv("SMTP_PASSWORD", "p")
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        with patch.object(eu.smtplib, "SMTP", return_value=smtp):
            assert send_smtp_email("to@example.com", "Hello", "plain body") is True
        sent = smtp.send_message.call_args.args[0]
        assert "text/html" not in str(sent)

    def test_smtp_exception_returns_false(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "u")
        monkeypatch.setenv("SMTP_PASSWORD", "p")
        with patch.object(eu.smtplib, "SMTP", side_effect=smtplib.SMTPConnectError(1, "down")):
            assert send_smtp_email("to@example.com", "Hi", "Body") is False

    def test_refuses_subject_with_newline_injection(self, monkeypatch):
        """RED (wave 78): subject containing CR/LF was previously sent verbatim,
        enabling SMTP header injection (CWE-93). Must fail closed."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "u")
        monkeypatch.setenv("SMTP_PASSWORD", "p")
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        with patch.object(eu.smtplib, "SMTP", return_value=smtp):
            result = send_smtp_email(
                "victim@example.com",
                "Legit\nBcc: attacker@evil.com",
                "Body",
            )
        assert result is False
        smtp.send_message.assert_not_called()

    def test_refuses_subject_with_carriage_return_injection(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "u")
        monkeypatch.setenv("SMTP_PASSWORD", "p")
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        with patch.object(eu.smtplib, "SMTP", return_value=smtp):
            assert send_smtp_email("victim@example.com", "A\rB", "Body") is False
        smtp.send_message.assert_not_called()

    def test_refuses_invalid_recipient(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "u")
        monkeypatch.setenv("SMTP_PASSWORD", "p")
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        with patch.object(eu.smtplib, "SMTP", return_value=smtp):
            assert send_smtp_email("not-an-email", "Hi", "Body") is False
        smtp.send_message.assert_not_called()

    def test_refuses_recipient_with_newline(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "u")
        monkeypatch.setenv("SMTP_PASSWORD", "p")
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        with patch.object(eu.smtplib, "SMTP", return_value=smtp):
            assert send_smtp_email("victim@example.com\nX-Evil: 1", "Hi", "Body") is False
        smtp.send_message.assert_not_called()


class TestValidateEmail:
    def test_valid(self):
        assert validate_email("user@example.com") is True

    def test_valid_with_plus_and_dots(self):
        assert validate_email("first.last+tag@sub.example.co") is True

    def test_invalid(self):
        assert validate_email("invalid") is False
        assert validate_email("user@") is False
        assert validate_email("@example.com") is False
        assert validate_email("user@example") is False

    def test_empty_or_non_string(self):
        assert validate_email("") is False
        assert validate_email(None) is False
        assert validate_email(123) is False

    def test_trailing_newline_rejected(self):
        """RED (wave 78): regex `$` matched before a final newline, so
        'user@example.com\\n' validated True — an SMTP header-injection footgun."""
        assert validate_email("user@example.com\n") is False

    def test_embedded_newline_rejected(self):
        assert validate_email("user@example.com\nBcc: x@y.com") is False


class TestValidateEmailStrict:
    def test_valid_returns_none_error(self):
        ok, err = validate_email_strict("user@example.com")
        assert ok is True
        assert err is None

    def test_non_string(self):
        assert validate_email_strict(123) == (False, "Email must be a string")

    def test_empty(self):
        assert validate_email_strict("") == (False, "Email is required")

    def test_no_at_symbol(self):
        assert validate_email_strict("nope")[0] is False
        assert "@" in validate_email_strict("nope")[1]

    def test_multiple_at_symbols(self):
        ok, err = validate_email_strict("a@b@c.com")
        assert ok is False
        assert "exactly one @" in err

    def test_missing_local_part(self):
        assert validate_email_strict("@domain.com") == (
            False,
            "Email must have username before @",
        )

    def test_missing_domain(self):
        assert validate_email_strict("user@") == (False, "Email must have domain after @")

    def test_missing_domain_extension(self):
        assert validate_email_strict("user@example") == (
            False,
            "Email domain must contain extension",
        )

    def test_invalid_format(self):
        ok, err = validate_email_strict("user@exa mple.com")
        assert ok is False
        assert err == "Invalid email format"

    def test_trailing_newline_rejected(self):
        ok, _ = validate_email_strict("user@example.com\n")
        assert ok is False


class TestValidateEmailWithPlusAddressing:
    def test_plus_tag_accepted(self):
        assert validate_email_with_plus_addressing("user+tag@example.com") is True

    def test_plain_accepted(self):
        assert validate_email_with_plus_addressing("user@example.com") is True

    def test_invalid(self):
        assert validate_email_with_plus_addressing("not-an-email") is False
        assert validate_email_with_plus_addressing("") is False
        assert validate_email_with_plus_addressing(None) is False


class TestValidateUrl:
    def test_valid_schemes(self):
        assert validate_url("https://example.com") is True
        assert validate_url("http://example.com") is True
        assert validate_url("ftp://example.com") is True

    def test_with_port_path_query_fragment(self):
        assert validate_url("https://example.com:8443/path/to?q=1#frag") is True

    def test_invalid(self):
        assert validate_url("example.com") is False
        assert validate_url("https://") is False
        assert validate_url("") is False
        assert validate_url(None) is False
        assert validate_url(42) is False


class TestValidateUrlWithParams:
    def test_valid(self):
        ok, err = validate_url_with_params("https://example.com?foo=bar")
        assert ok is True
        assert err is None

    def test_non_string(self):
        assert validate_url_with_params(42) == (False, "URL must be a string")

    def test_empty(self):
        assert validate_url_with_params("") == (False, "URL is required")

    def test_bad_scheme(self):
        ok, err = validate_url_with_params("example.com")
        assert ok is False
        assert "must start with" in err

    def test_invalid_format(self):
        ok, err = validate_url_with_params("https://")
        assert ok is False
        assert err == "Invalid URL format"


class TestValidateUrlSecure:
    def test_https_accepted(self):
        assert validate_url_secure("https://example.com") is True

    def test_http_rejected(self):
        assert validate_url_secure("http://example.com") is False

    def test_empty_rejected(self):
        assert validate_url_secure("") is False
        assert validate_url_secure(None) is False


class TestValidatePhone:
    def test_various_formats(self):
        assert validate_phone("1234567890") is True
        assert validate_phone("(123) 456-7890") is True
        assert validate_phone("+1 (123) 456-7890") is True  # 11 digits

    def test_invalid(self):
        assert validate_phone("123") is False
        assert validate_phone("123456789012") is False
        assert validate_phone("") is False
        assert validate_phone(None) is False


class TestValidatePhoneInternational:
    def test_plus_prefix(self):
        assert validate_phone_international("+11234567890") is True
        assert validate_phone_international("+44 20 7123 4567") is True

    def test_no_plus_us_format(self):
        assert validate_phone_international("1234567890") is True

    def test_length_bounds(self):
        assert validate_phone_international("+1") is False
        assert validate_phone_international("+1234567890123456") is False

    def test_invalid(self):
        assert validate_phone_international("") is False
        assert validate_phone_international(None) is False


class TestValidateUuid:
    def test_valid_v4(self):
        assert validate_uuid("123e4567-e89b-42d3-a456-426614174000") is True

    def test_uppercase_accepted(self):
        assert validate_uuid("123E4567-E89B-42D3-A456-426614174000") is True

    def test_non_v4_rejected(self):
        assert validate_uuid("123e4567-e89b-12d3-a456-426614174000") is False

    def test_invalid(self):
        assert validate_uuid("invalid") is False
        assert validate_uuid("") is False
        assert validate_uuid(None) is False


class TestValidateUuidAnyVersion:
    def test_any_version_accepted(self):
        assert validate_uuid_any_version("123e4567-e89b-12d3-a456-426614174000") is True
        assert validate_uuid_any_version("123e4567-e89b-42d3-a456-426614174000") is True

    def test_invalid(self):
        assert validate_uuid_any_version("garbage") is False
        assert validate_uuid_any_version("") is False
        assert validate_uuid_any_version(None) is False
        assert validate_uuid_any_version("123e4567-e89b-12d3-a456") is False


class TestValidateBoolean:
    def test_true_tokens(self):
        for token in ["true", "TRUE", "1", "yes"]:
            assert validate_boolean(token) is True

    def test_false_tokens(self):
        for token in ["false", "0", "no"]:
            assert validate_boolean(token) is True

    def test_invalid(self):
        assert validate_boolean("maybe") is False
        assert validate_boolean(1) is False
        assert validate_boolean(None) is False


class TestParseBoolean:
    def test_true_values(self):
        assert parse_boolean("true") is True
        assert parse_boolean("1") is True
        assert parse_boolean("YES") is True

    def test_false_values(self):
        assert parse_boolean("false") is False
        assert parse_boolean("0") is False
        assert parse_boolean("no") is False

    def test_invalid(self):
        assert parse_boolean("maybe") is None
        assert parse_boolean(1) is None
        assert parse_boolean(None) is None


class TestValidateInteger:
    def test_basic(self):
        assert validate_integer("123") is True

    def test_range_ok(self):
        assert validate_integer("150", min_val=0, max_val=200) is True

    def test_below_min(self):
        assert validate_integer("5", min_val=10) is False

    def test_above_max(self):
        assert validate_integer("500", max_val=100) is False

    def test_not_int(self):
        assert validate_integer("abc") is False
        assert validate_integer("1.5") is False
        assert validate_integer(5) is False


class TestValidateFloat:
    def test_basic(self):
        assert validate_float("123.45") is True

    def test_range_ok(self):
        assert validate_float("1.5", min_val=0.0, max_val=2.0) is True

    def test_below_min(self):
        assert validate_float("-1.0", min_val=0.0) is False

    def test_above_max(self):
        assert validate_float("3.0", max_val=2.5) is False

    def test_not_float(self):
        assert validate_float("abc") is False
        assert validate_float(1.5) is False


class TestValidateJson:
    def test_valid(self):
        assert validate_json('{"key": "value"}') is True

    def test_invalid(self):
        assert validate_json("invalid") is False

    def test_non_string(self):
        assert validate_json({"key": "value"}) is False
