"""Formula sidecar tests for the sheet dataset service.

pandas/Parquet carry only computed VALUES — the 2026-09-09 Trumatic-L3030S
conversation had to reverse-engineer '=I11/0.95' from the numbers and missed
the Final Price/Profit/Margin formula columns entirely. These tests pin the
contract introduced with the fix: materialization extracts per-cell formulas
from the ORIGINAL bytes (the only moment they exist — attachments are never
persisted) into a sibling .formulas.json next to each Parquet; reverts
self-heal the sidecar; prune/GC remove it with their Parquet; and the read
path renders a FORMULAS footer so "how is this computed?" turns cite real
cells instead of guessing.

Run: cd backend && python -m pytest tests/unit/test_sheet_dataset_formulas.py -q
(TESTING=1 is forced by tests/conftest.py — scratch SQLite, never the live DB.)
"""
import asyncio
import io
from pathlib import Path

import pytest

from core.database import Base, engine
from core.sheet_dataset_service import (
    _formula_sidecar_path,
    _formula_map_raw_xml,
    _write_formula_sidecar,
    load_formulas_for_parquet,
    materialize_sheet_bytes_sync,
    render_dataset_answer,
)


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    """Parquet writes go to a per-test temp root; catalog rows are cleaned."""
    import core.models  # noqa: F401 — register DatasetEntry on Base metadata
    from core.database import SessionLocal
    from core.models import DatasetEntry

    Base.metadata.create_all(bind=engine)
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path))
    yield
    with SessionLocal() as db:
        db.query(DatasetEntry).delete()
        db.commit()


