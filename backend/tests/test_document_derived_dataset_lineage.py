"""Source-lineage contract for document deletion and derived datasets.

A CSV/XLSX upload is automatically materialized into the sheet-dataset
catalog (Parquet + ``dataset_entries``). Before this contract, deleting the
source document left that derivative ``active``: an agent could still resolve
it by name, find it by value, and read its rows as current grounding after a
"verified" delete.

These tests drive the real catalog materializer, the real delete service and
the real catalog read paths against scratch SQLite/Parquet state. They pin:

* exact lineage (``source_document_id``) and direct tombstoning on delete;
* read-time refusal of a derivative whose document is removed/stale even when
  a delete sweep did not run;
* exactness under negative twins: foreign workspace, two files sharing a
  filename, unrelated/independently-saved artifacts;
* duplicate-operation replay and a fresh (restart-like) session;
* honest partial/unknown reporting when the derivative sweep cannot complete.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (
    DatasetEntry,
    IngestedDocument,
    Tenant,
    User,
    Workspace,
)
from core.sheet_dataset_service import (
    find_entries_sync,
    materialize_sheet_bytes_sync,
    read_sheet_row_sync,
    resolve_dataset_entry_scoped_sync,
    search_all_datasets_sync,
    source_document_id_for_source,
)

WS = "ws-lineage"
PEER_WS = "ws-peer"
TENANT = "t-lineage"


class _NoVectorRows:
    """Minimal handler: this document has no LanceDB rows in these tests."""

    def count_document_rows_by_id(self, table, doc_id):
        return 0

    def count_document_rows_by_prefix(self, table, prefix):
        return 0

    def delete_documents_by_id(self, table, doc_id):
        return True

    def delete_documents_by_prefix(self, table, prefix):
        return True


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    monkeypatch.setenv("ATOM_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path / "office"))
    engine = create_engine(
        f"sqlite:///{tmp_path / 'derived-lineage.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("core.database.get_db_session", factory)
    db = factory()
    db.add(Tenant(id=TENANT, name=TENANT, subdomain=TENANT))
    db.add(Workspace(id=WS, tenant_id=TENANT, name=WS))
    db.add(Workspace(id=PEER_WS, tenant_id=TENANT, name=PEER_WS))
    user = User(
        id="u-lineage", email="lineage@example.invalid", hashed_password="h",
        first_name="Line", last_name="Age", role="member", status="active",
        tenant_id=TENANT, workspace_id=WS, is_active=True)
    db.add(user)
    db.commit()
    yield {"db": db, "factory": factory, "user": user, "tmp_path": tmp_path,
           "handler": _NoVectorRows()}
    db.close()
    engine.dispose()


def _csv(marker: str) -> bytes:
    return (
        "region,metric,value\n"
        f"North,Orchid units,{marker}\n"
        "South,Tulip units,1180\n"
    ).encode("utf-8")


def _seed_document(
    scratch, *, doc_id: str, workspace_id: str = WS, file_name: str,
    content: bytes, integration_id: str = "manual_upload",
    external_id: str | None = None,
    freshness: str = "fresh",
) -> IngestedDocument:
    """Write the upload's materialized bytes + its authoritative SQL row."""
    upload_root = Path(scratch["tmp_path"]) / "office" / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    path = upload_root / f"{doc_id}.csv"
    path.write_bytes(content)
    row = IngestedDocument(
        id=doc_id,
        workspace_id=workspace_id,
        tenant_id=TENANT,
        file_name=file_name,
        file_path=str(path),
        file_type="csv",
        integration_id=integration_id,
        file_size_bytes=len(content),
        external_id=external_id or f"upload_{doc_id}",
        source_content_hash="ev4:" + hashlib.sha256(content).hexdigest(),
        freshness_status=freshness,
    )
    scratch["db"].add(row)
    scratch["db"].commit()
    return row


def _materialize_upload(scratch, *, doc_id: str, file_name: str,
                        content: bytes, workspace_id: str = WS):
    result = materialize_sheet_bytes_sync(
        content,
        file_name=file_name,
        source="upload",
        user_id=scratch["user"].id,
        workspace_id=workspace_id,
        external_id=None,
        source_document_id=doc_id,
    )
    assert result["status"] in ("materialized", "current"), result
    return result["datasets"][0]


async def _delete(scratch, doc_id: str, *, workspace_id: str = WS,
                  operation_id: str | None = None):
    from core.document_delete_service import delete_document_verified

    return await delete_document_verified(
        scratch["db"],
        actor=scratch["user"],
        workspace_id=workspace_id,
        doc_id=doc_id,
        handler=scratch["handler"],
        operation_id=operation_id,
    )


