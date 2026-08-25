"""Unit tests for the stage router (Switchyard port).

Covers: tool-history parsing, severity classification, read/write role
heuristics, signal extraction (severity/spinning/exploring/production),
corroborative tanh scoring, pickers + confidence threshold, decision
sources, handoff notes, the weighted-random A/B split harness, audit
persistence, and the agent-loop model-type mapping.
"""
from __future__ import annotations

import asyncio
import json
from typing import Dict, List, Optional

import pytest

from core.llm.stage_router import (
    CAPABLE,
    EFFICIENT,
    DecisionSource,
    SignalSeverity,
    StageDecision,
    StagePicker,
    StageRouter,
    StageSignals,
    ToolOutcome,
    WeightedRandomSplit,
    classify_severity,
    classify_tool_roles,
    get_stage_router,
    map_decision_to_model_type,
    parse_tool_history,
)

# ── Fixtures ────────────────────────────────────────────────────────────────


def outcome(
    name: str,
    severity: SignalSeverity = SignalSeverity.NONE,
    is_read: bool = False,
    is_write: bool = False,
    success: bool = True,
) -> ToolOutcome:
    return ToolOutcome(
        tool_name=name,
        is_read=is_read,
        is_write=is_write,
        severity=severity,
        success=success,
    )


def default_router(**kwargs) -> StageRouter:
    kwargs.setdefault("enabled", True)
    kwargs.setdefault("enforce", False)
    return StageRouter(**kwargs)


# ── History parsing ─────────────────────────────────────────────────────────


class TestParseToolHistory:
    def test_parses_json_action_blocks(self) -> None:
        history = (
            'Action: {"tool": "search_documents", "params": {"q": "x"}}\n'
            "Observation: found 3 docs\n"
            'Action: {"tool": "create_record", "params": {}}\n'
            "Observation: Error: tool execution failed\n"
        )
        entries = parse_tool_history(history)
        assert len(entries) == 2
        assert entries[0].outcome.tool_name == "search_documents"
        assert entries[0].outcome.success is True
        assert entries[1].outcome.tool_name == "create_record"
        assert entries[1].outcome.severity == SignalSeverity.MAJOR
        assert entries[1].outcome.success is False

    def test_parses_parallel_call_form(self) -> None:
        history = (
            'Action: search_documents({"q": "x"})\n'
            "Observation: ok\n"
        )
        entries = parse_tool_history(history)
        assert len(entries) == 1
        assert entries[0].outcome.tool_name == "search_documents"

    def test_skips_malformed_blocks(self) -> None:
        history = "Action: not json at all\nObservation: whatever\n"
        entries = parse_tool_history(history)
        assert entries == []

    def test_empty_history(self) -> None:
        assert parse_tool_history("") == []
        assert parse_tool_history(None) == []

    def test_ignores_blocks_without_action(self) -> None:
        history = "Observation: bare observation without action\n"
        assert parse_tool_history(history) == []


# ── Severity classification ─────────────────────────────────────────────────


class TestSeverity:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("everything worked fine", SignalSeverity.NONE),
            ("Governance blocked this action for safety", SignalSeverity.CRITICAL),
            ("Permission denied on that resource", SignalSeverity.CRITICAL),
            ("sandbox blocked the file write", SignalSeverity.CRITICAL),
            ("Error: tool execution failed", SignalSeverity.MAJOR),
            ("tool error. try again", SignalSeverity.MAJOR),
            ("request timed out after 30s", SignalSeverity.MAJOR),
            ("warning: cache stale", SignalSeverity.MINOR),
            ("no results found", SignalSeverity.MINOR),
        ],
    )
    def test_marker_mapping(self, text: str, expected: SignalSeverity) -> None:
        assert classify_severity(text) == expected

    def test_critical_wins_over_major(self) -> None:
        assert classify_severity("Error: permission denied") == SignalSeverity.CRITICAL

    def test_none_observation(self) -> None:
        assert classify_severity(None) == SignalSeverity.NONE


# ── Tool role heuristics ────────────────────────────────────────────────────


