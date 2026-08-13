# -*- coding: utf-8 -*-
"""Coverage wave 89 — api/feedback_phase2.py (promotion, export, analytics).

Fully mocked services (AgentPromotionService, FeedbackExportService,
AdvancedFeedbackAnalytics) — zero DB, zero network, zero LLM spend.

Covers every endpoint x {success, error paths, 422 validation, 401 unauth}:
promotion-suggestions, promotion-path (hit + 404), promotion-check
(hit + 404), export json/csv/invalid-format, export/summary, export/filters,
and the 4 advanced-analytics endpoints.
"""
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.feedback_phase2 import router as feedback_phase2_router
from core.auth import get_current_user

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(feedback_phase2_router)
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id="user-1")
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def anon_client():
    app = FastAPI()
    app.include_router(feedback_phase2_router)
    return TestClient(app)


@contextmanager
def _patch_services(promotion=None, export=None, analytics=None):
    promo_cls = MagicMock()
    promo_cls.return_value.get_promotion_suggestions.return_value = promotion or []
    promo_cls.return_value.get_promotion_path.return_value = {"status": "ready"}
    promo_cls.return_value.is_agent_ready_for_promotion.return_value = {
        "ready": True, "score": 0.9}
    export_cls = MagicMock()
    export_cls.return_value.export_to_json.return_value = '{"items": []}'
    export_cls.return_value.export_to_csv.return_value = "id,title\n1,foo"
    export_cls.return_value.export_summary_to_json.return_value = '{"summary": {}}'
    export_cls.return_value.get_export_filters.return_value = {
        "agent_ids": ["a1"], "types": ["correction"], "statuses": ["pending"]}
    analytics_cls = MagicMock()
    analytics_cls.return_value.analyze_feedback_performance_correlation.return_value = {
        "correlation": 0.5}
    analytics_cls.return_value.analyze_feedback_by_agent_cohort.return_value = {
        "cohorts": []}
    analytics_cls.return_value.predict_agent_performance.return_value = {
        "prediction": "stable"}
    analytics_cls.return_value.analyze_feedback_velocity.return_value = {
        "pattern": "uniform"}

    if promotion is not None and isinstance(promotion, dict) and "error" in promotion:
        promo_cls.return_value.get_promotion_path.return_value = promotion
    if promotion is not None and isinstance(promotion, dict) and "ready" in promotion:
        promo_cls.return_value.is_agent_ready_for_promotion.return_value = promotion

    with patch("api.feedback_phase2.AgentPromotionService", promo_cls), \
         patch("api.feedback_phase2.FeedbackExportService", export_cls), \
         patch("api.feedback_phase2.AdvancedFeedbackAnalytics", analytics_cls):
        yield


ENDPOINTS = [
    ("get", "/api/feedback/phase2/promotion-suggestions"),
    ("get", "/api/feedback/phase2/promotion-path/agent-1"),
    ("get", "/api/feedback/phase2/promotion-check/agent-1"),
    ("get", "/api/feedback/phase2/export"),
    ("get", "/api/feedback/phase2/export/summary"),
    ("get", "/api/feedback/phase2/export/filters"),
    ("get", "/api/feedback/phase2/analytics/advanced/correlation/agent-1"),
    ("get", "/api/feedback/phase2/analytics/advanced/cohorts"),
    ("get", "/api/feedback/phase2/analytics/advanced/prediction/agent-1"),
    ("get", "/api/feedback/phase2/analytics/advanced/velocity/agent-1"),
]


class TestAuthEnforcement:
    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_anonymous_requests_rejected(self, anon_client, method, path):
        resp = getattr(anon_client, method)(path)
        assert resp.status_code == 401


