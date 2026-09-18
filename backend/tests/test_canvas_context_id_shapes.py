# -*- coding: utf-8 -*-
"""The canvas id arrives NESTED — read both shapes or nothing works.

The canvas panel posts ``context={"canvas": {"id": ..., "canvas_type": ...,
"name": ...}}``. Four separate readers looked up ``context["canvas_id"]``, which
is always absent for real panel turns, so:

* canvas agent resolution never ran → ``request.agent_id`` stayed None, the
  canvas's own hire was never attached, and **every lesson taught to that agent
  was invisible in the panel the operator was typing into** (live 2026-09-16 —
  the reported "agent should be learning from my instructions in the agent chat"
  was this, not a retrieval bug: the logs showed
  ``[CHATCTX] request.agent_id=None`` with the canvas plainly in the context);
* the provenance hydration no-opped, so "why was this draft written this way?"
  could not be answered from the panel;
* the per-user canvas↔session binding never persisted;
* the orchestrator's canvas context was None — the editor ran blind on the very
  canvas the user was looking at.
"""
import pytest

from integrations.chat_orchestrator import _canvas_id_from_context
from integrations.chat_routes import _context_canvas_id, _context_canvas_type

CANVAS = "a1a13834-7bb3-4b3b-91cf-e83a2287daf0"
PANEL = {"canvas": {"id": CANVAS, "canvas_type": "email", "name": "Quote"}}


class TestBothShapes:
    def test_panel_shape_hydrates_canvas_id(self):
        assert _context_canvas_id(PANEL) == CANVAS
        assert _canvas_id_from_context(PANEL) == CANVAS

    def test_canvas_type_from_the_nested_shape(self):
        assert _context_canvas_type(PANEL) == "email"

    def test_legacy_flat_shape_still_works(self):
        flat = {"canvas_id": CANVAS, "canvas_type": "email"}
        assert _context_canvas_id(flat) == CANVAS
        assert _context_canvas_type(flat) == "email"
        assert _canvas_id_from_context(flat) == CANVAS

    def test_bare_string_canvas(self):
        assert _context_canvas_id({"canvas": CANVAS}) == CANVAS

    @pytest.mark.parametrize("bad", [{}, None, {"canvas": {}}, {"canvas": None}, 42])
    def test_missing_ids_are_none_not_errors(self, bad):
        assert _context_canvas_id(bad) is None
        assert _canvas_id_from_context(bad) is None


class TestCanvasResolutionUsesIt:
    """The readers must be FED by the normalizer.

    Asserted structurally plus by the normalizer's own behaviour: resolving an
    agent or loading canvas content depends on the store, and the test database
    is isolated (no canvas rows), so a behavioural assertion here would pass or
    fail on where the test runs rather than on the fix.
    """

    def test_route_reads_the_normalizer_not_the_raw_key(self):
        import inspect

        from integrations import chat_routes as cr

        src = inspect.getsource(cr)
        assert "request.context or {}).get(\"canvas_id\")" not in src, (
            "a raw context[\"canvas_id\"] read remains — real panel turns send the "
            "id nested under context[\"canvas\"][\"id\"] and it would be missed"
        )
        assert src.count("_context_canvas_id(request.context)") >= 3

    def test_orchestrator_canvas_reads_the_normalizer(self):
        import inspect

        from integrations.chat_orchestrator import ChatOrchestrator

        src = inspect.getsource(ChatOrchestrator._resolve_canvas_ctx)
        assert "_canvas_id_from_context(context)" in src
        # ignore comments — the fix's own explanation quotes the old bug
        code = "\n".join(
            line for line in src.splitlines() if not line.strip().startswith("#")
        )
        assert 'context["canvas_id"]' not in code
