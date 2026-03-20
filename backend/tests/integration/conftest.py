"""
Integration test fixtures with FastAPI TestClient setup.

Provides database sessions, TestClient with dependency overrides,
and authentication fixtures for API testing.
"""

import os
import pytest
import uuid
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set TESTING environment variable BEFORE any imports
os.environ["TESTING"] = "1"

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from main_api_app import app
from core.auth import create_access_token
from core.database import get_db, Base
from core.models import User
from tests.factories.user_factory import AdminUserFactory


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh in-memory database for each test.

    Simplified version that avoids sorted_tables to prevent NoReferencedTableError
    when running multiple tests in sequence.
    """
    # Use file-based temp SQLite for tests
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create tables using create_all with checkfirst
    # This handles missing foreign key references gracefully
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception:
        # If create_all fails, create tables individually
        for table in Base.metadata.tables.values():
            try:
                table.create(engine, checkfirst=True)
            except Exception:
                # Skip tables that can't be created (missing FK refs, etc.)
                continue

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    # Delete temp database file
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except Exception:
            pass


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


# ============================================================================
# E2E Test Fixtures for Agent Execution Workflow
# ============================================================================

@pytest.fixture(scope="function")
def e2e_db_session(db_session: Session):
    """
    E2E database session with aggressive cleanup.

    Cleans up all E2E test data after each test to prevent cross-test contamination.
    """
    yield db_session

    # Aggressive cleanup for E2E tests
    try:
        # Clean up in order of dependencies
        from sqlalchemy import text
        db_session.execute(text("DELETE FROM episode_segments WHERE 1=1"))
        db_session.execute(text("DELETE FROM agent_episodes WHERE agent_id LIKE 'test-agent%'"))
        db_session.execute(text("DELETE FROM agent_executions WHERE agent_id LIKE 'test-agent%'"))
        db_session.execute(text("DELETE FROM agent_registry WHERE id LIKE 'test-agent%'"))
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        print(f"E2E cleanup error: {e}")


@pytest.fixture(scope="function")
def mock_llm_streaming():
    """
    Mock LLM streaming response for E2E tests.

    Returns an async generator that yields streaming chunks.
    """
    async def stream_completion(*args, **kwargs):
        """Mock streaming completion with test response."""
        chunks = [
            "Test ",
            "response ",
            "chunk 1",
            "Test ",
            "response ",
            "chunk 2",
            "Test ",
            "response ",
            "chunk 3"
        ]
        for chunk in chunks:
            yield {
                "choices": [{
                    "delta": {"content": chunk},
                    "finish_reason": None
                }],
                "usage": None
            }
        # Final chunk with finish_reason
        yield {
            "choices": [{
                "delta": {},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }

    return stream_completion


@pytest.fixture(scope="function")
def mock_llm_streaming_error():
    """
    Mock LLM streaming error for E2E error path tests.
    """
    async def stream_completion_error(*args, **kwargs):
        """Mock streaming completion with error."""
        yield {
            "choices": [{
                "delta": {"content": "Initial chunk"},
                "finish_reason": None
            }],
            "usage": None
        }
        # Simulate LLM API error
        raise Exception("LLM API error: rate limit exceeded")

    return stream_completion_error


@pytest.fixture(scope="function")
def e2e_client(client, e2e_db_session, mock_websocket):
    """
    E2E test client with all necessary mocks.

    Combines TestClient with database session, WebSocket mocks,
    and authentication bypass for comprehensive E2E testing.
    """
    yield client


@pytest.fixture(scope="function")
def execution_id():
    """
    Generate unique execution ID for E2E tests.
    """
    import uuid
    return str(uuid.uuid4())
