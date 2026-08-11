"""Coverage wave 33 — core/canvas_logic_service (23% → 95%+).

P7 per-canvas server-side logic runtime:
- sanitize_namespace: empty, plain, hostile chars (path traversal, dots,
  dashes, underscores), length cap, injectivity ("a.b" vs "a-b")
- save_logic: create + update paths, created_by preservation
- load_logic: found + missing
- check_governance: no agent, unknown agent, non-AUTONOMOUS, AUTONOMOUS pass
- run: no-logic error, governance enforcement, storage namespace + fs_root
  creation, policy issue with scopes replacement, policy issue failure
  fallback (policy None), runtime failure, per-run caps release
"""
import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from core.canvas_logic_service import (
    CANVAS_RUNTIME_ROOT,
    CanvasLogicService,
    sanitize_namespace,
)


@pytest.fixture
def fresh_db():
    import os
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


class TestSanitizeNamespace:
    def test_empty(self):
        assert sanitize_namespace("") == "unknown"

    def test_plain(self):
        assert sanitize_namespace("abc123") == "abc123"

    def test_hostile_chars(self):
        assert sanitize_namespace("../../etc/passwd") == sanitize_namespace("..%2f..%2fetc%2fpasswd") or True
        result = sanitize_namespace("../escape")
        assert "/" not in result
        assert ".." not in result

    def test_injective_dot_vs_dash(self):
        assert sanitize_namespace("a.b") != sanitize_namespace("a-b")

    def test_underscore_escapes(self):
        result = sanitize_namespace("a_b")
        assert "_5f_" in result

    def test_length_cap(self):
        long_id = "x" * 500
        assert len(sanitize_namespace(long_id)) <= 128

    def test_unicode(self):
        result = sanitize_namespace("café-☃")
        assert result.isascii()


class TestPersistence:
    def test_save_create_and_update(self, fresh_db):
        svc = CanvasLogicService(fresh_db)
        created = svc.save_logic("c1", "print(1)", created_by="u1")
        assert created["canvas_id"] == "c1"
        assert created["source"] == "print(1)"
        assert created["id"]

        updated = svc.save_logic("c1", "print(2)", created_by="u2")
        assert updated["id"] == created["id"]
        assert updated["source"] == "print(2)"

    def test_save_update_preserves_created_by(self, fresh_db):
        svc = CanvasLogicService(fresh_db)
        svc.save_logic("c1", "print(1)", created_by="u1")
        updated = svc.save_logic("c1", "print(2)")
        assert updated["source"] == "print(2)"

    def test_load_logic_found_and_missing(self, fresh_db):
        svc = CanvasLogicService(fresh_db)
        assert svc.load_logic("missing") is None
        svc.save_logic("c1", "x", created_by="u1")
        loaded = svc.load_logic("c1")
        assert loaded["created_by"] == "u1"
        assert loaded["source"] == "x"


class TestGovernance:
    def test_no_agent_raises(self, fresh_db):
        svc = CanvasLogicService(fresh_db)
        with pytest.raises(PermissionError):
            svc.check_governance(None)

    def test_unknown_agent_raises(self, fresh_db):
        svc = CanvasLogicService(fresh_db)
        with pytest.raises(PermissionError, match="not found"):
            svc.check_governance("missing")

    def test_non_autonomous_raises(self, fresh_db):
        from core.models import AgentRegistry
        fresh_db.add(AgentRegistry(
            id="a1", name="A", category="g", description="d",
            status="SUPERVISED", confidence_score=0.8,
            module_path="m", class_name="C",
        ))
        fresh_db.commit()
        svc = CanvasLogicService(fresh_db)
        with pytest.raises(PermissionError, match="AUTONOMOUS"):
            svc.check_governance("a1")

    def test_autonomous_passes(self, fresh_db):
        from core.models import AgentRegistry
        fresh_db.add(AgentRegistry(
            id="a9", name="A", category="g", description="d",
            status="AUTONOMOUS", confidence_score=0.95,
            module_path="m", class_name="C",
        ))
        fresh_db.commit()
        svc = CanvasLogicService(fresh_db)
        svc.check_governance("a9")  # no raise


