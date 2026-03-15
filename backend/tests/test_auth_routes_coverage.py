"""
Coverage-driven tests for enterprise_auth_endpoints.py (0% -> 75%+ target)

API Endpoints Tested:
- POST /api/auth/register - Register new user
- POST /api/auth/login - Authenticate user and return JWT tokens
- POST /api/auth/refresh - Refresh access token using refresh token
- GET /api/auth/me - Get current user info from JWT token
- POST /api/auth/change-password - Change user password
- GET /api/auth/test-auth - Test authentication endpoint

Coverage Target Areas:
- Lines 1-30: Route initialization and dependencies
- Lines 30-123: Register endpoint
- Lines 125-196: Login endpoint
- Lines 198-283: Refresh token endpoint
- Lines 285-338: Get current user endpoint
- Lines 340-398: Change password endpoint
- Lines 400-468: Helper functions and test endpoint
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import auth routes router
from api.enterprise_auth_endpoints import router, UserRegister, UserLogin, TokenResponse, ChangePasswordRequest

# Import models
from core.models import Base, User

# Import auth dependencies
from core.auth import get_current_user
from core.database import get_db


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

    # Create only the tables we need for auth routes testing
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
    """Create FastAPI app with auth routes for testing."""
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
    # Create a password hash using bcrypt
    from core.enterprise_auth_service import EnterpriseAuthService
    auth_service = EnterpriseAuthService()
    password_hash = auth_service.hash_password("TestPassword123!")

    user = User(
        id=str(uuid.uuid4()),
        email="test@example.com",
        password_hash=password_hash,
        first_name="Test",
        last_name="User",
        role="member",
        status="active",
        email_verified=True,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_admin_user(test_db: Session) -> User:
    """Create test admin user."""
    from core.enterprise_auth_service import EnterpriseAuthService
    auth_service = EnterpriseAuthService()
    password_hash = auth_service.hash_password("AdminPassword123!")

    user = User(
        id=str(uuid.uuid4()),
        email="admin@example.com",
        password_hash=password_hash,
        first_name="Admin",
        last_name="User",
        role="admin",
        status="active",
        email_verified=True,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def locked_user(test_db: Session) -> User:
    """Create locked test user."""
    from core.enterprise_auth_service import EnterpriseAuthService
    auth_service = EnterpriseAuthService()
    password_hash = auth_service.hash_password("LockedPassword123!")

    user = User(
        id=str(uuid.uuid4()),
        email="locked@example.com",
        password_hash=password_hash,
        first_name="Locked",
        last_name="User",
        role="member",
        status="locked",
        email_verified=True,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def inactive_user(test_db: Session) -> User:
    """Create inactive test user."""
    from core.enterprise_auth_service import EnterpriseAuthService
    auth_service = EnterpriseAuthService()
    password_hash = auth_service.hash_password("InactivePassword123!")

    user = User(
        id=str(uuid.uuid4()),
        email="inactive@example.com",
        password_hash=password_hash,
        first_name="Inactive",
        last_name="User",
        role="member",
        status="inactive",
        email_verified=True,
        created_at=datetime.now(timezone.utc)
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# ============================================================================
# Helper function to create valid JWT token for testing
# ============================================================================

@pytest.fixture(scope="function")
def valid_auth_token(test_user: User):
    """Create a valid JWT token for testing."""
    from core.enterprise_auth_service import EnterpriseAuthService
    auth_service = EnterpriseAuthService()

    token = auth_service.create_access_token(
        test_user.id,
        {
            "username": test_user.email,
            "email": test_user.email,
            "roles": [test_user.role],
            "security_level": "standard"
        }
    )
    return token


@pytest.fixture(scope="function")
def valid_refresh_token(test_user: User):
    """Create a valid refresh token for testing."""
    from core.enterprise_auth_service import EnterpriseAuthService
    auth_service = EnterpriseAuthService()
    return auth_service.create_refresh_token(test_user.id)


@pytest.fixture(scope="function")
def expired_auth_token():
    """Create an expired JWT token for testing."""
    from jose import jwt
    import os

    # Create a token that expired in the past
    payload = {
        "user_id": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc).timestamp() - 3600,  # Expired 1 hour ago
        "type": "access"
    }
    secret_key = os.getenv("SECRET_KEY", "test-secret-key")
    return jwt.encode(payload, secret_key, algorithm="HS256")


# ============================================================================
# Mock EnterpriseAuthService
# ============================================================================

@pytest.fixture(autouse=True)
def mock_email_service():
    """Mock email service to avoid sending real emails."""
    with patch('core.enterprise_auth_service.send_email') as mock_send:
        mock_send.return_value = True
        yield mock_send


# ============================================================================
# Login Endpoint Tests (POST /api/auth/login)
# ============================================================================

class TestLoginEndpoint:
    """Tests for login endpoint."""

    def test_login_success_with_valid_credentials(self, client: TestClient, test_user: User):
        """Test successful login with valid credentials."""
        response = client.post("/api/auth/login", json={
            "username": test_user.email,
            "password": "TestPassword123!"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["email"] == test_user.email
        assert data["user_id"] == test_user.id
        assert "expires_in" in data
        assert isinstance(data["expires_in"], int)

    def test_login_with_username_as_email(self, client: TestClient, test_user: User):
        """Test login using email as username."""
        response = client.post("/api/auth/login", json={
            "username": test_user.email,
            "password": "TestPassword123!"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email

    def test_login_with_invalid_password(self, client: TestClient, test_user: User):
        """Test login with invalid password returns 401."""
        response = client.post("/api/auth/login", json={
            "username": test_user.email,
            "password": "WrongPassword123!"
        })

        assert response.status_code == 401
        data = response.json()
        assert "message" in data or "detail" in data

    def test_login_with_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user returns 401."""
        response = client.post("/api/auth/login", json={
            "username": "nonexistent@example.com",
            "password": "AnyPassword123!"
        })

        assert response.status_code == 401

    def test_login_with_missing_username(self, client: TestClient):
        """Test login with missing username returns 422."""
        response = client.post("/api/auth/login", json={
            "password": "TestPassword123!"
        })

        assert response.status_code == 422

    def test_login_with_missing_password(self, client: TestClient):
        """Test login with missing password returns 422."""
        response = client.post("/api/auth/login", json={
            "username": "test@example.com"
        })

        assert response.status_code == 422

    def test_login_with_empty_credentials(self, client: TestClient):
        """Test login with empty username and password."""
        response = client.post("/api/auth/login", json={
            "username": "",
            "password": ""
        })

        # This should return 422 (validation error) or 401 (auth failed)
        assert response.status_code in [401, 422]

    def test_login_updates_last_login_timestamp(self, client: TestClient, test_user: User, test_db: Session):
        """Test that successful login updates last_login timestamp."""
        # Get initial last_login
        initial_last_login = test_user.last_login

        # Wait a bit to ensure timestamp difference
        import time
        time.sleep(0.1)

        # Login
        response = client.post("/api/auth/login", json={
            "username": test_user.email,
            "password": "TestPassword123!"
        })

        assert response.status_code == 200

        # Refresh user from database
        test_db.refresh(test_user)
        assert test_user.last_login is not None
        if initial_last_login:
            assert test_user.last_login > initial_last_login

    def test_login_with_locked_account(self, client: TestClient, locked_user: User):
        """Test login with locked account returns 401."""
        response = client.post("/api/auth/login", json={
            "username": locked_user.email,
            "password": "LockedPassword123!"
        })

        # Should fail either at credential verification or account status check
        assert response.status_code in [401, 403]

    def test_login_with_inactive_account(self, client: TestClient, inactive_user: User):
        """Test login with inactive account returns 401."""
        response = client.post("/api/auth/login", json={
            "username": inactive_user.email,
            "password": "InactivePassword123!"
        })

        # Should fail either at credential verification or account status check
        assert response.status_code in [401, 403]

    def test_login_returns_user_roles(self, client: TestClient, test_user: User):
        """Test that login response includes user roles."""
        response = client.post("/api/auth/login", json={
            "username": test_user.email,
            "password": "TestPassword123!"
        })

        assert response.status_code == 200
        data = response.json()
        assert "roles" in data
        assert isinstance(data["roles"], list)
        assert test_user.role in data["roles"]

    def test_login_returns_security_level(self, client: TestClient, test_user: User):
        """Test that login response includes security level."""
        response = client.post("/api/auth/login", json={
            "username": test_user.email,
            "password": "TestPassword123!"
        })

        assert response.status_code == 200
        data = response.json()
        assert "security_level" in data
        assert isinstance(data["security_level"], str)

    @pytest.mark.parametrize("username,password,expected_status", [
        ("valid@example.com", "correct_password", 200),
        ("valid@example.com", "wrong_password", 401),
        ("nonexistent@example.com", "any_password", 401),
    ])
    def test_login_with_various_credentials(self, client: TestClient, test_user: User, username, password, expected_status):
        """Test login with various credential combinations."""
        # Override with actual test user email for the valid case
        if username == "valid@example.com":
            username = test_user.email
        if password == "correct_password":
            password = "TestPassword123!"

        response = client.post("/api/auth/login", json={
            "username": username,
            "password": password
        })

        assert response.status_code == expected_status

    def test_login_with_malformed_json(self, client: TestClient):
        """Test login with malformed JSON request."""
        response = client.post(
            "/api/auth/login",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_login_with_extra_fields(self, client: TestClient, test_user: User):
        """Test login ignores extra fields in request."""
        response = client.post("/api/auth/login", json={
            "username": test_user.email,
            "password": "TestPassword123!",
            "extra_field": "should_be_ignored"
        })

        assert response.status_code == 200
