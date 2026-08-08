"""
Bug-hunt tests for tools + agents + llm modules (TDD RED->GREEN).

Every test class here started RED (failing against the buggy source) and is
GREEN after the minimal source fix. See docs/testing/TESTED_FILES_TRACKER.md.
"""

import asyncio
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# ---------------------------------------------------------------------------
# KingAgent — canvas kwargs
# ---------------------------------------------------------------------------


def _sig_enforced_async(fn, return_value=None):
    """Async mock that emulates ``fn``'s parameter acceptance (rejects
    unexpected kwargs exactly like the real function would)."""
    import inspect

    sig = inspect.signature(fn)
    param_names = set(sig.parameters)
    accepts_kw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    ret = return_value if return_value is not None else {"success": True}

    async def _check(*args, **kwargs):
        if not accepts_kw:
            bad = sorted(set(kwargs) - param_names)
            if bad:
                raise TypeError(
                    f"{fn.__name__}() got an unexpected keyword argument {bad[0]!r}"
                )
        return ret

    return AsyncMock(side_effect=_check)


class TestKingAgentCanvasKwargs:
    """execute_blueprint passed tenant_id= to present_markdown/update_canvas
    which do not accept it -> TypeError on every canvas-updating execution."""

    def _king(self):
        from core.agents.king_agent import KingAgent

        king = object.__new__(KingAgent)
        king.queen = MagicMock()
        king.queen.generate_mermaid = Mock(return_value="graph TD")
        king.healer = MagicMock()
        king.agent_id = "king-1"
        return king

    @pytest.mark.asyncio
    async def test_execute_blueprint_present_markdown_kwargs(self):
        from tools.canvas_tool import present_markdown

        king = self._king()
        pm = _sig_enforced_async(present_markdown, {"success": True, "canvas_id": "c1"})
        with patch("core.agents.king_agent.present_markdown", new=pm) as pmock:
            result = await king.execute_blueprint(
                {"architecture_name": "Test", "nodes": []},
                context={"user_id": "u1", "tenant_id": "t1"},
            )
        assert pmock.called, "present_markdown should be called with valid kwargs"
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_blueprint_update_canvas_kwargs(self):
        from tools.canvas_tool import present_markdown, update_canvas

        king = self._king()
        pm = _sig_enforced_async(present_markdown, {"success": True, "canvas_id": "c1"})
        uc = _sig_enforced_async(update_canvas)
        with patch("core.agents.king_agent.present_markdown", new=pm), patch(
            "core.agents.king_agent.update_canvas", new=uc
        ) as ucmock:
            result = await king.execute_blueprint(
                {
                    "architecture_name": "Test",
                    "nodes": [
                        {
                            "id": "n1",
                            "name": "Node One",
                            "type": "skill",
                            "capability_required": "search",
                            "dependencies": [],
                        }
                    ],
                },
                context={"user_id": "u1", "tenant_id": "t1"},
            )
        assert ucmock.called, "update_canvas should be called with valid kwargs"


# ---------------------------------------------------------------------------
# QueenAgent — phantom LLMService.generate_response
# ---------------------------------------------------------------------------


class ModernLLMStub:
    """Emulates the CURRENT LLMService surface (no generate_response)."""

    def __init__(self, text):
        self._text = text

    async def generate(self, prompt="", system_instruction="", tenant_id=None, **kw):
        return self._text


class TestQueenAgentRealLLM:
    @pytest.mark.asyncio
    async def test_generate_blueprint_uses_real_llm_api(self):
        from core.agents.queen_agent import QueenAgent

        llm = ModernLLMStub(json.dumps({
            "architecture_name": "Real Queen Blueprint",
            "description": "d",
            "nodes": [{"id": "s1", "type": "agent", "name": "A", "capability_required": "c", "dependencies": []}],
            "required_integrations": [],
            "missing_capabilities": [],
        }))
        queen = QueenAgent(db=MagicMock(), llm=llm)
        blueprint = await queen.generate_blueprint("goal", tenant_id="t1")
        assert blueprint["architecture_name"] == "Real Queen Blueprint"
        assert blueprint.get("status") != "fallback"


