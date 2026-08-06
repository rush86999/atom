# -*- coding: utf-8 -*-
"""
Round 79 — gap coverage: core/debug_monitor.py (DebugMonitor health/ops/error
aggregation over debug_events/debug_insights; zero test references before this
file).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.debug_monitor import DebugMonitor
from core.models import DebugEvent, DebugInsight


@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.database import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine, tables=[DebugEvent.__table__, DebugInsight.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def monitor(db_session):
    return DebugMonitor(db_session)


def _seed_event(db, level, component_type="agent", component_id="agent-1", correlation_id="c1", age_minutes=5):
    evt = DebugEvent(
        event_type="log",
        component_type=component_type,
        component_id=component_id,
        correlation_id=correlation_id,
        level=level,
        message=f"{level} message",
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
    )
    db.add(evt)
    return evt


def _seed_insight(db, insight_type="error", severity="warning", scope="component",
                  affected=None, resolved=False, age_minutes=5):
    ins = DebugInsight(
        insight_type=insight_type,
        severity=severity,
        title=f"{insight_type} insight",
        summary="summary",
        scope=scope,
        affected_components=affected or [],
        resolved=resolved,
        generated_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
    )
    db.add(ins)
    return ins


class TestSystemHealth:
    async def test_empty_system_is_healthy(self, monitor):
        health = await monitor.get_system_health()
        assert health["overall_health_score"] == 100
        assert health["status"] == "healthy"
        assert health["total_events"] == 0

    async def test_error_events_penalize_score(self, db_session, monitor):
        _seed_event(db_session, "INFO", age_minutes=1)
        _seed_event(db_session, "ERROR", age_minutes=1)
        _seed_event(db_session, "ERROR", age_minutes=1)
        db_session.commit()
        health = await monitor.get_system_health()
        assert health["total_events"] == 3
        assert health["error_events"] == 2
        assert health["overall_health_score"] < 100
        assert health["error_rate"] > 0

    async def test_stale_events_excluded(self, db_session, monitor):
        _seed_event(db_session, "ERROR", age_minutes=600)
        db_session.commit()
        health = await monitor.get_system_health(time_range="last_1h")
        assert health["total_events"] == 0

    async def test_component_breakdown_present(self, db_session, monitor):
        _seed_event(db_session, "ERROR", component_type="agent", age_minutes=1)
        _seed_event(db_session, "ERROR", component_type="browser", age_minutes=1)
        db_session.commit()
        health = await monitor.get_system_health()
        assert set(health["components"].keys()) == {"agent", "browser"}


class TestComponentHealth:
    async def test_healthy_component(self, db_session, monitor):
        _seed_event(db_session, "INFO", component_id="agent-1", age_minutes=1)
        db_session.commit()
        result = await monitor.get_component_health("agent", "agent-1")
        assert result["health_score"] == 100
        assert result["status"] == "healthy"

    async def test_degraded_component(self, db_session, monitor):
        for _ in range(10):
            _seed_event(db_session, "INFO", component_id="agent-1", age_minutes=1)
        for _ in range(3):
            _seed_event(db_session, "ERROR", component_id="agent-1", age_minutes=1)
        db_session.commit()
        result = await monitor.get_component_health("agent", "agent-1")
        assert result["status"] == "degraded"
        assert result["error_events"] == 3

    async def test_unhealthy_component(self, db_session, monitor):
        for _ in range(5):
            _seed_event(db_session, "ERROR", component_id="agent-1", age_minutes=1)
        db_session.commit()
        result = await monitor.get_component_health("agent", "agent-1")
        assert result["status"] == "unhealthy"

    async def test_other_component_events_ignored(self, db_session, monitor):
        _seed_event(db_session, "ERROR", component_id="agent-2", age_minutes=1)
        db_session.commit()
        result = await monitor.get_component_health("agent", "agent-1")
        assert result["total_events"] == 0
        assert result["health_score"] == 100

    async def test_relevant_insight_attached(self, db_session, monitor):
        _seed_event(db_session, "ERROR", component_id="agent-1", age_minutes=1)
        _seed_insight(
            db_session, affected=[{"type": "agent", "id": "agent-1"}], age_minutes=1
        )
        db_session.commit()
        result = await monitor.get_component_health("agent", "agent-1")
        assert len(result["recent_insights"]) == 1
        assert result["recent_insights"][0]["type"] == "error"


class TestActiveOperations:
    async def test_operations_grouped_by_correlation(self, db_session, monitor):
        _seed_event(db_session, "INFO", correlation_id="op-1", age_minutes=1)
        _seed_event(db_session, "INFO", correlation_id="op-1", age_minutes=1)
        _seed_event(db_session, "INFO", correlation_id="op-2", age_minutes=1)
        db_session.commit()
        ops = await monitor.get_active_operations()
        assert {o["correlation_id"] for o in ops} == {"op-1", "op-2"}
        by_id = {o["correlation_id"]: o for o in ops}
        assert by_id["op-1"]["event_count"] == 2

    async def test_operation_with_errors_marked(self, db_session, monitor):
        _seed_event(db_session, "ERROR", correlation_id="op-1", age_minutes=1)
        db_session.commit()
        ops = await monitor.get_active_operations()
        assert ops[0]["status"] == "errors"

    async def test_old_operations_excluded(self, db_session, monitor):
        _seed_event(db_session, "INFO", correlation_id="op-old", age_minutes=600)
        db_session.commit()
        assert await monitor.get_active_operations() == []


class TestErrorRatesAndThroughput:
    async def test_error_rate_by_component_requires_10_events(self, db_session, monitor):
        for i in range(11):
            _seed_event(db_session, "ERROR", component_type="agent", age_minutes=1)
        _seed_event(db_session, "INFO", component_type="agent", age_minutes=1)
        _seed_event(db_session, "ERROR", component_type="browser", age_minutes=1)  # only 1 event
        db_session.commit()
        rates = await monitor.get_error_rate_by_component()
        assert len(rates) == 1
        assert rates[0]["component_type"] == "agent"
        assert rates[0]["error_count"] == 11

    async def test_throughput_metrics(self, db_session, monitor):
        for i in range(3):
            _seed_event(db_session, "INFO", component_type="agent", age_minutes=1)
        _seed_event(db_session, "INFO", component_type="browser", age_minutes=1)
        db_session.commit()
        metrics = await monitor.get_throughput_metrics(time_range="last_1h")
        assert metrics["total_events"] == 4
        assert metrics["throughput_by_component"]["agent"]["total_events"] == 3
        assert metrics["events_per_minute"] == pytest.approx(4 / 60)

    async def test_insight_summary(self, db_session, monitor):
        _seed_insight(db_session, insight_type="error", severity="critical", age_minutes=1)
        _seed_insight(db_session, insight_type="error", severity="critical", age_minutes=1)
        _seed_insight(db_session, insight_type="performance", severity="info", resolved=True, age_minutes=1)
        db_session.commit()
        summary = await monitor.get_insight_summary(time_range="last_24h")
        assert summary["total_count"] == 3
        assert summary["by_type"]["error"]["critical"] == 2
        assert summary["resolved_count"] == 1
        assert summary["unresolved_count"] == 2


class TestTimeRangeHelpers:
    def test_parse_time_range(self, monitor):
        assert monitor._get_duration_minutes("last_1h") == 60
        assert monitor._get_duration_minutes("last_24h") == 1440
        assert monitor._get_duration_minutes("last_7d") == 10080
        assert monitor._get_duration_minutes("unknown") == 60

    def test_parse_returns_aware_datetime(self, monitor):
        for rng in ("last_1h", "last_24h", "last_7d", "bogus"):
            parsed = monitor._parse_time_range(rng)
            assert parsed.tzinfo is not None
