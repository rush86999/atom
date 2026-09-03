"""Coverage wave 8 — core.hybrid_search gaps (complements tests/core/* suites).

Covers the branches the existing suites skip: FTS-table-absence fallbacks,
PG dialect branches, stopword routing, docs_hybrid error paths + kill switch,
backfill match legs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import Base, IngestedDocument, KnowledgeDocument


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    yield Session()
    engine.dispose()


def _seed(db):
    db.add_all(
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
            KnowledgeDocument(
                id="kd_1",
                workspace_id="default",
                tenant_id="default",
                title="Sales Playbook",
                content="Upsell motion for enterprise accounts.",
            ),
        ]
    )
    db.commit()


class TestLexicalRankerGaps:
    def test_query_safe_tokens(self):
        from core.hybrid_search.lexical_ranker import _query_safe_tokens

        assert _query_safe_tokens("Hello World!") == ["hello", "world"]
        assert _query_safe_tokens("a b c") == []  # <2 chars dropped
        assert _query_safe_tokens("") == []

    def test_fts_table_exists_no_bind(self):
        from core.hybrid_search.lexical_ranker import _fts_table_exists

        s = MagicMock()
        s.bind = None
        assert _fts_table_exists(s, "x") is False

    def test_fts_table_exists_sqlite_missing(self, db):
        from core.hybrid_search.lexical_ranker import _fts_table_exists

        assert _fts_table_exists(db, "ingested_documents_fts") is False

    def test_fts_table_exists_sqlite_present(self, db):
        from sqlalchemy import text

        db.execute(
            text(
                "CREATE VIRTUAL TABLE ingested_documents_fts USING fts5(file_name, content_preview)"
            )
        )
        db.commit()
        from core.hybrid_search.lexical_ranker import _fts_table_exists

        assert _fts_table_exists(db, "ingested_documents_fts") is True

    def test_fts_table_exists_postgresql(self):
        from core.hybrid_search.lexical_ranker import _fts_table_exists

        s = MagicMock()
        s.bind.dialect.name = "postgresql"
        s.execute.return_value.first.return_value = ("x",)
        assert _fts_table_exists(s, "some_table") is True
        s.execute.return_value.first.return_value = None
        assert _fts_table_exists(s, "some_table") is False

    def test_fts_table_exists_exception(self):
        from core.hybrid_search.lexical_ranker import _fts_table_exists

        s = MagicMock()
        s.bind.dialect.name = "sqlite"
        s.execute.side_effect = RuntimeError("db down")
        assert _fts_table_exists(s, "x") is False

    def test_short_query_returns_empty(self, db):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        assert search_documents_lexical(db, "") == []
        assert search_documents_lexical(db, "  ab ") == []  # <3 chars

    def test_no_safe_tokens_returns_empty(self, db):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        # query >= 3 chars but no >=2-char alphanumeric tokens
        assert search_documents_lexical(db, "!!! ###") == []

    def test_no_bind_falls_back(self):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        s = MagicMock()
        s.bind = None
        # ILIKE fallback path with empty DB (never raises)
        result = search_documents_lexical(s, "revenue")
        assert result == []

    def test_stopword_query_routes_to_iliike(self, db):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        _seed(db)
        results = search_documents_lexical(db, "the and of", source=None)
        # ILIKE fallback matches "and"-containing content? "the"/"of" tokens
        # match title/content substrings case-insensitively
        assert isinstance(results, list)
        for r in results:
            assert r["lexical_mode"] == "iliike_fallback"

    def test_iliike_fallback_ingested_only(self, db):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        _seed(db)
        results = search_documents_lexical(db, "revenue", source="ingested")
        assert results
        assert all(r["source"] == "ingested" for r in results)
        assert results[0]["lexical_mode"] == "iliike_fallback"

    def test_iliike_fallback_knowledge_only(self, db):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        _seed(db)
        results = search_documents_lexical(db, "playbook", source="knowledge")
        assert results
        assert all(r["source"] == "knowledge" for r in results)

    def test_iliike_fallback_author_filter(self, db):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        _seed(db)
        results = search_documents_lexical(db, "revenue", author="google_drive")
        assert results and results[0]["source"] == "ingested"
        results2 = search_documents_lexical(db, "revenue", author="no_such_drive")
        assert results2 == []

    def test_iliike_fallback_since_filter(self, db):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        _seed(db)
        future = datetime(2030, 1, 1, tzinfo=timezone.utc)
        assert search_documents_lexical(db, "revenue", since=future) == []

    def test_iliike_no_hits_after_prefilter(self, db):
        """Rows caught by ILIKE prefilter but without a real substring match
        (e.g. '%revenue%' vs 'rev enue') are skipped."""
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        db.add(
            IngestedDocument(
                id="doc_x",
                workspace_id="default",
                file_name="rev enue.pdf",
                file_path="/x.pdf",
                file_type="pdf",
                integration_id="g",
                file_size_bytes=1,
                content_preview="rev enue split",
                external_id="e-x",
                ingested_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        results = search_documents_lexical(db, "revenue", source="ingested")
        assert results == []

    def test_pg_vector_path(self):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        s = MagicMock()
        s.bind.dialect.name = "postgresql"

        def fake_first():
            return ("row",)

        s.execute.return_value.first.side_effect = fake_first
        # _fts_table_exists(ingested_documents) True + column exists → PG leg
        rows = [
            MagicMock(
                id="1",
                file_name="f.pdf",
                content_preview="c",
                external_modified_at=datetime.now(timezone.utc),
                rank=0.5,
            )
        ]
        s.execute.return_value.fetchall.return_value = rows
        results = search_documents_lexical(s, "revenue", source="ingested")
        assert results and results[0]["lexical_mode"] == "tsvector_rank"

    def test_pg_vector_path_since_author_and_knowledge(self):
        """PG legs with since + author filters and the knowledge table."""
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        s = MagicMock()
        s.bind.dialect.name = "postgresql"
        s.execute.return_value.first.return_value = ("row",)
        rows = [
            MagicMock(
                id="1",
                file_name="f.pdf",
                content_preview="c",
                external_modified_at=datetime.now(timezone.utc),
                rank=0.5,
            )
        ]
        s.execute.return_value.fetchall.return_value = rows
        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        results = search_documents_lexical(
            s, "revenue", source="ingested", since=since, author="drive"
        )
        assert results and results[0]["lexical_mode"] == "tsvector_rank"
        # knowledge leg (has no author param)
        results2 = search_documents_lexical(s, "revenue", source="knowledge", since=since)
        assert results2 and results2[0]["lexical_mode"] == "tsvector_rank"

    def test_fts5_full_path(self, db):
        """Real FTS5 tables: bm25 ranking + since/author filters."""
        from sqlalchemy import text as sa_text

        db.execute(
            sa_text(
                "CREATE VIRTUAL TABLE ingested_documents_fts USING fts5("
                "file_name, content_preview, content='ingested_documents', content_rowid='rowid')"
            )
        )
        db.execute(
            sa_text(
                "CREATE VIRTUAL TABLE knowledge_documents_fts USING fts5("
                "title, content, content='knowledge_documents', content_rowid='rowid')"
            )
        )
        db.commit()
        _seed(db)
        db.execute(sa_text("INSERT INTO ingested_documents_fts(rowid, file_name, content_preview) SELECT rowid, file_name, content_preview FROM ingested_documents"))
        db.execute(sa_text("INSERT INTO knowledge_documents_fts(rowid, title, content) SELECT rowid, title, content FROM knowledge_documents"))
        db.commit()

        from core.hybrid_search.lexical_ranker import search_documents_lexical

        # both sources, no filters
        results = search_documents_lexical(db, "revenue")
        assert results and results[0]["lexical_mode"] == "fts5_bm25"
        assert any(r["source"] == "ingested" for r in results)
        # ingested + author filter
        results2 = search_documents_lexical(db, "revenue", source="ingested", author="google_drive")
        assert results2 and results2[0]["source"] == "ingested"
        # ingested + since filter
        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        results3 = search_documents_lexical(db, "revenue", source="ingested", since=since)
        assert results3 and results3[0]["lexical_mode"] == "fts5_bm25"
        # knowledge source
        results4 = search_documents_lexical(db, "playbook", source="knowledge")
        assert results4 and results4[0]["source"] == "knowledge"
        assert results4[0]["lexical_mode"] == "fts5_bm25"
        # knowledge + since
        results5 = search_documents_lexical(db, "playbook", source="knowledge", since=since)
        assert results5
        # no hits
        assert search_documents_lexical(db, "zzzzz") == []

    def test_pg_missing_vector_column_falls_back(self):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        s = MagicMock()
        s.bind.dialect.name = "postgresql"
        s.execute.return_value.first.return_value = None  # no search_vector column
        results = search_documents_lexical(s, "revenue", source="ingested")
        assert results == []  # ILIKE on an empty mock DB

    def test_column_exists_pg(self):
        from core.hybrid_search.lexical_ranker import _column_exists_pg

        s = MagicMock()
        s.execute.return_value.first.return_value = ("x",)
        assert _column_exists_pg(s, "t", "c") is True
        s.execute.return_value.first.return_value = None
        assert _column_exists_pg(s, "t", "c") is False

    def test_column_exists_pg_exception(self):
        from core.hybrid_search.lexical_ranker import _column_exists_pg

        s = MagicMock()
        s.execute.side_effect = RuntimeError("boom")
        assert _column_exists_pg(s, "t", "c") is False

    def test_unknown_dialect_falls_back(self, db):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        engine = create_engine("sqlite:///:memory:")
        s = MagicMock()
        s.bind = engine
        s.bind.dialect.name = "mysql"
        results = search_documents_lexical(s, "revenue")
        assert results == []

    def test_iliike_prefilter_hit_but_substring_miss(self, db):
        """ILIKE '%rev%enue%' matches but the literal needle 'rev%enue' is
        NOT a substring → row is skipped by the exact-substring check."""
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        _seed(db)
        results = search_documents_lexical(db, "rev%enue", source="ingested")
        assert results == []

    def test_iliike_knowledge_substring_miss(self, db):
        """Knowledge-doc rows passing the ILIKE prefilter but failing the
        exact-substring check are skipped too."""
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        _seed(db)
        # 'upse%ll' ILIKE-matches "Upsell motion" but is not a substring
        results = search_documents_lexical(db, "upse%ll", source="knowledge")
        assert results == []

    def test_top_level_exception_returns_empty(self, db):
        from core.hybrid_search.lexical_ranker import search_documents_lexical

        with patch(
            "core.hybrid_search.lexical_ranker._query_safe_tokens",
            side_effect=RuntimeError("unexpected"),
        ):
            assert search_documents_lexical(db, "revenue") == []


class TestDocumentsHybridGaps:
    def test_search_short_query(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch()
        import asyncio

        result = asyncio.run(svc.search("ab"))
        assert result["hybrid"] == "no_results"
        assert result["results"] == []

    def test_search_gather_failure(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch()
        with patch.object(svc, "_lexical_leg", side_effect=RuntimeError("boom")):
            import asyncio

            result = asyncio.run(svc.search("revenue"))
        assert result["hybrid"] == "no_results"

    def test_lexical_only_label(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch()
        with patch.object(svc, "_lexical_leg", return_value=[{"source": "ingested", "id": "1"}]):
            with patch.object(svc, "_vector_leg", return_value=[]):
                # Conversations leg off — this test pins the document-legs
                # label composition (that slice has its own coverage).
                with patch("core.experiments.is_enabled", return_value=False):
                    import asyncio

                    result = asyncio.run(svc.search("revenue"))
        assert result["hybrid"] == "lexical_only"

    def test_semantic_only_label(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch()
        with patch.object(svc, "_lexical_leg", return_value=[]):
            with patch.object(svc, "_vector_leg", return_value=[{"id": "1", "_distance": 0.5}]):
                with patch.object(
                    svc,
                    "_fuse_rrf",
                    return_value=(
                        [
                            {
                                "source": "ingested",
                                "id": "1",
                                "title": "t",
                                "preview": "p",
                                "modified": None,
                                "bridged": True,
                                "legs": ["vector"],
                                "rrf": 0.05,
                            }
                        ],
                        0,
                    ),
                ):
                    with patch("core.experiments.is_enabled", return_value=False):
                        import asyncio

                        result = asyncio.run(svc.search("revenue"))
        assert result["hybrid"] == "semantic_only"

    def test_get_db_uses_session(self, db):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch(db=db)
        assert svc._get_db() is db

    def test_get_db_fallback_session(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch()
        fake = MagicMock()
        fake.__enter__ = MagicMock(return_value=fake)
        fake.__exit__ = MagicMock(return_value=False)
        with patch("core.database.get_db_session", return_value=fake):
            assert svc._get_db() is fake

    def test_vector_leg_kill_switch(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch()
        import asyncio

        with patch(
            "core.hybrid_search.documents_hybrid._vector_leg_enabled",
            return_value=False,
        ):
            assert asyncio.run(svc._vector_leg("q", 10)) == []

    def test_vector_leg_knowledge_source_skipped(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch()
        import asyncio

        with patch(
            "core.hybrid_search.documents_hybrid._vector_leg_enabled",
            return_value=True,
        ):
            assert asyncio.run(svc._vector_leg("q", 10, source="knowledge")) == []

    def test_vector_leg_lazy_lancedb(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch()
        import asyncio

        lancedb = MagicMock()
        lancedb.search.return_value = [
            {"id": "1", "_distance": 0.2, "metadata": {"a": 1}},
            {"id": "", "_distance": 0.5},  # no id → filtered
        ]
        with patch(
            "core.hybrid_search.documents_hybrid._vector_leg_enabled",
            return_value=True,
        ):
            with patch(
                "core.lancedb_handler.get_lancedb_handler",
                return_value=lancedb,
            ):
                rows = asyncio.run(svc._vector_leg("q", 10))
        assert rows == [{"id": "1", "score": 0.2, "metadata": {"a": 1}}]

    def test_vector_leg_lancedb_none(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch()
        import asyncio

        with patch(
            "core.hybrid_search.documents_hybrid._vector_leg_enabled",
            return_value=True,
        ):
            with patch(
                "core.lancedb_handler.get_lancedb_handler",
                return_value=None,
            ):
                assert asyncio.run(svc._vector_leg("q", 10)) == []

    def test_vector_leg_exception(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch(lancedb=MagicMock())
        svc._lancedb.search.side_effect = RuntimeError("LanceDB down")
        import asyncio

        with patch(
            "core.hybrid_search.documents_hybrid._vector_leg_enabled",
            return_value=True,
        ):
            assert asyncio.run(svc._vector_leg("q", 10)) == []

    def test_fuse_rrf_merges_and_counts_unbridged(self, db):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        _seed(db)
        svc = DocumentsHybridSearch(db=db)
        lexical = [{"source": "ingested", "id": "doc_a", "title": "t"}]
        vector = [
            {"id": "doc_a"},  # bridged
            {"id": "ghost"},  # unbridged — still returned, flagged bridged:false
        ]
        fused, unbridged = svc._fuse_rrf(lexical, vector)
        assert unbridged == 1
        assert len(fused) == 2
        merged = [r for r in fused if r["id"] == "doc_a"][0]
        assert set(merged["legs"]) == {"lexical", "vector"}
        assert merged["rrf"] > 0
        ghost = [r for r in fused if r["id"] == "ghost"][0]
        assert ghost["legs"] == ["vector"]
        assert ghost["bridged"] is False

    def test_fuse_rrf_hydration_failure(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch(db=None)
        with patch.object(svc, "_get_db", side_effect=RuntimeError("db down")):
            fused, unbridged = svc._fuse_rrf(
                [{"source": "ingested", "id": "1", "title": "t"}],
                [{"id": "1"}],
            )
        # Lexical leg still fused; vector leg unbridged (hydration failed)
        assert unbridged == 1
        assert fused and fused[0]["legs"] == ["lexical"]

    def test_hydrate_shape(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        svc = DocumentsHybridSearch()
        out = svc._hydrate(
            [
                {
                    "source": "ingested",
                    "id": "1",
                    "title": "t",
                    "preview": "p",
                    "rrf": 0.05,
                    "modified": None,
                    "bridged": True,
                }
            ]
        )
        assert out[0]["score"] == round(0.05, 6)
        assert out[0]["bridged"] is True

    def test_response_shape(self):
        from core.hybrid_search.documents_hybrid import DocumentsHybridSearch

        resp = DocumentsHybridSearch._response("q", [{"id": 1}], "bm25_vector_rrf", {"a": 1})
        assert resp["query"] == "q"
        assert resp["hybrid"] == "bm25_vector_rrf"
        assert resp["stats"] == {"a": 1}


class TestBackfillMatcherGaps:
    def test_match_external_id(self, db):
        from core.hybrid_search.backfill_matcher import match_pg_row

        _seed(db)
        assert match_pg_row(db, {"external_id": "e1"}, "l1") == "doc_a"

    def test_match_external_id_absent(self, db):
        from core.hybrid_search.backfill_matcher import match_pg_row

        _seed(db)
        assert match_pg_row(db, {"external_id": "nope"}, "l1") is None

    def test_match_file_name(self, db):
        from core.hybrid_search.backfill_matcher import match_pg_row

        _seed(db)
        assert match_pg_row(db, {"file_name": "revenue_report.pdf"}, "l1") == "doc_a"

    def test_match_file_name_with_integration(self, db):
        from core.hybrid_search.backfill_matcher import match_pg_row

        _seed(db)
        assert match_pg_row(db, {"file_name": "revenue_report.pdf", "integration_id": "google_drive"}, "l1") == "doc_a"

    def test_match_file_name_no_integration_match(self, db):
        from core.hybrid_search.backfill_matcher import match_pg_row

        _seed(db)
        assert match_pg_row(db, {"file_name": "revenue_report.pdf", "integration_id": "other"}, "l1") is None

    def test_no_metadata(self, db):
        from core.hybrid_search.backfill_matcher import match_pg_row

        assert match_pg_row(db, {}, "l1") is None
