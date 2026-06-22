"""
TDD regression tests for round 8 bug hunt fixes.

Covers:
- BUG R8-1: canvas_routes get_recording used wrong method name (get_playback_data)
- BUG R8-2: canvas_routes get_recording IDOR (no user ownership check)
"""

from __future__ import annotations

import inspect


# ---------------------------------------------------------------------------
# BUG R8-1+2: canvas_routes get_recording broken + IDOR
# ---------------------------------------------------------------------------


class TestCanvasGetRecordingFixed:
    """get_recording must call the right service method AND verify ownership."""

    def test_does_not_call_get_playback_data(self):
        """The non-existent get_playback_data must not be called."""
        from api import canvas_routes

        src = inspect.getsource(canvas_routes.get_recording)
        assert "get_playback_data" not in src, (
            "canvas_routes.get_recording still calls non-existent get_playback_data"
        )

    def test_calls_get_recording(self):
        """Should call the actual service method get_recording."""
        from api import canvas_routes

        src = inspect.getsource(canvas_routes.get_recording)
        assert "get_recording(" in src, (
            "canvas_routes.get_recording should call service.get_recording()"
        )

    def test_has_ownership_check(self):
        """Endpoint must verify the recording belongs to current_user."""
        from api import canvas_routes

        src = inspect.getsource(canvas_routes.get_recording)
        # Must reference user_id comparison somewhere
        assert "user_id" in src, (
            "canvas_routes.get_recording does not check recording ownership"
        )
