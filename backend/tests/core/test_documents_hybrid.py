"""DocumentsHybridSearch — vector + BM25 lexical legs fused by RRF (Step 3).

Uses a scratch in-memory SQLite engine + a fake LanceDB handler so no dev-DB or
cloud-embedding dependency. Covers the RRF fusion, join-key hydration, the
degradation ladder, and unbridged-hit dropping.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class FakeLanceDB:
    def __init__(self, rows: List[Dict[str, Any]]):
        self.rows = rows

    def search(self, table_name, query, user_id=None, limit=10, filter_str=None, **kwargs):
        if self.rows is None:
            raise RuntimeError("LanceDB down")
        return [dict(r) for r in self.rows[:limit]]


@pytest.fixture
def db(monkeypatch):
    # Hermetic: the conversations leg reads the REAL shared LanceDB comms
    # store and appends hits + a "+conversations" label suffix when a dev
    # store has ingested communications. These tests cover documents legs.
    monkeypatch.setenv("MEMORY_CONVERSATIONS_LEG", "false")
    from core.models import Base, IngestedDocument, KnowledgeDocument

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            IngestedDocument(
                id="doc_a",
                workspace_id="default",
                tenant_id="default",
                file_name="revenue_report.pdf",
                file_path="/reports/revenue_report.pdf",
                file_type="pdf",
                integration_id="google_drive",
                file_size_bytes=100,
                content_preview="Quarterly revenue grew twenty percent driven by enterprise growth.",
                external_id="e1",
                ingested_at=datetime.now(timezone.utc),
            ),
            IngestedDocument(
                id="doc_b",
                workspace_id="default",
                tenant_id="default",
                file_name="meeting_notes.txt",
                file_path="/notes/meeting_notes.txt",
                file_type="txt",
                integration_id="onedrive",
                file_size_bytes=50,
                content_preview="Meeting notes about the team picnic planning.",
                external_id="e2",
                ingested_at=datetime.now(timezone.utc),
            ),
            KnowledgeDocument(
                id="kd_a",
                workspace_id="default",
                tenant_id="default",
                title="Growth strategy",
                content="Revenue growth strategy for the enterprise market segment.",
            ),
        ]
    )
    session.commit()
    session.execute(
        text(
            "CREATE VIRTUAL TABLE ingested_documents_fts USING fts5("
            "file_name, content_preview, content='ingested_documents', content_rowid='rowid')"
        )
    )
    session.execute(
        text(
            "CREATE VIRTUAL TABLE knowledge_documents_fts USING fts5("
            "title, content, content='knowledge_documents', content_rowid='rowid')"
        )
    )
    session.execute(
        text(
            "INSERT INTO ingested_documents_fts(rowid, file_name, content_preview) "
            "SELECT rowid, COALESCE(file_name,''), COALESCE(content_preview,'') "
            "FROM ingested_documents"
        )
    )
    session.execute(
        text(
            "INSERT INTO knowledge_documents_fts(rowid, title, content) "
            "SELECT rowid, COALESCE(title,''), COALESCE(content,'') "
            "FROM knowledge_documents"
        )
    )
    session.commit()
    yield session
    session.close()


def bridged_row(doc_id: str, distance: float = 0.1) -> Dict[str, Any]:
    return {"id": doc_id, "_distance": distance, "metadata": {"file_name": "x"}}
    # metadata key shape varies by handler; hydration must not depend on it


def legacy_row(doc_id: str) -> Dict[str, Any]:
    return {"id": doc_id, "_distance": 0.5, "metadata": {"file_name": "orphan.pdf"}}


@pytest.mark.asyncio
async def test_semantic_query_returns_doc_without_lexical_overlap(db):
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    lancedb = FakeLanceDB([bridged_row("doc_a", 0.05)])
    svc = DocumentsHybridSearch(db=db, lancedb=lancedb)

    res = await svc.search("income increased substantially")

    assert res["hybrid"] == "semantic_only", res["hybrid"]
    assert [r["id"] for r in res["results"]] == ["doc_a"]
    assert res["results"][0]["bridged"] is True
    assert res["results"][0]["title"] == "revenue_report.pdf"


@pytest.mark.asyncio
async def test_rrf_fusion_ranks_both_leg_matches_first(db):
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    lancedb = FakeLanceDB([bridged_row("doc_a", 0.1), bridged_row("doc_b", 0.2)])
    svc = DocumentsHybridSearch(db=db, lancedb=lancedb)

    res = await svc.search("revenue growth")

    assert res["hybrid"] == "bm25_vector_rrf"
    ids = [r["id"] for r in res["results"]]
    assert ids[0] == "doc_a", f"both-leg match must rank first: {ids}"
    # dedupe: doc_a appears exactly once
    assert ids.count("doc_a") == 1
    assert ids[0] != ids[1]


@pytest.mark.asyncio
async def test_lexical_only_when_vector_leg_empty(db):
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    svc = DocumentsHybridSearch(db=db, lancedb=FakeLanceDB([]))

    res = await svc.search("revenue growth")

    assert res["hybrid"] == "lexical_only"
    ids = [r["id"] for r in res["results"]]
    assert ids[0] == "doc_a", f"ingested match should lead: {ids}"
    assert "kd_a" in ids, "knowledge docs must appear in the lexical leg"


@pytest.mark.asyncio
async def test_no_results_label(db):
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    svc = DocumentsHybridSearch(db=db, lancedb=FakeLanceDB([]))

    res = await svc.search("zzz qqq")

    assert res["hybrid"] == "no_results"
    assert res["results"] == []


@pytest.mark.asyncio
async def test_unbridged_vector_hits_flagged_not_dropped(db):
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    lancedb = FakeLanceDB([legacy_row("1789123456.123"), bridged_row("doc_a", 0.1)])
    svc = DocumentsHybridSearch(db=db, lancedb=lancedb)

    res = await svc.search("revenue growth")

    ids = [r["id"] for r in res["results"]]
    assert "1789123456.123" in ids, "unbridged hits must be surfaced, not dropped"
    hit = next(r for r in res["results"] if r["id"] == "1789123456.123")
    assert hit["bridged"] is False
    assert res["stats"]["unbridged_hits"] == 1


@pytest.mark.asyncio
async def test_vector_leg_failure_degrades_to_lexical(db):
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    svc = DocumentsHybridSearch(db=db, lancedb=FakeLanceDB(None))

    res = await svc.search("revenue growth")

    assert res["hybrid"] == "lexical_only"
    assert res["results"], "lexical results must survive vector failure"


@pytest.mark.asyncio
async def test_never_raises_on_garbage(db):
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    svc = DocumentsHybridSearch(db=db, lancedb=FakeLanceDB(None))

    res = await svc.search("")
    assert res["hybrid"] == "no_results"
    res = await svc.search("!!")
    assert res["results"] == []


# --- join-key bridge: chunks and ingest stamps (2026-09-11) -------------------
#
# Live evidence: the LanceDB `documents` table held 38,983 rows of which only
# 981 bridged by id equality. 35,325 were CHUNK rows (`<doc_id>::cN`) whose
# parent id had been stamped into `metadata.pg_document_id` at ingest, and 2,676
# carried a stamp not present in PG. Because `_fuse_rrf` matched on `id` alone,
# every one of those chunk hits was reported `bridged:false` — and, worse, a
# chunk hit and its parent's lexical hit landed on different RRF keys, so the
# two legs could never reinforce each other.


def chunk_row(chunk_id: str, pg_id: str, distance: float = 0.05) -> Dict[str, Any]:
    return {
        "id": chunk_id,
        "_distance": distance,
        "metadata": {"pg_document_id": pg_id, "file_name": "chunk.pdf"},
    }


@pytest.mark.asyncio
async def test_chunk_hit_hydrates_through_ingest_stamp(db):
    """A `::cN` chunk must hydrate to its parent document, not stay orphaned."""
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    lancedb = FakeLanceDB([chunk_row("doc_a::c0", "doc_a")])
    svc = DocumentsHybridSearch(db=db, lancedb=lancedb)

    res = await svc.search("zzz_no_lexical_overlap")

    assert res["stats"]["unbridged_hits"] == 0, "chunk was not bridged"
    hit = res["results"][0]
    assert hit["id"] == "doc_a", "must resolve to the parent document id"
    assert hit["bridged"] is True


@pytest.mark.asyncio
async def test_chunk_hit_hydrates_from_suffix_without_stamp(db):
    """Even with no ingest stamp, the `::cN` suffix identifies the parent."""
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    row = {"id": "doc_a::c7", "_distance": 0.05, "metadata": {"file_name": "c.pdf"}}
    svc = DocumentsHybridSearch(db=db, lancedb=FakeLanceDB([row]))

    res = await svc.search("zzz_no_lexical_overlap")

    assert res["results"][0]["id"] == "doc_a"
    assert res["results"][0]["bridged"] is True


@pytest.mark.asyncio
async def test_chunk_and_parent_lexical_hit_fuse_into_one_entry(db):
    """The whole point of hybrid: both legs must reinforce ONE document."""
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    # Lexical leg finds doc_a via its FTS row; vector leg finds a chunk of doc_a.
    lancedb = FakeLanceDB([chunk_row("doc_a::c0", "doc_a")])
    svc = DocumentsHybridSearch(db=db, lancedb=lancedb)

    res = await svc.search("revenue growth")  # 'revenue' matches doc_a lexically

    doc_a_entries = [r for r in res["results"] if r["id"] == "doc_a"]
    assert len(doc_a_entries) == 1, (
        f"parent and chunk must fuse into one entry, got {len(doc_a_entries)}"
    )
    assert res["stats"]["lexical_hits"] > 0, "precondition: lexical leg matched"


@pytest.mark.asyncio
async def test_unknown_chunk_still_surfaces_as_unbridged(db):
    """A chunk whose parent is genuinely absent must still be returned."""
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    lancedb = FakeLanceDB([chunk_row("no_such_doc::c3", "no_such_doc")])
    svc = DocumentsHybridSearch(db=db, lancedb=lancedb)

    res = await svc.search("zzz_no_lexical_overlap")

    hit = res["results"][0]
    assert hit["id"] == "no_such_doc::c3"
    assert hit["bridged"] is False
    assert res["stats"]["unbridged_hits"] == 1


@pytest.mark.asyncio
async def test_json_string_metadata_is_tolerated(db):
    """Metadata arrives as a dict OR a JSON string depending on the writer."""
    from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

    row = {
        "id": "doc_a::c1",
        "_distance": 0.05,
        "metadata": '{"pg_document_id": "doc_a", "file_name": "x.pdf"}',
    }
    svc = DocumentsHybridSearch(db=db, lancedb=FakeLanceDB([row]))

    res = await svc.search("zzz_no_lexical_overlap")

    assert res["results"][0]["id"] == "doc_a"
    assert res["results"][0]["bridged"] is True
