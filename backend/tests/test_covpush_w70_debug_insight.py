# -*- coding: utf-8 -*-
"""Coverage wave 70 — core/debug_insight_engine (in-memory SQLite, zero LLM spend).

- DebugInsightEngine: generate_insights_from_events (no-events, full pipeline
  with all 5 generators, confidence-threshold storage filter, exception),
  analyze_state_consistency (no snapshots, missing components, inconsistent,
  consistent, exception — operation_id column restored, BUG-FIX W70-1),
  _generate_consistency_insights (±snapshot data, exception), _generate_flow_insights
  (±errors, exception), _generate_error_insights (none/repeated warning/critical,
  exception), _generate_performance_insights (±slow ops, exception),
  _generate_anomaly_insights (spike/no-spike/single-minute, exception),
  _query_events (filters + time range + exception), _parse_time_range (all 5).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (  # noqa: F401 (register models)
    DebugEvent,
    DebugInsight,
    DebugMetric,
    DebugStateSnapshot,
)
from core.debug_insight_engine import DebugInsightEngine
import core.debug_insight_engine as mod


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _event(db, eid, *, correlation_id="corr-1", component_type="agent",
           component_id="agent-1", level="INFO", message="msg",
           data=None, event_type="log", ts=None):
    event = DebugEvent(
        id=eid,
        event_type=event_type,
        component_type=component_type,
        component_id=component_id,
        correlation_id=correlation_id,
        level=level,
        message=message,
        data=data or {},
        timestamp=ts if ts is not None else datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    return event


def _snapshot(db, sid, *, operation_id="op-1", component_id="node-1",
              state_data=None, captured_at=None):
    snap = DebugStateSnapshot(
        id=sid,
        component_type="agent",
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
# generate_insights_from_events
# ============================================================================

class TestGenerateInsights:
    async def test_no_events_returns_empty(self, db):
        engine = DebugInsightEngine(db)
        assert await engine.generate_insights_from_events(correlation_id="nope") == []

    async def test_full_pipeline_generates_and_stores(self, db):
        engine = DebugInsightEngine(db)
        # anomaly: volume spike (5 bg events share +5m; 1 each at +0..+4m;
        # 10 at +6m → 7 minutes, avg 3.0, spike threshold 9.0 → 10 spikes)
        base = datetime.now(timezone.utc)
        _event(db, "e-snap", event_type="state_snapshot", data={"step": 1},
               ts=base + timedelta(minutes=5))
        _event(db, "e-flow", level="ERROR", message="flow broke", data={"step": 2},
               ts=base + timedelta(minutes=5))
        _event(db, "e-err1", level="ERROR", message="same failure",
               ts=base + timedelta(minutes=5))
        _event(db, "e-err2", level="ERROR", message="same failure",
               ts=base + timedelta(minutes=5))
        _event(db, "e-slow", level="INFO", data={"duration_ms": 9000},
               ts=base + timedelta(minutes=5))
        for i in range(5):
            _event(db, f"e-vol-a{i}", ts=base + timedelta(minutes=i))
        for i in range(10):
            _event(db, f"e-vol-b{i}", ts=base + timedelta(minutes=6))

        insights = await engine.generate_insights_from_events()
        kinds = {i.insight_type for i in insights}
        assert kinds == {"consistency", "flow", "error", "performance", "anomaly"}
        assert db.query(DebugInsight).count() == len(insights)

    async def test_confidence_threshold_blocks_persistence(self, db):
        engine = DebugInsightEngine(db)
        _event(db, "e-err1", level="ERROR", message="same failure")
        _event(db, "e-err2", level="ERROR", message="same failure")
        with patch.object(mod, "DEBUG_INSIGHT_CONFIDENCE_THRESHOLD", 1.0):
            insights = await engine.generate_insights_from_events()
        # error-pattern + flow insights are generated but none persist
        assert len(insights) == 2
        assert db.query(DebugInsight).count() == 0

    async def test_exception_returns_empty(self, db):
        engine = DebugInsightEngine(db)
        _event(db, "e-err1", level="ERROR", message="same failure")
        _event(db, "e-err2", level="ERROR", message="same failure")
        with patch.object(engine.db, "add", side_effect=RuntimeError("db down")):
            with patch.object(engine.logger, "error"):
                assert await engine.generate_insights_from_events() == []


# ============================================================================
# analyze_state_consistency
# ============================================================================

class TestAnalyzeStateConsistency:
    async def test_no_snapshots_returns_none(self, db):
        engine = DebugInsightEngine(db)
        assert await engine.analyze_state_consistency("op-nope", ["node-1"]) is None

    async def test_missing_components_warning(self, db):
        _snapshot(db, "s1", operation_id="op-2", component_id="node-1")
        engine = DebugInsightEngine(db)
        insight = await engine.analyze_state_consistency(
            "op-2", ["node-1", "node-2"], component_type="agent")
        assert insight is not None
        assert insight.severity == "warning"
        assert "Incomplete state coverage" in insight.title
        assert insight.evidence["missing_components"] == ["node-2"]
        assert insight.confidence_score == 0.95

    async def test_inconsistent_state_warning(self, db):
        _snapshot(db, "s1", operation_id="op-3", component_id="node-1", state_data={"x": 1, "y": 1})
        _snapshot(db, "s2", operation_id="op-3", component_id="node-2", state_data={"x": 2, "y": 1})
        engine = DebugInsightEngine(db)
        insight = await engine.analyze_state_consistency("op-3", ["node-1", "node-2"])
        assert insight is not None
        assert "State inconsistency detected" in insight.title
        assert insight.evidence["inconsistencies"][0]["key"] == "x"
        assert insight.confidence_score == 0.90

    async def test_consistent_state_info(self, db):
        _snapshot(db, "s1", operation_id="op-4", component_id="node-1", state_data={"x": 1})
        _snapshot(db, "s2", operation_id="op-4", component_id="node-2", state_data={"x": 1})
        engine = DebugInsightEngine(db)
        insight = await engine.analyze_state_consistency("op-4", ["node-1", "node-2"])
        assert insight is not None
        assert "consistent" in insight.title.lower()
        assert insight.severity == "info"
        assert insight.confidence_score == 1.0

    async def test_exception_returns_none(self):
        engine = DebugInsightEngine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine.analyze_state_consistency("op-x", ["node-1"]) is None


# ============================================================================
# Individual generators
# ============================================================================

class TestConsistencyInsights:
    async def test_state_snapshot_event_with_data(self, db):
        _event(db, "e-1", event_type="state_snapshot", data={"step": 1}, ts=None)
        insights = await DebugInsightEngine(db)._generate_consistency_insights(
            db.query(DebugEvent).all())
        assert len(insights) == 1
        assert insights[0].insight_type == "consistency"
        assert insights[0].severity == "info"
        assert insights[0].evidence == {"snapshot_id": "e-1"}

    async def test_state_snapshot_event_without_data(self, db):
        _event(db, "e-2", event_type="state_snapshot", data={})
        insights = await DebugInsightEngine(db)._generate_consistency_insights(
            db.query(DebugEvent).all())
        assert insights == []

    async def test_non_snapshot_events(self, db):
        _event(db, "e-3", event_type="log")
        insights = await DebugInsightEngine(db)._generate_consistency_insights(
            db.query(DebugEvent).all())
        assert insights == []

    async def test_exception(self):
        engine = DebugInsightEngine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine._generate_consistency_insights(
                [_BoomEvent()]) == []


def _event_like(eid, **kwargs):
    fields = dict(id=eid, event_type="log", component_type="agent",
                  component_id="agent-1", correlation_id="corr-1", data={})
    ts = kwargs.pop("ts", None)
    if ts is not None:
        fields["timestamp"] = ts
    fields.update(kwargs)
    return DebugEvent(**fields)


class _BoomEvent:
    """Event whose attribute access raises — forces the generators' excepts."""

    @property
    def correlation_id(self):
        raise RuntimeError("boom")


