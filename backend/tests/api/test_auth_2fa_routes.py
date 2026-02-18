"""
Auth 2FA Routes API Tests

Tests for two-factor authentication endpoints including:
- Getting 2FA status
- Setting up 2FA
- Enabling 2FA
- Disabling 2FA
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from main_api_app import app
from core.auth import get_current_user
from core.models import User


class TestAuth2FARoutes:
    """Test 2FA authentication API endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "user@example.com"
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.two_factor_backup_codes = None
        return user

    @pytest.fixture
    def client(self, mock_user):
        """Create test client with auth override."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()

    def test_get_2fa_status_disabled(self, client, mock_user):
        """Test getting 2FA status when disabled."""
        mock_user.two_factor_enabled = False

        response = client.get("/api/auth/2fa/status")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert data["enabled"] is False

    def test_get_2fa_status_enabled(self, client, mock_user):
        """Test getting 2FA status when enabled."""
        mock_user.two_factor_enabled = True

        response = client.get("/api/auth/2fa/status")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert data["enabled"] is True

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_setup_2fa_success(self, mock_get_db, mock_audit, mock_pyotp, client, mock_user):
        """Test successful 2FA setup."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        mock_pyotp.random_base32.return_value = "test-secret-123"
        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://totp/test"
        mock_pyotp.totp.TOTP.return_value = mock_totp

        response = client.post("/api/auth/2fa/setup")

        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        assert "otpauth_url" in data
        assert data["secret"] == "test-secret-123"

    def test_setup_2fa_already_enabled(self, client, mock_user):
        """Test setup when 2FA is already enabled."""
        mock_user.two_factor_enabled = True

        response = client.post("/api/auth/2fa/setup")

        assert response.status_code == 409  # Conflict

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_enable_2fa_success(self, mock_get_db, mock_audit, mock_pyotp, client, mock_user):
        """Test successfully enabling 2FA."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        mock_user.two_factor_enabled = False
        mock_user.two_factor_secret = "existing-secret"

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp

        mock_audit.log_event = Mock()

        response = client.post(
            "/api/auth/2fa/enable",
            json={"code": "123456"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "backup_codes" in data or "success" in data
        assert mock_user.two_factor_enabled is True

    def test_enable_2fa_already_enabled(self, client, mock_user):
        """Test enable when 2FA is already enabled."""
        mock_user.two_factor_enabled = True

        response = client.post(
            "/api/auth/2fa/enable",
            json={"code": "123456"}
        )

        assert response.status_code == 409  # Conflict

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.get_db')
    def test_enable_2fa_no_setup(self, mock_get_db, mock_pyotp, client, mock_user):
        """Test enable without prior setup."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        mock_user.two_factor_enabled = False
        mock_user.two_factor_secret = None

        response = client.post(
            "/api/auth/2fa/enable",
            json={"code": "123456"}
        )

        assert response.status_code in [400, 422]  # Validation error

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_enable_2fa_invalid_code(self, mock_get_db, mock_audit, mock_pyotp, client, mock_user):
        """Test enable with invalid verification code."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        mock_user.two_factor_enabled = False
        mock_user.two_factor_secret = "test-secret"

        mock_totp = Mock()
        mock_totp.verify.return_value = False
        mock_pyotp.TOTP.return_value = mock_totp

        response = client.post(
            "/api/auth/2fa/enable",
            json={"code": "000000"}
        )

        assert response.status_code in [400, 422]  # Validation error

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_disable_2fa_success(self, mock_get_db, mock_audit, mock_pyotp, client, mock_user):
        """Test successfully disabling 2FA."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        mock_user.two_factor_enabled = True
        mock_user.two_factor_secret = "test-secret"

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp

        mock_audit.log_event = Mock()

        response = client.post(
            "/api/auth/2fa/disable",
            json={"code": "123456"}
        )

        assert response.status_code == 200
        assert mock_user.two_factor_enabled is False
        assert mock_user.two_factor_secret is None

    def test_disable_2fa_not_enabled(self, client, mock_user):
        """Test disable when 2FA is not enabled."""
        mock_user.two_factor_enabled = False

        response = client.post(
            "/api/auth/2fa/disable",
            json={"code": "123456"}
        )

        assert response.status_code in [400, 422]  # Validation error

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_disable_2fa_invalid_code(self, mock_get_db, mock_audit, mock_pyotp, client, mock_user):
        """Test disable with invalid verification code."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        mock_user.two_factor_enabled = True
        mock_user.two_factor_secret = "test-secret"

        mock_totp = Mock()
        mock_totp.verify.return_value = False
        mock_pyotp.TOTP.return_value = mock_totp

        response = client.post(
            "/api/auth/2fa/disable",
            json={"code": "000000"}
        )

        assert response.status_code in [400, 422]  # Validation error

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_2fa_endpoints_require_auth(self, mock_get_db, mock_audit, mock_pyotp):
        """Test that 2FA endpoints require authentication."""
        # Create client without auth override
        client = TestClient(app)

        # Test status endpoint
        response = client.get("/api/auth/2fa/status")
        assert response.status_code == 401

        # Test setup endpoint
        response = client.post("/api/auth/2fa/setup")
        assert response.status_code == 401

        # Test enable endpoint
        response = client.post("/api/auth/2fa/enable", json={"code": "123456"})
        assert response.status_code == 401

        # Test disable endpoint
        response = client.post("/api/auth/2fa/disable", json={"code": "123456"})
        assert response.status_code == 401

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_2fa_workflow_full_cycle(self, mock_get_db, mock_audit, mock_pyotp, client, mock_user):
        """Test full 2FA enable/disable cycle."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        mock_pyotp.random_base32.return_value = "secret-123"
        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://test"
        mock_totp.verify.return_value = True
        mock_pyotp.totp.TOTP.return_value = mock_totp

        mock_audit.log_event = Mock()

        # Setup 2FA
        response = client.post("/api/auth/2fa/setup")
        assert response.status_code == 200
        assert mock_user.two_factor_secret == "secret-123"

        # Enable 2FA
        response = client.post(
            "/api/auth/2fa/enable",
            json={"code": "123456"}
        )
        assert response.status_code == 200
        assert mock_user.two_factor_enabled is True

        # Disable 2FA
        response = client.post(
            "/api/auth/2fa/disable",
            json={"code": "123456"}
        )
        assert response.status_code == 200
        assert mock_user.two_factor_enabled is False
        assert mock_user.two_factor_secret is None

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_enable_creates_backup_codes(self, mock_get_db, mock_audit, mock_pyotp, client, mock_user):
        """Test that enabling 2FA creates backup codes."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        mock_user.two_factor_enabled = False
        mock_user.two_factor_secret = "secret"

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp

        mock_audit.log_event = Mock()

        response = client.post(
            "/api/auth/2fa/enable",
            json={"code": "123456"}
        )

        assert response.status_code == 200
        assert mock_user.two_factor_backup_codes is not None

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_enable_logs_audit_event(self, mock_get_db, mock_audit, mock_pyotp, client, mock_user):
        """Test that enabling 2FA logs audit event."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        mock_user.two_factor_enabled = False
        mock_user.two_factor_secret = "secret"

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp

        mock_audit.log_event = Mock()

        response = client.post(
            "/api/auth/2fa/enable",
            json={"code": "123456"}
        )

        assert response.status_code == 200
        mock_audit.log_event.assert_called_once()

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_disable_logs_audit_event(self, mock_get_db, mock_audit, mock_pyotp, client, mock_user):
        """Test that disabling 2FA logs audit event."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        mock_user.two_factor_enabled = True
        mock_user.two_factor_secret = "secret"

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp

        mock_audit.log_event = Mock()

        response = client.post(
            "/api/auth/2fa/disable",
            json={"code": "123456"}
        )

        assert response.status_code == 200
        mock_audit.log_event.assert_called_once()

    @patch('api.auth_2fa_routes.pyotp')
    @patch('api.auth_2fa_routes.audit_service')
    @patch('api.auth_2fa_routes.get_db')
    def test_2fa_endpoints_return_json(self, mock_get_db, mock_audit, mock_pyotp, client, mock_user):
        """Test that 2FA endpoints return JSON."""
        mock_db = Mock(spec=Session)
        mock_get_db.return_value = mock_db

        # Test status endpoint
        response = client.get("/api/auth/2fa/status")
        assert response.headers["content-type"].startswith("application/json")

        # Setup mocks for POST endpoints
        mock_pyotp.random_base32.return_value = "secret"
        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://test"
        mock_totp.verify.return_value = True
        mock_pyotp.totp.TOTP.return_value = mock_totp

        # Test setup endpoint
        response = client.post("/api/auth/2fa/setup")
        assert response.headers["content-type"].startswith("application/json")

        # Test enable endpoint
        mock_user.two_factor_enabled = False
        mock_user.two_factor_secret = "secret"
        response = client.post("/api/auth/2fa/enable", json={"code": "123456"})
        assert response.headers["content-type"].startswith("application/json")

        # Test disable endpoint
        mock_user.two_factor_enabled = True
        response = client.post("/api/auth/2fa/disable", json={"code": "123456"})
        assert response.headers["content-type"].startswith("application/json")
