"""Knowledge VFS population journey: every connector ingest must surface.

Journey trace (Aug 2026) on a live store: 69 LanceDB documents rows ingested
by connectors (OneDrive, Zoho WorkDrive) but 0 PG IngestedDocument rows — so
``ls knowledge/documents`` listed none of them, ``grep`` scanned none of them,
the FTS lexical leg never saw them, and hybrid search flagged them all
bridged:false forever.

Covers:
1. process_file_bytes (shared connector/upload ingest) must upsert the aligned
   PG mirror row (id == vector doc_id).
2. Re-ingest of a changed file with a stable external id must UPDATE that
   mirror row, not duplicate it.
3. Knowledge VFS ls must surface vector-only rows (no PG mirror) so browsing
   matches search.
4. Knowledge VFS cat must serve full vector text, not the ≤500-char PG
   preview, for bridged rows.
5. _persist_freshness_on_ingest must realign the PG row id when the vector
   row is rewritten under a new id (join-key drift).
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class FakeMemoryHandler:
    """In-memory stand-in for LanceDBHandler's upsert surface."""

    def __init__(self):
        self.docs = {}

    def get_document_by_id(self, table_name, doc_id):
        row = self.docs.get(str(doc_id))
        if row is None:
            return None
        return {"id": doc_id, "text": row["text"], "metadata": dict(row["metadata"])}

    def delete_documents_by_id(self, table_name, doc_id):
        self.docs.pop(str(doc_id), None)
        return True

    def add_document(self, **kwargs):
        self.docs[str(kwargs["doc_id"])] = {
            "text": kwargs["text"],
            "metadata": dict(kwargs.get("metadata") or {}),
        }
        return True


@pytest.fixture
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.database import Base

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # _freshness_session imports SessionLocal from core.database at call time.
    monkeypatch.setattr("core.database.SessionLocal", Session)
    yield session
    session.close()


@pytest.fixture
def ingestion_service(monkeypatch):
    """AutoDocumentIngestionService wired to a fake LanceDB handler."""
    handler = FakeMemoryHandler()
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler", lambda *a, **k: handler
    )

    from core.auto_document_ingestion import AutoDocumentIngestionService

    svc = AutoDocumentIngestionService(workspace_id="default")
    yield svc, handler


# ---------------------------------------------------------------------------
# 1+2. process_file_bytes writes the aligned PG mirror row
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_process_file_bytes_creates_aligned_pg_mirror_row(
    db_session, ingestion_service
):
    from core.models import IngestedDocument

    svc, handler = ingestion_service

    res = await svc.process_file_bytes(
        content=b"Q3 revenue grew 20 percent year over year.",
        file_name="revenue.pdf.txt",
        source="onedrive",
        external_id="drive-123",
    )
    assert res["status"] == "ingested"
    doc_id = res["doc_id"]

    row = db_session.query(IngestedDocument).filter(IngestedDocument.id == doc_id).first()
    assert row is not None, "connector ingest must create the PG mirror row"
    assert row.file_name == "revenue.pdf.txt"
    assert row.integration_id == "onedrive"
    assert row.workspace_id == "default"
    assert row.content_preview, "preview feeds the lexical (FTS) leg"
    # Join-key bridge: vector row id == PG row id.
    assert doc_id in handler.docs
    assert handler.docs[doc_id]["metadata"]["pg_document_id"] == doc_id


@pytest.mark.asyncio
async def test_changed_reingest_updates_mirror_row_without_duplicates(
    db_session, ingestion_service
):
    from core.models import IngestedDocument

    svc, handler = ingestion_service

    first = await svc.process_file_bytes(
        content=b"version one", file_name="doc.txt", source="onedrive",
        external_id="od-9",
    )
    second = await svc.process_file_bytes(
        content=b"version two with more words", file_name="doc.txt",
        source="onedrive", external_id="od-9",
    )
    assert first["doc_id"] == second["doc_id"], (
        "stable external id must yield a stable doc_id"
    )

    rows = (
        db_session.query(IngestedDocument)
        .filter(IngestedDocument.id == second["doc_id"])
        .all()
    )
    assert len(rows) == 1, "re-ingest must update, not duplicate"
    assert rows[0].content_preview.startswith("version two")


# ---------------------------------------------------------------------------
# 3. VFS ls must include vector-only rows
# ---------------------------------------------------------------------------
class HeadsOnlyHandler:
    def __init__(self, heads):
        self._heads = heads

    def list_document_heads(self, table_name, limit=200):
        return self._heads[:limit]


