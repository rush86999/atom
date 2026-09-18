# -*- coding: utf-8 -*-
"""The planning window must show REQUESTS and the answers they already got.

RCA 2026-09-17 finding 1, two defects in one branch (`if _tool_block:`):

1. `history[-3:]` slices ENTRIES. In a normal exchange the last three entries are
   assistant turns, so the window handed to the model could contain NO user
   request at all — three "requests" that were three replies.
2. Only user turns were included, so work that had ALREADY been answered looked
   unanswered: the model re-answered the earlier attachment and derivation asks,
   and declared a workbook unavailable that it had opened one turn earlier.

The original reason for the user-only rule is preserved and must stay: a
transcript full of FAILED attempts anchors weak models into refusing again, so
error turns and refusal turns are still excluded.
"""
import ast
from pathlib import Path

import integrations.chat_orchestrator as co

SRC = Path(co.__file__).read_text(encoding="utf-8")


def _window_source() -> str:
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                node.name == "_get_qwen_response":
            return ast.get_source_segment(SRC, node) or ""
    raise AssertionError("_get_qwen_response not found")


class TestWindowConstruction:
    def test_user_window_is_taken_over_user_turns(self):
        src = _window_source()
        code = "\n".join(
            line for line in src.splitlines() if not line.strip().startswith("#")
        )
        assert "history[-3:]" not in code, (
            "slicing entries gives a window of replies in a normal exchange"
        )
        assert 'h.get("message")][-3:]' in code

    def test_successful_assistant_turns_are_included(self):
        src = _window_source()
        assert "already answered earlier" in src

    def test_error_turns_stay_excluded(self):
        src = _window_source()
        assert '_h.get("error")' in src, (
            "failed attempts must not re-enter the prompt — they anchor refusals"
        )

    def test_refusal_turns_stay_excluded(self):
        src = _window_source()
        assert "_reply_claims_inability" in src, (
            "a reply that denied having the data is the specific anchor the "
            "user-only rule was protecting against"
        )

    def test_the_window_is_bounded(self):
        src = _window_source()
        assert "_answered[-2:]" in src, "not a second transcript"
        assert "_resp[:600]" in src
