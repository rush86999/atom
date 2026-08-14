# -*- coding: utf-8 -*-
"""Coverage wave 94 — integrations/atom_communication_memory_webhooks.py
(TDD, fully mocked — no network).

Closes the remaining branch gaps (~97% baseline from earlier waves): the
FAIL-CLOSED signature-mismatch 401 paths for slack/discord/gmail/outlook
endpoints, the WhatsApp processor exception path, plus missing-header
failures for every provider, slack stale/invalid timestamps, secret-token
flows for telegram, end-to-end processor flows for all six providers
(normalization + ingestion + no-payload no-op), verify_token passthrough,
get_router, and the health endpoint. Note: this module has NO message
dedup of its own — dedup lives downstream in the ingestion pipeline.
"""
import asyncio
import hashlib
import hmac
import json
import time
import types
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from integrations import atom_communication_memory_webhooks as webhooks_mod


def route_endpoint(router, path):
    for r in router.routes:
        if getattr(r, "path", None) == path:
            return r.endpoint
    raise AssertionError(f"route {path} not found")


def make_request(body: bytes):
    scope = {
        "type": "http", "method": "POST", "path": "/webhook", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "scheme": "http",
        "client": ("1.2.3.4", 1234),
    }
    req = types.SimpleNamespace()
    async def _body():
        return body
    req._body = _body
    req.scope = scope
    req.body = _body
    return req


def _webhooks(env_secrets=None):
    with patch.dict("os.environ", env_secrets or {}, clear=False):
        return webhooks_mod.AtomCommunicationMemoryWebhooks()


def _sig(secret: str, body: bytes, prefix: str = "") -> str:
    return prefix + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


WHATSAPP_BODY = json.dumps({
    "entry": [{"changes": [{"value": {
        "messages": [{"id": "w1", "from": "1555", "type": "text",
                      "text": {"body": "hello"}}],
        "metadata": {"phone_number_id": "999"},
    }}]}]
}).encode()


class TestVerifySignature:
    def test_missing_secret_fails_closed(self):
        wh = _webhooks()
        assert wh.verify_webhook_signature("slack", None, "v0=abc", b"body") is False

    def test_meta_prefix_stripped(self):
        wh = _webhooks({"ATOM_WHATSAPP_WEBHOOK_SECRET": "w"})
        body = b"payload"
        raw = hmac.new(b"w", body, hashlib.sha256).hexdigest()
        assert wh.verify_webhook_signature("whatsapp", None, "sha256=" + raw, body) is True

    def test_v0_prefix_stripped(self):
        wh = _webhooks({"ATOM_SLACK_WEBHOOK_SECRET": "s"})
        body = b"payload"
        raw = hmac.new(b"s", body, hashlib.sha256).hexdigest()
        assert wh.verify_webhook_signature("slack", None, "v0=" + raw, body) is True

    def test_slack_signing_key_includes_timestamp(self):
        wh = _webhooks({"ATOM_SLACK_WEBHOOK_SECRET": "s"})
        body = b"payload"
        ts = "1700000000"
        key = f"v0:{ts}:".encode() + body
        raw = hmac.new(b"s", key, hashlib.sha256).hexdigest()
        assert wh.verify_webhook_signature(
            "slack", None, raw, body, timestamp=ts) is True

    def test_mismatch_fails(self):
        wh = _webhooks({"ATOM_WHATSAPP_WEBHOOK_SECRET": "w"})
        assert wh.verify_webhook_signature("whatsapp", None, "deadbeef", b"body") is False

    def test_exception_fails_closed(self):
        wh = _webhooks({"ATOM_WHATSAPP_WEBHOOK_SECRET": "w"})
        with patch.object(webhooks_mod.hmac, "new",
                          side_effect=RuntimeError("boom")):
            assert wh.verify_webhook_signature(
                "whatsapp", None, "sig", b"body") is False

    def test_unknown_provider_fails_closed(self):
        wh = _webhooks()
        assert wh.verify_webhook_signature("mystery_app", None, "sig", b"body") is False


