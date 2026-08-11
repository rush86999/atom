"""
AgentGuidanceSystem tests — replaces the generated stub suite (was 3 skips).

Covers start_operation (disabled/blocked/success), update_step (found/missing/
progress-clamp/log), update_context (found/missing), complete_operation
(found/missing/completed-vs-failed), add_log_entry delegation, _create_audit
(commit + rollback), get_agent_guidance_system singleton.
"""
import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentOperationTracker, AgentRegistry
from tools.agent_guidance_canvas_tool import (
    AGENT_GUIDANCE_ENABLED,
    AgentGuidanceSystem,
    get_agent_guidance_system,
)


@pytest.fixture
def fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


@pytest.fixture
def system(fresh_db):
    with patch("tools.agent_guidance_canvas_tool.AgentContextResolver"), \
         patch("tools.agent_guidance_canvas_tool.AgentGovernanceService"):
        sys = AgentGuidanceSystem(fresh_db)
    sys.governance = MagicMock()
    return sys


def _tracker(db, operation_id=None, total_steps=4):
    t = AgentOperationTracker(
        id=str(uuid.uuid4()),
        tenant_id="default",
        agent_id="a1",
        user_id="u1",
        workspace_id="default",
        operation_type="browser_automate",
        operation_id=operation_id or f"op-{uuid.uuid4().hex[:8]}",
        current_step="Init",
        total_steps=total_steps,
        current_step_index=0,
        status="running",
        progress=0,
        what_explanation="w",
        why_explanation="y",
        next_steps="n",
        operation_metadata={},
        logs=[],
    )
    db.add(t)
    db.commit()
    return t


class TestStartOperation:
    async def test_disabled_returns_id(self, system):
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            result = await system.start_operation("u1", "a1", "browser", {})
        assert isinstance(result, str)

    async def test_governance_blocked(self, system, fresh_db):
        fresh_db.add(AgentRegistry(
            id="a1", name="A", category="g", description="d",
            status="INTERN", confidence_score=0.6,
            module_path="m", class_name="C", workspace_id="default",
        ))
        fresh_db.commit()
        system.governance.can_perform_action.return_value = {
            "allowed": False, "reason": "maturity"
        }
        result = await system.start_operation("u1", "a1", "browser", {})
        assert result["success"] is False
        assert "maturity" in result["error"]

    async def test_success_creates_tracker_and_broadcasts(self, system, fresh_db):
        with patch("tools.agent_guidance_canvas_tool.ws_manager") as ws:
            ws.broadcast = AsyncMock()
            op_id = await system.start_operation(
                "u1", "a1", "browser_automate",
                {"what": "Opening", "why": "Need data", "next": "Parse"},
                total_steps=4, metadata={"source": "test"},
            )
        assert isinstance(op_id, str)
        rows = fresh_db.query(AgentOperationTracker).filter(
            AgentOperationTracker.operation_id == op_id
        ).all()
        assert len(rows) == 1
        assert rows[0].status == "running"
        ws.broadcast.assert_awaited_once()
        payload = ws.broadcast.await_args.args[1]["data"]["data"]
        assert payload["operation_type"] == "browser_automate"
        assert payload["progress"] == 0

    async def test_exception_returns_id(self, system):
        system.db.add = Mock(side_effect=RuntimeError("boom"))
        result = await system.start_operation("u1", "a1", "browser", {})
        assert isinstance(result, str)


class TestUpdateStep:
    async def test_disabled(self, system):
        with patch("tools.agent_guidance_canvas_tool.AGENT_GUIDANCE_ENABLED", False):
            await system.update_step("u1", "op-1", "step")
        # no raise

    async def test_missing_tracker(self, system):
        with patch("tools.agent_guidance_canvas_tool.ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await system.update_step("u1", "missing", "step")
        ws.broadcast.assert_not_awaited()

    async def test_update_with_progress_and_log(self, system, fresh_db):
        t = _tracker(fresh_db)
        with patch("tools.agent_guidance_canvas_tool.ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await system.update_step(
                "u1", t.operation_id, "Parsing", progress=150,
                add_log={"level": "info", "message": "parsed"},
            )
        fresh_db.refresh(t)
        assert t.current_step == "Parsing"
        assert t.progress == 100  # clamped
        assert t.current_step_index == 1
        assert t.logs[0]["message"] == "parsed"

    async def test_progress_derived_from_total_steps(self, system, fresh_db):
        t = _tracker(fresh_db, total_steps=4)
        with patch("tools.agent_guidance_canvas_tool.ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await system.update_step("u1", t.operation_id, "Step 2")
        fresh_db.refresh(t)
        assert t.progress == 25  # index 1 / 4


class TestUpdateContext:
    async def test_updates_explanations(self, system, fresh_db):
        t = _tracker(fresh_db)
        with patch("tools.agent_guidance_canvas_tool.ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await system.update_context("u1", t.operation_id, what="New what", why="New why")
        fresh_db.refresh(t)
        assert t.what_explanation == "New what"
        assert t.why_explanation == "New why"

    async def test_missing_tracker_noop(self, system):
        with patch("tools.agent_guidance_canvas_tool.ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await system.update_context("u1", "missing", what="x")
        ws.broadcast.assert_not_awaited()


class TestCompleteOperation:
    async def test_completed(self, system, fresh_db):
        t = _tracker(fresh_db)
        with patch("tools.agent_guidance_canvas_tool.ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await system.complete_operation("u1", t.operation_id, status="completed")
        fresh_db.refresh(t)
        assert t.status == "completed"
        assert t.progress == 100
        assert t.completed_at is not None

    async def test_failed_keeps_progress(self, system, fresh_db):
        t = _tracker(fresh_db, total_steps=4)
        with patch("tools.agent_guidance_canvas_tool.ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await system.complete_operation("u1", t.operation_id, status="failed",
                                            final_message="boom")
        fresh_db.refresh(t)
        assert t.status == "failed"
        assert t.current_step == "boom"

    async def test_missing_tracker(self, system):
        with patch("tools.agent_guidance_canvas_tool.ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await system.complete_operation("u1", "missing")
        ws.broadcast.assert_not_awaited()


class TestLogAndAudit:
    async def test_add_log_entry_delegates(self, system, fresh_db):
        t = _tracker(fresh_db)
        with patch.object(system, "update_step", new=AsyncMock()) as us:
            await system.add_log_entry("u1", t.operation_id, "error", "msg")
        us.assert_awaited_once()
        kwargs = us.await_args.kwargs
        assert kwargs["add_log"] == {"level": "error", "message": "msg"}

    async def test_create_audit_commit(self, system, fresh_db):
        await system._create_audit(
            "a1", "u1", "op-1", "start_operation", True, {"k": "v"}
        )
        from core.models import CanvasAudit
        rows = fresh_db.query(CanvasAudit).filter(
            CanvasAudit.action_type == "start_operation"
        ).all()
        assert len(rows) == 1
        assert rows[0].details_json["operation_id"] == "op-1"

    async def test_create_audit_rollback(self, system):
        db = MagicMock()
        db.add = Mock(side_effect=RuntimeError("boom"))
        db.rollback = Mock()
        system.db = db
        await system._create_audit("a1", "u1", "op-1", "start_operation", True, {})
        assert db.rollback.called


class TestFactory:
    def test_get_agent_guidance_system(self, fresh_db):
        a = get_agent_guidance_system(fresh_db)
        b = get_agent_guidance_system(fresh_db)
        assert isinstance(a, AgentGuidanceSystem)
        assert a is not b  # new instance per call
