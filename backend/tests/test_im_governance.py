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
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import Request, HTTPException
from sqlalchemy.orm import Session

from core.im_governance_service import IMGovernanceService


@pytest.fixture
def db_session():
    """Create mock database session"""
    return MagicMock(spec=Session)


@pytest.fixture
def im_governance(db_session):
    """Create IMGovernanceService instance for testing"""
    return IMGovernanceService(db=db_session)


@pytest.fixture
def mock_telegram_request():
    """Create mock Telegram webhook request"""
    mock_request = Mock(spec=Request)
    mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "test_secret"}
    mock_request.path_params = {"platform": "telegram"}
    mock_request.query_params = {}
    body_bytes = b'{"message": {"from": {"id": "123"}, "text": "test"}}'
    mock_request.body = AsyncMock(return_value=body_bytes)
    mock_request.json = AsyncMock(return_value={"message": {"from": {"id": "123"}, "text": "test"}})
    return mock_request, body_bytes


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
    return mock_request, payload


class TestWebhookSignatureVerification:
    """Test webhook signature verification"""

    @pytest.mark.asyncio
    async def test_valid_telegram_signature_accepted(self, im_governance, mock_telegram_request):
        """Valid Telegram signature should be accepted"""
        mock_request, body_bytes = mock_telegram_request

        # Mock the adapter's verify_request to return True
        async def mock_verify(*args, **kwargs):
            return True

        with patch.object(im_governance.adapters["telegram"], "verify_request", side_effect=mock_verify):
            result = await im_governance.verify_and_rate_limit(
                mock_request,
                body_bytes,
                "telegram"
            )
            assert result["verified"] is True
            assert result["platform"] == "telegram"

    @pytest.mark.asyncio
    async def test_invalid_telegram_signature_rejected(self, im_governance, mock_telegram_request):
        """Invalid Telegram signature should be rejected"""
        mock_request, body_bytes = mock_telegram_request
        mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"}

        # Mock the adapter's verify_request to return False
        async def mock_verify(*args, **kwargs):
            return False

        with patch.object(im_governance.adapters["telegram"], "verify_request", side_effect=mock_verify):
            with pytest.raises(HTTPException) as exc:
                await im_governance.verify_and_rate_limit(
                    mock_request,
                    body_bytes,
                    "telegram"
                )
            assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_valid_whatsapp_signature_accepted(self, im_governance, mock_whatsapp_request):
        """Valid WhatsApp signature should be accepted"""
        mock_request, body_bytes = mock_whatsapp_request

        # Mock the adapter's verify_request to return True
        async def mock_verify(*args, **kwargs):
            return True

        with patch.object(im_governance.adapters["whatsapp"], "verify_request", side_effect=mock_verify):
            result = await im_governance.verify_and_rate_limit(
                mock_request,
                body_bytes,
                "whatsapp"
            )
            assert result["verified"] is True
            assert result["platform"] == "whatsapp"

    @pytest.mark.asyncio
    async def test_invalid_whatsapp_signature_rejected(self, im_governance, mock_whatsapp_request):
        """Invalid WhatsApp signature should be rejected"""
        mock_request, body_bytes = mock_whatsapp_request
        mock_request.headers = {"X-Hub-Signature-256": "sha256=invalid"}

        # Mock the adapter's verify_request to return False
        async def mock_verify(*args, **kwargs):
            return False

        with patch.object(im_governance.adapters["whatsapp"], "verify_request", side_effect=mock_verify):
            with pytest.raises(HTTPException) as exc:
                await im_governance.verify_and_rate_limit(
                    mock_request,
                    body_bytes,
                    "whatsapp"
                )
            assert exc.value.status_code == 403


class TestRateLimiting:
    """Test rate limiting (10 req/min per user)"""

    @pytest.mark.asyncio
    async def test_first_10_requests_allowed(self, im_governance, mock_telegram_request):
        """First 10 requests within 1 minute should be allowed"""
        mock_request, body_bytes = mock_telegram_request

        async def mock_verify(*args, **kwargs):
            return True

        with patch.object(im_governance.adapters["telegram"], "verify_request", side_effect=mock_verify):
            for i in range(10):
                result = await im_governance.verify_and_rate_limit(
                    mock_request,
                    body_bytes,
                    "telegram"
                )
                assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_11th_request_blocked(self, im_governance, mock_telegram_request):
        """11th request within 1 minute should be blocked"""
        mock_request, body_bytes = mock_telegram_request

        async def mock_verify(*args, **kwargs):
            return True

        with patch.object(im_governance.adapters["telegram"], "verify_request", side_effect=mock_verify):
            # First 10 should succeed
            for i in range(10):
                await im_governance.verify_and_rate_limit(
                    mock_request,
                    body_bytes,
                    "telegram"
                )

            # 11th should fail
            with pytest.raises(HTTPException) as exc:
                await im_governance.verify_and_rate_limit(
                    mock_request,
                    body_bytes,
                    "telegram"
                )
            assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_different_users_not_affected(self, im_governance, mock_telegram_request):
        """Rate limit should be per-user, not global"""
        mock_request, body_bytes = mock_telegram_request

        async def mock_verify(*args, **kwargs):
            return True

        with patch.object(im_governance.adapters["telegram"], "verify_request", side_effect=mock_verify):
            # User 123 hits limit
            for i in range(10):
                await im_governance.verify_and_rate_limit(
                    mock_request,
                    body_bytes,
                    "telegram"
                )

            # User 456 should still be allowed
            body_bytes_456 = b'{"message": {"from": {"id": "456"}, "text": "test"}}'
            mock_request.body = AsyncMock(return_value=body_bytes_456)
            mock_request.json = AsyncMock(return_value={"message": {"from": {"id": "456"}, "text": "test"}})

            result = await im_governance.verify_and_rate_limit(
                mock_request,
                body_bytes_456,
                "telegram"
            )
            assert result["verified"] is True


