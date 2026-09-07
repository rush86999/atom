"""Integration test: the read leg's dataset fast path (universal_integration_service).

Drives the REAL `_read_storage_file` seam with a WorkDrive-shaped fake
storage service and real .xlsx bytes:

  fresh copy present   → answers via NL→SQL over Parquet, ZERO downloads;
  source moved on      → falls through to the ordinary download+excerpt path,
                         and the fresh copy materializes IN THE READ LEG
                         (regression: materialization must not depend on the
                         ingest service, which can fail fast in production).

Ingestion and formula-memory side effects are stubbed so the test is
hermetic (never touches the dev LanceDB/memory stores).

Run: cd backend && python -m pytest tests/unit/test_read_storage_dataset_fastpath.py -q
"""
import asyncio
import datetime as _dt
import io
import logging

import pandas as pd
import pytest

from core.database import Base, engine

_LOG_RECORDS: list = []


class _FakeLLM:
    async def generate_structured_response(self, prompt, response_model, **kwargs):
        return response_model(
            dataset_name="zoho_workdrive_consolidated_price_list_2019__machine_pricing",
            sql='SELECT "Item Number", Price, __sheet_row FROM df '
                "WHERE \"Item Number\" = 'WG-350DSAV'",
            note="",
        )


class _FakeWorkDrive:
    def __init__(self, content: bytes, modified_at: str):
        self._content = content
        self._modified_at = modified_at
        self.downloads = 0

    async def search_files(self, user_id, query, limit=20):
        return [{
            "id": "file-123",
            "name": "Consolidated Price List 2019.xlsx",
            "extension": "xlsx",
            "modified_at": self._modified_at,
        }]

    async def download_file(self, user_id, file_id):
        self.downloads += 1
        return self._content


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    import core.models  # noqa: F401
    from core.database import SessionLocal
    from core.models import DatasetEntry

    Base.metadata.create_all(bind=engine)
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path))

    # Hermetic: the fall-through scenario's best-effort ingest and the
    # parser's formula extractor must not touch dev memory stores.
    class _NoIngest:
        def __init__(self, *a, **k):
            pass

        async def process_file_bytes(self, *a, **k):
            return {"status": "skipped", "reason": "test"}

    class _NoFormulas:
        def extract_from_excel(self, path, auto_store=False):
            return []

    monkeypatch.setattr(
        "core.auto_document_ingestion.AutoDocumentIngestionService", _NoIngest
    )

    import core.formula_extractor as fe

    monkeypatch.setattr(fe, "get_formula_extractor", lambda ws=None: _NoFormulas())

    # Capture the dataset service's own log lines (outcome observability).
    handler = logging.Handler()
    handler.emit = lambda record: _LOG_RECORDS.append(record.getMessage())
    svc_logger = logging.getLogger("core.sheet_dataset_service")
    svc_logger.addHandler(handler)
    yield
    svc_logger.removeHandler(handler)
    _LOG_RECORDS.clear()
    with SessionLocal() as db:
        db.query(DatasetEntry).delete()
        db.commit()


def _workbook_bytes(price=14145.0) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame({
        "Item Number": ["WG-350DSAV", "LINMAC-2"],
        "Price": [price, 9800.0],
    }).to_excel(buf, sheet_name="Machine Pricing", index=False)
    return buf.getvalue()


def _seed(modified_at: _dt.datetime):
    from core.sheet_dataset_service import materialize_sheet_bytes_sync

    result = materialize_sheet_bytes_sync(
        _workbook_bytes(),
        file_name="Consolidated Price List 2019.xlsx",
        source="zoho_workdrive",
        user_id="u1",
        workspace_id="default",
        external_id="file-123",
        source_modified_at=modified_at,
    )
    assert result["status"] == "materialized"


def _read(fake_storage):
    """Drive the real read leg, then drain the fire-and-forget materialization
    task on the SAME running loop (asyncio.run would otherwise cancel it)."""

    async def _flow():
        from integrations.universal_integration_service import UniversalIntegrationService

        svc = UniversalIntegrationService(workspace_id="default")
        result = await svc._read_storage_file(
            "zoho_workdrive",
            fake_storage,
            None,
            {"query": "price of WG-350DSAV"},
            {"user_id": "u1", "llm_service": _FakeLLM()},
        )
        from core.sheet_dataset_service import _BACKGROUND_TASKS

        if _BACKGROUND_TASKS:
            await asyncio.gather(*list(_BACKGROUND_TASKS))
        return result

    return asyncio.run(_flow())


def test_fresh_copy_answers_via_sql_without_download():
    _seed(_dt.datetime(2026, 9, 1, tzinfo=_dt.timezone.utc))
    fake = _FakeWorkDrive(_workbook_bytes(), modified_at="2026-09-01T00:00:00Z")

    result = _read(fake)

    assert result["status"] == "success"
    data = result["data"]
    assert data["dataset"]["name"].endswith("__machine_pricing")
    # Excerpt holds the SQL rows in the citable R# convention.
    assert "R2" in data["excerpt"] and "14145" in data["excerpt"]
    assert fake.downloads == 0  # the whole point: no 13MB round trip


