"""W69A — coverage push batch for 4 API modules.

Targets (statement coverage >= 95% each):
1. api/analytics_dashboard_endpoints.py   — 87% baseline (gap fills: engine
   singleton, top-workflows skip/zero/trend branches, exception paths,
   metrics-summary timeline variants)
2. api/protection_api.py                  — 72% baseline (success paths +
   multi-layer scan incl. LLM analyzer mode)
3. api/operational_routes.py              — never tested (existing
   tests/api/test_operational_routes.py is fully skipped; stale phantom
   patch targets) — full endpoint matrix here
4. api/llm_oauth_routes.py                — 95% baseline (rate-limit 429,
   state edge cases, HTTPException pass-through, revoke 404)

Style: FastAPI TestClient + app.dependency_overrides; patches use real
module names (no `backend.` prefix). Zero network / zero LLM spend.
"""

import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db


# ============================================================================
# Helpers
# ============================================================================

def make_client(router, overrides=None):
    """Build an isolated TestClient for a router with dependency overrides.

    ``overrides`` must be a dict keyed by the *dependency callable objects*
    (e.g. ``{get_current_user: override_fn}``) — never by keyword names, which
    would produce string keys that FastAPI cannot match.
    """
    app = FastAPI()
    app.include_router(router)
    for dep, value in (overrides or {}).items():
        app.dependency_overrides[dep] = value
    return TestClient(app, raise_server_exceptions=False)


def fake_user(user_id="u-69", tenant_id="t-1"):
    u = MagicMock()
    u.id = user_id
    u.tenant_id = tenant_id
    return u


def user_override(user_id="u-69", tenant_id="t-1"):
    def _override():
        return fake_user(user_id, tenant_id)
    return _override


# ============================================================================
# 1. api/analytics_dashboard_endpoints.py
# ============================================================================

class TestAnalyticsEngine:
    """Coverage for the module-level get_analytics_engine singleton."""

    def test_engine_created_on_demand_and_cached(self):
        import api.analytics_dashboard_endpoints as mod

        engine_cls = MagicMock()
        engine = engine_cls.return_value
        saved = mod._analytics_engine
        mod._analytics_engine = None
        try:
            with patch.object(mod, "WorkflowAnalyticsEngine", engine_cls):
                first = mod.get_analytics_engine()
                second = mod.get_analytics_engine()
            assert first is engine
            assert second is engine
            engine_cls.assert_called_once()
        finally:
            mod._analytics_engine = saved


def _perf_metrics(**overrides):
    from collections import namedtuple

    fields = [
        "total_executions", "successful_executions", "failed_executions",
        "success_rate", "average_duration_ms", "median_duration_ms",
        "p95_duration_ms", "p99_duration_ms", "error_rate", "unique_users",
        "executions_by_user", "most_common_errors", "average_step_duration",
    ]
    defaults = {
        "total_executions": 100,
        "successful_executions": 95,
        "failed_executions": 5,
        "success_rate": 95.0,
        "average_duration_ms": 1500.0,
        "median_duration_ms": 1200.0,
        "p95_duration_ms": 3000.0,
        "p99_duration_ms": 5000.0,
        "error_rate": 5.0,
        "unique_users": 10,
        "executions_by_user": {},
        "most_common_errors": [],
        "average_step_duration": {},
    }
    defaults.update(overrides)
    nt = namedtuple("PerformanceMetrics", fields)
    return nt(**defaults)


def _analytics_engine():
    engine = MagicMock()
    engine.get_performance_metrics.return_value = _perf_metrics()
    engine.get_all_workflow_ids.return_value = ["wf-1"]
    engine.get_workflow_name.return_value = None
    engine.get_last_execution_time.return_value = datetime.now()
    engine.get_execution_timeline.return_value = []
    engine.get_error_breakdown.return_value = {}
    engine.get_all_alerts.return_value = []
    engine.get_recent_events.return_value = []
    engine.get_unique_workflow_count.return_value = 1
    return engine


