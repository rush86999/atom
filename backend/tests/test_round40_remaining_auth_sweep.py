"""
Round 40 — Third-pass auth sweep: mounted routers with anonymous endpoints
(Red-Green-Refactor).

Round 38/39 swept the governance-decorated + partially-fixed routers. This
round covers the remaining *mounted* routers that were never touched:

  A. api/agent_control_routes.py    — start/stop/restart/execute are
     get_super_admin-guarded, but GET /api/agent/status (daemon PID, uptime,
     memory, CPU) is anonymous.
  B. api/canvas_coding_routes.py    — GET /api/canvas/coding/{id} returns the
     full coding-canvas audit details (code diffs) anonymously. R24 fixed
     canvas docs/email/terminal but missed coding.
  C. api/intelligence_routes.py     — GET /api/intelligence/{insights,entities}
     expose cross-platform business insights; /insights ALSO auto-seeds and
     ingests platform data in development mode (side-effecting, cost-bearing).
  D. api/skill_routes.py            — R22 fixed import/execute/promote; the 4
     reads (list, get, {id}/episodes — episodic memory, {id}/learning-progress)
     are anonymous.
  E. api/workflow_template_routes.py — R38 fixed create/import/execute; the 2
     reads (list, search) are anonymous.
  F. api/byok_routes.py             — key-management endpoints
     (GET/POST /api/ai/keys — mock but key surface) and all 5 pricing
     endpoints are anonymous; /api/ai/pricing/refresh triggers external
     fetches (network abuse). 5 remaining str(e) leaks in the pricing
     section (R25 fixed the earlier ones).
  G. api/analytics_dashboard_routes.py — all 12 endpoints (message analytics,
     sentiment, correlations POST, predictions, user patterns) anonymous.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user as auth_get_current_user
from core.database import get_db

SENTINEL = "SENTINEL_LEAK_round40"


def make_client(router, current_user=None, db=None):
    """TestClient with auth + db dependency overrides (authenticated)."""
    app = FastAPI()
    app.include_router(router)

    def _override_user():
        if current_user is not None:
            return current_user
        user = MagicMock(id="r40-user")
        user.role = "super_admin"
        return user

    def _override_db():
        return db if db is not None else MagicMock()

    app.dependency_overrides[auth_get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    return TestClient(app, raise_server_exceptions=False)


def make_anon_client(router):
    """TestClient WITHOUT auth overrides — requests must 401."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ============================================================================
# A. Agent control — anonymous daemon status
# ============================================================================

class TestAgentControlStatusAuth:
    def _anon(self):
        from api.agent_control_routes import router
        return make_anon_client(router)

    def test_get_status_requires_auth(self):
        assert self._anon().get("/api/agent/status").status_code == 401

    def test_authenticated_status_works(self):
        from api.agent_control_routes import router
        with patch(
            "api.agent_control_routes.DaemonManager.get_status",
            return_value={"running": True, "pid": 123},
        ):
            client = make_client(router)
            resp = client.get("/api/agent/status")
        assert resp.status_code == 200
        assert resp.json()["status"]["running"] is True


# ============================================================================
# B. Coding canvas — anonymous code-content reads
# ============================================================================

class TestCodingCanvasAuth:
    def _anon(self):
        from api.canvas_coding_routes import router
        return make_anon_client(router)

    def test_get_coding_canvas_requires_auth(self):
        assert self._anon().get("/api/canvas/coding/c-1").status_code == 401

    def test_authenticated_get_works(self):
        from api.canvas_coding_routes import router
        fake_audit = MagicMock()
        fake_audit.details_json = {"files": ["a.py"]}
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            fake_audit
        )
        client = make_client(router, db=db)
        resp = client.get("/api/canvas/coding/c-1")
        assert resp.status_code == 200


# ============================================================================
# C. Intelligence — anonymous business insights + side-effecting /insights
# ============================================================================

