"""Lexical ranker (FTS5/tsvector) over IngestedDocument + KnowledgeDocument.

Step 2 of the hybrid-search plan. Tests use a scratch in-memory SQLite engine and
create the FTS tables with the same SQL the migration ships — they never depend on
dev-DB schema state.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

FTS_INGESTED_SQL = (
    "CREATE VIRTUAL TABLE ingested_documents_fts USING fts5("
    "file_name, content_preview, content='ingested_documents', content_rowid='rowid')"
)
FTS_KNOWLEDGE_SQL = (
    "CREATE VIRTUAL TABLE knowledge_documents_fts USING fts5("
    "title, content, content='knowledge_documents', content_rowid='rowid')"
)


@pytest.fixture
def db():
    from core.models import Base, IngestedDocument, KnowledgeDocument

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    session.add_all(
        [
            IngestedDocument(
                id="doc_a",
                workspace_id="default",
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
                file_name="meeting_notes.txt",
                file_path="/notes/meeting_notes.txt",
                file_type="txt",
                integration_id="onedrive",
                file_size_bytes=50,
                content_preview="Meeting notes about the team picnic planning.",
                external_id="e2",
                ingested_at=datetime.now(timezone.utc),
            ),
            IngestedDocument(
                id="doc_c",
                workspace_id="default",
                file_name="hiring.md",
                file_path="/policies/hiring.md",
                file_type="md",
                integration_id="google_drive",
                file_size_bytes=80,
                content_preview="We are hiring engineers for the growth team.",
                external_id="e3",
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

    session.execute(text(FTS_INGESTED_SQL))
    session.execute(text(FTS_KNOWLEDGE_SQL))
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


@pytest.fixture
def db_without_fts():
    """Engine without FTS tables — exercises the ILIKE fallback path."""
    from core.models import Base, IngestedDocument

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(
        IngestedDocument(
            id="doc_fb",
            workspace_id="default",
            file_name="fallback.txt",
            file_path="/fallback.txt",
            file_type="txt",
            integration_id="google_drive",
            file_size_bytes=10,
            content_preview="Fallback document about quarterly revenue.",
            external_id="efb",
            ingested_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    yield session
    session.close()


@pytest.mark.parametrize(
    "query,expected_ids",
    [
        ("revenue growth", ["doc_a"]),
        ("picnic", ["doc_b"]),
    ],
)
def test_lexical_ranks_relevant_docs(db, query, expected_ids):
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    results = search_documents_lexical(db, query)
    ids = [r["id"] for r in results]
    for expected in expected_ids:
        assert expected in ids, f"{expected!r} missing from results {ids}"


def test_lexical_ranks_exact_match_above_partial(db):
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    results = search_documents_lexical(db, "revenue growth")
    assert results, "expected results"
    assert results[0]["id"] == "doc_a", "both-token match must rank first"
    assert results[0]["source"] == "ingested"
    assert 0.0 < results[0]["score"] <= 1.0, "score must normalize to (0, 1]"
    assert results[0]["lexical_mode"] == "fts5_bm25"


def test_lexical_includes_knowledge_documents(db):
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    results = search_documents_lexical(db, "enterprise market")
    sources = {(r["source"], r["id"]) for r in results}
    assert ("knowledge", "kd_a") in sources, "knowledge docs must be searchable"


def test_lexical_source_filter(db):
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    results = search_documents_lexical(db, "growth", source="ingested")
    assert results and all(r["source"] == "ingested" for r in results)

    results = search_documents_lexical(db, "growth", source="knowledge")
    assert results and all(r["source"] == "knowledge" for r in results)


def test_lexical_since_filter(db):
    from core.hybrid_search.lexical_ranker import search_documents_lexical
    from core.models import IngestedDocument

    doc_a = db.query(IngestedDocument).filter(IngestedDocument.id == "doc_a").first()
    doc_a.created_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db.commit()

    results = search_documents_lexical(db, "revenue", since=datetime(2024, 1, 1, tzinfo=timezone.utc))
    ids = [r["id"] for r in results]
    assert "doc_a" not in ids, "since filter must exclude older docs"


def test_lexical_iliike_fallback_when_fts_missing(db_without_fts):
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    results = search_documents_lexical(db_without_fts, "quarterly revenue")
    assert results, "fallback must still return matches"
    assert results[0]["id"] == "doc_fb"
    assert results[0]["lexical_mode"] == "iliike_fallback"
    assert 0.0 < results[0]["score"] <= 1.0


def test_lexical_never_raises(db):
    from core.hybrid_search.lexical_ranker import search_documents_lexical

    assert search_documents_lexical(db, "") == []
    assert search_documents_lexical(db, "a") == []  # too short
    assert search_documents_lexical(db, "!!!") == []
