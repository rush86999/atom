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
    WorkspaceMember,
    UserRole,
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
    """Test workspace validation rules."""
    # Test 1: Empty name should fail validation
    with pytest.raises(Exception):
        workspace = Workspace(
            name="",
            description="Test",
            created_by="test-user",
        )
        db_session.add(workspace)
        db_session.commit()

    # Rollback for next test
    db_session.rollback()

    # Test 2: Very short name (< 3 chars)
    with pytest.raises(Exception):
        workspace = Workspace(
            name="ab",  # Too short
            description="Test",
            created_by="test-user",
        )
        db_session.add(workspace)
        db_session.commit()

    db_session.rollback()

    # Test 3: Valid name should succeed
    workspace = Workspace(
        name="Valid Workspace Name",
        description="Valid workspace",
        created_by="test-user",
    )
    db_session.add(workspace)
    db_session.commit()

    assert workspace.id is not None


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
    ("", "Missing name", False),  # Empty name
    ("a", "Too short", False),  # Too short (<3 chars)
    ("ab", "Still too short", False),  # Too short
    ("Valid", None, True),  # No description (optional)
])
def test_workspace_validation_parametrized(
    db_session: Session,
    name: str,
    description: str,
    should_succeed: bool,
):
    """Parametrized test for workspace validation."""
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
    """Test workspace member management."""
    # Create workspace
    workspace = Workspace(
        name="Member Test Workspace",
        description="Testing member management",
        created_by=test_user.id,
    )
    db_session.add(workspace)
    db_session.commit()

    # Add members
    member1 = WorkspaceMember(
        workspace_id=workspace.id,
        user_id="user-1",
        role=UserRole.OWNER.value,
    )
    member2 = WorkspaceMember(
        workspace_id=workspace.id,
        user_id="user-2",
        role=UserRole.MEMBER.value,
    )
    member3 = WorkspaceMember(
        workspace_id=workspace.id,
        user_id="user-3",
        role=UserRole.VIEWER.value,
    )
    db_session.add_all([member1, member2, member3])
    db_session.commit()

    # Query members
    members = db_session.query(WorkspaceMember).filter_by(
        workspace_id=workspace.id
    ).all()

    assert len(members) == 3

    # Verify roles
    roles = {m.user_id: m.role for m in members}
    assert roles["user-1"] == UserRole.OWNER.value
    assert roles["user-2"] == UserRole.MEMBER.value
    assert roles["user-3"] == UserRole.VIEWER.value


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
    """Test deleting workspace (cascade delete members)."""
    # Create workspace with members
    workspace = Workspace(
        name="Delete Test Workspace",
        description="Testing deletion",
        created_by=test_user.id,
    )
    db_session.add(workspace)
    db_session.commit()

    # Add members
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id="member-user",
        role=UserRole.MEMBER.value,
    )
    db_session.add(member)
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

    # Verify members cascade deleted (or orphaned)
    members = db_session.query(WorkspaceMember).filter_by(
        workspace_id=workspace_id
    ).all()

    # Members should be deleted or have null workspace_id
    assert len(members) == 0


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
def test_workspace_member_roles(db_session: Session, test_user: User):
    """Test different member roles in workspace."""
    # Create workspace
    workspace = Workspace(
        name="Role Test Workspace",
        created_by=test_user.id,
    )
    db_session.add(workspace)
    db_session.commit()

    # Add members with different roles
    owner = WorkspaceMember(
        workspace_id=workspace.id,
        user_id="owner-user",
        role=UserRole.OWNER.value,
    )
    admin = WorkspaceMember(
        workspace_id=workspace.id,
        user_id="admin-user",
        role=UserRole.ADMIN.value,
    )
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id="member-user",
        role=UserRole.MEMBER.value,
    )
    viewer = WorkspaceMember(
        workspace_id=workspace.id,
        user_id="viewer-user",
        role=UserRole.VIEWER.value,
    )
    db_session.add_all([owner, admin, member, viewer])
    db_session.commit()

    # Query and verify roles
    members = db_session.query(WorkspaceMember).filter_by(
        workspace_id=workspace.id
    ).order_by(WorkspaceMember.role).all()

    assert len(members) == 4

    # Verify all roles present
    roles = {m.role for m in members}
    assert UserRole.OWNER.value in roles
    assert UserRole.ADMIN.value in roles
    assert UserRole.MEMBER.value in roles
    assert UserRole.VIEWER.value in roles


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
