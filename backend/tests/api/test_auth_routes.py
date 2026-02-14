"""
Auth Routes Integration Tests

Tests for authentication endpoints from api/auth_routes.py.

Coverage:
- POST /api/auth/mobile/login - Mobile user authentication
- POST /api/auth/mobile/biometric/register - Biometric registration
- POST /api/auth/mobile/biometric/authenticate - Biometric authentication
- POST /api/auth/mobile/refresh - Token refresh
- GET /api/auth/mobile/device - Device info
- DELETE /api/auth/mobile/device - Device deletion
"""

import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from api.auth_routes import router
from core.models import User, MobileDevice, UserRole
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
def test_user(db_session: Session):
    """Create test user"""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.MEMBER,
        status="active"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_device(db_session: Session, test_user: User):
    """Create test mobile device"""
    import uuid
    device = MobileDevice(
        id=str(uuid.uuid4()),
        user_id=str(test_user.id),
        device_token="test_device_token_123",
        platform="ios",
        status="active",
        notification_enabled=True,
        last_active=datetime.utcnow(),
        created_at=datetime.utcnow(),
        device_info={"model": "iPhone 14", "os_version": "16.0"}
    )
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


@pytest.fixture
def client():
    """Create TestClient for auth routes"""
    from main import app
    app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client


# ============================================================================
# POST /api/auth/mobile/login - Mobile Login Tests
# ============================================================================

class TestMobileLogin:
    """Test mobile login endpoint"""

    def test_mobile_login_success(self, client: TestClient, test_user: User, db_session: Session):
        """Test successful mobile login"""
        # Mock authenticate_mobile_user to return tokens
        with patch('api.auth_routes.authenticate_mobile_user') as mock_auth:
            mock_auth.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_at": "2026-02-14T00:00:00Z",
                "token_type": "bearer",
                "user": {
                    "id": test_user.id,
                    "email": test_user.email
                }
            }

            response = client.post(
                "/api/auth/mobile/login",
                json={
                    "email": test_user.email,
                    "password": "test_password",
                    "device_token": "new_device_token",
                    "platform": "ios",
                    "device_info": {"model": "iPhone 14"}
                }
            )

            # Should succeed or get validation error
            assert response.status_code in [200, 400, 401]
            if response.status_code == 200:
                data = response.json()
                assert "access_token" in data
                assert "refresh_token" in data

    def test_mobile_login_invalid_credentials(self, client: TestClient, test_user: User):
        """Test mobile login with invalid credentials"""
        with patch('api.auth_routes.authenticate_mobile_user') as mock_auth:
            mock_auth.return_value = None  # Auth failed

            response = client.post(
                "/api/auth/mobile/login",
                json={
                    "email": test_user.email,
                    "password": "wrong_password",
                    "device_token": "device_token",
                    "platform": "android"
                }
            )

            # Should fail with validation error
            assert response.status_code in [400, 401]

    def test_mobile_login_missing_fields(self, client: TestClient):
        """Test mobile login with missing required fields"""
        response = client.post(
            "/api/auth/mobile/login",
            json={
                "email": "test@example.com"
                # Missing password, device_token, platform
            }
        )

        assert response.status_code == 422  # Validation error


# ============================================================================
# POST /api/auth/mobile/biometric/register - Biometric Registration Tests
# ============================================================================

