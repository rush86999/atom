"""
P7 — Per-Canvas Server Runtime tests (G7b) + CustomComponent schema fix.

A canvas can have server-side Python logic executed in the isolated sandbox
runtime with a per-canvas storage namespace. Also fixes the CustomComponent
model stub drift (service writes slug/props_schema/default_props/is_public/
current_version/min_maturity_level/tenant_id that the stub doesn't declare).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


# ============================================================================
# CustomComponent model schema fix
# ============================================================================

class TestCustomComponentModelFix:
    def test_model_has_missing_columns(self):
        """The service writes these fields; the model must declare them."""
        from core.models import CustomComponent
        for col in ("slug", "props_schema", "default_props", "is_public",
                    "current_version", "min_maturity_level", "tenant_id"):
            assert hasattr(CustomComponent, col), (
                f"CustomComponent missing required column '{col}' that the "
                f"service writes (live schema drift)."
            )


# ============================================================================
# Canvas logic service — save/load
# ============================================================================

class TestCanvasLogicSaveLoad:
    def test_save_and_load_logic(self, db_session):
        """Logic source persists and round-trips."""
        from core.canvas_logic_service import CanvasLogicService
        svc = CanvasLogicService(db_session)
        svc.save_logic(
            canvas_id="c1",
            source="result = 1 + 1",
            language="python",
            created_by="u1",
        )
        logic = svc.load_logic("c1")
        assert logic is not None
        assert logic["source"] == "result = 1 + 1"
        assert logic["language"] == "python"

    def test_load_missing_returns_none(self, db_session):
        from core.canvas_logic_service import CanvasLogicService
        svc = CanvasLogicService(db_session)
        assert svc.load_logic("nope") is None


# ============================================================================
# Canvas logic service — run with sandbox + per-canvas namespace
# ============================================================================

class TestCanvasLogicRun:
    @pytest.mark.asyncio
    async def test_run_executes_in_sandbox_runtime(self, db_session, monkeypatch):
        """run() delegates to the sandbox runtime with the source + policy."""
        from core import canvas_logic_service as cls

        executed = {}

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None):
                executed["code"] = code
                executed["inputs"] = inputs
                executed["cwd"] = cwd
                result = MagicMock()
                result.success = True
                result.stdout = "ok"
                result.stderr = ""
                result.exit_code = 0
                return result

        monkeypatch.setattr(cls, "get_runtime", lambda: FakeRuntime())

        svc = cls.CanvasLogicService(db_session)
        svc.save_logic(canvas_id="c2", source="x = 42", created_by="u1")
        result = await svc.run("c2", inputs={"user_input": "hello"})
        assert executed["code"] == "x = 42"
        # Per-canvas storage namespace is injected.
        assert executed["inputs"]["storage_namespace"] == "c2"
        assert executed["inputs"]["user_input"] == "hello"

    @pytest.mark.asyncio
    async def test_run_namespace_isolation(self, db_session, monkeypatch):
        """Each canvas gets its own storage_namespace; no cross-canvas leakage."""
        from core import canvas_logic_service as cls

        namespaces = []

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None):
                namespaces.append(inputs.get("storage_namespace"))
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                return result
        monkeypatch.setattr(cls, "get_runtime", lambda: FakeRuntime())

        svc = cls.CanvasLogicService(db_session)
        svc.save_logic(canvas_id="canvasA", source="x=1", created_by="u1")
        svc.save_logic(canvas_id="canvasB", source="y=2", created_by="u1")
        await svc.run("canvasA", inputs={})
        await svc.run("canvasB", inputs={})
        assert "canvasA" in namespaces
        assert "canvasB" in namespaces
        assert namespaces[0] != namespaces[1]

    @pytest.mark.asyncio
    async def test_run_blocks_fs_escape(self, db_session, monkeypatch):
        """The per-canvas cwd rejects path escape attempts."""
        from core import canvas_logic_service as cls

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None):
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                return result
        monkeypatch.setattr(cls, "get_runtime", lambda: FakeRuntime())

        svc = cls.CanvasLogicService(db_session)
        # The service must normalize the canvas_id so a malicious id like
        # "../../etc" cannot escape the canvas_runtime root.
        svc.save_logic(canvas_id="../../etc", source="x=1", created_by="u1")
        # It should either reject or sanitize; either way it must NOT create a
        # path outside ./data/canvas_runtime/.
        import os
        # The saved logic should be keyed by the sanitized id (no traversal).
        # We accept either an error or a sanitized load.
        try:
            await svc.run("../../etc", inputs={})
        except Exception:
            pass  # rejection is acceptable
        # No file should exist outside data/canvas_runtime (no actual fs write in
        # this mocked test, but verify the namespace sanitization helper).
        assert cls.sanitize_namespace("../../etc") != "../../etc"
        assert "/" not in cls.sanitize_namespace("../../etc")


# ============================================================================
# Governance gate — AUTONOMOUS required
# ============================================================================

class TestGovernanceGate:
    def test_run_requires_autonomous_agent(self, db_session):
        """Editing/running canvas logic requires AUTONOMOUS maturity
        (mirrors custom_components_service._check_governance_for_js)."""
        from core.canvas_logic_service import CanvasLogicService
        svc = CanvasLogicService(db_session)
        # No agent_id -> rejected.
        with pytest.raises(Exception):
            svc.check_governance(agent_id=None)