class TestToolRoles:
    @pytest.mark.parametrize(
        "name,is_read,is_write",
        [
            ("search_documents", True, False),
            ("get_workflows", True, False),
            ("list_contacts", True, False),
            ("read_file", True, False),
            ("create_record", False, True),
            ("update_record", False, True),
            ("post_to_twitter", False, True),
            ("send_email", False, True),
            ("delete_contact", False, True),
            ("mcp_tool_search", True, False),  # search = read-like discovery
        ],
    )
    def test_role_detection(self, name: str, is_read: bool, is_write: bool) -> None:
        got_read, got_write = classify_tool_roles(name)
        assert (got_read, got_write) == (is_read, is_write)


# ── Signal extraction ───────────────────────────────────────────────────────


class TestSignals:
    def test_empty_history_is_neutral(self) -> None:
        signals = default_router().extract_signals([])
        assert signals.severity == 0.0
        assert signals.spinning is False
        assert signals.exploring is False
        assert signals.production_intensity == 0.0
        assert signals.critical is False

    def test_severity_is_window_max(self) -> None:
        router = default_router(window=3)
        history = [
            outcome("get_x", severity=SignalSeverity.MINOR, is_read=True),
            outcome("get_y", severity=SignalSeverity.NONE, is_read=True),
        ]
        assert router.extract_signals(history).severity == 1.0

    def test_critical_flag(self) -> None:
        router = default_router()
        signals = router.extract_signals(
            [outcome("get_x", severity=SignalSeverity.CRITICAL, is_read=True)]
        )
        assert signals.critical is True

    def test_spinning_detection(self) -> None:
        router = default_router(window=3)
        # three neutral calls (neither read nor write) with a failure → spin
        history = [
            outcome("invoke_capability", severity=SignalSeverity.MAJOR),
            outcome("invoke_capability", severity=SignalSeverity.MAJOR),
            outcome("invoke_capability", severity=SignalSeverity.MAJOR),
        ]
        assert router.extract_signals(history).spinning is True

    def test_productive_window_not_spinning(self) -> None:
        router = default_router(window=3)
        history = [
            outcome("search_documents", is_read=True),
            outcome("create_record", is_write=True),
            outcome("send_email", is_write=True),
        ]
        signals = router.extract_signals(history)
        assert signals.spinning is False
        assert signals.exploring is False
        assert signals.production_intensity == pytest.approx(2 / 3)

    def test_exploring_detection(self) -> None:
        router = default_router(window=3)
        history = [
            outcome("search_documents", is_read=True),
            outcome("get_workflows", is_read=True),
        ]
        signals = router.extract_signals(history)
        assert signals.exploring is True
        assert signals.production_intensity == 0.0

    def test_window_limits_history(self) -> None:
        router = default_router(window=2)
        history = [
            outcome("get_a", severity=SignalSeverity.MAJOR, is_read=True),
            outcome("get_b", is_read=True),
            outcome("get_c", is_read=True),
        ]
        # window of 2: the MAJOR (oldest) is dropped
        assert router.extract_signals(history).severity == 0.0


# ── Corroborative scoring ───────────────────────────────────────────────────


class TestScoring:
    def test_single_full_signal_below_default_threshold(self) -> None:
        router = default_router(confidence_threshold=0.5)
        # one full severity signal alone → ~0.46 (corroborative design)
        signals = StageSignals(severity=3.0)
        confidence = abs(router._score(signals))
        assert confidence < 0.5
        assert confidence == pytest.approx(0.462, abs=0.01)

    def test_corroborating_signals_cross_threshold(self) -> None:
        router = default_router(confidence_threshold=0.5)
        signals = StageSignals(severity=3.0, exploring=True)
        assert abs(router._score(signals)) > 0.5

    def test_production_pushes_efficient(self) -> None:
        router = default_router(confidence_threshold=0.5)
        signals = StageSignals(production_intensity=1.0)
        signed = router._score(signals)
        assert signed < 0
        assert abs(signed) < 0.5  # one full signal alone

    def test_mixed_signals_corroborate(self) -> None:
        router = default_router(confidence_threshold=0.5)
        # moderate severity + exploring → capable
        signals = StageSignals(severity=2.0, exploring=True)
        assert router._score(signals) > 0.5


# ── Decision logic ──────────────────────────────────────────────────────────


