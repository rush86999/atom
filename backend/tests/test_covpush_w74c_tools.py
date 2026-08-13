"""Coverage-push tests for backend/tools (W74c).

Standalone >=95% statement coverage for:
- tools/calendar_tool.py
- tools/data_analysis_tool.py
- tools/media_tool.py
- tools/predictive_tools.py
- tools/productivity_tool.py
- tools/smarthome_tool.py
- tools/creative_tool.py
- tools/canvas_orchestration_tool.py

Style: mocked deps, zero LLM spend, no network, no real DB.
"""

import importlib
import sys
import builtins
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@contextmanager
def _db_ctx(db):
    yield db


def _patch_db(db):
    return patch("core.database.get_db_session", side_effect=lambda: _db_ctx(db))


def _patch_tool_db(module, db):
    return patch(f"tools.{module}.get_db_session", side_effect=lambda: _db_ctx(db))


# ============================================================================
# tools/calendar_tool.py
# ============================================================================

class TestCalendarToolInit:
    @pytest.fixture(autouse=True)
    def _svc(self):
        self.svc = MagicMock()
        self.svc.authenticate.return_value = True
        with patch("tools.calendar_tool.google_calendar_service", self.svc):
            yield

    def test_init_authenticated(self):
        from tools.calendar_tool import CalendarTool
        tool = CalendarTool()
        assert tool.governance_cache is not None
        self.svc.authenticate.assert_called()

    def test_init_auth_exception(self):
        self.svc.authenticate.side_effect = RuntimeError("no token")
        from tools.calendar_tool import CalendarTool
        tool = CalendarTool()
        assert tool.governance_cache is not None


class TestCalendarPermission:
    async def _agent(self, maturity):
        return SimpleNamespace(maturity_level=maturity)

    async def test_no_agent_allowed(self):
        from tools.calendar_tool import CalendarTool
        tool = CalendarTool()
        ok, reason = await tool._check_calendar_permission(None, "u-1", "get_events", "INTERN")
        assert ok is True and reason is None

    async def test_cached_hit(self):
        from tools.calendar_tool import CalendarTool
        tool = CalendarTool()
        with patch("tools.calendar_tool._governance_cache") as cache:
            cache.get.return_value = {"allowed": False, "reason": "cached no"}
            ok, reason = await tool._check_calendar_permission("a-1", "u-1", "get_events", "INTERN")
        assert ok is False and reason == "cached no"

    async def test_agent_not_found(self):
        from tools.calendar_tool import CalendarTool
        tool = CalendarTool()
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = None
        with patch("tools.calendar_tool._governance_cache") as cache, \
                _patch_tool_db("calendar_tool", q):
            cache.get.return_value = None
            ok, reason = await tool._check_calendar_permission("a-1", "u-1", "get_events", "INTERN")
        assert ok is False and "not found" in reason

    async def test_invalid_maturity(self):
        from tools.calendar_tool import CalendarTool
        tool = CalendarTool()
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="GODMODE")
        with patch("tools.calendar_tool._governance_cache") as cache, \
                _patch_tool_db("calendar_tool", q):
            cache.get.return_value = None
            ok, reason = await tool._check_calendar_permission("a-1", "u-1", "get_events", "INTERN")
        assert ok is False and "Invalid maturity" in reason

    async def test_denied_caches(self):
        from tools.calendar_tool import CalendarTool
        tool = CalendarTool()
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="STUDENT")
        with patch("tools.calendar_tool._governance_cache") as cache, \
                _patch_tool_db("calendar_tool", q):
            cache.get.return_value = None
            cache.set = Mock()
            ok, reason = await tool._check_calendar_permission("a-1", "u-1", "create_event", "SUPERVISED")
        assert ok is False and "SUPERVISED" in reason
        cache.set.assert_called_once()
        call_kwargs = cache.set.call_args[0][2]
        assert call_kwargs["allowed"] is False

    async def test_allowed(self):
        from tools.calendar_tool import CalendarTool
        tool = CalendarTool()
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="AUTONOMOUS")
        with patch("tools.calendar_tool._governance_cache") as cache, \
                _patch_tool_db("calendar_tool", q):
            cache.get.return_value = None
            ok, reason = await tool._check_calendar_permission("a-1", "u-1", "get_events", "INTERN")
        assert ok is True and reason is None

    async def test_permission_exception(self):
        from tools.calendar_tool import CalendarTool
        tool = CalendarTool()
        with patch("tools.calendar_tool._governance_cache") as cache, \
                patch("tools.calendar_tool.get_db_session", side_effect=RuntimeError("db down")):
            cache.get.return_value = None
            ok, reason = await tool._check_calendar_permission("a-1", "u-1", "get_events", "INTERN")
        assert ok is False and "Permission check failed" in reason