class TestAnalyticsDashboardEndpoints:
    """Gap-fill tests for analytics_dashboard_endpoints (87% -> >=95%)."""

    @pytest.fixture
    def client(self):
        from api.analytics_dashboard_endpoints import router

        return make_client(router, {get_current_user: user_override()})

    def test_requires_auth(self):
        from api.analytics_dashboard_endpoints import router

        client = make_client(router)
        assert client.get("/api/analytics/dashboard/kpis").status_code == 401

    def test_kpis_error_is_500(self, client):
        engine = _analytics_engine()
        engine.get_performance_metrics.side_effect = RuntimeError("boom")
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/kpis")
        assert resp.status_code == 500

    def test_top_workflows_skips_missing_metrics(self, client):
        engine = _analytics_engine()

        def pm(**kwargs):
            if kwargs.get("workflow_id") == "missing":
                return None
            return _perf_metrics()

        engine.get_all_workflow_ids.return_value = ["missing", "wf-1"]
        engine.get_performance_metrics.side_effect = pm
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/workflows/top-performing")
        assert resp.status_code == 200
        assert [w["workflow_id"] for w in resp.json()] == ["wf-1"]

    def test_top_workflows_zero_executions_guard(self, client):
        engine = _analytics_engine()
        engine.get_all_workflow_ids.return_value = ["wf-zero"]
        engine.get_performance_metrics.return_value = _perf_metrics(total_executions=0)
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/workflows/top-performing")
        assert resp.status_code == 200
        assert resp.json()[0]["success_rate"] == 0.0

    def test_top_workflows_trend_up(self, client):
        engine = _analytics_engine()

        def pm(**kwargs):
            if kwargs.get("time_window") == "1h":
                return _perf_metrics(total_executions=100, successful_executions=95)
            return _perf_metrics(total_executions=100, successful_executions=10)

        engine.get_performance_metrics.side_effect = pm
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/workflows/top-performing")
        assert resp.status_code == 200
        assert resp.json()[0]["trend"] == "up"

    def test_top_workflows_trend_down(self, client):
        engine = _analytics_engine()

        def pm(**kwargs):
            if kwargs.get("time_window") == "1h":
                return _perf_metrics(total_executions=100, successful_executions=10)
            return _perf_metrics(total_executions=100, successful_executions=95)

        engine.get_performance_metrics.side_effect = pm
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/workflows/top-performing")
        assert resp.status_code == 200
        assert resp.json()[0]["trend"] == "down"

    def test_top_workflows_error_is_500(self, client):
        engine = _analytics_engine()
        engine.get_all_workflow_ids.side_effect = RuntimeError("boom")
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/workflows/top-performing")
        assert resp.status_code == 500

    def test_timeline_error_is_500(self, client):
        engine = _analytics_engine()
        engine.get_execution_timeline.side_effect = RuntimeError("boom")
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/timeline")
        assert resp.status_code == 500

    def test_error_breakdown_error_is_500(self, client):
        engine = _analytics_engine()
        engine.get_error_breakdown.side_effect = RuntimeError("boom")
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/errors/breakdown")
        assert resp.status_code == 500

    def test_get_alerts_error_is_500(self, client):
        engine = _analytics_engine()
        engine.get_all_alerts.side_effect = RuntimeError("boom")
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/alerts")
        assert resp.status_code == 500

    def test_update_alert_error_is_500(self, client):
        engine = _analytics_engine()
        engine.update_alert.side_effect = RuntimeError("boom")
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.put("/api/analytics/alerts/alert-1")
        assert resp.status_code == 500

    def test_delete_alert_error_is_500(self, client):
        engine = _analytics_engine()
        engine.delete_alert.side_effect = RuntimeError("boom")
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.delete("/api/analytics/alerts/alert-1")
        assert resp.status_code == 500

    def test_realtime_feed_error_is_500(self, client):
        engine = _analytics_engine()
        engine.get_recent_events.side_effect = RuntimeError("boom")
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/realtime-feed")
        assert resp.status_code == 500

    def test_metrics_summary_timeline_pydantic_models(self, client):
        from api.analytics_dashboard_endpoints import ExecutionTimelineData

        engine = _analytics_engine()
        engine.get_execution_timeline.return_value = [
            ExecutionTimelineData(
                timestamp=datetime.now(), count=1, success_count=1,
                failure_count=0, average_duration_ms=1.0,
            )
        ]
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/metrics/summary")
        assert resp.status_code == 200
        assert resp.json()["data"]["timeline"][0]["count"] == 1

    def test_metrics_summary_timeline_empty(self, client):
        engine = _analytics_engine()
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/metrics/summary")
        assert resp.status_code == 200
        assert resp.json()["data"]["timeline"] == []

    def test_metrics_summary_timeline_plain_dicts(self, client):
        engine = _analytics_engine()
        engine.get_execution_timeline.return_value = [{"timestamp": 1, "count": 2}]
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/metrics/summary")
        assert resp.status_code == 200
        assert resp.json()["data"]["timeline"][0]["count"] == 2

    def test_metrics_summary_error_is_500(self, client):
        engine = _analytics_engine()
        engine.get_performance_metrics.side_effect = RuntimeError("boom")
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/metrics/summary")
        assert resp.status_code == 500

    def test_kpis_zero_metrics_returns_zeros(self, client):
        engine = _analytics_engine()
        engine.get_performance_metrics.return_value = None
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_executions"] == 0
        assert data["success_rate"] == 0.0
        assert data["unique_workflows"] == 0

    def test_top_workflows_sort_by_executions(self, client):
        engine = _analytics_engine()
        engine.get_all_workflow_ids.return_value = ["few", "many"]
        metrics_by_id = {
            "few": _perf_metrics(total_executions=10, successful_executions=8),
            "many": _perf_metrics(total_executions=500, successful_executions=400),
        }

        def pm(**kwargs):
            return metrics_by_id[kwargs["workflow_id"]]

        engine.get_performance_metrics.side_effect = pm
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get(
                "/api/analytics/dashboard/workflows/top-performing?sort_by=executions"
            )
        assert resp.status_code == 200
        assert [w["workflow_id"] for w in resp.json()] == ["many", "few"]

    def test_top_workflows_sort_by_duration(self, client):
        engine = _analytics_engine()
        engine.get_all_workflow_ids.return_value = ["slow", "fast"]
        metrics_by_id = {
            "slow": _perf_metrics(average_duration_ms=9000.0),
            "fast": _perf_metrics(average_duration_ms=300.0),
        }

        def pm(**kwargs):
            return metrics_by_id[kwargs["workflow_id"]]

        engine.get_performance_metrics.side_effect = pm
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get(
                "/api/analytics/dashboard/workflows/top-performing?sort_by=duration"
            )
        assert resp.status_code == 200
        assert [w["workflow_id"] for w in resp.json()] == ["fast", "slow"]

    def test_get_alerts_maps_configurations(self, client):
        from core.workflow_analytics_engine import AlertSeverity

        engine = _analytics_engine()
        alert = MagicMock()
        alert.alert_id = "a-1"
        alert.name = "High error rate"
        alert.description = "desc"
        alert.severity = AlertSeverity.HIGH
        alert.metric_name = "error_rate"
        alert.condition = "error_rate > 5"
        alert.threshold_value = 5.0
        alert.workflow_id = "wf-1"
        alert.enabled = True
        alert2 = MagicMock()
        alert2.alert_id = "a-2"
        alert2.name = "n"
        alert2.description = "d"
        alert2.severity = AlertSeverity.LOW
        alert2.metric_name = "m"
        alert2.condition = "c"
        alert2.threshold_value = None
        alert2.workflow_id = None
        alert2.enabled = False
        engine.get_all_alerts.return_value = [alert, alert2]
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/alerts?enabled_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["severity"] == "high"
        assert data[0]["threshold_value"] == 5.0
        assert data[1]["threshold_value"] == 0.0
        assert data[1]["workflow_id"] is None

    def test_create_alert_success(self, client):
        engine = _analytics_engine()
        payload = {
            "alert_id": "a-new",
            "name": "Alert",
            "description": "d",
            "severity": "high",
            "metric_name": "error_rate",
            "condition": "error_rate > 10",
            "threshold_value": 10.0,
            "workflow_id": "wf-1",
            "enabled": True,
        }
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.post("/api/analytics/alerts", json=payload)
        assert resp.status_code == 200
        assert resp.json()["data"]["alert_id"] == "a-new"
        engine.create_alert.assert_called_once()

    def test_create_alert_invalid_severity_is_500(self, client):
        engine = _analytics_engine()
        payload = {
            "alert_id": "a-bad",
            "name": "Alert",
            "description": "d",
            "severity": "bogus",
            "metric_name": "error_rate",
            "condition": "c",
            "threshold_value": 1.0,
            "workflow_id": None,
            "enabled": True,
        }
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.post("/api/analytics/alerts", json=payload)
        assert resp.status_code == 500
        engine.create_alert.assert_not_called()

    def test_update_alert_success(self, client):
        engine = _analytics_engine()
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.put(
                "/api/analytics/alerts/a-1?enabled=false&threshold_value=12.5"
            )
        assert resp.status_code == 200
        engine.update_alert.assert_called_once_with(
            alert_id="a-1", enabled=False, threshold_value=12.5
        )

    def test_delete_alert_success(self, client):
        engine = _analytics_engine()
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.delete("/api/analytics/alerts/a-1")
        assert resp.status_code == 200
        engine.delete_alert.assert_called_once_with("a-1")

    def test_realtime_feed_maps_events(self, client):
        engine = _analytics_engine()
        event = MagicMock()
        event.event_id = "ev-1"
        event.workflow_id = "wf-1"
        event.execution_id = "ex-1"
        event.event_type = "workflow_completed"
        event.timestamp = datetime.now()
        event.status = "completed"
        event.duration_ms = 42
        event.user_id = "u-1"
        engine.get_recent_events.return_value = [event]
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/realtime-feed")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["event_id"] == "ev-1"
        assert data[0]["workflow_name"] == "wf-1"
        assert data[0]["duration_ms"] == 42

    def test_workflow_performance_detail_success(self, client):
        engine = _analytics_engine()
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/workflow/wf-1/performance")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["workflow_id"] == "wf-1"
        assert data["metrics"]["success_rate"] == 95.0
        assert data["metrics"]["median_duration_ms"] == 1200.0
        assert data["metrics"]["p95_duration_ms"] == 3000.0
        assert data["metrics"]["p99_duration_ms"] == 5000.0
        assert data["metrics"]["error_rate"] == 5.0
        assert data["step_performance"] == {}
        assert data["common_errors"] == []
        assert data["user_metrics"]["unique_users"] == 10

    def test_workflow_performance_detail_not_found(self, client):
        engine = _analytics_engine()
        engine.get_performance_metrics.return_value = None
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/workflow/missing/performance")
        assert resp.status_code == 404

    def test_workflow_performance_detail_error_is_500(self, client):
        engine = _analytics_engine()
        engine.get_performance_metrics.side_effect = RuntimeError("boom")
        with patch("api.analytics_dashboard_endpoints.get_analytics_engine", return_value=engine):
            resp = client.get("/api/analytics/dashboard/workflow/wf-1/performance")
        assert resp.status_code == 500


