"""
Comprehensive JWT Security Tests

Tests for centralized JWT verification including:
- Expired token rejection
- Invalid signature rejection
- Audience mismatch rejection
- Issuer mismatch rejection
- Missing claims rejection
- DEBUG mode with IP whitelist
- Default secret rejection in production
- Token revocation (future implementation
"""

import os
from datetime import datetime, timedelta
import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from core.jwt_verifier import JWTVerificationError, JWTVerifier, verify_token, verify_token_string


class TestJWTVerifierBasics:
    """Test basic JWT verifier functionality"""

    def test_init_with_default_secret_in_production(self):
        """Should reject default secret key in production"""
        with pytest.raises(ValueError, match="default secret key"):
            JWTVerifier(
                secret_key="your-secret-key-here-change-in-production",
                debug_mode=False,
            )

    def test_init_with_custom_secret_in_production(self):
        """Should accept custom secret key in production"""
        verifier = JWTVerifier(
            secret_key="custom-production-secret-key",
            debug_mode=False,
        )
        assert verifier.secret_key == "custom-production-secret-key"

    def test_init_with_default_secret_in_debug(self):
        """Should accept default secret in debug mode"""
        verifier = JWTVerifier(
            secret_key="your-secret-key-here-change-in-production",
            debug_mode=True,
        )
        assert verifier.secret_key == "your-secret-key-here-change-in-production"


class TestTokenCreation:
    """Test token creation functionality"""

    def test_create_basic_token(self):
        """Create basic token with subject"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)
        token = verifier.create_token(subject="user123")

        assert isinstance(token, str)
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert payload["sub"] == "user123"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_token_with_expiration(self):
        """Create token with custom expiration"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)
        token = verifier.create_token(
            subject="user123", expires_delta=timedelta(hours=1)
        )

        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
        exp = datetime.fromtimestamp(payload["exp"])
        iat = datetime.fromtimestamp(payload["iat"])
        assert (exp - iat) == timedelta(hours=1)

    def test_create_token_with_audience(self):
        """Create token with audience claim"""
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, audience="atom-app"
        )
        token = verifier.create_token(subject="user123")

        # Decode with audience verification disabled for creation test
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"], options={"verify_aud": False})
        assert payload["aud"] == "atom-app"

    def test_create_token_with_issuer(self):
        """Create token with issuer claim"""
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, issuer="atom-auth"
        )
        token = verifier.create_token(subject="user123")

        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert payload["iss"] == "atom-auth"

    def test_create_token_with_additional_claims(self):
        """Create token with additional claims"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)
        token = verifier.create_token(
            subject="user123",
            additional_claims={"role": "admin", "permissions": ["read", "write"]},
        )

        payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
        assert payload["role"] == "admin"
        assert payload["permissions"] == ["read", "write"]


class TestTokenVerification:
    """Test token verification functionality"""

    def test_verify_valid_token(self):
        """Verify a valid token"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)
        token = verifier.create_token(subject="user123")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )
        payload = verifier.verify_token(credentials)

        assert payload["sub"] == "user123"
        assert "exp" in payload

    def test_verify_expired_token(self):
        """Should reject expired token"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)

        # Create expired token
        payload = {
            "sub": "user123",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token(credentials)
        assert exc_info.value.status_code == 401
        assert "expired" in str(exc_info.value.detail).lower()

    def test_verify_invalid_signature(self):
        """Should reject token with invalid signature"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)

        # Create token with different secret
        token = jwt.encode(
            {"sub": "user123", "exp": datetime.utcnow() + timedelta(hours=1)},
            "wrong-secret",
            algorithm="HS256",
        )

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token(credentials)
        assert exc_info.value.status_code == 401
        assert "invalid" in str(exc_info.value.detail).lower()

    def test_verify_missing_expiration(self):
        """Should reject token without expiration claim"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)

        # Create token without exp claim
        token = jwt.encode({"sub": "user123"}, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token(credentials)
        assert exc_info.value.status_code == 401

    def test_verify_missing_subject(self):
        """Should reject token without subject claim"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)

        # Create token without sub claim - decode manually since verify checks for it
        token = jwt.encode(
            {"exp": datetime.utcnow() + timedelta(hours=1)},
            "test-secret",
            algorithm="HS256",
        )

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token(credentials)
        assert exc_info.value.status_code == 401
        # Any error message is fine - the important part is it rejects the token