class TestDecide:
    def test_critical_error_forces_capable_override(self) -> None:
        router = default_router()
        decision = router.decide(
            [outcome("get_x", severity=SignalSeverity.CRITICAL, is_read=True)]
        )
        assert decision.selected_group == CAPABLE
        assert decision.source == DecisionSource.OVERRIDE.value
        assert decision.confidence == 1.0

    def test_dimensions_routes_capable(self) -> None:
        router = default_router(confidence_threshold=0.5)
        decision = router.decide(
            [
                outcome("get_x", severity=SignalSeverity.MAJOR, is_read=True),
                outcome("get_y", severity=SignalSeverity.MAJOR, is_read=True),
            ]
        )
        assert decision.selected_group == CAPABLE
        assert decision.source == DecisionSource.DIMENSIONS.value

    def test_dimensions_routes_efficient_on_production(self) -> None:
        router = default_router(confidence_threshold=0.4)
        decision = router.decide(
            [
                outcome("create_record", is_write=True),
                outcome("update_record", is_write=True),
            ]
        )
        assert decision.selected_group == EFFICIENT
        assert decision.source == DecisionSource.DIMENSIONS.value

    def test_fall_open_efficient_first_default(self) -> None:
        router = default_router()
        decision = router.decide([outcome("get_x", is_read=True)])
        assert decision.selected_group == EFFICIENT
        assert decision.default_group == EFFICIENT
        assert decision.source == DecisionSource.FALL_OPEN.value

    def test_fall_open_capable_first_default(self) -> None:
        router = default_router(picker=StagePicker.CAPABLE_FIRST)
        decision = router.decide([outcome("get_x", is_read=True)])
        assert decision.selected_group == CAPABLE
        assert decision.default_group == CAPABLE

    def test_threshold_zero_acts_on_any_signal(self) -> None:
        router = default_router(confidence_threshold=0.0)
        # a single MAJOR (severity 2/3 → 0.333→0.32) now acts → capable
        decision = router.decide([outcome("get_x", severity=SignalSeverity.MAJOR, is_read=True)])
        assert decision.source == DecisionSource.DIMENSIONS.value
        assert decision.selected_group == CAPABLE

    def test_threshold_one_never_acts_on_signals(self) -> None:
        router = default_router(confidence_threshold=1.0)
        decision = router.decide(
            [outcome("get_x", severity=SignalSeverity.MAJOR, is_read=True)]
        )
        assert decision.source == DecisionSource.FALL_OPEN.value
        assert decision.selected_group == EFFICIENT  # picker default

    def test_empty_history_falls_open(self) -> None:
        decision = default_router().decide([])
        assert decision.source == DecisionSource.FALL_OPEN.value
        assert decision.selected_group == EFFICIENT

    def test_rationale_mentions_selection(self) -> None:
        decision = default_router().decide([])
        assert "stage_router selected efficient" in decision.rationale


# ── Handoff notes ───────────────────────────────────────────────────────────


class TestHandoffNotes:
    def test_escalation_note_on_switch_to_capable(self) -> None:
        router = default_router()
        note = router.handoff_note_for(CAPABLE, EFFICIENT, DecisionSource.OVERRIDE.value)
        assert note is not None
        assert "capable tier" in note
        assert "stalling" in note

    def test_deescalation_note_on_switch_to_efficient(self) -> None:
        router = default_router()
        note = router.handoff_note_for(EFFICIENT, CAPABLE, DecisionSource.DIMENSIONS.value)
        assert note is not None
        assert "efficient tier" in note

    def test_no_note_without_group_switch(self) -> None:
        router = default_router()
        assert router.handoff_note_for(CAPABLE, CAPABLE) is None
        assert router.handoff_note_for(EFFICIENT, EFFICIENT) is None

    def test_no_note_on_first_turn(self) -> None:
        router = default_router()
        assert router.handoff_note_for(CAPABLE, None) is None

    def test_decision_carries_note_on_switch(self) -> None:
        decision = default_router().decide(
            [outcome("get_x", severity=SignalSeverity.CRITICAL, is_read=True)],
            previous_group=EFFICIENT,
        )
        assert decision.handoff_note is not None


# ── Weighted-random A/B split (the calibration harness) ─────────────────────


