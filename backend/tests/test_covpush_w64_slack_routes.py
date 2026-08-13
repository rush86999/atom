"""Coverage wave W64 — integrations/slack_routes.py (TDD, baseline 40% via
tests/integrations/test_slack_routes_governance.py, which is stale: it predates
the auth requirement on POST /messages and fails with 401 — out of scope here).

Covers: status/health, messages (governance on/off, blocked, graceful,
real-client, SlackApiError, mock fallback), search, channels, users,
conversations/history, reactions, the interactive callback security chain
(rate limit, HMAC verify, replay window, payload validation, action dispatch),
OAuth callback + auth URL, and all module helpers.

Bugs found + fixed in module (regression tests below):
1. line 37: ImportError guard called logger.warning BEFORE logger existed ->
   module import would crash with NameError when slack_sdk is missing. logger
   moved above the guard — test_import_guard_with_missing_sdk.
2. lines 241/368: atom_ingestion_pipeline.ingest_record is a coroutine but was
   called WITHOUT await -> RuntimeWarning "never awaited", memory ingestion
   silently dead. Added await — test_search_ingests_to_memory /
   test_history_ingests_to_memory.
"""
import asyncio
import hashlib
import hmac
import importlib
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
    u.id = f"sl-{uuid.uuid4().hex[:8]}"
    u.email = "slack@x.com"
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
def fake_ingestion():
    """Swap atom_ingestion_pipeline (imported lazily inside handlers) for a
    fake module so no real pipeline runs."""

    class RecordType(Enum):
        COMMUNICATION = "communication"

    fake_mod = types.ModuleType("integrations.atom_ingestion_pipeline")
    fake_mod.RecordType = RecordType
    fake_mod.atom_ingestion_pipeline = types.SimpleNamespace(
        ingest_record=AsyncMock(return_value=True))
    sys.modules["integrations.atom_ingestion_pipeline"] = fake_mod
    yield fake_mod
    sys.modules.pop("integrations.atom_ingestion_pipeline", None)


