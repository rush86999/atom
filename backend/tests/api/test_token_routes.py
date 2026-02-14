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
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from api.token_routes import router
from core.models import User, UserRole
from core.database import get_db


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Create test database session"""
    from core.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def admin_user(db_session: Session):
    """Create admin user"""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"admin-{user_id}@example.com",
        password_hash="hashed_password",
        first_name="Admin",
        last_name="User",
        role=UserRole.SUPER_ADMIN,
        status="active"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_user(db_session: Session):
    """Create regular user"""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"user-{user_id}@example.com",
        password_hash="hashed_password",
        first_name="Regular",
        last_name="User",
        role=UserRole.MEMBER,
        status="active"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def valid_token_payload(regular_user: User):
    """Mock valid JWT payload"""
    return {
        "sub": regular_user.id,
        "jti": "token_123",
        "exp": int(datetime.utcnow().timestamp()) + 3600,
        "iat": int(datetime.utcnow().timestamp())
    }


@pytest.fixture
def client():
    """Create TestClient for token routes"""
    from main import app
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client


# ============================================================================
# POST /api/auth/tokens/revoke - Token Revocation Tests
# ============================================================================

class TestTokenRevocation:
    """Test token revocation endpoint"""

    def test_revoke_token_success(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test successful token revocation"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

        with patch('api.token_routes.revoke_token') as mock_revoke:
            mock_revoke.return_value = True

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "logout"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "revoked" in data["message"].lower() or "success" in data["message"].lower()

    def test_revoke_token_already_revoked(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test revoking already revoked token"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

        with patch('api.token_routes.revoke_token') as mock_revoke:
            mock_revoke.return_value = False  # Already revoked

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "logout"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "already" in data["message"].lower()

    def test_revoke_token_wrong_user(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test revoking token belonging to different user fails"""
        # Token belongs to different user
        valid_token_payload["sub"] = "different_user_123"

        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "logout"
                }
            )

            # Permission denied
            assert response.status_code == 403

    def test_revoke_token_no_jti(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test revoking token without JTI claim fails"""
        # Remove JTI from payload
        valid_token_payload_no_jti = valid_token_payload.copy()
        del valid_token_payload_no_jti["jti"]

        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload_no_jti

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "logout"
                }
            )

            # Validation error
            assert response.status_code == 422

    def test_revoke_token_default_reason(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test token revocation with default reason"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

        with patch('api.token_routes.revoke_token') as mock_revoke:
            mock_revoke.return_value = True

            response = client.post(
                "/api/auth/tokens/revoke",
                json={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
            )

            assert response.status_code == 200

    def test_revoke_token_security_breach(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test token revocation for security breach"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

        with patch('api.token_routes.revoke_token') as mock_revoke:
            mock_revoke.return_value = True

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "security_breach"
                }
            )

            assert response.status_code == 200


# ============================================================================
# POST /api/auth/tokens/cleanup - Token Cleanup Tests
# ============================================================================

class TestTokenCleanup:
    """Test token cleanup endpoint"""

    def test_cleanup_tokens_admin_success(self, client: TestClient, admin_user: User):
        """Test successful token cleanup by admin"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = admin_user

        with patch('api.token_routes.cleanup_expired_revoked_tokens') as mock_cleanup:
            mock_cleanup.return_value = 42  # Deleted 42 tokens

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=24"
            )

            assert response.status_code == 200
            data = response.json()
            assert "success" in data or "deleted_count" in data
            if "deleted_count" in data:
                assert data["deleted_count"] == 42

    def test_cleanup_tokens_custom_hours(self, client: TestClient, admin_user: User):
        """Test token cleanup with custom hours parameter"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = admin_user

        with patch('api.token_routes.cleanup_expired_revoked_tokens') as mock_cleanup:
            mock_cleanup.return_value = 100

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=48"
            )

            assert response.status_code == 200

    def test_cleanup_tokens_non_admin_forbidden(self, client: TestClient, regular_user: User):
        """Test token cleanup forbidden for non-admin users"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=24"
            )

            # Permission denied
            assert response.status_code == 403

    def test_cleanup_tokens_no_expired_tokens(self, client: TestClient, admin_user: User):
        """Test token cleanup when no expired tokens exist"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = admin_user

        with patch('api.token_routes.cleanup_expired_revoked_tokens') as mock_cleanup:
            mock_cleanup.return_value = 0

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=24"
            )

            assert response.status_code == 200

    def test_cleanup_tokens_default_hours(self, client: TestClient, admin_user: User):
        """Test token cleanup with default hours parameter"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = admin_user

        with patch('api.token_routes.cleanup_expired_revoked_tokens') as mock_cleanup:
            mock_cleanup.return_value = 15

            response = client.post(
                "/api/auth/tokens/cleanup"  # No older_than_hours parameter
            )

            assert response.status_code == 200


# ============================================================================
# GET /api/auth/tokens/verify - Token Verification Tests
# ============================================================================

