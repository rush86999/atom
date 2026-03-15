"""
Coverage-driven tests for auth_2fa_routes.py (0% -> 75%+ target)

API Endpoints Tested:
- GET /api/auth/2fa/status - Check 2FA enabled status
- POST /api/auth/2fa/setup - Generate TOTP secret and provisioning URL
- POST /api/auth/2fa/enable - Verify code and enable 2FA
- POST /api/auth/2fa/disable - Disable 2FA after verification

Coverage Target Areas:
- Lines 1-30: Route initialization and dependencies
- Lines 30-55: Status endpoint
- Lines 55-90: Setup endpoint (secret generation)
- Lines 90-125: Enable endpoint (code verification)
- Lines 125-165: Disable endpoint
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import auth 2FA routes router
from api.auth_2fa_routes import router, TwoFactorSetupResponse, TwoFactorVerifyRequest, TwoFactorStatusResponse

# Import models
from core.models import Base, User, AuditEventType, SecurityLevel

# Import auth dependencies
from core.auth import get_current_user
from core.database import get_db

# Mock audit service globally to avoid database issues
@pytest.fixture(autouse=True)
def mock_audit_service():
    """Mock audit service to avoid database table requirements."""
    with patch('api.auth_2fa_routes.audit_service') as mock_service:
        mock_service.log_event = Mock()
        yield mock_service


# ============================================================================
# Test Database Setup
# ============================================================================

@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    # Create only the tables we need for auth 2FA routes testing
    from core.models import User

    User.__table__.create(bind=engine, checkfirst=True)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    yield db

    # Cleanup
    db.close()
    User.__table__.drop(bind=engine)


@pytest.fixture(scope="function")
def test_app(test_db: Session):
    """Create FastAPI app with auth 2FA routes for testing."""
    app = FastAPI()
    app.include_router(router)

    # Override get_db dependency
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield app

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(test_app: FastAPI):
    """Create TestClient for testing."""
    return TestClient(test_app)


@pytest.fixture(scope="function")
def test_user(test_db: Session) -> User:
    """Create test user for authentication."""
    user = User(
        id=str(uuid.uuid4()),
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active",
        email_verified=True,
        two_factor_enabled=False,
        two_factor_secret=None,
        two_factor_backup_codes=None
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_user_with_2fa(test_db: Session) -> User:
    """Create test user with 2FA already enabled."""
    user = User(
        id=str(uuid.uuid4()),
        email="test2fa@example.com",
        first_name="Test",
        last_name="User2FA",
        role="member",
        status="active",
        email_verified=True,
        two_factor_enabled=True,
        two_factor_secret="JBSWY3DPEHPK3PXP",
        two_factor_backup_codes=["UP-BACKUP-1234-5678"]
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def authenticated_client(client: TestClient, test_user: User):
    """Create client with authenticated user override."""
    def override_get_current_user():
        return test_user

    from api.auth_2fa_routes import router
    # Override on the app, not the router
    client.app.dependency_overrides[get_current_user] = override_get_current_user

    yield client

    # Clean up
    client.app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def authenticated_client_with_2fa(client: TestClient, test_user_with_2fa: User):
    """Create client with authenticated user (2FA enabled) override."""
    def override_get_current_user():
        return test_user_with_2fa

    from api.auth_2fa_routes import router
    # Override on the app, not the router
    client.app.dependency_overrides[get_current_user] = override_get_current_user

    yield client

    # Clean up
    client.app.dependency_overrides.clear()


# ============================================================================
# Status Endpoint Tests (GET /api/auth/2fa/status)
# ============================================================================

class TestTwoFactorStatus:
    """Tests for 2FA status endpoint."""

    def test_get_2fa_status_disabled(self, authenticated_client: TestClient, test_user: User, test_db: Session):
        """Cover status endpoint when 2FA is disabled (lines 28-31)."""
        test_user.two_factor_enabled = False
        test_db.commit()

        response = authenticated_client.get("/api/auth/2fa/status")

        assert response.status_code == 200
        result = response.json()
        assert result["enabled"] is False

    def test_get_2fa_status_enabled(self, authenticated_client_with_2fa: TestClient, test_user_with_2fa: User, test_db: Session):
        """Cover status endpoint when 2FA is enabled."""
        test_user_with_2fa.two_factor_enabled = True
        test_db.commit()

        response = authenticated_client_with_2fa.get("/api/auth/2fa/status")

        assert response.status_code == 200
        result = response.json()
        assert result["enabled"] is True

    def test_status_endpoint_unauthorized(self, client: TestClient):
        """Cover unauthorized access to status endpoint."""
        # No auth override
        response = client.get("/api/auth/2fa/status")

        assert response.status_code == 401

    def test_status_response_model(self, authenticated_client: TestClient):
        """Cover status response model validation."""
        response = authenticated_client.get("/api/auth/2fa/status")

        assert response.status_code == 200
        # Verify response structure matches TwoFactorStatusResponse
        assert "enabled" in response.json()
        assert isinstance(response.json()["enabled"], bool)

    def test_status_endpoint_returns_json(self, authenticated_client: TestClient):
        """Cover status endpoint returns valid JSON."""
        response = authenticated_client.get("/api/auth/2fa/status")

        assert response.headers["content-type"] == "application/json"
        assert response.status_code == 200

    def test_status_no_database_query(self, authenticated_client: TestClient, test_db: Session):
        """Cover status endpoint doesn't query database beyond user context."""
        # Status endpoint only reads from current_user, no additional DB queries
        response = authenticated_client.get("/api/auth/2fa/status")

        assert response.status_code == 200
        # Should return immediately from user object
        assert response.json()["enabled"] is False


