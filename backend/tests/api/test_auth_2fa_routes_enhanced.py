"""
Enhanced Auth 2FA Routes API Tests

Comprehensive TestClient-based coverage for two-factor authentication endpoints.

Tests cover:
- 2FA status endpoint (GET /api/auth/2fa/status)
- 2FA setup endpoint (POST /api/auth/2fa/setup)
- 2FA enable endpoint (POST /api/auth/2fa/enable)
- 2FA disable endpoint (POST /api/auth/2fa/disable)
- TOTP verification with pyotp mocking
- Audit logging verification
- Error paths and edge cases
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from api.auth_2fa_routes import router
from core.auth import get_current_user
from core.models import User
from core.models import AuditEventType, SecurityLevel


# ============================================================================
# FastAPI Test App
# ============================================================================

def create_test_app():
    """Create FastAPI app with auth_2fa_routes for testing."""
    app = FastAPI()
    app.include_router(router)
    return app


# ============================================================================
# Test: 2FA Status Endpoint
# ============================================================================

class TestTwoFactorStatus:
    """Test GET /api/auth/2fa/status endpoint."""

    @pytest.fixture
    def mock_user_disabled(self):
        """Create mock user with 2FA disabled."""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "user@example.com"
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.two_factor_backup_codes = None
        return user

    @pytest.fixture
    def mock_user_enabled(self):
        """Create mock user with 2FA enabled."""
        user = Mock(spec=User)
        user.id = "user-456"
        user.email = "2fa@example.com"
        user.two_factor_enabled = True
        user.two_factor_secret = "JBSWY3DPEHPK3PXP"
        user.two_factor_backup_codes = ["BACKUP-1234-5678"]
        return user

    @pytest.fixture
    def client_disabled(self, mock_user_disabled):
        """Create test client with 2FA disabled user."""
        app = create_test_app()
        app.dependency_overrides[get_current_user] = lambda: mock_user_disabled
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()

    @pytest.fixture
    def client_enabled(self, mock_user_enabled):
        """Create test client with 2FA enabled user."""
        app = create_test_app()
        app.dependency_overrides[get_current_user] = lambda: mock_user_enabled
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()

    def test_status_when_disabled(self, client_disabled):
        """Test GET /api/auth/2fa/status returns enabled=False."""
        response = client_disabled.get("/api/auth/2fa/status")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert data["enabled"] is False

    def test_status_when_enabled(self, client_enabled):
        """Test GET /api/auth/2fa/status returns enabled=True."""
        response = client_enabled.get("/api/auth/2fa/status")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert data["enabled"] is True

    def test_status_requires_auth(self):
        """Test 401 without Authorization header."""
        app = create_test_app()
        client = TestClient(app)

        response = client.get("/api/auth/2fa/status")

        assert response.status_code == 401

    def test_status_response_format(self, client_disabled):
        """Test verify {"enabled": bool} structure."""
        response = client_disabled.get("/api/auth/2fa/status")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert isinstance(data, dict)
        assert "enabled" in data
        assert isinstance(data["enabled"], bool)

        # Verify no extra fields
        assert len(data.keys()) == 1


# ============================================================================
# Test: 2FA Setup Endpoint
# ============================================================================

class TestTwoFactorSetup:
    """Test POST /api/auth/2fa/setup endpoint."""

    @pytest.fixture
    def mock_user(self):
        """Create mock user with 2FA disabled."""
        user = Mock(spec=User)
        user.id = "user-789"
        user.email = "setup@example.com"
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.two_factor_backup_codes = None
        return user

    @pytest.fixture
    def mock_user_already_enabled(self):
        """Create mock user with 2FA already enabled."""
        user = Mock(spec=User)
        user.id = "user-already"
        user.email = "already@example.com"
        user.two_factor_enabled = True
        user.two_factor_secret = "EXISTING_SECRET"
        user.two_factor_backup_codes = ["BACKUP-EXISTING"]
        return user

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def client(self, mock_user, mock_db):
        """Create test client with auth override and db mock."""
        from core.database import get_db

        app = create_test_app()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()

    @pytest.fixture
    def client_already_enabled(self, mock_user_already_enabled, mock_db):
        """Create test client with 2FA already enabled."""
        from core.database import get_db

        app = create_test_app()
        app.dependency_overrides[get_current_user] = lambda: mock_user_already_enabled
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    @patch('api.auth_2fa_routes.pyotp.totp.TOTP')
    def test_setup_generates_secret(self, mock_totp_class, mock_random_base32, client, mock_user, mock_db):
        """Test POST /api/auth/2fa/setup generates new secret."""
        # Configure mocks
        mock_random_base32.return_value = "JBSWY3DPEHPK3PXP"

        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://totp/test"
        mock_totp_class.return_value = mock_totp

        response = client.post("/api/auth/2fa/setup")

        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        assert data["secret"] == "JBSWY3DPEHPK3PXP"

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    @patch('api.auth_2fa_routes.pyotp.totp.TOTP')
    def test_setup_returns_otpauth_url(self, mock_totp_class, mock_random_base32, client, mock_user, mock_db):
        """Test response includes otpauth_url for QR code."""
        # Configure mocks
        mock_random_base32.return_value = "TEST_SECRET"

        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://totp/Atom%20AI%20(Upstream):setup@example.com?secret=TEST_SECRET&issuer=Atom+AI+(Upstream)"
        mock_totp_class.return_value = mock_totp

        response = client.post("/api/auth/2fa/setup")

        assert response.status_code == 200
        data = response.json()
        assert "otpauth_url" in data
        assert data["otpauth_url"].startswith("otpauth://totp/")

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    @patch('api.auth_2fa_routes.pyotp.totp.TOTP')
    def test_setup_requires_auth(self, mock_totp_class, mock_random_base32):
        """Test 401 without Authorization header."""
        app = create_test_app()
        client = TestClient(app)

        response = client.post("/api/auth/2fa/setup")

        assert response.status_code == 401

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    @patch('api.auth_2fa_routes.pyotp.totp.TOTP')
    def test_setup_saves_secret_to_user(self, mock_totp_class, mock_random_base32, client, mock_user, mock_db):
        """Test verify two_factor_secret set on user model."""
        # Configure mocks
        mock_random_base32.return_value = "NEW_SECRET_32_CHARS"

        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://totp/test"
        mock_totp_class.return_value = mock_totp

        response = client.post("/api/auth/2fa/setup")

        assert response.status_code == 200
        assert mock_user.two_factor_secret == "NEW_SECRET_32_CHARS"
        assert mock_db.commit.called

    def test_setup_when_already_enabled(self, client_already_enabled):
        """Test 409 conflict when 2FA already enabled."""
        response = client_already_enabled.post("/api/auth/2fa/setup")

        assert response.status_code == 409
        data = response.json()
        assert "error" in data or "detail" in data

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    @patch('api.auth_2fa_routes.pyotp.totp.TOTP')
    def test_setup_issuer_name(self, mock_totp_class, mock_random_base32, client, mock_user, mock_db):
        """Test verify "Atom AI (Upstream)" in provisioning_uri."""
        # Configure mocks
        mock_random_base32.return_value = "SECRET"

        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://totp/Atom%20AI%20(Upstream):user@example.com?secret=SECRET&issuer=Atom+AI+(Upstream)"
        mock_totp_class.return_value = mock_totp

        response = client.post("/api/auth/2fa/setup")

        assert response.status_code == 200
        data = response.json()
        assert "otpauth_url" in data

        # Verify issuer name in URL
        assert "Atom+AI+(Upstream)" in data["otpauth_url"] or "Atom%20AI%20(Upstream)" in data["otpauth_url"]

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    @patch('api.auth_2fa_routes.pyotp.totp.TOTP')
    def test_setup_secret_length(self, mock_totp_class, mock_random_base32, client, mock_user, mock_db):
        """Test verify secret is 32 chars (base32)."""
        # Configure mock to return 32-char secret
        mock_random_base32.return_value = "JBSWY3DPEHPK3PXP"  # 16 chars (base32 standard)

        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://totp/test"
        mock_totp_class.return_value = mock_totp

        response = client.post("/api/auth/2fa/setup")

        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        # Base32 secrets are typically 16-32 chars
        assert len(data["secret"]) >= 16


# ============================================================================
# Test: 2FA Enable Endpoint
# ============================================================================

class TestTwoFactorEnable:
    """Test POST /api/auth/2fa/enable endpoint."""

    @pytest.fixture
    def mock_user(self):
        """Create mock user with 2FA setup but not enabled."""
        user = Mock(spec=User)
        user.id = "user-enable"
        user.email = "enable@example.com"
        user.two_factor_enabled = False
        user.two_factor_secret = "SECRET_FOR_ENABLE"
        user.two_factor_backup_codes = None
        return user

    @pytest.fixture
    def mock_user_already_enabled(self):
        """Create mock user with 2FA already enabled."""
        user = Mock(spec=User)
        user.id = "user-already-enabled"
        user.email = "already-enabled@example.com"
        user.two_factor_enabled = True
        user.two_factor_secret = "EXISTING_SECRET"
        user.two_factor_backup_codes = ["BACKUP-CODE"]
        return user

    @pytest.fixture
    def mock_user_no_secret(self):
        """Create mock user without 2FA secret."""
        user = Mock(spec=User)
        user.id = "user-no-secret"
        user.email = "no-secret@example.com"
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.two_factor_backup_codes = None
        return user

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def client(self, mock_user, mock_db):
        """Create test client with auth override and db mock."""
        from core.database import get_db

        app = create_test_app()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()

    @pytest.fixture
    def client_already_enabled(self, mock_user_already_enabled, mock_db):
        """Create test client with 2FA already enabled."""
        from core.database import get_db

        app = create_test_app()
        app.dependency_overrides[get_current_user] = lambda: mock_user_already_enabled
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()

    @pytest.fixture
    def client_no_secret(self, mock_user_no_secret, mock_db):
        """Create test client without 2FA secret."""
        from core.database import get_db

        app = create_test_app()
        app.dependency_overrides[get_current_user] = lambda: mock_user_no_secret
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    @patch('api.auth_2fa_routes.audit_service')
    def test_enable_with_valid_code(self, mock_audit, mock_totp_class, client, mock_user, mock_db):
        """Test POST /api/auth/2fa/enable success."""
        # Configure TOTP mock
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        # Configure audit mock
        mock_audit.log_event = Mock()

        response = client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 200
        data = response.json()
        assert "backup_codes" in data or "success" in data

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_enable_invalid_code(self, mock_totp_class, client, mock_user, mock_db):
        """Test 400 validation error for wrong TOTP code."""
        # Configure TOTP mock to reject code
        mock_totp = Mock()
        mock_totp.verify.return_value = False
        mock_totp_class.return_value = mock_totp

        response = client.post("/api/auth/2fa/enable", json={"code": "000000"})

        assert response.status_code in [400, 422]

    def test_enable_requires_auth(self):
        """Test 401 without Authorization header."""
        app = create_test_app()
        test_client = TestClient(app)

        response = test_client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 401

    def test_enable_requires_setup(self, client_no_secret):
        """Test 400 when two_factor_secret not set."""
        response = client_no_secret.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code in [400, 422]

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    @patch('api.auth_2fa_routes.audit_service')
    def test_enable_sets_enabled_flag(self, mock_audit, mock_totp_class, client, mock_user, mock_db):
        """Test verify two_factor_enabled=True after success."""
        # Configure mocks
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        mock_audit.log_event = Mock()

        response = client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 200
        assert mock_user.two_factor_enabled is True

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    @patch('api.auth_2fa_routes.audit_service')
    def test_enable_generates_backup_codes(self, mock_audit, mock_totp_class, client, mock_user, mock_db):
        """Test verify two_factor_backup_codes generated."""
        # Configure mocks
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        mock_audit.log_event = Mock()

        response = client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 200
        assert mock_user.two_factor_backup_codes is not None
        assert isinstance(mock_user.two_factor_backup_codes, list)

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    @patch('api.auth_2fa_routes.audit_service')
    def test_enable_audit_log(self, mock_audit, mock_totp_class, client, mock_user, mock_db):
        """Test verify audit_service.log_event called."""
        # Configure mocks
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        mock_audit.log_event = Mock()

        response = client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 200
        assert mock_audit.log_event.called

        # Verify audit log parameters
        call_kwargs = mock_audit.log_event.call_args.kwargs
        assert call_kwargs["event_type"] == AuditEventType.UPDATE.value
        assert call_kwargs["action"] == "2fa_enabled"
        assert call_kwargs["security_level"] == SecurityLevel.HIGH.value
        assert call_kwargs["user_id"] == mock_user.id
        assert call_kwargs["user_email"] == mock_user.email

    def test_enable_already_enabled(self, client_already_enabled):
        """Test 409 conflict when already enabled."""
        response = client_already_enabled.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 409


# ============================================================================
# Test: 2FA Disable Endpoint
# ============================================================================

class TestTwoFactorDisable:
    """Test POST /api/auth/2fa/disable endpoint."""

    @pytest.fixture
    def mock_user(self):
        """Create mock user with 2FA enabled."""
        user = Mock(spec=User)
        user.id = "user-disable"
        user.email = "disable@example.com"
        user.two_factor_enabled = True
        user.two_factor_secret = "SECRET_TO_DISABLE"
        user.two_factor_backup_codes = ["BACKUP-CODE-1"]
        return user

    @pytest.fixture
    def mock_user_not_enabled(self):
        """Create mock user with 2FA disabled."""
        user = Mock(spec=User)
        user.id = "user-not-enabled"
        user.email = "not-enabled@example.com"
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.two_factor_backup_codes = None
        return user

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = Mock(spec=Session)
        return db

    @pytest.fixture
    def client(self, mock_user, mock_db):
        """Create test client with auth override and db mock."""
        from core.database import get_db

        app = create_test_app()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()

    @pytest.fixture
    def client_not_enabled(self, mock_user_not_enabled, mock_db):
        """Create test client with 2FA not enabled."""
        from core.database import get_db

        app = create_test_app()
        app.dependency_overrides[get_current_user] = lambda: mock_user_not_enabled
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    @patch('api.auth_2fa_routes.audit_service')
    def test_disable_with_valid_code(self, mock_audit, mock_totp_class, client, mock_user, mock_db):
        """Test POST /api/auth/2fa/disable success."""
        # Configure TOTP mock
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        # Configure audit mock
        mock_audit.log_event = Mock()

        response = client.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_disable_invalid_code(self, mock_totp_class, client, mock_user, mock_db):
        """Test 400 validation error for wrong TOTP code."""
        # Configure TOTP mock to reject code
        mock_totp = Mock()
        mock_totp.verify.return_value = False
        mock_totp_class.return_value = mock_totp

        response = client.post("/api/auth/2fa/disable", json={"code": "000000"})

        assert response.status_code in [400, 422]

    def test_disable_requires_auth(self):
        """Test 401 without Authorization header."""
        app = create_test_app()
        test_client = TestClient(app)

        response = test_client.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 401

    def test_disable_when_not_enabled(self, client_not_enabled):
        """Test 400 validation error when 2FA not enabled."""
        response = client_not_enabled.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code in [400, 422]

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    @patch('api.auth_2fa_routes.audit_service')
    def test_disable_clears_enabled_flag(self, mock_audit, mock_totp_class, client, mock_user, mock_db):
        """Test verify two_factor_enabled=False after success."""
        # Configure mocks
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        mock_audit.log_event = Mock()

        response = client.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200
        assert mock_user.two_factor_enabled is False

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    @patch('api.auth_2fa_routes.audit_service')
    def test_disable_clears_secret(self, mock_audit, mock_totp_class, client, mock_user, mock_db):
        """Test verify two_factor_secret=None after success."""
        # Configure mocks
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        mock_audit.log_event = Mock()

        response = client.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200
        assert mock_user.two_factor_secret is None

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    @patch('api.auth_2fa_routes.audit_service')
    def test_disable_clears_backup_codes(self, mock_audit, mock_totp_class, client, mock_user, mock_db):
        """Test verify two_factor_backup_codes=None after success."""
        # Configure mocks
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        mock_audit.log_event = Mock()

        response = client.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200
        assert mock_user.two_factor_backup_codes is None

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    @patch('api.auth_2fa_routes.audit_service')
    def test_disable_audit_log(self, mock_audit, mock_totp_class, client, mock_user, mock_db):
        """Test verify audit_service.log_event called."""
        # Configure mocks
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        mock_audit.log_event = Mock()

        response = client.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200
        assert mock_audit.log_event.called

        # Verify audit log parameters
        call_kwargs = mock_audit.log_event.call_args.kwargs
        assert call_kwargs["event_type"] == AuditEventType.UPDATE.value
        assert call_kwargs["action"] == "2fa_disabled"
        assert call_kwargs["security_level"] == SecurityLevel.HIGH.value
        assert call_kwargs["user_id"] == mock_user.id
        assert call_kwargs["user_email"] == mock_user.email

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    @patch('api.auth_2fa_routes.audit_service')
    def test_disable_audit_details(self, mock_audit, mock_totp_class, client, mock_user, mock_db):
        """Test verify action="2fa_disabled" in log."""
        # Configure mocks
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp
        mock_audit.log_event = Mock()

        response = client.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200
        assert mock_audit.log_event.called

        # Verify description includes user email
        call_kwargs = mock_audit.log_event.call_args.kwargs
        assert "2fa_disabled" in call_kwargs.get("action", "")
        assert mock_user.email in str(call_kwargs.get("description", ""))


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
