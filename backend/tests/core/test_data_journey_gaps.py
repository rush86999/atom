"""Data-journey gap fixes: every ingested byte must be retrievable.

Journey trace (Aug 2026) found these breaks between INGEST → STORE → INDEX →
RETRIEVE → CONSUME:

1. documents.search RRF fusion DROPPED every vector hit whose id had no PG
   IngestedDocument row — i.e. connector file ingests (process_file_bytes,
   doc_id=file_<ts>) and manual uploads. The writer-side contract
   (auto_document_ingestion.py + test_hybrid_join_key.py) says such hits must
   be FLAGGED bridged:false, not silently dropped.
2. Knowledge VFS cat could not read those vector-only rows (PG-only _get_doc),
   so even after surfacing they were unconsumable.
3. POST /api/documents/upload wrote through a RAW LanceDBHandler() (the ROOT
   ./data/atom_memory store) while documents.search reads the per-workspace
   store via get_lancedb_handler("default") — uploads landed in a store the
   search never reads. Also no join-key stamp, no PG row, auto-generated id.
4. POST /v1/documents/upload created no PG row and stamped metadata["doc_id"]
   instead of the pg_document_id join key → vector-only, lexically invisible.
"""
import io
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# ---------------------------------------------------------------------------
# 1+2. Fusion must surface unbridged vector hits (bridged:false), not drop
# ---------------------------------------------------------------------------
class FakeLanceDB:
    def __init__(self, rows: List[Dict[str, Any]]):
        self.rows = rows

    def search(self, table_name, query, user_id=None, limit=10, filter_str=None, **kwargs):
        return [dict(r) for r in self.rows[:limit]]


@pytest.fixture
def hybrid_db():
    from core.models import Base, IngestedDocument, KnowledgeDocument

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        IngestedDocument(
            id="doc_a",
            workspace_id="default",
            tenant_id="default",
            file_name="revenue_report.pdf",
            file_path="/reports/revenue_report.pdf",
            file_type="pdf",
            integration_id="google_drive",
            file_size_bytes=100,
            content_preview="Quarterly revenue grew twenty percent.",
            external_id="e1",
            ingested_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        KnowledgeDocument(
            id="kd_a",
            workspace_id="default",
            tenant_id="default",
            title="Growth strategy",
            content="Revenue growth strategy for enterprise.",
        )
    )
    session.commit()
    yield session
    session.close()


@pytest.mark.asyncio
async def test_unbridged_vector_hits_surfaced_as_bridged_false(hybrid_db):
    """Vector-only rows (no PG row) must be RETURNED flagged bridged:false."""
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    lancedb = FakeLanceDB([
        {"id": "file_1789123456.123", "_distance": 0.05,
         "metadata": {"file_name": "orphan.pdf", "source_type": "file"}},
    ])
    svc = DocumentsHybridSearch(db=hybrid_db, lancedb=lancedb)

    res = await svc.search("income increased substantially")

    ids = [r["id"] for r in res["results"]]
    assert "file_1789123456.123" in ids, (
        "unbridged vector hits must be surfaced (flagged), never dropped"
    )
    hit = next(r for r in res["results"] if r["id"] == "file_1789123456.123")
    assert hit["bridged"] is False
    assert res["stats"]["unbridged_hits"] == 1


@pytest.mark.asyncio
async def test_unbridged_hit_title_from_metadata(hybrid_db):
    """Title/preview come from LanceDB metadata when there is no PG row."""
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    lancedb = FakeLanceDB([
        {"id": "file_1789123456.123", "_distance": 0.05,
         "metadata": {"file_name": "orphan.pdf"}},
    ])
    svc = DocumentsHybridSearch(db=hybrid_db, lancedb=lancedb)

    res = await svc.search("income increased substantially")

    hit = res["results"][0]
    assert hit["title"] == "orphan.pdf"


@pytest.mark.asyncio
async def test_bridged_hit_still_flagged_true_and_ranks_first(hybrid_db):
    """PG-resolvable hits stay bridged:true and outrank unbridged on ties."""
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    lancedb = FakeLanceDB([
        {"id": "doc_a", "_distance": 0.05, "metadata": {}},
        {"id": "file_9", "_distance": 0.06, "metadata": {"file_name": "f.pdf"}},
    ])
    svc = DocumentsHybridSearch(db=hybrid_db, lancedb=lancedb)

    res = await svc.search("income increased substantially")

    assert res["results"][0]["id"] == "doc_a"
    assert res["results"][0]["bridged"] is True
    assert any(r["id"] == "file_9" and r["bridged"] is False for r in res["results"])


# ---------------------------------------------------------------------------
# 2b. Knowledge VFS must cat vector-only rows (LanceDB fallback)
# ---------------------------------------------------------------------------
@pytest.fixture
def vfs_provider(monkeypatch):
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "true")
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.database import Base

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider

    provider = KnowledgeVFSProvider(db_factory=lambda: Session(bind=engine))
    yield provider, session
    session.close()


