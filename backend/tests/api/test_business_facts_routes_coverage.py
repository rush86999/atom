"""
Coverage-driven tests for business_facts_routes.py (0% -> 70%+ target)

This test file focuses on achieving comprehensive coverage of BusinessFactsRoutes API endpoints
including fact CRUD operations, citation verification, JIT fact provisioning, and access control.

Coverage Target: 70%+ on api/admin/business_facts_routes.py (407 lines)
Test Strategy: TestClient-based testing with proper mocking and parametrized tests
"""

import pytest
import uuid
import io
import os
import tempfile
from datetime import datetime, timezone
from typing import List
from unittest.mock import MagicMock, AsyncMock, patch, Mock
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Define UserRole enum first
class UserRole(str):
    ADMIN = "admin"
    MEMBER = "member"
    SUPER_ADMIN = "super_admin"

# Mock the problematic models import before importing router
import sys
mock_models = MagicMock()
mock_models.UserRole = UserRole
sys.modules['core.models'] = mock_models

# Import business facts routes router
from api.admin.business_facts_routes import router, FactResponse, FactCreateRequest, FactUpdateRequest

# Import BusinessFact from agent_world_model
from core.agent_world_model import BusinessFact


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

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    yield db

    # Cleanup
    db.close()


@pytest.fixture(scope="function")
def test_app(test_db: Session):
    """Create FastAPI app with business facts routes for testing."""
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
def test_client(test_app):
    """FastAPI TestClient instance."""
    return TestClient(test_app)


@pytest.fixture(scope="function")
def admin_user():
    """Admin user mock."""
    user = MagicMock()
    user.id = str(uuid.uuid4())
    user.role = UserRole.ADMIN
    user.workspace_id = "default"
    return user


@pytest.fixture(scope="function")
def regular_user():
    """Regular user mock."""
    user = MagicMock()
    user.id = str(uuid.uuid4())
    user.role = UserRole.MEMBER
    user.workspace_id = "default"
    return user


@pytest.fixture(scope="function")
def admin_headers(admin_user):
    """Admin authentication headers."""
    return {"Authorization": f"Bearer admin_token_{admin_user.id}"}


@pytest.fixture(scope="function")
def user_headers(regular_user):
    """Regular user authentication headers."""
    return {"Authorization": f"Bearer user_token_{regular_user.id}"}


@pytest.fixture(scope="function")
def mock_fact():
    """Mock BusinessFact object."""
    fact_id = str(uuid.uuid4())
    fact = BusinessFact(
        id=fact_id,
        fact="Invoices > $500 need VP approval",
        citations=["policy.pdf:p4"],
        reason="Company policy requires VP approval for large invoices",
        source_agent_id=f"user:{uuid.uuid4()}",
        created_at=datetime.now(timezone.utc),
        last_verified=datetime.now(timezone.utc),
        verification_status="verified",
        metadata={"domain": "accounting"}
    )
    return fact


# ============================================================================
# TestBusinessFactsRoutesCoverage - Main Test Class
# ============================================================================

