"""Connector document identity → derived sheet-dataset lineage.

Live defect pinned here: ``process_file_bytes`` stamped the derived dataset's
``source_document_id`` from a precomputed ``ext_sha1(source:external_id)`` key,
but passed **bytes** to a helper that already encodes its argument — so every
connector ingest that supplied a source-native ``external_id`` (Drive,
OneDrive, Box, Dropbox, WorkDrive …) raised ``AttributeError`` outside the
best-effort block and never reached memory at all.

The regression drives the REAL funnel boundary
(``AutoDocumentIngestionService.process_file_bytes``) with a real connector
CSV, the real sheet-dataset materializer (Parquet + ``dataset_entries``) and
the real shared vector upsert, on isolated scratch SQLite/Parquet state. It
pins the lineage contract the identity exists for:

* the id stamped on the dataset equals the id the memory row is written
  under (one computation, no drift);
* the established write identity is preserved verbatim: the WorkDrive walker
  has always passed an already ``"<source>:<id>"``-prefixed external id, so
  its durable rows live under ``ext_sha1("<source>:<source>:<id>")``. A
  normalising helper would orphan those rows (badge false, refresh writes a
  duplicate), so the pre-change key is pinned against a SEEDED existing row;
* the no-external-id branch still content-addresses and links its derivative.

Expected ids for the bare convention come from
``source_document_id_for_source`` — the catalog's lineage helper. The legacy
walker row uses the pre-change formula inline: seeding a pre-existing store
row from the helper under test would be circular.
"""
from __future__ import annotations

import os
import tempfile

# Absolute, private scratch state BEFORE any core import. The suite conftest
# already forces TESTING=1, but this module states both explicitly so a
# direct run can never resolve a relative DATABASE_URL against a live store
# (AGENTS.md: the 2026-09-04 live-DB wipe class).
_SCRATCH_ROOT = tempfile.mkdtemp(prefix="atom-doc-connector-lineage-")
_IMPORT_ENV = ("TESTING", "DATABASE_URL", "ATOM_DATA_DIR", "ATOM_OFFICE_DIR")
_PRIOR_ENV = {key: os.environ.get(key) for key in _IMPORT_ENV}
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = (
    "sqlite:///" + os.path.join(_SCRATCH_ROOT, "connector-lineage.db"))
os.environ["ATOM_DATA_DIR"] = os.path.join(_SCRATCH_ROOT, "data")
os.environ["ATOM_OFFICE_DIR"] = os.path.join(_SCRATCH_ROOT, "office")

import pytest

from core.auto_document_ingestion import AutoDocumentIngestionService
from core.sheet_dataset_service import source_document_id_for_source

# Restore immediately: `core.database`/`core.models` bind their module-level
# engine from os.environ when THEY are first imported, and a test module must
# not re-point the suite's shared engine at its own scratch file (that leaked
# before and broke sibling tests' row visibility). The per-test fixture below
# creates its own absolute scratch engine and reroutes every session entry
# point this funnel uses, so no live state is reachable either way.
for _key, _prior in _PRIOR_ENV.items():
    if _prior is None:
        os.environ.pop(_key, None)
    else:
        os.environ[_key] = _prior

WS = "ws-connector-lineage"
SOURCE = "google_drive"
EXTERNAL_ID = "file-7777"
CSV_BYTES = (
    "region,metric,value\n"
    "North,Orchid units,7777\n"
    "South,Tulip units,1180\n"
).encode("utf-8")