def _signed_form(payload: dict, body_str: str | None = None, ts: str | None = None) -> tuple:
    """Build form data + headers with a valid Slack HMAC signature."""
    if body_str is None:
        body_str = json.dumps(payload)
    if ts is None:
        ts = str(int(time.time()))
    body_bytes = b"payload=" + urllib.parse.quote(body_str, safe="").encode()
    basestring = f"v0:{ts}:{body_bytes.decode()}"
    sig = "v0=" + hmac.new(SECRET.encode(), basestring.encode(), hashlib.sha256).hexdigest()
    headers = {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": sig,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    return body_bytes, headers


class TestStatus:
    def test_status_mock_mode(self, client):
        with patch.object(sr, "get_slack_client", return_value=None):
            response = client.get("/api/slack/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "mock_mode"
        assert body["ok"] is True

    def test_status_connected(self, client):
        with patch.object(sr, "get_slack_client", return_value=MagicMock()):
            response = client.get("/api/slack/status?user_id=u1")
        assert response.json()["status"] == "connected"
        assert response.json()["user_id"] == "u1"

    def test_status_connected_real_token(self, client, monkeypatch):
        # Exercise the real get_slack_client() with SLACK_BOT_TOKEN set
        # (WebClient construction does not hit the network).
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        response = client.get("/api/slack/status")
        assert response.json()["status"] == "connected"

    def test_status_mock_mode_real_client_fn(self, client, monkeypatch):
        # Exercise the real get_slack_client() no-token branch.
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        response = client.get("/api/slack/status")
        assert response.json()["status"] == "mock_mode"

    def test_health_alias(self, client):
        with patch.object(sr, "get_slack_client", return_value=None):
            response = client.get("/api/slack/health")
        assert response.status_code == 200
        assert response.json()["service"] == "slack"


class TestSendMessage:
    def test_send_no_agent_mock_fallback(self, client):
        with patch.object(sr, "get_slack_client", return_value=None):
            response = client.post("/api/slack/messages", json={
                "channel": "C1", "text": "hello", "user_id": "u1"})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["channel"] == "C1"
        assert body["message_id"].startswith("msg_C1_")

    def test_send_governance_allowed_with_execution_record(self, client, user):
        agent = MagicMock()
        agent.id = "agent-1"
        with patch.object(sr, "get_slack_client", return_value=None), \
                patch.object(sr, "with_governance_check",
                             new=AsyncMock(return_value=(agent, {"allowed": True}))) as gov, \
                patch.object(sr, "create_execution_record",
                             return_value=MagicMock()) as record:
            response = client.post(
                "/api/slack/messages?agent_id=agent-1", json={
                    "channel": "C1", "text": "hello", "user_id": "u1"})
        assert response.status_code == 200
        gov.assert_awaited_once()
        assert gov.call_args[0][2] == "post_message"
        assert gov.call_args[0][3] == "agent-1"
        record.assert_called_once()
        assert record.call_args[0][1] == "agent-1"
        assert record.call_args[0][2] == "u1"
        assert record.call_args[0][3] == "slack_send_message"

    def test_send_governance_blocked_403(self, client):
        with patch.object(sr, "get_slack_client", return_value=None), \
                patch.object(sr, "with_governance_check",
                             new=AsyncMock(return_value=(
                                 None, {"allowed": False, "reason": "STUDENT cannot post"}))):
            response = client.post(
                "/api/slack/messages?agent_id=agent-1", json={
                    "channel": "C1", "text": "hello", "user_id": "u1"})
        assert response.status_code == 403
        assert "STUDENT cannot post" in response.json()["detail"]

    def test_send_governance_exception_graceful(self, client):
        with patch.object(sr, "get_slack_client", return_value=None), \
                patch.object(sr, "with_governance_check",
                             new=AsyncMock(side_effect=RuntimeError("gov down"))):
            response = client.post(
                "/api/slack/messages?agent_id=agent-1", json={
                    "channel": "C1", "text": "hello", "user_id": "u1"})
        assert response.status_code == 200

    def test_send_governance_disabled_flag(self, client):
        with patch.object(sr, "get_slack_client", return_value=None), \
                patch.object(sr, "SLACK_GOVERNANCE_ENABLED", False), \
                patch.object(sr, "with_governance_check") as gov:
            response = client.post(
                "/api/slack/messages?agent_id=agent-1", json={
                    "channel": "C1", "text": "hello", "user_id": "u1"})
        assert response.status_code == 200
        gov.assert_not_called()

    def test_send_emergency_bypass(self, client):
        with patch.object(sr, "get_slack_client", return_value=None), \
                patch.object(sr, "EMERGENCY_GOVERNANCE_BYPASS", True), \
                patch.object(sr, "with_governance_check") as gov:
            response = client.post(
                "/api/slack/messages?agent_id=agent-1", json={
                    "channel": "C1", "text": "hello", "user_id": "u1"})
        assert response.status_code == 200
        gov.assert_not_called()

    def test_send_real_client(self, client):
        real_client = MagicMock()
        real_client.chat_postMessage.return_value = {"channel": "C1", "ts": "111.222"}
        with patch.object(sr, "get_slack_client", return_value=real_client):
            response = client.post("/api/slack/messages", json={
                "channel": "C1", "text": "hello", "user_id": "u1"})
        assert response.status_code == 200
        body = response.json()
        assert body["message_id"] == "111.222"
        assert body["channel"] == "C1"
        real_client.chat_postMessage.assert_called_once_with(channel="C1", text="hello")

    def test_send_slack_api_error_400(self, client):
        from slack_sdk.errors import SlackApiError
        real_client = MagicMock()
        real_client.chat_postMessage.side_effect = SlackApiError(
            "invalid_auth", {"error": "invalid_auth", "ok": False})
        with patch.object(sr, "get_slack_client", return_value=real_client):
            response = client.post("/api/slack/messages", json={
                "channel": "C1", "text": "hello", "user_id": "u1"})
        assert response.status_code == 400

    def test_send_sdk_unavailable_mock_fallback(self, client):
        real_client = MagicMock()
        with patch.object(sr, "get_slack_client", return_value=real_client), \
                patch.object(sr, "SLACK_SDK_AVAILABLE", False):
            response = client.post("/api/slack/messages", json={
                "channel": "C1", "text": "hello", "user_id": "u1"})
        assert response.status_code == 200
        real_client.chat_postMessage.assert_not_called()

    def test_send_validation_422(self, client):
        response = client.post("/api/slack/messages", json={"channel": "C1"})
        assert response.status_code == 422


class TestSearch:
    def test_search_default(self, client, fake_ingestion):
        response = client.post("/api/slack/search", json={
            "query": "alpha", "user_id": "u1", "max_results": 3})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert len(body["results"]) == 3
        assert body["total_results"] == 3

    def test_search_governance_allowed(self, client, fake_ingestion):
        with patch.object(sr, "with_governance_check",
                          new=AsyncMock(return_value=(None, {"allowed": True}))) as gov:
            response = client.post(
                "/api/slack/search?agent_id=a1", json={
                    "query": "q", "user_id": "u1", "max_results": 2})
        assert response.status_code == 200
        assert gov.call_args[0][2] == "search"
        assert gov.call_args[0][3] == "a1"

    def test_search_governance_blocked_403(self, client):
        with patch.object(sr, "with_governance_check",
                          new=AsyncMock(return_value=(
                              None, {"allowed": False, "reason": "blocked"}))):
            response = client.post(
                "/api/slack/search?agent_id=a1", json={
                    "query": "q", "user_id": "u1"})
        assert response.status_code == 403

    def test_search_governance_exception_graceful(self, client, fake_ingestion):
        with patch.object(sr, "with_governance_check",
                          new=AsyncMock(side_effect=RuntimeError("gov down"))):
            response = client.post(
                "/api/slack/search?agent_id=a1", json={
                    "query": "q", "user_id": "u1"})
        assert response.status_code == 200

    # Regression: ingest_record is async; must be awaited.
    def test_search_ingests_to_memory(self, client, fake_ingestion):
        client.post("/api/slack/search", json={
            "query": "q", "user_id": "u1", "max_results": 2})
        pipeline = fake_ingestion.atom_ingestion_pipeline
        assert pipeline.ingest_record.await_count == 2

    def test_search_ingestion_failure_logged(self, client, fake_ingestion):
        fake_ingestion.atom_ingestion_pipeline.ingest_record.side_effect = \
            RuntimeError("pipeline down")
        response = client.post("/api/slack/search", json={
            "query": "q", "user_id": "u1", "max_results": 2})
        assert response.status_code == 200


class TestChannels:
    def test_get_channel(self, client):
        response = client.get("/api/slack/channels/C123")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["channel_id"] == "C123"
        assert len(body["members"]) == 5

    def test_get_channel_empty_id_direct(self):
        with pytest.raises(Exception) as exc:
            asyncio.run(sr.get_slack_channel(""))
        assert exc.value.status_code == 400

    def test_list_channels(self, client):
        response = client.get("/api/slack/channels")
        assert response.status_code == 200
        body = response.json()
        assert body["total_channels"] == 7
        assert len(body["channels"]) == 7


class TestUsers:
    def test_get_user(self, client):
        response = client.get("/api/slack/users/U123")
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["id"] == "U123"
        assert body["user"]["is_bot"] is False

    def test_get_bot_user(self, client):
        response = client.get("/api/slack/users/bot-1")
        assert response.json()["user"]["is_bot"] is True


class TestConversationHistory:
    def test_history_default(self, client, fake_ingestion):
        response = client.get("/api/slack/conversations/history?channel=C1&limit=3")
        assert response.status_code == 200
        body = response.json()
        assert len(body["messages"]) == 3

    def test_history_governance_allowed(self, client, fake_ingestion):
        with patch.object(sr, "with_governance_check",
                          new=AsyncMock(return_value=(None, {"allowed": True}))) as gov:
            response = client.get(
                "/api/slack/conversations/history?channel=C1&user_id=u1&agent_id=a1")
        assert response.status_code == 200
        assert gov.call_args[0][2] == "search"
        assert gov.call_args[0][3] == "a1"

    def test_history_governance_blocked_403(self, client):
        with patch.object(sr, "with_governance_check",
                          new=AsyncMock(return_value=(
                              None, {"allowed": False, "reason": "blocked"}))):
            response = client.get(
                "/api/slack/conversations/history?channel=C1&user_id=u1&agent_id=a1")
        assert response.status_code == 403

    def test_history_governance_exception_graceful(self, client, fake_ingestion):
        with patch.object(sr, "with_governance_check",
                          new=AsyncMock(side_effect=RuntimeError("gov down"))):
            response = client.get(
                "/api/slack/conversations/history?channel=C1&user_id=u1&agent_id=a1")
        assert response.status_code == 200

    # Regression: ingest_record must be awaited (channel context injected).
    def test_history_ingests_to_memory(self, client, fake_ingestion):
        client.get("/api/slack/conversations/history?channel=C1&limit=2")
        pipeline = fake_ingestion.atom_ingestion_pipeline
        assert pipeline.ingest_record.await_count == 2
        args = pipeline.ingest_record.await_args.args
        assert args[2]["channel"] == "C1"

    def test_history_ingestion_failure_logged(self, client, fake_ingestion):
        fake_ingestion.atom_ingestion_pipeline.ingest_record.side_effect = \
            RuntimeError("pipeline down")
        response = client.get("/api/slack/conversations/history?channel=C1")
        assert response.status_code == 200


class TestReactions:
    def test_add_reaction(self, client):
        response = client.post(
            "/api/slack/reactions/add?channel=C1&timestamp=111.222&reaction=thumbsup")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["reaction"] == "thumbsup"


class TestVerifySlackSignature:
    def _sig(self, body, ts):
        basestring = f"v0:{ts}:{body.decode('utf-8', errors='replace')}"
        return "v0=" + hmac.new(SECRET.encode(), basestring.encode(),
                                hashlib.sha256).hexdigest()

    def test_no_secret_configured(self):
        body = b"payload={}"
        with patch.object(sr, "SLACK_SIGNING_SECRET", ""):
            ok, reason = sr._verify_slack_signature(body, "1", "v0=abc")
        assert ok is False
        assert reason == "Signing secret not configured"

    def test_invalid_timestamp(self):
        body = b"payload={}"
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET):
            ok, reason = sr._verify_slack_signature(body, "not-a-ts", "v0=abc")
        assert ok is False
        assert "Invalid or missing" in reason

    def test_request_too_old(self):
        body = b"payload={}"
        old_ts = str(int(time.time()) - 1000)
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET):
            ok, reason = sr._verify_slack_signature(body, old_ts, "v0=abc")
        assert ok is False
        assert "too old" in reason

    def test_request_in_future(self):
        body = b"payload={}"
        future_ts = str(int(time.time()) + 1000)
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET):
            ok, reason = sr._verify_slack_signature(body, future_ts, "v0=abc")
        assert ok is False
        assert "future" in reason

    def test_signature_mismatch(self):
        body = b"payload={}"
        ts = str(int(time.time()))
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET):
            ok, reason = sr._verify_slack_signature(body, ts, "v0=wrong")
        assert ok is False
        assert "Signature verification failed" in reason

    def test_valid_signature(self):
        body = b"payload={}"
        ts = str(int(time.time()))
        sig = self._sig(body, ts)
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET):
            ok, reason = sr._verify_slack_signature(body, ts, sig)
        assert ok is True
        assert reason == "OK"


