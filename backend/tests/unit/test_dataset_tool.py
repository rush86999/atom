"""Unit tests for the dataset catalog agent tools (tools/dataset_tool.py).

Verifies the agent-runtime flow: find_datasets → load_registered_dataset →
existing query_data (DuckDB) against the loaded dataset.

Run: cd backend && python -m pytest tests/unit/test_dataset_tool.py -q
"""
import asyncio
import datetime as _dt
import io

import pandas as pd
import pytest

from core.database import Base, engine


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    import core.models  # noqa: F401
    from core.data.dataset_manager import get_dataset_manager
    from core.database import SessionLocal
    from core.models import DatasetEntry

    Base.metadata.create_all(bind=engine)
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path))
    get_dataset_manager().clear_all()
    yield
    get_dataset_manager().clear_all()
    with SessionLocal() as db:
        db.query(DatasetEntry).delete()
        db.commit()


def _seed_dataset() -> str:
    from core.sheet_dataset_service import materialize_sheet_bytes_sync

    buf = io.BytesIO()
    pd.DataFrame({
        "Item Number": ["WG-350DSAV", "LINMAC-2"],
        "Price": [14145.0, 9800.0],
    }).to_excel(buf, sheet_name="Machine Pricing", index=False)
    result = materialize_sheet_bytes_sync(
        buf.getvalue(),
        file_name="price list 2026.xlsx",
        source="zoho_workdrive",
        user_id="u1",
        workspace_id="ws-tool",
        external_id="file-9",
        source_modified_at=_dt.datetime(2026, 9, 1, tzinfo=_dt.timezone.utc),
    )
    assert result["status"] == "materialized"
    return result["datasets"][0]["dataset_name"]


def test_find_datasets_lists_and_hints_flow():
    from tools.dataset_tool import find_datasets

    name = _seed_dataset()
    found = asyncio.run(find_datasets(file_hint="price list", workspace_id="ws-tool"))
    assert found["success"] is True
    names = [d["dataset_name"] for d in found["datasets"]]
    assert name in names
    assert "load_registered_dataset" in found["how_to_use"]
    (ds,) = [d for d in found["datasets"] if d["dataset_name"] == name]
    assert ds["columns"][:2] == ["Item Number", "Price"]
    assert ds["rows"] == 2

    empty = asyncio.run(find_datasets(file_hint="nonexistent thing", workspace_id="ws-other"))
    assert empty["success"] is True and empty["count"] == 0


def test_load_then_query_data_roundtrip():
    from tools.data_analysis_tool import query_data
    from tools.dataset_tool import load_registered_dataset

    name = _seed_dataset()
    loaded = asyncio.run(load_registered_dataset(name, session_id="t1"))
    assert loaded["success"] is True
    assert loaded["dataset"]["row_count"] == 2
    assert loaded["freshness"]["content_hash"]

    result = asyncio.run(query_data(name, "SELECT COUNT(*) AS n FROM df", session_id="t1"))
    assert result["success"] is True and result["data"][0]["n"] == 2

    exact = asyncio.run(
        query_data(
            name,
            "SELECT Price FROM df WHERE \"Item Number\" = 'WG-350DSAV'",
            session_id="t1",
        )
    )
    assert exact["success"] is True and exact["data"][0]["Price"] == 14145.0


def test_load_unknown_and_disabled(monkeypatch):
    from tools.dataset_tool import load_registered_dataset

    name = _seed_dataset()
    missing = asyncio.run(load_registered_dataset("no_such_dataset", session_id="t2"))
    assert missing["success"] is False

    # Kill switch blocks NEW loads (materialization included), not the tools'
    # catalog lookups: loading an already-registered dataset is refused too.
    monkeypatch.setenv("ATOM_SHEET_DATASETS", "0")
    assert asyncio.run(load_registered_dataset(name, session_id="t3"))["success"] is False
