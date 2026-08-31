"""Coverage-push + bug-hunt tests for backend/tools (part 1).

Covers: atom_cli_skill_wrapper, memory_tool, registry, office_tool,
agent_guidance_canvas_tool, canvas_crud_tool, canvas docs/email/sheets/
orchestration/terminal/coding tools.

All external I/O (subprocess, DB, WebSockets, office services, LLM) is mocked.
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


# ============================================================================
# Shared helpers
# ============================================================================

@contextmanager
def _db_ctx(db):
    yield db


def _patch_db(db):
    return patch("core.database.get_db_session", side_effect=lambda: _db_ctx(db))


# ============================================================================
# atom_cli_skill_wrapper
# ============================================================================

class TestAtomCliSkillWrapper:
    def test_execute_success_with_args_and_cwd(self):
        result_obj = SimpleNamespace(returncode=0, stdout="Status: RUNNING\nPID: 1234", stderr="")
        with patch("tools.atom_cli_skill_wrapper.subprocess.run", return_value=result_obj) as run:
            from tools.atom_cli_skill_wrapper import execute_atom_cli_command
            res = execute_atom_cli_command("daemon", ["--port", "3000"], cwd="/tmp/agent/run1")
        assert res["success"] is True
        assert res["returncode"] == 0
        assert run.call_args[0][0] == ["atom-os", "daemon", "--port", "3000"]
        assert run.call_args[1]["cwd"] == "/tmp/agent/run1"
        assert "PATH" in run.call_args[1]["env"]

    def test_execute_no_args(self):
        result_obj = SimpleNamespace(returncode=1, stdout="", stderr="boom")
        with patch("tools.atom_cli_skill_wrapper.subprocess.run", return_value=result_obj) as run:
            from tools.atom_cli_skill_wrapper import execute_atom_cli_command
            res = execute_atom_cli_command("status")
        assert res["success"] is False
        assert res["stderr"] == "boom"
        assert run.call_args[0][0] == ["atom-os", "status"]
        assert run.call_args[1]["cwd"] is None
        assert run.call_args[1]["env"] is None

    def test_execute_timeout(self):
        import subprocess
        with patch("tools.atom_cli_skill_wrapper.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("cmd", 30)):
            from tools.atom_cli_skill_wrapper import execute_atom_cli_command
            res = execute_atom_cli_command("daemon")
        assert res["success"] is False
        assert res["returncode"] == -1
        assert "timed out" in res["stderr"]

    def test_execute_generic_error(self):
        with patch("tools.atom_cli_skill_wrapper.subprocess.run", side_effect=OSError("no atom-os")):
            from tools.atom_cli_skill_wrapper import execute_atom_cli_command
            res = execute_atom_cli_command("status")
        assert res["success"] is False
        assert res["returncode"] == -1
        assert "no atom-os" in res["stderr"]

    @pytest.mark.parametrize("stdout,expected", [
        ("Status: RUNNING\nPID: 99", True),
        ("Status: NOT RUNNING", False),
        ("no status here", False),
    ])
    def test_is_daemon_running(self, stdout, expected):
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": True, "stdout": stdout}):
            from tools.atom_cli_skill_wrapper import is_daemon_running
            assert is_daemon_running() is expected

    def test_is_daemon_running_command_failure(self):
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": False, "stdout": ""}):
            from tools.atom_cli_skill_wrapper import is_daemon_running
            assert is_daemon_running() is False

    def test_is_daemon_running_exception(self):
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   side_effect=RuntimeError("x")):
            from tools.atom_cli_skill_wrapper import is_daemon_running
            assert is_daemon_running() is False

    @pytest.mark.parametrize("stdout,expected", [
        ("Status: RUNNING\nPID: 12345", 12345),
        ("Status: RUNNING", None),
        ("junk", None),
    ])
    def test_get_daemon_pid(self, stdout, expected):
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": True, "stdout": stdout}):
            from tools.atom_cli_skill_wrapper import get_daemon_pid
            assert get_daemon_pid() == expected

    def test_get_daemon_pid_failure(self):
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   return_value={"success": False, "stdout": ""}):
            from tools.atom_cli_skill_wrapper import get_daemon_pid
            assert get_daemon_pid() is None

    def test_get_daemon_pid_exception(self):
        with patch("tools.atom_cli_skill_wrapper.execute_atom_cli_command",
                   side_effect=RuntimeError("x")):
            from tools.atom_cli_skill_wrapper import get_daemon_pid
            assert get_daemon_pid() is None

    def test_wait_for_daemon_ready_true(self):
        with patch("tools.atom_cli_skill_wrapper.is_daemon_running", return_value=True):
            from tools.atom_cli_skill_wrapper import wait_for_daemon_ready
            assert wait_for_daemon_ready(max_wait=5) is True

    def test_wait_for_daemon_ready_timeout(self):
        with patch("tools.atom_cli_skill_wrapper.is_daemon_running", return_value=False), \
             patch("tools.atom_cli_skill_wrapper.time.sleep"):
            from tools.atom_cli_skill_wrapper import wait_for_daemon_ready
            assert wait_for_daemon_ready(max_wait=0.1) is False

    def test_mock_daemon_response(self):
        from tools.atom_cli_skill_wrapper import mock_daemon_response
        ok = mock_daemon_response(stdout="Status: RUNNING", returncode=0)
        assert ok["success"] is True and ok["stdout"] == "Status: RUNNING"
        bad = mock_daemon_response(returncode=2, stderr="e")
        assert bad["success"] is False and bad["stderr"] == "e"

    def test_build_command_args(self):
        from tools.atom_cli_skill_wrapper import build_command_args
        args = build_command_args(port=3000, host="0.0.0.0", workers=4, host_mount=True,
                                  dev=True, foreground=True)
        assert args == ["--port", "3000", "--host", "0.0.0.0", "--workers", "4",
                        "--host-mount", "--dev", "--foreground"]
        assert build_command_args() == []


# ============================================================================
# memory_tool
# ============================================================================

class TestMemoryTool:
    @pytest.mark.parametrize("category", ["bogus", "wrong"])
    async def test_memory_remember_invalid_category(self, category):
        from tools.memory_tool import memory_remember
        res = await memory_remember("we use stripe", category)
        assert res["success"] is False
        assert "Invalid category" in res["message"]

    async def test_memory_remember_empty_fact(self):
        from tools.memory_tool import memory_remember
        res = await memory_remember("   ", "exact_value")
        assert res["success"] is False
        assert "required" in res["message"]

    async def test_memory_remember_success(self):
        row = SimpleNamespace(id="f-1", fact_text="we use stripe", category="exact_value",
                              confidence=0.95)
        with patch("tools.memory_tool.remember_fact_explicit", return_value=row) as rem:
            from tools.memory_tool import memory_remember
            res = await memory_remember("we use stripe", "exact_value", domain="finance",
                                        user_id="u-1", agent_workspace="ws-1")
        assert res["success"] is True and res["fact_id"] == "f-1"
        assert rem.call_args[1]["workspace_id"] == "ws-1"
        assert rem.call_args[1]["tenant_id"] == "default"

    async def test_memory_remember_persist_failure(self):
        with patch("tools.memory_tool.remember_fact_explicit", return_value=None):
            from tools.memory_tool import memory_remember
            res = await memory_remember("fact", "exact_value")
        assert res["success"] is False

    async def test_memory_forget_no_target(self):
        from tools.memory_tool import memory_forget
        res = await memory_forget()
        assert res["success"] is False
        assert "Refusing to forget" in res["message"]

    async def test_memory_forget_success(self):
        with patch("tools.memory_tool.forget_fact_explicit", return_value=2) as frg:
            from tools.memory_tool import memory_forget
            res = await memory_forget(fact_id="f-1")
        assert res["success"] is True and res["invalidated_count"] == 2
        assert frg.call_args[1]["fact_id"] == "f-1"

    async def test_memory_forget_no_match(self):
        with patch("tools.memory_tool.forget_fact_explicit", return_value=0):
            from tools.memory_tool import memory_forget
            res = await memory_forget(fact_text_contains="stripe")
        assert res["success"] is False

    def test_register_memory_tool(self):
        registry = MagicMock()
        from tools.memory_tool import register_memory_tool
        register_memory_tool(registry)
        names = [c.kwargs["name"] for c in registry.register.call_args_list]
        assert "memory_remember" in names and "memory_forget" in names


# ============================================================================
# registry
# ============================================================================

class TestRegistry:
    def test_type_name(self):
        import inspect
        from typing import List
        from tools.registry import _type_name
        assert _type_name(str) == "str"
        assert _type_name(inspect.Parameter.empty) == "Any"
        assert isinstance(_type_name(List[str]), str)

    def test_tool_metadata_to_dict(self):
        from tools.registry import ToolMetadata

        def dummy(a: str, b: int = 3):
            pass

        md = ToolMetadata(name="t", function=dummy, version="2.0.0", description="desc",
                          category="cat", complexity=3, maturity_required="SUPERVISED",
                          dependencies=["x"], parameters={"a": "str"}, examples=[{"x": 1}],
                          author="me", tags=["tag"], cacheable=True)
        d = md.to_dict()
        assert d["name"] == "t" and d["cacheable"] is True
        assert d["parameters"]["a"]["type"] == "str" and d["parameters"]["a"]["required"] is True
        assert d["parameters"]["b"]["required"] is False
        assert d["function_path"].endswith("dummy")
        assert d["registered_at"]

    def test_register_and_get(self):
        from tools.registry import ToolRegistry
        r = ToolRegistry()
        md = r.register("t1", lambda: None, description="d")
        assert md.description == "d"
        assert r.get("t1") is md
        assert r.get_function("t1") is not None
        assert r.get_function("nope") is None
        assert r.list_all() == ["t1"]
        assert r.list_by_category("general") == ["t1"]
        assert r.list_by_category("missing") == []

    def test_register_duplicate_updates(self):
        from tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register("t1", lambda: None)
        r.register("t1", lambda: None, version="2.0.0")
        assert len(r.list_all()) == 1
        assert r.get("t1").version == "2.0.0"

    def test_list_by_maturity(self):
        from tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register("student_tool", lambda: None, maturity_required="STUDENT")
        r.register("intern_tool", lambda: None, maturity_required="INTERN")
        r.register("autonomous_tool", lambda: None, maturity_required="AUTONOMOUS")
        assert r.list_by_maturity("STUDENT") == ["student_tool"]
        assert "intern_tool" in r.list_by_maturity("INTERN")
        assert r.list_by_maturity("BOGUS") == []

    def test_search_and_stats_and_export(self):
        from tools.registry import ToolRegistry
        r = ToolRegistry()
        r.register("get_weather", lambda: None, description="Fetch weather", tags=["weather", "forecast"])
        r.register("create_invoice", lambda: None, complexity=3, maturity_required="SUPERVISED")
        assert len(r.search("weather")) == 1
        assert len(r.search("fetch")) == 1
        assert len(r.search("forecast")) == 1
        assert len(r.search("zzz")) == 0
        stats = r.get_stats()
        assert stats["total_tools"] == 2
        assert stats["complexity_distribution"]["MODERATE"] == 1
        assert stats["maturity_distribution"]["SUPERVISED"] == 1
        assert len(r.export_all()) == 2
        simplified = r.get_simplified_tools()
        assert simplified[0]["name"] == "get_weather"
        assert "parameters" in simplified[0]

    def test_discover_tools(self):
        import tools.registry as reg_mod
        from tools.registry import ToolRegistry

        async def read_foo():
            """Docstring."""
            pass

        async def create_foo():
            pass

        async def execute_command_bar():
            pass

        async def deploy_thing():
            pass

        async def _private():
            pass

        fake = SimpleNamespace(read_foo=read_foo, create_foo=create_foo,
                               execute_command_bar=execute_command_bar,
                               deploy_thing=deploy_thing, _private=_private)
        with patch.object(reg_mod.importlib, "import_module", return_value=fake) as imp:
            r = ToolRegistry()
            count = r.discover_tools(["tools.fake_tool"])
        assert count == 4
        assert r.get("read_foo").complexity == 1
        assert r.get("read_foo").maturity_required == "STUDENT"
        assert r.get("read_foo").cacheable is True
        assert r.get("create_foo").complexity == 3
        assert r.get("create_foo").cacheable is False
        assert r.get("execute_command_bar").complexity == 4
        assert r.get("execute_command_bar").maturity_required == "AUTONOMOUS"
        assert r.get("execute_command_bar").cacheable is False
        assert r.get("deploy_thing").complexity == 4
        assert r.get("deploy_thing").maturity_required == "AUTONOMOUS"
        imp.assert_called_with("tools.fake_tool")

    def test_discover_tools_import_error(self):
        import tools.registry as reg_mod
        from tools.registry import ToolRegistry
        with patch.object(reg_mod.importlib, "import_module", side_effect=ImportError("nope")):
            r = ToolRegistry()
            count = r.discover_tools(["tools.missing_tool"])
        assert count == 0

    def test_discover_all_when_none(self):
        import tools.registry as reg_mod
        from tools.registry import ToolRegistry
        with patch.object(reg_mod.Path, "glob", return_value=[]):
            r = ToolRegistry()
            count = r.discover_tools(None)
        assert count == 0

    def test_initialize_runs_once(self):
        from tools.registry import ToolRegistry
        r = ToolRegistry()

        def _discover(*args, **kwargs):
            r._initialized = True
            return 5

        with patch.object(ToolRegistry, "discover_tools", side_effect=_discover) as disc, \
             patch.object(ToolRegistry, "_register_canvas_tools") as rc, \
             patch.object(ToolRegistry, "_register_browser_tools") as rb, \
             patch.object(ToolRegistry, "_register_device_tools") as rd, \
             patch.object(ToolRegistry, "_register_productivity_tools") as rp, \
             patch.object(ToolRegistry, "_register_memory_tools") as rm, \
             patch.object(ToolRegistry, "_register_data_tools") as rda:
            r.initialize()
            r.initialize()
        assert disc.call_count == 1
        rc.assert_called_once()
        rb.assert_called_once()
        rd.assert_called_once()
        rp.assert_called_once()
        rm.assert_called_once()
        rda.assert_called_once()

    def test_register_canvas_tools(self):
        from tools.registry import ToolRegistry
        r = ToolRegistry()
        func = lambda *a, **k: None  # noqa: E731
        with patch.object(ToolRegistry, "_get_function", return_value=func):
            r._register_canvas_tools()
        assert r.get("present_chart").category == "canvas"
        assert r.get("present_chart").complexity == 1
        assert r.get("read_canvas").cacheable is True
        assert r.get("list_canvases").cacheable is True
        assert r.get("update_canvas_content") is not None
        assert r.get("delete_canvas") is not None

    def test_register_browser_and_device_tools(self):
        from tools.registry import ToolRegistry
        r = ToolRegistry()
        func = lambda *a, **k: None  # noqa: E731
        with patch.object(ToolRegistry, "_get_function", return_value=func):
            r._register_browser_tools()
            r._register_device_tools()
        assert r.get("browser_create_session").maturity_required == "INTERN"
        assert r.get("browser_execute_script").complexity == 3
        assert r.get("device_execute_command").maturity_required == "AUTONOMOUS"
        assert r.get("device_camera_snap").maturity_required == "INTERN"

    def test_register_optional_tools(self):
        from tools.registry import ToolRegistry
        r = ToolRegistry()
        with patch("tools.calendar_tool.register_calendar_tool") as rc, \
             patch("tools.productivity_tool.register_notion_tool") as rn, \
             patch("tools.memory_tool.register_memory_tool") as rm, \
             patch("tools.data_analysis_tool.register_data_analysis_tools") as rda, \
             patch("tools.predictive_tools.register_predictive_tools") as rp:
            r._register_productivity_tools()
            r._register_memory_tools()
            r._register_data_tools()
        rc.assert_called_once()
        rn.assert_called_once()
        rm.assert_called_once()
        rda.assert_called_once()
        rp.assert_called_once()

    def test_register_optional_tools_failure(self):
        from tools.registry import ToolRegistry
        r = ToolRegistry()
        with patch("tools.calendar_tool.register_calendar_tool", side_effect=RuntimeError("x")), \
             patch("tools.productivity_tool.register_notion_tool", side_effect=RuntimeError("x")), \
             patch("tools.memory_tool.register_memory_tool", side_effect=RuntimeError("x")):
            r._register_productivity_tools()
            r._register_memory_tools()

    def test_get_function_missing(self):
        from tools.registry import ToolRegistry
        r = ToolRegistry()
        assert r._get_function("tools.registry", "does_not_exist") is None
        assert r._get_function("no.such.module", "x") is None

    def test_get_tool_registry_singleton(self):
        import tools.registry as reg_mod
        from tools.registry import get_tool_registry
        reg_mod._global_registry = None
        with patch.object(reg_mod.ToolRegistry, "initialize"):
            reg1 = get_tool_registry()
            reg2 = get_tool_registry()
        assert reg1 is reg2
        reg_mod._global_registry = None


# ============================================================================
# office_tool
# ============================================================================

def _office_service_mock():
    svc = MagicMock()
    svc.excel = MagicMock()
    svc.word = MagicMock()
    svc.pptx = MagicMock()
    svc.excel.read_range = Mock(return_value={"success": True, "value": "42"})
    svc.excel.write_cell = Mock(return_value={"success": True})
    svc.excel.get_evaluated_range = AsyncMock(return_value={"success": True, "value": 99.0})
    svc.excel.insert_rows = AsyncMock(return_value={"success": True})
    svc.excel.insert_columns = AsyncMock(return_value={"success": True})
    svc.excel.recalculate = AsyncMock(return_value={"success": True})
    svc.excel.add_pivot_table = AsyncMock(return_value={"success": True})
    svc.excel.run_excel_macro = AsyncMock(return_value={"success": True})
    svc.word.read_document = Mock(return_value={"success": True, "paragraphs": ["hi"]})
    svc.word.modify_document = Mock(return_value={"success": True})
    svc.pptx.read_slides = Mock(return_value={"success": True, "slides": []})
    svc.pptx.modify_slides = Mock(return_value={"success": True})
    return svc


class TestOfficeTool:
    @pytest.fixture(autouse=True)
    def _office_patch(self):
        with patch("tools.office_tool.office_service", _office_service_mock()), \
             patch("tools.office_tool.asyncio.create_task", side_effect=lambda c: None):
            yield

    async def test_read_excel_cell_success(self):
        from tools.office_tool import read_excel_cell
        res = await read_excel_cell("u-1", "data/office/book.xlsx", "/Sheet1/A1")
        assert res["value"] == "42"

    async def test_read_excel_cell_error(self):
        with patch("tools.office_tool.office_service.excel.read_range",
                   side_effect=ValueError("bad cell")):
            from tools.office_tool import read_excel_cell
            res = await read_excel_cell("u-1", "data/office/book.xlsx")
        assert res["success"] is False

    async def test_write_excel_cell_success(self):
        from tools.office_tool import write_excel_cell
        res = await write_excel_cell("u-1", "data/office/book.xlsx", "/Sheet1/A1", "42")
        assert res["success"] is True

    async def test_write_excel_cell_denied_path(self):
        from tools.office_tool import write_excel_cell
        res = await write_excel_cell("u-1", "/etc/passwd", "/Sheet1/A1", "42")
        assert res["success"] is False
        assert "outside the allowed office directory" in res["error"]

    async def test_write_excel_cell_error(self):
        from tools.office_tool import write_excel_cell
        with patch("tools.office_tool.office_service.excel.write_cell",
                   side_effect=RuntimeError("boom")):
            res = await write_excel_cell("u-1", "data/office/book.xlsx", "/Sheet1/A1", "42")
        assert res["success"] is False
        assert "Failed to write Excel cell" in res["error"]

    async def test_read_word_document(self):
        from tools.office_tool import read_word_document
        res = await read_word_document("u-1", "data/office/doc.docx")
        assert res["success"] is True
        with patch("tools.office_tool.office_service.word.read_document",
                   side_effect=OSError("x")):
            res2 = await read_word_document("u-1", "data/office/doc.docx")
        assert res2["success"] is False

    async def test_modify_word_document_success(self):
        from tools.office_tool import modify_word_document
        res = await modify_word_document("u-1", "data/office/doc.docx", "append", "more text")
        assert res["success"] is True

    async def test_modify_word_document_denied_and_error(self):
        from tools.office_tool import modify_word_document
        res = await modify_word_document("u-1", "/etc/hosts", "append", "x")
        assert res["success"] is False and "outside the allowed" in res["error"]
        with patch("tools.office_tool.office_service.word.modify_document",
                   side_effect=RuntimeError("x")):
            res2 = await modify_word_document("u-1", "data/office/doc.docx", "append", "x")
        assert res2["success"] is False and "Failed to modify Word" in res2["error"]

    async def test_read_pptx_slides(self):
        from tools.office_tool import read_pptx_slides
        res = await read_pptx_slides("u-1", "data/office/deck.pptx")
        assert res["success"] is True
        with patch("tools.office_tool.office_service.pptx.read_slides",
                   side_effect=RuntimeError("x")):
            res2 = await read_pptx_slides("u-1", "data/office/deck.pptx")
        assert res2["success"] is False

    async def test_modify_pptx_slides_success(self):
        from tools.office_tool import modify_pptx_slides
        res = await modify_pptx_slides("u-1", "data/office/deck.pptx", "add_slide", title="T")
        assert res["success"] is True

    async def test_modify_pptx_slides_denied_and_error(self):
        from tools.office_tool import modify_pptx_slides
        res = await modify_pptx_slides("u-1", "/tmp/evil.pptx", "add_slide")
        assert res["success"] is False and "outside the allowed" in res["error"]
        with patch("tools.office_tool.office_service.pptx.modify_slides",
                   side_effect=RuntimeError("x")):
            res2 = await modify_pptx_slides("u-1", "data/office/deck.pptx", "add_slide")
        assert res2["success"] is False and "Failed to modify PowerPoint" in res2["error"]

    async def test_get_excel_formula_result(self):
        from tools.office_tool import get_excel_formula_result
        res = await get_excel_formula_result("u-1", "data/office/book.xlsx", "Sheet1", "A4")
        assert res["success"] is True and res["value"] == 99.0
        with patch("tools.office_tool.office_service.excel.get_evaluated_range",
                   side_effect=RuntimeError("x")):
            res2 = await get_excel_formula_result("u-1", "data/office/book.xlsx", "Sheet1", "A4")
        assert res2["success"] is False

    async def test_insert_excel_rows_and_columns(self):
        from tools.office_tool import insert_excel_columns, insert_excel_rows
        res = await insert_excel_rows("u-1", "data/office/book.xlsx", "Sheet1", 2, 3)
        assert res["success"] is True
        res2 = await insert_excel_columns("u-1", "data/office/book.xlsx", "Sheet1", 1)
        assert res2["success"] is True
        with patch("tools.office_tool.office_service.excel.insert_rows",
                   side_effect=RuntimeError("x")):
            res3 = await insert_excel_rows("u-1", "data/office/book.xlsx", "Sheet1", 2)
        assert res3["success"] is False
        with patch("tools.office_tool.office_service.excel.insert_columns",
                   side_effect=RuntimeError("x")):
            res4 = await insert_excel_columns("u-1", "data/office/book.xlsx", "Sheet1", 1)
        assert res4["success"] is False

    async def test_recalculate_excel(self):
        from tools.office_tool import recalculate_excel
        res = await recalculate_excel("u-1", "data/office/book.xlsx")
        assert res["success"] is True
        with patch("tools.office_tool.office_service.excel.recalculate",
                   side_effect=RuntimeError("x")):
            res2 = await recalculate_excel("u-1", "data/office/book.xlsx")
        assert res2["success"] is False

    async def test_add_excel_pivot_table(self):
        from tools.office_tool import add_excel_pivot_table
        res = await add_excel_pivot_table("u-1", "data/office/book.xlsx", "Sheet1", "Pivot",
                                          "A1:D10", ["a"], ["b"], [{"field": "Sales", "function": "SUM"}])
        assert res["success"] is True
        with patch("tools.office_tool.office_service.excel.add_pivot_table",
                   side_effect=RuntimeError("x")):
            res2 = await add_excel_pivot_table("u-1", "data/office/book.xlsx", "Sheet1", "Pivot",
                                               "A1:D10", ["a"], ["b"], [{"field": "Sales"}])
        assert res2["success"] is False

    async def test_run_excel_macro(self):
        from tools.office_tool import run_excel_macro
        res = await run_excel_macro("u-1", "data/office/book.xlsx", "FormatData")
        assert res["success"] is True
        with patch("tools.office_tool.office_service.excel.run_excel_macro",
                   side_effect=RuntimeError("x")):
            res2 = await run_excel_macro("u-1", "data/office/book.xlsx", "FormatData")
        assert res2["success"] is False

    async def test_present_coedit_canvas_success(self):
        db = Mock()
        with _patch_db(db), patch("tools.office_tool.OfficeSyncService") as sync_cls:
            sync_cls.return_value.broadcast_file_update = Mock()
            from tools.office_tool import present_coedit_canvas
            res = await present_coedit_canvas("u-1", "data/office/book.xlsx")
        assert res["success"] is True
        assert res["canvas_id"].startswith("canvas_")

    async def test_present_coedit_canvas_with_canvas_id(self):
        db = Mock()
        with _patch_db(db), patch("tools.office_tool.OfficeSyncService") as sync_cls:
            sync_cls.return_value.broadcast_file_update = Mock()
            from tools.office_tool import present_coedit_canvas
            res = await present_coedit_canvas("u-1", "data/office/book.xlsx", canvas_id="c-1")
        assert res["success"] is True and res["canvas_id"] == "c-1"

    async def test_present_coedit_canvas_error(self):
        db = Mock()
        with _patch_db(db), patch("tools.office_tool.OfficeSyncService") as sync_cls:
            sync_cls.return_value.broadcast_file_update = Mock(side_effect=RuntimeError("x"))
            from tools.office_tool import present_coedit_canvas
            res = await present_coedit_canvas("u-1", "data/office/book.xlsx")
        assert res["success"] is False

    async def test_contained_path(self):
        from tools.office_tool import _contained_path
        assert _contained_path("data/office/a.xlsx") is not None
        assert _contained_path("/etc/passwd") is None

    async def test_ingest_after_write_import_error(self):
        with patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   side_effect=ImportError("no")):
            from tools.office_tool import _ingest_after_write
            await _ingest_after_write("data/office/a.xlsx", "u-1")

    async def test_ingest_after_write_missing_file(self):
        with patch("core.auto_document_ingestion.AutoDocumentIngestionService"), \
             patch("builtins.open", side_effect=FileNotFoundError("gone")):
            from tools.office_tool import _ingest_after_write
            await _ingest_after_write("data/office/missing.xlsx", "u-1")

    async def test_ingest_after_write_success(self):
        ing = MagicMock()
        ing.process_file_bytes = AsyncMock()
        with patch("core.auto_document_ingestion.AutoDocumentIngestionService",
                   return_value=ing), \
             patch("builtins.open", MagicMock(return_value=MagicMock(
                 __enter__=MagicMock(return_value=MagicMock(read=Mock(return_value=b"data"))),
                 __exit__=MagicMock(return_value=False)))):
            from tools.office_tool import _ingest_after_write
            await _ingest_after_write("data/office/a.xlsx", "u-1")
        ing.process_file_bytes.assert_awaited_once()


# ============================================================================
# agent_guidance_canvas_tool
# ============================================================================

def _guidance_db(agent=None, tracker=None):
    db = Mock()
    db.commit = Mock()
    db.add = Mock()

    def _query(model):
        q = MagicMock()
        q.filter.return_value = q
        if model.__name__ == "AgentRegistry":
            q.first.return_value = agent
        else:
            q.first.return_value = tracker
        return q

    db.query.side_effect = _query
    return db


class TestAgentGuidanceCanvasTool:
    @pytest.fixture(autouse=True)
    def _guidance_patch(self):
        self.agent = SimpleNamespace(name="Agent A", workspace_id="ws-1")
        self.tracker = SimpleNamespace(
            operation_id="op-1", current_step="Init", current_step_index=0,
            total_steps=4, progress=0, logs=[], what_explanation="",
            why_explanation="", next_steps="", status="running", completed_at=None,
        )
        with patch("tools.agent_guidance_canvas_tool.AgentGovernanceService") as gov_cls, \
             patch("tools.agent_guidance_canvas_tool.AgentContextResolver"), \
             patch("tools.agent_guidance_canvas_tool.ws_manager") as ws:
            gov = MagicMock()
            gov.can_perform_action.return_value = {"allowed": True, "reason": None}
            gov_cls.return_value = gov
            ws.broadcast = AsyncMock()
            self.ws = ws
            self.gov = gov
            yield

    _MISSING = object()

    def _system(self, agent=None, tracker=_MISSING):
        from tools.agent_guidance_canvas_tool import AgentGuidanceSystem
        return AgentGuidanceSystem(_guidance_db(
            self.agent if agent is None else agent,
            self.tracker if tracker is self._MISSING else tracker))

    async def test_start_operation_success(self):
        sys = self._system()
        op_id = await sys.start_operation("u-1", "a-1", "browser_automate",
                                          {"what": "x", "why": "y", "next": "z"}, total_steps=3)
        assert op_id
        self.ws.broadcast.assert_awaited_once()
        payload = self.ws.broadcast.await_args.args[1]["data"]
        assert payload["data"]["operation_type"] == "browser_automate"

    async def test_start_operation_governance_blocked(self):
        self.gov.can_perform_action.return_value = {"allowed": False, "reason": "nope"}
        sys = self._system()
        res = await sys.start_operation("u-1", "a-1", "browser_automate", {"what": "x"})
        assert res["success"] is False
        assert "nope" in res["error"]
        self.ws.broadcast.assert_not_awaited()

    async def test_start_operation_no_agent(self):
        sys = self._system(agent=None)
        op_id = await sys.start_operation("u-1", "a-1", "browser_automate", {})
        assert op_id
        self.ws.broadcast.assert_awaited_once()

    async def test_start_operation_exception(self):
        db = Mock()
        db.query.side_effect = RuntimeError("db down")
        with patch("tools.agent_guidance_canvas_tool.AgentGovernanceService"), \
             patch("tools.agent_guidance_canvas_tool.AgentContextResolver"), \
             patch("tools.agent_guidance_canvas_tool.ws_manager"):
            from tools.agent_guidance_canvas_tool import AgentGuidanceSystem
            sys = AgentGuidanceSystem(db)
            res = await sys.start_operation("u-1", "a-1", "op", {})
        assert isinstance(res, str) and len(res) == 36

    async def test_start_operation_disabled(self):
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            sys = self._system()
            res = await sys.start_operation("u-1", "a-1", "op", {})
        assert isinstance(res, str) and len(res) == 36
        self.ws.broadcast.assert_not_awaited()

    async def test_update_step_success_with_progress(self):
        sys = self._system(tracker=self.tracker)
        await sys.update_step("u-1", "op-1", "Working", progress=50,
                              add_log={"level": "info", "message": "m"})
        assert self.tracker.current_step == "Working"
        assert self.tracker.progress == 50
        assert len(self.tracker.logs) == 1
        self.ws.broadcast.assert_awaited_once()

    async def test_update_step_auto_progress(self):
        sys = self._system(tracker=self.tracker)
        await sys.update_step("u-1", "op-1", "Working")
        assert self.tracker.progress == int((1 / 4) * 100)

    async def test_update_step_not_found(self):
        sys = self._system(tracker=None)
        await sys.update_step("u-1", "op-1", "Working")
        self.ws.broadcast.assert_not_awaited()

    async def test_update_step_exception(self):
        db = Mock()
        db.query.side_effect = RuntimeError("db down")
        with patch("tools.agent_guidance_canvas_tool.AgentGovernanceService"), \
             patch("tools.agent_guidance_canvas_tool.AgentContextResolver"), \
             patch("tools.agent_guidance_canvas_tool.ws_manager"):
            from tools.agent_guidance_canvas_tool import AgentGuidanceSystem
            await AgentGuidanceSystem(db).update_step("u-1", "op-1", "Working")

    async def test_update_step_disabled(self):
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            sys = self._system()
            await sys.update_step("u-1", "op-1", "Working")
        self.ws.broadcast.assert_not_awaited()

    async def test_update_context(self):
        sys = self._system(tracker=self.tracker)
        await sys.update_context("u-1", "op-1", what="W", why="Y", next_steps="N")
        assert self.tracker.what_explanation == "W"
        assert self.tracker.why_explanation == "Y"
        assert self.tracker.next_steps == "N"
        self.ws.broadcast.assert_awaited_once()

    async def test_update_context_partial_and_not_found(self):
        sys = self._system(tracker=self.tracker)
        await sys.update_context("u-1", "op-1", what="W")
        assert self.tracker.what_explanation == "W"
        sys2 = self._system(tracker=None)
        await sys2.update_context("u-1", "op-1", what="W")
        assert self.ws.broadcast.await_count == 1

    async def test_update_context_exception_and_disabled(self):
        db = Mock()
        db.query.side_effect = RuntimeError("x")
        with patch("tools.agent_guidance_canvas_tool.AgentGovernanceService"), \
             patch("tools.agent_guidance_canvas_tool.AgentContextResolver"), \
             patch("tools.agent_guidance_canvas_tool.ws_manager"):
            from tools.agent_guidance_canvas_tool import AgentGuidanceSystem
            await AgentGuidanceSystem(db).update_context("u-1", "op-1", what="W")
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            sys = self._system()
            await sys.update_context("u-1", "op-1", what="W")
        self.ws.broadcast.assert_not_awaited()

    async def test_complete_operation(self):
        sys = self._system(tracker=self.tracker)
        await sys.complete_operation("u-1", "op-1", status="completed", final_message="done!")
        assert self.tracker.status == "completed"
        assert self.tracker.progress == 100
        self.ws.broadcast.assert_awaited_once()

    async def test_complete_operation_failed_and_not_found(self):
        sys = self._system(tracker=self.tracker)
        await sys.complete_operation("u-1", "op-1", status="failed")
        assert self.tracker.status == "failed"
        sys2 = self._system(tracker=None)
        await sys2.complete_operation("u-1", "op-1")
        assert self.ws.broadcast.await_count == 1

    async def test_complete_operation_exception_and_disabled(self):
        db = Mock()
        db.query.side_effect = RuntimeError("x")
        with patch("tools.agent_guidance_canvas_tool.AgentGovernanceService"), \
             patch("tools.agent_guidance_canvas_tool.AgentContextResolver"), \
             patch("tools.agent_guidance_canvas_tool.ws_manager"):
            from tools.agent_guidance_canvas_tool import AgentGuidanceSystem
            await AgentGuidanceSystem(db).complete_operation("u-1", "op-1")
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            sys = self._system()
            await sys.complete_operation("u-1", "op-1")

    async def test_add_log_entry(self):
        sys = self._system(tracker=self.tracker)
        with patch.object(sys, "update_step", new=AsyncMock()) as us:
            await sys.add_log_entry("u-1", "op-1", "warning", "careful")
        us.assert_awaited_once()
        assert us.await_args.kwargs["add_log"] == {"level": "warning", "message": "careful"}

    async def test_add_log_entry_disabled(self):
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            sys = self._system()
            await sys.add_log_entry("u-1", "op-1", "info", "m")

    async def test_create_audit_success_and_failure(self):
        db = Mock()
        with patch("tools.agent_guidance_canvas_tool.AgentGovernanceService"), \
             patch("tools.agent_guidance_canvas_tool.AgentContextResolver"), \
             patch("tools.agent_guidance_canvas_tool.ws_manager"):
            from tools.agent_guidance_canvas_tool import AgentGuidanceSystem
            sys = AgentGuidanceSystem(db)
            await sys._create_audit("a-1", "u-1", "op-1", "start_operation", True, {})
            db.add.side_effect = RuntimeError("x")
            await sys._create_audit("a-1", "u-1", "op-1", "start_operation", True, {})

    def test_get_agent_guidance_system(self):
        from tools.agent_guidance_canvas_tool import get_agent_guidance_system
        with patch("tools.agent_guidance_canvas_tool.AgentGuidanceSystem") as cls:
            get_agent_guidance_system(Mock())
        cls.assert_called_once()


# ============================================================================
# canvas_crud_tool
# ============================================================================

def _audit(**kw):
    base = dict(canvas_id="c-1", action_type="present", details_json={"content": "x", "title": "T"},
                created_at=datetime(2026, 1, 1), tenant_id="t-1", canvas_type="generic",
                user_id="u-1")
    base.update(kw)
    return SimpleNamespace(**base)


class TestCanvasCrudTool:
    @pytest.fixture(autouse=True)
    def _crud_patch(self):
        self.ws = MagicMock()
        self.ws.broadcast = AsyncMock()
        with patch("core.websockets.manager", self.ws):
            yield

    def _db(self, canvas=None, first=None, all_=None):
        db = Mock()

        def _query(model):
            q = MagicMock()
            q.filter.return_value = q
            q.order_by.return_value = q
            if model.__name__ == "Canvas":
                q.first.return_value = canvas
            else:
                q.first.return_value = first
                q.all.return_value = all_
            return q

        db.query.side_effect = _query
        return db

    async def test_verify_canvas_owner(self):
        from tools.canvas_crud_tool import _verify_canvas_owner
        db = Mock()
        canvas_q = db.query.return_value.filter.return_value
        canvas_q.first.return_value = SimpleNamespace(created_by="u-1")
        assert _verify_canvas_owner(db, "c-1", "u-1") is True
        canvas_q.first.return_value = SimpleNamespace(created_by="u-2")
        assert _verify_canvas_owner(db, "c-1", "u-1") is False
        canvas_q.first.return_value = None
        assert _verify_canvas_owner(db, "c-1", "u-1") is False

    async def test_read_canvas_success(self):
        db = self._db(canvas=SimpleNamespace(created_by="u-1"),
                      first=_audit(details_json={"content": "hello", "title": "T"}))
        with _patch_db(db):
            from tools.canvas_crud_tool import read_canvas
            res = await read_canvas("u-1", "c-1")
        assert res["success"] is True and res["content"] == "hello" and res["title"] == "T"
        assert res["canvas_type"] == "generic"

    async def test_read_canvas_content_from_data_fallback(self):
        db = self._db(canvas=SimpleNamespace(created_by="u-1"),
                      first=_audit(details_json={"data": [1, 2]}))
        with _patch_db(db):
            from tools.canvas_crud_tool import read_canvas
            res = await read_canvas("u-1", "c-1")
        assert res["content"] == [1, 2]

    async def test_read_canvas_not_owner_and_missing(self):
        db = self._db(canvas=SimpleNamespace(created_by="u-2"))
        with _patch_db(db):
            from tools.canvas_crud_tool import read_canvas
            res = await read_canvas("u-1", "c-1")
        assert res["success"] is False
        db2 = self._db(canvas=SimpleNamespace(created_by="u-1"), first=None)
        with _patch_db(db2):
            res2 = await read_canvas("u-1", "c-1")
        assert res2["success"] is False

    async def test_read_canvas_deleted(self):
        db = self._db(canvas=SimpleNamespace(created_by="u-1"), first=_audit(action_type="delete"))
        with _patch_db(db):
            from tools.canvas_crud_tool import read_canvas
            res = await read_canvas("u-1", "c-1")
        assert res["success"] is False and res["deleted"] is True

    async def test_read_canvas_exception(self):
        db = self._db(canvas=SimpleNamespace(created_by="u-1"))
        db.query.side_effect = RuntimeError("x")
        with _patch_db(db):
            from tools.canvas_crud_tool import read_canvas
            res = await read_canvas("u-1", "c-1")
        assert res["success"] is False

    async def test_update_canvas_content_success(self):
        db = self._db(canvas=SimpleNamespace(created_by="u-1"),
                      first=_audit(details_json={"old": 1}, tenant_id="t-1"))
        with _patch_db(db):
            from tools.canvas_crud_tool import update_canvas_content
            res = await update_canvas_content("u-1", "c-1", {"new": 2}, title="New")
        assert res["success"] is True
        self.ws.broadcast.assert_awaited_once()

    async def test_update_canvas_content_branches(self):
        from tools.canvas_crud_tool import update_canvas_content
        db = self._db(canvas=SimpleNamespace(created_by="u-2"))
        with _patch_db(db):
            res = await update_canvas_content("u-1", "c-1", {})
        assert res["success"] is False
        db2 = self._db(canvas=SimpleNamespace(created_by="u-1"), first=None)
        with _patch_db(db2):
            res2 = await update_canvas_content("u-1", "c-1", {})
        assert res2["success"] is False
        db3 = self._db(canvas=SimpleNamespace(created_by="u-1"), first=_audit(action_type="delete"))
        with _patch_db(db3):
            res3 = await update_canvas_content("u-1", "c-1", {})
        assert res3["success"] is False and "deleted" in res3["error"]

    async def test_update_canvas_content_ws_failure(self):
        db = self._db(canvas=SimpleNamespace(created_by="u-1"),
                      first=_audit(details_json={"old": 1}, tenant_id="t-1"))
        self.ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
        with _patch_db(db):
            from tools.canvas_crud_tool import update_canvas_content
            res = await update_canvas_content("u-1", "c-1", {"new": 2})
        assert res["success"] is True

    async def test_update_canvas_content_exception(self):
        db = self._db(canvas=SimpleNamespace(created_by="u-1"))
        db.query.side_effect = RuntimeError("x")
        with _patch_db(db):
            from tools.canvas_crud_tool import update_canvas_content
            res = await update_canvas_content("u-1", "c-1", {})
        assert res["success"] is False

    async def test_delete_canvas_success(self):
        db = self._db(canvas=SimpleNamespace(created_by="u-1"), first=_audit(canvas_type="docs"))
        with _patch_db(db):
            from tools.canvas_crud_tool import delete_canvas
            res = await delete_canvas("u-1", "c-1")
        assert res["success"] is True
        self.ws.broadcast.assert_awaited_once()

    async def test_delete_canvas_branches(self):
        from tools.canvas_crud_tool import delete_canvas
        db = self._db(canvas=SimpleNamespace(created_by="u-2"))
        with _patch_db(db):
            res = await delete_canvas("u-1", "c-1")
        assert res["success"] is False
        db2 = self._db(canvas=SimpleNamespace(created_by="u-1"), first=None)
        with _patch_db(db2):
            res2 = await delete_canvas("u-1", "c-1")
        assert res2["success"] is False
        db3 = self._db(canvas=SimpleNamespace(created_by="u-1"), first=_audit(action_type="delete"))
        with _patch_db(db3):
            res3 = await delete_canvas("u-1", "c-1")
        assert res3["success"] is False and "already deleted" in res3["error"]
        db4 = self._db(canvas=SimpleNamespace(created_by="u-1"), first=_audit())
        db4.query.side_effect = RuntimeError("x")
        with _patch_db(db4):
            res4 = await delete_canvas("u-1", "c-1")
        assert res4["success"] is False

    async def test_list_canvases(self, db_session):
        # Re-contracted 2026-08-30 for the list/discovery rewrite of
        # list_canvases (latest-per-canvas via a ROW_NUMBER() window +
        # search/paging): the old mock query-chain no longer matches the
        # implementation's query shape, so this runs against real
        # CanvasAudit rows. Intent unchanged: dedupe latest-wins, deleted
        # skipped, type filter + include_deleted.
        import uuid as _uuid
        from contextlib import contextmanager

        from core.models import CanvasAudit

        def _add(canvas_id, action_type, title, at):
            db_session.add(CanvasAudit(
                id=f"a-{_uuid.uuid4()}",
                canvas_id=canvas_id, tenant_id="t-1", user_id="u-1",
                canvas_type="docs", action_type=action_type,
                details_json={"title": title} if title else {},
                created_at=at,
            ))

        _add("c1", "present", "A", datetime(2026, 1, 3))
        _add("c1", "update", "B", datetime(2026, 1, 4))
        _add("c2", "delete", None, datetime(2026, 1, 5))
        db_session.commit()

        @contextmanager
        def _sess():
            yield db_session

        with patch("core.database.get_db_session", _sess):
            from tools.canvas_crud_tool import list_canvases
            res = await list_canvases("u-1")
        assert res["success"] is True and res["count"] == 1
        assert res["canvases"][0]["canvas_id"] == "c1"
        assert res["canvases"][0]["title"] == "B"
        with patch("core.database.get_db_session", _sess):
            res2 = await list_canvases("u-1", canvas_type="docs", include_deleted=True)
        assert res2["count"] == 2

    async def test_list_canvases_exception(self):
        db = self._db(canvas=None, all_=[])
        db.query.side_effect = RuntimeError("x")
        with _patch_db(db):
            from tools.canvas_crud_tool import list_canvases
            res = await list_canvases("u-1")
        assert res["success"] is False


# ============================================================================
# canvas docs/email/sheets/orchestration/terminal/coding tools
# ============================================================================

class TestSpecializedCanvasTools:
    @pytest.fixture(autouse=True)
    def _spec_patch(self):
        with _patch_db(Mock()), \
             patch("tools.canvas_tool.present_specialized_canvas",
                   AsyncMock(return_value={"success": True})) as present, \
             patch("tools.canvas_docs_tool.present_specialized_canvas",
                   AsyncMock(return_value={"success": True})) as present_docs:
            self.present = present
            self.present_docs = present_docs
            yield

    def _make_service(self, return_value):
        svc = MagicMock()
        for name in ("create_document_canvas", "create_email_canvas", "create_spreadsheet_canvas",
                     "create_orchestration_canvas", "create_terminal_canvas",
                     "create_coding_canvas"):
            setattr(svc, name, Mock(return_value=return_value))
        return svc

    async def _run_all(self, svc):
        with patch("tools.canvas_docs_tool.DocumentationCanvasService", return_value=svc), \
             patch("core.canvas_email_service.EmailCanvasService", return_value=svc), \
             patch("core.canvas_sheets_service.SpreadsheetCanvasService", return_value=svc), \
             patch("core.canvas_orchestration_service.OrchestrationCanvasService", return_value=svc), \
             patch("core.canvas_terminal_service.TerminalCanvasService", return_value=svc), \
             patch("core.canvas_coding_service.CodingCanvasService", return_value=svc):
            from tools.canvas_coding_tool import present_coding_canvas
            from tools.canvas_docs_tool import present_docs_canvas
            from tools.canvas_email_tool import present_email_canvas
            from tools.canvas_orchestration_tool import present_orchestration_canvas
            from tools.canvas_sheets_tool import present_sheets_canvas
            from tools.canvas_terminal_tool import present_terminal_canvas
            r1 = await present_docs_canvas("u-1", "Title", "# md")
            r2 = await present_email_canvas("u-1", "Subj", ["a@b.c"])
            r3 = await present_sheets_canvas("u-1", "Sheet", {"A1": 1})
            r4 = await present_orchestration_canvas("u-1", "Board")
            r5 = await present_terminal_canvas("u-1", "ls -la")
            r6 = await present_coding_canvas("u-1", "repo", "main")
        return [r1, r2, r3, r4, r5, r6]

    async def test_all_success(self):
        svc = self._make_service({"success": True, "canvas_id": "c-1", "cells": {}, "tasks": []})
        results = await self._run_all(svc)
        assert all(r["success"] for r in results)
        assert self.present.await_count == 5
        assert self.present_docs.await_count == 1

    async def test_all_create_failed(self):
        svc = self._make_service({"success": False, "error": "create failed"})
        results = await self._run_all(svc)
        assert all(r["success"] is False for r in results)
        assert self.present.await_count == 0
        assert self.present_docs.await_count == 0

    async def test_all_present_failed(self):
        svc = self._make_service({"success": True, "canvas_id": "c-1", "cells": {}, "tasks": []})
        self.present.return_value = {"success": False, "error": "present failed"}
        self.present_docs.return_value = {"success": False, "error": "present failed"}
        results = await self._run_all(svc)
        assert all(r["success"] is False for r in results)

    async def test_all_exception(self):
        svc = MagicMock()
        for name in ("create_document_canvas", "create_email_canvas", "create_spreadsheet_canvas",
                     "create_orchestration_canvas", "create_terminal_canvas",
                     "create_coding_canvas"):
            getattr(svc, name).side_effect = RuntimeError("boom")
        results = await self._run_all(svc)
        assert all(r["success"] is False for r in results)

    async def test_update_docs_canvas(self):
        svc = MagicMock()
        svc.update_document_content.return_value = {"success": True}
        with patch("tools.canvas_docs_tool.DocumentationCanvasService", return_value=svc):
            from tools.canvas_docs_tool import update_docs_canvas
            res = await update_docs_canvas("u-1", "c-1", "# new")
        assert res["success"] is True
        svc.update_document_content.return_value = {"success": False, "error": "no"}
        with patch("tools.canvas_docs_tool.DocumentationCanvasService", return_value=svc):
            res2 = await update_docs_canvas("u-1", "c-1", "# new")
        assert res2["success"] is False
        svc.update_document_content.side_effect = RuntimeError("x")
        with patch("tools.canvas_docs_tool.DocumentationCanvasService", return_value=svc):
            res3 = await update_docs_canvas("u-1", "c-1", "# new")
        assert res3["success"] is False
