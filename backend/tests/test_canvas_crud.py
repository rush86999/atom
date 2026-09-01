"""
Tests for canvas CRUD and canvas-aware learning.

Verifies that agents can read, update, and delete canvases across all types,
and that canvas state flows into the episode/learning system.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, AsyncMock


class TestCanvasCrudTools:

    def test_read_canvas_tool_exists(self):
        from tools.canvas_crud_tool import read_canvas
        assert callable(read_canvas)

    def test_update_canvas_tool_exists(self):
        from tools.canvas_crud_tool import update_canvas_content
        assert callable(update_canvas_content)

    def test_delete_canvas_tool_exists(self):
        from tools.canvas_crud_tool import delete_canvas
        assert callable(delete_canvas)

    def test_list_canvases_tool_exists(self):
        from tools.canvas_crud_tool import list_canvases
        assert callable(list_canvases)

    @pytest.mark.asyncio
    async def test_read_canvas_not_found(self):
        """Reading a nonexistent canvas returns an error."""
        from tools.canvas_crud_tool import read_canvas
        with patch("core.database.get_db_session") as mock_db:
            mock_session = Mock()
            mock_query = Mock()
            mock_query.filter.return_value.order_by.return_value.first.return_value = None
            mock_session.query.return_value = mock_query
            mock_db.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.return_value.__exit__ = Mock(return_value=False)

            result = await read_canvas("user1", "nonexistent")
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_canvas_not_found(self):
        """Deleting a nonexistent canvas returns an error."""
        from tools.canvas_crud_tool import delete_canvas
        with patch("core.database.get_db_session") as mock_db:
            mock_session = Mock()
            mock_query = Mock()
            mock_query.filter.return_value.order_by.return_value.first.return_value = None
            mock_session.query.return_value = mock_query
            mock_db.return_value.__enter__ = Mock(return_value=mock_session)
            mock_db.return_value.__exit__ = Mock(return_value=False)

            result = await delete_canvas("user1", "nonexistent")
            assert result["success"] is False
            assert "not found" in result["error"]


class TestCanvasHttpEndpoints:

    def test_read_endpoint_exists(self):
        """GET /api/canvas/{canvas_id} is registered."""
        from api.canvas_routes import router
        paths = {r.path for r in router.routes if hasattr(r, "path")}
        assert any("/{canvas_id}" in p for p in paths)

    def test_delete_endpoint_exists(self):
        """DELETE /api/canvas/{canvas_id} is registered."""
        from api.canvas_routes import router
        for r in router.routes:
            if hasattr(r, "methods") and hasattr(r, "path") and "/{canvas_id}" in r.path:
                if "DELETE" in r.methods:
                    return
        pytest.fail("No DELETE /{canvas_id} route found")

    def test_list_endpoint_exists(self):
        """GET / (list) is registered."""
        from api.canvas_routes import router
        paths = {r.path for r in router.routes if hasattr(r, "path")}
        assert "/" in paths or "/api/canvas/" in paths


class TestCanvasAwareLearning:

    def test_routing_feedback_has_canvas_type(self):
        """RoutingFeedback includes the canvas_type field."""
        from core.learning_llm_router import RoutingFeedback
        import inspect
        source = inspect.getsource(RoutingFeedback)
        assert "canvas_type" in source, \
            "RoutingFeedback should have a canvas_type field for canvas-aware learning"

    def test_routing_feedback_canvas_type_default_none(self):
        """canvas_type defaults to None when not provided."""
        from core.learning_llm_router import RoutingFeedback
        fb = RoutingFeedback(
            routing_result_id="test",
            tenant_id="t1",
            model_id="gpt-4o",
            task_type="code_generation",
            success=True,
            quality_satisfied=True,
            cost_within_budget=True,
        )
        assert fb.canvas_type is None


class TestEpisodeCanvasCapture:

    def test_episode_has_canvas_snapshots_in_metadata(self):
        """The episode metadata schema includes canvas_snapshots."""
        from core.episode_service import EpisodeService
        import inspect
        source = inspect.getsource(EpisodeService._extract_canvas_metadata)
        assert "canvas_snapshots" in source, \
            "Episode metadata should capture canvas_snapshots (raw content, not just IDs)"

    def test_episode_captures_canvas_by_session(self):
        """Episode capture falls back to session-based CanvasAudit lookup."""
        from core.episode_service import EpisodeService
        import inspect
        source = inspect.getsource(EpisodeService._extract_canvas_metadata)
        assert "session_id" in source, \
            "Episode canvas capture should use session_id as fallback when canvas_id is missing"
        assert "CanvasAudit" in source


class TestReadCanvasAfterEventRows:
    """Regression 2026-08-31: email_send / email_send_attempt rows append to
    the audit trail WITHOUT a content key. When such an event row became the
    latest row, read_canvas fell back to the stale canvases.content column
    and served the creation-era snapshot — the user's current draft "went
    missing" after every send attempt. The read must scan back to the latest
    content-bearing row before considering legacy fallbacks."""

    def _patch_session(self, db_session):
        from unittest.mock import Mock, patch

        ctx = Mock()
        ctx.__enter__ = Mock(return_value=db_session)
        ctx.__exit__ = Mock(return_value=False)
        return patch("core.database.get_db_session", return_value=ctx)

    def _seed(self, db_session, canvas_id, rows, canvas_content):
        from datetime import datetime, timedelta, timezone

        from core.models import Canvas, CanvasAudit

        db_session.add(Canvas(
            id=canvas_id, tenant_id="default", created_by="user-1",
            name="Ancient", canvas_type="email", status="active",
            content=canvas_content,
        ))
        now = datetime.now(timezone.utc)
        for offset, (action, details) in enumerate(rows):
            db_session.add(CanvasAudit(
                canvas_id=canvas_id, tenant_id="default", action_type=action,
                user_id="user-1", canvas_type="email", details_json=details,
                created_at=now - timedelta(minutes=30 - offset),
            ))
        db_session.commit()

    @pytest.mark.asyncio
    async def test_read_skips_trailing_send_event_row(self, db_session):
        import uuid

        from tools.canvas_crud_tool import read_canvas

        canvas_id = f"cv-{uuid.uuid4().hex[:8]}"
        draft = {"to": "mark@x.ca", "cc": "vipul@y.ca", "subject": "Re: Quote",
                 "body": "Hi Mark,"}
        self._seed(db_session, canvas_id, [
            ("update", {"content": draft, "title": "Quote draft"}),
            ("email_send_attempt", {
                "canvas_type": "email", "component_type": "compose_form",
                "send_status": "failed", "payload": {"to": ["mark@x.ca"]},
            }),
        ], canvas_content={"type": "doc", "content": "ANCIENT CREATION DOC"})

        with self._patch_session(db_session):
            result = await read_canvas("user-1", canvas_id)

        assert result["success"] is True
        # The DRAFT, not the ancient creation snapshot, and not the event row
        assert result["content"] == draft
        # provenance (title/type) comes from the content-bearing row too
        assert result["title"] == "Quote draft"
        assert result["canvas_type"] == "email"

    @pytest.mark.asyncio
    async def test_read_still_falls_back_for_legacy_canvas(self, db_session):
        """Legacy canvas whose audit rows never carry a body: the
        canvases.content fallback must keep working."""
        import uuid

        from tools.canvas_crud_tool import read_canvas

        canvas_id = f"cv-{uuid.uuid4().hex[:8]}"
        self._seed(db_session, canvas_id, [
            ("create", {"source": "chat", "title": "Legacy doc"}),
        ], canvas_content={"type": "doc", "content": "The real legacy body"})

        with self._patch_session(db_session):
            result = await read_canvas("user-1", canvas_id)

        assert result["success"] is True
        # the legacy body is served (coerce_email_canvas wraps doc-shaped
        # content into the email composer shape — pre-existing behavior)
        assert result["content"].get("body") == "The real legacy body"


class TestRestoreDeletedCanvas:
    """Un-delete: the delete path is an append-only tombstone, so restore
    appends a 'restore' row carrying the pre-delete content forward. After
    restore, the canvas is listed again, readable, and writable."""

    def _seed_full_lifecycle(self, db_session, canvas_id, owner="user-1"):
        from datetime import datetime, timedelta, timezone

        from core.models import Canvas, CanvasAudit

        db_session.add(Canvas(
            id=canvas_id, tenant_id="default", created_by=owner,
            name="To delete", canvas_type="email", status="active",
            content={"to": "", "subject": "s", "body": "pre-delete body"},
        ))
        now = datetime.now(timezone.utc)
        rows = [
            ("create", {"content": {"to": "a@b.c", "subject": "s", "body": "draft one"}}),
            ("update", {"content": {"to": "a@b.c", "subject": "s", "body": "pre-delete body"}}),
            ("delete", {"deleted": True, "previous_action": "update"}),
        ]
        for offset, (action, details) in enumerate(rows):
            db_session.add(CanvasAudit(
                canvas_id=canvas_id, tenant_id="default", action_type=action,
                user_id=owner, canvas_type="email", details_json=details,
                created_at=now - timedelta(minutes=30 - offset),
            ))
        db_session.commit()

    def _patch_session(self, db_session):
        from unittest.mock import Mock, patch

        ctx = Mock()
        ctx.__enter__ = Mock(return_value=db_session)
        ctx.__exit__ = Mock(return_value=False)
        return patch("core.database.get_db_session", return_value=ctx)

    @pytest.mark.asyncio
    async def test_restore_appends_row_and_makes_canvas_listed_again(
        self, db_session,
    ):
        import uuid

        from tools.canvas_crud_tool import (
            list_canvases,
            restore_deleted_canvas,
        )

        canvas_id = f"cv-{uuid.uuid4().hex[:8]}"
        self._seed_full_lifecycle(db_session, canvas_id)

        with self._patch_session(db_session), \
             patch("tools.canvas_crud_tool._broadcast_canvas_update", new=AsyncMock()):
            # before: hidden from the default listing (latest row = delete)
            before = await list_canvases("user-1")
            assert all(c["canvas_id"] != canvas_id for c in before["canvases"])

            result = await restore_deleted_canvas("user-1", canvas_id)
            assert result["success"] is True

            after = await list_canvases("user-1")
            match = [c for c in after["canvases"] if c["canvas_id"] == canvas_id]
            assert match, "restored canvas must be listed again"
            assert match[0]["action_type"] != "delete"

    @pytest.mark.asyncio
    async def test_restore_carries_pre_delete_content(self, db_session):
        import uuid

        from tools.canvas_crud_tool import read_canvas, restore_deleted_canvas

        canvas_id = f"cv-{uuid.uuid4().hex[:8]}"
        self._seed_full_lifecycle(db_session, canvas_id)

        with self._patch_session(db_session), \
             patch("tools.canvas_crud_tool._broadcast_canvas_update", new=AsyncMock()):
            result = await restore_deleted_canvas("user-1", canvas_id)
            assert result["success"] is True
            read = await read_canvas("user-1", canvas_id)
            assert read.get("success") is not False
            content = read.get("content") or {}
            assert content.get("body") == "pre-delete body"

    @pytest.mark.asyncio
    async def test_restore_rejects_non_deleted_canvas(self, db_session):
        import uuid

        from tools.canvas_crud_tool import restore_deleted_canvas

        canvas_id = f"cv-{uuid.uuid4().hex[:8]}"
        self._seed_full_lifecycle(db_session, canvas_id)

        with self._patch_session(db_session):
            result = await restore_deleted_canvas("user-1", canvas_id)
            assert result["success"] is True
            # second restore: latest row is now "restore", not "delete"
            again = await restore_deleted_canvas("user-1", canvas_id)
            assert again["success"] is False
            assert "not deleted" in again["error"]

    @pytest.mark.asyncio
    async def test_restore_is_owner_only(self, db_session):
        import uuid

        from tools.canvas_crud_tool import restore_deleted_canvas

        canvas_id = f"cv-{uuid.uuid4().hex[:8]}"
        self._seed_full_lifecycle(db_session, canvas_id)

        with self._patch_session(db_session):
            result = await restore_deleted_canvas("someone-else", canvas_id)
            assert result["success"] is False
            assert "not found" in result["error"]