class TestCalendarRun:
    async def _tool(self):
        from tools.calendar_tool import CalendarTool
        return CalendarTool()

    async def test_unknown_action(self):
        tool = await self._tool()
        res = await tool.run("do_magic", agent_id=None)
        assert res["success"] is False and "Unknown action" in res["error"]
        assert "create_event" in res["available_actions"]

    async def test_permission_denied_raises(self):
        from tools.calendar_tool import CalendarTool
        tool = await self._tool()
        with patch.object(CalendarTool, "_check_calendar_permission",
                          AsyncMock(return_value=(False, "not allowed"))):
            with pytest.raises(PermissionError, match="not allowed"):
                await tool.run("create_event", agent_id="a-1", user_id="u-1")

    async def test_success_path(self):
        tool = await self._tool()
        with patch.object(tool, "_check_calendar_permission",
                          AsyncMock(return_value=(True, None))), \
             patch.object(tool, "_execute_action",
                          AsyncMock(return_value={"success": True, "events": []})):
            res = await tool.run("get_events", agent_id="a-1", user_id="u-1")
        assert res["success"] is True

    async def test_execute_permission_error_reraises(self):
        tool = await self._tool()
        with patch.object(tool, "_check_calendar_permission",
                          AsyncMock(return_value=(True, None))), \
             patch.object(tool, "_execute_action",
                          AsyncMock(side_effect=PermissionError("nope"))):
            with pytest.raises(PermissionError, match="nope"):
                await tool.run("get_events", agent_id="a-1", user_id="u-1")

    async def test_execute_generic_error(self):
        tool = await self._tool()
        with patch.object(tool, "_check_calendar_permission",
                          AsyncMock(return_value=(True, None))), \
             patch.object(tool, "_execute_action",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            res = await tool.run("get_events", agent_id="a-1", user_id="u-1")
        assert res["success"] is False and res["action"] == "get_events"

    async def test_write_action_supervised(self):
        tool = await self._tool()
        with patch.object(tool, "_check_calendar_permission",
                          AsyncMock(return_value=(True, None))) as check, \
             patch.object(tool, "_execute_action",
                          AsyncMock(return_value={"success": True, "event": {"id": "e1"}})):
            res = await tool.run("create_event", agent_id="a-1", user_id="u-1",
                                 title="T", start_time="x", end_time="y")
        assert res["success"] is True
        assert check.await_args.kwargs["required_maturity"] == "SUPERVISED"


class TestCalendarExecuteAction:
    @pytest.fixture(autouse=True)
    def _svc(self):
        self.svc = MagicMock()
        self.svc.authenticate.return_value = True
        self.svc.get_events = AsyncMock(return_value=[{"summary": "m"}])
        self.svc.check_conflicts = AsyncMock(return_value={"success": True, "conflicts": []})
        self.svc.create_event = AsyncMock(return_value={"id": "e1"})
        self.svc.update_event = AsyncMock(return_value={"id": "e1"})
        self.svc.delete_event = AsyncMock(return_value=True)
        with patch("tools.calendar_tool.google_calendar_service", self.svc):
            yield

    async def _execute(self, action, **kwargs):
        from tools.calendar_tool import CalendarTool
        return await CalendarTool()._execute_action(action, "u-1", **kwargs)

    async def test_not_authenticated(self):
        self.svc.authenticate.return_value = False
        res = await self._execute("get_events")
        assert res["success"] is False and "not authenticated" in res["error"]

    async def test_get_events_with_times(self):
        res = await self._execute("get_events", time_min="2026-08-01T00:00:00",
                                  time_max="2026-08-08T00:00:00", max_results=5)
        assert res["success"] is True and res["count"] == 1
        assert self.svc.get_events.await_args.kwargs["max_results"] == 5

    async def test_get_events_default_times(self):
        res = await self._execute("get_events")
        assert res["success"] is True
        kwargs = self.svc.get_events.await_args.kwargs
        assert isinstance(kwargs["time_min"], datetime)
        assert kwargs["time_max"] - kwargs["time_min"] == timedelta(days=7)

    async def test_check_conflicts_missing_params(self):
        res = await self._execute("check_conflicts")
        assert res["success"] is False and "start_time" in res["error"]

    async def test_check_conflicts_success(self):
        res = await self._execute("check_conflicts", start_time="2026-08-01T09:00:00",
                                  end_time="2026-08-01T10:00:00")
        assert res["success"] is True and res["action"] == "check_conflicts"

    async def test_create_event_missing_params(self):
        res = await self._execute("create_event", title="T")
        assert res["success"] is False and "title" in res["error"]

    async def test_create_event_success(self):
        res = await self._execute("create_event", title="T", start_time="2026-08-01T09:00:00",
                                  end_time="2026-08-01T10:00:00", description="d",
                                  location="l", attendees=["a@b.c"])
        assert res["success"] is True and res["event"] == {"id": "e1"}
        payload = self.svc.create_event.await_args.args[0]
        assert payload["attendees"] == ["a@b.c"]

    async def test_create_event_none(self):
        self.svc.create_event.return_value = None
        res = await self._execute("create_event", title="T", start_time="2026-08-01T09:00:00",
                                  end_time="2026-08-01T10:00:00")
        assert res["success"] is False and "Failed to create" in res["error"]

    async def test_update_event_missing_params(self):
        res = await self._execute("update_event", event_id="e1")
        assert res["success"] is False and "updates" in res["error"]

    async def test_update_event_success(self):
        res = await self._execute("update_event", event_id="e1", updates={"title": "New"})
        assert res["success"] is True and res["event"] == {"id": "e1"}

    async def test_update_event_none(self):
        self.svc.update_event.return_value = None
        res = await self._execute("update_event", event_id="e1", updates={"title": "New"})
        assert res["success"] is False and "Failed to update" in res["error"]

    async def test_delete_event_missing(self):
        res = await self._execute("delete_event")
        assert res["success"] is False and "event_id" in res["error"]

    async def test_delete_event_success(self):
        res = await self._execute("delete_event", event_id="e1")
        assert res["success"] is True and res["event_id"] == "e1"

    async def test_delete_event_failed(self):
        self.svc.delete_event.return_value = False
        res = await self._execute("delete_event", event_id="e1")
        assert res["success"] is False

    async def test_unknown_action(self):
        res = await self._execute("nope")
        assert res["success"] is False and "Unknown action" in res["error"]
        assert res["available_actions"] == [
            "get_events", "check_conflicts", "create_event", "update_event", "delete_event"]


class TestCalendarRegister:
    @pytest.fixture(autouse=True)
    def _svc(self):
        self.svc = MagicMock()
        self.svc.authenticate.return_value = True
        with patch("tools.calendar_tool.google_calendar_service", self.svc):
            yield

    def test_register_with_registry(self):
        from tools.calendar_tool import register_calendar_tool
        registry = MagicMock()
        tool = register_calendar_tool(registry)
        assert tool is not None
        registry.register.assert_called_once()
        assert registry.register.call_args.kwargs["name"] == "calendar_tool"

    def test_register_default_registry(self):
        from tools.calendar_tool import register_calendar_tool
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            register_calendar_tool()
        registry.register.assert_called_once()


# ============================================================================
# tools/data_analysis_tool.py
# ============================================================================

class TestValidateDataCode:
    def test_clean_code(self):
        from tools.data_analysis_tool import _validate_data_code
        assert _validate_data_code("df['a'] = df['b'] + 1") is None

    def test_forbidden_import(self):
        from tools.data_analysis_tool import _validate_data_code
        err = _validate_data_code("import os")
        assert err and "Forbidden import" in err

    def test_syntax_error(self):
        from tools.data_analysis_tool import _validate_data_code
        err = _validate_data_code("def broken(:")
        assert err and err.startswith("Syntax error")

    def test_dunder_attribute(self):
        from tools.data_analysis_tool import _validate_data_code
        err = _validate_data_code("x = obj.__class__")
        assert err and "dunder" in err

    def test_getattr_call(self):
        from tools.data_analysis_tool import _validate_data_code
        err = _validate_data_code("x = getattr(obj, 'attr')")
        assert err and "getattr()" in err

    def test_getattr_attribute_call(self):
        from tools.data_analysis_tool import _validate_data_code
        err = _validate_data_code("x = some_mod.getattr(obj)")
        assert err and "Reflection" in err

    def test_getattribute_attribute_call(self):
        from tools.data_analysis_tool import _validate_data_code
        err = _validate_data_code("x = obj.__getattribute__('y')")
        assert err and "Reflection" in err


class TestValidateIdentifier:
    def test_non_string(self):
        from tools.data_analysis_tool import _validate_identifier
        assert _validate_identifier(123, "target_column")
        assert _validate_identifier(None, "target_column")

    def test_invalid_regex(self):
        from tools.data_analysis_tool import _validate_identifier
        assert _validate_identifier("9abc", "target_column")
        assert _validate_identifier("a b", "target_column")
        assert _validate_identifier("a.b", "target_column")

    def test_valid(self):
        from tools.data_analysis_tool import _validate_identifier
        assert _validate_identifier("sales_q3", "target_column") is None
        assert _validate_identifier("_x1", "target_column") is None


class TestDataTools:
    def _patch_dm(self, **attrs):
        dm = MagicMock()
        for k, v in attrs.items():
            setattr(dm, k, v)
        return patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), dm

    async def test_load_dataset_success(self):
        handle = SimpleNamespace(to_dict=lambda: {"name": "d"}, row_count=10,
                                 columns=["a", "b"])
        dm = MagicMock()
        dm.load.return_value = handle
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import load_dataset
            res = await load_dataset("data.csv", "d", format="csv", session_id="s1")
        assert res["success"] is True and res["dataset"] == {"name": "d"}
        assert "10 rows" in res["message"]
        dm.load.assert_called_with(source="data.csv", name="d", session_id="s1", format="csv")

    async def test_load_dataset_failure(self):
        dm = MagicMock()
        dm.load.side_effect = RuntimeError("bad file")
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import load_dataset
            res = await load_dataset("data.csv", "d")
        assert res["success"] is False

    async def test_analyze_dataset_not_loaded(self):
        dm = MagicMock()
        dm.get_dataframe.return_value = None
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("missing", "print('x')")
        assert res["success"] is False and "not loaded" in res["error"]

    async def test_analyze_code_blocked(self):
        df = MagicMock()
        dm = MagicMock()
        dm.get_dataframe.return_value = df
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("d", "import os")
        assert res["success"] is False and "Code blocked" in res["error"]

    async def test_analyze_sandbox_success_json(self):
        df = MagicMock()
        df.to_json.return_value = '[{"a": 1}]'
        result = SimpleNamespace(success=True, stdout='{"mean": 1.5}',
                                 stderr="", exit_code=0)
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=result)
        dm = MagicMock()
        dm.get_dataframe.return_value = df
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", return_value=runtime), \
             patch("core.sandbox_policy.SandboxPolicy") as sp_cls:
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("d", "print('x')", agent_id="a-1")
        assert res == {"success": True, "results": {"mean": 1.5}}
        sp_cls.assert_called_once_with(run_id="data_analysis_d", agent_id="a-1",
                                       tier_at_issuance="STUDENT", max_exec_seconds=30)
        assert "__inputs__['df']" in runtime.execute_python.await_args.args[0]
        assert runtime.execute_python.await_args.kwargs["inputs"] == {"df": '[{"a": 1}]'}

    async def test_analyze_sandbox_success_plain_output(self):
        df = MagicMock()
        df.to_json.return_value = "[]"
        result = SimpleNamespace(success=True, stdout="hello world output",
                                 stderr="", exit_code=0)
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=result)
        dm = MagicMock()
        dm.get_dataframe.return_value = df
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", return_value=runtime), \
             patch("core.sandbox_policy.SandboxPolicy"):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("d", "print('hello')")
        assert res == {"success": True, "output": "hello world output"}

    async def test_analyze_sandbox_unavailable_exit(self):
        df = MagicMock()
        df.to_json.return_value = "[]"
        result = SimpleNamespace(success=False, stdout="", stderr="docker down",
                                 exit_code=-1)
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=result)
        dm = MagicMock()
        dm.get_dataframe.return_value = df
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", return_value=runtime), \
             patch("core.sandbox_policy.SandboxPolicy"):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("d", "print(1)")
        assert res["success"] is False and "sandbox" in res["error"].lower()

    async def test_analyze_sandbox_exec_failure(self):
        df = MagicMock()
        df.to_json.return_value = "[]"
        result = SimpleNamespace(success=False, stdout="trace", stderr="NameError: x",
                                 exit_code=1)
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=result)
        dm = MagicMock()
        dm.get_dataframe.return_value = df
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", return_value=runtime), \
             patch("core.sandbox_policy.SandboxPolicy"):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("d", "print(1)")
        assert res["success"] is False and "NameError" in res["error"]

    async def test_analyze_sandbox_exec_failure_no_stderr(self):
        df = MagicMock()
        df.to_json.return_value = "[]"
        result = SimpleNamespace(success=False, stdout="", stderr="", exit_code=1)
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=result)
        dm = MagicMock()
        dm.get_dataframe.return_value = df
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", return_value=runtime), \
             patch("core.sandbox_policy.SandboxPolicy"):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("d", "print(1)")
        assert res["success"] is False and res["error"] == "Execution failed"

    async def test_analyze_sandbox_runtime_exception_fail_closed(self):
        df = MagicMock()
        df.to_json.return_value = "[]"
        dm = MagicMock()
        dm.get_dataframe.return_value = df
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", side_effect=RuntimeError("no runtime")), \
             patch("core.sandbox_policy.SandboxPolicy"):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("d", "print(1)")
        assert res["success"] is False and "sandbox" in res["error"].lower()

    async def test_analyze_outer_failure(self):
        dm = MagicMock()
        dm.get_dataframe.side_effect = RuntimeError("boom")
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("d", "print(1)")
        assert res["success"] is False

    async def test_query_data_success(self):
        dm = MagicMock()
        dm.query.return_value = {"success": True, "data": [{"a": 1}]}
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import query_data
            res = await query_data("d", "SELECT * FROM df", session_id="s1")
        assert res["success"] is True
        dm.query.assert_called_with("d", "SELECT * FROM df", session_id="s1")

    async def test_query_data_failure(self):
        dm = MagicMock()
        dm.query.side_effect = RuntimeError("boom")
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import query_data
            res = await query_data("d", "SELECT 1")
        assert res["success"] is False

    async def test_describe_data_success(self):
        dm = MagicMock()
        dm.describe.return_value = {"success": True, "stats": {}}
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import describe_data
            res = await describe_data("d", session_id="s1")
        assert res["success"] is True
        dm.describe.assert_called_with("d", session_id="s1")

    async def test_describe_data_failure(self):
        dm = MagicMock()
        dm.describe.side_effect = RuntimeError("boom")
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import describe_data
            res = await describe_data("d")
        assert res["success"] is False

    async def test_list_datasets_success(self):
        dm = MagicMock()
        dm.list_datasets.return_value = [{"name": "d"}]
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import list_datasets
            res = await list_datasets(session_id="s1")
        assert res["success"] is True and res["count"] == 1

    async def test_list_datasets_failure(self):
        dm = MagicMock()
        dm.list_datasets.side_effect = RuntimeError("boom")
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import list_datasets
            res = await list_datasets()
        assert res["success"] is False


