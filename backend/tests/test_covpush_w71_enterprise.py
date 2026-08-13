"""Coverage wave 71 — core/enterprise_user_management.py (93% → 95%+).

Closes the remaining holes:
- workspace update: description / status / plan_tier branches
- workspace soft-delete body
- team update: name + description branches, team delete
- remove_team_member: user-not-found path
- get_user: user-not-found path
- update_user: first_name branch, invalid-role 400, status branch
- deactivate_user: user-not-found path
- import-time EmailStr fallback branch (EMAIL_VALIDATION_AVAILABLE=False)
"""
import importlib
import sys
import types
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from core import enterprise_user_management as eum
from core.enterprise_user_management import (
    TeamCreate,
    TeamUpdate,
    UserCreate,
    UserUpdate,
    WorkspaceCreate,
    WorkspaceUpdate,
    add_team_member,
    create_team,
    create_workspace,
    deactivate_user,
    delete_team,
    delete_workspace,
    get_team,
    get_user,
    get_user_teams,
    get_workspace,
    get_workspace_teams,
    list_teams,
    list_users,
    list_workspaces,
    remove_team_member,
    update_team,
    update_user,
    update_workspace,
)
from core.models import User, UserRole, UserStatus, Workspace, WorkspaceStatus


@pytest.fixture
def db():
    return Mock()


@pytest.fixture
def workspace():
    w = Mock(spec=Workspace)
    w.id = "ws-1"
    w.name = "Acme"
    w.description = "d"
    w.status = WorkspaceStatus.ACTIVE.value
    w.plan_tier = "standard"
    w.created_at = datetime.now()
    w.updated_at = datetime.now()
    w.users = []
    w.teams = []
    return w


@pytest.fixture
def team():
    t = Mock()
    t.id = "team-1"
    t.name = "Eng"
    t.description = "desc"
    t.workspace_id = "ws-1"
    t.created_at = datetime.now()
    t.members = []
    return t


@pytest.fixture
def user():
    u = Mock(spec=User)
    u.id = "user-1"
    u.email = "a@b.com"
    u.first_name = "A"
    u.last_name = "B"
    u.role = UserRole.MEMBER.value
    u.status = UserStatus.ACTIVE.value
    u.workspace_id = "ws-1"
    u.created_at = datetime.now()
    u.last_login = None
    u.teams = []
    return u


class TestWorkspaceEndpoints:
    async def test_create_workspace(self, db):
        created = Mock(spec=Workspace)
        created.id = "ws-new"
        with patch.object(eum, "Workspace", return_value=created):
            result = await create_workspace(WorkspaceCreate(name="X", plan_tier="pro"), db)
        assert result == {"workspace_id": "ws-new"}
        db.add.assert_called_once_with(created)
        db.commit.assert_called()

    async def test_list_workspaces(self, db, workspace):
        db.query.return_value.all.return_value = [workspace]
        result = await list_workspaces(db)
        assert result[0]["workspace_id"] == "ws-1"

    async def test_get_workspace_found(self, db, workspace):
        db.query.return_value.filter.return_value.first.return_value = workspace
        result = await get_workspace("ws-1", db)
        assert result["name"] == "Acme"

    async def test_get_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await get_workspace("ghost", db)
        assert e.value.status_code == 404

    async def test_update_workspace_all_fields(self, db, workspace):
        db.query.return_value.filter.return_value.first.return_value = workspace
        result = await update_workspace("ws-1", WorkspaceUpdate(
            name="New Name", description="new desc",
            status="suspended", plan_tier="enterprise"), db)
        assert workspace.name == "New Name"
        assert workspace.description == "new desc"
        assert workspace.status == "suspended"
        assert workspace.plan_tier == "enterprise"
        assert result["message"] == "Workspace updated successfully"

    async def test_update_workspace_no_fields(self, db, workspace):
        db.query.return_value.filter.return_value.first.return_value = workspace
        await update_workspace("ws-1", WorkspaceUpdate(), db)
        assert workspace.name == "Acme"

    async def test_update_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await update_workspace("ghost", WorkspaceUpdate(name="x"), db)
        assert e.value.status_code == 404

    async def test_delete_workspace_soft_delete(self, db, workspace):
        db.query.return_value.filter.return_value.first.return_value = workspace
        result = await delete_workspace("ws-1", db)
        assert workspace.status == "deleted"
        assert result["message"] == "Workspace deleted successfully"

    async def test_delete_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await delete_workspace("ghost", db)
        assert e.value.status_code == 404

    async def test_get_workspace_teams(self, db, workspace, team):
        db.query.return_value.filter.return_value.first.return_value = workspace
        db.query.return_value.filter.return_value.all.return_value = [team]
        result = await get_workspace_teams("ws-1", db)
        assert result[0]["team_id"] == "team-1"
        assert result[0]["member_count"] == 0

    async def test_get_workspace_teams_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await get_workspace_teams("ghost", db)
        assert e.value.status_code == 404


