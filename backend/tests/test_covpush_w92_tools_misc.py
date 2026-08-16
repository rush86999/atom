# -*- coding: utf-8 -*-
"""Coverage wave 92 — mini_app_tool, media_tool, database_manager,
webhook_metrics, debug_ai_assistant, agent_social_layer.

No network, no LLM, no real DB: every external boundary (sessions, services,
event bus, redis, spotify/sonos) is mocked. Plain pytest + unittest.mock.
"""
import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

import tools.mini_app_tool as mini_app_tool
import tools.media_tool as media_tool
import core.database_manager as dbm
import core.webhook_metrics as wm
import core.debug_ai_assistant as dai
import core.agent_social_layer as asl


# =========================================================================== #
# helpers
# =========================================================================== #
def _ctx_manager(value):
    @contextmanager
    def _cm(*a, **k):
        yield value
    return _cm


class FakeQuery:
    def __init__(self, first=None, all_=None, count=0, scalar=0):
        self._first = first
        self._all = list(all_ or [])
        self._count = count
        self._scalar = scalar

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def offset(self, *a, **k):
        return self

    def distinct(self, *a, **k):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._all

    def count(self):
        return self._count

    def scalar(self):
        return self._scalar


class FakeDB:
    """Routes db.query(Model) to per-model-name results."""

    def __init__(self, routes=None, queue=None):
        # routes: {ModelName: dict(first=..., all=[...], count=n, scalar=n)}
        self.routes = routes or {}
        # queue: FIFO list of FakeQuery results (overrides routing)
        self.queue = list(queue or [])
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, model, *a, **k):
        if self.queue:
            return self.queue.pop(0)
        name = getattr(model, "__name__", str(model))
        cfg = self.routes.get(name, {})
        return FakeQuery(first=cfg.get("first"), all_=cfg.get("all"),
                         count=cfg.get("count", 0), scalar=cfg.get("scalar", 0))

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        pass

    def close(self):
        pass


class _Col:
    """Column stub supporting the comparison/boolean operators used in filters."""

    def __lt__(self, other):
        return self

    def __le__(self, other):
        return self

    def __gt__(self, other):
        return self

    def __ge__(self, other):
        return self

    def __eq__(self, other):
        return self

    def __ne__(self, other):
        return self

    def __and__(self, other):
        return self

    def __or__(self, other):
        return self

    def __invert__(self):
        return self

    def is_(self, other):
        return self

    def is_not(self, other):
        return self

    def in_(self, other):
        return self

    def like(self, other):
        return self

    def desc(self):
        return self

    def asc(self):
        return self

    def isoformat(self):
        return "2026-01-01T00:00:00+00:00"

    def get(self, key, default=None):
        return default

    value = "enum-value"


class _ModelMeta(type):
    def __getattr__(cls, name):
        return _Col()


class _Inst:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        return _Col()


def _C(name):
    """A fake model class with a distinguishable __name__ and column attrs."""
    return _ModelMeta(name, (_Inst,), {})


def _viewer_patch(user_id="u1", tier=None):
    viewer = SimpleNamespace(id=user_id, tenant_id="t", workspace_id="w", tier=tier)
    return patch.object(mini_app_tool, "_viewer", return_value=viewer)


MiniAppC = _C("MiniApp")
CanvasC = _C("Canvas")
CanvasStateC = _C("CanvasState")
UserC = _C("User")
AgentRegistryC = _C("AgentRegistry")
SocialPostC = _C("SocialPost")
ChannelC = _C("Channel")
AgentFeedbackC = _C("AgentFeedback")
EpisodeC = _C("Episode")


