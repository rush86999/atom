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
* read-time withholding — never "fresh" — when the authoritative document
  state is UNREADABLE (including a genuinely missing authority table/schema,
  which is never a successful empty query), while genuinely
  unlinked/independent artifacts stay served and a genuinely ABSENT document
  row (query succeeded, no row) keeps legacy compatibility;
* exactness under negative twins: foreign workspace/scope, two files sharing a
  filename, unrelated/independently-saved artifacts, and identical bytes that
  belong to a different source or document;
* duplicate-operation replay and a fresh (restart-like) session;
* honest partial/unknown reporting when the derivative sweep cannot complete.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
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
    catalog_has_entries_sync,
    current_dataset_version,
    find_all_occurrences_sync,
    find_entries_sync,
    materialize_sheet_bytes_sync,
    read_sheet_row_sync,
    render_find_all_result,
    resolve_dataset_entry_scoped_sync,
    revoke_datasets_for_document,
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


class _UnreadableAuthoritySession:
    """Real scratch session whose authoritative document read fails.

    Models a transient unreadable state of ``ingested_documents`` (lock,
    migration, connection loss): the catalog itself still answers, so the
    distinction between "no such document" and "could not read the document
    table" is exercised end-to-end through the real service functions.
    """

    def __init__(self, inner):
        self._inner = inner

    def query(self, model, *args, **kwargs):
        if model is IngestedDocument:
            raise RuntimeError("authoritative document table unavailable")
        return self._inner.query(model, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _make_authority_unreadable(scratch, monkeypatch):
    """Route every catalog session through an unreadable-document proxy."""
    from contextlib import contextmanager

    factory = scratch["factory"]

    @contextmanager
    def _session():
        inner = factory()
        try:
            yield _UnreadableAuthoritySession(inner)
        finally:
            inner.close()

    monkeypatch.setattr("core.database.get_db_session", _session)


@contextmanager
def _catalog_without_authority_table(scratch, monkeypatch):
    """A REAL scratch catalog whose ``ingested_documents`` table is absent.

    ``dataset_entries`` exists and answers normally; querying the authoritative
    document model raises the dialect's genuine "no such table:
    ingested_documents" error. This is a missing-schema twin, not a stubbed
    product branch: the service is driven unmodified.
    """
    engine = create_engine(
        f"sqlite:///{Path(scratch['tmp_path']) / 'catalog-only.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine, tables=[DatasetEntry.__table__])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("core.database.get_db_session", factory)
    db = factory()
    try:
        yield db, factory
    finally:
        db.close()
        engine.dispose()


def _write_test_parquet(scratch, name: str, payload: dict) -> Path:
    root = Path(scratch["tmp_path"]) / "data" / "sheet_datasets"
    root.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    path = root / f"{name}.parquet"
    pd.DataFrame(payload).to_parquet(path, index=False)
    return path


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


def _add_independent_entry(scratch, *, entry_id: str = "entry-independent"):
    """An independently saved app-records artifact: no source document."""
    root = Path(scratch["tmp_path"]) / "data" / "sheet_datasets"
    root.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    parquet = root / f"{entry_id}.parquet"
    pd.DataFrame({"invoice": ["INV-1"], "total": [42]}).to_parquet(
        parquet, index=False)
    row = DatasetEntry(
        id=entry_id,
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
        parquet_path=str(parquet),
        row_count=1,
        column_count=2,
        columns_json={"columns": [{"name": "invoice"}, {"name": "total"}]},
        status="active",
    )
    scratch["db"].add(row)
    scratch["db"].commit()
    return row, parquet


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

    independent, independent_parquet = _add_independent_entry(scratch)

    result = await _delete(scratch, doc_id)
    assert result["status"] == "verified", result
    assert _entry(scratch, source_entry["id"]).status == "removed"

    kept = _entry(scratch, independent.id)
    assert kept.status == "active"
    assert independent_parquet.exists()
    assert any(
        e["id"] == independent.id
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
    real_probe = sds._source_document_authority

    def _probe_then_removed(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return sds._LINEAGE_LIVE   # source still fresh when the copy starts
        return sds._LINEAGE_NON_FRESH  # source tombstoned while copy was written

    monkeypatch.setattr(sds, "_source_document_authority",
                        _probe_then_removed)
    result = sds.materialize_sheet_bytes_sync(
        content, file_name="Race.csv", source="upload",
        user_id=scratch["user"].id, workspace_id=WS, external_id=None,
        source_document_id=doc_id)
    monkeypatch.setattr(sds, "_source_document_authority", real_probe)

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


def test_unreadable_authority_withholds_linked_rows_but_keeps_independent(
        scratch, monkeypatch):
    """A failed authority read is UNKNOWN, not freshness: linked derivatives
    disappear from every current-grounding path while unlinked artifacts stay.
    """
    content = _csv("9241")
    doc_id = "doc_unreadable_authority"
    _seed_document(scratch, doc_id=doc_id, file_name="Orchid.csv",
                   content=content)
    entry = _materialize_upload(
        scratch, doc_id=doc_id, file_name="Orchid.csv", content=content)
    parquet = Path(entry["parquet_path"])

    # Durable truth: the source was removed. Then the authoritative read of
    # that truth fails (lock/migration/connection loss) — the dangerous state.
    doc = scratch["db"].query(IngestedDocument).filter(
        IngestedDocument.id == doc_id).one()
    doc.freshness_status = "removed"
    scratch["db"].commit()
    independent, independent_parquet = _add_independent_entry(scratch)

    _make_authority_unreadable(scratch, monkeypatch)

    served = [e["id"] for e in find_entries_sync("", workspace_id=WS)]
    assert entry["id"] not in served
    assert served == [independent.id]

    resolved = resolve_dataset_entry_scoped_sync(
        entry["dataset_name"], workspace_id=WS)
    assert resolved["state"] == "unavailable", resolved
    assert resolved["reason"] == "source_authority_unavailable"
    assert resolved["revoked"] is False

    assert read_sheet_row_sync(
        "Orchid.csv", entry["entity_name"], 2, workspace_id=WS) is None
    probe = search_all_datasets_sync("9241", workspace_id=WS)
    assert probe["hits"] == []
    assert all(hit.get("file_name") != "Orchid.csv"
               for hit in probe["hits"])
    # The withheld linked row makes the probe nonexhaustive: it must never be
    # rendered as a complete catalog sweep (local absence claims depend on it).
    assert probe["incomplete"] is True
    assert probe["authority_withheld"] == 1

    block = render_find_all_result(
        find_all_occurrences_sync("9241", workspace_id=WS))
    assert "INCOMPLETE scan (source authority unavailable for 1" in block
    from core.absence_guard import uncovered_absence_claims

    assert uncovered_absence_claims(
        "No spreadsheet cell contains 9241.", block), block

    assert current_dataset_version(entry["external_id"], WS) is None
    # The independent row is enough to keep the catalog lane available.
    assert catalog_has_entries_sync() is True

    # Read-time withholding never rewrites the catalog: the row stays
    # truthful history and the on-disk copy is untouched.
    assert _entry(scratch, entry["id"]).status == "active"
    assert parquet.exists()
    assert independent_parquet.exists()


def test_unreadable_authority_blocks_materialization_but_absence_stays_legacy(
        scratch, monkeypatch):
    content = _csv("9250")
    doc_id = "doc_blocked_authority"
    _seed_document(scratch, doc_id=doc_id, file_name="Blocked.csv",
                   content=content)
    doc = scratch["db"].query(IngestedDocument).filter(
        IngestedDocument.id == doc_id).one()
    doc.freshness_status = "removed"
    scratch["db"].commit()

    with monkeypatch.context() as scoped:
        _make_authority_unreadable(scratch, scoped)
        blocked = materialize_sheet_bytes_sync(
            _csv("9251"), file_name="Reborn.csv", source="upload",
            user_id=scratch["user"].id, workspace_id=WS, external_id=None,
            source_document_id=doc_id)
    assert blocked["status"] == "skipped", blocked
    assert blocked["reason"] == "source_authority_unavailable"
    assert scratch["db"].query(DatasetEntry).filter(
        DatasetEntry.file_name == "Reborn.csv").count() == 0

    # GENUINE ABSENCE is not a read failure: upload ingestion materializes
    # before its document row exists, so the legacy ordering must still work.
    legacy_content = _csv("9252")
    legacy = materialize_sheet_bytes_sync(
        legacy_content, file_name="Absent.csv", source="upload",
        user_id=scratch["user"].id, workspace_id=WS, external_id=None,
        source_document_id="doc_absent_not_a_failure")
    assert legacy["status"] == "materialized", legacy
    assert [e["id"] for e in find_entries_sync(
        "absent", workspace_id=WS)] == [legacy["datasets"][0]["id"]]

    # Positive twin: a provably fresh source still materializes.
    fresh_content = _csv("9253")
    _seed_document(scratch, doc_id="doc_fresh_twin", file_name="Fresh.csv",
                   content=fresh_content)
    fresh = materialize_sheet_bytes_sync(
        fresh_content, file_name="Fresh.csv", source="upload",
        user_id=scratch["user"].id, workspace_id=WS, external_id=None,
        source_document_id="doc_fresh_twin")
    assert fresh["status"] == "materialized", fresh


def test_missing_authority_table_is_unknown_not_a_successful_absence(
        scratch, monkeypatch):
    """A genuinely absent ``ingested_documents`` table proves NOTHING.

    Real scratch schema: ``dataset_entries`` answers, the authoritative
    document table does not exist. The failed query is UNKNOWN — source-linked
    rows must be withheld, never served as if a successful empty query had
    proven there is no tombstone. The independent unlinked row is unaffected.
    """
    content = _csv("9310")
    digest = hashlib.sha1(content).hexdigest()
    linked_parquet = _write_test_parquet(
        scratch, "missing-schema-linked", {"value": [9310]})
    independent_parquet = _write_test_parquet(
        scratch, "missing-schema-independent", {"invoice": ["INV-9"]})

    with _catalog_without_authority_table(scratch, monkeypatch) as (db, _):
        from sqlalchemy.exc import OperationalError

        # The negative twin's premise: this is a REAL missing-table failure,
        # not an empty successful query.
        with pytest.raises(OperationalError) as missing:
            db.query(IngestedDocument).all()
        assert "ingested_documents" in str(missing.value)

        db.add(DatasetEntry(
            id="entry-missing-schema-linked",
            workspace_id=WS,
            tenant_id=TENANT,
            created_by=scratch["user"].id,
            source_kind="file",
            source="upload",
            external_id=f"sha1:{digest}",
            source_document_id="doc_missing_schema_twin",
            file_name="MissingSchema.csv",
            content_hash=digest,
            entity_name="Sheet",
            dataset_name="upload_missing_schema__sheet",
            parquet_path=str(linked_parquet),
            row_count=1,
            column_count=1,
            columns_json={"columns": [{"name": "value"}]},
            status="active",
        ))
        db.add(DatasetEntry(
            id="entry-missing-schema-independent",
            workspace_id=WS,
            tenant_id=TENANT,
            created_by=scratch["user"].id,
            source_kind="app_records",
            source="zoho_books",
            external_id="invoices",
            file_name="Invoices (synced)",
            content_hash="b" * 40,
            entity_name="invoices",
            dataset_name="zoho_books_invoices",
            parquet_path=str(independent_parquet),
            row_count=1,
            column_count=1,
            columns_json={"columns": [{"name": "invoice"}]},
            status="active",
        ))
        db.commit()

        # Negative twin: every current-grounding path withholds the linked row.
        served = [e["id"] for e in find_entries_sync("", workspace_id=WS)]
        assert served == ["entry-missing-schema-independent"]
        resolved = resolve_dataset_entry_scoped_sync(
            "upload_missing_schema__sheet", workspace_id=WS)
        assert resolved["state"] == "unavailable", resolved
        assert resolved["reason"] == "source_authority_unavailable"
        assert resolved["revoked"] is False
        assert read_sheet_row_sync(
            "MissingSchema.csv", "Sheet", 2, workspace_id=WS) is None
        probe = search_all_datasets_sync("9310", workspace_id=WS)
        assert probe["hits"] == []
        assert probe["incomplete"] is True
        assert probe["authority_withheld"] == 1
        assert current_dataset_version(f"sha1:{digest}", WS) is None

        # Positive twin: the truly unlinked row never depended on document
        # authority, so a missing authority schema does not hide it.
        assert catalog_has_entries_sync() is True
        assert any(
            e["id"] == "entry-missing-schema-independent"
            for e in find_entries_sync("invoices", workspace_id=WS))

        # Withholding is a read-time verdict; the catalog stays truthful.
        db.expire_all()
        assert db.get(
            DatasetEntry, "entry-missing-schema-linked").status == "active"


def test_missing_authority_table_blocks_source_linked_materialization(
        scratch, monkeypatch):
    """Materialization must not fail OPEN on a missing authority schema.

    A source-linked copy whose owning-document table cannot be read is not
    provably fresh, so nothing is written. A truly unlinked file still
    materializes — the guard covers provenance, not every file.
    """
    with _catalog_without_authority_table(scratch, monkeypatch) as (db, _):
        blocked = materialize_sheet_bytes_sync(
            _csv("9311"), file_name="NoSchema.csv", source="upload",
            user_id=scratch["user"].id, workspace_id=WS, external_id=None,
            source_document_id="doc_missing_schema_blocked")
        assert blocked["status"] == "skipped", blocked
        assert blocked["reason"] == "source_authority_unavailable"
        assert db.query(DatasetEntry).count() == 0
        assert list(
            (Path(scratch["tmp_path"]) / "data" / "sheet_datasets")
            .glob("**/*.parquet")) == []

        # Independent positive twin: no lineage, no authority dependency.
        allowed = materialize_sheet_bytes_sync(
            _csv("9312"), file_name="NoLineage.csv", source="local_export",
            user_id=scratch["user"].id, workspace_id=WS, external_id=None)
        assert allowed["status"] == "materialized", allowed
        assert allowed["datasets"][0]["source_document_id"] is None
        assert [e["id"] for e in find_entries_sync(
            "nolineage", workspace_id=WS)] == [allowed["datasets"][0]["id"]]


def test_successful_empty_authority_table_is_true_absence(scratch):
    """The contrast twin: a real query that succeeds with NO row is absence.

    ``ingested_documents`` exists and answers; nothing is stored for this doc
    id (the legacy ordering where a copy is materialized before its document
    row). That genuine absence stays compatible — unlike a missing table,
    which is UNKNOWN and withheld.
    """
    content = _csv("9313")
    doc_id = "doc_empty_authority_successful"
    assert scratch["db"].query(IngestedDocument).filter(
        IngestedDocument.id == doc_id).first() is None

    entry = _materialize_upload(
        scratch, doc_id=doc_id, file_name="EmptyAuthority.csv",
        content=content)
    assert entry["source_document_id"] == doc_id
    assert [e["id"] for e in find_entries_sync(
        "emptyauthority", workspace_id=WS)] == [entry["id"]]
    assert read_sheet_row_sync(
        "EmptyAuthority.csv", entry["entity_name"], 2,
        workspace_id=WS)["row"]["value"] == 9313
    assert current_dataset_version(
        entry["external_id"], WS) == entry["content_hash"]


def test_post_commit_unknown_authority_withdraws_new_rows(
        scratch, monkeypatch):
    import core.sheet_dataset_service as sds

    content = _csv("9260")
    doc_id = "doc_postcommit_unknown"
    _seed_document(scratch, doc_id=doc_id, file_name="Postcommit.csv",
                   content=content)

    calls = {"n": 0}

    def _live_then_unknown(*_args, **_kwargs):
        calls["n"] += 1
        return (sds._LINEAGE_LIVE if calls["n"] == 1
                else sds._LINEAGE_UNKNOWN)

    monkeypatch.setattr(sds, "_source_document_authority",
                        _live_then_unknown)
    result = sds.materialize_sheet_bytes_sync(
        content, file_name="Postcommit.csv", source="upload",
        user_id=scratch["user"].id, workspace_id=WS, external_id=None,
        source_document_id=doc_id)

    assert result["status"] == "skipped", result
    assert result["reason"] == "source_authority_unavailable"
    assert result["discarded"] == 1
    assert result["datasets"] == []
    with scratch["factory"]() as fresh:
        assert fresh.query(DatasetEntry).filter(
            DatasetEntry.source_document_id == doc_id).count() == 0
    assert list(
        (Path(scratch["tmp_path"]) / "data" / "sheet_datasets")
        .glob("**/*.parquet")) == []
    assert find_entries_sync("postcommit", workspace_id=WS) == []


def test_linked_row_with_foreign_scope_document_is_withheld(scratch):
    """A same-id document in another workspace cannot attest freshness."""
    content = _csv("9280")
    doc_id = "doc_scope_unknown"
    _seed_document(scratch, doc_id=doc_id, workspace_id=PEER_WS,
                   file_name="Scoped.csv", content=content)

    root = Path(scratch["tmp_path"]) / "data" / "sheet_datasets"
    root.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    parquet = root / "scoped.parquet"
    pd.DataFrame({"value": [9280]}).to_parquet(parquet, index=False)
    scratch["db"].add(DatasetEntry(
        id="entry-scope-unknown",
        workspace_id=WS,
        tenant_id=TENANT,
        created_by=scratch["user"].id,
        source_kind="file",
        source="upload",
        external_id="sha1:" + hashlib.sha1(content).hexdigest(),
        source_document_id=doc_id,
        file_name="Scoped.csv",
        content_hash=hashlib.sha1(content).hexdigest(),
        entity_name="Scoped",
        dataset_name="upload_scoped__scoped",
        parquet_path=str(parquet),
        row_count=1,
        column_count=1,
        columns_json={"columns": [{"name": "value"}]},
        status="active",
    ))
    scratch["db"].commit()

    assert find_entries_sync("scoped", workspace_id=WS) == []
    resolved = resolve_dataset_entry_scoped_sync(
        "upload_scoped__scoped", workspace_id=WS)
    assert resolved["state"] == "unavailable", resolved
    assert resolved["revoked"] is False


def test_byte_hash_revocation_spares_other_sources_and_linked_rows(scratch):
    """Identical bytes are not one identity: only upload copies without an
    independent document are content-addressed by the source byte hash."""
    content = _csv("9270")
    digest = hashlib.sha1(content).hexdigest()
    owner_doc = "doc_hash_owner"
    peer_doc = "doc_hash_peer"
    _seed_document(scratch, doc_id=owner_doc, file_name="Owner.csv",
                   content=content)
    _seed_document(scratch, doc_id=peer_doc, file_name="Peer.csv",
                   content=content, integration_id="google_drive",
                   external_id="drive-peer")

    owner = _materialize_upload(
        scratch, doc_id=owner_doc, file_name="Owner.csv", content=content)
    # A connector copy with no stable source id is content-addressed exactly
    # like an upload but is another source, linked to its own document.
    peer = materialize_sheet_bytes_sync(
        content, file_name="Peer.csv", source="google_drive",
        user_id=scratch["user"].id, workspace_id=WS, external_id=None,
        source_document_id=peer_doc)
    peer_entry = peer["datasets"][0]
    assert peer_entry["content_hash"] == owner["content_hash"] == digest

    # A legacy upload copy predating lineage stamps: same bytes, no owner.
    root = Path(scratch["tmp_path"]) / "data" / "sheet_datasets"
    root.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    legacy_parquet = root / "legacy-hash.parquet"
    pd.DataFrame({"value": [9270]}).to_parquet(legacy_parquet, index=False)
    scratch["db"].add(DatasetEntry(
        id="entry-legacy-hash",
        workspace_id=WS,
        tenant_id=TENANT,
        created_by=scratch["user"].id,
        source_kind="file",
        source="upload",
        external_id=f"sha1:{digest}",
        source_document_id=None,
        file_name="Legacy.csv",
        content_hash=digest,
        entity_name="Legacy",
        dataset_name="upload_legacy__legacy",
        parquet_path=str(legacy_parquet),
        row_count=1,
        column_count=1,
        columns_json={"columns": [{"name": "value"}]},
        status="active",
    ))
    scratch["db"].commit()

    upload_path = (
        Path(scratch["tmp_path"]) / "office" / "uploads" / f"{owner_doc}.csv")
    effect = revoke_datasets_for_document(
        scratch["db"], doc_id=owner_doc, workspace_id=WS,
        materialized_path=str(upload_path))

    assert effect["state"] == "revoked", effect
    assert effect["content_hash_matched"] is True
    # Owner + the unlinked legacy copy are the two proven revocations.
    assert effect["matched"] == 2, effect
    assert _entry(scratch, owner["id"]).status == "removed"
    assert _entry(scratch, "entry-legacy-hash").status == "removed"
    assert not legacy_parquet.exists()

    kept = _entry(scratch, peer_entry["id"])
    assert kept.status == "active"
    assert Path(kept.parquet_path).exists()
