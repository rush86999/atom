"""Coverage-push + bug-hunt tests for backend/tools (part 5).

Covers: canvas_tool (gap coverage) and mini_app_tool.
"""

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@contextmanager
def _db_ctx(db):
    yield db


def _patch_db(db):
    return patch("core.database.get_db_session", side_effect=lambda: _db_ctx(db))


# ============================================================================
# canvas_tool gap coverage
# ============================================================================

class TestCanvasToolGaps:
    @pytest.fixture(autouse=True)
    def _canvas_patch(self):
        self.agent = SimpleNamespace(id="a-1", name="Agent A", status="autonomous",
                                     maturity_level="AUTONOMOUS", workspace_id="ws-1")
        self.resolver = MagicMock()
        self.resolver.resolve_agent_for_request = AsyncMock(return_value=(self.agent, {}))
        self.gov = MagicMock()
        self.gov.can_perform_action.return_value = {"allowed": True, "reason": None}
        self.gov.record_outcome = AsyncMock()
        with patch("tools.canvas_tool.ws_manager") as ws, \
             patch("tools.canvas_tool.AgentContextResolver", return_value=self.resolver), \
             patch("tools.canvas_tool.FeatureFlags.should_enforce_governance",
                   return_value=True), \
             patch("core.service_factory.ServiceFactory") as sf:
            ws.broadcast = AsyncMock()
            sf.get_governance_service.return_value = self.gov
            self.ws = ws
            yield

    def _db(self):
        db = MagicMock()
        db.commit = Mock()
        db.refresh = Mock()
        return db

    def _gov_deny(self):
        self.gov.can_perform_action.return_value = {"allowed": False, "reason": "nope"}

    async def test_present_chart_blocked(self):
        self._gov_deny()
        from tools.canvas_tool import present_chart
        with _patch_db(self._db()):
            res = await present_chart("u-1", "line_chart", [{"x": 1, "y": 2}],
                                      agent_id="a-1")
        assert res["success"] is False and "nope" in res["error"]
        self.ws.broadcast.assert_not_awaited()

    async def test_present_chart_full_success(self):
        from tools.canvas_tool import present_chart
        with _patch_db(self._db()):
            res = await present_chart("u-1", "line_chart", [{"x": 1, "y": 2}],
                                      title="Sales", agent_id="a-1", session_id="s-1",
                                      color="blue")
        assert res["success"] is True and res["agent_id"] == "a-1"
        self.ws.broadcast.assert_awaited_once()
        self.gov.record_outcome.assert_awaited_once()

    async def test_present_chart_exception_with_execution_failure(self):
        from tools.canvas_tool import present_chart
        db = self._db()
        db.query.side_effect = RuntimeError("db down")
        with _patch_db(db):
            res = await present_chart("u-1", "line_chart", [], agent_id="a-1")
        assert res["success"] is False

    async def test_present_status_panel_blocked(self):
        self._gov_deny()
        from tools.canvas_tool import present_status_panel
        with _patch_db(self._db()):
            res = await present_status_panel("u-1", [{"label": "L", "value": 1}],
                                             agent_id="a-1")
        assert res["success"] is False

    async def test_present_status_panel_success_and_error(self):
        from tools.canvas_tool import present_status_panel
        with _patch_db(self._db()):
            res = await present_status_panel("u-1", [{"label": "L", "value": 1}],
                                             title="Panel", agent_id="a-1", session_id="s-1")
        assert res["success"] is True
        self.ws.broadcast.assert_awaited_once()
        self.ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
        with _patch_db(self._db()):
            res2 = await present_status_panel("u-1", [{"label": "L", "value": 1}])
        assert res2["success"] is False

    async def test_present_markdown_blocked(self):
        self._gov_deny()
        from tools.canvas_tool import present_markdown
        with _patch_db(self._db()):
            res = await present_markdown("u-1", "# hi", agent_id="a-1")
        assert res["success"] is False

    async def test_present_markdown_success_and_error(self):
        from tools.canvas_tool import present_markdown
        with _patch_db(self._db()):
            res = await present_markdown("u-1", "# hi", title="T", agent_id="a-1",
                                         session_id="s-1")
        assert res["success"] is True and res["canvas_id"]
        self.ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
        with _patch_db(self._db()):
            res2 = await present_markdown("u-1", "# hi")
        assert res2["success"] is False

    async def test_present_form_blocked(self):
        self._gov_deny()
        from tools.canvas_tool import present_form
        with _patch_db(self._db()):
            res = await present_form("u-1", {"fields": []}, agent_id="a-1")
        assert res["success"] is False

    async def test_present_form_success_and_error(self):
        from tools.canvas_tool import present_form
        with _patch_db(self._db()):
            res = await present_form("u-1", {"fields": [{"name": "x"}]}, title="F",
                                     agent_id="a-1", session_id="s-1")
        assert res["success"] is True and res["canvas_id"]
        self.ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
        with _patch_db(self._db()):
            res2 = await present_form("u-1", {"fields": []})
        assert res2["success"] is False

    async def test_update_canvas_blocked(self):
        self._gov_deny()
        from tools.canvas_tool import update_canvas
        with _patch_db(self._db()):
            res = await update_canvas("u-1", "c-1", {"data": [1]}, agent_id="a-1")
        assert res["success"] is False

    async def test_update_canvas_success_and_error(self):
        from tools.canvas_tool import update_canvas
        with _patch_db(self._db()):
            res = await update_canvas("u-1", "c-1", {"data": [1], "title": "T"},
                                      agent_id="a-1", session_id="s-1")
        assert res["success"] is True and res["updated_fields"] == ["data", "title"]
        self.ws.broadcast.assert_awaited_once()
        self.ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
        with _patch_db(self._db()):
            res2 = await update_canvas("u-1", "c-1", {"data": [1]})
        assert res2["success"] is False

    async def test_present_to_canvas_routing(self):
        from tools.canvas_tool import present_to_canvas
        with _patch_db(self._db()):
            res = await present_to_canvas(Mock(), "u-1", "chart",
                                          {"chart_type": "bar_chart", "data": [1]})
            assert res["success"] is True
            res = await present_to_canvas(Mock(), "u-1", "form", {"fields": []})
            assert res["success"] is True
            res = await present_to_canvas(Mock(), "u-1", "markdown", {"content": "# m"})
            assert res["success"] is True
            res = await present_to_canvas(Mock(), "u-1", "status_panel", {"items": []})
            assert res["success"] is True
            res = await present_to_canvas(Mock(), "u-1", "docs",
                                           {"component_type": "rich_editor"})
            assert res["success"] is True
            res = await present_to_canvas(Mock(), "u-1", "unknown", {})
            assert res["success"] is False and "Unknown canvas type" in res["error"]

    async def test_present_to_canvas_exception(self):
        from tools.canvas_tool import present_to_canvas
        with patch("tools.canvas_tool.present_chart",
                   new=AsyncMock(side_effect=RuntimeError("x"))), _patch_db(self._db()):
            res = await present_to_canvas(Mock(), "u-1", "chart", {"data": []})
        assert res["success"] is False

    async def test_close_canvas(self):
        from tools.canvas_tool import close_canvas
        res = await close_canvas("u-1", session_id="s-1")
        assert res["success"] is True
        self.ws.broadcast.assert_awaited_once()
        self.ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
        res2 = await close_canvas("u-1")
        assert res2["success"] is False

    async def test_canvas_execute_javascript_no_agent(self):
        from tools.canvas_tool import canvas_execute_javascript
        res = await canvas_execute_javascript("u-1", "c-1", "x", agent_id=None)
        assert res["success"] is False

    async def test_canvas_execute_javascript_blocked(self):
        self._gov_deny()
        from tools.canvas_tool import canvas_execute_javascript
        with _patch_db(self._db()):
            res = await canvas_execute_javascript("u-1", "c-1", "x", agent_id="a-1")
        assert res["success"] is False

    async def test_canvas_execute_javascript_not_autonomous(self):
        from tools.canvas_tool import canvas_execute_javascript
        from core.models import AgentStatus
        agent = SimpleNamespace(id="a-1", name="Intern", status=AgentStatus.INTERN.value)
        self.resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, {}))
        with _patch_db(self._db()):
            res = await canvas_execute_javascript("u-1", "c-1", "x", agent_id="a-1")
        assert res["success"] is False and "AUTONOMOUS" in res["error"]

    async def test_canvas_execute_javascript_empty(self):
        from tools.canvas_tool import canvas_execute_javascript
        with _patch_db(self._db()):
            res = await canvas_execute_javascript("u-1", "c-1", "   ", agent_id="a-1")
        assert res["success"] is False and "cannot be empty" in res["error"]

    @pytest.mark.parametrize("code", [
        "eval('x')", "Function('x')", "setTimeout(f, 1)", "setInterval(f, 1)",
        "document.cookie", "localStorage.setItem", "sessionStorage.clear",
        "window.location", "window.top", "window.parent",
    ])
    async def test_canvas_execute_javascript_dangerous(self, code):
        from tools.canvas_tool import canvas_execute_javascript
        with _patch_db(self._db()):
            res = await canvas_execute_javascript("u-1", "c-1", code, agent_id="a-1")
        assert res["success"] is False and "dangerous pattern" in res["error"]

    async def test_canvas_execute_javascript_success(self):
        from tools.canvas_tool import canvas_execute_javascript
        with _patch_db(self._db()):
            res = await canvas_execute_javascript("u-1", "c-1", "document.title = 'x'",
                                                  agent_id="a-1", session_id="s-1",
                                                  timeout_ms=1000)
        assert res["success"] is True and res["javascript_length"] == len("document.title = 'x'")
        self.ws.broadcast.assert_awaited_once()
        self.gov.record_outcome.assert_awaited_once()

    async def test_canvas_execute_javascript_error(self):
        from tools.canvas_tool import canvas_execute_javascript
        self.ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
        with _patch_db(self._db()):
            res = await canvas_execute_javascript("u-1", "c-1", "document.title = 'x'",
                                                  agent_id="a-1")
        assert res["success"] is False

    async def test_present_specialized_canvas_validation(self):
        from tools.canvas_tool import present_specialized_canvas
        with _patch_db(self._db()):
            res = await present_specialized_canvas("u-1", "bogus", "x", {})
        assert res["success"] is False and "Invalid canvas type" in res["error"]
        with _patch_db(self._db()):
            res = await present_specialized_canvas("u-1", "docs", "bogus_component", {})
        assert res["success"] is False and "not supported" in res["error"]
        with _patch_db(self._db()):
            res = await present_specialized_canvas("u-1", "docs", "rich_editor", {},
                                                   layout="bogus_layout")
        assert res["success"] is False and "Layout" in res["error"]

    async def test_present_specialized_canvas_blocked(self):
        self._gov_deny()
        from tools.canvas_tool import present_specialized_canvas
        with _patch_db(self._db()):
            res = await present_specialized_canvas("u-1", "docs", "rich_editor", {},
                                                   agent_id="a-1")
        assert res["success"] is False and "not permitted" in res["error"]

    async def test_present_specialized_canvas_insufficient_maturity(self):
        from tools.canvas_tool import present_specialized_canvas
        agent = SimpleNamespace(id="a-1", name="Student", status="student")
        self.resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, {}))
        with _patch_db(self._db()):
            res = await present_specialized_canvas("u-1", "docs", "rich_editor", {},
                                                   agent_id="a-1")
        assert res["success"] is False and "insufficient" in res["error"]

    async def test_present_specialized_canvas_success(self):
        from tools.canvas_tool import present_specialized_canvas
        with _patch_db(self._db()):
            res = await present_specialized_canvas("u-1", "docs", "rich_editor",
                                                   {"content": "x"}, title="Doc",
                                                   agent_id="a-1", session_id="s-1",
                                                   layout="document")
        assert res["success"] is True and res["canvas_type"] == "docs"
        self.ws.broadcast.assert_awaited_once()
        self.gov.record_outcome.assert_awaited_once()

    async def test_present_specialized_canvas_error(self):
        from tools.canvas_tool import present_specialized_canvas
        self.ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
        with _patch_db(self._db()):
            res = await present_specialized_canvas("u-1", "docs", "rich_editor", {})
        assert res["success"] is False

    async def test_create_canvas_audit_error(self):
        from tools.canvas_tool import _create_canvas_audit
        db = MagicMock()
        db.add.side_effect = RuntimeError("x")
        assert await _create_canvas_audit(db, None, None, "u-1", "c-1", None) is None


