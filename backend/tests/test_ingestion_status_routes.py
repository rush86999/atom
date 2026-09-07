"""Tests for data-ingestion status surfaces and connection-truth fixes.

Pins the behavior that closed the "connected but nothing ingested" blind
spot:

- /api/integrations/{id}/ingestion-status merges real connection state
  with communication-memory ingestion progress (records, last ingest,
  stream state) and degrades gracefully when the pipeline is unavailable.
- POST /{id}/ingestion/start restarts the poller (404 unsupported,
  409 unconnected).
- get_integration_health is user-truthful: a configured registry entry
  WITHOUT an active token is "unhealthy" when a user context is present.
- The Microsoft token refresher registers from MICROSOFT_CLIENT_ID.
- outlook_service refresh writes BOTH the "outlook" and "microsoft" rows.
- The OAuth callback fails the connect (returns None) when the exchange
  produced no access_token and no token is stored.
"""

import asyncio
import importlib
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.integration_status_routes as status_routes
from api.integration_status_routes import (
    _INGESTION_APP_TYPES,
    _iso_or_none,
    get_current_tenant,
    get_current_user,
    router,
)
from core.database import get_db
from core.models import IntegrationToken, OAuthToken, TenantIntegration, UserConnection


class _StubQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


def _make_db(
    user_connections=(),
    tenant_integrations=(),
    integration_tokens=(),
):
    rows = {
        UserConnection: list(user_connections),
        TenantIntegration: list(tenant_integrations),
        IntegrationToken: list(integration_tokens),
        OAuthToken: [],
    }

    class _StubDB:
        def query(self, model):
            return _StubQuery(rows.get(model, []))

    return _StubDB()


def _make_client(db, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    app.dependency_overrides[get_current_tenant] = lambda: SimpleNamespace(id="t1")
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


class _StubPipeline:
    def __init__(self, stats=None, start_result=True):
        self._stats = stats if stats is not None else {
            "configured_apps": ["outlook"],
            "active_streams": ["outlook"],
            "total_messages": 2000,
            "app_stats": {
                "outlook": {
                    "total_messages": 2000,
                    "last_ingested": "2026-08-29T17:45:00+00:00",
                    "status": "active",
                },
            },
        }
        self._start_result = start_result
        self.start_calls = []
        self.legacy_start_calls = 0

    def get_ingestion_stats(self):
        return self._stats

    def start_outlook_poller(self):
        self.legacy_start_calls += 1
        return self._start_result

    def start_poller(self, app_type, polling_interval_seconds=60):
        self.start_calls.append(app_type)
        return self._start_result


def _patch_pipeline(monkeypatch, stub):
    monkeypatch.setattr(
        "integrations.atom_communication_ingestion_pipeline.ingestion_pipeline",
        stub,
    )
    # The route serves a background-refreshed snapshot and never scans
    # inline on the request path (a sync scan on a drive-hosted store can
    # block for minutes). Tests seed the cache directly and keep the
    # daemon refresher out so responses are deterministic.
    from api import integration_status_routes as _routes

    monkeypatch.setattr(_routes, "_STATS_CACHE", {
        "snapshot": None,
        "refreshing": False,
        "thread_alive": True,  # no background thread in tests
        "lock": threading.Lock(),
    })
    _routes._STATS_CACHE["snapshot"] = _routes._build_ingestion_snapshot()


# ---------------------------------------------------------------------------
# /ingestion-status (batch) and /{id}/ingestion-status
# ---------------------------------------------------------------------------


def test_batch_ingestion_status_keys_by_catalog_id(monkeypatch):
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/ingestion-status").json()
    assert body["available"] is True
    assert body["apps"]["outlook"]["records_ingested"] == 2000
    assert body["apps"]["outlook"]["stream_running"] is True
    assert body["apps"]["outlook"]["last_ingested"] == "2026-08-29T17:45:00+00:00"
    assert body["total_records_ingested"] == 2000


def test_batch_ingestion_status_includes_uncatalogued_app_types(monkeypatch):
    stats = {
        "configured_apps": ["crm_lead"],
        "active_streams": [],
        "total_messages": 7,
        "app_stats": {
            "crm_lead": {"total_messages": 7, "last_ingested": None, "status": "active"},
        },
    }
    _patch_pipeline(monkeypatch, _StubPipeline(stats=stats))
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/ingestion-status").json()
    assert body["apps"]["crm_lead"]["records_ingested"] == 7


def test_per_integration_status_merges_connection_and_ingestion(monkeypatch):
    token = SimpleNamespace(provider="outlook", status="active")
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(integration_tokens=[token]), monkeypatch)

    body = client.get("/api/integrations/outlook/ingestion-status").json()
    assert body["connected"] is True
    assert body["connection_source"] == "oauth_token"
    assert body["app_type"] == "outlook"
    assert body["stream_running"] is True
    assert body["records_ingested"] == 2000
    assert body["ingestion_status"] == "active"


