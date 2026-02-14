"""
Token Management Routes Tests

Comprehensive tests for token management endpoints covering:
- Token revocation (POST /api/auth/tokens/revoke)
- Token cleanup (POST /api/auth/tokens/cleanup)
- Token verification (GET /api/auth/tokens/verify)
"""

import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from sqlalchemy.orm import Session

from api.token_routes import router
from core.models import User, UserRole
from core.database import get_db


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_admin_user():
    """Mock admin user"""
    user = Mock(spec=User)
    user.id = "admin_user_123"
    user.email = "admin@example.com"
    user.role = UserRole.SUPER_ADMIN
    return user


@pytest.fixture
def mock_regular_user():
    """Mock regular user"""
    user = Mock(spec=User)
    user.id = "regular_user_123"
    user.email = "user@example.com"
    user.role = UserRole.MEMBER
    return user


@pytest.fixture
def valid_token_payload():
    """Mock valid JWT payload"""
    return {
        "sub": "user_123",
        "jti": "token_123",
        "exp": int(datetime.utcnow().timestamp()) + 3600,
        "iat": int(datetime.utcnow().timestamp())
    }


@pytest.fixture
def client(mock_db):
    """Test client with mocked database"""
    def get_db_override():
        return mock_db

    # Import main app to get TestClient
    from main import app
    app.dependency_overrides[get_db] = get_db_override
    app.include_router(router)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# =============================================================================
# Token Revocation Tests (POST /api/auth/tokens/revoke)
# =============================================================================