class TestAutoresearchRealLLM:
    @pytest.mark.asyncio
    async def test_run_experiment_loop_uses_real_llm_api(self, tmp_path):
        from core.agents.autoresearch_agent import AutoresearchAgent

        program = tmp_path / "instructions.md"
        program.write_text("Improve the model.")
        script = tmp_path / "train.py"
        script.write_text("print('FINAL_METRIC: 10.0')")

        llm = ModernLLMStub("print('FINAL_METRIC: 0.5')")
        agent = AutoresearchAgent(db=MagicMock(), llm_service=llm)
        result = await agent.run_experiment_loop(
            program_md_path=str(program),
            target_script_path=str(script),
            iterations=1,
        )
        assert result["status"] == "success"
        assert len(result["history"]) == 1
        assert result["history"][0]["kept"] is True


class TestSkillCreationRealLLM:
    @pytest.mark.asyncio
    async def test_generate_skill_code_uses_real_llm_api(self):
        from core.agents.skill_creation_agent import SkillCreationAgent

        llm = ModernLLMStub("async def execute(): return {'custom_marker': 1}")
        agent = SkillCreationAgent(db=MagicMock(), llm_service=llm)
        analysis = {
            "base_url": "https://api.example.com",
            "description": "Fetch data",
            "input_schema": {},
            "output_schema": {},
            "auth_headers": {},
        }
        code = await agent._generate_skill_code(analysis)
        assert "custom_marker" in code

    @pytest.mark.asyncio
    async def test_generate_component_code_uses_real_llm_api(self):
        from core.agents.skill_creation_agent import SkillCreationAgent

        llm = ModernLLMStub("export const MyComponent = () => null")
        agent = SkillCreationAgent(db=MagicMock(), llm_service=llm)
        skill = SimpleNamespace(name="Svc", description="d", output_schema={})
        code = await agent._generate_component_code(skill, {"category": "widget", "config_schema": {}})
        assert "MyComponent" in code


# ---------------------------------------------------------------------------
# platform_management_tool — phantom BYOKManager API + str(e) leaks
# ---------------------------------------------------------------------------


class TestPlatformSetByokKey:
    """set_byok_api_key used BYOKManager(db) + set_api_key() which don't exist
    on the real manager (no-arg ctor; store_api_key(...)) — the tool could
    never set a key."""

    @pytest.mark.asyncio
    async def test_set_byok_api_key_uses_real_manager_api(self):
        from tools.platform_management_tool import set_byok_api_key

        with patch("core.database.SessionLocal") as sl:
            db = MagicMock()
            sl.return_value = db
            with patch("core.byok_endpoints.BYOKManager") as byok_cls:
                inst = byok_cls.return_value
                inst.store_api_key = Mock(return_value="openai_default_production")
                res = await set_byok_api_key("openai", "sk-abc12345", {"workspace_id": "ws-1"})
        assert "Successfully" in res
        assert inst.store_api_key.called
        assert inst.store_api_key.call_args.kwargs.get("provider_id") == "openai"
        assert inst.store_api_key.call_args.kwargs.get("api_key") == "sk-abc12345"


