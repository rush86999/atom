# -*- coding: utf-8 -*-
"""Coverage wave 99 — tools/platform_management_tool.py (was 20%).

Uses a real in-memory SQLite schema (create_all) with SessionLocal patched to
an in-memory sessionmaker, so all query/commit paths execute for real.

Bugs found (RED -> GREEN, both pinned by failing tests here):
1. update_tenant_profile wrote tenant.billing_email / tenant.budget_limit_usd /
   tenant.metadata_json, but the Tenant model declares none of those columns —
   assignments were silently dropped on commit (data loss while reporting
   success). Fixed by adding the three nullable columns to core/models.Tenant.
2. list_tenant_members used `m.full_name` — User has a `name` property, no
   `full_name` — every call hit AttributeError and returned
   "Error listing tenant members". Fixed to `m.name`.

Coverage: get/update platform settings, update_tenant_profile (all fields,
missing tenant, no updates, exception), set_byok_api_key (no context, success,
ValueError, exception), list_tenant_members (no context, missing workspace,
empty, populated, exception), manage_tenant_member (all actions), manage_workspace
(create/update/unknown/tenant resolution), manage_team (create with members,
update, unknown, exception), tenant/workspace/team CRUD helpers
(success/not-found/exception), member add/remove strings, setup helpers.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    AgentRegistry,  # noqa: F401 (register models)
    Team,
    Tenant,
    TenantSetting,
    User,
    Workspace,
)

from tools import platform_management_tool as pm


# ============================================================================
# Shared fixtures
# ============================================================================

@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def session_factory(db):
    factory = sessionmaker(bind=db.bind)
    with patch("core.database.SessionLocal", factory), \
         patch.object(pm, "SessionLocal", factory):
        yield factory


def _make_tenant(db, tenant_id="t-1", name="Acme"):
    t = Tenant(id=tenant_id, name=name, subdomain=tenant_id)
    db.add(t)
    db.commit()
    return t


def _make_workspace(db, ws_id="ws-1", tenant_id="t-1", name="Main"):
    ws = Workspace(id=ws_id, name=name, tenant_id=tenant_id)
    db.add(ws)
    db.commit()
    return ws


def _make_user(db, user_id="u-1", tenant_id="t-1", email="u@atom.ai",
               first="U", last="Ser", role="MEMBER"):
    u = User(id=user_id, tenant_id=tenant_id, email=email, first_name=first,
             last_name=last, role=role, status="active", is_active=True)
    db.add(u)
    db.commit()
    return u


# ============================================================================
# Bug pins (RED before the model/string fixes)
# ============================================================================

class TestBugPins:
    def test_tenant_profile_fields_persist(self, db, session_factory):
        """RED: billing_email/budget_limit_usd/metadata_json were silently
        dropped — Tenant model lacked the columns."""
        _make_tenant(db)
        _make_workspace(db)
        with patch("core.database.SessionLocal", session_factory):
            msg = pytest_asyncio_run(pm.update_tenant_profile(
                billing_email="b@acme.ai", budget_limit_usd=99.5,
                logo_url="https://l/logo.png", primary_color="#fff",
                context={"workspace_id": "ws-1"}))
        assert "billing_email" in msg
        db.expire_all()
        fresh = db.query(Tenant).filter(Tenant.id == "t-1").first()
        assert fresh.billing_email == "b@acme.ai"
        assert fresh.budget_limit_usd == 99.5
        assert fresh.metadata_json["logo_url"] == "https://l/logo.png"
        assert fresh.metadata_json["primary_color"] == "#fff"

    def test_list_members_uses_name_not_full_name(self, db, session_factory):
        """RED: `m.full_name` raised AttributeError on real User rows ->
        always 'Error listing tenant members'."""
        _make_tenant(db)
        _make_workspace(db)
        _make_user(db)
        result = pytest_asyncio_run(pm.list_tenant_members(
            context={"workspace_id": "ws-1"}))
        assert "Members for Tenant t-1:" in result
        assert "U Ser" in result
        assert "Error" not in result


def pytest_asyncio_run(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)


# ============================================================================
# Platform settings
# ============================================================================

class TestPlatformSettings:
    def test_get_settings(self, db, session_factory):
        _make_tenant(db, tenant_id="default")
        db.add(TenantSetting(tenant_id="default", setting_key="theme", setting_value="dark"))
        db.commit()
        result = pytest_asyncio_run(pm.get_platform_settings(
            context={"workspace_id": "default"}))
        assert result == {"theme": "dark"}

    def test_get_settings_no_context_defaults(self, db, session_factory):
        _make_tenant(db, tenant_id="default")
        db.add(TenantSetting(tenant_id="default", setting_key="k", setting_value="v"))
        db.commit()
        result = pytest_asyncio_run(pm.get_platform_settings())
        assert result == {"k": "v"}

    def test_get_settings_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.get_platform_settings())
        assert result == {"error": "Failed to fetch settings"}

    def test_update_creates_new(self, db, session_factory):
        _make_tenant(db, tenant_id="default")
        result = pytest_asyncio_run(pm.update_platform_setting(
            "notify", "on", context={"workspace_id": "default"}))
        assert "successfully updated" in result
        row = db.query(TenantSetting).filter(TenantSetting.setting_key == "notify").first()
        assert row.setting_value == "on"

    def test_update_existing(self, db, session_factory):
        _make_tenant(db, tenant_id="default")
        db.add(TenantSetting(tenant_id="default", setting_key="k", setting_value="old"))
        db.commit()
        result = pytest_asyncio_run(pm.update_platform_setting(
            "k", "new", context={"workspace_id": "default"}))
        assert "successfully updated" in result
        assert db.query(TenantSetting).count() == 1
        db.expire_all()
        assert db.query(TenantSetting).first().setting_value == "new"

    def test_update_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.update_platform_setting("k", "v"))
        assert result == "Error: Failed to update setting"


# ============================================================================
# update_tenant_profile
# ============================================================================

class TestUpdateTenantProfile:
    def test_default_tenant_missing(self, db, session_factory):
        result = pytest_asyncio_run(pm.update_tenant_profile(name="X"))
        assert "Default tenant not found" in result

    def test_custom_tenant_missing(self, db, session_factory):
        _make_workspace(db, ws_id="ws-2", tenant_id="t-9")
        result = pytest_asyncio_run(pm.update_tenant_profile(
            name="X", context={"workspace_id": "ws-2"}))
        assert "Tenant t-9 not found" in result

    def test_no_updates(self, db, session_factory):
        _make_tenant(db)
        _make_workspace(db)
        result = pytest_asyncio_run(pm.update_tenant_profile(
            context={"workspace_id": "ws-1"}))
        assert result == "No updates provided."

    def test_name_and_email(self, db, session_factory):
        _make_tenant(db)
        _make_workspace(db)
        result = pytest_asyncio_run(pm.update_tenant_profile(
            name="NewCo", billing_email="b@new.co",
            context={"workspace_id": "ws-1"}))
        assert "name" in result and "billing_email" in result
        db.expire_all()
        t = db.query(Tenant).filter(Tenant.id == "t-1").first()
        assert t.name == "NewCo"
        assert t.billing_email == "b@new.co"

    def test_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.update_tenant_profile(name="X"))
        assert result == "Error: Failed to update tenant profile"


# ============================================================================
# set_byok_api_key
# ============================================================================

class TestSetByokApiKey:
    def test_no_context(self, db, session_factory):
        result = pytest_asyncio_run(pm.set_byok_api_key("openai", "sk-x"))
        assert "Could not resolve tenant" in result

    def test_success(self, db, session_factory):
        manager = MagicMock()
        with patch("core.byok_endpoints.BYOKManager", return_value=manager):
            result = pytest_asyncio_run(pm.set_byok_api_key(
                "openai", "sk-x", context={"workspace_id": "t-1"}))
        assert "Successfully set API key for openai" in result
        manager.store_api_key.assert_called_once_with(
            provider_id="openai", api_key="sk-x", key_name="default",
            environment="production")

    def test_invalid_provider(self, db, session_factory):
        with patch("core.byok_endpoints.BYOKManager") as cls:
            cls.return_value.store_api_key.side_effect = ValueError("bad")
            result = pytest_asyncio_run(pm.set_byok_api_key(
                "nope", "sk-x", context={"workspace_id": "t-1"}))
        assert "invalid provider or key" in result

    def test_exception(self, db, session_factory):
        with patch("core.byok_endpoints.BYOKManager") as cls:
            cls.return_value.store_api_key.side_effect = RuntimeError("boom")
            result = pytest_asyncio_run(pm.set_byok_api_key(
                "openai", "sk-x", context={"workspace_id": "t-1"}))
        assert result == "Error setting BYOK API key"


# ============================================================================
# list_tenant_members
# ============================================================================

class TestListTenantMembers:
    def test_no_context(self, db, session_factory):
        result = pytest_asyncio_run(pm.list_tenant_members())
        assert "Could not resolve workspace" in result

    def test_workspace_not_found(self, db, session_factory):
        result = pytest_asyncio_run(pm.list_tenant_members(
            context={"workspace_id": "missing"}))
        assert "Workspace missing not found" in result

    def test_no_members(self, db, session_factory):
        _make_tenant(db)
        _make_workspace(db)
        result = pytest_asyncio_run(pm.list_tenant_members(
            context={"workspace_id": "ws-1"}))
        assert result == "No members found for this tenant."

    def test_with_members(self, db, session_factory):
        _make_tenant(db)
        _make_workspace(db)
        _make_user(db)
        _make_user(db, user_id="u-2", email="two@atom.ai")
        result = pytest_asyncio_run(pm.list_tenant_members(
            context={"workspace_id": "ws-1"}))
        assert "Members for Tenant t-1:" in result
        assert "u-1" in result and "u-2" in result

    def test_exception(self, session_factory):
        boom = MagicMock()
        boom.query.side_effect = RuntimeError("down")
        with patch("core.database.SessionLocal", return_value=boom):
            result = pytest_asyncio_run(pm.list_tenant_members(
                context={"workspace_id": "ws-1"}))
        assert result == "Error listing tenant members"


# ============================================================================
# manage_tenant_member
# ============================================================================

class TestManageTenantMember:
    def test_user_not_found(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_tenant_member("ghost", "deactivate"))
        assert "User ghost not found" in result

    def test_update_role_requires_role(self, db, session_factory):
        _make_user(db)
        result = pytest_asyncio_run(pm.manage_tenant_member("u-1", "update_role"))
        assert "role is required" in result

    def test_update_role(self, db, session_factory):
        _make_user(db)
        result = pytest_asyncio_run(pm.manage_tenant_member(
            "u-1", "update_role", role="ADMIN"))
        assert "role updated to ADMIN" in result
        db.expire_all()
        assert db.query(User).filter(User.id == "u-1").first().role == "ADMIN"

    def test_deactivate(self, db, session_factory):
        _make_user(db)
        result = pytest_asyncio_run(pm.manage_tenant_member("u-1", "deactivate"))
        assert "deactivated" in result
        db.expire_all()
        assert db.query(User).filter(User.id == "u-1").first().is_active is False

    def test_reactivate(self, db, session_factory):
        u = _make_user(db)
        u.is_active = False
        db.commit()
        result = pytest_asyncio_run(pm.manage_tenant_member("u-1", "reactivate"))
        assert "reactivated" in result
        db.expire_all()
        assert db.query(User).filter(User.id == "u-1").first().is_active is True

    def test_unknown_action(self, db, session_factory):
        _make_user(db)
        result = pytest_asyncio_run(pm.manage_tenant_member("u-1", "fire"))
        assert "Unknown action" in result

    def test_exception(self, session_factory):
        boom = MagicMock()
        boom.query.side_effect = RuntimeError("down")
        with patch("core.database.SessionLocal", return_value=boom):
            result = pytest_asyncio_run(pm.manage_tenant_member("u-1", "deactivate"))
        assert result == "Error managing tenant member"


# ============================================================================
# manage_workspace
# ============================================================================

class TestManageWorkspace:
    def test_no_tenant_context(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_workspace("New"))
        assert "Could not resolve tenant ID" in result

    def test_create(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_workspace(
            "Sales", context={"tenant_id": "t-1"}))
        assert "created successfully" in result
        ws = db.query(Workspace).filter(Workspace.tenant_id == "t-1").first()
        assert ws.name == "Sales"

    def test_create_with_startup_flag(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_workspace(
            "Start", is_startup=True, context={"tenant_id": "t-1"}))
        assert "created successfully" in result
        ws = db.query(Workspace).filter(Workspace.name == "Start").first()
        assert ws.is_startup is True

    def test_create_resolves_tenant_from_workspace(self, db, session_factory):
        _make_tenant(db)
        _make_workspace(db, ws_id="ctx-ws", tenant_id="t-1")
        result = pytest_asyncio_run(pm.manage_workspace(
            "Derived", context={"workspace_id": "ctx-ws"}))
        assert "created successfully" in result
        ws = db.query(Workspace).filter(Workspace.name == "Derived").first()
        assert ws.tenant_id == "t-1"

    def test_update_requires_workspace_id(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_workspace(
            "X", action="update", context={"tenant_id": "t-1"}))
        assert "workspace_id is required" in result

    def test_update_not_found(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_workspace(
            "X", action="update", workspace_id="nope",
            context={"tenant_id": "t-1"}))
        assert "Workspace nope not found" in result

    def test_update_success(self, db, session_factory):
        _make_workspace(db)
        result = pytest_asyncio_run(pm.manage_workspace(
            "Renamed", action="update", workspace_id="ws-1",
            description="d", is_startup=True, context={"tenant_id": "t-1"}))
        assert "updated successfully" in result
        db.expire_all()
        ws = db.query(Workspace).filter(Workspace.id == "ws-1").first()
        assert ws.name == "Renamed"
        assert ws.description == "d"
        assert ws.is_startup is True

    def test_unknown_action(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_workspace(
            "X", action="delete", context={"tenant_id": "t-1"}))
        assert "Unknown action" in result

    def test_exception(self, session_factory):
        boom = MagicMock()
        boom.commit.side_effect = RuntimeError("down")
        with patch("core.database.SessionLocal", return_value=boom):
            result = pytest_asyncio_run(pm.manage_workspace(
                "X", context={"tenant_id": "t-1"}))
        assert result == "Error managing workspace"


# ============================================================================
# manage_team
# ============================================================================

class TestManageTeam:
    def test_no_context(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_team("T"))
        assert "Could not resolve tenant/workspace" in result

    def test_create_with_members(self, db, session_factory):
        _make_workspace(db)
        _make_user(db)
        _make_user(db, user_id="u-2", email="two@atom.ai")
        result = pytest_asyncio_run(pm.manage_team(
            "Eng", add_members=["u-1", "two@atom.ai", "ghost@nowhere"],
            context={"workspace_id": "ws-1"}))
        assert "Team 'Eng' created successfully" in result
        assert "Added 2 members" in result
        team = db.query(Team).filter(Team.name == "Eng").first()
        assert team.workspace_id == "ws-1"

    def test_create_existing_member_skipped(self, db, session_factory):
        _make_workspace(db)
        _make_user(db)
        _make_user(db, user_id="u-2", email="two@atom.ai")
        result = pytest_asyncio_run(pm.manage_team(
            "Eng", add_members=["u-1", "u-2"], context={"workspace_id": "ws-1"}))
        team = db.query(Team).filter(Team.name == "Eng").first()
        second = pytest_asyncio_run(pm.manage_team(
            "Eng", action="update", team_id=team.id, add_members=["u-1"],
            context={"workspace_id": "ws-1"}))
        assert "Added 0 members" in second

    def test_update(self, db, session_factory):
        _make_workspace(db)
        team = Team(name="Old", workspace_id="ws-1")
        db.add(team)
        db.commit()
        result = pytest_asyncio_run(pm.manage_team(
            "New", action="update", team_id=team.id,
            context={"workspace_id": "ws-1"}))
        assert "updated successfully" in result
        db.expire_all()
        assert db.query(Team).filter(Team.id == team.id).first().name == "New"

    def test_update_requires_team_id(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_team(
            "T", action="update", context={"workspace_id": "ws-1"}))
        assert "team_id is required" in result

    def test_update_not_found(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_team(
            "T", action="update", team_id="nope",
            context={"workspace_id": "ws-1"}))
        assert "Team nope not found" in result

    def test_unknown_action(self, db, session_factory):
        result = pytest_asyncio_run(pm.manage_team(
            "T", action="delete", context={"workspace_id": "ws-1"}))
        assert "Unknown action" in result

    def test_exception(self, session_factory):
        boom = MagicMock()
        boom.commit.side_effect = RuntimeError("down")
        with patch("core.database.SessionLocal", return_value=boom):
            result = pytest_asyncio_run(pm.manage_team(
                "T", context={"workspace_id": "ws-1"}))
        assert result == "Error managing team"


# ============================================================================
# Tenant CRUD helpers
# ============================================================================

class TestTenantCrud:
    def test_create_tenant(self, db, session_factory):
        result = pytest_asyncio_run(pm.create_tenant("NewTenant"))
        assert "created successfully" in result
        assert db.query(Tenant).count() == 1

    def test_create_tenant_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.create_tenant("X"))
        assert result == "Error creating tenant"

    def test_update_tenant(self, db, session_factory):
        _make_tenant(db)
        result = pytest_asyncio_run(pm.update_tenant("t-1", name="Renamed"))
        assert "updated successfully" in result
        db.expire_all()
        assert db.query(Tenant).filter(Tenant.id == "t-1").first().name == "Renamed"

    def test_update_tenant_not_found(self, db, session_factory):
        result = pytest_asyncio_run(pm.update_tenant("nope", name="X"))
        assert "Tenant nope not found" in result

    def test_update_tenant_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.update_tenant("t-1", name="X"))
        assert result == "Error updating tenant"

    def test_delete_tenant(self, db, session_factory):
        _make_tenant(db)
        result = pytest_asyncio_run(pm.delete_tenant("t-1"))
        assert "deleted successfully" in result
        assert db.query(Tenant).count() == 0

    def test_delete_tenant_not_found(self, db, session_factory):
        result = pytest_asyncio_run(pm.delete_tenant("nope"))
        assert "Tenant nope not found" in result

    def test_delete_tenant_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.delete_tenant("t-1"))
        assert result == "Error deleting tenant"


# ============================================================================
# Workspace CRUD helpers
# ============================================================================

class TestWorkspaceCrud:
    def test_create_workspace(self, db, session_factory):
        result = pytest_asyncio_run(pm.create_workspace("Sales", "t-1"))
        assert "created successfully" in result

    def test_create_workspace_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.create_workspace("Sales", "t-1"))
        assert result == "Error creating workspace"

    def test_update_workspace(self, db, session_factory):
        _make_workspace(db)
        result = pytest_asyncio_run(pm.update_workspace("ws-1", name="New"))
        assert "updated successfully" in result
        db.expire_all()
        assert db.query(Workspace).filter(Workspace.id == "ws-1").first().name == "New"

    def test_update_workspace_not_found(self, db, session_factory):
        result = pytest_asyncio_run(pm.update_workspace("nope", name="X"))
        assert "Workspace nope not found" in result

    def test_update_workspace_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.update_workspace("ws-1", name="X"))
        assert result == "Error updating workspace"

    def test_delete_workspace(self, db, session_factory):
        _make_workspace(db)
        result = pytest_asyncio_run(pm.delete_workspace("ws-1"))
        assert "deleted successfully" in result

    def test_delete_workspace_not_found(self, db, session_factory):
        result = pytest_asyncio_run(pm.delete_workspace("nope"))
        assert "Workspace nope not found" in result

    def test_delete_workspace_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.delete_workspace("ws-1"))
        assert result == "Error deleting workspace"


# ============================================================================
# Team CRUD helpers + member strings
# ============================================================================

class TestTeamCrud:
    def test_create_team(self, db, session_factory):
        _make_workspace(db)
        result = pytest_asyncio_run(pm.create_team("Eng", "ws-1"))
        assert "created successfully" in result

    def test_create_team_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.create_team("Eng", "ws-1"))
        assert result == "Error creating team"

    def test_update_team(self, db, session_factory):
        _make_workspace(db)
        team = Team(name="Old", workspace_id="ws-1")
        db.add(team)
        db.commit()
        result = pytest_asyncio_run(pm.update_team(team.id, name="New"))
        assert "updated successfully" in result

    def test_update_team_not_found(self, db, session_factory):
        result = pytest_asyncio_run(pm.update_team("nope", name="X"))
        assert "Team nope not found" in result

    def test_update_team_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.update_team("t-1", name="X"))
        assert result == "Error updating team"

    def test_delete_team(self, db, session_factory):
        _make_workspace(db)
        team = Team(name="Old", workspace_id="ws-1")
        db.add(team)
        db.commit()
        result = pytest_asyncio_run(pm.delete_team(team.id))
        assert "deleted successfully" in result

    def test_delete_team_not_found(self, db, session_factory):
        result = pytest_asyncio_run(pm.delete_team("nope"))
        assert "Team nope not found" in result

    def test_delete_team_exception(self, session_factory):
        with patch("core.database.SessionLocal", side_effect=RuntimeError("down")):
            result = pytest_asyncio_run(pm.delete_team("t-1"))
        assert result == "Error deleting team"


class TestMemberStrings:
    def test_add_remove_members(self):
        assert pytest_asyncio_run(
            pm.add_member_to_workspace("u-1", "ws-1")) == "User u-1 added to workspace ws-1."
        assert pytest_asyncio_run(
            pm.remove_member_from_workspace("u-1", "ws-1")) == "User u-1 removed from workspace ws-1."
        assert pytest_asyncio_run(
            pm.add_member_to_team("u-1", "t-1")) == "User u-1 added to team t-1."
        assert pytest_asyncio_run(
            pm.remove_member_from_team("u-1", "t-1")) == "User u-1 removed from team t-1."
