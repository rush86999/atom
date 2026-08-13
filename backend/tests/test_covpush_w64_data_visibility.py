"""Coverage wave 64 — core/data_visibility.py (pure logic, mocked user/resource).

Covers the DataVisibility enum, VisibilityMixin column contract,
apply_visibility_filter condition construction (private/team/workspace),
get_visibility_for_user defaults, and can_access decisions for every
visibility level plus the no-visibility-control fallthroughs.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock
import operator

import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from core.data_visibility import (
    DataVisibility,
    VisibilityMixin,
    apply_visibility_filter,
    can_access,
    get_visibility_for_user,
)

TestBase = declarative_base()


class FakeModel(TestBase):
    __tablename__ = "w64_test_vis_model"
    id = Column(String, primary_key=True)
    visibility = Column(String, default=DataVisibility.WORKSPACE.value, nullable=False)
    owner_id = Column(String, nullable=True)
    team_id = Column(String, nullable=True)


class FakeModelNoVisibility(TestBase):
    __tablename__ = "w64_test_vis_model_plain"
    id = Column(String, primary_key=True)
    name = Column(String)


class MixinModel(TestBase, VisibilityMixin):
    __tablename__ = "w64_test_vis_mixin_model"
    id = Column(String, primary_key=True)


def make_user(**kw):
    defaults = dict(id="user-1", teams=[], workspaces=[])
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_team(tid):
    return SimpleNamespace(id=tid)


def make_resource(**kw):
    defaults = dict(visibility="workspace", owner_id=None, team_id=None)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class TestDataVisibilityEnum:
    def test_values(self):
        assert DataVisibility.PRIVATE.value == "private"
        assert DataVisibility.TEAM.value == "team"
        assert DataVisibility.WORKSPACE.value == "workspace"

    def test_enum_members(self):
        assert set(DataVisibility.__members__) == {"PRIVATE", "TEAM", "WORKSPACE"}


class TestVisibilityMixin:
    def test_columns_present(self):
        assert MixinModel.__table__ is not None
        cols = MixinModel.__table__.columns
        assert "visibility" in cols
        assert "owner_id" in cols
        assert "team_id" in cols
        assert cols["owner_id"].index is True
        assert cols["team_id"].index is True

    def test_visibility_default_is_workspace(self):
        assert MixinModel.visibility.default.arg == DataVisibility.WORKSPACE.value

    def test_owner_id_fk(self):
        fk = list(MixinModel.__table__.columns["owner_id"].foreign_keys)
        assert fk and fk[0].target_fullname == "users.id"

    def test_team_id_fk(self):
        fk = list(MixinModel.__table__.columns["team_id"].foreign_keys)
        assert fk and fk[0].target_fullname == "teams.id"


class TestApplyVisibilityFilter:
    def test_no_visibility_attr_returns_query_unchanged(self):
        query = MagicMock()
        result = apply_visibility_filter(query, make_user(), FakeModelNoVisibility)
        assert result == query
        query.filter.assert_not_called()

    def test_user_with_teams_and_workspaces(self):
        query = MagicMock()
        user = make_user(
            teams=[make_team("team-a"), make_team("team-b")],
            workspaces=[make_team("ws-1")],
        )
        apply_visibility_filter(query, user, FakeModel)
        clause = query.filter.call_args[0][0]
        assert len(clause.clauses) == 3
        private, workspace, team = clause.clauses
        assert private.operator.__name__ == "and_"
        private_vis, private_owner = private.clauses
        assert private_vis.left.name == "visibility"
        assert private_vis.right.value == DataVisibility.PRIVATE.value
        assert private_owner.left.name == "owner_id"
        assert private_owner.right.value == "user-1"
        assert workspace.operator is operator.eq
        assert workspace.left.name == "visibility"
        assert workspace.right.value == DataVisibility.WORKSPACE.value
        team_vis, team_ids = team.clauses
        assert team_vis.right.value == DataVisibility.TEAM.value
        assert team_ids.left.name == "team_id"
        assert team_ids.right.value == ["team-a", "team-b"]

    def test_user_without_teams(self):
        query = MagicMock()
        user = make_user(teams=[], workspaces=[])
        apply_visibility_filter(query, user, FakeModel)
        clause = query.filter.call_args[0][0]
        assert len(clause.clauses) == 2

    def test_user_without_teams_attr(self):
        query = MagicMock()
        user = make_user(teams=[])
        del user.teams
        apply_visibility_filter(query, user, FakeModel)
        clause = query.filter.call_args[0][0]
        assert len(clause.clauses) == 2

    def test_workspaces_not_required(self):
        query = MagicMock()
        user = make_user(teams=[make_team("team-a")])
        del user.workspaces
        apply_visibility_filter(query, user, FakeModel)
        clause = query.filter.call_args[0][0]
        assert len(clause.clauses) == 3


class TestGetVisibilityForUser:
    def test_with_teams_uses_first(self):
        user = make_user(teams=[make_team("team-a"), make_team("team-b")])
        result = get_visibility_for_user(user)
        assert result == {
            "owner_id": "user-1",
            "team_id": "team-a",
            "visibility": DataVisibility.WORKSPACE.value,
        }

    def test_without_teams(self):
        result = get_visibility_for_user(make_user(teams=[]))
        assert result["team_id"] is None

    def test_without_teams_attr(self):
        user = make_user()
        del user.teams
        result = get_visibility_for_user(user)
        assert result["team_id"] is None

    def test_explicit_visibility_override(self):
        user = make_user(teams=[make_team("team-a")])
        result = get_visibility_for_user(user, visibility=DataVisibility.TEAM.value)
        assert result["visibility"] == DataVisibility.TEAM.value


class TestCanAccess:
    def test_no_visibility_control_public(self):
        resource = SimpleNamespace(name="x")
        assert can_access(make_user(), resource) is True

    def test_private_owner(self):
        assert can_access(make_user(id="user-1"), make_resource(visibility="private", owner_id="user-1")) is True

    def test_private_not_owner(self):
        assert can_access(make_user(id="user-1"), make_resource(visibility="private", owner_id="user-2")) is False

    def test_team_no_teams_attr(self):
        user = make_user(teams=[make_team("team-a")])
        del user.teams
        assert can_access(user, make_resource(visibility="team", team_id="team-a")) is False

    def test_team_empty_teams(self):
        user = make_user(teams=[])
        assert can_access(user, make_resource(visibility="team", team_id="team-a")) is False

    def test_team_member(self):
        user = make_user(teams=[make_team("team-a"), make_team("team-b")])
        assert can_access(user, make_resource(visibility="team", team_id="team-b")) is True

    def test_team_non_member(self):
        user = make_user(teams=[make_team("team-a")])
        assert can_access(user, make_resource(visibility="team", team_id="team-b")) is False

    def test_workspace_default(self):
        assert can_access(make_user(), make_resource(visibility="workspace")) is True

    def test_unknown_visibility_denied(self):
        assert can_access(make_user(), make_resource(visibility="secret")) is False
