"""
Enterprise User Management Coverage Tests
Comprehensive test coverage for enterprise user management, team collaboration, and workspace isolation
Target: 60%+ coverage (125+ lines)
"""

import pytest
from fastapi import status
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch
from datetime import datetime

from core.models import Workspace, Team, User, UserRole, UserStatus, WorkspaceStatus
from core.database import get_db


# ==================== Fixtures ====================

@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def sample_workspace():
    """Sample workspace for testing"""
    workspace = Mock(spec=Workspace)
    workspace.id = "workspace-123"
    workspace.name = "Test Workspace"
    workspace.description = "A test workspace"
    workspace.status = WorkspaceStatus.ACTIVE.value
    workspace.plan_tier = "standard"
    workspace.created_at = datetime.now()
    workspace.updated_at = datetime.now()
    workspace.users = []
    workspace.teams = []
    return workspace


@pytest.fixture
def sample_team():
    """Sample team for testing"""
    team = Mock(spec=Team)
    team.id = "team-123"
    team.name = "Test Team"
    team.description = "A test team"
    team.workspace_id = "workspace-123"
    team.created_at = datetime.now()
    team.members = []
    return team


@pytest.fixture
def sample_user():
    """Sample user for testing"""
    user = Mock(spec=User)
    user.id = "user-123"
    user.email = "test@example.com"
    user.first_name = "John"
    user.last_name = "Doe"
    user.role = UserRole.MEMBER.value
    user.status = UserStatus.ACTIVE.value
    user.workspace_id = "workspace-123"
    user.created_at = datetime.now()
    user.last_login = datetime.now()
    user.teams = []
    return user


# ==================== Test Workspace Management ====================

class TestWorkspaceManagement:
    """Tests for workspace CRUD operations"""

    def test_create_workspace_success(self, mock_db, sample_workspace):
        """Test successful workspace creation"""
        from core.enterprise_user_management import create_workspace
        from core.enterprise_user_management import WorkspaceCreate

        workspace_data = WorkspaceCreate(
            name="Test Workspace",
            description="A test workspace",
            plan_tier="standard"
        )

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        # Mock the Workspace constructor to return our sample
        with patch('core.enterprise_user_management.Workspace', return_value=sample_workspace):
            result = create_workspace(workspace_data, mock_db)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert result["workspace_id"] == "workspace-123"

    def test_create_workspace_minimal_data(self, mock_db, sample_workspace):
        """Test workspace creation with minimal required data"""
        from core.enterprise_user_management import create_workspace, WorkspaceCreate

        workspace_data = WorkspaceCreate(name="Minimal Workspace")

        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch('core.enterprise_user_management.Workspace', return_value=sample_workspace):
            result = create_workspace(workspace_data, mock_db)

        assert result["workspace_id"] == "workspace-123"

    def test_list_workspaces_empty(self, mock_db):
        """Test listing workspaces when none exist"""
        from core.enterprise_user_management import list_workspaces

        mock_db.query = Mock(return_value=Mock(all=Mock(return_value=[])))

        result = list_workspaces(mock_db)

        assert result == []
        mock_db.query.assert_called_once_with(Workspace)

    def test_list_workspaces_with_data(self, mock_db, sample_workspace):
        """Test listing workspaces with existing workspaces"""
        from core.enterprise_user_management import list_workspaces

        mock_query = Mock()
        mock_query.all = Mock(return_value=[sample_workspace])
        mock_db.query = Mock(return_value=mock_query)

        result = list_workspaces(mock_db)

        assert len(result) == 1
        assert result[0]["workspace_id"] == "workspace-123"
        assert result[0]["name"] == "Test Workspace"

    def test_get_workspace_success(self, mock_db, sample_workspace):
        """Test getting workspace by ID"""
        from core.enterprise_user_management import get_workspace

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=sample_workspace)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        result = get_workspace("workspace-123", mock_db)

        assert result["workspace_id"] == "workspace-123"
        assert result["name"] == "Test Workspace"

    def test_get_workspace_not_found(self, mock_db):
        """Test getting non-existent workspace"""
        from core.enterprise_user_management import get_workspace
        from fastapi import HTTPException

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=None)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        with pytest.raises(HTTPException) as exc_info:
            get_workspace("nonexistent", mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Workspace not found" in str(exc_info.value.detail)

    def test_update_workspace_success(self, mock_db, sample_workspace):
        """Test successful workspace update"""
        from core.enterprise_user_management import update_workspace, WorkspaceUpdate

        update_data = WorkspaceUpdate(name="Updated Workspace")

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=sample_workspace)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        result = update_workspace("workspace-123", update_data, mock_db)

        assert sample_workspace.name == "Updated Workspace"
        mock_db.commit.assert_called_once()
        assert result["message"] == "Workspace updated successfully"

    def test_update_workspace_not_found(self, mock_db):
        """Test updating non-existent workspace"""
        from core.enterprise_user_management import update_workspace, WorkspaceUpdate
        from fastapi import HTTPException

        update_data = WorkspaceUpdate(name="Updated")

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=None)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        with pytest.raises(HTTPException) as exc_info:
            update_workspace("nonexistent", update_data, mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_workspace_success(self, mock_db, sample_workspace):
        """Test successful workspace deletion (soft delete)"""
        from core.enterprise_user_management import delete_workspace

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=sample_workspace)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)
        mock_db.commit = Mock()

        result = delete_workspace("workspace-123", mock_db)

        assert sample_workspace.status == "deleted"
        mock_db.commit.assert_called_once()
        assert result["message"] == "Workspace deleted successfully"