class TestPlatformNoStrELeak:
    """Error paths must never surface raw exception text (R18-31)."""

    @pytest.mark.asyncio
    async def test_get_platform_settings_no_leak(self):
        from tools.platform_management_tool import get_platform_settings

        with patch("core.database.SessionLocal") as sl:
            db = MagicMock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            db.query.side_effect = RuntimeError("secret-db-detail-xyz")
            res = await get_platform_settings({"workspace_id": "ws-1"})
        assert "secret-db-detail-xyz" not in str(res)

    @pytest.mark.asyncio
    async def test_update_platform_setting_no_leak(self):
        from tools.platform_management_tool import update_platform_setting

        with patch("core.database.SessionLocal") as sl:
            db = MagicMock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            db.query.side_effect = RuntimeError("secret-db-detail-xyz")
            res = await update_platform_setting("k", "v", {"workspace_id": "ws-1"})
        assert "secret-db-detail-xyz" not in res

    @pytest.mark.asyncio
    async def test_update_tenant_profile_no_leak(self):
        from tools.platform_management_tool import update_tenant_profile

        with patch("core.database.SessionLocal") as sl:
            db = MagicMock()
            sl.return_value.__enter__ = Mock(return_value=db)
            sl.return_value.__exit__ = Mock(return_value=False)
            db.query.side_effect = RuntimeError("secret-db-detail-xyz")
            res = await update_tenant_profile(name="X", context={"workspace_id": "ws-1"})
        assert "secret-db-detail-xyz" not in res

    @pytest.mark.asyncio
    async def test_manage_workspace_no_leak(self):
        from tools.platform_management_tool import manage_workspace

        with patch("core.database.SessionLocal") as sl:
            db = MagicMock()
            sl.return_value = db
            db.commit.side_effect = RuntimeError("secret-db-detail-xyz")
            res = await manage_workspace("W", context={"tenant_id": "t-1"})
        assert "secret-db-detail-xyz" not in res

    @pytest.mark.asyncio
    async def test_manage_team_no_leak(self):
        from tools.platform_management_tool import manage_team

        with patch("core.database.SessionLocal") as sl:
            db = MagicMock()
            sl.return_value = db
            db.commit.side_effect = RuntimeError("secret-db-detail-xyz")
            res = await manage_team("T", context={"workspace_id": "ws-1"})
        assert "secret-db-detail-xyz" not in res

    @pytest.mark.asyncio
    async def test_crud_stubs_no_leak(self):
        from tools.platform_management_tool import (
            create_team,
            create_tenant,
            create_workspace,
            delete_team,
            delete_tenant,
            delete_workspace,
            update_team,
            update_tenant,
            update_workspace,
        )

        for fn, args in [
            (create_tenant, ("X",)),
            (update_tenant, ("t-1",)),
            (delete_tenant, ("t-1",)),
            (create_workspace, ("W", "t-1")),
            (update_workspace, ("ws-1",)),
            (delete_workspace, ("ws-1",)),
            (create_team, ("T", "ws-1")),
            (update_team, ("tm-1",)),
            (delete_team, ("tm-1",)),
        ]:
            with patch("core.database.SessionLocal") as sl:
                db = MagicMock()
                sl.return_value.__enter__ = Mock(return_value=db)
                sl.return_value.__exit__ = Mock(return_value=False)
                db.commit.side_effect = RuntimeError("secret-db-detail-xyz")
                res = await fn(*args)
            assert "secret-db-detail-xyz" not in res, f"{fn.__name__} leaked str(e)"


# ---------------------------------------------------------------------------
# creative_tool — tool-result contract: failure dicts, not raises
# ---------------------------------------------------------------------------


