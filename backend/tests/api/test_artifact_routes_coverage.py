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