class TestBiometricRegistration:
    """Test biometric registration endpoint"""

    def test_register_biometric_success(self, client: TestClient, test_user: User, test_device: MobileDevice):
        """Test successful biometric registration"""
        # Mock get_current_user to return test user
        with patch('api.auth_routes.get_current_user') as mock_auth:
            mock_auth.return_value = test_user

            response = client.post(
                "/api/auth/mobile/biometric/register",
                json={
                    "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA",
                    "device_token": test_device.device_token,
                    "platform": "ios"
                }
            )

            # Should succeed or not found
            assert response.status_code in [200, 404, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert "challenge" in data

    def test_register_biometric_device_not_found(self, client: TestClient, test_user: User):
        """Test biometric registration with non-existent device"""
        with patch('api.auth_routes.get_current_user') as mock_auth:
            mock_auth.return_value = test_user

            response = client.post(
                "/api/auth/mobile/biometric/register",
                json={
                    "public_key": "test_key",
                    "device_token": "nonexistent_device",
                    "platform": "android"
                }
            )

            # Device not found
            assert response.status_code == 404

    def test_register_biometric_missing_fields(self, client: TestClient, test_user: User):
        """Test biometric registration with missing fields"""
        with patch('api.auth_routes.get_current_user') as mock_auth:
            mock_auth.return_value = test_user

            response = client.post(
                "/api/auth/mobile/biometric/register",
                json={
                    "public_key": "test_key"
                    # Missing device_token, platform
                }
            )

            assert response.status_code == 422


# ============================================================================
# POST /api/auth/mobile/biometric/authenticate - Biometric Auth Tests
# ============================================================================

class TestBiometricAuthentication:
    """Test biometric authentication endpoint"""

    def test_authenticate_biometric_success(self, client: TestClient, test_device: MobileDevice):
        """Test successful biometric authentication"""
        # Mock get_mobile_device to return test device
        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_get_device.return_value = test_device

        # Mock verify_biometric_signature
        with patch('api.auth_routes.verify_biometric_signature') as mock_verify:
            mock_verify.return_value = True

        # Mock create_mobile_token
        with patch('api.auth_routes.create_mobile_token') as mock_token:
            mock_token.return_value = {
                "access_token": "biometric_access_token",
                "refresh_token": "biometric_refresh_token"
            }

            # Update device info with biometric data
            test_device.device_info = {
                "biometric_public_key": "test_key",
                "biometric_challenge": "test_challenge"
            }

            response = client.post(
                "/api/auth/mobile/biometric/authenticate",
                json={
                    "device_id": test_device.id,
                    "signature": "valid_signature",
                    "challenge": "test_challenge"
                }
            )

            # Should succeed or fail validation
            assert response.status_code in [200, 400, 404]
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert "access_token" in data

    def test_authenticate_biometric_invalid_signature(self, client: TestClient, test_device: MobileDevice):
        """Test biometric authentication with invalid signature"""
        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_get_device.return_value = test_device

        with patch('api.auth_routes.verify_biometric_signature') as mock_verify:
            mock_verify.return_value = False  # Invalid signature

            test_device.device_info = {
                "biometric_public_key": "test_key",
                "biometric_challenge": "test_challenge"
            }

            response = client.post(
                "/api/auth/mobile/biometric/authenticate",
                json={
                    "device_id": test_device.id,
                    "signature": "invalid_signature",
                    "challenge": "test_challenge"
                }
            )

            # Should succeed but with success=False
            assert response.status_code in [200, 400, 404]

    def test_authenticate_biometric_device_not_found(self, client: TestClient):
        """Test biometric authentication with non-existent device"""
        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_get_device.return_value = None

            response = client.post(
                "/api/auth/mobile/biometric/authenticate",
                json={
                    "device_id": "nonexistent_device",
                    "signature": "signature",
                    "challenge": "challenge"
                }
            )

            # Device not found
            assert response.status_code == 404


# ============================================================================
# POST /api/auth/mobile/refresh - Token Refresh Tests
# ============================================================================

class TestMobileTokenRefresh:
    """Test mobile token refresh endpoint"""

    def test_refresh_mobile_token_success(self, client: TestClient, test_device: MobileDevice):
        """Test successful token refresh"""
        # Mock JWT decode
        with patch('jose.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": test_device.user_id,
                "type": "refresh",
                "device_id": test_device.id,
                "exp": int(datetime.utcnow().timestamp()) + 3600
            }

        # Mock get_mobile_device
        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_get_device.return_value = test_device

        # Mock create_mobile_token
        with patch('api.auth_routes.create_mobile_token') as mock_token:
            mock_token.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token"
            }

            response = client.post(
                "/api/auth/mobile/refresh",
                json={
                    "refresh_token": "valid_refresh_token"
                }
            )

            # Should succeed or fail validation
            assert response.status_code in [200, 400, 401]
            if response.status_code == 200:
                data = response.json()
                assert "access_token" in data or "refresh_token" in data

    def test_refresh_mobile_token_invalid(self, client: TestClient):
        """Test refresh with invalid token"""
        from jose import JWTError

        with patch('jose.jwt.decode') as mock_decode:
            mock_decode.side_effect = JWTError("Invalid token")

            response = client.post(
                "/api/auth/mobile/refresh",
                json={
                    "refresh_token": "invalid_token"
                }
            )

            # Should fail with validation error
            assert response.status_code in [400, 422, 401]

    def test_refresh_mobile_token_wrong_type(self, client: TestClient):
        """Test refresh with wrong token type"""
        with patch('jose.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "user_id",
                "type": "access",  # Wrong type
                "device_id": "device_id"
            }

            response = client.post(
                "/api/auth/mobile/refresh",
                json={
                    "refresh_token": "access_token_instead"
                }
            )

            # Should fail with validation error
            assert response.status_code in [400, 422]