def test_per_integration_status_not_connected(monkeypatch):
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/outlook/ingestion-status").json()
    assert body["connected"] is False
    assert body["connection_source"] == "none"
    # Ingestion facts still surface even when disconnected.
    assert body["records_ingested"] == 2000


def test_per_integration_status_known_app_type_without_data(monkeypatch):
    # gmail maps to an app_type, so stream/records fields must exist.
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/gmail/ingestion-status").json()
    assert body["app_type"] == "gmail"
    assert body["records_ingested"] == 0
    assert body["last_ingested"] is None


def test_microsoft_alias_marks_outlook_connected(monkeypatch):
    token = SimpleNamespace(provider="microsoft", status="active")
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(integration_tokens=[token]), monkeypatch)

    body = client.get("/api/integrations/outlook/ingestion-status").json()
    assert body["connected"] is True
    assert body["connection_source"] == "oauth_token"


def test_pipeline_unavailable_degrades_gracefully(monkeypatch):
    class _BrokenPipeline:
        def get_ingestion_stats(self):
            raise RuntimeError("lancedb down")

    _patch_pipeline(monkeypatch, _BrokenPipeline())
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/outlook/ingestion-status").json()
    assert body["ingestion_available"] is False
    assert body["records_ingested"] == 0
    assert body["stream_running"] is False


def test_pipeline_error_shape_degrades_gracefully(monkeypatch):
    _patch_pipeline(monkeypatch, _StubPipeline(stats={"error": "boom"}))
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/outlook/ingestion-status").json()
    assert body["ingestion_available"] is False


def test_app_type_map_covers_core_communications():
    for integration_id, app_type in (
        ("outlook", "outlook"),
        ("gmail", "gmail"),
        ("slack", "slack"),
        ("teams", "microsoft_teams"),
    ):
        assert _INGESTION_APP_TYPES[integration_id] == app_type


def test_batch_ingestion_status_zero_fills_all_mapped_integrations(monkeypatch):
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/ingestion-status").json()
    for integration_id in _INGESTION_APP_TYPES:
        entry = body["apps"][integration_id]
        assert "records_ingested" in entry, integration_id
        assert "last_synced" in entry, integration_id
    assert body["apps"]["outlook"]["records_ingested"] == 2000
    assert body["apps"]["gmail"]["records_ingested"] == 0


def test_per_integration_non_memory_integration_has_hybrid_fields(monkeypatch):
    # github: no memory app_type, but the payload must still expose the
    # hybrid sync fields so detail pages can render a coherent panel.
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/github/ingestion-status").json()
    assert body["app_type"] is None
    assert body["last_synced"] is None
    assert body["auto_sync_enabled"] is False


def test_hybrid_sync_state_merged_into_status(monkeypatch):
    from datetime import datetime

    class _StubHybridService:
        usage_stats = {
            "salesforce": SimpleNamespace(
                last_synced=datetime(2026, 8, 29, 12, 0, 0),
                auto_sync_enabled=True,
                sync_frequency_minutes=15,
            ),
        }

    monkeypatch.setattr(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        lambda workspace_id: _StubHybridService(),
    )
    monkeypatch.setattr(
        "core.personal_scope.resolve_workspace_id", lambda user: "default"
    )
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/salesforce/ingestion-status").json()
    assert body["last_synced"] == "2026-08-29T12:00:00"
    assert body["auto_sync_enabled"] is True
    assert body["sync_frequency_minutes"] == 15

    batch = client.get("/api/integrations/ingestion-status").json()
    assert batch["apps"]["salesforce"]["auto_sync_enabled"] is True
    assert batch["apps"]["salesforce"]["last_synced"] == "2026-08-29T12:00:00"