# =========================================================================== #
# 1. tools/mini_app_tool.py
# =========================================================================== #
class TestMiniAppTool:
    async def test_context_user_id_variants(self):
        assert mini_app_tool._context_user_id(None) is None
        assert mini_app_tool._context_user_id({}) is None
        assert mini_app_tool._context_user_id({"user_id": "a"}) == "a"
        assert mini_app_tool._context_user_id({"userId": "b"}) == "b"
        assert mini_app_tool._context_user_id({"actor_id": 5}) == "5"
        user = SimpleNamespace(id="obj1")
        assert mini_app_tool._context_user_id({"user": user}) == "obj1"
        assert mini_app_tool._context_user_id({"user": "nope"}) is None

    async def test_viewer_no_user(self):
        v = mini_app_tool._viewer({})
        assert v.id is None and v.tenant_id is None

    async def test_viewer_with_row_and_failure(self):
        db = FakeDB(queue=[FakeQuery(first=SimpleNamespace(tenant_id="tn", workspace_id="ws", tier="INTERN"))])
        with patch("core.database.get_db_session", _ctx_manager(db)), patch("core.models.User", UserC):
            v = mini_app_tool._viewer({"user_id": "u1"})
            assert v.id == "u1" and v.tenant_id == "tn" and v.tier == "INTERN"
        # row missing → fallback
        db2 = FakeDB(queue=[FakeQuery(first=None)])
        with patch("core.database.get_db_session", _ctx_manager(db2)), patch("core.models.User", UserC):
            v = mini_app_tool._viewer({"user_id": "u1"})
            assert v.id == "u1" and v.tenant_id is None
        # exception path
        with patch("core.database.get_db_session", side_effect=RuntimeError("x")):
            v = mini_app_tool._viewer({"user_id": "u1"})
            assert v.id == "u1"

    async def test_scaffold_branches(self):
        args = {"name": "app", "spec": {"base_image": ""}, "declared_scopes": ["s"], "dependencies": []}
        with _viewer_patch(user_id=None):
            r = await mini_app_tool.mini_app_scaffold(args, {"user_id": "x"})
            assert "Authenticated" in r["error"]
        with _viewer_patch():
            r = await mini_app_tool.mini_app_scaffold({}, {"user_id": "u"})
            assert r["error"] == "name is required"

        app = SimpleNamespace(id="a1", name="app")
        db = FakeDB(queue=[
            FakeQuery(first=SimpleNamespace(manifest={"m": 1})),  # fresh re-query
        ])
        cls = MagicMock()
        cls.return_value.load_logic.return_value = {"source": "print(1)"}
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.mini_app_service.scaffold", return_value=(app, "c1")), \
             patch("core.canvas_logic_service.CanvasLogicService", cls), \
             patch("core.models.MiniApp", MiniAppC):
            r = await mini_app_tool.mini_app_scaffold(args, {"user_id": "u"})
            assert r["success"] is True and r["canvas_id"] == "c1" and r["logic_source"] == "print(1)"
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=RuntimeError("x")):
            r = await mini_app_tool.mini_app_scaffold(args, {"user_id": "u"})
            assert r["success"] is False and "scaffold failed" in r["error"]

    def _owned_app(self):
        return SimpleNamespace(id="a1", created_by="u1", tenant_id="t",
                               blueprint_canvas_id="c1", manifest={}, name="n", version=3,
                               status="draft", is_public=False, is_approved=False)

    async def test_write_logic_branches(self):
        with _viewer_patch(user_id=None):
            r = await mini_app_tool.mini_app_write_logic({}, {})
            assert "Authenticated" in r["error"]
        with _viewer_patch():
            r = await mini_app_tool.mini_app_write_logic({}, {"user_id": "u"})
            assert r["error"] == "app_id is required"

        cases = [
            (None, "not found"),
            (SimpleNamespace(id="a1", created_by="other", blueprint_canvas_id="c"), "Not the app owner"),
            (SimpleNamespace(id="a1", created_by="u1", blueprint_canvas_id=None), "no blueprint canvas"),
        ]
        for row, want in cases:
            db = FakeDB(routes={"MiniApp": {"first": row}})
            with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
                 patch("core.models.MiniApp", MiniAppC):
                r = await mini_app_tool.mini_app_write_logic({"app_id": "a1", "source": "x=1"}, {"user_id": "u"})
                assert want.lower() in r["error"].lower(), r

        app = self._owned_app()
        db = FakeDB(routes={"MiniApp": {"first": app}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.syntax_check", side_effect=SyntaxError("bad")):
            r = await mini_app_tool.mini_app_write_logic({"app_id": "a1", "source": "x="}, {"user_id": "u"})
            assert "SyntaxError" in r["error"]
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.syntax_check", MagicMock()), \
             patch("core.mini_app_service.record_logic_snapshot", return_value={"version": 2}), \
             patch("core.canvas_logic_service.CanvasLogicService", MagicMock()):
            r = await mini_app_tool.mini_app_write_logic({"app_id": "a1", "source": "x=1"}, {"user_id": "u"})
            assert r["success"] is True and r["version"] == 2
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=RuntimeError("x")):
            r = await mini_app_tool.mini_app_write_logic({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is False

    async def test_dev_run_branches(self):
        with _viewer_patch(user_id=None):
            assert "Authenticated" in (await mini_app_tool.mini_app_dev_run({}, {}))["error"]
        with _viewer_patch():
            assert (await mini_app_tool.mini_app_dev_run({}, {"user_id": "u"}))["error"] == "app_id is required"

        app = self._owned_app()
        db = FakeDB(routes={"MiniApp": {"first": app}})
        rs = AsyncMock(return_value={"success": True, "state": {"a": 1}, "version": 2,
                                     "state_changed": True, "stdout": "o", "exit_code": 0})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.prepare_runtime", MagicMock()), \
             patch("core.mini_app_service.run_stateful", rs):
            r = await mini_app_tool.mini_app_dev_run({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is True and r["state"] == {"a": 1}
        rs2 = AsyncMock(return_value={"success": False, "error": "runtime boom"})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.prepare_runtime", MagicMock()), \
             patch("core.mini_app_service.run_stateful", rs2):
            r = await mini_app_tool.mini_app_dev_run({"app_id": "a1"}, {"user_id": "u"})
            assert r["error"] == "runtime boom"
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.prepare_runtime", side_effect=RuntimeError("deps unsafe")), \
             patch("core.mini_app_service.run_stateful", AsyncMock()):
            r = await mini_app_tool.mini_app_dev_run({"app_id": "a1"}, {"user_id": "u"})
            assert r["error"] == "deps unsafe"
        for row, want in [(None, "not found"),
                          (SimpleNamespace(id="a", created_by="o", blueprint_canvas_id="c"), "owner"),
                          (SimpleNamespace(id="a", created_by="u1", blueprint_canvas_id=None), "canvas")]:
            d = FakeDB(routes={"MiniApp": {"first": row}})
            with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(d)), \
                 patch("core.models.MiniApp", MiniAppC):
                r = await mini_app_tool.mini_app_dev_run({"app_id": "a1"}, {"user_id": "u"})
                assert want.lower() in r["error"].lower()
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=ValueError("x")):
            r = await mini_app_tool.mini_app_dev_run({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is False

    async def test_publish_branches(self):
        app = self._owned_app()
        db = FakeDB(routes={"MiniApp": {"first": app}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.publish", return_value={"version": 4}):
            r = await mini_app_tool.mini_app_publish({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is True and r["version"] == 4
        with _viewer_patch(), patch("core.database.get_db_session",
                                    _ctx_manager(FakeDB(routes={"MiniApp": {"first": None}}))), \
             patch("core.models.MiniApp", MiniAppC):
            r = await mini_app_tool.mini_app_publish({"app_id": "a1"}, {"user_id": "u"})
            assert "not found" in r["error"]
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.publish", side_effect=RuntimeError("rootfs missing")):
            r = await mini_app_tool.mini_app_publish({"app_id": "a1"}, {"user_id": "u"})
            assert "rootfs" in r["error"]
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.publish", side_effect=ValueError("no logic")):
            r = await mini_app_tool.mini_app_publish({"app_id": "a1"}, {"user_id": "u"})
            assert "no logic" in r["error"]
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=Exception("x")):
            r = await mini_app_tool.mini_app_publish({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is False

    async def test_install_branches(self):
        app = self._owned_app()
        db = FakeDB(routes={"MiniApp": {"first": app}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.install", return_value="c9"):
            r = await mini_app_tool.mini_app_install({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is True and r["canvas_id"] == "c9"
        app_pub = SimpleNamespace(id="a1", created_by="other", is_public=True, is_approved=False, name="n")
        db2 = FakeDB(routes={"MiniApp": {"first": app_pub}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db2)), \
             patch("core.models.MiniApp", MiniAppC):
            r = await mini_app_tool.mini_app_install({"app_id": "a1"}, {"user_id": "u"})
            assert "pending review" in r["error"]
        app_priv = SimpleNamespace(id="a1", created_by="other", is_public=False, is_approved=False)
        db3 = FakeDB(routes={"MiniApp": {"first": app_priv}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db3)), \
             patch("core.models.MiniApp", MiniAppC):
            r = await mini_app_tool.mini_app_install({"app_id": "a1"}, {"user_id": "u"})
            assert "Not authorized" in r["error"]
        app_ok = SimpleNamespace(id="a1", created_by="other", is_public=True, is_approved=True, name="n")
        db4 = FakeDB(routes={"MiniApp": {"first": app_ok}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db4)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.install", return_value="c8"):
            r = await mini_app_tool.mini_app_install({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is True
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.install", side_effect=ValueError("nope")):
            r = await mini_app_tool.mini_app_install({"app_id": "a1"}, {"user_id": "u"})
            assert r["error"] == "nope"
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=Exception("x")):
            r = await mini_app_tool.mini_app_install({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is False

    async def test_run_and_list_and_state(self):
        rs = AsyncMock(return_value={"success": True})
        with _viewer_patch(), patch("core.mini_app_service.run_stateful", rs):
            r = await mini_app_tool.mini_app_run({"canvas_id": "c1", "inputs": {"a": 1}},
                                                 {"user_id": "u", "agent_id": "g"})
            assert r == {"success": True}
            assert rs.await_args.kwargs["persist"] is True

        rows = [SimpleNamespace(id="a1", name="n", version=1, status="draft", is_public=False, blueprint_canvas_id="c")]
        db = FakeDB(routes={"MiniApp": {"all": rows}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC):
            r = await mini_app_tool.mini_app_list({}, {"user_id": "u"})
            assert r["success"] is True and len(r["apps"]) == 1
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=Exception("x")):
            r = await mini_app_tool.mini_app_list({}, {"user_id": "u"})
            assert r["success"] is False and r["apps"] == []

        canvas = SimpleNamespace(id="c1", mini_app_id="a1")
        state = SimpleNamespace(state={"x": 1}, version=3)
        db2 = FakeDB(routes={"Canvas": {"first": canvas}, "CanvasState": {"first": state}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db2)), \
             patch("core.models.Canvas", CanvasC), patch("core.models.CanvasState", CanvasStateC):
            r = await mini_app_tool.mini_app_get_state({"canvas_id": "c1"}, {"user_id": "u"})
            assert r["success"] is True and r["version"] == 3
        nc = SimpleNamespace(id="c1", mini_app_id=None)
        db3 = FakeDB(routes={"Canvas": {"first": nc}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db3)), \
             patch("core.models.Canvas", CanvasC), patch("core.models.CanvasState", CanvasStateC):
            r = await mini_app_tool.mini_app_get_state({"canvas_id": "c1"}, {"user_id": "u"})
            assert "not a mini-app" in r["error"]
        db4 = FakeDB(routes={"Canvas": {"first": None}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db4)), \
             patch("core.models.Canvas", CanvasC), patch("core.models.CanvasState", CanvasStateC):
            r = await mini_app_tool.mini_app_get_state({"canvas_id": "c1"}, {"user_id": "u"})
            assert "not found" in r["error"]
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=Exception("x")), \
             patch("core.models.Canvas", CanvasC), patch("core.models.CanvasState", CanvasStateC):
            r = await mini_app_tool.mini_app_get_state({"canvas_id": "c1"}, {"user_id": "u"})
            assert r["success"] is False

    async def test_set_tests_and_run_tests(self):
        app = self._owned_app()
        db = FakeDB(routes={"MiniApp": {"first": app}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.validate_tests", MagicMock()):
            app.manifest = {}
            r = await mini_app_tool.mini_app_set_tests({"app_id": "a1", "tests": [{"t": 1}]}, {"user_id": "u"})
            assert r["success"] is True and r["tests"] == 1
        with _viewer_patch(), patch("core.mini_app_service.validate_tests",
                                    side_effect=ValueError("bad tests")):
            r = await mini_app_tool.mini_app_set_tests({"app_id": "a1", "tests": []}, {"user_id": "u"})
            assert r["error"] == "bad tests"
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=Exception("x")):
            r = await mini_app_tool.mini_app_set_tests({"app_id": "a1", "tests": []}, {"user_id": "u"})
            assert r["success"] is False

        db2 = FakeDB(routes={"MiniApp": {"first": self._owned_app()}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db2)), \
             patch("core.models.MiniApp", MiniAppC):
            r = await mini_app_tool.mini_app_run_tests({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is True and r["total"] == 0
        app2 = self._owned_app()
        app2.manifest = {"tests": [{"a": 1}]}
        db3 = FakeDB(routes={"MiniApp": {"first": app2}})
        rt = AsyncMock(return_value={"passed": 0, "total": 1, "results": []})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db3)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.run_tests", rt):
            r = await mini_app_tool.mini_app_run_tests({"app_id": "a1"}, {"user_id": "u"})
            assert r["all_passed"] is False and "0/1" in r["message"]
        rt2 = AsyncMock(return_value={"passed": 2, "total": 2, "results": []})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db3)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.run_tests", rt2):
            r = await mini_app_tool.mini_app_run_tests({"app_id": "a1"}, {"user_id": "u"})
            assert r["all_passed"] is True
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=Exception("x")):
            r = await mini_app_tool.mini_app_run_tests({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is False

    async def test_history_revert_status(self):
        app = self._owned_app()
        db = FakeDB(routes={"MiniApp": {"first": app}})
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.list_logic_history", return_value=[{"v": 1}]):
            r = await mini_app_tool.mini_app_logic_history({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is True
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=Exception("x")):
            r = await mini_app_tool.mini_app_logic_history({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is False

        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.revert_logic", return_value={"version": 1}):
            r = await mini_app_tool.mini_app_revert_logic({"app_id": "a1", "version": 1}, {"user_id": "u"})
            assert r["success"] is True
        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.revert_logic", side_effect=ValueError("no such version")):
            r = await mini_app_tool.mini_app_revert_logic({"app_id": "a1", "version": 9}, {"user_id": "u"})
            assert r["error"] == "no such version"
        with _viewer_patch():
            r = await mini_app_tool.mini_app_revert_logic({"app_id": "a1"}, {"user_id": "u"})
            assert r["error"] == "version is required"
        with _viewer_patch(user_id=None):
            assert "Authenticated" in (await mini_app_tool.mini_app_revert_logic(
                {"app_id": "a", "version": 1}, {}))["error"]

        with _viewer_patch(), patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.MiniApp", MiniAppC), \
             patch("core.mini_app_service.status_probe", return_value={"ok": True}):
            r = await mini_app_tool.mini_app_status({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is True and r["status"] == {"ok": True}
        with _viewer_patch(), patch("core.database.get_db_session", side_effect=Exception("x")):
            r = await mini_app_tool.mini_app_status({"app_id": "a1"}, {"user_id": "u"})
            assert r["success"] is False

    async def test_tier_helpers(self):
        assert mini_app_tool._context_tier({"tier": "INTERN"}) == "intern"
        assert mini_app_tool._context_tier({}) == "student"
        with _viewer_patch(tier="Autonomous"):
            assert mini_app_tool._context_tier({}) == "autonomous"
        assert mini_app_tool._require_tier({}, "supervised") is not None
        assert mini_app_tool._require_tier({"tier": "supervised"}, "supervised") is None

    async def test_db_query_branches(self):
        with _viewer_patch(user_id=None):
            assert "Authenticated" in (await mini_app_tool.mini_app_db_query({}, {}))["error"]
        with _viewer_patch():
            r = await mini_app_tool.mini_app_db_query({}, {"user_id": "u"})
            assert r["error"] == "canvas_id is required"
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "bogus"}, {"user_id": "u"})
            assert "op must be" in r["error"]
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "query"}, {"user_id": "u"})
            assert "INTERN" in r["error"]

        ctx = {"user_id": "u1", "tier": "autonomous"}
        canvas = SimpleNamespace(id="c1", mini_app_id="a1", created_by="u1")
        app = self._owned_app()
        db = FakeDB(routes={"Canvas": {"first": canvas}, "MiniApp": {"first": app}})

        import core.mini_app_db_service as mads
        with patch.object(mads, "db_store_enabled", lambda: True), \
             patch.object(mads, "validate_series", lambda s: "ok" if s and " " not in s and len(s) <= 64 else None), \
             patch.object(mads, "validate_filter", lambda f: True), \
             patch.object(mads, "query_records", lambda *a, **k: ["r1"]), \
             patch.object(mads, "count_records", lambda *a, **k: 7), \
             patch.object(mads, "get_record", lambda *a: {"id": "x"}), \
             patch.object(mads, "list_series", lambda *a: ["s1"]), \
             patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.Canvas", CanvasC), patch("core.models.MiniApp", MiniAppC):
            r = await mini_app_tool.mini_app_db_query(
                {"canvas_id": "c", "op": "query", "series": "s", "limit": 10, "order": "asc",
                 "filter": {"a": 1}}, ctx)
            assert r == {"success": True, "records": ["r1"], "count": 1}
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "count", "series": "s",
                                                       "filter": {}}, ctx)
            assert r == {"success": True, "count": 7}
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "get", "series": "s",
                                                       "record_id": "x"}, ctx)
            assert r == {"success": True, "record": {"id": "x"}}
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "list_series"}, ctx)
            assert r == {"success": True, "series": ["s1"]}
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "query", "series": "BAD SER"}, ctx)
            assert "series" in r["error"]
            with patch.object(mads, "validate_filter", lambda f: False):
                r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "query", "series": "s"}, ctx)
                assert "filter" in r["error"]
                r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "count", "series": "s"}, ctx)
                assert "filter" in r["error"]
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "query", "series": "s",
                                                       "limit": 0}, ctx)
            assert "limit" in r["error"]
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "get", "series": "s"}, ctx)
            assert "record_id" in r["error"]
            with patch.object(mads, "get_record", lambda *a: None):
                r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "get", "series": "s",
                                                           "record_id": "x"}, ctx)
                assert "record not found" in r["error"]
        with patch.object(mads, "db_store_enabled", lambda: False), \
             patch("core.database.get_db_session", _ctx_manager(db)):
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "query"}, ctx)
            assert r["error"] == "db_disabled"
        db_none = FakeDB(routes={"Canvas": {"first": None}})
        with patch.object(mads, "db_store_enabled", lambda: True), \
             patch("core.database.get_db_session", _ctx_manager(db_none)), \
             patch("core.models.Canvas", CanvasC), patch("core.models.MiniApp", MiniAppC):
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "query", "series": "s"}, ctx)
            assert "not owned" in r["error"]
        with patch("core.database.get_db_session", side_effect=Exception("x")):
            r = await mini_app_tool.mini_app_db_query({"canvas_id": "c", "op": "query", "series": "s"}, ctx)
            assert r["success"] is False

    async def test_db_write_branches(self):
        with _viewer_patch(user_id=None):
            assert "Authenticated" in (await mini_app_tool.mini_app_db_write({}, {}))["error"]
        with _viewer_patch():
            r = await mini_app_tool.mini_app_db_write({}, {"user_id": "u"})
            assert r["error"] == "canvas_id is required"
            r = await mini_app_tool.mini_app_db_write({"canvas_id": "c", "op": "zzz"}, {"user_id": "u"})
            assert "op must be" in r["error"]
            r = await mini_app_tool.mini_app_db_write({"canvas_id": "c", "op": "append"}, {"user_id": "u"})
            assert "SUPERVISED" in r["error"]

        ctx = {"user_id": "u1", "tier": "autonomous"}
        canvas = SimpleNamespace(id="c1", mini_app_id="a1", created_by="u1")
        app = self._owned_app()
        db = FakeDB(routes={"Canvas": {"first": canvas}, "MiniApp": {"first": app}})

        import core.mini_app_db_service as mads
        import core.mini_app_service as mas
        with patch.object(mads, "db_store_enabled", lambda: True), \
             patch.object(mads, "validate_series", lambda s: "ok" if s and " " not in s and len(s) <= 64 else None), \
             patch.object(mas, "_validate_record_op", lambda op, mb: op), \
             patch.object(mas, "_execute_record_op", lambda *a, **k: {"ok": True, "id": "r1"}), \
             patch("core.database.get_db_session", _ctx_manager(db)), \
             patch("core.models.Canvas", CanvasC), patch("core.models.MiniApp", MiniAppC):
            r = await mini_app_tool.mini_app_db_write(
                {"canvas_id": "c", "op": "append", "series": "s", "data": {"a": 1}, "id": "r1"}, ctx)
            assert r["success"] is True
            r = await mini_app_tool.mini_app_db_write({"canvas_id": "c", "op": "append", "series": "BAD SER"}, ctx)
            assert "series" in r["error"]
            app.manifest = {"db": {"enabled": False}}
            r = await mini_app_tool.mini_app_db_write({"canvas_id": "c", "op": "append", "series": "s"}, ctx)
            assert r["error"] == "db_disabled"
            app.manifest = {"db": {}}
            with patch.object(mas, "_validate_record_op", lambda op, mb: None):
                r = await mini_app_tool.mini_app_db_write({"canvas_id": "c", "op": "append", "series": "s"}, ctx)
                assert "invalid record op" in r["error"]
            r = await mini_app_tool.mini_app_db_write({"canvas_id": "c", "op": "clear"}, ctx)
            assert r["success"] is True
            # app missing after canvas resolve
            db2 = FakeDB(routes={"Canvas": {"first": canvas}, "MiniApp": {"first": None}})
            with patch("core.database.get_db_session", _ctx_manager(db2)):
                r = await mini_app_tool.mini_app_db_write({"canvas_id": "c", "op": "clear"}, ctx)
                assert "not owned" in r["error"]
        with patch.object(mads, "db_store_enabled", lambda: False), \
             patch("core.database.get_db_session", _ctx_manager(db)):
            r = await mini_app_tool.mini_app_db_write({"canvas_id": "c", "op": "clear"}, ctx)
            assert r["error"] == "db_disabled"
        with patch("core.database.get_db_session", side_effect=Exception("x")):
            r = await mini_app_tool.mini_app_db_write({"canvas_id": "c", "op": "clear"}, ctx)
            assert r["success"] is False

    async def test_resolve_record_target_branches(self):
        canvas = SimpleNamespace(id="c", mini_app_id="a", created_by="me")
        app = SimpleNamespace(created_by="me")

        def mk(c_first, a_first, viewer):
            db = FakeDB(routes={"Canvas": {"first": c_first}, "MiniApp": {"first": a_first}})
            return mini_app_tool._resolve_record_target(db, viewer, "c")

        assert mk(canvas, app, SimpleNamespace(id="me")) is canvas
        nc = SimpleNamespace(id="c", mini_app_id=None, created_by="me")
        assert mk(nc, app, SimpleNamespace(id="me")) is None
        assert mk(canvas, app, SimpleNamespace(id="other")) is None
        # app owner fallback
        app2 = SimpleNamespace(created_by="other2")
        assert mk(SimpleNamespace(id="c", mini_app_id="a", created_by="x"), app2,
                  SimpleNamespace(id="other2")) is not None


