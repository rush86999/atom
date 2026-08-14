# -*- coding: utf-8 -*-
"""Coverage wave 108 — core/debug_insights/consistency (in-memory SQLite, zero LLM spend).

- ConsistencyInsightGenerator.analyze_data_flow: no snapshots, missing
  components, replication lag >5s, consistent, single snapshot, exception.
- detect_state_divergence: <2 snapshots, divergence (critical), consistent
  (None), exception.
- _compare_states: equal values, missing key, divergent values, empty state
  data.
- verify_replication_completion: incomplete (warning), complete (info),
  exception.
- analyze_sync_patterns: none, single-component op (info), multi-component op,
  exception.
- _parse_time_range: all 4 branches.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (  # noqa: F401 (register models)
    DebugStateSnapshot,
)
from core.debug_insights.consistency import ConsistencyInsightGenerator


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _snapshot(db, sid, *, operation_id="op-1", component_type="agent",
              component_id="node-1", state_data=None, captured_at=None):
    snap = DebugStateSnapshot(
        id=sid,
        component_type=component_type,
        component_id=component_id,
        operation_id=operation_id,
        snapshot_type="full",
        state_data=state_data if state_data is not None else {"x": 1},
        captured_at=captured_at if captured_at is not None else datetime.now(timezone.utc),
    )
    db.add(snap)
    db.commit()
    return snap


class _BadSession:
    def query(self, model):
        raise RuntimeError("db down")

    def add(self, obj):
        raise RuntimeError("db down")


# ============================================================================
# analyze_data_flow
# ============================================================================

class TestAnalyzeDataFlow:
    async def test_no_snapshots_returns_none(self, db):
        gen = ConsistencyInsightGenerator(db)
        assert await gen.analyze_data_flow("op-nope", ["node-1"]) is None

    async def test_missing_components(self, db):
        _snapshot(db, "s1", operation_id="op-2", component_id="node-1")
        gen = ConsistencyInsightGenerator(db)
        insight = await gen.analyze_data_flow("op-2", ["node-1", "node-2"])
        assert insight is not None
        assert insight.severity == "warning"
        assert insight.title == "Incomplete data propagation"
        assert insight.evidence["missing_components"] == ["node-2"]
        assert insight.evidence["propagation_rate"] == 0.5
        assert insight.evidence["expected_components"] == ["node-1", "node-2"]
        assert insight.confidence_score == 0.95
        assert len(insight.affected_components) == 2

    async def test_replication_lag(self, db):
        base = datetime.now(timezone.utc)
        _snapshot(db, "l1", operation_id="op-3", component_id="node-1",
                  captured_at=base)
        _snapshot(db, "l2", operation_id="op-3", component_id="node-2",
                  captured_at=base + timedelta(seconds=10))
        gen = ConsistencyInsightGenerator(db)
        insight = await gen.analyze_data_flow("op-3", ["node-1", "node-2"])
        assert insight is not None
        assert insight.severity == "warning"
        assert insight.title == "Replication lag detected"
        assert insight.evidence["replication_lag_seconds"] == 10
        assert insight.evidence["first_confirmation"] is not None
        assert insight.evidence["last_confirmation"] is not None
        assert insight.confidence_score == 0.90

    async def test_consistent(self, db):
        base = datetime.now(timezone.utc)
        _snapshot(db, "c1", operation_id="op-4", component_id="node-1",
                  captured_at=base)
        _snapshot(db, "c2", operation_id="op-4", component_id="node-2",
                  captured_at=base + timedelta(seconds=1))
        gen = ConsistencyInsightGenerator(db)
        insight = await gen.analyze_data_flow("op-4", ["node-1", "node-2"])
        assert insight is not None
        assert insight.severity == "info"
        assert insight.title == "Data consistent across all nodes"
        assert insight.evidence["replication_complete"] is True
        assert insight.evidence["component_count"] == 2
        assert insight.confidence_score == 1.0

    async def test_single_snapshot_consistent(self, db):
        _snapshot(db, "c3", operation_id="op-5", component_id="node-1")
        gen = ConsistencyInsightGenerator(db)
        insight = await gen.analyze_data_flow("op-5", ["node-1"])
        assert insight is not None
        assert insight.severity == "info"

    async def test_exception_returns_none(self):
        gen = ConsistencyInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.analyze_data_flow("op-x", ["node-1"]) is None


# ============================================================================
# detect_state_divergence
# ============================================================================

class TestDetectStateDivergence:
    async def test_single_snapshot_returns_none(self, db):
        _snapshot(db, "d1", operation_id="op-d", component_id="node-1")
        gen = ConsistencyInsightGenerator(db)
        assert await gen.detect_state_divergence("op-d") is None

    async def test_no_snapshots_returns_none(self, db):
        gen = ConsistencyInsightGenerator(db)
        assert await gen.detect_state_divergence("op-nope") is None

    async def test_divergence_detected(self, db):
        _snapshot(db, "x1", operation_id="op-x", component_id="node-1",
                  state_data={"a": 1, "b": "same"})
        _snapshot(db, "x2", operation_id="op-x", component_id="node-2",
                  state_data={"a": 2, "b": "same"})
        gen = ConsistencyInsightGenerator(db)
        insight = await gen.detect_state_divergence("op-x")
        assert insight is not None
        assert insight.severity == "critical"
        assert insight.title == "State divergence detected"
        assert insight.evidence["affected_keys"] == ["a"]
        inc = insight.evidence["inconsistencies"]["a"]
        assert inc["divergence_detected"] is True
        assert inc["values"] == {"node-1": 1, "node-2": 2}
        assert insight.confidence_score == 0.92
        assert len(insight.affected_components) == 2

    async def test_consistent_returns_none(self, db):
        _snapshot(db, "y1", operation_id="op-y", component_id="node-1",
                  state_data={"a": 1})
        _snapshot(db, "y2", operation_id="op-y", component_id="node-2",
                  state_data={"a": 1})
        gen = ConsistencyInsightGenerator(db)
        assert await gen.detect_state_divergence("op-y") is None

    async def test_latest_snapshot_per_component_used(self, db):
        _snapshot(db, "z1", operation_id="op-z", component_id="node-1",
                  state_data={"a": 1})
        _snapshot(db, "z2", operation_id="op-z", component_id="node-1",
                  state_data={"a": 1})
        _snapshot(db, "z3", operation_id="op-z", component_id="node-2",
                  state_data={"a": 2})
        gen = ConsistencyInsightGenerator(db)
        insight = await gen.detect_state_divergence("op-z")
        assert insight is not None
        assert insight.evidence["affected_keys"] == ["a"]

    async def test_exception_returns_none(self):
        gen = ConsistencyInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.detect_state_divergence("op-x") is None


# ============================================================================
# _compare_states
# ============================================================================

class TestCompareStates:
    def test_equal_values(self, db):
        s1 = _snapshot(db, "c1", operation_id="op-c", component_id="node-1",
                       state_data={"a": 1, "b": "x"})
        s2 = _snapshot(db, "c2", operation_id="op-c", component_id="node-2",
                       state_data={"a": 1, "b": "x"})
        gen = ConsistencyInsightGenerator(db)
        assert gen._compare_states({"node-1": s1, "node-2": s2}) == {}

    def test_divergent_values(self, db):
        s1 = _snapshot(db, "d1", operation_id="op-d", component_id="node-1",
                       state_data={"a": 1})
        s2 = _snapshot(db, "d2", operation_id="op-d", component_id="node-2",
                       state_data={"a": 2})
        gen = ConsistencyInsightGenerator(db)
        result = gen._compare_states({"node-1": s1, "node-2": s2})
        assert set(result.keys()) == {"a"}
        assert result["a"]["divergence_detected"] is True

    def test_key_missing_on_one_component(self, db):
        s1 = _snapshot(db, "m1", operation_id="op-m", component_id="node-1",
                       state_data={"a": 1})
        s2 = _snapshot(db, "m2", operation_id="op-m", component_id="node-2",
                       state_data={"b": 2})
        gen = ConsistencyInsightGenerator(db)
        result = gen._compare_states({"node-1": s1, "node-2": s2})
        # key 'a' only on node-1 -> no divergence; key 'b' only on node-2
        assert result == {}

    def test_empty_state_data(self, db):
        s1 = _snapshot(db, "e1", operation_id="op-e", component_id="node-1",
                       state_data={})
        s2 = _snapshot(db, "e2", operation_id="op-e", component_id="node-2",
                       state_data={"a": 1})
        gen = ConsistencyInsightGenerator(db)
        assert gen._compare_states({"node-1": s1, "node-2": s2}) == {}

    def test_second_snapshot_without_state_data(self, db):
        s1 = _snapshot(db, "f1", operation_id="op-f", component_id="node-1",
                       state_data={"a": 1})
        s2 = _snapshot(db, "f2", operation_id="op-f", component_id="node-2",
                       state_data={"a": 2})
        s2.state_data = None
        db.commit()
        gen = ConsistencyInsightGenerator(db)
        result = gen._compare_states({"node-1": s1, "node-2": s2})
        # node-2 lacks state_data -> only node-1 value -> no divergence
        assert result == {}


# ============================================================================
# verify_replication_completion
# ============================================================================

class TestVerifyReplicationCompletion:
    async def test_incomplete(self, db):
        _snapshot(db, "r1", operation_id="op-r", component_id="node-1")
        gen = ConsistencyInsightGenerator(db)
        insight = await gen.verify_replication_completion("op-r", 3)
        assert insight is not None
        assert insight.severity == "warning"
        assert insight.title == "Incomplete replication"
        assert insight.evidence["expected_replicas"] == 3
        assert insight.evidence["actual_replicas"] == 1
        assert insight.evidence["completion_rate"] == 1 / 3
        assert insight.confidence_score == 0.98
        assert insight.affected_components == [{"type": "agent"}]

    async def test_complete(self, db):
        _snapshot(db, "c1", operation_id="op-c", component_id="node-1")
        _snapshot(db, "c2", operation_id="op-c", component_id="node-2")
        _snapshot(db, "c3", operation_id="op-c", component_id="node-3")
        gen = ConsistencyInsightGenerator(db)
        insight = await gen.verify_replication_completion("op-c", 3)
        assert insight is not None
        assert insight.severity == "info"
        assert insight.title == "Replication complete"
        assert insight.evidence["replica_count"] == 3
        assert insight.confidence_score == 1.0

    async def test_zero_expected(self, db):
        _snapshot(db, "z1", operation_id="op-z", component_id="node-1")
        gen = ConsistencyInsightGenerator(db)
        insight = await gen.verify_replication_completion("op-z", 0)
        assert insight is not None
        assert insight.severity == "info"

    async def test_exception_returns_none(self):
        gen = ConsistencyInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.verify_replication_completion("op-x", 2) is None


# ============================================================================
# analyze_sync_patterns
# ============================================================================

class TestAnalyzeSyncPatterns:
    async def test_no_snapshots(self, db):
        gen = ConsistencyInsightGenerator(db)
        assert await gen.analyze_sync_patterns() == []

    async def test_single_component_operation(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1")
        gen = ConsistencyInsightGenerator(db)
        insights = await gen.analyze_sync_patterns("last_1h")
        assert len(insights) == 1
        insight = insights[0]
        assert insight.severity == "info"
        assert insight.title == "Single-component operation detected"
        assert insight.evidence["operation_id"] == "op-1"
        assert insight.confidence_score == 0.70
        assert insight.affected_components == []

    async def test_multi_component_operation_skipped(self, db):
        _snapshot(db, "m1", operation_id="op-2", component_id="node-1")
        _snapshot(db, "m2", operation_id="op-2", component_id="node-2")
        gen = ConsistencyInsightGenerator(db)
        assert await gen.analyze_sync_patterns() == []

    async def test_outside_time_range(self, db):
        _snapshot(db, "o1", operation_id="op-3", component_id="node-1",
                  captured_at=datetime.now(timezone.utc) - timedelta(days=2))
        gen = ConsistencyInsightGenerator(db)
        assert await gen.analyze_sync_patterns("last_1h") == []

    async def test_exception_returns_empty(self):
        gen = ConsistencyInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.analyze_sync_patterns() == []


# ============================================================================
# _parse_time_range
# ============================================================================

class TestParseTimeRange:
    def test_all_branches(self, db):
        gen = ConsistencyInsightGenerator(db)
        now = datetime.now(timezone.utc)
        for label, delta in [
            ("last_1h", timedelta(hours=1)),
            ("last_24h", timedelta(hours=24)),
            ("last_7d", timedelta(days=7)),
            ("bogus", timedelta(hours=1)),
        ]:
            cutoff = gen._parse_time_range(label)
            assert abs((now - delta - cutoff).total_seconds()) < 5, label