@pytest.mark.asyncio
async def test_vfs_ls_surfaces_vector_only_documents(db_session, monkeypatch):
    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda *a, **k: HeadsOnlyHandler([
            {"id": "doc_vectoronly1", "metadata": {"file_name": "orphan.pdf"},
             "created_at": "2026-08-26T22:00:00+00:00"},
            {"id": "doc_vectoronly2", "metadata": {}, "created_at": ""},
        ]),
    )
    provider = KnowledgeVFSProvider(db_factory=lambda: db_session)

    nodes = await provider.ls("knowledge/documents", {"workspace_id": "default"})
    names = {n.name for n in nodes}
    assert {"doc_vectoronly1", "doc_vectoronly2"} <= names, (
        "vector-only rows must be listed so browsing matches search"
    )


@pytest.mark.asyncio
async def test_vfs_ls_does_not_duplicate_bridged_ids(db_session, monkeypatch):
    from core.models import IngestedDocument
    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    db_session.add(IngestedDocument(
        id="doc_a", workspace_id="default", file_name="a.txt",
        file_path="p", file_type="txt", integration_id="g", external_id="e1",
    ))
    db_session.commit()
    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda *a, **k: HeadsOnlyHandler([
            {"id": "doc_a", "metadata": {}, "created_at": ""},
        ]),
    )
    provider = KnowledgeVFSProvider(db_factory=lambda: db_session)

    nodes = await provider.ls("knowledge/documents", {"workspace_id": "default"})
    assert [n.name for n in nodes].count("doc_a") == 1


# ---------------------------------------------------------------------------
# 4. VFS cat serves full vector text for bridged rows (not the 500-char preview)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_vfs_cat_prefers_full_vector_text(db_session, monkeypatch):
    from core.models import IngestedDocument
    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    preview = ("preview body. " * 40)[:500]
    full_text = preview + " TAIL-ONLY-IN-VECTOR-STORE clause forty-two."
    db_session.add(IngestedDocument(
        id="doc_full", workspace_id="default", file_name="f.txt",
        file_path="p", file_type="txt", integration_id="g", external_id="e2",
        content_preview=preview,
    ))
    db_session.commit()

    class FullTextHandler:
        def get_document_by_id(self, table_name, doc_id):
            if doc_id == "doc_full":
                return {"id": doc_id, "text": full_text, "metadata": {}}
            return None

        def list_document_heads(self, table_name, limit=200):
            return []

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler", lambda *a, **k: FullTextHandler()
    )
    provider = KnowledgeVFSProvider(db_factory=lambda: db_session)

    res = await provider.cat("knowledge/documents/doc_full/content.lines")
    joined = "\n".join(res.lines)
    assert "TAIL-ONLY-IN-VECTOR-STORE" in joined, (
        "cat must serve the full vector text, not the truncated PG preview"
    )


# ---------------------------------------------------------------------------
# 5. Freshness persist realigns PG id when the vector row is rewritten
# ---------------------------------------------------------------------------
def test_persist_freshness_realigns_id_drift(db_session, monkeypatch):
    from core.models import IngestedDocument

    from core.auto_document_ingestion import AutoDocumentIngestionService

    svc = AutoDocumentIngestionService(workspace_id="default")

    db_session.add(IngestedDocument(
        id="doc_old", workspace_id="default", file_name="changed.txt",
        file_path="p", file_type="txt", integration_id="gdrive",
        external_id="src-1",
    ))
    db_session.commit()

    from core.auto_document_ingestion import IngestedDocument as DataclassDoc

    svc.ingested_docs["src-1"] = DataclassDoc(
        id="doc_new", file_name="changed.txt", file_path="p", file_type="txt",
        integration_id="gdrive", workspace_id="default", file_size_bytes=10,
        content_preview="fresh body", ingested_at=datetime.now(timezone.utc),
        external_id="src-1",
    )
    svc._persist_freshness_on_ingest(
        svc.ingested_docs["src-1"], source_url=None, content_hash="h2",
        source_modified_at=None,
    )

    ids = {r.id for r in db_session.query(IngestedDocument).all()}
    assert "doc_new" in ids, "PG row must realign to the fresh vector id"
    assert "doc_old" not in ids, "stale id must not linger (it points at a deleted vector row)"
