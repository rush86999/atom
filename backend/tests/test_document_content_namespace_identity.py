"""Scoped content identity for document upload/text ingest.

Root runtime at 01f72a136 showed two real workspaces uploading identical DOCX
content receive the same content-only id: the second upload returns 200 but
cannot export (404) and rewrites the first workspace's SQL metadata. The id
must be a digest of the trusted server scope + content, not content alone.

These twins cover:
- same-scope re-upload idempotency;
- two real workspace stores with identical bytes and preserved peer metadata;
- foreign read refusal;
- raw ``None`` vs literal ``"default"`` namespace identity;
- owned legacy id reuse vs foreign legacy preservation;
- an unbacked old vector failing closed on adoption;
- forged ingest-body identity/scope metadata being ignored.

Real ``/api/documents/upload``/``ingest`` routes, the existing export fixture,
the production workspace handler factory and scratch SQL are used. No model,
provider, browser or live database is called. Authored only; not executed here.
"""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import api.document_routes as routes
import core.lancedb_handler as storage
from core.auto_document_ingestion import DocumentParser
from core.models import IngestedDocument, User
from tests.test_document_export import exported, _read, _seed_sql, _seed_vector
from tests.test_root_document_parse_honesty import _docx_bytes


def _upload(ctx, payload, filename, content_type):
    return ctx.client.post(
        "/api/documents/upload",
        files={"file": (filename, payload, content_type)},
    )


def _docx_upload(ctx, payload, filename):
    return _upload(
        ctx, payload, filename,
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document",
    )


def _row_tuple(row):
    return (row.id, row.workspace_id, row.tenant_id, row.file_name,
            row.file_path, row.source_content_hash, row.freshness_status)


def test_same_scope_reupload_is_idempotent(exported, monkeypatch, tmp_path):
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    content = f"same-scope content {uuid.uuid4().hex}\n"

    first = _upload(exported, content.encode(), "first.txt", "text/plain")
    second = _upload(exported, content.encode(), "second.txt", "text/plain")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]

    exported.session.expire_all()
    rows = exported.session.query(IngestedDocument).filter(
        IngestedDocument.id == first.json()["id"]).all()
    assert len(rows) == 1
    assert rows[0].file_name == "second.txt"
    assert _read(exported, first.json()["id"])["content"] == content
    assert exported.client.get(
        f"/api/documents/{first.json()['id']}/export?format=text"
    ).status_code == 200


def test_identical_docx_two_real_workspaces_get_distinct_ids(
        exported, monkeypatch, tmp_path):
    """Root-observed collision, with real per-workspace physical stores."""
    monkeypatch.setattr(DocumentParser, "_docling_processor", False)
    monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path / "scoped-stores"))
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path / "office"))
    monkeypatch.setattr(storage, "_workspace_handlers", {})
    monkeypatch.setattr(
        routes, "get_lancedb_handler", storage.get_lancedb_handler)

    user_a = exported.user
    user_b = User(
        id="ns-peer-" + uuid.uuid4().hex,
        email="ns-peer-" + uuid.uuid4().hex + "@example.invalid",
        first_name="Peer", last_name="Team", role="member",
        status="active", is_active=True, tenant_id=user_a.tenant_id,
        workspace_id="ns-peer-workspace-" + uuid.uuid4().hex,
    )
    exported.session.add(user_b)
    exported.session.commit()

    content = "Identical DOCX bytes " + uuid.uuid4().hex
    payload = _docx_bytes(content)

    first = _docx_upload(exported, payload, "workspace-a.docx")
    assert first.status_code == 200, first.text
    a_id = first.json()["id"]

    exported.session.expire_all()
    a_row = exported.session.get(IngestedDocument, a_id)
    a_before = _row_tuple(a_row)

    exported.client.app.dependency_overrides[routes.get_current_user] = (
        lambda: user_b)
    second = _docx_upload(exported, payload, "workspace-b.docx")
    assert second.status_code == 200, second.text
    b_id = second.json()["id"]

    b_export = exported.client.get(
        f"/api/documents/{b_id}/export?format=text")
    assert b_export.status_code == 200, b_export.text
    assert content in b_export.text
    assert b_export.headers["X-Document-Provenance"] == "authoritative"

    exported.session.expire_all()
    a_after = _row_tuple(exported.session.get(IngestedDocument, a_id))
    assert a_id != b_id
    assert a_before == a_after
    b_row = exported.session.get(IngestedDocument, b_id)
    assert b_row is not None
    assert b_row.workspace_id == user_b.workspace_id

    assert storage.get_lancedb_handler(user_a.workspace_id).db_path != (
        storage.get_lancedb_handler(user_b.workspace_id).db_path)

    # Foreign workspace reads fail closed, both directions.
    assert exported.client.get(f"/api/documents/{a_id}").status_code == 404
    assert exported.client.get(
        f"/api/documents/{a_id}/export?format=text").status_code == 404

    exported.client.app.dependency_overrides[routes.get_current_user] = (
        lambda: user_a)
    assert exported.client.get(
        f"/api/documents/{a_id}/export?format=text").status_code == 200
    assert exported.client.get(f"/api/documents/{b_id}").status_code == 404