def _entry(scratch, entry_id: str) -> DatasetEntry:
    return scratch["db"].get(DatasetEntry, entry_id)


@pytest.mark.asyncio
async def test_upload_derivative_is_revoked_and_not_grounding(scratch):
    content = _csv("9241")
    doc_id = "doc_upload_lineage"
    _seed_document(scratch, doc_id=doc_id, file_name="Orchid.csv",
                   content=content)
    entry = _materialize_upload(
        scratch, doc_id=doc_id, file_name="Orchid.csv", content=content)

    assert entry["source_document_id"] == doc_id
    assert entry["status"] == "active"
    parquet = Path(entry["parquet_path"])
    assert parquet.exists()
    # Valid twin: the derivative IS current grounding before the delete.
    assert [e["id"] for e in find_entries_sync("orchid", workspace_id=WS)] == [
        entry["id"]]
    assert search_all_datasets_sync("9241", workspace_id=WS)["hits"]

    result = await _delete(scratch, doc_id)
    assert result["status"] == "verified", result
    effects = result["data"]["effects"]
    assert effects["derived"] == "revoked"
    assert effects["derived_matched"] == 1
    assert effects["derived_revoked"] == 1
    assert effects["complete"] is True

    row = _entry(scratch, entry["id"])
    assert row.status == "removed"
    assert row.source_document_id == doc_id
    assert not parquet.exists()
    assert not Path(str(parquet) + ".formulas.json").exists()

    # Negative twin: no catalog read path can serve the removed source.
    assert find_entries_sync("orchid", workspace_id=WS) == []
    resolved = resolve_dataset_entry_scoped_sync(
        entry["dataset_name"], workspace_id=WS)
    assert resolved["state"] == "inactive", resolved
    assert resolved["entry"]["status"] == "removed"
    assert resolved.get("revoked") is True
    probe = search_all_datasets_sync("9241", workspace_id=WS)
    assert probe["hits"] == []
    assert probe["files_searched"] == 0
    assert read_sheet_row_sync(
        "Orchid.csv", entry["entity_name"], 2, workspace_id=WS) is None


@pytest.mark.asyncio
async def test_foreign_scope_cannot_revoke_owner_derivative(scratch):
    content = _csv("5150")
    doc_id = "doc_foreign_guard"
    _seed_document(scratch, doc_id=doc_id, file_name="Foreign.csv",
                   content=content)
    entry = _materialize_upload(
        scratch, doc_id=doc_id, file_name="Foreign.csv", content=content)

    result = await _delete(scratch, doc_id, workspace_id=PEER_WS)
    assert result["status"] == "refused"
    assert result["http_status"] == 404

    row = _entry(scratch, entry["id"])
    assert row.status == "active"
    assert Path(row.parquet_path).exists()
    assert find_entries_sync("foreign", workspace_id=WS)


@pytest.mark.asyncio
async def test_same_filename_distinct_sources_are_not_collateral(scratch):
    drop_content = _csv("1111")
    keep_content = _csv("2222")
    drop_doc = "doc_drop_same_name"
    source = "google_drive"
    external_id = "shared-name-keep"
    keep_doc = source_document_id_for_source(source, external_id)
    _seed_document(scratch, doc_id=drop_doc, file_name="shared.csv",
                   content=drop_content)
    _seed_document(
        scratch, doc_id=keep_doc, file_name="shared.csv",
        content=keep_content, integration_id=source,
        external_id=external_id)
    drop_entry = _materialize_upload(
        scratch, doc_id=drop_doc, file_name="shared.csv",
        content=drop_content)
    keep_result = materialize_sheet_bytes_sync(
        keep_content, file_name="shared.csv", source=source,
        user_id=scratch["user"].id, workspace_id=WS,
        external_id=external_id)
    keep_entry = keep_result["datasets"][0]
    assert keep_entry["id"] != drop_entry["id"]

    result = await _delete(scratch, drop_doc)
    assert result["status"] == "verified", result

    assert _entry(scratch, drop_entry["id"]).status == "removed"
    kept = _entry(scratch, keep_entry["id"])
    assert kept.status == "active"
    assert Path(kept.parquet_path).exists()
    assert read_sheet_row_sync(
        "shared.csv", keep_entry["entity_name"], 2,
        workspace_id=WS)["row"]["value"] == 2222


