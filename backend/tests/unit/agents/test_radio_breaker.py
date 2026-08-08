"""Responsibility-breakpoint classifier tests.

The paper's rule: a fixed multi-agent team should NOT be the default; teams
only make sense when the task crosses ownership boundaries. These tests lock
in the deterministic classifier behavior.
"""

from core.agent_radio.radio_breaker import (
    classify_responsibility_breakpoints,
    should_attach_thread,
)


class TestClassifier:
    def test_legacy_cross_service_triggers(self):
        verdict = classify_responsibility_breakpoints(
            "root-cause an incident across services in a legacy system; "
            "the auth service and storage service disagree"
        )
        assert verdict.triggered is True
        assert verdict.score >= 2

    def test_security_refactor_triggers(self):
        verdict = classify_responsibility_breakpoints(
            "run a security review and plan the multi-module refactor"
        )
        assert verdict.triggered is True

    def test_bounded_one_file_never_triggers(self):
        verdict = classify_responsibility_breakpoints(
            "fix typo in one-file change — legacy name only"
        )
        assert verdict.triggered is False
        assert verdict.reasons == ["bounded local work"]

    def test_boilerplate_never_triggers(self):
        verdict = classify_responsibility_breakpoints(
            "generate boilerplate for the new API integration"
        )
        assert verdict.triggered is False

    def test_empty_task_no_trigger(self):
        verdict = classify_responsibility_breakpoints("")
        assert verdict.triggered is False

    def test_single_keyword_insufficient(self):
        verdict = classify_responsibility_breakpoints(
            "update the legacy pricing table totals"
        )
        assert verdict.triggered is False  # one hit is not a breakpoint

    def test_case_insensitive(self):
        verdict = classify_responsibility_breakpoints(
            "Cross-Service Incident Investigation required"
        )
        assert verdict.triggered is True


class TestShouldAttachThread:
    def test_gate_disabled_never_attaches(self, monkeypatch):
        monkeypatch.setattr("core.agent_radio.radio_config.breakpoint_gate_enabled",
                            lambda: False)
        verdict = should_attach_thread(
            "root-cause in legacy cross-service incident"
        )
        assert verdict.triggered is False

    def test_gate_enabled_passes_through(self, monkeypatch):
        monkeypatch.setattr("core.agent_radio.radio_config.breakpoint_gate_enabled",
                            lambda: True)
        verdict = should_attach_thread(
            "root-cause a legacy cross-service incident"
        )
        assert verdict.triggered is True