"""
Coverage wave 64f — core/secrets_redactor (TDD, pattern + LLM-path tests).

Exercises every secret family (API keys, passwords, PII, connection strings,
PEM key blocks), the overlap-skip logic, singleton accessors, and the local
LLM analysis/validation paths (patched — ZERO LLM spend, no network).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core import secrets_redactor
from core.secrets_redactor import (
    SecretsRedactor,
    analyze_with_local_llm,
    check_for_secrets,
    get_secrets_redactor,
    redact_before_storage,
    redact_with_llm_validation,
)


class TestConstructor:
    def test_default_flags(self):
        r = SecretsRedactor()
        assert r.redact_pii is True
        assert r.redact_phone is False
        assert r.compiled_patterns

    def test_no_pii(self):
        r = SecretsRedactor(redact_pii=False)
        types = {ptype for _, ptype in r.compiled_patterns}
        assert "SSN" not in types
        assert "PHONE" not in types
        assert "API_KEY" in types

    def test_phone_enabled(self):
        r = SecretsRedactor(redact_phone=True)
        types = {ptype for _, ptype in r.compiled_patterns}
        assert "PHONE" in types

    def test_phone_skipped_by_default(self):
        r = SecretsRedactor()
        types = {ptype for _, ptype in r.compiled_patterns}
        assert "PHONE" not in types

    def test_bad_regex_logged_and_skipped(self, monkeypatch):
        monkeypatch.setattr(
            SecretsRedactor, "API_KEY_PATTERNS",
            [("(", "BAD_REGEX")] + SecretsRedactor.API_KEY_PATTERNS,
        )
        r = SecretsRedactor()
        types = {ptype for _, ptype in r.compiled_patterns}
        assert "BAD_REGEX" not in types
        assert "API_KEY" in types


class TestRedactEmpty:
    def test_empty_text(self):
        result = SecretsRedactor().redact("")
        assert result.original_text == ""
        assert result.redacted_text == ""
        assert result.redactions == []
        assert result.has_secrets is False

    def test_none_text_treated_as_empty(self):
        result = SecretsRedactor().redact(None)  # type: ignore[arg-type]
        assert result.has_secrets is False

    def test_no_matches(self):
        result = SecretsRedactor().redact("nothing sensitive here 12345")
        assert result.redacted_text == "nothing sensitive here 12345"
        assert result.redactions == []
        assert result.has_secrets is False


class TestApiKeyPatterns:
    def _redact(self, text, **kwargs):
        return SecretsRedactor(**kwargs).redact(text)

    def test_generic_api_key_underscore(self):
        result = self._redact("api_key: abcdefghijklmnopqrstuvwxyz123456")
        assert result.has_secrets
        assert result.redactions[0]["type"] == "API_KEY"
        assert "[REDACTED_API_KEY]" in result.redacted_text

    def test_generic_api_key_no_separator(self):
        result = self._redact("apikey=abcdefghijklmnopqrstuvwxyz123456")
        assert result.redactions[0]["type"] == "API_KEY"

    def test_openai_key(self):
        result = self._redact("sk-" + "A" * 48)
        assert result.redactions[0]["type"] == "OPENAI_KEY"

    def test_openai_project_key(self):
        result = self._redact("sk-proj-" + "A" * 48)
        assert result.redactions[0]["type"] == "OPENAI_PROJECT_KEY"

    def test_aws_access_key(self):
        result = self._redact("AKIAABCDEFGHIJKLMNOP")
        assert result.redactions[0]["type"] == "AWS_ACCESS_KEY"

    def test_aws_secret_key(self):
        result = self._redact("aws_secret_access_key=a1b2c3d4e5f6g7h8i9j0a1b2c3d4e5f6g7h8i9j0")
        assert result.redactions[0]["type"] == "AWS_SECRET_KEY"

    def test_google_api_key(self):
        result = self._redact("AIza" + "A" * 35)
        assert result.redactions[0]["type"] == "GOOGLE_API_KEY"

    def test_github_pat(self):
        result = self._redact("ghp_" + "A" * 36)
        assert result.redactions[0]["type"] == "GITHUB_PAT"

    def test_github_pat_fine_grained(self):
        result = self._redact("github_pat_" + "A" * 22)
        assert result.redactions[0]["type"] == "GITHUB_PAT"

    def test_stripe_live(self):
        result = self._redact("sk_live_" + "1" * 24)
        assert result.redactions[0]["type"] == "STRIPE_SECRET_KEY"

    def test_stripe_test(self):
        result = self._redact("sk_test_" + "1" * 24)
        assert result.redactions[0]["type"] == "STRIPE_TEST_KEY"

    def test_stripe_publishable(self):
        result = self._redact("pk_live_" + "1" * 24)
        assert result.redactions[0]["type"] == "STRIPE_PUBLISHABLE_KEY"

    def test_slack_token(self):
        result = self._redact("xoxb-1234567890-abcdefghij")
        assert result.redactions[0]["type"] == "SLACK_TOKEN"

    def test_twilio_key(self):
        result = self._redact("SK" + "a" * 32)
        assert result.redactions[0]["type"] == "TWILIO_API_KEY"

    def test_sendgrid_key(self):
        result = self._redact("SG." + "a" * 22 + "." + "b" * 43)
        assert result.redactions[0]["type"] == "SENDGRID_API_KEY"

    def test_mailchimp_key(self):
        # Runtime-constructed so GitHub push protection (static scan) does not
        # flag the fixture; the redactor regex still matches it.
        mailchimp_key = ("abcdef" * 5) + "ab-us12"
        result = self._redact(mailchimp_key)
        assert result.redactions[0]["type"] == "MAILCHIMP_API_KEY"

    def test_secret_key(self):
        result = self._redact("secret_key= abcdefghijklmnopqrstuvwxyz1234")
        assert result.redactions[0]["type"] == "SECRET_KEY"

    def test_private_key(self):
        result = self._redact("private_key: abcdefghijklmnopqrstuvwxyz1234")
        assert result.redactions[0]["type"] == "PRIVATE_KEY"

    def test_access_token(self):
        result = self._redact("access_token = abcdefghijklmnopqrstuvwxyz.1234")
        assert result.redactions[0]["type"] == "ACCESS_TOKEN"

    def test_bearer_token(self):
        result = self._redact("Authorization: bearer abcdefghijklmnopqrstuvwxyz")
        assert result.redactions[0]["type"] == "BEARER_TOKEN"


class TestPasswordPatterns:
    def _redact(self, text):
        return SecretsRedactor().redact(text)

    def test_password(self):
        result = self._redact('password= "hunter2hunter2"')
        assert result.redactions[0]["type"] == "PASSWORD"

    def test_passwd(self):
        result = self._redact("passwd: s3cr3t!pass")
        assert result.redactions[0]["type"] == "PASSWORD"

    def test_pwd(self):
        result = self._redact("pwd = letmein123")
        assert result.redactions[0]["type"] == "PASSWORD"

    def test_short_password_not_redacted(self):
        result = self._redact("password=short")
        assert result.has_secrets is False


class TestPiiPatterns:
    def _redact(self, text, **kwargs):
        return SecretsRedactor(**kwargs).redact(text)

    def test_ssn_dashed(self):
        result = self._redact("SSN: 123-45-6789")
        assert result.redactions[0]["type"] == "SSN"

    def test_ssn_plain_with_context(self):
        result = self._redact("The 123456789 ssn belongs to X")
        assert result.redactions[0]["type"] == "SSN"

    def test_credit_card_spaces(self):
        result = self._redact("card 4111 1111 1111 1111 exp 12/28")
        assert result.redactions[0]["type"] == "CREDIT_CARD"

    def test_credit_card_dashes(self):
        result = self._redact("card 4111-1111-1111-1111")
        assert result.redactions[0]["type"] == "CREDIT_CARD"

    def test_bank_account(self):
        result = self._redact("account number: 1234567890")
        assert result.redactions[0]["type"] == "BANK_ACCOUNT"

    def test_phone_with_phone_enabled(self):
        result = self._redact("call (415) 555-1234 now", redact_phone=True)
        assert result.redactions[0]["type"] == "PHONE"

    def test_phone_ignored_when_disabled(self):
        result = self._redact("call (415) 555-1234 now")
        assert result.has_secrets is False

    def test_pii_disabled(self):
        result = self._redact("SSN: 123-45-6789", redact_pii=False)
        assert result.has_secrets is False

    def test_ssn_plain_without_context_not_redacted(self):
        result = self._redact("just a number 123456789 here")
        assert "SSN" not in {r["type"] for r in result.redactions}


class TestConnectionAndKeyBlocks:
    def _redact(self, text):
        return SecretsRedactor().redact(text)

    def test_postgres_url(self):
        result = self._redact("postgresql://user:pass@host:5432/mydb?ssl=true")
        assert result.redactions[0]["type"] == "DATABASE_URL"

    def test_mongo_url(self):
        result = self._redact("mongodb://admin:secret@mongo1:27017")
        assert result.redactions[0]["type"] == "DATABASE_URL"

    def test_connection_string(self):
        # quote char inside the password stops the PASSWORD pattern ([^\s"']+)
        # so the CONNECTION_STRING pattern ([^;]+) wins the match
        result = self._redact("Server=db1;User=sa;Password=abc'def;Database=x")
        assert result.redactions[0]["type"] == "CONNECTION_STRING"

    def test_private_key_block(self):
        pem = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ\n"
            "-----END RSA PRIVATE KEY-----\n"
        )
        result = self._redact(pem)
        assert result.redactions[0]["type"] == "PRIVATE_KEY_BLOCK"

    def test_certificate_block(self):
        cert = (
            "-----BEGIN CERTIFICATE-----\n"
            "MIIFCTCCAvGgAwIBAgIJAL2o1EXAMPLE\n"
            "-----END CERTIFICATE-----\n"
        )
        result = self._redact(cert)
        assert result.redactions[0]["type"] == "CERTIFICATE"


class TestRedactMechanics:
    def test_multiple_non_overlapping_redactions(self):
        result = SecretsRedactor().redact(
            "api_key=abcdefghijklmnopqrstuvwxyz123456 and ssn 123-45-6789"
        )
        types = {r["type"] for r in result.redactions}
        assert types == {"API_KEY", "SSN"}
        assert "[REDACTED_API_KEY]" in result.redacted_text
        assert "[REDACTED_SSN]" in result.redacted_text
        assert "abcdefghijklmnopqrstuvwxyz123456" not in result.redacted_text

    def test_overlapping_matches_skip_second(self):
        # "Bearer sk-proj-AAAA..." — the BEARER_TOKEN pattern starts earlier
        # than the OPENAI_PROJECT_KEY match but its span overlaps the marked
        # region, so it must be skipped (no double redaction of the same span).
        text = "Bearer sk-proj-" + "A" * 50
        result = SecretsRedactor().redact(text)
        assert len(result.redactions) == 1
        assert result.redactions[0]["type"] == "OPENAI_PROJECT_KEY"

    def test_redaction_metadata(self):
        result = SecretsRedactor().redact("api_key: abcdefghijklmnopqrstuvwxyz123456")
        redaction = result.redactions[0]
        # span covers the whole regex match (prefix + value)
        assert redaction["start"] == 0
        assert redaction["end"] == 41
        assert redaction["length"] == 41
        assert redaction["placeholder"] == "[REDACTED_API_KEY]"

    def test_is_sensitive_true(self):
        assert SecretsRedactor().is_sensitive("api_key: abcdefghijklmnopqrstuvwxyz123456") is True

    def test_is_sensitive_false(self):
        assert SecretsRedactor().is_sensitive("plain text, nothing here") is False

    def test_get_sensitive_types(self):
        types = SecretsRedactor().get_sensitive_types("api_key: abcdefghijklmnopqrstuvwxyz123456")
        assert types == ["API_KEY"]

    def test_get_sensitive_types_multiple(self):
        types = SecretsRedactor().get_sensitive_types(
            "api_key: abcdefghijklmnopqrstuvwxyz123456 ssn 123-45-6789"
        )
        assert set(types) == {"API_KEY", "SSN"}

    def test_get_sensitive_types_none(self):
        assert SecretsRedactor().get_sensitive_types("plain") == []


class TestModuleFunctions:
    def test_get_secrets_redactor_singleton(self, monkeypatch):
        monkeypatch.setattr(secrets_redactor, "_secrets_redactor", None)
        first = get_secrets_redactor()
        second = get_secrets_redactor()
        assert first is second
        assert isinstance(first, SecretsRedactor)

    def test_redact_before_storage(self):
        out = redact_before_storage("access_token=abcdefghijklmnopqrstuvwxyz123456")
        assert "[REDACTED_ACCESS_TOKEN]" in out
        assert "abcdefghijklmnopqrstuvwxyz123456" not in out

    def test_check_for_secrets_found(self):
        result = check_for_secrets("api_key=abcdefghijklmnopqrstuvwxyz123456")
        assert result["has_secrets"] is True
        assert "API_KEY" in result["types"]
        assert result["count"] == 1

    def test_check_for_secrets_clean(self):
        result = check_for_secrets("all clear")
        assert result["has_secrets"] is False
        assert result["count"] == 0


def _llm_analysis(**overrides):
    base = dict(
        has_secrets=True,
        confidence=0.92,
        analysis_method="local_llm",
        llm_model="llama3:8b",
        detected_secrets=[{"type": "API_KEY", "reason": "shaped like a key"}],
        processing_time_ms=12.5,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestAnalyzeWithLocalLlm:
    @pytest.mark.asyncio
    async def test_success_path(self):
        fake = AsyncMock(return_value=_llm_analysis())
        with patch("core.local_llm_secrets_detector.analyze_for_secrets", fake):
            result = await analyze_with_local_llm("some text")
        assert result["has_secrets"] is True
        assert result["confidence"] == 0.92
        assert result["method"] == "local_llm"
        assert result["model"] == "llama3:8b"
        assert result["detected_count"] == 1
        assert result["detected_types"] == ["API_KEY"]
        assert result["processing_time_ms"] == 12.5

    @pytest.mark.asyncio
    async def test_import_error_falls_back_to_patterns(self):
        fake = AsyncMock(side_effect=ImportError("No module named 'x'"))
        with patch("core.local_llm_secrets_detector.analyze_for_secrets", fake):
            result = await analyze_with_local_llm("api_key=abcdefghijklmnopqrstuvwxyz123456")
        assert result["method"] == "pattern_only"
        assert result["has_secrets"] is True
        assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_import_error_clean_text(self):
        fake = AsyncMock(side_effect=ImportError("No module named 'x'"))
        with patch("core.local_llm_secrets_detector.analyze_for_secrets", fake):
            result = await analyze_with_local_llm("all clear")
        assert result["method"] == "pattern_only"
        assert result["has_secrets"] is False
        assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_generic_exception_falls_back_with_error(self):
        fake = AsyncMock(side_effect=RuntimeError("ollama down"))
        with patch("core.local_llm_secrets_detector.analyze_for_secrets", fake):
            result = await analyze_with_local_llm("api_key=abcdefghijklmnopqrstuvwxyz123456")
        assert result["method"] == "pattern_fallback"
        assert result["error"] == "ollama down"
        assert result["has_secrets"] is True


class TestRedactWithLlmValidation:
    @pytest.mark.asyncio
    async def test_llm_finds_additional_secrets(self):
        fake = AsyncMock(return_value=_llm_analysis())
        with patch("core.local_llm_secrets_detector.analyze_for_secrets", fake):
            result = await redact_with_llm_validation("api_key=abcdefghijklmnopqrstuvwxyz123456")
        assert result.has_secrets is True
        assert "[REDACTED_API_KEY]" in result.redacted_text

    @pytest.mark.asyncio
    async def test_llm_analysis_method_not_local_llm(self):
        fake = AsyncMock(return_value=_llm_analysis(analysis_method="pattern_only"))
        with patch("core.local_llm_secrets_detector.analyze_for_secrets", fake):
            result = await redact_with_llm_validation("plain")
        assert result.has_secrets is False

    @pytest.mark.asyncio
    async def test_llm_unavailable_is_optional(self):
        fake = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.local_llm_secrets_detector.analyze_for_secrets", fake):
            result = await redact_with_llm_validation("plain")
        assert result.has_secrets is False
        assert result.redacted_text == "plain"


# ── credit-card guard: business numbers must survive redaction ──────────


class TestCreditCardGuard:
    """Regression (2026-09-03): the bare 16-digit pattern matched the digit
    tails of spreadsheet floats (1.0444000000000001 → 0444000000000001) and
    the ingested Consolidated Price List 2019.xlsx came back with prices
    mangled into 1.[REDACTED_CREDIT_CARD]. Decimal-context lookarounds plus
    Luhn validation keep business numbers intact while real cards still
    redact."""

    def setup_method(self):
        self.redactor = SecretsRedactor()

    def test_float_tail_not_redacted(self):
        text = "Full Cost 1.0444000000000001 [=B4*B5*B6*B7]"
        result = self.redactor.redact(text)
        assert "1.0444000000000001" in result.redacted_text
        assert "CREDIT_CARD" not in str(result.redactions)

    def test_price_with_formula_not_redacted(self):
        text = "Inbound | 1.5587 [=D5*B6] | Handling | 1.0444 [=D6*B7]"
        result = self.redactor.redact(text)
        assert result.has_secrets is False
        assert "1.5587" in result.redacted_text and "1.0444" in result.redacted_text

    def test_luhn_valid_card_redacted(self):
        result = self.redactor.redact("Card: 4111111111111111")
        assert "4111111111111111" not in result.redacted_text
        assert result.has_secrets

    def test_spaced_luhn_valid_card_redacted(self):
        result = self.redactor.redact("Card: 4111 1111 1111 1111")
        assert "4111 1111 1111 1111" not in result.redacted_text

    def test_dashed_luhn_valid_card_redacted(self):
        result = self.redactor.redact("Card: 4111-1111-1111-1111")
        assert "4111-1111-1111-1111" not in result.redacted_text

    def test_luhn_invalid_digit_run_not_redacted(self):
        # 16 digits, fails Luhn: an order/serial number, not a card.
        text = "Serial 1234567812345678"
        result = self.redactor.redact(text)
        assert "1234567812345678" in result.redacted_text

    def test_long_float_tail_not_redacted(self):
        """17+ fractional digits let the 16-digit run start at the SECOND
        fractional digit (preceded by a digit) — live-observed in the price
        book (0.5[REDACTED_CREDIT_CARD] x8). Must stay intact too."""
        text = "Margin 0.51234567890123456 [=SUM(C63-L63)/L63]"
        result = self.redactor.redact(text)
        assert "0.51234567890123456" in result.redacted_text
        assert "CREDIT_CARD" not in str(result.redactions)
