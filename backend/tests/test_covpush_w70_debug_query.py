# -*- coding: utf-8 -*-
"""Coverage wave 70 — core/debug_query (in-memory SQLite, zero LLM spend, no network).

- DebugQuery: get_component_health (unknown/healthy/degraded/unhealthy, insights
  serialization ±generated_at, cache hit, cache disabled, exception), 
  get_operation_progress (not_found/completed/failed/in_progress/started,
  message-less last event, timestamp-less events, exception), explain_error
  (not-found, basic explanation, insight-backed explanation via source_event_id
  — BUG-FIX W70-2 regression — exception), compare_components (single, health
  gap, error-rate variation, no-insights, exception), ask (why-failing route,
  health route, error route, unknown, exception), _explain_component_failure
  (no errors, most-common error, exception), _parse_time_range (h/d/m/default),
  _insight_to_dict (±generated_at).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import DebugEvent, DebugInsight  # noqa: F401 (register models)
from core.debug_query import DebugQuery
import core.debug_query as mod


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def _clear_global_cache():
    """The DebugQuery cache is a process-global singleton — clear it between
    tests so cached health results never leak across test cases."""
    from core.debug_cache import _cache_instance

    if _cache_instance is not None:
        _cache_instance.clear()
    yield
    if _cache_instance is not None:
        _cache_instance.clear()


def _event(db, eid, *, component_type="agent", component_id="agent-1",
           correlation_id="corr-1", level="INFO", message=None,
           data=None, ts=None, event_type="log"):
    event = DebugEvent(
        id=eid,
        event_type=event_type,
        component_type=component_type,
        component_id=component_id,
        correlation_id=correlation_id,
        level=level,
        message=message,
        data=data,
        timestamp=ts if ts is not None else datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    return event


def _insight(db, iid, *, scope="component", generated_at=None, source_event_id=None):
    insight = DebugInsight(
        id=iid,
        insight_type="error",
        severity="warning",
        title=f"Insight {iid}",
        description=f"Desc {iid}",
        summary=f"Summary {iid}",
        evidence={"k": "v"},
        confidence_score=0.9,
        suggestions=["s1", "s2"],
        scope=scope,
        affected_components=[{"type": "agent", "id": "agent-1"}],
        source_event_id=source_event_id,
        generated_at=generated_at if generated_at is not None else datetime.now(timezone.utc),
    )
    db.add(insight)
    db.commit()
    return insight


class _BadSession:
    """Session whose query() always raises."""

    def query(self, model):
        raise RuntimeError("db down")


# ============================================================================
# Component health
# ============================================================================

class TestComponentHealth:
    async def test_health_no_events_unknown(self, db):
        query = DebugQuery(db)
        result = await query.get_component_health("agent", "ghost-1", "1h")
        assert result["status"] == "unknown"
        assert result["health_score"] == 100
        assert result["total_events"] == 0
        assert result["error_rate"] == 0
        assert result["insights"] == []
        assert "analyzed_at" in result

    async def test_health_healthy(self, db):
        for i in range(19):
            _event(db, f"e{i}", level="INFO")
        _event(db, "e-bad", level="ERROR")
        result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert result["status"] == "healthy"
        assert result["health_score"] == 95
        assert result["error_events"] == 1

    async def test_health_degraded(self, db):
        for i in range(14):
            _event(db, f"e{i}", level="INFO")
        for i in range(6):
            _event(db, f"bad{i}", level="ERROR")
        result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert result["status"] == "degraded"
        assert result["health_score"] == 70

    async def test_health_unhealthy(self, db):
        for i in range(10):
            _event(db, f"bad{i}", level="CRITICAL")
        result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert result["status"] == "unhealthy"
        assert result["health_score"] == 0

    async def test_health_with_insights(self, db):
        _insight(db, "ins-2", scope="distributed",
                 generated_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        _insight(db, "ins-1", scope="component")
        result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert len(result["insights"]) == 2
        first = result["insights"][0]
        assert first["id"] == "ins-1"
        assert first["type"] == "error"
        assert first["severity"] == "warning"
        assert first["title"] == "Insight ins-1"
        assert first["summary"] == "Summary ins-1"
        assert first["confidence_score"] == 0.9
        assert first["generated_at"] is not None

    async def test_health_insight_without_generated_at(self, db):
        # Core insert bypasses the ORM Python-side default so generated_at is
        # stored as NULL; the time filter then excludes it from results.
        from sqlalchemy import insert

        db.execute(insert(DebugInsight).values(
            id="ins-null-ts", insight_type="error", severity="warning",
            title="T", scope="component", generated_at=None,
        ))
        db.commit()
        result = await DebugQuery(db).get_component_health("agent", "agent-1", "1h")
        assert result["insights"] == []

    async def test_health_cache_hit(self, db):
        query = DebugQuery(db)
        query.cache.set("health:cached:1:1h", {"from_cache": True})
        result = await query.get_component_health("cached", "1", "1h")
        assert result == {"from_cache": True}

    async def test_health_cache_disabled(self, db):
        with patch.object(mod, "DEBUG_QUERY_CACHE_ENABLED", False):
            query = DebugQuery(db)
            assert query.cache is None
        result = await query.get_component_health("agent", "agent-1", "1h")
        assert result["status"] == "unknown"

    async def test_health_exception(self):
        query = DebugQuery(_BadSession())
        result = await query.get_component_health("agent", "agent-1", "1h")
        assert result["status"] == "error"
        assert result["health_score"] == 0
        assert "db down" in result["error"]


# ============================================================================
# Operation progress
# ============================================================================

class TestOperationProgress:
    async def test_progress_not_found(self, db):
        result = await DebugQuery(db).get_operation_progress("op-nope")
        assert result["status"] == "not_found"
        assert result["progress"] == 0

    async def test_progress_completed(self, db):
        _event(db, "s1", correlation_id="op-full", data={"step": 1, "status": "completed"}, message="step one")
        _event(db, "s2", correlation_id="op-full", data={"step": 2, "status": "completed"}, message="step two")
        result = await DebugQuery(db).get_operation_progress("op-full")
        assert result["status"] == "completed"
        assert result["progress"] == 1.0
        assert result["total_steps"] == 2
        assert result["completed_steps"] == 2
        assert result["error_count"] == 0
        assert "Operation has 2 steps" in result["insights"]
        assert result["started_at"] is not None and result["updated_at"] is not None

    async def test_progress_failed(self, db):
        _event(db, "s1", correlation_id="op-bad", data={"step": 1, "status": "completed"})
        _event(db, "s2", correlation_id="op-bad", level="ERROR", data={"step": 2, "status": "failed"})
        result = await DebugQuery(db).get_operation_progress("op-bad")
        assert result["status"] == "failed"
        assert result["error_count"] == 1

    async def test_progress_in_progress_with_last_action(self, db):
        _event(db, "s1", correlation_id="op-mid", data={"step": 1, "status": "completed"})
        _event(db, "s2", correlation_id="op-mid", data={"progress": 0.5}, message="processing batch")
        result = await DebugQuery(db).get_operation_progress("op-mid")
        assert result["status"] == "in_progress"
        assert result["progress"] == 0.5
        assert "Last action: processing batch" in result["insights"]

    async def test_progress_in_progress_without_last_message(self, db):
        _event(db, "s1", correlation_id="op-nomsg", data={"step": 1, "status": "completed"})
        _event(db, "s2", correlation_id="op-nomsg", data={"progress": 0.5}, message=None)
        result = await DebugQuery(db).get_operation_progress("op-nomsg")
        assert result["status"] == "in_progress"
        assert "Last action" not in " ".join(result["insights"])

    async def test_progress_started_no_step_data(self, db):
        _event(db, "s1", correlation_id="op-start", data={"note": "hello"})
        result = await DebugQuery(db).get_operation_progress("op-start")
        assert result["status"] == "started"
        assert result["total_steps"] == 0

    async def test_progress_timestampless_events(self, db):
        # Core insert bypasses the ORM Python-side default so timestamp is
        # stored as NULL (the ORM would fire `default` for an explicit None).
        from sqlalchemy import insert

        db.execute(insert(DebugEvent).values(
            id="s-nts", event_type="log", component_type="agent",
            component_id="agent-1", correlation_id="op-nots",
            data={"step": 1, "status": "completed"}, timestamp=None,
        ))
        db.commit()
        result = await DebugQuery(db).get_operation_progress("op-nots")
        assert result["started_at"] is None
        assert result["updated_at"] is None

    async def test_progress_exception(self):
        query = DebugQuery(_BadSession())
        result = await query.get_operation_progress("op-x")
        assert result["status"] == "error"
        assert "db down" in result["error"]


# ============================================================================
# Error explanation
# ============================================================================

class TestExplainError:
    async def test_explain_error_not_found(self, db):
        result = await DebugQuery(db).explain_error("no-such-id")
        assert result["found"] is False

    async def test_explain_error_basic(self, db):
        _event(db, "err-1", level="ERROR", message="boom happened")
        result = await DebugQuery(db).explain_error("err-1")
        assert result["found"] is True
        assert result["message"] == "boom happened"
        assert result["component"] == "agent/agent-1"
        assert result["level"] == "ERROR"
        assert result["root_cause"] == "Error in agent"
        assert result["confidence"] == 0.5
        assert len(result["suggestions"]) == 3

    async def test_explain_error_with_insight(self, db):
        """BUG-FIX W70-2 regression: insight-backed explanations use the
        source_event_id link (column was lost from the model)."""
        event = _event(db, "err-2", level="CRITICAL", message="segfault")
        _insight(db, "ins-root", source_event_id="err-2")
        result = await DebugQuery(db).explain_error("err-2")
        assert result["found"] is True
        assert result["root_cause"] == "Desc ins-root"
        assert result["suggestions"] == ["s1", "s2"]
        assert result["confidence"] == 0.9

    async def test_explain_error_exception(self):
        query = DebugQuery(_BadSession())
        result = await query.explain_error("err-x")
        assert result["found"] is False
        assert "db down" in result["error"]


# ============================================================================
# Component comparison
# ============================================================================

class TestCompareComponents:
    async def test_compare_single_component(self, db):
        result = await DebugQuery(db).compare_components(
            [{"type": "agent", "id": "agent-1"}], "1h"
        )
        assert result["insights"] == ["Need at least 2 components to compare"]
        assert len(result["components"]) == 1

    async def test_compare_health_gap(self, db):
        for i in range(20):
            _event(db, f"g{i}", component_id="good-1", level="INFO")
        for i in range(10):
            _event(db, f"b{i}", component_id="bad-1", level="ERROR")
        result = await DebugQuery(db).compare_components(
            [{"type": "agent", "id": "good-1"}, {"type": "agent", "id": "bad-1"}], "1h"
        )
        assert len(result["components"]) == 2
        assert any("points healthier" in ins for ins in result["insights"])

    async def test_compare_error_rate_variation(self, db):
        for i in range(8):
            _event(db, f"a{i}", component_id="comp-a", level="INFO")
        for i in range(2):
            _event(db, f"a-bad{i}", component_id="comp-a", level="ERROR")
        for i in range(10):
            _event(db, f"c{i}", component_id="comp-c", level="INFO")
        result = await DebugQuery(db).compare_components(
            [{"type": "agent", "id": "comp-a"}, {"type": "agent", "id": "comp-c"}], "1h"
        )
        assert any("Error rate varies" in ins for ins in result["insights"])

    async def test_compare_no_insights(self, db):
        for i in range(10):
            _event(db, f"n{i}", component_id="same-1", level="INFO")
        for i in range(10):
            _event(db, f"m{i}", component_id="same-2", level="INFO")
        result = await DebugQuery(db).compare_components(
            [{"type": "agent", "id": "same-1"}, {"type": "agent", "id": "same-2"}], "1h"
        )
        assert result["insights"] == []

    async def test_compare_exception(self, db):
        # A component dict without the "type" key raises KeyError inside the
        # loop, which the outer except converts into the failure payload.
        result = await DebugQuery(db).compare_components([{"nokey": "x"}], "1h")
        assert result["components"] == []
        assert "Comparison failed" in result["insights"][0]


# ============================================================================
# Natural language query
# ============================================================================

class TestAsk:
    async def test_ask_why_failing_routes_to_explanation(self, db):
        _event(db, "wf-1", component_type="workflow", component_id="workflow-789",
               level="ERROR", message="timeout")
        result = await DebugQuery(db).ask("Why is workflow-789 failing?")
        assert "is failing due to: timeout" in result["answer"]
        assert result["confidence"] == 0.85

    async def test_ask_health_query(self, db):
        _event(db, "h-1", component_id="agent-42", level="INFO")
        result = await DebugQuery(db).ask("show me the health of agent-42")
        assert result["health_score"] == 100
        assert result["status"] == "healthy"

    async def test_ask_error_query(self, db):
        result = await DebugQuery(db).ask("What error is happening?")
        assert result["answer"] == "Please provide the error ID"

    async def test_ask_unknown_question(self, db):
        result = await DebugQuery(db).ask("how many stars are out tonight?")
        assert "couldn't understand" in result["answer"]
        assert result["confidence"] == 0.3

    async def test_ask_exception(self, db):
        # A non-string question raises inside ask()'s try block — the only
        # reachable path since every intent handler has its own try/except.
        result = await DebugQuery(db).ask(None)
        assert "Error processing question" in result["answer"]


# ============================================================================
# Failure explanation helper
# ============================================================================

class TestExplainComponentFailure:
    async def test_no_recent_errors(self, db):
        result = await DebugQuery(db)._explain_component_failure("agent-999")
        assert "No recent errors found" in result["answer"]
        assert result["confidence"] == 0.8

    async def test_most_common_error(self, db):
        _event(db, "f1", component_id="agent-5", level="ERROR", message="disk full")
        _event(db, "f2", component_id="agent-5", level="ERROR", message="disk full")
        _event(db, "f3", component_id="agent-5", level="ERROR", message="oom")
        result = await DebugQuery(db)._explain_component_failure("agent-5")
        assert "disk full" in result["answer"]
        assert result["evidence"][0]["error_count"] == 2
        assert result["evidence"][0]["recent_errors"] == 3
        assert len(result["suggestions"]) == 3

    async def test_exception(self):
        query = DebugQuery(_BadSession())
        result = await query._explain_component_failure("agent-5")
        assert "Error analyzing component failure" in result["answer"]
        assert result["confidence"] == 0.0


# ============================================================================
# Helpers
# ============================================================================

class TestHelpers:
    def test_parse_time_range_hours(self):
        q = DebugQuery(_BadSession())
        cutoff = q._parse_time_range("1h")
        assert abs((datetime.now(timezone.utc) - timedelta(hours=1) - cutoff).total_seconds()) < 5

    def test_parse_time_range_days(self):
        q = DebugQuery(_BadSession())
        cutoff = q._parse_time_range("7d")
        assert abs((datetime.now(timezone.utc) - timedelta(days=7) - cutoff).total_seconds()) < 5

    def test_parse_time_range_minutes(self):
        q = DebugQuery(_BadSession())
        cutoff = q._parse_time_range("30m")
        assert abs((datetime.now(timezone.utc) - timedelta(minutes=30) - cutoff).total_seconds()) < 5

    def test_parse_time_range_default(self):
        q = DebugQuery(_BadSession())
        cutoff = q._parse_time_range("bogus")
        assert abs((datetime.now(timezone.utc) - timedelta(hours=1) - cutoff).total_seconds()) < 5

    def test_insight_to_dict(self):
        q = DebugQuery(_BadSession())
        insight = DebugInsight(
            id="i-1", insight_type="error", severity="critical", title="T",
            summary="S", confidence_score=0.8,
            generated_at=datetime.now(timezone.utc),
        )
        d = q._insight_to_dict(insight)
        assert d["id"] == "i-1"
        assert d["severity"] == "critical"
        assert d["generated_at"] is not None

    def test_insight_to_dict_no_timestamp(self):
        q = DebugQuery(_BadSession())
        insight = DebugInsight(id="i-2", insight_type="flow", severity="info", title="T")
        assert q._insight_to_dict(insight)["generated_at"] is None