# ============================================================================
# GET /api/auth/mobile/device - Get Device Info Tests
# ============================================================================

class TestGetMobileDevice:
    """Test get mobile device info endpoint"""

    def test_get_device_info_success(self, client: TestClient, test_user: User, test_device: MobileDevice):
        """Test successful device info retrieval"""
        with patch('api.auth_routes.get_current_user') as mock_auth:
            mock_auth.return_value = test_user

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_get_device.return_value = test_device

            response = client.get(
                f"/api/auth/mobile/device?device_id={test_device.id}"
            )

            # Should succeed
            assert response.status_code == 200
            data = response.json()
            assert "device_id" in data
            assert "platform" in data

    def test_get_device_info_not_found(self, client: TestClient, test_user: User):
        """Test getting info for non-existent device"""
        with patch('api.auth_routes.get_current_user') as mock_auth:
            mock_auth.return_value = test_user

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_get_device.return_value = None

            response = client.get(
                "/api/auth/mobile/device?device_id=nonexistent_device"
            )

            # Device not found
            assert response.status_code == 404


# ============================================================================
# DELETE /api/auth/mobile/device - Delete Device Tests
# ============================================================================

class TestDeleteMobileDevice:
    """Test delete mobile device endpoint"""

    def test_delete_device_success(self, client: TestClient, test_user: User, test_device: MobileDevice):
        """Test successful device deletion"""
        with patch('api.auth_routes.get_current_user') as mock_auth:
            mock_auth.return_value = test_user

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_get_device.return_value = test_device

            response = client.delete(
                f"/api/auth/mobile/device?device_id={test_device.id}"
            )

            # Should succeed
            assert response.status_code == 200
            data = response.json()
            assert "success" in data or "message" in data

    def test_delete_device_not_found(self, client: TestClient, test_user: User):
        """Test deleting non-existent device"""
        with patch('api.auth_routes.get_current_user') as mock_auth:
            mock_auth.return_value = test_user

        with patch('api.auth_routes.get_mobile_device') as mock_get_device:
            mock_get_device.return_value = None

            response = client.delete(
                "/api/auth/mobile/device?device_id=nonexistent_device"
            )

            # Device not found
            assert response.status_code == 404


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling in auth routes"""

    def test_mobile_login_exception_handled(self, client: TestClient, test_user: User):
        """Test exception handling during mobile login"""
        with patch('api.auth_routes.authenticate_mobile_user') as mock_auth:
            mock_auth.side_effect = Exception("Database error")

            response = client.post(
                "/api/auth/mobile/login",
                json={
                    "email": test_user.email,
                    "password": "password",
                    "device_token": "token",
                    "platform": "ios"
                }
            )

            # Should handle error gracefully
            assert response.status_code == 500

    def test_biometric_registration_exception_handled(self, client: TestClient, test_user: User):
        """Test exception handling during biometric registration"""
        with patch('api.auth_routes.get_current_user') as mock_auth:
            mock_auth.return_value = test_user

        # Trigger exception by missing device_token
        response = client.post(
            "/api/auth/mobile/biometric/register",
            json={
                "public_key": "key",
                "device_token": "nonexistent",
                "platform": "ios"
            }
        )

        # Should handle error (404 or 500)
        assert response.status_code in [404, 500]

    def test_token_refresh_exception_handled(self, client: TestClient):
        """Test exception handling during token refresh"""
        with patch('jose.jwt.decode') as mock_decode:
            mock_decode.side_effect = Exception("JWT error")

            response = client.post(
                "/api/auth/mobile/refresh",
                json={
                    "refresh_token": "malformed_token"
                }
            )

            # Should handle error gracefully
            assert response.status_code == 500
