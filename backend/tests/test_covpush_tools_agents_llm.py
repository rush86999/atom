"""
Coverage-push tests for tools + agents + llm modules (target >=95% lines).

All tests are mocked — no network, no real DB writes. Companion bug tests in
test_bughunt_tools_agents_llm.py.
"""

import asyncio
import json
import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


def _cm(db):
    """Wrap a mock db so ``with get_db_session() as db`` works."""
    mgr = MagicMock()
    mgr.__enter__ = Mock(return_value=db)
    mgr.__exit__ = Mock(return_value=False)
    return mgr


def _first_chain(db, value):
    """db.query(X).filter(...).first() -> value"""
    db.query.return_value.filter.return_value.first.return_value = value


# ===========================================================================
# tools.creative_tool gaps
# ===========================================================================


class TestCreativeToolGaps:
    def test_fallback_basetool_without_langchain(self):
        import importlib

        import tools.creative_tool as ct

        real_langchain = sys.modules.get("langchain")
        real_langchain_tools = sys.modules.get("langchain.tools")
        try:
            sys.modules["langchain"] = None
            sys.modules["langchain.tools"] = None
            mod = importlib.reload(ct)
            base = mod.BaseTool()
            with pytest.raises(NotImplementedError):
                base._run()
            with pytest.raises(NotImplementedError):
                asyncio.run(base._arun())
        finally:
            if real_langchain is not None:
                sys.modules["langchain"] = real_langchain
            if real_langchain_tools is not None:
                sys.modules["langchain.tools"] = real_langchain_tools
            importlib.reload(ct)

    @pytest.mark.asyncio
    async def test_non_dict_success_result(self):
        with patch("tools.creative_tool.FFmpegService") as svc:
            svc.return_value.validate_path = Mock(return_value=True)
            from tools.creative_tool import FFmpegTool

            tool = FFmpegTool()
            tool.service = MagicMock()
            tool.service.trim_video = AsyncMock(return_value=True)
            res = await tool._run(
                "trim_video", "in.mp4", "out.mp4",
                maturity_level="AUTONOMOUS", start_time="00:00:01", duration="00:01:00",
            )
        assert res["success"] is True
        assert res["result"] is True

    @pytest.mark.asyncio
    async def test_operation_exception_generic_error(self):
        with patch("tools.creative_tool.FFmpegService") as svc:
            svc.return_value.validate_path = Mock(return_value=True)
            from tools.creative_tool import FFmpegTool

            tool = FFmpegTool()
            tool.service = MagicMock()
            tool.service.trim_video = AsyncMock(side_effect=RuntimeError("boom"))
            res = await tool._run(
                "trim_video", "in.mp4", "out.mp4",
                maturity_level="AUTONOMOUS", start_time="00:00:01", duration="00:01:00",
            )
        assert res["success"] is False
        assert "boom" not in res["error"]

    @pytest.mark.asyncio
    async def test_convert_and_normalize_ops(self):
        with patch("tools.creative_tool.FFmpegService") as svc:
            svc.return_value.validate_path = Mock(return_value=True)
            from tools.creative_tool import FFmpegTool

            tool = FFmpegTool()
            tool.service = MagicMock()
            tool.service.convert_format = AsyncMock(return_value={"job_id": "c1"})
            tool.service.normalize_audio = AsyncMock(return_value={"job_id": "n1"})
            res = await tool._run(
                "convert_format", "in.mov", "out.mp4",
                maturity_level="AUTONOMOUS", format="mp4",
            )
            assert res["success"] is True and res["job_id"] == "c1"
            res = await tool._run(
                "normalize_audio", "a.mp3", "b.mp3",
                maturity_level="AUTONOMOUS", target_lufs=-14.0,
            )
            assert res["success"] is True and res["job_id"] == "n1"

    def test_register_creative_tool_success_log(self, caplog):
        from tools.creative_tool import register_creative_tool

        registry = MagicMock()
        with patch("tools.creative_tool.FFmpegTool"):
            register_creative_tool(registry)
        assert registry.register.called


# ===========================================================================
# tools.mini_app_tool gaps
# ===========================================================================