class TestWhatsAppEndpoint:
    def test_missing_signature_header_401(self):
        wh = _webhooks({"ATOM_WHATSAPP_WEBHOOK_SECRET": "w"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"),
                                 background_tasks=Mock(), x_hub_signature_256=None,
                                 token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_invalid_signature_401(self):
        wh = _webhooks({"ATOM_WHATSAPP_WEBHOOK_SECRET": "w"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(WHATSAPP_BODY),
                                 background_tasks=Mock(),
                                 x_hub_signature_256="sha256=badsig", token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_unconfigured_secret_fails_closed(self):
        wh = _webhooks()
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(WHATSAPP_BODY),
                                 background_tasks=Mock(),
                                 x_hub_signature_256=_sig("w", WHATSAPP_BODY, "sha256="),
                                 token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_valid_signature_schedules_processing(self):
        wh = _webhooks({"ATOM_WHATSAPP_WEBHOOK_SECRET": "w"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        background_tasks = Mock()
        with patch.object(wh, "_process_whatsapp_webhook") as proc:
            result = asyncio.run(endpoint(
                request=make_request(WHATSAPP_BODY), background_tasks=background_tasks,
                x_hub_signature_256=_sig("w", WHATSAPP_BODY, "sha256="), token={}))
        assert result["status"] == "received"
        added = background_tasks.add_task.call_args
        assert added[0][0] is proc
        assert added[0][1]["entry"][0]["changes"][0]["value"]["messages"][0]["id"] == "w1"

    def test_invalid_json_500(self):
        wh = _webhooks({"ATOM_WHATSAPP_WEBHOOK_SECRET": "w"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        body = b"not-json{"
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                 x_hub_signature_256=_sig("w", body, "sha256="),
                                 token={}))
        assert getattr(exc.value, "status_code", None) == 500
        assert "not-json" not in str(getattr(exc.value, "detail", ""))


class TestSlackEndpoint:
    def test_missing_headers_401(self):
        wh = _webhooks({"ATOM_SLACK_WEBHOOK_SECRET": "s"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/slack")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_slack_signature=None,
                                 x_slack_request_timestamp=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_invalid_timestamp_401(self):
        wh = _webhooks({"ATOM_SLACK_WEBHOOK_SECRET": "s"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/slack")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_slack_signature="v0=abc",
                                 x_slack_request_timestamp="notanint", token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_stale_timestamp_401(self):
        wh = _webhooks({"ATOM_SLACK_WEBHOOK_SECRET": "s"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/slack")
        stale = int(time.time()) - 3600
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_slack_signature="v0=abc",
                                 x_slack_request_timestamp=str(stale), token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_invalid_signature_401(self):
        wh = _webhooks({"ATOM_SLACK_WEBHOOK_SECRET": "s"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/slack")
        now = str(int(time.time()))
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_slack_signature="v0=wrong",
                                 x_slack_request_timestamp=now, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_valid_signature_schedules_processing(self):
        wh = _webhooks({"ATOM_SLACK_WEBHOOK_SECRET": "s"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/slack")
        body = json.dumps({"event": {"type": "message", "ts": "1.0"}}).encode()
        now = str(int(time.time()))
        key = f"v0:{now}:".encode() + body
        sig = hmac.new(b"s", key, hashlib.sha256).hexdigest()
        background_tasks = Mock()
        with patch.object(wh, "_process_slack_webhook") as proc:
            result = asyncio.run(endpoint(
                request=make_request(body), background_tasks=background_tasks,
                x_slack_signature="v0=" + sig,
                x_slack_request_timestamp=now, token={}))
        assert result["status"] == "received"
        assert background_tasks.add_task.call_args[0][0] is proc


class TestDiscordEndpoint:
    def test_missing_headers_401(self):
        wh = _webhooks({"ATOM_DISCORD_WEBHOOK_SECRET": "d"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/discord")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_signature_ed25519=None, x_signature_timestamp=None,
                                 token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_invalid_signature_401(self):
        wh = _webhooks({"ATOM_DISCORD_WEBHOOK_SECRET": "d"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/discord")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_signature_ed25519="bad",
                                 x_signature_timestamp="123", token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_valid_signature_schedules_processing(self):
        wh = _webhooks({"ATOM_DISCORD_WEBHOOK_SECRET": "d"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/discord")
        body = json.dumps({"message": {"id": "1"}}).encode()
        background_tasks = Mock()
        with patch.object(wh, "_process_discord_webhook") as proc:
            result = asyncio.run(endpoint(
                request=make_request(body), background_tasks=background_tasks,
                x_signature_ed25519=_sig("d", body), x_signature_timestamp="123",
                token={}))
        assert result["status"] == "received"
        assert background_tasks.add_task.call_args[0][0] is proc


class TestTelegramEndpoint:
    def test_missing_secret_header_401(self):
        wh = _webhooks({"ATOM_TELEGRAM_WEBHOOK_SECRET": "tg"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/telegram")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_telegram_bot_api_secret_token=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_invalid_secret_401(self):
        wh = _webhooks({"ATOM_TELEGRAM_WEBHOOK_SECRET": "tg"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/telegram")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_telegram_bot_api_secret_token="wrong", token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_valid_secret_schedules_processing(self):
        wh = _webhooks({"ATOM_TELEGRAM_WEBHOOK_SECRET": "tg"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/telegram")
        body = json.dumps({"message": {"message_id": 1}}).encode()
        background_tasks = Mock()
        with patch.object(wh, "_process_telegram_webhook") as proc:
            result = asyncio.run(endpoint(
                request=make_request(body), background_tasks=background_tasks,
                x_telegram_bot_api_secret_token=_sig("tg", body), token={}))
        assert result["status"] == "received"
        assert background_tasks.add_task.call_args[0][0] is proc


class TestGmailOutlookEndpoints:
    def test_gmail_missing_secret_401(self):
        wh = _webhooks({"ATOM_GMAIL_WEBHOOK_SECRET": "g"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/gmail")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_atom_webhook_secret=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_gmail_invalid_secret_401(self):
        wh = _webhooks({"ATOM_GMAIL_WEBHOOK_SECRET": "g"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/gmail")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_atom_webhook_secret="wrong", token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_gmail_valid_secret_schedules_processing(self):
        wh = _webhooks({"ATOM_GMAIL_WEBHOOK_SECRET": "g"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/gmail")
        body = json.dumps({"message": {"id": "1"}}).encode()
        background_tasks = Mock()
        with patch.object(wh, "_process_gmail_webhook") as proc:
            result = asyncio.run(endpoint(
                request=make_request(body), background_tasks=background_tasks,
                x_atom_webhook_secret=_sig("g", body), token={}))
        assert result["status"] == "received"
        assert background_tasks.add_task.call_args[0][0] is proc

    def test_outlook_missing_secret_401(self):
        wh = _webhooks({"ATOM_OUTLOOK_WEBHOOK_SECRET": "o"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/outlook")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_atom_webhook_secret=None, token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_outlook_invalid_secret_401(self):
        wh = _webhooks({"ATOM_OUTLOOK_WEBHOOK_SECRET": "o"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/outlook")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(b"{}"), background_tasks=Mock(),
                                 x_atom_webhook_secret="wrong", token={}))
        assert getattr(exc.value, "status_code", None) == 401

    def test_outlook_valid_secret_schedules_processing(self):
        wh = _webhooks({"ATOM_OUTLOOK_WEBHOOK_SECRET": "o"})
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/outlook")
        body = json.dumps({"value": [{"id": "1"}]}).encode()
        background_tasks = Mock()
        with patch.object(wh, "_process_outlook_webhook") as proc:
            result = asyncio.run(endpoint(
                request=make_request(body), background_tasks=background_tasks,
                x_atom_webhook_secret=_sig("o", body), token={}))
        assert result["status"] == "received"
        assert background_tasks.add_task.call_args[0][0] is proc


class TestInvalidJson500Paths:
    def _bad_json_401_or_500(self, wh, path, headers_kwargs, body=b"not-json{{"):
        endpoint = route_endpoint(wh.router, path)
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                 **headers_kwargs))
        return getattr(exc.value, "status_code", None)

    def test_slack_invalid_json_500(self):
        wh = _webhooks({"ATOM_SLACK_WEBHOOK_SECRET": "s"})
        now = str(int(time.time()))
        body = b"not-json{{"
        key = f"v0:{now}:".encode() + body
        sig = hmac.new(b"s", key, hashlib.sha256).hexdigest()
        status = self._bad_json_401_or_500(
            wh, "/api/webhooks/communication/slack",
            {"x_slack_signature": "v0=" + sig, "x_slack_request_timestamp": now,
             "token": {}}, body=body)
        assert status == 500

    def test_discord_invalid_json_500(self):
        wh = _webhooks({"ATOM_DISCORD_WEBHOOK_SECRET": "d"})
        body = b"not-json{{"
        status = self._bad_json_401_or_500(
            wh, "/api/webhooks/communication/discord",
            {"x_signature_ed25519": _sig("d", body),
             "x_signature_timestamp": "123", "token": {}}, body=body)
        assert status == 500

    def test_telegram_invalid_json_500(self):
        wh = _webhooks({"ATOM_TELEGRAM_WEBHOOK_SECRET": "tg"})
        body = b"not-json{{"
        status = self._bad_json_401_or_500(
            wh, "/api/webhooks/communication/telegram",
            {"x_telegram_bot_api_secret_token": _sig("tg", body), "token": {}},
            body=body)
        assert status == 500

    def test_gmail_invalid_json_500(self):
        wh = _webhooks({"ATOM_GMAIL_WEBHOOK_SECRET": "g"})
        body = b"not-json{{"
        status = self._bad_json_401_or_500(
            wh, "/api/webhooks/communication/gmail",
            {"x_atom_webhook_secret": _sig("g", body), "token": {}}, body=body)
        assert status == 500

    def test_outlook_invalid_json_500(self):
        wh = _webhooks({"ATOM_OUTLOOK_WEBHOOK_SECRET": "o"})
        body = b"not-json{{"
        status = self._bad_json_401_or_500(
            wh, "/api/webhooks/communication/outlook",
            {"x_atom_webhook_secret": _sig("o", body), "token": {}}, body=body)
        assert status == 500

    def test_invalid_json_500_does_not_leak_body(self):
        wh = _webhooks({"ATOM_WHATSAPP_WEBHOOK_SECRET": "w"})
        body = b"secret-token-xyz{{"
        endpoint = route_endpoint(wh.router, "/api/webhooks/communication/whatsapp")
        with pytest.raises(Exception) as exc:
            asyncio.run(endpoint(request=make_request(body), background_tasks=Mock(),
                                 x_hub_signature_256=_sig("w", body, "sha256="),
                                 token={}))
        assert getattr(exc.value, "status_code", None) == 500
        assert "secret-token-xyz" not in str(getattr(exc.value, "detail", ""))


class TestHealthAndHelpers:
    def test_health_endpoint(self):
        wh = _webhooks()
        result = asyncio.run(route_endpoint(
            wh.router, "/api/webhooks/communication/health")())
        assert result["status"] == "healthy"
        assert set(result["webhooks"]) == {
            "whatsapp", "slack", "discord", "telegram", "gmail", "outlook"}

    def test_get_router(self):
        wh = _webhooks()
        assert wh.get_router() is wh.router

    def test_verify_token_passthrough(self):
        payload = {"sub": "u1"}
        assert webhooks_mod.verify_token(payload) is payload


class TestProcessors:
    def test_whatsapp_processor_full_flow(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(wh._process_whatsapp_webhook(json.loads(WHATSAPP_BODY.decode())))
        msg = pipe.ingest_message.call_args[0][1]
        assert msg["direction"] == "inbound"
        assert msg["from"] == "1555"
        assert msg["to"] == "999"
        assert msg["content"] == "hello"
        assert msg["metadata"]["whatsapp_webhook"] is True

    def test_whatsapp_processor_exception_no_raise(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(side_effect=RuntimeError("boom-secret"))
            asyncio.run(wh._process_whatsapp_webhook(json.loads(WHATSAPP_BODY.decode())))
        pipe.ingest_message.assert_awaited_once()

    def test_whatsapp_processor_skips_entry_without_changes(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(wh._process_whatsapp_webhook(
                {"entry": [{"changes": [{"value": {"statuses": []}}]}]}))
        pipe.ingest_message.assert_not_awaited()

    def test_slack_processor_full_flow(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(wh._process_slack_webhook({"event": {
                "type": "message", "ts": "1700000000.123", "user": "u1",
                "channel": "c1", "text": "hi", "channel_type": "channel"}}))
        msg = pipe.ingest_message.call_args[0][1]
        assert msg["id"] == "1700000000.123"
        assert msg["sender"] == "u1"
        assert msg["recipient"] == "c1"
        assert msg["timestamp"].startswith("2023-11")
        assert msg["metadata"]["slack_webhook"] is True

    def test_slack_processor_skips_non_message_events(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(wh._process_slack_webhook({"event": {"type": "reaction_added"}}))
        pipe.ingest_message.assert_not_awaited()

    def test_discord_processor_full_flow(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(wh._process_discord_webhook({"message": {
                "id": "d1", "author": {"id": "a1"}, "channel_id": "ch1",
                "content": "hi"}}))
        msg = pipe.ingest_message.call_args[0][1]
        assert msg["id"] == "d1"
        assert msg["sender"] == "a1"
        assert msg["recipient"] == "ch1"

    def test_telegram_processor_full_flow(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(wh._process_telegram_webhook({"message": {
                "message_id": 42, "from": {"id": 7}, "chat": {"id": 99},
                "text": "hi"}}))
        msg = pipe.ingest_message.call_args[0][1]
        assert msg["id"] == "42"
        assert msg["sender"] == "7"
        assert msg["recipient"] == "99"
        assert msg["content"] == "hi"

    def test_gmail_processor_full_flow(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(wh._process_gmail_webhook({"message": {
                "id": "g1", "sender": "a@x.com", "to": "b@x.com", "subject": "S",
                "body": "B", "thread_id": "t1", "labels": ["INBOX"]}}))
        msg = pipe.ingest_message.call_args[0][1]
        assert msg["message_type"] == "email"
        assert msg["metadata"]["thread_id"] == "t1"
        assert msg["content"] == "B"

    def test_outlook_processor_full_flow(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(wh._process_outlook_webhook({"value": [
                {"id": "o1", "from": {"emailAddress": "a@x.com"},
                 "toRecipients": [{"emailAddress": "b@x.com"},
                                  {"emailAddress": "c@x.com"}],
                 "subject": "S", "body": {"content": "B"},
                 "conversationId": "conv1", "webLink": "https://x"}]}))
        msg = pipe.ingest_message.call_args[0][1]
        assert msg["to"] == "b@x.com, c@x.com"
        assert msg["metadata"]["conversation_id"] == "conv1"
        assert msg["content"] == "B"

    def test_outlook_processor_no_value_noop(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(return_value=True)
            asyncio.run(wh._process_outlook_webhook({}))
        pipe.ingest_message.assert_not_awaited()

    def test_all_processors_swallow_exceptions(self):
        wh = _webhooks()
        with patch.object(webhooks_mod, "ingestion_pipeline") as pipe:
            pipe.ingest_message = AsyncMock(side_effect=RuntimeError("boom"))
            asyncio.run(wh._process_slack_webhook(
                {"event": {"type": "message", "ts": "1"}}))
            asyncio.run(wh._process_discord_webhook({"message": {"id": "1"}}))
            asyncio.run(wh._process_telegram_webhook({"message": {"message_id": 1}}))
            asyncio.run(wh._process_gmail_webhook({"message": {"id": "1"}}))
            asyncio.run(wh._process_outlook_webhook({"value": [{"id": "1"}]}))


class TestModuleExports:
    def test_global_instance_and_router(self):
        assert webhooks_mod.atom_memory_webhooks_router is not None
        assert webhooks_mod.atom_memory_webhooks is webhooks_mod.atom_memory_webhooks
        assert webhooks_mod.__all__ == [
            "AtomCommunicationMemoryWebhooks", "atom_memory_webhooks",
            "atom_memory_webhooks_router"]
