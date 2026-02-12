"""
Episode Routes Integration Tests

Tests for episode management endpoints from api/episode_routes.py.

Coverage:
- POST /episodes - Create episode
- GET /episodes/{episode_id} - Get episode
- GET /episodes - List episodes
- POST /episodes/search - Search episodes
- PUT /episodes/{episode_id} - Update episode
- DELETE /episodes/{episode_id} - Delete episode
- POST /episodes/{episode_id}/segments - Add segment
- GET /episodes/{episode_id}/segments - Get segments
- Authentication/authorization
- CRUD operations
- Search functionality
- Pagination
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.episode_routes import router
from core.models import User


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create TestClient for episode routes."""
    return TestClient(router)


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
def mock_episode_id():
    """Create mock episode ID."""
    import uuid
    return str(uuid.uuid4())


# ============================================================================
# POST /episodes - Create Episode Tests
# ============================================================================

def test_create_episode_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating episode successfully."""
    import uuid
    episode_data = {
        "agent_id": str(uuid.uuid4()),
        "title": "Test Episode",
        "summary": "This is a test episode",
        "segments": [
            {
                "content": "Segment 1 content",
                "segment_type": "action"
            }
        ]
    }

    with patch('api.episode_routes.EpisodeSegmentationService') as mock_seg:
        mock_service = MagicMock()
        mock_service.create_episode.return_value = {
            "success": True,
            "episode_id": str(uuid.uuid4())
        }
        mock_seg.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/episodes", json=episode_data)

            assert response.status_code in [200, 201]


def test_create_episode_invalid_schema(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test creating episode with invalid schema."""
    # Missing required fields
    episode_data = {
        "title": "Incomplete Episode"
    }

    with patch('api.episode_routes.get_current_user') as mock_auth:
        mock_auth.return_value = mock_user

        response = client.post("/episodes", json=episode_data)

        assert response.status_code == 422


# ============================================================================
# GET /episodes/{episode_id} - Get Episode Tests
# ============================================================================

def test_get_episode_success(
    client: TestClient,
    db: Session,
    mock_episode_id: str,
    mock_user: User
):
    """Test getting episode successfully."""
    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.get_episode.return_value = {
            "id": mock_episode_id,
            "title": "Test Episode",
            "segments": []
        }
        mock_ret.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get(f"/episodes/{mock_episode_id}")

            assert response.status_code == 200