class TestTeamEndpoints:
    async def test_create_team(self, db, workspace):
        created = Mock()
        created.id = "team-new"
        db.query.return_value.filter.return_value.first.return_value = workspace
        with patch.object(eum, "Team", return_value=created):
            result = await create_team(TeamCreate(name="T", workspace_id="ws-1"), db)
        assert result == {"team_id": "team-new"}

    async def test_create_team_workspace_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await create_team(TeamCreate(name="T", workspace_id="ghost"), db)
        assert e.value.status_code == 404

    async def test_list_teams_all(self, db, team):
        db.query.return_value.all.return_value = [team]
        result = await list_teams(None, db)
        assert result[0]["team_id"] == "team-1"

    async def test_list_teams_filtered(self, db, team):
        db.query.return_value.filter.return_value.all.return_value = [team]
        result = await list_teams("ws-1", db)
        assert len(result) == 1

    async def test_get_team_found_with_members(self, db, team, user):
        team.members = [user]
        db.query.return_value.filter.return_value.first.return_value = team
        result = await get_team("team-1", db)
        assert result["member_count"] == 1
        assert result["members"][0]["email"] == "a@b.com"

    async def test_get_team_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await get_team("ghost", db)
        assert e.value.status_code == 404

    async def test_update_team_name_and_description(self, db, team):
        db.query.return_value.filter.return_value.first.return_value = team
        result = await update_team("team-1", TeamUpdate(name="New Eng", description="nd"), db)
        assert team.name == "New Eng"
        assert team.description == "nd"
        assert result["message"] == "Team updated successfully"

    async def test_update_team_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await update_team("ghost", TeamUpdate(name="x"), db)
        assert e.value.status_code == 404

    async def test_delete_team(self, db, team):
        db.query.return_value.filter.return_value.first.return_value = team
        result = await delete_team("team-1", db)
        db.delete.assert_called_once_with(team)
        assert result["message"] == "Team deleted successfully"

    async def test_delete_team_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await delete_team("ghost", db)
        assert e.value.status_code == 404

    async def test_add_team_member(self, db, team, user):
        db.query.return_value.filter.return_value.first.side_effect = [team, user]
        result = await add_team_member("team-1", "user-1", db)
        assert result == {"message": "User added to team successfully"}

    async def test_add_team_member_team_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await add_team_member("ghost", "user-1", db)
        assert e.value.status_code == 404

    async def test_add_team_member_user_not_found(self, db, team):
        db.query.return_value.filter.return_value.first.side_effect = [team, None]
        with pytest.raises(HTTPException) as e:
            await add_team_member("team-1", "ghost", db)
        assert e.value.status_code == 404

    async def test_add_team_member_already_member(self, db, team, user):
        team.members = [user]
        db.query.return_value.filter.return_value.first.side_effect = [team, user]
        with pytest.raises(HTTPException) as e:
            await add_team_member("team-1", "user-1", db)
        assert e.value.status_code == 400

    async def test_remove_team_member(self, db, team, user):
        team.members = [user]
        db.query.return_value.filter.return_value.first.side_effect = [team, user]
        result = await remove_team_member("team-1", "user-1", db)
        assert user not in team.members
        assert result["message"] == "User removed from team successfully"

    async def test_remove_team_member_team_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await remove_team_member("ghost", "user-1", db)
        assert e.value.status_code == 404

    async def test_remove_team_member_user_not_found(self, db, team):
        db.query.return_value.filter.return_value.first.side_effect = [team, None]
        with pytest.raises(HTTPException) as e:
            await remove_team_member("team-1", "ghost", db)
        assert e.value.status_code == 404

    async def test_remove_team_member_not_in_team(self, db, team, user):
        db.query.return_value.filter.return_value.first.side_effect = [team, user]
        with pytest.raises(HTTPException) as e:
            await remove_team_member("team-1", "user-1", db)
        assert e.value.status_code == 400


