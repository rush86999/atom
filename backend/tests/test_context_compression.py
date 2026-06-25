# -*- coding: utf-8 -*-
"""
TDD tests for context compression improvements (gap-analysis #1).

Covers the two DETERMINISTIC phases ported from Hermes' compressor:
  1. Boundary protection in truncate_to_context — preserve head + tail,
     drop the stale middle (fixes the old head-chop that lost the tail).
  2. sanitize_tool_pairs — inject stub assistant.tool_calls before any
     orphaned tool result (prevents OpenAI 400 on truncation boundaries).

We deliberately do NOT test an LLM-summary phase — Hermes' own summary
compressor has 3 documented production bugs and we don't build one.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.byok_handler import BYOKHandler


@pytest.fixture()
def handler():
    """BYOKHandler with clients stubbed — we only test the pure methods."""
    h = BYOKHandler.__new__(BYOKHandler)
    h.clients = {}
    return h


# ===========================================================================
# truncate_to_context — boundary protection (head + tail preserved)
# ===========================================================================
class TestTruncateBoundaryProtection:
    def test_short_text_unchanged(self, handler):
        text = "short prompt"
        assert handler.truncate_to_context(text, "gpt-4o") == text

    def test_tail_is_preserved(self, handler):
        """The most important property: the tail (active task) survives."""
        tail_marker = "THIS_IS_THE_TAIL_MUST_SURVIVE_1234567890"
        text = "HEAD " + ("x" * 200000) + " " + tail_marker
        result = handler.truncate_to_context(text, "gpt-4o", reserve_tokens=1000)
        assert tail_marker in result, "tail must be preserved by truncation"

    def test_head_is_preserved(self, handler):
        head_marker = "THIS_IS_THE_HEAD_MUST_SURVIVE_1234567890"
        text = head_marker + " " + ("y" * 200000) + " TAIL"
        result = handler.truncate_to_context(text, "gpt-4o", reserve_tokens=1000)
        assert head_marker in result, "head must be preserved by truncation"

    def test_middle_is_elided(self, handler):
        middle_marker = "STALE_MIDDLE_CONTENT_TO_DROP"
        # Must exceed gpt-4o's ~512K char budget to trigger truncation
        text = "HEAD " + ("a" * 300000) + middle_marker + ("b" * 300000) + " TAIL"
        result = handler.truncate_to_context(text, "gpt-4o", reserve_tokens=1000)
        assert "HEAD" in result
        assert "TAIL" in result
        # The elision marker should be present
        assert "elided" in result.lower()

    def test_result_is_within_budget(self, handler):
        text = "H" + ("x" * 600000) + "T"
        result = handler.truncate_to_context(text, "gpt-4o", reserve_tokens=1000)
        # gpt-4o context = 128000 tokens * 4 chars ≈ 512000 chars minus reserve
        assert len(result) < len(text)
        assert len(result) < 520000  # within a reasonable bound

    def test_no_old_head_chop_behavior(self, handler):
        """Regression: the old code did text[:max_chars] which dropped the tail."""
        text = ("HEAD " * 10) + ("middle " * 50000) + "ACTIVE_TASK_AT_THE_END"
        result = handler.truncate_to_context(text, "gpt-4o")
        assert "ACTIVE_TASK_AT_THE_END" in result
        # The old head-chop would have cut this off


# ===========================================================================
# sanitize_tool_pairs — orphaned tool result protection
# ===========================================================================
class TestSanitizeToolPairs:
    def test_no_messages(self, handler):
        assert handler.sanitize_tool_pairs([]) == []

    def test_clean_messages_unchanged(self, handler):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        assert handler.sanitize_tool_pairs(msgs) == msgs

    def test_orphaned_tool_gets_stub(self, handler):
        """A tool result with no preceding assistant.tool_calls gets a stub."""
        msgs = [
            {"role": "user", "content": "run the tool"},
            {"role": "tool", "tool_call_id": "tc1", "content": "result"},
        ]
        result = handler.sanitize_tool_pairs(msgs)
        # A stub assistant.tool_calls should be inserted before the tool msg
        assert len(result) == 3
        assert result[1]["role"] == "assistant"
        assert result[1]["tool_calls"]
        assert result[1]["tool_calls"][0]["id"] == "tc1"
        assert result[2]["role"] == "tool"

    def test_paired_tool_unchanged(self, handler):
        """A properly paired tool_call → tool_result is left alone."""
        msgs = [
            {"role": "user", "content": "x"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "tc1", "type": "function", "function": {"name": "f", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "tc1", "content": "result"},
        ]
        result = handler.sanitize_tool_pairs(msgs)
        assert len(result) == 3  # unchanged — no stub injected

    def test_trailing_tool_calls_without_result_dropped(self, handler):
        """A trailing assistant.tool_calls whose result was truncated is dropped."""
        msgs = [
            {"role": "user", "content": "x"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "tc1", "type": "function", "function": {"name": "f", "arguments": "{}"}}
            ]},
            # NO tool result follows — this is the orphaned-call case
        ]
        result = handler.sanitize_tool_pairs(msgs)
        assert len(result) == 1
        assert result[-1]["role"] == "user"

    def test_assistant_with_content_kept(self, handler):
        """A trailing assistant with BOTH content and tool_calls is kept."""
        msgs = [
            {"role": "user", "content": "x"},
            {"role": "assistant", "content": "working on it", "tool_calls": [
                {"id": "tc1", "type": "function", "function": {"name": "f", "arguments": "{}"}}
            ]},
        ]
        result = handler.sanitize_tool_pairs(msgs)
        assert len(result) == 2  # kept — it has content

    def test_multiple_orphans_all_get_stubs(self, handler):
        msgs = [
            {"role": "tool", "tool_call_id": "tc1", "content": "r1"},
            {"role": "tool", "tool_call_id": "tc2", "content": "r2"},
        ]
        result = handler.sanitize_tool_pairs(msgs)
        # Each tool gets its own stub
        assert len(result) == 4
        assert result[0]["role"] == "assistant"
        assert result[1]["role"] == "tool"
        assert result[2]["role"] == "assistant"
        assert result[3]["role"] == "tool"
