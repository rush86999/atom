# -*- coding: utf-8 -*-
"""Coverage wave 84c (hybrid-search part) — 3 core/hybrid_search modules.

EXTENDS the R51 suites (before-%: backfill_matcher 100%, lexical_ranker 100%,
documents_hybrid 95% — closes label lines 77/83 and the real lexical leg
105-108). Re-derives >=95% standalone coverage for:

  core/hybrid_search/backfill_matcher.py
  core/hybrid_search/documents_hybrid.py
  core/hybrid_search/lexical_ranker.py

Style: mocked deps, zero LLM spend, no network. Real in-memory SQLite for the
ILIKE fallback + hydration paths; mocked sessions for the FTS/tsvector paths.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.hybrid_search.backfill_matcher import match_pg_row
from core.hybrid_search.documents_hybrid import DocumentsHybridSearch
from core.hybrid_search.lexical_ranker import (
    _column_exists_pg,
    _fts_table_exists,
    _query_safe_tokens,
    _search_iliike_fallback,
    _search_ingested_pg,
    _search_ingested_sqlite,
    _search_knowledge_pg,
    _search_knowledge_sqlite,
    search_documents_lexical,
)
from core.models import (  # noqa: F401 (register models)
    IngestedDocument,
    KnowledgeDocument,
)


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db(db_engine):
    from sqlalchemy.orm import sessionmaker

    session = sessionmaker(bind=db_engine)()
    yield session
    session.rollback()
    session.close()
    with db_engine.connect() as con:
        for table in reversed(Base.metadata.sorted_tables):
            con.execute(table.delete())
        con.commit()


def _ingested(db, doc_id, *, file_name="quarterly report", content="the quarterly report shows growth",
              integration_id="gdrive", external_id="ext-1", external_modified_at=None,
              created_at=None):
    doc = IngestedDocument(
        id=doc_id,
        workspace_id="ws-1",
        tenant_id="t1",
        file_name=file_name,
        file_path=f"/docs/{file_name}",
        file_type="txt",
        integration_id=integration_id,
        content_preview=content,
        external_id=external_id,
        external_modified_at=external_modified_at,
    )
    if created_at is not None:
        doc.created_at = created_at
    db.add(doc)
    db.commit()
    return doc


def _knowledge(db, doc_id, *, title="knowledge base", content="general knowledge entry", created_at=None):
    k = KnowledgeDocument(
        id=doc_id,
        tenant_id="t1",
        title=title,
        content=content,
    )
    if created_at is not None:
        k.created_at = created_at
    db.add(k)
    db.commit()
    return k


class _FakeLanceDB:
    """Sync search method — runs inside asyncio.to_thread."""

    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error

    def search(self, table, query, limit=10):
        if self.error is not None:
            raise self.error
        return self.rows


# ============================================================================
# core/hybrid_search/backfill_matcher.py
# ============================================================================


class TestBackfillMatcher:
    def test_leg1_external_id_exact(self, db):
        _ingested(db, "doc-1", external_id="ext-1")
        assert match_pg_row(db, {"external_id": "ext-1"}, "lancedb-id") == "doc-1"

    def test_leg1_external_id_earliest_wins(self, db):
        _ingested(db, "doc-2", external_id="ext-9", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
        _ingested(db, "doc-3", external_id="ext-9", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert match_pg_row(db, {"external_id": "ext-9"}, "lancedb-id") == "doc-3"

    def test_leg1_no_match_falls_through(self, db):
        _ingested(db, "doc-1", external_id="ext-1", file_name="report.txt", integration_id="gdrive")
        assert match_pg_row(db, {"external_id": "nope", "file_name": "report.txt"}, "lancedb-id") == "doc-1"

    def test_leg2_file_name_with_integration(self, db):
        _ingested(db, "doc-1", file_name="report.txt", integration_id="gdrive", external_id="x1")
        result = match_pg_row(db, {"file_name": "report.txt", "integration_id": "gdrive"}, "lancedb-id")
        assert result == "doc-1"

    def test_leg2_file_name_ignores_wrong_integration(self, db):
        _ingested(db, "doc-1", file_name="report.txt", integration_id="gdrive", external_id="x1")
        assert match_pg_row(db, {"file_name": "report.txt", "integration_id": "dropbox"}, "lancedb-id") is None

    def test_leg2_file_name_without_integration(self, db):
        _ingested(db, "doc-1", file_name="report.txt", integration_id="gdrive", external_id="x1")
        assert match_pg_row(db, {"file_name": "report.txt"}, "lancedb-id") == "doc-1"

    def test_leg2_earliest_wins(self, db):
        _ingested(db, "doc-2", file_name="dup.txt", integration_id="gdrive", external_id="x2",
                  created_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
        _ingested(db, "doc-3", file_name="dup.txt", integration_id="gdrive", external_id="x3",
                  created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert match_pg_row(db, {"file_name": "dup.txt", "integration_id": "gdrive"}, "l") == "doc-3"

    def test_no_match_returns_none(self, db):
        _ingested(db, "doc-1", file_name="report.txt", external_id="x1")
        assert match_pg_row(db, {"external_id": "nope", "file_name": "nope.txt"}, "l") is None

    def test_empty_metadata(self, db):
        assert match_pg_row(db, {}, "l") is None


# ============================================================================
# core/hybrid_search/lexical_ranker.py
# ============================================================================


def _mock_sqlite_session(rows, found=True, bind_name="sqlite"):
    db = MagicMock()
    execute = MagicMock()
    execute.fetchall.return_value = rows
    execute.first.return_value = object() if found else None
    db.execute.return_value = execute
    db.bind = SimpleNamespace(dialect=SimpleNamespace(name=bind_name))
    return db


def _row(**kwargs):
    return SimpleNamespace(**kwargs)


class TestQuerySafeTokens:
    def test_filters_tokens(self):
        assert _query_safe_tokens("Hello WORLD 123 !! a") == ["hello", "world", "123"]

    def test_no_valid_tokens(self):
        assert _query_safe_tokens("!! ??") == []


class TestFtsTableExists:
    def test_bind_none(self):
        db = MagicMock()
        db.bind = None
        assert _fts_table_exists(db, "x") is False

    def test_sqlite_found(self):
        db = _mock_sqlite_session([], found=True)
        assert _fts_table_exists(db, "ingested_documents_fts") is True

    def test_sqlite_missing(self):
        db = _mock_sqlite_session([], found=False)
        assert _fts_table_exists(db, "ingested_documents_fts") is False

    def test_postgres_found(self):
        db = _mock_sqlite_session([], found=True, bind_name="postgresql")
        assert _fts_table_exists(db, "ingested_documents_fts") is True

    def test_postgres_missing(self):
        db = _mock_sqlite_session([], found=False, bind_name="postgresql")
        assert _fts_table_exists(db, "ingested_documents_fts") is False

    def test_exception_returns_false(self):
        db = MagicMock()
        db.bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
        db.execute.side_effect = RuntimeError("db down")
        assert _fts_table_exists(db, "x") is False

    def test_other_dialect_false(self):
        db = _mock_sqlite_session([], bind_name="oracle")
        assert _fts_table_exists(db, "x") is False


class TestSearchIngestedSqlite:
    def test_since_and_author(self):
        row = _row(id="d1", file_name="f1", content_preview="preview",
                   external_modified_at=datetime(2026, 1, 1, tzinfo=timezone.utc), rank=2.0)
        db = _mock_sqlite_session([row])
        results = _search_ingested_sqlite(db, "q*", 10, since=datetime(2026, 1, 1), author="gdrive")
        assert results[0]["source"] == "ingested"
        assert results[0]["lexical_mode"] == "fts5_bm25"
        assert results[0]["modified"] == "2026-01-01T00:00:00+00:00"
        assert results[0]["rank"] == 2.0
        assert results[0]["score"] > 0

    def test_no_since_no_author_null_fields(self):
        row = _row(id="d1", file_name="f1", content_preview=None,
                   external_modified_at=None, rank=None)
        db = _mock_sqlite_session([row])
        results = _search_ingested_sqlite(db, "q*", 10, since=None, author=None)
        assert results[0]["preview"] == ""
        assert results[0]["modified"] is None
        assert results[0]["rank"] == 0.0

    def test_empty_rows(self):
        db = _mock_sqlite_session([])
        assert _search_ingested_sqlite(db, "q*", 10, None, None) == []


class TestSearchKnowledgeSqlite:
    def test_since_and_content(self):
        row = _row(id="k1", title="title", content="some content", rank=3.0)
        db = _mock_sqlite_session([row])
        results = _search_knowledge_sqlite(db, "q*", 10, since=datetime(2026, 1, 1))
        assert results[0]["source"] == "knowledge"
        assert results[0]["title"] == "title"
        assert results[0]["modified"] is None
        assert results[0]["rank"] == 3.0

    def test_no_since_null_content(self):
        row = _row(id="k1", title="title", content=None, rank=None)
        db = _mock_sqlite_session([row])
        results = _search_knowledge_sqlite(db, "q*", 10, since=None)
        assert results[0]["preview"] == ""
        assert results[0]["rank"] == 0.0

    def test_empty_rows(self):
        db = _mock_sqlite_session([])
        assert _search_knowledge_sqlite(db, "q*", 10, None) == []


class TestSearchIngestedPg:
    def test_with_since_author_modified(self):
        row = _row(id="d1", file_name="f1", content_preview="p",
                   external_modified_at=datetime(2026, 2, 2, tzinfo=timezone.utc), rank=1.0)
        db = _mock_sqlite_session([row], bind_name="postgresql")
        results = _search_ingested_pg(db, "query", 10, since=datetime(2026, 1, 1), author="x")
        assert results[0]["lexical_mode"] == "tsvector_rank"
        assert results[0]["modified"] == "2026-02-02T00:00:00+00:00"

    def test_without_filters_nulls(self):
        row = _row(id="d1", file_name="f1", content_preview=None,
                   external_modified_at=None, rank=None)
        db = _mock_sqlite_session([row], bind_name="postgresql")
        results = _search_ingested_pg(db, "query", 10, since=None, author=None)
        assert results[0]["modified"] is None
        assert results[0]["rank"] == 0.0


class TestSearchKnowledgePg:
    def test_with_since(self):
        row = _row(id="k1", title="t", content="c", rank=2.5)
        db = _mock_sqlite_session([row], bind_name="postgresql")
        results = _search_knowledge_pg(db, "query", 10, since=datetime(2026, 1, 1))
        assert results[0]["lexical_mode"] == "tsvector_rank"
        assert results[0]["modified"] is None

    def test_no_since_null_content(self):
        row = _row(id="k1", title="t", content=None, rank=None)
        db = _mock_sqlite_session([row], bind_name="postgresql")
        results = _search_knowledge_pg(db, "query", 10, since=None)
        assert results[0]["preview"] == ""


class TestColumnExistsPg:
    def test_found(self):
        db = _mock_sqlite_session([], found=True, bind_name="postgresql")
        assert _column_exists_pg(db, "t", "c") is True

    def test_missing(self):
        db = _mock_sqlite_session([], found=False, bind_name="postgresql")
        assert _column_exists_pg(db, "t", "c") is False

    def test_exception(self):
        db = MagicMock()
        db.execute.side_effect = RuntimeError("db down")
        assert _column_exists_pg(db, "t", "c") is False


class TestSearchIlikeFallback:
    def test_both_sources(self, db):
        _ingested(db, "doc-1", content="alpha beta")
        _knowledge(db, "k-1", content="alpha beta")
        results = _search_iliike_fallback(db, "alpha", 50, since=None, source=None, author=None)
        assert {r["source"] for r in results} == {"ingested", "knowledge"}
        assert all(r["lexical_mode"] == "iliike_fallback" for r in results)

    def test_ingested_only(self, db):
        _ingested(db, "doc-1", content="alpha beta")
        _knowledge(db, "k-1", content="alpha beta")
        results = _search_iliike_fallback(db, "alpha", 50, None, "ingested", None)
        assert [r["source"] for r in results] == ["ingested"]

    def test_knowledge_only(self, db):
        _ingested(db, "doc-1", content="alpha beta")
        _knowledge(db, "k-1", content="alpha beta")
        results = _search_iliike_fallback(db, "alpha", 50, None, "knowledge", None)
        assert [r["source"] for r in results] == ["knowledge"]

    def test_title_hit_and_content_hit_weights(self, db):
        _ingested(db, "doc-1", file_name="alpha report", content="nothing here")
        results = _search_iliike_fallback(db, "alpha", 50, None, None, None)
        assert len(results) == 1
        assert results[0]["score"] == round(3.0 / 4.0, 6)

    def test_since_filter(self, db):
        _ingested(db, "doc-1", content="alpha beta", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        results = _search_iliike_fallback(
            db, "alpha", 50, since=datetime(2026, 1, 2, tzinfo=timezone.utc), source=None, author=None
        )
        assert results == []

    def test_author_filter(self, db):
        _ingested(db, "doc-1", content="alpha beta", integration_id="gdrive")
        _ingested(db, "doc-2", content="alpha beta", integration_id="dropbox")
        results = _search_iliike_fallback(db, "alpha", 50, None, None, "drive")
        assert [r["id"] for r in results] == ["doc-1"]

    def test_knowledge_since_filter(self, db):
        _knowledge(db, "k-1", content="alpha beta", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        results = _search_iliike_fallback(
            db, "alpha", 50, since=datetime(2026, 1, 2, tzinfo=timezone.utc), source="knowledge", author=None
        )
        assert results == []

    def test_wildcard_needle_skips_row(self, db):
        # SQLite ILIKE treats % as wildcard → prefilter passes; the python
        # `in` needle check fails → row skipped by the defensive branch.
        _ingested(db, "doc-1", content="aXb")
        _knowledge(db, "k-1", content="aXb")
        results = _search_iliike_fallback(db, "a%b", 50, None, None, None)
        assert results == []

    def test_sorted_by_score_and_limit(self, db):
        _ingested(db, "doc-1", file_name="alpha file", content="alpha")  # both hits
        _ingested(db, "doc-2", content="alpha only here")
        results = _search_iliike_fallback(db, "alpha", 1, None, None, None)
        assert len(results) == 1
        assert results[0]["id"] == "doc-1"

    def test_no_matches(self, db):
        _ingested(db, "doc-1", content="nothing relevant")
        assert _search_iliike_fallback(db, "zzz", 50, None, None, None) == []

    def test_empty_db(self, db):
        assert _search_iliike_fallback(db, "alpha", 50, None, None, None) == []


class TestSearchDocumentsLexical:
    def test_none_query(self, db):
        assert search_documents_lexical(db, None) == []

    def test_short_query(self, db):
        assert search_documents_lexical(db, "ab") == []

    def test_whitespace_query(self, db):
        assert search_documents_lexical(db, "   ") == []

    def test_no_safe_tokens(self, db):
        assert search_documents_lexical(db, "!! ??") == []

    def test_stopword_only_routes_to_iliike(self, db):
        _ingested(db, "doc-1", content="understand the plan")
        results = search_documents_lexical(db, "and")
        assert results and results[0]["lexical_mode"] == "iliike_fallback"

    def test_bind_none_falls_back(self, db):
        from sqlalchemy.orm import Session

        bare = Session.__new__(Session)  # no bind
        _ingested(db, "doc-1", content="alpha beta")
        # patch the session's bind off — query still works via engine-backed db
        results = search_documents_lexical(_NoBindSession(bare, db), "alpha")
        assert results[0]["lexical_mode"] == "iliike_fallback"

    def test_sqlite_fts_both_tables(self):
        row_i = _row(id="d1", file_name="f", content_preview="c",
                     external_modified_at=None, rank=1.0,
                     title="ti", content="ci")
        row_k = _row(id="k1", title="t", content="c", rank=2.0,
                     file_name="kf", content_preview="kc", external_modified_at=None)
        db = _mock_sqlite_session([row_i, row_k])
        results = search_documents_lexical(db, "hello world", limit=50, source=None, author=None)
        assert {r["source"] for r in results} == {"ingested", "knowledge"}
        assert len(results) == 4  # both legs see both mocked rows
        assert results[0]["lexical_mode"] == "fts5_bm25"

    def test_sqlite_fts_ingested_source_only(self):
        row_i = _row(id="d1", file_name="f", content_preview="c",
                     external_modified_at=None, rank=1.0,
                     title="ti", content="ci")
        row_k = _row(id="k1", title="t", content="c", rank=2.0,
                     file_name="kf", content_preview="kc", external_modified_at=None)
        db = _mock_sqlite_session([row_i, row_k])
        results = search_documents_lexical(db, "hello world", source="ingested")
        # both mocked rows flow through the ingested leg
        assert [r["source"] for r in results] == ["ingested", "ingested"]
        assert all(r["id"] in ("d1", "k1") for r in results)

    def test_sqlite_fts_knowledge_source_only(self):
        row_i = _row(id="d1", file_name="f", content_preview="c",
                     external_modified_at=None, rank=1.0,
                     title="ti", content="ci")
        row_k = _row(id="k1", title="t", content="c", rank=2.0,
                     file_name="kf", content_preview="kc", external_modified_at=None)
        db = _mock_sqlite_session([row_i, row_k])
        results = search_documents_lexical(db, "hello world", source="knowledge")
        assert [r["source"] for r in results] == ["knowledge", "knowledge"]

    def test_sqlite_missing_fts_tables_falls_back(self, db):
        _ingested(db, "doc-1", content="alpha beta")
        results = search_documents_lexical(db, "alpha")
        assert results[0]["lexical_mode"] == "iliike_fallback"

    def test_postgres_has_vector(self):
        row_i = _row(id="d1", file_name="f", content_preview="c",
                     external_modified_at=None, rank=1.0,
                     title="ti", content="ci")
        row_k = _row(id="k1", title="t", content="c", rank=2.0,
                     file_name="kf", content_preview="kc", external_modified_at=None)
        db = _mock_sqlite_session([row_i, row_k], bind_name="postgresql")
        results = search_documents_lexical(db, "hello world", since=None, source=None, author="a")
        assert {r["source"] for r in results} == {"ingested", "knowledge"}
        assert all(r["lexical_mode"] == "tsvector_rank" for r in results)

    def test_postgres_ingested_source_only(self):
        row_i = _row(id="d1", file_name="f", content_preview="c",
                     external_modified_at=None, rank=1.0)
        db = _mock_sqlite_session([row_i], bind_name="postgresql")
        results = search_documents_lexical(db, "hello world", source="ingested")
        assert [r["source"] for r in results] == ["ingested"]

    def test_postgres_missing_vector_column_falls_back(self):
        db = _mock_sqlite_session([], found=True, bind_name="postgresql")
        with patch("core.hybrid_search.lexical_ranker._fts_table_exists", return_value=True):
            with patch("core.hybrid_search.lexical_ranker._column_exists_pg", return_value=False):
                # ILIKE fallback runs against the mocked session: iterating the
                # mocked query raises -> outer guard swallows -> []
                assert search_documents_lexical(db, "alpha") == []

    def test_other_dialect_falls_back(self, db):
        _ingested(db, "doc-1", content="alpha beta")
        with patch("core.hybrid_search.lexical_ranker._fts_table_exists", return_value=False):
            results = search_documents_lexical(db, "alpha")
        assert results[0]["lexical_mode"] == "iliike_fallback"

    def test_unknown_dialect_final_fallback(self, db):
        _ingested(db, "doc-1", content="alpha beta")
        with patch.object(db.bind.dialect, "name", "oracle"):
            results = search_documents_lexical(db, "alpha")
        assert results[0]["lexical_mode"] == "iliike_fallback"

    def test_exception_returns_empty(self, db):
        with patch(
            "core.hybrid_search.lexical_ranker._query_safe_tokens",
            side_effect=RuntimeError("tokenizer boom"),
        ):
            assert search_documents_lexical(db, "hello world") == []


class _NoBindSession:
    """Session-like wrapper with a None bind but a working query delegate."""

    def __init__(self, session, real_db):
        self._session = session
        self._real_db = real_db

    @property
    def bind(self):
        return None

    def query(self, *args, **kwargs):
        return self._real_db.query(*args, **kwargs)

    def execute(self, *args, **kwargs):
        return self._real_db.execute(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ============================================================================
# core/hybrid_search/documents_hybrid.py
# ============================================================================


class TestDocumentsHybridSearch:
    @pytest.fixture(autouse=True)
    def _hermetic(self, monkeypatch):
        # The conversations leg reads the REAL shared LanceDB comms store and
        # appends hits + a "+conversations" label suffix — non-hermetic in a
        # dev env with ingested communications. These tests cover the
        # documents legs only.
        monkeypatch.setenv("MEMORY_CONVERSATIONS_LEG", "false")

    async def test_short_query_no_results(self, db):
        svc = DocumentsHybridSearch(db=db)
        result = await svc.search("ab")
        assert result["hybrid"] == "no_results"
        assert result["results"] == []
        assert result["stats"] == {}

    async def test_bm25_vector_rrf_label(self, db):
        _ingested(db, "doc-1", content="quarterly report figures")
        lancedb = _FakeLanceDB([{"id": "doc-1", "_distance": 0.4, "metadata": {"x": 1}}])
        svc = DocumentsHybridSearch(db=db, lancedb=lancedb)
        result = await svc.search("quarterly report", limit=10)
        assert result["hybrid"] == "bm25_vector_rrf"
        assert result["stats"]["lexical_hits"] == 1
        assert result["stats"]["vector_hits"] == 1
        ids = [r["id"] for r in result["results"]]
        assert "doc-1" in ids
        assert all(r["bridged"] for r in result["results"])
        assert result["results"][0]["score"] > 0

    async def test_lexical_only_label(self, db):
        _ingested(db, "doc-1", content="quarterly report figures")
        svc = DocumentsHybridSearch(db=db, lancedb=_FakeLanceDB([]))
        result = await svc.search("quarterly report")
        assert result["hybrid"] == "lexical_only"

    async def test_semantic_only_label(self, db):
        _ingested(db, "doc-1", content="nothing matching here")
        lancedb = _FakeLanceDB([{"id": "doc-1", "_distance": 0.2}])
        svc = DocumentsHybridSearch(db=db, lancedb=lancedb)
        result = await svc.search("zzzqqq")
        assert result["hybrid"] == "semantic_only"
        assert [r["id"] for r in result["results"]] == ["doc-1"]

    async def test_no_results_label(self, db):
        _ingested(db, "doc-1", content="nothing matching here")
        svc = DocumentsHybridSearch(db=db, lancedb=_FakeLanceDB([]))
        result = await svc.search("zzzqqq")
        assert result["hybrid"] == "no_results"
        assert result["results"] == []

    async def test_vector_leg_disabled_env(self, db):
        _ingested(db, "doc-1", content="quarterly report figures")
        with patch.dict(os.environ, {"ATOM_HYBRID_VECTOR_LEG_ENABLED": "false"}):
            svc = DocumentsHybridSearch(db=db, lancedb=_FakeLanceDB([{"id": "doc-1"}]))
            result = await svc.search("quarterly report")
        assert result["hybrid"] == "lexical_only"
        assert "vector_hits" in result["stats"]

    async def test_source_knowledge_skips_vector_leg(self, db):
        _knowledge(db, "k-1", content="quarterly report knowledge")
        svc = DocumentsHybridSearch(db=db, lancedb=_FakeLanceDB([{"id": "doc-1"}]))
        result = await svc.search("quarterly report", source="knowledge")
        assert result["hybrid"] == "lexical_only"
        assert result["stats"]["vector_hits"] == 0

    async def test_unbridged_vector_hits_surfaced_flagged(self, db):
        _ingested(db, "doc-1", content="quarterly report figures")
        lancedb = _FakeLanceDB(
            [
                {"id": "doc-1", "_distance": 0.1},
                {"id": "orphan-id", "_distance": 0.2,
                 "metadata": {"file_name": "orphan.pdf"}},
            ]
        )
        svc = DocumentsHybridSearch(db=db, lancedb=lancedb)
        result = await svc.search("quarterly report")
        assert result["stats"]["unbridged_hits"] == 1
        ids = [r["id"] for r in result["results"]]
        assert "orphan-id" in ids, "unbridged hits are surfaced, not dropped"
        orphan = next(r for r in result["results"] if r["id"] == "orphan-id")
        assert orphan["bridged"] is False
        assert orphan["title"] == "orphan.pdf"

    async def test_vector_leg_missing_id_dropped(self, db):
        _ingested(db, "doc-1", content="quarterly report figures")
        lancedb = _FakeLanceDB([{"_distance": 0.1}, {"id": "", "_distance": 0.2}])
        svc = DocumentsHybridSearch(db=db, lancedb=lancedb)
        result = await svc.search("quarterly report")
        assert result["stats"]["vector_hits"] == 0

    async def test_vector_leg_exception_returns_empty(self, db):
        _ingested(db, "doc-1", content="quarterly report figures")
        lancedb = _FakeLanceDB([], error=RuntimeError("lancedb down"))
        svc = DocumentsHybridSearch(db=db, lancedb=lancedb)
        result = await svc.search("quarterly report")
        assert result["hybrid"] == "lexical_only"
        assert result["stats"]["vector_hits"] == 0

    async def test_lancedb_none_uses_default_handler(self, db):
        _ingested(db, "doc-1", content="quarterly report figures")
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=None):
            svc = DocumentsHybridSearch(db=db)
            result = await svc.search("quarterly report")
        assert result["hybrid"] == "lexical_only"

    async def test_get_db_default_session(self):
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        svc = DocumentsHybridSearch()
        with patch("core.database.get_db_session", return_value=session):
            assert svc._get_db() is session

    async def test_search_exception_returns_no_results(self, db):
        svc = DocumentsHybridSearch(db=db)
        with patch.object(
            svc, "_lexical_leg", side_effect=RuntimeError("leg boom")
        ):
            result = await svc.search("quarterly report")
        assert result["hybrid"] == "no_results"
        assert result["stats"] == {}

    async def test_hydration_lookup_exception_treated_as_unbridged(self, db):
        _ingested(db, "doc-1", content="quarterly report figures")
        lancedb = _FakeLanceDB([{"id": "doc-1", "_distance": 0.1}])
        svc = DocumentsHybridSearch(db=db, lancedb=lancedb)

        class _BoomDoc:
            id = None  # unmapped class -> query raises ArgumentError

        with patch("core.models.IngestedDocument", _BoomDoc):
            result = await svc.search("quarterly report")
        assert result["stats"]["unbridged_hits"] == 1
        # Hydration failure → every vector hit is unbridged but STILL surfaced.
        orphan = next(r for r in result["results"] if r["id"] == "doc-1")
        assert orphan["bridged"] is False

    def test_fuse_rrf_lexical_only(self, db):
        svc = DocumentsHybridSearch(db=db)
        lexical = [{"source": "ingested", "id": "d1", "title": "t", "preview": "p"}]
        fused, unbridged = svc._fuse_rrf(lexical, [])
        assert unbridged == 0
        assert fused[0]["legs"] == ["lexical"]
        assert fused[0]["rrf"] == 1.0 / 61.0

    def test_fuse_rrf_vector_bridged_and_unbridged(self, db):
        _ingested(db, "doc-1", content="x", external_modified_at=datetime(2026, 3, 3, tzinfo=timezone.utc))
        svc = DocumentsHybridSearch(db=db)
        fused, unbridged = svc._fuse_rrf(
            [],
            [{"id": "doc-1", "score": 0.5}, {"id": "ghost", "score": 0.9}],
        )
        assert unbridged == 1
        assert len(fused) == 2
        entry = next(e for e in fused if e["id"] == "doc-1")
        assert entry["source"] == "ingested"
        assert entry["title"] == "quarterly report"
        assert entry["preview"] == "x"
        assert entry["modified"] == "2026-03-03T00:00:00"
        assert entry["legs"] == ["vector"]
        assert entry["rrf"] == 1.0 / 61.0
        ghost = next(e for e in fused if e["id"] == "ghost")
        assert ghost["source"] == "vector"
        assert ghost["bridged"] is False
        # doc-1 outranks ghost despite worse vector rank (ghost has no legs tiebreak? no —
        # ghost ranked FIRST on the vector leg so it has better rrf; sort is by rrf only)
        ids = [e["id"] for e in fused]
        assert set(ids) == {"doc-1", "ghost"}

    def test_fuse_rrf_merge_sort(self, db):
        _ingested(db, "doc-1", content="alpha beta")
        svc = DocumentsHybridSearch(db=db)
        lexical = [
            {"source": "ingested", "id": "doc-1", "title": "t"},
            {"source": "ingested", "id": "doc-2", "title": "t"},
        ]
        vector = [{"id": "doc-1", "score": 0.1}]
        fused, unbridged = svc._fuse_rrf(lexical, vector)
        assert unbridged == 0
        assert fused[0]["id"] == "doc-1"  # rrf 1/61+1/62 > 1/62
        assert fused[0]["legs"] == ["lexical", "vector"]

    def test_fuse_rrf_hydration_exception(self, db):
        svc = DocumentsHybridSearch(db=db)
        with patch.object(svc, "_get_db", side_effect=RuntimeError("boom")):
            fused, unbridged = svc._fuse_rrf([], [{"id": "ghost"}])
        assert unbridged == 1
        # Hydration failed → the hit is surfaced as an unbridged vector row.
        assert len(fused) == 1
        assert fused[0]["id"] == "ghost"
        assert fused[0]["bridged"] is False

    def test_hydrate(self, db):
        svc = DocumentsHybridSearch(db=db)
        fused = [
            {"source": "ingested", "id": "d1", "title": "t", "preview": "p",
             "rrf": 0.016393, "modified": None, "bridged": True},
        ]
        hydrated = svc._hydrate(fused)
        assert hydrated[0]["score"] == 0.016393
        assert hydrated[0]["bridged"] is True

    def test_response(self):
        resp = DocumentsHybridSearch._response("q", [{"id": 1}], "lexical_only", {"x": 1})
        assert resp == {
            "success": True,
            "query": "q",
            "results": [{"id": 1}],
            "hybrid": "lexical_only",
            "stats": {"x": 1},
        }
