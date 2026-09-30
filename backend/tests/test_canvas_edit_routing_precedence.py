"""Canvas-edit precedence over a pending file objective (2026-09-29).

Original workbook→email incident: after a workbook search in the canvas
session, two draft-update turns were consumed by the pending-file
continuation — one replanned the OLD ask, one re-ran the read with item
tokens extracted from the edit prose itself ("FOB: Woodstock" became a
search probe) — and the canvas-edit planner was never reached.

The fix is a precedence yield in ``process_chat_message``: when the turn
is edit-shaped against the ACTUALLY OPEN canvas, the pending file
objective does not claim the turn. These tests pin both halves: the
detector decisions on the exact incident texts, and the presence+order of
the yield in the orchestrator source (the repo's established pattern for
the ``process_chat_message`` monolith — see test_task_correction_routing).
"""
from __future__ import annotations

import ast
import os
import sys
import unittest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from integrations.chat_orchestrator import (  # noqa: E402
    _canvas_edit_shaped,
)
from core.pending_file_task import (  # noqa: E402
    entity_set_edit,
    is_retrieval_refresh_request,
)

CANVAS_CTX = {"canvas": {"canvas_id": "fc99d46f", "canvas_type": "email"}}

TURN_RESEARCH = "try the search again and give me a clean response"
TURN_DRAFT = (
    "Using the price results you just found, update this draft email to "
    "quote all 8 machines I asked about, in my original order: No. 381, "
    "U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel "
    "Gang Slitter and GSL48-16. Where several rows matched (No. 381, "
    "No. 622, TK Multi Wheel Gang Slitter), leave the price as 'TBD - "
    "model confirmation pending' instead of picking one."
)
TURN_EDIT = (
    "Edit this email: replace the 4-row quote table with an 8-row table "
    "covering, in my original order, all eight machines from the price "
    "search you just ran (No. 381, U-22, No. 622, TK Manual Flanger, "
    "SLE24-16, TK 1624, TK Multi Wheel Gang Slitter, GSL48-16)."
)


class TestDetectorDecisions(unittest.TestCase):
    """The exact inputs the precedence yield judged in the incident."""

    def test_edit_shaped_turns_are_canvas_edit_shaped(self):
        for name, text in (("draft-update", TURN_DRAFT),
                           ("edit-first", TURN_EDIT)):
            self.assertTrue(
                _canvas_edit_shaped(text, CANVAS_CTX),
                f"{name} must reach the canvas-edit lane")

    def test_research_followup_is_not_canvas_edit_shaped(self):
        self.assertFalse(
            _canvas_edit_shaped(TURN_RESEARCH, CANVAS_CTX),
            "a research-only follow-up must keep resuming the file "
            "objective exactly as before")

    def test_no_canvas_no_yield_even_if_edit_shaped(self):
        self.assertFalse(
            _canvas_edit_shaped(TURN_EDIT, {}),
            "without an open canvas the wording alone must not yield")

    def test_objective_matchers_still_claim_their_own_turns(self):
        # The file lane's own detectors are unchanged: the research
        # follow-up is a refresh, and the entity-set edit detector still
        # fires on replace-with phrasing (that is what captured the
        # edit-first turn before the yield existed).
        self.assertTrue(is_retrieval_refresh_request(TURN_RESEARCH))
        self.assertIsNotNone(entity_set_edit(TURN_EDIT))
        self.assertTrue(is_retrieval_refresh_request(TURN_DRAFT))


class TestYieldPresentInProcessChatMessage(unittest.TestCase):
    """The yield exists in ``process_chat_message``, sits AFTER the
    pending-task matcher (so every consumer sees it) and BEFORE the
    replan-the-original-ask path (so the edit lane actually gets the
    turn)."""

    @classmethod
    def setUpClass(cls):
        src_path = os.path.join(
            BACKEND, "integrations", "chat_orchestrator.py")
        with open(src_path, "r") as fh:
            cls.source = fh.read()
        cls.tree = ast.parse(cls.source)

    def _process_chat_message(self):
        for node in ast.walk(self.tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == "process_chat_message"):
                return node
        self.fail("process_chat_message not found")

    def test_yield_block_exists(self):
        fn = self._process_chat_message()
        src = ast.get_source_segment(self.source, fn) or ""
        self.assertIn("yielding to the canvas-edit lane", src)
        self.assertIn("_canvas_edit_shaped(message", src)

    def test_yield_sits_between_matcher_and_replan(self):
        fn = self._process_chat_message()
        src = ast.get_source_segment(self.source, fn) or ""
        matcher = src.find("matching_pending_task(")
        replan = src.find("_pft_original")
        self.assertGreater(matcher, -1)
        self.assertGreater(replan, -1)
        yield_at = src.find("yielding to the canvas-edit lane")
        self.assertGreater(
            yield_at, matcher,
            "the yield must come after the pending-task matcher")
        self.assertLess(
            yield_at, replan,
            "the yield must come before the replan-the-original-ask path")


if __name__ == "__main__":
    unittest.main()