# ==================== Test Team Management ====================

class TestTeamManagement:
    """Tests for team CRUD operations"""

    def test_create_team_success(self, mock_db, sample_team):
        """Test successful team creation"""
        from core.enterprise_user_management import create_team, TeamCreate

        team_data = TeamCreate(
            name="Test Team",
            description="A test team",
            workspace_id="workspace-123"
        )

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=Mock(spec=Workspace))
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        with patch('core.enterprise_user_management.Team', return_value=sample_team):
            result = create_team(team_data, mock_db)

        mock_db.add.assert_called_once()
        assert result["team_id"] == "team-123"

    def test_create_team_workspace_not_found(self, mock_db):
        """Test creating team in non-existent workspace"""
        from core.enterprise_user_management import create_team, TeamCreate
        from fastapi import HTTPException

        team_data = TeamCreate(
            name="Test Team",
            workspace_id="nonexistent"
        )

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=None)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        with pytest.raises(HTTPException) as exc_info:
            create_team(team_data, mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Workspace not found" in str(exc_info.value.detail)

    def test_list_teams_no_filter(self, mock_db, sample_team):
        """Test listing all teams without workspace filter"""
        from core.enterprise_user_management import list_teams

        mock_query = Mock()
        mock_query.all = Mock(return_value=[sample_team])
        mock_db.query = Mock(return_value=mock_query)

        result = list_teams(None, mock_db)

        assert len(result) == 1
        assert result[0]["team_id"] == "team-123"

    def test_list_teams_with_workspace_filter(self, mock_db, sample_team):
        """Test listing teams filtered by workspace"""
        from core.enterprise_user_management import list_teams

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.all = Mock(return_value=[sample_team])
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        result = list_teams("workspace-123", mock_db)

        assert len(result) == 1
        mock_query.filter.assert_called_once()

    def test_get_team_success(self, mock_db, sample_team):
        """Test getting team by ID"""
        from core.enterprise_user_management import get_team

        sample_team.members = []

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=sample_team)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        result = get_team("team-123", mock_db)

        assert result["team_id"] == "team-123"
        assert result["name"] == "Test Team"
        assert result["members"] == []

    def test_get_team_not_found(self, mock_db):
        """Test getting non-existent team"""
        from core.enterprise_user_management import get_team
        from fastapi import HTTPException

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=None)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        with pytest.raises(HTTPException) as exc_info:
            get_team("nonexistent", mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_update_team_success(self, mock_db, sample_team):
        """Test successful team update"""
        from core.enterprise_user_management import update_team, TeamUpdate

        update_data = TeamUpdate(name="Updated Team")

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=sample_team)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        result = update_team("team-123", update_data, mock_db)

        assert sample_team.name == "Updated Team"
        assert result["message"] == "Team updated successfully"

    def test_delete_team_success(self, mock_db, sample_team):
        """Test successful team deletion"""
        from core.enterprise_user_management import delete_team

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=sample_team)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)
        mock_db.delete = Mock()
        mock_db.commit = Mock()

        result = delete_team("team-123", mock_db)

        mock_db.delete.assert_called_once_with(sample_team)
        mock_db.commit.assert_called_once()
        assert result["message"] == "Team deleted successfully"


# ==================== Test User Management ====================

