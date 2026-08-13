"""Coverage wave W70a — core/communication/adapters sibling modules.

Targets (>=95% statement coverage, standalone):
- matrix.py     (was 100% via other suites — re-cover standalone)
- whatsapp.py   (was 15%)
- facebook.py   (was 98%)
- email.py      (was 19%)
- intercom.py   (was 99%)
- sms.py        (was 36%)
- discord.py    (was 29%)

Pattern: pure unit tests, mocked deps, ZERO LLM spend, no network (httpx
mocked via `patch("httpx.AsyncClient")`), no DB. All `async` methods driven
via asyncio.run from sync tests (matching test_covpush_w69b_adapters.py).

Bugs found + fixed in the assigned modules (regression tests below):
1. email.py:46 — `self.ses_client = None` ran UNCONDITIONALLY after client
   creation, so the boto3 sesv2 client was always discarded and
   send_message always returned False ("SES Client not available").
   Fix: null the client only in the creation-failure branch.
   Regression: test_init_retains_created_ses_client.
2. discord.py:96 — `custom_id = data.get("custom_id")` then `.replace()` on
   None raised AttributeError (crash) for a component interaction without
   custom_id. Fix: `data.get("custom_id") or ""`.
   Regression: test_normalize_component_without_custom_id.
"""
import asyncio
import hashlib
import hmac
import json
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import Request


def _mock_request(headers=None):
    req = MagicMock(spec=Request)
    req.headers = headers or {}
    return req


def _wa_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _ed_keypair():
    """Return (adapter_hex_public_key, private_key) for Discord signing."""
    priv = Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()
    return pub_hex, priv


def _http_client(post_result=None, put_result=None, get_side_effect=None, post_side_effect=None):
    client = AsyncMock()
    client.__aenter__.return_value = client
    if post_result is not None:
        client.post = AsyncMock(return_value=post_result)
    if post_side_effect is not None:
        client.post = AsyncMock(side_effect=post_side_effect)
    if put_result is not None:
        client.put = AsyncMock(return_value=put_result)
    if get_side_effect is not None:
        client.get = AsyncMock(side_effect=get_side_effect)
    return client


# ===========================================================================
# core/communication/adapters/matrix.py
# ===========================================================================

class TestMatrixAdapter:
    def test_init_defaults(self):
        from core.communication.adapters.matrix import MatrixAdapter
        adapter = MatrixAdapter()
        assert adapter.homeserver_url == "https://matrix.org"
        assert adapter.access_token is None

    def test_init_explicit(self):
        from core.communication.adapters.matrix import MatrixAdapter
        adapter = MatrixAdapter(homeserver_url="https://hs.example", access_token="tok")
        assert adapter.homeserver_url == "https://hs.example"
        assert adapter.access_token == "tok"

    def test_verify_request_always_true(self):
        from core.communication.adapters.matrix import MatrixAdapter
        assert MatrixAdapter().verify_request({}, "") is True

    def test_normalize_wrong_type(self):
        from core.communication.adapters.matrix import MatrixAdapter
        assert MatrixAdapter().normalize_payload({"type": "m.room.membership"}) is None

    def test_normalize_missing_sender(self):
        from core.communication.adapters.matrix import MatrixAdapter
        payload = {"type": "m.room.message", "content": {"body": "hi"}, "room_id": "!r"}
        assert MatrixAdapter().normalize_payload(payload) is None

    def test_normalize_missing_body(self):
        from core.communication.adapters.matrix import MatrixAdapter
        payload = {"type": "m.room.message", "sender": "@u:hs", "room_id": "!r"}
        assert MatrixAdapter().normalize_payload(payload) is None

    def test_normalize_missing_room_id(self):
        from core.communication.adapters.matrix import MatrixAdapter
        payload = {"type": "m.room.message", "sender": "@u:hs", "content": {"body": "hi"}}
        assert MatrixAdapter().normalize_payload(payload) is None

    def test_normalize_success(self):
        from core.communication.adapters.matrix import MatrixAdapter
        payload = {
            "type": "m.room.message",
            "sender": "@u:hs",
            "content": {"msgtype": "m.text", "body": "hello"},
            "room_id": "!r:hs",
        }
        out = MatrixAdapter().normalize_payload(payload)
        assert out == {
            "source": "matrix",
            "source_id": "!r:hs",
            "channel_id": "!r:hs",
            "sender_id": "@u:hs",
            "content": "hello",
            "metadata": {"msgtype": "m.text"},
        }

    def test_send_message_no_token(self):
        from core.communication.adapters.matrix import MatrixAdapter
        assert asyncio.run(MatrixAdapter().send_message("!r", "hi")) is False

    def test_send_message_success(self):
        from core.communication.adapters.matrix import MatrixAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(put_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                MatrixAdapter(homeserver_url="https://hs", access_token="tok").send_message("!r", "hi")
            )
        assert result is True
        assert client.put.await_count == 1
        call = client.put.await_args
        assert call.args[0].startswith("https://hs/_matrix/client/v3/rooms/!r/send/m.room.message/")
        assert call.kwargs["json"] == {"msgtype": "m.text", "body": "hi"}
        assert call.kwargs["headers"]["Authorization"] == "Bearer tok"

    def test_send_message_error(self):
        from core.communication.adapters.matrix import MatrixAdapter
        response = Mock()
        response.raise_for_status = Mock(side_effect=RuntimeError("matrix down"))
        client = _http_client(put_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                MatrixAdapter(homeserver_url="https://hs", access_token="tok").send_message("!r", "hi")
            )
        assert result is False

    def test_send_media_default(self):
        from core.communication.adapters.matrix import MatrixAdapter
        assert asyncio.run(MatrixAdapter().get_media("m1")) is None