class TestPromotionSuggestions:
    def test_suggestions_success_default_limit(self, client):
        with _patch_services(promotion=[{"agent_id": "a1", "readiness_score": 0.9}]):
            resp = client.get(
                "/api/feedback/phase2/promotion-suggestions", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total_suggestions"] == 1
        assert body["data"]["suggestions"][0]["agent_id"] == "a1"

    def test_suggestions_empty(self, client):
        with _patch_services(promotion=[]):
            resp = client.get(
                "/api/feedback/phase2/promotion-suggestions", headers=AUTH_HEADERS)
        assert resp.json()["data"]["total_suggestions"] == 0

    def test_suggestions_limit_custom(self, client):
        with _patch_services():
            resp = client.get(
                "/api/feedback/phase2/promotion-suggestions",
                params={"limit": 50}, headers=AUTH_HEADERS)
        assert resp.status_code == 200

    @pytest.mark.parametrize("limit", [0, 51])
    def test_suggestions_limit_out_of_range_422(self, client, limit):
        with _patch_services():
            resp = client.get(
                "/api/feedback/phase2/promotion-suggestions",
                params={"limit": limit}, headers=AUTH_HEADERS)
        assert resp.status_code == 422


class TestPromotionPath:
    def test_path_success(self, client):
        with _patch_services():
            resp = client.get(
                "/api/feedback/phase2/promotion-path/agent-1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "ready"

    def test_path_agent_not_found_404(self, client):
        with _patch_services(promotion={"error": "Agent not found"}):
            resp = client.get(
                "/api/feedback/phase2/promotion-path/missing", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"]["code"] == "NOT_FOUND"


class TestPromotionCheck:
    def test_check_success(self, client):
        with _patch_services():
            resp = client.get(
                "/api/feedback/phase2/promotion-check/agent-1",
                params={"target_status": "SUPERVISED"}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["ready"] is True

    def test_check_agent_not_found_404(self, client):
        with _patch_services(promotion={"ready": False, "error": "no such agent"}):
            resp = client.get(
                "/api/feedback/phase2/promotion-check/missing", headers=AUTH_HEADERS)
        assert resp.status_code == 404


class TestExport:
    def test_export_json_success(self, client):
        with _patch_services():
            resp = client.get("/api/feedback/phase2/export",
                              params={"format": "json", "days": 30},
                              headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"
        assert "attachment; filename=feedback_export_" in resp.headers["content-disposition"]

    def test_export_csv_success(self, client):
        with _patch_services():
            resp = client.get("/api/feedback/phase2/export",
                              params={"format": "csv"}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert ".csv" in resp.headers["content-disposition"]
        assert resp.text == "id,title\n1,foo"

    def test_export_json_with_filters(self, client):
        with _patch_services():
            resp = client.get("/api/feedback/phase2/export",
                              params={
                                  "format": "json",
                                  "agent_id": "a1",
                                  "days": 7,
                                  "feedback_type": "rating",
                                  "status": "pending",
                                  "limit": 50,
                              }, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == {"items": []}

    def test_export_invalid_format_422(self, client):
        with _patch_services():
            resp = client.get("/api/feedback/phase2/export",
                              params={"format": "xml"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422
        err = resp.json()["detail"]["error"]
        assert err["code"] == "VALIDATION_ERROR"
        assert err["details"]["provided"] == "xml"

    @pytest.mark.parametrize("param,value", [
        ("days", 0), ("days", 366), ("limit", 0), ("limit", 10001)])
    def test_export_query_param_out_of_range_422(self, client, param, value):
        with _patch_services():
            resp = client.get("/api/feedback/phase2/export",
                              params={param: value}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_export_summary_success(self, client):
        with _patch_services():
            resp = client.get("/api/feedback/phase2/export/summary",
                              params={"agent_id": "a1", "days": 14},
                              headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"
        assert "feedback_summary_" in resp.headers["content-disposition"]

    def test_export_filters_success(self, client):
        with _patch_services():
            resp = client.get("/api/feedback/phase2/export/filters",
                              headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["agent_ids"] == ["a1"]
        assert data["types"] == ["correction"]


class TestAdvancedAnalytics:
    def test_correlation_success(self, client):
        with _patch_services():
            resp = client.get(
                "/api/feedback/phase2/analytics/advanced/correlation/agent-1",
                headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["correlation"] == 0.5

    def test_correlation_days_out_of_range_422(self, client):
        with _patch_services():
            resp = client.get(
                "/api/feedback/phase2/analytics/advanced/correlation/agent-1",
                params={"days": 0}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    def test_cohorts_success(self, client):
        with _patch_services():
            resp = client.get(
                "/api/feedback/phase2/analytics/advanced/cohorts",
                params={"days": 60}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["cohorts"] == []

    def test_prediction_success(self, client):
        with _patch_services():
            resp = client.get(
                "/api/feedback/phase2/analytics/advanced/prediction/agent-1",
                headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["prediction"] == "stable"

    def test_velocity_success(self, client):
        with _patch_services():
            resp = client.get(
                "/api/feedback/phase2/analytics/advanced/velocity/agent-1",
                headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["data"]["pattern"] == "uniform"

    def test_service_exception_surfaces_500(self, client):
        analytics_cls = MagicMock()
        analytics_cls.return_value.analyze_feedback_velocity.side_effect = \
            Exception("analytics engine down")
        with patch("api.feedback_phase2.AdvancedFeedbackAnalytics", analytics_cls):
            resp = client.get(
                "/api/feedback/phase2/analytics/advanced/velocity/agent-1",
                headers=AUTH_HEADERS)
        assert resp.status_code == 500
