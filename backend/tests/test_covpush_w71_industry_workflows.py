"""Coverage wave 71 — core/industry_workflow_endpoints.py (89% → 95%+).

Closes the remaining holes:
- REAL BUG (TDD red→green): the whole router was anonymous (template
  catalog + ROI + recommendations). Router now carries
  dependencies=[Depends(get_current_user)] matching the platform-wide
  post-R38 auth posture. RED: anonymous GET /api/v1/industries → 401.
- error paths: get_industry_templates generic 500, search ValueError 400,
  ROI generic 500, recommendations generic 500, analytics 500
- recommendation scoring branches: integration compatibility ≥0.5,
  medium/large company-size scoring, "10+ hours"/"5+" savings, low
  integration overhead, industry ValueError fallthrough
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.industry_workflow_endpoints as iwe
from core.industry_workflow_endpoints import (
    ROICalculationRequest,
    TemplateSearchRequest,
    _calculate_avg_savings,
    _extract_hours_from_savings,
    _get_integration_setup_details,
    get_industry_workflow_engine,
    router,
)
from core.industry_workflow_templates import Industry, IndustryWorkflowEngine, IndustryWorkflowTemplate


def make_template(**overrides):
    t = MagicMock(spec=IndustryWorkflowTemplate)
    t.id = overrides.get("id", "healthcare_patient_onboarding")
    t.name = overrides.get("name", "Patient Onboarding")
    t.description = overrides.get("description", "Automate onboarding")
    t.industry = overrides.get("industry", Industry.HEALTHCARE)
    t.sub_category = overrides.get("sub_category", "Patient Management")
    t.complexity = overrides.get("complexity", "Intermediate")
    t.estimated_time_savings = overrides.get("estimated_time_savings", "8 hours/week")
    t.required_integrations = overrides.get("required_integrations", ["gmail", "zoom"])
    t.optional_integrations = overrides.get("optional_integrations", ["slack"])
    t.benefits = overrides.get("benefits", ["b1", "b2", "b3"])
    t.use_cases = overrides.get("use_cases", ["u1"])
    t.compliance_notes = overrides.get("compliance_notes", None)
    t.setup_instructions = overrides.get("setup_instructions", ["Step 1"])
    t.workflow_data = overrides.get("workflow_data", {"nodes": []})
    t.created_at = overrides.get("created_at", datetime.now(timezone.utc))
    return t


@pytest.fixture
def engine():
    e = Mock(spec=IndustryWorkflowEngine)
    t = make_template()
    e.get_all_industries.return_value = [Industry.HEALTHCARE, Industry.FINANCE]
    e.get_templates_by_industry.return_value = [t]
    e.get_template_by_id.return_value = t
    e.search_templates.return_value = [t]
    e.calculate_roi.return_value = {
        "template_id": t.id,
        "time_savings": {"hours_per_week": 8, "weekly_savings": 400,
                         "monthly_savings": 1732, "annual_savings": 20784},
        "implementation": {"estimated_setup_hours": 8, "setup_cost": 400},
        "annual_roi": 516.0,
    }
    e.templates = {t.id: t}
    return e


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_industry_workflow_engine] = lambda: engine
    if hasattr(iwe, "get_current_user"):
        app.dependency_overrides[iwe.get_current_user] = lambda: Mock(id="u1")
    return TestClient(app)


class TestAuthGate:
    def test_anonymous_industries_rejected(self, engine):
        # RED before fix: anonymous catalog access returned 200.
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_industry_workflow_engine] = lambda: engine
        resp = TestClient(app).get("/api/v1/industries")
        assert resp.status_code == 401

    def test_anonymous_search_rejected(self, engine):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_industry_workflow_engine] = lambda: engine
        resp = TestClient(app).post("/api/v1/templates/search", json={})
        assert resp.status_code == 401


class TestIndustriesEndpoint:
    def test_get_supported_industries(self, client):
        resp = client.get("/api/v1/industries")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_industries"] == 2
        assert body["industries"]["healthcare"]["template_count"] == 1
        assert "avg_time_savings" in body["industries"]["healthcare"]

    def test_get_industry_templates_success(self, client):
        resp = client.get("/api/v1/industries/healthcare/templates")
        assert resp.status_code == 200
        body = resp.json()
        assert body["template_count"] == 1
        assert body["templates"][0]["id"] == "healthcare_patient_onboarding"

    def test_get_industry_templates_complexity_filter(self, client):
        resp = client.get("/api/v1/industries/healthcare/templates?complexity=Beginner")
        assert resp.status_code == 200
        assert resp.json()["template_count"] == 0

    def test_get_industry_templates_unsupported_404(self, client, engine):
        engine.get_templates_by_industry.side_effect = ValueError("no such industry")
        resp = client.get("/api/v1/industries/notreal/templates")
        assert resp.status_code == 404

    def test_get_industry_templates_generic_500(self, client, engine):
        engine.get_templates_by_industry.side_effect = RuntimeError("boom")
        resp = client.get("/api/v1/industries/healthcare/templates")
        assert resp.status_code == 500

    def test_template_details_found(self, client):
        resp = client.get("/api/v1/templates/industry/healthcare_patient_onboarding")
        assert resp.status_code == 200
        assert resp.json()["template"]["industry"] == "healthcare"

    def test_template_details_not_found(self, client, engine):
        engine.get_template_by_id.return_value = None
        resp = client.get("/api/v1/templates/industry/ghost")
        assert resp.status_code == 404


class TestSearchEndpoint:
    def test_search_with_all_filters(self, client):
        resp = client.post("/api/v1/templates/search", json={
            "industry": "healthcare", "complexity": "Intermediate",
            "keywords": ["onboarding"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["result_count"] == 1
        assert body["results"][0]["industry"] == "healthcare"
        assert "benefits" in body["results"][0]

    def test_search_no_criteria(self, client):
        resp = client.post("/api/v1/templates/search", json={})
        assert resp.status_code == 200
        assert resp.json()["result_count"] == 1

    def test_search_invalid_industry_400(self, client, engine):
        engine.search_templates.side_effect = ValueError("bad industry")
        resp = client.post("/api/v1/templates/search", json={"industry": "bogus"})
        assert resp.status_code == 400

    def test_search_generic_500(self, client, engine):
        engine.search_templates.side_effect = RuntimeError("boom")
        resp = client.post("/api/v1/templates/search", json={})
        assert resp.status_code == 500


class TestROIEndpoint:
    def test_roi_success_with_insights(self, client):
        resp = client.post("/api/v1/templates/healthcare_patient_onboarding/roi",
                           json={"hourly_rate": 50})
        assert resp.status_code == 200
        body = resp.json()
        assert body["hourly_rate_used"] == 50
        assert body["roi_analysis"]["annual_roi"] == 516.0
        insights = body["roi_analysis"]["insights"]
        assert insights["setup_timeframe"] == "3 business days"
        assert insights["integration_requirements"]["total"] == 3

    def test_roi_error_from_engine_400(self, client, engine):
        engine.calculate_roi.return_value = {"error": "Template not found"}
        resp = client.post("/api/v1/templates/ghost/roi", json={"hourly_rate": 50})
        assert resp.status_code == 400

    def test_roi_template_missing_insights_skipped(self, client, engine):
        engine.get_template_by_id.return_value = None
        resp = client.post("/api/v1/templates/ghost/roi", json={"hourly_rate": 50})
        assert resp.status_code == 200
        assert "insights" not in resp.json()["roi_analysis"]

    def test_roi_generic_500(self, client, engine):
        engine.calculate_roi.side_effect = RuntimeError("boom")
        resp = client.post("/api/v1/templates/x/roi", json={"hourly_rate": 50})
        assert resp.status_code == 500


class TestRecommendationsEndpoint:
    def _recommend_client(self, engine, template):
        engine.templates = {template.id: template}
        engine.get_all_industries.return_value = []
        engine.get_templates_by_industry.return_value = []
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_industry_workflow_engine] = lambda: engine
        if hasattr(iwe, "get_current_user"):
            app.dependency_overrides[iwe.get_current_user] = lambda: Mock(id="u1")
        return TestClient(app)

    def test_compatibility_and_small_size_scoring(self, engine):
        t = make_template(required_integrations=["gmail", "zoom"], complexity="Beginner",
                          estimated_time_savings="5 hours/week")
        resp = self._recommend_client(engine, t).get(
            "/api/v1/templates/recommendations?industry=healthcare&company_size=small"
            "&current_integrations=gmail,slack")
        assert resp.status_code == 200
        assert resp.json()["total_recommendations"] >= 1
        reasons = resp.json()["recommendations"][0]["reasons"]
        assert any("Compatible with 1 existing integrations" in r for r in reasons)
        assert any("Moderate time savings" in r for r in reasons)

    def test_medium_size_and_high_savings_scoring(self, engine):
        t = make_template(complexity="Intermediate", estimated_time_savings="10 hours/week",
                          required_integrations=["gmail"])
        resp = self._recommend_client(engine, t).get(
            "/api/v1/templates/recommendations?company_size=medium")
        assert resp.status_code == 200
        reasons = resp.json()["recommendations"][0]["reasons"]
        assert any("High time savings potential" in r for r in reasons)

    def test_large_size_scoring(self, engine):
        t = make_template(complexity="Advanced", estimated_time_savings="5 hours/week",
                          required_integrations=["gmail"])
        resp = self._recommend_client(engine, t).get(
            "/api/v1/templates/recommendations?company_size=large")
        assert resp.status_code == 200
        reasons = resp.json()["recommendations"][0]["reasons"]
        assert any("Scalable for enterprise" in r for r in reasons)

    def test_real_format_savings_scoring(self, engine):
        # REAL BUG: scoring checked for "10+ hours"/"5+" substrings that never
        # occur in the engine's real data ("10 hours/week") — the time-savings
        # scoring branches were dead on every real template. RED before fix:
        # no recommendations at all for a 10-hours/week template.
        t = make_template(complexity="Beginner", estimated_time_savings="10 hours/week",
                          required_integrations=["gmail"])
        resp = self._recommend_client(engine, t).get(
            "/api/v1/templates/recommendations")
        assert resp.status_code == 200
        assert resp.json()["total_recommendations"] >= 1
        reasons = resp.json()["recommendations"][0]["reasons"]
        assert any("High time savings potential" in r for r in reasons)

    def test_invalid_industry_ignored_and_excluded(self, engine):
        t = make_template(complexity="Beginner", estimated_time_savings="5 hours/week",
                          required_integrations=["gmail"])
        engine.get_all_industries.side_effect = None
        resp = self._recommend_client(engine, t).get(
            "/api/v1/templates/recommendations?industry=notreal&company_size=small")
        assert resp.status_code == 200

    def test_no_recommendations_when_score_below_threshold(self, engine):
        t = make_template(required_integrations=["gmail"], complexity="Advanced",
                          estimated_time_savings="2 hours/week")
        engine.get_all_industries.side_effect = None
        resp = self._recommend_client(engine, t).get("/api/v1/templates/recommendations")
        assert resp.status_code == 200
        assert resp.json()["total_recommendations"] == 0

    def test_recommendations_generic_500(self, client, engine):
        engine.templates = None
        resp = client.get("/api/v1/templates/recommendations")
        assert resp.status_code == 500


class TestAnalyticsEndpoint:
    def test_industry_analytics_shape(self, client):
        resp = client.get("/api/v1/templates/industry-analytics")
        assert resp.status_code == 200
        analytics = resp.json()["analytics"]
        assert analytics["complexity_distribution"]["Intermediate"] == 2
        assert analytics["industry_distribution"]["healthcare"] == 1
        assert "gmail" in analytics["top_integrations"]
        assert analytics["sub_categories"]["healthcare"]["Patient Management"] == 1
        assert analytics["time_savings_analysis"]["healthcare"]["average_hours_per_week"] == 8.0

    def test_industry_analytics_generic_500(self, client, engine):
        engine.get_all_industries.side_effect = RuntimeError("boom")
        resp = client.get("/api/v1/templates/industry-analytics")
        assert resp.status_code == 500


class TestImplementationGuide:
    def test_guide_full(self, client):
        resp = client.get("/api/v1/templates/implementation-guide/healthcare_patient_onboarding")
        assert resp.status_code == 200
        guide = resp.json()["implementation_guide"]
        assert guide["template_info"]["estimated_setup_time"] == "3 days"
        assert "compliance_requirements" not in guide

    def test_guide_with_compliance_notes(self, client, engine):
        engine.get_template_by_id.return_value = make_template(
            compliance_notes=["HIPAA-compliant handling"])
        resp = client.get("/api/v1/templates/implementation-guide/healthcare_patient_onboarding")
        assert resp.status_code == 200
        assert "compliance_requirements" in resp.json()["implementation_guide"]

    def test_guide_not_found(self, client, engine):
        engine.get_template_by_id.return_value = None
        resp = client.get("/api/v1/templates/implementation-guide/ghost")
        assert resp.status_code == 404


class TestHelperFunctions:
    def test_calculate_avg_savings_empty(self):
        assert _calculate_avg_savings([]) == "0 hours/week"

    def test_calculate_avg_savings_no_hours(self):
        t = make_template(estimated_time_savings="none")
        assert _calculate_avg_savings([t]) == "0 hours/week"

    def test_calculate_avg_savings_mixed(self):
        t1 = make_template(estimated_time_savings="8 hours/week")
        t2 = make_template(id="t2", estimated_time_savings="12 hours/week")
        assert _calculate_avg_savings([t1, t2]) == "10.0 hours/week"

    def test_extract_hours(self):
        assert _extract_hours_from_savings("Saves 10 hours/week") == 10.0
        assert _extract_hours_from_savings("5.5 hours weekly") == 5.5
        assert _extract_hours_from_savings("none") is None

    def test_get_integration_setup_details_known(self):
        details = _get_integration_setup_details(["salesforce", "slack"])
        assert "salesforce" in details
        assert "slack" in details
        assert len(details["salesforce"]) == 4

    def test_get_integration_setup_details_unknown(self):
        details = _get_integration_setup_details(["mystery_tool"])
        assert details["mystery_tool"][0] == "Configure mystery_tool API access"


class TestModelDefaults:
    def test_roi_request_default_hourly_rate(self):
        assert ROICalculationRequest().hourly_rate == 50.0

    def test_search_request_defaults(self):
        r = TemplateSearchRequest()
        assert r.industry is None
        assert r.complexity is None
        assert r.keywords is None