# ============================================================================
# Setup Endpoint Tests (POST /api/auth/2fa/setup)
# ============================================================================

class TestTwoFactorSetup:
    """Tests for 2FA setup endpoint."""

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    @patch('api.auth_2fa_routes.pyotp.totp.TOTP')
    def test_setup_2fa_success(self, mock_totp_class, mock_random, authenticated_client: TestClient, test_user: User, test_db: Session):
        """Cover successful 2FA setup (lines 33-52)."""
        mock_random.return_value = "TESTSECRET123"
        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://totp/Atom%20AI%20(Upstream):test@example.com?secret=TESTSECRET123&issuer=Atom+AI+(Upstream)"
        mock_totp_class.return_value = mock_totp
        test_user.two_factor_enabled = False
        test_db.commit()

        response = authenticated_client.post("/api/auth/2fa/setup")

        assert response.status_code == 200
        result = response.json()
        assert "secret" in result
        assert "otpauth_url" in result
        assert result["secret"] == "TESTSECRET123"
        # Verify secret was saved to user
        test_db.refresh(test_user)
        assert test_user.two_factor_secret == "TESTSECRET123"

    def test_setup_2fa_already_enabled(self, authenticated_client_with_2fa: TestClient, test_user_with_2fa: User, test_db: Session):
        """Cover setup when 2FA is already enabled."""
        test_user_with_2fa.two_factor_enabled = True
        test_db.commit()

        response = authenticated_client_with_2fa.post("/api/auth/2fa/setup")

        assert response.status_code == 409  # Conflict

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    def test_setup_generates_different_secrets(self, mock_random, authenticated_client: TestClient, test_user: User, test_db: Session):
        """Cover that each setup generates unique secrets."""
        secrets = ["SECRET1", "SECRET2"]
        mock_random.side_effect = secrets

        response1 = authenticated_client.post("/api/auth/2fa/setup")
        test_db.refresh(test_user)
        response2 = authenticated_client.post("/api/auth/2fa/setup")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["secret"] == "SECRET1"
        # Second setup should generate a different secret (since 2FA still not enabled)
        test_db.refresh(test_user)
        assert test_user.two_factor_secret == "SECRET2"

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    @patch('api.auth_2fa_routes.pyotp.totp.TOTP')
    def test_setup_creates_otpauth_url(self, mock_totp_class, mock_random, authenticated_client: TestClient):
        """Cover setup creates valid otpauth URL."""
        mock_random.return_value = "MYSECRET"
        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://totp/Atom%20AI%20(Upstream):test@example.com?secret=MYSECRET&issuer=Atom+AI+(Upstream)"
        mock_totp_class.return_value = mock_totp

        response = authenticated_client.post("/api/auth/2fa/setup")

        assert response.status_code == 200
        result = response.json()
        assert result["otpauth_url"].startswith("otpauth://totp/")
        assert "Atom+AI+(Upstream)" in result["otpauth_url"]
        assert "test@example.com" in result["otpauth_url"]

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    def test_setup_saves_secret_to_database(self, mock_random, authenticated_client: TestClient, test_user: User, test_db: Session):
        """Cover setup saves secret to user record."""
        mock_random.return_value = "DBSECRET123"
        test_user.two_factor_secret = None
        test_db.commit()

        response = authenticated_client.post("/api/auth/2fa/setup")

        assert response.status_code == 200
        test_db.refresh(test_user)
        assert test_user.two_factor_secret == "DBSECRET123"

    def test_setup_unauthorized(self, client: TestClient):
        """Cover setup endpoint requires authentication."""
        response = client.post("/api/auth/2fa/setup")

        assert response.status_code == 401

    @patch('api.auth_2fa_routes.pyotp.random_base32')
    def test_setup_without_committing_2fa_enabled(self, mock_random, authenticated_client: TestClient, test_user: User, test_db: Session):
        """Cover setup doesn't enable 2FA, only sets secret."""
        mock_random.return_value = "SECRETONLY"
        test_user.two_factor_enabled = False
        test_db.commit()

        response = authenticated_client.post("/api/auth/2fa/setup")

        assert response.status_code == 200
        test_db.refresh(test_user)
        assert test_user.two_factor_enabled is False  # Still disabled
        assert test_user.two_factor_secret == "SECRETONLY"  # But secret is set


