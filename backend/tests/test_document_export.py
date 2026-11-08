"""Stored-document export contract (NEXT03).

Mounted real Document Hub router over a scratch SQLite + real LanceDB store.
The only doubled leaf is EmbeddingService.generate_embedding (a deterministic
vector); parsing, upload, storage, SQL mirroring, auth/workspace resolution,
the strict revision matcher and response bytes are the production paths.
No model/provider/browser/live database is used.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.models  # noqa: F401 - register the model graph
import api.document_routes as dr
import api.document_ingestion_routes as di
from core.database import Base, get_db
from core.models import IngestedDocument, User
from core.lancedb_handler import LanceDBHandler


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _error_envelope(response):
    body = response.json()
    detail = body.get("detail", body)
    return detail.get("error", detail)


def _error_code(response):
    return _error_envelope(response)["code"]


@pytest.fixture()
def exported(tmp_path, monkeypatch):
    """Fresh workspace, real LanceDB handler, scratch SQLite session/client."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fastembed")
    from core.embedding_service import EmbeddingService

    async def _deterministic_embedding(self, text):
        return np.zeros(384, dtype=float).tolist()

    monkeypatch.setattr(
        EmbeddingService, "generate_embedding", _deterministic_embedding)

    workspace = f"ws-next03-{uuid.uuid4().hex[:8]}"
    handler = LanceDBHandler(workspace_id=workspace)
    monkeypatch.setattr(
        dr, "get_lancedb_handler", lambda ws=None: handler)
    monkeypatch.setattr(
        di, "get_lancedb_handler", lambda ws=None: handler)

    db_url = os.environ.get("DATABASE_URL")
    assert db_url, "bounded gate must supply a scratch DATABASE_URL"
    engine = create_engine(
        db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    user = User(
        id=f"next03-{uuid.uuid4().hex[:8]}",
        tenant_id="t1", workspace_id=workspace,
        email=f"next03-{uuid.uuid4().hex[:10]}@example.com", first_name="N", last_name="3",
        role="member", status="active", is_active=True)
    session.add(user)
    session.commit()

    app = FastAPI()
    app.include_router(dr.router)
    app.include_router(di.router)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[dr.get_current_user] = lambda: user
    app.dependency_overrides[di.get_current_user] = lambda: user
    client = TestClient(app)
    yield SimpleNamespace(
        client=client, handler=handler, workspace=workspace,
        session=session, user=user, engine=engine)
    session.close()
    engine.dispose()


def _upload(ctx, text: str, name: str = "next03.txt",
            content_type: str = "text/plain"):
    response = ctx.client.post(
        "/api/documents/upload",
        files={"file": (name, text.encode("utf-8"), content_type)})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("id"), body
    return body["id"]


def _read(ctx, doc_id: str) -> dict:
    response = ctx.client.get(f"/api/documents/{doc_id}")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _seed_vector(ctx, *, text: str, doc_id: str | None = None,
                 metadata: dict | None = None, source: str = "upload:seed.txt"):
    doc_id = doc_id or f"doc-{uuid.uuid4().hex[:16]}"
    meta = dict(metadata or {})
    ok = ctx.handler.add_document(
        table_name="documents",
        text=text,
        source=source,
        metadata=meta,
        user_id=ctx.user.id,
        workspace_id=ctx.workspace,
        doc_id=doc_id,
        extra_columns={"freshness_status": meta.get("freshness_status", "fresh")},
    )
    assert ok is True
    return doc_id


def _seed_sql(ctx, doc_id: str, *, version: str | None,
              freshness: str = "fresh", workspace: str | None = None,
              integration: str = "manual_upload",
              external_id: str | None = None,
              file_name: str = "seed.txt"):
    row = IngestedDocument(
        id=doc_id,
        workspace_id=workspace or ctx.workspace,
        tenant_id="t1",
        file_name=file_name,
        file_path=f"upload:{file_name}",
        file_type="txt",
        integration_id=integration,
        external_id=external_id or f"upload_{doc_id}",
        source_content_hash=version,
        freshness_status=freshness,
    )
    ctx.session.add(row)
    ctx.session.commit()
    return row


def test_export_requires_authentication():
    app = FastAPI()
    app.include_router(dr.router)
    client = TestClient(app)
    response = client.get("/api/documents/anything/export")
    assert response.status_code in (401, 403), response.text


@pytest.mark.parametrize("fmt", ["text", "markdown", "json"])
def test_normal_upload_open_export_matches_current_stored_content(exported, fmt):
    text = (
        f"NEXT03 normal upload ({fmt}).\n"
        "Unicode: café / 東京.\n"
        "This must be the same current stored content the reader sees.\n"
    )
    doc_id = _upload(exported, text)
    opened = _read(exported, doc_id)
    assert opened["id"] == doc_id
    assert opened["content"] == text

    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": fmt})
    assert response.status_code == 200, response.text

    if fmt in ("text", "markdown"):
        assert response.content.decode("utf-8") == opened["content"]
    else:
        body = json.loads(response.content)
        assert body["content"] == opened["content"]
        assert body["document_id"] == doc_id
        assert body["content_kind"] == "extracted_text"
        assert body["provenance_status"] == "authoritative"
        assert body["source_version_status"] == "matched"
        assert body["stored_text_sha256"] == _sha(opened["content"])
        assert "export_sha256" not in body
        assert "file_path" not in body
        assert "source_url" not in body

    headers = {k.lower(): v for k, v in response.headers.items()}
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["content-disposition"].startswith("attachment;")
    assert "inline" not in headers["content-disposition"].lower()
    assert headers["x-document-id"] == doc_id
    assert headers["x-document-content-kind"] == "extracted_text"
    assert headers["x-document-provenance"] == "authoritative"
    assert headers["x-document-stored-text-sha256"] == _sha(opened["content"])
    assert headers["x-document-export-sha256"] == hashlib.sha256(
        response.content).hexdigest()
    assert headers["x-document-source-version"]
    assert headers["x-document-source-version-status"] == "matched"
    assert headers["x-document-source-version-kind"] == "versioned"
    assert headers["x-document-source-version"] != (
        headers["x-document-stored-text-sha256"])
    if fmt == "json":
        assert headers["x-document-export-sha256"] != (
            headers["x-document-stored-text-sha256"])


def test_document_ingestion_upload_uses_opaque_revision_and_canonical_id(exported):
    text = '{"b": 2, "a": 1, "note": "Document-ingestion upload stores an opaque raw revision."}'
    response = exported.client.post(
        "/api/document-ingestion/upload",
        files={"file": ("ingested.json", text.encode("utf-8"), "application/json")},
    )
    assert response.status_code == 200, response.text
    doc_id = response.json()["data"]["document_id"]
    opened = _read(exported, doc_id)
    assert opened["content"] != text  # JSON extraction is normalized
    assert "Document-ingestion upload stores an opaque raw revision." in opened["content"]

    export = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "json"})
    assert export.status_code == 200, export.text
    body = json.loads(export.content)
    assert body["document_id"] == doc_id
    assert body["content"] == opened["content"]
    assert body["source_version_kind"] == "opaque"
    assert body["source_version_status"] == "matched"
    assert body["provenance_status"] == "authoritative"
    assert body["source_version"] != body["stored_text_sha256"]