# ============================================================================
# mini_app_tool
# ============================================================================

def _mini_app(**kw):
    base = dict(id="app-1", name="App", created_by="u-1", blueprint_canvas_id="bc-1",
                manifest={"tests": [{"name": "t1"}]}, tenant_id="t-1", status="draft",
                is_public=False, version=1, created_at=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _viewer_db(user_row):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user_row
    return db


def _keyed_db(mapping):
    db = MagicMock()

    def _query(model):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.first.return_value = mapping.get(model.__name__)
        return q

    db.query.side_effect = _query
    return db


class TestMiniAppTool:
    @pytest.fixture(autouse=True)
    def _mini_patch(self):
        self.app = _mini_app()
        self.viewer_row = SimpleNamespace(id="u-1", tenant_id="t-1", workspace_id="w-1",
                                          tier="AUTONOMOUS")
        yield

    def _user_ctx(self, **kw):
        ctx = {"user_id": "u-1", "agent_id": "ag-1"}
        ctx.update(kw)
        return ctx

    async def test_context_user_id(self):
        from tools.mini_app_tool import _context_user_id
        assert _context_user_id(None) is None
        assert _context_user_id({}) is None
        assert _context_user_id({"user_id": "u1"}) == "u1"
        assert _context_user_id({"userId": "u2"}) == "u2"
        assert _context_user_id({"actor_id": "u3"}) == "u3"
        assert _context_user_id({"user": SimpleNamespace(id="u4")}) == "u4"
        assert _context_user_id({"user": SimpleNamespace(id=None)}) is None

    async def test_viewer_with_row(self):
        with _patch_db(_viewer_db(self.viewer_row)):
            from tools.mini_app_tool import _viewer
            v = _viewer({"user_id": "u-1"})
        assert v.id == "u-1" and v.tenant_id == "t-1" and v.tier == "AUTONOMOUS"

    async def test_viewer_fallback(self):
        with _patch_db(_viewer_db(None)):
            from tools.mini_app_tool import _viewer
            v = _viewer({"user_id": "u-1"})
        assert v.id == "u-1" and v.tenant_id is None
        with _patch_db(_viewer_db(None)):
            v2 = _viewer({})
        assert v2.id is None

    async def test_viewer_db_error(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        with _patch_db(db):
            from tools.mini_app_tool import _viewer
            v = _viewer({"user_id": "u-1"})
        assert v.id == "u-1" and v.tenant_id is None

    async def test_scaffold_auth_and_name(self):
        from tools.mini_app_tool import mini_app_scaffold
        res = await mini_app_scaffold({}, {})
        assert res["success"] is False and "Authenticated user" in res["error"]
        res = await mini_app_scaffold({"name": "  "}, self._user_ctx())
        assert res["success"] is False and "name is required" in res["error"]

    async def test_scaffold_full(self):
        app = _mini_app()
        with _patch_db(_keyed_db({"User": self.viewer_row, "MiniApp": app})), \
             patch("core.mini_app_service.scaffold",
                   return_value=(app, "canvas-1")) as scaffold, \
             patch("core.canvas_logic_service.CanvasLogicService") as logic_cls:
            logic_cls.return_value.load_logic = Mock(return_value={"source": "print('hi')"})
            from tools.mini_app_tool import mini_app_scaffold
            res = await mini_app_scaffold(
                {"name": "MyApp", "spec": {"base_image": ""},
                 "declared_scopes": ["canvas"], "dependencies": ["pandas"]},
                self._user_ctx())
        assert res["success"] is True and res["app_id"] == "app-1"
        assert res["logic_source"] == "print('hi')"
        assert scaffold.call_args.kwargs["spec"]["base_image"] == "python:3.11-slim"

    async def test_scaffold_error(self):
        with _patch_db(_viewer_db(self.viewer_row)), \
             patch("core.mini_app_service.scaffold", side_effect=RuntimeError("x")):
            from tools.mini_app_tool import mini_app_scaffold
            res = await mini_app_scaffold({"name": "MyApp"}, self._user_ctx())
        assert res["success"] is False

    async def test_write_logic_paths(self):
        from tools.mini_app_tool import mini_app_write_logic
        res = await mini_app_write_logic({}, {})
        assert res["success"] is False
        res = await mini_app_write_logic({}, self._user_ctx())
        assert res["success"] is False and "app_id is required" in res["error"]
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = None
        with _patch_db(db):
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x"},
                                             self._user_ctx())
        assert res["success"] is False and "not found" in res["error"]

    async def test_write_logic_not_owner_and_no_blueprint(self):
        from tools.mini_app_tool import mini_app_write_logic
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = _mini_app(
            created_by="other")
        with _patch_db(db):
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x"},
                                             self._user_ctx())
        assert res["success"] is False and "owner" in res["error"]
        db2 = _viewer_db(self.viewer_row)
        db2.query.return_value.filter.return_value.first.return_value = _mini_app(
            blueprint_canvas_id=None)
        with _patch_db(db2):
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x"},
                                             self._user_ctx())
        assert res["success"] is False and "blueprint" in res["error"]

    async def test_write_logic_syntax_error(self):
        from tools.mini_app_tool import mini_app_write_logic
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = self.app
        with _patch_db(db), \
             patch("core.mini_app_service.syntax_check",
                   side_effect=SyntaxError("bad syntax")):
            res = await mini_app_write_logic({"app_id": "app-1", "source": "def x(:"},
                                             self._user_ctx())
        assert res["success"] is False and "SyntaxError" in res["error"]

    async def test_write_logic_success(self):
        from tools.mini_app_tool import mini_app_write_logic
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = self.app
        with _patch_db(db), \
             patch("core.mini_app_service.syntax_check", return_value=None), \
             patch("core.canvas_logic_service.CanvasLogicService") as logic_cls, \
             patch("core.mini_app_service.record_logic_snapshot",
                   return_value={"version": 2}):
            logic_cls.return_value.save_logic = Mock()
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x = 1"},
                                             self._user_ctx())
        assert res["success"] is True and res["version"] == 2
        logic_cls.return_value.save_logic.assert_called_once()

    async def test_write_logic_error(self):
        from tools.mini_app_tool import mini_app_write_logic
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = self.app
        with _patch_db(db), \
             patch("core.mini_app_service.syntax_check", side_effect=RuntimeError("x")):
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x"},
                                             self._user_ctx())
        assert res["success"] is False

    async def test_dev_run_paths(self):
        from tools.mini_app_tool import mini_app_dev_run
        res = await mini_app_dev_run({}, {})
        assert res["success"] is False
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = None
        with _patch_db(db):
            res = await mini_app_dev_run({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False and "not found" in res["error"]

    async def test_dev_run_runtime_error(self):
        from tools.mini_app_tool import mini_app_dev_run
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = self.app
        with _patch_db(db), \
             patch("core.mini_app_service.prepare_runtime",
                   side_effect=RuntimeError("deps unsafe")):
            res = await mini_app_dev_run({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False and "deps unsafe" in res["error"]

    async def test_dev_run_success(self):
        from tools.mini_app_tool import mini_app_dev_run
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = self.app
        result = {"success": True, "state": {"x": 1}, "version": 1, "state_changed": False,
                  "proposed_ops": [], "op_results": [], "stdout": "out", "stderr": "",
                  "exit_code": 0}
        with _patch_db(db), \
             patch("core.mini_app_service.prepare_runtime"), \
             patch("core.mini_app_service.run_stateful",
                   new=AsyncMock(return_value=result)) as run:
            res = await mini_app_dev_run({"app_id": "app-1", "inputs": {"a": 1}},
                                         self._user_ctx())
        assert res["success"] is True and res["state"] == {"x": 1}
        run.assert_awaited_once()
        assert run.await_args.kwargs["persist"] is False

    async def test_dev_run_failed_result_and_error(self):
        from tools.mini_app_tool import mini_app_dev_run
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = self.app
        with _patch_db(db), \
             patch("core.mini_app_service.prepare_runtime"), \
             patch("core.mini_app_service.run_stateful",
                   new=AsyncMock(return_value={"success": False, "error": "vm crash"})):
            res = await mini_app_dev_run({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False and "vm crash" in res["error"]
        with _patch_db(db), \
             patch("core.mini_app_service.prepare_runtime"), \
             patch("core.mini_app_service.run_stateful",
                   new=AsyncMock(side_effect=RuntimeError("generic"))):
            res2 = await mini_app_dev_run({"app_id": "app-1"}, self._user_ctx())
        assert res2["success"] is False and "generic" in res2["error"]

    async def test_publish_paths(self):
        from tools.mini_app_tool import mini_app_publish
        res = await mini_app_publish({}, {})
        assert res["success"] is False
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = None
        with _patch_db(db):
            res = await mini_app_publish({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False and "not found" in res["error"]
        db2 = _viewer_db(self.viewer_row)
        db2.query.return_value.filter.return_value.first.return_value = self.app
        with _patch_db(db2), \
             patch("core.mini_app_service.publish", return_value={"version": 3}):
            res = await mini_app_publish({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is True and res["version"] == 3
        with _patch_db(db2), \
             patch("core.mini_app_service.publish", side_effect=RuntimeError("boom")):
            res = await mini_app_publish({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False
        with _patch_db(db2), \
             patch("core.mini_app_service.publish", side_effect=RuntimeError("boom")):
            res = await mini_app_publish({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False

    async def test_install_paths(self):
        from tools.mini_app_tool import mini_app_install
        res = await mini_app_install({}, {})
        assert res["success"] is False
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = None
        with _patch_db(db):
            res = await mini_app_install({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False
        db2 = _viewer_db(self.viewer_row)
        db2.query.return_value.filter.return_value.first.return_value = self.app
        with _patch_db(db2), \
             patch("core.mini_app_service.install", return_value="canvas-9"):
            res = await mini_app_install({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is True and res["canvas_id"] == "canvas-9"
        with _patch_db(db2), \
             patch("core.mini_app_service.install",
                   side_effect=ValueError("already installed")):
            res = await mini_app_install({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False and "already installed" in res["error"]
        with _patch_db(db2), \
             patch("core.mini_app_service.install", side_effect=RuntimeError("x")):
            res = await mini_app_install({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False

    async def test_run_paths(self):
        from tools.mini_app_tool import mini_app_run
        res = await mini_app_run({}, {})
        assert res["success"] is False
        with _patch_db(_viewer_db(self.viewer_row)), \
             patch("core.mini_app_service.run_stateful",
                   new=AsyncMock(return_value={"success": True, "state": {}})) as run:
            res = await mini_app_run({"canvas_id": "c-1", "inputs": {}}, self._user_ctx())
        assert res["success"] is True
        assert run.await_args.kwargs["persist"] is True
        assert run.await_args.kwargs["agent_id"] == "ag-1"

    async def test_list_paths(self):
        from tools.mini_app_tool import mini_app_list
        res = await mini_app_list({}, {})
        assert res["success"] is False
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all \
            .return_value = [self.app]
        with _patch_db(db):
            res = await mini_app_list({}, self._user_ctx())
        assert res["success"] is True and len(res["apps"]) == 1
        assert res["apps"][0]["id"] == "app-1"
        db2 = _viewer_db(self.viewer_row)
        db2.query.side_effect = RuntimeError("x")
        with _patch_db(db2):
            res2 = await mini_app_list({}, self._user_ctx())
        assert res2["success"] is False and res2["apps"] == []

    async def test_get_state_paths(self):
        from tools.mini_app_tool import mini_app_get_state
        res = await mini_app_get_state({}, {})
        assert res["success"] is False
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = None
        with _patch_db(db):
            res = await mini_app_get_state({"canvas_id": "c-1"}, self._user_ctx())
        assert res["success"] is False and "not found" in res["error"]
        canvas = SimpleNamespace(id="c-1", mini_app_id="app-1")
        state_row = SimpleNamespace(state={"n": 1}, version=2)
        db2 = _viewer_db(self.viewer_row)
        q = db2.query.return_value.filter.return_value
        q.first.return_value = canvas
        q.order_by.return_value.first.return_value = state_row
        with _patch_db(db2):
            res = await mini_app_get_state({"canvas_id": "c-1"}, self._user_ctx())
        assert res["success"] is True and res["state"] == {"n": 1} and res["version"] == 2
        canvas2 = SimpleNamespace(id="c-1", mini_app_id=None)
        db3 = _viewer_db(self.viewer_row)
        db3.query.return_value.filter.return_value.first.return_value = canvas2
        with _patch_db(db3):
            res = await mini_app_get_state({"canvas_id": "c-1"}, self._user_ctx())
        assert res["success"] is False and "not a mini-app" in res["error"]
        canvas3 = SimpleNamespace(id="c-1", mini_app_id="app-1")
        db4 = _viewer_db(self.viewer_row)
        q4 = db4.query.return_value.filter.return_value
        q4.first.return_value = canvas3
        q4.order_by.return_value.first.return_value = None
        with _patch_db(db4):
            res = await mini_app_get_state({"canvas_id": "c-1"}, self._user_ctx())
        assert res["success"] is True and res["state"] == {} and res["version"] == 0
        db5 = _viewer_db(self.viewer_row)
        db5.query.side_effect = RuntimeError("x")
        with _patch_db(db5):
            res = await mini_app_get_state({"canvas_id": "c-1"}, self._user_ctx())
        assert res["success"] is False

    async def test_set_tests_paths(self):
        from tools.mini_app_tool import mini_app_set_tests
        res = await mini_app_set_tests({}, {})
        assert res["success"] is False
        res = await mini_app_set_tests({"app_id": "app-1", "tests": "notalist"},
                                       self._user_ctx())
        assert res["success"] is False and "must be a list" in res["error"]
        with _patch_db(_viewer_db(self.viewer_row)), \
             patch("core.mini_app_service.validate_tests") as vt:
            db = _viewer_db(self.viewer_row)
            db.query.return_value.filter.return_value.first.return_value = self.app
            with _patch_db(db):
                res = await mini_app_set_tests({"app_id": "app-1", "tests": [{"name": "t"}]},
                                               self._user_ctx())
            assert res["success"] is True and res["tests"] == 1
            vt.side_effect = ValueError("bad test")
            with _patch_db(db):
                res2 = await mini_app_set_tests({"app_id": "app-1", "tests": [{}]},
                                                self._user_ctx())
            assert res2["success"] is False and "bad test" in res2["error"]
            vt.side_effect = RuntimeError("boom")
            with _patch_db(db):
                res3 = await mini_app_set_tests({"app_id": "app-1", "tests": [{}]},
                                                self._user_ctx())
            assert res3["success"] is False

    async def test_run_tests_paths(self):
        from tools.mini_app_tool import mini_app_run_tests
        res = await mini_app_run_tests({}, {})
        assert res["success"] is False
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = None
        with _patch_db(db):
            res = await mini_app_run_tests({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False
        app_no_tests = _mini_app(manifest={})
        db2 = _viewer_db(self.viewer_row)
        db2.query.return_value.filter.return_value.first.return_value = app_no_tests
        with _patch_db(db2):
            res = await mini_app_run_tests({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is True and res["total"] == 0
        db3 = _viewer_db(self.viewer_row)
        db3.query.return_value.filter.return_value.first.return_value = self.app
        report = {"passed": 1, "total": 2, "results": [{"name": "t1", "passed": True}]}
        with _patch_db(db3), \
             patch("core.mini_app_service.run_tests", new=AsyncMock(return_value=report)):
            res = await mini_app_run_tests({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is True and res["all_passed"] is False
        assert "1/2" in res["message"]
        report2 = {"passed": 2, "total": 2, "results": []}
        with _patch_db(db3), \
             patch("core.mini_app_service.run_tests", new=AsyncMock(return_value=report2)):
            res2 = await mini_app_run_tests({"app_id": "app-1"}, self._user_ctx())
        assert res2["all_passed"] is True and "All 2" in res2["message"]
        with _patch_db(db3), \
             patch("core.mini_app_service.run_tests",
                   new=AsyncMock(side_effect=RuntimeError("x"))):
            res3 = await mini_app_run_tests({"app_id": "app-1"}, self._user_ctx())
        assert res3["success"] is False

    async def test_logic_history_paths(self):
        from tools.mini_app_tool import mini_app_logic_history
        res = await mini_app_logic_history({}, {})
        assert res["success"] is False
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = self.app
        with _patch_db(db), \
             patch("core.mini_app_service.list_logic_history", return_value=[{"v": 1}]):
            res = await mini_app_logic_history({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is True and res["history"] == [{"v": 1}]
        with _patch_db(db), \
             patch("core.mini_app_service.list_logic_history",
                   side_effect=RuntimeError("x")):
            res2 = await mini_app_logic_history({"app_id": "app-1"}, self._user_ctx())
        assert res2["success"] is False

    async def test_revert_logic_paths(self):
        from tools.mini_app_tool import mini_app_revert_logic
        res = await mini_app_revert_logic({}, {})
        assert res["success"] is False
        res = await mini_app_revert_logic({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is False and "version is required" in res["error"]
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = self.app
        with _patch_db(db), \
             patch("core.mini_app_service.revert_logic", return_value={"version": 1}):
            res = await mini_app_revert_logic({"app_id": "app-1", "version": 1},
                                              self._user_ctx())
        assert res["success"] is True and res["version"] == 1
        with _patch_db(db), \
             patch("core.mini_app_service.revert_logic",
                   side_effect=ValueError("no such version")):
            res2 = await mini_app_revert_logic({"app_id": "app-1", "version": 99},
                                               self._user_ctx())
        assert res2["success"] is False and "no such version" in res2["error"]
        with _patch_db(db), \
             patch("core.mini_app_service.revert_logic",
                   side_effect=RuntimeError("x")):
            res3 = await mini_app_revert_logic({"app_id": "app-1", "version": 1},
                                               self._user_ctx())
        assert res3["success"] is False

    async def test_status_paths(self):
        from tools.mini_app_tool import mini_app_status
        res = await mini_app_status({}, {})
        assert res["success"] is False
        db = _viewer_db(self.viewer_row)
        db.query.return_value.filter.return_value.first.return_value = self.app
        with _patch_db(db), \
             patch("core.mini_app_service.status_probe", return_value={"ready": True}):
            res = await mini_app_status({"app_id": "app-1"}, self._user_ctx())
        assert res["success"] is True and res["status"] == {"ready": True}
        with _patch_db(db), \
             patch("core.mini_app_service.status_probe", side_effect=RuntimeError("x")):
            res2 = await mini_app_status({"app_id": "app-1"}, self._user_ctx())
        assert res2["success"] is False