class TestRateLimit:
    def test_allowed_then_denied(self):
        store = defaultdict(deque)
        with patch.object(sr, "_rate_limit_store", store), \
                patch.object(sr, "_RATE_LIMIT_MAX", 2), \
                patch.object(sr, "_RATE_LIMIT_WINDOW", 60):
            assert sr._check_rate_limit("1.2.3.4") is True
            assert sr._check_rate_limit("1.2.3.4") is True
            assert sr._check_rate_limit("1.2.3.4") is False

    def test_evicts_stale_timestamps(self):
        store = defaultdict(deque)
        store["1.2.3.4"].append(time.time() - 120)  # outside 60s window
        with patch.object(sr, "_rate_limit_store", store), \
                patch.object(sr, "_RATE_LIMIT_MAX", 2), \
                patch.object(sr, "_RATE_LIMIT_WINDOW", 60):
            assert sr._check_rate_limit("1.2.3.4") is True
        assert len(store["1.2.3.4"]) == 1


class TestDispatchAction:
    def test_dispatch_found_ok(self):
        handler = MagicMock(return_value={"handled": True})
        with patch.object(sr, "_SLACK_ACTION_HANDLERS",
                          {"approve": handler}):
            result = sr._dispatch_slack_action(
                {"action_id": "approve"}, {"id": "U1"}, "trig-1")
        assert result["status"] == "dispatched"
        assert result["result"] == {"handled": True}
        handler.assert_called_once_with({"action_id": "approve"})

    def test_dispatch_handler_error(self):
        def handler(action):
            raise RuntimeError("handler bug")
        with patch.object(sr, "_SLACK_ACTION_HANDLERS", {"boom": handler}):
            result = sr._dispatch_slack_action({"action_id": "boom"}, {"id": "U1"}, "t")
        assert result["status"] == "handler_error"
        assert "handler bug" in result["error"]

    def test_dispatch_unhandled(self):
        with patch.object(sr, "_SLACK_ACTION_HANDLERS", {}):
            result = sr._dispatch_slack_action({"action_id": "nope"}, {"id": "U1"}, "t")
        assert result["status"] == "unhandled"
        assert result["action_id"] == "nope"