class TestAudienceValidation:
    """Test audience claim validation"""

    def test_verify_valid_audience(self):
        """Accept token with correct audience"""
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, audience="atom-app"
        )
        token = verifier.create_token(subject="user123")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )
        payload = verifier.verify_token(credentials)
        assert payload["aud"] == "atom-app"

    def test_verify_invalid_audience(self):
        """Reject token with wrong audience"""
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, audience="atom-app"
        )

        # Create token with different audience
        payload = {
            "sub": "user123",
            "aud": "wrong-app",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token(credentials)
        assert exc_info.value.status_code == 401
        assert "audience" in str(exc_info.value.detail).lower()

    def test_verify_without_audience_configured(self):
        """Accept token without audience when not configured"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)

        payload = {
            "sub": "user123",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )
        payload = verifier.verify_token(credentials)
        assert payload["sub"] == "user123"


class TestIssuerValidation:
    """Test issuer claim validation"""

    def test_verify_valid_issuer(self):
        """Accept token with correct issuer"""
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, issuer="atom-auth"
        )
        token = verifier.create_token(subject="user123")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )
        payload = verifier.verify_token(credentials)
        assert payload["iss"] == "atom-auth"

    def test_verify_invalid_issuer(self):
        """Reject token with wrong issuer"""
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, issuer="atom-auth"
        )

        # Create token with different issuer
        payload = {
            "sub": "user123",
            "iss": "wrong-auth",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token(credentials)
        assert exc_info.value.status_code == 401
        assert "issuer" in str(exc_info.value.detail).lower()


class TestDebugMode:
    """Test DEBUG mode functionality"""

    def test_debug_mode_without_whitelist(self):
        """In DEBUG mode without whitelist, should require valid token"""
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, debug_ip_whitelist=[]
        )

        # Invalid token
        token = "invalid-token-string"
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException):
            verifier.verify_token(credentials)

    def test_debug_mode_with_whitelisted_ip(self):
        """In DEBUG mode with whitelisted IP, should accept any token"""
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, debug_ip_whitelist=["127.0.0.1"]
        )

        # Create a valid JWT (even with wrong secret it should work in debug mode)
        token = jwt.encode(
            {"sub": "user123", "exp": datetime.utcnow() + timedelta(hours=1)},
            "any-secret",
            algorithm="HS256",
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # Should decode without validation in debug mode with whitelisted IP
        payload = verifier.verify_token(credentials, client_ip="127.0.0.1")
        assert payload is not None
        assert payload["sub"] == "user123"

    def test_debug_mode_with_non_whitelisted_ip(self):
        """In DEBUG mode with non-whitelisted IP, should require valid token"""
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, debug_ip_whitelist=["127.0.0.1"]
        )

        # Invalid token from non-whitelisted IP
        token = jwt.encode(
            {"sub": "user123", "exp": datetime.utcnow() + timedelta(hours=1)},
            "wrong-secret",
            algorithm="HS256",
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with pytest.raises(HTTPException):
            verifier.verify_token(credentials, client_ip="192.168.1.1")

    def test_debug_mode_cidr_whitelist(self):
        """In DEBUG mode, CIDR ranges should work"""
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, debug_ip_whitelist=["10.0.0.0/8"]
        )

        token = jwt.encode(
            {"sub": "user123", "exp": datetime.utcnow() + timedelta(hours=1)},
            "test-secret",
            algorithm="HS256",
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        # IP in range
        payload = verifier.verify_token(credentials, client_ip="10.0.0.5")
        assert payload["sub"] == "user123"


class TestIPWhitelistParsing:
    """Test IP whitelist parsing from environment"""

    def test_parse_empty_whitelist(self):
        """Empty whitelist should result in empty list"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)
        assert verifier.debug_ip_whitelist == []

    def test_parse_single_ip_whitelist(self):
        """Parse single IP from environment"""
        os.environ["DEBUG_IP_WHITELIST"] = "127.0.0.1"
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, debug_ip_whitelist=None
        )
        assert verifier.debug_ip_whitelist == ["127.0.0.1"]
        del os.environ["DEBUG_IP_WHITELIST"]

    def test_parse_multiple_ip_whitelist(self):
        """Parse multiple IPs from environment"""
        os.environ["DEBUG_IP_WHITELIST"] = "127.0.0.1,10.0.0.1,192.168.1.1"
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, debug_ip_whitelist=None
        )
        assert verifier.debug_ip_whitelist == ["127.0.0.1", "10.0.0.1", "192.168.1.1"]
        del os.environ["DEBUG_IP_WHITELIST"]

    def test_parse_cidr_whitelist(self):
        """Parse CIDR ranges from environment"""
        os.environ["DEBUG_IP_WHITELIST"] = "10.0.0.0/8,192.168.0.0/16"
        verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True, debug_ip_whitelist=None
        )
        assert verifier.debug_ip_whitelist == ["10.0.0.0/8", "192.168.0.0/16"]
        del os.environ["DEBUG_IP_WHITELIST"]


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_verify_token_string(self):
        """Verify token using string convenience function"""
        from core import jwt_verifier

        # Set global verifier
        jwt_verifier._jwt_verifier = JWTVerifier(
            secret_key="test-secret", debug_mode=True
        )

        token = jwt_verifier._jwt_verifier.create_token(subject="user123")
        payload = verify_token_string(token)
        assert payload["sub"] == "user123"

    def test_no_credentials(self):
        """Should raise exception when no credentials provided"""
        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)

        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token(None)
        assert exc_info.value.status_code == 401


class TestTokenAgeWarning:
    """Test token age warnings"""

    def test_old_token_warning(self, caplog):
        """Should warn about very old tokens"""
        import logging

        verifier = JWTVerifier(secret_key="test-secret", debug_mode=True)

        # Create token that's 35 days old
        iat = datetime.utcnow() - timedelta(days=35)
        payload = {
            "sub": "user123",
            "iat": iat,
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token
        )

        with caplog.at_level(logging.WARNING):
            verifier.verify_token(credentials)

        assert "very old" in caplog.text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
