# -*- coding: utf-8 -*-
"""Coverage wave 95 — integrations/whatsapp_production_test (WhatsAppProductionTester).

Standalone, fully mocked (requests.* + runpy __main__), zero network, zero LLM.

Covers: __init__ (default + custom base_url), test_api_endpoints (GET/POST mix,
json vs text content-type, success/failure tally, per-endpoint exception →
'error' status), test_message_capabilities (text + template success and
exception paths), test_configuration_status (health demo/production, config
profile present/absent, exception paths), test_search_and_analytics (search
results present/absent, export json/non-json, exceptions), run_comprehensive_test
(PASS/FAIL bands, duration, recommendations + production readiness wiring),
_generate_recommendations (per-suite texts, demo-mode, security defaults, top-5
cap), _assess_production_readiness (all 4 levels, demo penalty, critical-failure
penalty, score clamping), run_production_test success + error report write, and
the `if __name__ == '__main__'` block via exec.
"""
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

import pytest

from integrations.whatsapp_production_test import WhatsAppProductionTester


def _resp(status=200, payload=None, content_type="application/json", text="{}"):
    r = MagicMock()
    r.status_code = status
    r.headers = {"content-type": content_type}
    r.text = text or "{}"
    r.json.return_value = payload if payload is not None else {}
    r.elapsed = SimpleNamespace(total_seconds=lambda: 0.25)
    return r


@pytest.fixture()
def req():
    with patch("integrations.whatsapp_production_test.requests.get",
               return_value=_resp()) as g, \
         patch("integrations.whatsapp_production_test.requests.post",
               return_value=_resp(201)) as p:
        g.side_effect = None
        p.side_effect = None
        yield SimpleNamespace(get=g, post=p)


# ============================================================================
# __init__
# ============================================================================

class TestInit:
    def test_default_base_url(self):
        svc = WhatsAppProductionTester()
        assert svc.base_url == "http://127.0.0.1:5058"
        assert svc.test_results == []
        assert isinstance(svc.start_time, datetime)

    def test_custom_base_url(self):
        svc = WhatsAppProductionTester(base_url="http://localhost:9999")
        assert svc.base_url == "http://localhost:9999"


# ============================================================================
# test_api_endpoints
# ============================================================================

class TestApiEndpoints:
    def test_all_success(self, req):
        svc = WhatsAppProductionTester()
        summary = svc.test_api_endpoints()
        assert summary["test_name"] == "API Endpoints"
        assert summary["total_tests"] == 9
        assert summary["successful_tests"] == 9
        assert summary["success_rate"] == 100.0
        assert len(summary["results"]) == 9
        assert req.get.call_count == 8
        assert req.post.call_count == 1

    def test_post_uses_json_body(self, req):
        svc = WhatsAppProductionTester()
        svc.test_api_endpoints()
        req.post.assert_called_once_with(
            "http://127.0.0.1:5058/api/whatsapp/service/initialize",
            json={}, timeout=10)

    def test_get_passed_timeout(self, req):
        svc = WhatsAppProductionTester()
        svc.test_api_endpoints()
        assert all(
            c.kwargs.get("timeout") == 10
            for c in req.get.call_args_list
        )

    def test_mixed_success_failure(self, req):
        resp = _resp()
        req.get.side_effect = [_resp(200), _resp(503), _resp(200)] + [_resp(200)] * 5
        svc = WhatsAppProductionTester()
        summary = svc.test_api_endpoints()
        assert summary["successful_tests"] == 8
        assert summary["success_rate"] == 8 / 9 * 100
        failed = [r for r in summary["results"] if not r["success"]]
        assert len(failed) == 1
        assert failed[0]["status_code"] == 503

    def test_json_content_type_branch(self, req):
        req.get.return_value = _resp(200, payload={"status": "ok"}, content_type="application/json")
        svc = WhatsAppProductionTester()
        summary = svc.test_api_endpoints()
        assert summary["results"][0]["response"] == {"status": "ok"}

    def test_text_content_type_branch(self, req):
        req.get.return_value = _resp(200, payload=None, content_type="text/html", text="<html>hi</html>")
        svc = WhatsAppProductionTester()
        summary = svc.test_api_endpoints()
        assert summary["results"][0]["response"] == "<html>hi</html>"

    def test_failure_prints_error_from_body(self, req):
        req.get.return_value = _resp(500, payload={"error": "bad thing"})
        svc = WhatsAppProductionTester()
        summary = svc.test_api_endpoints()
        failed = [r for r in summary["results"] if not r["success"]]
        assert len(failed) == 8

    def test_endpoint_exception_marks_error(self, req):
        def _boom(*a, **k):
            raise ConnectionError("refused")
        req.get.side_effect = _boom
        req.post.side_effect = _boom
        svc = WhatsAppProductionTester()
        summary = svc.test_api_endpoints()
        assert all(r["status_code"] == "error" and not r["success"] for r in summary["results"])
        assert summary["successful_tests"] == 0
        assert summary["success_rate"] == 0.0


