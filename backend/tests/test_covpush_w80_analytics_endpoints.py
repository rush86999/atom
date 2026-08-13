# -*- coding: utf-8 -*-
"""Coverage wave 80 — core/analytics_endpoints.py to >=95% via TestClient on
a minimal FastAPI app hosting just this router (get_current_user overridden;
burnout/followup/workforce/workflow engines mocked — zero LLM spend, zero
network).

Covers:
- All static/derived endpoints: /health, /metrics, /dashboard, /performance,
  /insights, /insights/{id} (found + 404), /stats (daily/weekly/monthly +
  400), /real-time/streams, /reports, /status.
- /burnout-risk: high risk → workflow triggered; low risk → no workflow;
  WorkflowEngine constructor failure → logged (except branch).
- /deadline-risk: high risk → workflow triggered; critical → workflow;
  constructor failure → logged.
- /estimation-bias: success + service exception → 500.
- /skill-gaps: success + exception → 500.
- /email-followups: mock engine → candidates.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.analytics_endpoints import router, generate_insights
from core.auth import get_current_user
from core.burnout_detection_engine import WellnessScore

_FAKE_USER = SimpleNamespace(id="u1", email="u1@x.com")


def _make_app():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    return app


import pytest


@pytest.fixture()
def client():
    with TestClient(_make_app()) as c:
        yield c


def _wellness(risk_level="Low", score=30.0):
    return WellnessScore(
        risk_level=risk_level,
        score=score,
        factors={"meeting_density": 40.0},
        recommendations=["rest"],
        timestamp=datetime.now(),
        type="burnout",
    )


# ============================================================================
# Static / derived endpoints
# ============================================================================

def test_health(client):
    resp = client.get("/api/v1/analytics/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["validation_evidence"]["instant_analytics_operational"] is True


def test_metrics(client):
    resp = client.get("/api/v1/analytics/metrics")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_dashboard(client):
    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] > 15478
    assert data["real_time_processing"] is True
    assert "last_updated" in data


def test_performance(client):
    resp = client.get("/api/v1/analytics/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    assert all(m["uptime_percentage"] > 90 for m in data)
    assert all("endpoint" in m for m in data)


def test_insights(client):
    resp = client.get("/api/v1/analytics/insights")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    assert data[0]["insight_id"] == "insight_001"


def test_insight_found(client):
    resp = client.get("/api/v1/analytics/insights/insight_003")
    assert resp.status_code == 200
    assert resp.json()["category"] == "real_time"


def test_insight_not_found(client):
    resp = client.get("/api/v1/analytics/insights/nope")
    assert resp.status_code == 404


def test_stats_daily(client):
    resp = client.get("/api/v1/analytics/stats?period=daily")
    assert resp.status_code == 200
    data = resp.json()
    assert data["period"] == "daily"
    assert data["total_requests"] > 5234


def test_stats_weekly(client):
    resp = client.get("/api/v1/analytics/stats?period=weekly")
    assert resp.status_code == 200
    assert resp.json()["period"] == "weekly"


def test_stats_monthly(client):
    resp = client.get("/api/v1/analytics/stats?period=monthly")
    assert resp.status_code == 200
    assert resp.json()["period"] == "monthly"


def test_stats_bad_period(client):
    resp = client.get("/api/v1/analytics/stats?period=hourly")
    assert resp.status_code == 400
    assert "not supported" in resp.json()["detail"]


def test_real_time_streams(client):
    resp = client.get("/api/v1/analytics/real-time/streams")
    assert resp.status_code == 200
    assert len(resp.json()["streams"]) == 4
    assert resp.json()["real_time_status"] == "operational"


def test_reports(client):
    resp = client.get("/api/v1/analytics/reports")
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_status(client):
    resp = client.get("/api/v1/analytics/status")
    assert resp.status_code == 200
    assert resp.json()["analytics_engine"]["status"] == "operational"


def test_generate_insights_smoke():
    insights = generate_insights()
    assert len(insights) == 5
    assert all(i.confidence > 0.8 for i in insights)


def _patch_create_task(mod):
    """Capture the coroutine passed to asyncio.create_task (TestClient's
    loop never runs background tasks before assertions). Returns the
    coroutine; the test drives it with asyncio.run()."""
    captured = {}

    def fake_create_task(coro, *a, **k):
        captured["coro"] = coro
        return MagicMock()

    return patch.object(mod.asyncio, "create_task", side_effect=fake_create_task), captured


# ============================================================================
# /burnout-risk
# ============================================================================

def test_burnout_risk_high_triggers_workflow(client):
    import asyncio
    import core.analytics_endpoints as mod
    workflow_engine = MagicMock()
    workflow_engine.start_workflow = AsyncMock()
    create_task_patch, captured = _patch_create_task(mod)
    with patch.object(mod, "burnout_engine") as burnout, \
         patch.object(mod, "WorkflowEngine", return_value=workflow_engine), \
         create_task_patch:
        burnout.calculate_burnout_risk = AsyncMock(
            return_value=_wellness("High", 85.0))
        resp = client.get("/api/v1/analytics/burnout-risk")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "High"
    assert data["score"] == 85.0
    asyncio.run(captured["coro"])
    workflow_engine.start_workflow.assert_awaited_once()
    call = workflow_engine.start_workflow.await_args.args
    assert call[0]["id"] == "burnout_protection"
    assert call[1]["risk_score"] == 85.0


def test_burnout_risk_low_no_workflow(client):
    import core.analytics_endpoints as mod
    workflow_engine = MagicMock()
    workflow_engine.start_workflow = AsyncMock()
    with patch.object(mod, "burnout_engine") as burnout, \
         patch.object(mod, "WorkflowEngine", return_value=workflow_engine):
        burnout.calculate_burnout_risk = AsyncMock(
            return_value=_wellness("Low", 15.0))
        resp = client.get("/api/v1/analytics/burnout-risk")
    assert resp.status_code == 200
    workflow_engine.start_workflow.assert_not_called()


def test_burnout_risk_workflow_engine_exception_logged(client):
    import core.analytics_endpoints as mod
    with patch.object(mod, "burnout_engine") as burnout, \
         patch.object(mod, "WorkflowEngine", side_effect=RuntimeError("wf down")):
        burnout.calculate_burnout_risk = AsyncMock(
            return_value=_wellness("Critical", 95.0))
        resp = client.get("/api/v1/analytics/burnout-risk")
    assert resp.status_code == 200
    assert resp.json()["risk_level"] == "Critical"


# ============================================================================
# /deadline-risk
# ============================================================================

def test_deadline_risk_high_triggers_workflow(client):
    import asyncio
    import core.analytics_endpoints as mod
    workflow_engine = MagicMock()
    workflow_engine.start_workflow = AsyncMock()
    create_task_patch, captured = _patch_create_task(mod)
    with patch.object(mod, "burnout_engine") as burnout, \
         patch.object(mod, "WorkflowEngine", return_value=workflow_engine), \
         create_task_patch:
        burnout.calculate_deadline_risk = AsyncMock(
            return_value=_wellness("High", 80.0))
        resp = client.get("/api/v1/analytics/deadline-risk")
    assert resp.status_code == 200
    asyncio.run(captured["coro"])
    workflow_engine.start_workflow.assert_awaited_once()
    call = workflow_engine.start_workflow.await_args.args
    assert call[0]["id"] == "deadline_mitigation"


def test_deadline_risk_low_no_workflow(client):
    import core.analytics_endpoints as mod
    workflow_engine = MagicMock()
    workflow_engine.start_workflow = AsyncMock()
    with patch.object(mod, "burnout_engine") as burnout, \
         patch.object(mod, "WorkflowEngine", return_value=workflow_engine):
        burnout.calculate_deadline_risk = AsyncMock(
            return_value=_wellness("Medium", 55.0))
        resp = client.get("/api/v1/analytics/deadline-risk")
    assert resp.status_code == 200
    workflow_engine.start_workflow.assert_not_called()


def test_deadline_risk_engine_exception_logged(client):
    import core.analytics_endpoints as mod
    with patch.object(mod, "burnout_engine") as burnout, \
         patch.object(mod, "WorkflowEngine", side_effect=RuntimeError("boom")):
        burnout.calculate_deadline_risk = AsyncMock(
            return_value=_wellness("High", 90.0))
        resp = client.get("/api/v1/analytics/deadline-risk")
    assert resp.status_code == 200


# ============================================================================
# /estimation-bias & /skill-gaps
# ============================================================================

def test_estimation_bias_success(client):
    import core.analytics_endpoints as mod
    service = MagicMock()
    service.calculate_estimation_bias = MagicMock(
        return_value={"bias_factor": 0.92, "sample_size": 12})
    with patch.object(mod, "WorkforceAnalyticsService",
                      return_value=service):
        resp = client.get("/api/v1/analytics/estimation-bias?user_id=u1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["user_id"] == "u1"
    assert data["workspace_id"] == "default"
    service.calculate_estimation_bias.assert_called_once_with("default", "u1")


def test_estimation_bias_error(client):
    import core.analytics_endpoints as mod
    service = MagicMock()
    service.calculate_estimation_bias = MagicMock(
        side_effect=RuntimeError("boom"))
    with patch.object(mod, "WorkforceAnalyticsService",
                      return_value=service):
        resp = client.get("/api/v1/analytics/estimation-bias")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal error"


def test_skill_gaps_success(client):
    import core.analytics_endpoints as mod
    service = MagicMock()
    service.map_skill_gaps = MagicMock(
        return_value={"unmet_requirements": {"docker": ["t1"]}})
    with patch.object(mod, "WorkforceAnalyticsService",
                      return_value=service):
        resp = client.get("/api/v1/analytics/skill-gaps")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["workspace_id"] == "default"
    service.map_skill_gaps.assert_called_once_with("default")


def test_skill_gaps_error(client):
    import core.analytics_endpoints as mod
    service = MagicMock()
    service.map_skill_gaps = MagicMock(side_effect=RuntimeError("boom"))
    with patch.object(mod, "WorkforceAnalyticsService",
                      return_value=service):
        resp = client.get("/api/v1/analytics/skill-gaps")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal error"


# ============================================================================
# /email-followups
# ============================================================================

def test_email_followups(client):
    import core.analytics_endpoints as mod
    engine = MagicMock()
    engine.detect_missing_replies = AsyncMock(return_value=[{
        "id": "e1", "recipient": "investor@venture.com",
        "subject": "Quarterly Update",
        "original_sent_at": "2026-08-08T10:00:00",
        "days_since_sent": 5, "thread_id": "t1",
        "last_message_snippet": "checking in",
    }])
    with patch.object(mod, "followup_engine", engine):
        resp = client.get("/api/v1/analytics/email-followups")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "e1"
    engine.detect_missing_replies.assert_awaited_once()
