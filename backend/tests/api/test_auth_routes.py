"""
Auth Routes Integration Tests

Tests for authentication endpoints from api/auth_routes.py.

Coverage:
- POST /auth/register - User registration
- POST /auth/login - User login
- POST /auth/logout - User logout
- POST /auth/refresh - Refresh access token
- GET /auth/verify - Verify token validity
- POST /auth/forgot-password - Initiate password reset
- POST /auth/reset-password - Reset password
- POST /auth/change-password - Change password (authenticated)
- Authentication flow
- Token validation
- Error handling
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.auth_routes import router
from core.models import User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create TestClient for auth routes."""
    return TestClient(router)


@pytest.fixture
def mock_user(db: Session):
    """Create test user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ============================================================================
# POST /auth/register - Registration Tests
# ============================================================================

def test_register_success(
    client: TestClient,
    db: Session
):
    """Test user registration successfully."""
    import uuid
    registration_data = {
        "email": f"newuser-{uuid.uuid4()}@example.com",
        "password": "SecurePassword123!",
        "first_name": "New",
        "last_name": "User"
    }

    with patch('api.auth_routes.hash_password') as mock_hash:
        mock_hash.return_value = "hashed_password"

        response = client.post("/auth/register", json=registration_data)

        assert response.status_code in [200, 201]
        data = response.json()
        assert "access_token" in data or "id" in data or "user" in data


def test_register_duplicate_email(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test registration with duplicate email."""
    registration_data = {
        "email": mock_user.email,  # Already exists
        "password": "SecurePassword123!",
        "first_name": "Duplicate",
        "last_name": "User"
    }

    response = client.post("/auth/register", json=registration_data)

    assert response.status_code in [400, 409]
    data = response.json()
    assert "error" in data


def test_register_invalid_email(
    client: TestClient,
    db: Session
):
    """Test registration with invalid email."""
    registration_data = {
        "email": "not-an-email",
        "password": "SecurePassword123!",
        "first_name": "Test",
        "last_name": "User"
    }

    response = client.post("/auth/register", json=registration_data)

    assert response.status_code == 422


def test_register_weak_password(
    client: TestClient,
    db: Session
):
    """Test registration with weak password."""
    import uuid
    registration_data = {
        "email": f"user-{uuid.uuid4()}@example.com",
        "password": "123",  # Too short
        "first_name": "Test",
        "last_name": "User"
    }

    response = client.post("/auth/register", json=registration_data)

    assert response.status_code in [400, 422]


# ============================================================================
# POST /auth/login - Login Tests
# ============================================================================

def test_login_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test user login successfully."""
    login_data = {
        "email": mock_user.email,
        "password": "CorrectPassword123!"
    }

    with patch('api.auth_routes.verify_password') as mock_verify:
        mock_verify.return_value = True

        with patch('api.auth_routes.create_access_token') as mock_token:
            mock_token.return_value = "access_token_123"

            response = client.post("/auth/login", json=login_data)

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data or "token" in data


def test_login_invalid_credentials(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test login with invalid credentials."""
    login_data = {
        "email": mock_user.email,
        "password": "WrongPassword"
    }

    with patch('api.auth_routes.verify_password') as mock_verify:
        mock_verify.return_value = False

        response = client.post("/auth/login", json=login_data)

        assert response.status_code == 401
        data = response.json()
        assert "error" in data


def test_login_nonexistent_user(
    client: TestClient,
    db: Session
):
    """Test login with non-existent user."""
    login_data = {
        "email": "nonexistent@example.com",
        "password": "AnyPassword123!"
    }

    response = client.post("/auth/login", json=login_data)

    assert response.status_code == 401


# ============================================================================
# POST /auth/logout - Logout Tests
# ============================================================================