class TestWeightedRandomSplit:
    def test_picks_only_configured_groups(self) -> None:
        split = WeightedRandomSplit({"efficient": 1.0}, seed=42)
        for _ in range(50):
            assert split.pick() == EFFICIENT

    def test_weights_are_normalized(self) -> None:
        split = WeightedRandomSplit({"efficient": 70, "capable": 30}, seed=1)
        counts: Dict[str, int] = {EFFICIENT: 0, CAPABLE: 0}
        for _ in range(5000):
            counts[split.pick()] += 1
        ratio = counts[EFFICIENT] / (counts[EFFICIENT] + counts[CAPABLE])
        assert ratio == pytest.approx(0.7, abs=0.05)

    def test_seed_is_deterministic(self) -> None:
        a = WeightedRandomSplit({"efficient": 0.5, "capable": 0.5}, seed=7)
        b = WeightedRandomSplit({"efficient": 0.5, "capable": 0.5}, seed=7)
        assert [a.pick() for _ in range(20)] == [b.pick() for _ in range(20)]

    def test_invalid_groups_rejected(self) -> None:
        with pytest.raises(ValueError):
            WeightedRandomSplit({"bogus": 1.0})
        with pytest.raises(ValueError):
            WeightedRandomSplit({})

    def test_split_overrides_applied_group(self) -> None:
        router = default_router(split=WeightedRandomSplit({"efficient": 1.0}, seed=1))
        decision = router.decide(
            [outcome("get_x", severity=SignalSeverity.MAJOR, is_read=True)],
            use_split=True,
        )
        # signal says capable, harness forces efficient
        assert decision.selected_group == CAPABLE
        assert decision.applied_group == EFFICIENT
        assert decision.split_group == EFFICIENT

    def test_critical_never_rides_split(self) -> None:
        router = default_router(split=WeightedRandomSplit({"efficient": 1.0}, seed=1))
        decision = router.decide(
            [outcome("get_x", severity=SignalSeverity.CRITICAL, is_read=True)],
            use_split=True,
        )
        assert decision.selected_group == CAPABLE
        assert decision.applied_group == CAPABLE


# ── Model-type mapping (agent-loop seam) ────────────────────────────────────


class TestModelTypeMapping:
    def test_shadow_mode_returns_none(self) -> None:
        decision = default_router().decide([])
        assert map_decision_to_model_type(decision, enforce=False) is None

    def test_none_decision_returns_none(self) -> None:
        assert map_decision_to_model_type(None, enforce=True) is None

    def test_capable_maps_to_quality(self) -> None:
        decision = StageDecision(
            selected_group=CAPABLE,
            applied_group=CAPABLE,
            default_group=EFFICIENT,
            split_group=None,
            confidence=0.9,
            source=DecisionSource.DIMENSIONS.value,
            rationale="x",
        )
        assert map_decision_to_model_type(decision, enforce=True) == "quality"

    def test_efficient_maps_to_fast(self) -> None:
        decision = StageDecision(
            selected_group=EFFICIENT,
            applied_group=EFFICIENT,
            default_group=EFFICIENT,
            split_group=None,
            confidence=0.6,
            source=DecisionSource.DIMENSIONS.value,
            rationale="x",
        )
        assert map_decision_to_model_type(decision, enforce=True) == "fast"


# ── End-to-end via execution history + audit persistence ────────────────────