# ============================================================================
# test_message_capabilities
# ============================================================================

class TestMessageCapabilities:
    def test_both_success(self, req):
        svc = WhatsAppProductionTester()
        summary = svc.test_message_capabilities()
        assert summary["total_tests"] == 2
        assert summary["successful_tests"] == 2
        assert summary["success_rate"] == 100.0
        assert summary["results"]["text_message"]["success"] is True
        assert summary["results"]["template_message"]["success"] is True
        req.post.call_count == 2

    def test_text_failure(self, req):
        req.post.side_effect = [_resp(400), _resp(201)]
        svc = WhatsAppProductionTester()
        summary = svc.test_message_capabilities()
        assert summary["results"]["text_message"]["success"] is False
        assert summary["results"]["template_message"]["success"] is True
        assert summary["successful_tests"] == 1

    def test_template_failure(self, req):
        req.post.side_effect = [_resp(201), _resp(500)]
        svc = WhatsAppProductionTester()
        summary = svc.test_message_capabilities()
        assert summary["results"]["text_message"]["success"] is True
        assert summary["results"]["template_message"]["success"] is False

    def test_text_raises(self, req):
        def _boom(*a, **k):
            raise ConnectionError("down")
        req.post.side_effect = _boom
        svc = WhatsAppProductionTester()
        summary = svc.test_message_capabilities()
        assert summary["results"]["text_message"]["success"] is False
        assert "error" in summary["results"]["text_message"]

    def test_template_raises(self, req):
        def _boom(*a, **k):
            raise ConnectionError("down")
        req.post.side_effect = [_resp(201), _boom]
        svc = WhatsAppProductionTester()
        summary = svc.test_message_capabilities()
        assert summary["results"]["text_message"]["success"] is True
        assert summary["results"]["template_message"]["success"] is False
        assert "error" in summary["results"]["template_message"]

    def test_both_raise(self, req):
        def _boom(*a, **k):
            raise TimeoutError("slow")
        req.post.side_effect = _boom
        svc = WhatsAppProductionTester()
        summary = svc.test_message_capabilities()
        assert summary["successful_tests"] == 0
        assert summary["success_rate"] == 0.0


# ============================================================================
# test_configuration_status
# ============================================================================

class TestConfigurationStatus:
    def test_healthy_production_configured(self, req):
        req.get.side_effect = [
            _resp(200, payload={"status": "healthy", "configuration_type": "production",
                                "is_demo": False, "uptime_percentage": 99.9}),
            _resp(200, payload={"business_profile": {"name": "ACME", "phone": "+1"}}),
        ]
        svc = WhatsAppProductionTester()
        summary = svc.test_configuration_status()
        assert summary["total_tests"] == 2
        assert summary["successful_tests"] == 2
        health = summary["results"][0]
        assert health["status"] == "healthy"
        assert health["is_demo"] is False
        cfg = summary["results"][1]
        assert cfg["has_business_profile"] is True
        assert cfg["profile_fields"] == ["name", "phone"]

    def test_demo_mode(self, req):
        req.get.side_effect = [
            _resp(200, payload={"status": "ok", "configuration_type": "demo",
                                "is_demo": True, "uptime_percentage": 50}),
            _resp(200, payload={"business_profile": {}}),
        ]
        svc = WhatsAppProductionTester()
        summary = svc.test_configuration_status()
        assert summary["results"][0]["is_demo"] is True
        assert summary["results"][1]["has_business_profile"] is False

    def test_health_failure_status(self, req):
        req.get.side_effect = [
            _resp(503, payload={"status": "degraded", "configuration_type": "production",
                                "is_demo": False, "uptime_percentage": 10}),
            _resp(200, payload={"business_profile": {"name": "ACME"}}),
        ]
        svc = WhatsAppProductionTester()
        summary = svc.test_configuration_status()
        assert summary["results"][0]["success"] is False
        assert summary["successful_tests"] == 1

    def test_health_raises(self, req):
        def _boom(*a, **k):
            raise ConnectionError("down")
        req.get.side_effect = _boom
        svc = WhatsAppProductionTester()
        summary = svc.test_configuration_status()
        assert summary["results"][0]["success"] is False
        assert "error" in summary["results"][0]

    def test_config_raises(self, req):
        def _boom(*a, **k):
            raise TimeoutError("slow")
        req.get.side_effect = [_resp(200, payload={"status": "ok", "configuration_type": "prod",
                                                   "is_demo": False, "uptime_percentage": 1}), _boom]
        svc = WhatsAppProductionTester()
        summary = svc.test_configuration_status()
        assert summary["results"][1]["success"] is False
        assert "error" in summary["results"][1]
        assert summary["successful_tests"] == 1

    def test_non_json_config_response(self, req):
        req.get.side_effect = [
            _resp(200, payload={"status": "ok", "configuration_type": "prod",
                                "is_demo": False, "uptime_percentage": 1}),
            _resp(200, payload=None, content_type="text/html", text="oops"),
        ]
        svc = WhatsAppProductionTester()
        summary = svc.test_configuration_status()
        assert summary["results"][1]["has_business_profile"] is False
        assert summary["results"][1]["profile_fields"] == []


