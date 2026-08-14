# -*- coding: utf-8 -*-
"""Coverage wave 84c (debug-insights part) — 3 core/debug_insights modules.

EXTENDS the w108 suites (before-%: consistency 100%, error_causality 100%,
flow 100%). Re-derives >=95% standalone coverage for:

  core/debug_insights/consistency.py
  core/debug_insights/error_causality.py
  core/debug_insights/flow.py

Style: real in-memory SQLite (SQLAlchemy), zero LLM spend, no network.
Exception paths use a session whose query() raises.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.debug_insights.consistency import ConsistencyInsightGenerator
from core.debug_insights.error_causality import ErrorCausalityInsightGenerator
from core.debug_insights.flow import FlowInsightGenerator
from core.models import (  # noqa: F401 (register models)
    DebugEvent,
    DebugInsight,
    DebugStateSnapshot,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


class _BadSession:
    def query(self, model):
        raise RuntimeError("db down")

    def add(self, obj):
        raise RuntimeError("db down")


def _event(db, eid, *, correlation_id="corr-1", component_type="agent",
           component_id="agent-1", level="INFO", message="msg",
           parent_event_id=None, ts=None):
    event = DebugEvent(
        id=eid,
        event_type="log",
        component_type=component_type,
        component_id=component_id,
        correlation_id=correlation_id,
        level=level,
        message=message,
        parent_event_id=parent_event_id,
        timestamp=ts if ts is not None else datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    return event


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


# ============================================================================
# core/debug_insights/consistency.py
# ============================================================================


class TestAnalyzeDataFlow:
    async def test_no_snapshots_returns_none(self, db):
        gen = ConsistencyInsightGenerator(db)
        assert await gen.analyze_data_flow("op-missing", ["node-1"]) is None

    async def test_missing_components_warning(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1")
        insight = await ConsistencyInsightGenerator(db).analyze_data_flow("op-1", ["node-1", "node-2"])
        assert insight is not None
        assert insight.severity == "warning"
        assert insight.title == "Incomplete data propagation"
        assert insight.evidence["propagation_rate"] == 0.5
        assert len(insight.suggestions) == 3
        assert insight.affected_components == [{"type": "agent", "id": "node-1"}, {"type": "agent", "id": "node-2"}]

    async def test_replication_lag_warning(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1",
                  captured_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        _snapshot(db, "s2", operation_id="op-1", component_id="node-2",
                  captured_at=datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc))
        insight = await ConsistencyInsightGenerator(db).analyze_data_flow("op-1", ["node-1", "node-2"])
        assert insight.title == "Replication lag detected"
        assert insight.severity == "warning"
        assert insight.evidence["replication_lag_seconds"] == 10.0
        assert insight.confidence_score == 0.90

    async def test_consistent_info(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1",
                  captured_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        _snapshot(db, "s2", operation_id="op-1", component_id="node-2",
                  captured_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc))
        insight = await ConsistencyInsightGenerator(db).analyze_data_flow("op-1", ["node-1", "node-2"])
        assert insight.title == "Data consistent across all nodes"
        assert insight.severity == "info"
        assert insight.evidence["replication_complete"] is True
        assert insight.confidence_score == 1.0

    async def test_single_snapshot_consistent(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1")
        insight = await ConsistencyInsightGenerator(db).analyze_data_flow("op-1", ["node-1"])
        assert insight.title == "Data consistent across all nodes"

    async def test_snapshot_without_captured_at(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1", captured_at=None)
        insight = await ConsistencyInsightGenerator(db).analyze_data_flow("op-1", ["node-1"])
        assert insight is not None
        assert insight.title == "Data consistent across all nodes"

    async def test_exception_returns_none(self):
        gen = ConsistencyInsightGenerator(_BadSession())
        assert await gen.analyze_data_flow("op-1", ["node-1"]) is None


class TestDetectStateDivergence:
    async def test_less_than_two_returns_none(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1")
        assert await ConsistencyInsightGenerator(db).detect_state_divergence("op-1") is None

    async def test_divergence_critical(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1", state_data={"key": "a"})
        _snapshot(db, "s2", operation_id="op-1", component_id="node-2", state_data={"key": "b"})
        insight = await ConsistencyInsightGenerator(db).detect_state_divergence("op-1")
        assert insight is not None
        assert insight.severity == "critical"
        assert insight.title == "State divergence detected"
        assert "key" in insight.evidence["affected_keys"]
        assert sorted(insight.affected_components, key=lambda c: c["id"]) == [
            {"type": "agent", "id": "node-1"},
            {"type": "agent", "id": "node-2"},
        ]

    async def test_consistent_returns_none(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1", state_data={"key": "a"})
        _snapshot(db, "s2", operation_id="op-1", component_id="node-2", state_data={"key": "a"})
        assert await ConsistencyInsightGenerator(db).detect_state_divergence("op-1") is None

    async def test_latest_snapshot_per_component(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1", state_data={"key": "old"},
                  captured_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        _snapshot(db, "s2", operation_id="op-1", component_id="node-1", state_data={"key": "new"},
                  captured_at=datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc))
        _snapshot(db, "s3", operation_id="op-1", component_id="node-2", state_data={"key": "new"},
                  captured_at=datetime(2026, 1, 1, 0, 0, 6, tzinfo=timezone.utc))
        assert await ConsistencyInsightGenerator(db).detect_state_divergence("op-1") is None

    async def test_exception_returns_none(self):
        gen = ConsistencyInsightGenerator(_BadSession())
        assert await gen.detect_state_divergence("op-1") is None


class TestCompareStates:
    def test_equal_values(self, db):
        gen = ConsistencyInsightGenerator(db)
        s1 = _snapshot(db, "s1", component_id="n1", state_data={"k": 1})
        s2 = _snapshot(db, "s2", component_id="n2", state_data={"k": 1})
        assert gen._compare_states({"n1": s1, "n2": s2}) == {}

    def test_missing_key_in_one(self, db):
        gen = ConsistencyInsightGenerator(db)
        s1 = _snapshot(db, "s1", component_id="n1", state_data={"k": 1, "only": 1})
        s2 = _snapshot(db, "s2", component_id="n2", state_data={"k": 1})
        assert gen._compare_states({"n1": s1, "n2": s2}) == {}

    def test_divergent_values(self, db):
        gen = ConsistencyInsightGenerator(db)
        s1 = _snapshot(db, "s1", component_id="n1", state_data={"k": 1})
        s2 = _snapshot(db, "s2", component_id="n2", state_data={"k": 2})
        inconsistencies = gen._compare_states({"n1": s1, "n2": s2})
        assert "k" in inconsistencies
        assert inconsistencies["k"]["divergence_detected"] is True
        assert inconsistencies["k"]["values"] == {"n1": 1, "n2": 2}

    def test_empty_state_data(self, db):
        gen = ConsistencyInsightGenerator(db)
        s1 = _snapshot(db, "s1", component_id="n1", state_data=None)
        s2 = _snapshot(db, "s2", component_id="n2", state_data={})
        assert gen._compare_states({"n1": s1, "n2": s2}) == {}

    def test_str_vs_int_values_divergent(self, db):
        gen = ConsistencyInsightGenerator(db)
        s1 = _snapshot(db, "s1", component_id="n1", state_data={"k": True})
        s2 = _snapshot(db, "s2", component_id="n2", state_data={"k": 1})
        inconsistencies = gen._compare_states({"n1": s1, "n2": s2})
        assert "k" in inconsistencies  # str(True) != str(1)


class TestVerifyReplicationCompletion:
    async def test_incomplete_warning(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1")
        insight = await ConsistencyInsightGenerator(db).verify_replication_completion("op-1", 3)
        assert insight is not None
        assert insight.title == "Incomplete replication"
        assert insight.severity == "warning"
        assert insight.evidence["completion_rate"] == 1 / 3
        assert insight.affected_components == [{"type": "agent"}]

    async def test_complete_info(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1")
        _snapshot(db, "s2", operation_id="op-1", component_id="node-2")
        insight = await ConsistencyInsightGenerator(db).verify_replication_completion("op-1", 2)
        assert insight.title == "Replication complete"
        assert insight.severity == "info"
        assert insight.evidence["replica_count"] == 2

    async def test_duplicate_component_rows_counted_once(self, db):
        # Regression: DISTINCT ON is PG-only and silently ignored by SQLite —
        # duplicate rows for the same component_id must count as ONE replica.
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1")
        _snapshot(db, "s2", operation_id="op-1", component_id="node-1")
        insight = await ConsistencyInsightGenerator(db).verify_replication_completion("op-1", 2)
        assert insight.title == "Incomplete replication"
        assert insight.evidence["actual_replicas"] == 1

    async def test_exception_returns_none(self):
        gen = ConsistencyInsightGenerator(_BadSession())
        assert await gen.verify_replication_completion("op-1", 2) is None


class TestAnalyzeSyncPatterns:
    async def test_no_operations(self, db):
        assert await ConsistencyInsightGenerator(db).analyze_sync_patterns() == []

    async def test_single_component_operation_info(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1")
        insights = await ConsistencyInsightGenerator(db).analyze_sync_patterns()
        assert len(insights) == 1
        assert insights[0].title == "Single-component operation detected"
        assert insights[0].severity == "info"
        assert insights[0].evidence == {"operation_id": "op-1"}

    async def test_multi_component_operation_no_insight(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1")
        _snapshot(db, "s2", operation_id="op-1", component_id="node-2")
        assert await ConsistencyInsightGenerator(db).analyze_sync_patterns() == []

    async def test_custom_time_range(self, db):
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1",
                  captured_at=datetime.now(timezone.utc) - timedelta(days=10))
        assert await ConsistencyInsightGenerator(db).analyze_sync_patterns(time_range="last_24h") == []

    async def test_duplicate_component_rows_single_component_insight(self, db):
        # Regression: two snapshots from the SAME component must count as one
        # component in analyze_sync_patterns (portable distinct count).
        _snapshot(db, "s1", operation_id="op-1", component_id="node-1")
        _snapshot(db, "s2", operation_id="op-1", component_id="node-1")
        insights = await ConsistencyInsightGenerator(db).analyze_sync_patterns()
        assert len(insights) == 1
        assert insights[0].title == "Single-component operation detected"

    async def test_exception_returns_empty(self):
        gen = ConsistencyInsightGenerator(_BadSession())
        assert await gen.analyze_sync_patterns() == []


class TestConsistencyParseTimeRange:
    def test_all_branches(self, db):
        gen = ConsistencyInsightGenerator(db)
        now = datetime.now(timezone.utc)
        assert abs(now - gen._parse_time_range("last_1h") - timedelta(hours=1)).total_seconds() < 5
        assert abs(now - gen._parse_time_range("last_24h") - timedelta(hours=24)).total_seconds() < 5
        assert abs(now - gen._parse_time_range("last_7d") - timedelta(days=7)).total_seconds() < 5
        assert abs(now - gen._parse_time_range("bogus") - timedelta(hours=1)).total_seconds() < 5


# ============================================================================
# core/debug_insights/error_causality.py
# ============================================================================


class TestAnalyzeErrorChain:
    async def test_missing_event_returns_none(self, db):
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.analyze_error_chain("no-such-id") is None

    async def test_non_error_level_returns_none(self, db):
        _event(db, "e1", level="INFO")
        assert await ErrorCausalityInsightGenerator(db).analyze_error_chain("e1") is None

    async def test_single_event_info_insight(self, db):
        _event(db, "e1", level="ERROR", message="boom", component_type="agent", component_id="a1")
        insight = await ErrorCausalityInsightGenerator(db).analyze_error_chain("e1")
        assert insight is not None
        assert insight.severity == "info"
        assert insight.title == "Error analysis"
        assert insight.summary == "boom"
        assert insight.evidence["chain_length"] == 1
        assert insight.affected_components == [{"type": "agent", "id": "a1"}]

    async def test_single_event_no_message(self, db):
        _event(db, "e1", level="CRITICAL", message=None)
        insight = await ErrorCausalityInsightGenerator(db).analyze_error_chain("e1")
        assert insight.summary == "No message"

    async def test_chain_root_cause(self, db):
        _event(db, "e1", level="ERROR", message="outer failure", component_type="agent", component_id="a1")
        _event(db, "e2", level="ERROR", message="inner cause", component_type="browser", component_id="b1",
               parent_event_id="e1")
        insight = await ErrorCausalityInsightGenerator(db).analyze_error_chain("e2")
        assert insight is not None
        assert insight.severity == "critical"
        assert insight.title == "Root cause analysis for error in browser/b1"
        assert "outer failure" in insight.description
        assert "agent/a1 → browser/b1" in insight.description
        assert insight.evidence["root_cause"]["event_id"] == "e1"
        assert insight.evidence["chain_length"] == 2
        assert insight.evidence["propagation_chain"][0]["message"] == "inner cause"
        assert len(insight.affected_components) == 2

    async def test_chain_root_cause_no_message(self, db):
        _event(db, "e1", level="ERROR", message=None, component_type="agent", component_id="a1")
        _event(db, "e2", level="ERROR", message="outer", component_type="browser", component_id="b1",
               parent_event_id="e1")
        insight = await ErrorCausalityInsightGenerator(db).analyze_error_chain("e2")
        assert "No message" in insight.summary
        assert "Root cause: Unknown" in insight.description

    async def test_cycle_terminates(self, db):
        _event(db, "e1", level="ERROR", message="m1", component_type="agent", component_id="a1",
               parent_event_id="e2")
        _event(db, "e2", level="ERROR", message="m2", component_type="agent", component_id="a2",
               parent_event_id="e1")
        insight = await ErrorCausalityInsightGenerator(db).analyze_error_chain("e1")
        assert insight is not None
        assert insight.evidence["chain_length"] == 2

    async def test_exception_returns_none(self):
        gen = ErrorCausalityInsightGenerator(_BadSession())
        assert await gen.analyze_error_chain("e1") is None


class TestTrackErrorPropagation:
    async def test_no_events_returns_none(self, db):
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.track_error_propagation("corr-empty") is None

    async def test_no_error_events_returns_none(self, db):
        _event(db, "e1", correlation_id="corr-1", level="INFO")
        assert await ErrorCausalityInsightGenerator(db).track_error_propagation("corr-1") is None

    async def test_propagation_stops_at_first_error(self, db):
        base = datetime.now(timezone.utc)
        _event(db, "e1", correlation_id="corr-1", level="INFO", component_type="agent", component_id="a1",
               message="start", ts=base)
        _event(db, "e2", correlation_id="corr-1", level="ERROR", component_type="browser", component_id="b1",
               message="failed", ts=base + timedelta(seconds=1))
        _event(db, "e3", correlation_id="corr-1", level="CRITICAL", component_type="workflow", component_id="w1",
               message="after error", ts=base + timedelta(seconds=2))
        insight = await ErrorCausalityInsightGenerator(db).track_error_propagation("corr-1")
        assert insight is not None
        assert insight.severity == "critical"
        assert insight.title == "Error propagation in operation corr-1"
        assert set(insight.evidence["affected_components"]) == {"agent/a1", "browser/b1"}
        assert len(insight.evidence["propagation_order"]) == 2
        assert insight.affected_components == [{"type": "agent", "id": "a1"}, {"type": "browser", "id": "b1"}]

    async def test_exception_returns_none(self):
        gen = ErrorCausalityInsightGenerator(_BadSession())
        assert await gen.track_error_propagation("corr-1") is None


class TestDetectErrorPatterns:
    async def test_no_patterns_returns_empty(self, db):
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.detect_error_patterns() == []

    async def test_no_error_events(self, db):
        _event(db, "e1", level="INFO", message="same message")
        assert await ErrorCausalityInsightGenerator(db).detect_error_patterns() == []

    async def test_pattern_detected(self, db):
        base = datetime.now(timezone.utc) - timedelta(minutes=30)
        for i in range(5):
            _event(db, f"e{i}", level="ERROR", message="pool exhausted",
                   component_type="agent", component_id=f"a{i % 2}",
                   ts=base + timedelta(minutes=i))
        insights = await ErrorCausalityInsightGenerator(db).detect_error_patterns()
        assert len(insights) == 1
        insight = insights[0]
        assert insight.title == "Recurring error pattern: pool exhausted"
        assert insight.severity == "warning"
        assert insight.evidence["occurrence_count"] == 5
        assert len(insight.evidence["affected_components"]) == 2
        assert insight.evidence["duration_seconds"] == 240.0
        assert insight.evidence["frequency_per_min"] == 5 / 4
        assert insight.affected_components == [{"type": "agent", "id": "a0"}, {"type": "agent", "id": "a1"}]

    async def test_pattern_same_timestamp_zero_duration(self, db):
        ts = datetime.now(timezone.utc)
        for i in range(5):
            _event(db, f"e{i}", level="ERROR", message="burst", ts=ts)
        insights = await ErrorCausalityInsightGenerator(db).detect_error_patterns()
        assert insights[0].evidence["frequency_per_min"] == 0

    async def test_below_threshold_no_insight(self, db):
        for i in range(4):
            _event(db, f"e{i}", level="ERROR", message="rare error")
        assert await ErrorCausalityInsightGenerator(db).detect_error_patterns() == []

    async def test_exception_returns_empty(self):
        gen = ErrorCausalityInsightGenerator(_BadSession())
        assert await gen.detect_error_patterns() == []


class TestSuggestFixesFromHistory:
    async def test_no_history_returns_empty(self, db):
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.suggest_fixes_from_history("connection timeout") == []

    async def test_history_connection_timeout(self, db):
        _event(db, "e1", level="ERROR", message="connection timeout to db", ts=datetime.now(timezone.utc))
        fixes = await ErrorCausalityInsightGenerator(db).suggest_fixes_from_history("connection timeout")
        assert "Increase timeout duration" in fixes

    async def test_history_out_of_memory(self, db):
        _event(db, "e1", level="ERROR", message="out of memory error", ts=datetime.now(timezone.utc))
        fixes = await ErrorCausalityInsightGenerator(db).suggest_fixes_from_history("out of memory")
        assert "Increase available memory" in fixes

    async def test_history_permission(self, db):
        _event(db, "e1", level="ERROR", message="permission denied", ts=datetime.now(timezone.utc))
        fixes = await ErrorCausalityInsightGenerator(db).suggest_fixes_from_history("permission denied")
        assert "Check API credentials" in fixes

    async def test_history_unauthorized(self, db):
        _event(db, "e1", level="ERROR", message="unauthorized access", ts=datetime.now(timezone.utc))
        fixes = await ErrorCausalityInsightGenerator(db).suggest_fixes_from_history("unauthorized")
        assert "Check API credentials" in fixes

    async def test_history_not_found(self, db):
        _event(db, "e1", level="ERROR", message="resource not found", ts=datetime.now(timezone.utc))
        fixes = await ErrorCausalityInsightGenerator(db).suggest_fixes_from_history("not found")
        assert "Verify resource exists" in fixes

    async def test_history_rate_limit(self, db):
        _event(db, "e1", level="ERROR", message="rate limit exceeded", ts=datetime.now(timezone.utc))
        fixes = await ErrorCausalityInsightGenerator(db).suggest_fixes_from_history("rate limit")
        assert "Implement request throttling" in fixes

    async def test_history_generic(self, db):
        _event(db, "e1", level="ERROR", message="mystery failure", ts=datetime.now(timezone.utc))
        fixes = await ErrorCausalityInsightGenerator(db).suggest_fixes_from_history("mystery failure")
        assert "Review error logs for more details" in fixes

    async def test_history_outside_range_returns_empty(self, db):
        _event(db, "e1", level="ERROR", message="old error",
               ts=datetime.now(timezone.utc) - timedelta(days=90))
        fixes = await ErrorCausalityInsightGenerator(db).suggest_fixes_from_history("old error", "last_30d")
        assert fixes == []

    async def test_long_message_truncated(self, db):
        long_msg = "x" * 120
        _event(db, "e1", level="ERROR", message=long_msg, ts=datetime.now(timezone.utc))
        fixes = await ErrorCausalityInsightGenerator(db).suggest_fixes_from_history("x" * 120)
        assert fixes  # partial ilike match on 50-char prefix

    async def test_exception_returns_empty(self):
        gen = ErrorCausalityInsightGenerator(_BadSession())
        assert await gen.suggest_fixes_from_history("anything") == []


class TestAnalyzeErrorSeverityDistribution:
    async def test_no_errors_returns_none(self, db):
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.analyze_error_severity_distribution("agent") is None

    async def test_high_critical_rate(self, db):
        for i in range(3):
            _event(db, f"e{i}", level="ERROR", component_type="agent")
        for i in range(3):
            _event(db, f"c{i}", level="CRITICAL", component_type="agent")
        insight = await ErrorCausalityInsightGenerator(db).analyze_error_severity_distribution("agent")
        assert insight is not None
        assert insight.severity == "critical"
        assert insight.title == "High critical error rate for agent"
        assert insight.evidence["total_errors"] == 6
        assert insight.evidence["critical_errors"] == 3
        assert insight.evidence["critical_rate"] == 0.5
        assert insight.evidence["error_distribution"] == {"ERROR": 3, "CRITICAL": 3}
        assert insight.affected_components == [{"type": "agent"}]

    async def test_low_critical_rate_returns_none(self, db):
        for i in range(8):
            _event(db, f"e{i}", level="ERROR", component_type="agent")
        _event(db, "c1", level="CRITICAL", component_type="agent")
        assert await ErrorCausalityInsightGenerator(db).analyze_error_severity_distribution("agent") is None

    async def test_different_component_ignored(self, db):
        _event(db, "c1", level="CRITICAL", component_type="browser")
        assert await ErrorCausalityInsightGenerator(db).analyze_error_severity_distribution("agent") is None

    async def test_exception_returns_none(self):
        gen = ErrorCausalityInsightGenerator(_BadSession())
        assert await gen.analyze_error_severity_distribution("agent") is None


class TestErrorParseTimeRange:
    def test_all_branches(self, db):
        gen = ErrorCausalityInsightGenerator(db)
        now = datetime.now(timezone.utc)
        assert abs(now - gen._parse_time_range("last_1h") - timedelta(hours=1)).total_seconds() < 5
        assert abs(now - gen._parse_time_range("last_24h") - timedelta(hours=24)).total_seconds() < 5
        assert abs(now - gen._parse_time_range("last_7d") - timedelta(days=7)).total_seconds() < 5
        assert abs(now - gen._parse_time_range("last_30d") - timedelta(days=30)).total_seconds() < 5
        assert abs(now - gen._parse_time_range("bogus") - timedelta(hours=1)).total_seconds() < 5


# ============================================================================
# core/debug_insights/flow.py
# ============================================================================


class TestTraceOperationFlow:
    async def test_no_events_returns_none(self, db):
        gen = FlowInsightGenerator(db)
        assert await gen.trace_operation_flow("corr-empty") is None

    async def test_blocked_operation_warning(self, db):
        _event(db, "e1", correlation_id="corr-1", component_type="agent", component_id="a1", level="INFO",
               ts=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        _event(db, "e2", correlation_id="corr-1", component_type="browser", component_id="b1", level="INFO",
               ts=datetime(2026, 1, 1, 0, 1, 0, tzinfo=timezone.utc))
        insight = await FlowInsightGenerator(db).trace_operation_flow("corr-1")
        assert insight is not None
        assert insight.severity == "warning"
        assert insight.title == "Blocking operation detected"
        assert insight.evidence["blocking_component"] == "agent/a1"
        assert insight.evidence["block_duration_seconds"] == 60.0
        assert insight.evidence["event_count"] == 2
        assert insight.affected_components == [
            {"type": "agent", "id": "a1"},
            {"type": "browser", "id": "b1"},
        ]

    async def test_has_errors_critical(self, db):
        _event(db, "e1", correlation_id="corr-1", component_type="agent", component_id="a1", level="INFO",
               ts=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        _event(db, "e2", correlation_id="corr-1", component_type="browser", component_id="b1", level="ERROR",
               message="oops", ts=datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc))
        insight = await FlowInsightGenerator(db).trace_operation_flow("corr-1")
        assert insight.severity == "critical"
        assert insight.title == "Operation flow interrupted"
        assert insight.evidence["error_count"] == 1
        assert insight.evidence["error_messages"] == ["oops"]
        assert insight.evidence["components_touched"] == 2

    async def test_completed_info(self, db):
        _event(db, "e1", correlation_id="corr-1", component_type="agent", component_id="a1", level="INFO",
               ts=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        _event(db, "e2", correlation_id="corr-1", component_type="browser", component_id="b1", level="INFO",
               ts=datetime(2026, 1, 1, 0, 0, 5, tzinfo=timezone.utc))
        insight = await FlowInsightGenerator(db).trace_operation_flow("corr-1")
        assert insight.severity == "info"
        assert insight.title == "Operation flow completed"
        assert insight.evidence["duration_seconds"] == 5.0
        assert insight.evidence["components_touched"] == 2

    async def test_exception_returns_none(self):
        gen = FlowInsightGenerator(_BadSession())
        assert await gen.trace_operation_flow("corr-1") is None


class TestDetectBlockingOperations:
    async def test_none_returns_empty(self, db):
        gen = FlowInsightGenerator(db)
        assert await gen.detect_blocking_operations("agent", "a1") == []

    async def test_long_running_operation_detected(self, db):
        base = datetime.now(timezone.utc) - timedelta(minutes=30)
        _event(db, "e1", correlation_id="corr-1", component_type="agent", component_id="a1", level="INFO",
               ts=base)
        _event(db, "e2", correlation_id="corr-1", component_type="agent", component_id="a1", level="INFO",
               ts=base + timedelta(seconds=120))
        insights = await FlowInsightGenerator(db).detect_blocking_operations("agent", "a1")
        assert len(insights) == 1
        insight = insights[0]
        assert insight.title == "Long-running operation detected"
        assert insight.severity == "warning"
        assert insight.evidence["duration_seconds"] == 120.0
        assert insight.evidence["component_type"] == "agent"
        assert insight.affected_components == [{"type": "agent", "id": "a1"}]

    async def test_quick_operation_not_detected(self, db):
        _event(db, "e1", correlation_id="corr-1", component_type="agent", component_id="a1",
               ts=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        _event(db, "e2", correlation_id="corr-1", component_type="agent", component_id="a1",
               ts=datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc))
        assert await FlowInsightGenerator(db).detect_blocking_operations("agent", "a1") == []

    async def test_exception_returns_empty(self):
        gen = FlowInsightGenerator(_BadSession())
        assert await gen.detect_blocking_operations("agent", "a1") == []


class TestDetectDeadlocks:
    async def test_none_returns_empty(self, db):
        gen = FlowInsightGenerator(db)
        assert await gen.detect_deadlocks() == []

    async def test_stuck_operation_detected(self, db):
        base = datetime.now(timezone.utc) - timedelta(minutes=40)
        for i in range(11):
            _event(db, f"e{i}", correlation_id="corr-1", component_type="agent", component_id="a1",
                   level="WARNING", ts=base + timedelta(seconds=10 * i))
        insights = await FlowInsightGenerator(db).detect_deadlocks()
        assert len(insights) == 1
        insight = insights[0]
        assert insight.title == "Potential deadlock detected"
        assert insight.severity == "critical"
        assert insight.evidence["duration_seconds"] == 100.0
        assert insight.evidence["event_count"] == 11
        assert insight.evidence["duration_seconds"] == 100.0

    async def test_short_operation_not_detected(self, db):
        base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            _event(db, f"e{i}", correlation_id="corr-1", component_type="agent", component_id="a1",
                   ts=base + timedelta(seconds=2 * i))
        assert await FlowInsightGenerator(db).detect_deadlocks() == []

    async def test_exception_returns_empty(self):
        gen = FlowInsightGenerator(_BadSession())
        assert await gen.detect_deadlocks() == []


class TestAnalyzeWorkflowPatterns:
    async def test_none_returns_empty(self, db):
        gen = FlowInsightGenerator(db)
        assert await gen.analyze_workflow_patterns() == []

    async def test_high_failure_rate_detected(self, db):
        for i in range(7):
            _event(db, f"ok{i}", component_type="workflow", component_id="wf-1", level="INFO",
                   correlation_id=f"corr-{i}")
        for i in range(4):
            _event(db, f"err{i}", component_type="workflow", component_id="wf-1", level="ERROR",
                   correlation_id=f"corr-e{i}")
        insights = await FlowInsightGenerator(db).analyze_workflow_patterns()
        assert len(insights) == 1
        insight = insights[0]
        assert insight.title == "High failure rate for workflow wf-1"
        assert insight.severity == "critical"
        assert insight.evidence["total_executions"] == 11
        assert insight.evidence["failed_executions"] == 4
        assert insight.evidence["error_rate"] == 4 / 11
        assert insight.affected_components == [{"type": "workflow", "id": "wf-1"}]

    async def test_low_failure_rate_no_insight(self, db):
        for i in range(10):
            _event(db, f"ok{i}", component_type="workflow", component_id="wf-1", level="INFO",
                   correlation_id=f"corr-{i}")
        _event(db, "err1", component_type="workflow", component_id="wf-1", level="ERROR",
               correlation_id="corr-e1")
        assert await FlowInsightGenerator(db).analyze_workflow_patterns() == []

    async def test_exception_returns_empty(self):
        gen = FlowInsightGenerator(_BadSession())
        assert await gen.analyze_workflow_patterns() == []


class TestAnalyzeFlowInternal:
    async def test_empty_events(self, db):
        gen = FlowInsightGenerator(db)
        analysis = await gen._analyze_flow([])
        assert analysis["blocked"] is False
        assert analysis["has_errors"] is False
        assert analysis["components_touched"] == 0

    async def test_no_timestamps(self, db):
        gen = FlowInsightGenerator(db)
        e1 = _event(db, "e1", component_type="agent", component_id="a1", ts=None)
        e2 = _event(db, "e2", component_type="browser", component_id="b1", ts=None)
        e1.timestamp = None
        e2.timestamp = None
        db.commit()
        analysis = await gen._analyze_flow([e1, e2])
        assert analysis["duration"] == 0
        assert analysis["blocked"] is False
        assert analysis["components_touched"] == 2

    async def test_errors_and_duration(self, db):
        gen = FlowInsightGenerator(db)
        e1 = _event(db, "e1", component_type="agent", component_id="a1", level="INFO",
                    ts=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        e2 = _event(db, "e2", component_type="browser", component_id="b1", level="ERROR",
                    message=None, ts=datetime(2026, 1, 1, 0, 0, 3, tzinfo=timezone.utc))
        analysis = await gen._analyze_flow([e1, e2])
        assert analysis["has_errors"] is True
        assert analysis["error_count"] == 1
        assert analysis["error_messages"] == []  # None message filtered
        assert analysis["duration"] == 3.0

    async def test_gap_under_threshold(self, db):
        gen = FlowInsightGenerator(db)
        e1 = _event(db, "e1", component_type="agent", component_id="a1",
                    ts=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        e2 = _event(db, "e2", component_type="browser", component_id="b1",
                    ts=datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc))
        analysis = await gen._analyze_flow([e1, e2])
        assert analysis["blocked"] is False

    async def test_partial_missing_timestamps_in_gap_loop(self, db):
        gen = FlowInsightGenerator(db)
        e1 = _event(db, "e1", component_type="agent", component_id="a1", ts=None)
        e1.timestamp = None
        db.commit()
        e2 = _event(db, "e2", component_type="browser", component_id="b1",
                    ts=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        analysis = await gen._analyze_flow([e1, e2])
        assert analysis["blocked"] is False


class TestFlowParseTimeRange:
    def test_all_branches(self, db):
        gen = FlowInsightGenerator(db)
        now = datetime.now(timezone.utc)
        assert abs(now - gen._parse_time_range("last_1h") - timedelta(hours=1)).total_seconds() < 5
        assert abs(now - gen._parse_time_range("last_24h") - timedelta(hours=24)).total_seconds() < 5
        assert abs(now - gen._parse_time_range("last_7d") - timedelta(days=7)).total_seconds() < 5
        assert abs(now - gen._parse_time_range("bogus") - timedelta(hours=1)).total_seconds() < 5