def test_iso_or_none_handles_pandas_shapes():
    assert _iso_or_none(None) is None
    assert _iso_or_none("NaT") is None
    assert _iso_or_none("none") is None
    from datetime import datetime

    assert (
        _iso_or_none(datetime(2026, 8, 29, 17, 45, 0))
        == "2026-08-29T17:45:00"
    )


# ---------------------------------------------------------------------------
# POST /{id}/ingestion/start
# ---------------------------------------------------------------------------


def test_start_unsupported_integration_returns_404(monkeypatch):
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    # github has no memory-pipeline poller implementation.
    assert client.post("/api/integrations/github/ingestion/start").status_code == 404


def test_start_pollable_integration_without_connection_returns_409(monkeypatch):
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    for integration_id in ("outlook", "gmail", "slack", "teams", "whatsapp", "discord"):
        response = client.post(f"/api/integrations/{integration_id}/ingestion/start")
        assert response.status_code == 409, integration_id


def test_start_outlook_starts_poller(monkeypatch):
    stub = _StubPipeline()
    _patch_pipeline(monkeypatch, stub)
    token = SimpleNamespace(provider="outlook", status="active")
    client = _make_client(_make_db(integration_tokens=[token]), monkeypatch)

    body = client.post("/api/integrations/outlook/ingestion/start").json()
    assert stub.start_calls == ["outlook"]
    assert body["stream_running"] is True
    assert body["start_attempted"] is True


def test_start_gmail_starts_generic_poller(monkeypatch):
    stub = _StubPipeline()
    _patch_pipeline(monkeypatch, stub)
    token = SimpleNamespace(provider="google", status="active")
    client = _make_client(_make_db(integration_tokens=[token]), monkeypatch)

    body = client.post("/api/integrations/gmail/ingestion/start").json()
    assert stub.start_calls == ["gmail"]
    assert body["stream_running"] is True


def test_start_zoho_workdrive_without_connection_returns_409(monkeypatch):
    # zoho-workdrive has a one-shot sync starter (not a poller): connected
    # callers get 200 + background full-sync, unconnected get 409 — never the
    # poller-style 404 that made the panel's "Start sync" button useless.
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    response = client.post("/api/integrations/zoho-workdrive/ingestion/start")
    assert response.status_code == 409


def test_start_zoho_workdrive_runs_full_sync_in_background(monkeypatch):
    _patch_pipeline(monkeypatch, _StubPipeline())
    token = SimpleNamespace(provider="zoho", status="active")
    client = _make_client(_make_db(integration_tokens=[token]), monkeypatch)

    calls = []

    async def _fake_full_sync(user_id):
        calls.append(user_id)
        return {"success": True, "files_ingested": 3}

    from api.zoho_workdrive_routes import zoho_service

    monkeypatch.setattr(zoho_service, "full_sync", _fake_full_sync)

    # TestClient runs background tasks before returning.
    response = client.post("/api/integrations/zoho-workdrive/ingestion/start")
    assert response.status_code == 200
    body = response.json()
    assert body["started"] is True
    assert body["mode"] == "background_sync"
    assert body["start_attempted"] is True
    assert calls == ["u1"]


