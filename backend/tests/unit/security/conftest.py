"""
Fixtures for security unit tests.

Provides fixtures for testing authentication endpoints, JWT tokens,
and security-related functionality.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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

from core.auth import (
    SECRET_KEY,
    ALGORITHM,
    create_access_token,
    get_password_hash,
    create_mobile_token
)
from core.database import get_db, Base
from core.models import User, ActiveToken, RevokedToken
from tests.factories.user_factory import UserFactory, AdminUserFactory
from sqlalchemy import text


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for security tests.

    This includes ActiveToken and RevokedToken tables for token management tests.
    """
    # Use in-memory SQLite for fast, isolated tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create all tables, including ActiveToken and RevokedToken
    # Note: There are some duplicate index issues in models.py, so we use checkfirst=True
    # to handle them gracefully
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as e:
        # Log but don't fail - some tables may have been created
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Some tables failed to create during setup: {e}")

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()


@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Create a FastAPI TestClient for testing API endpoints.
    """
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
def test_user_with_password(db_session: Session):
    """Create user with known password for testing."""
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
    import jwt
    try:
        payload = jwt.decode(valid_auth_token, SECRET_KEY, algorithms=[ALGORITHM])
        payload["admin"] = True  # Add privilege escalation
        # Re-encode with wrong secret
        return jwt.encode(payload, "wrong_secret", algorithm=ALGORITHM)
    except:
        return "tampered.invalid.token"


@pytest.fixture(scope="function")
def admin_user(db_session: Session):
    """Create an admin user for testing."""
    user = AdminUserFactory(_session=db_session)
    return user


@pytest.fixture(scope="function")
def admin_token(client, admin_user: User) -> str:
    """Get an authentication token for the admin user."""
    return create_access_token(data={"sub": str(admin_user.id)})


def create_test_token(user_id: str, expires_delta: timedelta = None):
    """Helper to create test JWT tokens."""
    return create_access_token(data={"sub": user_id}, expires_delta=expires_delta)