def _formula_xlsx() -> bytes:
    """A workbook with the quote-style formula chain (openpyxl writes the
    formula strings; there are no cached values, which pandas tolerates)."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = "Machine"
    ws["B1"] = "USD"
    ws["C1"] = "Landed"
    ws["D1"] = "Dealer"
    ws["A2"] = "Trumatic-L3030S"
    ws["B2"] = 20000
    ws["C2"] = "=B2+5000"
    ws["D2"] = "=C2/0.74"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _plain_xlsx(price=14145.0) -> bytes:
    import pandas as pd

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame({"Item": ["A"], "Price": [price]}).to_excel(
            writer, sheet_name="Sheet1", index=False
        )
    return buf.getvalue()


def _materialize(content, **kw):
    return materialize_sheet_bytes_sync(
        content,
        file_name=kw.pop("file_name", "quote.xlsx"),
        source=kw.pop("source", "outlook"),
        user_id="u1",
        workspace_id="ws-formula",
        external_id=kw.pop("external_id", "file-f1"),
        **kw,
    )


def _entries():
    from core.database import SessionLocal
    from core.models import DatasetEntry

    with SessionLocal() as db:
        return db.query(DatasetEntry).all()


def test_materialize_writes_formula_sidecar():
    result = _materialize(_formula_xlsx())
    assert result["status"] == "materialized"
    (ds,) = result["datasets"]
    sidecar = _formula_sidecar_path(ds["parquet_path"])
    assert sidecar.exists()
    formulas = load_formulas_for_parquet(str(ds["parquet_path"]))
    assert formulas == {"C2": "=B2+5000", "D2": "=C2/0.74"}


def test_plain_workbook_gets_empty_sidecar():
    result = _materialize(_plain_xlsx())
    assert result["status"] == "materialized"
    (ds,) = result["datasets"]
    assert _formula_sidecar_path(ds["parquet_path"]).exists()
    assert load_formulas_for_parquet(str(ds["parquet_path"])) == {}


def test_csv_has_no_formula_sidecar():
    result = _materialize(
        b"Item,Price\nA,1.0\n", file_name="stock.csv", external_id="csv-f1"
    )
    assert result["status"] == "materialized"
    (ds,) = result["datasets"]
    # CSVs cannot carry formulas — the sidecar (always written, so its
    # existence means "formulas extracted at this version") is empty.
    assert load_formulas_for_parquet(str(ds["parquet_path"])) == {}


def test_reverted_version_self_heals_sidecar():
    """A re-materialization of previously superseded bytes (the 'user reverted
    the file' flow) reaches the per-sheet `already` branch — a missing sidecar
    is rebuilt there from the bytes in hand."""
    result = _materialize(_formula_xlsx())
    (ds,) = result["datasets"]
    sidecar = _formula_sidecar_path(ds["parquet_path"])
    sidecar.unlink()

    from core.database import SessionLocal
    from core.models import DatasetEntry

    with SessionLocal() as db:
        db.query(DatasetEntry).update({"status": "superseded"})
        db.commit()

    again = _materialize(_formula_xlsx())
    assert again["status"] == "materialized"
    assert sidecar.exists()
    assert load_formulas_for_parquet(str(ds["parquet_path"])) == {
        "C2": "=B2+5000",
        "D2": "=C2/0.74",
    }


def test_stale_version_prune_removes_sidecar_with_parquet():
    # Steady state keeps the active + last 2 superseded versions, so a 4th
    # materialization prunes exactly one. Which one is ingested_at-ordered
    # (all tie inside a fast test run) — the contract under test is that the
    # sidecar dies WITH its Parquet, never outliving or orphaning it.
    contents = [_formula_xlsx()] + [
        _plain_xlsx(price=float(1000 + n)) for n in range(3)
    ]
    paths = [
        _materialize(content)["datasets"][0]["parquet_path"]
        for content in contents
    ]

    gone = [p for p in paths if not Path(p).exists()]
    assert len(gone) == 1
    assert not _formula_sidecar_path(gone[0]).exists()
    for p in paths:
        if p not in gone:
            assert Path(p).exists()
            assert _formula_sidecar_path(p).exists()


def test_gc_evict_removes_sidecar_with_parquet(monkeypatch):
    from core import sheet_dataset_service as sds

    # The grace window protects just-served rows; these rows are test-local.
    monkeypatch.setattr(sds, "_GC_GRACE_S", 0)

    result = _materialize(_formula_xlsx())
    (ds,) = result["datasets"]
    sidecar = _formula_sidecar_path(ds["parquet_path"])
    assert sidecar.exists()

    gc = sds.gc_workspace_datasets_sync("ws-formula", max_store_bytes=1)
    assert gc["evicted"] == 1
    assert not sidecar.exists()


def test_identical_bytes_reverify_refreshes_freshness_stamp():
    """A re-materialization whose bytes hash to the copy's own content_hash
    is a freshness PROOF — 'current' must re-stamp ingested_at. Without this
    a stale-by-TTL copy stayed stale forever (reverify re-downloads identical
    bytes, status 'current' never touched the stamp) and every read kept
    falling through to the live download."""
    import datetime as _dt

    result = _materialize(_formula_xlsx())
    (ds,) = result["datasets"]

    from core.database import SessionLocal
    from core.models import DatasetEntry

    stale = _dt.datetime(2026, 9, 1, tzinfo=_dt.timezone.utc)
    with SessionLocal() as db:
        db.query(DatasetEntry).update({"ingested_at": stale})
        db.commit()

    again = _materialize(_formula_xlsx())
    assert again["status"] == "current"
    with SessionLocal() as db:
        row = db.query(DatasetEntry).filter(DatasetEntry.id == ds["id"]).first()
        stamp = row.ingested_at
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=_dt.timezone.utc)
        assert stamp > stale


def test_render_dataset_answer_includes_formulas():
    result = {
        "file_name": "quote.xlsx",
        "entity_name": "Sheet1",
        "source_modified_at": None,
        "sql": "SELECT * FROM df",
        "row_count": 1,
        "columns": ["Machine", "Dealer"],
        "rows": [{"Machine": "Trumatic-L3030S", "Dealer": 47415.84, "__sheet_row": 2}],
        "formulas": {"C2": "=B2+5000", "D2": "=C2/0.74"},
    }
    out = render_dataset_answer(result)
    assert "FORMULAS (original workbook):" in out
    assert "C2==B2+5000" in out
    assert "D2==C2/0.74" in out


def test_render_dataset_answer_without_formulas_omits_footer():
    result = {
        "file_name": "quote.xlsx",
        "entity_name": "Sheet1",
        "source_modified_at": None,
        "sql": "SELECT * FROM df",
        "row_count": 1,
        "columns": ["Machine"],
        "rows": [{"Machine": "Trumatic-L3030S"}],
    }
    assert "FORMULAS" not in render_dataset_answer(result)


def test_raw_xml_formula_fallback_scans_formula_cells():
    """The stdlib-XML scan (openpyxl-hostile workbooks) reads <f> bodies with
    real cell refs and sheet names — run here on a valid package."""
    formulas = _formula_map_raw_xml(_formula_xlsx())
    assert formulas == {"Sheet1": {"C2": "=B2+5000", "D2": "=C2/0.74"}}