# ============================================================================
# test_search_and_analytics
# ============================================================================

class TestSearchAndAnalytics:
    def test_both_success(self, req):
        req.get.side_effect = [
            _resp(200, payload={"conversations": [{"id": 1}]}),
            _resp(200, payload={"data": []}, content_type="application/json"),
        ]
        svc = WhatsAppProductionTester()
        summary = svc.test_search_and_analytics()
        assert summary["total_tests"] == 2
        assert summary["successful_tests"] == 2
        assert summary["results"][0]["has_results"] is True
        assert summary["results"][1]["is_json"] is True

    def test_search_params(self, req):
        svc = WhatsAppProductionTester()
        svc.test_search_and_analytics()
        assert req.get.call_args_list[0].kwargs == {
            "params": {"query": "test", "limit": 10, "offset": 0}, "timeout": 10}
        assert req.get.call_args_list[1].kwargs["params"] == {
            "format": "json", "start_date": "2024-01-01", "end_date": "2024-12-31"}

    def test_search_no_results_key(self, req):
        req.get.side_effect = [
            _resp(200, payload={"other": 1}),
            _resp(200, payload={}, content_type="application/json"),
        ]
        svc = WhatsAppProductionTester()
        summary = svc.test_search_and_analytics()
        assert summary["results"][0]["has_results"] is False
        assert summary["results"][0]["success"] is True

    def test_export_non_json(self, req):
        req.get.side_effect = [
            _resp(200, payload={"conversations": []}),
            _resp(200, payload=None, content_type="text/csv", text="a,b"),
        ]
        svc = WhatsAppProductionTester()
        summary = svc.test_search_and_analytics()
        assert summary["results"][1]["is_json"] is False
        assert summary["results"][1]["success"] is True

    def test_search_raises(self, req):
        def _boom(*a, **k):
            raise ConnectionError("down")
        req.get.side_effect = [_boom, _resp(200, payload={}, content_type="application/json")]
        svc = WhatsAppProductionTester()
        summary = svc.test_search_and_analytics()
        assert summary["results"][0]["success"] is False
        assert "error" in summary["results"][0]
        assert summary["successful_tests"] == 1

    def test_export_raises(self, req):
        def _boom(*a, **k):
            raise TimeoutError("slow")
        req.get.side_effect = [_resp(200, payload={"conversations": []}), _boom]
        svc = WhatsAppProductionTester()
        summary = svc.test_search_and_analytics()
        assert summary["results"][1]["success"] is False
        assert summary["results"][1]["test"] == "Analytics Export"

    def test_both_raise(self, req):
        def _boom(*a, **k):
            raise ConnectionError("down")
        req.get.side_effect = _boom
        svc = WhatsAppProductionTester()
        summary = svc.test_search_and_analytics()
        assert summary["successful_tests"] == 0
        assert summary["success_rate"] == 0.0


# ============================================================================
# run_comprehensive_test / _generate_recommendations / _assess_production_readiness
# ============================================================================