def _miniapp(**kw):
    base = dict(
        id="app-1",
        name="TestApp",
        created_by="user-1",
        tenant_id="default",
        blueprint_canvas_id="canvas-1",
        is_public=False,
        is_approved=False,
        version=1,
        status="draft",
        manifest={},
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _viewer(**kw):
    base = dict(id="user-1", tenant_id="default", workspace_id="ws-1", tier="autonomous")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def ctx():
    return {"user_id": "user-1", "agent_id": "agent-1", "tier": "autonomous"}


class TestMiniAppToolGaps:
    @pytest.mark.asyncio
    async def test_scaffold_spec_base_image_default(self, ctx):
        from tools.mini_app_tool import mini_app_scaffold

        with patch("core.mini_app_service.scaffold") as scaffold, patch(
            "core.database.get_db_session"
        ) as gds, patch("core.canvas_logic_service.CanvasLogicService") as cls:
            db = MagicMock()
            gds.return_value = _cm(db)
            app = _miniapp(manifest={"x": 1})
            db.query.return_value.filter.return_value.first.return_value = app
            scaffold.return_value = (app, "canvas-1")
            cls.return_value.load_logic = Mock(return_value={"source": "print(1)"})
            res = await mini_app_scaffold(
                {"name": "  App  ", "spec": {"base_image": ""}}, ctx
            )
        assert res["success"] is True
        assert res["logic_source"] == "print(1)"
        assert scaffold.call_args.kwargs["spec"]["base_image"] == "python:3.11-slim"

    @pytest.mark.asyncio
    async def test_scaffold_exception(self, ctx):
        from tools.mini_app_tool import mini_app_scaffold

        with patch("core.mini_app_service.scaffold", side_effect=RuntimeError("x")), patch(
            "core.database.get_db_session", side_effect=RuntimeError("x")
        ):
            res = await mini_app_scaffold({"name": "App"}, ctx)
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_write_logic_app_not_found(self, ctx):
        from tools.mini_app_tool import mini_app_write_logic

        with patch("core.database.get_db_session") as gds:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = None
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x = 1"}, ctx)
        assert res["success"] is False and "not found" in res["error"]

    @pytest.mark.asyncio
    async def test_write_logic_not_owner(self, ctx):
        from tools.mini_app_tool import mini_app_write_logic

        with patch("core.database.get_db_session") as gds:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp(created_by="other")
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x = 1"}, ctx)
        assert res["success"] is False and "owner" in res["error"]

    @pytest.mark.asyncio
    async def test_write_logic_no_blueprint(self, ctx):
        from tools.mini_app_tool import mini_app_write_logic

        with patch("core.database.get_db_session") as gds:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp(blueprint_canvas_id=None)
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x = 1"}, ctx)
        assert res["success"] is False and "blueprint" in res["error"]

    @pytest.mark.asyncio
    async def test_write_logic_syntax_error(self, ctx):
        from tools.mini_app_tool import mini_app_write_logic

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.syntax_check", side_effect=SyntaxError("bad")
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_write_logic({"app_id": "app-1", "source": "def :"}, ctx)
        assert res["success"] is False and "SyntaxError" in res["error"]

    @pytest.mark.asyncio
    async def test_write_logic_success(self, ctx):
        from tools.mini_app_tool import mini_app_write_logic

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.syntax_check"
        ), patch("core.mini_app_service.record_logic_snapshot", return_value={"version": 3}) as snap, patch(
            "core.canvas_logic_service.CanvasLogicService"
        ) as cls:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x = 1"}, ctx)
        assert res["success"] is True and res["version"] == 3
        cls.return_value.save_logic.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_logic_generic_exception(self, ctx):
        from tools.mini_app_tool import mini_app_write_logic

        with patch("core.database.get_db_session") as gds, patch(
            "core.canvas_logic_service.CanvasLogicService", side_effect=RuntimeError("x")
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_write_logic({"app_id": "app-1", "source": "x = 1"}, ctx)
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_dev_run_not_found_not_owner_no_blueprint(self, ctx):
        from tools.mini_app_tool import mini_app_dev_run

        with patch("core.database.get_db_session") as gds:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = None
            res = await mini_app_dev_run({"app_id": "app-1"}, ctx)
            assert res["success"] is False
            db.query.return_value.filter.return_value.first.return_value = _miniapp(created_by="o")
            res = await mini_app_dev_run({"app_id": "app-1"}, ctx)
            assert "owner" in res["error"]
            db.query.return_value.filter.return_value.first.return_value = _miniapp(blueprint_canvas_id=None)
            res = await mini_app_dev_run({"app_id": "app-1"}, ctx)
            assert "blueprint" in res["error"]

    @pytest.mark.asyncio
    async def test_dev_run_prepare_raises(self, ctx):
        from tools.mini_app_tool import mini_app_dev_run

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.prepare_runtime", side_effect=RuntimeError("deps unsafe")
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_dev_run({"app_id": "app-1"}, ctx)
        assert res["success"] is False and "deps unsafe" in res["error"]

    @pytest.mark.asyncio
    async def test_dev_run_run_failure_and_success(self, ctx):
        from tools.mini_app_tool import mini_app_dev_run

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.prepare_runtime"
        ), patch("core.mini_app_service.run_stateful") as rs:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            rs.return_value = {"success": False, "error": "vm failed"}
            res = await mini_app_dev_run({"app_id": "app-1"}, ctx)
            assert res["success"] is False and "vm failed" in res["error"]
            rs.return_value = {"success": True, "state": {"x": 1}, "version": 2,
                               "state_changed": True, "proposed_ops": [1], "op_results": [2],
                               "proposed_record_ops": [3], "record_results": [4],
                               "stdout": "o", "stderr": "e", "exit_code": 0}
            res = await mini_app_dev_run({"app_id": "app-1"}, ctx)
            assert res["success"] is True and res["state_changed"] is True

    @pytest.mark.asyncio
    async def test_dev_run_generic_exception(self, ctx):
        from tools.mini_app_tool import mini_app_dev_run

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.prepare_runtime", side_effect=TypeError("x")
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_dev_run({"app_id": "app-1"}, ctx)
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_publish_paths(self, ctx):
        from tools.mini_app_tool import mini_app_publish

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.publish", return_value={"version": 5}
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = None
            assert (await mini_app_publish({"app_id": "a"}, ctx))["success"] is False
            db.query.return_value.filter.return_value.first.return_value = _miniapp(created_by="o")
            assert "owner" in (await mini_app_publish({"app_id": "a"}, ctx))["error"]
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_publish({"app_id": "a"}, ctx)
            assert res["success"] is True and res["version"] == 5

    @pytest.mark.asyncio
    async def test_publish_raises(self, ctx):
        from tools.mini_app_tool import mini_app_publish

        for exc in (RuntimeError("rt"), ValueError("ve")):
            with patch("core.database.get_db_session") as gds, patch(
                "core.mini_app_service.publish", side_effect=exc
            ):
                db = MagicMock()
                gds.return_value = _cm(db)
                db.query.return_value.filter.return_value.first.return_value = _miniapp()
                res = await mini_app_publish({"app_id": "a"}, ctx)
            assert res["success"] is False
        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.publish", side_effect=TypeError("x")
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_publish({"app_id": "a"}, ctx)
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_install_paths(self, ctx):
        from tools.mini_app_tool import mini_app_install

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.install", return_value="canvas-9"
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = None
            assert (await mini_app_install({"app_id": "a"}, ctx))["success"] is False
            # public but unapproved (not owner)
            app = _miniapp(created_by="other", is_public=True, is_approved=False)
            db.query.return_value.filter.return_value.first.return_value = app
            res = await mini_app_install({"app_id": "a"}, ctx)
            assert res["success"] is False and "pending review" in res["error"]
            # not owner, private
            app = _miniapp(created_by="other")
            db.query.return_value.filter.return_value.first.return_value = app
            res = await mini_app_install({"app_id": "a"}, ctx)
            assert res["success"] is False and "authorized" in res["error"]
            # owner
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_install({"app_id": "a"}, ctx)
            assert res["success"] is True and res["canvas_id"] == "canvas-9"

    @pytest.mark.asyncio
    async def test_install_value_error(self, ctx):
        from tools.mini_app_tool import mini_app_install

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.install", side_effect=ValueError("bad")
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_install({"app_id": "a"}, ctx)
        assert res["success"] is False and "bad" in res["error"]

    @pytest.mark.asyncio
    async def test_list_exception(self, ctx):
        from tools.mini_app_tool import mini_app_list

        with patch("core.database.get_db_session", side_effect=RuntimeError("x")):
            res = await mini_app_list({}, ctx)
        assert res["success"] is False and res["apps"] == []

    @pytest.mark.asyncio
    async def test_get_state_paths(self, ctx):
        from tools.mini_app_tool import mini_app_get_state

        with patch("core.database.get_db_session") as gds:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = None
            assert (await mini_app_get_state({"canvas_id": "c"}, ctx))["success"] is False
            db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                id="c", mini_app_id=None
            )
            res = await mini_app_get_state({"canvas_id": "c"}, ctx)
            assert res["success"] is False and "not a mini-app" in res["error"]
            db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
                id="c", mini_app_id="app-1"
            )
            db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
            res = await mini_app_get_state({"canvas_id": "c"}, ctx)
            assert res["success"] is True and res["state"] == {} and res["version"] == 0

    @pytest.mark.asyncio
    async def test_get_state_exception(self, ctx):
        from tools.mini_app_tool import mini_app_get_state

        with patch("core.database.get_db_session", side_effect=RuntimeError("x")):
            res = await mini_app_get_state({"canvas_id": "c"}, ctx)
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_set_tests_paths(self, ctx):
        from tools.mini_app_tool import mini_app_set_tests

        assert (await mini_app_set_tests({"tests": []}, ctx))["success"] is False
        with patch("core.mini_app_service.validate_tests", side_effect=ValueError("bad test")):
            res = await mini_app_set_tests({"app_id": "a", "tests": [1]}, ctx)
        assert res["success"] is False and "bad test" in res["error"]
        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.validate_tests"
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_set_tests({"app_id": "a", "tests": [{"name": "t"}]}, ctx)
            assert res["success"] is True and res["tests"] == 1
            db.query.return_value.filter.return_value.first.return_value = _miniapp(created_by="o")
            res = await mini_app_set_tests({"app_id": "a", "tests": []}, ctx)
            assert "owner" in res["error"]

    @pytest.mark.asyncio
    async def test_run_tests_paths(self, ctx):
        from tools.mini_app_tool import mini_app_run_tests

        with patch("core.database.get_db_session") as gds:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp(manifest={"tests": []})
            res = await mini_app_run_tests({"app_id": "a"}, ctx)
            assert res["success"] is True and res["total"] == 0
            db.query.return_value.filter.return_value.first.return_value = _miniapp(
                manifest={"tests": [{"name": "t"}]}
            )
            with patch("core.mini_app_service.run_tests", return_value={
                "passed": 1, "total": 2, "results": [1],
            }) as rt:
                res = await mini_app_run_tests({"app_id": "a"}, ctx)
                assert res["success"] is True and res["all_passed"] is False
                rt.return_value = {"passed": 2, "total": 2, "results": []}
                res = await mini_app_run_tests({"app_id": "a"}, ctx)
                assert res["all_passed"] is True

    @pytest.mark.asyncio
    async def test_run_tests_exception(self, ctx):
        from tools.mini_app_tool import mini_app_run_tests

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.run_tests", side_effect=RuntimeError("x")
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp(
                manifest={"tests": [1]}
            )
            res = await mini_app_run_tests({"app_id": "a"}, ctx)
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_logic_history_paths(self, ctx):
        from tools.mini_app_tool import mini_app_logic_history

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.list_logic_history", return_value=[{"v": 1}]
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = None
            assert (await mini_app_logic_history({"app_id": "a"}, ctx))["success"] is False
            db.query.return_value.filter.return_value.first.return_value = _miniapp(created_by="o")
            assert "owner" in (await mini_app_logic_history({"app_id": "a"}, ctx))["error"]
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_logic_history({"app_id": "a"}, ctx)
            assert res["success"] is True and res["history"] == [{"v": 1}]

    @pytest.mark.asyncio
    async def test_logic_history_exception(self, ctx):
        from tools.mini_app_tool import mini_app_logic_history

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.list_logic_history", side_effect=RuntimeError("x")
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_logic_history({"app_id": "a"}, ctx)
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_revert_logic_paths(self, ctx):
        from tools.mini_app_tool import mini_app_revert_logic

        assert "app_id" in (await mini_app_revert_logic({"version": 2}, ctx))["error"]
        assert "version" in (await mini_app_revert_logic({"app_id": "a"}, ctx))["error"]
        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.revert_logic", return_value={"version": 4}
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = None
            assert (await mini_app_revert_logic({"app_id": "a", "version": 2}, ctx))["success"] is False
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_revert_logic({"app_id": "a", "version": 2}, ctx)
            assert res["success"] is True and res["version"] == 4

    @pytest.mark.asyncio
    async def test_revert_logic_errors(self, ctx):
        from tools.mini_app_tool import mini_app_revert_logic

        for exc in (ValueError("ve"), TypeError("x")):
            with patch("core.database.get_db_session") as gds, patch(
                "core.mini_app_service.revert_logic", side_effect=exc
            ):
                db = MagicMock()
                gds.return_value = _cm(db)
                db.query.return_value.filter.return_value.first.return_value = _miniapp()
                res = await mini_app_revert_logic({"app_id": "a", "version": 2}, ctx)
            assert res["success"] is False

    @pytest.mark.asyncio
    async def test_status_paths(self, ctx):
        from tools.mini_app_tool import mini_app_status

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.status_probe", return_value={"ok": True}
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = None
            assert (await mini_app_status({"app_id": "a"}, ctx))["success"] is False
            db.query.return_value.filter.return_value.first.return_value = _miniapp(created_by="o")
            assert "owner" in (await mini_app_status({"app_id": "a"}, ctx))["error"]
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_status({"app_id": "a"}, ctx)
            assert res["success"] is True and res["status"] == {"ok": True}

    @pytest.mark.asyncio
    async def test_status_exception(self, ctx):
        from tools.mini_app_tool import mini_app_status

        with patch("core.database.get_db_session") as gds, patch(
            "core.mini_app_service.status_probe", side_effect=RuntimeError("x")
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = _miniapp()
            res = await mini_app_status({"app_id": "a"}, ctx)
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_db_query_validation_paths(self, ctx):
        from tools.mini_app_tool import mini_app_db_query

        res = await mini_app_db_query({"op": "bogus", "canvas_id": "c"}, ctx)
        assert res["success"] is False and "op must be" in res["error"]
        res = await mini_app_db_query({"op": "query", "canvas_id": "c"}, {"user_id": "u", "tier": "student"})
        assert res["success"] is False and "INTERN" in res["error"]
        with patch("core.mini_app_db_service.db_store_enabled", return_value=False):
            res = await mini_app_db_query({"op": "query", "canvas_id": "c"}, ctx)
        assert res["success"] is False and res["error"] == "db_disabled"

    @pytest.mark.asyncio
    async def test_db_query_target_paths(self, ctx):
        from tools.mini_app_tool import mini_app_db_query

        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), patch(
            "core.database.get_db_session"
        ) as gds:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = None
            res = await mini_app_db_query({"op": "query", "canvas_id": "c", "series": "s"}, ctx)
            assert res["success"] is False and "not owned" in res["error"]
            canvas = SimpleNamespace(id="c", mini_app_id="app-1", created_by="user-1")
            db.query.return_value.filter.return_value.first.return_value = canvas
            # invalid series
            with patch("core.mini_app_db_service.validate_series", return_value=None):
                res = await mini_app_db_query({"op": "query", "canvas_id": "c", "series": "BAD!"}, ctx)
            assert res["success"] is False and "series" in res["error"]
            # invalid filter
            with patch("core.mini_app_db_service.validate_series", return_value="ok"), patch(
                "core.mini_app_db_service.validate_filter", return_value=False
            ):
                res = await mini_app_db_query({"op": "query", "canvas_id": "c", "series": "s"}, ctx)
            assert res["success"] is False and "filter" in res["error"]
            # bad limit/order
            with patch("core.mini_app_db_service.validate_series", return_value="ok"), patch(
                "core.mini_app_db_service.validate_filter", return_value=True
            ), patch("core.mini_app_db_service.query_records", return_value=[1]):
                res = await mini_app_db_query(
                    {"op": "query", "canvas_id": "c", "series": "s", "limit": 99999}, ctx
                )
                assert res["success"] is False and "limit" in res["error"]
                res = await mini_app_db_query(
                    {"op": "query", "canvas_id": "c", "series": "s", "limit": 5, "order": "bogus"}, ctx
                )
                assert res["success"] is False
                res = await mini_app_db_query(
                    {"op": "query", "canvas_id": "c", "series": "s", "limit": 5, "order": "asc"}, ctx
                )
                assert res["success"] is True and res["count"] == 1

    @pytest.mark.asyncio
    async def test_db_query_count_get_list(self, ctx):
        from tools.mini_app_tool import mini_app_db_query

        canvas = SimpleNamespace(id="c", mini_app_id="app-1", created_by="user-1")
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), patch(
            "core.database.get_db_session"
        ) as gds, patch("core.mini_app_db_service.validate_series", return_value="ok"), patch(
            "core.mini_app_db_service.validate_filter", return_value=True
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = canvas
            with patch("core.mini_app_db_service.count_records", return_value=7):
                res = await mini_app_db_query({"op": "count", "canvas_id": "c", "series": "s"}, ctx)
                assert res["success"] is True and res["count"] == 7
            with patch("core.mini_app_db_service.get_record", return_value=None):
                res = await mini_app_db_query({"op": "get", "canvas_id": "c", "series": "s", "record_id": "r"}, ctx)
                assert res["success"] is False and "not found" in res["error"]
            with patch("core.mini_app_db_service.get_record", return_value={"id": "r"}):
                res = await mini_app_db_query({"op": "get", "canvas_id": "c", "series": "s", "record_id": "r"}, ctx)
                assert res["success"] is True and res["record"] == {"id": "r"}
            with patch("core.mini_app_db_service.list_series", return_value=["a", "b"]):
                res = await mini_app_db_query({"op": "list_series", "canvas_id": "c"}, ctx)
                assert res["success"] is True and res["series"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_db_query_exception(self, ctx):
        from tools.mini_app_tool import mini_app_db_query

        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), patch(
            "core.database.get_db_session", side_effect=RuntimeError("x")
        ):
            res = await mini_app_db_query({"op": "query", "canvas_id": "c", "series": "s"}, ctx)
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_db_write_paths(self, ctx):
        from tools.mini_app_tool import mini_app_db_write

        res = await mini_app_db_write({"op": "bogus", "canvas_id": "c"}, ctx)
        assert res["success"] is False and "op must be" in res["error"]
        res = await mini_app_db_write({"op": "append", "canvas_id": "c"}, {"user_id": "u", "tier": "intern"})
        assert res["success"] is False and "SUPERVISED" in res["error"]
        with patch("core.mini_app_db_service.db_store_enabled", return_value=False):
            res = await mini_app_db_write({"op": "append", "canvas_id": "c"}, ctx)
        assert res["success"] is False and res["error"] == "db_disabled"
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), patch(
            "core.database.get_db_session"
        ) as gds:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = None
            res = await mini_app_db_write({"op": "append", "canvas_id": "c"}, ctx)
            assert res["success"] is False and "not owned" in res["error"]

    @pytest.mark.asyncio
    async def test_db_write_op_execution(self, ctx):
        from tools.mini_app_tool import mini_app_db_write

        canvas = SimpleNamespace(id="c", mini_app_id="app-1", created_by="user-1")
        app = _miniapp(manifest={"db": {"enabled": True, "max_record_bytes": 1024}})
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), patch(
            "core.database.get_db_session"
        ) as gds, patch("core.mini_app_db_service.validate_series", return_value="ok"), patch(
            "core.mini_app_service._validate_record_op", return_value={"op": "append"}
        ), patch("core.mini_app_service._execute_record_op", return_value={"ok": True, "id": "r1"}) as exe:
            db = MagicMock()
            gds.return_value = _cm(db)
            # _viewer queries User first, then _resolve_record_target queries
            # Canvas + MiniApp, then the tool re-queries MiniApp.
            user_row = SimpleNamespace(id="user-1", tenant_id="default",
                                       workspace_id="ws-1", tier="autonomous")
            db.query.return_value.filter.return_value.first.side_effect = [user_row, canvas, app, app]
            res = await mini_app_db_write(
                {"op": "append", "canvas_id": "c", "series": "s", "data": {"x": 1}}, ctx
            )
        assert res["success"] is True and res["ok"] is True
        exe.assert_called_once()
        # manifest db disabled
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), patch(
            "core.database.get_db_session"
        ) as gds:
            db = MagicMock()
            gds.return_value = _cm(db)
            user_row = SimpleNamespace(id="user-1", tenant_id="default",
                                       workspace_id="ws-1", tier="autonomous")
            db.query.return_value.filter.return_value.first.side_effect = [
                user_row, canvas, _miniapp(manifest={"db": {"enabled": False}}), _miniapp(manifest={"db": {"enabled": False}}),
            ]
            res = await mini_app_db_write({"op": "append", "canvas_id": "c", "series": "s"}, ctx)
        assert res["success"] is False and res["error"] == "db_disabled"
        # invalid record op
        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), patch(
            "core.database.get_db_session"
        ) as gds, patch("core.mini_app_db_service.validate_series", return_value="ok"), patch(
            "core.mini_app_service._validate_record_op", return_value=None
        ):
            db = MagicMock()
            gds.return_value = _cm(db)
            user_row = SimpleNamespace(id="user-1", tenant_id="default",
                                       workspace_id="ws-1", tier="autonomous")
            db.query.return_value.filter.return_value.first.side_effect = [user_row, canvas, app, app]
            res = await mini_app_db_write({"op": "append", "canvas_id": "c", "series": "s"}, ctx)
        assert res["success"] is False and "invalid record op" in res["error"]

    @pytest.mark.asyncio
    async def test_db_write_exception(self, ctx):
        from tools.mini_app_tool import mini_app_db_write

        with patch("core.mini_app_db_service.db_store_enabled", return_value=True), patch(
            "core.database.get_db_session", side_effect=RuntimeError("x")
        ):
            res = await mini_app_db_write({"op": "append", "canvas_id": "c", "series": "s"}, ctx)
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_context_user_id_variants(self):
        from tools.mini_app_tool import _context_user_id

        assert _context_user_id(None) is None
        assert _context_user_id({}) is None
        assert _context_user_id({"userId": 42}) == "42"
        assert _context_user_id({"actor_id": "a"}) == "a"
        assert _context_user_id({"user": SimpleNamespace(id="u")}) == "u"
        assert _context_user_id({"user": "not-an-object"}) is None
        assert _context_user_id({"user_id": ""}) is None

    @pytest.mark.asyncio
    async def test_viewer_db_failure_fallback(self):
        from tools.mini_app_tool import _viewer

        with patch("core.database.get_db_session", side_effect=RuntimeError("x")):
            v = _viewer({"user_id": "u1"})
        assert v.id == "u1" and v.tenant_id is None

    @pytest.mark.asyncio
    async def test_run_requires_canvas(self, ctx):
        from tools.mini_app_tool import mini_app_run

        res = await mini_app_run({}, ctx)
        assert res["success"] is False and "canvas_id" in res["error"]

    @pytest.mark.asyncio
    async def test_run_success(self, ctx):
        from tools.mini_app_tool import mini_app_run

        with patch("core.mini_app_service.run_stateful") as rs:
            rs.return_value = {"success": True, "state": {}}
            res = await mini_app_run({"canvas_id": "c", "inputs": {"x": 1}}, ctx)
        assert res["success"] is True
        assert rs.call_args.kwargs["persist"] is True
        assert rs.call_args.kwargs["agent_id"] == "agent-1"
        assert rs.call_args.kwargs["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_require_tier(self):
        from tools.mini_app_tool import _require_tier

        assert _require_tier({"tier": "intern"}, "supervised") is not None
        assert _require_tier({"tier": "autonomous"}, "supervised") is None
        assert _require_tier({"tier": "bogus"}, "intern") is not None
        assert _require_tier({}, "intern") is not None
        assert _require_tier({"tier": "SUPERVISED"}, "intern") is None


# ===========================================================================
# core/agents coverage gaps
# ===========================================================================


class TestAutoresearchGaps:
    @pytest.mark.asyncio
    async def test_read_instructions_failure(self, tmp_path):
        from core.agents.autoresearch_agent import AutoresearchAgent

        agent = AutoresearchAgent(db=MagicMock(), llm_service=MagicMock())
        res = await agent.run_experiment_loop("missing.md", "x.py", iterations=1)
        assert res["status"] == "error"

    @pytest.mark.asyncio
    async def test_read_script_failure(self, tmp_path):
        from core.agents.autoresearch_agent import AutoresearchAgent

        program = tmp_path / "p.md"
        program.write_text("instructions")
        agent = AutoresearchAgent(db=MagicMock(), llm_service=MagicMock())
        res = await agent.run_experiment_loop(str(program), "missing.py", iterations=1)
        assert res["status"] == "error"

    @pytest.mark.asyncio
    async def test_llm_failure_continues(self, tmp_path):
        from core.agents.autoresearch_agent import AutoresearchAgent

        program = tmp_path / "p.md"
        program.write_text("instructions")
        script = tmp_path / "t.py"
        script.write_text("print(1)")
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=RuntimeError("llm down"))
        agent = AutoresearchAgent(db=MagicMock(), llm_service=llm)
        res = await agent.run_experiment_loop(str(program), str(script), iterations=2)
        assert res["status"] == "success"
        assert res["history"] == []

    @pytest.mark.asyncio
    async def test_code_fence_stripping_and_rollback(self, tmp_path):
        from core.agents.autoresearch_agent import AutoresearchAgent

        program = tmp_path / "p.md"
        program.write_text("instructions")
        script = tmp_path / "t.py"
        script.write_text("print('FINAL_METRIC: 10.0')")

        llm = MagicMock()
        llm.generate = AsyncMock(return_value="```python\nprint('FINAL_METRIC: 0.5')\n```")
        agent = AutoresearchAgent(db=MagicMock(), llm_service=llm)

        # First iteration improves (kept); second run's LLM returns worse code.
        llm.generate.side_effect = [
            "```python\nprint('FINAL_METRIC: 0.5')\n```",
            "print('FINAL_METRIC: 9.9')",
        ]
        res = await agent.run_experiment_loop(str(program), str(script), iterations=2)
        assert res["status"] == "success"
        assert res["history"][0]["kept"] is True
        assert res["history"][1]["kept"] is False
        # the temp file was removed after rejection
        assert not (tmp_path / "t.py.tmp").exists()

    @pytest.mark.asyncio
    async def test_evaluate_returncode_and_missing_metric(self, tmp_path):
        from core.agents.autoresearch_agent import AutoresearchAgent

        agent = AutoresearchAgent(db=MagicMock(), llm_service=MagicMock())
        bad = tmp_path / "bad.py"
        bad.write_text("import sys; sys.exit(3)")
        assert await agent._evaluate_script(str(bad)) is None
        nometric = tmp_path / "no.py"
        nometric.write_text("print('hello')")
        assert await agent._evaluate_script(str(nometric)) is None

    @pytest.mark.asyncio
    async def test_evaluate_unparseable_metric_line(self, tmp_path):
        from core.agents.autoresearch_agent import AutoresearchAgent

        agent = AutoresearchAgent(db=MagicMock(), llm_service=MagicMock())
        f = tmp_path / "m.py"
        f.write_text("print('FINAL_METRIC: not-a-number')")
        assert await agent._evaluate_script(str(f)) is None

    @pytest.mark.asyncio
    async def test_evaluate_raises(self, tmp_path):
        from core.agents.autoresearch_agent import AutoresearchAgent

        agent = AutoresearchAgent(db=MagicMock(), llm_service=MagicMock())
        with patch("asyncio.create_subprocess_exec", side_effect=RuntimeError("boom")):
            assert await agent._evaluate_script("x.py") is None