def test_get_episode_not_found(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test getting non-existent episode."""
    import uuid
    non_existent_id = str(uuid.uuid4())

    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.get_episode.return_value = None
        mock_ret.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get(f"/episodes/{non_existent_id}")

            assert response.status_code == 404


# ============================================================================
# GET /episodes - List Episodes Tests
# ============================================================================

def test_list_episodes_success(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test listing episodes successfully."""
    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.list_episodes.return_value = {
            "episodes": [],
            "total": 0
        }
        mock_ret.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/episodes")

            assert response.status_code == 200


def test_list_episodes_with_pagination(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test listing episodes with pagination."""
    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.list_episodes.return_value = {
            "episodes": [],
            "total": 0,
            "limit": 10,
            "offset": 0
        }
        mock_ret.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/episodes?limit=10&offset=0")

            assert response.status_code == 200


# ============================================================================
# POST /episodes/search - Search Episodes Tests
# ============================================================================

def test_search_episodes_temporal(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test searching episodes with temporal filter."""
    search_data = {
        "search_type": "temporal",
        "start_date": "2026-01-01T00:00:00Z",
        "end_date": "2026-12-31T23:59:59Z"
    }

    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.search_episodes.return_value = {
            "episodes": [],
            "total": 0
        }
        mock_ret.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/episodes/search", json=search_data)

            assert response.status_code == 200


def test_search_episodes_semantic(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test searching episodes with semantic search."""
    search_data = {
        "search_type": "semantic",
        "query": "workflow automation",
        "limit": 10
    }

    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.search_episodes.return_value = {
            "episodes": [],
            "total": 0
        }
        mock_ret.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/episodes/search", json=search_data)

            assert response.status_code == 200


def test_search_episodes_canvas_type_filter(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test searching episodes with canvas type filter."""
    search_data = {
        "search_type": "contextual",
        "canvas_type": "form",
        "limit": 20
    }

    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.search_episodes.return_value = {
            "episodes": [],
            "total": 0
        }
        mock_ret.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/episodes/search", json=search_data)

            assert response.status_code == 200


# ============================================================================
# PUT /episodes/{episode_id} - Update Episode Tests
# ============================================================================

def test_update_episode_success(
    client: TestClient,
    db: Session,
    mock_episode_id: str,
    mock_user: User
):
    """Test updating episode successfully."""
    update_data = {
        "title": "Updated Episode Title",
        "summary": "Updated summary"
    }

    with patch('api.episode_routes.EpisodeSegmentationService') as mock_seg:
        mock_service = MagicMock()
        mock_service.update_episode.return_value = {
            "success": True
        }
        mock_seg.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.put(f"/episodes/{mock_episode_id}", json=update_data)

            assert response.status_code == 200


# ============================================================================
# DELETE /episodes/{episode_id} - Delete Episode Tests
# ============================================================================

def test_delete_episode_success(
    client: TestClient,
    db: Session,
    mock_episode_id: str,
    mock_user: User
):
    """Test deleting episode successfully."""
    with patch('api.episode_routes.EpisodeLifecycleService') as mock_life:
        mock_service = MagicMock()
        mock_service.delete_episode.return_value = {
            "success": True
        }
        mock_life.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.delete(f"/episodes/{mock_episode_id}")

            assert response.status_code in [200, 204]


# ============================================================================
# POST /episodes/{episode_id}/segments - Add Segment Tests
# ============================================================================

def test_add_segment_success(
    client: TestClient,
    db: Session,
    mock_episode_id: str,
    mock_user: User
):
    """Test adding segment to episode successfully."""
    segment_data = {
        "content": "New segment content",
        "segment_type": "action",
        "metadata": {}
    }

    with patch('api.episode_routes.EpisodeSegmentationService') as mock_seg:
        mock_service = MagicMock()
        mock_service.add_segment.return_value = {
            "success": True,
            "segment_id": "segment-123"
        }
        mock_seg.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post(f"/episodes/{mock_episode_id}/segments", json=segment_data)

            assert response.status_code == 200


# ============================================================================
# GET /episodes/{episode_id}/segments - Get Segments Tests
# ============================================================================

def test_get_segments_success(
    client: TestClient,
    db: Session,
    mock_episode_id: str,
    mock_user: User
):
    """Test getting episode segments successfully."""
    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.get_segments.return_value = {
            "segments": [],
            "total": 0
        }
        mock_ret.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get(f"/episodes/{mock_episode_id}/segments")

            assert response.status_code == 200


# ============================================================================
# Response Format Tests
# ============================================================================

def test_list_episodes_response_format(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test list episodes has correct response format."""
    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.list_episodes.return_value = {
            "episodes": [],
            "total": 0
        }
        mock_ret.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.get("/episodes")

        data = response.json()
        assert isinstance(data, dict) and "episodes" in data or isinstance(data, list)


def test_search_episodes_response_format(
    client: TestClient,
    db: Session,
    mock_user: User
):
    """Test search episodes has correct response format."""
    search_data = {
        "search_type": "temporal"
    }

    with patch('api.episode_routes.EpisodeRetrievalService') as mock_ret:
        mock_service = MagicMock()
        mock_service.search_episodes.return_value = {
            "episodes": [],
            "total": 0
        }
        mock_ret.return_value = mock_service

        with patch('api.episode_routes.get_current_user') as mock_auth:
            mock_auth.return_value = mock_user

            response = client.post("/episodes/search", json=search_data)

        data = response.json()
        assert isinstance(data, dict)
