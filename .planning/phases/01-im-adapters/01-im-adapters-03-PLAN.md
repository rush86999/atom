---
phase: 01-im-adapters
plan: 03
type: tdd
wave: 2
depends_on: ["01-im-adapters-01"]
files_modified:
  - backend/tests/test_im_governance.py
  - backend/tests/property_tests/im_governance_invariants.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Invalid webhook signatures are rejected (403 Forbidden)"
    - "Rate limiting blocks 11th request within 1 minute (429 Too Many Requests)"
    - "STUDENT agents blocked from IM triggers (403 Forbidden)"
    - "All IM interactions logged to IMAuditLog table"
    - "Property tests verify rate limit invariants (never exceeded)"
    - "Property tests verify HMAC signature invariants"
  artifacts:
    - path: "backend/tests/test_im_governance.py"
      provides: "Unit tests for IMGovernanceService security features"
      min_lines: 300
      exports: ["test_webhook_spoofing", "test_rate_limiting", "test_governance_checks", "test_audit_trail"]
    - path: "backend/tests/property_tests/im_governance_invariants.py"
      provides: "Property-based tests for IM governance invariants"
      min_lines: 200
      exports: ["test_rate_limit_never_exceeded", "test_hmac_signature_invariant"]
  key_links:
    - from: "backend/tests/test_im_governance.py"
      to: "backend/core/im_governance_service.py"
      via: "Direct imports and mocking"
      pattern: "from core.im_governance_service import IMGovernanceService"
    - from: "backend/tests/property_tests/im_governance_invariants.py"
      to: "backend/core/im_governance_service.py"
      via: "Hypothesis strategies for testing"
      pattern: "@given.*st.*"
---

<objective>
Create comprehensive test suite for IMGovernanceService using TDD approach. Test webhook signature verification, rate limiting, governance checks, and audit trail logging. Use property-based tests for invariants (rate limit never exceeded, HMAC validation always constant-time).

Purpose: Validate security guarantees and prevent regressions in IM governance layer
Output: Passing test suite with 80%+ coverage on IMGovernanceService
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-im-adapters/01-im-adapters-CONTEXT.md
@.planning/phases/01-im-adapters/01-im-adapters-RESEARCH.md
@.planning/phases/01-im-adapters/01-im-adapters-01-SUMMARY.md

# Existing test patterns
@backend/tests/unit/test_agent_governance_service.py
@backend/tests/property_tests/governance/test_governance_cache_invariants.py
@backend/tests/security/test_authorization.py
</context>

<feature>
  <name>IMGovernanceService Security Features</name>
  <files>
    - backend/tests/test_im_governance.py
    - backend/tests/property_tests/im_governance_invariants.py
    - backend/core/im_governance_service.py
  </files>
  <behavior>
    IMGovernanceService provides three-stage security pipeline:

    1. **Webhook Signature Verification**:
       - Valid signature → 200 OK, proceed to processing
       - Invalid signature → 403 Forbidden
       - Missing signature → 403 Forbidden

    2. **Rate Limiting**:
       - 1-10 requests → 200 OK
       - 11th request within 1 minute → 429 Too Many Requests
       - After 1 minute → Reset, 200 OK

    3. **Governance Checks**:
       - STUDENT agent → 403 Forbidden
       - INTERN+ agent → 200 OK
       - Blocked user → 403 Forbidden

    4. **Audit Trail**:
       - All interactions logged to IMAuditLog
       - Async logging (non-blocking)
       - Contains platform, sender_id, action, success, rate_limited, signature_valid

    Test Cases:
    - Valid Telegram signature → allowed
    - Invalid Telegram signature → 403
    - Valid WhatsApp signature → allowed
    - Invalid WhatsApp signature → 403
    - 10 requests in 1 minute → all allowed
    - 11th request in 1 minute → 429
    - STUDENT agent tries IM trigger → 403
    - AUTONOMOUS agent tries IM trigger → allowed
    - All requests create IMAuditLog entry
  </behavior>
  <implementation>
    RED phase: Write failing tests
    GREEN phase: Implement IMGovernanceService (already done in Plan 01)
    REFACTOR phase: Optimize test code and fix any issues
  </implementation>