def test_start_zoho_books_runs_suite_hybrid_sync(monkeypatch):
    """The whole Zoho suite's Start sync drives the same serialized 'zoho'
    hybrid sync (one grant covers Books/CRM/inventory/projects/workdrive)."""
    _patch_pipeline(monkeypatch, _StubPipeline())
    token = SimpleNamespace(provider="zoho", status="active")
    client = _make_client(_make_db(integration_tokens=[token]), monkeypatch)

    sync_calls = []

    class _FakeHybrid:
        async def sync_integration_data(self, integration_id, force=False, **kw):
            sync_calls.append((integration_id, force))
            return {"success": True, "records_synced": 10}

    monkeypatch.setattr(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        lambda workspace_id: _FakeHybrid(),
    )

    body = client.post("/api/integrations/zoho-books/ingestion/start").json()
    assert body["started"] is True
    assert body["mode"] == "background_sync"
    # force=True: a manual click must bypass the recently-synced guard.
    assert sync_calls == [("zoho", True)]


def test_status_uses_hybrid_records_when_pipeline_has_none(monkeypatch):
    """Document integrations ingest through the hybrid sync — when the
    communication pipeline has no stats for the app_type, the card must
    show the hybrid sync's cumulative record count instead of a permanent 0."""
    _patch_pipeline(monkeypatch, _StubPipeline())
    token = SimpleNamespace(provider="zoho", status="active")
    client = _make_client(_make_db(integration_tokens=[token]), monkeypatch)

    class _Stats:
        last_synced = None
        auto_sync_enabled = True
        sync_frequency_minutes = 60
        total_records_synced = 42

    class _FakeHybrid:
        usage_stats = {"zoho": _Stats()}

    monkeypatch.setattr(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        lambda workspace_id: _FakeHybrid(),
    )

    body = client.get("/api/integrations/zoho-books/ingestion-status").json()
    assert body["connected"] is True
    assert body["records_ingested"] == 42


# ---------------------------------------------------------------------------
# get_integration_health — user-scoped truth (no registry false positives)
# ---------------------------------------------------------------------------


class _HealthStubQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _HealthStubDB:
    def __init__(self, oauth_rows=(), integration_rows=()):
        self._rows = {
            OAuthToken: list(oauth_rows),
            IntegrationToken: list(integration_rows),
        }

    def query(self, model):
        return _HealthStubQuery(self._rows.get(model, []))


def test_health_without_token_is_unhealthy_for_user():
    from integration_health_endpoints import get_integration_health

    result = get_integration_health(
        "outlook", db=_HealthStubDB(), user=SimpleNamespace(id="u1")
    )
    assert result.status == "unhealthy"
    assert result.error_message == "No connected account"


def test_health_with_integration_token_is_healthy_for_user():
    from integration_health_endpoints import get_integration_health

    db = _HealthStubDB(integration_rows=[SimpleNamespace(provider="outlook")])
    result = get_integration_health("outlook", db=db, user=SimpleNamespace(id="u1"))
    assert result.status == "healthy"


def test_health_accepts_microsoft_row_for_outlook():
    from integration_health_endpoints import get_integration_health

    db = _HealthStubDB(integration_rows=[SimpleNamespace(provider="microsoft")])
    result = get_integration_health("outlook", db=db, user=SimpleNamespace(id="u1"))
    assert result.status == "healthy"


def test_health_anonymous_falls_back_to_registry():
    from integration_health_endpoints import get_integration_health

    # No db/user context: registry-configured integrations stay "healthy"
    # (dashboards probing /health anonymously keep working).
    result = get_integration_health("outlook")
    assert result.status == "healthy"
    assert result.error_message is None


# ---------------------------------------------------------------------------
# token refresher registration gate
# ---------------------------------------------------------------------------


def test_microsoft_refresher_registers_from_microsoft_client_id(monkeypatch):
    from core import token_refresher as mod

    monkeypatch.delenv("OUTLOOK_CLIENT_ID", raising=False)
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    importlib.reload(mod)
    assert "microsoft" in mod.token_refresher.refresh_handlers
    # Restore the module to its import-time configuration.
    monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
    importlib.reload(mod)


# ---------------------------------------------------------------------------
# outlook_service refresh writes both provider rows
# ---------------------------------------------------------------------------


