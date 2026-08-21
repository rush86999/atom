"""Coverage wave 96 — integrations/telegram_routes.py (TDD, 0% baseline).

BUGS FOUND + FIXED (wave 96, TDD RED->GREEN):

1. Webhook FAIL-OPEN (line ~58): with the secret env var unset the handler
   logged a warning and ACCEPTED all requests ("accepts all requests") —
   the opposite of its own comment ("Fails closed: rejects ... if not
   configured at all") and of the project R45/R69 webhook convention
   (ATOM_<PROVIDER>_WEBHOOK_SECRET fail-closed; cf. teams/gmail/whatsapp
   401/503 when unconfigured). It also read the NON-canonical env name
   TELEGRAM_WEBHOOK_SECRET_TOKEN. Now reads ATOM_TELEGRAM_WEBHOOK_SECRET
   (canonical) with TELEGRAM_WEBHOOK_SECRET_TOKEN as a legacy fallback,
   and FAILS CLOSED (401) when neither is configured. RED:
   test_webhook_no_secret_fails_closed_401 (200 before fix).

2. NO AUTH on the router: every endpoint answered anonymous callers —
   `/send`, `/send-photo`, `/send-poll`, `/send-keyboard`, `/edit-keyboard`,
   `/answer-callback`, `/answer-inline`, `/send-chat-action`,
   `/get-chat-info/{id}`, `/workspaces/{user_id}` (leaks another user's
   workspaces), `/status`, `/capabilities`. The sibling slack_routes router
   requires get_current_user on its endpoints; this router is mounted at
   /api/v1/integrations/telegram in main_api_app.py. get_current_user now
   gates every endpoint EXCEPT /webhook (secret-token-authed by design) and
   /health (public health convention, cf. dropbox/notion). RED: 12
   parametrized anonymous-401 tests (200 before fix).

Covers: webhook secret ok/mismatch/missing/invalid-JSON/callback_query/
inline_query/message governance (verify+permissions+bridge, audit trails,
reject paths, bridge failure 500), health (active/inactive/exception),
status, workspaces, and every interactive/message/utility endpoint
success + failure-500 + 422.
"""
import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import get_current_user
from core.database import get_db

import integrations.telegram_routes as tr


def _tg_secret_env(value=None):
    env = dict(os.environ)
    env.pop("ATOM_TELEGRAM_WEBHOOK_SECRET", None)
    env.pop("TELEGRAM_WEBHOOK_SECRET_TOKEN", None)
    if value is not None:
        env["ATOM_TELEGRAM_WEBHOOK_SECRET"] = value
    return env


