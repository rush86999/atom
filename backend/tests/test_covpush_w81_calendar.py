"""Coverage wave 81 — core/unified_calendar_endpoints.py (0% → ~100%).

Covers the 6 calendar routes: CRUD on MOCK_EVENTS, conflict detection,
schedule optimization, request validation (BUG-068 end>=start on BOTH create
and update), and — the wave's real-bug fixes — authentication on every
endpoint (the router is mounted at root in main_api_app via the lazy
integration registry, so all six routes answered anonymous CRUD in
production) plus the missing end>=start guard on UpdateEventRequest.
"""
import copy
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.unified_calendar_endpoints as cal
from core.auth import get_current_user
from core.unified_calendar_endpoints import (
    CalendarEvent,
    ConflictCheckRequest,
    CreateEventRequest,
    UpdateEventRequest,
)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(cal.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "tenant_id": "t1"}
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def events_snapshot():
    snapshot = copy.deepcopy(cal.MOCK_EVENTS)
    yield
    cal.MOCK_EVENTS = snapshot


def _now():
    return datetime.now().replace(microsecond=0)


class TestAuthentication:
    """REAL BUG (wave fix): all six calendar routes ran unauthenticated."""

    def test_anon_get_events_401(self):
        app = FastAPI()
        app.include_router(cal.router)
        resp = TestClient(app).get("/api/v1/calendar/events")
        assert resp.status_code == 401

    def test_anon_create_event_401(self):
        app = FastAPI()
        app.include_router(cal.router)
        resp = TestClient(app).post(
            "/api/v1/calendar/events",
            json={"title": "x", "start": _now().isoformat(),
                  "end": (_now() + timedelta(hours=1)).isoformat()})
        assert resp.status_code == 401

    def test_anon_update_event_401(self):
        app = FastAPI()
        app.include_router(cal.router)
        resp = TestClient(app).put(
            "/api/v1/calendar/events/1", json={"title": "x"})
        assert resp.status_code == 401

    def test_anon_delete_event_401(self):
        app = FastAPI()
        app.include_router(cal.router)
        resp = TestClient(app).delete("/api/v1/calendar/events/1")
        assert resp.status_code == 401

    def test_anon_check_conflicts_401(self):
        app = FastAPI()
        app.include_router(cal.router)
        resp = TestClient(app).post(
            "/api/v1/calendar/check-conflicts",
            json={"start": _now().isoformat(),
                  "end": (_now() + timedelta(hours=1)).isoformat()})
        assert resp.status_code == 401

    def test_anon_optimize_401(self):
        app = FastAPI()
        app.include_router(cal.router)
        resp = TestClient(app).get("/api/v1/calendar/optimize")
        assert resp.status_code == 401