# =========================================================================== #
# 2. tools/media_tool.py
# =========================================================================== #
class TestMediaTool:
    def _agent_db(self, status="SUPERVISED"):
        db = FakeDB(routes={"AgentRegistry": {"first": SimpleNamespace(status=status, category="eng")}})
        return db

    async def test_governance_human_and_denied(self):
        r = await media_tool._check_media_governance(MagicMock(), None, "spotify_play", "u")
        assert r["allowed"] is True
        r = await media_tool._check_media_governance(self._agent_db("STUDENT"), "g1", "spotify_play", "u")
        assert r["allowed"] is False and "insufficient" in r["reason"]
        db = FakeDB(routes={"AgentRegistry": {"first": None}})
        with patch("core.models.AgentRegistry", AgentRegistryC):
            r = await media_tool._check_media_governance(db, "g1", "spotify_play", "u")
            assert r["allowed"] is False

    async def test_governance_allowed_and_service_deny_and_error(self):
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"allowed": True})
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), \
             patch("core.models.AgentRegistry", AgentRegistryC):
            r = await media_tool._check_media_governance(self._agent_db("SUPERVISED"), "g1", "spotify_play", "u")
            assert r["allowed"] is True
        gov2 = MagicMock()
        gov2.can_perform_action_async = AsyncMock(return_value={"allowed": False, "reason": "budget spent"})
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov2), \
             patch("core.models.AgentRegistry", AgentRegistryC):
            r = await media_tool._check_media_governance(self._agent_db("AUTONOMOUS"), "g1", "spotify_play", "u")
            assert r["allowed"] is False and r["reason"] == "budget spent"
        gov3 = MagicMock()
        gov3.can_perform_action_async = AsyncMock(return_value={"allowed": False, "reason": "Agent not found"})
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov3), \
             patch("core.models.AgentRegistry", AgentRegistryC):
            r = await media_tool._check_media_governance(self._agent_db("SUPERVISED"), "g1", "spotify_play", "u")
            assert r["allowed"] is True
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        r = await media_tool._check_media_governance(db, "g1", "spotify_play", "u")
        assert r["allowed"] is False
        r = await media_tool._check_media_governance(db, None, "spotify_play", "u")
        assert r["allowed"] is True
        db2 = FakeDB(routes={"AgentRegistry": {"first": SimpleNamespace(status="WEIRD")}})
        with patch("core.models.AgentRegistry", AgentRegistryC):
            r = await media_tool._check_media_governance(db2, "g1", "spotify_play", "u")
            assert r["allowed"] is False

    async def test_spotify_functions(self):
        db = MagicMock()
        with patch.object(media_tool, "SpotifyService") as SS:
            SS.return_value.get_current_track = AsyncMock(return_value={"success": True, "name": "song"})
            r = await media_tool.spotify_current(db, "u")
            assert r["success"] is True
            SS.return_value.get_current_track = AsyncMock(side_effect=RuntimeError("api"))
            r = await media_tool.spotify_current(db, "u")
            assert r["success"] is False
            SS.return_value.play_track = AsyncMock(return_value={"success": True})
            r = await media_tool.spotify_play(db, "u", track_uri="t", device_id="d")
            assert r["success"] is True
            SS.return_value.play_track = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.spotify_play(db, "u"))["success"] is False
            SS.return_value.pause_playback = AsyncMock(return_value={"ok": 1})
            assert (await media_tool.spotify_pause(db, "u"))["ok"] == 1
            SS.return_value.pause_playback = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.spotify_pause(db, "u"))["success"] is False
            SS.return_value.skip_next = AsyncMock(return_value={"ok": 1})
            assert (await media_tool.spotify_next(db, "u"))["ok"] == 1
            SS.return_value.skip_next = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.spotify_next(db, "u"))["success"] is False
            SS.return_value.skip_previous = AsyncMock(return_value={"ok": 1})
            assert (await media_tool.spotify_previous(db, "u"))["ok"] == 1
            SS.return_value.skip_previous = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.spotify_previous(db, "u"))["success"] is False
            SS.return_value.set_volume = AsyncMock(return_value={"ok": 1})
            assert (await media_tool.spotify_volume(db, "u", 50))["ok"] == 1
            SS.return_value.set_volume = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.spotify_volume(db, "u", 50))["success"] is False
            SS.return_value.get_available_devices = AsyncMock(return_value={"devices": []})
            assert (await media_tool.spotify_devices(db, "u"))["devices"] == []
            SS.return_value.get_available_devices = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.spotify_devices(db, "u"))["success"] is False

    async def test_spotify_governance_blocked(self):
        db = self._agent_db("STUDENT")
        with patch("core.models.AgentRegistry", AgentRegistryC):
            r = await media_tool.spotify_play(db, "u", agent_id="g1")
            assert r["governance_blocked"] is True
            r = await media_tool.spotify_current(db, "u", agent_id="g1")
            assert r["governance_blocked"] is True

    async def test_sonos_functions(self):
        db = MagicMock()
        with patch.object(media_tool, "SonosService") as SO:
            SO.return_value.discover_speakers = AsyncMock(return_value=[{"ip": "1.2.3.4"}])
            r = await media_tool.sonos_discover(db)
            assert r["count"] == 1
            SO.return_value.discover_speakers = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.sonos_discover(db))["success"] is False
            SO.return_value.play = AsyncMock(return_value={"ok": 1})
            assert (await media_tool.sonos_play(db, "1.2.3.4"))["ok"] == 1
            SO.return_value.play = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.sonos_play(db, "1.2.3.4"))["success"] is False
            SO.return_value.pause = AsyncMock(return_value={"ok": 1})
            assert (await media_tool.sonos_pause(db, "1.2.3.4"))["ok"] == 1
            SO.return_value.pause = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.sonos_pause(db, "1.2.3.4"))["success"] is False
            SO.return_value.set_volume = AsyncMock(return_value={"ok": 1})
            assert (await media_tool.sonos_volume(db, "1.2.3.4", 30))["ok"] == 1
            SO.return_value.set_volume = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.sonos_volume(db, "1.2.3.4", 30))["success"] is False
            SO.return_value.get_groups = AsyncMock(return_value=[{"g": 1}])
            assert (await media_tool.sonos_groups(db))["count"] == 1
            SO.return_value.get_groups = AsyncMock(side_effect=RuntimeError("x"))
            assert (await media_tool.sonos_groups(db))["success"] is False

    async def test_register_media_tools(self):
        reg = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=reg):
            media_tool.register_media_tools()
        assert reg.register.call_count == 12