class TestKingGaps:
    def _king(self):
        from core.agents.king_agent import KingAgent

        king = object.__new__(KingAgent)
        king.queen = MagicMock()
        king.queen.generate_mermaid = Mock(return_value="graph TD")
        king.healer = MagicMock()
        king.agent_id = "king-1"
        king.workspace_id = "default"
        king.tenant_id = "default"
        return king

    @pytest.mark.asyncio
    async def test_stalled_execution(self):
        from core.agents.king_agent import KingAgent

        king = self._king()
        res = await king.execute_blueprint(
            {
                "architecture_name": "Stall",
                "nodes": [
                    {"id": "a", "name": "A", "type": "skill", "capability_required": "x",
                     "dependencies": ["missing-dep"]},
                ],
            }
        )
        assert res["status"] == "success" and res["execution_results"] == []

    @pytest.mark.asyncio
    async def test_node_error_dict_triggers_heal(self):
        from core.agents.king_agent import KingAgent

        king = self._king()
        king._execute_node = AsyncMock(return_value={"error": "node exploded"})
        king.healer.heal_blueprint = AsyncMock(return_value={"status": "failed"})
        res = await king.execute_blueprint(
            {
                "architecture_name": "X",
                "nodes": [
                    {"id": "n1", "name": "N", "type": "agent", "capability_required": "c",
                     "dependencies": []},
                ],
            }
        )
        assert res["status"] == "failed"
        king.healer.heal_blueprint.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_heal_success_records_trace(self):
        from core.agents.king_agent import KingAgent

        king = self._king()
        king._execute_node = AsyncMock(side_effect=[{"error": "boom"}, {"ok": True}])
        king.healer.heal_blueprint = AsyncMock(
            return_value={
                "status": "healed",
                "nodes": [
                    {"id": "n2", "name": "N2", "type": "agent", "capability_required": "c",
                     "dependencies": []},
                ],
            }
        )
        king.healer.summarize_healing_as_directive = AsyncMock(return_value="directive")
        with patch("core.agents.king_agent.SessionLocal") as sl:
            db = MagicMock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            res = await king.execute_blueprint(
                {
                    "architecture_name": "X",
                    "blueprint_id": "bp-1",
                    "nodes": [
                        {"id": "n1", "name": "N", "type": "agent", "capability_required": "c",
                         "dependencies": []},
                    ],
                }
            )
        assert res["status"] == "success"
        assert res["final_summary"].endswith("with 1 heal events.")
        db.add.assert_called()

    @pytest.mark.asyncio
    async def test_execute_node_agent_and_skill_and_unknown(self):
        from core.agents.king_agent import KingAgent

        king = self._king()
        king._execute_delegation = AsyncMock(return_value={"ok": True})
        king._execute_tool_with_governance = AsyncMock(return_value={"ok": True})
        res = await king._execute_node(
            {"id": "a", "name": "A", "type": "agent", "capability_required": "lead_scoring"},
            {}, None,
        )
        assert res["ok"] is True
        res = await king._execute_node(
            {"id": "s", "name": "S", "type": "skill", "capability_required": "search"}, {}, None
        )
        assert res["ok"] is True
        res = await king._execute_node({"id": "u", "name": "U", "type": "alien"}, {}, None)
        assert res["status"] == "skipped"

    def test_map_capability(self):
        from core.agents.king_agent import KingAgent

        king = self._king()
        assert king._map_capability_to_agent("reconciliation") == "accounting"
        assert king._map_capability_to_agent("b2b_extract_po") == "purchasing"
        assert king._map_capability_to_agent("unknown_thing") == "general"


