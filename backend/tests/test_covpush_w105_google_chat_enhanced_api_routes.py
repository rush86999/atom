"""Coverage wave 105 — integrations/google_chat_enhanced_api_routes.py
(TDD, 0% baseline — module was UNIMPORTABLE).

Fully mocked (module-level google_chat_service instance patched, fake
get_current_user, universal_webhook_bridge patched), zero network, zero LLM
spend.

BUG FOUND #1 (TDD RED->GREEN): line 12 imported
`google_chat_enhanced_service` from integrations.google_chat_enhanced_service
but that singleton does NOT exist there (the module-level instantiation is
commented out at google_chat_enhanced_service.py:1125) -> ImportError at
module import -> the whole google_chat router was dead on load via the lazy
registry (load_integration returns None). Fixed by importing the
GoogleChatEnhancedService class and instantiating the module-level
`google_chat_service` (mirrors the xero/mailchimp route pattern).

BUG FOUND #2 (TDD RED->GREEN): POST /send called
`send_message(space_name=..., thread_name=...)` but the service signature is
`send_message(space_id, text, thread_id=None, ...)` -> TypeError -> the
endpoint ALWAYS returned 500 "Internal error". Fixed by mapping the request
fields to the service kwargs (space_id / thread_id) in the handler.

BUG FOUND #3 (TDD RED->GREEN): POST /send and GET /spaces had NO
authentication. The anonymous-401 tests below were RED (200) before the fix;
`get_current_user` is now required on both data endpoints. (/health and
/webhook stay public: the webhook is an inbound external callback.)

Covers: /health (public), /webhook (MESSAGE dispatches to the universal
bridge, non-MESSAGE does not dispatch, invalid JSON -> 500), /send (success
with thread, success without thread, service failure -> 500, missing
space_name -> 422, missing text -> 422, anon 401), /spaces (public? no —
success + anon 401 after auth fix).
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.models import User

from integrations import google_chat_enhanced_api_routes as gcr


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = "gchat105-user"
    u.email = "gchat105@x.com"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(gcr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(gcr.router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _svc():
    with patch.object(gcr.google_chat_service, "send_message",
                      new=AsyncMock(return_value={"ok": True, "message_id": "m1"})), \
            patch.object(gcr.universal_webhook_bridge,
                         "process_incoming_message", new=AsyncMock()):
        yield gcr.google_chat_service


class TestHealth:
    def test_health(self, anon_client):
        response = anon_client.get("/api/google_chat/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["service"] == "Google Chat"


class TestWebhook:
    def test_message_dispatches(self, anon_client):
        captured = []
        with patch.object(gcr.asyncio, "create_task",
                          new=lambda coro: captured.append(coro) or coro):
            response = anon_client.post(
                "/api/google_chat/webhook",
                json={"type": "MESSAGE", "message": {"text": "hi", "space": {"name": "s/1"}}})
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert len(captured) == 1
        asyncio.run(captured[0])
        gcr.universal_webhook_bridge.process_incoming_message \
            .assert_awaited_once_with("google_chat", {"text": "hi", "space": {"name": "s/1"}})

    def test_non_message_no_dispatch(self, anon_client):
        with patch.object(gcr.asyncio, "create_task") as create_task:
            response = anon_client.post(
                "/api/google_chat/webhook",
                json={"type": "ADDED_TO_SPACE"})
        assert response.status_code == 200
        create_task.assert_not_called()

    def test_no_type_no_dispatch(self, anon_client):
        with patch.object(gcr.asyncio, "create_task") as create_task:
            response = anon_client.post("/api/google_chat/webhook", json={})
        assert response.status_code == 200
        create_task.assert_not_called()

    def test_invalid_json_500(self, anon_client):
        response = anon_client.post(
            "/api/google_chat/webhook",
            content=b"{not json",
            headers={"Content-Type": "application/json"})
        assert response.status_code == 500


class TestSendMessage:
    def test_success(self, client):
        response = client.post(
            "/api/google_chat/send",
            json={"space_name": "spaces/AAA", "text": "hello"})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["result"] == {"ok": True, "message_id": "m1"}
        gcr.google_chat_service.send_message.assert_awaited_once_with(
            space_id="spaces/AAA", text="hello", thread_id=None)

    def test_success_with_thread(self, client):
        response = client.post(
            "/api/google_chat/send",
            json={"space_name": "spaces/AAA", "text": "hello",
                  "thread_name": "spaces/AAA/threads/1"})
        assert response.status_code == 200
        gcr.google_chat_service.send_message.assert_awaited_once_with(
            space_id="spaces/AAA", text="hello",
            thread_id="spaces/AAA/threads/1")

    def test_service_failure_500(self, client):
        gcr.google_chat_service.send_message.side_effect = RuntimeError("boom")
        response = client.post(
            "/api/google_chat/send",
            json={"space_name": "spaces/AAA", "text": "hello"})
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal error"

    def test_missing_space_name_422(self, client):
        response = client.post("/api/google_chat/send", json={"text": "hello"})
        assert response.status_code == 422

    def test_missing_text_422(self, client):
        response = client.post("/api/google_chat/send",
                               json={"space_name": "spaces/AAA"})
        assert response.status_code == 422

    def test_anonymous_401(self, anon_client):
        response = anon_client.post(
            "/api/google_chat/send",
            json={"space_name": "spaces/AAA", "text": "hello"})
        assert response.status_code == 401


class TestListSpaces:
    def test_success(self, client):
        response = client.get("/api/google_chat/spaces")
        assert response.status_code == 200
        assert response.json() == {"spaces": []}

    def test_anonymous_401(self, anon_client):
        response = anon_client.get("/api/google_chat/spaces")
        assert response.status_code == 401
