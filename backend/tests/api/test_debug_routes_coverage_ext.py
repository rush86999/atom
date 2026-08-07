"""
Extended coverage tests for api/debug_routes.py

Imports via `api.debug_routes` (NOT `backend.api.debug_routes`) so that
coverage consolidates with the agent/admin modules under the `api.` path.

Covers endpoints NOT exercised by tests/api/test_debug_routes_coverage.py:
- POST /events/batch            (batch collection)
- GET  /state/{type}/{id}       (state retrieval w/ checkpoint)
- POST /insights/generate       (insight generation)
- PUT  /insights/{id}/resolve   (mark resolved)
- GET  /sessions                (list w/ filters)
- PUT  /sessions/{id}/close     (close session)
- POST /analytics/component-health
- GET  /analytics/error-patterns   (incl. None-message branch)
- GET  /analytics/system-health
- GET  /analytics/active-operations
- GET  /analytics/throughput
- GET  /analytics/insights-summary
- POST /analytics/performance    (incl. no-data branch)
- GET  /analytics/error-rate
- POST /ai/query
- GET  /opencode-usage           (incl. failure branch)
- helpers _get_storage, _parse_time_range

Plus TDD bug-hunt tests (BUG-prefixed docstrings).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.debug_routes import router
from core.models import DebugEvent, DebugInsight, DebugSession, User


# ============================================================================
# Fixtures
# ============================================================================

_current_test_user = None


@pytest.fixture
def client(db_session: Session):
    """TestClient with DB + auth overridden.

    Set _current_test_user to None to simulate 401.
    """
    global _current_test_user
    _current_test_user = None

    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.security_dependencies import get_current_user

    def override_get_db():
        yield db_session

    def override_get_current_user():
        if _current_test_user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return _current_test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()
    _current_test_user = None


@pytest.fixture
def user(db_session: Session):
    u = User(
        id="dbg-user-1",
        email="dbg@example.com",
        first_name="D",
        last_name="B",
        role="member",
        status="active",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _set_user(u):
    global _current_test_user
    _current_test_user = u


# ============================================================================
# Helpers
# ============================================================================

def test_parse_time_range_known_values():
    from api.debug_routes import _parse_time_range

    now = datetime.now(timezone.utc)
    for key, hours in [("last_1h", 1), ("last_24h", 24)]:
        delta = _parse_time_range(key)
        assert (now - delta).total_seconds() >= hours * 3600 - 60


def test_parse_time_range_unknown_falls_back_to_1h():
    from api.debug_routes import _parse_time_range

    now = datetime.now(timezone.utc)
    delta = _parse_time_range("bogus_range")
    # Falls back to last_1h
    elapsed = (now - delta).total_seconds()
    assert 3500 <= elapsed <= 3700


def test_parse_time_range_7d_and_30d():
    from api.debug_routes import _parse_time_range

    now = datetime.now(timezone.utc)
    assert (now - _parse_time_range("last_7d")).days >= 6
    assert (now - _parse_time_range("last_30d")).days >= 29


def test_get_storage_handles_config_error():
    """_get_storage must not raise if config/redis construction fails."""
    from api.debug_routes import _get_storage

    with patch("api.debug_routes.get_config", side_effect=RuntimeError("no config")):
        storage = _get_storage(db=Mock())
    assert storage is not None


# ============================================================================
# POST /events/batch
# ============================================================================

def test_collect_batch_events_success(client, user):
    _set_user(user)
    mock_collector = Mock()
    mock_events = [Mock(id="e1"), Mock(id="e2")]
    mock_collector.collect_batch_events = AsyncMock(return_value=mock_events)
    with patch("api.debug_routes.get_debug_collector", return_value=mock_collector):
        resp = client.post(
            "/api/debug/events/batch",
            json={
                "events": [
                    {"event_type": "log", "component_type": "agent", "correlation_id": "c1"},
                    {"event_type": "error", "component_type": "workflow", "correlation_id": "c2"},
                ]
            },
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["collected_count"] == 2
    assert data["event_ids"] == ["e1", "e2"]


def test_collect_batch_events_with_none_ids(client, user):
    """Events whose id is None are surfaced as None in event_ids list."""
    _set_user(user)
    mock_collector = Mock()
    mock_collector.collect_batch_events = AsyncMock(
        return_value=[Mock(id="e1"), Mock(id=None)]
    )
    with patch("api.debug_routes.get_debug_collector", return_value=mock_collector):
        resp = client.post(
            "/api/debug/events/batch",
            json={"events": [{"event_type": "log", "component_type": "a", "correlation_id": "c"}]},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["event_ids"] == ["e1", None]


# ============================================================================
# GET /state/{type}/{id}
# ============================================================================

def test_get_component_state_with_checkpoint(client, user):
    _set_user(user)
    mock_storage = Mock()
    mock_storage.get_state_snapshot = AsyncMock(return_value={"id": "snap"})
    with patch("api.debug_routes._get_storage", return_value=mock_storage):
        resp = client.get(
            "/api/debug/state/agent/agent-1",
            params={"operation_id": "op-1", "checkpoint_name": "cp1"},
        )
    assert resp.status_code == 200


def test_get_component_state_when_disabled(client, user):
    """Disabled system -> get_component_state returns 400 DEBUG_DISABLED."""
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.get(
            "/api/debug/state/agent/agent-1",
            params={"operation_id": "op-1"},
        )
    assert resp.status_code == 400


# ============================================================================
# POST /insights/generate
# ============================================================================

def test_generate_insights_success(client, user):
    _set_user(user)
    mock_engine = Mock()
    mock_insight = Mock()
    mock_engine.generate_insights_from_events = AsyncMock(return_value=[mock_insight])
    mock_engine._insight_to_dict = Mock(return_value={"id": "i1"})
    with patch("api.debug_routes.DebugInsightEngine", return_value=mock_engine):
        resp = client.post(
            "/api/debug/insights/generate",
            json={"correlation_id": "c1", "time_range": "last_1h"},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["count"] == 1
    assert data["insights"] == [{"id": "i1"}]


def test_generate_insights_empty(client, user):
    _set_user(user)
    mock_engine = Mock()
    mock_engine.generate_insights_from_events = AsyncMock(return_value=[])
    with patch("api.debug_routes.DebugInsightEngine", return_value=mock_engine):
        resp = client.post("/api/debug/insights/generate", json={})
    assert resp.status_code == 200
    assert resp.json()["data"]["count"] == 0


# ============================================================================
# PUT /insights/{id}/resolve
# ============================================================================

def test_resolve_insight_success(client, user, db_session):
    _set_user(user)
    ins = DebugInsight(
        id="ins-resolve-1",
        insight_type="performance",
        severity="medium",
        title="t",
        summary="s",
        description="d",
        confidence_score=0.5,
        resolved=False,
        generated_at=datetime.utcnow(),
    )
    db_session.add(ins)
    db_session.commit()

    resp = client.put(
        "/api/debug/insights/ins-resolve-1/resolve",
        params={"resolution_notes": "fixed"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["resolved"] is True
    db_session.refresh(ins)
    assert ins.resolved is True
    assert ins.resolution_notes == "fixed"


def test_resolve_insight_not_found(client, user):
    _set_user(user)
    resp = client.put(
        "/api/debug/insights/no-such/resolve",
        params={"resolution_notes": "x"},
    )
    assert resp.status_code == 404
    assert "INSIGHT_NOT_FOUND" in resp.json()["detail"]["error"]["code"]


def test_resolve_insight_when_disabled(client, user):
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.put(
            "/api/debug/insights/x/resolve",
            params={"resolution_notes": "x"},
        )
    assert resp.status_code == 400


# ============================================================================
# GET /sessions + PUT /sessions/{id}/close
# ============================================================================

def test_list_sessions_with_filters(client, user, db_session):
    _set_user(user)
    for i in range(3):
        db_session.add(
            DebugSession(
                id=f"sess-{i}",
                session_name=f"S{i}",
                active=(i == 0),
                resolved=(i == 2),
                event_count=i,
                insight_count=0,
                created_at=datetime.utcnow() - timedelta(minutes=i),
            )
        )
    db_session.commit()

    resp = client.get("/api/debug/sessions", params={"active": True})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["count"] == 1
    assert data["sessions"][0]["session_name"] == "S0"


def test_list_sessions_resolved_filter(client, user, db_session):
    _set_user(user)
    db_session.add(
        DebugSession(
            id="sess-r",
            session_name="R",
            active=False,
            resolved=True,
            event_count=0,
            insight_count=0,
            created_at=datetime.utcnow(),
        )
    )
    db_session.commit()
    resp = client.get("/api/debug/sessions", params={"resolved": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["count"] == 1


def test_list_sessions_empty(client, user):
    _set_user(user)
    resp = client.get("/api/debug/sessions")
    assert resp.status_code == 200
    assert resp.json()["data"]["count"] == 0


def test_close_session_success(client, user, db_session):
    _set_user(user)
    s = DebugSession(
        id="sess-close",
        session_name="X",
        active=True,
        event_count=0,
        insight_count=0,
        created_at=datetime.utcnow(),
    )
    db_session.add(s)
    db_session.commit()

    resp = client.put("/api/debug/sessions/sess-close/close")
    assert resp.status_code == 200
    db_session.refresh(s)
    assert s.active is False
    assert s.closed_at is not None


def test_close_session_when_disabled(client, user):
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.put("/api/debug/sessions/x/close")
    assert resp.status_code == 400


# ============================================================================
# Analytics endpoints
# ============================================================================

def test_component_health(client, user):
    _set_user(user)
    mock_q = Mock()
    mock_q.get_component_health = AsyncMock(return_value={"status": "ok"})
    with patch("api.debug_routes.DebugQuery", return_value=mock_q):
        resp = client.post(
            "/api/debug/analytics/component-health",
            json={"component_type": "agent", "component_id": "a1", "time_range": "1h"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"


def test_error_patterns_includes_none_message(client, user, db_session):
    """Events with message=None are bucketed under 'unknown' (line 644 branch)."""
    _set_user(user)
    db_session.add(
        DebugEvent(
            id="err-1",
            event_type="error",
            component_type="agent",
            component_id="a1",
            correlation_id="c",
            level="ERROR",
            message=None,
            timestamp=datetime.utcnow(),
        )
    )
    db_session.commit()
    resp = client.get("/api/debug/analytics/error-patterns")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_errors"] == 1
    assert len(data["error_patterns"]) == 1
    # None message is bucketed without crashing; message may be None or 'unknown'
    pat = data["error_patterns"][0]
    assert pat["message"] is None or "unknown" in (pat["message"] or "")


def test_error_patterns_aggregation(client, user, db_session):
    """Two identical errors aggregate into one pattern with count=2."""
    _set_user(user)
    now = datetime.utcnow()
    for _ in range(2):
        db_session.add(
            DebugEvent(
                id=f"err-{_}",
                event_type="error",
                component_type="agent",
                component_id="a1",
                correlation_id="c",
                level="ERROR",
                message="boom",
                timestamp=now,
            )
        )
    db_session.commit()
    resp = client.get("/api/debug/analytics/error-patterns", params={"time_range": "last_24h"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_errors"] == 2
    assert data["error_patterns"][0]["count"] == 2


def test_system_health(client, user):
    _set_user(user)
    mock_mon = Mock()
    mock_mon.get_system_health = AsyncMock(return_value={"healthy": True})
    with patch("core.debug_monitor.DebugMonitor", return_value=mock_mon):
        resp = client.get("/api/debug/analytics/system-health")
    assert resp.status_code == 200
    assert resp.json()["data"]["healthy"] is True


def test_active_operations(client, user):
    _set_user(user)
    mock_mon = Mock()
    mock_mon.get_active_operations = AsyncMock(return_value=[{"op": "x"}])
    with patch("core.debug_monitor.DebugMonitor", return_value=mock_mon):
        resp = client.get("/api/debug/analytics/active-operations", params={"limit": 5})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["count"] == 1


def test_throughput(client, user):
    _set_user(user)
    mock_mon = Mock()
    mock_mon.get_throughput_metrics = AsyncMock(return_value={"tps": 10})
    with patch("core.debug_monitor.DebugMonitor", return_value=mock_mon):
        resp = client.get("/api/debug/analytics/throughput")
    assert resp.status_code == 200
    assert resp.json()["data"]["tps"] == 10


def test_insights_summary(client, user):
    _set_user(user)
    mock_mon = Mock()
    mock_mon.get_insight_summary = AsyncMock(return_value={"by_type": {}})
    with patch("core.debug_monitor.DebugMonitor", return_value=mock_mon):
        resp = client.get("/api/debug/analytics/insights-summary")
    assert resp.status_code == 200


def test_performance_analytics_with_data(client, user):
    _set_user(user)
    mock_gen = Mock()
    mock_insight = Mock()
    mock_insight.id = "p1"
    mock_insight.insight_type = "performance"
    mock_insight.severity = "high"
    mock_insight.title = "slow"
    mock_insight.summary = "s"
    mock_insight.description = "d"
    mock_insight.evidence = {}
    mock_insight.confidence_score = 0.9
    mock_insight.suggestions = []
    mock_gen.analyze_component_latency = AsyncMock(return_value=mock_insight)
    with patch(
        "core.debug_insights.performance.PerformanceInsightGenerator",
        return_value=mock_gen,
    ):
        resp = client.post(
            "/api/debug/analytics/performance",
            json={"component_type": "agent", "component_id": "a1", "time_range": "1h"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["insight"]["id"] == "p1"


def test_performance_analytics_no_data(client, user):
    _set_user(user)
    mock_gen = Mock()
    mock_gen.analyze_component_latency = AsyncMock(return_value=None)
    with patch(
        "core.debug_insights.performance.PerformanceInsightGenerator",
        return_value=mock_gen,
    ):
        resp = client.post(
            "/api/debug/analytics/performance",
            json={"component_type": "agent", "component_id": "a1", "time_range": "1h"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["insight"] is None


def test_error_rate(client, user):
    _set_user(user)
    mock_mon = Mock()
    mock_mon.get_error_rate_by_component = AsyncMock(
        return_value=[{"component": "a", "rate": 0.1}]
    )
    with patch("core.debug_monitor.DebugMonitor", return_value=mock_mon):
        resp = client.get("/api/debug/analytics/error-rate")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["error_rates"]) == 1


# ============================================================================
# POST /ai/query
# ============================================================================

def test_ai_query_success(client, user):
    _set_user(user)
    mock_assistant = Mock()
    mock_assistant.ask = AsyncMock(return_value={"answer": "42"})
    with patch("api.debug_routes.DebugAIAssistant", return_value=mock_assistant):
        resp = client.post(
            "/api/debug/ai/query",
            json={"question": "what happened?", "context": {"user_id": "u1"}},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["answer"] == "42"


def test_ai_query_missing_question(client, user):
    _set_user(user)
    resp = client.post("/api/debug/ai/query", json={})
    assert resp.status_code == 422


# ============================================================================
# GET /opencode-usage
# ============================================================================

def test_opencode_usage_success(client, user):
    _set_user(user)
    mock_tracker = Mock()
    mock_tracker.usage_summary.return_value = {
        "provider": "opencode-go",
        "headroom": 0.9,
        "requests_in_window": 5,
        "tokens_in_window": 100.0,
        "limits": {},
        "monthly": None,
        "models": {},
    }
    mock_tracker.window_seconds = 60
    mock_tracker.get_model_headroom.return_value = 0.5

    mock_registry = Mock()
    mock_registry.summary.return_value = {
        "weights": {"gpt-4": 1.0},
        "model_limits": {"gpt-4": {"rpm": 60}},
    }

    with patch("core.llm.provider_rate_limits.get_provider_rate_tracker", return_value=mock_tracker), \
         patch("core.llm.opencode_model_limits.get_opencode_model_limits", return_value=mock_registry):
        resp = client.get("/api/debug/opencode-usage")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["provider"] == "opencode-go"
    assert "gpt-4" in data["models"]


def test_opencode_usage_with_model_filter(client, user):
    _set_user(user)
    mock_tracker = Mock()
    mock_tracker.usage_summary.return_value = {
        "provider": "opencode-go",
        "headroom": 0.9,
        "requests_in_window": 5,
        "tokens_in_window": 100.0,
        "limits": {},
        "monthly": None,
        "models": {},
    }
    mock_tracker.window_seconds = 60
    mock_tracker.get_model_headroom.return_value = 0.5

    mock_registry = Mock()
    mock_registry.summary.return_value = {
        "weights": {"gpt-4": 1.0, "claude": 2.0},
        "model_limits": {"gpt-4": {}, "claude": {}},
    }

    with patch("core.llm.provider_rate_limits.get_provider_rate_tracker", return_value=mock_tracker), \
         patch("core.llm.opencode_model_limits.get_opencode_model_limits", return_value=mock_registry):
        resp = client.get("/api/debug/opencode-usage", params={"model": "gpt-4"})
    assert resp.status_code == 200
    models = resp.json()["data"]["models"]
    assert list(models.keys()) == ["gpt-4"]


def test_opencode_usage_failure_returns_500(client, user):
    """When the underlying tracker raises, endpoint returns 500 OPCODE_USAGE_UNAVAILABLE."""
    _set_user(user)
    with patch(
        "core.llm.provider_rate_limits.get_provider_rate_tracker",
        side_effect=RuntimeError("tracker down"),
    ):
        resp = client.get("/api/debug/opencode-usage")
    assert resp.status_code == 500
    assert resp.json()["detail"]["error"]["code"] == "OPCODE_USAGE_UNAVAILABLE"


# ============================================================================
# Auth enforcement (every debug endpoint requires a user)
# ============================================================================

@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/debug/analytics/system-health"),
        ("GET", "/api/debug/analytics/active-operations"),
        ("GET", "/api/debug/analytics/throughput"),
        ("GET", "/api/debug/analytics/insights-summary"),
        ("GET", "/api/debug/analytics/error-rate"),
        ("GET", "/api/debug/opencode-usage"),
        ("GET", "/api/debug/sessions"),
    ],
)
def test_debug_analytics_requires_auth(client, method, path):
    """BUG: every analytics/usage endpoint must require auth (401 without token)."""
    _set_user(None)
    resp = getattr(client, method.lower())(path)
    assert resp.status_code == 401


# ============================================================================
# Disabled-system branches for collection endpoints (200 enabled=False)
# ============================================================================

def test_query_events_disabled_returns_empty(client, user):
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.get("/api/debug/events")
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False


def test_query_insights_disabled_returns_empty(client, user):
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.get("/api/debug/insights")
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False


def test_list_sessions_disabled_returns_empty(client, user):
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.get("/api/debug/sessions")
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False


def test_generate_insights_disabled(client, user):
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.post("/api/debug/insights/generate", json={})
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False


def test_component_health_disabled(client, user):
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.post(
            "/api/debug/analytics/component-health",
            json={"component_type": "a", "component_id": "b", "time_range": "1h"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False


def test_error_patterns_disabled(client, user):
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.get("/api/debug/analytics/error-patterns")
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False


def test_create_session_disabled(client, user):
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.post("/api/debug/sessions", json={"session_name": "x"})
    assert resp.status_code == 400
    assert "DEBUG_DISABLED" in resp.json()["detail"]["error"]["code"]


def test_collect_event_disabled(client, user):
    _set_user(user)
    with patch("api.debug_routes.DEBUG_SYSTEM_ENABLED", False):
        resp = client.post(
            "/api/debug/events",
            json={"event_type": "log", "component_type": "a", "correlation_id": "c"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False


# ============================================================================
# Event/snapshot collection with collector initialization branch
# ============================================================================

def test_collect_event_initializes_collector_when_missing(client, user):
    """When get_debug_collector returns None, init_debug_collector is called."""
    _set_user(user)
    mock_collector = Mock()
    mock_event = Mock(id="ev-init")
    mock_collector.collect_event = AsyncMock(return_value=mock_event)
    with patch("api.debug_routes.get_debug_collector", return_value=None), \
         patch("api.debug_routes.init_debug_collector", return_value=mock_collector):
        resp = client.post(
            "/api/debug/events",
            json={"event_type": "log", "component_type": "a", "correlation_id": "c"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["event_id"] == "ev-init"


def test_collect_event_returns_none_id(client, user):
    """When collector returns an event with no id, event_id is None."""
    _set_user(user)
    mock_collector = Mock()
    mock_collector.collect_event = AsyncMock(return_value=None)
    with patch("api.debug_routes.get_debug_collector", return_value=mock_collector):
        resp = client.post(
            "/api/debug/events",
            json={"event_type": "log", "component_type": "a", "correlation_id": "c"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["event_id"] is None


def test_collect_state_snapshot_initializes_collector(client, user):
    _set_user(user)
    mock_collector = Mock()
    mock_snap = Mock(id="snap-1")
    mock_collector.collect_state_snapshot = AsyncMock(return_value=mock_snap)
    with patch("api.debug_routes.get_debug_collector", return_value=None), \
         patch("api.debug_routes.init_debug_collector", return_value=mock_collector):
        resp = client.post(
            "/api/debug/state",
            json={
                "component_type": "agent",
                "component_id": "a1",
                "operation_id": "op-1",
                "state_data": {"x": 1},
            },
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["snapshot_id"] == "snap-1"


def test_collect_state_snapshot_returns_none(client, user):
    _set_user(user)
    mock_collector = Mock()
    mock_collector.collect_state_snapshot = AsyncMock(return_value=None)
    with patch("api.debug_routes.get_debug_collector", return_value=mock_collector):
        resp = client.post(
            "/api/debug/state",
            json={
                "component_type": "agent",
                "component_id": "a1",
                "operation_id": "op-1",
                "state_data": {},
            },
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["snapshot_id"] is None


# ============================================================================
# BUG-HUNT (TDD)
# ============================================================================

def test_bug_state_endpoint_requires_operation_id(client, user):
    """BUG: GET /state/{type}/{id} without operation_id must return 400, not 500.

    The handler explicitly checks for operation_id and raises MISSING_OPERATION_ID.
    This test locks that contract so a future refactor can't regress to a 500
    (None deref when constructing the storage query).
    """
    _set_user(user)
    resp = client.get("/api/debug/state/agent/agent-1")
    assert resp.status_code == 400
    assert "MISSING_OPERATION_ID" in resp.json()["detail"]["error"]["code"]


# ============================================================================
# Happy-path coverage for query/get endpoints (under the api. import path so
# coverage consolidates with agent/admin modules).
# ============================================================================

def test_query_events_happy_path(client, user):
    _set_user(user)
    mock_storage = Mock()
    mock_storage.query_events = AsyncMock(
        return_value=[{"id": "e1"}, {"id": "e2"}]
    )
    with patch("api.debug_routes._get_storage", return_value=mock_storage):
        resp = client.get(
            "/api/debug/events",
            params={
                "component_type": "agent",
                "component_id": "a1",
                "correlation_id": "c1",
                "event_type": "log",
                "level": "INFO",
                "time_range": "last_1h",
                "limit": 50,
                "offset": 10,
            },
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["count"] == 2
    # Ensure all filter params were forwarded
    _, kwargs = mock_storage.query_events.call_args
    assert kwargs["component_type"] == "agent"
    assert kwargs["offset"] == 10


def test_get_event_happy_path(client, user):
    _set_user(user)
    mock_storage = Mock()
    mock_storage.get_event = AsyncMock(return_value={"id": "ev-1", "level": "INFO"})
    with patch("api.debug_routes._get_storage", return_value=mock_storage):
        resp = client.get("/api/debug/events/ev-1")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == "ev-1"


def test_get_event_not_found(client, user):
    _set_user(user)
    mock_storage = Mock()
    mock_storage.get_event = AsyncMock(return_value=None)
    with patch("api.debug_routes._get_storage", return_value=mock_storage):
        resp = client.get("/api/debug/events/nope")
    assert resp.status_code == 404
    assert "EVENT_NOT_FOUND" in resp.json()["detail"]["error"]["code"]


def test_query_insights_happy_path(client, user):
    _set_user(user)
    mock_storage = Mock()
    mock_storage.query_insights = AsyncMock(
        return_value=[{"id": "i1", "severity": "high"}]
    )
    with patch("api.debug_routes._get_storage", return_value=mock_storage):
        resp = client.get(
            "/api/debug/insights",
            params={
                "insight_type": "performance",
                "severity": "high",
                "scope": "component",
                "resolved": "false",
                "time_range": "last_24h",
                "limit": 25,
            },
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["count"] == 1


def test_get_insight_happy_path(client, user):
    _set_user(user)
    mock_storage = Mock()
    mock_storage.get_insight = AsyncMock(return_value={"id": "i-x"})
    with patch("api.debug_routes._get_storage", return_value=mock_storage):
        resp = client.get("/api/debug/insights/i-x")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == "i-x"


def test_get_insight_not_found(client, user):
    _set_user(user)
    mock_storage = Mock()
    mock_storage.get_insight = AsyncMock(return_value=None)
    with patch("api.debug_routes._get_storage", return_value=mock_storage):
        resp = client.get("/api/debug/insights/nope")
    assert resp.status_code == 404
    assert "INSIGHT_NOT_FOUND" in resp.json()["detail"]["error"]["code"]


def test_create_debug_session_success(client, user):
    _set_user(user)
    resp = client.post(
        "/api/debug/sessions",
        json={
            "session_name": "My Session",
            "description": "desc",
            "filters": {"k": "v"},
            "scope": {"s": 1},
        },
    )
    assert resp.status_code == 200
    assert "session_id" in resp.json()["data"]