@pytest.mark.asyncio
async def test_vfs_cat_falls_back_to_lancedb_for_vector_only_id(
    vfs_provider, monkeypatch
):
    """A file_<ts>/upload vector-only id must be cat-able via LanceDB."""
    provider, _ = vfs_provider

    class FakeHandler:
        def get_document_by_id(self, table_name, doc_id):
            assert table_name == "documents"
            assert doc_id == "file_1789123456.123"
            return {
                "id": doc_id,
                "text": "Orphan contract clauses\nSecond line\n",
                "source": "google_drive:orphan.pdf",
                "metadata": {
                    "file_name": "orphan.pdf",
                    "source_type": "file",
                    "sensitivity": "internal",
                },
            }

    monkeypatch.setattr(
        "core.lancedb_handler.get_lancedb_handler",
        lambda *a, **k: FakeHandler(),
    )

    res = await provider.cat("knowledge/documents/file_1789123456.123/content.lines")
    assert res.lines, "vector-only row must be readable via the VFS"
    assert res.lines[0].startswith("L1: ")
    assert res.meta["file_name"] == "orphan.pdf"
    assert res.meta["source"] == "vector"


# ---------------------------------------------------------------------------
# 3. POST /api/documents/upload — store parity + join key + PG row
# ---------------------------------------------------------------------------
def _upload_file(name: str, data: bytes):
    from fastapi import UploadFile

    return UploadFile(file=io.BytesIO(data), size=len(data), filename=name)


class FakeUser:
    id = "u1"
    email = "u1@example.com"
    workspaces = []


class RecordingHandler:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def add_document(self, **kwargs):
        self.calls.append(kwargs)
        return True

    def get_table(self, name):
        return object()

    def create_table(self, name):
        return object()

    def get_document_by_id(self, table_name, doc_id):
        return {"text": "x"}


@pytest.fixture
def pg_session():
    from core.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, engine
    session.close()


@pytest.mark.asyncio
async def test_v1_upload_creates_pg_row_and_stamps_join_key(pg_session, monkeypatch):
    """document_routes.upload_document: full journey — PG row aligned to the
    vector id + pg_document_id/source_type stamps (lexical + VFS + citable)."""
    import contextlib

    import backend.api.document_routes as doc_routes
    import core.database as core_db

    session, engine = pg_session
    handler = RecordingHandler()
    monkeypatch.setattr(doc_routes, "get_lancedb_handler", lambda ws=None: handler)

    @contextlib.contextmanager
    def fake_session():
        yield session

    monkeypatch.setattr(core_db, "get_db_session", fake_session)

    resp = await doc_routes.upload_document(
        _upload_file("notes.txt", b"manual knowledge body"), current_user=FakeUser()
    )

    assert handler.calls, "add_document was not called"
    kwargs = handler.calls[0]
    doc_id = kwargs["doc_id"]
    assert kwargs["metadata"].get("pg_document_id") == doc_id
    assert kwargs["metadata"].get("source_type") == "upload"

    from core.models import IngestedDocument

    row = session.query(IngestedDocument).filter(IngestedDocument.id == doc_id).first()
    assert row is not None, "upload must create the aligned IngestedDocument row"
    assert row.integration_id == "manual_upload"
    assert row.content_preview, "content_preview feeds the lexical leg"
    assert resp.id == doc_id


@pytest.mark.asyncio
async def test_api_upload_uses_workspace_handler_join_key_and_pg_row(
    pg_session, monkeypatch
):
    """document_ingestion_routes.upload_document: must write through
    get_lancedb_handler (per-workspace store that search reads), pass an
    explicit doc_id, stamp the join key, and create the PG row."""
    import contextlib

    import backend.api.document_ingestion_routes as ingestion_routes
    import core.database as core_db

    session, engine = pg_session
    handler = RecordingHandler()
    seen_ws: List[Any] = []

    def fake_get_handler(ws=None):
        seen_ws.append(ws)
        return handler

    monkeypatch.setattr(ingestion_routes, "get_lancedb_handler", fake_get_handler)

    @contextlib.contextmanager
    def fake_session():
        yield session

    monkeypatch.setattr(core_db, "get_db_session", fake_session)

    resp = await ingestion_routes.upload_document(
        _upload_file("report.md", b"# report body"), current_user=FakeUser()
    )

    assert handler.calls, "add_document was not called"
    kwargs = handler.calls[0]
    doc_id = kwargs["doc_id"]
    assert doc_id, "route must pass an explicit doc_id (join-key alignment)"
    assert kwargs["metadata"].get("pg_document_id") == doc_id
    assert kwargs["metadata"].get("source_type") == "upload"

    from core.models import IngestedDocument

    row = session.query(IngestedDocument).filter(IngestedDocument.id == doc_id).first()
    assert row is not None, "upload must create the aligned IngestedDocument row"

    data = resp["data"] if isinstance(resp, dict) else resp
    assert data["file_name"] == "report.md"