def test_full_stored_content_over_model_reader_20k_is_not_truncated(exported):
    text = ("line-" + "x" * 80 + "\n") * 350
    assert len(text) > 20_000
    doc_id = _upload(exported, text)
    opened = _read(exported, doc_id)
    assert opened["content"] == text

    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == 200, response.text
    assert response.content.decode("utf-8") == text
    assert len(response.content) > 20_000
    body = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "json"})
    payload = json.loads(body.content)
    assert payload["content"] == text
    assert payload["stored_text_bytes"] == len(text.encode("utf-8"))


def test_non_txt_stored_document_exports_current_text(exported):
    text = "# Markdown source\n\nThis is not a TXT-only export.\n"
    doc_id = _upload(
        exported, text, name="next03-source.md",
        content_type="text/markdown")
    opened = _read(exported, doc_id)
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "markdown"})
    assert response.status_code == 200, response.text
    assert response.content.decode("utf-8") == opened["content"]


def test_manual_opaque_identity_matches_exactly(exported):
    text = "Manual opaque revision content.\n"
    doc_id = f"manual-{uuid.uuid4().hex[:12]}"
    version = "manual-opaque-v1"
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "manual.txt", "file_name": "manual.txt",
                  "source_content_hash": version,
                  "pg_document_id": doc_id},
        source="upload:manual.txt",
    )
    _seed_sql(exported, doc_id, version=version)
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "json"})
    assert response.status_code == 200, response.text
    body = json.loads(response.content)
    assert body["source_version"] == version
    assert body["source_version_kind"] == "opaque"
    assert body["source_version_status"] == "matched"
    assert body["provenance_status"] == "authoritative"


