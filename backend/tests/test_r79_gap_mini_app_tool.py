# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: tools/mini_app_tool.py (agent-facing mini-app
authoring harness, 15 mini_app_* actions; zero test references before this
file).

The tools open their own ``get_db_session()`` (imported lazily from
core.database) and call mini_app_service helpers lazily — both are patched
with fakes, mirroring tests/test_mini_apps.py. Auth/missing-arg error paths
need no DB at all.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.models import Canvas, CanvasState, MiniApp, User
from tools import mini_app_tool as mat


def _viewer_context(user_id="user-1"):
    return {"user_id": user_id, "agent_id": "agent-1"}


class FakeQuery:
    """One-model query stub: first()/all() return the configured value."""

    def __init__(self, model, first_value=None, all_value=None):
        self.model = model
        self._first = first_value
        self._all = all_value

    def filter(self, *a, **k):
        return self

    def order_by(self, *a):
        return self

    def limit(self, n):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._all if self._all is not None else []


class FakeSession:
    """Mimics a SQLAlchemy session for the few query shapes the tools use."""

    def __init__(self, rows):
        self.rows = rows  # {model: value_for_first}
        self.all_rows = {}  # {model: list_for_all}

    def query(self, model):
        return FakeQuery(
            model,
            first_value=self.rows.get(model),
            all_value=self.all_rows.get(model),
        )

    def commit(self):
        pass


