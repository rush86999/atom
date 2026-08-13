# -*- coding: utf-8 -*-
"""Coverage wave 86 — core/google_chat (webhook auth, message formatting, failure).

GoogleChatAdapter tested with httpx fully mocked (no network):

- verify_request: **fail-closed** webhook auth — a Bearer token must match
  GOOGLE_CHAT_WEBHOOK_SECRET; requests without/with wrong tokens are rejected
  and an unconfigured secret fails closed (no traffic accepted).
- normalize_payload: non-MESSAGE events → None, incomplete payloads → None,
  valid MESSAGE → normalized dict with source/channel/sender/content/metadata.
- send_message: HTTP 2xx → True; HTTP error → False; transport exception → False.

Zero LLM spend, no network.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.google_chat import GoogleChatAdapter


@pytest.fixture()
def adapter():
    return GoogleChatAdapter()


# ---------------------------------------------------------------------------
# verify_request — webhook auth (fail-closed)
# ---------------------------------------------------------------------------

def test_verify_request_accepts_valid_bearer(adapter, monkeypatch):
    monkeypatch.setenv("GOOGLE_CHAT_WEBHOOK_SECRET", "topsecret")
    assert adapter.verify_request(
        {"Authorization": "Bearer topsecret"}, '{"type": "MESSAGE"}'
    ) is True


def test_verify_request_rejects_wrong_token(adapter, monkeypatch):
    monkeypatch.setenv("GOOGLE_CHAT_WEBHOOK_SECRET", "topsecret")
    assert adapter.verify_request(
        {"Authorization": "Bearer nope"}, "{}"
    ) is False


def test_verify_request_rejects_missing_auth_header(adapter, monkeypatch):
    monkeypatch.setenv("GOOGLE_CHAT_WEBHOOK_SECRET", "topsecret")
    assert adapter.verify_request({}, "{}") is False


def test_verify_request_fails_closed_when_secret_unconfigured(adapter, monkeypatch):
    monkeypatch.delenv("GOOGLE_CHAT_WEBHOOK_SECRET", raising=False)
    assert adapter.verify_request(
        {"Authorization": "Bearer whatever"}, "{}"
    ) is False


# ---------------------------------------------------------------------------
# normalize_payload
# ---------------------------------------------------------------------------

def _payload(overrides=None, **kwargs):
    payload = {
        "type": "MESSAGE",
        "space": {"name": "spaces/AAA", "type": "ROOM"},
        "message": {
            "name": "spaces/AAA/messages/1",
            "sender": {"name": "users/9", "displayName": "Jane Doe", "email": "jane@example.com"},
            "text": "Hello world",
        },
    }
    payload.update(kwargs)
    if overrides:
        for key, value in overrides.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
    return payload


def test_normalize_payload_valid_message(adapter):
    out = adapter.normalize_payload(_payload())
    assert out == {
        "source": "google_chat",
        "source_id": "spaces/AAA",
        "channel_id": "spaces/AAA",
        "sender_id": "jane@example.com",
        "content": "Hello world",
        "metadata": {"display_name": "Jane Doe", "space_type": "ROOM"},
    }


def test_normalize_payload_skips_non_message_events(adapter):
    assert adapter.normalize_payload({"type": "ADDED_TO_SPACE"}) is None
    assert adapter.normalize_payload({}) is None


def test_normalize_payload_incomplete_message(adapter):
    no_sender = _payload()
    no_sender["message"]["sender"] = {}
    assert adapter.normalize_payload(no_sender) is None

    no_text = _payload()
    no_text["message"]["text"] = ""
    assert adapter.normalize_payload(no_text) is None

    no_space = _payload()
    no_space["space"] = {}
    assert adapter.normalize_payload(no_space) is None


def test_normalize_payload_sender_name_fallback(adapter):
    payload = _payload()
    del payload["message"]["sender"]["email"]
    out = adapter.normalize_payload(payload)
    assert out["sender_id"] == "users/9"
    assert out["metadata"]["display_name"] == "Jane Doe"


def _async_client_mock():
    """httpx.AsyncClient replacement that supports `async with`."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------

def test_send_message_success(adapter):
    client = _async_client_mock()
    response = MagicMock()
    client.post.return_value = response
    response.raise_for_status.return_value = None
    with patch("httpx.AsyncClient", return_value=client):
        result = asyncio.run(adapter.send_message("spaces/AAA", "hi there"))

    assert result is True
    client.post.assert_awaited_once()
    url, kwargs = client.post.await_args.args[0], client.post.await_args.kwargs
    assert url == "https://chat.googleapis.com/v1/spaces/AAA/messages"
    assert kwargs["json"] == {"text": "hi there"}
    assert kwargs["headers"]["Content-Type"] == "application/json; charset=UTF-8"


def test_send_message_http_error(adapter):
    client = _async_client_mock()
    response = MagicMock()
    client.post.return_value = response
    response.raise_for_status.side_effect = Exception("403 Forbidden")
    with patch("httpx.AsyncClient", return_value=client):
        result = asyncio.run(adapter.send_message("spaces/AAA", "hi"))

    assert result is False


def test_send_message_transport_exception(adapter):
    client = _async_client_mock()
    client.post.side_effect = Exception("connection reset")
    with patch("httpx.AsyncClient", return_value=client):
        result = asyncio.run(adapter.send_message("spaces/AAA", "hi"))

    assert result is False
