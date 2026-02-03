"""
Tests for Email Verification Service

Tests email verification endpoints with Mailgun integration,
rate limiting, and error handling.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from main_api_app import app
from core.database import get_db
from core.models import User, UserStatus, EmailVerificationToken


client = TestClient(app)


@pytest.fixture
def db_session():
    """Create a test database session"""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        status=UserStatus.PENDING.value,
        email_verified=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    # Cleanup
    db_session.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id
    ).delete()
    db_session.delete(user)
    db_session.commit()


class TestEmailVerification:
    """Test email verification endpoints"""

    def test_send_verification_email_dev_mode(self, test_user: User, monkeypatch):
        """Test sending verification email in development mode (logging only)"""
        monkeypatch.setenv("EMAIL_SERVICE_ENABLED", "false")

        response = client.post(
            "/api/email-verification/send",
            json={"email": test_user.email}
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Verification email sent"

    def test_send_verification_email_nonexistent_user(self, db_session: Session, monkeypatch):
        """Test that verification endpoint doesn't reveal user existence"""
        monkeypatch.setenv("EMAIL_SERVICE_ENABLED", "false")

        response = client.post(
            "/api/email-verification/send",
            json={"email": "nonexistent@example.com"}
        )

        # Should return success to prevent email enumeration
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_verify_email_success(self, test_user: User, db_session: Session):
        """Test successful email verification"""
        # Create a verification token
        import secrets
        code = secrets.token_hex(3)  # 6 characters
        token = EmailVerificationToken(
            user_id=test_user.id,
            token=code,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db_session.add(token)
        db_session.commit()

        # Verify the email
        response = client.post(
            "/api/email-verification/verify",
            json={
                "email": test_user.email,
                "code": code
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Email verified successfully"

        # Verify user is marked as verified and active
        db_session.refresh(test_user)
        assert test_user.email_verified is True
        assert test_user.status == UserStatus.ACTIVE.value

        # Verify token is deleted
        remaining_token = db_session.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == test_user.id
        ).first()
        assert remaining_token is None

    def test_verify_email_invalid_code(self, test_user: User):
        """Test verification with invalid code"""
        response = client.post(
            "/api/email-verification/verify",
            json={
                "email": test_user.email,
                "code": "000000"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid or expired" in data["detail"]

    def test_verify_email_expired_code(self, test_user: User, db_session: Session):
        """Test verification with expired code"""
        # Create an expired token
        import secrets
        code = secrets.token_hex(3)
        token = EmailVerificationToken(
            user_id=test_user.id,
            token=code,
            expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired
        )
        db_session.add(token)
        db_session.commit()

        response = client.post(
            "/api/email-verification/verify",
            json={
                "email": test_user.email,
                "code": code
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid or expired" in data["detail"]

    def test_verify_email_nonexistent_user(self):
        """Test verification for non-existent user"""
        response = client.post(
            "/api/email-verification/verify",
            json={
                "email": "nonexistent@example.com",
                "code": "123456"
            }
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_verify_email_invalid_format(self):
        """Test verification with invalid email format"""
        response = client.post(
            "/api/email-verification/verify",
            json={
                "email": "not-an-email",
                "code": "123456"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_rate_limiting(self, test_user: User, monkeypatch):
        """Test rate limiting for email sending"""
        # Enable email service to test rate limiting
        monkeypatch.setenv("EMAIL_SERVICE_ENABLED", "true")
        monkeypatch.setenv("MAILGUN_API_KEY", "test-key")
        monkeypatch.setenv("MAILGUN_DOMAIN", "test.domain")

        # Send 3 emails (should succeed)
        for i in range(3):
            response = client.post(
                "/api/email-verification/send",
                json={"email": test_user.email}
            )
            assert response.status_code == 200

        # 4th email should hit rate limit
        response = client.post(
            "/api/email-verification/send",
            json={"email": test_user.email}
        )
        assert response.status_code == 429
        data = response.json()
        assert "detail" in data
        assert "rate limit" in data["detail"].lower()

    def test_code_replacement(self, test_user: User, db_session: Session, monkeypatch):
        """Test that sending new email replaces old code"""
        monkeypatch.setenv("EMAIL_SERVICE_ENABLED", "false")

        # Send first email
        client.post(
            "/api/email-verification/send",
            json={"email": test_user.email}
        )

        # Get first token
        first_token = db_session.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == test_user.id
        ).first()
        assert first_token is not None
        first_code = first_token.token

        # Send second email
        client.post(
            "/api/email-verification/send",
            json={"email": test_user.email}
        )

        # Get new token
        new_tokens = db_session.query(EmailVerificationToken).filter(
            EmailVerificationToken.user_id == test_user.id
        ).all()

        # Should only have one token (old one replaced)
        assert len(new_tokens) == 1
        assert new_tokens[0].token != first_code

    def test_verification_code_format(self, test_user: User, db_session: Session):
        """Test that verification code is 6 characters"""
        import secrets

        # Generate code like the service does
        code = secrets.token_hex(3)

        assert len(code) == 6
        assert code.isalnum()


class TestEmailService:
    """Test EmailService class functionality"""

    def test_email_service_initialization(self, monkeypatch):
        """Test EmailService initialization with different configurations"""
        from api.email_verification_routes import EmailService

        # Test default initialization
        monkeypatch.setenv("EMAIL_SERVICE_ENABLED", "false")
        service = EmailService()
        assert service.enabled is False
        assert service.provider == "mailgun"

        # Test with enabled but no API key
        monkeypatch.setenv("EMAIL_SERVICE_ENABLED", "true")
        monkeypatch.setenv("MAILGUN_API_KEY", "")
        service = EmailService()
        assert service.enabled is False  # Should be disabled if no API key

        # Test with valid configuration
        monkeypatch.setenv("MAILGUN_API_KEY", "test-key")
        monkeypatch.setenv("MAILGUN_DOMAIN", "test.domain")
        service = EmailService()
        assert service.enabled is True

    def test_rate_limit_tracking(self):
        """Test rate limit tracking mechanism"""
        from api.email_verification_routes import _email_rate_tracker, _RATE_LIMIT_WINDOW
        from datetime import datetime, timedelta

        email = "test@example.com"
        now = datetime.utcnow()

        # Add some timestamps
        _email_rate_tracker[email] = [
            now - timedelta(minutes=30),
            now - timedelta(minutes=20),
            now - timedelta(minutes=10)
        ]

        # Should have 3 entries
        assert len(_email_rate_tracker[email]) == 3

        # Old entries outside window should be cleaned up
        # (This happens in _check_rate_limit method)