class TestRunComprehensive:
    def _suite_result(self, name, rate, tests=4):
        return {"test_name": name, "total_tests": tests,
                "successful_tests": int(tests * rate / 100), "success_rate": rate, "results": []}

    def test_pass_status(self):
        svc = WhatsAppProductionTester()
        with patch.object(svc, "test_api_endpoints",
                          return_value=self._suite_result("API Endpoints", 100)) as m1, \
             patch.object(svc, "test_message_capabilities",
                          return_value=self._suite_result("Message Capabilities", 100)) as m2, \
             patch.object(svc, "test_configuration_status",
                          return_value=self._suite_result("Configuration Status", 100)) as m3, \
             patch.object(svc, "test_search_and_analytics",
                          return_value=self._suite_result("Search and Analytics", 100)) as m4:
            report = svc.run_comprehensive_test()
        m1.assert_called_once()
        m2.assert_called_once()
        m3.assert_called_once()
        m4.assert_called_once()
        assert report["overall_summary"]["total_test_suites"] == 4
        assert report["overall_summary"]["total_tests"] == 16
        assert report["overall_summary"]["successful_tests"] == 16
        assert report["overall_summary"]["failed_tests"] == 0
        assert report["overall_summary"]["overall_success_rate"] == 100.0
        assert report["overall_summary"]["status"] == "PASS"
        assert report["duration_seconds"] >= 0
        assert "start_time" in report and "end_time" in report
        assert "recommendations" in report and "production_readiness" in report
        assert len(report["test_results"]) == 4

    def test_fail_status_below_80(self):
        svc = WhatsAppProductionTester()
        with patch.object(svc, "test_api_endpoints",
                          return_value=self._suite_result("API Endpoints", 50)), \
             patch.object(svc, "test_message_capabilities",
                          return_value=self._suite_result("Message Capabilities", 50)), \
             patch.object(svc, "test_configuration_status",
                          return_value=self._suite_result("Configuration Status", 50)), \
             patch.object(svc, "test_search_and_analytics",
                          return_value=self._suite_result("Search and Analytics", 50)):
            report = svc.run_comprehensive_test()
        assert report["overall_summary"]["overall_success_rate"] == 50.0
        assert report["overall_summary"]["status"] == "FAIL"
        assert report["overall_summary"]["failed_tests"] == 8


class TestRecommendations:
    def _result(self, name, rate, results=None):
        return {"test_name": name, "total_tests": 1, "successful_tests": 1,
                "success_rate": rate, "results": results or []}

    def test_all_recommendation_texts(self):
        svc = WhatsAppProductionTester()
        results = [
            self._result("API Endpoints", 50),
            self._result("Message Capabilities", 50),
            self._result("Configuration Status", 50),
            self._result("Search and Analytics", 50),
        ]
        recs = svc._generate_recommendations(results)
        assert any("API endpoints" in r for r in recs)
        assert any("credentials and permissions" in r for r in recs)
        assert any("environment variables and database" in r for r in recs)
        assert any("database connectivity and data models" in r for r in recs)
        assert len(recs) == 5  # top-5 cap (4 suite texts + 1 security default)

    def test_security_defaults_when_all_pass(self):
        svc = WhatsAppProductionTester()
        results = [
            self._result("API Endpoints", 100),
            self._result("Message Capabilities", 100),
            self._result("Configuration Status", 100),
            self._result("Search and Analytics", 100),
        ]
        recs = svc._generate_recommendations(results)
        assert len(recs) == 3
        assert any("webhook signature verification" in r for r in recs)
        assert any("monitoring and alerting" in r for r in recs)
        assert any("database backups" in r for r in recs)

    def test_demo_mode_recommendation(self):
        svc = WhatsAppProductionTester()
        results = [
            self._result("Configuration Status", 100,
                         results=[{"is_demo": True}]),
            self._result("API Endpoints", 100),
        ]
        recs = svc._generate_recommendations(results)
        assert any("exit demo mode" in r for r in recs)

    def test_demo_not_flagged(self):
        svc = WhatsAppProductionTester()
        results = [
            self._result("Configuration Status", 100, results=[{"is_demo": False}]),
            self._result("API Endpoints", 100),
        ]
        recs = svc._generate_recommendations(results)
        assert not any("exit demo mode" in r for r in recs)

    def test_top_five_cap(self):
        svc = WhatsAppProductionTester()
        results = [self._result(n, 0) for n in
                   ["API Endpoints", "Message Capabilities", "Configuration Status", "Search and Analytics"]]
        results += [self._result("Extra", 0)]
        recs = svc._generate_recommendations(results)
        assert len(recs) == 5