class TestBusinessFactsRoutesCoverage:
    """Coverage-driven tests for business_facts_routes.py

    Target: 70%+ line coverage on business_facts_routes.py (407 lines)
    Focus areas:
    - Lines 66-228: Fact CRUD endpoints (GET, POST, PUT, DELETE)
    - Lines 231-334: Document upload and fact extraction
    - Lines 336-407: Citation verification
    """

    # -------------------------------------------------------------------------
    # Fact Listing Tests (Lines 66-95)
    # -------------------------------------------------------------------------

    def test_list_facts_empty(self, test_client, admin_headers):
        """Cover list_facts with empty result (lines 77-95)"""
        mock_wm = AsyncMock()
        mock_wm.list_all_facts = AsyncMock(return_value=[])
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.get("/api/admin/governance/facts", headers=admin_headers)
            assert response.status_code == 200
            assert response.json() == []

    def test_list_facts_with_data(self, test_client, admin_headers, mock_fact):
        """Cover list_facts with data (lines 77-95)"""
        mock_wm = AsyncMock()
        mock_wm.list_all_facts = AsyncMock(return_value=[mock_fact])
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.get("/api/admin/governance/facts", headers=admin_headers)
            assert response.status_code == 200
            facts = response.json()
            assert len(facts) == 1
            assert facts[0]["fact"] == mock_fact.fact

    def test_list_facts_filters_deleted(self, test_client, admin_headers, mock_fact):
        """Cover list_facts filtering out deleted facts (line 94)"""
        deleted_fact = BusinessFact(
            id=str(uuid.uuid4()),
            fact="Deleted fact",
            citations=[],
            reason="",
            source_agent_id="user:test",
            created_at=datetime.now(timezone.utc),
            last_verified=datetime.now(timezone.utc),
            verification_status="deleted",
            metadata={}
        )

        mock_wm = AsyncMock()
        mock_wm.list_all_facts = AsyncMock(return_value=[mock_fact, deleted_fact])
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.get("/api/admin/governance/facts", headers=admin_headers)
            assert response.status_code == 200
            facts = response.json()
            assert len(facts) == 1
            assert facts[0]["verification_status"] != "deleted"

    def test_list_facts_with_status_filter(self, test_client, admin_headers, mock_fact):
        """Cover list_facts with status parameter (line 68, 81)"""
        mock_wm = AsyncMock()
        mock_wm.list_all_facts = AsyncMock(return_value=[mock_fact])
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.get("/api/admin/governance/facts?status=verified", headers=admin_headers)
            assert response.status_code == 200
            mock_wm.list_all_facts.assert_called_with(status="verified", domain=None, limit=100)

    def test_list_facts_with_domain_filter(self, test_client, admin_headers, mock_fact):
        """Cover list_facts with domain parameter (line 69, 81)"""
        mock_wm = AsyncMock()
        mock_wm.list_all_facts = AsyncMock(return_value=[mock_fact])
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.get("/api/admin/governance/facts?domain=accounting", headers=admin_headers)
            assert response.status_code == 200
            mock_wm.list_all_facts.assert_called_with(status=None, domain="accounting", limit=100)

    def test_list_facts_with_limit(self, test_client, admin_headers, mock_fact):
        """Cover list_facts with limit parameter (line 70, 81)"""
        mock_wm = AsyncMock()
        mock_wm.list_all_facts = AsyncMock(return_value=[mock_fact])
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.get("/api/admin/governance/facts?limit=50", headers=admin_headers)
            assert response.status_code == 200
            mock_wm.list_all_facts.assert_called_with(status=None, domain=None, limit=50)

    # -------------------------------------------------------------------------
    # Get Fact Tests (Lines 98-122)
    # -------------------------------------------------------------------------

    def test_get_fact_success(self, test_client, admin_headers, mock_fact):
        """Cover get_fact success path (lines 110-122)"""
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=mock_fact)
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.get(f"/api/admin/governance/facts/{mock_fact.id}", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["fact"] == mock_fact.fact

    def test_get_fact_not_found(self, test_client, admin_headers):
        """Cover get_fact with 404 error (lines 110-112)"""
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=None)
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.get("/api/admin/governance/facts/non-existent-id", headers=admin_headers)
            assert response.status_code == 404

    def test_get_fact_with_metadata_domain(self, test_client, admin_headers, mock_fact):
        """Cover get_fact extracting domain from metadata (line 119)"""
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=mock_fact)
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.get(f"/api/admin/governance/facts/{mock_fact.id}", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["domain"] == "accounting"

    def test_get_fact_without_metadata(self, test_client, admin_headers):
        """Cover get_fact with missing metadata (line 119, default to 'general')"""
        fact_no_metadata = BusinessFact(
            id=str(uuid.uuid4()),
            fact="Test fact",
            citations=[],
            reason="",
            source_agent_id="user:test",
            created_at=datetime.now(timezone.utc),
            last_verified=datetime.now(timezone.utc),
            verification_status="verified",
            metadata=None
        )

        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=fact_no_metadata)
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.get(f"/api/admin/governance/facts/{fact_no_metadata.id}", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["domain"] == "general"

    # -------------------------------------------------------------------------
    # Create Fact Tests (Lines 125-161)
    # -------------------------------------------------------------------------

    def test_create_fact_success(self, test_client, admin_headers):
        """Cover create_fact success path (lines 136-161)"""
        mock_wm = AsyncMock()
        mock_wm.record_business_fact = AsyncMock(return_value=True)
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.post(
                "/api/admin/governance/facts",
                json={
                    "fact": "Invoices > $500 need VP approval",
                    "citations": ["policy.pdf:p4"],
                    "reason": "Company policy",
                    "domain": "accounting"
                },
                headers=admin_headers
            )
            assert response.status_code == 201
            data = response.json()
            assert data["fact"] == "Invoices > $500 need VP approval"
            assert data["verification_status"] == "verified"

    def test_create_fact_failure(self, test_client, admin_headers):
        """Cover create_fact failure path (lines 149-151)"""
        mock_wm = AsyncMock()
        mock_wm.record_business_fact = AsyncMock(return_value=False)
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.post(
                "/api/admin/governance/facts",
                json={
                    "fact": "Test fact",
                    "citations": ["test.pdf:p1"]
                },
                headers=admin_headers
            )
            assert response.status_code == 500

    def test_create_fact_with_default_values(self, test_client, admin_headers):
        """Cover create_fact with default values (lines 45-47: empty citations, reason, domain)"""
        mock_wm = AsyncMock()
        mock_wm.record_business_fact = AsyncMock(return_value=True)
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.post(
                "/api/admin/governance/facts",
                json={
                    "fact": "Test fact"
                },
                headers=admin_headers
            )
            assert response.status_code == 201

    # -------------------------------------------------------------------------
    # Update Fact Tests (Lines 164-209)
    # -------------------------------------------------------------------------

    def test_update_fact_not_found(self, test_client, admin_headers):
        """Cover update_fact with 404 error (lines 177-179)"""
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=None)
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.put(
                "/api/admin/governance/facts/non-existent-id",
                json={"fact": "Updated"},
                headers=admin_headers
            )
            assert response.status_code == 404

    def test_update_fact_verification_status_only(self, test_client, admin_headers, mock_fact):
        """Cover update_fact with only verification_status (lines 182-183)"""
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=mock_fact)
        mock_wm.update_fact_verification = AsyncMock()
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.put(
                f"/api/admin/governance/facts/{mock_fact.id}",
                json={"verification_status": "outdated"},
                headers=admin_headers
            )
            assert response.status_code == 200
            mock_wm.update_fact_verification.assert_called_once()

    def test_update_fact_all_fields(self, test_client, admin_headers, mock_fact):
        """Cover update_fact with all fields (lines 186-209)"""
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=mock_fact)
        mock_wm.update_fact_verification = AsyncMock()
        mock_wm.record_business_fact = AsyncMock()
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.put(
                f"/api/admin/governance/facts/{mock_fact.id}",
                json={
                    "fact": "Updated fact",
                    "citations": ["updated.pdf:p1"],
                    "reason": "Updated reason",
                    "domain": "updated"
                },
                headers=admin_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["fact"] == "Updated fact"

    # -------------------------------------------------------------------------
    # Delete Fact Tests (Lines 212-228)
    # -------------------------------------------------------------------------

    def test_delete_fact_success(self, test_client, admin_headers, mock_fact):
        """Cover delete_fact success path (lines 224-228)"""
        mock_wm = AsyncMock()
        mock_wm.delete_fact = AsyncMock(return_value=True)
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.delete(f"/api/admin/governance/facts/{mock_fact.id}", headers=admin_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "deleted"
            assert data["id"] == mock_fact.id

    def test_delete_fact_not_found(self, test_client, admin_headers):
        """Cover delete_fact with 404 error (lines 224-226)"""
        mock_wm = AsyncMock()
        mock_wm.delete_fact = AsyncMock(return_value=False)
        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.delete("/api/admin/governance/facts/non-existent-id", headers=admin_headers)
            assert response.status_code == 404

    # -------------------------------------------------------------------------
    # Upload and Extract Tests (Lines 231-334)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("filename,expected_status", [
        ("test.pdf", 200),
        ("test.docx", 200),
        ("test.txt", 200),
        ("test.png", 200),
        ("test.exe", 422),
        ("test.zip", 422),
    ])
    def test_upload_file_validation(self, filename, expected_status, test_client, admin_headers):
        """Cover upload file type validation (lines 244-250)"""
        mock_storage = AsyncMock()
        mock_storage.upload_file = AsyncMock(return_value=f"s3://atom-business-facts/test/{filename}")
        mock_storage.bucket = "atom-business-facts"

        mock_wm = AsyncMock()
        mock_wm.bulk_record_facts = AsyncMock(return_value=0)

        mock_extractor = AsyncMock()
        mock_extractor.extract_facts_from_document = AsyncMock(
            return_value=Mock(facts=[], extraction_time=0.5)
        )

        with patch('api.admin.business_facts_routes.get_storage_service', return_value=mock_storage), \
             patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_policy_fact_extractor', return_value=mock_extractor), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            content = b"test content"
            files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}

            response = test_client.post(
                "/api/admin/governance/facts/upload",
                files=files,
                data={"domain": "general"},
                headers=admin_headers
            )

            assert response.status_code == expected_status

    def test_upload_success(self, test_client, admin_headers):
        """Cover upload success path with fact extraction (lines 256-321)"""
        mock_storage = AsyncMock()
        mock_storage.upload_file = AsyncMock(return_value="s3://atom-business-facts/test/doc.pdf")
        mock_storage.bucket = "atom-business-facts"

        extracted_fact = Mock(
            fact="Invoices > $500 need VP approval",
            citations=[],
            domain="accounting"
        )
        mock_extractor = AsyncMock()
        mock_extractor.extract_facts_from_document = AsyncMock(
            return_value=Mock(facts=[extracted_fact], extraction_time=1.5)
        )

        mock_wm = AsyncMock()
        mock_wm.bulk_record_facts = AsyncMock(return_value=1)

        with patch('api.admin.business_facts_routes.get_storage_service', return_value=mock_storage), \
             patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_policy_fact_extractor', return_value=mock_extractor), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            content = b"%PDF-1.4 test pdf content"
            files = {"file": ("policy.pdf", io.BytesIO(content), "application/pdf")}

            response = test_client.post(
                "/api/admin/governance/facts/upload",
                files=files,
                data={"domain": "accounting"},
                headers=admin_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["facts_extracted"] == 1
            assert data["source_document"] == "policy.pdf"

    def test_upload_extraction_failure(self, test_client, admin_headers):
        """Cover upload extraction failure (lines 323-325)"""
        mock_storage = AsyncMock()
        mock_storage.upload_file = AsyncMock(side_effect=Exception("Upload failed"))

        with patch('api.admin.business_facts_routes.get_storage_service', return_value=mock_storage), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            content = b"test content"
            files = {"file": ("test.pdf", io.BytesIO(content), "application/pdf")}

            response = test_client.post(
                "/api/admin/governance/facts/upload",
                files=files,
                data={"domain": "general"},
                headers=admin_headers
            )

            assert response.status_code == 500

    # -------------------------------------------------------------------------
    # Citation Verification Tests (Lines 336-407)
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("citation_exists,expected_status", [
        (True, "verified"),
        (False, "outdated"),
    ])
    def test_verify_citation_s3(self, citation_exists, expected_status, test_client, admin_headers, mock_fact):
        """Cover citation verification for S3 sources (lines 362-378)"""
        mock_fact.citations = ["s3://atom-business-facts/workspace-123/doc.pdf"]

        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=mock_fact)
        mock_wm.update_fact_verification = AsyncMock()

        mock_storage = AsyncMock()
        mock_storage.bucket = "atom-business-facts"
        mock_storage.check_exists = AsyncMock(return_value=citation_exists)

        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_storage_service', return_value=mock_storage), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.post(f"/api/admin/governance/facts/{mock_fact.id}/verify-citation", headers=admin_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["new_status"] == expected_status
            assert len(data["citations"]) == 1

    def test_verify_citation_local_exists(self, test_client, admin_headers, mock_fact):
        """Cover citation verification for local sources (lines 380-387)"""
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "test-policy.pdf")
        with open(temp_file, 'w') as f:
            f.write("test content")

        try:
            mock_fact.citations = ["test-policy.pdf"]

            mock_wm = AsyncMock()
            mock_wm.get_fact_by_id = AsyncMock(return_value=mock_fact)
            mock_wm.update_fact_verification = AsyncMock()

            with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
                 patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
                response = test_client.post(
                    f"/api/admin/governance/facts/{mock_fact.id}/verify-citation",
                    headers=admin_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert data["new_status"] == "verified"
                assert data["citations"][0]["source"] == "Local"
                assert data["citations"][0]["exists"] is True
        finally:
            os.unlink(temp_file)
            os.rmdir(temp_dir)

    def test_verify_citation_fact_not_found(self, test_client, admin_headers):
        """Cover verify_citation with 404 error (lines 348-350)"""
        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=None)

        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.post(
                "/api/admin/governance/facts/non-existent-id/verify-citation",
                headers=admin_headers
            )

            assert response.status_code == 404

    def test_verify_citation_s3_check_exception(self, test_client, admin_headers, mock_fact):
        """Cover S3 check exception handling (lines 377-378)"""
        mock_fact.citations = ["s3://atom-business-facts/test/doc.pdf"]

        mock_wm = AsyncMock()
        mock_wm.get_fact_by_id = AsyncMock(return_value=mock_fact)
        mock_wm.update_fact_verification = AsyncMock()

        mock_storage = AsyncMock()
        mock_storage.bucket = "atom-business-facts"
        mock_storage.check_exists = AsyncMock(side_effect=Exception("S3 error"))

        with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_wm), \
             patch('api.admin.business_facts_routes.get_storage_service', return_value=mock_storage), \
             patch('api.admin.business_facts_routes.get_current_user', return_value=admin_headers):
            response = test_client.post(
                f"/api/admin/governance/facts/{mock_fact.id}/verify-citation",
                headers=admin_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["new_status"] == "outdated"