class TestFFmpegToolDictContract:
    @pytest.fixture
    def tool(self):
        with patch("tools.creative_tool.FFmpegService") as svc:
            svc.return_value.validate_path = Mock()
            from tools.creative_tool import FFmpegTool

            yield FFmpegTool()

    @pytest.mark.asyncio
    async def test_non_autonomous_returns_failure_dict(self, tool):
        res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="STUDENT")
        assert isinstance(res, dict)
        assert res["success"] is False
        assert "AUTONOMOUS" in res["error"]

    @pytest.mark.asyncio
    async def test_no_maturity_returns_failure_dict(self, tool):
        res = await tool._run("trim_video", "in.mp4", "out.mp4")
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_path_violation_returns_failure_dict(self):
        with patch("tools.creative_tool.FFmpegService") as svc:
            svc.return_value.validate_path = Mock(side_effect=ValueError("outside allowed"))
            from tools.creative_tool import FFmpegTool

            tool = FFmpegTool()
            res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False
        assert "path" in res["error"].lower()

    @pytest.mark.asyncio
    async def test_traversal_rejected_when_validate_returns_false(self):
        """validate_path returns False (not raise) for traversal — the tool
        must treat a False return as a hard block (fail-open fix)."""
        with patch("tools.creative_tool.FFmpegService") as svc:
            svc.return_value.validate_path = Mock(return_value=False)
            svc.return_value.allowed_dirs = ["./data/media"]
            from tools.creative_tool import FFmpegTool

            tool = FFmpegTool()
            res = await tool._run(
                "trim_video", "../../etc/passwd", "out.mp4", maturity_level="AUTONOMOUS"
            )
        assert res["success"] is False
        assert "path" in res["error"].lower()

    @pytest.mark.asyncio
    async def test_service_unavailable_returns_failure_dict(self):
        with patch("tools.creative_tool.FFmpegService", side_effect=RuntimeError("no ffmpeg")):
            from tools.creative_tool import FFmpegTool

            tool = FFmpegTool()
            res = await tool._run("trim_video", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False
        assert "service" in res["error"].lower()

    @pytest.mark.asyncio
    async def test_unknown_action_returns_failure_dict(self, tool):
        res = await tool._run("explode", "in.mp4", "out.mp4", maturity_level="AUTONOMOUS")
        assert res["success"] is False
        assert "explode" in res["error"]

    @pytest.mark.asyncio
    async def test_success_wraps_result(self, tool):
        tool.service = MagicMock()
        tool.service.trim_video = AsyncMock(return_value={"job_id": "j1"})
        res = await tool._run(
            "trim_video", "in.mp4", "out.mp4",
            maturity_level="AUTONOMOUS", start_time="00:00:01", duration="00:01:00",
        )
        assert res["success"] is True
        assert res["job_id"] == "j1"

    @pytest.mark.asyncio
    async def test_dispatch_context_kwargs_do_not_crash(self, tool):
        """agent_id/db context kwargs must not leak into the op methods
        (exact signatures -> TypeError)."""
        tool.service = MagicMock()
        tool.service.trim_video = AsyncMock(return_value={"job_id": "j9"})
        res = await tool._run(
            "trim_video", "in.mp4", "out.mp4",
            maturity_level="AUTONOMOUS", start_time="00:00:01", duration="00:01:00",
            agent_id="agent-1", db="session",
        )
        assert res["success"] is True
        assert res["job_id"] == "j9"


# ---------------------------------------------------------------------------
# tools.registry — complexity inference: CRITICAL never reached
# ---------------------------------------------------------------------------


class TestRegistryComplexityInference:
    def _discover(self, mod_name, funcs):
        mod = types.ModuleType(mod_name)
        for fname, f in funcs.items():
            setattr(mod, fname, f)
        sys.modules[mod_name] = mod
        from tools.registry import ToolRegistry

        r = ToolRegistry()
        r.discover_tools(tool_modules=[mod_name])
        return r

    def test_execute_command_inferred_critical(self):
        async def execute_command_handler(**kw):
            return {}

        r = self._discover("fake_tools.exec_commands", {"execute_command_handler": execute_command_handler})
        assert r.get("execute_command_handler").complexity == 4
        assert r.get("execute_command_handler").maturity_required == "AUTONOMOUS"

    def test_create_inferred_high(self):
        async def create_record(**kw):
            return {}

        r = self._discover("fake_tools.crud_ops", {"create_record": create_record})
        assert r.get("create_record").complexity == 3

    def test_read_inferred_low(self):
        async def read_status(**kw):
            return {}

        r = self._discover("fake_tools.status_ops", {"read_status": read_status})
        assert r.get("read_status").complexity == 1

    def test_duplicate_register_warns_and_overwrites(self):
        from tools.registry import ToolRegistry

        r = ToolRegistry()
        r.register("dup", lambda: None, description="first")
        assert r.list_all() == ["dup"]
        r.register("dup", lambda: None, description="second")
        assert len(r.list_all()) == 1