class TestRegisterDataTools:
    def test_register_with_registry(self):
        import tools.data_analysis_tool  # noqa: F401
        from tools.data_analysis_tool import register_data_analysis_tools
        registry = MagicMock()
        register_data_analysis_tools(registry)
        names = [c.kwargs["name"] for c in registry.register.call_args_list]
        assert names == ["load_dataset", "analyze_data", "query_data", "describe_data", "list_datasets"]

    def test_register_default_registry(self):
        from tools.data_analysis_tool import register_data_analysis_tools
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            register_data_analysis_tools()
        assert registry.register.call_count == 5


# ============================================================================
# tools/media_tool.py
# ============================================================================

class TestMediaGovernance:
    async def test_human_allowed(self):
        from tools.media_tool import _check_media_governance
        res = await _check_media_governance(Mock(), None, "spotify_play", "u-1")
        assert res["allowed"] is True and res["governance_check_passed"] is True

    async def test_agent_not_found_defaults_student(self):
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = None
        from tools.media_tool import _check_media_governance
        res = await _check_media_governance(q, "a-1", "spotify_play", "u-1")
        assert res["allowed"] is False and "STUDENT" in res["reason"]

    async def test_student_insufficient(self):
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            status="STUDENT")
        from tools.media_tool import _check_media_governance
        res = await _check_media_governance(q, "a-1", "sonos_play", "u-1")
        assert res["allowed"] is False and "insufficient" in res["reason"]

    async def test_unknown_action_defaults_supervised(self):
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            status="INTERN")
        from tools.media_tool import _check_media_governance
        res = await _check_media_governance(q, "a-1", "some_new_action", "u-1")
        assert res["allowed"] is False

    async def test_intern_readonly_hierarchy_passes(self):
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            status="INTERN")
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"allowed": True, "reason": "ok"})
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov):
            from tools.media_tool import _check_media_governance
            res = await _check_media_governance(q, "a-1", "spotify_devices", "u-1")
        assert res["allowed"] is True and res["maturity_level"] == "INTERN"

    async def test_governance_denied(self):
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            status="AUTONOMOUS")
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "budget exhausted"})
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov):
            from tools.media_tool import _check_media_governance
            res = await _check_media_governance(q, "a-1", "spotify_play", "u-1")
        assert res["allowed"] is False and "budget" in res["reason"]

    async def test_governance_agent_not_found_falls_through(self):
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            status="AUTONOMOUS")
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(
            return_value={"allowed": False, "reason": "Agent not found"})
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov):
            from tools.media_tool import _check_media_governance
            res = await _check_media_governance(q, "a-1", "spotify_play", "u-1")
        assert res["allowed"] is True

    async def test_governance_allowed(self):
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            status="AUTONOMOUS")
        gov = MagicMock()
        gov.can_perform_action_async = AsyncMock(return_value={"allowed": True})
        with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov):
            from tools.media_tool import _check_media_governance
            res = await _check_media_governance(q, "a-1", "spotify_play", "u-1")
        assert res["allowed"] is True and res["governance_check_passed"] is True

    async def test_exception_fail_closed_agent(self):
        q = MagicMock()
        q.query.side_effect = RuntimeError("db down")
        from tools.media_tool import _check_media_governance
        res = await _check_media_governance(q, "a-1", "spotify_play", "u-1")
        assert res["allowed"] is False and "Governance check error" in res["reason"]


class TestMediaSpotify:
    @pytest.fixture(autouse=True)
    def _spotify(self):
        self.svc = MagicMock()
        self.svc.get_current_track = AsyncMock(return_value={"success": True})
        self.svc.play_track = AsyncMock(return_value={"success": True})
        self.svc.pause_playback = AsyncMock(return_value={"success": True})
        self.svc.skip_next = AsyncMock(return_value={"success": True})
        self.svc.skip_previous = AsyncMock(return_value={"success": True})
        self.svc.set_volume = AsyncMock(return_value={"success": True})
        self.svc.get_available_devices = AsyncMock(return_value={"success": True})
        with patch("tools.media_tool.SpotifyService", return_value=self.svc):
            yield

    async def _run(self, fn, **kwargs):
        return await fn(Mock(), "u-1", **kwargs)

    async def test_all_success(self):
        from tools.media_tool import (spotify_current, spotify_devices, spotify_next,
                                      spotify_pause, spotify_play, spotify_previous,
                                      spotify_volume)
        assert (await self._run(spotify_current))["success"] is True
        assert (await self._run(spotify_play, track_uri="x", device_id="d"))["success"] is True
        assert (await self._run(spotify_pause))["success"] is True
        assert (await self._run(spotify_next))["success"] is True
        assert (await self._run(spotify_previous))["success"] is True
        assert (await self._run(spotify_volume, volume_percent=40))["success"] is True
        assert (await self._run(spotify_devices))["success"] is True

    async def test_all_service_exceptions(self):
        from tools.media_tool import (spotify_current, spotify_devices, spotify_next,
                                      spotify_pause, spotify_play, spotify_previous,
                                      spotify_volume)
        self.svc.get_current_track.side_effect = RuntimeError("x")
        self.svc.play_track.side_effect = RuntimeError("x")
        self.svc.pause_playback.side_effect = RuntimeError("x")
        self.svc.skip_next.side_effect = RuntimeError("x")
        self.svc.skip_previous.side_effect = RuntimeError("x")
        self.svc.set_volume.side_effect = RuntimeError("x")
        self.svc.get_available_devices.side_effect = RuntimeError("x")
        for fn, kw in [(spotify_current, {}), (spotify_play, {}), (spotify_pause, {}),
                       (spotify_next, {}), (spotify_previous, {}),
                       (spotify_volume, {"volume_percent": 10}), (spotify_devices, {})]:
            res = await self._run(fn, **kw)
            assert res["success"] is False and "x" in res["error"]

    async def test_all_blocked(self):
        with patch("tools.media_tool._check_media_governance",
                   AsyncMock(return_value={"allowed": False, "reason": "no"})):
            from tools.media_tool import (spotify_current, spotify_devices, spotify_next,
                                          spotify_pause, spotify_play, spotify_previous,
                                          spotify_volume)
            for fn, kw in [(spotify_current, {}), (spotify_play, {}), (spotify_pause, {}),
                           (spotify_next, {}), (spotify_previous, {}),
                           (spotify_volume, {"volume_percent": 10}), (spotify_devices, {})]:
                res = await self._run(fn, **kw)
                assert res["success"] is False and res["governance_blocked"] is True