class TestIntelligenceAuth:
    def _anon(self):
        from api.intelligence_routes import router
        return make_anon_client(router)

    def test_get_insights_requires_auth(self):
        assert self._anon().get("/api/intelligence/insights").status_code == 401

    def test_get_entities_requires_auth(self):
        assert self._anon().get("/api/intelligence/entities").status_code == 401

    def test_authenticated_insights_works(self, monkeypatch):
        from api.intelligence_routes import router
        monkeypatch.setenv("ENVIRONMENT", "production")
        engine = MagicMock()
        engine.entity_registry = {}
        engine.detect_anomalies = AsyncMock(return_value=[])
        with patch("api.intelligence_routes.engine", engine):
            client = make_client(router)
            resp = client.get("/api/intelligence/insights")
        assert resp.status_code == 200


# ============================================================================
# D. Skills — anonymous skill definitions + episodic execution memory
# ============================================================================

class TestSkillReadsAuth:
    def _anon(self):
        from api.skill_routes import router
        return make_anon_client(router)

    def test_list_skills_requires_auth(self):
        assert self._anon().get("/api/skills/list").status_code == 401

    def test_get_skill_requires_auth(self):
        assert self._anon().get("/api/skills/s-1").status_code == 401

    def test_get_skill_episodes_requires_auth(self):
        assert self._anon().get(
            "/api/skills/s-1/episodes?agent_id=a-1"
        ).status_code == 401

    def test_get_skill_learning_progress_requires_auth(self):
        assert self._anon().get(
            "/api/skills/s-1/learning-progress?agent_id=a-1"
        ).status_code == 401

    def test_authenticated_list_works(self):
        from api.skill_routes import router
        service = MagicMock()
        service.list_skills.return_value = []
        with patch("api.skill_routes.get_skill_service", return_value=service):
            client = make_client(router)
            resp = client.get("/api/skills/list")
        assert resp.status_code == 200


# ============================================================================
# E. Workflow templates — anonymous template-definition reads
# ============================================================================

class TestWorkflowTemplateReadsAuth:
    def _anon(self):
        from api.workflow_template_routes import router
        return make_anon_client(router)

    def test_list_templates_requires_auth(self):
        assert self._anon().get("/api/workflow-templates/").status_code == 401

    def test_search_templates_requires_auth(self):
        assert self._anon().get(
            "/api/workflow-templates/search?query=invoice"
        ).status_code == 401

    def test_authenticated_list_works(self):
        from api.workflow_template_routes import router
        manager = MagicMock()
        manager.list_templates.return_value = []
        with patch("api.workflow_template_routes.get_template_manager", return_value=manager):
            client = make_client(router)
            resp = client.get("/api/workflow-templates/")
        assert resp.status_code == 200

    def test_search_reaches_search_templates_not_get_template(self):
        """Route-shadowing regression: /search was swallowed by /{template_id}."""
        from api.workflow_template_routes import router
        manager = MagicMock()
        manager.search_templates.return_value = []
        with patch("api.workflow_template_routes.get_template_manager", return_value=manager):
            client = make_client(router)
            resp = client.get("/api/workflow-templates/search?query=invoice")
            assert resp.status_code == 200
            manager.search_templates.assert_called_once_with("invoice", limit=20)

    def test_list_templates_no_leak(self):
        from api.workflow_template_routes import router
        with patch(
            "api.workflow_template_routes.get_template_manager",
            side_effect=RuntimeError(SENTINEL),
        ):
            client = make_client(router)
            resp = client.get("/api/workflow-templates/")
        assert resp.status_code == 500
        assert SENTINEL not in resp.text


# ============================================================================
# F. BYOK — anonymous key-management + pricing endpoints, str(e) leaks
# ============================================================================

