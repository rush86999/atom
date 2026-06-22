"""
TDD regression tests for round 17 bug hunt fixes.

Covers:
- BUG R17-1: chat_orchestrator leaked str(e) in 8 user-facing responses
"""

from __future__ import annotations

import inspect


class TestChatOrchestratorNoStrELeak:
    """chat_orchestrator must not return str(e) in user-facing responses."""

    def test_no_str_e_in_response_payloads(self):
        from integrations import chat_orchestrator

        src = inspect.getsource(chat_orchestrator)
        # The chat orchestrator returns error strings directly to users
        # via the chat message API. None should embed str(e).
        # Match `str(e)` not preceded by `# ` comment.
        import re
        # Find lines with str(e) that aren't inside comments
        bad_lines = []
        for i, line in enumerate(src.split("\n"), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if "str(e)" in line or "str(exc)" in line:
                bad_lines.append(i)
        assert not bad_lines, (
            f"chat_orchestrator still leaks str(e) at line(s): {bad_lines}"
        )
