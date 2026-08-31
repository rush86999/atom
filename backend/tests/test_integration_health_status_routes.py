"""Tests for the real integration status routes (connection-status + health-status).

The health dashboard must never report "healthy" from the legacy stubs
(integration_health_endpoints.py hardcodes configured=True for every
provider). These tests pin the real semantics:

- no connection/credential             -> status "not_connected"
- connected, credential not exercisable -> status "connected" (unverified)
- connected, live provider call fails   -> status "unreachable" (+ error)
- connected, live provider call works   -> status "healthy" (+ response time)
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.integration_status_routes import (
    _normalize_integration_id,
    _ping_provider,
    _token_from_credentials,
    get_current_tenant,
    get_current_user,
    router,
)
from core.database import get_db
from core.models import TenantIntegration, UserConnection


class _StubQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._rows)


def _make_db(user_connections=(), tenant_integrations=()):
    rows = {
        UserConnection: list(user_connections),
        TenantIntegration: list(tenant_integrations),
    }

    class _StubDB:
        def query(self, model):
            return _StubQuery(rows.get(model, []))

    return _StubDB()


def _make_client(db, monkeypatch, env=None, ping=None):
    for name in (
        "GITHUB_TOKEN",
        "GITHUB_ACCESS_TOKEN",
        "SLACK_BOT_TOKEN",
        "SLACK_TOKEN",
        "ZENDESK_API_TOKEN",
        "ZENDESK_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in (env or {}).items():
        monkeypatch.setenv(name, value)

    # Hermetic by default: ambient env creds (this machine exports a live
    # TELEGRAM_BOT_TOKEN) must never produce real provider calls in tests.
    monkeypatch.setattr(
        "api.integration_status_routes._ping_provider",
        ping or _dispatch_ping,
    )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    app.dependency_overrides[get_current_tenant] = lambda: SimpleNamespace(id="t1")
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


async def _dispatch_ping(provider_id, token):
    """Deterministic stand-in: tokens containing "bad" are rejected."""
    if "bad" in token:
        return False, 12, "HTTP 401"
    return True, 87, None


def _provider(body: dict, provider_id: str) -> dict:
    return body["providers"][provider_id]


def test_id_normalization():
    assert _normalize_integration_id("@activepieces/piece-slack") == "slack"
    assert _normalize_integration_id("GitHub") == "github"


def test_token_from_credentials_prefers_access_token():
    assert (
        _token_from_credentials({"refresh_token": "r", "access_token": "a"})
        == "a"
    )
    assert _token_from_credentials({"anything_key_like": "v"}) == "v"
    assert _token_from_credentials("not-a-dict") is None


@pytest.mark.asyncio
async def test_ping_provider_reports_http_failure(monkeypatch):
    class _FakeResponse:
        status_code = 401

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr(
        "api.integration_status_routes.httpx.AsyncClient", _FakeClient
    )
    reachable, elapsed_ms, error = await _ping_provider("github", "bad-token")
    assert reachable is False
    assert error == "HTTP 401"
    assert isinstance(elapsed_ms, int)


def test_env_credential_verified_healthy(monkeypatch):
    client = _make_client(
        _make_db(), monkeypatch, env={"GITHUB_TOKEN": "env-gh-token"}
    )

    github = _provider(client.get("/api/integrations/health-status").json(), "github")
    assert github["connected"] is True
    assert github["source"] == "env"
    assert github["status"] == "healthy"
    assert github["verified"] is True
    assert github["response_time_ms"] == 87


def test_env_credential_unreachable_on_provider_rejection(monkeypatch):
    client = _make_client(
        _make_db(), monkeypatch, env={"GITHUB_TOKEN": "bad-gh-token"}
    )

    github = _provider(client.get("/api/integrations/health-status").json(), "github")
    assert github["status"] == "unreachable"
    assert github["error"] == "HTTP 401"


def test_connected_without_pingable_credential_is_unverified(monkeypatch):
    # Zendesk is connected via env credential but has no one-call ping spec
    # (needs a subdomain): honest "connected", never the stubs' "healthy".
    client = _make_client(
        _make_db(), monkeypatch, env={"ZENDESK_API_TOKEN": "zd-token"}
    )

    zendesk = _provider(client.get("/api/integrations/health-status").json(), "zendesk")
    assert zendesk["connected"] is True
    assert zendesk["source"] == "env"
    assert zendesk["status"] == "connected"
    assert zendesk["verified"] is False


def test_no_connection_means_not_connected(monkeypatch):
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/health-status").json()
    for provider_id in ("github", "slack", "salesforce", "notion"):
        entry = _provider(body, provider_id)
        assert entry["connected"] is False
        assert entry["status"] == "not_connected"


def test_user_connection_row_drives_status_and_token(monkeypatch):
    connection = SimpleNamespace(
        integration_id="@activepieces/piece-slack",
        credentials={"access_token": "xoxb-stored"},
    )
    client = _make_client(_make_db(user_connections=[connection]), monkeypatch)

    slack = _provider(client.get("/api/integrations/health-status").json(), "slack")
    assert slack["connected"] is True
    assert slack["source"] == "user_connection"
    assert slack["status"] == "healthy"


def test_tenant_integration_without_token_is_unverified(monkeypatch):
    connector = SimpleNamespace(connector_id="notion", integration_id=None)
    client = _make_client(_make_db(tenant_integrations=[connector]), monkeypatch)

    notion = _provider(client.get("/api/integrations/health-status").json(), "notion")
    assert notion["connected"] is True
    assert notion["source"] == "tenant_integration"
    assert notion["status"] == "connected"


def test_catalog_is_complete_and_named(monkeypatch):
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/health-status").json()
    assert body["providers"]["github"]["name"] == "GitHub"
    assert body["providers"]["gmail"]["name"] == "Gmail"
    assert body["providers"]["zoho-workdrive"]["name"] == "Zoho WorkDrive"
    assert body["checked_at"]