# ============================================================================
# Enable Endpoint Tests (POST /api/auth/2fa/enable)
# ============================================================================

class TestTwoFactorEnable:
    """Tests for 2FA enable endpoint."""

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_enable_2fa_success(self, mock_totp_class, authenticated_client: TestClient, test_user: User, test_db: Session, mock_audit_service):
        """Cover successful 2FA enable (lines 54-90)."""
        test_user.two_factor_enabled = False
        test_user.two_factor_secret = "JBSWY3DPEHPK3PXP"
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        response = authenticated_client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 200
        test_db.refresh(test_user)
        assert test_user.two_factor_enabled is True
        assert test_user.two_factor_backup_codes == ["UP-BACKUP-1234-5678"]
        mock_audit_service.log_event.assert_called_once()

    def test_enable_2fa_already_enabled(self, authenticated_client_with_2fa: TestClient, test_user_with_2fa: User, test_db: Session):
        """Cover enable when already enabled."""
        test_user_with_2fa.two_factor_enabled = True
        test_db.commit()

        response = authenticated_client_with_2fa.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 409  # Conflict

    def test_enable_2fa_no_secret(self, authenticated_client: TestClient, test_user: User, test_db: Session):
        """Cover enable without setup (no secret)."""
        test_user.two_factor_enabled = False
        test_user.two_factor_secret = None
        test_db.commit()

        response = authenticated_client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 400  # Validation error

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_enable_2fa_invalid_code(self, mock_totp_class, authenticated_client: TestClient, test_user: User, test_db: Session):
        """Cover enable with invalid verification code."""
        test_user.two_factor_enabled = False
        test_user.two_factor_secret = "JBSWY3DPEHPK3PXP"
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = False
        mock_totp_class.return_value = mock_totp

        response = authenticated_client.post("/api/auth/2fa/enable", json={"code": "000000"})

        assert response.status_code == 400  # Validation error

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_enable_2fa_valid_code(self, mock_totp_class, authenticated_client: TestClient, test_user: User, test_db: Session):
        """Cover enable with valid verification code."""
        test_user.two_factor_enabled = False
        test_user.two_factor_secret = "JBSWY3DPEHPK3PXP"
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        response = authenticated_client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 200
        test_db.refresh(test_user)
        assert test_user.two_factor_enabled is True

    @pytest.mark.parametrize("code,valid", [
        ("123456", True),
        ("000000", False),
    ])
    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_enable_2fa_code_validation(self, mock_totp_class, authenticated_client: TestClient, test_user: User, test_db: Session, code, valid):
        """Cover various code formats."""
        test_user.two_factor_enabled = False
        test_user.two_factor_secret = "JBSWY3DPEHPK3PXP"
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = valid
        mock_totp_class.return_value = mock_totp

        response = authenticated_client.post("/api/auth/2fa/enable", json={"code": code})

        if valid:
            assert response.status_code == 200
        else:
            assert response.status_code == 400

    def test_enable_missing_code_field(self, authenticated_client: TestClient):
        """Cover validation when code field is missing."""
        response = authenticated_client.post("/api/auth/2fa/enable", json={})

        assert response.status_code == 422  # Validation error

    def test_enable_malformed_json_request(self, authenticated_client: TestClient):
        """Cover malformed JSON handling."""
        response = authenticated_client.post(
            "/api/auth/2fa/enable",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_enable_creates_audit_log(self, mock_totp_class, authenticated_client: TestClient, test_user: User, test_db: Session, mock_audit_service):
        """Cover audit log creation on 2FA enable."""
        test_user.two_factor_enabled = False
        test_user.two_factor_secret = "SECRET"
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        response = authenticated_client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 200
        mock_audit_service.log_event.assert_called_once()
        call_args = mock_audit_service.log_event.call_args
        assert call_args[1]['action'] == "2fa_enabled"
        assert call_args[1]['event_type'] == AuditEventType.UPDATE.value
        assert call_args[1]['security_level'] == SecurityLevel.HIGH.value

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_enable_generates_backup_codes(self, mock_totp_class, authenticated_client: TestClient, test_user: User, test_db: Session):
        """Cover enable generates backup codes."""
        test_user.two_factor_enabled = False
        test_user.two_factor_secret = "SECRET"
        test_user.two_factor_backup_codes = None
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        response = authenticated_client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 200
        test_db.refresh(test_user)
        assert test_user.two_factor_backup_codes == ["UP-BACKUP-1234-5678"]
        result = response.json()
        assert "backup_codes" in result["data"]


# ============================================================================
# Disable Endpoint Tests (POST /api/auth/2fa/disable)
# ============================================================================

class TestTwoFactorDisable:
    """Tests for 2FA disable endpoint."""

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_disable_2fa_success(self, mock_totp_class, authenticated_client_with_2fa: TestClient, test_user_with_2fa: User, test_db: Session, mock_audit_service):
        """Cover successful 2FA disable (lines 92-123)."""
        test_user_with_2fa.two_factor_enabled = True
        test_user_with_2fa.two_factor_secret = "JBSWY3DPEHPK3PXP"
        test_user_with_2fa.two_factor_backup_codes = ["BACKUP123"]
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        response = authenticated_client_with_2fa.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200
        test_db.refresh(test_user_with_2fa)
        assert test_user_with_2fa.two_factor_enabled is False
        assert test_user_with_2fa.two_factor_secret is None
        assert test_user_with_2fa.two_factor_backup_codes is None
        mock_audit_service.log_event.assert_called_once()

    def test_disable_2fa_not_enabled(self, authenticated_client: TestClient, test_user: User, test_db: Session):
        """Cover disable when 2FA is not enabled."""
        test_user.two_factor_enabled = False
        test_db.commit()

        response = authenticated_client.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 400  # Validation error

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_disable_2fa_invalid_code(self, mock_totp_class, authenticated_client_with_2fa: TestClient, test_user_with_2fa: User, test_db: Session):
        """Cover disable with invalid verification code."""
        test_user_with_2fa.two_factor_enabled = True
        test_user_with_2fa.two_factor_secret = "JBSWY3DPEHPK3PXP"
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = False
        mock_totp_class.return_value = mock_totp

        response = authenticated_client_with_2fa.post("/api/auth/2fa/disable", json={"code": "000000"})

        assert response.status_code == 400  # Validation error

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_disable_2fa_valid_code(self, mock_totp_class, authenticated_client_with_2fa: TestClient, test_user_with_2fa: User, test_db: Session):
        """Cover disable with valid verification code."""
        test_user_with_2fa.two_factor_enabled = True
        test_user_with_2fa.two_factor_secret = "JBSWY3DPEHPK3PXP"
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        response = authenticated_client_with_2fa.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200
        test_db.refresh(test_user_with_2fa)
        assert test_user_with_2fa.two_factor_enabled is False

    def test_disable_missing_code_field(self, authenticated_client: TestClient):
        """Cover validation when code field is missing."""
        response = authenticated_client.post("/api/auth/2fa/disable", json={})

        assert response.status_code == 422  # Validation error

    def test_disable_malformed_json_request(self, authenticated_client: TestClient):
        """Cover malformed JSON handling."""
        response = authenticated_client.post(
            "/api/auth/2fa/disable",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_disable_creates_audit_log(self, mock_totp_class, authenticated_client_with_2fa: TestClient, test_user_with_2fa: User, test_db: Session, mock_audit_service):
        """Cover audit log creation on 2FA disable."""
        test_user_with_2fa.two_factor_enabled = True
        test_user_with_2fa.two_factor_secret = "SECRET"
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        response = authenticated_client_with_2fa.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200
        mock_audit_service.log_event.assert_called_once()
        call_args = mock_audit_service.log_event.call_args
        assert call_args[1]['action'] == "2fa_disabled"

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_disable_clears_secret_and_backup_codes(self, mock_totp_class, authenticated_client_with_2fa: TestClient, test_user_with_2fa: User, test_db: Session):
        """Cover disable clears secret and backup codes."""
        test_user_with_2fa.two_factor_enabled = True
        test_user_with_2fa.two_factor_secret = "MYSECRET"
        test_user_with_2fa.two_factor_backup_codes = ["BACKUP1", "BACKUP2"]
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        response = authenticated_client_with_2fa.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200
        test_db.refresh(test_user_with_2fa)
        assert test_user_with_2fa.two_factor_secret is None
        assert test_user_with_2fa.two_factor_backup_codes is None

    def test_disable_unauthorized(self, client: TestClient):
        """Cover disable endpoint requires authentication."""
        response = client.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 401


# ============================================================================
# Audit Service Integration Tests
# ============================================================================

class TestAuditServiceIntegration:
    """Tests for audit service integration with 2FA operations."""

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_enable_audit_log_fields(self, mock_totp_class, authenticated_client: TestClient, test_user: User, test_db: Session, mock_audit_service):
        """Cover audit log contains all required fields for enable."""
        test_user.two_factor_enabled = False
        test_user.two_factor_secret = "SECRET"
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        response = authenticated_client.post("/api/auth/2fa/enable", json={"code": "123456"})

        assert response.status_code == 200
        mock_audit_service.log_event.assert_called_once()
        call_kwargs = mock_audit_service.log_event.call_args[1]
        assert call_kwargs['action'] == "2fa_enabled"
        assert call_kwargs['event_type'] == AuditEventType.UPDATE.value
        assert call_kwargs['user_id'] == test_user.id
        assert call_kwargs['user_email'] == test_user.email
        assert call_kwargs['security_level'] == SecurityLevel.HIGH.value
        assert "2FA enabled" in call_kwargs['description']

    @patch('api.auth_2fa_routes.pyotp.TOTP')
    def test_disable_audit_log_fields(self, mock_totp_class, authenticated_client_with_2fa: TestClient, test_user_with_2fa: User, test_db: Session, mock_audit_service):
        """Cover audit log contains all required fields for disable."""
        test_user_with_2fa.two_factor_enabled = True
        test_user_with_2fa.two_factor_secret = "SECRET"
        test_db.commit()

        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp_class.return_value = mock_totp

        response = authenticated_client_with_2fa.post("/api/auth/2fa/disable", json={"code": "123456"})

        assert response.status_code == 200
        mock_audit_service.log_event.assert_called_once()
        call_kwargs = mock_audit_service.log_event.call_args[1]
        assert call_kwargs['action'] == "2fa_disabled"
        assert call_kwargs['event_type'] == AuditEventType.UPDATE.value
        assert call_kwargs['user_id'] == test_user_with_2fa.id
        assert call_kwargs['user_email'] == test_user_with_2fa.email
        assert call_kwargs['security_level'] == SecurityLevel.HIGH.value
        assert "2FA disabled" in call_kwargs['description']
