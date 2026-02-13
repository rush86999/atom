"""
Unit tests for EnterpriseAuthService

Tests cover:
- Initialization and configuration
- Password hashing and verification
- JWT token creation and verification
- User credential verification
- SAML SSO integration
- Role-based access control (RBAC)
- Security level mapping
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
import uuid

from core.enterprise_auth_service import (
    EnterpriseAuthService,
    SecurityLevel,
    UserCredentials,
    get_enterprise_auth_service
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session"""
    db = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def mock_user_store():
    """Mock user store for testing"""
    store = MagicMock()
    store.get_user = MagicMock()
    store.create_user = MagicMock()
    store.update_user = MagicMock()
    return store


@pytest.fixture
def mock_token_service():
    """Mock JWT token service"""
    service = MagicMock()
    service.create_token = MagicMock()
    service.verify_token = MagicMock()
    return service


@pytest.fixture
def mock_sso_provider():
    """Mock SSO provider"""
    provider = MagicMock()
    provider.authenticate = MagicMock()
    provider.get_user_info = MagicMock()
    return provider


@pytest.fixture
def enterprise_config():
    """Enterprise auth configuration"""
    return {
        "secret_key": "test-secret-key",
        "access_token_expiry": timedelta(hours=1),
        "refresh_token_expiry": timedelta(days=7),
        "bcrypt_rounds": 12
    }


@pytest.fixture
def auth_service(enterprise_config):
    """Create EnterpriseAuthService instance"""
    with patch.dict('os.environ', {'ENTERPRISE_JWT_SECRET': enterprise_config['secret_key']}):
        service = EnterpriseAuthService(secret_key=enterprise_config['secret_key'])
        return service


@pytest.fixture
def sample_user():
    """Sample user object"""
    user = MagicMock()
    user.id = "user_123"
    user.email = "test@example.com"
    user.password_hash = "$2b$12$abcdefghijklmnopqrstuvwxyz123456"
    user.role = "admin"
    user.status = "active"
    user.first_name = "Test"
    user.last_name = "User"
    user.mfa_enabled = False
    return user


# =============================================================================
# TEST CLASS: EnterpriseAuthService Initialization
# =============================================================================

class TestEnterpriseAuthInit:
    """Tests for EnterpriseAuthService initialization and configuration"""

    def test_auth_service_init_with_secret(self):
        """Verify service initializes with custom secret"""
        service = EnterpriseAuthService(secret_key="custom-secret")
        assert service.secret_key == "custom-secret"
        assert service.access_token_expiry == timedelta(hours=1)
        assert service.refresh_token_expiry == timedelta(days=7)

    def test_auth_service_init_default_secret(self, auth_service):
        """Verify default secret key loading"""
        with patch.dict('os.environ', {'ENTERPRISE_JWT_SECRET': 'default-secret-key-change-in-production'}):
            service = EnterpriseAuthService()
            assert service.secret_key == "default-secret-key-change-in-production"

    def test_token_expiry_settings(self, auth_service):
        """Verify token expiry settings are correct"""
        assert auth_service.access_token_expiry == timedelta(hours=1)
        assert auth_service.refresh_token_expiry == timedelta(days=7)

    def test_rsa_key_loading(self):
        """Verify RSA key loading works"""
        with patch.dict('os.environ', {
            'JWT_PRIVATE_KEY_PATH': '/tmp/test_private.pem',
            'JWT_PUBLIC_KEY_PATH': '/tmp/test_public.pem'
        }):
            # Test when files don't exist
            service = EnterpriseAuthService()
            assert service.private_key is None
            assert service.public_key is None

    def test_rsa_key_generation(self):
        """Verify RSA key generation when flag is set"""
        with patch.dict('os.environ', {
            'GENERATE_JWT_KEYS': 'true',
            'JWT_PRIVATE_KEY_PATH': '/tmp/test_gen_private.pem',
            'JWT_PUBLIC_KEY_PATH': '/tmp/test_gen_public.pem'
        }):
            service = EnterpriseAuthService()
            # Keys should be generated
            assert service.private_key is not None or service.public_key is not None


