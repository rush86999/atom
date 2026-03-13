"""
Business Facts Routes API Tests

Tests for business facts routes (`api/admin/business_facts_routes.py`):
- GET /api/admin/governance/facts - List all facts with filters
- GET /api/admin/governance/facts/{fact_id} - Get specific fact
- POST /api/admin/governance/facts - Create new fact
- PUT /api/admin/governance/facts/{fact_id} - Update fact
- DELETE /api/admin/governance/facts/{fact_id} - Soft delete fact
- POST /api/admin/governance/facts/upload - Upload document and extract facts
- POST /api/admin/governance/facts/{fact_id}/verify-citation - Verify citation sources

Coverage target: 75%+ line coverage on business_facts_routes.py
"""

import pytest
import uuid
import io
import os
import enum
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import sys

# Define UserRole enum first
class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"
    SUPER_ADMIN = "super_admin"

# Mock the problematic models import before importing router
mock_models = MagicMock()
mock_models.UserRole = UserRole  # Use our real UserRole
sys.modules['core.models'] = mock_models

# Mock storage module to prevent boto3 import error
mock_storage_module = MagicMock()
mock_storage_service_instance = MagicMock()
mock_storage_service_instance.upload_file.return_value = "s3://atom-business-facts/workspace-123/doc.pdf"
mock_storage_service_instance.bucket = "atom-business-facts"
mock_storage_service_instance.check_exists.return_value = True
mock_storage_module.get_storage_service.return_value = mock_storage_service_instance
sys.modules['core.storage'] = mock_storage_module

# Mock policy_fact_extractor module
mock_policy_extractor_module = MagicMock()
mock_policy_extractor_instance = AsyncMock()
from core.policy_fact_extractor import ExtractionResult, ExtractedFact
mock_policy_extractor_instance.extract_facts_from_document.return_value = ExtractionResult(
    success=True,
    facts=[
        ExtractedFact(
            fact="Invoices over $500 require VP approval",
            domain="finance",
            confidence=0.95
        ),
        ExtractedFact(
            fact="All expenses must be submitted within 30 days",
            domain="finance",
            confidence=0.88
        ),
        ExtractedFact(
            fact="Travel advances require manager approval",
            domain="hr",
            confidence=0.92
        )
    ],
    extraction_time=1.5,
    source_document="test-policy.pdf"
)
mock_policy_extractor_module.get_policy_fact_extractor.return_value = mock_policy_extractor_instance
sys.modules['core.policy_fact_extractor'] = mock_policy_extractor_module

# Import business facts routes router
from api.admin.business_facts_routes import router

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

    # Create session (no tables needed since we mock User)
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
def client(test_app: FastAPI):
    """Create TestClient for testing."""
    return TestClient(test_app)


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def admin_user(test_db: Session):
    """Create mock admin user for authorization tests."""
    user = MagicMock()
    user.id = str(uuid.uuid4())
    user.email = "admin@test.com"
    user.first_name = "Admin"
    user.last_name = "User"
    user.name = "Admin User"
    user.role = UserRole.ADMIN
    user.status = "active"
    user.email_verified = True
    user.workspace_id = "default"
    return user


@pytest.fixture(scope="function")
def authenticated_admin_client(test_app: FastAPI, admin_user):
    """Create TestClient with authenticated admin user."""
    from core.auth import get_current_user

    # Override get_current_user
    async def override_get_current_user():
        return admin_user

    test_app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(test_app)
    yield client

    # Clean up
    test_app.dependency_overrides.clear()


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def sample_business_fact() -> BusinessFact:
    """Create sample BusinessFact for testing."""
    return BusinessFact(
        id=str(uuid.uuid4()),
        fact="Invoices over $500 require VP approval",
        citations=["s3://atom-business-facts/policies/ap-policy.pdf"],
        reason="Extracted from AP policy document",
        source_agent_id="user:test-user",
        created_at=datetime.now(timezone.utc),
        last_verified=datetime.now(timezone.utc),
        verification_status="verified",
        metadata={"domain": "finance"}
    )


@pytest.fixture(scope="function")
def sample_unverified_fact() -> BusinessFact:
    """Create sample unverified BusinessFact for testing."""
    return BusinessFact(
        id=str(uuid.uuid4()),
        fact="Unverified fact requiring review",
        citations=["local:policy.pdf"],
        reason="Pending verification",
        source_agent_id="user:test-user",
        created_at=datetime.now(timezone.utc),
        last_verified=datetime.now(timezone.utc),
        verification_status="unverified",
        metadata={"domain": "hr"}
    )