class TestMediaSonos:
    @pytest.fixture(autouse=True)
    def _sonos(self):
        self.svc = MagicMock()
        self.svc.discover_speakers = AsyncMock(return_value=[{"ip": "1.2.3.4"}])
        self.svc.play = AsyncMock(return_value={"success": True})
        self.svc.pause = AsyncMock(return_value={"success": True})
        self.svc.set_volume = AsyncMock(return_value={"success": True})
        self.svc.get_groups = AsyncMock(return_value=[{"id": "g1"}])
        with patch("tools.media_tool.SonosService", return_value=self.svc):
            yield

    async def test_all_success(self):
        from tools.media_tool import sonos_discover, sonos_groups, sonos_pause, sonos_play, sonos_volume
        res = await sonos_discover(Mock())
        assert res["success"] is True and res["count"] == 1
        assert (await sonos_play(Mock(), "1.2.3.4"))["success"] is True
        assert (await sonos_pause(Mock(), "1.2.3.4"))["success"] is True
        assert (await sonos_volume(Mock(), "1.2.3.4", 30))["success"] is True
        res = await sonos_groups(Mock())
        assert res["success"] is True and res["count"] == 1

    async def test_all_service_exceptions(self):
        from tools.media_tool import sonos_discover, sonos_groups, sonos_pause, sonos_play, sonos_volume
        self.svc.discover_speakers.side_effect = RuntimeError("x")
        self.svc.play.side_effect = RuntimeError("x")
        self.svc.pause.side_effect = RuntimeError("x")
        self.svc.set_volume.side_effect = RuntimeError("x")
        self.svc.get_groups.side_effect = RuntimeError("x")
        assert (await sonos_discover(Mock()))["success"] is False
        assert (await sonos_play(Mock(), "1.2.3.4"))["success"] is False
        assert (await sonos_pause(Mock(), "1.2.3.4"))["success"] is False
        assert (await sonos_volume(Mock(), "1.2.3.4", 30))["success"] is False
        assert (await sonos_groups(Mock()))["success"] is False

    async def test_all_blocked(self):
        with patch("tools.media_tool._check_media_governance",
                   AsyncMock(return_value={"allowed": False, "reason": "no"})):
            from tools.media_tool import (sonos_discover, sonos_groups, sonos_pause,
                                          sonos_play, sonos_volume)
            assert (await sonos_discover(Mock()))["governance_blocked"] is True
            assert (await sonos_play(Mock(), "1.2.3.4"))["governance_blocked"] is True
            assert (await sonos_pause(Mock(), "1.2.3.4"))["governance_blocked"] is True
            assert (await sonos_volume(Mock(), "1.2.3.4", 30))["governance_blocked"] is True
            assert (await sonos_groups(Mock()))["governance_blocked"] is True


class TestMediaRegister:
    def test_register_media_tools(self):
        import tools.media_tool  # noqa: F401 - import first so auto-register runs unpatched
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            from tools.media_tool import register_media_tools
            register_media_tools()
        names = [c.kwargs["name"] for c in registry.register.call_args_list]
        assert len(names) == 12
        assert names[0] == "spotify_current" and names[-1] == "sonos_groups"

    def test_auto_register_failure(self):
        with patch("tools.registry.get_tool_registry", side_effect=RuntimeError("boom")):
            mod = importlib.reload(sys.modules["tools.media_tool"])
        assert mod is not None


# ============================================================================
# tools/productivity_tool.py (Notion)
# ============================================================================

class TestNotionPermission:
    async def _tool(self):
        from tools.productivity_tool import NotionTool
        return NotionTool()

    async def test_no_agent_allowed(self):
        tool = await self._tool()
        ok, reason = await tool._check_notion_permission(None, "u-1", "search", "INTERN")
        assert ok is True and reason is None

    async def test_cached(self):
        tool = await self._tool()
        with patch("tools.productivity_tool._governance_cache") as cache:
            cache.get.return_value = {"allowed": False, "reason": "cached"}
            ok, reason = await tool._check_notion_permission("a-1", "u-1", "search", "INTERN")
        assert ok is False and reason == "cached"

    async def test_with_db_param_allowed(self):
        tool = await self._tool()
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="AUTONOMOUS")
        with patch("tools.productivity_tool._governance_cache") as cache, \
             patch("core.privsec.local_only_guard.LocalOnlyGuard"):
            cache.get.return_value = None
            ok, reason = await tool._check_notion_permission("a-1", "u-1", "create_page", "SUPERVISED", db=q)
        assert ok is True and reason is None

    async def test_db_none_uses_session(self):
        tool = await self._tool()
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="INTERN")
        with patch("tools.productivity_tool._governance_cache") as cache, \
             _patch_tool_db("productivity_tool", q), \
             patch("core.privsec.local_only_guard.LocalOnlyGuard"):
            cache.get.return_value = None
            ok, _ = await tool._check_notion_permission("a-1", "u-1", "search", "INTERN")
        assert ok is True

    async def test_agent_not_found(self):
        tool = await self._tool()
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = None
        with patch("tools.productivity_tool._governance_cache") as cache, \
                _patch_tool_db("productivity_tool", q):
            cache.get.return_value = None
            ok, reason = await tool._check_notion_permission("a-1", "u-1", "search", "INTERN")
        assert ok is False and "not found" in reason

    async def test_invalid_maturity(self):
        tool = await self._tool()
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="BOGUS")
        with patch("tools.productivity_tool._governance_cache") as cache, \
                _patch_tool_db("productivity_tool", q):
            cache.get.return_value = None
            ok, reason = await tool._check_notion_permission("a-1", "u-1", "search", "INTERN")
        assert ok is False and "Invalid maturity" in reason

    async def test_denied_reason(self):
        tool = await self._tool()
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="STUDENT")
        with patch("tools.productivity_tool._governance_cache") as cache, \
                _patch_tool_db("productivity_tool", q):
            cache.get.return_value = None
            ok, reason = await tool._check_notion_permission("a-1", "u-1", "create_page", "SUPERVISED", db=q)
        assert ok is False and "SUPERVISED" in reason

    async def test_local_only_blocked(self):
        tool = await self._tool()
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="AUTONOMOUS")
        guard = MagicMock()
        guard.allow_external_request.side_effect = RuntimeError("local-only mode")
        with patch("tools.productivity_tool._governance_cache") as cache, \
             patch("tools.productivity_tool.LocalOnlyGuard", return_value=guard):
            cache.get.return_value = None
            ok, reason = await tool._check_notion_permission("a-1", "u-1", "search", "INTERN", db=q)
        assert ok is False and "local-only" in reason

    async def test_permission_exception(self):
        tool = await self._tool()
        with patch("tools.productivity_tool._governance_cache") as cache, \
                patch("tools.productivity_tool.get_db_session", side_effect=RuntimeError("db")):
            cache.get.return_value = None
            ok, reason = await tool._check_notion_permission("a-1", "u-1", "search", "INTERN")
        assert ok is False and "Permission check failed" in reason


class TestNotionRun:
    async def _tool(self):
        from tools.productivity_tool import NotionTool
        return NotionTool()

    async def test_unknown_action(self):
        tool = await self._tool()
        res = await tool.run("explode")
        assert res["success"] is False and "Unknown action" in res["error"]

    async def test_permission_denied_dict(self):
        tool = await self._tool()
        with patch.object(tool, "_check_notion_permission", AsyncMock(return_value=(False, "no"))):
            res = await tool.run("search", agent_id="a-1", query="x")
        assert res["success"] is False and res["error"] == "no"

    async def test_success(self):
        tool = await self._tool()
        with patch.object(tool, "_check_notion_permission", AsyncMock(return_value=(True, None))), \
             patch.object(tool, "_execute_action", AsyncMock(return_value={"success": True})):
            res = await tool.run("search", agent_id="a-1", query="x")
        assert res["success"] is True

    async def test_permission_error_handled(self):
        tool = await self._tool()
        with patch.object(tool, "_check_notion_permission", AsyncMock(return_value=(True, None))), \
             patch.object(tool, "_execute_action", AsyncMock(side_effect=PermissionError("no"))):
            res = await tool.run("search", agent_id="a-1", query="x")
        assert res["success"] is False and "no" in res["error"]

    async def test_generic_exception(self):
        tool = await self._tool()
        with patch.object(tool, "_check_notion_permission", AsyncMock(return_value=(True, None))), \
             patch.object(tool, "_execute_action", AsyncMock(side_effect=RuntimeError("boom"))):
            res = await tool.run("search", agent_id="a-1", query="x")
        assert res["success"] is False and "boom" in res["error"]

    async def test_write_action_supervised(self):
        tool = await self._tool()
        with patch.object(tool, "_check_notion_permission",
                          AsyncMock(return_value=(True, None))) as check, \
             patch.object(tool, "_execute_action",
                          AsyncMock(return_value={"success": True, "page": {"id": "p1"}})):
            res = await tool.run("create_page", agent_id="a-1", user_id="u-1",
                                 database_id="db1", properties={"Name": "x"})
        assert res["success"] is True
        assert check.await_args.kwargs["required_maturity"] == "SUPERVISED"


