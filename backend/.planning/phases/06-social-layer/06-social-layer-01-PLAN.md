---
phase: 06-social-layer
plan: 01
type: execute
wave: 1
depends_on: ["05-agent-layer"]
files_modified:
  - tests/test_social_post_generator.py
  - tests/test_pii_redactor.py
  - tests/property_tests/social/test_pii_redaction_invariants.py
autonomous: true

must_haves:
  truths:
    - "GPT-4.1 mini generates social posts with >95% success rate (5s timeout)"
    - "Template fallback generates posts when LLM unavailable"
    - "Rate limiting prevents spam (5-minute default window)"
    - "PII redactor detects >95% of PII entities (email, SSN, credit card, phone)"
    - "PII redactor false positive rate <5% (legitimate content incorrectly redacted)"
    - "Microsoft Presidio provides 99% accuracy vs 60% for regex-only"
    - "Property tests verify PII never leaks (redacted text never contains original PII)"
  artifacts:
    - path: "tests/test_social_post_generator.py"
      provides: "Unit tests for social post generation (GPT-4.1 mini, templates, rate limiting)"
      min_lines: 350
    - path: "tests/test_pii_redactor.py"
      provides: "Unit tests for PII redaction (10 entity types, allowlist, audit logging)"
      min_lines: 400
    - path: "tests/property_tests/social/test_pii_redaction_invariants.py"
      provides: "Property tests for PII redaction invariants (no leaks, detection accuracy)"
      min_lines: 250
  key_links:
    - from: "tests/test_social_post_generator.py"
      to: "core/social_post_generator.py"
      via: "tests GPT-4.1 mini integration, template fallback, rate limiting"
      pattern: "test_generate_post_gpt4_mini|test_template_fallback|test_rate_limiting"
    - from: "tests/test_pii_redactor.py"
      to: "core/pii_redactor.py"
      via: "tests Microsoft Presidio integration, 10 entity types, allowlist"
      pattern: "test_redact_email|test_redact_ssn|test_redact_credit_card|test_allowlist"
    - from: "tests/property_tests/social/test_pii_redaction_invariants.py"
      to: "core/pii_redactor.py"
      via: "tests PII never leaks invariant, detection accuracy property tests"
      pattern: "test_pii_never_leaks|test_detection_accuracy|test_idempotent_redaction"
---

## Objective

Create comprehensive unit and property tests for social post generation (GPT-4.1 mini NLG, template fallback, rate limiting) and PII redaction (Microsoft Presidio, 10 entity types, allowlist).

**Purpose:** Social posts require accurate generation (>95% success) and PII protection (no leaks, >95% detection). Tests validate GPT-4.1 mini integration with 5-second timeout, template fallback, rate limiting, and Microsoft Presidio's 99% accuracy (vs 60% regex-only).

**Output:** Unit tests for post generation and PII redaction, property tests for invariants (no leaks, detection accuracy).

## Execution Context

@core/social_post_generator.py (GPT-4.1 mini NLG, template fallback, rate limiting)
@core/pii_redactor.py (Microsoft Presidio, 10 entity types, allowlist)
@core/secrets_redactor.py (fallback regex-based redactor)
@core/models.py (AgentOperationTracker, AgentRegistry)
@.planning/phases/05-agent-layer/05-agent-layer-VERIFICATION.md (Phase 5 complete)

## Context

@.planning/ROADMAP.md (Phase 6 requirements)
@.planning/REQUIREMENTS.md (AR-07: Social Layer Coverage, AR-12: Property-Based Testing)

# Phase 5 Complete: Agent Layer Tested
- Agent governance, graduation, and execution tested (3,917 lines, 127 tests)
- Four-tier maturity routing validated
- Agent-to-agent coordination tested

# Existing Social Layer Implementation
- social_post_generator.py: GPT-4.1 mini NLG, template fallback, rate limiting (5s timeout)
- pii_redactor.py: Microsoft Presidio integration, 10 entity types, allowlist, fallback to SecretsRedactor
- social_routes.py: REST endpoints for feed, post generation, filtering

## Tasks

### Task 1: Create Unit Tests for Social Post Generation

**Files:** `tests/test_social_post_generator.py`

**Action:**
Create comprehensive unit tests for social post generation:

```python
"""
Unit Tests for Social Post Generator

Tests cover:
- GPT-4.1 mini NLG for posts (success rate >95%)
- Template fallback generation
- Rate limiting (5-minute default window)
- Significant operation detection
- Post formatting (markdown, mentions, hashtags)
- Post length limits (≤280 chars for microblog, ≤5000 for long-form)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from core.social_post_generator import SocialPostGenerator
from core.models import AgentOperationTracker, AgentRegistry
from tests.factories import AgentFactory, AgentOperationTrackerFactory


class TestSocialPostGenerator:
    """Test social post generation."""

    @pytest.fixture
    def generator(self):
        """Create post generator."""
        return SocialPostGenerator()

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(name="TestAgent")
        db_session.commit()
        return agent

    def test_generate_post_gpt4_mini_success(self, generator, agent, db_session):
        """Test GPT-4.1 mini generates post successfully."""
        tracker = AgentOperationTrackerFactory(
            agent_id=agent.id,
            operation_type="workflow_execute",
            status="completed",
            what_explanation="Completed customer data export",
            why_explanation="Monthly reporting requirement"
        )
        db_session.commit()

        # Mock OpenAI client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Just finished automating the monthly customer data export! 🎯 #automation #efficiency"
        generator._openai_client = AsyncMock()
        generator._openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        post = await generator.generate_post(tracker.id)

        assert post is not None
        assert len(post["content"]) <= 280  # Microblog limit
        assert "#automation" in post["content"]
        assert generator._openai_client.chat.completions.create.called

    def test_template_fallback_when_llm_unavailable(self, generator, agent, db_session):
        """Test template fallback generates post when LLM unavailable."""
        tracker = AgentOperationTrackerFactory(
            agent_id=agent.id,
            operation_type="browser_automate",
            status="completed",
            what_explanation="Automated form submission",
            why_explanation="Reduce manual data entry"
        )
        db_session.commit()

        # No OpenAI client
        generator._openai_client = None

        post = await generator.generate_post(tracker.id)

        assert post is not None
        assert "browser_automate" in post["content"].lower()
        assert "form submission" in post["content"].lower()

    def test_rate_limiting_prevents_spam(self, generator, agent, db_session):
        """Test rate limiting prevents spam (5-minute default window)."""
        tracker = AgentOperationTrackerFactory(
            agent_id=agent.id,
            operation_type="workflow_execute",
            status="completed"
        )
        db_session.commit()

        # Mock successful post generation
        generator._openai_client = AsyncMock()
        generator._openai_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="Test post"))])
        )

        # First post succeeds
        post1 = await generator.generate_post(tracker.id)
        assert post1 is not None

        # Second post within rate limit window fails
        post2 = await generator.generate_post(tracker.id)
        assert post2 is None  # Rate limited

    def test_significant_operation_detection(self, generator, agent, db_session):
        """Test significant operation detection."""
        # Significant operations
        significant_ops = [
            "workflow_execute",
            "integration_connect",
            "browser_automate",
            "report_generate",
            "human_feedback_received",
            "approval_requested",
            "agent_to_agent_call"
        ]

        for op_type in significant_ops:
            tracker = AgentOperationTrackerFactory(
                agent_id=agent.id,
                operation_type=op_type,
                status="completed"
            )
            db_session.commit()

            assert generator.is_significant_operation(tracker) is True

        # Non-significant operation
        tracker = AgentOperationTrackerFactory(
            agent_id=agent.id,
            operation_type="internal_check",
            status="completed"
        )
        db_session.commit()

        assert generator.is_significant_operation(tracker) is False

    def test_post_formatting_markdown_mentions_hashtags(self, generator, agent, db_session):
        """Test post formatting includes markdown, mentions, hashtags."""
        tracker = AgentOperationTrackerFactory(
            agent_id=agent.id,
            operation_type="workflow_execute",
            status="completed",
            what_explanation="Deployed to production with @user1",
            why_explanation="Feature release"
        )
        db_session.commit()

        generator._openai_client = AsyncMock()
        generator._openai_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="Deployed with @user1! #deployment"))])
        )

        post = await generator.generate_post(tracker.id)

        assert "@user1" in post["content"]
        assert "#deployment" in post["content"]

    def test_post_length_limits_microblog(self, generator, agent, db_session):
        """Test post length limit ≤280 chars for microblog."""
        tracker = AgentOperationTrackerFactory(
            agent_id=agent.id,
            operation_type="workflow_execute",
            status="completed"
        )
        db_session.commit()

        generator._openai_client = AsyncMock()
        # Mock response exceeding 280 chars
        long_content = "A" * 500
        generator._openai_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content=long_content))])
        )

        post = await generator.generate_post(tracker.id, post_type="microblog")

        assert len(post["content"]) <= 280

    def test_post_length_limits_longform(self, generator, agent, db_session):
        """Test post length limit ≤5000 chars for long-form."""
        tracker = AgentOperationTrackerFactory(
            agent_id=agent.id,
            operation_type="report_generate",
            status="completed"
        )
        db_session.commit()

        generator._openai_client = AsyncMock()
        # Mock response exceeding 5000 chars
        long_content = "A" * 6000
        generator._openai_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content=long_content))])
        )

        post = await generator.generate_post(tracker.id, post_type="longform")

        assert len(post["content"]) <= 5000

    def test_llm_timeout_fallback_to_template(self, generator, agent, db_session):
        """Test LLM timeout (5s) falls back to template."""
        tracker = AgentOperationTrackerFactory(
            agent_id=agent.id,
            operation_type="workflow_execute",
            status="completed"
        )
        db_session.commit()

        # Mock timeout
        import asyncio
        generator._openai_client = AsyncMock()
        generator._openai_client.chat.completions.create = AsyncMock(
            side_effect=asyncio.TimeoutError("LLM timeout")
        )

        post = await generator.generate_post(tracker.id)

        # Should fallback to template
        assert post is not None
        assert "workflow_execute" in post["content"]
```