# ===========================================================================
# core/communication/adapters/whatsapp.py
# ===========================================================================

class TestWhatsAppAdapter:
    def test_init_explicit(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        adapter = WhatsAppAdapter(access_token="tok", phone_number_id="123", app_secret="sec")
        assert adapter.access_token == "tok"
        assert adapter.phone_number_id == "123"
        assert adapter.app_secret == "sec"
        assert adapter.api_version == "v17.0"
        assert adapter.base_url == "https://graph.facebook.com/v17.0/123"

    def test_init_from_env(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "env-tok")
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "env-sec")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "env-phone")
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        adapter = WhatsAppAdapter()
        assert adapter.access_token == "env-tok"
        assert adapter.app_secret == "env-sec"
        assert adapter.phone_number_id == "env-phone"

    def test_get_access_token_from_refresher(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        adapter = WhatsAppAdapter(access_token="own-tok")
        with patch("core.token_refresher.token_refresher.get_status",
                   return_value={"whatsapp": {"access_token": "fresh-tok"}}):
            assert asyncio.run(adapter._get_access_token()) == "fresh-tok"

    def test_get_access_token_fallback(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        adapter = WhatsAppAdapter(access_token="own-tok")
        with patch("core.token_refresher.token_refresher.get_status", return_value={}):
            assert asyncio.run(adapter._get_access_token()) == "own-tok"
        with patch("core.token_refresher.token_refresher.get_status",
                   return_value={"whatsapp": {}}):
            assert asyncio.run(adapter._get_access_token()) == "own-tok"

    def test_verify_no_secret_dev_mode(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        assert asyncio.run(WhatsAppAdapter().verify_request(_mock_request(), b"{}")) is True

    def test_verify_no_secret_prod_mode(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        assert asyncio.run(WhatsAppAdapter().verify_request(_mock_request(), b"{}")) is False

    def test_verify_missing_signature(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        adapter = WhatsAppAdapter(access_token="t", phone_number_id="1", app_secret="sec")
        assert asyncio.run(adapter.verify_request(_mock_request(), b"{}")) is False

    def test_verify_bad_signature_prefix(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        adapter = WhatsAppAdapter(access_token="t", phone_number_id="1", app_secret="sec")
        req = _mock_request({"X-Hub-Signature-256": "hmac-deadbeef"})
        assert asyncio.run(adapter.verify_request(req, b"{}")) is False

    def test_verify_valid_signature(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        adapter = WhatsAppAdapter(access_token="t", phone_number_id="1", app_secret="sec")
        body = b'{"hello": "world"}'
        req = _mock_request({"X-Hub-Signature-256": _wa_signature("sec", body)})
        assert asyncio.run(adapter.verify_request(req, body)) is True

    def test_verify_mismatched_signature(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        adapter = WhatsAppAdapter(access_token="t", phone_number_id="1", app_secret="sec")
        req = _mock_request({"X-Hub-Signature-256": _wa_signature("other-secret", b"{}")})
        assert asyncio.run(adapter.verify_request(req, b"{}")) is False

    def test_normalize_malformed(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        adapter = WhatsAppAdapter()
        assert adapter.normalize_payload({}) is None
        assert adapter.normalize_payload({"entry": []}) is None
        assert adapter.normalize_payload({"entry": [{}]}) is None

    def test_normalize_status_update_ignored(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "s1"}]}}]}]}
        assert WhatsAppAdapter().normalize_payload(payload) is None

    def test_normalize_text_message(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        payload = {
            "entry": [{"changes": [{"value": {
                "messages": [{"from": "+1555", "type": "text", "text": {"body": "hello"}}]
            }}]}],
        }
        out = WhatsAppAdapter().normalize_payload(payload)
        assert out["sender_id"] == "+1555"
        assert out["channel_id"] == "+1555"
        assert out["content"] == "hello"
        assert out["is_interaction"] is False
        assert out["metadata"] is payload

    def test_normalize_interactive_button_reply(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        payload = {
            "entry": [{"changes": [{"value": {
                "messages": [{"from": "+1555", "type": "interactive",
                              "interactive": {"type": "button_reply",
                                              "button_reply": {"id": "APPROVE action_9"}}}]
            }}]}],
        }
        out = WhatsAppAdapter().normalize_payload(payload)
        assert out["content"] == "APPROVE action_9"
        assert out["is_interaction"] is True

    def test_normalize_interactive_other(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        payload = {
            "entry": [{"changes": [{"value": {
                "messages": [{"from": "+1555", "type": "interactive",
                              "interactive": {"type": "list_reply", "list_reply": {"id": "x"}}}]
            }}]}],
        }
        out = WhatsAppAdapter().normalize_payload(payload)
        assert out["content"] == "[Interactive Message]"

    def test_normalize_audio_message(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        payload = {
            "entry": [{"changes": [{"value": {
                "messages": [{"from": "+1555", "type": "audio", "audio": {"id": "media-1"}}]
            }}]}],
        }
        out = WhatsAppAdapter().normalize_payload(payload)
        assert out["content"] == "[Audio Message]"
        assert out["metadata"]["media_id"] == "media-1"
        assert out["metadata"]["media_type"] == "audio"

    def test_normalize_other_type(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        payload = {
            "entry": [{"changes": [{"value": {
                "messages": [{"from": "+1555", "type": "image", "image": {"id": "i1"}}]
            }}]}],
        }
        out = WhatsAppAdapter().normalize_payload(payload)
        assert out["content"] == "[Non-text message: image]"

    def test_send_message_missing_creds(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        assert asyncio.run(WhatsAppAdapter().send_message("+1555", "hi")) is False

    def test_send_message_success(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                WhatsAppAdapter(access_token="tok", phone_number_id="123").send_message("+1555", "hi")
            )
        assert result is True
        call = client.post.await_args
        assert call.args[0] == "https://graph.facebook.com/v17.0/123/messages"
        assert call.kwargs["json"]["to"] == "+1555"
        assert call.kwargs["json"]["text"] == {"body": "hi"}

    def test_send_message_error(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        response = Mock()
        response.raise_for_status = Mock(side_effect=RuntimeError("graph down"))
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                WhatsAppAdapter(access_token="tok", phone_number_id="123").send_message("+1555", "hi")
            )
        assert result is False

    def test_send_approval_missing_creds_falls_back(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        adapter = WhatsAppAdapter()
        with patch.object(WhatsAppAdapter, "send_message", AsyncMock(return_value=True)) as sm:
            result = asyncio.run(adapter.send_approval_request("+1555", "a1", {"action_type": "x"}, "HIGH"))
        assert result is True
        sm.assert_awaited_once()

    def test_send_approval_success(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                WhatsAppAdapter(access_token="tok", phone_number_id="123")
                .send_approval_request("+1555", "a1", {"action_type": "refund", "reason": "dup"}, "HIGH")
            )
        assert result is True
        payload = client.post.await_args.kwargs["json"]
        assert payload["type"] == "interactive"
        ids = [b["reply"]["id"] for b in payload["interactive"]["action"]["buttons"]]
        assert ids == ["APPROVE a1", "REJECT a1"]

    def test_send_approval_error_fallback_fails(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        client = _http_client(post_side_effect=RuntimeError("graph down"))
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                WhatsAppAdapter(access_token="tok", phone_number_id="123")
                .send_approval_request("+1555", "a1", {}, "LOW")
            )
        assert result is False

    def test_send_approval_error_fallback_succeeds(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(post_side_effect=[RuntimeError("graph down"), response])
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                WhatsAppAdapter(access_token="tok", phone_number_id="123")
                .send_approval_request("+1555", "a1", {}, "LOW")
            )
        assert result is True

    def test_get_media_no_token(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        assert asyncio.run(WhatsAppAdapter().get_media("m1")) is None

    def test_get_media_fetch_info_error(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        client = _http_client(get_side_effect=RuntimeError("network"))
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                WhatsAppAdapter(access_token="tok").get_media("m1")
            )
        assert result is None

    def test_get_media_missing_url(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        res = Mock()
        res.raise_for_status = Mock()
        res.json = Mock(return_value={})
        client = _http_client(get_side_effect=[res])
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                WhatsAppAdapter(access_token="tok").get_media("m1")
            )
        assert result is None

    def test_get_media_download_error(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        res1 = Mock()
        res1.raise_for_status = Mock()
        res1.json = Mock(return_value={"url": "https://graph.media/file"})
        client = _http_client(get_side_effect=[res1, RuntimeError("download failed")])
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                WhatsAppAdapter(access_token="tok").get_media("m1")
            )
        assert result is None

    def test_get_media_success(self):
        from core.communication.adapters.whatsapp import WhatsAppAdapter
        res1 = Mock()
        res1.raise_for_status = Mock()
        res1.json = Mock(return_value={"url": "https://graph.media/file"})
        res2 = Mock()
        res2.raise_for_status = Mock()
        res2.content = b"audio-bytes"
        client = _http_client(get_side_effect=[res1, res2])
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(
                WhatsAppAdapter(access_token="tok").get_media("m1")
            )
        assert result == b"audio-bytes"
        assert res2.raise_for_status.called


# ===========================================================================
# core/communication/adapters/facebook.py
# ===========================================================================

class TestFacebookAdapter:
    def test_init(self):
        from core.communication.adapters.facebook import FacebookAdapter
        adapter = FacebookAdapter(page_access_token="tok")
        assert adapter.page_access_token == "tok"
        assert adapter.api_base == "https://graph.facebook.com/v19.0"

    def test_verify_request_always_true(self):
        from core.communication.adapters.facebook import FacebookAdapter
        assert FacebookAdapter().verify_request({}, "") is True

    def test_normalize_wrong_object(self):
        from core.communication.adapters.facebook import FacebookAdapter
        assert FacebookAdapter().normalize_payload({"object": "instagram"}) is None

    def test_normalize_exception_branch(self):
        """Regression-style: malformed sender (not a dict) must not crash."""
        from core.communication.adapters.facebook import FacebookAdapter
        payload = {"object": "page", "entry": [{"messaging": [{"sender": "not-a-dict"}]}]}
        assert FacebookAdapter().normalize_payload(payload) is None

    def test_normalize_missing_sender_or_text(self):
        from core.communication.adapters.facebook import FacebookAdapter
        payload = {"object": "page", "entry": [{"messaging": [{"sender": {"id": "U1"}, "message": {}}]}]}
        assert FacebookAdapter().normalize_payload(payload) is None
        payload2 = {"object": "page", "entry": [{"messaging": [{"message": {"text": "hi"}}]}]}
        assert FacebookAdapter().normalize_payload(payload2) is None

    def test_normalize_success(self):
        from core.communication.adapters.facebook import FacebookAdapter
        payload = {
            "object": "page",
            "entry": [{"messaging": [{
                "sender": {"id": "U1"},
                "recipient": {"id": "PAGE1"},
                "message": {"text": "hello"},
            }]}],
        }
        out = FacebookAdapter().normalize_payload(payload)
        assert out == {
            "source": "facebook",
            "source_id": "U1",
            "channel_id": "U1",
            "sender_id": "U1",
            "content": "hello",
        }

    def test_send_message_no_token(self):
        from core.communication.adapters.facebook import FacebookAdapter
        assert asyncio.run(FacebookAdapter().send_message("U1", "hi")) is False

    def test_send_message_success(self):
        from core.communication.adapters.facebook import FacebookAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(FacebookAdapter(page_access_token="tok").send_message("U1", "hi"))
        assert result is True
        call = client.post.await_args
        assert "access_token=tok" in call.args[0]
        assert call.kwargs["json"]["recipient"] == {"id": "U1"}

    def test_send_message_error(self):
        from core.communication.adapters.facebook import FacebookAdapter
        response = Mock()
        response.raise_for_status = Mock(side_effect=RuntimeError("fb down"))
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(FacebookAdapter(page_access_token="tok").send_message("U1", "hi"))
        assert result is False


# ===========================================================================
# core/communication/adapters/email.py
# ===========================================================================

class TestEmailAdapterImportBoto3:
    def test_import_boto3_success(self):
        from core.communication.adapters.email import _import_boto3
        boto3, client_error = _import_boto3()
        assert boto3 is not None
        assert client_error is not None

    def test_import_boto3_import_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "boto3", None)
        monkeypatch.setitem(sys.modules, "botocore", None)
        from core.communication.adapters.email import _import_boto3
        boto3, client_error = _import_boto3()
        assert boto3 is None
        assert client_error is Exception


class TestEmailAdapterInit:
    def test_init_defaults(self):
        from core.communication.adapters.email import EmailAdapter
        with patch("boto3.client", return_value=MagicMock()) as boto_client:
            adapter = EmailAdapter()
        assert adapter.region_name == "us-east-1"
        assert adapter.source_email == "support@atom.ai"
        assert adapter.ses_client is boto_client.return_value
        boto_client.assert_called_once_with("sesv2", region_name="us-east-1")

    def test_init_custom(self):
        from core.communication.adapters.email import EmailAdapter
        with patch("boto3.client", return_value=MagicMock()):
            adapter = EmailAdapter(region_name="us-west-2", source_email="ops@atom.ai")
        assert adapter.region_name == "us-west-2"
        assert adapter.source_email == "ops@atom.ai"

    def test_init_source_email_env(self, monkeypatch):
        monkeypatch.setenv("SES_SOURCE_EMAIL", "env@atom.ai")
        from core.communication.adapters.email import EmailAdapter
        with patch("boto3.client", return_value=MagicMock()):
            adapter = EmailAdapter()
        assert adapter.source_email == "env@atom.ai"

    def test_init_without_boto3(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "boto3", None)
        monkeypatch.setitem(sys.modules, "botocore", None)
        from core.communication.adapters.email import EmailAdapter
        adapter = EmailAdapter()
        assert adapter.ses_client is None
        assert adapter._client_error is Exception

    def test_init_boto3_client_failure_nullifies(self):
        from core.communication.adapters.email import EmailAdapter
        with patch("boto3.client", side_effect=RuntimeError("no creds")):
            with patch("logging.Logger.warning") as warn:
                adapter = EmailAdapter()
        assert adapter.ses_client is None
        assert warn.called

    def test_init_retains_created_ses_client(self):
        """Regression: the created boto3 sesv2 client must be retained
        (was unconditionally nulled at email.py:46, making SES sending
        always fail with 'SES Client not available')."""
        from core.communication.adapters.email import EmailAdapter
        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            adapter = EmailAdapter()
        assert adapter.ses_client is mock_client

    def test_verify_request_always_true(self):
        from core.communication.adapters.email import EmailAdapter
        assert EmailAdapter().verify_request({}, "") is True


class TestEmailAdapterNormalize:
    def setup_method(self):
        from core.communication.adapters.email import EmailAdapter
        with patch("boto3.client", return_value=MagicMock()):
            self.adapter = EmailAdapter()

    def _full_payload(self, **overrides):
        payload = {
            "notificationType": "Received",
            "mail": {
                "messageId": "msg-1",
                "source": "sender@example.com",
                "commonHeaders": {
                    "subject": "Help",
                    "from": ["Sender <sender@example.com>"],
                    "to": ["support@atom.ai"],
                },
            },
            "content": "Please help me",
        }
        payload.update(overrides)
        return payload

    def test_normalize_sns_wrapper(self):
        inner = self._full_payload()
        payload = {"Type": "Notification", "Message": json.dumps(inner)}
        out = self.adapter.normalize_payload(payload)
        assert out["sender_id"] == "sender@example.com"
        assert out["channel_id"] == "msg-1"
        assert out["content"] == "Please help me"
        assert out["metadata"]["subject"] == "Help"
        assert out["metadata"]["from_name"] == "Sender"

    def test_normalize_sns_bad_json(self):
        payload = {"Type": "Notification", "Message": "{not valid json"}
        assert self.adapter.normalize_payload(payload) is None

    def test_normalize_not_received(self):
        payload = {"notificationType": "Bounce", "mail": {}}
        assert self.adapter.normalize_payload(payload) is None

    def test_normalize_sender_from_mail_source(self):
        payload = self._full_payload()
        payload["mail"]["commonHeaders"] = {}
        out = self.adapter.normalize_payload(payload)
        assert out["sender_id"] == "sender@example.com"

    def test_normalize_content_from_body_field(self):
        payload = self._full_payload(content=None, body="body text")
        out = self.adapter.normalize_payload(payload)
        assert out["content"] == "body text"

    def test_normalize_content_from_subject(self):
        payload = self._full_payload(content=None, body=None)
        out = self.adapter.normalize_payload(payload)
        assert out["content"] == "Help"

    def test_normalize_no_sender(self):
        payload = {"notificationType": "Received", "mail": {"commonHeaders": {}}}
        assert self.adapter.normalize_payload(payload) is None

    def test_normalize_no_content(self):
        payload = {
            "notificationType": "Received",
            "mail": {"messageId": "m1", "source": "a@b.com", "commonHeaders": {}},
        }
        assert self.adapter.normalize_payload(payload) is None


class TestEmailAdapterSend:
    def setup_method(self):
        from core.communication.adapters.email import EmailAdapter
        with patch("boto3.client", return_value=MagicMock()):
            self.adapter = EmailAdapter(source_email="support@atom.ai")

    def test_send_non_email_target(self):
        assert asyncio.run(self.adapter.send_message("msg-1", "hi")) is False

    def test_send_no_ses_client(self):
        self.adapter.ses_client = None
        assert asyncio.run(self.adapter.send_message("user@example.com", "hi")) is False

    def test_send_success(self):
        self.adapter.ses_client = MagicMock()
        self.adapter.ses_client.send_email.return_value = {"MessageId": "m-42"}
        result = asyncio.run(self.adapter.send_message("user@example.com", "hi"))
        assert result is True
        call = self.adapter.ses_client.send_email.call_args
        assert call.kwargs["FromEmailAddress"] == "support@atom.ai"
        assert call.kwargs["Destination"] == {"ToAddresses": ["user@example.com"]}

    def test_send_client_error(self):
        from botocore.exceptions import ClientError
        self.adapter.ses_client = MagicMock()
        self.adapter.ses_client.send_email.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "denied"}}, "SendEmail"
        )
        assert asyncio.run(self.adapter.send_message("user@example.com", "hi")) is False

    def test_send_generic_exception(self):
        self.adapter.ses_client = MagicMock()
        self.adapter.ses_client.send_email.side_effect = RuntimeError("boom")
        assert asyncio.run(self.adapter.send_message("user@example.com", "hi")) is False


# ===========================================================================
# core/communication/adapters/intercom.py
# ===========================================================================

class TestIntercomAdapterVerify:
    def test_verify_no_secret(self):
        from core.communication.adapters.intercom import IntercomAdapter
        assert IntercomAdapter(access_token="tok").verify_request({}, "body") is True

    def test_verify_missing_header(self):
        from core.communication.adapters.intercom import IntercomAdapter
        adapter = IntercomAdapter(access_token="tok", client_secret="sec")
        assert adapter.verify_request({}, "body") is False

    def test_verify_invalid_format(self):
        from core.communication.adapters.intercom import IntercomAdapter
        adapter = IntercomAdapter(access_token="tok", client_secret="sec")
        assert adapter.verify_request({"x-hub-signature": "garbage-no-sep"}, "body") is False

    def test_verify_sha256_valid(self):
        from core.communication.adapters.intercom import IntercomAdapter
        adapter = IntercomAdapter(access_token="tok", client_secret="sec")
        sig = "sha256=" + hmac.new(b"sec", b"body", hashlib.sha256).hexdigest()
        assert adapter.verify_request({"x-hub-signature": sig}, "body") is True

    def test_verify_sha1_valid(self):
        from core.communication.adapters.intercom import IntercomAdapter
        adapter = IntercomAdapter(access_token="tok", client_secret="sec")
        sig = "sha1=" + hmac.new(b"sec", b"body", hashlib.sha1).hexdigest()
        assert adapter.verify_request({"x-hub-signature": sig}, "body") is True

    def test_verify_unsupported_algo(self):
        from core.communication.adapters.intercom import IntercomAdapter
        adapter = IntercomAdapter(access_token="tok", client_secret="sec")
        assert adapter.verify_request({"x-hub-signature": "md5=abc"}, "body") is False

    def test_verify_mismatch(self):
        from core.communication.adapters.intercom import IntercomAdapter
        adapter = IntercomAdapter(access_token="tok", client_secret="sec")
        bad = "sha256=" + "0" * 64
        assert adapter.verify_request({"x-hub-signature": bad}, "body") is False


class TestIntercomAdapterNormalize:
    def setup_method(self):
        from core.communication.adapters.intercom import IntercomAdapter
        self.adapter = IntercomAdapter(access_token="tok")

    def _payload(self):
        return {
            "topic": "conversation.user.created",
            "data": {"item": {
                "id": "c1",
                "user": {"id": "u1", "email": "a@b.com", "name": "A"},
                "conversation_message": {"body": "<p>Hello <b>there</b></p>"},
            }},
        }

    def test_normalize_unknown_topic(self):
        assert self.adapter.normalize_payload({"topic": "conversation.admin.assigned"}) is None
        assert self.adapter.normalize_payload({}) is None

    def test_normalize_missing_conversation_id(self):
        payload = self._payload()
        payload["data"]["item"]["id"] = None
        assert self.adapter.normalize_payload(payload) is None

    def test_normalize_missing_content(self):
        payload = self._payload()
        payload["data"]["item"]["conversation_message"] = {"body": ""}
        assert self.adapter.normalize_payload(payload) is None

    def test_normalize_user_email_fallback(self):
        payload = self._payload()
        payload["data"]["item"]["user"] = {"email": "b@c.com"}
        out = self.adapter.normalize_payload(payload)
        assert out["sender_id"] == "b@c.com"

    def test_normalize_success(self):
        out = self.adapter.normalize_payload(self._payload())
        assert out["source"] == "intercom"
        assert out["source_id"] == "c1"
        assert out["sender_id"] == "u1"
        assert out["content"] == "Hello there"
        assert out["metadata"]["topic"] == "conversation.user.created"
        assert out["metadata"]["email"] == "a@b.com"
        assert out["metadata"]["name"] == "A"


class TestIntercomAdapterSend:
    def test_send_success(self):
        from core.communication.adapters.intercom import IntercomAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(IntercomAdapter(access_token="tok").send_message("c1", "hi"))
        assert result is True
        call = client.post.await_args
        assert call.args[0] == "https://api.intercom.io/conversations/c1/reply"
        assert call.kwargs["headers"]["Authorization"] == "Bearer tok"
        assert call.kwargs["json"]["body"] == "hi"

    def test_send_error_with_response(self):
        import httpx
        from core.communication.adapters.intercom import IntercomAdapter
        resp = httpx.Response(401, text="unauthorized")
        err = Mock()
        err.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
            "401", request=httpx.Request("POST", "https://api.intercom.io"), response=resp))
        err.response = resp
        client = _http_client(post_result=err)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(IntercomAdapter(access_token="tok").send_message("c1", "hi"))
        assert result is False

    def test_send_error_without_response(self):
        from core.communication.adapters.intercom import IntercomAdapter
        err = Mock()
        err.raise_for_status = Mock(side_effect=RuntimeError("timeout"))
        err.response = None
        client = _http_client(post_result=err)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(IntercomAdapter(access_token="tok").send_message("c1", "hi"))
        assert result is False


# ===========================================================================
# core/communication/adapters/sms.py
# ===========================================================================

class TestSMSAdapter:
    def test_init(self):
        from core.communication.adapters.sms import SMSAdapter
        adapter = SMSAdapter(account_sid="sid", auth_token="tok", phone_number="+1500")
        assert adapter.account_sid == "sid"
        assert adapter.auth_token == "tok"
        assert adapter.phone_number == "+1500"
        assert adapter.api_base == "https://api.twilio.com/2010-04-01/Accounts/sid"

    def test_verify_request_always_true(self):
        from core.communication.adapters.sms import SMSAdapter
        assert SMSAdapter("sid", "tok", "+1500").verify_request({}, "") is True

    def test_normalize_missing_sender(self):
        from core.communication.adapters.sms import SMSAdapter
        assert SMSAdapter("sid", "tok", "+1500").normalize_payload({"Body": "hi"}) is None

    def test_normalize_missing_body(self):
        from core.communication.adapters.sms import SMSAdapter
        assert SMSAdapter("sid", "tok", "+1500").normalize_payload({"From": "+1000"}) is None
        assert SMSAdapter("sid", "tok", "+1500").normalize_payload({}) is None

    def test_normalize_success(self):
        from core.communication.adapters.sms import SMSAdapter
        payload = {
            "From": "+1000", "Body": "hello", "MessageSid": "SM1",
            "To": "+1500", "FromCity": "SF", "FromState": "CA",
        }
        out = SMSAdapter("sid", "tok", "+1500").normalize_payload(payload)
        assert out == {
            "source": "sms",
            "source_id": "SM1",
            "channel_id": "+1000",
            "sender_id": "+1000",
            "content": "hello",
            "metadata": {"to_number": "+1500", "city": "SF", "state": "CA"},
        }

    def test_send_success(self):
        from core.communication.adapters.sms import SMSAdapter
        response = Mock()
        response.is_error = False
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(SMSAdapter("sid", "tok", "+1500").send_message("+1000", "hi"))
        assert result is True
        call = client.post.await_args
        assert call.args[0] == "https://api.twilio.com/2010-04-01/Accounts/sid/Messages.json"
        assert call.kwargs["data"] == {"To": "+1000", "From": "+1500", "Body": "hi"}
        assert call.kwargs["auth"] == ("sid", "tok")

    def test_send_is_error(self):
        from core.communication.adapters.sms import SMSAdapter
        response = Mock()
        response.is_error = True
        response.text = "Error 21610"
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(SMSAdapter("sid", "tok", "+1500").send_message("+1000", "hi"))
        assert result is False

    def test_send_exception(self):
        from core.communication.adapters.sms import SMSAdapter
        client = _http_client(post_side_effect=RuntimeError("twilio down"))
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(SMSAdapter("sid", "tok", "+1500").send_message("+1000", "hi"))
        assert result is False


# ===========================================================================
# core/communication/adapters/discord.py
# ===========================================================================

class TestDiscordAdapterInit:
    def test_init_from_env(self, monkeypatch):
        monkeypatch.setenv("DISCORD_PUBLIC_KEY", "00" * 32)
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "bot-env")
        from core.communication.adapters.discord import DiscordAdapter
        adapter = DiscordAdapter()
        assert adapter.bot_token == "bot-env"
        assert adapter.public_key_hex == "00" * 32
        assert adapter.verify_key is not None

    def test_init_explicit(self):
        pub_hex, _ = _ed_keypair()
        from core.communication.adapters.discord import DiscordAdapter
        adapter = DiscordAdapter(bot_token="bot", public_key_hex=pub_hex)
        assert adapter.bot_token == "bot"
        assert adapter.verify_key is not None

    def test_init_invalid_key(self):
        from core.communication.adapters.discord import DiscordAdapter
        with patch("logging.Logger.error") as err:
            adapter = DiscordAdapter(bot_token="bot", public_key_hex="zz-not-hex")
        assert adapter.verify_key is None
        assert err.called

    def test_init_no_key(self):
        from core.communication.adapters.discord import DiscordAdapter
        adapter = DiscordAdapter(bot_token="bot")
        assert adapter.verify_key is None


class TestDiscordAdapterVerify:
    def test_no_key_dev_bypass(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("BYPASS_WEBHOOK_SIGNATURE", "true")
        from core.communication.adapters.discord import DiscordAdapter
        adapter = DiscordAdapter(bot_token="bot")
        with patch("logging.Logger.warning") as warn:
            assert asyncio.run(adapter.verify_request(_mock_request(), b"{}")) is True
        assert warn.called

    def test_no_key_prod_rejects(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("BYPASS_WEBHOOK_SIGNATURE", "true")
        from core.communication.adapters.discord import DiscordAdapter
        adapter = DiscordAdapter(bot_token="bot")
        assert asyncio.run(adapter.verify_request(_mock_request(), b"{}")) is False

    def test_missing_signature_or_timestamp(self):
        pub_hex, _ = _ed_keypair()
        from core.communication.adapters.discord import DiscordAdapter
        adapter = DiscordAdapter(bot_token="bot", public_key_hex=pub_hex)
        assert asyncio.run(adapter.verify_request(_mock_request(), b"{}")) is False
        req = _mock_request({"X-Signature-Ed25519": "ab"})
        assert asyncio.run(adapter.verify_request(req, b"{}")) is False

    def test_valid_signature(self):
        pub_hex, priv = _ed_keypair()
        from core.communication.adapters.discord import DiscordAdapter
        adapter = DiscordAdapter(bot_token="bot", public_key_hex=pub_hex)
        timestamp = "1234567890"
        body = b"hello"
        sig = priv.sign(timestamp.encode() + body).hex()
        req = _mock_request({
            "X-Signature-Ed25519": sig,
            "X-Signature-Timestamp": timestamp,
        })
        assert asyncio.run(adapter.verify_request(req, body)) is True

    def test_invalid_signature(self):
        pub_hex, _ = _ed_keypair()
        _, other_priv = _ed_keypair()
        from core.communication.adapters.discord import DiscordAdapter
        adapter = DiscordAdapter(bot_token="bot", public_key_hex=pub_hex)
        timestamp = "1234567890"
        body = b"hello"
        sig = other_priv.sign(timestamp.encode() + body).hex()
        req = _mock_request({
            "X-Signature-Ed25519": sig,
            "X-Signature-Timestamp": timestamp,
        })
        assert asyncio.run(adapter.verify_request(req, body)) is False

    def test_signature_value_error(self):
        pub_hex, _ = _ed_keypair()
        from core.communication.adapters.discord import DiscordAdapter
        adapter = DiscordAdapter(bot_token="bot", public_key_hex=pub_hex)
        req = _mock_request({
            "X-Signature-Ed25519": "zz-not-hex",
            "X-Signature-Timestamp": "123",
        })
        assert asyncio.run(adapter.verify_request(req, b"{}")) is False

    def test_signature_generic_exception(self):
        pub_hex, _ = _ed_keypair()
        from core.communication.adapters.discord import DiscordAdapter
        adapter = DiscordAdapter(bot_token="bot", public_key_hex=pub_hex)
        adapter.verify_key = MagicMock()
        adapter.verify_key.verify.side_effect = RuntimeError("crypto backend down")
        req = _mock_request({
            "X-Signature-Ed25519": "ab",
            "X-Signature-Timestamp": "123",
        })
        assert asyncio.run(adapter.verify_request(req, b"{}")) is False


class TestDiscordAdapterNormalize:
    def setup_method(self):
        from core.communication.adapters.discord import DiscordAdapter
        self.adapter = DiscordAdapter(bot_token="bot")

    def test_normalize_ping(self):
        out = self.adapter.normalize_payload({"type": 1})
        assert out == {"type": "challenge", "response": {"type": 1}}

    def test_normalize_command_with_options(self):
        payload = {
            "type": 2,
            "user": {"id": "U1", "username": "bob"},
            "channel_id": "C1",
            "data": {"name": "ask", "options": [{"name": "question", "value": "hi"}]},
        }
        out = self.adapter.normalize_payload(payload)
        assert out["sender_id"] == "U1"
        assert out["username"] == "bob"
        assert out["content"] == "hi"
        assert out["channel_id"] == "C1"
        assert out["source"] == "discord"
        assert out["is_interaction"] is False

    def test_normalize_command_without_options(self):
        payload = {"type": 2, "user": {"id": "U1"}, "data": {"name": "help"}}
        out = self.adapter.normalize_payload(payload)
        assert out["content"] == "help"

    def test_normalize_component(self):
        payload = {
            "type": 3,
            "user": {"id": "U1"},
            "channel_id": "C1",
            "data": {"custom_id": "approve_123"},
        }
        out = self.adapter.normalize_payload(payload)
        assert out["content"] == "APPROVE 123"
        assert out["is_interaction"] is True

    def test_normalize_component_without_custom_id(self):
        """Regression: a component interaction without custom_id must not
        crash (was AttributeError at discord.py:96)."""
        payload = {"type": 3, "user": {"id": "U1"}, "data": {}}
        out = self.adapter.normalize_payload(payload)
        assert out["content"] == ""

    def test_normalize_no_user_data(self):
        assert self.adapter.normalize_payload({"type": 2}) is None
        assert self.adapter.normalize_payload({"type": 3, "data": {}}) is None

    def test_normalize_guild_member_user(self):
        payload = {
            "type": 2,
            "member": {"user": {"id": "GUILD-U1", "username": "guild-user"}},
            "data": {"name": "ping"},
        }
        out = self.adapter.normalize_payload(payload)
        assert out["sender_id"] == "GUILD-U1"
        assert out["username"] == "guild-user"

    def test_normalize_unknown_type(self):
        assert self.adapter.normalize_payload({"type": 99}) is None


class TestDiscordAdapterSend:
    def test_send_no_token(self):
        from core.communication.adapters.discord import DiscordAdapter
        with patch("logging.Logger.error") as err:
            assert asyncio.run(DiscordAdapter().send_message("C1", "hi")) is False
        assert err.called

    def test_send_success_with_embeds(self):
        from core.communication.adapters.discord import DiscordAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(DiscordAdapter(bot_token="bot").send_message(
                "C1", "hi", embeds=[{"title": "t"}], components=[{"type": 1}]
            ))
        assert result is True
        call = client.post.await_args
        assert call.args[0] == "https://discord.com/api/v10/channels/C1/messages"
        assert call.kwargs["headers"]["Authorization"] == "Bot bot"
        assert call.kwargs["json"] == {
            "content": "hi", "embeds": [{"title": "t"}], "components": [{"type": 1}]
        }

    def test_send_error(self):
        from core.communication.adapters.discord import DiscordAdapter
        response = Mock()
        response.raise_for_status = Mock(side_effect=RuntimeError("discord down"))
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(DiscordAdapter(bot_token="bot").send_message("C1", "hi"))
        assert result is False

    def test_send_approval_no_token(self):
        from core.communication.adapters.discord import DiscordAdapter
        assert asyncio.run(DiscordAdapter().send_approval_request("C1", "a1", {}, "HIGH")) is False

    def test_send_approval_urgent(self):
        from core.communication.adapters.discord import DiscordAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(DiscordAdapter(bot_token="bot").send_approval_request(
                "C1", "a1", {"action_type": "refund", "reason": "dup"}, "URGENT"
            ))
        assert result is True
        payload = client.post.await_args.kwargs["json"]
        assert payload["embeds"][0]["color"] == 0xFF0000
        buttons = payload["components"][0]["components"]
        assert [b["custom_id"] for b in buttons] == ["approve_a1", "reject_a1"]

    def test_send_approval_non_urgent(self):
        from core.communication.adapters.discord import DiscordAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(DiscordAdapter(bot_token="bot").send_approval_request(
                "C1", "a1", {"action_type": "refund", "reason": "dup"}, "HIGH"
            ))
        assert result is True
        payload = client.post.await_args.kwargs["json"]
        assert payload["embeds"][0]["color"] == 0xFFFF00

    def test_send_direct_with_agent(self):
        from core.communication.adapters.discord import DiscordAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(DiscordAdapter(bot_token="bot").send_direct_message("C1", "hi", "Athena"))
        assert result is True
        assert client.post.await_args.kwargs["json"]["content"] == "**[Athena]** hi"

    def test_send_direct_without_agent(self):
        from core.communication.adapters.discord import DiscordAdapter
        response = Mock()
        response.raise_for_status = Mock()
        client = _http_client(post_result=response)
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(DiscordAdapter(bot_token="bot").send_direct_message("C1", "hi"))
        assert result is True
        assert client.post.await_args.kwargs["json"]["content"] == "hi"
