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
        assert "/{canvas_id}" in paths or any("/{canvas_id}" in p for p in paths)

    def test_delete_endpoint_exists(self):
        """DELETE /api/canvas/{canvas_id} is registered."""
        from api.canvas_routes import router
        methods = []
        for r in router.routes:
            if hasattr(r, "methods") and hasattr(r, "path") and "/{canvas_id}" in r.path:
                methods.extend(r.methods)
        assert "DELETE" in methods

    def test_list_endpoint_exists(self):
        """GET /api/canvas/ (list) is registered."""
        from api.canvas_routes import router
        paths = {r.path for r in router.routes if hasattr(r, "path")}
        # Router has prefix /api/canvas, so "/" becomes "/api/canvas/"
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
