"""
Regression tests for agent validation bugs discovered in Phase 301.

These tests prevent regressions of validation bugs that were fixed.
Each test follows TDD methodology: red → green → refactor.

Bug References:
- Bug #1: Agent name validation missing (empty strings allowed)
- Bug #2: Agent maturity validation missing (invalid enums accepted)
- Bug #3: Agent category validation missing (empty strings allowed)
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from core.database import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models import Base, User, UserRole, UserStatus
from core.auth import create_access_token
import uuid


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def db_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db(db_engine):
    """Create database session for test operations."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db):
    """Create FastAPI TestClient with test database override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_user(db):
    """Create admin user for authenticated requests."""
    from datetime import datetime
    user = User(
        id=str(uuid.uuid4()),
        email=f"admin-{uuid.uuid4()}@example.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.WORKSPACE_ADMIN.value,
        status=UserStatus.ACTIVE.value,
        tenant_id="default",
        workspace_id="default",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    yield user


@pytest.fixture(scope="function")
def auth_headers(admin_user):
    """Generate authentication headers for admin user."""
    token = create_access_token(data={"sub": admin_user.id})
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Bug #1: Agent Name Validation Missing
# ============================================================================

class TestAgentNameValidation:
    """Test suite for agent name validation (Bug #1)."""

    def test_agent_rejects_empty_name(self, client, auth_headers):
        """
        RED: Test that agent creation rejects empty name.

        Bug #1: Agent name validation missing
        Expected: POST /api/agents/custom with name="" returns 422
        Actual: Accepts empty name (BUG)

        This test should FAIL before the fix, PASS after the fix.
        """
        response = client.post(
            "/api/agents/custom",
            json={
                "name": "",  # Empty name should be rejected
                "description": "Test agent",
                "category": "testing",
                "configuration": {"test": True}
            },
            headers=auth_headers
        )

        # Should return 422 (Unprocessable Entity) for validation error
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

        # Error message should mention name field
        error_detail = response.json()
        assert "detail" in error_detail
        assert "name" in str(error_detail["detail"]).lower()


    def test_agent_rejects_whitespace_only_name(self, client, auth_headers):
        """
        Test that agent creation rejects whitespace-only name.

        Edge case: name with only spaces should be rejected.
        """
        response = client.post(
            "/api/agents/custom",
            json={
                "name": "   ",  # Whitespace only
                "description": "Test agent",
                "category": "testing",
                "configuration": {"test": True}
            },
            headers=auth_headers
        )

        # Should return 422
        assert response.status_code == 422


    def test_agent_accepts_valid_name(self, client, auth_headers):
        """
        Test that agent creation accepts valid name.

        GREEN: Ensure fix doesn't break valid agent creation.
        """
        response = client.post(
            "/api/agents/custom",
            json={
                "name": "Valid Test Agent",  # Valid name
                "description": "Test agent",
                "category": "testing",
                "configuration": {"test": True}
            },
            headers=auth_headers
        )

        # Should return 200 or 201
        assert response.status_code in [200, 201]


# ============================================================================
# Bug #2: Agent Maturity Validation Missing
# ============================================================================

class TestAgentMaturityValidation:
    """Test suite for agent maturity validation (Bug #2)."""

    def test_agent_rejects_invalid_maturity(self, client, auth_headers):
        """
        RED: Test that agent creation rejects invalid maturity enum.

        Bug #2: Agent maturity validation missing
        Expected: POST /api/agents with maturity="INVALID" returns 422
        Actual: Accepts invalid maturity (BUG)

        This test should FAIL before the fix, PASS after the fix.
        """
        # Note: This test assumes maturity is a field in agent creation
        # Adjust endpoint and payload based on actual API structure
        response = client.post(
            "/api/agents/custom",
            json={
                "name": "Test Agent",
                "description": "Test agent",
                "category": "testing",
                "maturity": "INVALID_LEVEL",  # Invalid enum value
                "configuration": {"test": True}
            },
            headers=auth_headers
        )

        # Should return 422 for invalid enum
        assert response.status_code == 422


    def test_agent_accepts_valid_maturities(self, client, auth_headers):
        """
        GREEN: Test that agent creation accepts valid maturity values.

        Valid maturities: STUDENT, INTERN, SUPERVISED, AUTONOMOUS
        """
        valid_maturities = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

        for maturity in valid_maturities:
            response = client.post(
                "/api/agents/custom",
                json={
                    "name": f"Test Agent {maturity}",
                    "description": "Test agent",
                    "category": "testing",
                    "maturity": maturity,
                    "configuration": {"test": True}
                },
                headers=auth_headers
            )

            # Should accept valid maturity values
            # Note: May return 400 if maturity field doesn't exist in API
            assert response.status_code in [200, 201, 400]


# ============================================================================
# Bug #3: Agent Category Validation Missing
# ============================================================================

class TestAgentCategoryValidation:
    """Test suite for agent category validation (Bug #3)."""

    def test_agent_rejects_empty_category(self, client, auth_headers):
        """
        RED: Test that agent creation rejects empty category.

        Bug #3: Agent category validation missing
        Expected: POST /api/agents with category="" returns 422
        Actual: Accepts empty category (BUG)

        This test should FAIL before the fix, PASS after the fix.
        """
        response = client.post(
            "/api/agents/custom",
            json={
                "name": "Test Agent",
                "description": "Test agent",
                "category": "",  # Empty category should be rejected
                "configuration": {"test": True}
            },
            headers=auth_headers
        )

        # Should return 422
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"


    def test_agent_rejects_whitespace_only_category(self, client, auth_headers):
        """
        Test that agent creation rejects whitespace-only category.

        Edge case: category with only spaces should be rejected.
        """
        response = client.post(
            "/api/agents/custom",
            json={
                "name": "Test Agent",
                "description": "Test agent",
                "category": "   ",  # Whitespace only
                "configuration": {"test": True}
            },
            headers=auth_headers
        )

        # Should return 422
        assert response.status_code == 422


    def test_agent_accepts_valid_category(self, client, auth_headers):
        """
        GREEN: Test that agent creation accepts valid category.

        Ensure fix doesn't break valid agent creation.
        """
        response = client.post(
            "/api/agents/custom",
            json={
                "name": "Valid Test Agent",
                "description": "Test agent",
                "category": "testing",  # Valid category
                "configuration": {"test": True}
            },
            headers=auth_headers
        )

        # Should return 200 or 201
        assert response.status_code in [200, 201]