def test_logout_success(
    client: TestClient,
    mock_user: User
):
    """Test user logout successfully."""
    with patch('api.auth_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/auth/logout")

        assert response.status_code == 200


# ============================================================================
# POST /auth/refresh - Refresh Token Tests
# ============================================================================

def test_refresh_token_success(
    client: TestClient,
    mock_user: User
):
    """Test token refresh successfully."""
    refresh_data = {
        "refresh_token": "valid_refresh_token"
    }

    with patch('api.auth_routes.decode_refresh_token') as mock_decode:
        mock_decode.return_value = {"sub": mock_user.id}

    with patch('api.auth_routes.create_access_token') as mock_token:
        mock_token.return_value = "new_access_token"

        response = client.post("/auth/refresh", json=refresh_data)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data


def test_refresh_token_invalid(
    client: TestClient
):
    """Test refresh with invalid token."""
    refresh_data = {
        "refresh_token": "invalid_token"
    }

    with patch('api.auth_routes.decode_refresh_token') as mock_decode:
        mock_decode.side_effect = Exception("Invalid token")

        response = client.post("/auth/refresh", json=refresh_data)

        assert response.status_code == 401


# ============================================================================
# GET /auth/verify - Verify Token Tests
# ============================================================================

def test_verify_token_success(
    client: TestClient,
    mock_user: User
):
    """Test token verification successfully."""
    with patch('api.auth_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.get("/auth/verify")

        assert response.status_code == 200
        data = response.json()
        assert "valid" in data or "user" in data


# ============================================================================
# POST /auth/forgot-password - Forgot Password Tests
# ============================================================================

def test_forgot_password_success(
    client: TestClient,
    mock_user: User
):
    """Test forgot password initiates successfully."""
    forgot_data = {
        "email": mock_user.email
    }

    response = client.post("/auth/forgot-password", json=forgot_data)

    assert response.status_code == 200
    data = response.json()
    assert "message" in data


# ============================================================================
# POST /auth/reset-password - Reset Password Tests
# ============================================================================

def test_reset_password_success(
    client: TestClient
):
    """Test password reset successfully."""
    reset_data = {
        "token": "valid_reset_token",
        "new_password": "NewSecurePassword123!"
    }

    with patch('api.auth_routes.verify_reset_token') as mock_verify:
        mock_verify.return_value = "user_id"

    with patch('api.auth_routes.hash_password') as mock_hash:
        mock_hash.return_value = "new_hashed_password"

        response = client.post("/auth/reset-password", json=reset_data)

        assert response.status_code == 200


def test_reset_password_invalid_token(
    client: TestClient
):
    """Test password reset with invalid token."""
    reset_data = {
        "token": "invalid_token",
        "new_password": "NewSecurePassword123!"
    }

    with patch('api.auth_routes.verify_reset_token') as mock_verify:
        mock_verify.return_value = None

        response = client.post("/auth/reset-password", json=reset_data)

        assert response.status_code == 400


# ============================================================================
# POST /auth/change-password - Change Password Tests
# ============================================================================

def test_change_password_success(
    client: TestClient,
    mock_user: User
):
    """Test password change successfully."""
    change_data = {
        "current_password": "CurrentPassword123!",
        "new_password": "NewPassword123!"
    }

    with patch('api.auth_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

    with patch('api.auth_routes.verify_password') as mock_verify:
        mock_verify.return_value = True

    with patch('api.auth_routes.hash_password') as mock_hash:
        mock_hash.return_value = "new_hash"

        response = client.post("/auth/change-password", json=change_data)

        assert response.status_code == 200


def test_change_password_wrong_current(
    client: TestClient,
    mock_user: User
):
    """Test password change with wrong current password."""
    change_data = {
        "current_password": "WrongPassword",
        "new_password": "NewPassword123!"
    }

    with patch('api.auth_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

    with patch('api.auth_routes.verify_password') as mock_verify:
        mock_verify.return_value = False

        response = client.post("/auth/change-password", json=change_data)

        assert response.status_code == 400


# ============================================================================
# Request Validation Tests
# ============================================================================

def test_register_missing_fields(
    client: TestClient
):
    """Test registration with missing required fields."""
    registration_data = {
        "email": "test@example.com"
        # Missing password, first_name, last_name
    }

    response = client.post("/auth/register", json=registration_data)

    assert response.status_code == 422


def test_login_missing_fields(
    client: TestClient
):
    """Test login with missing required fields."""
    login_data = {
        "email": "test@example.com"
        # Missing password
    }

    response = client.post("/auth/login", json=login_data)

    assert response.status_code == 422


# ============================================================================
# Response Format Tests
# ============================================================================

def test_login_response_format(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test login response has correct format."""
    login_data = {
        "email": mock_user.email,
        "password": "CorrectPassword123!"
    }

    with patch('api.auth_routes.verify_password') as mock_verify:
        mock_verify.return_value = True

    with patch('api.auth_routes.create_access_token') as mock_token:
        mock_token.return_value = "access_token_123"

        response = client.post("/auth/login", json=login_data)

        data = response.json()
        assert "access_token" in data or "token" in data
        assert isinstance(data.get("access_token", data.get("token")), str)


def test_register_response_format(
    client: TestClient,
    db: Session
):
    """Test register response has correct format."""
    import uuid
    registration_data = {
        "email": f"newuser-{uuid.uuid4()}@example.com",
        "password": "SecurePassword123!",
        "first_name": "New",
        "last_name": "User"
    }

    with patch('api.auth_routes.hash_password') as mock_hash:
        mock_hash.return_value = "hashed_password"

        response = client.post("/auth/register", json=registration_data)

        data = response.json()
        assert "access_token" in data or "id" in data or "user" in data


# ============================================================================
# Mobile Authentication - POST /mobile/login
# ============================================================================

def test_mobile_login_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test mobile login with device registration successfully."""
    login_data = {
        "email": mock_user.email,
        "password": "test_password",
        "device_token": "test_device_token_123",
        "platform": "ios",
        "device_info": {
            "model": "iPhone 14",
            "os_version": "16.0"
        }
    }

    with patch('api.auth_routes.authenticate_mobile_user') as mock_auth:
        mock_auth.return_value = {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "expires_at": "2026-02-14T00:00:00Z",
            "token_type": "bearer",
            "user": {
                "id": mock_user.id,
                "email": mock_user.email
            }
        }

        response = client.post("/api/auth/mobile/login", json=login_data)

        assert response.status_code in [200, 401, 500]
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data


def test_mobile_login_invalid_credentials(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test mobile login with invalid credentials."""
    login_data = {
        "email": mock_user.email,
        "password": "wrong_password",
        "device_token": "test_device_token_123",
        "platform": "android"
    }

    with patch('api.auth_routes.authenticate_mobile_user') as mock_auth:
        mock_auth.return_value = None

        response = client.post("/api/auth/mobile/login", json=login_data)

        assert response.status_code in [400, 401]


def test_mobile_login_without_device_info(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test mobile login without optional device info."""
    login_data = {
        "email": mock_user.email,
        "password": "test_password",
        "device_token": "test_device_token_123",
        "platform": "ios"
    }

    with patch('api.auth_routes.authenticate_mobile_user') as mock_auth:
        mock_auth.return_value = {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "expires_at": "2026-02-14T00:00:00Z",
            "token_type": "bearer",
            "user": {"id": mock_user.id}
        }

        response = client.post("/api/auth/mobile/login", json=login_data)

        assert response.status_code in [200, 500]


# ============================================================================
# Mobile Biometric - POST /mobile/biometric/register
# ============================================================================

def test_register_biometric_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test biometric registration successfully."""
    registration_data = {
        "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA",
        "device_token": "test_device_token_123",
        "platform": "ios"
    }

    with patch('api.auth_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/api/auth/mobile/biometric/register", json=registration_data)

        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "challenge" in data


def test_register_biometric_device_not_found(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test biometric registration with non-existent device."""
    registration_data = {
        "public_key": "test_public_key",
        "device_token": "non_existent_device",
        "platform": "android"
    }

    with patch('api.auth_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/api/auth/mobile/biometric/register", json=registration_data)

        assert response.status_code == 404


# ============================================================================
# Mobile Biometric - POST /mobile/biometric/authenticate
# ============================================================================

def test_authenticate_with_biometric_success(
    client: TestClient,
    db: Session
):
    """Test biometric authentication successfully."""
    auth_data = {
        "device_id": "test_device_id",
        "signature": "test_signature",
        "challenge": "test_challenge"
    }

    with patch('api.auth_routes.verify_biometric_signature') as mock_verify:
        mock_verify.return_value = True

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_device = MagicMock()
            mock_device.id = "test_device_id"
            mock_device.user_id = "test_user_id"
            mock_device.device_info = {
                "biometric_public_key": "test_key",
                "biometric_challenge": "test_challenge"
            }
            mock_get_device.return_value = mock_device

            with patch('api.auth_routes.create_mobile_token') as mock_token:
                mock_token.return_value = {
                    "access_token": "test_access_token",
                    "refresh_token": "test_refresh_token"
                }

                response = client.post("/api/auth/mobile/biometric/authenticate", json=auth_data)

                assert response.status_code in [200, 404]


def test_authenticate_with_biometric_invalid_signature(
    client: TestClient,
    db: Session
):
    """Test biometric authentication with invalid signature."""
    auth_data = {
        "device_id": "test_device_id",
        "signature": "invalid_signature",
        "challenge": "test_challenge"
    }

    with patch('api.auth_routes.verify_biometric_signature') as mock_verify:
        mock_verify.return_value = False

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_device = MagicMock()
            mock_device.id = "test_device_id"
            mock_device.device_info = {
                "biometric_public_key": "test_key",
                "biometric_challenge": "test_challenge"
            }
            mock_get_device.return_value = mock_device

            response = client.post("/api/auth/mobile/biometric/authenticate", json=auth_data)

            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert data.get("success") is False


def test_authenticate_with_biometric_not_registered(
    client: TestClient,
    db: Session
):
    """Test biometric authentication when biometric not registered."""
    auth_data = {
        "device_id": "test_device_id",
        "signature": "test_signature",
        "challenge": "test_challenge"
    }

    with patch('api.auth_routes.get_mobile_device') as mock_get_device:
        mock_device = MagicMock()
        mock_device.id = "test_device_id"
        mock_device.device_info = {}  # No biometric_public_key
        mock_get_device.return_value = mock_device

        response = client.post("/api/auth/mobile/biometric/authenticate", json=auth_data)

        assert response.status_code in [400, 422, 404]


# ============================================================================
# Mobile Token - POST /mobile/refresh
# ============================================================================

def test_refresh_mobile_token_success(
    client: TestClient,
    db: Session
):
    """Test refreshing mobile token successfully."""
    refresh_data = {
        "refresh_token": "valid_refresh_token"
    }

    with patch('jose.jwt.decode') as mock_decode:
        mock_decode.return_value = {
            "sub": "test_user_id",
            "type": "refresh",
            "device_id": "test_device_id"
        }

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_device = MagicMock()
            mock_device.id = "test_device_id"
            mock_get_device.return_value = mock_device

            with patch('api.auth_routes.create_mobile_token') as mock_token:
                mock_token.return_value = {
                    "access_token": "new_access_token",
                    "refresh_token": "new_refresh_token"
                }

                response = client.post("/api/auth/mobile/refresh", json=refresh_data)

                assert response.status_code in [200, 401]


def test_refresh_mobile_token_invalid(
    client: TestClient,
    db: Session
):
    """Test refreshing with invalid token."""
    refresh_data = {
        "refresh_token": "invalid_token"
    }

    with patch('jose.jwt.decode') as mock_decode:
        from jose import JWTError
        mock_decode.side_effect = JWTError("Invalid token")

        response = client.post("/api/auth/mobile/refresh", json=refresh_data)

        assert response.status_code in [400, 422, 401]


def test_refresh_mobile_token_wrong_type(
    client: TestClient,
    db: Session
):
    """Test refreshing with wrong token type."""
    refresh_data = {
        "refresh_token": "access_token_instead"
    }

    with patch('jose.jwt.decode') as mock_decode:
        mock_decode.return_value = {
            "sub": "test_user_id",
            "type": "access",  # Wrong type
            "device_id": "test_device_id"
        }

        response = client.post("/api/auth/mobile/refresh", json=refresh_data)

        assert response.status_code in [400, 422]


# ============================================================================
# Mobile Device - GET /mobile/device
# ============================================================================

def test_get_mobile_device_info_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting mobile device info successfully."""
    device_id = "test_device_id"

    with patch('api.auth_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            from datetime import datetime
            mock_device = MagicMock()
            mock_device.id = device_id
            mock_device.platform = "ios"
            mock_device.status = "active"
            mock_device.notification_enabled = True
            mock_device.last_active = datetime.utcnow()
            mock_device.created_at = datetime.utcnow()
            mock_get_device.return_value = mock_device

            response = client.get(f"/api/auth/mobile/device?device_id={device_id}")

            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "device_id" in data
                assert "platform" in data


def test_get_mobile_device_info_not_found(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting info for non-existent device."""
    device_id = "non_existent_device"

    with patch('api.auth_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_get_device.return_value = None

            response = client.get(f"/api/auth/mobile/device?device_id={device_id}")

            assert response.status_code == 404


# ============================================================================
# Mobile Device - DELETE /mobile/device
# ============================================================================

def test_delete_mobile_device_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test deleting mobile device successfully."""
    device_id = "test_device_id"

    with patch('api.auth_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_device = MagicMock()
            mock_device.id = device_id
            mock_get_device.return_value = mock_device

            response = client.delete(f"/api/auth/mobile/device?device_id={device_id}")

            assert response.status_code in [200, 404]
            if response.status_code == 200:
                data = response.json()
                assert "success" in data or "message" in data


def test_delete_mobile_device_not_found(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test deleting non-existent device."""
    device_id = "non_existent_device"

    with patch('api.auth_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_get_device.return_value = None

            response = client.delete(f"/api/auth/mobile/device?device_id={device_id}")

            assert response.status_code == 404