def test_vector_only_manual_legacy_is_explicit_snapshot_only(exported):
    text = "Genuine vector-only manual legacy text.\n"
    doc_id = _seed_vector(
        exported, text=text,
        metadata={"title": "legacy.txt", "file_name": "legacy.txt"},
        source="upload:legacy.txt",
    )
    assert exported.session.query(IngestedDocument).filter(
        IngestedDocument.id == doc_id).first() is None

    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "json"})
    assert response.status_code == 200, response.text
    body = json.loads(response.content)
    assert body["content"] == text
    assert body["provenance_status"] == "snapshot_only"
    assert body["source_version"] is None
    assert body["source_version_kind"] == "missing"
    assert body["source_version_status"] == "unknown"
    assert body["freshness_status"] is None
    headers = {k.lower(): v for k, v in response.headers.items()}
    assert headers["x-document-provenance"] == "snapshot_only"
    assert headers["x-document-source-version-status"] == "unknown"
    assert "x-document-source-version" not in headers


def test_manual_sql_row_with_missing_version_is_snapshot_only(exported):
    text = "Manual SQL row without a stored revision.\n"
    doc_id = f"manual-sql-{uuid.uuid4().hex[:12]}"
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "manual-sql.txt", "file_name": "manual-sql.txt"},
        source="upload:manual-sql.txt",
    )
    _seed_sql(exported, doc_id, version=None)
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "json"})
    assert response.status_code == 200, response.text
    body = json.loads(response.content)
    assert body["provenance_status"] == "snapshot_only"
    assert body["source_version"] is None
    assert body["source_version_status"] == "unknown"


def test_automated_sql_row_with_missing_version_refuses(exported):
    text = "Automated SQL row without a stored revision.\n"
    doc_id = f"auto-sql-{uuid.uuid4().hex[:12]}"
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "auto.txt", "file_name": "auto.txt"},
        source="gdrive:auto.txt",
    )
    _seed_sql(exported, doc_id, version=None, integration="google_drive")
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == 409, response.text
    assert _error_code(response) == "DOCUMENT_IDENTITY_UNVERIFIABLE"
    assert text not in response.text


def test_known_indexed_binding_without_sql_row_refuses(exported):
    text = "Known indexed binding without SQL row.\n"
    doc_id = f"indexed-{uuid.uuid4().hex[:12]}"
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "indexed.txt", "file_name": "indexed.txt",
                  "source_content_hash": "ev4:" + "a" * 64,
                  "pg_document_id": doc_id},
    )
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == 409, response.text
    assert _error_code(response) == (
        "DOCUMENT_IDENTITY_UNVERIFIABLE")
    assert text not in response.text


def test_known_indexed_binding_without_index_version_refuses(exported):
    text = "Known SQL binding without indexed version.\n"
    doc_id = f"sqlonly-{uuid.uuid4().hex[:12]}"
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "sqlonly.txt", "file_name": "sqlonly.txt",
                  "pg_document_id": doc_id},
    )
    _seed_sql(exported, doc_id, version="ev4:" + "b" * 64)
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == 409, response.text
    assert _error_code(response) == (
        "DOCUMENT_IDENTITY_UNVERIFIABLE")


