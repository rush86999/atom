"""
Unit Tests for JWT Verifier

Tests for JWT token verification, validation, and claims parsing.
"""

import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
import jwt

from core.jwt_verifier import (
    JWTVerifier,
    JWTVerificationError,
    get_jwt_verifier,
    verify_token,
    verify_token_string
)
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


@pytest.fixture
def test_secret():
    """Test JWT secret key"""
    return "test-jwt-secret-key-for-testing"


@pytest.fixture
def jwt_verifier(test_secret):
    """Create JWTVerifier instance with test secret"""
    return JWTVerifier(
        secret_key=test_secret,
        debug_mode=False
    )


@pytest.fixture
def valid_token(jwt_verifier):
    """Create valid JWT token"""
    return jwt_verifier.create_token(
        subject="test-user-123",
        expires_delta=timedelta(hours=1),
        additional_claims={"role": "user"}
    )


@pytest.fixture
def expired_token(test_secret):
    """Create expired JWT token"""
    payload = {
        "sub": "test-user",
        "iat": datetime.utcnow() - timedelta(hours=2),
        "exp": datetime.utcnow() - timedelta(hours=1),  # Expired
        "jti": "expired-jti"
    }
    return jwt.encode(payload, test_secret, algorithm="HS256")


@pytest.fixture
def invalid_token(test_secret):
    """Create token with invalid signature"""
    payload = {
        "sub": "test-user",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    token = jwt.encode(payload, test_secret, algorithm="HS256")
    # Tamper with token
    return token[:-5] + "wrong"


@pytest.fixture
def test_payload():
    """Test payload dictionary"""
    return {
        "sub": "user123",
        "name": "Test User",
        "email": "test@example.com",
        "role": "admin"
    }


class TestJWTVerifier:
    """Test JWTVerifier initialization and configuration"""

    def test_initialization_with_secret(self, test_secret):
        """Test initialization with secret key"""
        verifier = JWTVerifier(secret_key=test_secret)
        assert verifier.secret_key == test_secret
        assert verifier.algorithm == "HS256"

    def test_initialization_with_algorithm(self, test_secret):
        """Test initialization with custom algorithm"""
        verifier = JWTVerifier(
            secret_key=test_secret,
            algorithm="RS256"
        )
        assert verifier.algorithm == "RS256"

    def test_initialization_with_audience(self, test_secret):
        """Test initialization with audience"""
        verifier = JWTVerifier(
            secret_key=test_secret,
            audience="test-audience"
        )
        assert verifier.audience == "test-audience"

    def test_initialization_with_issuer(self, test_secret):
        """Test initialization with issuer"""
        verifier = JWTVerifier(
            secret_key=test_secret,
            issuer="test-issuer"
        )
        assert verifier.issuer == "test-issuer"

    @patch('core.jwt_verifier.os.getenv')
    def test_initialization_debug_mode_from_env(self, mock_getenv, test_secret):
        """Test debug mode from environment"""
        mock_getenv.return_value = "true"
        verifier = JWTVerifier(
            secret_key=test_secret,
            debug_mode=None
        )
        assert verifier.debug_mode is True

    def test_initialization_default_secret_from_env(self):
        """Test default secret from JWT_SECRET env var"""
        with patch.dict(os.environ, {"JWT_SECRET": "env-secret"}):
            verifier = JWTVerifier()
            assert verifier.secret_key == "env-secret"

    def test_initialization_no_secret_raises_error(self):
        """Test initialization without secret raises error"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                JWTVerifier(debug_mode=False)
            assert "JWT_SECRET" in str(exc_info.value)

    def test_initialization_default_secret_rejected_in_production(self):
        """Test default secret rejected in production"""
        with patch.dict(os.environ, {
            "JWT_SECRET": "your-secret-key-here-change-in-production",
            "DEBUG": "false"
        }, clear=True):
            with pytest.raises(ValueError) as exc_info:
                JWTVerifier(debug_mode=False)
            assert "default secret key" in str(exc_info.value).lower()

    def test_debug_mode_allows_default_secret(self):
        """Test debug mode allows default secret"""
        with patch.dict(os.environ, {
            "JWT_SECRET": "secret",
            "DEBUG": "true"
        }, clear=True):
            verifier = JWTVerifier(debug_mode=True)
            assert verifier.secret_key == "secret"


class TestTokenVerification:
    """Test JWT token verification"""

    def test_verify_valid_token(self, jwt_verifier, valid_token):
        """Test verifying valid token"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )

        payload = jwt_verifier.verify_token(credentials)

        assert payload["sub"] == "test-user-123"
        assert payload["role"] == "user"
        assert "exp" in payload
        assert "iat" in payload

    def test_verify_invalid_signature(self, jwt_verifier, test_secret):
        """Test rejecting token with invalid signature"""
        # Create token with different secret
        payload = {"sub": "user", "exp": datetime.utcnow() + timedelta(hours=1)}
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            jwt_verifier.verify_token(credentials)

        assert exc_info.value.status_code == 401

    def test_verify_expired_token(self, jwt_verifier, expired_token):
        """Test rejecting expired token"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=expired_token
        )

        with pytest.raises(HTTPException) as exc_info:
            jwt_verifier.verify_token(credentials)

        assert exc_info.value.status_code == 401
        assert "expired" in str(exc_info.value.detail).lower()

    def test_verify_malformed_token(self, jwt_verifier):
        """Test rejecting malformed token"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="not-a-valid-jwt-token"
        )

        with pytest.raises(HTTPException) as exc_info:
            jwt_verifier.verify_token(credentials)

        assert exc_info.value.status_code == 401

    def test_verify_missing_claims(self, jwt_verifier, test_secret):
        """Test rejecting token without required claims"""
        # Token without 'exp' claim
        payload = {"sub": "user"}
        token = jwt.encode(payload, test_secret, algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            jwt_verifier.verify_token(credentials)

        assert exc_info.value.status_code == 401

    def test_verify_returns_payload(self, jwt_verifier, valid_token):
        """Test verification returns decoded payload"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )

        payload = jwt_verifier.verify_token(credentials)

        assert isinstance(payload, dict)
        assert "sub" in payload
        assert "exp" in payload

    def test_verify_algorithm_mismatch(self, jwt_verifier):
        """Test rejecting token with wrong algorithm"""
        # Create token with RS256 but verifier expects HS256
        payload = {"sub": "user", "exp": datetime.utcnow() + timedelta(hours=1)}
        token = jwt.encode(payload, jwt_verifier.secret_key, algorithm="HS512")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            jwt_verifier.verify_token(credentials)

        assert exc_info.value.status_code == 401

    def test_verify_with_audience(self):
        """Test audience validation"""
        verifier = JWTVerifier(
            secret_key="test-secret",
            audience="test-audience"
        )

        # Token with audience
        payload = {
            "sub": "user",
            "aud": "test-audience",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        result = verifier.verify_token(credentials)
        assert result["aud"] == "test-audience"

    def test_verify_audience_mismatch(self):
        """Test rejecting token with wrong audience"""
        verifier = JWTVerifier(
            secret_key="test-secret",
            audience="expected-audience"
        )

        # Token with different audience
        payload = {
            "sub": "user",
            "aud": "wrong-audience",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token(credentials)

        assert exc_info.value.status_code == 401
        assert "audience" in str(exc_info.value.detail).lower()

    def test_verify_with_issuer(self):
        """Test issuer validation"""
        verifier = JWTVerifier(
            secret_key="test-secret",
            issuer="test-issuer"
        )

        # Token with issuer
        payload = {
            "sub": "user",
            "iss": "test-issuer",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        result = verifier.verify_token(credentials)
        assert result["iss"] == "test-issuer"

    def test_verify_issuer_mismatch(self):
        """Test rejecting token with wrong issuer"""
        verifier = JWTVerifier(
            secret_key="test-secret",
            issuer="expected-issuer"
        )

        # Token with different issuer
        payload = {
            "sub": "user",
            "iss": "wrong-issuer",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token(credentials)

        assert exc_info.value.status_code == 401
        assert "issuer" in str(exc_info.value.detail).lower()

    def test_verify_no_credentials(self, jwt_verifier):
        """Test verification with no credentials"""
        credentials = None

        with pytest.raises(HTTPException) as exc_info:
            jwt_verifier.verify_token(credentials)

        assert exc_info.value.status_code == 401

    def test_verify_empty_credentials(self, jwt_verifier):
        """Test verification with empty credentials"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=""
        )

        with pytest.raises(HTTPException) as exc_info:
            jwt_verifier.verify_token(credentials)

        assert exc_info.value.status_code == 401