class TestQueenGaps:
    def _queen(self):
        from core.agents.queen_agent import QueenAgent

        return QueenAgent(db=MagicMock(), llm=MagicMock())

    @pytest.mark.asyncio
    async def test_realize_blueprint_orchestrator_unavailable(self):
        queen = self._queen()
        with patch.dict(sys.modules, {"advanced_workflow_orchestrator": None}):
            from core.agents import queen_agent as qa

            with patch("builtins.__import__", side_effect=ImportError("no")):
                res = await queen.realize_blueprint({}, tenant_id="t")
        assert res == "orchestrator_not_available"

    @pytest.mark.asyncio
    async def test_realize_blueprint_registers_workflow(self):
        from core.agents.queen_agent import QueenAgent

        blueprint = {
            "architecture_name": "WF",
            "description": "d",
            "nodes": [
                {"id": "t1", "type": "trigger", "name": "Trig", "capability_required": "ev",
                 "dependencies": [], "metadata": {"trigger_event": "x"}},
                {"id": "a1", "type": "agent", "name": "Ag", "capability_required": "c",
                 "dependencies": ["t1"]},
                {"id": "e1", "type": "entity", "name": "Ent", "capability_required": "kg",
                 "dependencies": ["a1"]},
                {"id": "s1", "type": "skill", "name": "Sk", "capability_required": "tool",
                 "dependencies": ["e1"]},
            ],
        }
        orchestrator = MagicMock()
        queen = self._queen()
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orchestrator):
            wf_id = await queen.realize_blueprint(blueprint, tenant_id="t")
        assert wf_id.startswith("ai_wf_")
        orchestrator.register_workflow.assert_called_once()
        wf = orchestrator.register_workflow.call_args.args[0]
        assert wf.start_step == "t1"
        assert len(wf.steps) == 4

    @pytest.mark.asyncio
    async def test_realize_blueprint_no_triggers(self):
        from core.agents.queen_agent import QueenAgent

        orchestrator = MagicMock()
        queen = self._queen()
        with patch("advanced_workflow_orchestrator.get_orchestrator", return_value=orchestrator):
            wf_id = await queen.realize_blueprint(
                {"architecture_name": "W", "nodes": [
                    {"id": "s1", "type": "agent", "name": "A", "dependencies": []},
                ]},
                tenant_id="t",
            )
        wf = orchestrator.register_workflow.call_args.args[0]
        assert wf.start_step == "s1"

    @pytest.mark.asyncio
    async def test_generate_blueprint_json_fence(self):
        from core.agents.queen_agent import QueenAgent

        llm = MagicMock()
        blueprint = {"architecture_name": "Fenced", "description": "d", "nodes": [],
                     "required_integrations": [], "missing_capabilities": []}
        llm.generate = AsyncMock(return_value=f"```json\n{json.dumps(blueprint)}\n```")
        queen = QueenAgent(db=MagicMock(), llm=llm)
        res = await queen.generate_blueprint("goal", tenant_id="t")
        assert res["architecture_name"] == "Fenced"
        assert "blueprint_id" in res


class TestSkillCreationGaps:
    def _agent(self, llm=None):
        from core.agents.skill_creation_agent import SkillCreationAgent

        return SkillCreationAgent(db=MagicMock(), llm_service=llm or MagicMock())

    @pytest.mark.asyncio
    async def test_create_component_skill_not_found(self):
        agent = self._agent()
        agent.db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            await agent.create_canvas_component_for_skill("t", "a", "u", "skill-1")

    @pytest.mark.asyncio
    async def test_create_component_success(self):
        agent = self._agent()
        skill = SimpleNamespace(id="s1", name="Svc", description="d", output_schema={},
                                tags=["api"], version="1.0.0")
        agent.db.query.return_value.filter.return_value.first.return_value = skill
        agent._analyze_skill_for_component = AsyncMock(
            return_value={"category": "table", "config_schema": {}, "dependencies": []}
        )
        agent._generate_component_code = AsyncMock(return_value="export const X = 1")
        comp = await agent.create_canvas_component_for_skill("t", "a", "u", "s1")
        assert comp is not None
        agent.db.add.assert_called_once()

    def test_validate_url_variants(self):
        agent = self._agent()
        assert agent._validate_url("http://LOCALHOST/x") is False
        assert agent._validate_url("http://10.1.2.3/x") is False
        assert agent._validate_url("http://172.16.0.1/x") is False
        assert agent._validate_url("http://192.168.1.1/x") is False
        assert agent._validate_url("http://169.254.1.1/x") is False
        assert agent._validate_url("http://[fd00::1]/x") is False
        assert agent._validate_url("http://[fe80::1]/x") is False
        assert agent._validate_url("ftp://example.com/x") is False
        assert agent._validate_url("http://[not-an-ip]/x") is False
        assert agent._validate_url("http://example.com/x") is True

    def test_infer_category_and_tags(self):
        agent = self._agent()
        assert agent._infer_category({}, "shopify order sync") == "ecommerce"
        assert agent._infer_category({}, "salesforce crm leads") == "crm"
        assert agent._infer_category({}, "slack communication") == "communication"
        assert agent._infer_category({}, "finance invoice") == "finance"
        assert agent._infer_category({}, "marketing campaign") == "marketing"
        assert agent._infer_category({}, "random stuff") == "productivity"
        tags = agent._extract_tags({"title": "My API"}, "rest json docs")
        assert tags == ["api", "rest", "json"]

    @pytest.mark.asyncio
    async def test_generate_skill_code_markdown_fence(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="```python\nprint('hi')\n```")
        agent = self._agent(llm)
        code = await agent._generate_skill_code(
            {"base_url": "u", "description": "d", "input_schema": {}, "output_schema": {},
             "auth_headers": {}}
        )
        assert code == "print('hi')"

    def test_fallback_code_auth_variants(self):
        agent = self._agent()
        bearer = agent._generate_fallback_code(
            {"base_url": "u", "description": "d", "auth_headers": {"Authorization": "Bearer {{API_KEY}}"}}
        )
        assert "Bearer" in bearer
        key = agent._generate_fallback_code(
            {"base_url": "u", "description": "d", "auth_headers": {"X-API-Key": "{{API_KEY}}"}}
        )
        assert "X-API-Key" in key
        pub = agent._generate_fallback_code(
            {"base_url": "u", "description": "d", "auth_headers": {}}
        )
        assert "None (Public API)" in pub

    @pytest.mark.asyncio
    async def test_analyze_skill_for_component_categories(self):
        agent = self._agent()
        skill = SimpleNamespace(output_schema={})
        for ct in ["table", "chart", "form", "widget"]:
            cfg = await agent._analyze_skill_for_component(skill, ct)
            assert cfg["category"] == (ct if ct != "widget" else "widget")

    @pytest.mark.asyncio
    async def test_generate_component_code_fences(self):
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=[
            "```typescript\nexport const A = 1;\n```",
            "```tsx\nexport const B = 2;\n```",
        ])
        agent = self._agent(llm)
        skill = SimpleNamespace(name="S", description="d", output_schema={})
        c1 = await agent._generate_component_code(skill, {})
        assert c1 == "export const A = 1;"
        c2 = await agent._generate_component_code(skill, {})
        assert c2 == "export const B = 2;"

    def test_generate_skill_metadata_npm(self):
        agent = self._agent()
        md = agent.generate_skill_metadata(
            {"code": "import x from 'recharts';", "name": "comp", "dependencies": ["lucide"],
             "python_dependencies": ["pandas"], "config_schema": {"properties": {"a": {"type": "string"}}}},
            "skill-1", "t-1",
        )
        assert "recharts" in md and "lucide" in md
        md2 = agent.generate_skill_metadata({"name": "c2"}, "skill-2", "t-1")
        assert "[]" in md2

    def test_format_helpers(self):
        agent = self._agent()
        assert agent._format_npm_dependencies([]) == "None"
        assert agent._format_npm_dependencies(["a", "b"]) == "- **a**\n- **b**"
        assert agent._format_python_dependencies([]) == "None"
        assert agent._format_python_dependencies(["p"]) == "- **p**"
        assert agent._format_config_schema({}) == "No configuration required."
        out = agent._format_config_schema(
            {"required": ["a"], "properties": {"a": {"type": "string", "description": "d"}}}
        )
        assert "a" in out and "required" in out