def test_wrong_indexed_identity_refuses(exported):
    text = "Wrong indexed identity.\n"
    doc_id = f"wrongid-{uuid.uuid4().hex[:12]}"
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "wrongid.txt", "file_name": "wrongid.txt",
                  "source_content_hash": "ev4:" + "c" * 64,
                  "pg_document_id": "different-document"},
    )
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == 409, response.text
    assert _error_code(response) == "DOCUMENT_IDENTITY_MISMATCH"
    assert text not in response.text


def test_contradictory_versions_refuse(exported):
    text = "Contradictory versions.\n"
    doc_id = f"contradict-{uuid.uuid4().hex[:12]}"
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "contradict.txt", "file_name": "contradict.txt",
                  "source_content_hash": "ev4:" + "d" * 64,
                  "pg_document_id": doc_id},
    )
    _seed_sql(exported, doc_id, version="ev4:" + "e" * 64)
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "json"})
    assert response.status_code == 409, response.text
    assert _error_code(response) == "DOCUMENT_REVISION_INVALID"
    assert text not in response.text


def test_old_extractor_version_refuses(exported):
    text = "Old extractor version.\n"
    doc_id = f"oldext-{uuid.uuid4().hex[:12]}"
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "oldext.txt", "file_name": "oldext.txt",
                  "source_content_hash": "ev3:" + "f" * 64,
                  "pg_document_id": doc_id},
    )
    _seed_sql(exported, doc_id, version="ev3:" + "f" * 64)
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == 409, response.text
    assert _error_code(response) == "DOCUMENT_REVISION_INVALID"
    assert text not in response.text


@pytest.mark.parametrize("freshness,status,code", [
    ("stale", 409, "DOCUMENT_NOT_CURRENT"),
    ("outdated", 409, "DOCUMENT_NOT_CURRENT"),
    ("superseded", 409, "DOCUMENT_NOT_CURRENT"),
    ("removed", 404, "NOT_FOUND"),
])
def test_explicit_non_fresh_authority_refuses(exported, freshness, status, code):
    text = f"Non-fresh {freshness} content.\n"
    doc_id = f"fresh-{uuid.uuid4().hex[:12]}"
    version = "ev4:" + "a" * 64
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "fresh.txt", "file_name": "fresh.txt",
                  "source_content_hash": version,
                  "pg_document_id": doc_id},
    )
    _seed_sql(exported, doc_id, version=version, freshness=freshness)
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == status, response.text
    assert _error_code(response) == code
    assert text not in response.text


@pytest.mark.parametrize("freshness", ["", "unknown", "revoked", "pending"])
def test_unrecognized_or_revoked_freshness_is_never_authoritative(
        exported, freshness):
    """Only an explicit ``fresh`` SQL row can carry authoritative provenance.

    The old gate checked only NON_FRESH_STATUSES, so an empty/unknown/revoked
    status fell through as authoritative. These are distinct unknown states,
    not ``fresh`` and not a legacy snapshot: refuse before any body is made.
    """
    text = f"Unrecognized freshness {freshness!r} content.\n"
    doc_id = f"unknownfresh-{uuid.uuid4().hex[:12]}"
    version = "ev4:" + "a" * 64
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "unknown-fresh.txt", "file_name": "unknown-fresh.txt",
                  "source_content_hash": version,
                  "pg_document_id": doc_id},
        source="upload:unknown-fresh.txt",
    )
    _seed_sql(exported, doc_id, version=version, freshness=freshness)
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "json"})
    assert response.status_code == 409, response.text
    assert _error_code(response) == "DOCUMENT_NOT_CURRENT"
    assert text not in response.text


def test_foreign_workspace_and_unknown_document_are_not_found(exported):
    text = "Foreign workspace content.\n"
    doc_id = f"foreign-{uuid.uuid4().hex[:12]}"
    version = "ev4:" + "a" * 64
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "foreign.txt", "file_name": "foreign.txt",
                  "source_content_hash": version,
                  "pg_document_id": doc_id},
    )
    _seed_sql(exported, doc_id, version=version, workspace="other-workspace")
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == 404, response.text
    assert text not in response.text
    unknown = exported.client.get(
        f"/api/documents/unknown-next03/export", params={"format": "text"})
    assert unknown.status_code == 404, unknown.text


