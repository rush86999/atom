"""OneDrive refresh classification controls.

The shared resolver must distinguish ordinary expiry, revoked consent,
client-configuration rejection and transient provider failure. These tests
exercise the provider callback with a fake transport; no real token is used.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

import integrations.onedrive_service as onedrive_module
from core.integrations.token_store import TokenRefreshError
from integrations.onedrive_service import OneDriveService


class FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.response


def _refresh_with(monkeypatch, *, response=None, error=None):
    service = OneDriveService()
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(
        onedrive_module.httpx, "AsyncClient",
        lambda **kwargs: FakeClient(response=response, error=error),
    )
    return asyncio.run(service._refresh("plain-refresh-token"))


def test_successful_refresh_returns_provider_payload(monkeypatch):
    payload = {
        "access_token": "new-access",
        "refresh_token": "new-refresh",
        "expires_in": 3600,
    }
    assert _refresh_with(
        monkeypatch, response=FakeResponse(200, payload)
    ) == payload


def test_invalid_grant_is_revoked_consent(monkeypatch):
    with pytest.raises(TokenRefreshError) as exc:
        _refresh_with(
            monkeypatch,
            response=FakeResponse(400, {"error": "invalid_grant"}),
        )
    assert exc.value.kind == "invalid_grant"
    assert "consent" in exc.value.detail


def test_invalid_client_is_configuration(monkeypatch):
    with pytest.raises(TokenRefreshError) as exc:
        _refresh_with(
            monkeypatch,
            response=FakeResponse(401, {"error": "invalid_client"}),
        )
    assert exc.value.kind == "invalid_client"
    assert "configuration" in exc.value.detail


def test_provider_5xx_is_transient(monkeypatch):
    with pytest.raises(TokenRefreshError) as exc:
        _refresh_with(monkeypatch, response=FakeResponse(503, {}))
    assert exc.value.kind == "transient"


def test_provider_429_is_transient(monkeypatch):
    with pytest.raises(TokenRefreshError) as exc:
        _refresh_with(monkeypatch, response=FakeResponse(429, {}))
    assert exc.value.kind == "transient"


def test_other_provider_rejection_is_not_revoked(monkeypatch):
    with pytest.raises(TokenRefreshError) as exc:
        _refresh_with(
            monkeypatch,
            response=FakeResponse(400, {"error": "invalid_scope"}),
        )
    assert exc.value.kind == "refresh_rejected"
    assert "invalid_scope" in exc.value.detail


def test_network_failure_is_transient(monkeypatch):
    error = httpx.ConnectError(
        "connection refused", request=httpx.Request("POST", "https://example.invalid")
    )
    with pytest.raises(TokenRefreshError) as exc:
        _refresh_with(monkeypatch, error=error)
    assert exc.value.kind == "transient"


def test_missing_refresh_token_never_calls_provider(monkeypatch):
    service = OneDriveService()
    with pytest.raises(TokenRefreshError) as exc:
        asyncio.run(service._refresh(None))
    assert exc.value.kind == "refresh_unavailable"


def test_missing_client_credentials_are_configuration_not_revoked(monkeypatch):
    service = OneDriveService()
    monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
    monkeypatch.delenv("MICROSOFT_CLIENT_SECRET", raising=False)
    with pytest.raises(TokenRefreshError) as exc:
        asyncio.run(service._refresh("plain-refresh-token"))
    assert exc.value.kind == "invalid_client"
    assert "credentials are not configured" in exc.value.detail


def test_classification_details_never_echo_tokens(monkeypatch):
    with pytest.raises(TokenRefreshError) as exc:
        _refresh_with(
            monkeypatch,
            response=FakeResponse(
                400,
                {"error": "invalid_grant"},
                text="refresh_token=plain-refresh-token",
            ),
        )
    assert "plain-refresh-token" not in str(exc.value)


def _resolution(monkeypatch, state, token=None):
    async def fake_resolve(user_id, providers, refresh, *, status_out=None):
        status_out.update({
            "state": state,
            "token_available": bool(token),
            "requires_reconnect": state in {"invalid_grant", "refresh_unavailable"},
            "retryable": state == "transient",
        })
        return token

    monkeypatch.setattr(onedrive_module, "resolve_integration_token", fake_resolve)


def test_revoked_grant_does_not_fall_through_to_legacy(monkeypatch):
    _resolution(monkeypatch, "invalid_grant")
    legacy_calls = []
    monkeypatch.setattr(
        onedrive_module.connection_service, "get_connections",
        lambda *a, **k: legacy_calls.append(a) or [],
    )
    token, status = asyncio.run(
        OneDriveService().get_access_token_resolution("u1"))
    assert token is None
    assert status["state"] == "invalid_grant"
    assert legacy_calls == []


def test_invalid_client_does_not_fall_through_to_legacy(monkeypatch):
    _resolution(monkeypatch, "invalid_client")
    legacy_calls = []
    monkeypatch.setattr(
        onedrive_module.connection_service, "get_connections",
        lambda *a, **k: legacy_calls.append(a) or [],
    )
    token, status = asyncio.run(
        OneDriveService().get_access_token_resolution("u1"))
    assert token is None
    assert status["state"] == "invalid_client"
    assert legacy_calls == []


def test_no_integration_grant_may_use_legacy_connection(monkeypatch):
    _resolution(monkeypatch, "no_grant")
    monkeypatch.setattr(
        onedrive_module.connection_service, "get_connections",
        lambda *a, **k: [{"id": "legacy-1"}],
    )
    monkeypatch.setattr(
        onedrive_module.connection_service, "get_connection_credentials",
        AsyncMock(return_value={"access_token": "legacy-token"}),
    )
    token, status = asyncio.run(
        OneDriveService().get_access_token_resolution("u1"))
    assert token == "legacy-token"
    assert status["state"] == "legacy"
    assert status["legacy_connection"] is True