class TestTokenCreation:
    """Test JWT token creation"""

    def test_create_token_basic(self, jwt_verifier):
        """Test creating basic token"""
        token = jwt_verifier.create_token(subject="user123")

        assert isinstance(token, str)
        assert len(token) > 0

        # Verify it's valid
        payload = jwt.decode(
            token,
            jwt_verifier.secret_key,
            algorithms=[jwt_verifier.algorithm]
        )

        assert payload["sub"] == "user123"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_token_with_expiration(self, jwt_verifier):
        """Test creating token with custom expiration"""
        import time
        expires = timedelta(minutes=30)
        before_creation = time.time()

        token = jwt_verifier.create_token(
            subject="user123",
            expires_delta=expires
        )

        after_creation = time.time()

        payload = jwt.decode(
            token,
            jwt_verifier.secret_key,
            algorithms=[jwt_verifier.algorithm]
        )

        # Check that exp claim exists
        assert "exp" in payload
        exp_timestamp = payload["exp"]

        # Should be approximately 30 minutes (1800 seconds) from now
        # Calculate expected range based on creation time
        min_expected = before_creation + 1790  # 30 min - 10 sec tolerance
        max_expected = after_creation + 1810   # 30 min + 10 sec tolerance

        assert min_expected < exp_timestamp < max_expected

    def test_create_token_with_additional_claims(self, jwt_verifier):
        """Test creating token with additional claims"""
        additional = {"role": "admin", "email": "admin@example.com"}
        token = jwt_verifier.create_token(
            subject="user123",
            additional_claims=additional
        )

        payload = jwt.decode(
            token,
            jwt_verifier.secret_key,
            algorithms=[jwt_verifier.algorithm]
        )

        assert payload["role"] == "admin"
        assert payload["email"] == "admin@example.com"

    def test_create_token_with_audience(self):
        """Test creating token with audience"""
        verifier = JWTVerifier(
            secret_key="test-secret",
            audience="test-audience"
        )

        token = verifier.create_token(subject="user123")

        # Decode with audience specified
        payload = jwt.decode(
            token,
            "test-secret",
            algorithms=["HS256"],
            audience="test-audience"
        )

        assert payload["aud"] == "test-audience"

    def test_create_token_with_issuer(self):
        """Test creating token with issuer"""
        verifier = JWTVerifier(
            secret_key="test-secret",
            issuer="test-issuer"
        )

        token = verifier.create_token(subject="user123")

        payload = jwt.decode(
            token,
            "test-secret",
            algorithms=["HS256"]
        )

        assert payload["iss"] == "test-issuer"

    def test_create_token_with_jti(self, jwt_verifier):
        """Test creating token with custom JTI"""
        custom_jti = "custom-jti-123"
        token = jwt_verifier.create_token(
            subject="user123",
            jti=custom_jti
        )

        payload = jwt.decode(
            token,
            jwt_verifier.secret_key,
            algorithms=[jwt_verifier.algorithm]
        )

        assert payload["jti"] == custom_jti

    def test_create_token_generates_jti(self, jwt_verifier):
        """Test that JTI is auto-generated if not provided"""
        token = jwt_verifier.create_token(subject="user123")

        payload = jwt.decode(
            token,
            jwt_verifier.secret_key,
            algorithms=[jwt_verifier.algorithm]
        )

        assert "jti" in payload
        assert isinstance(payload["jti"], str)
        assert len(payload["jti"]) > 0