class TestDecideForHistory:
    def test_full_history_flow(self) -> None:
        router = default_router(enabled=True, enforce=False)
        history = (
            'Action: {"tool": "invoke_capability", "params": {}}\n'
            "Observation: Error: tool execution failed\n"
            'Action: {"tool": "invoke_capability", "params": {}}\n'
            "Observation: Error: tool execution failed\n"
            'Action: {"tool": "invoke_capability", "params": {}}\n'
            "Observation: Error: tool execution failed\n"
        )
        decision = asyncio.run(
            router.decide_for_history(
                history, previous_group=EFFICIENT, agent_id="agent-1", workspace_id="ws-1"
            )
        )
        assert decision is not None
        assert decision.selected_group == CAPABLE  # spinning + severity → escalate
        assert decision.handoff_note is not None  # handoff fires on group switch

    def test_audit_row_persisted(self, monkeypatch) -> None:
        from core import models

        persisted: List[Dict] = []

        class FakeSession:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def add(self_inner, row):
                persisted.append({c.name: getattr(row, c.name) for c in row.__table__.columns})

            def commit(self_inner):
                pass

        def fake_get_db_session():
            return FakeSession()

        monkeypatch.setattr("core.database.get_db_session", fake_get_db_session)
        router = default_router(enabled=True, enforce=False)
        decision = asyncio.run(
            router.decide_for_history(
                'Action: {"tool": "get_workflows", "params": {}}\nObservation: ok\n',
                agent_id="agent-1",
                workspace_id="ws-1",
            )
        )
        assert decision is not None
        assert len(persisted) == 1
        row = persisted[0]
        assert row["agent_id"] == "agent-1"
        assert row["workspace_id"] == "ws-1"
        assert row["selected_group"] == EFFICIENT
        assert row["applied_group"] == EFFICIENT
        assert row["decision_source"] == DecisionSource.FALL_OPEN.value
        assert row["enforced"] is False
        assert row["picker"] == StagePicker.EFFICIENT_FIRST.value
        assert row["confidence_threshold"] == pytest.approx(0.5)
        assert json.loads(row["signals"])["severity"] == 0.0

    def test_audit_failure_never_raises(self, monkeypatch) -> None:
        def broken_db():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", broken_db)
        router = default_router(enabled=True, enforce=False)
        decision = asyncio.run(
            router.decide_for_history(
                'Action: {"tool": "get_workflows", "params": {}}\nObservation: ok\n'
            )
        )
        assert decision is not None  # decision still returned

    def test_disabled_router_noop(self) -> None:
        router = default_router(enabled=False)
        decision = asyncio.run(
            router.decide_for_history(
                'Action: {"tool": "get_workflows", "params": {}}\nObservation: ok\n'
            )
        )
        assert decision is None


# ── Singleton config ────────────────────────────────────────────────────────


class TestSingleton:
    def test_env_split_invalid_returns_none(self, monkeypatch) -> None:
        monkeypatch.setenv("ATOM_STAGE_ROUTING_SPLIT", "{not json")
        assert WeightedRandomSplit.from_env() is None

    def test_env_split_valid(self, monkeypatch) -> None:
        monkeypatch.setenv("ATOM_STAGE_ROUTING_SPLIT", '{"efficient": 0.7, "capable": 0.3}')
        split = WeightedRandomSplit.from_env()
        assert split is not None
        assert split.pick() in (EFFICIENT, CAPABLE)

    def test_get_stage_router_constructs(self) -> None:
        router = get_stage_router()
        assert isinstance(router, StageRouter)


# ── Statistical sufficiency helpers ──────────────────────────────────────


class TestSampleSizeHelpers:
    def test_turns_needed_scales_with_effect_size(self) -> None:
        from core.llm.stage_router import min_turns_per_arm

        small_gap = min_turns_per_arm(effect_size=0.05)
        mid_gap = min_turns_per_arm(effect_size=0.10)
        big_gap = min_turns_per_arm(effect_size=0.20)
        assert small_gap > mid_gap > big_gap
        # ~200/arm for a 10-pt gap at base 0.8 (two-proportion z-test, 80% power)
        assert 150 <= mid_gap <= 260
        assert big_gap <= 60

    def test_min_detectable_gap_inverse(self) -> None:
        from core.llm.stage_router import min_detectable_gap, min_turns_per_arm

        n = min_turns_per_arm(effect_size=0.10)
        gap = min_detectable_gap(n)
        assert gap == pytest.approx(0.10, abs=0.01)
        # less data → only larger gaps visible
        assert min_detectable_gap(30) > min_detectable_gap(200)

    def test_invalid_inputs(self) -> None:
        from core.llm.stage_router import min_detectable_gap, min_turns_per_arm

        assert min_turns_per_arm(effect_size=0.0) == 0
        assert min_turns_per_arm(effect_size=-0.1) == 0
        assert min_turns_per_arm(base_rate=0.0) == 0
        assert min_detectable_gap(0) == 1.0

    def test_defaults_are_reasonable(self) -> None:
        from core.llm.stage_router import (
            DEFAULT_TARGET_EFFECT_SIZE,
            min_detectable_gap,
            min_turns_per_arm,
        )

        assert DEFAULT_TARGET_EFFECT_SIZE == 0.10
        assert min_detectable_gap(30) < 0.40  # a 30-turn floor still sees big gaps
        assert min_turns_per_arm() >= 1