</feature>

<tasks>

<task type="auto">
  <name>RED: Write failing unit tests for IMGovernanceService</name>
  <files>backend/tests/test_im_governance.py</files>
  <action>
Create backend/tests/test_im_governance.py with failing tests:

```python
"""
Tests for IMGovernanceService - IM platform security layer

Tests cover:
- Webhook signature verification (Telegram, WhatsApp)
- Rate limiting (10 req/min per user)
- Governance checks (STUDENT blocked, INTERN+ allowed)
- Audit trail logging
"""

import pytest
import hmac
import hashlib
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, HTTPException

from core.im_governance_service import IMGovernanceService


@pytest.fixture
def im_governance():
    """Create IMGovernanceService instance for testing"""
    return IMGovernanceService()


@pytest.fixture
def mock_telegram_request():
    """Create mock Telegram webhook request"""
    mock_request = Mock(spec=Request)
    mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "test_secret"}
    mock_request.path_params = {"platform": "telegram"}
    mock_request.query_params = {}
    mock_request.body = AsyncMock(return_value=b'{"message": {"from": {"id": "123"}, "text": "test"}}')
    mock_request.json = AsyncMock(return_value={"message": {"from": {"id": "123"}, "text": "test"}})
    return mock_request


@pytest.fixture
def mock_whatsapp_request():
    """Create mock WhatsApp webhook request with valid signature"""
    payload = b'{"entry": [{"changes": [{"value": {"messages": [{"from": "1234567890", "type": "text", "text": {"body": "test"}}]}}]}]}'
    signature = hmac.new(
        b"test_secret",
        payload,
        hashlib.sha256
    ).hexdigest()

    mock_request = Mock(spec=Request)
    mock_request.headers = {"X-Hub-Signature-256": f"sha256={signature}"}
    mock_request.path_params = {"platform": "whatsapp"}
    mock_request.query_params = {}
    mock_request.body = AsyncMock(return_value=payload)
    mock_request.json = AsyncMock(return_value={"entry": [{"changes": [{"value": {"messages": [{"from": "1234567890"}]}}]}]})
    return mock_request


class TestWebhookSignatureVerification:
    """Test webhook signature verification"""

    @pytest.mark.asyncio
    async def test_valid_telegram_signature_accepted(self, im_governance, mock_telegram_request):
        """Valid Telegram signature should be accepted"""
        result = await im_governance.verify_and_rate_limit(
            mock_telegram_request,
            await mock_telegram_request.body()
        )
        assert result["verified"] is True
        assert result["platform"] == "telegram"

    @pytest.mark.asyncio
    async def test_invalid_telegram_signature_rejected(self, im_governance, mock_telegram_request):
        """Invalid Telegram signature should be rejected"""
        mock_telegram_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"}

        with pytest.raises(HTTPException) as exc:
            await im_governance.verify_and_rate_limit(
                mock_telegram_request,
                await mock_telegram_request.body()
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_valid_whatsapp_signature_accepted(self, im_governance, mock_whatsapp_request):
        """Valid WhatsApp signature should be accepted"""
        result = await im_governance.verify_and_rate_limit(
            mock_whatsapp_request,
            await mock_whatsapp_request.body()
        )
        assert result["verified"] is True
        assert result["platform"] == "whatsapp"

    @pytest.mark.asyncio
    async def test_invalid_whatsapp_signature_rejected(self, im_governance, mock_whatsapp_request):
        """Invalid WhatsApp signature should be rejected"""
        mock_whatsapp_request.headers = {"X-Hub-Signature-256": "sha256=invalid"}

        with pytest.raises(HTTPException) as exc:
            await im_governance.verify_and_rate_limit(
                mock_whatsapp_request,
                await mock_whatsapp_request.body()
            )
        assert exc.value.status_code == 403


class TestRateLimiting:
    """Test rate limiting (10 req/min per user)"""

    @pytest.mark.asyncio
    async def test_first_10_requests_allowed(self, im_governance, mock_telegram_request):
        """First 10 requests within 1 minute should be allowed"""
        for i in range(10):
            result = await im_governance.verify_and_rate_limit(
                mock_telegram_request,
                await mock_telegram_request.body()
            )
            assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_11th_request_blocked(self, im_governance, mock_telegram_request):
        """11th request within 1 minute should be blocked"""
        # First 10 should succeed
        for i in range(10):
            await im_governance.verify_and_rate_limit(
                mock_telegram_request,
                await mock_telegram_request.body()
            )

        # 11th should fail
        with pytest.raises(HTTPException) as exc:
            await im_governance.verify_and_rate_limit(
                mock_telegram_request,
                await mock_telegram_request.body()
            )
        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_different_users_not_affected(self, im_governance, mock_telegram_request):
        """Rate limit should be per-user, not global"""
        # User 123 hits limit
        for i in range(10):
            await im_governance.verify_and_rate_limit(
                mock_telegram_request,
                await mock_telegram_request.body()
            )

        # User 456 should still be allowed
        mock_telegram_request.json = AsyncMock(return_value={"message": {"from": {"id": "456"}, "text": "test"}})
        result = await im_governance.verify_and_rate_limit(
            mock_telegram_request,
            await mock_telegram_request.body()
        )
        assert result["verified"] is True


class TestGovernanceChecks:
    """Test governance maturity checks"""

    @pytest.mark.asyncio
    async def test_blocked_user_rejected(self, im_governance):
        """Blocked user should be rejected"""
        with patch("core.governance_cache.get_governance_cache") as mock_cache:
            mock_cache.return_value.get.return_value = True  # User blocked

            with pytest.raises(HTTPException) as exc:
                await im_governance.check_permissions("123", "telegram")
            assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_allowed_user_accepted(self, im_governance):
        """Allowed user should pass checks"""
        with patch("core.governance_cache.get_governance_cache") as mock_cache:
            mock_cache.return_value.get.return_value = None  # Not blocked

            result = await im_governance.check_permissions("123", "telegram")
            assert result["allowed"] is True


class TestAuditTrail:
    """Test audit trail logging"""

    @pytest.mark.asyncio
    async def test_audit_log_created_on_success(self, im_governance):
        """Successful request should create audit log"""
        with patch("core.im_governance_service.asyncio.create_task") as mock_create_task:
            await im_governance.log_to_audit_trail(
                platform="telegram",
                sender_id="123",
                payload={"test": "data"},
                action="webhook_received",
                success=True
            )
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_log_created_on_failure(self, im_governance):
        """Failed request should create audit log with failure flag"""
        with patch("core.im_governance_service.asyncio.create_task") as mock_create_task:
            await im_governance.log_to_audit_trail(
                platform="telegram",
                sender_id="123",
                payload={"test": "data"},
                action="webhook_received",
                success=False
            )
            mock_create_task.assert_called_once()
```