# ============================================================================
# 2. api/protection_api.py
# ============================================================================

class TestProtectionApi:
    """Coverage for protection_api (72% -> >=95%)."""

    @pytest.fixture
    def client(self):
        from api.protection_api import router

        return make_client(
            router,
            {get_current_user: user_override(), get_db: lambda: MagicMock()},
        )

    def test_requires_auth(self):
        from api.protection_api import router

        client = make_client(router, {get_db: lambda: MagicMock()})
        assert client.get("/api/protection/churn").status_code == 401

    def test_churn_success(self, client):
        services = {"churn": MagicMock()}
        services["churn"].predict_churn_risk = AsyncMock(return_value={"risk": 0.42})
        with patch("api.protection_api.get_risk_services", return_value=services):
            resp = client.get("/api/protection/churn")
        assert resp.status_code == 200
        assert resp.json()["data"]["risk"] == 0.42

    def test_financial_success(self, client):
        services = {
            "warning": MagicMock(),
            "fraud": MagicMock(),
        }
        services["warning"].detect_ar_delays = AsyncMock(return_value=[{"days": 45}])
        services["warning"].monitor_booking_drops = AsyncMock(return_value=[{"drop": 0.1}])
        services["fraud"].detect_anomalies = AsyncMock(return_value=[{"alert": "x"}])
        with patch("api.protection_api.get_risk_services", return_value=services):
            resp = client.get("/api/protection/financial")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["ar_delays"] == [{"days": 45}]
        assert data["booking_anomaly"] == [{"drop": 0.1}]
        assert data["fraud_alerts"] == [{"alert": "x"}]

    def test_growth_success(self, client):
        services = {"growth": MagicMock()}
        services["growth"].check_scaling_readiness = AsyncMock(return_value={"ready": True})
        with patch("api.protection_api.get_risk_services", return_value=services):
            resp = client.get("/api/protection/growth")
        assert resp.status_code == 200
        assert resp.json()["data"]["ready"] is True

    def _finding(self, rule_id, severity, description="desc"):
        from atom_security.core.models import Finding

        return Finding(
            rule_id=rule_id,
            category="test",
            severity=severity,
            file_path="main.py",
            line_number=1,
            line_content="x = 1",
            description=description,
            remediation="fix it",
        )

    def test_scan_safe_without_llm(self, client):
        from atom_security.core.models import Severity

        static_cls = MagicMock()
        static_cls.return_value.scan_content.return_value = [
            self._finding("R1", Severity.LOW)
        ]
        with patch("atom_security.analyzers.static.StaticAnalyzer", static_cls):
            resp = client.post(
                "/api/protection/scan",
                json={"skill_name": "skill-a", "instruction_body": "do stuff"},
            )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["is_safe"] is True
        assert body["findings"][0]["analyzer"] == "static"
        assert body["findings"][0]["severity"] == "LOW"

    def test_scan_unsafe_with_files_and_llm(self, client):
        from atom_security.core.models import Severity

        static_cls = MagicMock()
        static_cls.return_value.scan_content.return_value = [
            self._finding("R1", Severity.LOW),
            self._finding("R2", Severity.HIGH),
        ]
        llm_cls = MagicMock()
        llm_cls.return_value.analyze = AsyncMock(return_value=[
            self._finding("R3", Severity.CRITICAL, description="llm hit")
        ])
        with patch("atom_security.analyzers.static.StaticAnalyzer", static_cls), \
                patch("atom_security.analyzers.llm.LLMAnalyzer", llm_cls), \
                patch.dict(os.environ, {
                    "ATOM_SECURITY_ENABLE_LLM_SCAN": "true",
                    "ATOM_SECURITY_LLM_MODE": "byok",
                }):
            resp = client.post(
                "/api/protection/scan",
                json={
                    "skill_name": "skill-a",
                    "instruction_body": "do stuff",
                    "file_contents": {"main.py": "print(1)"},
                },
            )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["is_safe"] is False
        assert llm_cls.called
        analyzers = {f["analyzer"] for f in body["findings"]}
        assert analyzers == {"static", "llm"}

    def test_scan_llm_analyzer_failure_is_contained(self, client):
        from atom_security.core.models import Severity

        static_cls = MagicMock()
        static_cls.return_value.scan_content.return_value = [
            self._finding("R1", Severity.LOW)
        ]
        llm_cls = MagicMock()
        llm_cls.return_value.analyze = AsyncMock(side_effect=RuntimeError("llm down"))
        with patch("atom_security.analyzers.static.StaticAnalyzer", static_cls), \
                patch("atom_security.analyzers.llm.LLMAnalyzer", llm_cls), \
                patch.dict(os.environ, {
                    "ATOM_SECURITY_ENABLE_LLM_SCAN": "true",
                }):
            resp = client.post(
                "/api/protection/scan",
                json={"skill_name": "skill-a", "instruction_body": "do stuff"},
            )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["is_safe"] is True
        assert {f["analyzer"] for f in body["findings"]} == {"static"}

    def test_churn_error_is_500(self, client):
        services = {"churn": MagicMock()}
        services["churn"].predict_churn_risk = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.protection_api.get_risk_services", return_value=services):
            resp = client.get("/api/protection/churn")
        assert resp.status_code == 500
        assert "boom" not in resp.text

    def test_financial_error_is_500(self, client):
        services = {"warning": MagicMock(), "fraud": MagicMock()}
        services["warning"].detect_ar_delays = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.protection_api.get_risk_services", return_value=services):
            resp = client.get("/api/protection/financial")
        assert resp.status_code == 500
        assert "boom" not in resp.text

    def test_growth_error_is_500(self, client):
        services = {"growth": MagicMock()}
        services["growth"].check_scaling_readiness = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("api.protection_api.get_risk_services", return_value=services):
            resp = client.get("/api/protection/growth")
        assert resp.status_code == 500
        assert "boom" not in resp.text

    def test_scan_static_analyzer_error_is_500(self, client):
        static_cls = MagicMock()
        static_cls.return_value.scan_content.side_effect = RuntimeError("boom")
        with patch("atom_security.analyzers.static.StaticAnalyzer", static_cls):
            resp = client.post(
                "/api/protection/scan",
                json={"skill_name": "skill-a", "instruction_body": "do stuff"},
            )
        assert resp.status_code == 500
        assert "boom" not in resp.text