class TestInteractiveCallback:
    def test_rate_limited(self, client):
        with patch.object(sr, "_RATE_LIMIT_MAX", 0), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(INTERACTIVE_URL, data={"payload": "{}"})
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_no_secret_skips_verification(self, client):
        with patch.object(sr, "SLACK_SIGNING_SECRET", ""), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(
                INTERACTIVE_URL,
                data={"payload": json.dumps({"type": "block_actions",
                                             "actions": [], "user": {"id": "U1"}})})
        assert response.status_code == 200

    def test_invalid_signature_rejected(self, client):
        payload = json.dumps({"type": "block_actions", "actions": []})
        body_bytes = b"payload=" + urllib.parse.quote(payload, safe="").encode()
        ts = str(int(time.time()))
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(
                INTERACTIVE_URL, data=body_bytes, headers={
                    "X-Slack-Request-Timestamp": ts,
                    "X-Slack-Signature": "v0=deadbeef"})
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_valid_signature_dispatches_actions(self, client):
        payload = {
            "type": "block_actions",
            "user": {"id": "U123", "name": "alice"},
            "trigger_id": "trig-9",
            "actions": [{"action_id": "approve"}, {"action_id": "deny"}],
        }
        body_bytes, headers = _signed_form(payload)
        handlers = {
            "approve": MagicMock(return_value={"ok": True}),
            "deny": MagicMock(side_effect=RuntimeError("deny failed")),
        }
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)), \
                patch.object(sr, "_SLACK_ACTION_HANDLERS", handlers):
            response = client.post(INTERACTIVE_URL, data=body_bytes, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        handlers["approve"].assert_called_once()

    def test_missing_payload_field(self, client):
        with patch.object(sr, "SLACK_SIGNING_SECRET", ""), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(INTERACTIVE_URL, data={"other": "x"})
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_invalid_payload_json(self, client):
        with patch.object(sr, "SLACK_SIGNING_SECRET", ""), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(INTERACTIVE_URL, data={"payload": "not-json{{"})
        assert response.status_code == 200

    def test_unexpected_payload_type(self, client):
        with patch.object(sr, "SLACK_SIGNING_SECRET", ""), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(
                INTERACTIVE_URL,
                data={"payload": json.dumps({"type": "mystery_event"})})
        assert response.status_code == 200

    def test_valid_payload_no_actions(self, client):
        body_bytes, headers = _signed_form({"type": "view_submission"})
        with patch.object(sr, "SLACK_SIGNING_SECRET", SECRET), \
                patch.object(sr, "_rate_limit_store", defaultdict(deque)):
            response = client.post(INTERACTIVE_URL, data=body_bytes, headers=headers)
        assert response.status_code == 200


class TestOAuthCallback:
    def test_missing_code_400(self, client):
        response = client.post("/api/slack/callback", json={"state": "s1"})
        assert response.status_code == 400
        assert "Authorization code is required" in response.json()["detail"]

    def test_missing_state_400(self, client):
        response = client.post("/api/slack/callback", json={"code": "c1"})
        assert response.status_code == 400
        assert "State parameter is required" in response.json()["detail"]

    def test_invalid_state_400(self, client):
        state_manager = MagicMock()
        state_manager.validate_state.side_effect = ValueError("expired")
        with patch.object(sr, "get_oauth_state_manager", return_value=state_manager):
            response = client.post("/api/slack/callback",
                                   json={"code": "c1", "state": "tampered"})
        assert response.status_code == 400
        assert "Invalid or expired state parameter" in response.json()["detail"]

    def test_success_flow(self, client, user):
        state_manager = MagicMock()
        state_manager.validate_state.return_value = {"user_id": user.id}

        handler_instance = MagicMock()
        handler_instance.exchange_code_for_tokens = AsyncMock(
            return_value={"access_token": "xoxp-123"})

        connection = MagicMock()
        connection.id = "conn-1"
        connection_service = MagicMock()
        connection_service.save_connection.return_value = connection

        with patch.object(sr, "get_oauth_state_manager", return_value=state_manager), \
                patch.object(sr, "OAuthHandler", return_value=handler_instance), \
                patch("core.connection_service.ConnectionService",
                      return_value=connection_service):
            response = client.post("/api/slack/callback",
                                   json={"code": "c1", "state": "s1"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["connection_id"] == "conn-1"
        state_manager.validate_state.assert_called_once_with(
            "s1", user_id=user.id, require_user_match=True)
        connection_service.save_connection.assert_called_once()
        kwargs = connection_service.save_connection.call_args.kwargs
        assert kwargs["integration_id"] == "slack"
        assert kwargs["credentials"] == {"access_token": "xoxp-123"}

    def test_generic_exception_500(self, client):
        state_manager = MagicMock()
        state_manager.validate_state.return_value = {}
        handler_instance = MagicMock()
        handler_instance.exchange_code_for_tokens = AsyncMock(
            side_effect=RuntimeError("oauth down"))
        with patch.object(sr, "get_oauth_state_manager", return_value=state_manager), \
                patch.object(sr, "OAuthHandler", return_value=handler_instance):
            response = client.post("/api/slack/callback",
                                   json={"code": "c1", "state": "s1"})
        assert response.status_code == 500


class TestAuthUrl:
    def test_get_auth_url_success(self, client, user):
        state_manager = MagicMock()
        state_manager.generate_state.return_value = "state-abc"
        handler_instance = MagicMock()
        handler_instance.get_authorization_url.return_value = "https://slack.com/oauth"
        with patch.object(sr, "get_oauth_state_manager", return_value=state_manager), \
                patch.object(sr, "OAuthHandler", return_value=handler_instance):
            response = client.get("/api/slack/auth/url")
        assert response.status_code == 200
        body = response.json()
        assert body["url"] == "https://slack.com/oauth"
        assert body["state"] == "state-abc"
        state_manager.generate_state.assert_called_once_with(user_id=user.id)

    def test_get_auth_url_exception_500(self, client):
        with patch.object(sr, "get_oauth_state_manager",
                          side_effect=RuntimeError("state store down")):
            response = client.get("/api/slack/auth/url")
        assert response.status_code == 500


class TestImportGuard:
    """Regression: ImportError guard must not crash when slack_sdk is missing
    (logger was referenced before definition)."""

    def test_import_guard_with_missing_sdk(self):
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