def test_raw_none_and_default_namespace_are_distinct_identities():
    """JSON canonicalization preserves raw None; it does not case/normalize."""
    content = "namespace distinction"
    assert routes._content_doc_key(content, None, None) != (
        routes._content_doc_key(content, "default", None))
    assert routes._content_doc_key(content, None, None) != (
        routes._content_doc_key(content, None, "default"))
    assert routes._content_doc_key(content, "default", "default") != (
        routes._content_doc_key(content, "Default", "default"))
    # Existing Personal-Edition ownership policy still treats a missing
    # workspace as the stored "default" workspace.
    assert routes._document_row_scope_matches(
        SimpleNamespace(workspace_id="default", tenant_id=None), None, None)


def test_owned_legacy_id_is_reused(exported, monkeypatch, tmp_path):
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    content = f"owned legacy {uuid.uuid4().hex}\n"
    legacy_id = routes._legacy_content_doc_key(content)
    _seed_sql(exported, legacy_id, version=None, file_name="seed.txt")

    response = _upload(
        exported, content.encode(), "owned-now.txt", "text/plain")
    assert response.status_code == 200, response.text
    assert response.json()["id"] == legacy_id

    exported.session.expire_all()
    row = exported.session.get(IngestedDocument, legacy_id)
    assert row.file_name == "owned-now.txt"
    assert row.workspace_id == exported.workspace
    scoped_id = routes._content_doc_key(
        content, exported.workspace, exported.user.tenant_id)
    assert exported.session.get(IngestedDocument, scoped_id) is None
    assert exported.client.get(
        f"/api/documents/{legacy_id}/export?format=text").status_code == 200


def test_foreign_legacy_row_is_preserved_and_not_adopted(
        exported, monkeypatch, tmp_path):
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    content = f"foreign legacy {uuid.uuid4().hex}\n"
    legacy_id = routes._legacy_content_doc_key(content)
    foreign = _seed_sql(
        exported, legacy_id, version=None, file_name="foreign-seed.txt",
        workspace="foreign-workspace-" + uuid.uuid4().hex)
    before = _row_tuple(foreign)

    response = _upload(
        exported, content.encode(), "current.txt", "text/plain")
    assert response.status_code == 200, response.text
    new_id = response.json()["id"]
    assert new_id != legacy_id
    assert new_id == routes._content_doc_key(
        content, exported.workspace, exported.user.tenant_id)

    exported.session.expire_all()
    foreign_after = _row_tuple(exported.session.get(IngestedDocument, legacy_id))
    assert foreign_after == before
    assert exported.session.get(IngestedDocument, new_id) is not None
    assert _read(exported, new_id)["content"] == content
    export = exported.client.get(
        f"/api/documents/{new_id}/export?format=text")
    assert export.status_code == 200, export.text
    assert export.headers["X-Document-Provenance"] == "authoritative"


def test_unbacked_legacy_vector_is_not_adopted(exported, monkeypatch, tmp_path):
    """Without an authoritative SQL owner, an old id cannot prove scope."""
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path))
    content = f"unbacked legacy vector {uuid.uuid4().hex}\n"
    legacy_id = routes._legacy_content_doc_key(content)
    _seed_vector(
        exported, text=content, doc_id=legacy_id,
        metadata={"title": "old.txt", "file_name": "old.txt"},
        source="upload:old.txt",
    )
    assert exported.session.query(IngestedDocument).filter(
        IngestedDocument.id == legacy_id).first() is None

    response = _upload(
        exported, content.encode(), "new.txt", "text/plain")
    assert response.status_code == 200, response.text
    new_id = response.json()["id"]
    assert new_id != legacy_id
    # Historical bytes remain readable; only adoption of the unproven id is
    # refused.
    assert _read(exported, legacy_id)["content"] == content
    assert _read(exported, new_id)["content"] == content


def test_forged_ingest_metadata_cannot_override_trusted_scope(exported):
    content = f"forged metadata {uuid.uuid4().hex}\n"
    forged_id = "forged-" + uuid.uuid4().hex
    response = exported.client.post("/api/documents/ingest", json={
        "content": content,
        "type": "text",
        "title": "Forged",
        "metadata": {
            "doc_id": forged_id,
            "pg_document_id": forged_id,
            "source_content_hash": "ev4:" + "a" * 64,
            "workspace_id": "foreign-workspace",
            "tenant_id": "foreign-tenant",
            "custom_note": "kept",
        },
    })
    assert response.status_code == 200, response.text
    expected_id = routes._content_doc_key(
        content, exported.workspace, exported.user.tenant_id)
    assert response.json()["id"] == expected_id
    assert expected_id != forged_id

    opened = _read(exported, expected_id)
    metadata = opened["metadata"]
    assert metadata["custom_note"] == "kept"
    for key in ("pg_document_id", "workspace_id", "tenant_id", "doc_id"):
        assert metadata.get(key) != forged_id
    assert metadata.get("pg_document_id") is None

    # A body-supplied PG binding must not make a text-only row authoritative.
    export = exported.client.get(
        f"/api/documents/{expected_id}/export?format=json")
    if export.status_code == 200:
        payload = json.loads(export.content)
        assert payload["provenance_status"] != "authoritative"
        assert payload["source_version_status"] != "matched"
