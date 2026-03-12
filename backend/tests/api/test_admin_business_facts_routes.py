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