class _RefreshSession:
    def __init__(self, records):
        self._records = records
        self.commits = 0

    def query(self, model):
        return _StubQuery(self._records)

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_refresh_updates_outlook_and_microsoft_rows(monkeypatch):
    from integrations import outlook_service as module

    rows = [
        SimpleNamespace(provider="outlook"),
        SimpleNamespace(provider="microsoft"),
    ]
    session = _RefreshSession(rows)

    class _FakeResponse:
        status = 200

        async def json(self):
            return {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            }

    class _FakePostCtx:
        async def __aenter__(self):
            return _FakeResponse()

        async def __aexit__(self, *args):
            return False

    class _FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return _FakePostCtx()

    monkeypatch.setattr(module.aiohttp, "ClientSession", _FakeSession)
    monkeypatch.setattr("core.database.get_db_session", lambda: session)
    monkeypatch.setattr(
        "core.privsec.token_encryption.encrypt_token", lambda value: f"enc:{value}"
    )

    service = module.outlook_service
    monkeypatch.setattr(service, "client_id", "cid", raising=False)
    monkeypatch.setattr(service, "client_secret", "csecret", raising=False)
    monkeypatch.setattr(service, "tenant_id_config", "common", raising=False)

    result = await service._refresh_access_token(
        "u1", {"refresh_token": "old-refresh"}
    )
    assert result == "new-access"
    assert session.commits == 1
    for row in rows:
        assert row.access_token == "enc:new-access"
        assert row.refresh_token == "enc:new-refresh"


# ---------------------------------------------------------------------------
# OAuth callback: no stored token + no access_token must fail the connect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_logic_fails_when_no_token_and_no_access_token(monkeypatch):
    from api import oauth_routes
    from core.oauth_handler import OAuthHandler

    db = _make_db()
    user = SimpleNamespace(id="u1")

    with patch.object(
        OAuthHandler, "exchange_code_for_tokens", new_callable=AsyncMock,
        return_value={},
    ):
        result = await oauth_routes._handle_callback_logic(
            "microsoft", "code", SimpleNamespace(), None, db, user
        )
    assert result is None


@pytest.mark.asyncio
async def test_callback_logic_treats_code_reuse_as_success(monkeypatch):
    from api import oauth_routes
    from core.oauth_handler import OAuthHandler

    existing = SimpleNamespace(provider="outlook", status="active")
    db = _make_db(integration_tokens=[existing])
    user = SimpleNamespace(id="u1")

    with patch.object(
        OAuthHandler, "exchange_code_for_tokens", new_callable=AsyncMock,
        return_value={},
    ):
        result = await oauth_routes._handle_callback_logic(
            "microsoft", "code", SimpleNamespace(), None, db, user
        )
    assert result == {}


# ---------------------------------------------------------------------------
# First-ingestion time guidance ("how long until my data shows up?")
# ---------------------------------------------------------------------------


def test_first_ingestion_pending_uses_static_catalog_range(monkeypatch):
    """Cold start (no sync ever ran): the static per-integration estimate."""
    _patch_pipeline(
        monkeypatch,
        _StubPipeline(stats={
            "configured_apps": ["gmail"],
            "active_streams": [],
            "total_messages": 0,
            "app_stats": {},
        }),
    )
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/gmail/ingestion-status").json()
    guidance = body["first_ingestion"]
    assert guidance["phase"] == "pending"
    assert guidance["measured"] is False
    assert guidance["range"] == [300, 1800]
    assert guidance["label"] == "~5–30 min"
    assert guidance["basis"]


def test_first_ingestion_complete_when_records_exist(monkeypatch):
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/outlook/ingestion-status").json()
    assert body["records_ingested"] == 2000
    assert body["first_ingestion"]["phase"] == "complete"


def test_first_ingestion_in_progress_while_sync_runs(monkeypatch):
    _patch_pipeline(
        monkeypatch,
        _StubPipeline(stats={
            "configured_apps": ["zoho"],
            "active_streams": [],
            "total_messages": 0,
            "app_stats": {},
        }),
    )

    class _FakeHybrid:
        usage_stats = {}
        _sync_locks = {"zoho": SimpleNamespace(locked=lambda: True)}
        _sync_started_at = {"zoho": "2026-09-02T13:00:00+00:00"}

    monkeypatch.setattr(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        lambda workspace_id: _FakeHybrid(),
    )
    client = _make_client(_make_db(integration_tokens=[SimpleNamespace(provider="zoho", status="active")]), monkeypatch)

    body = client.get("/api/integrations/zoho-books/ingestion-status").json()
    guidance = body["first_ingestion"]
    assert guidance["phase"] == "in_progress"
    assert guidance["range"] == [300, 900]