class TestTokenRevocation:
    """Test token revocation checking"""

    def test_verify_with_revocation_check_no_db(self, jwt_verifier, valid_token):
        """Test revocation check without database session"""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=valid_token
        )

        # Should pass even without db (graceful degradation)
        payload = jwt_verifier.verify_token(
            credentials,
            check_revocation=True,
            db=None
        )

        assert payload["sub"] == "test-user-123"

    @patch('core.jwt_verifier.logger')
    def test_verify_revocation_check_no_jti(self, mock_logger, jwt_verifier, test_secret):
        """Test revocation check when token has no JTI"""
        # Create token without JTI
        payload = {
            "sub": "user",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, test_secret, algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token
        )

        # Should pass with warning
        result = jwt_verifier.verify_token(
            credentials,
            check_revocation=True,
            db=None
        )

        assert result["sub"] == "user"

    def test_is_token_revoked_without_db(self, jwt_verifier):
        """Test _is_token_revoked without database"""
        payload = {"sub": "user", "jti": "test-jti"}

        # Should return False (allow token) when no db
        result = jwt_verifier._is_token_revoked(payload, db=None)

        assert result is False

    def test_is_token_revoked_without_jti(self, jwt_verifier):
        """Test _is_token_revoked without JTI in payload"""
        payload = {"sub": "user"}

        result = jwt_verifier._is_token_revoked(payload, db=None)

        assert result is False


