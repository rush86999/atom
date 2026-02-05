"""
Mobile Authentication Tests

Tests for mobile-specific authentication functionality:
- Mobile login with device registration
- Biometric authentication
- Mobile token refresh
- Device management
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from core.auth import (
    authenticate_mobile_user,
    create_mobile_token,
    get_mobile_device,
    verify_biometric_signature,
    verify_mobile_token,
)
from core.models import MobileDevice, User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_user(db_session: Session):
    """Create a test user."""
    user = User(
        email="mobile@test.com",
        first_name="Mobile",
        last_name="Test User",
        password_hash="$2b$12$test_hashed_password",  # Mock hashed password
        role="MEMBER"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_mobile_device(db_session: Session, test_user):
    """Create a test mobile device."""
    device = MobileDevice(
        user_id=str(test_user.id),
        device_token="test_device_token_123",
        platform="ios",
        status="active",
        device_info={"model": "iPhone 14", "os_version": "17.0"},
        notification_enabled=True
    )
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


# ============================================================================
# Mobile Login Tests
# ============================================================================

class TestMobileLogin:
    """Tests for mobile login functionality."""

    @pytest.mark.asyncio
    async def test_mobile_login_success(self, db_session: Session, test_user):
        """Test successful mobile login with device registration."""
        with patch('core.auth.verify_password', return_value=True):
            result = await authenticate_mobile_user(
                email=test_user.email,
                password="test_password",
                device_token="new_device_token",
                platform="ios",
                db=db_session
            )

            assert result is not None
            assert "access_token" in result
            assert "refresh_token" in result
            assert "user" in result
            assert result["user"]["email"] == test_user.email

            # Verify device was created
            device = db_session.query(MobileDevice).filter(
                MobileDevice.device_token == "new_device_token"
            ).first()
            assert device is not None
            assert device.platform == "ios"
            assert device.status == "active"

    @pytest.mark.asyncio
    async def test_mobile_login_invalid_credentials(self, db_session: Session):
        """Test mobile login with invalid credentials."""
        with patch('core.auth.verify_password', return_value=False):
            result = await authenticate_mobile_user(
                email="nonexistent@test.com",
                password="wrong_password",
                device_token="test_token",
                platform="android",
                db=db_session
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_mobile_login_existing_device(self, db_session: Session, test_user, test_mobile_device):
        """Test mobile login with existing device (should update)."""
        with patch('core.auth.verify_password', return_value=True):
            result = await authenticate_mobile_user(
                email=test_user.email,
                password="test_password",
                device_token=test_mobile_device.device_token,
                platform="android",  # Changed from ios
                db=db_session
            )

            assert result is not None

            # Verify device was updated
            db_session.refresh(test_mobile_device)
            assert test_mobile_device.platform == "android"


# ============================================================================
# Mobile Token Tests
# ============================================================================

class TestMobileTokens:
    """Tests for mobile token creation and validation."""

    def test_create_mobile_token(self, test_user):
        """Test mobile token creation."""
        tokens = create_mobile_token(test_user, "device_123")

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "expires_at" in tokens
        assert tokens["token_type"] == "bearer"

    def test_create_mobile_token_custom_expiry(self, test_user):
        """Test mobile token creation with custom expiry."""
        custom_expiry = timedelta(hours=1)
        tokens = create_mobile_token(test_user, "device_123", expires_delta=custom_expiry)

        assert "access_token" in tokens
        expires_at = datetime.fromisoformat(tokens["expires_at"])
        now = datetime.utcnow()

        # Should expire approximately 1 hour from now
        time_diff = (expires_at - now).total_seconds()
        assert 3500 < time_diff < 3700  # Allow some margin

    def test_verify_mobile_token_valid(self, db_session: Session, test_user):
        """Test verification of valid mobile token."""
        tokens = create_mobile_token(test_user, "device_123")

        user = verify_mobile_token(tokens["access_token"], db_session)

        assert user is not None
        assert user.id == test_user.id

    def test_verify_mobile_token_invalid(self, db_session: Session):
        """Test verification of invalid mobile token."""
        user = verify_mobile_token("invalid_token", db_session)

        assert user is None


# ============================================================================
# Device Management Tests
# ============================================================================

class TestDeviceManagement:
    """Tests for device management functionality."""

    def test_get_mobile_device_success(self, db_session: Session, test_mobile_device):
        """Test getting mobile device."""
        device = get_mobile_device(
            device_id=str(test_mobile_device.id),
            user_id=str(test_mobile_device.user_id),
            db=db_session
        )

        assert device is not None
        assert device.id == test_mobile_device.id

    def test_get_mobile_device_not_found(self, db_session: Session):
        """Test getting non-existent mobile device."""
        device = get_mobile_device(
            device_id="nonexistent_device_id",
            user_id="nonexistent_user_id",
            db=db_session
        )

        assert device is None

    def test_get_mobile_device_inactive(self, db_session: Session, test_mobile_device):
        """Test that inactive devices are not returned."""
        test_mobile_device.status = "inactive"
        db_session.commit()

        device = get_mobile_device(
            device_id=str(test_mobile_device.id),
            user_id=str(test_mobile_device.user_id),
            db=db_session
        )

        assert device is None


# ============================================================================
# Biometric Authentication Tests
# ============================================================================

class TestBiometricAuthentication:
    """Tests for biometric authentication functionality."""

    @pytest.mark.skip(reason="Requires cryptography library setup")
    def test_verify_biometric_signature_valid(self):
        """Test verification of valid biometric signature."""
        # This would require actual public/private key generation
        # and signing, which is complex to test
        pass

    def test_verify_biometric_signature_invalid(self):
        """Test verification of invalid biometric signature."""
        result = verify_biometric_signature(
            signature="invalid_signature",
            public_key="invalid_public_key",
            challenge="test_challenge"
        )

        assert result is False


# ============================================================================
# Integration Tests
# ============================================================================

class TestMobileAuthIntegration:
    """Integration tests for mobile authentication flow."""

    @pytest.mark.asyncio
    async def test_complete_mobile_auth_flow(self, db_session: Session, test_user):
        """Test complete mobile authentication flow."""
        with patch('core.auth.verify_password', return_value=True):
            # Step 1: Login
            login_result = await authenticate_mobile_user(
                email=test_user.email,
                password="test_password",
                device_token="test_flow_token",
                platform="ios",
                db=db_session
            )

            assert login_result is not None
            access_token = login_result["access_token"]

            # Step 2: Verify token
            verified_user = verify_mobile_token(access_token, db_session)
            assert verified_user is not None
            assert verified_user.id == test_user.id

            # Step 3: Get device
            device = db_session.query(MobileDevice).filter(
                MobileDevice.device_token == "test_flow_token"
            ).first()
            assert device is not None

            # Step 4: Clean up (unregister device)
            device.status = "inactive"
            db_session.commit()

            # Step 5: Verify device is now inactive
            device_check = get_mobile_device(
                device_id=str(device.id),
                user_id=str(test_user.id),
                db=db_session
            )
            assert device_check is None


# ============================================================================
# Performance Tests
# ============================================================================

class TestMobileAuthPerformance:
    """Performance tests for mobile authentication."""

    @pytest.mark.asyncio
    async def test_mobile_login_performance(self, db_session: Session, test_user):
        """Test mobile login performance."""
        import time

        with patch('core.auth.verify_password', return_value=True):
            start = time.time()
            result = await authenticate_mobile_user(
                email=test_user.email,
                password="test_password",
                device_token="perf_test_token",
                platform="ios",
                db=db_session
            )
            end = time.time()

            assert result is not None
            # Should complete in less than 1 second
            assert (end - start) < 1.0

    def test_token_verification_performance(self, db_session: Session, test_user):
        """Test token verification performance."""
        import time

        tokens = create_mobile_token(test_user, "device_123")

        start = time.time()
        user = verify_mobile_token(tokens["access_token"], db_session)
        end = time.time()

        assert user is not None
        # Should complete in less than 100ms
        assert (end - start) < 0.1