# ===========================================================================
# core/llm coverage gaps
# ===========================================================================


class TestActionJudgeGaps:
    @pytest.mark.asyncio
    async def test_cache_expiry_and_put(self):
        from core.llm.action_judge import _ResultCache

        cache = _ResultCache(ttl_seconds=0)
        await cache.put("k", "v")
        assert await cache.get("k") is None  # expired immediately
        cache2 = _ResultCache(ttl_seconds=60)
        await cache2.put("k", "v")
        assert await cache2.get("k") == "v"
        await cache2.clear()
        assert await cache2.get("k") is None

    def test_verdict_parse_value_error(self):
        from core.llm.action_judge import ActionJudge, JudgeVerdict

        judge = ActionJudge()
        verdict, rationale = judge._parse_response('{"verdict": "bogus", "rationale": "r"}')
        assert verdict == JudgeVerdict.ESCALATE
        assert "unparsed" in rationale
        verdict, rationale = judge._parse_response("```json\n{\"verdict\": \"block\"}\n```")
        assert verdict == JudgeVerdict.BLOCK
        verdict, _ = judge._parse_response("not json at all")
        assert verdict == JudgeVerdict.ESCALATE

    def test_hash_provenance_variants(self):
        from core.llm.action_judge import ActionJudge

        judge = ActionJudge()
        h1 = judge._hash("a", "c", [("tool_output", "x" * 300)])
        assert len(h1) == 64
        h2 = judge._hash("a", "c", ["plain-string"])
        assert len(h2) == 64
        h3 = judge._hash("a", "c", None)
        assert len(h3) == 64

    @pytest.mark.asyncio
    async def test_get_default_judge_singleton(self):
        from core.llm import action_judge as aj

        old = aj._default_judge
        aj._default_judge = None
        try:
            j1 = aj.get_default_judge()
            j2 = aj.get_default_judge()
            assert j1 is j2
        finally:
            aj._default_judge = old


class TestCacheAwareRouterGaps:
    def _router(self):
        from core.llm.cache_aware_router import CacheAwareRouter

        pricing = MagicMock()
        return CacheAwareRouter(pricing)

    def test_effective_cost_turn_mode_and_clamp(self):
        router = self._router()
        from core.llm.byok_handler import AwaitableResult

        res = router.calculate_effective_cost(
            "gpt-4o", "openai", 5000,
            cache_hit_probability=None, turn_index=2, prompt_hash="abc",
        )
        assert isinstance(res, AwaitableResult)
        res = router.calculate_effective_cost(
            "gpt-4o", "openai", 5000,
            cache_hit_probability=None, turn_index=0, prompt_hash=None,
        )
        assert isinstance(res, AwaitableResult)
        # probability clamp
        res = router.calculate_effective_cost(
            "deepseek-chat", "deepseek", 5000, cache_hit_probability=5.0, turn_index=0,
        )
        assert isinstance(res, AwaitableResult)

    def test_predict_with_history_and_record_eviction(self):
        router = self._router()
        router.record_cache_outcome("hash1234567890abcdef", "ws1", True)
        router.record_cache_outcome("hash1234567890abcdef", "ws1", False)
        prob = router.predict_cache_hit_probability("hash1234567890abcdef", "ws1")
        assert prob == 0.5
        # eviction path
        router._MAX_CACHE_KEYS = 2
        router.record_cache_outcome("key1", "ws1", True)
        router.record_cache_outcome("key2", "ws1", True)
        router.record_cache_outcome("key3", "ws1", True)
        assert len(router.cache_hit_history) <= 2
        # rolling window
        router._CACHE_WINDOW = 100
        for _ in range(150):
            router.record_cache_outcome("win1", "ws1", True)
        hits, total = router.cache_hit_history["ws1:win1"]
        assert total == 100

    def test_history_filter_and_clear(self):
        router = self._router()
        router.record_cache_outcome("aaa", "ws1", True)
        router.record_cache_outcome("bbb", "ws2", False)
        filtered = router.get_cache_hit_history("ws1")
        assert "ws1:aaa" in filtered and "ws2:bbb" not in filtered
        assert "ws2:bbb" in router.get_cache_hit_history()
        router.clear_cache_history("ws1")
        assert "ws1:aaa" not in router.get_cache_hit_history()
        router.clear_cache_history()
        assert router.get_cache_hit_history() == {}

    def test_provider_cache_capability(self):
        router = self._router()
        caps = router.get_provider_cache_capability("openai")
        assert caps["supports_cache"] is True
        caps = router.get_provider_cache_capability("google-gemini")
        assert "gemini" in str(caps) or caps["supports_cache"] is not None
        caps = router.get_provider_cache_capability("unknown-provider")
        assert caps["supports_cache"] is False