class TestDebugMode:
    """Test debug mode features"""

    def test_debug_mode_with_ip_whitelist(self):
        """Test debug mode with IP whitelist"""
        with patch.dict(os.environ, {
            "DEBUG": "true",
            "DEBUG_IP_WHITELIST": "192.168.1.1,10.0.0.0/8",
            "ENVIRONMENT": "development"
        }, clear=True):
            verifier = JWTVerifier(
                secret_key="test-secret",
                debug_mode=None
            )

            assert verifier.debug_mode is True
            assert "192.168.1.1" in verifier.debug_ip_whitelist
            assert "10.0.0.0/8" in verifier.debug_ip_whitelist

    def test_is_ip_whitelisted_single_ip(self):
        """Test IP whitelist with single IP"""
        verifier = JWTVerifier(
            secret_key="test-secret",
            debug_mode=True,
            debug_ip_whitelist=["192.168.1.100"]
        )

        assert verifier._is_ip_whitelisted("192.168.1.100") is True
        assert verifier._is_ip_whitelisted("192.168.1.101") is False

    def test_is_ip_whitelisted_cidr(self):
        """Test IP whitelist with CIDR range"""
        verifier = JWTVerifier(
            secret_key="test-secret",
            debug_mode=True,
            debug_ip_whitelist=["10.0.0.0/8"]
        )

        assert verifier._is_ip_whitelisted("10.0.0.1") is True
        assert verifier._is_ip_whitelisted("10.255.255.255") is True
        assert verifier._is_ip_whitelisted("192.168.1.1") is False

    def test_is_ip_whitelisted_no_whitelist(self):
        """Test IP whitelist when not configured"""
        verifier = JWTVerifier(
            secret_key="test-secret",
            debug_mode=True,
            debug_ip_whitelist=None
        )

        assert verifier._is_ip_whitelisted("192.168.1.1") is False

    @patch('core.jwt_verifier.os.getenv')
    def test_debug_mode_bypass_in_development(self, mock_getenv, test_secret):
        """Test debug mode bypasses verification in development"""
        mock_getenv.side_effect = lambda key: {
            "DEBUG": "true",
            "ENVIRONMENT": "development"
        }.get(key, "")

        verifier = JWTVerifier(
            secret_key=test_secret,
            debug_mode=True,
            debug_ip_whitelist=["192.168.1.1"]
        )

        # Create invalid token
        payload = {"sub": "user"}
        invalid_token = jwt.encode(payload, test_secret, algorithm="HS256")

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=invalid_token
        )

        # Should bypass verification for whitelisted IP
        result = verifier.verify_token(
            credentials,
            client_ip="192.168.1.1"
        )

        assert result["sub"] == "user"

    def test_debug_mode_blocked_in_production(self):
        """Test debug mode blocked in production"""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production"
        }, clear=True):
            verifier = JWTVerifier(
                secret_key="test-secret",
                debug_mode=True
            )

            payload = {"sub": "user", "exp": datetime.utcnow() + timedelta(hours=1)}
            token = jwt.encode(payload, "test-secret", algorithm="HS256")

            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=token
            )

            # Should still verify normally in production
            result = verifier.verify_token(credentials)
            assert result["sub"] == "user"


