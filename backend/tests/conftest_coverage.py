"""
Conftest for coverage tests - provides client fixture with proper app import.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import the app
try:
    from main_api_app import app
    APP_AVAILABLE = True
except ImportError:
    try:
        from main import app
        APP_AVAILABLE = True
    except ImportError:
        from fastapi import FastAPI
        app = FastAPI()
        APP_AVAILABLE = False


@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    Create TestClient with dependency override for test database.
    Similar to integration/conftest_atom_agent.py but for coverage tests.
    """
    if not APP_AVAILABLE:
        pytest.skip("FastAPI app not available")

    from core.database import get_db

    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db

    # Mock get_current_user to bypass auth
    def _mock_get_current_user():
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        email = f"test_{unique_id}@coverage.com"

        try:
            from core.models import User
            user = db_session.query(User).filter(User.email == email).first()
            if user:
                return user
        except Exception:
            pass

        # Create test user
        from datetime import datetime
        user = User(
            email=email,
            username=f"testuser_{unique_id}",
            hashed_password="hashed",
            is_active=True,
            created_at=datetime.utcnow()
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    # Override get_current_user to bypass auth
    try:
        from core.auth import get_current_user
        app.dependency_overrides[get_current_user] = _mock_get_current_user
    except ImportError:
        pass

    # Modify TrustedHostMiddleware to allow testserver
    for middleware in app.user_middleware:
        if hasattr(middleware, 'cls') and middleware.cls.__name__ == 'TrustedHostMiddleware':
            middleware.kwargs['allowed_hosts'] = ['testserver', 'localhost', '127.0.0.1', '0.0.0.0', '*']
            break

    # Create TestClient
    test_client = TestClient(app, base_url="http://testserver")

    yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_client(client: TestClient):
    """Alias for client fixture for compatibility."""
    yield client