class TestUserManagement:
    """Tests for user CRUD operations"""

    def test_list_users_no_filter(self, mock_db, sample_user):
        """Test listing all users without workspace filter"""
        from core.enterprise_user_management import list_users

        mock_query = Mock()
        mock_query.all = Mock(return_value=[sample_user])
        mock_db.query = Mock(return_value=mock_query)

        result = list_users(None, mock_db)

        assert len(result) == 1
        assert result[0]["user_id"] == "user-123"
        assert result[0]["email"] == "test@example.com"

    def test_list_users_with_workspace_filter(self, mock_db, sample_user):
        """Test listing users filtered by workspace"""
        from core.enterprise_user_management import list_users

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.all = Mock(return_value=[sample_user])
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        result = list_users("workspace-123", mock_db)

        assert len(result) == 1
        mock_query.filter.assert_called_once()

    def test_get_user_success(self, mock_db, sample_user):
        """Test getting user by ID"""
        from core.enterprise_user_management import get_user

        sample_user.teams = []

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=sample_user)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        result = get_user("user-123", mock_db)

        assert result["user_id"] == "user-123"
        assert result["email"] == "test@example.com"
        assert result["teams"] == []

    def test_get_user_not_found(self, mock_db):
        """Test getting non-existent user"""
        from core.enterprise_user_management import get_user
        from fastapi import HTTPException

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=None)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        with pytest.raises(HTTPException) as exc_info:
            get_user("nonexistent", mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_update_user_success(self, mock_db, sample_user):
        """Test successful user update"""
        from core.enterprise_user_management import update_user, UserUpdate

        update_data = UserUpdate(
            first_name="Jane",
            role=UserRole.ADMIN.value
        )

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=sample_user)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        result = update_user("user-123", update_data, mock_db)

        assert sample_user.first_name == "Jane"
        assert sample_user.role == UserRole.ADMIN.value
        assert result["message"] == "User updated successfully"

    def test_deactivate_user_success(self, mock_db, sample_user):
        """Test successful user deactivation"""
        from core.enterprise_user_management import deactivate_user

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=sample_user)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)
        mock_db.commit = Mock()

        result = deactivate_user("user-123", mock_db)

        assert sample_user.status == UserStatus.DELETED.value
        mock_db.commit.assert_called_once()
        assert result["message"] == "User deactivated successfully"


# ==================== Test Team Membership ====================