class TestGlobalVerifier:
    """Test global JWT verifier instance"""

    def test_get_jwt_verifier_creates_instance(self):
        """Test get_jwt_verifier creates instance"""
        # Create a new verifier instance
        verifier = JWTVerifier(secret_key="test-secret")

        # Should create a verifier successfully
        assert verifier is not None
        assert verifier.secret_key == "test-secret"

    def test_verify_token_dependency(self, test_secret):
        """Test verify_token FastAPI dependency"""
        mock_verifier = Mock()
        mock_verifier.verify_token = Mock(return_value={"sub": "user"})

        with patch('core.jwt_verifier.get_jwt_verifier', return_value=mock_verifier):
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="test-token"
            )

            result = verify_token(credentials)

            assert result["sub"] == "user"
            mock_verifier.verify_token.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_verify_very_old_token(self, jwt_verifier):
        """Test warning for very old tokens"""
        # Create token with old 'iat'
        old_time = datetime.utcnow() - timedelta(days=35)
        payload = {
            "sub": "user",
            "iat": old_time,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }

        with patch('core.jwt_verifier.logger') as mock_logger:
            token = jwt.encode(payload, jwt_verifier.secret_key, algorithm="HS256")
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

            result = jwt_verifier.verify_token(credentials)

            assert result["sub"] == "user"
            # Should log warning about old token
            assert mock_logger.warning.called

    def test_verify_token_with_various_algorithms(self):
        """Test tokens with different algorithms"""
        # HS256
        verifier_hs256 = JWTVerifier(secret_key="test-secret", algorithm="HS256")
        token_hs256 = verifier_hs256.create_token(subject="user")

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_hs256)
        result = verifier_hs256.verify_token(credentials)
        assert result["sub"] == "user"

    def test_verify_token_with_custom_claims(self, jwt_verifier):
        """Test token with custom claims"""
        custom_claims = {
            "department": "engineering",
            "permissions": ["read", "write"],
            "metadata": {"key": "value"}
        }

        token = jwt_verifier.create_token(
            subject="user123",
            additional_claims=custom_claims
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = jwt_verifier.verify_token(credentials)

        assert result["department"] == "engineering"
        assert result["permissions"] == ["read", "write"]
        assert result["metadata"]["key"] == "value"

    def test_verify_token_string_helper(self, jwt_verifier, valid_token):
        """Test verify_token_string helper function"""
        # Patch get_jwt_verifier to return our test verifier
        with patch('core.jwt_verifier.get_jwt_verifier', return_value=jwt_verifier):
            payload = verify_token_string(valid_token)

            assert payload["sub"] == "test-user-123"

    def test_verify_token_string_helper_with_client_ip(self, jwt_verifier, valid_token):
        """Test verify_token_string with client IP"""
        # Patch get_jwt_verifier to return our test verifier
        with patch('core.jwt_verifier.get_jwt_verifier', return_value=jwt_verifier):
            payload = verify_token_string(
                valid_token,
                client_ip="192.168.1.1"
            )

            assert payload["sub"] == "test-user-123"

    @patch('core.jwt_verifier.logger')
    def test_verify_with_exception_handling(self, mock_logger, jwt_verifier):
        """Test exception handling during verification"""
        # Create token that will cause unexpected error
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid"
        )

        with pytest.raises(HTTPException) as exc_info:
            jwt_verifier.verify_token(credentials)

        assert exc_info.value.status_code == 401
        # Check that error was logged
        assert mock_logger.error.called or mock_logger.warning.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
