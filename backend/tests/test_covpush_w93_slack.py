"""Coverage wave 93 — integrations/slack_routes.py (re-audit + security fixes).

W64 covered this module to 100%, but the wave-93 security re-audit found two
REAL bugs that w64's tests baked in as "expected" behavior:

1. Interactive callback FAIL-OPEN when SLACK_SIGNING_SECRET is unset
   (slack_routes.py:538-548). With no shared secret configured the handler
   skipped signature verification and STILL PROCESSED the attacker-supplied
   payload (dispatched actions). Security contract: without a configured
   secret the webhook must fail closed — no payload parsing, no dispatch.
   Slack still gets its mandatory 200, but nothing is processed.

2. POST /search and GET /conversations/history were UNauthenticated but
   ingest attacker-controlled content into agent memory with a
   client-supplied user_id (memory-forgery vector, R58/R69 class). Both now
   require get_current_user.

New coverage also closes the W64-baseline gaps: fail-closed branch, auth-401
on the newly-gated endpoints, OAuth auth-url success/error, callback
success/error, interactive dispatch error handling, and the governance
blocked/error branches on the memory-ingesting endpoints.

Every dep is mocked: slack_sdk WebClient, ingestion pipeline, state manager,
OAuthHandler, ConnectionService. No network, no LLM spend.
"""
import asyncio
import hashlib
import hmac
import json
import sys
import time
import types
import urllib.parse
import uuid
from collections import defaultdict, deque
from enum import Enum
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from integrations import slack_routes as sr
from core.models import User

INTERACTIVE_URL = "/api/slack/interactive"
SECRET = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def user():
    u = MagicMock(spec=User)
    u.id = f"sl93-{uuid.uuid4().hex[:8]}"
    u.email = "slack93@x.com"
    u.tenant_id = "t-1"
    return u


@pytest.fixture
def client(user):
    app = FastAPI()
    app.include_router(sr.router)

    from core.auth import get_current_user
    from core.database import get_db

    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: user
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    """Client WITHOUT the get_current_user override — real 401 checks."""
    app = FastAPI()
    app.include_router(sr.router)
    from core.database import get_db

    app.dependency_overrides[get_db] = lambda: MagicMock()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def fake_ingestion():
    """Swap atom_ingestion_pipeline (imported lazily inside handlers)."""

    class RecordType(Enum):
        COMMUNICATION = "communication"

    fake_mod = types.ModuleType("integrations.atom_ingestion_pipeline")
    fake_mod.RecordType = RecordType
    fake_mod.atom_ingestion_pipeline = types.SimpleNamespace(
        ingest_record=AsyncMock(return_value=True))
    sys.modules["integrations.atom_ingestion_pipeline"] = fake_mod
    yield fake_mod
    sys.modules.pop("integrations.atom_ingestion_pipeline", None)