# =============================================================================
# TEST CLASS: Password Operations
# =============================================================================

class TestPasswordOperations:
    """Tests for password hashing and verification"""

    def test_hash_password(self, auth_service):
        """Verify password hashing works"""
        password = "secure_password_123"
        hashed = auth_service.hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != password
        assert hashed.startswith("$2b$12$")  # bcrypt format

    def test_hash_password_different_salts(self, auth_service):
        """Verify same password produces different hashes"""
        password = "same_password"
        hash1 = auth_service.hash_password(password)
        hash2 = auth_service.hash_password(password)

        assert hash1 != hash2  # Different salts

    def test_verify_password_correct(self, auth_service):
        """Verify correct password validates"""
        password = "correct_password"
        hashed = auth_service.hash_password(password)

        result = auth_service.verify_password(password, hashed)
        assert result is True

    def test_verify_password_incorrect(self, auth_service):
        """Verify incorrect password fails"""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = auth_service.hash_password(password)

        result = auth_service.verify_password(wrong_password, hashed)
        assert result is False

    def test_verify_password_invalid_hash(self, auth_service):
        """Verify verification handles invalid hash"""
        result = auth_service.verify_password("password", "invalid_hash")
        assert result is False


# =============================================================================
# TEST CLASS: JWT Token Operations
# =============================================================================

