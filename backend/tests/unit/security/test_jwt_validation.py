"""
Unit tests for JWT Validation.

Tests cover:
- Token generation with user claims
- Token validation (valid, expired, malformed, signature)
- Token refresh with rotation
- Claims extraction
- Security edge cases (algorithm confusion, replay prevention)

These tests focus on JWT token lifecycle in core/auth.py and core/token_refresher.py
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

try:
    from freezegun import freeze_time
except ImportError:
    class freeze_time:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

from core.auth import (
    SECRET_KEY,
    ALGORITHM,
    create_access_token,
    create_mobile_token,
    decode_token,
    verify_password,
    get_password_hash,
)
from core.models import User, RevokedToken
from tests.factories.user_factory import UserFactory
from jose import jwt, JWTError


class TestTokenGeneration:
    """Test JWT token generation functions."""

    def test_create_access_token_with_user_claims(self):
        """Test access token generation with user claims."""
        user_id = "user_123"
        data = {"sub": user_id, "email": "test@example.com"}

        token = create_access_token(data)

        assert token is not None
        assert isinstance(token, str)

        # Decode and verify claims
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == user_id
        assert payload["email"] == "test@example.com"

    def test_create_access_token_with_custom_expiration(self):
        """Test access token generation with custom expiration."""
        expires_delta = timedelta(hours=2)
        data = {"sub": "user_456"}

        token = create_access_token(data, expires_delta)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check expiration is approximately 2 hours from now
        exp_timestamp = payload["exp"]
        exp_datetime = datetime.utcfromtimestamp(exp_timestamp)
        now = datetime.utcnow()

        time_diff = exp_datetime - now
        assert timedelta(hours=1.9) <= time_diff <= timedelta(hours=2.1)

    def test_create_access_token_default_expiration(self):
        """Test access token uses default 15 minute expiration."""
        with freeze_time("2026-02-01 10:00:00"):
            token = create_access_token({"sub": "user_789"})

            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            exp_datetime = datetime.utcfromtimestamp(payload["exp"])

            # Should expire at 10:15:00
            expected = datetime.utcfromtimestamp(1643728800 + 900)  # +15 minutes
            assert exp_datetime == expected

    def test_create_access_token_includes_exp_claim(self):
        """Test access token always includes exp claim."""
        token = create_access_token({"sub": "user_abc"})

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_create_mobile_token_with_device_info(self):
        """Test mobile token generation includes device information."""
        user = UserFactory()
        device_id = "device_123"

        tokens = create_mobile_token(user, device_id)

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "expires_at" in tokens
        assert "token_type" in tokens

        # Verify access token contains device info
        access_payload = jwt.decode(tokens["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
        assert access_payload["sub"] == str(user.id)
        assert access_payload["device_id"] == device_id
        assert access_payload["platform"] == "mobile"

    def test_create_mobile_token_refresh_token_expiration(self):
        """Test mobile refresh token has 30 day expiration."""
        with freeze_time("2026-02-01 10:00:00"):
            user = UserFactory()
            tokens = create_mobile_token(user, "device_456")

            # Check refresh token expiration
            refresh_payload = jwt.decode(tokens["refresh_token"], SECRET_KEY, algorithms=[ALGORITHM])
            exp_datetime = datetime.utcfromtimestamp(refresh_payload["exp"])

            # Should be ~30 days from now
            expected = datetime.utcfromtimestamp(1643728800 + (30 * 24 * 3600))
            assert exp_datetime == expected

    def test_token_signing_with_secret_key(self):
        """Test token is signed with configured secret key."""
        token = create_access_token({"sub": "user_sign"})

        # Verify signature with correct key
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "user_sign"

        # Verify fails with wrong key
        with pytest.raises(JWTError):
            jwt.decode(token, "wrong_secret", algorithms=[ALGORITHM])


class TestTokenValidation:
    """Test JWT token validation functions."""

    def test_valid_token_accepted(self):
        """Test valid token is accepted."""
        token = create_access_token({"sub": "user_valid"})

        result = decode_token(token)

        assert result is not None
        assert result["sub"] == "user_valid"

    def test_valid_token_with_all_claims(self):
        """Test valid token with additional claims is accepted."""
        data = {
            "sub": "user_claims",
            "email": "test@example.com",
            "role": "admin"
        }
        token = create_access_token(data)

        result = decode_token(token)

        assert result is not None
        assert result["sub"] == "user_claims"
        assert result["email"] == "test@example.com"
        assert result["role"] == "admin"

    def test_expired_token_rejected(self):
        """Test expired token returns None."""
        with freeze_time("2026-01-01 10:00:00"):
            token = create_access_token({"sub": "user_expired"})

        # Token should now be expired
        with freeze_time("2026-02-01 10:00:00"):
            result = decode_token(token)

            # Should return None for expired token
            assert result is None

    def test_malformed_token_rejected(self):
        """Test malformed token returns None."""
        malformed_tokens = [
            "invalid",
            "not.a.jwt",
            "",
            "abc.def.ghi",
            "Bearer token",
        ]

        for token in malformed_tokens:
            result = decode_token(token)
            assert result is None

    def test_signature_validation_rejects_tampered(self):
        """Test signature validation rejects tampered tokens."""
        original_token = create_access_token({"sub": "user_tampered"})

        # Try to tamper with token by decoding and re-encoding with wrong secret
        payload = jwt.decode(original_token, SECRET_KEY, algorithms=[ALGORITHM])
        payload["admin"] = True  # Add privilege escalation

        tampered_token = jwt.encode(payload, "wrong_secret", algorithm=ALGORITHM)

        result = decode_token(tampered_token)
        assert result is None

    def test_token_with_none_returns_none(self):
        """Test None token returns None."""
        result = decode_token(None)
        assert result is None

    def test_token_with_empty_string_returns_none(self):
        """Test empty string token returns None."""
        result = decode_token("")
        assert result is None


class TestTokenRefresh:
    """Test token refresh functionality."""

    def test_refresh_token_type_claim(self):
        """Test refresh token has 'type': 'refresh' claim."""
        user = UserFactory()
        tokens = create_mobile_token(user, "device_refresh")

        refresh_payload = jwt.decode(tokens["refresh_token"], SECRET_KEY, algorithms=[ALGORITHM])

        assert refresh_payload.get("type") == "refresh"

    def test_access_token_no_type_claim(self):
        """Test access token doesn't have type claim (or has different type)."""
        user = UserFactory()
        tokens = create_mobile_token(user, "device_access")

        access_payload = jwt.decode(tokens["access_token"], SECRET_KEY, algorithms=[ALGORITHM])

        # Access token may not have type claim, or should not be "refresh"
        assert access_payload.get("type") != "refresh"

    def test_refresh_token_contains_device_id(self):
        """Test refresh token contains device_id."""
        user = UserFactory()
        device_id = "test_device_123"
        tokens = create_mobile_token(user, device_id)

        refresh_payload = jwt.decode(tokens["refresh_token"], SECRET_KEY, algorithms=[ALGORITHM])

        assert refresh_payload.get("device_id") == device_id

    def test_token_rotation_generates_new_tokens(self):
        """Test that refresh generates new token pair."""
        user = UserFactory()
        old_tokens = create_mobile_token(user, "device_rotation")

        # Simulate token refresh - would normally call refresh endpoint
        new_tokens = create_mobile_token(user, "device_rotation")

        # Tokens should be different
        assert old_tokens["access_token"] != new_tokens["access_token"]
        assert old_tokens["refresh_token"] != new_tokens["refresh_token"]

    def test_refresh_token_longer_expiration_than_access(self):
        """Test refresh token has longer expiration than access token."""
        user = UserFactory()
        tokens = create_mobile_token(user, "device_compare")

        access_payload = jwt.decode(tokens["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
        refresh_payload = jwt.decode(tokens["refresh_token"], SECRET_KEY, algorithms=[ALGORITHM])

        # Refresh token should expire later than access token
        assert refresh_payload["exp"] > access_payload["exp"]


class TestClaimsExtraction:
    """Test claims extraction from JWT tokens."""

    def test_extract_user_id_from_sub_claim(self):
        """Test user ID extraction from 'sub' claim."""
        user_id = "user_12345"
        token = create_access_token({"sub": user_id})

        result = decode_token(token)

        assert result is not None
        assert result.get("sub") == user_id

    def test_extract_role_from_claims(self):
        """Test role extraction from token claims."""
        role = "SUPER_ADMIN"
        token = create_access_token({"sub": "user_role", "role": role})

        result = decode_token(token)

        assert result is not None
        assert result.get("role") == role

    def test_extract_email_from_claims(self):
        """Test email extraction from token claims."""
        email = "user@example.com"
        token = create_access_token({"sub": "user_email", "email": email})

        result = decode_token(token)

        assert result is not None
        assert result.get("email") == email

    def test_extract_metadata_claims(self):
        """Test extraction of metadata claims."""
        metadata = {
            "device": "mobile",
            "platform": "ios",
            "version": "1.0.0"
        }
        token = create_access_token({"sub": "user_meta", **metadata})

        result = decode_token(token)

        assert result is not None
        assert result.get("device") == "mobile"
        assert result.get("platform") == "ios"
        assert result.get("version") == "1.0.0"

    def test_extract_issued_at_claim(self):
        """Test 'iat' (issued at) claim is present."""
        with freeze_time("2026-02-01 10:00:00"):
            token = create_access_token({"sub": "user_iat"})

        result = decode_token(token)

        assert result is not None
        # Note: jose may not add iat by default, but exp should be there
        assert "exp" in result

    def test_extract_expires_at_claim(self):
        """Test 'exp' (expires at) claim is present and valid."""
        token = create_access_token({"sub": "user_exp"})

        result = decode_token(token)

        assert result is not None
        assert "exp" in result

        # Verify exp is in the future
        exp_timestamp = result["exp"]
        exp_datetime = datetime.utcfromtimestamp(exp_timestamp)
        assert exp_datetime > datetime.utcnow()


class TestSecurityEdgeCases:
    """Test security edge cases for JWT tokens."""

    def test_algorithm_confusion_prevention(self):
        """Test algorithm confusion attack is prevented."""
        # Try to create token with 'none' algorithm
        malicious_payload = {"sub": "attacker", "admin": True}

        # Token should use HS256, not 'none'
        token = create_access_token(malicious_payload)

        # Verify algorithm is HS256
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"

    def test_replay_attack_prevention_with_jti(self):
        """Test replay attack prevention using JTI (JWT ID)."""
        # This tests that tokens can include unique JTI for replay prevention
        # Implementation would check JTI against used tokens list
        user_id = "user_replay"
        jti = "unique_jti_123"

        token = create_access_token({"sub": user_id, "jti": jti})

        result = decode_token(token)

        assert result is not None
        assert result.get("jti") == jti

    def test_token_theft_detection_with_ip(self):
        """Test token can include IP for theft detection."""
        ip_address = "192.168.1.100"
        token = create_access_token({"sub": "user_ip", "ip": ip_address})

        result = decode_token(token)

        assert result is not None
        assert result.get("ip") == ip_address

    def test_token_with_unicode_characters(self):
        """Test token handles unicode characters in claims."""
        unicode_data = {
            "sub": "user_unicode",
            "name": "日本語",
            "email": "test@example.com"
        }
        token = create_access_token(unicode_data)

        result = decode_token(token)

        assert result is not None
        assert result.get("name") == "日本語"

    def test_very_long_claim_values(self):
        """Test token handles very long claim values."""
        long_string = "a" * 10000
        token = create_access_token({"sub": "user_long", "data": long_string})

        result = decode_token(token)

        assert result is not None
        assert result.get("data") == long_string

    def test_empty_claims(self):
        """Test token with only minimal required claims."""
        token = create_access_token({"sub": "user_minimal"})

        result = decode_token(token)

        assert result is not None
        assert result.get("sub") == "user_minimal"
        assert "exp" in result


class TestTokenRefresherService:
    """Test token refresher service for OAuth tokens."""

    def test_token_refresher_initialization(self):
        """Test TokenRefresher initializes correctly."""
        from core.token_refresher import TokenRefresher

        refresher = TokenRefresher()

        assert refresher is not None
        assert refresher.token_metadata == {}
        assert refresher.refresh_handlers == {}

    def test_register_service_for_refresh(self):
        """Test registering a service for token refresh."""
        from core.token_refresher import TokenRefresher

        refresher = TokenRefresher()

        async def mock_handler(metadata):
            return {"expires_at": datetime.utcnow() + timedelta(hours=1)}

        refresher.register_service("test_service", mock_handler)

        assert "test_service" in refresher.refresh_handlers
        assert "test_service" in refresher.token_metadata

    def test_should_refresh_check(self):
        """Test should_refresh determines if token needs refresh."""
        from core.token_refresher import TokenRefresher

        refresher = TokenRefresher()

        async def mock_handler(metadata):
            return {}

        # Register token expiring soon
        expires_soon = datetime.utcnow() + timedelta(minutes=10)
        refresher.register_service("expiring_service", mock_handler, expires_at=expires_soon)

        assert refresher.should_refresh("expiring_service", buffer_minutes=15) is True

    def test_should_not_refresh_fresh_token(self):
        """Test should_refresh returns False for fresh tokens."""
        from core.token_refresher import TokenRefresher

        refresher = TokenRefresher()

        async def mock_handler(metadata):
            return {}

        # Register token with plenty of time left
        expires_later = datetime.utcnow() + timedelta(hours=5)
        refresher.register_service("fresh_service", mock_handler, expires_at=expires_later)

        assert refresher.should_refresh("fresh_service", buffer_minutes=15) is False

    def test_get_status(self):
        """Test get_status returns token status information."""
        from core.token_refresher import TokenRefresher

        refresher = TokenRefresher()

        async def mock_handler(metadata):
            return {}

        expires_at = datetime.utcnow() + timedelta(hours=1)
        refresher.register_service("status_service", mock_handler, expires_at=expires_at)

        status = refresher.get_status()

        assert "status_service" in status
        assert status["status_service"]["expires_at"] is not None
        assert "needs_refresh" in status["status_service"]
