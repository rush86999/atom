"""Coverage wave 41 — tools/canvas_tool (5% → 90%+).

- _create_canvas_audit (success + exception)
- present_chart (governance-off success, governance-on success with agent
  execution, governance-blocked, exception marks execution failed)
- present_markdown / present_status_panel / present_form (governance-off
  success + failure)
- update_canvas (governance-off success + missing fields)
- present_to_canvas routing (chart/form/markdown/status_panel/specialized/
  unknown)
- close_canvas (success/failure)
- canvas_execute_javascript (governance-off success/failure)
- present_specialized_canvas (success/failure)
"""
import asyncio
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import tools.canvas_tool as ct


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


@pytest.fixture
def governance_off():
    with patch.object(ct.FeatureFlags, "should_enforce_governance", return_value=False):
        yield


@pytest.fixture
def ws():
    with patch.object(ct, "ws_manager") as m:
        m.broadcast = AsyncMock()
        yield m


class TestAudit:
    async def test_create_audit_success(self, fresh_db):
        from core.models import CanvasAudit
        audit = await ct._create_canvas_audit(
            db=fresh_db, agent_id="a1", agent_execution_id="ae1",
            user_id="u1", canvas_id="c1", session_id="s1",
            canvas_type="docs", component_type="markdown",
            action="present", governance_check_passed=True,
            metadata={"k": "v"},
        )
        assert audit is not None
        # canvas_type lives in details_json for the audit helper
        assert audit.details_json["canvas_type"] == "docs"
        assert audit.details_json["k"] == "v"

    async def test_create_audit_exception(self, fresh_db):
        fresh_db.add = MagicMock(side_effect=RuntimeError("boom"))
        audit = await ct._create_canvas_audit(
            db=fresh_db, agent_id=None, agent_execution_id=None,
            user_id="u1", canvas_id=None, session_id=None,
        )
        assert audit is None


class TestPresentChart:
    async def test_governance_off_success(self, governance_off, ws):
        result = await ct.present_chart(
            "u1", "line_chart", [{"x": 1, "y": 2}], title="Sales",
        )
        assert result["success"] is True
        assert result["canvas_id"]
        ws.broadcast.assert_awaited_once()

    async def test_governance_on_success(self, ws):
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        execution = SimpleNamespace(id="ae-1")
        db.query.return_value.filter.return_value.first.return_value = execution
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(
            SimpleNamespace(id="a1", name="Agent"), {}
        ))
        governance = MagicMock()
        governance.can_perform_action.return_value = {"allowed": True}
        governance.record_outcome = AsyncMock()
        with patch.object(ct.FeatureFlags, "should_enforce_governance", return_value=True), \
             patch("core.database.get_db_session") as gds, \
             patch.object(ct, "AgentContextResolver", return_value=resolver), \
             patch("core.service_factory.ServiceFactory") as sf:
            gds.return_value.__enter__.return_value = db
            sf.get_governance_service.return_value = governance
            result = await ct.present_chart(
                "u1", "bar_chart", [{"a": 1}], title="T", agent_id="a1",
            )
        assert result["success"] is True
        assert governance.record_outcome.await_count >= 1

    async def test_governance_blocked(self, ws):
        db = MagicMock()
        resolver = MagicMock()
        resolver.resolve_agent_for_request = AsyncMock(return_value=(
            SimpleNamespace(id="a1", name="Agent"), {}
        ))
        governance = MagicMock()
        governance.can_perform_action.return_value = {"allowed": False, "reason": "denied"}
        with patch.object(ct.FeatureFlags, "should_enforce_governance", return_value=True), \
             patch("core.database.get_db_session") as gds, \
             patch.object(ct, "AgentContextResolver", return_value=resolver), \
             patch("core.service_factory.ServiceFactory") as sf:
            gds.return_value.__enter__.return_value = db
            sf.get_governance_service.return_value = governance
            result = await ct.present_chart("u1", "line_chart", [], agent_id="a1")
        assert result["success"] is False
        assert "denied" in result["error"]

    async def test_exception(self, ws):
        with patch.object(ct.FeatureFlags, "should_enforce_governance",
                          side_effect=RuntimeError("boom")):
            result = await ct.present_chart("u1", "line_chart", [])
        assert result["success"] is False