class TestUserEndpoints:
    async def test_list_users_all(self, db, user):
        db.query.return_value.all.return_value = [user]
        result = await list_users(None, db)
        assert result[0]["user_id"] == "user-1"
        assert result[0]["last_login"] is None

    async def test_list_users_filtered(self, db, user):
        db.query.return_value.filter.return_value.all.return_value = [user]
        result = await list_users("ws-1", db)
        assert len(result) == 1

    async def test_get_user_found(self, db, user):
        t = Mock(id="team-1")
        t.name = "Eng"
        user.teams = [t]
        db.query.return_value.filter.return_value.first.return_value = user
        result = await get_user("user-1", db)
        assert result["teams"][0]["name"] == "Eng"

    async def test_get_user_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await get_user("ghost", db)
        assert e.value.status_code == 404

    async def test_update_user_all_fields(self, db, user):
        db.query.return_value.filter.return_value.first.return_value = user
        result = await update_user("user-1", UserUpdate(
            first_name="X", last_name="Y", role="admin", status="suspended"), db)
        assert user.first_name == "X"
        assert user.last_name == "Y"
        assert user.role == "admin"
        assert user.status == "suspended"
        assert result["message"] == "User updated successfully"

    async def test_update_user_invalid_role_400(self, db, user):
        db.query.return_value.filter.return_value.first.return_value = user
        with pytest.raises(HTTPException) as e:
            await update_user("user-1", UserUpdate(role="root"), db)
        assert e.value.status_code == 400
        assert "Invalid role" in e.value.detail

    async def test_update_user_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await update_user("ghost", UserUpdate(first_name="x"), db)
        assert e.value.status_code == 404

    async def test_deactivate_user(self, db, user):
        db.query.return_value.filter.return_value.first.return_value = user
        result = await deactivate_user("user-1", db)
        assert user.status == UserStatus.DELETED.value
        assert result["message"] == "User deactivated successfully"

    async def test_deactivate_user_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await deactivate_user("ghost", db)
        assert e.value.status_code == 404

    async def test_get_user_teams(self, db, user):
        user.teams = [Mock(id="team-1", name="Eng", description="d", workspace_id="ws-1")]
        db.query.return_value.filter.return_value.first.return_value = user
        result = await get_user_teams("user-1", db)
        assert result[0]["team_id"] == "team-1"

    async def test_get_user_teams_not_found(self, db):
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(HTTPException) as e:
            await get_user_teams("ghost", db)
        assert e.value.status_code == 404


class TestImportFallback:
    def test_emailstr_import_fallback_branch(self):
        import pydantic as real_pydantic

        fake = types.ModuleType("pydantic")
        fake.BaseModel = real_pydantic.BaseModel
        fake.Field = real_pydantic.Field
        old_module = sys.modules["pydantic"]
        sys.modules["pydantic"] = fake
        try:
            mod = importlib.reload(eum)
            assert mod.EMAIL_VALIDATION_AVAILABLE is False
            assert mod.EmailStr is str
        finally:
            sys.modules["pydantic"] = old_module
            importlib.reload(eum)
        assert eum.EMAIL_VALIDATION_AVAILABLE is True

    def test_user_create_defaults(self):
        c = UserCreate(email="a@b.com", password="pw", first_name="A", last_name="B")
        assert c.role == UserRole.MEMBER.value
        assert c.workspace_id is None

    def test_workspace_create_default_plan(self):
        assert WorkspaceCreate(name="X").plan_tier == "standard"
