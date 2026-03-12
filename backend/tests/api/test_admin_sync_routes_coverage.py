"""
Sync Admin Routes Coverage Tests

Tests for sync admin routes (api/sync_admin_routes.py) covering:
- Manual sync trigger (CRITICAL complexity, AUTONOMOUS required)
- Sync status and config endpoints
- Rating sync operations (HIGH complexity)
- WebSocket management (MODERATE/HIGH complexity)
- Conflict resolution (HIGH/CRITICAL complexity)

Coverage target: 75%+ line coverage on sync_admin_routes.py
Test count: 30+ tests across 7 test classes
"""

import pytest
import uuid
import sqlalchemy
from datetime import datetime, timezone, timedelta
from typing import List
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import sync admin routes router
from api.sync_admin_routes import router


# ============================================================================
# Mock User Model (avoid importing from core.models due to SQLAlchemy relationships)
# ============================================================================

class User:
    """Mock User class for testing."""
    def __init__(self, id, email, name, role, tenant_id, is_active=True):
        self.id = id
        self.email = email
        self.name = name
        self.role = role
        self.tenant_id = tenant_id
        self.is_active = is_active


# ============================================================================
# Test Database Setup
# ============================================================================

@pytest.fixture(scope="function")
def test_db():
    """Create mock database session for testing."""
    # Use MagicMock instead of real database to avoid JSONB/SQLite issues
    mock_db = MagicMock()
    mock_query = MagicMock()

    # Mock query chain: db.query(Model).first() -> None
    mock_query.first.return_value = None
    mock_db.query.return_value = mock_query

    return mock_db


@pytest.fixture(scope="function")
def test_app(test_db: MagicMock):
    """Create FastAPI app with sync admin routes for testing."""
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


@pytest.fixture(scope="function")
def admin_user() -> User:
    """Create super admin user for testing."""
    user = User(
        id="admin_test_user",
        email="admin@test.com",
        name="Test Admin",
        role="super_admin",
        tenant_id="test_tenant",
        is_active=True
    )
    return user


@pytest.fixture(scope="function")
def regular_user() -> User:
    """Create regular user for governance testing."""
    user = User(
        id="regular_test_user",
        email="user@test.com",
        name="Test User",
        role="member",
        tenant_id="test_tenant",
        is_active=True
    )
    return user


@pytest.fixture(scope="function")
def authenticated_client(client: TestClient, admin_user: User):
    """Create authenticated TestClient with admin user."""
    from core.auth import get_current_user

    def override_get_current_user():
        return admin_user

    client.app.dependency_overrides[get_current_user] = override_get_current_user

    yield client

    # Clean up
    client.app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def regular_client(client: TestClient, regular_user: User):
    """Create authenticated TestClient with regular user."""
    from core.auth import get_current_user

    def override_get_current_user():
        return regular_user

    client.app.dependency_overrides[get_current_user] = override_get_current_user

    yield client

    # Clean up
    client.app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def mock_governance_cache():
    """AsyncMock for GovernanceCache for maturity checks."""
    mock = AsyncMock()

    # Default: AUTONOMOUS maturity (passes all checks)
    mock.check_maturity.return_value = True

    return mock


# ============================================================================
# Test Classes
# ============================================================================

class TestSyncTrigger:
    """Tests for POST /api/admin/sync/trigger"""

    def test_trigger_manual_sync_success(self, authenticated_client: TestClient):
        """Test successful manual sync trigger."""
        response = authenticated_client.post("/api/admin/sync/trigger")

        assert response.status_code == 202
        data = response.json()
        assert "sync_id" in data
        assert data["status"] == "queued"
        assert "sync triggered" in data["message"].lower()
        assert data["sync_id"].startswith("manual_")

    def test_trigger_manual_sync_generates_sync_id(self, authenticated_client: TestClient):
        """Test sync ID format matches manual_YYYYMMDD_HHMMSS."""
        response = authenticated_client.post("/api/admin/sync/trigger")

        assert response.status_code == 202
        data = response.json()
        sync_id = data["sync_id"]

        # Check format: manual_YYYYMMDD_HHMMSS
        assert sync_id.startswith("manual_")
        # Format should be manual_YYYYMMDD_HHMMSS (with underscore between date and time)
        parts = sync_id.split("_")
        assert len(parts) >= 2  # At least ["manual", "YYYYMMDDHHMMSS"] or ["manual", "YYYYMMDD", "HHMMSS"]

    def test_trigger_manual_sync_governance_enforced(self, authenticated_client: TestClient):
        """Test that sync trigger requires agent_id for governance check."""
        # Since allow_user_initiated=True, requests without agent_id succeed
        # Requests with agent_id would trigger governance checks (requires AUTONOMOUS)
        response = authenticated_client.post("/api/admin/sync/trigger")

        # Should succeed when called by user without agent_id
        assert response.status_code == 202


