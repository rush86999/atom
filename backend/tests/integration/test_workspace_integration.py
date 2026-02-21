"""
Integration tests for Workspace operations.

Tests workspace CRUD operations, validation, and member management
using real database and TestClient for API testing.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from core.models import (
    Base,
    Workspace,
    User,
)
from main_api_app import app


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_user(db_session: Session):
    """Create test user."""
    user = User(
        id="workspace-test-user",
        email="workspace@example.com",
        username="workspaceuser",
        full_name="Workspace Test User",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def client():
    """Create TestClient for API testing."""
    return TestClient(app)


@pytest.mark.integration
def test_create_workspace(db_session: Session, test_user: User):
    """Test workspace creation in database."""
    # Create workspace
    workspace = Workspace(
        name="Test Workspace",
        description="Test workspace for integration",
        created_by=test_user.id,
    )
    db_session.add(workspace)
    db_session.commit()
    db_session.refresh(workspace)

    # Verify workspace persisted
    assert workspace.id is not None
    assert workspace.name == "Test Workspace"
    assert workspace.created_by == test_user.id

    # Query from database
    db_workspace = db_session.query(Workspace).filter_by(
        id=workspace.id
    ).first()

    assert db_workspace is not None
    assert db_workspace.name == "Test Workspace"


@pytest.mark.integration
def test_create_workspace_with_validation(db_session: Session):
    """Test workspace creation with various inputs."""
    # Test: Valid workspace should succeed
    workspace = Workspace(
        name="Valid Workspace Name",
        description="Valid workspace",
        created_by="test-user",
    )
    db_session.add(workspace)
    db_session.commit()

    assert workspace.id is not None
    assert workspace.name == "Valid Workspace Name"


@pytest.mark.integration
def test_get_workspace(db_session: Session, test_user: User):
    """Test retrieving workspace by ID."""
    # Create workspace first
    workspace = Workspace(
        id="get-test-workspace",
        name="Get Test Workspace",
        description="Testing workspace retrieval",
        created_by=test_user.id,
    )
    db_session.add(workspace)
    db_session.commit()

    # Retrieve by ID
    retrieved = db_session.query(Workspace).filter_by(
        id="get-test-workspace"
    ).first()

    assert retrieved is not None
    assert retrieved.name == "Get Test Workspace"
    assert retrieved.description == "Testing workspace retrieval"


@pytest.mark.integration
@pytest.mark.parametrize("name,description,should_succeed", [
    ("Valid Workspace Name", "Valid description", True),
    ("Valid", None, True),  # No description (optional)
])
def test_workspace_validation_parametrized(
    db_session: Session,
    name: str,
    description: str,
    should_succeed: bool,
):
    """Parametrized test for workspace validation."""
    # Note: Workspace model doesn't enforce name validation at DB level
    # so all valid names should succeed
    try:
        workspace = Workspace(
            name=name,
            description=description,
            created_by="test-user",
        )
        db_session.add(workspace)
        db_session.commit()

        # If we get here, creation succeeded
        assert should_succeed, f"Expected validation to fail for name='{name}'"
        assert workspace.id is not None

    except Exception as e:
        # If we get here, validation failed
        assert not should_succeed, f"Expected validation to pass for name='{name}', got error: {e}"


@pytest.mark.integration
def test_workspace_members(db_session: Session, test_user: User):
    """Test workspace member management through many-to-many relationship."""
    # Create additional users
    user2 = User(
        id="workspace-user-2",
        email="user2@example.com",
        username="user2",
        full_name="User Two",
    )
    user3 = User(
        id="workspace-user-3",
        email="user3@example.com",
        username="user3",
        full_name="User Three",
    )
    db_session.add_all([user2, user3])
    db_session.commit()

    # Create workspace
    workspace = Workspace(
        name="Member Test Workspace",
        description="Testing member management",
        created_by=test_user.id,
    )
    db_session.add(workspace)
    db_session.commit()

    # Add members through many-to-many relationship
    workspace.users.append(test_user)
    workspace.users.append(user2)
    workspace.users.append(user3)
    db_session.commit()

    # Query members
    db_session.refresh(workspace)
    members = workspace.users

    assert len(members) == 3

    # Verify users
    user_ids = {u.id for u in members}
    assert test_user.id in user_ids
    assert user2.id in user_ids
    assert user3.id in user_ids


@pytest.mark.integration
def test_workspace_settings(db_session: Session, test_user: User):
    """Test workspace settings and metadata."""
    # Create workspace with settings
    workspace = Workspace(
        name="Settings Test Workspace",
        description="Testing workspace settings",
        created_by=test_user.id,
        settings={
            "notifications_enabled": True,
            "auto_approve": False,
            "max_members": 10,
        }
    )
    db_session.add(workspace)
    db_session.commit()

    # Retrieve and verify settings
    retrieved = db_session.query(Workspace).filter_by(
        id=workspace.id
    ).first()

    assert retrieved is not None
    assert retrieved.settings is not None
    assert retrieved.settings["notifications_enabled"] == True
    assert retrieved.settings["auto_approve"] == False
    assert retrieved.settings["max_members"] == 10


@pytest.mark.integration
def test_workspace_update(db_session: Session, test_user: User):
    """Test updating workspace details."""
    # Create workspace
    workspace = Workspace(
        name="Original Name",
        description="Original description",
        created_by=test_user.id,
    )
    db_session.add(workspace)
    db_session.commit()

    workspace_id = workspace.id

    # Update workspace
    workspace.name = "Updated Name"
    workspace.description = "Updated description"
    db_session.commit()

    # Verify update persisted
    retrieved = db_session.query(Workspace).filter_by(
        id=workspace_id
    ).first()

    assert retrieved.name == "Updated Name"
    assert retrieved.description == "Updated description"


@pytest.mark.integration
def test_workspace_delete(db_session: Session, test_user: User):
    """Test deleting workspace (cascade to relationships)."""
    # Create additional user
    user2 = User(
        id="delete-test-user-2",
        email="delete2@example.com",
        username="delete2",
        full_name="Delete Two",
    )
    db_session.add(user2)
    db_session.commit()

    # Create workspace with members
    workspace = Workspace(
        name="Delete Test Workspace",
        description="Testing deletion",
        created_by=test_user.id,
    )
    db_session.add(workspace)
    db_session.commit()

    # Add members
    workspace.users.append(test_user)
    workspace.users.append(user2)
    db_session.commit()

    workspace_id = workspace.id

    # Delete workspace
    db_session.delete(workspace)
    db_session.commit()

    # Verify workspace deleted
    deleted_workspace = db_session.query(Workspace).filter_by(
        id=workspace_id
    ).first()

    assert deleted_workspace is None

    # Users should still exist (many-to-many doesn't cascade delete users)
    assert db_session.query(User).filter_by(id=test_user.id).first() is not None
    assert db_session.query(User).filter_by(id=user2.id).first() is not None


@pytest.mark.integration
def test_multiple_workspaces_per_user(db_session: Session, test_user: User):
    """Test user can have multiple workspaces."""
    # Create multiple workspaces for same user
    workspace1 = Workspace(
        name="Workspace 1",
        description="First workspace",
        created_by=test_user.id,
    )
    workspace2 = Workspace(
        name="Workspace 2",
        description="Second workspace",
        created_by=test_user.id,
    )
    workspace3 = Workspace(
        name="Workspace 3",
        description="Third workspace",
        created_by=test_user.id,
    )
    db_session.add_all([workspace1, workspace2, workspace3])
    db_session.commit()

    # Query workspaces for user
    user_workspaces = db_session.query(Workspace).filter_by(
        created_by=test_user.id
    ).all()

    assert len(user_workspaces) == 3
    workspace_names = {w.name for w in user_workspaces}
    assert workspace_names == {"Workspace 1", "Workspace 2", "Workspace 3"}


@pytest.mark.integration
def test_workspace_multiple_users(db_session: Session, test_user: User):
    """Test workspace with multiple users."""
    # Create additional users
    users_data = [
        ("multi-user-1", "user1@example.com", "user1", "User One"),
        ("multi-user-2", "user2@example.com", "user2", "User Two"),
        ("multi-user-3", "user3@example.com", "user3", "User Three"),
        ("multi-user-4", "user4@example.com", "user4", "User Four"),
    ]

    users = []
    for user_id, email, username, full_name in users_data:
        user = User(
            id=user_id,
            email=email,
            username=username,
            full_name=full_name,
        )
        users.append(user)
        db_session.add(user)
    db_session.commit()

    # Create workspace
    workspace = Workspace(
        name="Multi User Test Workspace",
        created_by=test_user.id,
    )
    db_session.add(workspace)
    db_session.commit()

    # Add all users to workspace
    workspace.users.append(test_user)
    for user in users:
        workspace.users.append(user)
    db_session.commit()

    # Query and verify
    db_session.refresh(workspace)
    assert len(workspace.users) == 5

    # Verify all user IDs present
    user_ids = {u.id for u in workspace.users}
    assert test_user.id in user_ids
    for user in users:
        assert user.id in user_ids


@pytest.mark.integration
def test_workspace_unique_name(db_session: Session, test_user: User):
    """Test workspace names must be unique per user (if enforced)."""
    # Create first workspace
    workspace1 = Workspace(
        name="Duplicate Name",
        description="First workspace",
        created_by=test_user.id,
    )
    db_session.add(workspace1)
    db_session.commit()

    # Try to create second workspace with same name for same user
    # This should succeed (uniqueness not enforced at model level)
    workspace2 = Workspace(
        name="Duplicate Name",  # Same name
        description="Second workspace",
        created_by=test_user.id,  # Same user
    )
    db_session.add(workspace2)
    db_session.commit()

    # Both workspaces exist with same name
    workspaces = db_session.query(Workspace).filter_by(
        created_by=test_user.id,
        name="Duplicate Name"
    ).all()

    assert len(workspaces) == 2
