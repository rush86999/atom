# -*- coding: utf-8 -*-
"""Coverage wave 108 — core/debug_insights/error_causality (in-memory SQLite, zero LLM spend).

- ErrorCausalityInsightGenerator.analyze_error_chain: missing event, non-error
  level, single-event chain (INFO fallback), multi-event root-cause chain,
  propagation path, cycle protection, exception -> None.
- track_error_propagation: no events, no error events, propagation order stops
  at first error, exception -> None.
- detect_error_patterns: no patterns, >=5 occurrence pattern with frequency,
  first/last seen isoformat, exception -> [].
- suggest_fixes_from_history: no history, all 6 heuristic keyword branches,
  exception -> [].
- analyze_error_severity_distribution: no errors, high critical rate, low
  critical rate, exception -> None.
- _parse_time_range: all 5 branches.
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
from core.debug_insights.error_causality import ErrorCausalityInsightGenerator


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


class _BadSession:
    def query(self, model):
        raise RuntimeError("db down")

    def add(self, obj):
        raise RuntimeError("db down")


# ============================================================================
# analyze_error_chain
# ============================================================================

class TestAnalyzeErrorChain:
    async def test_missing_event_returns_none(self, db):
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.analyze_error_chain("does-not-exist") is None

    async def test_non_error_level_returns_none(self, db):
        _event(db, "e1", level="WARNING")
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.analyze_error_chain("e1") is None

    async def test_single_event_returns_info_insight(self, db):
        _event(db, "e1", level="ERROR", message="boom", component_type="agent",
               component_id="a-1")
        gen = ErrorCausalityInsightGenerator(db)
        insight = await gen.analyze_error_chain("e1")
        assert insight is not None
        assert insight.insight_type == "error"
        assert insight.severity == "info"
        assert insight.evidence["chain_length"] == 1
        assert insight.evidence["error_id"] == "e1"
        assert insight.confidence_score == 0.70
        assert "Review error message" in insight.suggestions
        assert insight.affected_components == [{"type": "agent", "id": "a-1"}]

    async def test_single_event_no_message(self, db):
        _event(db, "e2", level="CRITICAL", message=None)
        gen = ErrorCausalityInsightGenerator(db)
        insight = await gen.analyze_error_chain("e2")
        assert insight is not None
        assert insight.summary == "No message"

    async def test_chain_root_cause(self, db):
        _event(db, "root", level="ERROR", message="db pool exhausted",
               component_type="database", component_id="db-1")
        _event(db, "mid", level="ERROR", message="query failed",
               component_type="service", component_id="svc-1",
               parent_event_id="root")
        _event(db, "err", level="ERROR", message="request failed",
               component_type="agent", component_id="a-1",
               parent_event_id="mid")
        gen = ErrorCausalityInsightGenerator(db)
        insight = await gen.analyze_error_chain("err")
        assert insight is not None
        assert insight.severity == "critical"
        assert insight.evidence["chain_length"] == 3
        assert insight.evidence["root_cause"]["event_id"] == "root"
        assert insight.evidence["root_cause"]["message"] == "db pool exhausted"
        assert "db-1" in insight.description
        assert "database/db-1" in insight.description
        assert insight.evidence["propagation_chain"][0]["level"] == "ERROR"
        assert len(insight.affected_components) == 3
        assert insight.confidence_score == 0.85

    async def test_chain_root_cause_no_message(self, db):
        _event(db, "root2", level="ERROR", message=None, component_type="db",
               component_id="db-1")
        _event(db, "err2", level="ERROR", message="x",
               component_id="a-1", parent_event_id="root2")
        gen = ErrorCausalityInsightGenerator(db)
        insight = await gen.analyze_error_chain("err2")
        assert insight is not None
        assert insight.evidence["root_cause"]["message"] is None
        assert "Root cause: Unknown" in insight.description

    async def test_cycle_terminates(self, db):
        _event(db, "c1", level="ERROR", message="loop", parent_event_id="c2")
        _event(db, "c2", level="ERROR", message="loop", parent_event_id="c1")
        gen = ErrorCausalityInsightGenerator(db)
        insight = await gen.analyze_error_chain("c1")
        assert insight is not None
        assert insight.evidence["chain_length"] == 2

    async def test_exception_returns_none(self):
        gen = ErrorCausalityInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.analyze_error_chain("x") is None


# ============================================================================
# track_error_propagation
# ============================================================================

class TestTrackErrorPropagation:
    async def test_no_events_returns_none(self, db):
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.track_error_propagation("corr-nope") is None

    async def test_no_error_events_returns_none(self, db):
        _event(db, "p1", level="INFO")
        _event(db, "p2", level="WARNING")
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.track_error_propagation("corr-1") is None

    async def test_propagation_stops_at_first_error(self, db):
        base = datetime.now(timezone.utc)
        _event(db, "p1", correlation_id="corr-p", component_type="agent",
               component_id="a-1", level="INFO", ts=base)
        _event(db, "p2", correlation_id="corr-p", component_type="service",
               component_id="s-1", level="ERROR", message="fail", ts=base + timedelta(seconds=1))
        _event(db, "p3", correlation_id="corr-p", component_type="browser",
               component_id="b-1", level="CRITICAL", message="later", ts=base + timedelta(seconds=2))
        gen = ErrorCausalityInsightGenerator(db)
        insight = await gen.track_error_propagation("corr-p")
        assert insight is not None
        assert insight.severity == "critical"
        # p2 is the first error -> stop, p3 not visited
        assert len(insight.evidence["affected_components"]) == 2
        order = [c["component"] for c in insight.evidence["propagation_order"]]
        assert order == ["agent/a-1", "service/s-1"]
        assert len(insight.affected_components) == 2
        assert insight.evidence["correlation_id"] == "corr-p"
        assert insight.confidence_score == 0.88

    async def test_exception_returns_none(self):
        gen = ErrorCausalityInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.track_error_propagation("corr-x") is None


# ============================================================================
# detect_error_patterns
# ============================================================================

class TestDetectErrorPatterns:
    async def test_no_patterns_returns_empty(self, db):
        _event(db, "d1", level="ERROR", message="once")
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.detect_error_patterns() == []

    async def test_no_error_events(self, db):
        _event(db, "d2", level="INFO", message="info")
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.detect_error_patterns() == []

    async def test_pattern_detected(self, db):
        base = datetime.now(timezone.utc) - timedelta(minutes=10)
        for i in range(5):
            _event(db, f"r{i}", level="ERROR", message="timeout connecting",
                   ts=base + timedelta(seconds=i))
        _event(db, "x1", level="ERROR", message="different", ts=base + timedelta(seconds=60))
        gen = ErrorCausalityInsightGenerator(db)
        insights = await gen.detect_error_patterns("last_1h")
        assert len(insights) == 1
        insight = insights[0]
        assert insight.insight_type == "error"
        assert insight.severity == "warning"
        assert insight.evidence["occurrence_count"] == 5
        assert insight.evidence["error_message"] == "timeout connecting"
        assert insight.evidence["duration_seconds"] == 4
        assert insight.evidence["frequency_per_min"] > 0
        assert insight.evidence["first_seen"] is not None
        assert insight.evidence["last_seen"] is not None
        assert insight.evidence["affected_components"] == [
            {"type": "agent", "id": "agent-1"}
        ]
        assert "Fix root cause of this error" in insight.suggestions
        assert insight.confidence_score == 0.90

    async def test_pattern_outside_time_range(self, db):
        base = datetime.now(timezone.utc) - timedelta(days=2)
        for i in range(5):
            _event(db, f"old{i}", level="ERROR", message="stale error",
                   ts=base + timedelta(seconds=i))
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.detect_error_patterns("last_1h") == []

    async def test_pattern_with_none_message(self, db):
        base = datetime.now(timezone.utc) - timedelta(minutes=2)
        for i in range(5):
            _event(db, f"nm{i}", level="ERROR", message=None,
                   ts=base + timedelta(seconds=i))
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.detect_error_patterns() == []

    async def test_exception_returns_empty(self):
        gen = ErrorCausalityInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.detect_error_patterns() == []


# ============================================================================
# suggest_fixes_from_history
# ============================================================================

class TestSuggestFixesFromHistory:
    async def test_no_history_returns_empty(self, db):
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.suggest_fixes_from_history("some error") == []

    async def test_past_error_triggers_heuristics(self, db):
        gen = ErrorCausalityInsightGenerator(db)

        for label, message, expected in [
            ("connection timeout", "connection timeout",
             "Increase timeout duration"),
            ("out of memory error", "out of memory error",
             "Increase available memory"),
            ("permission denied", "permission denied",
             "Check API credentials"),
            ("unauthorized access", "unauthorized access",
             "Refresh authentication tokens"),
            ("file not found", "file not found",
             "Verify resource exists"),
            ("rate limit exceeded", "rate limit exceeded",
             "Implement request throttling"),
            ("random failure", "random failure",
             "Review error logs for more details"),
        ]:
            _event(db, f"h-{label}", level="ERROR", message=message,
                   ts=datetime.now(timezone.utc) - timedelta(minutes=1))
            fixes = await gen.suggest_fixes_from_history(label)
            assert expected in fixes, label

    async def test_history_outside_range_returns_empty(self, db):
        _event(db, "h2", level="ERROR", message="old error",
               ts=datetime.now(timezone.utc) - timedelta(days=60))
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.suggest_fixes_from_history("old error") == []

    async def test_long_error_message_truncated_to_50(self, db):
        long_msg = "x" * 100
        _event(db, "h3", level="ERROR", message=long_msg,
               ts=datetime.now(timezone.utc) - timedelta(minutes=1))
        gen = ErrorCausalityInsightGenerator(db)
        fixes = await gen.suggest_fixes_from_history(long_msg)
        assert fixes == [
            "Review error logs for more details",
            "Check service health status",
            "Verify configuration",
            "Contact support if issue persists",
        ]

    async def test_exception_returns_empty(self):
        gen = ErrorCausalityInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.suggest_fixes_from_history("boom") == []


# ============================================================================
# analyze_error_severity_distribution
# ============================================================================

class TestAnalyzeErrorSeverityDistribution:
    async def test_no_errors_returns_none(self, db):
        _event(db, "s1", level="INFO", component_type="agent")
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.analyze_error_severity_distribution("agent") is None

    async def test_high_critical_rate(self, db):
        for i in range(4):
            _event(db, f"cr{i}", level="CRITICAL", component_type="agent")
        _event(db, "er1", level="ERROR", component_type="agent")
        gen = ErrorCausalityInsightGenerator(db)
        insight = await gen.analyze_error_severity_distribution("agent", "last_24h")
        assert insight is not None
        assert insight.severity == "critical"
        assert insight.evidence["total_errors"] == 5
        assert insight.evidence["critical_errors"] == 4
        assert insight.evidence["critical_rate"] == 0.8
        assert insight.evidence["error_distribution"] == {"CRITICAL": 4, "ERROR": 1}
        assert insight.title == "High critical error rate for agent"
        assert insight.affected_components == [{"type": "agent"}]
        assert insight.confidence_score == 0.92

    async def test_low_critical_rate_returns_none(self, db):
        for i in range(8):
            _event(db, f"lo{i}", level="ERROR", component_type="agent")
        _event(db, "cr1", level="CRITICAL", component_type="agent")
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.analyze_error_severity_distribution("agent") is None

    async def test_different_component_ignored(self, db):
        _event(db, "z1", level="ERROR", component_type="browser")
        gen = ErrorCausalityInsightGenerator(db)
        assert await gen.analyze_error_severity_distribution("agent") is None

    async def test_exception_returns_none(self):
        gen = ErrorCausalityInsightGenerator(_BadSession())
        with patch.object(gen.logger, "error"):
            assert await gen.analyze_error_severity_distribution("agent") is None


# ============================================================================
# _parse_time_range
# ============================================================================

class TestParseTimeRange:
    def test_all_branches(self, db):
        gen = ErrorCausalityInsightGenerator(db)
        now = datetime.now(timezone.utc)
        for label, delta in [
            ("last_1h", timedelta(hours=1)),
            ("last_24h", timedelta(hours=24)),
            ("last_7d", timedelta(days=7)),
            ("last_30d", timedelta(days=30)),
            ("bogus", timedelta(hours=1)),
        ]:
            cutoff = gen._parse_time_range(label)
            assert abs((now - delta - cutoff).total_seconds()) < 5, label
