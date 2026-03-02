"""
Business Facts Admin Routes Tests

Tests for business facts CRUD API endpoints with JIT citation support.

Coverage Target: 60%+ for api/admin/business_facts_routes.py

Routes Covered:
- GET /api/admin/governance/facts - List all facts
- POST /api/admin/governance/facts - Create new fact
- GET /api/admin/governance/facts/{id} - Get specific fact
- PUT /api/admin/governance/facts/{id} - Update fact
- DELETE /api/admin/governance/facts/{id} - Delete fact
- POST /api/admin/governance/facts/upload - Upload and extract
- POST /api/admin/governance/facts/{id}/verify-citation - Verify citations

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


class TestUpdateFact:
    """Tests for PUT /api/admin/governance/facts/{fact_id} endpoint."""

    @patch('api.admin.business_facts_routes.WorldModelService')
    def test_update_fact_not_found(self, mock_wm_class, client_with_admin_auth):
        """
        GIVEN fact does not exist
        WHEN PUT /api/admin/governance/facts/{fact_id} with update data
        THEN return 404 with not found error
        """
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id.return_value = None
        mock_wm_class.return_value = mock_wm

        response = client_with_admin_auth.put(
            "/api/admin/governance/facts/nonexistent-id",
            json={"fact": "Updated fact text"}
        )

        assert response.status_code == 404


class TestDeleteFact:
    """Tests for DELETE /api/admin/governance/facts/{fact_id} endpoint."""

    @patch('api.admin.business_facts_routes.WorldModelService')
    def test_delete_fact_not_found(self, mock_wm_class, client_with_admin_auth):
        """
        GIVEN fact does not exist
        WHEN DELETE /api/admin/governance/facts/{fact_id}
        THEN return 404 with not found error
        """
        mock_wm = AsyncMock()
        mock_wm.delete_fact.return_value = False
        mock_wm_class.return_value = mock_wm

        response = client_with_admin_auth.delete(
            "/api/admin/governance/facts/nonexistent-id"
        )

        assert response.status_code == 404


class TestUploadAndExtract:
    """Tests for POST /api/admin/governance/facts/upload endpoint."""

    def test_upload_unsupported_file_type(self, client_with_admin_auth):
        """
        GIVEN file with unsupported extension
        WHEN POST /api/admin/governance/facts/upload with .exe file
        THEN return 400 with validation error
        """
        files = {"file": ("test.exe", b"fake exe content", "application/x-msdownload")}
        data = {"domain": "general"}

        response = client_with_admin_auth.post(
            "/api/admin/governance/facts/upload",
            files=files,
            data=data
        )

        assert response.status_code == 400
        # Error response contains the error message
        assert "Unsupported file type" in str(response.json())

    @patch('core.policy_fact_extractor.get_policy_fact_extractor')
    @patch('core.storage.get_storage_service')
    @patch('api.admin.business_facts_routes.WorldModelService')
    def test_upload_extraction_failure(
        self, mock_wm_class, mock_storage_class, mock_extractor_class, client_with_admin_auth
    ):
        """
        GIVEN fact extraction raises exception
        WHEN POST /api/admin/governance/facts/upload with valid file
        THEN return 500 with internal error
        """
        import io

        # Mock storage
        mock_storage = Mock()
        mock_storage.upload_file.return_value = "s3://bucket/key/file.pdf"
        mock_storage_class.return_value = mock_storage

        # Mock extractor to raise exception
        mock_extractor = AsyncMock()
        # The actual method that gets called
        mock_extractor.extract_facts_from_document.side_effect = Exception("Extraction failed")
        mock_extractor_class.return_value = mock_extractor

        # Mock world model
        mock_wm = AsyncMock()
        mock_wm.bulk_record_facts.return_value = 1
        mock_wm_class.return_value = mock_wm

        files = {"file": ("test.pdf", b"fake pdf content", "application/pdf")}
        data = {"domain": "general"}

        response = client_with_admin_auth.post(
            "/api/admin/governance/facts/upload",
            files=files,
            data=data
        )

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert "Failed to extract facts" in data["error"]["message"]


class TestVerifyCitation:
    """Tests for POST /api/admin/governance/facts/{fact_id}/verify-citation endpoint."""

    @patch('api.admin.business_facts_routes.WorldModelService')
    def test_verify_citation_fact_not_found(self, mock_wm_class, client_with_admin_auth):
        """
        GIVEN fact does not exist
        WHEN POST /api/admin/governance/facts/{fact_id}/verify-citation
        THEN return 404 with not found error
        """
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id.return_value = None
        mock_wm_class.return_value = mock_wm

        response = client_with_admin_auth.post(
            "/api/admin/governance/facts/nonexistent-id/verify-citation"
        )

        assert response.status_code == 404
