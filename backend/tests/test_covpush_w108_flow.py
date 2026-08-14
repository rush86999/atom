# -*- coding: utf-8 -*-
"""Coverage wave 108 — core/debug_insights/flow (in-memory SQLite, zero LLM spend).

- FlowInsightGenerator.trace_operation_flow: no events, blocked operation
  (30s gap), interrupted flow (errors), successful flow, exception -> None.
  NOTE: the interrupted-flow branch previously raised AttributeError
  (DebugInsightSeverity.ERROR does not exist) and always fell to except.
- detect_blocking_operations: no slow ops, slow op (>60s spread via
  julianday), exception -> [].
- detect_deadlocks: no stuck ops, stuck op (>86s spread + >10 events),
  exception -> [].
- analyze_workflow_patterns: none, high failure rate, low failure rate,
  exception -> [].
- _analyze_flow: empty events, timestampless events, single event, gap
  blocking, error collection.
- _parse_time_range: all 4 branches.
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
)
from core.debug_insights.flow import FlowInsightGenerator


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _event(db, eid, *, correlation_id="corr-1", component_type="agent",
           component_id="agent-1", level="INFO", message="msg", ts=None):
    event = DebugEvent(
        id=eid,
        event_type="log",
        component_type=component_type,
        component_id=component_id,
        correlation_id=correlation_id,
        level=level,
        message=message,
        timestamp=ts if ts is not None else datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    return event


class _BadSession:
    def query(self, model):
        raise RuntimeError("db down")

    def add(self, obj):
        raise RuntimeError("db down")


# ============================================================================
# trace_operation_flow
# ============================================================================

class TestTraceOperationFlow:
    async def test_no_events_returns_none(self, db):
        gen = FlowInsightGenerator(db)
        assert await gen.trace_operation_flow("corr-nope") is None

    async def test_blocked_operation(self, db):
        base = datetime.now(timezone.utc)
        _event(db, "b1", correlation_id="corr-b", ts=base)
        _event(db, "b2", correlation_id="corr-b", ts=base + timedelta(seconds=45))
        gen = FlowInsightGenerator(db)
        insight = await gen.trace_operation_flow("corr-b")
        assert insight is not None
        assert insight.severity == "warning"
        assert insight.title == "Blocking operation detected"
        assert insight.evidence["block_duration_seconds"] == 45
        assert insight.evidence["blocking_component"] == "agent/agent-1"
        assert insight.evidence["event_count"] == 2
        assert insight.confidence_score == 0.88

    async def test_interrupted_flow(self, db):
        base = datetime.now(timezone.utc)
        _event(db, "e1", correlation_id="corr-e", ts=base)
        _event(db, "e2", correlation_id="corr-e", level="ERROR", message="boom",
               ts=base + timedelta(seconds=1))
        gen = FlowInsightGenerator(db)
        insight = await gen.trace_operation_flow("corr-e")
        assert insight is not None
        assert insight.severity == "critical"
        assert insight.title == "Operation flow interrupted"
        assert insight.evidence["error_count"] == 1
        assert insight.evidence["error_messages"] == ["boom"]
        assert insight.evidence["components_touched"] == 1
        assert insight.confidence_score == 0.92

    async def test_successful_flow(self, db):
        base = datetime.now(timezone.utc)
        _event(db, "s1", correlation_id="corr-s", ts=base)
        _event(db, "s2", correlation_id="corr-s", ts=base + timedelta(seconds=2))
        gen = FlowInsightGenerator(db)
        insight = await gen.trace_operation_flow("corr-s")
        assert insight is not None
        assert insight.severity == "info"
        assert insight.title == "Operation flow completed"
        assert insight.evidence["duration_seconds"] == 2
        assert insight.evidence["components_touched"] == 1
        assert insight.confidence_score == 0.95

    async def test_multiple_components_touched(self, db):
        base = datetime.now(timezone.utc)
        _event(db, "m1", correlation_id="corr-m", component_type="agent", ts=base)
        _event(db, "m2", correlation_id="corr-m", component_type="browser",
               ts=base + timedelta(seconds=1))
        gen = FlowInsightGenerator(db)
        insight = await gen.trace_operation_flow("corr-m")
        assert insight.evidence["components_touched"] == 2
        assert len(insight.affected_components) == 2

    async def test_exception_returns_none(self):
        gen = FlowInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.trace_operation_flow("corr-x") is None


# ============================================================================
# detect_blocking_operations
# ============================================================================

class TestDetectBlockingOperations:
    async def test_no_slow_operations(self, db):
        _event(db, "n1", correlation_id="corr-n", component_type="agent",
               component_id="a-1")
        gen = FlowInsightGenerator(db)
        assert await gen.detect_blocking_operations("agent", "a-1") == []

    async def test_slow_operation_detected(self, db):
        base = datetime.now(timezone.utc)
        _event(db, "o1", correlation_id="corr-o", component_type="agent",
               component_id="a-1", ts=base)
        _event(db, "o2", correlation_id="corr-o", component_type="agent",
               component_id="a-1", ts=base + timedelta(seconds=90))
        gen = FlowInsightGenerator(db)
        insights = await gen.detect_blocking_operations("agent", "a-1")
        assert len(insights) == 1
        insight = insights[0]
        assert insight.severity == "warning"
        assert insight.title == "Long-running operation detected"
        assert insight.evidence["duration_seconds"] == 90
        assert insight.evidence["correlation_id"] == "corr-o"
        assert insight.affected_components == [{"type": "agent", "id": "a-1"}]
        assert insight.confidence_score == 0.85

    async def test_fast_operation_skipped(self, db):
        base = datetime.now(timezone.utc)
        _event(db, "f1", correlation_id="corr-f", component_type="agent",
               component_id="a-1", ts=base)
        _event(db, "f2", correlation_id="corr-f", component_type="agent",
               component_id="a-1", ts=base + timedelta(seconds=5))
        gen = FlowInsightGenerator(db)
        assert await gen.detect_blocking_operations("agent", "a-1") == []

    async def test_other_component_ignored(self, db):
        base = datetime.now(timezone.utc)
        _event(db, "x1", correlation_id="corr-x", component_type="agent",
               component_id="a-1", ts=base)
        _event(db, "x2", correlation_id="corr-x", component_type="agent",
               component_id="a-1", ts=base + timedelta(seconds=90))
        gen = FlowInsightGenerator(db)
        assert await gen.detect_blocking_operations("browser", "b-1") == []

    async def test_exception_returns_empty(self):
        gen = FlowInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.detect_blocking_operations("agent", "a-1") == []


# ============================================================================
# detect_deadlocks
# ============================================================================

class TestDetectDeadlocks:
    async def test_no_stuck_operations(self, db):
        _event(db, "d1", correlation_id="corr-d", component_type="agent")
        gen = FlowInsightGenerator(db)
        assert await gen.detect_deadlocks() == []

    async def test_deadlock_detected(self, db):
        base = datetime.now(timezone.utc)
        for i in range(12):
            _event(db, f"st{i}", correlation_id="corr-st",
                   ts=base + timedelta(seconds=10 * i))
        gen = FlowInsightGenerator(db)
        insights = await gen.detect_deadlocks()
        assert len(insights) == 1
        insight = insights[0]
        assert insight.severity == "critical"
        assert insight.title == "Potential deadlock detected"
        assert insight.evidence["correlation_id"] == "corr-st"
        assert insight.evidence["event_count"] == 12
        assert insight.evidence["duration_seconds"] == 110
        assert insight.evidence["first_seen"] is not None
        assert insight.evidence["last_seen"] is not None
        assert insight.affected_components == []
        assert insight.confidence_score == 0.75

    async def test_few_events_skipped(self, db):
        base = datetime.now(timezone.utc)
        for i in range(5):
            _event(db, f"few{i}", correlation_id="corr-few",
                   ts=base + timedelta(seconds=30 * i))
        gen = FlowInsightGenerator(db)
        assert await gen.detect_deadlocks() == []

    async def test_exception_returns_empty(self):
        gen = FlowInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.detect_deadlocks() == []


# ============================================================================
# analyze_workflow_patterns
# ============================================================================

class TestAnalyzeWorkflowPatterns:
    async def test_no_workflows(self, db):
        _event(db, "w1", component_type="agent")
        gen = FlowInsightGenerator(db)
        assert await gen.analyze_workflow_patterns() == []

    async def test_high_failure_rate(self, db):
        base = datetime.now(timezone.utc)
        for i in range(8):
            _event(db, f"wf-ok{i}", correlation_id="corr-wf", component_type="workflow",
                   component_id="wf-1", level="INFO", ts=base + timedelta(seconds=i))
        for i in range(4):
            _event(db, f"wf-err{i}", correlation_id="corr-wf", component_type="workflow",
                   component_id="wf-1", level="ERROR", message="fail",
                   ts=base + timedelta(seconds=100 + i))
        gen = FlowInsightGenerator(db)
        insights = await gen.analyze_workflow_patterns("last_24h")
        assert len(insights) == 1
        insight = insights[0]
        assert insight.severity == "critical"
        assert insight.title == "High failure rate for workflow wf-1"
        assert insight.evidence["total_executions"] == 12
        assert insight.evidence["failed_executions"] == 4
        assert insight.evidence["error_rate"] == 4 / 12
        assert insight.affected_components == [{"type": "workflow", "id": "wf-1"}]
        assert insight.confidence_score == 0.90

    async def test_low_failure_rate_no_insight(self, db):
        base = datetime.now(timezone.utc)
        for i in range(11):
            _event(db, f"wf-ok2-{i}", correlation_id="corr-wf2",
                   component_type="workflow", component_id="wf-2", level="INFO",
                   ts=base + timedelta(seconds=i))
        _event(db, "wf-err2", correlation_id="corr-wf2", component_type="workflow",
               component_id="wf-2", level="ERROR", message="fail",
               ts=base + timedelta(seconds=100))
        gen = FlowInsightGenerator(db)
        assert await gen.analyze_workflow_patterns("last_24h") == []

    async def test_few_executions_no_insight(self, db):
        _event(db, "wf3", component_type="workflow", component_id="wf-3",
               level="ERROR")
        _event(db, "wf4", component_type="workflow", component_id="wf-3",
               level="ERROR")
        gen = FlowInsightGenerator(db)
        assert await gen.analyze_workflow_patterns("last_24h") == []

    async def test_exception_returns_empty(self):
        gen = FlowInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.analyze_workflow_patterns() == []


# ============================================================================
# _analyze_flow
# ============================================================================

class TestAnalyzeFlow:
    async def test_empty_events(self, db):
        gen = FlowInsightGenerator(db)
        analysis = await gen._analyze_flow([])
        assert analysis["blocked"] is False
        assert analysis["has_errors"] is False
        assert analysis["components_touched"] == 0
        assert analysis["duration"] == 0

    async def test_timestampless_events(self, db):
        e1 = DebugEvent(id="t1", event_type="log", component_type="agent",
                        component_id="a-1", correlation_id="c", level="INFO",
                        timestamp=None)
        e2 = DebugEvent(id="t2", event_type="log", component_type="agent",
                        component_id="a-1", correlation_id="c", level="INFO",
                        timestamp=None)
        gen = FlowInsightGenerator(db)
        analysis = await gen._analyze_flow([e1, e2])
        assert analysis["duration"] == 0
        assert analysis["blocked"] is False

    async def test_single_event(self, db):
        _event(db, "s1")
        gen = FlowInsightGenerator(db)
        analysis = await gen._analyze_flow(db.query(DebugEvent).all())
        assert analysis["duration"] == 0
        assert analysis["blocked"] is False

    async def test_blocking_gap(self, db):
        base = datetime.now(timezone.utc)
        e1 = DebugEvent(id="g1", event_type="log", component_type="agent",
                        component_id="a-1", correlation_id="c", level="INFO",
                        timestamp=base)
        e2 = DebugEvent(id="g2", event_type="log", component_type="agent",
                        component_id="a-1", correlation_id="c", level="INFO",
                        timestamp=base + timedelta(seconds=60))
        gen = FlowInsightGenerator(db)
        analysis = await gen._analyze_flow([e1, e2])
        assert analysis["blocked"] is True
        assert analysis["block_duration"] == 60
        assert analysis["blocking_component"] == "agent/a-1"

    async def test_error_messages_collected(self, db):
        base = datetime.now(timezone.utc)
        e1 = DebugEvent(id="x1", event_type="log", component_type="agent",
                        component_id="a-1", correlation_id="c", level="ERROR",
                        message="boom", timestamp=base)
        e2 = DebugEvent(id="x2", event_type="log", component_type="agent",
                        component_id="a-1", correlation_id="c", level="CRITICAL",
                        message="", timestamp=base + timedelta(seconds=1))
        gen = FlowInsightGenerator(db)
        analysis = await gen._analyze_flow([e1, e2])
        assert analysis["has_errors"] is True
        assert analysis["error_count"] == 2
        assert analysis["error_messages"] == ["boom"]


# ============================================================================
# _parse_time_range
# ============================================================================

class TestParseTimeRange:
    def test_all_branches(self, db):
        gen = FlowInsightGenerator(db)
        now = datetime.now(timezone.utc)
        for label, delta in [
            ("last_1h", timedelta(hours=1)),
            ("last_24h", timedelta(hours=24)),
            ("last_7d", timedelta(days=7)),
            ("bogus", timedelta(hours=1)),
        ]:
            cutoff = gen._parse_time_range(label)
            assert abs((now - delta - cutoff).total_seconds()) < 5, label