class TestNotionExecute:
    @pytest.fixture(autouse=True)
    def _svc(self):
        self.svc = MagicMock()
        self.svc.search_workspace = AsyncMock(return_value=[{"id": "p1"}])
        self.svc.list_databases = AsyncMock(return_value=[{"id": "db1"}])
        self.svc.query_database = AsyncMock(return_value=[{"id": "p1"}])
        self.svc.get_database_schema = AsyncMock(return_value={"properties": {}})
        self.svc.get_page = AsyncMock(return_value={"id": "p1"})
        self.svc.get_page_blocks = AsyncMock(return_value=[{"type": "paragraph"}])
        self.svc.create_page = AsyncMock(return_value={"id": "p1"})
        self.svc.update_page = AsyncMock(return_value={"id": "p1"})
        self.svc.append_page_blocks = AsyncMock(return_value={"ok": True})
        with patch("tools.productivity_tool.NotionService", return_value=self.svc):
            yield

    async def _execute(self, action, **kwargs):
        from tools.productivity_tool import NotionTool
        return await NotionTool()._execute_action(action, "u-1", **kwargs)

    async def test_search_no_query(self):
        res = await self._execute("search")
        assert res["success"] is False and "Query parameter required" in res["error"]

    async def test_search_success(self):
        res = await self._execute("search", query="alpha")
        assert res["success"] is True and res["count"] == 1
        self.svc.search_workspace.assert_awaited_with("alpha")

    async def test_list_databases(self):
        res = await self._execute("list_databases")
        assert res["success"] is True and res["count"] == 1

    async def test_query_database_missing_id(self):
        res = await self._execute("query_database")
        assert res["success"] is False and "database_id" in res["error"]

    async def test_query_database_filter_str(self):
        res = await self._execute("query_database", database_id="db1",
                                  filter='{"property": "Status"}')
        assert res["success"] is True
        self.svc.query_database.assert_awaited_with("db1", {"property": "Status"})

    async def test_query_database_filter_bad_json(self):
        res = await self._execute("query_database", database_id="db1", filter="{bad")
        assert res["success"] is False and "Invalid filter JSON" in res["error"]

    async def test_query_database_filter_dict(self):
        res = await self._execute("query_database", database_id="db1",
                                  filter={"property": "Status"})
        assert res["success"] is True

    async def test_get_schema_missing_id(self):
        res = await self._execute("get_schema")
        assert res["success"] is False and "database_id" in res["error"]

    async def test_get_schema_success(self):
        res = await self._execute("get_schema", database_id="db1")
        assert res["success"] is True and res["schema"] == {"properties": {}}

    async def test_get_page_missing(self):
        res = await self._execute("get_page")
        assert res["success"] is False and "page_id" in res["error"]

    async def test_get_page_success(self):
        res = await self._execute("get_page", page_id="p1")
        assert res["success"] is True and res["page"] == {"id": "p1"}

    async def test_get_blocks_missing(self):
        res = await self._execute("get_blocks")
        assert res["success"] is False and "page_id" in res["error"]

    async def test_get_blocks_success(self):
        res = await self._execute("get_blocks", page_id="p1")
        assert res["success"] is True and res["count"] == 1

    async def test_create_page_missing_db(self):
        res = await self._execute("create_page", properties={"a": 1})
        assert res["success"] is False and "database_id" in res["error"]

    async def test_create_page_missing_props(self):
        res = await self._execute("create_page", database_id="db1")
        assert res["success"] is False and "properties" in res["error"]

    async def test_create_page_props_str(self):
        res = await self._execute("create_page", database_id="db1",
                                  properties='{"Name": "x"}')
        assert res["success"] is True
        self.svc.create_page.assert_awaited_with("db1", {"Name": "x"})

    async def test_create_page_props_bad_json(self):
        res = await self._execute("create_page", database_id="db1", properties="{bad")
        assert res["success"] is False and "Invalid properties JSON" in res["error"]

    async def test_create_page_props_dict(self):
        res = await self._execute("create_page", database_id="db1", properties={"Name": "x"})
        assert res["success"] is True

    async def test_update_page_missing_page(self):
        res = await self._execute("update_page", properties={"a": 1})
        assert res["success"] is False and "page_id" in res["error"]

    async def test_update_page_missing_props(self):
        res = await self._execute("update_page", page_id="p1")
        assert res["success"] is False and "properties" in res["error"]

    async def test_update_page_props_str(self):
        res = await self._execute("update_page", page_id="p1", properties='{"Done": true}')
        assert res["success"] is True
        self.svc.update_page.assert_awaited_with("p1", {"Done": True})

    async def test_update_page_props_bad_json(self):
        res = await self._execute("update_page", page_id="p1", properties="{bad")
        assert res["success"] is False and "Invalid properties JSON" in res["error"]

    async def test_update_page_props_dict(self):
        res = await self._execute("update_page", page_id="p1", properties={"Done": True})
        assert res["success"] is True

    async def test_append_blocks_missing_page(self):
        res = await self._execute("append_blocks", blocks=[{"type": "p"}])
        assert res["success"] is False and "page_id" in res["error"]

    async def test_append_blocks_missing_blocks(self):
        res = await self._execute("append_blocks", page_id="p1")
        assert res["success"] is False and "blocks" in res["error"]

    async def test_append_blocks_str(self):
        res = await self._execute("append_blocks", page_id="p1", blocks='[{"type": "p"}]')
        assert res["success"] is True
        self.svc.append_page_blocks.assert_awaited_with("p1", [{"type": "p"}])

    async def test_append_blocks_bad_json(self):
        res = await self._execute("append_blocks", page_id="p1", blocks="[bad")
        assert res["success"] is False and "Invalid blocks JSON" in res["error"]

    async def test_append_blocks_list(self):
        res = await self._execute("append_blocks", page_id="p1", blocks=[{"type": "p"}])
        assert res["success"] is True

    async def test_unknown_action(self):
        res = await self._execute("nope")
        assert res["success"] is False and "Unknown action" in res["error"]


class TestRegisterNotion:
    def test_register_with_registry(self):
        import tools.productivity_tool  # noqa: F401
        from tools.productivity_tool import register_notion_tool
        registry = MagicMock()
        tool = register_notion_tool(registry)
        assert tool is not None
        registry.register.assert_called_once()
        assert registry.register.call_args.kwargs["name"] == "notion_tool"

    def test_register_default_registry(self):
        from tools.productivity_tool import register_notion_tool
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            register_notion_tool()
        registry.register.assert_called_once()


# ============================================================================
# tools/smarthome_tool.py
# ============================================================================

class TestHuePermission:
    @pytest.fixture(autouse=True)
    def _flags(self):
        with patch("tools.smarthome_tool.FeatureFlags",
                   SimpleNamespace(SMART_HOME_CONTROL_ENABLED=True)):
            yield

    async def test_flag_disabled(self):
        from tools.smarthome_tool import _check_hue_permission
        with patch("tools.smarthome_tool.FeatureFlags",
                   SimpleNamespace(SMART_HOME_CONTROL_ENABLED=False)):
            ok, reason = await _check_hue_permission("a-1", "u-1")
        assert ok is False and "disabled" in reason

    async def test_no_agent(self):
        from tools.smarthome_tool import _check_hue_permission
        assert await _check_hue_permission(None, "u-1") == (True, None)

    async def test_cached(self):
        from tools.smarthome_tool import _check_hue_permission
        with patch("tools.smarthome_tool._governance_cache") as cache:
            cache.get.return_value = {"allowed": True, "reason": None}
            assert await _check_hue_permission("a-1", "u-1") == (True, None)

    async def test_agent_not_found(self):
        from tools.smarthome_tool import _check_hue_permission
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = None
        with patch("tools.smarthome_tool._governance_cache") as cache, \
                _patch_tool_db("smarthome_tool", q):
            cache.get.return_value = None
            ok, reason = await _check_hue_permission("a-1", "u-1")
        assert ok is False and "not found" in reason

    async def test_denied(self):
        from tools.smarthome_tool import _check_hue_permission
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="STUDENT")
        with patch("tools.smarthome_tool._governance_cache") as cache, \
                _patch_tool_db("smarthome_tool", q):
            cache.get.return_value = None
            cache.set = Mock()
            ok, reason = await _check_hue_permission("a-1", "u-1")
        assert ok is False and "SUPERVISED" in reason

    async def test_allowed(self):
        from tools.smarthome_tool import _check_hue_permission
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="AUTONOMOUS")
        with patch("tools.smarthome_tool._governance_cache") as cache, \
                _patch_tool_db("smarthome_tool", q):
            cache.get.return_value = None
            assert await _check_hue_permission("a-1", "u-1") == (True, None)

    async def test_exception(self):
        from tools.smarthome_tool import _check_hue_permission
        with patch("tools.smarthome_tool._governance_cache") as cache, \
                patch("tools.smarthome_tool.get_db_session", side_effect=RuntimeError("db")):
            cache.get.return_value = None
            ok, reason = await _check_hue_permission("a-1", "u-1")
        assert ok is False and "Permission check failed" in reason


