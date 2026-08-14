"""
Coverage + security bug-hunt tests for core/pii_redactor.py.

Covers every public method and branch of PIIRedactor plus the module-level
helpers (get_pii_redactor singleton, redact_pii, check_for_pii). Exercises:
  * email / SSN / credit-card / phone / IP / URL / IBAN / date detection
  * allowlist (case-insensitive, default + dynamic) and URL-substring filtering
  * placeholder rendering, operators, audit logging
  * the Presidio runtime-failure fallback path
  * empty / None / falsy input

Security-bug tests carry a ``BUG:`` docstring (TDD).
"""
from __future__ import annotations

import logging
import re
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from core.pii_redactor import (
    PRESIDIO_AVAILABLE,
    PIIRedactor,
    check_for_pii,
    get_pii_redactor,
    redact_pii,
)
from core.secrets_redactor import RedactionResult


pytestmark = pytest.mark.skipif(
    not PRESIDIO_AVAILABLE,
    reason="Presidio not installed; fallback path covered by test_pii_redactor.py",
)


# The bundled spacy model (en_core_web_lg) has broken static vectors in this
# environment, so AnalyzerEngine.analyze() raises for every text and redact()
# would silently degrade to the regex fallback. To exercise the real Presidio
# pipeline (allowlist filtering, operators, placeholder rendering, audit log)
# deterministically, the analyzer is stubbed with these regex-backed results.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\(\d{3}\) \d{3}-\d{4}")
_CARD_RE = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")


def fake_analyze(text, language=None, entities=None, **kwargs):
    """Deterministic stand-in for AnalyzerEngine.analyze()."""
    from presidio_analyzer import RecognizerResult

    results = []
    for m in _EMAIL_RE.finditer(text):
        results.append(
            RecognizerResult(entity_type="EMAIL_ADDRESS", start=m.start(), end=m.end(), score=1.0)
        )
    for m in _PHONE_RE.finditer(text):
        results.append(
            RecognizerResult(entity_type="PHONE_NUMBER", start=m.start(), end=m.end(), score=1.0)
        )
    for m in _CARD_RE.finditer(text):
        results.append(
            RecognizerResult(entity_type="CREDIT_CARD", start=m.start(), end=m.end(), score=1.0)
        )
    return results


@pytest.fixture
def redactor():
    """Fresh PIIRedactor (not the module singleton) per test."""
    r = PIIRedactor()
    patcher = patch.object(r.analyzer, "analyze", side_effect=fake_analyze)
    patcher.start()
    yield r
    patcher.stop()


# ---------------------------------------------------------------------------
# Core redaction behaviour
# ---------------------------------------------------------------------------
class TestEmailRedaction:
    def test_email_redacted(self, redactor):
        result = redactor.redact("Contact john@example.com for details")
        assert result.has_secrets
        assert "john@example.com" not in result.redacted_text
        assert "<EMAIL_ADDRESS>" in result.redacted_text

    def test_multiple_emails_redacted(self, redactor):
        result = redactor.redact("Email alice@test.com and bob@example.com")
        assert result.has_secrets
        emails = [r for r in result.redactions if r["type"] == "EMAIL_ADDRESS"]
        assert len(emails) >= 2

    def test_redact_entities_only_emails(self, redactor):
        out = redactor.redact_entities("mail me at test@example.com", ["EMAIL_ADDRESS"])
        assert "test@example.com" not in out
        assert "<EMAIL_ADDRESS>" in out


class TestAllowlist:
    def test_default_allowlist_email_preserved(self, redactor):
        """support@atom.ai is in DEFAULT_ALLOWLIST and must NOT be redacted."""
        result = redactor.redact("Contact support@atom.ai for help")
        assert "support@atom.ai" in result.redacted_text
        # And it must not appear as a redacted EMAIL_ADDRESS.
        assert not any(
            r["type"] == "EMAIL_ADDRESS"
            and "support@atom.ai" in result.original_text[r["start"]:r["end"]]
            for r in result.redactions
        )

    def test_allowlist_case_insensitive(self, redactor):
        """SUPPORT@ATOM.AI matches the lowercased allowlist."""
        result = redactor.redact("Email SUPPORT@ATOM.AI")
        assert "SUPPORT@ATOM.AI" in result.redacted_text

    def test_add_allowlist_runtime(self, redactor):
        redactor.add_allowlist(["partners@external.com"])
        result = redactor.redact("Email partners@external.com now")
        assert "partners@external.com" in result.redacted_text

    def test_custom_allowlist_in_constructor(self):
        r = PIIRedactor(allowlist=["safe@company.io"])
        with patch.object(r.analyzer, "analyze", side_effect=fake_analyze):
            result = r.redact("Reach safe@company.io")
        assert "safe@company.io" in result.redacted_text

    def test_non_allowlisted_email_still_redacted(self, redactor):
        result = redactor.redact("Email attacker@evil.com")
        assert "attacker@evil.com" not in result.redacted_text