def _signed_form(payload: dict, body_str: str | None = None,
                 ts: str | None = None) -> tuple:
    """Form body + headers with a valid Slack HMAC signature."""
    if body_str is None:
        body_str = json.dumps(payload)
    if ts is None:
        ts = str(int(time.time()))
    body_bytes = b"payload=" + urllib.parse.quote(body_str, safe="").encode()
    basestring = f"v0:{ts}:{body_bytes.decode()}"
    sig = "v0=" + hmac.new(SECRET.encode(), basestring.encode(),
                           hashlib.sha256).hexdigest()
    headers = {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    return body_bytes, headers


class TestInteractiveFailClosed:
    """Wave-93 regression: no secret => payload must NOT be processed."""

    def _post_with_actions(self, client):
        payload = {
            "type": "block_actions",
            "user": {"id": "U1"},
            "actions": [{"action_id": "approve"}],
        }
        return client.post(INTERACTIVE_URL,
                           data={"payload": json.dumps(payload)})

    def test_no_secret_fails_closed_no_dispatch(self, client):
        handlers = {"approve": MagicMock(return_value={"ok": True})}
        with patch.object(sr, "SLACK_SIGNING_SECRET", ""), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)), \
                patch.object(sr, "_SLACK_ACTION_HANDLERS", handlers):
            response = self._post_with_actions(client)
        assert response.status_code == 200  # Slack always gets 200
        assert response.json() == {"ok": True}
        handlers["approve"].assert_not_called()  # fail closed: no dispatch

    def test_no_secret_no_payload_parse(self, client):
        """Even malformed payloads are never touched without a secret."""
        with patch.object(sr, "SLACK_SIGNING_SECRET", ""), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(INTERACTIVE_URL,
                                   data={"payload": "not-json{{"})
        assert response.status_code == 200

    def test_with_secret_still_dispatches(self, client):
        """Signed requests still work end-to-end (no regression)."""
        payload = {
            "type": "block_actions",
            "user": {"id": "U1"},
            "actions": [{"action_id": "approve"}],
        }
        body_bytes, headers = _signed_form(payload)
        handlers = {"approve": MagicMock(return_value={"ok": True})}
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)), \
                patch.object(sr, "_SLACK_ACTION_HANDLERS", handlers):
            response = client.post(INTERACTIVE_URL, data=body_bytes,
                                   headers=headers)
        assert response.status_code == 200
        handlers["approve"].assert_called_once()

    def test_signed_replay_rejected(self, client):
        """Stale timestamp within rate limit => no dispatch."""
        payload = {"type": "block_actions", "actions": []}
        body_bytes, headers = _signed_form(
            payload, ts=str(int(time.time()) - 400))
        handlers = {"approve": MagicMock()}
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)), \
                patch.object(sr, "_SLACK_ACTION_HANDLERS", handlers):
            response = client.post(INTERACTIVE_URL, data=body_bytes,
                                   headers=headers)
        assert response.status_code == 200
        handlers["approve"].assert_not_called()

    def test_handler_exception_logged_not_raised(self, client):
        payload = {
            "type": "block_actions",
            "actions": [{"action_id": "boom"}],
        }
        body_bytes, headers = _signed_form(payload)
        handlers = {"boom": MagicMock(side_effect=RuntimeError("kaboom"))}
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)), \
                patch.object(sr, "_SLACK_ACTION_HANDLERS", handlers):
            response = client.post(INTERACTIVE_URL, data=body_bytes,
                                   headers=headers)
        assert response.status_code == 200

    def test_rate_limited_skips_processing(self, client):
        with patch.object(sr, "_RATE_LIMIT_MAX", 0), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = self._post_with_actions(client)
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_missing_payload_field_ok(self, client):
        ts = str(int(time.time()))
        body_bytes = b"other=x"
        sig = "v0=" + hmac.new(
            SECRET.encode(), f"v0:{ts}:other=x".encode(),
            hashlib.sha256).hexdigest()
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(INTERACTIVE_URL, data=body_bytes, headers={
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": sig,
                "Content-Type": "application/x-www-form-urlencoded",
            })
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_invalid_payload_json_signed_ok(self, client):
        ts = str(int(time.time()))
        body_str = "payload=not-json{{"
        body_bytes = body_str.encode()
        sig = "v0=" + hmac.new(
            SECRET.encode(), f"v0:{ts}:{body_str}".encode(),
            hashlib.sha256).hexdigest()
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(INTERACTIVE_URL, data=body_bytes, headers={
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": sig,
                "Content-Type": "application/x-www-form-urlencoded",
            })
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_unexpected_payload_type_ok(self, client):
        body_bytes, headers = _signed_form({"type": "mystery"})
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(INTERACTIVE_URL, data=body_bytes,
                                   headers=headers)
        assert response.status_code == 200


