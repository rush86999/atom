"""
Episode Routes Integration Tests

Tests for episode management endpoints from api/episode_routes.py.

Coverage (ported to the current episodic-memory API surface):
- POST /api/episodes/create - Create episode from session
- GET /api/episodes/retrieve/{episode_id} - Sequential episode retrieval
- GET /api/episodes/{agent_id}/list - List episodes with pagination
- POST /api/episodes/retrieve/temporal - Temporal retrieval
- POST /api/episodes/retrieve/semantic - Semantic retrieval
- POST /api/episodes/retrieve/by-canvas-type - Canvas type filtered retrieval
- POST /api/episodes/{episode_id}/feedback - Submit feedback
- Authentication/authorization
- Retrieval functionality
- Pagination
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.episode_routes import router
from core.models import AgentRegistry, Episode, EpisodeSegment, User


# ============================================================================
# Fixtures
# ============================================================================

_current_test_user = None


@pytest.fixture
def app_with_overrides(db: Session):
    """Create FastAPI app with dependency overrides for episode routes."""
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.database import get_db

    def override_get_db():
        yield db

    def override_get_current_user():
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    # episode_routes resolves get_current_user from core.security_dependencies
    from core.security_dependencies import get_current_user
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield app

    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def client(app_with_overrides: FastAPI):
    """Create TestClient for episode routes."""
    return TestClient(app_with_overrides, raise_server_exceptions=False)


@pytest.fixture
def mock_user(db: Session):
    """Create test user."""
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        first_name="Test",
        last_name="User",
        role="member",
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def mock_agent(db: Session):
    """Create an AUTONOMOUS agent owning the episodes."""
    import uuid
    agent_id = str(uuid.uuid4())
    agent = AgentRegistry(
        id=agent_id,
        name=f"Episode Agent {agent_id[:8]}",
        category="testing",
        status="autonomous",
        confidence_score=0.95,
        module_path="test.module",
        class_name="TestClass"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture
def mock_episode(db: Session, mock_agent: AgentRegistry):
    """Create a persisted episode with one segment."""
    import uuid
    episode = Episode(
        id=str(uuid.uuid4()),
        agent_id=mock_agent.id,
        tenant_id="default",
        task_description="Test Episode",
        maturity_at_time="autonomous",
        outcome="success",
        success=True,
        status="completed",
        session_id="session-1",
        canvas_ids=[],
        feedback_ids=[],
    )
    db.add(episode)
    db.flush()

    segment = EpisodeSegment(
        episode_id=episode.id,
        segment_type="execution",
        sequence_order=0,
        content="Segment 1 content",
    )
    db.add(segment)
    db.commit()
    db.refresh(episode)
    return episode


@pytest.fixture
def mock_episode_id():
    """Create mock episode ID."""
    import uuid
    return str(uuid.uuid4())


# ============================================================================
# POST /api/episodes/create - Create Episode Tests
# ============================================================================

def test_create_episode_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating episode successfully."""
    global _current_test_user
    _current_test_user = mock_user

    import uuid
    episode_data = {
        "session_id": "session-123",
        "agent_id": str(uuid.uuid4()),
        "title": "Test Episode"
    }

    mock_episode_obj = MagicMock()
    mock_episode_obj.id = str(uuid.uuid4())
    mock_episode_obj.task_description = "Test Episode"
    mock_episode_obj.status = "active"

    with patch('api.episode_routes.EpisodeSegmentationService') as mock_seg:
        mock_service = MagicMock()
        mock_service.create_episode_from_session = AsyncMock(return_value=mock_episode_obj)
        mock_seg.return_value = mock_service

        response = client.post("/api/episodes/create", json=episode_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["episode_id"] == mock_episode_obj.id
        mock_service.create_episode_from_session.assert_awaited_once_with(
            session_id="session-123",
            agent_id=episode_data["agent_id"],
            title="Test Episode"
        )


def test_create_episode_invalid_schema(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating episode with invalid schema."""
    global _current_test_user
    _current_test_user = mock_user

    # Missing required fields (session_id, agent_id)
    episode_data = {
        "title": "Incomplete Episode"
    }

    response = client.post("/api/episodes/create", json=episode_data)

    assert response.status_code == 422


def test_create_episode_service_failure(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating episode when segmentation cannot build one."""
    global _current_test_user
    _current_test_user = mock_user

    import uuid
    episode_data = {
        "session_id": "session-404",
        "agent_id": str(uuid.uuid4()),
    }

    with patch('api.episode_routes.EpisodeSegmentationService') as mock_seg:
        mock_service = MagicMock()
        mock_service.create_episode_from_session = AsyncMock(return_value=None)
        mock_seg.return_value = mock_service

        response = client.post("/api/episodes/create", json=episode_data)

        assert response.status_code == 400
        error_body = response.json().get("detail", response.json())
        assert error_body["success"] is False


# ============================================================================
# GET /api/episodes/retrieve/{episode_id} - Sequential Retrieval Tests
# ============================================================================

def test_get_episode_success(
    client: TestClient,
    db: Session,
    mock_episode: Episode,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test getting episode (with segments) successfully."""
    global _current_test_user
    _current_test_user = mock_user

    response = client.get(
        f"/api/episodes/retrieve/{mock_episode.id}",
        params={"agent_id": mock_agent.id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["episode"]["id"] == mock_episode.id
    assert data["episode"]["title"] == "Test Episode"
    assert isinstance(data["segments"], list)
    assert len(data["segments"]) == 1
    assert data["segments"][0]["content"] == "Segment 1 content"


def test_get_episode_not_found(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test getting non-existent episode returns the error payload."""
    global _current_test_user
    _current_test_user = mock_user

    import uuid
    non_existent_id = str(uuid.uuid4())

    response = client.get(
        f"/api/episodes/retrieve/{non_existent_id}",
        params={"agent_id": mock_agent.id},
    )

    # Service contract: missing episodes yield {"error": "Episode not found"}
    assert response.status_code == 200
    assert response.json() == {"error": "Episode not found"}


# ============================================================================
# GET /api/episodes/{agent_id}/list - List Episodes Tests
# ============================================================================

def test_list_episodes_success(
    client: TestClient,
    db: Session,
    mock_episode: Episode,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test listing episodes successfully."""
    global _current_test_user
    _current_test_user = mock_user

    response = client.get(f"/api/episodes/{mock_agent.id}/list")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) == 1
    assert data["data"][0]["id"] == mock_episode.id
    assert data["data"][0]["title"] == "Test Episode"
    assert data["metadata"]["count"] == 1


def test_list_episodes_with_pagination(
    client: TestClient,
    db: Session,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test listing episodes with pagination."""
    global _current_test_user
    _current_test_user = mock_user

    # Seed two episodes; pagination window of 1 should return a single row.
    import uuid
    for i in range(2):
        db.add(Episode(
            id=str(uuid.uuid4()),
            agent_id=mock_agent.id,
            tenant_id="default",
            task_description=f"Episode {i}",
            maturity_at_time="autonomous",
            outcome="success",
            success=True,
            status="completed",
        ))
    db.commit()

    response = client.get(f"/api/episodes/{mock_agent.id}/list", params={"skip": 0, "limit": 1})

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


# ============================================================================
# POST /api/episodes/retrieve/temporal - Temporal Retrieval Tests
# ============================================================================

def test_search_episodes_temporal(
    client: TestClient,
    db: Session,
    mock_episode: Episode,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test retrieving episodes with temporal filter."""
    global _current_test_user
    _current_test_user = mock_user

    search_data = {
        "agent_id": mock_agent.id,
        "time_range": "30d",
        "limit": 10
    }

    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.retrieve_temporal = AsyncMock(return_value={
            "episodes": [{"id": mock_episode.id}],
            "count": 1,
            "time_range": "30d"
        })
        mock_ret.return_value = mock_service

        response = client.post("/api/episodes/retrieve/temporal", json=search_data)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        mock_service.retrieve_temporal.assert_awaited_once_with(
            agent_id=mock_agent.id,
            time_range="30d",
            user_id=mock_user.id,
            limit=10
        )


# ============================================================================
# POST /api/episodes/retrieve/semantic - Semantic Retrieval Tests
# ============================================================================

def test_search_episodes_semantic(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test retrieving episodes with semantic search."""
    global _current_test_user
    _current_test_user = mock_user

    import uuid
    search_data = {
        "agent_id": str(uuid.uuid4()),
        "query": "workflow automation",
        "limit": 10
    }

    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.retrieve_semantic = AsyncMock(return_value={
            "episodes": [],
            "count": 0,
            "query": "workflow automation"
        })
        mock_ret.return_value = mock_service

        response = client.post("/api/episodes/retrieve/semantic", json=search_data)

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "workflow automation"
        mock_service.retrieve_semantic.assert_awaited_once_with(
            agent_id=search_data["agent_id"],
            query="workflow automation",
            limit=10
        )


# ============================================================================
# POST /api/episodes/retrieve/by-canvas-type - Canvas Type Filter Tests
# ============================================================================

def test_search_episodes_canvas_type_filter(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test retrieving episodes filtered by canvas type."""
    global _current_test_user
    _current_test_user = mock_user

    import uuid
    search_data = {
        "agent_id": str(uuid.uuid4()),
        "canvas_type": "sheets",
        "action": "present",
        "time_range": "30d",
        "limit": 20
    }

    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.retrieve_by_canvas_type = AsyncMock(return_value={
            "episodes": [],
            "count": 0,
            "canvas_type": "sheets"
        })
        mock_ret.return_value = mock_service

        response = client.post("/api/episodes/retrieve/by-canvas-type", json=search_data)

        assert response.status_code == 200
        data = response.json()
        assert data["canvas_type"] == "sheets"
        mock_service.retrieve_by_canvas_type.assert_awaited_once_with(
            agent_id=search_data["agent_id"],
            canvas_type="sheets",
            action="present",
            time_range="30d",
            limit=20
        )


# ============================================================================
# POST /api/episodes/{episode_id}/feedback - Feedback Tests
# (ports the old update/delete mutation coverage onto the current
#  episode-mutation endpoint)
# ============================================================================

def test_submit_feedback_success(
    client: TestClient,
    db: Session,
    mock_episode: Episode,
    mock_user: User
):
    """Test submitting feedback for an episode successfully."""
    global _current_test_user
    _current_test_user = mock_user

    feedback_data = {"feedback_score": 0.8}

    with patch('api.episode_routes.EpisodeLifecycleService') as mock_life:
        mock_service = MagicMock()
        mock_service.update_importance_scores = AsyncMock(return_value=True)
        mock_life.return_value = mock_service

        response = client.post(
            f"/api/episodes/{mock_episode.id}/feedback", json=feedback_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["updated"] is True
        mock_service.update_importance_scores.assert_awaited_once_with(
            mock_episode.id, 0.8
        )


# ============================================================================
# Response Format Tests
# ============================================================================

def test_list_episodes_response_format(
    client: TestClient,
    db: Session,
    mock_episode: Episode,
    mock_agent: AgentRegistry,
    mock_user: User
):
    """Test list episodes has correct response format."""
    global _current_test_user
    _current_test_user = mock_user

    response = client.get(f"/api/episodes/{mock_agent.id}/list")

    data = response.json()
    assert isinstance(data, dict)
    assert "success" in data
    assert "data" in data
    assert "metadata" in data
    assert isinstance(data["data"], list)


def test_search_episodes_response_format(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test search episodes has correct response format."""
    global _current_test_user
    _current_test_user = mock_user

    import uuid
    search_data = {
        "agent_id": str(uuid.uuid4()),
        "time_range": "7d"
    }

    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.retrieve_temporal = AsyncMock(return_value={
            "episodes": [],
            "count": 0
        })
        mock_ret.return_value = mock_service

        response = client.post("/api/episodes/retrieve/temporal", json=search_data)

        data = response.json()
        assert isinstance(data, dict)
        assert "episodes" in data