def test_ttl_fresh_copy_answers_even_when_hint_stale():
    """Pre-resolution contract: the catalog is consulted BEFORE the drive, so
    a TTL-fresh copy answers even when the connector's mtime moved on. The
    copy self-heals at TTL expiry (hint-equality + download refresh)."""
    _seed(_dt.datetime(2026, 9, 1, tzinfo=_dt.timezone.utc))
    fake = _FakeWorkDrive(_workbook_bytes(price=15145.0), modified_at="2026-09-06T00:00:00Z")

    result = _read(fake)

    assert result["status"] == "success"
    data = result["data"]
    assert "dataset" in data  # answered from the copy
    assert "14145" in data["excerpt"]
    assert fake.downloads == 0


def test_expired_ttl_and_stale_hint_falls_through_to_download():
    """Double-stale: TTL expired AND the source mtime moved on → the copy may
    NOT answer; the live file is opened and its excerpt quoted."""
    _seed(_dt.datetime(2026, 9, 1, tzinfo=_dt.timezone.utc))
    from core.database import SessionLocal
    from core.models import DatasetEntry

    with SessionLocal() as db:
        for row in db.query(DatasetEntry).all():
            row.ingested_at = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=8)
        db.commit()

    fake = _FakeWorkDrive(_workbook_bytes(price=15145.0), modified_at="2026-09-06T00:00:00Z")
    result = _read(fake)

    data = result["data"]
    assert "dataset" not in data  # not a dataset answer
    assert fake.downloads == 1
    assert "15145" in data["excerpt"]  # answered from the live file's excerpt
    assert "queryable" in data["note"]  # refreshed copy announced


def test_materialization_survives_broken_ingest_service():
    """REGRESSION (live 2026-09-07): the hook inside process_file_bytes never
    ran because the read path's ingest block failed fast — two reads, zero
    datasets, everything logged at DEBUG. Materialization now happens in the
    read leg itself, so an ingest failure cannot prevent it, and the outcome
    is visible at INFO."""
    from core.database import SessionLocal
    from core.models import DatasetEntry
    from core.sheet_dataset_service import entries_for_file_sync

    fake = _FakeWorkDrive(_workbook_bytes(), modified_at="2026-09-06T00:00:00Z")

    result = _read(fake)

    assert result["status"] == "success"
    assert fake.downloads == 1  # first read: no copy existed, live file opened
    entries = entries_for_file_sync("zoho_workdrive", "file-123")
    assert len(entries) == 1  # materialized despite _NoIngest
    assert entries[0]["row_count"] == 2
    assert any("sheet datasets: materialized" in m for m in _LOG_RECORDS)

    # Second read with the SAME source mtime now takes the fast path:
    # zero downloads, SQL answer.
    fake2 = _FakeWorkDrive(_workbook_bytes(), modified_at="2026-09-01T00:00:00Z")
    second = _read(fake2)
    assert second["status"] == "success"
    assert "dataset" in second["data"]
    assert fake2.downloads == 0
    assert "14145" in second["data"]["excerpt"]


def test_reverify_selfheals_changed_source_after_serving():
    """TTL staleness contract, closed: an aged copy answers instantly (within
    its freshness window), and the background re-verify that follows every
    served answer downloads + hash-checks the source — a changed file is
    re-materialized immediately, so the NEXT ask sees the new value."""
    _seed(_dt.datetime(2026, 9, 1, tzinfo=_dt.timezone.utc))

    # Age the copy past the re-verify min-age so the background runs.
    from core.database import SessionLocal
    from core.models import DatasetEntry

    with SessionLocal() as db:
        for row in db.query(DatasetEntry).all():
            row.ingested_at = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=1)
        db.commit()
        first_hash = row.content_hash

    # Sneaky source edit WITHOUT an mtime change: the copy must still catch it.
    fake = _FakeWorkDrive(_workbook_bytes(price=15145.0), modified_at="2026-09-01T00:00:00Z")
    result = _read(fake)

    data = result["data"]
    assert data["found"] is True
    assert "dataset" in data  # answered from the copy (TTL-fresh)
    assert "14145" in data["excerpt"]
    # downloads == 1 AFTER the drain: the background re-verify downloaded
    # post-serving (user-facing latency was zero) and caught the changed
    # source — that is the self-heal working.
    assert fake.downloads == 1

    # After the drained re-verify: new version materialized, old superseded.
    with SessionLocal() as db:
        rows = db.query(DatasetEntry).filter(DatasetEntry.status == "active").all()
        assert len(rows) == 1
        assert rows[0].content_hash != first_hash

    # The next ask answers with the NEW value from the refreshed copy.
    result2 = _read(fake2 := _FakeWorkDrive(_workbook_bytes(price=15145.0), modified_at="2026-09-01T00:00:00Z"))
    assert "15145" in result2["data"]["excerpt"]
    assert fake2.downloads == 0  # still no download — the copy was current