# ── Operator guidance (stage_router_status) ─────────────────────────────────


class TestStageRouterStatus:
    def _patch_arms(self, monkeypatch, arms: dict) -> None:
        import core.llm.stage_router as sr

        monkeypatch.setattr(sr, "_read_arm_counts", lambda: arms)

    def test_off_phase_guides_enable(self, monkeypatch) -> None:
        import core.llm.stage_router as sr

        monkeypatch.setattr(sr, "stage_router_enabled", lambda: False)
        monkeypatch.setattr(sr, "stage_routing_force_enforce", lambda: False)
        self._patch_arms(monkeypatch, {})
        status = sr.stage_router_status()
        assert status["phase"] == "off"
        assert "ATOM_STAGE_ROUTING_ENABLED=true" in status["next_action"]
        assert status["why"]  # every phase explains itself

    def test_collecting_until_both_arms_observed(self, monkeypatch) -> None:
        import core.llm.stage_router as sr

        monkeypatch.setattr(sr, "stage_router_enabled", lambda: True)
        monkeypatch.setattr(sr, "stage_routing_force_enforce", lambda: False)
        # one workload, but only the efficient arm has outcome rows
        self._patch_arms(monkeypatch, {"agent-1": {"efficient": 200, "capable": 0}})
        status = sr.stage_router_status()
        assert status["phase"] == "collecting"
        assert "BOTH" in status["next_action"]

    def test_collecting_when_volume_too_low_for_target_gap(self, monkeypatch) -> None:
        import core.llm.stage_router as sr

        monkeypatch.setattr(sr, "stage_router_enabled", lambda: True)
        monkeypatch.setattr(sr, "stage_routing_force_enforce", lambda: False)
        self._patch_arms(monkeypatch, {"agent-1": {"efficient": 5, "capable": 5}})
        status = sr.stage_router_status()
        assert status["phase"] == "collecting"
        assert status["sufficiency"]["agent-1"]["min_detectable_gap"] > 0.10
        assert "10-point" in status["next_action"]

    def test_ready_when_workload_has_both_arms_above_floor(self, monkeypatch) -> None:
        import core.llm.stage_router as sr

        monkeypatch.setattr(sr, "stage_router_enabled", lambda: True)
        monkeypatch.setattr(sr, "stage_routing_force_enforce", lambda: False)
        self._patch_arms(
            monkeypatch,
            {"agent-1": {"efficient": 40, "capable": 35}, "agent-2": {"efficient": 2, "capable": 2}},
        )
        status = sr.stage_router_status()
        assert status["phase"] == "ready"
        assert "agent-1" in status["ready_workloads"]
        assert "agent-2" not in status["ready_workloads"]

    def test_enforced_phase_mentions_recertification(self, monkeypatch) -> None:
        import core.llm.stage_router as sr

        monkeypatch.setattr(sr, "stage_router_enabled", lambda: True)
        monkeypatch.setattr(sr, "stage_routing_force_enforce", lambda: True)
        self._patch_arms(monkeypatch, {"agent-1": {"efficient": 40, "capable": 35}})
        status = sr.stage_router_status()
        assert status["phase"] == "enforced"
        assert "re-certify" in status["next_action"]

    def test_error_phase_on_db_failure(self, monkeypatch) -> None:
        import core.llm.stage_router as sr

        monkeypatch.setattr(sr, "stage_router_enabled", lambda: True)
        monkeypatch.setattr(sr, "stage_routing_force_enforce", lambda: False)

        def broken_read():
            raise RuntimeError("db down")

        monkeypatch.setattr(sr, "_read_arm_counts", broken_read)
        status = sr.stage_router_status()
        assert status["phase"] == "error"
        assert status["why"]


# ── Per-agent policy (workload-specific control) ────────────────────────────


