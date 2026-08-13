"""Coverage wave W65f — api/monitoring_routes.py + api/recording_review_routes.py
(TDD).

Every endpoint x {success, error branch, validation}; auth is only enforced on
the endpoints that declare a get_current_user dependency (create/delete for
monitoring, all recording-review endpoints). Services are patched at the real
module attributes (api.<module>.<name>), DB sessions are MagicMock.
"""
from __future__ import annotations

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


def _make_app(router):
    app = FastAPI()
    app.include_router(router)
    return app


def _client(router, db, user=USER):
    app = _make_app(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _anon_client(router, db):
    app = _make_app(router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


# =========================================================================== #
# api/monitoring_routes.py
# =========================================================================== #
def _monitor(**overrides):
    m = SimpleNamespace(
        id="mon-1",
        agent_id="a-1",
        agent_name="Agent",
        name="Inbox monitor",
        description=None,
        condition_type="inbox_volume",
        threshold_config={"metric": "unread_count", "operator": ">", "value": 100},
        composite_logic=None,
        composite_conditions=None,
        check_interval_seconds=300,
        platforms=[{"platform": "slack", "recipient_id": "C1"}],
        alert_template=None,
        throttle_minutes=0,
        last_alert_sent_at=None,
        status="active",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=None,
    )
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


def _alert(**overrides):
    a = SimpleNamespace(
        id="al-1",
        monitor_id="mon-1",
        condition_value={"unread_count": 150},
        threshold_value={"value": 100},
        alert_message="Inbox over threshold",
        platforms_sent=[{"platform": "slack", "recipient_id": "C1"}],
        status="sent",
        triggered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        sent_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        error_message=None,
    )
    for k, v in overrides.items():
        setattr(a, k, v)
    return a


class TestMonitoringRoutes:
    def _c(self, db=None):
        from api.monitoring_routes import router

        return _client(router, db or MagicMock())

    def _anon(self, db=None):
        from api.monitoring_routes import router

        return _anon_client(router, db or MagicMock())

    @pytest.fixture
    def svc(self):
        s = MagicMock()
        s.check_and_alert_monitors = AsyncMock(
            return_value={"checked": 3, "triggered": 1, "alerts_sent": 1}
        )
        with patch("api.monitoring_routes.ConditionMonitoringService", return_value=s):
            yield s

    @pytest.fixture
    def presets(self):
        return [
            {
                "name": "inbox_volume",
                "condition_type": "inbox_volume",
                "threshold_config": {"metric": "unread_count", "operator": ">", "value": 100},
                "check_interval_seconds": 300,
            },
            {
                "name": "task_backlog",
                "condition_type": "task_backlog",
                "threshold_config": {"metric": "pending", "operator": ">", "value": 50},
                "check_interval_seconds": 600,
            },
        ]

    # -- create --
    def test_create_monitor(self, svc):
        svc.create_monitor.return_value = _monitor()
        r = self._c().post("/api/v1/monitoring/condition/create", json={
            "agent_id": "a-1",
            "name": "Inbox monitor",
            "condition_type": "inbox_volume",
            "threshold_config": {"metric": "unread_count", "operator": ">", "value": 100},
            "platforms": [{"platform": "slack", "recipient_id": "C1"}],
            "check_interval_seconds": 300,
            "alert_template": "Alert: {value}",
            "composite_logic": "OR",
            "composite_conditions": [{"condition_type": "inbox_volume"}],
            "governance_metadata": {"maturity": "supervised"},
        })
        assert r.status_code == 200
        assert r.json()["id"] == "mon-1"
        kwargs = svc.create_monitor.call_args.kwargs
        assert kwargs["agent_id"] == "a-1"
        assert kwargs["check_interval_seconds"] == 300
        assert kwargs["composite_logic"] == "OR"
        assert kwargs["governance_metadata"] == {"maturity": "supervised"}

    def test_create_monitor_missing_fields_422(self, svc):
        r = self._c().post("/api/v1/monitoring/condition/create", json={
            "name": "x", "condition_type": "y", "threshold_config": {},
            "platforms": [],
        })
        assert r.status_code == 422

    def test_create_monitor_requires_auth(self, svc):
        r = self._anon().post("/api/v1/monitoring/condition/create", json={
            "agent_id": "a-1", "name": "n", "condition_type": "inbox_volume",
            "threshold_config": {}, "platforms": [],
        })
        assert r.status_code == 401

    # -- list --
    def test_list_monitors(self, svc):
        svc.get_monitors.return_value = [_monitor(), _monitor(id="mon-2", name="B")]
        r = self._anon().get("/api/v1/monitoring/condition/list", params={
            "agent_id": "a-1", "condition_type": "inbox_volume",
            "monitor_status": "active", "limit": 5,
        })
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 2
        assert rows[1]["name"] == "B"
        kwargs = svc.get_monitors.call_args.kwargs
        assert kwargs["agent_id"] == "a-1"
        assert kwargs["status"] == "active"
        assert kwargs["limit"] == 5

    def test_list_monitors_defaults(self, svc):
        svc.get_monitors.return_value = []
        self._anon().get("/api/v1/monitoring/condition/list")
        kwargs = svc.get_monitors.call_args.kwargs
        assert kwargs["agent_id"] is None
        assert kwargs["limit"] == 100

    # -- get --
    def test_get_monitor_found(self, svc):
        svc.get_monitor.return_value = _monitor()
        r = self._anon().get("/api/v1/monitoring/condition/mon-1")
        assert r.status_code == 200
        assert r.json()["id"] == "mon-1"
        svc.get_monitor.assert_called_once_with(monitor_id="mon-1")

    def test_get_monitor_missing_404(self, svc):
        svc.get_monitor.return_value = None
        r = self._anon().get("/api/v1/monitoring/condition/ghost")
        assert r.status_code == 404

    # -- update --
    def test_update_monitor(self, svc):
        svc.update_monitor.return_value = _monitor(name="Renamed")
        r = self._anon().put("/api/v1/monitoring/condition/mon-1", json={
            "name": "Renamed",
            "threshold_config": {"metric": "unread_count", "value": 200},
            "check_interval_seconds": 60,
            "alert_template": "New template",
            "platforms": [{"platform": "discord", "recipient_id": "G1"}],
        })
        assert r.status_code == 200
        assert r.json()["name"] == "Renamed"
        kwargs = svc.update_monitor.call_args.kwargs
        assert kwargs["name"] == "Renamed"
        assert kwargs["check_interval_seconds"] == 60
        assert kwargs["platforms"] == [{"platform": "discord", "recipient_id": "G1"}]

    def test_update_monitor_partial(self, svc):
        svc.update_monitor.return_value = _monitor()
        r = self._anon().put("/api/v1/monitoring/condition/mon-1", json={"name": "Only"})
        assert r.status_code == 200
        kwargs = svc.update_monitor.call_args.kwargs
        assert kwargs["threshold_config"] is None
        assert kwargs["alert_template"] is None

    def test_update_monitor_invalid_body_422(self, svc):
        r = self._anon().put("/api/v1/monitoring/condition/mon-1", json={"name": 5})
        assert r.status_code == 422

    # -- pause / resume / delete --
    def test_pause_monitor(self, svc):
        svc.pause_monitor.return_value = _monitor(status="paused")
        r = self._anon().post("/api/v1/monitoring/condition/mon-1/pause")
        assert r.status_code == 200
        assert r.json()["status"] == "paused"
        svc.pause_monitor.assert_called_once_with(monitor_id="mon-1")

    def test_resume_monitor(self, svc):
        svc.resume_monitor.return_value = _monitor(status="active")
        r = self._anon().post("/api/v1/monitoring/condition/mon-1/resume")
        assert r.status_code == 200
        assert r.json()["status"] == "active"

    def test_delete_monitor(self, svc):
        svc.delete_monitor.return_value = _monitor(status="deleted")
        r = self._c().delete("/api/v1/monitoring/condition/mon-1")
        assert r.status_code == 200
        svc.delete_monitor.assert_called_once_with(monitor_id="mon-1")

    def test_delete_monitor_requires_auth(self, svc):
        r = self._anon().delete("/api/v1/monitoring/condition/mon-1")
        assert r.status_code == 401

    # -- alerts --
    def test_get_alerts(self, svc):
        svc.get_alerts.return_value = [_alert(), _alert(id="al-2", status="pending")]
        r = self._anon().get("/api/v1/monitoring/alerts", params={
            "monitor_id": "mon-1", "alert_status": "sent", "limit": 5,
        })
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 2
        assert rows[0]["alert_message"] == "Inbox over threshold"
        kwargs = svc.get_alerts.call_args.kwargs
        assert kwargs["monitor_id"] == "mon-1"
        assert kwargs["status"] == "sent"
        assert kwargs["limit"] == 5

    def test_get_alerts_defaults(self, svc):
        svc.get_alerts.return_value = []
        self._anon().get("/api/v1/monitoring/alerts")
        kwargs = svc.get_alerts.call_args.kwargs
        assert kwargs["monitor_id"] is None
        assert kwargs["limit"] == 100

    # -- test --
    def test_test_condition(self, svc):
        svc.test_condition.return_value = {
            "monitor_id": "mon-1",
            "monitor_name": "Inbox monitor",
            "condition_type": "inbox_volume",
            "triggered": True,
            "current_value": 150,
            "threshold": {"value": 100},
            "timestamp": "2026-01-01T00:00:00Z",
        }
        r = self._anon().post("/api/v1/monitoring/condition/mon-1/test")
        assert r.status_code == 200
        body = r.json()
        assert body["triggered"] is True
        assert body["current_value"] == 150

    # -- presets --
    def test_get_presets(self, svc, presets):
        svc.get_presets.return_value = presets
        r = self._anon().get("/api/v1/monitoring/presets")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_apply_preset_success(self, svc, presets):
        svc.get_presets.return_value = presets
        svc.create_monitor.return_value = _monitor()
        r = self._anon().post(
            "/api/v1/monitoring/presets/apply",
            params={"agent_id": "a-1", "preset_name": "inbox_volume"},
            json={"platforms": [{"platform": "slack", "recipient_id": "C1"}]},
        )
        assert r.status_code == 200
        kwargs = svc.create_monitor.call_args.kwargs
        assert kwargs["agent_id"] == "a-1"
        assert kwargs["name"] == "inbox_volume"
        assert kwargs["condition_type"] == "inbox_volume"
        assert kwargs["check_interval_seconds"] == 300

    def test_apply_preset_with_custom_overrides(self, svc, presets):
        svc.get_presets.return_value = presets
        svc.create_monitor.return_value = _monitor()
        self._anon().post(
            "/api/v1/monitoring/presets/apply",
            params={"agent_id": "a-1", "preset_name": "task_backlog"},
            json={
                "platforms": [{"platform": "discord", "recipient_id": "G1"}],
                "custom_overrides": {"value": 10},
            },
        )
        kwargs = svc.create_monitor.call_args.kwargs
        assert kwargs["threshold_config"] == {"metric": "pending", "operator": ">", "value": 10}

    def test_apply_preset_missing_404(self, svc, presets):
        svc.get_presets.return_value = presets
        r = self._anon().post(
            "/api/v1/monitoring/presets/apply",
            params={"agent_id": "a-1", "preset_name": "nope"},
            json={"platforms": [{"platform": "slack", "recipient_id": "C1"}]},
        )
        assert r.status_code == 404

    def test_apply_preset_missing_params_422(self, svc, presets):
        r = self._anon().post("/api/v1/monitoring/presets/apply", params={"agent_id": "a-1"})
        assert r.status_code == 422

    # -- metrics --
    def test_get_metrics(self, svc):
        svc.get_metrics.return_value = {
            "total_monitors": 5,
            "active_monitors": 3,
            "total_alerts": 12,
            "pending_alerts": 2,
            "alerts_last_24h": 4,
            "timestamp": "2026-01-01T00:00:00Z",
        }
        r = self._anon().get("/api/v1/monitoring/metrics")
        assert r.status_code == 200
        body = r.json()
        assert body["total_monitors"] == 5
        assert body["pending_alerts"] == 2

    # -- check-all --
    def test_check_all_monitors(self, svc):
        r = self._anon().post("/api/v1/monitoring/_check-monitors")
        assert r.status_code == 200
        body = r.json()
        assert body["checked"] == 3
        assert body["alerts_sent"] == 1
        svc.check_and_alert_monitors.assert_awaited_once()


# =========================================================================== #
# api/recording_review_routes.py
# =========================================================================== #
def _review(**overrides):
    r = SimpleNamespace(
        id="rv-1",
        recording_id="rec-1",
        agent_id="a-1",
        user_id="u-1",
        review_status="approved",
        overall_rating=5,
        performance_rating=4,
        safety_rating=5,
        feedback="good",
        identified_issues=[],
        positive_patterns=["x"],
        lessons_learned="l",
        confidence_delta=0.05,
        promoted=False,
        demoted=False,
        governance_notes=None,
        reviewed_by="u-1",
        reviewed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        auto_reviewed=False,
        training_value="0.8",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _recording(user_id="u-1"):
    rec = SimpleNamespace(recording_id="rec-1", user_id=user_id)
    return rec


class TestRecordingReviewRoutes:
    def _c(self, db=None, user=USER):
        from api.recording_review_routes import router

        return _client(router, db or MagicMock(), user=user)

    def _anon(self, db=None):
        from api.recording_review_routes import router

        return _anon_client(router, db or MagicMock())

    @pytest.fixture
    def svc(self):
        s = AsyncMock()
        with patch("api.recording_review_routes.get_recording_review_service", return_value=s):
            yield s

    def test_health_check(self):
        r = self._anon().get("/api/canvas/recording/review/health")
        assert r.status_code == 200
        assert r.json()["success"] is True

    # -- create --
    def test_create_review(self, svc):
        svc.create_review.return_value = "rv-1"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            _recording(), _review(),
        ]
        r = self._c(db).post("/api/canvas/recording/review", json={
            "recording_id": "rec-1", "review_status": "approved",
            "overall_rating": 5, "performance_rating": 4, "safety_rating": 5,
            "feedback": "good", "identified_issues": [], "positive_patterns": ["x"],
            "lessons_learned": "l",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["review_id"] == "rv-1"
        assert body["confidence_delta"] == 0.05
        assert body["governance_notes"] == "Review completed"
        kwargs = svc.create_review.await_args.kwargs
        assert kwargs["recording_id"] == "rec-1"
        assert kwargs["reviewer_id"] == "u-1"
        assert kwargs["auto_reviewed"] is False

    def test_create_review_with_governance_notes(self, svc):
        svc.create_review.return_value = "rv-1"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            _recording(), _review(governance_notes="noted"),
        ]
        r = self._c(db).post("/api/canvas/recording/review", json={
            "recording_id": "rec-1", "review_status": "approved",
            "overall_rating": 3, "feedback": "f",
        })
        assert r.status_code == 200
        assert r.json()["governance_notes"] == "noted"

    def test_create_review_missing_recording_404(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).post("/api/canvas/recording/review", json={
            "recording_id": "ghost", "review_status": "approved",
            "overall_rating": 3, "feedback": "f",
        })
        assert r.status_code == 404

    def test_create_review_value_error_422(self, svc):
        svc.create_review.side_effect = ValueError("bad status")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _recording()
        r = self._c(db).post("/api/canvas/recording/review", json={
            "recording_id": "rec-1", "review_status": "approved",
            "overall_rating": 3, "feedback": "f",
        })
        assert r.status_code == 422

    def test_create_review_service_error_500(self, svc):
        svc.create_review.side_effect = RuntimeError("boom")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _recording()
        r = self._c(db).post("/api/canvas/recording/review", json={
            "recording_id": "rec-1", "review_status": "approved",
            "overall_rating": 3, "feedback": "f",
        })
        assert r.status_code == 500

    def test_create_review_invalid_rating_422(self, svc):
        r = self._c().post("/api/canvas/recording/review", json={
            "recording_id": "rec-1", "review_status": "approved", "overall_rating": 9,
        })
        assert r.status_code == 422

    def test_create_review_requires_auth(self, svc):
        r = self._anon().post("/api/canvas/recording/review", json={
            "recording_id": "rec-1", "review_status": "approved",
        })
        assert r.status_code == 401

    # -- get review --
    def test_get_review_owner(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            _review(), _recording(),
        ]
        r = self._c(db).get("/api/canvas/recording/review/rv-1")
        assert r.status_code == 200
        body = r.json()
        assert body["review_id"] == "rv-1"
        assert body["review_status"] == "approved"
        assert body["reviewed_at"] is not None

    def test_get_review_missing_404(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).get("/api/canvas/recording/review/ghost")
        assert r.status_code == 404

    def test_get_review_non_owner_non_admin_403(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            _review(), _recording(user_id="someone-else"),
        ]
        r = self._c(db, user=SimpleNamespace(id="u-9", role="user")).get(
            "/api/canvas/recording/review/rv-1"
        )
        assert r.status_code == 403

    def test_get_review_admin_ok(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            _review(), _recording(user_id="someone-else"),
        ]
        r = self._c(db, user=ADMIN).get("/api/canvas/recording/review/rv-1")
        assert r.status_code == 200

    def test_get_review_exception_500(self, svc):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        r = self._c(db).get("/api/canvas/recording/review/rv-1")
        assert r.status_code == 500

    def test_get_review_requires_auth(self, svc):
        r = self._anon().get("/api/canvas/recording/review/rv-1")
        assert r.status_code == 401

    # -- list reviews for recording --
    def test_get_recording_reviews(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _recording()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _review(), _review(id="rv-2", review_status="rejected"),
        ]
        r = self._c(db).get("/api/canvas/recording/review/recording/rec-1")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 2
        assert rows[1]["review_status"] == "rejected"

    def test_get_recording_reviews_missing_404(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).get("/api/canvas/recording/review/recording/ghost")
        assert r.status_code == 404

    def test_get_recording_reviews_other_user_403(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _recording(user_id="x")
        r = self._c(db, user=SimpleNamespace(id="u-9", role="user")).get(
            "/api/canvas/recording/review/recording/rec-1"
        )
        assert r.status_code == 403

    def test_get_recording_reviews_exception_500(self, svc):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        r = self._c(db).get("/api/canvas/recording/review/recording/rec-1")
        assert r.status_code == 500

    # -- agent metrics --
    def test_agent_metrics(self, svc):
        svc.get_review_metrics.return_value = {
            "agent_id": "a-1", "total_reviews": 10, "approval_rate": 0.8,
            "average_rating": 4.2, "confidence_impact": 0.1,
            "common_issues": [], "strengths": [], "training_recordings": 3,
        }
        r = self._c().get("/api/canvas/recording/review/agent/a-1/metrics?days=7")
        assert r.status_code == 200
        assert r.json()["approval_rate"] == 0.8
        svc.get_review_metrics.assert_awaited_once_with(agent_id="a-1", days=7)

    def test_agent_metrics_error_500(self, svc):
        svc.get_review_metrics.side_effect = RuntimeError("boom")
        r = self._c().get("/api/canvas/recording/review/agent/a-1/metrics")
        assert r.status_code == 500

    # -- auto-review --
    def test_trigger_auto_review_created(self, svc):
        svc.auto_review_recording.return_value = "rv-2"
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _recording()
        r = self._c(db).post("/api/canvas/recording/review/recording/rec-1/auto-review")
        assert r.status_code == 200
        assert r.json()["data"]["review_id"] == "rv-2"
        svc.auto_review_recording.assert_awaited_once_with("rec-1")

    def test_trigger_auto_review_skipped(self, svc):
        svc.auto_review_recording.return_value = None
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _recording()
        r = self._c(db).post("/api/canvas/recording/review/recording/rec-1/auto-review")
        assert r.status_code == 200
        assert r.json()["data"]["review_id"] is None
        assert r.json()["message"] == "Auto-review skipped (low confidence or disabled)"

    def test_trigger_auto_review_missing_404(self, svc):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        r = self._c(db).post("/api/canvas/recording/review/recording/ghost/auto-review")
        assert r.status_code == 404

    def test_trigger_auto_review_exception_500(self, svc):
        db = MagicMock()
        db.query.side_effect = RuntimeError("boom")
        r = self._c(db).post("/api/canvas/recording/review/recording/rec-1/auto-review")
        assert r.status_code == 500