# =========================================================================== #
# 3. core/database_manager.py
# =========================================================================== #
class TestDatabaseManager:
    def _mgr(self, url):
        cfg = SimpleNamespace(database=SimpleNamespace(url=url))
        with patch.object(dbm, "get_config", return_value=cfg):
            return dbm.DatabaseManager()

    def test_url_branches(self):
        assert self._mgr("sqlite:///x.db").async_db_url == "sqlite+aiosqlite:///x.db"
        assert self._mgr("postgresql://h/db").async_db_url == "postgresql+asyncpg://h/db"
        assert self._mgr("mysql://x").async_db_url == "sqlite+aiosqlite:///atom_data.db"

    async def test_initialize_idempotent_and_error(self):
        m = self._mgr("sqlite:///t.db")
        engine = MagicMock()
        conn = MagicMock()
        conn.run_sync = AsyncMock()
        engine.begin.return_value.__aenter__ = AsyncMock(return_value=conn)
        engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch.object(dbm, "create_async_engine", return_value=engine), \
             patch.object(dbm, "async_sessionmaker", return_value=MagicMock()):
            await m.initialize()
            assert m._initialized is True
            await m.initialize()  # idempotent
        m2 = self._mgr("sqlite:///t.db")
        with patch.object(dbm, "create_async_engine", side_effect=RuntimeError("no db")):
            with pytest.raises(RuntimeError):
                await m2.initialize()

    def _session_ctx(self, session):
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    async def test_session_ops(self):
        m = self._mgr("sqlite:///t.db")
        session = MagicMock()
        session.execute = AsyncMock(return_value=MagicMock())
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        maker = MagicMock(return_value=self._session_ctx(session))
        m.async_session_maker = maker
        m._initialized = True

        result = MagicMock()
        session.execute = AsyncMock(return_value=result)
        await m.execute("INSERT INTO t VALUES (1)")
        session.execute = AsyncMock(side_effect=RuntimeError("bad sql"))
        with pytest.raises(RuntimeError):
            await m.execute("BAD")

        row = SimpleNamespace(_mapping={"id": 1})
        res = MagicMock()
        res.fetchone.return_value = row
        session.execute = AsyncMock(return_value=res)
        assert await m.fetch_one("SELECT 1") == {"id": 1}
        res2 = MagicMock()
        res2.fetchone.return_value = None
        session.execute = AsyncMock(return_value=res2)
        assert await m.fetch_one("SELECT 2") is None
        session.execute = AsyncMock(side_effect=RuntimeError("x"))
        with pytest.raises(RuntimeError):
            await m.fetch_one("BAD")

        res3 = MagicMock()
        res3.fetchall.return_value = [row, row]
        session.execute = AsyncMock(return_value=res3)
        assert len(await m.fetch_all("SELECT")) == 2
        session.execute = AsyncMock(side_effect=RuntimeError("x"))
        with pytest.raises(RuntimeError):
            await m.fetch_all("BAD")

    async def test_user_and_workflow_ops(self):
        m = self._mgr("sqlite:///t.db")
        session = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        m.async_session_maker = MagicMock(return_value=self._session_ctx(session))
        m._initialized = True

        existing = MagicMock()
        existing.fetchone.return_value = {"id": 1}
        session.execute = AsyncMock(return_value=existing)
        with pytest.raises(ValueError):
            await m.create_user("a@b.c")
        session.rollback.assert_awaited()

        fresh = MagicMock()
        fresh.fetchone.return_value = None
        session.execute = AsyncMock(return_value=fresh)
        with patch.object(dbm, "User",
                          MagicMock(return_value=SimpleNamespace(id="u", email="a@b.c",
                                                                first_name="A", last_name=None))):
            r = await m.create_user("a@b.c", name="A")
            assert r["email"] == "a@b.c"

        row = SimpleNamespace(_mapping={"id": "u", "email": "a@b.c", "first_name": "A",
                                        "last_name": "B", "role": "member", "status": "active"})
        res = MagicMock()
        res.fetchone.return_value = row
        session.execute = AsyncMock(return_value=res)
        r = await m.get_user_by_email("a@b.c")
        assert r["name"] == "A B"
        res2 = MagicMock()
        res2.fetchone.return_value = None
        session.execute = AsyncMock(return_value=res2)
        assert await m.get_user_by_email("z@z.z") is None
        session.execute = AsyncMock(side_effect=RuntimeError("x"))
        with pytest.raises(RuntimeError):
            await m.get_user_by_email("x")

        wf = SimpleNamespace(id="w")
        with patch.object(dbm, "WorkflowExecution", MagicMock(return_value=wf)):
            assert await m.create_workflow_execution(execution_id="w") is wf
            bad = AsyncMock(side_effect=RuntimeError("x"))
            session.commit = bad
            with pytest.raises(RuntimeError):
                await m.create_workflow_execution(execution_id="w")
            session.commit = AsyncMock()
        wrow = SimpleNamespace(_mapping={"execution_id": "e1"})
        res3 = MagicMock()
        res3.fetchone.return_value = wrow
        session.execute = AsyncMock(return_value=res3)
        with patch.object(dbm, "WorkflowExecution", MagicMock(return_value=wf)):
            assert await m.get_workflow_execution("e1") is wf
        res4 = MagicMock()
        res4.fetchone.return_value = None
        session.execute = AsyncMock(return_value=res4)
        assert await m.get_workflow_execution("nope") is None

    async def test_close_and_get_session(self):
        m = self._mgr("sqlite:///t.db")
        m.engine = MagicMock()
        m.engine.dispose = AsyncMock()
        await m.close()
        assert m.engine is None and not m._initialized
        m._initialized = False
        m.initialize = AsyncMock()
        maker = MagicMock()
        m.async_session_maker = maker
        await m._get_session()
        m.initialize.assert_awaited_once()
        maker.assert_called()

    def test_sync_session_helpers(self):
        s = MagicMock()
        with patch.object(dbm, "SessionLocal", return_value=s):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with dbm.get_db_session(commit=True) as db:
                    assert db is s
                s.commit.assert_called()
                with pytest.raises(RuntimeError):
                    with dbm.get_db_session() as db:
                        raise RuntimeError("x")
                s.rollback.assert_called()
                with dbm.get_db_session(close=False, rollback_on_error=False) as db:
                    pass
                s.close.assert_called()
                with pytest.raises(ValueError):
                    with dbm.get_db_session(rollback_on_error=False) as db:
                        raise ValueError("x")
                gen = dbm.get_db_session_for_request()
                assert next(gen) is s
                try:
                    next(gen)
                except StopIteration:
                    pass
                s.close.assert_called()
                mon = dbm.session_health_monitor
                base_sessions = mon.total_sessions
                base_errors = mon.error_count
                with dbm.get_monitored_db_session(commit=True) as db:
                    pass
                assert mon.total_sessions == base_sessions + 1
                with pytest.raises(RuntimeError):
                    with dbm.get_monitored_db_session() as db:
                        raise RuntimeError("x")
                assert mon.error_count == base_errors + 1

    def test_health_monitor(self):
        mon = dbm.SessionHealthMonitor(max_samples=10)
        mon.record_session_creation(0.1)
        mon.record_query(0.2)
        mon.record_error()
        stats = mon.get_stats()
        assert stats["total_sessions"] == 1
        assert stats["error_rate"] == 1.0
        assert stats["avg_creation_time"] == pytest.approx(0.1)
        assert stats["avg_query_time"] == pytest.approx(0.2)
        assert mon._percentile(mon.creation_times, 95) == 0.1
        assert mon._percentile([], 95) == 0.0


