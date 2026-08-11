"""Tests for the traffic-split harness and the stage-router outcome join.

Covers: ``pick_arm``/``assign_arm`` contracts, flag gating, the group-level
split wiring, the contextvar carrier, and ``record_stage_outcome`` writing
attempt outcomes back onto audit rows (the calibration data path).
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

import pytest

from core.llm.routing.traffic_split import (
    assign_arm,
    get_traffic_split,
    pick_arm,
    traffic_split_enabled,
)
from core.llm.stage_router import (
    EFFICIENT,
    get_stage_decision_carrier,
    record_stage_outcome,
    set_stage_decision_carrier,
)


class TestPickArm:
    def test_weights_respected(self) -> None:
        options = [("a", "arm-a"), ("b", "arm-b")]
        rng = random.Random(1)
        counts = {"a": 0, "b": 0}
        for _ in range(4000):
            arm_id, _label = pick_arm(options, [0.9, 0.1], rng=rng)
            counts[arm_id] += 1
        assert counts["a"] / sum(counts.values()) == pytest.approx(0.9, abs=0.05)

    def test_uniform_when_no_weights(self) -> None:
        options = [("a", "arm-a"), ("b", "arm-b")]
        rng = random.Random(2)
        assert pick_arm(options, rng=rng) in options

    def test_returns_full_tuple(self) -> None:
        arm = pick_arm([("x", "label-x")])
        assert arm == ("x", "label-x")

    def test_weight_length_mismatch_falls_back_uniform(self) -> None:
        options = [("a", "arm-a"), ("b", "arm-b"), ("c", "arm-c")]
        arm = pick_arm(options, [1.0])  # wrong length → uniform, never raises
        assert arm in options

    def test_nonpositive_weights_fall_back_uniform(self) -> None:
        options = [("a", "arm-a"), ("b", "arm-b")]
        assert pick_arm(options, [0.0, 0.0]) in options

    def test_empty_options_raises(self) -> None:
        with pytest.raises(ValueError):
            pick_arm([])


class TestAssignArm:
    def test_summary_contract(self) -> None:
        summary = assign_arm(
            "decision-1",
            [("m1", "model-1"), ("m2", "model-2"), ("m3", "model-3")],
            top_k=2,
            weights=[0.7, 0.3],
            rng=random.Random(3),
        )
        assert summary["decision_id"] == "decision-1"
        assert summary["arm"] in ("m1", "m2")  # top-k limits eligibility
        assert summary["top_k"] == 2
        assert summary["weights"] == [0.7, 0.3]
        assert summary["deterministic"] is True

    def test_deterministic_with_seeded_rng(self) -> None:
        a = assign_arm("d", [("m1", "a"), ("m2", "b")], rng=random.Random(7))
        b = assign_arm("d", [("m1", "a"), ("m2", "b")], rng=random.Random(7))
        assert a == b


class TestFlagGating:
    def test_disabled_by_default(self, monkeypatch) -> None:
        monkeypatch.delenv("ATOM_TRAFFIC_SPLIT", raising=False)
        monkeypatch.delenv("ATOM_STAGE_ROUTING_SPLIT", raising=False)
        assert traffic_split_enabled() is False
        assert get_traffic_split() is None

    def test_enabled_by_master_flag(self, monkeypatch) -> None:
        monkeypatch.setenv("ATOM_TRAFFIC_SPLIT", "true")
        monkeypatch.setenv("ATOM_STAGE_ROUTING_SPLIT", '{"efficient": 0.5, "capable": 0.5}')
        assert traffic_split_enabled() is True
        split = get_traffic_split()
        assert split is not None
        assert split.pick() in (EFFICIENT, "capable")

    def test_weights_presence_enables(self, monkeypatch) -> None:
        monkeypatch.setenv("ATOM_TRAFFIC_SPLIT", "false")
        monkeypatch.setenv("ATOM_STAGE_ROUTING_SPLIT", '{"efficient": 1.0, "capable": 0.0}')
        assert traffic_split_enabled() is True


# ── Outcome join (carrier + record_stage_outcome) ───────────────────────────


class TestOutcomeJoin:
    def test_carrier_default_none(self) -> None:
        assert get_stage_decision_carrier() is None

    def test_carrier_set_get(self) -> None:
        set_stage_decision_carrier("decision-abc")
        assert get_stage_decision_carrier() == "decision-abc"
        set_stage_decision_carrier(None)
        assert get_stage_decision_carrier() is None

    def test_record_stage_outcome_updates_row(self, monkeypatch) -> None:
        class FakeRow:
            def __init__(self, decision_id: str) -> None:
                self.id = decision_id
                self.success: Optional[bool] = None
                self.quality_satisfied: Optional[bool] = None
                self.actual_cost: Optional[float] = None
                self.actual_latency_ms: Optional[float] = None
                self.actual_model: Optional[str] = None
                self.actual_provider: Optional[str] = None

        rows: Dict[str, FakeRow] = {"decision-abc": FakeRow("decision-abc")}

        class FakeQuery:
            def __init__(self, target_id: str) -> None:
                self.target_id = target_id

            def filter(self, *args, **kwargs):  # noqa: A002 - fake query chain
                return self

            def first(self) -> Optional[FakeRow]:
                return rows.get(self.target_id)

        class FakeSession:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def query(self_inner, model):
                return FakeQuery("decision-abc")

            def commit(self_inner):
                pass

        monkeypatch.setattr("core.database.get_db_session", lambda: FakeSession())
        record_stage_outcome(
            "decision-abc",
            success=True,
            schema_error=False,
            content="ok",
            finish_reason="stop",
            actual_cost=0.0012,
            actual_latency_ms=340.0,
            actual_model="deepseek-v4-flash",
            actual_provider="opencode-go",
        )
        row = rows["decision-abc"]
        assert row.success is True
        assert row.quality_satisfied is True
        assert row.actual_cost == pytest.approx(0.0012)
        assert row.actual_latency_ms == pytest.approx(340.0)
        assert row.actual_model == "deepseek-v4-flash"
        assert row.actual_provider == "opencode-go"

    def test_record_stage_outcome_missing_row_noop(self, monkeypatch) -> None:
        class FakeQuery:
            def filter(self, *args, **kwargs):  # noqa: A002
                return self

            def first(self):
                return None

        class FakeSession:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def query(self_inner, model):
                return FakeQuery()

            def commit(self_inner):
                pass

        monkeypatch.setattr("core.database.get_db_session", lambda: FakeSession())
        record_stage_outcome("does-not-exist", success=True)  # must not raise

    def test_record_stage_outcome_db_failure_never_raises(self, monkeypatch) -> None:
        def broken_db():
            raise RuntimeError("db down")

        monkeypatch.setattr("core.database.get_db_session", broken_db)
        record_stage_outcome("decision-abc", success=False)  # must not raise

    def test_decision_carries_stable_id(self) -> None:
        from core.llm.stage_router import (
            DecisionSource,
            StageDecision,
            StageRouter,
        )

        decision = StageRouter().decide([])
        assert decision.id
        d2 = StageDecision(
            selected_group=EFFICIENT,
            applied_group=EFFICIENT,
            default_group=EFFICIENT,
            split_group=None,
            confidence=0.0,
            source=DecisionSource.FALL_OPEN.value,
            rationale="x",
        )
        assert d2.id != decision.id  # fresh id per decision
