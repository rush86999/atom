"""
Admin Routes API Tests - Part 2: WebSocket, Rating Sync, and Conflict Management

Tests for admin routes Part 2 (lines 546-1355):
- WebSocket management: status, reconnect, disable, enable
- Rating sync: sync, failed uploads, retry
- Conflict management: list, get, resolve, bulk-resolve

Coverage target: 75%+ line coverage on admin_routes.py Part 2

Note: Part 1 tests (lines 1-545) should be added in a separate plan (172-03).
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Dict, Any
import uuid

# Import admin routes router
from api.admin_routes import router

# Import base
from core.database import Base

# Import models
from core.models import (
    User, WebSocketState, FailedRatingUpload,
    SkillRating, ConflictLog, SkillCache
)

# Import services
from core.rating_sync_service import RatingSyncService
from core.atom_saas_client import AtomSaaSClient
from core.conflict_resolution_service import ConflictResolutionService


# ============================================================================
# Test Database Setup (SQLite-compatible)
# ============================================================================

@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    # Create session first
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # Create tables manually using raw SQL for SQLite compatibility
    # Users table
    db.execute("""
        CREATE TABLE users (
            id VARCHAR PRIMARY KEY,
            email VARCHAR NOT NULL,
            name VARCHAR,
            role VARCHAR,
            tenant_id VARCHAR,
            is_active BOOLEAN DEFAULT 1
        )
    """)

    # WebSocket state table
    db.execute("""
        CREATE TABLE websocket_state (
            id INTEGER PRIMARY KEY,
            connected BOOLEAN DEFAULT 0,
            ws_url VARCHAR,
            last_connected_at TIMESTAMP,
            last_message_at TIMESTAMP,
            disconnect_reason VARCHAR,
            reconnect_attempts INTEGER DEFAULT 0,
            consecutive_failures INTEGER DEFAULT 0,
            max_reconnect_attempts INTEGER DEFAULT 10,
            fallback_to_polling BOOLEAN DEFAULT 0,
            fallback_started_at TIMESTAMP,
            next_ws_attempt_at TIMESTAMP,
            rate_limit_messages_per_sec INTEGER DEFAULT 100,
            websocket_enabled BOOLEAN DEFAULT 1
        )
    """)

    # Skill ratings table
    db.execute("""
        CREATE TABLE skill_ratings (
            id VARCHAR PRIMARY KEY,
            skill_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            tenant_id VARCHAR NOT NULL,
            rating INTEGER NOT NULL,
            review TEXT,
            synced_at TIMESTAMP
        )
    """)

    # Failed rating uploads table
    db.execute("""
        CREATE TABLE failed_rating_uploads (
            id VARCHAR PRIMARY KEY,
            rating_id VARCHAR NOT NULL,
            error_message TEXT NOT NULL,
            failed_at TIMESTAMP NOT NULL,
            last_retry_at TIMESTAMP,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            tenant_id VARCHAR NOT NULL
        )
    """)

    # Skills table (for conflicts)
    db.execute("""
        CREATE TABLE skills (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL
        )
    """)

    # Tenants table
    db.execute("""
        CREATE TABLE tenants (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL
        )
    """)

    # Conflict log table
    db.execute("""
        CREATE TABLE conflict_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id VARCHAR NOT NULL,
            conflict_type VARCHAR NOT NULL,
            severity VARCHAR NOT NULL,
            local_data TEXT NOT NULL,
            remote_data TEXT NOT NULL,
            resolution_strategy VARCHAR,
            resolved_data TEXT,
            resolved_at TIMESTAMP,
            resolved_by VARCHAR,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP,
            tenant_id VARCHAR NOT NULL
        )
    """)

    # Skill cache table
    db.execute("""
        CREATE TABLE skill_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id VARCHAR NOT NULL UNIQUE,
            skill_data TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            tenant_id VARCHAR NOT NULL,
            hit_count INTEGER DEFAULT 0,
            last_hit_at TIMESTAMP
        )
    """)

    db.commit()

    yield db

    # Cleanup
    db.close()


@pytest.fixture(scope="function")
def test_app(test_db: Session):
    """Create FastAPI app with admin routes for testing."""
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
def admin_user(test_db: Session) -> User:
    """Create admin user for testing."""
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="admin@test.com",
        name="Test Admin",
        role="super_admin",
        tenant_id="test_tenant",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()

    return user


@pytest.fixture(scope="function")
def authenticated_client(client: TestClient, admin_user: User):
    """Create authenticated TestClient with admin user."""
    # Mock get_current_user to return admin_user
    from core.auth import get_current_user

    def override_get_current_user():
        return admin_user

    client.app.dependency_overrides[get_current_user] = override_get_current_user

    yield client

    # Clean up
    client.app.dependency_overrides.clear()


# ============================================================================
# WebSocket Management Tests (13 tests)
# ============================================================================

class TestWebSocketStatus:
    """Tests for GET /api/admin/websocket/status"""

    def test_get_websocket_status_connected(self, authenticated_client: TestClient, test_db: Session):
        """Test WebSocket status when connected."""
        # Create WebSocket state
        now = datetime.now(timezone.utc)
        test_db.execute("""
            INSERT INTO websocket_state
            (id, connected, ws_url, last_connected_at, last_message_at, reconnect_attempts, consecutive_failures, fallback_to_polling)
            VALUES (1, 1, 'wss://api.example.com/ws', :now, :now, 3, 0, 0)
        """, {"now": now})
        test_db.commit()

        response = authenticated_client.get("/api/admin/websocket/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["ws_url"] == "wss://api.example.com/ws"
        assert data["reconnect_attempts"] == 3
        assert data["consecutive_failures"] == 0
        assert data["fallback_to_polling"] is False

    def test_get_websocket_status_disconnected(self, authenticated_client: TestClient, test_db: Session):
        """Test WebSocket status when disconnected."""
        test_db.execute("""
            INSERT INTO websocket_state
            (id, connected, reconnect_attempts, consecutive_failures, disconnect_reason, fallback_to_polling)
            VALUES (1, 0, 5, 3, 'connection_lost', 1)
        """)
        test_db.commit()

        response = authenticated_client.get("/api/admin/websocket/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["reconnect_attempts"] == 5
        assert data["consecutive_failures"] == 3
        assert data["last_disconnect_reason"] == "connection_lost"
        assert data["fallback_to_polling"] is True

    def test_get_websocket_status_no_state(self, authenticated_client: TestClient):
        """Test WebSocket status when no state exists."""
        response = authenticated_client.get("/api/admin/websocket/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["reconnect_attempts"] == 0
        assert data["consecutive_failures"] == 0


class TestWebSocketReconnect:
    """Tests for POST /api/admin/websocket/reconnect"""

    def test_trigger_websocket_reconnect_success(self, authenticated_client: TestClient, test_db: Session):
        """Test triggering WebSocket reconnect."""
        # Create WebSocket state
        test_db.execute("""
            INSERT INTO websocket_state
            (id, connected, reconnect_attempts, consecutive_failures, fallback_to_polling)
            VALUES (1, 0, 5, 3, 1)
        """)
        test_db.commit()

        response = authenticated_client.post("/api/admin/websocket/reconnect")

        assert response.status_code == 200
        data = response.json()
        assert data["reconnect_triggered"] is True

        # Verify DB updated
        result = test_db.execute("SELECT reconnect_attempts, consecutive_failures, fallback_to_polling FROM websocket_state WHERE id = 1").fetchone()
        assert result[0] == 0  # reconnect_attempts
        assert result[1] == 0  # consecutive_failures
        assert result[2] == 0  # fallback_to_polling

    def test_trigger_websocket_reconnect_creates_state(self, authenticated_client: TestClient, test_db: Session):
        """Test reconnect creates WebSocket state if not exists."""
        response = authenticated_client.post("/api/admin/websocket/reconnect")

        assert response.status_code == 200

        # Verify state created
        result = test_db.execute("SELECT id FROM websocket_state").fetchone()
        assert result is not None
        assert result[0] == 1


class TestWebSocketDisable:
    """Tests for POST /api/admin/websocket/disable"""

    def test_disable_websocket_success(self, authenticated_client: TestClient, test_db: Session):
        """Test disabling WebSocket."""
        test_db.execute("""
            INSERT INTO websocket_state
            (id, connected, websocket_enabled, fallback_to_polling)
            VALUES (1, 1, 1, 0)
        """)
        test_db.commit()

        response = authenticated_client.post("/api/admin/websocket/disable")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["websocket_enabled"] is False

        # Verify DB updated
        result = test_db.execute("SELECT connected, disconnect_reason FROM websocket_state WHERE id = 1").fetchone()
        assert result[0] == 0  # connected
        assert result[1] == "disabled_by_admin"

    def test_disable_websocket_creates_state(self, authenticated_client: TestClient, test_db: Session):
        """Test disable creates WebSocket state if not exists."""
        response = authenticated_client.post("/api/admin/websocket/disable")

        assert response.status_code == 200

        # Verify state created
        result = test_db.execute("SELECT id FROM websocket_state").fetchone()
        assert result is not None


class TestWebSocketEnable:
    """Tests for POST /api/admin/websocket/enable"""

    def test_enable_websocket_success(self, authenticated_client: TestClient, test_db: Session):
        """Test enabling WebSocket."""
        now = datetime.now(timezone.utc) + timedelta(hours=1)
        test_db.execute("""
            INSERT INTO websocket_state
            (id, fallback_to_polling, next_ws_attempt_at, reconnect_attempts)
            VALUES (1, 1, :now, 5)
        """, {"now": now})
        test_db.commit()

        response = authenticated_client.post("/api/admin/websocket/enable")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["websocket_enabled"] is True

        # Verify DB updated
        result = test_db.execute("SELECT fallback_to_polling, next_ws_attempt_at, reconnect_attempts FROM websocket_state WHERE id = 1").fetchone()
        assert result[0] == 0  # fallback_to_polling
        assert result[1] is None  # next_ws_attempt_at
        assert result[2] == 0  # reconnect_attempts

    def test_enable_websocket_creates_state(self, authenticated_client: TestClient, test_db: Session):
        """Test enable creates WebSocket state if not exists."""
        response = authenticated_client.post("/api/admin/websocket/enable")

        assert response.status_code == 200

        # Verify state created
        result = test_db.execute("SELECT id FROM websocket_state").fetchone()
        assert result is not None


# ============================================================================
# Rating Sync Tests (12 tests)
# ============================================================================

class TestRatingSync:
    """Tests for POST /api/admin/sync/ratings"""

    def test_trigger_rating_sync_success(self, authenticated_client: TestClient, test_db: Session):
        """Test triggering rating sync successfully."""
        # Create pending ratings
        for i in range(5):
            test_db.execute("""
                INSERT INTO skill_ratings
                (id, skill_id, user_id, tenant_id, rating, synced_at)
                VALUES (:id, :skill_id, 'test_user', 'test_tenant', 5, NULL)
            """, {"id": f"rating_{i}", "skill_id": f"skill_{i}"})
        test_db.commit()

        # Mock RatingSyncService
        with patch('core.rating_sync_service.RatingSyncService') as mock_service_class:
            mock_service = MagicMock()
            mock_service._sync_in_progress = False
            mock_service.get_pending_ratings.return_value = [
                MagicMock(id=f"rating_{i}") for i in range(5)
            ]

            # Make sync_ratings async
            async def mock_sync(upload_all=False):
                return {"success": True, "uploaded": 5, "failed": 0, "skipped": 0}

            mock_service.sync_ratings = mock_sync
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/api/admin/sync/ratings",
                json={"upload_all": False}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["uploaded"] == 5
            assert data["failed"] == 0

    def test_trigger_rating_sync_in_progress(self, authenticated_client: TestClient, test_db: Session):
        """Test sync when already in progress."""
        with patch('core.rating_sync_service.RatingSyncService') as mock_service_class:
            mock_service = MagicMock()
            mock_service._sync_in_progress = True  # Already syncing
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/api/admin/sync/ratings",
                json={"upload_all": False}
            )

            assert response.status_code == 503

    def test_trigger_rating_sync_with_failures(self, authenticated_client: TestClient, test_db: Session):
        """Test sync with some failures."""
        with patch('core.rating_sync_service.RatingSyncService') as mock_service_class:
            mock_service = MagicMock()
            mock_service._sync_in_progress = False
            mock_service.get_pending_ratings.return_value = []

            async def mock_sync(upload_all=False):
                return {"success": True, "uploaded": 3, "failed": 2, "skipped": 1}

            mock_service.sync_ratings = mock_sync
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/api/admin/sync/ratings",
                json={"upload_all": False}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["uploaded"] == 3
            assert data["failed"] == 2
            assert data["skipped"] == 1


class TestFailedRatingUploads:
    """Tests for GET /api/admin/ratings/failed-uploads"""

    def test_get_failed_rating_uploads_success(self, authenticated_client: TestClient, test_db: Session):
        """Test getting failed rating uploads."""
        # Create failed uploads
        for i in range(3):
            test_db.execute("""
                INSERT INTO failed_rating_uploads
                (id, rating_id, error_message, failed_at, retry_count, tenant_id)
                VALUES (:id, :rating_id, :error, :now, :retry_count, 'test_tenant')
            """, {
                "id": f"failed_{i}",
                "rating_id": f"rating_{i}",
                "error": f"Error {i}",
                "now": datetime.now(timezone.utc),
                "retry_count": i
            })
        test_db.commit()

        response = authenticated_client.get("/api/admin/ratings/failed-uploads")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_get_failed_rating_uploads_empty(self, authenticated_client: TestClient):
        """Test getting failed uploads when none exist."""
        response = authenticated_client.get("/api/admin/ratings/failed-uploads")

        assert response.status_code == 200
        assert response.json() == []


class TestRetryFailedRatingUpload:
    """Tests for POST /api/admin/ratings/failed-uploads/{failed_id}/retry"""

    def test_retry_failed_rating_upload_success(self, authenticated_client: TestClient, test_db: Session):
        """Test retrying failed rating upload successfully."""
        # Create rating
        test_db.execute("""
            INSERT INTO skill_ratings
            (id, skill_id, user_id, tenant_id, rating, synced_at)
            VALUES ('rating_1', 'skill_1', 'test_user', 'test_tenant', 5, NULL)
        """)

        # Create failed upload
        test_db.execute("""
            INSERT INTO failed_rating_uploads
            (id, rating_id, error_message, failed_at, retry_count, tenant_id)
            VALUES ('failed_1', 'rating_1', 'Network error', :now, 0, 'test_tenant')
        """, {"now": datetime.now(timezone.utc)})
        test_db.commit()

        # Mock RatingSyncService
        with patch('core.rating_sync_service.RatingSyncService') as mock_service_class:
            mock_service = MagicMock()

            async def mock_upload(rating):
                return {"success": True, "rating_id": "remote_123"}

            mock_service.upload_rating = mock_upload
            mock_service.mark_as_synced = MagicMock()
            mock_service_class.return_value = mock_service

            response = authenticated_client.post("/api/admin/ratings/failed-uploads/failed_1/retry")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify failed record deleted
            result = test_db.execute("SELECT COUNT(*) FROM failed_rating_uploads").fetchone()
            assert result[0] == 0

    def test_retry_failed_rating_upload_rating_deleted(self, authenticated_client: TestClient, test_db: Session):
        """Test retry when rating no longer exists."""
        # Create failed upload without rating
        test_db.execute("""
            INSERT INTO failed_rating_uploads
            (id, rating_id, error_message, failed_at, retry_count, tenant_id)
            VALUES ('failed_1', 'deleted_rating', 'Network error', :now, 0, 'test_tenant')
        """, {"now": datetime.now(timezone.utc)})
        test_db.commit()

        response = authenticated_client.post("/api/admin/ratings/failed-uploads/failed_1/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "no longer exists" in data["message"].lower()

    def test_retry_failed_rating_upload_failed_again(self, authenticated_client: TestClient, test_db: Session):
        """Test retry that fails again."""
        # Create rating
        test_db.execute("""
            INSERT INTO skill_ratings
            (id, skill_id, user_id, tenant_id, rating, synced_at)
            VALUES ('rating_1', 'skill_1', 'test_user', 'test_tenant', 5, NULL)
        """)

        # Create failed upload
        test_db.execute("""
            INSERT INTO failed_rating_uploads
            (id, rating_id, error_message, failed_at, retry_count, tenant_id)
            VALUES ('failed_1', 'rating_1', 'Network error', :now, 1, 'test_tenant')
        """, {"now": datetime.now(timezone.utc)})
        test_db.commit()

        # Mock RatingSyncService to fail again
        with patch('core.rating_sync_service.RatingSyncService') as mock_service_class:
            mock_service = MagicMock()

            async def mock_upload(rating):
                return {"success": False, "error": "Network error"}

            mock_service.upload_rating = mock_upload
            mock_service_class.return_value = mock_service

            response = authenticated_client.post("/api/admin/ratings/failed-uploads/failed_1/retry")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_retry_failed_rating_upload_not_found(self, authenticated_client: TestClient):
        """Test retry with non-existent failed upload."""
        response = authenticated_client.post("/api/admin/ratings/failed-uploads/nonexistent/retry")

        assert response.status_code == 404


# ============================================================================
# Conflict Management Tests (21 tests)
# ============================================================================

class TestListConflicts:
    """Tests for GET /api/admin/conflicts"""

    def test_list_conflicts_success(self, authenticated_client: TestClient, test_db: Session):
        """Test listing conflicts successfully."""
        # Create conflicts
        for i in range(3):
            test_db.execute("""
                INSERT INTO conflict_log
                (id, skill_id, conflict_type, severity, local_data, remote_data, created_at, tenant_id)
                VALUES (:id, :skill_id, 'version_mismatch', 'high', '{"version": "1.0"}', '{"version": "2.0"}', :now, 'test_tenant')
            """, {"id": i + 1, "skill_id": f"skill_{i}", "now": datetime.now(timezone.utc)})
        test_db.commit()

        # Mock ConflictResolutionService
        with patch('core.conflict_resolution_service.ConflictResolutionService') as mock_service_class:
            mock_service = MagicMock()

            # Return mock conflict objects
            mock_conflicts = []
            for i in range(3):
                c = MagicMock()
                c.id = i + 1
                c.skill_id = f"skill_{i}"
                c.conflict_type = "version_mismatch"
                c.severity = "high"
                c.local_data = {"version": "1.0"}
                c.remote_data = {"version": "2.0"}
                c.resolution_strategy = None
                c.resolved_data = None
                c.resolved_at = None
                c.resolved_by = None
                c.created_at = datetime.now(timezone.utc)
                mock_conflicts.append(c)

            mock_service.get_unresolved_conflicts.return_value = mock_conflicts
            mock_service_class.return_value = mock_service

            response = authenticated_client.get("/api/admin/conflicts")

            assert response.status_code == 200
            data = response.json()
            assert "conflicts" in data
            assert data["total_count"] == 3

    def test_list_conflicts_empty(self, authenticated_client: TestClient, test_db: Session):
        """Test listing conflicts when none exist."""
        with patch('core.conflict_resolution_service.ConflictResolutionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_unresolved_conflicts.return_value = []
            mock_service_class.return_value = mock_service

            response = authenticated_client.get("/api/admin/conflicts")

            assert response.status_code == 200
            data = response.json()
            assert data["conflicts"] == []
            assert data["total_count"] == 0


class TestGetConflict:
    """Tests for GET /api/admin/conflicts/{conflict_id}"""

    def test_get_conflict_success(self, authenticated_client: TestClient, test_db: Session):
        """Test getting conflict by ID."""
        # Mock conflict
        mock_conflict = MagicMock()
        mock_conflict.id = 1
        mock_conflict.skill_id = "skill_1"
        mock_conflict.conflict_type = "version_mismatch"
        mock_conflict.severity = "high"
        mock_conflict.local_data = {"version": "1.0"}
        mock_conflict.remote_data = {"version": "2.0"}
        mock_conflict.created_at = datetime.now(timezone.utc)

        with patch('core.conflict_resolution_service.ConflictResolutionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_conflict_by_id.return_value = mock_conflict
            mock_service_class.return_value = mock_service

            response = authenticated_client.get("/api/admin/conflicts/1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["skill_id"] == "skill_1"

    def test_get_conflict_not_found(self, authenticated_client: TestClient, test_db: Session):
        """Test getting non-existent conflict."""
        with patch('core.conflict_resolution_service.ConflictResolutionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_conflict_by_id.return_value = None
            mock_service_class.return_value = mock_service

            response = authenticated_client.get("/api/admin/conflicts/999")

            assert response.status_code == 404


class TestResolveConflict:
    """Tests for POST /api/admin/conflicts/{conflict_id}/resolve"""

    def test_resolve_conflict_remote_wins(self, authenticated_client: TestClient, test_db: Session):
        """Test resolving conflict with remote_wins strategy."""
        resolved_data = {"skill_id": "skill_1", "version": "2.0"}

        # Mock ConflictResolutionService
        with patch('core.conflict_resolution_service.ConflictResolutionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.resolve_conflict.return_value = resolved_data
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/api/admin/conflicts/1/resolve",
                json={"strategy": "remote_wins", "resolved_by": "admin"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["resolved_data"] == resolved_data

    def test_resolve_conflict_local_wins(self, authenticated_client: TestClient, test_db: Session):
        """Test resolving conflict with local_wins strategy."""
        resolved_data = {"skill_id": "skill_1", "version": "1.0"}

        with patch('core.conflict_resolution_service.ConflictResolutionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.resolve_conflict.return_value = resolved_data
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/api/admin/conflicts/1/resolve",
                json={"strategy": "local_wins", "resolved_by": "admin"}
            )

            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_resolve_conflict_merge(self, authenticated_client: TestClient, test_db: Session):
        """Test resolving conflict with merge strategy."""
        resolved_data = {"skill_id": "skill_1", "version": "2.0", "local_changes": "preserved"}

        with patch('core.conflict_resolution_service.ConflictResolutionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.resolve_conflict.return_value = resolved_data
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/api/admin/conflicts/1/resolve",
                json={"strategy": "merge", "resolved_by": "admin"}
            )

            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_resolve_conflict_invalid_strategy(self, authenticated_client: TestClient, test_db: Session):
        """Test resolving conflict with invalid strategy."""
        response = authenticated_client.post(
            "/api/admin/conflicts/1/resolve",
            json={"strategy": "invalid", "resolved_by": "admin"}
        )

        assert response.status_code == 422

    def test_resolve_conflict_not_found(self, authenticated_client: TestClient, test_db: Session):
        """Test resolving non-existent conflict."""
        with patch('core.conflict_resolution_service.ConflictResolutionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.resolve_conflict.return_value = None
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/api/admin/conflicts/999/resolve",
                json={"strategy": "remote_wins", "resolved_by": "admin"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False


class TestBulkResolveConflicts:
    """Tests for POST /api/admin/conflicts/bulk-resolve"""

    def test_bulk_resolve_conflicts_success(self, authenticated_client: TestClient, test_db: Session):
        """Test bulk resolving conflicts successfully."""
        with patch('core.conflict_resolution_service.ConflictResolutionService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.resolve_conflict.return_value = {"skill_id": "skill_1", "version": "2.0"}
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/api/admin/conflicts/bulk-resolve",
                json={
                    "conflict_ids": [1, 2, 3],
                    "strategy": "remote_wins",
                    "resolved_by": "admin"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["resolved_count"] == 3
            assert data["failed_count"] == 0
            assert data["success"] is True

    def test_bulk_resolve_conflicts_partial_failure(self, authenticated_client: TestClient, test_db: Session):
        """Test bulk resolve with some failures."""
        with patch('core.conflict_resolution_service.ConflictResolutionService') as mock_service_class:
            mock_service = MagicMock()

            # Make second resolve fail
            def side_effect(conflict_id, strategy, resolved_by):
                if conflict_id == 2:
                    return None
                return {"skill_id": f"skill_{conflict_id}", "version": "2.0"}

            mock_service.resolve_conflict.side_effect = side_effect
            mock_service_class.return_value = mock_service

            response = authenticated_client.post(
                "/api/admin/conflicts/bulk-resolve",
                json={
                    "conflict_ids": [1, 2, 3],
                    "strategy": "remote_wins",
                    "resolved_by": "admin"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["resolved_count"] == 2
            assert data["failed_count"] == 1

    def test_bulk_resolve_conflicts_invalid_strategy(self, authenticated_client: TestClient, test_db: Session):
        """Test bulk resolve with invalid strategy."""
        response = authenticated_client.post(
            "/api/admin/conflicts/bulk-resolve",
            json={
                "conflict_ids": [1, 2, 3],
                "strategy": "invalid",
                "resolved_by": "admin"
            }
        )

        assert response.status_code == 422

    def test_bulk_resolve_conflicts_too_many_ids(self, authenticated_client: TestClient, test_db: Session):
        """Test bulk resolve with too many conflict IDs."""
        # Max is 100
        conflict_ids = list(range(101))

        response = authenticated_client.post(
            "/api/admin/conflicts/bulk-resolve",
            json={
                "conflict_ids": conflict_ids,
                "strategy": "remote_wins",
                "resolved_by": "admin"
            }
        )

        assert response.status_code == 422