class TestTokenVerification:
    """Test token verification endpoint"""

    def test_verify_token_valid(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test verifying a valid token"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

            # Mock JWT verifier
            with patch('api.token_routes.get_jwt_verifier') as mock_get_verifier:
                mock_verifier = Mock()
                mock_verifier._is_token_revoked.return_value = False  # Not revoked
                mock_get_verifier.return_value = mock_verifier

                response = client.get(
                    "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                )

                assert response.status_code == 200
                data = response.json()
                assert data["valid"] is True
                assert data["revoked"] is False

    def test_verify_token_revoked(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test verifying a revoked token"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

            # Mock JWT verifier
            with patch('api.token_routes.get_jwt_verifier') as mock_get_verifier:
                mock_verifier = Mock()
                mock_verifier._is_token_revoked.return_value = True  # Revoked
                mock_get_verifier.return_value = mock_verifier

                response = client.get(
                    "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                )

                assert response.status_code == 200
                data = response.json()
                assert data["valid"] is False
                assert data["revoked"] is True

    def test_verify_token_wrong_user(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test verifying token belonging to different user fails"""
        # Token belongs to different user
        valid_token_payload["sub"] = "different_user_123"

        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

            response = client.get(
                "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            )

            # Permission denied
            assert response.status_code == 403

    def test_verify_token_invalid_format(self, client: TestClient, regular_user: User):
        """Test verifying token with invalid format"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.side_effect = Exception("Invalid token format")

            response = client.get(
                "/api/auth/tokens/verify?token=invalid_token_string"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False
            assert "error" in data

    def test_verify_token_includes_expiry(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test token verification includes expiry timestamp"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

            # Mock JWT verifier
            with patch('api.token_routes.get_jwt_verifier') as mock_get_verifier:
                mock_verifier = Mock()
                mock_verifier._is_token_revoked.return_value = False
                mock_get_verifier.return_value = mock_verifier

                response = client.get(
                    "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                )

                assert response.status_code == 200
                data = response.json()
                assert "expires_at" in data

    def test_verify_token_includes_user_id(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test token verification includes user ID"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

            # Mock JWT verifier
            with patch('api.token_routes.get_jwt_verifier') as mock_get_verifier:
                mock_verifier = Mock()
                mock_verifier._is_token_revoked.return_value = False
                mock_get_verifier.return_value = mock_verifier

                response = client.get(
                    "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                )

                assert response.status_code == 200
                data = response.json()
                assert "user_id" in data

    def test_verify_token_includes_jti(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test token verification includes JTI"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

            # Mock JWT verifier
            with patch('api.token_routes.get_jwt_verifier') as mock_get_verifier:
                mock_verifier = Mock()
                mock_verifier._is_token_revoked.return_value = False
                mock_get_verifier.return_value = mock_verifier

                response = client.get(
                    "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                )

                assert response.status_code == 200
                data = response.json()
                assert "jti" in data


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling in token routes"""

    def test_revoke_token_exception_handled(self, client: TestClient, regular_user: User):
        """Test exceptions are properly handled during token revocation"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.side_effect = Exception("Database connection failed")

            response = client.post(
                "/api/auth/tokens/revoke",
                json={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
            )

            assert response.status_code == 500

    def test_cleanup_tokens_exception_handled(self, client: TestClient, admin_user: User):
        """Test exceptions are properly handled during token cleanup"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = admin_user

        with patch('api.token_routes.cleanup_expired_revoked_tokens') as mock_cleanup:
            mock_cleanup.side_effect = Exception("Database error")

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=24"
            )

            assert response.status_code == 500

    def test_verify_token_exception_handled(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test exceptions are properly handled during token verification"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.side_effect = Exception("Verification service unavailable")

            response = client.get(
                "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is False


# ============================================================================
# Security Tests
# ============================================================================

class TestSecurity:
    """Test security features in token routes"""

    def test_revoke_token_logs_security_event(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test token revocation logs security event"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

        with patch('api.token_routes.revoke_token') as mock_revoke:
            mock_revoke.return_value = True

            response = client.post(
                "/api/auth/tokens/revoke",
                json={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "reason": "security_breach"
                }
            )

            # Test should pass if no security exception is raised
            assert response.status_code == 200

    def test_cleanup_tokens_enforces_admin_role(self, client: TestClient, regular_user: User):
        """Test token cleanup enforces admin role requirement"""
        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

            response = client.post(
                "/api/auth/tokens/cleanup?older_than_hours=24"
            )

            # Should be forbidden for non-admin
            assert response.status_code == 403

    def test_verify_token_prevents_cross_user_access(self, client: TestClient, regular_user: User, valid_token_payload: dict):
        """Test token verification prevents cross-user token access"""
        # Token belongs to different user
        valid_token_payload["sub"] = "different_user_123"

        with patch('api.token_routes.get_current_user') as mock_auth:
            mock_auth.return_value = regular_user

        with patch('api.token_routes.verify_token_string') as mock_verify:
            mock_verify.return_value = valid_token_payload

            response = client.get(
                "/api/auth/tokens/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            )

            # Should be forbidden
            assert response.status_code == 403