def test_first_ingestion_measured_average_beats_catalog(monkeypatch):
    """After one completed sync, this workspace's measured average replaces
    the static estimate."""
    _patch_pipeline(
        monkeypatch,
        _StubPipeline(stats={
            "configured_apps": ["hubspot"],
            "active_streams": [],
            "total_messages": 0,
            "app_stats": {},
        }),
    )

    class _Stats:
        last_synced = None
        auto_sync_enabled = True
        sync_frequency_minutes = 60
        total_records_synced = 0
        avg_sync_duration_seconds = 240.0

    class _FakeHybrid:
        usage_stats = {"hubspot": _Stats()}

    monkeypatch.setattr(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        lambda workspace_id: _FakeHybrid(),
    )
    client = _make_client(_make_db(), monkeypatch)

    body = client.get("/api/integrations/hubspot/ingestion-status").json()
    guidance = body["first_ingestion"]
    assert guidance["measured"] is True
    assert guidance["seconds"] == 240
    assert guidance["label"] == "~4 min"
    assert guidance["range"] is None
    assert guidance["phase"] == "pending"


def test_batch_first_ingestion_present_for_every_app(monkeypatch):
    """"For each integration": the batch payload carries guidance for every
    card, including zero-filled entries and unmapped pass-through types."""
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    apps = client.get("/api/integrations/ingestion-status").json()["apps"]
    assert apps, "batch payload must not be empty"
    for key, entry in apps.items():
        guidance = entry.get("first_ingestion")
        assert guidance, f"missing first_ingestion for {key}"
        assert guidance["phase"] in ("pending", "in_progress", "complete")
        assert guidance["label"].startswith("~")


# ---------------------------------------------------------------------------
# Storage-drive per-app cards + Start sync (google_drive / onedrive)
# ---------------------------------------------------------------------------


def test_drive_integrations_have_app_type_and_starter():
    """google_drive/onedrive key the per-app ingestion card: they must map
    to an app_type (so the card renders records) and have a Start-sync
    starter (so the card's button isn't a guaranteed 404)."""
    from api.integration_status_routes import (
        _INGESTION_APP_TYPES,
        _SYNC_STARTERS,
    )

    for integration_id in ("google_drive", "onedrive"):
        assert _INGESTION_APP_TYPES.get(integration_id) == integration_id
        assert integration_id in _SYNC_STARTERS


def test_start_google_drive_without_connection_returns_409(monkeypatch):
    _patch_pipeline(monkeypatch, _StubPipeline())
    client = _make_client(_make_db(), monkeypatch)

    response = client.post("/api/integrations/google_drive/ingestion/start")
    assert response.status_code == 409


def test_start_google_drive_runs_full_sync_in_background(monkeypatch):
    """A google OAuth grant lights the catalog id, and Start sync runs the
    one-shot tree walk in the request background, recording per-app
    ingestion feedback when it lands."""
    _patch_pipeline(monkeypatch, _StubPipeline())
    token = SimpleNamespace(provider="google", status="active")
    client = _make_client(_make_db(integration_tokens=[token]), monkeypatch)

    from integrations.google_drive_service import google_drive_service

    async def _fake_token(user_id):
        return "tok"

    async def _fake_full_sync(workspace_id, access_token):
        return {"success": True, "files_ingested": 4}

    monkeypatch.setattr(google_drive_service, "get_access_token", _fake_token)
    monkeypatch.setattr(google_drive_service, "full_sync", _fake_full_sync)

    recorded = []

    class _FakeHybrid:
        def record_sync_completion(self, integration_id, records, success):
            recorded.append((integration_id, records, success))

    monkeypatch.setattr(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        lambda workspace_id: _FakeHybrid(),
    )

    response = client.post("/api/integrations/google_drive/ingestion/start")
    assert response.status_code == 200
    body = response.json()
    assert body["started"] is True
    assert body["mode"] == "background_sync"
    assert recorded == [("google_drive", 4, True)]


