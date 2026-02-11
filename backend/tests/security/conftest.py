"""
Security test fixtures for authentication and JWT testing.
"""
import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time
from jose import jwt
from sqlalchemy.orm import Session
from tests.property_tests.conftest import db_session
from tests.factories.user_factory import UserFactory
from core.auth import SECRET_KEY, ALGORITHM, create_access_token, get_password_hash


@pytest.fixture(scope="function")
def test_user_with_password(db_session: Session):
    """Create user with known password for testing."""
    from core.models import User

    user = UserFactory(
        email="auth@test.com",
        password_hash=get_password_hash("KnownPassword123!")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
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