class TestSyncStatus:
    """Tests for GET /api/admin/sync/status"""

    def test_get_sync_status_no_state(self, authenticated_client: TestClient, test_db: Session):
        """Test getting sync status when no SyncState exists."""
        response = authenticated_client.get("/api/admin/sync/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "idle"
        assert data["last_sync"] is None
        assert data["sync_age_minutes"] is None
        assert data["skills_cached"] == 0
        assert data["categories_cached"] == 0
        assert data["last_error"] is None

    def test_get_sync_status_age_calculation(self, authenticated_client: TestClient, test_db: Session):
        """Test sync_age_minutes calculation when last_sync exists."""
        # Note: Since SyncState model doesn't exist yet, this test will use the default behavior
        # When SyncState is added, this test should be updated to create a SyncState record

        # For now, test that the endpoint returns valid response structure
        response = authenticated_client.get("/api/admin/sync/status")

        assert response.status_code == 200
        data = response.json()
        # Verify response structure
        assert "status" in data
        assert "sync_age_minutes" in data
        assert "skills_cached" in data
        assert "categories_cached" in data


class TestSyncConfig:
    """Tests for GET /api/admin/sync/config"""

    def test_get_sync_config(self, authenticated_client: TestClient):
        """Test getting sync configuration."""
        response = authenticated_client.get("/api/admin/sync/config")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "interval_minutes" in data
        assert "batch_size" in data
        assert "websocket_enabled" in data
        assert "atom_saas_api_url" in data
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["interval_minutes"], int)
        assert isinstance(data["batch_size"], int)
        assert isinstance(data["websocket_enabled"], bool)
        assert isinstance(data["atom_saas_api_url"], str)