class TestFlowInsights:
    async def test_error_events_generate_flow_insight(self, db):
        _event(db, "f1", level="ERROR", message="failed step", data={"step": 1})
        insights = await DebugInsightEngine(db)._generate_flow_insights(
            db.query(DebugEvent).all())
        assert len(insights) == 1
        assert insights[0].insight_type == "flow"
        assert insights[0].severity == "warning"
        assert insights[0].evidence["error_count"] == 1
        assert insights[0].evidence["error_messages"] == ["failed step"]

    async def test_no_error_events(self, db):
        _event(db, "f2", level="INFO")
        insights = await DebugInsightEngine(db)._generate_flow_insights(
            db.query(DebugEvent).all())
        assert insights == []

    async def test_exception(self):
        engine = DebugInsightEngine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine._generate_flow_insights([_BoomEvent()]) == []


class TestErrorInsights:
    async def test_no_error_events(self, db):
        _event(db, "g1", level="INFO")
        assert await DebugInsightEngine(db)._generate_error_insights(
            db.query(DebugEvent).all()) == []

    async def test_repeated_pattern_warning(self, db):
        _event(db, "g2", level="ERROR", message="boom")
        _event(db, "g3", level="ERROR", message="boom")
        insights = await DebugInsightEngine(db)._generate_error_insights(
            db.query(DebugEvent).all())
        assert len(insights) == 1
        assert insights[0].severity == "warning"
        assert insights[0].insight_type == "error"
        assert "2 times" in insights[0].summary

    async def test_repeated_pattern_critical(self, db):
        _event(db, "g4", level="ERROR", message="crash")
        _event(db, "g5", level="CRITICAL", message="crash")
        insights = await DebugInsightEngine(db)._generate_error_insights(
            db.query(DebugEvent).all())
        assert insights[0].severity == "critical"

    async def test_single_error_no_pattern(self, db):
        _event(db, "g6", level="ERROR", message="once")
        assert await DebugInsightEngine(db)._generate_error_insights(
            db.query(DebugEvent).all()) == []

    async def test_exception(self):
        engine = DebugInsightEngine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine._generate_error_insights(
                [_event_like("e", level="ERROR"), _event_like("e2", level="ERROR")]) == []


