"""Unit tests for the generalized value-discovery layer:

  Batch 1 — datasets planner service (cross-file probe, evidence blocks)
  Batch 2 — external_id key normalization + bounded backfill contract
  Batch 3 — app-record sync (watermark landing, in-place upsert)

Run: cd backend && python -m pytest tests/unit/test_datasets_planner_service.py -q
"""
import asyncio
import datetime as _dt
import io
import json
from typing import Dict

import pandas as pd
import pytest

from core.database import Base, engine
from core.sheet_dataset_service import search_all_datasets_sync


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    import core.models  # noqa: F401
    from core.database import SessionLocal
    from core.models import DatasetEntry

    Base.metadata.create_all(bind=engine)
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path))
    yield
    with SessionLocal() as db:
        db.query(DatasetEntry).delete()
        db.commit()


def _wb_bytes(price=14145.0) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame({
        "Item Number": ["WG-350DSAV", "LINMAC-2"],
        "Price": [price, 9800.0],
    }).to_excel(buf, sheet_name="Machine Pricing", index=False)
    return buf.getvalue()


def _seed(name: str, external_id: str) -> Dict:
    from core.sheet_dataset_service import materialize_sheet_bytes_sync

    result = materialize_sheet_bytes_sync(
        _wb_bytes(),
        file_name=name,
        source="zoho_workdrive",
        user_id="u1",
        workspace_id="ws-test",
        external_id=external_id,
    )
    assert result["status"] == "materialized"
    return result


# ── Batch 1: cross-file probe + planner block ────────────────────────────────


def test_cross_file_probe_finds_value_and_names_source():
    _seed("price list 2019.xlsx", "file-1")
    result = search_all_datasets_sync("what is the price of WG-350DSAV?", user_id="u1")
    assert result is not None and result["files_searched"] >= 1
    assert result["hits"], "expected a hit"
    top = result["hits"][0]
    assert top["entity_name"] == "Machine Pricing"
    assert any(r["Item Number"] == "WG-350DSAV" for r in top["rows"])


def test_cross_file_probe_negative_evidence():
    _seed("price list 2019.xlsx", "file-1")
    result = search_all_datasets_sync("where is order ZZ-99999-Q?", user_id="u1")
    assert result is not None
    assert result["hits"] == []  # provably absent — real negative evidence
    assert result["token"] == "99999"


def test_probe_without_code_token_returns_none():
    # No digit-bearing token → None (callers fall back to memory).
    assert search_all_datasets_sync("what did we discuss?", user_id="u1") is None


def test_planner_block_positive_and_negative():
    from core.chat_tool_planner import _datasets_search_block

    _seed("price list 2019.xlsx", "file-1")
    block = asyncio.run(_datasets_search_block(
        "u1", "what is the price of WG-350DSAV?", {"workspace_id": "ws-test"}))
    assert block is not None
    assert "datasets.search" in block and "R2" in block and "14145" in block
    assert "GROUNDING RULE" in block

    negative = asyncio.run(_datasets_search_block(
        "u1", "where is order ZZ-99999-Q?", {"workspace_id": "ws-test"}))
    assert negative is not None
    assert "appear in NONE" in negative  # honest negative evidence


def test_no_code_query_delegates_to_memory(monkeypatch):
    from core.chat_tool_planner import _datasets_search_block

    async def _sentinel(*a, **k):
        return "MEMORY-BLOCK-SENTINEL"

    monkeypatch.setattr("core.chat_tool_planner._memory_search_block", _sentinel)
    block = asyncio.run(_datasets_search_block("u1", "what did we discuss?", None))
    assert block == "MEMORY-BLOCK-SENTINEL"


# ── Batch 2: identity normalization ─────────────────────────────────────────


def test_sync_keyed_and_read_keyed_collapse_to_one_identity():
    """REGRESSION: the sync funnel saves external_id='zoho_workdrive:{id}'
    while the read leg looks up the bare id — both must hit the same rows."""
    from core.sheet_dataset_service import ensure_sheet_dataset, entries_for_file_sync

    asyncio.run(ensure_sheet_dataset(
        _wb_bytes(), file_name="Synced.xlsx", source="zoho_workdrive",
        user_id="u1", workspace_id="ws-test",
        external_id="zoho_workdrive:file-sync-9",
    ))
    entries = entries_for_file_sync("zoho_workdrive", "file-sync-9")
    assert len(entries) == 1  # bare id finds the sync-keyed dataset


def test_read_leg_materialization_dedupes_backfill():
    """The backfill lane downloads sheets with the prefixed key — a later
    read-leg materialization with the bare key must dedupe (no duplicates)."""
    from core.sheet_dataset_service import ensure_sheet_dataset, entries_for_file_sync

    asyncio.run(ensure_sheet_dataset(
        _wb_bytes(), file_name="a.xlsx", source="zoho_workdrive",
        user_id="u1", workspace_id="ws-test",
        external_id="zoho_workdrive:file-bf",
    ))
    result = asyncio.run(ensure_sheet_dataset(
        _wb_bytes(), file_name="a.xlsx", source="zoho_workdrive",
        user_id="u1", workspace_id="ws-test",
        external_id="file-bf",
    ))
    assert result["status"] == "current"
    assert len(entries_for_file_sync("zoho_workdrive", "file-bf")) == 1


# ── Batch 3: app-record datasets ─────────────────────────────────────────────