Run tests (they should fail because IMGovernanceService may not be complete):
```bash
cd backend
pytest tests/test_im_governance.py -v
```
  </action>
  <verify>
```bash
cd backend
python -m pytest tests/test_im_governance.py -v --tb=short 2>&1 | head -50
```
  </verify>
  <done>
test_im_governance.py created with:
- TestWebhookSignatureVerification class with 4 tests
- TestRateLimiting class with 3 tests
- TestGovernanceChecks class with 2 tests
- TestAuditTrail class with 2 tests
- Fixtures for mock Telegram and WhatsApp requests
- All tests initially fail (RED phase)
  </done>
</task>

<task type="auto">
  <name>GREEN: Implement IMGovernanceService to pass tests</name>
  <files>backend/core/im_governance_service.py</files>
  <action>
IMGovernanceService was created in Plan 01, so verify it passes the tests. If tests fail, update implementation:

Run tests:
```bash
cd backend
pytest tests/test_im_governance.py -v
```

If tests fail, fix IMGovernanceService:

1. **If signature verification tests fail**: Ensure adapters are correctly called and `hmac.compare_digest()` is used
2. **If rate limiting tests fail**: Ensure SlowAPI is configured with per-user keys
3. **If governance tests fail**: Ensure GovernanceCache integration is correct
4. **If audit tests fail**: Ensure asyncio.create_task() is called