class TestHomeAssistantPermission:
    @pytest.fixture(autouse=True)
    def _flags(self):
        with patch("tools.smarthome_tool.FeatureFlags",
                   SimpleNamespace(SMART_HOME_CONTROL_ENABLED=True)):
            yield

    async def test_flag_disabled(self):
        from tools.smarthome_tool import _check_home_assistant_permission
        with patch("tools.smarthome_tool.FeatureFlags",
                   SimpleNamespace(SMART_HOME_CONTROL_ENABLED=False)):
            ok, reason = await _check_home_assistant_permission("a-1", "u-1")
        assert ok is False and "disabled" in reason

    async def test_no_agent(self):
        from tools.smarthome_tool import _check_home_assistant_permission
        assert await _check_home_assistant_permission(None, "u-1") == (True, None)

    async def test_cached(self):
        from tools.smarthome_tool import _check_home_assistant_permission
        with patch("tools.smarthome_tool._governance_cache") as cache:
            cache.get.return_value = {"allowed": False, "reason": "cached"}
            ok, reason = await _check_home_assistant_permission("a-1", "u-1")
        assert ok is False and reason == "cached"

    async def test_agent_not_found(self):
        from tools.smarthome_tool import _check_home_assistant_permission
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = None
        with patch("tools.smarthome_tool._governance_cache") as cache, \
                _patch_tool_db("smarthome_tool", q):
            cache.get.return_value = None
            ok, reason = await _check_home_assistant_permission("a-1", "u-1")
        assert ok is False and "not found" in reason

    async def test_denied(self):
        from tools.smarthome_tool import _check_home_assistant_permission
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="INTERN")
        with patch("tools.smarthome_tool._governance_cache") as cache, \
                _patch_tool_db("smarthome_tool", q):
            cache.get.return_value = None
            ok, reason = await _check_home_assistant_permission("a-1", "u-1")
        assert ok is False and "SUPERVISED" in reason

    async def test_allowed(self):
        from tools.smarthome_tool import _check_home_assistant_permission
        q = MagicMock()
        q.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            maturity_level="SUPERVISED")
        with patch("tools.smarthome_tool._governance_cache") as cache, \
                _patch_tool_db("smarthome_tool", q):
            cache.get.return_value = None
            assert await _check_home_assistant_permission("a-1", "u-1") == (True, None)

    async def test_exception(self):
        from tools.smarthome_tool import _check_home_assistant_permission
        with patch("tools.smarthome_tool._governance_cache") as cache, \
                patch("tools.smarthome_tool.get_db_session", side_effect=RuntimeError("db")):
            cache.get.return_value = None
            ok, reason = await _check_home_assistant_permission("a-1", "u-1")
        assert ok is False and "Permission check failed" in reason


class TestHueTools:
    @pytest.fixture(autouse=True)
    def _hue(self):
        self.hue = MagicMock()
        self.hue.discover_bridges = AsyncMock(return_value=["192.168.1.2"])
        self.hue.get_all_lights = AsyncMock(return_value=[{"id": "1", "on": True}])
        self.hue.set_light_state = AsyncMock(return_value={"on": False})
        with patch("tools.smarthome_tool.HueService", return_value=self.hue):
            yield

    async def test_discover_success(self):
        from tools.smarthome_tool import hue_discover_bridges
        res = await hue_discover_bridges(agent_id=None, user_id="u-1")
        assert res["success"] is True and res["count"] == 1

    async def test_discover_default_user(self):
        from tools.smarthome_tool import hue_discover_bridges
        res = await hue_discover_bridges()
        assert res["success"] is True

    async def test_discover_failure(self):
        self.hue.discover_bridges.side_effect = RuntimeError("mDNS down")
        from tools.smarthome_tool import hue_discover_bridges
        res = await hue_discover_bridges()
        assert res["success"] is False and "mDNS down" in res["error"]

    async def test_discover_blocked(self):
        with patch("tools.smarthome_tool._check_hue_permission",
                   AsyncMock(return_value=(False, "blocked"))):
            from tools.smarthome_tool import hue_discover_bridges
            with pytest.raises(PermissionError, match="blocked"):
                await hue_discover_bridges(agent_id="a-1")

    async def test_get_lights_success(self):
        from tools.smarthome_tool import hue_get_lights
        res = await hue_get_lights(bridge_ip="192.168.1.2", api_key="k")
        assert res["success"] is True and res["count"] == 1

    async def test_get_lights_missing_params(self):
        from tools.smarthome_tool import hue_get_lights
        with pytest.raises(ValueError, match="bridge_ip and api_key"):
            await hue_get_lights(bridge_ip=None, api_key=None)

    async def test_get_lights_failure(self):
        self.hue.get_all_lights.side_effect = RuntimeError("no bridge")
        from tools.smarthome_tool import hue_get_lights
        res = await hue_get_lights(bridge_ip="192.168.1.2", api_key="k")
        assert res["success"] is False and "no bridge" in res["error"]

    async def test_get_lights_blocked(self):
        with patch("tools.smarthome_tool._check_hue_permission",
                   AsyncMock(return_value=(False, "blocked"))):
            from tools.smarthome_tool import hue_get_lights
            with pytest.raises(PermissionError, match="blocked"):
                await hue_get_lights(agent_id="a-1", bridge_ip="1.2.3.4", api_key="k")

    async def test_set_light_state_success(self):
        from tools.smarthome_tool import hue_set_light_state
        res = await hue_set_light_state(bridge_ip="192.168.1.2", api_key="k", light_id="1",
                                        on=False, brightness=50, color_xy=(0.5, 0.5))
        assert res["success"] is True
        self.hue.set_light_state.assert_awaited_once_with("192.168.1.2", "k", "1", False, 50, (0.5, 0.5))

    async def test_set_light_state_missing_params(self):
        from tools.smarthome_tool import hue_set_light_state
        with pytest.raises(ValueError, match="bridge_ip, api_key, and light_id"):
            await hue_set_light_state(bridge_ip="1.2.3.4", api_key=None, light_id=None)

    async def test_set_light_state_failure(self):
        self.hue.set_light_state.side_effect = RuntimeError("denied")
        from tools.smarthome_tool import hue_set_light_state
        res = await hue_set_light_state(bridge_ip="192.168.1.2", api_key="k", light_id="1")
        assert res["success"] is False and "denied" in res["error"]

    async def test_set_light_state_blocked(self):
        with patch("tools.smarthome_tool._check_hue_permission",
                   AsyncMock(return_value=(False, "blocked"))):
            from tools.smarthome_tool import hue_set_light_state
            with pytest.raises(PermissionError, match="blocked"):
                await hue_set_light_state(agent_id="a-1", bridge_ip="1.2.3.4", api_key="k",
                                          light_id="1")


class TestHomeAssistantTools:
    @pytest.fixture(autouse=True)
    def _ha(self):
        self.ha = MagicMock()
        self.ha.get_states = AsyncMock(return_value=[{"entity_id": "light.x"}])
        self.ha.call_service = AsyncMock(return_value={"ok": True})
        self.ha.get_lights = AsyncMock(return_value=[{"entity_id": "light.y"}])
        self.ha.close = AsyncMock()
        with patch("tools.smarthome_tool.HomeAssistantService", return_value=self.ha):
            yield

    async def test_get_states_success(self):
        from tools.smarthome_tool import home_assistant_get_states
        res = await home_assistant_get_states(ha_url="http://ha.local", ha_token="t")
        assert res["success"] is True and res["count"] == 1
        self.ha.close.assert_awaited_once()

    async def test_get_states_missing_params(self):
        from tools.smarthome_tool import home_assistant_get_states
        with pytest.raises(ValueError, match="ha_url and ha_token"):
            await home_assistant_get_states(ha_url=None, ha_token=None)

    async def test_get_states_failure(self):
        self.ha.get_states.side_effect = RuntimeError("unreachable")
        from tools.smarthome_tool import home_assistant_get_states
        res = await home_assistant_get_states(ha_url="http://ha.local", ha_token="t")
        assert res["success"] is False and "unreachable" in res["error"]

    async def test_get_states_blocked(self):
        with patch("tools.smarthome_tool._check_home_assistant_permission",
                   AsyncMock(return_value=(False, "blocked"))):
            from tools.smarthome_tool import home_assistant_get_states
            with pytest.raises(PermissionError, match="blocked"):
                await home_assistant_get_states(agent_id="a-1", ha_url="http://ha", ha_token="t")

    async def test_call_service_success(self):
        from tools.smarthome_tool import home_assistant_call_service
        res = await home_assistant_call_service(ha_url="http://ha.local", ha_token="t",
                                                domain="light", service="turn_on",
                                                entity_id="light.x", data={"brightness": 50})
        assert res["success"] is True
        self.ha.call_service.assert_awaited_once_with("light", "turn_on", "light.x", {"brightness": 50})
        self.ha.close.assert_awaited_once()

    async def test_call_service_missing_params(self):
        from tools.smarthome_tool import home_assistant_call_service
        with pytest.raises(ValueError, match="ha_url, ha_token, domain, and service"):
            await home_assistant_call_service(ha_url="http://ha", ha_token="t", domain=None, service=None)

    async def test_call_service_failure(self):
        self.ha.call_service.side_effect = RuntimeError("service error")
        from tools.smarthome_tool import home_assistant_call_service
        res = await home_assistant_call_service(ha_url="http://ha.local", ha_token="t",
                                                domain="light", service="turn_on")
        assert res["success"] is False and "service error" in res["error"]

    async def test_call_service_blocked(self):
        with patch("tools.smarthome_tool._check_home_assistant_permission",
                   AsyncMock(return_value=(False, "blocked"))):
            from tools.smarthome_tool import home_assistant_call_service
            with pytest.raises(PermissionError, match="blocked"):
                await home_assistant_call_service(agent_id="a-1", ha_url="http://ha",
                                                  ha_token="t", domain="light", service="turn_on")

    async def test_get_lights_success(self):
        from tools.smarthome_tool import home_assistant_get_lights
        res = await home_assistant_get_lights(ha_url="http://ha.local", ha_token="t")
        assert res["success"] is True and res["count"] == 1
        self.ha.close.assert_awaited_once()

    async def test_get_lights_missing_params(self):
        from tools.smarthome_tool import home_assistant_get_lights
        with pytest.raises(ValueError, match="ha_url and ha_token"):
            await home_assistant_get_lights(ha_url=None, ha_token=None)

    async def test_get_lights_failure(self):
        self.ha.get_lights.side_effect = RuntimeError("no lights")
        from tools.smarthome_tool import home_assistant_get_lights
        res = await home_assistant_get_lights(ha_url="http://ha.local", ha_token="t")
        assert res["success"] is False and "no lights" in res["error"]

    async def test_get_lights_blocked(self):
        with patch("tools.smarthome_tool._check_home_assistant_permission",
                   AsyncMock(return_value=(False, "blocked"))):
            from tools.smarthome_tool import home_assistant_get_lights
            with pytest.raises(PermissionError, match="blocked"):
                await home_assistant_get_lights(agent_id="a-1", ha_url="http://ha", ha_token="t")


