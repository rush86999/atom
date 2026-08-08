"""Coverage-push + bug-hunt tests for backend/tools (part 2).

Covers: data_analysis_tool, predictive_tools, creative_tool,
platform_management_tool.
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
# data_analysis_tool
# ============================================================================

class TestDataAnalysisTool:
    def test_validate_data_code(self):
        from tools.data_analysis_tool import _validate_data_code
        assert _validate_data_code("df.head(5)") is None
        assert _validate_data_code("import os") is not None
        assert _validate_data_code("def broken(:") is not None
        assert _validate_data_code("x = obj.__class__") is not None
        assert _validate_data_code("getattr(obj, 'x')") is not None
        assert _validate_data_code("obj.__getattribute__('x')") is not None
        with patch("core.sandbox_tripwire.check_python_ast", return_value="tripwire!"):
            assert _validate_data_code("df.head(1)") == "tripwire!"

    def test_validate_identifier(self):
        from tools.data_analysis_tool import _validate_identifier
        assert _validate_identifier("good_name", "f") is None
        assert _validate_identifier("1bad", "f") is not None
        assert _validate_identifier(123, "f") is not None
        assert _validate_identifier("has space", "f") is not None

    def _dm_mock(self, handle=None, df=None):
        dm = MagicMock()
        dm.load.return_value = handle
        dm.get_dataframe.return_value = df
        return dm

    async def test_load_dataset_success(self):
        handle = SimpleNamespace(row_count=10, columns=["a", "b"])
        handle.to_dict = Mock(return_value={"rows": 10})
        dm = self._dm_mock(handle=handle)
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import load_dataset
            res = await load_dataset("file.csv", "ds1", format="csv", session_id="s1")
        assert res["success"] is True and res["dataset"] == {"rows": 10}
        assert "10 rows" in res["message"]

    async def test_load_dataset_error(self):
        dm = MagicMock()
        dm.load.side_effect = RuntimeError("x")
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import load_dataset
            res = await load_dataset("file.csv", "ds1")
        assert res["success"] is False

    async def test_analyze_data_missing_dataset(self):
        dm = self._dm_mock(df=None)
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("ds1", "df.head()")
        assert res["success"] is False
        assert "not loaded" in res["error"]

    async def test_analyze_data_code_blocked(self):
        dm = self._dm_mock(df=MagicMock())
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("ds1", "import os")
        assert res["success"] is False
        assert "sandbox policy" in res["error"]

    def _runtime_result(self, success=False, stdout="", stderr="", exit_code=0):
        return SimpleNamespace(success=success, stdout=stdout, stderr=stderr, exit_code=exit_code)

    async def test_analyze_data_sandbox_json(self):
        df = MagicMock()
        df.to_json.return_value = '[{"a": 1}]'
        dm = self._dm_mock(df=df)
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=self._runtime_result(
            success=True, stdout='{"forecast": [1, 2]}'))
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", return_value=runtime), \
             patch("core.sandbox_policy.SandboxPolicy"):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("ds1", "print('x')", agent_id="a-1")
        assert res["success"] is True and res["results"] == {"forecast": [1, 2]}
        assert runtime.execute_python.await_args.kwargs["inputs"]["df"] == '[{"a": 1}]'

    async def test_analyze_data_sandbox_non_json(self):
        df = MagicMock()
        df.to_json.return_value = "[]"
        dm = self._dm_mock(df=df)
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=self._runtime_result(
            success=True, stdout="not json"))
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", return_value=runtime), \
             patch("core.sandbox_policy.SandboxPolicy"):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("ds1", "print('x')")
        assert res["success"] is True and res["output"] == "not json"

    async def test_analyze_data_sandbox_unavailable(self):
        df = MagicMock()
        df.to_json.return_value = "[]"
        dm = self._dm_mock(df=df)
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=self._runtime_result(exit_code=-1))
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", return_value=runtime), \
             patch("core.sandbox_policy.SandboxPolicy"):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("ds1", "print('x')")
        assert res["success"] is False
        assert "Sandbox execution unavailable" in res["error"]

    async def test_analyze_data_sandbox_failure(self):
        df = MagicMock()
        df.to_json.return_value = "[]"
        dm = self._dm_mock(df=df)
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=self._runtime_result(
            success=False, stderr="boom", stdout="out"))
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", return_value=runtime), \
             patch("core.sandbox_policy.SandboxPolicy"):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("ds1", "print('x')")
        assert res["success"] is False and "boom" in res["error"]

    async def test_analyze_data_sandbox_exception(self):
        df = MagicMock()
        df.to_json.return_value = "[]"
        dm = self._dm_mock(df=df)
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm), \
             patch("core.sandbox_runtime.get_runtime", side_effect=RuntimeError("no docker")):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("ds1", "print('x')")
        assert res["success"] is False
        assert "Sandbox execution unavailable" in res["error"]

    async def test_analyze_data_generic_error(self):
        dm = MagicMock()
        dm.get_dataframe.side_effect = RuntimeError("x")
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import analyze_data
            res = await analyze_data("ds1", "print('x')")
        assert res["success"] is False

    async def test_query_data(self):
        dm = MagicMock()
        dm.query.return_value = {"success": True, "rows": [1]}
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import query_data
            res = await query_data("ds1", "select * from df")
        assert res["success"] is True
        dm.query.side_effect = RuntimeError("x")
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            res2 = await query_data("ds1", "select 1")
        assert res2["success"] is False

    async def test_describe_data(self):
        dm = MagicMock()
        dm.describe.return_value = {"success": True, "stats": {}}
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import describe_data
            res = await describe_data("ds1")
        assert res["success"] is True
        dm.describe.side_effect = RuntimeError("x")
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            res2 = await describe_data("ds1")
        assert res2["success"] is False

    async def test_list_datasets(self):
        dm = MagicMock()
        dm.list_datasets.return_value = ["a", "b"]
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            from tools.data_analysis_tool import list_datasets
            res = await list_datasets(session_id="s1")
        assert res["success"] is True and res["count"] == 2
        dm.list_datasets.side_effect = RuntimeError("x")
        with patch("core.data.dataset_manager.get_dataset_manager", return_value=dm):
            res2 = await list_datasets()
        assert res2["success"] is False

    def test_register_data_analysis_tools(self):
        registry = MagicMock()
        from tools.data_analysis_tool import register_data_analysis_tools
        register_data_analysis_tools(registry)
        names = [c.kwargs["name"] for c in registry.register.call_args_list]
        assert names == ["load_dataset", "analyze_data", "query_data", "describe_data",
                         "list_datasets"]
        assert registry.register.call_args_list[1].kwargs["maturity_required"] == "SUPERVISED"


# ============================================================================
# predictive_tools
# ============================================================================

class TestPredictiveTools:
    async def test_forecast_validation(self):
        from tools.predictive_tools import forecast
        res = await forecast("ds", "1bad")
        assert res["success"] is False
        res = await forecast("ds", "sales", date_column="date!")
        assert res["success"] is False
        res = await forecast("ds", "sales", periods=True)
        assert res["success"] is False
        res = await forecast("ds", "sales", periods=0)
        assert res["success"] is False
        res = await forecast("ds", "sales", periods=400)
        assert res["success"] is False
        res = await forecast("ds", "sales", method="bogus")
        assert res["success"] is False

    async def _forecast_run(self, method, **kw):
        with patch("tools.data_analysis_tool.analyze_data",
                   AsyncMock(return_value={"success": True, "results": {"forecast": [1]}})) as ad:
            from tools.predictive_tools import forecast
            res = await forecast("ds", "sales", method=method, **kw)
        return res, ad

    async def test_forecast_linear(self):
        res, ad = await self._forecast_run("linear", periods=5)
        assert res["success"] is True
        assert res["governance"]["requires_review"] is True
        code = ad.await_args.kwargs["code"]
        assert "LinearRegression" in code and "5" in code

    async def test_forecast_moving_average(self):
        res, ad = await self._forecast_run("moving_average", periods=3)
        assert res["success"] is True
        assert "moving_average" in ad.await_args.kwargs["code"]

    async def test_forecast_exponential(self):
        res, ad = await self._forecast_run("exponential")
        assert res["success"] is True
        assert "ExponentialSmoothing" in ad.await_args.kwargs["code"]

    async def test_forecast_with_date_column(self):
        res, ad = await self._forecast_run("linear", date_column="date")
        assert "pd.to_datetime" in ad.await_args.kwargs["code"]

    async def test_forecast_failure_passthrough(self):
        with patch("tools.data_analysis_tool.analyze_data",
                   AsyncMock(return_value={"success": False, "error": "x"})):
            from tools.predictive_tools import forecast
            res = await forecast("ds", "sales")
        assert res["success"] is False

    async def test_run_model_validation(self):
        from tools.predictive_tools import run_model
        res = await run_model("ds", "1bad")
        assert res["success"] is False
        res = await run_model("ds", "y", feature_columns=["ok", "b ad"])
        assert res["success"] is False
        res = await run_model("ds", "y", test_size=0)
        assert res["success"] is False
        res = await run_model("ds", "y", test_size=1.5)
        assert res["success"] is False
        res = await run_model("ds", "y", test_size=True)
        assert res["success"] is False
        res = await run_model("ds", "y", model_type="bogus")
        assert res["success"] is False

    async def test_run_model_regression(self):
        with patch("tools.data_analysis_tool.analyze_data",
                   AsyncMock(return_value={"success": True, "results": {"mse": 1}})) as ad:
            from tools.predictive_tools import run_model
            res = await run_model("ds", "price", feature_columns=["sqft", "age"], test_size=0.3)
        assert res["success"] is True
        assert res["governance"]["review_status"] == "PENDING"
        code = ad.await_args.kwargs["code"]
        assert "LinearRegression" in code and "0.3" in code

    async def test_run_model_classification_no_features(self):
        with patch("tools.data_analysis_tool.analyze_data",
                   AsyncMock(return_value={"success": True, "results": {}})) as ad:
            from tools.predictive_tools import run_model
            res = await run_model("ds", "churn", model_type="classification")
        assert res["success"] is True
        code = ad.await_args.kwargs["code"]
        assert "RandomForestClassifier" in code
        assert "feature_cols = [c for c in df.columns" in code

    async def test_run_model_failure(self):
        with patch("tools.data_analysis_tool.analyze_data",
                   AsyncMock(return_value={"success": False, "error": "x"})):
            from tools.predictive_tools import run_model
            res = await run_model("ds", "y")
        assert res["success"] is False

    def test_register_predictive_tools(self):
        registry = MagicMock()
        from tools.predictive_tools import register_predictive_tools
        register_predictive_tools(registry)
        names = [c.kwargs["name"] for c in registry.register.call_args_list]
        assert names == ["forecast", "run_model"]
        assert registry.register.call_args_list[0].kwargs["maturity_required"] == "SUPERVISED"


# ============================================================================
# creative_tool
# ============================================================================

class TestCreativeTool:
    @pytest.fixture(autouse=True)
    def _ffmpeg_patch(self):
        self.service = MagicMock()
        self.service.validate_path = Mock()
        self.service.allowed_dirs = ["/app/data/media", "/app/data/exports"]
        self.service.trim_video = AsyncMock(return_value={"job_id": "j1"})
        self.service.convert_format = AsyncMock(return_value={"job_id": "j2"})
        self.service.generate_thumbnail = AsyncMock(return_value={"job_id": "j3"})
        self.service.extract_audio = AsyncMock(return_value={"job_id": "j4"})
        self.service.normalize_audio = AsyncMock(return_value={"job_id": "j5"})
        with patch("tools.creative_tool.FFmpegService", return_value=self.service):
            yield

    def _tool(self):
        from tools.creative_tool import FFmpegTool
        return FFmpegTool()

    def test_init_failure(self):
        with patch("tools.creative_tool.FFmpegService", side_effect=RuntimeError("no ffmpeg")):
            from tools.creative_tool import FFmpegTool
            tool = FFmpegTool()
        assert tool.service is None

    async def test_run_not_autonomous(self):
        tool = self._tool()
        res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="STUDENT")
        assert res["success"] is False
        assert "AUTONOMOUS" in res["error"]

    async def test_run_no_maturity(self):
        tool = self._tool()
        res = await tool._run("trim_video", "in.mp4", "out.mp4")
        assert res["success"] is False

    async def test_run_service_unavailable(self):
        with patch("tools.creative_tool.FFmpegService", side_effect=RuntimeError("x")):
            from tools.creative_tool import FFmpegTool
            tool = FFmpegTool()
            res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False
        assert "service" in res["error"].lower()

    async def test_run_path_validation_failure(self):
        tool = self._tool()
        self.service.validate_path.side_effect = ValueError("outside")
        res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False
        assert "path" in res["error"].lower()

    async def test_run_unknown_action(self):
        tool = self._tool()
        res = await tool._run("explode", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False
        assert "explode" in res["error"]

    async def test_run_success_sync_context(self):
        from tools.creative_tool import FFmpegTool
        with patch.object(FFmpegTool, "_execute_operation",
                          return_value={"job_id": "j1"}) as exec_op:
            tool = self._tool()
            res = await tool._run("trim_video", "in.mp4", "out.mp4",
                                  maturity_level="AUTONOMOUS", start_time="00:00:01",
                                  duration="00:01:00")
        assert res["success"] is True
        assert res["job_id"] == "j1"
        exec_op.assert_called_once()

    def test_execute_operation_trim(self):
        tool = self._tool()
        with patch("asyncio.get_event_loop") as gel:
            loop = MagicMock()
            loop.run_until_complete = Mock(side_effect=lambda c: self.service.trim_video.return_value)
            gel.return_value = loop
            res = tool._execute_operation("trim_video", "in.mp4", "out.mp4",
                                          start_time="00:00:01", duration="00:01:00")
        assert res["job_id"] == "j1"

    def test_execute_operation_new_loop(self):
        tool = self._tool()
        with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")), \
             patch("asyncio.new_event_loop") as nel, \
             patch("asyncio.set_event_loop") as sel:
            loop = MagicMock()
            loop.run_until_complete = Mock(side_effect=lambda c: self.service.convert_format.return_value)
            nel.return_value = loop
            res = tool._execute_operation("convert_format", "in.mov", "out.mp4", format="mp4")
        assert res["job_id"] == "j2"
        sel.assert_called_once_with(loop)

    def test_execute_operation_unknown(self):
        tool = self._tool()
        with pytest.raises(ValueError):
            tool._execute_operation("explode", "in.mp4", "out.mp4")

    async def test_execute_operation_inside_running_loop(self):
        tool = self._tool()
        res = tool._execute_operation("trim_video", "in.mp4", "out.mp4",
                                      start_time="00:00:01", duration="00:01:00")
        assert res == {"job_id": "j1"}

    @pytest.mark.parametrize("op,kwargs", [
        ("generate_thumbnail", {"timestamp": "00:00:02"}),
        ("extract_audio", {"format": "mp3"}),
        ("normalize_audio", {"target_lufs": -16.0}),
    ])
    def test_execute_operation_others(self, op, kwargs):
        tool = self._tool()
        with patch("asyncio.get_event_loop") as gel:
            loop = MagicMock()
            loop.run_until_complete = Mock(side_effect=lambda c: {"job_id": "j"})
            gel.return_value = loop
            res = tool._execute_operation(op, "in.mp4", "out.mp4", **kwargs)
        assert res["job_id"] == "j"

    def test_register_creative_tool(self):
        registry = MagicMock()
        from tools.creative_tool import register_creative_tool
        with patch("tools.creative_tool.FFmpegTool"):
            register_creative_tool(registry)
        assert registry.register.call_args.kwargs["name"] == "ffmpeg_edit"

    def test_register_creative_tool_failure(self):
        registry = MagicMock()
        from tools.creative_tool import register_creative_tool
        with patch("tools.creative_tool.FFmpegTool", side_effect=RuntimeError("x")):
            register_creative_tool(registry)
        registry.register.assert_not_called()


# ============================================================================
# platform_management_tool
# ============================================================================

class TestPlatformManagementTool:
    @pytest.fixture(autouse=True)
    def _pm_patch(self):
        self.db = MagicMock()
        self.db.__enter__ = Mock(return_value=self.db)
        self.db.__exit__ = Mock(return_value=False)
        with patch("core.database.SessionLocal", return_value=self.db):
            yield

    def _tenant(self, **kw):
        base = dict(name="T", billing_email="b@t", metadata_json={"logo_url": "l"},
                    budget_limit_usd=10.0)
        base.update(kw)
        return SimpleNamespace(**base)

    async def test_get_platform_settings(self):
        setting = SimpleNamespace(setting_key="k1", setting_value="v1")
        self.db.query.return_value.filter.return_value.all.return_value = [setting]
        from tools.platform_management_tool import get_platform_settings
        res = await get_platform_settings({"workspace_id": "ws-1"})
        assert res == {"k1": "v1"}
        self.db.query.side_effect = RuntimeError("x")
        res2 = await get_platform_settings()
        assert "error" in res2

    async def test_update_platform_setting(self):
        setting = SimpleNamespace(setting_value="old")
        q = self.db.query.return_value.filter.return_value
        q.first.return_value = setting
        from tools.platform_management_tool import update_platform_setting
        res = await update_platform_setting("key", "new", {"workspace_id": "ws-1"})
        assert setting.setting_value == "new"
        assert "updated" in res
        q.first.return_value = None
        res2 = await update_platform_setting("key2", "val")
        assert "updated" in res2
        self.db.query.side_effect = RuntimeError("x")
        res3 = await update_platform_setting("key", "val")
        assert "Error" in res3

    async def test_update_tenant_profile_all_fields(self):
        ws = SimpleNamespace(tenant_id="t-1")
        tenant = self._tenant(metadata_json=None)
        q = self.db.query.return_value.filter.return_value
        q.first.side_effect = [ws, tenant]
        from tools.platform_management_tool import update_tenant_profile
        res = await update_tenant_profile(name="New", billing_email="b@x", logo_url="logo",
                                          primary_color="#fff", budget_limit_usd=99.5,
                                          context={"workspace_id": "ws-1"})
        assert "name" in res and "billing_email" in res and "logo_url" in res
        assert tenant.metadata_json["primary_color"] == "#fff"
        assert tenant.budget_limit_usd == 99.5

    async def test_update_tenant_profile_missing_tenant(self):
        q = self.db.query.return_value.filter.return_value
        q.first.return_value = None
        from tools.platform_management_tool import update_tenant_profile
        res = await update_tenant_profile(name="X", context={"workspace_id": "ws-1"})
        assert "Default tenant not found" in res

    async def test_update_tenant_profile_no_updates_and_error(self):
        ws = SimpleNamespace(tenant_id="t-1")
        tenant = self._tenant()
        q = self.db.query.return_value.filter.return_value
        q.first.side_effect = [ws, tenant]
        from tools.platform_management_tool import update_tenant_profile
        res = await update_tenant_profile(context={"workspace_id": "ws-1"})
        assert res == "No updates provided."
        self.db.query.side_effect = RuntimeError("x")
        res2 = await update_tenant_profile(name="X", context={"workspace_id": "ws-1"})
        assert "Error" in res2

    async def test_set_byok_api_key(self):
        from tools.platform_management_tool import set_byok_api_key
        res = await set_byok_api_key("openai", "sk-1")
        assert "Could not resolve" in res
        with patch("core.byok_endpoints.BYOKManager") as byok_cls:
            byok_cls.return_value.set_api_key = AsyncMock()
            res2 = await set_byok_api_key("openai", "sk-1", {"workspace_id": "ws-1"})
        assert "Successfully" in res2
        with patch("core.byok_endpoints.BYOKManager") as byok_cls:
            byok_cls.return_value.set_api_key = AsyncMock(side_effect=RuntimeError("x"))
            res3 = await set_byok_api_key("openai", "sk-1", {"workspace_id": "ws-1"})
        assert "Error" in res3

    async def test_list_tenant_members(self):
        from tools.platform_management_tool import list_tenant_members
        res = await list_tenant_members()
        assert "Could not resolve" in res
        q = self.db.query.return_value.filter.return_value
        q.first.return_value = None
        res2 = await list_tenant_members({"workspace_id": "ws-1"})
        assert "not found" in res2
        q.first.return_value = SimpleNamespace(tenant_id="t-1")
        q.all.return_value = []
        res3 = await list_tenant_members({"workspace_id": "ws-1"})
        assert "No members" in res3
        member = SimpleNamespace(full_name="Alice", email="a@b", id="u1")
        q.all.return_value = [member]
        res4 = await list_tenant_members({"workspace_id": "ws-1"})
        assert "Alice" in res4
        self.db.query.side_effect = RuntimeError("x")
        res5 = await list_tenant_members({"workspace_id": "ws-1"})
        assert "Error listing" in res5

    async def test_manage_tenant_member(self):
        from tools.platform_management_tool import manage_tenant_member
        user = SimpleNamespace(id="u1", role="member", is_active=True)
        q = self.db.query.return_value.filter.return_value
        q.first.return_value = None
        res = await manage_tenant_member("u1", "update_role", role="admin")
        assert "not found" in res
        q.first.return_value = user
        res = await manage_tenant_member("u1", "update_role")
        assert "role is required" in res
        res = await manage_tenant_member("u1", "update_role", role="admin")
        assert user.role == "admin"
        res = await manage_tenant_member("u1", "deactivate")
        assert user.is_active is False
        res = await manage_tenant_member("u1", "reactivate")
        assert user.is_active is True
        res = await manage_tenant_member("u1", "bogus")
        assert "Unknown action" in res
        self.db.query.side_effect = RuntimeError("x")
        res = await manage_tenant_member("u1", "update_role", role="admin")
        assert "Error managing" in res

    async def test_manage_workspace(self):
        from tools.platform_management_tool import manage_workspace
        self.db.query.return_value.filter.return_value.first.return_value = None
        res = await manage_workspace("W")
        assert "Could not resolve tenant" in res
        res = await manage_workspace("W", context={"workspace_id": "ws-1"})
        assert "Could not resolve tenant" in res
        ws = SimpleNamespace(tenant_id="t-1")
        with patch("core.database.SessionLocal") as sl:
            temp = MagicMock()
            temp.query.return_value.filter.return_value.first.return_value = ws
            sl.return_value.__enter__ = Mock(return_value=temp)
            sl.return_value.__exit__ = Mock(return_value=False)
            res = await manage_workspace("W", context={"workspace_id": "ws-1"})
        assert "created successfully" in res
        new_ws = SimpleNamespace(id="ws-9")
        self.db.query.return_value.filter.return_value.first.return_value = None
        res = await manage_workspace("W", context={"tenant_id": "t-1"})
        assert "created successfully" in res
        ws2 = SimpleNamespace(id="ws-1", name="W")
        self.db.query.return_value.filter.return_value.first.return_value = ws2
        res = await manage_workspace("W2", action="update", workspace_id="ws-1",
                                     description="d", is_startup=True,
                                     context={"tenant_id": "t-1"})
        assert "updated successfully" in res
        res = await manage_workspace("W", action="update", context={"tenant_id": "t-1"})
        assert "workspace_id is required" in res
        self.db.query.return_value.filter.return_value.first.return_value = None
        res = await manage_workspace("W", action="update", workspace_id="nope",
                                     context={"tenant_id": "t-1"})
        assert "not found" in res
        res = await manage_workspace("W", action="bogus", context={"tenant_id": "t-1"})
        assert "Unknown action" in res
        self.db.commit.side_effect = RuntimeError("x")
        res = await manage_workspace("W", context={"tenant_id": "t-1"})
        assert "Error managing" in res

    async def test_manage_team(self):
        from tools.platform_management_tool import manage_team
        res = await manage_team("Team")
        assert "Could not resolve" in res
        team = SimpleNamespace(id="tm-1", name="Team")
        self.db.query.return_value.filter.return_value.first.return_value = None
        res = await manage_team("Team", context={"workspace_id": "ws-1"})
        assert "created successfully" in res
        res = await manage_team("Team", action="update", context={"workspace_id": "ws-1"})
        assert "team_id is required" in res
        self.db.query.return_value.filter.return_value.first.return_value = team
        res = await manage_team("TeamX", action="update", team_id="tm-1",
                                context={"workspace_id": "ws-1"})
        assert "updated successfully" in res
        self.db.query.return_value.filter.return_value.first.return_value = None
        res = await manage_team("Team", action="update", team_id="nope",
                                context={"workspace_id": "ws-1"})
        assert "not found" in res
        res = await manage_team("Team", action="bogus", context={"workspace_id": "ws-1"})
        assert "Unknown action" in res
        user = SimpleNamespace(id="u1", email="a@b")
        self.db.query.return_value.filter.return_value.first.side_effect = [user, None, None, None]
        self.db.execute = Mock()
        with patch("core.models.Team", return_value=SimpleNamespace(id="tm-2")):
            res = await manage_team("Team", add_members=["u1", "missing@x"],
                                    context={"workspace_id": "ws-1"})
        assert "Added 1 members" in res
        self.db.commit.side_effect = RuntimeError("x")
        res = await manage_team("Team", context={"workspace_id": "ws-1"})
        assert "Error managing" in res

    async def test_tenant_workspace_team_crud(self):
        from tools.platform_management_tool import (
            add_member_to_team, add_member_to_workspace, create_team, create_tenant,
            create_workspace, delete_team, delete_tenant, delete_workspace,
            remove_member_from_team, remove_member_from_workspace, update_team,
            update_tenant, update_workspace,
        )
        tenant = SimpleNamespace(id="t-1")
        self.db.query.return_value.filter.return_value.first.return_value = tenant
        res = await create_tenant("NewCo")
        assert "created successfully" in res
        res = await update_tenant("t-1", name="Renamed")
        assert "updated successfully" in res
        self.db.query.return_value.filter.return_value.first.return_value = None
        res = await update_tenant("nope", name="X")
        assert "not found" in res
        res = await delete_tenant("nope")
        assert "not found" in res
        self.db.query.return_value.filter.return_value.first.return_value = tenant
        res = await delete_tenant("t-1")
        assert "deleted successfully" in res
        res = await create_workspace("W", "t-1")
        assert "created successfully" in res
        res = await update_workspace("ws-1", name="W2")
        assert "updated successfully" in res
        self.db.query.return_value.filter.return_value.first.return_value = None
        res = await update_workspace("nope", name="W")
        assert "not found" in res
        res = await delete_workspace("nope")
        assert "not found" in res
        self.db.query.return_value.filter.return_value.first.return_value = tenant
        res = await delete_workspace("ws-1")
        assert "deleted successfully" in res
        res = await create_team("T", "ws-1")
        assert "created successfully" in res
        res = await update_team("tm-1", name="T2")
        assert "updated successfully" in res
        self.db.query.return_value.filter.return_value.first.return_value = None
        res = await update_team("nope", name="T")
        assert "not found" in res
        res = await delete_team("nope")
        assert "not found" in res
        self.db.query.return_value.filter.return_value.first.return_value = tenant
        res = await delete_team("tm-1")
        assert "deleted successfully" in res
        assert "added" in (await add_member_to_workspace("u1", "ws-1"))
        assert "removed" in (await remove_member_from_workspace("u1", "ws-1"))
        assert "added" in (await add_member_to_team("u1", "tm-1"))
        assert "removed" in (await remove_member_from_team("u1", "tm-1"))
        self.db.commit.side_effect = RuntimeError("x")
        res = await create_tenant("X")
        assert "Error" in res