# ============================================================================
# 3. api/operational_routes.py
# ============================================================================

class TestOperationalRoutes:
    """Full coverage for operational_routes (never tested)."""

    @pytest.fixture
    def client(self):
        from api.operational_routes import router

        return make_client(
            router,
            {get_current_user: user_override(), get_db: lambda: MagicMock()},
        )

    def test_requires_auth(self):
        from api.operational_routes import router

        client = make_client(router, {get_db: lambda: MagicMock()})
        assert client.get("/api/business-health/priorities").status_code == 401

    def test_priorities_success(self, client):
        with patch("api.operational_routes.business_health_service") as svc:
            svc.get_daily_priorities = AsyncMock(return_value=[{"id": "p1"}])
            resp = client.get("/api/business-health/priorities")
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"id": "p1"}]

    def test_priorities_error_is_500(self, client):
        with patch("api.operational_routes.business_health_service") as svc:
            svc.get_daily_priorities = AsyncMock(side_effect=RuntimeError("boom"))
            resp = client.get("/api/business-health/priorities")
        assert resp.status_code == 500

    def test_simulate_success(self, client):
        with patch("api.operational_routes.business_health_service") as svc:
            svc.simulate_decision = AsyncMock(return_value={"roi": 1.25})
            resp = client.post(
                "/api/business-health/simulate",
                json={"decision_type": "hiring", "data": {"role": "dev"}},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["roi"] == 1.25

    def test_simulate_error_is_500(self, client):
        with patch("api.operational_routes.business_health_service") as svc:
            svc.simulate_decision = AsyncMock(side_effect=RuntimeError("boom"))
            resp = client.post(
                "/api/business-health/simulate",
                json={"decision_type": "hiring", "data": {"role": "dev"}},
            )
        assert resp.status_code == 500

    def test_simulate_missing_fields_422(self, client):
        assert client.post("/api/business-health/simulate", json={}).status_code == 422
        assert client.post(
            "/api/business-health/simulate", json={"decision_type": "hiring"}
        ).status_code == 422

    def test_price_drift_success(self, client):
        with patch("core.financial_forensics.VendorIntelligenceService") as cls:
            svc = cls.return_value
            svc.detect_price_drift = AsyncMock(return_value=[{"vendor": "AWS"}])
            resp = client.get("/api/business-health/forensics/price-drift")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == [{"vendor": "AWS"}]
        assert body["metadata"]["is_mock"] is False

    def test_price_drift_error_is_500(self, client):
        with patch("core.financial_forensics.VendorIntelligenceService") as cls:
            cls.side_effect = RuntimeError("boom")
            resp = client.get("/api/business-health/forensics/price-drift")
        assert resp.status_code == 500

    def test_pricing_advisor_success(self, client):
        with patch("core.financial_forensics.PricingAdvisorService") as cls:
            svc = cls.return_value
            svc.get_pricing_recommendations = AsyncMock(return_value=[{"product": "P1"}])
            resp = client.get("/api/business-health/forensics/pricing-advisor")
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"product": "P1"}]

    def test_pricing_advisor_error_is_500(self, client):
        with patch("core.financial_forensics.PricingAdvisorService") as cls:
            cls.side_effect = RuntimeError("boom")
            resp = client.get("/api/business-health/forensics/pricing-advisor")
        assert resp.status_code == 500

    def test_subscription_waste_success(self, client):
        with patch("core.financial_forensics.SubscriptionWasteService") as cls:
            svc = cls.return_value
            svc.find_zombie_subscriptions = AsyncMock(return_value=[{"service": "zombie"}])
            resp = client.get("/api/business-health/forensics/waste")
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"service": "zombie"}]

    def test_subscription_waste_error_graceful_fallback(self, client):
        with patch("core.financial_forensics.SubscriptionWasteService") as cls:
            cls.side_effect = RuntimeError("boom")
            resp = client.get("/api/business-health/forensics/waste")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["metadata"]["is_mock"] is False

    def test_generate_interventions_success(self, client):
        with patch("api.operational_routes.CrossSystemReasoningEngine") as cls:
            engine = cls.return_value
            engine.generate_interventions = AsyncMock(return_value=[{"id": "int-1"}])
            resp = client.post("/api/business-health/interventions/generate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == [{"id": "int-1"}]
        assert body["message"] == "Interventions generated successfully"

    def test_generate_interventions_error_is_500(self, client):
        with patch("api.operational_routes.CrossSystemReasoningEngine") as cls:
            cls.side_effect = RuntimeError("boom")
            resp = client.post("/api/business-health/interventions/generate")
        assert resp.status_code == 500

    def test_execute_intervention_success(self, client):
        with patch("api.operational_routes.active_intervention_service") as svc:
            svc.execute_intervention = AsyncMock(return_value={"status": "executed"})
            resp = client.post(
                "/api/business-health/interventions/int-1/execute",
                json={"action": "approve", "payload": {"notes": "ok"}},
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "executed"

    def test_execute_intervention_error_is_500(self, client):
        with patch("api.operational_routes.active_intervention_service") as svc:
            svc.execute_intervention = AsyncMock(side_effect=RuntimeError("boom"))
            resp = client.post(
                "/api/business-health/interventions/int-1/execute",
                json={"action": "approve", "payload": {"notes": "ok"}},
            )
        assert resp.status_code == 500

    def test_execute_intervention_missing_fields_422(self, client):
        assert client.post(
            "/api/business-health/interventions/int-1/execute", json={}
        ).status_code == 422
        assert client.post(
            "/api/business-health/interventions/int-1/execute",
            json={"action": "approve"},
        ).status_code == 422


# ============================================================================
# 4. api/llm_oauth_routes.py
# ============================================================================

class TestLlmOauthRoutes:
    """Gap-fill coverage for llm_oauth_routes (95% -> 100%)."""

    @pytest.fixture
    def client(self):
        from api.llm_oauth_routes import router

        return make_client(router, {get_current_user: user_override()})

    def _state(self, provider="openai", cred_type="oauth", user_id="u-69"):
        from api.llm_oauth_routes import _build_state

        return _build_state(provider, cred_type, user_id)

    def test_connect_requires_auth(self):
        from api.llm_oauth_routes import router

        client = make_client(router)
        assert client.get("/api/v1/llm-oauth/openai/connect").status_code == 401

    def test_connect_invalid_credential_type_422(self, client):
        resp = client.get(
            "/api/v1/llm-oauth/openai/connect", params={"credential_type": "evil"}
        )
        assert resp.status_code == 422

    def test_callback_rate_limited_429(self, client):
        limiter = MagicMock()
        limiter.check.return_value = (False, 0)
        with patch("api.llm_oauth_routes._oauth_limiter", limiter):
            resp = client.get(
                "/api/v1/llm-oauth/openai/callback",
                params={"code": "c", "state": self._state()},
            )
        assert resp.status_code == 429

    def test_callback_invalid_credential_type_in_state(self, client):
        resp = client.get(
            "/api/v1/llm-oauth/openai/callback",
            params={"code": "c", "state": "llm:openai:evil:u-69:nonce:sig"},
        )
        assert resp.status_code == 400

    def test_callback_bad_signature_400(self, client):
        state = self._state()
        tampered = state[:-1] + ("a" if state[-1] != "a" else "b")
        resp = client.get(
            "/api/v1/llm-oauth/openai/callback",
            params={"code": "c", "state": tampered},
        )
        assert resp.status_code == 400

    def test_callback_http_exception_passthrough(self, client):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.exchange_code_for_tokens = AsyncMock(return_value={"access_token": "at"})
            handler.store_oauth_credentials.side_effect = HTTPException(
                status_code=409, detail="Credential conflict"
            )
            handler_cls.return_value = handler
            resp = client.get(
                "/api/v1/llm-oauth/openai/callback",
                params={"code": "c", "state": self._state()},
            )
        assert resp.status_code == 409

    def test_revoke_missing_credential_404(self, client):
        with patch("api.llm_oauth_routes.LLMCredentialService") as svc_cls:
            svc = svc_cls.return_value
            svc.revoke_oauth_credential.return_value = False
            resp = client.delete("/api/v1/llm-oauth/credentials/cred-missing")
        assert resp.status_code == 404

    def test_connect_uses_env_encryption_and_secret_keys(self, client):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.get_authorization_url.return_value = {
                "authorization_url": "https://provider/auth",
                "state": "s",
                "provider_id": "openai",
            }
            handler_cls.return_value = handler
            with patch.dict(os.environ, {
                "BYOK_ENCRYPTION_KEY": "deadbeef",
                "SECRET_KEY": "custom-secret",
            }):
                resp = client.get("/api/v1/llm-oauth/openai/connect")
        assert resp.status_code == 200
        _, kwargs = handler_cls.call_args
        assert kwargs["encryption_key"] == b"deadbeef"

    def test_connect_unknown_provider_400(self, client):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.get_authorization_url.side_effect = ValueError("Unknown provider")
            handler_cls.return_value = handler
            resp = client.get("/api/v1/llm-oauth/nope/connect")
        assert resp.status_code == 400

    def test_callback_missing_state_400(self, client):
        resp = client.get(
            "/api/v1/llm-oauth/openai/callback", params={"code": "c"}
        )
        assert resp.status_code == 400

    def test_callback_malformed_state_400(self, client):
        resp = client.get(
            "/api/v1/llm-oauth/openai/callback",
            params={"code": "c", "state": "garbage"},
        )
        assert resp.status_code == 400

    def test_callback_provider_mismatch_400(self, client):
        state = self._state(provider="anthropic")
        resp = client.get(
            "/api/v1/llm-oauth/openai/callback",
            params={"code": "c", "state": state},
        )
        assert resp.status_code == 400

    def test_callback_user_mismatch_403(self, client):
        state = self._state(user_id="someone-else")
        resp = client.get(
            "/api/v1/llm-oauth/openai/callback",
            params={"code": "c", "state": state},
        )
        assert resp.status_code == 403

    def test_callback_generic_exchange_error_500(self, client):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.exchange_code_for_tokens = AsyncMock(
                side_effect=RuntimeError("provider down")
            )
            handler_cls.return_value = handler
            resp = client.get(
                "/api/v1/llm-oauth/openai/callback",
                params={"code": "c", "state": self._state()},
            )
        assert resp.status_code == 500
        assert "provider down" not in resp.text

    def test_callback_success_oauth(self, client):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.exchange_code_for_tokens = AsyncMock(return_value={"access_token": "at"})
            cred = MagicMock()
            cred.id = "cred-1"
            handler.store_oauth_credentials.return_value = cred
            handler_cls.return_value = handler
            resp = client.get(
                "/api/v1/llm-oauth/openai/callback",
                params={"code": "c", "state": self._state()},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["credential_id"] == "cred-1"
        assert body["message"] == "Connected openai"
        _, kwargs = handler.store_oauth_credentials.call_args
        assert kwargs["credential_type"] == "oauth"

    def test_callback_success_subscription(self, client):
        with patch("api.llm_oauth_routes.LLMOAuthHandler") as handler_cls:
            handler = MagicMock()
            handler.exchange_code_for_tokens = AsyncMock(return_value={"access_token": "at"})
            cred = MagicMock()
            cred.id = "cred-2"
            handler.store_oauth_credentials.return_value = cred
            handler_cls.return_value = handler
            resp = client.get(
                "/api/v1/llm-oauth/openai/callback",
                params={"code": "c", "state": self._state(cred_type="subscription")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["credential_type"] == "subscription"
        assert "subscription" in body["message"]
        _, kwargs = handler.store_oauth_credentials.call_args
        assert kwargs["credential_type"] == "subscription"

    def test_list_credentials(self, client):
        with patch("api.llm_oauth_routes.LLMCredentialService") as svc_cls:
            svc = svc_cls.return_value
            svc.list_oauth_credentials.return_value = [{"credential_id": "cred-1"}]
            resp = client.get("/api/v1/llm-oauth/credentials")
        assert resp.status_code == 200
        assert resp.json()["data"] == [{"credential_id": "cred-1"}]
        _, kwargs = svc_cls.call_args
        assert kwargs["user_id"] == "u-69"

    def test_revoke_credential_success(self, client):
        with patch("api.llm_oauth_routes.LLMCredentialService") as svc_cls:
            svc = svc_cls.return_value
            svc.revoke_oauth_credential.return_value = True
            resp = client.delete("/api/v1/llm-oauth/credentials/cred-1")
        assert resp.status_code == 200
        svc.revoke_oauth_credential.assert_called_once_with("cred-1")

    def test_status_reports_per_provider(self, client):
        with patch("api.llm_oauth_routes.LLMCredentialService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_provider_status.return_value = {
                "provider_id": "openai",
                "has_oauth": False,
                "has_subscription": True,
                "active_method": "subscription",
            }
            resp = client.get("/api/v1/llm-oauth/status")
        assert resp.status_code == 200
        statuses = resp.json()["statuses"]
        assert set(statuses) == {"openai", "anthropic", "google", "huggingface"}
        assert svc.get_provider_status.call_count == 4
