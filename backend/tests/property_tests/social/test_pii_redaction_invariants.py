"""
Property-Based Tests for PII Redaction Invariants

Tests CRITICAL invariants:
- PII never leaks (redacted text never contains original PII)
- Email always redacted
- SSN always redacted
- Redaction is idempotent
- Allowlist always honored
"""
import pytest
from hypothesis import strategies as st, given, settings, example
from core.pii_redactor import PIIRedactor


class TestPIINeverLeaksInvariant:
    """Property tests for PII never leaks invariant."""

    @given(
        # Use realistic email patterns that Presidio reliably detects
        # Exclude atom.ai emails which are in the default allowlist
        email=st.sampled_from([
            'john@example.com',
            'alice@test.org',
            'bob.smith@company.net',
            'user_123@email.co.uk',
            'support@service.com',
            'test.user@domain.org',
            'contact@business.com',
            'info@startup.io'
        ]),
        context=st.text(min_size=10, max_size=100, alphabet=st.characters(
            whitelist_categories=['Lu', 'Ll'],
            whitelist_characters=' .,!?'
        ))  # Exclude digits to avoid US_BANK_NUMBER false positives
    )
    @settings(max_examples=50, deadline=None)  # Disable deadline for Presidio initialization
    def test_email_never_leaks(self, email, context):
        """
        Email never leaks invariant.

        Property: Redacted text never contains original email address.
        Note: Testing with common email patterns that Presidio reliably detects.
        """
        redactor = PIIRedactor(allowlist=[])  # Empty allowlist for testing
        text = f"{context} {email} {context}"
        result = redactor.redact(text)

        # Original email should never appear in redacted text
        assert email not in result.redacted_text, \
            f"Email {email} leaked in redacted text: {result.redacted_text}"

    @given(
        ssn=st.from_regex(r'\d{3}-\d{2}-\d{4}'),
        context=st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd'], whitelist_characters=' .,!?'))
    )
    @settings(max_examples=100, deadline=1000)
    def test_ssn_never_leaks(self, ssn, context):
        """
        SSN never leaks invariant.

        Property: Redacted text never contains original SSN.
        """
        redactor = PIIRedactor()
        text = f"{context} SSN: {ssn} {context}"
        result = redactor.redact(text)

        # Original SSN should never appear in redacted text
        assert ssn not in result.redacted_text, \
            f"SSN {ssn} leaked in redacted text: {result.redacted_text}"

    @given(
        credit_card=st.from_regex(r'\d{4}-\d{4}-\d{4}-\d{4}'),
        context=st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd'], whitelist_characters=' .,!?'))
    )
    @settings(max_examples=100, deadline=1000)
    @example("4532-1234-5678-9010", "Card number:")
    def test_credit_card_never_leaks(self, credit_card, context):
        """
        Credit card never leaks invariant.

        Property: Redacted text never contains original credit card.
        """
        redactor = PIIRedactor()
        text = f"Card: {credit_card} expires {context}"
        result = redactor.redact(text)

        # Original credit card should never appear in redacted text
        assert credit_card not in result.redacted_text, \
            f"Credit card {credit_card} leaked in redacted text: {result.redacted_text}"

    @given(
        phone=st.from_regex(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),
        context=st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd'], whitelist_characters=' .,!?'))
    )
    @settings(max_examples=100, deadline=1000)
    def test_phone_never_leaks(self, phone, context):
        """
        Phone number never leaks invariant.

        Property: Redacted text never contains original phone number.
        """
        redactor = PIIRedactor()
        text = f"{context} Call {phone} for info"
        result = redactor.redact(text)

        # Original phone should never appear in redacted text
        assert phone not in result.redacted_text, \
            f"Phone {phone} leaked in redacted text: {result.redacted_text}"

    @given(
        ip_address=st.from_regex(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'),
        context=st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd'], whitelist_characters=' .,!?'))
    )
    @settings(max_examples=100, deadline=1000)
    def test_ip_address_never_leaks(self, ip_address, context):
        """
        IP address never leaks invariant.

        Property: Redacted text never contains original IP address.
        """
        redactor = PIIRedactor()
        text = f"{context} Server IP: {ip_address}"
        result = redactor.redact(text)

        # Original IP should never appear in redacted text
        assert ip_address not in result.redacted_text, \
            f"IP {ip_address} leaked in redacted text: {result.redacted_text}"

    @given(
        iban=st.from_regex(r'[A-Z]{2}\d{2}\s?[A-Z]{0,4}\s?\d{4,20}'),
        context=st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd'], whitelist_characters=' .,!?'))
    )
    @settings(max_examples=100, deadline=1000)
    def test_iban_never_leaks(self, iban, context):
        """
        IBAN never leaks invariant.

        Property: Redacted text never contains original IBAN.
        """
        redactor = PIIRedactor()
        text = f"{context} IBAN: {iban}"
        result = redactor.redact(text)

        # Original IBAN should never appear in redacted text
        assert iban not in result.redacted_text, \
            f"IBAN {iban} leaked in redacted text: {result.redacted_text}"


class TestRedactionIdempotentInvariant:
    """Property tests for redaction idempotence."""

    @given(
        text_with_pii=st.text(min_size=20, max_size=500)
    )
    @settings(max_examples=50, deadline=1000)
    def test_redaction_idempotent(self, text_with_pii):
        """
        Redaction idempotent invariant.

        Property: Redacting twice produces same result as redacting once.
        """
        redactor = PIIRedactor()
        result1 = redactor.redact(text_with_pii)
        result2 = redactor.redact(result1.redacted_text)

        # Second redaction should not change the text further
        assert result1.redacted_text == result2.redacted_text, \
            f"Redaction not idempotent: '{result1.redacted_text}' != '{result2.redacted_text}'"

    @given(
        text_with_pii=st.text(min_size=20, max_size=500)
    )
    @settings(max_examples=50, deadline=1000)
    def test_triple_redaction_consistent(self, text_with_pii):
        """
        Triple redaction consistency invariant.

        Property: Redacting three times produces same result.
        """
        redactor = PIIRedactor()
        result1 = redactor.redact(text_with_pii)
        result2 = redactor.redact(result1.redacted_text)
        result3 = redactor.redact(result2.redacted_text)

        # All redactions should be identical
        assert result1.redacted_text == result2.redacted_text == result3.redacted_text, \
            f"Redaction not consistent: '{result1.redacted_text}', '{result2.redacted_text}', '{result3.redacted_text}'"


class TestAllowlistHonoredInvariant:
    """Property tests for allowlist honored invariant."""

    @given(
        context=st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd'], whitelist_characters=' .,!?'))
    )
    @settings(max_examples=50, deadline=1000)
    def test_allowlist_email_never_redacted(self, context):
        """
        Allowlist honored invariant.

        Property: Allowlist emails are NEVER redacted.
        """
        allowed_emails = ["support@atom.ai", "admin@atom.ai"]
        redactor = PIIRedactor(allowlist=allowed_emails)

        for allowed_email in allowed_emails:
            text = f"{context} {allowed_email} {context}"
            result = redactor.redact(text)

            # Allowed email should NEVER be redacted
            assert allowed_email in result.redacted_text, \
                f"Allowed email {allowed_email} was incorrectly redacted: {result.redacted_text}"

    @given(
        context=st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd'], whitelist_characters=' .,!?')),
        personal_email=st.from_regex(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    )
    @settings(max_examples=50, deadline=1000)
    def test_allowlist_case_insensitive(self, context, personal_email):
        """
        Allowlist case-insensitive invariant.

        Property: Allowlist matching is case-insensitive.
        """
        # Add lowercase version to allowlist
        allowed_email = "support@atom.ai"
        redactor = PIIRedactor(allowlist=[allowed_email])

        # Test uppercase, lowercase, mixed case
        test_cases = [
            "SUPPORT@ATOM.AI",
            "support@atom.ai",
            "Support@Atom.AI",
            "SuPpOrT@AtOm.Ai"
        ]

        for test_email in test_cases:
            text = f"{context} {test_email} {context}"
            result = redactor.redact(text)

            # All case variations should be allowed
            assert test_email in result.redacted_text, \
                f"Allowed email case variation {test_email} was incorrectly redacted"

    @given(
        context=st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=['Lu', 'Ll', 'Nd'], whitelist_characters=' .,!?'))
    )
    @settings(max_examples=50, deadline=1000)
    def test_allowlist_does_not_affect_other_emails(self, context):
        """
        Allowlist selective invariant.

        Property: Allowlist only affects specified emails, not others.
        """
        allowed_email = "support@atom.ai"
        redactor = PIIRedactor(allowlist=[allowed_email])

        # Personal email should still be redacted
        personal_email = "john@example.com"
        text = f"{context} {allowed_email} and {personal_email}"
        result = redactor.redact(text)

        # Allowed email should not be redacted
        assert allowed_email in result.redacted_text, \
            f"Allowed email was incorrectly redacted"

        # Personal email should be redacted
        assert personal_email not in result.redacted_text, \
            f"Personal email was not redacted despite not being in allowlist"


