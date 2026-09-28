"""Tests for the sandbox-gate wrapper (blind-spot fix).

Contract: evaluate_tool_call behaves exactly like the inner evaluation,
plus a log-only observation on EVERY path (decision, None, fail-open,
killrun). Telemetry can never alter the decision or swallow KillRunAborted.
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import Mock, patch


def _gate():
    import core.sandbox_gate as sg
    import importlib
    importlib.reload(sg)
    return sg


class TestWrapper:
    def test_decision_passthrough(self):
        sg = _gate()
        sentinel = Mock()
        sentinel.decision = "allowed"
        sentinel.metadata_json = {}
        with patch.object(sg, "_evaluate_tool_call_inner", return_value=sentinel), \
             patch.object(sg, "_shadow_observe") as obs:
            assert sg.evaluate_tool_call("t", {}, {"workspace_id": "w"}) is sentinel
            assert obs.call_count == 1
            assert obs.call_args[0][3] == "allowed"

    def test_none_path_records_no_policy(self):
        sg = _gate()
        with patch.object(sg, "_evaluate_tool_call_inner", return_value=None), \
             patch.object(sg, "_shadow_observe") as obs:
            assert sg.evaluate_tool_call("t", {}, {}) is None
            assert obs.call_args[0][3] == "allowed(no-policy)"

    def test_error_metadata_labeled(self):
        sg = _gate()
        sentinel = Mock()
        sentinel.decision = "allowed"
        sentinel.metadata_json = {"error": "boom"}
        with patch.object(sg, "_evaluate_tool_call_inner", return_value=sentinel), \
             patch.object(sg, "_shadow_observe") as obs:
            sg.evaluate_tool_call("t", {}, {})
            assert obs.call_args[0][3] == "allowed(error)"

    def test_killrun_propagates_and_records(self):
        sg = _gate()
        from core.sandbox_killrun import KillRunAborted
        with patch.object(sg, "_evaluate_tool_call_inner",
                          side_effect=KillRunAborted("killed")), \
             patch.object(sg, "_shadow_observe") as obs:
            with pytest.raises(KillRunAborted):
                sg.evaluate_tool_call("t", {}, {})
            assert obs.call_args[0][3] == "blocked(killrun)"

    def test_other_exceptions_propagate_untouched(self):
        sg = _gate()
        with patch.object(sg, "_evaluate_tool_call_inner",
                          side_effect=ValueError("bug")), \
             patch.object(sg, "_shadow_observe") as obs:
            with pytest.raises(ValueError):
                sg.evaluate_tool_call("t", {}, {})
            assert obs.call_count == 0

    def test_observe_failure_never_breaks_gate(self):
        sg = _gate()
        sentinel = Mock()
        sentinel.decision = "allowed"
        sentinel.metadata_json = {}
        with patch.object(sg, "_evaluate_tool_call_inner", return_value=sentinel), \
             patch.object(sg, "_shadow_observe", side_effect=RuntimeError("telemetry down")):
            assert sg.evaluate_tool_call("t", {}, {}) is sentinel

    def test_real_inner_disabled_returns_none(self):
        sg = _gate()
        out = sg.evaluate_tool_call("read_file", {"p": 1}, {})
        assert out is None  # no run_id -> no policy in scope (unchanged behavior)