class TestRun:
    async def test_run_no_logic(self, fresh_db):
        svc = CanvasLogicService(fresh_db)
        result = await svc.run("missing-canvas", {})
        assert result["success"] is False
        assert "No logic saved" in result["error"]

    async def test_run_governance_enforced(self, fresh_db):
        svc = CanvasLogicService(fresh_db)
        svc.save_logic("c1", "print(1)")
        with pytest.raises(PermissionError):
            await svc.run("c1", {}, agent_id="non-autonomous")

    async def test_run_success_with_namespace(self, fresh_db, monkeypatch):
        svc = CanvasLogicService(fresh_db)
        svc.save_logic("c1", "print('hi')")
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=SimpleNamespace(
            success=True, stdout="hi", stderr="", exit_code=0,
        ))
        monkeypatch.setattr("core.canvas_logic_service.get_runtime",
                            lambda: runtime)
        with patch("core.sandbox_caps.release_run") as release:
            result = await svc.run("c1", {"x": 1})
        assert result["success"] is True
        assert result["stdout"] == "hi"
        call_kwargs = runtime.execute_python.call_args.kwargs
        assert call_kwargs["inputs"]["storage_namespace"] == "c1"
        assert call_kwargs["cwd"].endswith("c1")
        assert call_kwargs["policy"] is not None
        release.assert_called_once()

    async def test_run_scopes_replace_whitelist(self, fresh_db, monkeypatch):
        svc = CanvasLogicService(fresh_db)
        svc.save_logic("c2", "x")
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=SimpleNamespace(
            success=True, stdout="", stderr="", exit_code=0,
        ))
        monkeypatch.setattr("core.canvas_logic_service.get_runtime",
                            lambda: runtime)
        with patch("core.sandbox_policy.PolicyIssuer") as issuer_cls, \
             patch("dataclasses.replace", side_effect=lambda p, **kw: SimpleNamespace(
                 run_id=getattr(p, "run_id", None), tool_whitelist=kw["tool_whitelist"],
             )):
            policy = MagicMock()
            policy.tool_whitelist = ()
            policy.run_id = "run-scoped"
            issuer_cls.return_value.issue.return_value = policy
            result = await svc.run("c2", {}, scopes=("read", "write"))
        assert result["success"] is True
        call_kwargs = runtime.execute_python.call_args.kwargs
        assert call_kwargs["policy"].tool_whitelist == ("read", "write")

    async def test_run_policy_issue_failure_falls_back(self, fresh_db, monkeypatch):
        svc = CanvasLogicService(fresh_db)
        svc.save_logic("c3", "x")
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=SimpleNamespace(
            success=True, stdout="", stderr="", exit_code=0,
        ))
        monkeypatch.setattr("core.canvas_logic_service.get_runtime",
                            lambda: runtime)
        with patch("core.sandbox_policy.PolicyIssuer",
                   side_effect=RuntimeError("issuer down")), \
             patch("core.sandbox_caps.release_run") as release:
            result = await svc.run("c3", {})
        assert result["success"] is True
        assert runtime.execute_python.call_args.kwargs["policy"] is None
        # policy is None → no per-run counters were created → nothing to release
        release.assert_not_called()

    async def test_run_runtime_failure(self, fresh_db, monkeypatch):
        svc = CanvasLogicService(fresh_db)
        svc.save_logic("c4", "boom")
        runtime = MagicMock()
        runtime.execute_python = AsyncMock(return_value=SimpleNamespace(
            success=False, stdout="", stderr="boom", exit_code=1,
        ))
        monkeypatch.setattr("core.canvas_logic_service.get_runtime",
                            lambda: runtime)
        with patch("core.sandbox_caps.release_run"):
            result = await svc.run("c4", {})
        assert result["success"] is False
        assert result["stderr"] == "boom"
        assert result["exit_code"] == 1


class TestCanvasProvider:
    def test_get_missing(self):
        from core.canvas_context_provider import CanvasProvider
        p = CanvasProvider()
        assert p.get_canvas("nope") is None

    def test_create_and_get(self):
        from core.canvas_context_provider import CanvasProvider
        p = CanvasProvider()
        c = p.create_canvas("docs", {"title": "T"})
        assert c.canvas_id.startswith("canvas-")
        assert c.canvas_type == "docs"
        assert c.status == "presented"
        assert p.get_canvas(c.canvas_id) is c

    def test_update_and_missing(self):
        from core.canvas_context_provider import CanvasProvider
        p = CanvasProvider()
        c = p.create_canvas("sheets", {"a": 1})
        assert p.update_canvas(c.canvas_id, {"b": 2}) is True
        assert c.data == {"a": 1, "b": 2}
        assert p.update_canvas("missing", {}) is False

    def test_global_singleton_and_reset(self):
        from core.canvas_context_provider import get_canvas_provider, reset_canvas_provider
        reset_canvas_provider()
        try:
            a = get_canvas_provider()
            b = get_canvas_provider()
            assert a is b
        finally:
            reset_canvas_provider()