class TestGetEvents:
    def test_get_all_events(self, client, events_snapshot):
        resp = client.get("/api/v1/calendar/events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["events"]) == len(cal.MOCK_EVENTS)

    def test_get_events_filtered_by_start(self, client, events_snapshot):
        resp = client.get("/api/v1/calendar/events",
                          params={"start": _now().replace(hour=11, minute=0).isoformat()})
        events = resp.json()["events"]
        titles = [e["title"] for e in events]
        assert "Project Review" in titles
        assert "Team Standup" not in titles

    def test_get_events_filtered_by_end(self, client, events_snapshot):
        early = _now().replace(hour=6, minute=0)
        resp = client.get("/api/v1/calendar/events",
                          params={"end": early.isoformat()})
        assert resp.status_code == 200

    def test_get_events_both_bounds(self, client, events_snapshot):
        start = _now() - timedelta(hours=1)
        end = _now() + timedelta(hours=5)
        resp = client.get("/api/v1/calendar/events",
                          params={"start": start.isoformat(),
                                  "end": end.isoformat()})
        assert resp.status_code == 200


class TestCreateEvent:
    def test_create_event_full(self, client, events_snapshot):
        start = _now() + timedelta(days=2)
        resp = client.post("/api/v1/calendar/events", json={
            "title": "New Sync",
            "description": "desc",
            "start": start.isoformat(),
            "end": (start + timedelta(minutes=45)).isoformat(),
            "location": "Office",
            "status": "confirmed",
            "platform": "google",
            "color": "#FF0000",
            "metadata": {"deal_id": "d-1"},
            "attendees": [{"id": "a", "name": "Alice", "email": "a@x.io",
                           "role": "required"}],
        })
        assert resp.status_code == 200
        event = resp.json()["event"]
        assert event["title"] == "New Sync"
        assert event["id"]
        assert len(cal.MOCK_EVENTS) == 3

    def test_create_event_defaults(self, client, events_snapshot):
        start = _now() + timedelta(days=3)
        resp = client.post("/api/v1/calendar/events", json={
            "title": "Defaults",
            "start": start.isoformat(),
            "end": (start + timedelta(hours=1)).isoformat(),
        })
        event = resp.json()["event"]
        assert event["status"] == "confirmed"
        assert event["platform"] == "local"
        assert event["color"] == "#3182CE"
        assert event["attendees"] == []

    def test_create_event_end_before_start_422(self, client, events_snapshot):
        start = _now() + timedelta(days=4)
        resp = client.post("/api/v1/calendar/events", json={
            "title": "Bad",
            "start": start.isoformat(),
            "end": (start - timedelta(hours=1)).isoformat(),
        })
        assert resp.status_code == 422
        assert "Event end time must be after or equal to start time" in resp.text

    def test_create_event_missing_title_422(self, client, events_snapshot):
        start = _now() + timedelta(days=5)
        resp = client.post("/api/v1/calendar/events", json={
            "start": start.isoformat(),
            "end": (start + timedelta(hours=1)).isoformat(),
        })
        assert resp.status_code == 422


class TestUpdateEvent:
    def test_update_title_only(self, client, events_snapshot):
        resp = client.put("/api/v1/calendar/events/1", json={"title": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["event"]["title"] == "Renamed"
        assert resp.json()["event"]["description"] == "Daily sync"

    def test_update_full_event(self, client, events_snapshot):
        start = _now() + timedelta(days=6)
        resp = client.put("/api/v1/calendar/events/1", json={
            "title": "Moved",
            "description": "new desc",
            "start": start.isoformat(),
            "end": (start + timedelta(hours=2)).isoformat(),
            "location": "Remote",
            "status": "tentative",
            "platform": "outlook",
            "color": "#00FF00",
        })
        assert resp.status_code == 200
        assert resp.json()["event"]["platform"] == "outlook"

    def test_update_not_found_404(self, client, events_snapshot):
        resp = client.put("/api/v1/calendar/events/nope", json={"title": "x"})
        assert resp.status_code == 404

    def test_update_end_before_start_422(self, client, events_snapshot):
        """REAL BUG (wave fix): UpdateEventRequest had no end>=start guard —
        PUT could silently create invalid events (BUG-068 parity with create)."""
        start = _now() + timedelta(days=7)
        resp = client.put("/api/v1/calendar/events/1", json={
            "start": start.isoformat(),
            "end": (start - timedelta(hours=1)).isoformat(),
        })
        assert resp.status_code == 422

    def test_update_end_without_start_ok(self, client, events_snapshot):
        future_end = _now() + timedelta(days=8)
        resp = client.put("/api/v1/calendar/events/1",
                          json={"end": future_end.isoformat()})
        assert resp.status_code == 200

    def test_update_model_validator_direct(self):
        start = _now() + timedelta(days=9)
        with pytest.raises(ValueError):
            UpdateEventRequest(start=start,
                               end=start - timedelta(minutes=5))


class TestDeleteEvent:
    def test_delete_event(self, client, events_snapshot):
        resp = client.delete("/api/v1/calendar/events/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "1"
        assert len(cal.MOCK_EVENTS) == 1

    def test_delete_event_not_found_404(self, client, events_snapshot):
        resp = client.delete("/api/v1/calendar/events/ghost")
        assert resp.status_code == 404

    def test_delete_then_404(self, client, events_snapshot):
        assert client.delete("/api/v1/calendar/events/2").status_code == 200
        assert client.delete("/api/v1/calendar/events/2").status_code == 404


class TestCheckConflicts:
    def _window(self, base, hours=1):
        return {"start": base.isoformat(),
                "end": (base + timedelta(hours=hours)).isoformat()}

    def test_no_conflict(self, client, events_snapshot):
        resp = client.post("/api/v1/calendar/check-conflicts",
                           json=self._window(_now().replace(hour=23, minute=59)))
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_conflicts"] is False
        assert body["conflict_count"] == 0
        assert "No conflicts" in body["message"]

    def test_conflict_hit(self, client, events_snapshot):
        resp = client.post("/api/v1/calendar/check-conflicts",
                           json=self._window(_now().replace(hour=9, minute=55)))
        body = resp.json()
        assert body["has_conflicts"] is True
        assert body["conflict_count"] >= 1
        assert any(c["title"] == "Team Standup" for c in body["conflicts"])
        assert "conflict detected" in body["message"]

    def test_conflict_excluded_event(self, client, events_snapshot):
        resp = client.post("/api/v1/calendar/check-conflicts", json={
            "start": _now().replace(hour=9, minute=55).isoformat(),
            "end": _now().replace(hour=11, minute=0).isoformat(),
            "exclude_event_id": "1",
        })
        body = resp.json()
        assert body["has_conflicts"] is False
        assert body["conflict_count"] == 0

    def test_conflict_request_model_validation(self, client, events_snapshot):
        resp = client.post("/api/v1/calendar/check-conflicts", json={})
        assert resp.status_code == 422


class TestOptimize:
    def _optimizer_patch(self, conflicts=None, slots=None):
        optimizer = MagicMock()
        optimizer.detect_all_conflicts = AsyncMock(return_value=conflicts or [])
        optimizer.find_resolution_slots = AsyncMock(return_value=slots or [])
        return optimizer

    def test_optimize_no_conflicts(self, client, events_snapshot):
        with patch.object(cal, "schedule_optimizer",
                          self._optimizer_patch()):
            resp = client.get("/api/v1/calendar/optimize")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_optimize_with_resolution(self, client, events_snapshot):
        e1 = {"id": "1", "title": "Team Standup"}
        e2 = {"id": "2", "title": "Project Review"}
        slot = cal.ResolutionSlot(
            start=_now() + timedelta(days=1, hours=2),
            end=_now() + timedelta(days=1, hours=3),
            reason="free gap")
        conflicts = [{"event1": e1, "event2": e2, "priority1": 5, "priority2": 3}]
        with patch.object(cal, "schedule_optimizer",
                          self._optimizer_patch(conflicts, [slot])):
            resp = client.get("/api/v1/calendar/optimize")
        resolutions = resp.json()
        assert len(resolutions) == 1
        r = resolutions[0]
        assert r["event_to_move"] == "Project Review"
        assert r["event_id"] == "2"
        assert r["event_priority"] == 3
        assert r["conflict_with"] == "Team Standup"
        assert r["suggested_slots"][0]["reason"] == "free gap"

    def test_optimize_no_slots(self, client, events_snapshot):
        e1 = {"id": "1", "title": "Team Standup"}
        e2 = {"id": "2", "title": "Project Review"}
        conflicts = [{"event1": e1, "event2": e2, "priority1": 5, "priority2": 3}]
        with patch.object(cal, "schedule_optimizer",
                          self._optimizer_patch(conflicts, [])):
            resp = client.get("/api/v1/calendar/optimize")
        assert resp.json() == []

    def test_optimize_priority_swap(self, client, events_snapshot):
        e1 = {"id": "1", "title": "Team Standup"}
        e2 = {"id": "2", "title": "Project Review"}
        conflicts = [{"event1": e1, "event2": e2, "priority1": 2, "priority2": 9}]
        with patch.object(cal, "schedule_optimizer",
                          self._optimizer_patch(conflicts, [MagicMock()])):
            resp = client.get("/api/v1/calendar/optimize")
        resolutions = resp.json()
        assert resolutions[0]["event_to_move"] == "Team Standup"
        assert resolutions[0]["event_id"] == "1"