def test_empty_content_and_unsupported_formats_refuse(exported, monkeypatch):
    doc_id = _upload(exported, "placeholder content that will be emptied.")
    real_get = exported.handler.get_document_by_id

    def _empty_document(table_name, identity):
        doc = real_get(table_name, identity)
        if isinstance(doc, dict):
            doc = dict(doc)
            doc["text"] = ""
        return doc

    monkeypatch.setattr(exported.handler, "get_document_by_id",
                        _empty_document)
    empty = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert empty.status_code == 422, empty.text
    assert _error_code(empty) == "DOCUMENT_EMPTY"

    text = "Unsupported format content.\n"
    good_id = _upload(exported, text)
    for fmt in ("html", "pdf", "docx", "original", "binary"):
        response = exported.client.get(
            f"/api/documents/{good_id}/export", params={"format": fmt})
        assert response.status_code == 422, (fmt, response.text)
        assert _error_code(response) == (
            "UNSUPPORTED_EXPORT_FORMAT")
        assert "text" in _error_envelope(response).get("details", {}).get(
            "allowed_formats", [])


def test_client_path_url_and_original_parameters_refuse(exported):
    doc_id = _upload(exported, "Client authority must not be accepted.\n")
    for params in (
        {"format": "text", "path": "/etc/passwd"},
        {"format": "text", "url": "https://example.com/file"},
        {"format": "text", "file_path": "/etc/passwd"},
        {"format": "text", "locator": "remote"},
        {"format": "text", "download": "original"},
        {"format": "text", "original": "true"},
    ):
        response = exported.client.get(
            f"/api/documents/{doc_id}/export", params=params)
        assert response.status_code == 422, (params, response.text)
        assert _error_code(response) == "CLIENT_PATH_NOT_ALLOWED"


def test_unicode_and_header_injection_names_are_safe(exported):
    text = "Unicode filename content.\n"
    doc_id = f"name-{uuid.uuid4().hex[:12]}"
    version = "ev4:" + "a" * 64
    name = '../../etc/pa"ss\r\nX-Injected: yes 日本語.txt'
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": name, "file_name": name,
                  "source_content_hash": version,
                  "pg_document_id": doc_id},
        source="upload:name.txt",
    )
    _seed_sql(exported, doc_id, version=version, file_name=name)
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == 200, response.text
    values = [v for k, v in response.headers.items() if k.lower() == "x-injected"]
    assert values == []
    disposition = response.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    assert "filename*=" in disposition
    assert "../" not in disposition

    body = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "json"})
    assert body.status_code == 200, body.text
    payload = json.loads(body.content)
    assert "../" not in payload["file_name"]
    assert "../" not in payload["title"]
    assert "\r" not in payload["file_name"]
    assert "\n" not in payload["file_name"]


def test_source_version_header_is_not_injectable(exported):
    text = "Source-version header safety.\n"
    doc_id = f"vname-{uuid.uuid4().hex[:12]}"
    version = "opaque-rev\r\nX-Injected: yes"
    _seed_vector(
        exported, text=text, doc_id=doc_id,
        metadata={"title": "vname.txt", "file_name": "vname.txt",
                  "source_content_hash": version,
                  "pg_document_id": doc_id},
        source="upload:vname.txt",
    )
    _seed_sql(exported, doc_id, version=version)
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == 200, response.text
    assert not any(k.lower() == "x-injected" for k in response.headers)
    source_header = response.headers.get("x-document-source-version", "")
    assert "\r" not in source_header and "\n" not in source_header


def test_large_stored_text_refuses_without_truncation(exported):
    # 2 MiB is the explicit export bound; it is not the model 20k window.
    text = "x" * (2 * 1024 * 1024 + 1)
    doc_id = _seed_vector(
        exported, text=text, source="upload:large.txt",
        metadata={"title": "large.txt", "file_name": "large.txt"},
    )
    response = exported.client.get(
        f"/api/documents/{doc_id}/export", params={"format": "text"})
    assert response.status_code == 413, response.text
    assert _error_code(response) == "EXPORT_TOO_LARGE"
    assert len(response.content) < len(text)
