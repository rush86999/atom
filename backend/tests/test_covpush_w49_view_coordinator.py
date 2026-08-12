"""Coverage wave 49 — core/view_coordinator flag-off guards (80% → 97%).

Every public method has an early return when VIEW_COORDINATION_ENABLED is
False — drive each one, plus the _create_audit failure path.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.view_coordinator as vc
from core.view_coordinator import ViewCoordinator


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def coord(db):
    c = ViewCoordinator(db)
    c.db = db
    return c


@pytest.fixture
def disabled():
    with patch.object(vc, "VIEW_COORDINATION_ENABLED", False):
        yield


class TestDisabledGuards:
    async def test_switch_to_browser_disabled(self, coord, disabled):
        assert await coord.switch_to_browser_view("u1", "a1", "https://x.com", "g") is None

    async def test_switch_to_terminal_disabled(self, coord, disabled):
        assert await coord.switch_to_terminal_view("u1", "a1", "ls", "g") is None

    async def test_set_layout_disabled(self, coord, disabled):
        assert await coord.set_layout("u1", "grid") is None

    async def test_activate_view_disabled(self, coord, disabled):
        assert await coord.activate_view("u1", "browser") is None

    async def test_update_view_guidance_disabled(self, coord, disabled):
        assert await coord.update_view_guidance("u1", "v1", "g") is None

    async def test_close_view_disabled(self, coord, disabled):
        assert await coord.close_view("u1", "v1") is None


class TestAuditFailure:
    async def test_create_audit_exception_swallowed(self, coord):
        db = MagicMock()
        db.add = MagicMock(side_effect=RuntimeError("boom"))
        coord.db = db
        await coord._create_audit("a1", "u1", "s1", "present", {})  # no raise


class TestEnabledPaths:
    async def test_set_layout_broadcasts(self, coord):
        state = MagicMock()
        coord.db.query.return_value.filter.return_value.first.return_value = state
        with patch.object(vc, "VIEW_COORDINATION_ENABLED", True), \
             patch.object(vc, "ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await coord.set_layout("u1", "grid", session_id="s1")
        ws.broadcast.assert_awaited_once()
        payload = ws.broadcast.await_args.args[1]["data"]
        assert payload["layout"] == "grid"

    async def test_update_view_guidance_broadcasts(self, coord):
        with patch.object(vc, "VIEW_COORDINATION_ENABLED", True), \
             patch.object(vc, "ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await coord.update_view_guidance("u1", "v1", "new guidance")
        ws.broadcast.assert_awaited_once()

    async def test_close_view_broadcasts(self, coord):
        with patch.object(vc, "VIEW_COORDINATION_ENABLED", True), \
             patch.object(vc, "ws_manager") as ws:
            ws.broadcast = AsyncMock()
            result = await coord.close_view("u1", "v1")
        # the method broadcasts and returns nothing
        assert result is None
        ws.broadcast.assert_awaited_once()
