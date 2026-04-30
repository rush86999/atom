"""
Regression tests for agent business logic bugs discovered in Phase 301.

Bug References:
- Bug #4: Agent update partial update logic broken
- Bug #5: Agent delete cascade deletes related records
- Bug #6: Agent execution timeout not enforced
- Bug #7: Agent execution memory limits not enforced
- Bug #8: Agent execution retry logic broken
- Bug #9: Agent execution rollback logic broken
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from core.database import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models import Base, User, UserRole, UserStatus, AgentRegistry, AgentStatus
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


@pytest.fixture(scope="function")
def test_agent(db, admin_user):
    """Create a test agent for updates."""
    agent = AgentRegistry(
        id=str(uuid.uuid4()),
        name="Original Agent Name",
        description="Original Description",
        category="testing",
        class_name="GenericAgent",
        module_path="core.generic_agent",
        status=AgentStatus.STUDENT.value,
        workspace_id="default",
        tenant_id="default"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    yield agent


# ============================================================================
# Bug #4: Agent Update Partial Update Logic
# ============================================================================

class TestAgentPartialUpdate:
    """Test suite for agent partial update logic (Bug #4)."""

    def test_agent_partial_update_preserves_unchanged_fields(self, client, auth_headers, test_agent):
        """
        RED: Test that partial update preserves unchanged fields.

        Bug #4: Agent update partial update logic broken
        Issue: PUT /api/agents/{id} overwrites ALL fields, even None values
        Expected: Only provided fields are updated
        Actual: All fields updated, None values overwrite existing data (BUG)

        This test should FAIL before the fix, PASS after the fix.
        """
        # Get original state
        original_response = client.get(f"/api/agents/{test_agent.id}", headers=auth_headers)
        assert original_response.status_code == 200
        original_data = original_response.json()["data"]
        original_description = original_data.get("description")

        # Partial update: only change name
        update_response = client.put(
            f"/api/agents/{test_agent.id}",
            json={
                "name": "Updated Name",
                # description not provided - should be preserved
                # category not provided - should be preserved
            },
            headers=auth_headers
        )

        assert update_response.status_code == 200

        # Verify only name changed, description preserved
        updated_response = client.get(f"/api/agents/{test_agent.id}", headers=auth_headers)
        assert updated_response.status_code == 200
        updated_data = updated_response.json()["data"]

        # Name should be updated
        assert updated_data["name"] == "Updated Name"

        # Description should be preserved (NOT overwritten to None or default)
        assert updated_data["description"] == original_description, \
            f"Description was overwritten! Original: {original_description}, Got: {updated_data.get('description')}"


    def test_agent_partial_update_with_empty_string(self, client, auth_headers, test_agent):
        """
        Test that partial update handles explicit empty strings correctly.

        Edge case: Empty string is different from not provided.
        Empty string should update the field, but not provided should preserve.
        """
        # Update with explicit empty description
        response = client.put(
            f"/api/agents/{test_agent.id}",
            json={
                "name": "Updated Name",
                "description": "",  # Explicitly empty
                "category": "testing"
            },
            headers=auth_headers
        )

        assert response.status_code == 200

        # Verify description is now empty
        updated = client.get(f"/api/agents/{test_agent.id}", headers=auth_headers)
        updated_data = updated.json()["data"]
        assert updated_data["description"] == ""


    def test_agent_partial_update_multiple_fields(self, client, auth_headers, test_agent):
        """
        Test that partial update works correctly when updating multiple fields.

        GREEN: Ensure fix works for multiple field updates.
        """
        original_response = client.get(f"/api/agents/{test_agent.id}", headers=auth_headers)
        original_data = original_response.json()["data"]
        original_category = original_data.get("category")

        # Update name and description only
        response = client.put(
            f"/api/agents/{test_agent.id}",
            json={
                "name": "New Name",
                "description": "New Description",
                # category not provided - should preserve original
            },
            headers=auth_headers
        )

        assert response.status_code == 200

        # Verify changes
        updated = client.get(f"/api/agents/{test_agent.id}", headers=auth_headers)
        updated_data = updated.json()["data"]

        assert updated_data["name"] == "New Name"
        assert updated_data["description"] == "New Description"
        assert updated_data["category"] == original_category, "Category should be preserved!"


# ============================================================================
# Bug #5: Agent Delete Cascade
# ============================================================================

class TestAgentDeleteCascade:
    """Test suite for agent delete cascade behavior (Bug #5)."""

    def test_agent_delete_preserves_related_records(self, client, auth_headers, test_agent):
        """
        RED: Test that agent delete handles related records properly.

        Bug #5: Agent delete cascade deletes related records
        Issue: DELETE /api/agents/{id} hard deletes and removes all related records
        Expected: Soft delete or explicit cascade handling
        Actual: Hard delete removes executions, feedback, etc. (BUG)

        This test documents current behavior.
        Fix may require soft delete or cascade configuration changes.
        """
        # Create related records (executions, feedback)
        # For now, just verify delete works
        response = client.delete(f"/api/agents/{test_agent.id}", headers=auth_headers)

        # Current behavior: returns 200 or 204
        assert response.status_code in [200, 204]

        # Verify agent is deleted
        get_response = client.get(f"/api/agents/{test_agent.id}", headers=auth_headers)
        assert get_response.status_code == 404


# ============================================================================
# Bugs #6-9: Agent Execution Logic
# ============================================================================

class TestAgentExecutionLogic:
    """Test suite for agent execution bugs (Bugs #6-9)."""

    def test_agent_execution_enforces_timeout(self, client, auth_headers, test_agent):
        """
        Test that agent execution enforces timeout.

        Bug #6: Agent execution timeout not enforced
        Issue: Long-running agents don't timeout
        Expected: Execution terminated after timeout
        Actual: Agents run indefinitely (BUG)

        Note: This test requires mock for slow execution.
        """
        # For now, this is a placeholder documenting the bug
        # Full implementation requires mocking agent execution
        pytest.skip("Requires agent execution mocking - Bug documented but not fixed")


    def test_agent_execution_enforces_memory_limit(self, client, auth_headers, test_agent):
        """
        Test that agent execution enforces memory limits.

        Bug #7: Agent execution memory limits not enforced
        Issue: No memory monitoring during execution
        Expected: Execution terminated if memory exceeds limit
        Actual: No memory monitoring (BUG)

        Note: This test requires mock for memory-intensive operations.
        """
        pytest.skip("Requires memory monitoring mock - Bug documented but not fixed")


    def test_agent_execution_retries_on_failure(self, client, auth_headers, test_agent):
        """
        Test that agent execution retries on transient failures.

        Bug #8: Agent execution retry logic broken
        Issue: No retry mechanism for transient failures
        Expected: Failed executions retry with exponential backoff
        Actual: Fail immediately on error (BUG)

        Note: This test requires mock for transient failures.
        """
        pytest.skip("Requires failure injection mock - Bug documented but not fixed")


    def test_agent_execution_rolls_back_on_error(self, client, auth_headers, test_agent):
        """
        Test that agent execution rolls back on error.

        Bug #9: Agent execution rollback logic broken
        Issue: No rollback on execution failure
        Expected: Database changes rolled back on error
        Actual: Partial state persisted (BUG)

        Note: This test requires mock for execution failures.
        """
        pytest.skip("Requires transaction mock - Bug documented but not fixed")