Typical fixes:
- Import: `from core.communication.adapters.telegram import TelegramAdapter`
- Import: `from core.communication.adapters.whatsapp import WhatsAppAdapter`
- Fix: `key_func=lambda request: f"{request.path_params.get('platform')}_{sender_id}"` for per-user rate limiting

After fixes, all tests should pass:
```bash
pytest tests/test_im_governance.py -v
```

Expected output: 11 tests passing (may have some skipped if features not yet complete)
  </action>
  <verify>
```bash
cd backend
pytest tests/test_im_governance.py -v --tb=line
grep -E "PASSED|FAILED|ERROR" <<< $(pytest tests/test_im_governance.py -v 2>&1)
```
  </verify>
  <done>
All unit tests passing:
- 4 signature verification tests passing
- 3 rate limiting tests passing
- 2 governance check tests passing
- 2 audit trail tests passing
- IMGovernanceService implementation verified
  </done>
</task>

<task type="auto">
  <name>Create property-based tests for invariants</name>
  <files>backend/tests/property_tests/im_governance_invariants.py</files>
  <action>
Create backend/tests/property_tests/im_governance_invariants.py:

```python
"""
Property-based tests for IMGovernanceService invariants

Uses Hypothesis to test security invariants:
- Rate limit is never exceeded (can't make 11th request within 1 minute)
- HMAC signature validation is constant-time (prevents timing attacks)
- Audit log is always created (no IM interaction without trace)
"""

import pytest
import hmac
import hashlib
from hypothesis import given, strategies as st, settings, example
from unittest.mock import Mock, AsyncMock, patch

from core.im_governance_service import IMGovernanceService


@pytest.fixture
def im_governance():
    return IMGovernanceService()


class TestRateLimitInvariant:
    """
    INVARIANT: Rate limit is never exceeded.

    Property: For any sequence of n requests where n > 10 within 1 minute,
    at least (n - 10) requests must be rejected with 429 status.

    VALIDATED_BUG: None yet - this is a preventive invariant.
    """

    @given(request_count=st.integers(min_value=11, max_value=100))
    @settings(max_examples=50)  # IO-bound test, use 50 examples
    @pytest.mark.asyncio
    async def test_rate_limit_never_exceeded(self, im_governance, request_count):
        """
        If sending request_count requests within 1 minute,
        at most 10 should succeed, rest should fail with 429.
        """
        mock_request = Mock()
        mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "test_secret"}
        mock_request.path_params = {"platform": "telegram"}
        mock_request.query_params = {}
        mock_request.body = AsyncMock(return_value=b'{"message": {"from": {"id": "123"}, "text": "test"}}')
        mock_request.json = AsyncMock(return_value={"message": {"from": {"id": "123"}, "text": "test"}})

        successful = 0
        rate_limited = 0

        for i in range(request_count):
            try:
                await im_governance.verify_and_rate_limit(mock_request, await mock_request.body())
                successful += 1
            except Exception:
                # If status_code is 429, it's rate limited
                rate_limited += 1

        # Invariant: At most 10 successful, rest rate limited
        assert successful <= 10, f"Rate limit exceeded: {successful} > 10 successful requests"
        assert rate_limited >= (request_count - 10), f"Expected at least {request_count - 10} rate-limited, got {rate_limited}"


class TestHMACSignatureInvariant:
    """
    INVARIANT: HMAC signature validation is constant-time.

    Property: Signature verification time is independent of input similarity,
    preventing timing attacks where attackers measure response times to guess valid signatures.

    Uses hmac.compare_digest() which provides constant-time comparison.
    """

    @given(payload=st.binary(min_size=10, max_size=1000))
    @settings(max_examples=100)
    def test_hmac_signature_invariant(self, payload):
        """
        For any payload, signature verification should use constant-time comparison.

        This test verifies that hmac.compare_digest() is used, not ==.
        """
        # Generate valid signature
        secret = b"test_secret"
        valid_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()

        # Test with valid signature
        is_valid = hmac.compare_digest(valid_signature, hmac.new(secret, payload, hashlib.sha256).hexdigest())
        assert is_valid is True, "Valid signature should verify"

        # Test with invalid signature (one bit flipped)
        invalid_signature = valid_signature[:-1] + ("0" if valid_signature[-1] != "0" else "1")
        is_invalid = hmac.compare_digest(invalid_signature, hmac.new(secret, payload, hashlib.sha256).hexdigest())
        assert is_invalid is False, "Invalid signature should reject"

    @given(payload=st.binary(min_size=10, max_size=1000))
    @settings(max_examples=100)
    def test_signature_format_validation(self, payload):
        """
        Signature format must be "sha256=<hash>" to be valid.
        """
        # Valid format
        hash_value = hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
        valid_format = f"sha256={hash_value}"
        assert valid_format.startswith("sha256="), "Signature must start with 'sha256='"

        # Invalid formats
        assert not valid_format.startswith("sha1="), "SHA1 signatures should be rejected"
        assert not valid_format.startswith("md5="), "MD5 signatures should be rejected"


class TestAuditCompletenessInvariant:
    """
    INVARIANT: No IM interaction without audit log entry.

    Property: For every request that reaches verify_and_rate_limit(),
    a corresponding audit log entry must be created (async or sync).

    VALIDATED_BUG: None yet - this is a compliance invariant.
    """

    @given(platform=st.sampled_from(["telegram", "whatsapp"]))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_audit_always_created(self, im_governance, platform):
        """
        Every request (success or failure) must create an audit log entry.
        """
        with patch("core.im_governance_service.asyncio.create_task") as mock_create_task:
            # Call log_to_audit_trail
            await im_governance.log_to_audit_trail(
                platform=platform,
                sender_id="test_user",
                payload={"test": "data"},
                action="webhook_received",
                success=True
            )

            # Invariant: Audit log task must be created
            mock_create_task.assert_called_once()

            # Verify the call includes required fields
            call_args = mock_create_task.call_args
            assert "platform" in str(call_args)
            assert "sender_id" in str(call_args)
            assert "action" in str(call_args)
```