@pytest.mark.asyncio
async def test_unrelated_independent_artifact_is_preserved(scratch):
    content = _csv("3333")
    doc_id = "doc_with_unrelated_catalog"
    _seed_document(scratch, doc_id=doc_id, file_name="Source.csv",
                   content=content)
    source_entry = _materialize_upload(
        scratch, doc_id=doc_id, file_name="Source.csv", content=content)

    root = Path(scratch["tmp_path"]) / "data" / "sheet_datasets"
    root.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    independent_parquet = root / "invoices.parquet"
    pd.DataFrame({"invoice": ["INV-1"], "total": [42]}).to_parquet(
        independent_parquet, index=False)
    independent = DatasetEntry(
        id="entry-independent",
        workspace_id=WS,
        tenant_id=TENANT,
        created_by=scratch["user"].id,
        source_kind="app_records",
        source="zoho_books",
        external_id="invoices",
        file_name="Invoices (synced)",
        content_hash="a" * 40,
        entity_name="invoices",
        dataset_name="zoho_books_invoices",
        parquet_path=str(independent_parquet),
        row_count=1,
        column_count=2,
        columns_json={"columns": [{"name": "invoice"}, {"name": "total"}]},
        status="active",
    )
    scratch["db"].add(independent)
    scratch["db"].commit()

    result = await _delete(scratch, doc_id)
    assert result["status"] == "verified", result
    assert _entry(scratch, source_entry["id"]).status == "removed"

    kept = _entry(scratch, "entry-independent")
    assert kept.status == "active"
    assert independent_parquet.exists()
    assert any(
        e["id"] == "entry-independent"
        for e in find_entries_sync("invoices", workspace_id=WS))


@pytest.mark.asyncio
async def test_replay_and_fresh_session_keep_the_tombstone(scratch):
    content = _csv("4444")
    doc_id = "doc_replay_lineage"
    _seed_document(scratch, doc_id=doc_id, file_name="Replay.csv",
                   content=content)
    entry = _materialize_upload(
        scratch, doc_id=doc_id, file_name="Replay.csv", content=content)
    operation_id = "document:delete:lineage-replay"

    first = await _delete(scratch, doc_id, operation_id=operation_id)
    assert first["status"] == "verified", first
    replay = await _delete(scratch, doc_id, operation_id=operation_id)
    assert replay["status"] == "already_applied", replay
    assert replay["data"]["verification"]["status"] == "already_applied"
    assert replay["data"]["verification"]["replay"] == "do_not_repeat"
    assert replay["data"]["effects"]["derived"] == "revoked"

    # A new session is the restart-like read: the durable tombstone still
    # keeps the derivative out of every resolution/search path.
    fresh = scratch["factory"]()
    try:
        assert (
            fresh.query(DatasetEntry)
            .filter(DatasetEntry.id == entry["id"])
            .one()
            .status
        ) == "removed"
    finally:
        fresh.close()
    assert find_entries_sync("replay", workspace_id=WS) == []
    assert resolve_dataset_entry_scoped_sync(
        entry["dataset_name"], workspace_id=WS)["state"] == "inactive"
    assert search_all_datasets_sync("4444", workspace_id=WS)["hits"] == []


@pytest.mark.asyncio
async def test_unprovable_derivative_effect_is_not_a_verified_delete(
        scratch, monkeypatch):
    content = _csv("5555")
    doc_id = "doc_partial_lineage"
    _seed_document(scratch, doc_id=doc_id, file_name="Partial.csv",
                   content=content)
    entry = _materialize_upload(
        scratch, doc_id=doc_id, file_name="Partial.csv", content=content)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("catalog unavailable")

    monkeypatch.setattr(
        "core.sheet_dataset_service.revoke_datasets_for_document", _boom)
    result = await _delete(scratch, doc_id)

    assert result["status"] == "committed_unverified", result
    assert result["verification"]["effect"] == "partial"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["data"]["effects"]["derived"] == "unavailable"
    assert result["data"]["complete"] is False
    # The catalog was not silently claimed clean; it remains observable so a
    # reconciliation can finish the invalidation.
    assert _entry(scratch, entry["id"]).status == "active"


@pytest.mark.asyncio
async def test_reuploading_a_removed_version_cannot_resurrect_catalog(scratch):
    content = _csv("6666")
    doc_id = "doc_reupload_lineage"
    _seed_document(scratch, doc_id=doc_id, file_name="Resurrect.csv",
                   content=content)
    entry = _materialize_upload(
        scratch, doc_id=doc_id, file_name="Resurrect.csv", content=content)
    assert (await _delete(scratch, doc_id))["status"] == "verified"

    again = materialize_sheet_bytes_sync(
        content, file_name="Resurrect.csv", source="upload",
        user_id=scratch["user"].id, workspace_id=WS, external_id=None,
        source_document_id=doc_id)
    assert again["status"] == "skipped"
    assert again["reason"] == "source_document_removed"
    assert find_entries_sync("resurrect", workspace_id=WS) == []
    assert _entry(scratch, entry["id"]).status == "removed"


