"""Round 79 — mini-app action contract regression tests.

Every registered ``mini_app_*`` action must:
- reject a missing actor with the auth error (never a 500),
- return a clean "not found" error for unknown app ids,
- enforce ownership on mutations.

DB strategy mirrors tests/test_mini_app_agent_tools.py: ``core.database`` is
pointed at a fresh temp-file DB so the handlers and the test share state.
"""
import asyncio
import uuid

import pytest

from core.action_registry import action_registry

ALL_ACTIONS = [
    "mini_app_scaffold",
    "mini_app_write_logic",
    "mini_app_dev_run",
    "mini_app_publish",
    "mini_app_install",
    "mini_app_run",
    "mini_app_list",
    "mini_app_get_state",
    "mini_app_set_tests",
    "mini_app_run_tests",
    "mini_app_logic_history",
    "mini_app_revert_logic",
    "mini_app_status",
]

ARG_SETS = {
    "mini_app_scaffold": {"name": "X"},
    "mini_app_write_logic": {"app_id": "a1", "source": "x = 1"},
    "mini_app_dev_run": {"app_id": "a1"},
    "mini_app_publish": {"app_id": "a1"},
    "mini_app_install": {"app_id": "a1"},
    "mini_app_run": {"canvas_id": "c1"},
    "mini_app_list": {},
    "mini_app_get_state": {"canvas_id": "c1"},
    "mini_app_set_tests": {"app_id": "a1", "tests": []},
    "mini_app_run_tests": {"app_id": "a1"},
    "mini_app_logic_history": {"app_id": "a1"},
    "mini_app_revert_logic": {"app_id": "a1", "version": 1},
    "mini_app_status": {"app_id": "a1"},
}

APP_ID_ACTIONS = [
    "mini_app_write_logic",
    "mini_app_dev_run",
    "mini_app_publish",
    "mini_app_install",
    "mini_app_set_tests",
    "mini_app_run_tests",
    "mini_app_logic_history",
    "mini_app_revert_logic",
    "mini_app_status",
]

OWNER_MUTATIONS = [
    "mini_app_write_logic",
    "mini_app_dev_run",
    "mini_app_publish",
    "mini_app_set_tests",
    "mini_app_run_tests",
    "mini_app_logic_history",
    "mini_app_revert_logic",
    "mini_app_status",
]


def _run_sync(action: str, args: dict, context: dict) -> dict:
    return asyncio.run(action_registry.execute_action(action, args, context))


@pytest.fixture
def patched_db(test_database, monkeypatch):
    """Bind core.database to a fresh temp-file DB (mirrors the existing
    mini-app suite's fixture)."""
    from sqlalchemy.orm import sessionmaker

    engine, _ = test_database
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )
    monkeypatch.setattr("core.database.SessionLocal", SessionLocal)
    monkeypatch.setattr("core.database.engine", engine)
    return engine, SessionLocal


@pytest.fixture
def owned_app_id(patched_db):
    """A mini-app scaffolded by u-owner in the patched DB."""
    result = _run_sync(
        "mini_app_scaffold",
        {"name": f"Counter-{uuid.uuid4().hex[:6]}"},
        {"user_id": "u-owner"},
    )
    assert result["success"] is True, result
    return result["app_id"]


class TestMissingUserContract:
    """No actor in the dispatch context -> the auth error, for every action."""

    @pytest.mark.parametrize("action_name", ALL_ACTIONS)
    def test_missing_user_returns_auth_error(self, action_name):
        result = _run_sync(action_name, ARG_SETS[action_name], {})
        assert result == {"success": False, "error": "Authenticated user is required"}

    @pytest.mark.parametrize("action_name", ALL_ACTIONS)
    def test_context_without_any_user_key_returns_auth_error(self, action_name):
        result = _run_sync(action_name, ARG_SETS[action_name], {"db": object()})
        assert result == {"success": False, "error": "Authenticated user is required"}


class TestUnknownAppId:
    """Unknown app_id -> a clean not-found error, never a 500."""

    @pytest.mark.parametrize("action_name", APP_ID_ACTIONS)
    def test_unknown_app_id_returns_not_found(self, patched_db, action_name):
        args = dict(ARG_SETS[action_name])
        args["app_id"] = "no-such-app"
        result = _run_sync(action_name, args, {"user_id": "u-owner"})
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_unknown_canvas_id_returns_not_found(self, patched_db):
        result = _run_sync(
            "mini_app_get_state", {"canvas_id": "no-such-canvas"}, {"user_id": "u-1"}
        )
        assert result["success"] is False
        assert "not found" in result["error"]


class TestOwnerEnforcement:
    """Mutations by a non-owner -> 'Not the app owner'."""

    @pytest.mark.parametrize("action_name", OWNER_MUTATIONS)
    def test_non_owner_rejected(self, patched_db, owned_app_id, action_name):
        args = dict(ARG_SETS[action_name])
        args["app_id"] = owned_app_id
        if action_name == "mini_app_write_logic":
            args["source"] = "n = 0"
        if action_name == "mini_app_set_tests":
            args["tests"] = [{"name": "t", "expect_state": {"n": 1}}]
        if action_name == "mini_app_revert_logic":
            args["version"] = 1
        result = _run_sync(action_name, args, {"user_id": "u-other"})
        assert result["success"] is False
        assert result["error"] == "Not the app owner"

    def test_owner_mutation_succeeds(self, patched_db, owned_app_id):
        result = _run_sync(
            "mini_app_write_logic",
            {"app_id": owned_app_id, "source": "n = 42"},
            {"user_id": "u-owner"},
        )
        assert result["success"] is True

    def test_install_does_not_require_ownership(self, patched_db, owned_app_id):
        """Install is a read/use action — anyone may install a published app."""
        result = _run_sync(
            "mini_app_install", {"app_id": owned_app_id}, {"user_id": "u-other"}
        )
        # Either success (published) or a clean domain error — never a 500 or
        # an owner denial.
        assert result["success"] in (True, False)
        assert "owner" not in result.get("error", "").lower()


class TestActionRegistryWiring:
    def test_all_mini_app_actions_registered(self):
        names = set(action_registry.list_actions())
        for action in ALL_ACTIONS:
            assert action in names, f"{action} missing from registry"
