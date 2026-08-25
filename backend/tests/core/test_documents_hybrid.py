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
