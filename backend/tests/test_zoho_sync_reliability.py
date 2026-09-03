"""Zoho suite ingestion reliability — the connect → sync → auto-sync chain.

Covers the four failure modes that degraded record ingestion:
1. tokens expiring unrefreshed (proactive refresh window, 401 retry, family
   fan-out),
2. suite syncs that never completed (bounded WorkDrive leg),
3. incremental cursors advancing over failed pulls (success-only advance),
4. the scheduler never seeing an integration whose first sync never
   completed (active-token seeding at service init).
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, IngestionSettings, IntegrationToken


@pytest.fixture()
def temp_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine, tables=[IngestionSettings.__table__, IntegrationToken.__table__]
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    import core.hybrid_data_ingestion as hdi
    monkeypatch.setattr(hdi, "SessionLocal", Session)
    monkeypatch.setenv("ATOM_INGESTION_PERSIST_STATE", "true")
    yield session
    session.close()


def _add_token(session, provider="zoho", status="active",
               expires_at=None, workspace_id="default", tenant_id="default",
               token_id=None):
    row = IntegrationToken(
        id=token_id or f"id-{provider}",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        provider=provider,
        access_token="enc-access",
        refresh_token="enc-refresh",
        status=status,
        expires_at=expires_at or (datetime.now(timezone.utc) + timedelta(hours=1)),
    )
    session.add(row)
    session.commit()
    return row


def make_service(**kwargs):
    graphrag = MagicMock()
    graphrag.ingest_document = AsyncMock(return_value={"entities": 1, "relationships": 1})
    with patch("core.lancedb_handler.get_lancedb_handler", return_value=MagicMock()), \
         patch("core.graphrag_engine.GraphRAGEngine", return_value=graphrag), \
         patch("core.llm_service.get_llm_service", return_value=MagicMock()):
        from core.hybrid_data_ingestion import HybridDataIngestionService
        return HybridDataIngestionService(
            workspace_id=kwargs.pop("workspace_id", "default"),
            tenant_id=kwargs.pop("tenant_id", "default"),
            **kwargs,
        )


def make_adapter():
    from core.integrations.adapters.zoho import ZohoAdapter
    return ZohoAdapter(db=None, workspace_id="default")


# ---------------------------------------------------------------------------
# Phase 3: active-token seeding
# ---------------------------------------------------------------------------

class TestTokenBackedSeeding:
    def test_active_token_seeds_scheduled_sync(self, temp_db):
        _add_token(temp_db, provider="zoho")
        svc = make_service()
        assert "zoho" in svc.usage_stats
        assert svc.usage_stats["zoho"].auto_sync_enabled is True
        assert svc.sync_configs["zoho"].entity_types[0] == "workdrive_files"
        # Persisted so status routes and restarts see the same state.
        row = temp_db.query(IngestionSettings).filter_by(integration_id="zoho").one()
        assert row.enabled is True

    def test_no_token_no_seed(self, temp_db):
        svc = make_service()
        assert "zoho" not in svc.usage_stats

    def test_existing_state_wins_over_seed(self, temp_db):
        _add_token(temp_db, provider="zoho")
        temp_db.add(IngestionSettings(
            workspace_id="default", integration_id="zoho",
            enabled=False,
            usage_stats_json={"auto_sync_enabled": False, "total_calls": 4},
        ))
        temp_db.commit()
        svc = make_service()
        assert svc.usage_stats["zoho"].auto_sync_enabled is False
        assert svc.usage_stats["zoho"].total_calls == 4


# ---------------------------------------------------------------------------
# Phase 2a: proactive refresh + 401 retry + family fan-out
# ---------------------------------------------------------------------------

class TestProactiveRefresh:
    def test_refreshes_inside_margin(self):
        adapter = make_adapter()
        adapter._access_token = "tok"
        adapter._refresh_token = "rt"
        adapter._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=120)
        adapter.refresh_token = AsyncMock(return_value=True)
        asyncio.run(adapter.ensure_token())
        adapter.refresh_token.assert_awaited_once()

    def test_skips_when_lifetime_comfortable(self):
        adapter = make_adapter()
        adapter._access_token = "tok"
        adapter._refresh_token = "rt"
        adapter._token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        adapter.refresh_token = AsyncMock(return_value=True)
        asyncio.run(adapter.ensure_token())
        adapter.refresh_token.assert_not_awaited()

    def test_missing_expiry_keeps_old_behaviour(self):
        adapter = make_adapter()
        adapter._access_token = "tok"
        adapter._token_expires_at = None
        adapter.refresh_token = AsyncMock(return_value=True)
        asyncio.run(adapter.ensure_token())
        adapter.refresh_token.assert_not_awaited()


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def get(self, url, headers=None, params=None):
        # Snapshot headers like a real HTTP client would at request time —
        # the retry mutates the caller's dict in place.
        self.calls.append({
            "url": url,
            "headers": dict(headers) if headers else None,
            "params": params,
        })
        return self.responses.pop(0)


class TestAuthedGetRetry:
    def test_401_forces_one_refresh_then_retries(self):
        adapter = make_adapter()
        adapter._access_token = "stale"
        adapter.refresh_token = AsyncMock(
            side_effect=lambda: setattr(adapter, "_access_token", "fresh") or True
        )
        client = FakeClient([
            FakeResponse(status_code=401),
            FakeResponse(payload={"data": [{"id": "1"}]}),
        ])
        data = asyncio.run(adapter._authed_get_json(client, "https://x/Leads"))
        assert data == {"data": [{"id": "1"}]}
        assert len(client.calls) == 2
        assert client.calls[0]["headers"]["Authorization"].endswith("stale")
        assert client.calls[1]["headers"]["Authorization"].endswith("fresh")
        assert adapter.refresh_token.await_count == 1

    def test_204_no_content_maps_to_empty(self):
        adapter = make_adapter()
        adapter._access_token = "tok"
        client = FakeClient([FakeResponse(status_code=204)])
        assert asyncio.run(adapter._authed_get_json(client, "https://x/Leads")) == {}

    def test_if_modified_since_header_sent(self):
        adapter = make_adapter()
        adapter._access_token = "tok"
        client = FakeClient([FakeResponse(payload={"data": []})])
        cursor = datetime(2026, 9, 2, 13, 4, 59, tzinfo=timezone.utc)
        asyncio.run(adapter._authed_get_json(
            client, "https://x/Leads", modified_since=cursor
        ))
        assert client.calls[0]["headers"]["If-Modified-Since"] == \
            "2026-09-02T13:04:59+00:00"


class TestRefreshFanOut:
    def test_refresh_updates_canonical_and_record_rows_not_workdrive(self, temp_db, monkeypatch):
        canonical = _add_token(temp_db, provider="zoho", token_id="id-zoho")
        crm = _add_token(temp_db, provider="zoho_crm", token_id="id-zoho_crm")
        books = _add_token(temp_db, provider="zoho_books", token_id="id-zoho_books")
        wd = _add_token(
            temp_db, provider="zoho_workdrive", token_id="id-zoho_workdrive",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        monkeypatch.setattr(
            "core.privsec.token_encryption.encrypt_token",
            lambda value, **kwargs: f"enc:{value}",
        )
        monkeypatch.setattr(
            "core.privsec.token_encryption.stamp_credential_metadata",
            lambda row: {},
        )

        class FakeTokenResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"access_token": "new-access", "expires_in": 3600}

        posted = {}

        class FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, data=None):
                posted.update(data or {})
                return FakeTokenResponse()

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: FakeAsyncClient())

        adapter = make_adapter()
        adapter.db = temp_db
        adapter._token_row_id = canonical.id
        adapter._refresh_token = "grant-refresh-token"
        adapter._access_token = "old-access"

        assert asyncio.run(adapter.refresh_token()) is True
        assert posted["refresh_token"] == "grant-refresh-token"

        for row in (canonical, crm, books):
            temp_db.refresh(row)
            assert row.access_token == "enc:new-access", row.provider
            assert row.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)
        temp_db.refresh(wd)
        assert wd.access_token == "enc-access"  # untouched


# ---------------------------------------------------------------------------
# Phase 4: Books/Inventory last_modified_time filter
# ---------------------------------------------------------------------------

class TestBooksPagination:
    def test_pages_and_cursor_param(self):
        adapter = make_adapter()
        adapter._access_token = "tok"
        page1 = FakeResponse(payload={
            "invoices": [{"id": f"i{i}"} for i in range(100)],
            "page_context": {"has_more_page": True},
        })
        page2 = FakeResponse(payload={
            "invoices": [{"id": f"j{i}"} for i in range(50)],
            "page_context": {"has_more_page": False},
        })
        client = FakeClient([page1, page2])
        cursor = datetime(2026, 9, 2, 13, 4, 59, tzinfo=timezone.utc)
        rows = asyncio.run(adapter._fetch_books_pages(
            client, "https://x/invoices", "org-1", 500, "invoices",
            modified_since=cursor,
        ))
        assert len(rows) == 150
        assert client.calls[0]["params"]["last_modified_time"] == "2026-09-02T13:04:59+0000"
        assert client.calls[1]["params"]["page"] == 2


# ---------------------------------------------------------------------------
# Phase 1 + 4 at the sync level: WorkDrive cap, cursor advance rules
# ---------------------------------------------------------------------------

class TestSuiteSyncCursorAndCaps:
    def _make_zoho_service(self, temp_db):
        from core.hybrid_data_ingestion import (
            DEFAULT_SYNC_CONFIGS,
            IntegrationUsageStats,
        )

        _add_token(temp_db, provider="zoho")
        svc = make_service()
        svc.sync_configs["zoho"] = DEFAULT_SYNC_CONFIGS["zoho"]
        svc.usage_stats["zoho"] = IntegrationUsageStats(
            integration_id="zoho", integration_name="zoho",
            workspace_id="default", auto_sync_enabled=True,
        )
        return svc

    async def _run_sync(self, svc, fetch):
        with patch.object(svc, "_fetch_integration_data", new=fetch):
            return await svc.sync_integration_data("zoho", force=True)

    def test_clean_sync_advances_cursor(self, temp_db):
        svc = self._make_zoho_service(temp_db)

        async def fetch(integration_id, config, discovery_mode=False, role=None):
            self.calls = getattr(self, "calls", 0) + 1
            svc._last_zoho_fetch_errors = []
            return [{"id": "1", "type": "lead"}]

        results = asyncio.run(self._run_sync(svc, fetch))
        assert results["success"] is True
        stats = svc.usage_stats["zoho"]
        assert stats.sync_cursors.get(svc._ZOHO_CURSOR_KEY) is not None
        row = temp_db.query(IngestionSettings).filter_by(integration_id="zoho").one()
        assert row.usage_stats_json["sync_cursors"].get(svc._ZOHO_CURSOR_KEY)

    def test_module_fetch_failure_keeps_cursor_and_marks_failed(self, temp_db):
        svc = self._make_zoho_service(temp_db)
        stats = svc.usage_stats["zoho"]
        stats.sync_cursors[svc._ZOHO_CURSOR_KEY] = "2026-09-01T00:00:00+00:00"

        async def fetch(integration_id, config, discovery_mode=False, role=None):
            svc._last_zoho_fetch_errors = ["books_invoices: RuntimeError: HTTP 401"]
            return [{"id": "1", "type": "lead"}]  # CRM succeeded, Books failed

        results = asyncio.run(self._run_sync(svc, fetch))
        assert results["success"] is False
        assert results["partial"] is True
        assert stats.last_synced is None  # retry soon
        assert stats.sync_cursors[svc._ZOHO_CURSOR_KEY] == "2026-09-01T00:00:00+00:00"

    def test_stale_cursor_reverts_to_full_pull(self, temp_db):
        svc = self._make_zoho_service(temp_db)
        stats = svc.usage_stats["zoho"]
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        stats.sync_cursors[svc._ZOHO_CURSOR_KEY] = old
        assert svc._zoho_incremental_cursor() is None

        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        stats.sync_cursors[svc._ZOHO_CURSOR_KEY] = recent.isoformat()
        parsed = svc._zoho_incremental_cursor()
        assert parsed is not None
        assert abs((parsed - recent).total_seconds()) < 5

    def test_workdrive_leg_bounded(self, temp_db, monkeypatch):
        """8 folders × 3000 files must not append more than the total record
        cap, and the content budget bounds downloads."""
        from core.hybrid_data_ingestion import SyncConfiguration

        svc = make_service()
        svc.sync_configs["zoho"] = SyncConfiguration(
            integration_id="zoho",
            entity_types=["workdrive_files"],
            sync_last_n_days=30,
            max_records_per_sync=10000,
        )
        _add_token(temp_db, provider="zoho", token_id="id-wd")
        temp_db.query(IntegrationToken).filter_by(provider="zoho").update(
            {"user_id": "user-1"}
        )
        temp_db.commit()

        import integrations.zoho_workdrive_service as wd_mod
        monkeypatch.setattr(
            wd_mod.zoho_workdrive_service,
            "get_team_folders",
            AsyncMock(return_value=[
                {"id": f"team-{i}", "name": f"F{i}", "team_id": f"tid-{i}"}
                for i in range(8)
            ]),
        )
        monkeypatch.setattr(
            wd_mod.zoho_workdrive_service,
            "list_files",
            AsyncMock(return_value=[
                {"id": f"f{i}", "name": f"doc{i}.txt", "extension": "txt", "size": 10}
                for i in range(3000)
            ]),
        )
        download = AsyncMock(return_value=b"x")
        monkeypatch.setattr(wd_mod.zoho_workdrive_service, "download_file", download)
        # Keep the content extraction fully fake — no real parsing/storage.
        import core.auto_document_ingestion as adi_mod
        fake_ingestor = MagicMock()
        fake_ingestor.process_file_bytes = AsyncMock()
        monkeypatch.setattr(
            adi_mod, "AutoDocumentIngestionService",
            MagicMock(return_value=fake_ingestor),
        )

        records = asyncio.run(
            svc._fetch_zoho_multi_app_data(svc.sync_configs["zoho"])
        )
        wd_records = [
            r for r in records if r["type"] in ("workdrive_file", "workdrive_folder")
        ]
        # 8 team folders + capped file/folder records (uncapped: 24008).
        assert len(wd_records) > svc._WD_SYNC_FILE_RECORD_CAP
        assert len(wd_records) <= svc._WD_SYNC_FILE_RECORD_CAP + 8
        assert download.await_count <= 25  # content budget

    def test_wd_record_cap_constant_matches_saas_budget(self):
        from core.hybrid_data_ingestion import HybridDataIngestionService as S
        assert S._WD_SYNC_FILE_RECORD_CAP == 2000
        assert S._ZOHO_FULL_REPULL_AFTER == timedelta(days=7)


# ---------------------------------------------------------------------------
# Phase 2c: TokenRefreshWorker
# ---------------------------------------------------------------------------

class TestTokenRefreshWorker:
    def _worker(self):
        from workers.token_refresh_worker import TokenRefreshWorker
        return TokenRefreshWorker(interval_seconds=300)

    def test_refreshes_when_rows_expiring(self, temp_db, monkeypatch):
        _add_token(
            temp_db, provider="zoho",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        _add_token(
            temp_db, provider="zoho_workdrive",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        monkeypatch.setattr("core.database.SessionLocal", sessionmaker(bind=temp_db.bind))

        calls = []

        class FakeAdapter:
            def __init__(self, db=None, workspace_id="default"):
                pass

            async def refresh_token(self):
                calls.append(1)
                return True

        import core.integrations.adapters.zoho as zoho_mod
        monkeypatch.setattr(zoho_mod, "ZohoAdapter", FakeAdapter)
        asyncio.run(self._worker().refresh_expiring_tokens())
        assert len(calls) == 1

    def test_noop_when_tokens_fresh(self, temp_db, monkeypatch):
        _add_token(
            temp_db, provider="zoho",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=55),
        )
        monkeypatch.setattr("core.database.SessionLocal", sessionmaker(bind=temp_db.bind))

        calls = []

        class FakeAdapter:
            async def refresh_token(self):
                calls.append(1)
                return True

        import core.integrations.adapters.zoho as zoho_mod
        monkeypatch.setattr(zoho_mod, "ZohoAdapter", FakeAdapter)
        asyncio.run(self._worker().refresh_expiring_tokens())
        assert calls == []
