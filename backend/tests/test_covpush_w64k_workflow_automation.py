"""Coverage-push tests for integrations.workflow_automation_routes (W64k,
TDD, 82% baseline -> target >=95%).

Covers (all standalone): GET /workflows/auth/url + /callback; POST
/test-step (minimal, analytics-tracking success + failure, outer-exception);
all 9 /enhanced/* endpoints x 503-unavailable / success / service-exception;
GET /enhanced/status; WhatsApp automation (4 workflow types + unsupported
type + per-handler ImportError); the module-level import guard + component
singleton init via importlib.reload with fake backend.python_api_service
modules.

No LLM spend, no network: the integration singletons are MagicMocks;
analytics collector is patched; whatsapp ImportError branches triggered by
sys.modules poisoning.
"""

import asyncio
import importlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations import workflow_automation_routes as w


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(w.router)
    return TestClient(app, raise_server_exceptions=False)


def _mock_intelligence():
    m = MagicMock()
    m.analyze_workflow_request.return_value = {
        "analysis": {"summary": "a"}, "detected_services": ["slack"],
        "confidence_score": 0.9, "recommendations": ["r1"],
    }
    m.generate_optimized_workflow.return_value = {
        "workflow": {"steps": []}, "optimization_suggestions": ["opt"],
        "estimated_performance": 0.9,
    }
    return m


def _mock_optimization():
    m = MagicMock()
    m.analyze_workflow_performance.return_value = {
        "analysis": {"bottlenecks": []}, "performance_metrics": {"time": 1.0},
        "optimization_opportunities": [{"type": "cache"}],
        "estimated_improvement": 0.2,
    }
    m.apply_optimizations.return_value = {
        "optimized_workflow": {"steps": []},
        "applied_optimizations": ["cache"], "performance_improvement": 0.2,
    }
    return m


def _mock_monitoring():
    m = MagicMock()
    m.start_monitoring.return_value = {"monitoring_id": "m1", "status": "started"}
    m.get_workflow_health.return_value = {
        "health_score": 0.9, "status": "healthy", "issues": [], "recommendations": [],
    }
    m.get_workflow_metrics.return_value = {
        "metrics": {"success_rate": 0.9}, "trends": {"time": "stable"}, "alerts": [],
    }
    return m


def _mock_troubleshooting():
    m = MagicMock()
    m.analyze_workflow_issues.return_value = {
        "issues": [{"type": "timeout"}], "root_causes": ["net"],
        "recommendations": ["retry"], "confidence_score": 0.8,
    }
    m.auto_resolve_issues.return_value = {
        "resolved_issues": ["x"], "remaining_issues": [],
        "resolution_status": "fully_resolved",
    }
    return m


def _patch_all(available=True, raise_all=False):
    """Patch ENHANCED_WORKFLOW_AVAILABLE + the 4 singletons."""
    intelligence, optimization = _mock_intelligence(), _mock_optimization()
    monitoring, troubleshooting = _mock_monitoring(), _mock_troubleshooting()
    if raise_all:
        for m in (intelligence, optimization, monitoring, troubleshooting):
            for method in dir(m):
                if method.startswith("_"):
                    continue
                attr = getattr(m, method)
                if isinstance(attr, MagicMock):
                    attr.side_effect = RuntimeError("boom")
    return (
        patch.multiple(
            w,
            ENHANCED_WORKFLOW_AVAILABLE=available,
            intelligence=intelligence,
            optimization=optimization,
            monitoring=monitoring,
            troubleshooting=troubleshooting,
        ),
        intelligence, optimization, monitoring, troubleshooting,
    )


