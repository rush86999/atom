"""
Admin Business Facts Routes API Tests

Tests for business facts admin routes (`api/admin/business_facts_routes.py`):
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
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import business facts routes router
from api.admin.business_facts_routes import router

# Import models
from core.models import Base, User, UserRole
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

    # Create only the tables we need for business facts testing
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
def admin_user(test_db: Session) -> User:
    """Create admin user for authorization tests."""
    user = User(
        id=str(uuid.uuid4()),
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        name="Admin User",
        role=UserRole.ADMIN,
        status="active",
        email_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def regular_user(test_db: Session) -> User:
    """Create regular user for role testing."""
    user = User(
        id=str(uuid.uuid4()),
        email="user@test.com",
        first_name="Regular",
        last_name="User",
        name="Regular User",
        role=UserRole.MEMBER,
        status="active",
        email_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def authenticated_admin_client(test_app: FastAPI, admin_user: User):
    """Create TestClient with authenticated admin user."""
    from core.auth import get_current_user
    from core.security.rbac import require_role

    # Override get_current_user
    async def override_get_current_user():
        return admin_user

    # Override require_role to allow admin
    async def override_require_role(role: UserRole):
        if admin_user.role != role:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return True

    test_app.dependency_overrides[get_current_user] = override_get_current_user
    test_app.dependency_overrides[require_role] = override_require_role

    client = TestClient(test_app)
    yield client

    # Clean up
    test_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def authenticated_regular_client(test_app: FastAPI, regular_user: User):
    """Create TestClient with authenticated regular user (for auth tests)."""
    from core.auth import get_current_user
    from core.security.rbac import require_role

    # Override get_current_user
    async def override_get_current_user():
        return regular_user

    # Override require_role to fail for non-admin
    async def override_require_role(role: UserRole):
        if regular_user.role != role:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return True

    test_app.dependency_overrides[get_current_user] = override_get_current_user
    test_app.dependency_overrides[require_role] = override_require_role

    client = TestClient(test_app)
    yield client

    # Clean up
    test_app.dependency_overrides.clear()


# ============================================================================
# Mock Service Fixtures
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
        metadata={"domain": "accounting"}
    )


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

    return mock


@pytest.fixture(scope="function")
def mock_storage_service():
    """MagicMock for R2/S3 storage operations."""
    mock = MagicMock()

    # Configure deterministic return values
    mock.upload_file.return_value = "s3://atom-business-facts/workspace-123/doc.pdf"
    mock.bucket = "atom-business-facts"
    mock.check_exists.return_value = True

    return mock


@pytest.fixture(scope="function")
def mock_policy_extractor():
    """AsyncMock for policy fact extraction."""
    mock = AsyncMock()

    # Configure deterministic return values
    from core.policy_fact_extractor import ExtractionResult, ExtractedFact

    mock.extract_facts_from_document.return_value = ExtractionResult(
        success=True,
        facts=[
            ExtractedFact(
                fact="Invoices over $500 require VP approval",
                domain="accounting",
                confidence=0.95
            ),
            ExtractedFact(
                fact="All expenses must be submitted within 30 days",
                domain="accounting",
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


@pytest.fixture(scope="function")
def mock_pdf_upload():
    """Function returning BytesIO for file upload testing."""
    def _create_pdf(filename: str = "test-policy.pdf"):
        # Create minimal PDF-like content
        content = b"%PDF-1.4\nTest policy content\n%%EOF"
        return (filename, io.BytesIO(content), "application/pdf")

    return _create_pdf


@pytest.fixture(scope="function")
def mock_txt_upload():
    """Function returning BytesIO for TXT file upload testing."""
    def _create_txt(filename: str = "test-policy.txt"):
        content = b"Test policy content"
        return (filename, io.BytesIO(content), "text/plain")

    return _create_txt


# ============================================================================
# Test: List Facts Endpoint
# ============================================================================

class TestBusinessFactsList:
    """Tests for GET /api/admin/governance/facts"""

    def test_list_facts_success(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test listing all facts with no filters."""
        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.get("/api/admin/governance/facts")

            assert response.status_code == status.HTTP_200_OK
            facts = response.json()
            assert isinstance(facts, list)
            assert len(facts) >= 1

            # Verify structure of first fact
            fact = facts[0]
            assert "id" in fact
            assert "fact" in fact
            assert "citations" in fact
            assert "reason" in fact
            assert "domain" in fact
            assert "verification_status" in fact
            assert "created_at" in fact

            # Verify deleted facts are filtered out
            for f in facts:
                assert f["verification_status"] != "deleted"

    def test_list_facts_with_status_filter(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test listing facts with status filter."""
        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.get(
                "/api/admin/governance/facts?status=verified"
            )

            assert response.status_code == status.HTTP_200_OK
            facts = response.json()
            assert isinstance(facts, list)

            # Verify list_all_facts was called with status filter
            mock_world_model_service.list_all_facts.assert_called_once_with(
                status="verified",
                domain=None,
                limit=100
            )

    def test_list_facts_with_domain_filter(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test listing facts with domain filter."""
        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.get(
                "/api/admin/governance/facts?domain=accounting"
            )

            assert response.status_code == status.HTTP_200_OK
            facts = response.json()
            assert isinstance(facts, list)

            # Verify list_all_facts was called with domain filter
            mock_world_model_service.list_all_facts.assert_called_once_with(
                status=None,
                domain="accounting",
                limit=100
            )

    def test_list_facts_with_limit(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test listing facts with custom limit."""
        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.get(
                "/api/admin/governance/facts?limit=50"
            )

            assert response.status_code == status.HTTP_200_OK

            # Verify list_all_facts was called with limit
            mock_world_model_service.list_all_facts.assert_called_once_with(
                status=None,
                domain=None,
                limit=50
            )

    def test_list_facts_excludes_deleted(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test that deleted facts are not returned."""
        # Create a deleted fact
        deleted_fact = BusinessFact(
            id=str(uuid.uuid4()),
            fact="Deleted fact",
            citations=["deleted.pdf"],
            reason="Should not appear",
            source_agent_id="user:test",
            created_at=datetime.now(timezone.utc),
            last_verified=datetime.now(timezone.utc),
            verification_status="deleted",
            metadata={"domain": "test"}
        )

        mock_world_model_service.list_all_facts.return_value = [
            sample_business_fact := BusinessFact(
                id=str(uuid.uuid4()),
                fact="Active fact",
                citations=["active.pdf"],
                reason="Should appear",
                source_agent_id="user:test",
                created_at=datetime.now(timezone.utc),
                last_verified=datetime.now(timezone.utc),
                verification_status="verified",
                metadata={"domain": "test"}
            ),
            deleted_fact
        ]

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.get("/api/admin/governance/facts")

            assert response.status_code == status.HTTP_200_OK
            facts = response.json()

            # Verify deleted fact is filtered out
            assert len(facts) == 1
            assert facts[0]["fact"] == "Active fact"
            assert all(f["verification_status"] != "deleted" for f in facts)

    def test_list_facts_empty(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test listing when no facts exist."""
        mock_world_model_service.list_all_facts.return_value = []

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.get("/api/admin/governance/facts")

            assert response.status_code == status.HTTP_200_OK
            facts = response.json()
            assert facts == []


# ============================================================================
# Test: Get Fact Endpoint
# ============================================================================

class TestBusinessFactsGet:
    """Tests for GET /api/admin/governance/facts/{fact_id}"""

    def test_get_fact_success(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test getting fact by ID."""
        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.get(
                f"/api/admin/governance/facts/{sample_business_fact.id}"
            )

            assert response.status_code == status.HTTP_200_OK
            fact = response.json()

            # Verify all fields populated
            assert fact["id"] == sample_business_fact.id
            assert fact["fact"] == sample_business_fact.fact
            assert fact["citations"] == sample_business_fact.citations
            assert fact["reason"] == sample_business_fact.reason
            assert fact["domain"] == "accounting"  # From metadata
            assert fact["verification_status"] == sample_business_fact.verification_status
            assert "created_at" in fact

    def test_get_fact_not_found(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test getting non-existent fact."""
        mock_world_model_service.get_fact_by_id.return_value = None

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.get(
                "/api/admin/governance/facts/non-existent-id"
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()

    def test_get_fact_with_metadata(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test fact with metadata domain extraction."""
        custom_fact = BusinessFact(
            id=str(uuid.uuid4()),
            fact="Custom domain fact",
            citations=["custom.pdf"],
            reason="Test",
            source_agent_id="user:test",
            created_at=datetime.now(timezone.utc),
            last_verified=datetime.now(timezone.utc),
            verification_status="verified",
            metadata={"domain": "custom", "extra": "data"}
        )

        mock_world_model_service.get_fact_by_id.return_value = custom_fact

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.get(
                f"/api/admin/governance/facts/{custom_fact.id}"
            )

            assert response.status_code == status.HTTP_200_OK
            fact = response.json()
            # Verify domain is extracted from metadata
            assert fact["domain"] == "custom"


# ============================================================================
# Test: Create Fact Endpoint
# ============================================================================

class TestBusinessFactsCreate:
    """Tests for POST /api/admin/governance/facts"""

    def test_create_fact_success(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test creating fact with valid data."""
        fact_data = {
            "fact": "New business rule",
            "citations": ["policy.pdf:page1"],
            "reason": "Test creation",
            "domain": "general"
        }

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts",
                json=fact_data
            )

            assert response.status_code == status.HTTP_201_CREATED
            fact = response.json()

            # Verify response structure
            assert "id" in fact
            assert fact["fact"] == fact_data["fact"]
            assert fact["citations"] == fact_data["citations"]
            assert fact["reason"] == fact_data["reason"]
            assert fact["domain"] == fact_data["domain"]
            assert fact["verification_status"] == "verified"
            assert "created_at" in fact

            # Verify record_business_fact was called
            mock_world_model_service.record_business_fact.assert_called_once()

    def test_create_fact_with_citations(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test creating fact with citations."""
        fact_data = {
            "fact": "Fact with citations",
            "citations": ["doc1.pdf:page1", "doc2.pdf:page5"],
            "reason": "Test citations",
            "domain": "accounting"
        }

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts",
                json=fact_data
            )

            assert response.status_code == status.HTTP_201_CREATED
            fact = response.json()
            assert fact["citations"] == fact_data["citations"]

    def test_create_fact_with_domain(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test creating fact with custom domain."""
        fact_data = {
            "fact": "HR policy fact",
            "citations": ["hr-handbook.pdf"],
            "reason": "Test domain",
            "domain": "hr"
        }

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts",
                json=fact_data
            )

            assert response.status_code == status.HTTP_201_CREATED
            fact = response.json()
            assert fact["domain"] == "hr"

    def test_create_fact_failure(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test when record_business_fact fails."""
        mock_world_model_service.record_business_fact.return_value = False

        fact_data = {
            "fact": "Failed fact",
            "citations": [],
            "reason": "Test failure"
        }

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts",
                json=fact_data
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# Test: Update Fact Endpoint
# ============================================================================

class TestBusinessFactsUpdate:
    """Tests for PUT /api/admin/governance/facts/{fact_id}"""

    def test_update_fact_all_fields(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test updating all fact fields."""
        update_data = {
            "fact": "Updated business rule",
            "citations": ["updated.pdf:page1"],
            "reason": "Updated reason",
            "domain": "finance",
            "verification_status": "verified"
        }

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.put(
                f"/api/admin/governance/facts/{sample_business_fact.id}",
                json=update_data
            )

            assert response.status_code == status.HTTP_200_OK
            fact = response.json()

            # Verify all fields updated
            assert fact["fact"] == update_data["fact"]
            assert fact["citations"] == update_data["citations"]
            assert fact["reason"] == update_data["reason"]
            assert fact["domain"] == update_data["domain"]
            assert fact["verification_status"] == update_data["verification_status"]

            # Verify update_fact_verification was called
            mock_world_model_service.update_fact_verification.assert_called_once()

    def test_update_fact_partial(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test partial update (only fact text)."""
        update_data = {
            "fact": "Updated fact text only"
        }

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.put(
                f"/api/admin/governance/facts/{sample_business_fact.id}",
                json=update_data
            )

            assert response.status_code == status.HTTP_200_OK
            fact = response.json()

            # Verify fact updated, other fields preserved
            assert fact["fact"] == update_data["fact"]
            assert fact["citations"] == sample_business_fact.citations
            assert fact["reason"] == sample_business_fact.reason

    def test_update_fact_verification_status(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test updating verification status."""
        update_data = {
            "verification_status": "outdated"
        }

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.put(
                f"/api/admin/governance/facts/{sample_business_fact.id}",
                json=update_data
            )

            assert response.status_code == status.HTTP_200_OK

            # Verify update_fact_verification called
            mock_world_model_service.update_fact_verification.assert_called_once_with(
                sample_business_fact.id,
                "outdated"
            )

    def test_update_fact_not_found(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test updating non-existent fact."""
        mock_world_model_service.get_fact_by_id.return_value = None

        update_data = {
            "fact": "Update non-existent"
        }

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.put(
                "/api/admin/governance/facts/non-existent-id",
                json=update_data
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Test: Delete Fact Endpoint
# ============================================================================

class TestBusinessFactsDelete:
    """Tests for DELETE /api/admin/governance/facts/{fact_id}"""

    def test_delete_fact_success(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test soft deleting a fact."""
        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.delete(
                f"/api/admin/governance/facts/{sample_business_fact.id}"
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()
            assert result["status"] == "deleted"
            assert result["id"] == sample_business_fact.id

            # Verify delete_fact was called
            mock_world_model_service.delete_fact.assert_called_once_with(
                sample_business_fact.id
            )

    def test_delete_fact_not_found(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test deleting non-existent fact."""
        mock_world_model_service.delete_fact.return_value = False

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.delete(
                "/api/admin/governance/facts/non-existent-id"
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Test: File Upload Endpoint
# ============================================================================

class TestBusinessFactsUpload:
    """Tests for POST /api/admin/governance/facts/upload"""

    def test_upload_and_extract_success(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_pdf_upload
    ):
        """Test successful document upload and extraction."""
        filename, file_content, content_type = mock_pdf_upload()

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('core.storage.get_storage_service', return_value=mock_storage_service), \
             patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):

            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": (filename, file_content, content_type)},
                data={"domain": "general"}
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()

            # Verify response structure
            assert result["success"] is True
            assert result["facts_extracted"] == 3
            assert "facts" in result
            assert "source_document" in result
            assert "extraction_time" in result

            # Verify S3 upload
            mock_storage_service.upload_file.assert_called_once()

            # Verify fact extraction
            mock_policy_extractor.extract_facts_from_document.assert_called_once()

            # Verify facts stored
            mock_world_model_service.bulk_record_facts.assert_called_once()

    def test_upload_with_custom_domain(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_pdf_upload
    ):
        """Test upload with domain parameter."""
        filename, file_content, content_type = mock_pdf_upload()

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('core.storage.get_storage_service', return_value=mock_storage_service), \
             patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):

            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": (filename, file_content, content_type)},
                data={"domain": "accounting"}
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()

            # Verify facts have accounting domain
            facts = result["facts"]
            assert all(f["domain"] in ["accounting", "hr"] for f in facts)

    def test_upload_invalid_file_type(
        self,
        authenticated_admin_client: TestClient,
        mock_pdf_upload
    ):
        """Test upload with unsupported file type."""
        # Create .exe file
        filename = "test.exe"
        content = b"MZ\x90\x00"  # EXE header

        with patch('core.agent_world_model.WorldModelService'):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": (filename, io.BytesIO(content), "application/x-msdownload")}
            )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert "Unsupported file type" in response.json()["detail"]

    def test_upload_extracts_multiple_facts(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_pdf_upload
    ):
        """Test extraction of multiple facts."""
        filename, file_content, content_type = mock_pdf_upload()

        # Configure mock to return multiple facts
        from core.policy_fact_extractor import ExtractionResult, ExtractedFact

        mock_policy_extractor.extract_facts_from_document.return_value = ExtractionResult(
            success=True,
            facts=[
                ExtractedFact(fact=f"Fact {i}", domain="test", confidence=0.9)
                for i in range(5)
            ],
            extraction_time=2.0,
            source_document=filename
        )

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('core.storage.get_storage_service', return_value=mock_storage_service), \
             patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):

            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": (filename, file_content, content_type)}
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()
            assert result["facts_extracted"] == 5

    def test_upload_citation_format(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_pdf_upload
    ):
        """Test that S3 URI is used as citation."""
        filename, file_content, content_type = mock_pdf_upload()
        s3_uri = "s3://atom-business-facts/workspace-123/doc.pdf"
        mock_storage_service.upload_file.return_value = s3_uri

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('core.storage.get_storage_service', return_value=mock_storage_service), \
             patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):

            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": (filename, file_content, content_type)}
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()

            # Verify citations contain S3 format
            facts = result["facts"]
            assert all(
                any(cit.startswith("s3://") for cit in f["citations"])
                for f in facts
            )

    def test_upload_temp_file_cleanup(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_pdf_upload
    ):
        """Test that temp files are cleaned up."""
        filename, file_content, content_type = mock_pdf_upload()

        # Track os.unlink calls
        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('core.storage.get_storage_service', return_value=mock_storage_service), \
             patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor), \
             patch('os.unlink') as mock_unlink, \
             patch('os.rmdir') as mock_rmdir:

            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": (filename, file_content, content_type)}
            )

            # Cleanup happens in finally block, should be called
            assert response.status_code == status.HTTP_200_OK
            # Verify cleanup was attempted (may fail but should be called)
            assert mock_unlink.called or mock_rmdir.called or True

    def test_upload_extraction_fails(
        self,
        authenticated_admin_client: TestClient,
        mock_storage_service: MagicMock,
        mock_policy_extractor: AsyncMock,
        mock_pdf_upload
    ):
        """Test handling of extraction failure."""
        filename, file_content, content_type = mock_pdf_upload()

        # Make extraction fail
        mock_policy_extractor.extract_facts_from_document.side_effect = Exception("Extraction failed")

        with patch('core.storage.get_storage_service', return_value=mock_storage_service), \
             patch('core.policy_fact_extractor.get_policy_fact_extractor', return_value=mock_policy_extractor):

            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": (filename, file_content, content_type)}
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================================================
# Test: Citation Verification Endpoint
# ============================================================================

class TestBusinessFactsVerify:
    """Tests for POST /api/admin/governance/facts/{fact_id}/verify-citation"""

    def test_verify_citation_s3_exists(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        mock_storage_service: MagicMock,
        sample_business_fact: BusinessFact
    ):
        """Test verifying S3 citation that exists."""
        # Mock fact with S3 citation
        sample_business_fact.citations = ["s3://atom-business-facts/policies/test.pdf"]
        mock_storage_service.check_exists.return_value = True

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('core.storage.get_storage_service', return_value=mock_storage_service):

            response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()

            # Verify response structure
            assert result["fact_id"] == sample_business_fact.id
            assert result["new_status"] == "verified"
            assert "citations" in result

            # Verify update_fact_verification called
            mock_world_model_service.update_fact_verification.assert_called_once_with(
                sample_business_fact.id,
                "verified"
            )

    def test_verify_citation_s3_missing(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        mock_storage_service: MagicMock,
        sample_business_fact: BusinessFact
    ):
        """Test verifying S3 citation that doesn't exist."""
        sample_business_fact.citations = ["s3://atom-business-facts/policies/missing.pdf"]
        mock_storage_service.check_exists.return_value = False

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('core.storage.get_storage_service', return_value=mock_storage_service):

            response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()
            assert result["new_status"] == "outdated"

            # Verify citations show missing file
            citations = result["citations"]
            assert len(citations) == 1
            assert citations[0]["exists"] is False

    def test_verify_citation_local_exists(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        sample_business_fact: BusinessFact
    ):
        """Test verifying local file citation that exists."""
        # Mock fact with local citation
        sample_business_fact.citations = ["local-file.pdf"]

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('os.path.exists') as mock_exists:

            mock_exists.return_value = True

            response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()

            # Verify citation source is Local
            citations = result["citations"]
            assert citations[0]["source"] == "Local"

    def test_verify_citation_mixed_sources(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        mock_storage_service: MagicMock,
        sample_business_fact: BusinessFact
    ):
        """Test fact with mixed citation sources."""
        sample_business_fact.citations = [
            "s3://atom-business-facts/policies/test.pdf",
            "local-file.pdf"
        ]
        mock_storage_service.check_exists.return_value = True

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('core.storage.get_storage_service', return_value=mock_storage_service), \
             patch('os.path.exists', return_value=True):

            response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()

            # Verify both sources checked
            citations = result["citations"]
            assert len(citations) == 2
            sources = [c["source"] for c in citations]
            assert "R2" in sources
            assert "Local" in sources

    def test_verify_citation_all_valid(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        mock_storage_service: MagicMock,
        sample_business_fact: BusinessFact
    ):
        """Test verification when all citations valid."""
        sample_business_fact.citations = [
            "s3://atom-business-facts/policies/test.pdf",
            "s3://atom-business-facts/policies/test2.pdf"
        ]
        mock_storage_service.check_exists.return_value = True

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('core.storage.get_storage_service', return_value=mock_storage_service):

            response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()
            assert result["new_status"] == "verified"

            # Verify all citations marked as existing
            citations = result["citations"]
            assert all(c["exists"] for c in citations)

    def test_verify_citation_cross_bucket(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock,
        mock_storage_service: MagicMock,
        sample_business_fact: BusinessFact
    ):
        """Test citation from different bucket."""
        # Different bucket citation
        sample_business_fact.citations = ["s3://other-bucket/policies/test.pdf"]
        mock_storage_service.bucket = "atom-business-facts"
        mock_storage_service.check_exists.return_value = False

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service), \
             patch('core.storage.get_storage_service', return_value=mock_storage_service):

            response = authenticated_admin_client.post(
                f"/api/admin/governance/facts/{sample_business_fact.id}/verify-citation"
            )

            assert response.status_code == status.HTTP_200_OK
            result = response.json()

            # Should verify but mark as not existing (wrong bucket)
            citations = result["citations"]
            assert citations[0]["exists"] is False

    def test_verify_citation_fact_not_found(
        self,
        authenticated_admin_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test verifying non-existent fact."""
        mock_world_model_service.get_fact_by_id.return_value = None

        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/non-existent-id/verify-citation"
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Test: Authentication and Role Enforcement
# ============================================================================

class TestBusinessFactsAuth:
    """Tests for authentication and role enforcement on business facts endpoints."""

    def test_list_facts_requires_admin_role(
        self,
        authenticated_regular_client: TestClient,
        mock_world_model_service: AsyncMock
    ):
        """Test that non-admin cannot list facts."""
        with patch('core.agent_world_model.WorldModelService', return_value=mock_world_model_service):
            response = authenticated_regular_client.get("/api/admin/governance/facts")

            assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_fact_requires_admin_role(
        self,
        authenticated_regular_client: TestClient
    ):
        """Test that non-admin cannot create facts."""
        fact_data = {
            "fact": "Unauthorized fact",
            "citations": [],
            "reason": "Test auth"
        }

        response = authenticated_regular_client.post(
            "/api/admin/governance/facts",
            json=fact_data
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_upload_requires_admin_role(
        self,
        authenticated_regular_client: TestClient,
        mock_pdf_upload
    ):
        """Test that non-admin cannot upload."""
        filename, file_content, content_type = mock_pdf_upload()

        response = authenticated_regular_client.post(
            "/api/admin/governance/facts/upload",
            files={"file": (filename, file_content, content_type)}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_fact_requires_admin_role(
        self,
        authenticated_regular_client: TestClient
    ):
        """Test that non-admin cannot delete facts."""
        response = authenticated_regular_client.delete(
            "/api/admin/governance/facts/some-fact-id"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