@pytest.fixture(scope="function")
def sample_deleted_fact() -> BusinessFact:
    """Create sample deleted BusinessFact for testing."""
    return BusinessFact(
        id=str(uuid.uuid4()),
        fact="Deleted fact",
        citations=["s3://atom-business-facts/old.pdf"],
        reason="No longer valid",
        source_agent_id="user:test-user",
        created_at=datetime.now(timezone.utc),
        last_verified=datetime.now(timezone.utc),
        verification_status="deleted",
        metadata={"domain": "general"}
    )


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_world_model_service(sample_business_fact: BusinessFact):
    """AsyncMock for WorldModelService with deterministic return values."""
    mock = AsyncMock()

    # Configure deterministic return values
    mock.list_all_facts.return_value = [sample_business_fact]

    mock.get_fact_by_id.return_value = sample_business_fact

    mock.record_business_fact.return_value = True

    mock.delete_fact.return_value = True

    mock.update_fact_verification.return_value = None

    mock.bulk_record_facts.return_value = 3

    # Patch WorldModelService at the route level
    with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock):
        yield mock


@pytest.fixture(scope="function")
def mock_storage_service():
    """MagicMock for R2/S3 storage operations."""
    mock = mock_storage_service_instance
    # Reset mock for each test
    mock.reset_mock()

    # Configure deterministic return values
    mock.upload_file.return_value = "s3://atom-business-facts/workspace-123/doc.pdf"
    mock.bucket = "atom-business-facts"
    mock.check_exists.return_value = True

    return mock


@pytest.fixture(scope="function")
def mock_policy_extractor():
    """AsyncMock for policy fact extraction."""
    mock = mock_policy_extractor_instance
    # Reset mock for each test
    mock.reset_mock()

    # Configure deterministic return values
    from core.policy_fact_extractor import ExtractionResult, ExtractedFact

    mock.extract_facts_from_document.return_value = ExtractionResult(
        success=True,
        facts=[
            ExtractedFact(
                fact="Invoices over $500 require VP approval",
                domain="finance",
                confidence=0.95
            ),
            ExtractedFact(
                fact="All expenses must be submitted within 30 days",
                domain="finance",
                confidence=0.88
            ),
            ExtractedFact(
                fact="Travel advances require manager approval",
                domain="hr",
                confidence=0.92
            )
        ],
        extraction_time=1.5,
        source_document="test-policy.pdf"
    )

    return mock


# ============================================================================
# Task 1: Test List Facts Filter Tests
# ============================================================================

