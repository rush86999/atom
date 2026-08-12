"""Coverage wave 54 — api/messaging_routes.py (TDD).

Existing suite (tests/unit/api/test_messaging_routes.py) targets phantom
`/api/messaging/messages` routes (real prefix is /api/v1/messaging) — this wave
tests the actual proactive-messaging endpoints via a mocked
ProactiveMessagingService:
- _require_scheduler_secret (fail-closed 401 unset/mismatch, 200 match)
- send (success, service-403 propagate)
- schedule (missing scheduled_for → 422, success)
- queue (filters, defaults)
- approve (token attribution, success)
- reject (token attribution, missing reason 422, success)
- cancel (success)
- history (filters)
- get by id (found, not-found 404)
- send_scheduled (scheduler-secret gated, success)
"""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.models  # noqa: F401
from api.messaging_routes import router
from core.models import User


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = f"mu-{uuid.uuid4().hex[:8]}"
    u.email = "m@x.com"
    u.tenant_id = "t-1"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(router)

    from core.auth import get_current_user
    from core.database import get_db

    def _get_db():
        from core.database import SessionLocal
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


def _msg_resp(status="PENDING", msg_id="msg-1"):
    return {
        "id": msg_id,
        "agent_id": "agent-1",
        "agent_name": "Agent",
        "agent_maturity_level": "autonomous",
        "platform": "slack",
        "recipient_id": "chan-1",
        "content": "Hello",
        "scheduled_for": None,
        "send_now": True,
        "status": status,
        "approved_by": None,
        "approved_at": None,
        "rejection_reason": None,
        "sent_at": None,
        "error_message": None,
        "platform_message_id": None,
        "created_at": "2026-08-12T00:00:00Z",
        "updated_at": None,
    }


@pytest.fixture
def svc():
    s = MagicMock()
    s.create_proactive_message.return_value = _msg_resp()
    s.get_pending_messages.return_value = []
    s.approve_message.return_value = _msg_resp("APPROVED")
    s.reject_message.return_value = _msg_resp("CANCELLED")
    s.cancel_message.return_value = _msg_resp("CANCELLED")
    s.get_message_history.return_value = []
    s.get_message.return_value = None
    s.send_scheduled_messages = AsyncMock(
        return_value={"sent": 1, "failed": 0})
    with patch("api.messaging_routes.ProactiveMessagingService",
               return_value=s):
        yield s


def _msg(**over):
    base = {
        "agent_id": "agent-1",
        "platform": "slack",
        "recipient_id": "chan-1",
        "content": "Hello",
        "send_now": True,
    }
    base.update(over)
    return base


class TestSend:
    def test_send_success(self, client, svc):
        response = client.post(
            "/api/v1/messaging/proactive/send", json=_msg())
        assert response.status_code == 200
        assert response.json()["id"] == "msg-1"
        kwargs = svc.create_proactive_message.call_args.kwargs
        assert kwargs["agent_id"] == "agent-1"
        assert kwargs["send_now"] is True

    def test_send_service_403_propagates(self, client, svc):
        from fastapi import HTTPException
        svc.create_proactive_message.side_effect = HTTPException(
            status_code=403, detail="STUDENT blocked")
        response = client.post(
            "/api/v1/messaging/proactive/send", json=_msg())
        assert response.status_code == 403

    def test_send_422_missing_fields(self, client, svc):
        response = client.post("/api/v1/messaging/proactive/send", json={})
        assert response.status_code == 422


class TestSchedule:
    def test_schedule_missing_time_422(self, client, svc):
        response = client.post(
            "/api/v1/messaging/proactive/schedule", json=_msg())
        assert response.status_code == 422

    def test_schedule_success(self, client, svc):
        response = client.post(
            "/api/v1/messaging/proactive/schedule",
            json=_msg(scheduled_for="2030-01-01T00:00:00Z"))
        assert response.status_code == 200
        kwargs = svc.create_proactive_message.call_args.kwargs
        assert kwargs["send_now"] is False
        assert kwargs["scheduled_for"] is not None