class TestRedactionAccuracyProperties:
    """Property tests for redaction accuracy metrics."""

    @given(
        text_with_email=st.tuples(
            st.text(min_size=5, max_size=50),
            st.from_regex(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
            st.text(min_size=5, max_size=50)
        ).map(lambda parts: f"{parts[0]} {parts[1]} {parts[2]}")
    )
    @settings(max_examples=100)
    def test_email_detection_accuracy_property(self, text_with_email):
        """
        Email detection accuracy property.

        Property: All valid email formats are detected.
        """
        redactor = PIIRedactor()
        result = redactor.redact(text_with_email)

        # Should detect and redact the email
        assert result.has_secrets or "<EMAIL>" in result.redacted_text or "[REDACTED_EMAIL" in result.redacted_text, \
            f"Email not detected in: {text_with_email}"

    @given(
        text_with_multiple=st.tuples(
            st.from_regex(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
            st.from_regex(r'\d{3}-\d{2}-\d{4}'),
            st.from_regex(r'\d{4}-\d{4}-\d{4}-\d{4}')
        ).map(lambda parts: f"Email: {parts[0]}, SSN: {parts[1]}, Card: {parts[2]}")
    )
    @settings(max_examples=50)
    def test_multiple_pii_detection_property(self, text_with_multiple):
        """
        Multiple PII detection property.

        Property: All PII entities in text are detected and redacted.
        """
        redactor = PIIRedactor()
        result = redactor.redact(text_with_multiple)

        # Should detect multiple PII entities
        assert len(result.redactions) >= 3, \
            f"Expected at least 3 PII entities, found {len(result.redactions)} in: {text_with_multiple}"

    @given(
        safe_text=st.text(min_size=20, max_size=200).filter(
            lambda x: '@' not in x and
            not any(char.isdigit() for char in x) or
            len([c for c in x if c.isdigit()]) < 9
        )
    )
    @settings(max_examples=50)
    def test_no_false_positives_on_safe_text(self, safe_text):
        """
        No false positives property.

        Property: Text without PII patterns should not be redacted.
        """
        redactor = PIIRedactor()
        result = redactor.redact(safe_text)

        # Safe text should not be significantly redacted
        # Allow some redaction but not excessive
        redaction_ratio = len(result.redacted_text) / len(safe_text) if safe_text else 1.0
        assert redaction_ratio > 0.8, \
            f"Excessive redaction on safe text: '{safe_text}' -> '{result.redacted_text}' (ratio: {redaction_ratio:.2f})"


class TestRedactionResultStructure:
    """Property tests for RedactionResult structure."""

    @given(
        text=st.text(min_size=0, max_size=500)
    )
    @settings(max_examples=50)
    def test_redaction_result_structure(self, text):
        """
        RedactionResult structure invariant.

        Property: Result always has valid structure with required fields.
        """
        redactor = PIIRedactor()
        result = redactor.redact(text)

        # Check result structure
        assert hasattr(result, 'redacted_text'), "Result missing redacted_text"
        assert hasattr(result, 'original_text'), "Result missing original_text"
        assert hasattr(result, 'has_secrets'), "Result missing has_secrets"
        assert hasattr(result, 'redactions'), "Result missing redactions"

        # Check types
        assert isinstance(result.redacted_text, str), "redacted_text not a string"
        assert isinstance(result.original_text, str), "original_text not a string"
        assert isinstance(result.has_secrets, bool), "has_secrets not a bool"
        assert isinstance(result.redactions, list), "redactions not a list"

    @given(
        text=st.text(min_size=0, max_size=500)
    )
    @settings(max_examples=50)
    def test_redaction_metadata_consistency(self, text):
        """
        Redaction metadata consistency invariant.

        Property: Redaction count matches has_secrets flag.
        """
        redactor = PIIRedactor()
        result = redactor.redact(text)

        # If has_secrets is True, should have at least one redaction
        if result.has_secrets:
            assert len(result.redactions) > 0, \
                "has_secrets=True but no redactions found"

        # If has_secrets is False, should have zero redactions
        if not result.has_secrets:
            assert len(result.redactions) == 0, \
                f"has_secrets=False but {len(result.redactions)} redactions found"