def _make_app(**overrides):
    defaults = dict(
        id="app-1",
        tenant_id="t1",
        created_by="user-1",
        name="my-app",
        version="1.0.0",
        status="draft",
        is_public=False,
        blueprint_canvas_id="canvas-1",
        manifest={"name": "my-app", "version": "1.0.0"},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_canvas(**overrides):
    defaults = dict(id="canvas-1", created_by="user-1", mini_app_id="app-1", tenant_id="t1")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture()
def db_cm():
    """Context manager returning a FakeSession."""

    def make(*rows_by_model):
        pairs = list(zip(rows_by_model[::2], rows_by_model[1::2]))
        cm = MagicMock()
        cm.__enter__.return_value = FakeSession(dict(pairs))
        return cm

    return make


@pytest.fixture()
def patched_db(db_cm):
    def apply(*rows_by_model):
        return patch("core.database.get_db_session", return_value=db_cm(*rows_by_model))

    return apply


class TestAuthAndValidation:
    async def test_all_actions_require_authenticated_user(self):
        for fn in (
            mat.mini_app_scaffold, mat.mini_app_write_logic, mat.mini_app_dev_run,
            mat.mini_app_publish, mat.mini_app_install, mat.mini_app_run,
            mat.mini_app_list, mat.mini_app_get_state, mat.mini_app_set_tests,
            mat.mini_app_run_tests, mat.mini_app_logic_history,
            mat.mini_app_revert_logic, mat.mini_app_status,
        ):
            result = await fn({}, {})
            assert result == {"success": False, "error": "Authenticated user is required"}, fn.__name__

    async def test_scaffold_requires_name(self):
        result = await mat.mini_app_scaffold({}, _viewer_context())
        assert result["success"] is False
        assert "name" in result["error"]

    async def test_write_logic_requires_app_id(self):
        result = await mat.mini_app_write_logic({"source": "x"}, _viewer_context())
        assert result["success"] is False
        assert "app_id" in result["error"]

    async def test_dev_run_requires_app_id(self):
        result = await mat.mini_app_dev_run({}, _viewer_context())
        assert result["success"] is False

    async def test_run_requires_canvas_id(self):
        result = await mat.mini_app_run({}, _viewer_context())
        assert result["success"] is False
        assert "canvas_id" in result["error"]

    async def test_set_tests_requires_list(self):
        result = await mat.mini_app_set_tests(
            {"app_id": "a", "tests": "not-a-list"}, _viewer_context()
        )
        assert result["success"] is False
        assert "list" in result["error"]

    async def test_revert_requires_version(self):
        result = await mat.mini_app_revert_logic({"app_id": "a"}, _viewer_context())
        assert result["success"] is False
        assert "version" in result["error"]

    async def test_status_requires_app_id(self):
        result = await mat.mini_app_status({}, _viewer_context())
        assert result["success"] is False


class TestScaffold:
    async def test_scaffold_success(self, patched_db):
        app = _make_app()
        with patched_db(MiniApp, app):
            with patch("core.canvas_logic_service.CanvasLogicService") as svc:
                svc.return_value.load_logic.return_value = {"source": "def run(): pass"}
                from core.mini_app_service import scaffold as real_scaffold
                from core.database import get_db_session as real_gds
                with patch("core.mini_app_service.scaffold", return_value=(app, "canvas-1")):
                    result = await mat.mini_app_scaffold(
                        {"name": "my-app", "spec": {}, "declared_scopes": ["canvas.read"]},
                        _viewer_context(),
                    )
        assert result["success"] is True
        assert result["app_id"] == "app-1"
        assert result["canvas_id"] == "canvas-1"

    async def test_scaffold_failure_is_generic(self, patched_db):
        with patched_db(MiniApp, None):
            with patch("core.mini_app_service.scaffold", side_effect=RuntimeError("boom")):
                result = await mat.mini_app_scaffold(
                    {"name": "x", "spec": {}}, _viewer_context()
                )
        assert result["success"] is False
        assert "scaffold" in result["error"]
        assert "boom" not in result["error"]


class TestWriteLogic:
    async def test_missing_app(self, patched_db):
        with patched_db(MiniApp, None):
            result = await mat.mini_app_write_logic(
                {"app_id": "nope", "source": "x = 1\n"}, _viewer_context()
            )
        assert result["success"] is False
        assert "not found" in result["error"]

    async def test_non_owner_rejected(self, patched_db):
        with patched_db(MiniApp, _make_app(created_by="someone-else")):
            result = await mat.mini_app_write_logic(
                {"app_id": "app-1", "source": "x = 1\n"}, _viewer_context()
            )
        assert result["success"] is False
        assert "owner" in result["error"]

    async def test_syntax_error_rejected(self, patched_db):
        with patched_db(MiniApp, _make_app()):
            result = await mat.mini_app_write_logic(
                {"app_id": "app-1", "source": "def broken(:\n"}, _viewer_context()
            )
        assert result["success"] is False
        assert "SyntaxError" in result["error"]

    async def test_success_saves_and_checkpoints(self, patched_db):
        app = _make_app()
        with patched_db(MiniApp, app):
            with patch("core.canvas_logic_service.CanvasLogicService") as svc:
                with patch("core.mini_app_service.record_logic_snapshot",
                           return_value={"version": 3}):
                    result = await mat.mini_app_write_logic(
                        {"app_id": "app-1", "source": "x = 1\n"}, _viewer_context()
                    )
        assert result["success"] is True
        assert result["version"] == 3
        svc.return_value.save_logic.assert_called_once()


class TestDevRunAndRun:
    async def test_dev_run_success(self, patched_db):
        app = _make_app()
        with patched_db(MiniApp, app):
            with patch("core.mini_app_service.prepare_runtime") as prepare:
                with patch(
                    "core.mini_app_service.run_stateful",
                    new=AsyncMock(return_value={"success": True, "state": {"n": 1}}),
                ) as run:
                    result = await mat.mini_app_dev_run({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is True
        assert result["state"] == {"n": 1}
        prepare.assert_called_once()
        run.assert_awaited_once()

    async def test_dev_run_runtime_error_surfaced(self, patched_db):
        with patched_db(MiniApp, _make_app()):
            with patch("core.mini_app_service.prepare_runtime", side_effect=RuntimeError("rootfs missing")):
                result = await mat.mini_app_dev_run({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is False
        assert "rootfs missing" in result["error"]

    async def test_dev_run_failed_state(self, patched_db):
        with patched_db(MiniApp, _make_app()):
            with patch("core.mini_app_service.prepare_runtime"):
                with patch(
                    "core.mini_app_service.run_stateful",
                    new=AsyncMock(return_value={"success": False, "error": "vm boot failed"}),
                ):
                    result = await mat.mini_app_dev_run({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is False
        assert "vm boot failed" in result["error"]

    async def test_run_stateful_persists(self):
        with patch(
            "core.mini_app_service.run_stateful",
            new=AsyncMock(return_value={"success": True, "state": {"n": 2}}),
        ) as run:
            result = await mat.mini_app_run(
                {"canvas_id": "canvas-1", "inputs": {"n": 2}}, _viewer_context()
            )
        assert result["success"] is True
        run.assert_awaited_once()
        kwargs = run.await_args.kwargs
        assert kwargs["persist"] is True
        assert kwargs["user_id"] == "user-1"


class TestPublishInstall:
    async def test_publish_success(self, patched_db):
        app = _make_app()
        with patched_db(MiniApp, app):
            with patch("core.mini_app_service.publish", return_value={"version": "1.0.0"}):
                result = await mat.mini_app_publish({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is True
        assert result["version"] == "1.0.0"

    async def test_publish_value_error_surfaced(self, patched_db):
        with patched_db(MiniApp, _make_app()):
            with patch("core.mini_app_service.publish", side_effect=ValueError("no blueprint")):
                result = await mat.mini_app_publish({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is False
        assert "no blueprint" in result["error"]

    async def test_install_success(self, patched_db):
        app = _make_app()
        with patched_db(MiniApp, app):
            with patch("core.mini_app_service.install", return_value="canvas-9"):
                result = await mat.mini_app_install({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is True
        assert result["canvas_id"] == "canvas-9"

    async def test_install_not_published(self, patched_db):
        with patched_db(MiniApp, _make_app(status="draft")):
            with patch("core.mini_app_service.install", side_effect=ValueError("not published")):
                result = await mat.mini_app_install({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is False


class TestListAndState:
    async def test_list_returns_owned_apps(self, patched_db):
        app = _make_app(id="a1")
        with patched_db(MiniApp, app):
            with patch("core.database.get_db_session") as gds:
                cm = MagicMock()
                session = FakeSession({MiniApp: app})
                session.all_rows[MiniApp] = [app]
                cm.__enter__.return_value = session
                gds.return_value = cm
                result = await mat.mini_app_list({}, _viewer_context())
        assert result["success"] is True
        assert result["apps"][0]["id"] == "a1"

    async def test_list_without_auth(self):
        result = await mat.mini_app_list({}, {})
        assert result["success"] is False

    async def test_get_state_success(self, patched_db):
        canvas = _make_canvas()
        state_row = SimpleNamespace(state={"n": 5}, version=2)
        with patched_db(Canvas, canvas, CanvasState, state_row):
            result = await mat.mini_app_get_state({"canvas_id": "canvas-1"}, _viewer_context())
        assert result["success"] is True
        assert result["state"] == {"n": 5}
        assert result["version"] == 2

    async def test_get_state_not_instance(self, patched_db):
        with patched_db(Canvas, _make_canvas(mini_app_id=None)):
            result = await mat.mini_app_get_state({"canvas_id": "canvas-1"}, _viewer_context())
        assert result["success"] is False
        assert "not a mini-app instance" in result["error"]

    async def test_get_state_missing_canvas(self, patched_db):
        with patched_db(Canvas, None):
            result = await mat.mini_app_get_state({"canvas_id": "canvas-1"}, _viewer_context())
        assert result["success"] is False
        assert "not found" in result["error"]

    async def test_get_state_no_state_rows(self, patched_db):
        with patched_db(Canvas, _make_canvas(), CanvasState, None):
            result = await mat.mini_app_get_state({"canvas_id": "canvas-1"}, _viewer_context())
        assert result["success"] is True
        assert result["state"] == {}
        assert result["version"] == 0


class TestTestsHistoryRevertStatus:
    async def test_set_tests_success(self, patched_db):
        app = _make_app(manifest={"name": "my-app", "version": "1.0.0"})
        with patched_db(MiniApp, app):
            with patch("core.mini_app_service.validate_tests", return_value=None):
                result = await mat.mini_app_set_tests(
                    {"app_id": "app-1", "tests": [{"given": {}, "expected": {}}]},
                    _viewer_context(),
                )
        assert result["success"] is True
        assert result["tests"] == 1

    async def test_set_tests_invalid(self, patched_db):
        with patched_db(MiniApp, _make_app()):
            with patch("core.mini_app_service.validate_tests", side_effect=ValueError("bad test")):
                result = await mat.mini_app_set_tests(
                    {"app_id": "app-1", "tests": [{"bad": 1}]}, _viewer_context()
                )
        assert result["success"] is False
        assert "bad test" in result["error"]

    async def test_run_tests_no_tests_saved(self, patched_db):
        with patched_db(MiniApp, _make_app(manifest={"name": "my-app"})):
            result = await mat.mini_app_run_tests({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is True
        assert result["total"] == 0

    async def test_run_tests_report(self, patched_db):
        app = _make_app(manifest={"name": "my-app", "tests": [{"given": {}}]})
        with patched_db(MiniApp, app):
            with patch(
                "core.mini_app_service.run_tests",
                new=AsyncMock(return_value={"passed": 1, "total": 1, "results": [{"ok": True}]}),
            ):
                result = await mat.mini_app_run_tests({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is True
        assert result["all_passed"] is True

    async def test_logic_history_success(self, patched_db):
        with patched_db(MiniApp, _make_app()):
            with patch("core.mini_app_service.list_logic_history", return_value=[{"version": 1}]):
                result = await mat.mini_app_logic_history({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is True
        assert result["history"] == [{"version": 1}]

    async def test_revert_logic_success(self, patched_db):
        with patched_db(MiniApp, _make_app()):
            with patch("core.mini_app_service.revert_logic", return_value={"version": 1}):
                result = await mat.mini_app_revert_logic(
                    {"app_id": "app-1", "version": 1}, _viewer_context()
                )
        assert result["success"] is True
        assert result["version"] == 1

    async def test_revert_logic_value_error(self, patched_db):
        with patched_db(MiniApp, _make_app()):
            with patch("core.mini_app_service.revert_logic", side_effect=ValueError("no checkpoint 5")):
                result = await mat.mini_app_revert_logic(
                    {"app_id": "app-1", "version": 5}, _viewer_context()
                )
        assert result["success"] is False

    async def test_status_probe(self, patched_db):
        with patched_db(MiniApp, _make_app()):
            with patch("core.mini_app_service.status_probe", return_value={"stage": "authoring"}):
                result = await mat.mini_app_status({"app_id": "app-1"}, _viewer_context())
        assert result["success"] is True
        assert result["status"] == {"stage": "authoring"}