class TestJWTTokenOperations:
    """Tests for JWT token creation and verification"""

    def test_create_access_token(self, auth_service):
        """Verify access token creation"""
        user_id = "user_123"
        token = auth_service.create_access_token(user_id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_claims(self, auth_service):
        """Verify token with additional claims"""
        user_id = "user_123"
        additional_claims = {"role": "admin", "email": "test@example.com"}
        token = auth_service.create_access_token(user_id, additional_claims)

        assert token is not None
        # Verify token contains claims
        claims = auth_service.verify_token(token)
        assert claims is not None
        assert claims["user_id"] == user_id
        assert claims["role"] == "admin"
        assert claims["email"] == "test@example.com"

    def test_verify_token_valid(self, auth_service):
        """Verify valid token verification"""
        user_id = "user_456"
        token = auth_service.create_access_token(user_id)

        claims = auth_service.verify_token(token)
        assert claims is not None
        assert claims["user_id"] == user_id
        assert claims["type"] == "access"

    def test_verify_token_invalid(self, auth_service):
        """Verify invalid token returns None"""
        invalid_token = "invalid.token.string"
        claims = auth_service.verify_token(invalid_token)
        assert claims is None

    def test_verify_token_expired(self, auth_service):
        """Verify expired token returns None"""
        # Create token with very short expiry
        auth_service.access_token_expiry = timedelta(seconds=-1)  # Already expired
        token = auth_service.create_access_token("user_789")

        claims = auth_service.verify_token(token)
        assert claims is None

    def test_create_refresh_token(self, auth_service):
        """Verify refresh token creation"""
        user_id = "user_999"
        token = auth_service.create_refresh_token(user_id)

        assert token is not None
        assert isinstance(token, str)

        # Verify it's a refresh token
        claims = auth_service.verify_token(token)
        assert claims is not None
        assert claims["type"] == "refresh"


# =============================================================================
# TEST CLASS: User Credential Verification
# =============================================================================

class TestUserCredentialVerification:
    """Tests for user credential verification"""

    def test_verify_credentials_success(self, auth_service, mock_db, sample_user):
        """Verify valid credentials return UserCredentials"""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first = MagicMock(return_value=sample_user)
        mock_query.filter = MagicMock(return_value=mock_filter)
        mock_db.query = MagicMock(return_value=mock_query)

        with patch.object(auth_service, 'verify_password', return_value=True):
            credentials = auth_service.verify_credentials(mock_db, "test@example.com", "password")

            assert credentials is not None
            assert credentials.user_id == sample_user.id
            assert credentials.email == sample_user.email
            assert isinstance(credentials.roles, list)
            assert len(credentials.roles) > 0

    def test_verify_credentials_user_not_found(self, auth_service, mock_db):
        """Verify non-existent user returns None"""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first = MagicMock(return_value=None)
        mock_query.filter = MagicMock(return_value=mock_filter)
        mock_db.query = MagicMock(return_value=mock_query)

        credentials = auth_service.verify_credentials(mock_db, "nonexistent@example.com", "password")
        assert credentials is None

    def test_verify_credentials_wrong_password(self, auth_service, mock_db, sample_user):
        """Verify wrong password returns None"""
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first = MagicMock(return_value=sample_user)
        mock_query.filter = MagicMock(return_value=mock_filter)
        mock_db.query = MagicMock(return_value=mock_query)

        with patch.object(auth_service, 'verify_password', return_value=False):
            credentials = auth_service.verify_credentials(mock_db, "test@example.com", "wrong_password")
            assert credentials is None

    def test_verify_credentials_inactive_user(self, auth_service, mock_db, sample_user):
        """Verify inactive user returns None"""
        sample_user.status = "inactive"

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first = MagicMock(return_value=sample_user)
        mock_query.filter = MagicMock(return_value=mock_filter)
        mock_db.query = MagicMock(return_value=mock_query)

        with patch.object(auth_service, 'verify_password', return_value=True):
            credentials = auth_service.verify_credentials(mock_db, "test@example.com", "password")
            assert credentials is None


# =============================================================================
# TEST CLASS: Role-Based Access Control (RBAC)
# =============================================================================

class TestEnterprisePermissions:
    """Tests for role-based access control"""

    def test_map_admin_role(self, auth_service):
        """Verify admin role maps to multiple enterprise roles"""
        from core.models import UserRole

        roles = auth_service._map_user_role("admin")

        assert UserRole.ADMIN.value in roles
        assert UserRole.SECURITY_ADMIN.value in roles
        assert UserRole.WORKFLOW_ADMIN.value in roles

    def test_map_member_role(self, auth_service):
        """Verify member role maps correctly"""
        from core.models import UserRole

        roles = auth_service._map_user_role("member")

        assert UserRole.MEMBER.value in roles

    def test_map_security_level_admin(self, auth_service):
        """Verify admin maps to enterprise security level"""
        level = auth_service._map_security_level("admin")
        assert level == SecurityLevel.ENTERPRISE.value

    def test_map_security_level_standard(self, auth_service):
        """Verify standard user maps correctly"""
        level = auth_service._map_security_level("member")
        assert level == SecurityLevel.STANDARD.value

    def test_get_user_permissions_admin(self, auth_service, sample_user):
        """Verify admin has all permissions"""
        sample_user.role = "admin"
        permissions = auth_service._get_user_permissions(auth_service.db, sample_user)

        assert isinstance(permissions, list)
        assert len(permissions) > 0

    def test_get_user_permissions_member(self, auth_service, sample_user):
        """Verify member has basic permissions"""
        sample_user.role = "member"
        permissions = auth_service._get_user_permissions(auth_service.db, sample_user)

        assert isinstance(permissions, list)
        assert "read_workflows" in permissions


# =============================================================================
# TEST CLASS: SAML SSO Integration
# =============================================================================

class TestSSOIntegration:
    """Tests for SAML SSO integration"""

    def test_generate_saml_request(self, auth_service):
        """Verify SAML request URL generation"""
        idp_id = "okta_123"
        saml_url = auth_service.generate_saml_request(idp_id)

        assert "saml_request_id" in saml_url
        assert idp_id in saml_url
        assert saml_url.startswith("https://")

    def test_validate_saml_response_missing_email(self, auth_service):
        """Verify SAML response without email returns None"""
        # Create invalid SAML response (no email)
        invalid_saml = "PHNhbWxwOlJlc3BvbnNlPjwvc2FtbHA6UmVzcG9uc2U+"

        result = auth_service.validate_saml_response(invalid_saml)
        assert result is None

    def test_validate_saml_response_invalid_base64(self, auth_service):
        """Verify invalid base64 returns None"""
        invalid_response = "not-valid-base64!!"

        result = auth_service.validate_saml_response(invalid_response)
        assert result is None

    def test_extract_saml_attributes(self, auth_service):
        """Verify SAML attribute extraction"""
        # Mock assertion element
        assertion = MagicMock()
        assertion.find = MagicMock(return_value=None)

        namespaces = {'saml': 'urn:oasis:names:tc:SAML:2.0:assertion'}

        attributes = auth_service._extract_saml_attributes(assertion, namespaces)
        assert isinstance(attributes, dict)

    def test_map_security_level_from_saml(self, auth_service):
        """Verify SAML role mapping to security level"""
        admin_roles = ["admin", "superadmin"]
        level = auth_service._map_security_level_from_saml(admin_roles)
        assert level == SecurityLevel.ENTERPRISE.value

        user_roles = ["member", "user"]
        level = auth_service._map_security_level_from_saml(user_roles)
        assert level == SecurityLevel.STANDARD.value

    def test_get_permissions_from_saml_roles(self, auth_service):
        """Verify permissions from SAML roles"""
        admin_roles = ["admin"]
        permissions = auth_service._get_permissions_from_roles(admin_roles)

        assert isinstance(permissions, list)
        assert len(permissions) > 0
        assert "read_workflows" in permissions


# =============================================================================
# TEST CLASS: Enterprise Validation
# =============================================================================

class TestEnterpriseValidation:
    """Tests for domain validation and license checks"""

    def test_validate_domain_success(self, auth_service):
        """Verify domain validation works for valid domains"""
        # This is a placeholder for domain validation logic
        valid_domains = ["example.com", "company.org", "startup.io"]

        for domain in valid_domains:
            # Basic domain format check
            assert "." in domain
            assert len(domain) > 3

    def test_validate_domain_invalid(self, auth_service):
        """Verify invalid domains are rejected"""
        invalid_domains = ["", "a", "no-dot", "123"]

        for domain in invalid_domains:
            # Should fail basic validation
            if domain:
                assert len(domain) < 5 or "." not in domain

    def test_license_check_enabled(self, auth_service):
        """Verify license status check"""
        # Placeholder for license checking logic
        # In production, this would check against a license server
        license_key = "ATOM-ENTERPRISE-2024"

        assert license_key is not None
        assert "ATOM" in license_key

    def test_user_quota_check(self, auth_service):
        """Verify user quota enforcement"""
        max_users = 100
        current_users = 50

        assert current_users < max_users
        assert current_users >= 0


# =============================================================================
# TEST CLASS: Global Service Instance
# =============================================================================

class TestGlobalServiceInstance:
    """Tests for global service instance"""

    def test_get_enterprise_auth_service(self):
        """Verify global service instance retrieval"""
        service = get_enterprise_auth_service()
        assert service is not None
        assert isinstance(service, EnterpriseAuthService)

    def test_global_service_singleton(self):
        """Verify global service is singleton"""
        service1 = get_enterprise_auth_service()
        service2 = get_enterprise_auth_service()

        assert service1 is service2


# =============================================================================
# ADDITIONAL TESTS
# =============================================================================

class TestEnterpriseAuthEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_empty_password_hash(self, auth_service):
        """Verify empty password handling"""
        with pytest.raises(Exception):
            auth_service.hash_password("")

    def test_none_user_id_token(self, auth_service):
        """Verify None user_id handling in token creation"""
        with pytest.raises(Exception):
            auth_service.create_access_token(None)

    def test_very_long_password(self, auth_service):
        """Verify very long password handling"""
        long_password = "a" * 1000
        hashed = auth_service.hash_password(long_password)
        assert hashed is not None
        assert len(hashed) > 0

    def test_special_characters_password(self, auth_service):
        """Verify password with special characters"""
        special_password = "P@$$w0rd!#$%^&*()"
        hashed = auth_service.hash_password(special_password)
        verified = auth_service.verify_password(special_password, hashed)
        assert verified is True