class TestRegisterSmarthome:
    def test_register(self):
        import tools.smarthome_tool  # noqa: F401 - import first (deterministic auto-register)
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            from tools.smarthome_tool import register_smarthome_tools
            register_smarthome_tools()
        names = [c.kwargs["name"] for c in registry.register.call_args_list]
        assert names == [
            "hue_discover_bridges", "hue_get_lights", "hue_set_light_state",
            "home_assistant_get_states", "home_assistant_call_service", "home_assistant_get_lights"]

    def test_auto_register_failure(self):
        with patch("tools.registry.get_tool_registry", side_effect=RuntimeError("boom")):
            importlib.reload(sys.modules["tools.smarthome_tool"])
        importlib.reload(sys.modules["tools.smarthome_tool"])


# ============================================================================
# tools/creative_tool.py
# ============================================================================

class TestFFmpegTool:
    def _make_tool(self):
        service = MagicMock()
        service.validate_path.return_value = True
        service.trim_video = AsyncMock(return_value={"job_id": "j1"})
        service.convert_format = AsyncMock(return_value={"job_id": "j2"})
        service.generate_thumbnail = AsyncMock(return_value={"job_id": "j3"})
        service.extract_audio = AsyncMock(return_value={"job_id": "j4"})
        service.normalize_audio = AsyncMock(return_value={"job_id": "j5"})
        with patch("tools.creative_tool.FFmpegService", return_value=service):
            from tools.creative_tool import FFmpegTool
            return FFmpegTool(), service

    async def test_init_service_failure(self):
        with patch("tools.creative_tool.FFmpegService", side_effect=RuntimeError("no ffmpeg")):
            from tools.creative_tool import FFmpegTool
            tool = FFmpegTool()
        assert tool.service is None

    async def test_missing_maturity(self):
        tool, _ = self._make_tool()
        res = await tool._run("trim_video", "in.mp4", "out.mp4")
        assert res["success"] is False and "AUTONOMOUS" in res["error"]

    async def test_wrong_maturity(self):
        tool, _ = self._make_tool()
        res = await tool._run("trim_video", "in.mp4", "out.mp4",
                              maturity_level="SUPERVISED", agent_id="a-1")
        assert res["success"] is False and "SUPERVISED" in res["error"]

    async def test_service_unavailable(self):
        with patch("tools.creative_tool.FFmpegService", side_effect=RuntimeError("no ffmpeg")):
            from tools.creative_tool import FFmpegTool
            tool = FFmpegTool()
        res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False and "not available" in res["error"]

    async def test_input_path_out_of_scope(self):
        tool, service = self._make_tool()
        service.validate_path.side_effect = [False, True]
        res = await tool._run("trim_video", "../etc/passwd", "out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False and "outside allowed directories" in res["error"]

    async def test_output_path_out_of_scope(self):
        tool, service = self._make_tool()
        service.validate_path.side_effect = [True, False]
        res = await tool._run("trim_video", "in.mp4", "../../out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False and "outside allowed directories" in res["error"]

    async def test_validate_path_raises(self):
        tool, service = self._make_tool()
        service.validate_path.side_effect = ValueError("arg shape bad")
        res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False and "outside allowed directory" in res["error"]

    async def test_trim_success(self):
        tool, service = self._make_tool()
        res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS",
                              start_time="00:00:05", duration="00:01:00",
                              agent_id="a-1", db=None, session_id="s")
        assert res == {"success": True, "job_id": "j1"}
        service.trim_video.assert_awaited_once_with(
            input_path="in.mp4", output_path="out.mp4",
            start_time="00:00:05", duration="00:01:00")

    async def test_convert_success(self):
        tool, service = self._make_tool()
        res = await tool._run("convert_format", "in.mov", "out.mp4", maturity_level="AUTONOMOUS",
                              format="mp4", quality="high")
        assert res["success"] is True and res["job_id"] == "j2"
        service.convert_format.assert_awaited_once_with(
            input_path="in.mov", output_path="out.mp4", format="mp4", quality="high")

    async def test_thumbnail_success(self):
        tool, service = self._make_tool()
        res = await tool._run("generate_thumbnail", "in.mp4", "thumb.jpg",
                              maturity_level="AUTONOMOUS", timestamp="00:00:10")
        assert res["success"] is True and res["job_id"] == "j3"
        service.generate_thumbnail.assert_awaited_once_with(
            video_path="in.mp4", thumbnail_path="thumb.jpg", timestamp="00:00:10")

    async def test_extract_audio_success(self):
        tool, service = self._make_tool()
        res = await tool._run("extract_audio", "in.mp4", "out.mp3",
                              maturity_level="AUTONOMOUS", format="mp3")
        assert res["success"] is True and res["job_id"] == "j4"
        service.extract_audio.assert_awaited_once_with(
            video_path="in.mp4", audio_path="out.mp3", format="mp3")

    async def test_normalize_audio_success(self):
        tool, service = self._make_tool()
        res = await tool._run("normalize_audio", "in.mp3", "out.mp3",
                              maturity_level="AUTONOMOUS", target_lufs=-14.0)
        assert res["success"] is True and res["job_id"] == "j5"
        service.normalize_audio.assert_awaited_once_with(
            input_path="in.mp3", output_path="out.mp3", target_lufs=-14.0)

    async def test_non_dict_result_wrapped(self):
        tool, service = self._make_tool()
        service.trim_video.return_value = "ok"
        res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS",
                              start_time="00:00:00", duration="00:00:01")
        assert res == {"success": True, "result": "ok"}

    async def test_unknown_action(self):
        tool, _ = self._make_tool()
        res = await tool._run("explode", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False and "Unknown action" in res["error"]

    async def test_generic_exception(self):
        tool, service = self._make_tool()
        service.trim_video.side_effect = RuntimeError("segfault")
        res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS",
                              start_time="00:00:00", duration="00:00:01")
        assert res == {"success": False, "error": "FFmpeg operation failed"}

    def test_execute_operation_sync_no_loop(self):
        tool, service = self._make_tool()
        res = tool._execute_operation("trim_video", "in.mp4", "out.mp4",
                                      start_time="00:00:00", duration="00:00:01")
        assert res == {"job_id": "j1"}

    def test_execute_operation_unknown(self):
        tool, _ = self._make_tool()
        with pytest.raises(ValueError, match="Unknown action"):
            tool._execute_operation("nope", "in.mp4", "out.mp4")

    def test_execute_operation_creates_new_loop(self):
        tool, service = self._make_tool()
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no running loop")), \
             patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop set")):
            res = tool._execute_operation("trim_video", "in.mp4", "out.mp4",
                                          start_time="00:00:00", duration="00:00:01")
        assert res == {"job_id": "j1"}


class TestRegisterCreative:
    def test_register_success(self):
        import tools.creative_tool  # noqa: F401
        registry = MagicMock()
        from tools.creative_tool import register_creative_tool
        register_creative_tool(registry)
        registry.register.assert_called_once()
        assert registry.register.call_args.kwargs["name"] == "ffmpeg_edit"
        assert registry.register.call_args.kwargs["maturity_required"] == "AUTONOMOUS"

    def test_register_failure(self):
        registry = MagicMock()
        registry.register.side_effect = RuntimeError("boom")
        from tools.creative_tool import register_creative_tool
        register_creative_tool(registry)