class TestPerformanceInsights:
    async def test_slow_operations(self, db):
        _event(db, "p1", data={"duration_ms": 6000}, message="query")
        _event(db, "p2", data={"duration_ms": 1000}, message="fast")
        insights = await DebugInsightEngine(db)._generate_performance_insights(
            db.query(DebugEvent).all())
        assert len(insights) == 1
        assert insights[0].insight_type == "performance"
        assert insights[0].severity == "warning"
        assert insights[0].evidence["slow_operations"][0]["duration_ms"] == 6000

    async def test_no_slow_operations(self, db):
        _event(db, "p3", data={"duration_ms": 10})
        assert await DebugInsightEngine(db)._generate_performance_insights(
            db.query(DebugEvent).all()) == []

    async def test_no_duration_data(self, db):
        _event(db, "p4", data={})
        assert await DebugInsightEngine(db)._generate_performance_insights(
            db.query(DebugEvent).all()) == []

    async def test_exception(self):
        engine = DebugInsightEngine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine._generate_performance_insights([_BoomEvent()]) == []


class TestAnomalyInsights:
    async def test_volume_spike(self, db):
        base = datetime.now(timezone.utc)
        for i in range(3):
            _event(db, f"a1-{i}", ts=base + timedelta(minutes=i))
        for i in range(10):
            _event(db, f"a2-{i}", ts=base + timedelta(minutes=4))
        insights = await DebugInsightEngine(db)._generate_anomaly_insights(
            db.query(DebugEvent).all())
        assert len(insights) == 1
        assert insights[0].insight_type == "anomaly"
        assert insights[0].severity == "warning"
        assert insights[0].evidence["average_per_minute"] > 0
        assert insights[0].evidence["spikes"][0]["count"] == 10

    async def test_no_spike(self, db):
        base = datetime.now(timezone.utc)
        for i in range(3):
            _event(db, f"n1-{i}", ts=base)
        for i in range(4):
            _event(db, f"n2-{i}", ts=base + timedelta(minutes=1))
        insights = await DebugInsightEngine(db)._generate_anomaly_insights(
            db.query(DebugEvent).all())
        assert insights == []

    async def test_single_minute_no_analysis(self, db):
        for i in range(5):
            _event(db, f"s{i}", ts=datetime.now(timezone.utc))
        insights = await DebugInsightEngine(db)._generate_anomaly_insights(
            db.query(DebugEvent).all())
        assert insights == []

    async def test_timestampless_events_skipped(self, db):
        _event(db, "t1", ts=datetime.now(timezone.utc))
        _event(db, "t2", ts=datetime.now(timezone.utc) + timedelta(minutes=1))
        insights = await DebugInsightEngine(db)._generate_anomaly_insights(
            db.query(DebugEvent).all())
        assert insights == []  # 2 minutes, 1 event each → no spike

    async def test_exception(self):
        engine = DebugInsightEngine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine._generate_anomaly_insights([_BoomEvent()]) == []


# ============================================================================
# Query helpers
# ============================================================================

class TestQueryEvents:
    async def test_filters(self, db):
        _event(db, "q1", correlation_id="c-a", component_type="agent", component_id="a-1")
        _event(db, "q2", correlation_id="c-b", component_type="browser", component_id="b-1")
        _event(db, "q3", correlation_id="c-c", component_type="workflow", component_id="w-1",
               ts=datetime.now(timezone.utc) - timedelta(hours=3))
        engine = DebugInsightEngine(db)
        assert len(await engine._query_events(correlation_id="c-a")) == 1
        assert len(await engine._query_events(component_type="agent")) == 1
        assert len(await engine._query_events(component_id="b-1")) == 1
        assert len(await engine._query_events(time_range="last_1h")) == 2
        assert len(await engine._query_events()) == 3

    async def test_bad_time_range_ignored(self, db):
        _event(db, "q4", ts=datetime.now(timezone.utc) - timedelta(days=40))
        engine = DebugInsightEngine(db)
        assert len(await engine._query_events(time_range="bogus")) == 1

    async def test_exception(self):
        engine = DebugInsightEngine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine._query_events() == []


class TestParseTimeRange:
    def test_all_branches(self, db):
        engine = DebugInsightEngine(db)
        now = datetime.now(timezone.utc)
        for label, delta in [
            ("last_1h", timedelta(hours=1)),
            ("last_24h", timedelta(hours=24)),
            ("last_7d", timedelta(days=7)),
            ("last_30d", timedelta(days=30)),
        ]:
            cutoff = engine._parse_time_range(label)
            assert abs((now - delta - cutoff).total_seconds()) < 5, label
        assert engine._parse_time_range("bogus") is None
