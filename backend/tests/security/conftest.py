"""
Security test fixtures for authentication and JWT testing.
"""
import pytest
from datetime import datetime, timedelta
try:
    from freezegun import freeze_time
except ImportError:
    # freezegun not available, create a no-op context manager
    class freeze_time:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
from jose import jwt
from sqlalchemy.orm import Session
from tests.property_tests.conftest import db_session
from tests.factories.user_factory import UserFactory
from core.auth import SECRET_KEY, ALGORITHM, create_access_token, get_password_hash
from core.models import User


@pytest.fixture(scope="function")
def test_user_with_password(db_session: Session):
    """Create user with known password for testing."""
    from tests.factories.user_factory import UserFactory

    user = UserFactory(
        email="auth@test.com",
        password_hash=get_password_hash("KnownPassword123!"),
        _session=db_session
    )
    return user


@pytest.fixture(scope="function")
def valid_auth_token(test_user_with_password):
    """Create valid JWT token for test user."""
    return create_access_token(data={"sub": str(test_user_with_password.id)})


@pytest.fixture(scope="function")
def expired_auth_token(test_user_with_password):
    """Create expired JWT token for testing expiration."""
    with freeze_time("2026-02-01 10:00:00"):
        token = create_access_token(data={"sub": str(test_user_with_password.id)})
    return token


@pytest.fixture(scope="function")
def invalid_auth_token():
    """Create invalid JWT token (malformed)."""
    return "invalid.jwt.token"


@pytest.fixture(scope="function")
def tampered_token(valid_auth_token):
    """Create JWT token that has been tampered with."""
    # Decode, modify, re-encode with wrong secret
    try:
        payload = jwt.decode(valid_auth_token, SECRET_KEY, algorithms=[ALGORITHM])
        payload["admin"] = True  # Add privilege escalation
        # Re-encode with wrong secret
        return jwt.encode(payload, "wrong_secret", algorithm=ALGORITHM)
    except:
        return "tampered.invalid.token"


@pytest.fixture(scope="function")
def refresh_token(test_user_with_password):
    """Create a refresh token for testing."""
    # Create a token with longer expiry for refresh purposes
    with freeze_time("2026-02-01 10:00:00"):
        from core.auth import create_mobile_token
        tokens = create_mobile_token(
            test_user_with_password,
            device_id="test_device_123",
            expires_delta=timedelta(days=30)
        )
        return tokens.get("refresh_token")


def create_test_token(user_id: str, expires_delta: timedelta = None):
    """Helper to create test JWT tokens."""
    return create_access_token(data={"sub": user_id}, expires_delta=expires_delta)


# =============================================================================
# Additional fixtures for authorization and input validation tests
# =============================================================================

@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Create a FastAPI TestClient for testing API endpoints.
    """
    from fastapi.testclient import TestClient
    from core.database import get_db
    from main_api_app import app

    # Override the database dependency
    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_user(db_session: Session):
    """
    Create an admin user for testing.
    """
    from tests.factories.user_factory import AdminUserFactory

    user = AdminUserFactory(_session=db_session)
    return user


@pytest.fixture(scope="function")
def admin_token(client, admin_user: User) -> str:
    """
    Get an authentication token for the admin user.
    """
    # Create token directly for testing
    return create_access_token(data={"sub": str(admin_user.id)})