def test_start_onedrive_runs_full_sync_in_background(monkeypatch):
    _patch_pipeline(monkeypatch, _StubPipeline())
    token = SimpleNamespace(provider="microsoft", status="active")
    client = _make_client(_make_db(integration_tokens=[token]), monkeypatch)

    from integrations.onedrive_service import onedrive_service

    async def _fake_token(user_id):
        return "tok"

    async def _fake_full_sync(workspace_id, access_token):
        return {"success": True, "files_ingested": 2}

    monkeypatch.setattr(onedrive_service, "get_access_token", _fake_token)
    monkeypatch.setattr(onedrive_service, "full_sync", _fake_full_sync)

    recorded = []

    class _FakeHybrid:
        def record_sync_completion(self, integration_id, records, success):
            recorded.append((integration_id, records, success))

    monkeypatch.setattr(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        lambda workspace_id: _FakeHybrid(),
    )

    response = client.post("/api/integrations/onedrive/ingestion/start")
    assert response.status_code == 200
    assert response.json()["started"] is True
    assert recorded == [("onedrive", 2, True)]


def test_drive_ingestion_status_payload_shows_app_grid(monkeypatch):
    """With a google_drive app_type, the card payload carries the memory
    grid fields and falls back to the recorded hybrid counts (the drives
    have no communication poller — recorded feedback IS the number)."""
    _patch_pipeline(monkeypatch, _StubPipeline())
    token = SimpleNamespace(provider="google", status="active")
    client = _make_client(_make_db(integration_tokens=[token]), monkeypatch)

    payload = client.get("/api/integrations/google_drive/ingestion-status").json()
    assert payload["app_type"] == "google_drive"
    assert payload["connected"] is True
    assert payload["ingestion_available"] is True


# ---------------------------------------------------------------------------
# serve-stale-while-refresh contract (Sep 6, 2026 incident)
# ---------------------------------------------------------------------------


def test_snapshot_returns_unavailable_without_inline_scan(monkeypatch):
    """Cold cache must NOT scan LanceDB on the request path: the endpoint
    answers instantly and the background refresher populates it. Regression
    for the Sep 6 incident — with the external drive reconnected mid-backlog,
    every ingestion-status poll blocked the event loop on a sync scan for
    60s+ and stalled /api/health too."""
    from api import integration_status_routes as _routes

    class _SlowPipeline:
        def get_ingestion_stats(self):
            raise RuntimeError("scan would block for minutes")

    monkeypatch.setattr(
        "integrations.atom_communication_ingestion_pipeline.ingestion_pipeline",
        _SlowPipeline(),
    )
    monkeypatch.setattr(_routes, "_STATS_CACHE", {
        "snapshot": None,
        "refreshing": False,
        "thread_alive": True,  # no background thread in tests
        "lock": threading.Lock(),
    })

    snap = _routes._ingestion_snapshot()

    assert snap["available"] is False
    assert _routes._STATS_CACHE["snapshot"] is None  # nothing scanned inline


def test_snapshot_serves_cached_value_without_touching_pipeline(monkeypatch):
    from api import integration_status_routes as _routes

    sentinel = {"available": True, "active_streams": [], "app_stats": {"x": {}}}

    class _MustNotBeCalled:
        def get_ingestion_stats(self):
            raise AssertionError("cache hit must not scan the pipeline")

    monkeypatch.setattr(
        "integrations.atom_communication_ingestion_pipeline.ingestion_pipeline",
        _MustNotBeCalled(),
    )
    monkeypatch.setattr(_routes, "_STATS_CACHE", {
        "snapshot": sentinel,
        "refreshing": False,
        "thread_alive": True,
        "lock": threading.Lock(),
    })

    assert _routes._ingestion_snapshot() is sentinel