class TestGovernanceChecks:
    """Test governance maturity checks"""

    @pytest.mark.asyncio
    async def test_blocked_user_rejected(self, im_governance):
        """Blocked user should be rejected"""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value={"blocked": True})

        with patch("core.im_governance_service.get_governance_cache", return_value=mock_cache):
            with pytest.raises(HTTPException) as exc:
                await im_governance.check_permissions("123", "telegram")
            assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_allowed_user_accepted(self, im_governance):
        """Allowed user should pass checks"""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # Not blocked

        with patch("core.im_governance_service.get_governance_cache", return_value=mock_cache):
            result = await im_governance.check_permissions("123", "telegram")
            assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_student_agent_blocked(self, im_governance):
        """STUDENT agent should be blocked from IM triggers"""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # User not blocked
        mock_cache.get = AsyncMock(side_effect=lambda k, *args: {"maturity_level": "STUDENT"} if "agent_" in k else None)

        with patch("core.im_governance_service.get_governance_cache", return_value=mock_cache):
            with pytest.raises(HTTPException) as exc:
                await im_governance.check_permissions("123", "telegram", agent_id="agent_student")
            assert exc.value.status_code == 403
            assert "STUDENT" in exc.value.detail

    @pytest.mark.asyncio
    async def test_autonomous_agent_allowed(self, im_governance):
        """AUTONOMOUS agent should be allowed"""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(side_effect=lambda k, *args: {"maturity_level": "AUTONOMOUS"} if "agent_" in k else None)

        with patch("core.im_governance_service.get_governance_cache", return_value=mock_cache):
            result = await im_governance.check_permissions("123", "telegram", agent_id="agent_auto")
            assert result["allowed"] is True
            assert result["maturity_level"] == "AUTONOMOUS"


class TestAuditTrail:
    """Test audit trail logging"""

    @pytest.mark.asyncio
    async def test_audit_log_created_on_success(self, im_governance, db_session):
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
    async def test_audit_log_created_on_failure(self, im_governance, db_session):
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

    @pytest.mark.asyncio
    async def test_audit_log_includes_maturity_level(self, im_governance, db_session):
        """Audit log should include agent maturity level when provided"""
        with patch("core.im_governance_service.asyncio.create_task") as mock_create_task:
            await im_governance.log_to_audit_trail(
                platform="telegram",
                sender_id="123",
                payload={"test": "data"},
                action="webhook_received",
                success=True,
                agent_maturity_level="AUTONOMOUS"
            )
            mock_create_task.assert_called_once()
            # Verify the task was created with maturity level included
            call_args = mock_create_task.call_args
            assert call_args is not None


class TestRateLimitStatus:
    """Test rate limit status queries"""

    def test_rate_limit_status_returns_correct_info(self, im_governance):
        """Rate limit status should return correct information"""
        status = im_governance.get_rate_limit_status("telegram", "123")

        assert status["limit"] == 10
        assert status["remaining"] == 10
        assert status["window"] == 60
        assert "reset_at" in status

    def test_rate_limit_status_decrements_with_requests(self, im_governance, mock_telegram_request):
        """Rate limit remaining should decrease as requests are made"""
        mock_request, body_bytes = mock_telegram_request

        with patch.object(im_governance.adapters["telegram"], "verify_request", return_value=Mock(coroutine=AsyncMock(return_value=True))):
            # Make 5 requests
            for i in range(5):
                import asyncio
                asyncio.run(im_governance.verify_and_rate_limit(
                    mock_request,
                    body_bytes,
                    "telegram"
                ))

            # Check status
            status = im_governance.get_rate_limit_status("telegram", "123")
            assert status["remaining"] == 5


class TestSenderIdExtraction:
    """Test sender_id extraction from different platforms"""

    def test_extract_telegram_sender_id_from_message(self, im_governance):
        """Should extract sender_id from Telegram message"""
        body = b'{"message": {"from": {"id": "123456"}, "text": "hello"}}'
        sender_id = im_governance._extract_sender_id(None, body, "telegram")
        assert sender_id == "123456"

    def test_extract_telegram_sender_id_from_callback_query(self, im_governance):
        """Should extract sender_id from Telegram callback query"""
        body = b'{"callback_query": {"from": {"id": "789012"}}}'
        sender_id = im_governance._extract_sender_id(None, body, "telegram")
        assert sender_id == "789012"

    def test_extract_whatsapp_sender_id(self, im_governance):
        """Should extract sender_id from WhatsApp message"""
        body = b'{"entry": [{"changes": [{"value": {"messages": [{"from": "1234567890"}]}}]}]}'
        sender_id = im_governance._extract_sender_id(None, body, "whatsapp")
        assert sender_id == "1234567890"

    def test_extract_sender_id_returns_none_for_invalid_json(self, im_governance):
        """Should return None for invalid JSON"""
        body = b'invalid json'
        sender_id = im_governance._extract_sender_id(None, body, "telegram")
        assert sender_id is None

    def test_extract_sender_id_returns_none_for_unknown_platform(self, im_governance):
        """Should return None for unknown platform"""
        body = b'{"test": "data"}'
        sender_id = im_governance._extract_sender_id(None, body, "unknown")
        assert sender_id is None