@pytest.fixture
def user():
    u = MagicMock()
    u.id = f"tg96-{uuid.uuid4().hex[:8]}"
    u.email = "tg96@x.com"
    u.tenant_id = "t-1"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(tr.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app = FastAPI()
    app.include_router(tr.router)
    return TestClient(app, raise_server_exceptions=False)


def _post_webhook(client, body, secret=None, env_secret=None):
    headers = {}
    if secret is not None:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret
    with patch.dict(os.environ, _tg_secret_env(env_secret), clear=False):
        return client.post("/api/telegram/webhook", json=body, headers=headers)


# ── Webhook: secret verification (fail-closed) ──────────────────────────────
class TestWebhookSecret:
    def test_no_secret_fails_closed_401(self, client):
        """RED before fix: 200 (fail-open), now 401."""
        response = _post_webhook(
            client, {"update_id": 1, "message": {"text": "hi", "chat": {"id": 1}}})
        assert response.status_code == 401

    def test_mismatched_secret_401(self, client):
        response = _post_webhook(
            client, {"update_id": 1}, secret="wrong",
            env_secret="right-secret")
        assert response.status_code == 401

    def test_missing_header_401(self, client):
        response = _post_webhook(
            client, {"update_id": 1}, env_secret="right-secret")
        assert response.status_code == 401

    def test_correct_secret_ok(self, client):
        response = _post_webhook(
            client, {"update_id": 1}, secret="right-secret",
            env_secret="right-secret")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_legacy_env_name_fallback(self, client):
        # The primary var must be FALSY for the legacy fallback to trigger.
        # patch.dict cannot delete keys, and a developer .env may define
        # ATOM_TELEGRAM_WEBHOOK_SECRET (dotenv-loaded) — so override it "".
        with patch.dict(os.environ, {
            "ATOM_TELEGRAM_WEBHOOK_SECRET": "",
            "TELEGRAM_WEBHOOK_SECRET_TOKEN": "legacy-secret",
        }, clear=False):
            response = client.post(
                "/api/telegram/webhook", json={"update_id": 1},
                headers={"X-Telegram-Bot-Api-Secret-Token": "legacy-secret"})
        assert response.status_code == 200

    def test_invalid_json_400(self, client):
        with patch.dict(os.environ, _tg_secret_env("s"), clear=False):
            response = client.post(
                "/api/telegram/webhook",
                content=b"{not json",
                headers={"X-Telegram-Bot-Api-Secret-Token": "s"})
        assert response.status_code == 400


# ── Webhook: update routing ──────────────────────────────────────────────────
class TestWebhookRouting:
    def test_callback_query_routed(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "handle_callback_query",
                          new=AsyncMock()) as handler, \
                patch.dict(os.environ, _tg_secret_env("s"), clear=False):
            response = client.post(
                "/api/telegram/webhook",
                json={"update_id": 1,
                      "callback_query": {"id": "cq1", "data": "btn"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "s"})
        assert response.status_code == 200
        assert response.json()["callback_query_id"] == "cq1"
        handler.assert_awaited_once_with(
            {"id": "cq1", "data": "btn"})

    def test_inline_query_routed(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "handle_inline_query",
                          new=AsyncMock()) as handler, \
                patch.dict(os.environ, _tg_secret_env("s"), clear=False):
            response = client.post(
                "/api/telegram/webhook",
                json={"update_id": 2, "inline_query": {"id": "iq1"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "s"})
        assert response.status_code == 200
        assert response.json()["inline_query_id"] == "iq1"
        handler.assert_awaited_once_with({"id": "iq1"})

    def test_message_no_payload_ok(self, client):
        response = _post_webhook(client, {"update_id": 3},
                                 secret="s", env_secret="s")
        assert response.status_code == 200


class _Gov:
    """Fake IMGovernanceService factory."""

    def __init__(self, verify=None, perms=None):
        self.instances = []
        self.verify = verify or {"sender_id": "tg-sender-1"}
        self.perms = perms
        self.created = []

    def factory(self, db):
        gov = MagicMock()
        gov.verify_and_rate_limit = AsyncMock(return_value=self.verify)
        gov.check_permissions = AsyncMock(side_effect=self.perms or [None])
        gov.log_to_audit_trail = AsyncMock()
        self.created.append(gov)
        return gov


class TestWebhookMessageGovernance:
    def test_message_success_bridges_and_audits(self, client):
        gov = _Gov()
        with patch.object(tr, "IMGovernanceService", new=gov.factory), \
                patch.object(tr.universal_webhook_bridge,
                             "process_incoming_message",
                             new=AsyncMock(return_value=True)) as bridge, \
                patch.dict(os.environ, _tg_secret_env("s"), clear=False):
            response = client.post(
                "/api/telegram/webhook",
                json={"update_id": 4, "message": {"text": "hello",
                                                  "chat": {"id": 1}}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "s"})
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        bridge.assert_awaited_once()
        g = gov.created[0]
        g.verify_and_rate_limit.assert_awaited_once()
        g.check_permissions.assert_awaited_once()
        g.log_to_audit_trail.assert_awaited_once()

    def test_verify_rejection_401(self, client):
        from fastapi import HTTPException

        def reject(*a, **k):
            raise HTTPException(status_code=401, detail="rejected")

        def factory(db):
            g = MagicMock()
            g.verify_and_rate_limit = AsyncMock(side_effect=reject)
            g.check_permissions = AsyncMock()
            g.log_to_audit_trail = AsyncMock()
            return g

        with patch.object(tr, "IMGovernanceService", new=factory), \
                patch.object(tr.universal_webhook_bridge,
                             "process_incoming_message",
                             new=AsyncMock()) as bridge, \
                patch.dict(os.environ, _tg_secret_env("s"), clear=False):
            response = client.post(
                "/api/telegram/webhook",
                json={"update_id": 5, "message": {"text": "x"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "s"})
        assert response.status_code == 401
        bridge.assert_not_awaited()

    def test_permission_rejection_401_with_audit(self, client):
        from fastapi import HTTPException

        def factory(db):
            g = MagicMock()
            g.verify_and_rate_limit = AsyncMock(return_value={"sender_id": "u1"})

            def deny(*a, **k):
                raise HTTPException(status_code=403, detail="no perms")
            g.check_permissions = AsyncMock(side_effect=deny)
            g.log_to_audit_trail = AsyncMock()
            return g

        with patch.object(tr, "IMGovernanceService", new=factory), \
                patch.object(tr.universal_webhook_bridge,
                             "process_incoming_message",
                             new=AsyncMock()) as bridge, \
                patch.dict(os.environ, _tg_secret_env("s"), clear=False):
            response = client.post(
                "/api/telegram/webhook",
                json={"update_id": 6, "message": {"text": "x"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "s"})
        assert response.status_code == 403
        bridge.assert_not_awaited()

    def test_bridge_failure_500_audits_failure(self, client):
        with patch.object(tr, "IMGovernanceService",
                          new=_Gov().factory), \
                patch.object(tr.universal_webhook_bridge,
                             "process_incoming_message",
                             new=AsyncMock(
                                 side_effect=RuntimeError("bridge down"))), \
                patch.dict(os.environ, _tg_secret_env("s"), clear=False):
            response = client.post(
                "/api/telegram/webhook",
                json={"update_id": 7, "message": {"text": "x"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "s"})
        assert response.status_code == 500

    def test_bridge_runtime_error_500(self, client):
        """Bridge failure outside the awaited result — logging path."""
        with patch.object(tr, "IMGovernanceService",
                          new=_Gov().factory), \
                patch.object(tr.universal_webhook_bridge,
                             "process_incoming_message",
                             side_effect=RuntimeError("boom")), \
                patch.dict(os.environ, _tg_secret_env("s"), clear=False):
            response = client.post(
                "/api/telegram/webhook",
                json={"update_id": 8, "message": {"text": "x"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "s"})
        assert response.status_code == 500


# ── Health / status / workspaces ─────────────────────────────────────────────
class TestInfoEndpoints:
    def test_health_active(self, anon_client):
        with patch.object(tr.atom_telegram_integration,
                          "get_service_status",
                          return_value={"status": "active"}):
            response = anon_client.get("/api/telegram/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_inactive(self, anon_client):
        with patch.object(tr.atom_telegram_integration,
                          "get_service_status",
                          return_value={"status": "stopped"}):
            response = anon_client.get("/api/telegram/health")
        assert response.json()["status"] == "inactive"

    def test_health_exception(self, anon_client):
        with patch.object(tr.atom_telegram_integration,
                          "get_service_status",
                          side_effect=RuntimeError("boom")):
            response = anon_client.get("/api/telegram/health")
        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"

    def test_status_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "get_service_status",
                          return_value={"status": "active", "bot": "x"}):
            response = client.get("/api/telegram/status")
        assert response.status_code == 200
        assert response.json() == {"status": "active", "bot": "x"}

    def test_status_anonymous_401(self, anon_client):
        assert anon_client.get("/api/telegram/status").status_code == 401

    def test_workspaces_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "get_intelligent_workspaces",
                          new=AsyncMock(return_value=[{"id": 1}])):
            response = client.get("/api/telegram/workspaces/42")
        assert response.status_code == 200
        assert response.json() == [{"id": 1}]

    def test_workspaces_anonymous_401(self, anon_client):
        assert anon_client.get("/api/telegram/workspaces/42").status_code == 401

    def test_capabilities_success(self, client):
        response = client.get("/api/telegram/capabilities")
        assert response.status_code == 200
        assert response.json()["platform"] == "Telegram"

    def test_capabilities_anonymous_401(self, anon_client):
        assert anon_client.get("/api/telegram/capabilities").status_code == 401


# ── Auth gates: all interactive endpoints must be 401 anonymous ──────────────
ANON_CASES = [
    ("post", "/api/telegram/send-keyboard", {
        "chat_id": 1, "text": "hi", "keyboard": [[{"text": "B"}]]}),
    ("post", "/api/telegram/edit-keyboard?chat_id=1&message_id=2", None),
    ("post", "/api/telegram/answer-callback?callback_query_id=cq1", None),
    ("post", "/api/telegram/answer-inline", {
        "inline_query_id": "iq1", "results": []}),
    ("post", "/api/telegram/send-chat-action", {
        "chat_id": 1, "action": "typing"}),
    ("post", "/api/telegram/send", {
        "channel_id": 1, "message": "hello"}),
    ("post", "/api/telegram/send-photo", {
        "chat_id": 1, "photo": "https://x.com/p.png"}),
    ("post", "/api/telegram/send-poll", {
        "chat_id": 1, "question": "Q", "options": ["a", "b"]}),
    ("post", "/api/telegram/get-chat-info/42", None),
]


class TestAuthGates:
    @pytest.mark.parametrize("method,path,body", ANON_CASES)
    def test_anonymous_401(self, anon_client, method, path, body):
        response = getattr(anon_client, method)(path, json=body)
        assert response.status_code == 401


# ── Interactive / message endpoints (authed) ─────────────────────────────────
class TestInteractiveEndpoints:
    def test_send_keyboard_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "send_message_with_keyboard",
                          new=AsyncMock(
                              return_value={"success": True, "id": 9})):
            response = client.post("/api/telegram/send-keyboard", json={
                "chat_id": 1, "text": "menu",
                "keyboard": [[{"text": "A", "callback_data": "a"}]]})
        assert response.status_code == 200
        assert response.json()["id"] == 9

    def test_send_keyboard_failure_500(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "send_message_with_keyboard",
                          new=AsyncMock(
                              return_value={"success": False,
                                            "error": "Telegram API down"})):
            response = client.post("/api/telegram/send-keyboard", json={
                "chat_id": 1, "text": "menu", "keyboard": []})
        assert response.status_code == 500

    def test_send_keyboard_422(self, client):
        response = client.post("/api/telegram/send-keyboard",
                               json={"chat_id": 1})
        assert response.status_code == 422

    def test_edit_keyboard_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "edit_message_keyboard",
                          new=AsyncMock(return_value={"success": True})):
            response = client.post(
                "/api/telegram/edit-keyboard?chat_id=1&message_id=2",
                json=[[{"text": "New"}]])
        assert response.status_code == 200

    def test_edit_keyboard_failure_500(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "edit_message_keyboard",
                          new=AsyncMock(
                              return_value={"success": False,
                                            "error": "nope"})):
            response = client.post(
                "/api/telegram/edit-keyboard?chat_id=1&message_id=2",
                json=[[{"text": "New"}]])
        assert response.status_code == 500

    def test_answer_callback_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "answer_callback_query",
                          new=AsyncMock(return_value={"success": True})):
            response = client.post(
                "/api/telegram/answer-callback?callback_query_id=cq1"
                "&text=Done&show_alert=true&cache_time=5")
        assert response.status_code == 200

    def test_answer_callback_failure_500(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "answer_callback_query",
                          new=AsyncMock(
                              return_value={"success": False, "error": "x"})):
            response = client.post(
                "/api/telegram/answer-callback?callback_query_id=cq1")
        assert response.status_code == 500

    def test_answer_inline_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "answer_inline_query",
                          new=AsyncMock(return_value={"success": True})):
            response = client.post("/api/telegram/answer-inline", json={
                "inline_query_id": "iq1", "results": [{"id": "r1"}],
                "cache_time": 60, "personal": True, "next_offset": "2"})
        assert response.status_code == 200

    def test_answer_inline_failure_500(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "answer_inline_query",
                          new=AsyncMock(
                              return_value={"success": False, "error": "x"})):
            response = client.post("/api/telegram/answer-inline", json={
                "inline_query_id": "iq1", "results": []})
        assert response.status_code == 500

    def test_send_chat_action_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "send_chat_action",
                          new=AsyncMock(return_value={"success": True})):
            response = client.post("/api/telegram/send-chat-action", json={
                "chat_id": 1, "action": "typing", "progress": 50})
        assert response.status_code == 200

    def test_send_chat_action_failure_500(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "send_chat_action",
                          new=AsyncMock(
                              return_value={"success": False, "error": "x"})):
            response = client.post("/api/telegram/send-chat-action", json={
                "chat_id": 1, "action": "typing"})
        assert response.status_code == 500

    def test_send_message_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "send_intelligent_message",
                          new=AsyncMock(return_value={"success": True,
                                                      "id": 11})):
            response = client.post("/api/telegram/send", json={
                "channel_id": 1, "message": "hello", "parse_mode": "Markdown",
                "disable_web_page_preview": True,
                "disable_notification": False,
                "reply_to_message_id": 3})
        assert response.status_code == 200
        assert response.json()["id"] == 11

    def test_send_message_failure_500(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "send_intelligent_message",
                          new=AsyncMock(
                              return_value={"success": False,
                                            "error": "chat not found"})):
            response = client.post("/api/telegram/send", json={
                "channel_id": 1, "message": "hello"})
        assert response.status_code == 500

    def test_send_photo_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "send_photo",
                          new=AsyncMock(return_value={"success": True})):
            response = client.post("/api/telegram/send-photo", json={
                "chat_id": 1, "photo": "file_id_1", "caption": "cap",
                "parse_mode": "HTML"})
        assert response.status_code == 200

    def test_send_photo_failure_500(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "send_photo",
                          new=AsyncMock(
                              return_value={"success": False, "error": "x"})):
            response = client.post("/api/telegram/send-photo", json={
                "chat_id": 1, "photo": "file_id_1"})
        assert response.status_code == 500

    def test_send_poll_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "send_poll",
                          new=AsyncMock(return_value={"success": True})):
            response = client.post("/api/telegram/send-poll", json={
                "chat_id": 1, "question": "Best?", "options": ["a", "b"],
                "is_anonymous": True, "allows_multiple_answers": True,
                "explanation": "because"})
        assert response.status_code == 200

    def test_send_poll_failure_500(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "send_poll",
                          new=AsyncMock(
                              return_value={"success": False, "error": "x"})):
            response = client.post("/api/telegram/send-poll", json={
                "chat_id": 1, "question": "Q", "options": ["a"]})
        assert response.status_code == 500

    def test_get_chat_info_success(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "get_chat_info",
                          new=AsyncMock(
                              return_value={"success": True,
                                            "chat": {"id": 42}})):
            response = client.post("/api/telegram/get-chat-info/42")
        assert response.status_code == 200
        assert response.json()["chat"]["id"] == 42

    def test_get_chat_info_failure_500(self, client):
        with patch.object(tr.atom_telegram_integration,
                          "get_chat_info",
                          new=AsyncMock(
                              return_value={"success": False,
                                            "error": "not found"})):
            response = client.post("/api/telegram/get-chat-info/42")
        assert response.status_code == 500
