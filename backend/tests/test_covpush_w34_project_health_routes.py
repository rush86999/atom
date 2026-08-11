"""Coverage wave 34 — api/project_health_routes.py (26% → 90%+).

The router computes health metrics from fixed simulated data, so every
reachable branch is deterministic and testable via TestClient + direct unit
calls. The intra-calculator status ladders driven by fixed constants (e.g.
notion always scores 70 → "good") are exercised for the values the data
produces; alternate ladder values are unreachable without editing source
(same precedent as wave-19 — accepted).

Note: the pre-existing tests/unit/api/test_project_health_routes.py targets
phantom paths (/api/project-health/...) that don't exist — the real router
prefix is /api/v1/projects with /health + /health/templates.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.project_health_routes import (
    HealthMetric,
    calculate_overall_score,
    generate_overall_recommendations,
    router,
)
from core.database import get_db
from core.security_dependencies import get_current_user


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    return TestClient(app)


FULL_PAYLOAD = {
    "notion_api_key": "k",
    "notion_database_id": "db",
    "github_owner": "owner",
    "github_repo": "repo",
    "slack_channel_id": "chan",
    "time_range_days": 7,
}


def _metric(name, score=50, max_score=100, status="warning"):
    return HealthMetric(
        name=name, score=score, max_score=max_score,
        status=status, details={}, trend="stable",
    )


class TestCheckProjectHealthRoute:
    def test_full_payload_all_metrics(self, client):
        resp = client.post("/api/v1/projects/health", json=FULL_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["metrics"]) == {"notion", "github", "slack", "meetings"}
        assert data["overall_status"] in ("excellent", "good", "warning", "critical")
        assert data["time_range_days"] == 7
        assert len(data["check_id"]) == 36
        assert "checked_at" in data

    def test_notion_only(self, client):
        resp = client.post("/api/v1/projects/health", json={
            "notion_api_key": "k", "notion_database_id": "db"})
        assert resp.status_code == 200
        assert set(resp.json()["metrics"]) == {"notion", "meetings"}

    def test_github_only(self, client):
        resp = client.post("/api/v1/projects/health", json={
            "github_owner": "o", "github_repo": "r"})
        assert resp.status_code == 200
        assert set(resp.json()["metrics"]) == {"github", "meetings"}

    def test_slack_only(self, client):
        resp = client.post("/api/v1/projects/health", json={"slack_channel_id": "c"})
        assert resp.status_code == 200
        assert set(resp.json()["metrics"]) == {"slack", "meetings"}

    def test_no_credentials_meetings_only(self, client):
        resp = client.post("/api/v1/projects/health", json={})
        assert resp.status_code == 200
        assert set(resp.json()["metrics"]) == {"meetings"}

    def test_notion_calculation_failure_skipped(self, client):
        with patch("api.project_health_routes.calculate_notion_health",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = client.post("/api/v1/projects/health", json=FULL_PAYLOAD)
        assert resp.status_code == 200
        assert "notion" not in resp.json()["metrics"]
        assert "github" in resp.json()["metrics"]

    def test_all_calculations_fail_returns_400(self, client):
        patchers = [
            patch("api.project_health_routes.calculate_notion_health",
                  new=AsyncMock(side_effect=RuntimeError("n"))),
            patch("api.project_health_routes.calculate_github_health",
                  new=AsyncMock(side_effect=RuntimeError("g"))),
            patch("api.project_health_routes.calculate_slack_health",
                  new=AsyncMock(side_effect=RuntimeError("s"))),
            patch("api.project_health_routes.calculate_meeting_health",
                  new=AsyncMock(side_effect=RuntimeError("m"))),
        ]
        for p in patchers:
            p.start()
        try:
            resp = client.post("/api/v1/projects/health", json=FULL_PAYLOAD)
        finally:
            for p in patchers:
                p.stop()
        assert resp.status_code == 400

    def test_time_range_validation(self, client):
        resp = client.post("/api/v1/projects/health", json={
            "notion_api_key": "k", "notion_database_id": "db",
            "time_range_days": 0})
        assert resp.status_code == 422

    def test_meeting_calculation_failure_meeting_skipped(self, client):
        with patch("api.project_health_routes.calculate_meeting_health",
                   new=AsyncMock(side_effect=RuntimeError("m"))):
            resp = client.post("/api/v1/projects/health", json=FULL_PAYLOAD)
        assert resp.status_code == 200
        assert "meetings" not in resp.json()["metrics"]

    def test_slack_calculation_failure_skipped(self, client):
        with patch("api.project_health_routes.calculate_slack_health",
                   new=AsyncMock(side_effect=RuntimeError("s"))):
            resp = client.post("/api/v1/projects/health", json=FULL_PAYLOAD)
        assert resp.status_code == 200
        assert "slack" not in resp.json()["metrics"]

    def test_unexpected_error_returns_500(self, client):
        with patch("api.project_health_routes.calculate_overall_score",
                   side_effect=RuntimeError("boom")):
            resp = client.post("/api/v1/projects/health", json=FULL_PAYLOAD)
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal error"

    def test_unauthenticated_returns_401(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: SimpleNamespace()
        resp = TestClient(app).post("/api/v1/projects/health", json=FULL_PAYLOAD)
        assert resp.status_code == 401


class TestRecommendationsAndScore:
    def test_recommendation_each_name_warning(self):
        recs = generate_overall_recommendations({
            "a": _metric("Task Management", status="warning"),
            "b": _metric("Code Health", status="warning"),
            "c": _metric("Communication", status="warning"),
            "d": _metric("Meeting Balance", status="critical"),
        })
        joined = " ".join(recs)
        assert "overdue tasks" in joined
        assert "open PRs" in joined
        assert "response times" in joined
        assert "meeting load" in joined

    def test_recommendation_good_fallback(self):
        recs = generate_overall_recommendations({
            "a": _metric("Task Management", status="good"),
        })
        assert recs == ["Project health is good! Maintain current practices."]

    def test_overall_score_empty_unknown(self):
        score, status = calculate_overall_score({})
        assert score == 0.0 and status == "unknown"

    def test_overall_score_statuses(self):
        assert calculate_overall_score({"a": _metric("x", score=90)})[1] == "excellent"
        assert calculate_overall_score({"a": _metric("x", score=70)})[1] == "good"
        assert calculate_overall_score({"a": _metric("x", score=50)})[1] == "warning"
        assert calculate_overall_score({"a": _metric("x", score=30)})[1] == "critical"
        score, _ = calculate_overall_score({"a": _metric("x", score=80, max_score=100)})
        assert score == 80.0


class TestTemplatesRoute:
    def test_list_templates(self, client):
        resp = client.get("/api/v1/projects/health/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert set(data["templates"]) == {
            "software_development", "product_team", "research", "startup"}
        assert data["templates"]["software_development"]["metrics"] == [
            "notion", "github", "slack", "meetings"]
