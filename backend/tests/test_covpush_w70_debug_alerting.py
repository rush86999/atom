# -*- coding: utf-8 -*-
"""Coverage wave 70 — core/debug_alerting (in-memory SQLite, zero LLM spend).

- DebugAlertingEngine: check_system_health (all sub-checks + exception),
  check_component_health (low sample, above-threshold alert, cooldown dedup,
  below-threshold, exception), get_active_alerts (severity/resolved/time
  filtering + exception), _check_error_rates (grouped real query, alert
  creation, dedup suppression, below-threshold, exception),
  _check_performance (p95 latency alert, dedup, below-threshold, exception),
  _check_anomalies (3x spike alert, dedup, no-spike, exception),
  _check_recent_alert (component match/miss, generic hit/miss, exception),
  group_similar_alerts (grouping + exception fallback), _alerts_are_similar
  (type/severity/word-overlap branches), create_alert.
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
from core.debug_alerting import DebugAlertingEngine


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _now():
    return datetime.utcnow()


def _event(db, eid, *, component_type="agent", component_id="agent-1",
           level="INFO", data=None, ts=None, message="msg"):
    event = DebugEvent(
        id=eid,
        event_type="log",
        component_type=component_type,
        component_id=component_id,
        correlation_id="corr-1",
        level=level,
        message=message,
        data=data or {},
        timestamp=ts if ts is not None else _now(),
    )
    db.add(event)
    db.commit()
    return event


def _insight(db, iid, *, insight_type="error", severity="critical",
             title="Alert title", affected_components=None, generated_at=None,
             resolved=False):
    insight = DebugInsight(
        id=iid,
        insight_type=insight_type,
        severity=severity,
        title=title,
        description="D",
        summary="S",
        evidence={},
        confidence_score=0.95,
        suggestions=["s1"],
        scope="component",
        affected_components=affected_components or [],
        resolved=resolved,
        generated_at=generated_at if generated_at is not None else _now(),
    )
    db.add(insight)
    db.commit()
    return insight


class _BadSession:
    def query(self, model):
        raise RuntimeError("db down")


def _engine(db, **kwargs):
    return DebugAlertingEngine(db_session=db, **kwargs)


# ============================================================================
# check_system_health
# ============================================================================

class TestCheckSystemHealth:
    async def test_health_all_checks_run(self, db):
        # 10 ERROR events for one component → error-rate alert
        for i in range(10):
            _event(db, f"er-{i}", component_id="hot-1", level="ERROR")
        # latency events → performance alert
        for i in range(3):
            _event(db, f"sl-{i}", component_id="slow-1", level="INFO",
                   data={"duration_ms": 9000})
        engine = _engine(db)
        alerts = await engine.check_system_health()
        types = {a.insight_type for a in alerts}
        assert "error" in types
        assert "performance" in types

    async def test_health_exception(self):
        engine = _engine(_BadSession())
        with patch.object(engine.logger, "error") as err:
            assert await engine.check_system_health() == []
        # each sub-check logs its own failure (3 sub-checks, no outer raise)
        assert err.call_count == 3

    async def test_health_outer_except_when_subcheck_raises(self, db):
        engine = _engine(db)
        with patch.object(engine, "_check_error_rates",
                          side_effect=RuntimeError("hard failure")):
            with patch.object(engine.logger, "error") as err:
                assert await engine.check_system_health() == []
        err.assert_called_once()


# ============================================================================
# check_component_health
# ============================================================================

class TestCheckComponentHealth:
    async def test_below_minimum_sample(self, db):
        for i in range(9):
            _event(db, f"x-{i}", component_id="few-1", level="ERROR")
        assert await _engine(db).check_component_health("agent", "few-1") is None

    async def test_high_error_rate_creates_alert(self, db):
        for i in range(10):
            _event(db, f"x-{i}", component_id="bad-1", level="ERROR")
        alert = await _engine(db).check_component_health("agent", "bad-1")
        assert alert is not None
        assert alert.severity == "critical"
        assert "High error rate alert" in alert.title
        assert alert.evidence["error_rate"] == 1.0
        assert alert.affected_components == [{"type": "agent", "id": "bad-1"}]
        assert alert.confidence_score == 0.95

    async def test_high_error_rate_deduped_by_recent_alert(self, db):
        for i in range(10):
            _event(db, f"x-{i}", component_id="bad-2", level="ERROR")
        _insight(db, "recent-1", affected_components=[{"type": "agent", "id": "bad-2"}])
        assert await _engine(db).check_component_health("agent", "bad-2") is None

    async def test_below_threshold(self, db):
        for i in range(10):
            _event(db, f"x-{i}", component_id="ok-1", level="INFO")
        assert await _engine(db).check_component_health("agent", "ok-1") is None

    async def test_exception(self):
        engine = _engine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine.check_component_health("agent", "a-1") is None


# ============================================================================
# get_active_alerts
# ============================================================================

class TestGetActiveAlerts:
    async def test_filters_severity_resolved_time(self, db):
        _insight(db, "act-1", severity="critical", resolved=False)
        _insight(db, "act-2", severity="warning", resolved=False)
        _insight(db, "act-3", severity="critical", resolved=True)
        _insight(db, "act-4", severity="info", resolved=False)
        _insight(db, "act-5", severity="critical", resolved=False,
                 generated_at=_now() - timedelta(hours=48))
        alerts = await _engine(db).get_active_alerts()
        assert {a.id for a in alerts} == {"act-1", "act-2"}

    async def test_limit(self, db):
        for i in range(5):
            _insight(db, f"lim-{i}", severity="warning", resolved=False)
        alerts = await _engine(db).get_active_alerts(limit=2)
        assert len(alerts) == 2

    async def test_exception(self):
        engine = _engine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine.get_active_alerts() == []


# ============================================================================
# _check_error_rates
# ============================================================================

class TestCheckErrorRates:
    async def test_alert_created_for_hot_component(self, db):
        for i in range(10):
            _event(db, f"e-{i}", component_id="hot-1", level="ERROR")
        for i in range(10):
            _event(db, f"i-{i}", component_id="calm-1", level="INFO")
        alerts = await _engine(db)._check_error_rates()
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.title == "High error rate alert: agent/hot-1"
        assert alert.evidence["error_count"] == 10
        assert alert.evidence["total_count"] == 10
        assert alert.summary == "10/10 events were errors"

    async def test_recent_alert_suppresses(self, db):
        for i in range(10):
            _event(db, f"e-{i}", component_id="hot-2", level="ERROR")
        _insight(db, "recent-2", affected_components=[{"type": "agent", "id": "hot-2"}])
        assert await _engine(db)._check_error_rates() == []

    async def test_below_threshold_no_alert(self, db):
        for i in range(10):
            _event(db, f"i-{i}", component_id="calm-2", level="INFO")
        assert await _engine(db)._check_error_rates() == []

    async def test_exception(self):
        engine = _engine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine._check_error_rates() == []


# ============================================================================
# _check_performance
# ============================================================================

class TestCheckPerformance:
    async def test_p95_over_threshold_alert(self, db):
        for i in range(4):
            _event(db, f"sl-{i}", component_id="slow-1", level="INFO",
                   data={"duration_ms": 8000})
        _event(db, "sl-5", component_id="slow-1", level="INFO",
               data={"duration_ms": 1000})
        alerts = await _engine(db)._check_performance()
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.title == "High latency alert: agent/slow-1"
        assert alert.severity == "warning"
        assert alert.evidence["p95_latency_ms"] > 5000
        assert alert.evidence["sample_count"] == 5

    async def test_recent_alert_suppresses(self, db):
        for i in range(3):
            _event(db, f"sl-{i}", component_id="slow-2", level="INFO",
                   data={"duration_ms": 9000})
        _insight(db, "recent-3", affected_components=[{"type": "agent", "id": "slow-2"}])
        assert await _engine(db)._check_performance() == []

    async def test_below_threshold(self, db):
        _event(db, "sl-1", component_id="fast-1", level="INFO", data={"duration_ms": 10})
        assert await _engine(db)._check_performance() == []

    async def test_no_duration_data(self, db):
        _event(db, "sl-2", component_id="nodur-1", level="INFO", data={})
        assert await _engine(db)._check_performance() == []

    async def test_exception(self):
        engine = _engine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine._check_performance() == []


# ============================================================================
# _check_anomalies
# ============================================================================

class TestCheckAnomalies:
    async def test_spike_alert(self, db):
        now = _now()
        for i in range(5):
            _event(db, f"prev-{i}", level="ERROR",
                   ts=now - timedelta(minutes=90))
        for i in range(20):
            _event(db, f"curr-{i}", level="ERROR",
                   ts=now - timedelta(minutes=10))
        alerts = await _engine(db)._check_anomalies()
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.title == "Error rate spike detected"
        assert alert.severity == "critical"
        assert alert.scope == "system"
        assert alert.evidence["current_errors"] == 20
        assert alert.evidence["previous_errors"] == 5
        assert alert.evidence["spike_factor"] == 4.0

    async def test_recent_alert_suppresses(self, db):
        now = _now()
        for i in range(5):
            _event(db, f"prev-{i}", level="ERROR", ts=now - timedelta(minutes=90))
        for i in range(20):
            _event(db, f"curr-{i}", level="ERROR", ts=now - timedelta(minutes=10))
        _insight(db, "recent-4", insight_type="anomaly")
        assert await _engine(db)._check_anomalies() == []

    async def test_no_previous_errors(self, db):
        for i in range(5):
            _event(db, f"curr-{i}", level="ERROR", ts=_now() - timedelta(minutes=10))
        assert await _engine(db)._check_anomalies() == []

    async def test_no_spike(self, db):
        now = _now()
        for i in range(10):
            _event(db, f"prev-{i}", level="ERROR", ts=now - timedelta(minutes=90))
        for i in range(15):
            _event(db, f"curr-{i}", level="ERROR", ts=now - timedelta(minutes=10))
        assert await _engine(db)._check_anomalies() == []

    async def test_exception(self):
        engine = _engine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine._check_anomalies() == []


# ============================================================================
# _check_recent_alert
# ============================================================================

class TestCheckRecentAlert:
    async def test_component_match(self, db):
        _insight(db, "cr-1", affected_components=[{"type": "agent", "id": "a-1"},
                                                  {"type": "agent", "id": "a-2"}])
        engine = _engine(db)
        assert await engine._check_recent_alert(
            component_type="agent", component_id="a-2", alert_type="high_error_rate") is True

    async def test_component_no_match(self, db):
        _insight(db, "cr-2", affected_components=[{"type": "agent", "id": "a-1"}])
        engine = _engine(db)
        assert await engine._check_recent_alert(
            component_type="agent", component_id="a-9", alert_type="high_error_rate") is False

    async def test_component_no_insights(self, db):
        engine = _engine(db)
        assert await engine._check_recent_alert(
            component_type="agent", component_id="a-1", alert_type="high_error_rate") is False

    async def test_generic_hit(self, db):
        _insight(db, "cr-3")
        assert await _engine(db)._check_recent_alert(alert_type="error_spike") is True

    async def test_generic_miss(self, db):
        assert await _engine(db)._check_recent_alert(alert_type="error_spike") is False

    async def test_exception(self):
        engine = _engine(_BadSession())
        with patch.object(engine.logger, "error"):
            assert await engine._check_recent_alert(alert_type="x") is False


# ============================================================================
# grouping + similarity + create
# ============================================================================

class TestGrouping:
    async def test_groups_similar_alerts(self, db):
        a1 = _insight(db, "g-1", title="High error rate detected on node alpha")
        a2 = _insight(db, "g-2", title="High error rate detected on node beta")
        a3 = _insight(db, "g-3", title="Low disk space warning on storage")
        groups = await _engine(db).group_similar_alerts([a1, a2, a3])
        assert len(groups) == 2
        assert [len(g) for g in groups] == [2, 1]

    async def test_group_exception_fallback(self, db):
        engine = _engine(db)
        alerts = [_insight(db, "f-1", title="a b c d"), _insight(db, "f-2", title="e f g h")]
        with patch.object(engine, "_alerts_are_similar", side_effect=RuntimeError("boom")):
            with patch.object(engine.logger, "error"):
                groups = await engine.group_similar_alerts(alerts)
        assert len(groups) == 2
        assert all(len(g) == 1 for g in groups)

    def test_alerts_are_similar_type_mismatch(self, db):
        engine = _engine(db)
        a1 = _insight(db, "s-1", insight_type="error", title="one two three four")
        a2 = _insight(db, "s-2", insight_type="performance", title="one two three five")
        assert engine._alerts_are_similar(a1, a2) is False

    def test_alerts_are_similar_severity_mismatch(self, db):
        engine = _engine(db)
        a1 = _insight(db, "s-3", severity="critical", title="one two three four")
        a2 = _insight(db, "s-4", severity="warning", title="one two three five")
        assert engine._alerts_are_similar(a1, a2) is False

    def test_alerts_are_similar_word_overlap(self, db):
        engine = _engine(db)
        a1 = _insight(db, "s-5", title="high error rate alert node one")
        a2 = _insight(db, "s-6", title="high error rate alert node two")
        assert engine._alerts_are_similar(a1, a2) is True

    def test_alerts_are_similar_low_overlap(self, db):
        engine = _engine(db)
        a1 = _insight(db, "s-7", title="alpha beta gamma delta")
        a2 = _insight(db, "s-8", title="epsilon zeta eta theta")
        assert engine._alerts_are_similar(a1, a2) is False

    async def test_create_alert(self, db):
        engine = _engine(db)
        alert = await engine.create_alert(
            alert_type="error",
            severity="critical",
            title="Custom alert",
            description="Custom description",
            summary="Custom summary",
            evidence={"source": "test"},
            suggestions=["fix it"],
            affected_components=[{"type": "agent", "id": "a-1"}],
            scope="component",
        )
        assert alert.id is not None
        assert alert.confidence_score == 1.0
        stored = db.query(DebugInsight).filter(DebugInsight.id == alert.id).first()
        assert stored is not None
        assert stored.title == "Custom alert"
