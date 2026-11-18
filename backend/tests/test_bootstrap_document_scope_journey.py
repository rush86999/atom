"""Bootstrap administrator upload -> documents.search scope journey.

Reproduced on merged ``160621dfa``: the documented first-launch pilot account
``admin@example.com`` is created with NULL workspace/tenant scope. The document
upload routes hand ``None`` to ``get_lancedb_handler`` (the legacy *shared*
``default_shared`` store) while the RPC ``documents.search`` vector leg opens
the Personal ``default`` store. One upload therefore lands in one namespace and
every semantic search reads another.

These are synthetic, local-only tests (scratch SQLite/LanceDB, deterministic
embeddings, ordinary bearer auth). No model provider, browser, network, live
database or owner artifact is used.
"""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

import api.document_ingestion_routes as ingestion_routes
import api.document_routes as document_routes
import core.database as database
import core.lancedb_handler as storage
from core.auth import create_access_token
from core.database import Base
from core.models import IngestedDocument, Tenant, User, Workspace


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """Scratch auth/documents world with the real bootstrap admin account."""
    # --- storage + embedding isolation ---------------------------------
    monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path / "stores"))
    monkeypatch.setenv("ATOM_OFFICE_DIR", str(tmp_path / "office"))
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "true")
    monkeypatch.setenv("ATOM_BOOTSTRAP_PASSWORD_FILE", str(tmp_path / "pw"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fastembed")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    # This journey covers documents, not communications. The hybrid
    # conversations leg opens the shared comms store and initializes its own
    # SentenceTransformer, which on a cold CI agent downloads the model and
    # outlived the lane's 300s budget. The leg has its own tests
    # (tests/test_conversations_leg_and_vfs.py); keep this fixture hermetic.
    monkeypatch.setenv("MEMORY_CONVERSATIONS_LEG", "false")
    monkeypatch.setattr(storage, "_workspace_handlers", {})

    from core.embedding_service import EmbeddingService

    async def _deterministic_embedding(self, text):
        # Non-zero constant vector: cosine 1.0 for every text, so a vector
        # hit proves the *store* was read, not that a lexical coincidence
        # rescued the query.
        return [0.03125] * 384

    monkeypatch.setattr(
        EmbeddingService, "generate_embedding", _deterministic_embedding)

    # --- scratch SQL world ---------------------------------------------
    engine = create_engine(
        f"sqlite:///{tmp_path / 'scope-world.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", Session)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(document_routes, "get_lancedb_handler",
                        storage.get_lancedb_handler)
    monkeypatch.setattr(ingestion_routes, "get_lancedb_handler",
                        storage.get_lancedb_handler)

    # Real bootstrap path: ordinary first launch, ADMIN_PASSWORD supplied so
    # no password file is generated.
    monkeypatch.setenv("ADMIN_PASSWORD", "synthetic-bootstrap-password")
    from core.admin_bootstrap import ensure_admin_user

    ensure_admin_user()
    with Session() as db:
        admin = db.query(User).filter(
            User.email == "admin@example.com").one()
        assert admin.workspace_id is None
        assert admin.tenant_id is None

    app = FastAPI()
    app.include_router(document_routes.router)
    app.include_router(ingestion_routes.router)
    from api.rpc_routes import router as rpc_router

    app.include_router(rpc_router)
    client = TestClient(app)

    return SimpleNamespace(
        engine=engine, Session=Session, client=client, admin=admin,
        token=create_access_token({"sub": admin.id}, user=admin),
    )


def _auth(world, token=None):
    return {"Authorization": f"Bearer {token or world.token}"}


def _upload(world, content: str, filename: str = "pilot.txt",
            token: str | None = None):
    return world.client.post(
        "/api/documents/upload",
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
        headers=_auth(world, token),
    )


def _rpc_search(world, query: str, token: str | None = None):
    return world.client.post(
        "/api/rpc/documents.search",
        json={"params": {"query": query}},
        headers=_auth(world, token),
    )


def _add_member(world, workspace_id: str):
    tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
    user_id = f"member-{uuid.uuid4().hex[:8]}"
    with world.Session() as db:
        db.add(Tenant(id=tenant_id, name="Member tenant",
                      subdomain=f"member-{uuid.uuid4().hex[:8]}"))
        db.add(Workspace(id=workspace_id, name="Member workspace",
                         tenant_id=tenant_id))
        db.add(User(
            id=user_id, email=f"{user_id}@example.invalid",
            first_name="Member", last_name="User", role="member",
            status="active", is_active=True,
            tenant_id=tenant_id, workspace_id=workspace_id,
        ))
        db.commit()
        user = db.query(User).filter(User.id == user_id).one()
        return user, create_access_token({"sub": user_id}, user=user)


def _legacy_row(world, doc_id: str, *, content: str, owner_id: str,
                workspace_id: str = "default", tenant_id=None,
                freshness: str = "fresh",
                vector_freshness: str = "fresh",
                sql_revision: str | None = None,
                metadata_overrides: dict | None = None,
                metadata_drop: tuple = (),
                write_sql: bool = True):
    """Seed an already-written pre-fix upload in the legacy shared store.

    The shape mirrors an unmodified ``160621dfa`` upload exactly: content-only
    doc id, ``pg_document_id`` join key, extraction revision in metadata, the
    user stamp and a ``fresh`` freshness column on the vector row, plus the
    aligned SQL mirror row (workspace ``default``, raw NULL tenant for the
    bootstrap account).
    """
    from core.doc_freshness_service import extraction_content_hash

    revision = extraction_content_hash(content)
    metadata = {
        "title": "legacy.txt",
        "file_name": "legacy.txt",
        "file_type": "txt",
        "source": "upload",
        "source_type": "upload",
        "integration_id": "manual_upload",
        "doc_id": doc_id,
        "pg_document_id": doc_id,
        "source_content_hash": revision,
        # Real 160621dfa upload metadata has no workspace/tenant keys;
        # the physical namespace lives on the vector row.
        "author": "legacy@example.invalid",
    }
    if metadata_overrides:
        metadata.update(metadata_overrides)
    for key in metadata_drop:
        metadata.pop(key, None)
    handler = storage.get_lancedb_handler("default_shared")
    assert handler.add_document(
        table_name="documents",
        text=content,
        source="upload:legacy.txt",
        metadata=metadata,
        user_id=owner_id,
        workspace_id="default_shared",
        doc_id=doc_id,
        extra_columns={"freshness_status": vector_freshness},
    ) is True
    if not write_sql:
        return doc_id
    with world.Session() as db:
        db.add(IngestedDocument(
            id=doc_id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            file_name="legacy.txt",
            file_path="",
            file_type="txt",
            integration_id="manual_upload",
            external_id=f"upload_{doc_id}",
            content_preview=content[:500],
            source_content_hash=sql_revision or revision,
            freshness_status=freshness,
        ))
        db.commit()
    return doc_id


# ---------------------------------------------------------------------------
# Scope resolver
# ---------------------------------------------------------------------------


def test_bootstrap_owner_resolves_to_the_documented_personal_workspace(world):
    """Only the actual server-owned bootstrap account gets the Personal scope."""
    from core.personal_scope import is_bootstrap_identity

    with world.Session() as db:
        admin = db.query(User).filter(
            User.email == "admin@example.com").one()
        assert admin.workspace_id is None
        assert admin.tenant_id is None
        assert admin.id
        assert admin.role == "workspace_admin"
        assert is_bootstrap_identity(admin) is True
        assert document_routes._resolve_ws_id(admin) == "default"

    assert document_routes._resolve_ws_id(None) is None


def _forged_bootstrap(**overrides):
    """An unbound account shaped like the bootstrap row except where stated."""
    fields = dict(
        id=f"forged-{uuid.uuid4().hex[:8]}",
        email="admin@example.com",
        role="workspace_admin",
        tenant_id=None,
        workspace_id=None,
        workspaces=[],
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


@pytest.mark.parametrize(
    "forgery",
    [
        # Same bootstrap email, ordinary persisted role, no binding.
        pytest.param({"role": "member"}, id="same-email-ordinary-role"),
        # Right-looking row but no actual authenticated principal id.
        pytest.param({"id": ""}, id="blank-principal-id"),
        # Scope was written, so this is not the initializer's NULL row.
        pytest.param({"tenant_id": "tenant-forged"}, id="non-null-tenant"),
    ],
)
def test_bootstrap_fallback_requires_id_email_role_and_raw_null_scope(forgery):
    """Email alone is user-controllable and never grants the Personal store."""
    from fastapi import HTTPException

    from core.personal_scope import is_bootstrap_identity

    user = _forged_bootstrap(**forgery)
    assert is_bootstrap_identity(user) is False

    with pytest.raises(HTTPException) as exc:
        document_routes._resolve_ws_id(user)
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "DOCUMENT_SCOPE_UNAVAILABLE"


def test_unbound_ordinary_user_is_refused():
    """An unbound ordinary account is not the bootstrap identity."""
    from fastapi import HTTPException

    ordinary = SimpleNamespace(
        workspace_id=None, workspaces=[], email="member@example.invalid")

    with pytest.raises(HTTPException) as exc:
        document_routes._resolve_ws_id(ordinary)
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "DOCUMENT_SCOPE_UNAVAILABLE"


def test_workspace_lookup_failure_is_refused_not_guessed():
    """A resolution error fails closed; it never becomes a fallback scope."""
    from fastapi import HTTPException

    class _BrokenBinding:
        workspace_id = None
        email = "member@example.invalid"

        @property
        def workspaces(self):
            raise RuntimeError("binding store unavailable")

    with pytest.raises(HTTPException) as exc:
        document_routes._resolve_ws_id(_BrokenBinding())
    assert exc.value.status_code == 503
    assert exc.value.detail["error"]["code"] == (
        "DOCUMENT_SCOPE_RESOLUTION_FAILED")


def test_member_fk_and_relationship_precedence_is_unchanged():
    fk_user = SimpleNamespace(workspace_id="ws-fk", workspaces=[])
    rel_user = SimpleNamespace(
        workspace_id=None, workspaces=[SimpleNamespace(id="ws-rel")])

    assert document_routes._resolve_ws_id(fk_user) == "ws-fk"
    assert document_routes._resolve_ws_id(rel_user) == "ws-rel"


# ---------------------------------------------------------------------------
# Fresh bootstrap journey
# ---------------------------------------------------------------------------


def test_bootstrap_admin_upload_is_found_by_rpc_documents_search(world):
    content = (
        "The finance forecast estimates income for the coming period. "
        "Marker: ZEPHYR-42.\n"
    )
    upload = _upload(world, content)
    assert upload.status_code == 200, upload.text
    doc_id = upload.json()["id"]

    with world.Session() as db:
        row = db.get(IngestedDocument, doc_id)
        assert row is not None
        # Raw NULL tenant stays NULL; only workspace resolves.
        assert row.workspace_id == "default"
        assert row.tenant_id is None

    # Upload lands in the documented Personal store, not the shared one.
    assert storage.get_lancedb_handler("default").get_document_by_id(
        "documents", doc_id) is not None
    assert storage.get_lancedb_handler("default_shared").get_document_by_id(
        "documents", doc_id) is None

    # Paraphrase with no lexical overlap with the stored text: only the
    # vector leg can find it.
    response = _rpc_search(world, "quarterly revenue projection")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    data = body["data"]
    assert data["success"] is True, data
    assert data["status"] == "success", data
    assert data["stats"]["vector_hits"] >= 1, data
    assert data["legs"]["vector"]["status"] == "ok", data
    ids = [r["id"] for r in data["results"]]
    assert doc_id in ids, data
    hit = next(r for r in data["results"] if r["id"] == doc_id)
    assert hit["citation_path"] == (
        f"knowledge/documents/{doc_id}/content.lines")
    # The precise source text is available for citation.
    assert "ZEPHYR-42" in (hit.get("content") or "")


def test_ingestion_upload_surface_uses_the_same_personal_scope(world):
    content = f"ingestion-surface {uuid.uuid4().hex}\n"
    response = world.client.post(
        "/api/document-ingestion/upload",
        files={"file": ("ingested.txt", content.encode(), "text/plain")},
        headers=_auth(world),
    )
    assert response.status_code == 200, response.text
    doc_id = response.json()["data"]["document_id"]

    assert storage.get_lancedb_handler("default").get_document_by_id(
        "documents", doc_id) is not None
    assert storage.get_lancedb_handler("default_shared").get_document_by_id(
        "documents", doc_id) is None
    with world.Session() as db:
        row = db.get(IngestedDocument, doc_id)
        assert row.workspace_id == "default"
        assert row.tenant_id is None


# ---------------------------------------------------------------------------
# Already-written documents (upgrade compatibility)
# ---------------------------------------------------------------------------


def test_legacy_shared_upload_stays_listable_readable_and_exportable(world):
    content = (
        "Historical pilot notes: the archive code is HARBOR-77.\n"
    )
    doc_id = _legacy_row(
        world,
        document_routes._content_doc_key(content, None, None),
        content=content,
        owner_id=world.admin.id,
    )

    # Listing keeps the exact original id.
    listing = world.client.get("/api/documents", headers=_auth(world))
    assert listing.status_code == 200, listing.text
    body = listing.json()
    ids = {d["id"] for d in body["data"]}
    assert doc_id in ids, body
    assert body["metadata"]["total"] >= 1
    # Preview bodies are read only for the legacy rows actually served.
    served = next(d for d in body["data"] if d["id"] == doc_id)
    assert served["text_preview"].startswith("Historical pilot notes")

    # Exact-id read and export keep the original id and full text.
    opened = world.client.get(
        f"/api/documents/{doc_id}", headers=_auth(world))
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["content"] == content

    exported = world.client.get(
        f"/api/documents/{doc_id}/export?format=text", headers=_auth(world))
    assert exported.status_code == 200, exported.text
    assert exported.content.decode("utf-8") == content

    # Exact-term RPC retrieval still resolves the same durable document.
    search = _rpc_search(world, "HARBOR-77")
    assert search.status_code == 200, search.text
    results = search.json()["data"]["results"]
    assert doc_id in {r["id"] for r in results}, results
    hit = next(r for r in results if r["id"] == doc_id)
    assert hit["citation_path"] == (
        f"knowledge/documents/{doc_id}/content.lines")

    # A fresh process (handler cache cleared) reads the same doc back.
    storage._workspace_handlers.clear()
    again = world.client.get(
        f"/api/documents/{doc_id}", headers=_auth(world))
    assert again.status_code == 200, again.text
    assert again.json()["data"]["content"] == content


def test_legacy_and_current_documents_share_one_truthful_page(world):
    legacy_content = f"legacy page {uuid.uuid4().hex}\n"
    legacy_doc = _legacy_row(
        world,
        document_routes._content_doc_key(legacy_content, None, None),
        content=legacy_content,
        owner_id=world.admin.id,
    )
    current_content = f"current page {uuid.uuid4().hex}\n"
    current = _upload(world, current_content)
    assert current.status_code == 200, current.text
    current_doc = current.json()["id"]

    listing = world.client.get(
        "/api/documents", params={"limit": 100}, headers=_auth(world))
    assert listing.status_code == 200, listing.text
    body = listing.json()
    ids = [d["id"] for d in body["data"]]
    assert set(ids) == {legacy_doc, current_doc}, body
    assert body["metadata"]["total"] == 2
    assert body["metadata"]["count"] == 2
    assert body["metadata"]["has_more"] is False

    first = world.client.get(
        "/api/documents", params={"limit": 1}, headers=_auth(world)).json()
    assert first["metadata"]["total"] == 2
    assert first["metadata"]["count"] == 1
    assert first["metadata"]["has_more"] is True
    second = world.client.get(
        "/api/documents", params={"limit": 1, "offset": 1},
        headers=_auth(world)).json()
    assert second["metadata"]["count"] == 1
    assert second["metadata"]["has_more"] is False
    assert {first["data"][0]["id"], second["data"][0]["id"]} == {
        legacy_doc, current_doc}


def test_legacy_wrong_owner_and_non_fresh_rows_are_not_served(world):
    content = f"foreign legacy {uuid.uuid4().hex}\n"
    foreign_doc = document_routes._content_doc_key(content, None, None)
    _legacy_row(
        world, foreign_doc, content=content, owner_id="another-user-id",
    )

    stale_content = f"removed legacy {uuid.uuid4().hex}\n"
    stale_doc = document_routes._content_doc_key(stale_content, None, None)
    _legacy_row(
        world, stale_doc, content=stale_content, owner_id=world.admin.id,
        freshness="removed",
    )

    # Foreign vector ownership is not a grant merely because the durable SQL
    # row sits in the same normalized Personal workspace.
    assert world.client.get(
        f"/api/documents/{foreign_doc}", headers=_auth(world)).status_code == 404
    assert world.client.get(
        f"/api/documents/{foreign_doc}/export?format=text",
        headers=_auth(world)).status_code == 404

    # A retained tombstone is not readable source evidence.
    assert world.client.get(
        f"/api/documents/{stale_doc}", headers=_auth(world)).status_code == 404

    listing = world.client.get("/api/documents", headers=_auth(world))
    assert listing.status_code == 200, listing.text
    ids = {d["id"] for d in listing.json()["data"]}
    assert foreign_doc not in ids
    assert stale_doc not in ids


def test_legacy_delete_removes_the_exact_original_id(world):
    content = f"delete legacy {uuid.uuid4().hex}\n"
    doc_id = _legacy_row(
        world,
        document_routes._content_doc_key(content, None, None),
        content=content,
        owner_id=world.admin.id,
    )

    response = world.client.delete(
        f"/api/documents/{doc_id}", headers=_auth(world))
    assert response.status_code == 200, response.text
    verification = response.json()["metadata"]["verification"]
    assert verification["status"] == "verified", verification

    legacy = storage.get_lancedb_handler("default_shared")
    assert legacy.count_document_rows_by_id("documents", doc_id) == 0
    assert storage.get_lancedb_handler("default").get_document_by_id(
        "documents", doc_id) is None
    with world.Session() as db:
        row = db.get(IngestedDocument, doc_id)
        assert row is not None and row.freshness_status == "removed"
    assert world.client.get(
        f"/api/documents/{doc_id}", headers=_auth(world)).status_code == 404


# ---------------------------------------------------------------------------
# Already-written documents: semantic (vector-only) retrieval
# ---------------------------------------------------------------------------

_SEMANTIC_PARAPHRASE = "quarterly revenue projection"


def test_legacy_shared_upload_is_found_by_semantic_only_rpc_search(world):
    """The default RPC search must reach an upgrade-world document by meaning.

    On unmodified ``160621dfa`` the vector leg opens the Personal ``default``
    store while the already-written row lives in ``default_shared``: list/read
    could see it, semantic retrieval could not. The guarded legacy lane is
    part of the ordinary ``documents.search`` vector path, so no bespoke route
    or query flag is involved.
    """
    content = (
        "Historical pilot notes: the archive recovery code is HARBOR-77.\n"
    )
    doc_id = _legacy_row(
        world,
        document_routes._content_doc_key(content, None, None),
        content=content,
        owner_id=world.admin.id,
    )

    response = _rpc_search(world, _SEMANTIC_PARAPHRASE)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    data = body["data"]
    assert data["success"] is True, data
    assert data["status"] == "success", data
    assert data["absence_claimable"] is True, data
    assert data["legs"]["vector_legacy"]["status"] == "ok", data
    assert data["stats"]["legacy_vector_hits"] == 1, data
    # The paraphrase shares no retrievable token with the stored text, so this
    # is a semantic (vector) hit, not the lexical leg rescuing the query. (The
    # conversations leg may append its own suffix when that experiment is on.)
    assert data["hybrid"].startswith("semantic_only"), data
    assert data["stats"]["lexical_hits"] == 0, data

    ids = [r["id"] for r in data["results"]]
    assert ids == [doc_id], data
    hit = data["results"][0]
    assert hit["bridged"] is True, hit
    assert hit["citation_path"] == (
        f"knowledge/documents/{doc_id}/content.lines")
    assert "HARBOR-77" in (hit.get("content") or "")

    # The citation is usable through the normal VFS read, line-numbered and
    # resolving to the exact prior source text.
    cited = world.client.post(
        "/api/rpc/documents.cat",
        json={"params": {"path": hit["citation_path"]}},
        headers=_auth(world),
    )
    assert cited.status_code == 200, cited.text
    cited_body = cited.json()["data"]
    assert cited_body["success"] is True, cited_body
    assert cited_body["path"] == f"knowledge/documents/{doc_id}"
    assert "L1:" in cited_body["content"]
    assert "HARBOR-77" in cited_body["content"]

    # Reading is not writing: the original row and its namespace are intact.
    assert storage.get_lancedb_handler("default_shared").get_document_by_id(
        "documents", doc_id) is not None
    assert storage.get_lancedb_handler("default").get_document_by_id(
        "documents", doc_id) is None


@pytest.mark.parametrize(
    "seed",
    [
        # Vector-side tombstone (row still physically present in the store).
        pytest.param({"vector_freshness": "removed"}, id="stale-vector-row"),
        # Durable SQL tombstone.
        pytest.param({"freshness": "removed"}, id="stale-sql-row"),
        # A different account's pre-repair upload in the same shared store.
        pytest.param({"owner_id": "another-user-id"}, id="foreign-owner"),
        # Indexed revision disagrees with the authoritative SQL revision.
        pytest.param({"sql_revision": "ev0:not-the-same"}, id="revision-mismatch"),
        # No PG join key: the vector row cannot be bridged or proven.
        pytest.param({"metadata_drop": ("pg_document_id",)},
                     id="missing-bridge-id"),
        # Vector-only row with no durable SQL authority at all.
        pytest.param({"write_sql": False}, id="missing-sql-authority"),
        # Scope was written explicitly: no longer the raw-NULL bootstrap row.
        pytest.param({"tenant_id": "tenant-other"}, id="foreign-tenant"),
    ],
)
def test_legacy_semantic_lane_refuses_unproven_rows(world, seed):
    """Only a fully proven, fresh, this-owner record can be served."""
    content = f"unprovable legacy row {uuid.uuid4().hex}\n"
    seeded = {"content": content, "owner_id": world.admin.id}
    seeded.update(seed)
    doc_id = _legacy_row(
        world,
        document_routes._content_doc_key(content, None, None),
        **seeded,
    )

    response = _rpc_search(world, _SEMANTIC_PARAPHRASE)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "success", data
    assert data["legs"]["vector_legacy"]["status"] == "ok", data
    assert doc_id not in [r["id"] for r in data["results"]], data
    assert data["stats"]["legacy_vector_hits"] == 0, data
    # An empty, healthy legacy read may claim absence — and it does not leak
    # the refused row's text through any other lane.
    assert data["absence_claimable"] is True, data


def test_legacy_semantic_lane_rechecks_persisted_authority(world):
    """A downgraded principal loses the lane even with a forged authority."""
    import asyncio

    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    content = f"downgraded legacy {uuid.uuid4().hex}\n"
    doc_id = _legacy_row(
        world,
        document_routes._content_doc_key(content, None, None),
        content=content,
        owner_id=world.admin.id,
    )
    with world.Session() as db:
        admin = db.query(User).filter(User.id == world.admin.id).one()
        admin.role = "member"
        db.commit()

    result = asyncio.run(DocumentsHybridSearch(
        workspace_id="default",
        legacy_authority={
            "user_id": world.admin.id,
            "workspace_id": "default",
            "tenant_id": None,
        },
    ).search(_SEMANTIC_PARAPHRASE))

    assert result["legs"]["vector_legacy"]["status"] == "skipped", result
    assert result["legs"]["vector_legacy"]["skip_reason"] == (
        "legacy_authority_unverified"), result
    assert doc_id not in [r["id"] for r in result["results"]], result


def test_legacy_store_read_failure_is_not_reported_as_absence(
        world, monkeypatch):
    """An unreadable legacy store is coverage loss, never "no such document"."""
    from core.lancedb_handler import DocumentSearchUnavailable

    content = f"unreadable store {uuid.uuid4().hex}\n"
    _legacy_row(
        world,
        document_routes._content_doc_key(content, None, None),
        content=content,
        owner_id=world.admin.id,
    )

    def _broken(*args, **kwargs):
        raise DocumentSearchUnavailable("legacy store could not be read")

    monkeypatch.setattr(
        storage.LanceDBHandler, "search_documents_for_owner", _broken)

    response = _rpc_search(world, _SEMANTIC_PARAPHRASE)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["legs"]["vector_legacy"]["status"] == "failed", data
    assert data["legs"]["vector_legacy"]["error_category"], data
    assert data["status"] == "partial", data
    assert data["absence_claimable"] is False, data


# ---------------------------------------------------------------------------
# Member isolation
# ---------------------------------------------------------------------------


def test_member_workspace_isolation_survives_the_resolver_fallback(world):
    member, member_token = _add_member(
        world, f"ws-member-{uuid.uuid4().hex[:8]}")
    member_content = f"member private {uuid.uuid4().hex} MARKER-MEMBER-9\n"

    upload = _upload(world, member_content, "member.txt", member_token)
    assert upload.status_code == 200, upload.text
    member_doc = upload.json()["id"]

    with world.Session() as db:
        row = db.get(IngestedDocument, member_doc)
        assert row.workspace_id == member.workspace_id
        assert row.tenant_id == member.tenant_id

    # The member's own RPC search reads the member store.
    member_search = _rpc_search(world, "MARKER-MEMBER-9", member_token)
    assert member_doc in {
        r["id"] for r in member_search.json()["data"]["results"]}

    # The administrator's search and direct read never cross into it.
    admin_search = _rpc_search(world, "MARKER-MEMBER-9")
    assert admin_search.status_code == 200, admin_search.text
    assert member_doc not in {
        r["id"] for r in admin_search.json()["data"]["results"]}
    assert world.client.get(
        f"/api/documents/{member_doc}", headers=_auth(world)).status_code == 404
    assert world.client.get(
        f"/api/documents/{member_doc}/export?format=text",
        headers=_auth(world)).status_code == 404

    # And the member cannot read the bootstrap admin's Personal store.
    admin_content = f"admin private {uuid.uuid4().hex} MARKER-ADMIN-8\n"
    admin_upload = _upload(world, admin_content)
    admin_doc = admin_upload.json()["id"]
    assert world.client.get(
        f"/api/documents/{admin_doc}",
        headers=_auth(world, member_token)).status_code == 404


# ---------------------------------------------------------------------------
# Bounded legacy pagination
# ---------------------------------------------------------------------------


def _listing(world, **params):
    response = world.client.get(
        "/api/documents", params=params, headers=_auth(world))
    assert response.status_code == 200, response.text
    return response.json()


def test_legacy_duplicate_id_without_canonical_copy_on_page_is_counted_once(world):
    """A canonical copy outside the first requested page still dedupes."""
    legacy_content = f"shared identity {uuid.uuid4().hex}\n"
    legacy_doc = _legacy_row(
        world,
        document_routes._content_doc_key(legacy_content, None, None),
        content=legacy_content,
        owner_id=world.admin.id,
    )
    # The repaired canonical store also holds the same id (canonical copy).
    from core.doc_freshness_service import extraction_content_hash

    revision = extraction_content_hash(legacy_content)
    canonical = storage.get_lancedb_handler("default")
    assert canonical.add_document(
        table_name="documents",
        text=legacy_content,
        source="upload:canonical.txt",
        metadata={
            "title": "canonical.txt",
            "pg_document_id": legacy_doc,
            "source_content_hash": revision,
        },
        user_id=world.admin.id,
        workspace_id="default",
        doc_id=legacy_doc,
        extra_columns={"freshness_status": "fresh"},
    ) is True
    # A newer canonical-only document pushes the canonical copy off page 0.
    newer = _upload(world, f"newer {uuid.uuid4().hex}\n")
    assert newer.status_code == 200, newer.text
    newer_doc = newer.json()["id"]

    first = _listing(world, limit=1, offset=0)
    assert first["metadata"]["total"] == 2
    assert first["metadata"]["count"] == 1
    assert first["metadata"]["has_more"] is True
    assert first["metadata"]["next_offset"] == 1
    assert first["data"][0]["id"] == newer_doc

    second = _listing(world, limit=1, offset=1)
    assert second["metadata"]["total"] == 2
    assert second["metadata"]["has_more"] is False
    # Canonical copy wins: the upload's filename, not the legacy title.
    assert second["data"][0]["id"] == legacy_doc
    assert second["data"][0]["title"] == "canonical.txt"


def test_legacy_multibatch_owner_proof_and_deep_offset_bounded(
        world, monkeypatch):
    """Owner proof crosses head/SQL batches; deep offsets stay bounded."""
    monkeypatch.setattr(document_routes, "_LEGACY_HEAD_BATCH", 2)
    monkeypatch.setattr(document_routes, "_LEGACY_SQL_BATCH", 2)

    owned = []
    for index in range(3):
        content = f"owned legacy {index} {uuid.uuid4().hex}\n"
        owned.append(_legacy_row(
            world, document_routes._content_doc_key(content, None, None),
            content=content, owner_id=world.admin.id))
    foreign_content = f"foreign legacy {uuid.uuid4().hex}\n"
    foreign = _legacy_row(
        world, document_routes._content_doc_key(foreign_content, None, None),
        content=foreign_content, owner_id="another-user-id")
    stale_content = f"stale legacy {uuid.uuid4().hex}\n"
    stale = _legacy_row(
        world, document_routes._content_doc_key(stale_content, None, None),
        content=stale_content, owner_id=world.admin.id, freshness="removed")

    head_calls = []
    native_calls = []
    real_lister = storage.LanceDBHandler.list_document_heads_for_owner
    real_page = storage.LanceDBHandler.list_documents_page

    def _lister(self, *args, **kwargs):
        head_calls.append((kwargs.get("limit"), kwargs.get("offset")))
        return real_lister(self, *args, **kwargs)

    def _page(self, *args, **kwargs):
        native_calls.append((kwargs.get("limit"), kwargs.get("offset")))
        return real_page(self, *args, **kwargs)

    monkeypatch.setattr(
        storage.LanceDBHandler, "list_document_heads_for_owner", _lister)
    monkeypatch.setattr(
        storage.LanceDBHandler, "list_documents_page", _page)

    # Deep offset beyond the merged corpus: empty, truthful total, no crash.
    deep = _listing(world, limit=10, offset=150)
    assert deep["data"] == []
    assert deep["metadata"]["total"] == 3
    assert deep["metadata"]["count"] == 0
    assert deep["metadata"]["has_more"] is False
    assert "stale_page" not in deep["metadata"]

    # The head scan crossed batches with a bounded limit each time.
    assert len(head_calls) > 1
    assert all(limit == 2 for limit, _ in head_calls)
    assert any(offset and offset > 0 for _, offset in head_calls)
    # The canonical store was walked in bounded native pages, never with a
    # limit proportional to the requested offset.
    assert native_calls
    assert all(limit <= 100 for limit, _ in native_calls)

    seen = []
    for offset in (0, 2):
        body = _listing(world, limit=2, offset=offset)
        assert body["metadata"]["total"] == 3
        seen.extend(item["id"] for item in body["data"])
    assert len(seen) == 3 and len(set(seen)) == 3
    assert set(seen) == set(owned)
    assert foreign not in seen and stale not in seen


def _merge_row(prefix: str, stamp: str):
    return {"id": prefix, "created_at": stamp}


class _SyntheticNativeStore:
    """Deterministic canonical store with the native page contract."""

    def __init__(self, rows):
        self.rows = rows

    def list_documents_page(self, table, *, limit, offset):
        assert table == "documents"
        return {
            "total": len(self.rows),
            "documents": self.rows[offset:offset + limit],
        }


def test_merge_keeps_buffered_canonical_rows_after_native_exhaustion(
        monkeypatch):
    """The final canonical page is merged by key, not drained before legacy.

    With a 3-row chunk and 5 canonical rows, page 2 returns the last 2 rows and
    marks the native stream exhausted while the buffer still holds both. The
    legacy row interleaves between them and must not jump ahead of the buffered
    canonical head.
    """
    monkeypatch.setattr(document_routes, "_NATIVE_PAGE_CHUNK", 3)
    native = [
        _merge_row("c09", "2026-10-09T00:00:00"),
        _merge_row("c08", "2026-10-08T00:00:00"),
        _merge_row("c07", "2026-10-07T00:00:00"),
        _merge_row("c06", "2026-10-06T00:00:00"),
        _merge_row("c05", "2026-10-05T00:00:00"),
    ]
    legacy = [_merge_row("l05", "2026-10-05T12:00:00")]

    page = document_routes._merge_legacy_documents(
        _SyntheticNativeStore(native), iter(legacy), limit=6, offset=0)

    assert [row["id"] for row in page["documents"]] == [
        "c09", "c08", "c07", "c06", "l05", "c05"]
    assert page["count"] == 6
    assert page["total"] == 6
    assert page["has_more"] is False
    assert page["legacy_page_ids"] == {"l05"}


def test_merge_nonzero_offset_returns_only_the_requested_window(monkeypatch):
    """``offset`` is skipped via the merge cursor; it does not inflate `limit`.

    Also proves provenance retains only legacy ids inside the served window,
    not every legacy head scanned while ordering/counting.
    """
    monkeypatch.setattr(document_routes, "_NATIVE_PAGE_CHUNK", 3)
    native = [
        _merge_row("c09", "2026-10-09T00:00:00"),
        _merge_row("c08", "2026-10-08T00:00:00"),
        _merge_row("c07", "2026-10-07T00:00:00"),
        _merge_row("c06", "2026-10-06T00:00:00"),
        _merge_row("c05", "2026-10-05T00:00:00"),
    ]
    legacy = [
        _merge_row("l08", "2026-10-08T12:00:00"),
        _merge_row("l07", "2026-10-07T12:00:00"),
        _merge_row("l04", "2026-10-04T00:00:00"),
    ]

    page = document_routes._merge_legacy_documents(
        _SyntheticNativeStore(native), iter(legacy), limit=3, offset=2)

    # Global order: c09, l08, c08, l07, c07, c06, c05, l04.
    assert [row["id"] for row in page["documents"]] == ["c08", "l07", "c07"]
    assert page["count"] == 3
    assert page["total"] == 8
    assert page["has_more"] is True
    assert page["next_offset"] == 5
    assert page["legacy_page_ids"] == {"l07"}
