"""
Artifact Routes Test Suite

Comprehensive test coverage for artifact version control routes (artifact_routes.py).

Target Coverage: 75%+ line coverage for api/artifact_routes.py

Scope:
- Artifact listing with filters (session_id, type, workspace_id)
- Artifact creation (save) with optional fields
- Artifact updates with versioning (version records created)
- Artifact version history retrieval
- Authentication required for all endpoints
- Error paths (validation 422, not found 404)

Test Fixtures:
- In-memory SQLite database with StaticPool
- Mock User object (NOT real model - avoids SQLAlchemy relationship issues)
- TestClient with auth and DB overrides
- Factory fixtures for test data

External Services: None (all tests use database)
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import router and models
from api.artifact_routes import router
from core.models import Base, Artifact, ArtifactVersion
from core.database import get_db
from core.security_dependencies import get_current_user


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
def mock_user():
    """
    Mock User object for authentication.

    Using MagicMock instead of real User model avoids SQLAlchemy relationship issues
    (Artifact.author relationship causes NoForeignKeysError with real User instances).
    """
    user = MagicMock(spec=["id", "email", "created_at"])
    user.id = "test_user_1"
    user.email = "test@example.com"
    user.created_at = datetime.now()
    return user


@pytest.fixture(scope="function")
def authenticated_client(test_db, mock_user):
    """
    TestClient with authentication and database overrides.

    This fixture overrides both get_current_user (returns mock_user) and get_db (returns test_db),
    allowing authenticated requests to the artifact routes.
    """
    app = FastAPI()
    app.include_router(router)

    # Override dependencies
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)

    yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def unauthenticated_client(test_db):
    """
    TestClient without authentication override.

    This fixture overrides get_db but NOT get_current_user, triggering 401 Unauthorized responses.
    """
    app = FastAPI()
    app.include_router(router)

    # Override only database dependency
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # DO NOT override get_current_user - this triggers authentication error

    client = TestClient(app)

    yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sample_artifact_data():
    """
    Factory for valid ArtifactCreate request data.

    Returns a dict with all fields for creating an artifact.
    """
    return {
        "name": "test_artifact",
        "type": "code",
        "content": "print('hello world')",
        "metadata_json": {"language": "python"},
        "session_id": "test_session_1",
        "agent_id": "test_agent_1"
    }


@pytest.fixture(scope="function")
def sample_artifact(test_db, mock_user):
    """
    Artifact model fixture for database insertion.

    Creates a real Artifact instance in the database for testing.
    """
    artifact = Artifact(
        id="test_artifact_1",
        workspace_id="default",
        agent_id="test_agent_1",
        session_id="test_session_1",
        name="Test Artifact",
        type="code",
        content="print('hello')",
        metadata_json={"language": "python"},
        version=1,
        is_locked=False,
        author_id=mock_user.id,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    test_db.add(artifact)
    test_db.commit()
    test_db.refresh(artifact)
    return artifact


# ============================================================================
# Test Artifact List
# ============================================================================

class TestArtifactList:
    """Test artifact listing endpoint with various filters."""

    def test_list_artifacts_success(self, authenticated_client, test_db, mock_user):
        """Test listing all artifacts returns 200 with artifact list."""
        # Create 3 test artifacts
        for i in range(3):
            artifact = Artifact(
                id=f"artifact_{i}",
                workspace_id="default",
                name=f"Artifact {i}",
                type="code",
                content=f"content_{i}",
                version=1,
                author_id=mock_user.id
            )
            test_db.add(artifact)
        test_db.commit()

        # List artifacts
        response = authenticated_client.get("/api/artifacts/")

        assert response.status_code == 200
        artifacts = response.json()
        assert len(artifacts) == 3
        assert all(a["workspace_id"] == "default" for a in artifacts)

    def test_list_artifacts_filter_by_session(self, authenticated_client, test_db, mock_user):
        """Test filtering artifacts by session_id."""
        # Create artifacts with different session_id values
        artifact1 = Artifact(
            id="artifact_1",
            workspace_id="default",
            session_id="session_A",
            name="Artifact A",
            type="code",
            content="content_A",
            version=1,
            author_id=mock_user.id
        )
        artifact2 = Artifact(
            id="artifact_2",
            workspace_id="default",
            session_id="session_B",
            name="Artifact B",
            type="code",
            content="content_B",
            version=1,
            author_id=mock_user.id
        )
        test_db.add_all([artifact1, artifact2])
        test_db.commit()

        # Filter by session_id
        response = authenticated_client.get("/api/artifacts/?session_id=session_A")

        assert response.status_code == 200
        artifacts = response.json()
        assert len(artifacts) == 1
        assert artifacts[0]["session_id"] == "session_A"

    def test_list_artifacts_filter_by_type(self, authenticated_client, test_db, mock_user):
        """Test filtering artifacts by type."""
        # Create artifacts with different types
        artifact1 = Artifact(
            id="artifact_1",
            workspace_id="default",
            name="Code Artifact",
            type="code",
            content="python code",
            version=1,
            author_id=mock_user.id
        )
        artifact2 = Artifact(
            id="artifact_2",
            workspace_id="default",
            name="Markdown Artifact",
            type="markdown",
            content="# markdown",
            version=1,
            author_id=mock_user.id
        )
        test_db.add_all([artifact1, artifact2])
        test_db.commit()

        # Filter by type
        response = authenticated_client.get("/api/artifacts/?type=code")

        assert response.status_code == 200
        artifacts = response.json()
        assert len(artifacts) == 1
        assert artifacts[0]["type"] == "code"

    def test_list_artifacts_combined_filters(self, authenticated_client, test_db, mock_user):
        """Test filtering artifacts by both session_id and type."""
        # Create artifacts with mixed attributes
        artifact1 = Artifact(
            id="artifact_1",
            workspace_id="default",
            session_id="session_A",
            name="Code A",
            type="code",
            content="code_A",
            version=1,
            author_id=mock_user.id
        )
        artifact2 = Artifact(
            id="artifact_2",
            workspace_id="default",
            session_id="session_A",
            name="Markdown A",
            type="markdown",
            content="md_A",
            version=1,
            author_id=mock_user.id
        )
        artifact3 = Artifact(
            id="artifact_3",
            workspace_id="default",
            session_id="session_B",
            name="Code B",
            type="code",
            content="code_B",
            version=1,
            author_id=mock_user.id
        )
        test_db.add_all([artifact1, artifact2, artifact3])
        test_db.commit()

        # Filter by both session_id and type
        response = authenticated_client.get("/api/artifacts/?session_id=session_A&type=code")

        assert response.status_code == 200
        artifacts = response.json()
        assert len(artifacts) == 1
        assert artifacts[0]["session_id"] == "session_A"
        assert artifacts[0]["type"] == "code"

    def test_list_artifacts_empty(self, authenticated_client, test_db):
        """Test listing artifacts when database is empty."""
        # No artifacts in database
        response = authenticated_client.get("/api/artifacts/")

        assert response.status_code == 200
        artifacts = response.json()
        assert len(artifacts) == 0


# ============================================================================
# Test Artifact Save
# ============================================================================

class TestArtifactSave:
    """Test artifact creation (save) endpoint."""

    def test_save_artifact_success(self, authenticated_client, sample_artifact_data):
        """Test creating an artifact with valid data returns 200."""
        response = authenticated_client.post("/api/artifacts/", json=sample_artifact_data)

        assert response.status_code == 200
        artifact = response.json()
        assert "id" in artifact
        assert artifact["name"] == sample_artifact_data["name"]
        assert artifact["type"] == sample_artifact_data["type"]
        assert artifact["content"] == sample_artifact_data["content"]
        assert artifact["version"] == 1
        assert artifact["workspace_id"] == "default"

    def test_save_artifact_with_agent_id(self, authenticated_client, sample_artifact_data):
        """Test creating artifact with agent_id field."""
        response = authenticated_client.post("/api/artifacts/", json=sample_artifact_data)

        assert response.status_code == 200
        artifact = response.json()
        assert artifact["agent_id"] == sample_artifact_data["agent_id"]

    def test_save_artifact_with_metadata(self, authenticated_client, sample_artifact_data):
        """Test creating artifact with metadata_json field."""
        response = authenticated_client.post("/api/artifacts/", json=sample_artifact_data)

        assert response.status_code == 200
        artifact = response.json()
        assert artifact["metadata_json"] == sample_artifact_data["metadata_json"]

    def test_save_artifact_minimal(self, authenticated_client):
        """Test creating artifact with only required fields."""
        minimal_data = {
            "name": "minimal_artifact",
            "type": "markdown",
            "content": "# Minimal"
        }

        response = authenticated_client.post("/api/artifacts/", json=minimal_data)

        assert response.status_code == 200
        artifact = response.json()
        assert artifact["name"] == "minimal_artifact"
        assert artifact["version"] == 1
        assert artifact["workspace_id"] == "default"
        # Optional fields should be None or default
        assert artifact["session_id"] is None

    def test_save_artifact_author_assigned(self, authenticated_client, mock_user, sample_artifact_data):
        """Test that author_id is set to authenticated user ID."""
        response = authenticated_client.post("/api/artifacts/", json=sample_artifact_data)

        assert response.status_code == 200
        artifact = response.json()
        assert artifact["author_id"] == mock_user.id


# ============================================================================
# Test Artifact Update
# ============================================================================

class TestArtifactUpdate:
    """Test artifact update endpoint with versioning."""

    def test_update_artifact_name(self, authenticated_client, test_db, sample_artifact):
        """Test updating artifact name increments version."""
        update_data = {
            "id": sample_artifact.id,
            "name": "Updated Artifact Name"
        }

        response = authenticated_client.post("/api/artifacts/update", json=update_data)

        assert response.status_code == 200
        artifact = response.json()
        assert artifact["name"] == "Updated Artifact Name"
        assert artifact["version"] == 2  # Version incremented

    def test_update_artifact_content(self, authenticated_client, test_db, sample_artifact):
        """Test updating artifact content increments version."""
        update_data = {
            "id": sample_artifact.id,
            "content": "print('updated content')"
        }

        response = authenticated_client.post("/api/artifacts/update", json=update_data)

        assert response.status_code == 200
        artifact = response.json()
        assert artifact["content"] == "print('updated content')"
        assert artifact["version"] == 2

    def test_update_artifact_metadata(self, authenticated_client, test_db, sample_artifact):
        """Test updating artifact metadata increments version."""
        new_metadata = {"language": "python", "version": "3.11"}
        update_data = {
            "id": sample_artifact.id,
            "metadata_json": new_metadata
        }

        response = authenticated_client.post("/api/artifacts/update", json=update_data)

        assert response.status_code == 200
        artifact = response.json()
        assert artifact["metadata_json"] == new_metadata
        assert artifact["version"] == 2

    def test_update_creates_version_record(self, authenticated_client, test_db, sample_artifact, mock_user):
        """Test that update creates ArtifactVersion record with old content."""
        # Verify initial state
        assert sample_artifact.version == 1
        assert sample_artifact.content == "print('hello')"

        # Update content
        update_data = {
            "id": sample_artifact.id,
            "content": "print('updated')"
        }

        response = authenticated_client.post("/api/artifacts/update", json=update_data)

        assert response.status_code == 200

        # Verify artifact updated
        updated_artifact = test_db.query(Artifact).filter(Artifact.id == sample_artifact.id).first()
        assert updated_artifact.version == 2
        assert updated_artifact.content == "print('updated')"

        # Verify ArtifactVersion record created
        versions = test_db.query(ArtifactVersion).filter(
            ArtifactVersion.artifact_id == sample_artifact.id
        ).all()
        assert len(versions) == 1
        assert versions[0].version == 1  # Old version stored
        assert versions[0].content == "print('hello')"  # Old content stored

    def test_update_multiple_fields(self, authenticated_client, test_db, sample_artifact):
        """Test updating name, content, and metadata together."""
        update_data = {
            "id": sample_artifact.id,
            "name": "Multi Update",
            "content": "new content",
            "metadata_json": {"key": "value"}
        }

        response = authenticated_client.post("/api/artifacts/update", json=update_data)

        assert response.status_code == 200
        artifact = response.json()
        assert artifact["name"] == "Multi Update"
        assert artifact["content"] == "new content"
        assert artifact["metadata_json"] == {"key": "value"}
        assert artifact["version"] == 2

        # Verify single version record created
        versions = test_db.query(ArtifactVersion).filter(
            ArtifactVersion.artifact_id == sample_artifact.id
        ).all()
        assert len(versions) == 1


# ============================================================================
# Test Artifact Versions
# ============================================================================

class TestArtifactVersions:
    """Test artifact version history retrieval."""

    def test_get_artifact_versions_success(self, authenticated_client, test_db, sample_artifact):
        """Test retrieving version history returns all versions ordered desc."""
        # Update artifact twice to create 2 version records
        for i in range(2):
            update_data = {
                "id": sample_artifact.id,
                "content": f"update_{i}"
            }
            authenticated_client.post("/api/artifacts/update", json=update_data)

        # Get versions
        response = authenticated_client.get(f"/api/artifacts/{sample_artifact.id}/versions")

        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 2
        # Verify ordered by version desc (version 2, then version 1)
        assert versions[0]["version"] == 2
        assert versions[1]["version"] == 1

    def test_get_artifact_versions_empty(self, authenticated_client, sample_artifact):
        """Test retrieving versions for artifact with no updates."""
        # Artifact never updated - no version records
        response = authenticated_client.get(f"/api/artifacts/{sample_artifact.id}/versions")

        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 0

    def test_get_artifact_versions_content_preserved(self, authenticated_client, test_db, sample_artifact):
        """Test that version records preserve old content."""
        # Store original content
        original_content = sample_artifact.content

        # Update artifact
        update_data = {
            "id": sample_artifact.id,
            "content": "updated content"
        }
        authenticated_client.post("/api/artifacts/update", json=update_data)

        # Get versions
        response = authenticated_client.get(f"/api/artifacts/{sample_artifact.id}/versions")

        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 1

        # Verify version record has old content
        assert versions[0]["content"] == original_content

        # Verify current artifact has new content
        current_artifact = test_db.query(Artifact).filter(Artifact.id == sample_artifact.id).first()
        assert current_artifact.content == "updated content"


# ============================================================================
# Test Artifact Authentication
# ============================================================================

class TestArtifactAuth:
    """Test that all artifact endpoints require authentication."""

    def test_list_requires_auth(self, unauthenticated_client):
        """Test GET /api/artifacts/ requires authentication."""
        response = unauthenticated_client.get("/api/artifacts/")

        assert response.status_code == 401

    def test_save_requires_auth(self, unauthenticated_client):
        """Test POST /api/artifacts/ requires authentication."""
        artifact_data = {
            "name": "test",
            "type": "code",
            "content": "test content"
        }
        response = unauthenticated_client.post("/api/artifacts/", json=artifact_data)

        assert response.status_code == 401

    def test_update_requires_auth(self, unauthenticated_client):
        """Test POST /api/artifacts/update requires authentication."""
        update_data = {
            "id": "some_id",
            "name": "updated"
        }
        response = unauthenticated_client.post("/api/artifacts/update", json=update_data)

        assert response.status_code == 401

    def test_versions_requires_auth(self, unauthenticated_client):
        """Test GET /api/artifacts/{id}/versions requires authentication."""
        response = unauthenticated_client.get("/api/artifacts/some_id/versions")

        assert response.status_code == 401


# ============================================================================
# Test Artifact Error Paths
# ============================================================================

class TestArtifactErrorPaths:
    """Test error handling for artifact endpoints."""

    def test_save_missing_name(self, authenticated_client):
        """Test POST /api/artifacts/ without name returns 422."""
        invalid_data = {
            "type": "code",
            "content": "test"
        }
        response = authenticated_client.post("/api/artifacts/", json=invalid_data)

        assert response.status_code == 422

    def test_save_missing_type(self, authenticated_client):
        """Test POST /api/artifacts/ without type returns 422."""
        invalid_data = {
            "name": "test",
            "content": "test"
        }
        response = authenticated_client.post("/api/artifacts/", json=invalid_data)

        assert response.status_code == 422

    def test_update_artifact_not_found(self, authenticated_client):
        """Test POST /api/artifacts/update with invalid ID returns 404."""
        update_data = {
            "id": "nonexistent_artifact_id",
            "name": "updated"
        }
        response = authenticated_client.post("/api/artifacts/update", json=update_data)

        assert response.status_code == 404

    def test_update_empty_request(self, authenticated_client, test_db, sample_artifact):
        """Test POST /api/artifacts/update with no changes."""
        # Original content
        original_name = sample_artifact.name

        # Send update with only ID (no actual changes)
        update_data = {
            "id": sample_artifact.id
        }
        response = authenticated_client.post("/api/artifacts/update", json=update_data)

        # Should succeed (200) but not change anything
        assert response.status_code == 200
        artifact = test_db.query(Artifact).filter(Artifact.id == sample_artifact.id).first()
        assert artifact.name == original_name

    def test_get_versions_not_found(self, authenticated_client):
        """Test GET /api/artifacts/{invalid_id}/versions with non-existent artifact."""
        response = authenticated_client.get("/api/artifacts/nonexistent_id/versions")

        # Returns empty list for non-existent artifact (no 404)
        assert response.status_code == 200
        versions = response.json()
        assert len(versions) == 0

    def test_update_invalid_id_format(self, authenticated_client):
        """Test POST /api/artifacts/update with malformed ID."""
        # Even malformed ID format returns 404 (artifact not found)
        update_data = {
            "id": "invalid_uuid_format",
            "name": "updated"
        }
        response = authenticated_client.post("/api/artifacts/update", json=update_data)

        assert response.status_code == 404