class TestByokAuth:
    def _anon(self):
        from api.byok_routes import router
        return make_anon_client(router)

    def test_get_api_keys_requires_auth(self):
        assert self._anon().get("/api/ai/keys").status_code == 401

    def test_add_api_key_requires_auth(self):
        resp = self._anon().post("/api/ai/keys", json={"provider": "openai", "key": "sk-x"})
        assert resp.status_code == 401

    def test_get_ai_pricing_requires_auth(self):
        assert self._anon().get("/api/ai/pricing").status_code == 401

    def test_refresh_ai_pricing_requires_auth(self):
        assert self._anon().post("/api/ai/pricing/refresh").status_code == 401

    def test_get_model_pricing_requires_auth(self):
        assert self._anon().get("/api/ai/pricing/model/gpt-4o").status_code == 401

    def test_get_provider_pricing_requires_auth(self):
        assert self._anon().get("/api/ai/pricing/provider/openai").status_code == 401

    def test_estimate_request_cost_requires_auth(self):
        resp = self._anon().post("/api/ai/pricing/estimate", json={})
        assert resp.status_code == 401

    def test_authenticated_get_api_keys_works(self):
        from api.byok_routes import router
        client = make_client(router)
        resp = client.get("/api/ai/keys")
        assert resp.status_code == 200

    def test_get_ai_pricing_no_leak(self):
        """str(e) must not reach the client when the fetcher fails."""
        from api.byok_routes import router
        with patch(
            "core.dynamic_pricing_fetcher.get_pricing_fetcher",
            side_effect=RuntimeError(SENTINEL),
        ):
            client = make_client(router)
            resp = client.get("/api/ai/pricing")
        assert resp.status_code == 200
        assert SENTINEL not in resp.text

    def test_refresh_ai_pricing_no_leak(self):
        from api.byok_routes import router
        with patch(
            "core.dynamic_pricing_fetcher.refresh_pricing_cache",
            side_effect=RuntimeError(SENTINEL),
        ):
            client = make_client(router)
            resp = client.post("/api/ai/pricing/refresh")
        assert resp.status_code == 200
        assert SENTINEL not in resp.text


# ============================================================================
# G. Analytics dashboard — anonymous message/platform analytics
# ============================================================================

class TestAnalyticsDashboardAuth:
    def _anon(self):
        from api.analytics_dashboard_routes import router
        return make_anon_client(router)

    def test_summary_requires_auth(self):
        assert self._anon().get("/api/analytics/summary").status_code == 401

    def test_sentiment_requires_auth(self):
        assert self._anon().get("/api/analytics/sentiment").status_code == 401

    def test_response_times_requires_auth(self):
        assert self._anon().get("/api/analytics/response-times").status_code == 401

    def test_activity_requires_auth(self):
        assert self._anon().get("/api/analytics/activity").status_code == 401

    def test_cross_platform_requires_auth(self):
        assert self._anon().get("/api/analytics/cross-platform").status_code == 401

    def test_correlations_requires_auth(self):
        resp = self._anon().post("/api/analytics/correlations", json=[])
        assert resp.status_code == 401

    def test_timeline_requires_auth(self):
        assert self._anon().get(
            "/api/analytics/correlations/c-1/timeline"
        ).status_code == 401

    def test_predict_response_time_requires_auth(self):
        assert self._anon().get(
            "/api/analytics/predictions/response-time?recipient=r&platform=p"
        ).status_code == 401

    def test_recommend_channel_requires_auth(self):
        assert self._anon().get(
            "/api/analytics/recommendations/channel?recipient=r"
        ).status_code == 401

    def test_bottlenecks_requires_auth(self):
        assert self._anon().get("/api/analytics/bottlenecks").status_code == 401

    def test_user_patterns_requires_auth(self):
        assert self._anon().get("/api/analytics/patterns/u-1").status_code == 401

    def test_overview_requires_auth(self):
        assert self._anon().get("/api/analytics/overview").status_code == 401

    def test_authenticated_summary_works(self):
        from api.analytics_dashboard_routes import router
        with patch(
            "api.analytics_dashboard_routes.get_message_analytics_engine",
            return_value=MagicMock(),
        ):
            client = make_client(router)
            resp = client.get("/api/analytics/summary")
        assert resp.status_code == 200