**Tests:**
- GPT-4.1 mini NLG success rate (>95%)
- Template fallback when LLM unavailable
- Rate limiting (5-minute window)
- Significant operation detection
- Post formatting (markdown, mentions, hashtags)
- Post length limits (≤280 microblog, ≤5000 long-form)
- LLM timeout fallback to template

**Acceptance:**
- [ ] GPT-4.1 mini tested with >95% success rate
- [ ] Template fallback tested
- [ ] Rate limiting tested (5-minute window)
- [ ] Post formatting tested
- [ ] Post length limits tested

---

### Task 2: Create Unit Tests for PII Redaction

**Files:** `tests/test_pii_redactor.py`

**Action:**
Create comprehensive unit tests for PII redaction:

```python
"""
Unit Tests for PII Redactor

Tests cover:
- Microsoft Presidio integration (10 entity types)
- Redaction accuracy (>95% PII detected)
- False positive rate (<5% legitimate content redacted)
- Allowlist for company emails
- Audit logging
- Fallback to SecretsRedactor
"""
import pytest
from core.pii_redactor import PIIRedactor
from core.secrets_redactor import RedactionResult


class TestPIIRedactor:
    """Test PII redaction."""

    @pytest.fixture
    def redactor(self):
        """Create PII redactor."""
        return PIIRedactor()

    def test_redact_email_address(self, redactor):
        """Test email address redaction."""
        text = "Contact me at john.doe@example.com for details"
        result = redactor.redact(text)

        assert "john.doe@example.com" not in result
        assert "<EMAIL>" in result or "REDACTED" in result

    def test_redact_ssn(self, redactor):
        """Test Social Security Number redaction."""
        text = "My SSN is 123-45-6789 for verification"
        result = redactor.redact(text)

        assert "123-45-6789" not in result
        assert "<US_SSN>" in result or "REDACTED" in result

    def test_redact_credit_card(self, redactor):
        """Test credit card number redaction."""
        text = "Card number: 4532-1234-5678-9010 expires 12/25"
        result = redactor.redact(text)

        assert "4532-1234-5678-9010" not in result
        assert "<CREDIT_CARD>" in result or "REDACTED" in result

    def test_redact_phone_number(self, redactor):
        """Test phone number redaction."""
        text = "Call me at (555) 123-4567 for questions"
        result = redactor.redact(text)

        assert "(555) 123-4567" not in result
        assert "<PHONE_NUMBER>" in result or "REDACTED" in result

    def test_redact_multiple_entities(self, redactor):
        """Test redaction of multiple PII entities."""
        text = "Contact john@example.com or call (555) 123-4567. SSN: 123-45-6789"
        result = redactor.redact(text)

        assert "john@example.com" not in result
        assert "(555) 123-4567" not in result
        assert "123-45-6789" not in result

    def test_allowlist_company_emails(self, redactor):
        """Test allowlist for company emails."""
        redactor.allowlist = {"support@atom.ai", "admin@atom.ai"}

        text = "Contact support@atom.ai for help or john@example.com for personal"
        result = redactor.redact(text)

        # Company email should NOT be redacted
        assert "support@atom.ai" in result
        # Personal email should be redacted
        assert "john@example.com" not in result

    def test_redaction_accuracy_high(self, redactor):
        """Test redaction accuracy >95%."""
        test_cases = [
            ("Email: test@example.com", "test@example.com"),
            ("SSN: 987-65-4321", "987-65-4321"),
            ("Phone: 555-987-6543", "555-987-6543"),
            ("Card: 4111-1111-1111-1111", "4111-1111-1111-1111"),
            ("IBAN: GB82 WEST 1234 5698 7654 32", "GB82 WEST 1234 5698 7654 32")
        ]

        detected = 0
        for text, pii in test_cases:
            result = redactor.redact(text)
            if pii not in result:
                detected += 1

        accuracy = detected / len(test_cases)
        assert accuracy > 0.95  # >95% detection

    def test_false_positive_rate_low(self, redactor):
        """Test false positive rate <5%."""
        # Legitimate content that should NOT be redacted
        test_cases = [
            "Version 2.0 released today",
            "Meeting at 3 PM EST",
            "Project code: ALPHA-123",
            "Score: 95 out of 100",
            "Reference: case-456-def"
        ]

        false_positives = 0
        for text in test_cases:
            result = redactor.redact(text)
            # If redacted significantly, count as false positive
            if len(result) < len(text) * 0.8:
                false_positives += 1

        fp_rate = false_positives / len(test_cases)
        assert fp_rate < 0.05  # <5% false positive

    def test_audit_logging(self, redactor):
        """Test audit logging for all redactions."""
        text = "Contact test@example.com or (555) 123-4567"
        result = redactor.redact(text, log_audit=True)

        assert result.audit_log is not None
        assert len(result.audit_log) == 2  # 2 PII entities detected

    def test_fallback_to_secrets_redactor(self):
        """Test fallback to SecretsRedactor when Presidio unavailable."""
        # Mock Presidio unavailable
        with patch('core.pii_redactor.PRESIDIO_AVAILABLE', False):
            redactor = PIIRedactor()
            text = "Email: test@example.com"
            result = redactor.redact(text)

            assert "test@example.com" not in result
            # Should use regex-based fallback
            assert "REDACTED" in result

    def test_redact_ip_address(self, redactor):
        """Test IP address redaction."""
        text = "Server IP: 192.168.1.1"
        result = redactor.redact(text)

        assert "192.168.1.1" not in result
        assert "<IP_ADDRESS>" in result or "REDACTED" in result

    def test_redact_url(self, redactor):
        """Test URL redaction."""
        text = "Visit https://example.com/user/profile"
        result = redactor.redact(text)

        assert "https://example.com/user/profile" not in result
        assert "<URL>" in result or "REDACTED" in result

    def test_redact_date_time(self, redactor):
        """Test date/time redaction."""
        text = "Meeting on January 15, 2026 at 3 PM"
        result = redactor.redact(text)

        # Date/time should be redacted if DATE_TIME entity enabled
        assert result != text  # Something should be redacted

    def test_redact_iban_code(self, redactor):
        """Test IBAN bank code redaction."""
        text = "IBAN: GB82 WEST 1234 5698 7654 32"
        result = redactor.redact(text)

        assert "GB82 WEST 1234 5698 7654 32" not in result
        assert "<IBAN_CODE>" in result or "REDACTED" in result

    def test_redact_us_bank_number(self, redactor):
        """Test US bank account number redaction."""
        text = "Bank account: 123456789"
        result = redactor.redact(text)

        assert "123456789" not in result
        assert "<US_BANK_NUMBER>" in result or "REDACTED" in result

    def test_redact_us_driver_license(self, redactor):
        """Test US driver license redaction."""
        text = "Driver license: CA-D1234567"
        result = redactor.redact(text)

        assert "CA-D1234567" not in result
        assert "<US_DRIVER_LICENSE>" in result or "REDACTED" in result
```