class TestCreativeModuleFallbacks:
    def _reload_with_blocked_import(self, blocked_name):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == blocked_name:
                raise ImportError(f"blocked: {name}")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            return importlib.reload(sys.modules["tools.creative_tool"])

    def test_fallback_base_tool_when_langchain_missing(self):
        mod = self._reload_with_blocked_import("langchain.tools")
        fallback = mod.BaseTool()
        with pytest.raises(NotImplementedError):
            fallback._run("x")
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(fallback._arun("x"))

    def test_auto_register_import_error(self):
        mod = self._reload_with_blocked_import("tools.registry")
        assert mod is not None

    def test_reload_restores_normal_module(self):
        importlib.reload(sys.modules["tools.creative_tool"])
        from tools.creative_tool import FFmpegTool
        assert FFmpegTool is not None


# ============================================================================
# tools/predictive_tools.py
# ============================================================================

class TestForecast:
    @pytest.fixture(autouse=True)
    def _analyze(self):
        self.analyze = AsyncMock(
            return_value={"success": True, "results": {"method": "linear_regression"}})
        with patch("tools.data_analysis_tool.analyze_data", self.analyze):
            yield

    async def test_invalid_target_column(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "9bad")
        assert res["success"] is False and "identifier" in res["error"]

    async def test_invalid_date_column(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales", date_column="9bad")
        assert res["success"] is False and "identifier" in res["error"]

    async def test_periods_bool(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales", periods=True)
        assert res["success"] is False and "periods" in res["error"]

    async def test_periods_non_int(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales", periods="7")
        assert res["success"] is False and "periods" in res["error"]

    async def test_periods_zero(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales", periods=0)
        assert res["success"] is False and "periods" in res["error"]

    async def test_periods_too_big(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales", periods=400)
        assert res["success"] is False and "periods" in res["error"]

    async def test_unknown_method(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales", method="neural")
        assert res["success"] is False and "Unknown method" in res["error"]

    async def test_linear_success(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales", periods=7, session_id="s1")
        assert res["success"] is True
        assert res["forecast"] == {"method": "linear_regression"}
        assert res["governance"]["requires_review"] is True
        assert res["governance"]["review_status"] == "PENDING"
        code = self.analyze.await_args.kwargs.get("code") or self.analyze.await_args.args[1]
        assert "LinearRegression" in code
        assert "df['sales']" in code

    async def test_linear_with_date_column(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales", date_column="date", method="linear")
        assert res["success"] is True
        code = self.analyze.await_args.kwargs["code"]
        assert "pd.to_datetime(df['date'])" in code

    async def test_moving_average_success(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales", method="moving_average")
        assert res["success"] is True
        code = self.analyze.await_args.kwargs["code"]
        assert "np.mean(target[-window:])" in code

    async def test_exponential_success(self):
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales", method="exponential")
        assert res["success"] is True
        code = self.analyze.await_args.kwargs["code"]
        assert "ExponentialSmoothing" in code

    async def test_analyze_failure_propagated(self):
        self.analyze.return_value = {"success": False, "error": "dataset not loaded"}
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales")
        assert res["success"] is False and "dataset not loaded" in res["error"]

    async def test_analyze_output_fallback(self):
        self.analyze.return_value = {"success": True, "output": "raw output"}
        from tools.predictive_tools import forecast
        res = await forecast("d", "sales")
        assert res["success"] is True and res["forecast"] == "raw output"


class TestRunModel:
    @pytest.fixture(autouse=True)
    def _analyze(self):
        self.analyze = AsyncMock(
            return_value={"success": True, "results": {"model_type": "linear_regression"}})
        with patch("tools.data_analysis_tool.analyze_data", self.analyze):
            yield

    async def test_invalid_target(self):
        from tools.predictive_tools import run_model
        res = await run_model("d", "bad col")
        assert res["success"] is False and "identifier" in res["error"]

    async def test_invalid_feature_column(self):
        from tools.predictive_tools import run_model
        res = await run_model("d", "y", feature_columns=["bad col"])
        assert res["success"] is False and "identifier" in res["error"]

    async def test_invalid_test_size(self):
        from tools.predictive_tools import run_model
        assert (await run_model("d", "y", test_size=0.0))["success"] is False
        assert (await run_model("d", "y", test_size=1.0))["success"] is False
        assert (await run_model("d", "y", test_size=True))["success"] is False
        assert (await run_model("d", "y", test_size="0.2"))["success"] is False

    async def test_unknown_model_type(self):
        from tools.predictive_tools import run_model
        res = await run_model("d", "y", model_type="deep")
        assert res["success"] is False and "Unknown model_type" in res["error"]

    async def test_regression_all_features(self):
        from tools.predictive_tools import run_model
        res = await run_model("d", "y", model_type="regression")
        assert res["success"] is True
        code = self.analyze.await_args.kwargs["code"]
        assert "LinearRegression" in code
        assert "feature_cols = [c for c in df.columns if c != target_col]" in code

    async def test_regression_explicit_features(self):
        from tools.predictive_tools import run_model
        res = await run_model("d", "y", feature_columns=["a", "b"], model_type="regression")
        assert res["success"] is True
        code = self.analyze.await_args.kwargs["code"]
        assert "feature_cols = ['a', 'b']" in code
        assert res["governance"]["requires_review"] is True

    async def test_classification(self):
        from tools.predictive_tools import run_model
        res = await run_model("d", "y", feature_columns=["a"], model_type="classification")
        assert res["success"] is True
        code = self.analyze.await_args.kwargs["code"]
        assert "RandomForestClassifier" in code

    async def test_failure_propagated(self):
        self.analyze.return_value = {"success": False, "error": "nope"}
        from tools.predictive_tools import run_model
        res = await run_model("d", "y")
        assert res["success"] is False and "nope" in res["error"]

    async def test_session_id_passed(self):
        from tools.predictive_tools import run_model
        await run_model("d", "y", session_id="sess-9")
        assert self.analyze.await_args.kwargs["session_id"] == "sess-9"


class TestRegisterPredictive:
    def test_register_with_registry(self):
        import tools.predictive_tools  # noqa: F401
        from tools.predictive_tools import register_predictive_tools
        registry = MagicMock()
        register_predictive_tools(registry)
        names = [c.kwargs["name"] for c in registry.register.call_args_list]
        assert names == ["forecast", "run_model"]
        assert all(c.kwargs["maturity_required"] == "SUPERVISED"
                   for c in registry.register.call_args_list)

    def test_register_default_registry(self):
        from tools.predictive_tools import register_predictive_tools
        registry = MagicMock()
        with patch("tools.registry.get_tool_registry", return_value=registry):
            register_predictive_tools()
        assert registry.register.call_count == 2


# ============================================================================
# tools/canvas_orchestration_tool.py
# ============================================================================

class TestCanvasOrchestration:
    @pytest.fixture(autouse=True)
    def _mocks(self):
        self.svc = MagicMock()
        self.svc.create_orchestration_canvas.return_value = {
            "success": True, "canvas_id": "c-1", "tasks": [{"id": "t1"}]}
        self.present = AsyncMock(return_value={"success": True})
        with patch("core.canvas_orchestration_service.OrchestrationCanvasService",
                   return_value=self.svc), \
             patch("tools.canvas_tool.present_specialized_canvas", self.present), \
             _patch_db(Mock()):
            yield

    async def test_success(self):
        from tools.canvas_orchestration_tool import present_orchestration_canvas
        res = await present_orchestration_canvas("u-1", "Launch Plan", agent_id="a-1",
                                                 layout="board", tasks=[{"id": "t1"}])
        assert res["success"] is True
        assert res["canvas_id"] == "c-1" and "Launch Plan" in res["message"]
        self.present.assert_awaited_once()
        data = self.present.await_args.kwargs["data"]
        assert data["tasks"] == [{"id": "t1"}] and data["nodes"] == []

    async def test_defaults(self):
        from tools.canvas_orchestration_tool import present_orchestration_canvas
        res = await present_orchestration_canvas("u-1", "Board")
        assert res["success"] is True
        self.svc.create_orchestration_canvas.assert_called_once_with(
            user_id="u-1", title="Board", agent_id=None, layout="board", tasks=None)

    async def test_create_failure(self):
        self.svc.create_orchestration_canvas.return_value = {"success": False,
                                                             "error": "create failed"}
        from tools.canvas_orchestration_tool import present_orchestration_canvas
        res = await present_orchestration_canvas("u-1", "Board")
        assert res["success"] is False and res["error"] == "create failed"
        self.present.assert_not_awaited()

    async def test_present_failure(self):
        self.present.return_value = {"success": False, "error": "present failed"}
        from tools.canvas_orchestration_tool import present_orchestration_canvas
        res = await present_orchestration_canvas("u-1", "Board")
        assert res["success"] is False and res["error"] == "present failed"

    async def test_exception(self):
        self.svc.create_orchestration_canvas.side_effect = RuntimeError("boom")
        from tools.canvas_orchestration_tool import present_orchestration_canvas
        res = await present_orchestration_canvas("u-1", "Board")
        assert res["success"] is False and "boom" in res["error"]