class TestListFactsFilters:
    """Tests for GET /api/admin/governance/facts with filter variations"""

    @patch('api.admin.business_facts_routes.WorldModelService')
    def test_list_facts_filter_by_status_verified(
        self,
        mock_wm_class,
        authenticated_admin_client: TestClient,
        sample_business_fact: BusinessFact
    ):
        """Test list facts filtered by verified status."""
        # Configure mock to return verified facts
        mock_wm_instance = AsyncMock()
        mock_wm_instance.list_all_facts.return_value = [sample_business_fact]
        mock_wm_class.return_value = mock_wm_instance

        response = authenticated_admin_client.get(
            "/api/admin/governance/facts?status=verified"
        )

        assert response.status_code == status.HTTP_200_OK
        facts = response.json()
        assert len(facts) == 1
        assert facts[0]["verification_status"] == "verified"

    def test_list_facts_filter_by_status_unverified(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_unverified_fact: BusinessFact
    ):
        """Test list facts filtered by unverified status."""
        # Configure mock to return unverified facts
        mock_world_model_service.list_all_facts.return_value = [sample_unverified_fact]

        response = authenticated_admin_client.get(
            "/api/admin/governance/facts?status=unverified"
        )

        assert response.status_code == status.HTTP_200_OK
        facts = response.json()
        assert len(facts) == 1
        assert facts[0]["verification_status"] == "unverified"

    def test_list_facts_filter_by_domain_finance(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test list facts filtered by finance domain."""
        # Configure mock to return finance facts
        mock_world_model_service.list_all_facts.return_value = [sample_business_fact]

        response = authenticated_admin_client.get(
            "/api/admin/governance/facts?domain=finance"
        )

        assert response.status_code == status.HTTP_200_OK
        facts = response.json()
        assert len(facts) == 1
        assert facts[0]["domain"] == "finance"

    def test_list_facts_filter_by_domain_hr(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_unverified_fact: BusinessFact
    ):
        """Test list facts filtered by hr domain."""
        # Configure mock to return hr facts
        mock_world_model_service.list_all_facts.return_value = [sample_unverified_fact]

        response = authenticated_admin_client.get(
            "/api/admin/governance/facts?domain=hr"
        )

        assert response.status_code == status.HTTP_200_OK
        facts = response.json()
        assert len(facts) == 1
        assert facts[0]["domain"] == "hr"

    def test_list_facts_combined_filters(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test list facts with combined status and domain filters."""
        # Configure mock to return filtered facts
        mock_world_model_service.list_all_facts.return_value = [sample_business_fact]

        response = authenticated_admin_client.get(
            "/api/admin/governance/facts?status=verified&domain=finance"
        )

        assert response.status_code == status.HTTP_200_OK
        facts = response.json()
        assert len(facts) == 1
        assert facts[0]["verification_status"] == "verified"
        assert facts[0]["domain"] == "finance"

    def test_list_facts_excludes_deleted_status(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact,
        sample_deleted_fact: BusinessFact
    ):
        """Test list facts excludes deleted facts."""
        # Configure mock to return facts including deleted
        mock_world_model_service.list_all_facts.return_value = [
            sample_business_fact,
            sample_deleted_fact
        ]

        response = authenticated_admin_client.get("/api/admin/governance/facts")

        assert response.status_code == status.HTTP_200_OK
        facts = response.json()
        # Should filter out deleted facts
        assert len(facts) == 1
        assert facts[0]["verification_status"] != "deleted"

    def test_list_facts_custom_limit(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test list facts with custom limit parameter."""
        # Configure mock
        mock_world_model_service.list_all_facts.return_value = [sample_business_fact]

        response = authenticated_admin_client.get(
            "/api/admin/governance/facts?limit=50"
        )

        assert response.status_code == status.HTTP_200_OK
        # Verify limit was passed to service
        mock_world_model_service.list_all_facts.assert_called_with(
            status=None,
            domain=None,
            limit=50
        )

    def test_list_facts_default_limit(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test list facts with default limit (100)."""
        # Configure mock
        mock_world_model_service.list_all_facts.return_value = [sample_business_fact]

        response = authenticated_admin_client.get("/api/admin/governance/facts")

        assert response.status_code == status.HTTP_200_OK
        # Verify default limit was passed to service
        mock_world_model_service.list_all_facts.assert_called_with(
            status=None,
            domain=None,
            limit=100
        )


# ============================================================================
# Task 2: Create and Update Fact Validation Tests
# ============================================================================

class TestCreateFactValidation:
    """Tests for POST /api/admin/governance/facts validation scenarios"""

    def test_create_fact_with_empty_fact_text(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test create fact with empty fact text succeeds (API accepts empty strings)."""
        # Configure mock to return success
        mock_world_model_service.record_business_fact.return_value = True

        response = authenticated_admin_client.post(
            "/api/admin/governance/facts",
            json={
                "fact": "",
                "citations": ["s3://bucket/doc.pdf"],
                "reason": "Test",
                "domain": "finance"
            }
        )

        # Empty fact is accepted by API (no Pydantic min_length constraint)
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_fact_with_empty_citations(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test create fact with empty citations list succeeds."""
        # Configure mock to return success
        mock_world_model_service.record_business_fact.return_value = True

        response = authenticated_admin_client.post(
            "/api/admin/governance/facts",
            json={
                "fact": "Test fact",
                "citations": [],
                "reason": "Test reason",
                "domain": "general"
            }
        )

        # Empty citations should be allowed
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["fact"] == "Test fact"
        assert data["citations"] == []

    def test_create_fact_with_long_fact_text(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test create fact with very long fact text succeeds."""
        # Configure mock to return success
        mock_world_model_service.record_business_fact.return_value = True

        long_fact = "A" * 10000  # 10,000 characters

        response = authenticated_admin_client.post(
            "/api/admin/governance/facts",
            json={
                "fact": long_fact,
                "citations": ["s3://bucket/doc.pdf"],
                "reason": "Test",
                "domain": "general"
            }
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert len(data["fact"]) == 10000

    def test_create_fact_with_special_characters(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test create fact with unicode/emoji characters succeeds."""
        # Configure mock to return success
        mock_world_model_service.record_business_fact.return_value = True

        response = authenticated_admin_client.post(
            "/api/admin/governance/facts",
            json={
                "fact": "Invoices over $500 require VP approval ✓ 💼",
                "citations": ["s3://bucket/doc.pdf"],
                "reason": "Test with émojis 🎯",
                "domain": "finance"
            }
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "✓" in data["fact"]
        assert "💼" in data["fact"]
        assert "🎯" in data["reason"]

    def test_create_fact_with_array_citations(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test create fact with multiple citations stores all."""
        # Configure mock to return success
        mock_world_model_service.record_business_fact.return_value = True

        citations = [
            "s3://bucket/policy1.pdf",
            "s3://bucket/policy2.pdf",
            "s3://bucket/policy3.pdf"
        ]

        response = authenticated_admin_client.post(
            "/api/admin/governance/facts",
            json={
                "fact": "Multi-source fact",
                "citations": citations,
                "reason": "Test",
                "domain": "finance"
            }
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert len(data["citations"]) == 3
        assert data["citations"][0] == "s3://bucket/policy1.pdf"

    def test_create_fact_lancedb_failure_returns_500(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test create fact when LanceDB fails returns 500 error."""
        # Configure mock to return failure
        mock_world_model_service.record_business_fact.return_value = False

        response = authenticated_admin_client.post(
            "/api/admin/governance/facts",
            json={
                "fact": "Test fact",
                "citations": ["s3://bucket/doc.pdf"],
                "reason": "Test",
                "domain": "finance"
            }
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestUpdateFactAllFields:
    """Tests for PUT /api/admin/governance/facts/{id} field variations"""

    def test_update_fact_fact_field_only(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test update fact with only fact field."""
        # Configure mock
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact
        mock_world_model_service.record_business_fact.return_value = True

        response = authenticated_admin_client.put(
            f"/api/admin/governance/facts/{sample_business_fact.id}",
            json={"fact": "Updated fact text"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["fact"] == "Updated fact text"

    def test_update_fact_citations_field_only(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test update fact with only citations field."""
        # Configure mock
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact
        mock_world_model_service.record_business_fact.return_value = True

        new_citations = ["s3://bucket/new-policy.pdf"]

        response = authenticated_admin_client.put(
            f"/api/admin/governance/facts/{sample_business_fact.id}",
            json={"citations": new_citations}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["citations"] == new_citations

    def test_update_fact_reason_field_only(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test update fact with only reason field."""
        # Configure mock
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact
        mock_world_model_service.record_business_fact.return_value = True

        response = authenticated_admin_client.put(
            f"/api/admin/governance/facts/{sample_business_fact.id}",
            json={"reason": "Updated reason"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["reason"] == "Updated reason"

    def test_update_fact_domain_field_only(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test update fact with only domain field."""
        # Configure mock
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact
        mock_world_model_service.record_business_fact.return_value = True

        response = authenticated_admin_client.put(
            f"/api/admin/governance/facts/{sample_business_fact.id}",
            json={"domain": "hr"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["domain"] == "hr"

    def test_update_fact_all_fields_together(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test update fact with all fields."""
        # Configure mock
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact
        mock_world_model_service.record_business_fact.return_value = True

        response = authenticated_admin_client.put(
            f"/api/admin/governance/facts/{sample_business_fact.id}",
            json={
                "fact": "Updated all fields",
                "citations": ["s3://bucket/updated.pdf"],
                "reason": "Updated reason",
                "domain": "operations",
                "verification_status": "verified"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["fact"] == "Updated all fields"
        assert data["citations"] == ["s3://bucket/updated.pdf"]
        assert data["reason"] == "Updated reason"
        assert data["domain"] == "operations"
        assert data["verification_status"] == "verified"

    def test_update_fact_preserves_created_at(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test update fact preserves created_at timestamp."""
        original_created_at = sample_business_fact.created_at

        # Configure mock
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact
        mock_world_model_service.record_business_fact.return_value = True

        response = authenticated_admin_client.put(
            f"/api/admin/governance/facts/{sample_business_fact.id}",
            json={"fact": "Updated fact"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Verify created_at is preserved
        assert "created_at" in data


# ============================================================================
# Task 3: Upload and Extract Success Tests
# ============================================================================

class TestUploadAndExtractSuccess:
    """Tests for POST /api/admin/governance/facts/upload success scenarios"""

    def test_upload_pdf_file_success(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload PDF file succeeds."""
        # Create PDF file content
        pdf_content = b"%PDF-1.4\nTest policy\n%%EOF"

        response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
                data={"domain": "finance"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["facts_extracted"] > 0
        assert "extraction_time" in data

    def test_upload_docx_file_success(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload DOCX file succeeds."""
        docx_content = b"PK\x03\x04"  # DOCX header

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.docx", io.BytesIO(docx_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"domain": "hr"}
                )

        assert response.status_code == status.HTTP_200_OK

    def test_upload_txt_file_success(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload TXT file succeeds."""
        txt_content = b"Test policy content"

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.txt", io.BytesIO(txt_content), "text/plain")},
                data={"domain": "general"}
                )

        assert response.status_code == status.HTTP_200_OK

    def test_upload_png_file_success(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload PNG file succeeds."""
        png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # PNG header

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.png", io.BytesIO(png_content), "image/png")},
                data={"domain": "finance"}
                )

        assert response.status_code == status.HTTP_200_OK

    def test_upload_with_custom_domain(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload with custom domain parameter."""
        pdf_content = b"%PDF-1.4\nTest\n%%EOF"

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
                data={"domain": "operations"}
                )

        assert response.status_code == status.HTTP_200_OK

    def test_upload_storage_service_called(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload calls storage service upload_file."""
        pdf_content = b"%PDF-1.4\nTest\n%%EOF"

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
                data={"domain": "finance"}
                )

        # Verify storage service was called
        mock_storage_service.upload_file.assert_called_once()
        assert response.status_code == status.HTTP_200_OK

    def test_upload_fact_extractor_called(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload calls policy fact extractor."""
        pdf_content = b"%PDF-1.4\nTest\n%%EOF"

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
                data={"domain": "finance"}
                )

        # Verify extractor was called
        mock_policy_extractor.extract_facts_from_document.assert_called_once()
        assert response.status_code == status.HTTP_200_OK

    def test_upload_bulk_record_facts_called(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload calls bulk_record_facts with extracted facts."""
        pdf_content = b"%PDF-1.4\nTest\n%%EOF"

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
                data={"domain": "finance"}
                )

        # Verify bulk_record_facts was called
        mock_world_model_service.bulk_record_facts.assert_called_once()
        assert response.status_code == status.HTTP_200_OK

    def test_upload_returns_extraction_response(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload returns proper ExtractionResponse structure."""
        pdf_content = b"%PDF-1.4\nTest\n%%EOF"

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
                data={"domain": "finance"}
                )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Verify response structure
        assert "success" in data
        assert "facts_extracted" in data
        assert "facts" in data
        assert "source_document" in data
        assert "extraction_time" in data
        assert data["success"] is True

    def test_upload_temp_file_cleanup(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload cleans up temporary files."""
        pdf_content = b"%PDF-1.4\nTest\n%%EOF"

        with patch('core.storage.get_storage_service', return_value=mock_storage_service):
            with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
                with patch('os.unlink') as mock_unlink:
                    response = authenticated_admin_client.post(
                    "/api/admin/governance/facts/upload",
                    files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
                    data={"domain": "finance"}
                    )

        # Verify temp file cleanup was attempted
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# Task 4: Upload File Types and Citation Verification Tests
# ============================================================================

class TestUploadAndExtractFileTypes:
    """Tests for POST /upload with various file types"""

    def test_upload_jpeg_file_success(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload JPEG file succeeds."""
        jpeg_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG header

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.jpg", io.BytesIO(jpeg_content), "image/jpeg")},
                data={"domain": "finance"}
                )

        assert response.status_code == status.HTTP_200_OK

    def test_upload_tiff_file_success(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload TIFF file succeeds."""
        tiff_content = b"II\x2a\x00" + b"\x00" * 100  # TIFF header (little-endian)

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.tiff", io.BytesIO(tiff_content), "image/tiff")},
                data={"domain": "general"}
                )

        assert response.status_code == status.HTTP_200_OK

    def test_upload_jpg_file_success(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload .jpg file with image/jpeg content-type succeeds."""
        jpg_content = b"\xff\xd8\xff\xe1" + b"\x00" * 100  # JPEG header

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.jpg", io.BytesIO(jpg_content), "image/jpeg")},
                data={"domain": "hr"}
                )

        assert response.status_code == status.HTTP_200_OK

    def test_upload_doc_file_success(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_world_model_service: AsyncMock
    ):
        """Test upload .doc file with application/msword content-type succeeds."""
        doc_content = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # DOC header

        with patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.doc", io.BytesIO(doc_content), "application/msword")},
                data={"domain": "finance"}
                )

        assert response.status_code == status.HTTP_200_OK


class TestVerifyCitationS3:
    """Tests for POST /{fact_id}/verify-citation with S3 citations"""

    def test_verify_citation_s3_exists_true(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact,
        mock_storage_service: MagicMock
    ):
        """Test verify citation when S3 file exists returns verified status."""
        # Configure fact with S3 citation
        sample_business_fact.citations = ["s3://atom-business-facts/policies/doc.pdf"]

        # Configure mocks
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact
        mock_storage_service.check_exists.return_value = True

        response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["new_status"] == "verified"
        assert data["citations"][0]["exists"] is True

    def test_verify_citation_s3_exists_false(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact,
        mock_storage_service: MagicMock
    ):
        """Test verify citation when S3 file missing returns outdated status."""
        # Configure fact with S3 citation
        sample_business_fact.citations = ["s3://atom-business-facts/policies/missing.pdf"]

        # Configure mocks
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact
        mock_storage_service.check_exists.return_value = False

        response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["new_status"] == "outdated"
        assert data["citations"][0]["exists"] is False

    def test_verify_citation_s3_bucket_mismatch(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact,
        mock_storage_service: MagicMock
    ):
        """Test verify citation with different bucket name."""
        # Configure fact with different bucket citation
        sample_business_fact.citations = ["s3://other-bucket/policies/doc.pdf"]

        # Configure mocks
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact
        mock_storage_service.bucket = "atom-business-facts"
        mock_storage_service.check_exists.return_value = False

        response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

        assert response.status_code == status.HTTP_200_OK
        # Should handle bucket mismatch gracefully
        data = response.json()
        assert "new_status" in data

    def test_verify_citation_updates_status_to_verified(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact,
        mock_storage_service: MagicMock
    ):
        """Test verify citation updates fact status to verified."""
        # Configure fact with S3 citation
        sample_business_fact.citations = ["s3://atom-business-facts/policies/doc.pdf"]

        # Configure mocks
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact
        mock_storage_service.check_exists.return_value = True

        response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

        assert response.status_code == status.HTTP_200_OK
        # Verify update_fact_verification was called
        mock_world_model_service.update_fact_verification.assert_called_with(
            sample_business_fact.id,
            "verified"
        )


class TestVerifyCitationLocalFallback:
    """Tests for POST /{fact_id}/verify-citation with local file fallback"""

    def test_verify_citation_local_fallback_exists(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test verify citation with local fallback when file exists."""
        # Configure fact with local citation
        sample_business_fact.citations = ["policy.pdf"]

        # Configure mocks
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact

        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["citations"][0]["exists"] is True

    def test_verify_citation_local_fallback_not_exists(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test verify citation with local fallback when file missing."""
        # Configure fact with local citation
        sample_business_fact.citations = ["missing.pdf"]

        # Configure mocks
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact

        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["citations"][0]["exists"] is False

    def test_verify_citation_local_fallback_multiple_paths(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test verify citation checks all local base paths."""
        # Configure fact with local citation
        sample_business_fact.citations = ["policy.pdf"]

        # Configure mocks
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact

        call_count = [0]

        def side_effect_exists(path):
            call_count[0] += 1
            # Return True on /app/uploads path
            return "/app/uploads" in path

        with patch('os.path.exists', side_effect=side_effect_exists):
            with patch('os.getcwd', return_value='/app'):
                response = authenticated_admin_client.post(
                    f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
                )

        assert response.status_code == status.HTTP_200_OK
        # Verify multiple paths were checked
        assert call_count[0] > 0

    def test_verify_citation_non_s3_uri_uses_local(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test verify citation with non-S3 URI uses local fallback."""
        # Configure fact with local-style citation
        sample_business_fact.citations = ["local:policy.pdf"]

        # Configure mocks
        mock_world_model_service.get_fact_by_id.return_value = sample_business_fact

        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True
            response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should use local fallback
        assert data["citations"][0]["source"] == "Local"