# =========================================================================== #
# 4. core/webhook_metrics.py
# =========================================================================== #
class TestWebhookMetrics:
    def test_recording_and_counters(self):
        m = wm.WebhookMetrics()
        m.record_delivery("slack", "tenant-123", 10.0, signature_valid=True)
        m.record_delivery("slack", "tenant-123", 20.0, signature_valid=False)
        assert m.get_delivery_count("slack", "tenant-123") == 2
        assert m.get_signature_failure_count("slack", "tenant-123") == 1
        assert m.get_delivery_rate("slack", "tenant-123") == 50.0
        p = m.get_delivery_percentiles("slack", "tenant-123")
        assert p["p50"] in (10.0, 20.0)
        assert m.get_delivery_percentiles("none", "none") == {"p50": 0, "p95": 0, "p99": 0}
        assert m.get_total_deliveries("slack") == 2
        assert m.get_total_deliveries("other") == 0
        m.record_delivery("gh", "", 5.0, signature_valid=True)
        assert m.get_delivery_count("gh", "") == 1
        assert m.get_delivery_rate("ghost", "ghost") == 100.0

        m.record_processing_success("slack", "tenant-123", 30.0, entities_count=4)
        m.record_processing_success("slack", "tenant-123", 40.0)
        m.record_processing_error("slack", "tenant-123", "llm_error", 5.0)
        m.record_processing_error("slack", "tenant-123", "transformation_error")
        assert m.get_processing_success_count("slack", "tenant-123") == 2
        assert m.get_processing_error_count("slack", "tenant-123") == 2
        assert m.get_processing_errors_by_type("slack", "tenant-123")["llm_error"] == 1
        assert m.get_entities_extracted_count("slack", "tenant-123") == 4
        assert m.get_processing_success_rate("slack", "tenant-123") == 50.0
        assert m.get_processing_success_rate("x", "y") == 100.0
        pp = m.get_processing_percentiles("slack", "tenant-123")
        assert set(pp) == {"p50", "p95", "p99"}
        assert m.get_processing_percentiles("x", "y") == {"p50": 0, "p95": 0, "p99": 0}

    def test_sample_retention(self):
        m = wm.WebhookMetrics()
        for i in range(1100):
            m.record_delivery("c", "t", float(i), signature_valid=True)
            m.record_processing_success("c2", "t2", float(i))
        dk = m._make_duration_key("c", "t")
        pk = m._make_duration_key("c2", "t2")
        assert len(m._delivery_duration_samples[dk]) <= 1000
        assert len(m._processing_duration_samples[pk]) <= 1000

    def test_singleton_and_module_funcs(self):
        wm.WebhookMetrics._instance = None
        a = wm.WebhookMetrics.get_instance()
        assert wm.WebhookMetrics.get_instance() is a
        wm.record_webhook_delivery("c", "t", 1.0, True)
        wm.record_webhook_processing_success("c", "t", 1.0, 2)
        wm.record_webhook_processing_error("c", "t", "boom")
        assert wm.get_webhook_metrics() is wm._webhook_metrics

    def test_export_prometheus(self):
        m = wm.WebhookMetrics()
        m.record_delivery("slack", "tenant-123", 10.0, signature_valid=False)
        m.record_processing_success("slack", "tenant-123", 30.0, entities_count=4)
        m.record_processing_error("slack", "tenant-123", "llm_error", 5.0)
        out = m.export_prometheus()
        assert "webhook_delivery_count" in out
        assert 'status="signature_error"' in out
        assert "webhook_delivery_duration_ms" in out
        assert "webhook_signature_verification_failures" in out
        assert "webhook_processing_count" in out
        assert 'status="error"' in out
        assert "webhook_processing_duration_ms" in out
        assert "webhook_entities_extracted" in out
        assert 'error_type="llm_error"' in out
        assert "webhook_transformation_errors" in out

    def test_persist_to_redis(self):
        m = wm.WebhookMetrics()
        m.record_delivery("c", "t", 1.0, True)
        r = MagicMock()
        r.setex.side_effect = RuntimeError("redis down")
        m.persist_to_redis(r)  # error swallowed
        m.persist_to_redis(None)  # no-op
        r2 = MagicMock()
        m.persist_to_redis(r2)
        r2.setex.assert_called_once()