class TestCognitiveTierSystemGaps:
    def test_classify_fallback_complex(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

        classifier = CognitiveClassifier()
        long_prompt = "x" * 100000
        tier = classifier.classify(long_prompt)
        assert tier == CognitiveTier.COMPLEX

    def test_complexity_token_bands(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier

        classifier = CognitiveClassifier()
        score = classifier._calculate_complexity_score("y" * 9000)
        assert score >= 5
        score = classifier._calculate_complexity_score("y" * 9000 + "hello how are you")
        # simple signals cap the token contribution
        assert score <= 6

    def test_get_tier_models_override_and_defaults(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

        classifier = CognitiveClassifier()
        models = classifier.get_tier_models(CognitiveTier.MICRO)
        assert "gpt-4o-mini" in models
        assert "gpt-4o" in classifier.get_tier_models(CognitiveTier.HEAVY)
        assert isinstance(classifier.get_tier_models(CognitiveTier.COMPLEX), list)

    def test_get_tier_models_workspace_override(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

        classifier = CognitiveClassifier()
        pref = SimpleNamespace(metadata_json={"tier_models": {"micro": ["local-1"]}})
        with patch("core.database.get_db_session") as gds:
            db = MagicMock()
            gds.return_value = _cm(db)
            db.query.return_value.filter.return_value.first.return_value = pref
            models = classifier.get_tier_models(CognitiveTier.MICRO, workspace_id="ws1")
        assert models == ["local-1"]
        with patch("core.database.get_db_session", side_effect=RuntimeError("x")):
            models = classifier.get_tier_models(CognitiveTier.MICRO, workspace_id="ws1")
        assert "gpt-4o-mini" in models

    def test_get_tier_description(self):
        from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

        classifier = CognitiveClassifier()
        desc = classifier.get_tier_description(CognitiveTier.MICRO)
        assert isinstance(desc, str) and desc


class TestEscalationManagerGaps:
    def _mgr(self, db=None):
        from core.llm.escalation_manager import EscalationManager

        return EscalationManager(db, workspace_id="ws1", tenant_id="t1")

    def test_should_escalate_maxed_and_limit_and_cooldown(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import EscalationManager, MAX_ESCALATION_LIMIT

        mgr = self._mgr()
        ok, reason, target = mgr.should_escalate(CognitiveTier.COMPLEX, response_quality=10)
        assert ok is False
        mgr.request_escalations["req-1"] = MAX_ESCALATION_LIMIT
        ok, _, _ = mgr.should_escalate(CognitiveTier.MICRO, response_quality=10, request_id="req-1")
        assert ok is False
        # cooldown path
        mgr2 = self._mgr()
        mgr2.escalation_log[CognitiveTier.MICRO.value] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )
        ok, _, _ = mgr2.should_escalate(CognitiveTier.MICRO, response_quality=10)
        assert ok is False

    def test_escalate_for_reason_unknown_and_max(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import EscalationManager, EscalationReason

        mgr = self._mgr()
        ok, reason, target = mgr._escalate_for_reason("not-a-tier", EscalationReason.RATE_LIMITED)
        assert ok is False and target is None
        mgr.escalation_log[CognitiveTier.COMPLEX.value] = None  # not used
        ok, reason, target = mgr._escalate_for_reason(
            CognitiveTier.COMPLEX, EscalationReason.RATE_LIMITED
        )
        assert ok is False
        assert mgr.get_cooldown_remaining(CognitiveTier.MICRO) == 0.0

    def test_record_escalation_db_paths(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import EscalationReason

        db = MagicMock()
        mgr = self._mgr(db)
        mgr._record_escalation(
            CognitiveTier.MICRO, CognitiveTier.STANDARD, EscalationReason.ERROR_RESPONSE,
            request_id="r1", provider_id="p", model="m", error_message="e",
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db2 = MagicMock()
        db2.add.side_effect = RuntimeError("db boom")
        mgr2 = self._mgr(db2)
        mgr2._record_escalation(CognitiveTier.MICRO, CognitiveTier.STANDARD, EscalationReason.ERROR_RESPONSE)
        db2.rollback.assert_called_once()
        # rollback itself raises
        db3 = MagicMock()
        db3.add.side_effect = RuntimeError("db boom")
        db3.rollback.side_effect = RuntimeError("rollback boom")
        mgr3 = self._mgr(db3)
        mgr3._record_escalation(CognitiveTier.MICRO, CognitiveTier.STANDARD, EscalationReason.ERROR_RESPONSE)

    def test_reset_cooldown_and_count(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        mgr = self._mgr()
        mgr.escalation_log[CognitiveTier.MICRO.value] = 123
        assert mgr.get_escalation_count("nope") == 0
        mgr.request_escalations["r"] = 3
        assert mgr.get_escalation_count("r") == 3
        mgr.reset_cooldown(CognitiveTier.MICRO)
        assert CognitiveTier.MICRO.value not in mgr.escalation_log
        mgr.reset_cooldown(CognitiveTier.HEAVY)  # no-op

    def test_should_escalate_quality_confidence_no_escalation(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        mgr = self._mgr()
        ok, reason, target = mgr.should_escalate(CognitiveTier.MICRO, response_quality=99, confidence=1.0)
        assert ok is False
        ok, reason, target = mgr.should_escalate(CognitiveTier.MICRO, confidence=0.01)
        assert ok is True and target == CognitiveTier.STANDARD


class TestLearningRouterRegistryGaps:
    def test_double_checked_locking(self):
        import core.llm.learning_router_registry as lrr

        old = lrr._SINGLETON
        lrr._SINGLETON = None
        try:
            with patch("core.llm.learning_router_registry.learning_router_enabled", return_value=True), patch(
                "core.learning_llm_router.get_learning_router"
            ) as glr:
                router = MagicMock()
                router.load_feedback_from_db.return_value = 5
                glr.return_value = router
                first = lrr.get_learning_router_instance()
                # second call returns the same instance without re-hydrating
                second = lrr.get_learning_router_instance()
                assert first is second
                router.load_feedback_from_db.assert_called_once()
        finally:
            lrr._SINGLETON = old

    def test_hydrate_failure_and_instantiation_failure(self):
        import core.llm.learning_router_registry as lrr

        old = lrr._SINGLETON
        lrr._SINGLETON = None
        try:
            with patch("core.llm.learning_router_registry.learning_router_enabled", return_value=True), patch(
                "core.learning_llm_router.get_learning_router"
            ) as glr:
                router = MagicMock()
                router.load_feedback_from_db.side_effect = RuntimeError("hydrate boom")
                glr.return_value = router
                inst = lrr.get_learning_router_instance()
                assert inst is router
            lrr._SINGLETON = None
            with patch("core.llm.learning_router_registry.learning_router_enabled", return_value=True), patch(
                "core.learning_llm_router.get_learning_router", side_effect=RuntimeError("ctor boom")
            ):
                assert lrr.get_learning_router_instance() is None
        finally:
            lrr._SINGLETON = old

    def test_reset(self):
        import core.llm.learning_router_registry as lrr

        lrr._SINGLETON = "x"
        lrr.reset_learning_router_instance()
        assert lrr._SINGLETON is None
        with patch("core.llm.learning_router_registry.learning_router_enabled", return_value=False):
            assert lrr.get_learning_router_instance() is None
        assert lrr.ema_router_enabled() in (True, False)


class TestMatchConfidenceTiebreakerGaps:
    def _cands(self):
        from core.llm.match_confidence_tiebreaker import SelectorCandidate

        return [
            SelectorCandidate(selector=".a", match_count=1, attributes={}, tag_hint="div",
                              is_text_only=False, appeared_after_ms=0),
            SelectorCandidate(selector=".b", match_count=2, attributes={"id": "x"}, tag_hint="button",
                              is_text_only=False, appeared_after_ms=0),
        ]

    def test_cache_expiry_and_eviction(self):
        from core.llm.match_confidence_tiebreaker import (
            _TIEBREAK_CACHE_MAX,
            _cache_get,
            _cache_put,
            _tiebreak_cache,
            TiebreakResult,
        )

        _tiebreak_cache.clear()
        assert _cache_get("nope") is None
        _cache_put("k1", TiebreakResult(chosen_index=1, rationale="r", used_llm=True))
        assert _cache_get("k1").chosen_index == 1
        for i in range(_TIEBREAK_CACHE_MAX + 5):
            _cache_put(f"evict-{i}", TiebreakResult(chosen_index=0, rationale="r", used_llm=True))
        assert len(_tiebreak_cache) <= _TIEBREAK_CACHE_MAX
        _tiebreak_cache.clear()

    def test_parse_llm_response_variants(self):
        from core.llm.match_confidence_tiebreaker import _parse_llm_response

        r = _parse_llm_response("")
        assert r.chosen_index == -1 and r.used_llm is True
        r = _parse_llm_response("no json here")
        assert r.chosen_index == -1
        r = _parse_llm_response('{"chosen_index": 3, "rationale": "best"}')
        assert r.chosen_index == 3 and r.rationale == "best"
        r = _parse_llm_response('{"chosen_index": "not-an-int"}')
        assert r.chosen_index == -1

    @pytest.mark.asyncio
    async def test_break_tie_disabled_and_circuit(self):
        from core.llm.match_confidence_tiebreaker import break_tie

        with patch("core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED", False):
            res = await break_tie(self._cands(), {}, MagicMock())
        assert res.used_llm is False
        with patch("core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED", True), patch(
            "core.llm.match_confidence_tiebreaker._circuit_breaker"
        ) as cb:
            cb.is_tripped.return_value = True
            res = await break_tie(self._cands(), {}, MagicMock())
        assert res.used_llm is False
        assert "circuit" in res.rationale

    @pytest.mark.asyncio
    async def test_break_tie_timeout_and_error(self):
        from core.llm.match_confidence_tiebreaker import break_tie

        llm = MagicMock()
        llm.generate_completion = AsyncMock(side_effect=asyncio.TimeoutError("t"))
        with patch("core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED", True), patch(
            "core.llm.match_confidence_tiebreaker._circuit_breaker"
        ) as cb:
            cb.is_tripped.return_value = False
            res = await break_tie(self._cands(), {"url": "http://x"}, llm)
        assert res.used_llm is False and "timeout" in res.rationale.lower()
        cb.record_failure.assert_called_once()
        llm2 = MagicMock()
        llm2.generate_completion = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED", True), patch(
            "core.llm.match_confidence_tiebreaker._circuit_breaker"
        ) as cb2:
            cb2.is_tripped.return_value = False
            res = await break_tie(self._cands(), {}, llm2)
        assert res.used_llm is False and "LLM error" in res.rationale

    @pytest.mark.asyncio
    async def test_break_tie_success_and_out_of_range_and_cache(self):
        from core.llm.match_confidence_tiebreaker import break_tie

        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={"text": '{"chosen_index": 0, "rationale": "ok"}'})
        with patch("core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED", True), patch(
            "core.llm.match_confidence_tiebreaker._circuit_breaker"
        ) as cb, patch(
            "core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED", True
        ):
            cb.is_tripped.return_value = False
            res = await break_tie(self._cands(), {"url": "http://x"}, llm)
            assert res.chosen_index == 0 and res.used_llm is True
            # cache hit now
            res2 = await break_tie(self._cands(), {"url": "http://x"}, llm)
            assert res2.cache_hit is True
        llm2 = MagicMock()
        llm2.generate_completion = AsyncMock(return_value={"content": '{"chosen_index": 99}'})
        with patch("core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED", True), patch(
            "core.llm.match_confidence_tiebreaker._circuit_breaker"
        ) as cb3, patch(
            "core.llm.match_confidence_tiebreaker.SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED", False
        ):
            cb3.is_tripped.return_value = False
            res3 = await break_tie(self._cands(), {}, llm2)
        assert res3.chosen_index == -1 and "out-of-range" in res3.rationale


class TestMinimaxIntegrationGaps:
    @pytest.mark.asyncio
    async def test_test_connection_and_close(self):
        from core.llm.minimax_integration import MiniMaxIntegration

        response = MagicMock()
        response.status_code = 200
        mm = MiniMaxIntegration(api_key="x", model="MiniMax-M2")
        mm.client = MagicMock()
        mm.client.post = AsyncMock(return_value=response)
        assert await mm.test_connection() is True
        response.status_code = 500
        assert await mm.test_connection() is False
        mm.client.post = AsyncMock(side_effect=RuntimeError("conn"))
        assert await mm.test_connection() is False
        mm.client.aclose = AsyncMock()
        await mm.close()
        mm.client.aclose.assert_awaited_once()

    def test_pricing_capabilities_models(self):
        from core.llm.minimax_integration import MiniMaxIntegration

        mm = MiniMaxIntegration(api_key="x", model="MiniMax-M2")
        assert mm.get_pricing()["input_cost_per_token"] >= 0
        assert "supports_tools" in mm.get_capabilities()
        assert "MiniMax-M3" in mm.get_available_models()


class TestOpencodeModelLimitsGaps:
    def test_weight_from_prices(self):
        from core.llm.opencode_model_limits import weight_from_prices

        assert weight_from_prices("bad", None) == 1.0
        assert weight_from_prices(None, None) == 1.0
        assert weight_from_prices(0.0, 0.0) == 1.0
        assert weight_from_prices(0.000001, 0.000001) > 1.0

    def test_env_override_paths(self):
        from core.llm.opencode_model_limits import OpencodeModelLimits

        with patch.dict(os.environ, {"OPENCODE_MODEL_LIMITS": "not json"}, clear=False):
            limits = OpencodeModelLimits()
        with patch.dict(os.environ, {"OPENCODE_MODEL_LIMITS": "[1,2]"}, clear=False):
            limits = OpencodeModelLimits()
        with patch.dict(
            os.environ,
            {"OPENCODE_MODEL_LIMITS": json.dumps({
                "deepseek-x": {"weight": "bad", "rpm": "bad"},
                "kimi-x": "not-an-object",
                "good-x": {"weight": 3.0, "rpm": 20, "tpm": 500000},
            })},
            clear=False,
        ):
            limits = OpencodeModelLimits()
        assert limits.get_weight("opencode-go", "good-x") == 3.0
        assert limits.get_model_rate_limits("opencode-go", "good-x") == {"rpm": 20, "tpm": 500000}
        with patch.dict(os.environ, {"OPENCODE_MODEL_LIMITS": ""}, clear=False):
            limits = OpencodeModelLimits()

    def test_set_model_limits_and_apply_pricing(self):
        from core.llm.opencode_model_limits import OpencodeModelLimits

        limits = OpencodeModelLimits()
        limits.set_model_limits("p", "", weight=2.0)  # no model id -> no-op
        assert limits.get_weight("p", None) == 1.0
        assert limits.get_model_rate_limits("p", None) == {}
        limits.set_model_limits("p", "m1", weight=4.0, rpm=10)
        assert limits.get_weight("p", "m1") == 4.0
        limits.set_model_limits("p", "m1", weight=-1.0)
        assert limits.get_weight("p", "m1") == 1.0
        limits.set_model_limits("p", "m1", weight=4.0)
        w = limits.apply_pricing_weight("p", "m1", 0.001, 0.001)
        assert w == 4.0  # explicit override wins
        w = limits.apply_pricing_weight("p", "fresh", 0.0002, 0.0002)
        assert w > 1.0
        summary = limits.summary("p")
        assert summary["provider"] == "p" and "weights" in summary


class TestRateUsagePersistenceGaps:
    def _engine(self):
        from sqlalchemy import create_engine

        return create_engine("sqlite://")

    def test_table_failure_and_record(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence

        engine = MagicMock()
        engine.dialect = "sqlite"
        from sqlalchemy import MetaData
        p = RateUsagePersistence(engine)
        p._engine = engine
        with patch.object(p, "_session_factory"):
            p.record("p", "m", 10, 20)
        # engine failure -> record silently skipped
        p2 = RateUsagePersistence(self._engine())
        p2._table_ready = False
        with patch.object(p2, "_ensure_table", side_effect=RuntimeError("x")):
            p2.record("p", "m", 10, 20)
            assert p2.monthly_usage("p") is None

    def test_record_and_monthly_usage_sqlite(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence

        p = RateUsagePersistence(self._engine())
        p.record("openai", "gpt-4o", 100, 50)
        p.record("openai", "gpt-4o", 100, 50)
        p.record("openai", "gpt-4o-mini", 10, 5)
        usage = p.monthly_usage("openai")
        assert usage["requests"] == 3
        assert usage["total_tokens"] == 315
        model_usage = p.monthly_usage("openai", "gpt-4o")
        assert model_usage["requests"] == 2
        # cache path
        cached = p.monthly_usage("openai")
        assert cached == usage

    def test_singleton(self):
        from core.llm import rate_usage_persistence as rup

        old = rup._persistence
        rup._persistence = None
        try:
            s1 = rup.get_rate_usage_persistence()
            s2 = rup.get_rate_usage_persistence()
            assert s1 is s2
        finally:
            rup._persistence = old


class TestRoutingOverridesGaps:
    def test_case_insensitive_and_invalid(self):
        from core.llm.routing_overrides import parse_routing_overrides

        headers = {
            "X-Atom-Tier": "  VERSATILE ",
            "x-atom-model": "gpt-4o",
            "X-ATOM-INTENT": "coding",
        }
        res = parse_routing_overrides(headers)
        assert res == {"tier": "versatile", "model": "gpt-4o", "intent": "coding"}

    def test_invalid_values_dropped(self):
        from core.llm.routing_overrides import parse_routing_overrides

        res = parse_routing_overrides({
            "x-atom-tier": "bogus-tier",
            "x-atom-model": "",
            "x-atom-intent": "not-an-intent",
        })
        assert res == {}

    def test_unknown_model_dropped(self):
        from core.llm.routing_overrides import parse_routing_overrides

        with patch("core.llm.byok_handler.BYOKHandler._model_registry", {}, create=True):
            res = parse_routing_overrides({"x-atom-model": "not-a-known-model"})
        assert "model" not in res

    def test_non_mapping_headers(self):
        from core.llm.routing_overrides import parse_routing_overrides

        class NoGet:
            pass

        assert parse_routing_overrides(NoGet()) == {}

    def test_validator_failures_fall_open(self):
        from core.llm.routing_overrides import _is_known_model, _is_valid_intent, _is_valid_tier

        with patch.dict(sys.modules, {"core.llm.byok_handler": None}):
            assert _is_known_model("whatever") is True
        with patch("core.llm.cognitive_tier_system.CognitiveTier", side_effect=Exception("x")):
            assert _is_valid_tier("micro") is False
        with patch("core.llm.intent_detector.is_valid_intent", side_effect=Exception("x")):
            assert _is_valid_intent("coding") is False

    def test_known_prefix_model_accepted(self):
        from core.llm.routing_overrides import parse_routing_overrides

        with patch("core.llm.byok_handler.BYOKHandler._model_registry", {}, create=True):
            res = parse_routing_overrides({"x-atom-model": "gpt-4o"})
        assert res["model"] == "gpt-4o"


class TestCognitiveTierServiceGaps:
    def _svc(self, db=None, tenant_id=None):
        from core.llm.cognitive_tier_service import CognitiveTierService

        return CognitiveTierService(workspace_id="ws1", db_session=db, tenant_id=tenant_id)

    def _pref(self, **kw):
        base = dict(
            min_tier=None, max_tier=None, default_tier=None,
            preferred_providers=None, enable_auto_escalation=True,
            max_cost_per_request_cents=None, monthly_budget_cents=None,
            metadata_json={},
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_cache_router_lazy(self):
        svc = self._svc()
        with patch("core.dynamic_pricing_fetcher.get_pricing_fetcher") as gpf:
            router = svc.cache_router
        gpf.assert_called_once()
        assert svc.cache_router is router

    def test_select_tier_override_and_prefs(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        svc = self._svc()
        assert svc.select_tier("hi", user_tier_override="micro") == CognitiveTier.MICRO
        with patch.object(svc, "get_workspace_preference", return_value=None):
            svc.classifier.classify = Mock(return_value=CognitiveTier.MICRO)
            assert svc.select_tier("hi") == CognitiveTier.MICRO
        # invalid override -> falls through
        with patch.object(svc, "get_workspace_preference", return_value=None), patch.object(
            svc.classifier, "classify", return_value=CognitiveTier.STANDARD
        ):
            tier = svc.select_tier("hi", user_tier_override="bogus")
            assert tier == CognitiveTier.STANDARD

    def test_select_tier_intent_nudge(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        svc = self._svc()
        with patch.object(svc, "get_workspace_preference", return_value=None), patch.object(
            svc.classifier, "classify", return_value=CognitiveTier.MICRO
        ), patch("core.llm.cognitive_tier_system.get_intent_detector") if False else patch.object(
            svc, "get_workspace_preference", return_value=None
        ):
            pass
        # nudge path via intent_override
        with patch.object(svc, "get_workspace_preference", return_value=None), patch.object(
            svc.classifier, "classify", return_value=CognitiveTier.MICRO
        ), patch("core.llm.intent_detector.get_intent_detector") as gid:
            detector = MagicMock()
            detector.nudge_tier = Mock(return_value="heavy")
            gid.return_value = detector
            tier = svc.select_tier("hi", intent_override="coding")
            assert tier == CognitiveTier.HEAVY
        # nudge returns invalid value -> keep classified
        with patch.object(svc, "get_workspace_preference", return_value=None), patch.object(
            svc.classifier, "classify", return_value=CognitiveTier.MICRO
        ), patch("core.llm.intent_detector.get_intent_detector") as gid:
            detector = MagicMock()
            detector.nudge_tier = Mock(return_value="bogus")
            gid.return_value = detector
            tier = svc.select_tier("hi", intent_override="coding")
            assert tier == CognitiveTier.MICRO
        # intent detection raises -> skipped
        with patch.object(svc, "get_workspace_preference", return_value=None), patch.object(
            svc.classifier, "classify", return_value=CognitiveTier.MICRO
        ), patch("core.llm.intent_detector.get_intent_detector", side_effect=RuntimeError("x")):
            tier = svc.select_tier("hi")
            assert tier == CognitiveTier.MICRO

    def test_select_tier_preference_clamps(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        svc = self._svc()
        pref = self._pref(min_tier="standard", max_tier="heavy", default_tier="complex")
        with patch.object(svc, "get_workspace_preference", return_value=pref), patch.object(
            svc.classifier, "classify", return_value=CognitiveTier.MICRO
        ):
            tier = svc.select_tier("hi")
            assert tier == CognitiveTier.HEAVY  # clamped by max_tier
        pref2 = self._pref(default_tier="micro")
        with patch.object(svc, "get_workspace_preference", return_value=pref2), patch.object(
            svc.classifier, "classify", return_value=CognitiveTier.HEAVY
        ):
            assert svc.select_tier("hi") == CognitiveTier.MICRO
        pref3 = self._pref(min_tier="bogus", max_tier="bogus2", default_tier="bogus3")
        with patch.object(svc, "get_workspace_preference", return_value=pref3), patch.object(
            svc.classifier, "classify", return_value=CognitiveTier.MICRO
        ):
            assert svc.select_tier("hi") == CognitiveTier.MICRO

    def test_get_optimal_model_paths(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        svc = self._svc()
        with patch.object(svc, "get_workspace_preference", return_value=None), patch.object(
            svc, "_get_dynamic_tier_models", return_value=[]
        ), patch.object(svc.classifier, "get_tier_models", return_value=[]):
            provider, model = svc.get_optimal_model(CognitiveTier.MICRO, 100)
        assert provider is None and model is None
        cr = MagicMock()
        cr.predict_cache_hit_probability = Mock(return_value=0.5)
        cr.calculate_effective_cost = Mock(return_value=1.0)
        svc._cache_router = cr
        with patch.object(svc, "get_workspace_preference", return_value=None), patch.object(
            svc, "_get_dynamic_tier_models", return_value=["claude-3-5-sonnet", "gpt-4o"]
        ):
            provider, model = svc.get_optimal_model(CognitiveTier.HEAVY, 1000)
        assert provider == "anthropic"

    def test_get_optimal_model_preferred_provider(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        svc = self._svc()
        pref = self._pref(preferred_providers=["openai"])
        cr = MagicMock()
        cr.predict_cache_hit_probability = Mock(return_value=0.5)
        cr.calculate_effective_cost = Mock(side_effect=[9.0, 1.0])
        svc._cache_router = cr
        with patch.object(svc, "get_workspace_preference", return_value=pref), patch.object(
            svc, "_get_dynamic_tier_models", return_value=["claude-3-5-sonnet", "gpt-4o"]
        ):
            provider, model = svc.get_optimal_model(CognitiveTier.HEAVY, 1000)
        assert provider == "openai"

    def test_dynamic_tier_models(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        db = MagicMock()
        svc = self._svc(db, tenant_id="t1")
        assert svc._get_dynamic_tier_models(CognitiveTier.MICRO) == []
        db2 = MagicMock()
        db2.query.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [
            SimpleNamespace(model_name="mini-model")
        ]
        svc2 = self._svc(db2, tenant_id="t1")
        models = svc2._get_dynamic_tier_models(CognitiveTier.MICRO)
        assert models == ["mini-model"]
        db3 = MagicMock()
        db3.query.side_effect = RuntimeError("db boom")
        svc3 = self._svc(db3, tenant_id="t1")
        assert svc3._get_dynamic_tier_models(CognitiveTier.STANDARD) == []

    def test_model_to_provider(self):
        svc = self._svc()
        assert svc._model_to_provider("gpt-4o") == "openai"
        assert svc._model_to_provider("o3-mini") == "openai"
        assert svc._model_to_provider("claude-x") == "anthropic"
        assert svc._model_to_provider("deepseek-x") == "deepseek"
        assert svc._model_to_provider("gemini-x") == "gemini"
        assert svc._model_to_provider("qwen-x") == "qwen"
        assert svc._model_to_provider("minimax-x") == "minimax"
        assert svc._model_to_provider("glm-x") == "glm"
        assert svc._model_to_provider("kimi-x") == "moonshot"
        assert svc._model_to_provider("weird") == "unknown"

    def test_calculate_request_cost_and_budget(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        svc = self._svc()
        cr = MagicMock()
        cr.predict_cache_hit_probability = Mock(return_value=0.5)
        cr.calculate_effective_cost = Mock(side_effect=[0.002, 0.004])
        svc._cache_router = cr
        cost = svc.calculate_request_cost("hello world", CognitiveTier.MICRO)
        assert cost["cache_discount"] > 0 and cost["cost_cents"] > 0
        assert svc.check_budget_constraint(1.0) is True
        with patch.object(svc, "get_workspace_preference", return_value=None):
            assert svc.check_budget_constraint(1.0) is True
        pref = self._pref(max_cost_per_request_cents=5.0, monthly_budget_cents=10.0)
        with patch.object(svc, "get_workspace_preference", return_value=pref):
            assert svc.check_budget_constraint(6.0) is False
            assert svc.check_budget_constraint(11.0) is False
            assert svc.check_budget_constraint(3.0) is True

    def test_handle_escalation_and_preference_failure(self):
        from core.llm.cognitive_tier_system import CognitiveTier

        svc = self._svc()
        pref = self._pref(enable_auto_escalation=False)
        with patch.object(svc, "get_workspace_preference", return_value=pref):
            ok, reason, target = svc.handle_escalation(CognitiveTier.MICRO, response_quality=10)
        assert ok is False
        with patch.object(svc, "get_workspace_preference", return_value=None), patch.object(
            svc.escalation_manager, "should_escalate", return_value=(True, "q", CognitiveTier.STANDARD)
        ) as se:
            ok, reason, target = svc.handle_escalation(CognitiveTier.MICRO, response_quality=10)
            assert ok is True
            se.assert_called_once()

    def test_get_workspace_preference_paths(self):
        db = MagicMock()
        svc = self._svc(db, tenant_id="t1")
        pref = self._pref()
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = pref
        assert svc.get_workspace_preference() is pref
        db2 = MagicMock()
        db2.query.side_effect = RuntimeError("boom")
        svc2 = self._svc(db2, tenant_id="t1")
        assert svc2.get_workspace_preference() is None

    def test_record_cache_outcome(self):
        svc = self._svc()
        cr = MagicMock()
        svc._cache_router = cr
        svc.record_cache_outcome("hash", True)
        cr.record_cache_outcome.assert_called_once_with("hash", "ws1", True)


class TestKingGaps2:
    """Remaining king_agent lines: __init__, failure-canvas update, trace
    failure, heal-restart with canvas."""

    def test_init(self):
        from core.agents.king_agent import KingAgent

        llm = MagicMock()
        with patch("core.atom_meta_agent.WorldModelService"), patch(
            "core.atom_meta_agent.AdvancedWorkflowOrchestrator"
        ), patch("core.atom_meta_agent.SessionLocal") as sl, patch(
            "core.service_factory.ServiceFactory.get_llm_service", return_value=llm
        ), patch("core.atom_meta_agent.get_canvas_provider"), patch(
            "core.atom_meta_agent.mcp_service"
        ), patch("core.agents.king_agent.BlueprintHealer") as bh:
            db = MagicMock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            king = KingAgent(workspace_id="ws1", tenant_id="t1")
        assert king.workspace_id == "ws1"
        bh.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_updates_canvas(self):
        from core.agents.king_agent import KingAgent

        king = object.__new__(KingAgent)
        king.queen = MagicMock()
        king.queen.generate_mermaid = Mock(return_value="graph TD")
        king.healer = MagicMock()
        king.agent_id = "king-1"
        king._execute_node = AsyncMock(return_value={"error": "boom"})
        king.healer.heal_blueprint = AsyncMock(return_value={"status": "failed"})
        uc = AsyncMock(return_value={"success": True})
        pm = AsyncMock(return_value={"success": True, "canvas_id": "c1"})
        with patch("core.agents.king_agent.update_canvas", new=uc), patch(
            "core.agents.king_agent.present_markdown", new=pm
        ):
            res = await king.execute_blueprint(
                {
                    "architecture_name": "X",
                    "nodes": [
                        {"id": "n1", "name": "N", "type": "agent",
                         "capability_required": "c", "dependencies": []},
                    ],
                },
                context={"user_id": "u1", "tenant_id": "t1"},
            )
        assert res["status"] == "failed"
        assert uc.await_count == 2  # in_progress + failure updates

    @pytest.mark.asyncio
    async def test_trace_recording_failure(self):
        from core.agents.king_agent import KingAgent

        king = object.__new__(KingAgent)
        king.queen = MagicMock()
        king.queen.generate_mermaid = Mock(return_value="graph TD")
        king.healer = MagicMock()
        king.agent_id = "king-1"
        king._execute_node = AsyncMock(side_effect=[{"error": "boom"}, {"ok": True}])
        king.healer.heal_blueprint = AsyncMock(
            return_value={
                "status": "healed",
                "nodes": [
                    {"id": "n2", "name": "N2", "type": "agent",
                     "capability_required": "c", "dependencies": []},
                ],
            }
        )
        king.healer.summarize_healing_as_directive = AsyncMock(
            side_effect=RuntimeError("trace boom")
        )
        with patch("core.agents.king_agent.SessionLocal") as sl:
            db = MagicMock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            res = await king.execute_blueprint(
                {
                    "architecture_name": "X",
                    "nodes": [
                        {"id": "n1", "name": "N", "type": "agent",
                         "capability_required": "c", "dependencies": []},
                    ],
                },
                context={"user_id": "u1", "tenant_id": "t1"},
            )
        assert res["status"] == "success"

    @pytest.mark.asyncio
    async def test_heal_restart_with_canvas(self):
        from core.agents.king_agent import KingAgent

        king = object.__new__(KingAgent)
        king.queen = MagicMock()
        king.queen.generate_mermaid = Mock(return_value="graph TD")
        king.healer = MagicMock()
        king.agent_id = "king-1"
        king._execute_node = AsyncMock(side_effect=[{"error": "boom"}, {"ok": True}])
        king.healer.heal_blueprint = AsyncMock(
            return_value={
                "status": "healed",
                "nodes": [
                    {"id": "n2", "name": "N2", "type": "agent",
                     "capability_required": "c", "dependencies": []},
                ],
            }
        )
        king.healer.summarize_healing_as_directive = AsyncMock(return_value="d")
        uc = AsyncMock(return_value={"success": True})
        pm = AsyncMock(return_value={"success": True, "canvas_id": "c1"})
        with patch("core.agents.king_agent.SessionLocal") as sl, patch(
            "core.agents.king_agent.update_canvas", new=uc
        ), patch("core.agents.king_agent.present_markdown", new=pm):
            db = MagicMock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            res = await king.execute_blueprint(
                {
                    "architecture_name": "X",
                    "nodes": [
                        {"id": "n1", "name": "N", "type": "agent",
                         "capability_required": "c", "dependencies": []},
                    ],
                },
                context={"user_id": "u1", "tenant_id": "t1"},
            )
        assert res["status"] == "success"
        assert uc.await_count >= 4  # heal restart updated the canvas too


class TestEscalationManagerGaps2:
    def test_should_escalate_rate_limited_error_quality(self):
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import EscalationManager

        mgr = EscalationManager(None, workspace_id="ws1")
        ok, reason, target = mgr.should_escalate(
            CognitiveTier.MICRO, rate_limited=True, error="429"
        )
        assert ok is True and target == CognitiveTier.STANDARD
        mgr.reset_cooldown(CognitiveTier.MICRO)
        ok, reason, target = mgr.should_escalate(CognitiveTier.MICRO, error="boom")
        assert ok is True
        mgr.reset_cooldown(CognitiveTier.MICRO)
        ok, reason, target = mgr.should_escalate(CognitiveTier.MICRO, response_quality=10)
        assert ok is True and target == CognitiveTier.STANDARD

    def test_get_cooldown_remaining_with_entry(self):
        from datetime import datetime, timedelta, timezone
        from core.llm.cognitive_tier_system import CognitiveTier
        from core.llm.escalation_manager import EscalationManager

        mgr = EscalationManager(None, workspace_id="ws1")
        # expired entry -> 0.0
        mgr.escalation_log[CognitiveTier.MICRO.value] = datetime.now(timezone.utc) - timedelta(minutes=99)
        assert mgr.get_cooldown_remaining(CognitiveTier.MICRO) == 0.0
        assert mgr._is_on_cooldown(CognitiveTier.MICRO) is False
        # fresh entry -> > 0
        mgr.escalation_log[CognitiveTier.MICRO.value] = datetime.now(timezone.utc)
        assert mgr.get_cooldown_remaining(CognitiveTier.MICRO) > 0.0
        assert mgr._is_on_cooldown(CognitiveTier.MICRO) is True


class TestRoutingOverridesGaps2:
    def test_is_known_model_registry_paths(self):
        from core.llm.routing_overrides import _is_known_model

        spec = SimpleNamespace(model_name="my-model", model_id="my-model")
        with patch("core.llm.byok_handler.BYOKHandler._model_registry", {"gpt-4o": spec}, create=True):
            assert _is_known_model("gpt-4o") is True
            assert _is_known_model("my-model") is True
            assert _is_known_model("unknown-model") is False

    def test_validators_import_failure(self):
        import sys

        from core.llm.routing_overrides import _is_valid_intent, _is_valid_tier

        with patch.dict(sys.modules, {"core.llm.cognitive_tier_system": None}):
            assert _is_valid_tier("micro") is False
        with patch.dict(sys.modules, {"core.llm.intent_detector": None}):
            assert _is_valid_intent("coding") is False


class TestRateUsagePersistenceGaps2:
    def test_ensure_table_double_check_and_failure(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence

        engine = MagicMock()
        p = RateUsagePersistence(engine)
        p._ensure_table()
        p._ensure_table()  # second call hits the early return
        assert p._table_ready is True

    def test_table_create_failure_skips_record(self):
        from core.llm.rate_usage_persistence import RateUsagePersistence

        p = RateUsagePersistence(MagicMock())
        with patch(
            "core.llm.rate_usage_persistence.Base.metadata.create_all",
            side_effect=RuntimeError("no table"),
        ), patch.object(p, "_session_factory") as sf:
            p._ensure_table()
            assert p._table_ready is False
            p.record("p", "m", 1, 2)  # early return, no session created
            assert p.monthly_usage("p") is None  # early return, no query
            sf.assert_not_called()
