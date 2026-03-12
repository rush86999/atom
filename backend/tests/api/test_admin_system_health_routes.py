"""
Admin System Health Routes Test Suite

Comprehensive test coverage for system health routes (admin + public health endpoints).

Target Coverage: 75%+ line coverage for:
- api/admin/system_health_routes.py (Admin system health check)
- api/health_routes.py (Public liveness, readiness, metrics endpoints)

Scope:
- Admin system health endpoint (GET /api/admin/health) with all service states
- Database health check (operational, degraded, timeout scenarios)
- Redis health check (operational, degraded, disabled, no client)
- Vector store health check (LanceDB operational, degraded, maintenance)
- Public health endpoints (liveness, readiness, metrics)
- Disk space health checks
- Database connectivity checks

Test Fixtures:
- Per-file FastAPI apps (admin_health_app, public_health_app)
- TestClient fixtures for both routers
- Mock fixtures for database, Redis, LanceDB, psutil
- Super admin authentication fixture

External Services: All mocked (no real Redis, LanceDB, or DB connections required)
"""

import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy import text

# Import routers
from api.admin.system_health_routes import router as admin_health_router
from api.health_routes import router as health_router
from core.models import Base, User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_db():
    """
    In-memory SQLite database with StaticPool for testing.

    Using StaticPool ensures the same connection is reused across the session,
    preventing database locking issues during tests.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def admin_health_app():
    """FastAPI app with admin health router for testing."""
    app = FastAPI()
    app.include_router(admin_health_router)
    return app


@pytest.fixture(scope="function")
def public_health_app():
    """FastAPI app with public health router for testing."""
    app = FastAPI()
    app.include_router(health_router)
    return app


@pytest.fixture(scope="function")
def admin_health_client(admin_health_app):
    """TestClient for admin health routes."""
    return TestClient(admin_health_app)


@pytest.fixture(scope="function")
def public_health_client(public_health_app):
    """TestClient for public health routes."""
    return TestClient(public_health_app)


@pytest.fixture(scope="function")
def super_admin_user():
    """Create a super admin user for testing authenticated endpoints."""
    user = User(
        id="test_super_admin",
        email="superadmin@test.com",
        role="super_admin",
        full_name="Test Super Admin",
        is_active=True
    )
    return user


@pytest.fixture(scope="function")
def authenticated_admin_client(admin_health_app, super_admin_user):
    """
    TestClient with super admin authentication override.

    Overrides the get_super_admin dependency to return our test super admin user.
    """
    from core.admin_endpoints import get_super_admin

    def override_get_super_admin():
        return super_admin_user

    admin_health_app.dependency_overrides[get_super_admin] = override_get_super_admin

    client = TestClient(admin_health_app)
    try:
        yield client
    finally:
        admin_health_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def mock_db():
    """Mock database for health checks."""
    mock = MagicMock(spec=Session)
    return mock


@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis client for health checks."""
    mock = MagicMock()
    mock.ping.return_value = True
    return mock


@pytest.fixture(scope="function")
def mock_lancedb():
    """Mock LanceDB handler for health checks."""
    mock = MagicMock()
    mock.test_connection.return_value = {"connected": True}
    return mock


@pytest.fixture(scope="function")
def mock_psutil():
    """Mock psutil for disk space checks."""
    mock = MagicMock()
    mock_disk = MagicMock()
    mock_disk.free = 10 * (1024 ** 3)  # 10GB free
    mock.disk_usage.return_value = mock_disk
    return mock


# ============================================================================
# Test Classes Start Here
# ============================================================================