def test_materialization_that_loses_its_source_mid_parse_is_revoked(
        scratch, monkeypatch):
    """The delete can race a background materialization; the post-commit
    tombstone re-check must revoke a copy born after the delete sweep."""
    import core.sheet_dataset_service as sds

    content = _csv("9999")
    doc_id = "doc_race_lineage"
    _seed_document(scratch, doc_id=doc_id, file_name="Race.csv",
                   content=content)

    calls = {"n": 0}
    real_probe = sds._source_document_revoked

    def _probe_then_removed(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return False  # source still fresh when the copy starts
        return True       # source tombstoned while the copy was written

    monkeypatch.setattr(sds, "_source_document_revoked",
                        _probe_then_removed)
    result = sds.materialize_sheet_bytes_sync(
        content, file_name="Race.csv", source="upload",
        user_id=scratch["user"].id, workspace_id=WS, external_id=None,
        source_document_id=doc_id)
    monkeypatch.setattr(sds, "_source_document_revoked", real_probe)

    assert result["status"] == "skipped"
    assert result["reason"] == "source_document_removed"
    assert find_entries_sync("race", workspace_id=WS) == []
    with scratch["factory"]() as fresh:
        row = fresh.query(DatasetEntry).filter(
            DatasetEntry.source_document_id == doc_id).one()
        assert row.status == "removed"
        assert not Path(row.parquet_path).exists()


def test_connector_derivative_gets_lineage_and_read_guard_blocks_removed_source(
        scratch):
    content = _csv("7777")
    source = "google_drive"
    external_id = "drive-file-77"
    derived_doc = source_document_id_for_source(source, external_id)
    assert derived_doc
    _seed_document(
        scratch, doc_id=derived_doc, file_name="Drive.csv", content=content,
        integration_id=source, external_id=external_id)

    result = materialize_sheet_bytes_sync(
        content, file_name="Drive.csv", source=source,
        user_id=scratch["user"].id, workspace_id=WS,
        external_id=external_id)
    assert result["status"] == "materialized", result
    entry = result["datasets"][0]
    assert entry["source_document_id"] == derived_doc
    assert read_sheet_row_sync(
        "Drive.csv", entry["entity_name"], 2, workspace_id=WS)["row"][
            "value"] == 7777

    # A freshness/upstream removal that did NOT run the catalog sweep: the
    # read guard must still refuse the derivative as current grounding.
    doc = scratch["db"].query(IngestedDocument).filter(
        IngestedDocument.id == derived_doc).one()
    doc.freshness_status = "removed"
    scratch["db"].commit()

    assert find_entries_sync("drive", workspace_id=WS) == []
    resolved = resolve_dataset_entry_scoped_sync(
        entry["dataset_name"], workspace_id=WS)
    assert resolved["state"] == "inactive"
    assert resolved.get("revoked") is True
    assert search_all_datasets_sync("7777", workspace_id=WS)["hits"] == []
    assert read_sheet_row_sync(
        "Drive.csv", entry["entity_name"], 2, workspace_id=WS) is None

    # The row itself is untouched (truthful catalog history), proving the
    # refusal came from lineage freshness, not a delete-time sweep.
    assert _entry(scratch, entry["id"]).status == "active"


@pytest.mark.asyncio
async def test_connector_delete_revokes_without_upload_byte_hash(scratch):
    content = _csv("8888")
    source = "onedrive"
    external_id = "item-88"
    derived_doc = source_document_id_for_source(source, external_id)
    _seed_document(
        scratch, doc_id=derived_doc, file_name="OneDrive.csv",
        content=content, integration_id=source, external_id=external_id)
    result = materialize_sheet_bytes_sync(
        content, file_name="OneDrive.csv", source=source,
        user_id=scratch["user"].id, workspace_id=WS,
        external_id=external_id)
    entry = result["datasets"][0]

    deleted = await _delete(scratch, derived_doc)
    assert deleted["status"] == "verified", deleted
    assert deleted["data"]["effects"]["derived"] == "revoked"
    row = _entry(scratch, entry["id"])
    assert row.status == "removed"
    assert not Path(row.parquet_path).exists()