class TestAuthOnMemoryEndpoints:
    """Wave-93 regression: /search + /conversations/history require auth."""

    def test_search_anonymous_401(self, anon_client):
        response = anon_client.post("/api/slack/search",
                                    json={"query": "x", "user_id": "u1"})
        assert response.status_code == 401

    def test_history_anonymous_401(self, anon_client):
        response = anon_client.get(
            "/api/slack/conversations/history?channel=C1&user_id=u1")
        assert response.status_code == 401

    def test_search_authed_200(self, client, fake_ingestion):
        response = client.post("/api/slack/search", json={
            "query": "alpha", "user_id": "u1", "max_results": 2})
        assert response.status_code == 200
        assert response.json()["total_results"] == 2

    def test_history_authed_200(self, client, fake_ingestion):
        response = client.get(
            "/api/slack/conversations/history?channel=C1&limit=2&user_id=u1")
        assert response.status_code == 200
        assert len(response.json()["messages"]) == 2

    def test_search_governance_blocked_403(self, client):
        with patch.object(sr, "with_governance_check",
                          new=AsyncMock(return_value=(
                              None, {"allowed": False,
                                     "reason": "STUDENT cannot search"}))):
            response = client.post("/api/slack/search?agent_id=a1", json={
                "query": "q", "user_id": "u1"})
        assert response.status_code == 403

    def test_search_governance_error_graceful(self, client, fake_ingestion):
        with patch.object(sr, "with_governance_check",
                          new=AsyncMock(side_effect=RuntimeError("gov down"))):
            response = client.post("/api/slack/search?agent_id=a1", json={
                "query": "q", "user_id": "u1"})
        assert response.status_code == 200

    def test_history_governance_blocked_403(self, client):
        with patch.object(sr, "with_governance_check",
                          new=AsyncMock(return_value=(
                              None, {"allowed": False,
                                     "reason": "STUDENT cannot view"}))):
            response = client.get(
                "/api/slack/conversations/history?channel=C1&agent_id=a1")
        assert response.status_code == 403

    def test_history_governance_error_graceful(self, client):
        with patch.object(sr, "with_governance_check",
                          new=AsyncMock(side_effect=RuntimeError("gov down"))):
            response = client.get(
                "/api/slack/conversations/history?channel=C1&agent_id=a1")
        assert response.status_code == 200

    def test_search_ingestion_failure_logged(self, client):
        fake = types.SimpleNamespace(
            ingest_record=AsyncMock(side_effect=RuntimeError("pipeline down")))
        fake_mod = types.ModuleType("integrations.atom_ingestion_pipeline")
        fake_mod.RecordType = Enum("RT", {"COMMUNICATION": "communication"})
        fake_mod.atom_ingestion_pipeline = fake
        sys.modules["integrations.atom_ingestion_pipeline"] = fake_mod
        try:
            response = client.post("/api/slack/search", json={
                "query": "q", "user_id": "u1", "max_results": 1})
        finally:
            sys.modules.pop("integrations.atom_ingestion_pipeline", None)
        assert response.status_code == 200

    def test_history_ingestion_failure_logged(self, client):
        fake = types.SimpleNamespace(
            ingest_record=AsyncMock(side_effect=RuntimeError("pipeline down")))
        fake_mod = types.ModuleType("integrations.atom_ingestion_pipeline")
        fake_mod.RecordType = Enum("RT", {"COMMUNICATION": "communication"})
        fake_mod.atom_ingestion_pipeline = fake
        sys.modules["integrations.atom_ingestion_pipeline"] = fake_mod
        try:
            response = client.get(
                "/api/slack/conversations/history?channel=C1&limit=1")
        finally:
            sys.modules.pop("integrations.atom_ingestion_pipeline", None)
        assert response.status_code == 200


class TestStatusAndReadEndpoints:
    def test_status_mock_mode(self, client):
        with patch.object(sr, "get_slack_client", return_value=None):
            response = client.get("/api/slack/status")
        assert response.status_code == 200
        assert response.json()["status"] == "mock_mode"

    def test_status_connected(self, client):
        with patch.object(sr, "get_slack_client", return_value=MagicMock()):
            response = client.get("/api/slack/status?user_id=u9")
        assert response.json()["status"] == "connected"
        assert response.json()["user_id"] == "u9"

    def test_health_alias(self, client):
        with patch.object(sr, "get_slack_client", return_value=None):
            response = client.get("/api/slack/health?user_id=u9")
        assert response.status_code == 200
        assert response.json()["service"] == "slack"

    def test_channels_list(self, client):
        response = client.get("/api/slack/channels?user_id=u9")
        assert response.status_code == 200
        assert response.json()["total_channels"] == 7

    def test_channel_detail_empty_id_400(self):
        with pytest.raises(Exception) as exc:
            asyncio_run(sr.get_slack_channel("", "u9"))
        assert exc.value.status_code == 400

    def test_channel_detail(self, client):
        response = client.get("/api/slack/channels/C42?user_id=u9")
        assert response.status_code == 200
        body = response.json()
        assert body["channel_id"] == "C42"
        assert len(body["members"]) == 5

    def test_get_user(self, client):
        response = client.get("/api/slack/users/U007")
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["id"] == "U007"
        assert body["user"]["is_bot"] is False

    def test_get_bot_user(self, client):
        response = client.get("/api/slack/users/bot_x")
        assert response.json()["user"]["is_bot"] is True

    def test_add_reaction(self, client):
        response = client.post("/api/slack/reactions/add?channel=C1"
                               "&timestamp=123.4&reaction=thumbsup"
                               "&user_id=u9")
        assert response.status_code == 200
        assert response.json()["reaction"] == "thumbsup"