class TestTeamMembership:
    """Tests for team membership management"""

    def test_add_team_member_success(self, mock_db, sample_team, sample_user):
        """Test successfully adding user to team"""
        from core.enterprise_user_management import add_team_member

        sample_team.members = []

        # Mock team query
        mock_team_query = Mock()
        mock_team_filter = Mock()
        mock_team_filter.first = Mock(return_value=sample_team)
        mock_team_query.filter = Mock(return_value=mock_team_filter)

        # Mock user query
        mock_user_query = Mock()
        mock_user_filter = Mock()
        mock_user_filter.first = Mock(return_value=sample_user)
        mock_user_query.filter = Mock(return_value=mock_user_filter)

        mock_db.query = Mock(side_effect=[mock_team_query, mock_user_query])
        mock_db.commit = Mock()

        result = add_team_member("team-123", "user-123", mock_db)

        mock_db.commit.assert_called_once()
        assert result["message"] == "User added to team successfully"

    def test_add_team_member_team_not_found(self, mock_db):
        """Test adding user to non-existent team"""
        from core.enterprise_user_management import add_team_member
        from fastapi import HTTPException

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=None)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        with pytest.raises(HTTPException) as exc_info:
            add_team_member("nonexistent", "user-123", mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_add_team_member_user_not_found(self, mock_db, sample_team):
        """Test adding non-existent user to team"""
        from core.enterprise_user_management import add_team_member
        from fastapi import HTTPException

        sample_team.members = []

        # Mock team query (returns team)
        mock_team_query = Mock()
        mock_team_filter = Mock()
        mock_team_filter.first = Mock(return_value=sample_team)
        mock_team_query.filter = Mock(return_value=mock_team_filter)

        # Mock user query (returns None)
        mock_user_query = Mock()
        mock_user_filter = Mock()
        mock_user_filter.first = Mock(return_value=None)
        mock_user_query.filter = Mock(return_value=mock_user_filter)

        mock_db.query = Mock(side_effect=[mock_team_query, mock_user_query])

        with pytest.raises(HTTPException) as exc_info:
            add_team_member("team-123", "nonexistent", mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in str(exc_info.value.detail)

    def test_add_team_member_already_member(self, mock_db, sample_team, sample_user):
        """Test adding user who is already a team member"""
        from core.enterprise_user_management import add_team_member
        from fastapi import HTTPException

        sample_team.members = [sample_user]

        # Mock team query
        mock_team_query = Mock()
        mock_team_filter = Mock()
        mock_team_filter.first = Mock(return_value=sample_team)
        mock_team_query.filter = Mock(return_value=mock_team_filter)

        # Mock user query
        mock_user_query = Mock()
        mock_user_filter = Mock()
        mock_user_filter.first = Mock(return_value=sample_user)
        mock_user_query.filter = Mock(return_value=mock_user_filter)

        mock_db.query = Mock(side_effect=[mock_team_query, mock_user_query])

        with pytest.raises(HTTPException) as exc_info:
            add_team_member("team-123", "user-123", mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "already a team member" in str(exc_info.value.detail)

    def test_remove_team_member_success(self, mock_db, sample_team, sample_user):
        """Test successfully removing user from team"""
        from core.enterprise_user_management import remove_team_member

        sample_team.members = [sample_user]

        # Mock team query
        mock_team_query = Mock()
        mock_team_filter = Mock()
        mock_team_filter.first = Mock(return_value=sample_team)
        mock_team_query.filter = Mock(return_value=mock_team_filter)

        # Mock user query
        mock_user_query = Mock()
        mock_user_filter = Mock()
        mock_user_filter.first = Mock(return_value=sample_user)
        mock_user_query.filter = Mock(return_value=mock_user_filter)

        mock_db.query = Mock(side_effect=[mock_team_query, mock_user_query])
        mock_db.commit = Mock()

        result = remove_team_member("team-123", "user-123", mock_db)

        mock_db.commit.assert_called_once()
        assert result["message"] == "User removed from team successfully"

    def test_remove_team_member_team_not_found(self, mock_db):
        """Test removing user from non-existent team"""
        from core.enterprise_user_management import remove_team_member
        from fastapi import HTTPException

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=None)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        with pytest.raises(HTTPException) as exc_info:
            remove_team_member("nonexistent", "user-123", mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_remove_team_member_not_in_team(self, mock_db, sample_team, sample_user):
        """Test removing user who is not a team member"""
        from core.enterprise_user_management import remove_team_member
        from fastapi import HTTPException

        sample_team.members = []  # User not in team

        # Mock team query
        mock_team_query = Mock()
        mock_team_filter = Mock()
        mock_team_filter.first = Mock(return_value=sample_team)
        mock_team_query.filter = Mock(return_value=mock_team_filter)

        # Mock user query
        mock_user_query = Mock()
        mock_user_filter = Mock()
        mock_user_filter.first = Mock(return_value=sample_user)
        mock_user_query.filter = Mock(return_value=mock_user_filter)

        mock_db.query = Mock(side_effect=[mock_team_query, mock_user_query])

        with pytest.raises(HTTPException) as exc_info:
            remove_team_member("team-123", "user-123", mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "not a team member" in str(exc_info.value.detail)


# ==================== Test Workspace Teams ====================

class TestWorkspaceTeams:
    """Tests for workspace-team relationships"""

    def test_get_workspace_teams_success(self, mock_db, sample_workspace, sample_team):
        """Test getting all teams in a workspace"""
        from core.enterprise_user_management import get_workspace_teams

        # Mock workspace query
        mock_workspace_query = Mock()
        mock_workspace_filter = Mock()
        mock_workspace_filter.first = Mock(return_value=sample_workspace)
        mock_workspace_query.filter = Mock(return_value=mock_workspace_filter)

        # Mock team query
        mock_team_query = Mock()
        mock_team_filter = Mock()
        mock_team_filter.all = Mock(return_value=[sample_team])
        mock_team_query.filter = Mock(return_value=mock_team_filter)

        mock_db.query = Mock(side_effect=[mock_workspace_query, mock_team_query])

        result = get_workspace_teams("workspace-123", mock_db)

        assert len(result) == 1
        assert result[0]["team_id"] == "team-123"

    def test_get_workspace_teams_workspace_not_found(self, mock_db):
        """Test getting teams for non-existent workspace"""
        from core.enterprise_user_management import get_workspace_teams
        from fastapi import HTTPException

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=None)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        with pytest.raises(HTTPException) as exc_info:
            get_workspace_teams("nonexistent", mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ==================== Test User Teams ====================

class TestUserTeams:
    """Tests for user-team relationships"""

    def test_get_user_teams_success(self, mock_db, sample_user, sample_team):
        """Test getting all teams for a user"""
        from core.enterprise_user_management import get_user_teams

        sample_user.teams = [sample_team]

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=sample_user)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        result = get_user_teams("user-123", mock_db)

        assert len(result) == 1
        assert result[0]["team_id"] == "team-123"

    def test_get_user_teams_user_not_found(self, mock_db):
        """Test getting teams for non-existent user"""
        from core.enterprise_user_management import get_user_teams
        from fastapi import HTTPException

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first = Mock(return_value=None)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_db.query = Mock(return_value=mock_query)

        with pytest.raises(HTTPException) as exc_info:
            get_user_teams("nonexistent", mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
