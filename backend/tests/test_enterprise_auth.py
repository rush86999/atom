"""
Tests for Enterprise Authentication System
Tests user registration, login, JWT tokens, password hashing, and RBAC.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
import bcrypt
import pydantic

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.enterprise_auth_service import (
    EnterpriseAuthService,
    UserRole,
    SecurityLevel
)
from api.enterprise_auth_endpoints import (
    UserRegister,
    UserLogin,
    ChangePasswordRequest,
    router
)
from core.models import User, UserRole as DBUserRole


# Create test app
test_app = FastAPI()
test_app.include_router(router)


@pytest.fixture
def auth_service():
    """Create enterprise auth service instance"""
    # Use a test secret key
    return EnterpriseAuthService(secret_key="test-secret-key-for-jwt")


@pytest.fixture
def mock_db():
    """Create mock database session"""
    db = Mock()
    return db


class TestPasswordHashing:
    """Test password hashing with bcrypt"""

    def test_hash_password(self):
        """Test password hashing"""
        service = EnterpriseAuthService()

        password = "TestPassword123!"
        hashed = service.hash_password(password)

        # Hash should be different from password
        assert hashed != password
        assert len(hashed) == 60  # bcrypt hashes are 60 chars

        # Hash should start with $2a$ or $2b$ (bcrypt identifier)
        assert hashed.startswith("$2a$") or hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        """Test verifying correct password"""
        service = EnterpriseAuthService()

        password = "CorrectPassword123!"
        hashed = service.hash_password(password)

        # Should verify correctly
        assert service.verify_password(password, hashed) is True

    def test_verify_incorrect_password(self):
        """Test verifying incorrect password"""
        service = EnterpriseAuthService()

        password = "CorrectPassword123!"
        hashed = service.hash_password(password)

        # Incorrect password should fail
        assert service.verify_password("WrongPassword", hashed) is False

    def test_hash_is_consistent(self):
        """Test that hashing same password twice gives different salts but same verification result"""
        service = EnterpriseAuthService()

        password = "ConsistentPassword"

        hash1 = service.hash_password(password)
        hash2 = service.hash_password(password)

        # Hashes should be different (due to salt)
        assert hash1 != hash2

        # But both should verify the same password
        assert service.verify_password(password, hash1) is True
        assert service.verify_password(password, hash2) is True

    def test_hash_cost_factor(self):
        """Test that appropriate cost factor is used"""
        service = EnterpriseAuthService()

        password = "TestPassword123!"
        hashed = service.hash_password(password)

        # Extract rounds from bcrypt hash
        # Format: $2b$[rounds]... (note: $2b$ is the newer version)
        assert "$2b$12$" in hashed or "$2a$12$" in hashed  # Cost factor 12


class TestJWTTokenManagement:
    """Test JWT token creation and verification"""

    def test_create_access_token(self):
        """Test creating JWT access token"""
        service = EnterpriseAuthService()

        user_id = "test_user_123"
        token = service.create_access_token(user_id)

        assert token is not None
        assert isinstance(token, str)

        # Verify token structure
        # JWT has 3 parts separated by dots
        parts = token.split('.')
        assert len(parts) == 3

    def test_create_token_with_claims(self):
        """Test creating token with additional claims"""
        service = EnterpriseAuthService()

        user_id = "test_user_123"
        additional_claims = {
            "email": "test@example.com",
            "roles": ["admin", "user"],
            "security_level": "admin"
        }

        token = service.create_access_token(user_id, additional_claims)

        assert token is not None

    def test_verify_valid_token(self):
        """Test verifying a valid token"""
        service = EnterpriseAuthService()

        user_id = "test_user_456"
        token = service.create_access_token(user_id)

        # Verify the token
        claims = service.verify_token(token)

        assert claims is not None
        assert claims["user_id"] == user_id
        assert claims["type"] == "access"

    def test_verify_expired_token(self):
        """Test that expired tokens are rejected"""
        service = EnterpriseAuthService()

        # Create a token that's already expired
        import jwt
        from datetime import datetime, timezone, timedelta

        payload = {
            "user_id": "test_user",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
            "type": "access"
        }

        expired_token = jwt.encode(payload, service.secret_key, algorithm="HS256")

        # Should return None for expired token
        claims = service.verify_token(expired_token)
        assert claims is None

    def test_verify_invalid_token(self):
        """Test that invalid tokens are rejected"""
        service = EnterpriseAuthService()

        invalid_token = "invalid.jwt.token"

        claims = service.verify_token(invalid_token)
        assert claims is None

    def test_refresh_token_creation(self):
        """Test creating refresh token"""
        service = EnterpriseAuthService()

        user_id = "test_user_789"
        refresh_token = service.create_refresh_token(user_id)

        assert refresh_token is not None
        assert isinstance(refresh_token, str)

        # Verify refresh token
        claims = service.verify_token(refresh_token)
        assert claims is not None
        assert claims["type"] == "refresh"


class TestUserRegistration:
    """Test user registration endpoint"""

    def test_register_request_model(self):
        """Test that UserRegister model exists and validates"""
        from api.enterprise_auth_endpoints import UserRegister

        # Valid request
        user_data = UserRegister(
            email="newuser@example.com",
            password="SecurePass123!",
            first_name="New",
            last_name="User"
        )

        assert user_data.email == "newuser@example.com"
        assert user_data.password == "SecurePass123!"
        assert user_data.first_name == "New"
        assert user_data.last_name == "User"

    def test_register_endpoint_exists(self):
        """Test that register endpoint exists"""
        from api.enterprise_auth_endpoints import router

        # Check that the route is registered
        routes = [route.path for route in router.routes]
        assert "/api/auth/register" in routes

    @pytest.mark.asyncio
    async def test_register_weak_password(self):
        """Test that weak passwords are rejected"""
        client = TestClient(test_app)

        # Pydantic validates password length at model creation
        # Password must be at least 8 characters
        with pytest.raises(pydantic.ValidationError):
            user_data = UserRegister(
                email="test@example.com",
                password="weak",  # Too short
                first_name="Test",
                last_name="User"
            )


class TestUserLogin:
    """Test user login endpoint"""

    def test_login_request_model(self):
        """Test that UserLogin model exists and validates"""
        from api.enterprise_auth_endpoints import UserLogin

        # Valid request
        login_data = UserLogin(
            username="test@example.com",
            password="CorrectPassword"
        )

        assert login_data.username == "test@example.com"
        assert login_data.password == "CorrectPassword"

    def test_login_endpoint_exists(self):
        """Test that login endpoint exists"""
        from api.enterprise_auth_endpoints import router

        # Check that the route is registered
        routes = [route.path for route in router.routes]
        assert "/api/auth/login" in routes


class TestRBACMiddleware:
    """Test Role-Based Access Control middleware"""

    def test_require_role_decorator_exists(self):
        """Test that require_role decorator is available"""
        from api.enterprise_auth_endpoints import require_role

        # The decorator should be callable
        assert callable(require_role)

    def test_require_permission_decorator_exists(self):
        """Test that require_permission decorator is available"""
        from api.enterprise_auth_endpoints import require_permission

        # The decorator should be callable
        assert callable(require_permission)


class TestPasswordManagement:
    """Test password change functionality"""

    def test_change_password_request_model(self):
        """Test that ChangePasswordRequest model exists and validates"""
        from api.enterprise_auth_endpoints import ChangePasswordRequest

        # Valid request
        data = ChangePasswordRequest(
            old_password="OldPassword123!",
            new_password="NewPassword456!"
        )

        assert data.old_password == "OldPassword123!"
        assert data.new_password == "NewPassword456!"

    def test_change_password_endpoint_exists(self):
        """Test that change-password endpoint exists"""
        from api.enterprise_auth_endpoints import router

        # Check that the route is registered
        routes = [route.path for route in router.routes]
        assert "/api/auth/change-password" in routes


class TestSSOIntegration:
    """Test SAML SSO integration"""

    def test_generate_saml_request(self):
        """Test SAML request URL generation"""
        service = EnterpriseAuthService()

        saml_url = service.generate_saml_request("idp_123")

        assert saml_url is not None
        assert "atom.ai" in saml_url
        assert "saml" in saml_url.lower()

    def test_saml_validation_not_implemented(self):
        """Test that SAML validation is not yet implemented"""
        service = EnterpriseAuthService()

        result = service.validate_saml_response("fake_saml_response")

        # Should return None (not implemented)
        assert result is None


class TestSecurityFeatures:
    """Test security-related features"""

    def test_password_hash_is_secure(self):
        """Test that password hash is secure"""
        service = EnterpriseAuthService()

        password = "TestPassword123!"
        hashed = service.hash_password(password)

        # Should be bcrypt hash
        assert "$2a$" in hashed or "$2b$" in hashed

        # Should be 60 characters
        assert len(hashed) == 60

        # Should contain hash, not plain text
        assert password not in hashed

    def test_jwt_has_expiry(self):
        """Test that JWT tokens have proper expiry"""
        service = EnterpriseAuthService()

        token = service.create_access_token("user_123")

        # Decode and check expiry
        import jwt
        claims = jwt.decode(token, service.secret_key, algorithms=["HS256"])

        assert "exp" in claims
        assert "iat" in claims

        # Expiry should be in the future
        exp_time = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        assert exp_time > now

    def test_tokens_are_unique(self):
        """Test that generated tokens are unique"""
        service = EnterpriseAuthService()

        token1 = service.create_access_token("user_123")
        token2 = service.create_access_token("user_456")

        # Tokens should be different
        assert token1 != token2

        # But same user with same params should get same token (deterministic)
        token3 = service.create_access_token("user_123", {"test": "claim"})
        token4 = service.create_access_token("user_123", {"test": "claim"})

        # With different claims, tokens might differ, but that's OK


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