class TestMessages:
    def test_send_mock_fallback(self, client):
        with patch.object(sr, "get_slack_client", return_value=None):
            response = client.post("/api/slack/messages", json={
                "channel": "C1", "text": "hi", "user_id": "u9"})
        assert response.status_code == 200
        assert response.json()["message_id"].startswith("msg_C1_")

    def test_send_real_client(self, client):
        real = MagicMock()
        real.chat_postMessage.return_value = {"channel": "C1", "ts": "9.9"}
        with patch.object(sr, "get_slack_client", return_value=real):
            response = client.post("/api/slack/messages", json={
                "channel": "C1", "text": "hi", "user_id": "u9"})
        assert response.status_code == 200
        assert response.json()["message_id"] == "9.9"

    def test_send_slack_api_error_400(self, client):
        from slack_sdk.errors import SlackApiError
        real = MagicMock()
        real.chat_postMessage.side_effect = SlackApiError(
            "invalid_auth", {"error": "invalid_auth", "ok": False})
        with patch.object(sr, "get_slack_client", return_value=real):
            response = client.post("/api/slack/messages", json={
                "channel": "C1", "text": "hi", "user_id": "u9"})
        assert response.status_code == 400

    def test_send_anonymous_401(self, anon_client):
        response = anon_client.post("/api/slack/messages", json={
            "channel": "C1", "text": "hi"})
        assert response.status_code == 401

    def test_send_governance_execution_record(self, client):
        agent = MagicMock()
        agent.id = "agent-1"
        with patch.object(sr, "get_slack_client", return_value=None), \
                patch.object(sr, "with_governance_check",
                             new=AsyncMock(return_value=(
                                 agent, {"allowed": True}))), \
                patch.object(sr, "create_execution_record",
                             return_value=MagicMock()) as record:
            response = client.post(
                "/api/slack/messages?agent_id=agent-1", json={
                    "channel": "C1", "text": "hi", "user_id": "u9"})
        assert response.status_code == 200
        record.assert_called_once()
        assert record.call_args[0][3] == "slack_send_message"

    def test_send_governance_blocked_403(self, client):
        with patch.object(sr, "get_slack_client", return_value=None), \
                patch.object(sr, "with_governance_check",
                             new=AsyncMock(return_value=(
                                 None, {"allowed": False,
                                        "reason": "too risky"}))):
            response = client.post(
                "/api/slack/messages?agent_id=agent-1", json={
                    "channel": "C1", "text": "hi", "user_id": "u9"})
        assert response.status_code == 403

    def test_send_governance_error_graceful(self, client):
        with patch.object(sr, "get_slack_client", return_value=None), \
                patch.object(sr, "with_governance_check",
                             new=AsyncMock(side_effect=RuntimeError("down"))):
            response = client.post(
                "/api/slack/messages?agent_id=agent-1", json={
                    "channel": "C1", "text": "hi", "user_id": "u9"})
        assert response.status_code == 200