class TestBasicEndpoints:
    def test_get_auth_url(self, client):
        response = client.get("/workflows/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert body["url"] == "internal://auth"
        assert "timestamp" in body

    def test_oauth_callback(self, client):
        response = client.get("/workflows/callback", params={"code": "abc"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["message"] == "Workflow auth successful"


class TestEnhancedStatus:
    def test_status_default_unavailable(self, client):
        response = client.get("/workflows/enhanced/status")
        assert response.status_code == 200
        body = response.json()
        assert body["enhanced_workflow_available"] is False
        assert body["components"] == {
            "intelligence": False, "optimization": False,
            "monitoring": False, "troubleshooting": False}
        assert len(body["endpoints"]) == 9

    def test_status_available(self, client):
        ctx = _patch_all()[0]
        with ctx:
            response = client.get("/workflows/enhanced/status")

        body = response.json()
        assert body["enhanced_workflow_available"] is True
        assert all(body["components"].values())


class TestTestStep:
    def test_step_success_minimal(self, client):
        response = client.post("/workflows/test-step", json={
            "service": "Slack", "action": "send_message"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["result"]["tested_service"] == "Slack"
        assert body["result"]["connection_status"] == "connected"
        assert body["duration_ms"] >= 0

    def test_step_with_params_normalizes_service(self, client):
        response = client.post("/workflows/test-step", json={
            "service": "Google Sheets", "action": "add_row",
            "parameters": {"row": [1, 2]}})
        body = response.json()
        assert body["success"] is True
        assert body["result"]["tested_action"] == "add_row"

    def test_step_with_analytics_success(self, client):
        collector = MagicMock()
        collector.log_step = AsyncMock()
        with patch("analytics.collector.AsyncAnalyticsCollector.get_instance",
                   return_value=collector) as get_instance:
            response = client.post("/workflows/test-step", json={
                "service": "Slack", "action": "send_message",
                "parameters": {"channel": "#x"},
                "workflow_id": "wf-1", "step_id": "step-1"})
        assert response.status_code == 200
        assert response.json()["success"] is True
        get_instance.assert_called_once()
        collector.log_step.assert_awaited_once()
        call = collector.log_step.await_args.kwargs
        assert call["workflow_id"] == "wf-1"
        assert call["step_id"] == "step-1"
        assert call["status"] == "COMPLETED"
        assert call["trigger_data"] == {"channel": "#x"}

    def test_step_analytics_failure_is_swallowed(self, client):
        collector = MagicMock()
        collector.log_step = AsyncMock(side_effect=RuntimeError("collector down"))
        with patch("analytics.collector.AsyncAnalyticsCollector.get_instance",
                   return_value=collector):
            response = client.post("/workflows/test-step", json={
                "service": "Slack", "action": "send_message",
                "parameters": {},
                "workflow_id": "wf-1", "step_id": "step-1"})
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_step_analytics_import_error_swallowed(self, client):
        with patch.dict(sys.modules, {"analytics.collector": None}):
            response = client.post("/workflows/test-step", json={
                "service": "Slack", "action": "send_message",
                "workflow_id": "wf-1", "step_id": "step-1"})
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_step_outer_exception_returns_failure(self, client):
        request = MagicMock()
        request.service.lower.side_effect = RuntimeError("no service")
        response = asyncio.run(w.test_workflow_step(request))
        assert response.success is False
        assert response.error == "no service"
        assert response.duration_ms >= 0


# ============================================================================
# 503 paths (default module state: ENHANCED_WORKFLOW_AVAILABLE=False)
# ============================================================================

class TestUnavailable503:
    def test_intelligence_analyze_503(self, client):
        response = client.post("/workflows/enhanced/intelligence/analyze", json={
            "user_input": "build a workflow"})
        assert response.status_code == 503
        assert "not available" in response.json()["detail"]

    def test_intelligence_generate_503(self, client):
        response = client.post("/workflows/enhanced/intelligence/generate", json={
            "user_input": "build a workflow"})
        assert response.status_code == 503

    def test_optimization_analyze_503(self, client):
        response = client.post("/workflows/enhanced/optimization/analyze", json={
            "workflow": {"steps": []}})
        assert response.status_code == 503

    def test_optimization_apply_503(self, client):
        response = client.post("/workflows/enhanced/optimization/apply", json={
            "workflow": {"steps": []}, "optimizations": []})
        assert response.status_code == 503

    def test_monitoring_start_503(self, client):
        response = client.post("/workflows/enhanced/monitoring/start", json={
            "workflow_id": "wf-1"})
        assert response.status_code == 503

    def test_monitoring_health_503(self, client):
        response = client.get("/workflows/enhanced/monitoring/health",
                              params={"workflow_id": "wf-1"})
        assert response.status_code == 503

    def test_monitoring_metrics_503(self, client):
        response = client.get("/workflows/enhanced/monitoring/metrics",
                              params={"workflow_id": "wf-1", "metric_type": "perf"})
        assert response.status_code == 503

    def test_troubleshooting_analyze_503(self, client):
        response = client.post("/workflows/enhanced/troubleshooting/analyze", json={
            "workflow_id": "wf-1", "error_logs": ["err"]})
        assert response.status_code == 503

    def test_troubleshooting_resolve_503(self, client):
        response = client.post("/workflows/enhanced/troubleshooting/resolve", json={
            "workflow_id": "wf-1", "issues": [{"type": "timeout"}]})
        assert response.status_code == 503


# ============================================================================
# Enhanced endpoints: success + service-exception (available=True)
# ============================================================================

class TestEnhancedIntelligence:
    def test_analyze_success(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.post("/workflows/enhanced/intelligence/analyze", json={
                "user_input": "u", "context": {"project": "X"},
                "enhanced_intelligence": True})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["analysis"] == {"summary": "a"}
        assert body["detected_services"] == ["slack"]
        assert body["confidence_score"] == 0.9
        assert body["recommendations"] == ["r1"]
        intelligence.analyze_workflow_request.assert_called_once_with(
            "u", {"project": "X"})

    def test_analyze_no_context_defaults_empty(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.post("/workflows/enhanced/intelligence/analyze", json={
                "user_input": "u"})
        assert response.json()["success"] is True
        assert intelligence.analyze_workflow_request.call_args[0][1] == {}

    def test_analyze_exception(self, client):
        ctx = _patch_all(raise_all=True)[0]
        with ctx:
            response = client.post("/workflows/enhanced/intelligence/analyze", json={
                "user_input": "u"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "Enhanced intelligence analysis failed: boom"

    def test_generate_success(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.post("/workflows/enhanced/intelligence/generate", json={
                "user_input": "u", "context": {"c": 1},
                "optimization_strategy": "cost", "enhanced_intelligence": True})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["workflow"] == {"steps": []}
        assert body["optimization_suggestions"] == ["opt"]
        assert body["estimated_performance"] == 0.9
        intelligence.generate_optimized_workflow.assert_called_once_with(
            "u", {"c": 1}, "cost")

    def test_generate_exception(self, client):
        ctx = _patch_all(raise_all=True)[0]
        with ctx:
            response = client.post("/workflows/enhanced/intelligence/generate", json={
                "user_input": "u"})
        assert response.json()["success"] is False
        assert "generation failed" in response.json()["error"]


class TestEnhancedOptimization:
    def test_analyze_success(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.post("/workflows/enhanced/optimization/analyze", json={
                "workflow": {"steps": []}, "strategy": "reliability"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["performance_metrics"] == {"time": 1.0}
        assert body["optimization_opportunities"] == [{"type": "cache"}]
        assert body["estimated_improvement"] == 0.2
        optimization.analyze_workflow_performance.assert_called_once_with(
            {"steps": []}, "reliability")

    def test_analyze_exception(self, client):
        ctx = _patch_all(raise_all=True)[0]
        with ctx:
            response = client.post("/workflows/enhanced/optimization/analyze", json={
                "workflow": {"steps": []}})
        assert response.status_code == 200
        assert response.json()["success"] is False
        assert "analysis failed" in response.json()["error"]

    def test_apply_success(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.post("/workflows/enhanced/optimization/apply", json={
                "workflow": {"steps": []},
                "optimizations": [{"type": "cache"}]})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["optimized_workflow"] == {"steps": []}
        assert body["applied_optimizations"] == ["cache"]
        assert body["performance_improvement"] == 0.2
        optimization.apply_optimizations.assert_called_once_with(
            {"steps": []}, [{"type": "cache"}])

    def test_apply_exception(self, client):
        ctx = _patch_all(raise_all=True)[0]
        with ctx:
            response = client.post("/workflows/enhanced/optimization/apply", json={
                "workflow": {"steps": []}, "optimizations": []})
        assert response.json()["success"] is False
        assert "application failed" in response.json()["error"]


class TestEnhancedMonitoring:
    def test_start_success(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.post("/workflows/enhanced/monitoring/start", json={
                "workflow_id": "wf-1"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["monitoring_id"] == "m1"
        assert body["status"] == "started"
        monitoring.start_monitoring.assert_called_once_with("wf-1")

    def test_start_exception(self, client):
        ctx = _patch_all(raise_all=True)[0]
        with ctx:
            response = client.post("/workflows/enhanced/monitoring/start", json={
                "workflow_id": "wf-1"})
        assert response.json()["success"] is False
        assert "start failed" in response.json()["error"]

    def test_health_success(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.get("/workflows/enhanced/monitoring/health",
                                  params={"workflow_id": "wf-1"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["health_score"] == 0.9
        assert body["status"] == "healthy"
        assert body["issues"] == []
        assert body["recommendations"] == []
        monitoring.get_workflow_health.assert_called_once_with("wf-1")

    def test_health_exception(self, client):
        ctx = _patch_all(raise_all=True)[0]
        with ctx:
            response = client.get("/workflows/enhanced/monitoring/health",
                                  params={"workflow_id": "wf-1"})
        assert response.json()["success"] is False
        assert "health check failed" in response.json()["error"]

    def test_metrics_success(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.get("/workflows/enhanced/monitoring/metrics",
                                  params={"workflow_id": "wf-1", "metric_type": "perf"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["metrics"] == {"success_rate": 0.9}
        assert body["trends"] == {"time": "stable"}
        assert body["alerts"] == []
        monitoring.get_workflow_metrics.assert_called_once_with("wf-1", "perf")

    def test_metrics_default_metric_type(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.get("/workflows/enhanced/monitoring/metrics",
                                  params={"workflow_id": "wf-1"})
        assert response.json()["success"] is True
        assert monitoring.get_workflow_metrics.call_args[0][1] == "all"

    def test_metrics_exception(self, client):
        ctx = _patch_all(raise_all=True)[0]
        with ctx:
            response = client.get("/workflows/enhanced/monitoring/metrics",
                                  params={"workflow_id": "wf-1"})
        assert response.json()["success"] is False
        assert "metrics retrieval failed" in response.json()["error"]


class TestEnhancedTroubleshooting:
    def test_analyze_success(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.post("/workflows/enhanced/troubleshooting/analyze", json={
                "workflow_id": "wf-1", "error_logs": ["log1"]})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["issues"] == [{"type": "timeout"}]
        assert body["root_causes"] == ["net"]
        assert body["recommendations"] == ["retry"]
        assert body["confidence_score"] == 0.8
        troubleshooting.analyze_workflow_issues.assert_called_once_with(
            "wf-1", ["log1"])

    def test_analyze_exception(self, client):
        ctx = _patch_all(raise_all=True)[0]
        with ctx:
            response = client.post("/workflows/enhanced/troubleshooting/analyze", json={
                "workflow_id": "wf-1"})
        assert response.json()["success"] is False
        assert "analysis failed" in response.json()["error"]

    def test_resolve_success(self, client):
        ctx, intelligence, optimization, monitoring, troubleshooting = _patch_all()

        with ctx:
            response = client.post("/workflows/enhanced/troubleshooting/resolve", json={
                "workflow_id": "wf-1", "issues": [{"type": "timeout"}]})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["resolved_issues"] == ["x"]
        assert body["remaining_issues"] == []
        assert body["resolution_status"] == "fully_resolved"
        troubleshooting.auto_resolve_issues.assert_called_once_with(
            "wf-1", [{"type": "timeout"}])

    def test_resolve_exception(self, client):
        ctx = _patch_all(raise_all=True)[0]
        with ctx:
            response = client.post("/workflows/enhanced/troubleshooting/resolve", json={
                "workflow_id": "wf-1", "issues": []})
        assert response.json()["success"] is False
        assert "resolution failed" in response.json()["error"]


# ============================================================================
# WhatsApp workflow automation
# ============================================================================

class TestWhatsAppAutomation:
    def test_customer_support(self, client):
        response = client.post("/workflows/whatsapp/automate", json={
            "type": "customer_support",
            "parameters": {"trigger_keywords": ["help"],
                           "auto_response": "Hi",
                           "escalate_conditions": ["urgent"]}})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["workflow_type"] == "customer_support"
        result = body["result"]
        assert result["status"] == "configured"
        assert result["trigger_keywords"] == ["help"]
        assert result["escalation_rules"] == 1

    def test_customer_support_defaults(self, client):
        response = client.post("/workflows/whatsapp/automate", json={
            "type": "customer_support"})
        result = response.json()["result"]
        assert result["trigger_keywords"] == ["help", "support", "issue"]
        assert result["auto_response_enabled"] is True
        assert result["escalation_rules"] == 2
        assert result["integration_points"] == ["whatsapp", "support_tickets", "notifications"]

    def test_appointment_reminder(self, client):
        response = client.post("/workflows/whatsapp/automate", json={
            "type": "appointment_reminder",
            "parameters": {"reminder_intervals": [1, 2],
                           "template_name": "reminder_v2"}})
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["status"] == "configured"
        assert result["reminder_intervals"] == [1, 2]
        assert result["template"] == "reminder_v2"

    def test_appointment_reminder_defaults(self, client):
        response = client.post("/workflows/whatsapp/automate", json={
            "type": "appointment_reminder"})
        result = response.json()["result"]
        assert result["reminder_intervals"] == [24, 2, 0.5]

    def test_marketing_campaign(self, client):
        response = client.post("/workflows/whatsapp/automate", json={
            "type": "marketing_campaign",
            "parameters": {"campaign_type": "sale",
                           "target_audience": "vip",
                           "message_template": "flash_sale"}})
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["status"] == "configured"
        assert result["campaign_type"] == "sale"
        assert result["target_audience"] == "vip"
        assert result["template"] == "flash_sale"

    def test_follow_up_sequence(self, client):
        response = client.post("/workflows/whatsapp/automate", json={
            "type": "follow_up_sequence",
            "parameters": {"follow_up_delays": [1, 2],
                           "follow_up_templates": ["t1", "t2"]}})
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["status"] == "configured"
        assert result["follow_up_schedule"] == [1, 2]
        assert result["templates"] == ["t1", "t2"]

    def test_unsupported_type(self, client):
        response = client.post("/workflows/whatsapp/automate", json={
            "type": "bogus"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert "Unsupported workflow type" in body["error"]

    @pytest.mark.parametrize("workflow_type,handler", [
        ("customer_support", "_handle_customer_support_automation"),
        ("appointment_reminder", "_handle_appointment_reminder_automation"),
        ("marketing_campaign", "_handle_marketing_campaign_automation"),
        ("follow_up_sequence", "_handle_follow_up_automation"),
    ])
    def test_handler_import_error_branch(self, client, workflow_type, handler):
        """WhatsApp integration missing -> handler returns unavailable."""
        with patch.dict(sys.modules,
                        {"integrations.whatsapp_business_integration": None}):
            result = asyncio.run(getattr(w, handler)({}))
        assert result == {"status": "unavailable",
                          "reason": "WhatsApp integration not found"}


# ============================================================================
# Import guard + singleton init branches (via reload with fake modules)
# ============================================================================

class TestImportGuardReload:
    def test_enhanced_available_true_branch(self):
        """Reload with fake backend.python_api_service modules installed.

        Covers the import-success branch (ENHANCED_WORKFLOW_AVAILABLE=True)
        and the 4 singleton initializations.
        """
        fake_pkg = types.ModuleType("backend.python_api_service")
        fake_pkg.__path__ = []
        fake_enh = types.ModuleType("backend.python_api_service.enhanced_workflow")
        fake_enh.__path__ = []
        sys.modules["backend.python_api_service"] = fake_pkg
        sys.modules["backend.python_api_service.enhanced_workflow"] = fake_enh

        classes = {}
        for name, cls_name in [
            ("workflow_intelligence_integration", "WorkflowIntelligenceIntegration"),
            ("workflow_monitoring_integration", "WorkflowMonitoringIntegration"),
            ("workflow_optimization_integration", "WorkflowOptimizationIntegration"),
            ("workflow_troubleshooting_integration", "WorkflowTroubleshootingIntegration"),
        ]:
            mod = types.ModuleType(
                f"backend.python_api_service.enhanced_workflow.{name}")
            cls = type(cls_name, (), {})
            setattr(mod, cls_name, cls)
            classes[cls_name] = cls
            sys.modules[
                "backend.python_api_service.enhanced_workflow." + name] = mod

        try:
            reloaded = importlib.reload(w)
            assert reloaded.ENHANCED_WORKFLOW_AVAILABLE is True
            assert isinstance(reloaded.intelligence, classes["WorkflowIntelligenceIntegration"])
            assert isinstance(reloaded.optimization, classes["WorkflowOptimizationIntegration"])
            assert isinstance(reloaded.monitoring, classes["WorkflowMonitoringIntegration"])
            assert isinstance(reloaded.troubleshooting, classes["WorkflowTroubleshootingIntegration"])

            reloaded.intelligence.analyze_workflow_request = MagicMock(
                return_value={"analysis": {"a": 1}, "detected_services": [],
                              "confidence_score": 0.5, "recommendations": []})
            app = FastAPI()
            app.include_router(reloaded.router)
            c = TestClient(app)
            response = c.post("/workflows/enhanced/intelligence/analyze", json={
                "user_input": "u"})
            assert response.status_code == 200
            assert response.json()["success"] is True
            assert response.json()["analysis"] == {"a": 1}
        finally:
            for key in list(sys.modules):
                if key.startswith("backend.python_api_service"):
                    del sys.modules[key]
            importlib.reload(w)
            assert w.ENHANCED_WORKFLOW_AVAILABLE is False