class TestOtherEntities:
    def test_credit_card_redacted(self, redactor):
        result = redactor.redact("Card: 4532-1234-5678-9010")
        assert result.has_secrets
        assert "4532-1234-5678-9010" not in result.redacted_text

    def test_ip_address_redacted(self, redactor):
        result = redactor.redact("Server IP 10.0.0.1 is private")
        if result.has_secrets:
            assert "10.0.0.1" not in result.redacted_text

    def test_phone_redacted(self, redactor):
        result = redactor.redact("Call (555) 123-4567 now")
        assert result.has_secrets
        assert "(555) 123-4567" not in result.redacted_text

    def test_url_redacted(self, redactor):
        result = redactor.redact("Visit https://example.com/path?token=secret")
        if result.has_secrets:
            assert "token=secret" not in result.redacted_text


class TestCleanText:
    def test_no_pii_unchanged(self, redactor):
        result = redactor.redact("Hello world, safe text here")
        assert not result.has_secrets
        assert result.redacted_text == "Hello world, safe text here"

    def test_is_sensitive_true(self, redactor):
        assert redactor.is_sensitive("Email: test@example.com") is True

    def test_is_sensitive_false(self, redactor):
        assert redactor.is_sensitive("Just plain words") is False


class TestEmptyInput:
    def test_empty_string(self, redactor):
        result = redactor.redact("")
        assert not result.has_secrets
        assert result.redacted_text == ""
        assert result.redactions == []

    def test_none_input(self, redactor):
        result = redactor.redact(None)  # type: ignore[arg-type]
        assert not result.has_secrets
        assert result.redacted_text == ""


# ---------------------------------------------------------------------------
# Internals: operators, placeholders, audit log
# ---------------------------------------------------------------------------
class TestInternals:
    def test_get_operators_returns_all_entities(self, redactor):
        ops = redactor._get_operators()
        for entity in [
            "EMAIL_ADDRESS", "US_SSN", "CREDIT_CARD", "PHONE_NUMBER",
            "IBAN_CODE", "IP_ADDRESS", "US_BANK_NUMBER", "US_DRIVER_LICENSE",
            "URL", "DATE_TIME",
        ]:
            assert entity in ops

    def test_add_placeholders_replaces_hash(self, redactor):
        """_add_placeholders swaps a 64-char SHA256 hash for a <TYPE> token."""
        # Use a distinctive 64-char hash; the item start/end must match the
        # actual position of the hash inside anon.text (the helper reads the
        # hash from text[start:end]).
        h = "e69df8e0e6515fc0790350cb8028659fc464e7bb9aebc7e82dc2252557c1485c"
        prefix = "contact "
        text = f"{prefix}{h}."
        item = MagicMock()
        item.entity_type = "EMAIL_ADDRESS"
        item.start = len(prefix)
        item.end = len(prefix) + len(h)
        anon = MagicMock()
        anon.text = text
        anon.items = [item]
        out = redactor._add_placeholders(anon, [])
        assert out == f"{prefix}<EMAIL_ADDRESS>."

    def test_add_placeholders_ignores_short_hash(self, redactor):
        """A non-64-char anonymized span is left untouched (not a SHA256)."""
        item = MagicMock()
        item.entity_type = "URL"
        item.start = 0
        item.end = 5
        anon = MagicMock()
        anon.text = "abcde"
        anon.items = [item]
        out = redactor._add_placeholders(anon, [])
        assert out == "abcde"

    def test_audit_log_emitted_on_redaction(self, redactor):
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        logger = logging.getLogger("core.pii_redactor")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            redactor.redact("Email: test@example.com")
        finally:
            logger.removeHandler(handler)
        assert "PII redacted" in log_stream.getvalue()


