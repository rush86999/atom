# -*- coding: utf-8 -*-
"""Coverage wave 88 — core/signal (40 stmts, never wave-tested).

- SignalAdapter: default + custom api_url, verify_request always True.
- normalize_payload: full payload mapping, missing sender → None, missing
  content → None, empty payload → None.
- send_message: success 2xx returns True (URL /v2/send + payload shape with
  recipients [target_id] and message), non-2xx raise_for_status → False,
  transport exception → False, log output on both paths.

No network (httpx.AsyncClient faked) / no LLM.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from core.signal import SignalAdapter


def _http_response(status_code):
    resp = SimpleNamespace(status_code=status_code)
    resp.raise_for_status = MagicMock()
    return resp


def _patch_client(response=None, exc=None):
    client = MagicMock()
    if exc is not None:
        client.post = AsyncMock(side_effect=exc)
    else:
        client.post = AsyncMock(return_value=response)
    client.__aenter__.return_value = client
    return patch("httpx.AsyncClient", return_value=client)


class TestSignalAdapterConfig:
    def test_default_api_url(self):
        assert SignalAdapter().api_url == "http://localhost:8080"

    def test_custom_api_url(self):
        assert SignalAdapter("http://signal:3000").api_url == "http://signal:3000"

    def test_verify_request_always_true(self):
        assert SignalAdapter().verify_request({"X-Token": "x"}, "body") is True


class TestNormalizePayload:
    def test_full_payload_mapped(self):
        out = SignalAdapter().normalize_payload({"source": "+15550001", "message": "hello"})
        assert out == {
            "source": "signal",
            "source_id": "+15550001",
            "channel_id": "+15550001",
            "sender_id": "+15550001",
            "content": "hello",
        }

    def test_missing_sender_returns_none(self):
        assert SignalAdapter().normalize_payload({"message": "hello"}) is None

    def test_missing_content_returns_none(self):
        assert SignalAdapter().normalize_payload({"source": "+15550001"}) is None

    def test_empty_payload_returns_none(self):
        assert SignalAdapter().normalize_payload({}) is None


class TestSendMessage:
    def test_success_returns_true(self):
        with _patch_client(_http_response(200)) as ac:
            assert asyncio.run(SignalAdapter().send_message("+15550002", "hi")) is True
        call = ac.return_value.post.await_args
        assert call.args[0] == "http://localhost:8080/v2/send"
        payload = call.kwargs["json"]
        assert payload["message"] == "hi"
        assert payload["recipients"] == ["+15550002"]

    def test_uses_custom_url(self):
        with _patch_client(_http_response(200)) as ac:
            asyncio.run(SignalAdapter("http://bridge:9999").send_message("t", "m"))
        assert ac.return_value.post.await_args.args[0] == "http://bridge:9999/v2/send"

    def test_non_2xx_returns_false(self):
        # raise_for_status on a fake response must raise for non-2xx.
        resp = _http_response(500)
        resp.raise_for_status = MagicMock(side_effect=RuntimeError("HTTP 500"))
        with _patch_client(resp):
            assert asyncio.run(SignalAdapter().send_message("t", "m")) is False

    def test_exception_returns_false(self):
        with _patch_client(exc=RuntimeError("connection refused")):
            assert asyncio.run(SignalAdapter().send_message("t", "m")) is False

    def test_success_logs_info(self, caplog):
        with caplog.at_level("INFO", logger="core.signal"):
            with _patch_client(_http_response(200)):
                asyncio.run(SignalAdapter().send_message("+1555", "m"))
        assert "Sent message to +1555" in caplog.text

    def test_failure_logs_error(self, caplog):
        with caplog.at_level("ERROR", logger="core.signal"):
            with _patch_client(exc=RuntimeError("down")):
                asyncio.run(SignalAdapter().send_message("t", "m"))
        assert "Failed to send Signal message" in caplog.text