Run property tests:
```bash
cd backend
pytest tests/property_tests/im_governance_invariants.py -v
```
  </action>
  <verify>
```bash
cd backend
pytest tests/property_tests/im_governance_invariants.py -v --tb=short
```
  </verify>
  <done>
Property-based tests created:
- TestRateLimitInvariant with 1 property test
- TestHMACSignatureInvariant with 2 property tests
- TestAuditCompletenessInvariant with 1 property test
- All Hypothesis tests using appropriate strategies
- max_examples tuned (50-100) for IO-bound testing
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. All unit tests in test_im_governance.py pass
2. All property tests in im_governance_invariants.py pass
3. Coverage report shows >80% on IMGovernanceService
4. No test collection errors
5. Tests complete in reasonable time (<2 minutes)
</verification>

<success_criteria>
- pytest tests/test_im_governance.py shows 11 passed
- pytest tests/property_tests/im_governance_invariants.py shows 4 passed
- Coverage: backend/core/im_governance_service.py >80%
- Zero test failures or errors
- Property tests completed with 50-100 examples each
</success_criteria>

<output>
After completion, create `.planning/phases/01-im-adapters/01-im-adapters-03-SUMMARY.md` with:
- Test statistics (pass/fail counts)
- Coverage percentage achieved
- Any bugs found during testing
- Test execution time
</output>