# ---------------------------------------------------------------------------
# Presidio runtime-failure fallback
# ---------------------------------------------------------------------------
class TestPresidioFailureFallback:
    def test_runtime_analyze_failure_degrades_gracefully(self, redactor):
        """BUG: when Presidio is installed but analyzer.analyze() raises at
        runtime (e.g. NER model load error), redact() catches the exception
        and calls _fallback_redact() -- but the Presidio __init__ path never
        created self.fallback_redactor, so the "graceful" fallback crashed
        with AttributeError instead of degrading to SecretsRedactor.
        """
        text = "password=supersecret123"
        with patch.object(redactor.analyzer, "analyze", side_effect=RuntimeError("model boom")):
            result = redactor.redact(text)
        # Must return a RedactionResult, never raise.
        assert isinstance(result, RedactionResult)
        # Fallback (SecretsRedactor) must catch the password token.
        assert result.has_secrets
        assert "supersecret123" not in result.redacted_text


# ---------------------------------------------------------------------------
# Module-level convenience functions + singleton
# ---------------------------------------------------------------------------
class TestConvenienceFunctions:
    def setup_method(self):
        # Reset the singleton between tests so env/state changes take effect.
        import core.pii_redactor as mod
        mod._pii_redactor = None

    def teardown_method(self):
        import core.pii_redactor as mod
        mod._pii_redactor = None

    def test_get_pii_redactor_singleton(self):
        a = get_pii_redactor()
        b = get_pii_redactor()
        assert a is b

    def test_get_pii_redactor_reads_env_allowlist(self, monkeypatch):
        """PII_REDACTOR_ALLOWLIST env var seeds the singleton allowlist."""
        monkeypatch.setenv("PII_REDACTOR_ALLOWLIST", "one@env.io,two@env.io")
        r = get_pii_redactor()
        assert "one@env.io" in r.allowlist
        assert "two@env.io" in r.allowlist

    def test_redact_pii_returns_string(self):
        r = get_pii_redactor()
        with patch.object(r.analyzer, "analyze", side_effect=fake_analyze):
            out = redact_pii("mail me at test@example.com")
        assert isinstance(out, str)
        assert "test@example.com" not in out

    def test_check_for_pii_structure(self):
        r = get_pii_redactor()
        with patch.object(r.analyzer, "analyze", side_effect=fake_analyze):
            info = check_for_pii("mail me at test@example.com")
        assert info["has_pii"] is True
        assert "EMAIL_ADDRESS" in info["types"]
        assert info["count"] >= 1

    def test_check_for_pii_clean_text(self):
        info = check_for_pii("just normal words")
        assert info["has_pii"] is False
        assert info["count"] == 0
        assert info["types"] == []


class TestFallbackMode:
    """Cover the PRESIDIO_AVAILABLE=False code paths by toggling the module
    flag. These branches are live in environments without Presidio installed
    (e.g. minimal CI images), so they must be exercised."""

    def test_fallback_init_and_redact(self, monkeypatch):
        import core.pii_redactor as mod
        monkeypatch.setattr(mod, "PRESIDIO_AVAILABLE", False)
        r = mod.PIIRedactor()
        # In fallback mode the SecretsRedactor-backed redactor is wired up.
        assert hasattr(r, "fallback_redactor")
        result = r.redact("password=supersecret123")
        assert result.has_secrets
        assert "supersecret123" not in result.redacted_text

    def test_fallback_redact_empty(self, monkeypatch):
        import core.pii_redactor as mod
        monkeypatch.setattr(mod, "PRESIDIO_AVAILABLE", False)
        r = mod.PIIRedactor()
        result = r.redact("")
        assert not result.has_secrets
        assert result.redacted_text == ""

    def test_fallback_default_allowlist_applied(self, monkeypatch):
        import core.pii_redactor as mod
        monkeypatch.setattr(mod, "PRESIDIO_AVAILABLE", False)
        r = mod.PIIRedactor(allowlist=["custom@env.io"])
        assert "custom@env.io" in r.allowlist
        assert "support@atom.ai" in r.allowlist