class TestQueue:
    def test_queue_no_filters(self, client, svc):
        response = client.get("/api/v1/messaging/proactive/queue")
        assert response.status_code == 200
        svc.get_pending_messages.assert_called_once_with(
            agent_id=None, platform=None, limit=100)

    def test_queue_with_filters(self, client, svc):
        response = client.get(
            "/api/v1/messaging/proactive/queue",
            params={"agent_id": "agent-1", "platform": "slack", "limit": 5})
        assert response.status_code == 200
        svc.get_pending_messages.assert_called_once_with(
            agent_id="agent-1", platform="slack", limit=5)


class TestApprove:
    def test_approve_uses_token_identity(self, client, svc, user):
        response = client.post(
            "/api/v1/messaging/proactive/approve/msg-1", json={})
        assert response.status_code == 200
        svc.approve_message.assert_called_once_with(
            message_id="msg-1", approver_user_id=user.id)


class TestReject:
    def test_reject_missing_reason_422(self, client, svc):
        response = client.post(
            "/api/v1/messaging/proactive/reject/msg-1", json={})
        assert response.status_code == 422

    def test_reject_success(self, client, svc, user):
        response = client.post(
            "/api/v1/messaging/proactive/reject/msg-1",
            json={"rejection_reason": "spam"})
        assert response.status_code == 200
        svc.reject_message.assert_called_once_with(
            message_id="msg-1", rejecter_user_id=user.id,
            rejection_reason="spam")


class TestCancel:
    def test_cancel_success(self, client, svc):
        response = client.delete(
            "/api/v1/messaging/proactive/cancel/msg-1")
        assert response.status_code == 200
        svc.cancel_message.assert_called_once_with(message_id="msg-1")


class TestHistory:
    def test_history_defaults(self, client, svc):
        response = client.get("/api/v1/messaging/proactive/history")
        assert response.status_code == 200
        svc.get_message_history.assert_called_once_with(
            agent_id=None, recipient_id=None, platform=None,
            status=None, limit=100)

    def test_history_with_filters(self, client, svc):
        response = client.get(
            "/api/v1/messaging/proactive/history",
            params={"agent_id": "a1", "recipient_id": "r1",
                    "platform": "slack", "message_status": "SENT",
                    "limit": 10})
        assert response.status_code == 200
        svc.get_message_history.assert_called_once_with(
            agent_id="a1", recipient_id="r1", platform="slack",
            status="SENT", limit=10)


class TestGetMessage:
    def test_get_found(self, client, svc):
        svc.get_message.return_value = _msg_resp("SENT")
        response = client.get("/api/v1/messaging/proactive/msg-1")
        assert response.status_code == 200
        svc.get_message.assert_called_once_with(message_id="msg-1")

    def test_get_not_found_404(self, client, svc):
        response = client.get("/api/v1/messaging/proactive/ghost")
        assert response.status_code == 404


class TestSendScheduled:
    def test_missing_secret_401(self, client, svc, monkeypatch):
        monkeypatch.delenv("ATOM_SCHEDULER_SECRET", raising=False)
        response = client.post("/api/v1/messaging/proactive/_send_scheduled")
        assert response.status_code == 401

    def test_wrong_secret_401(self, client, svc, monkeypatch):
        monkeypatch.setenv("ATOM_SCHEDULER_SECRET", "real-secret")
        response = client.post(
            "/api/v1/messaging/proactive/_send_scheduled",
            headers={"X-Scheduler-Secret": "wrong"})
        assert response.status_code == 401

    def test_correct_secret_success(self, client, svc, monkeypatch):
        monkeypatch.setenv("ATOM_SCHEDULER_SECRET", "real-secret")
        response = client.post(
            "/api/v1/messaging/proactive/_send_scheduled",
            headers={"X-Scheduler-Secret": "real-secret"})
        assert response.status_code == 200
        assert response.json()["sent"] == 1
        svc.send_scheduled_messages.assert_awaited_once()
