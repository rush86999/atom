"""Coverage wave 52 — core/view_coordinator.py (16% → 90%+).

All orchestration methods: disabled-flag short-circuits, success paths (new +
existing state), WS broadcasts, audit creation, and exception tolerance.
Real in-memory SQLite for state; ws_manager mocked.
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import ViewOrchestrationState
from core.view_coordinator import ViewCoordinator, get_view_coordinator


@pytest.fixture
def vc():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    coord = ViewCoordinator(db)
    with patch("core.view_coordinator.ws_manager.broadcast", new=AsyncMock()) as br:
        yield coord, db, br
    db.close()
    engine.dispose()


def await_coroutine(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestSwitchToBrowser:
    def test_disabled(self, vc):
        coord, db, br = vc
        with patch("core.view_coordinator.VIEW_COORDINATION_ENABLED", False):
            assert await_coroutine(coord.switch_to_browser_view("u1", "a1", "https://x", "g")) is None
        br.assert_not_called()

    def test_success_new_state(self, vc):
        coord, db, br = vc
        await_coroutine(coord.switch_to_browser_view("u1", "a1", "https://x.com", "open it"))
        br.assert_awaited_once()
        state = db.query(ViewOrchestrationState).first()
        assert state is not None
        assert state.controlling_agent == "a1"
        assert state.layout == "split_vertical"
        assert state.active_views[0]["view_type"] == "browser"

    def test_success_existing_state(self, vc):
        coord, db, br = vc
        await_coroutine(coord.switch_to_browser_view("u1", "a1", "https://x.com", "g", session_id="s1"))
        await_coroutine(coord.switch_to_browser_view("u1", "a2", "https://y.com", "g2", session_id="s1"))
        state = db.query(ViewOrchestrationState).first()
        assert state.controlling_agent == "a2"
        assert len(state.active_views) == 2  # both views appended

    def test_exception_swallowed(self, vc):
        coord, db, br = vc
        with patch.object(db, "commit", side_effect=RuntimeError("boom")):
            await_coroutine(coord.switch_to_browser_view("u1", "a1", "https://x", "g"))
        # must not raise


class TestSwitchToTerminal:
    def test_disabled(self, vc):
        coord, db, br = vc
        with patch("core.view_coordinator.VIEW_COORDINATION_ENABLED", False):
            assert await_coroutine(coord.switch_to_terminal_view("u1", "a1", "ls", "g")) is None
        br.assert_not_called()

    def test_success(self, vc):
        coord, db, br = vc
        await_coroutine(coord.switch_to_terminal_view("u1", "a1", "ls -la", "run it"))
        br.assert_awaited_once()
        state = db.query(ViewOrchestrationState).first()
        assert state.active_views[0]["view_type"] == "terminal"
        assert state.layout == "split_horizontal"

    def test_exception_swallowed(self, vc):
        coord, db, br = vc
        with patch.object(db, "commit", side_effect=RuntimeError("boom")):
            await_coroutine(coord.switch_to_terminal_view("u1", "a1", "ls", "g"))


class TestSetLayout:
    def test_disabled(self, vc):
        coord, db, br = vc
        with patch("core.view_coordinator.VIEW_COORDINATION_ENABLED", False):
            assert await_coroutine(coord.set_layout("u1", "grid")) is None

    def test_success_with_state(self, vc):
        coord, db, br = vc
        await_coroutine(coord.switch_to_browser_view("u1", "a1", "https://x", "g", session_id="s1"))
        await_coroutine(coord.set_layout("u1", "tabs", session_id="s1"))
        br.assert_awaited()
        state = db.query(ViewOrchestrationState).first()
        assert state.layout == "tabs"

    def test_success_without_state(self, vc):
        coord, db, br = vc
        await_coroutine(coord.set_layout("u1", "grid"))
        br.assert_awaited_once()

    def test_exception_swallowed(self, vc):
        coord, db, br = vc
        with patch.object(db, "query", side_effect=RuntimeError("boom")):
            await_coroutine(coord.set_layout("u1", "grid"))


class TestActivateView:
    def test_disabled(self, vc):
        coord, db, br = vc
        with patch("core.view_coordinator.VIEW_COORDINATION_ENABLED", False):
            assert await_coroutine(coord.activate_view("u1", "canvas")) is None

    def test_browser_with_url(self, vc):
        coord, db, br = vc
        await_coroutine(coord.activate_view("u1", "browser", url="https://z.com", size="1/2"))
        state = db.query(ViewOrchestrationState).first()
        view = state.active_views[0]
        assert view["view_type"] == "browser"
        assert view["url"] == "https://z.com"
        assert view["title"] == "Browser: https://z.com"
        assert view["size"]["width"] == "1/2"

    def test_terminal_with_command(self, vc):
        coord, db, br = vc
        await_coroutine(coord.activate_view("u1", "terminal", command="top"))
        state = db.query(ViewOrchestrationState).first()
        assert state.active_views[0]["command"] == "top"

    def test_plain_view(self, vc):
        coord, db, br = vc
        await_coroutine(coord.activate_view("u1", "app"))
        state = db.query(ViewOrchestrationState).first()
        assert state.active_views[0]["view_type"] == "app"
        assert state.active_views[0]["title"] == "App"

    def test_exception_swallowed(self, vc):
        coord, db, br = vc
        with patch.object(db, "commit", side_effect=RuntimeError("boom")):
            await_coroutine(coord.activate_view("u1", "browser", url="https://x"))


class TestUpdateGuidanceAndClose:
    def test_update_guidance_disabled_and_success(self, vc):
        coord, db, br = vc
        with patch("core.view_coordinator.VIEW_COORDINATION_ENABLED", False):
            assert await_coroutine(coord.update_view_guidance("u1", "v1", "g")) is None
        await_coroutine(coord.update_view_guidance("u1", "v1", "new guidance"))
        br.assert_awaited_once()

    def test_update_guidance_exception(self, vc):
        coord, db, br = vc
        br.side_effect = RuntimeError("ws down")
        await_coroutine(coord.update_view_guidance("u1", "v1", "g"))

    def test_close_view_success(self, vc):
        coord, db, br = vc
        await_coroutine(coord.activate_view("u1", "browser", url="https://x", session_id="s1"))
        state = db.query(ViewOrchestrationState).first()
        view_id = state.active_views[0]["view_id"]
        await_coroutine(coord.close_view("u1", view_id, session_id="s1"))
        state = db.query(ViewOrchestrationState).first()
        assert state.active_views == []

    def test_close_view_no_state(self, vc):
        coord, db, br = vc
        await_coroutine(coord.close_view("u1", "v1"))
        br.assert_awaited_once()

    def test_close_view_exception(self, vc):
        coord, db, br = vc
        with patch.object(db, "commit", side_effect=RuntimeError("boom")):
            await_coroutine(coord.close_view("u1", "v1"))


class TestHelpers:
    def test_get_or_create_session(self, vc):
        coord, db, br = vc
        sid = coord._get_or_create_session("u1")
        assert sid.startswith("session_u1_")

    def test_create_audit_success(self, vc):
        coord, db, br = vc
        await_coroutine(coord._create_audit("a1", "u1", "s1", "switch", {"k": "v"}))
        from core.models import CanvasAudit
        audit = db.query(CanvasAudit).first()
        assert audit is not None
        assert audit.action_type == "switch"

    def test_create_audit_exception(self, vc):
        coord, db, br = vc
        with patch.object(db, "commit", side_effect=RuntimeError("boom")):
            await_coroutine(coord._create_audit("a1", "u1", "s1", "switch", {}))

    def test_get_view_coordinator(self, vc):
        coord, db, br = vc
        assert isinstance(get_view_coordinator(db), ViewCoordinator)


class TestRemainingBranches:
    def test_terminal_existing_state_updates_agent(self, vc):
        coord, db, br = vc
        await_coroutine(coord.switch_to_terminal_view("u1", "a1", "ls", "g", session_id="s1"))
        await_coroutine(coord.switch_to_terminal_view("u1", "a2", "pwd", "g", session_id="s1"))
        state = db.query(ViewOrchestrationState).first()
        assert state.controlling_agent == "a2"
        assert len(state.active_views) == 2

    def test_close_view_disabled(self, vc):
        coord, db, br = vc
        with patch("core.view_coordinator.VIEW_COORDINATION_ENABLED", False):
            assert await_coroutine(coord.close_view("u1", "v1")) is None
        br.assert_not_called()

    def test_close_view_removes_matching_only(self, vc):
        coord, db, br = vc
        await_coroutine(coord.activate_view("u1", "browser", url="https://x", session_id="s1"))
        await_coroutine(coord.activate_view("u1", "terminal", command="top", session_id="s1"))
        state = db.query(ViewOrchestrationState).first()
        keep = [v for v in state.active_views if v["view_type"] == "terminal"][0]
        await_coroutine(coord.close_view("u1", keep["view_id"], session_id="s1"))
        state = db.query(ViewOrchestrationState).first()
        assert [v["view_type"] for v in state.active_views] == ["browser"]