# =========================================================================== #
# 5. core/debug_ai_assistant.py
# =========================================================================== #
class TestDebugAIAssistant:
    def _assistant(self, db):
        with patch.object(dai, "DebugQuery", MagicMock()), \
             patch.object(dai, "DebugMonitor", MagicMock()), \
             patch.object(dai, "ConsistencyInsightGenerator", MagicMock()), \
             patch.object(dai, "PerformanceInsightGenerator", MagicMock()):
            a = dai.DebugAIAssistant(db)
        a.query_api = MagicMock()
        a.monitor = MagicMock()
        a.performance_gen = MagicMock()
        a.consistency_gen = MagicMock()
        return a

    async def test_detect_intent(self):
        a = self._assistant(MagicMock())
        assert a._detect_intent("how is agent health") == "component_health"
        assert a._detect_intent("why is it failing") == "failure_analysis"
        assert a._detect_intent("why is this slow") == "performance_analysis"
        assert a._detect_intent("check consistency") == "consistency_check"
        assert a._detect_intent("recurring error pattern") == "error_patterns"
        assert a._detect_intent("what happened here") == "general_explanation"
        assert a._detect_intent("zzz") == "general_explanation"

    async def test_ask_routes_and_error(self):
        a = self._assistant(MagicMock())
        a._handle_component_health_question = AsyncMock(return_value={"answer": "h"})
        r = await a.ask("system health", {})
        assert r["answer"] == "h"
        a._handle_failure_question = AsyncMock(side_effect=RuntimeError("boom"))
        r = await a.ask("why is agent failing")
        assert "error" in r["answer"] and r["confidence"] == 0.0

    async def test_component_health(self):
        db = FakeDB()
        a = self._assistant(db)
        r = await a._handle_component_health_question("status?", None)
        assert r["clarification_needed"] == "component_id"
        r = await a._handle_component_health_question("status?", {})
        assert r["clarification_needed"] == "component_id"
        a.query_api.get_component_health = AsyncMock(return_value={
            "error_rate": 0.1, "health_score": 99, "error_events": 0, "recent_insights": []})
        r = await a._handle_component_health_question("health of agent-123", None)
        assert "healthy" in r["answer"]
        a.query_api.get_component_health = AsyncMock(return_value={
            "error_rate": 0.9, "health_score": 10, "error_events": 5, "recent_insights": []})
        db.queue = [FakeQuery(all_=[SimpleNamespace(message="m1")])]
        r = await a._handle_component_health_question("health of agent-123", None)
        assert "issues" in r["answer"]
        a.monitor.get_system_health = AsyncMock(return_value={
            "overall_health_score": 90, "status": "healthy", "active_operations": 5,
            "total_events": 10, "error_rate": 0.0})
        r = await a._handle_component_health_question("how is the system health",
                                                      {"component_type": "system"})
        assert "System health" in r["answer"]
        a.query_api.get_component_health = AsyncMock(side_effect=RuntimeError("x"))
        r = await a._handle_component_health_question("health of agent-123", None)
        assert r["confidence"] == 0.0

    async def test_failure_question(self):
        db = FakeDB()
        a = self._assistant(db)
        r = await a._handle_failure_question("why is it broken", None)
        assert r["clarification_needed"] == "component_id"
        r = await a._handle_failure_question("why is agent-1 failing", None)
        assert "No recent errors" in r["answer"]
        errs = [SimpleNamespace(message="m"), SimpleNamespace(message="m"), SimpleNamespace(message=None)]
        insights = [SimpleNamespace(id="i", insight_type="error", severity="high",
                                    summary="s", suggestions=["do x"])]
        db.queue = [FakeQuery(all_=errs), FakeQuery(all_=insights)]
        r = await a._handle_failure_question("why is agent-1 failing", None)
        assert "3 error(s)" in r["answer"]
        assert "do x" in r["suggestions"]
        # no error messages at all → "No common errors" branch
        db2 = FakeDB(queue=[FakeQuery(all_=[SimpleNamespace(message=None)]),
                            FakeQuery(all_=insights)])
        a2 = self._assistant(db2)
        r = await a2._handle_failure_question("why is agent-1 failing", None)
        assert "No common errors" in r["answer"]
        # error branch
        dbx = MagicMock()
        dbx.query.side_effect = RuntimeError("db")
        a3 = self._assistant(dbx)
        r = await a3._handle_failure_question("why is agent-1 failing", None)
        assert r["confidence"] == 0.0

    async def test_performance_question(self):
        db = FakeDB()
        a = self._assistant(db)
        r = await a._handle_performance_question("is it slow", None)
        assert r["clarification_needed"] == "component_id"
        ins = SimpleNamespace(severity="warning", summary="slow", description="d",
                              confidence_score=0.8, evidence={}, suggestions=["s"])
        a.performance_gen.analyze_component_latency = AsyncMock(return_value=ins)
        r = await a._handle_performance_question("why is workflow-2 slow", None)
        assert r["answer"] == "slow" and "description" in r
        ins2 = SimpleNamespace(severity="info", summary="fine", description="d",
                               confidence_score=0.9, evidence={}, suggestions=[])
        a.performance_gen.analyze_component_latency = AsyncMock(return_value=ins2)
        r = await a._handle_performance_question("why is workflow-2 slow", None)
        assert "No action needed" in r["suggestions"]
        a.performance_gen.analyze_component_latency = AsyncMock(return_value=None)
        r = await a._handle_performance_question("why is workflow-2 slow", None)
        assert "No performance data" in r["answer"]
        a.performance_gen.analyze_component_latency = AsyncMock(side_effect=RuntimeError("x"))
        r = await a._handle_performance_question("why is workflow-2 slow", None)
        assert r["confidence"] == 0.0

    async def test_consistency_question(self):
        db = FakeDB()
        a = self._assistant(db)
        r = await a._handle_consistency_question("is data consistent", None)
        assert r["clarification_needed"] == "operation_or_component"
        r = await a._handle_consistency_question("is agent-1 data consistent", None)
        assert r["clarification_needed"] == "operation_id"
        r = await a._handle_consistency_question("check op-123 consistency", None)
        assert "No activity" in r["answer"]
        db.queue = [FakeQuery(all_=[("agent", "a1")])]
        ins = SimpleNamespace(summary="consistent", description="d", confidence_score=0.7,
                              evidence={"e": 1}, suggestions=["s"])
        a.consistency_gen.analyze_data_flow = AsyncMock(return_value=ins)
        r = await a._handle_consistency_question("check op-123 sync", None)
        assert r["answer"] == "consistent"
        a.consistency_gen.analyze_data_flow = AsyncMock(return_value=None)
        db.queue = [FakeQuery(all_=[("agent", "a1")])]
        r = await a._handle_consistency_question("check op-123 sync", None)
        assert "No consistency data" in r["answer"]
        dbx = MagicMock()
        dbx.query.side_effect = RuntimeError("x")
        a2 = self._assistant(dbx)
        r = await a2._handle_consistency_question("check op-123 sync", None)
        assert r["confidence"] == 0.0

    async def test_error_patterns_question(self):
        db = FakeDB()
        a = self._assistant(db)
        r = await a._handle_error_patterns_question("error patterns", None)
        assert "No significant error patterns" in r["answer"]
        db.queue = [FakeQuery(all_=[SimpleNamespace(
            title="t", evidence={"occurrence_count": 3}, severity="high", summary="s")])]
        r = await a._handle_error_patterns_question("frequent error pattern", None)
        assert "1 error pattern" in r["answer"]
        dbx = MagicMock()
        dbx.query.side_effect = RuntimeError("x")
        a2 = self._assistant(dbx)
        r = await a2._handle_error_patterns_question("error patterns", None)
        assert r["confidence"] == 0.0

    async def test_general_question(self):
        db = FakeDB()
        a = self._assistant(db)
        a.query_api.get_operation_progress = AsyncMock(return_value={
            "status": "in_progress", "progress": 0.5, "started_at": "t",
            "total_steps": 3, "insights": ["i"]})
        r = await a._handle_general_question("explain operation op-99", None)
        assert "50% progress" in r["answer"]
        a.monitor.get_system_health = AsyncMock(return_value={
            "status": "healthy", "overall_health_score": 95, "error_rate": 0.0,
            "active_operations": 1})
        r = await a._handle_general_question("explain the situation", None)
        assert "No critical issues" in r["answer"]
        a.monitor.get_system_health = AsyncMock(return_value={
            "status": "degraded", "overall_health_score": 50, "error_rate": 2.5,
            "active_operations": 500})
        r = await a._handle_general_question("explain the situation", None)
        assert "Error rate is 2.5%" in r["answer"]
        a.monitor.get_system_health = AsyncMock(side_effect=RuntimeError("x"))
        r = await a._handle_general_question("explain", None)
        assert r["confidence"] == 0.0

    async def test_helpers(self):
        a = self._assistant(MagicMock())
        assert a._generate_failure_suggestions([], [SimpleNamespace(suggestions=["a"])]) == ["a"]
        s = a._generate_failure_suggestions([1], [SimpleNamespace(suggestions=None)])
        assert "Review error logs for details" in s
        assert set(a._generate_failure_suggestions([], [])) == {
            "Check component configuration", "Verify external dependencies"}
        recs = a._get_system_recommendations({"error_rate": 0.5, "overall_health_score": 50,
                                               "active_operations": 500})
        assert len(recs) == 3
        assert a._get_system_recommendations({"error_rate": 0.0, "overall_health_score": 100,
                                               "active_operations": 0}) == ["System is operating normally"]
        er = a._error_response("boom")
        assert "boom" in er["answer"] and er["confidence"] == 0.0


# =========================================================================== #
# 6. core/agent_social_layer.py
# =========================================================================== #
_FakeSocialPost = _C("SocialPost")
_FakeAgentRegistry = _C("AgentRegistry")


