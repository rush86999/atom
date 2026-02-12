"""
Integration test fixtures with FastAPI TestClient setup.

Provides database sessions, TestClient with dependency overrides,
and authentication fixtures for API testing.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from main_api_app import app
from core.auth import create_access_token
from core.database import get_db
from tests.factories.user_factory import UserFactory, AdminUserFactory
from tests.property_tests.conftest import db_session


@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Create TestClient with dependency override for test database.

    This fixture overrides the get_db dependency to use the test database
    session, ensuring all API requests use the test database with transaction
    rollback for isolation.
    """
    def _get_db():
        try:
            yield db_session
        finally:
            pass  # Transaction rolls back

    app.dependency_overrides[get_db] = _get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_token(db_session: Session):
    """
    Create valid JWT token for test user.

    Creates a test user in the database and returns a JWT token
    that can be used for authenticated requests.
    """
    user = UserFactory(email="integration@test.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(data={"sub": user.id})
    return token


@pytest.fixture(scope="function")
def admin_token(db_session: Session):
    """
    Create JWT token for admin user.

    Creates an admin user in the database and returns a JWT token
    with admin privileges for testing admin-only endpoints.
    """
    admin = AdminUserFactory(email="admin@test.com")
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    token = create_access_token(data={"sub": admin.id})
    return token


@pytest.fixture(scope="function")
def test_user(db_session: Session):
    """
    Create a test user in the database.

    Returns a User instance that can be used for testing
    user-related endpoints.
    """
    user = UserFactory(email="testuser@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def auth_headers(auth_token: str):
    """
    Create authentication headers for API requests.

    Returns a dictionary with Authorization header set to Bearer token.
    """
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="function")
def admin_headers(admin_token: str):
    """
    Create admin authentication headers for API requests.

    Returns a dictionary with Authorization header set to admin Bearer token.
    """
    return {"Authorization": f"Bearer {admin_token}"}