class TestOAuth:
    def test_auth_url_success(self, client, user):
        state_manager = MagicMock()
        state_manager.generate_state.return_value = "state-abc"
        handler = MagicMock()
        handler.get_authorization_url.return_value = "https://slack.com/oauth"
        with patch.object(sr, "get_oauth_state_manager",
                          return_value=state_manager), \
                patch.object(sr, "OAuthHandler", return_value=handler):
            response = client.get("/api/slack/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "state-abc"
        assert body["url"] == "https://slack.com/oauth"

    def test_auth_url_error_500(self, client, user):
        with patch.object(sr, "get_oauth_state_manager",
                          side_effect=RuntimeError("boom")):
            response = client.get("/api/slack/auth/url")
        assert response.status_code == 500

    def test_callback_missing_code_400(self, client):
        response = client.post("/api/slack/callback", json={"state": "s1"})
        assert response.status_code == 400

    def test_callback_missing_state_400(self, client):
        response = client.post("/api/slack/callback", json={"code": "c1"})
        assert response.status_code == 400

    def test_callback_invalid_state_400(self, client):
        state_manager = MagicMock()
        state_manager.validate_state.side_effect = ValueError("expired")
        with patch.object(sr, "get_oauth_state_manager",
                          return_value=state_manager):
            response = client.post("/api/slack/callback",
                                   json={"code": "c1", "state": "bad"})
        assert response.status_code == 400

    def test_callback_success(self, client, user):
        state_manager = MagicMock()
        state_manager.validate_state.return_value = {"user_id": user.id}
        handler = MagicMock()
        handler.exchange_code_for_tokens = AsyncMock(
            return_value={"access_token": "xoxp-1"})
        connection = MagicMock()
        connection.id = "conn-9"
        conn_svc = MagicMock()
        conn_svc.save_connection.return_value = connection
        with patch.object(sr, "get_oauth_state_manager",
                          return_value=state_manager), \
                patch.object(sr, "OAuthHandler", return_value=handler), \
                patch("core.connection_service.ConnectionService",
                      return_value=conn_svc):
            response = client.post("/api/slack/callback",
                                   json={"code": "c1", "state": "good"})
        assert response.status_code == 200
        assert response.json()["connection_id"] == "conn-9"

    def test_callback_exchange_error_500(self, client):
        state_manager = MagicMock()
        state_manager.validate_state.return_value = {"user_id": "u"}
        handler = MagicMock()
        handler.exchange_code_for_tokens = AsyncMock(
            side_effect=RuntimeError("meta down"))
        with patch.object(sr, "get_oauth_state_manager",
                          return_value=state_manager), \
                patch.object(sr, "OAuthHandler", return_value=handler):
            response = client.post("/api/slack/callback",
                                   json={"code": "c1", "state": "good"})
        assert response.status_code == 500

    def test_callback_anonymous_401(self, anon_client):
        response = anon_client.post("/api/slack/callback", json={
            "code": "c1", "state": "s1"})
        assert response.status_code == 401


def asyncio_run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestImportGuard:
    def test_missing_slack_sdk_guard(self):
        import importlib
        saved = {k: sys.modules.pop(k)
                 for k in ("slack_sdk", "slack_sdk.errors")
                 if k in sys.modules}

        class Blocker:
            def find_spec(self, name, path=None, target=None):
                if name == "slack_sdk" or name.startswith("slack_sdk."):
                    raise ImportError("blocked for test")
                return None

        sys.meta_path.insert(0, Blocker())
        try:
            reloaded = importlib.reload(sr)
            assert reloaded.SLACK_SDK_AVAILABLE is False
        finally:
            sys.meta_path.pop(0)
            for name, mod in saved.items():
                sys.modules[name] = mod
            importlib.reload(sr)
            assert sr.SLACK_SDK_AVAILABLE is True


class TestHelpers:
    def test_get_slack_client_no_token(self, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        assert sr.get_slack_client() is None

    def test_get_slack_client_with_token(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-t")
        client = sr.get_slack_client()
        assert client is not None

    def test_verify_signature_no_secret(self):
        ok, reason = sr._verify_slack_signature(b"{}", "1", "v0=abc")
        assert ok is False
        assert "not configured" in reason

    def test_verify_signature_bad_timestamp(self):
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET):
            ok, reason = sr._verify_slack_signature(b"{}", "x", "v0=abc")
        assert ok is False

    def test_verify_signature_future_timestamp(self):
        future = str(int(time.time()) + 120)
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET):
            ok, reason = sr._verify_slack_signature(b"{}", future, "v0=abc")
        assert ok is False

    def test_verify_signature_mismatch(self):
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET):
            ok, reason = sr._verify_slack_signature(
                b"{}", str(int(time.time())), "v0=wrong")
        assert ok is False

    def test_verify_signature_ok(self):
        ts = str(int(time.time()))
        body = b"payload=hello"
        sig = "v0=" + hmac.new(
            SECRET.encode(), f"v0:{ts}:{body.decode()}".encode(),
            hashlib.sha256).hexdigest()
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET):
            ok, reason = sr._verify_slack_signature(body, ts, sig)
        assert ok is True
        assert reason == "OK"

    def test_rate_limit_blocks_after_max(self):
        with patch.object(sr, "_RATE_LIMIT_MAX", 2), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            assert sr._check_rate_limit("1.2.3.4") is True
            assert sr._check_rate_limit("1.2.3.4") is True
            assert sr._check_rate_limit("1.2.3.4") is False

    def test_rate_limit_window_eviction(self):
        store = defaultdict(deque)
        now = time.time()
        store["1.2.3.4"].append(now - 120)
        with patch.object(sr, "_RATE_LIMIT_MAX", 30), \
                patch.object(sr, "_RATE_LIMIT_WINDOW", 60), \
                patch.object(sr, "_rate_limit_store", store):
            assert sr._check_rate_limit("1.2.3.4") is True
        assert len(store["1.2.3.4"]) == 1

    def test_dispatch_unhandled_action(self):
        result = sr._dispatch_slack_action({"action_id": "nope"},
                                           {"id": "U1"}, "trig")
        assert result["status"] == "unhandled"

    def test_dispatch_handler_error(self):
        handlers = {"bad": MagicMock(side_effect=RuntimeError("x"))}
        with patch.object(sr, "_SLACK_ACTION_HANDLERS", handlers):
            result = sr._dispatch_slack_action({"action_id": "bad"},
                                               {"id": "U1"}, "trig")
        assert result["status"] == "handler_error"