class TestAgentSocialLayer:
    def _db(self, agent=None, posts=None, channels=None, feedback_count=0, post_count=None):
        posts = posts if posts is not None else []
        return FakeDB(routes={
            "AgentRegistry": {"first": agent},
            "SocialPost": {"first": posts[0] if posts else None,
                           "all": posts,
                           "count": len(posts) if post_count is None else post_count},
            "Channel": {"first": channels[0] if channels else None, "all": channels or []},
            "AgentFeedback": {"count": feedback_count},
        })

    def _post(self, **kw):
        return SimpleNamespace(
            id=kw.get("id", "p1"),
            tenant_id="default",
            author_type=kw.get("author_type", "agent"),
            author_id=kw.get("author_id", "g1"),
            post_type=kw.get("post_type", "status"),
            content=kw.get("content", "hello"),
            created_at=kw.get("created_at", datetime(2026, 1, 1, tzinfo=timezone.utc)),
            reactions=kw.get("reactions", None),
            post_metadata=kw.get("post_metadata", {}),
        )

    def _agent(self, status="INTERN", tenant_id="t1"):
        return SimpleNamespace(id="g1", status=status, category="eng",
                               tenant_id=tenant_id, name="Robo")

    def _bus(self):
        bus = MagicMock()
        bus.broadcast_post = AsyncMock()
        bus.publish = AsyncMock()
        return bus

    def _redactor(self, text="red", secrets=False):
        gr = MagicMock()
        gr.return_value.redact.return_value = SimpleNamespace(
            redacted_text=text, has_secrets=secrets, redactions=[{"type": "EMAIL"}] if secrets else [])
        return gr

    async def test_create_post_governance(self):
        layer = asl.AgentSocialLayer()
        with patch.object(asl, "agent_event_bus", self._bus()):
            with pytest.raises(PermissionError):
                await layer.create_post("agent", "g1", "N", "status", "hi", db=None)
            with patch.object(asl, "SocialPost", _FakeSocialPost), \
                 patch.object(asl, "AgentRegistry", _FakeAgentRegistry):
                with pytest.raises(PermissionError):  # agent not found
                    await layer.create_post("agent", "g1", "N", "status", "hi", db=self._db())
                with pytest.raises(PermissionError):  # student blocked
                    db = self._db(agent=self._agent(status="student"))
                    await layer.create_post("agent", "g1", "N", "status", "hi", db=db)
            with pytest.raises(ValueError):  # invalid type
                await layer.create_post("human", "u1", "N", "bogus", "hi", db=None)
            with patch.object(asl, "get_pii_redactor", self._redactor("red")), \
                 patch.object(asl, "SocialPost", _FakeSocialPost):
                r = await layer.create_post("human", "u1", "N", "command", "hi", db=None)
                assert r["post_type"] == "command"
            with patch.object(asl, "get_pii_redactor", self._redactor("red")):
                r = await layer.create_post("human", "u1", "N", "status", "hi", db=None)
                assert r["sender_id"] == "u1"

    async def test_create_post_full(self):
        layer = asl.AgentSocialLayer()
        db = self._db(agent=self._agent(status="INTERN"))
        with patch.object(asl, "agent_event_bus", self._bus()), \
             patch.object(asl, "SocialPost", _FakeSocialPost), \
             patch.object(asl, "AgentRegistry", _FakeAgentRegistry), \
             patch.object(asl, "get_pii_redactor", self._redactor("clean")):
            r = await layer.create_post("agent", "g1", "Robo", "insight", "found @g2",
                                        db=db, channel_id="ch", channel_name="Ch",
                                        mentioned_agent_ids=["g2"])
            assert r["tenant_id"] == "t1"
            assert r["channel_id"] == "ch"
            assert db.added
            # redaction failure falls back to original content
            bad = MagicMock()
            bad.side_effect = RuntimeError("redactor down")
            with patch.object(asl, "get_pii_redactor", bad):
                r = await layer.create_post("human", "u1", "N", "status", "secret@x.com", db=None)
                assert r["content"] == "secret@x.com"
            # redaction with secrets
            with patch.object(asl, "get_pii_redactor", self._redactor("***", secrets=True)):
                r = await layer.create_post("human", "u1", "N", "status", "a@b.c", db=None)
                assert r["content"] == "***"

    async def test_get_feed(self):
        layer = asl.AgentSocialLayer()
        assert await layer.get_feed("u", db=None) == {"posts": [], "total": 0}
        p = self._post()
        db = self._db(posts=[p])
        with patch.object(asl, "SocialPost", _FakeSocialPost), patch.object(asl, "func"), \
             patch.object(asl, "desc", lambda c: c):
            r = await layer.get_feed("u", post_type="status", sender_filter="g1",
                                     channel_id="ch", is_public=False, db=db)
            assert r["total"] == 1 and r["posts"][0]["id"] == "p1"

    async def test_reactions_and_trending(self):
        layer = asl.AgentSocialLayer()
        with pytest.raises(ValueError):
            await layer.add_reaction("p", "u", "👍", db=None)
        db = self._db()
        with patch.object(asl, "SocialPost", _FakeSocialPost):
            with pytest.raises(ValueError):
                await layer.add_reaction("missing", "u", "👍", db=db)
        p = self._post(reactions={"👍": 1})
        db2 = self._db(posts=[p])
        with patch.object(asl, "SocialPost", _FakeSocialPost), \
             patch.object(asl, "agent_event_bus", self._bus()):
            r = await layer.add_reaction("p1", "u", "👍", db=db2)
            assert r["👍"] == 2
        p2 = self._post(reactions=[SimpleNamespace(emoji="❤️"), SimpleNamespace(emoji=None)])
        db3 = self._db(posts=[p2])
        with patch.object(asl, "SocialPost", _FakeSocialPost), \
             patch.object(asl, "agent_event_bus", self._bus()):
            r = await layer.add_reaction("p1", "u", "❤️", db=db3)
            assert r["❤️"] == 2

        assert await layer.get_trending_topics(db=None) == []
        tp = self._post(post_metadata={
            "mentioned_agent_ids": ["g2"], "mentioned_user_ids": ["u2"],
            "mentioned_episode_ids": ["e1"], "mentioned_task_ids": ["t1"]})
        with patch.object(asl, "SocialPost", _FakeSocialPost):
            tr = await layer.get_trending_topics(db=self._db(posts=[tp]))
            assert {t["topic"] for t in tr} >= {"agent:g2", "user:u2", "episode:e1", "task:t1"}

    async def test_add_reply(self):
        layer = asl.AgentSocialLayer()
        with pytest.raises(ValueError):
            await layer.add_reply("p", "human", "u", "N", "hi", db=None)
        db = self._db()
        with patch.object(asl, "SocialPost", _FakeSocialPost):
            with pytest.raises(ValueError):
                await layer.add_reply("missing", "human", "u", "N", "hi", db=db)
        db2 = self._db(posts=[self._post()], agent=self._agent(status="STUDENT"))
        with patch.object(asl, "SocialPost", _FakeSocialPost), \
             patch.object(asl, "AgentRegistry", _FakeAgentRegistry):
            with pytest.raises(PermissionError):
                await layer.add_reply("p1", "agent", "g1", "N", "hi", db=db2)
        db3 = self._db(posts=[self._post()])
        with patch.object(asl, "SocialPost", _FakeSocialPost), \
             patch.object(asl, "get_pii_redactor", self._redactor()), \
             patch.object(asl, "agent_event_bus", self._bus()):
            r = await layer.add_reply("p1", "human", "u1", "N", "hi", db=db3)
            assert r["post_type"] == "response"

    async def test_feed_cursor(self):
        layer = asl.AgentSocialLayer()
        assert await layer.get_feed_cursor("u", db=None) == {"posts": [], "next_cursor": None,
                                                             "has_more": False}
        posts = [self._post(id=f"p{i}", created_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc))
                 for i in range(3)]
        with patch.object(asl, "SocialPost", _FakeSocialPost), \
             patch.object(asl, "func"), patch.object(asl, "cast", lambda *a, **k: _Col()), \
             patch.object(asl, "desc", lambda c: c), patch.object(asl, "String", MagicMock()):
            db = self._db(posts=posts)
            r = await layer.get_feed_cursor("u", cursor="not-a-cursor", db=db)
            assert r["has_more"] is False and len(r["posts"]) == 3
            r = await layer.get_feed_cursor("u", cursor="2026-01-02T00:00:00", db=db)
            assert isinstance(r["posts"], list)
            # has_more true → next cursor emitted
            db2 = self._db(posts=posts)
            db2.queue = None
            db2.query = lambda *a, **k: FakeQuery(all_=posts + [posts[0]])
            r = await layer.get_feed_cursor("u", limit=3, db=db2)
            assert r["has_more"] is True and r["next_cursor"]
            # compound cursor
            r = await layer.get_feed_cursor("u", cursor="2026-01-02T00:00:00:p1",
                                            db=self._db(posts=posts))
            assert isinstance(r["posts"], list)

    async def test_channels(self):
        layer = asl.AgentSocialLayer()
        with pytest.raises(ValueError):
            await layer.create_channel("c", "n", "u", db=None)
        assert await layer.get_channels(db=None) == []
        ch = SimpleNamespace(
            id="c1", name="n", display_name="N", description="d", channel_type="general",
            is_public=True, created_by="u", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        db = self._db(channels=[ch])
        with patch("core.models.Channel", ChannelC), patch.object(asl, "agent_event_bus", self._bus()):
            r = await layer.create_channel("c1", "n", "u", db=db)  # exists
            assert r["exists"] is True
            db2 = self._db()
            made = SimpleNamespace(id="c2", name="n2")
            with patch("core.models.Channel", MagicMock(return_value=made)):
                r = await layer.create_channel("c2", "n2", "u", db=db2)
                assert r["created"] is True
        with patch("core.models.Channel", ChannelC):
            chs = await layer.get_channels(db=db)
            assert chs[0]["id"] == "c1"

    async def test_replies_listing_and_episode_helpers(self):
        layer = asl.AgentSocialLayer()
        assert await layer.get_replies("p", db=None) == {"replies": [], "total": 0}
        rp = self._post()
        db = self._db(posts=[rp])
        with patch.object(asl, "SocialPost", _FakeSocialPost), patch.object(asl, "func"):
            r = await layer.get_replies("p1", db=db)
            assert r["total"] == 1

        seg = SimpleNamespace(id="s1")
        with patch.object(asl, "get_pii_redactor", self._redactor()), \
             patch.object(asl, "agent_event_bus", self._bus()), \
             patch("core.models.EpisodeSegment", MagicMock(return_value=seg)):
            r = await layer.create_post_with_episode(
                "human", "u1", "N", "status", "hi", episode_ids=["e1"], db=FakeDB())
            assert r["sender_id"] == "u1"
            layer._retrieve_relevant_episodes = AsyncMock(return_value=["e2"])
            dba = self._db(agent=self._agent())
            with patch.object(asl, "SocialPost", _FakeSocialPost), \
                 patch.object(asl, "AgentRegistry", _FakeAgentRegistry):
                r = await layer.create_post_with_episode("agent", "g1", "N", "status", "hi", db=dba)
                assert r["sender_id"] == "g1"
            with patch("core.models.EpisodeSegment", side_effect=Exception("seg fail")):
                r = await layer.create_post_with_episode(
                    "human", "u1", "N", "status", "hi", episode_ids=["e1"], db=FakeDB())
                assert r["sender_id"] == "u1"

        # restore the real method (was stubbed above) and exercise it directly
        layer._retrieve_relevant_episodes = asl.AgentSocialLayer._retrieve_relevant_episodes.__get__(layer)
        assert await layer._retrieve_relevant_episodes("g", "c", db=None) == []
        with patch("core.episode_retrieval_service.EpisodeRetrievalService") as ERS:
            ERS.return_value.retrieve_episodes = AsyncMock(
                return_value=[SimpleNamespace(id="e1"), SimpleNamespace(id="e2")])
            out = await layer._retrieve_relevant_episodes("g", "c", db=FakeDB())
            assert out == ["e1", "e2"]
        with patch("core.episode_retrieval_service.EpisodeRetrievalService",
                   side_effect=ImportError("no")):
            assert await layer._retrieve_relevant_episodes("g", "c", db=FakeDB()) == []

    async def test_feed_with_episode_context(self):
        layer = asl.AgentSocialLayer()
        posts = [self._post(post_metadata={"mentioned_episode_ids": ["e1"]})]
        db = self._db(posts=posts)
        with patch.object(asl, "SocialPost", _FakeSocialPost), patch.object(asl, "func"), \
             patch.object(asl, "desc", lambda c: c), \
             patch.object(layer, "_get_episode_summaries", AsyncMock(return_value=[{"id": "e1"}])):
            r = await layer.get_feed_with_episode_context(db=db)
            assert r["posts"][0]["episode_context"] == [{"id": "e1"}]
        with patch.object(asl, "SocialPost", _FakeSocialPost), patch.object(asl, "func"), \
             patch.object(asl, "desc", lambda c: c), \
             patch.object(layer, "_get_episode_summaries", AsyncMock(side_effect=RuntimeError("x"))):
            r = await layer.get_feed_with_episode_context(db=db)
            assert r["posts"][0]["episode_context"] == []

        assert await layer._get_episode_summaries([], db=db) == []
        assert await layer._get_episode_summaries(["e"], db=None) == []
        ep = SimpleNamespace(id="e1", title="T", summary="s" * 300,
                             created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), agent_id="g")
        db2 = FakeDB(queue=[FakeQuery(all_=[ep])])
        with patch("core.models.Episode", EpisodeC):
            out = await layer._get_episode_summaries(["e1"], db=db2)
            assert out[0]["id"] == "e1" and len(out[0]["summary"]) == 200
        dbx = MagicMock()
        dbx.query.side_effect = RuntimeError("x")
        with patch("core.models.Episode", EpisodeC):
            assert await layer._get_episode_summaries(["e1"], db=dbx) == []

    async def test_interaction_tracking(self):
        layer = asl.AgentSocialLayer()
        await layer.track_positive_interaction("p", "reaction", db=None)  # no-op
        db = self._db(posts=[self._post()])  # author_type str "agent"
        with patch.object(asl, "SocialPost", _FakeSocialPost), \
             patch("core.agent_graduation_service.AgentGraduationService", MagicMock()), \
             patch("core.models.AgentFeedback", MagicMock()):
            await layer.track_positive_interaction("p1", "👍", user_id="u", db=db)
            assert db.added
        db2 = self._db(posts=[self._post(author_type="human")])
        with patch.object(asl, "SocialPost", _FakeSocialPost):
            await layer.track_positive_interaction("p1", "👎", db=db2)
        dbx = MagicMock()
        dbx.query.side_effect = RuntimeError("x")
        await layer.track_positive_interaction("p1", "👍", db=dbx)

        assert layer._is_positive_interaction("THANKS") is True
        assert layer._is_positive_interaction("👍") is True
        assert layer._is_positive_interaction("meh") is False
        await layer._update_agent_reputation("g", "reaction", db=None)

    async def test_reputation(self):
        layer = asl.AgentSocialLayer()
        r = await layer.get_agent_reputation("g", db=None)
        assert r["reputation_score"] == 0
        p1 = self._post(reactions=[1, 2])
        p2 = self._post(reactions={"👍": 3})
        db = self._db(posts=[p1, p2], feedback_count=4)
        with patch.object(asl, "SocialPost", _FakeSocialPost), patch.object(asl, "func"):
            r = await layer.get_agent_reputation("g1", db=db)
            assert r["total_reactions"] == 5 and r["helpful_replies"] == 4
        dbx = MagicMock()
        dbx.query.side_effect = RuntimeError("x")
        r = await layer.get_agent_reputation("g1", db=dbx)
        assert "error" in r

        assert await layer._count_helpful_replies("g", db=None) == 0
        with patch("core.models.AgentFeedback", AgentFeedbackC):
            assert await layer._count_helpful_replies("g", db=self._db(feedback_count=2)) == 2
        dbq = MagicMock()
        dbq.query.side_effect = RuntimeError("x")
        with patch("core.models.AgentFeedback", AgentFeedbackC):
            assert await layer._count_helpful_replies("g", db=dbq) == 0

        assert await layer._calculate_percentile_rank("g", 50, db=None) == 0.0
        with patch.object(asl, "AgentRegistry", _FakeAgentRegistry):
            assert await layer._calculate_percentile_rank("g", 50, db=self._db()) == 0.0
            dbn = FakeDB(queue=[FakeQuery(all_=[SimpleNamespace()])])
            assert await layer._calculate_percentile_rank("g", 50, db=dbn) == 50.0
        dbq2 = MagicMock()
        dbq2.query.side_effect = RuntimeError("x")
        with patch.object(asl, "AgentRegistry", _FakeAgentRegistry):
            assert await layer._calculate_percentile_rank("g", 50, db=dbq2) == 0.0

        assert await layer._get_reputation_trend("g", db=None) == []
        tp = self._post()
        with patch.object(asl, "SocialPost", _FakeSocialPost):
            tr = await layer._get_reputation_trend("g1", db=self._db(posts=[tp]))
            assert tr == [{"date": "2026-01-01", "post_count": 1}]
        dbq3 = MagicMock()
        dbq3.query.side_effect = RuntimeError("x")
        with patch.object(asl, "SocialPost", _FakeSocialPost):
            assert await layer._get_reputation_trend("g", db=dbq3) == []

    async def test_graduation_milestone(self):
        layer = asl.AgentSocialLayer()
        assert await layer.post_graduation_milestone("g", "a", "b", db=None) == {}
        db = self._db()
        with patch.object(asl, "SocialPost", _FakeSocialPost), \
             patch.object(asl, "AgentRegistry", _FakeAgentRegistry):
            with pytest.raises(ValueError):
                await layer.post_graduation_milestone("missing", "a", "b", db=db)
        dba = self._db(agent=self._agent())
        with patch.object(asl, "SocialPost", _FakeSocialPost), \
             patch.object(asl, "AgentRegistry", _FakeAgentRegistry), \
             patch.object(asl, "get_pii_redactor", self._redactor(text="🎉 graduated!")), \
             patch.object(asl, "agent_event_bus", self._bus()):
            r = await layer.post_graduation_milestone("g1", "INTERN", "SUPERVISED", db=dba)
            assert "graduated" in r["content"]

    async def test_rate_limits(self):
        layer = asl.AgentSocialLayer()
        assert await layer.check_rate_limit("g", db=None) == (True, None)
        with patch.object(asl, "AgentRegistry", _FakeAgentRegistry):
            allowed, reason = await layer.check_rate_limit("missing", db=self._db())
            assert allowed is False and "not found" in reason
            dbs = self._db(agent=self._agent(status="student"))
            allowed, reason = await layer.check_rate_limit("g1", db=dbs)
            assert allowed is False and "read-only" in reason
            with patch.object(asl, "SocialPost", _FakeSocialPost):
                dbi = self._db(agent=self._agent(status="INTERN"), posts=[self._post()])
                allowed, reason = await layer.check_rate_limit("g1", db=dbi)
                assert allowed is False and "Rate limit" in reason
                dbu = self._db(agent=self._agent(status="SUPERVISED"), posts=[self._post()])
                assert (await layer.check_rate_limit("g1", db=dbu)) == (True, None)
            dba = self._db(agent=self._agent(status="AUTONOMOUS"))
            assert (await layer.check_rate_limit("g1", db=dba)) == (True, None)
        dbx = MagicMock()
        dbx.query.side_effect = RuntimeError("x")
        assert await layer.check_rate_limit("g1", db=dbx) == (True, None)

        assert await layer._check_hourly_limit("g", 5, db=None) == (True, None)
        with patch.object(asl, "SocialPost", _FakeSocialPost):
            ok, _ = await layer._check_hourly_limit("g1", max_posts=1,
                                                    db=self._db(posts=[self._post()]))
            assert ok is False
            ok, _ = await layer._check_hourly_limit("g1", max_posts=5,
                                                    db=self._db(posts=[self._post()]))
            assert ok is True
        dbq = MagicMock()
        dbq.query.side_effect = RuntimeError("x")
        assert await layer._check_hourly_limit("g", 1, db=dbq) == (True, None)

        assert "error" in await layer.get_rate_limit_info("g", db=None)
        with patch.object(asl, "AgentRegistry", _FakeAgentRegistry):
            assert "error" in await layer.get_rate_limit_info("missing", db=self._db())
            with patch.object(asl, "SocialPost", _FakeSocialPost):
                dba2 = self._db(agent=self._agent(status="AUTONOMOUS"))
                r = await layer.get_rate_limit_info("g1", db=dba2)
                assert r["unlimited"] is True
                dbi2 = self._db(agent=self._agent(status="INTERN"))
                r = await layer.get_rate_limit_info("g1", db=dbi2)
                assert r["max_posts_per_hour"] == 1 and r["remaining_posts"] == 1
        dbx2 = MagicMock()
        dbx2.query.side_effect = RuntimeError("x")
        assert "error" in await layer.get_rate_limit_info("g1", db=dbx2)

    def test_register_hooks(self):
        with patch("core.operation_tracker_hooks.register_auto_post_hooks", MagicMock()):
            asl.register_hooks_if_needed()
        with patch("core.operation_tracker_hooks.register_auto_post_hooks",
                   side_effect=ImportError("nope")):
            asl.register_hooks_if_needed()  # warning path
