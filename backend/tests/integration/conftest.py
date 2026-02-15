"""
Integration test fixtures with FastAPI TestClient setup.

Provides database sessions, TestClient with dependency overrides,
and authentication fixtures for API testing.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from main_api_app import app
from core.auth import create_access_token
from core.database import get_db
from core.models import User
from tests.factories.user_factory import AdminUserFactory
from tests.property_tests.conftest import db_session


@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Create TestClient with dependency override for test database.

    This fixture overrides the get_db dependency to use the test database
    session, ensuring all API requests use the test database with transaction
    rollback for isolation. Also bypasses authentication for integration tests.
    """
    def _get_db():
        try:
            yield db_session
        finally:
            pass  # Transaction rolls back

    app.dependency_overrides[get_db] = _get_db

    # Override get_current_user to bypass auth - create lazy user factory
    def _mock_get_current_user():
        """Mock get_current_user - creates or returns test user with admin role"""
        from tests.factories.user_factory import AdminUserFactory

        # Use unique email to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        email = f"test_{unique_id}@integration.com"

        # Try to get existing user, handling case where tables don't exist yet
        try:
            user = db_session.query(User).filter(User.email == email).first()
            if user:
                return user
        except Exception as e:
            # Table doesn't exist or other error, will create user below
            pass

        # Create new admin user with all permissions
        user = AdminUserFactory(email=email, _session=db_session)
        db_session.commit()
        db_session.refresh(user)

        return user

    # Override get_current_user to bypass auth
    # Import from core.auth where it's actually defined
    try:
        from core.auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_get_current_user
    except ImportError:
        pass

    # Modify TrustedHostMiddleware to allow testserver
    # The middleware is stored as Middleware objects with cls and kwargs attributes
    for middleware in app.user_middleware:
        if hasattr(middleware, 'cls') and middleware.cls.__name__ == 'TrustedHostMiddleware':
            # Modify the allowed_hosts to include testserver
            middleware.kwargs['allowed_hosts'] = ['testserver', 'localhost', '127.0.0.1', '0.0.0.0', '*']
            break

    # Create TestClient with proper headers
    test_client = TestClient(app, base_url="http://testserver")

    yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client_no_auth(db_session: Session):
    """
    Create TestClient WITHOUT bypassing authentication.

    This fixture provides a client that enforces authentication,
    useful for testing auth requirements and permissions.
    """
    def _get_db():
        try:
            yield db_session
        finally:
            pass  # Transaction rolls back

    app.dependency_overrides[get_db] = _get_db

    # Do NOT override get_current_user - authentication is enforced

    # Modify TrustedHostMiddleware to allow testserver
    for middleware in app.user_middleware:
        if hasattr(middleware, 'cls') and middleware.cls.__name__ == 'TrustedHostMiddleware':
            middleware.kwargs['allowed_hosts'] = ['testserver', 'localhost', '127.0.0.1', '0.0.0.0', '*']
            break

    # Create TestClient with proper headers
    test_client = TestClient(app, base_url="http://testserver")

    yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def auth_token(db_session: Session):
    """
    Create valid JWT token for test user.

    Creates a test user in the database and returns a JWT token
    that can be used for authenticated requests.
    """
    from tests.factories.user_factory import UserFactory
    unique_id = str(uuid.uuid4())[:8]
    user = UserFactory(email=f"auth_{unique_id}@integration.com", _session=db_session)
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
    from tests.factories.user_factory import AdminUserFactory
    unique_id = str(uuid.uuid4())[:8]
    admin = AdminUserFactory(email=f"admin_{unique_id}@integration.com", _session=db_session)
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
    from tests.factories.user_factory import UserFactory
    unique_id = str(uuid.uuid4())[:8]
    user = UserFactory(email=f"user_{unique_id}@integration.com", _session=db_session)
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