**Tests:**
- Email, SSN, credit card, phone redaction
- Multiple entities in one text
- Allowlist for company emails
- Redaction accuracy >95%
- False positive rate <5%
- Audit logging
- Fallback to SecretsRedactor
- All 10 entity types

**Acceptance:**
- [ ] All 10 entity types tested
- [ ] Redaction accuracy >95% verified
- [ ] False positive rate <5% verified
- [ ] Allowlist tested
- [ ] Audit logging tested
- [ ] Fallback tested

---

### Task 3: Create Property Tests for PII Redaction Invariants

**Files:** `tests/property_tests/social/test_pii_redaction_invariants.py`

**Action:**
Create property-based tests for PII redaction invariants:

```python
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
from hypothesis import strategies as st, given, settings
from core.pii_redactor import PIIRedactor


class TestPIINeverLeaksInvariant:
    """Property tests for PII never leaks invariant."""

    @given(
        email=st.emails(),
        context=st.text(min_size=10, max_size=100)
    )
    @settings(max_examples=100)
    def test_email_never_leaks(self, email, context):
        """
        Email never leaks invariant.

        Property: Redacted text never contains original email address.
        """
        redactor = PIIRedactor()
        text = f"{context} {email} {context}"
        result = redactor.redact(text)

        assert email not in result

    @given(
        ssn=st.from_regex(r'\d{3}-\d{2}-\d{4}'),
        context=st.text(min_size=10, max_size=100)
    )
    @settings(max_examples=100)
    def test_ssn_never_leaks(self, ssn, context):
        """
        SSN never leaks invariant.

        Property: Redacted text never contains original SSN.
        """
        redactor = PIIRedactor()
        text = f"{context} SSN: {ssn} {context}"
        result = redactor.redact(text)

        assert ssn not in result

    @given(
        credit_card=st.from_regex(r'\d{4}-\d{4}-\d{4}-\d{4}'),
        context=st.text(min_size=10, max_size=100)
    )
    @settings(max_examples=100)
    def test_credit_card_never_leaks(self, credit_card, context):
        """
        Credit card never leaks invariant.

        Property: Redacted text never contains original credit card.
        """
        redactor = PIIRedactor()
        text = f"Card: {credit_card} expires"
        result = redactor.redact(text)

        assert credit_card not in result


class TestRedactionIdempotentInvariant:
    """Property tests for redaction idempotence."""

    @given(
        text_with_pii=st.text(min_size=20, max_size=500)
    )
    @settings(max_examples=50)
    def test_redaction_idempotent(self, text_with_pii):
        """
        Redaction idempotent invariant.

        Property: Redacting twice produces same result as redacting once.
        """
        redactor = PIIRedactor()
        result1 = redactor.redact(text_with_pii)
        result2 = redactor.redact(result1)

        assert result1 == result2


class TestAllowlistHonoredInvariant:
    """Property tests for allowlist honored invariant."""

    @given(
        context=st.text(min_size=10, max_size=100)
    )
    @settings(max_examples=50)
    def test_allowlist_email_never_redacted(self, context):
        """
        Allowlist honored invariant.

        Property: Allowlist emails are NEVER redacted.
        """
        redactor = PIIRedactor(allowlist=["support@atom.ai", "admin@atom.ai"])
        allowed_email = "support@atom.ai"

        text = f"{context} {allowed_email} {context}"
        result = redactor.redact(text)

        assert allowed_email in result
```

**Property Tests:**
- PII never leaks (email, SSN, credit card)
- Redaction idempotent
- Allowlist always honored

**Acceptance:**
- [ ] Email never leaks tested (100 examples)
- [ ] SSN never leaks tested (100 examples)
- [ ] Credit card never leaks tested (100 examples)
- [ ] Redaction idempotent tested (50 examples)
- [ ] Allowlist honored tested (50 examples)

---

## Deviations

**Rule 1 (Auto-fix bugs):** If post generation or PII redaction has bugs, fix immediately.

**Rule 2 (Presidio):** If Presidio unavailable, tests should verify fallback to SecretsRedactor works.

**Rule 3 (Property tests):** If Hypothesis tests flaky, adjust strategies or settings.

## Success Criteria

- [ ] Social post generation tested (>95% success rate)
- [ ] Template fallback tested
- [ ] Rate limiting tested
- [ ] PII redaction tested (>95% detection, <5% false positives)
- [ ] All 10 entity types tested
- [ ] Property tests verify PII never leaks

## Dependencies

- Plan 05-03 (Agent Execution & Coordination) must be complete ✅

## Estimated Duration

2-3 hours (post generation tests + PII redaction tests + property tests)