class _MemoryStore:
    """Durable vector rows stand-in: no embeddings/models, real upsert path.

    ``upsert_document_chunks``/``upsert_document`` run unchanged — only the
    storage calls are local, so the identity they write is the identity under
    test (the buggy ``process_file_bytes`` call is never mocked away).
    """

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def get_document_by_id(self, table_name: str, doc_id: str):
        return self.rows.get(doc_id)

    def get_document_ids_by_prefix(self, table_name: str, prefix: str):
        return [doc_id for doc_id in self.rows if doc_id.startswith(prefix)]

    def delete_documents_by_id(self, table_name: str, doc_id: str) -> bool:
        self.rows.pop(doc_id, None)
        return True

    def delete_documents_by_prefix(self, table_name: str, prefix: str) -> int:
        doomed = [doc_id for doc_id in self.rows if doc_id.startswith(prefix)]
        for doc_id in doomed:
            self.rows.pop(doc_id, None)
        return len(doomed)

    def add_document(self, **kwargs) -> bool:
        doc_id = kwargs["doc_id"]
        self.rows[doc_id] = {
            "id": doc_id,
            "text": kwargs.get("text"),
            "metadata": kwargs.get("metadata") or {},
        }
        return True

    def add_documents_batch(self, table_name: str, docs: list[dict]) -> int:
        for doc in docs:
            self.rows[doc["id"]] = {
                "id": doc["id"],
                "text": doc.get("text"),
                "metadata": doc.get("metadata") or {},
            }
        return len(docs)


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    """Isolated SQLite catalog + Parquet root; all session factories rerouted."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.database import Base

    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path / "office"))
    engine = create_engine(
        f"sqlite:///{tmp_path / 'catalog.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("core.database.get_db_session", factory)
    monkeypatch.setattr("core.database.SessionLocal", factory)
    db = factory()
    yield {"db": db, "factory": factory}
    db.close()
    engine.dispose()


def _service(store: _MemoryStore, workspace_id: str = WS):
    from unittest.mock import patch

    with patch("core.lancedb_handler.get_lancedb_handler", return_value=store):
        return AutoDocumentIngestionService(workspace_id=workspace_id)


def _capture_dataset_materialization(monkeypatch) -> dict:
    """Spy that still delegates to the real materializer, capturing kwargs."""
    from core.sheet_dataset_service import ensure_sheet_dataset as real

    captured: dict = {}

    async def spy(content, **kwargs):
        captured.update(kwargs)
        captured["bytes_len"] = len(content)
        captured["result"] = await real(content, **kwargs)
        return captured["result"]

    monkeypatch.setattr(
        "core.sheet_dataset_service.ensure_sheet_dataset", spy)
    return captured


@pytest.mark.asyncio
async def test_connector_csv_ingest_stamps_dataset_with_row_identity(
        scratch, monkeypatch):
    """THE regression: external_id ingest succeeds and lineage is exact.

    Before the fix this call raised ``AttributeError`` (bytes → helper that
    encodes itself) for every connector that passes a source-native id, so no
    memory row and no dataset could exist.
    """
    store = _MemoryStore()
    captured = _capture_dataset_materialization(monkeypatch)
    service = _service(store)

    result = await service.process_file_bytes(
        CSV_BYTES,
        file_name="Drive Prices.csv",
        source=SOURCE,
        user_id="u-lineage",
        workspace_id=WS,
        external_id=EXTERNAL_ID,
        explicit=True,
    )

    # Actual successful downstream ingest (real shared upsert path).
    assert result["status"] == "ingested", result
    assert result["chars_ingested"] > 0
    assert list(store.rows) == [result["doc_id"]]

    expected = source_document_id_for_source(SOURCE, EXTERNAL_ID)
    assert expected
    assert result["doc_id"] == expected
    # The dataset was stamped BEFORE the row existed — with the very id the
    # later `_file_doc_id` write used. (Traced, not inferred: same value.)
    assert captured["source_document_id"] == expected
    assert captured["bytes_len"] == len(CSV_BYTES)
    assert captured["external_id"] == EXTERNAL_ID

    # Real materialization produced the catalog derivative with that lineage.
    assert captured["result"]["status"] == "materialized", captured["result"]
    entries = captured["result"]["datasets"]
    assert entries
    assert {entry["source_document_id"] for entry in entries} == {expected}
    assert {entry["external_id"] for entry in entries} == {EXTERNAL_ID}

    with scratch["factory"]() as db:
        from core.models import DatasetEntry, IngestedDocument

        catalog = db.query(DatasetEntry).all()
        assert catalog and {
            row.source_document_id for row in catalog} == {expected}
        mirror = db.query(IngestedDocument).filter(
            IngestedDocument.id == expected).one()
        assert mirror.external_id == EXTERNAL_ID
        assert mirror.integration_id == SOURCE


WALKER_SOURCE = "zoho_workdrive"
WALKER_RAW_ID = "file-88"
WALKER_PREFIXED_ID = f"{WALKER_SOURCE}:{WALKER_RAW_ID}"
REFRESH_CSV_BYTES = (
    "region,metric,value\n"
    "North,Orchid units,8888\n"
    "South,Tulip units,1180\n"
).encode("utf-8")
OLD_CSV_TEXT = "region | metric | value\nNorth | Orchid units | 7777"


def _pre_change_doc_id(source: str, external_id: str) -> str:
    """The identity the funnel has ALWAYS written: caller input verbatim.

    Deliberately not imported from the module under test — this is the
    pre-change contract a seeded durable row must keep matching.
    """
    import hashlib

    digest = hashlib.sha1(
        f"{source}:{external_id}".encode("utf-8")).hexdigest()
    return f"ext_{digest[:24]}"


@pytest.mark.asyncio
async def test_seeded_pre_change_walker_row_stays_discoverable_and_refreshes(
        scratch, monkeypatch):
    """Pre-existing double-prefixed walker identity survives the crash fix.

    The walker passes ``external_id="zoho_workdrive:<id>"``; before the fix
    that row lived under ``ext_sha1("zoho_workdrive:zoho_workdrive:<id>")``.
    Seed exactly that durable row, then exercise the real badge probe, the
    non-explicit update/refresh gate, and the explicit refresh write. None may
    re-key it into a "canonical" sibling, and the dataset lineage must name
    the row that actually exists.
    """
    store = _MemoryStore()
    captured = _capture_dataset_materialization(monkeypatch)
    service = _service(store)

    legacy_id = _pre_change_doc_id(WALKER_SOURCE, WALKER_PREFIXED_ID)
    foreign_id = _pre_change_doc_id("box", WALKER_PREFIXED_ID)
    foreign_row = {
        "id": foreign_id,
        "text": "foreign workspace/source copy",
        "metadata": {
            "external_id": WALKER_PREFIXED_ID,
            "source_modified_at": "2026-01-01T00:00:00+00:00",
        },
    }
    store.rows[foreign_id] = foreign_row
    store.rows[legacy_id] = {
        "id": legacy_id,
        "text": OLD_CSV_TEXT,
        "metadata": {
            "file_name": "WorkDrive Prices.csv",
            "integration_id": WALKER_SOURCE,
            "external_id": WALKER_PREFIXED_ID,
            "source_modified_at": "2026-01-01T00:00:00+00:00",
            "freshness_status": "fresh",
        },
    }

    # 1. Durable badge probe — the panel lists BARE ids, while the walker
    #    wrote the prefixed key; both asks must still see the stored row.
    found = await service.ingested_external_ids(
        WALKER_SOURCE, [WALKER_PREFIXED_ID, WALKER_RAW_ID])
    assert found == [WALKER_PREFIXED_ID, WALKER_RAW_ID]

    # 2. Non-explicit source update: hybrid mode must see the stored row as
    #    outdated and refresh it, not call it absent and skip the content.
    class _Hybrid:
        def get_content_mode(self, source: str) -> str:
            return "hybrid"

    monkeypatch.setattr(
        "core.hybrid_data_ingestion.get_hybrid_ingestion_service",
        lambda workspace_id: _Hybrid(),
    )
    refreshed = await service.process_file_bytes(
        REFRESH_CSV_BYTES,
        file_name="WorkDrive Prices.csv",
        source=WALKER_SOURCE,
        user_id="u-lineage",
        workspace_id=WS,
        external_id=WALKER_PREFIXED_ID,
        extra_metadata={
            "source_modified_at": "2026-06-01T00:00:00+00:00",
        },
        explicit=False,
    )
    assert refreshed["status"] == "ingested", refreshed
    assert refreshed["doc_id"] == legacy_id
    assert captured["source_document_id"] == legacy_id
    assert set(store.rows) == {legacy_id, foreign_id}
    assert store.rows[foreign_id] is foreign_row
    assert store.rows[legacy_id]["metadata"]["source_modified_at"].startswith(
        "2026-06-01")

    # Real catalog derivative names the SAME id that actually holds the row.
    with scratch["factory"]() as db:
        from core.models import DatasetEntry

        catalog = db.query(DatasetEntry).all()
        assert catalog and {
            row.source_document_id for row in catalog} == {legacy_id}
        assert {row.external_id for row in catalog} == {WALKER_RAW_ID}

    # 3. Explicit refresh from the OTHER convention (the single-file panel
    #    posts the bare id) reuses the legacy row's identity, so there is no
    #    second "canonical" copy for a later delete to leave behind.
    again = await service.process_file_bytes(
        CSV_BYTES,
        file_name="WorkDrive Prices.csv",
        source=WALKER_SOURCE,
        user_id="u-lineage",
        workspace_id=WS,
        external_id=WALKER_RAW_ID,
        explicit=True,
    )
    assert again["doc_id"] == legacy_id
    assert set(store.rows) == {legacy_id, foreign_id}
    assert store.rows[foreign_id] is foreign_row


def test_external_doc_id_preserves_established_write_identity():
    """The one helper every identity site uses — exactly the pre-change key."""
    from core.auto_document_ingestion import (
        _external_doc_id,
        _external_doc_id_candidates,
    )

    # Bare connector id: unchanged (`source_document_id_for_source` agrees).
    assert _external_doc_id(SOURCE, EXTERNAL_ID) == _pre_change_doc_id(
        SOURCE, EXTERNAL_ID)
    assert _external_doc_id(SOURCE, EXTERNAL_ID) == (
        source_document_id_for_source(SOURCE, EXTERNAL_ID))
    # Walker's already-prefixed id stays VERBATIM — normalising it would
    # orphan every durable row written before this fix.
    walker_legacy = _pre_change_doc_id(
        WALKER_SOURCE, WALKER_PREFIXED_ID)
    walker_bare = _pre_change_doc_id(WALKER_SOURCE, WALKER_RAW_ID)
    assert _external_doc_id(
        WALKER_SOURCE, WALKER_PREFIXED_ID) == walker_legacy
    # Lookups cover both historical conventions, exact-caller-id first. No
    # write is re-keyed and no other source is included.
    assert _external_doc_id_candidates(
        WALKER_SOURCE, WALKER_PREFIXED_ID) == [walker_legacy, walker_bare]
    assert _external_doc_id_candidates(
        WALKER_SOURCE, WALKER_RAW_ID) == [walker_bare, walker_legacy]
    # Source-scoped: a reused raw id in another integration is another file.
    assert _external_doc_id("box", EXTERNAL_ID) != _external_doc_id(
        SOURCE, EXTERNAL_ID)
    assert _external_doc_id_candidates("box", EXTERNAL_ID) == [
        _external_doc_id("box", EXTERNAL_ID),
        _external_doc_id("box", f"box:{EXTERNAL_ID}"),
    ]


@pytest.mark.asyncio
async def test_no_external_id_branch_still_links_content_addressed_dataset(
        scratch, monkeypatch):
    """Positive control: identity falls back to content addressing, unchanged."""
    import hashlib

    store = _MemoryStore()
    captured = _capture_dataset_materialization(monkeypatch)
    service = _service(store)

    result = await service.process_file_bytes(
        CSV_BYTES,
        file_name="Local Prices.csv",
        source="manual_import",
        user_id="u-lineage",
        workspace_id=WS,
        explicit=True,
    )

    assert result["status"] == "ingested", result
    assert result["doc_id"].startswith("doc_")
    assert list(store.rows) == [result["doc_id"]]
    # No stable source id ⇒ no id to stamp before extraction.
    assert captured["source_document_id"] is None

    content_hash = hashlib.sha1(CSV_BYTES).hexdigest()
    assert captured["result"]["status"] == "materialized", captured["result"]
    with scratch["factory"]() as db:
        from core.models import DatasetEntry

        catalog = db.query(DatasetEntry).all()
        assert catalog
        # Linked after extraction to the SAME content-addressed row id.
        assert {row.source_document_id for row in catalog} == {result["doc_id"]}
        assert {row.external_id for row in catalog} == {f"sha1:{content_hash}"}
