"""Coverage wave 10f — integration_dashboard + canvas_recording + recording_review (TDD).

Real-bug probes (RED first):
- WG1: canvas_recording handlers re-raise only when the error text contains
  "not found" — ``permission_denied_error`` messages don't, so ownership
  violations on get/flag/replay return **500 instead of 403**.
- WG2: recording_review ``get_review``/``get_recording_reviews``/
  ``trigger_auto_review`` catch ALL exceptions (no ``except HTTPException:
  raise``) — their 404s and 403s become **500s**.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db

USER = SimpleNamespace(id="u-1", role="user", email="u@t.com")
ADMIN = SimpleNamespace(id="u-1", role="workspace_admin", email="u@t.com")


def _app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def _client(router, db, user=USER):
    app = _app(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


# =========================================================================== #
# integration_dashboard_routes (14 endpoints)
# =========================================================================== #
class TestIntegrationDashboard:
    def _c(self):
        from api.integration_dashboard_routes import router

        return _client(router, MagicMock())

    @pytest.fixture
    def dash(self):
        d = MagicMock()
        with patch("api.integration_dashboard_routes.get_integration_dashboard", return_value=d):
            yield d

    def test_get_metrics(self, dash):
        dash.get_metrics.return_value = {"slack": {"messages_fetched": 5}}
        r = self._c().get("/api/integrations/dashboard/metrics")
        assert r.status_code == 200
        assert r.json()["data"] == {"slack": {"messages_fetched": 5}}
        r2 = self._c().get("/api/integrations/dashboard/metrics?integration=slack")
        assert r2.status_code == 200
        dash.get_metrics.assert_called_with("slack")

    def test_get_metrics_error_500(self, dash):
        dash.get_metrics.side_effect = RuntimeError("boom")
        assert self._c().get("/api/integrations/dashboard/metrics").status_code == 500

    def test_get_health(self, dash):
        dash.get_health.return_value = {"slack": {"status": "healthy"}}
        r = self._c().get("/api/integrations/dashboard/health")
        assert r.status_code == 200
        assert r.json()["data"]["slack"]["status"] == "healthy"
        self._c().get("/api/integrations/dashboard/health?integration=teams")
        dash.get_health.assert_called_with("teams")

    def test_get_health_error_500(self, dash):
        dash.get_health.side_effect = RuntimeError("boom")
        assert self._c().get("/api/integrations/dashboard/health").status_code == 500

    def test_overall_status(self, dash):
        dash.get_overall_status.return_value = {
            "overall_status": "healthy", "total_integrations": 3,
            "healthy_count": 2, "degraded_count": 1, "error_count": 0,
            "disabled_count": 0, "total_messages_fetched": 100,
            "total_messages_processed": 90, "total_messages_failed": 2,
            "overall_success_rate": 97.8, "integrations": {},
        }
        r = self._c().get("/api/integrations/dashboard/status/overall")
        assert r.status_code == 200
        body = r.json()
        assert body["overall_status"] == "healthy"
        assert body["overall_success_rate"] == 97.8

    def test_overall_status_error_500(self, dash):
        dash.get_overall_status.side_effect = RuntimeError("boom")
        assert self._c().get("/api/integrations/dashboard/status/overall").status_code == 500

    def test_alerts_and_filter(self, dash):
        dash.get_alerts.return_value = [
            {"integration": "slack", "severity": "critical", "type": "rate",
             "message": "m", "value": 90.0, "threshold": 80.0, "timestamp": "t"},
            {"integration": "teams", "severity": "warning", "type": "rate",
             "message": "m", "value": 60.0, "threshold": 80.0, "timestamp": "t"},
        ]
        r = self._c().get("/api/integrations/dashboard/alerts")
        assert r.status_code == 200
        assert len(r.json()) == 2
        r2 = self._c().get("/api/integrations/dashboard/alerts?severity=warning")
        assert len(r2.json()) == 1
        assert r2.json()[0]["severity"] == "warning"
        r3 = self._c().get("/api/integrations/dashboard/alerts?severity=info")
        assert r3.json() == []

    def test_alerts_error_500(self, dash):
        dash.get_alerts.side_effect = RuntimeError("boom")
        assert self._c().get("/api/integrations/dashboard/alerts").status_code == 500

    def test_alerts_count(self, dash):
        dash.get_alerts.return_value = [
            {"severity": "critical"}, {"severity": "critical"}, {"severity": "warning"},
        ]
        r = self._c().get("/api/integrations/dashboard/alerts/count")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data == {"total": 3, "critical": 2, "warning": 1}

    def test_alerts_count_error_500(self, dash):
        dash.get_alerts.side_effect = RuntimeError("boom")
        assert self._c().get("/api/integrations/dashboard/alerts/count").status_code == 500

    def test_statistics_summary(self, dash):
        dash.get_statistics_summary.return_value = {"recent_activity": []}
        r = self._c().get("/api/integrations/dashboard/statistics/summary")
        assert r.status_code == 200
        assert r.json()["data"] == {"recent_activity": []}

    def test_get_configuration(self, dash):
        dash.get_configuration.return_value = {"slack": {"channel": "x"}}
        r = self._c().get("/api/integrations/dashboard/configuration")
        assert r.status_code == 200
        assert r.json()["data"]["slack"]["channel"] == "x"

    def test_update_configuration(self, dash):
        r = self._c().post("/api/integrations/dashboard/configuration/slack", json={
            "enabled": True, "configured": True, "has_valid_token": True,
            "has_required_permissions": False, "config": {"channel": "new"},
        })
        assert r.status_code == 200
        dash.update_health.assert_called_once()
        kwargs = dash.update_health.call_args.kwargs
        assert kwargs["integration"] == "slack"
        assert kwargs["enabled"] is True
        assert kwargs["has_required_permissions"] is False
        dash.update_configuration.assert_called_once_with("slack", {"channel": "new"})

    def test_update_configuration_health_only(self, dash):
        r = self._c().post("/api/integrations/dashboard/configuration/slack", json={"enabled": False})
        assert r.status_code == 200
        dash.update_health.assert_called_once()
        dash.update_configuration.assert_not_called()

    def test_update_configuration_error_500(self, dash):
        dash.update_health.side_effect = RuntimeError("boom")
        r = self._c().post("/api/integrations/dashboard/configuration/slack", json={"enabled": True})
        assert r.status_code == 500

    def test_reset_metrics(self, dash):
        r = self._c().post("/api/integrations/dashboard/metrics/reset", json={})
        assert r.status_code == 200
        dash.reset_metrics.assert_called_once_with(None)
        r2 = self._c().post("/api/integrations/dashboard/metrics/reset", json={"integration": "slack"})
        assert r2.status_code == 200
        dash.reset_metrics.assert_called_with("slack")

    def test_list_integrations(self, dash):
        dash.get_health.return_value = {
            "slack": {"status": "healthy", "enabled": True, "configured": True},
            "teams": {"status": "error", "enabled": False, "configured": False},
        }
        dash.get_metrics.return_value = {
            "slack": {"messages_fetched": 10, "last_fetch_time": "t"},
            "teams": {},
        }
        r = self._c().get("/api/integrations/dashboard/integrations")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["count"] == 2
        slack = [i for i in data["integrations"] if i["name"] == "slack"][0]
        assert slack["messages_fetched"] == 10
        assert slack["status"] == "healthy"

    def test_integration_details(self, dash):
        dash.get_health.return_value = {"status": "healthy"}
        dash.get_metrics.return_value = {"messages_fetched": 1}
        dash.get_configuration.return_value = {"c": 1}
        r = self._c().get("/api/integrations/dashboard/integrations/slack/details")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["integration"] == "slack"
        assert data["health"] == {"status": "healthy"}

    def test_integration_details_missing_404(self, dash):
        dash.get_health.return_value = None
        r = self._c().get("/api/integrations/dashboard/integrations/ghost/details")
        assert r.status_code == 404

    def test_check_integration_health(self, dash):
        dash.get_health.return_value = {"status": "healthy"}
        r = self._c().post("/api/integrations/dashboard/health/slack/check")
        assert r.status_code == 200
        dash.update_health.assert_called_once_with("slack")

    def test_performance_metrics(self, dash):
        dash.get_metrics.return_value = {
            "slack": {"avg_fetch_time_ms": 10, "p99_fetch_time_ms": 20,
                      "avg_process_time_ms": 5, "p99_process_time_ms": 9,
                      "fetch_size_bytes": 100, "attachment_count": 2},
            "teams": {},
        }
        r = self._c().get("/api/integrations/dashboard/performance")
        assert r.status_code == 200
        perf = r.json()["data"]
        assert perf["slack"]["avg_fetch_time_ms"] == 10
        assert perf["teams"]["attachment_count"] == 0

    def test_data_quality_metrics(self, dash):
        dash.get_metrics.return_value = {
            "slack": {"messages_fetched": 100, "messages_processed": 95,
                      "messages_failed": 3, "messages_duplicate": 2,
                      "success_rate": 95.0, "duplicate_rate": 2.0},
        }
        r = self._c().get("/api/integrations/dashboard/data-quality")
        assert r.status_code == 200
        q = r.json()["data"]
        assert q["slack"]["success_rate"] == 95.0

    def test_mutations_require_auth(self):
        from api.integration_dashboard_routes import router

        client = TestClient(_app(router), raise_server_exceptions=False)
        assert client.post(
            "/api/integrations/dashboard/configuration/slack", json={"enabled": True}
        ).status_code == 401
        assert client.post(
            "/api/integrations/dashboard/metrics/reset", json={}
        ).status_code == 401


# =========================================================================== #
# canvas_recording_routes (8 endpoints)
# =========================================================================== #
class TestCanvasRecordingRoutes:
    def _c(self, db=None, user=USER):
        from api.canvas_recording_routes import router

        return _client(router, db or MagicMock(), user=user)

    @pytest.fixture
    def svc(self):
        s = AsyncMock()
        with patch("api.canvas_recording_routes.get_canvas_recording_service", return_value=s):
            yield s

    def _recording(self, user_id="u-1"):
        return {
            "recording_id": "rec-1", "user_id": user_id, "agent_id": "a-1",
            "canvas_id": None, "reason": "manual", "status": "recording",
            "session_id": None, "tags": [], "started_at": "2026-01-01T00:00:00",
            "stopped_at": None, "duration_seconds": None, "event_count": 0,
            "events": [], "summary": None, "recording_metadata": {},
            "expires_at": None, "flagged_for_review": False,
        }

    def test_start_recording(self, svc):
        svc.start_recording.return_value = "rec-1"
        r = self._c().post("/api/canvas/recording/start", json={
            "agent_id": "a-1", "canvas_id": "c-1", "reason": "manual",
            "session_id": "s-1", "tags": ["t"],
        })
        assert r.status_code == 200
        body = r.json()
        assert body["recording_id"] == "rec-1"
        assert body["status"] == "recording"
        kwargs = svc.start_recording.await_args.kwargs
        assert kwargs["user_id"] == "u-1"
        assert kwargs["agent_id"] == "a-1"
        assert kwargs["tags"] == ["t"]

    def test_start_recording_error_500(self, svc):
        svc.start_recording.side_effect = RuntimeError("boom")
        r = self._c().post("/api/canvas/recording/start", json={
            "agent_id": "a-1", "reason": "manual",
        })
        assert r.status_code == 500

    def test_record_event(self, svc):
        r = self._c().post("/api/canvas/recording/rec-1/event", json={
            "event_type": "operation_start", "event_data": {"op": 1},
        })
        assert r.status_code == 200
        svc.record_event.assert_awaited_once()
        kwargs = svc.record_event.await_args.kwargs
        assert kwargs["recording_id"] == "rec-1"
        assert kwargs["event_type"] == "operation_start"

    def test_record_event_error_500(self, svc):
        svc.record_event.side_effect = RuntimeError("boom")
        r = self._c().post("/api/canvas/recording/rec-1/event", json={
            "event_type": "update", "event_data": {},
        })
        assert r.status_code == 500

    def test_stop_recording(self, svc):
        r = self._c().post("/api/canvas/recording/rec-1/stop", json={
            "status": "completed", "summary": "done",
        })
        assert r.status_code == 200
        svc.stop_recording.assert_awaited_once()
        assert svc.stop_recording.await_args.kwargs["status"] == "completed"

    def test_get_recording_found(self, svc):
        svc.get_recording.return_value = self._recording()
        r = self._c().get("/api/canvas/recording/rec-1")
        assert r.status_code == 200
        assert r.json()["recording_id"] == "rec-1"

    def test_get_recording_missing_404(self, svc):
        svc.get_recording.return_value = None
        assert self._c().get("/api/canvas/recording/rec-1").status_code == 404

    def test_get_recording_other_user_403(self, svc):
        """WG1: permission_denied must NOT be swallowed into a 500."""
        svc.get_recording.return_value = self._recording(user_id="someone-else")
        r = self._c().get("/api/canvas/recording/rec-1")
        assert r.status_code == 403

    def test_get_recording_error_500(self, svc):
        svc.get_recording.side_effect = RuntimeError("boom")
        assert self._c().get("/api/canvas/recording/rec-1").status_code == 500

    def test_list_recordings(self, svc):
        rec = self._recording()
        svc.list_recordings.return_value = [rec]
        r = self._c().get("/api/canvas/recording?agent_id=a-1&limit=10&offset=0")
        assert r.status_code == 200
        body = r.json()
        assert body["metadata"]["total"] == 1
        assert len(body["data"]) == 1
        svc.list_recordings.assert_awaited_once()
        kwargs = svc.list_recordings.await_args.kwargs
        assert kwargs["user_id"] == "u-1"
        assert kwargs["agent_id"] == "a-1"
        assert kwargs["limit"] == 10

    def test_list_recordings_error_500(self, svc):
        svc.list_recordings.side_effect = RuntimeError("boom")
        assert self._c().get("/api/canvas/recording").status_code == 500

    def test_flag_recording(self, svc):
        from core.models import CanvasRecording

        rec = MagicMock(spec=CanvasRecording)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = rec
        r = self._c(db).post("/api/canvas/recording/rec-1/flag", json={
            "flag_reason": "suspicious_activity",
        })
        assert r.status_code == 200
        svc.flag_for_review.assert_awaited_once()
        assert svc.flag_for_review.await_args.kwargs["flag_reason"] == "suspicious_activity"

    def test_flag_recording_missing_404(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).post("/api/canvas/recording/rec-1/flag", json={"flag_reason": "x"})
        assert r.status_code == 404

    def test_replay(self, svc):
        svc.get_recording.return_value = self._recording()
        r = self._c().get("/api/canvas/recording/rec-1/replay")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["recording_id"] == "rec-1"
        assert data["events"] == []

    def test_replay_other_user_403(self, svc):
        """WG1: replay ownership violation must be 403, not 500."""
        svc.get_recording.return_value = self._recording(user_id="someone-else")
        r = self._c().get("/api/canvas/recording/rec-1/replay")
        assert r.status_code == 403

    def test_health_and_auth(self):
        from api.canvas_recording_routes import router

        client = TestClient(_app(router), raise_server_exceptions=False)
        assert client.get("/api/canvas/recording/health").status_code == 200
        assert client.get("/api/canvas/recording/rec-1").status_code == 401
        assert client.post("/api/canvas/recording/start", json={
            "agent_id": "a", "reason": "x",
        }).status_code == 401


# =========================================================================== #
# recording_review_routes (6 endpoints)
# =========================================================================== #
class TestRecordingReviewRoutes:
    def _c(self, db=None, user=USER):
        from api.recording_review_routes import router

        return _client(router, db or MagicMock(), user=user)

    @pytest.fixture
    def svc(self):
        s = AsyncMock()
        with patch("api.recording_review_routes.get_recording_review_service", return_value=s):
            yield s

    def _review(self, **overrides):
        r = MagicMock()
        r.id = "rv-1"
        r.recording_id = "rec-1"
        r.agent_id = "a-1"
        r.user_id = "u-1"
        r.review_status = "approved"
        r.overall_rating = 5
        r.performance_rating = 4
        r.safety_rating = 5
        r.feedback = "good"
        r.identified_issues = []
        r.positive_patterns = ["x"]
        r.lessons_learned = "l"
        r.confidence_delta = 0.05
        r.promoted = False
        r.demoted = False
        r.governance_notes = None
        r.reviewed_by = "u-1"
        r.reviewed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        r.auto_reviewed = False
        r.training_value = "0.8"
        r.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for k, v in overrides.items():
            setattr(r, k, v)
        return r

    def _recording(self, user_id="u-1"):
        rec = MagicMock()
        rec.recording_id = "rec-1"
        rec.user_id = user_id
        return rec

    def test_create_review(self, svc):
        svc.create_review.return_value = "rv-1"
        db = MagicMock()
        rec = self._recording()
        review = self._review()
        db.query.return_value.filter.return_value.first.side_effect = [rec, review]
        r = self._c(db).post("/api/canvas/recording/review", json={
            "recording_id": "rec-1", "review_status": "approved",
            "overall_rating": 5, "performance_rating": 4, "safety_rating": 5,
            "feedback": "good", "identified_issues": [], "positive_patterns": [],
        })
        assert r.status_code == 200
        body = r.json()
        assert body["review_id"] == "rv-1"
        assert body["confidence_delta"] == 0.05
        kwargs = svc.create_review.await_args.kwargs
        assert kwargs["recording_id"] == "rec-1"
        assert kwargs["reviewer_id"] == "u-1"
        assert kwargs["auto_reviewed"] is False

    def test_create_review_missing_recording_404(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).post("/api/canvas/recording/review", json={
            "recording_id": "ghost", "review_status": "approved",
            "overall_rating": 3, "feedback": "f",
        })
        assert r.status_code == 404

    def test_create_review_service_error_500(self, svc):
        svc.create_review.side_effect = RuntimeError("boom")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._recording()
        r = self._c(db).post("/api/canvas/recording/review", json={
            "recording_id": "rec-1", "review_status": "approved",
            "overall_rating": 3, "feedback": "f",
        })
        assert r.status_code == 500

    def test_get_review_found(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            self._review(), self._recording(),
        ]
        r = self._c(db).get("/api/canvas/recording/review/rv-1")
        assert r.status_code == 200
        assert r.json()["review_id"] == "rv-1"

    def test_get_review_missing_404(self, svc):
        """WG2: 404 must not be swallowed into 500."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).get("/api/canvas/recording/review/ghost")
        assert r.status_code == 404

    def test_get_review_non_owner_non_admin_403(self, svc):
        """WG2: 403 must not be swallowed into 500."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            self._review(), self._recording(user_id="someone-else"),
        ]
        r = self._c(db, user=SimpleNamespace(id="u-9", role="user")).get(
            "/api/canvas/recording/review/rv-1"
        )
        assert r.status_code == 403

    def test_get_review_admin_ok(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            self._review(), self._recording(user_id="someone-else"),
        ]
        r = self._c(db, user=ADMIN).get("/api/canvas/recording/review/rv-1")
        assert r.status_code == 200

    def test_get_recording_reviews(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._recording()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [self._review()]
        r = self._c(db).get("/api/canvas/recording/review/recording/rec-1")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        assert rows[0]["review_status"] == "approved"

    def test_get_recording_reviews_missing_404(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).get("/api/canvas/recording/review/recording/ghost")
        assert r.status_code == 404

    def test_get_recording_reviews_other_user_403(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._recording(user_id="x")
        r = self._c(db, user=SimpleNamespace(id="u-9", role="user")).get(
            "/api/canvas/recording/review/recording/rec-1"
        )
        assert r.status_code == 403

    def test_agent_metrics(self, svc):
        svc.get_review_metrics.return_value = {
            "agent_id": "a-1", "total_reviews": 10, "approval_rate": 0.8,
            "average_rating": 4.2, "confidence_impact": 0.1,
            "common_issues": [], "strengths": [], "training_recordings": 3,
        }
        r = self._c().get("/api/canvas/recording/review/agent/a-1/metrics?days=7")
        assert r.status_code == 200
        body = r.json()
        assert body["approval_rate"] == 0.8
        svc.get_review_metrics.assert_awaited_once_with(agent_id="a-1", days=7)

    def test_agent_metrics_error_500(self, svc):
        svc.get_review_metrics.side_effect = RuntimeError("boom")
        assert self._c().get("/api/canvas/recording/review/agent/a-1/metrics").status_code == 500

    def test_trigger_auto_review(self, svc):
        svc.auto_review_recording.return_value = "rv-2"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = self._recording()
        r = self._c(db).post("/api/canvas/recording/review/recording/rec-1/auto-review")
        assert r.status_code == 200
        assert r.json()["data"]["review_id"] == "rv-2"

        svc.auto_review_recording.return_value = None
        r2 = self._c(db).post("/api/canvas/recording/review/recording/rec-1/auto-review")
        assert r2.status_code == 200
        assert r2.json()["data"]["review_id"] is None

    def test_trigger_auto_review_missing_404(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).post("/api/canvas/recording/review/recording/ghost/auto-review")
        assert r.status_code == 404

    def test_health_and_auth(self):
        from api.recording_review_routes import router

        client = TestClient(_app(router), raise_server_exceptions=False)
        assert client.get("/api/canvas/recording/review/health").status_code == 200
        assert client.get("/api/canvas/recording/review/rv-1").status_code == 401