class TestAgentStagePolicy:
    def test_inherits_global_without_config(self) -> None:
        from core.llm.stage_router import resolve_agent_policy

        policy = resolve_agent_policy(None, global_enforce=False)
        assert policy.enforce is False
        assert policy.picker == StagePicker.EFFICIENT_FIRST
        assert policy.source == "global"

    def test_agent_enforce_overrides_global_off(self) -> None:
        from core.llm.stage_router import resolve_agent_policy

        policy = resolve_agent_policy(
            {"stage_routing": {"enforce": True}}, global_enforce=False
        )
        assert policy.enforce is True
        assert policy.source == "agent-config"

    def test_agent_enforce_off_overrides_global_on(self) -> None:
        from core.llm.stage_router import resolve_agent_policy

        policy = resolve_agent_policy(
            {"stage_routing": {"enforce": False}}, global_enforce=True
        )
        assert policy.enforce is False

    def test_agent_tuning_knobs_apply(self) -> None:
        from core.llm.stage_router import resolve_agent_policy

        policy = resolve_agent_policy(
            {
                "stage_routing": {
                    "enforce": True,
                    "confidence_threshold": 0.2,
                    "picker": "capable_first",
                    "window": 5,
                }
            },
            global_enforce=False,
        )
        assert policy.confidence_threshold == 0.2
        assert policy.picker == StagePicker.CAPABLE_FIRST
        assert policy.window == 5

    def test_invalid_values_fall_back_to_global(self) -> None:
        from core.llm.stage_router import resolve_agent_policy

        policy = resolve_agent_policy(
            {
                "stage_routing": {
                    "enforce": "yes",  # not a bool → ignored
                    "confidence_threshold": 7.0,  # clamped to 1.0
                    "picker": "bogus",  # → global default
                    "window": -3,  # → global default
                }
            },
            global_enforce=True,
        )
        assert policy.enforce is True  # global default retained
        assert policy.confidence_threshold == 1.0
        assert policy.picker == StagePicker.EFFICIENT_FIRST
        assert policy.window == default_router().window

    def test_threshold_clamped_to_unit_interval(self) -> None:
        from core.llm.stage_router import resolve_agent_policy

        policy = resolve_agent_policy({"stage_routing": {"confidence_threshold": -0.5}})
        assert policy.confidence_threshold == 0.0

    def test_policy_drives_decision_threshold(self) -> None:
        from core.llm.stage_router import resolve_agent_policy

        router = default_router(confidence_threshold=0.5)
        # policy threshold 0.0 → even a weak signal becomes decisive
        policy = resolve_agent_policy({"stage_routing": {"confidence_threshold": 0.0}})
        decision = router.decide(
            [outcome("get_x", severity=SignalSeverity.MINOR, is_read=True)],
            policy=policy,
        )
        assert decision.source == DecisionSource.DIMENSIONS.value

    def test_policy_picker_sets_fall_open_default(self) -> None:
        from core.llm.stage_router import resolve_agent_policy

        router = default_router()
        policy = resolve_agent_policy({"stage_routing": {"picker": "capable_first"}})
        decision = router.decide([outcome("get_x", is_read=True)], policy=policy)
        assert decision.default_group == CAPABLE
        assert decision.selected_group == CAPABLE

    def test_audit_row_records_policy_fields(self, monkeypatch) -> None:
        import asyncio as _asyncio

        from core.llm.stage_router import resolve_agent_policy

        persisted: List[Dict] = []

        class FakeSession:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def add(self_inner, row):
                persisted.append({c.name: getattr(row, c.name) for c in row.__table__.columns})

            def commit(self_inner):
                pass

        monkeypatch.setattr("core.database.get_db_session", lambda: FakeSession())
        router = default_router(enabled=True, enforce=False)
        policy = resolve_agent_policy(
            {"stage_routing": {"enforce": True, "confidence_threshold": 0.3}},
            global_enforce=False,
        )
        _asyncio.run(
            router.decide_for_history(
                'Action: {"tool": "get_workflows", "params": {}}\nObservation: ok\n',
                agent_id="agent-1",
                policy=policy,
            )
        )
        assert persisted[0]["policy_source"] == "agent-config"
        assert persisted[0]["picker"] == StagePicker.EFFICIENT_FIRST.value
        assert persisted[0]["confidence_threshold"] == pytest.approx(0.3)
        assert persisted[0]["enforced"] is True
