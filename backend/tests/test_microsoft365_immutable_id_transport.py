import asyncio

import aiohttp
import pytest

from integrations.microsoft365_service import Microsoft365Service


class _JsonResponse:
    def __init__(self, body, status=200):
        self.status = status
        self._body = body
        self.headers = {"Content-Type": "application/json"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self):
        return self._body

    async def text(self):
        return ""

    async def read(self):
        return b""


def _install_transport(monkeypatch, response):
    calls = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            if isinstance(response, BaseException):
                raise response
            return response

    monkeypatch.setattr(aiohttp, "ClientSession", lambda *args, **kwargs: Session())
    return calls


def _forbid_transport(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("transport must not be created")

    monkeypatch.setattr(aiohttp, "ClientSession", forbidden)


def test_default_graph_request_keeps_legacy_headers_and_payload(monkeypatch, caplog):
    token = "synthetic-token-default"
    payload = {"resource": "/me/messages"}
    calls = _install_transport(monkeypatch, _JsonResponse({"ok": True}))
    service = Microsoft365Service(config={})
    url = service.base_url + "/me/messages"
    result = asyncio.run(service._make_graph_request("GET", url, token, payload))
    assert result == {"status": "success", "data": {"ok": True}}
    assert len(calls) == 1
    method, emitted_url, kwargs = calls[0]
    assert method == "GET"
    assert emitted_url == url
    assert kwargs["headers"] == {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    assert kwargs["json"] is payload
    assert token not in caplog.text


def test_immutable_graph_request_adds_only_static_prefer(monkeypatch, caplog):
    token = "synthetic-token-immutable"
    payload = {"resource": "/me/messages"}
    calls = _install_transport(monkeypatch, _JsonResponse({"ok": True}))
    service = Microsoft365Service(config={})
    url = service.base_url + "/me/messages"
    result = asyncio.run(service._make_graph_request(
        "GET", url, token, payload, prefer_immutable_id=True
    ))
    assert result == {"status": "success", "data": {"ok": True}}
    _, emitted_url, kwargs = calls[0]
    assert emitted_url == url
    assert kwargs["headers"] == {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": 'IdType="ImmutableId"',
    }
    assert kwargs["json"] is payload
    assert "ImmutableId" not in caplog.text


@pytest.mark.parametrize("value", [1, 0, "true", None])
def test_invalid_prefer_flag_fails_before_transport(monkeypatch, value):
    _forbid_transport(monkeypatch)
    service = Microsoft365Service(config={})
    with pytest.raises(ValueError, match="^prefer_immutable_id must be a bool$"):
        asyncio.run(service._make_graph_request(
            "POST", service.base_url + "/subscriptions", "synthetic-token", {},
            prefer_immutable_id=value,
        ))


@pytest.mark.parametrize("value", [1, 0, "false", None])
def test_create_subscription_invalid_immutable_flag_fails_before_transport(monkeypatch, caplog, value):
    token = "synthetic-token-invalid-flag"
    _forbid_transport(monkeypatch)
    service = Microsoft365Service(config={})
    result = asyncio.run(service.create_subscription(
        token, "/me/messages", "updated", "https://example.invalid/callback",
        "2026-11-25T00:00:00Z", immutable_ids=value,
    ))
    assert result == {"status": "error", "message": "Invalid subscription immutable IDs flag"}
    assert token not in str(result)
    assert token not in caplog.text


def test_create_subscription_forwards_immutable_prefer(monkeypatch):
    token = "synthetic-token-create-immutable"
    calls = _install_transport(monkeypatch, _JsonResponse({"id": "subscription"}))
    service = Microsoft365Service(config={})
    result = asyncio.run(service.create_subscription(
        token, "/me/messages", "updated", "https://example.invalid/callback",
        "2026-11-25T00:00:00Z", immutable_ids=True,
    ))
    assert result == {"status": "success", "data": {"id": "subscription"}}
    method, url, kwargs = calls[0]
    assert method == "POST"
    assert url == service.base_url + "/subscriptions"
    assert kwargs["headers"]["Prefer"] == 'IdType="ImmutableId"'
    assert kwargs["json"] == {
        "changeType": "updated",
        "notificationUrl": "https://example.invalid/callback",
        "resource": "/me/messages",
        "expirationDateTime": "2026-11-25T00:00:00Z",
        "clientState": "secretClientState",
    }


def test_legacy_create_subscription_emits_no_immutable_option(monkeypatch):
    token = "synthetic-token-create-legacy"
    calls = _install_transport(monkeypatch, _JsonResponse({"id": "subscription"}))
    service = Microsoft365Service(config={})
    result = asyncio.run(service.create_subscription(
        token, "/me/messages", "updated", "https://example.invalid/callback",
        "2026-11-25T00:00:00Z",
    ))
    assert result == {"status": "success", "data": {"id": "subscription"}}
    _, _, kwargs = calls[0]
    assert kwargs["headers"] == {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    assert kwargs["json"] == {
        "changeType": "updated",
        "notificationUrl": "https://example.invalid/callback",
        "resource": "/me/messages",
        "expirationDateTime": "2026-11-25T00:00:00Z",
        "clientState": "secretClientState",
    }


def test_transport_exception_does_not_leak_token_or_raw_exception(monkeypatch, caplog):
    token = "synthetic-token-private"
    private = "raw-transport-secret"
    _install_transport(monkeypatch, RuntimeError(private))
    service = Microsoft365Service(config={})
    result = asyncio.run(service.create_subscription(
        token, "/me/messages", "updated", "https://example.invalid/callback",
        "2026-11-25T00:00:00Z",
    ))
    assert result == {"status": "error", "message": "Create subscription failed"}
    assert token not in str(result)
    assert private not in str(result)
    assert token not in caplog.text
    assert private not in caplog.text
    assert "RuntimeError" in caplog.text


def test_development_mock_log_preserves_path_without_opaque_cursor(monkeypatch, caplog):
    import logging
    monkeypatch.setenv('ATOM_ENV', 'development')
    _forbid_transport(monkeypatch)
    caplog.set_level(logging.INFO, logger='integrations.microsoft365_service')
    path='/users/u/mailFolders/f/messages/delta'
    response=asyncio.run(Microsoft365Service(config={})._make_graph_request(
        'GET','https://graph.microsoft.com/v1.0'+path+'?$deltatoken=private-opaque-state',
        'fake_token',prefer_immutable_id=True))
    assert response['status'] == 'success'
    assert path in caplog.text
    assert 'private-opaque-state' not in caplog.text