def test_app_records_land_and_are_probeable():
    from core.app_dataset_sync import land_app_records_sync
    from core.database import SessionLocal
    from core.models import DatasetEntry

    rows = [
        {"Invoice Number": "INV-81575", "Customer": "Blumetric", "Total": 13782.73,
         "last_modified_time": "2026-09-06T10:00:00+00:00"},
        {"Invoice Number": "INV-81576", "Customer": "Acme", "Total": 500.0,
         "last_modified_time": "2026-09-05T10:00:00+00:00"},
    ]
    out = land_app_records_sync("ws-test", "zoho_books", "invoices", rows)
    assert out["status"] == "synced"

    # Probeable through the SAME cross-file search — this is the whole point.
    result = search_all_datasets_sync("total for invoice 81575?", user_id="u1")
    assert result is not None and result["hits"]
    top = result["hits"][0]
    assert top["source_kind"] == "app_records"
    assert top["entity_name"] == "invoices"
    assert any("81575" in json.dumps(r, default=str) for r in top["rows"])

    # Unchanged pull is a no-op (hash skip, no rewrite churn).
    again = land_app_records_sync("ws-test", "zoho_books", "invoices", rows)
    assert again["status"] == "current"
    with SessionLocal() as db:
        assert db.query(DatasetEntry).filter(
            DatasetEntry.source_kind == "app_records").count() == 1


def test_app_record_watermark_persists():
    from core.app_dataset_sync import land_app_records_sync
    from core.database import SessionLocal
    from core.models import DatasetEntry

    rows = [{"Invoice Number": "INV-1", "last_modified_time": "2026-09-06T10:00:00+00:00"}]
    land_app_records_sync("ws-test", "zoho_books", "invoices", rows)
    with SessionLocal() as db:
        row = db.query(DatasetEntry).filter(
            DatasetEntry.source_kind == "app_records").first()
        assert row is not None and row.source_modified_at is not None


# ── VFS: the catalog as an agent-native filesystem ──────────────────────────


def test_vfs_datasets_provider_ls_cat_grep():
    """Agents navigate datasets with the ls/cat/grep they already know —
    grep citations carry precise line numbers, no location hinting needed."""
    _seed("price list 2019.xlsx", "file-1")

    from integrations.vfs.datasets_vfs import DatasetsVFSProvider

    provider = DatasetsVFSProvider()

    async def _flow():
        groups = await provider.ls("datasets")
        assert groups and groups[0].name == "zoho_workdrive_price_list_2019"
        group = groups[0].name
        leaves = await provider.ls(f"datasets/{group}")
        assert leaves and leaves[0].type == "file"
        resource = await provider.cat(f"datasets/{group}/{leaves[0].name}")
        assert resource.meta["row_count"] == 2
        joined = "\n".join(resource.lines)
        assert "R2" in joined and "14145" in joined
        citations = await provider.grep("WG-350DSAV", "datasets")
        assert citations
        assert citations[0].path.endswith("content.lines")
        assert citations[0].line >= 1

    asyncio.run(_flow())


# ── Scalability: DuckDB probe + storage GC ──────────────────────────────────


def test_probe_falls_back_to_pandas_without_duckdb(monkeypatch):
    """DuckDB is the scalable engine; pandas remains a working fallback."""
    import sys

    _seed("price list 2019.xlsx", "file-1")
    monkeypatch.setitem(sys.modules, "duckdb", None)  # import duckdb → ImportError
    result = search_all_datasets_sync("what is the price of WG-350DSAV?", user_id="u1")
    assert result is not None and result["hits"]
    top = result["hits"][0]
    assert any(r["Item Number"] == "WG-350DSAV" for r in top["rows"])


def test_gc_evicts_oldest_under_quota_keeps_grace_rows(tmp_path, monkeypatch):
    """Quota eviction: superseded/old rows go first; rows inside the grace
    window (just-served answers) are never evicted."""
    from core.database import SessionLocal
    from core.models import DatasetEntry
    from core.sheet_dataset_service import gc_workspace_datasets_sync

    _seed("old.xlsx", "file-old")
    _seed("new.xlsx", "file-new")

    # Age BOTH rows beyond the grace window, then set a tiny quota.
    monkeypatch.setenv("ATOM_SHEET_DATASET_GC_GRACE_S", "0")
    monkeypatch.setenv("ATOM_SHEET_DATASET_MAX_STORE_MB", "0.001")
    with SessionLocal() as db:
        for r in db.query(DatasetEntry).all():
            r.ingested_at = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=2)
        db.commit()

    out = gc_workspace_datasets_sync("ws-test")
    assert out["status"] == "ok" and out["evicted"] >= 1
    with SessionLocal() as db:
        assert db.query(DatasetEntry).count() == 0  # tiny quota → everything evicted
    for p in tmp_path.rglob("*.parquet"):
        raise AssertionError(f"parquet survived GC: {p}")


def test_gc_grace_protects_fresh_rows(tmp_path, monkeypatch):
    from core.database import SessionLocal
    from core.models import DatasetEntry
    from core.sheet_dataset_service import gc_workspace_datasets_sync

    _seed("fresh.xlsx", "file-fresh")
    monkeypatch.setenv("ATOM_SHEET_DATASET_MAX_STORE_MB", "0.001")
    monkeypatch.setenv("ATOM_SHEET_DATASET_GC_GRACE_S", "3600")

    out = gc_workspace_datasets_sync("ws-test")
    assert out["status"] == "ok" and out["evicted"] == 0  # inside grace window
    with SessionLocal() as db:
        assert db.query(DatasetEntry).count() == 1


def test_adapter_registry_shape():
    """Registry is generic: every integration lists entities with fetch +
    configured; nothing here is allowed to hardcode a business."""
    from core.app_dataset_sync import ADAPTERS

    assert "zoho" in ADAPTERS
    names = {spec.name for spec in ADAPTERS["zoho"]}
    assert {"books_invoices", "inventory_items"} <= names
    for specs in ADAPTERS.values():
        for spec in specs:
            assert callable(spec.fetch) and callable(spec.configured)