class TestReadiness:
    def _result(self, name, rate, results=None):
        return {"test_name": name, "total_tests": 1, "successful_tests": 1,
                "success_rate": rate, "results": results or []}

    def test_excellent(self):
        svc = WhatsAppProductionTester()
        r = svc._assess_production_readiness([self._result("API Endpoints", 95)], 95)
        assert r["status"] == "PRODUCTION_READY"
        assert r["level"].startswith("EXCELLENT")
        assert r["score"] == 95
        assert r["is_demo_mode"] is False
        assert r["critical_failures"] == 0

    def test_mostly_ready(self):
        svc = WhatsAppProductionTester()
        r = svc._assess_production_readiness([self._result("API Endpoints", 85)], 85)
        assert r["status"] == "MOSTLY_READY"
        assert r["score"] == 85

    def test_needs_work(self):
        svc = WhatsAppProductionTester()
        r = svc._assess_production_readiness([self._result("API Endpoints", 65)], 65)
        assert r["status"] == "NEEDS_WORK"
        assert r["score"] == 65

    def test_not_ready(self):
        svc = WhatsAppProductionTester()
        r = svc._assess_production_readiness([self._result("API Endpoints", 55)], 55)
        assert r["status"] == "NOT_READY"
        assert r["score"] == 55

    def test_demo_penalty(self):
        svc = WhatsAppProductionTester()
        results = [self._result("Configuration Status", 100, results=[{"is_demo": True}])]
        r = svc._assess_production_readiness(results, 100)
        assert r["is_demo_mode"] is True
        assert r["score"] == 80

    def test_critical_failure_penalty(self):
        svc = WhatsAppProductionTester()
        results = [self._result("API Endpoints", 40)]
        r = svc._assess_production_readiness(results, 40)
        assert r["critical_failures"] == 1
        assert r["score"] == 30

    def test_multiple_critical_and_demo(self):
        svc = WhatsAppProductionTester()
        results = [
            self._result("API Endpoints", 10),
            self._result("Message Capabilities", 20),
            self._result("Configuration Status", 100, results=[{"is_demo": True}]),
        ]
        r = svc._assess_production_readiness(results, 30)
        assert r["critical_failures"] == 2
        assert r["score"] == 0  # 30 - 20 - 20 clamped to 0

    def test_score_clamps_high(self):
        svc = WhatsAppProductionTester()
        r = svc._assess_production_readiness([], 120)
        assert r["score"] == 100

    def test_no_results_score_floor(self):
        svc = WhatsAppProductionTester()
        r = svc._assess_production_readiness([self._result("API Endpoints", 1)], -5)
        assert r["score"] == 0
        assert r["status"] == "NOT_READY"


# ============================================================================
# run_production_test (module function)
# ============================================================================

class TestRunProductionTest:
    def test_success_path(self):
        report = {"overall_summary": {"status": "PASS"}}
        with patch("integrations.whatsapp_production_test.WhatsAppProductionTester") as cls, \
             patch("builtins.open", mock_open()) as m:
            inst = cls.return_value
            inst.run_comprehensive_test.return_value = report
            out = __import__("integrations.whatsapp_production_test",
                             fromlist=["run_production_test"]).run_production_test()
        assert out == report
        m.assert_called_once()
        handle = m()
        payload = "".join(c.args[0] for c in handle.write.call_args_list)
        assert json.loads(payload) == report

    def test_error_path(self):
        with patch("integrations.whatsapp_production_test.WhatsAppProductionTester") as cls, \
             patch("builtins.open", mock_open()) as m:
            inst = cls.return_value
            inst.run_comprehensive_test.side_effect = RuntimeError("suite crashed")
            out = __import__("integrations.whatsapp_production_test",
                             fromlist=["run_production_test"]).run_production_test()
        assert "error" in out
        assert out["error"] == "suite crashed"
        assert m.call_count == 1
        path = m.call_args[0][0]
        assert path.endswith("whatsapp_production_test_error.json")


class TestMainBlock:
    def test_main_block_executes(self):
        fake_requests = MagicMock()
        fake_requests.get.return_value = _resp(200)
        fake_requests.post.return_value = _resp(201)
        with patch.dict("sys.modules", {"requests": fake_requests}), \
             patch("builtins.open", mock_open()):
            import runpy
            runpy.run_path("integrations/whatsapp_production_test.py", run_name="__main__")
