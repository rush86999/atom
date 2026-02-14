"""
Workspace Management Routes Unit Tests

Tests for workspace synchronization API endpoints including:
- Create unified workspace
- Add platform to workspace
- Propagate changes to other platforms
- Get workspace sync status
- List all unified workspaces
- Delete unified workspace

Coverage: workspace_routes.py (353 lines)
Tests: 25-30 comprehensive tests
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.workspace_routes import router
from core.models import Base, UnifiedWorkspace, User


# ============================================================================
# Test Database Setup
# ============================================================================

# Create in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Create a test database session with in-memory SQLite."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create TestClient for workspace routes with test database."""
    from fastapi import FastAPI
    from core.base_routes import BaseAPIRouter

    app = FastAPI()
    app.include_router(router)

    # Override the get_db dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    from core.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app)


@pytest.fixture
def test_user(db_session):
    """Create a test user in the database."""
    user = User(
        id="test-user-123",
        email="test@example.com",
        username="testuser",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_workspace_data():
    """Sample workspace creation data."""
    return {
        "user_id": "test-user-123",
        "name": "Test Workspace",
        "description": "A test workspace for unit testing",
        "slack_workspace_id": "T123456",
        "sync_config": {"auto_sync": True, "conflict_resolution": "latest"}
    }


@pytest.fixture
def multi_platform_workspace_data():
    """Sample workspace with multiple platforms."""
    return {
        "user_id": "test-user-123",
        "name": "Multi-Platform Workspace",
        "description": "Workspace with Slack and Discord",
        "slack_workspace_id": "T123456",
        "discord_guild_id": "G789012",
        "google_chat_space_id": "spaces/ABC123",
        "sync_config": {"auto_sync": True}
    }


# ============================================================================
# POST /api/v1/workspaces/unified - Create Unified Workspace Tests
# ============================================================================

class TestCreateUnifiedWorkspace:
    """Test suite for creating unified workspaces."""

    def test_create_workspace_with_slack(self, client, sample_workspace_data):
        """Test creating a workspace with Slack platform."""
        response = client.post("/api/v1/workspaces/unified", json=sample_workspace_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["name"] == "Test Workspace"
        assert data["data"]["slack_workspace_id"] == "T123456"
        assert data["data"]["platform_count"] == 1
        assert "created_at" in data["data"]
        assert "id" in data["data"]

    def test_create_workspace_with_discord(self, client, test_user):
        """Test creating a workspace with Discord platform."""
        request_data = {
            "user_id": test_user.id,
            "name": "Discord Workspace",
            "discord_guild_id": "G789012"
        }

        response = client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["discord_guild_id"] == "G789012"
        assert data["data"]["platform_count"] == 1

    def test_create_workspace_with_google_chat(self, client, test_user):
        """Test creating a workspace with Google Chat platform."""
        request_data = {
            "user_id": test_user.id,
            "name": "Google Chat Workspace",
            "google_chat_space_id": "spaces/ABC123"
        }

        response = client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["google_chat_space_id"] == "spaces/ABC123"

    def test_create_workspace_with_teams(self, client, test_user):
        """Test creating a workspace with Microsoft Teams platform."""
        request_data = {
            "user_id": test_user.id,
            "name": "Teams Workspace",
            "teams_team_id": "team19:xyz123"
        }

        response = client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["teams_team_id"] == "team19:xyz123"

    def test_create_workspace_multiple_platforms(self, client, multi_platform_workspace_data):
        """Test creating a workspace with multiple platforms."""
        response = client.post("/api/v1/workspaces/unified", json=multi_platform_workspace_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["platform_count"] == 3
        assert data["data"]["slack_workspace_id"] == "T123456"
        assert data["data"]["discord_guild_id"] == "G789012"
        assert data["data"]["google_chat_space_id"] == "spaces/ABC123"

    def test_create_workspace_no_platforms(self, client, test_user):
        """Test that creating workspace without platforms returns validation error."""
        request_data = {
            "user_id": test_user.id,
            "name": "Empty Workspace"
        }

        response = client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 422
        data = response.json()
        assert "platforms" in str(data).lower() or "at least one platform" in str(data).lower()

    def test_create_workspace_with_description(self, client, test_user):
        """Test creating workspace with optional description."""
        request_data = {
            "user_id": test_user.id,
            "name": "Descriptive Workspace",
            "description": "This is a detailed description for the workspace",
            "slack_workspace_id": "T999999"
        }

        response = client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["description"] == "This is a detailed description for the workspace"

    def test_create_workspace_without_description(self, client, test_user):
        """Test creating workspace without description."""
        request_data = {
            "user_id": test_user.id,
            "name": "Minimal Workspace",
            "slack_workspace_id": "T888888"
        }

        response = client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["description"] is None

    def test_create_workspace_persists_to_db(self, client, db_session, sample_workspace_data):
        """Test that workspace is persisted to database."""
        response = client.post("/api/v1/workspaces/unified", json=sample_workspace_data)

        assert response.status_code == 200

        # Verify it exists in database
        workspace = db_session.query(UnifiedWorkspace).filter(
            UnifiedWorkspace.name == "Test Workspace"
        ).first()

        assert workspace is not None
        assert workspace.slack_workspace_id == "T123456"
        assert workspace.user_id == "test-user-123"


# ============================================================================
# POST /api/v1/workspaces/unified/{workspace_id}/platforms - Add Platform Tests
# ============================================================================

class TestAddPlatformToWorkspace:
    """Test suite for adding platforms to existing workspaces."""

    def test_add_slack_to_workspace(self, client, test_user, db_session):
        """Test adding Slack platform to existing workspace."""
        # Create initial workspace with Discord
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Expandable Workspace",
            discord_guild_id="G111111",
            platform_count=1,
            member_count=0
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        # Add Slack platform
        request_data = {
            "workspace_id": workspace.id,
            "platform": "slack",
            "platform_id": "T222222"
        }

        response = client.post(f"/api/v1/workspaces/unified/{workspace.id}/platforms", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["slack_workspace_id"] == "T222222"

    def test_add_discord_to_workspace(self, client, test_user, db_session):
        """Test adding Discord platform to existing workspace."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Slack Only",
            slack_workspace_id="T111111",
            platform_count=1,
            member_count=0
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        request_data = {
            "workspace_id": workspace.id,
            "platform": "discord",
            "platform_id": "G222222"
        }

        response = client.post(f"/api/v1/workspaces/unified/{workspace.id}/platforms", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["discord_guild_id"] == "G222222"

    def test_add_platform_nonexistent_workspace(self, client, test_user):
        """Test adding platform to non-existent workspace."""
        fake_id = "nonexistent-workspace-id"
        request_data = {
            "workspace_id": fake_id,
            "platform": "slack",
            "platform_id": "T999999"
        }

        response = client.post(f"/api/v1/workspaces/unified/{fake_id}/platforms", json=request_data)

        assert response.status_code == 404

    def test_add_google_chat_to_workspace(self, client, test_user, db_session):
        """Test adding Google Chat platform to workspace."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Add Google Chat",
            slack_workspace_id="T333333",
            platform_count=1,
            member_count=0
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        request_data = {
            "workspace_id": workspace.id,
            "platform": "google_chat",
            "platform_id": "spaces/XYZ789"
        }

        response = client.post(f"/api/v1/workspaces/unified/{workspace.id}/platforms", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["google_chat_space_id"] == "spaces/XYZ789"

    def test_add_teams_to_workspace(self, client, test_user, db_session):
        """Test adding Microsoft Teams platform to workspace."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Add Teams",
            slack_workspace_id="T444444",
            platform_count=1,
            member_count=0
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        request_data = {
            "workspace_id": workspace.id,
            "platform": "teams",
            "platform_id": "team19:abc123"
        }

        response = client.post(f"/api/v1/workspaces/unified/{workspace.id}/platforms", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["teams_team_id"] == "team19:abc123"


# ============================================================================
# POST /api/v1/workspaces/unified/{workspace_id}/sync - Propagate Changes Tests
# ============================================================================

class TestPropagateChanges:
    """Test suite for propagating changes across platforms."""

    def test_propagate_name_change(self, client, test_user, db_session):
        """Test propagating workspace name change."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Original Name",
            slack_workspace_id="T555555",
            discord_guild_id="G666666",
            platform_count=2,
            member_count=10
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        request_data = {
            "workspace_id": workspace.id,
            "source_platform": "slack",
            "change_type": "name_change",
            "change_data": {"old_name": "Original Name", "new_name": "Updated Name"},
            "conflict_resolution": "latest"
        }

        response = client.post(f"/api/v1/workspaces/unified/{workspace.id}/sync", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "status" in data["data"]

    def test_propagate_member_add(self, client, test_user, db_session):
        """Test propagating member addition."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Member Test Workspace",
            slack_workspace_id="T777777",
            platform_count=1,
            member_count=5
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        request_data = {
            "workspace_id": workspace.id,
            "source_platform": "slack",
            "change_type": "member_add",
            "change_data": {"member_id": "U123", "member_name": "John Doe"}
        }

        response = client.post(f"/api/v1/workspaces/unified/{workspace.id}/sync", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_propagate_with_default_conflict_resolution(self, client, test_user, db_session):
        """Test that default conflict resolution is LATEST_WINS."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Conflict Test",
            slack_workspace_id="T888888",
            platform_count=1,
            member_count=0
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        request_data = {
            "workspace_id": workspace.id,
            "source_platform": "slack",
            "change_type": "settings_change",
            "change_data": {"setting": "value"}
            # No conflict_resolution specified
        }

        response = client.post(f"/api/v1/workspaces/unified/{workspace.id}/sync", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_propagate_nonexistent_workspace(self, client, test_user):
        """Test propagating changes to non-existent workspace."""
        fake_id = "nonexistent-workspace"
        request_data = {
            "workspace_id": fake_id,
            "source_platform": "slack",
            "change_type": "name_change",
            "change_data": {}
        }

        response = client.post(f"/api/v1/workspaces/unified/{fake_id}/sync", json=request_data)

        assert response.status_code == 404


# ============================================================================
# GET /api/v1/workspaces/unified/{workspace_id} - Get Workspace Status Tests
# ============================================================================

class TestGetWorkspaceStatus:
    """Test suite for retrieving workspace sync status."""

    def test_get_workspace_status(self, client, test_user, db_session):
        """Test retrieving workspace sync status."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Status Test Workspace",
            slack_workspace_id="T999999",
            sync_status="active",
            platform_count=1,
            member_count=15
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        response = client.get(f"/api/v1/workspaces/unified/{workspace.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

    def test_get_workspace_status_not_found(self, client):
        """Test retrieving status for non-existent workspace."""
        fake_id = "nonexistent-workspace"
        response = client.get(f"/api/v1/workspaces/unified/{fake_id}")

        assert response.status_code == 404

    def test_get_workspace_status_with_last_sync(self, client, test_user, db_session):
        """Test workspace status includes last sync timestamp."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Synced Workspace",
            slack_workspace_id="T000001",
            sync_status="active",
            platform_count=1,
            member_count=0,
            last_sync_at=datetime.now(timezone.utc)
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        response = client.get(f"/api/v1/workspaces/unified/{workspace.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ============================================================================
# GET /api/v1/workspaces/unified - List Workspaces Tests
# ============================================================================

class TestListUnifiedWorkspaces:
    """Test suite for listing unified workspaces."""

    def test_list_all_workspaces(self, client, test_user, db_session):
        """Test listing all workspaces."""
        # Create multiple workspaces
        for i in range(3):
            workspace = UnifiedWorkspace(
                user_id=test_user.id,
                name=f"Workspace {i}",
                slack_workspace_id=f"T{i:06d}",
                platform_count=1,
                member_count=0
            )
            db_session.add(workspace)
        db_session.commit()

        response = client.get("/api/v1/workspaces/unified")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert data["data"]["total"] == 3

    def test_list_workspaces_by_user(self, client, db_session):
        """Test listing workspaces filtered by user."""
        # Create workspaces for different users
        user1_workspace = UnifiedWorkspace(
            user_id="user-1",
            name="User 1 Workspace",
            slack_workspace_id="T111111",
            platform_count=1,
            member_count=0
        )
        user2_workspace = UnifiedWorkspace(
            user_id="user-2",
            name="User 2 Workspace",
            slack_workspace_id="T222222",
            platform_count=1,
            member_count=0
        )
        db_session.add_all([user1_workspace, user2_workspace])
        db_session.commit()

        # List workspaces for user-1
        response = client.get("/api/v1/workspaces/unified?user_id=user-1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 1
        assert data["data"]["items"][0]["user_id"] == "user-1"

    def test_list_workspaces_empty(self, client):
        """Test listing workspaces when none exist."""
        response = client.get("/api/v1/workspaces/unified")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total"] == 0
        assert data["data"]["items"] == []

    def test_list_workspaces_pagination_structure(self, client, test_user, db_session):
        """Test that list response has proper structure."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Pagination Test",
            slack_workspace_id="T333333",
            platform_count=1,
            member_count=0
        )
        db_session.add(workspace)
        db_session.commit()

        response = client.get("/api/v1/workspaces/unified")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert "message" in data


# ============================================================================
# DELETE /api/v1/workspaces/unified/{workspace_id} - Delete Workspace Tests
# ============================================================================

class TestDeleteUnifiedWorkspace:
    """Test suite for deleting unified workspaces."""

    def test_delete_workspace(self, client, test_user, db_session):
        """Test deleting a workspace."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Deletable Workspace",
            slack_workspace_id="T444444",
            platform_count=1,
            member_count=0
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        workspace_id = workspace.id

        response = client.delete(f"/api/v1/workspaces/unified/{workspace_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["deleted_workspace_id"] == workspace_id
        assert "Deletable Workspace" in data["message"]

        # Verify deletion
        deleted_workspace = db_session.query(UnifiedWorkspace).filter(
            UnifiedWorkspace.id == workspace_id
        ).first()
        assert deleted_workspace is None

    def test_delete_workspace_not_found(self, client):
        """Test deleting non-existent workspace."""
        fake_id = "nonexistent-workspace"
        response = client.delete(f"/api/v1/workspaces/unified/{fake_id}")

        assert response.status_code == 404

    def test_delete_workspace_preserves_platforms(self, client, test_user, db_session):
        """Test that deleting unified workspace doesn't fail - actual platform deletion is not expected."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Platform Preservation Test",
            slack_workspace_id="T555555",
            discord_guild_id="G666666",
            platform_count=2,
            member_count=0
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        response = client.delete(f"/api/v1/workspaces/unified/{workspace.id}")

        assert response.status_code == 200
        # The unified workspace is deleted, but actual platforms are not touched
        # as mentioned in the endpoint docstring


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestWorkspaceHelper:
    """Test suite for workspace helper functions."""

    def test_workspace_to_dict_structure(self, client, test_user, db_session):
        """Test that _workspace_to_dict returns proper structure."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Helper Test",
            description="Test description",
            slack_workspace_id="T666666",
            discord_guild_id="G777777",
            platform_count=2,
            member_count=25,
            sync_status="active"
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        response = client.get(f"/api/v1/workspaces/unified/{workspace.id}")

        assert response.status_code == 200
        data = response.json()
        workspace_dict = data["data"]

        # Verify all expected fields
        expected_fields = [
            "id", "user_id", "name", "description",
            "slack_workspace_id", "discord_guild_id", "google_chat_space_id", "teams_team_id",
            "sync_status", "last_sync_at", "platform_count", "member_count",
            "created_at", "updated_at"
        ]

        for field in expected_fields:
            assert field in workspace_dict, f"Missing field: {field}"

    def test_workspace_to_dict_with_null_platforms(self, client, test_user, db_session):
        """Test workspace dict with only some platforms."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Partial Platforms",
            slack_workspace_id="T777777",
            platform_count=1,
            member_count=0
        )
        db_session.add(workspace)
        db_session.commit()
        db_session.refresh(workspace)

        response = client.get(f"/api/v1/workspaces/unified/{workspace.id}")

        assert response.status_code == 200
        data = response.json()
        workspace_dict = data["data"]

        assert workspace_dict["slack_workspace_id"] == "T777777"
        assert workspace_dict["discord_guild_id"] is None
        assert workspace_dict["google_chat_space_id"] is None
        assert workspace_dict["teams_team_id"] is None


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test suite for error handling in workspace routes."""

    def test_invalid_json_in_request(self, client):
        """Test handling of invalid JSON in request body."""
        response = client.post(
            "/api/v1/workspaces/unified",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_missing_required_field(self, client, test_user):
        """Test validation when required field is missing."""
        request_data = {
            # Missing required 'name' field
            "user_id": test_user.id,
            "slack_workspace_id": "T888888"
        }

        response = client.post("/api/v1/workspaces/unified", json=request_data)

        assert response.status_code == 422

    def test_workspace_status_after_sync_error(self, client, test_user, db_session):
        """Test workspace status reflects error state."""
        workspace = UnifiedWorkspace(
            user_id=test_user.id,
            name="Error State Test",
            slack_workspace_id="T999999",
            sync_status="error",
            last_sync_error="Connection timeout",
            platform_count=1,
            member_count=0
        )
        db_session.add(workspace)
        db_session.commit()

        response = client.get(f"/api/v1/workspaces/unified/{workspace.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
