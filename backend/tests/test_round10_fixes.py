"""
TDD regression tests for round 10 bug hunt fixes.

Covers:
- BUG R10-1: event_bus.py used raw eval() for workflow conditions (RCE)
- BUG R10-2: conductor_agent.py used raw eval() for workflow conditions (RCE)
"""

from __future__ import annotations

import ast
import inspect


def _has_raw_eval_call(path: str) -> list:
    """Parse file with ast, return list of raw eval() call line numbers.

    Excludes calls like safe_eval(...), _safe_eval(...), etc.
    """
    with open(path) as f:
        src = f.read()
    tree = ast.parse(src)
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "eval":
                matches.append(node.lineno)
    return matches


# ---------------------------------------------------------------------------
# BUG R10-1: event_bus.py raw eval()
# ---------------------------------------------------------------------------


class TestEventBusNoRawEval:
    """event_bus.py must not use raw eval() — use safe_eval instead."""

    def test_no_raw_eval(self):
        path = "/Users/rushiparikh/projects/atom/backend/core/orchestration/event_bus.py"
        matches = _has_raw_eval_call(path)
        assert not matches, (
            f"event_bus.py still uses raw eval() at line(s): {matches}"
        )

    def test_uses_safe_eval(self):
        path = "/Users/rushiparikh/projects/atom/backend/core/orchestration/event_bus.py"
        with open(path) as f:
            src = f.read()
        assert "safe_eval" in src or "safe_evaluator" in src, (
            "event_bus.py should use safe_eval from core.safe_evaluator"
        )


# ---------------------------------------------------------------------------
# BUG R10-2: conductor_agent.py raw eval()
# ---------------------------------------------------------------------------


class TestConductorAgentNoRawEval:
    """conductor_agent.py must not use raw eval() — use safe_eval instead."""

    def test_no_raw_eval(self):
        path = "/Users/rushiparikh/projects/atom/backend/core/orchestration/conductor_agent.py"
        matches = _has_raw_eval_call(path)
        assert not matches, (
            f"conductor_agent.py still uses raw eval() at line(s): {matches}"
        )