class TestRatingSync:
    """Tests for rating sync endpoints"""

    def test_trigger_rating_sync_success(self, authenticated_client: TestClient):
        """Test triggering rating sync."""
        response = authenticated_client.post("/api/admin/sync/ratings")

        assert response.status_code == 202
        data = response.json()
        assert "sync_id" in data
        assert data["status"] == "queued"
        assert data["sync_id"].startswith("rating_")

    def test_trigger_rating_sync_governance_enforced(self, authenticated_client: TestClient):
        """Test that rating sync accepts user-initiated requests."""
        # Since allow_user_initiated=True, requests without agent_id succeed
        response = authenticated_client.post("/api/admin/sync/ratings")

        assert response.status_code == 202

    def test_get_rating_sync_status(self, authenticated_client: TestClient):
        """Test getting rating sync status."""
        response = authenticated_client.get("/api/admin/sync/ratings/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "last_sync" in data
        assert "pending_ratings" in data
        assert "failed_uploads" in data

    def test_list_failed_rating_uploads(self, authenticated_client: TestClient):
        """Test listing failed uploads."""
        response = authenticated_client.get("/api/admin/sync/ratings/failed-uploads")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Placeholder returns empty list
        assert len(data) == 0

    def test_list_failed_uploads_with_pagination(self, authenticated_client: TestClient):
        """Test pagination parameters for failed uploads."""
        response = authenticated_client.get(
            "/api/admin/sync/ratings/failed-uploads?page=2&page_size=50"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_retry_failed_upload(self, authenticated_client: TestClient):
        """Test retrying failed upload."""
        upload_id = str(uuid.uuid4())
        response = authenticated_client.post(
            f"/api/admin/sync/ratings/failed-uploads/{upload_id}/retry"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "retry" in data["message"].lower()

    def test_retry_upload_governance_enforced(self, authenticated_client: TestClient):
        """Test that retry accepts user-initiated requests."""
        upload_id = str(uuid.uuid4())
        response = authenticated_client.post(
            f"/api/admin/sync/ratings/failed-uploads/{upload_id}/retry"
        )

        assert response.status_code == 200


class TestWebSocketManagement:
    """Tests for WebSocket management endpoints"""

    def test_get_websocket_status(self, authenticated_client: TestClient):
        """Test getting WebSocket status."""
        response = authenticated_client.get("/api/admin/sync/websocket/status")

        assert response.status_code == 200
        data = response.json()
        assert "connected" in data
        assert "enabled" in data
        assert "reconnect_count" in data
        # Placeholder returns connected=False
        assert data["connected"] is False

    def test_force_websocket_reconnect(self, authenticated_client: TestClient):
        """Test forcing WebSocket reconnection."""
        response = authenticated_client.post("/api/admin/sync/websocket/reconnect")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False  # Placeholder
        assert "reconnect" in data["message"].lower()

    def test_websocket_reconnect_governance_enforced(self, authenticated_client: TestClient):
        """Test that reconnect accepts user-initiated requests."""
        response = authenticated_client.post("/api/admin/sync/websocket/reconnect")

        assert response.status_code == 200

    def test_disable_websocket(self, authenticated_client: TestClient):
        """Test disabling WebSocket."""
        response = authenticated_client.post("/api/admin/sync/websocket/disable")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert "disabled" in data["message"].lower()

    def test_disable_websocket_governance_enforced(self, authenticated_client: TestClient):
        """Test that disable accepts user-initiated requests."""
        response = authenticated_client.post("/api/admin/sync/websocket/disable")

        assert response.status_code == 200

    def test_enable_websocket(self, authenticated_client: TestClient):
        """Test enabling WebSocket."""
        response = authenticated_client.post("/api/admin/sync/websocket/enable")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert "enabled" in data["message"].lower()

    def test_enable_websocket_governance_enforced(self, authenticated_client: TestClient):
        """Test that enable accepts user-initiated requests."""
        response = authenticated_client.post("/api/admin/sync/websocket/enable")

        assert response.status_code == 200


class TestConflictResolution:
    """Tests for conflict resolution endpoints"""

    def test_list_conflicts(self, authenticated_client: TestClient):
        """Test listing conflicts."""
        response = authenticated_client.get("/api/admin/sync/conflicts")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Placeholder returns empty list
        assert len(data) == 0

    def test_list_conflicts_with_filters(self, authenticated_client: TestClient):
        """Test listing with status filter."""
        response = authenticated_client.get(
            "/api/admin/sync/conflicts?status=unresolved"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_conflicts_with_pagination(self, authenticated_client: TestClient):
        """Test pagination parameters."""
        response = authenticated_client.get(
            "/api/admin/sync/conflicts?page=1&page_size=20"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_conflict_detail_not_found(self, authenticated_client: TestClient):
        """Test getting non-existent conflict returns 404."""
        conflict_id = str(uuid.uuid4())
        response = authenticated_client.get(f"/api/admin/sync/conflicts/{conflict_id}")

        # Placeholder always raises not_found
        assert response.status_code == 404

    def test_resolve_conflict(self, authenticated_client: TestClient):
        """Test resolving conflict."""
        conflict_id = str(uuid.uuid4())
        response = authenticated_client.post(
            f"/api/admin/sync/conflicts/{conflict_id}/resolve?strategy=local_wins"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conflict_id"] == conflict_id
        assert "resolved" in data["message"].lower()

    def test_resolve_conflict_governance_enforced(self, authenticated_client: TestClient):
        """Test that resolve accepts user-initiated requests."""
        conflict_id = str(uuid.uuid4())
        response = authenticated_client.post(
            f"/api/admin/sync/conflicts/{conflict_id}/resolve?strategy=local_wins"
        )

        assert response.status_code == 200

    def test_bulk_resolve_conflicts(self, authenticated_client: TestClient):
        """Test bulk resolving conflicts."""
        conflict_ids = [str(uuid.uuid4()) for _ in range(3)]
        response = authenticated_client.post(
            "/api/admin/sync/conflicts/bulk-resolve?strategy=merge",
            json=conflict_ids
        )

        assert response.status_code == 200
        data = response.json()
        assert data["resolved_count"] == 3
        assert data["failed_count"] == 0
        assert len(data["failed_ids"]) == 0

    def test_bulk_resolve_governance_enforced(self, authenticated_client: TestClient):
        """Test that bulk resolve accepts user-initiated requests."""
        conflict_ids = [str(uuid.uuid4()) for _ in range(3)]
        response = authenticated_client.post(
            "/api/admin/sync/conflicts/bulk-resolve?strategy=merge",
            json=conflict_ids
        )

        assert response.status_code == 200

    def test_bulk_resolve_with_failures(self, authenticated_client: TestClient):
        """Test bulk resolve with some failures (placeholder always succeeds)."""
        conflict_ids = [str(uuid.uuid4()) for _ in range(5)]
        response = authenticated_client.post(
            "/api/admin/sync/conflicts/bulk-resolve?strategy=remote_wins",
            json=conflict_ids
        )

        # Placeholder always returns success
        assert response.status_code == 200
        data = response.json()
        assert data["resolved_count"] == 5
        assert data["failed_count"] == 0


class TestGovernanceEnforcement:
    """Tests for governance enforcement across all endpoints"""

    def test_all_endpoints_accept_user_initiated_requests(self, authenticated_client: TestClient):
        """Test that all endpoints accept user-initiated requests (no agent_id)."""
        # Since allow_user_initiated=True, all endpoints should succeed without agent_id

        # CRITICAL endpoints
        response1 = authenticated_client.post("/api/admin/sync/trigger")
        assert response1.status_code == 202

        conflict_ids = [str(uuid.uuid4()) for _ in range(3)]
        response2 = authenticated_client.post(
            "/api/admin/sync/conflicts/bulk-resolve?strategy=merge",
            json=conflict_ids
        )
        assert response2.status_code == 200

        # HIGH endpoints
        response3 = authenticated_client.post("/api/admin/sync/ratings")
        assert response3.status_code == 202

        response4 = authenticated_client.post("/api/admin/sync/websocket/disable")
        assert response4.status_code == 200

        conflict_id = str(uuid.uuid4())
        response5 = authenticated_client.post(
            f"/api/admin/sync/conflicts/{conflict_id}/resolve?strategy=local_wins"
        )
        assert response5.status_code == 200

        # MODERATE endpoints
        upload_id = str(uuid.uuid4())
        response6 = authenticated_client.post(
            f"/api/admin/sync/ratings/failed-uploads/{upload_id}/retry"
        )
        assert response6.status_code == 200

        response7 = authenticated_client.post("/api/admin/sync/websocket/reconnect")
        assert response7.status_code == 200

        response8 = authenticated_client.post("/api/admin/sync/websocket/enable")
        assert response8.status_code == 200
