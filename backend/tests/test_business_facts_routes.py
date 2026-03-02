"""
Business Facts Admin Routes Tests

Tests for business facts CRUD API endpoints with JIT citation support.

Coverage Target: 60%+ for api/admin/business_facts_routes.py

Routes Covered:
- GET /api/admin/governance/facts - List all facts
- POST /api/admin/governance/facts - Create new fact
- GET /api/admin/governance/facts/{id} - Get specific fact

Note: Due to core.security.rbac syntax errors, auth is mocked at import level.
This will be fixed in a future plan.

Reference: Phase 121-01 test_health_routes.py patterns
"""

import os
os.environ["TESTING"] = "1"

import sys
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from fastapi import status

# Mock core.security.rbac before any imports that might use it
sys.modules['core.security.rbac'] = MagicMock()
sys.modules['core.security.rbac'].require_role = lambda role: lambda: None

from main_api_app import app
from core.database import get_db, SessionLocal
from core.models import User, UserRole
from core.auth import get_current_user


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def db_session():
    """Create a test database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing."""
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"admin-{user_id}@test.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN.value,
        tenant_id="default",
        status="active",
        email_verified=True,
        onboarding_completed=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client_with_admin_auth(client, admin_user):
    """Create a test client with admin authentication overrides."""
    def override_get_current_user():
        return admin_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_world_model_service():
    """Mock WorldModelService for testing."""
    mock_wm = AsyncMock()
    return mock_wm


# ============================================================================
# TEST CLASSES
# ============================================================================

class TestListFacts:
    """Tests for GET /api/admin/governance/facts endpoint."""

    def test_list_facts_returns_empty_list_initially(
        self, client_with_admin_auth, mock_world_model_service
    ):
        """
        GIVEN admin user is authenticated
        WHEN GET /api/admin/governance/facts is called
        THEN return 200 with empty list
        """
        # Mock list_all_facts to return empty list
        mock_world_model_service.list_all_facts.return_value = []

        # Patch at the import location in business_facts_routes
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_world_model_service):
            response = client_with_admin_auth.get("/api/admin/governance/facts")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 0
            mock_world_model_service.list_all_facts.assert_called_once_with(
                status=None, domain=None, limit=100
            )


class TestCreateFact:
    """Tests for POST /api/admin/governance/facts endpoint."""

    def test_create_fact_success(
        self, client_with_admin_auth, mock_world_model_service
    ):
        """
        GIVEN admin user is authenticated
        WHEN POST /api/admin/governance/facts with valid fact data
        THEN return 201 with created fact details
        """
        # Mock record_business_fact to return True
        mock_world_model_service.record_business_fact.return_value = True

        # Patch at the import location in business_facts_routes
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_world_model_service):
            fact_data = {
                "fact": "Invoices > $500 need VP approval",
                "citations": ["policy.pdf:p4"],
                "reason": "Financial control policy",
                "domain": "finance"
            }

            response = client_with_admin_auth.post(
                "/api/admin/governance/facts",
                json=fact_data
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["fact"] == "Invoices > $500 need VP approval"
            assert data["citations"] == ["policy.pdf:p4"]
            assert data["reason"] == "Financial control policy"
            assert data["domain"] == "finance"
            assert data["verification_status"] == "verified"
            assert "id" in data
            assert "created_at" in data

            # Verify WorldModelService.record_business_fact was called
            mock_world_model_service.record_business_fact.assert_called_once()
            call_args = mock_world_model_service.record_business_fact.call_args[0][0]
            assert call_args.fact == "Invoices > $500 need VP approval"
            assert call_args.citations == ["policy.pdf:p4"]


class TestGetFact:
    """Tests for GET /api/admin/governance/facts/{id} endpoint."""

    def test_get_fact_by_id(
        self, client_with_admin_auth, mock_world_model_service
    ):
        """
        GIVEN admin user is authenticated and fact exists
        WHEN GET /api/admin/governance/facts/{id} is called
        THEN return 200 with fact details
        """
        from core.agent_world_model import BusinessFact

        # Mock BusinessFact
        fact_id = str(uuid.uuid4())
        mock_fact = BusinessFact(
            id=fact_id,
            fact="Invoices > $500 need VP approval",
            citations=["policy.pdf:p4"],
            reason="Financial control policy",
            source_agent_id="user:test-user",
            created_at=datetime.now(),
            last_verified=datetime.now(),
            verification_status="verified",
            metadata={"domain": "finance"}
        )

        mock_world_model_service.get_fact_by_id.return_value = mock_fact

        # Patch at the import location in business_facts_routes
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_world_model_service):
            response = client_with_admin_auth.get(f"/api/admin/governance/facts/{fact_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == fact_id
            assert data["fact"] == "Invoices > $500 need VP approval"
            assert data["citations"] == ["policy.pdf:p4"]
            assert data["domain"] == "finance"
            assert data["verification_status"] == "verified"

            mock_world_model_service.get_fact_by_id.assert_called_once_with(fact_id)