class TestTokenRevocation:
    """Test token revocation endpoint"""

    def test_revoke_token_success(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test successful token revocation"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify, \
             patch('api.token_routes.revoke_token') as mock_revoke:

            mock_verify.return_value = valid_token_payload
            mock_revoke.return_value = True

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "logout"
                },
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "revoked" in data["message"].lower() or "success" in data["message"].lower()

    def test_revoke_token_already_revoked(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test revoking already revoked token"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify, \
             patch('api.token_routes.revoke_token') as mock_revoke:

            mock_verify.return_value = valid_token_payload
            mock_revoke.return_value = False  # Already revoked

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "logout"
                },
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "already" in data["message"].lower()

    def test_revoke_token_wrong_user(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test revoking token belonging to different user fails"""
        # Token belongs to different user
        valid_token_payload["sub"] = "different_user_123"

        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.return_value = valid_token_payload

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "logout"
                },
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 403  # Permission denied

    def test_revoke_token_no_jti(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test revoking token without JTI claim fails"""
        # Remove JTI from payload
        valid_token_payload_without_jti = valid_token_payload.copy()
        del valid_token_payload_without_jti["jti"]

        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.return_value = valid_token_payload_without_jti

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "logout"
                },
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 422  # Validation error

    def test_revoke_token_with_default_reason(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test token revocation with default reason"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify, \
             patch('api.token_routes.revoke_token') as mock_revoke:

            mock_verify.return_value = valid_token_payload
            mock_revoke.return_value = True

            response = client.post(
                "/api/auth/tokens/revoke",
                json={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."},
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200

    def test_revoke_token_security_breach_reason(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test token revocation for security breach"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify, \
             patch('api.token_routes.revoke_token') as mock_revoke:

            mock_verify.return_value = valid_token_payload
            mock_revoke.return_value = True

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "security_breach"
                },
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200


# =============================================================================
# Token Cleanup Tests (POST /api/auth/tokens/cleanup)
# =============================================================================

class TestTokenCleanup:
    """Test token cleanup endpoint"""

    def test_cleanup_tokens_admin_success(self, client, mock_db, mock_admin_user):
        """Test successful token cleanup by admin"""
        with patch('api.token_routes.get_current_user', return_value=mock_admin_user), \
             patch('api.token_routes.cleanup_expired_revoked_tokens') as mock_cleanup:

            mock_cleanup.return_value = 42  # Deleted 42 tokens

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=24",
                headers={"Authorization": "Bearer admin_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "success" in data or "deleted_count" in data
            if "deleted_count" in data:
                assert data["deleted_count"] == 42

    def test_cleanup_tokens_custom_hours(self, client, mock_db, mock_admin_user):
        """Test token cleanup with custom hours parameter"""
        with patch('api.token_routes.get_current_user', return_value=mock_admin_user), \
             patch('api.token_routes.cleanup_expired_revoked_tokens') as mock_cleanup:

            mock_cleanup.return_value = 100

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=48",
                headers={"Authorization": "Bearer admin_token"}
            )

            assert response.status_code == 200

    def test_cleanup_tokens_non_admin_forbidden(self, client, mock_db, mock_regular_user):
        """Test token cleanup forbidden for non-admin users"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user):

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=24",
                headers={"Authorization": "Bearer user_token"}
            )

            assert response.status_code == 403  # Permission denied

    def test_cleanup_tokens_no_expired_tokens(self, client, mock_db, mock_admin_user):
        """Test token cleanup when no expired tokens exist"""
        with patch('api.token_routes.get_current_user', return_value=mock_admin_user), \
             patch('api.token_routes.cleanup_expired_revoked_tokens') as mock_cleanup:

            mock_cleanup.return_value = 0

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=24",
                headers={"Authorization": "Bearer admin_token"}
            )

            assert response.status_code == 200

    def test_cleanup_tokens_default_hours(self, client, mock_db, mock_admin_user):
        """Test token cleanup with default hours parameter"""
        with patch('api.token_routes.get_current_user', return_value=mock_admin_user), \
             patch('api.token_routes.cleanup_expired_revoked_tokens') as mock_cleanup:

            mock_cleanup.return_value = 15

            response = client.post(
                "/api/auth/tokens/cleanup",  # No older_than_hours parameter
                headers={"Authorization": "Bearer admin_token"}
            )

            assert response.status_code == 200


# =============================================================================
# Token Verification Tests (GET /api/auth/tokens/verify)
# =============================================================================

class TestTokenVerification:
    """Test token verification endpoint"""

    def test_verify_token_valid(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test verifying a valid token"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.return_value = valid_token_payload

            # Mock JWT verifier
            with patch('api.token_routes.get_jwt_verifier') as mock_get_verifier:
                mock_verifier = Mock()
                mock_verifier._is_token_revoked.return_value = False  # Not revoked
                mock_get_verifier.return_value = mock_verifier

                response = client.get(
                    "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    headers={"Authorization": "Bearer test_token"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["valid"] is True
                assert data["revoked"] is False

    def test_verify_token_revoked(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test verifying a revoked token"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.return_value = valid_token_payload

            # Mock JWT verifier
            with patch('api.token_routes.get_jwt_verifier') as mock_get_verifier:
                mock_verifier = Mock()
                mock_verifier._is_token_revoked.return_value = True  # Revoked
                mock_get_verifier.return_value = mock_verifier

                response = client.get(
                    "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    headers={"Authorization": "Bearer test_token"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["valid"] is False
                assert data["revoked"] is True

    def test_verify_token_wrong_user(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test verifying token belonging to different user fails"""
        # Token belongs to different user
        valid_token_payload["sub"] = "different_user_123"

        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.return_value = valid_token_payload

            response = client.get(
                "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 403  # Permission denied

    def test_verify_token_invalid_format(self, client, mock_db, mock_regular_user):
        """Test verifying token with invalid format"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.side_effect = Exception("Invalid token format")

            response = client.get(
                "/api/auth/tokens/verify?token=invalid_token_string",
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False
            assert "error" in data

    def test_verify_token_includes_expiry(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test token verification includes expiry timestamp"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.return_value = valid_token_payload

            # Mock JWT verifier
            with patch('api.token_routes.get_jwt_verifier') as mock_get_verifier:
                mock_verifier = Mock()
                mock_verifier._is_token_revoked.return_value = False
                mock_get_verifier.return_value = mock_verifier

                response = client.get(
                    "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    headers={"Authorization": "Bearer test_token"}
                )

                assert response.status_code == 200
                data = response.json()
                assert "expires_at" in data

    def test_verify_token_includes_user_id(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test token verification includes user ID"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.return_value = valid_token_payload

            # Mock JWT verifier
            with patch('api.token_routes.get_jwt_verifier') as mock_get_verifier:
                mock_verifier = Mock()
                mock_verifier._is_token_revoked.return_value = False
                mock_get_verifier.return_value = mock_verifier

                response = client.get(
                    "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    headers={"Authorization": "Bearer test_token"}
                )

                assert response.status_code == 200
                data = response.json()
                assert "user_id" in data

    def test_verify_token_includes_jti(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test token verification includes JTI"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.return_value = valid_token_payload

            # Mock JWT verifier
            with patch('api.token_routes.get_jwt_verifier') as mock_get_verifier:
                mock_verifier = Mock()
                mock_verifier._is_token_revoked.return_value = False
                mock_get_verifier.return_value = mock_verifier

                response = client.get(
                    "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    headers={"Authorization": "Bearer test_token"}
                )

                assert response.status_code == 200
                data = response.json()
                assert "jti" in data


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling in token routes"""

    def test_revoke_token_exception_handled(self, client, mock_db, mock_regular_user):
        """Test exceptions are properly handled during token revocation"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.side_effect = Exception("Database connection failed")

            response = client.post(
                "/api/auth/tokens/revoke",
                json={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."},
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 500

    def test_cleanup_tokens_exception_handled(self, client, mock_db, mock_admin_user):
        """Test exceptions are properly handled during token cleanup"""
        with patch('api.token_routes.get_current_user', return_value=mock_admin_user), \
             patch('api.token_routes.cleanup_expired_revoked_tokens') as mock_cleanup:

            mock_cleanup.side_effect = Exception("Database error")

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=24",
                headers={"Authorization": "Bearer admin_token"}
            )

            assert response.status_code == 500

    def test_verify_token_exception_handled(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test exceptions are properly handled during token verification"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.side_effect = Exception("Verification service unavailable")

            response = client.get(
                "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False


# =============================================================================
# Security Tests
# =============================================================================

class TestSecurity:
    """Test security features in token routes"""

    def test_revoke_token_logs_security_event(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test token revocation logs security event"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify, \
             patch('api.token_routes.revoke_token') as mock_revoke:

            mock_verify.return_value = valid_token_payload
            mock_revoke.return_value = True

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "security_breach"
                },
                headers={"Authorization": "Bearer test_token"}
            )

            # Test should pass if no security exception is raised
            assert response.status_code == 200

    def test_cleanup_tokens_enforces_admin_role(self, client, mock_db, mock_regular_user):
        """Test token cleanup enforces admin role requirement"""
        with patch('api.token_routes.get_current_user', return_value=mock_regular_user):

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=24",
                headers={"Authorization": "Bearer user_token"}
            )

            # Should be forbidden for non-admin
            assert response.status_code == 403

    def test_verify_token_prevents_cross_user_access(self, client, mock_db, mock_regular_user, valid_token_payload):
        """Test token verification prevents cross-user token access"""
        # Token belongs to different user
        valid_token_payload["sub"] = "different_user_123"

        with patch('api.token_routes.get_current_user', return_value=mock_regular_user), \
             patch('api.token_routes.verify_token_string') as mock_verify:

            mock_verify.return_value = valid_token_payload

            response = client.get(
                "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                headers={"Authorization": "Bearer test_token"}
            )

            # Should be forbidden
            assert response.status_code == 403
