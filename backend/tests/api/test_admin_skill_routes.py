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


# ============================================================================
# POST /api/admin/skills - Success Path Tests
# ============================================================================

class TestAdminSkillRoutesSuccess:
    """Tests for successful skill creation via admin skill routes."""

    def test_create_skill_success(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: AsyncMock
    ):
        """Test successful skill creation with valid request."""
        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills",
                    json={
                        "name": "test_skill",
                        "description": "A test skill for coverage",
                        "instructions": "You are a helpful assistant",
                        "capabilities": ["web_search", "data_analysis"],
                        "scripts": {
                            "main.py": "def main():\n    pass",
                            "utils.py": "def helper():\n    pass"
                        }
                    }
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["success"] is True
        assert "skill_path" in data["data"]
        assert "message" in data

    def test_create_skill_with_all_fields(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: AsyncMock
    ):
        """Test skill creation with all optional fields populated."""
        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills",
                    json={
                        "name": "advanced_skill",
                        "description": "An advanced skill with all fields",
                        "instructions": "You are an advanced assistant",
                        "capabilities": [
                            "web_search",
                            "data_analysis",
                            "file_operations",
                            "api_calls"
                        ],
                        "scripts": {
                            "main.py": "def main():\n    pass",
                            "utils.py": "def helper():\n    pass",
                            "config.py": "CONFIG = {}"
                        }
                    }
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify skill builder was called with correct parameters
        mock_skill_builder.create_skill_package.assert_called_once()
        call_args = mock_skill_builder.create_skill_package.call_args
        assert call_args[1]["metadata"].capabilities == [
            "web_search",
            "data_analysis",
            "file_operations",
            "api_calls"
        ]

    def test_create_skill_tenant_id_from_admin(
        self,
        authenticated_admin_client: TestClient,
        super_admin_user: User,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: AsyncMock
    ):
        """Test that tenant_id is extracted from admin user."""
        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills",
                    json={
                        "name": "tenant_skill",
                        "description": "Skill for specific tenant",
                        "instructions": "You are a tenant-specific assistant",
                        "scripts": {"main.py": "def main():\n    pass"}
                    }
                )

        assert response.status_code == 200

        # Verify tenant_id was passed to skill builder
        mock_skill_builder.create_skill_package.assert_called_once()
        call_args = mock_skill_builder.create_skill_package.call_args
        assert call_args[1]["tenant_id"] == super_admin_user.tenant_id

    def test_create_skill_default_author(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: AsyncMock
    ):
        """Test that author defaults to admin email."""
        with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
            with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                response = authenticated_admin_client.post(
                    "/api/admin/skills",
                    json={
                        "name": "author_skill",
                        "description": "Skill to test author default",
                        "instructions": "You are an assistant",
                        "scripts": {"main.py": "def main():\n    pass"}
                    }
                )

        assert response.status_code == 200

        # Verify author was set from admin email
        mock_skill_builder.create_skill_package.assert_called_once()
        call_args = mock_skill_builder.create_skill_package.call_args
        assert call_args[1]["metadata"].author == "superadmin@test.com"

    def test_create_skill_without_llm_scan(
        self,
        authenticated_admin_client: TestClient,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: AsyncMock
    ):
        """Test skill creation when LLM scan is disabled."""
        # Ensure LLM scan is disabled
        original_env = os.environ.get("ATOM_SECURITY_ENABLE_LLM_SCAN")
        os.environ["ATOM_SECURITY_ENABLE_LLM_SCAN"] = "false"

        try:
            with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
                with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                    response = authenticated_admin_client.post(
                        "/api/admin/skills",
                        json={
                            "name": "no_llm_skill",
                            "description": "Skill without LLM scan",
                            "instructions": "You are an assistant",
                            "scripts": {"main.py": "def main():\n    pass"}
                        }
                    )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            # Restore original environment
            if original_env is not None:
                os.environ["ATOM_SECURITY_ENABLE_LLM_SCAN"] = original_env
            else:
                os.environ.pop("ATOM_SECURITY_ENABLE_LLM_SCAN", None)


# ============================================================================
# POST /api/admin/skills - Authentication & Authorization Tests
# ============================================================================

class TestAdminSkillRoutesAuth:
    """Tests for authentication and authorization on admin skill routes."""

    def test_create_skill_requires_super_admin(
        self,
        client: TestClient,
        regular_user: User,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: AsyncMock
    ):
        """Test that non-super_admin cannot create skills."""
        from core.admin_endpoints import get_super_admin

        def override_get_super_admin():
            return regular_user  # Regular user, not super_admin

        client.app.dependency_overrides[get_super_admin] = override_get_super_admin

        try:
            with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
                with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                    response = client.post(
                        "/api/admin/skills",
                        json={
                            "name": "unauthorized_skill",
                            "description": "Should fail",
                            "instructions": "You are an assistant",
                            "scripts": {"main.py": "def main():\n    pass"}
                        }
                    )

            # Should return 403 because regular_user is not super_admin
            assert response.status_code == 403
        finally:
            client.app.dependency_overrides.clear()

    def test_create_skill_unauthenticated(
        self,
        unauthenticated_client: TestClient
    ):
        """Test that unauthenticated request fails."""
        response = unauthenticated_client.post(
            "/api/admin/skills",
            json={
                "name": "unauth_skill",
                "description": "Should fail",
                "instructions": "You are an assistant",
                "scripts": {"main.py": "def main():\n    pass"}
            }
        )

        # Should return 401 because no authentication provided
        assert response.status_code == 401

    def test_create_skill_inactive_admin(
        self,
        client: TestClient,
        inactive_admin_user: User,
        mock_static_analyzer: MagicMock,
        mock_skill_builder: AsyncMock
    ):
        """Test that inactive admin cannot create skills."""
        from core.admin_endpoints import get_super_admin

        def override_get_super_admin():
            return inactive_admin_user  # Inactive super_admin

        client.app.dependency_overrides[get_super_admin] = override_get_super_admin

        try:
            with patch('api.admin.skill_routes.StaticAnalyzer', return_value=mock_static_analyzer):
                with patch('api.admin.skill_routes.skill_builder_service', mock_skill_builder):
                    response = client.post(
                        "/api/admin/skills",
                        json={
                            "name": "inactive_skill",
                            "description": "Should fail",
                            "instructions": "You are an assistant",
                            "scripts": {"main.py": "def main():\n    pass"}
                        }
                    )

            # Should return 401 or 403 because admin is inactive
            # The exact behavior depends on get_super_admin implementation
            assert response.status_code in [401, 403]
        finally:
            client.app.dependency_overrides.clear()

    def test_get_super_admin_dependency(
        self,
        client: TestClient,
        super_admin_user: User,
        regular_user: User
    ):
        """Test get_super_admin dependency directly."""
        from core.admin_endpoints import get_super_admin

        # Test 1: super_admin role should pass
        client.app.dependency_overrides[get_super_admin] = lambda: super_admin_user
        try:
            result = get_super_admin(user=super_admin_user)
            assert result == super_admin_user
        finally:
            client.app.dependency_overrides.clear()

        # Test 2: non-super_admin role should raise HTTPException
        client.app.dependency_overrides[get_super_admin] = lambda: regular_user
        try:
            with pytest.raises(Exception) as exc_info:
                result = get_super_admin(user=regular_user)
            # Should raise HTTPException with 403 status
            assert exc_info.value.status_code == 403
        finally:
            client.app.dependency_overrides.clear()