class TestSimplePresents:
    async def test_present_markdown(self, governance_off, ws):
        result = await ct.present_markdown("u1", "# Hello", title="T")
        assert result["success"] is True
        ws.broadcast.assert_awaited_once()

    async def test_present_status_panel(self, governance_off, ws):
        result = await ct.present_status_panel(
            "u1", [{"label": "A", "value": "1"}], title="Panel"
        )
        assert result["success"] is True

    async def test_present_form(self, governance_off, ws):
        result = await ct.present_form(
            "u1", {"fields": [{"id": "name", "label": "Name"}]}, title="Form"
        )
        assert result["success"] is True

    async def test_present_markdown_failure(self, ws):
        with patch.object(ct.FeatureFlags, "should_enforce_governance",
                          side_effect=RuntimeError("boom")):
            result = await ct.present_markdown("u1", "# X")
        assert result["success"] is False


class TestUpdateCanvas:
    async def test_update_success(self, governance_off, ws):
        result = await ct.update_canvas(
            "u1", "c1", updates={"data": [1, 2], "title": "Updated"}
        )
        assert result["success"] is True
        ws.broadcast.assert_awaited_once()

    async def test_update_empty_updates(self, governance_off, ws):
        # empty updates dict is broadcast as-is (no validation in the tool)
        result = await ct.update_canvas("u1", "c1", updates={})
        assert result["success"] is True


class TestPresentToCanvas:
    async def test_routes_all_types(self, governance_off, ws):
        cases = [
            ("chart", {"chart_type": "line_chart", "data": []}),
            ("form", {"fields": []}),
            ("markdown", {"content": "hi"}),
            ("status_panel", {"items": []}),
            ("docs", {"component_type": "rich_editor"}),
            ("email", {"component_type": "thread_view"}),
            ("sheets", {"component_type": "data_grid"}),
            ("terminal", {"component_type": "shell_output"}),
            ("coding", {"component_type": "code_editor"}),
        ]
        for canvas_type, content in cases:
            result = await ct.present_to_canvas(
                MagicMock(), "u1", canvas_type, content, title="T"
            )
            assert result["success"] is True, f"{canvas_type}: {result}"

    async def test_unknown_type(self, governance_off, ws):
        result = await ct.present_to_canvas(MagicMock(), "u1", "bogus", {})
        assert result["success"] is False
        assert "Unknown canvas type" in result["error"]

    async def test_exception(self, ws):
        with patch.object(ct.FeatureFlags, "should_enforce_governance",
                          side_effect=RuntimeError("boom")):
            result = await ct.present_to_canvas(MagicMock(), "u1", "chart", {})
        assert result["success"] is False


class TestCloseAndJS:
    async def test_close_canvas(self, ws):
        result = await ct.close_canvas("u1", session_id="s1")
        assert result["success"] is True

    async def test_close_canvas_failure(self):
        with patch.object(ct, "ws_manager") as m:
            m.broadcast = AsyncMock(side_effect=RuntimeError("boom"))
            result = await ct.close_canvas("u1")
        assert result["success"] is False

    async def test_execute_javascript_success(self, governance_off, ws):
        result = await ct.canvas_execute_javascript(
            "u1", "c1", "document.title='X';", "a1"
        )
        assert result["success"] is True
        ws.broadcast.assert_awaited_once()

    async def test_execute_javascript_failure(self, ws):
        with patch.object(ct.FeatureFlags, "should_enforce_governance",
                          side_effect=RuntimeError("boom")):
            result = await ct.canvas_execute_javascript("u1", "c1", "bad();", "a1")
        assert result["success"] is False

    async def test_specialized_canvas_success(self, governance_off, ws):
        result = await ct.present_specialized_canvas(
            "u1", "docs", "rich_editor", {"content": "x"}, title="Doc"
        )
        assert result["success"] is True

    async def test_specialized_canvas_failure(self, ws):
        with patch.object(ct.FeatureFlags, "should_enforce_governance",
                          side_effect=RuntimeError("boom")):
            result = await ct.present_specialized_canvas("u1", "docs", "rich_editor", {})
        assert result["success"] is False
