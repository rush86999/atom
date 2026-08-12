"""Coverage wave 56 — api/canvas_recording_routes.py (TDD).

Existing suite (tests/unit/api/test_canvas_recording_routes.py) is a phantom
smoke suite (play/pause/download endpoints don't exist). This wave tests the
real endpoints with a mocked `get_canvas_recording_service` + a real
CanvasRecording row for the flag path:
- health, start (success + 500), event (success + 500), stop (success + 500)
- get (success, not-found 404, ownership 403, 500)
- list (success/empty/500)
- flag (success w/ DB row, not-found 404, service 500)
- replay (success, 404, 403, 500)
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.models  # noqa: F401
from api.canvas_recording_routes import router
from core.database import Base
from core.models import CanvasRecording, User


@pytest.fixture(scope="module")
def engine():
    import os
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    os.unlink(path)


@pytest.fixture
def db(engine):
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def user(db):
    uid = f"ru-{uuid.uuid4().hex[:8]}"
    u = User(
        id=uid, email=f"{uid}@x.com",
        hashed_password="h", first_name="R", last_name="U",
        role="member", status="active", tenant_id="t-1")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def client(db, user):
    app = FastAPI()
    app.include_router(router)

    from core.database import get_db
    from core.security_dependencies import get_current_user

    def _get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


def _recording_dict(user_id="u-1", recording_id="rec-1"):
    return {
        "recording_id": recording_id,
        "agent_id": "agent-1",
        "user_id": user_id,
        "canvas_id": "c-1",
        "session_id": "s-1",
        "reason": "manual",
        "status": "recording",
        "tags": ["test"],
        "started_at": "2026-08-12T00:00:00Z",
        "stopped_at": None,
        "duration_seconds": 12.5,
        "event_count": 2,
        "summary": None,
        "events": [{"type": "update"}],
        "recording_metadata": {"source": "test"},
        "expires_at": None,
        "flagged_for_review": False,
    }


@pytest.fixture
def svc():
    s = MagicMock()
    s.start_recording = AsyncMock(return_value="rec-1")
    s.record_event = AsyncMock()
    s.stop_recording = AsyncMock()
    s.get_recording = AsyncMock(return_value=_recording_dict())
    s.list_recordings = AsyncMock(return_value=[])
    s.flag_for_review = AsyncMock()
    with patch("api.canvas_recording_routes.get_canvas_recording_service",
               return_value=s):
        yield s


def _row(db, user, recording_id=None):
    rid = recording_id or f"rec-{uuid.uuid4().hex[:8]}"
    row = CanvasRecording(
        id=f"cr-{uuid.uuid4().hex[:8]}", recording_id=rid,
        tenant_id="t-1", user_id=user.id, agent_id="agent-1",
        reason="manual", status="recording")
    db.add(row)
    db.commit()
    return rid


class TestHealth:
    def test_health(self, client):
        response = client.get("/api/canvas/recording/health")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "healthy"


class TestStart:
    def test_start_success(self, client, svc, user):
        response = client.post("/api/canvas/recording/start", json={
            "agent_id": "agent-1", "canvas_id": "c-1",
            "reason": "manual", "session_id": "s-1",
            "tags": ["a", "b"]})
        assert response.status_code == 200
        data = response.json()
        assert data["recording_id"] == "rec-1"
        assert data["user_id"] == user.id
        assert data["status"] == "recording"
        kwargs = svc.start_recording.call_args.kwargs
        assert kwargs["tags"] == ["a", "b"]

    def test_start_service_error_500(self, client, svc):
        svc.start_recording.side_effect = RuntimeError("boom")
        response = client.post("/api/canvas/recording/start", json={
            "agent_id": "agent-1", "reason": "manual"})
        assert response.status_code == 500

    def test_start_missing_fields_422(self, client, svc):
        response = client.post("/api/canvas/recording/start", json={})
        assert response.status_code == 422


class TestRecordEvent:
    def test_event_success(self, client, svc):
        response = client.post("/api/canvas/recording/rec-1/event", json={
            "event_type": "update", "event_data": {"x": 1}})
        assert response.status_code == 200
        svc.record_event.assert_awaited_once_with(
            recording_id="rec-1", event_type="update", event_data={"x": 1})

    def test_event_service_error_500(self, client, svc):
        svc.record_event.side_effect = RuntimeError("boom")
        response = client.post("/api/canvas/recording/rec-1/event", json={
            "event_type": "update", "event_data": {}})
        assert response.status_code == 500


class TestStop:
    def test_stop_success(self, client, svc):
        response = client.post("/api/canvas/recording/rec-1/stop", json={
            "status": "completed", "summary": "done"})
        assert response.status_code == 200
        svc.stop_recording.assert_awaited_once_with(
            recording_id="rec-1", status="completed", summary="done")

    def test_stop_default_status(self, client, svc):
        response = client.post("/api/canvas/recording/rec-1/stop", json={})
        assert response.status_code == 200
        assert svc.stop_recording.call_args.kwargs["status"] == "completed"

    def test_stop_service_error_500(self, client, svc):
        svc.stop_recording.side_effect = RuntimeError("boom")
        response = client.post("/api/canvas/recording/rec-1/stop", json={})
        assert response.status_code == 500


class TestGet:
    def test_get_success(self, client, svc, user):
        svc.get_recording.return_value = _recording_dict(user_id=user.id)
        response = client.get("/api/canvas/recording/rec-1")
        assert response.status_code == 200
        data = response.json()
        assert data["recording_id"] == "rec-1"
        assert data["event_count"] == 2

    def test_get_not_found_404(self, client, svc):
        svc.get_recording.return_value = None
        response = client.get("/api/canvas/recording/ghost")
        assert response.status_code == 404

    def test_get_ownership_denied_403(self, client, svc, user):
        svc.get_recording.return_value = _recording_dict(user_id="someone-else")
        response = client.get("/api/canvas/recording/rec-1")
        assert response.status_code == 403

    def test_get_service_error_500(self, client, svc):
        svc.get_recording.side_effect = RuntimeError("boom")
        response = client.get("/api/canvas/recording/rec-1")
        assert response.status_code == 500


class TestList:
    def test_list_success(self, client, svc, user):
        svc.list_recordings.return_value = [
            _recording_dict(user_id=user.id, recording_id="a"),
            _recording_dict(user_id=user.id, recording_id="b")]
        response = client.get("/api/canvas/recording")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["total"] == 2
        assert len(data["data"]) == 2
        svc.list_recordings.assert_awaited_once_with(
            user_id=user.id, agent_id=None, limit=50, offset=0)

    def test_list_with_filters(self, client, svc, user):
        response = client.get(
            "/api/canvas/recording?agent_id=agent-1&limit=10&offset=5")
        assert response.status_code == 200
        svc.list_recordings.assert_awaited_once_with(
            user_id=user.id, agent_id="agent-1", limit=10, offset=5)

    def test_list_service_error_500(self, client, svc):
        svc.list_recordings.side_effect = RuntimeError("boom")
        response = client.get("/api/canvas/recording")
        assert response.status_code == 500


class TestFlag:
    def test_flag_success(self, client, db, user, svc):
        rid = _row(db, user)
        response = client.post(f"/api/canvas/recording/{rid}/flag", json={
            "flag_reason": "suspicious_activity"})
        assert response.status_code == 200
        svc.flag_for_review.assert_awaited_once_with(
            recording_id=rid, flag_reason="suspicious_activity",
            flagged_by=user.id)

    def test_flag_not_found_404(self, client, db, user, svc):
        response = client.post("/api/canvas/recording/ghost/flag", json={
            "flag_reason": "x"})
        assert response.status_code == 404
        svc.flag_for_review.assert_not_awaited()

    def test_flag_other_users_recording_404(self, client, db, user, svc):
        other = User(
            id=f"other-{uuid.uuid4().hex[:8]}", email="o2@x.com",
            hashed_password="h", first_name="O", last_name="U",
            role="member", status="active", tenant_id="t-1")
        db.add(other)
        db.commit()
        rid = _row(db, other)
        response = client.post(f"/api/canvas/recording/{rid}/flag", json={
            "flag_reason": "x"})
        assert response.status_code == 404

    def test_flag_service_error_500(self, client, db, user, svc):
        rid = _row(db, user)
        svc.flag_for_review.side_effect = RuntimeError("boom")
        response = client.post(f"/api/canvas/recording/{rid}/flag", json={
            "flag_reason": "x"})
        assert response.status_code == 500


class TestReplay:
    def test_replay_success(self, client, svc, user):
        svc.get_recording.return_value = _recording_dict(user_id=user.id)
        response = client.get("/api/canvas/recording/rec-1/replay")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["recording_id"] == "rec-1"
        assert data["events"] == [{"type": "update"}]
        assert data["recording_metadata"] == {"source": "test"}

    def test_replay_not_found_404(self, client, svc):
        svc.get_recording.return_value = None
        response = client.get("/api/canvas/recording/rec-1/replay")
        assert response.status_code == 404

    def test_replay_ownership_denied_403(self, client, svc, user):
        svc.get_recording.return_value = _recording_dict(user_id="someone-else")
        response = client.get("/api/canvas/recording/rec-1/replay")
        assert response.status_code == 403

    def test_replay_service_error_500(self, client, svc):
        svc.get_recording.side_effect = RuntimeError("boom")
        response = client.get("/api/canvas/recording/rec-1/replay")
        assert response.status_code == 500
