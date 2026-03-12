"""
Admin Skill Routes API Tests

Tests for admin skill routes (`api/admin/skill_routes.py`):
- POST /api/admin/skills - Create new standardized skill package
- Security scanning: Static analysis and optional LLM analysis
- Governance enforcement: AUTONOMOUS maturity, super_admin role required
- Error paths: 403 unauthorized, 409 policy violation, 422 validation error, 500 internal error

Coverage target: 75%+ line coverage on admin/skill_routes.py
"""

import pytest
import uuid
import os
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import admin skill routes router
from api.admin.skill_routes import router

# Import models
from core.models import Base, User


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

    # Create only the User table for admin skill routes testing
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
    """Create FastAPI app with admin skill routes for testing."""
    app = FastAPI()
    app.include_router(router)

    # Override get_db dependency
    from core.database import get_db

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
def super_admin_user(test_db: Session) -> User:
    """Create super admin user for authorization tests."""
    user = User(
        id=str(uuid.uuid4()),
        email="superadmin@test.com",
        first_name="Super",
        last_name="Admin",
        name="Super Admin",
        role="super_admin",
        status="active",
        email_verified=True,
        tenant_id="test_tenant"
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def regular_user(test_db: Session) -> User:
    """Create regular user for authentication testing."""
    user = User(
        id=str(uuid.uuid4()),
        email="member@test.com",
        first_name="Regular",
        last_name="Member",
        name="Regular Member",
        role="member",
        status="active",
        email_verified=True,
        tenant_id="test_tenant"
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def authenticated_admin_client(client: TestClient, super_admin_user: User):
    """Create authenticated TestClient with super admin user."""
    from core.admin_endpoints import get_super_admin

    def override_get_super_admin():
        return super_admin_user

    client.app.dependency_overrides[get_super_admin] = override_get_super_admin
    yield client
    client.app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def unauthenticated_client(client: TestClient):
    """Create unauthenticated TestClient (no auth override)."""
    yield client


@pytest.fixture(scope="function")
def mock_static_analyzer():
    """Create MagicMock for StaticAnalyzer with configurable findings."""
    from atom_security.analyzers.static import StaticAnalyzer

    mock = MagicMock(spec=StaticAnalyzer)

    # Default: no findings (scan passes)
    mock.scan_content.return_value = []

    return mock


@pytest.fixture(scope="function")
def mock_skill_builder():
    """Create AsyncMock for skill_builder_service with deterministic return values."""
    mock = AsyncMock()

    # Default: successful skill creation
    mock.create_skill_package.return_value = {
        "success": True,
        "message": "Skill package created successfully",
        "skill_path": "/tmp/skills/test_skill",
        "metadata": {
            "name": "test_skill",
            "description": "Test skill",
            "version": "1.0.0"
        }
    }

    return mock


@pytest.fixture(scope="function")
def inactive_admin_user(test_db: Session) -> User:
    """Create inactive super admin user for testing."""
    user = User(
        id=str(uuid.uuid4()),
        email="inactive_admin@test.com",
        first_name="Inactive",
        last_name="Admin",
        name="Inactive Admin",
        role="super_admin",
        status="inactive",
        email_verified=True,
        tenant_id="test_tenant"
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user
